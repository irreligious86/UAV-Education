---
id: px4-ros2
title: "PX4 и ROS 2: uXRCE-DDS и offboard"
level: L4
readingTime: 30 мин
firmware: PX4 1.15+ / ROS 2 Jazzy (Humble — запасной)
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
---

## summary
В PX4 топики uORB можно вывести прямо в ROS 2: клиент uXRCE-DDS на полётнике и агент на companion-компьютере прокидывают сообщения в обе стороны. Это даёт ROS-узлам доступ к ориентации, позиции и командам без MAVLink-обёртки. Модуль показывает, как поднять мост на SITL, что такое `px4_msgs`, как устроено offboard-управление (`OffboardControlMode` + `TrajectorySetpoint` + `VehicleCommand`) и почему PX4 выкидывает из Offboard, если ты замолчал.

## theory
### Мост uXRCE-DDS
- **Клиент** `uxrce_dds_client` в PX4 публикует/подписывает ограниченный набор топиков uORB (список — `dds_topics.yaml`).
- **Агент** `MicroXRCEAgent` на companion или ПК принимает их по UDP или serial и выставляет в DDS — то есть в ROS 2.
- Сообщения на стороне ROS 2 — пакет `px4_msgs`; **ветка `px4_msgs` должна соответствовать версии PX4**, иначе несовпадение определений. Для разных версий есть узел-переводчик сообщений.

Топики появляются в ROS 2 как `/fmu/out/*` (из PX4) и `/fmu/in/*` (в PX4).

### Offboard: три сообщения
1. **`OffboardControlMode`** — говорит PX4, *чем* ты управляешь (позиция, скорость, ускорение, ориентация, rates). Должен идти потоком **до** перехода в Offboard и всё время в нём; при частоте ниже ~2 Гц PX4 выходит из Offboard.
2. **`TrajectorySetpoint`** — сама цель: позиция/скорость в NED (Z вниз!), yaw.
3. **`VehicleCommand`** — команды: сменить режим (`VEHICLE_CMD_DO_SET_MODE`, Offboard = base 1, custom 6), арм (`VEHICLE_CMD_COMPONENT_ARM_DISARM`). Подтверждение — `VehicleCommandAck`.

Та же философия, что GUIDED в ArduPilot: companion советует потоком, автопилот следит за таймаутом и всегда может быть перехвачен пилотом.

### Против MAVLink/MAVSDK
MAVLink через MAVSDK проще для простых задач и не требует ROS. uXRCE-DDS — когда нужны ROS-экосистема (навигация, зрение, планирование), низкая задержка и доступ к внутренним топикам.

### Настройка моста на реальном борту
PX4: `UXRCE_DDS_CFG` = TELEM2 (порт), `SER_TEL2_BAUD` = 921600; на companion: `MicroXRCEAgent serial --dev /dev/ttyTHS1 -b 921600` (Jetson) или `udp4 -p 8888` для SITL/Wi-Fi. Проверка: `ros2 topic list | grep fmu`, `ros2 topic hz /fmu/out/vehicle_odometry` (ожидаемо десятки–сотни Гц). Если топиков нет: порт занят MAVLink (`MAV_1_CONFIG` на том же TELEM2 — конфликт), скорость, `uxrce_dds_client status` в консоли PX4.

### Системы координат — главный источник ошибок
PX4 работает в NED (север-восток-вниз) и FRD (вперёд-вправо-вниз); ROS 2 (REP-103) — ENU и FLU. `TrajectorySetpoint.position = [x, y, z]` — NED: z = −10 означает 10 м вверх. Переводы: ENU→NED: (x, y, z) → (y, x, −z); FLU→FRD: (x, y, z) → (x, −y, −z). Пакет `px4_ros_com` содержит утилиты преобразования; MAVROS делает это сам. Ошибка знака по z — классический «аппарат ушёл в землю при взлёте в симуляторе».

### Минимальный offboard-узел (Python, rclpy)
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
Защиты из модуля «Слежение» (лимиты, watchdog, таймауты `COM_OF_LOSS_T` = 1 с и действие `COM_OBL_RC_ACT`) обязательны и здесь.

{{diagram:px4-offboard-seq|Offboard из ROS 2: поток OffboardControlMode и TrajectorySetpoint до переключения режима, затем команды режима и арма; при обрыве — failsafe.}}

