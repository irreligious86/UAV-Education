---
id: ap-missions
title: "Миссии и планирование"
level: L2
readingTime: 35 мин
firmware: ArduPilot 4.7 (сверено с 4.7.3; лабораторная снята на SITL 4.7.2)
status: published
added: 2026-11-07
tags:
  - миссии
  - AUTO
  - waypoints
related:
  - ap-sitl
  - ap-ekf
next:
  - ap-ekf
---

## summary
Миссия в ArduPilot — список команд, который полётник выполняет сам в режиме AUTO: взлететь, пройти точки, снять кадр, вернуться. Модуль объясняет, из чего состоит миссия, чем навигационные команды отличаются от DO- и CONDITION-команд, как считается высота, где дом и что происходит при потере связи посреди маршрута. Практика — на SITL, по схеме «маршрут отдельно, сценарий отдельно».

## theory
### Три типа команд
- **NAV** — куда лететь. `NAV_TAKEOFF` (22), `NAV_WAYPOINT` (16), `NAV_LOITER_TIME` (19), `NAV_RETURN_TO_LAUNCH` (20), `NAV_LAND` (21). Миссия идёт от одной NAV-команды к следующей.
- **DO** — что сделать по пути, не меняя маршрута: `DO_CHANGE_SPEED` (178), `DO_SET_SERVO` (183), `DO_SET_CAM_TRIGG_DIST` (206), `DO_JUMP` (177) для циклов.
- **CONDITION** — подождать условия перед следующей DO-командой: `CONDITION_DELAY` (112), `CONDITION_DISTANCE`.

Числа в скобках — коды MAV_CMD: так команды выглядят в файле миссии и в MAVLink.

### Как исполняется список
Миссия хранится в полётнике как пронумерованный список, `seq` 0 — всегда дом: при загрузке аппарат подставляет туда свою домашнюю точку, а пока дом не установлен, отдаёт нули (в выгрузке шага 4 строка 0 — `0.0000000 0.0000000`). Реальные команды начинаются с `seq` 1, число команд вместе с домом — параметр только для чтения `MIS_TOTAL`.

Исполнитель (`libraries/AP_Mission/AP_Mission.cpp`, `advance_current_nav_cmd`) держит одну текущую NAV-команду и одну текущую DO-команду. Когда NAV завершена (промежуточная точка без задержки — когда цель траектории дошла до точки; точка с остановкой — когда аппарат внутри `WP_RADIUS_M`; взлёт — когда набрана высота), он идёт по списку вперёд: встреченную DO-команду запускает, а следующую NAV делает текущей. Поэтому DO-команда, стоящая **после** NAV №N, срабатывает в момент прихода в точку N, то есть действует на участок к следующей точке. В прогоне шага 4 это видно по строкам `Mission: 2 ChangeSpeed` и `Mission: 3 WP` в одну и ту же секунду — сразу после завершения взлёта. CONDITION-команда держит следующие DO-команды, пока её условие не выполнено, но не останавливает полёт к текущей точке.

### DO_JUMP и DO_CHANGE_SPEED
`DO_JUMP` (177): `param1` — номер команды, куда прыгнуть (`seq`), `param2` — сколько раз повторить, −1 — бесконечно. Повтор 1 означает, что участок между целью и прыжком пролетается **дважды**: первый раз по порядку, второй — после прыжка. В прогоне: точки 3→4, `Mission: 5 Jump 1/1`, снова 3→4, затем прыжок пропускается и миссия идёт к команде 6. Счётчики прыжков сбрасываются при новом запуске миссии, а конечный счётчик обнуляется и после завершения своего цикла — вернёшь миссию к началу цикла, и он отработает снова (бит 3 `MIS_OPTIONS` DontZeroCounter это отключает, но для Copter в списке опций он не указан); число отслеживаемых `DO_JUMP` в одной миссии — до 100 на платах с памятью класса ≥ 500 КБ и 15 на остальных (`AP_Mission.h:29–33`). Цель может быть и DO-командой — она выполнится, и полёт пойдёт к следующей за ней NAV; цель 0 или ≥ `MIS_TOTAL` завершает миссию. `DO_JUMP` с −1 и без выхода — бесконечный облёт до разряда батареи; выйти из такого цикла можно только сменой режима — пилотом или GCS — или срабатыванием failsafe (батарея, RC, GCS) либо геозоны.

