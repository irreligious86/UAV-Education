---
id: ros2-from-ros1
title: "Из ROS 1 в ROS 2: читать старые проекты и переносить их"
level: L3
readingTime: 45 мин
firmware: ROS 2 Humble · Jazzy · Lyrical · ROS 1 Noetic (EOL) · PX4 · ArduPilot
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
ROS 1 Noetic закончил поддержку 31 мая 2025 года, но половина открытых дроновых проектов, статей и туториалов — на ROS 1: MAVROS 1, catkin-воркспейсы, launch в XML, `rospy`. Модуль учит быстро читать такой проект («что здесь главное и что от чего зависит»), знать соответствия понятий ROS 1 → ROS 2, решать, переносить или запускать рядом через мост, и переносить небольшой пакет. Модуль даёт статус дистрибутивов на ноябрь 2026 и как выбрать целевой, что заменило `roscore` (DDS discovery, домены, RMW), какие неявные свойства ROS 1 приходится явно задавать через QoS, как переносятся сборка (catkin → colcon) и launch-файлы. Лабораторная (выполнена без установленного ROS): ROS 1 bag с эталонным выходом старого узла → `rosbags-convert` → ROS 2 bag в MCAP → перенесённая логика с pytest и сравнение выходов; плюс проверка совместимости QoS на типовых случаях MAVROS 2.

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
| `rosbag` (`.bag`) | `ros2 bag` (MCAP по умолчанию с Iron, SQLite3 по выбору) | конвертеры есть (rosbags) |
| `tf` | `tf2` (был и в ROS 1) | почти без изменений |
| nodelets | компоненты (composable nodes) | несколько узлов в одном процессе без копирования |
| MAVROS 1 | MAVROS 2 (`mavros` в ROS 2) | те же плагины, другие имена сервисов/QoS |

### Статус версий на ноябрь 2026 и выбор цели
ROS 1 Noetic закончил поддержку 31 мая 2025 года, в тот же день, что и стандартная поддержка Ubuntu 20.04; последняя синхронизация пакетов была 29 мая 2025 года. После EOL исправлений в бинарных пакетах не будет. В декабре 2025 года Open Robotics объявила вывод из эксплуатации инфраструктуры ROS 1: сборочной фермы build.ros.org (после отключения она будет перенаправлять на build.ros2.org) и внутреннего repositories.ros.org; уже собранные пакеты остаются на packages.ros.org. Читать и запускать старый проект можно — в контейнере на Ubuntu 20.04, — но развивать его на ROS 1 значит копить долг.

| Дистрибутив | Выпуск | Конец поддержки | Ubuntu (Tier 1) | Статус на 26.11.2026 |
|---|---|---|---|---|
| Noetic (ROS 1) | май 2020 | 31.05.2025 | 20.04 | EOL |
| Foxy | 05.06.2020 | 20.06.2023 | 20.04 | EOL |
| Humble (LTS) | 23.05.2022 | май 2027 | 22.04 | поддерживается, полгода до EOL |
| Iron | 23.05.2023 | 04.12.2024 | 22.04 | EOL |
| Jazzy (LTS) | 23.05.2024 | май 2029 | 24.04 | поддерживается |
| Kilted | 23.05.2025 | декабрь 2026 (в REP 2000 — ноябрь 2026) | 24.04 | доживает последние недели |
| Lyrical (LTS) | 22.05.2026 | май 2031 | 26.04 (24.04 — Tier 3, только из исходников) | поддерживается, самый свежий LTS |

Как выбрать цель для переноса дронового проекта. Цель задаёт не самый новый дистрибутив, а самая «узкая» зависимость. AP_DDS в ArduPilot 4.7 официально поддерживает только Humble (`ros2-ardupilot`), документация PX4 (main) рекомендует Jazzy на Ubuntu 24.04, а документация релизов до v1.18 включительно — Humble на 22.04 (`ros2-px4`), MAVROS 2.17.0 выпущен для Humble, Jazzy, Kilted и Lyrical (rosdistro, ноябрь 2026). Отсюда правило курса: ArduPilot через AP_DDS — Humble, но с планом переезда до мая 2027; PX4 или MAVROS — Jazzy; Lyrical — для нового проекта, если все нужные пакеты уже выпущены под него (проверяется в `distribution.yaml` rosdistro). Kilted как цель переноса не берут: его поддержка кончается в декабре 2026.

