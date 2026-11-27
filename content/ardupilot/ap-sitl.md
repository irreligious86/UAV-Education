---
id: ap-sitl
title: "SITL: дрон без дрона"
level: L2
readingTime: 35 мин
firmware: ArduPilot 4.7 (сверено с 4.7.3; лабораторная снята на SITL 4.7.2)
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

Технически SITL — один процесс: бинарник `build/sitl/bin/arducopter` (собирается `./waf configure --board sitl && ./waf copter`) содержит и прошивку, и встроенную модель аппарата, выбранную ключом `--model`. Модель и прошивка шагают по общим часам (lockstep): модель считает физику с частотой `SIM_RATE_HZ` (по умолчанию 1200 Гц на SITL, `libraries/SITL/SITL.cpp:47`), прошивка — свой основной цикл с частотой `SCHED_LOOP_RATE` (400 Гц у Copter) по тем же симулированным часам: примерно три шага физики на цикл прошивки. Прошивка читает «датчики» модели, отдаёт ШИМ моторам, модель превращает ШИМ в тягу. Отсюда главное свойство: время в SITL — **симулированное**. Его можно ускорить, и тогда минута полёта проходит за 6 секунд, но только если компьютер успевает считать.

### Запуск: sim_vehicle.py или бинарник напрямую
`sim_vehicle.py` — обёртка на Python: собирает прошивку, подбирает файлы параметров для рамы, запускает бинарник и MAVProxy. Для рамы `-f octa-quad` она передаёт бинарнику `--defaults copter.parm,copter-octaquad.parm` (таблица рам — `Tools/autotest/pysim/vehicleinfo.py`), для `-f hexa` — `copter.parm,copter-hexa.parm`, для `+`/`quad` — только `copter.parm`. Стартовая точка по умолчанию — аэродром CMAC в Канберре: `SIM_OPOS_LAT/LNG/ALT` = −35.363261, 149.165230, 584 м — то же, что строка `CMAC` в `Tools/autotest/locations.txt` (`-35.363261,149.165230,584,353`: широта, долгота, высота над уровнем моря в метрах, курс в градусах). Другая точка — `-L <имя>` из того же файла или `--home lat,lon,alt,hdg` у бинарника.

Для автотестов и CI бинарник удобнее запускать напрямую, без MAVProxy: меньше процессов, полный контроль над флагами, а скрипт на pymavlink сам становится наземкой. Команда, которой пользуется практика этого модуля:

```
build/sitl/bin/arducopter --model + --speedup 10 -w \
  --defaults Tools/autotest/default_params/copter.parm,lab.parm \
  --home -35.363261,149.165230,584,353
```

### Слои параметров: кто кого перебивает
Параметр в SITL получает значение из четырёх слоёв, и почти все «странности» симулятора — это забытый слой.

1. Значение по умолчанию в коде прошивки (`AP_GROUPINFO`).
2. Файлы `--defaults` слева направо: каждый следующий перебивает предыдущий. `sim_vehicle.py --add-param-file my.parm` дописывает файл в конец этого списка.
3. Сохранённые значения в `eeprom.bin` в рабочей папке: всё, что ты менял через `param set`, лежит там и **перебивает** defaults при следующем запуске.
4. `param set` в текущем сеансе — сразу пишется в слой 3.

Ключ `-w` (`--wipe`) стирает `eeprom.bin` при старте, и тогда работают только слои 1–2. Вывод из этого порядка: если правишь `lab.parm`, а значение не меняется, в `eeprom.bin` лежит старое — запускай с `-w` или удаляй файл. И наоборот: чтобы сохранить настройки между запусками (как в лабораторной по Lua ниже), запускай без `-w` из той же папки.

{{diagram:sitl-param-layers|Слои параметров SITL: файл defaults задаёт значения по умолчанию, но eeprom.bin их перебивает; -w стирает eeprom.bin, иначе правка .parm может не подействовать.}}

