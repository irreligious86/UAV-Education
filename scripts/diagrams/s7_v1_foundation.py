"""Visual pass (stage 7), batch v1_foundation: one new diagram per foundation module, two for ops-maintenance.

chart-hover-throttle      f-physics — hover throttle u vs T/W from the module's thrust curve T = (1 - e)u + e·u²
                          (e = MOT_THST_EXPO = 0.65) against the pure square u = sqrt(f) and the thrust share f = 1/(T/W);
                          T/W < 2 shaded, the course 60 % stop line, the worked example T/W 4.1 -> 40 % (24–49 %).
motor-esc-selection       f-motors-esc — the module's worked selection chain: task -> thrust per motor -> motor table peak
                          current -> ESC current by the 1.3x rule (5": 38 A -> 49.4 A -> 45 A is 1.18x, 55–60 A; 7": 22 A).
fc-board-choice-tree      f-fc-sensors — the board selection rule of «Что ограничивает выбор платы»: target, navigation
                          firmware (baro + compass, >= 4 UART), SBUS on F4, VTOL / large -> H7, CAN, 8+ outputs.
preflight-go-nogo         f-safety — the printed pre-flight checklist as a go/no-go chain: any «нет» stops the sortie,
                          a strange hover after arming ends in a landing.
chart-fc-damper-window    f-frame-mech — the damper rule: f0 must be 3–5x below the lowest motor harmonic but above the
                          control band (>= 50–80 Hz); the window exists only from 150 Hz (240 Hz for the 80 Hz bound):
                          5" 250 Hz has 50–83 Hz (text picks 60–80), the 7" example 125, 10" 80, X8 55 Hz have none.
easa-open-category-tree   f-regulations — EU Open/Specific decision for a homemade (unmarked) aircraft from the module's
                          EASA text: BVLOS / over assemblies of people -> Specific (Reg. 2019/947 Art. 4), > 25 kg -> Specific, class mark -> by class,
                          < 250 g and < 19 m/s -> A1, else A3 (the worked 7" 1.4 kg).
crash-search-flow         ops-field — the downed-aircraft procedure: first minute, last known point (by accuracy),
                          inertia correction v·sqrt(2h/g) (20 m/s, 30 m -> 49 m), search pattern, 30–40 min decision;
                          battery budget 0.39 Ah x 22 V = 8.6 Wh / 10 W or 3 W.
eng-architecture-layers   eng-method-101 — the module's example architecture sheet: power layer (battery -> ESC, BEC 5 V,
                          BEC 9 V) and data layer (CRSF UART1, UBX UART2, DShot, MSP/OSD UART3, Blackbox).
chart-impact-energy       ops-case-studies — impact energies of the three cases (118, 13 700, 24 800 J) on a log scale
                          against the ~80 J serious-injury threshold; ratios computed.
inair-disarm-tree         diag-troubleshooting — tree 6: no disarm event -> power / brownout; disarm reason -> branch.
remote-id-data-path       f-remote-id-security — where the Remote ID broadcast comes from: autopilot -> module by
                          MAVLink/DroneCAN (OPEN_DRONE_ID_*), pilot position from the GCS, BT/Wi-Fi broadcast to a phone,
                          standalone beacon; module status gates arming on certified builds.
maint-inspection-timeline ops-maintenance — the inspection schedule against flight hours: every flight, after any impact,
                          bearings/frame 10–20 h, full teardown ~50 h; the module's 30 h bearing example -> inspections every 20 h
                          (hand-placed: axis ticks only, so no grid line crosses a label).
post-crash-recheck-flow   ops-maintenance — the post-crash checklist order: battery first and quarantine, mechanics,
                          wiring, then the props-off re-check steps 1–5 and the control hover.
"""
from __future__ import annotations

import math

from plot import Axis, chart
from svg import ACCENT, DANGER, INK, MUTED, WARN, Box, Node, esc, flow, svg, text, tree


# ---------------------------------------------------------------- helpers for hand-placed diagrams
def _rect(x, y, w, h, cls="box", rx=6, extra=""):
    return f'<rect class="{cls}" x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}"{extra}/>'


def _arrow(pts, cls="ln"):
    d = "M" + " L".join(f"{x} {y}" for x, y in pts)
    mk = "ara" if cls == "lna" else "ar"
    return f'<path class="{cls}" d="{d}" marker-end="url(#{mk})"/>'


