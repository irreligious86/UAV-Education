---
id: ap-missions
title: "Місії та планування"
level: L2
readingTime: 25 хв
firmware: ArduPilot 4.5+
status: published
added: 2026-11-07
tags:
  - місії
  - AUTO
  - waypoints
related:
  - ap-sitl
  - ap-ekf
next:
  - ap-ekf
source: content/ardupilot/ap-missions.md
source_hash: 2c8780dcaaa0
---

## summary
Місія в ArduPilot — список команд, котрий польотник виконує сам у режимі AUTO: злетіти, пройти точки, зробити кадр, вернутися. Модуль пояснює, з чого ся складає місія, чим навігаційні команди відрізняються від DO- і CONDITION-команд, як рахується висота, де дім і що ся діє при втраті зв'язку посеред маршруту. Практика — на SITL, за схемою «маршрут окремо, сценарій окремо».

## theory
### Три типи команд
- **NAV** — куди летіти. `NAV_TAKEOFF` (22), `NAV_WAYPOINT` (16), `NAV_LOITER_TIME` (19), `NAV_RETURN_TO_LAUNCH` (20), `NAV_LAND` (21). Місія йде від однієї NAV-команди до наступної.
- **DO** — що зробити по дорозі, не міняючи маршруту: `DO_CHANGE_SPEED` (178), `DO_SET_SERVO` (183), `DO_SET_CAM_TRIGG_DIST` (206), `DO_JUMP` (177) для циклів.
- **CONDITION** — дочекатися умови перед наступною DO-командою: `CONDITION_DELAY` (112), `CONDITION_DISTANCE`.

Числа в дужках — коди MAV_CMD: так команди виглядають у файлі місії та в MAVLink.

### Висота
Кожна точка має систему відліку (frame). Для місій майже завжди беруть висоту **відносно дому** (`MAV_FRAME_GLOBAL_RELATIVE_ALT`, код 3): «100 м» значить 100 м над точкою арму. Абсолютна висота над рівнем моря (`MAV_FRAME_GLOBAL`, 0) треба рідко, а помилку в сотні метрів з нею трафити — раз плюнути. Висота над рельєфом (terrain) потребує даних про місцевість.

### Дім
Домашня точка для Copter — місце, де апарат заармився. RTL вертає туди, а не туди, де стоїть пілот. Як стартував з даху машини й переїхав — дім лишився на старому місці. У GCS дім можна перевстановити до зльоту.

### Запуск і відновлення
Місія Copter звичайно починається з `NAV_TAKEOFF`. Перехід в AUTO на землі із заармленим апаратом запускає зліт, коли пілот підніме газ (або зара ж, як в `AUTO_OPTIONS` увімкнено біт 1 «Allow Takeoff Without Raising Throttle»); у SITL — `rc 3 1500`. За замовчуванням при повторному вході в AUTO місія йде далі з поточної команди; параметр `MIS_RESTART` змушує починати з першої.

### Failsafe у місії
Втрату радіозв'язку під час AUTO обробляє `FS_THR_ENABLE` (RTL, Land, SmartRTL…), а продовження місії вмикається бітом 0 `FS_OPTIONS`. Для автономних польотів за межами видимості то рішення ухвалюють до зльоту, а не за фактом. Втрата GCS — окремий параметр `FS_GCS_ENABLE`. Батарейний failsafe (`BATT_FS_LOW_ACT`, `BATT_FS_CRT_ACT`) перебиває місію.

### Файл місії
GCS зберігають місію в текстовий файл формату `QGC WPL 110`: по рядку на команду — номер, прапорець поточної, frame, код команди, чотири параметри, широта, довгота, висота, прапорець автопродовження. Такий файл файно тримати в git коло параметрів.

### Команди, котрі варто знати напам'ять
NAV: `NAV_WAYPOINT` (p1 — затримка в точці, с), `NAV_TAKEOFF` (alt), `NAV_LAND`, `NAV_RETURN_TO_LAUNCH`, `NAV_LOITER_TIME/TURNS/UNLIM`, `NAV_SPLINE_WAYPOINT` (сплайн), `NAV_DELAY`; DO: `DO_SET_SERVO`, `DO_SET_RELAY`, `DO_DIGICAM_CONTROL`, `DO_SET_CAM_TRIGG_DIST` (зйомка через кожні N м — основа фотограмметрії), `DO_CHANGE_SPEED`, `DO_SET_ROI` (націлити гімбал/ніс), `DO_JUMP` (цикл, з лічильником), `DO_LAND_START` (точка входу посадкової послідовності для failsafe), `DO_SET_HOME`; CONDITION: `CONDITION_DELAY`, `CONDITION_DISTANCE`, `CONDITION_YAW`. Параметри виконання: `WP_SPD` (м/с горизонталь), `WP_SPD_UP/DN`, `WP_RADIUS_M` (радіус захоплення), `WP_ACC` (до 4.7 — `WPNAV_SPEED` у см/с, `WPNAV_SPEED_UP/DN`, `WPNAV_RADIUS`, `WPNAV_ACCEL`), `WP_YAW_BEHAVIOR` (ніс за курсом/ні), `MIS_RESTART` (0 — продовжити з останньої команди при вході в Auto, 1 — з початку), `MIS_OPTIONS` (біт 0 — стирати місію при перезавантаженні; біт 1 — враховувати відстань до посадки у failsafe АКБ (лише Plane); біт 2 — продовжувати після посадки), `RTL_*` для кінця місії.

