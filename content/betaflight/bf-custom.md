---
id: bf-custom
title: "Свои сборки прошивок"
level: L4
readingTime: 40 мин
firmware: Betaflight 4.5 (сверено с 4.5.3, Configurator 10.10) и 2025.12 (2025.12.5) / ArduPilot 4.5+
status: published
added: 2026-11-07
tags:
  - cloud build
  - сборка
  - targets
related:
  - bf-cli
  - ap-quadplane
next: []
---

## summary
Флеш-память полётника не резиновая: включить всё сразу нельзя, а значит, прошивка под твой аппарат — это выбор. Модуль разбирает Cloud Build в Betaflight по исходникам 4.5.3 и Configurator 10.10: что уходит на сервер сборки, какие группы опций есть, что делают Core Only и Custom Defines, где на плате виден ключ сборки и как проверить, что внутри прошивки. Отдельно — почему отсутствующая опция исчезает молча и как перенести `diff all` в сборку с другим набором опций, не потеряв половину настроек. Для ArduPilot — сборка из исходников с отключением подсистем (кейс HeeWing F405). Лабораторная без железа — Python-порт логики CLI 4.5.3, который предсказывает, какие строки `diff all` не примутся и сохранится ли конфиг.

## theory
### Зачем вообще собирать
- На F411/F405 стандартная прошивка со всеми опциями не влезает или влезает без нужной функции.
- Нужна опция, которой нет в стандартном наборе (дальномер, транспондер, экзотический протокол).
- Нужно убрать то, чего на борту нет и не будет (GPS, компас, OSD-чип), освободив место и память.

Сколько места на самом деле (линкер-скрипты 4.5.3): у F411 и F722 512 КБ флеша, у F405 1 МБ, у H743 — 2 МБ. После сектора конфига (16 КБ) и первого 16-КБ сектора (таблица векторов, на F411 ещё инициализированные данные) основной код (`.text`) должен влезть в регион `FLASH1` (на F722 он называется `AXIM_FLASH1`): 480 КБ на F411/F722 и 992 КБ на F405. Сумма регионов кода больше (496 и 1008 КБ), но упирается сборка обычно именно в `FLASH1`; дальше в курсе считаем по нему. «Классическая» сборка без облака (так собирает CI проекта и локальный `make` без опций) включает почти все функции только на платах с флешем от 1024 КБ. На 512-килобайтных платах этот блок `common_pre.h` пропускается целиком: нет GPS, LED-ленты, транспондера, дальномера, MAVLink-телеметрии. Поэтому GPS на F411 — только через свою сборку.

### Betaflight: Cloud Build
Начиная с 4.4 прошивку собирает сервер build.betaflight.com под твой список опций. Прошивка Betaflight состоит из двух частей:

- **target** — семейство процессора (`STM32F405`, `STM32F411`, `STM32H743`…), общий код;
- **конфиг платы** (`config.h` из репозитория betaflight/config): пины, гироскоп, флеш, OSD-чип. Драйверы конкретной платы приходят из него сами, их выбирать не надо.

Что происходит при нажатии кнопки сборки (по `firmware_flasher.js` Configurator 10.10):

1. Configurator отправляет на `/api/builds` запрос из трёх полей: `target` (плата), `release` (версия) и `options` — список строк (в Expert Mode для Development ещё `commit`). Первая строка — `CLOUD_BUILD`, дальше значения выбранных пунктов всех списков, например `USE_SERIALRX_CRSF`, `USE_DSHOT`, `USE_OSD_SD`, `USE_GPS`.
2. Сервер собирает прошивку с этими флагами. В исходниках `CLOUD_BUILD` выключает классический набор (`common_pre.h:52–272`): в прошивку попадает то, что пришло в списке, и то, что опции тянут за собой. Кроме того, сервер явно добавляет базовые флаги, которых нет в списке Configurator (например, без `USE_SERIALRX` и `USE_TELEMETRY` `common_post.h` вырезал бы CRSF целиком); какие именно — в открытом коде не видно, это вывод курса из того, что облачные сборки с CRSF работают. Точный набор показывают `/api/builds/<ключ>/json` и лог сборки. Например, `USE_GPS` добавляет GPS Rescue и драйверы NMEA/UBLOX, а `USE_OSD_SD` или `USE_OSD_HD` — OSD, CMS и меню.
3. В прошивку вшивается ключ сборки `BUILD_KEY` (`build/version.c:33–43`). Это 32 символа, по которым сервер находит запрос и лог сборки. Одинаковый запрос сервер отдаёт из кэша: статус `success (cached)`.
4. Прошивка. Если Expert Mode выключен, Configurator всегда стирает флеш целиком (Full chip erase, `firmware_flasher.js:581–585`): конфиг пропадает, `diff all` нужен до прошивки, а не после.

