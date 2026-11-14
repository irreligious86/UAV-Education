#!/usr/bin/env python3
"""Score targets.csv against truth.csv: geo error, precision/recall per slice, ID switches, interlock states.
python3 score.py data"""
import csv, math, sys
import numpy as np

d = sys.argv[1] if len(sys.argv) > 1 else "data"
truth = {int(r["frame"]): r for r in csv.DictReader(open(f"{d}/truth.csv"))}
rows = list(csv.DictReader(open(f"{d}/targets.csv")))
GATE = 1.0                                                           # m on the ground = "correct"


def slice_of(t):
    if 20.0 <= t < 24.0: return "dark (gain 0.25)"
    if 28.0 <= t < 30.0: return "motion blur"
    if 33.0 <= t < 35.0: return "occluded"
    return "nominal"


stats, errs, ids, states = {}, [], [], {}
for r in rows:
    f = int(r["frame"]); tr = truth[f]; t = int(r["t_us"]) / 1e6
    s = stats.setdefault(slice_of(t), dict(TP=0, FP=0, FN=0))
    visible = tr["visible"] == "1"
    tracked = r["state"] == "TRACK"
    states[r["state"]] = states.get(r["state"], 0) + 1
    if tracked:
        # pipeline reports the target relative to the vehicle: compare with truth (target - vehicle)
        n_err = float(r["n"]) - (float(tr["tgt_n"]) - float(tr["veh_n"]))
        e_err = float(r["e"]) - (float(tr["tgt_e"]) - float(tr["veh_e"]))
        err = math.hypot(n_err, e_err)
        if visible and err < GATE:
            s["TP"] += 1; errs.append(err); ids.append(int(r["track_id"]))
        else:
            s["FP"] += 1
    elif visible:
        s["FN"] += 1

print(f"{'slice':18s}{'TP':>6s}{'FP':>6s}{'FN':>6s}{'precision':>11s}{'recall':>8s}")
for k, s in stats.items():
    p = s["TP"] / max(1, s["TP"] + s["FP"]); rc = s["TP"] / max(1, s["TP"] + s["FN"])
    print(f"{k:18s}{s['TP']:6d}{s['FP']:6d}{s['FN']:6d}{p:11.2f}{rc:8.2f}")
e = np.array(errs)
print(f"geo error on TP frames: mean {e.mean():.2f} m, p95 {np.percentile(e, 95):.2f} m, max {e.max():.2f} m")
print(f"track IDs used on TP frames: {sorted(set(ids))}  (ID switches = {len(set(ids)) - 1})")
print("interlock states:", states)
