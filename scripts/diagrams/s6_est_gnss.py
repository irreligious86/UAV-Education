"""Stage 6 thin-module pass, est-gnss: what a wall does to the number of satellites and to HDOP.

chart-gnss-hdop-wall — the module's 10-satellite sky (same azimuth/elevation list as the practice
script gnss_lab). A wall blocks an azimuth sector of width W centred on 180 deg (south). For each W the
script counts the remaining satellites and computes HDOP = sqrt(Q11 + Q22), Q = (G^T G)^-1, rows of G
= [-e_E, -e_N, -e_U, 1]. Worked example: W = 180 deg -> 6 satellites, HDOP 3.48 (practice output).
Horizontal lines: GPS_HDOP_GOOD = 1.4 (Copter pre-arm) and 2.5 (EKF3 check, EK3_GPS_CHECK bit 1).
"""
from __future__ import annotations

import math

from plot import Axis, chart

SKY = [(0, 75), (40, 30), (85, 50), (130, 20), (175, 60), (220, 35), (260, 15), (300, 45), (335, 25), (20, 10)]


def _inv(a: list[list[float]]) -> list[list[float]] | None:
    n = len(a)
    m = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        if abs(m[p][c]) < 1e-12:
            return None
        m[c], m[p] = m[p], m[c]
        piv = m[c][c]
        m[c] = [v / piv for v in m[c]]
        for r in range(n):
            if r != c:
                f = m[r][c]
                m[r] = [v - f * w for v, w in zip(m[r], m[c])]
    return [row[n:] for row in m]


def hdop(sats) -> float | None:
    if len(sats) < 4:
        return None
    rows = []
    for az, el in sats:
        a, e = math.radians(az), math.radians(el)
        rows.append([-math.cos(e) * math.sin(a), -math.cos(e) * math.cos(a), -math.sin(e), 1.0])
    gtg = [[sum(r[i] * r[j] for r in rows) for j in range(4)] for i in range(4)]
    q = _inv(gtg)
    return math.sqrt(q[0][0] + q[1][1]) if q else None


def visible(width: float):
    return [s for s in SKY if abs(((s[0] - 180) + 180) % 360 - 180) > width / 2]


def build(D: dict) -> None:
    ws = list(range(0, 301, 10))
    hs = [hdop(visible(w)) for w in ws]
    ns = [len(visible(w)) for w in ws]
    h180, n180 = hdop(visible(180)), len(visible(180))
    D["chart-gnss-hdop-wall"] = chart(
        "Стена закрывает сектор неба: спутников чуть меньше, HDOP кратно хуже",
        [dict(name="HDOP", xs=ws, ys=[h if h and h <= 10 else None for h in hs], cls="d", label_at=210, label_dy=-8),
         dict(name="спутников", xs=ws, ys=ns, cls="a", axis=2, label_at=130, label_dy=-8)],
        Axis("ширина закрытого сектора (центр — юг), °", 0, 300, ticks=[0, 60, 120, 180, 240, 300]),
        Axis("HDOP", 0, 10, ticks=[0, 1.4, 2.5, 5, 7.5, 10]),
        y2=Axis("спутников", 0, 10, ticks=[0, 2, 4, 6, 8, 10]),
        marks=[(180, f"стена 180°: {n180} спутн., HDOP {h180:.2f}", "ink", 60)],
        hmarks=[(1.4, "GPS_HDOP_GOOD 1.4", "a"), (2.5, "EKF3: 2.5", "w")])
