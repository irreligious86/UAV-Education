"""Diagrams for module ap-ahrs-choice (EKF3, EKF2 or DCM in ArduPilot 4.7.2).

ahrs-choice-tree          the module's selection rule: vehicle -> where position and yaw come from -> AHRS_EKF_TYPE
                          and EK3_SRCn_* set; leaves = the rows of the selection table (GPS copter, bad compass,
                          no GPS / VIO, plane or VTOL with and without airspeed sensor, 1 MB flash board without
                          ExternalNav / VisualOdom / MAVLink GPS).
ahrs-ekf-trouble-tree     the module's "EKF misbehaves" decision tree: what the pilot sees (PreArm AHRS, "EKF variance",
                          lane switch, "AHRS: DCM active") -> which XKF4 field / SS bit to open -> the fix; the
                          "all variances ~0" branch is the SITL GPS-loss case of practice step 3 (flags 0x033f -> 0x0025).
chart-ahrs-deadreckon     practice step 7, ArduPlane 4.7.2 SITL: EKF3 position error against truth after
                          SIM_GPS1_ENABLE = 0 in LOITER at 50 m, wind 8 m/s (7.3 m/s at 50 m by the SITL square-root
                          profile), with ARSPD_USE = 1 and ARSPD_USE = 0 (poserr.py samples every 5 s, copied from the
                          module text); the dashed line is the module's estimate e = dw * t with dw = 7.3 - 7.1 = 0.2 m/s.
"""
from __future__ import annotations

import math

from plot import Axis, chart
from svg import Node, tree, text


def _add_footer(svg_str: str, lines: list[str], lh: int = 16) -> str:
    """Grow a tree() SVG downwards and add muted footnote lines under it."""
    import re
    m = re.search(r'viewBox="0 0 (\d+(?:\.\d+)?) (\d+(?:\.\d+)?)"', svg_str)
    w, h = float(m.group(1)), float(m.group(2))
    nh = h + lh * len(lines) + 6
    body = "".join(text(16, h + 4 + lh * (i + 1) - 4, s, "m t", "start") for i, s in enumerate(lines))
    svg_str = svg_str.replace(m.group(0), f'viewBox="0 0 {w:g} {nh:g}"', 1)
    i = svg_str.rfind("</svg>")
    return svg_str[:i] + body + svg_str[i:]


# ---------------------------------------------------------------- selection rule
def choice_tree() -> str:
    t = tree("Какой оценщик и какие источники: правило выбора", Node("veh", ["Что за аппарат", "и сколько флеша?"], [
        ("коптер", Node("cop", ["Откуда позиция", "и курс?"], [
            ("GPS+компас", Node("std", ["EKF3, SRC1:", "3/3/1/3/1", "(умолчания)"], leaf=True, accent=True)),
            ("компас плох", Node("gsf", ["EKF3, YAW = 8", "(GSF) или 2/3", "при 2 антеннах"], leaf=True)),
            ("нет GPS", Node("nogps", ["EKF3: поток 5,", "маяки 4, VIO 6;", "запас в SRC2"], leaf=True)),
        ], accent=True)),
        ("самолёт/VTOL", Node("pl", ["Есть датчик", "скорости?"], [
            ("да", Node("asp", ["EKF3 + ARSPD:", "ветер, счисление", "12 м за 60 с"], leaf=True, accent=True)),
            ("нет", Node("noasp", ["EKF3, без GPS", "96 м за 60 с;", "DCM — запасной"], leaf=True)),
        ])),
        ("плата 1 МБ", Node("f405", ["EKF3: GPS, поток,", "GSF; ExtNav и", "VIO вырезаны"], leaf=True)),
    ]), width=720, box_w=112, box_h=50, gap_y=84)
    return _add_footer(t, [
        "SRC1 = POSXY/VELXY/POSZ/VELZ/YAW; в 4.7 EKF2 — только SITL/custom, маяки (4) — флеш > 2 МБ",
        "AHRS_EKF_TYPE = 3 везде; 0 (DCM) законен только у Plane/Rover — коптер с ним не армится"])