def _lines(cx, cy, lines, cls="", size=None, lh=14, anchor="middle"):
    y0 = cy - (len(lines) - 1) * lh / 2 + 4
    return "".join(text(cx, y0 + i * lh, s, cls, anchor, size) for i, s in enumerate(lines))


def _add_footer(svg_str: str, lines: list[str], lh: int = 16) -> str:
    """Grow a helper-built SVG downwards and add muted footnote lines under it."""
    import re
    m = re.search(r'viewBox="0 0 (\d+(?:\.\d+)?) (\d+(?:\.\d+)?)"', svg_str)
    w, h = float(m.group(1)), float(m.group(2))
    nh = h + lh * len(lines) + 6
    body = "".join(text(16, h + 4 + lh * (i + 1) - 4, s, "m t", "start") for i, s in enumerate(lines))
    svg_str = svg_str.replace(m.group(0), f'viewBox="0 0 {w:g} {nh:g}"', 1)
    i = svg_str.rfind("</svg>")
    return svg_str[:i] + body + svg_str[i:]


# ---------------------------------------------------------------- f-physics
def _hover_u(f: float, e: float) -> float:
    return (-(1 - e) + math.sqrt((1 - e) ** 2 + 4 * e * f)) / (2 * e)


def hover_throttle() -> str:
    tws = [1.6 + 0.05 * i for i in range(169)]           # 1.6 … 10
    e = 0.65
    u_curve = [100 * _hover_u(1 / t, e) for t in tws]
    u_sq = [100 * math.sqrt(1 / t) for t in tws]
    f_share = [100 / t for t in tws]
    tw_ex = 4 * 1500 / 1450                                 # worked example: 4.14
    u_ex = 100 * _hover_u(1 / tw_ex, e)                     # 40 %
    lo, hi = 100 / tw_ex, 100 * math.sqrt(1 / tw_ex)        # 24 … 49 %
    tw60_sq = 1 / (0.60 ** 2)                               # 60 % by the square: T/W 2.78
    tw60_c = 1 / (0.65 * 0.6 ** 2 + 0.35 * 0.6)             # 60 % on the 0.65 curve: T/W 2.25 (text: 2.25–2.8)
    assert abs(u_ex - 40) < 1 and abs(lo - 24) < 1 and abs(hi - 49) < 1
    assert abs(tw60_sq - 2.78) < 0.01 and abs(tw60_c - 2.25) < 0.01
    return chart(
        "Газ висения от T/W: кривая тяги 0.65 между прямой f и квадратом",
        [dict(name="√f (тяга ∝ газ²)", xs=tws, ys=u_sq, cls="w", label_at=6.2, label_dy=-10, label_anchor="start"),
         dict(name="газ по кривой 0.65", xs=tws, ys=u_curve, cls="a", label_at=6.2, label_dy=-10, label_anchor="start"),
         dict(name="доля тяги f = 1/(T/W)", xs=tws, ys=f_share, cls="m", dash=True, label_at=6.2, label_dy=-10, label_anchor="start")],
        Axis("T/W (максимальная тяга / взлётный вес)", 1.6, 10, ticks=[2, 3, 4, 5, 6, 7, 8, 9, 10]),
        Axis("газ или доля тяги на висении, %", 0, 80, ticks=[0, 10, 20, 30, 40, 50, 60, 70, 80]),
        bands=[(1.6, 2.0, "")],
        hmarks=[(60, "60 % — стоп первого висения 5–7\"", "d")],
        marks=[(tw_ex, f"пример T/W {tw_ex:.1f}: газ {u_ex:.0f} % (полоса {lo:.0f}–{hi:.0f} %), f = {lo / 100:.2f}", "ink", 52)],
        notes=[(68, 300, "T/W < 2: запаса нет", "w"), (290, 300, "ArduPilot и PX4 показывают f, Betaflight и INAV — газ", "m")])


