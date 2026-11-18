"""Stage 6 diagrams for module inav-mixer-vtol (INAV mixer, outputs and VTOL profiles).

inav-mixer-signal-path          — stabilised axes / RC / other sources -> mmix, smix -> servo params -> timers -> outputs.
inav-vtol-transition-timeline   — the module's 4+1 worked example: profile 2 (hover) -> 4.0 s transition
                                  (mixer_switch_trans_timer = 40, mmix 4 -1.300 -> 1300 us) -> profile 1 (airplane).
"""
from __future__ import annotations

from svg import Box, flow, timeline


def build(D: dict) -> None:
    W, H = 150, 48
    boxes = [
        Box("pid", ["PID: axisPID", "крен/танг./рыск. ±500"], 10, 40, W, H, accent=True),
        Box("thr", ["Газ", "1000…2000"], 10, 112, W, H),
        Box("src", ["RC, GVAR, MAX, flaps,", "CAMSTAB, вход 38"], 10, 204, W, H),
        Box("mmix", ["mmix: до 12 строк", "throttle R P Y"], 196, 76, W, H, accent=True),
        Box("smix", ["smix: до 36 правил", "вход×вес, speed, lc"], 196, 204, W, H, accent=True),
        Box("mlim", ["Ограничение", "idle 1080…2000"], 382, 76, W, H),
        Box("servo", ["servo: rate,", "min / mid / max"], 382, 176, W, H),
        Box("lpf", ["servo_lpf_hz", "20 Гц"], 382, 248, W, H),
        Box("tm", ["Таймеры MOTORS", "DShot / OneShot"], 560, 76, W, H),
        Box("ts", ["Таймеры SERVOS", "servo_pwm_rate 50 Гц"], 560, 212, W, H),
    ]
    links = [
        ("pid", "mmix", "", True, "h"),
        ("thr", "mmix", "", False, "h"),
        ("pid", "smix", "", False, "auto"),
        ("src", "smix", "", False, "h"),
        ("mmix", "mlim", "", True, "h"),
        ("smix", "servo", "сумма", False, "h"),
        ("servo", "lpf", "", False, "v"),
        ("mlim", "tm", "", True, "h"),
        ("lpf", "ts", "", False, "h"),
    ]
    D["inav-mixer-signal-path"] = flow(
        "Путь сигнала: PID → mmix / smix → таймеры → выходы S",
        boxes, links, 720, 340,
        notes=[(10, 316, "Один таймер — одна функция: timer_output_mode AUTO | MOTORS | SERVOS | LED.", "m t"),
               (10, 331, "Таблицы mmix и smix свои в каждом из двух профилей миксера; servo и таймеры — общие.", "w t")])

    # worked example of the module: hover 0-3 s, transition 3-7 s (timer 40 ds = 4.0 s), airplane after 7 s (axis 0-10 s)
    D["inav-vtol-transition-timeline"] = timeline(
        "VTOL 4+1: висение → переход 4.0 с → самолёт",
        [
            ("тумблер", [(0, 3, "MC"), (3, 7, "MC + TRANSITION", True), (7, 10, "FW")]),
            ("профиль миксера", [(0, 3, "2: MULTIROTOR"), (3, 7, "2: MULTIROTOR"), (7, 10, "1: AIRPLANE", True)]),
            ("вход 38 smix", [(0, 3, "0"), (3, 7, "500", True), (7, 10, "0")]),
            ("моторы 0–3", [(0, 3, "газ + стабилиз."), (3, 7, "газ + стабилизация"), (7, 10, "стоп (−1.000)")]),
            ("мотор 4", [(0, 3, "стоп"), (3, 7, "1300 мкс", True), (7, 10, "газ со стика")]),
            ("control-профиль", [(0, 3, "2: PID коптера"), (3, 7, "2: PID коптера"), (7, 10, "1: PID крыла", True)]),
        ],
        t_max=10, unit="с",
        marks=[(3, "MIXER TRANSITION"), (7, "смена профиля")])
