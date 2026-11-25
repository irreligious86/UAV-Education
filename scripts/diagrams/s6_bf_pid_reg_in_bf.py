"""Stage 6 diagrams for module bf-pid-reg-in-bf (throttle path of Betaflight 4.5.3: thrust_linear, TPA).

chart-bf-thrust-linear — pidApplyThrustLinearization() (flight/pid.c:338-342 in 4.5.3): motor output
                         x·(1 + k·(1 − x)²) for thrust_linear 0 / 20 / 40; slope 1 + k at zero,
                         back to 1 at x = 1/3 and below 1 above it (the module's throttle lab, part 1).
chart-bf-tpa-factor    — pidUpdateTpaFactor() (flight/pid.c:280-296) with pid_init.c:427-434: TPA multiplier vs
                         rc throttle for the defaults 65 / 1350 and tpa_low 20 / 1050 (before the first pass of the
                         low breakpoint), and for tpa_rate 80 / tpa_breakpoint 1250 (the module's practice step 6).
"""
from __future__ import annotations

from plot import Axis, chart


def _tl(x: float, k: float) -> float:
    return x * (1.0 + k * (1.0 - x) ** 2)


def _tpa(thr: float, rate=65, bp=1350, low_rate=20, low_bp=1050, low_faded=True) -> float:
    t = min(max((thr - 1000) / 1000.0, 0.0), 1.0)
    tbp = min(max((bp - 1000) / 1000.0, 0.0), 0.99)
    mult = (rate / 100.0) / (1.0 - tbp)
    lbp = min(min(max((low_bp - 1000) / 1000.0, 0.01), 1.0), tbp)
    lmult = low_rate / (100.0 * lbp)
    past_low = not (t < lbp and lbp > 0.01)
    r = mult * max(t - tbp, 0.0) if (past_low or low_faded) else lmult * (lbp - t)
    return 1.0 - r


def build(D: dict) -> None:
    xs = [i / 100 for i in range(101)]
    D["chart-bf-thrust-linear"] = chart(
        "thrust_linear: команда мотору = x·(1 + k·(1 − x)²)",
        [dict(name="0 (выкл.)", xs=xs, ys=[_tl(x, 0) for x in xs], cls="ink", dash=True,
              label_at=0.88, label_dy=18, label_anchor="start"),
         dict(name="20", xs=xs, ys=[_tl(x, 0.2) for x in xs], cls="a", label_at=0.16, label_dy=-8),
         dict(name="40", xs=xs, ys=[_tl(x, 0.4) for x in xs], cls="w", label_at=0.10, label_dy=-10)],
        Axis("x = газ + поправка PID, доля диапазона", 0, 1, ticks=[0, 0.2, 1 / 3, 0.6, 0.8, 1.0],
             fmt="{:.2f}"),
        Axis("выход на мотор, доля диапазона", 0, 1, ticks=[0, 0.2, 0.4, 0.6, 0.8, 1.0]),
        marks=[(1 / 3, "x = 1/3: наклон снова 1", "m", 230)],
        notes=[(440, 236, "у нуля наклон 1 + k: 1.2 и 1.4", "a"),
               (440, 254, "выше 1/3 наклон < 1 (при 40: до 0.87)", "w"),
               (440, 272, "x = 0.10 → 0.116 и 0.132", "m")])

    thr = list(range(1000, 2001, 5))
    low = [t for t in thr if t <= 1050]
    D["chart-bf-tpa-factor"] = chart(
        "TPA: множитель D (и P при tpa_mode = PD) от газа",
        [dict(name="умолчание 65 / 1350", xs=thr, ys=[_tpa(t) for t in thr], cls="a",
              label_at=1700, label_dy=-10, label_anchor="start"),
         dict(name="tpa_low до 1-го прохода 1050", xs=low, ys=[_tpa(t, low_faded=False) for t in low],
              cls="w", label_at=1010, label_dy=62, label_anchor="start"),
         dict(name="80 / 1250", xs=thr, ys=[_tpa(t, 80, 1250) for t in thr], cls="d", dash=True,
              label_at=1880, label_dy=24, label_anchor="end")],
        Axis("газ (rcCommand), мкс", 1000, 2000, ticks=[1000, 1050, 1250, 1350, 1500, 1750, 2000]),
        Axis("множитель", 0, 1.1, ticks=[0, 0.2, 0.35, 0.6, 0.8, 1.0]),
        marks=[(1350, "1350", "a", 236), (1050, "1050", "w", 236)],
        notes=[(400, 286, "полный газ: 0.35 (умолч.) и 0.20 (80/1250)", "m")])