# ---------------------------------------------------------------- f-motors-esc
def motor_esc_selection() -> str:
    k = 1.3                                                  # rule from f-components-choice
    i5, esc5 = 38, 45
    need5 = k * i5                                           # 49.4 A
    i7 = 22
    need7 = k * i7                                           # 28.6 A
    tw7 = 4 * 1200 / 1400                                    # 3.4
    assert abs(need5 - 49.4) < 0.05 and abs(esc5 / i5 - 1.18) < 0.005 and abs(need7 - 28.6) < 0.05
    W = 720
    boxes = [
        Box("t5", ["5\" 6S, 700 г", "нужен T/W ≥ 5"], 10, 34, 160, 48),
        Box("th5", ["5 × 700 = 3500 г,", "≥ 875 г на мотор"], 190, 34, 160, 48),
        Box("m5", ["2207 1750KV, 5.1×3:", f"~1600 г при {i5} А"], 370, 34, 160, 48),
        Box("e5", [f"ESC ≥ 1.3 × {i5} А", f"= {need5:.1f} → ≥ 50 А"], 550, 34, 160, 48, accent=True),
        Box("x45", [f"45 А: запас {esc5 / i5:.2f}×", "— впритык"], 370, 124, 160, 44),
        Box("ok5", ["55–60 А —", "спокойнее"], 550, 124, 160, 44, accent=True),
        Box("t7", ["7\" 6S, 1.4 кг"], 10, 214, 150, 48),
        Box("m7", ["2806.5 1300KV, 7×3.5:", f"~1200 г при ~{i7} А"], 178, 214, 184, 48),
        Box("tw7", ["T/W = 4·1200/1400", f"= {tw7:.1f}"], 380, 214, 160, 48),
        Box("e7", [f"ESC ≥ 1.3 × {i7} А", f"= {need7:.1f} → 35–45 А"], 560, 214, 150, 48, accent=True),
    ]
    links = [("t5", "th5"), ("th5", "m5"), ("m5", "e5", "", True), ("e5", "x45", "мало", False, "v"),
             ("e5", "ok5", "", True, "v"), ("t7", "m7"), ("m7", "tw7"), ("tw7", "e7", "", True)]
    notes = [(10, 20, "Подбор: задача → тяга на мотор → пиковый ток по таблице тяги → ESC по правилу ≥ 1.3×", "m t"),
             (10, 290, "Разница KV у 5\" и 7\" — из-за момента на пропе (Kt = 60/(2π·KV))", "m t"),
             (10, 140, "45 А держит пик секундами,", "m t"), (10, 156, "но впритык в агрессивном", "m t"),
             (10, 172, "полёте на свежей АКБ", "m t")]
    return flow("Подбор мотора и ESC: от T/W к току регулятора", boxes, links, W, 300, notes=notes)


# ---------------------------------------------------------------- f-fc-sensors
def fc_board_choice() -> str:
    t = tree("Выбор платы FC: прошивка → навигация → порты и выходы", Node("tgt", ["Есть target нужной", "прошивки и версии?"], [
        ("нет", Node("other", ["Другая плата"], leaf=True)),
        ("да", Node("nav", ["Навигация: INAV,", "ArduPilot, PX4?"], [
            ("нет", Node("sbus", ["Betaflight: SBUS-", "приёмник на F4?"], [
                ("да", Node("inv", ["Порт с аппаратным", "инвертором (SBUS)"], leaf=True)),
                ("нет", Node("bf", ["F4/F7: любой UART", "под приёмник"], leaf=True)),
            ])),
            ("да", Node("baro", ["Нужны баро, компас,", "UART ≥ 4 (RX, GPS, VTX,", "companion). VTOL/большой?"], [
                ("нет", Node("std", ["Плата с баро,", "компасом, 4+ UART"], leaf=True)),
                ("да", Node("h7", ["H7: CAN (DroneCAN),", "выходов 8+"], leaf=True, accent=True)),
            ], accent=True)),
        ])),
    ]), width=720, box_w=166, box_h=46, gap_y=74)
    return _add_footer(t, ["Для любой ветки: ток BEC под нагрузку, размер и масса, крепление 30.5/20 мм"])


