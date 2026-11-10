---
id: bf-cli
title: "CLI і ремапінг ресурсів у Betaflight"
level: L3
readingTime: 45 хв
firmware: Betaflight 4.5+
status: published
tags:
  - CLI
  - resource
  - remapping
  - backup
  - Betaflight
references:
  - title: "Betaflight CLI Documentation"
    url: "https://betaflight.com/docs/wiki/guides/current/Cli"
    tier: primary
    stack: betaflight
  - title: "Betaflight Resource Remapping Guide"
    url: "https://www.betaflight.com/docs/wiki/guides/current/Resource-remapping"
    tier: primary
    stack: betaflight
  - title: "Betaflight 4.5 CLI Command Reference"
    url: "https://betaflight.com/docs/wiki/guides/archive/Betaflight-4.5-CLI-commands"
    tier: primary
    stack: betaflight
  - title: "How to Check Betaflight Build Options"
    url: "https://oscarliang.com/check-betaflight-build-options/"
    tier: secondary
    stack: betaflight
related:
  - bf-custom
  - bf-ports
next:
  - bf-custom
source: content/betaflight/bf-cli.md
source_hash: 9af6f291e217
---

## summary

Командний рядок (CLI) Betaflight — це текстовий інтерфейс, що відкриває доступ до конфігурації польотного контролера на рівні, недоступному в графічному інтерфейсі. Із CLI можна змінювати будь-які параметри, зокрема не винесені у вкладки конфігуратора, перевіряти апаратний стан, керувати ресурсами (виводами мікроконтролера) і створювати резервні копії.

Ключове практичне завдання статті — дати навичку впевненої роботи з `resource` і ремапінгом виводів без перепрошивки, а також навчити діагностувати склад прошивки та відновлювати конфігурацію після збоїв.

## theory

### Архітектура CLI

CLI працює поверх послідовного порту (UART), використовуючи той самий канал, що й конфігуратор (`MSP`, `MultiWii Serial Protocol`). Щоб увійти в CLI через термінал (наприклад, PuTTY/screen), потрібно надіслати символ `#` — він перемикає контролер у командний режим.

### Ключові команди та їхнє призначення

- Керування сесією: `save`, `exit`, `batch start`, `batch end`
- Перегляд конфігурації: `get`, `diff`, `dump`, `status`, `version`
- Зміна параметрів: `set`, `feature`, `profile`, `rateprofile`
- Ремапінг ресурсів: `resource`, `timer`
- Діагностика та налагодження: `tasks`, `flash_info`, `dma`

### Diff vs Dump: що і коли використовувати

`diff all` виводить лише змінені параметри. Це основний формат для резервних копій і безпечного перенесення в межах однієї версії прошивки.

`dump all` виводить повний знімок конфігурації, включно зі значеннями за замовчуванням. Підходить для глибокої діагностики, але небезпечний для перенесення між різними версіями.

Рекомендується зберігати окремо:
- `diff all`
- `resource show`
- `status` (версія/збірка)

### Ремапінг ресурсів: концепція та обмеження

Команда `resource` керує прив'язкою «функція -> фізичний пін»:

```text
resource <ФУНКЦІЯ> <ІНДЕКС> <ПІН> 
resource MOTOR 1 B00 
resource MOTOR 5 NONE
```

- ADC-ресурси (`ADC_BATT`, `ADC_CURR`, `ADC_RSSI`) призначаються лише на ADC-піни.
- UART обмежений апаратними блоками контролера — не будь-який пін можна використати як серіал.
- Для DShot критичні таймери та DMA: неправильний пін/канал призводить до непрацюючих моторів.

### Специфіка Betaflight 4.5

Між версіями змінюються назви та логіка частини параметрів:

- D-term naming: у 4.5 `d_roll` — піковий D, `d_min_roll` — базовий; у 2025.12 навпаки: `d_roll` — базовий, `d_max_roll` — піковий (`d_min_*` видалено).
- GPS rescue: частину змінних перероблено.
- Failsafe landing: з'явилися відмінності в naming/поведінці.

Через це старі бекапи не можна бездумно вставляти в нову прошивку.

### Перевірка складу прошивки через BUILD KEY

У `status` у Betaflight 4.5+ відображається `BUILD KEY`. Підставивши його в URL нижче, можна отримати JSON зі списком увімкнених опцій (`Options`):

