---
id: px4-architecture
title: "Архітектура PX4: модулі та uORB"
level: L3
readingTime: 25 хв
firmware: PX4 1.14+
status: published
added: 2026-11-08
tags:
  - uORB
  - архітектура
related:
  - px4-intro
  - px4-ros2
next:
  - px4-control
source: content/px4/px4-architecture.md
source_hash: 5453ed2c4c43
---

## summary
PX4 — то не одна програма, а набір незалежних модулів, які ся обмінюють повідомленнями через шину uORB за схемою publish/subscribe. То пояснює майже вшитко в PX4: чому модуль можна перезапустити в польоті, чому ROS 2 бачить нутрощі автопілота напряму, як влаштований шлях від датчика до мотора. Модуль розбирає flight stack і middleware, повідомлення `.msg`, частоти оновлення та інструменти, аби зазирнути всередину системи, яка якраз працює.

## theory
### Два шари
- **Middleware** — драйвери датчиків, зв'язок із зовнішнім світом (MAVLink, uXRCE-DDS), шина uORB і шар симуляції.
- **Flight stack** — алгоритми: оцінювання стану (estimator), контролери, навігатор, commander, розподіл керування (control allocation).

### Шлях від датчика до мотора
1. Драйвери IMU читають FIFO датчика (кілогерци, у сучасних IMU до 8 кГц); гіроскоп після фільтрів ся публікує у `vehicle_angular_velocity` на `IMU_GYRO_RATEMAX` (400 Гц), інтегровані дані — у `vehicle_imu` на `IMU_INTEG_RATE` (200 Гц).
2. **EKF2** зводить докупи IMU, GPS, баро, магнітометр в оцінку орієнтації, швидкості й позиції.
3. **Navigator** вирішує, куди летіти: місія, повернення, утримання.
4. **Position controller** з бажаної позиції робить бажану орієнтацію й тягу.
5. **Attitude controller** → бажані кутові швидкості; **rate controller** → моменти.
6. **Control allocation** перетворює моменти й тягу на команди конкретним моторам/сервам за геометрією рами (`CA_AIRFRAME`, `CA_ROTOR*`).
7. Драйвери виходів — PWM/DShot.

**Commander** — то такий «арбітр»: арм/дизарм, зміна режимів, перевірки готовності, failsafe.

