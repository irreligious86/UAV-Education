---
id: px4-intro
title: "Введение в PX4"
level: L2
readingTime: 20 мин
firmware: PX4 1.18 (сверено с v1.18.0)
status: published
added: 2026-11-08
tags:
  - PX4
  - QGroundControl
related:
  - ap-intro
  - px4-architecture
next:
  - px4-architecture
---

## summary
PX4 — второй большой открытый автопилот рядом с ArduPilot. Он вырос из академической среды и ближе к исследовательским задачам: модульная архитектура, строгие интерфейсы, глубокая интеграция с ROS 2. Модуль объясняет, чем PX4 отличается от ArduPilot на практике — наземная станция, режимы полёта, параметры, симуляция, требования к железу, — и когда его выбирать.

## theory
### PX4 против ArduPilot
Обе прошивки — полноценные автопилоты с навигацией, миссиями и companion-интерфейсами. Различия в характере:

- **Экосистема.** PX4 — Dronecode Foundation, стандарты (Pixhawk, MAVLink, MAVSDK), QGroundControl как «родная» GCS. ArduPilot — сообщество, Mission Planner, огромная база поддерживаемого железа.
- **Архитектура.** PX4 — модули, общающиеся через шину uORB; каждый модуль можно остановить и перезапустить на лету. ArduPilot — монолитнее, но с Lua-скриптами внутри.
- **ROS 2.** В PX4 — нативно через uXRCE-DDS: топики PX4 видны в ROS 2 напрямую. В ArduPilot (4.5+) — тоже нативный DDS-клиент (AP_DDS), но с меньшим набором топиков.
- **Тюнинг.** В PX4 хорошо проработан autotune мультиротора и самолёта, параметры структурированы по контурам (`MC_*RATE_*`, `MC_*_P`, `MPC_*`).

Правило выбора: исследования, компьютерное зрение и ROS 2 — PX4; поддержка экзотического железа, Lua на борту, большое сообщество практиков — ArduPilot. Летают оба.

### Наземная станция
QGroundControl: прошивка, выбор airframe, калибровки, параметры, миссии, анализ логов (`.ulg`). Работает с ArduPilot тоже, но для PX4 это основной инструмент.

### Режимы полёта мультиротора
- **Manual/Stabilized** — стабилизация углов, газ ручной.
- **Acro** — угловые скорости.
- **Altitude** — удержание высоты.
- **Position** — удержание позиции по GPS; стик — скорость.
- **Hold**, **Return**, **Land**, **Takeoff**, **Mission**, **Orbit**, **Follow Me** — автономные.
- **Offboard** — управление с companion-компьютера.

Как и везде: режим выбирают по тому, каким датчикам доверяешь. Position без надёжного GPS не включится. Требования режимов с пилотом в исходниках (`src/modules/commander/ModeUtil/mode_requirements.cpp`, v1.17.0 и v1.18.0) вложены друг в друга: Acro — угловая скорость, Stabilized — плюс ориентация, Altitude — плюс высота, Position — плюс локальная позиция; всем четырём нужен пульт. Пропала оценка в полёте — PX4 спускается на ступень: из Position в Altitude, без оценки высоты — в Stabilized (с 1.17 это поведение не настраивается, см. `COM_POSCTL_NAVL` в таблице перехода).

{{diagram:px4-mode-ladder|Каждый следующий режим требует ещё одну оценку и держит за пилота ещё одну величину; при потере оценки PX4 спускается на ступень ниже.}}

### Параметры и логи
Параметры — через QGC или консоль `param set/show`. Логи ULog (`.ulg`) содержат все топики uORB, которые включены в логирование; анализ — Flight Review (веб) или `pyulog`.

### Железо
Стандарт — Pixhawk-совместимые полётники (FMUv5/v6, H7). PX4 требовательнее к ресурсам, чем Betaflight, и F4-платы для него — редкость.

### Симуляция
`make px4_sitl gz_x500` поднимает SITL с Gazebo и моделью квадрокоптера x500; QGC подключается сама. Для ROS 2 это тот же стенд, что и для реального аппарата.

### Первая настройка в QGroundControl: порядок, который нельзя нарушать
1. **Прошивка** (Firmware → PX4 stable) и **airframe** (Airframe → тип рамы: задаёт `CA_AIRFRAME`, `CA_ROTOR_COUNT`, геометрию и стартовые параметры). Смена airframe сбрасывает параметры.
2. **Датчики**: компас (вращение по всем осям), гироскоп (неподвижно), акселерометр (6 положений), уровень горизонта; ориентация платы `SENS_BOARD_ROT`, внешнего компаса — автодетект.
3. **Радио**: калибровка стиков, `RC_MAP_*`; режимы на тумблерах (Flight Modes), kill switch — обязателен на тестах.
4. **Моторы**: Actuators — назначение выходов, протокол (DShot/PWM — по группам таймеров в Actuators, `PWM_MAIN_TIMx`), тест каждого **без пропов**, направление по схеме airframe.
5. **Питание**: `BAT1_N_CELLS`, калибровка делителя напряжения и тока по мультиметру/ваттметру, пороги `BAT_LOW_THR`/`BAT_CRIT_THR`.
6. **Safety**: действия при потере RC (`COM_RC_LOSS_T` = 0.5 с по умолчанию, `NAV_RCL_ACT`), потере канала данных с GCS (`NAV_DLL_ACT`, по умолчанию 0 — выключено, включают сами), низкой АКБ (`COM_LOW_BAT_ACT`), геозона (`GF_*`), высота возврата `RTL_RETURN_ALT`; kill switch `RC_MAP_KILL_SW` — моторы останавливаются сразу, в любом режиме и в воздухе (полная матрица — `px4-safety-return`).
Пред-армовые проверки сообщаются в QGC текстом («Preflight Fail: …»); `CBRK_*` circuit breakers отключают их только на стенде.

### Экраны QGC: что где настраивается
Правило: вход — что нужно настроить; решение — экран по таблице; проверка — параметр из столбца «Что пишет» в Parameters после перезагрузки. Названия экранов — QGC Stable 5.0 (PX4); в более новых сборках QGC страницы Safety и Power разбиты на отдельные (порты, батарея, ESC, failsafe, Return и Land) — названия зависят от версии QGC, параметры те же.

