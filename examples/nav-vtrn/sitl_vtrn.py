#!/usr/bin/env python3
"""nav-vtrn SITL lab: closed loop "camera -> map matching -> GPS_INPUT -> EKF3" on ArduCopter 4.6.3.

The copter flies in SITL over the SYNTHETIC orthophoto of vtrn_lab.py. A "vision node" renders the nadir
camera frame from the simulator's true pose (stabilised camera: roll/pitch are not rendered), runs VO at
5 Hz and map matching every 2 s (worker thread), fuses them in the lab's 2-state Kalman filter and
publishes the estimate as a second GPS (GPS2_TYPE = 14, MAVLink GPS_INPUT, gps_id = 1) at 5 Hz.
Scenario: take-off to 100 m, 400 m north with GNSS (vision in the shadow), SIM_GPS_DISABLE = 1, 250 m east
and 400 m south on vision alone (with a 60 m wrong fix injected for 4 s), RTL; below 45 m EKF3 is switched
to source set 2 (SITL optical flow + rangefinder) for the landing.

Start SITL first (instance 3 -> TCP 5790); home = map point x=300 m, y=700 m:
  mkdir -p sitl3 && cd sitl3 && <ardupilot>/build/sitl/bin/arducopter -S --model + --speedup 1 -I 3 -w \
     --defaults <ardupilot>/Tools/autotest/default_params/copter.parm --home 55.693712,37.504782,150,0
Then:  python3 sitl_vtrn.py tcp:127.0.0.1:5790 [--lake] [--no-map-yaw] [--pos-only]
  --lake        leg B is 550 m and crosses the featureless lake (expected: BLIND -> EKF failsafe -> LAND)
  --no-map-yaw  rotate VO by ATTITUDE.yaw only, without the heading correction from the homography
  --pos-only    after GNSS loss switch EKF3 to source set 3 (GPS position without GPS velocity)
Afterwards:  python3 dfsum.py sitl3/logs/00000001.BIN   (which GPS the EKF used, XKF3/XKF4 statistics)
"""
import math
import os
import sys
import threading
import time

os.environ["MAVLINK20"] = "1"          # GPS_INPUT.yaw and GPS2_RAW.h_acc are MAVLink 2 extension fields
import cv2
import numpy as np
from pymavlink import mavutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vtrn_lab as lab

URL = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "tcp:127.0.0.1:5790"
GPS_EPOCH, LEAP_S = 315964800, 18
R = lab.R_EARTH
HOME_XY = (300.0, 700.0)               # map metres: x east, y south of the top-left corner
ALT = 100.0                            # flight altitude AGL, m (GSD 0.2 m/px, footprint 128 x 96 m)
AGL_MAP_MIN = 40.0                     # below this a frame covers < 51 x 38 m: too few map features, no map fixes
AGL_VO_MIN = 40.0                      # below this the vision node reports "no fix" (on a real texture VO works lower;
                                       # the synthetic 0.25 m/px map magnified 4-6x gives VO nothing but blur and noise)
BLIND_FRAMES = 10                      # VO lost for 10 frames (2 s) -> report NO FIX instead of dead-reckoned guesses
AGL_FLOW = 45.0                        # on the final descent switch EKF3 to source set 2 = optical flow, m
AGL_SCALE = 1.013                      # AGL known to 1.3 % (rangefinder/baro error), as in the Python lab
N_MAP = 10                             # map fix every 10th frame (2 s at 5 Hz)
YAW_FROM_MAP = "--no-map-yaw" not in sys.argv   # correct the AHRS heading by the rotation left in the homography
POS_ONLY = "--pos-only" in sys.argv             # after GNSS loss switch EKF3 to source set 3 (GPS position, no GPS velocity)
LAKE = "--lake" in sys.argv                     # leg B crosses the 220 m featureless lake (x = 586..806 m)
X_EAST = 850.0 if LAKE else 550.0
T0 = time.time()


def xy_from_latlon(lat, lon):
    return ((lon - lab.LON0) * math.pi / 180 * R * math.cos(math.radians(lab.LAT0)),
            (lab.LAT0 - lat) * math.pi / 180 * R)


