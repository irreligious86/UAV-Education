---
id: bf-intro
title: "Вступ до Betaflight"
level: L1
readingTime: 25 хв
firmware: Betaflight 4.5+
status: published
tags:
  - Betaflight
  - початок роботи
  - конфігуратор
  - налаштування
references:
  - title: "Getting Started — Betaflight Documentation"
    url: "https://betaflight.com/docs/wiki/getting-started"
    tier: primary
    stack: betaflight
  - title: "Betaflight 4.5 Release Notes"
    url: "https://www.betaflight.com/docs/wiki/release/Betaflight-4-5-Release-Notes"
    tier: primary
    stack: betaflight
  - title: "Betaflight Configurator — Official Web App"
    url: "https://app.betaflight.com"
    tier: primary
    stack: betaflight
  - title: "Betaflight Advanced Guide — iFlight"
    url: "https://help.iflight-rc.eu/en-US/betaflight-advanced-guide-951396"
    tier: secondary
    stack: betaflight
  - title: "Betaflight FAQ — How to Start"
    url: "https://www.betaflight.com/docs/wiki/guides/current/FAQ"
    tier: primary
    stack: betaflight
  - title: "Betaflight Configurator — Releases"
    url: "https://github.com/betaflight/betaflight-configurator/releases"
    tier: primary
    stack: betaflight
related:
  - bf-ports
  - bf-modes-osd
  - bf-cli
next:
  - bf-ports
source: content/betaflight/bf-intro.md
source_hash: 18aabbcd6bb5
---

## summary

Betaflight — відкрита прошивка для польотних контролерів мультикоптерів, котра ставить на перше місце **низьку затримку** керування й гнучке налаштування. У статті — цілий шлях від встановлення конфігуратора до першого безпечного вильоту.

**Як дочитаєш, будеш уміти:**

- прошити FC і зробити **бекап** конфігурації (`diff all`);
- налаштувати **порти, приймач, режими** й калібрування датчиків;
- перевірити **мотори та failsafe** перед польотом.

## theory

### Що то є Betaflight

Betaflight — форк **Cleanflight** (спадкоємця Baseflight / STM32-порту MultiWii). Головне для цього стека — **продуктивність**: мінімальна **latency** і висока частота контуру гіроскопа (до **8 кГц**).

**Підтримка:** польотні контролери на **STM32** (F4, F7, H7). **Що вміє прошивка:**

- багатопрофільні **PID**;
- фільтрація гіроскопа й **D-term**;
- цифрові протоколи до ESC (**DShot**, ProShot);
- **Blackbox** для логів;
- **CLI** для точного налаштування.

### Архітектура прошивки

Прошивка модульна, задачі виконуються в реальному часі. **Основні задачі (tasks):**

- **Gyro task** — читання гіроскопа (до 8 кГц), фільтри.
- **PID task** — вихід на мотори за помилкою **setpoint** vs **gyro**.
- **RX task** — приймач (CRSF, SBUS, ELRS і т. д.).
- **Scheduler** — ділить час між задачами.

**PID-цикл:** параметр `pid_process_denom` задає частоту контуру PID. Приклад: gyro **8 кГц**, `pid_process_denom = 2` → PID **4 кГц** (звична відправна точка для більшості збірок).

### Версії прошивки та сумісність

**Betaflight 4.5** — попередня стабільна гілка (останній випуск 4.5.5); актуальні — 2025.12.x і 2026.6.x. Ключові зміни:

- GPS (зокрема модулі **M10**) і **GPS Rescue**;
- магнітометри;
- **Angle / Horizon** з опцією *Earth referencing*;
- шрифти для HD VTX (Walksnail);
- фільтрація з урахуванням гармонік **RPM**.

**Важливо:** під час переходу **4.4 → 4.5** треба **Full Chip Erase** і налаштування з нуля. Старі **CLI-дампи** з 4.3 і нижче часто **несумісні**, бо параметри перейменували й поміняли їм діапазони.

### Екосистема Betaflight

Крім прошивки, є ще **Betaflight Configurator**. Веб-застосунок був уже для 4.5 (Configurator 10.10), а від версії **2025.12** основним став **веб-конфігуратор** (`https://app.betaflight.com`) через **WebUSB / WebSerial**. Для Android, як і давніше, є нативні застосунки.

