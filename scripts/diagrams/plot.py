"""Static SVG charts for the course, in the same theme as svg.py (no external libraries).

  chart(title, series, x=Axis(...), y=Axis(...), y2=None, marks=..., bands=..., notes=...)
  polar(title, series, rmin_db=-30)

Series: dict(name, xs, ys, cls='ink'|'a'|'w'|'d'|'m', dash=False, axis=1|2, dots=False, label_at=None).
Every curve is labelled at its end (or at label_at = x) instead of a legend: readable on a phone and
without colour. Data are computed in Python at build time from formulas stated in the module.
"""
from __future__ import annotations

import math
import zlib
from dataclasses import dataclass

from svg import ACCENT, DANGER, INK, MUTED, WARN, esc, svg, text

STROKE = {"ink": INK, "a": ACCENT, "w": WARN, "d": DANGER, "m": MUTED}


@dataclass
class Axis:
    label: str
    lo: float
    hi: float
    log: bool = False
    ticks: list | None = None          # explicit tick values
    fmt: str = "{:g}"


def _nice_ticks(lo: float, hi: float, n: int = 6) -> list[float]:
    span = hi - lo
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = min((s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw), default=10 * mag)
    first = math.ceil(lo / step - 1e-9) * step
    out, v = [], first
    while v <= hi + 1e-9 * span:
        out.append(round(v, 10))
        v += step
    return out


def _log_ticks(lo: float, hi: float) -> list[float]:
    out = []
    for e in range(math.floor(math.log10(lo)), math.ceil(math.log10(hi)) + 1):
        for m in (1, 2, 5):
            v = m * 10 ** e
            if lo <= v <= hi:
                out.append(v)
    return out


class _Scale:
    def __init__(self, ax: Axis, p0: float, p1: float):
        self.ax, self.p0, self.p1 = ax, p0, p1
        self.a = math.log10(ax.lo) if ax.log else ax.lo
        self.b = math.log10(ax.hi) if ax.log else ax.hi

    def __call__(self, v: float) -> float:
        v = math.log10(max(v, 1e-12)) if self.ax.log else v
        return self.p0 + (v - self.a) / (self.b - self.a) * (self.p1 - self.p0)

    def ticks(self):
        if self.ax.ticks is not None:
            return self.ax.ticks
        return _log_ticks(self.ax.lo, self.ax.hi) if self.ax.log else _nice_ticks(self.ax.lo, self.ax.hi)


def _path(pts) -> str:
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)


