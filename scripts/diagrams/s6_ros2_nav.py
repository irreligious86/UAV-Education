"""Stage 6 thin-module pass, ros2-nav: Dijkstra object avoidance around an exclusion polygon.

chart-nav-oa-dijkstra-track — ArduCopter 4.7.2 SITL, OA_TYPE = 2, exclusion square N 30..50 m,
E -10..10 m, OA_MARGIN_MAX = 5 m (default), GUIDED target 80 m north. The planned path is computed
here the way AP_OADijkstra builds it (AP_OADijkstra.cpp:420-490): each convex vertex is pushed out
along the corner bisector by OA_MARGIN_MAX, i.e. by 5/sqrt(2) = 3.54 m on each axis for a square.
The measured track is LOCAL_POSITION_NED from the module's practice run (examples/sitl-nav-labs, tag oa,
WP_SPD 5 m/s), decimated to 1 s (path 87.0 m vs 80 m straight, max |E| 13.7 m, min clearance 3.6 m, 31.8 s).
"""
from __future__ import annotations

import math

from plot import Axis, chart

SQUARE = [(30, -10), (30, 10), (50, 10), (50, -10), (30, -10)]          # (N, E), m
MARGIN = 5.0                                                              # OA_MARGIN_MAX default
TRACK = [(-0.0, 0.0), (0.4, 0.2), (1.8, 0.9), (4.5, 2.3), (8.3, 4.3), (12.5, 6.4), (16.8, 8.6), (21.0, 10.7),
         (24.5, 12.5), (26.3, 13.4), (26.8, 13.7), (27.2, 13.7), (28.2, 13.7), (30.4, 13.7), (33.7, 13.7),
         (37.9, 13.7), (42.4, 13.7), (47.0, 13.6), (50.8, 13.6), (53.2, 13.6), (53.9, 13.6), (54.1, 13.4),
         (55.0, 13.0), (56.7, 12.1), (59.6, 10.7), (63.2, 8.8), (67.1, 6.7), (71.3, 4.6), (75.3, 2.5),
         (78.4, 0.8), (80.0, 0.0), (80.3, -0.1)]


def planned() -> list[tuple[float, float]]:
    d = MARGIN / math.sqrt(2)
    return [(0.0, 0.0), (30 - d, 10 + d), (50 + d, 10 + d), (80.0, 0.0)]


def build(D: dict) -> None:
    p = planned()
    length = sum(math.dist(a, b) for a, b in zip(p, p[1:]))
    d = MARGIN / math.sqrt(2)
    grown = [(30 - d, -10 - d), (30 - d, 10 + d), (50 + d, 10 + d), (50 + d, -10 - d), (30 - d, -10 - d)]
    D["chart-nav-oa-dijkstra-track"] = chart(
        "Dijkstra (OA_TYPE = 2) в SITL 4.7.2: облёт запретного квадрата",
        [dict(name="прямая 80 м", xs=[0, 80], ys=[0, 0], cls="m", dash=True, w=1.2, label_at=70, label_dy=-6),
         dict(xs=[q[0] for q in SQUARE], ys=[q[1] for q in SQUARE], cls="d"),
         dict(xs=[q[0] for q in grown], ys=[q[1] for q in grown], cls="w", dash=True, w=1.2),
         dict(xs=[q[0] for q in p], ys=[q[1] for q in p], cls="ink", dash=True, w=1.2),
         dict(xs=[q[0] for q in TRACK], ys=[q[1] for q in TRACK], cls="a")],
        Axis("север N, м", -2, 84, ticks=[0, 10, 20, 30, 40, 50, 60, 70, 80]),
        Axis("восток E, м", -16, 22, ticks=[-15, -10, -5, 0, 5, 10, 15, 20]),
        height=340,
        legend=[("трек SITL: 87.0 м", "a", False), (f"план: {length:.1f} м", "ink", True),
                ("вершины + 5 м", "w", True), ("запрет 20 × 20 м", "d", False)],
        legend_at=(520, 222),
        notes=[(250, 58, f"углы плана смещены на 5/√2 = {d:.2f} м по каждой оси", "m")])