### Target, unified target і Cloud Build
Прошивка збирається під **target** — опис плати: процесор, котрі ніжки куди заведено (`resource`), котрий гіроскоп на котрому SPI. Від 4.3 майже всі плати — **unified targets**: один бінарник на сімейство процесора (наприклад, `STM32F405`) плюс текстовий конфіг плати (`board_name`, `manufacturer_id`, набір `resource`/`set`), котрий конфігуратор підтягує під час прошивання. Cloud Build (4.4+) збирає бінарник на сервері з вибраним набором функцій: протокол приймача, OSD, GPS, телеметрія, LED — чого не позначив, того в прошивці гет нема (звична причина «приймач мовчить»). `version` у CLI показує версію, target, дату й git-ревізію збірки; `BUILD KEY` (ключ збірки, аби її відтворити) друкує `status`, а список опцій віддає build.betaflight.com за цим ключем.

### Що робить планувальник кожні 125 мкс
`fc/tasks.c` описує задачі з періодом і пріоритетом; `scheduler/scheduler.c` їх вибирає. Критичні: `GYRO` (читання, фільтри) і `PID` (`taskMainPidLoop`: RC-команда → PID → мікшер → DShot) — на частоті гіроскопа / `pid_process_denom`. Решта — як лишиться час: `RX` (приймання й обробка кадрів, подієво), `SERIAL`, `BATTERY_*`, `GPS`, `OSD` (за `osd_framerate_hz`), `BLACKBOX`, `TELEMETRY`, `LED_STRIP`. CLI `tasks` показує фактичний період, середній і максимальний час кожної задачі та завантаження CPU; `status` — частоту гіроскопа, завантаження й прапорці арму. Перевантаження (> 85–90% на F4 з 8 кГц) — то пропуски задач, джиттер, прапорець `LOAD`: лікується `pid_process_denom = 2` або вимкненням функцій.

### Карта налаштування: де що живе
| Що | Де в конфігураторі | Ключові параметри CLI |
|---|---|---|
| Порти та пристрої | Ports | `serial`, `resource`, `serialrx_provider` |
| Приймач, канали, рейти | Receiver | `map`, `rates_type`, `roll_rc_rate`… |
| Режими на тумблерах | Modes | `aux` |
| Мотори, ESC, протокол | Motors | `motor_pwm_protocol`, `dshot_bidir`, `motor_poles`, `dshot_idle_value` (2025.12: `motor_idle`) |
| PID, фільтри, FF | PID Tuning | `set p_roll`… `simplified_*`, `gyro_lpf*`, `rpm_filter_*` |
| OSD | OSD | `osd_*_pos`, `osd_warn_bitmask` |
| Blackbox | Blackbox | `blackbox_device`, `blackbox_sample_rate`, `debug_mode` |
| Failsafe | Failsafe | `failsafe_procedure`, `failsafe_delay`, `rxfail` |
| Прошивка | Firmware Flasher | — |
Профілі: до 4 PID-профілів (`profile`) і 4 профілів рейтів (`rateprofile`), котрі перемикаються тумблером/adjustments — один «спокійний», один «гоночний».

### Розібраний приклад: порядок першого налаштування
Прошивка (Cloud Build: CRSF, OSD HD, GPS як є) → `resource`/target за замовчуванням → Ports (UART приймача) → Receiver (CRSF, перевірка каналів і `map` AETR) → Motors (DShot600, `motor_poles`, `dshot_bidir`, напрямок без пропів) → Modes (ARM, ANGLE, BEEPER, FAILSAFE) → Failsafe (DROP для першого польоту) → OSD (напруга, LQ, таймер, попередження) → Blackbox (2 кГц) → `diff all` у репозиторій (модуль «CI»). Перший політ — на стандартних PID: Betaflight 4.5 «з коробки» літає на 5" ліпше, ніж більшість ручних тюнів новачка; тюнінг — аж після логів.

{{diagram:bf-setup-map|Порядок першого налаштування: резервна копія → Ports → Receiver → Modes → Motors (без пропелерів) → OSD → PID і фільтри за логом.}}

## practice

### Встановлення Betaflight Configurator

**Варіант А — веб (найліпше для ПК):**

1. Браузер на базі **Chromium** (Chrome, Edge, Opera).
2. Відкрити `https://app.betaflight.com`.
3. Як уперше підключаєш FC — дозволити доступ до **USB**.

**Варіант Б — офлайн або старе середовище:**

- інсталятор із репозиторію GitHub Releases: `https://github.com/betaflight/betaflight-configurator/releases` (Windows / macOS / Linux).

