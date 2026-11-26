---
id: px4-ros2
title: "PX4 і ROS 2: uXRCE-DDS та offboard"
level: L4
readingTime: 30 хв
firmware: PX4 1.15+ / ROS 2 Jazzy (Humble — запасний)
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
source: content/px4/px4-ros2.md
source_hash: df1e92027766
---

## summary
У PX4 топіки uORB можна вивести просто в ROS 2: клієнт uXRCE-DDS на польотному контролері та агент на companion-комп'ютері прокидають повідомлення в обидва боки. Це дає ROS-вузлам доступ до орієнтації, позиції та команд без MAVLink-обгортки. Модуль показує, як підняти міст на SITL, що таке `px4_msgs`, як влаштоване offboard-керування (`OffboardControlMode` + `TrajectorySetpoint` + `VehicleCommand`) і чому PX4 викидає з Offboard, якщо ти замовк.

## theory
### Міст uXRCE-DDS
- **Клієнт** `uxrce_dds_client` у PX4 публікує/підписується на обмежений набір топіків uORB (список — `dds_topics.yaml`).
- **Агент** `MicroXRCEAgent` на companion або ПК приймає їх по UDP чи serial і виставляє в DDS — тобто в ROS 2.
- Повідомлення на боці ROS 2 — пакет `px4_msgs`; **гілка `px4_msgs` має відповідати версії PX4**, інакше визначення не збігаються. Для різних версій є вузол-перекладач повідомлень.

Топіки з'являються в ROS 2 як `/fmu/out/*` (з PX4) і `/fmu/in/*` (у PX4).

{{diagram:px4-dds-topic-naming|Суффикс _v1 зависит от версии сообщения, а не от направления: старое имя без суффикса после обновления до 1.17 молчит.}}

### Offboard: три повідомлення
1. **`OffboardControlMode`** — каже PX4, *чим* ти керуєш (позиція, швидкість, прискорення, орієнтація, rates). Має йти потоком **до** переходу в Offboard і весь час у ньому; за частоти нижче ~2 Гц PX4 виходить з Offboard.
2. **`TrajectorySetpoint`** — сама ціль: позиція/швидкість у NED (Z униз!), yaw.
3. **`VehicleCommand`** — команди: змінити режим (`VEHICLE_CMD_DO_SET_MODE`, Offboard = base 1, custom 6), арм (`VEHICLE_CMD_COMPONENT_ARM_DISARM`). Підтвердження — `VehicleCommandAck`.

Та сама філософія, що й GUIDED в ArduPilot: companion радить потоком, автопілот стежить за таймаутом, і пілот завжди може перехопити керування.

{{diagram:px4-offboard-loss-timeline|PX4 выходит из Offboard через COM_OF_LOSS_T после метки последнего сообщения (4.9 → 5.9 с); с метками из прошлого Offboard недоступен вовсе, даже при потоке 10 Гц.}}

### Проти MAVLink/MAVSDK
MAVLink через MAVSDK простіший для простих задач і не потребує ROS. uXRCE-DDS — коли потрібні ROS-екосистема (навігація, зір, планування), низька затримка й доступ до внутрішніх топіків.

### Налаштування мосту на реальному борту
PX4: `UXRCE_DDS_CFG` = TELEM2 (порт), `SER_TEL2_BAUD` = 921600; на companion: `MicroXRCEAgent serial --dev /dev/ttyTHS1 -b 921600` (Jetson) або `udp4 -p 8888` для SITL/Wi-Fi. Перевірка: `ros2 topic list | grep fmu`, `ros2 topic hz /fmu/out/vehicle_odometry` (очікувано десятки–сотні Гц). Якщо топіків немає: порт зайнятий MAVLink (`MAV_1_CONFIG` на тому ж TELEM2 — конфлікт), швидкість, `uxrce_dds_client status` у консолі PX4.

### Системи координат — головне джерело помилок
PX4 працює в NED (північ-схід-униз) і FRD (уперед-праворуч-униз); ROS 2 (REP-103) — ENU і FLU. `TrajectorySetpoint.position = [x, y, z]` — NED: z = −10 означає 10 м угору. Перетворення: ENU→NED: (x, y, z) → (y, x, −z); FLU→FRD: (x, y, z) → (x, −y, −z). Пакет `px4_ros_com` містить утиліти перетворення; MAVROS робить це сам. Помилка знака по z — класичне «апарат пішов у землю під час зльоту в симуляторі».

### Мінімальний offboard-вузол (Python, rclpy)
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
Захисти з модуля «Стеження» (ліміти, watchdog, таймаути `COM_OF_LOSS_T` = 1 с і дія `COM_OBL_RC_ACT`) обов'язкові й тут.

{{diagram:px4-offboard-seq|Offboard з ROS 2: потік OffboardControlMode і TrajectorySetpoint до перемикання режиму, потім команди режиму та арму; у разі обриву — failsafe.}}

