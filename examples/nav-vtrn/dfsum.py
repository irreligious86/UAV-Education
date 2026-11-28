#!/usr/bin/env python3
"""nav-vtrn: dataflash evidence that EKF3 uses the vision "receiver": which GPS is primary, innovations, test ratios.

usage: python3 dfsum.py <SITL dataflash log, e.g. sitl3/logs/00000001.BIN>
Prints GPS/GPA/XKF3/XKF4 rows whenever the primary GPS or a receiver status changes (and every 20 s), the
"on GPS2 (vision) from t = ..." summary line quoted in the module (XKF4.SP/SV, |XKF3.IPE|) and GPS/EKF messages.
"""
import sys
from pymavlink import mavutil
if len(sys.argv) != 2:
    sys.exit(__doc__)
log = mavutil.mavlink_connection(sys.argv[1])
rows = []          # (t, used_gps, st1, st2, hacc2, IPN, IPE, SP, SV)
cur = {"u": None, "s1": 0, "s2": 0, "h2": 0.0, "ipn": 0.0, "ipe": 0.0}
ev = []
while True:
    m = log.recv_match(type=["GPS", "GPA", "XKF3", "XKF4", "MSG", "MODE", "XKFS"])
    if m is None:
        break
    t = m.TimeUS * 1e-6
    ty = m.get_type()
    if ty == "GPS":
        cur["s1" if m.I == 0 else "s2"] = m.Status
        if m.U:
            cur["u"] = m.I + 1
    elif ty == "GPA" and m.I == 1:
        cur["h2"] = m.HAcc
    elif ty == "XKF3" and m.C == 0:
        cur["ipn"], cur["ipe"] = m.IPN, m.IPE
    elif ty == "XKF4" and m.C == 0:
        rows.append((t, cur["u"], cur["s1"], cur["s2"], cur["h2"], cur["ipn"], cur["ipe"], m.SP, m.SV))
    elif ty == "MSG":
        ev.append((t, m.Message))
    elif ty == "MODE":
        ev.append((t, f"MODE {m.Mode}"))
print("   t,s  GPS used  GPS1.Status GPS2.Status GPA2.HAcc  XKF3.IPN  XKF3.IPE  XKF4.SP  XKF4.SV")
last, lt = None, None
for r in rows:
    key = (r[1], r[2], r[3])
    if key != last or int(r[0]) % 20 == 0 and int(r[0]) != int(lt):
        print(f"{r[0]:7.1f}  {r[1]}         {r[2]}           {r[3]}          {r[4]:5.1f}     {r[5]:6.2f}    {r[6]:6.2f}    {r[7]:5.2f}    {r[8]:5.2f}")
        last, lt = key, r[0]
sw = [r[0] for i, r in enumerate(rows) if i and r[1] == 2 and rows[i - 1][1] == 1]
if sw:
    seg = [r for r in rows if r[0] > sw[0] and r[3] >= 3]
    print(f"on GPS2 (vision) from t = {sw[0]:.1f} s: {len(seg)} XKF4 samples, SP max {max(r[7] for r in seg):.2f}, SP median {sorted(r[7] for r in seg)[len(seg) // 2]:.2f}, "
          f"SV max {max(r[8] for r in seg):.2f}; samples with SP > 1: {sum(1 for r in seg if r[7] > 1)}; |IPE| max {max(abs(r[6]) for r in seg):.1f} m")
for t, s in ev:
    if any(k in s for k in ("GPS", "EKF", "Glitch", "MODE", "lane")):
        print(f"{t:7.1f}  {s}")
