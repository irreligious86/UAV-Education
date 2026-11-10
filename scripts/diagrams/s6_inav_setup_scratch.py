"""Stage 6 diagrams for inav-setup-scratch (INAV с нуля: GPS-квадрокоптер).

inav-setup-flow      — the 17 setup steps in order, tagged SITL / стол / поле (snake layout).
chart-inav-vbat-cal  — pack-voltage error before/after the vbat_scale fix from the module's worked example
                       (multimeter 16.42 V, INAV 15.95 V at vbat_scale 1100 -> 1132).
"""
from __future__ import annotations

from plot import Axis, chart
from svg import Box, flow

STEPS = [
    ("1 Прошивка", "бэкап · SITL"),
    ("2 Миксер", "Quad X · SITL"),
    ("3 Порты UART", "SITL"),
    ("4 Приёмник", "bind · стол"),
    ("5 Каналы", "map · SITL"),
    ("6 Протокол", "DShot · стол"),
    ("7 Моторы", "порядок · стол"),
    ("8 ESC PWM", "калибр. · стол"),
    ("9 Acc, компас", "стол + поле"),
    ("10 АКБ V/A", "стол + полёт"),
    ("11 Режимы", "aux · SITL"),
    ("12 Failsafe", "SITL + стол"),
    ("13 OSD, VTX", "стол"),
    ("14 GPS, RTH", "поле"),
    ("15 Висение", "пропы · поле"),
    ("16 Настройка", "поле"),
    ("17 diff all", "лог · SITL"),
]
FLIGHT = {14, 15, 16}          # 1-based step numbers that need props on (accent boxes)


def build(D: dict) -> None:
    w, h, gx, x0 = 108, 44, 10, 12
    rows = [STEPS[0:6], STEPS[6:12], STEPS[12:17]]
    boxes, links, n = [], [], 0
    for r, row in enumerate(rows):
        y = 40 + r * 84
        for c, (a, b) in enumerate(row):
            n += 1
            col = c if r % 2 == 0 else 5 - c           # snake: row 2 runs right-to-left
            boxes.append(Box(f"s{n}", [a, b], x0 + col * (w + gx), y, w, h, accent=n in FLIGHT))
    for i in range(1, 17):
        same_row = (i - 1) // 6 == i // 6
        links.append((f"s{i}", f"s{i + 1}", "", i + 1 in FLIGHT, "h" if same_row else "v"))
    D["inav-setup-flow"] = flow(
        "INAV с нуля: 17 шагов по порядку — где каждый выполняется",
        boxes, links, 720, 300,
        notes=[(12, 270, "SITL: конфигурация без железа (UART → TCP 5760+).", "m t", "start"),
               (12, 286, "Стол: без пропов. Пропы ставятся только на шаге 15.", "m t", "start")])

    # vbat_scale worked example: reported = true * 1100/1132.4 before, * 1132/1132.4 after
    k_true = 1100 * 16.42 / 15.95                   # scale that would read exactly (1132.4)
    vs = [12.8 + i * 0.04 for i in range(101)]      # 4S: 3.2..4.2 V/cell
    err_old = [(v - v * 1100 / k_true) / 4 * 1000 for v in vs]
    err_new = [(v - v * 1132 / k_true) / 4 * 1000 for v in vs]
    D["chart-inav-vbat-cal"] = chart(
        "Занижение напряжения 4S: vbat_scale 1100 → 1132",
        [dict(name="vbat_scale 1100", xs=vs, ys=err_old, cls="w", label_at=14.2, label_dy=-10),
         dict(name="vbat_scale 1132", xs=vs, ys=err_new, cls="a", label_at=14.2, label_dy=-10)],
        Axis("напряжение пакета (мультиметр), В", 12.8, 16.8), Axis("занижение, мВ на банку", 0, 140),
        hmarks=[(50, "допуск 50 мВ/банку", "m")],
        marks=[(16.42, "калибр.", "m")])
