---
id: px4-ros2
title: "PX4 и ROS 2: uXRCE-DDS и offboard"
level: L4
readingTime: 45 мин
firmware: PX4 1.18 (сверено с исходниками v1.17.0; отличия 1.18.0 отмечены) · ROS 2 Humble (рекомендован документацией v1.17) / Jazzy · Micro XRCE-DDS Agent v2.4.2/v2.4.3
status: published
added: 2026-11-08
tags:
  - ROS 2
  - uXRCE-DDS
  - offboard
related:
  - px4-architecture
  - ap-companion
next:
  - px4-companion-jetson
---

## summary
В PX4 топики uORB можно вывести прямо в ROS 2: клиент uXRCE-DDS на полётнике и агент на companion-компьютере прокидывают сообщения в обе стороны. Это даёт ROS-узлам доступ к ориентации, позиции и командам без MAVLink-обёртки. Модуль показывает, как устроен мост изнутри (откуда берутся имена топиков с суффиксом `_vN`, частоты и QoS, как переводятся метки времени), как поднять его на SITL и на борту, что такое `px4_msgs`, как устроено offboard-управление (`OffboardControlMode` + `TrajectorySetpoint` + `VehicleCommand`) и по какому именно правилу PX4 выкидывает из Offboard, если ты замолчал. Лабораторная: скрипт читает `dds_topics.yaml` и определения сообщений PX4 1.17.0, выводит имена топиков, предельные частоты и нагрузку на UART, считает момент выхода из Offboard; затем — свой offboard-узел в SITL.

## theory
### Мост uXRCE-DDS
- **Клиент** `uxrce_dds_client` в PX4 публикует/подписывает ограниченный набор топиков uORB (список — `dds_topics.yaml`).
- **Агент** `MicroXRCEAgent` на companion или ПК принимает их по UDP или serial и выставляет в DDS — то есть в ROS 2.
- Сообщения на стороне ROS 2 — пакет `px4_msgs`; **ветка `px4_msgs` должна соответствовать версии PX4** (для 1.17 — `release/1.17`), иначе несовпадение определений. С 1.16 сообщения версионируются: топик сообщения с версией больше 0 получает суффикс `_vN`. В 1.17.0 это выходные `vehicle_status_v1`, `vehicle_local_position_v1`, `battery_status_v1`, `home_position_v1`, `airspeed_validated_v1`, `arming_check_request_v1` и входные `vehicle_attitude_setpoint_v1`, `arming_check_reply_v1`; в 1.16 — только `vehicle_status_v1`, в 1.15 суффиксов нет. Для разных версий есть узел-переводчик сообщений (Message Translation Node, экспериментальный с 1.16).

Топики появляются в ROS 2 как `/fmu/out/*` (из PX4) и `/fmu/in/*` (в PX4). Имя собирает клиент: строка из `dds_topics.yaml` плюс `_vN`, если в `.msg` задано `MESSAGE_VERSION` = N > 0 (`generate_topic_name()` в `src/modules/uxrce_dds_client/utilities.hpp`). Поэтому `VehicleLocalPosition.msg` (версия 1) даёт `/fmu/out/vehicle_local_position_v1`, а `TrajectorySetpoint.msg` (версия 0) — `/fmu/in/trajectory_setpoint` без суффикса. Топика нет в `dds_topics.yaml` — нет его и в ROS 2, сколько ни ищи: в 1.17.0 там 27 выходных и 38 входных топиков, а `vehicle_angular_velocity`, например, закомментирован. Чтобы добавить топик, правят `dds_topics.yaml` и пересобирают прошивку — параметра для этого нет.

{{diagram:px4-dds-topic-naming|Суффикс _v1 зависит от версии сообщения, а не от направления: старое имя без суффикса после обновления до 1.17 молчит.}}

Версия меняется при несовместимом изменении полей, и следующий релиз может её поднять. В PX4 1.18.0 (вышел 24 ноября 2026, UTC) `VehicleStatus` стал версии 4, и топик называется `/fmu/out/vehicle_status_v4`; `vehicle_command_ack` получил суффикс `_v1`, предел `vehicle_attitude` снижен со 100 до 50 Гц, а `arming_check_request_v1` потерял предел 5 Гц (без `rate_limit` теперь действует интервал по умолчанию 4 мс, до 250 Гц); добавились выходные топики (`vtx`, `input_rc`, `config_overrides_confirm_v1` и другие) — полный список даёт вывод шага 1 для v1.18.0 (проверено лабораторной ниже на тегах v1.17.0 и v1.18.0). Вывод: имя топика в узле не пишут руками, а собирают из константы `MESSAGE_VERSION` класса сообщения — тогда обновление `px4_msgs` вместе с прошивкой само меняет имя.

Внутри клиент работает так (вывод из кода `uxrce_dds_client`, v1.17.0). При старте он создаёт сессию с агентом (ключ `UXRCE_DDS_KEY`, домен `UXRCE_DDS_DOM_ID`), затем для каждой строки `publications` — DataWriter, для каждой строки `subscriptions` — DataReader. Связь клиент проверяет пингами: если поток в одну из сторон нулевой, он раз в секунду пингует агента и после трёх пропущенных ответов (~3 с) разрывает сессию и создаёт её заново (`checkConnectivity()`). `UXRCE_DDS_TX_TO` (3 с) рвёт сессию, если клиент сам ничего не отправил столько секунд, `UXRCE_DDS_RX_TO` (по умолчанию −1, выкл.) — если ничего не принял. Поэтому после перезапуска агента клиент обычно восстанавливает сессию сам, без перезагрузки полётника (вывод из кода, на стенде не проверено); если после перезапуска топики `/fmu/in/*` не доходят, включи `UXRCE_DDS_RX_TO`. Клиент шлёт все топики из `publications` независимо от того, подписан ли на них кто-нибудь в ROS 2: нагрузка на канал определяется списком в прошивке, а не твоими узлами.

