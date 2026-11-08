#!/usr/bin/env python3
"""Automatic checks of an ArduPilot DataFlash log (.bin) against lab criteria.

Usage:
  python3 check_lab_log.py <log.bin> --lab failsafe     # RC-failsafe lab (ap-safety-fs)
  python3 check_lab_log.py <log.bin> --lab mission      # mission lab (ap-missions): waypoints reached, RTL
  python3 check_lab_log.py <log.bin> --lab hover        # first-flight lab: vibration, hover throttle, tracking
  python3 check_lab_log.py <log.bin> --lab motorfail    # redundancy lab (el-redundancy): motor failure survived

Exit code 0 when every check passes, 1 otherwise. Output is a table the student pastes into the
engineering folder. Checks are intentionally simple and transparent — read the code.
"""
import argparse, sys
from pymavlink import mavutil

COPTER_MODES = {0: "STABILIZE", 2: "ALT_HOLD", 3: "AUTO", 4: "GUIDED", 5: "LOITER", 6: "RTL", 9: "LAND", 16: "POSHOLD", 21: "SMART_RTL"}


def read(log, types):
    m = mavutil.mavlink_connection(log)
    out = {t: [] for t in types}
    while True:
        msg = m.recv_match(type=types, blocking=False)
        if msg is None:
            break
        out[msg.get_type()].append(msg)
    return out


def t_s(msg):
    return msg.TimeUS / 1e6


def report(rows):
    ok_all = all(ok for _, ok, _ in rows)
    w = max(len(n) for n, _, _ in rows)
    for name, ok, detail in rows:
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(w)}  {detail}")
    print("RESULT:", "PASS" if ok_all else "FAIL")
    return 0 if ok_all else 1


def lab_failsafe(log):
    d = read(log, ["MODE", "RCIN", "ERR", "EV", "MSG"])
    rows = []
    # RC loss: ERR Subsys 5 (RADIO) ECode 1 (failsafe triggered)
    rc_fs = [e for e in d["ERR"] if e.Subsys == 5 and e.ECode == 1]
    rows.append(("RC failsafe triggered", bool(rc_fs), f"{len(rc_fs)} event(s)" if rc_fs else "no ERR Subsys=5 ECode=1 — simulate RC loss (SIM_RC_FAIL=1 or switch off the TX)"))
    if rc_fs:
        t0 = t_s(rc_fs[0])
        modes = [mo for mo in d["MODE"] if t_s(mo) >= t0 - 0.2]
        react = next((mo for mo in modes if mo.Mode in (6, 9, 21)), None)
        dt = (t_s(react) - t0) if react else None
        rows.append(("Mode changed to RTL/LAND/SMART_RTL", react is not None, f"{COPTER_MODES.get(react.Mode, react.Mode)} after {dt:.1f} s" if react else "no RTL/LAND after failsafe"))
        rows.append(("Reaction within 5 s", bool(react) and dt <= 5.0, f"{dt:.1f} s" if react else "-"))
        resolved = [e for e in d["ERR"] if e.Subsys == 5 and e.ECode == 0 and t_s(e) > t0]
        rows.append(("Failsafe cleared (RC back) logged", True, f"{len(resolved)} clear event(s) — informational"))
    return report(rows)


def lab_mission(log):
    d = read(log, ["MODE", "CMD", "MSG", "GPS", "ERR"])
    rows = []
    auto = [mo for mo in d["MODE"] if mo.Mode == 3]
    rows.append(("AUTO mode entered", bool(auto), f"at {t_s(auto[0]):.1f} s" if auto else "never"))
    cmds = d["CMD"]
    nav = [c for c in cmds if c.CId in (16, 22, 21, 20, 82)]        # WAYPOINT, TAKEOFF, LAND, RTL, SPLINE
    rows.append(("Mission commands executed", len(nav) >= 3, f"{len(nav)} nav commands logged"))
    reached = [m for m in d["MSG"] if "Reached" in m.Message or "reached" in m.Message]
    rows.append(("Waypoints reached messages", len(reached) >= 2, f"{len(reached)} 'Reached' messages"))
    rtl_or_land = [mo for mo in d["MODE"] if mo.Mode in (6, 9)] or [c for c in cmds if c.CId in (20, 21)]
    rows.append(("Mission ends with RTL/LAND", bool(rtl_or_land), "ok" if rtl_or_land else "no RTL/LAND at the end"))
    gps_bad = [g for g in d["GPS"] if g.NSats < 6]
    rows.append(("GPS satellites >= 6 throughout", not gps_bad, f"{len(gps_bad)} samples below 6" if gps_bad else "ok"))
    errs = [e for e in d["ERR"] if e.Subsys in (16, 17, 11)]          # EKF variance, EKF failsafe, GPS glitch
    rows.append(("No EKF/GPS errors", not errs, f"{len(errs)} ERR events (EKF/GPS)" if errs else "ok"))
    return report(rows)


