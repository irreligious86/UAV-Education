---
id: bf-intro
title: "Введение в Betaflight"
level: L1
readingTime: 25 мин
firmware: Betaflight 2025.12 (сверено с 2025.12.5)
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
  - title: "Betaflight 2025.12 Release Notes"
    url: "https://betaflight.com/docs/wiki/release/Betaflight-2025-12-Release-Notes"
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

**Поддержка:** полётные контроллеры на **STM32** (F4, F7, H7, G4) **AT32F435**, **APM32** и **RP2350** (последние два — с 2025.12; в 4.5 их нет). **Возможности прошивки:**

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

**PID-цикл:** параметр `pid_process_denom` задаёт частоту контура PID. Пример: gyro **8 кГц**, `pid_process_denom = 1` (дефолт) → PID **8 кГц**; `= 2` → **4 кГц**. На F4/G4 с bidirectional DShot и gyro выше 4 кГц прошивка сама поднимает denom минимум до 2 и меняет DSHOT600 на DSHOT300.

### Версии прошивки и совместимость

Курс ведётся по **Betaflight 2025.12** (сверено с 2025.12.5). С этой ветки номер версии календарный: год.месяц.патч. Предыдущая значимая ветка — **4.5** (в курсе отсчёт переименований идёт от 4.5.3; последний выпуск 4.5.5, ветка `4.5-maintenance` несёт номер 4.5.6, из неё собран SITL в модуле «Betaflight с нуля»). Теги 2026.6 существуют, но целевой версией курса не являются. Что добавила 2025.12 к 4.5:

- удержание высоты и позиции (режимы ALTHOLD и POS HOLD), общий автопилот `ap_*` для них и GPS Rescue;
- дизарм по удару при посадке (`landing_disarm_threshold`), новый turtle (`crashflip_rate`);
- для крыла: S-term, TPA по скорости, кривые TPA;
- генератор чирпа для идентификации (режим CHIRP);
- новые гироскопы (IIM-42653, ICM-456xx), платформы APM32 и RP2350.

Ветка 4.5 в своё время принесла GPS M10 и переработанный GPS Rescue, *Earth referencing* для Angle / Horizon, шрифты для HD VTX и RPM-фильтр с весами гармоник — всё это в 2025.12 сохранено.

**Важно:** при переходе **4.5 → 2025.12** (как и раньше 4.4 → 4.5) нужен **Full Chip Erase** и настройка по разделам. Старые **CLI-дампы** построчно **несовместимы** из‑за переименований, диапазонов и сменившегося смысла параметров — см. таблицу в конце теории.

### Экосистема Betaflight

Помимо прошивки — конфигуратор. С **2025.12** это **Betaflight App**: веб-приложение и PWA (`https://app.betaflight.com`), работает через **WebUSB / WebSerial**, номер версии совпадает с прошивкой (до 2025.12 — Betaflight Configurator 10.10, отдельная программа с собственной нумерацией; веб-версия была доступна уже для 4.5). Для Android есть нативное приложение. В курсе слово «конфигуратор» означает Betaflight App, названия вкладок те же.

### Target, unified target и Cloud Build
Прошивка собирается под **target** — описание платы: процессор, какие ноги на что заведены (`resource`), какой гироскоп на каком SPI. С 4.3 почти все платы — **unified targets**: один бинарник на семейство процессора (например, `STM32F405`) плюс текстовый конфиг платы (`board_name`, `manufacturer_id`, набор `resource`/`set`), который конфигуратор подгружает при прошивке. Cloud Build (4.4+) собирает бинарник на сервере с выбранным набором функций: протокол приёмника, OSD (аналоговый `USE_OSD_SD` и/или HD `USE_OSD_HD`), GPS, магнитометр, телеметрия, LED, сервы или пакет WING, удержание высоты и позиции — чего не отметил, того в прошивке нет (типичные причины «приёмник молчит» и «после 2025.12 пропал OSD»). `version` в CLI показывает версию, target, дату и git-ревизию сборки; `BUILD KEY` (ключ сборки для воспроизведения) печатает `status`, а список опций отдаёт build.betaflight.com по этому ключу.

