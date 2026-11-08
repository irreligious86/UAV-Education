---
id: px4-intro
title: "Введение в PX4"
level: L2
readingTime: 20 мин
firmware: PX4 1.14+
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

Как и везде: режим выбирают по тому, каким датчикам доверяешь. Position без надёжного GPS не включится.

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
6. **Safety**: действия при потере RC (`COM_RC_LOSS_T` = 0.5 с по умолчанию, `NAV_RCL_ACT`), потере данных (`NAV_DLL_ACT`), низкой АКБ (`COM_LOW_BAT_ACT`), геозона (`GF_*`), высота возврата `RTL_RETURN_ALT`.
Пред-армовые проверки сообщаются в QGC текстом («Preflight Fail: …»); `CBRK_*` circuit breakers отключают их только на стенде.

### Параметры: как они устроены
Имена — группами по модулю: `MC_*` (контроллеры мультиротора), `MPC_*` (позиция), `EKF2_*`, `IMU_*`, `COM_*` (commander/failsafe), `NAV_*`, `RTL_*`, `BAT*`, `CA_*` (control allocation), `SER_*`/`MAV_*`/`UXRCE_*` (порты). Полный справочник с диапазонами и умолчаниями — «Parameter Reference» в документации (генерируется из исходников, как у ArduPilot). Экспорт/импорт — QGC → Parameters → Tools (файл `.params`), версионируется (модуль «CI»).

### Числа для ориентира (умолчания, мультиротор)
Внутренний контур на `IMU_GYRO_RATEMAX` = 400 Гц (до 1 кГц на быстрых платах); фильтр гироскопа `IMU_GYRO_CUTOFF` = 40 Гц, D-term `IMU_DGYRO_CUTOFF` = 20 Гц — заметно ниже Betaflight: PX4 рассчитан на более крупные и медленные аппараты, для 5" их поднимают (80–120 / 40–60) вместе с notch по ESC (`IMU_GYRO_DNF_EN`, нужен DShot-телеметрия). Максимальный наклон `MPC_TILTMAX_AIR` = 45°, в ручных режимах `MPC_MAN_TILT_MAX` = 35°; максимальная скорость `MPC_XY_VEL_MAX` = 12 м/с.

### Логи ULog и Flight Review
Лог включается при арме (`SDLOG_MODE`), содержит топики uORB с заданной частотой (`SDLOG_PROFILE` — профили: по умолчанию, высокая частота для тюнинга, ...). Flight Review (веб) рисует: отклик rate (setpoint vs actual), спектр вибраций (acceleration power spectral density — по нему видно моторы и резонансы), оценку GPS/EKF (innovation test ratios — те же «ворота», что в модуле про Калмана), загрузку CPU и RAM, потери RC. `pyulog` (`ulog2csv`) — для Python-анализа (модуль «Python для данных»).

{{diagram:px4-qgc-order|Порядок первой настройки PX4 в QGroundControl.}}

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

### Лабораторная
Взлёт, короткая миссия из QGC и посадка в SITL; лог загружен в Flight Review, найдены графики attitude и position setpoint против фактических.

## diagnostics
- **Симптом:** QGC не подключается к SITL
  - Возможная причина: другой экземпляр PX4 или занятый UDP-порт.
  - Что сделать: закрыть старые процессы, перезапустить SITL.
- **Симптом:** Position не включается
  - Возможная причина: нет GPS-фикса (в SITL — ждать инициализации).
  - Что сделать: подождать «ready for takeoff» в QGC.
- **Симптом:** прошивка не ставится на F4-плату
  - Возможная причина: PX4 не поддерживает это железо.
  - Что сделать: Pixhawk-совместимый FMUv5/v6 или ArduPilot.
- **Симптом:** `make` падает на зависимостях
  - Возможная причина: не выполнен `ubuntu.sh`.
  - Что сделать: запустить скрипт настройки окружения, перелогиниться.
- **Симптом:** «Preflight Fail: Compass sensor 0 missing» / «Accel inconsistent»
  - Возможная причина: не выполнена калибровка или датчик не найден (ориентация, шлейф).
  - Что сделать: калибровать по порядку, проверить `SENS_BOARD_ROT`, лог `dmesg` в консоли.
- **Симптом:** Position mode не включается
  - Возможная причина: EKF не доверяет GPS (`EKF2_GPS_CHECK`), нет fix, компас врёт.
  - Что сделать: QGC → MAVLink Console `ekf2 status`, число спутников, калибровка компаса в поле.
- **Симптом:** в Flight Review высокий уровень вибраций
  - Возможная причина: механика, жёсткое крепление FC.
  - Что сделать: модуль «Рама и вибрации», демпферы, балансировка.

## references
- PX4 User Guide — Flight Modes (Multicopter) | https://docs.px4.io/main/en/flight_modes_mc/ | primary | A
- PX4 User Guide — Simulation | https://docs.px4.io/main/en/simulation/ | primary | A
- PX4-Autopilot — source code (GitHub) | https://github.com/PX4/PX4-Autopilot | primary | A
- QGroundControl — User Guide | https://docs.qgroundcontrol.com/master/en/ | primary | A

## checklist
- Могу объяснить, когда PX4, а когда ArduPilot
- SITL с Gazebo запущен, QGC подключена
- Режимы Stabilized/Altitude/Position попробованы
- Лог .ulg открыт в Flight Review
