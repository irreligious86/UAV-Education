---
id: ap-missions
title: "Миссии и планирование"
level: L2
readingTime: 25 мин
firmware: ArduPilot 4.5+
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

### Высота
У каждой точки есть система отсчёта (frame). Для миссий почти всегда берут высоту **относительно дома** (`MAV_FRAME_GLOBAL_RELATIVE_ALT`, код 3): «100 м» означает 100 м над точкой арма. Абсолютная высота над уровнем моря (`MAV_FRAME_GLOBAL`, 0) нужна редко и легко приводит к ошибке в сотни метров. Высота над рельефом (terrain) требует данных о местности.

### Дом
Домашняя точка для Copter — место, где аппарат заармился. RTL возвращает туда, а не туда, где стоит пилот. Если стартовал с крыши машины и переехал — дом остался на старом месте. В GCS дом можно переустановить до взлёта.

### Запуск и возобновление
Миссия Copter обычно начинается с `NAV_TAKEOFF`. Переход в AUTO на земле с заармленным аппаратом запускает взлёт после подъёма газа пилотом (или сразу, если в `AUTO_OPTIONS` включён бит 1 «Allow Takeoff Without Raising Throttle»); в SITL — `rc 3 1500`. По умолчанию при повторном входе в AUTO миссия продолжается с текущей команды; параметр `MIS_RESTART` заставляет начинать с первой.

### Failsafe в миссии
Потеря радиосвязи во время AUTO ведёт себя по `FS_THR_ENABLE` (RTL, Land, SmartRTL…), а продолжение миссии включается битом 0 `FS_OPTIONS`. Для автономных полётов за пределами видимости это решение принимают до взлёта, а не по факту. Потеря GCS — отдельный параметр `FS_GCS_ENABLE`. Батарейный failsafe (`BATT_FS_LOW_ACT`, `BATT_FS_CRT_ACT`) перебивает миссию.

### Файл миссии
GCS сохраняют миссию в текстовый файл формата `QGC WPL 110`: по строке на команду — номер, флаг текущей, frame, код команды, четыре параметра, широта, долгота, высота, флаг автопродолжения. Такой файл удобно хранить в git рядом с параметрами.

### Команды, которые стоит знать наизусть
NAV: `NAV_WAYPOINT` (p1 — задержка в точке, с), `NAV_TAKEOFF` (alt), `NAV_LAND`, `NAV_RETURN_TO_LAUNCH`, `NAV_LOITER_TIME/TURNS/UNLIM`, `NAV_SPLINE_WAYPOINT` (сплайн), `NAV_DELAY`; DO: `DO_SET_SERVO`, `DO_SET_RELAY`, `DO_DIGICAM_CONTROL`, `DO_SET_CAM_TRIGG_DIST` (съёмка через каждые N м — основа фотограмметрии), `DO_CHANGE_SPEED`, `DO_SET_ROI` (нацелить гимбал/нос), `DO_JUMP` (цикл, с счётчиком), `DO_LAND_START` (точка входа посадочной последовательности для failsafe), `DO_SET_HOME`; CONDITION: `CONDITION_DELAY`, `CONDITION_DISTANCE`, `CONDITION_YAW`. Параметры выполнения: `WP_SPD` (м/с горизонталь), `WP_SPD_UP/DN`, `WP_RADIUS_M` (радиус захвата), `WP_ACC` (до 4.7 — `WPNAV_SPEED` в см/с, `WPNAV_SPEED_UP/DN`, `WPNAV_RADIUS`, `WPNAV_ACCEL`), `WP_YAW_BEHAVIOR` (нос по курсу/нет), `MIS_RESTART` (0 — продолжить с последней команды при входе в Auto, 1 — с начала), `MIS_OPTIONS` (бит 0 — стирать миссию при перезагрузке; бит 1 — учитывать расстояние до посадки в failsafe АКБ (только Plane); бит 2 — продолжать после посадки), `RTL_*` для конца миссии.

### Высоты: три системы и одна ошибка
Относительная (над домом, `MAV_FRAME_GLOBAL_RELATIVE_ALT`, по умолчанию), абсолютная (над уровнем моря — ошибка при другом месте взлёта), terrain (над рельефом по данным SRTM с GCS или дальномера, `TERRAIN_ENABLE`, frame «Terrain» у точек и `WP_RFND_USE`/`RTL_ALT_TYPE`). Классическая авария: миссия с абсолютными высотами, составленная для другой площадки на 300 м выше — аппарат пытается уйти под землю или в небо. Правило: относительные высоты, проверка в GCS профилем высот над рельефом.

### Разобранный пример: съёмка участка 300×200 м
Mission Planner → Survey (Grid): камера (сенсор, фокус), высота 80 м, перекрытие 75/65% → план сам считает расстояние между галсами и `DO_SET_CAM_TRIGG_DIST`; скорость 8 м/с (по выдержке камеры: смаз ≤ 1 px → v·t_exp ≤ GSD); `NAV_TAKEOFF` 80, галсы, `DO_SET_CAM_TRIGG_DIST 0` в конце, `NAV_RETURN_TO_LAUNCH`. Проверка: профиль высот, время миссии против ёмкости АКБ (`BATT_LOW_MAH` с запасом на RTL + запас ёмкости на возврат), геозона вокруг участка. Прогон в SITL с тем же файлом миссии — обязателен.

{{diagram:mission-alt-frames|Выбор системы высот в миссии: Relative для ровного участка, Terrain при перепадах рельефа, Absolute когда задана высота над уровнем моря.}}

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

**Автопроверка лога:** `check_lab_log.py <лог.bin> --lab mission` — AUTO включён, ≥ 3 навигационных команд, сообщения «Reached», RTL/LAND в конце, спутники ≥ 6, нет ошибок EKF/GPS.

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
- **Симптом:** после посадки в миссии аппарат не дизармится или продолжает
  - Возможная причина: `MIS_OPTIONS` бит 2 (ContinueAfterLand), `LAND_*`.
  - Что сделать: выставить осознанно; проверить в SITL.

## references
- Planning a Mission with Waypoints and Events — ArduPilot Copter | https://ardupilot.org/copter/docs/common-planning-a-mission-with-waypoints-and-events.html | primary | A
- Copter Mission Command List — ArduPilot | https://ardupilot.org/copter/docs/mission-command-list.html | primary | A
- MAVLink Mission Protocol | https://mavlink.io/en/services/mission.html | primary | A
- MAVLink common message set (common.xml) | https://github.com/mavlink/mavlink/blob/master/message_definitions/v1.0/common.xml | primary | A

## checklist
- Знаю разницу NAV, DO и CONDITION команд
- Все точки миссии в относительной высоте
- Понимаю, где дом и как его переустановить
- Failsafe радио/GCS/батареи настроены до автономного полёта
- Миссия загружается из кода как диалог запрос–ответ
- Маршрут хранится отдельно от сценария
