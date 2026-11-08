---
id: fw-reading
title: "Как читать исходники прошивки: Betaflight и ArduPilot"
level: L4
readingTime: 45 мин
firmware: Betaflight · ArduPilot
status: published
added: 2026-11-08
tags:
  - исходники
  - Betaflight
  - ArduPilot
  - SITL
  - патч
related:
  - bf-custom
  - emb-basics
  - ctl-theory
  - ap-sitl
next:
  - eng-ci-configs
---

## summary
Документация описывает, что параметр «делает»; только код показывает, что он делает **на самом деле** — с порядком операций, ограничениями и побочными эффектами. Модуль учит ориентироваться в двух больших кодовых базах без чтения всего: как найти путь от гироскопа до моторов, где живут PID и фильтры, как сверить реализацию с теорией (и найти расхождения), и как внести минимальное изменение, собрать и проверить в SITL — не трогая реальный аппарат. Лабораторная: патч с отчётом.

## theory
### Инструменты чтения
`git clone` + `grep -rn`/`rg` + редактор с переходом к определению (VS Code с clangd, или просто `rg "pidController\("`). Для C/C++ прошивок главный приём — идти от **точки входа планировщика** вниз по вызовам, и от **параметра** (его имя в коде) к месту использования. `git blame`/`git log -S "имя"` показывает, когда и зачем строку добавили — комментарий к PR часто объясняет больше, чем вики.

### Betaflight: путь gyro → PID → mixer
Репозиторий `betaflight/betaflight`, код в `src/main/`:

1. **Планировщик**: `scheduler/scheduler.c` — выбирает задачи из таблицы `fc/tasks.c`. Задача `TASK_GYRO` (`taskGyroSample`) и `TASK_FILTER`/`TASK_PID` (`taskMainPidLoop` в `fc/core.c`).
2. **Гироскоп**: `sensors/gyro.c` — `gyroUpdate()` читает драйвер (`drivers/accgyro/accgyro_spi_icm426xx.c` и др., через DMA), `gyroFiltering()` применяет цепочку: RPM-notch (`flight/rpm_filter.c`), динамический notch (`flight/dyn_notch_filter.c`), LPF1/LPF2 (`common/filter.c`: PT1/PT2/PT3/biquad). Порядок фильтров — именно здесь, и он не очевиден из конфигуратора.
3. **PID**: `flight/pid.c` — `pidController()`: для каждой оси ошибка = setpoint − gyro, P, I с anti-windup и iterm_relax, D на отфильтрованном гироскопе (D-LPF, `d_min`/`d_max`), feedforward (`flight/pid_init.c`, `fc/rc.c` — FF считается из производной setpoint с интерполяцией/сглаживанием), TPA, anti-gravity, `pidSum` в `pidData[axis].Sum`.
4. **Миксер**: `flight/mixer.c` — `mixTable()`: pidSum по осям × матрица миксера (`mixer_init.c`/`mixer_tricopter.c`) + газ → моторы, `airmode`, ограничение (`mixer_type`: LEGACY/LINEAR/DYNAMIC), idle (`dshot_idle_value`), `motorOutputLimit`.
5. **Вывод**: `drivers/dshot.c` (кодирование кадра), `drivers/pwm_output.c`; платформенная часть на текущем master — `src/platform/STM32/dshot_bitbang.c`, `src/platform/common/stm32/dshot_dpwm.c`, `pwm_output_dshot_shared.c` — формирование кадров DShot через таймер+DMA; декодирование eRPM bidirectional DShot — `drivers/dshot_bitbang_decode.c` (в 4.5 `dshot_dpwm.c` лежал в `src/main/drivers/`).
6. **Blackbox**: `blackbox/blackbox.c` — что и как логируется (`blackbox_fields.c`).

