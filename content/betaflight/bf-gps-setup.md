---
id: bf-gps-setup
title: "GPS в Betaflight: модули M8/M10, конфигурация, точность и домашняя точка"
level: L2
readingTime: 50 мин
firmware: Betaflight 2025.12 (сверено с 2025.12.5); разбор автоконфигурации и лабораторная — по исходнику 4.5.6 · u-blox M8 (SPG 3.01), M10 (SPG 5.00/5.10)
status: published
added: 2026-11-14
tags:
  - GPS
  - GNSS
  - u-blox
  - M10
  - домашняя точка
  - Betaflight
related:
  - bf-failsafe
  - bf-setup-scratch
  - bf-ports
  - bf-cli
  - bf-modes-osd
  - bf-arming-safety
  - est-gnss
  - inav-gps
  - el-peripherals
  - el-emi
  - link-vtx
next: []
---

## summary
GPS на Betaflight нужен для GPS Rescue, стрелки дома и скорости в OSD. Важно не «спутники есть», а «дом записан правильно и курс известен». Модуль разбирает выбор и подключение u-blox M8 или M10, что Betaflight пишет в приёмник при `gps_auto_config = ON` (по коду `io/gps.c`, который в четырёх местах расходится с документацией), переменные `gps_*` и `mag_*`, флаг арма GPS, запись дома, курс без компаса, OSD, `gpspassthrough` с u-center, холодный, тёплый и горячий старт, DOP и CEP. Лабораторная на Python: парсер UBX по правилам 4.5 проверяется на реальной записи M8030 (DOP совпал с приёмником до 0.02), затем шесть синтетических логов показывают влияние созвездий и шума VTX, плюс загрузка UART. На железе — спутники при выключенном и включённом VTX, хронометраж холодного старта и проверка дома. Сам GPS Rescue — в `bf-failsafe` и `bf-setup-scratch`.

## theory
### Что GPS даёт Betaflight 2025.12
Betaflight не летает по точкам (это INAV и ArduPilot, `inav-gps`). С 2025.12 он умеет удерживать позицию (режим POS HOLD, id 11, переменные `pos_hold_*` и `ap_position_*`; опция сборки) и высоту (ALTHOLD); в 4.5 этих режимов нет. Координаты идут в GPS Rescue, в дом, дистанцию и стрелку OSD, в скорость и координаты OSD и телеметрии, в высоту (`flight/position.c` смешивает GPS с баро с весом `gpsTrust = min(1/PDOP, 0.9)`) и в круговой таймер `gps_lap_timer_*`. Без компаса GPS ещё и задаёт курс; POS HOLD без компаса разрешает `pos_hold_without_mag` (по умолчанию OFF).

### Модуль: M8 или M10
| Параметр | u-blox M8 (NEO-M8N, FW 3.01) | u-blox M10 (MAX-M10S, ROM SPG 5.10) |
|---|---|---|
| Созвездия по умолчанию | GPS + GLONASS (+ SBAS, QZSS), Galileo выключен | GPS + Galileo + BeiDou B1I (+ QZSS, SBAS) |
| Холодный старт | 26 с (GPS+GLO), 29 с только GPS | 27 с по умолчанию, 23–28 с в других наборах |
| Горячий старт | 1 с | 1 с |
| Точность CEP (24 ч, статика) | 2.5 м (2.0 м с SBAS) | 1.5 м |
| Макс. частота навигации | NEO-M8N: 5 Гц при двух системах, 10 Гц при одной | 3 Гц по умолчанию (GPS+GAL+BDS), 10 Гц для GPS+GAL, 6 Гц для GPS+GAL+GLO; 18 Гц при одной системе |
| Питание самого модуля | 2.7–3.6 В | 1.76–3.6 В, 9.5 мА при 3 В (GPS+GAL+BDS) |
| UART по умолчанию | 9600 8N1, NMEA | 9600 8N1, NMEA |

Цифры — из даташитов u-blox. M10 точнее, экономнее и видит больше спутников, но заводской MAX-M10S при GPS+GAL+BDS не выдаёт 10 Гц, на которые его настраивает Betaflight: потолок 3 Гц. Умолчания M10 зависят от прошивки: у ROM 5.00 это GPS+GAL, у SAM-M10Q — GPS+GAL+GLO+BDS B1C. Версию и набор созвездий смотри в u-center (MON-VER, MON-GNSS).

FPV-модуль — это приёмник, LDO, патч-антенна, иногда конденсатор или батарейка на V_BCKP и компас на I²C. «5 В» на шелкографии — вход LDO, сам чип питается 3.3 или 1.8 В; без LDO нужен пад 3.3 В, решает маркировка платы. Питание V_BCKP сохраняет эфемериды и часы — повторный старт за секунды. Пусковой ток SAM-M10Q — до 100 мА.

### Проводка и установка
- **UART крест-накрест:** TX модуля → RX полётника, RX → TX, общий GND. Нужны оба провода: Betaflight шлёт модулю конфигурацию. Только аппаратный UART: на SoftSerial скорость режется до 19200 (`serial.c`), этого мало (шаг 3). Компас (SDA/SCL) — на I²C-пады.
- **Антенна** смотрит в небо, над ней ничего проводящего. SAM-M10Q даёт оптимальную диаграмму на земляной плоскости 50 × 50 мм; плата FPV-модуля 20–25 мм, поэтому крупный модуль на мачте обычно лучше мелкого в раме.
- **Помехи:** сигналы L1 у Земли — около −130 дБм на 1561–1602 МГц (BeiDou B1I 1561.098, GPS и Galileo 1575.42, GLONASS ≈ 1602). Модуль — подальше от VTX и его антенны, цифрового модуля с камерой, ESC и силовых проводов; видео 1.2–1.3 ГГц ближе всех к L-диапазону. Насколько мешает твой VTX, покажет стендовый тест в практике.
- **Наклон:** документация советует наклонить аппарат на 45° во все стороны — спутники не должны теряться, домой аппарат летит с наклоном.

### Как Betaflight настраивает модуль (по коду)
Последовательность ниже прочитана по `io/gps.c` 4.5.6 (проверено на 4.5.6). В 2025.12 файл переформатирован; по нему сверено только то, что названо явно: скорости автопоиска (добавлена 230400), провайдер VIRTUAL, умолчания `pg/gps.c`, порог `GPS_MIN_SAT_COUNT` = 4, переключение модели через `gps_ublox_acquire_model` / `gps_ublox_flight_model` и то, что `gps_auto_baud` по-прежнему читается только в `status`.

{{diagram:bf-gps-boot-flow|После включения Betaflight сам ищет скорость модуля, переводит его на скорость из `serial`, пишет настройки в RAM и переключает динамическую модель на первом 3D fix. Дом записывается при арме (и при калибровке гиро стиками) и только при числе спутников не меньше `gps_rescue_min_sats`.}}

При `gps_provider = UBLOX` автомат `gpsConfigureUblox()` делает следующее.
1. **Поиск скорости.** Три запроса MON-VER через 330 мс. Нет ответа — следующая скорость: от скорости из `serial` вверх до 115200, затем с 9600 вверх по кругу. Ответ (hwVersion `00080000` = M8, `000A0000` = M10) выбирает ветку: для M9 и новее CFG-VALSET, для M8 и старше старые сообщения CFG.
2. **Смена скорости.** Модулю уходит `$PUBX,41,…` со скоростью GPS из команды `serial`, затем пауза 990 мс.
3. **Конфигурация** (только при `gps_auto_config = ON`): пауза 1 с, затем 16 (M10) или 22 (M8) шагов не чаще раза в 110 мс: частота 1 Гц, отключение NMEA, модель `gps_ublox_acquire_model`, SBAS, питание FULL, NAV-PVT каждый цикл, NAV-SAT каждый 5-й, `gps_update_rate_hz`, CFG-GNSS (Galileo). Всё — в RAM модуля (`UBX_VAL_LAYER_RAM`). Оценка по константам: заводской модуль на 9600 при `serial … 57600` готов через 2 + 0.3 + 1 + 1 + 1.8 ≈ 6 с.
4. **Приём.** На первом 3D fix (не при арме!) модуль получает `gps_ublox_flight_model`. Если NAV-данных нет 2.5 с, автомат снова уходит в поиск скорости.

