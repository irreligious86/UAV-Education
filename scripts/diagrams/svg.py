"""Tiny SVG diagram toolkit for the course (no external libraries).

Diagrams inherit colours from the page: fill/stroke use `currentColor` and CSS variables from the
Ground Control design system, so they follow dark/light theme and work offline (inlined at build).

Primitives:
  flow(boxes, links, ...)      – boxes with arrows (data-flow / system diagrams)
  frame(fields, ...)           – byte/bit layout of a protocol frame
  timeline(lanes, ...)         – horizontal timing diagram (stages with durations)
  tree(nodes, ...)             – decision tree (top-down)
"""
from __future__ import annotations

import html
import math
from dataclasses import dataclass, field

ACCENT = "var(--gc-accent-hud, #5ef1d2)"
INK = "currentColor"
MUTED = "var(--gc-ink-muted, #8a93a3)"
WARN = "var(--gc-signal-amber, #f0b24c)"
DANGER = "var(--gc-signal-red, #e8636b)"
PANEL = "var(--gc-surface-200, rgba(128,128,128,0.08))"
FONT = "font-family: var(--gc-font-mono, ui-monospace, Menlo, monospace); font-size: 12px"

STYLE = (
    f"<style>text{{{FONT};fill:{INK}}} .m{{fill:{MUTED}}} .a{{fill:{ACCENT}}} .w{{fill:{WARN}}} .d{{fill:{DANGER}}}"
    f" .box{{fill:{PANEL};stroke:{INK};stroke-width:1.2}} .boxa{{fill:{PANEL};stroke:{ACCENT};stroke-width:1.6}}"
    f" .ln{{stroke:{INK};stroke-width:1.2;fill:none}} .lna{{stroke:{ACCENT};stroke-width:1.6;fill:none}}"
    f" .lnm{{stroke:{MUTED};stroke-width:1;fill:none;stroke-dasharray:4 3}} .t{{font-size:11px}} .b{{font-weight:600}}</style>"
)


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def svg(width: int, height: int, title: str, body: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" role="img" '
            f'aria-labelledby="t" style="max-width:{width}px;display:block;margin:0 auto">'
            f'<title id="t">{esc(title)}</title>{STYLE}'
            '<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M0 0L10 5L0 10z" fill="{INK}"/></marker>'
            '<marker id="ara" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M0 0L10 5L0 10z" fill="{ACCENT}"/></marker></defs>'
            f'{body}</svg>\n')


def text(x, y, s, cls="", anchor="middle", size=None) -> str:
    st = f' style="font-size:{size}px"' if size else ""
    c = f' class="{cls}"' if cls else ""
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}"{c}{st}>{esc(s)}</text>'


def multiline(x, y, lines, cls="", anchor="middle", lh=14, size=None) -> str:
    return "".join(text(x, y + i * lh, ln, cls, anchor, size) for i, ln in enumerate(lines))


# ---------------------------------------------------------------- flow
@dataclass
class Box:
    id: str
    label: str | list[str]
    x: float
    y: float
    w: float = 120
    h: float = 44
    accent: bool = False
    note: str = ""

    def cx(self): return self.x + self.w / 2
    def cy(self): return self.y + self.h / 2