Проверка на теорию: в `pid.c` найти, как считается D — `-(gyroRateDterm[axis] - previousGyroRateDterm[axis]) * pidFrequency`, где `gyroRateDterm` — гироскоп, уже пропущенный через D-notch и D-LPF1/LPF2 (фильтры стоят до дифференцирования), затем умножение на `pidCoefficient[axis].Kd` и `dMinFactor` (в master — `dMaxMultiplier`): D берётся от **гироскопа**, а не от ошибки (нет «derivative kick» при движении стика), и масштаб коэффициента — константы в `pid.h`, применяются в `pid_init.c` (`PTERM_SCALE`, `ITERM_SCALE`, `DTERM_SCALE`: отсюда «безразмерные» значения в конфигураторе).

### ArduPilot: путь IMU → rate → motors
Репозиторий `ArduPilot/ardupilot`, транспорт в `ArduCopter/`, библиотеки в `libraries/`:

{{diagram:ardupilot-fast-loop|Быстрая петля ArduCopter: задачи, которые планировщик вызывает каждый тик, и медленные задачи с собственной частотой.}}

1. **Планировщик**: `ArduCopter/Copter.cpp` — таблица `scheduler_tasks[]`: `FAST_TASK_CLASS(AP_InertialSensor, &copter.ins, update)` → `FAST_TASK(run_rate_controller_main)` → `FAST_TASK(motors_output_main)` → `FAST_TASK(read_AHRS)` → … → `FAST_TASK(update_flight_mode)`; медленные задачи `SCHED_TASK(rc_loop, 250, 130, 3)` с частотой, бюджетом (мкс) и приоритетом. Новые версии умеют выделенный rate-поток (`ArduCopter/rate_thread.cpp`, `FSTRATE_ENABLE`) на частоте гироскопа.
2. **IMU и фильтры**: `libraries/AP_InertialSensor/` — `AP_InertialSensor.cpp` (`update()`), backend драйверы (`AP_InertialSensor_Invensensev3.cpp`), гармонический notch `libraries/Filter/HarmonicNotchFilter.cpp`, LPF `Filter/LowPassFilter2p.cpp`.
3. **Rate-контур**: `ArduCopter/Attitude.cpp` — `run_rate_controller_main()` → `attitude_control->rate_controller_run()` в `libraries/AC_AttitudeControl/AC_AttitudeControl_Multi.cpp`: для каждой оси `_motors.set_roll(get_rate_roll_pid().update_all(target, gyro, dt, _motors.limit.roll, …))` в `libraries/AC_PID/AC_PID.cpp` (P, I с limit, D с фильтром `FLTD`, FF, ошибка через `FLTE`, цель через `FLTT`) → `_motors.set_roll(...)`.
4. **Angle-контур**: `AC_AttitudeControl.cpp` — `input_euler_angle_roll_pitch_euler_rate_yaw()` и др. → кватернионная ошибка → `rate_target_ang_vel` с `ATC_ANG_*_P` и ограничениями ускорения (`ATC_ACCEL_*_MAX`) — реализация input shaping.
5. **Моторы**: `ArduCopter/motors.cpp` `motors_output_main()` → `libraries/AP_Motors/AP_MotorsMulticopter.cpp` `output()` (фильтр газа, lift_max по напряжению АКБ, spool-логика) → `AP_MotorsMatrix.cpp` `output_armed_stabilizing()` (распределение roll/pitch/yaw/throttle по матрице с приоритетом и `MOT_YAW_HEADROOM`) → `output_to_motors()` → `SRV_Channel`/`AP_HAL` RCOutput (DShot/PWM).
6. **EKF**: `libraries/AP_NavEKF3/` — `AP_NavEKF3_core.cpp` (`UpdateFilter`), по файлу на тип измерений (`*_PosVelFusion.cpp`, `*_MagFusion.cpp`, `*_OptFlowFusion.cpp`), источники в `AP_NavEKF/AP_NavEKF_Source.cpp`.
7. **Параметры**: `ArduCopter/Parameters.cpp` и `*_Params.cpp` в библиотеках — блоки `// @Param:` с описанием, диапазоном и `@Values` — это источник вики параметров.

Проверка на теорию: в `AC_PID::update_all()` увидеть, что D считается от ошибки, пропущенной через `FLTD`, а не от сырого гироскопа; что I ограничивается `IMAX` и не накапливается при `limit` (насыщение моторов) — это anti-windup; `AP_MotorsMatrix::output_armed_stabilizing()` — порядок: сначала roll/pitch, затем yaw — сколько помещается (`MOT_YAW_HEADROOM` — гарантированный минимум), и только потом подбирается throttle, который влезает в оставшийся диапазон.