{{diagram:ros2-distro-timeline|Окна поддержки по годам: в ноябре 2026 живы Humble (до мая 2027), Jazzy, Lyrical и уходящий Kilted; Noetic и мост к нему уже за чертой.}}

### Что заменило `roscore`: DDS, домены, RMW
В ROS 1 узел сначала регистрировался у мастера (`roscore`), узнавал у него, кто публикует нужный топик, и только потом открывал прямое TCP-соединение. Упал мастер — новые узлы не находят друг друга. В ROS 2 мастера нет: каждый процесс — участник DDS, который сам рассылает объявления о себе по UDP-multicast и слушает чужие (discovery). Плюсы — нет единой точки отказа; минусы — каждый узел в сети видит всех, и это надо ограничивать.

Ограничивают тремя способами. **Домен** `ROS_DOMAIN_ID`: участники разных доменов друг друга не видят; безопасный диапазон — 0–101 (документация ROS 2 называет безопасными на Linux ещё 215–232; остальные пересекаются с эфемерными портами). **Дальность discovery** `ROS_AUTOMATIC_DISCOVERY_RANGE` (появилась в Iron, то есть есть в Jazzy и новее, в Humble её нет; `LOCALHOST` — только своя машина, `SUBNET` — по умолчанию) заменила устаревшую `ROS_LOCALHOST_ONLY=1` из Humble. **Реализация middleware (RMW)**: по умолчанию `rmw_fastrtps_cpp` (eProsima Fast DDS) во всех поддерживаемых дистрибутивах, есть Cyclone DDS, Connext и, с Kilted, `rmw_zenoh_cpp` уровня Tier 1. Связь между разными DDS-реализациями (Fast DDS и Cyclone DDS часто связываются по общему протоколу RTPS) не гарантируется, а `rmw_zenoh_cpp` с DDS-RMW не общается вовсе, поэтому `RMW_IMPLEMENTATION`, домен и дистрибутив должны совпадать на борту и на ноутбуке. В ROS 1 этих настроек не было вовсе, поэтому в перенесённом проекте их надо явно прописать в launch или в окружении сервиса.

### QoS: что в ROS 1 было неявным
ROS 1 почти всегда передавал по TCPROS — по сути, «надёжно», с очередью `queue_size`, а «защёлкнутый» (`latch=True`) издатель отдавал последнее сообщение опоздавшему подписчику. В ROS 2 эти свойства стали политиками QoS, и у издателя и подписчика они задаются отдельно. Соединение возникает, только если подписчик просит не больше, чем издатель предлагает (модель «request vs offered»).

| Политика | Издатель | Подписчик | Связь |
|---|---|---|---|
| Reliability | best effort | best effort | да |
| | best effort | reliable | **нет** |
| | reliable | best effort / reliable | да |
| Durability | volatile | transient local | **нет** |
| | transient local | volatile | да, только новые сообщения |
| | transient local | transient local | да, новые и последнее сохранённое («latched») |

Профиль по умолчанию — keep last 10, reliable, volatile; профиль sensor data — keep last 5, best effort, volatile (`rmw/qos_profiles.h`). Аналог ROS 1: `queue_size` ≈ depth, TCPROS ≈ reliable, `latch=True` ≈ transient local **с обеих сторон**. Главная ловушка переноса дроновых узлов: MAVROS 2 публикует телеметрию (`~/pose`, скорости) с `SensorDataQoS`, то есть best effort, а перенесённый узел подписывается с профилем по умолчанию (reliable) — соединения нет, ошибки нет, данных нет. `/mavros/state` MAVROS 2 публикует с transient local (издатель создаётся в `plugins/sys_status.cpp` с профилем `StateQoS()` из `mavros/qos.hpp`), поэтому на него подписка по умолчанию работает. Проверка — `ros2 topic info -v <топик>`: там видны профили всех издателей и подписчиков.

{{lesson:ros2-basics|Узлы, топики, QoS и discovery в ROS 2 с нуля — основа, на которую ложится перенос.}}

