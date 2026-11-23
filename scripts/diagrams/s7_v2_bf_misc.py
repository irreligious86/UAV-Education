"""Visual pass (stage 7), batch v2_bf_misc: one new diagram per module (Betaflight, aero-wing, telemetry radios,
sensors, GNSS).

chart-failsafe-landing-time  bf-failsafe — the module's rule failsafe_landing_time >= h_max / v x 1.5 for the three
                             descent rates of the self-check (0.7, 1, 1.5 m/s) plus the stopwatch margin 2 at 1 m/s;
                             the 250 s parameter limit, the default 60 s, the worked 30 m @ 1 m/s -> 45 s and the
                             7" LR 150 m -> 225 s («почти предел»).
bf-serial-valid-tree         bf-ports — isSerialConfigValid() in io/serial.c as the module states it: MSP on VCP and
                             <= 3 MSP ports; one function per port, or MSP + telemetry / Blackbox / VTX (DisplayPort),
                             or Serial RX + FrSky Hub / LTM / MAVLink telemetry on the TX line; else the whole port
                             config is reset at boot. VTX_MSP alone on a port is invalid too (bitCount == 1 check).
chart-blackbox-flash-minutes bf-blackbox — minutes until the flash is full, t = size / stream (1 MB = 1024 KB), for
                             16, 8 and 2 MB over 40–120 KB/s; the module's 60–100 KB/s band for 2 kHz with all fields;
                             the self-check numbers 16 MB: 4.6 / 3.4 / 2.7 min, 8 MB @ 80: 102 s, 2 MB @ 80: 26 s.
bf-aux-ranges                bf-modes-osd — the worked team layout drawn on the 900–2100 us AUX axis: ARM, PREARM,
                             the three-position AUX3 (ACRO / ANGLE / HORIZON at 900–1300 / 1300–1700 / 1700–2100),
                             FAILSAFE and BEEPER; switch positions ~988 / 1500 / 2012 us (CRSF scaling in rx/crsf.c)
                             and the 200–312 us distance to the range edge (hand-placed: no grid through labels).
bf-migrate-line-tree         bf-intro — what to do with each line of an old 4.5.3 diff all after the upgrade, from the
                             module's migration checklist and table: board not in the 2025.12 target list -> stay on 4.5.x; name gone ->
                             renamed (new name, units: failsafe_off_delay / 10) or removed (INVALID NAME); name kept but
                             meaning changed (d_*, iterm_windup, osd_warn_bitmask, beeper) -> set again; else carry over.
                             Footer: item 6 — D and GPS Rescue throttle are set again even under the new name.
bf-diff-scopes               bf-cli — which parts of the config each diff variant writes (printConfig() table of the
                             module): plain diff takes only the active PID and rate profile; only diff all takes all
                             4 + 4, mcu_id/signature and the defaults nosave / save wrapper.
bf-custom-verify-flow        bf-custom — the module's six checks after a custom build, each with the cause the module
                             names when it fails (receiver protocol not built, HD OSD not built, no SERVOS -> no servo/smix).
bf-cli-apply-verify          bf-cli-automation — Step 2 / Step 4 of the practice as a flow: backup diff all -> set -> save
                             (reboot) -> find_craft again -> get each key -> OK / FAIL -> diff all after -> git diff shows
                             exactly CHANGES; the two failure exits as the module explains them.
chart-wing-stall-bank        aero-wing — V_s(phi) = V_s / sqrt(cos phi) for the worked wing (0.4 m², 2 kg, C_Lmax 1.1 ->
                             8.5 m/s) against AIRSPEED_MIN = 1.2 V_s and cruise 1.4 V_s; 45° -> 10.1 m/s, the crossings
                             46° and 59°, 60° -> +41 %. AIRSPEED_MIN / cruise labels on the left, clear of the curve.
chart-elrs-param-download    link-telemetry-radios — t = N·L/B for PARAM_VALUE (L = 37 B) over N parameters for the
                             ELRS downlink capacities of the module's table (F1000 2375, 333Hz Full 1470, 250Hz 590,
                             50Hz 110 B/s); N = 1000 -> 15.6 / 25.2 / 62.7 / 336 s. Log-log axes: t ∝ N gives parallel
                             straight lines, the gap between modes is the constant capacity ratio.
compass-cal-choice-tree      est-sensors — the module's compass calibration choice (ArduPilot column): can the vehicle be
                             rotated, does |MAG| change with throttle -> rotation cal (COMPASS_CAL_FIT 16), + CompassMot
                             or MagFit, Large Vehicle MagCal, Large Vehicle MagCal + CompassMot or MagFit; footer: acceptance numbers and INAV.
gnss-rtk-choice-tree         est-gnss — «Когда нужен RTK» as a tree: ~2 m is enough -> no RTK; centimetres in real time ->
                             RTK (own base 10–20 km: fix 1–3 cm; NTRIP 50–100 km: 1 ppm, slower); centimetres after the
                             flight -> PPK; yaw without a compass -> moving baseline (GPS1_TYPE 17 / GPS2_TYPE 18).
"""
from __future__ import annotations