| Экран | Что пишет (PX4 1.18) | Где в курсе |
|---|---|---|
| Summary | ничего: красные/зелёные плашки готовности страниц | — |
| Firmware | прошивка PX4 stable / beta / свой `.px4`, загрузчик | `px4-setup-scratch` |
| Airframe | `SYS_AUTOSTART` → умолчания airframe (геометрия `CA_*`, усиления, `rc.mc_defaults`); Apply and Restart сбрасывает параметры, кроме калибровок `CAL_*` (и, до 1.18, `RC*` и `COM_FLTMODE*`; `rcS` v1.18.0 их больше не сохраняет) | `px4-setup-scratch` |
| Sensors | калибровки компаса, гироскопа, акселерометра, горизонта, датчика скорости; ориентации `SENS_BOARD_ROT`, `CAL_MAGn_ROT` | `px4-setup-scratch`, `px4-hardware-peripherals` |
| Radio | `RCn_MIN/TRIM/MAX/REV`, `RC_MAP_ROLL…THROTTLE`; Copy Trims; каналы AUX `RC_MAP_AUX1…6`; каналы подстройки `RC_MAP_PARAM1…3` | `px4-setup-scratch`, `px4-rc-tuning` |
| Flight Modes | `RC_MAP_FLTMODE` + `COM_FLTMODE1…6`, `RC_MAP_ARM_SW`, `RC_MAP_KILL_SW`, `RC_MAP_RETURN_SW`, `RC_MAP_LOITER_SW`, `RC_MAP_OFFB_SW` | `px4-rc-tuning` |
| Power | `BAT1_N_CELLS`, `BAT1_V_CHARGED/EMPTY`, `BAT1_V_DIV`, `BAT1_A_PER_V` (кнопки Calculate), калибровка ESC, настройки UAVCAN | `px4-setup-scratch` |
| Actuators | геометрия `CA_*`, функция каждого выхода `PWM_MAIN_FUNCn`, протокол группы `PWM_MAIN_TIMn`, Disarmed/Min/Max/Failsafe на выход, реверс `PWM_MAIN_REV`, слайдеры теста, Set Spin Direction (DShot) | `px4-outputs-servos` |
| Safety | low battery, потеря RC и канала данных, геозона, Return, Land, kill switch | `px4-safety-return` |
| PID Tuning | кнопка Start AutoTune (нужен `MC_AT_EN` = 1; кнопка шлёт `MAV_CMD_DO_AUTOTUNE_ENABLE`), ползунки rate / attitude / velocity / position, графики отклика | `px4-control` |
| Camera | триггер камеры `TRIG_*`, обратная связь `CAM_CAP_*` (страница есть в руководстве QGC, но в исходниках Stable 5.0 для PX4 её нет — задавать в Parameters) | `px4-camera-gimbal` |
| Parameters | весь список, Save/Load `.params`, Reset all to firmware's defaults / Reset to vehicle's configuration defaults, Set RC to Param, Reboot Vehicle | `px4-console-params`, `px4-rc-tuning` |
| Joystick | геймпад вместо пульта по MAVLink (`COM_RC_IN_MODE`) | `px4-setup-scratch` |
| Analyze Tools | MAVLink Console (`nsh>`), Log Download (ULog), MAVLink Inspector | `px4-console-params` |
| Plan → Fence, Rally | полигоны и круги геозоны, rally-точки для Return | `px4-safety-return` |

### Параметры: как они устроены
Имена — группами по модулю: `MC_*` (контроллеры мультиротора), `MPC_*` (позиция), `EKF2_*`, `IMU_*`, `COM_*` (commander/failsafe), `NAV_*`, `RTL_*`, `BAT*`, `CA_*` (control allocation), `SER_*`/`MAV_*`/`UXRCE_*` (порты). Полный справочник с диапазонами и умолчаниями — «Parameter Reference» в документации (генерируется из исходников, как у ArduPilot). Экспорт/импорт — QGC → Parameters → Tools (файл `.params`), версионируется (модуль «CI»).

### Числа для ориентира (умолчания, мультиротор)
Значения — для PX4 1.18 (сверено с v1.18.0; в 1.17 те же), прежние умолчания — в скобках. Внутренний контур на `IMU_GYRO_RATEMAX` = 800 Гц: у самого параметра умолчание 400, но airframe мультиротора поднимает его до 800 (`rc.mc_defaults`); максимум — 2000 Гц. Фильтр гироскопа `IMU_GYRO_CUTOFF` = 40 Гц, D-term `IMU_DGYRO_CUTOFF` = 20 Гц (до 1.17 — 30) — заметно ниже Betaflight: PX4 рассчитан на более крупные и медленные аппараты, для 5" их поднимают (гироскоп около 120, D-term 50–80 — по руководству PX4 по фильтрам) вместе с notch по ESC (`IMU_GYRO_DNF_EN`, нужны обороты ESC: bidirectional DShot — в 1.18 значения −6/−7/−8 в `PWM_AUX_TIMn` группы моторов, в 1.16–1.17 — `DSHOT_BIDIR_EN`; в 1.15 была только телеметрия ESC по UART `DSHOT_TEL_CFG`). Максимальный наклон `MPC_TILTMAX_AIR` = 45°, в ручных режимах `MPC_MAN_TILT_MAX` = 35°; максимальная скорость `MPC_XY_VEL_MAX` = 12 м/с.

### Логи ULog и Flight Review
Лог включается при арме (`SDLOG_MODE`), содержит топики uORB с заданной частотой (`SDLOG_PROFILE` — профили: по умолчанию, высокая частота для тюнинга, ...). С 1.18 ротация включена по умолчанию: файл не больше `SDLOG_MAX_SIZE` = 1024 МиБ, при старте записи старые логи удаляются, пока свободно меньше (100 − `SDLOG_ROTATE`) = 10 % карты; свой `etc/logging/logger_topics.txt` на SD добавляется к профилю, а не заменяет его. Flight Review (веб) рисует: отклик rate (setpoint vs actual), спектр вибраций (acceleration power spectral density — по нему видно моторы и резонансы), оценку EKF («Estimator Flags»; точность GPS — «GPS Uncertainty», «GPS Noise & Jamming»), загрузку CPU и RAM, входы RC и флаги failsafe (потеря RC видна там как `manual_control_signal_lost`). Innovation test ratios (те же «ворота», что в модуле про Калмана) Flight Review не рисует — их берут из `estimator_innovation_test_ratios` через `pyulog`. `pyulog` (`ulog2csv`) — для Python-анализа (модуль «Python для данных»).

