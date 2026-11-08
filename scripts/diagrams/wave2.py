"""Second infographics wave (Stage 2, iteration 9): one diagram for every module that had none.

build(D, arch) adds entries to the diagram dict; `arch` is build_diagrams._arch (two rows of boxes).
"""
from __future__ import annotations

from svg import Node, sequence, timeline, tree


def L(i, lines, acc=False, col=None):
    return (i, lines, acc) if col is None else (i, lines, acc, col)


def build(D: dict, arch) -> None:
    # ------------------------------------------------------------ ArduPilot
    D["tecs-energy"] = arch("TECS: газ управляет полной энергией, тангаж — её распределением",
        [L("tgt", ["Цели", "h*, V*"]), L("tot", ["Полная энергия", "mgh + ½mV²"], True),
         L("bal", ["Баланс", "потенц. ↔ кинет."], True), L("ac", ["Самолёт"])],
        [L("thr", ["Ошибка полной →", "газ, THR_MIN/MAX"], False, 1), L("pit", ["Ошибка баланса →", "тангаж, SPDWEIGHT"], False, 2)],
        [("tgt", "tot"), ("tot", "bal"), ("bal", "ac"), ("tot", "thr", "", True, "v"), ("bal", "pit", "", True, "v")],
        notes=[(10, 160, "Набор высоты без газа", "m t"), (10, 174, "= потеря скорости", "m t")])

    D["guided-timeout"] = sequence("GUIDED: цель по скорости живёт GUID_TIMEOUT (3 с)",
        ["Companion", "ArduPilot"],
        [(0, 1, "SET_POSITION_TARGET_LOCAL_NED (vx, vy, vz)", True), (1, 1, "выполняет, таймер сброшен"),
         (1, 0, "LOCAL_POSITION_NED, HEARTBEAT", False, True), (0, 1, "та же цель каждые 100–500 мс", True),
         (0, 0, "companion завис / упал"), (1, 1, "3 с без новой цели"), (1, 0, "скорость → 0, висение", False, True)],
        notes=[(0, "type_mask: только скорость"), (3, "≥ 2 Гц — запас к таймауту"), (6, "защита, а не помеха")])

    D["x8-layout"] = arch("X8: четыре луча, на каждом соосная пара",
        [L("bat", ["АКБ 6S Li-Ion"]), L("esc", ["ESC ×8"], True), L("pair", ["4 пары верх/низ", "вращение встречное"], True), L("mix", ["Миксер", "AP_MotorsMatrix"])],
        [L("fail", ["Отказ мотора:", "соосный партнёр"], True, 2), L("hdr", ["MOT_YAW_HEADROOM", "запас на рыскание"], False, 3)],
        [("bat", "esc"), ("esc", "pair"), ("mix", "pair", "", True), ("pair", "fail", "", False, "v"), ("mix", "hdr", "", False, "v")],
        notes=[(10, 150, "Висение ≈ 30–35 % газа", "m t"), (10, 164, "— запас на отказ", "m t")])

    D["log-triage"] = tree("Разбор лога ArduPilot: с чего начать", Node("r", ["Что пошло", "не так?"], [
        ("тряска", Node("v", ["VIBE: X/Y/Z,", "Clip0–2"], leaf=True, accent=True)),
        ("питание", Node("p", ["BAT: Volt, Curr,", "POWR: Vcc"], leaf=True)),
        ("уплыл", Node("n", ["XKF4: SV/SP/SH,", "GPS: NSats, HDop"], leaf=True)),
        ("не держит", Node("c", ["RATE, ATT:", "Des против факта"], leaf=True)),
        ("режим", Node("m", ["MODE, ERR, EV,", "RCIN, MSG"], leaf=True)),
    ]), width=720)

    D["lua-runtime"] = arch("Скриптинг ArduPilot: как исполняется update()",
        [L("sd", ["APM/scripts/", "*.lua"]), L("vm", ["Lua VM", "SCR_HEAP_SIZE"], True), L("up", ["update()", "→ return fn, мс"], True), L("api", ["Привязки", "ahrs, vehicle, gcs"])],
        [L("pc", ["pcall: ошибка", "не роняет скрипт"], True, 2), L("act", ["Режим, цель,", "сообщение, лог"], False, 3)],
        [("sd", "vm"), ("vm", "up"), ("up", "api"), ("up", "pc", "", False, "v"), ("api", "act", "", False, "v")],
        notes=[(10, 150, "SCR_ENABLE=1; скрипт", "m t"), (10, 164, "не заменяет FS_*", "m t")])

    D["mission-alt-frames"] = tree("Высота в миссии: какую систему выбрать", Node("r", ["Рельеф под", "маршрутом?"], [
        ("ровный", Node("rel", ["Relative", "от точки дома"], leaf=True, accent=True)),
        ("перепады", Node("ter", ["Terrain", "над рельефом"], leaf=True, accent=True)),
        ("нужна AMSL", Node("abs", ["Absolute", "над уровнем моря"], leaf=True)),
        ("дом выше", Node("warn", ["Relative на", "склоне опасен"], leaf=True)),
    ]), width=720)

    D["failsafe-map"] = tree("Карта failsafe ArduCopter", Node("r", ["Событие"], [
        ("пульт", Node("rc", ["FS_THR_ENABLE"], [("", Node("rc1", ["RTL / LAND /", "SmartRTL"], leaf=True))])),
        ("GCS", Node("g", ["FS_GCS_ENABLE"], [("", Node("g1", ["RTL / LAND"], leaf=True))])),
        ("батарея", Node("b", ["BATT_FS_LOW_ACT,", "BATT_FS_CRT_ACT"], [("", Node("b1", ["RTL → LAND"], leaf=True))], accent=True)),
        ("EKF", Node("e", ["FS_EKF_ACTION"], [("", Node("e1", ["LAND / AltHold"], leaf=True))])),
        ("геозона", Node("f", ["FENCE_ACTION"], [("", Node("f1", ["RTL / Brake", "/ LAND"], leaf=True))])),
        ("вибрации", Node("vb", ["FS_VIBE_ENABLE"], [("", Node("vb1", ["другой алгоритм", "высоты"], leaf=True))])),
    ]), width=720, box_w=112)

    D["sitl-arch"] = arch("SITL: тот же код автопилота, физика вместо железа",
        [L("phys", ["Модель физики", "SIM_* параметры"], True), L("ap", ["ArduCopter", "тот же код"], True), L("mp", ["MAVProxy", "tcp:5760"]), L("gcs", ["GCS", "udp:14550"])],
        [L("py", ["pymavlink-скрипт", "udp:14551"], True, 2), L("log", ["logs/*.BIN", "как в полёте"], False, 1)],
        [("phys", "ap"), ("ap", "mp"), ("mp", "gcs"), ("mp", "py", "", False, "v"), ("ap", "log", "", False, "v")],
        notes=[(10, 150, "SITL врёт:", "m t"), (10, 164, "вибрации, ветер, радио", "m t")])

    D["ap-tuning-order"] = arch("Порядок тюнинга ArduPilot",
        [L("base", ["Базовые", "параметры"]), L("notch", ["Harmonic notch", "INS_HNTCH_*"], True), L("man", ["QuikTune", "или вручную"]),
         L("at", ["AUTOTUNE"], True), L("sh", ["Input shaping", "ATC_INPUT_TC"])],
        [L("log", ["Лог после шага:", "VIBE, PIDR, RATE"], True, 2)],
        [("base", "notch"), ("notch", "man"), ("man", "at"), ("at", "sh"), ("log", "man", "", False, "v")])

    # ------------------------------------------------------------ Betaflight
    D["blackbox-chain"] = arch("Blackbox: где в контуре берутся поля лога",
        [L("g", ["Гироскоп"]), L("f", ["Фильтры"], True), L("pid", ["PID"], True), L("m", ["Миксер → ESC"]), L("st", ["Flash / SD", ".bbl"])],
        [L("u", ["gyroUnfilt"], False, 0), L("a", ["gyroADC"], False, 1), L("t", ["axisP/I/D/F"], False, 2), L("mo", ["motor, eRPM"], False, 3), L("dec", ["blackbox_decode", "→ Explorer"], True, 4)],
        [("g", "f"), ("f", "pid"), ("pid", "m"), ("m", "st"), ("g", "u", "", False, "v"), ("f", "a", "", False, "v"), ("pid", "t", "", False, "v"), ("m", "mo", "", False, "v"), ("st", "dec", "", True, "v")])

    D["bf-cli-session"] = sequence("Сессия CLI Betaflight по serial",
        ["Скрипт", "FC"],
        [(0, 1, "#  (вход в CLI)", True), (1, 0, "приглашение «# »", False, True), (0, 1, "diff all"), (1, 0, "текст конфига …  # ", False, True),
         (0, 1, "set gyro_lpf1_static_hz = 250"), (1, 0, "значение могло быть исправлено молча", False, True),
         (0, 1, "get … → сверка", True), (0, 1, "save"), (1, 1, "перезагрузка: порт может смениться")],
        notes=[(0, "ждать приглашение, не время"), (5, "всегда перечитывать"), (8, "искать порт заново по VID/PID")])

    D["bf-resource-remap"] = arch("Ремаппинг мотора на другой пад",
        [L("pad", ["Свободный пад", "LED / PPM / SERVO"]), L("tim", ["Таймер и DMA", "timer, dma show"], True), L("res", ["resource MOTOR 2", "<пин>"], True), L("sv", ["save →", "вкладка Motors"])],
        [L("cf", ["Конфликт:", "другой пад"], False, 1)],
        [("pad", "tim"), ("tim", "res"), ("res", "sv"), ("tim", "cf", "", False, "v")],
        notes=[(10, 150, "Сначала MOTOR 2 NONE,", "m t"), (10, 164, "потом новый пин", "m t")])

    D["fw-build-paths"] = tree("Своя сборка прошивки: какой путь", Node("r", ["Что нужно", "поменять?"], [
        ("опции BF", Node("cb", ["Cloud Build:", "драйверы, протоколы"], leaf=True, accent=True)),
        ("код BF", Node("lb", ["Локальная сборка", "make CONFIG=…"], leaf=True)),
        ("опции AP", Node("cs", ["custom.ardupilot.org", "набор функций"], leaf=True, accent=True)),
        ("код AP", Node("waf", ["./waf configure", "--board X; copter"], leaf=True)),
    ]), width=720)

    D["bf-setup-map"] = arch("Первая настройка Betaflight: порядок вкладок",
        [L("bk", ["Резерв", "diff all"], True), L("pt", ["Ports", "UART"]), L("rx", ["Receiver", "протокол, каналы"]), L("md", ["Modes", "ARM, режимы"]), L("mt", ["Motors", "без пропов!"], True)],
        [L("pid", ["PID и фильтры", "по логу"], False, 3), L("osd", ["OSD", "напряжение, RSSI"], False, 4)],
        [("bk", "pt"), ("pt", "rx"), ("rx", "md"), ("md", "mt"), ("mt", "osd", "", False, "v"), ("osd", "pid", "", False, "h")])

    D["bf-modes-layout"] = tree("Раскладка тумблеров: пример", Node("r", ["AUX-каналы"], [
        ("AUX1", Node("a1", ["ARM", "(+ PREARM)"], leaf=True, accent=True)),
        ("AUX2", Node("a2", ["ANGLE / HORIZON", "/ ACRO"], leaf=True)),
        ("AUX3", Node("a3", ["BEEPER", "поиск в траве"], leaf=True)),
        ("AUX4", Node("a4", ["FLIP OVER", "AFTER CRASH"], leaf=True)),
    ]), width=720)

    D["bf-pid-terms"] = arch("PID в Betaflight: откуда каждое слагаемое",
        [L("sp", ["Setpoint", "rates"]), L("err", ["Ошибка", "setpoint − gyro"], True), L("sum", ["pidSum"], True), L("mix", ["Миксер"])],
        [L("ff", ["FF: d(setpoint)/dt"], False), L("p", ["P · ошибка"], False), L("i", ["I + iterm_relax"], False), L("d", ["D по gyro, d_min"], False)],
        [("sp", "err"), ("err", "sum"), ("sum", "mix"), ("sp", "ff", "", False, "v"), ("err", "p", "", False, "v"), ("i", "sum", "", False, "v"), ("d", "sum", "", False, "v")])

    D["bf-tuning-loop"] = arch("Тюнинг по данным: один шаг за раз",
        [L("flt", ["Фильтры", "сначала"], True), L("sl", ["Слайдеры", "одно изменение"]), L("fl", ["Полёт по", "программе"]), L("m", ["Метрики", "из лога"], True), L("dec", ["Решение"])],
        [L("rb", ["Хуже → откат", "к прошлому diff"], False, 4)],
        [("flt", "sl"), ("sl", "fl"), ("fl", "m"), ("m", "dec"), ("dec", "rb", "", False, "v")],
        notes=[(10, 150, "Лучше → следующий шаг", "m t"), (10, 164, "снова со слайдеров", "m t")])

    D["bf-uart-plan"] = arch("F405: пять устройств на четыре UART",
        [L("u1", ["UART1", "CRSF (ELRS)"], True), L("u2", ["UART2", "GPS"], True), L("u3", ["UART3 TX", "SmartAudio"]), L("u4", ["UART4 RX", "ESC Sensor"])],
        [L("ss", ["SoftSerial 11", "RunCam (LED-пад)"], False, 3)],
        [("u4", "ss", "некритичное", False, "v")],
        notes=[(10, 150, "Порядок: полнодуплексные →", "m t"), (10, 164, "однопроводные → softserial", "m t")])

    D["rpm-filter-chain"] = arch("RPM-фильтр: от eRPM до notch на каждом моторе",
        [L("esc", ["ESC", "bidir DShot"]), L("rpm", ["eRPM ÷ полюсные", "пары → об/мин"], True), L("hz", ["f = RPM/60", "и 2f, 3f"], True), L("n", ["Notch: 4 мотора", "× 3 гармоники"], True), L("g", ["Чистый gyro", "→ D можно выше"])],
        [L("min", ["…_min_hz:", "нижняя граница"], False, 3), L("w", ["…_weights:", "глубина"], False, 4)],
        [("esc", "rpm"), ("rpm", "hz"), ("hz", "n"), ("n", "g"), ("min", "n", "", False, "v")],
        notes=[(10, 150, "10\": f на висении 50–100 Гц —", "m t"), (10, 164, "граница 100 Гц режет мимо", "m t")])