`DO_CHANGE_SPEED` (178): `param1` — тип скорости (0 — воздушная, 1 — путевая, 2 — набор, 3 — снижение), `param2` — скорость в м/с, `param3` — газ в процентах (−1 — не менять; Copter его игнорирует). У Copter типы 0 и 1 оба меняют горизонтальную скорость `WP_SPD`, 2 и 3 — `WP_SPD_UP` и `WP_SPD_DN` (`ArduCopter/mode_auto.cpp:1991`); значение ≤ 0 игнорируется. Новая скорость действует до конца миссии или до следующей `DO_CHANGE_SPEED`, параметр `WP_SPD` при этом не меняется.

### Время участка
Генератор траектории разгоняет аппарат с ускорением не больше `WP_ACC` (2.5 м/с²) до скорости участка v и тормозит перед точкой, а ускорение меняется не быстрее рывка `WP_JERK` (1 м/с³, `AC_WPNav.cpp:37`). Для участка d с остановками в начале и в конце, если d заметно длиннее v²/a:

t ≈ d / v + v / a + a / J,

где J = `WP_JERK`. Без последнего слагаемого получается трапеция скорости — учебная модель без ограничения рывка (её считает задача модуля).

Для 100 м с остановками: при 5 м/с ≈ 20 + 2 + 2.5 = 24.5 с, при 10 м/с ≈ 10 + 4 + 2.5 = 16.5 с. Независимый прогон в SITL 4.7.2 с остановкой в каждой точке (точки с задержкой 3 с) дал 24.1–24.6 с и 16.8–16.9 с движения. В шаге 4 промежуточные точки проходятся **без остановки**, поэтому формулу он не проверяет: участки там короче — 20.6–21.6 с на 5 м/с (≈ d/v плюс поворот), 14.0–14.8 с на 10 м/с, первый участок после взлёта — 23.2 с. Это ориентир курса для бюджета времени: к сумме участков добавляй взлёт, посадку, ветер и 10–20 % запаса.

### Конец миссии
Если последняя команда — обычная точка, а не `NAV_RETURN_TO_LAUNCH` или `NAV_LAND`, Copter по окончании списка **остаётся в AUTO** и висит на месте (`ModeAuto::exit_mission`: `loiter_start()`), а если позиция плохая — переходит в LAND; если аппарат уже на земле — дизармится. В прогоне через 20 с после последней точки: режим AUTO, 20.0 м, заармлен, скорость 0.01 м/с. Висящий в AUTO аппарат тратит батарею, пока не сработает батарейный failsafe, поэтому правило (ориентир курса): последняя команда миссии — `NAV_RETURN_TO_LAUNCH` или `NAV_LAND`. `MIS_OPTIONS` бит 2 (ContinueAfterLand) позволяет продолжить миссию после `NAV_LAND` посреди списка — для доставки с посадкой.

### Загрузка и выгрузка — диалог
Загрузка идёт по протоколу MAVLink Mission: клиент шлёт `MISSION_COUNT`, дальше **аппарат** запрашивает каждую команду `MISSION_REQUEST_INT(seq)`, клиент отвечает `MISSION_ITEM_INT`, в конце аппарат шлёт `MISSION_ACK` (0 — `MAV_MISSION_ACCEPTED`). Выгрузка — зеркально: клиент шлёт `MISSION_REQUEST_LIST`, получает `MISSION_COUNT`, сам запрашивает каждую команду и в конце отвечает `MISSION_ACK`. Координаты в `MISSION_ITEM_INT` — целые градусы × 10⁷, высота — float в метрах; frame 3/6 — относительно дома. Наблюдение из прогона: в первые секунды после старта SITL загрузка может получить отказ, поэтому скрипт шага 4 ждёт 10 с по часам прошивки.

{{diagram:mavlink-mission-seq|Загрузка миссии ведёт аппарат: он сам запрашивает каждую команду по номеру, а потерянный ответ запрашивает повторно.}}

