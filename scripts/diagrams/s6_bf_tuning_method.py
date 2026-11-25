"""Stage 6 diagrams for module bf-tuning-method (A/B method: tuning as an experiment).

chart-bf-ab-power   — share of simulated A/B series in which the module's rule (|d|/SE > 2 and permutation p < 0.05)
                      detects the true -15 % propwash change, against flights per arm, plus the false-alarm share of
                      A-vs-A series. Numbers: output of the module's lab script (bf-tuning-method.lab.py --demo,
                      power table: 400 draws per n from pools of 30 synthetic flights per arm). The band n = 1..3 is
                      the arithmetic of the exact permutation test: minimum two-sided p = 2 / C(2n, n) >= 0.10.
bf-ab-order         — the same 10-flight session with wind rising +3 % propwash per flight, flown in blocked order
                      (AAAAA BBBBB) and in ABBA order: the mean drift each arm receives (computed here from 3 % x slot)
                      and the estimates the lab printed (-3.1 % blocked, -20.5 % ABBA, true -15 %).
"""
from __future__ import annotations

import math

from plot import Axis, chart
from svg import svg, text

# lab output, power table (n/arm: detected %, false alarm %)
_POWER = {1: (0.0, 0.0), 2: (0.0, 0.0), 3: (0.0, 0.0), 4: (67.2, 3.2), 5: (92.5, 5.0), 6: (98.8, 5.2),
          7: (99.8, 8.5), 8: (100.0, 7.8)}
_DRIFT = 3.0      # % propwash per flight slot, as in the lab session
_EST = {"blocked": -3.1, "abba": -20.5}   # lab output, propwash B-A


def _order_row(y, label, order, cell_w, x0):
    out = [text(x0 - 8, y + 21, label, "", "end", size=11)]
    for k, arm in enumerate(order):
        x = x0 + k * cell_w
        cls = "boxa" if arm == "B" else "box"
        out.append(f'<rect class="{cls}" x="{x + 2:.1f}" y="{y}" width="{cell_w - 4:.1f}" height="30" rx="4"/>')
        out.append(text(x + cell_w / 2, y + 20, f"{arm}{k + 1}", "b" if arm == "B" else "", size=12))
    da = sum(_DRIFT * k for k, a in enumerate(order) if a == "A") / order.count("A")
    db = sum(_DRIFT * k for k, a in enumerate(order) if a == "B") / order.count("B")
    return out, da, db


def build(D: dict) -> None:
    ns = sorted(_POWER)
    D["chart-bf-ab-power"] = chart(
        "Сколько полётов на плечо нужно, чтобы увидеть −15 % пропвоша (CV ≈ 8 %)",
        [dict(xs=ns, ys=[_POWER[n][0] for n in ns], cls="a"),
         dict(xs=ns, ys=[_POWER[n][0] for n in ns], cls="a", dots=True),
         dict(name="A против A: ложная тревога", xs=ns, ys=[_POWER[n][1] for n in ns], cls="w", dash=True,
              label_at=7.6, label_dy=-8)],
        x=Axis("полётов на каждое плечо (A и B)", 1, 8, ticks=list(range(1, 9))),
        y=Axis("доля серий, %", 0, 100, ticks=[0, 20, 40, 60, 80, 100]),
        bands=[(1, 3.5, "n ≤ 3: p < 0.05 недостижим")],
        hmarks=[(80, "80 % — ориентир курса", "m")],
        notes=[(470, 170, "B против A: эффект найден", "a b"),
               (470, 186, f"n = 4: {_POWER[4][0]:.0f} %,  n = 5: {_POWER[5][0]:.0f} %", "a")])

    # order diagram
    cell_w, x0 = 54, 150
    b = [text(16, 18, "Одна сессия из 10 полётов, ветер растёт: +3 % пропвоша на каждый следующий полёт", "m t", "start")]
    b.append(text(x0 - 8, 52, "дрейф пропвоша", "", "end", size=11))
    for k in range(10):
        b.append(text(x0 + k * cell_w + cell_w / 2, 52, f"+{_DRIFT * k:.0f} %", "w t", size=11))
    r1, da1, db1 = _order_row(66, "AAAAA BBBBB", "AAAAABBBBB", cell_w, x0)
    b += r1
    b.append(text(x0, 116, f"дрейф в среднем: A +{da1:.0f} %, B +{db1:.0f} % → лишние +{db1 - da1:.0f} % у B съели эффект:"
                  f" оценка {_EST['blocked']:+.1f} %".replace("-", "−"), "d t", "start"))
    r2, da2, db2 = _order_row(134, "ABBA ABBA AB", "ABBAABBAAB", cell_w, x0)
    b += r2
    b.append(text(x0, 184, f"дрейф в среднем: A +{da2:.1f} %, B +{db2:.1f} % → разница {db2 - da2:.1f} %:"
                  f" оценка {_EST['abba']:+.1f} %, p = 0.016".replace("-", "−"), "a t", "start"))
    b.append(text(16, 214, "Истинный эффект B в модели −15 %. Порядок не меняет число полётов, он решает, на кого ляжет дрейф.",
                  "m t", "start"))
    D["bf-ab-order"] = svg(720, 228, "Порядок полётов в A/B: блоки против ABBA", "".join(b))