Где документация расходится с кодом (проверено на 4.5.6):
- Страница GPS говорит: Stationary до арма, Airborne <4g после. В коде переключение происходит на первом 3D fix (`gpsUpdate()`), арм тут ни при чём.
- Там же сказано, что `gps_sbas_mode` по умолчанию AUTO. В `pg/gps.c` (4.5 и 2025.12) — `SBAS_NONE`.
- По документации GPS Rescue прерывается, когда спутников меньше половины `gps_rescue_min_sats`. В коде порог фиксирован: `GPS_MIN_SAT_COUNT` = 4. Это 10 с в полёте (`RESCUE_LOWSATS`), а для «Rescue доступен» хватает 2 с ниже 4. При min_sats 8 результат тот же, при 12 уже нет.
- `gps_auto_baud` (и в 4.5, и в 2025.12) ни на что не влияет, кроме текста `status` («set to AUTO»): для UBLOX поиск скорости идёт всегда, для NMEA не идёт никогда.

Ещё следствия кода. Galileo переключается только старым UBX-CFG-GNSS (опрос → правка → запись), и шаг пропускается при включённом SBAS и выключенном Galileo: `gps_ublox_use_galileo = OFF` с `gps_sbas_mode = AUTO` оставляет Galileo как в модуле (у M10 — включён). Описание интерфейса M10 из CFG-сообщений знает только CFG-CFG, CFG-RST и VALSET/VALGET/VALDEL, поэтому результат проверяй списком спутников E на вкладке GPS. `gps_ublox_mode` из 4.4 удалён: старый `diff` с ним даёт `INVALID NAME`.

### Справочник: переменные и команды (2025.12)
| Переменная / команда | Умолчание | Диапазон | Смысл |
|---|---|---|---|
| `feature GPS` | выкл. | — | без неё GPS-задача не запускается, `status` → `NOT ENABLED` |
| `serial <id> 2 … <gps_baud> …` | 57600 | 9600–115200 (SoftSerial ≤ 19200) | функция GPS (значение 2 = бит 1) и скорость; порт в 2025.12 пишется именем (`serial UART2 2 …`), автопоиск скорости знает 230400 (в 4.5 — до 115200, порт номером) |
| `gps_provider` | UBLOX | NMEA, UBLOX, MSP, VIRTUAL | NMEA — без конфигурации и поиска скорости; VIRTUAL — GPS в SITL (с 2025.12, в 4.5 его нет) |
| `gps_auto_config` | ON | OFF, ON | шаги CONFIGURE; OFF — модуль должен быть настроен в u-center |
| `gps_auto_baud` | OFF | OFF, ON | только текст в `status` |
| `gps_update_rate_hz` | 10 | 1–20 | частота навигации; не выше потолка модуля |
| `gps_ublox_use_galileo` | OFF | OFF, ON | Galileo через CFG-GNSS (см. выше) |
| `gps_sbas_mode` | NONE | AUTO, EGNOS, WAAS, MSAS, GAGAN, NONE | SBAS и маска PRN (EGNOS: 123, 126, 136) |
| `gps_sbas_integrity` | OFF | OFF, ON | использовать флаги целостности SBAS |
| `gps_ublox_acquire_model` | STATIONARY | PORTABLE, STATIONARY, PEDESTRIAN, AUTOMOTIVE, AT_SEA, AIRBORNE_1G/2G/4G | модель до первого 3D fix |
| `gps_ublox_flight_model` | AIRBORNE_4G | те же | модель после первого 3D fix |
| `gps_ublox_utc_standard` | AUTO | AUTO, USNO, EU, SU, NTSC | источник UTC |
| `gps_set_home_point_once` | OFF | OFF, ON | ON: дом пишется на первом арме (или раньше — калибровкой гиро стиками) и держится до перезагрузки |
| `gps_use_3d_speed` | OFF | OFF, ON | скорость в OSD и пройденный путь с учётом вертикали |
| `gps_nmea_custom_commands` | пусто | строка | команды модулю при `gps_provider = NMEA` |
| `gps_rescue_min_sats` | 8 | 5–50 | спутников для снятия флага GPS и для записи дома |
| `gps_rescue_allow_arming_without_fix` | OFF | OFF, ON | арм без фикса, тогда без дома: Rescue недоступен |
| `mag_hardware` | AUTO | AUTO, NONE, HMC5883, AK8975, AK8963, QMC5883, LIS2MDL, LIS3MDL, MPU925X_AK8963, IST8310 | только в сборке с магнитометром |
| `align_mag`, `mag_align_roll/pitch/yaw` | DEFAULT, 0 | −3600…3600 (0.1°) | ориентация компаса |
| `mag_declination` | 0 | −300…300 (0.1°) | магнитное склонение, западное — со знаком минус (в 4.5 диапазон 0–3599) |
| `gps_rescue_use_mag` | ON | OFF, ON | использовать компас в Rescue (если он есть) |
| `osd_gps_sats_show_pdop` | OFF | OFF, ON | PDOP рядом с числом спутников |
| `gpspassthrough` | — | — | мост USB ↔ UART GPS до перезагрузки |
| `status` | — | — | строка `GPS: connected, UART2 57600 (set to 57600), configured, version =  M10` |
| `debug_mode = GPS_CONNECTION` / `GPS_DOP` | — | — | интервал NAV, шаг конфигурации; спутники и DOP в Blackbox |

### Спутники, флаг арма и домашняя точка
- **3D fix** = NAV-PVT `fixType == 3` и бит `gnssFixOK`; спутники — `numSV` оттуда же.
- **Флаг арма GPS** есть, только если Rescue настроен (`failsafe_procedure = GPS-RESCUE` или режим GPS RESCUE). Снимается при 3D fix и `numSat ≥ gps_rescue_min_sats`, после первого арма или при `gps_rescue_allow_arming_without_fix = ON`. Rescue настроен, а `feature GPS` выключена — флаг вечный.
- **Сигналы:** при выполнении условия до арма — один READY_BEEP. На арме — дважды «коротко-длинно» при fix и `numSat ≥ gps_rescue_min_sats`, иначе три длинных по 300 мс.
- **Дом** `GPS_reset_home_position()` пишет на арме (и при калибровке гиро стиками газ вниз + рыскание влево + тангаж вниз), только при fix и `numSat ≥ gps_rescue_min_sats`. При `gps_set_home_point_once = OFF` дом стирается на каждом дизарме: дизарм в поле переносит дом. При ON дом держится до перезагрузки — первый арм делай там, куда возвращаться, и не калибруй гиро стиками в другом месте.
- **В полёте** порог Rescue — 4 спутника, на арме — 8.
- На арме NAV-SAT отключается до перезагрузки: список спутников на вкладке GPS «застывает», это штатно.

### Курс без компаса и сам компас
Без магнитометра рыскание интегрируется гироскопом от включения. `imu.c` поправляет его по путевому углу GPS при fix, больше 4 спутниках и после первого превышения 1 м/с. Вес: 0 при 0 м/с, ∝ v² до 1 м/с, линейно до ×10 при 10 м/с; умножается на наклон вперёд по тангажу (0 при горизонтали или наклоне назад, ×1 при 45°); крен больше 12° и стик рыскания его гасят. Стрелка дома рисуется как `направление на дом − yaw`, поэтому до первого прямого пролёта она врёт. Документация: 30–50 м прямо быстрее 1–2 м/с, потом верить стрелке.