# ---------------------------------------------------------------- f-safety
def preflight_go_nogo() -> str:
    W = 720
    steps = [
        "Пропы: целые, затянуты, направление по схеме",
        "АКБ: без вздутий, 4.1–4.2 В/эл., ремень",
        "Антенны RC и VTX на месте, не в плоскости пропов",
        "Пульт: модель, ARM/PREARM выкл., failsafe-тест",
        "OSD: напряжение, LQ/RSSI, флагов нет",
        "Зона: люди вне 10–15 м (5\"), 30 м (тяжёлый)",
        "Арм → висение 0.5–1 м, 2–3 с: отклик, звук",
    ]
    x0, w, h, step, top = 20, 400, 38, 52, 34
    out = [text(16, 18, "Предполётная проверка: любое «нет» — не взлетаем", "m t", "start")]
    for i, s in enumerate(steps):
        y = top + i * step
        acc = i == len(steps) - 1
        out.append(_rect(x0, y, w, h, "boxa" if acc else "box"))
        out.append(text(x0 + 12, y + h / 2 + 4, f"{i + 1}. {s}", "b" if acc else "", "start", 11.5))
        out.append(_arrow([(x0 + w / 2, y + h), (x0 + w / 2, y + step - 1)], "lna" if acc else "ln"))
        if i < len(steps) - 1:
            out.append(_arrow([(x0 + w, y + h / 2), (536, y + h / 2)], "ln"))
            out.append(text(x0 + w + 40, y + h / 2 - 5, "нет", "d t", "middle", 10))
    rail_y0, rail_y1 = top, top + (len(steps) - 2) * step + h
    out.append(_rect(540, rail_y0, 170, rail_y1 - rail_y0, "box", 8, f' style="stroke:{DANGER};stroke-width:1.6"'))
    out.append(_lines(625, (rail_y0 + rail_y1) / 2, ["СТОП", "не взлетаем:", "устранить причину,", "пункт заново"], "", 11.5, 16))
    y7 = top + (len(steps) - 1) * step
    out.append(_arrow([(x0 + w, y7 + h / 2), (536, y7 + h / 2)], "ln"))
    out.append(text(x0 + w + 58, y7 + h / 2 - 5, "странность", "w t", "middle", 10))
    out.append(_rect(540, y7, 170, h, "box", 18, f' style="stroke:{WARN};stroke-width:1.6"'))
    out.append(text(625, y7 + h / 2 + 4, "посадка", "", "middle", 11.5))
    yf = top + len(steps) * step
    out.append(_rect(x0, yf, w, h, "boxa", 18))
    out.append(text(x0 + w / 2, yf + h / 2 + 4, "Полёт", "b"))
    H = yf + h + 30
    out.append(text(16, H - 10, "Флаг или PreArm — устранить причину, а не отключать проверку", "m t", "start"))
    return svg(W, H, "Предполётная проверка: идти дальше или стоп", "".join(out))


# ---------------------------------------------------------------- f-frame-mech
def damper_window() -> str:
    fs = [40 + 2 * i for i in range(181)]                    # 40 … 400 Hz
    up = [f / 3 for f in fs]
    dn = [f / 5 for f in fs]
    f_open_50 = 50 * 3                                       # f/3 = 50 -> 150 Hz
    f_open_80 = 80 * 3                                       # 240 Hz
    win5 = (max(50, 250 / 5), 250 / 3)                       # 50 … 83 Hz for 5" (text: 60–80)
    assert f_open_50 == 150 and abs(win5[1] - 83.3) < 0.1
    return chart(
        "Демпферы FC: окно f₀ = гармоника/5 … /3, но не ниже полосы управления",
        [dict(name="f₀ = f/3", xs=fs, ys=up, cls="a", label_at=380, label_dy=-8),
         dict(name="f₀ = f/5", xs=fs, ys=dn, cls="a", dash=True, label_at=190, label_dy=18, label_anchor="start")],
        Axis("самая низкая гармоника моторов на висении, Гц", 40, 400, ticks=[50, 100, 150, 200, 250, 300, 350, 400]),
        Axis("собственная частота крепления f₀, Гц", 0, 140, ticks=[0, 20, 40, 60, 80, 100, 120, 140]),
        bands=[(40, f_open_50, "окна нет: баланс, notch")],
        hmarks=[(50, "полоса управления 50 Гц", "d"), (80, "80 Гц", "d")],
        marks=[(55, "X8 55", "m", 44), (80, "10\" 80", "m", 60), (125, "7\" 125 (пример)", "m", 76),
               (250, f"5\" 250: окно {win5[0]:.0f}–{win5[1]:.0f} Гц, берут 60–80", "ink", 44)],
        notes=[(462, 292, "окно — с 150 Гц (с 240 Гц при 80)", "m")])


