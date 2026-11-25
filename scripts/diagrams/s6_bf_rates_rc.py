"""Stage 6 diagrams for module bf-rates-rc (Betaflight 4.5 fc/rc.c: rates, RC smoothing).

chart-bf-rates-curves      — the module's converter run: Actual 20/67/54 vs Betaflight 101/70/1 (max 4 deg/s apart),
                             default Actual 7/67/0 vs its best Betaflight fit 208/3/89 (151 deg/s apart at stick 0.71).
chart-bf-rc-smoothing-step — the module's PT3 run: stick step 0 -> 670 deg/s, first packet T/2 after the snap,
                             8 kHz PID loop, auto cutoff floor(0.375 * f_rx): 50/150/500/1000 Hz -> 18/56/187/375 Hz,
                             plus the unsmoothed 50 Hz step.
chart-bf-actual-two-profiles — applyActualRates (4.5.3 fc/rc.c:209) for the module's worked example:
                             70/670/0 vs 200/850/0.20; 185 vs 232 deg/s at half stick, dashed C·x = linear part.
flow-bf-ff-pipeline        — calculateFeedforward() of 4.5.3 (fc/rc.c:499-626) step by step, then PT3 and Kf (pid.c).
"""
from __future__ import annotations

import math

from plot import Axis, chart
from svg import Box, flow


def _bf(x, rc_rate, srate, expo):            # applyBetaflightRates
    a = abs(x)
    if expo:
        e = expo / 100
        x = x * a ** 3 * e + x * (1 - e)
    r = rc_rate / 100
    if r > 2.0:
        r += 14.54 * (r - 2.0)
    rate = 200.0 * r * x
    if srate:
        rate *= 1.0 / min(max(1.0 - a * srate / 100, 0.01), 1.0)
    return rate


def _actual(x, rc_rate, srate, expo):        # applyActualRates
    a = abs(x)
    e = expo / 100
    c = rc_rate * 10.0
    return x * c + max(0.0, srate * 10.0 - c) * a * (x ** 5 * e + x * (1 - e))


def _pt3_step(rx_hz, cutoff, smoothing=True, dt=125e-6, t_end=0.04, target=670.0):
    w = 2 * math.pi * cutoff * 1.961459177 * dt
    k = w / (w + 1) if smoothing else 1.0
    s1 = s2 = s3 = 0.0
    xs, ys = [0.0], [0.0]
    for i in range(1, int(t_end / dt) + 1):
        t = i * dt
        raw = target if t >= 0.5 / rx_hz else 0.0
        s1 += k * (raw - s1)
        s2 += k * (s1 - s2)
        s3 += k * (s2 - s3)
        if i % 4 == 0 or t < 0.005:
            xs.append(t * 1e3)
            ys.append(s3)
    return xs, ys


def build(D: dict) -> None:
    build_ff(D)
    xs = [i / 100 for i in range(101)]
    series = [
        dict(name="Actual 20/67/54", xs=xs, ys=[_actual(x, 20, 67, 54) for x in xs], cls="a",
             label_at=0.40, label_dy=-22),
        dict(name="BF 1.01/0.70/0.01", xs=xs, ys=[_bf(x, 101, 70, 1) for x in xs], cls="ink", dash=True,
             label_at=0.80, label_dy=22, label_anchor="start"),
        dict(name="Actual 7/67/0 (дефолт)", xs=xs, ys=[_actual(x, 7, 67, 0) for x in xs], cls="w",
             label_at=0.50, label_dy=-10),
        dict(xs=xs, ys=[_bf(x, 208, 3, 89) for x in xs], cls="d", dash=True),
    ]
    D["chart-bf-rates-curves"] = chart(
        "Рейты с одинаковыми центром и максимумом: совпадают не всегда",
        series, Axis("отклонение стика x", 0, 1, ticks=[0, 0.25, 0.5, 0.75, 1.0]),
        Axis("setpoint, °/с", 0, 700, ticks=[0, 100, 200, 300, 400, 500, 600, 700]),
        marks=[(0.71, "разница 151 °/с", "d", 40)],
        notes=[(72, 56, "Центр 200 и 70 °/с, максимум 670 °/с; пунктир — Betaflight", "m"),
               (540, 292, "BF 2.08/0.03/0.89", "d b")])

    curves = []
    t0, t1 = 0.3, 60.0
    for hz, cut, cls in ((1000, 375, "ink"), (500, 187, "a"), (150, 56, "d"), (50, 18, "w")):
        tx, ty = _pt3_step(hz, cut, t_end=t1 / 1e3)
        pts = [(a, b) for a, b in zip(tx, ty) if a >= t0]
        t50 = next(a for a, b in pts if b >= 335)
        curves.append(dict(name=f"{hz}/{cut} Гц", xs=[a for a, _ in pts], ys=[b for _, b in pts], cls=cls,
                           label_at=t50, label_dy=-6, label_anchor="end"))
    tx, ty = _pt3_step(50, 18, smoothing=False, t_end=t1 / 1e3)
    pts = [(a, b) for a, b in zip(tx, ty) if a >= t0]
    curves.append(dict(xs=[a for a, _ in pts], ys=[b for _, b in pts], cls="m", dash=True))
    px10 = 64 + (math.log10(10) - math.log10(t0)) / (math.log10(t1) - math.log10(t0)) * (720 - 64 - 24)
    D["chart-bf-rc-smoothing-step"] = chart(
        "RC smoothing auto (factor 30): ступенька стика 0 → 670 °/с",
        curves, Axis("время после движения стика, мс (лог. шкала)", t0, t1, log=True,
                     ticks=[0.5, 1, 2, 5, 10, 20, 50]),
        Axis("setpoint, °/с", 0, 700, ticks=[0, 100, 200, 335, 500, 600, 700]),
        hmarks=[(335, "50 %", "m")],
        notes=[(px10 + 4, 200, "50 Гц без", "m"), (px10 + 4, 214, "сглаживания", "m"),
               (72, 56, "подпись: packet rate / срез PT3", "m")])


