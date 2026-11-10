"""Stage 6 diagrams for module inav-setup-wing (INAV wing from scratch).

inav-wing-setup-flow  — the 17 setup steps for a wing, merged into 14 boxes, marked SITL / bench / field.
chart-inav-loiter-bank — loiter bank angle tan(phi) = V^2/(g R) vs radius, worked example of the module.
"""
from __future__ import annotations

import math

from plot import Axis, chart
from svg import Box, flow


def build(D: dict) -> None:
    W, H, GX, GY = 160, 44, 180, 72
    cells = [
        ("s1", ["1. Прошивка, бэкап", "SITL + USB"], True),
        ("s2", ["2. Платформа, миксер", "SITL"], True),
        ("s3", ["3. Порты UART", "SITL"], True),
        ("s4", ["4–5. Приёмник, RC", "стол"], False),
        ("s5", ["6–8. Мотор, ESC", "стол, без пропа"], False),
        ("s6", ["7б. Сервы: реверс,", "центр, расходы — стол"], False),
        ("s7", ["9. Акселер., ЦТ", "стол"], False),
        ("s8", ["10. Батарея V / мА·ч", "стол + поле"], False),
        ("s9", ["11. Режимы, арм", "SITL"], True),
        ("s10", ["12. Failsafe", "SITL, затем стол"], True),
        ("s11", ["13–14. OSD, GPS, RTH", "SITL (RF/X-Plane)"], True),
        ("s12", ["15. Предполётка,", "бросок — поле"], False),
        ("s13", ["16. Autotrim,", "autotune — поле"], False),
        ("s14", ["17. Лог + diff all", "SITL + поле"], True),
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
        acc = a == "s11"                  # props go on only after step 15 checks
        links.append((a, b, "", acc, route))
    D["inav-wing-setup-flow"] = flow(
        "INAV-крыло с нуля: 17 шагов, где их делать",
        boxes, links, 720, 318,
        notes=[(10, 296, "Акцентная рамка — шаг можно пройти в SITL; обычная — только на железе.", "m t"),
               (10, 311, "Проп ставится только на шаге 15, после теста failsafe и направлений рулей.", "w t")])

    radii = [20 + i * 0.5 for i in range(241)]           # 20…140 m
    series = []
    for v, cls in ((12, "m"), (15, "a"), (18, "w")):
        ys = [math.degrees(math.atan(v * v / (9.81 * r))) for r in radii]
        series.append(dict(name=f"{v} м/с", xs=radii, ys=ys, cls=cls, label_at=128))
    D["chart-inav-loiter-bank"] = chart(
        "Крен в круге loiter: tan φ = V² / (g·R)",
        series,
        Axis("радиус круга nav_fw_loiter_radius, м", 20, 140), Axis("нужный крен, °", 0, 60),
        marks=[(30, "30 м: 37° при 15 м/с", "d"), (75, "75 м (по умолч.): 17°", "a")],
        hmarks=[(35, "nav_fw_bank_angle = 35°", "w")])
