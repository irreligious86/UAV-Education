"""Stage 6 diagrams for module inav-led-pinio-beeper (INAV 9.1.0: io/ledstrip.c, io/piniobox.c, io/beeper.c,
programming/logic_condition.c).

inav-led-pinio-beeper-flow — what drives each output: AUX switch -> mode (permanent ids 47/48/57/58, 15, 13, 60),
                             mission user action -> logic operand only, logic condition -> LED pin PWM (op 52)
                             directly and PINIO only through RC channel override (op 38), firmware events ->
                             LED strip functions and beeper / DShot beacon (disarmed only).
chart-inav-led-budget      — the module's practice step 4: strip current vs LED count at 0.06 A per LED (white)
                             and 0.02 A (single colour channel); line = 0.78 A left on a 2 A BEC after 0.55 A of
                             other 5 V loads with the course rule "BEC rating >= 1.5 x sum" (2 / 1.5 - 0.55).
                             White crosses it at 13 LEDs; 24 LEDs draw 1.44 A.
"""
from __future__ import annotations

from plot import Axis, chart
from svg import Box, flow

I_WHITE = 0.06      # A per LED, el-power-design
I_ONE = 0.02        # A per colour channel, bf-led-buzzer
BEC, K, OTHER = 2.0, 1.5, 0.55


def build(D: dict) -> None:
    boxes = [
        Box("sw", ["Тумблер AUX", "строка aux, шаг 25"], 10, 40, 310, 44),
        Box("wp", ["Миссия: p3 точки, user action 1–4", "операнды логики 6–13"], 350, 40, 190, 44),
        Box("lc", ["Логическое условие", "10 Гц, не в CLI"], 580, 40, 150, 44, accent=True),
        Box("modes", ["BEEPER 13", "BEEPER MUTE 60"], 10, 150, 140, 44),
        Box("user", ["Режим USER1–4", "id 47, 48, 57, 58"], 180, 150, 140, 44, accent=True),
        Box("ovr", ["Оп. 38: подмена канала", "с диапазоном USER"], 370, 150, 170, 44),
        Box("pwm", ["Оп. 52: LED Pin PWM", "0…100 %, иначе стоп"], 580, 150, 150, 44),
        Box("beep", ["Пищалка; моторы DShot", "только в дизарме"], 10, 260, 150, 44, accent=True),
        Box("pinio", ["PINIO 1–4", "pinio_box1..4"], 180, 260, 140, 44, accent=True),
        Box("led", ["Пин LED: лента WS2812", "или ШИМ 24 кГц"], 480, 260, 250, 44, accent=True),
        Box("ev", ["События прошивки: арм, батарея, GPS, failsafe, стики",
                   "24 условия пищалки и функции ленты; LEDS OFF (15) гасит ленту"], 10, 360, 720, 44),
    ]
    links = [
        ("sw", "modes", "", False, "v"),
        ("sw", "user", "", True, "v"),
        ("wp", "lc", "", False, "h"),
        ("lc", "ovr", "", False, "v"),
        ("lc", "pwm", "", True, "v"),
        ("ovr", "user", "", False, "h"),
        ("modes", "beep", "", True, "v"),
        ("user", "pinio", "", True, "v"),
        ("pwm", "led", "", True, "v"),
        ("ev", "beep", "", False, "v"),
        ("ev", "led", "", False, "v"),
    ]
    D["inav-led-pinio-beeper-flow"] = flow(
        "INAV 9.1: что управляет лентой, PINIO и пищалкой",
        boxes, links, 740, 460,
        notes=[(10, 430, "User action миссии сам ничего не включает: это операнд для логики.", "w t"),
               (10, 446, "Прямой операции «логика → PINIO» нет: только подмена канала с диапазоном USER.", "m t")])

    budget = BEC / K - OTHER                       # 0.783 A
    ns = list(range(0, 49))
    D["chart-inav-led-budget"] = chart(
        "Ток ленты и запас BEC 5 В 2 А (прочие нагрузки 0.55 А, правило 1.5×)",
        [dict(name="белый, 0.06 А/шт", xs=ns, ys=[n * I_WHITE for n in ns], cls="d", label_at=40, label_dy=-8),
         dict(name="один канал, 0.02 А/шт", xs=ns, ys=[n * I_ONE for n in ns], cls="a", label_at=26, label_dy=20, label_anchor="start")],
        Axis("число светодиодов", 0, 48, ticks=[0, 8, 13, 16, 24, 32, 40, 48]),
        Axis("ток ленты, А", 0, 3.0, ticks=[0, 0.5, 0.78, 1.0, 1.44, 2.0, 2.5, 3.0]),
        marks=[(13, "13 шт: 0.78 А", "w", 150), (24, "24 шт: 1.44 А", "d", 110)],
        hmarks=[(budget, "", "w")],
        notes=[(70, 254, "запас BEC 0.78 А", "w"), (392, 54, "128 шт на белом — 7.68 А", "m")])
