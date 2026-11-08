---
id: ros2-basics
title: "ROS 2 для борта: узлы, топики, QoS, tf2, bag"
level: L3
readingTime: 50 мин
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
---

## summary
ROS 2 — не «библиотека для дронов», а способ собрать бортовое ПО из независимых процессов, которые общаются через DDS. Его ценность для БПЛА — готовые узлы (камеры, лидары, SLAM, Nav2), единые типы сообщений и инструменты отладки: запись и повтор всего трафика, граф узлов, визуализация. Его цена — сложность: QoS, системы координат, время. Модуль даёт ровно ту часть ROS 2, без которой не взлетит ни один offboard-узел: граф узлов, топики/сервисы/действия, параметры и launch, QoS и почему подписка на PX4 «по умолчанию» молчит, REP-103/105 и `tf2`, время симуляции и `ros2 bag`. Лабораторная: узел-логгер телеметрии, запись и повтор bag, разбор QoS-несовместимости своими руками. Окружение — `examples/ros2-docker/`.

## theory
### Граф: узлы, топики, сервисы, действия
- **Узел (node)** — процесс или часть процесса с именем, параметрами и интерфейсами. Правило проектирования: один узел — одна ответственность (мост, восприятие, решение, защита).
- **Топик** — поток сообщений одного типа «один-ко-многим», издатели и подписчики не знают друг о друге. Телеметрия, уставки, изображения.
- **Сервис** — запрос-ответ (`ArmMotors`, `ModeSwitch`). Синхронная семантика, но вызывать в узле надо асинхронно (`call_async`), иначе можно заблокировать собственный executor.
- **Действие (action)** — долгая цель с обратной связью и отменой (`NavigateToPose` в Nav2). Это топики+сервисы, собранные в протокол.
- **Параметры** — типизированные настройки узла (`ros2 param set /node alt 7.0`), с колбэком проверки при изменении.

DDS сам находит участников в сети (discovery) внутри одного `ROS_DOMAIN_ID`. На борту с companion и ноутбуком в одной Wi-Fi-сети это значит: без разных доменов или фильтров ноутбук «увидит» и сможет публиковать в топики аппарата. Для полётов в поле — отдельный домен, а лучше `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` (Jazzy; в Humble — `ROS_LOCALHOST_ONLY=1`) на борту и мост наружу только для нужных топиков.

{{diagram:ros2-graph|Учебная система как граф: мост к автопилоту, логгер, автомат состояний, восприятие и watchdog — отдельные узлы.}}

### QoS: почему подписка молчит
Каждый издатель и подписчик имеют профиль QoS: **reliability** (RELIABLE/BEST_EFFORT), **durability** (VOLATILE/TRANSIENT_LOCAL — получит ли поздний подписчик последнее сообщение), **history/depth** (сколько хранить), deadline, lifespan, liveliness. Связь устанавливается только при **совместимых** профилях, и несовместимость не вызывает ошибку — подписчик просто ничего не получает (в логе может появиться предупреждение «incompatible QoS»).

Главное правило: издатель BEST_EFFORT + подписчик RELIABLE = нет связи. PX4 публикует `/fmu/out/*` как BEST_EFFORT (и TRANSIENT_LOCAL), а подписчик ROS 2 по умолчанию RELIABLE. Поэтому подписка на PX4 делается профилем `qos_profile_sensor_data` (BEST_EFFORT) или явным `QoSProfile`. Зачем BEST_EFFORT для телеметрии: при потере пакета по Wi-Fi повтор старого положения бесполезен, нужен следующий — та же логика, что UDP против TCP в модуле mav-routing.

Проверка: `ros2 topic info -v /fmu/out/vehicle_status_v1` покажет профили обеих сторон.

{{diagram:ros2-qos|Совместимость reliability: BEST_EFFORT-издатель не связывается с RELIABLE-подписчиком — молча.}}

### Системы координат: REP-103 и REP-105
ROS живёт в **ENU** (мир) и **FLU** (корпус) — REP-103; автопилоты — в NED/FRD. Это главный источник ошибок интеграции (модуль math-linalg-rot): x/y меняются местами, z меняет знак, рысканье ψ_enu = 90° − ψ_ned, кватернионы в ROS хранятся как (x, y, z, w). REP-105 задаёт стандартные фреймы: `map` (глобальный, без дрейфа, может прыгать), `odom` (непрерывный, дрейфует), `base_link` (корпус). Мосты по-разному берут это на себя: AP_DDS публикует сразу в ENU/`map`/`base_link`, PX4 uXRCE-DDS — в NED/FRD, как внутри PX4, и конвертация на вашей стороне.

`tf2` — дерево преобразований между фреймами во времени: «где была камера относительно `map` в момент кадра». Узел публикует `TransformStamped` в `/tf` (динамические) и `/tf_static` (крепления датчиков), а потребитель спрашивает `lookup_transform(target, source, time)`. Камера на кронштейне — статическое преобразование `base_link → camera_link`, его задают один раз в launch-файле.

### Время
У каждого сообщения с заголовком есть `header.stamp`. В симуляции время идёт по `/clock` (параметр `use_sim_time:=true`), иначе узлы и bag живут в разных временах, и `tf2` отказывается давать преобразования «из будущего». PX4 использует свои метки времени в микросекундах (`timestamp`) и синхронизирует их с агентом; ArduPilot публикует `/ap/time` и `/ap/clock`.

