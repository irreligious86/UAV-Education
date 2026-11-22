"""Stage 6 (theory-first) diagrams for module ops-applications.

apps-selection-tree  — the module's class-selection rule (step 3): work time <= 40 min? -> (no) is hovering the
                       main work? / (yes) serious failure consequences? with the module's worked missions at the leaves.
chart-apps-spray-rate — application rate (L/ha) vs ground speed for the worked spraying example: ArduCopter 4.7.2
                       AC_Sprayer pump command = speed * SPRAY_PUMP_RATE (clamped to 100 %), linear pump 16 L/min at
                       100 %, swath 7 m. Default SPRAY_PUMP_RATE = 10 gives 38.1 L/ha and saturates at 10 m/s;
                       the recalculated 3.94 gives 15 L/ha up to 25.4 m/s.
"""
from __future__ import annotations

from plot import Axis, chart
from svg import Node, tree

Q_MAX, SWATH = 16.0, 7.0


def _rate(v: float, pump_rate: float) -> float:
    pct = min(100.0, v * pump_rate)
    q = pct / 100 * Q_MAX                 # L/min
    return q * 10000 / (SWATH * v * 60)   # L/ha


def build(D: dict) -> None:
    D["apps-selection-tree"] = tree("Правило выбора класса: работа → требования → класс", Node("time", ["Рабочее время", "t ≤ 40 мин?"], [
        ("нет", Node("hover", ["Висение — основная", "работа?"], [
            ("нет", Node("wing", ["VTOL / самолёт 1–3 ч:", "карта 120 га = 56 мин"], leaf=True, accent=True)),
            ("да", Node("sorties", ["Несколько вылетов", "мультиротора"], leaf=True)),
        ])),
        ("да", Node("risk", ["Над людьми, BVLOS", "или MTOW > 25 кг?"], [
            ("нет", Node("quad", ["Квадро: тепловизор,", "шоу (+RTK)"], leaf=True)),
            ("да", Node("hex", ["Гекса / окто: агро 92 кг,", "доставка BVLOS"], leaf=True, accent=True)),
        ])),
    ]), width=720, box_w=160)

    vs = [2 + 0.25 * i for i in range(49)]          # 2 … 14 m/s
    D["chart-apps-spray-rate"] = chart(
        "Норма внесения от скорости: AC_Sprayer, насос 16 л/мин, захват 7 м",
        [dict(name="SPRAY_PUMP_RATE = 10 (по умолчанию)", xs=vs, ys=[_rate(v, 10.0) for v in vs], cls="w",
              label_at=2.2, label_dy=-8, label_anchor="start"),
         dict(name="SPRAY_PUMP_RATE = 3.94 (пересчитан)", xs=vs, ys=[_rate(v, 3.9375) for v in vs], cls="a",
              label_at=2.2, label_dy=-8, label_anchor="start")],
        Axis("скорость галса, м/с", 2, 14, ticks=[2, 4, 6, 8, 10, 12, 14]), Axis("норма внесения, л/га", 0, 45),
        hmarks=[(15, "цель 15 л/га", "d")],
        marks=[(10, "насыщение при 10: 100 % хода", "m", 120), (6, "галс 6 м/с: 38.1 против 15 л/га", "m", 150)],
        notes=[(495, 176, "выше 10 м/с норма падает как 381/v", "m")])
