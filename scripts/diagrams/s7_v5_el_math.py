"""Visual pass (stage 7), batch v5_el_math: one new diagram per electronics / math module (two for math-ode-dyn).

dshot600-pulse-train        el-measure — the module's worked DShot frame (throttle 1046, telemetry 0, CRC 6 = 0x82C6)
                            as the oscilloscope shows it: 16 bits of 1/600 kbit/s ≈ 1.67 us, «1» high ~75 % of the bit,
                            «0» ~37 %, frame ≈ 27 us; CRC = (v ^ v>>4 ^ v>>8) & 0xF computed in the script.
chart-emi-wire-field        el-emi — B = 2·10⁻⁷·I/r of a single wire and B ≈ 2·10⁻⁷·I·d/r² of a twisted pair (d = 3 mm) at
                            60 A against the Earth field ~50 uT and 30 % of it (the compassmot threshold); the module's
                            table points at 5 / 10 / 20 cm and the «at least 10 cm» rule.
chart-pack-sag-sp           el-battery-packs — sag ΔU = I·R_pack, R_pack = R_cell·S/P for 6S P42A (25 mOhm) with P = 2, 3, 4;
                            each curve ends at the S/P rule limit P·0.6·45 A; 4P with tape and joints (+10–20 mOhm) as
                            a band; the worked 60 A case (2.3–3.5 V) against one cell (3.6 V).
periph-connect-flow         el-peripherals — the module's connection protocol (steps 1–7) as a flow: datasheet, FC map,
                            wiring, multimeter before power, smoke stopper, firmware check; no data -> analyzer: bytes,
                            speed, inversion.
x8-power-redundancy         el-redundancy — the X8 power scheme of the module: two batteries with a fuse each (1.3 × branch
                            maximum), ORing or parallel, PDB / copper bars for 150+ A (peak ~130 A), 4 arms of ~32 A with no
                            fuses on motors, fused companion branch, two BECs with diode ORing to FC and receiver.
kicad-design-flow           el-kicad — the KiCad cycle with its checks: schematic -> ERC -> footprints -> fab rules in
                            Board Setup -> layout -> DRC -> 3D view -> outputs -> Gerber Viewer; every failed check goes
                            back to the step that caused it.
rot-order-noncommute        math-linalg-rot — practice step 3: Rx(90°)·Ry(90°) and Ry(90°)·Rx(90°) applied to (1, 0, 0),
                            step by step (the right factor acts first): (0, 1, 0) against (0, 0, −1); for 1° and 1° the
                            difference ≈ 3·10⁻⁴ (computed here).
chart-delay-gain-limit      math-ode-dyn — K_p.кр against the pure delay L from the phase condition
                            atan(ωJ/b) + atan(ωτ) + ωL = π and the modulus √(1 + (ωτ)²)·√((Jω)² + b²) for τ_m = 20 ms
                            (J = 1, b = 0.2) and τ_m = 100 ms; the module's model points 2 / 5 / 10 ms (509.7, 208.8, 108.0).
chart-pt1-discrete-phase    math-ode-dyn — phase of a 50 Hz sine through PT1 100 Hz for the three coefficients (forward
                            Euler, backward Euler, exact) against T_s, from H = k / (1 − (1 − k)·e^(−j·2π·f·T_s)); the
                            continuous −26.6°, the module's table points at 1/8000, 1/1000, 1/250 s; forward Euler's pole
                            negative for T_s > τ and unstable for T_s > 2τ.
cov-ellipse-rotation        math-prob-est — practice step 4: the 2σ ellipse of P = [[4, 2.4], [2.4, 2.25]] (σ 2 and 1.5,
                            ρ = 0.8, eigenvalues and axes computed here) and of R·P·Rᵀ after 45° = [[0.725, 0.875],
                            [0.875, 5.525]]: the ellipse turns with the cloud.
"""
from __future__ import annotations

import cmath
import math
import random

import re

from plot import Axis, _Scale, chart
from svg import ACCENT, DANGER, INK, MUTED, WARN, Box, flow, svg, text


# ---------------------------------------------------------------- helpers
def _rect(x, y, w, h, cls="box", rx=6, extra=""):
    return f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}"{extra}/>'


def _arrow(d, acc=False, extra=""):
    return f'<path class="{"lna" if acc else "ln"}" d="{d}" marker-end="url(#{"ara" if acc else "ar"})"{extra}/>'


def _line(x1, y1, x2, y2, col=INK, w=1.0, extra=""):
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{col}" stroke-width="{w}"{extra}/>'


def _px(xa: Axis, ya: Axis, x: float, y: float, width: int = 720, height: int = 360) -> tuple[float, float]:
    """Pixel position of a data point in plot.chart (same margins: L 64, R 24, T 36, B 48)."""
    return _Scale(xa, 64, width - 24)(x), _Scale(ya, height - 48, 36)(y)


def _add_footer(svg_str: str, lines: list[str], lh: int = 16) -> str:
    """Grow a helper-built SVG downwards and add muted footnote lines under it."""
    m = re.search(r'viewBox="0 0 (\d+(?:\.\d+)?) (\d+(?:\.\d+)?)"', svg_str)
    w, h = float(m.group(1)), float(m.group(2))
    nh = h + lh * len(lines) + 6
    body = "".join(text(16, h + 4 + lh * (i + 1) - 4, s_, "m t", "start") for i, s_ in enumerate(lines))
    svg_str = svg_str.replace(m.group(0), f'viewBox="0 0 {w:g} {nh:g}"', 1)
    i = svg_str.rfind("</svg>")
    return svg_str[:i] + body + svg_str[i:]


