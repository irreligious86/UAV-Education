#!/usr/bin/env python3
"""Flight-log analysis service, project #3 starter: ArduPilot DataFlash (.bin) -> findings JSON + HTML report.

  python log_report.py flight.bin --html report.html --json findings.json

Each check returns findings with a severity (ok / warn / fail), a measured value, the threshold and the
reason, so a report can be read by a person and asserted by a test. Thresholds come from ArduPilot's
own guidance (vibration levels, clipping) and from the course modules (ap-logs, ap-tuning).
"""
from __future__ import annotations

import argparse
import html
import json
import math
from dataclasses import asdict, dataclass

from pymavlink import mavutil

COPTER_MODES = {0: "STABILIZE", 2: "ALT_HOLD", 3: "AUTO", 4: "GUIDED", 5: "LOITER", 6: "RTL", 9: "LAND", 16: "POSHOLD", 17: "BRAKE"}


@dataclass
class Finding:
    check: str
    severity: str            # ok | warn | fail | info
    value: float | str | None
    threshold: str
    message: str


def load(path: str, types=("VIBE", "BAT", "ERR", "MODE", "GPS", "ATT", "MSG", "CTUN", "RCOU")) -> dict:
    log = mavutil.mavlink_connection(path)
    out = {t: [] for t in types}
    while True:
        m = log.recv_match(type=list(types))
        if m is None:
            break
        d = m.to_dict()
        d["t"] = d.get("TimeUS", 0) / 1e6
        out[m.get_type()].append(d)
    return out


def check_vibration(data) -> list[Finding]:
    v = data["VIBE"]
    if not v:
        return [Finding("vibration", "info", None, "", "no VIBE messages")]
    peak = max(max(r["VibeX"], r["VibeY"], r["VibeZ"]) for r in v)
    clip = max(r["Clip"] for r in v) - min(r["Clip"] for r in v)
    sev = "fail" if peak > 60 else "warn" if peak > 30 else "ok"
    out = [Finding("vibration", sev, round(peak, 1), "warn > 30, fail > 60 m/s²", "peak vibration level across axes")]
    out.append(Finding("clipping", "fail" if clip > 100 else "warn" if clip > 0 else "ok", clip, "any increase is a warning",
                       "accelerometer clipping events during the flight"))
    return out


def check_battery(data) -> list[Finding]:
    b = [r for r in data["BAT"] if r.get("Inst", 0) == 0]
    if len(b) < 2:
        return [Finding("battery", "info", None, "", "not enough BAT messages")]
    vmin = min(r["Volt"] for r in b)
    idle = max(b, key=lambda r: r["Volt"])
    loaded = max(b, key=lambda r: r["Curr"])
    out = [Finding("battery_min_voltage", "info", round(vmin, 2), "", "lowest pack voltage")]
    di = loaded["Curr"] - idle["Curr"]
    if di > 5:
        r_mohm = (idle["Volt"] - loaded["Volt"]) / di * 1000
        out.append(Finding("battery_resistance", "warn" if r_mohm > 60 else "ok", round(r_mohm, 1), "warn > 60 mΩ (pack)",
                           "pack internal resistance estimated from sag between lightest and heaviest load"))
    return out


def check_errors(data) -> list[Finding]:
    errs = [r for r in data["ERR"] if r.get("ECode", 0) != 0]
    out = []
    for r in errs:
        out.append(Finding("error", "fail", f"Subsys {r['Subsys']} ECode {r['ECode']}", "none expected",
                           f"ERR at {r['t']:.1f} s (see ArduPilot ERR subsystem table)"))
    return out or [Finding("error", "ok", 0, "none expected", "no ERR events")]


def check_gps(data) -> list[Finding]:
    g = data["GPS"]
    if not g:
        return [Finding("gps", "info", None, "", "no GPS messages")]
    flying = [r for r in g if r["Status"] >= 3] or g
    sats = min(r["NSats"] for r in flying)
    hdop = max(r["HDop"] for r in flying)
    return [Finding("gps_sats", "warn" if sats < 10 else "ok", sats, "warn < 10", "minimum satellites with 3D fix"),
            Finding("gps_hdop", "warn" if hdop > 1.5 else "ok", round(hdop, 2), "warn > 1.5", "maximum HDOP with 3D fix")]


