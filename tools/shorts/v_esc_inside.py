"""Video C1: «chip tuning» of the ESC — what is hidden inside Bluejay and AM32 firmware.

Not a repeat of the earlier «ESC firmware» video (which covered chips, choosing and flashing).
Facts checked against sources: Bluejay master (src/Settings/BluejaySettings.asm defaults, Makefile PWM_FREQS,
src/Modules/DShot.asm commands, README), AM32 2.22 (Inc/eeprom.h layout, Src/main.c limits and PWM logic),
Betaflight 4.5.3 (cli/settings.c dshot_edt). Silent.
usage: python3 v_esc_inside.py [preview|render]"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import *

TB = topbar(9)


def s_hook(t, dur=7):
    def draw(d, t, a):
        rows = [("Bluejay", "EFM8 · BLHeli_S-совместимые", TE), ("AM32", "ARM · 32 бита", GR)]
        for i, (h, s, col) in enumerate(rows):
            aa = ease((t - 0.9 - i * 0.4) / 0.5) * (a > 0)
            x = 60 + i * 490
            d.rounded_rectangle([x, 760, x + 470, 1010], radius=24, fill=mix(BG, PANEL, aa), outline=mix(BG, col, aa), width=4)
            text(d, (x + 30, 800), h, F(52, "Bold"), col, "la", aa)
            text(d, (x + 30, 880), s, F(28, "Medium"), FG, "la", aa)
            text(d, (x + 30, 940), "свои настройки в EEPROM", M(24), MUTED, "la", aa)
    return hook(t, dur, "Прошивка регулятора изнутри", "что можно настроить в ESC, кроме «прошить и забыть»",
                "Прошить Bluejay или AM32 — половина дела. Внутри регулятора живут частота ШИМ, тайминг, мощность старта, защиты, тормоз, мелодия и маяк. Эти настройки хранятся в самом ESC, а не в полётнике.",
                "где настраивать · ШИМ · тайминг · старт и защиты · тормоз · звук · EDT · правила", draw)


def s_where(t, dur=12):
    im, d = base(); TB(d, "ГДЕ ЭТО ЖИВЁТ", 0)
    ty = title(d, "Настройки в ESC, а не в полётнике")
    boxes = [("ESC Configurator", "браузер, USB", OR), ("полётник", "passthrough: пропуск команд к ESC", TE), ("4 × ESC", "EEPROM каждого регулятора", GR)]
    for i, (h, s, col) in enumerate(boxes):
        aa = ease((t - 0.4 - i * 0.5) / 0.5); y = ty + 30 + i * 160
        d.rounded_rectangle([120, y, W - 120, y + 120], radius=18, fill=mix(BG, PANEL, aa), outline=mix(BG, col, aa), width=3)
        text(d, (160, y + 40), h, F(36, "Bold"), col, "lm", aa)
        text(d, (160, y + 84), s, F(26, "Medium"), FG, "lm", aa)
        if i < 2:
            arrow(d, (W / 2, y + 122), (W / 2, y + 156), MUTED, aa, 4, 12)
    rows = [("Читай все четыре", "конфигуратор показывает каждый ESC отдельно: разные значения на одном дроне — первая находка", OR),
            ("В diff all их нет", "бэкап Betaflight настройки регулятора не сохраняет: записывай их отдельно", RD),
            ("Пропеллеры сняты", "при любой работе с ESC и проверке моторов", GR)]
    cards(d, t, rows, ty + 540, gap=20, t0=2.4, step=1.0)
    return fade(im, t, dur)


def s_pwm(t, dur=15):
    im, d = base(); TB(d, "ЧАСТОТА ШИМ", 1)
    ty = title(d, "Частота ШИМ: файл прошивки или ручка")
    rows = [("Bluejay", "24, 48 или 96 кГц — это разные файлы прошивки, выбираешь при прошивке. В EEPROM такой настройки нет", TE),
            ("AM32", "pwm_frequency — настройка в EEPROM, прошивка принимает 8–144 кГц. Плюс variable PWM: 0 — фиксированная, 1 — меняется с оборотами в заданном диапазоне, 2 — автоматически", GR)]
    y = cards(d, t, rows, ty + 30, gap=22, t0=0.4, step=1.2)
    a = ease((t - 3.4) / 0.5)
    text(d, (60, y + 20), "Что меняет частота", F(36, "Bold"), FG, "la", a)
    pts = [("выше частота", "ровнее ток, тише мотор, мягче отклик на малом газе", GR), ("но", "больше потерь на переключение — регулятор теплее", RD)]
    for i, (h, s, col) in enumerate(pts):
        aa = ease((t - 4.0 - i * 0.8) / 0.5)
        text(d, (60, y + 90 + i * 100), h, F(32, "Bold"), col, "la", aa)
        wrap_text(d, 300, y + 92 + i * 100, s, F(29, "Medium"), W - 360, FG, aa)
    chip(d, (60, y + 320), "Правило выбора по классу — в курсе (f-esc-firmware): мелочь 48 кГц, 5\" 24–48, 7\" и крупнее 24 или variable. С DJI O3/O4 и Gyroflow — 48 кГц и выше для любого класса: 24 кГц мешает IMU камеры", F(28), OR, ease((t - 6.5) / 0.6))
    return fade(im, t, dur)


def s_timing(t, dur=14):
    im, d = base(); TB(d, "ТАЙМИНГ", 2)
    ty = title(d, "Тайминг и demag: против десинков")
    rows = [("Bluejay: Motor timing", "1 Low … 5 High, по умолчанию 4 (MediumHigh)", TE),
            ("Bluejay: Demag compensation", "1 выкл · 2 Low (умолчание) · 3 High", TE),
            ("AM32: Timing advance", "0–30° с шагом ≈ 0.94°, есть auto advance", GR),
            ("AM32: Demag compensation", "0 выкл … 4 сильнее всего (срез мощности после demag)", GR)]
    y = cards(d, t, rows, ty + 30, gap=18, t0=0.4, step=0.8, hs=34, bs=29)
    rows2 = [("Десинк на резком газе, тяжёлые пропы", "сначала demag High, потом тайминг на шаг выше", RD),
             ("Моторы горячие при ровном полёте", "тайминг на шаг ниже, если десинков нет", OR)]
    cards(d, t, rows2, y + 20, gap=18, t0=4.4, step=1.0, hs=32, bs=29)
    return fade(im, t, dur)


def s_start(t, dur=15):
    im, d = base(); TB(d, "СТАРТ И ЗАЩИТЫ", 3)
    ty = title(d, "Старт мотора и защиты регулятора")
    rows = [("Bluejay: Startup power min / max", "сколько мощности дать на трогании; RPM power protection (умолчание 9, 0 — выкл) ограничивает мощность на малых оборотах — бережёт мотор при застревании", TE),
            ("Bluejay: Temperature protection", "по умолчанию выключена; можно 80…140 °C", TE),
            ("AM32: старт и застревание", "startup power, sine start (плавный старт), stuck rotor и stall protection", GR),
            ("AM32: пределы", "температура 70–140 °C (выше — мощность плавно снижается), ток: значение × 2 А, отсечка 2.5–3.5 В на ячейку", GR)]
    y = cards(d, t, rows, ty + 30, gap=18, t0=0.4, step=1.0, hs=32, bs=28)
    chip(d, (60, y + 20), "Защита, которая срабатывает в воздухе, опускает дрон. Порог отсечки ставь ниже, чем предупреждение в OSD, иначе узнаешь о нём по падению", F(28), RD, ease((t - 6.0) / 0.6))
    return fade(im, t, dur)


def s_brake(t, dur=11):
    im, d = base(); TB(d, "ТОРМОЗ И 3D", 4)
    ty = title(d, "Тормоз и направление")
    rows = [("Brake on stop", "держит мотор на нулевом газе. Bluejay — по умолчанию выключен; сила торможения 0–100 %", OR),
            ("Направление", "Normal / Reversed / Bidirectional (3D). Направление удобнее менять так: в ESC или командой DShot из полётника, а не перепайкой", TE),
            ("AM32", "brake on stop, active brake power 1–5 %, bi-direction", GR)]
    cards(d, t, rows, ty + 40, gap=30, t0=0.4, step=1.1, hs=42, bs=34)
    return fade(im, t, dur)


def s_sound(t, dur=13):
    im, d = base(); TB(d, "ЗВУК", 5)
    ty = title(d, "Мелодия и маяк самого ESC")
    rows = [("Стартовая мелодия", "Bluejay: своя мелодия при включении (редактор в ESC Configurator). AM32: tune — 128 байт в EEPROM", PU),
            ("Громкость", "Bluejay beep strength 40, beacon strength 80 (0–255)", TE),
            ("Маяк регулятора", "Bluejay beacon delay: 1, 2, 5, 10 мин или никогда, по умолчанию 10 мин без сигнала", OR),
            ("Не путать с маяком Betaflight", "DShot beacon — команда от полётника; маяк ESC пищит сам, когда сигнала нет совсем", RD)]
    y = cards(d, t, rows, ty + 30, gap=18, t0=0.4, step=1.0, hs=34, bs=29)
    chip(d, (60, y + 20), "Четыре ESC = четыре голоса мелодии. Один молчит — не армить: проверь мотор и регулятор", F(28), GR, ease((t - 5.5) / 0.6))
    return fade(im, t, dur)


def s_edt(t, dur=12):
    im, d = base(); TB(d, "EDT", 6)
    ty = title(d, "EDT: регулятор рассказывает о себе")
    rows = [("Что это", "Extended DShot Telemetry: по тому же проводу DShot вместе с оборотами приходят температура и другие данные", TE),
            ("Включение в Betaflight", "set dshot_edt = ON (нужен двунаправленный DShot)", OR),
            ("Bluejay: EDT safety arm", "можно запретить старт мотора, пока полётник не включил EDT", GR),
            ("Зачем", "температура каждого ESC в OSD и в логе: перегрев видно до того, как пахнет", PU)]
    cards(d, t, rows, ty + 40, gap=26, t0=0.4, step=1.0, hs=40, bs=33)
    return fade(im, t, dur)


def s_rules(t, dur=12):
    im, d = base(); TB(d, "ПРАВИЛА", 7)
    ty = title(d, "Как «чиповать» и не сжечь")
    items = [("одинаковые настройки на всех четырёх ESC", GR), ("одна настройка за раз, потом висение и рука на моторы", OR),
             ("после каждой правки — проверка направления моторов", TE), ("записать, что стояло и что стало", PU),
             ("перегрев или десинк — вернуть прошлое значение", RD)]
    for i, (s, col) in enumerate(items):
        aa = ease((t - 0.4 - i * 0.7) / 0.5); y = ty + 40 + i * 150
        d.rounded_rectangle([60, y, W - 60, y + 120], radius=18, fill=mix(BG, PANEL, aa))
        text(d, (100, y + 60), f"{i + 1}", F(48, "Bold"), col, "lm", aa)
        wrap_text(d, 170, y + 28, s, F(32, "SemiBold"), W - 270, FG, aa)
    return fade(im, t, dur)


def s_end(t, dur=6):
    return end_card(t, dur, [("Настройки ESC — в самом ESC, не в diff all", OR), ("Bluejay: ШИМ = файл прошивки, AM32 — ручка", TE),
                             ("Десинк: demag, потом тайминг", GR), ("Защиты опускают дрон — ставь пороги осознанно", RD),
                             ("EDT: температура ESC в OSD", PU)], "чип-тюнинг · блок 2")


SCENES = [("01_hook", s_hook, 7), ("02_where", s_where, 12), ("03_pwm", s_pwm, 15), ("04_timing", s_timing, 14),
          ("05_start", s_start, 15), ("06_brake", s_brake, 11), ("07_sound", s_sound, 13), ("08_edt", s_edt, 12),
          ("09_rules", s_rules, 12), ("10_end", s_end, 6)]

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    if sys.argv[1:] == ["preview"]:
        preview("v_esc_inside", f"{here}/out/esc_prev")
    else:
        render_video("v_esc_inside", f"{here}/out/esc", f"{here}/out/C1_ESC_firmware_inside.mp4")
