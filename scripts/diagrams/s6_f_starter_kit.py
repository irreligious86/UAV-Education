"""Stage 6 diagrams for f-starter-kit: purchase order and minutes in the air per session.

Chart numbers come from the module's worked example: a 3.5" quad on 4S, average current 10 A
(the stated input of the exercise), 80 % of capacity used: t = 0.8 * Q / I per pack.
"""
from __future__ import annotations

from plot import Axis, chart
from svg import Box, flow

I_AVG = 10.0   # A, input of the worked example
USABLE = 0.8


def _pack_min(mah: float) -> float:
    return USABLE * mah / 1000 / I_AVG * 60


def build(D: dict) -> None:
    y, w, h = 56, 124, 48
    xs = [8, 152, 296, 440, 584]
    boxes = [
        Box("radio", ["1. Пульт EdgeTX", "+ ELRS 2.4 ГГц"], xs[0], y, w, h, accent=True, note="переживает всё"),
        Box("sim", ["2. Симулятор", "5–10 ч в акро"], xs[1], y, w, h, note="пульт по USB"),
        Box("video", ["3. Видеосистема", "и очки"], xs[2], y, w, h, accent=True, note="замок на экосистему"),
        Box("craft", ["4. Аппарат", "BNF под очки"], xs[3], y, w, h, note="расходник"),
        Box("power", ["5. АКБ, зарядка,", "инструмент"], xs[4], y, w, h, note="под класс аппарата"),
    ]
    links = [("radio", "sim"), ("sim", "video"), ("video", "craft", "", True), ("craft", "power")]
    D["starter-kit-order"] = flow(
        "Порядок покупок: от долгоживущего к расходному", boxes, links, 720, 170,
        notes=[(8, 150, "Очки выбирают раньше аппарата: VTX аппарата обязан совпасть с системой очков.", "m t")])

    ns = list(range(1, 9))
    t850 = [n * _pack_min(850) for n in ns]
    t650 = [n * _pack_min(650) for n in ns]
    D["chart-starter-kit-session"] = chart(
        "Минут в воздухе за выезд от числа АКБ (3.5\", 4S, средний ток 10 А, 80 % ёмкости)",
        [dict(name="4S 850 мА·ч: 4.1 мин на АКБ", xs=ns, ys=t850, cls="a", label_at=7, label_dy=-10),
         dict(name="", xs=ns, ys=t850, cls="a", dots=True),
         dict(name="4S 650 мА·ч: 3.1 мин на АКБ", xs=ns, ys=t650, cls="w", label_at=8, label_dy=18),
         dict(name="", xs=ns, ys=t650, cls="w", dots=True)],
        Axis("число АКБ в комплекте", 1, 8, ticks=ns), Axis("время в воздухе за выезд, мин", 0, 35),
        hmarks=[(15, "цель: 15 мин", "d")],
        marks=[(4, "4 АКБ: 16.3 / 12.5 мин", "m", 150)])
