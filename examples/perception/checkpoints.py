#!/usr/bin/env python3
"""Map accuracy from check points (project #7 starter, per-mapping lab).

  python checkpoints.py points.csv            # columns: name,role,e_true,n_true,h_true,e_map,n_map,h_map

`role` is "gcp" (used in processing) or "check" (independent). Accuracy is reported on check points only:
GCP residuals describe the fit, not the accuracy. Coordinates in a projected CRS (metres), e.g. UTM.
"""
from __future__ import annotations

import argparse
import csv
import math


def rmse(points: list[dict], role: str = "check") -> dict:
    pts = [p for p in points if p["role"] == role]
    if not pts:
        raise ValueError(f"no points with role '{role}'")
    dxy2 = [(p["e_map"] - p["e_true"]) ** 2 + (p["n_map"] - p["n_true"]) ** 2 for p in pts]
    dz = [p["h_map"] - p["h_true"] for p in pts]
    return {"n": len(pts), "rmse_xy": math.sqrt(sum(dxy2) / len(pts)), "rmse_z": math.sqrt(sum(d * d for d in dz) / len(pts)),
            "max_xy": math.sqrt(max(dxy2)), "mean_dz": sum(dz) / len(pts)}


def in_gsd(r: dict, gsd_m: float) -> dict:
    return {"xy_gsd": r["rmse_xy"] / gsd_m, "z_gsd": r["rmse_z"] / gsd_m}


def load(path: str) -> list[dict]:
    with open(path) as f:
        out = []
        for row in csv.DictReader(f):
            out.append({"name": row["name"], "role": row["role"].strip().lower(),
                        **{k: float(row[k]) for k in ("e_true", "n_true", "h_true", "e_map", "n_map", "h_map")}})
        return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--gsd", type=float, help="GSD in metres, to express the result in GSD units")
    a = ap.parse_args()
    pts = load(a.csv)
    r = rmse(pts, "check")
    print("check points:", {k: round(v, 3) if isinstance(v, float) else v for k, v in r.items()})
    if a.gsd:
        print("in GSD:", {k: round(v, 2) for k, v in in_gsd(r, a.gsd).items()})
    if any(p["role"] == "gcp" for p in pts):
        g = rmse(pts, "gcp")
        print("gcp residuals (fit, NOT accuracy):", round(g["rmse_xy"], 3), round(g["rmse_z"], 3))


if __name__ == "__main__":
    main()
