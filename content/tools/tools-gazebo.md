---
id: tools-gazebo
title: "Симуляция в Gazebo: миры, датчики, камера в ROS 2 и сценарные тесты"
level: L3
readingTime: 40 мин
firmware: ArduPilot 4.5+ · PX4 1.15+ · Gazebo Harmonic · ROS 2 Jazzy
status: published
tags:
  - Gazebo
  - симуляция
  - SITL
  - сценарные тесты
related:
  - ap-sitl
  - ros2-basics
  - per-camera
  - eng-ci-configs
next:
  - per-cv
---

## summary
SITL без внешнего симулятора считает физику простой встроенной моделью и не знает, что такое дерево, стена или изображение с камеры. Для зрения, обхода препятствий, точной посадки и подвесов нужен мир: Gazebo даёт физику, освещение, камеры, лидары и дальномеры, а автопилот работает с ним как с настоящим аппаратом. Модуль разбирает связку ArduPilot SITL и PX4 SITL с Gazebo (новым, `gz`), устройство мира на SDF, добавление препятствия и камеры, мост изображений в ROS 2, сценарные тесты без графики для CI и что такое HITL и чем он отличается от SITL.

## theory
### Какой Gazebo
- **Gazebo (gz)** — новая линейка (бывший Ignition). Для ROS 2 Jazzy парная LTS-версия — **Gazebo Harmonic**; её же рекомендует плагин ArduPilot.
- **Gazebo Classic** (gazebo11) закончил поддержку в январе 2025 — старые инструкции с `gazebo --verbose` и `.world` для Classic не переносить.
- Пара «ROS 2 — Gazebo» фиксирована: смешивать версии мимо рекомендованных пар — источник трудноуловимых проблем со сборкой мостов.

### Как автопилот говорит с миром
- **ArduPilot**: плагин `ardupilot_gazebo` (система `ArduPilotPlugin` в модели). Gazebo считает физику и датчики, плагин отправляет состояние в SITL и получает от него команды моторам/сервам; обмен — JSON по UDP, в режиме lockstep (симуляция ждёт автопилот, время согласовано). Запуск: в одном терминале `gz sim -v4 -r iris_runway.sdf`, в другом `sim_vehicle.py -v ArduCopter -f gazebo-iris --model JSON --map --console`. Имя фрейма должно содержать `gazebo-`, модель — `JSON`.
- **PX4**: Gazebo встроен в сборку SITL: `make px4_sitl gz_x500`; варианты моделей с датчиками (например `gz_x500_depth`, `gz_x500_mono_cam`) и самолёты/VTOL; мир выбирается переменной `PX4_GZ_WORLD`.
- Переменные окружения: `GZ_SIM_SYSTEM_PLUGIN_PATH` — где искать плагины (сборка `ardupilot_gazebo`), `GZ_SIM_RESOURCE_PATH` — модели и миры.

### Мир на SDF
Мир — XML-файл SDF: физика (шаг, например 1 мс), освещение, земля, модели. Модель — звенья (`link`) с геометрией столкновений (`collision`) и видимой (`visual`), массой и инерцией, суставы (`joint`), датчики (`sensor`) и системы-плагины. Препятствие — статическая модель:
```xml
<model name="pole">
  <static>true</static>
  <pose>10 0 5 0 0 0</pose>
  <link name="link">
    <collision name="collision">
      <geometry><cylinder><radius>0.3</radius><length>10</length></cylinder></geometry>
    </collision>
    <visual name="visual">
      <geometry><cylinder><radius>0.3</radius><length>10</length></cylinder></geometry>
    </visual>
  </link>
</model>
```
Столб 10 м высотой, в 10 м к востоку от начала координат мира (ENU: x — восток, y — север, z — вверх).

