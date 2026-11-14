"""Stage 6 diagrams for module bf-adjustments (Betaflight 4.5 in-flight adjustments, fc/rc_adjustments.c).

bf-adjustments-flow       — range channel -> slot -> function configs[N-1] -> step / absolute / select -> RAM,
                            OSD 2 s, Blackbox event -> saved only by the disarmed stick command.
chart-bf-adj-step-timing  — the module's lab run: adjrange 0 0 1 900 1300 8 3 0 0, two taps then a 1.6 s hold
                            up and a 0.7 s hold down on AUX4; d_roll 40 -> 46 -> 44 (steps at 200, 700, 1200,
                            1690, 2190, 2690 ms up, 3200, 3690 ms down).
"""
from __future__ import annotations

from plot import Axis, chart
from svg import Box, flow


def build(D: dict) -> None:
    boxes = [
        Box("rng", ["Канал диапазона", "AUX2 в start..end?"], 10, 14, 160, 44),
        Box("slot", ["Слот adjrange", "0…29 активен"], 190, 14, 160, 44),
        Box("fn", ["Функция N из CLI", "= configs[N − 1]"], 370, 14, 160, 44, accent=True),
        Box("adj", ["Канал подстройки", "AUX4 / крутилка"], 550, 14, 160, 44),
        Box("step", ["STEP: center = 0", "> 1700 → +1, < 1300 → −1", "повтор 500 мс"], 10, 100, 220, 58),
        Box("abs", ["ABSOLUTE: center ≠ 0", "c + (rc − 1500)·s / 500", "при каждом изменении rc"], 250, 100, 220, 58),
        Box("sel", ["SELECT: 12, 24, 25, 29, 30", "поз. = (rc − 900) / (1200/N)", "профиль рейтов/OSD/LED"], 490, 100, 220, 58),
        Box("ram", ["Значение в RAM", "config dirty"], 10, 200, 160, 44, accent=True),
        Box("osd", ["OSD 2 с", "«PITCH/ROLL D:  41»"], 190, 200, 160, 44),
        Box("bb", ["Blackbox-событие", "код = enum, не CLI"], 370, 200, 160, 44),
        Box("save", ["Сохранить: дизарм,", "T↓ Y← P↓ R→"], 550, 200, 160, 44, accent=True),
    ]
    links = [
        ("rng", "slot", "", False, "h"), ("slot", "fn", "", False, "h"), ("fn", "adj", "", False, "h"),
        ("adj", "step", "", False, "v"), ("adj", "abs", "", False, "v"), ("adj", "sel", "", False, "v"),
        ("abs", "ram", "", True, "v"),
        ("ram", "osd", "", False, "h"), ("osd", "bb", "", False, "h"), ("bb", "save", "", True, "h"),
    ]
    D["bf-adjustments-flow"] = flow(
        "Adjustments в Betaflight 4.5: от тумблера до EEPROM",
        boxes, links, 720, 300,
        notes=[(10, 268, "Без stick-save или Save в Configurator изменение живёт до выключения питания.", "w t"),
               (10, 284, "В режиме CLI подстройки не обрабатываются; при PARALYZE и дизарме — тоже.", "m t")])

    # lab run (bf-adjustments.adj_lab.py, step mode, 10 ms ticks)
    steps_t = [200, 700, 1200, 1690, 2190, 2690, 3200, 3690]
    steps_v = [41, 42, 43, 44, 45, 46, 45, 44]
    xs, ys = [0], [40]
    for t, v in zip(steps_t, steps_v):
        xs += [t, t]
        ys += [ys[-1], v]
    xs.append(4000)
    ys.append(ys[-1])
    aux_seg = [(0, 200, 1500), (200, 400, 2000), (400, 700, 1500), (700, 900, 2000), (900, 1200, 1500),
               (1200, 2800, 2000), (2800, 3200, 1500), (3200, 3900, 1000), (3900, 4000, 1500)]
    ax, ay = [], []
    for a, b, v in aux_seg:
        ax += [a, b]
        ay += [v, v]
    D["chart-bf-adj-step-timing"] = chart(
        "Шаговая подстройка D: два нажатия, удержание вверх 1.6 с, вниз 0.7 с",
        [dict(name="d_roll", xs=xs, ys=ys, cls="a", label_at=2400, label_dy=-8),
         dict(name="AUX4, мкс", xs=ax, ys=ay, cls="m", axis=2, dash=True, label_at=3500, label_dy=14)],
        Axis("время, мс", 0, 4000), Axis("d_roll", 38, 48, ticks=[38, 40, 42, 44, 46, 48]),
        y2=Axis("AUX4, мкс", 900, 2100, ticks=[1000, 1300, 1500, 1700, 2000]),
        marks=[(1200, "удержание: шаг сразу", "w", 52), (1690, "+490 мс", "w", 68), (2190, "+500 мс", "w", 100)],
        notes=[(72, 304, "Тап быстрее удержания: возврат в центр сбрасывает таймер 500 мс.", "m")])
