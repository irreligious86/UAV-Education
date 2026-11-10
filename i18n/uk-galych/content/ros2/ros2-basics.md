---
id: ros2-basics
title: "ROS 2 для борту: вузли, топіки, QoS, tf2, bag"
level: L3
readingTime: 50 хв
firmware: PX4 · ArduPilot
status: published
added: 2026-11-08
tags:
  - ROS 2
  - QoS
  - tf2
  - rosbag
  - launch
related:
  - math-linalg-rot
  - px4-ros2
  - mav-sdk
next:
  - ros2-px4
source: content/ros2/ros2-basics.md
source_hash: 17265f1f6d76
---

## summary
ROS 2 — то не «бібліотека для дронів», а спосіб зібрати бортове ПЗ з незалежних процесів, що говорять між собою через DDS. Його вартість для БпЛА — готові вузли (камери, лідари, SLAM, Nav2), єдині типи повідомлень та інструменти налагодження: запис і повтор цілого трафіку, граф вузлів, візуалізація. Його ціна — складність: QoS, системи координат, час. Модуль дає рівно ту частину ROS 2, без якої не злетить жоден offboard-вузол: граф вузлів, топіки/сервіси/дії, параметри й launch, QoS і чому підписка на PX4 «за замовчуванням» мовчить, REP-103/105 і `tf2`, час симуляції та `ros2 bag`. Лабораторна: вузол-логер телеметрії, запис і повтор bag, розбір QoS-несумісності власноруч. Оточення — `examples/ros2-docker/`.

## theory
### Граф: вузли, топіки, сервіси, дії
- **Вузол (node)** — процес або частина процесу з іменем, параметрами й інтерфейсами. Правило проєктування: один вузол — одна відповідальність (міст, сприйняття, рішення, захист).
- **Топік** — потік повідомлень одного типу «один-до-багатьох», видавці й підписники ніц не знають одне про одного. Телеметрія, уставки, зображення.
- **Сервіс** — запит-відповідь (`ArmMotors`, `ModeSwitch`). Семантика синхронна, але викликати у вузлі треба асинхронно (`call_async`), бо інакше можна заблокувати власний executor.
- **Дія (action)** — довга ціль зі зворотним зв'язком і скасуванням (`NavigateToPose` у Nav2). То топіки+сервіси, зібрані в протокол.
- **Параметри** — типізовані налаштування вузла (`ros2 param set /node alt 7.0`), з колбеком перевірки під час зміни.

DDS сам знаходить учасників у мережі (discovery) в межах одного `ROS_DOMAIN_ID`. На борту з companion і ноутбуком в одній Wi-Fi-мережі то значить: без різних доменів ци фільтрів ноутбук «побачить» топіки апарата і зможе в них публікувати. Для польотів у полі — окремий домен, а ще ліпше `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` (Jazzy; у Humble — `ROS_LOCALHOST_ONLY=1`) на борту й міст назовні лиш для потрібних топіків.

{{diagram:ros2-graph|Навчальна система як граф: міст до автопілота, логер, автомат станів, сприйняття й watchdog — окремі вузли.}}

### QoS: чому підписка мовчить
Кожен видавець і підписник мають профіль QoS: **reliability** (RELIABLE/BEST_EFFORT), **durability** (VOLATILE/TRANSIENT_LOCAL — ци дістане пізній підписник останнє повідомлення), **history/depth** (скільки тримати), deadline, lifespan, liveliness. Зв'язок ся встановлює лиш за **сумісних** профілів, і несумісність помилки не дає — підписник просто ніц не дістає (у логу може ся появити попередження «incompatible QoS»).

