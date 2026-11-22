"""Stage 6 (theory-first) diagrams for module per-fpv-footage.

footage-gyroflow-paths — two recording paths into Gyroflow (docs.gyroflow.xyz, Gyroflow 1.7): camera gyro in the
                         video file (GoPro HERO8+, DJI, Insta360 — no sync needed) and Betaflight Blackbox
                         (250 Hz, uptilt in Motion data -> Rotation -> Pitch, sync needed); no gyro -> Optical
                         correction.
chart-footage-nd       — the module's worked example: ND stops needed vs scene EV (ISO 100, f/2.5) for 60 fps at
                         180 deg (1/120 s) and 90 deg (1/240 s). EV 15 -> 5.45 / 4.45 stops, EV 12 -> 2.45 / 1.45.
"""
from __future__ import annotations

import math

from plot import Axis, chart
from svg import Box, flow

F_NUMBER = 2.5


def _stops(ev: float, fps: float, angle: float) -> float:
    t = angle / 360 / fps
    t_free = F_NUMBER ** 2 / 2 ** ev
    return math.log2(t / t_free)


def build(D: dict) -> None:
    D["footage-gyroflow-paths"] = flow("Gyroflow: откуда берутся данные движения и что нужно для результата", [
        Box("cam", ["Камера с гироскопом", "GoPro 8+, DJI, Insta360"], 10, 40, 170, 48, accent=True),
        Box("mp4", ["MP4 + гиро в файле", "EIS выкл. (DJI)"], 215, 40, 150, 48),
        Box("fc", ["Полётник: Blackbox", "250 Гц, .bbl/.bfl"], 10, 130, 170, 48, accent=True),
        Box("bbl", ["Лог + видео без", "гиро; наклон камеры"], 215, 130, 150, 48),
        Box("nogyro", ["Нет гироскопа", "в кадре"], 10, 220, 170, 44),
        Box("opt", ["Optical correction", "движение по пикселям"], 215, 220, 150, 44),
        Box("gf", ["Gyroflow", "профиль линзы", "синхронизация", "сглаживание, RS"], 430, 40, 140, 224, accent=True),
        Box("out", ["Экспорт / плагин", "кроп по запасу"], 600, 130, 115, 44),
    ], [("cam", "mp4"), ("mp4", "gf", "без синхр."), ("fc", "bbl"), ("bbl", "gf", "синхр.", True),
        ("nogyro", "opt"), ("opt", "gf"), ("gf", "out")],
        720, 290, notes=[(10, 282, "Наклон камеры для лога FC: Motion data → Rotation → Pitch; ошибка в нём даёт уход горизонта", "m t")])

    evs = [9 + i * 0.05 for i in range(141)]
    s180 = [_stops(e, 60, 180) for e in evs]
    s90 = [_stops(e, 60, 90) for e in evs]
    D["chart-footage-nd"] = chart(
        "Сколько стопов ND нужно: 60 кадр/с, f/2.5, ISO 100",
        [dict(name="180° (1/120 с)", xs=evs, ys=s180, cls="a", label_at=12.6, label_dy=-12, label_anchor="end"),
         dict(name="90° (1/240 с, Gyroflow)", xs=evs, ys=s90, cls="d", dash=True, label_at=13.6, label_dy=20,
              label_anchor="start")],
        Axis("освещённость сцены, EV при ISO 100", 9, 16, ticks=[9, 10, 11, 12, 13, 14, 15, 16]),
        Axis("нужно стопов ND", -1, 7, ticks=[0, 1, 2, 3, 4, 5, 6, 7]),
        marks=[(12, "EV 12: 2.45 → ND8", "m", 262), (15, "EV15: 5.45→ND64", "m", 262)],
        hmarks=[(3, "ND8", "w"), (4, "ND16", "w"), (5, "ND32", "w"), (6, "ND64", "w")],
        notes=[(72, 84, "стопы = log2(t_нужн · 2^EV / N²);", "m"),
               (72, 98, "дробь — вверх до фильтра, остаток добирает ISO", "m")])
