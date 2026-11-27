"""Stage 6 thin-module pass, per-visual-nav: what three VIO failures do to ArduCopter 4.7.2 EKF3.

chart-vio-fault-gap — horizontal gap |EKF estimate - SITL truth| per second, LOITER hover at 3 m,
ExternalNav only (VISION_POSITION_ESTIMATE 30 Hz, 50 ms lag, 2 cm noise), wind 3 m/s. The fault starts
at t = 0 and lasts 20 s. Series are the "gap" column of the module's practice runs
(examples/sitl-nav-labs/vio_fault_feed.py via run_lab.sh, tags freeze / stop / jump):
  freeze - the last pose is re-sent with fresh timestamps: ratio <= 0.01, gap 6.3 m at the end of the fault;
           afterwards the true poses are rejected (ratio 4.7) until EKF resets onto them at +27.3 s;
  stop   - no messages: EKF failsafe -> LAND at +7.9 s, touchdown at +18.4 s, gap 4.9 m;
  jump   - +5 m north: rejected (ratio 3.4) for ~4.5 s, then accepted: the estimate follows the source.
"""
from __future__ import annotations

from plot import Axis, chart

FREEZE_T = [-10.0, -9.0, -8.0, -7.0, -6.0, -4.9, -3.9, -2.9, -1.9, -0.9, 0.1, 1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 7.2, 8.2, 9.2, 10.2, 11.2, 12.2, 13.2, 14.2, 15.2, 16.2, 17.3, 18.3, 19.3, 20.3, 21.3, 22.3, 23.3, 24.3, 25.3, 26.3, 27.3, 28.4, 29.4, 30.4, 31.4, 32.4, 33.4, 34.4]
FREEZE = [0.0, 0.0, 0.01, 0.02, 0.01, 0.01, 0.01, 0.0, 0.03, 0.02, 0.02, 0.01, 0.04, 0.09, 0.16, 0.26, 0.39, 0.55, 0.75, 0.99, 1.26, 1.59, 1.96, 2.38, 2.87, 3.43, 4.03, 4.71, 5.45, 6.27, 7.15, 8.08, 9.07, 10.14, 11.24, 12.42, 13.68, 0.26, 0.07, 0.06, 0.04, 0.02, 0.02, 0.01, 0.01]
STOP_T = [-10.0, -9.0, -8.0, -7.0, -6.0, -5.0, -3.9, -2.9, -1.9, -0.9, 0.1, 1.1, 2.1, 3.1, 4.1, 5.1, 6.2, 7.2, 8.2, 9.2, 10.2, 11.2, 12.2, 13.2, 14.2, 15.2, 16.3, 17.3, 18.3, 19.3, 20.3, 21.3, 22.3, 23.3, 24.3, 25.4, 26.4, 27.4, 28.4, 29.4, 30.4, 31.4, 32.4, 33.5, 34.5]
STOP = [0.0, 0.0, 0.01, 0.02, 0.01, 0.01, 0.01, 0.01, 0.04, 0.02, 0.02, 0.03, 0.05, 0.06, 0.11, 0.17, 0.27, 0.38, 0.54, 0.73, 0.97, 1.25, 1.59, 1.97, 2.45, 2.98, 3.58, 4.2, 4.83, 4.87, 0.01, 0.0, 0.02, 0.01, 0.01, 0.0, 0.0, 0.01, 0.01, 0.01, 0.02, 0.01, 0.01, 0.01, 0.01]
JUMP_T = [-10.0, -9.0, -8.0, -7.0, -6.0, -4.9, -3.9, -2.9, -1.9, -0.9, 0.1, 1.1, 2.1, 3.2, 4.2, 5.2, 6.2, 7.2, 8.2, 9.3, 10.3, 11.3, 12.3, 13.3, 14.3, 15.3, 16.4, 17.4, 18.4, 19.4, 20.4, 21.4, 22.4, 23.5, 24.5, 25.5, 26.5, 27.5, 28.5, 29.5, 30.6, 31.6, 32.6, 33.6, 34.6]
JUMP = [0.01, 0.0, 0.01, 0.02, 0.01, 0.01, 0.0, 0.0, 0.03, 0.02, 0.02, 0.04, 0.06, 0.08, 0.14, 5.97, 5.97, 5.12, 4.69, 4.71, 4.89, 5.01, 5.02, 5.01, 5.0, 4.99, 5.0, 5.01, 5.01, 5.01, 4.99, 4.96, 4.9, 4.84, 2.82, 1.58, 0.66, 0.09, 0.32, 0.23, 0.05, 0.03, 0.02, 0.03, 0.01]


def build(D: dict) -> None:
    D["chart-vio-fault-gap"] = chart(
        "Отказы VIO в SITL 4.7.2: расхождение оценки EKF с истиной",
        [dict(xs=FREEZE_T, ys=FREEZE, cls="d"), dict(xs=JUMP_T, ys=JUMP, cls="w"), dict(xs=STOP_T, ys=STOP, cls="a")],
        Axis("время от начала отказа, с", -10, 35, ticks=[-10, -5, 0, 5, 10, 15, 20, 25, 30, 35]),
        Axis("|оценка − истина|, м", 0, 15, ticks=[0, 5, 10, 15]),
        bands=[(0, 20, "отказ 20 с")],
        marks=[(27.3, "сброс EKF", "m", 44)],
        legend=[("поза замёрзла: 6.3 м за 20 с, SP ≤ 0.01", "d", False),
                ("скачок +5 м: отброшен ~4.5 с, затем принят", "w", False),
                ("публикация остановлена: LAND через 7.9 с", "a", False)],
        legend_at=(80, 66))
