#!/usr/bin/env python3
"""Touchdown statistics for a series of precision landings.

  python landing_stats.py touchdowns.csv --marker 3.0 -2.0 --limit 0.15

CSV columns: n,e (local NED metres of each touchdown, e.g. LOCAL_POSITION_NED when LAND completes).
Acceptance (project #5): error <= 15 cm in at least 9 of 10 landings.
"""
from __future__ import annotations

import argparse
import csv
import math


def errors(points, marker) -> list[float]:
    return [math.hypot(n - marker[0], e - marker[1]) for n, e in points]


def verdict(errs: list[float], limit: float = 0.15, required_frac: float = 0.9) -> dict:
    ok = sum(1 for x in errs if x <= limit)
    s = sorted(errs)
    return {"n": len(errs), "within": ok, "frac": ok / len(errs) if errs else 0.0,
            "median": s[len(s) // 2] if s else float("nan"), "max": s[-1] if s else float("nan"),
            "pass": bool(errs) and ok / len(errs) >= required_frac}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--marker", nargs=2, type=float, default=(0.0, 0.0))
    ap.add_argument("--limit", type=float, default=0.15)
    a = ap.parse_args()
    with open(a.csv) as f:
        pts = [(float(r["n"]), float(r["e"])) for r in csv.DictReader(f)]
    v = verdict(errors(pts, a.marker), a.limit)
    print(v)
    raise SystemExit(0 if v["pass"] else 1)


if __name__ == "__main__":
    main()
