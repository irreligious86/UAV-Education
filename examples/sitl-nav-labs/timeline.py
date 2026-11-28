#!/usr/bin/env python3
"""Print XKF1 position, XKF3 innovations and XKF4.SP (core 0) once per second between t0 and t1.
usage: timeline.py <log.BIN> <t0_s> <t1_s> [step_s]"""
import sys
from pymavlink import DFReader
log = DFReader.DFReader_binary(sys.argv[1])
t0, t1 = float(sys.argv[2]), float(sys.argv[3])
step = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
last = {}; nxt = t0; visp = None
print("    t   VISP.PX  XKF1.PN  XKF1.PE  XKF3.IPN  XKF3.IPE  XKF4.SP  MSG")
while True:
    m = log.recv_msg()
    if m is None:
        break
    t = m.get_type()
    if t not in ("MSG", "VISP", "XKF1", "XKF3", "XKF4"):
        continue
    ts = m.TimeUS / 1e6
    if t == "MSG" and t0 <= ts <= t1:
        print(f"{ts:6.1f}  {'':52s} {m.Message}")
    if t == "VISP":
        visp = m
    if t in ("XKF1", "XKF3", "XKF4") and getattr(m, "C", 0) == 0:
        last[t] = m
    if t == "XKF4" and getattr(m, "C", 0) == 0 and ts >= nxt and ts <= t1 and len(last) == 3 and visp:
        nxt = ts + step
        print(f"{ts:6.1f}  {visp.PX:7.2f}  {last['XKF1'].PN:7.2f}  {last['XKF1'].PE:7.2f}  {last['XKF3'].IPN:8.2f}  {last['XKF3'].IPE:8.2f}  {m.SP:7.2f}")
