---
id: tools-gazebo
title: "Симуляція в Gazebo: світи, датчики, камера в ROS 2 і сценарні тести"
level: L3
readingTime: 40 хв
firmware: ArduPilot 4.5+ · PX4 1.15+ · Gazebo Harmonic · ROS 2 Jazzy
status: published
tags:
  - Gazebo
  - симуляція
  - SITL
  - сценарні тести
related:
  - ap-sitl
  - ros2-basics
  - per-camera
  - eng-ci-configs
next:
  - per-cv
source: content/tools/tools-gazebo.md
source_hash: 86f99ad4c74a
---

## summary
SITL без зовнішнього симулятора рахує фізику простою вбудованою моделлю і ніц не знає про дерево, стіну чи зображення з камери. Для зору, обходу перешкод, точної посадки й підвісів треба світ: Gazebo дає фізику, освітлення, камери, лідари й далекоміри, а автопілот працює з ним як зі справжнім апаратом. Модуль розбирає зв'язку ArduPilot SITL і PX4 SITL з Gazebo (новим, `gz`), будову світу на SDF, як додати перешкоду й камеру, міст зображень у ROS 2, сценарні тести без графіки для CI, а також що то є HITL і чим він ся відрізняє від SITL.

## theory
### Який Gazebo
- **Gazebo (gz)** — нова лінійка (колишній Ignition). Для ROS 2 Jazzy парна LTS-версія — **Gazebo Harmonic**; її ж радить плагін ArduPilot.
- **Gazebo Classic** (gazebo11) скінчив підтримку в січні 2025 — старих інструкцій з `gazebo --verbose` і `.world` для Classic не переносити.
- Пара «ROS 2 — Gazebo» фіксована: як змішаєш версії поза рекомендованими парами, то потім фест намучишся з проблемами зі збиранням мостів, які важко зловити.

### Як автопілот говорить зі світом
- **ArduPilot**: плагін `ardupilot_gazebo` (система `ArduPilotPlugin` у моделі). Gazebo рахує фізику й датчики, плагін шле стан у SITL і дістає від нього команди моторам/сервам; обмін — JSON по UDP, у режимі lockstep (симуляція чекає на автопілот, час узгоджено). Запуск: в одному терміналі `gz sim -v4 -r iris_runway.sdf`, в іншому `sim_vehicle.py -v ArduCopter -f gazebo-iris --model JSON --map --console`. Ім'я фрейму мусить мати `gazebo-`, модель — `JSON`.
- **PX4**: Gazebo вбудовано в збірку SITL: `make px4_sitl gz_x500`; є варіанти моделей із датчиками (наприклад `gz_x500_depth`, `gz_x500_mono_cam`) і літаки/VTOL; світ вибираєш змінною `PX4_GZ_WORLD`.
- Змінні оточення: `GZ_SIM_SYSTEM_PLUGIN_PATH` — де шукати плагіни (збірка `ardupilot_gazebo`), `GZ_SIM_RESOURCE_PATH` — моделі й світи.

### Світ на SDF
Світ — то XML-файл SDF: фізика (крок, наприклад 1 мс), освітлення, земля, моделі. Модель — ланки (`link`) з геометрією зіткнень (`collision`) і видимою (`visual`), масою та інерцією, шарніри (`joint`), датчики (`sensor`) і системи-плагіни. Перешкода — статична модель:
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
Ади: стовп заввишки 10 м, за 10 м на схід від початку координат світу (ENU: x — схід, y — північ, z — угору).

