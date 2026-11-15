"""Stage 6 diagrams for module bf-gps-setup (GPS on Betaflight 4.5: M8/M10, auto-config, home point).

chart-bf-gps-cold-sats — the module's lab run (gps_lab.py, SYNTHETIC captures, seeds 100..104): satellites in the
                         3D fix (NAV-PVT numSV) from power-on, cold start, for GPS only, M8 default GPS+GLONASS,
                         M10 default GPS+Galileo+BeiDou and the same M10 with the noise floor raised 10 dB by a VTX.
                         The horizontal line is gps_rescue_min_sats = 8: the arming flag GPS clears there.
bf-gps-boot-flow       — io/gps.c (4.5) state machine for a u-blox module: baud detection with MON-VER, PUBX,41 to the
                         baud from `serial`, ~15-21 RAM config steps, acquire model until the first 3D fix, then the
                         flight model; home point at arming only with >= gps_rescue_min_sats (GPS_reset_home_position).
"""
from __future__ import annotations

from plot import Axis, chart
from svg import Box, flow

# numSV per second, t = 1..60 s, printed from the lab's synthetic_*_cold_*.ubx files
_SATS = {
    "GPS": [0] * 26 + [4, 4, 4, 4, 4, 7, 8, 9, 9] + [10] * 25,
    "M8 GPS+GLO": [0] * 25 + [5, 7, 8, 9, 9, 12, 14, 14, 15] + [16] * 26,
    "M10 GPS+GAL+BDS": [0] * 25 + [6, 9, 10, 14, 16, 16, 18, 22, 25, 26, 27, 27, 27, 27] + [28] * 21,
    "M10, VTX +10 дБ": [0] * 27 + [6, 7, 8] + [9] * 30,
}


def build(D: dict) -> None:
    t = list(range(1, 61))
    lo = 20
    style = {"GPS": ("ink", 57, -8), "M8 GPS+GLO": ("w", 50, -8), "M10 GPS+GAL+BDS": ("a", 50, -8),
             "M10, VTX +10 дБ": ("d", 45, 22)}
    series = []
    for name, ys in _SATS.items():
        cls, at, dy = style[name]
        series.append(dict(name=name, xs=t[lo - 1:], ys=ys[lo - 1:], cls=cls, label_at=at, label_dy=dy,
                           dash=name.startswith("M10, VTX")))
    D["chart-bf-gps-cold-sats"] = chart(
        "Холодный старт: спутники в решении (синтетический лог лабораторной)",
        series, Axis("время от включения, с", lo, 60, ticks=[20, 25, 30, 35, 40, 45, 50, 55, 60]),
        Axis("спутников в 3D fix (numSV)", 0, 30, ticks=[0, 4, 8, 12, 16, 20, 24, 28]),
        hmarks=[(8, "", "m")],
        marks=[(25.4, "fix M10", "a", 20), (27.8, "fix с шумом VTX", "d", 40)],
        notes=[(70, 256, "min_sats = 8", "m"),
               (345, 186, "Шум VTX +10 дБ: видно 28 спутников,", "d"),
               (345, 200, "в решении 9 — эфемериды не декодированы", "d")])

    boxes = [
        Box("pwr", ["Питание", "UART из serial"], 10, 40, 110, 46),
        Box("det", ["DETECT_BAUD", "MON-VER ×3, 330 мс"], 140, 40, 130, 46),
        Box("chg", ["CHANGE_BAUD", "PUBX,41 → 57600"], 290, 40, 130, 46),
        Box("cfg", ["CONFIGURE (RAM)", "1 с + шаги ≥ 110 мс"], 440, 40, 140, 46, accent=True),
        Box("rx", ["RECEIVING", "NAV-PVT 10 Гц"], 600, 40, 110, 46),
        Box("fix", ["Первый 3D fix:", "flight model AIRBORNE_4G"], 440, 150, 170, 46, accent=True),
        Box("ready", ["fix и sats ≥ min_sats:", "флаг GPS снят, READY_BEEP"], 225, 150, 190, 46),
        Box("arm", ["ARM: дом = точка,", "если sats ≥ min_sats"], 10, 150, 190, 46, accent=True),
    ]
    links = [
        ("pwr", "det", "", False, "h"),
        ("det", "chg", "ответ", True, "h"),
        ("chg", "cfg", "990 мс", False, "h"),
        ("cfg", "rx", "", False, "h"),
        ("rx", "fix", "", False, "v"),
        ("fix", "ready", "", False, "h"),
        ("ready", "arm", "", True, "h"),
    ]
    D["bf-gps-boot-flow"] = flow(
        "GPS в Betaflight 4.5 от включения до точки дома (io/gps.c)",
        boxes, links, 720, 300,
        notes=[(10, 232, "Нет ответа 3 раза — следующая скорость: 57600 → 115200 → 9600 → 19200 → 38400 → 57600 …", "m t"),
               (10, 247, "Нет NAV-данных 2.5 с → LOST_COMMUNICATION → снова DETECT_BAUD. gps_auto_config = OFF — CONFIGURE пропущен.", "m t"),
               (10, 262, "До первого fix — gps_ublox_acquire_model (STATIONARY), не до арма. Всё пишется в RAM модуля.", "w t"),
               (10, 277, "gps_set_home_point_once = OFF: дом сбрасывается при каждом дизарме и пишется заново при арме.", "m t")])