### Справочник: команды и параметры миссии (Copter 4.7.2)
| Команда / параметр | Код / по умолчанию | Параметры или смысл | Ловушка |
|---|---|---|---|
| `NAV_WAYPOINT` | 16 | p1 — задержка в точке, с; lat/lon/alt | без задержки точка проходится без остановки |
| `NAV_TAKEOFF` | 22 | alt — высота взлёта | на земле в AUTO нужен газ или `AUTO_OPTIONS` бит 1 |
| `NAV_LAND` | 21 | lat/lon = 0 — на месте | без `MIS_OPTIONS` бит 2 миссия на ней кончается |
| `NAV_RETURN_TO_LAUNCH` | 20 | — | высота по правилам RTL, включая конус |
| `DO_JUMP` | 177 | p1 — цель `seq`, p2 — повторы, −1 — бесконечно | повтор N = N + 1 проход |
| `DO_CHANGE_SPEED` | 178 | p1 — тип 0…3, p2 — м/с, p3 — газ % или −1 (Copter игнорирует) | действует до конца миссии |
| `CONDITION_DELAY` | 112 | p1 — с | держит DO, не полёт |
| `MIS_TOTAL` | только чтение | число команд с домом | |
| `MIS_RESTART` | 0 | 0 — продолжить, 1 — с начала при входе в AUTO | |
| `MIS_OPTIONS` | 0 | Copter: бит 0 — стирать миссию при перезагрузке, бит 2 — продолжать после посадки | |
| `WP_SPD`, м/с | 10 | горизонтальная скорость (до 4.7 — `WPNAV_SPEED`, см/с) | `DO_CHANGE_SPEED` её перекрывает |
| `WP_ACC`, м/с² | 2.5 | ускорение (до 4.7 — `WPNAV_ACCEL`, см/с²) | входит в t ≈ d/v + v/a + a/J |
| `WP_JERK`, м/с³ | 1 | рывок — скорость изменения ускорения | добавляет ≈ a/J к участку с остановками |
| `WP_RADIUS_M`, м | 2 | радиус «достигнута» для точки с остановкой; для пролётных — радиус срезания угла (до 4.7 — `WPNAV_RADIUS`, см) | промежуточные точки без задержки радиусом не проверяются |
| `AUTO_OPTIONS` | 0 | бит 0 — арм в AUTO, бит 1 — взлёт без подъёма газа | для скриптов и SITL |

### Высота
У каждой точки есть система отсчёта (frame). Для миссий почти всегда берут высоту **относительно дома** (`MAV_FRAME_GLOBAL_RELATIVE_ALT`, код 3): «100 м» означает 100 м над точкой арма. Абсолютная высота над уровнем моря (`MAV_FRAME_GLOBAL`, 0) нужна редко и легко приводит к ошибке в сотни метров. Высота над рельефом (terrain) требует данных о местности.

### Дом
Домашняя точка для Copter — место, где аппарат заармился. RTL возвращает туда, а не туда, где стоит пилот. Если стартовал с крыши машины и переехал — дом остался на старом месте. В GCS дом можно переустановить до взлёта.

### Запуск и возобновление
Миссия Copter обычно начинается с `NAV_TAKEOFF`. Переход в AUTO на земле с заармленным аппаратом запускает взлёт после подъёма газа пилотом (или сразу, если в `AUTO_OPTIONS` включён бит 1 «Allow Takeoff Without Raising Throttle»); в SITL — `rc 3 1500`. По умолчанию при повторном входе в AUTO миссия продолжается с текущей команды; параметр `MIS_RESTART` заставляет начинать с первой.

### Failsafe в миссии
Потеря радиосвязи во время AUTO ведёт себя по `FS_THR_ENABLE` (RTL, Land, SmartRTL…), а продолжение миссии включается битом 0 `FS_OPTIONS`. Для автономных полётов за пределами видимости это решение принимают до взлёта, а не по факту. Потеря GCS — отдельный параметр `FS_GCS_ENABLE`. Батарейный failsafe (`BATT_FS_LOW_ACT`, `BATT_FS_CRT_ACT`) перебивает миссию.

{{lesson:ap-safety-fs|Какое действие failsafe выбрать для автономной миссии и как проверить его в SITL до вылета.}}

### Файл миссии
GCS сохраняют миссию в текстовый файл формата `QGC WPL 110`: по строке на команду — номер, флаг текущей, frame, код команды, четыре параметра, широта, долгота, высота, флаг автопродолжения. Такой файл удобно хранить в git рядом с параметрами.

