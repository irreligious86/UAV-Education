#!/usr/bin/env python3
"""End-to-end vision pipeline on a video + telemetry log (per-vision-pipeline lab).

capture -> undistort -> detect (HSV/contour or YOLO) -> track (Kalman + association, SORT-lite)
-> geo-reference (pixel -> ray -> ground with ATTITUDE/GLOBAL_POSITION_INT interpolated at the
exposure time stamp) -> velocity command with watchdog/timeout interlock.
Logs per-stage latency and writes targets.csv (one row per frame).

python3 pipeline.py data [--att-offset-ms 0] [--detector hsv|yolo] [--undistort frame|point]
                                  [--select lock|maxhits]
"""
import argparse, bisect, csv, math, os, sys, time
import cv2, numpy as np

sys.path.insert(0, os.environ.get("CAMGEO_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "perception")))   # examples/perception/camgeo.py
import camgeo as cg

# ---- camera (from calibration; here the generator's values) ----------------------------------
K = cg.K_matrix(400.0, 400.0, 320.0, 240.0)
DIST = np.array([-0.10, 0.02, 0.0, 0.0, 0.0])
R_BC = cg.R_bc_for_mount(90)             # nadir camera, top of frame = forward
TARGET_R_M = 0.40                        # physical radius of the target (for the size gate)
R_E = 6378137.0

# ---- interlock / command -------------------------------------------------------------------
KP, V_MAX = 0.8, 2.0                     # 1/s, m/s
WATCHDOG_S, TIMEOUT_S = 0.5, 3.0


class Telemetry:
    """ATTITUDE and GLOBAL_POSITION_INT streams with their own time stamps, interpolated at t."""
    def __init__(self, path):
        self.att, self.gpi = [], []
        for r in csv.DictReader(open(path)):
            t = int(r["time_boot_ms"]) / 1000.0
            if r["msg"] == "ATTITUDE":
                self.att.append((t, float(r["a"]), float(r["b"]), float(r["c"])))
            else:
                self.gpi.append((t, int(r["a"]) / 1e7, int(r["b"]) / 1e7, int(r["c"]) / 1000.0))
        self.t_att = [a[0] for a in self.att]
        self.t_gpi = [g[0] for g in self.gpi]

    @staticmethod
    def _interp(ts, rows, t):
        i = bisect.bisect_right(ts, t)
        if i <= 0: return rows[0][1:]
        if i >= len(ts): return rows[-1][1:]
        (t0, *a), (t1, *b) = rows[i - 1], rows[i]
        w = (t - t0) / (t1 - t0)
        return [x + w * (y - x) for x, y in zip(a, b)]

    def attitude(self, t):
        r, p, y = self._interp(self.t_att, self.att, t)
        return r, p, y

    def position(self, t):
        lat, lon, agl = self._interp(self.t_gpi, self.gpi, t)
        return lat, lon, agl


class Track:
    """Constant-velocity Kalman track in pixels; SORT-style confirm/age bookkeeping."""
    _next_id = 1

    def __init__(self, u, v, fps):
        kf = cv2.KalmanFilter(4, 2)
        dt = 1.0 / fps
        kf.transitionMatrix = np.array([[1, 0, dt, 0], [0, 1, 0, dt], [0, 0, 1, 0], [0, 0, 0, 1]], np.float32)
        kf.measurementMatrix = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], np.float32)
        kf.processNoiseCov = np.diag([1, 1, 25, 25]).astype(np.float32)
        kf.measurementNoiseCov = np.diag([4, 4]).astype(np.float32)
        kf.statePost = np.array([[u], [v], [0], [0]], np.float32)
        self.kf, self.hits, self.misses = kf, 1, 0
        self.id = Track._next_id; Track._next_id += 1

    def predict(self):
        s = self.kf.predict(); return float(s[0, 0]), float(s[1, 0])

    def update(self, u, v):
        self.kf.correct(np.array([[u], [v]], np.float32)); self.hits += 1; self.misses = 0

    @property
    def confirmed(self): return self.hits >= 3


