---
id: ap-sitl
title: "SITL: дрон без дрона"
level: L2
readingTime: 25 хв
firmware: ArduPilot 4.5+
status: published
added: 2026-11-07
tags:
  - SITL
  - pymavlink
  - симуляція
related:
  - ap-intro
  - ap-lua
next:
  - ap-missions
source: content/ardupilot/ap-sitl.md
source_hash: 7ac85e12824f
---

## summary
SITL (Software In The Loop) — справжня прошивка ArduPilot, запущена на комп'ютері замість польотного контролера, із симулятором фізики замість реального світу. Тут можна безкоштовно розбити сотню октокоптерів: переплутати параметри, вимкнути GPS у польоті, «впустити» мотор. Модуль показує, як підняти SITL, підключити наземну станцію, керувати дроном скриптом на Python і організувати проєкт так, щоб маршрути та сценарії жили окремо.

## theory
### Як влаштований SITL
Прошивка збирається під Linux і обмінюється із симулятором фізики «показами датчиків» і «командами моторам». Усе інше — справжнє: ті самі параметри, режими, EKF, failsafe, логи. Тому все, що ти налагодив у SITL, переноситься на залізо майже без змін. Майже — бо в симуляції ідеальні вібрації, ідеальний зв'язок і чесний GPS, якщо ти не зіпсуєш їх сам.

### sim_vehicle.py і MAVProxy
Скрипт `sim_vehicle.py` збирає прошивку, запускає її та консольну наземну станцію MAVProxy. Ключові прапорці:

- `-v ArduCopter` або `-v ArduPlane` — тип апарата;
- `-f octa-quad`, `-f quad`, `-f quadplane` — модель рами в симуляторі;
- `--console --map` — вікна консолі та карти;
- `-w` — скинути параметри до стандартних (корисно, коли експерименти зайшли не туди).

Наземну станцію (QGroundControl, Mission Planner) підключають до виходу MAVProxy через UDP — зазвичай вона знаходить його сама.

### Сценарій проти маршруту
Головне архітектурне рішення в навчальному проєкті: маршрут і сценарій живуть окремо.

- **Маршрут** — лише послідовність точок в одному форматі. Перша точка — старт, остання — фініш.
- **Сценарій** — лише команди: зліт, «пролети маршрут X», посадка, відмова мотора на третій точці. Координат у сценарії немає.

Так один маршрут проганяється різними сценаріями, а один сценарій — різними маршрутами. Це та сама ідея, що й розділення даних і логіки в будь-якому нормальному коді.

### Що вміє SITL, крім «політати»
- **Моделі рам** (`-f`): quad, hexa, octa, octa-quad (X8), y6, tri, heli, plane, quadplane, quadplane-tilttri/quadplane-tilt (тілтротори), rover, boat, sub — у кожної своя фізика в `libraries/SITL/SIM_*.cpp`; параметри за замовчуванням для моделі — `Tools/autotest/default_params/*.parm`.
- **Відмови та середовище** через `SIM_*`: вітер (`SIM_WIND_SPD/DIR/TURB`), відмова мотора (`SIM_ENGINE_FAIL` + `SIM_ENGINE_MUL`), GPS (вимкнення, шум, глітч, затримка), компас (зміщення), баро (дрейф/глітч), вібрації (`SIM_VIB_*`), втрата RC (`SIM_RC_FAIL`), напруга АКБ (`SIM_BATT_VOLTAGE`), далекомір і оптичний потік (`RNGFND1_TYPE = 100`, `FLOW_TYPE = 10`). Це основа модулів «Відмовостійкість» і «Стійкість навігації».
- **Прискорення часу** `--speedup 10` для довгих місій; `--add-param-file` для своїх параметрів; `--out=udp:IP:14550` для зовнішньої GCS; `--no-mavproxy` для скриптів.
- **Зовнішні фізичні рушії**: Gazebo (`-f gazebo-iris`), RealFlight, X-Plane, JSBSim (крило), Webots — коли потрібна аеродинаміка/візуалізація; для логіки failsafe і місій вбудованої фізики достатньо.
- **Lua і companion**: скрипти (`SCR_ENABLE = 1`, тека `scripts/` поруч із запуском) і MAVLink-клієнти (`tcp:127.0.0.1:5760`, наступні — 5762/5763) працюють як на залізі.