### Что делает планировщик каждые 125 мкс
`fc/tasks.c` описывает задачи с периодом и приоритетом; `scheduler/scheduler.c` выбирает их. Критичные: `GYRO` (чтение, фильтры) и `PID` (`taskMainPidLoop`: RC-команда → PID → миксер → DShot) — на частоте гироскопа / `pid_process_denom`. Остальные — по остаточному принципу: `RX` (приём и обработка кадров, событийно), `SERIAL`, `BATTERY_*`, `GPS`, `OSD` (по `osd_framerate_hz`), `BLACKBOX`, `TELEMETRY`, `LED_STRIP`. CLI `tasks` показывает фактический период, среднее и максимальное время каждой задачи и загрузку CPU; `status` — частоту гироскопа, загрузку и флаги арма. Перегрузка (> 85–90% на F4 с 8 кГц) — пропуски задач, джиттер, флаг `LOAD`: лечится `pid_process_denom = 2` или отключением функций.

### Карта настройки: где что живёт
| Что | Где в конфигураторе | Ключевые параметры CLI |
|---|---|---|
| Порты и устройства | Ports | `serial`, `resource`, `serialrx_provider` |
| Приёмник, каналы | Receiver | `map`, `serialrx_provider`, `rxrange`, `rc_smoothing_*` |
| Рейты, экспо, кривая газа | PID Tuning → Rateprofile Settings | `rates_type`, `roll_rc_rate`, `roll_srate`, `roll_expo`, `thr_mid`, `thr_expo`, `rateprofile` (bf-rates-rc) |
| Режимы на тумблерах | Modes | `aux` |
| Подстройки в полёте | Adjustments | `adjrange` (bf-adjustments) |
| Видеопередатчик | Video Transmitter | `vtxtable`, `vtx_band`, `vtx_channel`, `vtx_power`, `vtx` — VTX на тумблере (link-vtx, bf-adjustments) |
| LED-лента | LED Strip | `led`, `color`, `mode_color`, `ledstrip_*` (bf-led-buzzer) |
| Готовые наборы настроек | Presets | своих параметров нет: пресет — это блок CLI-команд из репозитория сообщества; применять поверх умолчаний, `diff all` до и после |
| Моторы, ESC, протокол | Motors | `motor_pwm_protocol`, `dshot_bidir`, `motor_poles`, `motor_idle` (до 2025.12 — `dshot_idle_value`) |
| PID, фильтры, FF | PID Tuning | `set p_roll`… `simplified_*`, `gyro_lpf*`, `rpm_filter_*` |
| OSD | OSD | `osd_*_pos`, `osd_warn_bitmask` |
| Blackbox | Blackbox | `blackbox_device`, `blackbox_sample_rate`, `debug_mode` |
| Failsafe | Failsafe | `failsafe_procedure`, `failsafe_delay`, `rxfail` |
| Прошивка | Firmware Flasher | — |
Профили: до 4 PID-профилей (`profile`) и 4 профилей рейтов (`rateprofile`) — один «спокойный», один «гоночный». Тумблером/adjustment в полёте переключается только рейт-профиль; PID-профиль — на земле при снятом арме (стиками, OSD-меню, `profile N`).

### Разобранный пример: порядок первой настройки
Прошивка (Cloud Build: CRSF, OSD HD, GPS если есть) → `resource`/target по умолчанию → Ports (UART приёмника) → Receiver (CRSF, проверка каналов и `map` AETR) → Motors (DShot600, `motor_poles`, `dshot_bidir`, направление без пропов) → Modes (ARM, ANGLE, BEEPER, FAILSAFE) → Failsafe (DROP для первого полёта) → OSD (напряжение, LQ, таймер, предупреждения) → Blackbox (2 кГц) → `diff all` в репозиторий (модуль «CI»). Первый полёт — на умолчаниях PID: Betaflight «из коробки» летает на 5" лучше, чем большинство ручных тюнов новичка; тюнинг — после логов.

{{diagram:bf-setup-map|Порядок первой настройки: резервная копия → Ports → Receiver → Modes → Motors (без пропеллеров) → OSD → PID и фильтры по логу.}}

### Переход 4.5.3 → 2025.12: что переименовано и изменилось
Этот раздел — чек-лист перехода и единая таблица курса: остальные модули ссылаются сюда. Таблица получена сравнением `cli/settings.c`, `cli/cli.c`, `fc/runtime_config.c`, `io/beeper.c`, `msp/msp_box.c`, `osd/osd.h` и умолчаний PG на тегах 4.5.3 и 2025.12.5. Между 4.5.3 и 4.5.5 таблица настроек не менялась; единственное заметное отличие внутри 4.5.x — аргумент `noreboot` (с 4.5.4).

