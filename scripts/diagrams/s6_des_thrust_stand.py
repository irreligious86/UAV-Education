"""Stage 6 diagrams for des-thrust-stand: g/W vs thrust (stand vs datasheet), stand signal chain.

Numbers come from the module's worked example: T-Motor MN4006 KV380 + 15x5 CF at 24 V (manufacturer
table, store.tmotor.com) and the processed synthetic stand log (gen_stand_data.py seed 42 ->
process_stand.py output pasted in the module, step 4).
"""
from __future__ import annotations

from plot import Axis, chart
from svg import Box, flow

# datasheet 15x5 @ 24 V: thrust g, electric power W
DS = [(805, 74), (959, 98), (1093, 115), (1236, 139), (1561, 199), (1823, 257), (2228, 360)]
# stand (module step 4): thrust g, g/W
STAND = [(780.7, 10.03), (931.6, 9.05), (1058.3, 8.79), (1198.2, 8.24), (1515.7, 7.30), (1768.6, 6.62), (2161.9, 5.79)]


def build(D: dict) -> None:
    D["chart-stand-gpw"] = chart(
        "Удельная тяга г/Вт: стенд против таблицы T-Motor (MN4006 KV380, 15×5, 24 В)",
        [dict(name="", xs=[t for t, _ in DS], ys=[t / p for t, p in DS], cls="a"),
         dict(name="", xs=[t for t, _ in DS], ys=[t / p for t, p in DS], cls="a", dots=True),
         dict(name="", xs=[t for t, _ in STAND], ys=[g for _, g in STAND], cls="w", dash=True),
         dict(name="", xs=[t for t, _ in STAND], ys=[g for _, g in STAND], cls="w", dots=True)],
        Axis("тяга, г", 700, 2300), Axis("г/Вт", 5, 11.5),
        legend=[("таблица производителя", "a", False), ("стенд: на 8–9 % ниже", "w", True)], legend_at=(80, 272),
        notes=[(330, 70, "C_T стенда 0.080 = C_T таблицы: проп и тяга в норме;", "m"),
               (330, 86, "г/Вт ниже из-за тока (+5 %): виноват ESC/провода.", "m"),
               (330, 102, "U(k=2) по г/Вт ≈ ±1.3 % — разница не шум.", "m")])

    D["stand-signal-chain"] = flow(
        "Тяговый стенд: датчики → ESP32 → CSV → обработка",
        [Box("cell", ["Тензодатчик 5 кг", "1.0 мВ/В, мост"], 10, 20, 150, accent=True),
         Box("hx", ["HX711, 24 бит", "×128, 10 Гц"], 190, 20, 150, accent=True),
         Box("shunt", ["Шунт 2 мОм", "в минусе АКБ"], 10, 100, 150),
         Box("ina", ["INA226, I²C", "1.25 мВ / 1.25 мА"], 190, 100, 150),
         Box("mark", ["Метка на колоколе", "мотора"], 10, 180, 150),
         Box("tach", ["Оптодатчик", "импульс/оборот"], 190, 180, 150),
         Box("esp", ["ESP32", "чтение 10 Гц,", "лимит 16 А,", "таймаут 0.5 с"], 380, 80, 140, 80, accent=True),
         Box("esc", ["ESC → мотор", "PWM 1000–2000 мкс"], 560, 20, 150),
         Box("pc", ["ПК: CSV →", "г/Вт, C_T, U"], 560, 150, 150)],
        [("cell", "hx", "мВ"), ("hx", "esp", "", True), ("shunt", "ina", "мВ"), ("ina", "esp"),
         ("mark", "tach"), ("tach", "esp"), ("esp", "esc", "газ", True), ("esp", "pc", "USB")],
        720, 250, notes=[(380, 200, "ПК шлёт команду ≥ 2 Гц;", "m t", "start"),
                         (380, 214, "молчит — газ 0.", "m t", "start")])