### Команды, которые стоит знать наизусть
NAV: `NAV_WAYPOINT` (p1 — задержка в точке, с), `NAV_TAKEOFF` (alt), `NAV_LAND`, `NAV_RETURN_TO_LAUNCH`, `NAV_LOITER_TIME/TURNS/UNLIM`, `NAV_SPLINE_WAYPOINT` (сплайн), `NAV_DELAY`; DO: `DO_SET_SERVO`, `DO_SET_RELAY`, `DO_DIGICAM_CONTROL`, `DO_SET_CAM_TRIGG_DIST` (съёмка через каждые N м — основа фотограмметрии), `DO_CHANGE_SPEED`, `DO_SET_ROI` (нацелить гимбал/нос), `DO_JUMP` (цикл, с счётчиком), `DO_LAND_START` (точка входа посадочной последовательности для failsafe), `DO_SET_HOME`; CONDITION: `CONDITION_DELAY`, `CONDITION_DISTANCE`, `CONDITION_YAW`. Параметры выполнения: `WP_SPD` (м/с горизонталь, по умолчанию 10), `WP_SPD_UP/DN` (2.5 и 1.5 м/с), `WP_RADIUS_M` (радиус захвата, 2 м), `WP_ACC` (2.5 м/с²) (до 4.7 — `WPNAV_SPEED`, `WPNAV_SPEED_UP/DN`, `WPNAV_RADIUS`, `WPNAV_ACCEL` в см/с, см и см/с²), `WP_YAW_BEHAVIOR` (нос по курсу/нет), `MIS_RESTART` (0 — продолжить с последней команды при входе в Auto, 1 — с начала), `MIS_OPTIONS` (бит 0 — стирать миссию при перезагрузке; бит 1 — учитывать расстояние до посадки в failsafe АКБ (только Plane); бит 2 — продолжать после посадки), `RTL_*` для конца миссии.

### Высоты: три системы и одна ошибка
Относительная (над домом, `MAV_FRAME_GLOBAL_RELATIVE_ALT`, по умолчанию), абсолютная (над уровнем моря — ошибка при другом месте взлёта), terrain (над рельефом по данным SRTM с GCS или дальномера, `TERRAIN_ENABLE`, frame «Terrain» у точек и `WP_RFND_USE`/`RTL_ALT_TYPE`). Классическая авария: миссия с абсолютными высотами, составленная для другой площадки на 300 м выше — аппарат пытается уйти под землю или в небо. Правило (ориентир курса): относительные высоты, проверка в GCS профилем высот над рельефом.

{{diagram:mission-jump-order|Порядок выполнения миссии шага 4: DO-команды срабатывают на границе участков, DO_JUMP с повтором 1 даёт второй проход A–B, а без RTL в конце аппарат висит в AUTO.}}

### Разобранный пример: съёмка участка 300×200 м
Mission Planner → Survey (Grid): камера (сенсор, фокус), высота 80 м, перекрытие 75/65% → план сам считает расстояние между галсами и `DO_SET_CAM_TRIGG_DIST`; скорость 8 м/с (по выдержке камеры: смаз ≤ 1 px → v·t_exp ≤ GSD); `NAV_TAKEOFF` 80, галсы, `DO_SET_CAM_TRIGG_DIST 0` в конце, `NAV_RETURN_TO_LAUNCH`. Проверка: профиль высот, время миссии против ёмкости АКБ (`BATT_LOW_MAH` с запасом на RTL + запас ёмкости на возврат), геозона вокруг участка. Прогон в SITL с тем же файлом миссии — обязателен.

{{diagram:mission-alt-frames|Выбор системы высот в миссии: Relative для ровного участка, Terrain при перепадах рельефа, Absolute когда задана высота над уровнем моря.}}

### Место в системе

- **Получает:** позицию и точку дома от EKF — AUTO требует здоровой оценки (`ap-ekf`); действия при потере связи и разряде АКБ (`ap-safety-fs`); данные рельефа для высот terrain (`nav-terrain`).
- **Отдаёт:** точки и ограничения `WP_SPD`, `WP_ACC` — генератору траектории (`ctl-guidance`); `DO_SET_CAM_TRIGG_DIST` — съёмке (`per-mapping`); файл миссии — прогону в `ap-sitl`.
- **Если ошибиться здесь:** абсолютные высоты в миссии, составленной для другой площадки → аппарат идёт под землю или в небо; ловится профилем высот и прогоном в `ap-sitl`. Время миссии больше ёмкости АКБ → батарейный failsafe перебивает миссию посреди маршрута (`ap-safety-fs`); откуда берётся просадка — `f-power`.

## practice
### Шаг 1. Миссия в SITL через GCS
1. Запусти SITL: `sim_vehicle.py -v ArduCopter --console --map`.
2. В Mission Planner (Plan) или QGC (Plan) поставь TAKEOFF 20 м, три точки, RTL.
3. Запиши миссию в аппарат, сохрани файл `.waypoints`.
4. Арм, режим AUTO, наблюдай. Потом попробуй переключиться в LOITER посреди маршрута и вернуться в AUTO.

### Шаг 2. Та же миссия из кода
Маршрут — данные, сценарий — команды. Пример загрузки маршрута через pymavlink:

```python
from pymavlink import mavutil

ROUTE = [  # (lat, lon, alt_m) — data only, no commands here
    (-35.3630, 149.1652, 30),
    (-35.3625, 149.1660, 30),
    (-35.3632, 149.1668, 30),
]

m = mavutil.mavlink_connection("tcp:127.0.0.1:5762")
m.wait_heartbeat()
FRAME = mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT  # 6

def item(seq, cmd, lat=0, lon=0, alt=0, p1=0):
    return m.mav.mission_item_int_encode(
        m.target_system, m.target_component, seq, FRAME, cmd,
        0, 1, p1, 0, 0, 0, int(lat * 1e7), int(lon * 1e7), alt)

items = [item(0, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT), item(1, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, alt=20)]  # seq 0 = home
items += [item(i + 1, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, *wp) for i, wp in enumerate(ROUTE)]
items.append(item(len(items), mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH))

m.waypoint_clear_all_send()
m.waypoint_count_send(len(items))
for _ in items:
    req = m.recv_match(type=["MISSION_REQUEST", "MISSION_REQUEST_INT"], blocking=True)
    m.mav.send(items[req.seq])
ack = m.recv_match(type="MISSION_ACK", blocking=True)
print("mission upload:", ack.type)  # 0 = MAV_MISSION_ACCEPTED
```

Загрузка миссии — диалог: аппарат сам запрашивает каждую точку по номеру, поэтому отправлять их «пачкой» нельзя.

### Шаг 3. Сценарии поверх маршрута
Напиши три сценария, которые принимают маршрут как параметр: «пролететь», «пролететь и сделать фото на каждой точке» (`DO_DIGICAM_CONTROL`), «пролететь с отказом мотора на второй точке» (тумблер из модуля про Lua). Один маршрут — три сценария без правки координат.

### Шаг 4. DO_JUMP, DO_CHANGE_SPEED и конец списка — прогон в SITL
Этот шаг выполнен на ArduCopter 4.7.2 SITL (рама `+`, `--speedup 10`, pymavlink 2.4.50) без MAVProxy и без GCS. Маршрут — квадрат 100 × 100 м на 20 м, словарь `ROUTE` (данные); план — список команд (сценарий): взлёт, скорость 5 м/с, точки A и B, `DO_JUMP` на A с повтором 1, скорость 10 м/с, точки C и D. RTL в конце **нет** нарочно — чтобы увидеть, что Copter делает, когда список кончился. Скрипт загружает миссию, выгружает её обратно в файл `QGC WPL 110`, летит и печатает время каждого участка и максимальную скорость на нём. Запуск: `mkdir run && cd run && python3 ../mission_lab.py ~/ardupilot`, около 1 мин реального времени.

