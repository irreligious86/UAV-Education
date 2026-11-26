"""Diagrams for module el-measure (thin-module pass, 2026-11).

chart-measure-current-calibration   practice step 5 (calib_lab.py): error of the Betaflight current reading against
                                    true current for one sensor (50 mV offset + 27.5 mV/A) with three settings —
                                    the default ibata_scale 400; scale-only calibration from one flight's mAh
                                    (400 * 1018 / 1350 = 302); two-point calibration from three clamp points
                                    (ibata_scale 275, ibata_offset -1827 mA). I_mA = 10000 * mV / scale + offset
                                    (src/main/sensors/current.c, Betaflight 2025.12.5). Marks: the clamp points.
"""
from __future__ import annotations

from plot import Axis, chart


def _reading(i_true: float, scale: float, offset_ma: float) -> float:
    mv = 50 + 27.5 * i_true
    return (10000 * mv / scale + offset_ma) / 1000


def calibration() -> str:
    xs = [1 + 0.25 * k for k in range(117)]                # 1 ... 30 A
    s1 = round(400 * 1018 / 1350)                          # 302
    assert s1 == 302
    err = lambda sc, off: [(_reading(x, sc, off) / x - 1) * 100 for x in xs]
    e2 = err(275, -1827)
    assert max(abs(v) for v in e2[4:]) < 0.5               # two-point: < 0.5 % from 2 A up
    assert abs(err(302, 0)[4] - 74.1) < 0.5                # +74 % at 2 A, as in the module
    return chart(
        "Ошибка тока Betaflight до и после калибровки (датчик 50 мВ + 27.5 мВ/А)",
        [dict(name="умолчание 400", xs=xs, ys=err(400, 0), cls="d", label_at=30, label_dy=14),
         dict(name="по мА·ч: 302", xs=xs, ys=err(302, 0), cls="w", label_at=9, label_dy=-8, label_anchor="start"),
         dict(name="две точки: 275 / −1827 мА", xs=xs, ys=e2, cls="a", label_at=24, label_dy=16)],
        Axis("истинный ток по клещам, А", 0, 30, ticks=[0, 2, 5, 10, 15, 20, 25, 30]),
        Axis("ошибка показания, %", -40, 80, ticks=[-40, -20, 0, 20, 40, 60, 80]),
        marks=[(2, "2 А", "m", 20), (10, "10 А", "m", 20), (25, "25 А", "m", 20)],
        notes=[(284, 96, "калибровка по одному полёту", "m"),
               (284, 112, "точна только около его среднего", "m"),
               (284, 128, "тока (~19 А): смещение остаётся", "m")])


def build(D: dict) -> None:
    D["chart-measure-current-calibration"] = calibration()
