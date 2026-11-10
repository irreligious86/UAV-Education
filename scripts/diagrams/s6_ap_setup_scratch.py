"""Stage 6 diagrams for ap-setup-scratch (ArduCopter 4.6 from an empty board to a logged hover).

ap-setup-flow       — the 17 setup steps in order, marked SITL / bench / field (svg.flow)
chart-ap-batt-cal   — current-sensor calibration from the module's worked example (plot.chart)
"""
from __future__ import annotations

from plot import Axis, chart
from svg import Box, flow

# step, short label, where it is done. "SITL" = main path in the simulator, "стол" = bench, no props,
# "поле" = field with props.
STEPS = [
    (1, "Прошивка, .param", "стол + SITL"),
    (2, "FRAME_CLASS/TYPE", "SITL"),
    (3, "SERIALn_PROTOCOL", "SITL"),
    (4, "Приёмник, bind", "стол"),
    (5, "Калибровка RC", "стол"),
    (6, "MOT_PWM_TYPE", "SITL + стол"),
    (7, "Motor Test", "SITL + стол"),
    (8, "ESC cal, SPIN_*", "стол"),
    (9, "Accel + компас", "стол (SITL)"),
    (10, "BATT_VOLT/AMP", "SITL + стол"),
    (11, "Режимы, арм", "SITL"),
    (12, "FS_THR, BATT_FS", "SITL + стол"),
    (13, "OSD_TYPE", "стол"),
    (14, "GPS, RTL_ALT", "SITL"),
    (15, "Висение S→AH→L", "SITL → поле"),
    (16, "QuikTune/AutoTune", "поле"),
    (17, "Лог + .param", "SITL + поле"),
]


def _flow() -> str:
    cols, bw, bh, gx, gy, x0, y0 = 4, 158, 46, 18, 30, 12, 40
    boxes, links = [], []
    for i, (n, label, where) in enumerate(STEPS):
        row, col = divmod(i, cols)
        if row % 2:                       # snake layout: odd rows run right to left
            col = cols - 1 - col
        x, y = x0 + col * (bw + gx), y0 + row * (bh + gy)
        flight = "поле" in where
        boxes.append(Box(f"s{n}", [f"{n}. {label}", where], x, y, bw, bh, accent=flight))
        if i:
            prev_row = (i - 1) // cols
            links.append((f"s{n - 1}", f"s{n}", "", flight, "v" if prev_row != row else "h"))
    h = y0 + 5 * (bh + gy) + 20
    notes = [
        (12, h - 34, "Рамка с акцентом — шаги с пропеллерами (поле).", "m t"),
        (12, h - 20, "До шага 15 пропы сняты: арм, Motor Test, ESC cal и failsafe — без пропов.", "m t"),
        (12, h - 6, "SITL: 1–3, 6, 7, 9–12, 14, 15, 17; bind, RC cal, ESC cal, OSD, тюн — только железо.", "m t"),
    ]
    return flow("ArduCopter 4.6 с нуля: 17 шагов, где каждый делается", boxes, links, 720, h, notes)


def _batt_chart() -> str:
    # Worked example from the module: the sensor really gives Vpin = 0.0125 V + I / 44 A/V.
    # Factory setting: BATT_AMP_OFFSET = 0, BATT_AMP_PERVLT = 40  -> reads 0.50 A at rest, 9.59 A at 10 A.
    # Step 1 (offset at 0 A):  offset = 0 + 0.50 / 40 = 0.0125 V  -> 9.09 A at 10 A.
    # Step 2 (gain at 10 A):   PERVLT = 40 * 10 / 9.09 = 44.0     -> 10.0 A.
    xs = [i * 0.25 for i in range(0, 81)]
    vpin = [0.0125 + i / 44.0 for i in xs]
    factory = [v * 40 for v in vpin]
    offset_only = [(v - 0.0125) * 40 for v in vpin]
    calibrated = [(v - 0.0125) * 44.0 for v in vpin]
    series = [
        dict(name="заводские: 0 В, 40 А/В", xs=xs, ys=factory, cls="d", label_at=19.8, label_dy=-6),
        dict(name="после AMP_OFFSET", xs=xs, ys=offset_only, cls="w", dash=True, label_at=17, label_dy=62),
        dict(name="после AMP_PERVLT = 44", xs=xs, ys=calibrated, cls="a", label_at=9.6, label_dy=-14),
    ]
    return chart("Калибровка датчика тока: сначала ноль, потом наклон", series,
                 Axis("ток по клещам, А", 0, 20), Axis("ток в GCS, А", 0, 20),
                 marks=[(10, "10 А: 9.59 → 9.09 → 10.0 А", "ink", 200)],
                 notes=[(470, 284, "0 А: заводские показывают 0.50 А", "m"), (470, 298, "→ BATT_AMP_OFFSET = 0.0125 В", "m")])


def build(D: dict) -> None:
    D["ap-setup-flow"] = _flow()
    D["chart-ap-batt-cal"] = _batt_chart()
