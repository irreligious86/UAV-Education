"""Stage 6 diagrams for module bf-setup-scratch (Betaflight 4.5 from an empty board to the maiden hover).

bf-setup-flow             — the 17 setup steps merged into 12 boxes, marked SITL / bench / field.
chart-bf-mah-calibration  — mAh the FC would report for the module's worked-example flight vs ibata_scale
                            (I ~ 1/ibata_scale, sensors/current.c): 905 mAh at 400, charger 1032 mAh, new 351.
"""
from __future__ import annotations

from plot import Axis, chart
from svg import Box, flow


def build(D: dict) -> None:
    W, H, GX, GY = 160, 44, 180, 72
    cells = [
        ("s1", ["1. SITL, бэкап", "SITL + USB"], True),
        ("s2", ["2–3. Quad X, порты", "SITL"], True),
        ("s3", ["4–5. ELRS, каналы", "стол"], False),
        ("s4", ["6–8. DShot, порядок,", "вращение — стол"], False),
        ("s5", ["9. Акселерометр", "SITL, затем стол"], True),
        ("s6", ["10. vbat / ibata", "стол + полёт"], False),
        ("s7", ["11. Режимы, арм", "SITL"], True),
        ("s8", ["12. Failsafe", "SITL, затем стол"], True),
        ("s9", ["13–14. OSD, VTX,", "GPS Rescue — стол"], False),
        ("s10", ["15. Предполётка,", "висение — поле"], False),
        ("s11", ["16. Фильтры, PID", "SITL + поле"], True),
        ("s12", ["17. Лог, diff all", "SITL + поле"], True),
    ]
    boxes = []
    for i, (bid, lines, acc) in enumerate(cells):
        row, col = divmod(i, 4)
        if row % 2:                       # snake: odd rows run right to left
            col = 3 - col
        boxes.append(Box(bid, lines, 10 + col * GX, 14 + row * GY, W, H, accent=acc))
    links = []
    for i in range(len(cells) - 1):
        a, b = cells[i][0], cells[i + 1][0]
        route = "v" if (i + 1) % 4 == 0 else "h"
        links.append((a, b, "", a == "s9", route))   # props go on only between step 14 and 15
    D["bf-setup-flow"] = flow(
        "Betaflight 4.5 с нуля: 17 шагов, где их делать",
        boxes, links, 720, 248,
        notes=[(10, 226, "Акцентная рамка — шаг проходится в SITL; обычная — только на железе.", "m t"),
               (10, 241, "Пропеллеры ставятся только на шаге 15, после теста failsafe и моторов.", "w t")])

    scales = [250 + i for i in range(201)]                 # 250…450
    reported = [905 * 400 / s for s in scales]             # same flight, same sensor millivolts
    D["chart-bf-mah-calibration"] = chart(
        "мА·ч полёта в OSD при разном ibata_scale",
        [dict(name="показание FC", xs=scales, ys=reported, cls="a", label_at=290)],
        Axis("ibata_scale", 250, 450), Axis("мА·ч по данным FC", 700, 1500),
        marks=[(400, "было 400: 905", "d"), (351, "стало 351: 1031", "a")],
        hmarks=[(1032, "зарядка 1032", "m"), (1084, "+5 %", "w"), (980, "−5 %", "w")])