Компас — опция сборки (в Cloud Build выбирается отдельно; так и в 4.5, и в 2025.12). На 5″ его обычно не ставят: поле от десятков ампер в силовых проводах и ESC мешает больше, чем компас помогает; документация советует не включать его без лога «квадрата» с чистыми поворотами на 90°. Если он есть: `align_mag`, калибровка из Betaflight App (15 с на начало вращения, затем 30 с во всех осях), `mag_declination` в 0.1°, сверка с телефоном (истинный север) в пределах 10°. Здоровый компас отключает поправку по GPS-курсу; Rescue сам отключает компас, если 30 с не приближается к дому.

### Элементы OSD
| Элемент | Переменная | Что показывает (проверено на 4.5.6) |
|---|---|---|
| Спутники | `osd_gps_sats_pos` | `NC`, пока GPS не в приёме данных; важность «критично» без fix или при < 4, «внимание» при < `gps_rescue_min_sats` и настроенном Rescue |
| Скорость | `osd_gps_speed_pos` | только при fix; `gps_use_3d_speed` добавляет вертикаль |
| Стрелка дома | `osd_home_dir_pos` | `-`, пока нет fix и дома; символ «над домом» при дистанции 0 |
| Дистанция до дома | `osd_home_dist_pos` | метры от записанного дома |
| Координаты | `osd_gps_lat_pos`, `osd_gps_lon_pos` | широта и долгота для поиска после падения |
| Высота | `osd_altitude_pos` | смесь баро и GPS (`position.c`) |
| Предупреждения | `osd_warnings_pos` | `RESCUE N/A` (Rescue настроен, но недоступен), `RESCUE OFF` |

Минимум: спутники, стрелка и дистанция до дома, координаты, предупреждения. Координаты последнего кадра в записи очков — лучший способ найти упавший аппарат.

Телеметрия CRSF/ELRS (вопрос № 47): кадр GPS уходит при `feature GPS`, если не все четыре `telemetry_disabled_lat_long`, `_ground_speed`, `_heading`, `_altitude` = ON; датчики в EdgeTX — через «Discover new». Режим на пульте `WAIT`, пока аппарат не армлен и нет fix или дома. Дома до первого арма нет, а при `gps_set_home_point_once = OFF` он стирается на каждом дизарме, так что `WAIT` на земле — норма.

### Точность и время старта
**Холодный старт** (нет альманаха, эфемерид, времени): 26–29 с по даташитам при открытом небе. **Тёплый** — время и альманах есть, эфемериды устарели (u-blox: годны до 4 ч); их всё равно скачивать (GPS шлёт их в подкадрах 1–3 по 6 с), так что тёплый ближе к холодному, даташиты цифры не дают. **Горячий** — свежие эфемериды в BBR при живом V_BCKP: 1 с, дольше идёт автоконфигурация Betaflight (около 6 с).

DOP — множитель геометрии: ошибка позиции ≈ DOP × ошибка дальности (`est-gnss`). Betaflight работает с **PDOP** (проверено на 4.5.6): NAV-DOP на M7+ отключён, поле `hdop` не обновляется, приложение и MSP получают PDOP. PDOP около 1.0 и ниже — хорошо (документация Rescue), выше 2.5 — слабая геометрия. Хороший модуль на месте: 1–2 м CEP, скорость не больше 10–20 см/с; стабильно выше 25 см/с — модуль или место непригодны (документация Rescue).

### `gpspassthrough` и u-center
`gpspassthrough` замыкает USB-порт CLI на UART GPS на текущей скорости порта (после автоконфигурации — 57600) в бесконечном цикле: выход только перезагрузкой. Нужны `feature GPS` и порт с функцией GPS; если плата не питает GPS-пад от USB (документация называет SPRacingF3), подключи АКБ без пропеллеров. Порядок: `gpspassthrough` → закрыть Betaflight App → u-center на том же COM-порту. Смотреть: MON-VER (ROM SPG 5.00 или 5.10), MON-GNSS, C/N0 в NAV-SAT; записать `.ubx` для лабораторной. Настраивать то, чего Betaflight не трогает: созвездия M10 через CFG-SIGNAL (GPS+GAL ради 10 Гц), питание у ROM 5.00. Сохранять в BBR/flash; у MAX-M10S flash нет, BBR живёт, пока есть V_BCKP. Свои пункты (скорость, модель, SBAS, частота, сообщения) Betaflight перепишет в RAM при каждой загрузке.

### Чем отличается 4.5 и что дальше
Переменные `gps_*` в 4.5 и 2025.12 одни и те же (по `cli/settings.c` отличается только диапазон `mag_declination`). В 4.5 поиск скорости не знает 230400, провайдера VIRTUAL нет (в SITL 4.5 GPS нет вовсе), а высоту посадки и газ GPS Rescue задают `gps_rescue_landing_alt` и `gps_rescue_throttle_*` — в 2025.12 их заменили общие `ap_landing_altitude_m`, `ap_hover_throttle`, `ap_throttle_min/max`, `ap_altitude_*`. Умолчание `gps_rescue_disarm_threshold` в 2025.12 — 30 (в 4.5 — 20). В 2026.6 удалены `gps_rescue_velocity_p/i/d`, `gps_rescue_max_angle`, `gps_rescue_roll_mix`, `gps_rescue_use_mag` и добавлен `trust_mag` (по примечаниям к выпуску 2026.6; к целевой версии курса не относится). `master` (2026.12): `gps_uart`, `gps_baud`, `gps_ublox_enable_ana` (AssistNow Autonomous, в 4.5 закомментирован).

### Место в системе

- **Получает:** аппаратный UART с функцией GPS и скоростью из `serial` (`bf-ports`); опции GPS и магнитометра в сборке (`bf-custom`); помехи от VTX и силовых проводов, из-за которых падает число спутников (`el-emi`); геометрию спутников — DOP (`est-gnss`).
- **Отдаёт:** дом, дистанцию и курс — GPS Rescue (`bf-failsafe`); флаг арма `GPS` (`bf-arming-safety`); спутники, стрелку дома и координаты — в OSD (`bf-modes-osd`) и в телеметрию CRSF (`link-elrs`).
- **Если ошибиться здесь:** дизарм и повторный арм в поле при `gps_set_home_point_once = OFF` → дом перенесён, Rescue вернёт аппарат не туда, откуда взлетал (`bf-failsafe`). GPS повешен на SoftSerial → скорость ограничена 19200, этого мало; выглядит как плохой модуль, а причина — в распределении портов (`bf-ports`).

## practice
### Шаг 1. Парсер UBX по правилам 4.5 и проверка на реальной записи
Скрипт и вывод всей лабораторной сняты по `io/gps.c` 4.5.6; разбор кадров в 2025.12 построчно не перепроверялся (фаза 2 перезапустит лабораторную). В SITL Betaflight 4.5 GPS нет (в 2025.12 есть виртуальный), поэтому лабораторная — Python, который читает UBX так же, как `UBLOX_parse_gps()`. Файл `gps_lab.py` — это четыре блока этого модуля подряд. Блок 1: кадры с контрольной суммой, поля NAV-PVT и NAV-SAT, DOP из геометрии.

