---
id: ros2-ardupilot
title: "ROS 2 + ArduPilot: AP_DDS и MAVROS, один узел — два маршрута"
level: L3
readingTime: 60 мин
firmware: ArduPilot 4.7.2 (AP_DDS) · ROS 2 Humble
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
У ArduPilot два пути в ROS 2. **AP_DDS** — встроенный в прошивку DDS-клиент (тот же принцип, что uXRCE-DDS у PX4): топики `/ap/*` в ENU и стандартных типах ROS, сервисы арма и смены режима, управление скоростью через `/ap/cmd_vel`. **MAVROS** — мост MAVLink ↔ ROS, работающий с любой прошивкой и с полным набором MAVLink-функций, ценой лишнего слоя. Модуль разбирает оба по исходникам и документации, сравнивает с маршрутом PX4 и показывает, как тот же автомат состояний из модуля ros2-px4 летает квадрат на ArduPilot через AP_DDS. Всё про AP_DDS сверено с исходниками Copter-4.7.2: параметры `DDS_*` и их умолчания (`DDS_ENABLE` в сборке с DDS уже 1), цикл подключения к агенту и гонка загрузки с companion, полный список топиков и сервисов с QoS и частотами, преобразования кадров — включая место, где `base_link` в 4.7.2 ведёт себя не по REP-103. Лабораторная: проверка, есть ли AP_DDS в твоей сборке, и численная проверка преобразований кадров (выполнено), затем квадрат в SITL через AP_DDS и через MAVROS со сравнительной таблицей задержек — процедура по документации ArduPilot, в окружении автора не прогонялась (нет ROS 2 Humble).

## theory
### AP_DDS: как подключить
В прошивке — клиент DDS (`libraries/AP_DDS`, eProsima Micro XRCE-DDS Client), снаружи — агент micro-ROS (`micro_ros_agent`), который выводит данные в DDS-сеть ROS 2. Клиент лёгкий: он не участвует в обнаружении DDS сам, а через агента создаёт участника `ap`, издателей, подписчиков и сервисы.

{{diagram:uxrce-scheme|Схема та же, что у PX4: клиент в прошивке, агент на companion, обычные топики ROS 2 снаружи.}}

**Сборка.** AP_DDS компилируется только с ключом `--enable-DDS` (`Tools/ardupilotwaf/boards.py`: без ключа `AP_DDS_ENABLED=0`, если его не включил hwdef платы). Для сборки нужны генератор `microxrceddsgen` в `PATH` (`libraries/AP_DDS/wscript` ищет его обязательным) и подмодули `modules/Micro-XRCE-DDS-Client` и `modules/Micro-CDR`. Генератор — форк ArduPilot `Micro-XRCE-DDS-Gen`, для ArduPilot 4.7 и новее — ветка `v4.7.0`, до 4.7 — `v4.5.1` (ArduPilot dev wiki, «Install ROS 2»). Поддерживаемая версия ROS 2 по той же странице — только Humble (на ноябрь 2026); агент — `micro-ROS-Agent`, ветка `humble` (`Tools/ros2/ros2.repos`). Обычная сборка SITL этих параметров не имеет: в SITL 4.7.2 без ключа `DDS_ENABLE` отвечает «нет такого параметра», а в бинарнике нет ни одной строки `rt/ap/` (проверено в практике). Это первая проверка при «топиков нет».

**Транспорт.** UDP — `DDS_UDP_PORT` (умолчание 2019) и адрес агента `DDS_IP0`…`DDS_IP3`; умолчание 127.0.0.1 в SITL и 192.168.144.2 на платах ChibiOS (`AP_DDS_config.h`). UDP на железе требует сетевого стека ArduPilot (`AP_NETWORKING_ENABLED`: Ethernet на плате или PPP по UART), иначе — последовательный порт: `SERIALn_PROTOCOL = 45` (DDS XRCE) и скорость `SERIALn_BAUD` (в `dds_serial.parm` пакета `ardupilot_sitl` — 115). Один порт — один протокол: UART под DDS уже не отдаёт MAVLink, поэтому companion с ROS 2 и MAVLink-роутером занимает два порта FC или Ethernet.

