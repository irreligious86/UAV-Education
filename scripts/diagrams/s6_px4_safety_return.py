"""Stage 6 diagrams for px4-safety-return (PX4 v1.18.0).

px4-failsafe-flow    — how commander/failsafe/framework.cpp turns failsafe_flags into one action:
                       per-condition action -> worst action wins -> optional Hold delay (COM_FAIL_ACT_T)
                       -> fallback chain if the mode cannot run -> user takeover.
chart-px4-rtl-cone   — return altitude above the destination vs horizontal distance, computed with the
                       same function as navigator/rtl.cpp RTL::computeReturnAltitude() (v1.18.0; in v1.17.0
                       calculate_return_alt_from_cone_half_angle(), same arithmetic); curves use the parameter
                       set of the module's exercise and the v1.18 multicopter defaults (NAV_ACC_RAD 10 m, was 2 m).
"""
from __future__ import annotations

import math

from plot import Axis, chart
from svg import Box, flow


def rtl_alt(d: float, h_now: float, ret: float, min_dist: float, cone: float, acc: float = 2.0) -> float:
    """Heights above the destination, metres. Mirrors rtl.cpp (v1.18.0)."""
    if cone <= 0:
        return max(h_now, ret)
    alt = ret
    if d <= acc:
        alt = 2.0 * d
    else:
        if d <= min_dist:
            alt = min(d / math.tan(math.radians(min(max(cone, 1.0), 89.0))), alt)
        alt = max(alt, 2.0 * acc)
    return h_now if alt < h_now else min(alt, ret)


def build(D: dict) -> None:
    w, h = 204, 56
    xs = [17, 258, 499]
    ys = [36, 142, 248]
    boxes = [
        Box("flags", ["Проверки commander", "→ failsafe_flags"], xs[0], ys[0], w, h, note="RC, GCS, АКБ, позиция, геозона, FD"),
        Box("act", ["Условие → действие", "NAV_RCL_ACT, GF_ACTION …"], xs[1], ys[0], w, h, note="у каждого условия своё"),
        Box("worst", ["Берётся худшее:", "Hold < RTL < Land <", "Descend < Disarm < Terminate"], xs[2], ys[0], w, h, accent=True),
        Box("delay", ["Отложить? COM_FAIL_ACT_T > 0,", "действие RTL / Land,", "ещё не в failsafe"], xs[2], ys[1], w, h,
            note="Hold, Disarm, Terminate — сразу"),
        Box("hold", ["Hold на COM_FAIL_ACT_T", "(5 с), перехват —", "только сменой режима"], xs[1], ys[1], w, h, accent=True),
        Box("run", ["Действие выполняется"], xs[0], ys[1], w, h),
        Box("can", ["Режим недоступен →", "Hold → RTL → Land →", "Descend → Terminate"], xs[0], ys[2], w, h,
            note="нет позиции, дома, высоты"),
        Box("take", ["Перехват пилотом:", "режим или быстрое", "движение стика (OVERRIDE_SPD)"], xs[1], ys[2], w, h, accent=True,
            note="стики — только мультиротор"),
        Box("clear", ["Снятие: условие ушло", "+ смена режима", "или дизарм"], xs[2], ys[2], w, h,
            note="Terminate не снимается"),
    ]
    links = [("flags", "act"), ("act", "worst"), ("worst", "delay", "", False, "v"),
             ("delay", "hold", "да", True), ("hold", "run", "5 с", True),
             ("run", "can", "", False, "v"), ("can", "take"), ("take", "clear")]
    D["px4-failsafe-flow"] = flow(
        "PX4 1.18: от флага отказа до действия", boxes, links, 720, 344,
        notes=[(17, 336, "Источник: commander/failsafe/framework.cpp и failsafe.cpp, v1.18.0.", "m t")])

    ds = [i * 0.5 for i in range(0, 241)]
    ex45 = [rtl_alt(d, 0.0, 40.0, 60.0, 45.0) for d in ds]
    ex65 = [rtl_alt(d, 0.0, 40.0, 60.0, 65.0) for d in ds]
    mc = [rtl_alt(d, 0.0, 30.0, 10.0, 45.0, acc=10.0) for d in ds]
    D["chart-px4-rtl-cone"] = chart(
        "Высота возврата по конусу: конус действует только ближе RTL_MIN_DIST",
        [dict(name="упражнение, конус 45°", xs=ds, ys=ex45, cls="a", label_at=57, label_dy=-8, label_anchor="end"),
         dict(name="упражнение, конус 65°", xs=ds, ys=ex65, cls="w", label_at=36, label_dy=22, label_anchor="start", dash=True),
         dict(name="умолчания MC 1.18: 30 м, RTL_MIN_DIST 10, NAV_ACC_RAD 10", xs=ds, ys=mc, cls="ink", label_at=72, label_dy=16,
              label_anchor="start")],
        Axis("горизонтальная дистанция до точки возврата, м", 0, 120), Axis("высота возврата над точкой, м", 0, 48),
        marks=[(60, "RTL_MIN_DIST = 60 м", "m", 190), (10, "RTL_MIN_DIST = 10 м", "m", 130)],
        notes=[(392, 286, "упражнение: RTL_RETURN_ALT 40 м, NAV_ACC_RAD 2 м", "m"),
               (392, 302, "текущая высота 0 м; ниже текущей не назначается", "m")])
