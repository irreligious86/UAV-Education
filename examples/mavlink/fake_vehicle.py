#!/usr/bin/env python3
"""A tiny MAVLink "vehicle" for tests without SITL.

Speaks just enough of the protocol for the labs: HEARTBEAT at 1 Hz, parameter read/write,
the mission upload/download handshake, COMMAND_LONG with ACKs (arm/disarm, set mode), and
it listens to DISTANCE_SENSOR from other components so a virtual rangefinder can be checked.
It also drops a configurable fraction of outgoing packets to exercise client retries.

  python fake_vehicle.py --port 14560 --loss 0.2
"""
from __future__ import annotations

import argparse
import random
import threading
import time

from pymavlink import mavutil


class FakeVehicle:
    def __init__(self, conn: str = "udpin:127.0.0.1:14560", sysid: int = 1, loss: float = 0.0, seed: int = 1):
        self.m = mavutil.mavlink_connection(conn, source_system=sysid, source_component=1)
        self.loss = loss
        self.rng = random.Random(seed)
        self.params = {"RTL_ALT": 3000.0, "WPNAV_SPEED": 1000.0, "FS_THR_ENABLE": 1.0, "SYSID_THISMAV": float(sysid)}
        self.mission: list = []
        self._upload_expected = 0
        self._upload_items: dict[int, object] = {}
        self.armed = False
        self.mode = 0
        self.distance_sensor: list = []      # received DISTANCE_SENSOR messages
        self.stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    # -- sending with simulated loss -------------------------------------------------
    def _maybe_drop(self) -> bool:
        return self.loss > 0 and self.rng.random() < self.loss

    def send(self, fn, *args, **kw):
        if self._maybe_drop():
            return
        with self._lock:
            fn(*args, **kw)

    def heartbeat(self):
        base = mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED | (mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED if self.armed else 0)
        self.send(self.m.mav.heartbeat_send, mavutil.mavlink.MAV_TYPE_QUADROTOR, mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
                  base, self.mode, mavutil.mavlink.MAV_STATE_STANDBY)

    # -- message handling ------------------------------------------------------------
    def handle(self, msg) -> None:
        t = msg.get_type()
        if t == "HEARTBEAT":
            return
        if t == "PARAM_REQUEST_LIST":
            keys = sorted(self.params)
            for i, k in enumerate(keys):
                self.send(self.m.mav.param_value_send, k.encode(), self.params[k], mavutil.mavlink.MAV_PARAM_TYPE_REAL32, len(keys), i)
        elif t == "PARAM_REQUEST_READ":
            k = msg.param_id if isinstance(msg.param_id, str) else msg.param_id.decode().rstrip("\x00")
            if k in self.params:
                self.send(self.m.mav.param_value_send, k.encode(), self.params[k], mavutil.mavlink.MAV_PARAM_TYPE_REAL32, len(self.params), sorted(self.params).index(k))
        elif t == "PARAM_SET":
            k = msg.param_id if isinstance(msg.param_id, str) else msg.param_id.decode().rstrip("\x00")
            if k in self.params:
                self.params[k] = float(msg.param_value)
                self.send(self.m.mav.param_value_send, k.encode(), self.params[k], mavutil.mavlink.MAV_PARAM_TYPE_REAL32, len(self.params), sorted(self.params).index(k))
        elif t == "MISSION_COUNT":
            self._upload_expected = msg.count
            self._upload_items = {}
            if msg.count == 0:
                self.mission = []
                self.send(self.m.mav.mission_ack_send, msg.get_srcSystem(), msg.get_srcComponent(), mavutil.mavlink.MAV_MISSION_ACCEPTED)
            else:
                self.send(self.m.mav.mission_request_int_send, msg.get_srcSystem(), msg.get_srcComponent(), 0)
        elif t == "MISSION_ITEM_INT":
            self._upload_items[msg.seq] = msg
            nxt = next((i for i in range(self._upload_expected) if i not in self._upload_items), None)
            if nxt is None:
                self.mission = [self._upload_items[i] for i in range(self._upload_expected)]
                self.send(self.m.mav.mission_ack_send, msg.get_srcSystem(), msg.get_srcComponent(), mavutil.mavlink.MAV_MISSION_ACCEPTED)
            else:
                self.send(self.m.mav.mission_request_int_send, msg.get_srcSystem(), msg.get_srcComponent(), nxt)
        elif t == "MISSION_REQUEST_LIST":
            self.send(self.m.mav.mission_count_send, msg.get_srcSystem(), msg.get_srcComponent(), len(self.mission))
        elif t == "MISSION_REQUEST_INT":
            if msg.seq < len(self.mission):
                it = self.mission[msg.seq]
                self.send(self.m.mav.mission_item_int_send, msg.get_srcSystem(), msg.get_srcComponent(), it.seq, it.frame, it.command,
                          it.current, it.autocontinue, it.param1, it.param2, it.param3, it.param4, it.x, it.y, it.z)
        elif t == "MISSION_ACK":
            pass
        elif t == "COMMAND_LONG":
            res = mavutil.mavlink.MAV_RESULT_ACCEPTED
            if msg.command == mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM:
                self.armed = msg.param1 >= 0.5
            elif msg.command == mavutil.mavlink.MAV_CMD_DO_SET_MODE:
                self.mode = int(msg.param2)
            elif msg.command == mavutil.mavlink.MAV_CMD_NAV_TAKEOFF:
                res = mavutil.mavlink.MAV_RESULT_ACCEPTED if self.armed else mavutil.mavlink.MAV_RESULT_FAILED
            else:
                res = mavutil.mavlink.MAV_RESULT_UNSUPPORTED
            self.send(self.m.mav.command_ack_send, msg.command, res)
        elif t == "DISTANCE_SENSOR":
            self.distance_sensor.append(msg)
        elif t == "TIMESYNC":
            if msg.tc1 == 0:
                self.send(self.m.mav.timesync_send, int(time.time() * 1e9), msg.ts1)

    # -- main loop ---------------------------------------------------------------------
    def run(self) -> None:
        last_hb = 0.0
        while not self.stop.is_set():
            now = time.time()
            if now - last_hb >= 1.0:
                self.heartbeat(); last_hb = now
            msg = self.m.recv_match(blocking=True, timeout=0.05)
            if msg is not None:
                self.handle(msg)

    def start(self) -> "FakeVehicle":
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()
        return self

    def close(self) -> None:
        self.stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        self.m.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=14560)
    ap.add_argument("--loss", type=float, default=0.0, help="fraction of outgoing packets to drop")
    a = ap.parse_args()
    v = FakeVehicle(f"udpin:127.0.0.1:{a.port}", loss=a.loss)
    print(f"fake vehicle on udp 127.0.0.1:{a.port}, loss {a.loss}")
    try:
        v.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