```python
"""Mission lab: upload, download to a QGC WPL 110 file and fly a mission with DO_CHANGE_SPEED and DO_JUMP
in ArduCopter 4.7.2 SITL; no RTL at the end, to see what the copter does when the list runs out.
Usage: python3 mission_lab.py ~/ardupilot   (run from an empty folder)"""
import math, subprocess, sys, time
from pymavlink import mavutil

AP, C = sys.argv[1], mavutil.mavlink
sitl = subprocess.Popen([AP + "/build/sitl/bin/arducopter", "--model", "+", "--speedup", "10", "-w",
                         "--defaults", AP + "/Tools/autotest/default_params/copter.parm",
                         "--home", "-35.363261,149.165230,584,353"], stdout=open("sitl.out", "w"), stderr=subprocess.STDOUT)
time.sleep(1)
m = mavutil.mavlink_connection("tcp:127.0.0.1:5760"); m.wait_heartbeat()
m.mav.command_long_send(1, 1, C.MAV_CMD_SET_MESSAGE_INTERVAL, 0, 33, 200000, 0, 0, 0, 0, 0)  # GLOBAL_POSITION_INT 5 Hz
LAT0, LON0, K = -35.363261, 149.165230, 111319.5   # home and metres per degree (latitude)
ROUTE = {"A": (100, 0), "B": (100, 100), "C": (0, 100), "D": (0, 0)}   # data: north_m, east_m


def nav(cmd, n=0, e=0, alt=20.0, p=(0, 0, 0, 0)):
    lat, lon = LAT0 + n / K, LON0 + e / (K * math.cos(math.radians(LAT0)))
    return [cmd, *p, int(lat * 1e7), int(lon * 1e7), alt]


def do(cmd, *p):
    return [cmd, *p, *[0] * (4 - len(p)), 0, 0, 0]


plan = [nav(C.MAV_CMD_NAV_WAYPOINT, alt=0),           # 0: home, the vehicle overwrites it
        nav(C.MAV_CMD_NAV_TAKEOFF),                    # 1
        do(C.MAV_CMD_DO_CHANGE_SPEED, 1, 5, -1),       # 2: ground speed 5 m/s, throttle unchanged
        nav(C.MAV_CMD_NAV_WAYPOINT, *ROUTE["A"]),      # 3
        nav(C.MAV_CMD_NAV_WAYPOINT, *ROUTE["B"]),      # 4
        do(C.MAV_CMD_DO_JUMP, 3, 1),                   # 5: back to 3, repeat once
        do(C.MAV_CMD_DO_CHANGE_SPEED, 1, 10, -1),      # 6: 10 m/s
        nav(C.MAV_CMD_NAV_WAYPOINT, *ROUTE["C"]),      # 7
        nav(C.MAV_CMD_NAV_WAYPOINT, *ROUTE["D"])]      # 8: last item, no RTL after it
F = C.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT
while m.recv_match(type="GLOBAL_POSITION_INT", blocking=True).time_boot_ms < 10000:
    pass                                                  # right after boot the upload is refused (ACK 4 = MAV_MISSION_NO_SPACE)
m.mav.mission_count_send(1, 1, len(plan))                 # upload: the vehicle pulls each item by seq
while (r := m.recv_match(type=["MISSION_REQUEST_INT", "MISSION_REQUEST", "MISSION_ACK"], blocking=True)).get_type() != "MISSION_ACK":
    c, p1, p2, p3, p4, x, y, z = plan[r.seq]
    m.mav.mission_item_int_send(1, 1, r.seq, F, c, 0, 1, p1, p2, p3, p4, x, y, z)
print(f"upload: MISSION_ACK type {r.type} (0 = MAV_MISSION_ACCEPTED)")
m.mav.mission_request_list_send(1, 1)                     # download: we pull each item by seq
n = m.recv_match(type="MISSION_COUNT", blocking=True).count
with open("mission.waypoints", "w") as f:
    f.write("QGC WPL 110\n")
    for s in range(n):
        m.mav.mission_request_int_send(1, 1, s)
        i = m.recv_match(type="MISSION_ITEM_INT", blocking=True)
        f.write(f"{i.seq}\t{int(s == 0)}\t{i.frame}\t{i.command}\t{i.param1:g}\t{i.param2:g}\t{i.param3:g}\t{i.param4:g}"
                f"\t{i.x / 1e7:.7f}\t{i.y / 1e7:.7f}\t{i.z:g}\t{i.autocontinue}\n")
m.mav.mission_ack_send(1, 1, 0)
print(open("mission.waypoints").read(), end="")
m.set_mode("GUIDED")
while not m.motors_armed():
    m.arducopter_arm(); m.recv_match(type="HEARTBEAT", blocking=True); m.recv_match(type="HEARTBEAT", blocking=True)
m.set_mode("AUTO")
m.mav.command_long_send(1, 1, C.MAV_CMD_MISSION_START, 0, 0, 0, 0, 0, 0, 0, 0)  # throttle stays low in this SITL
t0, last, v, t = None, None, [], 0.0
while True:
    r = m.recv_match(type=["STATUSTEXT", "GLOBAL_POSITION_INT"], blocking=True)
    if r.get_type() == "GLOBAL_POSITION_INT":
        t = r.time_boot_ms / 1000; t0 = t0 or t
        v.append(math.hypot(r.vx, r.vy) / 100)
    elif r.text.startswith(("Mission:", "Reached")):
        t0 = t0 or t
        leg = f"  leg {t - last:5.1f} s, top speed {max(v):4.1f} m/s" if r.text.startswith("Reached") and last else ""
        print(f"[{t - t0:6.1f} s] {r.text}{leg}")
        if r.text.startswith("Reached"):
            last, v = t, []
        elif last is None and "WP" in r.text:
            last, v = t, []
        if r.text == "Reached command #8":
            break
end = t
while (r := m.recv_match(type="GLOBAL_POSITION_INT", blocking=True)).time_boot_ms / 1000 < end + 20:
    pass
hb = m.recv_match(type="HEARTBEAT", blocking=True)
print(f"+20 s after the last item: mode {mavutil.mode_string_v10(hb)}, armed {bool(hb.base_mode & 128)}, "
      f"alt {r.relative_alt / 1000:.1f} m, speed {math.hypot(r.vx, r.vy) / 100:.2f} m/s")
sitl.terminate()
```

Вывод прогона (2026-11-26):

