"""Video P3: your own EdgeTX telemetry widget in Lua on a colour radio (RadioMaster TX16S).

Facts checked against EdgeTX 2.12.5 source: radio/src/sdcard.h (WIDGETS, SCRIPTS, SCRIPTS/MIXES paths),
radio/src/lua/widgets.cpp (widget table keys name/options/create/update/refresh/background/useLvgl; file /main.lua in a
folder under /WIDGETS), lua/interface.cpp (telemetry scripts only for PCBTARANIS, i.e. B&W radios), dataconstants.h
(LEN_SCRIPT_FILENAME 6 for SCRIPTS files), translations/untranslated.h CRSF sensor names (1RSS, RQly, RSNR, ANT, RFMD,
TPWR, TRSS, TQly, RxBt, Curr, Capa, FM). Silent. The widget code shown is an original minimal example.
usage: python3 v_lua_widget.py [preview|render]"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import *

TB = topbar(8)

WIDGET = ['local function create(zone, options)', '  return { zone = zone, options = options }', 'end',
          'local function update(w, options) w.options = options end',
          'local function refresh(w, event, touch)', '  local lq  = getValue("RQly")', '  local bat = getValue("RxBt")',
          '  local fm  = getValue("FM")', '  lcd.drawText(w.zone.x, w.zone.y, "LQ " .. lq, DBLSIZE)', '  -- ... батарея, режим',
          'end', 'return { name = "LinkBox", options = {},', '  create = create, update = update, refresh = refresh }']


def radio(d, x, y, a, lq=98, bat=24.6, fm="ACRO"):
    d.rounded_rectangle([x, y, x + 900, y + 520], radius=30, fill=mix(BG, (34, 38, 46), a), outline=mix(BG, (70, 76, 88), a), width=4)
    d.rounded_rectangle([x + 60, y + 50, x + 840, y + 470], radius=12, fill=mix(BG, (10, 12, 16), a))
    text(d, (x + 90, y + 80), "Model 1", F(26, "Bold"), MUTED, "la", a)
    d.rounded_rectangle([x + 90, y + 130, x + 470, y + 430], radius=14, fill=mix(BG, PANEL, a), outline=mix(BG, TE, a), width=3)
    text(d, (x + 110, y + 150), "LinkBox", F(22, "Medium"), MUTED, "la", a)
    col = GR if lq >= 70 else (OR if lq >= 40 else RD)
    text(d, (x + 110, y + 190), f"LQ {lq}", F(64, "Bold"), col, "la", a)
    text(d, (x + 110, y + 290), f"{bat:.1f} V", F(46, "Bold"), FG, "la", a)
    text(d, (x + 110, y + 360), fm, F(36, "Bold"), OR, "la", a)
    for i, (lab, v) in enumerate([("1RSS", "-63"), ("RSNR", "9"), ("TPWR", "250")]):
        text(d, (x + 520, y + 160 + i * 90), lab, M(26), MUTED, "la", a)
        text(d, (x + 800, y + 160 + i * 90), v, M(34), FG, "ra", a)


def s_hook(t, dur=7):
    im, d = base()
    a = ease(t / 0.6)
    text(d, (60, 230), "BETAFLIGHT ИЗНУТРИ · ТЮНИНГ И ПЕРСОНАЛИЗАЦИЯ", F(24, "Bold"), MUTED, "la", a)
    y = wrap_text(d, 60, 290, "Свой виджет на пульте", F(84, "Bold"), W - 120, FG, a, lh=96)
    wrap_text(d, 60, y + 10, "Lua в EdgeTX: экран телеметрии под себя на TX16S", F(46, "Bold"), W - 120, OR, ease((t - 0.4) / 0.6), lh=58)
    lq = int(98 - 60 * max(0, math.sin(t * 0.9)) ** 2)
    radio(d, 90, 640, ease((t - 0.8) / 0.6), lq=lq)
    wrap_text(d, 60, 1240, "Стандартные виджеты показывают по одному значению. Свой Lua-виджет собирает на одном экране то, что важно тебе: качество связи с цветом, батарею дрона, режим полёта.", F(32, "Medium"), W - 120, FG, ease((t - 1.8) / 0.7), lh=44)
    text(d, (60, 1700), "типы скриптов · где лежит · структура · сенсоры CRSF · отрисовка · ошибки", F(24, "Medium"), MUTED, "la", ease((t - 2.6) / 0.6))
    return fade(im, t, dur)


def s_types(t, dur=14):
    im, d = base(); TB(d, "ТИПЫ СКРИПТОВ", 0)
    ty = title(d, "Пять типов Lua-скриптов в EdgeTX")
    rows = [("Widget  /WIDGETS/<имя>/main.lua", "окно на главном экране цветного пульта — наш случай", GR),
            ("Telemetry  /SCRIPTS/TELEMETRY", "экран телеметрии только на ч/б пультах (Taranis-подобные). На TX16S вместо него — виджеты", MUTED),
            ("Function  /SCRIPTS/FUNCTIONS", "запускается из Special Functions; имя файла до 6 символов", TE),
            ("Mix  /SCRIPTS/MIXES", "свои миксы; нужен флаг сборки LUA_MIXER, есть не на всех пультах", OR),
            ("Tool  /SCRIPTS/TOOLS", "запускается вручную из меню, как ELRS Lua", PU)]
    cards(d, t, rows, ty + 30, gap=16, t0=0.4, step=0.9, hs=32, bs=28)
    return fade(im, t, dur)


def s_struct(t, dur=16):
    im, d = base(); TB(d, "СТРУКТУРА", 1)
    ty = title(d, "Виджет — это таблица с функциями")
    y = code_block(d, 40, ty + 20, WIDGET, ease((t - 0.4) / 0.6), 22, w=W - 80)
    rows = [("create(zone, options)", "один раз при добавлении: зона экрана и настройки", TE),
            ("refresh(w, event, touch)", "каждый кадр, пока виджет на экране: рисуем здесь", GR),
            ("background(w)", "вызывается, когда виджет НЕ виден: тяжёлую логику — в общую функцию, вызываемую из обеих", OR)]
    cards(d, t, rows, y + 24, gap=14, t0=3.0, step=1.0, hs=30, bs=27)
    return fade(im, t, dur)


def s_sensors(t, dur=13):
    im, d = base(); TB(d, "СЕНСОРЫ CRSF", 2)
    ty = title(d, "Что можно читать: сенсоры ELRS / CRSF")
    pairs = [("1RSS", "уровень сигнала у приёмника"), ("RQly", "качество связи, %"), ("RSNR", "сигнал/шум"), ("TPWR", "мощность TX"),
             ("TQly", "качество обратного канала"), ("RxBt", "батарея дрона"), ("Curr / Capa", "ток и израсходовано"), ("FM", "режим полёта")]
    for i, (k, v) in enumerate(pairs):
        aa = ease((t - 0.4 - i * 0.25) / 0.4)
        y = ty + 30 + i * 112
        d.rounded_rectangle([60, y, W - 60, y + 94], radius=14, fill=mix(BG, PANEL, aa))
        text(d, (100, y + 47), k, M(32), OR, "lm", aa)
        text(d, (430, y + 47), v, F(30, "Medium"), FG, "lm", aa)
    chip(d, (60, ty + 30 + 8 * 112 + 10), "Сенсоры появляются после «Discover new sensors» в телеметрии модели. В скрипте: getValue(\"RQly\")", F(28), TE, ease((t - 3.5) / 0.6))
    return fade(im, t, dur)


def s_draw(t, dur=13):
    im, d = base(); TB(d, "ОТРИСОВКА", 3)
    ty = title(d, "Цвет — это информация")
    radio(d, 90, ty + 40, ease((t - 0.4) / 0.5), lq=int(98 - 70 * ease((t - 1.0) / 6)))
    rows = [("Пороги цвета", "свои: например, LQ ≥ 70 зелёный, 40–70 оранжевый, ниже — красный. Это пример, подбери под свой канал", OR),
            ("Крупно главное", "LQ и батарея — большим шрифтом, остальное мелко", TE),
            ("Не рисуй лишнего", "refresh вызывается часто: тяжёлые расчёты сбавляют отклик интерфейса", RD)]
    cards(d, t, rows, ty + 600, gap=16, t0=2.0, step=1.0, hs=32, bs=28)
    return fade(im, t, dur)


def s_install(t, dur=12):
    im, d = base(); TB(d, "УСТАНОВКА", 4)
    ty = title(d, "Как поставить")
    items = [("SD-карта → /WIDGETS/LinkBox/main.lua", TE), ("пульт: Model → настройка экрана → пустая зона", OR),
             ("выбрать виджет LinkBox из списка", GR), ("Discover new sensors в телеметрии модели", PU), ("ошибка в коде — сообщение прямо в зоне виджета", RD)]
    for i, (s, col) in enumerate(items):
        aa = ease((t - 0.4 - i * 0.7) / 0.5); y = ty + 40 + i * 150
        d.rounded_rectangle([60, y, W - 60, y + 120], radius=18, fill=mix(BG, PANEL, aa))
        text(d, (100, y + 60), f"{i + 1}", F(48, "Bold"), col, "lm", aa)
        wrap_text(d, 170, y + 28, s, F(31, "SemiBold"), W - 270, FG, aa)
    return fade(im, t, dur)


def s_traps(t, dur=12):
    im, d = base(); TB(d, "ГРАБЛИ", 5)
    ty = title(d, "Частые ошибки")
    rows = [("Нет данных", "getValue возвращает 0: сенсоры не найдены или дрон не подключён", OR),
            ("Логика только в refresh", "переключил экран — виджет перестал считать. Общая функция из refresh и background", RD),
            ("Сломал главный экран", "держи копию на ПК; ошибка Lua не ломает пульт, но виджет выключится", TE),
            ("Ждёшь телеметрию быстрее канала", "частота данных — от telem ratio в ELRS (видео про ELRS)", PU)]
    cards(d, t, rows, ty + 30, gap=18, t0=0.4, step=1.0, hs=34, bs=29)
    return fade(im, t, dur)


def s_end(t, dur=6):
    return end_card(t, dur, [("Цветной пульт — виджеты, не telemetry-скрипты", TE), ("/WIDGETS/<имя>/main.lua", OR),
                             ("create · update · refresh · background", GR), ("Сенсоры CRSF: RQly, 1RSS, RxBt, FM…", PU),
                             ("Цвет и размер — по важности", FG)], "персонализация · блок 3")


SCENES = [("01_hook", s_hook, 7), ("02_types", s_types, 14), ("03_struct", s_struct, 16), ("04_sensors", s_sensors, 13),
          ("05_draw", s_draw, 13), ("06_install", s_install, 12), ("07_traps", s_traps, 12), ("08_end", s_end, 6)]

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    if sys.argv[1:] == ["preview"]:
        preview("v_lua_widget", f"{here}/out/lua_prev")
    else:
        render_video("v_lua_widget", f"{here}/out/lua", f"{here}/out/P3_EdgeTX_Lua_widget.mp4")