```python
"""bf-gps-setup lab: read a u-blox UBX capture the way Betaflight 4.5 reads it.

Block 1 - UBX framing and the fields io/gps.c (4.5) takes from NAV-PVT / NAV-SAT, DOP from geometry.
Block 2 - SYNTHETIC capture generator (no real log in the course repo): fixed sky, 10 Hz NAV-PVT +
          NAV-SAT every 5th epoch, exactly the message set Betaflight 4.5 auto-config enables.
          Every number of the sky / signal / error model is an assumption and is printed in the header.
Block 3 - analysis: TTFF, time to "8 sats + 3D fix" (arming flag GPS clears), sats, PDOP, HDOP,
          position scatter (CEP50 / R95), still-speed, UART load, for six scenarios; check_real() runs
          the same parser on a real capture and compares our DOP with the receiver's NAV-DOP.
Run:  python3 gps_lab.py [outdir] [real_capture.ubx]
"""
import math
import random
import struct
import sys
from pathlib import Path

import numpy as np

# ---------------- Block 1: UBX as Betaflight 4.5 parses it ----------------
GNSS = {0: "G", 1: "S", 2: "E", 3: "C", 5: "J", 6: "R"}   # u-blox gnssId: GPS, SBAS, GAL, BDS, QZSS, GLO


def ubx(cls, mid, payload):
    body = bytes([cls, mid]) + struct.pack("<H", len(payload)) + payload
    a = b = 0
    for x in body:                                # 8-bit Fletcher over class..payload
        a = (a + x) & 0xFF
        b = (b + a) & 0xFF
    return b"\xb5\x62" + body + bytes([a, b])


def frames(data, stats):
    i = 0
    while True:
        i = data.find(b"\xb5\x62", i)
        if i < 0 or i + 8 > len(data):
            return
        n = struct.unpack_from("<H", data, i + 4)[0]
        end = i + 8 + n
        if end > len(data):
            return
        a = b = 0
        for x in data[i + 2:i + 6 + n]:
            a = (a + x) & 0xFF
            b = (b + a) & 0xFF
        if data[end - 2] == a and data[end - 1] == b:
            yield data[i + 2], data[i + 3], data[i + 6:i + 6 + n]
            i = end
        else:
            stats["bad"] += 1
            i += 2


def nav_pvt(p):
    """UBLOX_parse_gps(), case NAV-PVT: fix = gnssFixOK && fixType == 3D; numSV; pDOP; gSpeed/10."""
    fix_type, flags, num_sv = p[20], p[21], p[23]
    lon, lat, _h, hmsl, hacc = struct.unpack_from("<iiiiI", p, 24)
    gspeed = struct.unpack_from("<i", p, 60)[0]
    return dict(t=struct.unpack_from("<I", p, 0)[0] / 1000, fix=bool(flags & 1) and fix_type == 3,
                sats=num_sv, lat=lat * 1e-7, lon=lon * 1e-7, alt_cm=int(hmsl / 10),
                hacc=hacc / 1000, speed_cms=int(gspeed / 10), pdop=struct.unpack_from("<H", p, 76)[0] / 100)


def nav_sat(p):
    t, _ver, n = struct.unpack_from("<IBB", p, 0)
    svs = [struct.unpack_from("<BBBbhhI", p, 8 + 12 * k) for k in range(n)]
    return t / 1000, [(GNSS[g], sv, cno, el, az, bool(fl & 8)) for g, sv, cno, el, az, _pr, fl in svs]


def dop(used, clock_per_system=False):
    """used: [(system, el_deg, az_deg)]. Unknowns E, N, U + receiver clock(s). One common clock reproduces
    the receiver's NAV-DOP (checked on the real capture); a clock per system is the stricter LS model."""
    systems = sorted({s for s, _, _ in used}) if clock_per_system else ["*"]
    H = []
    for s, el, az in used:
        e, a = math.radians(el), math.radians(az)
        H.append([-math.cos(e) * math.sin(a), -math.cos(e) * math.cos(a), -math.sin(e)]
                 + [1.0 if k in (s, "*") else 0.0 for k in systems])
    H = np.array(H)
    Q = np.linalg.inv(H.T @ H)
    return math.sqrt(Q[0, 0] + Q[1, 1]), math.sqrt(Q[0, 0] + Q[1, 1] + Q[2, 2]), H, Q
```

Проверка на настоящем приёмнике — открытая запись u-blox M8030 из тестов pyubx2: `curl -O https://raw.githubusercontent.com/semuconsulting/pyubx2/master/tests/pygpsdata-MIXED.log`. `check_real()` (блок 4) печатает, что увидел бы Betaflight, и сравнивает DOP по углам из NAV-SAT с NAV-DOP приёмника:

```text
real capture pygpsdata-MIXED.log: HW UBX-M8030 00080000, NAV-PVT 39, NAV-SAT 28, NAV-DOP 17, bad checksums 0
  Betaflight view: 3D fix 39/39, numSV 13-15, pDOP 1.35-1.75, hAcc 6.3-7.0 m, scatter over 38 s: max 0.88 m
  epoch     used (sys)          HDOP rx / 1 clk / clk per sys   PDOP rx / 1 clk / clk per sys
     473615  15 {'G': 8, 'R': 7}    0.78 /  0.78 /  0.78              1.35 /  1.35 /  1.36
     473621  13 {'G': 7, 'R': 6}    1.07 /  1.05 /  1.29              1.75 /  1.75 /  1.92
     473627  14 {'G': 7, 'R': 7}    0.94 /  0.94 /  1.00              1.66 /  1.67 /  1.74
     473645  13 {'G': 6, 'R': 7}    0.96 /  0.97 /  1.02              1.68 /  1.68 /  1.74
     473648  14 {'G': 7, 'R': 7}    0.94 /  0.94 /  1.00              1.66 /  1.66 /  1.73
```

Показаны 5 из 14 эпох, остальные такие же. Модель «одни часы» повторяет DOP приёмника до 0.02; «часы на каждую систему» при 13–14 спутниках даёт на 5–23 % больше — значит, отчётный DOP M8 в этой записи считается с одними часами. Приёмник оценивает hAcc в 6–7 м, а за 38 с точка ушла на 0.88 м: короткая запись точность не измеряет, ошибка меняется минутами. Поэтому на железе пишем 10 минут.

### Шаг 2. Синтетические логи: созвездия, шум VTX, старт
Блок 2 пишет **синтетические** `.ubx` с тем же набором сообщений, что после автоконфигурации 4.5 (NAV-PVT 10 Гц, NAV-SAT каждый 5-й цикл). Небо, C/N0 и ошибки — допущения, они печатаются в заголовке вывода; декодирование эфемерид (18–30 с после захвата) подобрано под холодный старт 26–29 с из даташитов. Ошибка позиции — настоящее решение МНК по геометрии с коррелированной ошибкой дальности каждого спутника. Фикс: 3 + число систем спутников и PDOP ≤ 25 (маска, которую Betaflight пишет в M8).

