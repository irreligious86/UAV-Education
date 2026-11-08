"""Second infographics wave (Stage 2, iteration 9): one diagram for every module that had none.

build(D, arch) adds entries to the diagram dict; `arch` is build_diagrams._arch (two rows of boxes).
"""
from __future__ import annotations

from svg import Box, Node, flow, sequence, timeline, tree


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


def build2(D: dict, arch) -> None:
    # ------------------------------------------------------------ companion / engineering
    D["esp32-roles"] = tree("Три роли ESP32 в курсе", Node("r", ["ESP32"], [
        ("мост", Node("br", ["UART ↔ Wi-Fi/BLE", "MAVLink к телефону"], leaf=True)),
        ("датчик", Node("cmp", ["Компонент MAVLink", "HEARTBEAT + данные"], leaf=True, accent=True)),
        ("пульт", Node("tx", ["Компаньон TX16S", "CRSF с порта AUX"], leaf=True)),
    ]), width=720)

    D["fc-loop-125us"] = timeline("Один цикл 8 кГц (125 мкс): кто занимает процессор",
        [("SPI DMA", [(0, 8, "гиро", True)]), ("Фильтры", [(8, 30, "RPM, notch, LPF")]), ("PID+миксер", [(30, 44, "")]),
         ("DShot DMA", [(44, 71, "кадр 27 мкс", True)]), ("ISR UART", [(52, 55, "байт RX")]), ("Остаток", [(71, 125, "OSD, телеметрия, blackbox")])],
        125, unit="мкс", marks=[(0, "прерывание гиро"), (125, "")])

    D["config-ci"] = arch("Конфиги как код: путь изменения",
        [L("dump", ["Снять конфиг", "diff all / param"]), L("git", ["git: ветка", "+ PR"]), L("lint", ["Инварианты", "и линтер"], True), L("sitl", ["SITL-автотест"], True), L("rel", ["Релиз-тег", "и откат"])],
        [L("rev", ["Ревью: человек", "читает diff"], False, 1), L("red", ["Красное —", "нет слияния"], False, 3)],
        [("dump", "git"), ("git", "lint"), ("lint", "sitl"), ("sitl", "rel"), ("git", "rev", "", False, "v"), ("sitl", "red", "", False, "v")])

    D["v-model"] = arch("V-модель: каждому уровню требований — свой уровень проверки",
        [L("req", ["Требования", "к системе"], True), L("arc", ["Архитектура", "интерфейсы"]), L("cmp", ["Компоненты"]), L("imp", ["Реализация"])],
        [L("val", ["Валидация", "в поле"], True, 0), L("sys", ["Системные", "тесты, SITL"], False, 1), L("int", ["Интеграция"], False, 2), L("unit", ["Модульные", "тесты"], False, 3)],
        [("req", "arc"), ("arc", "cmp"), ("cmp", "imp"), ("imp", "unit", "", False, "v"), ("unit", "int"), ("int", "sys"), ("sys", "val")])

    D["mav-component-seq"] = sequence("Свой компонент MAVLink: обязательный минимум",
        ["Компонент", "Автопилот"],
        [(0, 1, "HEARTBEAT 1 Гц (свой compid)", True), (1, 0, "HEARTBEAT", False, True), (0, 1, "DISTANCE_SENSOR 10–20 Гц", True),
         (1, 0, "PARAM_REQUEST_LIST"), (0, 1, "PARAM_VALUE × N", False, True), (1, 0, "COMMAND_LONG"), (0, 1, "COMMAND_ACK", False, True)],
        notes=[(0, "без него компонента нет"), (2, "заполнить min/max, ориентацию"), (6, "на каждую команду — ответ")])

    D["mav-sdk-layers"] = arch("Библиотеки над MAVLink: уровень абстракции",
        [L("app", ["Ваше приложение"]), L("lib", ["Библиотека"], True), L("mav", ["MAVLink", "UDP / serial"]), L("fc", ["Автопилот"])],
        [L("py", ["pymavlink:", "сообщения как есть"]), L("sdk", ["MAVSDK: действия,", "async, Offboard"], True), L("ros", ["MAVROS:", "топики ROS"])],
        [("app", "lib"), ("lib", "mav"), ("mav", "fc")],
        notes=[])

    D["glass-to-glass"] = timeline("Задержка «стекло → стекло» видеопотока (типично, 30 кадр/с)",
        [("Экспозиция", [(0, 16, "до 33 мс")]), ("Считывание", [(16, 30, "")]), ("ISP + кодер", [(30, 55, "H.264", True)]),
         ("Сеть", [(55, 85, "Wi-Fi / 4G", True)]), ("Декодер", [(85, 100, "")]), ("Экран", [(100, 120, "vsync")])],
        120, marks=[(0, "свет на сенсоре"), (120, "")])

    D["cv-pipeline"] = arch("Конвейер зрения на борту",
        [L("cap", ["Захват", "камера"]), L("pre", ["Препроцессинг", "ресайз, норма"]), L("det", ["Детектор", "5–10 Гц"], True), L("trk", ["Трекер", "частота камеры"], True), L("out", ["Цель", "→ управление"])],
        [L("met", ["Метрики:", "precision, recall"], False, 2), L("lat", ["Задержка кадра", "p99 в бюджете"], False, 4)],
        [("cap", "pre"), ("pre", "det"), ("det", "trk"), ("trk", "out"), ("det", "met", "", False, "v"), ("out", "lat", "", False, "v")])

    D["tracking-guards"] = tree("Слежение: обязательные защиты", Node("r", ["Условие"], [
        ("цель потеряна", Node("l", ["> 1 с → висеть,", "скорость 0"], leaf=True, accent=True)),
        ("низкая увер.", Node("c", ["Не управлять", "по этой детекции"], leaf=True)),
        ("слишком близко", Node("d", ["Мин. дистанция", "→ стоп"], leaf=True)),
        ("граница", Node("f", ["Геозона и высота", "— у автопилота"], leaf=True)),
        ("оператор", Node("o", ["Смена режима", "с пульта — сразу"], leaf=True, accent=True)),
    ]), width=780)

    D["visual-nav-levels"] = tree("Визуальная навигация: три уровня", Node("r", ["Что даёт", "камера?"], [
        ("скорость", Node("of", ["Оптический поток", "+ дальномер"], [("", Node("of1", ["OPTICAL_FLOW", "EK3_SRC*_VELXY=5"], leaf=True))])),
        ("поза", Node("vio", ["VIO", "камера + IMU"], [("", Node("vio1", ["ODOMETRY /", "VISION_POSITION_*"], leaf=True))], accent=True)),
        ("поза + карта", Node("sl", ["SLAM", "замыкание петель"], [("", Node("sl1", ["тот же вход,", "меньше дрейф"], leaf=True))])),
    ]), width=720)

    # ------------------------------------------------------------ electronics & RF
    D["chemistry-choice"] = tree("Какая химия под задачу", Node("r", ["Что важнее?"], [
        ("ток", Node("lp", ["LiPo", "фристайл, рывки"], leaf=True)),
        ("энергия", Node("li", ["Li-Ion", "крейсер, long range"], leaf=True, accent=True)),
        ("ресурс", Node("lf", ["LiFePO4", "наземка, станции"], leaf=True)),
    ]), width=720)

    D["emi-paths"] = arch("Три пути помехи: источник → путь → жертва",
        [L("src", ["Источники", "ESC, buck, VTX"]), L("mag", ["Магнитное поле", "тока, 1/r"], True), L("rad", ["Излучение", "фронтов"], True), L("con", ["Кондуктивные", "по питанию/земле"], True)],
        [L("v1", ["Компас"], False, 1), L("v2", ["GPS, приёмник"], False, 2), L("v3", ["RX, видео", "полосы"], False, 3)],
        [("src", "mag"), ("mag", "v1", "", False, "v"), ("rad", "v2", "", False, "v"), ("con", "v3", "", False, "v")],
        notes=[(10, 150, "60 А на 5 см: 240 мкТл", "m t"), (10, 164, "≈ 5 полей Земли", "m t")])

    D["measure-tools"] = tree("Каким прибором смотреть", Node("r", ["Что нужно", "увидеть?"], [
        ("U, I, R", Node("mm", ["Мультиметр", "постоянные значения"], leaf=True)),
        ("форму", Node("osc", ["Осциллограф", "пульсации, DShot"], leaf=True, accent=True)),
        ("протокол", Node("la", ["Логический анализатор", "UART, I2C, SPI"], leaf=True)),
    ]), width=720)

    D["redundancy-schemes"] = tree("Отказ одного мотора: что переживает схема", Node("r", ["Схема"], [
        ("квад", Node("q", ["Нет резерва", "падение"], leaf=True)),
        ("гекса", Node("h", ["Держит высоту,", "yaw плохо"], leaf=True)),
        ("X8", Node("x", ["Партнёр + пара:", "тяга и момент"], leaf=True, accent=True)),
        ("окто", Node("o", ["Переживает и", "два отказа"], leaf=True)),
        ("VTOL", Node("v", ["Висение — как", "квад"], leaf=True)),
    ]), width=720)

    D["wiring-chain"] = arch("Надёжное соединение: от пайки до проверки",
        [L("prep", ["Подготовка", "зачистка, флюс"]), L("sol", ["Пайка", "жало, 2–3 с"], True), L("rel", ["Разгрузка", "термоусадка"]), L("har", ["Жгут", "крепление"]), L("chk", ["Проверка", "под током"], True)],
        [L("pull", ["Тянуть, прозвон,", "падение U"], False, 4)],
        [("prep", "sol"), ("sol", "rel"), ("rel", "har"), ("har", "chk"), ("chk", "pull", "", False, "v")])

    D["polarization-loss"] = tree("Потери на поляризации пары антенн", Node("r", ["Пара антенн"], [
        ("лин. ∥ лин.", Node("a", ["0 дБ"], leaf=True, accent=True)),
        ("лин. ⊥ лин.", Node("b", ["−20 дБ", "и хуже"], leaf=True)),
        ("лин. ↔ круг.", Node("c", ["−3 дБ", "при любом крене"], leaf=True)),
        ("RHCP ↔ RHCP", Node("d", ["0 дБ"], leaf=True, accent=True)),
        ("RHCP ↔ LHCP", Node("e", ["−20 дБ", "и хуже"], leaf=True)),
    ]), width=720)

    D["link-budget-chain"] = arch("Бюджет радиолинка: ELRS 2.4 ГГц, 250 мВт, 10 км",
        [L("pt", ["Pпд", "24 дБм"]), L("g", ["+ Gпд + Gпр", "+2 + 0"]), L("loss", ["− потери", "−1 −3"]), L("fspl", ["− FSPL 10 км", "−120 дБ"], True), L("pr", ["Pпр", "−98 дБм"], True)],
        [L("s", ["S(250 Гц)", "−108 дБм"], False, 3), L("m", ["Запас", "10 дБ"], True, 4)],
        [("pt", "g"), ("g", "loss"), ("loss", "fspl"), ("fspl", "pr"), ("pr", "m", "", True, "v"), ("s", "m")],
        notes=[(10, 150, "+6 дБ = удвоить дальность", "m t")])

    # ------------------------------------------------------------ estimation
    D["complementary-filter"] = arch("Комплементарный фильтр: гироскоп для быстрого, акселерометр для медленного",
        [L("gyr", ["Гироскоп ω"]), L("int", ["∫ ω dt", "дрейфует"]), L("hp", ["× α", "(≈0.98)"], True), L("sum", ["Угол"], True)],
        [L("acc", ["Акселерометр"], False, 0), L("ang", ["atan2 по g", "шумит при манёвре"], False, 1), L("lp", ["× (1 − α)"], True, 2)],
        [("gyr", "int"), ("int", "hp"), ("hp", "sum"), ("acc", "ang"), ("ang", "lp"), ("lp", "sum", "", True, "h")])

    D["rtk-chain"] = arch("GNSS и RTK: откуда сантиметры",
        [L("sat", ["Спутники", "GPS/GLO/GAL/BDS"]), L("rov", ["Приёмник борта", "псевдодальности"]), L("sol", ["Решение", "2–5 м"]), L("rtk", ["RTK fix", "1–3 см"], True)],
        [L("base", ["База на известной", "точке"], False, 0), L("rtcm", ["RTCM-поправки", "радио / NTRIP"], True, 1)],
        [("sat", "rov"), ("rov", "sol"), ("sol", "rtk"), ("base", "rtcm"), ("rtcm", "rov", "", True, "v")])

    D["imu-error-model"] = arch("Модель ошибок MEMS-датчика",
        [L("tru", ["Истинное", "значение"]), L("sc", ["× масштаб,", "перекос осей"]), L("b", ["+ смещение", "дрейф, t°"], True), L("n", ["+ шум", "+ вибрации"], True), L("m", ["Измерение", "(клиппинг)"])],
        [L("cal", ["Калибровка:", "6 положений, t°"], False, 1), L("est", ["EKF оценивает", "bias в полёте"], False, 2)],
        [("tru", "sc"), ("sc", "b"), ("b", "n"), ("n", "m"), ("cal", "sc", "", False, "v"), ("est", "b", "", False, "v")])

    D["degradation-signatures"] = tree("Деградация навигации: отпечаток в логе", Node("r", ["Что видно?"], [
        ("NSats ↓, HAcc ↑", Node("j", ["Помеха или", "закрытое небо"], leaf=True)),
        ("HAcc скачет", Node("mp", ["Многолучёвость"], leaf=True)),
        ("fix хороший, SP ↑", Node("sp", ["Подмена:", "источники спорят"], leaf=True, accent=True)),
        ("SM > 1", Node("mg", ["Помеха компасу"], leaf=True)),
    ]), width=720)


