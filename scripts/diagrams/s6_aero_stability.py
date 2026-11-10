"""Stage 6 charts for aero-stability: static margin vs CG and the drag polar of the worked example.

Numbers are the module's worked example: Skywalker 1830 (span 1.83 m, wing area 0.4106 m^2,
manufacturer CG 90-100 mm, flying weight 2.7 kg), tail AR 4, eta 0.9, C_D0 0.040, e 0.80, eta_total 0.5.
"""
from __future__ import annotations

import math

from plot import Axis, chart

RHO, G = 1.225, 9.81
B, S = 1.83, 0.4106
MAC = S / B
AR = B ** 2 / S


def _lift_slope(ar):
    return 2 * math.pi * ar / (2 + math.sqrt(ar ** 2 + 4))


def _np(v_h, ar_t=4.0, eta=0.9):
    a_w, a_t = _lift_slope(AR), _lift_slope(ar_t)
    deda = 2 * a_w / (math.pi * AR)
    return 0.25 + eta * v_h * (a_t / a_w) * (1 - deda)


def _lin(a, b, n=120):
    return [a + (b - a) * i / (n - 1) for i in range(n)]


def build(D: dict) -> None:
    # ------------------------------------------------------------ static margin vs CG
    xs = _lin(60, 140)
    series = []
    for v_h, cls, dash in ((0.5, "w", True), (0.6, "a", False), (0.7, "ink", False)):
        h_n = _np(v_h)
        series.append(dict(name="", xs=xs, ys=[(h_n - x / 1000 / MAC) * 100 for x in xs], cls=cls, dash=dash))
    D["chart-stability-margin"] = chart(
        "Статический запас от положения ЦТ: Skywalker 1830, САХ 224 мм",
        series,
        Axis("ЦТ за передней кромкой, мм", 60, 140), Axis("статический запас, % САХ", -15, 35),
        bands=[(90, 100, "ЦТ по инструкции")],
        hmarks=[(15, "15 %: тяжёлый нос", "m"), (5, "5 %: нижняя граница", "w"), (0, "0: нейтрально", "d")],
        legend=[("V_h = 0.7", "ink", False), ("V_h = 0.6", "a", False), ("V_h = 0.5", "w", True)], legend_at=(80, 250),
        notes=[(330, 300, "V_h 0.6: ЦТ 92 мм → запас 10 %", "a")])

    # ------------------------------------------------------------ drag polar: power and L/D vs speed
    m, cd0, e, eta = 2.7, 0.040, 0.80, 0.5
    w = m * G
    k = 1 / (math.pi * e * AR)
    vs = _lin(7, 20)

    def cl(v):
        return 2 * w / (RHO * S * v ** 2)

    def cd(v):
        return cd0 + k * cl(v) ** 2

    power = [w * cd(v) / cl(v) * v / eta for v in vs]
    ld = [cl(v) / cd(v) for v in vs]
    D["chart-stability-polar"] = chart(
        "Поляра в скоростях: мощность и качество, 2.7 кг, C_D0 0.040, e 0.8",
        [dict(name="мощность от АКБ, Вт", xs=vs, ys=power, cls="a", label_at=13, label_dy=22, label_anchor="start"),
         dict(name="качество L/D", xs=vs, ys=ld, cls="w", axis=2, label_at=18.5, label_dy=18)],
        Axis("воздушная скорость, м/с", 7, 20), Axis("мощность, Вт (η 0.5)", 0, 160), Axis("L/D", 0, 14),
        bands=[(7, 9.4, "ниже V_s")],
        marks=[(8.2, "V_mp 8.2", "m", 46), (9.4, "V_s 9.4", "d", 62), (10.8, "V_md 10.8: L/D 11.3", "a", 78)],
        notes=[(330, 250, "10.8 м/с: 50 Вт; 12: 57 Вт; 15: 86 Вт", "m")])