### Сборка и launch: catkin → colcon, XML → Python
**Сборка.** catkin заменён на ament (система сборки пакета) и colcon (инструмент сборки воркспейса). Пакет на Python теперь — обычный setuptools-пакет: в `package.xml` (формат 3; формат 2 тоже принимается) `<build_type>ament_python</build_type>`, узлы объявляются как `console_scripts` в `setup.py`; пакет на C++ — `ament_cmake`. Команды: `colcon build --symlink-install` вместо `catkin_make` (с `--symlink-install` правки Python-кода не требуют пересборки), `colcon build --packages-select <pkg>` для одного пакета, `source install/setup.bash` вместо `devel/setup.bash`, `colcon test` и `colcon test-result --verbose` для тестов. Каталога `devel/` больше нет: только `build/`, `install/`, `log/`.

**Launch.** ROS 2 читает launch-файлы на Python, XML и YAML, но XML ROS 1 не совместим один в один (руководство по миграции launch-файлов): атрибут `type` стал `exec`, `ns` — `namespace`, `required="true"` — `on_exit="shutdown"`, `$(find pkg)` — `$(find-pkg-share pkg)`, `<rosparam>` заменён атрибутом `from` у `<param>`, глобальных параметров нет — каждый параметр принадлежит узлу. Минимальный перенос — XML с этими заменами; Python-launch нужен, когда появляется логика: условия, циклы по аппаратам, вычисляемые параметры. Пример Python-launch для перенесённого узла: `Node(package="descent_guard", executable="guard", name="guard", parameters=[{"k": 0.5}], remappings=[("pose", "/mavros/local_position/pose")])` внутри `LaunchDescription([...])`.

### Как читать ROS 1 проект за 30 минут
1. **Корень**: `package.xml`/`CMakeLists.txt` — зависимости (что за датчики, MAVROS ли, OpenCV ли).
2. **Launch-файлы** (`launch/*.launch`) — что запускается, с какими параметрами и remap-ами. Это «схема системы».
3. **Узлы** (`scripts/*.py`, `src/*.cpp`): найдите `init_node`, `Subscriber`, `Publisher`, `Service`, `Timer`/`Rate`. Нарисуйте граф: что слушает, что публикует.
4. **Параметры** (`config/*.yaml`, `rospy.get_param`) — что настраивается.
5. **Сообщения** (`msg/`, `srv/`) — свои типы.
6. **MAVROS-специфика**: `/mavros/setpoint_*`, `/mavros/set_mode`, `/mavros/cmd/arming` — где проект управляет аппаратом и в какой системе координат.

Итог — граф узлов (как в ros2-basics) и список внешних зависимостей. С ним понятно, сколько стоит перенос.

### Перенос или мост
- **ros1_bridge** — двунаправленный мост топиков/сервисов между ROS 1 и ROS 2 при запущенных обоих. Мост на C++ знает только типы, с которыми собран: стандартные интерфейсы он знает и при обычной сборке из исходников, свои — только если собран с обоими воркспейсами. Бинарный пакет был до Foxy/Galactic включительно. На ноябрь 2026 ни в одном дистрибутиве ROS 2 нет бинарного пакета `ros1_bridge` (rosdistro: в Humble есть запись о release-репозитории без версии, в Jazzy, Kilted, Lyrical — без релиза), а README моста прямо пишет: на Ubuntu 24.04 ROS 1 нет, значит, моста нет; полная поддержка — только Ubuntu 20.04 (Noetic), на 22.04 — сборка из исходников без официальной поддержки ROS 1. Практически мост — временный костыль в контейнере на 20.04, а не путь.
- **Перенос** — правильный путь для живого кода. Порядок: сообщения → библиотечный код без ROS (вынести!) → узлы → launch → тесты на записанных данных.
- **Запуск ROS 1 в контейнере** — для «посмотреть, как это работало» и для записи эталонных данных до переноса.

