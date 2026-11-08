#!/usr/bin/env python3
"""Inspection mission along a line object (power line, pipe, fence) — project #6 starter.

  python plan.py line.csv --offset 15 --alt 30 --trigger 5 --out mission.waypoints

line.csv: lat,lon per row (the object's centreline). The vehicle flies parallel to it at --offset metres
(positive = right of the direction of travel), shooting every --trigger metres, then returns (RTL).
Output: QGC WPL 110 text that Mission Planner and QGroundControl both import.
"""
from __future__ import annotations

import argparse
import csv
import math

R_EARTH = 6378137.0
CMD_TAKEOFF, CMD_WAYPOINT, CMD_RTL, CMD_CAM_DIST = 22, 16, 20, 206


def to_local(lat, lon, lat0, lon0):
    return (math.radians(lat - lat0) * R_EARTH, math.radians(lon - lon0) * R_EARTH * math.cos(math.radians(lat0)))


def to_global(n, e, lat0, lon0):
    return (lat0 + math.degrees(n / R_EARTH), lon0 + math.degrees(e / (R_EARTH * math.cos(math.radians(lat0)))))


def offset_polyline(pts_ne: list[tuple[float, float]], d: float) -> list[tuple[float, float]]:
    """Parallel polyline at distance d (right of travel for d > 0); mitred joints, mitre limited to 4·d."""
    out = []
    n = len(pts_ne)
    for i in range(n):
        dirs = []
        if i > 0:
            dirs.append((pts_ne[i][0] - pts_ne[i - 1][0], pts_ne[i][1] - pts_ne[i - 1][1]))
        if i < n - 1:
            dirs.append((pts_ne[i + 1][0] - pts_ne[i][0], pts_ne[i + 1][1] - pts_ne[i][1]))
        normals = []
        for dn, de in dirs:
            L = math.hypot(dn, de)
            normals.append((-de / L, dn / L))          # right-hand normal in (N, E): rotate travel by -90°
        nn = sum(v[0] for v in normals) / len(normals); ne = sum(v[1] for v in normals) / len(normals)
        L = math.hypot(nn, ne)
        if L < 1e-9:
            nn, ne = normals[0]; L = 1.0
        nn, ne = nn / L, ne / L
        cos_half = sum(nn * v[0] + ne * v[1] for v in normals) / len(normals)
        k = min(d / max(cos_half, 1e-6), 4 * abs(d)) if d >= 0 else max(d / max(cos_half, 1e-6), -4 * abs(d))
        out.append((pts_ne[i][0] + nn * k, pts_ne[i][1] + ne * k))
    return out


def plan(line: list[tuple[float, float]], offset: float, alt: float, trigger: float) -> list[dict]:
    lat0, lon0 = line[0]
    local = [to_local(la, lo, lat0, lon0) for la, lo in line]
    path = [to_global(n, e, lat0, lon0) for n, e in offset_polyline(local, offset)]
    items = [dict(cmd=CMD_TAKEOFF, lat=0, lon=0, alt=alt)]
    items.append(dict(cmd=CMD_WAYPOINT, lat=path[0][0], lon=path[0][1], alt=alt))
    items.append(dict(cmd=CMD_CAM_DIST, p1=trigger, lat=0, lon=0, alt=0))        # start shooting at the first point
    for la, lo in path[1:]:
        items.append(dict(cmd=CMD_WAYPOINT, lat=la, lon=lo, alt=alt))
    items.append(dict(cmd=CMD_CAM_DIST, p1=0, lat=0, lon=0, alt=0))              # stop before the way home
    items.append(dict(cmd=CMD_RTL, lat=0, lon=0, alt=0))
    return items


def length_m(line):
    lat0, lon0 = line[0]
    loc = [to_local(a, b, lat0, lon0) for a, b in line]
    return sum(math.hypot(loc[i + 1][0] - loc[i][0], loc[i + 1][1] - loc[i][1]) for i in range(len(loc) - 1))


def to_wpl(items, home) -> str:
    rows = ["QGC WPL 110", f"0\t1\t0\t16\t0\t0\t0\t0\t{home[0]:.7f}\t{home[1]:.7f}\t0\t1"]
    for k, it in enumerate(items, start=1):
        frame = 3   # MAV_FRAME_GLOBAL_RELATIVE_ALT
        rows.append(f"{k}\t0\t{frame}\t{it['cmd']}\t{it.get('p1', 0)}\t0\t0\t0\t{it['lat']:.7f}\t{it['lon']:.7f}\t{it['alt']}\t1")
    return "\n".join(rows) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv"); ap.add_argument("--offset", type=float, default=15); ap.add_argument("--alt", type=float, default=30)
    ap.add_argument("--trigger", type=float, default=5); ap.add_argument("--out", default="mission.waypoints")
    a = ap.parse_args()
    with open(a.csv) as f:
        line = [(float(r["lat"]), float(r["lon"])) for r in csv.DictReader(f)]
    items = plan(line, a.offset, a.alt, a.trigger)
    open(a.out, "w").write(to_wpl(items, line[0]))
    print(f"{len(items)} items, line {length_m(line):.0f} m, ≈{length_m(line) / a.trigger:.0f} photos")


if __name__ == "__main__":
    main()
