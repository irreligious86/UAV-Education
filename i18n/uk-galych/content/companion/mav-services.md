---
id: mav-services
title: "Мікросервіси MAVLink: команди, параметри, місії, потоки"
level: L3
readingTime: 50 хв
firmware: ArduPilot · PX4
status: published
added: 2026-11-08
tags:
  - MAVLink
  - місії
  - параметри
  - COMMAND_ACK
  - MAVFTP
related:
  - mav-protocol
  - ap-missions
  - comp-mavlink
next:
  - mav-routing
source: content/companion/mav-services.md
source_hash: d570897fba1a
---

## summary
MAVLink — то не набір повідомлень, а набір **діалогів** (мікросервісів): хто починає, хто відповідає, шо робити при втраті. Майже всі помилки інтеграції companion — то порушення одного з тих діалогів: команда без очікування ACK, параметр, «записаний» без еха, місія, завантажена наполовину. Модуль іде головними мікросервісами: heartbeat і стан, команди (`COMMAND_LONG`/`COMMAND_INT`, ACK, IN_PROGRESS, лічильник confirmation), параметри (читання списку, запис із підтвердженням, пакування типів), місії (завантаження, вивантаження, часткове оновлення, геозони й точки збору як окремі типи місій), керування потоками телеметрії, MAVFTP, камера/гімбал і Remote ID — на рівні «котрий діалог і де він ся ламає». Лабораторна: клієнт місій із повторами, котрий проходить тести за 25 % втрат пакетів.

## theory
### Heartbeat і стан
`HEARTBEAT` (0) раз на секунду від кожного компонента: тип (`MAV_TYPE`), автопілот, `base_mode` (прапорець арму — `MAV_MODE_FLAG_SAFETY_ARMED`), `custom_mode` (номер режиму, свій у кожної прошивки), `system_status`. Heartbeat — то і виявлення учасників, і джерело адреси для маршрутизації, і основа failsafe: автопілот, котрий перестав чути heartbeat GCS, запускає GCS failsafe (як він ввімкнений); companion, котрий перестав чути автопілот, мусить перестати видавати уставки. Правило: жодних адресних команд, доки не прийшов перший heartbeat від адресата.

### Команди: COMMAND_LONG, COMMAND_INT і ACK
`COMMAND_LONG` (76): `target_system`, `target_component`, `command` (MAV_CMD), `confirmation`, сім float-параметрів. `COMMAND_INT` (75): та сама адресація й param1–4, але без поля `confirmation` (замість нього `current`/`autocontinue`, не використовуються); параметри 5–6 — цілі `x`, `y` (широта/довгота × 10⁷ без втрати точності float) і є поле `frame`; для команд із координатами ліпше брати саме його. Відповідь — `COMMAND_ACK` (77) з `result`:

| result | Значення | Що робити клієнту |
|---|---|---|
| ACCEPTED (0) | виконано/прийнято | готово |
| TEMPORARILY_REJECTED (1) | зараз не можна | повторити пізніше |
| DENIED (2) | заборонено в цьому стані | читати STATUSTEXT, не повторювати |
| UNSUPPORTED (3) | команда не підтримується | не повторювати |
| FAILED (4) | спроба була й не вдалася | розбирати причину |
| IN_PROGRESS (5) | довга команда, `progress` 0–100 | чекати фінальний ACK |

Протокол каже: як ACK не прийшов за таймаут, повтори команду, **збільшивши `confirmation`**. Отримувач за ним може відрізнити повтор від нової команди. Без очікування ACK команда — то лиш надія; без ліміту повторів — зависання.

{{diagram:mavlink-command-seq|Команда з підтвердженням: повтор при втраті ACK, проміжний IN_PROGRESS, фінальний результат.}}

### Параметри
- Список: `PARAM_REQUEST_LIST` (21) → потік `PARAM_VALUE` (22) з `param_count` і `param_index`. Пропуски дозапитують за індексом через `PARAM_REQUEST_READ` (20) з `param_index`.
- Читання одного: `PARAM_REQUEST_READ` за іменем (16 символів, без завершального нуля при довжині 16!) або індексом.
- Запис: `PARAM_SET` (23). **Окремого ACK нема** — підтвердження то `PARAM_VALUE` з тим самим іменем і новим значенням. Як ехо прийшло зі старим значенням — запис відхилено (поза діапазоном, лише для читання).
- Всі значення передаються в полі `float param_value`. Цілі типи ArduPilot передає як число, зведене до float (C-cast), PX4 — побайтово (біти цілого в бітах float). Котру схему вживає автопілот, каже прапорець у `AUTOPILOT_VERSION.capabilities` (`MAV_PROTOCOL_CAPABILITY_PARAM_ENCODE_C_CAST` або `..._BYTEWISE`). Помилка в схемі перетворює `SYSID_THISMAV = 1` на 1.4e-45 — йой.