def build_ff(D: dict) -> None:
    xs = [i / 100 for i in range(101)]
    D["chart-bf-actual-two-profiles"] = chart(
        "Actual: C·x + (M − C)·|x|·(x⁵·e + x·(1 − e))",
        [dict(name="200/850/0.20", xs=xs, ys=[_actual(x, 20, 85, 20) for x in xs], cls="a",
              label_at=0.80, label_dy=-10),
         dict(name="70/670/0 (дефолт)", xs=xs, ys=[_actual(x, 7, 67, 0) for x in xs], cls="w",
              label_at=0.62, label_dy=24, label_anchor="start"),
         dict(name="200·x", xs=xs, ys=[200 * x for x in xs], cls="a", dash=True, w=1.2, label_at=1.0, label_dy=-6),
         dict(name="70·x", xs=xs, ys=[70 * x for x in xs], cls="w", dash=True, w=1.2, label_at=1.0, label_dy=-6)],
        Axis("отклонение стика x", 0, 1, ticks=[0, 0.25, 0.5, 0.75, 1.0]),
        Axis("setpoint, °/с", 0, 900, ticks=[0, 185, 232, 400, 600, 670, 850]),
        marks=[(0.5, "x = 0.5: 185 и 232 °/с", "m", 62)],
        notes=[(72, 56, "пунктир — C·x", "m"),
               (72, 72, "у упора 12.7 / 20.2 °/с на 1 %", "m")])

    W, H, G, X0 = 128, 48, 14, 10
    col = [X0 + i * (W + G) for i in range(5)]
    boxes = [
        Box("pkt", ["Новый RC-пакет", "rcCommand, sp"], col[0], 40, W, H),
        Box("spd", ["Скорость sp", "Δsp · f_rx"], col[1], 40, W, H, accent=True, note="дубликат: экстраполяция"),
        Box("pt1", ["PT1 скорости", "k = 1 − smooth/100"], col[2], 40, W, H, accent=True),
        Box("bst", ["+ boost", "Δv·f·boost/1000"], col[3], 40, W, H),
        Box("trn", ["transition", "× |x|/tr у центра"], col[4], 40, W, H),
        Box("avg", ["averaging", "среднее 2…4 пак."], col[4], 140, W, H),
        Box("jit", ["× jitter_att", "Δ rcCommand < j"], col[3], 140, W, H, accent=True),
        Box("lim", ["max_rate_limit", "≤ (max−|sp|)·90"], col[2], 140, W, H, accent=True),
        Box("pt3", ["PT3 RC smoothing", "срез FF (авто)"], col[1], 140, W, H),
        Box("kf", ["× Kf → F-член", "Kf=0.013754·F/100"], col[0], 140, W, H),
    ]
    links = [("pkt", "spd"), ("spd", "pt1"), ("pt1", "bst"), ("bst", "trn"), ("trn", "avg", "", False, "v"),
             ("avg", "jit"), ("jit", "lim"), ("lim", "pt3"), ("pt3", "kf")]
    D["flow-bf-ff-pipeline"] = flow(
        "Feedforward 4.5.3: что делает calculateFeedforward() с каждым пакетом", boxes, links, 720, 260,
        notes=[(10, 220, "jitter_att = 1 − max(0, 1 − (Δ + Δпред)/(2·j))², при Δ < j (j = jitter_factor)", "m t"),
               (10, 238, "всё до limit — раз на RC-пакет; PT3 и ×Kf — каждый PID-цикл; limit — roll/pitch", "m t")])