| Параметр (4.7.2) | Умолчание | Диапазон | Что делает |
|---|---|---|---|
| `DDS_ENABLE` | 1 (если DDS вкомпилирован) | 0, 1; перезагрузка | включает клиент; 0 — выключить, не трогая сборку |
| `DDS_UDP_PORT` | 2019 | 1–65535 | порт агента |
| `DDS_IP0`…`DDS_IP3` | 127.0.0.1 (SITL), 192.168.144.2 (ChibiOS) | октеты | адрес агента |
| `DDS_DOMAIN_ID` | 0 | 0–232 | `ROS_DOMAIN_ID` (0 — переменная не задана) |
| `DDS_TIMEOUT_MS` | 1000 мс | 1–10000 | ожидание ответа агента на пинг |
| `DDS_MAX_RETRY` | 10 | 0–100; 0 — без предела | пингов в пачке до сообщения «exiting» |
| `SERIALn_PROTOCOL` | — | 45 = DDS XRCE | DDS по UART |

Все параметры `DDS_*` требуют перезагрузки (`@RebootRequired: True` в `AP_DDS_Client.cpp`). В пакете `ardupilot_sitl` есть готовые наборы: `dds_udp.parm` (`DDS_ENABLE 1`, `DDS_UDP_PORT 2019`) и `dds_serial.parm` (`DDS_ENABLE 1`, `SERIAL1_BAUD 115`, `SERIAL1_PROTOCOL 45`). Типы ArduPilot-специфичных сообщений — пакет `ardupilot_msgs` (`Tools/ros2/ardupilot_msgs`): сообщения `Status`, `GlobalPosition`, `Rc`, `Airspeed`, сервисы `ArmMotors`, `ModeSwitch`, `Takeoff`; ветка пакета должна совпадать с прошивкой.

### Цикл подключения и гонка загрузки
Поток AP_DDS (`AP_DDS_Client::main_loop`, 4.7.2) после инициализации транспорта пингует агента: каждый пинг ждёт ответа `DDS_TIMEOUT_MS`, пачка — `DDS_MAX_RETRY` пингов. Если пачка без ответа, в GCS уходит `DDS: No ping response, exiting` — и цикл **продолжается** (`continue`), несмотря на слово «exiting»: при умолчаниях клиент пробует снова каждые 10 с, бесконечно. С `DDS_MAX_RETRY = 0` он пингует без пачек и пишет `No ping response, retrying` после каждого неудачного пинга — раз в секунду, что засоряет сообщения GCS. После ответа создаются сессия и сущности (`DDS: Initialization passed`); внутри сессии клиент пингует агента каждые 500 мс (`DELAY_PING_MS`) и после трёх пропусков подряд (> 2) пишет `No ping response, disconnecting` и возвращается к пингам. Всё это — вывод из кода; поведение «exiting, но продолжает» стоит один раз увидеть в SITL.

Практическое следствие — гонка загрузки. FC готов через секунды, Raspberry Pi с агентом — через десятки секунд. Если агент поднимается на 35-й секунде (ориентир курса для Pi с systemd-сервисом), GCS успевает показать три «exiting» (на 12, 22 и 32 с), а сессия создаётся при первом пинге после старта агента. Это не ошибка конфигурации; ошибка — решить по этим сообщениям, что DDS «упал», и полезть менять параметры.

{{diagram:ros2-ap-dds-boot-race|Клиент ArduPilot пингует агента пачками по 10 × 1 с и после каждой пишет «exiting», но не сдаётся: агент, поднявшийся на 35-й секунде, подключается при следующем пинге.}}

### Что публикует и принимает AP_DDS
Полный список 4.7.2 — из `AP_DDS_Topic_Table.h` и `AP_DDS_Service_Table.h`; частоты — из задержек в `AP_DDS_config.h` (публикация, когда с прошлой прошло больше задержки, поэтому 33 мс дают ≈ 30 Гц). Имя DDS-топика `rt/ap/…` в ROS 2 видно как `/ap/…`; запрос сервиса `rq/ap/get_parametersRequest` — как сервис `/ap/get_parameters`.

