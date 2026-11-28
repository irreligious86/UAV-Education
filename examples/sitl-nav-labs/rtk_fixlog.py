#!/usr/bin/env python3
"""Fix type vs accuracy from a GNSS fix log (CSV: t_s, fix_type, hacc_m, nsats, corr_age_s).

Usage: python3 rtk_fixlog.py [log.csv] [plot.png]
Without a file the script generates a 300 s dataset that mimics an F9P rover: cold 3D fix,
corrections arrive, float -> fixed, a 25 s NTRIP dropout (correction age grows), recovery.
"""
import csv
import random
import sys

random.seed(7)
FIX = {1: "no fix", 2: "2D", 3: "3D", 4: "DGPS", 5: "RTK float", 6: "RTK fixed"}
HACC = {3: (1.5, 0.4), 4: (0.6, 0.15), 5: (0.25, 0.08), 6: (0.014, 0.003)}   # mean, sigma (m)


def generate(n=300):
    rows, age, fix = [], 0.0, 3
    for t in range(n):
        if t < 20:        fix, age = 3, 0.0                       # no corrections yet
        elif t < 35:      fix, age = 4, 1.0                       # RTCM arrived, DGPS
        elif t < 60:      fix, age = 5, 1.0                       # float: ambiguities not resolved
        elif t < 150:     fix, age = 6, 1.0                       # fixed
        elif t < 175:     age += 1.0; fix = 6 if age < 10 else (5 if age < 20 else 3)   # NTRIP dropout
        elif t < 190:     fix, age = 5, 1.0                       # re-convergence
        else:             fix, age = 6, 1.0
        mu, sd = HACC[fix]
        rows.append((t, fix, max(0.005, random.gauss(mu, sd)), random.randint(18, 24), age))
    return rows


def load(path):
    with open(path, newline="") as f:
        return [(float(r[0]), int(r[1]), float(r[2]), int(r[3]), float(r[4])) for r in csv.reader(f) if r and r[0][0].isdigit()]


rows = load(sys.argv[1]) if len(sys.argv) > 1 else generate()
print(f"{len(rows)} fixes, {rows[-1][0] - rows[0][0]:.0f} s")
print(f"{'fix':10} {'n':>4} {'share':>6} {'hAcc mean':>10} {'hAcc p95':>9}")
for k in sorted(FIX):
    h = sorted(r[2] for r in rows if r[1] == k)
    if h:
        print(f"{FIX[k]:10} {len(h):4d} {len(h)/len(rows):6.1%} {sum(h)/len(h):8.3f} m {h[int(len(h)*0.95)]:7.3f} m")
fixed = [r for r in rows if r[1] == 6]
print(f"time-to-fixed from first correction: {fixed[0][0] - next(r[0] for r in rows if r[4] > 0):.0f} s")
lost = [r for r in rows if r[4] >= 10]
print(f"samples with correction age >= 10 s: {len(lost)}, worst age {max(r[4] for r in rows):.0f} s, "
      f"fix during them: {sorted(set(FIX[r[1]] for r in lost))}")

if len(sys.argv) > 2:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    t = [r[0] for r in rows]
    fig, ax = plt.subplots(3, 1, sharex=True, figsize=(9, 6))
    ax[0].step(t, [r[1] for r in rows], where="post"); ax[0].set_yticks(list(FIX)); ax[0].set_yticklabels(FIX.values()); ax[0].set_ylabel("fix type")
    ax[1].semilogy(t, [r[2] for r in rows], "."); ax[1].set_ylabel("hAcc, m"); ax[1].axhline(0.05, ls="--", c="gray")
    ax[2].plot(t, [r[4] for r in rows]); ax[2].set_ylabel("corr. age, s"); ax[2].set_xlabel("t, s"); ax[2].axhline(10, ls="--", c="gray")
    fig.tight_layout(); fig.savefig(sys.argv[2], dpi=110)
    print("plot:", sys.argv[2])
