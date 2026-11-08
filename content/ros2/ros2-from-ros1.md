---
id: ros2-from-ros1
title: "Из ROS 1 в ROS 2: читать старые проекты и переносить их"
level: L3
readingTime: 30 мин
firmware: PX4 · ArduPilot
status: published
added: 2026-11-08
tags:
  - ROS 1
  - ROS 2
  - миграция
  - MAVROS
  - catkin
related:
  - ros2-basics
  - ros2-ardupilot
next:
  - ros2-app-arch
---

## summary
ROS 1 Noetic закончил поддержку в мае 2025 года, но половина открытых дроновых проектов, статей и туториалов — на ROS 1: MAVROS 1, catkin-воркспейсы, launch в XML, `rospy`. Модуль учит быстро читать такой проект («что здесь главное и что от чего зависит»), знать соответствия понятий ROS 1 → ROS 2, решать, переносить или запускать рядом через мост, и переносить небольшой пакет. Лабораторная: перенос узла ROS 1 на ROS 2 с сохранением поведения, проверенный на записанных данных.

## theory
### Чем ROS 2 отличается по существу
| ROS 1 | ROS 2 | Что это меняет |
|---|---|---|
| `roscore` (master) — центральный узел имён | нет master, DDS discovery | нет единой точки отказа; нужны домены/ограничение discovery |
| TCPROS/UDPROS | DDS с QoS | надо думать о QoS (модуль ros2-basics) |
| `rospy`, `roscpp` | `rclpy`, `rclcpp` | API другой, но идеи те же |
| catkin, `catkin_make`/`catkin build` | ament, `colcon build` | другая сборка, `package.xml` format 3 |
| launch XML (`.launch`) | launch Python/XML/YAML (`.launch.py`) | логика в launch-файле |
| параметры в глобальном сервере | параметры у каждого узла | `rosparam` → `ros2 param` к конкретному узлу |
| `rosbag` (`.bag`) | `ros2 bag` (SQLite3/MCAP) | конвертеры есть (rosbags) |
| `tf` | `tf2` (был и в ROS 1) | почти без изменений |
| nodelets | компоненты (composable nodes) | несколько узлов в одном процессе без копирования |
| MAVROS 1 | MAVROS 2 (`mavros` в ROS 2) | те же плагины, другие имена сервисов/QoS |

### Как читать ROS 1 проект за 30 минут
1. **Корень**: `package.xml`/`CMakeLists.txt` — зависимости (что за датчики, MAVROS ли, OpenCV ли).
2. **Launch-файлы** (`launch/*.launch`) — что запускается, с какими параметрами и remap-ами. Это «схема системы».
3. **Узлы** (`scripts/*.py`, `src/*.cpp`): найдите `init_node`, `Subscriber`, `Publisher`, `Service`, `Timer`/`Rate`. Нарисуйте граф: что слушает, что публикует.
4. **Параметры** (`config/*.yaml`, `rospy.get_param`) — что настраивается.
5. **Сообщения** (`msg/`, `srv/`) — свои типы.
6. **MAVROS-специфика**: `/mavros/setpoint_*`, `/mavros/set_mode`, `/mavros/cmd/arming` — где проект управляет аппаратом и в какой системе координат.

Итог — граф узлов (как в ros2-basics) и список внешних зависимостей. С ним понятно, сколько стоит перенос.

### Перенос или мост
- **ros1_bridge** — двунаправленный мост топиков/сервисов между ROS 1 и ROS 2 при запущенных обоих. Требует совместимой сборки (одинаковые типы сообщений с обеих сторон), исторически — Noetic + Foxy/Humble из исходников. После окончания поддержки Noetic это временное решение.
- **Перенос** — правильный путь для живого кода. Порядок: сообщения → библиотечный код без ROS (вынести!) → узлы → launch → тесты на записанных данных.
- **Запуск ROS 1 в контейнере** — для «посмотреть, как это работало» и для записи эталонных данных до переноса.

