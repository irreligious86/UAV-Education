"""Video C3: ExpressLRS inside — binding phrase, regulatory domain, model match, packet rate and telemetry ratio.

Facts checked against ExpressLRS 4.1 source: python/build_flags.py (UID = first 6 bytes of MD5 of the define string
'-DMY_BINDING_PHRASE="..."'), FHSS regulatory domains (FCC_915, EU_868, IN_866, AU_915, AU_433, EU_433, US_433,
US_433_WIDE, ISM_2400, EU_CE_2400 with LBT in lib/LBT), lib/tx-crsf/TXModuleParameters.cpp (Lua items Packet Rate,
Telem Ratio, Switch Mode, Link Mode, Model Match; 2.4 GHz rate list with sensitivities 50Hz -115 ... F1000 -104 dBm;
telemetry ratios Std/Off/1:128..1:2/Race), src/tx_main.cpp (model match XORs the last UID byte with the model id).
Silent.
usage: python3 v_elrs_inside.py [preview|render]"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import *
import hashlib

TB = topbar(8)
RATES = [("50Hz", -115), ("100Hz Full", -112), ("150Hz", -112), ("250Hz", -108), ("333Hz Full", -105), ("500Hz", -105),
         ("D250", -104), ("D500", -104), ("F500", -104), ("F1000", -104)]
PHRASE = "my-secret-phrase"
UID = list(hashlib.md5(f'-DMY_BINDING_PHRASE="{PHRASE}"'.encode()).digest()[:6])


def s_hook(t, dur=7):
    def draw(d, t, a):
        code_block(d, 60, 700, [f'phrase = "{PHRASE}"', "UID = MD5(...)[0:6]", "     = " + " ".join(f"{b:02X}" for b in UID)], a, 30)
    return hook(t, dur, "ELRS изнутри", "фраза привязки, регион, model match и packet rate",
                "ExpressLRS прошивают за минуту и забывают. А внутри — шесть байт из фразы привязки, частотный план региона, защита от «не той модели» и десять режимов пакетов, у каждого своя дальность. Разбираем по исходникам 4.1.",
                "фраза → UID · регион и LBT · model match · packet rate · телеметрия · выбор", draw)


def s_uid(t, dur=13):
    im, d = base(); TB(d, "ФРАЗА ПРИВЯЗКИ", 0)
    ty = title(d, "Binding phrase превращается в 6 байт")
    y = code_block(d, 60, ty + 30, [f'-DMY_BINDING_PHRASE="{PHRASE}"', "MD5(эта строка) → первые 6 байт",
                                    "UID = " + " ".join(f"{b:02X}" for b in UID)], ease((t - 0.4) / 0.5), 27)
    rows = [("Зачем", "передатчик и приёмник с одним UID слышат только друг друга и прыгают по одной таблице частот", TE),
            ("Фраза одна на весь парк", "все приёмники с этой фразой видят твой передатчик — удобно, если моделей много", OR),
            ("Это не шифрование", "фраза отделяет тебя от соседей, но не защищает канал. Не делай её «12345»", RD)]
    cards(d, t, rows, y + 30, gap=18, t0=1.6, step=1.1, hs=34, bs=29)
    return fade(im, t, dur)


def s_domain(t, dur=13):
    im, d = base(); TB(d, "РЕГИОН", 1)
    ty = title(d, "Regulatory domain: где и как можно излучать")
    rows = [("900 МГц", "FCC_915, EU_868, IN_866, AU_915, а также 433 МГц варианты: AU_433, EU_433, US_433", OR),
            ("2.4 ГГц", "ISM_2400 — обычный; EU_CE_2400 — с LBT: перед передачей «слушает» эфир, как требуют правила ЕС", TE),
            ("Обе стороны", "у TX и RX должен быть одинаковый регион: разные частотные планы не встретятся", RD),
            ("Выбор", "по месту полётов и правилам страны, а не «где дальше летает»", GR)]
    cards(d, t, rows, ty + 30, gap=18, t0=0.4, step=1.0, hs=34, bs=29)
    return fade(im, t, dur)


def s_match(t, dur=13):
    im, d = base(); TB(d, "MODEL MATCH", 2)
    ty = title(d, "Model match: дрон отвечает только своей модели")
    rows = [("Как устроено", "передатчик смешивает номер модели пульта с последним байтом UID. Приёмник, привязанный с Model Match, слышит только этот номер", TE),
            ("Что даёт", "выбрал на пульте не ту модель — дрон не подключится, вместо «полетел с чужими миксами и failsafe»", GR),
            ("Где включается", "ELRS Lua → Model Match: On. Номер — это номер приёмника в настройках модели EdgeTX", OR),
            ("Типичная ловушка", "включил Model Match, а в двух моделях один номер — защита не работает", RD)]
    cards(d, t, rows, ty + 30, gap=18, t0=0.4, step=1.0, hs=34, bs=29)
    return fade(im, t, dur)


def s_rates(t, dur=15):
    im, d = base(); TB(d, "PACKET RATE", 3)
    ty = title(d, "Packet rate: частота против чувствительности")
    x0, y0, w = 330, ty + 40, 520
    for i, (lab, s) in enumerate(RATES):
        aa = ease((t - 0.4 - i * 0.2) / 0.4)
        y = y0 + i * 86
        col = GR if s <= -112 else (OR if s <= -108 else TE)
        bl = (s + 100) / -15 * w
        d.rounded_rectangle([x0, y, x0 + bl * aa, y + 62], radius=10, fill=mix(BG, col, aa * 0.85))
        text(d, (x0 - 20, y + 31), lab, F(30, "Bold"), FG, "rm", aa)
        text(d, (x0 + bl * aa + 14, y + 31), f"{s} дБм", M(26), FG, "lm", aa)
    wrap_text(d, 60, y0 + 10 * 86 + 30, "Чувствительность приёмника из меню ELRS 4.1 (2.4 ГГц). Каждые 6 дБ — примерно вдвое по дальности в свободном пространстве.", F(28, "Medium"), W - 120, MUTED, ease((t - 3.0) / 0.6))
    chip(d, (60, y0 + 10 * 86 + 150), "50 Гц слышит на 11 дБ тише, чем F1000: это почти в 3.5 раза по дальности. F1000 — минимальная задержка для гонок", F(29), OR, ease((t - 5.0) / 0.6))
    return fade(im, t, dur)


def s_tlm(t, dur=12):
    im, d = base(); TB(d, "ТЕЛЕМЕТРИЯ", 4)
    ty = title(d, "Telem ratio: сколько пакетов отдать обратно")
    rows = [("Варианты", "Std · Off · 1:128 … 1:2 · Race", TE),
            ("Что это", "каждый N-й пакет идёт от дрона к пульту: LQ, RSSI, батарея, режим", OR),
            ("Больше телеметрии", "чаще данные, но меньше пакетов управления", RD),
            ("Для MAVLink и Backpack", "нужна плотная телеметрия; для гонки — Race или Off", GR)]
    cards(d, t, rows, ty + 30, gap=18, t0=0.4, step=1.0, hs=34, bs=29)
    return fade(im, t, dur)


def s_choose(t, dur=13):
    im, d = base(); TB(d, "ВЫБОР", 5)
    ty = title(d, "Какой режим под задачу")
    rows = [("Гонка", "F500 / F1000: минимальная задержка, дальность небольшая", RD),
            ("Фристайл", "250Hz или 500Hz: баланс отклика и запаса", OR),
            ("Дальние полёты", "50Hz / 100Hz Full / 150Hz: максимум чувствительности", GR),
            ("Помехи, длинный полёт", "D250 / D500: каждый пакет повторяется — надёжнее при той же частоте управления", TE)]
    y = cards(d, t, rows, ty + 30, gap=18, t0=0.4, step=1.0, hs=34, bs=29)
    chip(d, (60, y + 20), "И связка с Betaflight: feedforward любит частые ровные пакеты (видео про рейты). Медленный канал — больше сглаживания", F(29), MUTED, ease((t - 5.0) / 0.6))
    return fade(im, t, dur)


def s_check(t, dur=11):
    im, d = base(); TB(d, "ПРОВЕРКА", 6)
    ty = title(d, "Перед полётом — 4 проверки")
    items = [("одна фраза и один регион на TX и RX", TE), ("Model Match: номер модели уникален", OR), ("в OSD/пульте видны LQ и RSSI, не просто «есть связь»", GR),
             ("failsafe: выключил пульт — дрон ушёл в нужный режим", RD)]
    for i, (s, col) in enumerate(items):
        aa = ease((t - 0.4 - i * 0.7) / 0.5); y = ty + 40 + i * 160
        d.rounded_rectangle([60, y, W - 60, y + 130], radius=18, fill=mix(BG, PANEL, aa))
        text(d, (100, y + 65), f"{i + 1}", F(48, "Bold"), col, "lm", aa)
        wrap_text(d, 170, y + 32, s, F(32, "SemiBold"), W - 270, FG, aa)
    return fade(im, t, dur)


def s_end(t, dur=6):
    return end_card(t, dur, [("Фраза → MD5 → 6 байт UID", TE), ("Регион одинаковый на обеих сторонах", OR),
                             ("Model Match спасает от чужой модели", GR), ("Packet rate = отклик против дальности", RD),
                             ("Телеметрия съедает пакеты управления", PU)], "чип-тюнинг · блок 2")


SCENES = [("01_hook", s_hook, 7), ("02_uid", s_uid, 13), ("03_domain", s_domain, 13), ("04_match", s_match, 13),
          ("05_rates", s_rates, 15), ("06_tlm", s_tlm, 12), ("07_choose", s_choose, 13), ("08_check", s_check, 11), ("09_end", s_end, 6)]

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    if sys.argv[1:] == ["preview"]:
        preview("v_elrs_inside", f"{here}/out/elrs_prev")
    else:
        render_video("v_elrs_inside", f"{here}/out/elrs", f"{here}/out/C3_ELRS_inside.mp4")
