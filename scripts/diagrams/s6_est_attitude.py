"""Diagrams for module est-attitude (thin-module pass, 2026-11).

chart-attitude-kp-sweep   practice step 2 of the module (att_lab.py, seed 1, 120 s flight): RMS tilt error over
                          the whole flight against the Mahony gain Kp, with the Betaflight-style accelerometer gate
                          0.9-1.1 g and without it (numbers copied from the pasted output). Marks: Kp = 0.2
                          (INAV ahrs_dcm_kp 2000, ArduPilot AHRS_RP_P) and 0.25 (Betaflight imu_dcm_kp 2500).
                          The left asymptote is the b/Kp steady error formula with b = 0.583 deg/s (dashed).
attitude-mahony-loop      the Mahony cycle as Betaflight 2025.12.5 runs it (flight/imu.c): gyro -> + Kp*e + Ki*int(e)
                          -> quaternion integration -> predicted "down"; accelerometer -> PT2 25 Hz (acc_lpf_hz)
                          -> gate 0.9 g < |a| < 1.1 g -> cross product e. Gains: 0.25 armed, x10 disarmed.
"""
from __future__ import annotations

import math

from plot import Axis, chart
from svg import Box, flow

KP = [0.02, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
RMS_GATE = [19.47, 10.51, 5.85, 2.84, 2.48, 3.30, 4.81, 5.65, 6.07]
RMS_NOGATE = [17.39, 8.94, 5.59, 6.93, 9.69, 11.60, 12.94, 13.41, 13.62]
B_XY = math.radians(math.hypot(0.5, 0.3))     # 0.583 deg/s in rad/s


def kp_sweep() -> str:
    xs = [10 ** (k / 20) for k in range(-34, 21)]          # 0.02 ... 10
    ss = [math.degrees(B_XY / x) for x in xs]              # steady error b/Kp, deg
    assert abs(math.degrees(B_XY / 0.25) - 2.33) < 0.01
    return chart(
        "Ошибка наклона за полёт против Kp фильтра Mahony",
        [dict(name="без защиты |a|", xs=KP, ys=RMS_NOGATE, cls="d", label_at=2.5, label_dy=-10),
         dict(name="окно 0.9–1.1 g", xs=KP, ys=RMS_GATE, cls="a", label_at=10, label_dy=-10),
         dict(name="b/Kp", xs=xs, ys=ss, cls="m", dash=True, label_at=0.035, label_dy=-6, label_anchor="start")],
        Axis("Kp (логарифмическая шкала)", 0.02, 10, log=True, ticks=[0.02, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]),
        Axis("RMS ошибки наклона, °", 0, 20, ticks=[0, 5, 10, 15, 20]),
        marks=[(0.2, "INAV, AP DCM: 0.2", "m", 54), (0.25, "Betaflight: 0.25", "a", 70)],
        notes=[(470, 60, "модель att_lab.py: bias 0.58 °/с,", "m"), (470, 76, "разгоны 4 м/с², вираж 30°", "m")])


def mahony_loop() -> str:
    boxes = [
        Box("gyro", ["Гироскоп ω", "рад/с, с bias"], 20, 40, 130),
        Box("sum", ["ω + Kp·e + Ki·∫e", "Kp 0.25 (×10 до арма)"], 200, 40, 170, accent=True),
        Box("int", ["q ← q ⊗ exp(ω'Δt/2)", "нормировать"], 420, 40, 170),
        Box("out", ["кватернион →", "углы, регулятор"], 600, 40, 110),
        Box("pred", ["v = Rᵀ(0,0,1)", "ожидаемый «низ»"], 420, 150, 170),
        Box("cross", ["e = (−a/|a|) × v"], 200, 150, 170, accent=True),
        Box("gate", ["0.9 g < |a| < 1.1 g?", "иначе e = 0"], 200, 250, 170),
        Box("lpf", ["PT2 25 Гц", "acc_lpf_hz"], 20, 250, 130),
        Box("acc", ["Акселерометр", "f = a − g"], 20, 150, 130),
    ]
    links = [("gyro", "sum"), ("sum", "int", "", True), ("int", "out"), ("int", "pred", "", False, "v"),
             ("pred", "cross"), ("acc", "lpf", "", False, "v"), ("lpf", "gate"), ("gate", "cross", "", False, "v"),
             ("cross", "sum", "", True, "v")]
    return flow("Цикл Mahony в Betaflight 2025.12.5 (flight/imu.c)", boxes, links, 720, 330,
                notes=[(410, 262, "Ki = 0 по умолчанию: bias не оценивается,", "m t"),
                       (410, 278, "его убирает калибровка гироскопа", "m t"),
                       (410, 294, "при включении; ошибка наклона e = b/Kp", "m t"),
                       (410, 316, "задача: 100 Гц в Acro, f_acc/2 в Angle", "m t")])


def build(D: dict) -> None:
    D["chart-attitude-kp-sweep"] = kp_sweep()
    D["attitude-mahony-loop"] = mahony_loop()
