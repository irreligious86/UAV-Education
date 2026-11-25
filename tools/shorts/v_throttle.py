"""Video T2: throttle behaviour — dynamic idle, thrust linearization, battery sag compensation, TPA, anti-gravity.

Facts checked against Betaflight 4.5.3: flight/pid.c defaults (dyn_idle_* 0/50/50/50/150, thrust_linear 0,
vbat_sag_compensation 0, tpa_mode D, tpa_rate 65, tpa_breakpoint 1350, tpa_low_rate 20, tpa_low_breakpoint 1050,
tpa_low_always 0, anti_gravity_gain 80, throttle_boost 5), cli/settings.c ranges (dyn_idle_min_rpm 0..200,
thrust_linear 0..150, vbat_sag 0..150), flight/mixer_init.c (dyn idle only with DShot telemetry and then motor low =
DSHOT_MIN_THROTTLE; sag compensation between 4.20 V/cell and the warning cell voltage), flight/pid.c pidUpdateTpaFactor
and the thrust linearization formula, build/debug.c DYN_IDLE. Silent.
usage: python3 v_throttle.py [preview|render]"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import *

TB = topbar(8)


def tpa_factor(thr, low_phase=True, rate=0.65, bp=0.35, low_rate=0.20, low_bp=0.05):
    """1 - tpaRate for throttle 0..1 (pidUpdateTpaFactor). low_phase=True: before the first pass of tpa_low_breakpoint."""
    if low_phase and thr < low_bp:
        return 1 - (low_rate / low_bp) * (low_bp - thr)
    return 1 - (rate / (1 - bp)) * max(thr - bp, 0.0)


def axes(d, x0, y0, w, h, a, xl, yl, yticks):
    d.line([(x0, y0 + h), (x0 + w, y0 + h)], fill=mix(BG, (60, 66, 78), a), width=2)
    d.line([(x0, y0), (x0, y0 + h)], fill=mix(BG, (60, 66, 78), a), width=2)
    for v, lab in yticks:
        yy = y0 + h - v * h
        d.line([(x0, yy), (x0 + w, yy)], fill=mix(BG, (30, 34, 42), a))
        text(d, (x0 - 12, yy), lab, F(22, "Medium"), MUTED, "rm", a)
    text(d, (x0 + w, y0 + h + 30), xl, F(24, "Medium"), MUTED, "ra", a)
    text(d, (x0, y0 - 40), yl, F(24, "Medium"), MUTED, "la", a)


def s_hook(t, dur=7):
    def draw(d, t, a):
        x0, y0, w, h = 140, 680, 800, 480
        axes(d, x0, y0, w, h, a, "газ →", "D-член, % от заданного", [(1, "100"), (0.5, "50"), (0, "0")])
        pts = [(x0 + k / 100 * w, y0 + h - tpa_factor(k / 100, False) * h) for k in range(int(101 * ease((t - 1.0) / 1.2)))]
        polyline(d, pts, OR, a, 5)
    return hook(t, dur, "Газ: почему дрон «проваливается»", "dynamic idle, thrust linear, просадка батареи и TPA",
                "Сбросил газ — дрон просел и затрясся. Дал полный — начал звенеть. Это не PID «плохой»: на разных уровнях газа у пропеллера разная сила, а у батареи — разное напряжение. В Betaflight на это есть пять ручек.",
                "провал · dynamic idle · кривая тяги · просадка · TPA · anti-gravity · проверка", draw)


def s_drop(t, dur=12):
    im, d = base(); TB(d, "ПРОВАЛ", 0)
    ty = title(d, "Что происходит на сбросе газа")
    rows = [("Пропеллер почти стоит", "тяга растёт примерно как квадрат оборотов: на малых оборотах любая коррекция PID почти ничего не даёт", RD),
            ("Свой же поток", "дрон падает в воздух, который сам отбросил вниз, — это propwash: тряска и раскачка", OR),
            ("Что держит обороты", "без dynamic idle — фиксированный минимум dshot_idle_value; с ним — регулятор по реальным оборотам", TE)]
    y = cards(d, t, rows, ty + 30, gap=22, t0=0.4, step=1.2)
    chip(d, (60, y + 20), "Чем выше минимальные обороты, тем больше управляемости на сбросе, но тем хуже дрон «садится» и быстрее падает", F(29), MUTED, ease((t - 5.0) / 0.6))
    return fade(im, t, dur)


def s_dynidle(t, dur=14):
    im, d = base(); TB(d, "DYNAMIC IDLE", 1)
    ty = title(d, "Dynamic idle: держит обороты, а не газ")
    y = code_block(d, 60, ty + 30, ["set dyn_idle_min_rpm = 0    # × 100 об/мин, 0–200; 0 = выключено",
                                    "set dyn_idle_p_gain = 50    # i 50, d 50 — как быстро держит",
                                    "set dyn_idle_max_increase = 150"], ease((t - 0.4) / 0.5), 22)
    rows = [("Нужен двунаправленный DShot", "без телеметрии оборотов от ESC прошивка dynamic idle просто не включает", RD),
            ("dshot_idle_value перестаёт работать", "с включённым dynamic idle нижняя граница мотора сбрасывается в минимум DShot: обороты держит регулятор", OR),
            ("Как подбирать", "минимум, при котором на сбросе газа нет провала и тряски. Проверка: debug_mode = DYN_IDLE и обороты в логе", GR)]
    cards(d, t, rows, y + 30, gap=20, t0=1.6, step=1.2, hs=34, bs=29)
    return fade(im, t, dur)


def s_linear(t, dur=14):
    im, d = base(); TB(d, "КРИВАЯ ТЯГИ", 2)
    ty = title(d, "thrust_linear: выпрямляет тягу внизу")
    x0, y0, w, h = 140, ty + 80, 820, 560
    a = ease((t - 0.3) / 0.5)
    axes(d, x0, y0, w, h, a, "команда мотору, %", "выход на ESC, %", [(1, "100"), (0.5, "50"), (0, "0")])
    for i, (k, col, lab) in enumerate([(0.0, MUTED, "0 (умолчание)"), (0.4, TE, "40"), (0.8, OR, "80")]):
        aa = ease((t - 0.8 - i * 0.9) / 0.6)
        pts = [(x0 + u * w, y0 + h - min(1.0, u * (1 + k * (1 - u) ** 2)) * h) for u in [j / 80 for j in range(81)]]
        polyline(d, pts, col, aa, 5)
        text(d, (x0 + 30, y0 + 20 + i * 44), f"thrust_linear = {lab}", F(28), col, "la", aa)
    wrap_text(d, 60, y0 + h + 70, "Формула из прошивки: выход × (1 + k · (1 − выход)²). Внизу мотор получает больше, вверху — почти столько же, сколько просили.", F(29, "Medium"), W - 120, FG, ease((t - 4.0) / 0.6))
    chip(d, (60, y0 + h + 230), "Зачем: на малом газе отклик становится ближе к линейному, PID работает одинаково на всём ходе. Диапазон 0–150 %", F(28), GR, ease((t - 6.0) / 0.6))
    return fade(im, t, dur)


def s_sag(t, dur=13):
    im, d = base(); TB(d, "ПРОСАДКА", 3)
    ty = title(d, "vbat_sag_compensation: батарея садится, а газ тот же")
    rows = [("Проблема", "в начале полёта 4.2 В на ячейку, в конце — у порога предупреждения. Тот же стик даёт заметно меньше тяги", RD),
            ("Что делает", "поднимает выход моторов по мере падения напряжения: от 4.20 В на ячейку до vbat_warning_cell_voltage", TE),
            ("Ручка", "0–150 %, по умолчанию 0. Нужен датчик напряжения батареи", OR),
            ("Особенно для Li-Ion", "у Li-Ion просадка под нагрузкой больше, чем у LiPo: без компенсации дрон «тяжелеет» к концу полёта", GR)]
    cards(d, t, rows, ty + 30, gap=18, t0=0.4, step=1.0, hs=34, bs=29)
    return fade(im, t, dur)


def s_tpa(t, dur=16):
    im, d = base(); TB(d, "TPA", 4)
    ty = title(d, "TPA: меньше D на полном газе")
    x0, y0, w, h = 150, ty + 80, 810, 520
    a = ease((t - 0.3) / 0.5)
    axes(d, x0, y0, w, h, a, "газ 1000 → 2000", "D, % от заданного", [(1, "100"), (0.65, "65"), (0.35, "35"), (0, "0")])
    pts = [(x0 + k / 200 * w, y0 + h - tpa_factor(k / 200, False) * h) for k in range(201)]
    polyline(d, pts, OR, ease((t - 0.8) / 0.6), 5)
    pl = [(x0 + k / 200 * w, y0 + h - tpa_factor(k / 200, True) * h) for k in range(0, 11)]
    polyline(d, pl, TE, ease((t - 2.4) / 0.6), 5)
    bx = x0 + 0.35 * w
    d.line([(bx, y0), (bx, y0 + h)], fill=mix(BG, MUTED, ease((t - 1.4) / 0.5)), width=2)
    text(d, (bx + 10, y0 + 10), "tpa_breakpoint 1350", F(24), MUTED, "la", ease((t - 1.4) / 0.5))
    text(d, (x0 + w - 10, y0 + h - 0.35 * h - 40), "−65 % на 2000", F(26), OR, "ra", ease((t - 1.8) / 0.5))
    text(d, (x0 + 20, y0 + h - 0.62 * h), "← tpa_low: −20 % у нуля, до первого взлёта", F(24), TE, "la", ease((t - 2.4) / 0.5))
    rows = [("Зачем", "на полном газе моторы быстрее, D усиливает шум и греет моторы — TPA его убирает", OR),
            ("Режим", "tpa_mode = D (умолчание) — только D; PD — ещё и P", TE),
            ("tpa_low", "на земле перед взлётом D ниже, чтобы не трясло; после первого прохода 1050 выключается, если tpa_low_always = 0", GR)]
    cards(d, t, rows, y0 + h + 60, gap=16, t0=3.6, step=1.0, hs=32, bs=28)
    return fade(im, t, dur)


def s_ag(t, dur=12):
    im, d = base(); TB(d, "РЕЗКИЙ ГАЗ", 5)
    ty = title(d, "Anti-gravity и throttle boost")
    rows = [("Проблема", "резко дал газ — нос клюнул: момент от моторов меняется быстрее, чем I успевает подстроиться", RD),
            ("anti_gravity_gain = 80", "на быстрых движениях газа временно усиливает I (и немного P): угол держится", TE),
            ("throttle_boost = 5", "добавляет «рывок» к быстрому движению газа: моторы откликаются резче", OR)]
    y = cards(d, t, rows, ty + 30, gap=22, t0=0.4, step=1.2)
    chip(d, (60, y + 20), "Клюёт на «панч» газом — сначала anti-gravity, потом смотри I. Не путать с провалом на сбросе", F(29), GR, ease((t - 5.0) / 0.6))
    return fade(im, t, dur)


def s_check(t, dur=12):
    im, d = base(); TB(d, "ПРОВЕРКА", 6)
    ty = title(d, "Тест-полёт на одну ручку")
    items = [("резкий сброс газа с высоты и подхват — смотри обороты и тряску", TE), ("пролёт на полном газе — шум D и температура моторов", OR),
             ("начало и конец батареи — один и тот же манёвр", GR), ("в логе: motor, rpm, debug DYN_IDLE", PU), ("одна ручка за полёт, сравнение двух логов", FG)]
    for i, (s, col) in enumerate(items):
        aa = ease((t - 0.4 - i * 0.7) / 0.5); y = ty + 40 + i * 150
        d.rounded_rectangle([60, y, W - 60, y + 120], radius=18, fill=mix(BG, PANEL, aa))
        text(d, (100, y + 60), f"{i + 1}", F(48, "Bold"), col, "lm", aa)
        wrap_text(d, 170, y + 28, s, F(31, "SemiBold"), W - 270, FG, aa)
    return fade(im, t, dur)


def s_end(t, dur=6):
    return end_card(t, dur, [("Провал на сбросе — dynamic idle (нужен bidir DShot)", TE), ("Слабый низ — thrust_linear", OR),
                             ("Тяжелеет к концу — vbat_sag_compensation", GR), ("Звенит на полном — TPA", RD),
                             ("Клюёт на панч — anti-gravity", PU)], "тюнинг · блок 1")


SCENES = [("01_hook", s_hook, 7), ("02_drop", s_drop, 12), ("03_dynidle", s_dynidle, 14), ("04_linear", s_linear, 14),
          ("05_sag", s_sag, 13), ("06_tpa", s_tpa, 16), ("07_ag", s_ag, 12), ("08_check", s_check, 12), ("09_end", s_end, 6)]

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    if sys.argv[1:] == ["preview"]:
        preview("v_throttle", f"{here}/out/thr_prev")
    else:
        render_video("v_throttle", f"{here}/out/thr", f"{here}/out/T2_Throttle_dynamic_idle_TPA.mp4")
