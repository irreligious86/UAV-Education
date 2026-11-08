#!/usr/bin/env python3
"""Match photos to the autopilot's camera log and build a GeoJSON of findings — project #6 starter.

  python geotag.py cam.csv photos.csv findings.csv --out report.geojson

cam.csv:      img,t,lat,lon,alt     (CAM log records: shutter feedback; or TRIG if no feedback)
photos.csv:   file,t                (photo files and their EXIF DateTimeOriginal as seconds, camera clock)
findings.csv: file,label,severity   (what an inspector or a detector marked)
The camera clock is not the autopilot clock: the offset is estimated as the median difference of the first
pairs, then every photo is matched to the nearest CAM record within --tol seconds. Missed triggers show up
as CAM records without a photo; extra photos as photos without a CAM record.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics


def estimate_offset(cam_t: list[float], photo_t: list[float], n: int = 5) -> float:
    k = min(n, len(cam_t), len(photo_t))
    return statistics.median(c - p for c, p in zip(cam_t[:k], photo_t[:k]))


def match(cam: list[dict], photos: list[dict], tol: float = 0.4) -> dict:
    """Greedy nearest match in time after removing the clock offset. Returns matches and both kinds of misses."""
    off = estimate_offset([c["t"] for c in cam], [p["t"] for p in photos])
    used, pairs, extra = set(), [], []
    j = 0
    for p in photos:
        t = p["t"] + off
        while j + 1 < len(cam) and abs(cam[j + 1]["t"] - t) <= abs(cam[j]["t"] - t):
            j += 1
        if abs(cam[j]["t"] - t) <= tol and j not in used:
            used.add(j); pairs.append((p, cam[j]))
        else:
            extra.append(p)
    missed = [c for k, c in enumerate(cam) if k not in used]
    return {"offset_s": off, "pairs": pairs, "missed_triggers": missed, "photos_without_cam": extra}


def to_geojson(pairs, findings: dict[str, list[dict]]) -> dict:
    feats = []
    for p, c in pairs:
        for fd in findings.get(p["file"], []):
            feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [c["lon"], c["lat"], c["alt"]]},
                          "properties": {"file": p["file"], "label": fd["label"], "severity": fd["severity"], "cam_img": c["img"]}})
    return {"type": "FeatureCollection", "features": feats}


def _read(path, cast):
    with open(path) as f:
        return [cast(r) for r in csv.DictReader(f)]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cam"); ap.add_argument("photos"); ap.add_argument("findings")
    ap.add_argument("--tol", type=float, default=0.4); ap.add_argument("--out", default="report.geojson")
    a = ap.parse_args()
    cam = _read(a.cam, lambda r: {"img": int(r["img"]), "t": float(r["t"]), "lat": float(r["lat"]), "lon": float(r["lon"]), "alt": float(r["alt"])})
    photos = _read(a.photos, lambda r: {"file": r["file"], "t": float(r["t"])})
    fnd: dict[str, list[dict]] = {}
    for r in _read(a.findings, dict):
        fnd.setdefault(r["file"], []).append(r)
    m = match(cam, photos, a.tol)
    json.dump(to_geojson(m["pairs"], fnd), open(a.out, "w"), indent=1)
    print(f"offset {m['offset_s']:.2f} s; matched {len(m['pairs'])}; missed triggers {len(m['missed_triggers'])}; "
          f"photos without CAM {len(m['photos_without_cam'])}")


if __name__ == "__main__":
    main()
