"""Summarise XKF4.SP (core 0) per 5 s window and count VISP messages: logsum.py <log.BIN>"""
import sys
from pymavlink import DFReader
log = DFReader.DFReader_binary(sys.argv[1])
sp, visp, t0 = {}, 0, None
while (m := log.recv_match(type=["XKF4", "VISP"])) is not None:
    if m.get_type() == "VISP":
        visp += 1; continue
    if m.C != 0: continue
    t0 = t0 or m.TimeUS
    k = int((m.TimeUS - t0) / 5e6)
    sp[k] = max(sp.get(k, 0), m.SP)
print("VISP msgs", visp)
print(" ".join(f"{k*5:>3}s:{v:4.2f}" for k, v in sorted(sp.items())))
