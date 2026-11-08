---
id: bf-intro
title: "Введение в Betaflight"
level: L1
readingTime: 25 мин
firmware: Betaflight 4.5+
status: published
tags:
  - Betaflight
  - начало работы
  - конфигуратор
  - настройка
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
---

## summary

Betaflight — открытая прошивка для полётных контроллеров мультикоптеров с упором на **низкую задержку** управления и гибкую настройку. В статье — цепочка от установки конфигуратора до первого безопасного вылета.

**После прочтения вы сможете:**

- прошить FC и сделать **бэкап** конфигурации (`diff all`);
- настроить **порты, приёмник, режимы** и калибровку датчиков;
- проверить **моторы и failsafe** перед полётом.

## theory

### Что такое Betaflight

Betaflight — форк **Cleanflight** (наследник Baseflight / STM32-порт MultiWii). Главный акцент стека — **производительность**: минимальная **latency** и высокая частота контура гироскопа (до **8 кГц**).

**Поддержка:** полётные контроллеры на **STM32** (F4, F7, H7). **Возможности прошивки:**

- многопрофильные **PID**;
- фильтрация гироскопа и **D-term**;
- цифровые протоколы к ESC (**DShot**, ProShot);
- **Blackbox** для логов;
- **CLI** для точной настройки.

### Архитектура прошивки

Прошивка модульная, задачи выполняются в реальном времени. **Основные задачи (tasks):**

- **Gyro task** — чтение гироскопа (до 8 кГц), фильтры.
- **PID task** — выход на моторы по ошибке **setpoint** vs **gyro**.
- **RX task** — приёмник (CRSF, SBUS, ELRS и др.).
- **Scheduler** — распределение времени между задачами.

**PID-цикл:** параметр `pid_process_denom` задаёт частоту контура PID. Пример: gyro **8 кГц**, `pid_process_denom = 2` → PID **4 кГц** (типичная отправная точка для большинства сборок).

### Версии прошивки и совместимость

**Betaflight 4.5** — предыдущая стабильная ветка (последний выпуск 4.5.5); актуальные — 2025.12.x и 2026.6.x. Ключевые изменения:

- GPS (в т.ч. модули **M10**) и **GPS Rescue**;
- магнитометры;
- **Angle / Horizon** с опцией *Earth referencing*;
- шрифты для HD VTX (Walksnail);
- фильтрация с учётом гармоник **RPM**.

**Важно:** при переходе **4.4 → 4.5** нужен **Full Chip Erase** и настройка с нуля. Старые **CLI-дампы** с 4.3 и ниже часто **несовместимы** из‑за переименований и диапазонов параметров.

### Экосистема Betaflight

Помимо прошивки — **Betaflight Configurator**. Веб-приложение было доступно уже для 4.5 (Configurator 10.10), а с версии **2025.12** основным стал **веб-конфигуратор** (`https://app.betaflight.com`) через **WebUSB / WebSerial**. Для Android по-прежнему есть нативные приложения.

### Target, unified target и Cloud Build
Прошивка собирается под **target** — описание платы: процессор, какие ноги на что заведены (`resource`), какой гироскоп на каком SPI. С 4.3 почти все платы — **unified targets**: один бинарник на семейство процессора (например, `STM32F405`) плюс текстовый конфиг платы (`board_name`, `manufacturer_id`, набор `resource`/`set`), который конфигуратор подгружает при прошивке. Cloud Build (4.4+) собирает бинарник на сервере с выбранным набором функций: протокол приёмника, OSD, GPS, телеметрия, LED — чего не отметил, того в прошивке нет (типичная причина «приёмник молчит»). `version` в CLI показывает версию, target, дату и git-ревизию сборки; `BUILD KEY` (ключ сборки для воспроизведения) печатает `status`, а список опций отдаёт build.betaflight.com по этому ключу.