def _boxes(boxes) -> str:
    """Boxes only (links are drawn by hand so that every label sits beside its line)."""
    out = []
    for b in boxes:
        lines = b.label if isinstance(b.label, list) else [b.label]
        out.append(_rect(b.x, b.y, b.w, b.h, "boxa" if b.accent else "box"))
        ty = b.cy() - (len(lines) - 1) * 7 + 4
        for i, s in enumerate(lines):
            out.append(text(b.cx(), ty + i * 14, s, "b" if (b.accent and i == 0) else "", "middle", 11))
    return "".join(out)


# ---------------------------------------------------------------- el-measure
def dshot_pulse_train() -> str:
    throttle, telem = 1046, 0
    v = (throttle << 1) | telem
    crc = (v ^ (v >> 4) ^ (v >> 8)) & 0xF
    frame = (v << 4) | crc
    assert crc == 6 and frame == 0x82C6
    bits = [(frame >> (15 - i)) & 1 for i in range(16)]
    assert "".join(map(str, bits)) == "1000001011000110"
    t_bit = 1 / 600e3 * 1e6                                    # us
    hi1, hi0 = 0.75 * t_bit, 0.37 * t_bit                      # ~75 % and ~37 % of the bit (module text)
    t_frame = 16 * t_bit
    assert abs(t_bit - 1.667) < 0.001 and round(t_frame) == 27
    W, L, R = 720, 64, 20
    t_max = 31.0
    X = lambda t: L + (W - L - R) * t / t_max
    y_hi, y_lo = 74, 118
    out = [text(16, 18, f"Кадр DShot600 на осциллографе: газ {throttle}, телеметрия {telem}, CRC {crc} — 16 бит, 0x{frame:04X}",
                "m t", "start")]
    # bit cells: faint separators and the digit above each bit
    for i, bt in enumerate(bits):
        x0 = X(i * t_bit)
        out.append(_line(x0, 52, x0, y_lo + 4, MUTED, 0.5, ' stroke-dasharray="2 3" opacity="0.6"'))
        out.append(text(X((i + 0.5) * t_bit), 46, str(bt), "a b" if bt else "m b", "middle", 12))
    out.append(_line(X(t_frame), 52, X(t_frame), y_lo + 4, MUTED, 0.5, ' stroke-dasharray="2 3" opacity="0.6"'))
    # waveform
    pts = [(X(0) - 14, y_lo)]
    for i, bt in enumerate(bits):
        t0 = i * t_bit
        t1 = t0 + (hi1 if bt else hi0)
        pts += [(X(t0), y_lo), (X(t0), y_hi), (X(t1), y_hi), (X(t1), y_lo)]
    pts.append((X(t_max), y_lo))
    d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    out.append(f'<path d="{d}" fill="none" stroke="{ACCENT}" stroke-width="2"/>')
    out.append(text(X(0) - 18, y_hi + 4, "3.3 В", "m t", "end", 10))
    out.append(text(X(0) - 18, y_lo + 4, "0", "m t", "end", 10))
    # dimension lines for the first «1», the first «0» and one whole bit; labels stacked so no leader crosses a label
    yd, row = 134, 17
    dims = [(0, hi1, f"«1»: высокий {hi1:.2f} мкс (~75 % бита)", 3),
            (t_bit, t_bit + hi0, f"«0»: высокий {hi0:.2f} мкс (~37 %)", 2),
            (2 * t_bit, 3 * t_bit, f"бит: 1/600 кбит/с = {t_bit:.2f} мкс", 1)]
    for t0, t1, lab, r in dims:
        a_, b_ = X(t0), X(t1)
        out += [_line(a_, yd - 5, a_, yd + 5), _line(b_, yd - 5, b_, yd + 5), _line(a_, yd, b_, yd)]
        xm, yl = (a_ + b_) / 2, yd + r * row
        out.append(_line(xm, yd + 3, xm, yl - 4, MUTED, 0.8))
        out.append(text(xm + 5, yl, lab, "t", "start", 10.5))
    # field brackets
    yb = 212
    groups = [(0, 11, f"газ: 10000010110 = {throttle}", "a"), (11, 12, "телем.", "m"), (12, 16, f"CRC 0110 = {crc}", "w")]
    for a_, b_, lab, cls in groups:
        xa, xb = X(a_ * t_bit) + 2, X(b_ * t_bit) - 2
        col = {"a": ACCENT, "m": MUTED, "w": WARN}[cls]
        out.append(f'<path d="M{xa:.1f} {yb - 6} L{xa:.1f} {yb} L{xb:.1f} {yb} L{xb:.1f} {yb - 6}" fill="none" stroke="{col}" stroke-width="1.4"/>')
        out.append(text((xa + xb) / 2, yb + 16, lab, f"{cls} t b", "middle", 10.5))
    # time axis, drawn by hand under everything
    ya = 252
    out.append(_line(X(0), ya, X(t_max), ya))
    for t in range(0, 26, 5):
        out.append(_line(X(t), ya - 4, X(t), ya + 4))
        out.append(text(X(t), ya + 18, f"{t}", "m t", "middle", 11))
    out.append(_line(X(t_frame), ya - 6, X(t_frame), ya + 6, ACCENT, 1.6))
    out.append(text(X(t_frame) + 5, ya + 18, f"кадр {t_frame:.1f}", "a t", "start", 10.5))
    out.append(text((X(0) + X(25)) / 2, ya + 34, "время, мкс", "m t", "middle", 11))
    H = ya + 72
    out.append(text(16, H - 22, "CRC = (v ⊕ v>>4 ⊕ v>>8) & 0xF, v — 12 бит газа и телеметрии. Бит несёт ширина импульса,", "m t", "start"))
    out.append(text(16, H - 6, "а не уровень. После кадра — низкий уровень до следующего: при цикле 8 кГц кадр каждые 125 мкс.", "m t", "start"))
    return svg(W, H, "Кадр DShot600 по времени", "".join(out))


