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
- `-f octa-quad`, `-f quad`, `-f quadplane` — модель рамы в симуляторе;
- `--console --map` — окна консоли и карты;
- `-w` — сбросить параметры к дефолтам (полезно, когда эксперименты зашли не туда).

Наземную станцию (QGroundControl, Mission Planner) подключают к выходу MAVProxy по UDP — обычно она находит его сама.

### Сценарий против маршрута
Главное архитектурное решение в учебном проекте: маршрут и сценарий живут раздельно.

- **Маршрут** — только последовательность точек в одном формате. Первая точка — старт, последняя — финиш.
- **Сценарий** — только команды: взлёт, «пролети маршрут X», посадка, отказ мотора на третьей точке. Координат в сценарии нет.

Так один маршрут прогоняется разными сценариями, а один сценарий — по разным маршрутам. Это та же идея, что разделение данных и логики в любом нормальном коде.

### Что умеет SITL кроме «полетать»
- **Модели рам** (`-f`): quad, hexa, octa, octa-quad (X8), y6, tri, heli, plane, quadplane, quadplane-tilttri/quadplane-tilt (тилтроторы), rover, boat, sub — у каждой своя физика в `libraries/SITL/SIM_*.cpp`; параметры по умолчанию для модели — `Tools/autotest/default_params/*.parm`.
- **Отказы и среда** через `SIM_*`: ветер (`SIM_WIND_SPD/DIR/TURB`), отказ мотора (`SIM_ENGINE_FAIL` + `SIM_ENGINE_MUL`), GPS (выключение, шум, глитч, задержка), компас (смещение), баро (дрейф/глитч), вибрации (`SIM_VIB_*`), потеря RC (`SIM_RC_FAIL`), напряжение АКБ (`SIM_BATT_VOLTAGE`), дальномер и оптический поток (`RNGFND1_TYPE = 100`, `FLOW_TYPE = 10`). Это основа модулей «Отказоустойчивость» и «Устойчивость навигации».
- **Ускорение времени** `--speedup 10` для длинных миссий; `--add-param-file` для своих параметров; `--out=udp:IP:14550` для внешней GCS; `--no-mavproxy` для скриптов.
- **Внешние физические движки**: Gazebo (`-f gazebo-iris`), RealFlight, X-Plane, JSBSim (крыло), Webots — когда нужна аэродинамика/визуализация; для логики failsafe и миссий встроенной физики достаточно.
- **Lua и companion**: скрипты (`SCR_ENABLE = 1`, папка `scripts/` рядом с запуском) и MAVLink-клиенты (`tcp:127.0.0.1:5760`, следующие — 5762/5763) работают как на железе.

### Логи SITL и их чтение
Логи пишутся в `logs/` рабочей папки (`.BIN`), читаются теми же инструментами, что реальные (`mavexplorer.py`, Mission Planner, `pymavlink` — модуль «Python для данных»). Это и есть смысл SITL: отрабатывать **метод** анализа до реальных полётов.

### Разобранный пример: проверка миссии с отказом
`sim_vehicle.py -v ArduCopter -f hexa --console --map --speedup 5`; загрузить миссию (`wp load mission.txt`), `mode auto`, `arm throttle`; на третьей точке `param set SIM_ENGINE_FAIL 4` (мотор 3, битовая маска), наблюдать `RCOU`, высоту, рыскание; вернуть `0`; далее `param set SIM_RC_FAIL 1` в Loiter — проверить `FS_THR_ENABLE`. Результат — в журнал тестов (модуль «Отказоустойчивость»): сценарий, ожидание, факт, лог. Сценарий можно записать как скрипт pymavlink — заготовка в `examples/sitl-pymavlink` репозитория курса.

### Где SITL врёт
Нет вибраций и шума моторов (фильтры не проверить), идеальная механика, ESC без задержек, GPS с заданным шумом, нет помех на компас кроме смоделированных. Параметры тюнинга PID из SITL **не переносятся** на реальный аппарат; переносятся логика, миссии, скрипты, failsafe и навыки анализа.

{{diagram:sitl-arch|SITL: тот же код ArduCopter получает сенсоры от модели физики; MAVProxy раздаёт MAVLink на GCS и скрипты, логи пишутся как в полёте.}}

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
sim_vehicle.py -v ArduCopter -f octa-quad --console --map -w
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

### Что должно получиться и что записать
- **Шаг 1.** Установка занимает 10–30 минут. После неё в новом терминале должна находиться команда `sim_vehicle.py`. Если её нет, значит, не перечитан `~/.profile`.
- **Шаг 2.** Первая сборка идёт несколько минут, следующие запуски — секунды. В консоли видно, как GPS получает фиксацию и EKF начинает использовать GPS, после этого арм проходит. Арм раньше этого момента отклоняется сообщением `PreArm`, и это нормально. `takeoff 10` поднимает аппарат на 10 м. После `mode rtl` он сначала набирает высоту возврата `RTL_ALT` (в Copter 4.7 — `RTL_ALT_M`; по умолчанию 15 м), если находится ниже, и только потом летит домой. Запиши время набора 10 м и итоговую высоту перед возвратом: так проверяется, что параметры работают так, как ты их понимаешь.
- **Шаг 3.** Порты SITL: 5760 — SERIAL0, его занимает MAVProxy; 5762 и 5763 — SERIAL1 и SERIAL2 для своих клиентов. Скрипт печатает растущую высоту и выходит на 9.5 м. Добавь вывод времени от команды до выхода — это первая метрика сценария.
- **Шаг 4.** Маршрут — данные, сценарий — код. Пример маршрута `routes/square_20m.csv`, строки `north_m,east_m,alt_m` относительно точки взлёта:

```text
20,0,10
20,20,10
0,20,10
0,0,10
```

Сценарий читает файл, переводит смещения в цели GUIDED и ждёт прихода в радиус 1 м. Второй маршрут — тот же формат с другими числами.

### Лабораторная
Напиши сценарий «взлёт → круг → посадка» так, чтобы координаты лежали в `routes/`, а сценарий просто ссылался на маршрут. Прогони его на двух разных маршрутах без правки кода сценария.

Лабораторная засчитывается, когда SITL запускается скриптом `run_sitl.sh` с нужной рамой и наземка подключена, сценарий на pymavlink взлетает, проходит маршрут и садится, маршруты лежат в `routes/` отдельно от сценариев, а два маршрута прогнаны одним и тем же кодом с записанным временем прохождения.

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
- **Симптом:** sim_vehicle.py не стартует / «waf configure» ошибки
  - Возможная причина: не установлены зависимости.
  - Что сделать: `Tools/environment_install/install-prereqs-ubuntu.sh -y`, перелогиниться, `git submodule update --init --recursive`.
- **Симптом:** GCS не подключается к SITL
  - Возможная причина: порты заняты, MAVProxy не пробрасывает.
  - Что сделать: `--out=udp:127.0.0.1:14550` явно, проверить `ss -lunp`.

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
