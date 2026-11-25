"""Video T1: Rates and feedforward, choosing them for a flying style.

Facts checked against Betaflight 4.5.3 source (fc/rc.c applyActualRates and the feedforward calculation,
fc/controlrate_profile.c and flight/pid.c defaults, cli/settings.c names, pg/rx.c rc smoothing).
Example rate profiles in scene 3 are illustrations and are labelled as such. Silent.
usage: python3 v_rates_ff.py [preview|render]"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import *

TB = topbar(8)


def actual(x, center, mx, expo):
    """Betaflight Actual rates: deg/s for stick x in [-1, 1] (fc/rc.c applyActualRates)."""
    ax = abs(x)
    e = ax * (x ** 5 * expo + x * (1 - expo))
    return x * center + max(0.0, mx - center) * e


PROFILES = [("по умолчанию 70 / 670 / 0", 70, 670, 0.0, MUTED),
            ("пример: плавный 50 / 450 / 0.5", 50, 450, 0.5, TE),
            ("пример: резкий 200 / 850 / 0.2", 200, 850, 0.2, OR)]


def curves(d, t, x0, y0, w, h, ymax, a_base, label_x=False, delay=0.0, step=0.8):
    d.line([(x0, y0 + h), (x0 + w, y0 + h)], fill=mix(BG, (60, 66, 78), a_base), width=2)
    d.line([(x0, y0), (x0, y0 + h)], fill=mix(BG, (60, 66, 78), a_base), width=2)
    for v in range(0, ymax + 1, 200):
        yy = y0 + h - v / ymax * h
        d.line([(x0, yy), (x0 + w, yy)], fill=mix(BG, (30, 34, 42), a_base))
        text(d, (x0 - 12, yy), str(v), F(20, "Medium"), MUTED, "rm", a_base)
    for i, (lab, c, m, e, col) in enumerate(PROFILES):
        a = ease((t - delay - i * step) / 0.6)
        n = int(80 * a)
        pts = [(x0 + k / 80 * w, y0 + h - actual(k / 80, c, m, e) / ymax * h) for k in range(n + 1)]
        polyline(d, pts, col, a_base, 5)
    if label_x:
        text(d, (x0 + w, y0 + h + 34), "отклонение стика →  100 %", F(22, "Medium"), MUTED, "ra", a_base)
        text(d, (x0, y0 - 34), "скорость вращения, °/с", F(22, "Medium"), MUTED, "la", a_base)


def s_hook(t, dur=7):
    def draw(d, t, a):
        curves(d, t, 140, 640, 800, 520, 900, a, delay=1.0, step=0.5)
    return hook(t, dur, "Rates и feedforward", "почему двум пилотам нужен разный дрон",
                "Один и тот же квадрик один пилот называет «вялым», другой «нервным». Дело не в PID: стик превращается в скорость вращения по кривой рейтов, а feedforward решает, как быстро дрон отзовётся на движение стика.",
                "кривая Actual · три числа · под стиль · FF изнутри · связь · проверка по логу", draw)


def s_what(t, dur=13):
    im, d = base(); TB(d, "ЧТО ТАКОЕ РЕЙТ", 0)
    ty = title(d, "Стик задаёт не наклон, а скорость")
    a = ease((t - 0.4) / 0.5)
    boxes = [("стик", "−100…+100 %", MUTED), ("кривая рейтов", "rates_type = ACTUAL", OR), ("setpoint", "°/с по оси", TE), ("PID + FF", "догоняет setpoint", GR)]
    for i, (h, s, col) in enumerate(boxes):
        aa = ease((t - 0.4 - i * 0.5) / 0.5); y = ty + 30 + i * 140
        d.rounded_rectangle([140, y, W - 140, y + 110], radius=18, fill=mix(BG, PANEL, aa), outline=mix(BG, col, aa), width=3)
        text(d, (180, y + 55), h, F(36, "Bold"), col, "lm", aa)
        text(d, (W - 180, y + 55), s, M(26), FG, "rm", aa)
        if i < 3:
            arrow(d, (W / 2, y + 112), (W / 2, y + 146), MUTED, aa, 4, 12)
    text(d, (60, 980), "Actual rates — три числа на ось", F(34, "Bold"), FG, "la", ease((t - 3.0) / 0.5))
    rows = [("Center sensitivity", "наклон кривой у центра стика, °/с на весь ход", OR),
            ("Max rate", "скорость вращения при полном стике, °/с", TE),
            ("Expo", "0…1: насколько долго кривая остаётся пологой", GR)]
    y = cards(d, t, rows, 1040, gap=18, t0=3.4, step=0.7, hs=34, bs=29)
    code_block(d, 60, y + 14, ["set rates_type = ACTUAL", "set roll_rc_rate = 7    # центр = 7 × 10 = 70 °/с",
                               "set roll_srate = 67     # макс = 67 × 10 = 670 °/с", "set roll_expo = 0"], ease((t - 6.5) / 0.5), 25)
    return fade(im, t, dur)


def s_curve(t, dur=14):
    im, d = base(); TB(d, "КРИВАЯ", 1)
    title(d, "Одна и та же рука — три разных дрона")
    a = ease((t - 0.3) / 0.5)
    curves(d, t, 140, 420, 840, 700, 900, a, label_x=True, delay=0.6, step=1.2)
    for i, (lab, c, m, e, col) in enumerate(PROFILES):
        aa = ease((t - 0.9 - i * 1.2) / 0.5)
        y = 1220 + i * 58
        d.rounded_rectangle([60, y + 8, 100, y + 18], radius=4, fill=mix(BG, col, aa))
        text(d, (120, y), lab, F(28, "SemiBold"), FG, "la", aa)
    v50 = [actual(0.5, c, m, e) for _, c, m, e, _ in PROFILES]
    s = f"На половине стика: {v50[0]:.0f} · {v50[1]:.0f} · {v50[2]:.0f} °/с — разница почти втрое"
    chip(d, (60, 1430), s, F(32), OR, ease((t - 5.0) / 0.6))
    wrap_text(d, 60, 1560, "Формула из прошивки: setpoint = центр · x + (макс − центр) · |x| · (expo · x⁵ + (1 − expo) · x).", F(25, "Medium"), W - 120, MUTED, ease((t - 7.0) / 0.6))
    return fade(im, t, dur)


def s_style(t, dur=14):
    im, d = base(); TB(d, "ПОД СТИЛЬ", 2)
    ty = title(d, "Как выбирать: от задачи, а не от чужого пресета")
    rows = [("Фристайл", "резкий отклик и флипы: высокий max rate, умеренный центр, небольшое expo", OR),
            ("Синематик и дальние полёты", "плавные пролёты: низкий центр и max rate, больше expo, мягкий FF", TE),
            ("Гонки", "точность у центра и быстрые перекладки: высокий FF, без лишнего сглаживания", RD),
            ("Свои дроны", "viking и viking2 летают на стандартных рейтах; у viking10 чуть выше max по крену — тяжёлому 10\" нужно больше «запаса» на манёвр", GR)]
    y = cards(d, t, rows, ty + 30, gap=20, t0=0.5, step=1.1)
    chip(d, (60, y + 20), "Это ориентиры, а не значения из прошивки. Проверка одна: полетать и посмотреть в логе, догоняет ли gyro setpoint", F(30), MUTED, ease((t - 6.0) / 0.6))
    return fade(im, t, dur)


def s_ff(t, dur=14):
    im, d = base(); TB(d, "FEEDFORWARD", 3)
    title(d, "PID ждёт ошибку. Feedforward — нет")
    a = ease((t - 0.4) / 0.5)
    x0, y0, w, h = 120, 420, 840, 420
    d.line([(x0, y0 + h), (x0 + w, y0 + h)], fill=mix(BG, (60, 66, 78), a), width=2)
    sp = [(x0 + k / 100 * w, y0 + h - h * 0.8 * (0 if k < 20 else (1 if k > 45 else ease((k - 20) / 25)))) for k in range(101)]
    polyline(d, sp, TE, ease((t - 0.8) / 0.6), 5)
    ff = []
    for k in range(101):
        v = 0.0
        if 20 <= k <= 45:
            v = math.sin(math.pi * (k - 20) / 25)
        ff.append((x0 + k / 100 * w, y0 + h - h * 0.55 * v))
    polyline(d, ff, OR, ease((t - 2.0) / 0.6), 5)
    gyro_np = [(x0 + k / 100 * w, y0 + h - h * 0.8 * (0 if k < 28 else (1 if k > 60 else ease((k - 28) / 32)))) for k in range(101)]
    polyline(d, gyro_np, MUTED, ease((t - 3.2) / 0.6), 3)
    text(d, (x0 + w, y0 + 40), "setpoint", F(26), TE, "ra", ease((t - 0.8) / 0.6))
    text(d, (x0 + w * 0.5, y0 + h - h * 0.22), "← FF ∝ скорость стика", F(28), OR, "la", ease((t - 2.0) / 0.6))
    text(d, (x0 + w, y0 + h * 0.55), "отклик без FF — позже", F(24, "Medium"), MUTED, "ra", ease((t - 3.2) / 0.6))
    rows = [("P, I, D", "реагируют на ошибку: сначала setpoint ушёл, потом gyro отстал, потом PID толкает", MUTED),
            ("F-член", "считается из того, как быстро двигается стик: дрон начинает вращение одновременно с рукой", OR),
            ("Умолчания 4.5", "f_roll 120 · f_pitch 125 · f_yaw 120", TE)]
    cards(d, t, rows, 960, gap=22, t0=4.4, step=1.0, hs=34, bs=29)
    return fade(im, t, dur)


def s_knobs(t, dur=17):
    im, d = base(); TB(d, "РУЧКИ FF", 4)
    ty = title(d, "Шесть ручек feedforward в 4.5")
    rows = [("feedforward_smooth_factor = 25", "сглаживает скорость стика и её ускорение: выше — мягче, но позже", TE),
            ("feedforward_jitter_factor = 7", "гасит FF, когда стик за пакет сдвинулся меньше чем на 7 единиц (из ±500): тише при мелких движениях", GR),
            ("feedforward_boost = 15", "добавляет член ускорения стика: резче старт вращения, больше риск перелёта", OR),
            ("feedforward_max_rate_limit = 90", "срезает FF у предела рейта, чтобы дрон не проскакивал на полном стике", RD),
            ("feedforward_transition = 0", "ослабляет FF у центра стика: 0 — выключено", PU),
            ("feedforward_averaging = OFF", "усреднение 2–4 пакетов связи: для медленных каналов", MUTED)]
    cards(d, t, rows, ty + 30, gap=18, t0=0.4, step=0.9, hs=30, bs=27)
    chip(d, (60, 1640), "Ещё одна ручка рядом: rc_smoothing_auto_factor = 30 — фильтр setpoint и FF подстраивается под частоту пакетов", F(29), MUTED, ease((t - 7.5) / 0.6))
    return fade(im, t, dur)


def s_link(t, dur=12):
    im, d = base(); TB(d, "СВЯЗЬ РЕШАЕТ", 5)
    ty = title(d, "FF настолько хорош, насколько ровна связь")
    rows = [("Откуда берётся «скорость стика»", "разница между двумя пакетами связи. Пропущенный или повторный пакет даёт ступеньку, и FF дёргается", OR),
            ("Что делает прошивка", "повторный пакет она узнаёт: один пакет держит прошлую скорость, дальше обнуляет FF. Это смягчает, но не убирает ступеньки", TE),
            ("Медленный канал", "редкие пакеты → крупные ступеньки: больше smooth, averaging 2–3 точки, меньше boost", RD),
            ("Быстрый ровный канал", "можно меньше сглаживания и больше boost: отклик острее", GR)]
    cards(d, t, rows, ty + 30, gap=18, t0=0.5, step=1.1)
    chip(d, (60, 1600), "Сначала сделай связь ровной (packet rate, антенны, LQ), потом крути FF", F(32), OR, ease((t - 6.0) / 0.6))
    return fade(im, t, dur)


def s_check(t, dur=13):
    im, d = base(); TB(d, "ПРОВЕРКА", 6)
    ty = title(d, "Как понять по логу, что FF настроен")
    cy = code_block(d, 60, ty + 30, ["set debug_mode = FEEDFORWARD", "# в логе: setpoint, FF до и после ограничений"], ease((t - 0.4) / 0.5), 24)
    rows = [("gyro проскакивает setpoint на остановке стика", "много boost или FF: убавь boost, проверь max_rate_limit", RD),
            ("gyro отстаёт на быстрых перекладках", "мало FF или много smooth: прибавь f_* по 10 %", OR),
            ("моторы «шуршат», дрожь у центра стика", "шум связи в FF: jitter_factor выше или transition 20–40", TE),
            ("всё ровно, но «как через вату»", "много сглаживания: rc_smoothing_auto_factor и smooth_factor ниже", PU)]
    cards(d, t, rows, cy + 30, gap=22, t0=1.4, step=1.1, hs=32, bs=28)
    chip(d, (60, 1620), "Правило серии: одна ручка за полёт, два полёта на изменение, сравнение по логу", F(31), GR, ease((t - 7.0) / 0.6))
    return fade(im, t, dur)


def s_end(t, dur=6):
    return end_card(t, dur, [("Рейт = стик → °/с по кривой Actual", OR), ("Центр, max, expo — под задачу, не под пресет", TE),
                             ("FF работает до ошибки, из скорости стика", GR), ("Сначала ровная связь, потом FF", RD),
                             ("Одна ручка за полёт и проверка по логу", FG)], "тюнинг · блок 1")


SCENES = [("01_hook", s_hook, 7), ("02_what", s_what, 13), ("03_curve", s_curve, 14), ("04_style", s_style, 14),
          ("05_ff", s_ff, 14), ("06_knobs", s_knobs, 17), ("07_link", s_link, 12), ("08_check", s_check, 13), ("09_end", s_end, 6)]

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    if sys.argv[1:] == ["preview"]:
        preview("v_rates_ff", f"{here}/out/rates_ff_prev")
    else:
        render_video("v_rates_ff", f"{here}/out/rates_ff", f"{here}/out/T1_Rates_and_feedforward.mp4")