### Частоты, QoS и пропускная способность
Частоту каждого выходного топика ограничивает поле `rate_limit` в `dds_topics.yaml`: клиент вызывает `orb_set_interval()` с периодом 1000/`rate_limit` мс, округлённым вниз до целых миллисекунд, а без `rate_limit` — 10 мс (`UXRCE_DEFAULT_POLL_INTERVAL_MS`). Значит, топик без `rate_limit` идёт **не чаще 100 Гц**, даже если в uORB он публикуется на 250 Гц, а в стоковом `dds_topics.yaml` 1.17.0 нет значений выше 100 — так что все выходные топики ограничены 100 Гц (свой `rate_limit: 200.` в собственной сборке поднял бы предел): `vehicle_odometry` и `vehicle_attitude` — до 100 Гц, `vehicle_local_position_v1` — до 50, `vehicle_status_v1` — до 5, `battery_status_v1` — до 1 Гц. Реальная частота может быть ниже предела, если модуль PX4 публикует реже. В 1.18.0 интервал по умолчанию — 4 мс (250 Гц), период округляется до ближайшей миллисекунды, а `rate_limit: 0` (или `unlimited`) снимает предел (`generate_dds_topics.py`, `dds_topics.h.em`, v1.18.0).

QoS зашит в клиент: выходные DataWriter — BEST_EFFORT, TRANSIENT_LOCAL, KEEP_LAST; входные DataReader — BEST_EFFORT, VOLATILE, KEEP_LAST. По правилам совместимости DDS из этого следует простое правило: **подписчик в ROS 2 на `/fmu/out/*` обязан быть BEST_EFFORT** (RELIABLE-подписчик с best-effort-писателем не совместим — топик виден в `ros2 topic list`, но данных нет), а издатель в `/fmu/in/*` может быть любым. Готовый профиль — `qos_profile_sensor_data`.

Пропускная способность — главный ограничитель на UART. Байт 8N1 занимает 10 бит, поэтому 921600 бод — это 92160 байт/с. Размер сообщения в CDR считается по полям с выравниванием каждого поля на его размер (тот же обход, что в `Tools/msg/templates/ucdr/msg.h.em`): `VehicleOdometry` — 114 байт, `VehicleLocalPosition` — 216, `TrajectorySetpoint` — 64, `OffboardControlMode` — 15. На serial каждый сэмпл добавляет подзаголовок и заголовок WRITE_DATA (4 + 4 байта, с выравниванием до 4), а каждое сообщение — заголовок XRCE (4 байта: у сессии PX4 0x81 нет ключа клиента) и кадрирование (флаг 0x7E, адреса, длина, CRC — 7 байт), общие для отправленных вместе сэмплов: не больше ~23 байт на сэмпл, если каждый уходит отдельно, — пессимистичная оценка курса по исходникам клиента. Если все 27 выходных топиков 1.17.0 пойдут на своих пределах, это до 107 495 байт/с (верхняя оценка) — больше, чем вмещает 921600 бод. На практике часть топиков публикуется реже предела (`vehicle_command_ack` — только на команду), но запас тонкий: фактический поток показывает `uxrce_dds_client status` (строки `Payload tx` и `Payload rx`, байт/с). `Payload tx` считает только данные CDR, без заголовков (до ~23 байт на сэмпл) (`num_payload_sent += topic_size` в `dds_topics.h.em`): при всех топиках на пределах он покажет ~78 900 байт/с, а по проводу пойдёт до ~107 500. Поэтому `Payload tx` держат ниже ~50 % байт/с выбранной скорости (ориентир курса: с заголовками это около 70 % линии; при 921600 — ниже ~46 000 байт/с). Решения: 1.5–3 Мбод (клиент принимает `-b` до 3000000), Ethernet, где он есть, или урезанный `dds_topics.yaml` в своей сборке.

### Метки времени и timesync
У агента и PX4 разные часы: Linux считает время от эпохи или запуска системы, PX4 — от включения полётника. При `UXRCE_DDS_SYNCT = 1` (по умолчанию) клиент измеряет смещение между ними и переводит поля `timestamp` и `timestamp_sample` каждого сообщения: на выходе прибавляет смещение, на входе вычитает его. Для входящих сообщений есть два правила из шаблона сериализации (`Tools/msg/templates/ucdr/msg.h.em`): `timestamp = 0` заменяется временем прихода (`hrt_absolute_time()`), а метка «из будущего» обрезается до текущего времени PX4. Метка из прошлого не исправляется — и это ловушка. Узел, который берёт время с часов, сдвинутых на полторы секунды (симуляционное время при `use_sim_time`, неверное смещение, timesync выключен), шлёт `OffboardControlMode`, который PX4 видит уже устаревшим: Offboard недоступен, хотя поток идёт 10 Гц. Проверка — `ros2 topic echo --once /fmu/out/timesync_status` и строка `timesync converged: true` в `uxrce_dds_client status`. Надёжный вариант для своих узлов — ставить метку часами узла после схождения timesync или отправлять 0 и отдать штамповку PX4.

### Offboard: три сообщения
1. **`OffboardControlMode`** — говорит PX4, *чем* ты управляешь (позиция, скорость, ускорение, ориентация, угловые скорости, тяга и моменты, напрямую актуаторы). Должен идти потоком **до** перехода в Offboard и всё время в нём; правило выхода — ниже.
2. **`TrajectorySetpoint`** — сама цель: позиция/скорость/ускорение в NED (Z вниз!), yaw и yawspeed. Поле со значением NaN означает «не управлять этой величиной»: так задают, например, только скорость при `position = [NaN, NaN, NaN]`.
3. **`VehicleCommand`** — команды: сменить режим (`VEHICLE_CMD_DO_SET_MODE` = 176, Offboard = base 1, custom 6), арм (`VEHICLE_CMD_COMPONENT_ARM_DISARM` = 400, param1 = 1). Подтверждение — `VehicleCommandAck` в `/fmu/out/vehicle_command_ack`.