Если плата подключена к Firmware Flasher, Configurator читает её ключ и подставляет в списки опции текущей сборки (`loadOptionsByBuildKey`). Это самый простой способ «повторить, но добавить одну опцию».

{{diagram:bf-cloud-build-pipeline|Путь Cloud Build: опция, которой не было в запросе, отсутствует в коде — исчезают настройка, команда CLI и вкладка, без единого сообщения об ошибке.}}

Типы выпусков в списке версий: `Release`, `Release And Release Candidate`, `Development`. Для `Development` в Expert Mode можно выбрать конкретный коммит.

### Группы опций (Configurator 10.10 ↔ Betaflight 4.5)
Список приходит с сервера (`/api/options/<версия>`). Прошивка 4.5 хранит его копию в `msp/msp_build_info.h`: по ней плата сообщает Configurator, что в неё собрано (MSP_BUILD_INFO, API 1.46).

| Группа в интерфейсе | Опции 4.5 (`USE_` + имя) | Заметки |
|---|---|---|
| Radio Protocol | SERIALRX_CRSF, SERIALRX_FPORT, SERIALRX_GHST, SERIALRX_IBUS, SERIALRX_JETIEXBUS, RX_PPM, SERIALRX_SBUS, SERIALRX_SPEKTRUM, SERIALRX_SRXL2, SERIALRX_SUMD, SERIALRX_SUMH, SERIALRX_XBUS | для CRSF, FPort и GHST поле телеметрии блокируется с пометкой `Automatically Included` |
| Telemetry Protocol | TELEMETRY_FRSKY_HUB, TELEMETRY_HOTT, TELEMETRY_IBUS_EXTENDED, TELEMETRY_LTM, TELEMETRY_MAVLINK, TELEMETRY_SMARTPORT, TELEMETRY_SRXL | телеметрия ELRS/CRSF отдельно не выбирается |
| Other Options | ACRO_TRAINER, AKK_SMARTAUDIO, BATTERY_CONTINUE, CAMERA_CONTROL, DASHBOARD, EMFAT_TOOLS, ESCSERIAL_SIMONK, FRSKYOSD, GPS, LED_STRIP, LED_STRIP_64, MAG, OSD_SD, OSD_HD, PINIO, RACE_PRO, SERVOS, VTX | здесь же OSD: `OSD_SD` — аналоговый (MAX7456), `OSD_HD` — цифровой через MSP DisplayPort |
| Motor Protocol | BRUSHED, DSHOT, MULTISHOT, ONESHOT, PROSHOT, PWM_OUTPUT | при `CLOUD_BUILD` DShot сам не включается (`common_pre.h:52–53`): без `DSHOT` в списке DShot в прошивке нет |

*2025.12:* к списку добавлены `SERIALRX_MAVLINK`, `ALTITUDE_HOLD`, `POSITION_HOLD`, `WING`, `CHIRP`, `SOFTSERIAL`, MSP API 1.47. Configurator 10.10 работает только с API до 1.46, поэтому прошивки 2025.12 собирают и прошивают в Betaflight App (`bf-intro`).

Ловушки зависимостей из `common_pre.h` 4.5.3:

- только `OSD_HD` без `OSD_SD` → драйвер MAX7456 вырезается (`#undef USE_MAX7456`, строка 414), даже если чип распаян на плате: аналоговый OSD пропадёт;
- `LED_STRIP` даёт 32 светодиода, `LED_STRIP_64` — 64 (`LED_STRIP_MAX_LENGTH`); на F411 `LED_STRIP_64` не поддерживается: `#error` в `target/STM32F411/target.h:87–88`, сборка упадёт;
- `VTX` тянет SmartAudio, Tramp, MSP VTX и таблицы VTX;
- без `MAG` нет компаса, без `GPS` нет GPS Rescue, и вкладка GPS скрыта.