def build3(D: dict, arch) -> None:
    # ------------------------------------------------------------ foundation
    D["traceability"] = arch("Трассируемость: от требования до записи в журнале",
        [L("req", ["Требование", "измеримое"], True), L("arc", ["Архитектура", "кто отвечает"]), L("tst", ["Тест", "как проверено"], True), L("doc", ["Документ", "и журнал"])],
        [L("chg", ["Изменение →", "какие тесты снова"], False, 2)],
        [("req", "arc"), ("arc", "tst"), ("tst", "doc"), ("tst", "chg", "", False, "v")],
        notes=[(10, 150, "У каждого требования —", "m t"), (10, 164, "тест, у теста — требование", "m t")])

    D["thrust-sag-chain"] = arch("От тяги к просадке",
        [L("t", ["Тяга ↑"]), L("i", ["Ток I ↑"], True), L("dv", ["Просадка", "ΔU = I · Rвн"], True), L("u", ["U под", "нагрузкой ↓"]), L("p", ["Мощность", "P = U · I"])],
        [L("e", ["Энергия, Вт·ч", "= В × А·ч"], False, 4)],
        [("t", "i"), ("i", "dv"), ("dv", "u"), ("u", "p"), ("p", "e", "", False, "v")],
        notes=[(10, 150, "Rвн растёт на холоде", "m t"), (10, 164, "и со старением", "m t")])

    D["vibration-path"] = arch("Путь вибраций: от пропеллера до контура",
        [L("src", ["Моторы, пропы", "f = RPM/60"]), L("frm", ["Рама", "резонанс"], True), L("mnt", ["Крепление FC", "демпфер"]), L("gyr", ["Гироскоп", "шум, клиппинг"], True), L("ctl", ["Контур", "D-term, моторы"])],
        [L("bal", ["Баланс пропов,", "затяжка"], False, 0), L("alias", ["Алиасинг выше", "Найквиста"], False, 3)],
        [("src", "frm"), ("frm", "mnt"), ("mnt", "gyr"), ("gyr", "ctl"), ("bal", "src", "", False, "v"), ("gyr", "alias", "", False, "v")])

    D["forces-moments"] = arch("Уравнения движения коптера: силы и моменты",
        [L("t", ["Тяга ΣTᵢ", "по оси тела"]), L("g", ["Вес m·g"]), L("d", ["Сопротивление", "~ V²"]), L("ma", ["m · a = ΣF"], True)],
        [L("m", ["Моменты:", "ΔT·плечо, yaw"], False, 1), L("jw", ["J · ω̇ = ΣM"], True, 3)],
        [("t", "g"), ("g", "d"), ("d", "ma"), ("m", "jw")],
        notes=[(10, 150, "Меньше J — резче", "m t"), (10, 164, "отклик по осям", "m t")])

    D["flight-time-chain"] = arch("Честное время полёта",
        [L("c", ["Ёмкость", "А·ч"]), L("u", ["× 0.8", "не в ноль"], True), L("i", ["÷ средний ток", "висение + манёвры"], True), L("t", ["× 60", "= минуты"])],
        [L("corr", ["Поправки: холод,", "старение, ветер"], False, 2)],
        [("c", "u"), ("u", "i"), ("i", "t"), ("corr", "i", "", False, "v")])

    D["airspace-check"] = tree("Можно ли лететь здесь?", Node("r", ["Зона на", "официальной карте"], [
        ("запретная", Node("n", ["Нет"], leaf=True)),
        ("ограниченная", Node("p", ["Разрешение", "заранее"], leaf=True, accent=True)),
        ("открытая", Node("o", ["Правила категории:", "высота, VLOS, масса"], leaf=True)),
        ("частоты", Node("f", ["Разрешённые", "диапазоны и мощность"], leaf=True)),
    ]), width=720)

    D["incident-analysis"] = arch("Схема разбора аварии",
        [L("sym", ["Симптом", "что видели"]), L("seq", ["Хронология", "по логам"], True), L("cause", ["Причина", "техн. + систем."], True), L("data", ["Данные", "сообщения лога"]), L("cons", ["Последствия", "энергия, зона"])],
        [L("rec", ["Что изменить", "у себя"], True, 2)],
        [("sym", "seq"), ("seq", "cause"), ("cause", "data"), ("data", "cons"), ("cause", "rec", "", False, "v")])

    D["sortie-flow"] = arch("Вылет как процесс",
        [L("plan", ["План", "зона, погода"]), L("brief", ["Брифинг", "10 мин"], True), L("site", ["Чек-лист", "площадки"]), L("fly", ["Полёт", "радиообмен"], True), L("deb", ["Дебрифинг", "+ журнал"], True)],
        [L("roles", ["Роли: пилот,", "наблюдатель"], False, 3)],
        [("plan", "brief"), ("brief", "site"), ("site", "fly"), ("fly", "deb"), ("fly", "roles", "", False, "v")])

    # ------------------------------------------------------------ INAV
    D["inav-rth-steps"] = arch("RTH в INAV (мультиротор) по шагам",
        [L("d", ["Дом ближе", "min_rth_distance?"]), L("alt", ["Высота RTH", "climb_first"], True), L("go", ["Домой", "nav_auto_speed"]), L("home", ["Над домом", "allow_landing"])],
        [L("land", ["Посадка", "на месте"], False, 0), L("abort", ["Растёт дистанция", "→ авар. посадка"], True, 2)],
        [("d", "alt", "нет"), ("alt", "go"), ("go", "home"), ("d", "land", "да", False, "v"), ("go", "abort", "", False, "v")])

    D["firmware-choice"] = tree("Какая прошивка под задачу", Node("r", ["Задача"], [
        ("фристайл, гонки", Node("bf", ["Betaflight"], leaf=True)),
        ("навигация, крыло", Node("in", ["INAV: оценщик,", "RTH, миссии, крыло"], leaf=True, accent=True)),
        ("автономия", Node("ap", ["ArduPilot / PX4:", "EKF, MAVLink, API"], leaf=True)),
    ]), width=720)

    D["inav-ipf-model"] = arch("INAV Programming Framework: модель",
        [L("op", ["Операнды", "RC, высота, GVAR"]), L("lc", ["Logic Condition", "операция"], True), L("gv", ["GVAR", "−32768…32767"]), L("out", ["Действия", "VTX, газ, режим"])],
        [L("act", ["Активатор:", "другое условие"], False, 1), L("pid", ["Programming PID", "×4"], False, 2)],
        [("op", "lc"), ("lc", "gv"), ("gv", "out"), ("act", "lc", "", False, "v"), ("pid", "gv", "", False, "v")])

    D["inav-mission-flow"] = arch("Миссия INAV: от планирования до выполнения",
        [L("pl", ["Точки WP", "lat, lon, alt"]), L("up", ["Загрузка", "Configurator, CLI"]), L("sv", ["Сохранение", "в EEPROM"]), L("wp", ["Режим WP", "с тумблера"], True)],
        [L("end", ["Последняя точка:", "RTH или висение"], False, 3)],
        [("pl", "up"), ("up", "sv"), ("sv", "wp"), ("wp", "end", "", False, "v")])

    D["inav-autolaunch"] = timeline("Автозапуск крыла в INAV (значения по умолчанию)",
        [("Детекция", [(0, 0.2, "бросок ≈1.9 g", True)]), ("Задержка", [(0.2, 0.7, "0.5 с")]),
         ("Набор", [(0.7, 5.2, "launch_thr 1700, угол 18°", True)]), ("Пилот", [(5.2, 6.5, "стики / таймаут")])],
        6.5, unit="с", marks=[(0, "бросок"), (5.2, "launch_timeout 5 с")])

    D["vtx-four-pilots"] = arch("Четыре аналоговых аппарата: Raceband через канал",
        [L("r1", ["R1", "5658 МГц"], True), L("r3", ["R3", "5732 МГц"], True), L("r5", ["R5", "5806 МГц"], True), L("r7", ["R7", "5880 МГц"], True)],
        [L("f2", ["Пятый на F2 5760 —", "помехи R3"], False, 1)],
        [("r1", "r3", "74"), ("r3", "r5", "74"), ("r5", "r7", "74"), ("f2", "r3", "", False, "v")],
        notes=[(10, 150, "Разнос 74 МГц,", "m t"), (10, 164, "мощность 200 мВт", "m t")])

    # ------------------------------------------------------------ PX4
    D["px4-uorb-path"] = arch("PX4: путь от датчика до мотора через uORB",
        [L("s", ["sensors", "sensor_combined"]), L("e", ["ekf2", "поза, скорость"], True), L("pc", ["mc_pos_control", "→ attitude_sp"]), L("ac", ["mc_att_control", "→ rates_sp"]), L("rc", ["mc_rate_control", "→ torque_sp"], True)],
        [L("ca", ["Аллокатор", "actuator_motors"], True, 4)],
        [("s", "e"), ("e", "pc"), ("pc", "ac"), ("ac", "rc"), ("rc", "ca", "", False, "v")],
        notes=[(10, 150, "listener <топик> —", "m t"), (10, 164, "посмотреть любой шаг", "m t")])

    D["px4-jetson-link"] = arch("PX4 + Jetson: связь и роли",
        [L("cam", ["Камера", "CSI / USB"]), L("j", ["Jetson", "зрение, ROS 2"], True), L("pix", ["Pixhawk / PX4", "TELEM2"], True), L("qgc", ["QGC"])],
        [L("m", ["MAVLink 921600", "MAVSDK / MAVROS"], False, 1), L("d", ["uXRCE-DDS", "топики ROS 2"], False, 2)],
        [("cam", "j"), ("j", "pix", "UART"), ("pix", "qgc"), ("j", "m", "", False, "v"), ("pix", "d", "", False, "v")])

    D["px4-cascade"] = arch("Каскад управления PX4",
        [L("pos", ["Позиция", "P"]), L("vel", ["Скорость", "PID"]), L("att", ["Ориентация", "P (кватернион)"], True), L("rate", ["Угл. скорость", "PID + FF"], True), L("alloc", ["Аллокатор"])],
        [L("pp", ["MPC_XY_P", "MPC_XY_VEL_*"], False, 1), L("ap", ["MC_ROLL_P", "MC_ROLLRATE_*"], False, 3)],
        [("pos", "vel"), ("vel", "att"), ("att", "rate"), ("rate", "alloc"), ("vel", "pp", "", False, "v"), ("rate", "ap", "", False, "v")],
        notes=[(10, 150, "Внутренний в 3–5", "m t"), (10, 164, "раз быстрее", "m t")])

    D["px4-qgc-order"] = arch("Первая настройка PX4 в QGroundControl",
        [L("fw", ["Прошивка", "+ airframe"], True), L("sen", ["Датчики", "компас, accel"]), L("rc", ["Радио", "режимы, kill"]), L("mot", ["Моторы", "без пропов"]), L("bat", ["Питание", "делитель, пороги"])],
        [L("saf", ["Safety: RC loss,", "АКБ, геозона"], True, 4)],
        [("fw", "sen"), ("sen", "rc"), ("rc", "mot"), ("mot", "bat"), ("bat", "saf", "", False, "v")],
        notes=[(10, 150, "Смена airframe", "m t"), (10, 164, "сбрасывает параметры", "m t")])

    D["px4-offboard-seq"] = sequence("Offboard через uXRCE-DDS: три сообщения",
        ["ROS 2 узел", "PX4"],
        [(0, 1, "OffboardControlMode ≥ 2 Гц", True), (0, 1, "TrajectorySetpoint (NED)", True), (0, 0, "поток идёт ≥ 1 с"),
         (0, 1, "VehicleCommand: режим OFFBOARD"), (0, 1, "VehicleCommand: ARM"), (1, 0, "VehicleStatus", False, True),
         (0, 0, "поток прервался"), (1, 1, "COM_OF_LOSS_T → failsafe")],
        notes=[(1, "ENU/FLU ROS → NED/FRD PX4"), (3, "без потока режим не включится"), (7, "COM_OBL_RC_ACT — действие")])

    # ------------------------------------------------------------ ROS / tools
    D["ros1-migration"] = tree("Старый проект ROS 1: что делать", Node("r", ["Проект ROS 1"], [
        ("нужен сейчас", Node("br", ["ros1_bridge", "временно"], leaf=True)),
        ("живой код", Node("pt", ["Перенос: rclpy,", "launch.py, QoS"], leaf=True, accent=True)),
        ("MAVROS", Node("mv", ["MAVROS 2:", "те же плагины"], leaf=True)),
        ("мёртвый", Node("rw", ["Взять идеи,", "написать заново"], leaf=True)),
    ]), width=720)

    D["peak-diagnosis"] = tree("Пик в спектре гироскопа: что это", Node("r", ["Как пик ведёт", "себя с газом?"], [
        ("едет", Node("m", ["Гармоника моторов", "f = k · RPM/60"], [("", Node("m1", ["RPM-фильтр,", "баланс пропов"], leaf=True))], accent=True)),
        ("стоит", Node("f", ["Резонанс рамы", "или крепления"], [("", Node("f1", ["Статический notch,", "механика"], leaf=True))])),
        ("широкий", Node("w", ["Шум, турбулентность,", "люфт"], [("", Node("w1", ["Механика, LPF"], leaf=True))])),
    ]), width=720)

    D["angle-rate-cascade"] = arch("Каскад «угол → угловая скорость»",
        [L("asp", ["Уставка угла"]), L("ap", ["P угла"], True), L("rsp", ["Уставка", "угл. скорости"]), L("rpid", ["PID скорости", "+ FF"], True), L("pl", ["Объект", "моторы + рама"])],
        [L("est", ["Оценка угла", "фильтр/EKF"], False, 1), L("gyr", ["Гироскоп"], False, 3)],
        [("asp", "ap"), ("ap", "rsp"), ("rsp", "rpid"), ("rpid", "pl"), ("est", "ap", "", False, "v"), ("gyr", "rpid", "", False, "v")],
        notes=[(10, 150, "Внутренний", "m t"), (10, 164, "контур быстрее", "m t")])

    D["log-analysis-pipeline"] = arch("Анализ лога на Python",
        [L("log", ["Лог → CSV", ".bin / .bbl"]), L("df", ["DataFrame", "pandas"]), L("rs", ["Ресемплинг", "общая ось t"]), L("an", ["Welch, спектр,", "step-метрики"], True), L("rep", ["Отчёт", "графики + числа"])],
        [L("jit", ["Джиттер петли", "по меткам t"], False, 2)],
        [("log", "df"), ("df", "rs"), ("rs", "an"), ("an", "rep"), ("rs", "jit", "", False, "v")])

    D["toolbox-map"] = tree("Рабочее место инженера", Node("r", ["Инструменты"], [
        ("настройка", Node("cfg", ["Configurator BF/INAV,", "Mission Planner, QGC"], leaf=True)),
        ("логи", Node("lg", ["Blackbox Explorer,", "PlotJuggler"], leaf=True)),
        ("код", Node("cd", ["Python, git,", "терминал"], leaf=True, accent=True)),
        ("без дрона", Node("sim", ["SITL", "ArduPilot / PX4"], leaf=True)),
    ]), width=720)