### Порты и несколько аппаратов
Последовательные порты прошивки в SITL превращены в TCP-сокеты (`libraries/AP_HAL_SITL/SITL_State.h:33`): SERIAL0 — `tcp:0:wait`, порт 5760, и прошивка **ждёт** клиента на нём перед стартом; SERIAL1 — 5762, SERIAL2 — 5763; SERIAL3 и SERIAL4 заняты симулированными GPS1/GPS2; SERIAL5…SERIAL8 — 5765…5768. Ключ `-I N` (`--instance`) сдвигает базовый порт на 10·N (`SITL_cmdline.cpp:438`): второй аппарат с `-I 1` слушает 5770, 5772, 5773. Так поднимают рой из 2–3 аппаратов на одной машине (`sim_vehicle.py -n 3` делает это сам). MAVProxy держит 5760 и раздаёт поток дальше по UDP (`--out=udp:IP:14550`); без MAVProxy к 5760 подключается твой скрипт.

### Время и ускорение
`--speedup N` записывает параметр `SIM_SPEEDUP` (по умолчанию 1). В прогоне практики на `--speedup 10` за 10.1 с реального времени прошло 101 с симулированного — ровно 10×. Правило для скриптов: все интервалы и таймауты считай по времени прошивки (`time_boot_ms` в `SYSTEM_TIME`, `GLOBAL_POSITION_INT`), а не по `time.time()` компьютера. Сценарий «подожди 20 с» на `time.sleep(20)` при ускорении 10× ждёт 200 с симулированных. Если компьютер не успевает, реальное ускорение будет меньше заданного — потому его и стоит измерять, как в шаге 5.

### sim_vehicle.py и MAVProxy
Скрипт `sim_vehicle.py` собирает прошивку, запускает её и консольную наземную станцию MAVProxy. Ключевые флаги:

- `-v ArduCopter` или `-v ArduPlane` — тип аппарата;
- `-f octa-quad`, `-f quad`, `-f quadplane` — модель рамы в симуляторе (`-f quad` и запуск без `-f` — это Quad Plus, `FRAME_TYPE = 0`; Quad X — `-f X`);
- `--console --map` — окна консоли и карты;
- `-w` — сбросить параметры к дефолтам (полезно, когда эксперименты зашли не туда).

Наземную станцию (QGroundControl, Mission Planner) подключают к выходу MAVProxy по UDP — обычно она находит его сама.

### Сценарий против маршрута
Главное архитектурное решение в учебном проекте (ориентир курса): маршрут и сценарий живут раздельно.

- **Маршрут** — только последовательность точек в одном формате. Первая точка — старт, последняя — финиш.
- **Сценарий** — только команды: взлёт, «пролети маршрут X», посадка, отказ мотора на третьей точке. Координат в сценарии нет.

Так один маршрут прогоняется разными сценариями, а один сценарий — по разным маршрутам. Это та же идея, что разделение данных и логики в любом нормальном коде.

### Что умеет SITL кроме «полетать»
- **Модели рам** (`-f`): quad, hexa, octa, octa-quad (X8), y6, tri, heli, plane, quadplane, quadplane-tilttri/quadplane-tilt (тилтроторы), rover, motorboat, sailboat (Rover), vectored (Sub) — у каждой своя физика в `libraries/SITL/SIM_*.cpp`; параметры по умолчанию для модели — `Tools/autotest/default_params/*.parm`.
- **Отказы и среда** через `SIM_*`: ветер (`SIM_WIND_SPD/DIR/TURB`), отказ мотора (`SIM_ENGINE_FAIL` + `SIM_ENGINE_MUL`), GPS (выключение, шум, глитч, задержка), компас (смещение), баро (дрейф/глитч), вибрации (`SIM_VIB_*`), потеря RC (`SIM_RC_FAIL`), напряжение АКБ (`SIM_BATT_VOLTAGE`), дальномер и оптический поток (`RNGFND1_TYPE = 100`, `FLOW_TYPE = 10`). Это основа модулей «Отказоустойчивость» и «Устойчивость навигации».
- **Ускорение времени** `--speedup 10` для длинных миссий; `--add-param-file` для своих параметров; `--out=udp:IP:14550` для внешней GCS; `--no-mavproxy` для скриптов.
- **Внешние физические движки**: Gazebo (`-f gazebo-iris`), RealFlight, X-Plane, JSBSim (крыло), Webots — когда нужна аэродинамика/визуализация; для логики failsafe и миссий встроенной физики достаточно.
- **Lua и companion**: скрипты (`SCR_ENABLE = 1`, папка `scripts/` рядом с запуском) и MAVLink-клиенты (`tcp:127.0.0.1:5760`, следующие — 5762/5763) работают как на железе.