Для масового завантаження параметрів, аби не робити 1000 діалогів по радіо, є MAVFTP: ArduPilot віддає файл `@PARAM/param.pck` цілим.

### Місії: діалог, котрий веде отримувач
Завантаження (клієнт → апарат):
1. Клієнт: `MISSION_COUNT` (44) з кількістю пунктів і `mission_type`.
2. Апарат запитує по одному: `MISSION_REQUEST_INT` (51) з `seq`.
3. Клієнт відповідає `MISSION_ITEM_INT` (73) з тим `seq`.
4. Після останнього пункту апарат шле `MISSION_ACK` (47) з результатом.

Ключова думка: **ініціативу тримає сторона, шо приймає**. Вона запитує пункти, вона ж повторює запит за таймаутом. Відправник відповідає на кожен запит, включно з повторними, і не шле пунктів «наперед». Вивантаження (апарат → клієнт) симетричне: `MISSION_REQUEST_LIST` → `MISSION_COUNT` → клієнт запитує `MISSION_REQUEST_INT` → `MISSION_ITEM_INT` → клієнт завершує `MISSION_ACK`.

`mission_type`: 0 — маршрут, 1 — геозона (fence), 2 — точки збору (rally), 255 — всі (для очищення `MISSION_CLEAR_ALL`). Пункт 0 в ArduPilot — домашня точка; завантаження з пункту 1 у Mission Planner — то інтерфейс, а на проводі home однаково seq 0. Застарілих `MISSION_ITEM` (39) і `MISSION_REQUEST` (40) з float-координатами стережися: точність float на широті ~ метр.

Під час польоту: `MISSION_CURRENT` (42) — поточний пункт, `MISSION_ITEM_REACHED` (46) — досягнуто, `MAV_CMD_DO_SET_MISSION_CURRENT` (224) — перейти (повідомлення `MISSION_SET_CURRENT` (41) застаріло з 2022 р. і замінене тою командою). Часткове оновлення: `MISSION_WRITE_PARTIAL_LIST` (38) з діапазоном індексів — підтримується не всюди, певніше перезалити цілу місію й перевірити вивантаженням.

{{diagram:mavlink-mission-seq|Завантаження місії: апарат запитує пункти по одному й сам повторює запит при втраті; завершує MISSION_ACK.}}

### Потоки телеметрії
Апарат шле телеметрію або за своїми налаштуваннями (ArduPilot — групи потоків на порт, параметри `SRn_*` у 4.6 і `MAVn_*` у 4.7+; PX4 — профілі `MAV_n_MODE`), або на запит клієнта:
- `MAV_CMD_SET_MESSAGE_INTERVAL` (511): param1 — msgid, param2 — інтервал у мкс (−1 — вимкнути, 0 — за замовчуванням).
- `MAV_CMD_REQUEST_MESSAGE` (512): одне повідомлення зара (наприклад, `AUTOPILOT_VERSION`, `HOME_POSITION`).

Бюджет каналу: SiK на 57600 дає ~5 КБ/с корисних; ATTITUDE (28 байт payload + 12 службових) на 10 Гц — 0.4 КБ/с. Companion через UART 921600 — ~90 КБ/с, і там можна просити IMU на 100 Гц, а по радіо — та де. Запитуй рівно те, шо вживаєш, і на тому каналі, де вживаєш.

### Час
`SYSTEM_TIME` (2) — час від завантаження й UTC; `TIMESYNC` (111) — оцінка зміщення годинників companion і автопілота (обмін tc1/ts1, як NTP). Без синхронізації часу злиття кадрів камери з телеметрією точним не буде: затримка USB/UART і буферів легко 10–50 мс.