### Core Only и Custom Defines
**Core Only** (чекбокс `coreBuildModeCheckbox`) шлёт вместо списка одну строку `CORE_BUILD`. По описанию в Configurator это драйверы железа и ограниченный набор функций: сборка нужна, чтобы проверить, видит ли плата гироскоп, флеш и OSD-чип, а не для полёта. В исходниках 4.5.3 `CORE_BUILD` напрямую отключает немногое (например, Launch Control, `common_pre.h:380–389`); полный набор того, что сервер добавляет к такому запросу, в открытом коде не виден.

**Custom Defines** — поле в Expert Mode. Имена вводятся через пробел **без** префикса `USE_`, сервер добавит его сам (подсказка `firmwareFlasherCustomDefinesDescription`). Каждое слово уходит в тот же список `options`. Примеры флагов, которые есть в исходниках 4.5.3, но которых нет в списках:

| Ввести | Флаг | Что даёт |
|---|---|---|
| `RANGEFINDER RANGEFINDER_TF` | `USE_RANGEFINDER`, `USE_RANGEFINDER_TF` | лидары Benewake TFmini/TF02, `feature RANGEFINDER` |
| `GPS_LAP_TIMER` | `USE_GPS_LAP_TIMER` | GPS-секундомер круга и пункт меню OSD (только вместе с `GPS`) |
| `TRANSPONDER` | `USE_TRANSPONDER` | ИК-транспондер хронометража; в Configurator 10.10 вкладка и пункт Features не появятся (опции нет в MSP_BUILD_INFO 4.5), настройка только через CLI |
| `ESC_SENSOR` | `USE_ESC_SENSOR` | телеметрия ESC по проводу (в 4.5.3 включается сам вместе с DShot, `common_post.h:159–161`; без DShot его нет) |

Опечатка в имени обычно не ломает сборку: неизвестный `USE_…` компилятор просто не заметит, и функции не будет. `build request error (please check build configuration, e.g. custom defines)` означает, что сервер отклонил сам запрос `POST /api/builds`; почему — из кода Configurator не видно. Имена разбиваются по одиночному пробелу (`split(' ')`): двойной пробел даёт пустой элемент списка. `failed (please check log)` — запрос принят, но не собрался; ссылка `Show Log.` открывает лог компилятора. Опции, которой нужен пин, назначают его через `resource` в CLI.

### Как узнать, что внутри прошивки
Справочник команд и мест, где видно состав сборки (строки формата — из `cli.c` 4.5.3):

| Где | Что видно о сборке | Как выглядит |
|---|---|---|
| `version` | имя прошивки, target, идентификатор платы, версия, дата, git-ревизия, MSP API | `# Betaflight / STM32F405 (S405) 4.5.3 <дата> / <время> (<git>) MSP API: 1.46`; ниже `# config rev: …` (сборка с конфигом платы) и `# board: manufacturer_id: …, board_name: …` |
| `status` | ключ сборки, только у облачной | `BUILD KEY: <32 символа> (<имя выпуска>)`; у локальной строки нет |
| `get <часть имени>` | есть ли параметры подсистемы (поиск по подстроке) | нет ни одного → `###ERROR IN get: INVALID NAME: gps_provider###` |
| `help <строка>` | есть ли команда | нет совпадений → `###ERROR IN help: NO MATCHES FOR 'smix'###` |
| `feature list` | **не** проверка сборки: таблица имён одна на все сборки | 4.5.3: `feature GPS` без GPS печатает `unavailable`, `feature LED_STRIP` без ленты включается молча; *2025.12:* любой отсутствующий пункт — `Unavailable <ИМЯ>`, ошибкой batch это не считается |
| `diff all` | версия в начале, ключа нет | `# version`, затем закомментированная строка `# Betaflight / … MSP API: 1.46` (без `# board:`) |
| Setup → Firmware info | ссылки `Config`, `Log`, `Options` на build.betaflight.com/api/builds/<ключ>/… | локальная сборка: `Local Build - no Cloud information` |
| Firmware Flasher и журнал Configurator | опции текущей сборки подставляются в списки флешера | при подключении в журнале `Build Key: <ключ>` |

Configurator 10.10 по списку опций ещё и **прячет вкладки**: GPS, LED Strip, OSD и Servos показываются, только если в сборке есть соответствующая опция (`gui.js:57–63`, `serial_backend.js:611–620`; подстроку `osd` даёт и `USE_FRSKYOSD`). Вкладка Transponder в 4.5 скрыта на любой сборке: такой опции нет в MSP_BUILD_INFO. Список опций плата сообщает сама (MSP_BUILD_INFO, API 1.46), поэтому так же ведут себя и локальные сборки. На вкладке Features так же пропадают пункты, чьей опции нет (`Features.js:44–51`), в том числе TRANSPONDER и SONAR.