| Топик/сервис | Тип | Частота, QoS | Назначение |
|---|---|---|---|
| `/ap/pose/filtered` | `geometry_msgs/PoseStamped` | ≈ 30 Гц, BEST_EFFORT | локальная поза из EKF относительно home, ENU (в `header.frame_id` прошивка пишет `base_link`) |
| `/ap/twist/filtered` | `geometry_msgs/TwistStamped` | ≈ 30 Гц, BEST_EFFORT | скорость |
| `/ap/geopose/filtered`, `/ap/navsat` | `geographic_msgs/GeoPoseStamped`, `sensor_msgs/NavSatFix` | ≈ 30 Гц / по GPS, BEST_EFFORT | глобальная поза, GNSS (`frame_id` = номер приёмника) |
| `/ap/gps_global_origin/filtered` | `geographic_msgs/GeoPointStamped` | 1 Гц, BEST_EFFORT | начало координат EKF |
| `/ap/goal_lla` | `geographic_msgs/GeoPointStamped` | 5 Гц, RELIABLE + TRANSIENT_LOCAL | текущая цель навигации |
| `/ap/battery` | `sensor_msgs/BatteryState` | 1 Гц, BEST_EFFORT | батарея |
| `/ap/status` | `ardupilot_msgs/Status` | при изменении, иначе 2 Гц; RELIABLE + TRANSIENT_LOCAL | armed, mode, flying, external_control, failsafe |
| `/ap/rc`, `/ap/airspeed` | `ardupilot_msgs/Rc`, `ardupilot_msgs/Airspeed` | 10 Гц / ≈ 30 Гц, BEST_EFFORT | пульт; воздушная скорость |
| `/ap/imu/experimental/data` | `sensor_msgs/Imu` | 200 Гц, BEST_EFFORT | IMU, экспериментально |
| `/ap/tf_static`, `/ap/clock`, `/ap/time` | tf2, `rosgraph_msgs/Clock`, `builtin_interfaces/Time` | однократно (RELIABLE + TRANSIENT_LOCAL) / 100 Гц (RELIABLE) | крепления GPS к `base_link`, часы для sim time |
| `/ap/cmd_vel` (вход) | `geometry_msgs/TwistStamped` | BEST_EFFORT | скорость в GUIDED; frame `map` (ENU) или `base_link` |
| `/ap/cmd_gps_pose` (вход) | `ardupilot_msgs/GlobalPosition` | BEST_EFFORT | глобальная цель в GUIDED (frame `map`) |
| `/ap/joy`, `/ap/tf` (вход) | `sensor_msgs/Joy`, `tf2_msgs/TFMessage` | BEST_EFFORT | джойстик; внешняя одометрия через TF |
| `/ap/arm_motors`, `/ap/mode_switch`, `/ap/prearm_check`, `/ap/experimental/takeoff` | сервисы | — | арм, режим (номер режима Copter: GUIDED = 4, LAND = 9), предарм (`std_srvs/Trigger`), взлёт |
| `/ap/set_parameters`, `/ap/get_parameters` | `rcl_interfaces` сервисы | — | параметры ArduPilot как параметры ROS 2 |

Важно: AP_DDS сам переводит ENU ↔ NED — для `cmd_vel` по `header.frame_id` (`map` — мировые ENU, `base_link` — корпус). Позиция: x_ENU = восток = y_NED, y_ENU = север = x_NED, z_ENU = −z_NED; ориентация — перестановка компонент кватерниона и поворот на 90° вокруг z, чтобы курс «на север» стал 90° по ENU. Скорость рысканья в `cmd_vel` инвертируется (ROS: против часовой положительно). Любой другой `frame_id` (например, `odom`) молча отбрасывается. То есть в отличие от PX4 твой ROS-узел живёт в соглашениях ROS — с одной оговоркой. Для `base_link` код 4.7.2 инвертирует только z (`{x, y, -z}`), а y оставляет как есть и поворачивает вектор матрицей корпуса FRD (`AP_DDS_ExternalControl.cpp`, так же в master на ноябрь 2026): по REP-103 `linear.y > 0` — влево, а по коду аппарат пойдёт вправо. Это вывод из кода, проверенный численно в практике (шаг 2), но не полётом; до использования `base_link` для бокового движения проверь знак в SITL, а надёжный путь — слать скорости в `map`.