Та же философия, что GUIDED в ArduPilot: companion советует потоком, автопилот следит за таймаутом и всегда может быть перехвачен пилотом.

### Что именно проверяет PX4 и что будет при обрыве
Документация формулирует правило как «PX4 выходит из Offboard, если частота `OffboardControlMode` ниже примерно 2 Гц». Код точнее (`HealthAndArmingChecks/checks/offboardCheck.cpp`, v1.17.0): сигнал Offboard считается доступным, если в последнем сообщении поднят хотя бы один флаг **и** `timestamp` этого сообщения моложе `COM_OF_LOSS_T` (1.0 с по умолчанию). Плюс условия по оценке состояния: флаг `position` требует валидной локальной позиции, `velocity` — валидной скорости, `acceleration` (а с 1.18.0 и `attitude`) — валидной ориентации. Отсюда три вывода из кода. Первый: время выхода — это метка последнего сообщения плюс `COM_OF_LOSS_T`; узел на 10 Гц, остановленный в 5.0 с, последний раз отправил в 4.9 с, и PX4 выйдет из Offboard в 5.9 с. Второй: «2 Гц» — запас, а не порог: на 2 Гц один пропуск даёт паузу ровно 1.0 с — с учётом задержки доставки сигнал уже теряется. Третий: зависание узла на 1.2 с (тяжёлый инференс в том же процессе) выбивает из Offboard при любой частоте — таймер публикации держат в отдельном потоке или процессе.

Что произойдёт дальше, задаёт `COM_OBL_RC_ACT`: 0 — Position (по умолчанию), 1 — Altitude, 2 — Stabilized (до 1.16 — Manual), 3 — Return, 4 — Land, 5 — Hold, 6 — Terminate, 7 — Disarm. Переход выполняет `checkModeFallback()` в `failsafe.cpp`. В 1.17, если выбран Position, Altitude или Stabilized, а ручного управления в этот момент нет, PX4 выполняет действие потери RC `NAV_RCL_ACT` (по умолчанию 2 — Return; в 1.15 и 1.16 этой проверки не было; в 1.18 то же, а при новом `NAV_RCL_ACT` = 7 «Hold без failsafe» вместо ручного режима берётся Hold — `failsafe.h`, v1.18.0). Для аппарата без пульта, управляемого только companion, разумно сразу ставить `COM_OBL_RC_ACT` = 4 (Land) или 3 (Return): в 1.17 без ручного управления PX4 и так подменит Position на `NAV_RCL_ACT`, но в 1.16 и раньше, а также в 1.17 при живом пульте без пилота, Position означает висение на месте до разряда батареи.

Две смежные защиты путают с этой. `NAV_DLL_ACT` (потеря связи с GCS, по умолчанию 0 — выключено, таймаут `COM_DL_LOSS_T` = 10 с) срабатывает по heartbeat MAVLink от наземной станции; DDS-канал companion в нём не участвует. `COM_RCL_EXCEPT` бит 2 и `COM_DLL_EXCEPT` бит 2 отключают реакцию на потерю RC и GCS в режиме Offboard — включай их, только если companion действительно должен лететь без пульта и станции, а `COM_OBL_RC_ACT` настроен безопасно.

{{diagram:px4-offboard-loss-timeline|PX4 выходит из Offboard через COM_OF_LOSS_T после метки последнего сообщения (4.9 → 5.9 с); с метками из прошлого Offboard недоступен вовсе, даже при потоке 10 Гц.}}

{{lesson:ros2-px4|Там из этих трёх сообщений собран автомат состояний миссии с обработкой вмешательства пилота и отладкой по bag-файлам.}}

### Против MAVLink/MAVSDK
MAVLink через MAVSDK проще для простых задач и не требует ROS. uXRCE-DDS — когда нужны ROS-экосистема (навигация, зрение, планирование), низкая задержка и доступ к внутренним топикам. Цена — привязка к версии прошивки: MAVLink-сообщения стабильны годами, а `px4_msgs` меняются с каждым релизом.

### Настройка моста на реальном борту
PX4: `UXRCE_DDS_CFG` = TELEM2 (значение 102), `SER_TEL2_BAUD` = 921600 (это и умолчание TELEM2); на companion: `MicroXRCEAgent serial --dev /dev/ttyTHS1 -b 921600` (Jetson; имя порта зависит от платы и JetPack — `ttyTHS0` или `ttyTHS1`, проверка петлёй в px4-companion-jetson) или `udp4 -p 8888` для SITL/Wi-Fi/Ethernet. Агент — ветки v2.x: документация PX4 1.17 даёт v2.4.3 для Jazzy и v2.4.2 для Humble и Foxy, а v3.x со стоковым клиентом PX4 не совместим (1.18 можно собрать под него с `UXRCE_DDS_CLIENT_USE_DDS_V3`). Для Ethernet `UXRCE_DDS_CFG` = 1000, адрес агента — `UXRCE_DDS_AG_IP` в виде int32 (192.168.1.2 → −1062731518), порт — `UXRCE_DDS_PRT` (8888). Проверка: `ros2 topic list | grep fmu`, `ros2 topic hz /fmu/out/vehicle_odometry` (ожидаемо до 100 Гц). Если топиков нет: порт занят MAVLink (`MAV_1_CONFIG` на том же TELEM2 — конфликт), скорость, `uxrce_dds_client status` в консоли PX4.