### Данные: bag-файлы и эталон
Записанные в ROS 1 bag-файлы — главный актив переноса: на них проверяют, что новый узел ведёт себя как старый. Чистый Python-пакет `rosbags` (0.11.11 от 27.11.2026; лабораторная ниже снята на 0.11.10, на 0.11.11 вывод тот же) читает и пишет ROS 1 bag и ROS 2 bag без установленного ROS, а `rosbags-convert --src old.bag --dst new_dir --dst-storage mcap` переводит один формат в другой. При конвертации меняются сами типы: в ROS 2 у `std_msgs/Header` нет поля `seq`, время — `builtin_interfaces/Time` с полями `sec` и `nanosec`, а не `rospy.Time` с `secs`/`nsecs`; конвертер отбрасывает `seq` сам. Свои типы сообщений (`msg/`) нужно зарегистрировать в typestore `rosbags`, иначе конвертер их не разберёт. Сравнивают выходы по времени записи: таймер в ROS 2 должен тикать на той же сетке, что `rospy.Rate` в старом узле, иначе число выходов и их моменты не совпадут — это и есть «различия во времени», которые лабораторная показывает на числах.

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

{{diagram:ros2-sync-call-deadlock|Синхронный cli.call() в колбэке занимает единственный поток executor: ответ некому доставить, тики таймера пропадают; call_async() возвращается сразу, и уставки идут каждые 50 мс.}}

### MAVROS 1 → MAVROS 2
Имена топиков в основном те же (`/mavros/state`, `/mavros/local_position/pose`, `/mavros/setpoint_position/local`), но: QoS телеметрии — sensor data; некоторые сервисы и параметры переименованы; запуск — `ros2 launch mavros apm.launch fcu_url:=...` (или `px4.launch`). Для PX4 в ROS 2 вместо MAVROS обычно переходят на uXRCE-DDS (модуль ros2-px4), для ArduPilot — на AP_DDS там, где его функций хватает (модуль ros2-ardupilot).

{{diagram:ros1-migration|Что делать со старым проектом ROS 1: временный мост, перенос, MAVROS 2 или переписать по идеям.}}

### Место в системе

- **Получает:** старый проект — launch-файлы, узлы, обращения к `/mavros/*`; понятия QoS, таймеров и параметров узла (`ros2-basics`); эталонные данные, записанные до переноса.
- **Отдаёт:** граф узлов и список зависимостей — решению «мост или перенос»; перенесённый узел — в архитектуру приложения (`ros2-app-arch`); выбор моста к автопилоту: uXRCE-DDS (`ros2-px4`), AP_DDS (`ros2-ardupilot`) или MAVROS 2 (`mav-sdk`).
- **Если ошибиться здесь:** оставил синхронный вызов сервиса внутри колбэка → узел блокирует сам себя → уставки перестают идти → автопилот выходит из Offboard или останавливается по таймауту (`ros2-px4`). Перенёс подписки MAVROS без QoS sensor data → телеметрия не приходит (`ros2-basics`).

## practice
### Шаг 1. Чтение проекта
Возьмите открытый ROS 1 дроновый проект (например, пример offboard из документации PX4 для ROS 1 / MAVROS или любой репозиторий с MAVROS 1). За 30 минут нарисуйте граф узлов, список зависимостей и где проект управляет аппаратом.

### Шаг 2. Эталонные данные
Если есть возможность — запустите проект в контейнере ROS 1 Noetic с SITL и запишите `rosbag` входов и выходов узла. Если нет — используйте bag из открытых источников или синтетические входы.

### Шаг 3. Перенос
Перенесите один узел (до ~200 строк): логику без ROS — в отдельный модуль с pytest-тестами (как `offboard_fsm.py` из модуля `ros2-px4`), узел — тонкая обёртка `rclpy`. Сконвертируйте bag в формат ROS 2 (пакет `rosbags`: `rosbags-convert`) и проверьте, что выходы перенесённого узла совпадают с эталонными.

### Шаг 4. Итоговая запись
Таблица: что заменено, сколько строк логики стало тестируемыми без ROS, какие различия в поведении найдены (обычно — QoS и время).

### Шаг 5. Разобранный перенос на синтетическом полёте (выполнено, без ROS)
Шаги 1–4 требуют настоящего проекта и ROS; этот шаг проходится на любой машине с Python 3 и показывает весь цикл на маленьком узле. Узел «защита снижения» подписан на позу MAVROS и 20 раз в секунду публикует вертикальную скорость: не быстрее 1.5 м/с, ниже 2 м — не быстрее 0.3 м/с, на земле — 0. Старый узел на rospy (для чтения, не запускался):