Порядок обновления и ловушки:

1. На старой прошивке сохрани в файл `diff all` и `dump all`, запиши вывод `version` и `status` (имя платы, BUILD KEY), сними скриншоты вкладок Modes, OSD, Failsafe. Скачай логи Blackbox: Full chip erase их сотрёт.
2. Проверь, что плата есть в списке target для 2025.12 во Firmware Flasher. Плату без поддержки оставляй на 4.5.x: «чужой» target даёт неверные `resource` (типичная жалоба — газ доходит до 30 %).
3. Работай в **Betaflight App** (`https://app.betaflight.com`) той же версии, что и прошивка: с 2025.12 номер приложения совпадает с номером прошивки. Configurator 10.10 рассчитан на 4.5.
4. В Cloud Build отметь всё, чем пользуешься: протокол приёмника, OSD (аналоговый и/или HD), GPS, магнитометр, LED Strip, SERVOS или пакет WING, удержание высоты и позиции. Нет OSD после прошивки — не та опция OSD в сборке.
5. Прошивай с **Full chip erase**. Старый `diff all` целиком не вставляй: строки с удалёнными именами дают `INVALID NAME`, а строки, чьё имя сохранилось при другом смысле (`d_roll`, `iterm_windup`, `osd_warn_bitmask`, `beeper`), молча дают другой результат. Переноси по разделам, сверяясь с таблицей.
6. Не переносятся вообще: D-составляющая PID (смысл `d_*` перевёрнут), числовые маски `osd_warn_bitmask` и пищалки (поле `beeper_off_flags` в MSP), номера битов флагов арма, `failsafe_off_delay` (другие единицы), газ GPS Rescue (`gps_rescue_throttle_*`), выравнивание гироскопа `gyro_1_sensor_align`.
7. После настройки: `status` без лишних флагов арма, тест моторов без пропов, проверка failsafe на столе, первый полёт на умолчаниях PID 2025.12.
8. Плата со встроенным SPI-приёмником ELRS под 2025.12 остаётся на ELRS 3 (`ELRS_OTA_VERSION_ID 3` в исходнике 2025.12.5): с передатчиком на ELRS 4 она не свяжется. Поддержка ELRS 4 для SPI-приёмников появляется только в 2026.6; до этого — передатчик на 3.x для этой модели или отдельный приёмник на UART.

