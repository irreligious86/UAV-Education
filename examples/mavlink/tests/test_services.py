"""mav-services lab: commands, parameters and missions against a lossy fake vehicle."""
import pytest
from pymavlink import mavutil

import mav_client as mc

M = mavutil.mavlink


def client(port):
    return mc.connect(f"udpout:127.0.0.1:{port}", timeout=5)


def test_arm_command_ack(vehicle_factory):
    v, port = vehicle_factory()
    m = client(port)
    assert mc.command(m, M.MAV_CMD_COMPONENT_ARM_DISARM, 1) == M.MAV_RESULT_ACCEPTED
    assert v.armed


def test_rejected_command_raises(vehicle_factory):
    v, port = vehicle_factory()
    m = client(port)
    with pytest.raises(RuntimeError):
        mc.command(m, M.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 10)   # not armed → FAILED


def test_param_roundtrip_with_loss(vehicle_factory):
    v, port = vehicle_factory(loss=0.3)
    m = client(port)
    assert mc.param_set(m, "RTL_ALT", 4500, retries=20) == 4500
    assert mc.param_get(m, "RTL_ALT", retries=20) == 4500


@pytest.mark.parametrize("loss", [0.0, 0.25])
def test_mission_upload_download(vehicle_factory, loss):
    v, port = vehicle_factory(loss=loss)
    m = client(port)
    home = (50.45, 30.52)
    items = [mc.waypoint(0, *home, 0)] + [mc.waypoint(i, home[0] + 0.0002 * i, home[1] + 0.0001 * i, 20 + i) for i in range(1, 8)]
    mc.mission_upload(m, items, timeout=0.3, max_retries=50)
    got = mc.mission_download(m, timeout=0.3, max_retries=50)
    assert [(g.x, g.y, round(g.z, 3)) for g in got] == [(i["x"], i["y"], round(i["z"], 3)) for i in items]