# ---------------------------------------------------------------- el-emi
def emi_wire_field() -> str:
    I, d = 60.0, 0.003
    single = lambda r: 2e-7 * I / r * 1e6                       # uT
    pair = lambda r: 2e-7 * I * d / r ** 2 * 1e6
    table = [(5, 240, 14), (10, 120, 3.6), (20, 60, 0.9)]
    for rc, s, p in table:
        assert abs(single(rc / 100) - s) < 0.5 and abs(pair(rc / 100) - p) / p < 0.05
    earth = 50.0
    gate = 0.3 * earth                                          # compassmot: > ~30 % of the Earth field -> move the compass
    rs = [3 + 0.25 * k for k in range(109)]                     # 3 … 30 cm
    xa = Axis("расстояние от провода до компаса, см", 3, 30, ticks=[5, 10, 15, 20, 25, 30])
    ya = Axis("поле, мкТл (логарифмическая шкала)", 0.3, 600, log=True, ticks=[0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500])
    notes = []
    for rc, sv, pv in table:                                    # the module's table values beside their dots
        x, y = _px(xa, ya, rc, sv)
        notes.append((x + 6, y - 6, f"{sv:g}", "d"))
        x, y = _px(xa, ya, rc, pv)
        notes.append((x - 6 - 7 * len(f"{pv:g}"), y + 15, f"{pv:g}", "a"))
    return chart(
        f"Поле провода с током {I:.0f} А у компаса: одиночный ∝ 1/r, скрученная пара ∝ 1/r²",
        [dict(name="одиночный провод", xs=rs, ys=[single(r / 100) for r in rs], cls="d", label_at=14, label_dy=-10,
              label_anchor="start"),
         dict(name="скрученная пара, зазор 3 мм", xs=rs, ys=[pair(r / 100) for r in rs], cls="a", label_at=21, label_dy=-12,
              label_anchor="start"),
         dict(name="", xs=[t[0] for t in table], ys=[t[1] for t in table], cls="d", dots=True, w=0),
         dict(name="", xs=[t[0] for t in table], ys=[t[2] for t in table], cls="a", dots=True, w=0)],
        xa, ya,
        hmarks=[(earth, "поле Земли ~50 мкТл", "ink"), (gate, f"{gate:.0f} мкТл = 30 % поля Земли: выше — переносить компас", "w")],
        marks=[(10, "минимум 10 см", "m", 18)],
        notes=notes)


# ---------------------------------------------------------------- el-battery-packs
def pack_sag_sp() -> str:
    S, r_cell, i_cell, rule = 6, 0.025, 45.0, 0.6               # 6S, P42A ~25 mOhm, 45 A, P >= I / (0.6 · I_cell)
    i_lim = rule * i_cell                                       # 27 A per cell
    r_pack = lambda P: r_cell * S / P
    assert abs(r_pack(4) - 0.0375) < 1e-9 and round(60 * r_pack(4), 1) == 2.3 and round(60 * (r_pack(4) + 0.02), 1) == 3.5
    assert i_lim == 27 and math.ceil(60 / i_lim) == 3
    series = []
    for P, cls in ((2, "d"), (3, "w"), (4, "a")):
        imax = P * i_lim
        xs = [k * imax / 60 for k in range(61)]
        series.append(dict(name=f"{P}P", xs=xs, ys=[x * r_pack(P) for x in xs], cls=cls, label_anchor="end", label_dy=-8))
        series.append(dict(name="", xs=[imax], ys=[imax * r_pack(P)], cls=cls, dots=True, w=0))
    xs4 = [k * 108 / 60 for k in range(61)]
    series.insert(0, dict(name="", xs=xs4, ys=[x * r_pack(4) for x in xs4], cls="a",
                          band=([x * r_pack(4) for x in xs4], [x * (r_pack(4) + 0.02) for x in xs4]), w=0))
    series.append(dict(name="", xs=[60, 60], ys=[60 * r_pack(4), 60 * (r_pack(4) + 0.02)], cls="a", dots=True, w=0))
    xa = Axis("ток пакета, А", 0, 120, ticks=[0, 20, 40, 60, 80, 100, 120])
    ya = Axis("просадка ΔU = I·R, В", 0, 6, ticks=[0, 1, 2, 3, 4, 5, 6])
    x0, y0 = _px(xa, ya, 1.5, 3.6)
    s_ = chart(
        "Просадка 6S из P42A: R пакета = R элемента × S / P",
        series, xa, ya,
        hmarks=[(3.6, "", "d")],
        marks=[(60, "пример: 4P при 60 А — 2.3–3.5 В", "ink", 20)],
        notes=[(x0, y0 - 6, "≈ 1 элемент (3.6 В номинал)", "d"),
               (386, 262, "полоса 4P: от одних элементов до +20 мОм ленты", "a")])
    return _add_footer(s_, [
        f"R пакета: 2P — {r_pack(2) * 1000:.0f} мОм, 3P — {r_pack(3) * 1000:.0f} мОм, 4P — {r_pack(4) * 1000:.1f} ≈ 38 мОм (только элементы).",
        f"Точка — конец кривой: предел по правилу P ≥ I / (0.6 × 45 А) = {i_lim:.0f} А на элемент: 54, 81, 108 А."])


