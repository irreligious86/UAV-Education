#!/usr/bin/env python3
"""nav-rtk SITL lab: moving-baseline GPS yaw in ArduCopter 4.6.3 SITL (pymavlink).

SITL must already run with copter-gps-for-yaw.parm:
  arducopter -S --model + --defaults copter.parm,copter-gps-for-yaw.parm
or: ./run_lab.sh mb_yaw "$ARDUPILOT/Tools/autotest/default_params/copter-gps-for-yaw.parm" "" rtk_mb_lab.py
usage: rtk_mb_lab.py [--port 5790 | tcp:127.0.0.1:5760]
On 4.7 the first receiver's SIM names are SIM_GPS1_HDG / SIM_GPS1_ACC (the SIM_GPS_* lines then print None).
"""
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


def pget(name):
    m.mav.param_request_read_send(m.target_system, m.target_component, name.encode(), -1)
    t0 = time.time()
    while time.time() - t0 < 5:
        p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=1)
        if p and p.param_id == name:
            return p.param_value
    return None


def pset(name, val):
    m.mav.param_set_send(m.target_system, m.target_component, name.encode(), float(val), mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
    time.sleep(0.3)


def latest(t, timeout=5):
    m.recv_match(type=t, blocking=False)
    msg = m.recv_match(type=t, blocking=True, timeout=timeout)
    return msg


print("== params (copter-gps-for-yaw.parm)")
for n in ["GPS1_TYPE", "GPS2_TYPE", "GPS1_POS_Y", "GPS2_POS_Y", "GPS1_MB_TYPE", "GPS1_MB_OFS_Y",
          "GPS_AUTO_SWITCH", "GPS_DRV_OPTIONS", "EK3_SRC1_YAW", "SIM_GPS_HDG", "SIM_GPS2_HDG",
          "SIM_GPS_ACC", "SIM_GPS2_ACC", "SIM_GPS_NUMSATS", "SIM_GPS_LAG_MS"]:
    print(f"  {n} = {pget(n)}")

print("== waiting for GPS2_RAW fix_type >= 6 (RTK fixed on the rover)")
t0 = time.time()
while True:
    g2 = latest("GPS2_RAW")
    if g2 is None:
        continue
    print(f"  t+{time.time()-t0:4.1f}s fix_type={g2.fix_type} sats={g2.satellites_visible} yaw={g2.yaw} (cdeg) "
          f"h_acc={getattr(g2,'h_acc',None)} mm dgps_age={g2.dgps_age} ms")
    if g2.fix_type >= 6:
        break
    if time.time() - t0 > 120:
        sys.exit("no RTK fixed")

print("== GPS_RAW_INT (base, instance 1) vs GPS2_RAW (rover, instance 2)")
g1 = latest("GPS_RAW_INT")
g2 = latest("GPS2_RAW")
print(f"  GPS_RAW_INT: fix_type={g1.fix_type} sats={g1.satellites_visible} eph={g1.eph} h_acc={g1.h_acc} mm "
      f"v_acc={g1.v_acc} mm vel_acc={g1.vel_acc} mm/s yaw={g1.yaw}")
print(f"  GPS2_RAW:    fix_type={g2.fix_type} sats={g2.satellites_visible} eph={g2.eph} h_acc={g2.h_acc} mm "
      f"yaw={g2.yaw} cdeg dgps_numch={g2.dgps_numch} dgps_age={g2.dgps_age}")

print("== GPS yaw vs EKF yaw, 10 samples")
for i in range(10):
    g2 = latest("GPS2_RAW")
    att = latest("ATTITUDE")
    print(f"  GPS2_RAW.yaw={g2.yaw/100:7.2f} deg   ATTITUDE.yaw={math.degrees(att.yaw)%360:7.2f} deg")
    time.sleep(0.5)

print("== EKF status flags")
es = latest("EKF_STATUS_REPORT")
print(f"  flags=0x{es.flags:04x} pos_horiz_variance={es.pos_horiz_variance:.3f} compass_variance={es.compass_variance:.3f}")

print("== breaking the baseline: GPS2_POS_Y 0.2 -> 0.5 (reported 0.4 m vs configured 0.7 m, >20 %)")
pset("GPS2_POS_Y", 0.5)
time.sleep(1.0)
for i in range(6):
    g2 = latest("GPS2_RAW")
    print(f"  GPS2_RAW.yaw={g2.yaw} (65535 = yaw configured but not available) fix_type={g2.fix_type}")
    time.sleep(0.5)
txt = []
t0 = time.time()
while time.time() - t0 < 3:
    s = m.recv_match(type="STATUSTEXT", blocking=True, timeout=0.5)
    if s:
        txt.append(s.text)
print("  statustext:", txt)
pset("GPS2_POS_Y", 0.2)
time.sleep(2.0)
g2 = latest("GPS2_RAW")
print(f"== restored: GPS2_RAW.yaw={g2.yaw} cdeg")
