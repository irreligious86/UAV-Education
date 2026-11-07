---
id: px4-ros2
title: "PX4 и ROS 2: uXRCE-DDS и offboard"
level: L4
readingTime: 30 мин
firmware: PX4 1.14+ / ROS 2 Humble
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

## practice
### Шаг 1. Окружение
```
# ROS 2 Humble установлен и source'нут
mkdir -p ~/ws_px4/src && cd ~/ws_px4/src
git clone https://github.com/PX4/px4_msgs.git      # branch matching your PX4 version
git clone https://github.com/PX4/px4_ros_com.git
cd .. && colcon build && source install/setup.bash
```

Агент: `MicroXRCEAgent udp4 -p 8888` (сборка из исходников или snap — по документации).

### Шаг 2. SITL с клиентом
`make px4_sitl gz_x500` — в SITL клиент uXRCE-DDS стартует сам и ищет агента на 8888. Проверка: `ros2 topic list` показывает `/fmu/out/vehicle_attitude` и прочие; `ros2 topic echo /fmu/out/vehicle_local_position`.

### Шаг 3. Offboard-пример
Запусти пример из `px4_ros_com` (offboard control): узел 10 циклов шлёт `OffboardControlMode` + `TrajectorySetpoint`, затем переключает режим и армит через `VehicleCommand`, после чего держит точку на 5 м. Прочитай код: порядок «сначала поток, потом режим» — ключевой.

### Шаг 4. Свой узел
Напиши узел на Python (`rclpy`), который держит квадрокоптер на высоте 3 м и каждые 10 с меняет цель по кругу радиусом 5 м. Проверь: остановил узел — через ~2 с PX4 выходит из Offboard (в SITL — переход в Hold/Land по failsafe-настройке).

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
