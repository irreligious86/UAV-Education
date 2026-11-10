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

### MAVROS
MAVROS — вузол, який тримає MAVLink-з'єднання і розкладає його по плагінах, як по шуфлядах: `/mavros/state` (підключення, armed, mode), `/mavros/local_position/pose`, `/mavros/setpoint_position/local`, `/mavros/setpoint_velocity/cmd_vel`, сервіси `/mavros/cmd/arming`, `/mavros/set_mode`, `/mavros/cmd/takeoff`, `/mavros/mission/push`, параметри, геозони, повний доступ до будь-якого MAVLink-повідомлення через `mavros_msgs/Mavlink`. Він теж перетворює ENU ↔ NED. Запуск: `ros2 launch mavros apm.launch fcu_url:=udp://:14550@` (підключення до SITL або до роутера на companion).

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
docker compose --profile ardupilot up --build    # або нативно: waf configure --enable-DDS, sim_vehicle.py --enable-DDS
docker compose run --rm ros bash
ros2 topic list | grep /ap/
ros2 topic echo /ap/status --once
ros2 service call /ap/mode_switch ardupilot_msgs/srv/ModeSwitch "{mode: 4}"
```

### Крок 2. Квадрат через AP_DDS
`ros2 launch uav_ros2_labs ap_square.launch.py`. Звір переходи автомата в лозі з режимами в Mission Planner/QGC. Побудуй траєкторію з `/tmp/ap_flight.csv`. Зупини вузол посеред квадрата й зміряй за логом ArduPilot, за скільки апарат ся зупинив, — порівняй з `GUID_TIMEOUT`.

### Крок 3. Той самий квадрат через MAVROS
Напиши обгортку `mavros_square.py` (той самий автомат): `/mavros/state` → armed/mode, `/mavros/local_position/pose` → позиція, `/mavros/setpoint_position/local` → уставки, сервіси `cmd/arming`, `set_mode` (custom_mode "GUIDED"), `cmd/takeoff`. Перевір, що тестів автомата не довелося чіпати.

### Крок 4. Порівняння
Зміряй затримку «уставка → зміна швидкості в позі» для AP_DDS і MAVROS (за мітками часу в bag), завантаження CPU агента й MAVROS, і заповни таблицю з теорії своїми цифрами.


### Що має вийти і що записати
- **Квадрат через AP_DDS.** У лозі вузла переходи автомата сходяться з режимами в наземці (GUIDED на цілому квадраті), а траєкторія з CSV — квадрат із кутами в межах пари метрів від заданих точок. Збережи графік.
- **GUID_TIMEOUT.** Як зупиниш вузол посеред квадрата, апарат зависає через `GUID_TIMEOUT` (за замовчуванням 3 с). Час від останньої уставки до зупинки за логом ArduPilot мусить зійтися з параметром ± період публікації уставок.
- **MAVROS.** Той самий автомат через обгортку проходить ті самі тести. Як поведінка інша, шукай різницю в системах координат і одиницях топіків, а не в автоматі.
- **Таблиця порівняння:** затримка «уставка → початок зміни швидкості» (медіана й максимум за 20+ уставками) і завантаження CPU агента AP_DDS і MAVROS. Записуй свої цифри: вони залежать від машини та збірки, чужі тобі ніц не поможуть.

Лабораторну зараховано, коли квадрат пролетіли через AP_DDS (графік, переходи), перевірено `GUID_TIMEOUT`, є обгортка MAVROS із тим самим автоматом і таблиця порівняння з вимірюваннями.

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