| Старое (4.5.3) | Новое (2025.12) | Что изменилось | С какого выпуска |
|---|---|---|---|
| `d_min_roll`, `d_min_pitch`, `d_min_yaw` (база 30 / 34 / 0) | `d_roll`, `d_pitch`, `d_yaw` (база 30 / 34 / 0) | в 2025.12 `d_*` — базовый D; `d_min_*` удалены | 2025.12 |
| `d_roll`, `d_pitch`, `d_yaw` (пик 40 / 46 / 0) | `d_max_roll`, `d_max_pitch`, `d_max_yaw` (пик 40 / 46 / 0) | пиковый D получил своё имя; `d_max_gain` 37 и `d_max_advance` 20 без изменений | 2025.12 |
| `simplified_dmax_gain` | `simplified_d_max_gain` | только имя | 2025.12 |
| `iterm_limit` (400) | — | удалён; потолок I теперь задаёт `iterm_windup` | 2025.12 |
| `iterm_windup` 85, 30–100 | `iterm_windup` 80, 20–100 | другой смысл: было «порог насыщения моторов, выше которого I ослабляется», стало «потолок I в % от `pidsum_limit`» | 2025.12 |
| `dshot_idle_value` (550) | `motor_idle` (550) | имя; единицы те же (×0.01 %), 0–2000 | 2025.12 |
| `min_throttle` (1070) | — | удалён; для коллекторных моторов умолчание `motor_idle` = 700 | 2025.12 |
| `dyn_idle_start_increase` (50) | — | удалён; предел прибавки до airmode берётся из `motor_idle` | 2025.12 |
| `feedforward_averaging` OFF, `feedforward_smooth_factor` 25 | 2_POINT и 65 | новые умолчания; добавлены `feedforward_yaw_hold_gain` (15) и `feedforward_yaw_hold_time` (100) | 2025.12 |
| `rc_smoothing_feedforward_cutoff` | — | удалён; срез FF считается вместе с setpoint | 2025.12 |
| `tpa_mode` PD / D | PD / D; в сборке WING — ещё PDS | на коптере набор значений не менялся; PDS, `tpa_curve_*`, `tpa_speed_*` и отрицательные значения `tpa_low_rate` есть только в сборке WING (на коптере `tpa_low_rate` по-прежнему 0–100, умолчание 20) | 2025.12 |
| `angle_limit` 10–85 | `angle_limit` 10–80 | умолчание 60 не менялось; в сборке WING добавлен `angle_pitch_offset` | 2025.12 |
| `dyn_notch_count` 0–5 | `dyn_notch_count` 0–7 | диапазон | 2025.12 |
| `debug_mode = GYRO_SCALED` | поле лога `gyroUnfilt` | режим удалён; `DUAL_GYRO_*` → `MULTI_GYRO_*`, `D_MIN` → `D_MAX`, `GPS_RESCUE_THROTTLE_PID` → `AUTOPILOT_ALTITUDE`; добавлены TPA, S_TERM, SPA, TASK, GIMBAL, WING_SETPOINT, AUTOPILOT_POSITION, CHIRP, OPTICALFLOW, FLASH_TEST_PRBS, MAVLINK_TELEMETRY | 2025.12 |
| `failsafe_off_delay` (10 = 1 с; 0–200, десятые секунды) | `failsafe_landing_time` (60 с; 0–250, секунды) | имя, единицы и умолчание; значение пересчитывать: старое ÷ 10 | 2025.12 |
| `gps_rescue_throttle_hover` / `_min` / `_max` (1275 / 1100 / 1700) | `ap_hover_throttle` (1275; 1100–1700), `ap_throttle_min` (1100; 1050–1400), `ap_throttle_max` (1700; 1400–2000) | общие переменные автопилота: их используют GPS Rescue, ALTHOLD и POS HOLD | 2025.12 |
| `gps_rescue_throttle_p` / `_i` / `_d` (15 / 15 / 20) | `ap_altitude_p` / `_i` / `_d` / `_f` (15 / 15 / 15 / 15) | контур высоты общий; диапазон 0–200 | 2025.12 |
| `gps_rescue_landing_alt` (4 м; 1–15) | `ap_landing_altitude_m` (4 м; 0–200) | имя и диапазон | 2025.12 |
| `gps_rescue_disarm_threshold` 20 | 30 | умолчание | 2025.12 |
| `gps_rescue_velocity_p/i/d`, `gps_rescue_yaw_p` 0–255 | 0–200 | диапазон; в 2026.6 эти переменные удалены | 2025.12 |
| `gps_provider` NMEA / UBLOX / MSP | + VIRTUAL | GPS в SITL; автопоиск скорости знает 230400 | 2025.12 |
| `mag_declination` 0–3599 | −300…300 | по-прежнему десятые доли градуса; западное склонение пишется отрицательным | 2025.12 |
| — | `alt_hold_climb_rate` (50), `alt_hold_deadband` (20), `pos_hold_deadband` (5), `pos_hold_without_mag` (OFF), `ap_position_*`, `ap_max_angle` (50) | новые режимы ALTHOLD (id 3) и POS HOLD (id 11) | 2025.12 |
| — | `landing_disarm_threshold` (0 = выкл; 0–250) | дизарм по удару при посадке | 2025.12 |
| — | `prearm_allow_rearm` (OFF) | переарм без переключения PREARM | 2025.12 |
| флаг арма `ARMSWITCH`, бит 25 (всего 26) | `ARM_SWITCH`, бит 28 (всего 29) | на битах 25–27 новые `FLIP_SWITCH`, `ALT_HOLD_SW`, `POS_HOLD_SW`; hex-маску расшифровывать таблицей своей версии | 2025.12 |
| `beeper` … `CRASH_FLIP`, `RC_SMOOTHING_INIT_FAIL` | `CRASHFLIP`; `RC_SMOOTHING_INIT_FAIL` удалён | номер `ALL` 24 → 23; числовая маска пищалки (MSP) сдвинута — переносить именами | 2025.12 |
| предупреждение OSD `RC_SMOOTHING` (бит 8 `osd_warn_bitmask`) | — | удалено; биты 9–18 сдвинулись на один вниз, на бите 18 новое `POSHOLD_FAILED` | 2025.12 |
| `crashflip_expo` (35; 0–100) | `crashflip_rate` (0; 0–250), `crashflip_auto_rearm` (OFF) | другой алгоритм turtle; звук и предупреждение `CRASH_FLIP` → `CRASHFLIP` | 2025.12 |
| `launch_control_mode` NORMAL | PITCHONLY | умолчание | 2025.12 |
| adjustments 0–30 | + 31 `LED_DIMMER` | функция `SIMPLIFIED_MASTER_MULTIPLIER` из документации в 2025.12 отсутствует | 2025.12 |
| режим id 29 «3D DISABLE / SWITCH» | «3D DISABLE» | добавлены id 3 ALTHOLD, 11 POS HOLD, 55 CHIRP; остальные permanentId те же | 2025.12 |
| `serial 2 64 …` (номер порта) | `serial UART3 64 …` (имя порта) | `diff` пишет имена; старые номера принимаются (0 = UART1) | 2025.12 |
| `save`, `exit` — всегда с перезагрузкой | `save noreboot`, `exit noreboot` | необязательный аргумент | 4.5.4 |
| `flash_read <length> <address>` | `flash_read <address> <length>` | порядок аргументов | 2025.12 |
| `gyro_to_use` FIRST / SECOND / BOTH | `gyro_enabled_bitmask`, `gyro_1_enabled` … `gyro_8_enabled` | до 8 гироскопов; `gyro_1_sensor_align`, `gyro_1_align_*`, `gyro_2_*` удалены — после обновления проверь, что стрелка на плате смотрит вперёд, а `align_board_*` верны | 2025.12 |
| `dshot_edt` OFF / ON | OFF / ON / FORCE | новое значение | 2025.12 |
| `expresslrs_rate_index`, `expresslrs_switch_mode` | — | удалены (SPI-приёмник ELRS) | 2025.12 |
| `serialrx_provider` … SPEK1024 | + MAVLINK | новый протокол приёмника | 2025.12 |
| `blackbox_device` NONE / SPIFLASH / SDCARD / SERIAL | + VIRTUAL | добавлены `blackbox_disable_attitude`, `blackbox_disable_servos` | 2025.12 |
| порт: функции до 131072 | + GIMBAL = 262144 | последовательный подвес `gimbal_*` | 2025.12 |
| компас IST8310, адрес I2C 0x0C | 0x0E | компас «пропал» после обновления — `set mag_i2c_address = 12` | 2025.12 |
| Betaflight Configurator 10.10 | Betaflight App 2025.12 | веб-приложение и PWA; версия совпадает с прошивкой | 2025.12 |