{{lesson:bf-cli|Как сохранять `diff all`, читать `dump` и автоматизировать проверки CLI — там подробно.}}

### Чего нет в сборке, того нет нигде
Главный риск своей сборки в том, что ошибки молчат. Флаг `USE_*` убирает код целиком: параметры, команды CLI, элементы OSD, режимы. Прошивка при этом загружается и летает, просто функции нет. Коварнее всего таблицы значений: имена протоколов в `serialrx_provider` и `motor_pwm_protocol` одни на все сборки. Поэтому `set serialrx_provider = CRSF` и `set motor_pwm_protocol = DSHOT600` принимаются без ошибки и в сборке без CRSF или DShot, а приёмник и моторы молчат, и это похоже на ошибку проводки (`bf-ports`). Исчезают совсем параметры подсистемы (`dshot_bidir`, `gps_*`) и команды (`servo`, `smix`, `led`, `gpspassthrough`). Если сборка не влезает, компоновщик GNU ld сообщает, что регион `FLASH1` переполнен на N байт; заполнение каждого региона печатает `-Wl,--print-memory-usage` (`Makefile:295`).

### Восстановление конфига после смены сборки
`diff all` устроен так (`cli.c:6197–6376`): строка версии, `batch start`, `defaults nosave` (сброс к умолчаниям), потом `board_name`, `manufacturer_id`, `resource`, `feature`, `serial`, `set` по разделам, профили и в конце `save`. Пока идёт batch, **любая** ошибка помечает весь пакет. Строка с несуществующим параметром даёт `INVALID NAME`, отсутствующая команда — `###ERROR IN input: UNKNOWN COMMAND, TRY 'HELP'###`. Тогда `save` в конце не сохраняет ничего и печатает:

- `###ERROR IN save: ERRORS WERE DETECTED - PLEASE REVIEW BEFORE CONTINUING###`
- `###ERROR IN save: PLEASE FIX ERRORS THEN 'SAVE'###`

После этого batch сбрасывается. Принятые строки уже применены в памяти, и второй `save`, набранный вручную, запишет их. Порядок действий:

1. До прошивки: `diff all`, `version`, `status` — в файл (ключ сборки есть только в выводе `status`).
2. После прошивки вставить `diff all` целиком и прочитать **все** строки `###ERROR`.
3. Каждую ошибку объяснить: опции нет в новой сборке (это нормально, если от неё отказались сознательно) или имя переименовано между версиями (тогда это не та версия, `bf-intro`).
4. `save` вручную, перезагрузка, затем `diff all` ещё раз и сравнение с исходным файлом построчно (`git diff`).

Переносить `diff all` между **версиями** (4.5 → 2025.12) так нельзя: имена и смысл параметров менялись, и часть строк примется с другим результатом без ошибки (`bf-intro`, таблица переименований).

### ArduPilot: сборка из исходников
ArduPilot собирается `waf`: `./waf configure --board <board>` и `./waf copter` (или `plane`). Таргет описывается в `libraries/AP_HAL_ChibiOS/hwdef/<board>/hwdef.dat`: пины, шины, какие драйверы включать. Там же через `define`-строки отключают ненужное.

Для плат с маленькой флешью существуют урезанные конфигурации: много функций в коде обёрнуто проверками `#if AP_<FEATURE>_ENABLED`, и hwdef может задать `define AP_<FEATURE>_ENABLED 0`. Веб-инструмент Custom Firmware Builder (ссылка в документации «Building the code») делает то же через интерфейс: ставишь галочки, получаешь прошивку.

### Кейс: HeeWing F405 без GPS
Стоковый F405 в проекте HeeWing T1 — плата с ограниченной флешью: нет Lua-скриптинга, часть возможностей урезана. Варианты прошивки, которые планировались для него: убрать поддержку GPS (на этой сборке он не используется для арма и базового полёта) и лишние драйверы, чтобы освободить место под нужное. Это осмысленное решение, если понимаешь последствия: без GPS в прошивке не будет ни RTL, ни геозоны по координатам — не только «сейчас», а вообще.

