"""Stage 6 diagrams for module inav-mc-tuning (INAV 9.1.0 multirotor tuning).

inav-mc-filter-chain  — gyro filters in the order the code applies them (sensors/gyro.c gyroUpdate/gyroFilter,
                        flight/pid.c pidController), with the 9.1.0 defaults from settings.yaml.
inav-mc-nav-cascade   — position -> velocity -> angle -> rate cascade and the altitude branch, with the physical
                        gains computed in the module from the default integers (65/100, 40/20, 20/6.56, 50/100, 100/66.7).
"""
from __future__ import annotations

from svg import Box, flow


def build(D: dict) -> None:
    W, H = 160, 48
    boxes = [
        Box("gyro", ["Гироскоп", "задача 4 кГц"], 10, 40, W, H),
        Box("aa", ["Anti-alias PT1", "250 Гц"], 190, 40, W, H),
        Box("rpm", ["RPM-notch: выкл.", "уже в PID-задаче"], 370, 40, W, H),
        Box("lpf", ["Main LPF PT1", "60 Гц"], 550, 40, W, H, accent=True),
        Box("dyn", ["Dynamic notch", "3 пика, Q 1.2"], 550, 132, W, H, accent=True),
        Box("dyn3", ["3D-notch: выкл.", "1 пик, Q 2.0"], 370, 132, W, H),
        Box("kal", ["Kalman по setpoint", "q = 100"], 190, 132, W, H, accent=True),
        Box("smith", ["Smith predictor", "выкл. (delay 0)"], 10, 132, W, H),
        Box("pi", ["P, I и CD", "ошибка и setpoint"], 10, 224, W, H),
        Box("dlpf", ["D-term LPF PT2", "110 Гц → D"], 190, 224, W, H, accent=True),
        Box("sum", ["Сумма ±500", "(рыскание ±400)"], 370, 224, W, H),
        Box("mix", ["Миксер", "mmix → моторы"], 550, 224, W, H),
    ]
    links = [
        ("gyro", "aa", "", False, "h"),
        ("aa", "rpm", "", False, "h"),
        ("rpm", "lpf", "", False, "h"),
        ("lpf", "dyn", "", True, "v"),
        ("dyn", "dyn3", "", False, "h"),
        ("dyn3", "kal", "", False, "h"),
        ("kal", "smith", "", False, "h"),
        ("smith", "pi", "", False, "v"),
        ("pi", "dlpf", "", False, "h"),
        ("dlpf", "sum", "", False, "h"),
        ("sum", "mix", "", False, "h"),
    ]
    D["inav-mc-filter-chain"] = flow(
        "INAV 9.1: фильтры гироскопа в порядке применения (умолчания)",
        boxes, links, 720, 318,
        notes=[(10, 294, "Только anti-alias работает на частоте гироскопа; остальное — в PID-задаче (looptime 500 мкс).", "m t"),
               (10, 309, "Выделены звенья, включённые по умолчанию после anti-alias. Между RPM и Main LPF — LULU (выкл.).", "w t")])

    boxes = [
        Box("tp", ["Цель позиции", "navTgtPos[0,1]"], 10, 40, W, H),
        Box("pxy", ["Pos XY: P → см/с", "65 → 0.65 1/с"], 190, 40, W, H, accent=True),
        Box("vxy", ["Vel XY: PID + FF", "40 → 2.0 1/с → см/с²"], 370, 40, W, H, accent=True),
        Box("ang", ["Ускорение → угол", "≤ nav_mc_bank_angle"], 550, 40, W, H),
        Box("lvl", ["ANGLE: P", "20 → 3.05 1/с"], 550, 132, W, H, accent=True),
        Box("rate", ["Rate PID", "40 → 1.29 ед./(°/с)"], 280, 132, W, H, accent=True),
        Box("mix", ["Миксер", "axisPID + газ"], 10, 132, W, H),
        Box("tz", ["Цель высоты", "navTgtPos[2]"], 550, 224, W, H),
        Box("pz", ["Pos Z: sqrt-P → см/с", "50 → 0.5 1/с"], 370, 224, W, H, accent=True),
        Box("vz", ["Vel Z: PID → мкс", "hover_thr + поправка"], 190, 224, W, H, accent=True),
    ]
    links = [
        ("tp", "pxy", "", False, "h"),
        ("pxy", "vxy", "", False, "h"),
        ("vxy", "ang", "", False, "h"),
        ("ang", "lvl", "угол", True, "v"),
        ("lvl", "rate", "°/с", True, "h"),
        ("rate", "mix", "±500", True, "h"),
        ("tz", "pz", "", False, "h"),
        ("pz", "vz", "", False, "h"),
        ("vz", "mix", "", False, "h"),
    ]
    D["inav-mc-nav-cascade"] = flow(
        "INAV 9.1: каскад навигации и стабилизации мультиротора (умолчания)",
        boxes, links, 720, 318,
        notes=[(10, 294, "Обратная связь внешних контуров — оценщик позиции (navPos, navVel), внутренних — гироскоп и attitude.", "m t"),
               (10, 309, "Настраивают изнутри наружу: rate → ANGLE → Vel Z / Pos Z → Vel XY / Pos XY.", "w t")])