Ещё два факта из кода. Уставки `cmd_vel` и `cmd_gps_pose` принимаются, только если аппарат в GUIDED (или в AUTO на пункте NAV_GUIDED) и заармлен (`AP_ExternalControl_Copter::ready_for_external_control`), иначе молча отбрасываются. Поле `external_control` в `/ap/status` в 4.7.2 всегда `true` («to be filled after PR#28429» в `AP_DDS_Client.cpp`) — опираться на него нельзя. QoS: позы и скорости — BEST_EFFORT, `/ap/status`, `/ap/goal_lla` и `tf_static` — RELIABLE + TRANSIENT_LOCAL (подписчик BEST_EFFORT совместим и с тем, и с другим; `tf_static` удобнее читать с `--qos-durability transient_local`, как в README).

### Порядок действий в ArduPilot
ArduCopter армится только в режиме, разрешающем арм (GUIDED подходит), и только после pre-arm проверок. Взлёт в GUIDED — отдельная команда (сервис takeoff — аналог `MAV_CMD_NAV_TAKEOFF`, вызывает `AP_Vehicle::start_takeoff`), без неё аппарат на земле игнорирует горизонтальные уставки. Последовательность в узле: GUIDED → arm → takeoff(alt) → уставки скорости/позиции → LAND. Таймаут уставок скорости в GUIDED — `GUID_TIMEOUT` (секунды, по умолчанию 3 с — `ArduCopter/Parameters.cpp` 4.7.2): если `cmd_vel` перестал приходить, аппарат остановится. `cmd_vel` идёт в тот же субрежим VelAccel (`set_vel_NED_ms` → `set_vel_accel_NED_m`), что и `SET_POSITION_TARGET_LOCAL_NED` с маской скорости, поэтому замер из модуля ap-companion переносится один к одному: спад скорости через 3.2–3.3 с после последней уставки, стоп < 0.2 м/с — через 4.3 с. Это тот же принцип «доказательства жизни», что Offboard у PX4.

{{diagram:ap-dds-guided-seq|Порядок важен: GUIDED, арм, отдельный takeoff и только потом поток cmd_vel в фрейме map; замолчал — через GUID_TIMEOUT аппарат встаёт.}}

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

### Место в системе

- **Получает:** сборку прошивки с `--enable-DDS` и свободный UART или Ethernet FC (`ap-companion`); позу и скорость из EKF как `/ap/pose/filtered` и `/ap/twist/filtered` (`ap-ekf`); правила GUIDED и `GUID_TIMEOUT` (`ap-companion`); автомат `OffboardFSM` (`ros2-px4`); для MAVROS — поток MAVLink (`mav-sdk`).
- **Отдаёт:** `/ap/cmd_vel` — режиму GUIDED; топики `/ap/*` в ENU и стандартных типах ROS — планированию (`ros2-nav`) и узлам приложения (`ros2-app-arch`).
- **Если ошибиться здесь:** в `cmd_vel` указан `frame_id` `base_link` вместо `map` → скорость трактуется в осях корпуса → план из `ros2-nav` уводит аппарат не туда (а боковые команды в `base_link` в 4.7.2 ещё и с обратным знаком). Агент на companion стартует позже FC → в GCS «DDS: No ping response, exiting», что легко принять за отказ, хотя клиент подключится сам. Уставки пошли до команды takeoff → аппарат на земле их игнорирует, автомат ждёт высоту до таймаута; порядок действий GUIDED — в `ap-companion`.

## practice
Шаги 1–3 выполнены в окружении автора (ArduPilot 4.7.2, Python 3); шаги 4–7 требуют ROS 2 Humble и сборки SITL с `--enable-DDS` — их там не было, поэтому команды взяты из ArduPilot dev wiki и `libraries/AP_DDS/README.md` 4.7.2 и помечены как не прогонявшиеся. Критерии самопроверки ниже разделены так же.

### Шаг 1. Есть ли AP_DDS в твоей сборке
Прежде чем искать ошибку в ROS, убедись, что клиент вообще вкомпилирован. Два способа: параметр `DDS_ENABLE` (в наземке или скриптом аудита из модуля ap-companion) и строки DDS-топиков в бинарнике SITL:

```bash
strings build/sitl/bin/arducopter | grep -c "rt/ap/"      # stock 4.7.2 SITL build (./waf copter)
# 0
# param audit of the same SITL (companion_lab.py from ap-companion):
# DDS_ENABLE        = None
```

Ноль строк и отсутствующий параметр — сборка без `--enable-DDS`. В сборке с DDS `strings` найдёт имена из `AP_DDS_Topic_Table.h` (`rt/ap/pose/filtered` и др.), а `DDS_ENABLE` будет равен 1 без всякой настройки.

### Шаг 2. Преобразования кадров — численно
Скрипт повторяет формулы AP_DDS 4.7.2 (`AP_DDS_Client.cpp` для `/ap/pose/filtered`, `AP_DDS_ExternalControl.cpp` для `/ap/cmd_vel`) и прогоняет их на простых случаях, где ответ известен заранее. Для `base_link` взят горизонтальный полёт (поворот только по курсу), как в коде через `body_to_earth`.

```python
"""Re-implementation of the AP_DDS frame conversions of ArduPilot 4.7.2 (AP_DDS_Client.cpp,
AP_DDS_ExternalControl.cpp) to check by numbers what a ROS 2 node sends and receives."""
import math

def qmul(a, b):
    w1, x1, y1, z1 = a; w2, x2, y2, z2 = b
    return (w1*w2 - x1*x2 - y1*y2 - z1*z2, w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2, w1*z2 + x1*y2 - y1*x2 + z1*w2)

def yaw_q(yaw):                                   # rotation about z (NED: about Down)
    return (math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2))

def q_yaw_deg(q):
    w, x, y, z = q
    return math.degrees(math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)))

# /ap/pose/filtered: position NED -> ENU, orientation NED -> ENU with a 90 deg z rotation
def pose_out(pos_ned, q_ned):
    pos_enu = (pos_ned[1], pos_ned[0], -pos_ned[2])
    aux = (q_ned[0], q_ned[2], q_ned[1], -q_ned[3])
    return pos_enu, qmul(aux, (math.sqrt(2) * 0.5, 0, 0, math.sqrt(2) * 0.5))

# /ap/cmd_vel in: frame "map" (ENU) or "base_link"
def cmd_vel_in(frame, lin, yaw_rate_ros, heading_ned):
    if frame == "map":
        v_ned = (lin[1], lin[0], -lin[2])
    elif frame == "base_link":
        body = (lin[0], lin[1], -lin[2])          # as in 4.7.2: only z is negated
        c, s = math.cos(heading_ned), math.sin(heading_ned)
        v_ned = (c * body[0] - s * body[1], s * body[0] + c * body[1], body[2])   # body_to_earth, level flight
    else:
        return None                                # any other frame_id is ignored (returns false)
    return v_ned, -yaw_rate_ros

print("pose: vehicle 10 m north, 5 m east, 20 m up, heading north (NED yaw 0)")
p, q = pose_out((10, 5, -20), yaw_q(0))
print(f"  /ap/pose/filtered position ENU = {p}, ENU yaw = {q_yaw_deg(q):.1f} deg")
p, q = pose_out((0, 0, -20), yaw_q(math.radians(90)))
print(f"  heading east (NED yaw 90): ENU yaw = {q_yaw_deg(q):.1f} deg")

print("cmd_vel frame 'map': linear (x=1 east, y=2 north, z=0.5 up), angular.z = 0.3 rad/s (CCW)")
v, r = cmd_vel_in("map", (1, 2, 0.5), 0.3, 0)
print(f"  -> NED velocity {v} (north, east, down), yaw rate {r} rad/s (NED, CW positive)")

for hdg in (0, 90):
    print(f"cmd_vel frame 'base_link', heading {hdg} deg: linear.y = +1 (REP-103: to the LEFT)")
    v, _ = cmd_vel_in("base_link", (0, 1, 0), 0, math.radians(hdg))
    print(f"  -> NED velocity ({v[0]:.2f}, {v[1]:.2f}, {v[2]:.2f})")
print("cmd_vel frame 'odom' ->", cmd_vel_in("odom", (1, 0, 0), 0, 0))
```

```text
pose: vehicle 10 m north, 5 m east, 20 m up, heading north (NED yaw 0)
  /ap/pose/filtered position ENU = (5, 10, 20), ENU yaw = 90.0 deg
  heading east (NED yaw 90): ENU yaw = 0.0 deg
cmd_vel frame 'map': linear (x=1 east, y=2 north, z=0.5 up), angular.z = 0.3 rad/s (CCW)
  -> NED velocity (2, 1, -0.5) (north, east, down), yaw rate -0.3 rad/s (NED, CW positive)
cmd_vel frame 'base_link', heading 0 deg: linear.y = +1 (REP-103: to the LEFT)
  -> NED velocity (0.00, 1.00, 0.00)
cmd_vel frame 'base_link', heading 90 deg: linear.y = +1 (REP-103: to the LEFT)
  -> NED velocity (-1.00, 0.00, 0.00)
cmd_vel frame 'odom' -> None
```

Читаем. Поза: 10 м на север и 5 м на восток в NED стали (5, 10, 20) в ENU — x восток, y север, z вверх; курс «на север» по ENU — 90°, «на восток» — 0°, как требует REP-103. `cmd_vel` в `map`: (1 на восток, 2 на север, 0.5 вверх) → NED (2, 1, −0.5), рысканье 0.3 рад/с против часовой → −0.3 по NED. `base_link`, `linear.y = +1`: при курсе 0° аппарат получает скорость на восток (вправо), при курсе 90° — на юг (тоже вправо), хотя по REP-103 +y — влево. Это и есть оговорка из теории. `frame_id = odom` → None: уставка отброшена.

### Шаг 3. Гонка загрузки — расчёт
Исходные: FC инициализирует DDS на 2-й секунде, `DDS_TIMEOUT_MS = 1000`, `DDS_MAX_RETRY = 10`, агент на companion готов на 35-й секунде. Пачка — 10 × 1 с = 10 с, сообщения «exiting» — на 12, 22 и 32 с, то есть ⌊(35 − 2) / 10⌋ = 3 штуки; сессия — при первом пинге после 35 с. С `DDS_MAX_RETRY = 40` пачка длится 40 с: агент, поднявшийся на 35-й секунде, подключится внутри первой пачки, и «exiting» не будет вовсе (оно появилось бы на 42-й секунде, только если агента нет и к тому времени). Если агент отвалится в полёте, клиент заметит это после 3 пропущенных пингов по 500 мс — за 1.5–2 с в зависимости от фазы (ответ на пинг проверяется на следующем такте).

### Шаг 4. SITL с DDS и агент (не прогонялось здесь)
Нативно, по ArduPilot dev wiki («Install ROS 2», «ROS 2 with SITL»; ROS 2 Humble на Ubuntu 22.04), для ArduPilot 4.7.x:

```bash
mkdir -p ~/ardu_ws/src && cd ~/ardu_ws
vcs import --recursive --input https://raw.githubusercontent.com/ArduPilot/ardupilot/master/Tools/ros2/ros2.repos src
(cd src/ardupilot && git checkout Copter-4.7.2 && git submodule update --init --recursive)   # match firmware and ardupilot_msgs
sudo apt update && rosdep update && source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -r -y
sudo apt install default-jre
git clone --recurse-submodules --branch v4.7.0 https://github.com/ardupilot/Micro-XRCE-DDS-Gen.git
(cd Micro-XRCE-DDS-Gen && ./gradlew assemble) && export PATH=$PATH:$PWD/Micro-XRCE-DDS-Gen/scripts
colcon build --packages-up-to ardupilot_sitl && source install/setup.bash
ros2 launch ardupilot_sitl sitl_dds_udp.launch.py transport:=udp4 synthetic_clock:=True wipe:=False model:=quad \
  speedup:=1 slave:=0 instance:=0 \
  defaults:=$(ros2 pkg prefix ardupilot_sitl)/share/ardupilot_sitl/config/default_params/copter.parm,$(ros2 pkg prefix ardupilot_sitl)/share/ardupilot_sitl/config/default_params/dds_udp.parm \
  sim_address:=127.0.0.1 master:=tcp:127.0.0.1:5760 sitl:=127.0.0.1:5501
# second terminal
source ~/ardu_ws/install/setup.bash
ros2 node list                      # /ap
ros2 topic list | grep /ap/
ros2 topic echo /ap/status --once
ros2 service call /ap/mode_switch ardupilot_msgs/srv/ModeSwitch "{mode: 4}"
ros2 service call /ap/arm_motors ardupilot_msgs/srv/ArmMotors "{arm: True}"
ros2 service call /ap/experimental/takeoff ardupilot_msgs/srv/Takeoff "{alt: 10.5}"
```

Курсовой вариант с Docker — `examples/ros2-docker` (`docker compose --profile ardupilot up --build`). Без лаунча вручную: агент `ros2 run micro_ros_agent micro_ros_agent udp4 -p 2019`, SITL — `sim_vehicle.py -v ArduCopter --enable-DDS` с `DDS_ENABLE 1`. Ожидаемое (по README 4.7.2): узел `/ap`, сервисы `/ap/arm_motors`, `/ap/mode_switch`, `/ap/prearm_check`, `/ap/experimental/takeoff`; в MAVProxy — `DDS: Initialization passed`. Прерывание: если за 60 с после старта агента нет `/ap` в `ros2 node list` — сверить `DDS_DOMAIN_ID` с `ROS_DOMAIN_ID` и порт агента с `DDS_UDP_PORT`, а не пересобирать.

### Шаг 5. Квадрат через AP_DDS (не прогонялось здесь)
`ros2 launch uav_ros2_labs ap_square.launch.py`. Сверьте переходы автомата в логе с режимами в Mission Planner/QGC. Постройте траекторию из `/tmp/ap_flight.csv`. Остановите узел посреди квадрата и измерьте по логу ArduPilot, через сколько аппарат остановился — сравните с `GUID_TIMEOUT`.

### Шаг 6. Тот же квадрат через MAVROS (не прогонялось здесь)
Напишите обёртку `mavros_square.py` (тот же автомат): `/mavros/state` → armed/mode, `/mavros/local_position/pose` → позиция, `/mavros/setpoint_position/local` → уставки, сервисы `cmd/arming`, `set_mode` (custom_mode "GUIDED"), `cmd/takeoff`. Проверьте, что тесты автомата не пришлось трогать.

### Шаг 7. Сравнение (не прогонялось здесь)
Измерьте задержку «уставка → изменение скорости в позе» для AP_DDS и MAVROS (по меткам времени в bag), загрузку CPU агента и MAVROS, и заполните таблицу из теории своими цифрами.


### Что должно получиться и что записать
- **Квадрат через AP_DDS.** В логе узла переходы автомата совпадают с режимами в наземке (GUIDED на всём квадрате), а траектория из CSV — квадрат с углами в пределах пары метров от заданных точек. Сохрани график.
- **GUID_TIMEOUT.** После остановки узла посреди квадрата аппарат зависает через `GUID_TIMEOUT` (по умолчанию 3 с). Время от последней уставки до остановки по логу ArduPilot должно совпасть с параметром ± период публикации уставок.
- **MAVROS.** Тот же автомат через обёртку проходит те же тесты. Если поведение отличается, ищи разницу в системах координат и единицах топиков, а не в автомате.
- **Таблица сравнения:** задержка «уставка → начало изменения скорости» (медиана и максимум по 20+ уставкам) и загрузка CPU агента AP_DDS и MAVROS. Записывай свои цифры: они зависят от машины и сборки, чужие тебе не помогут.

### Переход на реальное железо
По README AP_DDS 4.7.2 (раздел о Pixhawk 6X) — DDS по UART: прошивка, собранная `./waf configure --board <плата> --enable-DDS`, параметры `DDS_ENABLE 1`, `SERIALn_PROTOCOL 45`, `SERIALn_BAUD 115` на свободном порту, перезагрузка; на companion — `ros2 run micro_ros_agent micro_ros_agent serial -b 115200 -D /dev/serial/by-id/<порт>`. Порядок: (1) стол, пропеллеры сняты — в GCS `DDS: Initialization passed`, `ros2 topic hz /ap/pose/filtered` ≈ 30 Гц; прерывание: «No ping response» дольше двух минут после старта агента — проверить TX/RX, скорость с обеих сторон и что порт не занят MAVLink; (2) стол — сервисы `mode_switch` (4) и `arm_motors` возвращают успех, `cmd_vel` без арма игнорируется; (3) поле, пилот с пультом и тумблером LOITER/RTL, геозона — взлёт сервисом на 5 м, `cmd_vel` 1 м/с в `map` на север 3 с, тишина; приёмка: аппарат движется на север и останавливается через `GUID_TIMEOUT` ± 0.5 с; прерывание: любое движение не в ту сторону — пилот забирает управление.

Самопроверка: лабораторная выполнена, когда **(выполнимо без ROS)** по шагу 1 ты определил, есть ли AP_DDS в своей сборке (`strings … | grep -c "rt/ap/"` > 0 и `DDS_ENABLE` = 1 — есть; 0 и «нет параметра» — нет); скрипт шага 2 даёт ровно: позу ENU (5, 10, 20), курсы 90.0° и 0.0°, NED-скорость (2, 1, −0.5) с рысканьем −0.3, для `base_link` при курсах 0° и 90° — (0, 1, 0) и (−1, 0, 0), для `odom` — None; расчёт шага 3 даёт 3 сообщения «exiting» и 1.5–2 с до обнаружения пропажи агента. **(С ROS 2 Humble и DDS-сборкой)** квадрат пролетан через AP_DDS — траектория из `/tmp/ap_flight.csv` даёт квадрат с углами в пределах пары метров от заданных точек, а переходы автомата совпадают с режимами в наземке; время от последней уставки до начала торможения по логу ArduPilot — `GUID_TIMEOUT` (3 с) ± 0.5 с, как в замере ap-companion (3.2–3.3 с); обёртка MAVROS проходит те же тесты автомата без их правки; таблица сравнения заполнена медианой и максимумом задержки по 20+ уставкам и загрузкой CPU для AP_DDS и MAVROS. На железе — три критерия из предыдущего подраздела.

**Эталон для самопроверки.** Верный результат: один автомат и одни тесты, две обёртки, отличие — только в системах координат и единицах топиков; скрипт шага 2 печатает ровно вывод выше. Типичные неверные: (1) аппарат летит «на восток вместо севера» — уставка в ENU отправлена как NED (или наоборот) либо не тот `frame_id`; (2) боковая команда в `base_link` уводит вправо вместо влево — это поведение кода 4.7.2 (y не инвертируется), а не ошибка узла: перейди на `map`; (3) уставки `cmd_vel` игнорируются на земле — не выполнен takeoff в GUIDED или аппарат не заармлен; (4) в GCS три «DDS: No ping response, exiting», и ты решил, что DDS сломан, — это гонка загрузки, клиент подключится сам; (5) для MAVROS пришлось править тесты автомата — логика утекла из автомата в обёртку.

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
- **Симптом:** в GCS повторяется «DDS: No ping response, exiting», топиков нет
  - Возможная причина: агент ещё не запущен (companion грузится дольше FC), не тот адрес/порт (`DDS_IP0..3`, `DDS_UDP_PORT`) или UART под DDS с другой скоростью.
  - Что сделать: подождать старта агента — клиент продолжает попытки каждые `DDS_TIMEOUT_MS × DDS_MAX_RETRY` (10 с); проверить адрес, порт, скорость; не пересобирать прошивку.
  - Что видно в логе: сообщение раз в 10 с при умолчаниях, затем `DDS: Initialization passed`.
- **Симптом:** `DDS_ENABLE` нет в списке параметров
  - Возможная причина: прошивка или SITL собраны без `--enable-DDS`.
  - Что сделать: сборка с `--enable-DDS` и `microxrceddsgen` в PATH (Gen v4.7.0 для 4.7); проверка `strings … | grep rt/ap/`.
- **Симптом:** боковая уставка в `base_link` уводит в противоположную сторону
  - Возможная причина: в 4.7.2 для `base_link` инвертируется только z, y трактуется как «вправо» (вывод из кода `AP_DDS_ExternalControl.cpp`).
  - Что сделать: слать скорости в `map` (ENU) и поворачивать вектор в узле; для `base_link` проверить знак в SITL.
- **Симптом:** узел опирается на `/ap/status.external_control`, а он всегда true
  - Возможная причина: в 4.7.2 поле не заполняется (в коде — «to be filled after PR#28429»).
  - Что сделать: судить о внешнем управлении по `mode` (GUIDED = 4) и `armed`.
- **Симптом:** аппарат летит «на восток вместо севера»
  - Возможная причина: уставка в ENU отправлена как NED (или наоборот), frame_id не тот.
  - Что сделать: frame_id `map` для мировых ENU; конвертация только на границе.

## references
- ArduPilot — AP_DDS README (setup, topics, services) | https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_DDS/README.md | primary | A
- ArduPilot — ROS 2 with ArduPilot (dev docs) | https://ardupilot.org/dev/docs/ros2.html | primary | A
- ArduPilot — AP_DDS topic and service tables (source) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/AP_DDS | primary | A
- ArduPilot Copter-4.7.2 — AP_DDS_Client.cpp (DDS_* params, main_loop, QoS use) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_DDS/AP_DDS_Client.cpp | primary | A
- ArduPilot Copter-4.7.2 — AP_DDS_ExternalControl.cpp (cmd_vel frames) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_DDS/AP_DDS_ExternalControl.cpp | primary | A
- ArduPilot Copter-4.7.2 — AP_DDS_Topic_Table.h / AP_DDS_config.h | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_DDS/AP_DDS_Topic_Table.h | primary | A
- ArduPilot dev wiki — Install ROS 2 (Humble only, Micro-XRCE-DDS-Gen v4.7.0) | https://ardupilot.org/dev/docs/ros2.html | primary | A
- ArduPilot dev wiki — ROS 2 with SITL (sitl_dds_udp.launch.py) | https://ardupilot.org/dev/docs/ros2-sitl.html | primary | A
- MAVROS | https://github.com/mavlink/mavros | primary | A
- ArduPilot — Copter commands in Guided mode | https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html | primary | A

## checklist
- Подключаю ArduPilot к ROS 2 через AP_DDS (параметры, агент, сборка SITL)
- Знаю топики и сервисы /ap/* и в каких фреймах они
- Выдерживаю порядок GUIDED → arm → takeoff → уставки → LAND и знаю GUID_TIMEOUT
- Использую MAVROS там, где не хватает AP_DDS
- Сравниваю маршруты PX4/AP_DDS/MAVROS по фактам и измерениям
- Проверяю, вкомпилирован ли AP_DDS, до поиска ошибок в ROS
- Понимаю цикл подключения клиента и не путаю гонку загрузки с отказом
- Шлю `cmd_vel` в `map`; `base_link` для бокового движения — только после проверки знака
- Переиспользую один автомат состояний для разных автопилотов