```text
https://build.betaflight.com/api/builds/<BUILD_KEY>/json
```

Це допомагає діагностувати відсутність функцій (наприклад, GPS/LED/VTX) без перепрошивки.

### Рецепти, які потрібні найчастіше (команди з `cli/cli.c`)
| Завдання | Команда |
|---|---|
| Дізнатися версію, target / BUILD KEY | `version` / `status` |
| Завантаження CPU, прапорці арму, частота гіроскопа | `status`, `tasks` |
| Перепризначити мотор на інший пад | `resource MOTOR 3 B01` → `save` (`resource show all` — зайнятість) |
| Змінити порядок моторів без перепаювання | `resource` своп пар або в Motors tab «Motor direction/remap» |
| Реверс напрямку одного мотора (DShot-команди) | `dshotprog 0 21` (21 — reversed, 20 — normal; у частини ESC 7/8 — direction 1/2), потім `dshotprog 0 12` (save settings); мотори без пропів, індекс з 0 (255 — усі мотори) |
| Перевірити DShot-телеметрію | `dshot_telemetry_info` |
| Таймери/DMA (конфлікти моторів, LED, serial) | `timer`, `dma show` |
| Скидання до замовчувань без збереження / зі збереженням | `defaults nosave`, `defaults` |
| Увійти в завантажувач DFU | `bl` (або `bl rom`) |
| Flash як USB-диск (вивантаження логів) | `msc` |
| Прошити ESC/налаштувати | `serialpassthrough`/`escprog` через конфігуратор ESC |
| Пакетне завантаження diff без проміжних перезавантажень | `batch start` … `batch end` → `save` |
| Діапазони каналів, карта стіків | `rxrange`, `map AETR1234` |
| Профілі | `profile 1`, `rateprofile 2` (команди `battery_profile` у Betaflight немає) |
| Тест пищалки/звуку, сенсори | `beeper`, `play_sound`, `gyroregisters` (знайдені датчики — у виводі `status`) |
| Підпис та ідентифікація плати | `board_name`, `manufacturer_id`, `mcu_id`, `signature` |

### Розібраний приклад: згорів пад мотора 2
Плата F405, пад M2 відпав. `resource show all` — вільні таймерні пади: `LED_STRIP 1 A08`. Перевірка `timer A08 list` — є таймер із DMA; `resource LED_STRIP 1 NONE`, `resource MOTOR 2 A08`, `timer A08 AF1` (якщо потрібно), `dma pin A08 0`, `save`; Motors tab — мотор 2 крутиться на правильній позиції без пропів; `diff all` у репозиторій із коментарем. Якщо таймер пада конфліктує з DShot інших моторів (одна DMA-група) — `dma show` це покаже, а bitbang DShot (`dshot_bitbang = ON`) обходить частину конфліктів.

{{diagram:bf-resource-remap|Перенесення мотора на інший пад: перевірити таймер і DMA, звільнити старий ресурс, призначити новий, зберегти й перевірити на вкладці Motors.}}

## practice

### Доступ до CLI

1. Підключи польотний контролер по USB і відкрий Betaflight Configurator.
2. Перейди на вкладку CLI.
3. Натисни `Connect`, якщо з'єднання не піднялося автоматично.

Альтернатива через термінал:
- підключися до порту (`/dev/ttyACM0` у Linux або `COMx` у Windows);
- встанови швидкість `115200`;
- надішли символ `#`.

### Створення повної резервної копії

Перед будь-якими змінами збережи стан:

```text
status
version
diff all
resource show
timer show
```

Збережи вивід у файл — це дасть:
- версію та збірку;
- список змінених параметрів;
- призначення ресурсів;
- конфігурацію таймерів.

### Перегляд і зміна параметрів

Перегляд:

```text
get gyro_
get acc
set dyn_notch_min_hz = 150
```

Зміна:

```text
set dyn_notch_min_hz = 150
set dyn_notch_q = 250
save
```

Для пакетного редагування (менше перезавантажень):

```text
batch start
set gyro_lpf1_static_hz = 0
set gyro_lpf2_static_hz = 300
set dterm_lpf2_static_hz = 150
batch end
save
```

### Ремапінг моторів: повний приклад

