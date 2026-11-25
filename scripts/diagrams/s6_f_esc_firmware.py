"""Stage 6 diagram for module f-esc-firmware (temperature protection, from firmware source).

chart-esc-temp-derate — maximum power the ESC allows vs its own temperature, both with the protection limit
                        set to 100 °C:
                        * Bluejay 0.21 (Modules/Scheduler.asm, scheduler_steps_even): below the limit setpoint
                          255/255; at the limit 200, then 150, 100, 50 every TEMP_LIMIT_STEP/2 = 4 ADC counts
                          (TEMP_LIMIT_STEP = 9 counts per 10 °C, Layouts/Base.inc) — steps at +0, +4.4, +8.9,
                          +13.3 °C; Pwm_Limit then walks to the setpoint one unit per ~256 ms (chart = setpoint).
                        * AM32 2.22 (Src/main.c:2412-2414): above the limit
                          duty_max = map(T, L − 10, L + 10, 2000/2, 1) out of 2000, with map() from
                          Src/functions.c (clamped, bisection) ported below.
"""
from __future__ import annotations

import math

from plot import Axis, chart

LIMIT = 100          # °C, the module's example (Bluejay option 3 = 100 °C; AM32 TEMPERATURE_LIMIT 100)
ADC_PER_C = 9 / 10   # Bluejay: TEMP_LIMIT_STEP = 9 ADC counts per 10 °C


def am32_map(x: int, in_min: int, in_max: int, out_min: int, out_max: int) -> int:
    """Port of map() from AM32 Src/functions.c (integer, clamped, recursive bisection)."""
    if x >= in_max:
        return out_max
    if x <= in_min:
        return out_min
    if in_min > in_max:
        return am32_map(x, in_max, in_min, out_max, out_min)
    if out_min == out_max:
        return out_min
    in_mid = (in_min + in_max) >> 1
    out_mid = (out_min + out_max) >> 1
    if in_min == in_mid:
        return out_mid
    if x <= in_mid:
        return am32_map(x, in_min, in_mid, out_min, out_mid)
    return am32_map(x, in_mid + 1, in_max, out_mid, out_max)


def am32_pct(t: int, limit: int = LIMIT) -> float:
    if t > limit:                                   # degrees_celsius > limits.temperature
        return am32_map(t, limit - 10, limit + 10, 2000 // 2, 1) / 2000 * 100
    return 100.0


def bluejay_pct(t: float, limit: int = LIMIT) -> float:
    a = math.floor((t - limit) * ADC_PER_C + 1e-9)                # ADC counts above the limit
    if a < 0:
        return 255 / 255 * 100
    setpoint = 200
    for nxt in (150, 100, 50):
        a -= 9 // 2
        if a < 0:
            break
        setpoint = nxt
    return setpoint / 255 * 100


def build(D: dict) -> None:
    ts = [85 + i * 0.1 for i in range(0, 351)]                       # 85…120 °C
    bj = [bluejay_pct(t) for t in ts]
    am_t = ts
    am = [am32_pct(math.floor(t + 1e-9)) for t in ts]              # the ESC reads whole degrees
    D["chart-esc-temp-derate"] = chart(
        "Предел заполнения ШИМ при перегреве ESC (порог 100 °C, уставка)",
        [dict(name="Bluejay: ступени 78 → 59 → 39 → 20 %", xs=ts, ys=bj, cls="a",
              label_at=101, label_dy=-8, label_anchor="start"),
         dict(name="AM32: сразу 25 %, к +10 °C — ноль", xs=am_t, ys=am, cls="d",
              label_at=102, label_dy=-8, label_anchor="start")],
        Axis("температура ESC, °C", 85, 120, ticks=[85, 90, 95, 100, 105, 110, 115, 120]),
        Axis("предел заполнения ШИМ, %", 0, 110, ticks=[0, 20, 40, 60, 80, 100]),
        marks=[(100, "порог", "m", 20)],
        notes=[(92, 160, "Bluejay идёт к уставке медленно:", "m"), (92, 176, "≈14 с до 78 %, ≈52 с до 20 %", "m")])
