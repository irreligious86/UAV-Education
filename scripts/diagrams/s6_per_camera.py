"""Stage 6 thin-module diagram for per-camera.

camera-motion-blur — motion blur in pixels vs exposure time (log-log) for the module's worked example:
                     Raspberry Pi Camera Module 3 in the 2304x1296 mode (effective pixel 2.8 um, f = 4.74 mm,
                     f_px = 1693), nadir at 50 m (GSD 2.95 cm/px): translation 10 m/s (v*t/GSD) and rotation
                     90 deg/s across the optical axis (omega*t*f_px); 1/500 s marked, 0.5 and 1 px levels.
"""
from __future__ import annotations

import math

from plot import Axis, chart

P, F, H = 2.8e-6, 4.74e-3, 50.0
GSD = H * P / F
FPX = F / P


def motion_blur() -> str:
    ts = [10 ** (math.log10(0.4) + i * (math.log10(20) - math.log10(0.4)) / 80) for i in range(81)]   # ms
    trans = [10.0 * t / 1000 / GSD for t in ts]
    rot = [math.radians(90) * t / 1000 * FPX for t in ts]
    return chart(
        "Смаз за экспозицию: CM3 2304×1296, 50 м, GSD 2.95 см/px",
        [dict(name="вращение 90°/с", xs=ts, ys=rot, cls="w"),
         dict(name="полёт 10 м/с", xs=ts, ys=trans, cls="a")],
        Axis("экспозиция, мс (лог. шкала)", 0.4, 20, log=True, ticks=[0.5, 1, 2, 5, 10, 20]),
        Axis("смаз, px (лог. шкала)", 0.05, 100, log=True, ticks=[0.1, 0.5, 1, 5, 10, 50]),
        marks=[(2.0, "1/500 с: 0.68 px и 5.3 px", "ink", 20)],
        hmarks=[(1.0, "1 px", "d"), (0.5, "0.5 px — трекинг признаков", "m")])


def build(D: dict) -> None:
    D["camera-motion-blur"] = motion_blur()