### Датчики и мост в ROS 2
- Камеры, камеры глубины, лидары (`gpu_lidar`), IMU — элементы `sensor` в модели; публикуют в шину Gazebo (gz-transport), список — `gz topic -l`.
- **ros_gz_bridge** переносит топики между Gazebo и ROS 2: `ros2 run ros_gz_bridge parameter_bridge /camera@sensor_msgs/msg/Image@gz.msgs.Image` — имя топика, тип ROS 2, тип Gazebo; `@` — в обе стороны, `[` — из Gazebo в ROS, `]` — из ROS в Gazebo.
- Отдельный плагин `GstCameraPlugin` из `ardupilot_gazebo` отдаёт видео с камеры по GStreamer (H.264, UDP 5600) — как настоящая камера на companion; поток включается сообщением в топик `.../enable_streaming`. Пример мира с подвесом и камерой — `gimbal.sdf`; подвес Iris в `iris_runway.sdf` (SITL с `gazebo-iris-gimbal.parm`) управляется каналами RC6–RC8.
- Реализм: идеальная камера без шума и размытия обманывает — алгоритмы зрения стоит проверять с шумом, сменой освещения и размытием движения (параметры шума в описании датчика).

### Скорость и ресурсы
- **Real-time factor (RTF)** — отношение скорости симуляции к реальному времени; с камерами и лидарами на слабой машине падает ниже 1. Lockstep сохраняет корректность, но тест длится дольше.
- Рендеринг нужен только датчикам изображения; для тестов логики без камер — сервер без графики `gz sim -s -r мир.sdf`, для камер на машине без экрана — режим `--headless-rendering`.

### HITL и SITL
- **SITL** — прошивка собрана под компьютер, всё виртуальное.
- **HITL** (hardware in the loop) — настоящий полётник со своей прошивкой, датчики подменяются данными симулятора по USB/MAVLink, моторы не крутятся. Проверяет реальное железо: тайминги, загрузку процессора, драйверы, что SITL скрывает. Поддержка и способ настройки отличаются у PX4 и ArduPilot и между версиями — по документации своей версии.

### Сценарные тесты
Сценарий — воспроизводимый полёт с проверкой результата: «взлёт на 10 м, облёт столба, посадка; не ближе 2 м к столбу, высота в допуске». Запуск без графики, проверка через MAVLink и лог, результат — pass/fail для CI (модуль «Конфигурации в CI»). Один сценарий на каждую функцию безопасности (failsafe, геозона, RTL) ловит регрессии при обновлении прошивки и параметров раньше поля.

{{diagram:gazebo-sitl|Gazebo считает физику и датчики, плагин обменивается с SITL по JSON в lockstep; изображения идут в ROS 2 через ros_gz_bridge, наземка и тесты подключаются к SITL по MAVLink.}}

## practice
### Шаг 1. Iris в Gazebo
Установить Gazebo Harmonic и собрать `ardupilot_gazebo` по README (зависимости, `cmake`, `make`), выставить `GZ_SIM_SYSTEM_PLUGIN_PATH` и `GZ_SIM_RESOURCE_PATH`. Запустить `iris_runway.sdf` и SITL с `-f gazebo-iris --model JSON`. Взлёт в GUIDED на 10 м из MAVProxy. Записать RTF при висении.

### Шаг 2. Свой мир со столбом
Скопировать `iris_runway.sdf` в свой мир, добавить столб из теории. Миссия: взлёт, точка в 20 м к востоку на высоте 5 м, возврат. Что происходит с аппаратом без обхода препятствий? Перенести точку так, чтобы маршрут проходил в 3 м от столба.

### Шаг 3. Камера в ROS 2
Запустить мир с камерой (`gimbal.sdf` или модель с камерой), найти топик изображения (`gz topic -l`), поднять мост в ROS 2 и проверить `ros2 topic hz` и `rqt_image_view` (или `ros2 run image_tools showimage`). Записать частоту кадров и разрешение.