# ---------------------------------------------------------------- el-peripherals
def periph_connect_flow() -> str:
    x0, w, h, step, top = 10, 370, 40, 54, 36
    steps = [["1. Даташит: интерфейс, уровни,", "питание (В, мА), протокол и скорость"],
             ["2. Карта FC: свободный порт,", "его инвертор и питание, лимит BEC"],
             ["3. Провода подписаны; TX/RX", "перекрёстно; земля общая"],
             ["4. До включения — мультиметр: нет КЗ", "5 В / 3.3 В на GND, питание с нужного пада"],
             ["5. Включение через smoke stopper,", "напряжение на устройстве в норме"],
             ["6. Прошивка: порт → функция →", "протокол/скорость. Данные есть?"]]
    boxes = [Box(f"s{i}", lab, x0, top + i * step, w, h, accent=(i in (3, 4))) for i, lab in enumerate(steps)]
    ex = 420
    ok = Box("ok", ["готово: GPS — спутники, компас —", "курс при повороте, ESC — RPM"], ex, top + 4 * step - 6, 290, h)
    an = Box("an", ["7. Анализатор на линию:"], ex, top + 5 * step + 50, 290, 30, accent=True)
    q = [("нет байтов →", "TX/RX перекрёстно?"), ("байты-мусор →", "скорость, инверсия (SBUS), общая земля")]
    out = [text(16, 18, "Протокол подключения периферии: всегда один порядок, мультиметр — до питания", "m t", "start"),
           _boxes(boxes + [ok, an])]
    for i in range(5):
        y1 = top + i * step + h
        out.append(_arrow(f"M{x0 + w / 2} {y1} L{x0 + w / 2} {y1 + step - h}"))
    b6 = boxes[5]
    # yes -> done (up-right), no -> analyzer (down-right)
    out.append(_arrow(f"M{x0 + w} {b6.cy() - 8} L{ex - 20} {b6.cy() - 8} L{ex - 20} {ok.cy()} L{ex} {ok.cy()}", True))
    out.append(text(x0 + w + 3, b6.cy() - 12, "да", "a t", "start", 10.5))
    out.append(_arrow(f"M{x0 + w} {b6.cy() + 8} L{ex - 20} {b6.cy() + 8} L{ex - 20} {an.cy()} L{ex} {an.cy()}"))
    out.append(text(ex - 16, b6.cy() + 22, "нет", "m t", "start", 10.5))
    yq = an.y + an.h + 18
    for i, (what, fix) in enumerate(q):
        y = yq + i * 36
        out.append(text(ex + 10, y, what, "w t", "start", 10.5))
        out.append(text(ex + 10, y + 15, fix, "t", "start", 10.5))
    out.append(_line(ex + 4, an.y + an.h, ex + 4, yq + 51, MUTED, 0.8))
    H = yq + 64
    return svg(720, H, "Протокол подключения периферии", "".join(out))


# ---------------------------------------------------------------- el-redundancy
def x8_power_redundancy() -> str:
    i_hover_m, i_max_m = (3.6, 3.9), (15, 16)
    i_arm = 2 * i_max_m[1]                                      # two motors per arm
    i_peak = 4 * i_arm
    assert i_arm == 32 and abs(i_peak - 130) < 5
    W = 720
    b1 = Box("b1", ["АКБ 1 6S,", "предохранитель", "1.3 × I_max ветки"], 10, 40, 150, 58)
    b2 = Box("b2", ["АКБ 2 6S,", "предохранитель", "1.3 × I_max ветки"], 10, 120, 150, 58)
    orr = Box("or", ["ORing или", "параллель:", "отказ АКБ —", "летим на второй"], 190, 66, 130, 84)
    pdb = Box("pdb", ["PDB / медные", "шины 150+ А", "(пик ~130 А)"], 350, 72, 128, 72, accent=True)
    arms = Box("arms", ["4 луча × 2 мотора:", "до ~32 А на луч,", "12–14 AWG, XT90;", "предохранителей нет"], 520, 36, 190, 84)
    comp = Box("comp", ["предохранитель →", "companion / нагрузка"], 520, 140, 190, 44)
    f1 = Box("f1", ["предохранитель → BEC 1 5 В"], 190, 236, 210, 34)
    f2 = Box("f2", ["предохранитель → BEC 2 5 В"], 190, 292, 210, 34)
    dio = Box("dio", ["диодный ORing:", "отказ BEC —", "борт жив"], 430, 245, 130, 72)
    fc = Box("fc", ["FC + приёмник"], 590, 262, 120, 38, accent=True)
    out = [text(16, 18, "X8 6S: две АКБ, предохранители по веткам, два BEC — отказ одной ветки борт переживает", "m t", "start"),
           _boxes([b1, b2, orr, pdb, arms, comp, f1, f2, dio, fc])]
    out.append(_arrow("M160 69 L175 69 L175 98 L190 98"))
    out.append(_arrow("M160 149 L175 149 L175 118 L190 118"))
    out.append(_arrow("M320 108 L350 108", True))
    out.append(_arrow("M478 92 L499 92 L499 78 L520 78", True))
    out.append(_arrow("M478 124 L499 124 L499 162 L520 162"))
    # PDB -> two BEC branches
    out.append(_arrow("M414 144 L414 204 L172 204 L172 253 L190 253"))
    out.append(_arrow("M172 253 L172 309 L190 309"))
    out.append(_arrow("M400 253 L415 253 L415 270 L430 270"))
    out.append(_arrow("M400 309 L415 309 L415 292 L430 292"))
    out.append(_arrow("M560 281 L590 281", True))
    H = 384
    out.append(text(16, H - 38, f"Мотор: висение ~{i_hover_m[0]}–{i_hover_m[1]} А, максимум ~{i_max_m[0]}–{i_max_m[1]} А; луч = 2 мотора → до ~{i_arm} А:", "m t", "start"))
    out.append(text(16, H - 22, "XT60 (30 А длительно) на пределе, XT90 — с запасом. Предохранители — на АКБ, ветках нагрузки и BEC.", "m t", "start"))
    out.append(text(16, H - 6, "Одна шина и один BEC → отказ разъёма обрывает лог без события дизарма.", "m t", "start"))
    return svg(W, H, "Резервированное питание X8", "".join(out))


