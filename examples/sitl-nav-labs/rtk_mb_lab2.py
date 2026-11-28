#!/usr/bin/env python3
"""nav-rtk SITL lab, part 2: break the baseline, lose the heading, change the simulated accuracy.
Same SITL setup as rtk_mb_lab.py.  usage: rtk_mb_lab2.py [--port 5790 | tcp:127.0.0.1:5760]
On 4.7 step F needs SIM_GPS1_ACC instead of SIM_GPS_ACC."""
import math
import sys
import time

from pymavlink import mavutil

URL = sys.argv[1] if len(sys.argv) > 1 else "tcp:127.0.0.1:5760"
if URL == "--port":                       # run_lab.sh passes --port N
    URL = f"tcp:127.0.0.1:{sys.argv[2]}"
m = mavutil.mavlink_connection(URL, source_system=255)
m.wait_heartbeat(timeout=90)
m.mav.request_data_stream_send(m.target_system, m.target_component, mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)


def pset(name, val):
    m.mav.param_set_send(m.target_system, m.target_component, name.encode(), float(val), mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
    time.sleep(0.3)


def sample(seconds, label):
    """print GPS2_RAW yaw / ATTITUDE yaw / fix / h_acc once a second for `seconds` and collect STATUSTEXT"""
    t_end = time.time() + seconds
    texts, last = [], {}
    t_print = 0
    while time.time() < t_end:
        msg = m.recv_match(blocking=True, timeout=0.2)
        if msg is None:
            continue
        t = msg.get_type()
        if t == "STATUSTEXT":
            texts.append(msg.text)
        last[t] = msg
        if time.time() - t_print > 1.0 and "GPS2_RAW" in last and "ATTITUDE" in last:
            g, a = last["GPS2_RAW"], last["ATTITUDE"]
            print(f"  [{label}] GPS2_RAW.yaw={g.yaw:5d} cdeg fix={g.fix_type} h_acc={g.h_acc} mm   "
                  f"EKF yaw={math.degrees(a.yaw)%360:6.2f} deg")
            t_print = time.time()
    if texts:
        print("  statustext:", texts)


print("== A. healthy: GPS1_POS_Y=-0.2, GPS2_POS_Y=+0.2 (baseline 0.4 m)")
sample(3, "ok")

print("== B. GPS2_POS_Y -> 0.5: configured baseline 0.7 m, receiver reports 0.4 m (error 43 % > 20 %)")
pset("GPS2_POS_Y", 0.5)
sample(8, "bad-ofs")
pset("GPS2_POS_Y", 0.2)
print("== C. restored 0.2")
sample(6, "restored")

print("== D. SIM_GPS2_HDG -> 0: rover stops sending UBX-NAV-RELPOSNED")
pset("SIM_GPS2_HDG", 0)
sample(8, "no-relposned")
pset("SIM_GPS2_HDG", 1)
print("== E. RELPOSNED back")
sample(6, "relposned")

print("== F. SIM_GPS2_ACC 0.3 -> 0.02 m: what an RTK-fixed receiver would report as hAcc")
pset("SIM_GPS2_ACC", 0.02)
pset("SIM_GPS_ACC", 0.02)
sample(4, "acc=0.02")
pset("SIM_GPS2_ACC", 0.3)
pset("SIM_GPS_ACC", 0.3)
