#!/usr/bin/env python3
"""Synthetic blackbox_decode-style CSV logs with known properties, for grader self-tests and for practising
on the course labs before you have your own logs.

  python make_bf_fixture.py good.csv --kind good
Kinds: good, noisy (motor-frequency noise passes the filters), sluggish (gyro lags setpoint), oscillating (15 Hz wobble in hover),
       saturated (motors pinned at max), imbalanced (one motor works 25 % harder), no_rpm, no_unfilt.
"""
from __future__ import annotations

import argparse
import math

import numpy as np

FS = 2000.0          # Hz, logged rate
LO, HI = 48, 2047


def make(kind: str = "good", seconds: float = 6.0, seed: int = 0) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    n = int(seconds * FS)
    t = np.arange(n) / FS
    d = {"loopIteration": np.arange(n, dtype=float), "time": t * 1e6}
    motor_hz = 250.0                                   # motor fundamental in hover
    for ax in range(3):
        # stick input: two snap moves of 600 deg/s, otherwise centred
        sp = np.zeros(n)
        for t0 in (1.0 + ax * 0.3, 3.5 + ax * 0.3):
            m = (t >= t0) & (t < t0 + 0.4)
            sp[m] = 600.0 * (1 if ax != 1 else -1)
        lag = 0.008 if kind != "sluggish" else 0.060
        a = 1 / (1 + lag * FS)
        g = np.zeros(n)
        for i in range(1, n):
            g[i] = g[i - 1] + a * (sp[i] - g[i - 1])
        if kind == "oscillating" and ax < 2:
            g = g + 20.0 * np.sin(2 * math.pi * 15.0 * t)          # P too high / D too low: low-frequency wobble
        noise = 25.0 * np.sin(2 * math.pi * motor_hz * t + ax) + rng.normal(0, 6.0, n)
        unf = g + noise
        leak = 0.05 if kind != "noisy" else 0.6
        filt = g + leak * noise
        d[f"setpoint[{ax}]"] = sp
        d[f"gyroADC[{ax}]"] = filt
        if kind != "no_unfilt":
            d[f"gyroUnfilt[{ax}]"] = unf
    d["setpoint[3]"] = np.full(n, 500.0)
    thr = np.full(n, 1350.0)
    d["rcCommand[3]"] = thr
    base = LO + 0.35 * (HI - LO)
    for k in range(4):
        m = base + rng.normal(0, 15, n)
        if kind == "imbalanced" and k == 2:
            m = LO + (m - LO) * 1.25
        if kind == "saturated":
            m = np.where((t % 1.0) < 0.2, HI, m)
        d[f"motor[{k}]"] = m
        if kind != "no_rpm":
            erpm = motor_hz * 60 * 7 / 100.0                # 14-pole motor: eRPM = RPM * 7; logged /100
            d[f"eRPM[{k}]"] = np.full(n, erpm) + rng.normal(0, 3, n)
    return d


def write_csv(path: str, d: dict[str, np.ndarray]) -> None:
    names = list(d)
    header = ["time (us)" if k == "time" else k for k in names]
    cols = [d[k] for k in names]
    with open(path, "w") as f:
        f.write(", ".join(header) + "\n")
        for i in range(len(cols[0])):
            f.write(", ".join(f"{c[i]:.3f}" for c in cols) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("--kind", default="good")
    a = ap.parse_args()
    write_csv(a.out, make(a.kind))


if __name__ == "__main__":
    main()