def build4(D: dict, arch) -> None:
    """Stage 4 new modules."""
    D["dronecan-bus"] = arch("DroneCAN: одна пара проводов на всё",
        [L("t1", ["120 Ом", "терминатор"], True), L("fc", ["Полётник", "node 10, DNA"], True), L("gps", ["GPS + компас", "node auto"]),
         L("pm", ["Датчик тока", "node auto"]), L("t2", ["120 Ом", "терминатор"], True)],
        [L("esc", ["ESC ×8 по CAN2", "отдельная шина"], False, 1), L("chk", ["H–L без питания:", "≈ 60 Ом"], True, 3)],
        [("t1", "fc"), ("fc", "gps"), ("gps", "pm"), ("pm", "t2"), ("fc", "esc", "", False, "v")],
        notes=[(10, 150, "Линия, не звезда;", "m t"), (10, 164, "отводы короткие", "m t")])
    D["fpv-video-choice"] = tree("Какую систему FPV-видео выбрать", Node("r", ["Что важнее", "всего?"], [
        ("гонки", Node("an", ["Аналог / HDZero", "постоянная задержка"], leaf=True, accent=True)),
        ("картинка", Node("dj", ["DJI / Walksnail", "сжатое HD"], leaf=True)),
        ("открытость", Node("oi", ["OpenIPC + WFB-ng", "MAVLink в канале"], leaf=True)),
        ("дальность", Node("lr", ["цифра + ELRS", "OSD с качеством линка"], leaf=True, accent=True)),
    ]), width=780)
    D["gimbal-manager"] = arch("MAVLink Gimbal Protocol v2: кто кем командует",
        [L("gcs", ["GCS / companion", "SET_PITCHYAW"]), L("mgr", ["Gimbal manager", "автопилот, MNT1_*"], True),
         L("dev", ["Gimbal device", "подвес, свой IMU"], True), L("cam", ["Камера", "CAM1_*, захват"])],
        [L("rc", ["RC: RCx_OPTION", "212–214, 163 lock"], False, 0), L("mis", ["Миссия: ROI,", "GIMBAL_MANAGER_*"], False, 1),
         L("st", ["ATTITUDE_STATUS", "обратно, кватернион"], False, 2)],
        [("gcs", "mgr"), ("mgr", "dev", "", True), ("dev", "cam"), ("rc", "mgr", "", False, "v"), ("mis", "mgr", "", False, "v"),
         ("dev", "st", "", False, "v")],
        notes=[(10, 196, "Одна точка управления: manager решает, чья команда главная (primary control)", "m t")], height=210)
    D["esc-firmware-choice"] = tree("Какая прошивка ESC: по микроконтроллеру", Node("r", ["Что стоит", "на ESC?"], [
        ("8-бит BB21/BB51", Node("bs", ["BLHeli_S → Bluejay", "bidir DShot, EDT"], leaf=True, accent=True)),
        ("32-бит ARM", Node("am", ["AM32", "если есть таргет"], leaf=True, accent=True)),
        ("BLHeli_32", Node("b32", ["работает — оставить", "развитие прекращено"], leaf=True)),
        ("нет таргета", Node("no", ["родная прошивка", "не прошивать наугад"], leaf=True)),
    ]), width=780)
    D["security-surface"] = arch("Поверхность атаки аппарата и что её закрывает",
        [L("rc", ["RC-линк", "ELRS binding"]), L("tel", ["Телеметрия", "MAVLink"], True), L("gnss", ["GNSS", "глушение, спуфинг"], True),
         L("comp", ["Companion", "Wi-Fi, DDS, SSH"]), L("fw", ["Прошивка", "загрузчик"])],
        [L("d1", ["свой binding", "phrase, failsafe"], False, 0), L("d2", ["MAVLink 2", "signing, 32 байта"], True, 1),
         L("d3", ["EKF-проверки,", "нав. без GNSS"], False, 2), L("d4", ["файрвол, ключи,", "ROS_DOMAIN, SROS2"], False, 3),
         L("d5", ["подписанная", "прошивка"], True, 4)],
        [("rc", "d1", "", False, "v"), ("tel", "d2", "", True, "v"), ("gnss", "d3", "", False, "v"), ("comp", "d4", "", False, "v"),
         ("fw", "d5", "", True, "v")],
        notes=[(10, 196, "Подпись MAVLink — аутентификация, не шифрование: трафик остаётся читаемым", "m t")], height=210)
    D["multi-vehicle"] = flow("Флот: адресация, маршрутизация и разнесение", [
        Box("gcs", ["GCS, sysid 255", "один оператор"], 10, 30, 160, 48), Box("rt", ["mavlink-router", "UDP на каждый аппарат"], 280, 30, 160, 48, accent=True),
        Box("sup", ["Супервизор", "дистанции, общий стоп"], 550, 30, 160, 48, accent=True),
        Box("v1", ["Аппарат 1", "sysid 1, слой 30 м"], 10, 140, 160, 48), Box("v2", ["Аппарат 2", "sysid 2, слой 40 м"], 280, 140, 160, 48),
        Box("v3", ["Аппарат 3, FOLLOW", "FOLL_SYSID = 2"], 550, 140, 160, 48)],
        [("gcs", "rt"), ("rt", "sup", "", True), ("rt", "v1", "", False, "v"), ("rt", "v2", "", False, "v"), ("rt", "v3", "", False, "v")],
        720, 230, notes=[(10, 216, "target_system = 0 — команда всем аппаратам: только сознательно", "m t")])
