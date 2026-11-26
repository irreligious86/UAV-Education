"""Thin-module pass (stage 6) diagram for module px4-ros2.

px4-offboard-loss-timeline — when PX4 1.17.0 drops out of Offboard. offboardCheck.cpp marks the offboard signal as
                             lost when hrt_absolute_time() >= OffboardControlMode.timestamp + COM_OF_LOSS_T
                             (default 1.0 s, commander_params.c); failsafe.cpp checkModeFallback() then applies
                             COM_OBL_RC_ACT (default 0 = Position). Numbers are the module's lab (dds_lab.py, part 3):
                             10 Hz stream stopped at 5.0 s -> last message 4.9 s -> fallback at 5.9 s; the same node
                             with timestamps 1.5 s in the past never makes Offboard available.
"""
from __future__ import annotations

from svg import timeline

LOSS_T = 1.0          # COM_OF_LOSS_T default, s
STOP = 5.0            # node stopped (Ctrl+C) at 5.0 s
PERIOD = 0.1          # 10 Hz stream
LAST = round(STOP - PERIOD, 1)          # 4.9 s, last OffboardControlMode
FALLBACK = round(LAST + LOSS_T, 1)      # 5.9 s


def loss_timeline() -> str:
    lanes = [
        ("Узел, 10 Гц", [(0, STOP, "OffboardControlMode + уставка", True), (STOP, 8, "тишина")]),
        ("PX4 1.17", [(0, 1, "поток"), (1, FALLBACK, "Offboard", True), (FALLBACK, 8, "COM_OBL_RC_ACT")]),
        ("метки −1.5 с", [(0, 8, "сигнал «старый» всегда: в Offboard не войти")]),
    ]
    return timeline("Выход из Offboard: последняя метка + COM_OF_LOSS_T (1 с), а не «частота ниже 2 Гц»",
                    lanes, 8, unit="с",
                    marks=[(LAST, f"{LAST} с"), (FALLBACK, f"{FALLBACK} с: откат")])


def build(D: dict) -> None:
    D["px4-offboard-loss-timeline"] = loss_timeline()