## practice
### Крок 0. Міст на папері: імена, частоти, навантаження, таймаут
Виконується на будь-якому комп'ютері з Python 3 та інтернетом, без ROS. Скрипт читає `dds_topics.yaml` і файли `.msg` тегу PX4, будує імена ROS 2 із суфіксом `_vN`, розміри CDR, граничні частоти, навантаження на UART і момент втрати Offboard (`offboardCheck.cpp`: остання мітка + `COM_OF_LOSS_T`). Збережи як `px4_dds_lab.py`:
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
Вивід `python3 px4_dds_lab.py v1.17.0` (2026-11-26); з `v1.18.0` у списку з'являється `vehicle_status_v4`, а сума зростає до 117077 B/s:
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

### Крок 1. Оточення
```
# ROS 2 Jazzy (Ubuntu 24.04) встановлено й source'нуто; запасний варіант — Humble (22.04)
mkdir -p ~/ws_px4/src && cd ~/ws_px4/src
git clone https://github.com/PX4/px4_msgs.git      # branch matching your PX4 version
git clone https://github.com/PX4/px4_ros_com.git
cd .. && colcon build && source install/setup.bash
```

Агент: `MicroXRCEAgent udp4 -p 8888` (збірка з вихідних кодів або snap — за документацією).

### Крок 2. SITL із клієнтом
`make px4_sitl gz_x500` — у SITL клієнт uXRCE-DDS стартує сам і шукає агента на 8888. Перевірка: `ros2 topic list` показує `/fmu/out/vehicle_attitude` та інші; `ros2 topic echo /fmu/out/vehicle_local_position` (з PX4 1.17 — `/fmu/out/vehicle_local_position_v1`).

### Крок 3. Offboard-приклад
Запусти приклад із `px4_ros_com` (offboard control): вузол 10 циклів шле `OffboardControlMode` + `TrajectorySetpoint`, потім перемикає режим і армить через `VehicleCommand`, після чого тримає точку на 5 м. Прочитай код: порядок «спочатку потік, потім режим» — ключовий.

### Крок 4. Власний вузол
Напиши вузол на Python (`rclpy`), який тримає квадрокоптер на висоті 3 м і кожні 10 с змінює ціль по колу радіусом 5 м. Перевір: зупинив вузол — через ~1 с (`COM_OF_LOSS_T`, типово 1 с) PX4 виходить з Offboard (у SITL — перехід у Hold/Land згідно з налаштуванням failsafe).

Каркас (структура як у прикладі `px4_ros_com`, імена топіків звір із `ros2 topic list` своєї версії PX4):
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
Що перевірити за логом: у `.ulg` `trajectory_setpoint` змінюється сходинкою кожні 10 с, `vehicle_local_position` наздоганяє за 2–4 с без перельоту понад 0.5 м; після `Ctrl+C` вузла — перехід режиму через `COM_OF_LOSS_T`.

### Лабораторна
Вузол працює в SITL; лог `.ulg` показує `vehicle_local_position` проти `trajectory_setpoint`; задокументовано поведінку при зупинці вузла.

## diagnostics
- **Симптом:** `ros2 topic list` порожній
  - Можлива причина: агента не запущено, не той порт, не збігається версія `px4_msgs`.
  - Що зробити: запустити агента на 8888, перевірити гілку `px4_msgs`.
- **Симптом:** не перемикається в Offboard
  - Можлива причина: `OffboardControlMode` не йшов потоком до команди.
  - Що зробити: слати потік ≥ 2 Гц заздалегідь, потім режим.
- **Симптом:** викидає з Offboard у польоті
  - Можлива причина: частота `OffboardControlMode` впала нижче ~2 Гц.
  - Що зробити: таймер вузла, перевірити завантаження companion.
- **Симптом:** летить угору замість униз
  - Можлива причина: знак Z у NED.
  - Що зробити: Z униз додатний, висота 3 м — Z = −3.
- **Симптом:** PX4 не входить в Offboard
  - Можлива причина: setpoint'и не йшли ≥ 1 с до команди, частота < 2 Гц, неправильний QoS.
  - Що зробити: потік до зміни режиму, 10+ Гц, BEST_EFFORT QoS; `commander status`.
- **Симптом:** зліт «у землю» в SITL
  - Можлива причина: знак z (NED).
  - Що зробити: z від'ємний угору; перевірити конверсію ENU/NED.

## references
- PX4 ROS 2 User Guide | https://docs.px4.io/main/en/ros2/user_guide.html | primary | A
- PX4 uXRCE-DDS | https://docs.px4.io/main/en/middleware/uxrce_dds.html | primary | A
- PX4 ROS 2 Offboard Control Example | https://docs.px4.io/main/en/ros2/offboard_control.html | primary | A
- px4_msgs (GitHub) | https://github.com/PX4/px4_msgs | primary | A
- px4_ros_com (GitHub) | https://github.com/PX4/px4_ros_com | primary | A

## checklist
- Агент і клієнт пов'язані, топіки видно в ROS 2
- Гілка `px4_msgs` відповідає версії PX4
- Приклад offboard запущено й прочитано
- Власний вузол тримає потік `OffboardControlMode` ≥ 2 Гц
- Поведінку при зупинці вузла перевірено