### Правила своих сборок
1. Хранить конфигурацию сборки в git рядом с параметрами: список опций Betaflight или `hwdef`-патч ArduPilot.
2. Называть сборку с датой и хешем коммита; вывод `version` и BUILD KEY из `status` должны совпадать с записью.
3. Перед прошивкой — полный бэкап (`diff all` / файл параметров), после — перечитать всё критичное.
4. Не смешивать: своя сборка + стандартный конфиг от другой версии = непредсказуемость.
5. Ориентир курса: держать запас не меньше 5 % региона `FLASH1` (на F411 это 24 КБ). Патч-выпуск той же ветки может оказаться толще, и сборка «впритык» перестанет собираться с теми же опциями.

### Локальная сборка Betaflight (когда Cloud Build не подходит)
```bash
git clone https://github.com/betaflight/betaflight && cd betaflight
make arm_sdk_install                      # toolchain
make configs                              # unified target configs
make STM32H743 EXTRA_FLAGS="-DUSE_GPS_LAP_TIMER"   # family target + extra define
# или с конфигом конкретной платы:
make SPEEDYBEEF405V4 EXTRA_FLAGS="-DUSE_..."
```
`make configs` клонирует репозиторий betaflight/config в `src/config`. `make <ИМЯ_ПЛАТЫ>` — то же, что `make CONFIG=<ИМЯ_ПЛАТЫ>`: target берётся из `FC_TARGET_MCU` в `config.h` платы (`mk/config.mk`), а `TARGET` и `CONFIG` одновременно задавать нельзя. Имя платы в примере условное, бери своё из списка конфигов. Результат: `obj/betaflight_4.5.3_STM32F405_<ПЛАТА>.hex` (`Makefile:309–324`). Его прошивают кнопкой «Load Firmware [Local]».

Два способа передать флаги:

- `OPTIONS="CLOUD_BUILD USE_SERIALRX USE_SERIALRX_CRSF USE_TELEMETRY USE_DSHOT USE_OSD_SD USE_GPS"` — `Makefile:252` добавляет каждому слову `-D`. С `CLOUD_BUILD` классический набор выключен, и в прошивку попадает только перечисленное. Список Configurator дословно не годится: `USE_SERIALRX` и `USE_TELEMETRY` определены только в классическом блоке (`common_pre.h:178`, `191`), а без них `common_post.h:198–223` вырежет CRSF и его телеметрию. Облако добавляет такие базовые флаги само (их набор виден в `/api/builds/<ключ>/json`) — сверяй свой список с ним. Так на F411 получают GPS, которого нет в классической 512-килобайтной сборке;
- `EXTRA_FLAGS="-DUSE_…"` — флаги дописываются в конец строки компилятора. Это способ **добавить**, а не убрать: `-U` из командной строки не отменит `#define` в `common_pre.h`, который срабатывает позже. Ловушка: флаг, который `common_pre.h` для этого target уже задаёт без `#ifndef` (например, `USE_RANGEFINDER` на H743 с флешем ≥ 1024 КБ), через `EXTRA_FLAGS` даёт `error: "USE_RANGEFINDER" redefined` — сборка идёт с `-Werror`. Убирают опции только через гейт `CLOUD_BUILD` (или `CORE_BUILD`) с явным списком — неважно, через `OPTIONS` или `EXTRA_FLAGS="-DCLOUD_BUILD …"`.

У локальной сборки нет `BUILD_KEY`: строки в `status` нет, Setup пишет `Local Build - no Cloud information`. Вкладки и пункты Features Configurator прячет так же, как у облачной: список опций плата сообщает сама (MSP_BUILD_INFO). Поэтому список `OPTIONS` и хеш коммита записывай сам. Для проверки без железа есть `make SITL` и `make test` (юнит-тесты gtest, модуль «Как читать исходники»).

### Что ломается после своей сборки и как проверять
1. По BUILD KEY из `status` (`https://build.betaflight.com/api/builds/<key>/json`) — ожидаемые опции.
2. `status` — гироскоп найден.
3. Ports/Receiver — приёмник отвечает.
4. Motors — DShot и bidir работают без пропов.
5. OSD видно.
6. `diff all` совпадает с бэкапом по смыслу.

Чек-лист — в журнал аппарата вместе с хешем коммита и `EXTRA_FLAGS`/`OPTIONS`.

{{diagram:bf-custom-verify-flow|Шесть проверок после своей сборки: молчащий приёмник или пропавший OSD — это обычно состав сборки, а не проводка.}}