```python
# ROS 1 (rospy) — the node being ported; shown for reading, not run (no ROS 1 here)
import rospy
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Float32
from descent_guard import descent_cmd

z = None
def on_pose(msg):
    global z
    z = msg.pose.position.z

rospy.init_node("descent_guard")
rospy.Subscriber("/mavros/local_position/pose", PoseStamped, on_pose)
pub = rospy.Publisher("/descent_guard/vz", Float32, queue_size=10)
rate = rospy.Rate(20)
while not rospy.is_shutdown():
    if z is not None:
        pub.publish(Float32(descent_cmd(z)))
    rate.sleep()
```

Логика без ROS вынесена в модуль и покрыта тестами — она переносится без единой правки:

```python
"""ROS-free logic of the ported node: vertical speed command for a guarded descent (ENU, up positive)."""
def descent_cmd(z, z_land=0.0, k=0.5, v_max=1.5, slow_alt=2.0, v_slow=0.3):
    """z — altitude above the landing point, m. Returns vz, m/s (negative = down)."""
    err = z - z_land
    if err <= 0.05:
        return 0.0
    limit = v_slow if err < slow_alt else v_max
    return -min(k * err, limit)
```

```python
from descent_guard import descent_cmd
def test_high_altitude_is_limited():   assert descent_cmd(10.0) == -1.5
def test_proportional_zone():           assert descent_cmd(2.4) == -1.2
def test_slow_zone_below_2m():          assert descent_cmd(1.0) == -0.3
def test_stop_on_ground():              assert descent_cmd(0.03) == 0.0
```

Обёртка на rclpy (синтаксис проверен `py_compile`; в окружении автора ROS 2 нет, поэтому не запускалась). Обрати внимание на QoS подписки и таймер вместо цикла:

```python
# ROS 2 (rclpy) — thin wrapper around the same logic; syntax checked, not run (no ROS 2 here)
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Float32
from descent_guard import descent_cmd


class Guard(Node):
    def __init__(self):
        super().__init__("descent_guard")
        self.z = None
        # MAVROS 2 publishes pose with SensorDataQoS (best effort): a default (reliable) subscription gets nothing
        self.create_subscription(PoseStamped, "/mavros/local_position/pose", self.on_pose, qos_profile_sensor_data)
        self.pub = self.create_publisher(Float32, "/descent_guard/vz", 10)
        self.create_timer(0.05, self.tick)          # replaces rospy.Rate(20) + while loop

    def on_pose(self, msg):
        self.z = msg.pose.position.z

    def tick(self):
        if self.z is not None:
            self.pub.publish(Float32(data=descent_cmd(self.z)))


def main():
    rclpy.init()
    rclpy.spin(Guard())


if __name__ == "__main__":
    main()
```

Проверка поведения без ROS: скрипт пишет ROS 1 bag (поза 30 Гц, 10 с снижения с 8 м со скоростью 1 м/с, плюс эталонный выход старого узла на сетке 20 Гц), конвертирует его `rosbags-convert` в ROS 2 bag в MCAP с типами Jazzy, читает обратно и прогоняет логику двумя способами: как таймер на той же сетке и «наивно» — публикацией прямо в колбэке позы. Нужен только `pip install rosbags pytest`.