# ---------------------------------------------------------------- el-kicad
def kicad_design_flow() -> str:
    x0, w, h, step, top = 40, 330, 38, 52, 36
    steps = [(["1. Схема: символы, цепи,", "номиналы, PWR_FLAG"], False),
             (["ERC: ошибок нет?"], True),
             (["2. Посадочные места: 0603,", "SOT-23-6, MSOP-10, JST-GH"], False),
             (["Board Setup: правила фабрики", "(до разводки)"], False),
             (["3. Разводка: контур, слои, дорожки,", "полигоны, Kelvin-пара шунта"], False),
             (["4. DRC: ошибок нет?"], True),
             (["3D-вид: корпуса и разъёмы встают?"], True),
             (["5. Выход: Gerber, сверловка,", "BOM, файл позиций"], False),
             (["Gerber Viewer: каждый слой —", "контур, маска, шелкография, отверстия"], False)]
    boxes = [Box(f"k{i}", lab, x0, top + i * step, w, h, accent=acc) for i, (lab, acc) in enumerate(steps)]
    out = [text(16, 18, "Цикл в KiCad: каждая проверка возвращает к шагу, где ошибка сделана", "m t", "start"), _boxes(boxes)]
    cx = x0 + w / 2
    for i in range(len(boxes) - 1):
        y1 = top + i * step + h
        out.append(_arrow(f"M{cx} {y1} L{cx} {y1 + step - h}", True))
        if boxes[i].accent:
            out.append(text(cx + 6, y1 + 11, "да", "a t", "start", 10))
    # error branches on the right, each going back up to the step that caused it
    ex, ew = 420, 290

    def back(i_gate, i_target, lines):
        g, t = boxes[i_gate], boxes[i_target]
        eh = 16 + 14 * len(lines)
        ey = g.cy() - eh / 2
        s = [_rect(ex, ey, ew, eh, "box")]
        s += [text(ex + 10, ey + 18 + 14 * k, ln, "t", "start", 10.5) for k, ln in enumerate(lines)]
        s.append(_arrow(f"M{x0 + w} {g.cy()} L{ex} {g.cy()}"))
        s.append(text(x0 + w + 6, g.cy() - 5, "нет", "d t", "start", 10))
        xr = ex + ew - 14
        s.append(_arrow(f"M{xr} {ey} L{xr} {t.cy()} L{x0 + w} {t.cy()}", extra=f' style="stroke:{DANGER};stroke-dasharray:5 4"'))
        return s
    out += back(1, 0, ["неподключённый вывод, два выхода", "на цепи, нет PWR_FLAG → в схему"])
    out += back(5, 4, ["ширина, зазор, отверстие, отступ", "от края → в разводку"])
    # the 3D check goes back to footprints: on the left lane, so it crosses nothing
    g, t = boxes[6], boxes[2]
    out.append(_arrow(f"M{x0} {g.cy()} L{x0 - 22} {g.cy()} L{x0 - 22} {t.cy()} L{x0} {t.cy()}",
                      extra=f' style="stroke:{DANGER};stroke-dasharray:5 4"'))
    out.append(text(ex, g.cy() - 4, "нет: ошибка посадочного места — самая", "d t", "start", 10.5))
    out.append(text(ex, g.cy() + 10, "дорогая (плата пришла, микросхема не", "d t", "start", 10.5))
    out.append(text(ex, g.cy() + 24, "встаёт) → назад к шагу 2, линия слева", "d t", "start", 10.5))
    out.append(_line(x0 + w, g.cy(), ex - 6, g.cy(), DANGER, 1, ' stroke-dasharray="2 3"'))
    H = top + len(boxes) * step + 4
    out.append(text(x0 + w + 50, top + 3 * step + 24, "правила загружены → DRC проверяет", "m t", "start", 10.5))
    out.append(text(x0 + w + 50, top + 3 * step + 38, "именно их: дорожка и зазор ~0.127–0.15 мм,", "m t", "start", 10.5))
    out.append(text(x0 + w + 50, top + 3 * step + 52, "отверстия от ~0.3 мм", "m t", "start", 10.5))
    out.append(_line(x0 + w, boxes[3].cy(), x0 + w + 44, top + 3 * step + 20, MUTED, 0.8))
    return svg(720, H, "Цикл проектирования платы в KiCad", "".join(out))


