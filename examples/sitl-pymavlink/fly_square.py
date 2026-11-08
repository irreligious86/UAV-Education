#!/usr/bin/env python3
"""Arm, take off, fly a 20 m square in GUIDED mode and land. ArduPilot SITL or a real vehicle
with GUIDED available (use with extreme care on hardware)."""
import argparse, math, time
from pymavlink import mavutil


def wait_mode(m, name, timeout=10):
    t0 = time.time()
    while time.time() - t0 < timeout:
        hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
        if hb and mavutil.mode_string_v10(hb) == name:
            return True
    return False


def set_mode(m, name):
    m.set_mode(m.mode_mapping()[name])
    if not wait_mode(m, name):
        raise SystemExit(f"mode {name} not confirmed")


def local_pos(m):
    msg = m.recv_match(type="LOCAL_POSITION_NED", blocking=True, timeout=2)
    return (msg.x, msg.y, -msg.z) if msg else None


def goto_local(m, x, y, z_up, tol=1.0, timeout=60):
    """Send a position setpoint in the local NED frame and wait until within tol metres."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        m.mav.set_position_target_local_ned_send(
            0, m.target_system, m.target_component, mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            0b0000111111111000,  # use position only
            x, y, -z_up, 0, 0, 0, 0, 0, 0, 0, 0)
        p = local_pos(m)
        if p and math.dist(p, (x, y, z_up)) < tol:
            return True
        time.sleep(0.2)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--connect", default="tcp:127.0.0.1:5760")
    ap.add_argument("--alt", type=float, default=10.0)
    ap.add_argument("--side", type=float, default=20.0)
    a = ap.parse_args()

    m = mavutil.mavlink_connection(a.connect)
    m.wait_heartbeat()
    print(f"heartbeat from sys {m.target_system} comp {m.target_component}")

    # wait for a position estimate (EKF ready): GPS_RAW_INT fix >= 3 and LOCAL_POSITION_NED flowing
    while True:
        gps = m.recv_match(type="GPS_RAW_INT", blocking=True, timeout=5)
        if gps and gps.fix_type >= 3 and local_pos(m):
            break
        print("waiting for GPS/EKF...")

    set_mode(m, "GUIDED")
    m.arducopter_arm()
    m.motors_armed_wait()
    print("armed")
    m.mav.command_long_send(m.target_system, m.target_component,
                            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, a.alt)
    while True:
        p = local_pos(m)
        if p and p[2] > a.alt * 0.95:
            break
        time.sleep(0.5)
    print("at altitude")

    s = a.side
    for (x, y) in [(s, 0), (s, s), (0, s), (0, 0)]:
        ok = goto_local(m, x, y, a.alt)
        print(f"waypoint ({x},{y}) {'reached' if ok else 'TIMEOUT'}")

    set_mode(m, "LAND")
    m.motors_disarmed_wait()
    print("landed and disarmed")


if __name__ == "__main__":
    main()
