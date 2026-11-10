"""Stage 6: ctl-allocation (mixer and control allocation).

Numbers come from the module's worked example (PX4 effectiveness formula, x500 geometry:
arm r = 0.246 m, |KM| = 0.05; tangential motor tilt).
"""
from __future__ import annotations

import math

from plot import Axis, chart
from svg import Box, flow


def build(D: dict) -> None:
    # ------------------------------------------------------------ allocation pipeline (PX4 names)
    D["alloc-pipeline"] = flow(
        "Распределение управления в PX4: от моментов к моторам",
        [Box("rate", ["mc_rate_control", "моменты + тяга"], 10, 30, 140, accent=True),
         Box("geo", ["Матрица B", "CA_ROTORn_P*, A*,", "CT, KM"], 190, 120, 150, 60),
         Box("pinv", ["Псевдообратная", "M = pinv(B),", "нормировка"], 190, 20, 150, 60, accent=True),
         Box("desat", ["Десатурация", "CA_METHOD,", "MC_AIRMODE"], 390, 20, 150, 60, accent=True),
         Box("mot", ["actuator_motors", "0…1 на мотор"], 575, 30, 135),
         Box("fd", ["Отказ мотора", "CA_FAILURE_MODE"], 390, 130, 150),
         Box("out", ["PWM_MAIN_FUNCn", "DShot/PWM → ESC"], 575, 130, 135)],
        [("rate", "pinv", "τ, F"), ("geo", "pinv", "", False, "v"), ("pinv", "desat", "M·sp"),
         ("desat", "mot", "", True), ("fd", "geo", "−столбец"), ("mot", "out", "", False, "v")],
        720, 240,
        notes=[(10, 206, "Приоритет: тяга и крен/тангаж держатся,", "m t"),
               (10, 220, "рыскание отдаётся первым (запас 15 %)", "m t")])

    # ------------------------------------------------------------ tilted motors: yaw authority vs thrust
    r, km = 0.174 * math.sqrt(2), 0.05
    th = [i * 0.1 for i in range(201)]                      # 0 … 20 deg
    yaw = [(r * math.sin(math.radians(t)) + km * math.cos(math.radians(t))) / km for t in th]
    fz = [100 * math.cos(math.radians(t)) for t in th]
    D["chart-alloc-tilt"] = chart(
        "Наклон моторов по касательной (x500: r = 0.246 м, KM = 0.05)",
        [dict(name="рыскание, ×", xs=th, ys=yaw, cls="a", label_at=12, label_dy=-10),
         dict(name="тяга Fz, %", xs=th, ys=fz, cls="w", axis=2, label_at=18, label_dy=20)],
        Axis("наклон оси мотора, °", 0, 20), Axis("момент рыскания, × от вертикали", 1, 3),
        Axis("вертикальная тяга, %", 90, 100),
        marks=[(5, "5°: ×1.43, −0.4 %", "m", 44), (10, "10°: ×1.84, −1.5 %", "m", 28)],
        notes=[(80, 300, "Рыскание = CT·(r·sinθ + KM·cosθ), тяга = CT·cosθ", "m")])