Ещё три параметра решают «топики не видны» на системах с несколькими участниками. `UXRCE_DDS_DOM_ID` должен совпадать с `ROS_DOMAIN_ID` узлов (в SITL скрипт `rcS` копирует `ROS_DOMAIN_ID` из окружения сам). `UXRCE_DDS_NS_IDX` = N (с 1.17) добавляет пространство имён: топики становятся `/uav_N/fmu/...`. При нескольких полётниках на одном агенте у каждого свой `UXRCE_DDS_KEY` (ключ сессии, по умолчанию 1) — иначе сессии вытесняют друг друга.

### Справочник: параметры и интерфейсы (PX4 1.17.0)
| Параметр / интерфейс | Умолчание | Значения, единица | Что делает |
|---|---|---|---|
| `UXRCE_DDS_CFG` | 0 (выкл.) | 101 TELEM1, 102 TELEM2, 1000 Ethernet… | порт клиента |
| `SER_TEL2_BAUD` | 921600 | бод | скорость TELEM2 |
| `UXRCE_DDS_DOM_ID` | 0 | целое | домен DDS = `ROS_DOMAIN_ID` |
| `UXRCE_DDS_KEY` | 1 | ≠ 0, уникальный | ключ сессии на агенте |
| `UXRCE_DDS_PRT` | 8888 | 0–65535 | UDP-порт агента (Ethernet) |
| `UXRCE_DDS_AG_IP` | 2130706433 (127.0.0.1) | int32 | IP агента (Ethernet) |
| `UXRCE_DDS_PTCFG` | 0 | 0 обычный, 1 localhost, 2 свой профиль | участник на агенте |
| `UXRCE_DDS_SYNCT` | 1 | 0/1 | перевод меток времени |
| `UXRCE_DDS_SYNCC` | 0 | 0/1 | ставить системные часы PX4 по агенту |
| `UXRCE_DDS_TX_TO` / `RX_TO` | 3 / −1 | с (< 1 — выкл.) | разрыв сессии, если клиент столько секунд ничего не отправил / не принял; пропажу агента ловят 3 пропущенных пинга |
| `UXRCE_DDS_NS_IDX` | −1 | −1…9999 (с 1.17) | пространство имён `uav_N` |
| `UXRCE_DDS_FLCTRL` | — | 0/1 | аппаратное управление потоком; **только с 1.18.0** |
| `COM_OF_LOSS_T` | 1.0 | 0–60 с | таймаут сигнала Offboard |
| `COM_OBL_RC_ACT` | 0 (Position) | 0–7 | действие при потере Offboard |
| `NAV_RCL_ACT` | 2 (Return) | 1–7 (7 — с 1.18) | потеря RC; с 1.17 — и подмена для 0–2 выше |
| `NAV_DLL_ACT` / `COM_DL_LOSS_T` | 0 / 10 | действие / с | потеря GCS (MAVLink) |
| `COM_RCL_EXCEPT`, `COM_DLL_EXCEPT` | 0 | бит 2 = Offboard | исключения failsafe; бит 1 в 1.18 — все авторежимы (в 1.17 — Hold) |
| `rate_limit` в `dds_topics.yaml` | нет → 10 мс (100 Гц) | Гц | предел частоты выходного топика; в стоке ≤ 100 |
| `MicroXRCEAgent serial --dev <порт> -b <бод>` / `udp4 -p 8888` | — | агент v2.4.x | сторона companion |
| `uxrce_dds_client status` | — | консоль PX4 | связь, `Payload tx/rx`, timesync |

### Системы координат — главный источник ошибок
PX4 работает в NED (север-восток-вниз) и FRD (вперёд-вправо-вниз); ROS 2 (REP-103) — ENU и FLU. `TrajectorySetpoint.position = [x, y, z]` — NED: z = −10 означает 10 м вверх. Переводы: ENU→NED: (x, y, z) → (y, x, −z); FLU→FRD: (x, y, z) → (x, −y, −z); курс: yaw_NED = π/2 − yaw_ENU (в ENU курс отсчитывают от востока против часовой, в NED — от севера по часовой). Пакет `px4_ros_com` содержит утилиты преобразования; MAVROS делает это сам. Ошибка знака по z — классический «аппарат ушёл в землю при взлёте в симуляторе».

{{lesson:math-linalg-rot|Если перевод ENU↔NED и кватернионы курса делаешь сам, а не утилитой, там разобрана математика поворотов без ошибок знака.}}

### Минимальный offboard-узел (Python, rclpy)
```python
import rclpy
from rclpy.node import Node
from px4_msgs.msg import OffboardControlMode, TrajectorySetpoint, VehicleCommand
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy

class Offboard(Node):
    def __init__(self):
        super().__init__("offboard_min")
        qos = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                         history=HistoryPolicy.KEEP_LAST, depth=1)   # PX4 publishes best-effort
        self.mode_pub = self.create_publisher(OffboardControlMode, "/fmu/in/offboard_control_mode", qos)
        self.sp_pub = self.create_publisher(TrajectorySetpoint, "/fmu/in/trajectory_setpoint", qos)
        self.cmd_pub = self.create_publisher(VehicleCommand, "/fmu/in/vehicle_command", qos)
        self.n = 0
        self.create_timer(0.1, self.step)                               # 10 Hz > 2 Hz minimum

    def cmd(self, command, p1=0.0, p2=0.0):
        m = VehicleCommand(command=command, param1=p1, param2=p2, target_system=1, target_component=1,
                           source_system=1, source_component=1, from_external=True,
                           timestamp=int(self.get_clock().now().nanoseconds / 1000))
        self.cmd_pub.publish(m)

    def step(self):
        now = int(self.get_clock().now().nanoseconds / 1000)
        self.mode_pub.publish(OffboardControlMode(position=True, timestamp=now))
        self.sp_pub.publish(TrajectorySetpoint(position=[0.0, 0.0, -5.0], yaw=0.0, timestamp=now))  # 5 m up (NED)
        if self.n == 10:                                                # after 1 s of setpoints
            self.cmd(VehicleCommand.VEHICLE_CMD_DO_SET_MODE, 1.0, 6.0)  # Offboard
            self.cmd(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 1.0)
        self.n += 1

rclpy.init(); rclpy.spin(Offboard())
```
Защиты из модуля «Слежение» (лимиты, watchdog, таймауты `COM_OF_LOSS_T` = 1 с и действие `COM_OBL_RC_ACT`) обязательны и здесь. Метка `timestamp` здесь — часы узла; это работает, пока timesync сошёлся и узел не на симуляционном времени (раздел о метках времени выше).