def flow(title: str, boxes: list[Box], links: list[tuple], width: int, height: int, notes: list[tuple] = ()) -> str:
    """links: (from_id, to_id, label='', accent=False, route='h'|'v'|'auto')"""
    by = {b.id: b for b in boxes}
    pairs = {(l[0], l[1]) for l in links}
    out = []
    for b in boxes:
        lines = b.label if isinstance(b.label, list) else [b.label]
        out.append(f'<rect class="{"boxa" if b.accent else "box"}" x="{b.x}" y="{b.y}" width="{b.w}" height="{b.h}" rx="6"/>')
        ty = b.cy() - (len(lines) - 1) * 7 + 4
        out.append(multiline(b.cx(), ty, lines, "b" if b.accent else ""))
        if b.note:
            out.append(text(b.cx(), b.y + b.h + 13, b.note, "m t"))
    for ln in links:
        a, b = by[ln[0]], by[ln[1]]
        label = ln[2] if len(ln) > 2 else ""
        acc = ln[3] if len(ln) > 3 else False
        route = ln[4] if len(ln) > 4 else "auto"
        if route == "auto":
            route = "h" if abs(a.cy() - b.cy()) < 1 or abs(a.cx() - b.cx()) > abs(a.cy() - b.cy()) else "v"
        off = 9 if (ln[1], ln[0]) in pairs else 0   # bidirectional pair: shift each line to its own lane
        if route == "h":
            x1 = a.x + a.w if b.cx() > a.cx() else a.x
            x2 = b.x if b.cx() > a.cx() else b.x + b.w
            y1, y2 = a.cy() + off, b.cy() + off
            mid = (x1 + x2) / 2
            d = f"M{x1} {y1} L{mid} {y1} L{mid} {y2} L{x2} {y2}" if abs(y1 - y2) > 1 else f"M{x1} {y1} L{x2} {y2}"
            lx, ly = mid, min(y1, y2) - 6 if abs(y1 - y2) > 1 else y1 - 7
            if off and b.cx() < a.cx():      # the return lane: label under the line
                ly = y1 + 13
        else:
            y1 = a.y + a.h if b.cy() > a.cy() else a.y
            y2 = b.y if b.cy() > a.cy() else b.y + b.h
            x1, x2 = a.cx() + off, b.cx() + off
            mid = (y1 + y2) / 2
            d = f"M{x1} {y1} L{x1} {mid} L{x2} {mid} L{x2} {y2}" if abs(x1 - x2) > 1 else f"M{x1} {y1} L{x2} {y2}"
            lx, ly = (x1 + x2) / 2 + 6, mid - 4
        out.append(f'<path class="{"lna" if acc else "ln"}" d="{d}" marker-end="url(#{"ara" if acc else "ar"})"/>')
        if label:
            out.append(text(lx, ly, label, "m t", size=10))
    for n in notes:
        out.append(text(n[0], n[1], n[2], n[3] if len(n) > 3 else "m t", n[4] if len(n) > 4 else "start"))
    return svg(width, height, title, "".join(out))


# ---------------------------------------------------------------- frame
def frame(title: str, fields: list[tuple], width: int = 720, unit: str = "байт", note: str = "", scale: float | None = None) -> str:
    """fields: (name, size, accent=False, sub='')  — size in units; drawn proportionally (min width for labels)."""
    total = sum(f[1] for f in fields)
    pad = 16
    usable = width - 2 * pad
    minw = 64
    # sqrt scaling: big fields stay visibly bigger, but single-byte fields keep room for a label
    wsum = sum(math.sqrt(f[1]) for f in fields)
    raw = [max(minw, usable * math.sqrt(f[1]) / wsum) for f in fields]
    k = usable / sum(raw)
    widths = [r * k for r in raw]
    out = []
    x = pad
    y = 28
    h = 46
    for i, (f, w) in enumerate(zip(fields, widths)):
        name, size = f[0], f[1]
        fs = 11 if w >= 72 else 9
        acc = f[2] if len(f) > 2 else False
        sub = f[3] if len(f) > 3 else ""
        out.append(f'<rect class="{"boxa" if acc else "box"}" x="{x:.1f}" y="{y}" width="{w:.1f}" height="{h}" rx="3"/>')
        out.append(text(x + w / 2, y + 20, name, "b" if acc else "", size=fs))
        out.append(text(x + w / 2, y + 36, f"{size} {unit}" if size else "", "m t", size=9))
        if sub:
            sy = y + h + (14 if i % 2 == 0 else 28)
            out.append(f'<line class="lnm" x1="{x + w / 2:.1f}" y1="{y + h}" x2="{x + w / 2:.1f}" y2="{sy - 10}"/>')
            anchor = "end" if x + w / 2 > width - 90 else ("start" if x + w / 2 < 90 else "middle")
            out.append(text(x + w / 2, sy, sub, "m t", anchor, size=9.5))
        x += w
    out.append(text(pad, 16, f"{title} — {total} {unit}" if all(len(f) < 5 for f in fields) else title, "m t", "start"))
    if note:
        out.append(text(pad, y + h + 50, note, "m t", "start"))
    return svg(width, y + h + (58 if note else 40), title, "".join(out))