```python
# ---------------- Block 2: SYNTHETIC capture (assumptions, not measurements) ----------------
VISIBLE = {"G": 10, "E": 8, "C": 10, "R": 7}     # sats above 5 deg, mid-latitude open sky (assumed)
CNO_TRACK, CNO_DECODE = 20, 30                   # dB-Hz: keep tracking / decode ephemeris from cold (assumed)
SIGMA_SLOW, TAU_S, SIGMA_WHITE = 1.5, 60.0, 0.3  # m per sat: multipath+atmosphere (Gauss-Markov) + noise
LAT0, LON0, ALT0 = 50.45, 30.52, 180.0           # arbitrary bench location


def sky(seed=7):
    rnd = random.Random(seed)
    out = []
    for s, n in VISIBLE.items():
        for k in range(n):
            el = math.degrees(math.asin(rnd.uniform(math.sin(math.radians(5)), 1.0)))
            out.append(dict(sys=s, sv=k + 1, el=el, az=rnd.uniform(0, 360),
                            cno0=28 + 18 * math.sin(math.radians(el)) + rnd.gauss(0, 1.5)))
    return out


def make_capture(path, systems, start="cold", noise_db=0.0, seed=1, duration=600, rate=10):
    rnd = random.Random(seed)
    sats = [dict(s) for s in sky() if s["sys"] in systems]
    for s in sats:
        s["cno"] = max(0.0, s["cno0"] - noise_db)
        acq = rnd.uniform(2, 10) if start == "cold" else rnd.uniform(0.3, 1.0)
        s["t_acq"] = acq if s["cno"] >= CNO_TRACK else math.inf
        if start == "hot":
            s["t_eph"] = s["t_acq"]                      # ephemeris kept in BBR (V_BCKP), < 4 h old
        else:
            s["t_eph"] = acq + rnd.uniform(18, 30) if s["cno"] >= CNO_DECODE else math.inf
        s["err"] = rnd.gauss(0, SIGMA_SLOW)
    phi = math.exp(-1 / (rate * TAU_S))
    m_per_deg = 111_320.0
    out = bytearray()
    for k in range(1, duration * rate + 1):
        t = k / rate
        for s in sats:
            s["err"] = phi * s["err"] + math.sqrt(1 - phi * phi) * rnd.gauss(0, SIGMA_SLOW)
        used = [s for s in sats if t >= s["t_eph"] and s["cno"] >= CNO_TRACK]
        fix, pdop_v, hdop_v, dE = False, 99.99, 99.99, np.zeros(3)
        if len(used) >= 3 + len({s["sys"] for s in used}):
            geo = [(s["sys"], s["el"], s["az"]) for s in used]
            hdop_v, pdop_v, _, _ = dop(geo)              # what the receiver reports
            _, _, H, Q = dop(geo, clock_per_system=True)  # solution with an inter-system clock bias
            eps = np.array([s["err"] + rnd.gauss(0, SIGMA_WHITE) for s in used])
            dE = (Q @ H.T @ eps)[:3]                     # least-squares position error, metres E/N/U
            fix = pdop_v <= 25.0                          # pDOP mask Betaflight writes to M8 (NAV5 pDOP = 250)
        lat = LAT0 + dE[1] / m_per_deg
        lon = LON0 + dE[0] / (m_per_deg * math.cos(math.radians(LAT0)))
        vel = [rnd.gauss(0, 0.05 * hdop_v) if fix else 0.0 for _ in range(2)]   # 0.05 m/s per axis x HDOP
        pvt = bytearray(92)
        struct.pack_into("<I", pvt, 0, int(t * 1000))
        pvt[20], pvt[21], pvt[23] = (3 if fix else 0), (1 if fix else 0), (len(used) if fix else 0)
        struct.pack_into("<iiiiII", pvt, 24, round(lon * 1e7), round(lat * 1e7), round((ALT0 + dE[2]) * 1000),
                         round((ALT0 + dE[2]) * 1000), round(hdop_v * SIGMA_SLOW * 1000), 9999)
        struct.pack_into("<i", pvt, 60, round(math.hypot(*vel) * 1000))
        struct.pack_into("<H", pvt, 76, min(9999, round(pdop_v * 100)))
        out += ubx(0x01, 0x07, bytes(pvt))
        if k % 5 == 0:                                   # setSatInfoMessageRate(5): NAV-SAT every 5th epoch
            inv = {v: g for g, v in GNSS.items()}
            body = struct.pack("<IBBH", int(t * 1000), 1, len(sats), 0)
            for s in sats:
                cno = round(s["cno"]) if t >= s["t_acq"] else 0
                flags = 4 | (8 if s in used and fix else 0)
                body += struct.pack("<BBBbhhI", inv[s["sys"]], s["sv"], cno, round(s["el"]), round(s["az"]), 0, flags)
            out += ubx(0x01, 0x35, body)
    Path(path).write_bytes(bytes(out))
    return len(sats)
```

Блок 3 — анализ: TTFF (первый 3D fix), «8sat» (флаг арма GPS снялся бы при `gps_rescue_min_sats = 8`), медианы спутников и DOP, CEP50/R95 и v95 после первой минуты фикса, загрузка UART.

```python
# ---------------- Block 3: analysis ----------------
def analyze(path, min_sats=8):
    stats = {"bad": 0}
    pvts, sat_epochs = [], []
    for cls, mid, p in frames(Path(path).read_bytes(), stats):
        if (cls, mid) == (0x01, 0x07):
            pvts.append(nav_pvt(p))
        elif (cls, mid) == (0x01, 0x35):
            sat_epochs.append(nav_sat(p))
    t_fix = next((e["t"] for e in pvts if e["fix"]), None)
    t_arm = next((e["t"] for e in pvts if e["fix"] and e["sats"] >= min_sats), None)
    if t_fix is None:
        return dict(n=len(pvts), bad=stats["bad"], ttff=None, t_arm=None)
    late = [e for e in pvts if e["fix"] and e["t"] >= t_fix + 60]     # skip the first minute after fix
    lat0 = np.mean([e["lat"] for e in late])
    lon0 = np.mean([e["lon"] for e in late])
    east = np.array([(e["lon"] - lon0) * 111_320 * math.cos(math.radians(lat0)) for e in late])
    north = np.array([(e["lat"] - lat0) * 111_320 for e in late])
    r = np.hypot(east, north)
    hd = [dop([(s, el, az) for s, _sv, _c, el, az, u in svs if u])[0]
          for t, svs in sat_epochs if t >= t_fix + 60]
    last = sat_epochs[-1][1]
    return dict(n=len(pvts), bad=stats["bad"], ttff=t_fix, t_arm=t_arm,
                sats=float(np.median([e["sats"] for e in late])), pdop=float(np.median([e["pdop"] for e in late])),
                hdop=float(np.median(hd)), cep50=float(np.percentile(r, 50)), r95=float(np.percentile(r, 95)),
                rmax=float(r.max()), v95=float(np.percentile([e["speed_cms"] for e in late], 95)),
                trk=sum(1 for sv in last if sv[2] > 0), used=sum(1 for sv in last if sv[5]))


def uart_load(n_svs, rate=10, sat_div=5):
    pvt = 8 + 92                                        # header 6 + checksum 2 + payload
    sat = 8 + 8 + 12 * n_svs
    bps = 10 * (rate * pvt + rate / sat_div * sat)      # 8N1 = 10 bits per byte
    return bps, {b: 100 * bps / b for b in (9600, 19200, 38400, 57600, 115200)}
```

Вывод `python3 gps_lab.py out pygpsdata-MIXED.log`, синтетическая часть:

```text
SYNTHETIC capture - model assumptions:
  visible sats {'G': 10, 'E': 8, 'C': 10, 'R': 7}, track >= 20 dB-Hz, cold decode >= 30 dB-Hz,
  pseudorange error 1.5 m (tau 60 s) + 0.3 m white, 10 Hz NAV-PVT, NAV-SAT 1:5, 600 s

scenario                             file kB TTFF s 8sat s trk sats  PDOP  HDOP CEP50   R95  v95 bad
GPS only                                 745   26.7   32.8  10   10  1.57  0.79  1.13  2.61    9   0
M8 default: GPS+GLO (galileo OFF)        844   25.8   27.1  17   16  1.38  0.60  0.70  1.30    7   0
M8 + gps_ublox_use_galileo=ON            956   28.6   29.3  25   24  1.06  0.50  0.44  0.90    6   0
M10 default: GPS+GAL+BDS                 998   25.4   26.5  28   28  0.87  0.46  0.55  1.23    5   0
M10 default, VTX noise +10 dB            998   27.8   29.2  28    9  4.70  1.31  1.91  3.33   15   0
M10 default, hot start                   998    0.5    0.6  28   28  0.87  0.46  0.59  1.09    5   0
  (TTFF and 8sat: s from power-on; trk = sats with C/N0 > 0 in the last NAV-SAT; sats/DOP/scatter: medians after the first 60 s of fix; CEP50/R95 m; v95 = 95th pct still speed, cm/s; bad = frames with a wrong checksum)
```

{{diagram:chart-bf-gps-cold-sats|Холодный старт по синтетическим логам: GPS+GLONASS и M10 проходят порог 8 спутников за 1–2 с после фикса, только GPS — за 6 с. Шум VTX +10 дБ оставляет в решении 9 спутников из 28 видимых.}}

