"""Thin-module pass (stage 6) diagrams for module ap-companion.

chart-ap-guided-silence-stop  — ground speed of ArduCopter 4.7.2 SITL after the companion stops sending a 2 m/s
                                velocity target (5 Hz stream), measured in the module's lab (companion_lab.py via
                                MAVProxy --streamrate=-1, LOCAL_POSITION_NED 10 Hz). Speed stays 1.98-1.99 m/s up to
                                3.21 s, first drop at 3.31 s, < 0.2 m/s at 4.32 s. GUID_TIMEOUT = 3.0 s (ArduCopter/Parameters.cpp,
                                guided_timeout) is marked; the band is the braking phase.
guided-silence-tree           — what ArduCopter 4.7.2 GUIDED does when the companion goes silent, by the last target
                                type (mode_guided.cpp: pos_control_run, velaccel/accel_control_run,
                                posvelaccel_control_run, angle_control_run; get_timeout_ms() is used only for
                                velocity, acceleration, angle and rate targets), plus the pilot override.
"""
from __future__ import annotations

from plot import Axis, chart
from svg import Node, tree

# measured trace: seconds after the last setpoint, ground speed m/s (guided_timeout_trace.csv of the lab run)
TRACE = [(0.3, 1.99), (0.7, 1.99), (1.1, 1.99), (1.51, 1.99), (1.91, 1.98), (2.31, 1.98), (2.71, 1.98),
         (3.01, 1.99), (3.21, 1.98), (3.31, 1.96), (3.41, 1.89), (3.51, 1.76), (3.61, 1.57), (3.71, 1.33),
         (3.81, 1.05), (3.92, 0.79), (4.02, 0.57), (4.12, 0.39), (4.22, 0.27), (4.32, 0.18), (4.42, 0.12),
         (4.52, 0.08), (4.72, 0.04), (5.02, 0.02), (5.32, 0.02)]
GUID_TIMEOUT = 3.0


def silence_chart() -> str:
    xs, ys = [p[0] for p in TRACE], [p[1] for p in TRACE]
    return chart("После последней цели по скорости: SITL 4.7.2, 2 м/с, GUID_TIMEOUT = 3 с",
                 [dict(name="путевая скорость", xs=xs, ys=ys, cls="a", dots=True, label_at=2.0, label_dy=-10)],
                 Axis("время после последней цели SET_POSITION_TARGET, с", 0, 6),
                 Axis("скорость, м/с", 0, 2.4, fmt="{:.1f}"),
                 marks=[(GUID_TIMEOUT, "GUID_TIMEOUT 3.0 с", "w"), (4.32, "< 0.2 м/с: 4.3 с", "ink")],
                 bands=[(3.21, 4.32, "торможение")],
                 height=320)


def silence_tree() -> str:
    root = Node("root", ["GUIDED: companion", "замолчал"], [
        ("пилот сменил режим", Node("pilot", ["режим пилота;", "цели не нужны"], leaf=True)),
        ("цель — позиция", Node("pos", ["летит в точку", "и висит: таймаута нет"], accent=True, leaf=True)),
        ("скорость / ускорение", Node("vel", ["через GUID_TIMEOUT", "скорость → 0, висит"], leaf=True)),
        ("углы / тяга", Node("ang", ["через GUID_TIMEOUT", "горизонт, верт. 0"], leaf=True)),
    ])
    return tree("Что делает ArduCopter 4.7.2, если цели перестали приходить", root, box_w=160, gap_y=80)


def build(D: dict) -> None:
    D["chart-ap-guided-silence-stop"] = silence_chart()
    D["guided-silence-tree"] = silence_tree()