### uORB
Кожен модуль публікує свої топіки й ся підписує на чужі. Топік описаний файлом `.msg` (ім'я в CamelCase → топік у snake_case: `VehicleAttitude.msg` → `vehicle_attitude`), обов'язкове поле — `uint64 timestamp`. Один `.msg` може задавати кілька топіків (`# TOPICS ...`). Шина асинхронна: підписник ся будить, коли прийшли нові дані, тому частоту модуля задає той, хто публікує.

То є та сама ідея, шо й у ROS: саме тому міст uXRCE-DDS виглядає так природно — він просто виносить частину топіків uORB назовні.

### Виконання
Модулі — окремі задачі (на NuttX — потоки з пріоритетами; на Linux/macOS у SITL — потоки процесу). Їх можна запускати й зупиняти командами `<module> start/stop`, дивитися завантаження через `top`, частоти топіків — `uorb top`, вміст — `listener <topic>`.

### Нащо то знати
- Коли ловиш дивну поведінку, ти шукаєш не «параметр», а **модуль і топік**: шо опубліковано, з якою частотою, шо дістав контролер.
- Твій власний код у PX4 — то новий модуль із підпискою на топіки, а не правка чужого.
- Логи ULog — просто запис топіків; коли їх аналізуєш, читаєш ті самі повідомлення.

### Модулі за назвами (де шукати в коді)
`src/modules/`: `sensors` (збір датчиків, `sensor_combined`), `ekf2` (оцінювання стану), `commander` (арм, режими, failsafe, pre-arm), `navigator` (місії, RTL, геозона, `position_setpoint_triplet`), `mc_pos_control` (позиція → орієнтація+тяга), `mc_att_control` (кут → кутова швидкість), `mc_rate_control` (швидкість → моменти, `vehicle_torque_setpoint`/`vehicle_thrust_setpoint`), `control_allocator` (моменти → `actuator_motors`/`actuator_servos`), `logger`, `mavlink`, `uxrce_dds_client`, `land_detector`, `battery_status`, `mc_autotune_attitude_control`. Драйвери — `src/drivers/` (imu, gps, barometer, dshot, pwm_out). Шлях IMU → мотор: `sensors` → `ekf2` → `mc_pos_control` → `mc_att_control` → `mc_rate_control` → `control_allocator` → `dshot`/`pwm_out`.

### Виконання: work queue і пріоритети
На NuttX більшість модулів — не окремі потоки, а елементи **work queue** з пріоритетами (`wq:rate_ctrl` вище, `wq:nav_and_controllers`, `wq:hp_default`, `wq:lp_default` нижче): шпаркі задачі (rate control) ся будять, як тільки прийдуть дані гіроскопа, і виконуються першими; `work_queue status` їх показує. Окремі задачі — logger, mavlink; EKF2 теж працює у work queue (ScheduledWorkItem). `top` у консолі — завантаження CPU за задачами (норма < 70–80% на FMUv5); перевантаження видно, коли ростуть затримки й сиплються попередження.

### Сховище й конфігурація
Параметри — у flash/EEPROM (`param save`, `param reset_all`), місії й геозона — у `dataman` (SD або flash), логи — SD. Завантажувальні скрипти — `ROMFS/px4fmu_common/init.d/` (`rc.*`): який драйвер стартувати, з якими параметрами; airframe-файли `init.d/airframes/` — то і є «вибір airframe» у QGC. Свій модуль ся додає в `boards/<board>/default.px4board` і стартує з `rc.*` або за параметром.

### Розібраний приклад: розбір «апарат розгойдує по roll»
1. `listener vehicle_angular_velocity` — частота ~400 Гц? якщо нижча — перевантаження (`top`).
2. `listener vehicle_rates_setpoint` проти `vehicle_angular_velocity` у лозі: осциляція лиш у фактичних даних → rate P/D; і в setpoint теж → attitude P/position.
3. `uorb top -1` — хто публікує незвично рідко/часто (датчик із пропусками → інновації EKF2).
4. Flight Review → спектр: пік моторів у смузі? → `IMU_GYRO_CUTOFF`/notch (`IMU_GYRO_NF0_FRQ`/`BW`, `IMU_GYRO_DNF_EN`).
Ади, так архітектура ся перетворює на метод: топік → модуль → параметр, а не «підкрутити P».

{{diagram:px4-uorb-path|Шлях даних у PX4 від датчиків до моторів: модулі ся обмінюють топіками uORB, кожен крок можна підглянути командою listener.}}

## practice
### Крок 1. Зазирнути всередину SITL
```
make px4_sitl gz_x500
pxh> top
pxh> uorb top
pxh> listener vehicle_attitude
pxh> listener sensor_combined -n 1
```

### Крок 2. Простежити ланцюжок
Знайди в `uorb top` частоти `sensor_combined`, `vehicle_attitude`, `vehicle_local_position`, `actuator_motors`. Зістав їх із ланцюжком вище: хто шпаркіший, хто повільніший і чому.

### Крок 3. Зупинити й запустити модуль
`mc_rate_control stop` під час зависання в SITL — апарат втрачає керування; `mc_rate_control start` — повертає. Роби то лиш у симуляторі: то демонстрація модульності, а не прийом.

### Крок 4. Прочитати `.msg`
Відкрий `msg/VehicleCommand.msg` (з PX4 1.16 — `msg/versioned/VehicleCommand.msg`) і `msg/OffboardControlMode.msg` у вихідному коді: ці два повідомлення ся тобі придадуть для ROS 2.

### Що має вийти і що записати
- **Крок 1.** `top` показує модулі та їхнє завантаження CPU: у SITL то `px4` як процес, усередині — модулі стека. `uorb top` — таблиця топіків із частотою публікацій і кількістю підписників. `listener sensor_combined -n 1` друкує одне повідомлення з прискореннями й кутовими швидкостями, і в ньому видно поля, які потім знадобляться в ROS 2.
- **Крок 2.** Запиши фактичні частоти чотирьох топіків з `uorb top`. Чого чекати: датчики й орієнтація — сотні герц, локальна позиція — десятки, виходи моторів — з частотою контуру кутових швидкостей. Частоти в SITL залежать від моделі симулятора й можуть відрізнятися від заліза — порівнюй їх між собою, а не з чужими цифрами. Поясни, чому позиція повільніша за орієнтацію: она спирається на GNSS і барометр, які самі по собі повільні.
- **Крок 3.** Після `mc_rate_control stop` апарат у SITL ся перевертає або падає за частки секунди: без контуру кутових швидкостей ніц не тримає орієнтацію. Після `start` модуль знов підписаний на топіки, але апарат, шо впав, треба перезапустити. То наочно показує, шо модулі — окремі процеси, пов'язані лиш топіками.
- **Крок 4.** Випиши поля `VehicleCommand` (команда, сім параметрів, адресати) і `OffboardControlMode` (який тип уставок дозволений) — то пряма підготовка до модуля PX4 + ROS 2.

### Лабораторна
Звіт на сторінку: ланцюжок від IMU до моторів з назвами модулів і топіків та їхніми частотами, знятими в SITL.

Лабораторна ся зараховує, коли частоти чотирьох топіків зняті через `uorb top` і записані, `listener` виконано щонайменше на двох топіках із розбором полів, а звіт описує ланцюжок «датчики → оцінювання → контур кутових швидкостей → мотори» з назвами модулів і топіків.

## diagnostics
- **Симптом:** контролер не реагує на setpoint
  - Можлива причина: топік не публікується або публікується з нульовою частотою.
  - Що зробити: `uorb top`, `listener <topic>` — ци є дані.
- **Симптом:** модуль не стартує
  - Можлива причина: не зібраний для цієї плати або залежить від драйвера, якого нема.
  - Що зробити: перевірити board config і вивід під час старту.
- **Симптом:** у лозі нема потрібного топіка
  - Можлива причина: не ввімкнений у профіль логування (`SDLOG_PROFILE`).
  - Що зробити: увімкнути профіль, повторити політ.

## references
- PX4 Architectural Overview | https://docs.px4.io/main/en/concept/architecture.html | primary | A
- PX4 uORB Messaging | https://docs.px4.io/main/en/middleware/uorb.html | primary | A
- PX4 Control Allocation | https://docs.px4.io/main/en/concept/control_allocation.html | primary | A
- PX4-Autopilot msg definitions (GitHub) | https://github.com/PX4/PX4-Autopilot/tree/main/msg | primary | A

## checklist
- Можу назвати ланцюжок модулів від IMU до моторів
- Розумію publish/subscribe і роль timestamp
- Використовував-єм `top`, `uorb top`, `listener` у SITL
- Знаю, де лежать `.msg` і як ім'я файлу стає топіком
