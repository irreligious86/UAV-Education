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

Командний рядок (CLI) Betaflight — то є текстовий інтерфейс, котрий пускає тебе до конфігурації польотного контролера на такому рівні, куди графічний інтерфейс ніц не дістає. Із CLI можна міняти будь-які параметри, навіть ті, що не винесені у вкладки конфігуратора, перевіряти апаратний стан, ґаздувати ресурсами (виводами мікроконтролера) і робити резервні копії.

Головне практичне завдання статті — щоб ти навчив-ся впевнено працювати з `resource` і ремапінгом виводів без перепрошивки, а також умів розпізнати, що є в прошивці, і відновити конфігурацію, коли щось ся зіпсує.

## theory

### Архітектура CLI

CLI працює поверх послідовного порту (UART), через той самий канал, що й конфігуратор (`MSP`, `MultiWii Serial Protocol`). Аби зайти в CLI через термінал (наприклад, PuTTY/screen), треба надіслати символ `#` — він перемикає контролер у командний режим.

### Ключові команди та їхнє призначення

- Керування сесією: `save`, `exit`, `batch start`, `batch end`
- Перегляд конфігурації: `get`, `diff`, `dump`, `status`, `version`
- Зміна параметрів: `set`, `feature`, `profile`, `rateprofile`
- Ремапінг ресурсів: `resource`, `timer`
- Діагностика та налагодження: `tasks`, `flash_info`, `dma`

### Diff vs Dump: що і коли брати

`diff all` виводить лиш змінені параметри. То є основний формат для резервних копій і безпечного перенесення в межах однієї версії прошивки.

`dump all` виводить повний знімок конфігурації, разом зі значеннями за замовчуванням. Файно надається для глибокої діагностики, але небезпечний для перенесення між різними версіями.

Ліпше тримати окремо:
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

- ADC-ресурси (`ADC_BATT`, `ADC_CURR`, `ADC_RSSI`) ся призначають лиш на ADC-піни.
- UART обмежений апаратними блоками контролера — не кожен пін ся надасть на серіал.
- Для DShot критичні таймери та DMA: трафиш не той пін/канал — і мотори не крутять.

### Специфіка Betaflight 4.5

Між версіями міняються назви та логіка частини параметрів:

- D-term naming: у 4.5 `d_roll` — піковий D, `d_min_roll` — базовий; у 2025.12 навпаки: `d_roll` — базовий, `d_max_roll` — піковий (`d_min_*` видалено).
- GPS rescue: частину змінних перероблено.
- Failsafe landing: з'явили-ся відмінності в naming/поведінці.

Тому старі бекапи не можна бездумно пхати в нову прошивку.

### Перевірка складу прошивки через BUILD KEY

У `status` у Betaflight 4.5+ показується `BUILD KEY`. Підстав його в URL нижче — і дістанеш JSON зі списком увімкнених опцій (`Options`):

```text
https://build.betaflight.com/api/builds/<BUILD_KEY>/json
```

То помагає з'ясувати, чому нема якоїсь функції (наприклад, GPS/LED/VTX), без перепрошивки.

### Рецепти, котрі треба найчастіше (команди з `cli/cli.c`)
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
| Зайти в завантажувач DFU | `bl` (або `bl rom`) |
| Flash як USB-диск (вивантаження логів) | `msc` |
| Прошити ESC/налаштувати | `serialpassthrough`/`escprog` через конфігуратор ESC |
| Пакетне завантаження diff без проміжних перезавантажень | `batch start` … `batch end` → `save` |
| Діапазони каналів, карта стіків | `rxrange`, `map AETR1234` |
| Профілі | `profile 1`, `rateprofile 2` (команд `battery_profile` у Betaflight нема) |
| Тест пищалки/звуку, сенсори | `beeper`, `play_sound`, `gyroregisters` (знайдені датчики — у виводі `status`) |
| Підпис та ідентифікація плати | `board_name`, `manufacturer_id`, `mcu_id`, `signature` |