{{diagram:px4-offboard-seq|Offboard из ROS 2: поток OffboardControlMode и TrajectorySetpoint до переключения режима, затем команды режима и арма; при обрыве — failsafe.}}

### Место в системе

- **Получает:** топики uORB через `uxrce_dds_client` (`px4-architecture`); порт и скорость `UXRCE_DDS_CFG` на борту (`px4-companion-jetson`); QoS и соглашения об осях ROS 2 (`ros2-basics`).
- **Отдаёт:** `/fmu/out/*` — узлам ROS 2; `TrajectorySetpoint` — контроллеру позиции (`px4-control`); три сообщения Offboard — автомату состояний (`ros2-px4`) и контуру слежения (`per-tracking`).
- **Если ошибиться здесь:** отправил уставку в ENU без перевода в NED → z со знаком «вверх» уводит аппарат в землю на взлёте (`math-linalg-rot`). Узел завис на инференсе дольше `COM_OF_LOSS_T` → PX4 выходит из Offboard по `COM_OBL_RC_ACT`, со стороны — самопроизвольная смена режима (`ros2-app-arch`). Имя топика вписано руками → после обновления прошивки до 1.18 `vehicle_status_v1` молчит, узел считает статус устаревшим (`ros2-px4`).

## practice
### Шаг 1. Мост на бумаге: имена, частоты, нагрузка, таймаут
Этот шаг выполняется на любом компьютере с Python 3 и интернетом, без ROS и симулятора. Скрипт скачивает `dds_topics.yaml` и нужные `.msg` выбранного тега PX4 с GitHub, собирает ROS-имена с суффиксами, считает размер сообщений в CDR тем же обходом полей, что генератор PX4, предел частоты по `rate_limit` и нагрузку на UART, а затем — момент потери сигнала Offboard по правилу `offboardCheck.cpp`. Сохрани как `px4_dds_lab.py`:
```python
import math, re, sys, urllib.request

TAG = sys.argv[1] if len(sys.argv) > 1 else "v1.17.0"
RAW = f"https://raw.githubusercontent.com/PX4/PX4-Autopilot/{TAG}/"
SIZE = {"bool": 1, "char": 1, "int8": 1, "uint8": 1, "int16": 2, "uint16": 2,
        "int32": 4, "uint32": 4, "float32": 4, "int64": 8, "uint64": 8, "float64": 8}
MSG = {}

def get(rel):
    try:
        return urllib.request.urlopen(RAW + rel, timeout=20).read().decode()
    except Exception:
        return None

def msg(name):                       # -> (MESSAGE_VERSION, [(type, count)])
    if name not in MSG:
        ver, fields = 0, []
        for line in (get(f"msg/versioned/{name}.msg") or get(f"msg/{name}.msg")).splitlines():
            s = line.split("#")[0].strip()
            m = re.match(r"uint32\s+MESSAGE_VERSION\s*=\s*(\d+)", s)
            ver = int(m.group(1)) if m else ver
            if s and "=" not in s:
                t = s.split()[0]
                n = int(t[t.index("[") + 1:-1]) if "[" in t else 1
                fields.append((t.split("[")[0].split("/")[-1], n))
        MSG[name] = (ver, fields)
    return MSG[name]

def cdr(name, off=0):                # same walk as Tools/msg/templates/ucdr/msg.h.em
    for t, n in msg(name)[1]:
        if t in SIZE:
            off += (SIZE[t] - off % SIZE[t]) & (SIZE[t] - 1)
            off += SIZE[t] * n
        else:
            for _ in range(n):
                off = cdr(t, off)
    return off

sec, rows = None, []
for line in get("src/modules/uxrce_dds_client/dds_topics.yaml").splitlines():
    s = line.split("#")[0].strip()
    if re.match(r"^[a-z_]+:$", s):
        sec = s[:-1]
    elif s.startswith("- topic:"):
        rows.append([sec, s.split(":", 1)[1].strip(), None, None])
    elif s.startswith("type:"):
        rows[-1][2] = s.split("::")[-1]
    elif s.startswith("rate_limit:"):
        rows[-1][3] = float(s.split(":")[1])

total = 0
for sec, topic, typ, r in rows:
    ver = msg(typ)[0]
    name = topic + (f"_v{ver}" if ver else "")
    if sec == "publications":
        cap = 1000 / (int(1e3 / r) if r else 10)          # orb_set_interval in whole ms, 10 ms default
        total += cap * (cdr(typ) + 23)                    # +23 B XRCE/serial overhead (course estimate)
    if ver or typ in ("TrajectorySetpoint", "OffboardControlMode", "VehicleOdometry"):
        print(f"{name:40s} v{ver}  {cdr(typ):4d} B" + (f"  cap {cap:5.1f} Hz" if sec == "publications" else ""))
print(f"out {sum(r[0] == 'publications' for r in rows)}, in {sum(r[0] != 'publications' for r in rows)}; "
      f"all /fmu/out at caps: {total:.0f} B/s vs {921600 // 10} B/s on UART 921600")

LOSS_T = 1.0                                              # COM_OF_LOSS_T, s
for hz, stop, shift in ((10, 5.0, 0.0), (2, 5.0, 0.0), (10, 99.0, -1.5)):
    last = math.floor((stop - 1e-9) * hz) / hz + shift    # timestamp PX4 sees for the last message
    print(f"{hz:2d} Hz, stop {stop:4.1f} s, stamp shift {shift:+.1f} s -> " +
          ("never available" if shift <= -LOSS_T else f"signal lost at {last + LOSS_T:.1f} s"))
```
Запуск `python3 px4_dds_lab.py v1.17.0` дал (2026-11-26):
```
/fmu/out/arming_check_request_v1         v1    16 B  cap   5.0 Hz
/fmu/out/battery_status_v1               v1   176 B  cap   1.0 Hz
/fmu/out/vehicle_local_position_v1       v1   216 B  cap  50.0 Hz
/fmu/out/vehicle_odometry                v0   114 B  cap 100.0 Hz
/fmu/out/vehicle_status_v1               v1    80 B  cap   5.0 Hz
/fmu/out/airspeed_validated_v1           v1    44 B  cap  50.0 Hz
/fmu/out/home_position_v1                v1    60 B  cap   5.0 Hz
/fmu/in/arming_check_reply_v1            v1   227 B
/fmu/in/offboard_control_mode            v0    15 B
/fmu/in/trajectory_setpoint              v0    64 B
/fmu/in/vehicle_attitude_setpoint_v1     v1    40 B
/fmu/in/vehicle_mocap_odometry           v0   114 B
/fmu/in/vehicle_visual_odometry          v0   114 B
out 27, in 38; all /fmu/out at caps: 107495 B/s vs 92160 B/s on UART 921600
10 Hz, stop  5.0 s, stamp shift +0.0 s -> signal lost at 5.9 s
 2 Hz, stop  5.0 s, stamp shift +0.0 s -> signal lost at 5.5 s
10 Hz, stop 99.0 s, stamp shift -1.5 s -> never available
```
Прочитай вывод как карту моста. Первые семь строк — именно те имена, под которые надо подписываться в 1.17.0; суффикс есть у `vehicle_local_position`, но не у `vehicle_odometry`. Строка с суммой показывает, что все выходные топики на своих пределах не помещаются в 921600 бод: 107 495 против 92 160 байт/с, то есть 117 % (из них данных CDR — ~78 900 байт/с, это и покажет `Payload tx`) — на реальном борту смотри `Payload tx`. Последние три строки — правило выхода из Offboard: последнее сообщение плюс 1 с, и «вечная недоступность» при метках из прошлого. Затем запусти `python3 px4_dds_lab.py v1.18.0`: в выводе появится `/fmu/out/vehicle_status_v4` вместо `_v1` и `/fmu/out/vehicle_command_ack_v1`, а сумма вырастет до 117 077 байт/с (31 выходной топик) — так выглядит обновление прошивки для узла с захардкоженными именами. Скрипт считает по правилу 1.17 (10 мс по умолчанию, отбрасывание дробной части); по правилу 1.18.0 (4 мс по умолчанию, округление) те же 31 топик на пределах дают 198 077 байт/с.

