"""Stage 6 thin-module diagrams for eng-method-101.

eng-method-loop    — the method cycle of theory §5: requirement with conditions -> hypothesis with a predicted
                     number -> experiment planned in advance -> immutable log -> decision (accept / reject /
                     not proven); «not proven» loops back to a new experiment, every step leaves a file.
eng-error-budget   — the R-02 error budget of practice step 6 (tw_budget.py), recomputed here: share of
                     variance per contribution (bars) and the lower bound T/W - U after each candidate next
                     experiment against the limit 2.5.
"""
from __future__ import annotations

import math

from svg import ACCENT, DANGER, MUTED, WARN, Box, flow, svg, text


def method_loop() -> str:
    base = flow("Цикл инженерного метода", [
        Box("req", ["1. Требование", "критерий + условия"], 10, 40, 128, 48, accent=True),
        Box("hyp", ["2. Гипотеза", "предсказывает число"], 153, 40, 128, 48),
        Box("exp", ["3. Эксперимент", "план до запуска"], 296, 40, 128, 48),
        Box("log", ["4. Лог", "сырой, с номером"], 439, 40, 128, 48),
        Box("dec", ["5. Решение", "по U и пределу"], 582, 40, 128, 48, accent=True),
        Box("ok", ["выполнено →", "CHANGELOG, тег"], 582, 160, 128, 44),
        Box("np", ["не доказано →", "эксперимент по бюджету"], 300, 160, 190, 44, accent=True),
        Box("no", ["не выполнено →", "изменить конструкцию"], 10, 160, 170, 44),
    ], [("req", "hyp"), ("hyp", "exp"), ("exp", "log"), ("log", "dec"), ("dec", "ok", "", False, "v")],
        720, 250, notes=[(10, 236, "Файлы: requirements.md · tests.md · logs/ + sha256 · CHANGELOG.md · тег baseline", "m t")])
    extra = (
        # decision bus: dec -> np, dec -> no
        '<path class="ln" d="M646 88 L646 124 L120 124 L120 160" marker-end="url(#ar)"/>'
        '<path class="lna" d="M440 124 L440 160" marker-end="url(#ara)"/>'
        # loops back
        '<path class="lna" d="M330 160 L330 88" marker-end="url(#ara)"/>'
        '<path class="ln" d="M50 160 L50 88" marker-end="url(#ar)"/>'
        f'{text(324, 146, "новый эксперимент", "a t", "end", 10)}'
        f'{text(56, 146, "новое требование", "m t", "start", 10)}'
    )
    return base.replace("</svg>", extra + "</svg>")


def _budget():
    """Same inputs as practice step 6 (tw_budget.py)."""
    T1, V0, V, a, m = 750.0, 16.0, 14.0, 1.8, 860.0
    rho = (273.15 + 20) / (273.15 + 35)
    tw = 4 * T1 * (V / V0) ** a * rho / m
    rows = [("разброс экземпляров", 0.03 * math.sqrt(12) / 4),     # one measured motor stands for all four
            ("показатель a (1.6–2.0)", abs(math.log(V / V0)) * 0.2 / math.sqrt(3)),
            ("напряжение ±0.2 В", a * 0.2 / math.sqrt(3) / V),
            ("калибровка стенда", 0.0061 / 2),
            ("весы ±2 г", 2 / math.sqrt(3) / m)]
    return tw, rows


def error_budget() -> str:
    tw, rows = _budget()
    tot2 = sum(u * u for _, u in rows)
    W, out = 720, []
    out.append(text(16, 18, f"Бюджет R-02: T/W = {tw:.2f}, U(k=2) = {2 * math.sqrt(tot2) * tw:.2f} — доля дисперсии", "b", "start", 13))
    x0, bw, y, rh = 200, 300, 40, 26
    for name, u in rows:
        share = u * u / tot2
        out.append(text(x0 - 8, y + 17, name, "", "end", 11))
        out.append(f'<rect x="{x0}" y="{y + 4}" width="{bw:.0f}" height="{rh - 8}" fill="{MUTED}" fill-opacity="0.12"/>')
        out.append(f'<rect x="{x0}" y="{y + 4}" width="{max(1.5, bw * share):.1f}" height="{rh - 8}" '
                   f'fill="{ACCENT if share > 0.2 else MUTED}"/>')
        out.append(text(x0 + bw * share + 6, y + 17, f"{share * 100:.1f} %", "t", "start"))
        y += rh
    # lower bound after each candidate experiment
    y += 22
    out.append(text(16, y, "Нижняя граница T/W − U после следующего эксперимента (предел 2.5)", "b", "start", 13))
    y += 14
    lo_ax, hi_ax = 2.40, 2.56
    X = lambda v: x0 + (v - lo_ax) / (hi_ax - lo_ax) * (W - x0 - 40)
    names = {r[0]: r[1] for r in rows}
    cases = [("сейчас", []), ("весы 0.1 г", ["весы ±2 г"]), ("все 4 мотора", ["разброс экземпляров"]),
             ("стенд при 14.0 В", ["показатель a (1.6–2.0)"]),
             ("4 мотора + 14.0 В", ["разброс экземпляров", "показатель a (1.6–2.0)"])]
    ytop = y
    for label, drop in cases:
        u = math.sqrt(sum(v * v for k, v in names.items() if k not in drop))
        lb = tw - 2 * u * tw
        ok = lb >= 2.5
        out.append(text(x0 - 8, y + 17, label, "", "end", 11))
        out.append(f'<line x1="{X(lo_ax):.1f}" y1="{y + 13}" x2="{X(lb):.1f}" y2="{y + 13}" stroke="{MUTED}" stroke-width="1"/>')
        out.append(f'<circle cx="{X(lb):.1f}" cy="{y + 13}" r="5" fill="{ACCENT if ok else WARN}"/>')
        out.append(text(X(lb) + 9, y + 17, f"{lb:.3f} {'выполнено' if ok else 'не доказано'}", "t", "start"))
        y += rh
    xl = X(2.5)
    out.append(f'<line x1="{xl:.1f}" y1="{ytop}" x2="{xl:.1f}" y2="{y + 4}" stroke="{DANGER}" stroke-width="1.4" stroke-dasharray="5 3"/>')
    out.append(text(xl, y + 18, "2.5", "d t"))
    for v in (2.40, 2.45, 2.55):
        out.append(text(X(v), y + 18, f"{v:.2f}", "m t"))
    h = y + 30
    return svg(W, h, "Бюджет ошибок R-02 и выбор следующего эксперимента", "".join(out))


def build(D: dict) -> None:
    D["eng-method-loop"] = method_loop()
    D["eng-error-budget"] = error_budget()