### MAVFTP, камера, гімбал, Remote ID
- **MAVFTP** — `FILE_TRANSFER_PROTOCOL` (110): файлова система поверх MAVLink (читання/запис/лістинг, повтор за послідовністю сесії). ArduPilot: логи, скрипти Lua, `@PARAM/param.pck`, `@SYS/` з діагностикою.
- **Камера** (Camera Protocol v2): `MAV_CMD_IMAGE_START_CAPTURE` (2000), `CAMERA_INFORMATION`, `CAMERA_IMAGE_CAPTURED` з координатами й часом кадру. Камера — окремий компонент (compid 100–105).
- **Гімбал** (Gimbal Protocol v2): менеджер гімбала на автопілоті й пристрій; `MAV_CMD_DO_GIMBAL_MANAGER_PITCHYAW` (1000), `GIMBAL_MANAGER_SET_ATTITUDE` (282), статус `GIMBAL_DEVICE_ATTITUDE_STATUS`.
- **Remote ID**: група `OPEN_DRONE_ID_*` (12900+) — автопілот або модуль транслює ідентифікатор, місцеположення й дані оператора; вимоги до їх передавання — питання регуляторики (див. f-regulations).

## practice
### Крок 1. Тести без SITL
`examples/mavlink/mav_client.py` — довідкова реалізація, `fake_vehicle.py` — апарат, котрий уміє губити пакети.

```bash
cd examples/mavlink
python -m pytest -q tests/test_services.py
```

Прочитай `mission_upload`: клієнт відповідає на будь-який `MISSION_REQUEST_INT`, включно з повторами, і перезапускає транзакцію `MISSION_COUNT`, як апарат замовк.

### Крок 2. Власний клієнт місій
Напиши **власну** реалізацію `mission_upload/mission_download` (не копіюючи), підстав її в тест замість `mav_client` і доможися проходження при `loss=0.25`. Потім додай тест: апарат відповідає `MISSION_ACK` з помилкою — клієнт мусить підняти виняток, а не «мовчки успіх».

### Крок 3. У SITL
Тим самим клієнтом завантаж місію з 10 точок в ArduPilot SITL, вивантаж і порівняй поелементно; потім зроби те саме для геозони (`mission_type = 1`, команди `MAV_CMD_NAV_FENCE_POLYGON_VERTEX_INCLUSION`). Переконайся, шо Mission Planner бачить обидві.

### Крок 4. Параметри з пакуванням
Прочитай `SYSID_THISMAV` (або `MAV_SYSID` на 4.7+) в ArduPilot SITL і `MAV_SYS_ID` у PX4 SITL через `PARAM_REQUEST_READ`; глянь на сире `param_value` і `param_type`. Поясни різницю схем C-cast і bytewise на тих двох значеннях.

Лабораторна зараховується, коли власний клієнт місій проходить тести за втрат, місія й геозона збігаються після вивантаження в SITL і пояснено пакування параметрів.

## diagnostics
- **Симптом:** місію «завантажено», але в апараті на один-два пункти менше
  - Можлива причина: клієнт слав пункти підряд, не чекаючи запитів; частина ся загубила, ACK не перевірено.
  - Що зробити: відповідай лиш на MISSION_REQUEST_INT; вимагай MISSION_ACK ACCEPTED; вивантажуй і порівнюй.
- **Симптом:** PARAM_SET «пройшов», а значення ся не змінило
  - Можлива причина: ехо PARAM_VALUE не перевіряли; значення поза діапазоном або неправильне пакування типу.
  - Що зробити: порівнюй ехо зі значенням; зважай на C-cast проти bytewise.
- **Симптом:** команда деколи виконується двічі
  - Можлива причина: повтор без збільшення confirmation на неідемпотентній команді.
  - Що зробити: confirmation++ при повторі; перевіряй стан перед повтором.
- **Симптом:** телеметрія по радіо «заїкається» після підключення скрипта
  - Можлива причина: скрипт запросив високі частоти через SET_MESSAGE_INTERVAL на каналі радіо.
  - Що зробити: запитуй потоки лиш на своєму каналі; рахуй бюджет.

## references
- MAVLink — Mission protocol | https://mavlink.io/en/services/mission.html | primary | A
- MAVLink — Command protocol | https://mavlink.io/en/services/command.html | primary | A
- MAVLink — Parameter protocol (encoding) | https://mavlink.io/en/services/parameter.html | primary | A
- MAVLink — FTP protocol | https://mavlink.io/en/services/ftp.html | primary | A
- MAVLink — Camera and Gimbal protocols v2 | https://mavlink.io/en/services/camera.html | primary | A
- ArduPilot — MissionItemProtocol (source) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/GCS_MAVLink | primary | A

## checklist
- Знаю коди COMMAND_ACK і шо робити на кожен
- Повторюю команди з confirmation++ і лімітом
- Підтверджую PARAM_SET ехом PARAM_VALUE і розумію пакування типів
- Описую діалог завантаження/вивантаження місії і хто в ньому повторює запити
- Розрізняю типи місій (маршрут, геозона, rally)
- Керую частотою потоків і рахую бюджет каналу
