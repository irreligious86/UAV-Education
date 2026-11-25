"""Stage 6 diagrams for module tx-lua-widgets (EdgeTX 2.12.5 Lua widgets on colour radios).

edgetx-lua-script-types  — decision tree: which of the five EdgeTX script types (widget, telemetry, function,
                           mix, tool) a task needs, with the SD-card folder of each and the filename limits
                           from radio/src/dataconstants.h (6 characters for mix/telemetry, 8 for function).
edgetx-widget-lifecycle  — widget lifecycle from radio/src/lua/widgets.cpp, lua_widget_factory.cpp and
                           lua_widget.cpp: load at start, registration (name + create + options), create(zone,
                           options, path), update() on option/zone change (right after create only with useLvgl),
                           the 50 ms menu cycle (tasks.cpp MENU_TASK_PERIOD) that calls refresh() for a visible zone
                           and background() otherwise; an error in any function or the ~20 000 instruction limit
                           disables that widget instance until it is created again.
"""
from __future__ import annotations

from svg import Box, Node, flow, tree


def _types() -> str:
    root = Node("q", ["Что должен делать", "скрипт?"], [
        ("экран", Node("scr", ["Пульт цветной?"], [
            ("да", Node("wid", ["Widget", "/WIDGETS/<имя>/", "main.lua"], accent=True, leaf=True)),
            ("нет", Node("tel", ["Telemetry", "/SCRIPTS/TELEMETRY", "имя ≤ 6 симв."], leaf=True)),
        ])),
        ("тумблер", Node("fun", ["Function", "/SCRIPTS/FUNCTIONS", "имя ≤ 8 симв."], leaf=True)),
        ("канал", Node("mix", ["Mix", "/SCRIPTS/MIXES", "имя ≤ 6 симв."], leaf=True)),
        ("из меню", Node("tool", ["Tool", "/SCRIPTS/TOOLS", "файл или папка"], leaf=True)),
    ])
    return tree("EdgeTX 2.12: какой тип Lua-скрипта нужен", root, width=720, box_w=168, box_h=50, gap_y=80)


def _lifecycle() -> str:
    W, H = 160, 50
    xs = [10, 196, 382, 556]
    boxes = [
        Box("load", ["Старт пульта:", "/WIDGETS/*/main.lua"], xs[0], 40, W, H),
        Box("reg", ["Регистрация, если", "name, create, options"], xs[1], 40, W, H),
        Box("zone", ["Виджет выбран", "в зоне экрана"], xs[2], 40, W, H),
        Box("create", ["create(zone,", "options, path) → w"], xs[3], 40, W, H, accent=True),
        Box("upd", ["update(w, options):", "смена опций / зоны"], xs[3], 150, W, H),
        Box("cyc", ["Цикл меню", "каждые 50 мс"], xs[2], 150, W, H),
        Box("ref", ["refresh(w, event,", "touchState): рисует"], xs[1], 150, W, H, accent=True),
        Box("bg", ["background(w):", "lcd.* не рисует"], xs[1], 260, W, H),
        Box("err", ["Ошибка в любой ф-ции", "или > ~20 000 инстр."], xs[0], 150, W, H),
        Box("off", ["«ERROR in …» в зоне,", "до пересоздания"], xs[0], 260, W, H),
    ]
    links = [
        ("load", "reg", "", False, "h"),
        ("reg", "zone", "", False, "h"),
        ("zone", "create", "", False, "h"),
        ("create", "upd", "", False, "v"),
        ("upd", "cyc", "", False, "h"),
        ("cyc", "ref", "", True, "h"),
        ("cyc", "bg", "", False, "v"),
        ("ref", "err", "", False, "h"),
        ("err", "off", "", False, "v"),
    ]
    notes = [
        (10, 24, "Нет name, create или таблицы options — виджета нет в списке, ошибки тоже нет.", "m t"),
        (369, 142, "видна", "a t", "middle"),
        (500, 224, "не видна", "m t", "middle"),
        (556, 270, "LinkBox: до 393", "a t"),
        (556, 286, "инструкций main.lua", "a t"),
        (556, 302, "на вызов, 2 % бюджета", "a t"),
        (628, 124, "сразу после create —", "m t", "end"),
        (628, 138, "только с useLvgl", "m t", "end"),
        (10, 336, "event — число только в полноэкранном режиме, touchState — только при касании.", "m t"),
    ]
    return flow("Жизненный цикл Lua-виджета EdgeTX 2.12", boxes, links, 720, 350, notes=notes)


def build(D: dict) -> None:
    D["edgetx-lua-script-types"] = _types()
    D["edgetx-widget-lifecycle"] = _lifecycle()
