"""Run: python -m pytest -q examples/precision-landing/tests"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pymavlink.dialects.v20 import ardupilotmega as mav  # noqa: E402

import landing_stats as ls  # noqa: E402
from lt_sender import landing_target_fields  # noqa: E402
from target_sim import TargetSim  # noqa: E402


def test_marker_below_is_on_axis():
    d = TargetSim((0, 0), noise_px=0).detect(1.0, (0, 0, -10), 0, 0, 0, 10)
    assert abs(d.angle_x) < 1e-9 and abs(d.angle_y) < 1e-9 and abs(d.distance - 10) < 1e-9


def test_marker_north_appears_up_in_image():
    # nadir camera, nose north: a marker 2 m north is "forward" = top of the image = negative angle_y
    d = TargetSim((2, 0), noise_px=0).detect(1.0, (0, 0, -10), 0, 0, 0, 10)
    assert d.v < 240 and d.angle_y < 0 and abs(d.angle_x) < 1e-9
    assert abs(math.tan(-d.angle_y) - 0.2) < 1e-9


def test_marker_east_appears_right_and_yaw_rotates_it():
    d = TargetSim((0, 2), noise_px=0).detect(1.0, (0, 0, -10), 0, 0, 0, 10)
    assert d.angle_x > 0
    d90 = TargetSim((0, 2), noise_px=0).detect(1.0, (0, 0, -10), 0, 0, math.pi / 2, 10)   # nose east: marker ahead
    assert d90.angle_y < 0 and abs(d90.angle_x) < 1e-9


def test_too_small_or_out_of_frame_is_not_detected():
    sim = TargetSim((0, 0), marker_size_m=0.5, noise_px=0)
    assert sim.detect(0, (0, 0, 0), 0, 0, 0, sim.capture_range() * 1.05) is None
    assert sim.detect(0, (0, 0, 0), 0, 0, 0, sim.capture_range() * 0.95) is not None
    assert sim.detect(0, (30, 0, -5), 0, 0, 0, 5) is None          # far outside the frame


def test_dropout_rate():
    sim = TargetSim((0, 0), dropout=0.3, seed=1)
    hits = sum(sim.detect(0, (0, 0, -5), 0, 0, 0, 5) is not None for _ in range(2000))
    assert 0.65 < hits / 2000 < 0.75


def test_landing_target_uses_exposure_time_and_encodes():
    sim = TargetSim((1, 1), noise_px=0)
    det = sim.detect(100.0, (0, 0, -8), 0.05, -0.02, 0.3, 8)
    f = landing_target_fields(det, boot_offset_s=40.0)
    assert f["time_usec"] == 60_000_000                  # exposure 100 s on host clock = 60 s since vehicle boot
    msg = mav.MAVLink_landing_target_message(**f)
    enc = mav.MAVLink(None, srcSystem=1, srcComponent=191)
    back = mav.MAVLink(None).decode(bytearray(msg.pack(enc)))
    assert abs(back.angle_x - det.angle_x) < 1e-6 and back.frame == mav.MAV_FRAME_BODY_FRD


def test_landing_stats_acceptance():
    pts = [(3.0 + dx, -2.0) for dx in (0.02, -0.05, 0.1, 0.03, 0.0, -0.12, 0.08, 0.14, -0.01, 0.4)]
    v = ls.verdict(ls.errors(pts, (3.0, -2.0)))
    assert v["within"] == 9 and v["pass"]
    v2 = ls.verdict(ls.errors(pts[:8] + [(3.3, -2.0), (3.5, -2.0)], (3.0, -2.0)))
    assert not v2["pass"]