import math

from plot import Axis, chart
from svg import ACCENT, DANGER, INK, MUTED, WARN, Box, Node, flow, svg, text, tree


# ---------------------------------------------------------------- helpers for hand-placed diagrams
def _rect(x, y, w, h, cls="box", rx=6, extra=""):
    return f'<rect class="{cls}" x="{x:.1f}" y="{y}" width="{w:.1f}" height="{h}" rx="{rx}"{extra}/>'


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


# ---------------------------------------------------------------- bf-failsafe
def failsafe_landing_time() -> str:
    hs = [2 * i for i in range(0, 101)]                      # 0 … 200 m
    k = 1.5
    t = lambda h, v, kk=k: h / v * kk
    assert t(30, 1) == 45 and t(150, 1) == 225                # module: 45 s; 225 s «почти предел 250»
    assert round(t(30, 1.5)) == 30 and round(t(30, 0.7)) == 64   # self-check: 30 s; «нужно 65 с» (64.3, rounded up)
    h_lim = 250 / k                                           # 1 m/s: the limit is reached at 167 m
    return chart(
        "failsafe_landing_time ≥ h_max / v × 1.5: сколько секунд дать AUTO-LAND",
        [dict(name="v = 0.7 м/с", xs=hs, ys=[t(h, 0.7) for h in hs], cls="w", label_at=90, label_dy=-8, label_anchor="end"),
         dict(name="v = 1 м/с", xs=hs, ys=[t(h, 1.0) for h in hs], cls="a", label_at=110, label_dy=18, label_anchor="start"),
         dict(name="v = 1.5 м/с", xs=hs, ys=[t(h, 1.5) for h in hs], cls="ink", label_at=120, label_dy=16, label_anchor="start"),
         dict(name="", xs=[30, 150], ys=[45, 225], cls="ink", dots=True)],
        Axis("h_max — наибольшая рабочая высота, м", 0, 200, ticks=[0, 25, 50, 75, 100, 125, 150, 175, 200]),
        Axis("failsafe_landing_time, с", 0, 280, ticks=[0, 50, 100, 150, 200, 250]),
        bands=[(h_lim, 200, "")],
        hmarks=[(250, "", "d"), (60, "умолчание 60 с", "m")],
        marks=[(30, "30 м, 1 м/с → 45 с (шаг 2)", "ink", 20), (150, "", "ink")],
        # labels placed off the curves: the 250 s label right of the 0.7 m/s crossing, the band text under the 1.5 m/s line
        notes=[(448, 60, "предел 250 с", "d"), (440, 86, "150 м → 225 с", ""),
               (598, 170, "при 1 м/с", "w"), (598, 184, "выше 250 с:", "w"), (598, 198, "AUTO-LAND", "w"),
               (598, 212, "не годится", "w"), (598, 226, "→ GPS-RESCUE", "w"),
               (200, 290, "по секундомеру — запас 2 вместо 1.5", "m")])