class Link:
    def __init__(self):
        self.lock, self.tx = threading.Lock(), threading.Lock()
        self.texts = []
        self.connect()

    def connect(self):
        self.m = mavutil.mavlink_connection(URL, source_system=255)
        self.m.wait_heartbeat(timeout=90)
        with self.tx:
            self.m.mav.request_data_stream_send(self.m.target_system, self.m.target_component,
                                                mavutil.mavlink.MAV_DATA_STREAM_ALL, 20, 1)
        self.last, self.t_recv = {}, {}

    def pump(self, seconds, quiet=False):
        t_end = time.time() + seconds
        while time.time() < t_end:
            msg = self.m.recv_match(blocking=True, timeout=0.1)
            if msg is None:
                continue
            t = msg.get_type()
            with self.lock:
                self.last[t] = msg
                self.t_recv[t] = time.time()
            if t == "STATUSTEXT":
                self.texts.append(msg.text)
                if not quiet:
                    print(f"    [{time.time() - T0:5.0f} s] STATUSTEXT: {msg.text}", flush=True)

    def get(self, t):
        with self.lock:
            return self.last.get(t)

    def set_param(self, name, value):
        with self.tx:
            self.m.mav.param_set_send(self.m.target_system, self.m.target_component, name.encode(), float(value),
                                      mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        for _ in range(30):
            msg = self.m.recv_match(type="PARAM_VALUE", blocking=True, timeout=1)
            if msg and msg.param_id == name:
                print(f"  set {name} = {msg.param_value:g}")
                return
        print(f"  {name}: no ack")

    def cmd(self, cmd, *args):
        with self.tx:
            self.m.mav.command_long_send(self.m.target_system, self.m.target_component, cmd, 0, *(list(args) + [0] * (7 - len(args))))
        ack = self.m.recv_match(type="COMMAND_ACK", blocking=True, timeout=3)
        return ack.result if ack else None

    def mode(self):
        return mavutil.mode_string_v10(self.get("HEARTBEAT"))


class VisionNode:
    """one 5 Hz loop: render the frame, VO step, Kalman predict, GPS_INPUT; map matching every 2 s in a worker
    thread, applied as a delayed measurement when it is ready."""

    def __init__(self, link, flightimg, mapdb):
        self.link, self.img, self.db = link, flightimg, mapdb
        self.rng = np.random.default_rng(3)
        self.state = "PREFLIGHT"                 # PREFLIGHT -> TRACKING <-> BLIND -> LOST (below the working altitude)
        self.blind_n = self.gate_n = self.k_track = 0
        self.xy = np.array(HOME_XY)              # estimate, map metres (x east, y south)
        self.P = np.eye(2) * 25.0
        self.vel_dr = np.zeros(2)                # smoothed velocity for dead reckoning, m/s
        self.have_vel = False
        self.prev, self.t_prev = None, 0.0
        self.k = 0
        self.d_since_fix = 0.0
        self.n_rej = 0
        self.pending = None                      # snapshot waiting for the map-matching worker
        self.result = None
        self.offset = np.zeros(2)                # fault injection: constant error added to the output, m
        self.sent = 0
        self.fix_stats = []                      # (t, err_m, sigma, inliers, ms, accepted)
        self.vo_fail = 0
        self.yaw_bias = 0.0                      # rad, learned from map fixes: true heading = AHRS yaw + bias
        self.err_hist = []                       # (t, error of the estimate against truth at frame time, sigma)
        self.lock = threading.Lock()
        threading.Thread(target=self.loop, daemon=True).start()
        threading.Thread(target=self.worker, daemon=True).start()

    def truth(self):
        sim, gpi, att = self.link.get("SIMSTATE"), self.link.get("GLOBAL_POSITION_INT"), self.link.get("ATTITUDE")
        if sim is None or gpi is None or att is None:
            return None
        x, y = xy_from_latlon(sim.lat * 1e-7, sim.lng * 1e-7)
        return (x, y, sim.yaw - math.pi / 2, max(gpi.relative_alt / 1000.0, 0.5), att.yaw - math.pi / 2,
                self.link.t_recv["SIMSTATE"])    # receive time of the truth sample = "exposure timestamp" of the frame

    def note(self, text):
        print(f"    [{time.time() - T0:5.0f} s] vision: {text}", flush=True)

    def send(self, xy, vel, hacc, sacc, fix):
        gpi = self.link.get("GLOBAL_POSITION_INT")
        xy = xy + self.offset
        lat, lon = lab.to_latlon(xy[0], xy[1])
        now = time.time()
        gps_s = now - GPS_EPOCH + LEAP_S
        with self.link.tx:
            self.link.m.mav.gps_input_send(
                int(now * 1e6), 1,                   # gps_id 1 = second receiver (GPS2)
                mavutil.mavlink.GPS_INPUT_IGNORE_FLAG_VDOP | mavutil.mavlink.GPS_INPUT_IGNORE_FLAG_VEL_VERT,
                int((gps_s % 604800) * 1000), int(gps_s // 604800), fix,
                int(lat * 1e7), int(lon * 1e7), gpi.alt / 1000.0,
                1.0, 0.0,                            # hdop (EK3_GPS_CHECK wants <= 2.5); vdop ignored
                float(-vel[1]), float(vel[0]), 0.0,  # vn, ve from VO; vd ignored
                float(sacc),                         # speed_accuracy, m/s
                float(hacc), 3.0,                    # horiz_accuracy = filter sigma (floor 1 m), vert_accuracy
                8 if fix == 3 else 0,                # "satellites": >= 6 for EK3_GPS_CHECK, < 10 so that UseBest prefers real GNSS
                0)                                   # yaw 0 = not provided
        self.sent += 1

    def loop(self):
        nxt = time.time()
        while True:
            nxt += 0.2
            time.sleep(max(0.0, nxt - time.time()))
            tr = self.truth()
            if tr is None:
                continue
            x_t, y_t, psi_t, agl_t, psi_ahrs, t_sim = tr
            agl_est = agl_t * AGL_SCALE
            psi_est = psi_ahrs + self.yaw_bias
            if self.state == "PREFLIGHT":
                if agl_est < AGL_MAP_MIN:            # the camera sees nothing useful: report the known take-off point
                    self.send(np.array(HOME_XY), np.zeros(2), 5.0, 0.5, 3)
                    continue
                self.state, self.prev = "TRACKING", None
                self.P = np.eye(2) * 15.0 ** 2       # drift during the climb is unknown: 15 m
                self.note(f"AGL {agl_est:.0f} m >= {AGL_MAP_MIN:.0f} m: TRACKING, start from the take-off point, sigma 15 m")
            if self.state in ("TRACKING", "BLIND") and agl_est < AGL_VO_MIN:
                self.state = "LOST"
                self.note(f"AGL {agl_est:.0f} m < {AGL_VO_MIN:.0f} m: frame footprint too small, reporting NO FIX")
            if self.state == "LOST":
                self.send(self.xy, np.zeros(2), 99.0, 0.5, 1)
                continue
            frame = lab.cut_frame(self.img, x_t, y_t, psi_t, agl_t, self.rng)   # the "camera"
            with self.lock:
                d, v, vo_ok = np.zeros(2), np.zeros(2), True
                if self.prev is not None:
                    dt = t_sim - self.t_prev
                    if dt < 0.04:                    # no new truth sample since the last frame
                        continue
                    r = lab.vo_step(self.prev, frame, agl_est)
                    if r is not None:
                        fwd, rgt = r[0], r[1]
                        d = np.array([fwd * math.cos(psi_est) - rgt * math.sin(psi_est),
                                      fwd * math.sin(psi_est) + rgt * math.cos(psi_est)])
                        v = d / dt
                        # sanity gate: a copter does not change speed by 6 m/s between frames; such a step is a false match
                        if np.hypot(*v) > 25.0 or (self.have_vel and np.hypot(*(v - self.vel_dr)) > 6.0):
                            self.gate_n += 1
                            if self.gate_n < 3:      # ... unless it repeats: then the reference is stale, not the measurement
                                r = None
                            else:
                                self.have_vel = False
                        else:
                            self.gate_n = 0
                    if r is not None:
                        self.vel_dr = v if not self.have_vel else 0.7 * self.vel_dr + 0.3 * v
                        self.have_vel = True
                        self.blind_n = 0
                    else:                            # dead reckoning with the smoothed velocity
                        v, vo_ok = self.vel_dr, False
                        d = v * dt
                        self.vo_fail += self.state == "TRACKING"
                        self.blind_n += 1
                        if self.blind_n == BLIND_FRAMES and self.state == "TRACKING":
                            self.state = "BLIND"
                            self.note(f"no VO for {BLIND_FRAMES} frames ({BLIND_FRAMES * 0.2:.0f} s): BLIND, reporting NO FIX until a map fix relocalises")
                    self.xy = self.xy + d
                    dist = float(np.hypot(*d))
                    self.P = self.P + np.eye(2) * (0.03 ** 2 * (2 * self.d_since_fix * dist + dist * dist)
                                                   + (0.05 if vo_ok else 0.5) ** 2)
                    self.d_since_fix += dist
                self.prev, self.t_prev = frame, t_sim
                self.k += 1
                if self.result is not None:
                    self.apply(self.result)
                    self.result = None
                if self.k % N_MAP == 0 and self.pending is None and agl_est >= AGL_MAP_MIN:
                    self.pending = (frame, self.xy.copy(), self.P.copy(), psi_est, agl_est, (x_t, y_t))
                if self.state == "TRACKING":
                    self.k_track += 1
                    self.err_hist.append((time.time() - T0, float(np.hypot(self.xy[0] - x_t, self.xy[1] - y_t)), math.sqrt(self.P[0, 0])))
                # position and velocity of one measurement must refer to one moment: the middle of the last VO step
                out_xy, hacc = self.xy - 0.5 * d, max(1.0, math.sqrt(self.P[0, 0]))
            if self.state == "BLIND":
                self.send(out_xy, np.zeros(2), 99.0, 0.5, 1)
            else:
                self.send(out_xy, v, hacc, 0.5 if vo_ok else 1.0, 3)   # EKF3 drops a GPS whose filtered sAcc exceeds 1.5 m/s

    # ---- worker: map matching takes 25-200 ms, so it must not block VO or the 5 Hz output ---------
    def worker(self):
        while True:
            time.sleep(0.02)
            p = self.pending
            if p is None or self.result is not None:
                continue
            frame, xy, P, psi, agl, tr = p
            search = float(np.clip(3 * math.sqrt(P[0, 0]), 30.0, 150.0))     # search radius = 3 sigma of the prior
            prior = xy
            if self.state == "BLIND":                # no usable prior: match against the whole 1 km2 map (~0.3-1 s)
                prior, search = np.array([lab.MAP_PX * lab.GSD_MAP / 2] * 2), 1500.0
            fx = lab.map_fix(self.db, frame, prior[0], prior[1], psi, agl, search_m=search)
            with self.lock:
                self.result = (fx, xy, P, tr)
                self.pending = None

    def apply(self, res):
        fx, xy_snap, P_snap, tr = res
        if fx is None:
            self.fix_stats.append((time.time() - T0, None, None, 0, None, False))
            return
        mx, my, sig, ninl, nm, ms, rot = fx
        z = np.array([float(mx), float(my)])
        err = float(np.hypot(z[0] - tr[0], z[1] - tr[1]))
        if YAW_FROM_MAP:      # rot = heading error seen by the map, valid even if the position gate rejects the fix;
            self.yaw_bias += 0.5 * float(np.clip(rot, -math.radians(6), math.radians(6)))   # noisy (1-2 deg): filter and clip
        nu = z - xy_snap                              # innovation at the moment the frame was taken
        if self.state == "BLIND":                     # relocalisation: no prior to gate against, so demand a strong match
            if ninl >= 25:
                self.xy, self.P, self.n_rej, self.d_since_fix = self.xy + nu, np.eye(2) * max(sig, 1.0) ** 2, 0, 0.0
                self.state, self.blind_n = "TRACKING", 0
                self.note(f"relocalised by a whole-map match: {ninl} inliers, true error {err:.1f} m -> TRACKING")
            self.fix_stats.append((time.time() - T0, err, sig, ninl, ms, ninl >= 25))
            return
        S = P_snap + np.eye(2) * sig ** 2
        ok = bool(nu @ np.linalg.solve(S, nu) < 11.8)
        if ok:
            K = P_snap @ np.linalg.inv(S)
            self.xy = self.xy + K @ nu                # VO increments since the frame are relative: shift the present state
            self.P = self.P - K @ P_snap
            self.n_rej, self.d_since_fix = 0, 0.0
        else:
            self.n_rej += 1
            self.note(f"map fix REJECTED by the 3-sigma gate: innovation {np.hypot(*nu):.1f} m, fix sigma {sig:.2f} m, "
                      f"prior sigma {math.sqrt(P_snap[0, 0]):.1f} m, true fix error {err:.1f} m")
            if self.n_rej >= 3:
                self.xy, self.P, self.n_rej, self.d_since_fix = self.xy + nu, np.eye(2) * sig ** 2, 0, 0.0
                self.note("3 rejections in a row: reset to the fix")
        self.fix_stats.append((time.time() - T0, err, sig, ninl, ms, ok))


def ekf_err(link):
    sim, gpi = link.get("SIMSTATE"), link.get("GLOBAL_POSITION_INT")
    dlat = (gpi.lat - sim.lat) * 1e-7 * math.pi / 180 * R
    dlon = (gpi.lon - sim.lng) * 1e-7 * math.pi / 180 * R * math.cos(math.radians(sim.lat * 1e-7))
    return math.hypot(dlat, dlon)


def vis_err(link):
    """error of what the autopilot received as GPS2 against the simulator's truth"""
    sim, g2 = link.get("SIMSTATE"), link.get("GPS2_RAW")
    if g2 is None:
        return float("nan")
    dlat = (g2.lat - sim.lat) * 1e-7 * math.pi / 180 * R
    dlon = (g2.lon - sim.lng) * 1e-7 * math.pi / 180 * R * math.cos(math.radians(sim.lat * 1e-7))
    return math.hypot(dlat, dlon)


def line(link, vn=None):
    g1, g2, e = link.get("GPS_RAW_INT"), link.get("GPS2_RAW"), link.get("EKF_STATUS_REPORT")
    s = f"GPS1 fix={g1.fix_type} sats={g1.satellites_visible:2d}" if g1 else "GPS1 -"
    s += f" | GPS2 fix={g2.fix_type} sats={g2.satellites_visible} h_acc={g2.h_acc / 1000:4.1f} m err={vis_err(link):4.1f} m" if g2 else " | GPS2 -"
    if e:
        s += f" | EKF pos_var={e.pos_horiz_variance:.2f} vel_var={e.velocity_variance:.2f} flags=0x{e.flags:04x}"
    s += f" | EKF err={ekf_err(link):4.1f} m"
    att, sim = link.get("ATTITUDE"), link.get("SIMSTATE")
    s += f" yaw_err={math.degrees((att.yaw - sim.yaw + math.pi) % (2 * math.pi) - math.pi):+.1f} deg"
    if vn is not None:
        s += f" | map yaw corr {math.degrees(vn.yaw_bias):+.1f} deg"
    return s + f" | {link.mode()}"


def goto(link, x, y, label, vn, timeout=150, every=10, on_tick=None):
    lat, lon = lab.to_latlon(x, y)
    with link.tx:
        link.m.mav.set_position_target_global_int_send(0, link.m.target_system, link.m.target_component,
                                                       mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, 0b110111111000,
                                                       int(lat * 1e7), int(lon * 1e7), ALT, 0, 0, 0, 0, 0, 0, 0, 0)
    errs, verrs = [], []
    for i in range(timeout):
        link.pump(1)
        sim = link.get("SIMSTATE")
        tx, ty = xy_from_latlon(sim.lat * 1e-7, sim.lng * 1e-7)
        errs.append(ekf_err(link))
        verrs.append(vis_err(link))
        if on_tick:
            on_tick(i)
        if i % every == every - 1:
            print(f"  {label} t+{i + 1:3d} s x={tx:4.0f} y={ty:4.0f} | " + line(link, vn), flush=True)
        if link.mode() != "GUIDED":
            print(f"  {label}: ABORTED, mode changed to {link.mode()}", flush=True)
            return None, None
        if math.hypot(tx - x, ty - y) < 3.0:
            break
    print(f"  {label}: reached in {i + 1} s; EKF-vs-truth error mean {np.mean(errs):.2f} m, max {max(errs):.2f} m; "
          f"GPS2(vision)-vs-truth mean {np.nanmean(verrs):.2f} m, max {np.nanmax(verrs):.2f} m", flush=True)
    return errs, verrs


def report(vn):
    ok = [f for f in vn.fix_stats if f[1] is not None]
    acc = [f for f in ok if f[5]]
    eh = np.array([e[1] for e in vn.err_hist])
    print(f"== summary: GPS_INPUT sent {vn.sent}; map fixes attempted {len(vn.fix_stats)}, matched {len(ok)}, accepted {len(acc)}; "
          f"fix error median {np.median([f[1] for f in ok]):.2f} m, p90 {np.percentile([f[1] for f in ok], 90):.2f} m, max {max(f[1] for f in ok):.2f} m; "
          f"match time median {np.median([f[4] for f in ok]):.0f} ms, max {max(f[4] for f in ok):.0f} ms; VO failures {vn.vo_fail} of {vn.k_track} frames while TRACKING")
    print(f"   vision estimate vs truth at frame time (TRACKING): median {np.median(eh):.2f} m, p90 {np.percentile(eh, 90):.2f} m, max {eh.max():.2f} m; "
          f"heading correction learned from the map {math.degrees(vn.yaw_bias):+.1f} deg")
    import json
    json.dump({"err_hist": [(round(a, 1), round(b, 2), round(c, 2)) for a, b, c in vn.err_hist],
               "fixes": [(round(f[0], 1), None if f[1] is None else round(f[1], 2), f[5]) for f in vn.fix_stats]},
              open(os.environ.get("VTRN_JSON", "sitl_series.json"), "w"))


def main():
    print("building the synthetic map and its ORB database ...", flush=True)
    rng = np.random.default_rng(1)
    cv2.setRNGSeed(1)
    mapimg, cell = lab.make_map()
    mapdb = lab.MapFeatures(cv2.cvtColor(mapimg, cv2.COLOR_BGR2GRAY), "orb")
    flightimg = lab.season_variant(mapimg, cell, rng)
    hl = lab.to_latlon(*HOME_XY)
    print(f"  map 1024 x 1024 m, {len(mapdb.pts)} features; home = map ({HOME_XY[0]:.0f}, {HOME_XY[1]:.0f}) m = {hl[0]:.6f}, {hl[1]:.6f}")
    L = Link()
    global T0
    T0 = time.time()
    print("== step 1: second GPS of MAVLink type, reboot")
    L.set_param("GPS2_TYPE", 14)           # 14 = MAVLink (GPS_INPUT)
    L.set_param("GPS_AUTO_SWITCH", 1)      # 1 = UseBest (default)
    L.set_param("GPS2_DELAY_MS", 100)      # our output is extrapolated to "now": ~0.1 s old, not the 0.2 s assumed for MAVLink GPS
    L.set_param("RTL_ALT", 10000)          # return at 100 m: the vision node needs its working altitude
    # source set 2 for the last 45 m: optical flow + rangefinder (SITL sensors), baro height, compass yaw
    for name, val in (("SIM_FLOW_ENABLE", 1), ("FLOW_TYPE", 10), ("RNGFND1_TYPE", 1), ("RNGFND1_MIN_CM", 0), ("RNGFND1_MAX_CM", 4000),
                      ("RNGFND1_SCALING", 12.12), ("RNGFND1_PIN", 0),
                      ("EK3_SRC2_POSXY", 0), ("EK3_SRC2_VELXY", 5), ("EK3_SRC2_POSZ", 1), ("EK3_SRC2_VELZ", 0), ("EK3_SRC2_YAW", 1),
                      # source set 3 (experiment --pos-only): lat/lon from the vision GPS, no GPS velocity
                      ("EK3_SRC3_POSXY", 3), ("EK3_SRC3_VELXY", 0), ("EK3_SRC3_POSZ", 1), ("EK3_SRC3_VELZ", 0), ("EK3_SRC3_YAW", 1)):
        L.set_param(name, val)
    L.cmd(mavutil.mavlink.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN, 1)
    time.sleep(6)
    L.connect()
    L.pump(5, quiet=True)

    print("== step 2: GPS_INPUT at 5 Hz from the vision node (PREFLIGHT: take-off point, h_acc 5 m); wait for EKF")
    vn = VisionNode(L, flightimg, mapdb)
    L.pump(30, quiet=True)
    print("  " + line(L))
    print("  STATUSTEXT so far:", [t for t in L.texts if "GPS" in t or "origin" in t])

    print("== step 3: GUIDED, arm, take-off to 100 m")
    L.m.set_mode_apm("GUIDED")
    L.pump(2, quiet=True)
    for _ in range(15):
        r = L.cmd(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 1)
        L.pump(1)
        if L.get("HEARTBEAT").base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED:
            break
    print("  arm result", r, "armed:", bool(L.get("HEARTBEAT").base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED))
    L.cmd(mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, ALT)
    for i in range(90):
        L.pump(1)
        if i % 10 == 9:
            print(f"  climb t+{i + 1:2d} s alt={L.get('GLOBAL_POSITION_INT').relative_alt / 1000:5.1f} m | " + line(L, vn), flush=True)
        if L.get("GLOBAL_POSITION_INT").relative_alt > (ALT - 1.5) * 1000:
            break

    print("== step 4: leg A, 400 m north with GNSS: vision runs in the shadow (GPS1 is primary)")
    goto(L, 300, 300, "A", vn)
    ok = [f for f in vn.fix_stats if f[1] is not None]
    print(f"  map fixes so far: {len(vn.fix_stats)} attempted, {len(ok)} matched, {sum(f[5] for f in ok)} accepted; "
          f"error median {np.median([f[1] for f in ok]):.2f} m, max {max(f[1] for f in ok):.2f} m; match time median {np.median([f[4] for f in ok]):.0f} ms")

    print(f"== step 5: GNSS loss (SIM_GPS_DISABLE = 1), leg B: {X_EAST - 300:.0f} m east" + (" across the lake" if LAKE else "") + " on vision only")
    L.set_param("SIM_GPS_DISABLE", 1)
    for _ in range(10):
        L.pump(0.5)
        if L.get("GPS_RAW_INT").fix_type < 3:
            break
    if POS_ONLY:
        r = L.cmd(mavutil.mavlink.MAV_CMD_SET_EKF_SOURCE_SET, 3)
        print(f"  GPS1 fix_type {L.get('GPS_RAW_INT').fix_type}: MAV_CMD_SET_EKF_SOURCE_SET 3 -> result {r} (0 = accepted)")
    n0 = len(vn.fix_stats)
    if goto(L, X_EAST, 300, "B", vn)[0] is None:
        report(vn)
        return
    seg = vn.fix_stats[n0:]
    print(f"  leg B map fixes: {len(seg)} attempted, {sum(1 for f in seg if f[1] is not None)} matched; VO failures so far {vn.vo_fail}")

    print("== step 6: leg C, 400 m south; a wrong fix (+60 m east) is sent for 4 s in the middle")
    def fault(i):
        if i == 15:
            vn.offset = np.array([60.0, 0.0])
            print("  >>> fault on: vision output shifted 60 m east", flush=True)
        if 15 <= i < 19:
            print(f"  fault t+{i - 14} s | " + line(L, vn), flush=True)
        if i == 19:
            vn.offset = np.zeros(2)
            print("  >>> fault off", flush=True)
    if goto(L, X_EAST, 700, "C", vn, on_tick=fault)[0] is None:
        report(vn)
        return

    print(f"== step 7: RTL without GNSS: {X_EAST - 300:.0f} m back to the take-off point, then descent")
    L.m.set_mode_apm("RTL")
    errs, on_flow, landed_err = [], False, None
    for i in range(400):
        L.pump(1)
        sim, gpi = L.get("SIMSTATE"), L.get("GLOBAL_POSITION_INT")
        tx, ty = xy_from_latlon(sim.lat * 1e-7, sim.lng * 1e-7)
        d_home = math.hypot(tx - HOME_XY[0], ty - HOME_XY[1])
        if vn.state == "TRACKING" and not on_flow:
            errs.append(ekf_err(L))
        if not on_flow and d_home < 10 and gpi.relative_alt < AGL_FLOW * 1000:
            r = L.cmd(mavutil.mavlink.MAV_CMD_SET_EKF_SOURCE_SET, 2)
            on_flow = True
            print(f"  alt {gpi.relative_alt / 1000:.1f} m: MAV_CMD_SET_EKF_SOURCE_SET 2 (optical flow) -> result {r}; "
                  f"{d_home:.1f} m from home, EKF err {ekf_err(L):.1f} m", flush=True)
        if i % 10 == 9:
            print(f"  RTL t+{i + 1:3d} s alt={gpi.relative_alt / 1000:5.1f} m, {d_home:5.1f} m from home (truth) | " + line(L, vn), flush=True)
        if not L.get("HEARTBEAT").base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED:
            landed_err = d_home
            break
    print(f"  RTL on vision down to {AGL_FLOW:.0f} m: EKF-vs-truth error mean {np.mean(errs):.2f} m, max {max(errs):.2f} m")
    print(f"  disarmed after {i + 1} s; touchdown {landed_err:.1f} m from the take-off point (truth)" if landed_err is not None else "  did not land in time")
    report(vn)
    print("done")


if __name__ == "__main__":
    main()