{{lesson:ap-lua|Fault injection скриптом: отказ мотора по таймеру или тумблеру через те же SIM_ENGINE_FAIL/SIM_ENGINE_MUL.}}

### Справочник: ключи запуска и параметры SIM_* (ArduCopter 4.7.2)
Имена и значения по умолчанию сверены с исходниками тега Copter-4.7.2: ключи — `libraries/AP_HAL_SITL/SITL_cmdline.cpp:327–386` и `Tools/autotest/sim_vehicle.py`, параметры — `libraries/SITL/SITL.cpp`, `libraries/SITL/SIM_GPS.cpp`. В MAVProxy полный список своей сборки — `param show SIM_*`.

| Ключ / параметр | По умолчанию | Что делает | Как использовать |
|---|---|---|---|
| `--model` (бинарник), `-f` (sim_vehicle) | — | модель рамы: `+`, `X`, `hexa`, `octa-quad`, `quadplane`… | `-f` ещё и подбирает файлы `--defaults` |
| `--defaults a.parm,b.parm` | — | значения по умолчанию, правый файл перебивает левый | свой `lab.parm` в конце списка |
| `-w` / `--wipe` | выкл. | стереть `eeprom.bin` при старте | правка `.parm` не подействовала — запусти с `-w` |
| `--speedup N` (бинарник: `-s N`; sim_vehicle.py: `-S N`) | 1 | пишет `SIM_SPEEDUP` | 10 для длинных миссий; измеряй реальное |
| `--home lat,lon,alt,hdg`, `-L имя` | CMAC | точка старта | своя площадка для миссий |
| `-I N` / `--instance` | 0 | базовый порт + 10·N | несколько аппаратов |
| `SIM_WIND_SPD`, м/с | 0 | скорость ветра | 5–10 м/с для проверки удержания |
| `SIM_WIND_DIR`, ° | 180 | откуда дует ветер | 0 — с севера |
| `SIM_WIND_TURB`, м/с | 0 | турбулентность | 2–3 м/с поверх ветра |
| `SIM_ENGINE_FAIL` | 0 | битовая маска моторов: бит 0 — мотор 1 | 1 → мотор 1, 4 → мотор 3 |
| `SIM_ENGINE_MUL` | 0 | множитель тяги моторов из маски, 0…1 | 0 — полный отказ, 0.5 — половина тяги |
| `SIM_RC_FAIL` | 0 | 0 — норма, 1 — нет импульсов RC, 2 — все каналы в нейтрали, газ 950 мкс | проверка `FS_THR_ENABLE` |
| `SIM_GPS1_ENABLE` | 1 (см. ниже) | 0 — GPS1 пропадает | потеря GPS в полёте |
| `SIM_GPS1_NUMSATS` | 10 | число спутников | 5 — ниже порога арма |
| `SIM_GPS1_GLTCH_X/Y/Z` | 0 | скачок позиции GPS | проверка реакции EKF на глитч |
| `SIM_GPS1_LAG_MS`, мс | 100 | задержка GPS | |
| `SIM_BATT_VOLTAGE`, В | 12.6 | напряжение модели АКБ | проверка `BATT_FS_*` |
| `SIM_VIB_FREQ_X/Y/Z`, Гц | 0 | синусоидальная вибрация IMU | проверка фильтров на форме, не на числах |
| `SIM_ESC_TELEM` | 1 | телеметрия ESC в модели | для Lua `esc_telem:*` |
| `SIM_RATE_HZ`, Гц | 1200 | частота шага физики | не трогать без причины |

