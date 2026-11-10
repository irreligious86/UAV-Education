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
SITL (Software In The Loop) — то справжня прошивка ArduPilot, запущена на комп'ютері замість польотного контролера, із симулятором фізики замість реального світу. Тут можна задарма розбити сотню октокоптерів: переплутати параметри, вимкнути GPS у польоті, «впустити» мотор — і ніц тобі за то не буде. Модуль показує, як підняти SITL, підключити наземну станцію, керувати дроном скриптом на Python і поґаздувати в проєкті так, щоб маршрути та сценарії жили окремо.

## theory
### Як влаштований SITL
Прошивка збирається під Linux і міняється із симулятором фізики «показами датчиків» і «командами моторам». Вшитко інше — справжнє: ті самі параметри, режими, EKF, failsafe, логи. Тому все, що ти налагодив у SITL, переноситься на залізо майже без змін. Майже — бо в симуляції ідеальні вібрації, ідеальний зв'язок і чесний GPS, хіба шо ти їх сам зіпсуєш.

### sim_vehicle.py і MAVProxy
Скрипт `sim_vehicle.py` збирає прошивку, запускає її та консольну наземну станцію MAVProxy. Ключові прапорці:

- `-v ArduCopter` або `-v ArduPlane` — тип апарата;
- `-f octa-quad`, `-f quad`, `-f quadplane` — модель рами в симуляторі;
- `--console --map` — вікна консолі та карти;
- `-w` — скинути параметри до стандартних (придасться, коли експерименти зайшли гет не туди).

Наземну станцію (QGroundControl, Mission Planner) підключають до виходу MAVProxy через UDP — зазвичай вона його сама знаходить.

### Сценарій проти маршруту
Головне архітектурне рішення в навчальному проєкті: маршрут і сценарій живуть окремо.

- **Маршрут** — лиш послідовність точок в одному форматі. Перша точка — старт, остання — фініш.
- **Сценарій** — лиш команди: зліт, «пролети маршрут X», посадка, відмова мотора на третій точці. Координат у сценарії нема.

Так один маршрут проганяється різними сценаріями, а один сценарій — різними маршрутами. То та сама ідея, шо й розділення даних і логіки в кожнім нормальнім коді.

### Що вміє SITL, крім «політати»
- **Моделі рам** (`-f`): quad, hexa, octa, octa-quad (X8), y6, tri, heli, plane, quadplane, quadplane-tilttri/quadplane-tilt (тілтротори), rover, boat, sub — у кожної своя фізика в `libraries/SITL/SIM_*.cpp`; параметри за замовчуванням для моделі — `Tools/autotest/default_params/*.parm`.
- **Відмови та середовище** через `SIM_*`: вітер (`SIM_WIND_SPD/DIR/TURB`), відмова мотора (`SIM_ENGINE_FAIL` + `SIM_ENGINE_MUL`), GPS (вимкнення, шум, глітч, затримка), компас (зміщення), баро (дрейф/глітч), вібрації (`SIM_VIB_*`), втрата RC (`SIM_RC_FAIL`), напруга АКБ (`SIM_BATT_VOLTAGE`), далекомір і оптичний потік (`RNGFND1_TYPE = 100`, `FLOW_TYPE = 10`). То основа модулів «Відмовостійкість» і «Стійкість навігації».
- **Прискорення часу** `--speedup 10` для довгих місій; `--add-param-file` для своїх параметрів; `--out=udp:IP:14550` для зовнішньої GCS; `--no-mavproxy` для скриптів.
- **Зовнішні фізичні рушії**: Gazebo (`-f gazebo-iris`), RealFlight, X-Plane, JSBSim (крило), Webots — коли треба аеродинаміка/візуалізація; для логіки failsafe і місій вбудованої фізики вистачить.
- **Lua і companion**: скрипти (`SCR_ENABLE = 1`, тека `scripts/` поруч із запуском) і MAVLink-клієнти (`tcp:127.0.0.1:5760`, наступні — 5762/5763) працюють так само, як на залізі.

### Логи SITL та як їх читати
Логи пишуться в `logs/` робочої теки (`.BIN`), читаються тими самими інструментами, що й реальні (`mavexplorer.py`, Mission Planner, `pymavlink` — модуль «Python для даних»). Во в тім і сенс SITL: відпрацювати **метод** аналізу ще до реальних польотів.

