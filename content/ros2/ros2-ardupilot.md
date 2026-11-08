---
id: ros2-ardupilot
title: "ROS 2 + ArduPilot: AP_DDS и MAVROS, один узел — два маршрута"
level: L3
readingTime: 45 мин
firmware: ArduPilot
status: published
added: 2026-11-08
tags:
  - ROS 2
  - ArduPilot
  - AP_DDS
  - MAVROS
  - GUIDED
related:
  - ros2-px4
  - ap-companion
  - mav-sdk
next:
  - per-tracking
---

## summary
У ArduPilot два пути в ROS 2. **AP_DDS** — встроенный в прошивку DDS-клиент (тот же принцип, что uXRCE-DDS у PX4): топики `/ap/*` в ENU и стандартных типах ROS, сервисы арма и смены режима, управление скоростью через `/ap/cmd_vel`. **MAVROS** — мост MAVLink ↔ ROS, работающий с любой прошивкой и с полным набором MAVLink-функций, ценой лишнего слоя. Модуль разбирает оба по исходникам и документации, сравнивает с маршрутом PX4 и показывает, как тот же автомат состояний из модуля ros2-px4 летает квадрат на ArduPilot через AP_DDS. Лабораторная: квадрат в SITL через AP_DDS, затем через MAVROS, и сравнительная таблица задержек и удобства.

## theory
### AP_DDS: как подключить
В прошивке — клиент DDS (`libraries/AP_DDS`), снаружи — агент micro-ROS (`micro_ros_agent`), который выводит данные в DDS-сеть ROS 2.

- Параметры: `DDS_ENABLE = 1`; транспорт UDP — `DDS_UDP_PORT` (по умолчанию 2019) и адрес агента `DDS_IP0..3`; транспорт serial — `SERIALn_PROTOCOL = 45` на нужном порту. `DDS_DOMAIN_ID` — домен ROS 2.
- SITL: сборка с поддержкой DDS (`./waf configure --board sitl --enable-DDS`), запуск `sim_vehicle.py -v ArduCopter --enable-DDS`, агент: `ros2 run micro_ros_agent micro_ros_agent udp4 -p 2019`.
- Типы ArduPilot-специфичных сообщений — пакет `ardupilot_msgs` (в репозитории ArduPilot, `Tools/ros2/ardupilot_msgs`): `Status`, `GlobalPosition`, сервисы `ArmMotors`, `ModeSwitch`, `Takeoff`.

{{diagram:uxrce-scheme|Схема та же, что у PX4: клиент в прошивке, агент на companion, обычные топики ROS 2 снаружи.}}

### Что публикует и принимает AP_DDS
| Топик/сервис | Тип | Назначение |
|---|---|---|
| `/ap/pose/filtered` | `geometry_msgs/PoseStamped` | локальная поза из EKF относительно home, ENU (в `header.frame_id` прошивка пишет `base_link`) |
| `/ap/twist/filtered` | `geometry_msgs/TwistStamped` | скорость |
| `/ap/geopose/filtered`, `/ap/navsat` | `geographic_msgs/GeoPoseStamped`, `sensor_msgs/NavSatFix` | глобальная поза, GNSS |
| `/ap/battery`, `/ap/status`, `/ap/rc` | `sensor_msgs/BatteryState`, `ardupilot_msgs/Status`, `ardupilot_msgs/Rc` | батарея; armed, mode, flying, external_control, failsafe |
| `/ap/tf_static`, `/ap/clock`, `/ap/time` | tf2, время | крепления, часы для sim time |
| `/ap/cmd_vel` (вход) | `geometry_msgs/TwistStamped` | скорость в GUIDED; frame `map` (ENU) или `base_link` |
| `/ap/cmd_gps_pose` (вход) | `ardupilot_msgs/GlobalPosition` | глобальная цель в GUIDED |
| `/ap/arm_motors`, `/ap/mode_switch`, `/ap/prearm_check`, `/ap/experimental/takeoff` | сервисы | арм, режим (номер режима Copter: GUIDED = 4, LAND = 9), предарм, взлёт |

Важно: AP_DDS сам переводит ENU ↔ NED — для `cmd_vel` по `header.frame_id` (`map` — мировые ENU, `base_link` — корпус). То есть в отличие от PX4, ваш ROS-узел живёт полностью в соглашениях ROS. QoS: позы и скорости — BEST_EFFORT, `/ap/status` и `tf_static` — RELIABLE + TRANSIENT_LOCAL (подписчик BEST_EFFORT совместим и с тем, и с другим).

### Порядок действий в ArduPilot
ArduCopter армится только в режиме, разрешающем арм (GUIDED подходит), и только после pre-arm проверок. Взлёт в GUIDED — отдельная команда (сервис takeoff = `MAV_CMD_NAV_TAKEOFF`), без неё аппарат на земле игнорирует горизонтальные уставки. Последовательность в узле: GUIDED → arm → takeoff(alt) → уставки скорости/позиции → LAND. Таймаут уставок скорости в GUIDED — `GUID_TIMEOUT` (секунды): если `cmd_vel` перестал приходить, аппарат остановится. Это тот же принцип «доказательства жизни», что Offboard у PX4.

### MAVROS
MAVROS — узел, который держит MAVLink-соединение и раскладывает его по плагинам: `/mavros/state` (подключение, armed, mode), `/mavros/local_position/pose`, `/mavros/setpoint_position/local`, `/mavros/setpoint_velocity/cmd_vel`, сервисы `/mavros/cmd/arming`, `/mavros/set_mode`, `/mavros/cmd/takeoff`, `/mavros/mission/push`, параметры, геозоны, полный доступ к любому MAVLink-сообщению через `mavros_msgs/Mavlink`. Он тоже переводит ENU ↔ NED. Запуск: `ros2 launch mavros apm.launch fcu_url:=udp://:14550@` (подключение к SITL или к роутеру на companion).

