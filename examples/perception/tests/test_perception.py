"""Self-test for examples/perception. Run: python -m pytest -q examples/perception/tests"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import camgeo as cg  # noqa: E402
import latency_bench as lb  # noqa: E402
import obstacles as ob  # noqa: E402

K = cg.K_matrix(800, 800, 640, 360)


def test_center_pixel_hits_point_below_when_level():
    g = cg.pixel_to_ground(640, 360, K, 0, 0, 0, 50)
    assert np.allclose(g, [0, 0], atol=1e-9)


def test_image_up_is_forward_for_nadir_camera():
    # downward camera on the nose: top of the image (v < cy) looks forward (north at yaw 0)
    g = cg.pixel_to_ground(640, 360 - 80, K, 0, 0, 0, 100)
    assert g[0] > 0 and abs(g[1]) < 1e-9
    assert abs(g[0] - 100 * 80 / 800) < 1e-9           # similar triangles: 10 m


def test_roll_shifts_footprint():
    g = cg.pixel_to_ground(640, 360, K, math.radians(10), 0, 0, 50)
    # positive roll = right wing down: the belly (and a nadir camera's optical axis) turns to the LEFT,
    # i.e. towards -E at yaw 0. Body z in NED = Rx(roll)·(0,0,1) = (0, -sin roll, cos roll).
    assert abs(g[1] + 50 * math.tan(math.radians(10))) < 1e-9


@pytest.mark.parametrize("roll,pitch,yaw,tilt", [(0.1, -0.05, 1.2, 90), (-0.2, 0.15, -2.5, 60), (0.0, 0.3, 0.7, 45)])
def test_roundtrip_ground_pixel(roll, pitch, yaw, tilt):
    R = cg.R_bc_for_mount(tilt)
    rng = np.random.default_rng(3)
    for _ in range(50):
        u, v = rng.uniform(100, 1180), rng.uniform(100, 620)
        g = cg.pixel_to_ground(u, v, K, roll, pitch, yaw, 40, R_bc=R, k1=-0.1, k2=0.01)
        if g is None:
            continue
        uu, vv = cg.ground_to_pixel(g[0], g[1], K, roll, pitch, yaw, 40, R_bc=R, k1=-0.1, k2=0.01)
        assert abs(uu - u) < 1e-3 and abs(vv - v) < 1e-3


def test_forward_camera_horizon_returns_none():
    R = cg.R_bc_for_mount(0)
    assert cg.pixel_to_ground(640, 360 - 10, K, 0, 0, 0, 30, R_bc=R) is None     # above horizon


def test_undistort_inverts_distort():
    for x, y in [(0.1, 0.2), (-0.4, 0.3), (0.6, -0.5)]:
        xd, yd = cg.distort(np.float64(x), np.float64(y), -0.2, 0.05)
        xu, yu = cg.undistort(float(xd), float(yd), -0.2, 0.05)
        assert abs(xu - x) < 1e-9 and abs(yu - y) < 1e-9


def test_gsd_and_spacing():
    # 1" sensor 13.2 mm wide, 8.8 mm lens, 5472 px, 100 m -> 2.74 cm/px (DJI-class camera)
    assert abs(cg.gsd_cm(100, 13.2, 8.8, 5472) - 2.741) < 0.01
    line, trig = cg.survey_spacing(100, 84.0, 62.0, 0.7, 0.8)
    assert abs(line - 0.3 * 2 * 100 * math.tan(math.radians(42))) < 1e-9 and trig < line


def test_fx_from_hfov():
    assert abs(cg.fx_from_hfov(1280, 90) - 640) < 1e-9


def test_landing_target_angles():
    ax, ay = cg.landing_target_angles(640 + 800 * math.tan(0.1), 360, K)
    assert abs(ax - 0.1) < 1e-9 and abs(ay) < 1e-9


def test_depth_to_sectors_finds_wall():
    depth = np.full((60, 160), np.nan)
    depth[:, 100:120] = 3.0                        # wall to the right of centre
    d, inc, off = ob.depth_to_sectors(depth, 87.0)
    assert inc == 5.0 and len(d) == 72
    b, r = ob.closest(d, inc, off)
    assert 0 < b < 45 and 3.0 <= r < 3.3            # right of forward, slant range a bit above 3 m
    assert d[36] == ob.UNKNOWN                      # behind the camera: unknown, not "clear"


def test_stop_distance_and_speed_are_inverse():
    for v in (2.0, 5.0, 10.0):
        r = ob.stop_distance(v, 3.0, 0.2, 1.0)
        assert abs(ob.max_safe_speed(r, 3.0, 0.2, 1.0) - v) < 1e-9


def test_latency_summary():
    s = lb.summarize([10, 11, 12, 13, 100], budget_ms=50)
    assert s["p50"] == 12 and not s["ok"] and abs(s["over_budget_frac"] - 0.2) < 1e-12
    assert lb.percentile([1, 2, 3, 4], 50) == 2.5
