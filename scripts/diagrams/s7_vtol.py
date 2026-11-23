"""Visual pass (stage 7), batch vtol: diagrams of the two ArduPilot VTOL lessons (ArduPlane 4.7.2).

vtol-anatomy-controllers       ap-vtol-anatomy — one set of sensors and one AHRS/EKF feed two controller sets:
                               plane (RLL_RATE_, PTCH_RATE_, TECS_, NAVL1_ -> surfaces and Throttle 70) and copter
                               (Q_A_, Q_P_, Q_M_, Q_WP_ -> Motor1..8 = 33..40); the mode selects who flies; only the
                               transition and Q-assist run both (QuadPlane::update(), SLT_Transition::update()).
vtol-symptom-side-tree         ap-vtol-anatomy — the module's selection rule «с какой стороны настраивать симптом»:
                               mode at the moment of the symptom -> is QTUN logged (lift motors active) ->
                               right after a Q-mode change (transition) or not (Q-assist: Trn goes 0 -> 1 -> 2 again)
                               -> copter side, plane side or VTOL parameters.
chart-vtol-forward-transition  ap-vtol-modes — the real SITL 4.7.2 forward transition of practice step 1 (FBWA, full
                               throttle, model quadplane): airspeed and mean lift-motor PWM against time from
                               «Transition started»; threshold 18.3 m/s at 4.2 s = Q_ASSIST_SPEED 18 (not AIRSPEED_MIN
                               13), «Transition done» at 9.2 s = + Q_TRANSITION_MS 5 s.
vtol-qassist-tree              ap-vtol-modes — VTOL_Assist::should_assist() as a decision tree: disabled / not safe to
                               spin up -> none; force -> always; Q_ASSIST_SPEED <= 0 -> transitions only; speed (no
                               delay), altitude and angle (Q_ASSIST_DELAY 0.5 s) -> lift motors on without a mode change.
vtol-landing-stages            ap-vtol-modes — the poscontrol states of a mission VTOL landing with their entry
                               conditions and the SITL numbers of practice step 4: airbrake at V²/(2·2) + 2V = 130.6 m
                               for 19.2 m/s, POSITION1 at max(13 - 2, 18) = 18 m/s, POSITION2 < 10 m and < 9 m/s,
                               descent 1.5 m/s, final 0.5 m/s below Q_LAND_FINAL_ALT 6 m.
"""
from __future__ import annotations

import re

from plot import Axis, chart
from svg import Box, Node, flow, text, tree


def _add_footer(svg_str: str, lines: list[str], lh: int = 16) -> str:
    """Grow a helper-built SVG downwards and add muted footnote lines under it."""
    m = re.search(r'viewBox="0 0 (\d+(?:\.\d+)?) (\d+(?:\.\d+)?)"', svg_str)
    w, h = float(m.group(1)), float(m.group(2))
    nh = h + lh * len(lines) + 6
    body = "".join(text(16, h + 4 + lh * (i + 1) - 4, s, "m t", "start") for i, s in enumerate(lines))
    svg_str = svg_str.replace(m.group(0), f'viewBox="0 0 {w:g} {nh:g}"', 1)
    i = svg_str.rfind("</svg>")
    return svg_str[:i] + body + svg_str[i:]


# ---------------------------------------------------------------- ap-vtol-anatomy
def anatomy_controllers() -> str:
    W = 720
    boxes = [
        Box("sens", ["Датчики: IMU, GPS,", "баро, ARSPD_*"], 16, 40, 200, 50),
        Box("ahrs", ["AHRS / EKF3:", "одна оценка на всех"], 260, 40, 200, 50, accent=True),
        Box("mode", ["Режим: Q-режимы,", "самолётные, MANUAL"], 504, 40, 200, 50),
        Box("plane", ["Самолётный комплект:", "RLL_RATE_, PTCH_RATE_,", "TECS_, NAVL1_"], 16, 150, 228, 64),
        Box("trans", ["Переход и Q-assist:", "работают оба", "комплекта"], 262, 150, 196, 64, accent=True),
        Box("copter", ["Коптерный комплект:", "Q_A_, Q_P_, Q_M_,", "Q_WP_, Q_LOIT_"], 476, 150, 228, 64),
        Box("surf", ["Рули 4, 19, 21 и", "маршевый газ 70"], 16, 280, 228, 50),
        Box("mot", ["Подъёмные моторы", "Motor1…8 (33…40)"], 476, 280, 228, 50),
    ]
    links = [("sens", "ahrs"), ("ahrs", "plane", "", False, "v"), ("ahrs", "copter", "", False, "v"),
             ("mode", "copter", "", False, "v"),
             ("plane", "surf", "", False, "v"), ("copter", "mot", "", False, "v"),
             ("trans", "surf", "", True, "h"), ("trans", "mot", "", True, "h")]
    notes = [(16, 20, "QuadPlane: одна прошивка ArduPlane, два комплекта регуляторов", "m t"),
             (138, 240, "FBWA, AUTO, RTL…", "m t"),
             (598, 240, "Q-режимы", "m t"),
             (16, 350, "MANUAL, ACRO, TRAINING: коптерный комплект не работает (4+1 — моторы стоят)", "m t")]
    return flow("QuadPlane: самолётный и коптерный комплекты регуляторов", boxes, links, W, 362, notes=notes)


