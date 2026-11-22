"""Stage 6 diagrams for module ap-payload (ArduPilot 4.7 payload: camera, mount, gripper).

ap-payload-paths                  — command -> library -> output for camera / mount / gripper. Names follow
                                    Copter-4.7.2: RC_Channel.h (aux functions 9, 19, 27, 163, 212-214),
                                    AP_Mission_Commands.cpp (DO_* handlers), AP_Camera / AP_Mount / AP_Gripper
                                    backends, SRV_Channel.h (functions 6-10, 28), AP_Relay_Params (function 4).
chart-ap-payload-trigger-interval — time between shots t = d / v and the real shot spacing max(d, v * T) for the
                                    module's practice step 2: d = 24 m (120 m footprint, 80 % overlap),
                                    CAM1_INTRVAL_MIN = T = 1.5 s. AP_Camera_Backend::take_picture() postpones a
                                    shot until T has passed, so above v = d / T the spacing grows with speed.
"""
from __future__ import annotations

from plot import Axis, chart
from svg import Box, flow

D_TRIG = 24.0        # m, CAM1_TRIGG_DIST of practice step 2
T_MIN = 1.5          # s, CAM1_INTRVAL_MIN = camera cycle time
FOOT = 120.0         # m, along-track footprint
V_PLAN = 12.0        # m/s, planned ground speed
V_WIND = 18.0        # m/s, ground speed with tail wind


def interval_s(v: float, d: float = D_TRIG) -> float:
    """Time between distance triggers at ground speed v."""
    return d / v


def spacing_m(v: float, d: float = D_TRIG, t_min: float = T_MIN) -> float:
    """Real distance between shots: the trigger waits for CAM1_INTRVAL_MIN."""
    return max(d, v * t_min)


def overlap(v: float) -> float:
    return 1.0 - spacing_m(v) / FOOT


def build(D: dict) -> None:
    bw, bh = 150, 46
    x1, x2, x3 = 10, 300, 544
    y1, y2, y3 = 44, 124, 204
    boxes = [
        Box("c_in", ["RCx_OPTION 9, DO_DIGICAM_CONTROL,", "DO_SET_CAM_TRIGG_DIST"], x1, y1, 250, bh),
        Box("c_lib", ["AP_Camera", "CAM1_TYPE"], x2, y1, bw, bh, accent=True),
        Box("c_out", ["серва 10, реле 4,", "подвес, MAVLink"], x3, y1, 166, bh),
        Box("m_in", ["RCx_OPTION 212–214, 27, 163,", "DO_GIMBAL_MANAGER_PITCHYAW"], x1, y2, 250, bh),
        Box("m_lib", ["AP_Mount", "MNT1_TYPE"], x2, y2, bw, bh, accent=True),
        Box("m_out", ["сервы 6–8, 9;", "UART 8 или 7; MAVLink"], x3, y2, 166, bh),
        Box("g_in", ["RCx_OPTION 19, DO_GRIPPER,", "FS_OPTIONS бит 5"], x1, y3, 250, bh),
        Box("g_lib", ["AP_Gripper", "GRIP_TYPE"], x2, y3, bw, bh, accent=True),
        Box("g_out", ["серва 28 или", "узел DroneCAN"], x3, y3, 166, bh),
    ]
    links = [
        ("c_in", "c_lib", "", False, "h"), ("c_lib", "c_out", "", True, "h"),
        ("m_in", "m_lib", "", False, "h"), ("m_lib", "m_out", "", True, "h"),
        ("g_in", "g_lib", "", False, "h"), ("g_lib", "g_out", "", True, "h"),
        ("c_lib", "m_lib", "", False, "v"),
    ]
    D["ap-payload-paths"] = flow(
        "ArduPilot 4.7: от команды до выхода — камера, подвес, захват",
        boxes, links, 720, 330,
        notes=[(x2 + bw / 2 + 10, 111, "CAM1_TYPE = 4", "m t"),
               (14, 276, "Источник не пишет в выход напрямую: тумблер, миссия и MAVLink вызывают библиотеку, она выбирает драйвер по TYPE.", "t"),
               (14, 292, "Камера типа 4 спускается через драйвер подвеса: без рабочего MNT1_TYPE кадров не будет.", "a t"),
               (14, 308, "Сервы — обычные PWM-выходы: группы таймеров и BRD_SAFETY_MASK действуют; реле на GPIO кнопка не блокирует.", "w t"),
               (14, 324, "Захват отпускают три разных источника: тумблер 19 (LOW), DO_GRIPPER и failsafe с FS_OPTIONS бит 5.", "m t")])

    vs = [4 + 0.25 * i for i in range(0, 73)]          # 4 … 22 m/s
    v_lim = D_TRIG / T_MIN
    D["chart-ap-payload-trigger-interval"] = chart(
        "Шаг съёмки 24 м: интервал между кадрами и реальный шаг при CAM1_INTRVAL_MIN = 1.5 с",
        [
            dict(name="интервал t = d / v, с", xs=vs, ys=[interval_s(v) for v in vs], cls="ink", label_at=6.5,
                 label_anchor="start", label_dy=-8),
            dict(name="реальный шаг, м", xs=vs, ys=[spacing_m(v) for v in vs], cls="a", axis=2, label_at=18.3,
                 label_anchor="start", label_dy=22),
        ],
        x=Axis("путевая скорость, м/с", 4, 22, ticks=[4, 6, 8, 10, 12, 14, 16, 18, 20, 22]),
        y=Axis("интервал между кадрами, с", 0, 6, ticks=[0, 1, 1.5, 2, 3, 4, 5, 6]),
        y2=Axis("шаг съёмки, м", 20, 35, ticks=[20, 24, 27, 30, 35]),
        marks=[(V_PLAN, f"{V_PLAN:g} м/с: {interval_s(V_PLAN):.1f} с", "ink", 44),
               (v_lim, f"{v_lim:g} м/с: предел", "w", 16),
               (V_WIND, f"{V_WIND:g} м/с: шаг {spacing_m(V_WIND):g} м", "d", 34)],
        hmarks=[(T_MIN, "CAM1_INTRVAL_MIN = 1.5 с", "w")],
        notes=[(76, 284, f"До {v_lim:g} м/с шаг равен 24 м.", "m"),
               (76, 300, f"Выше — v · 1.5 с; при 18 м/с перекрытие {overlap(V_WIND) * 100:.1f} %.", "m")],
    )
