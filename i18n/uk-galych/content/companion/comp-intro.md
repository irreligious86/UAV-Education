---
id: comp-intro
title: "Companion: навіщо і де межа"
level: L2
readingTime: 15 хв
firmware: MAVLink / Companion
status: published
added: 2026-11-07
tags:
  - companion
  - архітектура
related:
  - comp-mavlink
  - ap-intro
next:
  - comp-mavlink
source: content/companion/comp-intro.md
source_hash: 1c07d96adcd3
---

## summary
Польотний контролер робить одну річ: тримає апарат у повітрі й виконує прості команди, тисячі разів на секунду і без права ся завісити. Вшитко, що важче, — комп'ютерний зір, планування, зв'язок із мережею, власна логіка місій, — живе на бортовому комп'ютері (companion). Модуль проводить межу між ними, показує типові конфігурації від ESP32 до Jetson і пояснює головне правило: companion радить, FC вирішує.

## theory
### Хто за що відповідає
- **Польотний контролер (FC):** стабілізація, навігація, failsafe, мікшер. Жорсткий реальний час, мінімальна затримка, перевірений код. Він мусить літати, навіть як companion завис, перезавантажив ся або гет згорів.
- **Companion:** вшитко інше. Зір, нейромережі, обробка карт, складні сценарії, інтернет, логування в хмару, інтерфейс оператора.

{{diagram:companion-system|Companion і польотний контролер: FC тримає апарат у повітрі, companion бачить, планує і спілкує ся з мережею.}}

Межа проходить за вимогою до надійності: те, без чого апарат впаде, — на FC; те, без чого він просто вернеся до хати, — на companion.

### Як вони ся спілкують
По MAVLink через UART (телеметрійний порт FC) або через мережу. Companion — окремий компонент у тій самій системі MAVLink. Він може:

- читати телеметрію і параметри;
- переводити апарат у GUIDED і задавати цілі за позицією/швидкістю;
- завантажувати й запускати місії;
- отримувати текстові повідомлення і стан.

Чого він не робить: не керує моторами напряму й не підміняє стабілізацію. Навіть за offboard-керування FC сам пантрує обмеження і failsafe.

### Правило «радить, не керує»
Companion пропонує «лети в точку X зі швидкістю Y». FC перевіряє геозону, батарею, здоров'я EKF і виконує — або відмовляє. Як companion перестав слати команди, FC за таймаутом переходить у безпечний режим. Саме тому GCS-failsafe і таймаути GUIDED — то частина дизайну, а не завада.

### Типові платформи
- **ESP32 / ESP32-S3** — мікроконтролер із Wi-Fi і BLE. Телеметрія в телефон, міст MAVLink через Wi-Fi, датчики, індикація, невеликі сценарії. Linux нема, зате миттєвий старт і мілівати.
- **Raspberry Pi** — Linux, Python, камера. Маршрутизація MAVLink, відеопотік, скрипти місій, логи. Стандартний перший companion.
- **Jetson / Orange Pi з NPU** — коли треба нейромережі в реальному часі.

### Протоколи та ролі
ArduPilot чекає MAVLink 2 на `SERIALx_PROTOCOL = 2`; PX4 на companion-порту — той самий MAVLink або uXRCE-DDS для ROS 2. Для Betaflight/INAV companion у класичному сенсі трафляєся рідко: там є MSP, і бортовий комп'ютер зазвичай потрібен хіба для відео й телеметрії.