### Підключення польотного контролера

1. USB-кабель **з передаванням даних** (не «лиш зарядка»).
2. У конфігураторі: порт (**COM*** / `/dev/ttyACM*`) → **Connect**.
3. Як порту нема — драйвери (**ImpulseRC Driver Fixer** або вручну у Windows).

**Перевірка:** вкладка **Setup** — 3D-модель повторює нахили. Ніц не реагує — дивись акселерометр або з'єднання.

### Резервна копія (CLI)

Заки щось правити: вкладка **CLI** → введи команду нижче → **Save to File**.

```text
diff all
```

`diff all` зберігає лиш **відмінності від дефолту** — файно для відновлення. `dump all` — для глибокої діагностики; **між мажорними версіями** переносити ним конфіг не радять.

### Оновлення прошивки (Firmware Flasher)

1. **Firmware Flasher** — цільовий контролер (часто сам ся визначає по USB).
2. Версія — остання стабільна **4.5.x**.
3. Увімкнути **Full chip erase**, як міняєш мажорну гілку.
4. **Load Firmware [Online]** → **Flash Firmware**; не висмикувати USB до кінця.
5. Після перезавантаження — відновити конфіг із бекапу (**CLI**) або налаштувати наново.

### Вкладка Configuration

- **Mixer** — тип рами (**Quad X** для звичайного FPV-квада).
- **Board and Sensor Alignment** — **Yaw degrees**, як FC повернутий на рамі.
- **Battery Voltage** — **VBAT**, аби показувало напругу.
- **ESC/Motor** — у теперішньому застосунку протокол DShot, **Bidirectional DShot** і Motor idle налаштовуються у вкладці **Motors**.
- **Motor Stop** — як мотори не мусять крутитися на нульовому газу після арму.

### Вкладка Ports

- **USB VCP** — окремий рядок у Ports (не UART1), MSP на ньому обов'язковий; UART1 — звичайний апаратний порт.
- **UART2/3/4** — **Serial RX** на тому порту, куди припаяно приймач.
- **UART5** (приклад) — **GPS**, швидкість **57600** або **115200**.

### Вкладка Receiver

- **Serial-based receiver** для CRSF / SBUS / FPORT.
- **Provider:** **CRSF** (ELRS, TBS), **SBUS** (FrSky, DJI і т. д.).
- Ворушиш стіки на пульті → повзунки в конфігураторі мусять рухатися.
- Діапазон **1000–2000** (центр **1500**); як ні — **rxrange** у CLI або endpoints на пульті.
- **Channel Map** (наприклад **AETR**, **TAER**), як канали переплутані.

### Вкладка Modes

Признач **AUX** на режими. Коротко, що є що:

- **ARM** — увімкнення моторів (ліпше 2-поз. тумблер).
- **ANGLE** — самовирівнювання, для навчання.
- **HORIZON** — гібрид стабілізації та акро.
- **ACRO** — за замовчуванням, окремого рядка в списку нема.
- **BEEPER** — шукати дрона.
- **GPS RESCUE** — як налаштовано GPS.

Для кожного режиму: **Add Range** → вибрати канал і діапазон положення перемикача.

### Калібрування датчиків

- **Акселерометр:** **Setup**, горизонтальна поверхня → **Calibrate Accelerometer**.
- **Магнітометр:** **Calibrate Magnetometer**, ~30 с крутити по осях; перевірити, ци збігається зі справжнім курсом.

### ESC і мотори (без пропелерів!)

**Небезпека:** завжди **знімай пропелери**, заки тестуєш мотори.

1. **Motors** — увімкнути **I understand the risks**.
2. **Motor 1** — перевірити, ци то той фізичний мотор (у Betaflight Quad X: Motor 1 — задній правий, 2 — передній правий, 3 — задній лівий, 4 — передній лівий).
3. Напрямок обертання — за схемою рами; виправляти дротами або **BLHeli / Bluejay**.
4. Переплутаний порядок/напрямок — звична причина, чом дрон перевертається на зльоті.

### Передпольотна перевірка

- **ARM без пропів** — мотори крутяться на малих обертах.
- **Нахил уперед** — передні мотори коротко додають газ (стабілізація реагує).
- **Failsafe** — вимкнути пульт; очікувана поведінка (посадка / **GPS Rescue**).
- **OSD** — напруга, таймер, режим (як маєш відеолінк).