Что показывает таблица (числа — свойства модели, причины — физические):
1. **Созвездия.** Только GPS: 10 спутников, PDOP 1.57, R95 2.6 м; с GLONASS — 16 и 1.38; с Galileo — 24 и 1.06, R95 0.9 м против 1.3 м. M10 из коробки по геометрии лучше M8 из коробки. TTFF у всех 25–29 с: его задаёт декодирование эфемерид, а не число спутников.
2. **Флаг GPS.** «Только GPS» доходит до 8 спутников через 6 с после фикса (32.8 против 26.7 с), с двумя системами — через 1 с.
3. **Шум VTX** +10 дБ снижает C/N0 всех спутников на 10 дБ. Отслеживаются все 28 (`trk`), но эфемериды из холодного старта скачаны только у 9 сильных: PDOP 4.70, R95 3.3 м, скорость на месте 15 см/с. Механизм — в даташите: чувствительность холодного старта −148 дБм, слежения −167 дБм. Поэтому стенд сравнивает и спутники после фикса, и холодный старт с включённым VTX.
4. **Горячий старт:** фикс за 0.5 с, дольше ждать автоконфигурацию Betaflight (около 6 с).

### Шаг 3. Скорость UART
```text
UART load, 10 Hz NAV-PVT + NAV-SAT 1:5 (disarmed):
  10 SVs in NAV-SAT:  12720 bit/s -> 9600: 132.5%  19200:  66.2%  38400:  33.1%  57600:  22.1%  115200:  11.0%
  28 SVs in NAV-SAT:  17040 bit/s -> 9600: 177.5%  19200:  88.8%  38400:  44.4%  57600:  29.6%  115200:  14.8%
  32 SVs in NAV-SAT:  18000 bit/s -> 9600: 187.5%  19200:  93.8%  38400:  46.9%  57600:  31.2%  115200:  15.6%
```

На 9600 при 10 Гц не помещается даже NAV-PVT. На 19200 (предел SoftSerial) загрузка 89–94 % до арма — кадры будут теряться. 57600 (умолчание) — 30 %; на 115200 документация отмечает потери пакетов и советует 57600.

Четвёртый блок — проверка реальной записи и запуск. Свою запись подставь вторым аргументом: `python3 gps_lab.py out my_m10.ubx`.

```python
def check_real(path):
    """A real capture: what Betaflight would read, and our DOP from NAV-SAT vs the receiver's NAV-DOP."""
    data = Path(path).read_bytes()
    hw = [ln.split(",")[-1].split("*")[0] for ln in data.decode("ascii", "replace").splitlines()
          if ln.startswith("$GNTXT") and "HW" in ln]
    stats, pvt, sat, rx = {"bad": 0}, {}, {}, {}
    for cls, mid, p in frames(data, stats):
        if (cls, mid) == (0x01, 0x07):
            e = nav_pvt(p)
            pvt[e["t"]] = e
        elif (cls, mid) == (0x01, 0x35):
            t, svs = nav_sat(p)
            sat[t] = svs
        elif (cls, mid) == (0x01, 0x04):                 # NAV-DOP: gDOP pDOP tDOP vDOP hDOP (x0.01)
            t = struct.unpack_from("<I", p, 0)[0] / 1000
            rx[t] = [v / 100 for v in struct.unpack_from("<5H", p, 4)]
    print(f"real capture {Path(path).name}: {hw[0] if hw else '?'}, NAV-PVT {len(pvt)}, NAV-SAT {len(sat)},"
          f" NAV-DOP {len(rx)}, bad checksums {stats['bad']}")
    e = list(pvt.values())
    lat0, lon0 = np.mean([x["lat"] for x in e]), np.mean([x["lon"] for x in e])
    r = [math.hypot((x["lon"] - lon0) * 111_320 * math.cos(math.radians(lat0)), (x["lat"] - lat0) * 111_320) for x in e]
    print(f"  Betaflight view: 3D fix {sum(x['fix'] for x in e)}/{len(e)}, numSV {min(x['sats'] for x in e)}-"
          f"{max(x['sats'] for x in e)}, pDOP {min(x['pdop'] for x in e):.2f}-{max(x['pdop'] for x in e):.2f},"
          f" hAcc {min(x['hacc'] for x in e):.1f}-{max(x['hacc'] for x in e):.1f} m,"
          f" scatter over {e[-1]['t'] - e[0]['t']:.0f} s: max {max(r):.2f} m")
    print("  epoch     used (sys)          HDOP rx / 1 clk / clk per sys   PDOP rx / 1 clk / clk per sys")
    for t in sorted(set(sat) & set(rx)):
        used = [(s, el, az) for s, _sv, _c, el, az, u in sat[t] if u]
        h1, p1, _, _ = dop(used)
        h2, p2, _, _ = dop(used, clock_per_system=True)
        by = {k: sum(1 for u in used if u[0] == k) for k in sorted({u[0] for u in used})}
        print(f"  {t:9.0f}  {len(used):2d} {str(by):16s}   {rx[t][4]:5.2f} / {h1:5.2f} / {h2:5.2f}"
              f"             {rx[t][1]:5.2f} / {p1:5.2f} / {p2:5.2f}")


SCENARIOS = [  # name, constellations, start, VTX noise rise dB
    ("GPS only", "G", "cold", 0),
    ("M8 default: GPS+GLO (galileo OFF)", "GR", "cold", 0),
    ("M8 + gps_ublox_use_galileo=ON", "GRE", "cold", 0),
    ("M10 default: GPS+GAL+BDS", "GEC", "cold", 0),
    ("M10 default, VTX noise +10 dB", "GEC", "cold", 10),
    ("M10 default, hot start", "GEC", "hot", 0),
]

if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) > 2:
        check_real(sys.argv[2])
        print()
    print("SYNTHETIC capture - model assumptions:")
    print(f"  visible sats {VISIBLE}, track >= {CNO_TRACK} dB-Hz, cold decode >= {CNO_DECODE} dB-Hz,")
    print(f"  pseudorange error {SIGMA_SLOW} m (tau {TAU_S:.0f} s) + {SIGMA_WHITE} m white, 10 Hz NAV-PVT, NAV-SAT 1:5, 600 s")
    print()
    print(f"{'scenario':36s} {'file kB':>7s} {'TTFF s':>6s} {'8sat s':>6s} {'trk':>3s} {'sats':>4s} {'PDOP':>5s} {'HDOP':>5s}"
          f" {'CEP50':>5s} {'R95':>5s} {'v95':>4s} {'bad':>3s}")
    for i, (name, systems, start, noise) in enumerate(SCENARIOS):
        f = out / f"synthetic_{i}_{systems}_{start}_{noise}dB.ubx"
        make_capture(f, systems, start, noise, seed=100 + i)
        a = analyze(f)
        kb = f.stat().st_size / 1024
        if a["ttff"] is None:
            print(f"{name:36s} {kb:7.0f}  no 3D fix in 600 s")
            continue
        arm = f"{a['t_arm']:6.1f}" if a["t_arm"] is not None else "  never"
        print(f"{name:36s} {kb:7.0f} {a['ttff']:6.1f} {arm} {a['trk']:3d} {a['sats']:4.0f} {a['pdop']:5.2f} {a['hdop']:5.2f}"
              f" {a['cep50']:5.2f} {a['r95']:5.2f} {a['v95']:4.0f} {a['bad']:3d}")
    print("  (TTFF and 8sat: s from power-on; trk = sats with C/N0 > 0 in the last NAV-SAT; sats/DOP/scatter: medians after the first 60 s of fix;"
          " CEP50/R95 m; v95 = 95th pct still speed, cm/s; bad = frames with a wrong checksum)")
    print()
    print("UART load, 10 Hz NAV-PVT + NAV-SAT 1:5 (disarmed):")
    for n in (10, 28, 32):
        bps, util = uart_load(n)
        print(f"  {n:2d} SVs in NAV-SAT: {bps:6.0f} bit/s -> " + "  ".join(f"{b}: {u:5.1f}%" for b, u in util.items()))
```

