"""Stage 6 diagrams for module bf-hd-osd-video (digital video on Betaflight 4.5: DJI, Walksnail, HDZero).

bf-hd-wiring   — the module's worked example: 6S 5" quad, ELRS on UART1 (serial 0 64), air unit on UART4
                 (serial 3 131073 = MSP + VTX_MSP, 115200), power from the FC 9-12 V BEC or VBAT per system,
                 DJI HDL/S.Bus only with a DJI remote.
bf-hd-no-osd   — "video but no OSD" triage in the order the firmware checks it: serial mask (isSerialConfigValid,
                 config.c DisplayPort pick), vcd_video_system / feature OSD (fc/init.c), link (VTX LED, vtx_info,
                 canvas reported by the goggles), then the goggle side.
bf-osd-logo-grid — the boot logo as font characters: osdDrawLogo() (osd/osd.c) writes 24 x 4 characters starting
                 at 160 (0xA0) up to SYM_END_OF_FONT 255 (0xFF); each MAX7456 character is 12 x 18 px (drivers/osd.h),
                 so the Configurator 10.10 LogoManager wants a 288 x 72 px PNG/BMP of pure green / black / white;
                 font memory strip 0-159 glyphs, 160-255 logo; HD: the same codes go to the goggles over MSP.
"""
from __future__ import annotations

from svg import ACCENT, Box, Node, flow, svg, text, tree


def logo_grid() -> str:
    W, cols, rows, first = 720, 24, 4, 160
    assert first + cols * rows - 1 == 255                       # osdDrawLogo stops at SYM_END_OF_FONT 0xFF
    tw, th = 24, 36                                             # 12 x 18 px character, drawn at 2x
    gx, gy = 112, 44
    out = [text(16, 18, "Логотип = 96 символов шрифта: 24 × 4 клетки по 12 × 18 px, коды 160–255 (0xA0–0xFF)", "m t", "start", 11)]
    for r in range(rows):
        lo = first + r * cols
        out.append(text(gx - 10, gy + r * th + th / 2 + 4, f"{lo}–{lo + cols - 1}", "m t", "end", 11))
        for c in range(cols):
            code = lo + c
            x, y = gx + c * tw, gy + r * th
            out.append(f'<rect class="box" x="{x}" y="{y}" width="{tw}" height="{th}" rx="1"/>')
            out.append(text(x + tw / 2, y + th / 2 + 4, f"{code:02X}", "m", "middle", 10.5))
    gw, gh = cols * tw, rows * th
    out.append(f'<rect x="{gx}" y="{gy}" width="{gw}" height="{gh}" fill="none" stroke="{ACCENT}" stroke-width="1.6"/>')
    out.append(text(gx + gw / 2, gy + gh + 18, "картинка 288 × 72 px: 24 × 12 px по ширине, 4 × 18 px по высоте", "a t", "middle", 11))
    # font memory strip 0..255
    sy, sx, sw = gy + gh + 40, 16, W - 32
    split = sx + sw * 160 / 256
    out.append(f'<rect class="box" x="{sx}" y="{sy}" width="{split - sx:.1f}" height="28" rx="3"/>')
    out.append(f'<rect class="boxa" x="{split:.1f}" y="{sy}" width="{sx + sw - split:.1f}" height="28" rx="3"/>')
    out.append(text((sx + split) / 2, sy + 18, "0–159: буквы, цифры, значки OSD", "", "middle", 11.5))
    out.append(text((split + sx + sw) / 2, sy + 18, "160–255: логотип", "b", "middle", 11.5))
    out.append(text(sx, sy + 44, "Память шрифта MAX7456 — 256 символов в NVM чипа, не во flash полётника.", "m t", "start", 11))
    ny = sy + 66
    notes = [
        "Цвета картинки — только 0,255,0 (прозрачный), 0,0,0 (чёрный) и 255,255,255 (белый); PNG или BMP.",
        "Upload Font пишет все 256 символов: логотип — это символы 160–255 шрифта, загруженного последним.",
        "HD (MSP DisplayPort): те же коды 160–255 уходят в очки, картинку рисует шрифт очков.",
    ]
    for i, n in enumerate(notes):
        out.append(text(16, ny + i * 17, n, "m t", "start", 11))
    return svg(W, ny + len(notes) * 17 + 4, "Загрузочный логотип в шрифте OSD", "".join(out))


def build(D: dict) -> None:
    D["bf-osd-logo-grid"] = logo_grid()
    boxes = [
        Box("bat", ["АКБ 6S", "18–25.2 В"], 10, 40, 100, 44),
        Box("fc", ["Полётник F405", "BEC 9–12 В, UART"], 160, 40, 150, 44, accent=True),
        Box("elrs", ["ELRS RX", "UART1: serial 0 64"], 160, 150, 150, 44),
        Box("au", ["Воздушный модуль", "UART4: 131073"], 420, 40, 150, 44, accent=True),
        Box("cam", ["Камера", "MIPI/шлейф"], 420, 150, 150, 44),
        Box("gog", ["Очки", "рисуют OSD"], 620, 40, 90, 44),
    ]
    links = [
        ("bat", "fc", "VBAT", False, "h"),
        ("fc", "au", "TX→RX 115200", True, "h"),
        ("au", "fc", "RX←TX", True, "h"),
        ("elrs", "fc", "CRSF", False, "v"),
        ("cam", "au", "", False, "v"),
        ("au", "gog", "5.8 ГГц", False, "h"),
    ]
    D["bf-hd-wiring"] = flow(
        "HD-видео на Betaflight 4.5: питание, UART и маска порта",
        boxes, links, 720, 290,
        notes=[(10, 222, "Питание: O3, O4 Pro, Vista — VBAT 2S–6S; O4 (не Pro) 3.7–13.2 В, Walksnail Mini 3.1–13 В,", "m t"),
               (10, 237, "HDZero Race V3 4–12 В — только от BEC. Земля питания и сигнальная земля — обе на полётник.", "m t"),
               (10, 252, "UART4 = serial 3 131073: MSP (1) + VTX_MSP (131072). Без бита MSP конфиг портов сбрасывается.", "w t"),
               (10, 267, "DJI HDL/S.Bus (жёлтый) — на S.Bus-пад, только если управление идёт с пульта DJI.", "m t")])

    root = Node("r", ["Видео есть,", "OSD нет"], [
        ("маска не 131073", Node("m", ["Ports: VTX (MSP +", "DisplayPort), 115200"], leaf=True, accent=True)),
        ("маска 131073", Node("v", ["vcd_video_system = HD,", "feature OSD?"], [
            ("нет", Node("v1", ["set vcd_video_system", "= HD, OSD вкл."], leaf=True, accent=True)),
            ("да", Node("s", ["Модуль отвечает по MSP?", "LED, vtx_info, canvas"], [
                ("нет", Node("s1", ["TX↔RX крест, GND,", "не SoftSerial"], leaf=True, accent=True)),
                ("да", Node("s2", ["Очки: Canvas/OSD,", "прошивки, шрифт"], leaf=True, accent=True)),
            ])),
        ])),
    ])
    D["bf-hd-no-osd"] = tree("«Нет OSD в очках»: проверки в порядке, в каком их делает прошивка",
                             root, 720, box_w=160, gap_y=72)
