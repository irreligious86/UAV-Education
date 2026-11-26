"""Thin-module pass diagrams for module f-safety.

safety-thermal-ladder   — temperature scale of a lithium cell: the course charge window 10–45 °C (Gens Ace, via
                          f-power) and the thermal-runaway steps from Liu et al., Sci. Adv. 2018 (self-heating
                          from ~80 °C, SEI ~90 °C, PE separator ~135 °C, PP ~165 °C, LiCoO2 O2 release 180–250 °C).
safety-bench-sequence   — the bench power-up order the module prescribes: multimeter -> smoke stopper -> USB/
                          configurator -> motor test without props -> arm without props -> failsafe test without
                          props -> props only at the field, as the last step before the first hover.
"""
from __future__ import annotations

from svg import ACCENT, DANGER, INK, MUTED, WARN, Box, flow, svg, text

T_MAX = 260.0
STEPS = [  # (°C, label line 1, label line 2, row)
    (80, "~80 °C", "саморазогрев", 0),
    (90, "~90 °C", "распад SEI, газ", 1),
    (135, "~135 °C", "плавится PE-сепаратор", 2),
    (165, "~165 °C", "плавится PP", 0),
    (180, "180–250 °C", "LiCoO2 отдаёт O2", 1),
]


def thermal_ladder() -> str:
    W, L, R = 720, 40, 30
    X = lambda t: L + (W - L - R) * t / T_MAX
    y0 = 78
    out = [text(16, 18, "Температура банки: окно заряда и ступени термического разгона", "m t", "start")]
    # charge window and warm-up band
    out.append(f'<rect x="{X(10):.1f}" y="{y0 - 22}" width="{X(45) - X(10):.1f}" height="22" fill="{ACCENT}" '
               f'fill-opacity="0.25" stroke="{ACCENT}"/>')
    out.append(text((X(10) + X(45)) / 2, y0 - 7, "заряд 10–45", "b", size=10))
    out.append(text((X(10) + X(45)) / 2, y0 - 30, "окно курса", "a t", size=10))
    # runaway zone
    out.append(f'<rect x="{X(80):.1f}" y="{y0 - 22}" width="{X(T_MAX) - X(80):.1f}" height="22" fill="{DANGER}" '
               f'fill-opacity="0.18" stroke="{DANGER}"/>')
    out.append(text((X(80) + X(T_MAX)) / 2, y0 - 30, "реакции идут сами: охлаждать или дать прогореть", "d t", size=10))
    # gap 45..80
    out.append(f'<rect x="{X(45):.1f}" y="{y0 - 22}" width="{X(80) - X(45):.1f}" height="22" fill="{WARN}" fill-opacity="0.18"/>')
    out.append(text((X(45) + X(80)) / 2, y0 - 7, "35 °C", "w t", size=10))
    # axis
    out.append(f'<line x1="{L}" y1="{y0}" x2="{W - R}" y2="{y0}" stroke="{INK}" stroke-width="1.2"/>')
    for t in range(0, 261, 20):
        out.append(f'<line x1="{X(t):.1f}" y1="{y0}" x2="{X(t):.1f}" y2="{y0 + 5}" stroke="{INK}"/>')
        out.append(text(X(t), y0 + 18, f"{t}", "m t", size=10))
    out.append(text(W - R, y0 + 32, "°C", "m t", "end", size=10))
    for t, a, b, row in STEPS:
        yy = y0 + 52 + row * 40
        out.append(f'<line class="lnm" x1="{X(t):.1f}" y1="{y0}" x2="{X(t):.1f}" y2="{yy - 12}"/>')
        out.append(text(X(t) + 3, yy, a, "b", "start", size=10.5))
        out.append(text(X(t) + 3, yy + 13, b, "", "start", size=10.5))
    h = y0 + 52 + 3 * 40 + 14
    out.append(text(16, h - 8, "Между верхом окна заряда и началом саморазогрева — 35 °C: горячий после полёта пакет не заряжают",
                    "m t", "start"))
    return svg(W, h, "Окно заряда и ступени термического разгона Li-ion/LiPo", "".join(out))


def bench_sequence() -> str:
    return flow("Стенд: порядок включения новой или перепаянной сборки", [
        Box("ohm", ["1. Мультиметр:", "нет КЗ на входе"], 5, 40, 170, 48),
        Box("smoke", ["2. Smoke stopper или", "БП с лимитом тока"], 183, 40, 170, 48),
        Box("usb", ["3. USB, конфигуратор:", "пропов нет"], 361, 40, 170, 48),
        Box("mot", ["4. Тест моторов:", "направление, газ мал"], 539, 40, 176, 48),
        Box("arm", ["5. Арм тумблером:", "холостые крутятся"], 539, 140, 176, 48, accent=True),
        Box("fs", ["6. Failsafe-тест:", "пульт выключен"], 361, 140, 170, 48, accent=True),
        Box("props", ["7. Пропы — на площадке,", "последним шагом"], 150, 140, 190, 48),
    ], [("ohm", "smoke"), ("smoke", "usb"), ("usb", "mot"), ("mot", "arm", "", False, "v"),
        ("arm", "fs"), ("fs", "props", "", True)],
        720, 230, notes=[(10, 216, "Шаги 1–6 — без пропов. Любой непройденный шаг: обесточить и разбираться, не идти дальше",
                          "m t")])


def build(D: dict) -> None:
    D["safety-thermal-ladder"] = thermal_ladder()
    D["safety-bench-sequence"] = bench_sequence()