### Типовые замены в коде (Python)
| ROS 1 (rospy) | ROS 2 (rclpy) |
|---|---|
| `rospy.init_node("n")` | `rclpy.init(); node = Node("n")` |
| `rospy.Subscriber("/t", T, cb)` | `node.create_subscription(T, "/t", cb, qos)` |
| `rospy.Publisher("/t", T, queue_size=10)` | `node.create_publisher(T, "/t", 10)` |
| `rospy.Rate(20); while not rospy.is_shutdown(): ... rate.sleep()` | `node.create_timer(0.05, tick); rclpy.spin(node)` |
| `rospy.get_param("~alt", 5.0)` | `node.declare_parameter("alt", 5.0); node.get_parameter("alt").value` |
| `rospy.ServiceProxy("/s", S)(req)` | `cli = node.create_client(S, "/s"); cli.call_async(req)` |
| `rospy.Time.now()` | `node.get_clock().now()` |
| `rospy.loginfo(...)` | `node.get_logger().info(...)` |

Главная смена мышления — **цикл `while` с `rate.sleep()` заменяется таймером и колбэками**, а синхронный вызов сервиса внутри колбэка — асинхронным, иначе узел заблокирует сам себя (тот же executor обслуживает ответ).

### MAVROS 1 → MAVROS 2
Имена топиков в основном те же (`/mavros/state`, `/mavros/local_position/pose`, `/mavros/setpoint_position/local`), но: QoS телеметрии — sensor data; некоторые сервисы и параметры переименованы; запуск — `ros2 launch mavros apm.launch fcu_url:=...` (или `px4.launch`). Для PX4 в ROS 2 вместо MAVROS обычно переходят на uXRCE-DDS (модуль ros2-px4), для ArduPilot — на AP_DDS там, где его функций хватает (модуль ros2-ardupilot).

{{diagram:ros1-migration|Что делать со старым проектом ROS 1: временный мост, перенос, MAVROS 2 или переписать по идеям.}}

## practice
### Шаг 1. Чтение проекта
Возьмите открытый ROS 1 дроновый проект (например, пример offboard из документации PX4 для ROS 1 / MAVROS или любой репозиторий с MAVROS 1). За 30 минут нарисуйте граф узлов, список зависимостей и где проект управляет аппаратом.

### Шаг 2. Эталонные данные
Если есть возможность — запустите проект в контейнере ROS 1 Noetic с SITL и запишите `rosbag` входов и выходов узла. Если нет — используйте bag из открытых источников или синтетические входы.

### Шаг 3. Перенос
Перенесите один узел (до ~200 строк): логику без ROS — в отдельный модуль с pytest-тестами (как `offboard_fsm.py`), узел — тонкая обёртка `rclpy`. Сконвертируйте bag в формат ROS 2 (пакет `rosbags`: `rosbags-convert`) и проверьте, что выходы перенесённого узла совпадают с эталонными.

### Шаг 4. Отчёт
Таблица: что заменено, сколько строк логики стало тестируемыми без ROS, какие различия в поведении найдены (обычно — QoS и время).

Лабораторная засчитывается, когда есть граф исходного проекта, перенесённый узел с тестами логики и сравнение выходов на одних и тех же данных.

## diagnostics
- **Симптом:** перенесённый узел «зависает» на вызове сервиса
  - Возможная причина: синхронный вызов в колбэке однопоточного executor-а.
  - Что сделать: call_async + обработка future, или отдельная группа колбэков.
- **Симптом:** узел не получает телеметрию MAVROS 2
  - Возможная причина: QoS (sensor data у издателя) или другое имя топика.
  - Что сделать: `ros2 topic info -v`, профиль подписки.
- **Симптом:** параметры «не применяются»
  - Возможная причина: в ROS 2 параметр нужно объявить (`declare_parameter`) и передать конкретному узлу.
  - Что сделать: объявление в конструкторе, YAML с именем узла в launch.
- **Симптом:** ros1_bridge не передаёт свой тип сообщения
  - Возможная причина: мост собран без этого типа или определения различаются.
  - Что сделать: собрать мост из исходников с обоими воркспейсами; лучше — переносить.

## references
- ROS 2 — Migration guide from ROS 1 | https://docs.ros.org/en/jazzy/How-To-Guides/Migrating-from-ROS1.html | primary | A
- ros1_bridge | https://github.com/ros2/ros1_bridge | primary | A
- rosbags (bag conversion, pure Python) | https://gitlab.com/ternaris/rosbags | primary | A
- MAVROS (ROS 2 branch) | https://github.com/mavlink/mavros | primary | A

## checklist
- Знаю соответствия понятий ROS 1 → ROS 2 и что меняется по существу
- Читаю ROS 1 проект через launch-файлы и рисую граф узлов
- Выбираю между мостом и переносом
- Заменяю цикл с rate.sleep таймером, синхронные сервисы — асинхронными
- Проверяю перенос на эталонных записанных данных
