---
id: mav-component
title: "Свой компонент MAVLink: датчик, параметры, сообщения"
level: L3
readingTime: 45 мин
firmware: ArduPilot · PX4
status: published
added: 2026-11-08
tags:
  - MAVLink
  - компонент
  - DISTANCE_SENSOR
  - ESP32
  - параметры
related:
  - mav-routing
  - comp-esp32
  - est-alt-sources
next:
  - mav-sdk
---

## summary
До сих пор companion был клиентом: читал телеметрию и слал команды. Здесь он становится **участником системы** — компонентом со своим compid, heartbeat, параметрами и сообщениями, которые автопилот использует как данные датчика. Это путь, которым к ArduPilot и PX4 подключаются дальномеры, датчики препятствий, внешняя навигация, гимбалы и полезная нагрузка. Модуль разбирает обязанности компонента (heartbeat, ответы на запросы, параметры), сообщения датчиков (`DISTANCE_SENSOR`, `OBSTACLE_DISTANCE`, `ODOMETRY`/`VISION_POSITION_ESTIMATE`), отладочные (`NAMED_VALUE_*`, `DEBUG_VECT`), и две реализации: Python на companion и C на ESP32. Лабораторная: виртуальный дальномер, который ArduPilot SITL принимает как `RNGFND1`, затем тот же компонент на ESP32.

## theory
### Что делает компонент «правильным»
1. **Heartbeat** 1 Гц со своим `MAV_TYPE` (для датчика — `MAV_TYPE_GENERIC` или специфичный), `MAV_AUTOPILOT_INVALID` (не автопилот!), sysid своей системы (того же аппарата), уникальным compid. Без heartbeat маршрутизация до компонента не работает (модуль mav-routing).
2. **Отвечает на адресованные ему запросы**: `COMMAND_LONG` с его compid → `COMMAND_ACK` (даже UNSUPPORTED — лучше, чем тишина, на которой клиент будет висеть до таймаута); `MAV_CMD_REQUEST_MESSAGE` для `COMPONENT_INFORMATION`/`AUTOPILOT_VERSION`-подобного описания — по возможности.
3. **Свои параметры** — если они нужны, по протоколу параметров: отвечает на `PARAM_REQUEST_LIST`/`PARAM_REQUEST_READ`/`PARAM_SET` от GCS, адресованные его compid; хранит значения в энергонезависимой памяти. QGC и Mission Planner покажут их в отдельной группе компонента.
4. **Не дублирует чужие сообщения** и не шлёт команды автопилоту, которые конфликтуют с оператором.
5. **Деградирует честно**: при потере измерений перестаёт слать сообщение (или ставит признак недостоверности), а не продолжает выдавать последнее значение. Автопилот обнаружит таймаут и отключит источник.

### Датчик расстояния: DISTANCE_SENSOR (132)
Поля: `time_boot_ms`, `min_distance`/`max_distance`/`current_distance` в **сантиметрах**, `type` (`MAV_DISTANCE_SENSOR_LASER`, `_ULTRASOUND`, `_RADAR`…), `id`, `orientation` (`MAV_SENSOR_ROTATION_PITCH_270` = вниз, `_NONE` = вперёд…), `covariance` (255 — неизвестна), а в extension-полях — `horizontal_fov`, `vertical_fov`, `quaternion`, `signal_quality` (0 — неизвестно, 1 — плохо … 100 — отлично).

ArduPilot: `RNGFND1_TYPE = 10` (MAVLink), `RNGFND1_ORIENT = 25` (вниз), `RNGFND1_MIN`/`RNGFND1_MAX` (в новых версиях в метрах, в старых `_MIN_CM`/`_MAX_CM`). Значения вне диапазона [min, max] автопилот считает «вне дальности», а не измерением. Частота — 10–50 Гц; реже 5 Гц автопилот может посчитать датчик отвалившимся. Дальномер вниз используется для высоты над землёй (`RFND` в логе, EKF источник POSZ = дальномер, посадка, террейн-фоллоуинг); датчики по другим ориентациям — для обхода препятствий (`PRX` proximity, `PRX1_TYPE = 2` MAVLink).

### Препятствия и внешняя навигация
- `OBSTACLE_DISTANCE` (330): массив из 72 расстояний по секторам (`increment` градусов на сектор, `angle_offset`), для 2D-лидаров и стереокамер → proximity в ArduPilot (`PRX1_TYPE = 2`), collision prevention в PX4.
- `VISION_POSITION_ESTIMATE` (102), `VISION_SPEED_ESTIMATE` (103), `ODOMETRY` (331): поза/скорость от VIO или motion capture → EKF ArduPilot как ExternalNav (`EK3_SRC1_POSXY = 6`), PX4 — как vision (`EKF2_EV_CTRL`). Здесь важно время (`usec` метки, TIMESYNC) и системы координат (FRD/NED против FLU/ENU — модуль math-linalg-rot).

### Отладочные сообщения
Чтобы вывести своё значение в GCS и в лог без своего диалекта: `NAMED_VALUE_FLOAT` (251) — имя до 10 символов и float; `NAMED_VALUE_INT` (252); `DEBUG_VECT` (250) — имя и три float. Mission Planner показывает их в Quick tab/графиках, ArduPilot пишет полученные `NAMED_VALUE_FLOAT` в лог (`NVF`), PX4 — в ulog топиками debug. Для постоянной интеграции — свой диалект (модуль mav-protocol) или `TUNNEL` (385).