# ---------------------------------------------------------------- math-linalg-rot
def _rx(a):
    c, s = math.cos(a), math.sin(a)
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def _ry(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def _mv(M, v):
    return [sum(M[i][j] * v[j] for j in range(3)) for i in range(3)]


def rot_order_noncommute() -> str:
    q = math.radians(90)
    v0 = [1, 0, 0]
    a1 = _mv(_ry(q), v0); a2 = _mv(_rx(q), a1)                 # Rx·Ry·v: Ry first
    b1 = _mv(_rx(q), v0); b2 = _mv(_ry(q), b1)                 # Ry·Rx·v: Rx first
    rnd = lambda v: [round(c) + 0 for c in v]
    assert rnd(a1) == [0, 0, -1] and rnd(a2) == [0, 1, 0] and rnd(b1) == [1, 0, 0] and rnd(b2) == [0, 0, -1]
    e = math.radians(1)
    da = _mv(_rx(e), _mv(_ry(e), v0)); db = _mv(_ry(e), _mv(_rx(e), v0))
    diff = math.sqrt(sum((x - y) ** 2 for x, y in zip(da, db)))
    assert abs(diff - e ** 2) / e ** 2 < 0.01 and abs(diff - 3e-4) < 0.1e-4

    W, H = 720, 446
    s = 46                                                      # px per unit
    ux = (-0.62, 0.42)                                          # screen direction of +x (towards the viewer)
    P = lambda cx, cy, v: (cx + s * (v[1] + v[0] * ux[0]), cy - s * (v[2] - v[0] * ux[1]))

    def panel(cx, cy, v, prev=None):
        o = []
        for axis, name in (([1.35, 0, 0], "x"), ([0, 1.35, 0], "y"), ([0, 0, 1.35], "z")):
            for sg in (1, -1):
                x2, y2 = P(cx, cy, [c * sg for c in axis])
                o.append(_line(cx, cy, x2, y2, MUTED, 0.8, '' if sg > 0 else ' stroke-dasharray="3 3"'))
            lx, ly = P(cx, cy, [c * 1.12 for c in axis])
            o.append(text(lx + (8 if name == "y" else -6 if name == "x" else 8), ly + (14 if name == "x" else 4), name, "m t", "middle", 11))
        if prev is not None:
            px, py = P(cx, cy, prev)
            o.append(f'<path d="M{cx} {cy} L{px:.1f} {py:.1f}" fill="none" stroke="{ACCENT}" stroke-width="2" '
                     f'stroke-dasharray="4 3" opacity="0.5"/>')
        tx, ty = P(cx, cy, v)
        o.append(_arrow(f"M{cx} {cy} L{tx:.1f} {ty:.1f}", True, ' style="stroke-width:2.4"'))
        return o

    def vec(v):
        return "(" + ", ".join(str(int(round(c)) + 0).replace("-", "−") for c in v) + ")"

    out = [text(16, 18, "R = A·B·v: сначала к вектору применяется правый множитель B, потом A", "m t", "start")]
    xs = [110, 360, 610]
    rows = [(118, "Rx(90°)·Ry(90°)·v", [(v0, None), (a1, v0), (a2, a1)], ["Ry(90°)", "Rx(90°)"]),
            (300, "Ry(90°)·Rx(90°)·v", [(v0, None), (b1, v0), (b2, b1)], ["Rx(90°)", "Ry(90°)"])]
    for cy, title, vs, ops in rows:
        out.append(text(16, cy - 78, title, "b", "start", 12))
        for k, (cx, (v, prev)) in enumerate(zip(xs, vs)):
            out += panel(cx, cy, v, prev)
            cap = "v = (1, 0, 0)" if k == 0 else vec(v)
            out.append(text(cx, cy + 82, cap, "a b" if k == 2 else "t", "middle", 11.5))
        for k, op in enumerate(ops):
            xa, xb = xs[k] + 78, xs[k + 1] - 78
            out.append(_arrow(f"M{xa} {cy - 62} L{xb} {cy - 62}"))
            out.append(text((xa + xb) / 2, cy - 68, op, "t b", "middle", 11))
        unchanged = rows.index((cy, title, vs, ops)) == 1
        if unchanged:
            out.append(text(xs[1], cy + 96, "x вокруг x не меняется", "m t", "middle", 10.5))
    out.append(text(16, H - 22, "Те же два поворота в другом порядке: (0, 1, 0) против (0, 0, −1). Бледный пунктир — вектор до шага.", "m t", "start"))
    out.append(text(16, H - 6, f"Для 1° и 1° разница {diff:.1e} = (1° в радианах)² — второй порядок, поэтому работает малый угол.".replace("e-04", "·10⁻⁴"), "m t", "start"))
    return svg(W, H, "Порядок поворотов: Rx·Ry ≠ Ry·Rx", "".join(out))


# ---------------------------------------------------------------- math-ode-dyn
def _crit(L, tau, J=1.0, b=0.2):
    f = lambda w: math.atan(w * J / b) + math.atan(w * tau) + w * L - math.pi
    lo, hi = 1e-3, 1e5
    for _ in range(200):                                        # bisection: f grows with w
        mid = math.sqrt(lo * hi)
        lo, hi = (mid, hi) if f(mid) < 0 else (lo, mid)
    w = math.sqrt(lo * hi)
    return w, math.sqrt(1 + (w * tau) ** 2) * math.sqrt((J * w) ** 2 + b * b)


def delay_gain_limit() -> str:
    model = [(2, 509.7), (5, 208.8), (10, 108.0)]                # the module's table: kp at the boundary, model
    calc = {2: 510.2, 5: 208.8, 10: 108.0}
    for Lms, kp in calc.items():
        assert abs(_crit(Lms / 1000, 0.02)[1] - kp) < 0.1
    assert abs(_crit(0.005, 0.02)[0] - 96.2) < 0.05
    Ls = [1.6 + 0.1 * k for k in range(105)]                     # 1.6 … 12 ms
    k20 = [_crit(L / 1000, 0.02)[1] for L in Ls]
    k100 = [_crit(L / 1000, 0.10)[1] for L in Ls]
    return chart(
        "Предел усиления задаёт задержка: K_p.кр из условия фазы −180° (J = 1, b = 0.2)",
        [dict(name="τ_m = 20 мс", xs=Ls, ys=k20, cls="a", label_at=11.5, label_dy=-10),
         dict(name="τ_m = 100 мс", xs=Ls, ys=k100, cls="w", dash=True, label_at=11.5, label_dy=18),
         dict(name="", xs=[m[0] for m in model], ys=[m[1] for m in model], cls="ink", dots=True, w=0)],
        Axis("чистая задержка L, мс", 1.6, 12, ticks=[2, 4, 5, 6, 8, 10, 12]),
        Axis("граничное K_p.кр", 0, 650, ticks=[0, 100, 200, 300, 400, 500, 600]),
        notes=[(112, 92, "2 мс: 509.7", "ink"), (270, 218, "5 мс: 208.8 (частота 96 рад/с)", "ink"),
               (520, 252, "10 мс: 108.0", "ink"),
               (300, 70, "точки — модель sim_axis (τ_m = 20 мс), линии — расчёт", "m"),
               (300, 86, "выше линии колебания растут, ниже — затухают;", "m"),
               (300, 102, "при L → 0 предела нет: K_p.кр → ∞", "m")])


def pt1_discrete_phase() -> str:
    fc, f = 100.0, 50.0
    tau = 1 / (2 * math.pi * fc)
    ph_cont = -math.degrees(math.atan(f / fc))
    assert round(ph_cont, 1) == -26.6

    def phase(Ts, kind):
        k = {"fw": Ts / tau, "bw": Ts / (tau + Ts), "ex": 1 - math.exp(-Ts / tau)}[kind]
        if abs(1 - k) >= 1:
            return None                                         # pole outside the unit circle: unstable
        H = k / (1 - (1 - k) * cmath.exp(-1j * 2 * math.pi * f * Ts))
        return math.degrees(cmath.phase(H))
    table = {(8000, "fw"): -24.5, (8000, "bw"): -26.3, (8000, "ex"): -25.5, (1000, "fw"): -10.1, (1000, "bw"): -24.5,
             (1000, "ex"): -18.5, (250, "bw"): -16.5, (250, "ex"): -4.5}
    for (fs, kind), ph in table.items():
        assert abs(phase(1 / fs, kind) - ph) < 0.06, (fs, kind, phase(1 / fs, kind))
    assert phase(1 / 250, "fw") is None
    t_neg, t_uns = tau * 1000, 2 * tau * 1000                   # ms: forward Euler pole < 0 above tau, < −1 above 2·tau
    tss = [0.1 + 0.01 * k for k in range(391)]                  # 0.1 … 4 ms
    series = []
    for kind, name, cls, lab_at, dy in (("bw", "Эйлер назад", "w", 3.3, 16), ("ex", "точная", "a", 3.3, -8),
                                        ("fw", "Эйлер вперёд", "d", 1.0, -10)):
        ys = [phase(t / 1000, kind) for t in tss]
        series.append(dict(name=name, xs=tss, ys=ys, cls=cls, label_at=lab_at, label_dy=dy, label_anchor="start"))
        pts = [(1000 / fs, ph) for (fs, k_), ph in table.items() if k_ == kind]
        series.append(dict(name="", xs=[p[0] for p in pts], ys=[p[1] for p in pts], cls=cls, dots=True, w=0))
    xa = Axis("шаг T_s, мс (1/8000 = 0.125, 1/1000 = 1, 1/250 = 4)", 0, 4, ticks=[0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4])
    ya = Axis("фаза выхода, °", -30, 30, ticks=[-30, -20, -10, 0, 10, 20, 30])
    xn, _ = _px(xa, ya, t_neg, 0)
    xu, _ = _px(xa, ya, t_uns, 0)
    _, y25 = _px(xa, ya, 0, 26)
    left = [f"T_s > τ = {t_neg:.2f} мс:", "полюс Эйлера", "вперёд < 0:", "знакопеременный", "«звон»"]
    right = ["T_s > 2τ =", f"{t_uns:.2f} мс:", "Эйлер вперёд", "неустойчив"]
    x_l = xn - 6 - 6.7 * max(len(t) for t in left)
    notes = [(x_l, y25 + 15 * i, t, "d") for i, t in enumerate(left)] + [(xu + 5, y25 + 15 * i, t, "d") for i, t in enumerate(right)]
    return chart(
        "PT1 100 Гц на синусе 50 Гц: фаза дискретного фильтра против шага T_s",
        series, xa, ya,
        bands=[(t_uns, 4, "")],
        hmarks=[(ph_cont, "непрерывный фильтр −26.6°", "ink")],
        marks=[(t_neg, "", "d"), (t_uns, "", "d")],
        notes=notes)


# ---------------------------------------------------------------- math-prob-est
def cov_ellipse_rotation() -> str:
    P = [[4.0, 2.4], [2.4, 2.25]]
    c = s = math.sqrt(0.5)
    R = [[c, -s], [s, c]]
    mm = lambda A, B: [[sum(A[i][k] * B[k][j] for k in range(2)) for j in range(2)] for i in range(2)]
    tr = lambda A: [[A[j][i] for j in range(2)] for i in range(2)]
    P2 = mm(mm(R, P), tr(R))
    assert all(abs(P2[i][j] - v) < 1e-9 for (i, j), v in {(0, 0): 0.725, (0, 1): 0.875, (1, 1): 5.525}.items())

    def eig(A):
        a, b, d = A[0][0], A[0][1], A[1][1]
        m, r = (a + d) / 2, math.sqrt(((a - d) / 2) ** 2 + b * b)
        l1, l2 = m + r, m - r
        ang = math.atan2(l1 - a, b)                             # direction of the major axis
        return l1, l2, ang
    l1, l2, ang1 = eig(P)
    _, _, ang2 = eig(P2)
    rho = P[0][1] / math.sqrt(P[0][0] * P[1][1])
    assert abs(rho - 0.8) < 1e-9 and abs(math.degrees(ang2 - ang1) - 45) < 1e-6
    rng = random.Random(4)
    L = [[math.sqrt(P[0][0]), 0], [P[0][1] / math.sqrt(P[0][0]), 0]]   # Cholesky of P
    L[1][1] = math.sqrt(P[1][1] - L[1][0] ** 2)
    pts = []
    for _ in range(400):
        g1, g2 = rng.gauss(0, 1), rng.gauss(0, 1)
        pts.append((L[0][0] * g1, L[1][0] * g1 + L[1][1] * g2))

    W, H = 720, 440
    sc = 26                                                      # px per unit
    out = [text(16, 18, "Ковариация поворачивается вместе с облаком: P_y = R·P·Rᵀ (эллипс 2σ, 400 точек)", "m t", "start")]

    def panel(cx, cy, Pm, ang, l1_, l2_, rot, title, mat, extra):
        o = [text(cx, 44, title, "b", "middle", 12)]
        half = 5.6 * sc
        o.append(_rect(cx - half, cy - half, 2 * half, 2 * half, "box", 2, ' style="fill:none;stroke-width:0.8"'))
        for g in range(-4, 5, 2):
            o.append(_line(cx + g * sc, cy - half, cx + g * sc, cy + half, MUTED, 0.4, ' opacity="0.5"'))
            o.append(_line(cx - half, cy - g * sc, cx + half, cy - g * sc, MUTED, 0.4, ' opacity="0.5"'))
            o.append(text(cx + g * sc, cy + half + 14, str(g), "m t", "middle", 10))
            o.append(text(cx - half - 4, cy - g * sc + 4, str(g), "m t", "end", 10))
        o.append(text(cx + half - 4, cy + half + 28, "x₁", "m t", "end", 11))
        o.append(text(cx - half - 16, cy - half + 4, "x₂", "m t", "end", 11))
        dots = []                                   # one <g> carries the style: keeps the SVG under the size limit
        for (x, y) in pts:
            if rot:
                x, y = c * x - s * y, s * x + c * y
            if abs(x) < 5.5 and abs(y) < 5.5:
                dots.append(f'<circle cx="{cx + x * sc:.0f}" cy="{cy - y * sc:.0f}" r="1.5"/>')
        o.append(f'<g fill="{MUTED}" opacity="0.6">' + "".join(dots) + "</g>")
        a, b_ = 2 * math.sqrt(l1_) * sc, 2 * math.sqrt(l2_) * sc
        o.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{a:.1f}" ry="{b_:.1f}" transform="rotate({-math.degrees(ang):.2f} {cx} {cy})" '
                 f'fill="none" stroke="{ACCENT}" stroke-width="2"/>')
        ex_, ey_ = cx + a * math.cos(ang), cy - a * math.sin(ang)
        o.append(_line(cx - a * math.cos(ang), cy + a * math.sin(ang), ex_, ey_, ACCENT, 1, ' stroke-dasharray="5 3"'))
        o.append(text(cx, cy + half + 50, mat, "t b", "middle", 11.5))
        for k, ln in enumerate(extra):
            o.append(text(cx, cy + half + 66 + 15 * k, ln, "m t", "middle", 10.5))
        return o
    cy = 200
    out += panel(190, cy, P, ang1, l1, l2, False, "P", "P = [[4, 2.4], [2.4, 2.25]]",
                 [f"σ₁ = 2, σ₂ = 1.5, ρ = 2.4 / (2·1.5) = {rho:.1f}",
                  f"λ = {l1:.2f} и {l2:.2f}; большая ось под {math.degrees(ang1):.0f}°"])
    out += panel(530, cy, P2, ang2, l1, l2, True, "после поворота R(45°)", "R·P·Rᵀ = [[0.725, 0.875], [0.875, 5.525]]",
                 ["те же λ и полуоси; ось под " + f"{math.degrees(ang2):.0f}° = {math.degrees(ang1):.0f}° + 45°",
                  "дисперсии компонент поменялись: 0.725 и 5.525"])
    return svg(W, H, "Эллипс ковариации и поворот", "".join(out))


def build(D: dict) -> None:
    D["dshot600-pulse-train"] = dshot_pulse_train()
    D["chart-emi-wire-field"] = emi_wire_field()
    D["chart-pack-sag-sp"] = pack_sag_sp()
    D["periph-connect-flow"] = periph_connect_flow()
    D["x8-power-redundancy"] = x8_power_redundancy()
    D["kicad-design-flow"] = kicad_design_flow()
    D["rot-order-noncommute"] = rot_order_noncommute()
    D["chart-delay-gain-limit"] = delay_gain_limit()
    D["chart-pt1-discrete-phase"] = pt1_discrete_phase()
    D["cov-ellipse-rotation"] = cov_ellipse_rotation()
