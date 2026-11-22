"""Stage 6 diagrams for px4-setup-vtol (PX4 v1.17.0).

px4-vtol-setup-flow       — the 17 setup steps for a plane / standard VTOL, marked bench (props off) vs field.
chart-px4-vtol-transition — front transition of the module's worked example (practice step 2): airspeed table,
                            pusher throttle and multicopter weight computed with the same rules as
                            vtol_att_control/standard.cpp and vtol_type.cpp (v1.17.0).
"""
from __future__ import annotations

from plot import Axis, chart
from svg import Box, flow

STEPS = [
    (["1 Прошивка,", "бэкап"], "стол"), (["2 Airframe", "13000, CA_*"], "стол"),
    (["3 Порты,", "датчик скорости"], "стол"), (["4 Приёмник,", "бинд"], "стол"),
    (["5 Радио,", "тумблер перехода"], "стол"), (["6 Протоколы", "по группам"], "стол"),
    (["7 Моторы", "и рули"], "стол, без пропов"), (["8 ESC тянущего", "мотора (PWM)"], "стол, без пропов"),
    (["9 Датчики,", "калибр. скорости"], "стол"), (["10 Питание", "BAT1_*"], "стол"),
    (["11 Режимы", ""], "стол"), (["12 Failsafe,", "quad-chute"], "стол + поле"),
    (["13 OSD,", "телеметрия"], "стол"), (["14 Return,", "посадка миссии"], "стол"),
    (["15 Висение →", "переход ≥ 20 м"], "поле"), (["16 MC, затем", "FW_AT_*"], "поле"),
    (["17 ULog,", ".params"], "стол"),
]

# practice step 2 (учебный пример): VT_ARSP_BLEND 10, VT_ARSP_TRANS 11.5, VT_TRANS_MIN_TM 4,
# VT_PSHER_SLEW 0.33, VT_F_TRANS_THR 0.9; airspeed table at 1 s steps, linear in between.
T = list(range(0, 11))
V = [0, 1.5, 3.5, 5.5, 7.2, 8.6, 9.8, 10.6, 11.2, 11.7, 12.1]
BLEND, TRANS, TMIN, SLEW, THR = 10.0, 11.5, 4.0, 0.33, 0.9


def airspeed(t: float) -> float:
    i = min(int(t), len(T) - 2)
    return V[i] + (V[i + 1] - V[i]) * (t - T[i])


def completion_time() -> float:
    """First time after VT_TRANS_MIN_TM at which the (linear) airspeed reaches VT_ARSP_TRANS."""
    for i in range(1, len(T)):
        if V[i] >= TRANS and T[i] > TMIN:
            t = T[i - 1] + (TRANS - V[i - 1]) / (V[i] - V[i - 1])
            return max(t, TMIN)
    return float(T[-1])


def build(D: dict) -> None:
    w, x0, h = 106, 17, 44
    rows_y = [34, 112, 190]
    boxes = []
    for i, (lab, where) in enumerate(STEPS):
        row, col = divmod(i, 6)
        if row == 1:
            col = 5 - col
        x = x0 + col * (w + 10)
        lab = [s for s in lab if s]
        boxes.append(Box(f"s{i + 1}", lab, x, rows_y[row], w, h, accent="поле" in where, note=where))
    links = [(f"s{i}", f"s{i + 1}") for i in range(1, 17)]
    D["px4-vtol-setup-flow"] = flow(
        "PX4 самолёт / VTOL с нуля: 17 шагов — стол или поле", boxes, links, 720, 292,
        notes=[(17, 268, "Выделено — шаг требует поля. «стол» — без пропеллеров; рули — после перехода в FW без арма.", "m t"),
               (17, 284, "Пропеллеры ставятся только на шаге 15; первый переход — на 20 м и выше, против ветра.", "m t")])

    tc = completion_time()
    ts = [i * 0.05 for i in range(0, 201)]
    vs = [airspeed(t) for t in ts]
    push = [min(THR, SLEW * t) for t in ts]
    mcw = []
    for t, v in zip(ts, vs):
        if t >= tc:
            mcw.append(0.0)
        elif v >= BLEND and t > TMIN:
            mcw.append(max(0.0, min(1.0, 1 - (v - BLEND) / (TRANS - BLEND))))
        else:
            mcw.append(1.0)
    D["chart-px4-vtol-transition"] = chart(
        f"Переход вперёд стандартного VTOL: самолёт на {tc:.1f} с (учебный пример)",
        [dict(name="воздушная скорость", xs=ts, ys=vs, cls="a", label_at=3.2, label_dy=-8, label_anchor="start"),
         dict(name="газ тянущего мотора", xs=ts, ys=push, cls="w", axis=2, label_at=1.0, label_dy=-10,
              label_anchor="start", dash=True),
         dict(name="вес подъёмных моторов w", xs=ts, ys=mcw, cls="ink", axis=2, label_at=4.6, label_dy=-8,
              label_anchor="start")],
        Axis("время от включения тумблера, с", 0, 10), Axis("скорость, м/с", 0, 14),
        y2=Axis("газ / вес, 0…1", 0, 1.17),
        hmarks=[(BLEND, "VT_ARSP_BLEND 10", "m"), (TRANS, "VT_ARSP_TRANS 11.5", "m")],
        marks=[(TMIN, "VT_TRANS_MIN_TM", "m", 300), (tc, f"{tc:.1f} с", "a", 44)],
        notes=[(80, 302, "без датчика: w → 0 к 4 с, самолёт на VT_F_TR_OL_TM = 8 с", "m")])
