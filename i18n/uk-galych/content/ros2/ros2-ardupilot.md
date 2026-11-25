---
id: ros2-ardupilot
title: "ROS 2 + ArduPilot: AP_DDS і MAVROS, один вузол — два маршрути"
level: L3
readingTime: 45 хв
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
source: content/ros2/ros2-ardupilot.md
source_hash: 284f391657ba
---

## summary
В ArduPilot є два шляхи в ROS 2. **AP_DDS** — вбудований у прошивку DDS-клієнт (той самий принцип, що uXRCE-DDS у PX4): топіки `/ap/*` в ENU і стандартних типах ROS, сервіси арму та зміни режиму, керування швидкістю через `/ap/cmd_vel`. **MAVROS** — міст MAVLink ↔ ROS, що працює з будь-якою прошивкою і з повним набором MAVLink-функцій, але ціною зайвого шару. Модуль розбирає обидва за вихідними кодами й документацією, порівнює з маршрутом PX4 і показує, як той самий автомат станів із модуля ros2-px4 літає квадрат на ArduPilot через AP_DDS. Лабораторна: квадрат у SITL через AP_DDS, потім через MAVROS, і порівняльна таблиця затримок і зручності.

## theory
### AP_DDS: як підключити
У прошивці сидить клієнт DDS (`libraries/AP_DDS`), а зовні — агент micro-ROS (`micro_ros_agent`), який виводить дані в DDS-мережу ROS 2.

- Параметри: `DDS_ENABLE = 1`; транспорт UDP — `DDS_UDP_PORT` (за замовчуванням 2019) і адреса агента `DDS_IP0..3`; транспорт serial — `SERIALn_PROTOCOL = 45` на потрібному порту. `DDS_DOMAIN_ID` — домен ROS 2.
- SITL: збірка з підтримкою DDS (`./waf configure --board sitl --enable-DDS`), запуск `sim_vehicle.py -v ArduCopter --enable-DDS`, агент: `ros2 run micro_ros_agent micro_ros_agent udp4 -p 2019`.
- Типи ArduPilot-специфічних повідомлень — пакет `ardupilot_msgs` (у репозиторії ArduPilot, `Tools/ros2/ardupilot_msgs`): `Status`, `GlobalPosition`, сервіси `ArmMotors`, `ModeSwitch`, `Takeoff`.

{{diagram:uxrce-scheme|Схема та сама, що в PX4: клієнт у прошивці, агент на companion, звичайні топіки ROS 2 зовні.}}

{{diagram:ros2-ap-dds-boot-race|Клиент ArduPilot пингует агента пачками по 10 × 1 с и после каждой пишет «exiting», но не сдаётся: агент, поднявшийся на 35-й секунде, подключается при следующем пинге.}}

### Що публікує і приймає AP_DDS
| Топік/сервіс | Тип | Призначення |
|---|---|---|
| `/ap/pose/filtered` | `geometry_msgs/PoseStamped` | локальна поза з EKF відносно home, ENU (у `header.frame_id` прошивка пише `base_link`) |
| `/ap/twist/filtered` | `geometry_msgs/TwistStamped` | швидкість |
| `/ap/geopose/filtered`, `/ap/navsat` | `geographic_msgs/GeoPoseStamped`, `sensor_msgs/NavSatFix` | глобальна поза, GNSS |
| `/ap/battery`, `/ap/status`, `/ap/rc` | `sensor_msgs/BatteryState`, `ardupilot_msgs/Status`, `ardupilot_msgs/Rc` | батарея; armed, mode, flying, external_control, failsafe |
| `/ap/tf_static`, `/ap/clock`, `/ap/time` | tf2, час | кріплення, годинник для sim time |
| `/ap/cmd_vel` (вхід) | `geometry_msgs/TwistStamped` | швидкість у GUIDED; frame `map` (ENU) або `base_link` |
| `/ap/cmd_gps_pose` (вхід) | `ardupilot_msgs/GlobalPosition` | глобальна ціль у GUIDED |
| `/ap/arm_motors`, `/ap/mode_switch`, `/ap/prearm_check`, `/ap/experimental/takeoff` | сервіси | арм, режим (номер режиму Copter: GUIDED = 4, LAND = 9), предарм, зліт |

