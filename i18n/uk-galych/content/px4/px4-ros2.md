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
У PX4 топіки uORB можна вивести просто в ROS 2: клієнт uXRCE-DDS на польотному контролері та агент на companion-комп'ютері прокидають повідомлення в обидва боки. То дає ROS-вузлам доступ до орієнтації, позиції та команд без MAVLink-обгортки. Модуль показує, як підняти міст на SITL, що то є `px4_msgs`, як влаштоване offboard-керування (`OffboardControlMode` + `TrajectorySetpoint` + `VehicleCommand`) і чому PX4 викидає з Offboard, як ти замовк.

## theory
### Міст uXRCE-DDS
- **Клієнт** `uxrce_dds_client` у PX4 публікує/підписується на обмежений набір топіків uORB (список — `dds_topics.yaml`).
- **Агент** `MicroXRCEAgent` на companion або ПК приймає їх по UDP ци serial і виставляє в DDS — тобто в ROS 2.
- Повідомлення з боку ROS 2 — пакет `px4_msgs`; **гілка `px4_msgs` мусить відповідати версії PX4**, бо інакше визначення ся не зійдуть. Для різних версій є вузол-перекладач повідомлень.

Топіки ся появляють у ROS 2 як `/fmu/out/*` (з PX4) і `/fmu/in/*` (у PX4).

### Offboard: три повідомлення
1. **`OffboardControlMode`** — каже PX4, *чим* ти керуєш (позиція, швидкість, прискорення, орієнтація, rates). Мусить іти потоком **до** переходу в Offboard і весь час у ньому; як частота впаде нижче ~2 Гц, PX4 виходить з Offboard.
2. **`TrajectorySetpoint`** — сама ціль: позиція/швидкість у NED (Z униз!), yaw.
3. **`VehicleCommand`** — команди: змінити режим (`VEHICLE_CMD_DO_SET_MODE`, Offboard = base 1, custom 6), арм (`VEHICLE_CMD_COMPONENT_ARM_DISARM`). Підтвердження — `VehicleCommandAck`.

Та сама філософія, що й GUIDED в ArduPilot: companion радить потоком, автопілот пантрує таймаут, а пілот завжди може перехопити керування.

### Проти MAVLink/MAVSDK
MAVLink через MAVSDK простіший для простих задач і не потребує ROS. uXRCE-DDS — коли треба ROS-екосистему (навігація, зір, планування), низьку затримку й доступ до внутрішніх топіків.

### Налаштування мосту на реальному борту
PX4: `UXRCE_DDS_CFG` = TELEM2 (порт), `SER_TEL2_BAUD` = 921600; на companion: `MicroXRCEAgent serial --dev /dev/ttyTHS1 -b 921600` (Jetson) або `udp4 -p 8888` для SITL/Wi-Fi. Перевірка: `ros2 topic list | grep fmu`, `ros2 topic hz /fmu/out/vehicle_odometry` (мають бути десятки–сотні Гц). Як топіків ніц нема: порт зайнятий MAVLink (`MAV_1_CONFIG` на тому самому TELEM2 — конфлікт), швидкість, `uxrce_dds_client status` у консолі PX4.

### Системи координат — головне джерело помилок
PX4 працює в NED (північ-схід-униз) і FRD (уперед-праворуч-униз); ROS 2 (REP-103) — ENU і FLU. `TrajectorySetpoint.position = [x, y, z]` — NED: z = −10 значить 10 м угору. Перетворення: ENU→NED: (x, y, z) → (y, x, −z); FLU→FRD: (x, y, z) → (x, −y, −z). Пакет `px4_ros_com` має утиліти перетворення; MAVROS робить то сам. Помилка знака по z — класичне «апарат пішов у землю на зльоті в симуляторі».

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
Захисти з модуля «Стеження» (ліміти, watchdog, таймаути `COM_OF_LOSS_T` = 1 с і дія `COM_OBL_RC_ACT`) тут так само обов'язкові.

{{diagram:px4-offboard-seq|Offboard з ROS 2: потік OffboardControlMode і TrajectorySetpoint до перемикання режиму, потім команди режиму та арму; як зв'язок урветься — failsafe.}}

## practice
### Крок 1. Оточення
```
# ROS 2 Jazzy (Ubuntu 24.04) встановлено й source'нуто; запасний варіант — Humble (22.04)
mkdir -p ~/ws_px4/src && cd ~/ws_px4/src
git clone https://github.com/PX4/px4_msgs.git      # branch matching your PX4 version
git clone https://github.com/PX4/px4_ros_com.git
cd .. && colcon build && source install/setup.bash
```

Агент: `MicroXRCEAgent udp4 -p 8888` (збірка з вихідних кодів або snap — як пише документація).

### Крок 2. SITL із клієнтом
`make px4_sitl gz_x500` — у SITL клієнт uXRCE-DDS стартує сам і шукає агента на 8888. Перевірка: `ros2 topic list` показує `/fmu/out/vehicle_attitude` та інші; `ros2 topic echo /fmu/out/vehicle_local_position` (з PX4 1.17 — `/fmu/out/vehicle_local_position_v1`).

### Крок 3. Offboard-приклад
Запусти приклад із `px4_ros_com` (offboard control): вузол 10 циклів шле `OffboardControlMode` + `TrajectorySetpoint`, потім перемикає режим і армить через `VehicleCommand`, а відтак тримає точку на 5 м. Прочитай код: порядок «спершу потік, потім режим» — то ключ до вшиткого.

### Крок 4. Власний вузол
Напиши вузол на Python (`rclpy`), який тримає квадрокоптер на висоті 3 м і кожні 10 с міняє ціль по колу радіусом 5 м. Перевір: зупинив вузол — за ~1 с (`COM_OF_LOSS_T`, з коробки 1 с) PX4 виходить з Offboard (у SITL — перехід у Hold/Land, як налаштовано failsafe).

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
Що глянути в логу: у `.ulg` `trajectory_setpoint` міняється сходинкою кожні 10 с, `vehicle_local_position` наздоганяє за 2–4 с без перельоту понад 0.5 м; після `Ctrl+C` вузла — перехід режиму через `COM_OF_LOSS_T`.

### Лабораторна
Вузол працює в SITL; лог `.ulg` показує `vehicle_local_position` проти `trajectory_setpoint`; поведінку при зупинці вузла задокументовано.

## diagnostics
- **Симптом:** `ros2 topic list` порожній
  - Можлива причина: агента не запущено, не той порт, не сходиться версія `px4_msgs`.
  - Що зробити: запустити агента на 8888, перевірити гілку `px4_msgs`.
- **Симптом:** не перемикається в Offboard
  - Можлива причина: `OffboardControlMode` не йшов потоком до команди.
  - Що зробити: слати потік ≥ 2 Гц заздалегідь, а вже потім режим.
- **Симптом:** викидає з Offboard у польоті
  - Можлива причина: частота `OffboardControlMode` впала нижче ~2 Гц.
  - Що зробити: таймер вузла, глянути, ци не перевантажений companion.
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
