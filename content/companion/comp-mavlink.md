---
id: comp-mavlink
title: "MAVLink и MAVSDK"
level: L2
readingTime: 30 мин
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
---

## summary
MAVLink — язык, на котором полётник говорит с наземной станцией, бортовым компьютером, телеметрией и твоими скриптами. Всё, что ты делал в SITL через pymavlink, — это MAVLink. Модуль разбирает протокол на уровне, достаточном чтобы писать свои клиенты: структуру пакета, систему и компонент, heartbeat, команды с подтверждением, параметры, потоки телеметрии. Два инструмента на выбор: pymavlink (низкий уровень, всё видно) и MAVSDK (высокоуровневый API).

## theory
### Пакет
MAVLink 2 — бинарный протокол поверх UART, UDP или TCP. Пакет: стартовый байт `0xFD`, длина, флаги, порядковый номер, `system_id`, `component_id`, трёхбайтный ID сообщения, полезная нагрузка, CRC. Контрольная сумма включает «соль» из описания сообщения, поэтому обе стороны обязаны использовать одинаковые определения (диалект). Сообщения описаны в XML: `common.xml` — общие, `ardupilotmega.xml` — расширения ArduPilot. Из XML генерируются библиотеки для C, Python и других языков.

### Система и компонент
`system_id` — аппарат (по умолчанию 1), `component_id` — что внутри: автопилот (1), камера, гимбал, бортовой компьютер. GCS обычно система 255. Команды адресуются паре система+компонент; бортовой компьютер — это отдельный компонент той же системы.

### Heartbeat
`HEARTBEAT` (ID 0) раз в секунду от каждого участника: тип аппарата, автопилот, режим, состояние арма. Пока нет heartbeat, нет и связи — поэтому любой клиент начинается с `wait_heartbeat()`. Отсутствие heartbeat от GCS дольше таймаута — это GCS-failsafe.

### Основные сообщения
- Телеметрия от аппарата: `SYS_STATUS` (1), `ATTITUDE` (30), `GLOBAL_POSITION_INT` (33), `RC_CHANNELS` (65), `BATTERY_STATUS` (147), `STATUSTEXT` (253 — текстовые сообщения, в том числе pre-arm).
- Команды: `COMMAND_LONG` (76) с кодом `MAV_CMD_*` и семью параметрами; ответ — `COMMAND_ACK` (77) с результатом. Примеры кодов: `MAV_CMD_COMPONENT_ARM_DISARM` (400), `MAV_CMD_NAV_TAKEOFF` (22), `MAV_CMD_DO_SET_MODE` (176).
- Частота потоков: `MAV_CMD_SET_MESSAGE_INTERVAL` (511) — попросить конкретное сообщение с нужным интервалом; `MAV_CMD_REQUEST_MESSAGE` (512) — один раз.
- Параметры: `PARAM_REQUEST_READ` (20) → `PARAM_VALUE` (22); запись `PARAM_SET` (23), подтверждение тем же `PARAM_VALUE`.
- Управление в GUIDED: `SET_POSITION_TARGET_LOCAL_NED` (84) и `SET_POSITION_TARGET_GLOBAL_INT` (86) — цель по позиции или скорости; основа offboard-управления с companion.
- Миссии: `MISSION_COUNT` (44), `MISSION_ITEM_INT` (73), `MISSION_REQUEST_INT` (51), `MISSION_ACK` (47) — диалог из модуля про миссии.

### Правило подтверждений
Команда без проверки `COMMAND_ACK` — это надежда, а не управление. Результат `MAV_RESULT_ACCEPTED` (0) означает «принято»; остальные коды — отказ, и его причина обычно приходит в `STATUSTEXT`.

### pymavlink против MAVSDK
- **pymavlink** — тонкая обёртка над протоколом: видишь каждое сообщение, подходит для обучения, диагностики и нестандартных вещей. Код многословный.
- **MAVSDK** (C++, Python) — высокоуровневые действия: `arm()`, `takeoff()`, `goto_location()`, подписки на телеметрию. Быстрее писать приложения, меньше видно изнутри. Исторически ближе к PX4, но с ArduPilot работает.