# ---------------------------------------------------------------- bf-ports
def serial_valid_tree() -> str:
    t = tree("Конфигурация портов валидна? (isSerialConfigValid, io/serial.c)", Node("msp", ["MSP на USB VCP есть и", "портов с MSP ≤ 3", "(вместе с VCP)?"], [
        ("нет", Node("bad1", ["Невалидно: при", "загрузке все порты", "→ умолчания"], leaf=True)),
        ("да", Node("one", ["На порту", "одна функция?"], [
            ("да", Node("ok1", ["OK; но VTX_MSP", "один — невалидно:", "только в паре с MSP"], leaf=True, accent=True)),
            ("нет", Node("mspsh", ["MSP + телеметрия,", "Blackbox или VTX", "(DisplayPort)?"], [
                ("да", Node("ok2", ["OK: 131073 =", "MSP + VTX_MSP"], leaf=True, accent=True)),
                ("нет", Node("rxsh", ["Serial RX + FrSky Hub,", "LTM или MAVLink", "на TX-линии?"], [
                    ("да", Node("ok3", ["OK: SBUS на RX,", "телеметрия на TX"], leaf=True, accent=True)),
                    ("нет", Node("bad2", ["Невалидно: сброс", "всех портов"], leaf=True)),
                ])),
            ])),
        ])),
    ], accent=True), width=720, box_w=150, box_h=48, gap_y=74)
    return _add_footer(t, ["Проверяется каждый порт; одного невалидного хватает, чтобы пропал приёмник (флаг RXLOSS)",
                           "SoftSerial: MSP и Serial RX на нём снимаются сами, скорость ≤ 19200"])


# ---------------------------------------------------------------- bf-blackbox
def blackbox_flash_minutes() -> str:
    rates = [40 + i for i in range(81)]                      # 40 … 120 KB/s
    mins = lambda mb, r: mb * 1024 / r / 60
    assert [round(mins(16, r), 1) for r in (60, 80, 100)] == [4.6, 3.4, 2.7]
    assert round(mins(8, 80) * 60) == 102 and round(mins(2, 80) * 60) == 26
    return chart(
        "Blackbox: сколько минут влезает во flash (t = объём / поток)",
        [dict(name="16 МБ", xs=rates, ys=[mins(16, r) for r in rates], cls="a", label_at=118, label_dy=-8),
         dict(name="8 МБ", xs=rates, ys=[mins(8, r) for r in rates], cls="ink", label_at=118, label_dy=-8),
         dict(name="2 МБ", xs=rates, ys=[mins(2, r) for r in rates], cls="w", label_at=118, label_dy=-8)],
        Axis("поток лога, КБ/с", 40, 120, ticks=[40, 50, 60, 70, 80, 90, 100, 110, 120]),
        Axis("до заполнения, мин", 0, 7, ticks=[0, 1, 2, 3, 4, 5, 6, 7]),
        bands=[(60, 100, "2 кГц, все поля: 60–100 КБ/с")],
        marks=[(80, "80 КБ/с: 16 МБ — 3.4 мин,", "ink", 46)],
        notes=[(384, 96, "8 МБ — 102 с, 2 МБ — 26 с", ""), (580, 150, "SD-карта — часы", "m")])