# ---------------------------------------------------------------- f-regulations
def easa_open_tree() -> str:
    return tree("ЕС: Open или Specific (самодельный аппарат — без маркировки класса C)", Node("op", ["BVLOS или над", "скоплениями людей?"], [
        ("да", Node("spec1", ["Specific:", "SORA или STS"], leaf=True)),
        ("нет", Node("m25", ["Взлётная масса", "< 25 кг?"], [
            ("нет", Node("spec2", ["Specific"], leaf=True)),
            ("да", Node("cls", ["Маркировка", "класса C есть?"], [
                ("да", Node("bycls", ["Open: подкатегория", "по классу C0–C4"], leaf=True)),
                ("нет", Node("m250", ["< 250 г и", "< 19 м/с?"], [
                    ("да", Node("a1", ["Open A1"], leaf=True, accent=True)),
                    ("нет", Node("a3", ["Open A3: ≥ 150 м от", "зон, вдали от людей;", "7\" 1.4 кг — здесь"], leaf=True, accent=True)),
                ])),
            ])),
        ])),
    ]), width=720, box_w=150, box_h=46, gap_y=72)


# ---------------------------------------------------------------- ops-field
def crash_search() -> str:
    g = 9.81
    over20 = 20 * math.sqrt(2 * 30 / g)                      # 49.5 m
    wh = 0.39 * 22                                           # 8.6 Wh
    t_dig, t_min = wh / 10, wh / 3                           # 0.86 h, 2.9 h
    assert abs(over20 - 50) < 1 and abs(wh - 8.6) < 0.05
    W = 720
    boxes = [
        Box("s1", ["1. Дизарм. Пилот:", "ориентир вслух,", "никто не бежит"], 10, 34, 160, 58),
        Box("s2", ["2. Пульт включён:", "координаты,", "BEEPER"], 190, 34, 160, 58),
        Box("s3", ["3. DVR: стоп записи,", "последние кадры"], 370, 34, 160, 58),
        Box("s4", ["4. Время падения,", "остаток АКБ"], 550, 34, 160, 58),
        Box("pt", ["Последняя точка:", "телеметрия → OSD", "→ tlog → курс"], 550, 134, 160, 70, accent=True),
        Box("in", ["+ инерция v·√(2h/g):", f"20 м/с, 30 м ≈ {round(over20, -1):.0f} м", "вперёд по курсу"], 370, 134, 160, 70, accent=True),
        Box("pat", ["Полоса по курсу →", "спираль; тишина", "10–15 с / 20–30 м"], 190, 134, 160, 70),
        Box("dec", ["Нашли: подход сбоку,", "сразу отключить АКБ;", "нет за 30–40 мин —", "решение старшего"], 10, 134, 160, 70, accent=True),
    ]
    links = [("s1", "s2"), ("s2", "s3"), ("s3", "s4"), ("s4", "pt", "", False, "v"), ("pt", "in", "", True),
             ("in", "pat", "", True), ("pat", "dec")]
    notes = [(10, 20, "Поиск упавшего аппарата: первая минута → последняя точка → схема поиска", "m t"),
             (10, 232, f"Бюджет АКБ: 6S, 30 % от 1300 мА·ч = 0.39 А·ч × 22 В ≈ {wh:.1f} Вт·ч — с цифровым видео (10 Вт)", "m t"),
             (10, 248, f"≈ {t_dig * 60:.0f} мин, только FC + RX + GPS + пищалка (3 Вт) ≈ {t_min:.1f} ч; шаг галсов 5–10 м в траве", "m t")]
    return flow("Поиск упавшего аппарата", boxes, links, W, 262, notes=notes)