```python
"""ros2-from-ros1 lab without ROS: ROS 1 bag (reference) -> rosbags-convert -> ROS 2 bag -> ported logic -> compare."""
import subprocess, sys, shutil
from pathlib import Path
from rosbags.rosbag1 import Writer as W1
from rosbags.highlevel import AnyReader
from rosbags.typesys import Stores, get_typestore
from descent_guard import descent_cmd
work = Path(sys.argv[1]); shutil.rmtree(work, ignore_errors=True); work.mkdir()
ts1 = get_typestore(Stores.ROS1_NOETIC)
Pose, Stamped, Hdr, Time = (ts1.types[n] for n in ("geometry_msgs/msg/Pose", "geometry_msgs/msg/PoseStamped",
                                                    "std_msgs/msg/Header", "builtin_interfaces/msg/Time"))
P, Q, F32 = ts1.types["geometry_msgs/msg/Point"], ts1.types["geometry_msgs/msg/Quaternion"], ts1.types["std_msgs/msg/Float32"]
NS = 1_000_000_000; T0 = 100 * NS
def alt(t): return max(0.0, 8.0 - 1.0 * t)          # descent from 8 m at 1 m/s (synthetic flight)
# 1) ROS 1 bag: pose at 30 Hz + output of the OLD node (rospy.Rate(20) loop, latest pose) as the reference
bag1 = work / "flight_ros1.bag"
with W1(bag1) as w:
    cp = w.add_connection("/mavros/local_position/pose", Stamped.__msgtype__, typestore=ts1)
    cc = w.add_connection("/descent_guard/vz", F32.__msgtype__, typestore=ts1)
    poses = [(T0 + i * NS // 30, alt(i / 30)) for i in range(300)]          # 10 s
    for t, z in poses:
        m = Stamped(Hdr(seq=0, stamp=Time(sec=t // NS, nanosec=t % NS), frame_id="map"),
                    Pose(P(x=0.0, y=0.0, z=z), Q(x=0.0, y=0.0, z=0.0, w=1.0)))
        w.write(cp, t, ts1.serialize_ros1(m, Stamped.__msgtype__))
    latest = None; j = 0
    for n in range(200):                                                     # while not shutdown: ... rate.sleep()
        tick = T0 + n * NS // 20
        while j < len(poses) and poses[j][0] <= tick: latest = poses[j][1]; j += 1
        if latest is not None:
            w.write(cc, tick, ts1.serialize_ros1(F32(data=descent_cmd(latest)), F32.__msgtype__))
# 2) convert to ROS 2 (MCAP, Jazzy message definitions)
bag2 = work / "flight_ros2"
r = subprocess.run(["rosbags-convert", "--src", str(bag1), "--dst", str(bag2), "--dst-storage", "mcap",
                    "--dst-typestore", "ros2_jazzy"], capture_output=True, text=True)
print("rosbags-convert exit", r.returncode, "->", sorted(p.name for p in bag2.iterdir()))
# 3) read the ROS 2 bag, run the ported node two ways
ts2 = get_typestore(Stores.ROS2_JAZZY)
pose_in, ref = [], []
with AnyReader([bag2], default_typestore=ts2) as rd:
    for c in rd.connections: print(f"  {c.topic:30s} {c.msgtype:28s} {c.msgcount} msgs")
    for c, t, raw in rd.messages():
        msg = rd.deserialize(raw, c.msgtype)
        (pose_in if c.topic.endswith("pose") else ref).append((t, msg.pose.position.z if c.topic.endswith("pose") else msg.data))
def timer_port():                      # node.create_timer(0.05, tick): latest pose, same 20 Hz grid
    out, latest, j = [], None, 0
    for n in range(200):
        tick = T0 + n * NS // 20
        while j < len(pose_in) and pose_in[j][0] <= tick: latest = pose_in[j][1]; j += 1
        if latest is not None: out.append((tick, descent_cmd(latest)))
    return out
def callback_port():                   # naive port: publish inside the pose callback (30 Hz)
    return [(t, descent_cmd(z)) for t, z in pose_in]
import struct
f32 = lambda v: struct.unpack("f", struct.pack("f", v))[0]     # Float32 on the wire
for name, out in (("timer port", timer_port()), ("callback port", callback_port())):
    same = len(out) == len(ref) and all(abs(f32(a[1]) - b[1]) < 1e-6 and a[0] == b[0] for a, b in zip(out, ref))
    print(f"{name:13s}: {len(out)} outputs vs {len(ref)} reference -> {'MATCH' if same else 'DIFFERENT'}")
```

Последний скрипт — правила совместимости QoS из документации ROS 2 на типовых случаях переноса:

```python
"""Request-vs-offered QoS rules from the ROS 2 docs (reliability, durability) applied to typical migration cases."""
RANK_REL = {"best_effort": 0, "reliable": 1}
RANK_DUR = {"volatile": 0, "transient_local": 1}
def compatible(pub, sub):
    """pub/sub: (reliability, durability). A subscription may request no more than the publisher offers."""
    return RANK_REL[pub[0]] >= RANK_REL[sub[0]] and RANK_DUR[pub[1]] >= RANK_DUR[sub[1]]
DEFAULT, SENSOR = ("reliable", "volatile"), ("best_effort", "volatile")
LATCHED = ("reliable", "transient_local")
cases = [
    ("MAVROS 2 telemetry (sensor data) -> port with default QoS", SENSOR, DEFAULT),
    ("MAVROS 2 telemetry (sensor data) -> port with sensor data", SENSOR, SENSOR),
    ("default publisher -> sensor-data subscriber", DEFAULT, SENSOR),
    ("ROS 1 latched map, ported as default -> late subscriber wants transient_local", DEFAULT, LATCHED),
    ("transient_local publisher -> default subscriber (no old samples)", LATCHED, DEFAULT),
]
for name, pub, sub in cases:
    print(f"{'OK ' if compatible(pub, sub) else 'NO '} {name}")
```

Вывод в окружении автора (Python 3.13, rosbags 0.11.10, pytest 9.2.0):

```text
$ python -m pytest -q test_descent_guard.py
4 passed in 0.01s
$ python migrate_lab.py ./work
rosbags-convert exit 0 -> ['flight_ros2.mcap', 'metadata.yaml']
  /mavros/local_position/pose    geometry_msgs/msg/PoseStamped 300 msgs
  /descent_guard/vz              std_msgs/msg/Float32         200 msgs
timer port   : 200 outputs vs 200 reference -> MATCH
callback port: 300 outputs vs 200 reference -> DIFFERENT
$ python qos_check.py
NO  MAVROS 2 telemetry (sensor data) -> port with default QoS
OK  MAVROS 2 telemetry (sensor data) -> port with sensor data
OK  default publisher -> sensor-data subscriber
NO  ROS 1 latched map, ported as default -> late subscriber wants transient_local
OK  transient_local publisher -> default subscriber (no old samples)
```

Что здесь видно. Логика прошла тесты и дала на сконвертированном bag те же 200 значений в те же моменты, что эталон, — когда таймер тикает на сетке старого `rospy.Rate(20)`. «Наивный» перенос в колбэк дал 300 выходов: частота выхода стала частотой входа (30 Гц), и сравнение с эталоном не проходит — это пример «различия во времени» без единой ошибки в логике. Подписка с профилем по умолчанию на телеметрию MAVROS 2 (best effort) несовместима; на опоздавший «защёлкнутый» топик подписчик с transient local получит что-то, только если издатель тоже transient local.

Самопроверка: лабораторная выполнена, когда **(шаг 5, без ROS)** 4 теста проходят, `rosbags-convert` завершился с кодом 0 и создал `flight_ros2.mcap`, в ROS 2 bag 300 сообщений позы и 200 эталонных, «timer port» даёт 200 выходов и MATCH, «callback port» — 300 и DIFFERENT, а `qos_check.py` печатает NO ровно для двух случаев: sensor data → default и default → transient local; **(свой проект, шаги 1–4)** нарисован граф исходного проекта (узлы, топики, зависимости и место, где проект управляет аппаратом), перенесённый узел — тонкая обёртка `rclpy` вокруг модуля логики без ROS, тесты логики проходят через pytest, выходы перенесённого узла на сконвертированном bag совпадают с эталонными выходами из шага 2, а в таблице шага 4 каждое найденное различие в поведении отнесено к причине.

**Эталон для самопроверки.** Верный результат: на одних и тех же входах старый и новый узел дают одинаковые выходы, а различия объясняются QoS и временем. Типичные неверные: (1) перенесённый узел «зависает» на вызове сервиса — синхронный вызов внутри колбэка, нужен `call_async`; (2) узел не получает телеметрию или параметры «не применяются» — подписка не совместима с QoS издателя либо параметр не объявлен через `declare_parameter`; (3) в узле остался цикл `while` с `rate.sleep()` — в ROS 2 его заменяют таймер и колбэки; (4) в шаге 5 у тебя «timer port» дал 199 или 201 выход — сетка таймера сдвинута относительно эталона (старт не с T0 или шаг не 50 мс); (5) `rosbags-convert` падает на своём типе — тип не зарегистрирован в typestore.

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
- **Симптом:** узлы на борту и на ноутбуке не видят друг друга, хотя сеть есть
  - Возможная причина: разные `ROS_DOMAIN_ID`, `RMW_IMPLEMENTATION` или дистрибутив; на одной из машин `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`; multicast режется Wi-Fi-точкой.
  - Что сделать: `printenv | grep ROS` и `ros2 doctor --report` на обеих машинах; выровнять домен и RMW.