```text
upload: MISSION_ACK type 0 (0 = MAV_MISSION_ACCEPTED)
QGC WPL 110
0	1	0	16	0	0	0	0	0.0000000	0.0000000	0	1
1	0	3	22	0	0	0	0	-35.3632610	149.1652300	20	1
2	0	0	178	1	5	-1	0	0.0000000	0.0000000	0	1
3	0	3	16	0	0	0	0	-35.3623626	149.1652300	20	1
4	0	3	16	0	0	0	0	-35.3623626	149.1663315	20	1
5	0	0	177	3	1	0	0	0.0000000	0.0000000	0	1
6	0	0	178	1	10	-1	0	0.0000000	0.0000000	0	1
7	0	3	16	0	0	0	0	-35.3632610	149.1663315	20	1
8	0	3	16	0	0	0	0	-35.3632610	149.1652300	20	1
[   0.0 s] Mission: 1 Takeoff
[  11.4 s] Mission: 2 ChangeSpeed
[  11.4 s] Mission: 3 WP
[  34.6 s] Reached command #3  leg  23.2 s, top speed  5.0 m/s
[  34.6 s] Mission: 4 WP
[  55.2 s] Reached command #4  leg  20.6 s, top speed  5.0 m/s
[  55.2 s] Mission: 5 Jump 1/1
[  55.2 s] Mission: 3 WP
[  76.8 s] Reached command #3  leg  21.6 s, top speed  5.0 m/s
[  76.8 s] Mission: 4 WP
[  98.0 s] Reached command #4  leg  21.2 s, top speed  5.0 m/s
[  98.0 s] Mission: 6 ChangeSpeed
[  98.0 s] Mission: 7 WP
[ 112.0 s] Reached command #7  leg  14.0 s, top speed  9.9 m/s
[ 112.0 s] Mission: 8 WP
[ 126.8 s] Reached command #8  leg  14.8 s, top speed  9.9 m/s
+20 s after the last item: mode AUTO, armed True, alt 20.0 m, speed 0.01 m/s
```

Что читать в выводе. `MISSION_ACK type 0` — загрузка принята. Выгруженный файл совпадает с планом: `seq` 2 — `178 1 5 -1` (путевая скорость 5 м/с, газ не менять), `seq` 5 — `177 3 1` (прыжок на 3, повтор 1), координаты точек — дом плюс 100 м (−35.3623626 = −35.3632610 + 100 / 111319.5; сама ArduPilot считает по сферической константе 111318.845 м на градус, разница в седьмом знаке). Строка 0 — нули: дом ещё не установлен в момент загрузки. Порядок прохождения 3, 4, `Jump 1/1`, 3, 4, 6, 7, 8 — один повтор дал два прохода A–B. Скорость на участках после `DO_CHANGE_SPEED 5` — 5.0 м/с, после `DO_CHANGE_SPEED 10` — 9.9 м/с, хотя `WP_SPD` = 10 всё время. Участки без остановки длятся около d/v плюс поворот; формула из теории — для участка с остановками. Последняя строка — аппарат висит в AUTO на 20 м: без `NAV_RETURN_TO_LAUNCH` миссия «закончилась», а полёт — нет.

**Автопроверка лога:** `check_lab_log.py <лог.bin> --lab mission` — AUTO включён, ≥ 3 навигационных команд, сообщения «Reached», RTL/LAND в конце, спутники ≥ 6, нет ошибок EKF/GPS.

**Эталон для самопроверки.** Шаг 2: скрипт печатает `mission upload: 0` — это `MAV_MISSION_ACCEPTED`; если он завис на загрузке, точки ушли «пачкой», без ожидания запросов: аппарат сам запрашивает каждую по номеру. Шаг 3: все три сценария получают один и тот же `ROUTE` как параметр, и в коде сценариев нет ни одной координаты — смена маршрута не требует правки сценария. Автопроверка на логе каждого прогона проходит по всем пунктам: AUTO включён, не меньше трёх навигационных команд, есть «Reached», в конце RTL/LAND. Шаг 4: типичные неверные результаты — (1) после прыжка точки 3–4 пролетаются трижды: в `param2` стоит 2 (повтор N даёт N + 1 проход); (2) скорость на первом участке 10 м/с вместо 5 — `DO_CHANGE_SPEED` поставлена после точки A, а не перед ней, и действует только со следующего участка; (3) аппарат «завис» после точки D — это не сбой, а конец списка без RTL; (4) загрузка получила отказ — скрипт отправил `MISSION_COUNT` в первые секунды после старта SITL.

