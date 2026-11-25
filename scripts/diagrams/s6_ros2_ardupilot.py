"""Thin-module pass (stage 6) diagram for module ros2-ardupilot.

ros2-ap-dds-boot-race  — the AP_DDS connect loop of ArduPilot 4.7.2 (AP_DDS_Client.cpp main_loop) against a companion
                         that boots slower than the autopilot. Defaults DDS_TIMEOUT_MS = 1000, DDS_MAX_RETRY = 10:
                         a batch of 10 pings = 10 s, then STATUSTEXT «DDS: No ping response, exiting» and the loop
                         continues (despite the text). The agent of the module's example comes up at t = 35 s
                         (Pi boot, course estimate), the next batch finds it and the session is created; inside the
                         session a ping every DELAY_PING_MS = 500 ms, more than 2 missed -> «disconnecting» and back
                         to the ping loop.
"""
from __future__ import annotations

from svg import timeline

T_AGENT = 35          # course example: micro_ros_agent ready 35 s after power-on
BATCH = 10            # DDS_TIMEOUT_MS 1000 ms x DDS_MAX_RETRY 10


def boot_race() -> str:
    fc = [(0, 2, "")]
    t = 2
    while t + BATCH <= T_AGENT:
        fc.append((t, t + BATCH, "10 × 1 с"))
        t += BATCH
    fc.append((t, T_AGENT + 1, "пинги"))
    fc.append((T_AGENT + 1, 50, "сессия, топики /ap/*", True))
    comp = [(0, T_AGENT, "Linux грузится, агента нет"), (T_AGENT, 50, "агент на UDP 2019", True)]
    return timeline("Гонка загрузки: DDS-клиент ArduPilot 4.7.2 ждёт агента пачками по 10 с",
                    [("Автопилот", fc), ("Companion", comp)], 50, unit="с",
                    marks=[(12, "«No ping response, exiting» на 12, 22, 32 с"), (22, ""), (32, "")])


def build(D: dict) -> None:
    D["ros2-ap-dds-boot-race"] = boot_race()
