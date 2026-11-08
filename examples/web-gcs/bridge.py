#!/usr/bin/env python3
"""MAVLink -> WebSocket bridge for a browser GCS (project #1 starter).

  pip install pymavlink websockets
  python bridge.py --mavlink udpin:0.0.0.0:14550 --port 8765      # then open web/index.html

Design:
  * `telemetry_json(msg)` turns one MAVLink message into one small JSON frame (pure function, tested).
  * `Link` owns the MAVLink connection in a thread and tracks link health (heartbeat age).
  * Commands from the browser are JSON {"op": "arm"|"disarm"|"mode", ...}; each is executed with
    COMMAND_LONG + COMMAND_ACK retries (examples/mavlink/mav_client.py) and answered with
    {"type": "ack", "id": ..., "ok": bool, "detail": str}. The UI never shows a command as done
    without that answer.
Protocol: docs/protocol.md.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import threading
import time
from pathlib import Path

from pymavlink import mavutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mavlink"))
import mav_client as mc  # noqa: E402

M = mavutil.mavlink
HEARTBEAT_TIMEOUT_S = 3.0

# ArduCopter custom modes (subset). PX4 uses a different encoding — see docs/protocol.md.
COPTER_MODES = {0: "STABILIZE", 2: "ALT_HOLD", 3: "AUTO", 4: "GUIDED", 5: "LOITER", 6: "RTL", 9: "LAND", 16: "POSHOLD"}
COPTER_MODE_IDS = {v: k for k, v in COPTER_MODES.items()}


def telemetry_json(msg) -> dict | None:
    """One MAVLink message -> one JSON-able dict for the browser, or None if the UI does not need it."""
    t = msg.get_type()
    if t == "HEARTBEAT":
        if msg.autopilot == M.MAV_AUTOPILOT_INVALID:          # GCS, companion, peripherals: not the vehicle
            return None
        return {"type": "heartbeat", "armed": bool(msg.base_mode & M.MAV_MODE_FLAG_SAFETY_ARMED),
                "mode": COPTER_MODES.get(msg.custom_mode, str(msg.custom_mode)), "sysid": msg.get_srcSystem()}
    if t == "GLOBAL_POSITION_INT":
        return {"type": "position", "lat": msg.lat / 1e7, "lon": msg.lon / 1e7,
                "alt_rel": round(msg.relative_alt / 1000.0, 2), "hdg": None if msg.hdg == 65535 else msg.hdg / 100.0,
                "vel": round(math.hypot(msg.vx, msg.vy) / 100.0, 2)}
    if t == "ATTITUDE":
        return {"type": "attitude", "roll": round(math.degrees(msg.roll), 1), "pitch": round(math.degrees(msg.pitch), 1),
                "yaw": round(math.degrees(msg.yaw) % 360, 1)}
    if t == "SYS_STATUS":
        return {"type": "battery", "voltage": round(msg.voltage_battery / 1000.0, 2),
                "current": None if msg.current_battery < 0 else round(msg.current_battery / 100.0, 1),
                "remaining": None if msg.battery_remaining < 0 else msg.battery_remaining}
    if t == "STATUSTEXT":
        text = msg.text if isinstance(msg.text, str) else msg.text.decode(errors="replace")
        return {"type": "text", "severity": msg.severity, "text": text.rstrip("\x00")}
    return None


class Link:
    """MAVLink connection + receive thread. Telemetry frames go to `on_frame` (thread-safe callback)."""

    def __init__(self, url: str, on_frame):
        self.url = url
        self.on_frame = on_frame
        self.m = None
        self.last_hb = 0.0
        self.stop = threading.Event()
        self.lock = threading.Lock()          # commands and the receive loop share the connection
        self._rx: threading.Thread | None = None

    def start(self, timeout: float = 10.0) -> "Link":
        self.m = mc.connect(self.url, timeout=timeout)
        self.last_hb = time.time()
        self._rx = threading.Thread(target=self._loop, daemon=True)
        self._rx.start()
        return self

    def healthy(self) -> bool:
        return time.time() - self.last_hb < HEARTBEAT_TIMEOUT_S

    def _loop(self) -> None:
        was_ok = True
        while not self.stop.is_set():
            with self.lock:
                msg = self.m.recv_match(blocking=False)
            if msg is None:
                ok = self.healthy()
                if ok != was_ok:
                    self.on_frame({"type": "link", "ok": ok})
                    was_ok = ok
                time.sleep(0.01)
                continue
            if msg.get_type() == "HEARTBEAT" and msg.autopilot != M.MAV_AUTOPILOT_INVALID:
                self.last_hb = time.time()
                if not was_ok:
                    self.on_frame({"type": "link", "ok": True}); was_ok = True
            frame = telemetry_json(msg)
            if frame is not None:
                self.on_frame(frame)

    def execute(self, req: dict) -> dict:
        """Run one browser command; always returns an ack frame."""
        rid = req.get("id")
        try:
            op = req.get("op")
            with self.lock:
                if op in ("arm", "disarm"):
                    mc.command(self.m, M.MAV_CMD_COMPONENT_ARM_DISARM, 1 if op == "arm" else 0)
                elif op == "mode":
                    mode = str(req.get("mode", "")).upper()
                    if mode not in COPTER_MODE_IDS:
                        raise ValueError(f"unknown mode {mode}")
                    mc.command(self.m, M.MAV_CMD_DO_SET_MODE, M.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, COPTER_MODE_IDS[mode])
                else:
                    raise ValueError(f"unknown op {op}")
            return {"type": "ack", "id": rid, "ok": True, "detail": "accepted"}
        except Exception as e:                     # rejection, timeout, bad request: report, never pretend
            return {"type": "ack", "id": rid, "ok": False, "detail": str(e)}

    def close(self) -> None:
        self.stop.set()
        if self._rx:
            self._rx.join(timeout=2)
        if self.m:
            self.m.close()


async def serve(mavlink_url: str, host: str, port: int) -> None:
    import websockets

    clients: set = set()
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue(maxsize=1000)

    def on_frame(frame: dict) -> None:
        loop.call_soon_threadsafe(lambda: queue.full() or queue.put_nowait(frame))

    link = Link(mavlink_url, on_frame).start()

    async def fanout():
        while True:
            frame = await queue.get()
            data = json.dumps(frame)
            for ws in list(clients):
                try:
                    await ws.send(data)
                except Exception:
                    clients.discard(ws)

    async def handler(ws):
        clients.add(ws)
        await ws.send(json.dumps({"type": "link", "ok": link.healthy()}))
        try:
            async for raw in ws:
                req = json.loads(raw)
                ack = await asyncio.to_thread(link.execute, req)    # retries block: keep them off the event loop
                await ws.send(json.dumps(ack))
        finally:
            clients.discard(ws)

    asyncio.create_task(fanout())
    async with websockets.serve(handler, host, port):
        print(f"bridge: {mavlink_url} -> ws://{host}:{port}")
        await asyncio.Future()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mavlink", default="udpin:0.0.0.0:14550")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    try:
        asyncio.run(serve(a.mavlink, a.host, a.port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
