#!/usr/bin/env python3
"""Feed SITL with LANDING_TARGET from the synthetic camera (project #5 starter).

  # ArduPilot SITL: PLND_ENABLED=1 PLND_TYPE=1 PLND_EST_TYPE=1 RNGFND1_TYPE=100 RNGFND1_MAX=30 ...
  python lt_sender.py --url udpin:0.0.0.0:14551 --marker 3.0 -2.0

Reads LOCAL_POSITION_NED, ATTITUDE and DISTANCE_SENSOR (or relative altitude) from the vehicle, runs the
synthetic camera at --fps, delays each detection by the camera latency and sends LANDING_TARGET with
time_usec = exposure time. Any monotonic clock works: ArduPilot's jitter correction learns the clock offset
from the fastest messages, which removes the *variable* part of the delay; the *constant* camera latency
looks like clock offset to it and must be set as PLND_LAG (here ≈ Camera.latency_s). We stamp on the
vehicle's boot clock only so the numbers are readable next to the log.
"""
from __future__ import annotations

import argparse
import collections
import time

from pymavlink import mavutil

from target_sim import Camera, TargetSim

M = mavutil.mavlink


def landing_target_fields(det, boot_offset_s: float) -> dict:
    """Arguments for landing_target_send(); time is the exposure time on the vehicle's boot clock (µs)."""
    return dict(time_usec=max(0, int((det.t_exposure - boot_offset_s) * 1e6)), target_num=0, frame=M.MAV_FRAME_BODY_FRD,
                angle_x=det.angle_x, angle_y=det.angle_y, distance=det.distance, size_x=0.0, size_y=0.0)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="udpin:0.0.0.0:14551")
    ap.add_argument("--marker", nargs=2, type=float, default=(0.0, 0.0), metavar=("N", "E"))
    ap.add_argument("--fps", type=float, default=20.0)
    ap.add_argument("--dropout", type=float, default=0.0)
    a = ap.parse_args()
    m = mavutil.mavlink_connection(a.url, source_system=1, source_component=M.MAV_COMP_ID_ONBOARD_COMPUTER)
    m.wait_heartbeat()
    sim = TargetSim(tuple(a.marker), dropout=a.dropout, camera=Camera())
    state = {"pos": None, "att": None, "hagl": None, "boot_offset": None}
    pending = collections.deque()
    next_frame = time.time()
    print(f"capture range {sim.capture_range():.1f} m; sending LANDING_TARGET")
    while True:
        msg = m.recv_match(blocking=True, timeout=0.01)
        now = time.time()
        if msg is not None:
            t = msg.get_type()
            if t == "LOCAL_POSITION_NED":
                state["pos"] = (msg.x, msg.y, msg.z)
                state["boot_offset"] = now - msg.time_boot_ms / 1000.0
                if state["hagl"] is None:
                    state["hagl"] = -msg.z
            elif t == "ATTITUDE":
                state["att"] = (msg.roll, msg.pitch, msg.yaw)
            elif t == "DISTANCE_SENSOR" and msg.orientation == M.MAV_SENSOR_ROTATION_PITCH_270:
                state["hagl"] = msg.current_distance / 100.0
        if now >= next_frame and state["pos"] and state["att"] and state["hagl"] is not None:
            next_frame += 1.0 / a.fps
            det = sim.detect(now, state["pos"], *state["att"], state["hagl"])
            if det:
                pending.append((now + sim.cam.latency_s, det))
        while pending and pending[0][0] <= now:
            _, det = pending.popleft()
            m.mav.landing_target_send(**landing_target_fields(det, state["boot_offset"]))


if __name__ == "__main__":
    main()