### Минимальный патч и SITL
Betaflight: `make SITL` собирает прошивку под Linux (`obj/main/betaflight_SITL.elf`), связывается с симулятором (RealFlight/gazebo через UDP) или просто позволяет подключиться конфигуратором через TCP: изменения в логике CLI/параметров проверяются без железа; для PID-логики — юнит-тесты в `src/test/unit/` (`make test` — gtest), например `pid_unittest.cc`.
ArduPilot: `Tools/autotest/sim_vehicle.py -v ArduCopter --console --map` собирает и запускает SITL; патч → пересборка → полёт в SITL → лог; автотесты `Tools/autotest/arducopter.py` (`./Tools/autotest/autotest.py build.Copter test.Copter.<Test>`).

Минимальное изменение для лабораторной (безопасное, проверяемое): добавить GCS-сообщение/лог-поле (ArduPilot `gcs().send_text(MAV_SEVERITY_INFO, ...)` при событии; Betaflight — новый `DEBUG_` режим с своим значением) или изменить ограничение/значение по умолчанию параметра и увидеть эффект в SITL.

## practice
### Шаг 1. Карта вызовов
Для одной прошивки — список файлов и функций пути gyro → фильтры → PID → mixer → output со ссылками (путь + строка/функция на текущем master). Для второй — только файлы.

### Шаг 2. Сверка с теорией
Ответить по коду с цитатами: откуда берётся D (ошибка или гироскоп)? где anti-windup? в каком порядке применяются фильтры гироскопа? как ограничивается выход миксера при насыщении?

### Шаг 3. Патч
Выбрать минимальное изменение; ветка; сборка SITL; проверка (сообщение в консоли / поле в логе / поведение); `git diff` в отчёт.

### Шаг 4. Отчёт
Страница: карта, ответы на сверку, diff, как проверялось, что не удалось. Лабораторная: путь найден с ссылками, патч собран и проверен в SITL, отчёт.

## diagnostics
- **Симптом:** не нахожу, где используется параметр
  - Возможная причина: имя в коде отличается от имени в GUI (Betaflight: `pidProfile()->pid[PID_ROLL].D`; ArduPilot: `_pid_rate_roll` из `ATC_RAT_RLL_*`).
  - Что сделать: искать по `@Param`/`PG_REGISTER`/`parameter_names.h`, затем по полю структуры.
- **Симптом:** сборка SITL падает
  - Возможная причина: не те зависимости/тулчейн.
  - Что сделать: `Tools/environment_install/install-prereqs-ubuntu.sh` (ArduPilot), `make arm_sdk_install`/`make SITL` по README Betaflight.
- **Симптом:** патч не влияет на поведение в SITL
  - Возможная причина: изменён не тот путь (другой контроллер/режим), либо значение переопределено параметром.
  - Что сделать: `printf`/send_text в точке изменения, проверить, что код исполняется.
- **Симптом:** «теория не сходится» с кодом
  - Возможная причина: это нормально — масштабы, фильтры, порядок операций; иногда — баг.
  - Что сделать: записать расхождение в отчёт с цитатой; при подозрении на баг — issue с воспроизведением в SITL.

## references
- Betaflight — source tree (src/main) | https://github.com/betaflight/betaflight/tree/master/src/main | primary | A
- ArduPilot — ArduCopter scheduler and attitude control sources | https://github.com/ArduPilot/ardupilot/tree/master/ArduCopter | primary | A
- ArduPilot — Developer docs: SITL setup and autotest | https://ardupilot.org/dev/docs/sitl-simulator-software-in-the-loop.html | primary | A

## checklist
- Нашёл путь gyro → PID → mixer в Betaflight и ArduPilot с файлами
- Сверил реализацию D-term и anti-windup с теорией по коду
- Знаю порядок фильтров гироскопа по коду, а не по вики
- Собрал SITL и проверил минимальный патч
- Отчёт с diff и ссылками готов
