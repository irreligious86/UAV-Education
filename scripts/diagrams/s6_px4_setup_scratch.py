"""Stage 6 diagrams for px4-setup-scratch: the 17 setup steps (SITL / bench / flight) and the
hover-thrust estimate from the module's SIH run (PX4 v1.15.4, sihsim_quadx, log 20_35_33.ulg)."""
from __future__ import annotations

from plot import Axis, chart
from svg import Box, flow

# hover_thrust_estimate.hover_thrust, sampled every 2 s from arming (t = 0); valid from t = 8 s.
# Autotune ran from 35.4 s (STATE_INIT) to 61.2 s (STATE_WAIT_FOR_DISARM).
HTE = [(8.0, 0.5153), (10.0, 0.5074), (12.0, 0.5050), (14.0, 0.5031), (16.0, 0.4992), (18.0, 0.4964),
       (20.0, 0.4969), (22.0, 0.4958), (24.0, 0.4939), (26.0, 0.4922), (28.0, 0.4923), (30.0, 0.4923),
       (32.0, 0.4928), (34.0, 0.4910), (36.0, 0.4908), (38.0, 0.4905), (40.0, 0.4911), (42.0, 0.4921),
       (44.0, 0.4918), (46.0, 0.4917), (48.0, 0.4911), (50.0, 0.4909), (52.0, 0.4905), (54.0, 0.4900),
       (56.0, 0.4893), (58.0, 0.4885), (60.0, 0.4883), (62.0, 0.4880), (64.0, 0.4877), (66.0, 0.4886),
       (68.0, 0.4891), (70.0, 0.4890), (72.0, 0.4888), (74.0, 0.4895), (76.0, 0.4898), (78.0, 0.4905),
       (80.0, 0.4906), (82.0, 0.4920), (84.0, 0.4925), (86.0, 0.4921), (88.0, 0.4898), (90.0, 0.4889)]

STEPS = [
    (["1 Прошивка,", "бэкап"], "стол"), (["2 Airframe,", "SENS_BOARD_ROT"], "SITL"),
    (["3 Порты", "*_CONFIG"], "стол"), (["4 Приёмник", "CRSF, бинд"], "стол"),
    (["5 Радио:", "калибровка"], "стол"), (["6 Протокол", "DShot / PWM"], "стол"),
    (["7 Моторы:", "порядок, вращ."], "SITL + стол"), (["8 ESC калибр.", "только PWM"], "стол"),
    (["9 Датчики:", "акс, гиро, комп"], "стол"), (["10 Питание", "BAT1_V_DIV"], "стол"),
    (["11 Режимы,", "арм-тумблер"], "SITL"), (["12 Failsafe", "и его тест"], "SITL"),
    (["13 OSD,", "телеметрия"], "стол"), (["14 GPS, RTL", "RTL_RETURN_ALT"], "SITL"),
    (["15 Висение", "Position"], "полёт"), (["16 Autotune", "MC_AT_*"], "SITL + полёт"),
    (["17 ULog,", ".params"], "SITL + полёт"),
]


def build(D: dict) -> None:
    w, gap, x0, h = 106, 10, 17, 44
    rows_y = [34, 112, 190]
    boxes = []
    for i, (lab, where) in enumerate(STEPS):
        row, col = divmod(i, 6)
        if row == 1:                      # snake: second row runs right to left
            col = 5 - col
        x = x0 + col * (w + gap)
        boxes.append(Box(f"s{i + 1}", lab, x, rows_y[row], w, h, accent="SITL" in where, note=where))
    links = [(f"s{i}", f"s{i + 1}") for i in range(1, 17)]
    D["px4-setup-flow"] = flow(
        "PX4 с нуля: 17 шагов — где каждый делается", boxes, links, 720, 292,
        notes=[(17, 268, "Выделено — шаг проходится в SITL (SIH / gz_x500). «стол» — USB или АКБ без пропов.", "m t"),
               (17, 284, "Пропеллеры ставятся только на шаге 15; failsafe-тест (12) на железе — сначала без пропов.", "m t")])

    xs = [p[0] for p in HTE]
    ys = [p[1] for p in HTE]
    D["chart-px4-hte"] = chart(
        "Оценка газа висения в SIH: 0.488–0.493 против расчёта m·g/(4·T_max) = 0.4905",
        [dict(name="hover_thrust (HTE)", xs=xs, ys=ys, cls="a", label_at=66, label_dy=20, label_anchor="start")],
        Axis("время от арма, с", 0, 92), Axis("нормированная тяга", 0.47, 0.53),
        hmarks=[(0.4905, "", "w"), (0.5, "MPC_THR_HOVER = 0.50 (умолчание)", "m")],
        notes=[(120, 240, "расчёт: 1 кг, 4 × 5 Н → 0.4905", "w")],
        bands=[(35.4, 61.2, "autotune")],
        marks=[(8.0, "valid", "m", 44)])