# ---------------------------------------------------------------- eng-method-101
def architecture_layers() -> str:
    W, H = 720, 330
    bw, bh = 120, 46
    B = {  # id: (x, y, w, lines, accent)
        "bat": (20, 120, 110, ["АКБ"], False),
        "esc": (200, 30, bw, ["ESC ×4"], False),
        "b5": (200, 120, bw, ["BEC 5 В"], False),
        "b9": (200, 210, bw, ["BEC 9 В"], False),
        "fc": (400, 120, 130, ["FC"], True),
        "fl": (400, 210, 130, ["Флеш"], False),
        "rx": (590, 30, bw, ["Приёмник"], False),
        "gps": (590, 120, bw, ["GPS + компас", "на мачте"], False),
        "vtx": (590, 210, bw, ["VTX"], False),
    }
    out = [text(16, 18, "Архитектура на одном листе: питание — тонкие, данные — цветные", "m t", "start")]
    for k, (x, y, w, lines, acc) in B.items():
        out.append(_rect(x, y, w, bh, "boxa" if acc else "box"))
        out.append(_lines(x + w / 2, y + bh / 2, lines, "b" if acc else "", 11.5, 13))
    # power layer
    out.append(_arrow([(130, 135), (165, 135), (165, 53), (200, 53)]))
    out.append(_arrow([(130, 143), (200, 143)]))
    out.append(_arrow([(130, 151), (165, 151), (165, 233), (200, 233)]))
    out.append(_arrow([(320, 143), (400, 143)]))
    out.append(text(360, 137, "5 В", "t", "middle", 10))
    out.append(text(360, 170, "→ FC, RX, GPS", "m t", "middle", 10))
    out.append(_arrow([(260, 256), (260, 284), (650, 284), (650, 260)]))
    out.append(text(455, 278, "9 В", "t", "middle", 10))
    # data layer
    out.append(_arrow([(440, 120), (440, 90), (330, 90), (330, 53), (324, 53)], "lna"))
    out.append(text(385, 84, "DShot", "a t", "middle", 10))
    out.append(_arrow([(590, 53), (560, 53), (560, 133), (534, 133)], "lna"))
    out.append(text(566, 100, "CRSF · UART1", "a t", "start", 10))
    out.append(_arrow([(590, 148), (534, 148)], "lna"))
    out.append(text(560, 162, "UBX", "a t", "middle", 10))
    out.append(text(560, 174, "UART2", "a t", "middle", 10))
    out.append(_arrow([(515, 166), (515, 186), (575, 186), (575, 228), (586, 228)], "lna"))
    out.append(text(569, 202, "MSP/OSD · UART3", "a t", "end", 10))
    out.append(_arrow([(440, 166), (440, 206)], "lna"))
    out.append(text(434, 192, "Blackbox", "a t", "end", 10))
    out.append(text(16, H - 14, "Ток подписать на каждой стрелке питания — своими числами; решение — одной фразой («GPS на мачте —", "m t", "start"))
    out.append(text(16, H - 1, "компас подальше от силовых»)", "m t", "start"))
    return svg(W, H + 6, "Архитектура дрона: слои питания и данных", "".join(out))


# ---------------------------------------------------------------- ops-case-studies
def impact_energy() -> str:
    W = 720
    L, R, top, row = 230, 655, 54, 62
    lo, hi = 10, 100000
    X = lambda v: L + (math.log10(v) - math.log10(lo)) / (math.log10(hi) - math.log10(lo)) * (R - L)
    thr = 80
    cases = [("Matternet M2, 2019", "без груза; 50 м от детей", 118),
             ("Freefly Alta X, 2022", "28 кг, ≈ 30 м/с; удар в лодку", 13700),
             ("Airspeeder Mk II, 2019", "95 кг; 40 м от домов", 24800)]
    H = top + len(cases) * row + 50
    out = [text(16, 20, "Энергия удара трёх аварий против порога серьёзной травмы (лог. шкала)", "b", "start", 13)]
    for v in (10, 100, 1000, 10000, 100000):
        out.append(f'<line x1="{X(v):.1f}" y1="{top - 10}" x2="{X(v):.1f}" y2="{H - 40}" stroke="{MUTED}" stroke-width="0.5" opacity="0.5"/>')
        out.append(text(X(v), H - 26, f"{v:,}".replace(",", " ") + " Дж", "m t"))
    for i, (name, sub, e) in enumerate(cases):
        y = top + i * row
        out.append(text(L - 10, y + 14, name, "", "end", 11.5))
        out.append(text(L - 10, y + 30, sub, "m t", "end", 10))
        out.append(f'<rect x="{X(lo):.1f}" y="{y + 4}" width="{X(e) - X(lo):.1f}" height="26" rx="3" fill="{WARN if e < 1000 else DANGER}" opacity="0.55"/>')
        lab = f"{e:,}".replace(",", " ") + f" Дж = {e / thr:.1f}× порога" if e < 1000 else f"{e:,}".replace(",", " ") + f" Дж = {e / thr:.0f}×"
        if X(e) + 8 + 7 * len(lab) < W - 4:
            out.append(text(X(e) + 6, y + 22, lab, "t b", "start"))
        else:
            out.append(text(X(e) - 6, y + 22, lab, "t b", "end"))
    out.append(f'<line x1="{X(thr):.1f}" y1="{top - 14}" x2="{X(thr):.1f}" y2="{H - 40}" stroke="{INK}" stroke-width="1.6" stroke-dasharray="5 3"/>')
    out.append(text(X(thr) + 4, top - 18, "~80 Дж — порог серьёзной травмы", "t", "start"))
    out.append(text(16, H - 6, "Пострадавших нет во всех трёх — везение: лёгкий аппарат опасен, тяжёлый смертелен", "m t", "start"))
    return svg(W, H, "Энергия удара в трёх разобранных авариях", "".join(out))