# ---------------------------------------------------------------- bf-modes-osd
def aux_ranges() -> str:
    W, pad_l, pad_r, top, lane_h = 720, 150, 24, 58, 40
    lo, hi = 900, 2100
    X = lambda us: pad_l + (W - pad_l - pad_r) * (us - lo) / (hi - lo)
    # CRSF scaling in rx/crsf.c: 172 -> 988 us, 992 -> 1500 us, 1811 -> 2012 us (±100 % on the radio)
    # code: 0.62477120195241 * v + 881 (float), isRangeActive() in fc/rc_modes.c casts to uint16 -> truncation
    crsf = lambda v: int(0.62477120195241 * v + 881)
    pos = [crsf(172), crsf(992), crsf(1811)]
    assert pos == [988, 1500, 2012]
    gaps = [1300 - pos[0], pos[1] - 1300, 1700 - pos[1], pos[2] - 1700]
    assert gaps == [312, 200, 200, 312]
    lanes = [("AUX1", [(1700, 2100, "ARM", True)]),
             ("AUX8 (7\"+)", [(1700, 2100, "PREARM", True)]),
             ("AUX3", [(900, 1300, "ACRO: ничего", False), (1300, 1700, "ANGLE", True), (1700, 2100, "HORIZON", True)]),
             ("AUX6", [(1700, 2100, "FAILSAFE", True)]),
             ("AUX7", [(1700, 2100, "BEEPER", True)])]
    ax = top + len(lanes) * lane_h + 6
    out = [text(16, 18, "Раскладка команды на оси AUX: режим активен, пока канал внутри своего диапазона", "m t", "start")]
    out.append(text(pad_l - 10, 44, "положение тумблера", "m t", "end", 10))
    for us in pos:
        out.append(f'<path d="M{X(us):.1f} {top - 10} L{X(us):.1f} {ax}" stroke="{ACCENT}" stroke-width="1.4" stroke-dasharray="3 3"/>')
        out.append(text(X(us), 44, f"≈{us}", "a t", "middle", 10))
    for i, (name, segs) in enumerate(lanes):
        y = top + i * lane_h + 6
        out.append(text(pad_l - 10, y + 18, name, "", "end", 11.5))
        for a, b, label, acc in segs:
            out.append(_rect(X(a) + 1, y, X(b) - X(a) - 2, lane_h - 12, "boxa" if acc else "box", 4))
            out.append(text((X(a) + X(b)) / 2, y + 18, label, "b" if acc else "m", "middle", 11))
    out.append(f'<line class="lnm" x1="{X(lo):.1f}" y1="{ax}" x2="{X(hi):.1f}" y2="{ax}" style="stroke-dasharray:none"/>')
    for us in (900, 1300, 1700, 2100):
        out.append(f'<line class="ln" x1="{X(us):.1f}" y1="{ax - 4}" x2="{X(us):.1f}" y2="{ax + 4}"/>')
        out.append(text(X(us), ax + 18, f"{us}", "m t", "middle", 11))
    out.append(text(X(1500), ax + 34, "мкс; диапазоны с шагом 25", "m t", "middle", 10))
    # distance from the middle position to the 1300 edge
    yb = top + 2 * lane_h + lane_h - 3
    out.append(f'<path d="M{X(1300):.1f} {yb} L{X(1500):.1f} {yb}" stroke="{WARN}" stroke-width="1.6"/>')
    H = ax + 74
    out.append(text(16, H - 22, f"До границы диапазона {min(gaps)}–{max(gaps)} мкс (жёлтая черта — 200): джиттер канала не переключает режим.", "m t", "start"))
    out.append(text(16, H - 6, "Арм — только когда ARM и PREARM оба в диапазоне; ANGLE в Stage 2 failsafe включается и без тумблера.", "m t", "start"))
    return svg(W, H, "Раскладка режимов на оси AUX-канала", "".join(out))


