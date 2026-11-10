---
id: ros2-from-ros1
title: "З ROS 1 у ROS 2: читати старі проєкти й переносити їх"
level: L3
readingTime: 30 хв
firmware: PX4 · ArduPilot
status: published
added: 2026-11-08
tags:
  - ROS 1
  - ROS 2
  - міграція
  - MAVROS
  - catkin
related:
  - ros2-basics
  - ros2-ardupilot
next:
  - ros2-app-arch
source: content/ros2/ros2-from-ros1.md
source_hash: a1ec2f4af0ee
---

## summary
Підтримка ROS 1 Noetic закінчилася в травні 2025 року, але половина відкритих дронових проєктів, статей і туторіалів — на ROS 1: MAVROS 1, catkin-воркспейси, launch у XML, `rospy`. Модуль навчає швидко читати такий проєкт («що тут головне і що від чого залежить»), знати відповідності понять ROS 1 → ROS 2, вирішувати, переносити чи запускати поруч через міст, і переносити невеликий пакет. Лабораторна: перенесення вузла ROS 1 на ROS 2 зі збереженням поведінки, перевірене на записаних даних.

## theory
### Чим ROS 2 відрізняється по суті
| ROS 1 | ROS 2 | Що це змінює |
|---|---|---|
| `roscore` (master) — центральний вузол імен | немає master, DDS discovery | немає єдиної точки відмови; потрібні домени/обмеження discovery |
| TCPROS/UDPROS | DDS з QoS | треба думати про QoS (модуль ros2-basics) |
| `rospy`, `roscpp` | `rclpy`, `rclcpp` | API інший, але ідеї ті самі |
| catkin, `catkin_make`/`catkin build` | ament, `colcon build` | інша збірка, `package.xml` format 3 |
| launch XML (`.launch`) | launch Python/XML/YAML (`.launch.py`) | логіка в launch-файлі |
| параметри в глобальному сервері | параметри в кожного вузла | `rosparam` → `ros2 param` до конкретного вузла |
| `rosbag` (`.bag`) | `ros2 bag` (SQLite3/MCAP) | конвертери є (rosbags) |
| `tf` | `tf2` (був і в ROS 1) | майже без змін |
| nodelets | компоненти (composable nodes) | кілька вузлів в одному процесі без копіювання |
| MAVROS 1 | MAVROS 2 (`mavros` у ROS 2) | ті самі плагіни, інші імена сервісів/QoS |

### Як прочитати ROS 1 проєкт за 30 хвилин
1. **Корінь**: `package.xml`/`CMakeLists.txt` — залежності (які датчики, чи MAVROS, чи OpenCV).
2. **Launch-файли** (`launch/*.launch`) — що запускається, з якими параметрами й remap-ами. Це «схема системи».
3. **Вузли** (`scripts/*.py`, `src/*.cpp`): знайдіть `init_node`, `Subscriber`, `Publisher`, `Service`, `Timer`/`Rate`. Намалюйте граф: що слухає, що публікує.
4. **Параметри** (`config/*.yaml`, `rospy.get_param`) — що налаштовується.
5. **Повідомлення** (`msg/`, `srv/`) — власні типи.
6. **MAVROS-специфіка**: `/mavros/setpoint_*`, `/mavros/set_mode`, `/mavros/cmd/arming` — де проєкт керує апаратом і в якій системі координат.

Підсумок — граф вузлів (як у ros2-basics) і список зовнішніх залежностей. З ним зрозуміло, скільки коштує перенесення.

### Перенесення чи міст
- **ros1_bridge** — двонапрямлений міст топіків/сервісів між ROS 1 і ROS 2, коли запущено обидва. Потребує сумісної збірки (однакові типи повідомлень з обох боків), історично — Noetic + Foxy/Humble з вихідних кодів. Після закінчення підтримки Noetic це тимчасове рішення.
- **Перенесення** — правильний шлях для живого коду. Порядок: повідомлення → бібліотечний код без ROS (винести!) → вузли → launch → тести на записаних даних.
- **Запуск ROS 1 у контейнері** — щоб «подивитися, як це працювало», і для запису еталонних даних до перенесення.