### Логи SITL та їх читання
Логи пишуться в `logs/` робочої теки (`.BIN`), читаються тими самими інструментами, що й реальні (`mavexplorer.py`, Mission Planner, `pymavlink` — модуль «Python для даних»). Це і є сенс SITL: відпрацювати **метод** аналізу до реальних польотів.

### Розібраний приклад: перевірка місії з відмовою
`sim_vehicle.py -v ArduCopter -f hexa --console --map --speedup 5`; завантажити місію (`wp load mission.txt`), `mode auto`, `arm throttle`; на третій точці `param set SIM_ENGINE_FAIL 4` (мотор 3, бітова маска), спостерігати `RCOU`, висоту, рискання; повернути `0`; далі `param set SIM_RC_FAIL 1` у Loiter — перевірити `FS_THR_ENABLE`. Результат — у журнал тестів (модуль «Відмовостійкість»): сценарій, очікування, факт, лог. Сценарій можна записати як скрипт pymavlink — заготовка в `examples/sitl-pymavlink` репозиторію курсу.

### Де SITL бреше
Немає вібрацій і шуму моторів (фільтри не перевірити), ідеальна механіка, ESC без затримок, GPS із заданим шумом, немає завад на компас, крім змодельованих. Параметри тюнінгу PID із SITL **не переносяться** на реальний апарат; переносяться логіка, місії, скрипти, failsafe і навички аналізу.

{{diagram:sitl-param-layers|Слои параметров SITL: файл defaults задаёт значения по умолчанию, но eeprom.bin их перебивает; -w стирает eeprom.bin, иначе правка .parm может не подействовать.}}

{{diagram:sitl-arch|SITL: той самий код ArduCopter отримує сенсори від моделі фізики; MAVProxy роздає MAVLink на GCS і скрипти, логи пишуться як у польоті.}}

## practice
### Крок 1. Встановлення (Ubuntu)
```
git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git
cd ardupilot
Tools/environment_install/install-prereqs-ubuntu.sh -y
. ~/.profile
```

### Крок 2. Перший запуск
```
sim_vehicle.py -v ArduCopter -f octa-quad --console --map -w
```

У консолі MAVProxy:

```
mode guided
arm throttle
takeoff 10
```

Дрон злетить на 10 м. `mode rtl` поверне його додому.

### Крок 3. Керування скриптом (pymavlink)
SITL відкриває додаткові TCP-порти для зовнішніх клієнтів. Приклад зльоту скриптом:

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

```text
connected to system 1
alt 9.5 m after 6.6 s (sim time)
```

### Крок 4. Структура проєкту
```
ardupilot-lab/
  sitl/
    lib/          # shared code: connection, waiting for modes, helpers
    routes/       # data only: lists of waypoints, one format everywhere
    scenarios/    # commands only: takeoff, fly route X, inject failure, land
    run_sitl.sh   # start SITL + GCS with the right frame
```