### Что делает планировщик каждые 125 мкс
`fc/tasks.c` описывает задачи с периодом и приоритетом; `scheduler/scheduler.c` выбирает их. Критичные: `GYRO` (чтение, фильтры) и `PID` (`taskMainPidLoop`: RC-команда → PID → миксер → DShot) — на частоте гироскопа / `pid_process_denom`. Остальные — по остаточному принципу: `RX` (приём и обработка кадров, событийно), `SERIAL`, `BATTERY_*`, `GPS`, `OSD` (по `osd_framerate_hz`), `BLACKBOX`, `TELEMETRY`, `LED_STRIP`. CLI `tasks` показывает фактический период, среднее и максимальное время каждой задачи и загрузку CPU; `status` — частоту гироскопа, загрузку и флаги арма. Перегрузка (> 85–90% на F4 с 8 кГц) — пропуски задач, джиттер, флаг `LOAD`: лечится `pid_process_denom = 2` или отключением функций.

### Карта настройки: где что живёт
| Что | Где в конфигураторе | Ключевые параметры CLI |
|---|---|---|
| Порты и устройства | Ports | `serial`, `resource`, `serialrx_provider` |
| Приёмник, каналы, рейты | Receiver | `map`, `rates_type`, `roll_rc_rate`… |
| Режимы на тумблерах | Modes | `aux` |
| Моторы, ESC, протокол | Motors | `motor_pwm_protocol`, `dshot_bidir`, `motor_poles`, `dshot_idle_value` (2025.12: `motor_idle`) |
| PID, фильтры, FF | PID Tuning | `set p_roll`… `simplified_*`, `gyro_lpf*`, `rpm_filter_*` |
| OSD | OSD | `osd_*_pos`, `osd_warn_bitmask` |
| Blackbox | Blackbox | `blackbox_device`, `blackbox_sample_rate`, `debug_mode` |
| Failsafe | Failsafe | `failsafe_procedure`, `failsafe_delay`, `rxfail` |
| Прошивка | Firmware Flasher | — |
Профили: до 4 PID-профилей (`profile`) и 4 профилей рейтов (`rateprofile`), переключаемые тумблером/adjustments — один «спокойный», один «гоночный».

### Разобранный пример: порядок первой настройки
Прошивка (Cloud Build: CRSF, OSD HD, GPS если есть) → `resource`/target по умолчанию → Ports (UART приёмника) → Receiver (CRSF, проверка каналов и `map` AETR) → Motors (DShot600, `motor_poles`, `dshot_bidir`, направление без пропов) → Modes (ARM, ANGLE, BEEPER, FAILSAFE) → Failsafe (DROP для первого полёта) → OSD (напряжение, LQ, таймер, предупреждения) → Blackbox (2 кГц) → `diff all` в репозиторий (модуль «CI»). Первый полёт — на умолчаниях PID: Betaflight 4.5 «из коробки» летает на 5" лучше, чем большинство ручных тюнов новичка; тюнинг — после логов.

{{diagram:bf-setup-map|Порядок первой настройки: резервная копия → Ports → Receiver → Modes → Motors (без пропеллеров) → OSD → PID и фильтры по логу.}}

## practice

### Установка Betaflight Configurator

**Вариант А — веб (рекомендуется для ПК):**

1. Браузер на базе **Chromium** (Chrome, Edge, Opera).
2. Открыть `https://app.betaflight.com`.
3. При первом подключении FC разрешить доступ к **USB**.

**Вариант Б — офлайн или старая среда:**

- установщик с репозитория GitHub Releases: `https://github.com/betaflight/betaflight-configurator/releases` (Windows / macOS / Linux).

### Подключение полётного контроллера

1. USB-кабель **с передачей данных** (не «только зарядка»).
2. В конфигураторе: порт (**COM*** / `/dev/ttyACM*`) → **Connect**.
3. При отсутствии порта — драйверы (**ImpulseRC Driver Fixer** или вручную в Windows).

**Проверка:** вкладка **Setup** — 3D-модель повторяет наклоны. Нет реакции — акселерометр или соединение.

### Резервная копия (CLI)

Перед любыми правками: вкладка **CLI** → введите команду ниже → **Save to File**.

