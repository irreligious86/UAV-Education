#!/usr/bin/env python3
"""Grade a Betaflight Blackbox log for the course labs (mirror of examples/sitl-pymavlink/check_lab_log.py).

Input is the CSV written by blackbox_decode (blackbox-tools):
    blackbox_decode LOG00001.BFL            # -> LOG00001.01.csv
    python check_bf_log.py LOG00001.01.csv --lab all --motor-range 48,2047 --json result.json
    # result.json -> course progress page, "Импорт результата грейдера" (ticks the matching lab criteria)

Labs (thresholds are course defaults, override with --set name=value):
  filters   gyroUnfilt vs gyroADC: high-frequency noise before/after filtering, dominant noise frequency
  tracking  setpoint vs gyroADC: relative tracking error on stick moves, residual rate when sticks are centred
  motors    output saturation and per-motor imbalance in steady flight
  rpm       bidirectional DShot telemetry present and non-zero for every motor (needed by the RPM filter)
Exit code 0 when every requested check passes. Units: gyro and setpoint in deg/s (gyro_scale = 1.0 in BF 4.x
logs), eRPM column = eRPM/100, time in microseconds.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys

import numpy as np

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import labresult  # noqa: E402

GRADER_VERSION = 1
# lab -> course lab criteria (module:lab:index) proven when every check of that lab passes
MARKS = {
    "filters": ["bf-filters:lab:0", "bf-filters:lab:1"],
    "tracking": ["bf-pid:lab:4"],
    "motors": ["bf-pid:lab:5"],
    "rpm": ["bf-rpm-filter:lab:4"],
}
BLACKBOX_RATE_MARK = ("bf-blackbox:lab:0", 1000.0)   # "log recorded at >= 1 kHz"

DEFAULTS = {
    "noise_max_dps": 4.0,          # HF noise RMS left after filtering, roll/pitch
    "noise_reduction_db": 6.0,     # filtered vs unfiltered HF noise
    "hf_window_ms": 5.0,           # moving-average window separating "motion" from "noise"
    "track_err_max": 0.25,         # RMS(setpoint - gyro) / RMS(setpoint) during stick moves
    "stick_move_dps": 100.0,       # |setpoint| above this counts as a stick move
    "centred_rate_max_dps": 6.0,   # RMS gyro when |setpoint| < 5 deg/s (oscillation / bounce indicator)
    "settle_ms": 300.0,            # ignore this long after any stick input when judging centred-stick motion
    "sat_frac_max": 0.02,          # fraction of samples with any motor at >= 98 % of range
    "imbalance_max": 0.12,         # max |motor_i / mean - 1| in steady flight
    "rpm_valid_frac": 0.95,        # eRPM > 0 for this fraction of samples above idle
}


def load_csv(path: str) -> dict[str, np.ndarray]:
    """Columns by normalised name: 'time (us)' -> 'time', 'gyroADC[0]' stays 'gyroADC[0]'."""
    with open(path, newline="") as f:
        rd = csv.reader(f)
        header = [re.sub(r"\s*\(.*\)$", "", h.strip()) for h in next(rd)]
        rows = [r for r in rd if len(r) == len(header)]
    data = {}
    for i, name in enumerate(header):
        try:
            data[name] = np.array([float(r[i]) for r in rows])
        except ValueError:
            continue                                  # text columns (flight mode names etc.)
    if "time" not in data:
        raise ValueError("no 'time' column: is this a blackbox_decode CSV?")
    return data


def sample_rate(d) -> float:
    dt = np.diff(d["time"]) / 1e6
    dt = dt[dt > 0]
    return 1.0 / float(np.median(dt))


def hf_noise_rms(x: np.ndarray, fs: float, window_ms: float) -> float:
    n = max(3, int(round(fs * window_ms / 1000)))
    k = np.ones(n) / n
    smooth = np.convolve(x, k, mode="same")
    r = (x - smooth)[n:-n]
    return float(np.sqrt(np.mean(r * r))) if r.size else float("nan")


def dominant_freq(x: np.ndarray, fs: float, fmin: float = 50.0) -> float:
    x = x - np.mean(x)
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1 / fs)
    m = f >= fmin
    return float(f[m][np.argmax(spec[m])]) if m.any() else float("nan")


def check(name, ok, value, limit, meaning):
    return {"check": name, "pass": bool(ok), "value": None if value is None or (isinstance(value, float) and math.isnan(value)) else round(float(value), 4),
            "limit": limit, "meaning": meaning}


def lab_filters(d, fs, p):
    out = []
    for ax, nm in ((0, "roll"), (1, "pitch")):
        u, g = f"gyroUnfilt[{ax}]", f"gyroADC[{ax}]"
        if u not in d:
            return [check("gyroUnfilt logged", False, None, "present",
                          "Unfiltered gyro is not in the log: enable it in Blackbox fields so filtering can be judged.")]
        nu, nf = hf_noise_rms(d[u], fs, p["hf_window_ms"]), hf_noise_rms(d[g], fs, p["hf_window_ms"])
        red = 20 * math.log10(nu / nf) if nf > 0 else float("inf")
        out.append(check(f"{nm} noise after filters", nf <= p["noise_max_dps"], nf, f"<= {p['noise_max_dps']} deg/s",
                         "High-frequency gyro noise reaching the PID loop; it ends up in D-term and motor heat."))
        out.append(check(f"{nm} noise reduction", red >= p["noise_reduction_db"], red, f">= {p['noise_reduction_db']} dB",
                         "How much the filter stack removes; little reduction with high noise = filters miss the peak."))
        out.append(check(f"{nm} dominant noise frequency", True, dominant_freq(d[u], fs), "info",
                         "Compare with motor frequency (eRPM*100/(poles/2)/60) and frame resonances."))
    return out


def lab_tracking(d, fs, p):
    out = []
    for ax, nm in ((0, "roll"), (1, "pitch"), (2, "yaw")):
        sp, g = d.get(f"setpoint[{ax}]"), d.get(f"gyroADC[{ax}]")
        if sp is None or g is None:
            return [check("setpoint and gyro logged", False, None, "present", "Tracking needs setpoint[] and gyroADC[] fields.")]
        mv = np.abs(sp) > p["stick_move_dps"]
        if mv.sum() < fs * 0.2:
            out.append(check(f"{nm} stick moves", False, float(mv.sum() / fs), ">= 0.2 s",
                             "Not enough stick activity to judge tracking: fly snap rolls/flips for the test log."))
            continue
        e = (sp - g)[mv]
        rel = float(np.sqrt(np.mean(e * e)) / np.sqrt(np.mean(sp[mv] ** 2)))
        out.append(check(f"{nm} tracking error", rel <= p["track_err_max"], rel, f"<= {p['track_err_max']}",
                         "Relative RMS error between commanded and measured rate during moves: P/FF too low or too much delay."))
        if ax < 2:
            # centred sticks, excluding the settle-time after each move (the rate decaying back is not oscillation)
            settle = int(p["settle_ms"] / 1000 * fs)
            recent = np.convolve(np.abs(sp) > 5, np.ones(settle), mode="full")[: len(sp)] > 0
            c = (np.abs(sp) < 5) & ~recent
            if c.sum() > fs * 0.5:
                rr = float(np.sqrt(np.mean(g[c] ** 2)))
                out.append(check(f"{nm} rate with centred sticks", rr <= p["centred_rate_max_dps"], rr,
                                 f"<= {p['centred_rate_max_dps']} deg/s", "Residual motion in hover: oscillation, bounce-back or wind."))
    return out


def lab_motors(d, fs, p, motor_range):
    cols = [k for k in sorted(d) if re.fullmatch(r"motor\[\d+\]", k)]
    if not cols:
        return [check("motor outputs logged", False, None, "present", "No motor[] columns in the log.")]
    lo, hi = motor_range
    m = np.vstack([d[c] for c in cols])
    sat = float(np.mean(np.any(m >= lo + 0.98 * (hi - lo), axis=0)))
    out = [check("motor saturation", sat <= p["sat_frac_max"], sat, f"<= {p['sat_frac_max']}",
                 "Share of time a motor is at full output: no authority left, PID cannot correct (too heavy, too aggressive).")]
    thr = d.get("rcCommand[3]")
    steady = np.ones(m.shape[1], bool)
    if thr is not None:
        steady = np.abs(thr - np.median(thr)) < 0.05 * (np.max(thr) - np.min(thr) + 1e-9)
    if steady.sum() > fs * 0.5:
        mean_each = (m[:, steady] - lo).mean(axis=1)
        imb = float(np.max(np.abs(mean_each / mean_each.mean() - 1)))
        out.append(check("motor imbalance in steady flight", imb <= p["imbalance_max"], imb, f"<= {p['imbalance_max']}",
                         "One motor working harder: centre of gravity offset, bent prop, weak motor or twisted arm."))
    return out


def lab_rpm(d, fs, p, motor_range):
    cols = [k for k in sorted(d) if re.fullmatch(r"eRPM\[\d+\]", k)]
    if not cols:
        return [check("eRPM telemetry logged", False, None, "present",
                      "No eRPM fields: bidirectional DShot is off (dshot_bidir) or ESC firmware lacks it; RPM filter cannot work.")]
    mcols = [k for k in sorted(d) if re.fullmatch(r"motor\[\d+\]", k)]
    lo, hi = motor_range
    active = np.ones(len(d["time"]), bool)
    if mcols:
        active = np.min(np.vstack([d[c] for c in mcols]), axis=0) > lo + 0.05 * (hi - lo)
    out = []
    for c in cols:
        v = d[c][active]
        frac = float(np.mean(v > 0)) if v.size else 0.0
        out.append(check(f"{c} valid", frac >= p["rpm_valid_frac"], frac, f">= {p['rpm_valid_frac']}",
                         "Fraction of samples with RPM telemetry while the motor spins; dropouts disable RPM-filter notches."))
    return out


def grade(path: str, labs: list[str], motor_range=(48, 2047), overrides: dict | None = None) -> dict:
    p = {**DEFAULTS, **(overrides or {})}
    d = load_csv(path)
    fs = sample_rate(d)
    res = {"file": path, "sample_rate_hz": round(fs, 1), "checks": []}
    for lab in labs:
        fn = {"filters": lambda: lab_filters(d, fs, p), "tracking": lambda: lab_tracking(d, fs, p),
              "motors": lambda: lab_motors(d, fs, p, motor_range), "rpm": lambda: lab_rpm(d, fs, p, motor_range)}[lab]
        for c in fn():
            res["checks"].append({"lab": lab, **c})
    res["pass"] = all(c["pass"] for c in res["checks"])
    return res


def to_lab_result(r: dict, path: str) -> dict:
    """Convert grade() output to the course lab result file (uav-lab-result/1)."""
    labs: dict[str, list[dict]] = {}
    for c in r["checks"]:
        labs.setdefault(c["lab"], []).append({"check": c["check"], "pass": bool(c["pass"]), "value": str(c["value"]),
                                              "limit": str(c["limit"])})
    extra = [BLACKBOX_RATE_MARK[0]] if r["sample_rate_hz"] >= BLACKBOX_RATE_MARK[1] else []
    return labresult.build("check_bf_log", GRADER_VERSION, path, labs, MARKS, extra, {"sample_rate_hz": r["sample_rate_hz"]})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--lab", default="all", choices=["filters", "tracking", "motors", "rpm", "all"])
    ap.add_argument("--motor-range", default="48,2047", help="log header 'motorOutput' low,high")
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE", help="override a threshold")
    ap.add_argument("--json", help="write the result as JSON")
    a = ap.parse_args()
    labs = ["filters", "tracking", "motors", "rpm"] if a.lab == "all" else [a.lab]
    over = {k: float(v) for k, v in (s.split("=", 1) for s in a.set)}
    lo, hi = (float(x) for x in a.motor_range.split(","))
    r = grade(a.csv, labs, (lo, hi), over)
    for c in r["checks"]:
        print(f"[{'PASS' if c['pass'] else 'FAIL'}] {c['lab']:8} {c['check']}: {c['value']} (limit {c['limit']})")
        if not c["pass"]:
            print(f"         {c['meaning']}")
    print("RESULT:", "PASS" if r["pass"] else "FAIL", f"({r['sample_rate_hz']} Hz)")
    if a.json:
        labresult.write(a.json, to_lab_result(r, a.csv))
    sys.exit(0 if r["pass"] else 1)


if __name__ == "__main__":
    main()