### Що має вийти і що записати
- **Крок 1.** Встановлення триває 10–30 хвилин. Після нього в новому терміналі має знаходитися команда `sim_vehicle.py`. Якщо її немає, значить, не перечитано `~/.profile`.
- **Крок 2.** Перше збирання триває кілька хвилин, наступні запуски — секунди. У консолі видно, як GPS отримує фіксацію і EKF починає використовувати GPS, після цього арм проходить. Арм раніше за цей момент відхиляється повідомленням `PreArm`, і це нормально. `takeoff 10` піднімає апарат на 10 м. Після `mode rtl` він спочатку набирає висоту повернення `RTL_ALT` (у Copter 4.7 — `RTL_ALT_M`; за замовчуванням 15 м), якщо перебуває нижче, і лише потім летить додому. Запиши час набору 10 м і підсумкову висоту перед поверненням: так перевіряється, що параметри працюють так, як ти їх розумієш.
- **Крок 3.** Порти SITL: 5760 — SERIAL0, його займає MAVProxy; 5762 і 5763 — SERIAL1 і SERIAL2 для своїх клієнтів. Скрипт друкує зростаючу висоту і виходить на 9.5 м — але лише якщо `GLOBAL_POSITION_INT` взагалі йде на цей порт. У Copter потоки на SERIAL1 за замовчуванням вимкнені (`SR1_POSITION = 0`, у 4.7 — `MAV2_POSITION`), тому перед циклом запроси повідомлення через `MAV_CMD_SET_MESSAGE_INTERVAL`, інакше `recv_match` чекатиме вічно. Додай виведення часу від команди до виходу — це перша метрика сценарію.
- **Крок 4.** Маршрут — дані, сценарій — код. Приклад маршруту `routes/square_20m.csv`, рядки `north_m,east_m,alt_m` відносно точки зльоту:

```text
20,0,10
20,20,10
0,20,10
0,0,10
```

Сценарій читає файл, перетворює зміщення на цілі GUIDED і чекає на прибуття в радіус 1 м. Другий маршрут — той самий формат з іншими числами.

### Лабораторна
Напиши сценарій «зліт → коло → посадка» так, щоб координати лежали в `routes/`, а сценарій просто посилався на маршрут. Прожени його на двох різних маршрутах без правки коду сценарію.

Лабораторну зараховано, коли SITL запускається скриптом `run_sitl.sh` з потрібною рамою і наземку підключено, сценарій на pymavlink злітає, проходить маршрут і сідає, маршрути лежать у `routes/` окремо від сценаріїв, а два маршрути прогнано одним і тим самим кодом із записаним часом проходження.

Прогін цього кроку в SITL (ArduCopter 4.7.2); розбір і очікуваний результат — у російському оригіналі.

```
build/sitl/bin/arducopter --model + --speedup 10 -w \
  --defaults Tools/autotest/default_params/copter.parm,lab.parm \
  --home -35.363261,149.165230,584,353
```

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


## diagnostics
- **Симптом:** `sim_vehicle.py: command not found`
  - Можлива причина: не перечитано профіль після встановлення.
  - Що зробити: `. ~/.profile` або новий термінал.
- **Симптом:** скрипт висить на `wait_heartbeat`
  - Можлива причина: неправильна адреса або порт, SITL не запущено.
  - Що зробити: перевірити, що SITL працює, і номер порту.
- **Симптом:** `arm throttle` відмовляє з `PreArm`
  - Можлива причина: EKF ще не зійшовся після старту.
  - Що зробити: зачекати 10–20 с після запуску, читати повідомлення PreArm.
- **Симптом:** після експериментів дрон поводиться дивно
  - Можлива причина: залишилися змінені параметри.
  - Що зробити: перезапуск з `-w` для скидання.
- **Симптом:** sim_vehicle.py не стартує / помилки «waf configure»
  - Можлива причина: не встановлено залежності.
  - Що зробити: `Tools/environment_install/install-prereqs-ubuntu.sh -y`, перелогінитися, `git submodule update --init --recursive`.
- **Симптом:** GCS не підключається до SITL
  - Можлива причина: порти зайняті, MAVProxy не прокидає.
  - Що зробити: `--out=udp:127.0.0.1:14550` явно, перевірити `ss -lunp`.

## references
- Setting up SITL on Linux — ArduPilot Dev | https://ardupilot.org/dev/docs/setting-up-sitl-on-linux.html | primary | A
- Setting Up SITL — ArduPilot Dev | https://ardupilot.org/dev/docs/SITL-setup-landingpage.html | primary | A
- pymavlink — source code (GitHub) | https://github.com/ArduPilot/pymavlink | primary | A

## checklist
- SITL запускається, GCS підключено
- Зліт і RTL виконано з консолі MAVProxy
- Скрипт на pymavlink піднімає дрон
- Маршрути та сценарії рознесено по різних теках
- Знаю, як скинути параметри SITL
