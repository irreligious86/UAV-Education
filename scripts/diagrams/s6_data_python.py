"""Stage 6 (thin-module pass) diagram for module data-python.

chart-dpy-sitl-roll-step — one real roll-rate step from the module's lab log (ArduCopter 4.7.2 SITL, ACRO, stick
                           +0.4 for 0.5 s; RATE message at 400 Hz). RDes (target, ramp-limited by ATC_ACC_R_MAX =
                           1100 deg/s^2) and R (measured) every 4th sample (10 ms), copied from the lab output;
                           marks are the step_metrics() values printed for this step (t = 62.1 s): lag 30.0 ms,
                           rise 10-90 % = 120.0 ms, settle into +-5 % = 202.4 ms, overshoot 0 %.
"""
from __future__ import annotations

from plot import Axis, chart

# RATE.RDes / RATE.R, deg/s, t = 0, 10, 20 ... ms from the quiet start of the step (lab log, t0 = 62.067 s)
_SP = [0.8, 5.9, 15.6, 27.1, 38.7, 50.3, 62.0, 73.8, 85.7, 95.2, 101.6, 106.0, 108.8, 110.9, 112.3, 113.2, 113.8,
       114.2, 114.4, 114.5, 114.6, 114.5, 114.5, 114.4, 114.3, 113.7, 113.6, 113.5, 113.3, 113.2, 113.1, 112.9, 112.8,
       112.7, 112.5, 112.4, 112.3, 112.1, 112.0, 111.9, 111.7, 111.7, 111.6, 111.4, 111.4, 111.3, 111.2, 111.1, 111.0,
       110.9, 110.9, 109.1, 102.9, 92.3, 80.7, 69.1, 57.5, 45.6, 33.8, 22.2, 13.4, 7.6]
_GY = [0.2, 0.1, 0.7, 4.1, 10.9, 20.6, 31.1, 40.3, 49.4, 59.8, 70.4, 80.0, 87.2, 91.6, 95.0, 98.4, 101.1, 103.2,
       104.7, 105.5, 106.6, 107.8, 108.1, 108.5, 109.0, 109.1, 109.5, 109.7, 109.5, 109.6, 109.8, 109.5, 109.6, 109.7,
       109.4, 109.5, 109.5, 109.2, 109.3, 109.3, 109.0, 109.1, 108.9, 108.6, 108.7, 108.7, 108.4, 108.5, 108.4, 108.1,
       108.3, 108.2, 107.8, 106.8, 102.7, 94.6, 84.7, 74.7, 65.4, 56.3, 45.8, 35.0]
_LAG, _RISE, _SETTLE = 30.0, 120.0, 202.4      # step_metrics() output for this step
_BASE, _STEP = 0.8, 112.0                       # base and step size printed by step_metrics (target ~ 112.8)


def _cross(ts, ys, level):
    """First time the series reaches `level`, linear interpolation between 10 ms samples."""
    for k in range(1, len(ys)):
        if ys[k] >= level:
            return ts[k - 1] + (level - ys[k - 1]) / (ys[k] - ys[k - 1]) * (ts[k] - ts[k - 1])
    return ts[-1]


def build(D: dict) -> None:
    ts = [10 * k for k in range(len(_SP))]
    half = _BASE + 0.5 * _STEP
    t_sp = _cross(ts, _SP, half)        # the R crossing is t_sp + lag (step_metrics works on 2.5 ms samples)
    target = _BASE + _STEP
    lo, hi = _BASE + 0.95 * _STEP, _BASE + 1.05 * _STEP
    D["chart-dpy-sitl-roll-step"] = chart(
        "Ступенька крена в логе ArduCopter 4.7.2 SITL (RATE, 400 Гц)",
        [dict(name="цель RDes", xs=ts, ys=_SP, cls="ink", dash=True, label_at=150, label_dy=-8),
         dict(name="отклик R", xs=ts, ys=_GY, cls="a", label_at=330, label_dy=16),
         dict(xs=[0, 610], ys=[lo, lo], cls="m", w=1),
         dict(xs=[0, 610], ys=[hi, hi], cls="m", w=1)],
        x=Axis("время от начала ступеньки, мс", 0, 600, ticks=[0, 100, 200, 300, 400, 500, 600]),
        y=Axis("скорость крена, °/с", 0, 130, ticks=[0, 20, 40, 60, 80, 100, 120]),
        marks=[(t_sp, "цель 50 %", "m", 200), (t_sp + _LAG, f"отклик 50 %: +{_LAG:.0f} мс", "a", 222),
               (_SETTLE, f"в ±5 % с {_SETTLE:.0f} мс", "a", 160)],
        bands=[(500, 600, "стик отпущен")],
        notes=[(330, 250, f"нарастание 10→90 %: {_RISE:.0f} мс, перелёта нет", "a"),
               (330, 266, f"коридор ±5 %: {lo:.1f}…{hi:.1f} °/с вокруг {target:.1f}", "m")])
