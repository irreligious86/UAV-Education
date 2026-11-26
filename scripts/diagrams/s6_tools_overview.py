"""Thin-module pass diagram for module tools-overview.

tools-firmware-tree — decision tree «прошивка → инструменты» from the module's task table and version table
                      (Nov 2026): configurator / GCS with the version-compatibility rule, log tool, simulator.
"""
from __future__ import annotations

from svg import Node, tree


def firmware_tree() -> str:
    leaf = lambda i, lines: Node(i, lines, leaf=True)
    root = Node("fw", ["Какая прошивка", "на аппарате?"], [
        ("", Node("bf", ["Betaflight", "2025.12"], [("", leaf("bfl", ["App 2026.6.2:", "MSP API ≥ 1.44", "BB Explorer", "SITL: make"]))], accent=True)),
        ("", Node("inav", ["INAV 9.1"], [("", leaf("inl", ["Configurator", "только 9.x", "BB Explorer", "INAV SITL"]))], accent=True)),
        ("", Node("ap", ["ArduPilot", "4.7.2"], [("", leaf("apl", ["MP 1.3.83 / QGC", "имена 4.7!", "MAVExplorer", "SITL 4.7.2"]))], accent=True)),
        ("", Node("px4", ["PX4 1.17"], [("", leaf("pxl", ["QGC 5.1.5", "Flight Review", "PlotJuggler", "SITL + Gazebo"]))], accent=True)),
    ])
    return tree("Сначала прошивка, потом инструмент (версии на ноябрь 2026)", root, width=720, box_w=160, box_h=60,
                gap_y=86)


def build(D: dict) -> None:
    D["tools-firmware-tree"] = firmware_tree()
