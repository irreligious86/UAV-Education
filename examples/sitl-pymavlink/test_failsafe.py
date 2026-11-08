#!/usr/bin/env python3
"""RC-failsafe test for ArduPilot SITL: exit 0 if the vehicle switches to RTL/LAND within 5 s
of simulated RC loss, exit 1 otherwise. Intended for CI."""
import argparse, sys, time
from pymavlink import mavutil


def set_param(m, name, value):
    m.mav.param_set_send(m.target_system, m.target_component, name.encode(), float(value),
                         mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
    for _ in range(10):
        msg = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=1)
        if msg and msg.param_id.strip("\x00") == name:
            return msg.param_value
    raise RuntimeError(f"param {name} not acknowledged")


def mode_name(m):
    hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=2)
    return mavutil.mode_string_v10(hb) if hb else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--connect", default="tcp:127.0.0.1:5760")
    a = ap.parse_args()
    m = mavutil.mavlink_connection(a.connect)
    m.wait_heartbeat()

    fs = set_param(m, "FS_THR_ENABLE", 1)  # 1 = RTL (do not silently "fix" a broken config in real CI;
    print("FS_THR_ENABLE =", fs)           #     here we set it so the test documents the expectation)

    # wait for EKF/GPS
    while True:
        gps = m.recv_match(type="GPS_RAW_INT", blocking=True, timeout=5)
        if gps and gps.fix_type >= 3:
            break
    m.set_mode(m.mode_mapping()["GUIDED"])
    time.sleep(1)
    m.arducopter_arm(); m.motors_armed_wait()
    m.mav.command_long_send(m.target_system, m.target_component,
                            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, 10)
    time.sleep(12)

    set_param(m, "SIM_RC_FAIL", 1)         # simulate loss of RC
    t0 = time.time(); seen = None
    while time.time() - t0 < 5:
        seen = mode_name(m)
        if seen in ("RTL", "LAND", "SMART_RTL"):
            print(f"PASS: mode {seen} after {time.time() - t0:.1f} s")
            set_param(m, "SIM_RC_FAIL", 0)
            sys.exit(0)
    print(f"FAIL: mode still {seen} 5 s after RC loss")
    sys.exit(1)


if __name__ == "__main__":
    main()