```text
diff all
```

`diff all` сохраняет только **отличия от дефолта** — удобно для восстановления. `dump all` — для глубокой диагностики; **между мажорными версиями** для переноса конфига не рекомендуется.

### Обновление прошивки (Firmware Flasher)

1. **Firmware Flasher** — целевой контроллер (часто определяется по USB).
2. Версия — последняя стабильная **4.5.x**.
3. Включить **Full chip erase** при смене мажорной ветки.
4. **Load Firmware [Online]** → **Flash Firmware**; не отключать USB до конца.
5. После перезагрузки — восстановить конфиг из бэкапа (**CLI**) или настроить заново.

### Вкладка Configuration

- **Mixer** — тип рамы (**Quad X** для типичного FPV-квада).
- **Board and Sensor Alignment** — **Yaw degrees**, если FC повёрнут на раме.
- **Battery Voltage** — **VBAT** для отображения напряжения.
- **ESC/Motor** — в текущем приложении протокол DShot, **Bidirectional DShot** и Motor idle настраиваются во вкладке **Motors**.
- **Motor Stop** — если моторы не должны крутиться на нулевом газу после арм.

### Вкладка Ports

- **USB VCP** — отдельная строка в Ports (не UART1), MSP на ней обязателен; UART1 — обычный аппаратный порт.
- **UART2/3/4** — **Serial RX** на том порту, куда припаян приёмник.
- **UART5** (пример) — **GPS**, скорость **57600** или **115200**.

### Вкладка Receiver

- **Serial-based receiver** для CRSF / SBUS / FPORT.
- **Provider:** **CRSF** (ELRS, TBS), **SBUS** (FrSky, DJI и др.).
- Стики на пульте → ползунки в конфигураторе должны двигаться.
- Диапазон **1000–2000** (центр **1500**); иначе **rxrange** в CLI или endpoints на пульте.
- **Channel Map** (например **AETR**, **TAER**) при перепутанных каналах.

### Вкладка Modes

Назначьте **AUX** на режимы. Кратко по смыслу:

- **ARM** — включение моторов (лучше 2-поз. тумблер).
- **ANGLE** — самовыравнивание, обучение.
- **HORIZON** — гибрид стабилизации и акро.
- **ACRO** — по умолчанию, в списке отдельной строки нет.
- **BEEPER** — поиск дрона.
- **GPS RESCUE** — если настроен GPS.

Для каждого режима: **Add Range** → выбрать канал и диапазон положения переключателя.

### Калибровка датчиков

- **Акселерометр:** **Setup**, горизонтальная поверхность → **Calibrate Accelerometer**.
- **Магнитометр:** **Calibrate Magnetometer**, ~30 с вращений по осям; проверить согласованность с реальным курсом.

### ESC и моторы (без пропеллеров!)

**Опасность:** всегда **снимайте пропеллеры** перед тестом моторов.

1. **Motors** — включить **I understand the risks**.
2. **Motor 1** — проверить соответствие физическому мотору (в Betaflight Quad X: Motor 1 — задний правый, 2 — передний правый, 3 — задний левый, 4 — передний левый).
3. Направление вращения — по схеме рамы; править проводами или **BLHeli / Bluejay**.
4. Несовпадение порядка/направления — типичная причина переворота при взлёте.

### Предполётная проверка

- **ARM без пропов** — моторы крутятся на малых оборотах.
- **Наклон вперёд** — передние моторы кратко добавляют газ (стабилизация реагирует).
- **Failsafe** — выключить пульт; ожидаемое поведение (посадка / **GPS Rescue**).
- **OSD** — напряжение, таймер, режим (если используете видеолинк).

## diagnostics
- **Симптом:** Конфигуратор не видит контроллер, порт не появляется
  - Возможная причина: не установлены драйверы (Windows), некачественный USB-кабель, конфликт портов.
  - Что проверить/сделать: заменить кабель на кабель с передачей данных. Для Windows установить драйверы через ImpulseRC Driver Fixer. Перезагрузить компьютер. Попробовать другой порт USB.