## practice
### Шаг 1. Окружение
```
# ROS 2 Jazzy (Ubuntu 24.04) установлен и source'нут; запасной вариант — Humble (22.04)
mkdir -p ~/ws_px4/src && cd ~/ws_px4/src
git clone https://github.com/PX4/px4_msgs.git      # branch matching your PX4 version
git clone https://github.com/PX4/px4_ros_com.git
cd .. && colcon build && source install/setup.bash
```

Агент: `MicroXRCEAgent udp4 -p 8888` (сборка из исходников или snap — по документации).

### Шаг 2. SITL с клиентом
`make px4_sitl gz_x500` — в SITL клиент uXRCE-DDS стартует сам и ищет агента на 8888. Проверка: `ros2 topic list` показывает `/fmu/out/vehicle_attitude` и прочие; `ros2 topic echo /fmu/out/vehicle_local_position` (с PX4 1.17 — `/fmu/out/vehicle_local_position_v1`).

### Шаг 3. Offboard-пример
Запусти пример из `px4_ros_com` (offboard control): узел 10 циклов шлёт `OffboardControlMode` + `TrajectorySetpoint`, затем переключает режим и армит через `VehicleCommand`, после чего держит точку на 5 м. Прочитай код: порядок «сначала поток, потом режим» — ключевой.

### Шаг 4. Свой узел
Напиши узел на Python (`rclpy`), который держит квадрокоптер на высоте 3 м и каждые 10 с меняет цель по кругу радиусом 5 м. Проверь: остановил узел — через ~1 с (`COM_OF_LOSS_T`, 1 с по умолчанию) PX4 выходит из Offboard (в SITL — переход в Hold/Land по failsafe-настройке).

Каркас (структура как в примере `px4_ros_com`, имена топиков сверить с `ros2 topic list` своей версии PX4):
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
Что проверить по логу: в `.ulg` `trajectory_setpoint` ступенькой меняется каждые 10 с, `vehicle_local_position` догоняет за 2–4 с без перелёта больше 0.5 м; при `Ctrl+C` узла — переход режима через `COM_OF_LOSS_T`.

### Лабораторная
Узел работает в SITL; лог `.ulg` показывает `vehicle_local_position` против `trajectory_setpoint`; документировано поведение при остановке узла.

## diagnostics
- **Симптом:** `ros2 topic list` пуст
  - Возможная причина: агент не запущен, не тот порт, не совпадает версия `px4_msgs`.
  - Что сделать: запустить агента на 8888, проверить ветку `px4_msgs`.
- **Симптом:** не переключается в Offboard
  - Возможная причина: `OffboardControlMode` не шёл потоком до команды.
  - Что сделать: слать поток ≥ 2 Гц заранее, затем режим.
- **Симптом:** выкидывает из Offboard в полёте
  - Возможная причина: частота `OffboardControlMode` упала ниже ~2 Гц.
  - Что сделать: таймер узла, проверить загрузку companion.
- **Симптом:** летит вверх вместо вниз
  - Возможная причина: знак Z в NED.
  - Что сделать: Z вниз положительный, высота 3 м — Z = −3.
- **Симптом:** PX4 не входит в Offboard
  - Возможная причина: setpoint'ы не шли ≥ 1 с до команды, частота < 2 Гц, неверный QoS.
  - Что сделать: поток до смены режима, 10+ Гц, BEST_EFFORT QoS; `commander status`.
- **Симптом:** взлёт «в землю» в SITL
  - Возможная причина: знак z (NED).
  - Что сделать: z отрицательный вверх; проверить конверсию ENU/NED.

## references
- PX4 ROS 2 User Guide | https://docs.px4.io/main/en/ros2/user_guide.html | primary | A
- PX4 uXRCE-DDS | https://docs.px4.io/main/en/middleware/uxrce_dds.html | primary | A
- PX4 ROS 2 Offboard Control Example | https://docs.px4.io/main/en/ros2/offboard_control.html | primary | A
- px4_msgs (GitHub) | https://github.com/PX4/px4_msgs | primary | A
- px4_ros_com (GitHub) | https://github.com/PX4/px4_ros_com | primary | A

## checklist
- Агент и клиент связаны, топики видны в ROS 2
- Ветка `px4_msgs` соответствует версии PX4
- Пример offboard запущен и прочитан
- Свой узел держит поток `OffboardControlMode` ≥ 2 Гц
- Поведение при остановке узла проверено