### Launch и параметры
Launch-файл (Python) запускает набор узлов с параметрами, пространствами имён, перенаправлением топиков (`remappings`). Это то, что запускается на борту при старте: systemd-сервис → `ros2 launch`. Параметры в YAML-файле, а не в коде — чтобы один и тот же пакет работал на двух разных аппаратах.

### ros2 bag
`ros2 bag record -o run1 /topic1 /topic2` пишет трафик в файл (в Jazzy по умолчанию MCAP, в Humble — SQLite3; формат задаётся ключом `-s`); `ros2 bag play run1` воспроизводит его, и ваши узлы не отличат повтор от полёта. Это главный инструмент отладки: записали полёт с ошибкой — воспроизводите и чините узел на столе сколько угодно раз. Запись всех топиков с камерами на борту быстро съедает диск и CPU: пишите сжатые изображения или с пониженной частотой.

## practice
### Шаг 1. Окружение
```bash
cd examples/ros2-docker
docker compose build ros
docker compose run --rm ros bash
ros2 doctor --report | head -20
```
Образ собирается на ROS 2 Jazzy (Ubuntu 24.04); запасной вариант — `ROS_DISTRO=humble docker compose build ros`. Если Docker недоступен — установите ROS 2 Jazzy на Ubuntu 24.04 (или Humble на 22.04) по официальной инструкции и соберите `ws/` через `colcon build`.

### Шаг 2. Граф руками
В двух терминалах `ros2 run demo_nodes_py talker` и `listener`; посмотрите `ros2 node list`, `ros2 topic info -v /chatter`, `ros2 topic hz`. Затем опубликуйте в топик с BEST_EFFORT (`ros2 topic pub --qos-reliability best_effort ...`) и подпишитесь RELIABLE (`ros2 topic echo --qos-reliability reliable ...`) — связи нет. Поменяйте подписчика на best_effort — появилась. Запишите вывод `topic info -v` в обоих случаях.

### Шаг 3. Логгер телеметрии
Запустите PX4 SITL (`docker compose --profile px4 up`) или ArduPilot SITL с DDS. Запустите `ros2 run uav_ros2_labs telemetry_logger --ros-args -p source:=px4`. Прочитайте код: QoS подписки, таймер записи независимо от частоты сообщений, конвертация NED→ENU для PX4 (и её отсутствие для AP_DDS — он уже в ENU). Поменяйте QoS подписки на RELIABLE и убедитесь, что CSV перестал пополняться.

### Шаг 4. Bag: запись и повтор
Запишите 60 с полёта в bag, остановите SITL, воспроизведите bag и запустите логгер снова — CSV должен получиться тем же (с точностью до момента старта). Это и есть «отладка без аппарата».

### Шаг 5. tf2
Опубликуйте статическое преобразование камеры (`ros2 run tf2_ros static_transform_publisher --x 0.1 --z -0.05 --pitch 0.5 --frame-id base_link --child-frame-id camera_link`) и запросите `ros2 run tf2_ros tf2_echo base_link camera_link`. Объясните, почему pitch положительный означает «камера смотрит вниз» в FLU.

Лабораторная засчитывается, когда показан эффект QoS (вывод topic info), CSV логгера получен в SITL и из bag, и объяснено преобразование камеры.

## diagnostics
- **Симптом:** `ros2 topic echo /fmu/out/...` молчит, хотя `topic list` его показывает
  - Возможная причина: QoS — подписка RELIABLE на BEST_EFFORT-издателя; или нет суффикса версии `_v1`.
  - Что сделать: `--qos-reliability best_effort`; проверить точное имя топика.
- **Симптом:** ноутбук в той же сети «вмешивается» в топики аппарата
  - Возможная причина: общий ROS_DOMAIN_ID и открытый discovery.
  - Что сделать: свой домен, localhost-only на борту, явный мост наружу.
- **Симптом:** tf2 «extrapolation into the future» при воспроизведении bag
  - Возможная причина: узлы на системном времени, bag — на времени записи.
  - Что сделать: `ros2 bag play --clock` и `use_sim_time:=true` у всех узлов.
- **Симптом:** аппарат летит «боком» после перевода координат
  - Возможная причина: перепутаны ENU/NED или FLU/FRD, или порядок компонент кватерниона.
  - Что сделать: тесты конвертаций (`frames.py`), проверка на неподвижном аппарате с известным курсом.

## references
- ROS 2 Jazzy — Concepts (nodes, topics, services, actions) | https://docs.ros.org/en/jazzy/Concepts.html | primary | A
- ROS 2 — About Quality of Service settings (compatibility table) | https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Quality-of-Service-Settings.html | primary | A
- REP-103 — Standard units and coordinate conventions | https://www.ros.org/reps/rep-0103.html | primary | A
- REP-105 — Coordinate frames for mobile platforms | https://www.ros.org/reps/rep-0105.html | primary | A
- PX4 — ROS 2 user guide (QoS for /fmu/out topics) | https://docs.px4.io/main/en/ros2/user_guide.html | primary | A

## checklist
- Различаю топик, сервис, действие и параметр и выбираю нужный
- Объясняю совместимость QoS и почему подписка на PX4 требует BEST_EFFORT
- Знаю REP-103/105 и где мост конвертирует фреймы, а где нет
- Пользуюсь tf2 для креплений датчиков
- Управляю временем (sim time) и пишу/воспроизвожу bag
- Изолирую ROS 2 аппарата от посторонних участников сети
