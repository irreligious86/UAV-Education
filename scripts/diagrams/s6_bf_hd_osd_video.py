"""Stage 6 diagrams for module bf-hd-osd-video (digital video on Betaflight 4.5: DJI, Walksnail, HDZero).

bf-hd-wiring   — the module's worked example: 6S 5" quad, ELRS on UART1 (serial 0 64), air unit on UART4
                 (serial 3 131073 = MSP + VTX_MSP, 115200), power from the FC 9-12 V BEC or VBAT per system,
                 DJI HDL/S.Bus only with a DJI remote.
bf-hd-no-osd   — "video but no OSD" triage in the order the firmware checks it: serial mask (isSerialConfigValid,
                 config.c DisplayPort pick), vcd_video_system / feature OSD (fc/init.c), link (VTX LED, vtx_info,
                 canvas reported by the goggles), then the goggle side.
"""
from __future__ import annotations

from svg import Box, Node, flow, tree


def build(D: dict) -> None:
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
