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
Підтримка ROS 1 Noetic скінчилася в травні 2025 року, але половина відкритих дронових проєктів, статей і туторіалів — на ROS 1: MAVROS 1, catkin-воркспейси, launch у XML, `rospy`. Модуль учить шпарко читати такий проєкт («що тут головне і що від чого залежить»), знати відповідності понять ROS 1 → ROS 2, вирішувати, ци переносити, ци запускати поруч через міст, і переносити невеликий пакет. Лабораторна: перенесення вузла ROS 1 на ROS 2 так, аби поведінка лишилася та сама, перевірене на записаних даних.

## theory
### Чим ROS 2 відрізняється по суті
| ROS 1 | ROS 2 | Що це змінює |
|---|---|---|
| `roscore` (master) — центральний вузол імен | нема master, DDS discovery | нема єдиної точки відмови; треба домени/обмеження discovery |
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
1. **Корінь**: `package.xml`/`CMakeLists.txt` — залежності (які датчики, ци є MAVROS, ци OpenCV).
2. **Launch-файли** (`launch/*.launch`) — що запускається, з якими параметрами й remap-ами. То «схема системи».
3. **Вузли** (`scripts/*.py`, `src/*.cpp`): знайди `init_node`, `Subscriber`, `Publisher`, `Service`, `Timer`/`Rate`. Намалюй граф: що слухає, що публікує.
4. **Параметри** (`config/*.yaml`, `rospy.get_param`) — що налаштовується.
5. **Повідомлення** (`msg/`, `srv/`) — власні типи.
6. **MAVROS-специфіка**: `/mavros/setpoint_*`, `/mavros/set_mode`, `/mavros/cmd/arming` — де проєкт керує апаратом і в якій системі координат.

Підсумок — граф вузлів (як у ros2-basics) і список зовнішніх залежностей. З ним зразу видно, кілько коштуватиме перенесення.

### Перенесення ци міст
- **ros1_bridge** — двонапрямлений міст топіків/сервісів між ROS 1 і ROS 2, коли запущено обидва. Потребує сумісної збірки (однакові типи повідомлень з обох боків), історично — Noetic + Foxy/Humble з вихідних кодів. Після того, як скінчилася підтримка Noetic, то рішення тимчасове.
- **Перенесення** — правильний шлях для живого коду. Порядок: повідомлення → бібліотечний код без ROS (винести!) → вузли → launch → тести на записаних даних.
- **Запуск ROS 1 у контейнері** — аби «глянути, як то працювало», і для запису еталонних даних до перенесення.

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

Головна зміна в голові — **цикл `while` з `rate.sleep()` заміняється таймером і колбеками**, а синхронний виклик сервісу всередині колбека — асинхронним, бо інакше вузол сам себе заблокує (той самий executor обслуговує відповідь).

{{diagram:ros2-distro-timeline|Окна поддержки по годам: в ноябре 2026 живы Humble (до мая 2027), Jazzy, Lyrical и уходящий Kilted; Noetic и мост к нему уже за чертой.}}

{{diagram:ros2-sync-call-deadlock|Синхронный cli.call() в колбэке занимает единственный поток executor: ответ некому доставить, тики таймера пропадают; call_async() возвращается сразу, и уставки идут каждые 50 мс.}}

### MAVROS 1 → MAVROS 2
Імена топіків здебільшого ті самі (`/mavros/state`, `/mavros/local_position/pose`, `/mavros/setpoint_position/local`), але: QoS телеметрії — sensor data; деякі сервіси й параметри перейменовано; запуск — `ros2 launch mavros apm.launch fcu_url:=...` (або `px4.launch`). Для PX4 у ROS 2 замість MAVROS звичайно переходять на uXRCE-DDS (модуль ros2-px4), для ArduPilot — на AP_DDS там, де його функцій стає (модуль ros2-ardupilot).

{{diagram:ros1-migration|Що робити зі старим проєктом ROS 1: тимчасовий міст, перенесення, MAVROS 2 або переписати за ідеями.}}

## practice
### Крок 1. Читання проєкту
Візьми відкритий дроновий проєкт на ROS 1 (приміром, приклад offboard із документації PX4 для ROS 1 / MAVROS або будь-який репозиторій з MAVROS 1). За 30 хвилин намалюй граф вузлів, список залежностей і де проєкт керує апаратом.

### Крок 2. Еталонні дані
Як є змога — запусти проєкт у контейнері ROS 1 Noetic із SITL і запиши `rosbag` входів і виходів вузла. Як ні — візьми bag з відкритих джерел або синтетичні входи.

### Крок 3. Перенесення
Перенеси один вузол (до ~200 рядків): логіку без ROS — в окремий модуль із pytest-тестами (як `offboard_fsm.py`), а вузол — тонка обгортка `rclpy`. Сконвертуй bag у формат ROS 2 (пакет `rosbags`: `rosbags-convert`) і перевір, що виходи перенесеного вузла сходяться з еталонними.

### Крок 4. Звіт
Таблиця: що замінено, кілько рядків логіки стало придатними до тестування без ROS, які відмінності в поведінці трафилися (звичайно — QoS і час).

Лабораторну зараховано, коли є граф вихідного проєкту, перенесений вузол із тестами логіки й порівняння виходів на тих самих даних.

### Шаг 5 (текст — в русской версии)

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

## diagnostics
- **Симптом:** перенесений вузол «зависає» на виклику сервісу
  - Можлива причина: синхронний виклик у колбеку однопотокового executor-а.
  - Що зробити: call_async + обробка future, або окрема група колбеків.
- **Симптом:** вузол не дістає телеметрії MAVROS 2
  - Можлива причина: QoS (sensor data у видавця) або інше ім'я топіка.
  - Що зробити: `ros2 topic info -v`, профіль підписки.
- **Симптом:** параметри «не застосовуються»
  - Можлива причина: у ROS 2 параметр треба оголосити (`declare_parameter`) і передати конкретному вузлу.
  - Що зробити: оголошення в конструкторі, YAML з іменем вузла в launch.
- **Симптом:** ros1_bridge не передає власного типу повідомлення
  - Можлива причина: міст зібрано без того типу або визначення відрізняються.
  - Що зробити: зібрати міст із вихідних кодів з обома воркспейсами; а ліпше — переносити.

## references
- ROS 2 — Migration guide from ROS 1 | https://docs.ros.org/en/jazzy/How-To-Guides/Migrating-from-ROS1.html | primary | A
- ros1_bridge | https://github.com/ros2/ros1_bridge | primary | A
- rosbags (bag conversion, pure Python) | https://gitlab.com/ternaris/rosbags | primary | A
- MAVROS (ROS 2 branch) | https://github.com/mavlink/mavros | primary | A

## checklist
- Знаю відповідності понять ROS 1 → ROS 2 і що міняється по суті
- Читаю ROS 1 проєкт через launch-файли й малюю граф вузлів
- Вибираю між мостом і перенесенням
- Заміняю цикл із rate.sleep таймером, синхронні сервіси — асинхронними
- Перевіряю перенесення на еталонних записаних даних