def chart(title: str, series: list[dict], x: Axis, y: Axis, y2: Axis | None = None, width: int = 720,
          height: int = 360, marks: list[tuple] = (), hmarks: list[tuple] = (), bands: list[tuple] = (),
          notes: list[tuple] = (), legend: list[tuple] = (), legend_at: tuple = (0, 0)) -> str:
    """marks: vertical lines (x, label, cls); hmarks: horizontal (y, label, cls, axis=1);
    bands: shaded x-ranges (x0, x1, label); notes: free text (x_px, y_px, text, cls)."""
    L, R, T, B = 64, 64 if y2 else 24, 36, 48
    sx = _Scale(x, L, width - R)
    sy = _Scale(y, height - B, T)
    sy2 = _Scale(y2, height - B, T) if y2 else None
    cid = "pc" + format(zlib.crc32(title.encode()), "x")
    out = [text(L, 20, title, "b", "start", 13)]
    for x0, x1, lab in bands:
        a, b = sx(x0), sx(x1)
        out.append(f'<rect x="{a:.1f}" y="{T}" width="{b - a:.1f}" height="{height - B - T}" fill="{WARN}" opacity="0.10"/>')
        out.append(text((a + b) / 2, T + 14, lab, "w t"))
    # grid and ticks
    for v in sx.ticks():
        px = sx(v)
        out.append(f'<line x1="{px:.1f}" y1="{T}" x2="{px:.1f}" y2="{height - B}" stroke="{MUTED}" stroke-width="0.5" opacity="0.4"/>')
        out.append(text(px, height - B + 16, x.fmt.format(v), "m t"))
    for v in sy.ticks():
        py = sy(v)
        out.append(f'<line x1="{L}" y1="{py:.1f}" x2="{width - R}" y2="{py:.1f}" stroke="{MUTED}" stroke-width="0.5" opacity="0.4"/>')
        out.append(text(L - 6, py + 4, y.fmt.format(v), "m t", "end"))
    if sy2:
        for v in sy2.ticks():
            out.append(text(width - R + 6, sy2(v) + 4, y2.fmt.format(v), "m t", "start"))
    out.append(f'<rect x="{L}" y="{T}" width="{width - L - R}" height="{height - B - T}" fill="none" stroke="{INK}" stroke-width="1"/>')
    out.append(text((L + width - R) / 2, height - 10, x.label, "m"))
    out.append(f'<text transform="translate(16 {(T + height - B) / 2}) rotate(-90)" text-anchor="middle" class="m">{esc(y.label)}</text>')
    if y2:
        out.append(f'<text transform="translate({width - 12} {(T + height - B) / 2}) rotate(90)" text-anchor="middle" class="m">{esc(y2.label)}</text>')
    for mk in marks:
        v, lab, cls = mk[:3]
        dy = mk[3] if len(mk) > 3 else 28
        px = sx(v)
        out.append(f'<line x1="{px:.1f}" y1="{T}" x2="{px:.1f}" y2="{height - B}" stroke="{STROKE.get(cls, INK)}" stroke-width="1.2" stroke-dasharray="5 3"/>')
        out.append(text(px + 4, T + dy, lab, f"{cls} t" if cls != "ink" else "t", "start"))
    for hm in hmarks:
        v, lab, cls = hm[:3]
        s = sy2 if (len(hm) > 3 and hm[3] == 2) else sy
        py = s(v)
        out.append(f'<line x1="{L}" y1="{py:.1f}" x2="{width - R}" y2="{py:.1f}" stroke="{STROKE.get(cls, INK)}" stroke-width="1.2" stroke-dasharray="5 3"/>')
        out.append(text(width - R - 4, py - 5, lab, f"{cls} t" if cls != "ink" else "t", "end"))
    # clip curves to the plot area
    out.append(f'<clipPath id="{cid}"><rect x="{L}" y="{T}" width="{width - L - R}" height="{height - B - T}"/></clipPath>')
    for s in series:
        scale_y = sy2 if s.get("axis") == 2 else sy
        pts = [(sx(a), scale_y(b)) for a, b in zip(s["xs"], s["ys"]) if b is not None]
        col = STROKE.get(s.get("cls", "ink"), INK)
        if s.get("band"):          # (ys_low, ys_high) shaded
            lo, hi = s["band"]
            poly = [(sx(a), scale_y(b)) for a, b in zip(s["xs"], hi)] + [(sx(a), scale_y(b)) for a, b in reversed(list(zip(s["xs"], lo)))]
            out.append(f'<path d="{_path(poly)} Z" fill="{col}" opacity="0.15" clip-path="url(#{cid})"/>')
        if s.get("dots"):
            out += [f'<circle cx="{px:.1f}" cy="{py:.1f}" r="2.2" fill="{col}" clip-path="url(#{cid})"/>' for px, py in pts]
        else:
            dash = ' stroke-dasharray="6 4"' if s.get("dash") else ""
            out.append(f'<path d="{_path(pts)}" fill="none" stroke="{col}" stroke-width="{s.get("w", 2)}"{dash} clip-path="url(#{cid})"/>')
        if s.get("name"):
            if s.get("label_at") is not None:
                i = min(range(len(s["xs"])), key=lambda k: abs(s["xs"][k] - s["label_at"]))
            else:
                inside = [k for k, (px, py) in enumerate(pts) if L <= px <= width - R and T <= py <= height - B]
                i = inside[-1] if inside else len(pts) - 1
            px, py = pts[i]
            dy = s.get("label_dy", -6)
            anchor = s.get("label_anchor", "end")
            out.append(text(px + (-4 if anchor == "end" else 4), py + dy, s["name"], (s.get("cls", "") if s.get("cls") != "ink" else "") + " t b", anchor))
    lx, ly = legend_at
    for i, (name, cls, dash) in enumerate(legend):
        y0 = ly + i * 16
        d = ' stroke-dasharray="6 4"' if dash else ""
        out.append(f'<line x1="{lx}" y1="{y0 - 4}" x2="{lx + 26}" y2="{y0 - 4}" stroke="{STROKE.get(cls, INK)}" stroke-width="2"{d}/>')
        out.append(text(lx + 32, y0, name, "t", "start"))
    for nx, ny, t, cls in notes:
        out.append(text(nx, ny, t, cls + " t", "start"))
    return svg(width, height, title, "".join(out))


def polar(title: str, series: list[dict], rmin_db: float = -30, size: int = 340, gap: int = 40) -> str:
    """Side-by-side polar patterns. series: dict(name, fn(theta_rad) -> gain_linear_power, cls).
    0 dB at the outer ring, rmin_db at the centre; 0° points up."""
    n = len(series)
    width = n * size + (n - 1) * gap
    height = size + 64
    out = [text(10, 20, title, "b", "start", 13)]
    r0 = size / 2 - 22
    for k, s in enumerate(series):
        cx = k * (size + gap) + size / 2
        cy = 36 + size / 2
        for db in range(0, int(rmin_db) - 1, -10):
            r = r0 * (1 - db / rmin_db)
            out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="none" stroke="{MUTED}" stroke-width="0.6" opacity="0.5"/>')
            out.append(text(cx + 3, cy - r + 11, f"{db} дБ", "m t", "start"))
        for a in range(0, 360, 30):
            t = math.radians(a)
            out.append(f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{cx + r0 * math.sin(t):.1f}" y2="{cy - r0 * math.cos(t):.1f}" stroke="{MUTED}" stroke-width="0.5" opacity="0.4"/>')
        pts = []
        for i in range(0, 361, 2):
            t = math.radians(i)
            g = max(s["fn"](t), 1e-9)
            db = max(10 * math.log10(g), rmin_db)
            r = r0 * (1 - db / rmin_db)
            pts.append((cx + r * math.sin(t), cy - r * math.cos(t)))
        out.append(f'<path d="{_path(pts)} Z" fill="{STROKE.get(s.get("cls", "a"))}" fill-opacity="0.12" stroke="{STROKE.get(s.get("cls", "a"))}" stroke-width="2"/>')
        out.append(text(cx, cy + r0 + 34, s["name"], "b"))
        if s.get("sub"):
            out.append(text(cx, cy + r0 + 50, s["sub"], "m t"))
    return svg(width, height + 12, title, "".join(out))
