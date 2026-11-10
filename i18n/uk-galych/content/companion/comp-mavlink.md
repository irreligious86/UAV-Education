---
id: comp-mavlink
title: "MAVLink і MAVSDK"
level: L2
readingTime: 30 хв
firmware: MAVLink 2
status: published
added: 2026-11-07
tags:
  - MAVLink
  - pymavlink
  - MAVSDK
related:
  - ap-sitl
  - comp-esp32
next:
  - comp-esp32
source: content/companion/comp-mavlink.md
source_hash: e3e4078d2bf6
---

## summary
MAVLink — то мова, якою польотний контролер говорить із наземною станцією, бортовим комп'ютером, телеметрією і твоїми скриптами. Вшитко, що ти робив у SITL через pymavlink, — то MAVLink. Модуль розбирає протокол настільки, щоб ти міг писати власні клієнти: структуру пакета, систему й компонент, heartbeat, команди з підтвердженням, параметри, потоки телеметрії. Два інструменти на вибір: pymavlink (низький рівень, вшитко видно) і MAVSDK (високорівневий API).

## theory
### Пакет
MAVLink 2 — бінарний протокол поверх UART, UDP або TCP. Пакет: стартовий байт `0xFD`, довжина, прапорці, порядковий номер, `system_id`, `component_id`, трибайтовий ID повідомлення, корисне навантаження, CRC. Контрольна сума включає «сіль» з опису повідомлення, тому обидва боки мусять вживати однакові визначення (діалект). Повідомлення описано в XML: `common.xml` — загальні, `ardupilotmega.xml` — розширення ArduPilot. З XML генерують бібліотеки для C, Python та інших мов.

### Система і компонент
`system_id` — апарат (за замовчуванням 1), `component_id` — що всередині: автопілот (1), камера, гімбал, бортовий комп'ютер. GCS зазвичай система 255. Команди адресують парі система+компонент; бортовий комп'ютер — то окремий компонент тої самої системи.

### Heartbeat
`HEARTBEAT` (ID 0) раз на секунду від кожного учасника: тип апарата, автопілот, режим, стан арму. Нема heartbeat — нема й зв'язку, тому кожен клієнт ся починає з `wait_heartbeat()`. Як від GCS нема heartbeat довше за таймаут — то GCS-failsafe.

### Основні повідомлення
- Телеметрія від апарата: `SYS_STATUS` (1), `ATTITUDE` (30), `GLOBAL_POSITION_INT` (33), `RC_CHANNELS` (65), `BATTERY_STATUS` (147), `STATUSTEXT` (253 — текстові повідомлення, зокрема pre-arm).
- Команди: `COMMAND_LONG` (76) з кодом `MAV_CMD_*` і сімома параметрами; відповідь — `COMMAND_ACK` (77) з результатом. Приклади кодів: `MAV_CMD_COMPONENT_ARM_DISARM` (400), `MAV_CMD_NAV_TAKEOFF` (22), `MAV_CMD_DO_SET_MODE` (176).
- Частота потоків: `MAV_CMD_SET_MESSAGE_INTERVAL` (511) — попросити конкретне повідомлення з потрібним інтервалом; `MAV_CMD_REQUEST_MESSAGE` (512) — один раз.
- Параметри: `PARAM_REQUEST_READ` (20) → `PARAM_VALUE` (22); запис `PARAM_SET` (23), підтвердження тим самим `PARAM_VALUE`.
- Керування в GUIDED: `SET_POSITION_TARGET_LOCAL_NED` (84) і `SET_POSITION_TARGET_GLOBAL_INT` (86) — ціль за позицією або швидкістю; основа offboard-керування з companion.
- Місії: `MISSION_COUNT` (44), `MISSION_ITEM_INT` (73), `MISSION_REQUEST_INT` (51), `MISSION_ACK` (47) — діалог із модуля про місії.

### Правило підтверджень
Команда без перевірки `COMMAND_ACK` — то надія, а не керування. Результат `MAV_RESULT_ACCEPTED` (0) значить «прийнято»; решта кодів — відмова, і її причина зазвичай приходить у `STATUSTEXT`.

### pymavlink проти MAVSDK
- **pymavlink** — тонка обгортка над протоколом: бачиш кожне повідомлення, файно надає ся для навчання, діагностики й нестандартних речей. Код багатослівний.
- **MAVSDK** (C++, Python) — високорівневі дії: `arm()`, `takeoff()`, `goto_location()`, підписки на телеметрію. Застосунки пишеш шпаркіше, але зсередини видно менше. Історично ближчий до PX4, але з ArduPilot теж працює.