# ---------------------------------------------------------------- bf-intro
def migrate_line_tree() -> str:
    t = tree("Строка старого diff all (4.5.3) после перехода на 2025.12", Node("tgt", ["Плата есть в списке", "target 2025.12?"], [
        ("нет", Node("stay", ["Остаться на 4.5.x:", "чужой target —", "неверные resource"], leaf=True)),
        ("да", Node("name", ["Имя параметра", "есть в 2025.12?"], [
            ("нет", Node("gone", ["По таблице:", "переименован", "или удалён?"], [
                ("переим.", Node("ren", ["Новое имя; значение", "сверить по таблице:", "failsafe_off_delay", "÷ 10"], leaf=True, accent=True)),
                ("удалён", Node("del", ["INVALID NAME:", "iterm_limit,", "min_throttle — убрать"], leaf=True)),
            ])),
            ("да", Node("same", ["Смысл и единицы", "те же?"], [
                ("нет", Node("redo", ["Не переносить:", "d_*, iterm_windup,", "osd_warn_bitmask,", "beeper"], leaf=True, accent=True)),
                ("да", Node("keep", ["Как есть: aux, map,", "рейты, фильтры,", "vbat_*, rxrange"], leaf=True)),
            ], accent=True)),
        ])),
    ]), width=720, box_w=136, box_h=60, gap_y=84)
    return _add_footer(t, ["Опасна правая ветка: строка с прежним именем принимается молча, но даёт другой тюн или другие сигналы",
                           "Не переносятся и под новым именем (п. 6): D-составляющая PID и газ GPS Rescue — задать заново"])


# ---------------------------------------------------------------- bf-cli
def diff_scopes() -> str:
    W = 720
    cols = ["железо:", "остальной", "PID-", "PID-", "рейт-", "рейт-", "mcu_id,", "defaults"]
    cols2 = ["resource,", "master: aux,", "профиль", "профили", "профиль", "профили", "signature", "nosave …"]
    cols3 = ["serial, dma", "map, rxfail", "активный", "ещё 3", "активный", "ещё 3", "", "save"]
    # rows: command, covered columns (printConfig() in cli/cli.c, as tabulated in the module)
    rows = [("diff profile", {2}), ("diff rates", {4}), ("diff hardware", {0}),
            ("diff  (= master)", {0, 1, 2, 4}), ("diff all", {0, 1, 2, 3, 4, 5, 6, 7})]
    L, cw, top, rh = 150, 70, 80, 34
    out = [text(16, 18, "Что попадает в вывод diff: только diff all берёт все 4 + 4 профиля", "m t", "start")]
    for j in range(len(cols)):
        cx = L + j * cw + cw / 2
        for k, s in enumerate((cols[j], cols2[j], cols3[j])):
            out.append(text(cx, 40 + k * 13, s, "m t", "middle", 10))
    for i, (cmd, cov) in enumerate(rows):
        y = top + i * rh
        acc_row = cmd == "diff all"
        out.append(text(L - 10, y + rh / 2 + 4, cmd, "b" if acc_row else "", "end", 11.5))
        for j in range(len(cols)):
            x = L + j * cw + 4
            if j in cov:
                out.append(_rect(x, y + 4, cw - 8, rh - 8, "boxa" if acc_row or j in (3, 5) else "box", 4))
            else:
                out.append(f'<rect x="{x}" y="{y + 4}" width="{cw - 8}" height="{rh - 8}" rx="4" fill="none" stroke="{MUTED}" stroke-width="0.8" stroke-dasharray="3 3"/>')
    # the trap: plain diff misses the three other profiles
    yd = top + 3 * rh
    for j in (3, 5):
        x = L + j * cw + cw / 2
        out.append(text(x, yd + rh / 2 + 4, "нет", "d t b", "middle", 11))
    H = top + len(rows) * rh + 44
    out.append(text(16, H - 22, "Бэкап «с профилем 2 под Li-Ion», снятый простым diff при активном профиле 1, профиля 2 не содержит.", "m t", "start"))
    out.append(text(16, H - 6, "bare убирает обёртку, mcu_id/signature и возврат к профилям; defaults — умолчание в комментарии.", "m t", "start"))
    return svg(W, H, "Области команды diff", "".join(out))