- **Симптом:** после конвертации bag сравнение с эталоном «почти совпадает»: другое число выходов
  - Возможная причина: в перенесённом узле публикация в колбэке входа вместо таймера на сетке старого `rospy.Rate`.
  - Что сделать: таймер с тем же периодом; сравнивать по времени записи, как в шаге 5.
- **Симптом:** `apt` не находит `ros-<distro>-ros1-bridge`
  - Возможная причина: бинарного пакета нет ни в одном поддерживаемом дистрибутиве ROS 2 (rosdistro, ноябрь 2026), а на Ubuntu 24.04 нет ROS 1.
  - Что сделать: контейнер Ubuntu 20.04 с Noetic и сборкой моста из исходников — только как временная мера; лучше переносить.
- **Симптом:** ros1_bridge не передаёт свой тип сообщения
  - Возможная причина: мост собран без этого типа или определения различаются.
  - Что сделать: собрать мост из исходников с обоими воркспейсами; лучше — переносить.

## references
- ROS 2 — Migration guide from ROS 1 | https://docs.ros.org/en/jazzy/How-To-Guides/Migrating-from-ROS1.html | primary | A
- ros1_bridge | https://github.com/ros2/ros1_bridge | primary | A
- rosbags (bag conversion, pure Python) | https://gitlab.com/ternaris/rosbags | primary | A
- MAVROS (ROS 2 branch) | https://github.com/mavlink/mavros | primary | A
- ROS 2 Documentation, исходник — Distributions (даты выпуска и EOL, ноябрь 2026) | https://github.com/ros2/ros2_documentation/blob/rolling/source/Releases.rst | primary | A
- REP 2000 — ROS 2 Releases and Target Platforms | https://github.com/ros-infrastructure/rep/blob/master/rep-2000.rst | primary | A
- ROS Noetic End-of-Life: May 31, 2025 — Open Robotics Discourse | https://discourse.openrobotics.org/t/ros-noetic-end-of-life-may-31-2025/43160 | primary | A
- ROS 2 Documentation (Lyrical) — Migrating launch files from ROS 1 | https://github.com/ros2/ros2_documentation/blob/lyrical/source/Migration-and-Upgrades/Migrating-from-ROS1/Migrating-Launch-Files.rst | primary | A
- ROS 2 Documentation — About Quality of Service settings (совместимость политик) | https://github.com/ros2/ros2_documentation/blob/rolling/source/ROS-Framework/interfaces/topics/About-Quality-of-Service-Settings.rst | primary | A
- ros2/rmw — qos_profiles.h (профили default и sensor data) | https://github.com/ros2/rmw/blob/jazzy/rmw/include/rmw/qos_profiles.h | primary | A
- rosdistro — distribution.yaml (mavros 2.17.0, ros1_bridge без релиза в Humble/Jazzy/Kilted/Lyrical) | https://github.com/ros/rosdistro/blob/master/jazzy/distribution.yaml | primary | A

## checklist
- Знаю соответствия понятий ROS 1 → ROS 2 и что меняется по существу
- Выбираю целевой дистрибутив по самой узкой зависимости (AP_DDS — Humble, PX4 — Jazzy) и знаю даты EOL
- Прописываю домен, RMW и QoS подписок явно; подписку на телеметрию MAVROS 2 делаю с sensor data
- Читаю ROS 1 проект через launch-файлы и рисую граф узлов
- Выбираю между мостом и переносом
- Заменяю цикл с rate.sleep таймером, синхронные сервисы — асинхронными
- Проверяю перенос на эталонных записанных данных
