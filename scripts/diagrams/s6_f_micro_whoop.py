"""Stage 6 diagrams for module f-micro-whoop (whoops and micro: 1S physics, connectors, SPI ELRS).

chart-micro-connector-sag — the module's worked example (practice step 2): voltage seen by the board vs current for
                            one 1S cell (E = 3.90 V, 60 mOhm), 2 x 40 mm of 22 AWG and three connectors:
                            PH2.0 new (10 mOhm/contact, JST max), PH2.0 aged (20 mOhm), A30 (1.6 mOhm, GNB).
micro-elrs-spi-trap       — the ELRS version trap for SPI receivers: Betaflight 2025.12 speaks OTA version 3,
                            an ELRS 4.x transmitter speaks 4; the three ways out (svg.tree).
"""
from __future__ import annotations

from plot import Axis, chart
from svg import Node, tree

E, R_CELL, R_WIRE = 3.90, 0.060, 0.080 * 0.05296


def _line(r_contact: float):
    xs = [i * 0.5 for i in range(0, 25)]
    return xs, [E - i * (R_CELL + R_WIRE + 2 * r_contact) for i in xs]


def _i_at(v: float, r_contact: float) -> float:
    return (E - v) / (R_CELL + R_WIRE + 2 * r_contact)


def build(D: dict) -> None:
    xa, ya = _line(0.0016)
    xn, yn = _line(0.010)
    xo, yo = _line(0.020)
    D["chart-micro-connector-sag"] = chart(
        "1S под током: что видит плата через разные разъёмы",
        [dict(name="A30, 1.6 мОм", xs=xa, ys=ya, cls="a", label_at=11),
         dict(name="PH2.0 новый, 10 мОм", xs=xn, ys=yn, cls="m", label_at=9.5, label_dy=16),
         dict(name="PH2.0 изношенный, 20 мОм", xs=xo, ys=yo, cls="d", label_at=7, label_dy=18)],
        Axis("ток, А", 0, 12), Axis("напряжение на плате, В", 2.6, 4.0),
        marks=[(_i_at(3.3, 0.020), f"{_i_at(3.3, 0.020):.1f} А", "d", 30),
               (_i_at(3.3, 0.0016), f"{_i_at(3.3, 0.0016):.1f} А", "a", 30)],
        hmarks=[(3.5, "тревога 3.50 В (умолчание)", "w"), (3.3, "критический 3.30 В", "d")])

    leaf = lambda i, lines: Node(i, lines, leaf=True)
    D["micro-elrs-spi-trap"] = tree(
        "SPI-приёмник ELRS и версия протокола",
        Node("r", ["Betaflight 2025.12:", "SPI ELRS = OTA 3;", "пульт на ELRS 4.x = OTA 4", "→ связи нет"], [
            ("пульт", leaf("a", ["оставить 3.x", "или второй модуль", "на 3.x для вупов"])),
            ("приёмник", leaf("b", ["внешний ELRS", "по UART (CRSF),", "прошить 4.x;", "нужен свободный UART"])),
            ("прошивка", leaf("c", ["Betaflight 2026.6", "+ опция ELRSV4;", "с 3.x больше", "не работает"])),
        ], accent=True),
        width=720, box_w=190, box_h=78, gap_y=96)