Самопроверка: лабораторная выполнена, когда в шаге 2 скрипт печатает `mission upload: 0`; в шаге 3 три сценария используют один `ROUTE` без координат в коде; в шаге 4 у тебя `MISSION_ACK type 0`, выгруженный файл совпадает с таблицей плана построчно (коды 16, 22, 178, 16, 16, 177, 178, 16, 16), порядок `Reached` — 3, 4, 3, 4, 7, 8, скорость на участках 3–4 — 5.0 ± 0.2 м/с, на участках 7–8 — 10 ± 0.3 м/с, время 100-метровых участков на 5 м/с — 20–23 с, на 10 м/с — 13.5–15.5 с, а через 20 с после точки 8 режим AUTO, аппарат заармлен на 20 ± 0.5 м; если добавить в конец `NAV_RETURN_TO_LAUNCH` и прогнать снова, аппарат садится у дома и дизармится.

## diagnostics
- **Симптом:** AUTO не запускается, аппарат стоит
  - Возможная причина: миссия не загружена, нет `NAV_TAKEOFF` первой командой или аппарат не заармлен.
  - Что сделать: прочитать миссию из аппарата, проверить первую команду и сообщения GCS.
- **Симптом:** аппарат летит на 100 м выше ожидаемого
  - Возможная причина: абсолютная высота вместо относительной.
  - Что сделать: проверить frame каждой точки в файле миссии.
- **Симптом:** RTL возвращает не туда, где пилот
  - Возможная причина: дом — место арма.
  - Что сделать: переустанавливать дом перед взлётом после переезда.
- **Симптом:** загрузка миссии зависает
  - Возможная причина: отправка точек без ожидания запросов или неверный `seq`.
  - Что сделать: отвечать на `MISSION_REQUEST(_INT)` по номеру, проверить `MISSION_ACK`.
- **Симптом:** в Auto аппарат ушёл в землю/набор после смены площадки
  - Возможная причина: абсолютные высоты в миссии.
  - Что сделать: относительные/terrain; проверять профиль высот в GCS.
- **Симптом:** после последней точки аппарат висит на месте в AUTO
  - Возможная причина: в конце миссии нет `NAV_RETURN_TO_LAUNCH`/`NAV_LAND`; Copter по концу списка переходит в удержание внутри AUTO.
  - Что сделать: последней командой ставить RTL или LAND; сейчас — переключить в RTL.
  - Последствия: висение до батарейного failsafe.
- **Симптом:** цикл по `DO_JUMP` пролетается на один раз больше или меньше, чем ждал
  - Возможная причина: `param2` — число повторов, а не проходов; повтор N = N + 1 проход; −1 — бесконечно.
  - Что сделать: считать проходы по `Mission: N Jump k/N` в сообщениях GCS.
- **Симптом:** `DO_CHANGE_SPEED` «не действует» на нужном участке
  - Возможная причина: DO-команда срабатывает при завершении предыдущей NAV, то есть влияет на участок **после** точки, за которой стоит.
  - Что сделать: ставить её перед NAV-точкой участка, где нужна новая скорость; проверить по скорости в логе.
- **Симптом:** после посадки в миссии аппарат не дизармится или продолжает
  - Возможная причина: `MIS_OPTIONS` бит 2 (ContinueAfterLand), `LAND_*`.
  - Что сделать: выставить осознанно; проверить в SITL.

## references
- Planning a Mission with Waypoints and Events — ArduPilot Copter | https://ardupilot.org/copter/docs/common-planning-a-mission-with-waypoints-and-events.html | primary | A
- Copter Mission Command List — ArduPilot | https://ardupilot.org/copter/docs/mission-command-list.html | primary | A
- MAVLink Mission Protocol | https://mavlink.io/en/services/mission.html | primary | A
- MAVLink common message set (common.xml) | https://github.com/mavlink/mavlink/blob/master/message_definitions/v1.0/common.xml | primary | A
- AP_Mission.cpp (MIS_* parameters, DO_JUMP, command execution), Copter-4.7.2 | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_Mission/AP_Mission.cpp | primary | A
- mode_auto.cpp (DO_CHANGE_SPEED, end of mission), Copter-4.7.2 | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/ArduCopter/mode_auto.cpp | primary | A

## checklist
- Знаю разницу NAV, DO и CONDITION команд
- Все точки миссии в относительной высоте
- Понимаю, где дом и как его переустановить
- Failsafe радио/GCS/батареи настроены до автономного полёта
- Миссия загружается из кода как диалог запрос–ответ
- Маршрут хранится отдельно от сценария
- Последняя команда миссии — RTL или LAND
- Число проходов цикла `DO_JUMP` и место `DO_CHANGE_SPEED` проверены в SITL