Не затронуто и переносится как есть: `aux`, `adjrange` (номера функций 0–30), `rxrange`, `map`, `vtxtable`, `led`, `color`, `mode_color`, рейты (`rates_type`, `*_rc_rate`, `*_srate`, `*_expo`), фильтры (`gyro_lpf*`, `dterm_lpf*`, `rpm_filter_*`, `dyn_notch_*` кроме верхней границы числа notch), `failsafe_delay`, `failsafe_procedure`, `failsafe_throttle`, `vbat_*`, `ibata_*`. Отличия 2026.6 в курсе не разбираются, кроме трёх, о которые спотыкаются: ELRS 4 для SPI-приёмников, удаление `gps_rescue_velocity_*` и исправленный диапазон гироскопа IIM-42652 (по примечаниям к выпуску 2026.6 после обновления PID фактически удваиваются).

{{diagram:bf-migrate-line-tree|Строку старого diff all переносят только если имя, смысл и единицы те же; опасны строки с прежним именем и новым смыслом — они принимаются молча.}}

### Место в системе

- **Получает:** target платы и набор опций Cloud Build (`bf-custom`); гироскоп на частоте до 8 кГц; кадры приёмника в задаче RX (`bf-ports`, `link-protocols`).
- **Отдаёт:** порядок первой настройки и карту «где что живёт» — остальным модулям; частоту PID-цикла, на которой работают фильтры и регулятор (`bf-filters`, `bf-pid-reg-in-bf`); единую таблицу переименований 4.5 → 2025.12 (`bf-cli-automation`).
- **Если ошибиться здесь:** старый `diff all` вставлен целиком после обновления → строки с сохранившимся именем (`d_roll`, `iterm_windup`, `beeper`) молча получают другой смысл; проявляется как изменившийся тюн (`bf-pid-reg-in-bf`) и другие сигналы пищалки (`bf-led-buzzer`). Перегрузка CPU на F4 при 8 кГц → пропуски задач и флаг `LOAD`, арм запрещён (`bf-arming-safety`).