- **Симптом:** Контроллер подключается, но 3D-модель не реагирует на движение
  - Возможная причина: не откалиброван акселерометр, повреждён датчик.
  - Что проверить/сделать: выполнить калибровку акселерометра на горизонтальной поверхности. Если не помогает — в CLI проверить status и убедиться, что ACCEL распознаётся. Проверить целостность проводов и пайку.

- **Симптом:** Дрон не армуется, в правом верхнем углу мигает ошибка (например, RXLOSS)
  - Возможная причина: приёмник не получает сигнал, не настроен порт, неверный протокол.
  - Что проверить/сделать: проверить, что выбран правильный UART для Serial RX, выбран верный протокол (CRSF/SBUS). Убедиться, что пульт включён и приёмник связан (индикатор на приёмнике горит). Во вкладке Receiver проверить, что ползунки движутся.

- **Симптом:** Моторы вращаются, но дрон не взлетает или переворачивается при попытке
  - Возможная причина: неправильное направление вращения моторов, неверный порядок подключения, неправильная ориентация FC.
  - Что проверить/сделать: на вкладке Motors проверить соответствие порядка моторов (Motor 1 — задний правый, Motor 2 — передний правый и т.д.). Проверить направление вращения (маркировкой на пропеллерах). Убедиться, что угол поворота FC (Yaw degrees) установлен правильно.

- **Симптом:** Стики в конфигураторе двигаются, но значения не достигают 1000–2000
  - Возможная причина: конечные точки на пульте настроены неверно.
  - Что проверить/сделать: в настройках пульта отрегулировать Travel/Endpoints до 1000–2000 мкс. Альтернативно использовать CLI-команду rxrange для коррекции.

- **Симптом:** Дрон армуется, но моторы не вращаются (при выключенном MOTOR_STOP)
  - Возможная причина: минимальный газ (min_throttle) слишком низкий для старта моторов.
  - Что проверить/сделать: с DShot `min_throttle` не используется: на вкладке Motors поднять Motor Idle (`dshot_idle_value` в 4.5, `motor_idle` в 2025.12; дефолт 5.5%).
- **Симптом:** после прошивки приёмник/GPS не работают, хотя проводка верна
  - Возможная причина: функция не включена в Cloud Build.
  - Что сделать: `version` → список опций; перепрошить с нужными.
- **Симптом:** `LOAD` в флагах арма или CPU > 90%
  - Возможная причина: F4 на 8 кГц со всеми функциями.
  - Что сделать: `pid_process_denom = 2`, отключить LED/лишние телеметрии, `tasks` для поиска тяжёлых.

## references
- Getting Started — Betaflight Documentation | https://betaflight.com/docs/wiki/getting-started | primary | A
- Betaflight 4.5 Release Notes | https://www.betaflight.com/docs/wiki/release/Betaflight-4-5-Release-Notes | primary | A
- Betaflight Configurator — Official Web App | https://app.betaflight.com | primary | A
- Betaflight CLI Documentation — Command Reference | https://betaflight.com/docs/wiki/guides/current/Cli | primary | A
- Betaflight Configurator — GitHub Releases | https://github.com/betaflight/betaflight-configurator/releases | primary | A
- Betaflight FAQ — How to Start | https://www.betaflight.com/docs/wiki/guides/current/FAQ | primary | A
- Betaflight Advanced Guide — iFlight | https://help.iflight-rc.eu/en-US/betaflight-advanced-guide-951396 | secondary | B
- How to Enable GPS Rescue — SpeedyBee Docs | https://docs.speedybee.cn/en/fpv/gps/gps-faq/how-to-enable-gps-rescue-mode-and-failsafe.html | secondary | B
- My FPV Quad won't arm — iFlight Support | https://iflightrc.freshdesk.com/support/solutions/articles/48001149405/thumbs_down | secondary | B
- Joshua Bardwell — Betaflight Setup Tutorial | https://www.youtube.com/watch?v=xSzO6HP6yzs | secondary | B

