"""Thin-module pass (stage 6) diagram for module mav-sdk.

mav-sdk-ap-startup-seq  — what MAVSDK-Python 4.2.1 (native binding, libcmavsdk) and ArduCopter 4.7.2 SITL exchange in
                          the module's lab run, in order: HEARTBEAT -> first_autopilot (0.9 s); set_rate_* ->
                          SET_MESSAGE_INTERVAL (4.7 Copter streams MAVn_* default to 0); EKF_STATUS_REPORT with
                          POS_HORIZ_ABS -> health.is_global_position_ok (42.0 s); upload of 4 MissionItem with speed ->
                          8 raw items (NAV_WAYPOINT + DO_CHANGE_SPEED each), seq 0 overwritten by home (hence the
                          placeholder); arm in the current mode; takeoff() switches GUIDED itself.
All times are from the pasted output of mavsdk_lab.py in the module.
"""
from __future__ import annotations

from svg import sequence


def startup_seq() -> str:
    return sequence("MAVSDK 4.2.1 и ArduCopter 4.7.2: что уходит по проводу (лабораторная модуля)",
                    ["Скрипт asyncio", "libcmavsdk", "ArduCopter 4.7.2"], [
                        (0, 1, "add_any_connection(tcpout://…)"),
                        (2, 1, "HEARTBEAT, autopilot=3", False, True),
                        (1, 0, "first_autopilot() → System"),
                        (0, 1, "set_rate_health / _position"),
                        (1, 2, "SET_MESSAGE_INTERVAL ×3", True),
                        (2, 1, "SYS_STATUS, EKF_STATUS_REPORT", False, True),
                        (1, 0, "health: global_pos = True"),
                        (0, 1, "upload_mission(4 пункта)"),
                        (1, 2, "MISSION_COUNT 8, ITEM_INT ×8", True),
                        (2, 2, "seq 0 затёрт домом: пункт-подставка"),
                        (0, 1, "arm(); takeoff()"),
                        (1, 2, "ARM, GUIDED, TAKEOFF"),
                    ], notes=[(1, "0.9 с"), (4, "потоки MAVn_* = 0"), (6, "42.0 с"),
                              (8, "WAYPOINT + CHANGE_SPEED"), (11, "GUIDED = OFFBOARD")])


def build(D: dict) -> None:
    D["mav-sdk-ap-startup-seq"] = startup_seq()
