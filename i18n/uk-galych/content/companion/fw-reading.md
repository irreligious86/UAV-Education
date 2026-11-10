---
id: fw-reading
title: "Як читати вихідний код прошивки: Betaflight і ArduPilot"
level: L4
readingTime: 45 хв
firmware: Betaflight · ArduPilot
status: published
added: 2026-11-08
tags:
  - вихідний код
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
source: content/companion/fw-reading.md
source_hash: 6ae3972e9635
---

## summary
Документація описує, що параметр «робить»; а що він робить **насправді**, покаже лише код — з порядком операцій, обмеженнями й побічними ефектами. Модуль учить, як ся орієнтувати у двох великих кодових базах і не читати вшитко підряд: як знайти шлях від гіроскопа до моторів, де живуть PID і фільтри, як звірити реалізацію з теорією (і знайти розбіжності), і як внести мінімальну зміну, зібрати й перевірити в SITL — і навіть не торкати реального апарата. Лабораторна: патч зі звітом.

## theory
### Інструменти читання
`git clone` + `grep -rn`/`rg` + редактор із переходом до визначення (VS Code із clangd, або просто `rg "pidController\("`). Для C/C++ прошивок головний прийом — іти від **точки входу планувальника** вниз за викликами, і від **параметра** (його ім'я в коді) до місця використання. `git blame`/`git log -S "имя"` показує, коли і нащо рядок додали — коментар до PR часто пояснює більше, ніж вікі.

### Betaflight: шлях gyro → PID → mixer
Репозиторій `betaflight/betaflight`, код у `src/main/`:

1. **Планувальник**: `scheduler/scheduler.c` — вибирає задачі з таблиці `fc/tasks.c`. Задача `TASK_GYRO` (`taskGyroSample`) і `TASK_FILTER`/`TASK_PID` (`taskMainPidLoop` у `fc/core.c`).
2. **Гіроскоп**: `sensors/gyro.c` — `gyroUpdate()` читає драйвер (`drivers/accgyro/accgyro_spi_icm426xx.c` та ін., через DMA), `gyroFiltering()` застосовує ланцюжок: RPM-notch (`flight/rpm_filter.c`), динамічний notch (`flight/dyn_notch_filter.c`), LPF1/LPF2 (`common/filter.c`: PT1/PT2/PT3/biquad). Порядок фільтрів — саме тут, і з конфігуратора його гет не видно.
3. **PID**: `flight/pid.c` — `pidController()`: для кожної осі помилка = setpoint − gyro, P, I з anti-windup та iterm_relax, D на відфільтрованому гіроскопі (D-LPF, `d_min`/`d_max`), feedforward (`flight/pid_init.c`, `fc/rc.c` — FF рахується з похідної setpoint з інтерполяцією/згладжуванням), TPA, anti-gravity, `pidSum` у `pidData[axis].Sum`.
4. **Мікшер**: `flight/mixer.c` — `mixTable()`: pidSum за осями × матриця мікшера (`mixer_init.c`/`mixer_tricopter.c`) + газ → мотори, `airmode`, обмеження (`mixer_type`: LEGACY/LINEAR/DYNAMIC), idle (`dshot_idle_value`), `motorOutputLimit`.
5. **Вивід**: `drivers/dshot.c` (кодування кадру), `drivers/pwm_output.c`; платформна частина на поточному master — `src/platform/STM32/dshot_bitbang.c`, `src/platform/common/stm32/dshot_dpwm.c`, `pwm_output_dshot_shared.c` — формування кадрів DShot через таймер+DMA; декодування eRPM bidirectional DShot — `drivers/dshot_bitbang_decode.c` (у 4.5 `dshot_dpwm.c` лежав у `src/main/drivers/`).
6. **Blackbox**: `blackbox/blackbox.c` — що і як логується (`blackbox_fields.c`).

Перевірка на теорію: у `pid.c` знайди, як ся рахує D — `-(gyroRateDterm[axis] - previousGyroRateDterm[axis]) * pidFrequency`, де `gyroRateDterm` — гіроскоп, уже пропущений через D-notch і D-LPF1/LPF2 (фільтри стоять до диференціювання), потім множення на `pidCoefficient[axis].Kd` і `dMinFactor` (у master — `dMaxMultiplier`): D береться від **гіроскопа**, а не від помилки (нема «derivative kick» під час руху стіка), а масштаб коефіцієнта — константи в `pid.h`, застосовуються в `pid_init.c` (`PTERM_SCALE`, `ITERM_SCALE`, `DTERM_SCALE`: звідси «безрозмірні» значення в конфігураторі).

### ArduPilot: шлях IMU → rate → motors
Репозиторій `ArduPilot/ardupilot`, транспорт у `ArduCopter/`, бібліотеки в `libraries/`:

{{diagram:ardupilot-fast-loop|Швидка петля ArduCopter: задачі, які планувальник викликає кожен тік, і повільні задачі з власною частотою.}}

1. **Планувальник**: `ArduCopter/Copter.cpp` — таблиця `scheduler_tasks[]`: `FAST_TASK_CLASS(AP_InertialSensor, &copter.ins, update)` → `FAST_TASK(run_rate_controller_main)` → `FAST_TASK(motors_output_main)` → `FAST_TASK(read_AHRS)` → … → `FAST_TASK(update_flight_mode)`; повільні задачі `SCHED_TASK(rc_loop, 250, 130, 3)` з частотою, бюджетом (мкс) і пріоритетом. Нові версії вже вміють виділений rate-потік (`ArduCopter/rate_thread.cpp`, `FSTRATE_ENABLE`) на частоті гіроскопа.
2. **IMU і фільтри**: `libraries/AP_InertialSensor/` — `AP_InertialSensor.cpp` (`update()`), backend-драйвери (`AP_InertialSensor_Invensensev3.cpp`), гармонічний notch `libraries/Filter/HarmonicNotchFilter.cpp`, LPF `Filter/LowPassFilter2p.cpp`.
3. **Rate-контур**: `ArduCopter/Attitude.cpp` — `run_rate_controller_main()` → `attitude_control->rate_controller_run()` у `libraries/AC_AttitudeControl/AC_AttitudeControl_Multi.cpp`: для кожної осі `_motors.set_roll(get_rate_roll_pid().update_all(target, gyro, dt, _motors.limit.roll, …))` у `libraries/AC_PID/AC_PID.cpp` (P, I з limit, D з фільтром `FLTD`, FF, помилка через `FLTE`, ціль через `FLTT`) → `_motors.set_roll(...)`.
4. **Angle-контур**: `AC_AttitudeControl.cpp` — `input_euler_angle_roll_pitch_euler_rate_yaw()` та ін. → кватерніонна помилка → `rate_target_ang_vel` з `ATC_ANG_*_P` і обмеженнями прискорення (`ATC_ACCEL_*_MAX`) — реалізація input shaping.
5. **Мотори**: `ArduCopter/motors.cpp` `motors_output_main()` → `libraries/AP_Motors/AP_MotorsMulticopter.cpp` `output()` (фільтр газу, lift_max за напругою АКБ, spool-логіка) → `AP_MotorsMatrix.cpp` `output_armed_stabilizing()` (розподіл roll/pitch/yaw/throttle за матрицею з пріоритетом і `MOT_YAW_HEADROOM`) → `output_to_motors()` → `SRV_Channel`/`AP_HAL` RCOutput (DShot/PWM).
6. **EKF**: `libraries/AP_NavEKF3/` — `AP_NavEKF3_core.cpp` (`UpdateFilter`), по файлу на тип вимірювань (`*_PosVelFusion.cpp`, `*_MagFusion.cpp`, `*_OptFlowFusion.cpp`), джерела в `AP_NavEKF/AP_NavEKF_Source.cpp`.
7. **Параметри**: `ArduCopter/Parameters.cpp` і `*_Params.cpp` у бібліотеках — блоки `// @Param:` з описом, діапазоном і `@Values` — то і є джерело вікі параметрів.

Перевірка на теорію: в `AC_PID::update_all()` подивися, що D рахується від помилки, пропущеної через `FLTD`, а не від сирого гіроскопа; що I обмежується `IMAX` і не накопичується при `limit` (насичення моторів) — то і є anti-windup; `AP_MotorsMatrix::output_armed_stabilizing()` — порядок: спочатку roll/pitch, потім yaw — скільки вміщається (`MOT_YAW_HEADROOM` — гарантований мінімум), і аж потім добирається throttle, який ще влазить у залишковий діапазон.

### Мінімальний патч і SITL
Betaflight: `make SITL` збирає прошивку під Linux (`obj/main/betaflight_SITL.elf`), зв'язується із симулятором (RealFlight/gazebo через UDP) або просто дає змогу підключитися конфігуратором через TCP: зміни в логіці CLI/параметрів перевіряються без заліза; для PID-логіки — юніт-тести в `src/test/unit/` (`make test` — gtest), наприклад `pid_unittest.cc`.
ArduPilot: `Tools/autotest/sim_vehicle.py -v ArduCopter --console --map` збирає й запускає SITL; патч → перезбирання → політ у SITL → лог; автотести `Tools/autotest/arducopter.py` (`./Tools/autotest/autotest.py build.Copter test.Copter.<Test>`).

Мінімальна зміна для лабораторної (безпечна й перевірювана): додати GCS-повідомлення/поле логу (ArduPilot `gcs().send_text(MAV_SEVERITY_INFO, ...)` під час події; Betaflight — новий режим `DEBUG_` зі своїм значенням) або змінити обмеження/значення за замовчуванням параметра й побачити ефект у SITL.

## practice
### Крок 1. Карта викликів
Для однієї прошивки — список файлів і функцій шляху gyro → фільтри → PID → mixer → output із посиланнями (шлях + рядок/функція на поточному master). Для другої — бай там, лише файли.

### Крок 2. Звірка з теорією
Відповідай за кодом, із цитатами: звідки береться D (помилка чи гіроскоп)? де anti-windup? у якому порядку застосовуються фільтри гіроскопа? як обмежується вихід мікшера при насиченні?

### Крок 3. Патч
Вибери мінімальну зміну; гілка; збирання SITL; перевірка (повідомлення в консолі / поле в лозі / поведінка); `git diff` у звіт.

### Крок 4. Звіт
Сторінка: карта, відповіді на звірку, diff, як перевірялося, що ся не вдало.

### Як шукати в коді, а не гортати без кінця
- `git grep -n "pidController\|mixTable" src/main/flight/` (Betaflight) або `git grep -n "rate_controller_run" ArduCopter libraries/AC_AttitudeControl` (ArduPilot) знаходить точки входу шпаркіше за будь-який зміст.
- Посилання у звіті — на конкретний коміт, а не на `master`: `https://github.com/<org>/<repo>/blob/<sha>/<path>#L<n>`. За місяць `master` поїде, як та фіра з горба, а посилання на коміт залишиться правильним.
- На питання «звідки береться D» відповідай цитатою з коду: диференціюється помилка (уставка мінус гіроскоп) чи лише гіроскоп. Від того залежить, ци апарат ся смикає під час різкого руху стіка.

### Приклад мінімального патча
Найбезпечніший патч — повідомлення під час старту або нове поле в лозі. Воно ніц не змінює в керуванні, зате доводить, що запущена якраз твоя збірка, а не якась інша. ArduPilot: рядок `gcs().send_text(MAV_SEVERITY_INFO, "my build: hello");` в ініціалізації Copter, збирання `./waf configure --board sitl && ./waf copter`, запуск SITL. Повідомлення видно в консолі MAVProxy. Betaflight: збирання `make TARGET=SITL`, свій рядок у виводі під час старту.

### Що має вийти і що записати
- Карта викликів: 6–10 рядків «файл → функція → що робить», у порядку проходження даних від гіроскопа до виходу.
- Відповіді на чотири питання звірки, кожна з цитатою коду (2–5 рядків) і посиланням на коміт.
- `git diff` патча (зазвичай 1–10 рядків), команда збирання, доказ роботи: рядок із консолі або поле з логу.
- Що не вдалося — то чесний пункт звіту, а не провал.

Лабораторну зараховано, коли шлях gyro → PID → mixer знайдено в коді з посиланнями на файли й коміт, мінімальний патч зібрано й перевірено в SITL із доказом із консолі або логу, а звіт містить карту, відповіді на звірку та diff.

## diagnostics
- **Симптом:** не можу знайти, де ся використовує параметр
  - Можлива причина: ім'я в коді відрізняється від імені в GUI (Betaflight: `pidProfile()->pid[PID_ROLL].D`; ArduPilot: `_pid_rate_roll` з `ATC_RAT_RLL_*`).
  - Що зробити: шукати за `@Param`/`PG_REGISTER`/`parameter_names.h`, потім за полем структури.
- **Симптом:** збирання SITL падає
  - Можлива причина: не ті залежності/тулчейн.
  - Що зробити: `Tools/environment_install/install-prereqs-ubuntu.sh` (ArduPilot), `make arm_sdk_install`/`make SITL` за README Betaflight.
- **Симптом:** патч не впливає на поведінку в SITL
  - Можлива причина: змінено не той шлях (інший контролер/режим), або значення перевизначено параметром.
  - Що зробити: `printf`/send_text у точці зміни, перевірити, що код виконується.
- **Симптом:** «теорія не сходиться» з кодом
  - Можлива причина: то нормально — масштаби, фільтри, порядок операцій; часом — баг.
  - Що зробити: записати розбіжність у звіт із цитатою; за підозри на баг — issue з відтворенням у SITL.

## references
- Betaflight — source tree (src/main) | https://github.com/betaflight/betaflight/tree/master/src/main | primary | A
- ArduPilot — ArduCopter scheduler and attitude control sources | https://github.com/ArduPilot/ardupilot/tree/master/ArduCopter | primary | A
- ArduPilot — Developer docs: SITL setup and autotest | https://ardupilot.org/dev/docs/sitl-simulator-software-in-the-loop.html | primary | A

## checklist
- Знайшов-єм шлях gyro → PID → mixer у Betaflight і ArduPilot із файлами
- Звірив-єм реалізацію D-term і anti-windup з теорією за кодом
- Знаю порядок фільтрів гіроскопа за кодом, а не за вікі
- Зібрав-єм SITL і перевірив мінімальний патч
- Звіт із diff і посиланнями готовий
