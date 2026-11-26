"""Thin-module pass (stage 6) diagram for module px4-companion-jetson.

jetson-link-choice — which link between a Jetson and PX4 1.17.0, by the module's rule. Numbers come from the
                     module's lab (link_lab.py): UART 921600 8N1 = 92160 B/s; MAV_1_RATE = 0 -> baud/20 = 46080 B/s
                     (src/modules/mavlink/module.yaml); all 27 /fmu/out topics at their caps = 107495 B/s = 117 % of
                     921600 and 36 % of 3000000 (uxrce_dds_client -b max); Ethernet = config value 1000
                     (Tools/serial/generate_config.py), fmu-v6x sets MAV_2_CONFIG 1000 (rc.board_defaults);
                     UXRCE_DDS_AG_IP is the IPv4 address as int32 (192.168.1.2 -> -1062731518, module.yaml).
"""
from __future__ import annotations

from svg import Node, tree


def link_tree() -> str:
    root = Node("root", ["Jetson ↔ PX4 1.17:", "какой канал?"], [
        ("есть Ethernet (6X)", Node("eth", ["UDP: MAV_2_CONFIG = 1000,", "UXRCE_DDS_CFG = 1000"], [
            ("", Node("ip", ["UXRCE_DDS_AG_IP =", "IP как int32"], leaf=True, accent=True)),
        ])),
        ("только UART", Node("uart", ["нужны ROS 2 и", "топики /fmu/*?"], [
            ("да", Node("dds", ["uXRCE-DDS, TELEM2:", "все топики = 117 %", "от 921600"], [
                ("", Node("baud", ["3 Мбод (36 %) или", "смотреть Payload tx"], leaf=True, accent=True)),
            ])),
            ("нет", Node("mav", ["MAVLink, TELEM2:", "MAV_1_CONFIG = 102,", "Onboard, 46080 B/s"], leaf=True)),
            ("оба", Node("both", ["MAVLink — TELEM1/", "USB/ETH, DDS —", "TELEM2"], leaf=True)),
        ])),
    ])
    return tree("Канал Jetson ↔ PX4: на одном порту — один протокол", root, box_w=170, box_h=48, gap_y=78)


def build(D: dict) -> None:
    D["jetson-link-choice"] = link_tree()