### Шаг 2. Окружение ROS 2 (на своей машине)
```
# ROS 2 Humble (Ubuntu 22.04, recommended by the PX4 v1.17 docs) or Jazzy (Ubuntu 24.04), sourced
mkdir -p ~/ws_px4/src && cd ~/ws_px4/src
git clone -b release/1.17 https://github.com/PX4/px4_msgs.git      # branch matching your PX4 version
git clone https://github.com/PX4/px4_ros_com.git
cd .. && colcon build && source install/setup.bash
```

Агент: `MicroXRCEAgent udp4 -p 8888` (сборка из исходников ветки v2.4.3 для Jazzy или v2.4.2 для Humble, или snap из канала `--edge` — стабильный snap, по документации PX4, ошибается при создании топиков). Шаги 2–5 в этом курсе на сервере авторов не запускались (нет ROS 2 и места под сборку SITL); критерии ниже — из документации и кода v1.17.0.

### Шаг 3. SITL с клиентом
`make px4_sitl gz_x500` — в SITL клиент uXRCE-DDS стартует сам (`uxrce_dds_client start -t udp -p 8888` в `rcS`) и ищет агента на 8888. Проверка: `ros2 topic list` показывает `/fmu/out/vehicle_attitude` и прочие; `ros2 topic echo /fmu/out/vehicle_local_position_v1` (до 1.17 — `/fmu/out/vehicle_local_position`, без суффикса). В консоли PX4 `uxrce_dds_client status` — `Running, connected`, `timesync converged: true` и `Payload tx` в байт/с: сравни с суммой шага 1 без заголовков (~78 900 байт/с, если все топики идут на пределах).

### Шаг 4. Offboard-пример
Запусти пример из `px4_ros_com` (offboard control): узел 10 циклов шлёт `OffboardControlMode` + `TrajectorySetpoint`, затем переключает режим и армит через `VehicleCommand`, после чего держит точку на 5 м. Прочитай код: порядок «сначала поток, потом режим» — ключевой.

### Шаг 5. Свой узел
Напиши узел на Python (`rclpy`), который держит квадрокоптер на высоте 3 м и каждые 10 с меняет цель по кругу радиусом 5 м. Проверь: остановил узел — через ~1 с (`COM_OF_LOSS_T`, 1 с по умолчанию) PX4 выходит из Offboard (в SITL — переход по `COM_OBL_RC_ACT`; без пульта с 1.17 — по `NAV_RCL_ACT`).