## practice

### Установка Betaflight App (конфигуратора)

**Вариант А — веб (рекомендуется для ПК):**

1. Браузер на базе **Chromium** (Chrome, Edge, Opera).
2. Открыть `https://app.betaflight.com`.
3. При первом подключении FC разрешить доступ к **USB**.

**Вариант Б — офлайн или прошивка 4.5:**

- установить Betaflight App как PWA из того же адреса (кнопка установки в адресной строке браузера); приложение обновляется из сети;
- для плат, оставшихся на 4.5.x, — Configurator 10.10 с GitHub Releases: `https://github.com/betaflight/betaflight-configurator/releases` (Windows / macOS / Linux).

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
2. Версия — последняя из ветки **2025.12.x** (курс сверен с 2025.12.5); в Cloud Build отметить протокол приёмника, тип OSD, GPS и остальные нужные опции.
3. Включить **Full chip erase** при смене ветки (4.5 → 2025.12 — обязательно).
4. **Load Firmware [Online]** → **Flash Firmware**; не отключать USB до конца.
5. После перезагрузки — настроить заново или перенести конфиг из бэкапа по разделам; бэкап от 4.5 целиком не вставлять (раздел «Переход 4.5.3 → 2025.12» в теории).

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

### Упражнение без железа: перенос `diff` с 4.5.3 на 2025.12
Плата не нужна — только таблица «Переход 4.5.3 → 2025.12» из теории. Ниже 13 строк из бэкапа аппарата на 4.5.3 (учебный пример, собран вручную). Для каждой строки запишите одно из четырёх решений и, где нужно, новую строку для 2025.12: **как есть**; **переименовать**; **пересчитать**; **не переносить** (с причиной). Затем посчитайте, сколько строк при вставке блока целиком дали бы `INVALID NAME` и сколько молча получили бы другой смысл.

| № | Строка из `diff all` на 4.5.3 |
|---|---|
| 1 | `set d_roll = 44` |
| 2 | `set d_min_roll = 33` |
| 3 | `set iterm_windup = 70` |
| 4 | `set iterm_limit = 350` |
| 5 | `set dshot_idle_value = 600` |
| 6 | `set failsafe_off_delay = 50` |
| 7 | `set gps_rescue_throttle_hover = 1300` |
| 8 | `set simplified_dmax_gain = 120` |
| 9 | `set osd_warn_bitmask = 8191` |
| 10 | `aux 0 0 0 1700 2100 0` |
| 11 | `serial 2 64 115200 57600 0 115200` |
| 12 | `set failsafe_delay = 10` |
| 13 | `set min_throttle = 1050` |

И два вопроса по разделу «Архитектура прошивки»: (а) гироскоп 8 кГц, `pid_process_denom = 2` — какова частота PID и период цикла в микросекундах? (б) плата F405, `dshot_bidir = ON`, гироскоп 8 кГц, в конфиге `pid_process_denom = 1` и DSHOT600 — что на самом деле выставит прошивка?

Самопроверка: лабораторная выполнена, когда:
- решения по строкам совпали с таблицей эталона ниже — все 13;
- `INVALID NAME` дали бы 7 строк (2, 4, 5, 6, 7, 8, 13), молча сменили бы смысл 3 строки (1, 3, 9), без изменений переносятся 3 строки (10, 11, 12);
- (а) 4 кГц и 250 мкс; (б) denom не меньше 2, то есть PID 4 кГц, и DSHOT300;
- на железе (если оно есть): после переноса по разделам `status` не показывает лишних флагов арма, а `diff all` на 2025.12 не содержит ни одного имени из левого столбца таблицы переименований.

**Эталон для самопроверки.**