### Кадр MAVLink 2 побайтно
`FD | len | incompat_flags | compat_flags | seq | sysid | compid | msgid(3) | payload(len) | crc(2) | [signature(13)]`. `incompat_flags` бит 0 — пакет подписан; подпись — HMAC-SHA256 по секретному ключу + timestamp (защита от подмены команд по открытому радиоканалу — `MAV_SIGNING` в ArduPilot/QGC). CRC-16/MCRF4XX по кадру + `CRC_EXTRA` байт сообщения (из XML) — несовпадение диалектов = «молчание». Payload сжимается обрезанием нулевых байтов в конце (поэтому `len` меньше размера структуры). Параметры в `PARAM_VALUE` — всегда float (32 бит), целые упакованы «по байтам» (`MAV_PARAM_TYPE`), о чём легко споткнуться в pymavlink.

{{diagram:mavlink2-frame|Кадр MAVLink 2: заголовок, идентификаторы системы и компонента, полезная нагрузка, CRC с CRC_EXTRA, необязательная подпись.}}

### Потоки телеметрии: кто задаёт частоту
ArduPilot шлёт потоки по `SRx_*` параметрам порта (`SR2_EXTRA1` — ATTITUDE, `SR2_POSITION` — GLOBAL_POSITION_INT, `SR2_RAW_SENS` — RAW_IMU…) в Гц; современный способ — `MAV_CMD_SET_MESSAGE_INTERVAL` (511) от клиента: интервал в мкс (−1 — выключить, 0 — по умолчанию). PX4 — профили `MAV_x_MODE` (Normal/Onboard/OSD…). Порт 921600 бод вмещает ~90 КБ/с: ATTITUDE на 50 Гц + позиция 10 Гц + RAW_IMU 50 Гц — порядка 10 КБ/с, запас есть; на 57600 (радиомодем) — всё, что выше 5–10 Гц, захлёбывается.

### Разобранный пример: надёжная команда
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
`STATUSTEXT` параллельно объясняет отказ («PreArm: …»). MAVSDK делает то же под капотом — но понимать, что внутри, нужно, чтобы читать tlog при разборе.

## practice
### Шаг 1. Слушать телеметрию
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

### Шаг 2. Команда с подтверждением
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

### Шаг 3. Параметры
```python
m.mav.param_request_read_send(m.target_system, m.target_component, b"FS_THR_ENABLE", -1)
p = m.recv_match(type="PARAM_VALUE", blocking=True)
print(p.param_id, p.param_value)
```

### Шаг 4. Прослушать эфир
Запусти `mavproxy.py --master=tcp:127.0.0.1:5762` и команду `watch ATTITUDE`: видно живой поток сообщений. Это лучший способ понять, что именно летает по линии, прежде чем писать код.

## diagnostics
- **Симптом:** `wait_heartbeat()` не возвращается
  - Возможная причина: неверный адрес/порт, не тот диалект, скорость UART.
  - Что сделать: проверить порт, baud (57600 или 115200 на телеметрии), что SITL запущен.
- **Симптом:** команда «выполнилась», а аппарат ничего не сделал
  - Возможная причина: `COMMAND_ACK` не проверен, команда отклонена.
  - Что сделать: читать ACK и `STATUSTEXT`.
- **Симптом:** телеметрия приходит редко
  - Возможная причина: дефолтные интервалы потоков.
  - Что сделать: `MAV_CMD_SET_MESSAGE_INTERVAL` для нужных сообщений.
- **Симптом:** CRC-ошибки, сообщения «unknown»
  - Возможная причина: разные версии определений на двух сторонах.
  - Что сделать: обновить pymavlink/MAVSDK, использовать тот же диалект (ardupilotmega).

## references
- MAVLink Developer Guide | https://mavlink.io/en/ | primary | A
- MAVLink common message set | https://mavlink.io/en/messages/common.html | primary | A
- pymavlink — source code (GitHub) | https://github.com/ArduPilot/pymavlink | primary | A
- MAVSDK — Documentation | https://mavsdk.mavlink.io/main/en/ | primary | A
- MAVLink Interface — ArduPilot Dev | https://ardupilot.org/dev/docs/mavlink-basics.html | primary | A

## checklist
- Понимаю system_id / component_id и heartbeat
- Каждая команда проверяется по `COMMAND_ACK`
- Умею запросить телеметрию с нужной частотой
- Читаю и пишу параметры из кода
- Знаю, когда брать pymavlink, а когда MAVSDK
