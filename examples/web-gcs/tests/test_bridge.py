"""Starter tests for the web GCS bridge: message translation and commands against the fake vehicle.
Run: python -m pytest -q examples/web-gcs/tests"""
from __future__ import annotations

import socket
import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "mavlink"))

from pymavlink.dialects.v20 import ardupilotmega as mav  # noqa: E402

import bridge  # noqa: E402
from fake_vehicle import FakeVehicle  # noqa: E402

M = mav


def free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def test_position_frame():
    msg = mav.MAVLink_global_position_int_message(1000, 504500000, 305200000, 150000, 12345, 300, 400, 0, 9000)
    f = bridge.telemetry_json(msg)
    assert f == {"type": "position", "lat": 50.45, "lon": 30.52, "alt_rel": 12.35, "hdg": 90.0, "vel": 5.0}


def test_heartbeat_frame_ignores_non_autopilot():
    gcs = mav.MAVLink_heartbeat_message(M.MAV_TYPE_GCS, M.MAV_AUTOPILOT_INVALID, 0, 0, 0, 3)
    assert bridge.telemetry_json(gcs) is None
    ap = mav.MAVLink_heartbeat_message(M.MAV_TYPE_QUADROTOR, M.MAV_AUTOPILOT_ARDUPILOTMEGA, M.MAV_MODE_FLAG_SAFETY_ARMED, 5, 4, 3)
    f = bridge.telemetry_json(ap)
    assert f["armed"] is True and f["mode"] == "LOITER"


def test_battery_unknowns_are_null():
    msg = mav.MAVLink_sys_status_message(0, 0, 0, 0, 15800, -1, -1, 0, 0, 0, 0, 0, 0)
    assert bridge.telemetry_json(msg) == {"type": "battery", "voltage": 15.8, "current": None, "remaining": None}


@pytest.fixture
def link():
    port = free_port()
    v = FakeVehicle(f"udpin:127.0.0.1:{port}").start()
    frames = []
    lk = bridge.Link(f"udpout:127.0.0.1:{port}", frames.append).start(timeout=5)
    yield lk, v, frames
    lk.close(); v.close()


def test_commands_are_acked_or_rejected(link):
    lk, v, _ = link
    assert lk.execute({"id": 1, "op": "arm"}) == {"type": "ack", "id": 1, "ok": True, "detail": "accepted"}
    assert v.armed
    assert lk.execute({"id": 2, "op": "mode", "mode": "loiter"})["ok"] and v.mode == 5
    bad = lk.execute({"id": 3, "op": "mode", "mode": "WARP"})
    assert bad["ok"] is False and "unknown mode" in bad["detail"]
    assert lk.execute({"id": 4, "op": "selfdestruct"})["ok"] is False


def test_heartbeat_frames_flow(link):
    lk, v, frames = link
    time.sleep(1.5)
    assert any(f["type"] == "heartbeat" for f in frames)
    assert lk.healthy()


def test_link_loss_is_reported(link):
    lk, v, frames = link
    v.close()                                   # vehicle goes silent
    time.sleep(bridge.HEARTBEAT_TIMEOUT_S + 0.5)
    assert not lk.healthy()
    assert {"type": "link", "ok": False} in frames
