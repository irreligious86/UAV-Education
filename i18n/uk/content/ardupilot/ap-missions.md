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
Місія в ArduPilot — список команд, який польотник виконує сам у режимі AUTO: злетіти, пройти точки, зробити кадр, повернутися. Модуль пояснює, з чого складається місія, чим навігаційні команди відрізняються від DO- і CONDITION-команд, як рахується висота, де дім і що відбувається при втраті зв'язку посеред маршруту. Практика — на SITL, за схемою «маршрут окремо, сценарій окремо».

## theory
### Три типи команд
- **NAV** — куди летіти. `NAV_TAKEOFF` (22), `NAV_WAYPOINT` (16), `NAV_LOITER_TIME` (19), `NAV_RETURN_TO_LAUNCH` (20), `NAV_LAND` (21). Місія йде від однієї NAV-команди до наступної.
- **DO** — що зробити дорогою, не змінюючи маршруту: `DO_CHANGE_SPEED` (178), `DO_SET_SERVO` (183), `DO_SET_CAM_TRIGG_DIST` (206), `DO_JUMP` (177) для циклів.
- **CONDITION** — дочекатися умови перед наступною DO-командою: `CONDITION_DELAY` (112), `CONDITION_DISTANCE`.

Числа в дужках — коди MAV_CMD: так команди виглядають у файлі місії та в MAVLink.

### Висота
Кожна точка має систему відліку (frame). Для місій майже завжди беруть висоту **відносно дому** (`MAV_FRAME_GLOBAL_RELATIVE_ALT`, код 3): «100 м» означає 100 м над точкою арму. Абсолютна висота над рівнем моря (`MAV_FRAME_GLOBAL`, 0) потрібна рідко й легко призводить до помилки в сотні метрів. Висота над рельєфом (terrain) потребує даних про місцевість.

### Дім
Домашня точка для Copter — місце, де апарат заармився. RTL повертає туди, а не туди, де стоїть пілот. Якщо стартував з даху машини й переїхав — дім лишився на старому місці. У GCS дім можна перевстановити до зльоту.

### Запуск і відновлення
Місія Copter зазвичай починається з `NAV_TAKEOFF`. Перехід в AUTO на землі із заармленим апаратом запускає зліт після підняття газу пілотом (або одразу, якщо в `AUTO_OPTIONS` увімкнено біт 1 «Allow Takeoff Without Raising Throttle»); у SITL — `rc 3 1500`. За замовчуванням при повторному вході в AUTO місія продовжується з поточної команди; параметр `MIS_RESTART` змушує починати з першої.

### Failsafe у місії
Втрата радіозв'язку під час AUTO обробляється за `FS_THR_ENABLE` (RTL, Land, SmartRTL…), а продовження місії вмикається бітом 0 `FS_OPTIONS`. Для автономних польотів за межами видимості це рішення ухвалюють до зльоту, а не за фактом. Втрата GCS — окремий параметр `FS_GCS_ENABLE`. Батарейний failsafe (`BATT_FS_LOW_ACT`, `BATT_FS_CRT_ACT`) перебиває місію.

### Файл місії
GCS зберігають місію в текстовий файл формату `QGC WPL 110`: по рядку на команду — номер, прапорець поточної, frame, код команди, чотири параметри, широта, довгота, висота, прапорець автопродовження. Такий файл зручно зберігати в git поруч із параметрами.

### Команди, які варто знати напам'ять
NAV: `NAV_WAYPOINT` (p1 — затримка в точці, с), `NAV_TAKEOFF` (alt), `NAV_LAND`, `NAV_RETURN_TO_LAUNCH`, `NAV_LOITER_TIME/TURNS/UNLIM`, `NAV_SPLINE_WAYPOINT` (сплайн), `NAV_DELAY`; DO: `DO_SET_SERVO`, `DO_SET_RELAY`, `DO_DIGICAM_CONTROL`, `DO_SET_CAM_TRIGG_DIST` (зйомка через кожні N м — основа фотограмметрії), `DO_CHANGE_SPEED`, `DO_SET_ROI` (націлити гімбал/ніс), `DO_JUMP` (цикл, з лічильником), `DO_LAND_START` (точка входу посадкової послідовності для failsafe), `DO_SET_HOME`; CONDITION: `CONDITION_DELAY`, `CONDITION_DISTANCE`, `CONDITION_YAW`. Параметри виконання: `WP_SPD` (м/с горизонталь), `WP_SPD_UP/DN`, `WP_RADIUS_M` (радіус захоплення), `WP_ACC` (до 4.7 — `WPNAV_SPEED` у см/с, `WPNAV_SPEED_UP/DN`, `WPNAV_RADIUS`, `WPNAV_ACCEL`), `WP_YAW_BEHAVIOR` (ніс за курсом/ні), `MIS_RESTART` (0 — продовжити з останньої команди при вході в Auto, 1 — з початку), `MIS_OPTIONS` (біт 0 — стирати місію при перезавантаженні; біт 1 — враховувати відстань до посадки у failsafe АКБ (лише Plane); біт 2 — продовжувати після посадки), `RTL_*` для кінця місії.