### Реализация на Python
`examples/mavlink/virtual_rangefinder.py` — компонент целиком: свой compid (`MAV_COMP_ID_PERIPHERAL`), heartbeat, чтение `GLOBAL_POSITION_INT` для имитации измерения, публикация `DISTANCE_SENSOR` на заданной частоте, ограничение диапазона. Структура (опрос, отправка с фиксированной частотой, heartbeat отдельно) одинакова для любого датчика: замените `measurement_cm()` на чтение реального лидара по UART/I2C — и это рабочий драйвер.

### Реализация на ESP32 (C)
На микроконтроллере используют сгенерированную C-библиотеку (header-only `c_library_v2` или свою из mavgen):

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

Приём — побайтно через `mavlink_parse_char(chan, byte, &msg, &status)` в задаче, читающей UART. Отдельная задача FreeRTOS шлёт heartbeat раз в секунду; отправка из нескольких задач — под мьютексом, иначе кадры перемешаются в UART. Подробности по ESP-IDF и UART — модуль comp-esp32.

### Тестирование компонента
Компонент тестируется на трёх уровнях: (1) юнит — функция измерения/упаковки (`test_component.py`, ограничение диапазона); (2) интеграция с фейковым аппаратом — сообщение дошло с правильными compid и ориентацией; (3) SITL — автопилот действительно использует данные (`RFND.Dist` в логе совпадает с тем, что слали, `RNGFND1` в статусе healthy). Только третий уровень доказывает, что параметры автопилота и сообщение согласованы.

{{diagram:mav-component-seq|Минимум «правильного» компонента: HEARTBEAT со своим compid, данные датчика, параметры по запросу и ответ на каждую команду.}}

## practice
### Шаг 1. Тесты компонента
```bash
cd examples/mavlink
python -m pytest -q tests/test_component.py
```
Прочитайте, что проверяют тесты: compid отправителя, ориентация, диапазон значений.

### Шаг 2. ArduPilot SITL принимает дальномер
Запустите SITL (модуль ap-sitl), задайте `RNGFND1_TYPE = 10`, `RNGFND1_ORIENT = 25`, `RNGFND1_MAX` = 40 м (или `RNGFND1_MAX_CM = 4000` на старых версиях), перезагрузите. Запустите `virtual_rangefinder.py --master udpout:127.0.0.1:14551` (отдельный выход SITL/роутера). Взлетите на 10 м: в Mission Planner `rangefinder1` показывает ~10 м минус «рельеф», в логе — `RFND`. Остановите скрипт — через несколько сотен миллисекунд автопилот должен перестать считать дальномер здоровым.

### Шаг 3. Параметр компонента
Добавьте компоненту параметр `RF_OFFSET_CM` (смещение установки): ответы на `PARAM_REQUEST_LIST`/`READ`/`SET` для своего compid, хранение в JSON-файле. Проверьте, что QGC видит его в группе компонента и что изменение из QGC сразу меняет `DISTANCE_SENSOR`.

### Шаг 4. ESP32
Перенесите компонент на ESP32: UART к TELEM-порту SITL через USB-UART адаптер (или к реальному FC), heartbeat + `DISTANCE_SENSOR` с синусом вместо датчика; затем подключите реальный дальномер (VL53L1X по I2C или TFmini по UART). Сверьте `RFND` в логе с показаниями.

Лабораторная засчитывается, когда проходят тесты, SITL использует виртуальный дальномер (лог), параметр компонента меняется из GCS и есть ESP32-версия хотя бы с синтетическими данными.

## diagnostics
- **Симптом:** SITL не видит дальномер, хотя пакеты идут
  - Возможная причина: не перезагружен после `RNGFND1_TYPE`; ориентация не совпадает с `RNGFND1_ORIENT`; значения вне min/max.
  - Что сделать: перезагрузка; ORIENT 25 ↔ PITCH_270; проверить единицы (см против м).
- **Симптом:** дальномер «мигает» healthy/unhealthy
  - Возможная причина: частота отправки низкая или нестабильная (сон в цикле приёма).
  - Что сделать: отправка по таймеру ≥ 10 Гц, приём неблокирующий.
- **Симптом:** QGC не показывает параметры компонента
  - Возможная причина: нет heartbeat от компонента или ответы идут с compid автопилота.
  - Что сделать: heartbeat; отвечать со своим compid и учитывать target_component в запросе.
- **Симптом:** на ESP32 периодически приходят «битые» кадры
  - Возможная причина: две задачи пишут в UART одновременно.
  - Что сделать: одна задача-отправитель с очередью или мьютекс на UART.

## references
- MAVLink — DISTANCE_SENSOR, OBSTACLE_DISTANCE, ODOMETRY (common.xml) | https://mavlink.io/en/messages/common.html | primary | A
- ArduPilot — Rangefinder parameters (RNGFND1_TYPE 10: MAVLink) | https://ardupilot.org/copter/docs/common-rangefinder-landingpage.html | primary | A
- ArduPilot — AP_RangeFinder (source) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/AP_RangeFinder | primary | A
- MAVLink — c_library_v2 (generated C headers) | https://github.com/mavlink/c_library_v2 | primary | A
- PX4 — Distance sensors and MAVLink | https://docs.px4.io/main/en/sensor/rangefinders.html | primary | A

## checklist
- Знаю обязанности компонента: heartbeat, ответы, свои параметры, честная деградация
- Заполняю DISTANCE_SENSOR правильно (единицы, ориентация, диапазон)
- Настраиваю ArduPilot на MAVLink-дальномер и проверяю по логу
- Использую NAMED_VALUE_* для быстрой отладки
- Реализую компонент на Python и на ESP32 (mavlink_parse_char, мьютекс)
- Тестирую на трёх уровнях: юнит, фейковый аппарат, SITL
