#!/usr/bin/env python3
"""Summarise an ArduCopter dataflash log of the nav-indoor lab.
usage: analyze.py <log.BIN> [--csv out.csv]   (--csv: per-sample est-vs-truth error)"""
import sys, math
from pymavlink import DFReader

log = DFReader.DFReader_binary(sys.argv[1])
core0 = lambda m: getattr(m, "C", 0) == 0
rows = {"XKF1": [], "XKF3": [], "XKF4": [], "VISP": [], "SIM": [], "ORGN": [], "ARM": [], "MODE": [], "MSG": [], "XKF5": []}
while True:
    m = log.recv_msg()
    if m is None:
        break
    t = m.get_type()
    if t in rows:
        if t.startswith("XKF") and not core0(m):
            continue
        rows[t].append(m)

armed_spans = []
t_arm = rows["XKF1"][0].TimeUS if rows["XKF1"] else None   # LOG_DISARMED=0: log starts at arming
for a in rows["ARM"]:
    if a.ArmState == 1 and t_arm is None:
        t_arm = a.TimeUS
    elif a.ArmState == 0 and t_arm is not None:
        armed_spans.append((t_arm, a.TimeUS)); t_arm = None
if t_arm is not None:
    armed_spans.append((t_arm, 1e18))
inflight = lambda tus: any(a <= tus <= b for a, b in armed_spans)
print("armed spans (s):", [(round(a/1e6, 1), round(b/1e6, 1)) for a, b in armed_spans])

# origin
org = rows["ORGN"][-1] if rows["ORGN"] else None
lat0, lng0, alt0 = (org.Lat, org.Lng, org.Alt) if org else (None, None, None)
print(f"ORGN: {lat0} {lng0} {alt0}")

# truth NED from SIM (lat lng alt in log are floats, deg / m)
def sim_ned(s):
    dn = (s.Lat - lat0) * 111319.5
    de = (s.Lng - lng0) * 111319.5 * math.cos(math.radians(lat0))
    return dn, de, -(s.Alt - alt0)

# estimate vs truth: interpolate truth at XKF1 time (nearest)
sim = rows["SIM"]
si = 0
errs = []
for x in rows["XKF1"]:
    if not inflight(x.TimeUS):
        continue
    while si + 1 < len(sim) and sim[si + 1].TimeUS <= x.TimeUS:
        si += 1
    n, e, d = sim_ned(sim[si])
    errs.append((x.TimeUS, math.hypot(x.PN - n, x.PE - e), abs(x.PD - d)))
if errs:
    h = sorted(v for _, v, _ in errs); z = sorted(v for _, _, v in errs)
    print(f"XKF1 vs truth in flight: horiz mean {sum(h)/len(h):.3f} p95 {h[int(.95*len(h))]:.3f} max {h[-1]:.3f} m | vert mean {sum(z)/len(z):.3f} max {z[-1]:.3f} m (n={len(h)})")

# innovations and test ratios in flight
ipn = [(m.TimeUS, m.IPN, m.IPE, m.IPD) for m in rows["XKF3"] if inflight(m.TimeUS)]
if ipn:
    mx = max(math.hypot(a, b) for _, a, b, _ in ipn)
    mean = sum(math.hypot(a, b) for _, a, b, _ in ipn) / len(ipn)
    print(f"XKF3 |IPN,IPE| in flight: mean {mean:.3f} max {mx:.3f} m; |IPD| max {max(abs(c) for *_, c in ipn):.3f} m")
sp = [(m.TimeUS, m.SP, m.SV, m.SH, m.SM, m.TS, m.SS) for m in rows["XKF4"] if inflight(m.TimeUS)]
if sp:
    print(f"XKF4 in flight: SP mean {sum(s[1] for s in sp)/len(sp):.2f} max {max(s[1] for s in sp):.2f}; samples with SP>1: {sum(1 for s in sp if s[1] > 1)}/{len(sp)}; SH max {max(s[3] for s in sp):.2f}; TS!=0: {sum(1 for s in sp if s[5] != 0)}")
vis = rows["VISP"]
if vis:
    ign = sum(1 for v in vis if v.Ign)
    print(f"VISP: {len(vis)} msgs, ignored {ign}; last PErr {vis[-1].PErr} AErr {vis[-1].AErr}")
print("MSG:")
for mm in rows["MSG"]:
    if any(k in mm.Message for k in ("EKF", "variance", "Failsafe", "failsafe", "Need", "PreArm", "Arm", "ground", "origin", "external")):
        print(f"  [{mm.TimeUS/1e6:7.1f}] {mm.Message}")
if len(sys.argv) > 3 and sys.argv[2] == "--csv":
    with open(sys.argv[3], "w") as f:
        f.write("t_s,err_h,err_v\n")
        for tus, eh, ev in errs:
            f.write(f"{tus/1e6:.2f},{eh:.3f},{ev:.3f}\n")