Примечание: в таблице параметров `SIM_GPS1_ENABLE` по умолчанию 0, но симулятор GPS сам ставит 1 для первого приёмника, если параметр не задан явно (`libraries/SITL/SIM_GPS.cpp:177`); в выводе шага 5 он читается как 1.

### Ловушка, которую показывает SITL: конус RTL
Copter не всегда набирает `RTL_ALT_M` перед возвратом. Код `ArduCopter/mode_rtl.cpp:546–555` считает высоту возврата так (`RTL_CLIMB_MIN_M = 0`, по умолчанию):

h_ret = min( max(`RTL_ALT_M`, h), max(d · `RTL_CONE_SLOPE`, h) ),

где h — текущая высота, d — горизонтальное расстояние до дома, `RTL_CONE_SLOPE` = 3 по умолчанию (меньше 0.5 — конус выключен). Прямо над домом d = 0, и h_ret = h: аппарат на 10 м не поднимется до 20 м — повисит над домом `RTL_LOIT_TIME` (5000 мс по умолчанию) и сядет с текущей высоты. В 40.7 м от дома конус даёт 122 м, ограничивает `RTL_ALT_M` = 20 — и аппарат набирает 20 м. Оба случая прогнаны в шаге 5. До Copter 4.7 параметр назывался `RTL_ALT` и задавался в сантиметрах.

### Логи SITL и их чтение
Логи пишутся в `logs/` рабочей папки (`.BIN`), читаются теми же инструментами, что реальные (`mavexplorer.py`, Mission Planner, `pymavlink` — модуль «Python для данных»). Это и есть смысл SITL: отрабатывать **метод** анализа до реальных полётов.

### Разобранный пример: проверка миссии с отказом
`sim_vehicle.py -v ArduCopter -f hexa --console --map --speedup 5`; загрузить миссию (`wp load mission.txt`), `mode auto`, `arm throttle`; на третьей точке `param set SIM_ENGINE_FAIL 4` (мотор 3, битовая маска), наблюдать `RCOU`, высоту, рыскание; вернуть `0`; далее `param set SIM_RC_FAIL 1` в Loiter — проверить `FS_THR_ENABLE`. Результат — в журнал тестов (модуль «Отказоустойчивость»): сценарий, ожидание, факт, лог. Сценарий можно записать как скрипт pymavlink — заготовка в `examples/sitl-pymavlink` репозитория курса.

### Где SITL врёт
Нет вибраций и шума моторов, пока их не включить через `SIM_VIB_*` — и даже тогда это синусоида заданной частоты, а не спектр твоей рамы (фильтры по SITL не настроить), идеальная механика, ESC без задержек, GPS с заданным шумом, нет помех на компас кроме смоделированных. Параметры тюнинга PID из SITL **не переносятся** на реальный аппарат; переносятся логика, миссии, скрипты, failsafe и навыки анализа.

{{diagram:sitl-arch|SITL: тот же код ArduCopter получает сенсоры от модели физики; MAVProxy раздаёт MAVLink на GCS и скрипты, логи пишутся как в полёте.}}

### Место в системе

- **Получает:** ту же прошивку, параметры и файл миссии (`ap-missions`); Lua-скрипты (`ap-lua`) и MAVLink-клиенты companion (`ap-companion`); при необходимости — внешнюю физику и камеры (`tools-gazebo`).
- **Отдаёт:** проверенную логику failsafe и журнал тестов (`ap-safety-fs`); логи `.BIN` для отработки метода анализа (`ap-logs`, `data-python`); автотест для CI (`eng-ci-configs`).
- **Если ошибиться здесь:** перенёс PID и фильтры из SITL на реальный аппарат → в симуляции нет вибраций и шума моторов, значения не подходят; тюнинг делается по реальным логам (`ap-tuning`). Не испортил GPS и связь сам → failsafe «прошёл» на идеальных датчиках, а в поле деградация выглядит иначе (`nav-resilience`).

## practice
### Шаг 1. Установка (Ubuntu)
```
git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git
cd ardupilot
Tools/environment_install/install-prereqs-ubuntu.sh -y
. ~/.profile
```