### Типові заміни в коді (Python)
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

Головна зміна мислення — **цикл `while` з `rate.sleep()` замінюється таймером і колбеками**, а синхронний виклик сервісу всередині колбека — асинхронним, інакше вузол заблокує сам себе (той самий executor обслуговує відповідь).

### MAVROS 1 → MAVROS 2
Імена топіків здебільшого ті самі (`/mavros/state`, `/mavros/local_position/pose`, `/mavros/setpoint_position/local`), але: QoS телеметрії — sensor data; деякі сервіси й параметри перейменовано; запуск — `ros2 launch mavros apm.launch fcu_url:=...` (або `px4.launch`). Для PX4 у ROS 2 замість MAVROS зазвичай переходять на uXRCE-DDS (модуль ros2-px4), для ArduPilot — на AP_DDS там, де його функцій вистачає (модуль ros2-ardupilot).

{{diagram:ros1-migration|Що робити зі старим проєктом ROS 1: тимчасовий міст, перенесення, MAVROS 2 або переписати за ідеями.}}

## practice
### Крок 1. Читання проєкту
Візьміть відкритий дроновий проєкт на ROS 1 (наприклад, приклад offboard із документації PX4 для ROS 1 / MAVROS або будь-який репозиторій з MAVROS 1). За 30 хвилин намалюйте граф вузлів, список залежностей і де проєкт керує апаратом.

### Крок 2. Еталонні дані
Якщо є можливість — запустіть проєкт у контейнері ROS 1 Noetic із SITL і запишіть `rosbag` входів і виходів вузла. Якщо ні — використайте bag з відкритих джерел або синтетичні входи.

### Крок 3. Перенесення
Перенесіть один вузол (до ~200 рядків): логіку без ROS — в окремий модуль із pytest-тестами (як `offboard_fsm.py`), вузол — тонка обгортка `rclpy`. Сконвертуйте bag у формат ROS 2 (пакет `rosbags`: `rosbags-convert`) і перевірте, що виходи перенесеного вузла збігаються з еталонними.

### Крок 4. Звіт
Таблиця: що замінено, скільки рядків логіки стало придатними до тестування без ROS, які відмінності в поведінці знайдено (зазвичай — QoS і час).

Лабораторну зараховано, коли є граф вихідного проєкту, перенесений вузол із тестами логіки й порівняння виходів на тих самих даних.

## diagnostics
- **Симптом:** перенесений вузол «зависає» на виклику сервісу
  - Можлива причина: синхронний виклик у колбеку однопотокового executor-а.
  - Що зробити: call_async + обробка future, або окрема група колбеків.
- **Симптом:** вузол не отримує телеметрію MAVROS 2
  - Можлива причина: QoS (sensor data у видавця) або інше ім'я топіка.
  - Що зробити: `ros2 topic info -v`, профіль підписки.
- **Симптом:** параметри «не застосовуються»
  - Можлива причина: у ROS 2 параметр треба оголосити (`declare_parameter`) і передати конкретному вузлу.
  - Що зробити: оголошення в конструкторі, YAML з іменем вузла в launch.
- **Симптом:** ros1_bridge не передає власний тип повідомлення
  - Можлива причина: міст зібрано без цього типу або визначення відрізняються.
  - Що зробити: зібрати міст із вихідних кодів з обома воркспейсами; краще — переносити.

## references
- ROS 2 — Migration guide from ROS 1 | https://docs.ros.org/en/jazzy/How-To-Guides/Migrating-from-ROS1.html | primary | A
- ros1_bridge | https://github.com/ros2/ros1_bridge | primary | A
- rosbags (bag conversion, pure Python) | https://gitlab.com/ternaris/rosbags | primary | A
- MAVROS (ROS 2 branch) | https://github.com/mavlink/mavros | primary | A

## checklist
- Знаю відповідності понять ROS 1 → ROS 2 і що змінюється по суті
- Читаю ROS 1 проєкт через launch-файли й малюю граф вузлів
- Вибираю між мостом і перенесенням
- Замінюю цикл із rate.sleep таймером, синхронні сервіси — асинхронними
- Перевіряю перенесення на еталонних записаних даних