Каркас (структура как в примере `px4_ros_com`, имена топиков сверить с `ros2 topic list` своей версии PX4):
```python
import math
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from px4_msgs.msg import OffboardControlMode, TrajectorySetpoint, VehicleCommand

QOS = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                 history=HistoryPolicy.KEEP_LAST, depth=1)

class Circle(Node):
    def __init__(self):
        super().__init__("circle")
        self.mode_pub = self.create_publisher(OffboardControlMode, "/fmu/in/offboard_control_mode", QOS)
        self.sp_pub = self.create_publisher(TrajectorySetpoint, "/fmu/in/trajectory_setpoint", QOS)
        self.cmd_pub = self.create_publisher(VehicleCommand, "/fmu/in/vehicle_command", QOS)
        self.ticks = 0
        self.create_timer(0.1, self.tick)                       # 10 Hz, well above the 2 Hz minimum

    def now_us(self):
        return self.get_clock().now().nanoseconds // 1000

    def command(self, cmd, p1=0.0, p2=0.0):
        m = VehicleCommand(command=cmd, param1=p1, param2=p2, target_system=1, target_component=1,
                           source_system=1, source_component=1, from_external=True, timestamp=self.now_us())
        self.cmd_pub.publish(m)

    def tick(self):
        self.mode_pub.publish(OffboardControlMode(position=True, timestamp=self.now_us()))
        a = 2 * math.pi * (self.ticks // 100) / 6               # next point on the circle every 10 s
        sp = TrajectorySetpoint(timestamp=self.now_us())
        sp.position = [5.0 * math.cos(a), 5.0 * math.sin(a), -3.0]   # NED: z = -3 is 3 m up
        sp.yaw = float(a + math.pi)
        self.sp_pub.publish(sp)
        if self.ticks == 10:                                    # stream first, then switch mode and arm
            self.command(VehicleCommand.VEHICLE_CMD_DO_SET_MODE, 1.0, 6.0)   # custom mode 6 = Offboard
            self.command(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 1.0)
        self.ticks += 1

def main():
    rclpy.init(); rclpy.spin(Circle())

if __name__ == "__main__":
    main()
```
Что проверить по логу: в `.ulg` `trajectory_setpoint` ступенькой меняется каждые 10 с, `vehicle_local_position` догоняет за 2–4 с без перелёта больше 0.5 м (ориентир курса); при `Ctrl+C` узла — переход режима через `COM_OF_LOSS_T` после последней метки `offboard_control_mode` (в логе — разница времени 1.0 ± 0.1 с в реальном времени SITL; при `PX4_SIM_SPEED_FACTOR` ≠ 1 `rcS` умножает таймаут на этот множитель).

### Переход на реальное железо
Мост на борту поднимают в три захода, пропеллеры сняты до последнего. (1) На столе, без пропеллеров, полётник и companion запитаны: `uxrce_dds_client status` — `connected`, `ros2 topic hz /fmu/out/vehicle_odometry` показывает частоту не выше 100 Гц, `Payload tx` ниже 50 % байт/с выбранной скорости (ориентир курса: `Payload tx` не считает заголовки, с ними это около 70 % линии; при 921600 — ниже ~46 000 байт/с). Если выше — поднять скорость или урезать список топиков. (2) Там же: узел шлёт поток, режим переключается в Offboard **без арма** (арм пропусти в коде), затем `Ctrl+C` — через ~1 с `listener failsafe_flags` показывает `offboard_control_signal_lost: True`, QGC сообщает, что Offboard недоступен; сам режим не меняется: действия failsafe выполняются только в арме (`framework.cpp`). Действие `COM_OBL_RC_ACT` проверяют в арме, в SITL (проверка в лабораторной выше). (3) Полёт: пилот держит пульт с переключателем режима Position, первый тест — висение 2 м на открытой площадке; прерывание — переключение режима пилотом, проверено до взлёта. Отбой: любое расхождение высоты больше 0.5 м от уставки (ориентир курса), смена режима без команды, `timesync converged: false`.

### Лабораторная
Самопроверка: лабораторная выполнена, когда (путь без симулятора) твой запуск шага 1 для v1.17.0 дал те же семь имён `/fmu/out/*_v1` и `vehicle_odometry`, «out 27, in 38», сумму 107495 B/s и моменты 5.9 с и 5.5 с, а запуск для v1.18.0 показал `vehicle_status_v4`; (путь SITL) узел держит 3 м и каждые 10 с меняет цель по кругу радиусом 5 м, в `.ulg` `trajectory_setpoint` меняется ступенькой каждые 10 с, а `vehicle_local_position` догоняет её за 2–4 с без перелёта больше 0.5 м (ориентир курса), и после `Ctrl+C` узла PX4 выходит из Offboard через 1.0 ± 0.1 с после последней метки (SITL в реальном времени) — в твоих заметках записано, в какой режим он перешёл; (железо) три захода из подраздела выше пройдены без срабатывания условий отбоя.

**Эталон для самопроверки.** Верный результат: порядок «сначала поток `OffboardControlMode` + `TrajectorySetpoint`, потом режим и арм», высота 3 м задана как z = −3, подписчики BEST_EFFORT, имена топиков собраны из `MESSAGE_VERSION`. Типичные неверные: (1) PX4 не входит в Offboard — уставки не шли потоком до команды, метки времени из прошлого (симуляционное время, timesync не сошёлся) или нет валидной локальной позиции при флаге `position`; (2) аппарат летит вверх вместо вниз или взлетает «в землю» — знак z в NED; (3) `ros2 topic list` пуст — агент не запущен на 8888, не та ветка агента (v3.x) или `UXRCE_DDS_DOM_ID` ≠ `ROS_DOMAIN_ID`; (4) в задаче на `rate_limit` (например, 60 Гц) вышло 60 Гц вместо 62.5 — забыто, что период 16.67 мс отбрасывается до 16 мс; в шаге 1 округление ни на что не влияет, все пределы 1.17.0 делят 1000 нацело.

