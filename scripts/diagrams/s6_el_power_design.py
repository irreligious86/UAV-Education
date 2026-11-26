"""Diagrams for module el-power-design (thin-module pass, 2026-11).

chart-power-lc-filter   practice step 3 (power_lab.py): transfer function of the LC filter on the 12 V video branch,
                        L = 22 uH (DCR 0.05 Ohm), C = 470 uF, for capacitor ESR 0.01 Ohm (polymer) and 0.15 Ohm
                        (ordinary electrolytic). H = Zc / (Zc + DCR + jwL), Zc = ESR + 1/(jwC). Marks: the resonance
                        f0 = 1/(2*pi*sqrt(LC)) = 1565 Hz and ESC switching 24 / 48 kHz. Numbers match the module text
                        (+11.2 / +2.9 dB peak, -45.6 / -26.8 dB at 24 kHz).
"""
from __future__ import annotations

import math

from plot import Axis, chart

L, C, DCR = 22e-6, 470e-6, 0.05


def _gain_db(f: float, esr: float) -> float:
    w = 2 * math.pi * f
    zc = esr + 1 / complex(0, w * C)
    return 20 * math.log10(abs(zc / (zc + DCR + complex(0, w * L))))


def lc_filter() -> str:
    f0 = 1 / (2 * math.pi * math.sqrt(L * C))
    xs = [100 * 10 ** (k / 40) for k in range(121)]          # 100 Hz ... 100 kHz
    assert round(f0) == 1565
    assert abs(_gain_db(24e3, 0.01) + 45.6) < 0.1 and abs(_gain_db(24e3, 0.15) + 26.8) < 0.1
    return chart(
        "LC-фильтр видео 22 мкГн + 470 мкФ: ослабление по частоте",
        [dict(name="ESR 0.01 Ом (полимер)", xs=xs, ys=[_gain_db(x, 0.01) for x in xs], cls="d",
              label_at=12000, label_dy=18, label_anchor="end"),
         dict(name="ESR 0.15 Ом (электролит)", xs=xs, ys=[_gain_db(x, 0.15) for x in xs], cls="a",
              label_at=4500, label_dy=-12, label_anchor="start")],
        Axis("частота, Гц (логарифмическая шкала)", 100, 100000, log=True,
             ticks=[100, 300, 1000, 3000, 10000, 30000, 100000]),
        Axis("усиление, дБ", -60, 20, ticks=[-60, -40, -20, 0, 20]),
        marks=[(f0, "f₀ = 1565 Гц", "ink", 20), (24000, "ESC 24 кГц", "m", 20), (48000, "48 кГц", "m", 40)],
        notes=[(80, 250, "0 дБ — как без фильтра;", "m"), (80, 266, "выше нуля фильтр усиливает", "m")])


def build(D: dict) -> None:
    D["chart-power-lc-filter"] = lc_filter()
