"""Run: python -m pytest -q examples/lua-protection/tests   (needs: pip install lupa)"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("lupa")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import apmock  # noqa: E402

RTL, LAND, AUTO = 6, 9, 3


def fresh():
    v = apmock.Vehicle()
    _, fn, period = apmock.load(v)
    assert period == 100 and v.texts == ["GRD loaded"]
    assert v.params == {"GRD_ENABLE": 1, "GRD_VIBE_MAX": 30, "GRD_VIBE_S": 2, "GRD_POLY_M": 10}
    return v, fn


def test_quiet_flight_does_nothing():
    v, fn = fresh()
    apmock.run(v, fn, 30)
    assert v.mode == AUTO and v.texts == ["GRD loaded"] and len(v.logs) == 300


def test_short_vibration_spike_is_ignored_sustained_lands():
    v, fn = fresh()
    v.vibe = (45, 10, 10)
    fn = apmock.run(v, fn, 1.5)
    v.vibe = (5, 5, 8)
    fn = apmock.run(v, fn, 1)
    assert v.mode == AUTO                                 # 1.5 s < GRD_VIBE_S
    v.vibe = (45, 10, 10)
    apmock.run(v, fn, 2.2)
    assert v.mode == LAND and "vibration 45" in v.texts[-1]


def test_polygon_margin_triggers_rtl_once():
    v, fn = fresh()
    def drift_east(veh):
        if veh.mode != RTL:                                       # RTL turns the vehicle home
            veh.latlon = (veh.latlon[0], veh.latlon[1] + 2e-6)   # ≈ 0.18 m per 100 ms east
    apmock.run(v, fn, 150, each=drift_east)
    rtl_msgs = [t for t in v.texts if "RTL" in t]
    assert v.mode == RTL and len(rtl_msgs) == 1
    assert 149.16785 < v.latlon[1] < 149.16800                  # acted ≈10 m before the edge


def test_no_fix_does_not_crash():
    v, fn = fresh()
    v.fix = False
    apmock.run(v, fn, 5)
    assert v.mode == AUTO and not any("error" in t for t in v.texts)


def test_script_errors_are_caught_and_fall_back_to_rtl():
    v, fn = fresh()
    v.fail_vibration = True
    apmock.run(v, fn, 0.3)
    assert sum("GRD error" in t for t in v.texts) == 3 and v.mode == RTL


def test_disarm_resets_and_disable_param():
    v, fn = fresh()
    v.vibe = (45, 10, 10)
    fn = apmock.run(v, fn, 2.5)
    assert v.mode == LAND
    v.armed = False; v.mode = AUTO
    fn = apmock.run(v, fn, 1)
    v.armed = True; v.params["GRD_ENABLE"] = 0
    apmock.run(v, fn, 5)
    assert v.mode == AUTO