Сценарій: поворот FC на 90° за годинниковою стрілкою без зміни орієнтації в прошивці.

Крок 1. Перевірити поточні призначення:

```text
resource show
```

Приклад виводу:

```text
A06: MOTOR 1
A07: MOTOR 2
A11: MOTOR 3
A12: MOTOR 4
```

Крок 2. Поточна схема:

```text
         FRONT
4 (A12)        2 (A07)

3 (A11)        1 (A06)
         BACK
```

Крок 3. Цільова схема після повороту FC:

```text
         FRONT
3 (A11)        4 (A12)

1 (A06)        2 (A07)
         BACK
```

Крок 4. Призначити нові відповідності:

```text
resource MOTOR 1 none
resource MOTOR 2 none
resource MOTOR 3 none
resource MOTOR 4 none
resource MOTOR 1 A07
resource MOTOR 2 A12
resource MOTOR 3 A06
resource MOTOR 4 A11
save
```

Після `save` контролер перезавантажиться з новою схемою.

### Перевірка build-опцій через BUILD KEY

```text
status
```

Далі відкрий:

```text
https://build.betaflight.com/api/builds/<BUILD_KEY>/json
```

Приклад секції опцій:

```json
"Options": [
  "CLOUD_BUILD",
  "USE_DSHOT",
  "USE_GPS",
  "USE_OSD",
  "USE_SERIALRX",
  "USE_SERIALRX_CRSF",
  "USE_TELEMETRY",
  "USE_VTX"
]
```

### Відновлення конфігурації з бекапу

1. Виконай скидання:

```text
defaults
```

2. Після перезавантаження знову увійди в CLI.
3. Встав команди з бекапу частинами (не одним величезним блоком).
4. Перевір критичні параметри для твоєї версії прошивки.
5. Виконай `save`.

## diagnostics

- Симптом: CLI не відповідає, команди не виконуються.
  - Можлива причина: неправильний вхід у CLI (не надіслано `#`), конфлікт порту, некоректна швидкість.
  - Що зробити: переконатися, що активна вкладка CLI, закрити інші застосунки з доступом до COM-порту, звірити швидкість MSP на порту (`serial`/вкладка Ports) і швидкість термінала (для USB VCP вона не важлива).

- Симптом: після вставлення бекапу дрон працює некоректно.
  - Можлива причина: невідповідність версій прошивки.
  - Що зробити: звірити `version` із бекапу та поточну версію, відновлювати через `diff all`, а не через `dump all`, вручну перевірити критичні параметри.

- Симптом: під час ремапінгу з'являються помилки `also used by MOTOR`.
  - Можлива причина: тимчасове перекриття ресурсів під час послідовного призначення.
  - Що зробити: спочатку очистити призначення (`resource MOTOR N none`), потім призначити нові, зберегти через `save`.

- Симптом: після ремапінгу мотори не працюють або працюють неправильно.
  - Можлива причина: неправильний пін, конфлікт таймера/DMA, відсутня підтримка DShot на вибраному піні.
  - Що зробити: виконати `resource show` і `timer show`, звірити розпіновку плати та підтримувані функції пінів.

- Симптом: команда `save` зависає або контролер не перезавантажується.
  - Можлива причина: нестабільне USB-підключення, живлення, пошкоджена конфігурація.
  - Що зробити: перепідключити живлення та USB, перевірити кабель, у разі повторення виконати `defaults` і відновлення покроково.

- Симптом: не вдається отримати BUILD KEY або URL повертає помилку.
  - Можлива причина: стара версія Betaflight (< 4.4, до Cloud Build), ключ скопійовано не повністю, неправильний URL.
  - Що зробити: переконатися, що версія 4.5+, повторно скопіювати ключ, за потреби перевірити альтернативний endpoint `.../<BUILD_KEY>/log`.

## references

- Betaflight CLI Documentation | https://betaflight.com/docs/wiki/guides/current/Cli | primary | A
- Betaflight Resource Remapping Guide | https://www.betaflight.com/docs/wiki/guides/current/Resource-remapping | primary | A
- Betaflight 4.5 CLI Command Reference | https://betaflight.com/docs/wiki/guides/archive/Betaflight-4.5-CLI-commands | primary | A
- How to Check Betaflight Build Options | https://oscarliang.com/check-betaflight-build-options/ | secondary | B