class Tracker:
    def __init__(self, fps, gate_px=30, max_age=15, reacq_px=100, coast=3, select="lock"):
        self.select = select
        self.tracks, self.fps, self.gate, self.max_age, self.reacq_px, self.coast = [], fps, gate_px, max_age, reacq_px, coast
        self.lock_id, self.last_uv = None, (320.0, 240.0)     # target lock: keep one ID, re-acquire near last position

    def step(self, dets):
        preds = [t.predict() for t in self.tracks]
        used = set()
        for t, (pu, pv) in zip(self.tracks, preds):
            best, bd = None, self.gate
            for j, d in enumerate(dets):
                if j in used: continue
                dd = math.hypot(d[0] - pu, d[1] - pv)
                if dd < bd: best, bd = j, dd
            if best is None:
                t.misses += 1
            else:
                used.add(best); t.update(dets[best][0], dets[best][1])
        for j, d in enumerate(dets):
            if j not in used: self.tracks.append(Track(d[0], d[1], self.fps))
        self.tracks = [t for t in self.tracks if t.misses <= self.max_age]
        live = [t for t in self.tracks if t.confirmed and t.misses <= self.coast]   # coast through short gaps
        if not live: return None
        locked = [t for t in live if t.id == self.lock_id]
        if self.select == "maxhits":            # naive rule (for the lab): the track seen most often wins
            best = max(live, key=lambda t: t.hits)
        elif locked:
            best = locked[0]
        else:                                   # (re)acquire: the confirmed track closest to where the target was
            dist = lambda t: math.hypot(t.kf.statePost[0, 0] - self.last_uv[0], t.kf.statePost[1, 0] - self.last_uv[1])
            best = min(live, key=dist)
            if dist(best) > self.reacq_px: return None          # a confirmed blob far from the target is not the target
            self.lock_id = best.id
        s = best.kf.statePost
        self.last_uv = (float(s[0, 0]), float(s[1, 0]))
        return best.id, float(s[0, 0]), float(s[1, 0])


