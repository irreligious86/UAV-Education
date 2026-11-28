#!/usr/bin/env python3
"""truth_at.py <log.BIN> t1 t2 ... : true N/E offset from the EKF origin (SIM) and XKF1 PN/PE at given times."""
import sys, math
from pymavlink import DFReader
log = DFReader.DFReader_binary(sys.argv[1]); ts = [float(x) for x in sys.argv[2:]]
org = sim = x1 = None
while ts:
    m = log.recv_msg()
    if m is None: break
    t = m.get_type()
    if t == "ORGN": org = m
    elif t == "SIM": sim = m
    elif t == "XKF1" and m.C == 0:
        x1 = m
        if org and sim and m.TimeUS / 1e6 >= ts[0]:
            n = (sim.Lat - org.Lat) * 111319.5; e = (sim.Lng - org.Lng) * 111319.5 * math.cos(math.radians(org.Lat))
            print(f"t={ts.pop(0):5.1f}  truth N {n:+6.2f} E {e:+6.2f}   XKF1 PN {m.PN:+6.2f} PE {m.PE:+6.2f}")
