#!/usr/bin/env python3
"""nav-vtrn lab: VO drift vs map-matching fixes vs fusion on a synthetic orthophoto.

Map-tile servers are not reachable from the authoring sandbox, so the "satellite map" is SYNTHETIC:
value-noise fields, Voronoi field boundaries, roads, tree clumps, buildings and a featureless lake,
rendered at 0.25 m/px (4096 x 4096 px = 1024 x 1024 m). The flight path, camera frames, VO,
map matching and fusion are real OpenCV code; only the terrain picture is generated.

Usage: python3 vtrn_lab.py [--out out]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time

import cv2
import numpy as np

# ---------------------------------------------------------------- map ---------------------------
GSD_MAP = 0.25            # m/px of the "orthophoto"
MAP_PX = 4096             # 1024 m x 1024 m
LAT0, LON0 = 55.7000, 37.5000   # georeference of the top-left corner (fake, north-up)
R_EARTH = 6378137.0


def value_noise(size: int, octaves=(16, 32, 64, 128, 256), rng=None, persistence=0.55) -> np.ndarray:
    rng = rng or np.random.default_rng(0)
    out = np.zeros((size, size), np.float32)
    amp = 1.0
    for cells in octaves:
        g = rng.random((cells + 1, cells + 1)).astype(np.float32)
        layer = cv2.resize(g, (size, size), interpolation=cv2.INTER_CUBIC)
        out += amp * layer
        amp *= persistence
    out -= out.min()
    out /= out.max()
    return out


def make_map(seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = MAP_PX
    base = value_noise(n, rng=rng)                                  # soil / crop tone
    fine = value_noise(n, octaves=(256, 512, 1024), rng=rng, persistence=0.6)   # crop rows / texture
    # Voronoi "fields": each cell gets its own tone and texture strength
    pts = rng.random((60, 2)) * n
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    cell = np.zeros((n, n), np.int32)
    best = np.full((n, n), np.inf, np.float32)
    for i, (px, py) in enumerate(pts):
        d = (xx - px) ** 2 + (yy - py) ** 2
        m = d < best
        best[m] = d[m]
        cell[m] = i
    tone = rng.uniform(0.35, 0.85, 60)[cell].astype(np.float32)
    tex = rng.uniform(0.05, 0.45, 60)[cell].astype(np.float32)
    img = tone * 0.6 + base * 0.25 + (fine - 0.5) * tex
    # crop rows: directional stripes in some fields
    ang = rng.uniform(0, math.pi, 60)
    rows = np.sin((xx * np.cos(ang[cell]) + yy * np.sin(ang[cell])) * 2 * math.pi / 12.0)
    striped = (rng.random(60) < 0.5)[cell]
    img += np.where(striped, rows * 0.04, 0)
    img = np.clip(img, 0, 1)
    col = np.stack([img * 0.75 + 0.05, img * 0.85 + 0.05, img * 0.55], axis=-1)   # greenish-brown
    col = (col * 255).astype(np.uint8)
    # field boundaries (dark lines between Voronoi cells)
    edges = cv2.Canny(cell.astype(np.uint8), 0, 1)
    col[edges > 0] = (60, 70, 55)
    # roads: a few long polylines, light grey with dark shoulders
    for _ in range(5):
        p = rng.random((4, 2)) * n
        p[0, rng.integers(0, 2)] = rng.choice([0, n - 1])
        cv2.polylines(col, [p.astype(np.int32)], False, (120, 125, 130), 10)
        cv2.polylines(col, [p.astype(np.int32)], False, (175, 180, 185), 6)
    # tree clumps
    for _ in range(900):
        c = (int(rng.integers(0, n)), int(rng.integers(0, n)))
        r = int(rng.integers(3, 14))
        g = int(rng.integers(40, 90))
        cv2.circle(col, c, r, (25, g, 30), -1)
    # buildings
    for _ in range(80):
        x, y = rng.integers(0, n - 60, 2)
        w, h = rng.integers(12, 60, 2)
        col[y:y + h, x:x + w] = (rng.integers(150, 230),) * 3
        col[y + h:y + h + 3, x:x + w] = (40, 40, 40)
    # featureless lake: low-texture blue disk, 220 m across
    cx, cy, r = int(n * 0.68), int(n * 0.30), int(110 / GSD_MAP)
    lake = np.zeros((n, n), np.uint8)
    cv2.circle(lake, (cx, cy), r, 255, -1)
    col[lake > 0] = (95, 80, 60)          # flat colour: real water has no static texture to track
    return col, cell


def season_variant(col: np.ndarray, cell: np.ndarray, rng) -> np.ndarray:
    """what the camera sees months after the orthophoto was taken: per-field tone change (crops grew
    or were harvested), softer optics, some new tree clumps. Roads, buildings and the lake stay."""
    gain = rng.uniform(0.65, 1.35, 60).astype(np.float32)[cell]
    img = col.astype(np.float32) * gain[..., None]
    img = cv2.GaussianBlur(img, (0, 0), 1.2)
    out = np.clip(img, 0, 255).astype(np.uint8)
    for _ in range(150):
        c = (int(rng.integers(0, MAP_PX)), int(rng.integers(0, MAP_PX)))
        cv2.circle(out, c, int(rng.integers(3, 12)), (25, int(rng.integers(40, 90)), 30), -1)
    return out


# ---------------------------------------------------------------- camera / flight -----------------
FX = 500.0                 # px
W, H = 640, 480
AGL = 100.0                # m
SPEED = 10.0               # m/s
DT = 0.5                   # s between frames (2 Hz)
N_MAP = 10                 # map-matching every N frames (5 s)


def truth_path(n_frames: int):
    """closed-ish loop with turns: x east, y north in metres from map origin (top-left, y down!)."""
    out = []
    x, y, psi = 260.0, 400.0, 0.0
    for k in range(n_frames):
        t = k * DT
        # heading programme: straight, left turn, straight, right turn ... (deg/s)
        rate = 0.0
        if 20 <= t < 32:
            rate = +7.5
        elif 60 <= t < 72:
            rate = +7.5
        elif 100 <= t < 112:
            rate = +7.5
        elif 150 <= t < 162:
            rate = +7.5          # closes the loop; the last east leg crosses the lake
        psi += math.radians(rate) * DT
        x += SPEED * DT * math.cos(psi)
        y += SPEED * DT * math.sin(psi)
        out.append((x, y, psi))
    return out


def cut_frame(mapimg, x, y, psi, agl, rng):
    """nadir camera frame at (x,y) m, heading psi, altitude agl: rotate+scale crop of the map plus
    illumination change and sensor noise. Frame 'up' = flight direction."""
    gsd_cam = agl / FX                       # m/px seen by the camera
    s = GSD_MAP / gsd_cam                    # map px -> cam px
    cx, cy = x / GSD_MAP, y / GSD_MAP
    M = cv2.getRotationMatrix2D((cx, cy), math.degrees(psi) + 90, s)   # heading -> image up
    M[0, 2] += W / 2 - cx
    M[1, 2] += H / 2 - cy
    f = cv2.warpAffine(mapimg, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gain = rng.uniform(0.75, 1.25)
    g = g * gain + rng.uniform(-25, 25)
    g += rng.normal(0, 6, g.shape)
    return np.clip(g, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- VO ----------------------------
ORB = cv2.ORB_create(nfeatures=1500, scaleFactor=1.2, nlevels=8, fastThreshold=12)
BF = cv2.BFMatcher(cv2.NORM_HAMMING)


def match(d1, d2, ratio=0.8):
    if d1 is None or d2 is None or len(d1) < 8 or len(d2) < 8:
        return []
    good = []
    for pair in BF.knnMatch(d1, d2, k=2):
        if len(pair) == 2 and pair[0].distance < ratio * pair[1].distance:
            good.append(pair[0])
    return good


def vo_step(prev, cur, agl_est):
    """frame-to-frame similarity (R, t, s) with RANSAC -> body-frame displacement in metres."""
    k1, d1 = ORB.detectAndCompute(prev, None)
    k2, d2 = ORB.detectAndCompute(cur, None)
    m = match(d1, d2)
    if len(m) < 12:
        return None
    p1 = np.float32([k1[a.queryIdx].pt for a in m])
    p2 = np.float32([k2[a.trainIdx].pt for a in m])
    A, inl = cv2.estimateAffinePartial2D(p1, p2, method=cv2.RANSAC, ransacReprojThreshold=2.0)
    if A is None or inl.sum() < 12:
        return None
    dtheta = math.atan2(A[1, 0], A[0, 0])        # image rotation between frames (rad)
    # A = [sR | t] rotates about the image origin, so take the motion of the image CENTRE:
    c = np.array([W / 2, H / 2, 1.0])
    tx, ty = -(A @ c - c[:2])                    # the scene moved by -t; image 'up' (−v) is flight direction
    gsd = agl_est / FX
    forward, right = -ty * gsd, tx * gsd
    return forward, right, -dtheta, int(inl.sum()), len(m)


# ---------------------------------------------------------------- map matching -------------------
AKAZE = (cv2.xfeatures2d_AKAZE if hasattr(cv2, "xfeatures2d_AKAZE") else cv2.AKAZE).create(threshold=0.0008)   # OpenCV 5 moved AKAZE to xfeatures2d
BF_AKAZE = cv2.BFMatcher(cv2.NORM_HAMMING)
ORB_MAP = cv2.ORB_create(nfeatures=1200, scaleFactor=1.2, nlevels=8, fastThreshold=12)
ORB_FRAME = cv2.ORB_create(nfeatures=2500, scaleFactor=1.2, nlevels=8, fastThreshold=12)


class MapFeatures:
    """feature database of the orthophoto, built ONCE offline (tile by tile so that features are spread
    evenly over the map, not only on the busiest fields). A companion loads this from disk at boot."""

    def __init__(self, mapgray: np.ndarray, detector="orb", tile=512):
        t0 = time.perf_counter()
        det = ORB_MAP if detector == "orb" else AKAZE
        pts, descs = [], []
        for ty in range(0, mapgray.shape[0], tile):
            for tx in range(0, mapgray.shape[1], tile):
                k, d = det.detectAndCompute(mapgray[ty:ty + tile, tx:tx + tile], None)
                if d is None:
                    continue
                pts.append(np.float32([(p.pt[0] + tx, p.pt[1] + ty) for p in k]))
                descs.append(d)
        self.pts = np.concatenate(pts)
        self.desc = np.concatenate(descs)
        self.build_s = time.perf_counter() - t0

    def window(self, x0, y0, x1, y1):
        m = (self.pts[:, 0] >= x0) & (self.pts[:, 0] < x1) & (self.pts[:, 1] >= y0) & (self.pts[:, 1] < y1)
        return self.pts[m], self.desc[m]


def map_fix(mapdb, frame, x_pred, y_pred, psi_pred, agl_est, search_m=150.0, detector="orb"):
    """georeference a frame: rectify to map scale and heading using AGL + intrinsics + predicted yaw,
    match against a map window around the predicted position, homography + RANSAC, map the frame
    centre to map px -> metres. Returns (x, y, sigma_m, n_inliers, n_matches, ms, rot) or None;
    rot = rotation left in the homography, rad: the error of psi_pred, i.e. an absolute heading measurement."""
    t0 = time.perf_counter()
    gsd_cam = agl_est / FX
    s = gsd_cam / GSD_MAP                                # cam px -> map px
    # rectify: rotate so that map north is up, scale to map GSD
    rot = -(math.degrees(psi_pred) + 90)
    Wr, Hr = int(W * s * 1.5), int(H * s * 1.5)
    M = cv2.getRotationMatrix2D((W / 2, H / 2), rot, s)
    M[0, 2] += Wr / 2 - W / 2
    M[1, 2] += Hr / 2 - H / 2
    rect = cv2.warpAffine(frame, M, (Wr, Hr), flags=cv2.INTER_LINEAR, borderValue=0)
    # map window
    r = int(search_m / GSD_MAP) + max(Wr, Hr) // 2
    cx, cy = int(x_pred / GSD_MAP), int(y_pred / GSD_MAP)
    x0, y0 = max(cx - r, 0), max(cy - r, 0)
    x1, y1 = min(cx + r, MAP_PX), min(cy + r, MAP_PX)
    pw_all, dw = mapdb.window(x0, y0, x1, y1)           # map features inside the search window (map px)
    det = ORB_FRAME if detector == "orb" else AKAZE
    bf = BF if detector == "orb" else BF_AKAZE
    kf, df = det.detectAndCompute(rect, None)
    if df is None or len(df) < 8 or len(dw) < 8:
        return None
    good = []
    for pair in bf.knnMatch(df, dw, k=2):
        if len(pair) == 2 and pair[0].distance < 0.8 * pair[1].distance:
            good.append(pair[0])
    if len(good) < 15:
        return None
    pf = np.float32([kf[a.queryIdx].pt for a in good])
    pw = pw_all[[a.trainIdx for a in good]] - np.float32([x0, y0])
    Hm, inl = cv2.findHomography(pf, pw, cv2.RANSAC, 3.0)
    if Hm is None or inl.sum() < 15:
        return None
    inl = inl.ravel().astype(bool)
    c = cv2.perspectiveTransform(np.float32([[[Wr / 2, Hr / 2]]]), Hm)[0, 0]
    # sanity: homography must be close to a similarity (no wild skew/scale) for a nadir frame
    sc = math.sqrt(abs(Hm[0, 0] * Hm[1, 1] - Hm[0, 1] * Hm[1, 0]))
    if not 0.8 < sc < 1.25:                  # more than 25 % scale mismatch = wrong AGL or wrong match
        return None
    # covariance proxy: residual RMS of inliers / sqrt(n), scaled by map GSD, floor 0.5 m
    proj = cv2.perspectiveTransform(pf[inl].reshape(-1, 1, 2), Hm).reshape(-1, 2)
    rms = float(np.sqrt(((proj - pw[inl]) ** 2).sum(1).mean()))
    sigma = max(0.5, 3.0 * rms * GSD_MAP / math.sqrt(inl.sum()) + 0.004 * search_m)
    ms = (time.perf_counter() - t0) * 1e3
    rot = math.atan2(Hm[1, 0] - Hm[0, 1], Hm[0, 0] + Hm[1, 1])
    return (x0 + c[0]) * GSD_MAP, (y0 + c[1]) * GSD_MAP, sigma, int(inl.sum()), len(good), ms, rot


def to_latlon(x_m, y_m):
    lat = LAT0 - (y_m / R_EARTH) * 180 / math.pi
    lon = LON0 + (x_m / (R_EARTH * math.cos(math.radians(LAT0)))) * 180 / math.pi
    return lat, lon


# ---------------------------------------------------------------- VPR (coarse) -------------------
VPR_SIDE = 96.0            # m: square north-up patch described by one global vector
VPR_STEP = 32.0            # m: grid step of the reference database


def global_descriptor(img: np.ndarray) -> np.ndarray:
    """hand-made stand-in for a learned global descriptor (NetVLAD, AnyLoc, ...): a 16x16 thumbnail of
    intensity plus an 8x8 map of gradient energy, each zero-mean and L2-normalised -> 320 floats."""
    g = cv2.resize(img, (64, 64), interpolation=cv2.INTER_AREA).astype(np.float32)
    t = cv2.resize(cv2.GaussianBlur(g, (0, 0), 2), (16, 16), interpolation=cv2.INTER_AREA)
    t -= t.mean()
    g2 = cv2.resize(img, (128, 128), interpolation=cv2.INTER_AREA).astype(np.float32)
    m = cv2.resize(np.hypot(cv2.Sobel(g2, cv2.CV_32F, 1, 0), cv2.Sobel(g2, cv2.CV_32F, 0, 1)), (8, 8), interpolation=cv2.INTER_AREA)
    m -= m.mean()
    return np.concatenate([(t / (np.linalg.norm(t) + 1e-6)).ravel(), (m / (np.linalg.norm(m) + 1e-6)).ravel()])


def vpr_database(mapgray):
    n, st = int(VPR_SIDE / GSD_MAP), int(VPR_STEP / GSD_MAP)
    pos, db = [], []
    for y0 in range(0, MAP_PX - n + 1, st):
        for x0 in range(0, MAP_PX - n + 1, st):
            db.append(global_descriptor(mapgray[y0:y0 + n, x0:x0 + n]))
            pos.append(((x0 + n / 2) * GSD_MAP, (y0 + n / 2) * GSD_MAP))
    return np.array(db), np.array(pos)


def vpr_query(frame, psi, agl_est):
    """rectify the frame to a north-up VPR_SIDE patch (yaw from the compass, scale from AGL) and describe it"""
    s = (agl_est / FX) / GSD_MAP
    n = int(VPR_SIDE / GSD_MAP)
    M = cv2.getRotationMatrix2D((W / 2, H / 2), -(math.degrees(psi) + 90), s)
    M[0, 2] += n / 2 - W / 2
    M[1, 2] += n / 2 - H / 2
    return global_descriptor(cv2.warpAffine(frame, M, (n, n), borderMode=cv2.BORDER_REFLECT))


# ---------------------------------------------------------------- main ----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    ap.add_argument("--frames", type=int, default=460)
    ap.add_argument("--detector", default="orb", choices=["orb", "akaze"])
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--agl-bias", type=float, default=None, help="AGL estimate error in m (default: random ±2 m)")
    ap.add_argument("--yaw-from", default="ahrs", choices=["ahrs", "vo"],
                    help="heading source: 'ahrs' = autopilot attitude (gyro+compass, 0.5 deg noise, slow drift); 'vo' = integrate image rotation")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    rng = np.random.default_rng(args.seed)
    cv2.setRNGSeed(args.seed)                 # RANSAC in OpenCV uses its own generator

    t0 = time.perf_counter()
    mapimg, cell = make_map()
    mapgray = cv2.cvtColor(mapimg, cv2.COLOR_BGR2GRAY)          # the georeferenced reference ("orthophoto")
    flightimg = season_variant(mapimg, cell, rng)               # the terrain as seen on the flight day
    cv2.imwrite(os.path.join(args.out, "map_flight_day.jpg"), cv2.resize(flightimg, (1024, 1024)), [cv2.IMWRITE_JPEG_QUALITY, 85])
    cv2.imwrite(os.path.join(args.out, "map_synthetic.jpg"), cv2.resize(mapimg, (1024, 1024)), [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"synthetic map {MAP_PX}x{MAP_PX} px @ {GSD_MAP} m/px = {MAP_PX * GSD_MAP:.0f} m side, built in {time.perf_counter() - t0:.1f} s (SYNTHETIC DATA)")

    truth = truth_path(args.frames)
    # AGL estimate: barometric, slow bias up to +2 m (2 %), as on a real quad without rangefinder
    agl_bias = rng.uniform(-2.0, 2.0) if args.agl_bias is None else args.agl_bias
    agl_est = AGL + agl_bias
    print(f"camera {W}x{H}, f={FX:.0f} px, AGL {AGL:.0f} m -> GSD {AGL / FX:.3f} m/px, footprint {W * AGL / FX:.0f}x{H * AGL / FX:.0f} m; AGL estimate used: {agl_est:.2f} m")

    mapdb = MapFeatures(mapgray, args.detector)
    print(f"map feature database ({args.detector.upper()}): {len(mapdb.pts)} features, {mapdb.desc.nbytes / 1e6:.1f} MB, built in {mapdb.build_s:.1f} s")
    frames = [cut_frame(flightimg, x, y, p, AGL, rng) for (x, y, p) in truth]
    # heading as a companion would get it from ATTITUDE: compass-aided yaw, 0.5 deg noise + slow 0.01 deg/s walk
    walk = np.cumsum(rng.normal(0, math.radians(0.01) * DT, len(truth)))
    yaw_ahrs = [p + w + rng.normal(0, math.radians(0.5)) for (_, _, p), w in zip(truth, walk)]
    print(f"heading source: {args.yaw_from}")
    cv2.imwrite(os.path.join(args.out, "frame_000.png"), frames[0])
    cv2.imwrite(os.path.join(args.out, "frame_100.png"), frames[100])

    # --- VO only ---
    x_vo, y_vo, psi_vo = truth[0]            # start known (take-off point)
    vo_tr = [(x_vo, y_vo)]
    vo_stats = []
    t_vo = []
    for k in range(1, len(frames)):
        t1 = time.perf_counter()
        r = vo_step(frames[k - 1], frames[k], agl_est)
        t_vo.append((time.perf_counter() - t1) * 1e3)
        if r is None:                      # tracking lost: dead-reckon with the last displacement
            vo_stats.append((k, 0, 0))
            x_vo, y_vo = 2 * x_vo - vo_tr[-2][0] if len(vo_tr) > 1 else x_vo, 2 * y_vo - vo_tr[-2][1] if len(vo_tr) > 1 else y_vo
            vo_tr.append((x_vo, y_vo))
            continue
        fwd, rgt, dpsi, ninl, nm = r
        psi_vo = psi_vo + dpsi if args.yaw_from == "vo" else yaw_ahrs[k]
        # body -> map (x east, y "down" on the image = south): heading psi measured in map px frame
        x_vo += fwd * math.cos(psi_vo) - rgt * math.sin(psi_vo)
        y_vo += fwd * math.sin(psi_vo) + rgt * math.cos(psi_vo)
        vo_tr.append((x_vo, y_vo))
        vo_stats.append((k, ninl, nm))

    # --- map only + fused ---
    kf_x, kf_y = truth[0][0], truth[0][1]
    P = np.eye(2) * 0.25
    S_VO = 0.03                # VO scale/heading error budget: 3 % of distance since the last accepted fix (bias-like)
    d_since_fix = 0.0
    psi_f = truth[0][2]
    last_d = (0.0, 0.0)
    n_rej = 0
    fused_tr = [(kf_x, kf_y)]
    map_fixes = []             # (k, x, y, sigma, n_inl, n_match, ms, err)
    map_only = {}
    t_map = []
    for k in range(1, len(frames)):
        r = vo_step(frames[k - 1], frames[k], agl_est)
        if r is not None:
            fwd, rgt, dpsi, _, _ = r
            psi_f = psi_f + dpsi if args.yaw_from == "vo" else yaw_ahrs[k]
            dx = fwd * math.cos(psi_f) - rgt * math.sin(psi_f)
            dy = fwd * math.sin(psi_f) + rgt * math.cos(psi_f)
            last_d = (dx, dy)
        else:
            dx, dy = last_d                                   # constant-velocity dead reckoning
            if args.yaw_from == "ahrs":
                psi_f = yaw_ahrs[k]
        kf_x += dx
        kf_y += dy
        d = math.hypot(dx, dy)
        # a scale/heading bias gives error ~ S_VO * D, so variance (S_VO*D)^2: add its increment per step,
        # plus per-step noise (0.05 m with tracking, 1 m when dead-reckoning)
        P += np.eye(2) * (S_VO ** 2 * (2 * d_since_fix * d + d * d) + (0.05 if r is not None else 1.0) ** 2)
        d_since_fix += d
        if k % N_MAP == 0:
            fx = map_fix(mapdb, frames[k], kf_x, kf_y, psi_f, agl_est, detector=args.detector)
            if fx is not None:
                mx, my, sig, ninl, nm, ms, _rot = fx
                t_map.append(ms)
                mx, my = float(mx), float(my)
                err = math.hypot(mx - truth[k][0], my - truth[k][1])
                map_fixes.append((k, mx, my, sig, ninl, nm, ms, err))
                map_only[k] = (mx, my)
                # KF update with R = sigma^2 I, 3-sigma gate
                z = np.array([mx, my])
                xk = np.array([kf_x, kf_y])
                S = P + np.eye(2) * sig ** 2
                nu = z - xk
                if nu @ np.linalg.solve(S, nu) < 11.8:   # chi-square, 2 dof, p = 0.997 ("3 sigma")
                    K = P @ np.linalg.inv(S)
                    xk = xk + K @ nu
                    P = (np.eye(2) - K) @ P
                    kf_x, kf_y = xk
                    n_rej = 0
                    d_since_fix = 0.0
                    # yaw correction from the fix is left out on purpose (see module text)
                else:
                    n_rej += 1
                    print(f"  frame {k}: fix rejected by 3-sigma gate (innovation {np.hypot(*nu):.1f} m, sigma {sig:.1f} m)")
                    if n_rej >= 3:                        # like EK3_GLITCH_RAD: after repeated rejections, reset to the fix
                        kf_x, kf_y = mx, my
                        P = np.eye(2) * sig ** 2
                        n_rej = 0
                        d_since_fix = 0.0
                        print(f"  frame {k}: 3 rejections in a row -> position reset to the fix")
            else:
                t_map.append(float("nan"))
                map_fixes.append((k, None, None, None, 0, 0, float("nan"), None))
        fused_tr.append((kf_x, kf_y))

    # --- report ---
    dist = [0.0]
    for k in range(1, len(truth)):
        dist.append(dist[-1] + math.hypot(truth[k][0] - truth[k - 1][0], truth[k][1] - truth[k - 1][1]))
    err_vo = [math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(vo_tr, truth)]
    err_f = [math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(fused_tr, truth)]
    ok = [f for f in map_fixes if f[1] is not None]
    print(f"\nVO: {len(frames) - 1} steps, inliers median {int(np.median([s[1] for s in vo_stats]))}, "
          f"{np.mean(t_vo):.1f} ms/step on this machine; failures {sum(1 for s in vo_stats if s[1] == 0)}")
    print(f"path length {dist[-1]:.0f} m, {len(frames)} frames at {1 / DT:.0f} Hz, {SPEED:.0f} m/s")
    print("VO-only error [m] at distance:")
    for d_target in (100, 250, 500, 1000, 1500, dist[-1]):
        k = min(range(len(dist)), key=lambda i: abs(dist[i] - d_target))
        print(f"  {dist[k]:6.0f} m -> {err_vo[k]:6.1f} m ({100 * err_vo[k] / max(dist[k], 1):.1f} % of path)")
    print(f"map fixes attempted {len(map_fixes)}, succeeded {len(ok)}; "
          f"err median {np.median([f[7] for f in ok]):.2f} m, p90 {np.percentile([f[7] for f in ok], 90):.2f} m, max {max(f[7] for f in ok):.2f} m; "
          f"sigma reported median {np.median([f[3] for f in ok]):.2f} m; inliers median {int(np.median([f[4] for f in ok]))}; "
          f"{np.nanmean(t_map):.0f} ms per fix")
    fails = [f[0] for f in map_fixes if f[1] is None]
    print(f"map fix failures at frames {fails} (positions: {[tuple(round(v) for v in truth[k][:2]) for k in fails]})")
    print(f"fused error: median {np.median(err_f):.2f} m, p90 {np.percentile(err_f, 90):.2f} m, max {max(err_f):.2f} m, final {err_f[-1]:.2f} m")
    lat, lon = to_latlon(ok[0][1], ok[0][2])
    print(f"first fix: frame {ok[0][0]} -> x={ok[0][1]:.1f} y={ok[0][2]:.1f} m -> lat {lat:.6f} lon {lon:.6f}, sigma {ok[0][3]:.2f} m, inliers {ok[0][4]}/{ok[0][5]}")

    # --- coarse localisation without any position prior ("where am I on this map?") ---
    vdb, vpos = vpr_database(mapgray)
    q = list(range(0, len(frames), 5))
    h1 = h5 = v_ok = v_bad = v_none = 0
    t_v = []
    for k in q:
        x, y, _ = truth[k]
        order = np.argsort(-(vdb @ vpr_query(frames[k], yaw_ahrs[k], agl_est)))[:5]
        e = np.hypot(vpos[order, 0] - x, vpos[order, 1] - y)
        h1 += e[0] < 64
        h5 += (e < 64).any()
        # retrieve -> verify: local features + homography around each of the 5 candidates, first that passes wins
        t1 = time.perf_counter()
        r = None
        for c in order:
            r = map_fix(mapdb, frames[k], vpos[c, 0], vpos[c, 1], yaw_ahrs[k], agl_est, search_m=64.0, detector=args.detector)
            if r is not None:
                break
        t_v.append((time.perf_counter() - t1) * 1e3)
        if r is None:
            v_none += 1
        elif math.hypot(r[0] - x, r[1] - y) < 5:
            v_ok += 1
        else:
            v_bad += 1
    print(f"VPR: {len(vdb)} reference patches {VPR_SIDE:.0f} m every {VPR_STEP:.0f} m, {vdb.shape[1]} floats each ({vdb.nbytes / 1e6:.1f} MB); "
          f"hand-made descriptor top-1 {100 * h1 / len(q):.0f} %, top-5 {100 * h5 / len(q):.0f} % of {len(q)} queries (hit = within 64 m)")
    print(f"VPR top-5 + geometric verification: correct {v_ok}, wrong {v_bad}, no answer {v_none}; {np.mean(t_v):.0f} ms per query")
    b_ok = b_bad = b_none = 0
    t_b = []
    for k in q:
        x, y, _ = truth[k]
        t1 = time.perf_counter()
        r = map_fix(mapdb, frames[k], MAP_PX * GSD_MAP / 2, MAP_PX * GSD_MAP / 2, yaw_ahrs[k], agl_est, search_m=1500.0, detector=args.detector)
        t_b.append((time.perf_counter() - t1) * 1e3)
        if r is None:
            b_none += 1
        elif math.hypot(r[0] - x, r[1] - y) < 5:
            b_ok += 1
        else:
            b_bad += 1
    print(f"brute force over the whole map ({len(mapdb.pts)} features): correct {b_ok}, wrong {b_bad}, no answer {b_none}; {np.mean(t_b):.0f} ms per query")

    # dump series for the diagram script and the SITL replay
    series = {"dist": [round(d, 1) for d in dist], "err_vo": [round(e, 2) for e in err_vo], "err_fused": [round(e, 2) for e in err_f],
              "map_fix": [(f[0], round(float(f[7]), 2), round(float(f[3]), 2)) for f in ok], "truth": [(round(x, 2), round(y, 2)) for x, y, _ in truth],
              "fix_err_xy": [(f[0], round(float(f[1] - truth[f[0]][0]), 2), round(float(f[2] - truth[f[0]][1]), 2), round(float(f[3]), 2)) for f in ok],
              "fail_frames": fails, "lat0": LAT0, "lon0": LON0,
              "vo_fail_frames": [st[0] for st in vo_stats if st[1] == 0]}
    with open(os.path.join(args.out, "series.json"), "w") as fh:
        json.dump(series, fh)
    # plot for the author
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
        ax[0].plot(dist, err_vo, label="VO only")
        ax[0].plot(dist, err_f, label="fused (KF)")
        ax[0].scatter([dist[f[0]] for f in ok], [f[7] for f in ok], s=12, c="r", label="map fix")
        ax[0].set_xlabel("distance, m"); ax[0].set_ylabel("error, m"); ax[0].legend(); ax[0].grid()
        tx, ty = zip(*[(x, y) for x, y, _ in truth])
        ax[1].imshow(mapgray, cmap="gray", extent=(0, MAP_PX * GSD_MAP, MAP_PX * GSD_MAP, 0))
        ax[1].plot(tx, ty, "g", label="truth"); ax[1].plot(*zip(*vo_tr), "b", label="VO"); ax[1].plot(*zip(*fused_tr), "r--", label="fused")
        ax[1].legend(); fig.tight_layout(); fig.savefig(os.path.join(args.out, "lab.png"), dpi=110)
    except Exception as e:  # noqa
        print("plot skipped:", e)


if __name__ == "__main__":
    main()
