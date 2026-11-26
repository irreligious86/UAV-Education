"""Thin-module review diagram for eng-systems.

eng-verify-method-tree — choosing the verification method for a requirement with the four methods of the
                         NASA Systems Engineering Handbook §5.3 (inspection, analysis, demonstration, test),
                         in the order the module's text gives; SITL counts as analysis (modelling and
                         simulation), the leaves name the course's examples (REQ-SAF-03 / T-12 etc.).
"""
from __future__ import annotations

from svg import Node, tree


def build(D: dict) -> None:
    D["eng-verify-method-tree"] = tree(
        "Какой метод проверки у требования (NASA SEH §5.3)",
        Node("q1", ["Свойство видно или", "измеряется на готовом", "изделии без работы?"], children=[
            ("да", Node("ins", ["Осмотр (I)", "маркировка, разъёмы,", "комплектность по BOM"], leaf=True)),
            ("нет", Node("q2", ["Изделие можно", "безопасно запустить", "в нужных условиях?"], children=[
                ("нет", Node("ana", ["Анализ (A)", "расчёт, SITL-модель,", "бюджет линка"], leaf=True, accent=True)),
                ("да", Node("q3", ["Нужно число", "с допуском, а не", "только «работает»?"], children=[
                    ("нет", Node("dem", ["Демонстрация (D)", "арм по чек-листу,", "RTH-переключатель"], leaf=True)),
                    ("да", Node("tst", ["Испытание (T)", "ток висения на стенде,", "RTL в поле (T-31)"],
                                leaf=True, accent=True)),
                ])),
            ])),
        ]),
        width=720, box_w=170, box_h=50, gap_y=80)