Клон по умолчанию стоит на ветке `master` — это разработка следующего выпуска, имена параметров в ней могут уже отличаться от курса. Чтобы симулятор совпадал с модулями, переключись на стабильный тег: `git checkout Copter-4.7.3`, затем `git submodule update --init --recursive`. Выводы ниже сняты на `Copter-4.7.2`; в 4.7.3 для этих шагов ничего не меняется (отличия выпусков — в `ap-intro`).

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

# Copter streams on SERIAL1 are off by default (MAV2_* = 0): ask for GLOBAL_POSITION_INT at 5 Hz
master.mav.command_long_send(
    master.target_system, master.target_component,
    mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
    mavutil.mavlink.MAVLINK_MSG_ID_GLOBAL_POSITION_INT, 200000, 0, 0, 0, 0, 0)

master.set_mode(master.mode_mapping()["GUIDED"])
while not master.motors_armed():      # PreArm refuses until the EKF uses GPS: retry
    master.arducopter_arm()
    master.recv_match(type="HEARTBEAT", blocking=True)
    master.recv_match(type="HEARTBEAT", blocking=True)

master.mav.command_long_send(
    master.target_system, master.target_component,
    mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
    0, 0, 0, 0, 0, 0, 0, 10,  # param7 = altitude, m
)

t0 = None
while True:
    msg = master.recv_match(type="GLOBAL_POSITION_INT", blocking=True)
    t0 = t0 or msg.time_boot_ms
    alt = msg.relative_alt / 1000
    if alt > 9.5:
        print(f"alt {alt:.1f} m after {(msg.time_boot_ms - t0) / 1000:.1f} s (sim time)")
        break
```

Вывод при запуске рядом с MAVProxy на 5760 (SITL 4.7.2, `--speedup 10`):

```text
connected to system 1
alt 9.5 m after 6.6 s (sim time)
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

### Шаг 5. Слои параметров, ускорение, ветер и потеря RC — одним скриптом
Этот шаг прогнан на ArduCopter 4.7.2 (бинарник собран из тега `Copter-4.7.2`, pymavlink 2.4.50) без MAVProxy: скрипт сам запускает SITL, подключается к SERIAL0 (5760) и делает пять проверок. Слой `lab.parm` ставит `RTL_ALT_M 20` поверх `copter.parm`; ускорение измеряется по `time_boot_ms`; ветер 8 м/с с севера включается на лету; RTL проверяется дважды — прямо над домом и в 40 м от него, второй раз через имитацию потери пульта `SIM_RC_FAIL = 1`. Запуск: `mkdir run && cd run && python3 ../sitl_lab.py ~/ardupilot`, прогон занимает около 1.5 мин реального времени.

