"""Video P1: custom OSD boot logo (analog MAX7456 / AT7456E OSD), plus how HD systems differ.

Facts checked against sources: Betaflight Configurator 10.10 (src/js/LogoManager.js: 24x4 tiles of 12x18 px,
colour map green=transparent / black / white, PNG or BMP; locales/en/messages.json texts; tabs/osd.js SYM.LOGO=0xA0),
Betaflight 4.5.3 (osd/osd.c osdDrawLogo chars 160..255 at boot and on arming, osd_logo_on_arming OFF/ON/FIRST_ARMING,
osd_logo_on_arming_duration 5..50 x 0.1 s, default 5). Silent. The example logo is an original design.
usage: python3 v_boot_logo.py [preview|render|logo]"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import *
from PIL import ImageFilter

TB = topbar(7)
LOGO_W, LOGO_H = 288, 72                    # 24 x 12 px by 4 x 18 px
GREEN, BLACK, WHITE = (0, 255, 0), (0, 0, 0), (255, 255, 255)


def make_logo():
    """Original example logo: X-quad icon + text, white with a black outline on green (transparent)."""
    mask = Image.new("L", (LOGO_W, LOGO_H), 0)
    d = ImageDraw.Draw(mask)
    d.fontmode = "1"                          # no antialiasing: Configurator accepts only 3 exact colours
    cx, cy, r = 38, 36, 26
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        d.line([(cx, cy), (cx + sx * r, cy + sy * r)], fill=255, width=4)
        d.ellipse([cx + sx * r - 9, cy + sy * r - 9, cx + sx * r + 9, cy + sy * r + 9], outline=255, width=3)
    d.rectangle([cx - 6, cy - 6, cx + 6, cy + 6], fill=255)
    f1 = ImageFont.truetype(f"{FONT_DIR}/Inter-Black.otf", 34)
    f2 = ImageFont.truetype(f"{FONT_DIR}/Inter-Bold.otf", 16)
    d.text((82, 6), "MY QUAD", font=f1, fill=255)
    d.text((84, 46), "CALLSIGN · CONTACT", font=f2, fill=255)
    outline = mask.filter(ImageFilter.MaxFilter(5))
    im = Image.new("RGB", (LOGO_W, LOGO_H), GREEN)
    im.paste(BLACK, (0, 0), outline)
    im.paste(WHITE, (0, 0), mask)
    cols = {c for _, c in im.getcolors(1 << 16)}
    assert cols <= {GREEN, BLACK, WHITE}, cols
    return im


LOGO = make_logo()


def draw_logo(im, x, y, scale, a=1.0, grid=False, transparent_bg=None):
    big = LOGO.resize((LOGO_W * scale, LOGO_H * scale), Image.NEAREST)
    if transparent_bg is not None:
        px = big.load()
        bg = Image.new("RGB", big.size, transparent_bg)
        m = Image.new("L", big.size, 0); mp = m.load()
        for yy in range(big.size[1]):
            for xx in range(big.size[0]):
                if px[xx, yy] != GREEN:
                    mp[xx, yy] = 255
        bg.paste(big, (0, 0), m); big = bg
    if a < 1:
        big = Image.blend(Image.new("RGB", big.size, BG), big, a)
    im.paste(big, (x, y))
    if grid:
        d = ImageDraw.Draw(im)
        for i in range(25):
            d.line([(x + i * 12 * scale, y), (x + i * 12 * scale, y + LOGO_H * scale)], fill=mix(BG, OR, a * 0.9), width=2)
        for j in range(5):
            d.line([(x, y + j * 18 * scale), (x + LOGO_W * scale, y + j * 18 * scale)], fill=mix(BG, OR, a * 0.9), width=2)


def osd_screen(im, d, x, y, w, h, a, t_show):
    """Mock analog goggles view at boot: noisy grey video + logo + version text (layout from osdCompleteInitialization)."""
    d.rounded_rectangle([x, y, x + w, y + h], radius=14, fill=mix(BG, (58, 62, 66), a))
    for k in range(0, h, 6):
        d.line([(x + 6, y + k), (x + w - 6, y + k)], fill=mix(BG, (66 + (k * 37) % 9, 70, 74), a))
    s = (w - 40) // LOGO_W
    lx = x + (w - LOGO_W * s) // 2; ly = y + h // 2 - 5 * 18 * s // 2 - 30
    big = LOGO.resize((LOGO_W * s, LOGO_H * s), Image.NEAREST)
    m = Image.new("L", big.size, 0)
    m.putdata([0 if p == GREEN else int(255 * a * t_show) for p in big.getdata()])
    im.paste(big, (lx, ly), m)
    text(d, (x + w / 2 + 40, ly + LOGO_H * s + 30), "V4.5.3", M(26), WHITE, "la", a * t_show)
    text(d, (x + w / 2, ly + LOGO_H * s + 90), "MENU:THR MID", M(24), WHITE, "ma", a * t_show)
    text(d, (x + w / 2, ly + LOGO_H * s + 126), "+ YAW LEFT", M(24), WHITE, "ma", a * t_show)
    text(d, (x + w / 2, ly + LOGO_H * s + 162), "+ PITCH UP", M(24), WHITE, "ma", a * t_show)


def s_hook(t, dur=7):
    im, d = base()
    a = ease(t / 0.6)
    text(d, (60, 230), "BETAFLIGHT ИЗНУТРИ · ТЮНИНГ И ПЕРСОНАЛИЗАЦИЯ", F(24, "Bold"), MUTED, "la", a)
    y = wrap_text(d, 60, 290, "Своя заставка OSD", F(84, "Bold"), W - 120, FG, a, lh=96)
    wrap_text(d, 60, y + 10, "логотип при включении дрона: как сделать и где он живёт", F(46, "Bold"), W - 120, OR, ease((t - 0.4) / 0.6), lh=58)
    osd_screen(im, d, 90, 640, 900, 560, ease((t - 0.8) / 0.6), ease((t - 1.4) / 0.6))
    wrap_text(d, 60, 1290, "Аналоговое OSD показывает картинку при каждом включении. По умолчанию там логотип прошивки, но это всего лишь 96 символов шрифта, и их можно заменить своими.", F(32, "Medium"), W - 120, FG, ease((t - 1.8) / 0.7), lh=44)
    text(d, (60, 1700), "что это · картинка · загрузка · что переживает прошивку · HD · практика", F(24, "Medium"), MUTED, "la", ease((t - 2.6) / 0.6))
    return fade(im, t, dur)


def s_what(t, dur=13):
    im, d = base(); TB(d, "ЧТО ЭТО", 0)
    ty = title(d, "Заставка — это часть шрифта OSD")
    rows = [("Чип OSD на полётнике", "MAX7456 или AT7456E рисует поверх видео символы 12 × 18 px из шрифта на 256 символов", TE),
            ("Где шрифт", "в собственной памяти чипа OSD, а не во flash полётника", OR),
            ("Где логотип", "символы 160–255 (0xA0–0xFF): 24 в ширину × 4 в высоту = 96 символов", GR),
            ("Когда показывается", "при включении, вместе с версией прошивки и подсказкой входа в меню", PU)]
    y = cards(d, t, rows, ty + 30, gap=18, t0=0.4, step=1.0, hs=34, bs=29)
    code_block(d, 60, y + 16, ["set osd_logo_on_arming = FIRST_ARMING   # OFF / ON / FIRST_ARMING",
                               "set osd_logo_on_arming_duration = 5     # × 0.1 с, 5–50"], ease((t - 5.4) / 0.5), 22)
    return fade(im, t, dur)


def s_image(t, dur=15):
    im, d = base(); TB(d, "КАРТИНКА", 1)
    ty = title(d, "288 × 72 пикселя и только три цвета")
    a = ease((t - 0.4) / 0.6)
    draw_logo(im, 108, ty + 40, 3, a, grid=ease((t - 1.6) / 0.6) > 0.5)
    text(d, (W / 2, ty + 40 + 216 + 24), "сетка: 24 × 4 символа по 12 × 18 px", F(26, "Medium"), OR, "ma", ease((t - 1.6) / 0.6))
    rows = [("Зелёный 0,255,0", "прозрачно: сквозь него видно видео", GR),
            ("Чёрный 0,0,0", "чёрный пиксель", MUTED),
            ("Белый 255,255,255", "белый пиксель", FG)]
    y = cards(d, t, rows, ty + 330, gap=14, t0=2.6, step=0.7, hs=32, bs=28)
    chip(d, (60, y + 14), "Любой другой цвет — ошибка «invalid pixel» с координатами. Рисуй без сглаживания (antialiasing выкл.), формат PNG или BMP", F(28), RD, ease((t - 5.4) / 0.6))
    return fade(im, t, dur)


def s_upload(t, dur=14):
    im, d = base(); TB(d, "ЗАГРУЗКА", 2)
    ty = title(d, "Как залить: Font Manager")
    steps = [("Configurator → вкладка OSD", "в статусе полётника должен быть найден чип MAX7456", TE),
             ("Font Manager", "выбрать основу шрифта из списка", OR),
             ("Boot logo → Select custom image…", "размер и цвета проверяются сразу, обе строки должны стать зелёными", GR),
             ("Upload Font", "в чип уходит весь шрифт вместе с логотипом: «Uploaded all … characters»", PU)]
    y = ty + 30
    for i, (h, s, col) in enumerate(steps):
        aa = ease((t - 0.4 - i * 1.1) / 0.5)
        d.rounded_rectangle([60, y, W - 60, y + 170], radius=20, fill=mix(BG, PANEL, aa))
        text(d, (100, y + 85), str(i + 1), F(56, "Bold"), col, "lm", aa)
        text(d, (180, y + 30), h, F(32, "Bold"), col, "la", aa)
        wrap_text(d, 180, y + 82, s, F(28, "Medium"), W - 280, FG, aa)
        y += 192
    chip(d, (60, y + 10), "На многих платах чип OSD питается не от USB: подключи батарею, пропеллеры сняты", F(28), OR, ease((t - 5.6) / 0.6))
    return fade(im, t, dur)


def s_persist(t, dur=13):
    im, d = base(); TB(d, "ЧТО ОСТАЁТСЯ", 3)
    ty = title(d, "Что переживёт перепрошивку")
    rows = [("Остаётся", "перепрошивка Betaflight и Full chip erase стирают flash процессора, а шрифт лежит в чипе OSD", GR),
            ("Теряется", "при загрузке любого другого шрифта: заливается весь шрифт целиком, и логотип вместе с ним", RD),
            ("Не в бэкапе", "diff all логотип не содержит. Храни PNG рядом с бэкапом дрона", OR),
            ("Новый полётник", "новый чип OSD — заливай заново", TE)]
    cards(d, t, rows, ty + 30, gap=20, t0=0.4, step=1.0)
    return fade(im, t, dur)


def s_hd(t, dur=13):
    im, d = base(); TB(d, "HD-СИСТЕМЫ", 4)
    ty = title(d, "В цифре логотип рисуют очки")
    a = ease((t - 0.4) / 0.5)
    boxes = [("полётник", "шлёт номера символов по MSP DisplayPort", TE), ("очки / VTX", "рисуют своим шрифтом", OR)]
    for i, (h, s, col) in enumerate(boxes):
        aa = ease((t - 0.4 - i * 0.6) / 0.5); x = 60 + i * 500
        d.rounded_rectangle([x, ty + 40, x + 460, ty + 230], radius=20, fill=mix(BG, PANEL, aa), outline=mix(BG, col, aa), width=3)
        text(d, (x + 30, ty + 80), h, F(36, "Bold"), col, "la", aa)
        wrap_text(d, x + 30, ty + 135, s, F(27, "Medium"), 400, FG, aa)
    arrow(d, (522, ty + 135), (558, ty + 135), MUTED, ease((t - 1.0) / 0.5))
    rows = [("Тот же номер, другой рисунок", "полётник и в цифре выводит символы 160–255 при старте, но как они выглядят — решает файл шрифта в очках или VTX", TE),
            ("Font Manager не поможет", "чипа MAX7456 на HD-полётнике нет: заливать нечего и некуда", RD),
            ("Как менять", "свой файл шрифта по инструкции конкретной системы (формат и место у всех разные)", OR)]
    cards(d, t, rows, ty + 280, gap=20, t0=2.0, step=1.1)
    return fade(im, t, dur)


def s_practice(t, dur=13):
    im, d = base(); TB(d, "ПРАКТИКА", 5)
    ty = title(d, "Что положить в заставку")
    draw_logo(im, 108, ty + 40, 3, ease((t - 0.4) / 0.6), transparent_bg=(62, 66, 70))
    rows = [("Позывной и контакт", "если дрон найдут после падения — заставку видно при включении", GR),
            ("Контраст", "белое с чёрной обводкой читается и на небе, и на траве", TE),
            ("Толщина", "линии от 2–3 px: OSD и аналоговое видео размывают мелочь", OR),
            ("Проверка", "смотри в очках, а не на мониторе. И без чужих логотипов", PU)]
    cards(d, t, rows, ty + 300, gap=16, t0=1.4, step=0.9, hs=34, bs=29)
    return fade(im, t, dur)


def s_end(t, dur=6):
    return end_card(t, dur, [("Логотип = символы 160–255 шрифта OSD", OR), ("288 × 72 px: зелёный, чёрный, белый", GR),
                             ("Font Manager → Upload Font", TE), ("Живёт в чипе OSD, не в diff all", RD),
                             ("В HD — файл шрифта очков", PU)], "персонализация · блок 3")


SCENES = [("01_hook", s_hook, 7), ("02_what", s_what, 13), ("03_image", s_image, 15), ("04_upload", s_upload, 14),
          ("05_persist", s_persist, 13), ("06_hd", s_hd, 13), ("07_practice", s_practice, 13), ("08_end", s_end, 6)]

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    if sys.argv[1:] == ["preview"]:
        preview("v_boot_logo", f"{here}/out/logo_prev")
    elif sys.argv[1:] == ["logo"]:
        LOGO.save(f"{here}/out/osd_boot_logo_template_288x72.png")
    else:
        render_video("v_boot_logo", f"{here}/out/logo", f"{here}/out/P1_OSD_boot_logo.mp4")
