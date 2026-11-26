"""Stage 6 diagrams for ap-sitl (ArduCopter 4.7.2 SITL).

sitl-param-layers — where a parameter value in SITL comes from: code default, --defaults files left to right,
                    eeprom.bin, param set; -w wipes eeprom.bin (svg.flow). Numbers: RTL_ALT_M 15 (code) and
                    20 (lab.parm) from the module's step 5.
"""
from __future__ import annotations

from svg import Box, flow


def _layers() -> str:
    y, bw, bh = 56, 150, 58
    xs = [12, 190, 368, 546]
    boxes = [
        Box("code", ["1. Код прошивки", "AP_GROUPINFO", "RTL_ALT_M = 15"], xs[0], y, bw, bh),
        Box("def", ["2. --defaults", "copter.parm,", "lab.parm (20)"], xs[1], y, bw, bh),
        Box("eep", ["3. eeprom.bin", "сюда пишет", "param set (4)"], xs[2], y, bw, bh, accent=True),
        Box("val", ["Значение", "в прошивке", "RTL_ALT_M"], xs[3], y, bw, bh),
        Box("w", ["-w / --wipe", "стирает eeprom.bin"], xs[2], y + 120, bw, 44),
    ]
    links = [
        ("code", "def", "", False, "h"),
        ("def", "eep", "", False, "h"),
        ("eep", "val", "", True, "h"),
        ("w", "eep", "", False, "v"),
    ]
    notes = [
        (12, 30, "Стрелка: слой справа перебивает слой слева.", "m t"),
        (12, 250, "Правый файл в --defaults перебивает левый; eeprom.bin перебивает все файлы.", "m t"),
        (12, 266, "Правка .parm «не работает» → в eeprom.bin старое значение: запуск с -w.", "m t"),
        (12, 282, "Шаг 5: copter.parm + lab.parm с -w → RTL_ALT_M = 20, а не 15.", "m t"),
    ]
    return flow("SITL: откуда берётся значение параметра", boxes, links, 720, 296, notes)


def build(D: dict) -> None:
    D["sitl-param-layers"] = _layers()
