"""Stage 6 diagrams for module inav-adjustments (INAV 9.1.0 in-flight adjustments, fc/rc_adjustments.c).

inav-adjustments-flow     — range channel -> adjrange row -> slot (0..3) -> step by thresholds 1300/1700 ->
                            RAM -> whole-config EEPROM writes (stick Save, CLI save, CMS, side effects).
chart-inav-adj-staircase  — the module's practice step 2: nav_fw_cruise_thr 1400, AUX4 held high 2.3 s
                            (steps at 0, 480, 980, 1480, 1980 ms after the press — Python port of
                            updateAdjustmentStates/processRcAdjustments, 20 ms RX cycle), then two 0.2 s taps
                            low: 1400 -> 1450 -> 1430.
"""
from __future__ import annotations

from plot import Axis, chart
from svg import Box, flow


def build(D: dict) -> None:
    boxes = [
        Box("rng", ["Канал диапазона", "начало ≤ AUX < конец?"], 10, 14, 165, 44),
        Box("row", ["Строка adjrange", "0…19, функция ≠ 0"], 195, 14, 160, 44),
        Box("slot", ["Слот 0…3 свободен?", "занимает меньший индекс"], 375, 14, 170, 44, accent=True),
        Box("adj", ["Канал подстройки", "самовозвратный тумблер"], 565, 14, 165, 44),
        Box("up", ["> 1700: + шаг", "2 сигнала"], 10, 104, 165, 44),
        Box("dn", ["< 1300: − шаг", "1 сигнал"], 195, 104, 160, 44),
        Box("mid", ["1300…1700: ничего", "слот взведён"], 375, 104, 170, 44),
        Box("rep", ["Удержание: первый шаг", "сразу, повтор 500 мс"], 565, 104, 165, 44),
        Box("ram", ["Значение в RAM, в границах из таблицы", "OSD: число мигает · Blackbox: событие"], 10, 196, 345, 44, accent=True),
        Box("save", ["Запись всего конфига:", "Save стиками, CLI, CMS"], 375, 196, 170, 44, accent=True),
        Box("side", ["…и побочно: stats,", "autotrim, смена профиля"], 565, 196, 165, 44),
    ]
    links = [
        ("rng", "row", "", False, "h"), ("row", "slot", "", False, "h"), ("slot", "adj", "", False, "h"),
        ("adj", "up", "", False, "v"), ("adj", "dn", "", False, "v"), ("adj", "mid", "", False, "v"),
        ("adj", "rep", "", False, "v"),
        ("up", "ram", "", True, "v"), ("dn", "ram", "", True, "v"),
        ("ram", "save", "", True, "h"), ("save", "side", "", False, "h"),
    ]
    D["inav-adjustments-flow"] = flow(
        "Подстройка INAV 9.1: от тумблера до EEPROM",
        boxes, links, 740, 300,
        notes=[(10, 266, "Положение селектора без строки = подстройка выключена.", "m t"),
               (10, 282, "Без записи EEPROM значение живёт до выключения питания.", "w t")])

    # practice step 2, model run (20 ms RX cycle); press at t = 1000 ms
    steps = [(1000, 1410), (1480, 1420), (1980, 1430), (2480, 1440), (2980, 1450), (4000, 1440), (4500, 1430)]
    xs, ys = [0], [1400]
    for t, v in steps:
        xs += [t, t]
        ys += [ys[-1], v]
    xs.append(5500)
    ys.append(ys[-1])
    aux_seg = [(0, 1000, 1500), (1000, 3300, 2000), (3300, 4000, 1500), (4000, 4200, 1000), (4200, 4500, 1500),
               (4500, 4700, 1000), (4700, 5500, 1500)]
    ax, ay = [], []
    for a, b, v in aux_seg:
        ax += [a, b]
        ay += [v, v]
    D["chart-inav-adj-staircase"] = chart(
        "nav_fw_cruise_thr: удержание вверх 2.3 с, затем два нажатия вниз",
        [dict(name="nav_fw_cruise_thr", xs=xs, ys=ys, cls="a", label_at=3500, label_dy=18),
         dict(name="AUX4, мкс", xs=ax, ys=ay, cls="m", axis=2, dash=True, label_at=5000, label_dy=14)],
        Axis("время, мс", 0, 5500), Axis("nav_fw_cruise_thr", 1380, 1460, ticks=[1400, 1410, 1420, 1430, 1440, 1450]),
        y2=Axis("AUX4, мкс", 900, 2100, ticks=[1000, 1300, 1500, 1700, 2000]),
        marks=[(1000, "шаг сразу", "w", 52), (1480, "+480 мс", "w", 68), (1980, "+500 мс", "w", 84)],
        notes=[(72, 304, "n = 1 + ⌊T / 0.5 с⌋ = 5 шагов по 10; нажатие с возвратом в центр — один шаг.", "m")])
