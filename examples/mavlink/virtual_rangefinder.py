#!/usr/bin/env python3
"""A MAVLink component: a virtual downward rangefinder that publishes DISTANCE_SENSOR.

ArduPilot uses it when RNGFND1_TYPE = 10 (MAVLink) and RNGFND1_ORIENT = 25 (down).
The component has its own compid (MAV_COMP_ID_PERIPHERAL), sends its own HEARTBEAT, and
reads altitude from GLOBAL_POSITION_INT to fake a terrain-following measurement.

  python virtual_rangefinder.py --master udpin:0.0.0.0:14551 --rate 20   # SITL: add --out=udp:127.0.0.1:14551
"""
from __future__ import annotations

import argparse
import math
import time

from pymavlink import mavutil

M = mavutil.mavlink


class VirtualRangefinder:
    MIN_CM, MAX_CM = 20, 4000

    def __init__(self, conn, sysid: int = 1, compid: int = M.MAV_COMP_ID_PERIPHERAL, noise_cm: float = 2.0):
        self.m = conn if not isinstance(conn, str) else mavutil.mavlink_connection(conn, source_system=sysid, source_component=compid)
        self.noise_cm = noise_cm
        self.t0 = time.time()
        self.alt_m = 0.0

    def heartbeat(self):
        self.m.mav.heartbeat_send(M.MAV_TYPE_GENERIC, M.MAV_AUTOPILOT_INVALID, 0, 0, M.MAV_STATE_ACTIVE)

    def measurement_cm(self, alt_m: float, t: float) -> int:
        terrain = 0.3 * math.sin(0.5 * t)                       # gentle fake terrain
        d = (alt_m - terrain) * 100 + self.noise_cm * math.sin(37 * t)
        return int(max(self.MIN_CM, min(self.MAX_CM, d)))

    def send(self, distance_cm: int):
        self.m.mav.distance_sensor_send(
            int((time.time() - self.t0) * 1000), self.MIN_CM, self.MAX_CM, distance_cm,
            M.MAV_DISTANCE_SENSOR_LASER, 0, M.MAV_SENSOR_ROTATION_PITCH_270, 255)

    def run(self, rate: float = 20.0, duration: float | None = None):
        period = 1.0 / rate
        last_hb = 0.0
        end = None if duration is None else time.time() + duration
        while end is None or time.time() < end:
            now = time.time()
            if now - last_hb > 1.0:
                self.heartbeat(); last_hb = now
            msg = self.m.recv_match(type="GLOBAL_POSITION_INT", blocking=False)
            if msg is not None:
                self.alt_m = msg.relative_alt / 1000.0
            self.send(self.measurement_cm(self.alt_m, now - self.t0))
            time.sleep(period)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--master", default="udpin:0.0.0.0:14551",
                    help="listen where MAVProxy/mavlink-router sends a copy of the stream (udpin), or tcp:127.0.0.1:5762")
    ap.add_argument("--rate", type=float, default=20.0)
    a = ap.parse_args()
    VirtualRangefinder(a.master).run(a.rate)


if __name__ == "__main__":
    main()
