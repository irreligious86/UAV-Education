"""Stage 6 diagrams for comp-jetson-nano: voltage at the Jetson power input vs current (micro-USB vs barrel),
and the sizing tree Pi 5 / Nano / Orin Nano.

Numbers come from the module's worked example (theory, «Питание: 5 В 4 А и ловушка micro-USB»):
U = U_BEC - I * (2 * L * r_AWG + R_conn); r: 28 AWG 0.213 Ω/m, 24 AWG 0.084 Ω/m, 20 AWG 0.033 Ω/m;
brown-out threshold 4.75 V (Jetson Nano Developer Kit User Guide, module data sheet VDD_IN 4.75-5.25 V); load points
from the tegrastats sample (2.9 W with a CSI camera running, 7.7 W TensorRT peak -> 0.58 A, 1.54 A at 5 V) and the
module's worked budget of 15 W with peripherals (3 A).
"""
from __future__ import annotations

from plot import Axis, chart
from svg import Node, tree


def _u(u_bec: float, r: float, xs: list[float]) -> list[float]:
    return [u_bec - i * r for i in xs]


def build(D: dict) -> None:
    xs = [i / 10 for i in range(0, 41)]
    r_usb_long = 2 * 1.0 * 0.213 + 0.10     # 1 m micro-USB, 28 AWG, + connector  = 0.526 Ω
    r_usb_short = 2 * 0.3 * 0.084 + 0.10    # 0.3 m "good" micro-USB, 24 AWG     = 0.150 Ω
    r_barrel = 2 * 0.3 * 0.033 + 0.03       # 0.3 m 20 AWG to the barrel jack      = 0.050 Ω
    D["chart-jetson-brownout"] = chart(
        "Напряжение на входе Jetson Nano: U = 5.0 В − I·R (кабель + разъём)",
        [dict(name="", xs=xs, ys=_u(5.0, r_usb_long, xs), cls="d"),
         dict(name="", xs=xs, ys=_u(5.0, r_usb_short, xs), cls="w", dash=True),
         dict(name="", xs=xs, ys=_u(5.0, r_barrel, xs), cls="a")],
        Axis("ток, А", 0, 4), Axis("U на плате, В", 2.8, 5.3),
        height=420, hmarks=[(4.75, "", "d")], notes=[(546, 125, "минимум 4.75 В", "d")],
        marks=[(0.58, "2.9 Вт: камера", "m"), (1.54, "7.7 Вт: TensorRT", "m"), (3.0, "15 Вт: с периферией", "m")],
        legend=[("micro-USB 1 м, 28 AWG: R = 0.53 Ом", "d", False),
                ("micro-USB 0.3 м, 24 AWG: R = 0.15 Ом", "w", True),
                ("barrel 0.3 м, 20 AWG: R = 0.05 Ом", "a", False)], legend_at=(80, 330))

    D["jetson-sizing-tree"] = tree("Какой companion: Pi 5, Jetson Nano или Orin Nano", Node("r", ["Что считаем", "на борту?"], [
        ("MAVLink + логика", Node("pi", ["Pi 5: 5 В 5 А,", "CPU-детектор ≤ 15 к/с"], leaf=True, accent=True)),
        ("1 сеть, 20 к/с", Node("nano", ["Jetson Nano: 10 Вт,", "JP4 EOL, NVENC есть"], leaf=True)),
        ("детектор + трекер", Node("orin", ["Orin Nano: 7–25 Вт,", "TRT INT8, без NVENC"], leaf=True, accent=True)),
        ("SLAM, 2+ сети", Node("nx", ["Orin NX / AGX:", "RAM 16 ГБ+, DLA"], leaf=True)),
    ]), width=760, box_w=164)