# ---------------------------------------------------------------- diag-troubleshooting
def inair_disarm_tree() -> str:
    return tree("Дерево 6: отключение в воздухе — сначала лог, потом ветка", Node("log", ["Лог скопирован до включения.", "Событие дизарма есть?"], [
        ("нет", Node("pwr", ["Нет дизарма:", "питание, brownout,", "VBAT, POWR.VCC"], leaf=True)),
        ("да", Node("rsn", ["Причина дизарма", "записана в логе"], [
            ("", Node("fs", ["Failsafe:", "связь — дерево 5,", "что настроено"], leaf=True)),
            ("", Node("sw", ["Тумблер, стики:", "тумблер", "с фиксацией"], leaf=True)),
            ("", Node("det", ["Runaway, crash:", "причина выше —", "мотор/ESC/desync"], leaf=True)),
            ("", Node("ekf", ["EKF, GPS:", "XKF4, VIBE,", "спутники, компас"], leaf=True)),
            ("", Node("auto", ["Автодизарм:", "газ 0, касание,", "пауза после арма"], leaf=True)),
        ])),
    ], accent=True), width=720, box_w=190, box_h=50, gap_y=80)


# ---------------------------------------------------------------- f-remote-id-security
def remote_id_path() -> str:
    boxes = [
        Box("gcs", ["Наземка", "координаты пилота"], 10, 40, 140, 50),
        Box("fc", ["Автопилот", "ArduPilot / PX4", "позиция, высота"], 200, 34, 160, 62, accent=True),
        Box("mod", ["Модуль Remote ID", "ArduRemoteID", "(ESP32-S3/C3), Cube ID"], 480, 34, 190, 62, accent=True),
        Box("bc", ["Отдельный маячок", "свой GPS и батарея"], 10, 150, 150, 50),
        Box("air", ["Широковещание: BT 4 legacy,", "BT 5 LR, Wi-Fi NAN/Beacon"], 440, 150, 270, 50),
        Box("ph", ["Смартфон рядом", "без интернета"], 500, 250, 150, 46),
    ]
    links = [("gcs", "fc", "SYSTEM"), ("fc", "mod", "BASIC_ID, LOCATION", True), ("mod", "fc", "статус → PreArm"),
             ("mod", "air", "", True, "v"), ("bc", "air"), ("air", "ph", "", False, "v")]
    notes = [(10, 20, "Remote ID: OPEN_DRONE_ID_* по MAVLink или DroneCAN, трансляция без сервера", "m t"),
             (10, 236, "Сертифицированная сборка ArduPilot:", "m t"), (10, 252, "без рабочего Remote ID нет арма —", "m t"),
             (10, 268, "искать в PreArm, а не в моторах", "m t")]
    return flow("Remote ID: откуда берутся данные трансляции", boxes, links, 720, 310, notes=notes)