# ---------------------------------------------------------------- bf-custom
def custom_verify_flow() -> str:
    steps = [("k", "1. BUILD KEY → JSON: опции как в записи?"), ("g", "2. status: гироскоп найден?"),
             ("r", "3. Ports / Receiver: приёмник отвечает?"), ("m", "4. Motors без пропов: DShot и bidir?"),
             ("o", "5. OSD видно в очках?"), ("d", "6. diff all совпадает с бэкапом по смыслу?")]
    x0, w, h, step, top = 10, 330, 34, 46, 34
    boxes = [Box(k, [s], x0, top + i * step, w, h) for i, (k, s) in enumerate(steps)]
    boxes[0].accent = True
    yj = top + len(steps) * step
    boxes += [Box("j", ["Журнал: хеш коммита, EXTRA_FLAGS, чек-лист"], x0, yj, w, h, accent=True),
              Box("xr", ["нет: протокол приёмника", "не отмечен в сборке"], 420, top + 2 * step - 3, 290, 40),
              Box("xo", ["нет: собрано без HD OSD", "(маска порта ни при чём)"], 420, top + 4 * step - 3, 290, 40),
              Box("xs", ["нет servo / smix в CLI:", "собрано без SERVOS"], 420, top + 5 * step - 3, 290, 40)]
    links = [(steps[i][0], steps[i + 1][0], "", False, "v") for i in range(len(steps) - 1)]
    links += [("d", "j", "", True, "v"), ("r", "xr", "", False, "h"), ("o", "xo", "", False, "h"),
              ("d", "xs", "", False, "h")]
    H = yj + h + 50
    notes = [(10, 20, "Шесть проверок по порядку; приёмник молчит или нет OSD — смотреть состав сборки", "m t"),
             (10, H - 12, "В diff all BUILD KEY нет — вывод status хранить отдельно, рядом с конфигом", "m t")]
    return flow("Проверка своей сборки Betaflight", boxes, links, 720, H, notes=notes)


# ---------------------------------------------------------------- bf-cli-automation
def cli_apply_verify() -> str:
    boxes = [
        Box("f", ["find_craft:", "порт по craft_name"], 10, 40, 150, 50, accent=True),
        Box("b", ["diff all →", "*_before_diff.txt"], 186, 40, 150, 50),
        Box("s", ["set из CHANGES,", "save"], 362, 40, 150, 50),
        Box("w", ["перезагрузка:", "ждать 6 с, порт", "мог смениться"], 550, 34, 160, 62),
        Box("f2", ["find_craft", "заново"], 550, 140, 160, 50, accent=True),
        Box("g", ["get по каждому", "ключу: все OK?"], 362, 140, 150, 50),
        Box("a", ["diff all →", "*_after_diff.txt"], 186, 140, 150, 50),
        Box("gd", ["git diff: ровно", "строки CHANGES"], 10, 140, 150, 50, accent=True),
        Box("xf", ["FAIL: не сохранилось", "или ключ переименован"], 352, 236, 170, 50),
        Box("xg", ["лишняя строка:", "правили руками"], 10, 236, 150, 50),
    ]
    links = [("f", "b"), ("b", "s"), ("s", "w"), ("w", "f2", "", False, "v"), ("f2", "g"), ("g", "a", "", True),
             ("a", "gd", "", True), ("g", "xf", "", False, "v"), ("gd", "xg", "", False, "v")]
    notes = [(10, 20, "Правка через скрипт: каждое значение перечитать после save, итог сверить двумя бэкапами", "m t"),
             (560, 236, "exit не слать: он", "m t"), (560, 252, "перезагружает FC,", "m t"),
             (560, 268, "а noreboot нет", "m t"), (560, 284, "до 4.5.4", "m t"),
             (352, 304, "переименования — таблица в bf-intro", "m t"),
             (10, 304, "diff all читать до «# », не по таймеру", "m t")]
    return flow("Скрипт CLI: изменить, перечитать, сверить", boxes, links, 720, 316, notes=notes)


