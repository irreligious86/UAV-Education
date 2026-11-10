---
id: mav-component
title: "Власний компонент MAVLink: датчик, параметри, повідомлення"
level: L3
readingTime: 45 хв
firmware: ArduPilot · PX4
status: published
added: 2026-11-08
tags:
  - MAVLink
  - компонент
  - DISTANCE_SENSOR
  - ESP32
  - параметри
related:
  - mav-routing
  - comp-esp32
  - est-alt-sources
next:
  - mav-sdk
source: content/companion/mav-component.md
source_hash: 6a095d5ce136
---

## summary
Досі companion був клієнтом: читав телеметрію й надсилав команди. Тут він стає **учасником системи** — компонентом зі своїм compid, heartbeat, параметрами та повідомленнями, які автопілот використовує як дані датчика. Це шлях, яким до ArduPilot і PX4 підключаються далекоміри, датчики перешкод, зовнішня навігація, гімбали та корисне навантаження. Модуль розбирає обов'язки компонента (heartbeat, відповіді на запити, параметри), повідомлення датчиків (`DISTANCE_SENSOR`, `OBSTACLE_DISTANCE`, `ODOMETRY`/`VISION_POSITION_ESTIMATE`), налагоджувальні (`NAMED_VALUE_*`, `DEBUG_VECT`), і дві реалізації: Python на companion і C на ESP32. Лабораторна: віртуальний далекомір, який ArduPilot SITL приймає як `RNGFND1`, потім той самий компонент на ESP32.

## theory
### Що робить компонент «правильним»
1. **Heartbeat** 1 Гц зі своїм `MAV_TYPE` (для датчика — `MAV_TYPE_GENERIC` або специфічний), `MAV_AUTOPILOT_INVALID` (не автопілот!), sysid своєї системи (того самого апарата), унікальним compid. Без heartbeat маршрутизація до компонента не працює (модуль mav-routing).
2. **Відповідає на адресовані йому запити**: `COMMAND_LONG` з його compid → `COMMAND_ACK` (навіть UNSUPPORTED — краще, ніж тиша, на якій клієнт висітиме до таймауту); `MAV_CMD_REQUEST_MESSAGE` для опису на кшталт `COMPONENT_INFORMATION`/`AUTOPILOT_VERSION` — за можливості.
3. **Власні параметри** — якщо вони потрібні, за протоколом параметрів: відповідає на `PARAM_REQUEST_LIST`/`PARAM_REQUEST_READ`/`PARAM_SET` від GCS, адресовані його compid; зберігає значення в енергонезалежній пам'яті. QGC і Mission Planner покажуть їх в окремій групі компонента.
4. **Не дублює чужих повідомлень** і не надсилає автопілоту команд, які конфліктують з оператором.
5. **Деградує чесно**: у разі втрати вимірювань перестає надсилати повідомлення (або ставить ознаку недостовірності), а не продовжує видавати останнє значення. Автопілот виявить таймаут і відключить джерело.

### Датчик відстані: DISTANCE_SENSOR (132)
Поля: `time_boot_ms`, `min_distance`/`max_distance`/`current_distance` у **сантиметрах**, `type` (`MAV_DISTANCE_SENSOR_LASER`, `_ULTRASOUND`, `_RADAR`…), `id`, `orientation` (`MAV_SENSOR_ROTATION_PITCH_270` = вниз, `_NONE` = вперед…), `covariance` (255 — невідома), а в extension-полях — `horizontal_fov`, `vertical_fov`, `quaternion`, `signal_quality` (0 — невідомо, 1 — сигнал недостовірний … 100 — відмінно).

ArduPilot: `RNGFND1_TYPE = 10` (MAVLink), `RNGFND1_ORIENT = 25` (вниз), `RNGFND1_MIN`/`RNGFND1_MAX` (у нових версіях у метрах, у старих `_MIN_CM`/`_MAX_CM`). Значення поза діапазоном [min, max] автопілот вважає «поза дальністю», а не вимірюванням. Частота — 10–50 Гц; таймаут MAVLink-далекоміра в ArduPilot — 500 мс: якщо пакети надходять рідше ніж ~2 Гц або з пропусками довшими за 0.5 с, датчик вважається таким, що відвалився. Далекомір униз використовується для висоти над землею (`RFND` у логу, джерело EKF POSZ = далекомір, посадка, террейн-фоловінг); датчики з іншими орієнтаціями — для обходу перешкод (`PRX` proximity, `PRX1_TYPE = 2` MAVLink).

