"""Stage 6 diagrams for nav-rtk: moving-baseline yaw chain and fix type vs horizontal accuracy.

The chart uses the same generated 300 s rover log as the module's practice script (seed 7): 3D fix,
corrections arrive at t = 20 s, DGPS -> RTK float -> RTK fixed at t = 60 s, a 25 s NTRIP dropout
from t = 150 s (correction age grows to 26 s, fix degrades fixed -> float -> 3D), re-convergence.
hAcc per state: 3D 1.5 m, DGPS 0.6 m, float 0.25 m, fixed 0.014 m (ZED-F9P data sheet: 1.5 m CEP
standard, 0.01 m + 1 ppm RTK).
"""
from __future__ import annotations

import random

from plot import Axis, chart
from svg import Box, flow

HACC = {3: (1.5, 0.4), 4: (0.6, 0.15), 5: (0.25, 0.08), 6: (0.014, 0.003)}


def _rover_log(n: int = 300) -> list[tuple]:
    rnd = random.Random(7)
    rows, age, fix = [], 0.0, 3
    for t in range(n):
        if t < 20:
            fix, age = 3, 0.0
        elif t < 35:
            fix, age = 4, 1.0
        elif t < 60:
            fix, age = 5, 1.0
        elif t < 150:
            fix, age = 6, 1.0
        elif t < 175:
            age += 1.0
            fix = 6 if age < 10 else (5 if age < 20 else 3)
        elif t < 190:
            fix, age = 5, 1.0
        else:
            fix, age = 6, 1.0
        mu, sd = HACC[fix]
        rows.append((t, fix, max(0.005, rnd.gauss(mu, sd)), rnd.randint(18, 24), age))
    return rows


def build(D: dict) -> None:
    rows = _rover_log()
    series = []
    for fix, name, cls, at, dy in ((3, "3D: 1.4 м", "d", 1, -12), (4, "DGPS: 0.6 м", "w", 34, -14),
                                   (5, "RTK float: 0.25 м", "m", 59, -16), (6, "RTK fixed: 0.014 м", "a", 61, 26)):
        xs = [r[0] for r in rows if r[1] == fix]
        ys = [r[2] for r in rows if r[1] == fix]
        series.append(dict(name=name, xs=xs, ys=ys, cls=cls, dots=True, label_at=at, label_dy=dy, label_anchor="start"))
    D["chart-rtk-fix-hacc"] = chart(
        "Ровер F9P: hAcc по состояниям fix (сгенерированный лог, 300 с)",
        series,
        Axis("время, с", 0, 300, ticks=[0, 50, 100, 150, 200, 250, 300]),
        Axis("hAcc, м (лог. шкала)", 0.005, 3, log=True, ticks=[0.01, 0.1, 1]),
        bands=[(20, 60, "сходимость 40 с"), (150, 175, "обрыв NTRIP 25 с")],
        hmarks=[(0.05, "порог 5 см для посадки", "ink")],
        notes=[(455, 125, "возраст поправок > 10 с → float,", "m"), (455, 139, "> 20 с → 3D", "m")])

    D["rtk-mb-yaw-chain"] = flow(
        "Moving baseline в ArduPilot 4.6: от двух F9P до курса в EKF3",
        [Box("base", ["F9P база", "GPS1_TYPE = 17", "RTCM 4072.0 + MSM4"], 10, 30, 160, 54, accent=True),
         Box("rover", ["F9P ровер", "GPS2_TYPE = 18", "UBX-NAV-RELPOSNED"], 10, 140, 160, 54, accent=True),
         Box("drv", ["AP_GPS_UBLOX", "relPosHeading, Length", "carrSoln = fixed?"], 250, 30, 180, 54),
         Box("chk", ["Проверка базы", "L ≥ 5 см, fix = 6,", "|L − L_POS| ≤ 20 %"], 250, 140, 180, 54),
         Box("out", ["GPS2_RAW.yaw", "0 / 65535 / 1…36000", "лог GPS.Yaw, GPA.YAcc"], 250, 250, 180, 54),
         Box("ekf", ["EKF3", "EK3_SRC1_YAW = 2 / 3", "σ_yaw ≥ 5°, XKF3.IYAW"], 520, 140, 180, 54, accent=True)],
        [("base", "rover", "UART2→UART2, 1–5 Гц", True, "v"), ("rover", "drv", "UART1 → FC", False, "h"), ("drv", "chk", "", False, "v"),
         ("chk", "ekf", "yaw, σ_yaw", False, "h"), ("chk", "out", "", False, "v")],
        720, 360, notes=[(520, 60, "pos/vel в EKF3 — как обычно;", "m t"), (520, 74, "RTCM-поправки — est-gnss.", "m t"),
                         (10, 330, "Без 4072.0 ровер не входит в режим MB; без 1230 GLONASS остаётся float.", "m t"),
                         (10, 346, "Нарушено 20 % или нет RELPOSNED → yaw = 65535, EKF3 едет на гироскопе.", "m t")])