Важливо: AP_DDS сам перетворює ENU ↔ NED — для `cmd_vel` за `header.frame_id` (`map` — світові ENU, `base_link` — корпус). Тобто, не так, як у PX4, твій ROS-вузол живе гет повністю в угодах ROS. QoS: пози та швидкості — BEST_EFFORT, `/ap/status` і `tf_static` — RELIABLE + TRANSIENT_LOCAL (підписник BEST_EFFORT ся зійде і з тим, і з другим).

### Порядок дій в ArduPilot
ArduCopter армиться лиш у режимі, що дозволяє арм (GUIDED підходить), і лиш після pre-arm перевірок. Зліт у GUIDED — окрема команда (сервіс takeoff = `MAV_CMD_NAV_TAKEOFF`); без неї апарат на землі ігнорує горизонтальні уставки. Послідовність у вузлі: GUIDED → arm → takeoff(alt) → уставки швидкості/позиції → LAND. Таймаут уставок швидкості в GUIDED — `GUID_TIMEOUT` (секунди): як `cmd_vel` перестав приходити, апарат ся зупинить. То той самий принцип «доказу життя», що й Offboard у PX4.

{{diagram:ap-dds-guided-seq|Порядок важен: GUIDED, арм, отдельный takeoff и только потом поток cmd_vel в фрейме map; замолчал — через GUID_TIMEOUT аппарат встаёт.}}

### MAVROS
MAVROS — вузол, який тримає MAVLink-з'єднання і розкладає його по плагінах: `/mavros/state` (підключення, armed, mode), `/mavros/local_position/pose`, `/mavros/setpoint_position/local`, `/mavros/setpoint_velocity/cmd_vel`, сервіси `/mavros/cmd/arming`, `/mavros/set_mode`, `/mavros/cmd/takeoff`, `/mavros/mission/push`, параметри, геозони, повний доступ до будь-якого MAVLink-повідомлення через `mavros_msgs/Mavlink`. Він теж перетворює ENU ↔ NED. Запуск: `ros2 launch mavros apm.launch fcu_url:=udp://:14550@` (підключення до SITL або до роутера на companion).

Коли MAVROS ліпший за AP_DDS: треба функціонал, якого нема в AP_DDS (місії, параметри, камера, довільні MAVLink-повідомлення); парк мішаний (одна кодова база для ArduPilot і PX4 через MAVLink); прошивка без DDS. Коли AP_DDS ліпший: менше шарів і затримка, стандартні типи ROS, нема MAVLink-трафіку на companion для ROS-частини.