def lab_hover(log):
    d = read(log, ["VIBE", "CTUN", "ATT", "BAT"])
    rows = []
    if d["VIBE"]:
        vz = sorted(v.VibeZ for v in d["VIBE"]); p95 = vz[int(0.95 * (len(vz) - 1))]
        clips = max((v.Clip for v in d["VIBE"]), default=0)
        rows.append(("Vibration Z p95 < 30 m/s²", p95 < 30, f"p95 = {p95:.1f}"))
        rows.append(("No accelerometer clipping", clips == 0, f"Clip = {clips}"))
    else:
        rows.append(("VIBE logged", False, "enable LOG_BITMASK with VIBE"))
    if d["CTUN"]:
        th = [c.ThO for c in d["CTUN"] if c.ThO > 0.05]
        if th:
            th.sort(); med = th[len(th) // 2]
            rows.append(("Hover throttle 0.2–0.6", 0.2 <= med <= 0.6, f"median ThO = {med:.2f} (T/W ≈ {1 / med:.1f})"))
    if d["ATT"]:
        err = [abs(a.DesRoll - a.Roll) for a in d["ATT"]] + [abs(a.DesPitch - a.Pitch) for a in d["ATT"]]
        err.sort(); p99 = err[int(0.99 * (len(err) - 1))]
        rows.append(("Attitude tracking p99 < 10°", p99 < 10, f"p99 error = {p99:.1f}°"))
    if d["BAT"]:
        vmin = min(b.Volt for b in d["BAT"]); vmax = max(b.Volt for b in d["BAT"])
        rows.append(("Battery sag < 15 %", (vmax - vmin) / vmax < 0.15, f"{vmax:.2f} → {vmin:.2f} V ({100 * (vmax - vmin) / vmax:.0f} %)"))
    return report(rows)


def lab_motorfail(log):
    d = read(log, ["RCOU", "CTUN", "ATT", "MODE"])
    rows = []
    if not d["RCOU"]:
        return report([("RCOU logged", False, "no motor outputs in log")])
    n = max(i for i in range(1, 13) if hasattr(d["RCOU"][0], f"C{i}"))
    # a failed motor shows as one output pinned at max while the vehicle keeps flying
    sat = {}
    for r in d["RCOU"]:
        for i in range(1, n + 1):
            v = getattr(r, f"C{i}")
            if v >= 1950:
                sat[i] = sat.get(i, 0) + 1
    worst = max(sat.items(), key=lambda kv: kv[1]) if sat else (None, 0)
    rows.append(("Motor failure visible (an output saturated)", worst[1] > 20, f"motor {worst[0]} saturated in {worst[1]} samples" if worst[0] else "no saturation — did the failure trigger?"))
    if d["CTUN"]:
        alts = [c.Alt for c in d["CTUN"]]
        drop = max(alts) - min(alts[len(alts) // 2:]) if len(alts) > 10 else 0
        rows.append(("Altitude held after failure (drop < 5 m)", drop < 5, f"max drop in second half = {drop:.1f} m"))
    if d["ATT"]:
        err = sorted(abs(a.DesRoll - a.Roll) for a in d["ATT"]); p99 = err[int(0.99 * (len(err) - 1))]
        rows.append(("Roll tracking p99 < 15° with motor out", p99 < 15, f"p99 = {p99:.1f}°"))
    return report(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log"); ap.add_argument("--lab", required=True, choices=["failsafe", "mission", "hover", "motorfail"])
    a = ap.parse_args()
    sys.exit({"failsafe": lab_failsafe, "mission": lab_mission, "hover": lab_hover, "motorfail": lab_motorfail}[a.lab](a.log))


if __name__ == "__main__":
    main()
