"""Stage 6 diagrams for des-sizing: endurance vs battery size, configuration choice.

Numbers come from the module's worked example: payload 1.0 kg, T-Motor MN4014 KV330 (datasheet table
at 22.2 V), Molicel P45B cells in 6S·nP, frame 18 % of take-off mass, 10 W avionics, 85 % usable
energy, 20 % reserve. The model is the same as the sizing script in the module's practice section.
"""
from __future__ import annotations

import math

from plot import Axis, chart
from svg import Node, tree

RHO, G = 1.225, 9.81
TABLE = {15: [(830, 79.92), (1150, 130.98), (1430, 173.16)],      # MN4014 KV330, 50/65/75 % rows
         17: [(1050, 104.34), (1580, 177.60), (1970, 237.54)]}


def _area(d_in: float) -> float:
    return math.pi * (d_in * 0.0254 / 2) ** 2


def _p_ideal(t_n: float, area: float) -> float:
    return t_n ** 1.5 / math.sqrt(2 * RHO * area)


def _endurance(d_in: int, n_p: int) -> tuple[float, float]:
    fm = sum(_p_ideal(t / 1000 * G, _area(d_in)) / p for t, p in TABLE[d_in]) / 3
    m_bat = 6 * n_p * 0.070 * 1.10
    m = (1.0 + 0.25 + 4 * (0.171 + 0.020 + 0.030) + m_bat) / (1 - 0.18)
    p = _p_ideal(m * G, 4 * _area(d_in)) / fm + 10
    return m, 6 * n_p * 16.2 * 0.85 * 0.8 / p * 60


def build(D: dict) -> None:
    ns = list(range(1, 9))
    e15 = [_endurance(15, n)[1] for n in ns]
    e17 = [_endurance(17, n)[1] for n in ns]
    D["chart-sizing-endurance"] = chart(
        "Время висения от числа параллелей 6S·nP (квадро, MN4014, 1 кг груза)",
        [dict(name="проп 17×5.8", xs=ns, ys=e17, cls="a", label_at=7, label_dy=-10),
         dict(name="", xs=ns, ys=e17, cls="a", dots=True),
         dict(name="проп 15×5", xs=ns, ys=e15, cls="w", label_at=7, label_dy=20),
         dict(name="", xs=ns, ys=e15, cls="w", dots=True)],
        Axis("параллелей P в сборке 6S·nP (масса 3.2 → 7.1 кг)", 1, 8, ticks=ns), Axis("время до резерва 20 %, мин", 10, 40),
        hmarks=[(25, "ТЗ: 25 мин", "d")],
        marks=[(3, "6S3P: 4.29 кг; 28.8 / 25.1 мин", "m", 150)],
        notes=[(430, 240, "6S4P → 6S8P: масса +2.3 кг,", "m"), (430, 254, "время +4.4 мин (17\")", "m")])

    D["sizing-config-tree"] = tree("Выбор схемы по ТЗ: висение, время, отказ мотора", Node("r", ["Нужно висеть", "над точкой?"], [
        ("нет", Node("wing", ["Самолёт:", "1–3 ч, P ≈ W·V/(L/D)"], leaf=True, accent=True)),
        ("взлёт без полосы", Node("vtol", ["VTOL:", "+20–30 % массы"], [
            ("", Node("vtol1", ["Время > 40 мин,", "висение < 10 %"], leaf=True))])),
        ("да, основная часть", Node("mr", ["Мультиротор:", "20–40 мин"], [
            ("дёшево", Node("quad", ["Квадро: проще,", "отказ = падение"], leaf=True)),
            ("груз дорогой", Node("hex", ["Гекса / окто:", "переживает отказ"], leaf=True, accent=True)),
            ("тесно", Node("coax", ["Соосная X8:", "−15 % тяги пары"], leaf=True)),
        ])),
    ]), width=720)
