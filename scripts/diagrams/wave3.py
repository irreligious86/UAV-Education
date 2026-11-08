"""Charts (Stage 4, iteration 1): quantitative plots computed from the formulas the modules teach.

Each chart states its model in the caption of the module that embeds it; numbers are the module's own
worked-example values, so the picture and the text agree.
"""
from __future__ import annotations

import math
import random

from plot import Axis, chart, polar


def lin(a, b, n=200):
    return [a + (b - a) * i / (n - 1) for i in range(n)]


def logspace(a, b, n=240):
    la, lb = math.log10(a), math.log10(b)
    return [10 ** (la + (lb - la) * i / (n - 1)) for i in range(n)]


def interp(table, x):
    """table: list of (x, y) sorted by x."""
    for (x0, y0), (x1, y1) in zip(table, table[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return table[-1][1] if x > table[-1][0] else table[0][1]


def build(D: dict) -> None:
    # ------------------------------------------------------------ f-aero-props
    u = lin(0, 1)
    tmax, imax, vbat = 1500.0, 40.0, 22.2
    D["chart-thrust-current"] = chart(
        "Тяга и ток от газа: T ∝ n², I ∝ n³ (5\", 6S, ориентир 1.5 кг / 40 А)",
        [dict(name="тяга, г", xs=[x * 100 for x in u], ys=[tmax * x ** 2 for x in u], cls="a"),
         dict(name="ток, А", xs=[x * 100 for x in u], ys=[imax * x ** 3 for x in u], cls="w", axis=2, label_at=88, label_dy=16)],
        Axis("газ (≈ обороты), %", 0, 100), Axis("тяга, г", 0, 1600), Axis("ток, А", 0, 45),
        marks=[(50, "50 %: 375 г, 5 А → 3.4 г/Вт", "m")],
        notes=[(80, 70, "100 %: 1500 г, 40 А → 1.7 г/Вт", "w")])

    # ------------------------------------------------------------ f-power
    lipo = [(0, 4.20), (10, 4.11), (20, 4.02), (30, 3.95), (40, 3.87), (50, 3.84), (60, 3.80), (70, 3.77), (80, 3.73), (90, 3.69), (95, 3.61), (100, 3.27)]
    liion = [(0, 4.20), (10, 4.06), (20, 3.96), (30, 3.87), (40, 3.79), (50, 3.70), (60, 3.62), (70, 3.55), (80, 3.46), (90, 3.30), (95, 3.15), (100, 2.80)]
    c = lin(0, 100)
    D["chart-discharge"] = chart(
        "Напряжение банки под нагрузкой: U = OCV − I·R (типичная форма кривых)",
        [dict(name="", xs=c, ys=[interp(lipo, x) - 1.3 * 0.0025 for x in c], cls="a"),
         dict(name="", xs=c, ys=[interp(lipo, x) - 52 * 0.0025 for x in c], cls="a", dash=True),
         dict(name="", xs=c, ys=[interp(liion, x) - 4.2 * 0.015 for x in c], cls="w"),
         dict(name="", xs=c, ys=[interp(liion, x) - 12.6 * 0.015 for x in c], cls="w", dash=True)],
        Axis("израсходовано ёмкости, %", 0, 100), Axis("напряжение банки, В", 2.4, 4.3),
        hmarks=[(3.5, "посадка LiPo 3.5 В", "a"), (3.0, "отсечка Li-Ion 3.0 В", "w")],
        legend=[("LiPo, слабая нагрузка", "a", False), ("LiPo 40C: 52 А, R 2.5 мОм", "a", True),
                ("Li-Ion 1C: 4.2 А, R 15 мОм", "w", False), ("Li-Ion 3C: 12.6 А", "w", True)], legend_at=(90, 254))

    # ------------------------------------------------------------ bf-filters
    f = logspace(10, 1000)
    db = lambda g: 20 * math.log10(max(g, 1e-6))
    pt1 = [db(1 / math.sqrt(1 + (x / 100) ** 2)) for x in f]
    bq = [db(1 / math.sqrt(1 + (x / 100) ** 4)) for x in f]
    q, f0 = 3.0, 200.0
    notch = [db(abs(1 - (x / f0) ** 2) / math.sqrt((1 - (x / f0) ** 2) ** 2 + (x / (f0 * q)) ** 2)) for x in f]
    D["chart-filter-response"] = chart(
        "АЧХ фильтров гироскопа: PT1 и biquad на 100 Гц, notch 200 Гц (Q = 3)",
        [dict(name="PT1 100 Гц: −20 дБ/дек", xs=f, ys=pt1, cls="a", label_at=600, label_dy=-8),
         dict(name="biquad 100 Гц: −40 дБ/дек", xs=f, ys=bq, cls="w", label_at=250, label_dy=22, label_anchor="start"),
         dict(name="notch 200 Гц", xs=f, ys=notch, cls="ink", dash=True, label_at=200, label_dy=-6, label_anchor="start")],
        Axis("частота, Гц", 10, 1000, log=True), Axis("усиление, дБ", -40, 3, ticks=[-40, -30, -20, -10, -3, 0]),
        hmarks=[(-3, "−3 дБ = частота среза", "m")],
        notes=[(74, 300, "Задержка на низких частотах: PT1 ≈ 1/(2π·fc) = 1.6 мс, biquad ≈ 2.3 мс", "m")])

    # ------------------------------------------------------------ ctl-signals
    def psd(x):
        floor = -38 + 6 * math.exp(-x / 40)                       # rising floor at low freq (vibration, motion)
        peaks = [(180, 26, 6), (360, 18, 9), (540, 10, 12), (260, 14, 3)]
        v = 10 ** (floor / 10)
        for fc, h, w in peaks:
            v += 10 ** ((floor + h) / 10) / (1 + ((x - fc) / w) ** 2)
        motion = 10 ** ((-12) / 10) / (1 + (x / 6) ** 2)          # stick inputs and flight motion
        return 10 * math.log10(v + motion)
    fs = lin(1, 1000, 500)
    D["chart-gyro-spectrum"] = chart(
        "Модельный спектр гироскопа: что есть что",
        [dict(name="", xs=fs, ys=[psd(x) for x in fs], cls="a")],
        Axis("частота, Гц", 0, 1000), Axis("плотность мощности, дБ", -45, 0),
        marks=[(180, "1× мотор", "a"), (360, "2×", "a"), (540, "3×", "a"), (260, "рама", "w", 44)],
        notes=[(90, 300, "0–20 Гц: движение — сигнал", "m"),
               (430, 300, "гармоники едут с газом, рама — нет", "m")])
    tf = lin(0, 1500, 601)
    D["chart-aliasing"] = chart(
        "Алиасинг: какую частоту «увидит» выборка 1 кГц",
        [dict(name="наблюдаемая частота", xs=tf, ys=[abs(x - 1000 * round(x / 1000)) for x in tf], cls="a", label_at=1250, label_dy=-8),
         dict(name="без алиасинга", xs=tf, ys=tf, cls="m", dash=True, label_at=420, label_dy=-8)],
        Axis("истинная частота вибрации, Гц", 0, 1500), Axis("частота в данных, Гц", 0, 600),
        marks=[(500, "Найквист fs/2", "w"), (700, "700 Гц → 300 Гц", "d", 48)])

    # ------------------------------------------------------------ rf-antennas
    D["chart-antenna-patterns"] = polar(
        "Диаграммы направленности (мощность, дБ относительно максимума)",
        [dict(name="Диполь, вертикальный", sub="срез по вертикали: ноль вдоль оси", fn=lambda t: math.sin(t) ** 2, cls="a"),
         dict(name="Патч", sub="срез по горизонтали: вперёд ~±35°", fn=lambda t: max(math.cos(t), 0) ** 4 + 0.01, cls="w")])

    # ------------------------------------------------------------ rf-link-budget
    d = logspace(0.1, 60)
    fspl = lambda km, mhz: 20 * math.log10(km) + 20 * math.log10(mhz) + 32.44
    D["chart-link-margin"] = chart(
        "Принятая мощность от дистанции: 250 мВт, антенны +2/0 дБи, потери 4 дБ",
        [dict(name="2.4 ГГц", xs=d, ys=[24 + 2 - 4 - fspl(x, 2400) for x in d], cls="a", label_at=0.3, label_dy=-8, label_anchor="start"),
         dict(name="868 МГц", xs=d, ys=[24 + 2 - 4 - fspl(x, 868) for x in d], cls="w", label_at=1.0, label_dy=-8, label_anchor="start")],
        Axis("дистанция, км (без учёта зоны Френеля и препятствий)", 0.1, 60, log=True), Axis("принятая мощность, дБм", -130, -50),
        hmarks=[(-105, "ELRS 2.4: 500 Hz −105, 250 Hz −108", "a"), (-108, "", "a"), (-115, "50 Hz: −115", "a"), (-123, "900 МГц 25 Hz: −123", "w")],
        marks=[(10, "10 км", "m")])

    # ------------------------------------------------------------ est-kalman
    rng = random.Random(3)
    true, R, Q = 10.0, 4.0, 0.0
    xs, zs, est, lo, hi = [], [], [], [], []
    x_hat, P = 0.0, 100.0
    for k in range(40):
        z = true + rng.gauss(0, math.sqrt(R))
        P = P + Q
        K = P / (P + R)
        x_hat = x_hat + K * (z - x_hat)
        P = (1 - K) * P
        xs.append(k + 1); zs.append(z); est.append(x_hat)
        lo.append(x_hat - math.sqrt(P)); hi.append(x_hat + math.sqrt(P))
    D["chart-kalman-1d"] = chart(
        "Калман на постоянной величине: измерения σ = 2, оценка и её ±σ = √P",
        [dict(name="измерения z", xs=xs, ys=zs, cls="m", dots=True, label_at=3, label_dy=-10, label_anchor="start"),
         dict(name="оценка x̂ ± √P", xs=xs, ys=est, cls="a", band=(lo, hi), label_at=40, label_dy=-10),
         dict(name="истина", xs=xs, ys=[true] * len(xs), cls="ink", dash=True, w=1, label_at=40, label_dy=16)],
        Axis("шаг k", 1, 40), Axis("значение", 4, 16),
        notes=[(300, 300, "K = P/(P+R): 0.96 на первом шаге, 0.06 на двадцатом", "m")])

    # ------------------------------------------------------------ ctl-theory
    t = lin(0, 12, 300)
    def step(z):
        if z >= 1:
            return [1 - math.exp(-x) * (1 + x) for x in t]
        wd = math.sqrt(1 - z * z)
        return [1 - math.exp(-z * x) * (math.cos(wd * x) + z / wd * math.sin(wd * x)) for x in t]
    D["chart-step-responses"] = chart(
        "Переходный процесс второго порядка при разном ζ",
        [dict(name="ζ = 0.3: 37 %", xs=t, ys=step(0.3), cls="d", label_at=3.3, label_dy=-6, label_anchor="start"),
         dict(name="ζ = 0.5: 16 %", xs=t, ys=step(0.5), cls="w", label_at=4.4, label_dy=-8, label_anchor="start"),
         dict(name="ζ = 0.7: 4.6 % — цель", xs=t, ys=step(0.7), cls="a", label_at=6.5, label_dy=-8, label_anchor="start"),
         dict(name="ζ = 1: без перерегулирования", xs=t, ys=step(1.0), cls="m", label_at=7, label_dy=16, label_anchor="start")],
        Axis("время × ωₙ", 0, 12), Axis("отклик на ступеньку", 0, 1.45),
        hmarks=[(1.0, "", "m")])

    # ------------------------------------------------------------ per-mapping
    h = lin(20, 150)
    cams = [("1\": 13.2 мм, f 8.8, 5472 px", 13.2, 8.8, 5472, "a"),
            ("4/3: 17.3 мм, f 12.3, 5280 px", 17.3, 12.3, 5280, "w"),
            ("1/2.3\": 6.17 мм, f 4.5, 4000 px", 6.17, 4.5, 4000, "ink")]
    D["chart-gsd-altitude"] = chart(
        "GSD от высоты: GSD = H · w_сенсора / (f · W_px)",
        [dict(name="1\" и 4/3: почти одинаково", xs=h, ys=[x * 13.2 / (8.8 * 5472) * 100 for x in h], cls="a", label_at=110, label_dy=24, label_anchor="start"),
         dict(name="", xs=h, ys=[x * 17.3 / (12.3 * 5280) * 100 for x in h], cls="w"),
         dict(name="1/2.3\": 6.17 мм, f 4.5, 4000 px", xs=h, ys=[x * 6.17 / (4.5 * 4000) * 100 for x in h], cls="ink", label_at=100, label_dy=-12, label_anchor="end")],
        Axis("высота над землёй, м", 20, 150), Axis("GSD, см/пиксель", 0, 6),
        hmarks=[(2, "кадастр 2 см", "m"), (5, "сельхоз 5 см", "m")])

    # ------------------------------------------------------------ bf-rpm-filter
    rpm = lin(2000, 12000)
    D["chart-rpm-harmonics"] = chart(
        "viking10: гармоники моторов против нижней границы RPM-фильтра",
        [dict(name="1×", xs=rpm, ys=[r / 60 for r in rpm], cls="a"),
         dict(name="2×", xs=rpm, ys=[2 * r / 60 for r in rpm], cls="a", dash=True),
         dict(name="3×", xs=rpm, ys=[3 * r / 60 for r in rpm], cls="m", dash=True)],
        Axis("обороты мотора, об/мин", 2000, 12000), Axis("частота, Гц", 0, 600),
        hmarks=[(100, "rpm_filter_min_hz = 100 (кейс)", "d"), (50, "= 50 (исправление)", "a")],
        bands=[(2000, 6000, "1× < 100 Гц: notch мимо")])

    # ------------------------------------------------------------ f-mechanics
    phi = lin(0, 75)
    D["chart-tilt-thrust"] = chart(
        "Тяга для удержания высоты в наклоне: T / (m·g) = 1 / cos φ",
        [dict(name="", xs=phi, ys=[1 / math.cos(math.radians(p)) for p in phi], cls="a")],
        Axis("угол наклона φ, °", 0, 75), Axis("нужная тяга, × вес", 1, 4),
        hmarks=[(2, "T/W = 2: предел 60°", "w"), (1.155, "30°: +15.5 %", "m")],
        marks=[(60, "60°", "w")])

    # ------------------------------------------------------------ per-geometry
    zr = lin(0.5, 20)
    err = lambda Z, B: Z * Z * 0.5 / (800 * B)
    D["chart-stereo-error"] = chart(
        "Ошибка глубины стерео: ΔZ = Z² · Δd / (f · B), f = 800 px, Δd = 0.5 px",
        [dict(name="база 5 см", xs=zr, ys=[err(z, 0.05) for z in zr], cls="w", label_at=13, label_dy=-6),
         dict(name="база 12 см", xs=zr, ys=[err(z, 0.12) for z in zr], cls="a", label_at=20, label_dy=-6)],
        Axis("дистанция Z, м", 0, 20), Axis("ошибка ΔZ, м", 0, 3),
        hmarks=[(0.5, "0.5 м", "m")])

    # ------------------------------------------------------------ ap-plane-tuning
    t = lin(0, 2.5)
    def fo(tau, delay=0.08):
        return [0 if x < delay else 30 * (1 - math.exp(-(x - delay) / tau)) for x in t]
    D["chart-plane-tconst"] = chart(
        "Крен на ступеньку 30°: первый порядок с постоянной времени RLL2SRV_TCONST",
        [dict(name="", xs=t, ys=fo(0.3), cls="a"), dict(name="", xs=t, ys=fo(0.5), cls="w"),
         dict(name="", xs=t, ys=fo(0.8), cls="m")],
        Axis("время, с", 0, 2.5), Axis("крен, °", 0, 35),
        hmarks=[(30 * (1 - math.exp(-1)), "63 % за τ", "m")],
        legend=[("τ = 0.3 с: резче, ближе к перерегулированию", "a", False), ("τ = 0.5 с: значение по умолчанию", "w", False),
                ("τ = 0.8 с: мягко, для тяжёлых и медленных", "m", False)], legend_at=(330, 250))

    # ------------------------------------------------------------ ops-weather
    h = lin(0, 4000)
    rho = lambda z: 1.225 * (1 - 2.25577e-5 * z) ** 4.2559
    D["chart-density-altitude"] = chart(
        "Плотностная высота: тяга на полном газу падает ∝ ρ, мощность висения растёт ∝ 1/√ρ",
        [dict(name="", xs=h, ys=[100 * rho(z) / 1.225 for z in h], cls="w"),
         dict(name="", xs=h, ys=[100 * math.sqrt(1.225 / rho(z)) for z in h], cls="a")],
        Axis("плотностная высота, м", 0, 4000), Axis("% от уровня моря (МСА)", 60, 130),
        marks=[(3025, "2000 м, +30 °C", "m")],
        legend=[("максимальная тяга, %", "w", False), ("мощность висения, %", "a", False)], legend_at=(90, 250))

    # wind profile (power law, open terrain) for the same module
    z = lin(2, 150)
    D["chart-wind-profile"] = chart(
        "Ветер растёт с высотой: v(h) = v₁₀·(h/10)^α, открытая местность α ≈ 1/7",
        [dict(name="", xs=[10 * (x / 10) ** (1 / 7) for x in z], ys=z, cls="a"),
         dict(name="", xs=[10 * 1.4 * (x / 10) ** (1 / 7) for x in z], ys=z, cls="w", dash=True)],
        Axis("скорость ветра, м/с (на 10 м — 10 м/с)", 0, 24), Axis("высота, м", 0, 150),
        legend=[("средний ветер", "a", False), ("порывы ×1.4", "w", True)], legend_at=(90, 60))

    # ------------------------------------------------------------ ops-maintenance
    hrs = lin(0, 300)
    lam = 1 / 1000.0
    rq = [math.exp(-4 * lam * x) for x in hrs]
    rh = [(lambda r: r ** 6 + 6 * r ** 5 * (1 - r))(math.exp(-lam * x)) for x in hrs]
    D["chart-reliability"] = chart(
        "Вероятность обойтись без потери из-за моторов: λ мотора = 1/1000 ч (иллюстрация)",
        [dict(name="", xs=hrs, ys=[100 * v for v in rq], cls="w"),
         dict(name="", xs=hrs, ys=[100 * v for v in rh], cls="a")],
        Axis("налёт без замены моторов, ч", 0, 300), Axis("вероятность, %", 0, 100),
        marks=[(100, "100 ч: квадро 67 %, гекса 90 %", "m")],
        legend=[("квадро: нужны все 4 (R⁴)", "w", False), ("гекса, переживает 1 отказ", "a", False)], legend_at=(90, 250))