# ---------------------------------------------------------------- aero-wing
def wing_stall_bank() -> str:
    m, S, cl, rho, g = 2.0, 0.4, 1.1, 1.225, 9.81
    vs = math.sqrt(2 * m * g / (rho * S * cl))              # 8.53 m/s
    vmin, vcr = 1.2 * vs, 1.4 * vs                          # 10.2, 11.9
    phis = [0.5 * i for i in range(0, 141)]                 # 0 … 70°
    v = [vs / math.sqrt(math.cos(math.radians(p))) for p in phis]
    v45 = vs / math.sqrt(math.cos(math.radians(45)))        # 10.15
    phi_min = math.degrees(math.acos(1 / 1.2 ** 2))         # 46.0°
    phi_cr = math.degrees(math.acos(1 / 1.4 ** 2))          # 59.3°
    r60 = 1 / math.sqrt(math.cos(math.radians(60)))         # 1.41
    assert abs(vs - 8.5) < 0.05 and abs(v45 - 10.1) < 0.06 and abs(r60 - 1.41) < 0.005
    return chart(
        "Скорость сваливания в вираже: V_s(φ) = V_s / √cos φ (крыло 0.4 м², 2 кг)",
        [dict(name="V_s в вираже", xs=phis, ys=v, cls="a", label_at=34, label_dy=-10, label_anchor="end")],
        Axis("крен φ, °", 0, 70, ticks=[0, 10, 20, 30, 40, 50, 60, 70]),
        Axis("скорость, м/с", 6, 16, ticks=[6, 8, 10, 12, 14, 16]),
        bands=[(phi_min, 70, "")],
        hmarks=[(vmin, "", "d"), (vcr, "", "m"), (vs, f"V_s прямо = {vs:.1f} м/с", "m")],
        marks=[(45, f"45°: {v45:.1f} м/с", "ink", 255), (60, f"60°: +{(r60 - 1) * 100:.0f} %", "ink", 255)],
        notes=[(74, 60, f"AIRSPEED_MIN = 1.2·V_s, крейсер = 1.4·V_s", "m"),
               (70, 141, f"крейсер ≈ {vcr:.0f}", "m"), (70, 190, f"AIRSPEED_MIN ≈ {vmin:.1f}", "d"),(496, 60, f"с {phi_min:.0f}° сваливание", "w"), (496, 74, "выше AIRSPEED_MIN,", "w"),
               (496, 88, f"с {phi_cr:.0f}° — выше крейсера", "w")])


# ---------------------------------------------------------------- link-telemetry-radios
def elrs_param_download() -> str:
    L = 25 + 12                                              # PARAM_VALUE, MAVLink2: payload + overhead, bytes
    modes = [("F1000", 2375, "a"), ("333Hz Full", 1470, "ink"), ("250Hz", 590, "w"), ("50Hz", 110, "d")]
    ns = [50 * 2 ** (i / 8) for i in range(0, 43)]           # 50 … 2000 parameters (log steps)
    t1000 = {name: 1000 * L / b for name, b, _ in modes}
    assert [round(t1000[k], 1) for k in ("F1000", "333Hz Full", "250Hz")] == [15.6, 25.2, 62.7] and round(t1000["50Hz"]) == 336
    # parallel lines on log-log axes; labels above their line (line falls away to the left), F1000 well below it
    lab = {"F1000": (2000, 30), "333Hz Full": (2000, -7), "250Hz": (2000, -7), "50Hz": (1700, -7)}
    series = [dict(name=name, xs=ns, ys=[n * L / b for n in ns], cls=c, label_at=lab[name][0],
                   label_dy=lab[name][1]) for name, b, c in modes]
    series.append(dict(name="", xs=[1000] * 4, ys=[t1000[k] for k, _, _ in modes], cls="ink", dots=True))
    return chart(
        "Загрузка параметров по ELRS MAVLink: t = N · 37 Б / B (без повторов)",
        series,
        Axis("число параметров N (param_count), лог. шкала", 50, 2000, log=True, ticks=[50, 100, 200, 500, 1000, 2000]),
        Axis("время, с (лог. шкала)", 1, 1000, log=True, ticks=[1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]),
        marks=[(1000, "", "ink")],
        notes=[(230, 56, "N = 1000: 15.6 · 25.2 · 62.7 · 336 с", ""),
               (230, 72, "при B = 2375 · 1470 · 590 · 110 Б/с", "m"),
               (400, 284, "параметры и миссию — на F1000 / 333Hz Full", "m"), (400, 298, "на земле, потом полётный режим", "m")])


