"""Thin-module review diagrams for rf-link-budget.

chart-link-two-ray — received power of the module's worked example (ELRS 2.4 GHz 250 Hz, 250 mW,
                     antennas 2 / 0 dBi, 1 dB cables, 3 dB polarisation) over distance: free space against
                     the two-ray ground-reflection model (flat ground, reflection coefficient -1, ground
                     antenna 1.5 m) for an aircraft at 10 m and at 120 m; mode sensitivity -108 dBm and the
                     course warning threshold -98 dBm as horizontal lines. Same formulas as the module's
                     link_lab.py (practice, step 3).
"""
from __future__ import annotations

import math

from plot import Axis, chart

C = 299_792_458.0
F_MHZ = 2440.0
LAM = C / (F_MHZ * 1e6)
EIRP_MINUS_LOSSES = 24.0 + 2.0 + 0.0 - 1.0 - 3.0     # P_tx + G_tx + G_rx - L_cab - L_pol, dB(m)
SENS, WARN_DBM = -108.0, -98.0
H_GROUND = 1.5


def _fspl(d_km: float) -> float:
    return 20 * math.log10(d_km) + 20 * math.log10(F_MHZ) + 32.44


def _two_ray_excess(d_m: float, ht: float, hr: float) -> float:
    direct = math.hypot(d_m, hr - ht)
    refl = math.hypot(d_m, hr + ht)
    dphi = 2 * math.pi * (refl - direct) / LAM
    a = direct / refl
    re, im = 1 - a * math.cos(dphi), a * math.sin(dphi)
    return -20 * math.log10(max(math.hypot(re, im), 1e-3))


def _logspace(a: float, b: float, n: int = 400) -> list[float]:
    la, lb = math.log10(a), math.log10(b)
    return [10 ** (la + (lb - la) * i / (n - 1)) for i in range(n)]


def build(D: dict) -> None:
    xs = _logspace(0.3, 20)
    free = [EIRP_MINUS_LOSSES - _fspl(d) for d in xs]
    low = [EIRP_MINUS_LOSSES - _fspl(d) - _two_ray_excess(d * 1000, H_GROUND, 10) for d in xs]
    high = [EIRP_MINUS_LOSSES - _fspl(d) - _two_ray_excess(d * 1000, H_GROUND, 120) for d in xs]
    D["chart-link-two-ray"] = chart(
        "ELRS 2.4 ГГц, 250 мВт: свободное пространство против отражения от земли",
        [dict(name="", xs=xs, ys=high, cls="m", w=1.4),
         dict(name="", xs=xs, ys=low, cls="d"),
         dict(name="", xs=xs, ys=free, cls="a")],
        x=Axis("Дистанция, км (антенна земли 1.5 м)", 0.3, 20, log=True, ticks=[0.5, 1, 2, 5, 10, 20]),
        y=Axis("Принятая мощность, дБм", -125, -60),
        hmarks=[(SENS, "", "d"), (WARN_DBM, "предупреждение S+10 = −98", "w")],
        marks=[(4 * H_GROUND * 10 / LAM / 1000, "излом 10 м: 0.49 км", "d", 290),
               (4 * H_GROUND * 120 / LAM / 1000, "излом 120 м: 5.9 км", "m", 20)],
        notes=[(150, 270, "чувствительность 250 Гц −108", "d")],
        legend=[("свободное пространство", "a", False), ("аппарат 10 м", "d", False),
                ("аппарат 120 м", "m", False)], legend_at=(500, 100),
        height=380)