```python
"""SITL lab: layered defaults, speedup, wind and RC-loss injection (ArduCopter 4.7.2, no MAVProxy).
Usage: python3 sitl_lab.py ~/ardupilot   (run from an empty folder; logs/ and eeprom.bin appear here)"""
import math, subprocess, sys, time
from pymavlink import mavutil

AP = sys.argv[1]
open("lab.parm", "w").write("RTL_ALT_M 20\n")          # applied after copter.parm, so it wins
sitl = subprocess.Popen([AP + "/build/sitl/bin/arducopter", "--model", "+", "--speedup", "10", "-w",
                         "--defaults", AP + "/Tools/autotest/default_params/copter.parm,lab.parm",
                         "--home", "-35.363261,149.165230,584,353"], stdout=open("sitl.out", "w"), stderr=subprocess.STDOUT)
time.sleep(1)
m = mavutil.mavlink_connection("tcp:127.0.0.1:5760")   # SERIAL0 waits for this client
m.wait_heartbeat()
for name in ("GLOBAL_POSITION_INT", "ATTITUDE", "LOCAL_POSITION_NED"):   # 10 Hz each
    m.mav.command_long_send(1, 1, mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
                            getattr(mavutil.mavlink, "MAVLINK_MSG_ID_" + name), 100000, 0, 0, 0, 0, 0)


def param(name, value=None):
    if value is None:
        m.mav.param_request_read_send(1, 1, name.encode(), -1)
    else:
        m.param_set_send(name, value)
    while (r := m.recv_match(type="PARAM_VALUE", blocking=True)).param_id != name:
        pass
    return r.param_value


def sim_t():  # simulated seconds since boot, from a fresh message
    while m.recv_match(blocking=False):
        pass
    return m.recv_match(type="GLOBAL_POSITION_INT", blocking=True).time_boot_ms / 1000


def fly_until(test):  # read messages until test(msg) is true, return that message
    while not test(r := m.recv_match(blocking=True)):
        pass
    return r


def takeoff(alt):
    m.set_mode("GUIDED")
    while not m.motors_armed():      # PreArm refuses until the EKF uses GPS
        m.arducopter_arm()
        m.recv_match(type="HEARTBEAT", blocking=True); m.recv_match(type="HEARTBEAT", blocking=True)
    m.mav.command_long_send(1, 1, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, alt)
    fly_until(lambda r: r.get_type() == "GLOBAL_POSITION_INT" and r.relative_alt > (alt - 0.5) * 1000)


def mean_tilt(sec):
    t_end, tilt = sim_t() + sec, []
    while (r := m.recv_match(type=["ATTITUDE", "GLOBAL_POSITION_INT"], blocking=True)).time_boot_ms / 1000 < t_end:
        if r.get_type() == "ATTITUDE":
            tilt.append(math.degrees(math.hypot(r.roll, r.pitch)))
    return sum(tilt) / len(tilt)


def rtl_max_alt():  # watch RTL until disarm, return the highest altitude
    top = 0
    while (r := m.recv_match(type=["GLOBAL_POSITION_INT", "HEARTBEAT"], blocking=True)):
        if r.get_type() == "GLOBAL_POSITION_INT":
            top = max(top, r.relative_alt / 1000)
        elif r.get_srcSystem() == 1 and not r.base_mode & 128 and top > 1:
            return top


for n in ("FS_THR_ENABLE", "RC_FS_TIMEOUT", "RTL_ALT_M", "RTL_CONE_SLOPE", "SIM_WIND_DIR", "SIM_GPS1_ENABLE"):
    print(f"{n} = {param(n):g}")
t0, w0 = sim_t(), time.time(); time.sleep(10)
print(f"speedup: {(sim_t() - t0) / (time.time() - w0):.1f}x")
takeoff(10)
print(f"airborne at sim t = {sim_t():.0f} s; calm: mean tilt {mean_tilt(10):.1f} deg")
param("SIM_WIND_DIR", 0); param("SIM_WIND_SPD", 8)                  # 8 m/s FROM the north
mean_tilt(5)                                                         # let the controller settle
print(f"wind 8 m/s: mean tilt {mean_tilt(15):.1f} deg")
param("SIM_WIND_SPD", 0)
m.set_mode("RTL")
print(f"A: RTL straight above home -> max alt {rtl_max_alt():.1f} m")
takeoff(10)
m.mav.set_position_target_local_ned_send(0, 1, 1, mavutil.mavlink.MAV_FRAME_LOCAL_NED, 0b110111111000,
                                         40, 0, -10, 0, 0, 0, 0, 0, 0, 0, 0)
pos = fly_until(lambda r: r.get_type() == "LOCAL_POSITION_NED" and abs(r.x - 40) < 1 and abs(r.vx) < 0.3)
t_fail = sim_t(); param("SIM_RC_FAIL", 1)
fly_until(lambda r: r.get_type() == "HEARTBEAT" and r.get_srcSystem() == 1 and r.custom_mode == 6)
print(f"B: {pos.x:.1f} m north, SIM_RC_FAIL=1 -> RTL after {sim_t() - t_fail:.1f} s, max alt {rtl_max_alt():.1f} m")
sitl.terminate()
```

Вывод прогона (2026-11-26):

