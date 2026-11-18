"""Stage 6 diagrams for module bf-arming-safety (Betaflight 2025.12 arming flags, runaway takeoff, yaw spin).

bf-arming-flag-groups   — the 29 arming-disable flags of 2025.12 (armingDisableFlagNames[] in fc/runtime_config.c) grouped by what the pilot does about them (svg.tree).
chart-bf-runaway-trip   — the module's worked example B: roll motors swapped, pidSum and gyro after lift-off,
                          trip at 217 ms (|pidSum| >= 600 and gyro > 15 deg/s), disarm 75 ms later at 292 ms
                          (fc/core.c constants; same plant model and numbers as the practice script).
"""
from __future__ import annotations

from plot import Axis, chart
from svg import Node, tree


def _runaway_trace():
    """Re-run scenario B of the practice script: roll feedback inverted, P = 45, I = 80, pidsum_limit 500,
    iterm_limit 400, plant 12 deg/s^2 per pidSum unit, motor lag 20 ms, 8 kHz loop, 5 deg/s initial disturbance."""
    kp, ki, dt = 0.032029 * 45, 0.244381 * 80, 125e-6
    w, cmd, i_term = 5.0, 0.0, 0.0
    ts, ps, gs = [], [], []
    trig, disarm = 0, None
    for k in range(int(0.40 / dt)):
        t_us = k * 125
        err = -w
        i_term = max(-400.0, min(400.0, i_term + ki * err * dt))
        pidsum = kp * err + i_term
        if disarm is None:
            cmd += (max(-500.0, min(500.0, pidsum)) - cmd) * dt / 0.020
            w += -1 * 12.0 * cmd * dt
            if abs(pidsum) >= 600 and abs(w) > 15:
                if trig == 0:
                    trig = t_us + 75_000
                elif t_us > trig:
                    disarm = t_us
            else:
                trig = 0
        if disarm is not None and t_us > disarm:
            break                                  # motors off: the plot ends at the disarm
        if k % 40 == 0:
            ts.append(t_us / 1000)
            ps.append(abs(pidsum))
            gs.append(abs(w))
    return ts, ps, gs, (trig - 75_000) / 1000, disarm / 1000


def build(D: dict) -> None:
    W = 140
    leaf = lambda i, lines: Node(i, lines, leaf=True)
    D["bf-arming-flag-groups"] = tree(
        "Betaflight 2025.12: 29 флагов запрета арма по тому, что делать",
        Node("r", ["status / OSD /", "пищалка: флаги"], [
            ("тумблеры, стики", leaf("g1", ["THROTTLE ARM_SWITCH", "NOT_DISARMED", "NOPREARM BOXFAILSAFE", "RESCUE_SW FLIP_SWITCH",
                                              "ALT_HOLD_SW", "POS_HOLD_SW"])),
            ("датчики, поза", leaf("g2", ["ANGLE CALIB", "NO_ACC_CAL GPS", "NOGYRO", "BOOTGRACE"])),
            ("связь, меню", leaf("g3", ["RXLOSS FAILSAFE", "MSP CLI CMS", "REBOOT_REQD", "BST"])),
            ("моторы, CPU", leaf("g4", ["MOTOR_PROTO", "DSHOT_TELEM", "DSHOT_BBANG", "LOAD"])),
            ("после сбоя", leaf("g5", ["RUNAWAY CRASH", "PARALYZE", "→ дизарм /", "перезагрузка"])),
        ], accent=True),
        width=720, box_w=W, box_h=80, gap_y=114)

    ts, ps, gs, t_trip, t_disarm = _runaway_trace()
    D["chart-bf-runaway-trip"] = chart(
        "Перепутаны моторы крена: как Betaflight ловит runaway",
        [dict(name="|pidSum| roll", xs=ts, ys=ps, cls="d", label_at=180),
         dict(name="|gyro| °/с", xs=ts, ys=gs, cls="a", label_at=250, label_dy=14, label_anchor="start")],
        Axis("время после отрыва, мс", 0, 360), Axis("pidSum / °/с", 0, 1500),
        marks=[(t_trip, f"порог: {t_trip:.0f} мс", "w", 40), (t_disarm, f"дизарм: {t_disarm:.0f} мс", "d", 60)],
        hmarks=[(600, "порог pidSum 600", "w"), (500, "pidsum_limit 500", "m")])
