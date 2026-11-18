"""Stage 6 diagrams for module inav-osd-hd (INAV 9.1 OSD: analogue MAX7456 and HD over MSP DisplayPort).

inav-osd-signal-path  — who draws the OSD: analogue (MAX7456 on the FC mixes characters into the camera
                        signal) versus HD (FC sends characters over a UART with FUNCTION_MSP_OSD, the
                        goggles draw them with their own font). Order of display-port selection as in
                        fc/fc_init.c 9.1.0: FrSky OSD, then MSP DisplayPort, then MAX7456.
chart-inav-osd-canvas — character grids selected by osd_video_system (io/displayport_msp_osd.c 9.1.0)
                        drawn to scale, with the ten elements of the module's worked example
                        (layout for 53x20): which of them fall outside 50x18 and 30x16.
"""
from __future__ import annotations

from svg import ACCENT, DANGER, INK, MUTED, WARN, Box, flow, svg, text

# (item id, short name, col, row, visible) — the same lines as in the module, practice step 2
EXAMPLE = [
    (0, "RSSI", 2, 1, True), (1, "VBAT", 2, 2, True), (15, "ALT", 44, 1, True), (23, "DIST", 44, 2, True),
    (14, "SATS", 2, 18, True), (7, "MODE", 24, 17, True), (30, "MSG", 13, 18, True), (12, "MAH", 44, 18, True),
    (110, "LQ", 2, 3, False), (147, "CUST", 22, 3, True),
]
CANVAS = [  # name, cols, rows, colour, dash
    ("DJIWTF 60×22", 60, 22, MUTED, "4 3"),
    ("AVATAR / BFHDCOMPAT / DJI_NATIVE 53×20", 53, 20, ACCENT, ""),
    ("HDZERO 50×18", 50, 18, WARN, ""),
    ("PAL / AUTO / BF43COMPAT 30×16", 30, 16, INK, ""),
    ("NTSC 30×13", 30, 13, MUTED, "2 3"),
]


def build(D: dict) -> None:
    boxes = [
        Box("cam", ["Аналог. камера", "CVBS"], 10, 40, 130, 44),
        Box("max", ["MAX7456 на FC", "30×16 / 30×13"], 190, 40, 140, 44),
        Box("vtx", ["Аналог. VTX", "5.8 ГГц"], 380, 40, 130, 44),
        Box("gog1", ["Очки", "показывают кадр"], 570, 40, 140, 44),
        Box("fc", ["FC: osd.c", "сетка символов"], 190, 150, 140, 44, accent=True),
        Box("au", ["Возд. модуль HD", "DJI/Avatar/HDZero"], 380, 150, 130, 44, accent=True),
        Box("gog2", ["Очки: шрифт,", "рисуют OSD"], 570, 150, 140, 44, accent=True),
        Box("cam2", ["Цифр. камера", "MIPI"], 380, 240, 130, 40),
    ]
    links = [
        ("cam", "max", "видео", False, "h"),
        ("max", "vtx", "+OSD", False, "h"),
        ("vtx", "gog1", "радио", False, "h"),
        ("fc", "max", "SPI", False, "v"),
        ("fc", "au", "UART", True, "h"),
        ("au", "gog2", "радио", True, "h"),
        ("cam2", "au", "", False, "v"),
    ]
    D["inav-osd-signal-path"] = flow(
        "INAV OSD: аналог (рисует MAX7456) и HD (рисуют очки)",
        boxes, links, 720, 350,
        notes=[(10, 306, "HD: UART 115200, функция MSP_OSD (33554432); сетку задаёт osd_video_system. Модуль шлёт MSP", "a t"),
               (10, 321, "раз в ~125 мс; молчит 1 с — полётник перестаёт слать OSD. Выбор в fc_init.c: FrSky OSD → MSP → MAX7456.", "m t"),
               (10, 336, "Если назначен порт MSP_OSD, чип MAX7456 не используется: аналоговое OSD пропадёт.", "w t")])

    # canvases to scale: 10 px per column, 12 px per row
    cw, rh, x0, y0 = 10, 12, 60, 44
    out = [text(x0, 20, "Сетки osd_video_system в одном масштабе и элементы примера (раскладка под 53×20)", "b", "start", 13)]
    for name, cols, rows, colour, dash in CANVAS:
        da = f' stroke-dasharray="{dash}"' if dash else ""
        out.append(f'<rect x="{x0}" y="{y0}" width="{cols * cw}" height="{rows * rh}" fill="none" stroke="{colour}" '
                   f'stroke-width="1.4"{da}/>')
    out.append(text(x0 + 60 * cw - 4, y0 + 22 * rh - 5, "60×22", "m t", "end"))
    out.append(text(x0 + 53 * cw - 4, y0 + 20 * rh - 5, "53×20", "a t", "end"))
    out.append(text(x0 + 50 * cw - 4, y0 + 18 * rh - 5, "50×18", "w t", "end"))
    out.append(text(x0 + 30 * cw - 4, y0 + 16 * rh - 5, "30×16", "t", "end"))
    out.append(text(x0 + 30 * cw - 4, y0 + 13 * rh - 5, "30×13", "m t", "end"))
    for c in (0, 10, 20, 30, 40, 50, 60):
        out.append(text(x0 + c * cw, y0 - 6, str(c), "m t"))
    for r in (0, 5, 10, 13, 16, 18, 20, 22):
        out.append(text(x0 - 8, y0 + r * rh + 4, str(r), "m t", "end"))
    out.append(text(x0 - 8, y0 - 20, "стр.", "m t", "end"))
    out.append(text(x0 + 60 * cw + 14, y0 - 6, "стлб", "m t", "start"))
    for item, name, col, row, vis in EXAMPLE:
        px, py = x0 + col * cw + cw / 2, y0 + row * rh + rh / 2
        in_hdz = col < 50 and row < 18
        in_pal = col < 30 and row < 16
        colour = INK if in_pal else (WARN if in_hdz else DANGER)
        fill = colour if vis else "none"
        out.append(f'<circle cx="{px}" cy="{py}" r="4" fill="{fill}" stroke="{colour}" stroke-width="1.4"/>')
        if col >= 40:
            out.append(text(px - 8, py + 4, f"{name} {col},{row}", "t", "end", 10))
        else:
            out.append(text(px + 8, py + 4, f"{name} {col},{row}", "t", "start", 10))
    yb = y0 + 22 * rh + 20
    out.append(text(x0, yb, "Тёмная точка — внутри 30×16; жёлтая — вне 30×16, внутри 50×18; красная — вне 50×18; пустая — H.", "m t", "start"))
    out.append(text(x0, yb + 15, "Вне 30×16 — 6 элементов из 10; вне 50×18 — 3 (строка 18). INAV не сдвигает элементы сам.", "w t", "start"))
    D["chart-inav-osd-canvas"] = svg(720, yb + 28, "Сетки OSD INAV 9.1 и элементы примера", "".join(out))