### Кадр MAVLink 2 побайтово
`FD | len | incompat_flags | compat_flags | seq | sysid | compid | msgid(3) | payload(len) | crc(2) | [signature(13)]`. `incompat_flags` біт 0 — пакет підписано; підпис — перші 48 біт SHA-256 від (секретний ключ + заголовок + payload + CRC + link_id + timestamp), не HMAC (захист від підміни команд відкритим радіоканалом — ключ задають у Mission Planner/QGC і передають автопілоту повідомленням `SETUP_SIGNING`). CRC-16/MCRF4XX по кадру + байт `CRC_EXTRA` повідомлення (з XML) — розбіжність діалектів = «мовчання». Payload ся стискає обрізанням нульових байтів у кінці (тому `len` менший за розмір структури). Параметри в `PARAM_VALUE` — завжди float (32 біт), цілі ArduPilot передає приведенням до float (C-cast), PX4 — побайтово; тип значення — у `param_type` (`MAV_PARAM_TYPE`), і на тім легко ся спіткнути в pymavlink.

{{diagram:mavlink2-frame|Кадр MAVLink 2: заголовок, ідентифікатори системи й компонента, корисне навантаження, CRC з CRC_EXTRA, необов'язковий підпис.}}

### Потоки телеметрії: хто задає частоту
ArduPilot шле потоки за параметрами порту `SRx_*` (`SR2_EXTRA1` — ATTITUDE, `SR2_POSITION` — GLOBAL_POSITION_INT, `SR2_RAW_SENS` — RAW_IMU…) у Гц; сучасний спосіб — `MAV_CMD_SET_MESSAGE_INTERVAL` (511) від клієнта: інтервал у мкс (−1 — вимкнути, 0 — за замовчуванням). PX4 — профілі `MAV_x_MODE` (Normal/Onboard/OSD…). Порт 921600 бод вміщує ~90 КБ/с: ATTITUDE на 50 Гц + позиція 10 Гц + RAW_IMU 50 Гц — коло 10 КБ/с, запас є; на 57600 (радіомодем) вшитко, що вище 5–10 Гц, ся захлинає.

### Розібраний приклад: надійна команда
```python
def cmd(m, command, *params, retries=3, timeout=1.0):
    """Send COMMAND_LONG and wait for a matching ACK; retry on timeout; raise on rejection."""
    p = list(params) + [0] * (7 - len(params))
    for _ in range(retries):
        m.mav.command_long_send(m.target_system, m.target_component, command, 0, *p)
        t0 = time.time()
        while time.time() - t0 < timeout:
            ack = m.recv_match(type="COMMAND_ACK", blocking=True, timeout=timeout)
            if ack and ack.command == command:
                if ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED: return True
                if ack.result == mavutil.mavlink.MAV_RESULT_IN_PROGRESS: continue
                raise RuntimeError(f"cmd {command} rejected: result {ack.result}")
    raise TimeoutError(f"cmd {command}: no ACK")
```
`STATUSTEXT` паралельно пояснює відмову («PreArm: …»). MAVSDK робить те саме під капотом — але розуміти, що всередині, треба, щоб читати tlog під час розбору.

## practice
### Крок 1. Слухати телеметрію
```python
from pymavlink import mavutil

m = mavutil.mavlink_connection("tcp:127.0.0.1:5762")
m.wait_heartbeat()
print(f"system {m.target_system} component {m.target_component}")

# ask for ATTITUDE at 10 Hz (interval in microseconds)
m.mav.command_long_send(
    m.target_system, m.target_component,
    mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
    mavutil.mavlink.MAVLINK_MSG_ID_ATTITUDE, 100_000, 0, 0, 0, 0, 0)

for _ in range(20):
    msg = m.recv_match(type=["ATTITUDE", "STATUSTEXT"], blocking=True)
    if msg.get_type() == "ATTITUDE":
        print(f"roll {msg.roll:+.2f} pitch {msg.pitch:+.2f} yaw {msg.yaw:+.2f} rad")
    else:
        print("FC says:", msg.text)
```

### Крок 2. Команда з підтвердженням
```python
def command(m, cmd, *params):
    m.mav.command_long_send(m.target_system, m.target_component, cmd, 0, *params)
    ack = m.recv_match(type="COMMAND_ACK", blocking=True, timeout=3)
    if ack is None or ack.command != cmd:
        raise RuntimeError(f"no ACK for {cmd}")
    if ack.result != mavutil.mavlink.MAV_RESULT_ACCEPTED:
        raise RuntimeError(f"command {cmd} rejected: result {ack.result}")

m.set_mode(m.mode_mapping()["GUIDED"])
command(m, mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 1, 0, 0, 0, 0, 0, 0)
command(m, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 15)
```

### Крок 3. Параметри
```python
m.mav.param_request_read_send(m.target_system, m.target_component, b"FS_THR_ENABLE", -1)
p = m.recv_match(type="PARAM_VALUE", blocking=True)
print(p.param_id, p.param_value)
```

### Крок 4. Прослухати ефір
Запусти `mavproxy.py --master=tcp:127.0.0.1:5762` і команду `watch ATTITUDE`: ади, видно живий потік повідомлень. То найліпший спосіб зрозуміти, що саме літає лінією, заки сядеш писати код.

### Що має вийти і що записати
- **Крок 1.** У SITL перший heartbeat приходить від системи 1, компонента 1 (автопілот). Частоту не бери на віру — виміряй: збери 50 повідомлень `ATTITUDE` і поділи кількість інтервалів (49) на різницю `time_boot_ms` першого й останнього (у секундах). Очікувано 9.5–10.5 Гц при інтервалі 100 000 мкс. Як `ATTITUDE` не приходить гет зовсім, команда інтервалу не дійшла: на порту 5762 у Copter частота за замовчуванням (`SR1_EXTRA1`, у 4.7 — `MAV2_EXTRA1`) дорівнює 0. Коло 4 Гц — то частота, яку MAVProxy сам запитує на своєму порту 5760.
- **Крок 2.** Повтори арм зразу після старту SITL, заки EKF не зійшов ся. Прийде `COMMAND_ACK` з результатом 4 (`MAV_RESULT_FAILED`), а причина — у `STATUSTEXT` з префіксом `PreArm:`. Запиши обидва рядки: так виглядає відмова, яку код мусить обробити. Коди результату: 0 — прийнято, 1 — тимчасово відхилено, 2 — заборонено, 3 — не підтримує ся, 4 — помилка, 5 — виконує ся.
- **Крок 3.** Запис параметра — то `PARAM_SET` і відповідний `PARAM_VALUE` з новим значенням. Доки відповідь не прийшла, параметр не записано:

```python
m.mav.param_set_send(m.target_system, m.target_component, b"FS_THR_ENABLE", 1,
                     mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=3)
assert p and p.param_id == "FS_THR_ENABLE" and p.param_value == 1, p
```

- **Крок 4.** У `watch ATTITUDE` видно частоту й живі кути. Порівняй її з виміряною в кроці 1. У польоті з модуля «SITL» кути ся міняють на кожному маневрі — так перевіряють, що потік живий, а не застиглий.

Лабораторну зараховано, коли частоту `ATTITUDE` виміряно (а не задано) і вона близька до 10 Гц, відмову арму та успішний арм розібрано за `COMMAND_ACK` і `STATUSTEXT`, параметр записано з перевіркою відповіді `PARAM_VALUE`, ефір переглянуто в MAVProxy.

## diagnostics
- **Симптом:** `wait_heartbeat()` не вертає ся
  - Можлива причина: хибна адреса/порт, не той діалект, швидкість UART.
  - Що зробити: перевірити порт, baud (57600 або 115200 на телеметрії), ци SITL запущено.
- **Симптом:** команда «виконала ся», а апарат ніц не зробив
  - Можлива причина: `COMMAND_ACK` не перевірено, команду відхилено.
  - Що зробити: читати ACK і `STATUSTEXT`.
- **Симптом:** телеметрія приходить рідко
  - Можлива причина: інтервали потоків за замовчуванням.
  - Що зробити: `MAV_CMD_SET_MESSAGE_INTERVAL` для потрібних повідомлень.
- **Симптом:** CRC-помилки, повідомлення «unknown»
  - Можлива причина: різні версії визначень з двох боків.
  - Що зробити: оновити pymavlink/MAVSDK, вживати той самий діалект (ardupilotmega).

## references
- MAVLink Developer Guide | https://mavlink.io/en/ | primary | A
- MAVLink common message set | https://mavlink.io/en/messages/common.html | primary | A
- pymavlink — source code (GitHub) | https://github.com/ArduPilot/pymavlink | primary | A
- MAVSDK — Documentation | https://mavsdk.mavlink.io/main/en/ | primary | A
- MAVLink Interface — ArduPilot Dev | https://ardupilot.org/dev/docs/mavlink-basics.html | primary | A

## checklist
- Розумію system_id / component_id і heartbeat
- Кожну команду перевіряю за `COMMAND_ACK`
- Вмію запитати телеметрію з потрібною частотою
- Читаю й пишу параметри з коду
- Знаю, коли брати pymavlink, а коли MAVSDK