# ---------------------------------------------------------------- ops-maintenance
def inspection_timeline() -> str:
    """Hand-placed timeline: axis ticks only (no grid through labels), interval example drawn as ticks."""
    W, pad_l, pad_r, top, lane_h, t_max = 720, 150, 24, 44, 40, 50
    X = lambda t: pad_l + (W - pad_l - pad_r) * t / t_max
    life, interval = 30, 20                                  # the module's example: bearings die at 30 h -> 20 h
    assert interval < life
    lanes = ["Каждый полёт", "После удара", "Каждые 10–20 ч", "Пример журнала", "~50 ч, сезон"]
    ax = top + len(lanes) * lane_h + 4
    H = ax + 26
    out = [text(16, 18, "Регламент осмотров по налёту: интервалы стартовые, свои — по журналу", "m t", "start")]
    out.append(f'<line class="lnm" x1="{X(0):.1f}" y1="{ax}" x2="{X(t_max):.1f}" y2="{ax}"/>')
    for k in range(0, 6):
        t = 10 * k
        out.append(f'<line class="lnm" x1="{X(t):.1f}" y1="{ax - 4}" x2="{X(t):.1f}" y2="{ax + 4}"/>')
        out.append(text(X(t), ax + 18, f"{t} ч", "m t", size=11))
    for i, name in enumerate(lanes):
        out.append(text(pad_l - 10, top + i * lane_h + 24, name, "", "end", 11.5))

    def bar(i, t0, t1, label, cls="box", tcls="", anchor="middle"):
        y = top + i * lane_h + 6
        out.append(_rect(X(t0), y, X(t1) - X(t0), lane_h - 12, cls, 4))
        tx = (X(t0) + X(t1)) / 2 if anchor == "middle" else X(t0) + 10
        out.append(text(tx, y + (lane_h - 12) / 2 + 4, label, tcls, anchor, 11))
    bar(0, 0, 50, "до: винты, АКБ, антенны · после: нагрев моторов и ESC, журнал")
    bar(1, 0, 50, "в любой момент: чек-лист после аварии, все винты — замена")
    bar(2, 10, 20, "подшипники", "boxa", "b")
    out.append(text(X(20) + 8, top + 2 * lane_h + 24, "+ винты рамы, пайка, демпферы FC", "m t", "start", 11))
    bar(3, 0, life, f"подшипники умирают за {life} ч", anchor="start")
    for t in (interval, 2 * interval):
        x = X(t)
        y = top + 3 * lane_h + 3
        out.append(f'<path d="M{x:.1f} {y} L{x:.1f} {y + lane_h - 6}" stroke="{ACCENT}" stroke-width="2.4"/>')
    out.append(text(X(2 * interval) + 8, top + 3 * lane_h + 24, f"осмотр: шаг {interval} ч", "a t", "start", 11))
    bar(4, 43, 50, "разборка", "boxa", "b")
    out.append(text(X(43) - 8, top + 4 * lane_h + 24, "проводка, изоляция, разъёмы питания, прошивка", "m t", "end", 11))
    return svg(W, H, "Регламент осмотров по налёту", "".join(out))


def post_crash_flow() -> str:
    boxes = [
        Box("bat", ["АКБ первой:", "оболочка, нагрев,", "банки сразу и 30 мин"], 10, 34, 160, 58, accent=True),
        Box("q", ["Карантин ≥ 15 мин,", "журнал «удар»"], 190, 34, 160, 58),
        Box("mech", ["Рама, лучи,", "диагонали, моторы,", "все пропы"], 370, 34, 160, 58),
        Box("wire", ["Проводка, разъёмы,", "стек, антенны, GPS"], 550, 34, 160, 58),
        Box("ss", ["Пропы сняты,", "smoke stopper"], 550, 134, 160, 58),
        Box("cal", ["Горизонт 0, каналы,", "failsafe"], 370, 134, 160, 58),
        Box("mot", ["Моторы по одному,", "все 20–30 с: шум", "≤ логов до аварии"], 190, 134, 160, 58),
        Box("hov", ["Новые пропы: висение", "30–60 с на 1–2 м,", "лог против тренда"], 10, 134, 160, 58, accent=True),
    ]
    links = [("bat", "q"), ("q", "mech"), ("mech", "wire"), ("wire", "ss", "", False, "v"), ("ss", "cal"),
             ("cal", "mot"), ("mot", "hov", "", True)]
    notes = [(10, 20, "После аварии: порядок проверки; любой критерий «не летать» — аппарат на земле", "m t"),
             (10, 222, "Запись в журнал: что случилось, что заменено (серийники), результат висения, номер АКБ в карантине", "m t")]
    return flow("Чек-лист после аварии: порядок", boxes, links, 720, 236, notes=notes)


def build(D: dict) -> None:
    D["chart-hover-throttle"] = hover_throttle()
    D["motor-esc-selection"] = motor_esc_selection()
    D["fc-board-choice-tree"] = fc_board_choice()
    D["preflight-go-nogo"] = preflight_go_nogo()
    D["chart-fc-damper-window"] = damper_window()
    D["easa-open-category-tree"] = easa_open_tree()
    D["crash-search-flow"] = crash_search()
    D["eng-architecture-layers"] = architecture_layers()
    D["chart-impact-energy"] = impact_energy()
    D["inair-disarm-tree"] = inair_disarm_tree()
    D["remote-id-data-path"] = remote_id_path()
    D["maint-inspection-timeline"] = inspection_timeline()
    D["post-crash-recheck-flow"] = post_crash_flow()