| № | Решение | Строка для 2025.12 |
|---|---|---|
| 1 | переименовать: в 4.5 это пиковый D | `set d_max_roll = 44` |
| 2 | переименовать: в 4.5 это базовый D | `set d_roll = 33` |
| 3 | не переносить: имя то же, смысл другой (стал потолком I в % от `pidsum_limit`) | оставить умолчание 80 |
| 4 | не переносить: параметр удалён | — |
| 5 | переименовать, единицы те же | `set motor_idle = 600` |
| 6 | пересчитать: десятые доли секунды → секунды, 50 ÷ 10 | `set failsafe_landing_time = 5` |
| 7 | переименовать | `set ap_hover_throttle = 1300` |
| 8 | переименовать | `set simplified_d_max_gain = 120` |
| 9 | не переносить числом: биты сдвинулись | отметить предупреждения заново во вкладке OSD |
| 10 | как есть | `aux 0 0 0 1700 2100 0` |
| 11 | как есть: номер порта принимается, `diff` запишет его именем | `serial UART3 64 115200 57600 0 115200` |
| 12 | как есть | `set failsafe_delay = 10` |
| 13 | не переносить: параметр удалён | — |

Частые неверные ответы: строка 1 оставлена как есть — тогда базовый D станет 44 вместо 33, и это главная ловушка перехода; строка 6 перенесена числом 50 — посадка по failsafe длилась бы 50 с вместо 5; строка 3 отнесена к `INVALID NAME` — имя `iterm_windup` существует, поэтому CLI примет её молча; строка 11 записана как `serial UART2 …` — номера портов считаются с нуля, 2 — это UART3.

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
  - Возможная причина: холостой ход моторов слишком низкий для старта.
  - Что проверить/сделать: переменной `min_throttle` в 2025.12 нет (в 4.5 она была, но с DShot не использовалась): на вкладке Motors поднять Motor Idle (`motor_idle`, до 2025.12 — `dshot_idle_value`; дефолт 5.5%).
- **Симптом:** после прошивки приёмник/GPS не работают, хотя проводка верна
  - Возможная причина: функция не включена в Cloud Build.
  - Что сделать: `status` → BUILD KEY, по нему на build.betaflight.com — список опций сборки (`version` печатает только версию, target, дату и git-ревизию); перепрошить с нужными.
- **Симптом:** `LOAD` в флагах арма или CPU > 90%
  - Возможная причина: F4 на 8 кГц со всеми функциями.
  - Что сделать: `pid_process_denom = 2`, отключить LED/лишние телеметрии, `tasks` для поиска тяжёлых.

## references
- Getting Started — Betaflight Documentation | https://betaflight.com/docs/wiki/getting-started | primary | A
- Betaflight 2025.12 Release Notes | https://betaflight.com/docs/wiki/release/Betaflight-2025-12-Release-Notes | primary | A
- Betaflight 4.5 Release Notes | https://www.betaflight.com/docs/wiki/release/Betaflight-4-5-Release-Notes | primary | A
- Betaflight cli/settings.c, тег 2025.12.5 (таблица настроек) | https://github.com/betaflight/betaflight/blob/2025.12.5/src/main/cli/settings.c | primary | A
- Betaflight cli/settings.c, тег 4.5.3 | https://github.com/betaflight/betaflight/blob/4.5.3/src/main/cli/settings.c | primary | A
- Betaflight Configurator — Official Web App | https://app.betaflight.com | primary | A
- Betaflight CLI Documentation — Command Reference | https://betaflight.com/docs/wiki/guides/current/Cli | primary | A
- Betaflight Configurator — GitHub Releases | https://github.com/betaflight/betaflight-configurator/releases | primary | A
- Betaflight FAQ — How to Start | https://www.betaflight.com/docs/wiki/guides/current/FAQ | primary | A
- Betaflight Advanced Guide — iFlight | https://help.iflight-rc.eu/en-US/betaflight-advanced-guide-951396 | secondary | B
- GPS Rescue 4.5 — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/GPS-Rescue-v4-5 | primary | A
- Betaflight — Arming sequence and safety (arming flags) | https://www.betaflight.com/docs/wiki/guides/current/Arming-Sequence-And-Safety | secondary | B
- Joshua Bardwell — Betaflight Setup Tutorial | https://www.youtube.com/watch?v=xSzO6HP6yzs | secondary | B

