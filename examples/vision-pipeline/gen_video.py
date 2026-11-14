#!/usr/bin/env python3
"""Synthetic nadir-camera flight for the per-vision-pipeline lab (no dataset needed).

Renders a textured ground plane seen from a copter at ~15 m AGL with a slowly rolling/pitching/yawing
attitude, a moving orange disc target (R = 6 m circle, 0.6 m/s), an orange "rock" distractor, dark
shadow patches, a lens with k1/k2 distortion, a 4 s exposure drop (gain 0.25), a motion-blur segment and a
2 s occlusion. Writes:
  flight.mp4        640x480 @ 30 fps, 40 s
  telemetry.csv     ATTITUDE at 50 Hz and GLOBAL_POSITION_INT at 10 Hz with their own time stamps
  truth.csv         per-frame exposure time stamp, true target and vehicle positions (for scoring)
Usage: python3 gen_video.py data
"""
import csv, math, os, sys
import cv2, numpy as np

sys.path.insert(0, os.environ.get("CAMGEO_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "perception")))   # examples/perception/camgeo.py
import camgeo as cg

W, H, FPS, T = 640, 480, 30, 40.0
FX = 400.0                       # px  (HFOV = 2*atan(320/400) = 77.3 deg)
K = cg.K_matrix(FX, FX, 320.0, 240.0)
K1, K2 = -0.10, 0.02
AGL = 15.0
LAT0, LON0 = -35.3632621, 149.1652374      # SITL CMAC home; only used to produce lat/lon numbers
R_E = 6378137.0
PX_PER_M = 20                    # ground texture resolution
WORLD = 50                       # m, texture covers [-25, 25] m N and E


def ned_to_ll(n, e):
    return LAT0 + math.degrees(n / R_E), LON0 + math.degrees(e / (R_E * math.cos(math.radians(LAT0))))


def target_pos(t):
    w = 0.6 / 6.0                          # 0.6 m/s on R = 6 m
    return 6.0 * math.cos(w * t), 6.0 * math.sin(w * t)


def vehicle_pose(t):
    tn, te = target_pos(t - 1.5)           # vehicle lags the target by 1.5 s and sits 1 m short
    n, e = 0.85 * tn, 0.85 * te
    roll = math.radians(8.0 * math.sin(2 * math.pi * 0.50 * t))
    pitch = math.radians(5.0 * math.sin(2 * math.pi * 0.35 * t + 1.0))
    yaw = math.radians(20.0 + 15.0 * math.sin(2 * math.pi * 0.05 * t))
    agl = AGL + 0.5 * math.sin(2 * math.pi * 0.1 * t)
    return n, e, roll, pitch, yaw, agl


def make_texture(rng):
    n = WORLD * PX_PER_M
    base = rng.normal(0, 1, (n // 8, n // 8)).astype(np.float32)
    base = cv2.resize(base, (n, n), interpolation=cv2.INTER_CUBIC)
    fine = rng.normal(0, 1, (n, n)).astype(np.float32)
    g = 110 + 25 * base + 12 * fine
    img = np.stack([g * 0.55, g * 0.75, g * 0.65], axis=-1)    # BGR: greenish-brown ground
    img = np.clip(img, 0, 255).astype(np.uint8)
    for i in range(0, n, 5 * PX_PER_M):                         # faint 5 m grid (field tracks)
        cv2.line(img, (i, 0), (i, n - 1), (70, 90, 80), 1)
        cv2.line(img, (0, i), (n - 1, i), (70, 90, 80), 1)
    for _ in range(25):                                         # dark shadow patches
        c = (int(rng.uniform(0, n)), int(rng.uniform(0, n)))
        ax = (int(rng.uniform(10, 60)), int(rng.uniform(10, 60)))
        cv2.ellipse(img, c, ax, rng.uniform(0, 180), 0, 360, (28, 32, 30), -1)
    # orange-ish rock, R = 0.30 m, at N = -3, E = 4  (a classic false positive for a colour detector)
    cv2.circle(img, world_to_tex(-3.0, 4.0), int(0.30 * PX_PER_M), (30, 95, 200), -1)
    return img


def world_to_tex(n, e):
    return int((e + WORLD / 2) * PX_PER_M), int((WORLD / 2 - n) * PX_PER_M)   # x = E, y = -N


def main(out):
    os.makedirs(out, exist_ok=True)
    rng = np.random.default_rng(7)
    tex = make_texture(rng)
    # distortion map: for every distorted output pixel find its ideal source pixel
    uu, vv = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    pts = np.stack([uu.ravel(), vv.ravel()], -1).reshape(-1, 1, 2)
    dist = np.array([K1, K2, 0, 0, 0], dtype=np.float64)
    ideal = cv2.undistortPoints(pts, K, dist, P=K).reshape(H, W, 2)
    map_x, map_y = ideal[..., 0].astype(np.float32), ideal[..., 1].astype(np.float32)

    vw = cv2.VideoWriter(os.path.join(out, "flight.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    truth = csv.writer(open(os.path.join(out, "truth.csv"), "w", newline=""))
    truth.writerow(["frame", "t_us", "tgt_n", "tgt_e", "veh_n", "veh_e", "roll", "pitch", "yaw", "agl", "visible"])
    nframes = int(T * FPS)
    for i in range(nframes):
        t = i / FPS
        n, e, roll, pitch, yaw, agl = vehicle_pose(t)
        tn, te = target_pos(t)
        frame_tex = tex.copy()
        visible = not (33.0 <= t < 35.0)                                    # occlusion window
        if visible:
            cv2.circle(frame_tex, world_to_tex(tn, te), int(0.40 * PX_PER_M), (20, 110, 235), -1)   # orange disc R=0.4 m
        else:
            cv2.ellipse(frame_tex, world_to_tex(tn, te), (int(1.5 * PX_PER_M), int(1.1 * PX_PER_M)), 30, 0, 360, (40, 120, 50), -1)
        # homography ground -> ideal image from four ground points (pinhole only: distortion applied after)
        src, dst = [], []
        for dn, de in ((-12, -12), (-12, 12), (12, 12), (12, -12)):          # relative to the vehicle
            u, v = cg.ground_to_pixel(dn, de, K, roll, pitch, yaw, agl, R_bc=cg.R_bc_for_mount(90))
            src.append(world_to_tex(n + dn, e + de)); dst.append((u, v))
        Hm = cv2.getPerspectiveTransform(np.float32(src), np.float32(dst))
        img = cv2.warpPerspective(frame_tex, Hm, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        img = cv2.remap(img, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        if 28.0 <= t < 30.0:                                                 # motion blur segment
            k = np.zeros((1, 41), np.float32); k[0, :] = 1 / 41
            img = cv2.filter2D(img, -1, k)
        gain = 0.25 if 20.0 <= t < 24.0 else 1.0                             # exposure drop (cloud / AE lag)
        img = np.clip(img.astype(np.float32) * gain + rng.normal(0, 3, img.shape), 0, 255).astype(np.uint8)
        vw.write(img)
        truth.writerow([i, int(t * 1e6), f"{tn:.3f}", f"{te:.3f}", f"{n:.3f}", f"{e:.3f}",
                        f"{roll:.5f}", f"{pitch:.5f}", f"{yaw:.5f}", f"{agl:.3f}", int(visible)])
    vw.release()

    # telemetry as the autopilot would stream it: ATTITUDE 50 Hz, GLOBAL_POSITION_INT 10 Hz
    with open(os.path.join(out, "telemetry.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["msg", "time_boot_ms", "a", "b", "c", "d"])
        for k in range(int(T * 50) + 1):
            t = k / 50
            n, e, roll, pitch, yaw, agl = vehicle_pose(t)
            w.writerow(["ATTITUDE", int(t * 1000), f"{roll:.5f}", f"{pitch:.5f}", f"{yaw:.5f}", ""])
        for k in range(int(T * 10) + 1):
            t = k / 10
            n, e, roll, pitch, yaw, agl = vehicle_pose(t)
            lat, lon = ned_to_ll(n, e)
            w.writerow(["GLOBAL_POSITION_INT", int(t * 1000), int(lat * 1e7), int(lon * 1e7), int(agl * 1000), int(math.degrees(yaw) * 100)])
    print(f"wrote {nframes} frames, K: fx={FX}, k1={K1}, k2={K2}, AGL≈{AGL} m, HFOV={2*math.degrees(math.atan(320/FX)):.1f}°")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data")