### Датчики й міст у ROS 2
- Камери, камери глибини, лідари (`gpu_lidar`), IMU — то елементи `sensor` у моделі; вони публікують у шину Gazebo (gz-transport), список — `gz topic -l`.
- **ros_gz_bridge** переносить топіки між Gazebo і ROS 2: `ros2 run ros_gz_bridge parameter_bridge /camera@sensor_msgs/msg/Image@gz.msgs.Image` — ім'я топіка, тип ROS 2, тип Gazebo; `@` — в обидва боки, `[` — з Gazebo в ROS, `]` — з ROS у Gazebo.
- Окремий плагін `GstCameraPlugin` з `ardupilot_gazebo` віддає відео з камери через GStreamer (H.264, UDP 5600) — як справжня камера на companion; потік ся вмикає повідомленням у топік `.../enable_streaming`. Приклад світу з підвісом і камерою — `gimbal.sdf`; підвіс Iris в `iris_runway.sdf` (SITL з `gazebo-iris-gimbal.parm`) керується каналами RC6–RC8.
- Реалізм: ідеальна камера без шуму й розмиття вводить в оману — алгоритми зору перевіряй з шумом, зміною освітлення й розмиттям руху (параметри шуму в описі датчика).

### Швидкість і ресурси
- **Real-time factor (RTF)** — відношення швидкості симуляції до реального часу; з камерами й лідарами на слабкій машині падає нижче 1. Lockstep тримає коректність, але тест триває довше.
- Рендеринг треба лиш датчикам зображення; для тестів логіки без камер — сервер без графіки `gz sim -s -r мир.sdf`, для камер на машині без екрана — режим `--headless-rendering`.

### HITL і SITL
- **SITL** — прошивку зібрано під комп'ютер, вшитко віртуальне.
- **HITL** (hardware in the loop) — справжній польотний контролер зі своєю прошивкою, датчики підмінюються даними симулятора через USB/MAVLink, мотори не крутяться. Перевіряє реальне залізо: таймінги, завантаження процесора, драйвери — те, що SITL ховає. Підтримка і спосіб налаштування різняться в PX4 і ArduPilot та між версіями — глянь документацію своєї версії.

### Сценарні тести
Сценарій — то відтворюваний політ із перевіркою результату: «зліт на 10 м, обліт стовпа, посадка; не ближче ніж 2 м до стовпа, висота в допуску». Запуск без графіки, перевірка через MAVLink і лог, результат — pass/fail для CI (модуль «Конфігурації в CI»). Один сценарій на кожну функцію безпеки (failsafe, геозона, RTL) ловить регресії під час оновлення прошивки й параметрів скоріше, ніж поле.

{{diagram:gazebo-sitl|Gazebo рахує фізику й датчики, плагін обмінюється із SITL через JSON у lockstep; зображення йдуть у ROS 2 через ros_gz_bridge, наземна станція й тести підключаються до SITL через MAVLink.}}

## practice
### Крок 1. Iris у Gazebo
Встановити Gazebo Harmonic і зібрати `ardupilot_gazebo` за README (залежності, `cmake`, `make`), виставити `GZ_SIM_SYSTEM_PLUGIN_PATH` і `GZ_SIM_RESOURCE_PATH`. Запустити `iris_runway.sdf` і SITL з `-f gazebo-iris --model JSON`. Зліт у GUIDED на 10 м з MAVProxy. Записати RTF під час зависання.

### Крок 2. Свій світ зі стовпом
Скопіювати `iris_runway.sdf` у свій світ, додати стовп із теорії. Місія: зліт, точка за 20 м на схід на висоті 5 м, повернення. Що ся діє з апаратом без обходу перешкод? Перенести точку так, щоб маршрут проходив за 3 м від стовпа.

### Крок 3. Камера в ROS 2
Запустити світ із камерою (`gimbal.sdf` або модель із камерою), знайти топік зображення (`gz topic -l`), підняти міст у ROS 2 і перевірити `ros2 topic hz` та `rqt_image_view` (або `ros2 run image_tools showimage`). Записати частоту кадрів і роздільну здатність.