### Висоти: три системи й одна помилка
Відносна (над домом, `MAV_FRAME_GLOBAL_RELATIVE_ALT`, за замовчуванням), абсолютна (над рівнем моря — помилка, як злітаєш з іншого місця), terrain (над рельєфом за даними SRTM з GCS або далекоміра, `TERRAIN_ENABLE`, frame «Terrain» у точок і `WP_RFND_USE`/`RTL_ALT_TYPE`). Класична аварія: місія з абсолютними висотами, складена для іншого майданчика на 300 м вище, — апарат силується піти під землю або в небо. Правило: відносні висоти, перевірка в GCS профілем висот над рельєфом.

### Розібраний приклад: зйомка ділянки 300×200 м
Mission Planner → Survey (Grid): камера (сенсор, фокус), висота 80 м, перекриття 75/65% → план сам рахує відстань між галсами й `DO_SET_CAM_TRIGG_DIST`; швидкість 8 м/с (за витримкою камери: змаз ≤ 1 px → v·t_exp ≤ GSD); `NAV_TAKEOFF` 80, галси, `DO_SET_CAM_TRIGG_DIST 0` наприкінці, `NAV_RETURN_TO_LAUNCH`. Перевірка: профіль висот, час місії проти ємності АКБ (`BATT_LOW_MAH` із запасом на RTL + запас ємності на повернення), геозона довкола ділянки. Прогін у SITL з тим самим файлом місії — обов'язковий, без жодного «бай там».

{{diagram:mission-alt-frames|Вибір системи висот у місії: Relative для рівної ділянки, Terrain при перепадах рельєфу, Absolute коли задано висоту над рівнем моря.}}

## practice
### Крок 1. Місія в SITL через GCS
1. Запусти SITL: `sim_vehicle.py -v ArduCopter --console --map`.
2. У Mission Planner (Plan) або QGC (Plan) постав TAKEOFF 20 м, три точки, RTL.
3. Запиши місію в апарат, збережи файл `.waypoints`.
4. Арм, режим AUTO, пантруй. Потім спробуй перемкнутися в LOITER посеред маршруту й вернутися в AUTO.

### Крок 2. Та сама місія з коду
Маршрут — то дані, сценарій — то команди. Приклад завантаження маршруту через pymavlink:

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

Завантаження місії — то діалог: апарат сам питає кожну точку за номером, тому пхати їх «пачкою» не можна.

### Крок 3. Сценарії поверх маршруту
Напиши три сценарії, котрі беруть маршрут як параметр: «пролетіти», «пролетіти й зробити фото на кожній точці» (`DO_DIGICAM_CONTROL`), «пролетіти з відмовою мотора на другій точці» (тумблер із модуля про Lua). Один маршрут — три сценарії, і жодної правки координат.

**Автоперевірка логу:** `check_lab_log.py <лог.bin> --lab mission` — AUTO увімкнено, ≥ 3 навігаційних команд, повідомлення «Reached», RTL/LAND наприкінці, супутників ≥ 6, нема помилок EKF/GPS.

## diagnostics
- **Симптом:** AUTO не запускається, апарат стоїть
  - Можлива причина: місію не завантажено, нема `NAV_TAKEOFF` першою командою або апарат не заармлено.
  - Що зробити: прочитай місію з апарата, перевір першу команду й повідомлення GCS.
- **Симптом:** апарат летить на 100 м вище, ніж мав би
  - Можлива причина: абсолютна висота замість відносної.
  - Що зробити: перевір frame кожної точки у файлі місії.
- **Симптом:** RTL вертає не туди, де пілот
  - Можлива причина: дім — місце арму.
  - Що зробити: перевстановлюй дім перед зльотом після переїзду.
- **Симптом:** завантаження місії зависає
  - Можлива причина: точки шлються без очікування запитів або неправильний `seq`.
  - Що зробити: відповідай на `MISSION_REQUEST(_INT)` за номером, перевір `MISSION_ACK`.
- **Симптом:** в Auto апарат пішов у землю/набір після зміни майданчика
  - Можлива причина: абсолютні висоти в місії.
  - Що зробити: відносні/terrain; перевіряй профіль висот у GCS.
- **Симптом:** після посадки в місії апарат не дизармиться або летить далі
  - Можлива причина: `MIS_OPTIONS` біт 2 (ContinueAfterLand), `LAND_*`.
  - Що зробити: виставляй свідомо; перевір у SITL.

## references
- Planning a Mission with Waypoints and Events — ArduPilot Copter | https://ardupilot.org/copter/docs/common-planning-a-mission-with-waypoints-and-events.html | primary | A
- Copter Mission Command List — ArduPilot | https://ardupilot.org/copter/docs/mission-command-list.html | primary | A
- MAVLink Mission Protocol | https://mavlink.io/en/services/mission.html | primary | A
- MAVLink common message set (common.xml) | https://github.com/mavlink/mavlink/blob/master/message_definitions/v1.0/common.xml | primary | A

## checklist
- Знаю різницю між командами NAV, DO і CONDITION
- Усі точки місії у відносній висоті
- Розумію, де дім і як його перевстановити
- Failsafe радіо/GCS/батареї налаштовано до автономного польоту
- Місія завантажується з коду як діалог запит–відповідь
- Маршрут тримаю окремо від сценарію
