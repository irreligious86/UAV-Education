"""Stage 6 (theory-first) diagrams for module ops-pilot-training.

chart-pilot-training-rates — the module's worked example: Betaflight Actual rates (applyActualRates, fc/rc.c,
                             2025.12) for the default 7/67/0, the training profile 15/60/40 read in the practice
                             and a freestyle profile 18/85/55. At half stick: 185 / 145 / 171 deg/s.
pilot-training-ladder      — the four stages of the module's training plan with the gate that opens the next one.
"""
from __future__ import annotations

from plot import Axis, chart
from svg import Box, flow


def _actual(x, rc_rate, srate, expo):        # applyActualRates
    a = abs(x)
    e = expo / 100
    c = rc_rate * 10.0
    return x * c + max(0.0, srate * 10.0 - c) * a * (x ** 5 * e + x * (1 - e))


def build(D: dict) -> None:
    xs = [i / 100 for i in range(101)]
    series = [
        dict(name="по умолчанию 7/67/0", xs=xs, ys=[_actual(x, 7, 67, 0) for x in xs], cls="w",
             label_at=0.80, label_dy=-14, label_anchor="end"),
        dict(name="учебный 15/60/40", xs=xs, ys=[_actual(x, 15, 60, 40) for x in xs], cls="a",
             label_at=0.80, label_dy=24, label_anchor="start"),
        dict(name="фристайл 18/85/55", xs=xs, ys=[_actual(x, 18, 85, 55) for x in xs], cls="d", dash=True,
             label_at=0.95, label_dy=-10, label_anchor="end"),
    ]
    D["chart-pilot-training-rates"] = chart(
        "Actual rates: что получает PID при одном и том же движении стика",
        series, Axis("отклонение стика x", 0, 1, ticks=[0, 0.25, 0.5, 0.75, 1.0]),
        Axis("setpoint, °/с", 0, 900, ticks=[0, 150, 300, 450, 600, 750, 900]),
        marks=[(0.5, "x = 0.5: 185 / 145 / 171 °/с", "m")],
        notes=[(72, 84, "rc_rate / srate / expo;", "m"), (72, 98, "центр = rc_rate·10, максимум = srate·10", "m")])

    D["pilot-training-ladder"] = flow("План обучения: четыре ступени и ворота между ними", [
        Box("sim", ["1. Симулятор", "акро, свой пульт"], 10, 40, 150, 48, accent=True),
        Box("whoop", ["2. Вуп дома", "65–75 мм, 1S"], 195, 40, 150, 48),
        Box("field", ["3. Поле", "LOS, затем FPV"], 380, 40, 150, 48),
        Box("hundred", ["4. До 100 АКБ", "журнал, упражнения"], 565, 40, 150, 48, accent=True),
        Box("g1", ["5 кругов «восьмёрки»", "без сброса"], 100, 130, 160, 44),
        Box("g2", ["3 АКБ подряд", "без касаний стен"], 285, 130, 160, 44),
        Box("g3", ["10 АКБ: взлёт–круг–", "посадка в круг 2 м"], 470, 130, 160, 44),
    ], [("sim", "whoop"), ("whoop", "field"), ("field", "hundred", "", True),
        ("g1", "sim", "", False, "v"), ("g2", "whoop", "", False, "v"), ("g3", "field", "", False, "v")],
        720, 210, notes=[(10, 198, "Ворота — проверяемый навык, а не число часов: часы только оценка времени", "m t")])