Головне правило: видавець BEST_EFFORT + підписник RELIABLE = зв'язку нема. PX4 публікує `/fmu/out/*` як BEST_EFFORT (і TRANSIENT_LOCAL), а підписник ROS 2 за замовчуванням RELIABLE. Тому підписку на PX4 роблять профілем `qos_profile_sensor_data` (BEST_EFFORT) або явним `QoSProfile`. Нащо BEST_EFFORT для телеметрії: як пакет пропав по Wi-Fi, повтор старого положення ніц не дасть, треба наступне — та сама логіка, що UDP проти TCP у модулі mav-routing.

Перевірка: `ros2 topic info -v /fmu/out/vehicle_status_v1` покаже профілі обох сторін.

{{diagram:ros2-qos|Сумісність reliability: BEST_EFFORT-видавець не зв'язується з RELIABLE-підписником — і то мовчки.}}

### Системи координат: REP-103 і REP-105
ROS живе в **ENU** (світ) і **FLU** (корпус) — REP-103; автопілоти — у NED/FRD. То головне джерело помилок інтеграції (модуль math-linalg-rot): x/y міняються місцями, z міняє знак, рискання ψ_enu = 90° − ψ_ned, кватерніони в ROS тримають як (x, y, z, w). REP-105 задає стандартні фрейми: `map` (глобальний, без дрейфу, може стрибати), `odom` (неперервний, дрейфує), `base_link` (корпус). Мости беруть то на себе по-різному: AP_DDS публікує зразу в ENU/`map`/`base_link`, PX4 uXRCE-DDS — у NED/FRD, як усередині PX4, і конвертація — з твого боку.

`tf2` — дерево перетворень між фреймами в часі: «де була камера відносно `map` у момент кадру». Вузол публікує `TransformStamped` у `/tf` (динамічні) і `/tf_static` (кріплення датчиків), а споживач питає `lookup_transform(target, source, time)`. Камера на кронштейні — статичне перетворення `base_link → camera_link`, його задають раз у launch-файлі.

### Час
Кожне повідомлення із заголовком має `header.stamp`. У симуляції час іде за `/clock` (параметр `use_sim_time:=true`), бо інакше вузли й bag живуть у різних часах, і `tf2` не хоче давати перетворення «з майбутнього». PX4 вживає власні мітки часу в мікросекундах (`timestamp`) і синхронізує їх з агентом; ArduPilot публікує `/ap/time` і `/ap/clock`.

### Launch і параметри
Launch-файл (Python) запускає набір вузлів із параметрами, просторами імен, перенаправленням топіків (`remappings`). То те, що стартує на борту: systemd-сервіс → `ros2 launch`. Параметри — в YAML-файлі, а не в коді, аби той самий пакет працював на двох різних апаратах.

### ros2 bag
`ros2 bag record -o run1 /topic1 /topic2` пише трафік у файл (у Jazzy за замовчуванням MCAP, у Humble — SQLite3; формат задає ключ `-s`); `ros2 bag play run1` відтворює його, і твої вузли не відрізнять повтору від польоту. То головний інструмент налагодження: записав політ із помилкою — відтворюй і лагодь вузол на столі скільки душа забагне. Запис вшитких топіків із камерами на борту шпарко з'їдає диск і CPU: пиши стиснені зображення або зі зниженою частотою.

## practice
### Крок 1. Оточення
```bash
cd examples/ros2-docker
docker compose build ros
docker compose run --rm ros bash
ros2 doctor --report | head -20
```
Образ збирається й перевіряється в CI на ROS 2 Jazzy (Ubuntu 24.04 усередині контейнера, тож хост може бути й на 22.04). Збірка з `ROS_DISTRO=humble` зараз не проходить: гілка humble у micro-ROS-Agent не компілюється з Fast-CDR 2.x. Як Docker недоступний — постав ROS 2 Jazzy на Ubuntu 24.04 (або Humble на 22.04) за офіційною інструкцією і збери `ws/` через `colcon build`.

### Крок 2. Граф руками
У двох терміналах `ros2 run demo_nodes_py talker` і `listener`; глянь `ros2 node list`, `ros2 topic info -v /chatter`, `ros2 topic hz`. Потім опублікуй у топік із BEST_EFFORT (`ros2 topic pub --qos-reliability best_effort ...`) і підпишися RELIABLE (`ros2 topic echo --qos-reliability reliable ...`) — зв'язку нема. Зміни підписника на best_effort — ади, появився. Запиши вивід `topic info -v` в обох випадках.

### Крок 3. Логер телеметрії
Запусти PX4 SITL (`docker compose --profile px4 up`) або ArduPilot SITL з DDS. Запусти `ros2 run uav_ros2_labs telemetry_logger --ros-args -p source:=px4`. Прочитай код: QoS підписки, таймер запису незалежно від частоти повідомлень, конвертація NED→ENU для PX4 (і її брак для AP_DDS — він уже в ENU). Зміни QoS підписки на RELIABLE і переконайся, що CSV перестав рости.

### Крок 4. Bag: запис і повтор
Запиши 60 с польоту в bag, зупини SITL, відтвори bag і запусти логер знов — CSV мусить вийти той самий (з точністю до моменту старту). То і є «налагодження без апарата».

### Крок 5. tf2
Опублікуй статичне перетворення камери (`ros2 run tf2_ros static_transform_publisher --x 0.1 --z -0.05 --pitch 0.5 --frame-id base_link --child-frame-id camera_link`) і запитай `ros2 run tf2_ros tf2_echo base_link camera_link`. Поясни, чому додатний pitch значить «камера дивиться вниз» у FLU.

Лабораторну зараховано, коли показано ефект QoS (вивід topic info), CSV логера дістали в SITL і з bag, і пояснено перетворення камери.

## diagnostics
- **Симптом:** `ros2 topic echo /fmu/out/...` мовчить, хоч `topic list` його показує
  - Можлива причина: QoS — підписка RELIABLE на BEST_EFFORT-видавця; або нема суфікса версії `_v1`.
  - Що зробити: `--qos-reliability best_effort`; перевірити точне ім'я топіка.
- **Симптом:** ноутбук у тій самій мережі «влазить» у топіки апарата
  - Можлива причина: спільний ROS_DOMAIN_ID і відкритий discovery.
  - Що зробити: свій домен, localhost-only на борту, явний міст назовні.
- **Симптом:** tf2 «extrapolation into the future» під час відтворення bag
  - Можлива причина: вузли на системному часі, bag — на часі запису.
  - Що зробити: `ros2 bag play --clock` і `use_sim_time:=true` у вшитких вузлів.
- **Симптом:** апарат летить «боком» після перетворення координат
  - Можлива причина: поплутано ENU/NED або FLU/FRD, або порядок компонент кватерніона.
  - Що зробити: тести конвертацій (`frames.py`), перевірка на нерухомому апараті з відомим курсом.

## references
- ROS 2 Jazzy — Concepts (nodes, topics, services, actions) | https://docs.ros.org/en/jazzy/Concepts.html | primary | A
- ROS 2 — About Quality of Service settings (compatibility table) | https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Quality-of-Service-Settings.html | primary | A
- REP-103 — Standard units and coordinate conventions | https://www.ros.org/reps/rep-0103.html | primary | A
- REP-105 — Coordinate frames for mobile platforms | https://www.ros.org/reps/rep-0105.html | primary | A
- PX4 — ROS 2 user guide (QoS for /fmu/out topics) | https://docs.px4.io/main/en/ros2/user_guide.html | primary | A

## checklist
- Розрізняю топік, сервіс, дію та параметр і вибираю, що треба
- Пояснюю сумісність QoS і чому підписка на PX4 потребує BEST_EFFORT
- Знаю REP-103/105 і де міст конвертує фрейми, а де ні
- Вживаю tf2 для кріплень датчиків
- Керую часом (sim time) і пишу/відтворюю bag
- Відгороджую ROS 2 апарата від сторонніх учасників мережі