```text
FS_THR_ENABLE = 1
RC_FS_TIMEOUT = 1
RTL_ALT_M = 20
RTL_CONE_SLOPE = 3
SIM_WIND_DIR = 180
SIM_GPS1_ENABLE = 1
speedup: 10.0x
airborne at sim t = 112 s; calm: mean tilt 0.3 deg
wind 8 m/s: mean tilt 6.5 deg
A: RTL straight above home -> max alt 10.0 m
B: 40.7 m north, SIM_RC_FAIL=1 -> RTL after 1.1 s, max alt 20.0 m
```

Что читать в выводе. `RTL_ALT_M = 20` — слой `lab.parm` перебил дефолт 15 м; `FS_THR_ENABLE = 1` и `RC_FS_TIMEOUT = 1` пришли из кода и `copter.parm`. Ускорение 10.0× совпало с заданным — машина успевает. Ветер 8 м/с наклонил аппарат в среднем на 6.5° против 0.3° в штиль: так выглядит удержание позиции против ветра. Случай A: RTL прямо над домом поднялся не выше 10.0 м — это конус, а не ошибка. Случай B: через 1.1 с после пропажи RC (таймаут `RC_FS_TIMEOUT` = 1 с) включился RTL, и аппарат поднялся до 20.0 м перед возвратом.

### Что должно получиться и что записать
- **Шаг 1.** Установка занимает 10–30 минут. После неё в новом терминале должна находиться команда `sim_vehicle.py`. Если её нет, значит, не перечитан `~/.profile`.
- **Шаг 2.** Первая сборка идёт несколько минут, следующие запуски — секунды. В консоли видно, как GPS получает фиксацию и EKF начинает использовать GPS, после этого арм проходит. Арм раньше этого момента отклоняется сообщением `PreArm`, и это нормально. `takeoff 10` поднимает аппарат на 10 м. После `mode rtl` прямо над точкой взлёта он **не** набирает `RTL_ALT_M` (до Copter 4.7 — `RTL_ALT`, см; по умолчанию 15 м), а садится с 10 м: конус RTL при d = 0 оставляет текущую высоту (см. теорию). Чтобы увидеть набор высоты, сначала отлети метров на 40 (в GUIDED — «Fly To Here» в GCS или командой `SET_POSITION_TARGET_LOCAL_NED`, как в шаге 5), затем `mode rtl` — аппарат поднимется до 15 м и только потом полетит домой. Запиши время набора 10 м и высоту в обоих случаях: так проверяется, что параметры работают так, как ты их понимаешь.
- **Шаг 3.** Порты SITL: 5760 — SERIAL0, его занимает MAVProxy; 5762 и 5763 — SERIAL1 и SERIAL2 для своих клиентов. Скрипт выходит на 9.5 м и печатает время подъёма по часам прошивки (в прогоне — 6.6 с) — первая метрика сценария. У Copter потоки на SERIAL1 по умолчанию выключены (`MAV2_POSITION = 0`; до 4.7 — `SR1_POSITION`), поэтому скрипт сначала запрашивает `GLOBAL_POSITION_INT` через `MAV_CMD_SET_MESSAGE_INTERVAL` — без этого `recv_match` ждёт вечно. Арм повторяется в цикле: пока EKF не использует GPS, PreArm отклоняет его, а `motors_armed_wait()` без повтора зависла бы навсегда.
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

Самопроверка: лабораторная выполнена, когда `run_sitl.sh` поднимает SITL с нужной рамой и наземка подключается без ручных команд, в шаге 2 `takeoff 10` дал 10 м, `mode rtl` над домом посадил аппарат с 10 м без набора, а в 40 м от дома — после набора до `RTL_ALT_M` (15 м по умолчанию), время и высоты записаны, шаг 5 у тебя печатает ускорение 10× ± 1 (если меньше — машина не успевает, это не ошибка скрипта), средний наклон при ветре 8 м/с в пределах 5–8° против меньше 1° в штиль, случай A — не выше 10.5 м, случай B — 20 ± 0.5 м и RTL через 1–1.5 с после `SIM_RC_FAIL = 1`, скрипт шага 3 сам выходит на 9.5 м и печатает время подъёма 5–9 с по часам прошивки (в прогоне 6.6 с), маршруты лежат в `routes/` в формате `north_m,east_m,alt_m`, а сценарий «взлёт → круг → посадка» прошёл два разных маршрута без единой правки кода сценария, приходя к каждой точке в радиус 1 м, — время прохождения каждого записано.