# ---------------------------------------------------------------- misbehaving EKF
def trouble_tree() -> str:
    t = tree("EKF ведёт себя плохо: от сообщения к причине", Node("see", ["Что видно", "в GCS?"], [
        ("PreArm AHRS", Node("pre", ["строка PreArm:", "AHRS_EKF_TYPE,", "EK3_ENABLE, GPS"], leaf=True)),
        ("EKF variance", Node("var", ["XKF4: что", "выше 0.8?"], [
            ("SM", Node("sm", ["компас: ток,", "калибровка,", "YAW 3 или 8"], leaf=True)),
            ("SV/SP", Node("sp", ["GPS: NSats,", "HAcc, глитч,", "задержка"], leaf=True)),
            ("всё ≈ 0", Node("nopos", ["SS без бит 3/4:", "источник позиции", "пропал"], leaf=True, accent=True)),
        ], accent=True)),
        ("lane switch", Node("lane", ["сравни C=0/1:", "IMU, вибрации,", "клиппинг"], leaf=True)),
        ("DCM", Node("dcm", ["Plane: EKF3 без", "позиции/нездоров;", "DCM идёт по GPS"], leaf=True)),
    ]), width=720, box_w=112, box_h=50, gap_y=84)
    return _add_footer(t, [
        "Порог FS_EKF_THRESH не поднимать: 0.8 при воротах 500 — это уже 4σ",
        "SITL: GPS выключен в Loiter — все вариации 0.01, а Land через 8 с (флаги 0x033f -> 0x0025)"])


# ---------------------------------------------------------------- dead reckoning without GPS (Plane SITL)
T = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60]
ERR_ASPD = [1.0, 1.4, 1.1, 2.2, 5.6, 6.5, 6.9, 6.3, 4.7, 7.8, 11.3, 11.8, 11.5]      # run_wind, 110 ... 170 s
ERR_NOASPD = [1.0, 1.3, 2.0, 17.7, 23.5, 29.9, 39.7, 46.5, 61.6, 75.0, 78.9, 87.2, 96.3]  # run_noarspd_wind


def deadreckon() -> str:
    w_true = 8 * math.sqrt(50 / 60)          # SITL wind 8 m/s, square-root profile to 60 m, flight at 50 m
    w_est = 7.1                              # XKF2.VWE with airspeed sensor
    dw = round(w_true - w_est, 1)            # 0.2 m/s
    assert abs(w_true - 7.30) < 0.01 and abs(dw - 0.2) < 1e-9
    xs = [0.5 * i for i in range(121)]
    return chart(
        "Самолёт без GPS в ветре 7.3 м/с: ошибка позиции EKF3",
        [dict(name="ARSPD_USE = 0", xs=T, ys=ERR_NOASPD, cls="d", label_at=40, label_dy=-10, label_anchor="end"),
         dict(name="ARSPD_USE = 1", xs=T, ys=ERR_ASPD, cls="a", label_at=60, label_dy=-12, label_anchor="end"),
         dict(xs=xs, ys=[dw * x for x in xs], cls="m", dash=True)],
        Axis("время после SIM_GPS1_ENABLE = 0, с", 0, 60, ticks=[0, 10, 20, 30, 40, 50, 60]),
        Axis("ошибка позиции к истине, м", 0, 100, ticks=[0, 20, 40, 60, 80, 100]),
        notes=[(76, 70, "ArduPlane 4.7.2 SITL, LOITER на 50 м; к 60-й секунде 11.5 и 96.3 м", "m"),
               (76, 88, f"пунктир — оценка Δw·t при Δw = {dw:.1f} м/с (ветер 7.3, оценка EKF 7.1)", "m")])


def build(D: dict) -> None:
    D["ahrs-choice-tree"] = choice_tree()
    D["ahrs-ekf-trouble-tree"] = trouble_tree()
    D["chart-ahrs-deadreckon"] = deadreckon()