### Порівняння маршрутів
| | PX4 uXRCE-DDS | ArduPilot AP_DDS | MAVROS |
|---|---|---|---|
| Що на дроті | uORB-структури через XRCE | DDS-клієнт, стандартні типи ROS | MAVLink |
| Система координат з боку ROS | NED/FRD (конвертуєш сам) | ENU/FLU (конвертує прошивка) | ENU/FLU (конвертує MAVROS) |
| Сумісність версій | px4_msgs = версія PX4, суфікси _vN | ardupilot_msgs з тої самої гілки | діалект MAVLink, стабільно |
| Охоплення функцій | вшитко, що в dds_topics.yaml | набір /ap/*, росте | майже весь MAVLink |
| Зовнішнє керування | Offboard, потік > 2 Гц | GUIDED, `GUID_TIMEOUT` | GUIDED/Offboard через setpoint_* |

### Один автомат, дві обгортки
`ap_dds_square.py` вживає той самий `OffboardFSM`, що й вузол PX4. Різниця лиш в обгортці: спостереження з `/ap/status` і `/ap/pose/filtered` (ENU → NED для автомата), «режим зовнішнього керування» = GUIDED, запит арму перетворюється на «спершу GUIDED, потім arm», після виходу на висоту — сервіс takeoff, уставки позиції автомата перетворюються на швидкість (П-регулятор з обмеженням 3 м/с) на `/ap/cmd_vel` у фреймі `map`. Логіка захистів і вшиткі тести автомата лишаються чинні.

## practice
### Крок 1. SITL з DDS
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

### Крок 2. Квадрат через AP_DDS
`ros2 launch uav_ros2_labs ap_square.launch.py`. Звір переходи автомата в логу з режимами в Mission Planner/QGC. Побудуй траєкторію з `/tmp/ap_flight.csv`. Зупини вузол посеред квадрата й зміряй за логом ArduPilot, за скільки апарат ся зупинив, — порівняй з `GUID_TIMEOUT`.

### Крок 3. Той самий квадрат через MAVROS
Напиши обгортку `mavros_square.py` (той самий автомат): `/mavros/state` → armed/mode, `/mavros/local_position/pose` → позиція, `/mavros/setpoint_position/local` → уставки, сервіси `cmd/arming`, `set_mode` (custom_mode "GUIDED"), `cmd/takeoff`. Перевір, що тестів автомата не довелося чіпати.

### Крок 4. Порівняння
Зміряй затримку «уставка → зміна швидкості в позі» для AP_DDS і MAVROS (за мітками часу в bag), завантаження CPU агента й MAVROS, і заповни таблицю з теорії своїми цифрами.


### Що має вийти і що записати
- **Квадрат через AP_DDS.** У логу вузла переходи автомата сходяться з режимами в наземці (GUIDED на цілому квадраті), а траєкторія з CSV — квадрат із кутами в межах пари метрів від заданих точок. Збережи графік.
- **GUID_TIMEOUT.** Як зупиниш вузол посеред квадрата, апарат зависає через `GUID_TIMEOUT` (за замовчуванням 3 с). Час від останньої уставки до зупинки за логом ArduPilot мусить зійтися з параметром ± період публікації уставок.
- **MAVROS.** Той самий автомат через обгортку проходить ті самі тести. Як поведінка інша, шукай різницю в системах координат і одиницях топіків, а не в автоматі.
- **Таблиця порівняння:** затримка «уставка → початок зміни швидкості» (медіана й максимум за 20+ уставками) і завантаження CPU агента AP_DDS і MAVROS. Записуй свої цифри: вони залежать від машини та збірки, чужі тобі ніц не поможуть.

Лабораторну зараховано, коли квадрат пролетіли через AP_DDS (графік, переходи), перевірено `GUID_TIMEOUT`, є обгортка MAVROS із тим самим автоматом і таблиця порівняння з вимірюваннями.

### Крок 8. Перевірки, котрі можна виконати (прогнано автором)
Перевірка наявності DDS у збірці та чисельне відтворення перетворень кадрів AP_DDS 4.7.2 зі справжнім виводом; кожен рядок пояснено в російськім оригіналі (увага: `base_link` linear.y у 4.7.2 не інвертується).

```bash
strings build/sitl/bin/arducopter | grep -c "rt/ap/"      # stock 4.7.2 SITL build (./waf copter)
# 0
# param audit of the same SITL (companion_lab.py from ap-companion):
# DDS_ENABLE        = None
```

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

## diagnostics
- **Симптом:** топіків `/ap/*` нема
  - Можлива причина: SITL зібрано без `--enable-DDS`, `DDS_ENABLE = 0`, агент на іншому порту або в іншому домені.
  - Що зробити: збірка з DDS; порт 2019; однаковий `ROS_DOMAIN_ID`/`DDS_DOMAIN_ID`.
- **Симптом:** `arm_motors` вертає false
  - Можлива причина: режим не дозволяє арм або не пройдено pre-arm перевірки.
  - Що зробити: спершу GUIDED; `/ap/prearm_check`; STATUSTEXT у GCS.
- **Симптом:** уставки `cmd_vel` ігноруються на землі
  - Можлива причина: не виконано takeoff у GUIDED.
  - Що зробити: сервіс takeoff, дочекатися висоти, потім швидкості.
- **Симптом:** апарат летить «на схід замість півночі»
  - Можлива причина: уставку в ENU вислано як NED (або навпаки), frame_id не той.
  - Що зробити: frame_id `map` для світових ENU; конвертація лиш на межі.

## references
- ArduPilot — AP_DDS README (setup, topics, services) | https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_DDS/README.md | primary | A
- ArduPilot — ROS 2 with ArduPilot (dev docs) | https://ardupilot.org/dev/docs/ros2.html | primary | A
- ArduPilot — AP_DDS topic and service tables (source) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/AP_DDS | primary | A
- MAVROS | https://github.com/mavlink/mavros | primary | A
- ArduPilot — Copter commands in Guided mode | https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html | primary | A

## checklist
- Підключаю ArduPilot до ROS 2 через AP_DDS (параметри, агент, збірка SITL)
- Знаю топіки й сервіси /ap/* і в яких вони фреймах
- Тримаюся порядку GUIDED → arm → takeoff → уставки → LAND і знаю GUID_TIMEOUT
- Вживаю MAVROS там, де AP_DDS не стає
- Порівнюю маршрути PX4/AP_DDS/MAVROS за фактами й вимірюваннями
- Повторно вживаю один автомат станів для різних автопілотів
