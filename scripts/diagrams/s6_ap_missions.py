"""Stage 6 diagrams for ap-missions (ArduCopter 4.7.2).

mission-jump-order — the module's SITL mission: execution order with DO_CHANGE_SPEED and DO_JUMP (repeat 1),
                     leg times measured in the run, and what happens after the last item (LOITER inside AUTO)
                     (svg.flow).
"""
from __future__ import annotations

from svg import Box, flow


def _order() -> str:
    bw, bh, gx = 150, 58, 28
    x = [12 + i * (bw + gx) for i in range(4)]
    y1, y2 = 50, 180
    boxes = [
        Box("s1", ["1 TAKEOFF 20 м"], x[0], y1, bw, bh),
        Box("s2", ["2 CHANGE_SPEED", "5 м/с"], x[1], y1, bw, bh),
        Box("s3", ["3 WP A", "100 м N", "≈ 21–23 с"], x[2], y1, bw, bh, accent=True),
        Box("s4", ["4 WP B", "+100 м E", "≈ 21 с"], x[3], y1, bw, bh, accent=True),
        Box("s5", ["5 DO_JUMP → 3", "повтор 1"], x[3], y2, bw, bh),
        Box("s6", ["6 CHANGE_SPEED", "10 м/с"], x[2], y2, bw, bh),
        Box("s7", ["7 WP C", "100 м S", "14.0 с"], x[1], y2, bw, bh),
        Box("s8", ["8 WP D", "дом", "14.8 с"], x[0], y2, bw, bh),
        Box("end", ["конец списка:", "LOITER в AUTO, 20 м"], x[0], 300, bw + 40, 50, accent=True),
    ]
    links = [
        ("s1", "s2", "", False, "h"), ("s2", "s3", "", False, "h"), ("s3", "s4", "", False, "h"),
        ("s4", "s5", "", False, "v"), ("s5", "s6", "", False, "h"),
        ("s6", "s7", "", False, "h"), ("s7", "s8", "", False, "h"), ("s8", "end", "", True, "v"),
    ]
    notes = [
        (x[2], 258, "пунктир: 5 → 3 (Jump 1/1), A и B ещё раз", "w t"),
        (240, 320, "Миссия без RTL: через 20 с — AUTO, 20.0 м, заармлен.", "m t"),
        (240, 336, "100 м без остановки: 5 м/с ≈ 21 с, 10 м/с ≈ 14 с (≈ d/v + поворот).", "m t"),
    ]
    out = flow("Порядок выполнения миссии с DO_JUMP (прогон SITL 4.7.2)", boxes, links, 720, 362, notes)
    # the jump: dashed accent arrow from item 5 back up to item 3
    xa, xb = x[3] + 20, x[2] + bw - 20
    arrow = (f'<path class="lna" style="stroke-dasharray:5 4" d="M{xa} {y2} L{xa} {y2 - 30} L{xb} {y2 - 30} '
             f'L{xb} {y1 + bh}" marker-end="url(#ara)"/>')
    return out.replace("</svg>", arrow + "</svg>")


def build(D: dict) -> None:
    D["mission-jump-order"] = _order()
