"""Stage 6 diagrams for ap-sensors (ArduPilot 4.7.2: compass calibration, battery monitors).

ap-sensors-compass-flow — which compass calibration method to use (svg.tree). Branches follow the module's
                          decision table; thresholds are the ones quoted in the theory (COMPASS_CAL_FIT,
                          CompassMot 30 %, MagFit 10 deg).
ap-sensors-batt-sum     — battery monitor instances of practice step 3 feeding GCS / OSD / compass
                          compensation and the per-instance failsafe (svg.flow). Numbers come from the worked
                          example: two 6S 10 Ah packs, sum mask 6, capacity 20000, LOW_MAH 5000.
"""
from __future__ import annotations

from svg import Box, Node, flow, tree

# worked example of practice step 3
PACK_MAH = 10000
SUM_MONITORS = (2, 3)                       # monitors included in the sum
SUM_MASK = sum(1 << (n - 1) for n in SUM_MONITORS)
CAPACITY = PACK_MAH * len(SUM_MONITORS)
LOW_MAH = 5000


def _compass() -> str:
    root = Node("q1", ["Аппарат можно вращать", "в руках всеми сторонами?"], [
        ("да", Node("rot", ["Калибровка вращением", "fitness ≤ COMPASS_CAL_FIT"], [
            ("", Node("q2", ["Поле меняется", "с током (MAG и BAT.Curr)?"], [
                ("нет", Node("ok", ["Готово: проверить", "|OFS|, |B|, XKF4.SM"], leaf=True)),
                ("да", Node("mot", ["Разнести компас и провода,", "остаток: CompassMot / MagFit"], accent=True, leaf=True)),
            ])),
        ])),
        ("нет", Node("lv", ["COMPASS_ORIENT вручную,", "Large Vehicle MagCal"], [
            ("", Node("fly", ["Первый полёт", "без удержания позиции"], [
                ("", Node("mf", ["MagFit по логу:", "отклонение курса < 10°"], accent=True, leaf=True)),
            ])),
        ])),
    ])
    return tree("Компас в ArduPilot 4.7: какой способ калибровки выбрать", root, width=720, box_w=190, box_h=42, gap_y=74)


def _batt() -> str:
    assert SUM_MASK == 6 and CAPACITY == 20000
    bw, bh = 150, 50
    boxes = [
        Box("b2", ["BATT2: тип 4", "АКБ A, 6S 10 А·ч"], 14, 50, bw, bh),
        Box("b3", ["BATT3: тип 4", "АКБ B, 6S 10 А·ч"], 14, 130, bw, bh),
        Box("b4", ["BATT4: тип 3", "авионика 3S"], 14, 230, bw, bh),
        Box("sum", ["BATT: тип 10 (сумма)", f"BATT_SUM_MASK = {SUM_MASK}"], 216, 90, 170, bh, accent=True),
        Box("use", ["SYS_STATUS, OSD,", "COMPASS_MOTCT = 2"], 440, 40, 170, bh),
        Box("fs1", ["Failsafe монитора 1", f"остаток < {LOW_MAH} из {CAPACITY}"], 440, 130, 170, bh, accent=True),
        Box("fs4", ["Failsafe монитора 4", "BATT4_LOW_VOLT"], 440, 230, 170, bh, accent=True),
    ]
    links = [
        ("b2", "sum", "I, мА·ч", False, "h"),
        ("b3", "sum", "", False, "h"),
        ("sum", "use", "", False, "h"),
        ("sum", "fs1", "", True, "h"),
        ("b4", "fs4", "только V", True, "h"),
    ]
    notes = [
        (14, 300, "Сумма: ток и мА·ч складываются, напряжение усредняется.", "m t"),
        (14, 316, "Маска 6 = биты 1 и 2 = мониторы 2 и 3. Маска 0 у монитора 1 добавила бы авионику в среднее напряжение.", "m t"),
        (14, 332, "Пороги и действие BATTn_FS_*_ACT проверяются у каждого монитора отдельно и только в арме.", "m t"),
    ]
    return flow("Несколько АКБ: сумма первым монитором, failsafe у каждого свой", boxes, links, 720, 344, notes)


def build(D: dict) -> None:
    D["ap-sensors-compass-flow"] = _compass()
    D["ap-sensors-batt-sum"] = _batt()
