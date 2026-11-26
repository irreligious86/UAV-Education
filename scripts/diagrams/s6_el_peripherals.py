"""Thin-module pass (stage 6) diagram for module el-peripherals.

chart-i2c-pullup-window — allowed I2C pull-up resistance versus bus capacitance at 3.3 V, from TI SLVA689 (I2C-bus
                          spec values): Rp_min = (3.3 - 0.4) / 3 mA = 967 Ohm; Rp_max = tr / (0.8473 * Cb) with
                          tr = 1000 ns (100 kHz) and 300 ns (400 kHz). The module's worked example (periph_lab.py):
                          FC 4.7k || GPS 4.7k = 2.35 kOhm; at an example 100 pF Rp_max(400 kHz) = 3.54 kOhm, so 4.7k alone
                          is too weak for 400 kHz on a 100 pF bus, 2.35k fits; at 200 pF the 400 kHz window
                          is 0.97-1.77 kOhm.
"""
from __future__ import annotations

from plot import Axis, chart

RP_MIN = (3.3 - 0.4) / 3e-3 / 1000          # kOhm


def rmax(tr_ns: float, cb_pf: float) -> float:
    return tr_ns / (0.8473 * cb_pf) # ns/pF = kOhm


def pullup_chart() -> str:
    cbs = [20 + 5 * i for i in range(57)]   # 20 ... 300 pF
    series = [
        dict(name="100 кГц", xs=cbs, ys=[rmax(1000, c) for c in cbs], cls="a", label_at=180),
        dict(name="400 кГц", xs=cbs, ys=[rmax(300, c) for c in cbs], cls="ink", label_at=70, label_dy=-8),
    ]
    return chart("Окно подтяжки I²C при 3.3 В: ниже кривой и выше 0.97 кОм",
                 series, Axis("ёмкость шины Cb, пФ", 0, 300), Axis("Rp, кОм (лог.)", 0.5, 30, log=True),
                 hmarks=[(RP_MIN, "Rp_min 0.97 кОм (3 мА)", "d"), (4.7, "4.7 кОм — одна подтяжка", "w"),
                         (2.35, "2.35 кОм — FC ∥ GPS", "w")],
                 marks=[(100, "пример: 100 пФ", "m"), (200, "200 пФ", "m", 44)],
                 height=340)


def build(D: dict) -> None:
    D["chart-i2c-pullup-window"] = pullup_chart()