### Перешкоди та зовнішня навігація
- `OBSTACLE_DISTANCE` (330): масив із 72 відстаней за секторами (`increment` градусів на сектор, `angle_offset`), для 2D-лідарів і стереокамер → proximity в ArduPilot (`PRX1_TYPE = 2`), collision prevention у PX4.
- `VISION_POSITION_ESTIMATE` (102), `VISION_SPEED_ESTIMATE` (103), `ODOMETRY` (331): поза/швидкість від VIO або motion capture → EKF ArduPilot як ExternalNav (`EK3_SRC1_POSXY = 6`), PX4 — як vision (`EKF2_EV_CTRL`). Тут важливі час (мітки `usec`, TIMESYNC) і системи координат (FRD/NED проти FLU/ENU — модуль math-linalg-rot).

### Налагоджувальні повідомлення
Щоб вивести своє значення в GCS і в лог без власного діалекту: `NAMED_VALUE_FLOAT` (251) — ім'я до 10 символів і float; `NAMED_VALUE_INT` (252); `DEBUG_VECT` (250) — ім'я і три float. Mission Planner показує їх у Quick tab/графіках, ArduPilot пише отримані `NAMED_VALUE_FLOAT` у лог (`NVAL`), PX4 — в ulog топіками debug. Для постійної інтеграції — власний діалект (модуль mav-protocol) або `TUNNEL` (385).

### Реалізація на Python
`examples/mavlink/virtual_rangefinder.py` — компонент цілком: свій compid (`MAV_COMP_ID_PERIPHERAL`), heartbeat, читання `GLOBAL_POSITION_INT` для імітації вимірювання, публікація `DISTANCE_SENSOR` із заданою частотою, обмеження діапазону. Структура (опитування, надсилання з фіксованою частотою, heartbeat окремо) однакова для будь-якого датчика: заміни `measurement_cm()` на читання реального лідара по UART/I2C — і це робочий драйвер.

### Реалізація на ESP32 (C)
На мікроконтролері використовують згенеровану C-бібліотеку (header-only `c_library_v2` або власну з mavgen):

```c
#include <common/mavlink.h>

static void send_distance(uart_port_t uart, uint16_t dist_cm) {
    mavlink_message_t msg;
    uint8_t buf[MAVLINK_MAX_PACKET_LEN];
    mavlink_msg_distance_sensor_pack(1, MAV_COMP_ID_PERIPHERAL, &msg,
        esp_timer_get_time() / 1000, 20, 4000, dist_cm,
        MAV_DISTANCE_SENSOR_LASER, 0, MAV_SENSOR_ROTATION_PITCH_270, 255,
        0, 0, NULL, 0);                                   /* fovs, quaternion, signal_quality: extensions */
    uint16_t len = mavlink_msg_to_send_buffer(buf, &msg);
    uart_write_bytes(uart, (const char *)buf, len);
}
```

Прийом — побайтово через `mavlink_parse_char(chan, byte, &msg, &status)` у задачі, що читає UART. Окрема задача FreeRTOS надсилає heartbeat раз на секунду; надсилання з кількох задач — під м'ютексом, інакше кадри перемішаються в UART. Подробиці щодо ESP-IDF і UART — модуль comp-esp32.

### Тестування компонента
Компонент тестується на трьох рівнях: (1) юніт — функція вимірювання/пакування (`test_component.py`, обмеження діапазону); (2) інтеграція з фейковим апаратом — повідомлення дійшло з правильними compid і орієнтацією; (3) SITL — автопілот справді використовує дані (`RFND.Dist` у логу збігається з тим, що надсилали, `RNGFND1` у статусі healthy). Лише третій рівень доводить, що параметри автопілота й повідомлення узгоджені.

{{diagram:mav-component-seq|Мінімум «правильного» компонента: HEARTBEAT зі своїм compid, дані датчика, параметри на запит і відповідь на кожну команду.}}