def symptom_side_tree() -> str:
    t = tree("С какой стороны настраивать симптом", Node("mode", ["Какой режим был", "в момент симптома?"], [
        ("Q-режим", Node("cop", ["Коптер: notch,", "Q_A_RAT_*, Q_M_THST_", "HOVER, Q_P_*"], leaf=True, accent=True)),
        ("самолётный", Node("qtun", ["Есть QTUN? (подъём-", "ные моторы активны)"], [
            ("нет", Node("pl", ["Самолёт: RLL_RATE_*,", "PTCH_RATE_*, TECS_,", "NAVL1_"], leaf=True, accent=True)),
            ("да", Node("trn", ["Только что сменил", "Q-режим (MODE)?"], [
                ("да", Node("tr", ["Переход: AIRSPEED_", "MIN, Q_TRANSITION_MS,", "Q_TILT_*, рули"], leaf=True)),
                ("нет", Node("ast", ["Q-assist: Q_ASSIST_*,", "ARSPD_RATIO", "(Trn снова 0, Ast ≠ 0)"], leaf=True)),
            ])),
        ])),
        ("MANUAL", Node("man", ["Самолёт без", "страховки: рули,", "центровка"], leaf=True)),
    ]), width=720, box_w=180, box_h=48, gap_y=72)
    return _add_footer(t, ["Правка «чужой» половины не помогает: на крейсере подъёмные моторы стоят,",
                           "а на висении крен держат моторы, не рули. Q-assist в крейсере тоже даёт QTUN.Trn 0 → 1 → 2"])


# ---------------------------------------------------------------- ap-vtol-modes
# SITL ArduPlane 4.7.2, model quadplane, practice step 1 (outB.txt): sim time, airspeed m/s, mean PWM of outputs 5–8
_B = [(69.73, 0.7, 1711), (70.23, 0.9, 1710), (70.73, 0.6, 1705), (71.23, 3.6, 1689), (71.73, 6.3, 1652),
      (72.23, 9.2, 1594), (72.73, 11.8, 1517), (73.23, 14.3, 1418), (73.83, 17.1, 1248), (74.23, 18.7, 1171),
      (74.73, 20.5, 1172), (75.23, 22.0, 1171), (75.83, 23.5, 1172), (76.33, 24.6, 1171), (76.73, 25.4, 1172),
      (77.23, 26.2, 1172), (77.83, 26.9, 1172), (78.33, 27.5, 1172), (78.83, 27.9, 1172), (79.33, 28.3, 1144),
      (79.83, 28.6, 1000), (80.33, 29.0, 1000), (80.83, 29.2, 1000), (81.33, 29.4, 1000), (81.83, 29.6, 1000)]
_T0, _T_REACHED, _T_DONE = 69.73, 73.93, 78.93


def forward_transition_chart() -> str:
    ts = [r[0] - _T0 for r in _B]
    asp = [r[1] for r in _B]
    pwm = [r[2] for r in _B]
    t_r, t_d = _T_REACHED - _T0, _T_DONE - _T0
    assert abs(t_r - 4.2) < 0.01 and abs(t_d - 9.2) < 0.01 and abs((t_d - t_r) - 5.0) < 0.01
    return chart(
        "SITL 4.7.2: переход вперёд в FBWA с полным газом",
        [dict(name="воздушная скорость", xs=ts, ys=asp, cls="a", label_at=10.6, label_dy=-8),
         dict(name="ШИМ подъёмных моторов", xs=ts, ys=pwm, cls="w", axis=2, label_at=0.2, label_dy=18,
              label_anchor="start")],
        Axis("время от «Transition started», с", 0, 12, ticks=[0, 2, 4, 6, 8, 10, 12]),
        Axis("воздушная скорость, м/с", 0, 32, ticks=[0, 5, 10, 15, 20, 25, 30]),
        y2=Axis("ШИМ выходов 5–8, мкс", 900, 1800, ticks=[1000, 1200, 1400, 1600, 1800]),
        bands=[(0, t_r, "AIRSPEED_WAIT"), (t_r, t_d, "TIMER 5 с")],
        hmarks=[(18, "Q_ASSIST_SPEED 18", "d"), (13, "AIRSPEED_MIN 13", "m")],
        marks=[(t_r, "18.3 м/с, 4.2 с", "ink", 150), (t_d, "done, 9.2 с", "ink", 100)],
        notes=[(330, 296, "159 м по земле до «done»", "m")])