### Висоти: три системи й одна помилка
Відносна (над домом, `MAV_FRAME_GLOBAL_RELATIVE_ALT`, за замовчуванням), абсолютна (над рівнем моря — помилка при іншому місці зльоту), terrain (над рельєфом за даними SRTM з GCS або далекоміра, `TERRAIN_ENABLE`, frame «Terrain» у точок і `WP_RFND_USE`/`RTL_ALT_TYPE`). Класична аварія: місія з абсолютними висотами, складена для іншого майданчика на 300 м вище, — апарат намагається піти під землю або в небо. Правило: відносні висоти, перевірка в GCS профілем висот над рельєфом.

### Розібраний приклад: зйомка ділянки 300×200 м
Mission Planner → Survey (Grid): камера (сенсор, фокус), висота 80 м, перекриття 75/65% → план сам рахує відстань між галсами й `DO_SET_CAM_TRIGG_DIST`; швидкість 8 м/с (за витримкою камери: змаз ≤ 1 px → v·t_exp ≤ GSD); `NAV_TAKEOFF` 80, галси, `DO_SET_CAM_TRIGG_DIST 0` наприкінці, `NAV_RETURN_TO_LAUNCH`. Перевірка: профіль висот, час місії проти ємності АКБ (`BATT_LOW_MAH` із запасом на RTL + запас ємності на повернення), геозона навколо ділянки. Прогін у SITL з тим самим файлом місії — обов'язковий.

{{diagram:mavlink-mission-seq|Загрузка миссии ведёт аппарат: он сам запрашивает каждую команду по номеру, а потерянный ответ запрашивает повторно.}}

{{diagram:mission-jump-order|Порядок выполнения миссии шага 4: DO-команды срабатывают на границе участков, DO_JUMP с повтором 1 даёт второй проход A–B, а без RTL в конце аппарат висит в AUTO.}}

{{diagram:mission-alt-frames|Вибір системи висот у місії: Relative для рівної ділянки, Terrain при перепадах рельєфу, Absolute коли задано висоту над рівнем моря.}}

## practice
### Крок 1. Місія в SITL через GCS
1. Запусти SITL: `sim_vehicle.py -v ArduCopter --console --map`.
2. У Mission Planner (Plan) або QGC (Plan) постав TAKEOFF 20 м, три точки, RTL.
3. Запиши місію в апарат, збережи файл `.waypoints`.
4. Арм, режим AUTO, спостерігай. Потім спробуй перемкнутися в LOITER посеред маршруту й повернутися в AUTO.

### Крок 2. Та сама місія з коду
Маршрут — дані, сценарій — команди. Приклад завантаження маршруту через pymavlink:

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

Завантаження місії — діалог: апарат сам запитує кожну точку за номером, тому надсилати їх «пачкою» не можна.

### Крок 3. Сценарії поверх маршруту
Напиши три сценарії, які приймають маршрут як параметр: «пролетіти», «пролетіти й зробити фото на кожній точці» (`DO_DIGICAM_CONTROL`), «пролетіти з відмовою мотора на другій точці» (тумблер із модуля про Lua). Один маршрут — три сценарії без правки координат.

**Автоперевірка логу:** `check_lab_log.py <лог.bin> --lab mission` — AUTO увімкнено, ≥ 3 навігаційних команд, повідомлення «Reached», RTL/LAND наприкінці, супутників ≥ 6, немає помилок EKF/GPS.

Прогін цього кроку в SITL (ArduCopter 4.7.2); розбір і очікуваний результат — у російському оригіналі.

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


## diagnostics
- **Симптом:** AUTO не запускається, апарат стоїть
  - Можлива причина: місію не завантажено, немає `NAV_TAKEOFF` першою командою або апарат не заармлено.
  - Що зробити: прочитати місію з апарата, перевірити першу команду й повідомлення GCS.
- **Симптом:** апарат летить на 100 м вище очікуваного
  - Можлива причина: абсолютна висота замість відносної.
  - Що зробити: перевірити frame кожної точки у файлі місії.
- **Симптом:** RTL повертає не туди, де пілот
  - Можлива причина: дім — місце арму.
  - Що зробити: перевстановлювати дім перед зльотом після переїзду.
- **Симптом:** завантаження місії зависає
  - Можлива причина: надсилання точок без очікування запитів або неправильний `seq`.
  - Що зробити: відповідати на `MISSION_REQUEST(_INT)` за номером, перевірити `MISSION_ACK`.
- **Симптом:** в Auto апарат пішов у землю/набір після зміни майданчика
  - Можлива причина: абсолютні висоти в місії.
  - Що зробити: відносні/terrain; перевіряти профіль висот у GCS.
- **Симптом:** після посадки в місії апарат не дизармиться або продовжує
  - Можлива причина: `MIS_OPTIONS` біт 2 (ContinueAfterLand), `LAND_*`.
  - Що зробити: виставити свідомо; перевірити в SITL.

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
- Маршрут зберігається окремо від сценарію
