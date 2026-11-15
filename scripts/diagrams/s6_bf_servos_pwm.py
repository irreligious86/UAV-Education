"""Stage 6 diagrams for module bf-servos-pwm (Betaflight 4.5 servos, PWM and timers).

bf-servo-timer-map          — SPEEDYBEEF405V4 (4.5-config) timer map from the module's lab run: TIM4/TIM3 locked by
                              DSHOT600 on M1–M4, TIM2 (M7 = SERVO 2) and TIM12 (S9 = SERVO 1, shared with CAMERA_CONTROL)
                              at 50 Hz, TIM8 (M5/M6) free but a bitbang pacer candidate, TIM1 LED_STRIP.
chart-bf-servo-tilt-pulse   — lab step 4: SERVO_TILT + CAMSTAB pulse vs pitch, rate 100 vs rate 56 for a servo with
                              90° over 1000 µs (pulse = 1500 + rate·pitch_decideg/50, clamped to 1000…2000).
"""
from __future__ import annotations

from plot import Axis, chart
from svg import Box, flow


def build(D: dict) -> None:
    w = 108
    xs = [8, 126, 244, 362, 480, 598]
    tims = [
        ("t4", ["TIM4", "DShot600", "PSC 6 · ARR 19"], True),
        ("t3", ["TIM3", "DShot600", "PSC 6 · ARR 19"], True),
        ("t2", ["TIM2", "серва 50 Гц", "PSC 83 · ARR 19999"], False),
        ("t12", ["TIM12", "серва 50 Гц", "PSC 83 · ARR 19999"], False),
        ("t8", ["TIM8", "свободен", "(пейсер bitbang)"], False),
        ("t1", ["TIM1", "LED_STRIP", "800 кГц + DMA"], False),
    ]
    pads = [
        ("p4", ["M1 B06 · CH1", "M2 B07 · CH2"]),
        ("p3", ["M3 B00 · CH3", "M4 B01 · CH4"]),
        ("p2", ["M7 B10 → SERVO 2", "M8 A15 · свободен"]),
        ("p12", ["S9 B15 → SERVO 1", "CAM B14 → NONE"]),
        ("p8", ["M5 C08 · M6 C09", "не трогать при bitbang"]),
        ("p1", ["LED A08 · CH1", "DMA opt 0"]),
    ]
    boxes = [Box(i, lab, x, 30, w, 58, accent=acc) for (i, lab, acc), x in zip(tims, xs)]
    boxes += [Box(i, lab, x, 140, w, 50) for (i, lab), x in zip(pads, xs)]
    links = [(t[0], p[0], "", t[2], "v") for t, p in zip(tims, pads)]
    D["bf-servo-timer-map"] = flow(
        "SpeedyBee F405 V4 (4.5): один таймер — одна база времени на все его каналы",
        boxes, links, 720, 270,
        notes=[(8, 222, "Моторы M1–M4 занимают TIM4 и TIM3 целиком: серву на их каналы ставить нельзя.", "w t"),
               (8, 238, "SERVO 1 на S9 делит TIM12 с CAMERA_CONTROL: камеру-джойстик освободить (resource CAMERA_CONTROL NONE).", "m t"),
               (8, 254, "SERVO 2 — на пад M7 (TIM2): ни мотор, ни DShot bitbang этот таймер не трогают.", "m t")])

    # lab step 4 (bf-servos-pwm.servo_lab.py, section 6)
    pitch = [-40, -30, -20, -10, 0, 10, 20, 30, 40]
    r100 = [1000, 1000, 1100, 1300, 1500, 1700, 1900, 2000, 2000]
    r56 = [1052, 1164, 1276, 1388, 1500, 1612, 1724, 1836, 1948]
    ideal = [1500 + p * 1000 / 90 for p in pitch]
    D["chart-bf-servo-tilt-pulse"] = chart(
        "SERVO_TILT + CAMSTAB: импульс сервы тангажа при наклоне рамы",
        [dict(name="rate 100", xs=pitch, ys=r100, cls="w", label_at=12, label_dy=-10),
         dict(name="rate 56", xs=pitch, ys=r56, cls="a", label_at=32, label_dy=16, label_anchor="start"),
         dict(xs=pitch, ys=ideal, cls="m", dash=True)],
        Axis("тангаж рамы, °", -40, 40, ticks=[-40, -30, -20, -10, 0, 10, 20, 30, 40]),
        Axis("импульс, мкс", 950, 2050, ticks=[1000, 1250, 1500, 1750, 2000]),
        hmarks=[(1000, "min 1000", "m"), (2000, "max 2000", "m")],
        legend=[("нужно: 90° на 1000 мкс", "m", True)], legend_at=(470, 280),
        notes=[(72, 60, "Прошивка добавляет rate/5 мкс на градус: rate 100 даёт 20 мкс/° и перекомпенсирует в 1.8 раза,", "m"),
               (72, 74, "упираясь в упоры уже на ±25°. rate = 5·(мкс/°) сервы = 56 даёт ошибку ≤ 0.3°.", "m")])
