"""Stage 6 diagrams for module bf-modes-osd (modes and OSD on Betaflight 4.5 / 2025.12).

bf-osd-pos-bits — the 16-bit osd_*_pos value as the osd.h macros lay it out (identical in 4.5.3 and 2025.12):
                  bits 0-4 x, 5-9 y, 10 the HD extension of x (x bit 5), 11-13 visibility in OSD profiles 1-3
                  (OSD_PROFILE_BITS_POS 11), 14-15 element variant (OSD_TYPE_MASK 0xC000). Filled with the module's
                  worked example x = 40, y = 17, profiles 1 + 3 -> 11816 (computed below with the same macros as
                  the lab script), and the decode example 21665 -> x 33, y 5, profile 2, variant 1.
"""
from __future__ import annotations

from svg import ACCENT, svg, text


def _osd_pos(x: int, y: int, profiles=(), variant: int = 0) -> int:
    v = (x & 31) | ((x << 5) & 0x400) | ((y & 31) << 5)          # OSD_POS(x, y)
    for p in profiles:
        v |= 1 << (p - 1 + 11)                                   # OSD_PROFILE_FLAG(p)
    return v | (variant << 14)


def _decode(v: int):
    return (v & 31) | ((v & 0x400) >> 5), (v >> 5) & 31, [p for p in (1, 2, 3) if v & (1 << (p + 10))], v >> 14


def pos_bits() -> str:
    W, pad = 720, 16
    val = _osd_pos(40, 17, (1, 3))
    assert val == 11816
    dec = 21665
    assert _decode(dec) == (33, 5, [2], 1) and _osd_pos(33, 5, (2,), 1) == dec
    cw = (W - 2 * pad) / 16
    top = 44
    ch = 34
    # field groups, MSB first: (first bit, last bit, label, contribution text, accent)
    groups = [
        (15, 14, ["вариант", "биты 14–15"], "0", False),
        (13, 11, ["профили 3·2·1", "биты 11–13"], "8192 + 2048", True),
        (10, 10, ["x: бит 5", "бит 10"], "1024", True),
        (9, 5, ["y", "биты 5–9"], "17 × 32 = 544", False),
        (4, 0, ["x", "биты 0–4"], "40 & 31 = 8", False),
    ]
    out = [text(pad, 18, "osd_avg_cell_voltage_pos: x = 40, y = 17, видим в профилях 1 и 3 → 11816 (0x2E28)", "m t", "start", 11)]
    bits = f"{val:016b}"
    for i in range(16):
        b = 15 - i
        x = pad + i * cw
        acc = any(g[4] and g[1] <= b <= g[0] for g in groups)
        one = bits[i] == "1"
        out.append(f'<rect class="{"boxa" if (acc and one) else "box"}" x="{x + 1:.1f}" y="{top}" width="{cw - 2:.1f}" height="{ch}" rx="3"/>')
        out.append(text(x + cw / 2, top - 6, str(b), "m t", "middle", 11))
        out.append(text(x + cw / 2, top + 22, bits[i], "b" if one else "m", "middle", 14))
    gy = top + ch + 10
    for hi, lo, label, contrib, acc in groups:
        x0 = pad + (15 - hi) * cw + 3
        x1 = pad + (15 - lo + 1) * cw - 3
        xm = (x0 + x1) / 2
        out.append(f'<path d="M{x0:.1f} {gy} L{x0:.1f} {gy + 6} L{x1:.1f} {gy + 6} L{x1:.1f} {gy}" '
                   f'stroke="{ACCENT if acc else "currentColor"}" stroke-width="1.3" fill="none"/>')
        out.append(text(xm, gy + 22, label[0], "b" if acc else "", "middle", 11.5))
        out.append(text(xm, gy + 37, label[1], "m t", "middle", 11))
        out.append(text(xm, gy + 54, contrib, "a" if acc else "", "middle", 11.5))
    y = gy + 82
    out.append(text(pad, y, "Сумма: 8 + 544 + 1024 + 2048 + 8192 = 11816 → set osd_avg_cell_voltage_pos = 11816", "", "start", 12))
    out.append(text(pad, y + 20, "x до 63 (5 бит + бит 10), y до 31. Без бита 10 столбец 40 читается как 8 — элемент уедет влево.", "m t", "start", 11))
    out.append(text(pad, y + 38, "Обратно: 21665 = 0x54A1 → вариант 1, профиль 2, x = 1 + 32 = 33, y = 5.", "m t", "start", 11))
    out.append(text(pad, y + 56, "Ни одного профильного бита (341 — умолчание HD-сборки) → элемент скрыт во всех трёх профилях.", "m t", "start", 11))
    return svg(W, y + 68, "Раскладка 16-битного значения osd_*_pos (osd.h, 4.5 и 2025.12)", "".join(out))


def build(D: dict) -> None:
    D["bf-osd-pos-bits"] = pos_bits()
