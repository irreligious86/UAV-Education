"""Stage 6 diagrams for px4-outputs-servos.

1. px4-outputs-pipeline — who produces an output value in PX4 1.18 (same chain as 1.17) and in which order
   (control_allocator -> actuator_motors / actuator_servos -> mixer_module -> driver -> timer).
2. px4-outputs-timers-v6x — timer groups of px4/fmu-v6x (boards/px4/fmu-v6x/src/timer_config.cpp,
   v1.17.0, lines 59-77; unchanged in v1.18.0) and of its IO processor (boards/px4/io-v2/src/timer_config.cpp, lines 36-51),
   with the reference plan from the module's practice step 1 written under each group.
"""
from __future__ import annotations

from svg import Box, flow

# (timer, outputs, DShot-capable = the io_timers line has DMA, TIM parameter, plan from practice step 1)
FMU_GROUPS = [
    ("TIM5", "AUX1 AUX2 AUX3 AUX4", True, "PWM_AUX_TIM0 = −3", "Motor 1–4, DShot600"),
    ("TIM4", "AUX5 AUX6", True, "PWM_AUX_TIM1 = 50", "Servo 1, Servo 2"),
    ("TIM12", "AUX7 AUX8", False, "PWM_AUX_TIM2", "Trigger; AUX8 пуст"),
    ("TIM1", "CAP1", False, "PWM_AUX_TIM3", "не занят"),
]
IO_GROUPS = [
    ("TIM2", "MAIN1 MAIN2", "PWM_MAIN_TIM0 = 50", "Servo 3, 50 Гц"),
    ("TIM4", "MAIN3 MAIN4", "PWM_MAIN_TIM1", "не занят"),
    ("TIM3", "MAIN5 MAIN6 MAIN7 MAIN8", "PWM_MAIN_TIM2", "не занят"),
]


def build(D: dict) -> None:
    # ---- 1. pipeline -------------------------------------------------------------------------
    boxes = [
        Box("ctl", ["Контроллеры:", "момент, тяга"], 12, 44, 100, 46),
        Box("ca", ["control_allocator", "CA_*"], 130, 44, 118, 46, accent=True),
        Box("am", ["actuator_motors", "0…1, NaN = стоп"], 268, 30, 122, 36),
        Box("as", ["actuator_servos", "−1…+1"], 268, 76, 122, 36),
        Box("mm", ["mixer_module", "FUNC, MIN/MAX, REV"], 412, 44, 160, 46, accent=True),
        Box("drv", ["pwm_out, dshot,", "px4io"], 596, 44, 112, 46),
        Box("oth", ["Команды и RC:", "DO_SET_ACTUATOR,", "RC AUX, gear, gripper"], 250, 150, 170, 56),
        Box("arm", ["actuator_armed:", "armed, prearmed,", "kill, termination"], 438, 150, 134, 56),
        Box("tim", ["Таймер MCU", "→ пин выхода"], 596, 150, 112, 56),
    ]
    links = [
        ("ctl", "ca"), ("ca", "am"), ("ca", "as"), ("am", "mm"), ("as", "mm"),
        ("mm", "drv", "", True), ("oth", "mm", "", False, "v"), ("arm", "mm", "", False, "v"),
        ("drv", "tim", "", False, "v"),
    ]
    D["px4-outputs-pipeline"] = flow(
        "PX4 1.18: путь значения от контроллера до пина", boxes, links, 720, 262,
        notes=[
            (12, 232, "mixer_module работает внутри каждого драйвера выходов: функция выхода выбирает источник,", "m t"),
            (12, 247, "MIN/MAX/CENT/REV переводят −1…+1 в мкс (DShot: 1…1999); armed-флаги решают — значение, DIS или FAIL.", "m t"),
        ])

    # ---- 2. timer groups of px4/fmu-v6x ------------------------------------------------------
    tb = []
    x = 12
    widths = [224, 150, 150, 148]
    for (tim, outs, dshot, par, plan), w in zip(FMU_GROUPS, widths):
        tb.append(Box("f" + tim, [tim + (" · DMA" if dshot else " · без DMA"), outs, par], x, 52, w, 58,
                      accent=dshot, note=plan))
        x += w + 12
    x = 12
    for (tim, outs, par, plan), w in zip(IO_GROUPS, [224, 224, 236]):
        tb.append(Box("i" + tim, [tim + " · IO", outs, par], x, 178, w, 58, note=plan))
        x += w + 12
    D["px4-outputs-timers-v6x"] = flow(
        "px4/fmu-v6x: группы таймеров FMU (AUX) и IO (MAIN)", tb, [], 720, 292,
        notes=[
            (12, 42, "FMU — PWM_AUX_*: DShot только там, где у таймера есть DMA (выделено)", "m t"),
            (12, 168, "IO — PWM_MAIN_*: только PWM и OneShot, Camera Trigger назначить нельзя", "m t"),
            (12, 272, "Под группой — план из шага 1: 4 мотора DShot600, 3 сервы 50 Гц, триггер камеры.", "m t"),
            (12, 286, "Одна группа — один протокол и одна частота: серва в группе DShot работать не будет.", "m t"),
        ])
