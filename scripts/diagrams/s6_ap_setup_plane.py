"""Stage 6 diagrams for ap-setup-plane (ArduPlane 4.7 from an empty board to the first flight).

ap-setup-plane-flow         — the 17 setup steps in order, marked bench / outdoors / flight (svg.flow)
ap-setup-plane-fs-timeline  — RC failsafe timeline for the five scenarios of practice step 3 (svg.timeline).
                              Times follow ArduPlane 4.7.2: radio.cpp (RC_FS_TIMEOUT, 10 read cycles of 20 ms,
                              recovery in 4 cycles), system.cpp (check_long_failsafe, FS_LONG_TIMEOUT), events.cpp
                              (action by the mode at the moment of the event).
"""
from __future__ import annotations

from svg import Box, flow, timeline

# step, short label, where it is done. "стол" = bench, propeller off; "улица" = outdoors on the ground
# (GPS fix, pitot check); "полёт" = in the air.
STEPS = [
    (1, "Прошивка, .param", "стол"),
    (2, "SERVOn_FUNCTION", "стол"),
    (3, "SERIALn_PROTOCOL", "стол"),
    (4, "Приёмник, bind", "стол"),
    (5, "Калибровка RC", "стол"),
    (6, "Газ: THR_*", "стол, без пропа"),
    (7, "Направление рулей", "стол"),
    (8, "ESC (только PWM)", "стол, без пропа"),
    (9, "Accel, компас", "стол"),
    (10, "BATT_VOLT/AMP", "стол"),
    (11, "FLTMODE, ARMING", "стол"),
    (12, "Failsafe RC, АКБ", "стол, без пропа"),
    (13, "OSD_TYPE", "стол"),
    (14, "GPS, RTL, ARSPD", "стол + улица"),
    (15, "MANUAL, FBWA, RTL", "полёт"),
    (16, "AUTOTUNE, TECS", "полёт"),
    (17, "Лог + .param", "полёт"),
]

# RC failsafe timing, seconds (defaults of 4.7.2)
RC_FS_TIMEOUT = 1.0
COUNTER = 10 * 0.02          # failsafe.throttle_counter reaches 10 at 50 Hz
FS_LONG_TIMEOUT = 5.0
RECOVERY = 4 * 0.02          # counter 10 -> 3 -> 2 -> 1 -> 0
T_MAX = 10.0


def short_time(no_frames: bool) -> float:
    """Moment of the short failsafe event after the last valid RC frame."""
    return (RC_FS_TIMEOUT if no_frames else 0.0) + COUNTER


def _flow() -> str:
    cols, bw, bh, gx, gy, x0, y0 = 4, 158, 46, 18, 30, 12, 40
    boxes, links = [], []
    for i, (n, label, where) in enumerate(STEPS):
        row, col = divmod(i, cols)
        if row % 2:                       # snake layout: odd rows run right to left
            col = cols - 1 - col
        x, y = x0 + col * (bw + gx), y0 + row * (bh + gy)
        flight = where == "полёт"
        boxes.append(Box(f"s{n}", [f"{n}. {label}", where], x, y, bw, bh, accent=flight))
        if i:
            prev_row = (i - 1) // cols
            links.append((f"s{n - 1}", f"s{n}", "", flight, "v" if prev_row != row else "h"))
    h = y0 + 5 * (bh + gy) + 20
    notes = [
        (12, h - 34, "Рамка с акцентом — шаги в воздухе. До шага 15 пропеллер снят.", "m t"),
        (12, h - 20, "Шаг 7: сначала реакция на наклон в FBWA (SERVOn_REVERSED), потом стики в MANUAL (RCn_REVERSED).", "m t"),
        (12, h - 6, "Шаг 12: failsafe — на земле выключением пульта, без пропеллера: блокировку газа снимает скачок GPS.", "m t"),
    ]
    return flow("ArduPlane 4.7 с нуля: 17 шагов, где каждый делается", boxes, links, 720, h, notes)


def _fs_timeline() -> str:
    s_nf = short_time(True)       # 1.2 s: no frames
    s_thr = short_time(False)     # 0.2 s: throttle below THR_FS_VALUE
    back = 3.0 + RECOVERY         # scenario 5: link returns at 3.0 s
    lanes = [
        ("1 FBWA, 0/0", [(0, s_nf, "FBWA"), (s_nf, FS_LONG_TIMEOUT, "CIRCLE", True), (FS_LONG_TIMEOUT, T_MAX, "RTL", True)]),
        ("2 газ 900, 0.2 с", [(0, s_thr, ""), (s_thr, FS_LONG_TIMEOUT, "CIRCLE", True), (FS_LONG_TIMEOUT, T_MAX, "RTL", True)]),
        ("3 AUTO, 0/0", [(0, T_MAX, "AUTO — миссия продолжается")]),
        ("4 AUTO, 1/0", [(0, s_nf, "AUTO"), (s_nf, FS_LONG_TIMEOUT, "CIRCLE", True), (FS_LONG_TIMEOUT, T_MAX, "RTL", True)]),
        ("5 связь с 3.0 с", [(0, s_nf, "FBWA"), (s_nf, back, "CIRCLE", True), (back, T_MAX, "FBWA восстановлен")]),
    ]
    return timeline("ArduPlane 4.7.2: RC-failsafe по сценариям (FS_SHORT_ACTN / FS_LONG_ACTN)", lanes, T_MAX, unit="с",
                    marks=[(s_nf, f"{s_nf:g} с: короткий"), (FS_LONG_TIMEOUT, f"{FS_LONG_TIMEOUT:g} с: длинный")])


def build(D: dict) -> None:
    D["ap-setup-plane-flow"] = _flow()
    D["ap-setup-plane-fs-timeline"] = _fs_timeline()