# ---------------------------------------------------------------- timeline
def timeline(title: str, lanes: list[tuple], t_max: float, width: int = 720, unit: str = "мс", marks: list[tuple] = ()) -> str:
    """lanes: (lane_name, [(t0, t1, label, accent)]) ; marks: (t, label)"""
    pad_l, pad_r, top, lane_h = 120, 16, 46, 34
    usable = width - pad_l - pad_r
    X = lambda t: pad_l + usable * t / t_max
    out = [text(16, 16, title, "m t", "start")]
    for i, (name, segs) in enumerate(lanes):
        y = top + i * lane_h
        out.append(text(pad_l - 8, y + 21, name, "", "end", size=11))
        out.append(f'<line class="lnm" x1="{pad_l}" y1="{y + lane_h - 2}" x2="{width - pad_r}" y2="{y + lane_h - 2}"/>')
        for s in segs:
            t0, t1, label = s[0], s[1], s[2]
            acc = s[3] if len(s) > 3 else False
            x0, x1 = X(t0), X(t1)
            out.append(f'<rect class="{"boxa" if acc else "box"}" x="{x0:.1f}" y="{y + 5}" width="{max(2, x1 - x0):.1f}" height="{lane_h - 12}" rx="3"/>')
            if x1 - x0 > 30:
                out.append(text((x0 + x1) / 2, y + 20, label, "b" if acc else "", size=10))
            else:
                out.append(text(x1 + 4, y + 20, label, "m t", "start", size=10))
    h = top + len(lanes) * lane_h + 24
    # axis
    for k in range(0, 6):
        t = t_max * k / 5
        out.append(f'<line class="lnm" x1="{X(t):.1f}" y1="{top - 6}" x2="{X(t):.1f}" y2="{h - 20}"/>')
        out.append(text(X(t), h - 6, f"{t:g} {unit}", "m t", size=10))
    for m in marks:
        out.append(f'<line class="lna" x1="{X(m[0]):.1f}" y1="{top - 8}" x2="{X(m[0]):.1f}" y2="{h - 20}"/>')
        out.append(text(min(X(m[0]) + 4, width - 150), top - 12, m[1], "a t", "start", size=10))
    return svg(width, h, title, "".join(out))


# ---------------------------------------------------------------- tree
@dataclass
class Node:
    id: str
    label: str | list[str]
    children: list[tuple] = field(default_factory=list)   # (edge_label, Node)
    accent: bool = False
    leaf: bool = False


def tree(title: str, root: Node, width: int = 720, box_w: int = 150, box_h: int = 40, gap_y: int = 70) -> str:
    # compute leaf count for layout
    def leaves(n): return max(1, sum(leaves(c[1]) for c in n.children)) if n.children else 1
    total = leaves(root)
    slot = (width - 20) / total
    out = []
    depth_max = [0]

    def place(n, depth, x0):
        w = leaves(n) * slot
        cx = x0 + w / 2
        y = 34 + depth * gap_y
        depth_max[0] = max(depth_max[0], depth)
        lines = n.label if isinstance(n.label, list) else [n.label]
        bw = min(box_w, w - 6)
        cls = "boxa" if n.accent else "box"
        rx = 18 if n.leaf else 6
        out.append(f'<rect class="{cls}" x="{cx - bw / 2:.1f}" y="{y}" width="{bw:.1f}" height="{box_h}" rx="{rx}"/>')
        fs = 10.5 if bw >= 140 else 9.5
        out.append(multiline(cx, y + box_h / 2 - (len(lines) - 1) * 6 + 4, lines, "b" if n.accent else "", size=fs, lh=12))
        cx0 = x0
        for (el, c) in n.children:
            cw = leaves(c) * slot
            ccx = cx0 + cw / 2
            cy = 34 + (depth + 1) * gap_y
            mid = (y + box_h + cy) / 2
            out.append(f'<path class="ln" d="M{cx:.1f} {y + box_h} L{cx:.1f} {mid} L{ccx:.1f} {mid} L{ccx:.1f} {cy}" marker-end="url(#ar)"/>')
            if el:
                out.append(text(ccx + 4, mid - 4, el, "a t", "start", size=10))
            place(c, depth + 1, cx0)
            cx0 += cw
    place(root, 0, 10)
    h = 34 + (depth_max[0] + 1) * gap_y + 10
    return svg(width, h, title, text(16, 16, title, "m t", "start") + "".join(out))