### Шаг 4. Конфигурация (процедура по исходнику и документации)
Betaflight App: Ports → UART2 → Sensor Input «GPS», 57600 → Save and Reboot. Configuration → GPS включить, протокол UBLOX, Auto Config. То же в CLI:

```text
feature GPS
serial UART2 2 115200 57600 0 115200
set gps_provider = UBLOX
set gps_auto_config = ON
set gps_ublox_use_galileo = ON
set gps_sbas_mode = AUTO
set gps_update_rate_hz = 10
set gps_set_home_point_once = OFF
set gps_rescue_min_sats = 8
set osd_gps_sats_show_pdop = ON
save
```

`serial UART2 2 …` (в 4.5 — `serial 1 2 …`): UART2, функция GPS (значение 2 = бит 1), четвёртое число — скорость GPS. Для MAX-M10S с заводским набором GPS+GAL+BDS (потолок 3 Гц) есть два пути. Первый — `set gps_update_rate_hz = 3`. Второй — u-center через `gpspassthrough`: CFG-SIGNAL GPS+GAL, сохранить в BBR, тогда 10 Гц. После перезагрузки `status` должен показать `GPS: connected, UART2 57600 (set to 57600), configured, version =  M10` (два пробела после `=` — так в `cli.c`).

### Переход на реальное железо
Пропеллеры сняты на шагах 1–5. GPS Rescue включается только после этой процедуры, по `bf-failsafe`.
1. **Проводка.** Прозвонить TX→RX и RX→TX, GND. Напряжение пада питания GPS без модуля — по маркировке платы модуля (5 В на вход LDO или 3.3 В). `status` → `connected … configured, version = M8|M10`. Если `NOT CONNECTED`, смотри диагностику.
2. **Холодный старт, открытое небо.** Аппарат на столе в поле или на крыше, VTX без питания или в pit mode. Модуль без питания больше 4 ч, либо сброс через u-center (CFG-RST cold). Засечь время от подключения АКБ до 3D fix и до 8 спутников (вкладка GPS или OSD). Записать через `gpspassthrough` и u-center 10 минут `.ubx` и прогнать `gps_lab.py`. Критерий: фикс до 60 с, спутников не меньше 12 через 2 минуты (документация: «около 20»), PDOP ≤ 1.5, скорость на месте p95 ≤ 20 см/с, R95 ≤ 3 м.
3. **VTX выкл./вкл.** После устойчивого фикса VTX на минимальной, затем на рабочих мощностях (25 / 200 / 400 мВт или режимы цифрового модуля), по 2 минуты на ступень: спутники, PDOP, средний C/N0 из NAV-SAT (u-center). Затем холодный старт с включённым VTX. Критерий: на рабочей мощности спутников меньше не более чем на 2, C/N0 ниже не больше чем на 3 дБ, холодный старт не дольше 90 с. Иначе переносить модуль и повторять.
4. **Наклон.** Наклонить аппарат на 45° вперёд, назад и вбок. Число спутников в фиксе не падает больше чем на 2.
5. **Дом.** Арм без пропеллеров (`bf-arming-safety`): два «коротко-длинно», в OSD стрелка и 0 м. Дизарм, перенос на 20 м: при `gps_set_home_point_once = OFF` стрелка показывает `-`, после нового арма дом — в новой точке. Координаты в OSD видны.
6. **Первый полёт с GPS** (Rescue выключен): взлёт, прямой пролёт 50 м быстрее 2 м/с. Стрелка смотрит домой в пределах сектора символа (документация: за 5–10 с или 50–80 м), на обратном пути дистанция убывает. Прервать полёт, если стрелка не выровнялась после 80 м, спутников меньше 8, появилось `RESCUE N/A` или скорость на висении в штиль больше 1 м/с.

Самопроверка: лабораторная выполнена, когда:
- **Расчёт (без железа):** `gps_lab.py` запущен. Реальная запись M8030 дала совпадение DOP с NAV-DOP не хуже 0.03 (модель «одни часы»). Таблица шести синтетических сценариев воспроизведена, и для каждого ты записал, чем он отличается от M10 по умолчанию, и сверил запись с разбором под таблицей. Выбрана скорость UART с загрузкой меньше 50 % (по выводу шага 3 это 38400 и выше).
- **Железо:** `status` с версией модуля записан. Холодный старт засечён (время фикса и 8 спутников) и укладывается в 60 с. 10-минутная запись `.ubx` своего модуля прогнана через `gps_lab.py`, и числа проходят критерий пункта 2: PDOP ≤ 1.5, v95 ≤ 20 см/с, R95 ≤ 3 м. Таблица «VTX выкл./по ступеням мощности» заполнена и проходит критерий пункта 3 (спутников меньше не более чем на 2, C/N0 ниже не больше чем на 3 дБ), проверены наклон 45° и дом при арме. `diff all` после настройки сохранён рядом с записью `.ubx`.

**Эталон для самопроверки.** Расчёт верен, если строки таблицы сценариев совпадают с модулем: «GPS only» — 10 спутников и PDOP 1.57, «M10 default» — 28 и 0.87, «VTX noise +10 dB» — `trk` 28, но в решении 9 и PDOP 4.70. Правильное объяснение отличий — в разборе под таблицей: число созвездий меняет геометрию и R95, но не TTFF (25–29 с задаёт декодирование эфемерид); шум VTX оставляет слежение, но не даёт скачать эфемериды слабых спутников. DOP модели отличается от NAV-DOP на 5–23 % — посчитаны «часы на каждую систему» вместо одних часов. На железе R95 по короткой записи выглядит лучше 1 м — это не точность: записано меньше 10 минут, ошибка меняется минутами.

## diagnostics
- **Симптом:** `status` → `GPS: NOT CONNECTED` или `NOT ENABLED`
  - Возможная причина: `feature GPS` выключена; TX/RX не крест-накрест; модуль без питания (на USB некоторые платы не питают GPS-пад); функция GPS не на том UART; SoftSerial.
  - Что сделать: `feature GPS`, `serial` с функцией 2 (GPS) на нужном UART, прозвонка, питание от АКБ без пропеллеров.
- **Симптом:** не армится, в `status` флаг `GPS`
  - Возможная причина: Rescue настроен (процедура или режим), а fix нет или спутников меньше `gps_rescue_min_sats`; либо Rescue настроен при выключенной `feature GPS` — тогда флаг вечный.
  - Что сделать: ждать под открытым небом, смотреть OSD и вкладку GPS; не снижать `gps_rescue_min_sats` ниже 8 и не включать `gps_rescue_allow_arming_without_fix` ради арма.
  - Последствия: арм без дома даёт `RESCUE N/A` — при failsafe аппарат не полетит домой.
- **Симптом:** спутников мало или фикс долгий, при выключенном VTX всё нормально (вопрос № 17)
  - Возможная причина: помехи от VTX или цифрового модуля поднимают шумовой порог; холодный старт особенно чувствителен (декодирование эфемерид).
  - Что сделать: стендовый тест «VTX выкл./вкл.», модуль дальше от антенны VTX и выше, антенна в небо, VTX включать после фикса, батарейка или конденсатор на V_BCKP для горячего старта.
- **Симптом:** M10 не даёт 10 Гц, интервал NAV в `debug_mode = GPS_CONNECTION` больше 100 мс
  - Возможная причина: заводской набор GPS+GAL+BDS у MAX-M10S ограничен 3 Гц (даташит).
  - Что сделать: `gps_update_rate_hz = 3`, или через u-center набор GPS+GAL (10 Гц) с сохранением в BBR.
- **Симптом:** M10 на Betaflight 4.4 и более ранних версиях работает плохо или «как попало»
  - Возможная причина: 4.4 не знает M10 и шлёт только старые CFG-сообщения; документация вкладки GPS требует 4.5 для M10.
  - Что сделать: обновиться до 2025.12 (или хотя бы до 4.5, если плата не поддерживается новее).
