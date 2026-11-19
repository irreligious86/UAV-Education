"""Stage 6 diagrams for module ap-aux-tune (ArduPilot 4.7.2: RCx_OPTION aux functions and the Copter TUNE knob).

ap-aux-eval-flow        — how an aux channel is evaluated: validity limits, LOW/MIDDLE/HIGH thresholds, change
                          detection, 200 ms debounce, function call + AUXF log; boot behaviour in the notes.
                          Numbers from libraries/RC_Channel/RC_Channel.h (RC_MIN_LIMIT_PWM 800, RC_MAX_LIMIT_PWM 2200,
                          AUX_SWITCH_PWM_TRIGGER_LOW 1200 / HIGH 1800) and RC_Channel.cpp (SWITCH_DEBOUNCE_TIME_MS 200,
                          read_aux, debounce_completed, init_position_on_first_radio_read) of Copter-4.7.2.
chart-ap-aux-tune-knob  — knob PWM -> tuned value for the module's worked example (practice step 2):
                          RC6_MIN 1100, RC6_MAX 1900, TUNE_MIN 0.05, TUNE_MAX 0.25, stored ATC_RAT_RLL_P 0.135.
                          Formula: RC_Channel::norm_input_ignore_trim + linear_interpolate (ArduCopter/tuning.cpp).
"""
from __future__ import annotations

from plot import Axis, chart
from svg import Box, flow

RC_MIN, RC_MAX = 1100, 1900
TUNE_MIN, TUNE_MAX = 0.05, 0.25
STORED = 0.135


def knob_value(pwm: float, rc_min: float = RC_MIN, rc_max: float = RC_MAX, tmin: float = TUNE_MIN, tmax: float = TUNE_MAX) -> float:
    """Copter::tuning(): n = clamp(2*((pwm-min)/(max-min)-0.5), -1, 1); value = lerp(tmin, tmax, n, -1, 1)."""
    n = max(-1.0, min(1.0, 2.0 * ((pwm - rc_min) / (rc_max - rc_min) - 0.5)))
    return tmin + (tmax - tmin) * (n + 1) / 2


def pwm_for(value: float) -> float:
    return RC_MIN + (value - TUNE_MIN) / (TUNE_MAX - TUNE_MIN) * (RC_MAX - RC_MIN)


def build(D: dict) -> None:
    boxes = [
        Box("pwm", ["Канал n", "опрос 10 Гц"], 14, 40, 112, 48, note="RCn_OPTION ≠ 0"),
        Box("valid", ["Импульс годен?", "800 < PWM < 2200"], 150, 40, 124, 48, accent=True, note="иначе пропуск"),
        Box("pos", ["Положение", "LOW / MID / HIGH"], 298, 40, 124, 48, note="< 1200 · > 1800 мкс"),
        Box("deb", ["Изменилось?", "держится 200 мс"], 446, 40, 124, 48, accent=True, note="иначе отсчёт заново"),
        Box("run", ["Функция", "+ запись AUXF"], 594, 40, 112, 48, note="один вызов"),
    ]
    links = [("pwm", "valid", "", False, "h"), ("valid", "pos", "", True, "h"), ("pos", "deb", "", False, "h"), ("deb", "run", "", True, "h")]
    D["ap-aux-eval-flow"] = flow(
        "ArduPilot 4.7.2: от импульса канала до вызова aux-функции",
        boxes, links, 720, 214,
        notes=[(14, 128, "Гистерезиса нет: 1200…1800 мкс включительно — MIDDLE. От щелчка до вызова 200–300 мс.", "a t"),
               (14, 144, "Разворот тумблера: RCn_REVERSED = 1 и бит 7 (128) в RC_OPTIONS — оба сразу.", "m t"),
               (14, 160, "Первый кадр приёмника: запомненное положение равно −1, поэтому текущее исполняется через 200 мс.", "m t"),
               (14, 176, "Исключения: 153, 154, 165 (арм) и 22 (парашют) первое положение только запоминают.", "w t"),
               (14, 192, "При failsafe по радио Copter aux-каналы не читает; режимный канал читается так же, но с шестью позициями.", "m t"),
               (14, 208, "Опасные в полёте: 31 и 165 LOW — стоп моторов; 81 HIGH и 153 LOW — дизарм без проверки высоты.", "d t")])

    xs = list(range(950, 2051, 10))
    ys = [knob_value(p) for p in xs]
    pts = [1000, 1500, 1750, 2000]
    home = pwm_for(STORED)
    assert abs(home - 1440) < 1e-6 and abs(knob_value(1750) - 0.2125) < 1e-9 and abs(knob_value(1000) - 0.05) < 1e-9
    D["chart-ap-aux-tune-knob"] = chart(
        "Copter TUNE = 4: значение ATC_RAT_RLL_P от положения крутилки (RC6 1100…1900, TUNE 0.05…0.25)",
        [dict(name="значение от крутилки", xs=xs, ys=ys, cls="a", label_at=1640, label_dy=-10),
         dict(name="", xs=pts, ys=[knob_value(p) for p in pts], cls="ink", dots=True)],
        x=Axis("положение крутилки, мкс", 950, 2050, ticks=[1000, 1100, 1300, 1440, 1500, 1750, 1900, 2000]),
        y=Axis("ATC_RAT_RLL_P", 0, 0.3, ticks=[0, 0.05, 0.1, 0.135, 0.15, 0.2125, 0.25, 0.3]),
        marks=[(1000, "ловушка: 0.05", "d", 150), (home, "1440 мкс: 0.135", "w", 60)],
        hmarks=[(STORED, "сохранено в памяти: 0.135", "w")],
        notes=[(300, 281, "1000 → 0.05 · 1500 → 0.15 · 1750 → 0.2125 · 2000 → 0.25", "m"),
               (300, 294, "За RC6_MIN и RC6_MAX значение обрезается; RC6_TRIM не участвует.", "m"),
               (300, 307, "После перезагрузки: 0.135 из памяти, затем снова значение крутилки.", "d")])