def check_attitude(data) -> list[Finding]:
    a = data["ATT"]
    if not a:
        return [Finding("attitude", "info", None, "", "no ATT messages")]
    err = [math.hypot(r["DesRoll"] - r["Roll"], r["DesPitch"] - r["Pitch"]) for r in a]
    rms = math.sqrt(sum(e * e for e in err) / len(err))
    return [Finding("attitude_tracking", "fail" if rms > 5 else "warn" if rms > 2 else "ok", round(rms, 2),
                    "warn > 2°, fail > 5° RMS", "roll/pitch tracking error (desired vs actual)")]


def mode_timeline(data) -> list[tuple[float, str]]:
    return [(r["t"], COPTER_MODES.get(r["ModeNum"], str(r["ModeNum"]))) for r in data["MODE"]]


def analyse(data) -> list[Finding]:
    out = []
    for fn in (check_vibration, check_battery, check_errors, check_gps, check_attitude):
        out += fn(data)
    return out


def verdict(findings) -> str:
    sev = {f.severity for f in findings}
    return "fail" if "fail" in sev else "warn" if "warn" in sev else "ok"


# ---------------------------------------------------------------- HTML
def sparkline(points, w=640, h=90, label=""):
    if len(points) < 2:
        return ""
    xs = [p[0] for p in points]; ys = [p[1] for p in points]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    sy = (y1 - y0) or 1.0
    pts = " ".join(f"{(x - x0) / ((x1 - x0) or 1) * (w - 10) + 5:.1f},{h - 5 - (y - y0) / sy * (h - 20):.1f}" for x, y in points)
    return (f'<figure><svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="{html.escape(label)}">'
            f'<polyline fill="none" stroke="currentColor" stroke-width="1.5" points="{pts}"/>'
            f'<text x="5" y="12" font-size="11" fill="currentColor">{html.escape(label)}: {y0:.1f} … {y1:.1f}</text></svg></figure>')


def render_html(path, data, findings) -> str:
    colors = {"ok": "#2e7d32", "warn": "#b26a00", "fail": "#c62828", "info": "#555"}
    rows = "".join(f'<tr><td>{html.escape(f.check)}</td><td style="color:{colors[f.severity]};font-weight:600">{f.severity.upper()}</td>'
                   f'<td>{html.escape(str(f.value))}</td><td>{html.escape(f.threshold)}</td><td>{html.escape(f.message)}</td></tr>' for f in findings)
    modes = "".join(f"<li>{t:.1f} s — {html.escape(m)}</li>" for t, m in mode_timeline(data))
    msgs = "".join(f"<li>{r['t']:.1f} s — {html.escape(str(r['Message']))}</li>" for r in data["MSG"][:50])
    charts = sparkline([(r["t"], max(r["VibeX"], r["VibeY"], r["VibeZ"])) for r in data["VIBE"]], label="vibration m/s²")
    charts += sparkline([(r["t"], r["Volt"]) for r in data["BAT"]], label="battery V")
    charts += sparkline([(r["t"], r["Alt"]) for r in data["CTUN"]], label="altitude m")
    v = verdict(findings)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Flight log report</title><style>body{{font:14px/1.5 system-ui,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;color:#222}}
table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #ddd;padding:6px;text-align:left;vertical-align:top}}
figure{{margin:12px 0;color:#1565c0}}</style></head><body>
<h1>Flight log report</h1><p>{html.escape(str(path))} — verdict: <strong style="color:{colors[v]}">{v.upper()}</strong></p>
<h2>Findings</h2><table><tr><th>Check</th><th>Result</th><th>Value</th><th>Threshold</th><th>Meaning</th></tr>{rows}</table>
<h2>Charts</h2>{charts}<h2>Modes</h2><ul>{modes}</ul><h2>Messages</h2><ul>{msgs}</ul></body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log")
    ap.add_argument("--html")
    ap.add_argument("--json")
    a = ap.parse_args()
    data = load(a.log)
    findings = analyse(data)
    for f in findings:
        print(f"{f.severity.upper():5} {f.check:20} {f.value!s:>12}  {f.message}")
    if a.json:
        json.dump({"log": a.log, "verdict": verdict(findings), "findings": [asdict(f) for f in findings]}, open(a.json, "w"), indent=1)
    if a.html:
        open(a.html, "w", encoding="utf-8").write(render_html(a.log, data, findings))
    return 1 if verdict(findings) == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