{{diagram:fw-build-paths|Какой путь сборки выбрать: опции — Cloud Build или custom.ardupilot.org, свой код — локальная сборка.}}

### Место в системе

- **Получает:** список того, что реально стоит на борту: протокол приёмника (`bf-ports`), тип OSD — аналоговый или HD (`bf-hd-osd-video`), GPS (`bf-gps-setup`), сервы (`bf-servos-pwm`); ограничение — объём флеш-памяти полётника.
- **Отдаёт:** прошивку с выбранным набором опций и BUILD KEY в `status`, по которому состав сборки проверяется и воспроизводится (`bf-cli`).
- **Если ошибиться здесь:** не отметил протокол приёмника → приёмник «молчит» при любой распайке, а выглядит это как ошибка проводки или портов (`bf-ports`). Собрал без HD OSD → видео в очках есть, OSD нет при любой маске порта (`bf-hd-osd-video`). Собрал без SERVOS → в CLI нет команд `servo` и `smix` (`bf-servos-pwm`).

## practice
### Betaflight: сборка под конкретный аппарат
1. Firmware Flasher → таргет платы → версия. Если плата подключена, Configurator подставит опции её текущей сборки — начни с них.
2. Опции: приёмник (CRSF), Motor Protocol (DShot — обязательно, при облачной сборке он сам не включается), OSD (`OSD_SD` для аналога, `OSD_HD` для цифры, оба — если не уверен), телеметрия, GPS только если он есть.
3. Expert Mode → Custom Defines, если нужно что-то вне списков: имена без `USE_`, через пробел.
4. Build → Flash. После прошивки в CLI: `version` и `status` — сохранить вывод (BUILD KEY — в `status`) в папку дрона.
5. Восстановить конфиг из `diff all` **той же** версии, прочитать все строки `###ERROR`, затем `save` вручную, если ошибки объяснены.

### ArduPilot: сборка из исходников
```
git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git
cd ardupilot
Tools/environment_install/install-prereqs-ubuntu.sh -y
./waf configure --board MatekF405-Wing   # example board name; use yours
./waf plane
ls build/MatekF405-Wing/bin/             # arduplane.apj / .bin / .hex
```

Отключение функции: добавить в `hwdef.dat` платы (или в отдельный файл extra hwdef) строку вида `define AP_<FEATURE>_ENABLED 0`, пересобрать, проверить размер в выводе сборки. Для первого опыта проще Custom Firmware Builder на сайте.

### Шаг 1. Упражнение без железа: перенос `diff all` в другую сборку
Ситуация. На F405 стояла облачная сборка 4.5.3 с GPS, LED-лентой, DShot и аналоговым OSD. GPS сняли, ленту и сервы тоже, и собрали новую прошивку без `GPS`, `LED_STRIP` и `SERVOS`. В новую сборку вставляют старый `diff all`; в нём, среди прочего, такие строки: `feature GPS`, `feature LED_STRIP`, `led 0 0,0::C:0`, `set serialrx_provider = CRSF`, `set motor_pwm_protocol = DSHOT600`, `set dshot_bidir = ON`, `set gps_provider = UBLOX`, `set gps_rescue_min_sats = 7`, `set ledstrip_profile = STATUS`, `set osd_vbat_pos = 2401`, в конце `save`.

Предскажи для каждой строки: примется, `unavailable`, `INVALID NAME` или `UNKNOWN COMMAND`, — и сохранится ли конфиг. Потом сверь с лабораторной: `bf-custom.lab.py` повторяет логику `cliGet`/`cliSet`/`cliFeature`/batch из `cli.c` 4.5.3. Вывод скрипта для новой сборки:

- `feature GPS` → `unavailable` (без ошибки), `feature LED_STRIP` → `Enabled LED_STRIP` (молча, хотя кода ленты нет);
- `led …` → `###ERROR IN input: UNKNOWN COMMAND, TRY 'HELP'###`;
- `gps_provider`, `gps_rescue_min_sats`, `ledstrip_profile` → `###ERROR IN set: INVALID NAME: …###`;
- `serialrx_provider`, `motor_pwm_protocol`, `dshot_bidir`, `osd_vbat_pos` → `… set to …`;
- итог: ошибок 6 (четыре в строках и две в ответе `save`), сохранено: `False`; после второго ручного `save` — `True`.

