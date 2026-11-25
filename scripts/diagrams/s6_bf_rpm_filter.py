"""Stage 6 diagram for module bf-rpm-filter (Betaflight 4.5.3 flight/rpm_filter.c, rpmFilterUpdate()).

chart-bf-rpm-notch-weight — effective weight of each RPM notch vs motor rpm: f_k = k·rpm/60 is clamped to
                            [rpm_filter_min_hz, maxHz], weight = (f_k − min_hz)/fade_range_hz inside the fade band,
                            times rpm_filter_weights[k]. Defaults min 100 Hz, fade 50 Hz, weights 100/100/100 for
                            harmonics 1–3; dashed: harmonic 1 with min_hz 50 (the module's 10" case).
                            Mark: dynamic idle 30 (3000 rpm) — the module's worked example.
"""
from __future__ import annotations

from plot import Axis, chart


def _w(rpm: float, k: int, min_hz=100.0, fade=50.0, weight=1.0) -> float:
    f = max(k * rpm / 60.0, min_hz)          # constrainf(..., minHz, maxHz); maxHz is far above this range
    margin = f - min_hz
    w = margin / fade if (fade > 0 and margin < fade) else 1.0
    return w * weight


def build(D: dict) -> None:
    rpm = list(range(0, 12001, 50))
    D["chart-bf-rpm-notch-weight"] = chart(
        "Сила RPM-notch от оборотов: min_hz 100, fade 50",
        [dict(name="1-я гармоника", xs=rpm, ys=[_w(r, 1) for r in rpm], cls="a",
              label_at=9300, label_dy=-8, label_anchor="start"),
         dict(name="2-я", xs=rpm, ys=[_w(r, 2) for r in rpm], cls="w", label_at=3700, label_dy=-6,
              label_anchor="end"),
         dict(name="3-я", xs=rpm, ys=[_w(r, 3) for r in rpm], cls="ink", label_at=2350, label_dy=-6,
              label_anchor="end"),
         dict(name="1-я при min_hz 50", xs=rpm, ys=[_w(r, 1, 50.0) for r in rpm], cls="d", dash=True,
              label_at=5000, label_dy=32, label_anchor="start")],
        Axis("обороты мотора, об/мин", 0, 12000, ticks=[0, 2000, 3000, 4500, 6000, 9000, 12000]),
        Axis("вес notch (0 — выключен)", 0, 1.1, ticks=[0, 0.25, 0.5, 0.75, 1.0]),
        marks=[(3000, "dyn idle 30", "m", 20), (6000, "100 Гц", "a", 230), (9000, "150 Гц", "a", 250)])