### Переход 1.15 → 1.17: что переименовано и изменилось
До 27 ноября 2026 курс был сверен с PX4 v1.17.0; таблица ниже — переход на него с 1.15 (v1.15.4) и 1.16 (v1.16.2), следующий шаг — «Переход 1.17 → 1.18» после неё. Таблица получена сравнением определений параметров и airframe-умолчаний трёх тегов. Порядок обновления:
- **Бэкап до прошивки.** QGC → Parameters → Tools → Save to file (`.params`), логи с SD, версия из `ver all`. Этот файл — справка, а не то, что потом загружают целиком.
- **Обновление через QGC параметры не стирает, но хранятся только значения, которые отличаются от умолчания.** Всё, что совпадало с умолчанием — в том числе выставленное тобой вручную в то же число, — после прошивки молча получает умолчание 1.17: `MC_ROLL_P`/`MC_PITCH_P` 4.0 вместо 6.5, `IMU_DGYRO_CUTOFF` 20 вместо 30. Аппарат, который летал на умолчаниях, полетит иначе — тюн проверяют заново.
- **Удалённые параметры не переносятся.** Автоматически переводятся только единичные имена (в `param_translation.cpp` 1.17 из актуального — `SDLOG_MODE` = −1 → `SDLOG_BACKEND` = 0 и `ASPD_FALLBACK_GW` → `ASPD_FALLBACK`). `MPC_HOLD_DZ` → `MAN_DEADZONE`, `BAT1_V_LOAD_DROP`, `COM_POSCTL_NAVL` и остальные строки таблицы — руками.
- **Чистый старт надёжнее.** Сброс к умолчаниям (QGC: Parameters → Tools → Reset all to firmware's defaults; в консоли `param reset_all` — он стирает и `SYS_AUTOSTART`, разница в `px4-console-params`), заново airframe, калибровки датчиков и радио, затем перенос своих значений из файла по списку, сверяясь с таблицей.
- **Не переносится вообще:** `.params` из SITL на аппарат; сборка ROS 2 со старым `px4_msgs` (ветка должна соответствовать прошивке, часть топиков получила суффикс `_v1`); на fmu-v6x — настройка приёмника через `RC_PORT_CONFIG` (в сборке 1.17 другой набор RC-драйверов).
- **После обновления:** тест моторов без пропов, проверка failsafe на столе, короткое висение с логом — как при первой настройке (px4-setup-scratch).

{{diagram:px4-upgrade-param-tree|Опаснее всего правая ветка: параметр, который совпадал со старым умолчанием, после прошивки молча получает новое — MC_ROLL_P 4.0 вместо 6.5.}}

| Было (1.15 / 1.16) | Стало (1.17) | Что изменилось | С версии |
|---|---|---|---|
| `BAT1_V_LOAD_DROP` (и `BAT2_`, `BAT3_`) | удалён | поправки на нагрузку «газ × падение» больше нет; без датчика тока напряжение элемента не исправляется | 1.16 |
| `BAT1_R_INTERNAL` = 0.005 Ом | `BAT1_R_INTERNAL` = −1 | −1 — сопротивление оценивается в полёте; значение ≥ 0 задаёт его вручную | 1.16 |
| `BAT_N_CELLS`, `BAT_V_EMPTY`, `BAT_V_CHARGED`, `BAT_V_LOAD_DROP` | `BAT1_N_CELLS`, `BAT1_V_EMPTY`, `BAT1_V_CHARGED` | старые имена без номера батареи удалены | 1.16 |
| `COM_ARM_BAT_MIN` = 0 | `COM_ARM_BAT_MIN` = −1 | −1 — порогом запрета арма служит `BAT_CRIT_THR` | 1.16 |
| `COM_ARM_WO_GPS`: 0 — нужен GPS, 1 — не нужен | 0 — запрет арма, 1 — только предупреждение, 2 — проверка выключена | умолчание 1 то же, смысл значений другой: это реакция на проваленную проверку `EKF2_GPS_CHECK` | 1.16 |
| — | `COM_RAM_MAX` = 95 % | запрет арма, когда занято больше памяти, чем порог; −1 — проверка выключена (так в SITL) | 1.16 |
| только телеметрия ESC по UART (`DSHOT_TEL_CFG`) | `DSHOT_BIDIR_EN` (в 1.18 удалён, см. ниже) | bidirectional DShot (eRPM для динамического notch) появился в 1.16; только на поддерживаемых платах и выходах FMU | 1.16 |
| `DSHOT_MIN`, единица % | `DSHOT_MIN`, единица norm (0…1) | значение по умолчанию 0.055 то же, изменилась только подпись единицы | 1.17 |
| `PWM_MAIN_TIMn` / `PWM_AUX_TIMn` = −2 — DShot1200 (1.15) | значения нет: DShot только −5 / −4 / −3 (150 / 300 / 600) | DShot1200 убран | 1.16 |
| — | `PWM_MAIN_CENTn`, `PWM_AUX_CENTn` (−1 или 800…2200 мкс; на выходах IO — с 1.18) | центр сервы в микросекундах: две прямые `MIN`–`CENT`–`MAX` (`px4-outputs-servos`) | 1.17 |
| `CA_SV_CSn_TRIM` для любых серв | для PWM-серв заменён на `CENTn`; при любом `CENTn` ≠ −1 прошивка обнуляет все ненулевые `CA_SV_CSn_TRIM` | нейтраль переехала из миксера на выход | 1.17 |
| функции выходов до 440 (1.15) | + 450–453 IC Engine Ignition / Throttle / Choke / Starter, + 2070 RPM Input | новые функции | 1.16 |
| `PD_GRIPPER_EN` (0), `PD_GRIPPER_TO` = 3 с (1.15) | `PD_GRIPPER_EN` удалён, `PD_GRIPPER_TO` = 1 с | отдельного включения захвата больше нет: достаточно `PD_GRIPPER_TYPE` = 0 (Servo, умолчание) и выхода с функцией Gripper | 1.16 |
| `msp_osd`: элементы DJI legacy MSP | `msp_osd`: MSP DisplayPort, новый `OSD_RC_STICK` | драйвер переписан; совместимость с конкретными очками PX4 не документирует | 1.16 |
| `EKF2_EV_CTRL` = 15 | `EKF2_EV_CTRL` = 0 | внешнее зрение по умолчанию выключено — биты включают сами | 1.16 |
| `EKF2_OF_CTRL` = 0 | `EKF2_OF_CTRL` = 1 | оптический поток по умолчанию включён | 1.16 |
| `EKF2_AGP_CTRL` = 1 | `EKF2_AGP_CTRL` = 0; новый `EKF2_AGP_MODE` (в 1.18 — `EKF2_AGP0_*`, см. ниже) | вход абсолютной позиции по умолчанию выключен (1.16); режим сброса — 1.17 | 1.16 / 1.17 |
| `EKF2_GPS_CHECK` = 245 (макс. 511) | `EKF2_GPS_CHECK` = 2047 | 1.16: 1023, добавлен бит 9 «Spoofing»; 1.17: бит 10 — тип fix (`EKF2_REQ_FIX`, по умолчанию 3D) | 1.16 / 1.17 |
| `EKF2_TERR_MASK` | удалён | — | 1.16 |
| `COM_ARM_EKF_HGT/POS/VEL/YAW`, `COM_POS_FS_DELAY` | удалены | пороги pre-arm по EKF и задержка failsafe позиции больше не настраиваются | 1.16 |
| — | `COM_POS_LOW_ACT` (3 = Return) | действие при низкой точности позиции в Mission/Hold; порог `COM_POS_LOW_EPH` был и раньше, по умолчанию −1 (выключено) | 1.16 |
| — | `COM_DLL_EXCEPT` | режимы, в которых потеря канала данных игнорируется: бит 0 Mission, бит 1 Hold (в 1.18 — все авторежимы), бит 2 Offboard | 1.16 |
| `COM_RCL_EXCEPT`: биты 0–2 (Mission, Hold, Offboard) | + бит 3 External Mode, бит 4 Altitude Cruise | новые исключения потери RC | 1.17 |
| `COM_POS_FS_EPH` = 50 м у самолёта и VTOL (`rc.fw_defaults`, `rc.vtol_defaults`) | 5 м (умолчание параметра) | airframe больше не переопределяет порог: позиция теряется при eph > 2.5 × 5 = 12.5 м вместо 125 м | 1.17 |
| `COM_POSCTL_NAVL` (0 — Altitude, 1 — Land) | удалён | при потере позиции в Position всегда Altitude, без оценки высоты — Stabilized | 1.17 |
| `COM_FLTT_LOW_ACT` = 3 (Return) | `COM_FLTT_LOW_ACT` = 0 (None) | возврат по остатку времени полёта по умолчанию выключен (в 1.18 параметр удалён: возврат по времени снова входит в `COM_LOW_BAT_ACT` = 3) | 1.17 |
| `COM_RC_IN_MODE` 0…4 | `COM_RC_IN_MODE` 0…8 | добавлены приоритеты 5–8 (RC и два MAVLink-источника); «Joystick» в подписях заменён на «MAVLink»; умолчание 3 то же | 1.17 |
| `COM_OBL_RC_ACT`: 2 = Manual | 2 = Stabilized | подпись значения (1.16); в 1.17, если выбран переход в Position/Altitude/Stabilized, а ручного управления нет, выполняется `NAV_RCL_ACT` | 1.16 / 1.17 |
| `COM_FLTMODEn`: до 13 | добавлено 16 — Altitude Cruise | новый режим полёта | 1.17 |
| `RC_MAP_ACRO_SW`, `RC_MAP_MAN_SW`, `RC_MAP_POSCTL_SW`, `RC_MAP_RATT_SW`, `RC_MAP_STAB_SW` | удалены | режимы — только через `RC_MAP_FLTMODE` и `COM_FLTMODEn` | 1.16 |
| `MPC_HOLD_DZ` | `MAN_DEADZONE` (0.1) | мёртвая зона стиков, общая для режимов | 1.17 |
| `MPC_XY_MAN_EXPO`, `MPC_Z_MAN_EXPO`, `MPC_YAW_EXPO` | удалены | экспонента стиков в Position больше не настраивается (используется прежнее умолчание) | 1.17 |
| `RCn_DZ` (`RC1_DZ`…`RC18_DZ`) | удалены | мёртвой зоны на канал больше нет; для режимов — `MAN_DEADZONE` | 1.17 |
| `MC_ROLL_P`, `MC_PITCH_P` = 6.5 | = 4.0 | мягче контур угла; после обновления проверить отклик | 1.17 |
| `IMU_DGYRO_CUTOFF` = 30 Гц | = 20 Гц | фильтр D-составляющей ниже | 1.17 |
| `MPC_YAWRAUTO_MAX` = 45 °/с, `MPC_YAWRAUTO_ACC` = 60 °/с² | 60 °/с, 20 °/с² | рыскание в автоматических режимах | 1.17 |
| `GPS_UBX_DYNMODEL` = 6 у мультиротора (`rc.mc_defaults`) | 7 (умолчание параметра) | airframe больше не переопределяет динамическую модель u-blox | 1.17 |
| модуль `fw_pos_control` | `fw_mode_manager` + `fw_lat_lon_control` | контроллер положения самолёта разделён на два модуля; имена параметров в основном те же (удалённые — ниже), в `top` и `work_queue status` другие имена (`px4-setup-vtol`) | 1.17 |
| `FW_SPOILERS_DESC` | удалён | — | 1.16 |
| — | `FW_T_F_ALT_ERR`, `FW_T_THR_LOW_HGT`, `LNDFW_ROT_MAX` | новые параметры TECS и посадки самолёта | 1.16 |
| `FW_AT_SYSID_AMP`, `RWTO_HDG`, `RWTO_NPFG_PERIOD`, `NPFG_EN_MIN_GSP`, `NPFG_GSP_MAX_TK`, `NPFG_TRACK_KEEP`, `NPFG_WIND_REG` | удалены | при переносе `.params` самолёта эти строки пропускаются | 1.17 |
| `FW_AT_SYSID_F1` = 20 Гц, `FW_AT_SYSID_TYPE` = 0 (Step) | 10 Гц, 1 (Linear sine sweep) | автотюн самолёта по умолчанию возбуждает систему иначе | 1.17 |
| — | `FW_AIRSPD_FLP_SC` (1.0, 0.5…1) | масштаб минимальной скорости при выпущенных закрылках | 1.17 |
| подвес: уставка скорости из MAVLink или пульта держится, пока не придёт новая | обнуляется через 2 с без обновлений | подвес не крутится бесконечно при обрыве связи (`px4-camera-gimbal`) | 1.16 |
| `GIMBAL_MANAGER_INFORMATION`: фиксированные пределы ±90° по тангажу, ±180° по рысканию | из сведений устройства (`MNT_MODE_OUT` = 2) или из `MNT_RANGE_*` (AUX; в 1.18 — `MNT_MIN/MAX_PITCH`) | наземка видит реальные пределы подвеса | 1.16 |
| `MAV_PROTO_VER` = 0 | = 2 | MAVLink 2 с первого пакета (значения 0 больше нет: 1 — версия 1 с автопереходом на 2, 2 — версия 2) | 1.17 |
| `MAV_n_MODE` до 12 (1.15) | + 13 Low Bandwidth | новый набор потоков для узкого канала | 1.16 |
| — | `GPS_CFG_WIPE` = 0 | 1 — стереть настройки во flash u-blox при загрузке | 1.17 |
| `ASPD_PRIMARY` 0…3 | 0…4 | 4 — оценка скорости по тяге; `ASPD_FALLBACK` = 2 — она же как запасная | 1.17 |
| fmu-v6x: `SENS_EN_AUAVX` нет в сборке | есть | драйвер датчика скорости AUAV добавлен в `default.px4board` | 1.17 |
| `UAVCAN_RNG_MIN` / `_MAX` = 0.3 / 200 (1.15) | 0 / 999 | умолчания пределов дальномера по CAN | 1.16 |
| — (1.15) | `UAVCAN_SUB_FUEL` = 0 | приём уровня топлива по CAN | 1.16 |
| — | `UAVCAN_ESC_IFACE` = 255 | маска интерфейсов CAN для команд ESC | 1.17 |
| fmu-v6x: порта 300 в списке нет | 300 «Radio Controller» = `/dev/ttyS5` | это линия PX4IO; на плате с IO-процессором не назначать (`px4-hardware-peripherals`) | 1.17 |
| `MIS_PD_TO` | `MIS_COMMAND_TOUT` | переименован | 1.16 |
| `MIS_DIST_1WP` = 900 м | = 10000 м | допустимое расстояние до первой точки миссии | 1.16 |
| `RTL_TYPE` 0…3 | `RTL_TYPE` 0…4 | 4 — посадка миссии или дом по миссии в обратном порядке, что ближе по числу точек; rally-точки не учитываются | 1.16 |
| Return мультиротора и VTOL в висении: всегда остановка и снижение до `RTL_DESCEND_ALT` | при `RTL_LAND_DELAY` = 0 посадка начинается прямо с высоты возврата | остановка на `RTL_DESCEND_ALT` с ожиданием — только при ненулевой задержке | 1.16 |
| `COM_OBS_AVOID`, сообщения `TRAJECTORY_REPRESENTATION_*` | удалены | интерфейс внешнего планировщика обхода убран; Collision Prevention (`CP_*`) остался | 1.16 |
| файл параметров выбирает `rcS`: `/fs/mtd_params`, если есть, иначе SD | путь задаёт сборка платы (`CONFIG_BOARD_PARAM_FILE`, по умолчанию `/fs/mtd_params`) | на части плат параметры на SD или во flash (`px4-console-params`) | 1.16 |
| — | `SYS_PARAM_VER` | несовпадение с `PARAM_DEFAULTS_VER` airframe при загрузке ставит `SYS_AUTOCONFIG` = 1: параметры сбрасываются к умолчаниям (кроме `SYS_AUTOSTART`, калибровок, `RC*`), плата перезагружается | 1.16 |
| `SDLOG_MODE` = −1 (выключено) | `SDLOG_BACKEND` = 0 | новый параметр: бит 0 — SD, бит 1 — MAVLink, по умолчанию 3 | 1.17 |
| `msg/VehicleCommand.msg` | `msg/versioned/VehicleCommand.msg` | версионируемые сообщения перенесены в `msg/versioned/` | 1.16 |
| `/fmu/out/vehicle_status` | `/fmu/out/vehicle_status_v1` | суффикс `_vN` у топиков с версией сообщения > 0 | 1.16 |
| `/fmu/out/vehicle_local_position`, `battery_status`, `home_position`, `airspeed_validated`; `/fmu/in/vehicle_attitude_setpoint` | те же имена с `_v1` | версия сообщений поднята | 1.17 |
| — | `UXRCE_DDS_RX_TO`, `UXRCE_DDS_TX_TO` (1.16), `UXRCE_DDS_NS_IDX` (1.17) | таймауты и индексное пространство имён клиента; `UXRCE_DDS_CFG` без изменений | 1.16 / 1.17 |
| fmu-v6x, default-сборка: `rc_input` (`RC_PORT_CONFIG`) | `crsf_rc`, `sbus_rc`, `dsm_rc`, `ghst_rc` (`RC_CRSF_PRT_CFG`, `RC_SBUS_PRT_CFG`, `RC_DSM_PRT_CFG`, `RC_GHST_PRT_CFG`) | CRSF/ELRS работает без своей сборки, `rc_input` в сборке нет (так же fmu-v5x, fmu-v6xrt) | 1.17 |
| SITL: `COM_LOW_BAT_ACT` = 2 | SITL: `COM_LOW_BAT_ACT` = 3 | умолчание симулятора (`init.d-posix/rcS`); на полётнике по-прежнему 0 | 1.16 |
| SITL `gz_x500`: `NAV_DLL_ACT` = 0 | = 2 (Return) | только airframe 4001 симулятора; на полётнике 0 | 1.16 |

Не изменилось и перепроверено по v1.17.0: `IMU_GYRO_RATEMAX` 400 (у мультиротора 800), `RTL_RETURN_ALT` 60 м (у мультиротора 30 м, `RTL_DESCEND_ALT` 10 м), `NAV_DLL_ACT` 0, `NAV_RCL_ACT` 2, `COM_RC_LOSS_T` 0.5 с, `COM_FAIL_ACT_T` 5 с, `COM_OF_LOSS_T` 1 с, `MC_AT_EN` 0 (SITL — 1), пороги `BAT_*_THR`, `MAV_1_CONFIG` = Disabled, цели `make px4_sitl gz_x500` и `make px4_sitl sihsim_quadx`.

### Переход 1.17 → 1.18
PX4 v1.18.0 (тег от 23 ноября 2026, коммит 935addf) — цель курса с 27 ноября 2026. По сравнению определений параметров тегов v1.17.0 и v1.18.0: 65 параметров удалено, 237 добавлено, у 9 изменилось умолчание (у двух — только для одного типа аппарата). Те же списки лежат в теге в `Tools/migrate_param_file.py` (`CONVERSIONS`, `REMOVED`, `DEFAULT_CHANGES`). Значения новых и отсутствие удалённых параметров проверены командой `param show` в SITL v1.18.0 (SIH, `sihsim_quadx`). Порядок обновления:
1. **Бэкап до прошивки** — как для 1.17: `.params`, логи, `ver all`.
2. **Прошивать поверх.** При первой загрузке 1.18 переводит сохранённые на борту значения (`param_translation.cpp`): `EKF2_GPS_POS_X/Y/Z`, `EKF2_GPS_DELAY`, `MNT_RANGE_PITCH`, `MOT_POLE_COUNT`, `SENS_IMU_TEMP*`, `SENS_TEMP_ID`, `MPC_LAND_RC_HELP`, `EKF2_AGP_*`, `RCn_REV` (из дробного в целое) и только значение «выключено» у `COM_RC_OVERRIDE`. Остальные удалённые параметры не переносятся вовсе.
3. **Файл `.params` от 1.17 так не переводится.** QGC ставит параметры по имени, и старые имена молча пропускаются, а новые остаются на умолчании. Перед загрузкой прогони файл через `Tools/migrate_param_file.py старый.params новый.params` из тега v1.18.0: он делает те же переводы, пишет `RCn_REV` целыми, выбрасывает удалённые параметры и перечисляет значения, оставшиеся на старом умолчании. QGC может загрузить сохранённое `-1.000000` в целый `RCn_REV` как 0 (так предупреждает `migrate_param_file.py`; версии QGC, где это исправлено, в теге не названы) — проверь направление каждого канала.
4. **Умолчания.** Аппарат, который стоял на умолчании, получает новое: `FD_ACT_EN` и `SENS_MAG_AUTOCAL` становятся 0, `NAV_ACC_RAD` у мультиротора — 10 м вместо 2.
5. **После обновления:** перехват стиками на висении (новый порог), failsafe на столе (биты исключений, `COM_LOW_BAT_ACT`), подвес на столе (`px4-camera-gimbal`), обороты ESC в `esc_status`, если был bidirectional DShot.

| Было (1.17) | Стало (1.18) | Что делать | Где в коде (v1.18.0) |
|---|---|---|---|
| `COM_RC_OVERRIDE` (1: бит 0 — авторежимы, бит 1 — Offboard), `COM_RC_STICK_OV` (30 → порог 0.3 /с) | `MAN_OVERRIDE_SPD` = 1 /с (−1…10, отрицательное — выкл): перехват по скорости стика во всех авторежимах и в Offboard, мультиротор и VTOL в висении | переносится только «выключено» (0 → −1); проверь перехват резким движением стика (`px4-safety-return`) | `manual_control_params.yaml:43`, `ManualControl.cpp:142`, `param_translation.cpp:247` |
| `COM_DISARM_MAN` = 1 | удалён: дизарм с пульта в воздухе в Stabilized и Acro разрешён всегда | если стоял 0 — арм на тумблер с фиксацией (`px4-rc-tuning`) | `Commander.cpp:766` |
| `COM_KILL_DISARM` = 5 с, `COM_RC_ARM_HYST` = 1000 мс, `COM_LKDOWN_TKO` = 3 с, `COM_OBC_LOSS_T` = 5 с | удалены, прежние умолчания зашиты | ничего; другие времена больше не задаются | `Commander.cpp:849`, `ManualControl.cpp:355`, `failsafe.cpp:681`, `Commander.cpp:3049` |
| `COM_ARM_SDCARD`, `COM_IMB_PROP_ACT`, `COM_MOT_TEST_EN`, `COM_TAKEOFF_ACT`, `COM_HLDL_REG_T`, `COM_FLT_PROFILE` | удалены: SD и дисбаланс винта — всегда предупреждение, тест моторов всегда разрешён, после Takeoff всегда Hold | нужен взлёт сразу в миссию — армь в Mission | `migrate_param_file.py:134–142`, `failsafe.cpp:694`, `Commander.cpp:1786`, `Commander.cpp:2219` |
| `COM_FLTT_LOW_ACT` = 0 (возврат по остатку времени выключен) | удалён; возврат по остатку времени входит в `COM_LOW_BAT_ACT` = 3, новое значение 5 — то же без него | не переносится: при 3 и заданной `BAT1_CAPACITY` (или «умной» АКБ) Return может начаться раньше critical; не нужно — 5 | `commander_params.yaml:156`, `failsafe.cpp:666` |
| `COM_RCL_EXCEPT`, `COM_DLL_EXCEPT`: бит 1 — Hold (и Takeoff) | бит 1 — все авторежимы (Hold, Takeoff, VTOL Takeoff, Land, Return, Descend, Follow Target, Precision Land, Orbit, Guided Course самолёта) | сохранённое значение не меняется: стоял бит 1 — теперь и Return с Land игнорируют потерю связи | `commander_params.yaml:437`, `:454` |
| `COM_PARACHUTE` 0 / 1 (1 — запрет арма) | 0–4: 1 — только предупреждение, 2 — запрет арма, 3 Return, 4 Land | нужен запрет арма — 2 и выше | `commander_params.yaml:484` |
| `COM_ARM_ODID` 0–2 | 0–5: 3 Return, 4 Land, 5 Terminate при потере Remote ID в полёте | — | `commander_params.yaml:569` |
| `NAV_RCL_ACT` 1, 2, 3, 5, 6 | + 7 — Hold без failsafe | для внешних режимов и Offboard без пульта | `commander_params.yaml:416` |
| `FD_ESCS_EN` = 1; `FD_ACT_EN` = 1 | `FD_ESCS_EN` удалён, `FD_ACT_EN` = **0**; ESC offline и неисправности — при `COM_ARM_CHK_ESCS` = 1 | хочешь проверку тока моторов и дизарм при неармленных ESC — `FD_ACT_EN` = 1 | `esc_check_params.yaml:5`, `escCheck.cpp:84` |
| `FD_ACT_MOT_C2T` (2 А/%), `FD_ACT_MOT_THR`, `FD_ACT_MOT_TOUT` | `MOTFAIL_C2T` 35 А, `MOTFAIL_OFF` 10 А, `MOTFAIL_TIME` 1 с: срабатывает и недоток, и перегрузка | не переносятся — задать заново | `esc_check_params.yaml:15–40`, `escCheck.cpp:311` |
| `DSHOT_BIDIR_EN` (только таймер 0 на STM32) | `PWM_MAIN/AUX_TIMn` = −6 / −7 / −8 — BDShot600/300/150 на группу; `DSHOT_BIDIR_EDT` | не переносится: выбрать BDShot у каждой группы моторов (`px4-outputs-servos`) | `pwm_out/module.yaml:24`, `dshot.c:303` |
| `MOT_POLE_COUNT` = 14 | `DSHOT_MOT_POL1…12` = 14 | переносится во все 12 | `dshot/module.yaml:77`, `param_translation.cpp:212` |
| `MNT_RANGE_PITCH` = 90, `MNT_OFF_ROLL/PITCH/YAW` | `MNT_MIN_PITCH` = −45, `MNT_MAX_PITCH` = 45 (несимметрично можно); смещений нет — трим выхода; новый параметр `MNT_TAU` (0.3 с), новые значения `MNT_DO_STAB` = 3 и `MNT_MODE_IN` = 5 (`MNT_FIXED_PITCH`; умолчания самих параметров прежние, 0 и −1) | диапазон переносится как ±range/2, смещения — нет; ручка в режиме скорости — `MNT_TAU` = 0; при `MNT_DO_STAB` = 0 угловые уставки в мировой системе не проходят (SITL) — `px4-camera-gimbal` | `gimbal_params.yaml:101–171`, `output.cpp`, `param_translation.cpp:167` |
| `EKF2_GPS_POS_X/Y/Z`, `EKF2_GPS_DELAY` = 110 мс | `SENS_GPS0_OFFX/Y/Z`, `SENS_GPS0_DELAY` / `SENS_GPS1_DELAY` = 110, привязка к приёмнику — `SENS_GPS0_ID` / `SENS_GPS1_ID` | переносятся; с двумя GNSS проверь каждый приёмник (`est-gnss`) | `vehicle_gps_position/module.yaml:58–110`, `param_translation.cpp:181, 202` |
| `EKF2_AGP_CTRL/MODE/DELAY/NOISE/GATE` (шум 0.9 м) | `EKF2_AGP0…3_*` + `EKF2_AGP0_ID`; шум 1.0 м; включает только бит 0 `CTRL` | переносятся в набор 0, при `CTRL` ≠ 0 — `EKF2_AGP0_ID` = 1; источник с другим id — задать его (`nav-vtrn`) | `params_aux_global_position.yaml:7–68`, `param_translation.cpp:318` |
| `SENS_IMU_TEMP*`, `SENS_TEMP_ID` | `HEATER1_TEMP*`, `HEATER1_SENS_ID` (0 — автовыбор; сохранённый 0 становится −1, выкл) | переносятся | `param_translation.cpp:273` |
| `MC_AT_START`, `FW_AT_START` | удалены: автотюн — командой `MAV_CMD_DO_AUTOTUNE_ENABLE` (QGC) | — | `mc_autotune_attitude_control.cpp:112` |
| `LNDMC_TRIG_TIME` = 1 с | удалён: 1 с, 3 с с дальномером без данных | — | `MulticopterLandDetector.cpp:127` |
| `GF_PREDICT`, `MPC_USE_HTE` = 1 | удалены; оценщик тяги висения работает всегда | — | `migrate_param_file.py:155, 160` |
| `MPC_LAND_RC_HELP` | бит 1 `MPC_AUTO_NUDGING`; бит 0 — рыскание стиком во всех авторежимах. Для любого бита, включая подруливание на посадке, нужен `MAN_OVERRIDE_SPD` = −1 (`multicopter_nudging_params.yaml:20`) | переносится, но `MAN_OVERRIDE_SPD` остаётся 1: резкое подруливание в Land будет перехватом в Position — поставь −1 | `multicopter_nudging_params.yaml:5`, `param_translation.cpp:302` |
| `NAV_ACC_RAD` у мультиротора 2 м (`rc.mc_defaults`) | 10 м (умолчание параметра; у лодок и airframe 4016, 4020, 24001 — 2) | на старом умолчании радиус вырастет: точки миссии принимаются раньше, высота Return у дома — 2·d (`px4-safety-return`) | `navigator_params.yaml:20`, `rc.mc_defaults` |
| `SENS_MAG_AUTOCAL` = 1 | 0: некалиброванный компас сам начальную калибровку не сохраняет | калибровать компас в QGC | `sensor_params_mag.yaml:77` |
| `VT_PITCH_MIN`, `VT_LND_PITCH_MIN` = −5° | 0° | — | `vtol_att_control_params.yaml:267, 280` |
| `EKF2_REQ_PDOP` у самолёта 2.5 | 4.0 (`rc.fw_defaults`); у остальных 2.5 | — | `rc.fw_defaults:31` |
| `FW_T_HRATE_FF` 0.3; `MPC_LAND_RADIUS` 1000 | 0.5; −1 | — | `fw_lat_long_params.yaml:146`, `multicopter_nudging_params.yaml:26` |
| `RCn_REV` — дробный | целый (−1 / 1) | при загрузке `.params` старым QGC проверить реверс | `rc_update/params.yaml:32`, `param_translation.cpp:236` |
| функции Servo 1…8 (201…208) | Servo 1…15 (201…215) | — | `output_functions.yaml:14` |
| — | `COM_FLTMODE_BOOT` = 4 (Hold) — режим до первой команды; `SYS_HAS_NUM_GNSS` + `COM_GNSSLOSS_ACT`; `FD_ALT_LOSS`; `ESC_TEMP_WARN_TH` 90 °C; `COM_CC_TEMP_WARN` 80 °C; `MC_REF_FF` 0; `MPC_Z_ERR_MAX` 1 м; `EKF2_POS_LOCK`; `EKF2_SENS_EN`; `RTL_TYPE` = 5 | новые возможности, по умолчанию прежнее поведение, кроме предупреждений о температуре и `MPC_Z_ERR_MAX` = 1 м: растяжение вертикальной траектории в авторежимах включено (0 — как в 1.17; `multicopter_autonomous_params.yaml:134`, `FlightTaskAuto.cpp:782`) | `commander_params.yaml:132, 309, 612`, `system_params.yaml:139`, `failure_detector_params.yaml:94` |
| логи: без ограничения размера файла, старые каталоги удалялись только при свободном месте меньше 300 МиБ (`logger/util.cpp:192`, v1.17.0); `logger_topics.txt` заменяет профиль | `SDLOG_MAX_SIZE` = 1024 МиБ, `SDLOG_ROTATE` = 90 % (свободно ≥ 10 % карты); `logger_topics.txt` добавляется к профилю | в своём `logger_topics.txt` оставить только лишние топики | `logger/module.yaml:105, 120` |
| MAVLink-подписи в 1.17.0 нет | подпись по стандарту MAVLink: ключ на SD-карте, `SETUP_SIGNING` по любому каналу, но не в арме | — (`mav-protocol`) | `mavlink_sign_control.h:46`, `mavlink_main.cpp:1224` |
| `MAV_CMD_REQUEST_AUTOPILOT_CAPABILITIES`, `GET_HOME_POSITION` и др. | удалены — только `MAV_CMD_REQUEST_MESSAGE`; команды из таблицы проверки с ненулевым неиспользуемым параметром (1–7) отклоняются `DENIED`, а миссия с таким пунктом не загружается (`MAV_MISSION_INVALID_PARAMn`, `mavlink_mission.cpp`) | скрипты companion: неиспользуемые параметры — 0 или NaN | `mavlink_command_params.hpp`, `mavlink_receiver.cpp:685` |
| топики uXRCE-DDS `_v1` | `vehicle_status_v4`, `vehicle_command_ack_v1` и др. | `px4_msgs` ветки v1.18.0 (`px4-ros2`) | `msg/versioned/` |

Не изменилось и перепроверено по v1.18.0: те же умолчания, что в списке выше для 1.17 (`IMU_GYRO_RATEMAX`, фильтры гироскопа, `MC_ROLL_P` 4.0, `RTL_RETURN_ALT`/`RTL_DESCEND_ALT`, `NAV_DLL_ACT`, `NAV_RCL_ACT`, `COM_RC_LOSS_T`, `COM_FAIL_ACT_T`, `COM_OF_LOSS_T`, `MC_AT_EN`, `GPS_UBX_DYNMODEL`, `MIS_TAKEOFF_ALT` 2.5 м), состав групп таймеров fmu-v6x (`timer_config.cpp`), арифметика `rc_update`, слоты `COM_FLTMODEn`, выбор самого тяжёлого действия failsafe (`framework.cpp`; уточнено: Warn больше не вызывает отложенный Hold, отключённые условия пропускаются, уведомление приходит и о новом условии, которое поглощено уже идущим действием), формула конуса Return, драйверы триггера и обратной связи камеры. Требования режимов (`mode_requirements.cpp`) те же, добавлен только Guided Course самолёта.

{{diagram:px4-qgc-order|Порядок первой настройки PX4 в QGroundControl.}}

### Место в системе

- **Получает:** Pixhawk-совместимый полётник с H7 (`f-fc-sensors`); результаты калибровок датчиков (`est-sensors`); привычки ArduPilot для сравнения (`ap-intro`).
- **Отдаёт:** порядок экранов QGC — пошаговой настройке (`px4-setup-scratch`); таблицы перехода 1.15 → 1.17 и 1.17 → 1.18 — тюнингу, failsafe и мосту ROS 2 (`px4-control`, `px4-safety-return`, `px4-ros2`); лог ULog — Flight Review и `data-python`.
- **Если ошибиться здесь:** обновил прошивку, не сверив таблицу → значения, совпадавшие со старым умолчанием, молча получили новое → аппарат летит иначе, тюн проверять заново (`px4-control`). Оставил старый `px4_msgs` → топики с суффиксом `_v1` не находятся → offboard-узел не видит статус (`ros2-px4`).

## practice
### Шаг 1. SITL и QGC
```
git clone https://github.com/PX4/PX4-Autopilot.git --recursive
cd PX4-Autopilot
bash ./Tools/setup/ubuntu.sh
make px4_sitl gz_x500
```

В консоли PX4 (`pxh>`): `commander takeoff`, `commander land`. QGC подключится по UDP сама.

### Шаг 2. Режимы
В QGC переключи Position → Altitude → Stabilized на симуляторе, наблюдай, как меняется реакция на стик (в QGC есть виртуальный джойстик).

### Шаг 3. Параметры и лог
`param show MPC_THR_HOVER` в консоли; после полёта скачай `.ulg` из QGC (Analyze → Log Download) и открой в Flight Review.

### Что должно получиться и что записать
- **Шаг 1.** Первая сборка и первый запуск Gazebo идут долго: сборка — минуты, модели мира скачиваются при первом старте. Дальше запуск занимает секунды. `commander takeoff` поднимает x500 на высоту взлёта `MIS_TAKEOFF_ALT` (по умолчанию 2.5 м) и держит её. QGC подключается сама по UDP. Если связи нет, проверь, что QGC запущена на той же машине и порт 14550 не занят другим клиентом.
- **Шаг 2.** В Position отпущенные стики держат точку. В Altitude держится только высота, и аппарат сносит. В Stabilized стик задаёт угол, а высоту держишь ты. Запиши одной строкой на режим, что держит автопилот и что пилот, — это главный вывод модуля.
- **Шаг 3.** Миссия в QGC (Plan): взлёт, три точки на 20 м, Return. `.ulg` в SITL лежит в `build/px4_sitl_default/rootfs/log/<дата>/`. В Flight Review найди графики угла по крену и тангажу (оценка против уставки) и позиции против уставки. Расхождение больше нескольких градусов в SITL значит, что что-то не так с настройкой, а не с ветром: ветра в SITL нет, пока ты его не включишь.

### Лабораторная
Взлёт, короткая миссия из QGC и посадка в SITL; лог загружен в Flight Review, найдены графики attitude и position setpoint против фактических.

Самопроверка: лабораторная выполнена, когда SITL `gz_x500` запущен и QGC подключилась сама, `commander takeoff` поднял аппарат на `MIS_TAKEOFF_ALT` (по умолчанию 2.5 м), миссия из трёх точек выполнена до посадки, по строке на режим записано, что держит автопилот и что пилот, а рядом с `.ulg` в твоих заметках лежат два скриншота из Flight Review (угол и позиция: уставка против факта) с одной фразой вывода к каждому — расхождение по углу в SITL не больше нескольких градусов.

**Эталон для самопроверки.** Position: при отпущенных стиках автопилот держит точку. Altitude: держит только высоту, аппарат сносит. Stabilized: стик задаёт угол, высоту держишь ты. Типичные неверные: (1) угол расходится с уставкой больше чем на несколько градусов — ветра в SITL нет, пока ты его не включил, значит, дело в настройке; (2) QGC не подключилась — она запущена на другой машине, порт 14550 занят другим клиентом или остался старый экземпляр PX4.

## diagnostics
- **Симптом:** QGC не подключается к SITL
  - Возможная причина: другой экземпляр PX4 или занятый UDP-порт.
  - Что сделать: закрыть старые процессы, перезапустить SITL.
- **Симптом:** Position не включается
  - Возможная причина: нет GPS-фикса (в SITL — ждать инициализации).
  - Что сделать: подождать «Ready To Fly» в QGC.
- **Симптом:** прошивка не ставится на F4-плату
  - Возможная причина: PX4 не поддерживает это железо.
  - Что сделать: Pixhawk-совместимый FMUv5/v6 или ArduPilot.
- **Симптом:** `make` падает на зависимостях
  - Возможная причина: не выполнен `ubuntu.sh`.
  - Что сделать: запустить скрипт настройки окружения, перелогиниться.
- **Симптом:** «Preflight Fail: Compass Sensor 0 missing» / «Preflight Fail: Accel 0 inconsistent - check cal»
  - Возможная причина: не выполнена калибровка или датчик не найден (ориентация, шлейф).
  - Что сделать: калибровать по порядку, проверить `SENS_BOARD_ROT`, лог `dmesg` в консоли.
- **Симптом:** Position mode не включается
  - Возможная причина: EKF не доверяет GPS (`EKF2_GPS_CHECK`), нет fix, компас врёт.
  - Что сделать: QGC → MAVLink Console `ekf2 status`, число спутников, калибровка компаса в поле.
- **Симптом:** в Flight Review высокий уровень вибраций
  - Возможная причина: механика, жёсткое крепление FC.
  - Что сделать: модуль «Рама и вибрации», демпферы, балансировка.

## references
- PX4 User Guide — Flight Modes (Multicopter) | https://docs.px4.io/v1.17/en/flight_modes_mc/index.html | primary | A
- PX4 User Guide — Simulation | https://docs.px4.io/v1.17/en/simulation/ | primary | A
- PX4-Autopilot — source code (GitHub) | https://github.com/PX4/PX4-Autopilot | primary | A
- PX4-Autopilot v1.18.0: docs/en/releases/1.18.md (release notes, Upgrade Guide) | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/docs/en/releases/1.18.md | primary | A
- PX4-Autopilot v1.18.0: Tools/migrate_param_file.py (перевод .params 1.17 → 1.18) | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/Tools/migrate_param_file.py | primary | A
- PX4-Autopilot v1.18.0: src/lib/parameters/param_translation.cpp | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/lib/parameters/param_translation.cpp | primary | A
- QGroundControl — User Guide | https://docs.qgroundcontrol.com/Stable_V5.0/en/ | primary | A

## checklist
- Могу объяснить, когда PX4, а когда ArduPilot
- SITL с Gazebo запущен, QGC подключена
- Режимы Stabilized/Altitude/Position попробованы
- Лог .ulg открыт в Flight Review
