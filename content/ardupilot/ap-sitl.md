---
id: ap-sitl
title: "SITL: дрон без дрона"
level: L2
readingTime: 25 мин
firmware: ArduPilot 4.5+
status: published
added: 2026-11-07
tags:
  - SITL
  - pymavlink
  - симуляция
related:
  - ap-intro
  - ap-lua
next:
  - ap-missions
---

## summary
SITL (Software In The Loop) — настоящая прошивка ArduPilot, запущенная на компьютере вместо полётного контроллера, с симулятором физики вместо реального мира. Здесь можно бесплатно разбить сотню октокоптеров: перепутать параметры, выключить GPS в полёте, уронить мотор. Модуль показывает, как поднять SITL, подключить наземную станцию, управлять дроном скриптом на Python и организовать проект так, чтобы маршруты и сценарии жили отдельно.

## theory
### Как устроен SITL
Прошивка собирается под Linux и обменивается с симулятором физики «показаниями датчиков» и «командами моторам». Всё остальное — настоящее: те же параметры, режимы, EKF, failsafe, логи. Поэтому всё, что ты отладил в SITL, переносится на железо почти без изменений. Почти — потому что в симуляции идеальные вибрации, идеальная связь и честный GPS, если ты не испортишь их сам.

### sim_vehicle.py и MAVProxy
Скрипт `sim_vehicle.py` собирает прошивку, запускает её и консольную наземную станцию MAVProxy. Ключевые флаги:

- `-v ArduCopter` или `-v ArduPlane` — тип аппарата;
- `-f octaquad`, `-f quad`, `-f quadplane` — модель рамы в симуляторе;
- `--console --map` — окна консоли и карты;
- `-w` — сбросить параметры к дефолтам (полезно, когда эксперименты зашли не туда).

Наземную станцию (QGroundControl, Mission Planner) подключают к выходу MAVProxy по UDP — обычно она находит его сама.

### Сценарий против маршрута
Главное архитектурное решение в учебном проекте: маршрут и сценарий живут раздельно.

- **Маршрут** — только последовательность точек в одном формате. Первая точка — старт, последняя — финиш.
- **Сценарий** — только команды: взлёт, «пролети маршрут X», посадка, отказ мотора на третьей точке. Координат в сценарии нет.

Так один маршрут прогоняется разными сценариями, а один сценарий — по разным маршрутам. Это та же идея, что разделение данных и логики в любом нормальном коде.

## practice
### Шаг 1. Установка (Ubuntu)
```
git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git
cd ardupilot
Tools/environment_install/install-prereqs-ubuntu.sh -y
. ~/.profile
```

### Шаг 2. Первый запуск
```
sim_vehicle.py -v ArduCopter -f octaquad --console --map -w
```

В консоли MAVProxy:

```
mode guided
arm throttle
takeoff 10
```

Дрон взлетит на 10 м. `mode rtl` вернёт его домой.

### Шаг 3. Управление скриптом (pymavlink)
SITL открывает дополнительные TCP-порты для внешних клиентов. Пример взлёта скриптом:

```python
from pymavlink import mavutil

master = mavutil.mavlink_connection("tcp:127.0.0.1:5762")
master.wait_heartbeat()
print("connected to system", master.target_system)

master.set_mode(master.mode_mapping()["GUIDED"])
master.arducopter_arm()
master.motors_armed_wait()

master.mav.command_long_send(
    master.target_system, master.target_component,
    mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
    0, 0, 0, 0, 0, 0, 0, 10,  # param7 = altitude, m
)

while True:
    msg = master.recv_match(type="GLOBAL_POSITION_INT", blocking=True)
    alt = msg.relative_alt / 1000
    print(f"alt {alt:.1f} m")
    if alt > 9.5:
        break
```

### Шаг 4. Структура проекта
```
ardupilot-lab/
  sitl/
    lib/          # shared code: connection, waiting for modes, helpers
    routes/       # data only: lists of waypoints, one format everywhere
    scenarios/    # commands only: takeoff, fly route X, inject failure, land
    run_sitl.sh   # start SITL + GCS with the right frame
```

### Лабораторная
Напиши сценарий «взлёт → круг → посадка» так, чтобы координаты лежали в `routes/`, а сценарий просто ссылался на маршрут. Прогони его на двух разных маршрутах без правки кода сценария.

## diagnostics
- **Симптом:** `sim_vehicle.py: command not found`
  - Возможная причина: не перечитан профиль после установки.
  - Что сделать: `. ~/.profile` или новый терминал.
- **Симптом:** скрипт висит на `wait_heartbeat`
  - Возможная причина: неверный адрес или порт, SITL не запущен.
  - Что сделать: проверить, что SITL работает, и номер порта.
- **Симптом:** `arm throttle` отказывает с `PreArm`
  - Возможная причина: EKF ещё не сошёлся после старта.
  - Что сделать: подождать 10–20 с после запуска, читать сообщение PreArm.
- **Симптом:** после экспериментов дрон ведёт себя странно
  - Возможная причина: остались изменённые параметры.
  - Что сделать: перезапуск с `-w` для сброса.

## references
- Setting up SITL on Linux — ArduPilot Dev | https://ardupilot.org/dev/docs/setting-up-sitl-on-linux.html | primary | A
- Setting Up SITL — ArduPilot Dev | https://ardupilot.org/dev/docs/SITL-setup-landingpage.html | primary | A
- pymavlink — source code (GitHub) | https://github.com/ArduPilot/pymavlink | primary | A

## checklist
- SITL запускается, GCS подключена
- Взлёт и RTL выполнены из консоли MAVProxy
- Скрипт на pymavlink поднимает дрон
- Маршруты и сценарии разнесены по разным папкам
- Знаю, как сбросить параметры SITL
