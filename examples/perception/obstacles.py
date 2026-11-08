"""Obstacle sensing helpers: depth image -> OBSTACLE_DISTANCE sectors, and sector queries.

MAVLink OBSTACLE_DISTANCE carries up to 72 distances (cm) in equal sectors starting at angle_offset,
clockwise in the chosen frame (MAV_FRAME_BODY_FRD: 0 = forward, 90 = right). UINT16_MAX means
"no obstacle / unknown", max_distance+1 means "nothing within range" (see the message definition).
"""
from __future__ import annotations

import math

import numpy as np

UNKNOWN = 65535


def depth_to_sectors(depth_m: np.ndarray, hfov_deg: float, n_sectors: int = 72, min_m: float = 0.2,
                     max_m: float = 10.0, rows: slice | None = None) -> tuple[list[int], float, float]:
    """Collapse a depth image (H×W, metres, 0/NaN = invalid) into OBSTACLE_DISTANCE distances.

    Each image column has a bearing  atan((u - cx)/fx). For every 360/n sector we keep the minimum valid
    range over the columns falling in it (closest obstacle wins). Returns (distances_cm[n], increment_deg,
    angle_offset_deg) with the sectors covering only the camera's field of view filled; the rest UNKNOWN.
    """
    h, w = depth_m.shape
    fx = (w / 2) / math.tan(math.radians(hfov_deg) / 2)
    cx = (w - 1) / 2
    band = depth_m[rows] if rows is not None else depth_m[h // 3: 2 * h // 3]      # ignore floor and sky rows
    inc = 360.0 / n_sectors
    out = [UNKNOWN] * n_sectors
    for u in range(w):
        col = band[:, u]
        col = col[np.isfinite(col) & (col >= min_m)]
        bearing = math.degrees(math.atan((u - cx) / fx))
        k = int(round(bearing / inc)) % n_sectors
        if col.size == 0:
            continue
        # range along the optical axis -> slant range along the column's bearing
        r = float(col.min()) / math.cos(math.radians(bearing))
        cm = int(max_m * 100) + 1 if r > max_m else int(round(r * 100))
        out[k] = cm if out[k] == UNKNOWN else min(out[k], cm)
    return out, inc, 0.0


def closest(distances_cm: list[int], inc_deg: float, offset_deg: float = 0.0) -> tuple[float, float] | None:
    """(bearing_deg, distance_m) of the nearest valid sector, or None."""
    best = None
    for i, d in enumerate(distances_cm):
        if d == UNKNOWN:
            continue
        b = (offset_deg + i * inc_deg) % 360
        if best is None or d < best[1]:
            best = (b, d)
    return None if best is None else (best[0], best[1] / 100.0)


def stop_distance(speed: float, accel_max: float, latency_s: float, margin: float) -> float:
    """Distance needed to stop: travel during sensing+control latency, braking v²/2a, plus margin."""
    return speed * latency_s + speed * speed / (2 * accel_max) + margin


def max_safe_speed(range_m: float, accel_max: float, latency_s: float, margin: float) -> float:
    """Largest speed whose stop_distance fits into the sensor range (solves v·L + v²/2a = R − margin)."""
    avail = range_m - margin
    if avail <= 0:
        return 0.0
    a, L = accel_max, latency_s
    return -a * L + math.sqrt((a * L) ** 2 + 2 * a * avail)