def detect_hsv(frame, agl):
    """Orange disc: HSV gate -> open -> contours -> size (from AGL) and fill-ratio gates."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (5, 120, 70), (25, 255, 255))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    r_exp = TARGET_R_M * K[0, 0] / max(agl, 1.0)                  # expected radius in px
    a_min, a_max = math.pi * (0.8 * r_exp) ** 2, math.pi * (1.3 * r_exp) ** 2
    out = []
    for c in cnts:
        a = cv2.contourArea(c)
        if not (a_min <= a <= a_max): continue
        (u, v), r = cv2.minEnclosingCircle(c)
        fill = a / (math.pi * r * r)                               # disc ≈ 0.85; a motion-blurred streak < 0.5
        if fill < 0.6: continue
        out.append((u, v, a, min(1.0, fill)))
    return out


_yolo = None
def detect_yolo(frame, agl):
    """YOLOv8n/11n path (COCO weights will not know an orange disc: fine-tune first, see module)."""
    global _yolo
    if _yolo is None:
        from ultralytics import YOLO
        _yolo = YOLO(os.environ.get("YOLO_WEIGHTS", "yolo11n.pt"))
    res = _yolo.predict(frame, imgsz=320, conf=0.25, verbose=False)[0]
    out = []
    for b in res.boxes:
        x1, y1, x2, y2 = b.xyxy[0].tolist()
        out.append(((x1 + x2) / 2, (y1 + y2) / 2, (x2 - x1) * (y2 - y1), float(b.conf[0])))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data"); ap.add_argument("--att-offset-ms", type=float, default=0.0)
    ap.add_argument("--detector", default="hsv", choices=("hsv", "yolo"))
    ap.add_argument("--undistort", default="frame", choices=("frame", "point"))
    ap.add_argument("--select", default="lock", choices=("lock", "maxhits"))
    args = ap.parse_args()
    point_only = args.undistort == "point"
    tel = Telemetry(os.path.join(args.data, "telemetry.csv"))
    cap = cv2.VideoCapture(os.path.join(args.data, "flight.mp4"))
    fps = cap.get(cv2.CAP_PROP_FPS)
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    map1, map2 = cv2.initUndistortRectifyMap(K, DIST, None, K, (W, H), cv2.CV_16SC2)
    detect = detect_yolo if args.detector == "yolo" else detect_hsv
    trk = Tracker(fps, select=args.select)
    out = csv.writer(open(os.path.join(args.data, "targets.csv"), "w", newline=""))
    out.writerow(["frame", "t_us", "state", "track_id", "u", "v", "n", "e", "lat", "lon", "angle_x", "angle_y",
                  "vx", "vy", "lat_cap", "lat_und", "lat_det", "lat_trk", "lat_geo", "lat_cmd", "lat_total"])
    lat = {k: [] for k in ("cap", "und", "det", "trk", "geo", "cmd", "total")}
    last_seen, i = 0.0, 0
    while True:
        t0 = time.perf_counter()
        ok, frame = cap.read()
        if not ok: break
        t_us = int(i / fps * 1e6)                   # exposure time stamp (from the camera driver in real life)
        t1 = time.perf_counter()
        img = frame if point_only else cv2.remap(frame, map1, map2, cv2.INTER_LINEAR)
        t2 = time.perf_counter()
        t_frame = t_us / 1e6
        lat_v, lon_v, agl = tel.position(t_frame)
        dets = detect(img, agl)
        t3 = time.perf_counter()
        hit = trk.step(dets)
        t4 = time.perf_counter()
        n = e = lat_t = lon_t = ax = ay = float("nan"); tid = 0
        if hit:
            tid, u, v = hit
            if point_only:                                    # undistort just the point
                u, v = cv2.undistortPoints(np.array([[[u, v]]], np.float64), K, DIST, P=K)[0, 0]
            roll, pitch, yaw = tel.attitude(t_frame + args.att_offset_ms / 1000.0)
            g = cg.pixel_to_ground(u, v, K, roll, pitch, yaw, agl, R_bc=R_BC)
            if g is not None:
                n, e = float(g[0]), float(g[1])
                lat_t = lat_v + math.degrees(n / R_E)
                lon_t = lon_v + math.degrees(e / (R_E * math.cos(math.radians(lat_v))))
                ax, ay = cg.landing_target_angles(u, v, K)
                last_seen = t_frame
        t5 = time.perf_counter()
        age = t_frame - last_seen
        if age <= WATCHDOG_S and not math.isnan(n):
            state, vx, vy = "TRACK", max(-V_MAX, min(V_MAX, KP * n)), max(-V_MAX, min(V_MAX, KP * e))
        elif age <= TIMEOUT_S:
            state, vx, vy = "HOLD", 0.0, 0.0                          # watchdog: zero velocity, stay GUIDED
        else:
            state, vx, vy = "LOITER", 0.0, 0.0                        # timeout: hand back to the autopilot
        t6 = time.perf_counter()
        d = dict(cap=t1 - t0, und=t2 - t1, det=t3 - t2, trk=t4 - t3, geo=t5 - t4, cmd=t6 - t5, total=t6 - t0)
        for k, v_ in d.items(): lat[k].append(v_ * 1000)
        out.writerow([i, t_us, state, tid, f"{u:.1f}" if hit else "", f"{v:.1f}" if hit else "",
                      f"{n:.3f}", f"{e:.3f}", f"{lat_t:.7f}", f"{lon_t:.7f}", f"{ax:.4f}", f"{ay:.4f}",
                      f"{vx:.2f}", f"{vy:.2f}"] + [f"{d[k] * 1000:.2f}" for k in ("cap", "und", "det", "trk", "geo", "cmd", "total")])
        i += 1
    print(f"{i} frames @ {fps:.0f} fps, detector={args.detector}, undistort={'point only' if point_only else 'full frame'}, select={args.select}, "
          f"att offset {args.att_offset_ms:+.0f} ms")
    print(f"{'stage':8s}{'p50 ms':>9s}{'p95 ms':>9s}{'max ms':>9s}")
    for k in ("cap", "und", "det", "trk", "geo", "cmd", "total"):
        a = np.array(lat[k]); print(f"{k:8s}{np.percentile(a, 50):9.2f}{np.percentile(a, 95):9.2f}{a.max():9.2f}")


if __name__ == "__main__":
    main()