### Шаг 2. Бюджет флеша
Та же лабораторная считает место под основной код (регион `FLASH1`): F411 — 480 КБ, F405 — 992 КБ. Прошивка 450 КБ на F411 занимает 93.8 % `FLASH1`, свободно 30 КБ: проходит по ориентиру курса (запас ≥ 5 %, 24 КБ). 470 КБ — 97.9 %, свободно 10 КБ: собирается, но ориентир не выполнен. 490 КБ не влезает: компоновщик сообщит о переполнении `FLASH1` на 10 КБ. Убирать начинай с того, чего нет на борту: второй тип OSD, лишние протоколы приёмника и телеметрии.

### Шаг 3. Лабораторная на железе
Собери две прошивки ArduPlane для своей платы: стандартную и без одной подсистемы. Сравни размер бинарников, прошей вторую в SITL-подобный стенд (плата на столе) и убедись, что отключённая подсистема действительно исчезла из параметров. Для Betaflight то же самое: две облачные сборки, отличающиеся одной опцией (например, `GPS`). Пропеллеры сняты на всех шагах — проверяется только CLI и вкладки.

### Что должно получиться и что записать
- **Betaflight.** После прошивки урезанной сборки `version` и `status` сохранены в файл рядом с конфигом (BUILD KEY позволяет пересобрать ровно ту же прошивку). Конфиг восстановлен из `diff all` той же версии, все строки `###ERROR` объяснены, ключевые параметры перечитаны через `get`. Настройки отключённых опций в CLI отсутствуют: после сборки без GPS `get gps_provider` отвечает `INVALID NAME`, `help gps` — `NO MATCHES FOR 'gps'`, вкладки GPS в Configurator нет.
- **ArduPilot.** Вывод сборки показывает размер прошивки и свободную flash. Запиши оба числа для двух сборок: разница — цена отключённой подсистемы в байтах. После прошивки параметры подсистемы (её префикс) исчезают из полного списка параметров в наземке — сделай скриншот поиска по префиксу до и после.
- **Git.** Файл с опциями сборки (`hwdef` с `define AP_<FEATURE>_ENABLED 0` или список опций Cloud Build / `OPTIONS` локальной сборки) лежит в репозитории рядом с конфигом. Через полгода на вопрос «почему на этом дроне нет X» ответит коммит, а не память.

Самопроверка: лабораторная выполнена, когда (без железа) для всех десяти строк шага 1 предсказан тот же исход, что в выводе лабораторной, и ответ «сохранено: нет, после второго `save` — да» совпал; в шаге 2 посчитано 93.8 % ± 0.1 % и 30 КБ свободно для 450 КБ на F411 (97.9 % и 10 КБ для 470 КБ); (на железе) собраны стандартная и урезанная прошивки, размеры сравнены, вывод `version`/`status` с BUILD KEY сохранён, исчезновение отключённой подсистемы подтверждено выводом CLI (`INVALID NAME`) или скриншотом, а конфигурация сборки лежит в git.

**Эталон для самопроверки.** Правильный результат шага 1: принимаются `serialrx_provider`, `motor_pwm_protocol`, `dshot_bidir`, `osd_vbat_pos` и обе строки `feature` (GPS — с ответом `unavailable`); ошибки дают `led` и три `set` для GPS и ленты; `save` отказывается сохранять. Типичные ошибки: «`feature LED_STRIP` даст ошибку» — нет, `cliFeature` 4.5.3 проверяет только GPS и RANGEFINDER, остальное включает молча (в 2025.12 печатает `Unavailable LED_STRIP`, но тоже без ошибки batch), поэтому `feature list` не говорит о составе сборки; «принятые строки потеряны» — нет, они применены в памяти, второй `save` их запишет; «конфиг сохранится без строк с ошибками» — нет, batch с ошибкой блокирует `save` целиком. На железе: размеры двух сборок совпали — флаг в сборку не попал (`define AP_<FEATURE>_ENABLED 0` не в том `hwdef`, опция не отмечена в Cloud Build): сверь `/api/builds/<ключ>/json` или вывод сборки. Параметры подсистемы остались — на плате прошита старая сборка: сверь `version` и BUILD KEY с записью.

## diagnostics
- **Симптом:** Cloud Build падает с ошибкой размера
  - Возможная причина: слишком много опций для флеша платы (F411/F722 — 480 КБ в `FLASH1`).
  - Что сделать: открыть `Show Log.`, найти сообщение о переполнении `FLASH1`; убрать неиспользуемое (второй OSD, лишние протоколы, GPS без GPS).
