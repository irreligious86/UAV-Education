"""Stage 6 diagrams for module ap-osd-video (ArduPilot 4.7 OSD backends, MSP DisplayPort grids, VTX).

ap-osd-backend-map     — which OSD_TYPE pairs with which SERIALn_PROTOCOL and who draws the picture:
                         MAX7456 (type 1, no serial port), MSP DisplayPort (type 5 + protocol 42),
                         legacy MSP telemetry (type 3 + protocol 33/32). Values as in AP_OSD.h (osd_types)
                         and AP_SerialManager.h of Copter-4.7.2.
chart-ap-osd-grid-fit  — the three OSDn_TXT_RES grids (AP_OSD_Screen.cpp 4.7.2: 0 = 30x16, 1 = 50x18,
                         2 = 60x22) drawn to scale with the ten elements of the module's practice step 2
                         (layout made for 60x22): which anchors fall outside 50x18 and 30x16.
"""
from __future__ import annotations

from svg import ACCENT, DANGER, INK, MUTED, WARN, Box, flow, svg, text

# (name, col, row, width, height) — the same lines as in the module, practice step 2; widths: MESSAGE 26 visible
# cells (message_visible_width), ALTITUDE "%4d%c", SATS 2 icons + "%2u", FLTMODE name4 + arm icon; STATS is 6 rows
# tall (draw_stat), its 7-cell width here is only for drawing
EXAMPLE = [
    ("BAT_VOLT", 2, 1, 1, 1), ("CURRENT", 2, 2, 1, 1), ("GSPEED", 2, 10, 1, 1), ("HOME", 46, 1, 1, 1),
    ("ALTITUDE", 54, 10, 5, 1), ("VSPEED", 25, 15, 1, 1), ("MESSAGE", 6, 15, 26, 1), ("SATS", 2, 20, 4, 1),
    ("FLTMODE", 27, 20, 5, 1), ("STATS", 40, 13, 7, 6),
]
GRIDS = [  # OSDn_TXT_RES, cols, rows, colour, dash
    (2, 60, 22, MUTED, "4 3"),
    (1, 50, 18, ACCENT, ""),
    (0, 30, 16, INK, ""),
]


def anchors_outside(cols: int, rows: int) -> list[str]:
    return [n for n, c, r, _w, _h in EXAMPLE if not (c < cols and r < rows)]


