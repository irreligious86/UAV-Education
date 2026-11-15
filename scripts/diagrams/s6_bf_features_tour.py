"""Stage 6 diagrams for module bf-features-tour (Betaflight 4.5 modes and features).

chart-bf-dyn-idle            — the module's worked example (practice step 2): slowest motor rpm with static idle
                               (dshot_idle_value 5.5 %) and with dynamic idle (dyn_idle_min_rpm 30) on the same
                               synthetic flight: ground idle, climb, throttle chop and flat drop 0.9–1.6 s.
                               Controller copied from flight/mixer.c, gains from flight/mixer_init.c (4.5); the motor
                               model (26000·sqrt(u) rpm, tau 40 ms, 4000 rpm inflow brake) is the module's stand-in.
chart-bf-horizon-strength    — calcHorizonLevelStrength() (flight/pid.c, 4.5 defaults 75/75/135) vs inclination
                               for three stick deflections (practice step 1c).
"""
from __future__ import annotations

import math

from plot import Axis, chart

DT = 1 / 8000


def _pt1(f: float, dt: float) -> float:
    w = 2 * math.pi * f * dt
    return w / (w + 1)


def _scenario(t: float):
    if t < 0.3:
        return 0.0, 0.0, False
    if t < 0.8:
        return 0.35, 0.0, True
    if 0.9 <= t < 1.6:
        return 0.0, 4000.0, True
    return 0.0, 0.0, True


def _idle_trace(dyn: bool):
    """Same loop as the practice script (bf-features-tour.lab.py, part 2b)."""
    min_rps, kp, ki, kd = 3000 / 60, 50 * 0.00015, 50 * 0.01 * DT, 50 * 3e-7 * 8000
    max_inc, start_inc, kdel = 0.150, 0.050, 800 * DT / 20
    k_rpm = _pt1(150, DT)
    rpm_ss = lambda u, inflow: max(0.0, 26000 * math.sqrt(max(u, 0.0)) - inflow)
    rpm = rpm_ss(0.055, 0)
    f = rpm / 60
    prev, i_term = f, 0.0
    ts, rs = [], []
    n, t = 0, 0.0
    while t < 2.0:
        m, inflow, airmode = _scenario(t)
        if dyn:
            cap = max_inc if airmode else start_inc
            err = min_rps - f
            filt = prev + kdel * (f - prev)
            d_term = (prev - filt) * kd
            prev = filt
            p_term = err * kp
            i_term = min(max(i_term + max(-0.1, err) * ki, 0.0), cap)
            inc = min(max(p_term + i_term + d_term, 0.0), cap)
            m = max(m, 0.01)
            u = inc + m * (1 - inc)
        else:
            u = 0.055 + m * (1 - 0.055)
        rpm += (rpm_ss(u, inflow) - rpm) * DT / 0.040
        f += k_rpm * (rpm / 60 - f)
        if n % 40 == 0:
            ts.append(t)
            rs.append(rpm)
        t += DT
        n += 1
    return ts, rs


def _horizon(incl: float, stick: float) -> float:
    s = max((135 - incl) / 135, 0.0)
    s *= max((0.75 - stick) / 0.75, 0.0)
    return s * 0.75


def build(D: dict) -> None:
    ts, static = _idle_trace(False)
    _, dyn = _idle_trace(True)
    D["chart-bf-dyn-idle"] = chart(
        "Dynamic idle держит 3000 об/мин там, где статический idle проваливается",
        [dict(name="dshot_idle_value 5.5 %", xs=ts, ys=static, cls="d", label_at=1.35, label_dy=16),
         dict(name="dyn_idle_min_rpm 30", xs=ts, ys=dyn, cls="a", label_at=1.35, label_dy=-8)],
        Axis("время, с", 0, 2.0), Axis("самый медленный мотор, об/мин", 0, 17000),
        bands=[(0.9, 1.6, "сброс газа, плоское падение")],
        hmarks=[(3000, "", "a")],
        marks=[(0.3, "", "m"), (0.8, "", "m")],
        notes=[(116, 150, "взлёт →", "m"), (212, 150, "газ в ноль →", "m"), (585, 284, "цель 3000 об/мин", "a")])

    xs = [float(a) for a in range(0, 181, 3)]
    D["chart-bf-horizon-strength"] = chart(
        "Horizon 4.5: сила выравнивания от наклона и стика",
        [dict(name="стик 0", xs=xs, ys=[_horizon(a, 0.0) for a in xs], cls="a", label_at=20, label_dy=-6,
              label_anchor="start"),
         dict(name="стик 25 %", xs=xs, ys=[_horizon(a, 0.25) for a in xs], cls="w", label_at=20, label_dy=-6,
              label_anchor="start"),
         dict(name="стик 50 %", xs=xs, ys=[_horizon(a, 0.5) for a in xs], cls="d", label_at=20, label_dy=-6,
              label_anchor="start")],
        Axis("наклон (max |крен|, |тангаж|), °", 0, 180, ticks=[0, 30, 60, 90, 135, 180]),
        Axis("сила выравнивания (1 = Angle)", 0, 1.0),
        marks=[(135, "limit_degrees", "m", 170)],
        hmarks=[(0.75, "level_strength 75", "m")])