## diagnostics
- **Симптом:** Конфігуратор не бачить контролер, порт не з'являється
  - Можлива причина: не встановлено драйвери (Windows), поганий USB-кабель, конфлікт портів.
  - Що зробити (перевірити): поміняти кабель на кабель із передаванням даних. Для Windows поставити драйвери через ImpulseRC Driver Fixer. Перезавантажити комп'ютер. Спробувати інший порт USB.

- **Симптом:** Контролер підключається, але 3D-модель не реагує на рух
  - Можлива причина: не відкалібровано акселерометр, пошкоджено датчик.
  - Що зробити (перевірити): відкалібрувати акселерометр на горизонтальній поверхні. Як не поможе — у CLI перевірити status і пересвідчитися, що ACCEL ся розпізнає. Перевірити, ци цілі дроти й паяння.

- **Симптом:** Дрон не армиться, у правому верхньому куті блимає помилка (наприклад, RXLOSS)
  - Можлива причина: приймач не має сигналу, не налаштовано порт, не той протокол.
  - Що зробити (перевірити): перевірити, що вибрано правильний UART для Serial RX і правильний протокол (CRSF/SBUS). Пересвідчитися, що пульт увімкнено і приймач зв'язаний (індикатор на приймачі світить). У вкладці Receiver перевірити, що повзунки рухаються.

- **Симптом:** Мотори крутяться, але дрон не злітає або перевертається, як пробуєш злетіти
  - Можлива причина: неправильний напрямок обертання моторів, неправильний порядок підключення, неправильна орієнтація FC.
  - Що зробити (перевірити): на вкладці Motors перевірити порядок моторів (Motor 1 — задній правий, Motor 2 — передній правий і т. д.). Перевірити напрямок обертання (за маркуванням на пропелерах). Пересвідчитися, що кут повороту FC (Yaw degrees) поставлено правильно.

- **Симптом:** Стіки в конфігураторі рухаються, але значення не доходять до 1000–2000
  - Можлива причина: кінцеві точки на пульті налаштовано неправильно.
  - Що зробити (перевірити): у налаштуваннях пульта відрегулювати Travel/Endpoints до 1000–2000 мкс. Інший варіант — підправити CLI-командою rxrange.

- **Симптом:** Дрон армиться, але мотори не крутяться (за вимкненого MOTOR_STOP)
  - Можлива причина: мінімальний газ (min_throttle) занизький, аби мотори рушили.
  - Що зробити (перевірити): з DShot `min_throttle` не використовується: на вкладці Motors підняти Motor Idle (`dshot_idle_value` у 4.5, `motor_idle` у 2025.12; дефолт 5.5%).
- **Симптом:** після прошивання приймач/GPS не працюють, хоч проводка правильна
  - Можлива причина: функцію не ввімкнено в Cloud Build.
  - Що зробити: `version` → список опцій; перепрошити з потрібними.
- **Симптом:** `LOAD` у прапорцях арму або CPU > 90%
  - Можлива причина: F4 на 8 кГц з усіма функціями.
  - Що зробити: `pid_process_denom = 2`, вимкнути LED/зайві телеметрії, `tasks` — аби знайти, хто найважчий.

## references
- Getting Started — Betaflight Documentation | https://betaflight.com/docs/wiki/getting-started | primary | A
- Betaflight 4.5 Release Notes | https://www.betaflight.com/docs/wiki/release/Betaflight-4-5-Release-Notes | primary | A
- Betaflight Configurator — Official Web App | https://app.betaflight.com | primary | A
- Betaflight CLI Documentation — Command Reference | https://betaflight.com/docs/wiki/guides/current/Cli | primary | A
- Betaflight Configurator — GitHub Releases | https://github.com/betaflight/betaflight-configurator/releases | primary | A
- Betaflight FAQ — How to Start | https://www.betaflight.com/docs/wiki/guides/current/FAQ | primary | A
- Betaflight Advanced Guide — iFlight | https://help.iflight-rc.eu/en-US/betaflight-advanced-guide-951396 | secondary | B
- GPS Rescue 4.5 — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/GPS-Rescue-v4-5 | primary | A
- Betaflight — Arming sequence and safety (arming flags) | https://www.betaflight.com/docs/wiki/guides/current/Arming-Sequence-And-Safety | secondary | B
- Joshua Bardwell — Betaflight Setup Tutorial | https://www.youtube.com/watch?v=xSzO6HP6yzs | secondary | B