## practice
### Крок 1. Тести компонента
```bash
cd examples/mavlink
python -m pytest -q tests/test_component.py
```
Прочитай, що перевіряють тести: compid відправника, орієнтація, діапазон значень.

### Крок 2. ArduPilot SITL приймає далекомір
Запусти SITL (модуль ap-sitl), задай `RNGFND1_TYPE = 10`, `RNGFND1_ORIENT = 25`, `RNGFND1_MAX` = 40 м (або `RNGFND1_MAX_CM = 4000` на старих версіях), перезавантаж. Запусти `virtual_rangefinder.py --master udpin:0.0.0.0:14551` (скрипт слухає окремий вихід SITL/роутера `--out=udp:127.0.0.1:14551` і відповідає на адресу, з якої прийшов потік). Злети на 10 м: у Mission Planner `rangefinder1` показує ~10 м мінус «рельєф», у логу — `RFND`. Зупини скрипт — за кілька сотень мілісекунд автопілот має перестати вважати далекомір здоровим.

### Крок 3. Параметр компонента
Додай компоненту параметр `RF_OFFSET_CM` (зміщення встановлення): відповіді на `PARAM_REQUEST_LIST`/`READ`/`SET` для свого compid, зберігання в JSON-файлі. Перевір, що QGC бачить його в групі компонента і що зміна з QGC одразу змінює `DISTANCE_SENSOR`.

### Крок 4. ESP32
Перенеси компонент на ESP32: UART до TELEM-порту SITL через USB-UART адаптер (або до реального FC), heartbeat + `DISTANCE_SENSOR` із синусом замість датчика; потім підключи реальний далекомір (VL53L1X по I2C або TFmini по UART). Звір `RFND` у логу з показами.

Лабораторну зараховано, коли проходять тести, SITL використовує віртуальний далекомір (лог), параметр компонента змінюється з GCS і є ESP32-версія хоча б із синтетичними даними.

## diagnostics
- **Симптом:** SITL не бачить далекоміра, хоча пакети йдуть
  - Можлива причина: не перезавантажено після `RNGFND1_TYPE`; орієнтація не збігається з `RNGFND1_ORIENT`; значення поза min/max.
  - Що зробити: перезавантаження; ORIENT 25 ↔ PITCH_270; перевірити одиниці (см проти м).
- **Симптом:** далекомір «блимає» healthy/unhealthy
  - Можлива причина: частота надсилання низька або нестабільна (сон у циклі прийому).
  - Що зробити: надсилання за таймером ≥ 10 Гц, прийом неблокувальний.
- **Симптом:** QGC не показує параметрів компонента
  - Можлива причина: немає heartbeat від компонента або відповіді йдуть із compid автопілота.
  - Що зробити: heartbeat; відповідати зі своїм compid і враховувати target_component у запиті.
- **Симптом:** на ESP32 періодично надходять «биті» кадри
  - Можлива причина: дві задачі пишуть в UART одночасно.
  - Що зробити: одна задача-відправник із чергою або м'ютекс на UART.

## references
- MAVLink — DISTANCE_SENSOR, OBSTACLE_DISTANCE, ODOMETRY (common.xml) | https://mavlink.io/en/messages/common.html | primary | A
- ArduPilot — Rangefinder parameters (RNGFND1_TYPE 10: MAVLink) | https://ardupilot.org/copter/docs/common-rangefinder-landingpage.html | primary | A
- ArduPilot — AP_RangeFinder (source) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/AP_RangeFinder | primary | A
- MAVLink — c_library_v2 (generated C headers) | https://github.com/mavlink/c_library_v2 | primary | A
- PX4 — Distance sensors and MAVLink | https://docs.px4.io/main/en/sensor/rangefinders.html | primary | A

## checklist
- Знаю обов'язки компонента: heartbeat, відповіді, власні параметри, чесна деградація
- Заповнюю DISTANCE_SENSOR правильно (одиниці, орієнтація, діапазон)
- Налаштовую ArduPilot на MAVLink-далекомір і перевіряю за логом
- Використовую NAMED_VALUE_* для швидкого налагодження
- Реалізую компонент на Python і на ESP32 (mavlink_parse_char, м'ютекс)
- Тестую на трьох рівнях: юніт, фейковий апарат, SITL