Когда MAVROS лучше AP_DDS: нужен функционал, которого нет в AP_DDS (миссии, параметры, камера, произвольные MAVLink-сообщения); парк смешанный (одна кодовая база для ArduPilot и PX4 через MAVLink); прошивка без DDS. Когда AP_DDS лучше: меньше слоёв и задержка, стандартные типы ROS, нет MAVLink-трафика на companion для ROS-части.

### Сравнение маршрутов
| | PX4 uXRCE-DDS | ArduPilot AP_DDS | MAVROS |
|---|---|---|---|
| Что на проводе | uORB-структуры через XRCE | DDS-клиент, стандартные типы ROS | MAVLink |
| Система координат на стороне ROS | NED/FRD (конвертируете сами) | ENU/FLU (конвертирует прошивка) | ENU/FLU (конвертирует MAVROS) |
| Совместимость версий | px4_msgs = версия PX4, суффиксы _vN | ardupilot_msgs из той же ветки | диалект MAVLink, устойчиво |
| Охват функций | всё, что в dds_topics.yaml | набор /ap/*, растёт | почти весь MAVLink |
| Внешнее управление | Offboard, поток > 2 Гц | GUIDED, `GUID_TIMEOUT` | GUIDED/Offboard через setpoint_* |

### Один автомат, две обёртки
`ap_dds_square.py` использует тот же `OffboardFSM`, что узел PX4. Отличия только в обёртке: наблюдения из `/ap/status` и `/ap/pose/filtered` (ENU → NED для автомата), «режим внешнего управления» = GUIDED, запрос арма превращается в «сначала GUIDED, потом arm», после выхода на высоту — сервис takeoff, уставки позиции автомата превращаются в скорость (П-регулятор с ограничением 3 м/с) на `/ap/cmd_vel` в фрейме `map`. Логика защит и все тесты автомата остаются в силе.

## practice
### Шаг 1. SITL с DDS
```bash
docker compose --profile ardupilot up --build    # или нативно: waf configure --enable-DDS, sim_vehicle.py --enable-DDS
docker compose run --rm ros bash
ros2 topic list | grep /ap/
ros2 topic echo /ap/status --once
ros2 service call /ap/mode_switch ardupilot_msgs/srv/ModeSwitch "{mode: 4}"
```

### Шаг 2. Квадрат через AP_DDS
`ros2 launch uav_ros2_labs ap_square.launch.py`. Сверьте переходы автомата в логе с режимами в Mission Planner/QGC. Постройте траекторию из `/tmp/ap_flight.csv`. Остановите узел посреди квадрата и измерьте по логу ArduPilot, через сколько аппарат остановился — сравните с `GUID_TIMEOUT`.

### Шаг 3. Тот же квадрат через MAVROS
Напишите обёртку `mavros_square.py` (тот же автомат): `/mavros/state` → armed/mode, `/mavros/local_position/pose` → позиция, `/mavros/setpoint_position/local` → уставки, сервисы `cmd/arming`, `set_mode` (custom_mode "GUIDED"), `cmd/takeoff`. Проверьте, что тесты автомата не пришлось трогать.

### Шаг 4. Сравнение
Измерьте задержку «уставка → изменение скорости в позе» для AP_DDS и MAVROS (по меткам времени в bag), загрузку CPU агента и MAVROS, и заполните таблицу из теории своими цифрами.

Лабораторная засчитывается, когда квадрат пролетан через AP_DDS (график, переходы), проверен `GUID_TIMEOUT`, есть обёртка MAVROS с тем же автоматом и таблица сравнения с измерениями.

## diagnostics
- **Симптом:** `/ap/*` топиков нет
  - Возможная причина: SITL собран без `--enable-DDS`, `DDS_ENABLE = 0`, агент на другом порту или в другом домене.
  - Что сделать: сборка с DDS; порт 2019; одинаковый `ROS_DOMAIN_ID`/`DDS_DOMAIN_ID`.
- **Симптом:** `arm_motors` возвращает false
  - Возможная причина: режим не разрешает арм или не пройдены pre-arm проверки.
  - Что сделать: сначала GUIDED; `/ap/prearm_check`; STATUSTEXT в GCS.
- **Симптом:** уставки `cmd_vel` игнорируются на земле
  - Возможная причина: не выполнен takeoff в GUIDED.
  - Что сделать: сервис takeoff, дождаться высоты, потом скорости.
- **Симптом:** аппарат летит «на восток вместо севера»
  - Возможная причина: уставка в ENU отправлена как NED (или наоборот), frame_id не тот.
  - Что сделать: frame_id `map` для мировых ENU; конвертация только на границе.

## references
- ArduPilot — AP_DDS README (setup, topics, services) | https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_DDS/README.md | primary | A
- ArduPilot — ROS 2 with ArduPilot (dev docs) | https://ardupilot.org/dev/docs/ros2.html | primary | A
- ArduPilot — AP_DDS topic and service tables (source) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/AP_DDS | primary | A
- MAVROS | https://github.com/mavlink/mavros | primary | A
- ArduPilot — Copter commands in Guided mode | https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html | primary | A

## checklist
- Подключаю ArduPilot к ROS 2 через AP_DDS (параметры, агент, сборка SITL)
- Знаю топики и сервисы /ap/* и в каких фреймах они
- Выдерживаю порядок GUIDED → arm → takeoff → уставки → LAND и знаю GUID_TIMEOUT
- Использую MAVROS там, где не хватает AP_DDS
- Сравниваю маршруты PX4/AP_DDS/MAVROS по фактам и измерениям
- Переиспользую один автомат состояний для разных автопилотов
