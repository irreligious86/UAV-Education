"""Thin-module review diagrams for aero-wing.

chart-wing-stall-prevention — ArduPlane 4.7.2 stall prevention (ArduPlane/Attitude.cpp:695-762): bank limit
                              acos(1/n_max), n_max = (V / V_stall_1g)^2, floor 25 deg, capped by ROLL_LIMIT_DEG 45,
                              for the module's worked example (AIRSPEED_MIN 10 m/s) with AIRSPEED_STALL = 0 (firmware
                              then takes AIRSPEED_MIN as the 1 g stall speed) and AIRSPEED_STALL = 8.5 m/s (the
                              calculated V_s). Same function as wing_lab.py in the module's practice.
"""
from __future__ import annotations

import math

from plot import Axis, chart


def _roll_limit(v: float, airspeed_min: float, airspeed_stall: float = 0.0, roll_limit: float = 45) -> float:
    vs1g = airspeed_stall if airspeed_stall > 0 else airspeed_min
    n_max = (v / max(vs1g, 1)) ** 2
    n_dem = 1 / math.cos(math.radians(85))
    if n_max <= 1:
        lim = 25.0
    elif n_max < n_dem:
        lim = max(math.degrees(math.acos(1 / n_max)), 25.0, 5.0)
    else:
        lim = roll_limit
    return min(lim, roll_limit)


def build(D: dict) -> None:
    xs = [8 + i * 0.02 for i in range(351)]          # 8..15 m/s
    D["chart-wing-stall-prevention"] = chart(
        "ArduPlane 4.7: предел крена STALL_PREVENTION, AIRSPEED_MIN = 10 м/с",
        [dict(name="", xs=xs, ys=[_roll_limit(v, 10) for v in xs], cls="d"),
         dict(name="", xs=xs, ys=[_roll_limit(v, 10, 8.5) for v in xs], cls="a")],
        x=Axis("Воздушная скорость (EAS), м/с", 8, 15),
        y=Axis("Разрешённый крен, °", 0, 50),
        hmarks=[(45, "ROLL_LIMIT_DEG = 45", "ink"), (25, "нижний предел 25°", "m")],
        marks=[(8.53, "V_s 8.5", "a", 210), (10, "AIRSPEED_MIN", "d", 230), (11.9, "крейсер 11.9", "ink", 210)],
        legend=[("AIRSPEED_STALL = 8.5 (= V_s)", "a", False),
                ("AIRSPEED_STALL = 0 (= MIN)", "d", False)], legend_at=(450, 196),
        height=340)
