"""Video T3: mechanics before PID — reading motor balance from the log (centre of gravity, weak motor, yaw imbalance).

Facts: Betaflight Quad X motor numbering (1 rear right, 2 front right, 3 rear left, 4 front left; log motor[0..3]),
yaw comes from the diagonal pairs 1+4 vs 2+3 (reaction torque). Case numbers (viking10: steady yaw imbalance 6–8 %,
traced to centre of gravity and a weak motor) come from the owner's own tuning logs as recorded in the series plan.
Thresholds marked «ориентир» are course rules of thumb, not firmware values. Silent.
usage: python3 v_mechanics.py [preview|render]"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import *

TB = topbar(8)
MOT = {1: (0.70, 0.70, "1", "задний правый"), 2: (0.70, 0.30, "2", "передний правый"), 3: (0.30, 0.70, "3", "задний левый"), 4: (0.30, 0.30, "4", "передний левый")}


def quad(d, x, y, s, a, vals=None, hi=None):
    """Top view of a Quad X; vals: {motor: % load} shown in the discs."""
    c = (x + s / 2, y + s / 2)
    for m, (fx, fy, lab, _) in MOT.items():
        p = (x + fx * s, y + fy * s)
        d.line([c, p], fill=mix(BG, (90, 96, 108), a), width=10)
    d.rounded_rectangle([c[0] - 40, c[1] - 60, c[0] + 40, c[1] + 60], radius=12, fill=mix(BG, (70, 76, 88), a))
    arrow(d, (c[0], c[1] + 30), (c[0], c[1] - 50), FG, a, 4, 14)
    text(d, (c[0], y - 10), "нос", F(24, "Medium"), MUTED, "md", a)
    for m, (fx, fy, lab, _) in MOT.items():
        p = (x + fx * s, y + fy * s)
        col = RD if hi and m in hi else TE
        r = s * 0.13
        d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=mix(BG, PANEL, a), outline=mix(BG, col, a), width=5)
        text(d, (p[0], p[1] - (14 if vals else 0)), lab, F(34, "Bold"), col, "mm", a)
        if vals:
            text(d, (p[0], p[1] + 24), f"{vals[m]}%", M(24), FG, "mm", a)


def s_hook(t, dur=7):
    def draw(d, t, a):
        quad(d, 290, 700, 500, a, {1: 52, 2: 46, 3: 51, 4: 45}, hi={1, 3})
    return hook(t, dur, "Механика важнее PID", "что лог моторов говорит о раме, весе и моторах",
                "Дрон тянет в сторону, греется один мотор, PID «не держит» рыскание — и человек неделю крутит P и D. А ответ лежит в логе: четыре мотора должны работать почти одинаково. Где не одинаково — там отвёртка, а не Configurator.",
                "нумерация · медианы · центр тяжести · слабый мотор · рыскание · кейс 10\" · порядок", draw)


def s_num(t, dur=12):
    im, d = base(); TB(d, "НУМЕРАЦИЯ", 0)
    ty = title(d, "Сначала — какой мотор где")
    quad(d, 290, ty + 60, 500, ease((t - 0.4) / 0.6))
    rows = [("Betaflight, Quad X", "1 — задний правый · 2 — передний правый · 3 — задний левый · 4 — передний левый", TE),
            ("В логе", "motor[0] … motor[3] = моторы 1 … 4 (счёт с нуля)", OR),
            ("Рыскание", "делается диагоналями: 1 + 4 против 2 + 3, за счёт реактивного момента пропеллеров", GR)]
    cards(d, t, rows, ty + 620, gap=18, t0=1.6, step=1.0, hs=34, bs=29)
    return fade(im, t, dur)


def s_median(t, dur=13):
    im, d = base(); TB(d, "МЕДИАНЫ", 1)
    ty = title(d, "Метод: медиана каждого мотора на ровном участке")
    rows = [("Участок", "висение или ровный пролёт без манёвров, хотя бы 10–20 с", TE),
            ("Число", "медиана motor[i] на этом участке — устойчива к рывкам", OR),
            ("Сравнение", "перед/зад, лево/право, диагональ 1+4 против 2+3", GR),
            ("Ориентир курса", "разница в пару процентов — норма; больше 5 % стабильно — искать причину в железе", PU)]
    y = cards(d, t, rows, ty + 30, gap=18, t0=0.4, step=1.0, hs=34, bs=29)
    code_block(d, 60, y + 20, ["front = (m[1] + m[3]) / 2   # моторы 2, 4", "rear  = (m[0] + m[2]) / 2   # моторы 1, 3",
                               "yaw   = (m[0] + m[3]) - (m[1] + m[2])"], ease((t - 5.0) / 0.5), 25)
    return fade(im, t, dur)


def s_cg(t, dur=13):
    im, d = base(); TB(d, "ЦЕНТР ТЯЖЕСТИ", 2)
    ty = title(d, "Задние работают больше — центр тяжести сзади")
    quad(d, 290, ty + 60, 500, ease((t - 0.4) / 0.6), {1: 54, 2: 46, 3: 54, 4: 46}, hi={1, 3})
    rows = [("Признак", "медианы моторов 1 и 3 стабильно выше 2 и 4; задние горячее на ощупь", RD),
            ("Причина", "батарея или камера смещены, тяжёлый GoPro на одном краю", OR),
            ("Что делать", "двигать батарею и проверять лог снова. PID этот перекос не уберёт — он его только держит током", GR)]
    cards(d, t, rows, ty + 620, gap=18, t0=1.6, step=1.0, hs=34, bs=29)
    return fade(im, t, dur)


def s_weak(t, dur=13):
    im, d = base(); TB(d, "СЛАБЫЙ МОТОР", 3)
    ty = title(d, "Один мотор выше всех — он слабее остальных")
    quad(d, 290, ty + 60, 500, ease((t - 0.4) / 0.6), {1: 49, 2: 49, 3: 49, 4: 56}, hi={4})
    rows = [("Признак", "один мотор стабильно работает больше своего соседа по диагонали", RD),
            ("Что проверить", "пропеллер (сколы, не та модель), подшипник, магниты, винты крепления, перекос луча", OR),
            ("Проверка", "поменять пропеллеры местами: перекос ушёл за пропом — проп, остался — мотор или луч", GR)]
    cards(d, t, rows, ty + 620, gap=18, t0=1.6, step=1.0, hs=34, bs=29)
    return fade(im, t, dur)


def s_yaw(t, dur=13):
    im, d = base(); TB(d, "РЫСКАНИЕ", 4)
    ty = title(d, "Перекос по рысканию: диагональ против диагонали")
    rows = [("Признак", "1 + 4 стабильно больше или меньше 2 + 3: прошивка постоянно «докручивает» yaw", TE),
            ("Почему плохо", "запас по рысканию уходит на удержание, а не на манёвр; I по yaw копится", OR),
            ("Причины", "моторы чуть завалены на лучах, погнутый луч, слабый мотор в одной диагонали, разные пропеллеры", RD),
            ("Метод", "найти и убрать механически, потом заново снять лог", GR)]
    cards(d, t, rows, ty + 30, gap=18, t0=0.4, step=1.0)
    return fade(im, t, dur)


def s_case(t, dur=13):
    im, d = base(); TB(d, "КЕЙС 10\"", 5)
    ty = title(d, "Кейс: 10\", перекос по рысканию 6–8 %")
    steps = [("лог: диагонали расходятся на 6–8 % на ровном полёте", RD), ("PID по yaw не помогал — менялся только ток", OR),
             ("медианы показали два вклада: центр тяжести и один слабый мотор", TE), ("отвёртка и перестановка батареи — затем новый лог", GR)]
    for i, (s, col) in enumerate(steps):
        aa = ease((t - 0.4 - i * 1.0) / 0.5); y = ty + 40 + i * 170
        d.rounded_rectangle([60, y, W - 60, y + 140], radius=18, fill=mix(BG, PANEL, aa))
        d.rounded_rectangle([60, y, 74, y + 140], radius=6, fill=mix(BG, col, aa))
        wrap_text(d, 110, y + 36, s, F(32, "SemiBold"), W - 220, FG, aa)
    chip(d, (60, ty + 740), "Вывод: сначала механика выводит дрон в баланс, потом PID настраивается под чистый аппарат — и сохраняет запас на манёвры", F(30), GR, ease((t - 5.5) / 0.6))
    return fade(im, t, dur)


def s_order(t, dur=12):
    im, d = base(); TB(d, "ПОРЯДОК", 6)
    ty = title(d, "Порядок работ перед тюнингом")
    items = [("пропеллеры: целые, одной модели, правильное направление", TE), ("моторы: свободно крутятся, винты затянуты, лучи ровные", OR),
             ("стек и камера закреплены, батарея по центру", GR), ("лог висения → медианы моторов", PU), ("только потом фильтры и PID", FG)]
    for i, (s, col) in enumerate(items):
        aa = ease((t - 0.4 - i * 0.7) / 0.5); y = ty + 40 + i * 150
        d.rounded_rectangle([60, y, W - 60, y + 120], radius=18, fill=mix(BG, PANEL, aa))
        text(d, (100, y + 60), f"{i + 1}", F(48, "Bold"), col, "lm", aa)
        wrap_text(d, 170, y + 28, s, F(31, "SemiBold"), W - 270, FG, aa)
    return fade(im, t, dur)


def s_end(t, dur=6):
    return end_card(t, dur, [("Четыре мотора должны работать почти одинаково", TE), ("Перед/зад — центр тяжести", OR),
                             ("Один выше всех — слабый мотор или проп", RD), ("Диагонали — рыскание и завал моторов", GR),
                             ("Сначала отвёртка, потом PID", FG)], "тюнинг · блок 1")


SCENES = [("01_hook", s_hook, 7), ("02_num", s_num, 12), ("03_median", s_median, 13), ("04_cg", s_cg, 13),
          ("05_weak", s_weak, 13), ("06_yaw", s_yaw, 13), ("07_case", s_case, 13), ("08_order", s_order, 12), ("09_end", s_end, 6)]

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    if sys.argv[1:] == ["preview"]:
        preview("v_mechanics", f"{here}/out/mech_prev")
    else:
        render_video("v_mechanics", f"{here}/out/mech", f"{here}/out/T3_Mechanics_before_PID.mp4")