### Розібраний приклад: перевірка місії з відмовою
`sim_vehicle.py -v ArduCopter -f hexa --console --map --speedup 5`; завантажити місію (`wp load mission.txt`), `mode auto`, `arm throttle`; на третій точці `param set SIM_ENGINE_FAIL 4` (мотор 3, бітова маска), пантрувати `RCOU`, висоту, рискання; повернути `0`; далі `param set SIM_RC_FAIL 1` у Loiter — перевірити `FS_THR_ENABLE`. Результат — до журналу тестів (модуль «Відмовостійкість»): сценарій, очікування, факт, лог. Сценарій можна записати як скрипт pymavlink — заготовка є в `examples/sitl-pymavlink` репозиторію курсу.

### Де SITL бреше
Нема вібрацій і шуму моторів (фільтри не перевіриш), ідеальна механіка, ESC без затримок, GPS із заданим шумом, нема завад на компас, крім змодельованих. Параметри тюнінгу PID із SITL **не переносяться** на реальний апарат; переносяться логіка, місії, скрипти, failsafe і навички аналізу.

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

Дрон злетить на 10 м. `mode rtl` поверне його до хати.

### Крок 3. Керування скриптом (pymavlink)
SITL відкриває додаткові TCP-порти для зовнішніх клієнтів. Ади, приклад зльоту скриптом:

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
- **Крок 1.** Встановлення триває 10–30 хвилин. Потім у новому терміналі має знаходитися команда `sim_vehicle.py`. Як її нема, значить, не перечитав `~/.profile`.
- **Крок 2.** Перше збирання триває кілька хвилин, наступні запуски — секунди. У консолі видно, як GPS ловить фіксацію і EKF починає використовувати GPS, і аж тоді арм проходить. Як армиш раніше, то дістанеш відмову з повідомленням `PreArm`, і то нормально. `takeoff 10` піднімає апарат на 10 м. Після `mode rtl` він спершу набирає висоту повернення `RTL_ALT` (у Copter 4.7 — `RTL_ALT_M`; за замовчуванням 15 м), як є нижче, і аж потім летить додому. Запиши час набору 10 м і підсумкову висоту перед поверненням: так перевіряєш, шо параметри працюють так, як ти їх розумієш.
- **Крок 3.** Порти SITL: 5760 — SERIAL0, його займає MAVProxy; 5762 і 5763 — SERIAL1 і SERIAL2 для своїх клієнтів. Скрипт друкує зростаючу висоту і виходить на 9.5 м — але лиш тоді, як `GLOBAL_POSITION_INT` взагалі йде на цей порт. У Copter потоки на SERIAL1 за замовчуванням вимкнені (`SR1_POSITION = 0`, у 4.7 — `MAV2_POSITION`), тому перед циклом запроси повідомлення через `MAV_CMD_SET_MESSAGE_INTERVAL`, бо інакше `recv_match` чекатиме вічно. Додай виведення часу від команди до виходу — то перша метрика сценарію.
- **Крок 4.** Маршрут — дані, сценарій — код. Приклад маршруту `routes/square_20m.csv`, рядки `north_m,east_m,alt_m` відносно точки зльоту:

```text
20,0,10
20,20,10
0,20,10
0,0,10
```

Сценарій читає файл, перетворює зміщення на цілі GUIDED і чекає, аж апарат прибуде в радіус 1 м. Другий маршрут — той самий формат з іншими числами.

### Лабораторна
Напиши сценарій «зліт → коло → посадка» так, щоб координати лежали в `routes/`, а сценарій лиш посилався на маршрут. Прожени його на двох різних маршрутах, не чіпаючи коду сценарію.

Лабораторну зараховано, коли SITL запускається скриптом `run_sitl.sh` з потрібною рамою і наземку підключено, сценарій на pymavlink злітає, проходить маршрут і сідає, маршрути лежать у `routes/` окремо від сценаріїв, а два маршрути прогнано одним і тим самим кодом із записаним часом проходження.

## diagnostics
- **Симптом:** `sim_vehicle.py: command not found`
  - Можлива причина: не перечитано профіль після встановлення.
  - Що зробити: `. ~/.profile` або новий термінал.
- **Симптом:** скрипт висить на `wait_heartbeat`
  - Можлива причина: хибна адреса або порт, SITL не запущено.
  - Що зробити: перевірити, ци SITL працює, і номер порту.
- **Симптом:** `arm throttle` відмовляє з `PreArm`
  - Можлива причина: EKF ще не зійшовся після старту.
  - Що зробити: зачекати 10–20 с по запуску, читати повідомлення PreArm.
- **Симптом:** по експериментах дрон поводиться дивно
  - Можлива причина: лишилися змінені параметри.
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