**Эталон для самопроверки.** Верный результат: чтобы сменить маршрут, меняется только имя файла из `routes/`. Типичные неверные: (1) скрипт шага 3 молчит и висит на `recv_match` — из кода выпал запрос `MAV_CMD_SET_MESSAGE_INTERVAL`, а у Copter поток `GLOBAL_POSITION_INT` на SERIAL1 по умолчанию выключен; (2) арм отклонён сообщением `PreArm` — EKF ещё не начал использовать GPS, подожди 10–20 с после запуска; (3) для второго маршрута пришлось править сценарий — координаты остались в коде, а не в `routes/`. (4) В шаге 5 случай B поднялся до 15 м, а не до 20 м — в рабочей папке остался старый `eeprom.bin` без `-w`, или `lab.parm` стоит в `--defaults` не последним. (5) Случай A набрал 20 м — RTL включён не над домом: сначала дождись, пока аппарат вернётся в точку взлёта.

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
- **Симптом:** поменял значение в `.parm`, а в SITL осталось старое
  - Возможная причина: в `eeprom.bin` рабочей папки сохранено прежнее значение — оно перебивает `--defaults`.
  - Что сделать: запуск с `-w` или удалить `eeprom.bin`; проверить, что свой файл стоит последним в `--defaults`.
- **Симптом:** бинарник `arducopter` запущен, но ничего не происходит, лог пуст
  - Возможная причина: SERIAL0 открыт как `tcp:0:wait` — прошивка ждёт клиента на 5760.
  - Что сделать: подключить MAVProxy или свой скрипт к `tcp:127.0.0.1:5760`.
- **Симптом:** сценарий с `--speedup 10` «ждёт» в 10 раз дольше, чем надо, или таймауты срабатывают раньше
  - Возможная причина: интервалы считаются по часам компьютера, а не по `time_boot_ms`.
  - Что сделать: все ожидания — по времени прошивки, как `sim_t()` в шаге 5; реальное ускорение измерять.
- **Симптом:** RTL не набирает `RTL_ALT_M`, аппарат садится с текущей высоты
  - Возможная причина: аппарат рядом с домом, конус `RTL_CONE_SLOPE` = 3 ограничил высоту до d · 3.
  - Что сделать: это штатно; для теста набора отлети дальше `RTL_ALT_M` / 3 или поставь `RTL_CONE_SLOPE = 0`.
- **Симптом:** GCS не подключается к SITL
  - Возможная причина: порты заняты, MAVProxy не пробрасывает.
  - Что сделать: `--out=udp:127.0.0.1:14550` явно, проверить `ss -lunp`.

## references
- Setting up SITL on Linux — ArduPilot Dev | https://ardupilot.org/dev/docs/setting-up-sitl-on-linux.html | primary | A
- Setting Up SITL — ArduPilot Dev | https://ardupilot.org/dev/docs/SITL-setup-landingpage.html | primary | A
- pymavlink — source code (GitHub) | https://github.com/ArduPilot/pymavlink | primary | A
- SITL command line options — SITL_cmdline.cpp, Copter-4.7.2 | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_HAL_SITL/SITL_cmdline.cpp | primary | A
- SIM_* parameters — libraries/SITL/SITL.cpp, Copter-4.7.2 | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/SITL/SITL.cpp | primary | A
- sim_vehicle.py, Copter-4.7.2 | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/Tools/autotest/sim_vehicle.py | primary | A
- RTL return altitude — mode_rtl.cpp, Copter-4.7.2 | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/ArduCopter/mode_rtl.cpp | primary | A

## checklist
- SITL запускается, GCS подключена
- Взлёт и RTL выполнены из консоли MAVProxy
- Скрипт на pymavlink поднимает дрон
- Маршруты и сценарии разнесены по разным папкам
- Знаю, как сбросить параметры SITL и какой слой перебивает какой
- Ожидания в скриптах считаю по времени прошивки, ускорение измеряю
