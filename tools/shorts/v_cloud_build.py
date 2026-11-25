"""Video C2: Betaflight Cloud Build — building your own firmware with only the features you need.

Facts checked against Betaflight Configurator 10.10 (tabs/firmware_flasher.js option groups: radioProtocols,
telemetryProtocols, generalOptions, motorProtocols; locales: Build Configuration, Other Options, Custom Defines (expert
mode), Core Only description, Build Key, Cloud Build Log) and Betaflight 4.5.3 (cli/cli.c `status` prints BUILD KEY and
release name for cloud builds). Silent.
usage: python3 v_cloud_build.py [preview|render]"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import *

TB = topbar(8)


def s_hook(t, dur=7):
    def draw(d, t, a):
        items = [("Radio Protocol", "CRSF", OR), ("Telemetry", "CRSF", TE), ("Motor Protocol", "DSHOT", GR), ("Other Options", "GPS · LED_STRIP · OSD_SD", PU)]
        for i, (h, v, col) in enumerate(items):
            aa = ease((t - 0.9 - i * 0.25) / 0.4) * (a > 0)
            y = 680 + i * 140
            d.rounded_rectangle([60, y, W - 60, y + 112], radius=18, fill=mix(BG, PANEL, aa), outline=mix(BG, col, aa), width=3)
            text(d, (100, y + 56), h, F(32, "Bold"), col, "lm", aa)
            text(d, (W - 100, y + 56), v, M(28), FG, "rm", aa)
    return hook(t, dur, "Своя прошивка за минуту", "Betaflight Cloud Build: что включить и чем рискуешь",
                "С 4.4 Configurator не скачивает «готовую прошивку на всё». Он собирает её на сервере из того, что ты выбрал. Выберешь лишнее — потратишь место. Забудешь нужное — приёмник просто не заработает.",
                "как работает · что выбирать · custom defines · core only · build key · риски", draw)


def s_how(t, dur=12):
    im, d = base(); TB(d, "КАК РАБОТАЕТ", 0)
    ty = title(d, "Сборка на сервере под твой полётник")
    steps = [("выбираешь плату и версию", MUTED), ("отмечаешь протоколы и функции", OR), ("сервер компилирует прошивку", TE),
             ("Configurator прошивает результат", GR)]
    for i, (s, col) in enumerate(steps):
        aa = ease((t - 0.4 - i * 0.6) / 0.5); y = ty + 40 + i * 150
        d.rounded_rectangle([140, y, W - 140, y + 110], radius=18, fill=mix(BG, PANEL, aa), outline=mix(BG, col, aa), width=3)
        text(d, (W / 2, y + 55), s, F(32, "Bold"), col, "mm", aa)
        if i < 3:
            arrow(d, (W / 2, y + 112), (W / 2, y + 146), MUTED, aa, 4, 12)
    chip(d, (60, ty + 660), "Плюс: в прошивке только нужное, на маленьких платах (F411) это важно. Минус: чего не выбрал — того в прошивке нет совсем", F(30), OR, ease((t - 3.4) / 0.6))
    return fade(im, t, dur)


def s_groups(t, dur=15):
    im, d = base(); TB(d, "ЧТО ВЫБИРАТЬ", 1)
    ty = title(d, "Четыре группы настроек сборки")
    rows = [("Radio Protocol", "протокол приёмника: CRSF для ELRS и Crossfire, SBUS и другие. Ошибёшься — нет управления", OR),
            ("Telemetry Protocol", "телеметрия обратно в пульт. У части протоколов приёмника она уже включена — поле становится серым", TE),
            ("Motor Protocol", "DShot и другие протоколы моторов", GR),
            ("Other Options", "GPS, LED-лента, OSD (аналоговое или HD), VTX-управление, сервы и прочее — по списку", PU)]
    cards(d, t, rows, ty + 30, gap=20, t0=0.4, step=1.1, hs=36, bs=30)
    return fade(im, t, dur)


def s_checklist(t, dur=14):
    im, d = base(); TB(d, "ПЕРЕД СБОРКОЙ", 2)
    ty = title(d, "Список «что у меня на борту»")
    a = ease((t - 0.4) / 0.5)
    y = code_block(d, 60, ty + 30, ["# старый полётник подключён: CLI", "status            # что найдено: OSD, сенсоры, BUILD KEY",
                                    "diff all          # что включено: serial, feature, set ..."], a, 24)
    rows = [("Приёмник", "какой протокол и на каком UART", OR), ("Видео", "аналог (чип OSD) или HD (MSP DisplayPort)", TE),
            ("Периферия", "GPS, LED, сервы, VTX по SmartAudio/Tramp", GR), ("Потом", "отметить всё это в сборке, а не по памяти", PU)]
    cards(d, t, rows, y + 30, gap=16, t0=1.6, step=0.9, hs=34, bs=29)
    return fade(im, t, dur)


def s_expert(t, dur=13):
    im, d = base(); TB(d, "ЭКСПЕРТ", 3)
    ty = title(d, "Custom Defines и Core Only")
    rows = [("Custom Defines", "поле для своих define-ов сборки; видно только в Expert Mode. Это уже правка исходника — нужна причина и понимание, что именно включаешь", RD),
            ("Core Only", "прошивка только с драйверами железа и минимумом функций. Нужна, чтобы проверить, что плата вообще определяется, — не для полёта", TE),
            ("Не получилось собрать", "у сборки есть лог на сервере, Configurator даёт на него ссылку", OR)]
    cards(d, t, rows, ty + 30, gap=22, t0=0.4, step=1.2)
    return fade(im, t, dur)


def s_key(t, dur=12):
    im, d = base(); TB(d, "BUILD KEY", 4)
    ty = title(d, "Build key: паспорт твоей прошивки")
    code_block(d, 60, ty + 30, ["status", "...", "BUILD KEY: <ключ сборки> (<версия>)"], ease((t - 0.4) / 0.5), 26)
    rows = [("Что это", "идентификатор именно этой сборки на сервере: плата, версия, выбранные опции", TE),
            ("Где видно", "в Configurator после сборки и в CLI командой status", OR),
            ("Зачем", "записать рядом с diff all: через полгода будет понятно, какая прошивка стояла и что в ней было", GR)]
    cards(d, t, rows, ty + 300, gap=20, t0=1.4, step=1.1, hs=34, bs=29)
    return fade(im, t, dur)


def s_risks(t, dur=13):
    im, d = base(); TB(d, "РИСКИ", 5)
    ty = title(d, "Где чаще всего ошибаются")
    rows = [("Нет протокола приёмника", "прошил — пульт не видит. Не паника: пересобрать с нужным протоколом", RD),
            ("Нет OSD нужного типа", "аналог и HD — разные опции. В очках пусто", OR),
            ("Нет SERVOS, LED_STRIP, GPS", "функция есть в Configurator, но вкладка пустая или настройки не сохраняются", TE),
            ("Вставил diff от другой сборки", "строки для невыбранных функций выдадут ошибки — читай вывод CLI", PU)]
    cards(d, t, rows, ty + 30, gap=18, t0=0.4, step=1.0, hs=34, bs=29)
    return fade(im, t, dur)


def s_rules(t, dur=11):
    im, d = base(); TB(d, "ПРАВИЛА", 6)
    ty = title(d, "Своя прошивка без сюрпризов")
    items = [("перед прошивкой: diff all в файл", OR), ("список железа — до выбора опций", TE), ("после прошивки: status и проверка всех вкладок", GR),
             ("build key и diff храни вместе", PU), ("Full chip erase — осознанно: он сбрасывает настройки", RD)]
    for i, (s, col) in enumerate(items):
        aa = ease((t - 0.4 - i * 0.7) / 0.5); y = ty + 40 + i * 150
        d.rounded_rectangle([60, y, W - 60, y + 120], radius=18, fill=mix(BG, PANEL, aa))
        text(d, (100, y + 60), f"{i + 1}", F(48, "Bold"), col, "lm", aa)
        wrap_text(d, 170, y + 28, s, F(32, "SemiBold"), W - 270, FG, aa)
    return fade(im, t, dur)


def s_end(t, dur=6):
    return end_card(t, dur, [("Прошивка собирается под твой выбор", OR), ("Чего не выбрал — того нет совсем", RD),
                             ("Список железа до сборки", TE), ("Build key + diff all = паспорт дрона", GR),
                             ("Custom Defines — только с причиной", PU)], "чип-тюнинг · блок 2")


SCENES = [("01_hook", s_hook, 7), ("02_how", s_how, 12), ("03_groups", s_groups, 15), ("04_checklist", s_checklist, 14),
          ("05_expert", s_expert, 13), ("06_key", s_key, 12), ("07_risks", s_risks, 13), ("08_rules", s_rules, 11), ("09_end", s_end, 6)]

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    if sys.argv[1:] == ["preview"]:
        preview("v_cloud_build", f"{here}/out/cb_prev")
    else:
        render_video("v_cloud_build", f"{here}/out/cb", f"{here}/out/C2_Betaflight_Cloud_Build.mp4")
