"""Stage 6 diagrams for module inav-geozones-landing (INAV geozones, safehome, trackback, FW autoland).

chart-inav-autoland-top     — top view of the autoland pattern built by navigation.c for the module's worked
                              example: fwapproach <i> 5000 0 1 270 -180 0, nav_fw_land_approach_length = 40000,
                              nav_fw_loiter_radius = 7500, wind from 120 deg at 5 m/s -> landing heading 90 deg.
chart-inav-autoland-profile — commanded altitude along base leg and final approach for the same example.

Geometry repeats navOnEnteringState_NAV_STATE_FW_LANDING_LOITER / _APPROACH (INAV 9.1.0):
  finalApproachAlt = approachAlt / 3 * 2 (integer), WP_LAND = landPos + L along landing heading at
  z = landAlt - finalApproachAlt, WP_FINAL_APPROACH = landPos - L at z = finalApproachAlt,
  WP_TURN = WP_FINAL_APPROACH + max(4 * loiter_radius, L / 2) sideways at z = approachAlt;
  the altitude target of a leg goes linearly from the altitude at the leg start to the waypoint altitude
  and reaches it when 10 % of the leg distance is left.
"""
from __future__ import annotations

import math

from plot import Axis, chart

APPROACH_ALT = 5000      # cm
LAND_ALT = 0             # cm
L = 40000                # nav_fw_land_approach_length, cm
LOITER = 7500            # nav_fw_loiter_radius, cm
GLIDE_ALT = 200          # nav_fw_land_glide_alt, cm
FLARE_ALT = 150          # nav_fw_land_flare_alt, cm


def build(D: dict) -> None:
    fa = APPROACH_ALT // 3 * 2                      # 3332 cm
    turn_dist = max(4 * LOITER, L // 2)             # 30000 cm
    # local metres, landing point at (N 0, E 0), landing heading 90 deg (east), turn point to the north
    faf = (0.0, -L / 100)
    land = (0.0, L / 100)
    turn = (turn_dist / 100, -L / 100)

    ang = [math.radians(a) for a in range(0, 361, 5)]
    circle_e = [LOITER / 100 * math.sin(a) for a in ang]
    circle_n = [LOITER / 100 * math.cos(a) for a in ang]
    start = (LOITER / 100 * math.cos(math.radians(300)), LOITER / 100 * math.sin(math.radians(300)))  # N, E

    D["chart-inav-autoland-top"] = chart(
        "Автопосадка крыла, вид сверху: L = 400 м, посадочный курс 90°, заход RIGHT",
        [
            dict(xs=circle_e, ys=circle_n, cls="m"),
            dict(xs=[start[1], turn[1]], ys=[start[0], turn[0]], cls="a"),
            dict(xs=[turn[1], faf[1]], ys=[turn[0], faf[0]], cls="w"),
            dict(xs=[faf[1], land[1]], ys=[faf[0], land[0]], cls="d"),
            dict(xs=[turn[1], faf[1], 0, land[1]], ys=[turn[0], faf[0], 0, land[0]], cls="ink", dots=True),
        ],
        Axis("восток от точки посадки, м", -500, 500), Axis("север, м", -70, 367),
        notes=[(136, 70, "WP_TURN (300; −400), z = 50 м", ""),
               (250, 160, "1. downwind: высота 50 м", "a"),
               (136, 200, "2. base: 50 → 33.3 м", "w"),
               (136, 258, "3. final → glide → flare, курс 90°", "d"),
               (70, 290, "WP_FINAL_APPROACH (0; −400), z = 33.3 м", ""),
               (436, 240, "круг, R = 75 м", "m"),
               (340, 290, "safehome (0; 0)", ""),
               (500, 290, "WP_LAND (0; +400), z = −33.3 м", ""),
               (470, 70, "ветер 5 м/с дует с 120° (с ESE)", "m")])

    # altitude profile: x = distance from WP_FINAL_APPROACH along the track, negative on the base leg
    slope = (fa - (LAND_ALT - fa)) / (0.9 * 2 * L)          # 0.09256
    xs_base = [-turn_dist / 100, -0.1 * turn_dist / 100, 0]
    ys_base = [APPROACH_ALT / 100, fa / 100, fa / 100]
    x_ground = (fa - LAND_ALT) / slope / 100                # 360 m
    x_glide = (fa - LAND_ALT - GLIDE_ALT) / slope / 100     # 338.4 m
    xs_final = [0, x_glide]
    ys_final = [fa / 100, (LAND_ALT + GLIDE_ALT) / 100]
    xs_cmd = [x_glide, x_ground, 0.9 * 2 * L / 100]
    ys_cmd = [GLIDE_ALT / 100, 0, (LAND_ALT - fa) / 100]
    D["chart-inav-autoland-profile"] = chart(
        "Заданная высота на заходе: approach 50 м, final с 33.3 м, наклон 5.3°",
        [
            dict(xs=xs_base, ys=ys_base, cls="w"),
            dict(xs=xs_final, ys=ys_final, cls="d"),
            dict(xs=xs_cmd, ys=ys_cmd, cls="m", dash=True),
        ],
        Axis("путь от WP_FINAL_APPROACH, м (отрицательные — base leg)", -300, 450),
        Axis("высота над точкой посадки, м", -10, 55),
        marks=[(0, "WP_FINAL_APPROACH", "ink", 14), (x_glide, "", "a", 28), (L / 100, "", "ink", 46)],
        hmarks=[(0, "", "m")],
        notes=[(150, 76, "base: 50 → 33.3 м за 270 м", "w"),
               (400, 150, "final: 9.26 м на 100 м (5.3°)", "d"),
               (470, 56, "glide 2 м: 338 м от FAF", "a"),
               (500, 76, "safehome: 400 м", ""),
               (70, 262, "земля (land alt = 0)", "m"),
               (326, 286, "Пунктир: цель уходит под землю в 360 м от FAF,", "m"),
               (326, 300, "мотор выключается за 62 м до safehome.", "m")])