### Маршрутизація MAVLink
Один порт FC — кілька споживачів (GCS через 4G, скрипт на companion, логер): треба маршрутизатор. `mavlink-router` (C++, systemd-сервіс, конфіг з endpoint'ами UART/UDP/TCP) або `mavproxy.py --master=/dev/ttyAMA0 --out=udp:gcs-ip:14550 --out=udp:127.0.0.1:14551` — кожен клієнт дістає копію потоку, команди йдуть назад до FC. Швидкість UART companion-порту: 921600 бод (`SERIALx_BAUD = 921`) — інакше за потоків `SRx_*` на 10–50 Гц порт ся захлинає. Потік налаштовують з companion (`REQUEST_DATA_STREAM`/`SET_MESSAGE_INTERVAL`), а не за замовчуванням.

{{diagram:mavlink-routing|Типова схема маршрутизації MAVLink на борту з companion.}}

### Затримки і що можна доручити companion
Цикл команди «companion → FC → відгук»: UART 1–5 мс + обробка FC + динаміка контуру швидкості 0.3–1 с. То файно для «лети в точку» і стеження за ціллю (модуль «Стеження»), але не для стабілізації. Companion не повинен: керувати моторами, підміняти EKF (окрім передавання ExternalNav як джерела), обходити failsafe. Companion може: цілі GUIDED/Offboard, місії, параметри, ExternalNav/оптичний потік як джерело, камеру й відео, логи в хмару, інтерфейс оператора.

### Живлення, тепло, відмова
Raspberry Pi 4/5 — 1–3 А при 5 В з піками до 5 А: окремий BEC 5 В/5 А, не пад FC (модуль «Підключення периферії»); Jetson Orin Nano — 7–15 Вт, 19 В або 5 В/4 А залежно від модуля; радіатор і потік повітря обов'язкові — як почне ся тротлінг через температуру, затримки ростуть непередбачувано. Відмову companion (зависання, перезавантаження, обрив UART) FC мусить пережити: таймаути GUIDED, GCS-failsafe з усвідомленою дією, пілот із режимом без companion на тумблері. Перевіряють то висмикуванням UART у SITL/на стенді.

### Три типові архітектури
1. **Телеметрія і міст**: ESP32 з прошивкою-мостом (MAVLink через Wi-Fi/BLE у телефон, клас DroneBridge) — ніц не вирішує, лиш транслює.
2. **Pi + камера + скрипти**: Raspberry Pi 4/5, mavlink-router, Python-скрипти місій, відеопотік у GCS, оптичний потік/далекомір через MAVLink. Стандарт для навчання і прототипів.
3. **Jetson + ROS 2**: детекція/VIO на GPU, PX4 через uXRCE-DDS або ArduPilot через MAVROS/AP_DDS, вузли із захистами (модуль «Стеження»). Для серйозної автономії.
Стартові репозиторії для 2 і 3 — `examples/` у репозиторії курсу.

## practice
### Вибір платформи під задачу
1. Телеметрія на екран, індикація, налаштування з телефона — ESP32.
2. Відео, маршрутизація MAVLink, Python-сценарії — Raspberry Pi.
3. Розпізнавання об'єктів, стеження — Jetson.

### Чек-лист архітектури перед проєктом
1. Що робить апарат, як companion вимкнув ся в польоті? Відповідь мусить бути «переходить у режим X за таймаутом».
2. Яким портом і на якій швидкості йде MAVLink? Ци вистачає смуги під телеметрію і команди?
3. Як живить ся companion? Не з телеметрійного порту FC.
4. Хто логує: FC на SD-карту, companion — свої логи. Ци збігають ся мітки часу?
5. Як оновлювати софт companion у полі?

### Код спостерігача і що має вийти
```python
import time
from pymavlink import mavutil

# own identity: system 1 (this vehicle), component 191 = onboard computer
m = mavutil.mavlink_connection("tcp:127.0.0.1:5762", source_system=1,
                               source_component=mavutil.mavlink.MAV_COMP_ID_ONBOARD_COMPUTER)
m.wait_heartbeat()
with open("companion_track.csv", "a") as f:
    last_hb = 0.0
    while True:
        if time.time() - last_hb > 1.0:          # say "I am here" once a second, like a real companion
            m.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER,
                                 mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
            last_hb = time.time()
        p = m.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=1)
        if p:
            f.write(f"{time.monotonic():.3f},{p.lat / 1e7:.7f},{p.lon / 1e7:.7f},{p.relative_alt / 1000:.1f}\n")
            f.flush()
```
- У наземній станції (MAVLink Inspector) ади з'являє ся другий учасник: компонент 191 тої самої системи. Саме так companion виглядає для решти мережі.
- На порту 5762 (SERIAL1) у Copter потоки за замовчуванням вимкнено (`SR1_POSITION = 0`, у 4.7 — `MAV2_POSITION`), тому без запиту файл лишить ся порожній. Спершу запроси інтервал `GLOBAL_POSITION_INT` 1 000 000 мкс (`MAV_CMD_SET_MESSAGE_INTERVAL`) — тоді у файлі буде один рядок на секунду.
- **Відмова.** Зупини процес (Ctrl+C або `kill`) у польоті в LOITER. Апарат далі робить, що робив, бо ніц від companion не чекав. Запиши то як факт. Якби companion керував (GUIDED), зупинка довела б до таймауту уставок — то вже наступний модуль.

### Лабораторна
У SITL підніми «companion» як окремий процес на pymavlink (окремий `component_id`), який раз на секунду читає `GLOBAL_POSITION_INT` і пише у файл. Зупини процес у польоті й переконай ся, що апарат ніц не помітив.

Лабораторну зараховано, коли процес з окремим `component_id` видно в наземній станції і він пише позицію у файл, зупинка в польоті не змінила поведінки апарата, а у звіті записано, що стало би ся за відмови companion, який керує в GUIDED.

## diagnostics
- **Симптом:** апарат «завмирає» або падає, коли companion зависає
  - Можлива причина: companion робить те, що мав би робити FC (стабілізація, прямі команди моторам).
  - Що зробити: перенести критичне на FC, лишити companion хіба поради через GUIDED.
- **Симптом:** FC не бачить companion
  - Можлива причина: не той порт, протокол ци швидкість; переплутано TX/RX.
  - Що зробити: `SERIALx_PROTOCOL`, `SERIALx_BAUD`, перевірка heartbeat через MAVProxy.
- **Симптом:** companion перезавантажує ся на газу
  - Можлива причина: живлення від слабкого BEC або просідання.
  - Що зробити: окремий BEC/стабілізатор із запасом за струмом.

## references
- Companion Computers — ArduPilot Dev | https://ardupilot.org/dev/docs/companion-computers.html | primary | A
- Communicating with Raspberry Pi via MAVLink — ArduPilot Dev | https://ardupilot.org/dev/docs/raspberry-pi-via-mavlink.html | primary | A
- Companion Computers — PX4 User Guide | https://docs.px4.io/main/en/companion_computer/ | primary | A

## checklist
- Можу пояснити, що лишає ся на FC і чому
- Знаю, що робить апарат, як companion відмовить
- Вибрав-єм платформу під задачу, а не навпаки
- Companion живить ся не від порту телеметрії
- Companion виступає окремим компонентом MAVLink
