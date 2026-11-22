"""Stage 6 diagrams for module ap-notify (ArduPilot 4.7 AP_Notify: LEDs, buzzer, DShot beacon).

ap-notify-paths       — event -> device path: flags/events -> AP_Notify devices -> hardware (RGB LEDs of every
                        type, plain board LEDs, ToneAlarm, GPIO buzzer, display). Names as in
                        libraries/AP_Notify/AP_Notify.cpp and AP_HAL_ChibiOS/Util.cpp of Copter-4.7.2.
ap-notify-led-states  — state-colour chart: the twelve sequences of RGBLed.h / RGBLed::get_colour_sequence()
                        in priority order, ten 100 ms steps each (DEFINE_COLOUR_SEQUENCE*). The table below is
                        a transcription of the macros, not of the wiki.
"""
from __future__ import annotations

from svg import ACCENT, INK, MUTED, Box, flow, svg, text

# colours of RGBLed.h: BLACK 0, BLUE 1, GREEN 2, RED 4, YELLOW = RED|GREEN, WHITE = all
K, B, G, R, Y, W = "K", "B", "G", "R", "Y", "W"
FILL = {K: "none", B: "#3b82f6", G: "#22c55e", R: "#ef4444", Y: "#eab308", W: "#f8fafc"}
LETTER = {K: "", B: "С", G: "З", R: "К", Y: "Ж", W: "Б"}


def slow(c): return [c] * 5 + [K] * 5                 # DEFINE_COLOUR_SEQUENCE_SLOW
def failsafe(c): return [Y] * 5 + [c] * 5             # DEFINE_COLOUR_SEQUENCE_FAILSAFE
def solid(c): return [c] * 10                         # DEFINE_COLOUR_SEQUENCE_SOLID
def alternate(a, b): return [a, b] * 5                # DEFINE_COLOUR_SEQUENCE_ALTERNATE


# (label, sequence) in the order RGBLed::get_colour_sequence() tests them
STATES = [
    ("1 инициализация", alternate(R, B)),
    ("2 калибровка, save trim", [R, B, G, R, B, G, R, B, G, K]),
    ("3 протечка (Sub)", failsafe(W)),
    ("4 EKF недостоверен", failsafe(R)),
    ("5 сбой GPS", failsafe(B)),
    ("6 failsafe: радио, АКБ, GCS", failsafe(K)),
    ("7 арм, 3D-фикс и позиция", solid(G)),
    ("8 арм без позиции", solid(B)),
    ("9 дизарм, PreArm не пройден", [Y, Y, K, K, Y, Y, K, K, K, K]),
    ("10 дизарм, готов, DGPS+", alternate(G, K)),
    ("11 дизарм, готов, 3D-фикс", slow(G)),
    ("12 дизарм, готов, нет позиции", slow(B)),
]


def on_time_ms(seq: list[str]) -> int:
    """Milliseconds per 1 s cycle during which the LED is lit (any colour)."""
    return 100 * sum(1 for c in seq if c != K)


def build(D: dict) -> None:
    boxes = [
        Box("src", ["Код прошивки", "арм, failsafe, EKF"], 14, 96, 128, 48, note="флаги и события"),
        Box("ntf", ["AP_Notify", "50 раз в секунду"], 176, 96, 128, 48, accent=True, note="параметры NTF_*"),
        Box("rgb", ["RGBLed", "одна таблица цветов"], 348, 28, 150, 44, accent=True),
        Box("gpio", ["Светодиоды платы", "1–2 штуки, ритм"], 348, 98, 150, 44),
        Box("tone", ["ToneAlarm", "мелодии"], 348, 168, 150, 44, accent=True),
        Box("buz", ["Buzzer", "NTF_BUZZ_PIN"], 348, 238, 150, 44),
        Box("hw1", ["I2C, CAN, NeoPixel,", "ProfiLED, ESC LED"], 548, 28, 158, 44),
        Box("hw3", ["пад BUZZ, DroneCAN,", "писк моторами"], 548, 168, 158, 44),
        Box("hw4", ["активная пищалка", "на ножке GPIO"], 548, 238, 158, 44),
    ]
    links = [
        ("src", "ntf", "", False, "h"),
        ("ntf", "rgb", "", True, "h"), ("ntf", "gpio", "", False, "h"),
        ("ntf", "tone", "", True, "h"), ("ntf", "buz", "", False, "h"),
        ("rgb", "hw1", "", True, "h"), ("tone", "hw3", "", True, "h"), ("buz", "hw4", "", False, "h"),
    ]
    D["ap-notify-paths"] = flow(
        "AP_Notify 4.7: от события до светодиода и пищалки",
        boxes, links, 720, 372,
        notes=[(14, 312, "Флаги общие: RGB-светодиод платы, модуля GPS и лента показывают одно и то же.", "a t"),
               (14, 328, "Писк моторами (NTF_BUZZ_TYPES бит 1), светодиоды ESC (NTF_LED_TYPES бит 11): только в дизарме.", "w t"),
               (14, 344, "Устройства создаются при загрузке: после смены NTF_LED_TYPES, NTF_BUZZ_TYPES — перезагрузка.", "m t"),
               (14, 360, "Экран I2C (NTF_DISPLAY_TYPE) — отдельное устройство, в арме не обновляется.", "m t")])

    x0, y0, cw, ch, lx = 250, 48, 38, 20, 14
    out = [text(lx, 20, "RGBLed.h (Copter-4.7.2): 10 шагов по 100 мс, сверху вниз — порядок проверки условий", "b", "start", 12)]
    for i in range(10):
        out.append(text(x0 + i * cw + cw / 2, y0 - 8, f"{i * 100}", "m t", "middle", 9))
    out.append(text(x0 + 10 * cw + 8, y0 - 8, "мс", "m t", "start", 9))
    for r, (label, seq) in enumerate(STATES):
        y = y0 + r * (ch + 6)
        out.append(text(lx, y + 14, label, "t", "start", 11))
        for i, c in enumerate(seq):
            x = x0 + i * cw
            dash = ' stroke-dasharray="2 3"' if c == K else ""
            out.append(f'<rect x="{x + 2}" y="{y}" width="{cw - 4}" height="{ch}" rx="3" fill="{FILL[c]}" '
                       f'stroke="{MUTED if c == K else INK}" stroke-width="1"{dash}/>')
            if c != K:
                out.append(f'<text x="{x + cw / 2}" y="{y + 14}" text-anchor="middle" '
                           f'style="font-size:10px;font-weight:600;fill:#111">{LETTER[c]}</text>')
        out.append(text(x0 + 10 * cw + 8, y + 14, f"{on_time_ms(seq)} мс", "m t", "start", 10))
    yb = y0 + len(STATES) * (ch + 6) + 12
    out.append(text(lx, yb, "К красный, С синий, З зелёный, Ж жёлтый, Б белый; пунктир — не горит. Справа — свечение за 1 с.", "m t", "start"))
    out.append(text(lx, yb + 15, "Строки 3–6 — и в арме, и в дизарме. Жёлтый 0.5 с — авария; две вспышки по 0.2 с — PreArm.", "a t", "start"))
    out.append(f'<line x1="{x0 + 5 * cw}" y1="{y0 - 4}" x2="{x0 + 5 * cw}" y2="{yb - 14}" stroke="{ACCENT}" stroke-width="1" stroke-dasharray="4 3"/>')
    D["ap-notify-led-states"] = svg(720, yb + 26, "Таблица состояний RGB-светодиода ArduPilot", "".join(out))
