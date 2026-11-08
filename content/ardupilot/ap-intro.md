---
id: ap-intro
title: "Введение в ArduPilot"
level: L2
readingTime: 20 мин
firmware: ArduPilot 4.5+
status: published
added: 2026-11-07
tags:
  - ArduPilot
  - параметры
  - режимы
related:
  - ap-sitl
  - bf-intro
next:
  - ap-sitl
---

## summary
ArduPilot — автопилот, а не просто стабилизатор. Если Betaflight делает квадрокоптер послушным под стиками, то ArduPilot знает, где он находится, куда летит и что делать без пилота. Модуль объясняет, чем мышление в ArduPilot отличается от Betaflight: параметры вместо CLI-дифов, режимы полёта как уровни автономности, наземная станция, pre-arm проверки и требования к железу. После него открывается весь трек «Автономия».

## theory
### Один код — много аппаратов
ArduPilot — общий код и отдельные прошивки под тип аппарата: Copter (мультироторы и вертолёты), Plane (самолёты, крылья и QuadPlane-VTOL), Rover, Sub. Тип рамы внутри прошивки задаётся параметрами: для Copter это `FRAME_CLASS` (1 — Quad, 2 — Hexa, 3 — Octa, 4 — OctaQuad, 7 — Tri…) и `FRAME_TYPE` (0 — Plus, 1 — X, 2 — V, 3 — H…).

{{diagram:ardupilot-fast-loop|Как устроен цикл ArduCopter: датчики → EKF → контуры режима → контур угловой скорости → моторы.}}

### Параметры
Вся конфигурация — это параметры (их больше тысячи). Ключевое отличие от Betaflight: изменение параметра записывается сразу, команды `save` нет. Часть параметров требует перезагрузки (тип рамы, протоколы, включение подсистем). Рабочий процесс:

1. Сохранить полный список параметров в файл (`.param`) до изменений.
2. Менять по одному смысловому блоку.
3. Сравнивать файлы параметров до и после — как `diff all` в Betaflight.

### Режимы полёта
Режимы — это уровни автономности. Для Copter:

- **STABILIZE** — самовыравнивание, газ ручной. Базовый режим, работает без GPS.
- **ALT_HOLD** — плюс удержание высоты по барометру.
- **LOITER** — плюс удержание позиции, нужен GPS.
- **AUTO** — выполнение миссии.
- **GUIDED** — команды от наземной станции или скрипта (основа companion-компьютеров).
- **RTL** и **LAND** — возврат домой и посадка.

Правило: режим выбирают по тому, каким датчикам ты доверяешь. Нет GPS — нет LOITER, RTL и AUTO.

### Наземная станция и MAVLink
Настраивают ArduPilot через наземную станцию (GCS): Mission Planner, QGroundControl или консольный MAVProxy. Все они говорят с полётником по MAVLink — тому же протоколу, по которому потом будет общаться твой companion-компьютер.

### Pre-arm проверки
ArduPilot не армится, пока что-то не так: не откалиброван акселерометр или компас, нет связи, плохой EKF, неверные параметры. Сообщение `PreArm: ...` в GCS — подсказка, а не помеха. Отключать проверки, чтобы «просто полетело», — классический путь к аварии.

### Требования к железу
ArduPilot заметно тяжелее Betaflight. На F4-контроллерах часть функций недоступна: например, Lua-скрипты требуют минимум 2 МБ флеша и не работают на F4. Для сложных платформ берут H7.

### Что меняется для пилота Betaflight
- Не дифы, а файлы параметров.
- Не «прошил и полетел», а калибровки (акселерометр, компас, радио, ESC) и pre-arm.
- Логи DataFlash (`.bin`) пишутся почти всегда и содержат всё: от вибраций до решений EKF.
- Тюнинг чаще начинают с AUTOTUNE, а не с ручного PID.

### Режимы Copter по номерам (`FLTMODE1..6`, значения из `Parameters.cpp`)
0 Stabilize, 1 Acro, 2 AltHold, 3 Auto, 4 Guided, 5 Loiter, 6 RTL, 7 Circle, 9 Land, 11 Drift, 13 Sport, 14 Flip, 15 AutoTune, 16 PosHold, 17 Brake, 18 Throw, 20 Guided_NoGPS, 21 Smart_RTL, 22 FlowHold, 23 Follow, 24 ZigZag, 25 SystemID, 27 Auto RTL, 28 Turtle. Шесть позиций канала `FLTMODE_CH` (границы PWM 1230/1360/1490/1620/1749) + любые режимы на `RCx_OPTION`. Группы по требованиям к датчикам: без позиции — Stabilize, Acro, AltHold (баро), Land (частично), FlowHold (поток); с позицией — Loiter, PosHold, Auto, Guided, RTL, Smart_RTL, Circle, Follow, ZigZag, Brake. Первый полёт любой сборки — Stabilize → AltHold → Loiter в этом порядке.