def build(D: dict) -> None:
    boxes = [
        Box("fc", ["AP_OSD", "экраны OSD1…OSD6"], 20, 130, 150, 48, accent=True),
        Box("max", ["OSD_TYPE = 1", "MAX7456 на плате"], 250, 40, 170, 44),
        Box("dp", ["OSD_TYPE = 5", "DisplayPort: клетки"], 250, 130, 170, 48, accent=True),
        Box("msp", ["OSD_TYPE = 3", "MSP: только числа"], 250, 226, 170, 44),
        Box("vtxa", ["Аналоговый VTX", "рисует чип, 30×16/13"], 520, 40, 180, 44),
        Box("hd", ["HDZero, Walksnail,", "DJI O3/O4, WTFOS"], 520, 130, 180, 48, accent=True),
        Box("dji", ["DJI FPV V1/V2", "рисуют очки сами"], 520, 226, 180, 44),
    ]
    links = [
        ("fc", "max", "SPI", False, "h"),
        ("fc", "dp", "", True, "h"),
        ("fc", "msp", "", False, "h"),
        ("max", "vtxa", "видео + OSD", False, "h"),
        ("dp", "hd", "PROTOCOL 42", True, "h"),
        ("msp", "dji", "PROTOCOL 33", False, "h"),
    ]
    D["ap-osd-backend-map"] = flow(
        "ArduPilot 4.7: тип OSD, протокол порта и кто рисует",
        boxes, links, 720, 350,
        notes=[(20, 302, "UART 115200 (SERIALn_BAUD = 115), провода TX и RX. Сетка DisplayPort: OSDn_TXT_RES 0/1/2 = 30×16 / 50×18 / 60×22.", "a t"),
               (20, 317, "MSP_OPTIONS: бит 2 (4) — символы Betaflight, бит 3 (8) — INAV, бит 0 (1) — push-телеметрия только для протокола 33.", "m t"),
               (20, 332, "OSD_TYPE2 добавляет второй бэкенд: 1 + 5 или 1 + 3. Пара 3 + 5 и два одинаковых типа не запускаются.", "w t")])

    cw, rh, x0, y0 = 10, 12, 60, 44
    out = [text(x0, 20, "Сетки OSDn_TXT_RES в одном масштабе и элементы шага 2 (раскладка под 60×22)", "b", "start", 13)]
    for res, cols, rows, colour, dash in GRIDS:
        da = f' stroke-dasharray="{dash}"' if dash else ""
        out.append(f'<rect x="{x0}" y="{y0}" width="{cols * cw}" height="{rows * rh}" fill="none" stroke="{colour}" '
                   f'stroke-width="1.4"{da}/>')
        cls = {2: "m t", 1: "a t", 0: "t"}[res]
        ly = {2: y0 + rows * rh - 5, 1: y0 + 6 * rh, 0: y0 + 14}[res]
        out.append(text(x0 + cols * cw - 4, ly, f"TXT_RES {res}: {cols}×{rows}", cls, "end"))
    for c in (0, 10, 20, 30, 40, 50, 60):
        out.append(text(x0 + c * cw, y0 - 6, str(c), "m t"))
    for r in (0, 5, 10, 16, 18, 22):
        out.append(text(x0 - 8, y0 + r * rh + 4, str(r), "m t", "end"))
    out.append(text(x0 - 8, y0 - 20, "Y", "m t", "end"))
    out.append(text(x0 + 60 * cw + 14, y0 - 6, "X", "m t", "start"))
    for name, col, row, w, h in EXAMPLE:
        in_50 = col < 50 and row < 18
        in_30 = col < 30 and row < 16
        colour = INK if in_30 else (WARN if in_50 else DANGER)
        if w > 1 or h > 1:   # footprint of wide / tall elements
            out.append(f'<rect x="{x0 + col * cw}" y="{y0 + row * rh}" width="{w * cw}" height="{h * rh}" fill="none" '
                       f'stroke="{colour}" stroke-width="0.9" stroke-dasharray="2 2"/>')
        px, py = x0 + col * cw + cw / 2, y0 + row * rh + rh / 2
        out.append(f'<circle cx="{px}" cy="{py}" r="3.6" fill="{colour}" stroke="{colour}" stroke-width="1.2"/>')
        label = f"{name} {col},{row}"
        if name in ("ALTITUDE", "STATS"):
            out.append(text(px - 8, py - 6, label, "t", "end", 10))
        elif name == "MESSAGE":
            out.append(text(px + 8, py - 8, label + " (ширина 26)", "t", "start", 10))
        elif name == "VSPEED":
            out.append(text(px, py + 17, label, "t", "middle", 10))
        elif name == "HOME":
            out.append(text(px - 8, py + 4, label, "t", "end", 10))
        else:
            out.append(text(px + 8, py + 4, label, "t", "start", 10))
    o50, o30 = anchors_outside(50, 18), anchors_outside(30, 16)
    yb = y0 + 22 * rh + 20
    out.append(text(x0, yb, "Тёмная точка — якорь внутри 30×16; жёлтая — вне 30×16, внутри 50×18; красная — вне 50×18.", "m t", "start"))
    out.append(text(x0, yb + 15, f"Вне 50×18 — {len(o50)} якоря из {len(EXAMPLE)} и нижняя строка STATS; вне 30×16 — {len(o30)} якорей и 2 символа MESSAGE.", "w t", "start"))
    out.append(text(x0, yb + 30, "ArduPilot не сдвигает элементы при смене OSDn_TXT_RES: координаты остаются как записаны.", "m t", "start"))
    D["chart-ap-osd-grid-fit"] = svg(720, yb + 42, "Сетки OSD ArduPilot 4.7 и элементы примера", "".join(out))