def qassist_tree() -> str:
    t = tree("Q-assist в самолётном режиме: включать ли подъёмные моторы", Node("off", ["Выключен? Дизарм, тумблер 82", "вниз, выравнивание посадки"], [
        ("да", Node("n1", ["Помощи нет"], leaf=True)),
        ("нет", Node("safe", ["Безопасно? Авто-газ,", "газ > 0 или летит"], [
            ("нет", Node("n2", ["Помощи нет"], leaf=True)),
            ("да", Node("force", ["Force: тумблер 82", "вверх или бит 7?"], [
                ("да", Node("all", ["Помощь", "всегда"], leaf=True, accent=True)),
                ("нет", Node("spd", ["Q_ASSIST_SPEED > 0?"], [
                    ("нет", Node("tr", ["Только на", "переходах"], leaf=True)),
                    ("да", Node("trg", ["V < Q_ASSIST_SPEED (сразу)", "или h < Q_ASSIST_ALT, или угол", "вне пределов (0.5 с)?"], [
                        ("да", Node("on", ["Моторы вкл.,", "режим тот же"], leaf=True, accent=True)),
                        ("нет", Node("n3", ["Помощи нет"], leaf=True)),
                    ])),
                ])),
            ])),
        ])),
    ]), width=720, box_w=210, box_h=48, gap_y=72)
    return _add_footer(t, ["Q_ASSIST_SPEED = 0 запрещает арм; помощь по высоте и углу снимается через 2 × Q_ASSIST_DELAY",
                           "Без смены режима — в отличие от quad-chute PX4"])


def landing_stages() -> str:
    W = 720
    y1, y2, h = 44, 230, 58
    xs = [16, 192, 368, 544]
    boxes = [
        Box("app", ["APPROACH", "L1 + TECS, моторы", "стоят; 19 м/с"], xs[0], y1, 160, h),
        Box("ab", ["AIRBRAKE", "подъёмные моторы —", "тормоз, ≥ 1 с"], xs[1], y1, 160, h, accent=True),
        Box("p1", ["POSITION1", "контур коптера,", "V = √(2·a·d)"], xs[2], y1, 160, h),
        Box("p2", ["POSITION2", "точное наведение"], xs[3], y1, 160, h),
        Box("ld", ["LAND_DESCEND", "1.5 м/с"], xs[3], y2, 160, h),
        Box("lf", ["LAND_FINAL", "0.5 м/с ниже 6 м"], xs[2], y2, 160, h),
        Box("lc", ["LAND_COMPLETE", "дизарм"], xs[1], y2, 160, h),
    ]
    links = [("app", "ab"), ("ab", "p1"), ("p1", "p2"), ("p2", "ld", "", False, "v"), ("ld", "lf"), ("lf", "lc")]
    cond = [  # entry condition of the next stage, written under each box of the first row
        (xs[0], ["→ AIRBRAKE:", "d < V²/2a + 2V", "= 130.6 м при 19.2 м/с"]),
        (xs[1], ["→ POSITION1:", "V < max(MIN−2, ASSIST)", "= max(11, 18) = 18 м/с"]),
        (xs[2], ["→ POSITION2:", "d < 10 м и V < 9 м/с"]),
    ]
    notes = [(16, 22, "VTOL-посадка в миссии: этапы QPOS и условия перехода (a = Q_TRANS_DECEL = 2 м/с²)", "m t")]
    for x, lines in cond:
        for i, s in enumerate(lines):
            notes.append((x + 2, y1 + h + 18 + 14 * i, s, "m t"))
    notes += [(16, y2 + h + 26, "SITL 4.7.2: «VTOL airbrake v=19.2 d=130 sd=130», position1 при 18.0 м/с,", "m t"),
              (16, y2 + h + 42, "position2 при d=9.5 м и v=6.5 м/с, «Land final started» на 6.0 м", "m t"),
              (xs[3] + 88, y1 + h + 50, "точка", "m t"), (xs[3] + 88, y1 + h + 64, "достигнута", "m t")]
    return flow("Этапы VTOL-посадки ArduPlane 4.7.2", boxes, links, W, y2 + h + 54, notes=notes)


def build(D: dict) -> None:
    D["vtol-anatomy-controllers"] = anatomy_controllers()
    D["vtol-symptom-side-tree"] = symptom_side_tree()
    D["chart-vtol-forward-transition"] = forward_transition_chart()
    D["vtol-qassist-tree"] = qassist_tree()
    D["vtol-landing-stages"] = landing_stages()