### Порядок первой настройки (Mission Planner / QGC)
1. Прошивка по типу платы (`hwdef`), выбор frame class/type (`FRAME_CLASS`, `FRAME_TYPE`).
2. Калибровки: акселерометр (6 положений), уровень, компас (в поле), радио (`RC1..4_MIN/MAX/TRIM`), ESC (`MOT_PWM_TYPE` DShot — калибровка не нужна), датчик напряжения/тока (`BATT_MONITOR`, `BATT_VOLT_MULT`, `BATT_AMP_PERVLT` по ваттметру).
3. Режимы на тумблерах, `RCx_OPTION` (ARM/DISARM, Motor E-Stop, EKF source set…).
4. Failsafe (модуль «Отказоустойчивость»), геозона, `RTL_ALT`.
5. Стартовые параметры тюнинга по размеру пропа (модуль «Тюнинг ArduPilot»): `INS_GYRO_FILTER`, `ATC_RAT_*_FLT*`, `MOT_THST_EXPO`, `ATC_INPUT_TC`, `PSC_ACCZ_*`.
6. Логи (`LOG_BITMASK`), `LOG_DISARMED` для наземных измерений.
7. Motor test (Mission Planner → Optional Hardware → Motor Test) без пропов: порядок и направление по схеме frame type.

### Разобранный пример: перевод пилота с Betaflight
«Почему не армится?» — `ARMING_CHECK` сообщает причину текстом (компас, GPS, INS, параметры, RC не откалибровано); «почему не держит высоту в Stabilize?» — потому что Stabilize = Betaflight Angle, высоту держит AltHold; «где rates?» — `ACRO_RP_RATE`/`ACRO_Y_RATE`, `ACRO_RP_EXPO`; «где PID?» — `ATC_RAT_RLL_P/I/D/FF/FLTD/FLTE/FLTT` (rate) и `ATC_ANG_RLL_P` (angle); «где фильтры?» — `INS_GYRO_FILTER`, `INS_HNTCH_*`; «где Blackbox?» — DataFlash на SD, Log Review; «где diff all?» — Full Parameter List → Save/Compare, или `param save` в MAVProxy.

## practice
### Первое знакомство без риска
1. Пройди модуль про SITL: всё ниже можно сделать на симуляторе.
2. Открой полный список параметров в GCS и найди `FRAME_CLASS`, `FRAME_TYPE`, `ARMING_CHECK`, `FS_THR_ENABLE`.
3. Сохрани параметры в файл с датой в имени.
4. Переключи режимы STABILIZE → ALT_HOLD → LOITER в SITL и посмотри, какие требуют GPS.

### Чек перед первым реальным полётом
1. Тип рамы и порядок моторов проверены без пропов (Motor Test).
2. Калибровки пройдены: акселерометр, компас (если есть), радио, ESC.
3. Настроены failsafe по радио и по батарее.
4. Нет `PreArm`-сообщений.
5. Первый полёт — в STABILIZE низко, затем ALT_HOLD.

**Автопроверка первого висения:** `examples/sitl-pymavlink/check_lab_log.py <лог.bin> --lab hover` — вибрации p95 < 30, без клиппинга, газ висения 0.2–0.6, трекинг углов p99 < 10°, просадка АКБ < 15%.

## diagnostics
- **Симптом:** `PreArm: ...` и дрон не армится
  - Возможная причина: незавершённая калибровка или неверный параметр, текст сообщения указывает подсистему.
  - Что сделать: читать сообщение целиком, устранять причину, а не отключать `ARMING_CHECK`.
- **Симптом:** после изменения параметра ничего не изменилось
  - Возможная причина: параметр требует перезагрузки.
  - Что сделать: перезагрузить полётник и перечитать значение.
- **Симптом:** LOITER/RTL недоступны
  - Возможная причина: нет GPS-фикса или EKF не готов.
  - Что сделать: дождаться 3D-фикса, проверить статус EKF в GCS.
- **Симптом:** Lua-скрипты не запускаются на полётнике
  - Возможная причина: F4-плата или мало памяти.
  - Что сделать: проверить серию процессора; для скриптов нужен F7/H7.
- **Симптом:** «PreArm: Compass not calibrated / inconsistent»
  - Возможная причина: калибровка не выполнена или внутренний и внешний компасы не согласны (помехи).
  - Что сделать: калибровка в поле, отключить внутренний (`COMPASS_USE2 = 0`) при внешнем на мачте.
- **Симптом:** «PreArm: Check fence» / «Need 3D Fix»
  - Возможная причина: геозона включена, GPS без fix.
  - Что сделать: ждать fix (`GPS_HDOP_GOOD`), или временно летать без геозоны только в режимах без позиции.

## references
- Frame Class and Type Configuration — ArduPilot Copter | https://ardupilot.org/copter/docs/frame-type-configuration.html | primary | A
- Pre-Arm Safety Checks — ArduPilot Copter | https://ardupilot.org/copter/docs/common-prearm-safety-checks.html | primary | A
- Choosing an Autopilot — ArduPilot Copter | https://ardupilot.org/copter/docs/common-autopilots.html | primary | A
- Lua Scripts — ArduPilot | https://ardupilot.org/copter/docs/common-lua-scripts.html | primary | A

## checklist
- Понимаю разницу Copter/Plane и что задают `FRAME_CLASS` и `FRAME_TYPE`
- Сохраняю параметры в файл до изменений
- Знаю, какие режимы требуют GPS
- Не отключаю pre-arm проверки ради взлёта
- Знаю серию процессора своего FC и ограничения F4
