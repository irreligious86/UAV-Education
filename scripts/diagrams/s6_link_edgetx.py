"""Stage 6 diagrams for module link-edgetx (EdgeTX 2.12.5: models, mixes, telemetry, modules).

edgetx-mixer-pipeline — sources -> Inputs -> Mixes -> Outputs -> RF module, with the numbers of the
                        module's worked example (roll stick +50 %, expo 40 -> 35.1 % -> 1679 us -> CRSF 1279).
chart-edgetx-expo     — the expo curve from radio/src/mixer.cpp, y = k*x^3 + (1 - k)*x, for k = 0, 40, 80 %,
                        with the worked-example point (50 % -> 35 %).
"""
from __future__ import annotations

from plot import Axis, chart
from svg import Box, flow


def _expo(x: float, k: float) -> float:
    return k * x ** 3 + (1 - k) * x


def build(D: dict) -> None:
    W, H, Y = 124, 62, 44
    xs = [10, 152, 294, 436, 578]
    boxes = [
        Box("src", ["Источники", "стики, тумблеры,", "крутилки, LS, GV"], xs[0], Y, W, H),
        Box("inp", ["INPUTS", "expo/кривая →", "вес → offset, трим"], xs[1], Y, W, H, accent=True),
        Box("mix", ["MIXES", "кривая → вес →", "offset; Add/Repl"], xs[2], Y, W, H, accent=True),
        Box("out", ["OUTPUTS", "subtrim, Min/Max,", "реверс, центр"], xs[3], Y, W, H, accent=True),
        Box("rf", ["RF-модуль", "CRSF: 16 каналов", "по 11 бит"], xs[4], Y, W, H),
        Box("n1", ["стик Ail +50 %", "512 из ±1024"], xs[0], 150, W, 44),
        Box("n2", ["expo 40, вес 100", "35.1 % (359)"], xs[1], 150, W, 44),
        Box("n3", ["CH1 = I1 · 100 %", "35.1 %"], xs[2], 150, W, 44),
        Box("n4", ["1500 + 359/2", "= 1679 мкс"], xs[3], 150, W, 44),
        Box("n5", ["992 + 359·4/5", "= CRSF 1279"], xs[4], 150, W, 44),
    ]
    links = [("src", "inp"), ("inp", "mix"), ("mix", "out"), ("out", "rf"),
             ("n1", "n2"), ("n2", "n3"), ("n3", "n4"), ("n4", "n5")]
    D["edgetx-mixer-pipeline"] = flow(
        "EdgeTX: путь сигнала от стика до модуля (и пример с числами)",
        boxes, links, 720, 250,
        notes=[(10, 136, "Пример модуля: крен +50 %, expo 40 на пульте", "m t"),
               (10, 218, "−100…+100 % = ±1024 внутри = 988…2012 мкс = CRSF 173…1811.", "m t"),
               (10, 234, "Для полётника expo и веса оставляют 0 и 100: рейты считает он сам.", "w t")])

    n = 101
    x = [i / (n - 1) * 100 for i in range(n)]
    series = [
        dict(name="expo 0", xs=x, ys=[_expo(v / 100, 0.0) * 100 for v in x], cls="ink", dash=True, label_at=38, label_dy=-12, label_anchor="end"),
        dict(name="expo 40", xs=x, ys=[_expo(v / 100, 0.4) * 100 for v in x], cls="a", label_at=76, label_dy=-10, label_anchor="end"),
        dict(name="expo 80", xs=x, ys=[_expo(v / 100, 0.8) * 100 for v in x], cls="w", label_at=86, label_dy=30, label_anchor="start"),
    ]
    D["chart-edgetx-expo"] = chart(
        "Expo в EdgeTX: y = k·x³ + (1 − k)·x",
        series,
        Axis("отклонение стика, %", 0, 100), Axis("выход Input, %", 0, 100),
        marks=[(50, "стик 50 %", "m")],
        hmarks=[(35, "expo 40 → 35 %", "a"), (20, "expo 80 → 20 %", "w")],
        notes=[(76, 56, "края не меняются: 100 % → 100 % при любом k", "m")])