## diagnostics
- **Симптом:** `ros2 topic list` пуст
  - Возможная причина: агент не запущен, не тот порт, агент ветки v3.x, `UXRCE_DDS_DOM_ID` не равен `ROS_DOMAIN_ID`.
  - Что сделать: агент v2.4.x на 8888, `uxrce_dds_client status` в консоли PX4, сверить домен.
- **Симптом:** топик виден в `ros2 topic list`, а `ros2 topic echo` молчит
  - Возможная причина: подписчик RELIABLE против best-effort-писателя PX4; не та ветка `px4_msgs` (другое определение типа).
  - Что сделать: `qos_profile_sensor_data` или `--qos-reliability best_effort`; `px4_msgs` из `release/1.17`.
- **Симптом:** после обновления прошивки узел перестал видеть статус
  - Возможная причина: суффикс версии поменялся (1.17 → 1.18: `vehicle_status_v1` → `vehicle_status_v4`), имя вписано руками.
  - Что сделать: собирать имя из `MESSAGE_VERSION`, обновлять `px4_msgs` вместе с прошивкой или запустить Message Translation Node.
- **Симптом:** PX4 не входит в Offboard, хотя поток 10 Гц
  - Возможная причина: метки `timestamp` из прошлого (узел на симуляционном времени, timesync не сошёлся), нет валидной локальной позиции при флаге `position`, поток не шёл до команды.
  - Что сделать: `timesync converged: true` в `uxrce_dds_client status`, метка 0 или часы узла после схождения; проверить `estimator_status_flags`; поток до смены режима.
  - Что видно в логе: `offboard_control_mode` приходит, а в `failsafe_flags` `offboard_control_signal_lost` = true.
- **Симптом:** выкидывает из Offboard в полёте
  - Возможная причина: пауза потока дольше `COM_OF_LOSS_T` — узел завис на инференсе или сборке мусора, перегружен UART.
  - Что сделать: таймер публикации в отдельном потоке или процессе, `Payload tx` против ёмкости канала, загрузка companion.
  - Что видно в логе: разрыв в `offboard_control_mode` ≥ 1 с прямо перед сменой режима.
- **Симптом:** после потери Offboard аппарат ушёл на Return, хотя `COM_OBL_RC_ACT` = Position
  - Возможная причина: с 1.17 при отсутствии ручного управления вместо Position выполняется `NAV_RCL_ACT` (по умолчанию Return; в 1.18 при `NAV_RCL_ACT` = 7 — Hold).
  - Что сделать: это задуманное поведение; задать нужное действие прямо в `COM_OBL_RC_ACT` (Land/Return/Hold) и `NAV_RCL_ACT`.
- **Симптом:** летит вверх вместо вниз, взлёт «в землю» в SITL
  - Возможная причина: знак Z в NED, уставка в ENU без перевода.
  - Что сделать: Z вниз положительный, высота 3 м — Z = −3; ENU→NED: (x, y, z) → (y, x, −z).
- **Симптом:** топики пропадают при высокой частоте, `Payload tx` у предела
  - Возможная причина: UART 921600 переполнен (все топики на пределах — 117 % ёмкости).
  - Что сделать: 1.5–3 Мбод, Ethernet или урезанный `dds_topics.yaml` в своей сборке.

## references
- PX4 ROS 2 User Guide | https://docs.px4.io/v1.17/en/ros2/user_guide.html | primary | A
- PX4 uXRCE-DDS | https://docs.px4.io/v1.17/en/middleware/uxrce_dds.html | primary | A
- PX4 ROS 2 Offboard Control Example | https://docs.px4.io/v1.17/en/ros2/offboard_control.html | primary | A
- PX4-Autopilot v1.17.0 — dds_topics.yaml (topic list, rate_limit) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/uxrce_dds_client/dds_topics.yaml | primary | A
- PX4-Autopilot v1.17.0 — uxrce_dds_client module.yaml (UXRCE_DDS_* parameters) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/uxrce_dds_client/module.yaml | primary | A
- PX4-Autopilot v1.17.0 — offboardCheck.cpp (offboard signal rule) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/commander/HealthAndArmingChecks/checks/offboardCheck.cpp | primary | A
- PX4 ROS 2 Message Translation Node | https://docs.px4.io/v1.17/en/ros2/px4_ros2_msg_translation_node.html | primary | A
- px4_msgs (GitHub, branch release/1.17) | https://github.com/PX4/px4_msgs | primary | A
- px4_ros_com (GitHub) | https://github.com/PX4/px4_ros_com | primary | A
- eProsima Micro XRCE-DDS Agent | https://github.com/eProsima/Micro-XRCE-DDS-Agent | primary | A

## checklist
- Агент v2.4.x и клиент связаны, топики видны в ROS 2, домен совпадает
- Ветка `px4_msgs` соответствует версии PX4, имена топиков собираются из `MESSAGE_VERSION`
- Подписчики на `/fmu/out/*` — BEST_EFFORT
- `Payload tx` ниже ёмкости канала с запасом
- Метки времени узла проверены (timesync сошёлся, не симуляционное время)
- Свой узел держит поток `OffboardControlMode` без пауз дольше `COM_OF_LOSS_T`
- `COM_OBL_RC_ACT` и `NAV_RCL_ACT` выбраны осознанно, поведение при остановке узла проверено