# ---------------------------------------------------------------- est-sensors
def compass_cal_tree() -> str:
    t = tree("Калибровка компаса (ArduPilot): после мачты и ориентации — два вопроса", Node("rot", ["Аппарат можно", "вращать в руках?"], [
        ("да", Node("cur1", ["Длина MAG", "меняется с газом?"], [
            ("нет", Node("rc", ["Вращением:", "COMPASS_CAL_FIT 16", "(внешний первый)"], leaf=True, accent=True)),
            ("да", Node("rcm", ["Вращением + CompassMot", "(Copter) или MagFit", "по логу с током"], leaf=True, accent=True)),
        ])),
        ("нет", Node("cur2", ["Длина MAG", "меняется с газом?"], [
            ("нет", Node("lv", ["Large Vehicle MagCal:", "известный курс,", "только смещения"], leaf=True)),
            ("да", Node("lvf", ["Large Vehicle MagCal", "+ CompassMot (Copter)", "или MagFit по логу"], leaf=True)),
        ])),
    ], accent=True), width=720, box_w=170, box_h=52, gap_y=80)
    return _add_footer(t, ["Принять: |B| постоянна ±5 % при повороте, смещения < COMPASS_OFFS_MAX 1800,",
                           "отличие от модели < ARMING_MAGTHRESH 100 мГс по горизонтали, CompassMot < 30 %, MagFit: курс < 10°.",
                           "INAV: компенсации по току нет — только перенос компаса."])


# ---------------------------------------------------------------- est-gnss
def gnss_rtk_tree() -> str:
    t = tree("Нужен ли RTK: решает требуемая точность, а не «чем точнее, тем лучше»", Node("need", ["Что нужно", "задаче?"], [
        ("~2 м", Node("std", ["Полёт по точкам, FPV:", "GNSS + EKF, 1.5–3 м", "в поле — RTK не нужен"], leaf=True)),
        ("см, в полёте", Node("rtk", ["RTK: F9P / UM982", "на базе и борту,", "поправки RTCM"], [
            ("своя база", Node("own", ["≤ 10–20 км: fix", "1–3 см, float", "10–50 см"], leaf=True, accent=True)),
            ("NTRIP", Node("ntrip", ["до 50–100 км:", "1 ppm и дольше", "сходимость"], leaf=True)),
        ], accent=True)),
        ("см, после", Node("ppk", ["Фотограмметрия:", "PPK — постобработка", "по логам"], leaf=True)),
        ("курс", Node("mb", ["Курс без компаса:", "moving baseline:", "GPS1_TYPE = 17,", "GPS2_TYPE = 18"], leaf=True)),
    ]), width=720, box_w=150, box_h=62, gap_y=90)
    return _add_footer(t, ["RTK не лечит многолучёвость (скачки 1–10+ м у стены) и потерю спутников под крышей"])


def build(D: dict) -> None:
    D["chart-failsafe-landing-time"] = failsafe_landing_time()
    D["bf-serial-valid-tree"] = serial_valid_tree()
    D["chart-blackbox-flash-minutes"] = blackbox_flash_minutes()
    D["bf-aux-ranges"] = aux_ranges()
    D["bf-migrate-line-tree"] = migrate_line_tree()
    D["bf-diff-scopes"] = diff_scopes()
    D["bf-custom-verify-flow"] = custom_verify_flow()
    D["bf-cli-apply-verify"] = cli_apply_verify()
    D["chart-wing-stall-bank"] = wing_stall_bank()
    D["chart-elrs-param-download"] = elrs_param_download()
    D["compass-cal-choice-tree"] = compass_cal_tree()
    D["gnss-rtk-choice-tree"] = gnss_rtk_tree()