### Шаг 4. Сценарный тест
pytest-сценарий против SITL (Gazebo без графики: `gz sim -s -r мир.sdf`):
```python
import time
from pymavlink import mavutil

def test_takeoff_hold_land():
    m = mavutil.mavlink_connection("udpin:0.0.0.0:14550")
    m.wait_heartbeat(timeout=30)
    m.set_mode("GUIDED")
    deadline = time.time() + 60
    while not m.motors_armed():                    # pre-arm checks pass once EKF and GPS are ready
        assert time.time() < deadline, "не армится за 60 с"
        m.arducopter_arm()
        m.recv_match(type="HEARTBEAT", blocking=True, timeout=2)
    m.mav.command_long_send(m.target_system, m.target_component,
                            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, 10)
    alts, t0 = [], time.time()
    while time.time() - t0 < 30:
        p = m.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=2)
        if p:
            alts.append(p.relative_alt / 1000)
    assert max(alts) > 9.0, f"не набрал высоту: {max(alts):.1f} м"
    assert abs(alts[-1] - 10) < 1.0, f"не держит высоту: {alts[-1]:.1f} м"
    m.set_mode("LAND")
```
Добавить второй тест: геозона (`FENCE_ENABLE = 1`, радиус 50 м) и полёт в точку за ней — аппарат должен уйти в действие геозоны. Записать время прогона каждого теста.

Лабораторная засчитывается, когда Iris летает в Gazebo с измеренным RTF, свой мир со столбом загружается, изображение с камеры видно в ROS 2 с измеренной частотой, два сценарных теста проходят без графики.

## diagnostics
- **Симптом:** SITL не видит Gazebo, аппарат «висит» на земле
  - Возможная причина: не выставлен `GZ_SIM_SYSTEM_PLUGIN_PATH`, плагин не собран, фрейм без `gazebo-` или модель не `JSON`.
  - Что сделать: проверить переменные, сборку плагина, аргументы `sim_vehicle.py`.
- **Симптом:** мир не находит модели
  - Возможная причина: не выставлен `GZ_SIM_RESOURCE_PATH`.
  - Что сделать: добавить пути `models` и `worlds`.
- **Симптом:** симуляция идёт медленнее реального времени
  - Возможная причина: камеры и лидары на слабой машине, мелкий шаг физики, рендеринг в окне.
  - Что сделать: сервер без графики, меньше датчиков и разрешение, `--headless-rendering` для камер.
- **Симптом:** ros_gz_bridge запущен, топика в ROS 2 нет
  - Возможная причина: неверное имя топика или тип, несовпадение версий ROS 2 и Gazebo.
  - Что сделать: `gz topic -l` и `gz topic -i`, точное имя и тип, рекомендованная пара версий.
- **Симптом:** алгоритм зрения отлично работает в симуляции и плохо в поле
  - Возможная причина: идеальная картинка без шума, размытия и смены освещения.
  - Что сделать: шум датчика в SDF, разные освещения и текстуры, проверка на записанных реальных данных.

## references
- ArduPilot — ardupilot_gazebo plugin (README) | https://github.com/ArduPilot/ardupilot_gazebo | primary | A
- ArduPilot — Using SITL with Gazebo | https://ardupilot.org/dev/docs/sitl-with-gazebo.html | primary | A
- PX4 — Gazebo simulation | https://docs.px4.io/main/en/sim_gazebo_gz/ | primary | A
- Gazebo — documentation (Harmonic) | https://gazebosim.org/docs/harmonic/getstarted/ | primary | A
- ros_gz — ROS 2 ↔ Gazebo bridge | https://github.com/gazebosim/ros_gz | primary | A

## checklist
- Выбираю версию Gazebo в паре с ROS 2 и не путаю с Gazebo Classic
- Запускаю ArduPilot и PX4 SITL с Gazebo
- Описываю мир и модели на SDF и добавляю препятствия
- Передаю изображение камеры в ROS 2 через ros_gz_bridge
- Пишу сценарные тесты, которые идут без графики в CI
- Объясняю разницу SITL и HITL