- **Симптом:** `build request error (please check build configuration, e.g. custom defines)`
  - Возможная причина: сервер отклонил сам запрос; чаще всего виноваты Custom Defines.
  - Что сделать: одно имя через одиночный пробел, без `USE_`, без запятых; сверить имя с исходниками нужной версии. Неизвестное имя обычно не ломает сборку, а просто не даёт функции.
- **Симптом:** после своей сборки функция «есть», но не работает
  - Возможная причина: опции нужен пин, не назначенный через `resource`; или `feature` включён, а кода в сборке нет (LED_STRIP).
  - Что сделать: `get` по имени параметров функции и `help` по имени команды; если `INVALID NAME` — пересобрать с опцией; иначе `resource`, перезагрузка, `status`.
- **Симптом:** после вставки `diff all` настройки не сохранились, в выводе `ERRORS WERE DETECTED`
  - Возможная причина: в пакете есть строки для опций, которых нет в новой сборке; batch с ошибкой блокирует `save`.
  - Что сделать: прочитать все `###ERROR`, убедиться, что это только сознательно убранные опции, набрать `save` вручную.
- **Симптом:** аналоговый OSD пропал после пересборки
  - Возможная причина: собрано только `OSD_HD` — драйвер MAX7456 вырезан.
  - Что сделать: добавить `OSD_SD` (или оба).
- **Симптом:** моторы не отвечают на DShot, `get dshot_bidir` → `INVALID NAME`
  - Возможная причина: облачная сборка без `DSHOT` в Motor Protocol; `motor_pwm_protocol = DSHOT600` при этом принимается, но кода DShot нет. То же с приёмником: `serialrx_provider = CRSF` принимается и без `SERIALRX_CRSF` в сборке.
  - Что сделать: пересобрать с `DSHOT`; после прошивки `get dshot_bidir` должен отвечать значением.
- **Симптом:** в Configurator нет вкладки GPS / OSD / LED Strip / Servos
  - Возможная причина: опции нет в сборке — Configurator прячет вкладку по списку опций.
  - Что сделать: Setup → Firmware info → `Options`; пересобрать.
- **Симптом:** ArduPilot `waf configure` не находит плату
  - Возможная причина: опечатка в имени, нет сабмодулей.
  - Что сделать: `./waf list_boards`, `git submodule update --init --recursive`.
- **Симптом:** после своей сборки часть параметров исчезла
  - Возможная причина: это и есть эффект отключённой подсистемы.
  - Что сделать: сверить с записью о сборке; если параметр нужен — вернуть функцию.

## references
- Betaflight 4.5.3 — src/main/cli/cli.c (status, version, get, help, batch) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/cli/cli.c | primary | A
- Betaflight 4.5.3 — src/main/target/common_pre.h (CLOUD_BUILD, CORE_BUILD, зависимости опций) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/target/common_pre.h | primary | A
- Betaflight 4.5.3 — src/main/msp/msp_build_info.h (список опций Cloud Build 4.5) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/msp/msp_build_info.h | primary | A
- Betaflight 4.5.3 — Makefile и mk/config.mk (OPTIONS, EXTRA_FLAGS, CONFIG) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/Makefile | primary | A
- Betaflight Configurator 10.10.0 — firmware_flasher.js (запрос сборки, Custom Defines, Core Only) | https://raw.githubusercontent.com/betaflight/betaflight-configurator/10.10.0/src/js/tabs/firmware_flasher.js | primary | A
- Build Options — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/Build-Options | primary | A
- Defines — Betaflight Development | https://betaflight.com/docs/development/Defines | primary | A
- Building the code — ArduPilot Dev | https://ardupilot.org/dev/docs/building-the-code.html | primary | A
- Setting up SITL / build environment — ArduPilot Dev | https://ardupilot.org/dev/docs/SITL-setup-landingpage.html | primary | A

## checklist
- Знаю, какие опции реально нужны моему аппарату, и что DShot в облачной сборке надо отметить явно
- Сборка описана в git: опции / `OPTIONS` / hwdef-патч, дата, хеш
- Вывод `version` и `status` (BUILD KEY) сохранён после прошивки
- Конфиг восстанавливается из той же версии; все `###ERROR` прочитаны и объяснены
- Проверяю состав сборки через `get` и `help`, а не через `feature list`
- Понимаю, что теряю, отключая подсистему
