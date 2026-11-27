#!/usr/bin/env python3
"""est-gnss lab: which GNSS check blocks arming in ArduCopter 4.7.2 SITL.
Waits 40 s, then tries to arm in LOITER every 3 s for 20 s; prints PreArm/EKF/GPS messages and the
GPS_RAW_INT fields (fix, sats, eph=HDOP*100, h_acc).  usage: gnss_prearm.py --port 5810"""
import argparse, time
from pymavlink import mavutil
ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=5810); a = ap.parse_args()
m = mavutil.mavlink_connection(f"tcp:127.0.0.1:{a.port}", source_system=255, source_component=190)
m.wait_heartbeat()
m.mav.command_long_send(m.target_system, m.target_component, mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
                        0, mavutil.mavlink.MAVLINK_MSG_ID_GPS_RAW_INT, 1e6, 0, 0, 0, 0, 0)
seen, t0, t_try, raw, armed = set(), time.time(), 0, None, False
while time.time() - t0 < 60 and not armed:
    msg = m.recv_match(blocking=True, timeout=1)
    if msg is None:
        continue
    t = msg.get_type()
    if t == "STATUSTEXT" and any(k in msg.text for k in ("PreArm", "GPS", "EKF", "Arm")) and msg.text not in seen:
        seen.add(msg.text); print(f"[{time.time() - t0:5.1f}s] {msg.text}")
    elif t == "GPS_RAW_INT":
        raw = msg
    elif t == "HEARTBEAT" and msg.get_srcComponent() == 1:
        armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
    if time.time() - t0 > 40 and time.time() - t_try > 3:
        t_try = time.time(); m.set_mode_apm("LOITER")
        m.mav.command_long_send(m.target_system, m.target_component, mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 1, 0, 0, 0, 0, 0, 0)
if raw:
    print(f"GPS_RAW_INT: fix {raw.fix_type}, sats {raw.satellites_visible}, HDOP {raw.eph / 100:.2f}, h_acc {raw.h_acc / 1000:.2f} m")
print("ARMED in LOITER" if armed else "NOT armed after 60 s")
