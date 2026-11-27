"""Stage 6 diagrams for px4-rc-tuning (PX4 v1.17.0 and v1.18.0, src/modules/rc_update/rc_update.cpp unchanged).

1. px4-rc-flow             — input_rc -> rc_update (calibration, normalisation) -> three products:
                             manual_control_input (sticks, flaps, AUX), manual_control_switches (mode slot and
                             single-function switches) and param_set() for the RC_MAP_PARAMn tuning channels.
2. chart-px4-rc-mode-slots — mode slot against channel pulse for RC6_MIN/TRIM/MAX = 1000/1500/2000, computed with
                             the expression from RCUpdate::UpdateManualSwitches(); slot changes at 1107, 1282, 1457,
                             1632 and 1807 us (same numbers as the table in the module); a 2-position switch lands in
                             slots 1 and 6, a 3-position switch in 1, 4 and 6.
"""
from __future__ import annotations

from plot import Axis, chart
from svg import Box, flow

NUM_SLOTS = 6
SLOT_MIN, SLOT_MAX = -1.05, 1.05


def _norm(pwm: float, mn: float = 1000.0, trim: float = 1500.0, mx: float = 2000.0) -> float:
    """math::interpolateNXY(value, {min, trim, max}, {-1, 0, 1}) — clamped piecewise-linear."""
    if pwm <= mn:
        return -1.0
    if pwm > mx:
        return 1.0
    if pwm <= trim:
        return (pwm - trim) / (trim - mn)
    return (pwm - trim) / (mx - trim)


def _slot(value: float) -> int:
    half = 1.0 / NUM_SLOTS
    s = int((((value - SLOT_MIN) * NUM_SLOTS) + half) / (SLOT_MAX - SLOT_MIN) + half) + 1
    return min(s, NUM_SLOTS)


def build(D: dict) -> None:
    # ---- 1. flow -----------------------------------------------------------------------------
    boxes = [
        Box("rx", ["Приёмник:", "CRSF, SBUS, PPM"], 12, 60, 108, 46),
        Box("in", ["input_rc", "мкс, до 18 каналов"], 138, 60, 118, 46),
        Box("ru", ["rc_update", "MIN / TRIM / MAX / REV", "→ −1…+1"], 276, 52, 150, 62, accent=True),
        Box("mi", ["manual_control_input", "стики, flaps, aux1…6"], 452, 30, 256, 36),
        Box("sw", ["manual_control_switches", "mode_slot, arm, kill, return…"], 452, 78, 256, 36),
        Box("map", ["rc_parameter_map", "от GCS: PARAM_MAP_RC"], 100, 160, 156, 46),
        Box("ps", ["param_set()", "ручки 1…3, ≤ 1 Гц"], 276, 160, 150, 46),
        Box("mc", ["manual_control", "COM_RC_IN_MODE"], 452, 160, 122, 46, accent=True),
        Box("joy", ["MAVLink:", "джойстик GCS"], 596, 160, 112, 46),
        Box("cm", ["commander", "режим, арм, kill"], 452, 240, 122, 40),
    ]
    links = [
        ("rx", "in"), ("in", "ru"), ("ru", "mi", "", True), ("ru", "sw", "", True),
        ("ru", "ps", "", True, "v"), ("map", "ps"), ("sw", "mc", "", False, "v"), ("joy", "mc"),
        ("mc", "cm", "", False, "v"),
    ]
    D["px4-rc-flow"] = flow(
        "PX4 1.18: канал пульта → нормировка → стики, тумблеры, подстройка", boxes, links, 720, 330,
        notes=[
            (12, 300, "Тумблеры и ручки подстройки живут только в rc_update: джойстик MAVLink приходит", "m t"),
            (12, 315, "в manual_control мимо него — слотов режимов, kill и RC_MAP_PARAMn у джойстика нет.", "m t"),
            (12, 236, "Привязка ручки к параметру (rc_parameter_map)", "m t"),
            (12, 251, "хранится в ОЗУ и теряется при перезагрузке.", "m t"),
        ])

    # ---- 2. mode-slot chart ------------------------------------------------------------------
    xs, ys = [], []
    prev = None
    edges = []
    for pwm in range(950, 2051):
        s = _slot(_norm(pwm))
        if prev is not None and s != prev:
            edges.append(pwm)
            xs.append(pwm)          # vertical riser of the step
            ys.append(prev)
        xs.append(pwm)
        ys.append(s)
        prev = s
    assert edges == [1107, 1282, 1457, 1632, 1807], edges
    marks = [(e, str(e), "m", 20 + 16 * (i % 2)) for i, e in enumerate(edges)]
    dots3 = dict(name="3 позиции: слоты 1, 4, 6", xs=[1000, 1500, 2000], ys=[1, 4, 6], cls="a", dots=True,
                 label_at=1500, label_dy=-10, label_anchor="end")
    D["chart-px4-rc-mode-slots"] = chart(
        "Слот режима по импульсу канала RC_MAP_FLTMODE (калибровка 1000 / 1500 / 2000)",
        [dict(xs=xs, ys=ys, cls="ink"), dots3],
        Axis("импульс канала, мкс", 950, 2050, ticks=[1000, 1250, 1500, 1750, 2000]),
        Axis("слот (COM_FLTMODEn)", 0, 7, ticks=[1, 2, 3, 4, 5, 6]),
        marks=marks,
        notes=[
            (300, 268, "Шаг слота 0.35 шкалы −1…+1 = 175 мкс; центр 1500 мкс — слот 4, а не 3.", "m"),
            (300, 284, "Двухпозиционный тумблер (1000 / 2000 мкс) даёт слоты 1 и 6.", "m"),
        ])
