"""Stage 6 diagrams for px4-camera-gimbal (PX4 v1.17.0).

px4-gimbal-flow            — command sources -> gimbal module (input selected by MNT_MODE_IN, gimbal
                             manager, angle math) -> output selected by MNT_MODE_OUT. Mirrors
                             src/modules/gimbal/gimbal.cpp (input/output objects), output.cpp and
                             output_rc.cpp (limits, offsets, stabilisation only for AUX and MAVLink v1).
chart-px4-trigger-interval — time between frames T = F * (1 - p) / v for the module's worked example
                             (frame footprint along track F = 90 m) and three forward overlaps, with the
                             camera cycle time 1.2 s and TRIG_MIN_INTERVA 1.0 s of the exercise.
"""
from __future__ import annotations

from plot import Axis, chart
from svg import Box, flow

FOOTPRINT_M = 90.0          # practice step 2
CAMERA_CYCLE_S = 1.2        # practice step 2
MIN_INTERVAL_S = 1.0        # TRIG_MIN_INTERVA = 1000 ms, practice step 2


def interval(v: float, overlap: float, footprint: float = FOOTPRINT_M) -> float:
    """Seconds between frames: TRIG_DISTANCE / ground speed."""
    return footprint * (1.0 - overlap) / v


def build(D: dict) -> None:
    w, h = 150, 46
    x0, x1, x2, x3 = 12, 190, 378, 558
    ya, yb, yc = 40, 128, 216
    boxes = [
        Box("rc", ["Пульт: RC_MAP_AUXn", "→ MNT_MAN_*"], x0, ya, w, h, note="угол или скорость"),
        Box("gcs", ["Наземка, companion:", "GIMBAL_MANAGER_*"], x0, yb + 5, w, h, note="нужен primary control"),
        Box("mis", ["Миссия: ROI,", "DO_GIMBAL_MANAGER_*"], x0, yc + 5, w, h, note="через navigator"),
        Box("in", ["Вход: MNT_MODE_IN", "0 оба · 1 пульт · 4 v2"], x1, ya, 160, h, accent=True),
        Box("mgr", ["Gimbal manager:", "кто управляет,", "ROI → углы"], x1, yb, 160, 56, accent=True),
        Box("calc", ["Только AUX и v1:", "DO_STAB, ±RANGE/2,", "LND_P, OFF"], x2, yb, 160, 56),
        Box("aux", ["MNT_MODE_OUT 0:", "функции 420–422"], x3, ya, w, h, note="mixer: MIN…MAX, мкс"),
        Box("v1", ["MNT_MODE_OUT 1:", "DO_MOUNT_CONTROL"], x3, yb + 5, w, h, note="MNT_MAV_SYSID/COMPID"),
        Box("v2", ["MNT_MODE_OUT 2:", "GIMBAL_DEVICE_", "SET_ATTITUDE"], x2, yc, 160, 56, accent=True,
            note="кватернион как есть"),
        Box("dev", ["Подвес v2 device:", "свои пределы", "и стабилизация"], x3, yc, w, 56),
    ]
    links = [
        ("rc", "in"), ("gcs", "mgr"), ("mis", "mgr", "", False, "h"), ("in", "mgr", "", False, "v"),
        ("mgr", "calc"), ("calc", "aux", "", False, "h"), ("calc", "v1"),
        ("mgr", "v2", "", True, "h"), ("v2", "dev", "", True),
    ]
    D["px4-gimbal-flow"] = flow(
        "PX4 1.17: от источника команды до подвеса", boxes, links, 720, 330,
        notes=[
            (12, 308, "MNT_MODE_IN = −1 (по умолчанию): модуль gimbal не запущен. Смена MODE_IN / MODE_OUT — с перезагрузкой.", "m t"),
            (12, 323, "Выход v2: MNT_RANGE, MNT_OFF, MNT_DO_STAB не действуют; адрес — из GIMBAL_DEVICE_INFORMATION.", "m t"),
        ])

    vs = [4 + i * 0.1 for i in range(0, 181)]          # 4…22 m/s
    s70 = [interval(v, 0.70) for v in vs]
    s80 = [interval(v, 0.80) for v in vs]
    s85 = [interval(v, 0.85) for v in vs]
    D["chart-px4-trigger-interval"] = chart(
        "Интервал между кадрами: кадр 90 м вдоль галса, T = F·(1 − p) / v",
        [dict(xs=vs, ys=s70, cls="ink"), dict(xs=vs, ys=s80, cls="a"), dict(xs=vs, ys=s85, cls="w", dash=True)],
        Axis("путевая скорость, м/с", 4, 22), Axis("интервал между кадрами, с", 0, 5),
        marks=[(12, "12 м/с → 1.5 с", "m", 122), (15, "предел при 80 %: 15 м/с", "m", 152)],
        hmarks=[(CAMERA_CYCLE_S, "", "d"), (MIN_INTERVAL_S, "", "m")],
        legend=[("перекрытие 70 %, шаг 27 м", "ink", False), ("перекрытие 80 %, шаг 18 м", "a", False),
                ("перекрытие 85 %, шаг 13.5 м", "w", True)],
        legend_at=(440, 62),
        notes=[(70, 241, "цикл камеры 1.2 с", "d"),
               (70, 272, "TRIG_MIN_INTERVA 1.0 с", "m")])