- **Симптом:** M10 с прошивкой ROM SPG 5.00 (MON-VER) теряет точность при сильном сигнале
  - Возможная причина: известное ограничение 14 из release notes 5.00 — «balanced» режим питания. Betaflight (проверено на 4.5.6) шлёт M9+ только CFG-PM-OPERATEMODE = FULL, а CFG-PMS — только модулям M8.
  - Что сделать: u-center → CFG-PMS full power с сохранением в BBR, или модуль с SPG 5.10.
- **Симптом:** стрелка дома показывает не туда сразу после взлёта
  - Возможная причина: компаса нет, курс по GPS ещё не выучен (нужна скорость больше 1 м/с, нос наклонён вперёд, крен меньше 12°, стик рыскания в центре).
  - Что сделать: прямой пролёт 30–50 м на скорости больше 2 м/с, потом проверить стрелку; если не выровнялась — сесть, перезагрузить.
- **Симптом:** дом оказался в точке посадки, а не взлёта
  - Возможная причина: `gps_set_home_point_once = OFF` и дизарм в поле — новый арм перезаписал дом.
  - Что сделать: `gps_set_home_point_once = ON` для полётов с промежуточными посадками, первый арм — на месте старта.
- **Симптом:** `gps_ublox_use_galileo = ON`, но спутников Galileo (E) на вкладке GPS нет — или они есть при OFF
  - Возможная причина: Galileo меняется только через CFG-GNSS; шаг пропускается при SBAS ≠ NONE и Galileo OFF; M10 документирует только VALSET.
  - Что сделать: проверить список спутников на вкладке GPS; при необходимости задать CFG-SIGNAL в u-center и сохранить в BBR.
- **Симптом:** потеря GPS в полёте, `status` показывает скорость 115200, в логах интервалы NAV скачут
  - Возможная причина: потери кадров на 115200 (документация).
  - Что сделать: `serial … 57600 …` для GPS, проверить загрузку по шагу 3.

## checklist
- Модуль M8 или M10, версия прошивки и набор созвездий известны (MON-VER, MON-GNSS)
- Питание по маркировке платы модуля, UART крест-накрест, аппаратный UART, `feature GPS`
- Антенна в небо, модуль на мачте или сверху, дальше от VTX и силовых проводов; тест «VTX выкл./вкл.» пройден
- `status` → `connected, configured`, скорость 57600, частота не выше потолка модуля
- Знаю расхождения документации и кода (проверены на 4.5.6): модель на первом фиксе, SBAS NONE, низкие спутники — порог 4, `gps_auto_baud` ни на что не влияет
- `gps_rescue_min_sats` ≥ 8, `gps_rescue_allow_arming_without_fix = OFF`, дом записывается при арме (два «коротко-длинно»)
- В OSD: спутники с PDOP, стрелка и дистанция до дома, координаты, предупреждения
- Без компаса: прямой пролёт 30–50 м перед тем, как верить стрелке
- GPS Rescue настроен и проверен по `bf-failsafe`

## references
- Betaflight io/gps.c — автомат конфигурации u-blox, NAV-PVT, дом, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/io/gps.c | primary | A
- Betaflight pg/gps.c — умолчания gpsConfig, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/pg/gps.c | primary | A
- Betaflight cli/settings.c — переменные gps_*, mag_*, osd_gps_*, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/cli/settings.c | primary | A
- Betaflight cli/cli.c — status (строка GPS), gpspassthrough, serial, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/cli/cli.c | primary | A
- Betaflight fc/core.c — флаг арма GPS, сигналы арма, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/fc/core.c | primary | A
- Betaflight flight/gps_rescue.c — порог GPS_MIN_SAT_COUNT, LOWSATS, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/gps_rescue.c | primary | A
- Betaflight flight/imu.c — курс по GPS без компаса, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/imu.c | primary | A
- Betaflight flight/position.c — доверие GPS по PDOP, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/position.c | primary | A
- Betaflight osd/osd_elements.c — элементы спутников, скорости, дома, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/osd/osd_elements.c | primary | A
- Betaflight sensors/compass.c — mag_hardware, калибровка, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/sensors/compass.c | primary | A
- Betaflight io/gps.c, тег 2025.12.5 (230400, GPS_VIRTUAL) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/io/gps.c | primary | A
- Betaflight cli/settings.c, тег 2025.12.5 (gps_*, mag_declination, ap_*, pos_hold_*) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/cli/settings.c | primary | A
- Betaflight cli/settings.c, 4.4-maintenance (gps_ublox_mode) | https://raw.githubusercontent.com/betaflight/betaflight/4.4-maintenance/src/main/cli/settings.c | primary | A
- Betaflight docs — GPS guide (u-center, модели, SBAS) | https://betaflight.com/docs/wiki/guides/current/Gps | primary | B
- Betaflight docs — GPS Rescue (проверка модуля, курс без компаса, компас) | https://betaflight.com/docs/wiki/guides/current/GPS-Rescue | primary | B
- Betaflight App — GPS tab (M10 требует 4.5, PDOP) | https://betaflight.com/docs/wiki/app/gps-tab | primary | B
- u-blox MAX-M10S Data sheet UBX-20035208 (созвездия, TTFF, частота, питание) | https://content.u-blox.com/sites/default/files/MAX-M10S_DataSheet_UBX-20035208.pdf | primary | A
- u-blox M10 SPG 5.10 Interface Description UBX-21035062 (CFG-SIGNAL, DYNMODEL, PM) | https://cdn.sparkfun.com/assets/f/1/2/9/e/u-blox-M10-SPG-5.10_InterfaceDescription_UBX-21035062.pdf | primary | A
- u-blox MAX-M10S Integration manual UBX-20053088 (эфемериды 4 ч, V_BCKP, слои RAM/BBR) | https://cdn.sparkfun.com/assets/5/c/a/0/b/MAX-M10S_IntegrationManual_UBX-20053088.pdf | primary | A
- u-blox M10 ROM 5.00 Release notes UBX-20050981 (известные ограничения) | https://cdn.sparkfun.com/assets/2/0/d/7/4/u-blox_M10_ROM_5.00_ReleaseNotes_UBX-20050981.pdf | primary | A
- u-blox NEO-M8 FW3 Data sheet UBX-15031086 | https://www.mouser.lt/datasheet/3/3699/1/NEO_M8_FW3_DataSheet_UBX_15031086.pdf | primary | A
- u-blox SAM-M10Q Data sheet UBX-22013293 (земляная плоскость 50 × 50 мм, пусковой ток) | https://cdn.sparkfun.com/assets/1/1/d/f/4/SAM-M10Q_DataSheet_UBX-22013293.pdf | primary | A
- pyubx2 test data — реальная запись u-blox M8030 (pygpsdata-MIXED.log) | https://raw.githubusercontent.com/semuconsulting/pyubx2/master/tests/pygpsdata-MIXED.log | secondary | B

## notes
Имена, умолчания и диапазоны сверены с таблицей настроек и умолчаниями 2025.12.5; поведение автоконфигурации и парсера взято из исходника 4.5.6 и проверено по ходу кода, а не по названиям. Цифры модулей — из даташитов u-blox. Синтетические логи — модель с допущениями из заголовка вывода: их числа показывают направление эффекта, а не свойства конкретного модуля. Реальная проверка — одна чужая запись M8030 длиной 38 с. Не проверено: отвечает ли M10 на опрос UBX-CFG-GNSS, то есть работает ли `gps_ublox_use_galileo` на M10; что делает MAX-M10S, если запросить 10 Гц сверх потолка 3 Гц; совпадает ли CFG-PM-OPERATEMODE = FULL с «full power» CFG-PMS на ROM 5.00. Время автоконфигурации около 6 с — оценка по константам `gps.c`, без измерения. Пороги приёмлемости на стенде (C/N0 −3 дБ, ±2 спутника) — правило курса, не норма производителя.
