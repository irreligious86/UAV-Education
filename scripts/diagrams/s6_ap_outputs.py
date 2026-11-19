"""Stage 6 diagrams for module ap-outputs (ArduPilot 4.7 outputs: functions, timer groups, DShot, GPIO).

ap-outputs-pipeline   — the output pipeline: source (mixer / RC / script) -> function -> SRV_Channel (SERVOn_*)
                        -> RCOutput (protocol) -> timer -> pad. Names as in SRV_Channel*.cpp and
                        AP_HAL_ChibiOS/RCOutput.cpp of Copter-4.7.2.
ap-outputs-timer-map  — timer groups of MatekH743 (libraries/AP_HAL_ChibiOS/hwdef/MatekH743/hwdef.dat, lines
                        145-157 of Copter-4.7.2) with the plan of the module's practice step 1: DShot600 motors
                        on outputs 1-4, two 50 Hz servos on 7-8, relay GPIO on 9, NeoPixel on 13; outputs 5-6
                        are lost for PWM because TIM5 is shared with motors 3-4.
"""
from __future__ import annotations

from svg import ACCENT, DANGER, INK, MUTED, WARN, Box, flow, svg, text

# (timer, [outputs]) exactly as in the hwdef PWM(n) lines; GPIO number of output n is 49 + n on this board
GROUPS = [("TIM8", [1, 2]), ("TIM5", [3, 4, 5, 6]), ("TIM4", [7, 8, 9, 10]), ("TIM15", [11, 12]), ("TIM1", [13])]
# practice step 1 plan: output -> (label, kind)
PLAN = {
    1: ("Motor1", "dshot"), 2: ("Motor2", "dshot"), 3: ("Motor3", "dshot"), 4: ("Motor4", "dshot"),
    5: ("нет PWM", "lost"), 6: ("нет PWM", "lost"),
    7: ("захват 28", "pwm"), 8: ("подвес 7", "pwm"), 9: ("GPIO 58", "gpio"), 10: ("свободен", "free"),
    11: ("свободен", "free"), 12: ("свободен", "free"), 13: ("NeoPixel", "led"),
}
MODE = {"TIM8": "DShot600", "TIM5": "DShot600", "TIM4": "PWM 50 Гц", "TIM15": "PWM 50 Гц", "TIM1": "NeoP"}
COLOUR = {"dshot": ACCENT, "lost": DANGER, "pwm": INK, "gpio": WARN, "free": MUTED, "led": WARN}


def lost_outputs(digital: list[int]) -> list[int]:
    """Outputs disabled because they share a timer with a digital (DShot / LED) output."""
    out = []
    for _t, chans in GROUPS:
        if set(chans) & set(digital):
            out += [c for c in chans if c not in digital]
    return out


def build(D: dict) -> None:
    boxes = [
        Box("src", ["Источник", "миксер, RC, Lua"], 14, 34, 122, 48, note="значение функции"),
        Box("fn", ["Функция", "Motor1, Elevator"], 160, 34, 122, 48, accent=True, note="SERVOn_FUNCTION"),
        Box("srv", ["SRV_Channel", "MIN/MAX/TRIM"], 306, 34, 122, 48, note="микросекунды"),
        Box("rc", ["RCOutput", "PWM, DShot, LED"], 452, 34, 122, 48, accent=True, note="протокол, кадр"),
        Box("tim", ["Таймер", "группа выходов"], 598, 34, 108, 48, note="частота, DMA"),
    ]
    links = [("src", "fn", "", False, "h"), ("fn", "srv", "", True, "h"), ("srv", "rc", "", False, "h"), ("rc", "tim", "", True, "h")]
    D["ap-outputs-pipeline"] = flow(
        "ArduPilot 4.7: путь сигнала от функции до пада",
        boxes, links, 720, 186,
        notes=[(14, 122, "На выход: SERVOn_FUNCTION, MIN, MAX, TRIM, REVERSED. Одну функцию можно дать нескольким выходам.", "a t"),
               (14, 138, "На таймер: протокол (MOT_PWM_TYPE, SERVO_BLH_OTYPE, лента) и частота (RC_SPEED, SERVO_RATE).", "m t"),
               (14, 154, "PWM-выход в группе с DShot или лентой отключается: PreArm «… on disabled channel».", "w t"),
               (14, 170, "Выход с функцией −1 (GPIO) исключается из группы при загрузке и таймеру не мешает.", "m t")])

    cw, ch, x0, y0, gap = 46, 40, 20, 62, 14
    out = [text(x0, 20, "MatekH743 (стандартная сборка 4.7.2): таймерные группы и план шага 1", "b", "start", 13)]
    x = x0
    for timer, chans in GROUPS:
        w = cw * len(chans)
        out.append(f'<rect x="{x}" y="{y0 - 20}" width="{w}" height="{ch + 62}" rx="6" fill="none" stroke="{MUTED}" '
                   f'stroke-width="1" stroke-dasharray="4 3"/>')
        out.append(text(x + w / 2, y0 - 26, timer, "b", "middle", 12))
        out.append(text(x + w / 2, y0 + ch + 34, MODE[timer], "a t" if "DShot" in MODE[timer] else "m t", "middle", 10))
        for i, n in enumerate(chans):
            label, kind = PLAN[n]
            cx = x + i * cw
            col = COLOUR[kind]
            dash = ' stroke-dasharray="3 2"' if kind in ("lost", "free") else ""
            out.append(f'<rect x="{cx + 3}" y="{y0}" width="{cw - 6}" height="{ch}" rx="4" fill="none" stroke="{col}" '
                       f'stroke-width="1.5"{dash}/>')
            out.append(text(cx + cw / 2, y0 + 17, str(n), "b", "middle", 13))
            out.append(text(cx + cw / 2, y0 + 32, f"G{49 + n}", "m t", "middle", 9))
        x += w + gap
    # second row: what is connected, drawn as a list to keep labels readable at phone width
    yl = y0 + ch + 62
    rows = [
        ("1–4", "Motor1–4, DShot600: TIM8 и TIM5 целиком в цифровом режиме", "a t"),
        ("5–6", "общий TIM5 с моторами 3 и 4 — PWM-серву сюда нельзя (можно GPIO или ещё два DShot-мотора)", "w t"),
        ("7–8", "сервы 50 Гц: захват (28) и наклон подвеса (7) — TIM4, SERVO_RATE", "t"),
        ("9", "SERVO9_FUNCTION = −1, RELAY1_PIN = 58: ножка исключена из группы TIM4", "t"),
        ("13", "NeoPixel (120): одна на TIM1, никого не отключает", "t"),
        ("10–12", "свободны; лента на 9 или 10 отключила бы сервы на 7 и 8", "m t"),
    ]
    for i, (o, s, cls) in enumerate(rows):
        out.append(text(x0 + 44, yl + i * 16, o, "b", "end", 11))
        out.append(text(x0 + 54, yl + i * 16, s, cls, "start", 11))
    lost = lost_outputs([1, 2, 3, 4])
    yb = yl + len(rows) * 16 + 8
    out.append(text(x0, yb, f"Под номером выхода — номер ножки GPIO (G50…G62). Потеряны для PWM при моторах на 1–4: выходы {lost[0]} и {lost[1]}.",
                    "m t", "start"))
    out.append(text(x0, yb + 15, "В сборке MatekH743-bdshot группы другие: 1–2 TIM3, 3–4 TIM2, 5–6 TIM5, 7–10 TIM4.", "m t", "start"))
    D["ap-outputs-timer-map"] = svg(720, yb + 28, "Таймерные группы MatekH743 и план выходов", "".join(out))