### Крок 4. Сценарний тест
pytest-сценарій проти SITL (Gazebo без графіки: `gz sim -s -r мир.sdf`):
```python
import time
from pymavlink import mavutil

def test_takeoff_hold_land():
    m = mavutil.mavlink_connection("udpin:0.0.0.0:14550")
    m.wait_heartbeat(timeout=30)
    m.set_mode("GUIDED")
    deadline = time.time() + 60
    while not m.motors_armed():                    # pre-arm checks pass once EKF and GPS are ready
        assert time.time() < deadline, "не армиться за 60 с"
        m.arducopter_arm()
        m.recv_match(type="HEARTBEAT", blocking=True, timeout=2)
    m.mav.command_long_send(m.target_system, m.target_component,
                            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, 10)
    alts, t0 = [], time.time()
    while time.time() - t0 < 30:
        p = m.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=2)
        if p:
            alts.append(p.relative_alt / 1000)
    assert max(alts) > 9.0, f"не набрав висоту: {max(alts):.1f} м"
    assert abs(alts[-1] - 10) < 1.0, f"не тримає висоту: {alts[-1]:.1f} м"
    m.set_mode("LAND")
```
Додати другий тест: геозона (`FENCE_ENABLE = 1`, радіус 50 м) і політ у точку за нею — апарат мусить перейти до дії геозони. Записати час прогону кожного тесту.

Лабораторна зараховується, коли Iris літає в Gazebo з виміряним RTF, свій світ зі стовпом завантажується, зображення з камери видно в ROS 2 з виміряною частотою, два сценарні тести проходять без графіки.

## diagnostics
- **Симптом:** SITL не бачить Gazebo, апарат «висить» на землі
  - Можлива причина: не виставлено `GZ_SIM_SYSTEM_PLUGIN_PATH`, плагін не зібрано, фрейм без `gazebo-` або модель не `JSON`.
  - Що зробити: перевірити змінні, збірку плагіна, аргументи `sim_vehicle.py`.
- **Симптом:** світ не знаходить моделі
  - Можлива причина: не виставлено `GZ_SIM_RESOURCE_PATH`.
  - Що зробити: додати шляхи `models` і `worlds`.
- **Симптом:** симуляція йде повільніше за реальний час
  - Можлива причина: камери й лідари на слабкій машині, дрібний крок фізики, рендеринг у вікні.
  - Що зробити: сервер без графіки, менше датчиків і нижча роздільна здатність, `--headless-rendering` для камер.
- **Симптом:** ros_gz_bridge запущено, а топіка в ROS 2 нема
  - Можлива причина: хибне ім'я топіка або тип, розбіжність версій ROS 2 і Gazebo.
  - Що зробити: `gz topic -l` і `gz topic -i`, точне ім'я й тип, рекомендована пара версій.
- **Симптом:** алгоритм зору файно працює в симуляції й погано в полі
  - Можлива причина: ідеальна картинка без шуму, розмиття й зміни освітлення.
  - Що зробити: шум датчика в SDF, різне освітлення й текстури, перевірка на записаних реальних даних.

## references
- ArduPilot — ardupilot_gazebo plugin (README) | https://github.com/ArduPilot/ardupilot_gazebo | primary | A
- ArduPilot — Using SITL with Gazebo | https://ardupilot.org/dev/docs/sitl-with-gazebo.html | primary | A
- PX4 — Gazebo simulation | https://docs.px4.io/main/en/sim_gazebo_gz/ | primary | A
- Gazebo — documentation (Harmonic) | https://gazebosim.org/docs/harmonic/getstarted/ | primary | A
- ros_gz — ROS 2 ↔ Gazebo bridge | https://github.com/gazebosim/ros_gz | primary | A

## checklist
- Вибираю версію Gazebo в парі з ROS 2 і не плутаю з Gazebo Classic
- Запускаю ArduPilot і PX4 SITL з Gazebo
- Описую світ і моделі на SDF і додаю перешкоди
- Передаю зображення камери в ROS 2 через ros_gz_bridge
- Пишу сценарні тести, які йдуть без графіки в CI
- Пояснюю різницю між SITL і HITL
