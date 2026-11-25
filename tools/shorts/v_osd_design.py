"""Video P2: OSD as a design object — fonts, layout, three OSD profiles on a switch, warnings and stats.

Facts checked against Betaflight 4.5.3: osd/osd.h position encoding (x bits 0-4, y bits 5-9, extra X bit 10 for HD,
profile flags bits 11-13), cli/settings.c (osd_profile 1..3, osd_profile_N_name, osd_warn_bitmask, osd_stat_bitmask,
craft_name, pilot_name, osd_profile_name_pos), fc/rc_adjustments.h/.c (ADJUSTMENT_OSD_PROFILE enum 33 = CLI function 29 (array index 28 + 1), select mode with
3 positions over 900..2100), cli/cli.c adjrange format; Configurator 10.10 font presets (resources/osd/2: default, bold,
large, extra_large, betaflight, digital, clarity, vision, impact, impact_mini) and «Open Font File» (.mcm). Silent.
usage: python3 v_osd_design.py [preview|render]"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import *

TB = topbar(8)


def pos(x, y, profiles):
    v = (x & 31) | ((y & 31) << 5) | ((x >> 5) & 1) << 10
    for p in profiles:
        v |= 1 << (10 + p)
    return v


assert pos(1, 12, (1, 2)) == 6529


def goggles(im, d, x, y, w, h, a, elems):
    """Analog goggles mock (30 x 16 grid). elems: list of (col, row, text, colour)."""
    d.rounded_rectangle([x, y, x + w, y + h], radius=14, fill=mix(BG, (60, 64, 68), a))
    for k in range(0, h, 7):
        d.line([(x + 6, y + k), (x + w - 6, y + k)], fill=mix(BG, (68 + (k * 13) % 7, 72, 76), a))
    cw, ch = w / 30, h / 16
    for c, r, s, col in elems:
        text(d, (x + c * cw, y + r * ch + 2), s, M(int(ch * 0.78)), col, "la", a)


FULL = [(1, 1, "4.02V", (255, 255, 255)), (22, 1, "LQ 100 -63dBm", (255, 255, 255)), (1, 14, "02:41", (255, 255, 255)),
        (12, 7, "-+-", (255, 255, 255)), (22, 14, "1240mAh", (255, 255, 255)), (1, 3, "18.6A", (255, 255, 255)),
        (11, 1, "SHARP", (255, 255, 255)), (12, 14, "H 85m", (255, 255, 255)), (1, 12, "48km/h", (255, 255, 255))]
MIN = [(1, 1, "4.02V", (255, 255, 255)), (22, 1, "LQ 100", (255, 255, 255)), (1, 14, "02:41", (255, 255, 255))]
CLEAN = []


def s_hook(t, dur=7):
    im, d = base()
    a = ease(t / 0.6)
    text(d, (60, 230), "BETAFLIGHT ИЗНУТРИ · ТЮНИНГ И ПЕРСОНАЛИЗАЦИЯ", F(24, "Bold"), MUTED, "la", a)
    y = wrap_text(d, 60, 290, "OSD как дизайн", F(84, "Bold"), W - 120, FG, a, lh=96)
    wrap_text(d, 60, y + 10, "шрифт, раскладка и три экрана на одном тумблере", F(46, "Bold"), W - 120, OR, ease((t - 0.4) / 0.6), lh=58)
    k = int(t / 1.6) % 3
    goggles(im, d, 90, 640, 900, 520, ease((t - 0.8) / 0.6), [FULL, MIN, CLEAN][k])
    text(d, (W / 2, 1190), ["профиль 1 — полный", "профиль 2 — минимум", "профиль 3 — чистая картинка"][k], F(34, "Bold"), [OR, TE, GR][k], "ma", ease((t - 0.8) / 0.6))
    wrap_text(d, 60, 1290, "OSD — это не «включить всё, что есть». Это интерфейс, который ты читаешь краем глаза на 100 км/ч. В Betaflight у него три профиля, свой шрифт и правила раскладки.", F(32, "Medium"), W - 120, FG, ease((t - 1.8) / 0.7), lh=44)
    text(d, (60, 1700), "шрифты · раскладка · профили · кодирование позиций · тумблер · предупреждения", F(24, "Medium"), MUTED, "la", ease((t - 2.6) / 0.6))
    return fade(im, t, dur)


def s_fonts(t, dur=12):
    im, d = base(); TB(d, "ШРИФТ", 0)
    ty = title(d, "Шрифт: десять готовых и свой")
    a = ease((t - 0.4) / 0.5)
    names = ["default", "bold", "large", "extra_large", "betaflight", "digital", "clarity", "vision", "impact", "impact_mini"]
    for i, n in enumerate(names):
        aa = ease((t - 0.4 - i * 0.12) / 0.4)
        x = 60 + (i % 2) * 490; y = ty + 30 + (i // 2) * 92
        d.rounded_rectangle([x, y, x + 470, y + 76], radius=14, fill=mix(BG, PANEL, aa))
        text(d, (x + 24, y + 38), n, M(30), FG, "lm", aa)
    rows = [("Где", "Configurator → OSD → Font Manager: список шрифтов и кнопка Open Font File (.mcm)", OR),
            ("Как выбирать", "читаемость в очках важнее красоты: жирный шрифт держится на шумной картинке", TE),
            ("Помни", "шрифт и заставка заливаются вместе — смена шрифта стирает свою заставку", RD)]
    cards(d, t, rows, ty + 520, gap=18, t0=2.0, step=1.0, hs=34, bs=29)
    return fade(im, t, dur)


def s_layout(t, dur=14):
    im, d = base(); TB(d, "РАСКЛАДКА", 1)
    ty = title(d, "Раскладка: центр свободен, углы работают")
    goggles(im, d, 90, ty + 30, 900, 520, ease((t - 0.4) / 0.6), FULL)
    rows = [("Центр", "только прицел/горизонт. Здесь ты смотришь на дорогу", GR),
            ("Углы", "батарея и связь — туда, куда взгляд уходит быстро и сам", OR),
            ("Низ", "таймер, ёмкость, высота: читаешь реже", TE),
            ("Правило", "вольты на ячейку, LQ и dBm, таймер — минимум для любого полёта", PU)]
    cards(d, t, rows, ty + 590, gap=16, t0=1.6, step=0.9, hs=34, bs=29)
    return fade(im, t, dur)


def s_profiles(t, dur=14):
    im, d = base(); TB(d, "ТРИ ПРОФИЛЯ", 2)
    ty = title(d, "Три профиля: один набор элементов, три экрана")
    for i, (els, lab, col) in enumerate([(FULL, "1 · полный", OR), (MIN, "2 · минимум", TE), (CLEAN, "3 · чисто", GR)]):
        aa = ease((t - 0.4 - i * 0.6) / 0.5)
        x = 60 + i * 330
        goggles(im, d, x, ty + 40, 300, 180, aa, els)
        text(d, (x + 150, ty + 236), lab, F(28, "Bold"), col, "ma", aa)
    rows = [("Как это устроено", "у каждого элемента одна позиция на экране и три флажка: показывать в профиле 1, 2, 3", TE),
            ("Имена профилей", "osd_profile_1_name … _3_name и элемент osd_profile_name_pos — видно, какой экран включён", OR),
            ("Какой активен", "osd_profile = 1…3, либо с тумблера (дальше)", GR)]
    cards(d, t, rows, ty + 320, gap=20, t0=2.2, step=1.1)
    return fade(im, t, dur)


def s_bits(t, dur=15):
    im, d = base(); TB(d, "ПОЗИЦИЯ В БИТАХ", 3)
    ty = title(d, "Как кодируется osd_*_pos")
    a = ease((t - 0.4) / 0.5)
    cells = [("13", OR), ("12", OR), ("11", OR), ("10", MUTED), ("9", TE), ("8", TE), ("7", TE), ("6", TE), ("5", TE), ("4", GR), ("3", GR), ("2", GR), ("1", GR), ("0", GR)]
    bw = (W - 120) / 14
    val = pos(1, 12, (1, 2))
    for i, (b, col) in enumerate(cells):
        aa = ease((t - 0.6 - i * 0.06) / 0.4)
        x = 60 + i * bw; y = ty + 60
        bit = (val >> int(b)) & 1
        d.rounded_rectangle([x + 3, y, x + bw - 3, y + 100], radius=10, fill=mix(BG, col, aa * (0.9 if bit else 0.25)))
        text(d, (x + bw / 2, y + 50), str(bit), M(40), BG if bit else FG, "mm", aa)
        text(d, (x + bw / 2, y + 128), b, F(20, "Medium"), MUTED, "mm", aa)
    labs = [("профили 3 · 2 · 1", OR, 60 + 1.5 * bw), ("X для HD", MUTED, 60 + 3.5 * bw), ("Y — строка", TE, 60 + 7 * bw), ("X — столбец", GR, 60 + 11.5 * bw)]
    for s, col, x in labs:
        text(d, (x, ty + 190), s, F(24, "Bold"), col, "ma", ease((t - 1.8) / 0.5))
    y = code_block(d, 60, ty + 260, ["# столбец 1, строка 12, видно в профилях 1 и 2",
                                     "1 + 12×32 + 2048 + 4096 = 6529",
                                     "set osd_vbat_pos = 6529"], ease((t - 3.0) / 0.5), 26)
    chip(d, (60, y + 30), "Число в diff all — это не «магия Configurator»: его можно собрать руками и проверить. Флаг профиля = 2048 · 4096 · 8192", F(29), OR, ease((t - 5.5) / 0.6))
    return fade(im, t, dur)


def s_switch(t, dur=14):
    im, d = base(); TB(d, "ТУМБЛЕР", 4)
    ty = title(d, "Профиль с трёхпозиционного тумблера")
    y = code_block(d, 60, ty + 30, ["# AUX2 = индекс 1; функция 29 = OSD profile",
                                    "adjrange 0 0 1 900 2100 29 1 0 0"], ease((t - 0.4) / 0.5), 27)
    a = ease((t - 1.4) / 0.5)
    x0, w = 90, 900
    for i, (lo, hi, lab, col) in enumerate([(900, 1300, "профиль 1", OR), (1300, 1700, "профиль 2", TE), (1700, 2100, "профиль 3", GR)]):
        aa = ease((t - 1.6 - i * 0.4) / 0.4)
        xa = x0 + (lo - 900) / 1200 * w; xb = x0 + (hi - 900) / 1200 * w
        d.rounded_rectangle([xa + 4, y + 50, xb - 4, y + 150], radius=14, fill=mix(BG, col, aa * 0.85))
        text(d, ((xa + xb) / 2, y + 100), lab, F(30, "Bold"), BG, "mm", aa)
        text(d, (xa + 4, y + 170), str(lo), F(22, "Medium"), MUTED, "la", aa)
    text(d, (x0 + w - 4, y + 170), "2100", F(22, "Medium"), MUTED, "ra", a)
    rows = [("Как читать строку", "слот 0 · всегда активен (AUX2 900–2100) · функция 29 · канал переключения AUX2", TE),
            ("Позиции", "900–2100 делится на три: тумблер ≈1000 / 1500 / 2000 попадает в 1 / 2 / 3", OR),
            ("Проверка", "щёлкни тумблер в Configurator: имя профиля в превью OSD должно меняться", GR)]
    cards(d, t, rows, y + 230, gap=18, t0=3.0, step=1.0, hs=34, bs=29)
    return fade(im, t, dur)


def s_warn(t, dur=12):
    im, d = base(); TB(d, "ПРЕДУПРЕЖДЕНИЯ", 5)
    ty = title(d, "Предупреждения, статистика, имена")
    rows = [("osd_warn_bitmask", "какие предупреждения показывать: батарея, связь, failsafe, GPS rescue и др. — по битам", RD),
            ("osd_stat_bitmask", "что показать после посадки: время, мин. напряжение, макс. ток, ёмкость…", TE),
            ("craft_name и pilot_name", "имя дрона и пилота: видно в OSD и в логах, удобно, когда дронов несколько", OR),
            ("Правило", "предупреждения мигают и не прячутся в «чистом» профиле: они важнее красоты", GR)]
    cards(d, t, rows, ty + 30, gap=18, t0=0.4, step=1.0, hs=34, bs=29)
    return fade(im, t, dur)


def s_end(t, dur=6):
    return end_card(t, dur, [("Шрифт — читаемость важнее красоты", OR), ("Центр свободен, углы работают", TE),
                             ("Три профиля = три флажка у каждого элемента", GR), ("adjrange …29… — профиль с тумблера", PU),
                             ("Предупреждения не прячь", RD)], "персонализация · блок 3")


SCENES = [("01_hook", s_hook, 7), ("02_fonts", s_fonts, 12), ("03_layout", s_layout, 14), ("04_profiles", s_profiles, 14),
          ("05_bits", s_bits, 15), ("06_switch", s_switch, 14), ("07_warn", s_warn, 12), ("08_end", s_end, 6)]

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    if sys.argv[1:] == ["preview"]:
        preview("v_osd_design", f"{here}/out/osdd_prev")
    else:
        render_video("v_osd_design", f"{here}/out/osdd", f"{here}/out/P2_OSD_design_profiles.mp4")