### Розібраний приклад: згорів пад мотора 2
Плата F405, пад M2 відпав. `resource show all` — вільні таймерні пади: `LED_STRIP 1 A08`. Перевірка `timer A08 list` — є таймер із DMA; `resource LED_STRIP 1 NONE`, `resource MOTOR 2 A08`, `timer A08 AF1` (як треба), `dma pin A08 0`, `save`; Motors tab — мотор 2 крутить-ся на правильній позиції без пропів; `diff all` у репозиторій із коментарем. Як таймер пада конфліктує з DShot інших моторів (одна DMA-група) — `dma show` то покаже, а bitbang DShot (`dshot_bitbang = ON`) обходить частину конфліктів.

{{diagram:bf-resource-remap|Перенесення мотора на інший пад: перевірити таймер і DMA, звільнити старий ресурс, призначити новий, зберегти й перевірити на вкладці Motors.}}

## practice

### Доступ до CLI

1. Підключи польотний контролер по USB і відкрий Betaflight Configurator.
2. Перейди на вкладку CLI.
3. Натисни `Connect`, як з'єднання само ся не підняло.

Інший варіант — через термінал:
- підключи-ся до порту (`/dev/ttyACM0` у Linux або `COMx` у Windows);
- постав швидкість `115200`;
- надішли символ `#`.

### Повна резервна копія

Заки щось міняти, збережи стан:

```text
status
version
diff all
resource show
timer show
```

Збережи вивід у файл — то дасть тобі:
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

Сценарій: FC повернули на 90° за годинниковою стрілкою, а орієнтацію в прошивці не міняли.

Крок 1. Перевірити теперішні призначення:

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

Крок 2. Теперішня схема:

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

По `save` контролер ся перезавантажить уже з новою схемою.

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

1. Зроби скидання:

```text
defaults
```

2. Після перезавантаження знов зайди в CLI.
3. Встав команди з бекапу частинами (не одним величезним кавалком).
4. Перевір критичні параметри для твоєї версії прошивки.
5. Зроби `save`.

## diagnostics

- Симптом: CLI не відповідає, команди не виконуються.
  - Можлива причина: неправильно зайшли в CLI (не надіслано `#`), конфлікт порту, некоректна швидкість.
  - Що зробити: пересвідчитися, що активна вкладка CLI, позакривати інші програми, котрі тримають COM-порт, звірити швидкість MSP на порту (`serial`/вкладка Ports) і швидкість термінала (для USB VCP вона ніц не важить).

- Симптом: після вставлення бекапу дрон працює некоректно.
  - Можлива причина: не співпадають версії прошивки.
  - Що зробити: звірити `version` із бекапу та теперішню версію, відновлювати через `diff all`, а не через `dump all`, вручну перевірити критичні параметри.

- Симптом: під час ремапінгу вискакують помилки `also used by MOTOR`.
  - Можлива причина: ресурси тимчасово ся перекривають, коли призначаєш їх по черзі.
  - Що зробити: спершу очистити призначення (`resource MOTOR N none`), потім призначити нові, зберегти через `save`.

- Симптом: після ремапінгу мотори не працюють або працюють неправильно.
  - Можлива причина: не той пін, конфлікт таймера/DMA, на вибраному піні нема підтримки DShot.
  - Що зробити: виконати `resource show` і `timer show`, звірити розпіновку плати та підтримувані функції пінів.

- Симптом: команда `save` зависає або контролер не перезавантажується.
  - Можлива причина: хитке USB-підключення, живлення, пошкоджена конфігурація.
  - Що зробити: перепідключити живлення та USB, перевірити кабель, як ся повторює — виконати `defaults` і відновлювати покроково.

- Симптом: не вдається дістати BUILD KEY або URL вертає помилку.
  - Можлива причина: стара версія Betaflight (< 4.4, до Cloud Build), ключ скопійовано не цілий, неправильний URL.
  - Що зробити: пересвідчитися, що версія 4.5+, ще раз скопіювати ключ, як треба — перевірити альтернативний endpoint `.../<BUILD_KEY>/log`.

## references

- Betaflight CLI Documentation | https://betaflight.com/docs/wiki/guides/current/Cli | primary | A
- Betaflight Resource Remapping Guide | https://www.betaflight.com/docs/wiki/guides/current/Resource-remapping | primary | A
- Betaflight 4.5 CLI Command Reference | https://betaflight.com/docs/wiki/guides/archive/Betaflight-4.5-CLI-commands | primary | A
- How to Check Betaflight Build Options | https://oscarliang.com/check-betaflight-build-options/ | secondary | B
