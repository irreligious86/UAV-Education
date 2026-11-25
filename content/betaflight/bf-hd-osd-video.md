---
id: bf-hd-osd-video
title: "Цифровое видео на Betaflight: DJI, Walksnail, HDZero — подключение, OSD и настройка"
level: L2
readingTime: 50 мин
firmware: Betaflight 2025.12 (сверено с 2025.12.5); лабораторная снята на исходнике 4.5.6 · INAV 9.1 (сверено с 9.1.0) · ArduPilot 4.7 (сверено с 4.7.2)
status: published
added: 2026-11-14
tags:
  - цифровое видео
  - HD OSD
  - MSP DisplayPort
  - DJI
  - Walksnail
  - HDZero
related:
  - link-digital-video
  - link-vtx
  - bf-modes-osd
  - bf-ports
  - bf-cli
  - el-power-design
  - bf-setup-scratch
  - inav-setup-scratch
  - ap-setup-scratch
next: []
---

## summary
Обзор четырёх семейств цифрового видео — в `link-digital-video`, VTX-таблицы аналога — в `link-vtx`. Здесь — как подключить конкретный воздушный модуль к полётнику Betaflight 2025.12, чтобы он не сгорел, OSD появился в очках, а запись и мощность были настроены. Для DJI (O3, O4, старые Air Unit и Vista), Walksnail Avatar и HDZero: питание, разводка, маска порта, `osd_displayport_device`, `vcd_video_system`, канва, шрифты и загрузочный логотип (аналог и HD), сторона очков, порядок включения, нагрев, запись, мощность, задержка и аналоги в INAV и ArduPilot. Лабораторная — Python-калькулятор по логике прошивки (маски портов, проверка `isSerialConfigValid()`, перенос элементов OSD между канвами по `osd.h`), затем стол: прозвонка, вентилятор, линк, OSD, запись.

## theory
### Кто что делает
В цифровой системе OSD рисуют очки. Полётник только сообщает, какой символ и в какой клетке сетки нарисовать: команды MSP DisplayPort (`MSP_DP_WRITE_STRING`, `MSP_DP_DRAW_SCREEN`, heartbeat) идут по одному UART. По тому же UART воздушный модуль может управлять VTX по MSP (канал, мощность, pit mode) и сообщает полётнику размер своей сетки — канвы. Поэтому для HD-видео нужны три вещи: правильная разводка UART, правильная маска функций порта и HD-режим OSD. Если не хватает хотя бы одной, получается главный вопрос форумов: видео есть, OSD нет.

### Три системы: питание и провода
Цифры взяты из документации производителей (ссылки в references). Питание — главное, что отличает модели внутри одной системы.

| Система / модель | Питание по спецификации | Откуда брать | UART (провод модуля → пад FC) | RC из очков | Задержка (заявлено) |
|---|---|---|---|---|---|
| DJI FPV Air Unit (2019) | 7.4–17.6 В, 4–9 Вт | VBAT 2S–4S | MSP по UART | DJI-пульт → S.Bus | < 28 мс 720p/120 |
| Caddx Vista | 7.4–26.4 В | VBAT 2S–6S | как у Air Unit | то же | 21–28 мс 720p/120 |
| DJI O3 Air Unit | 7.4–26.4 В (2S–6S) | VBAT или BEC | белый UART_RX → TX, серый UART_TX → RX, чёрный и коричневый — земли | жёлтый DJI HDL/S.Bus → S.Bus-пад | < 28 мс 810p/120 (Goggles V2), 30 мс 1080p/100 (Goggles 2) |
| DJI O4 Air Unit | 3.7–13.2 В, BEC ≥ 10 Вт | только BEC (5 В/2 А) | те же цвета | то же | от 20 мс 1080p/100 (Goggles 3) |
| DJI O4 Air Unit Pro | 7.4–26.4 В, BEC ≥ 13.5 Вт | VBAT или BEC 9 В/1.5 А | те же цвета | то же | от 15 мс 1080p/100 (Goggles 3) |
| Walksnail Avatar HD Pro | 6–25.2 В | VBAT (6S — с конденсатором 50 В/47 мкФ) | RX модуля → TX, TX модуля → RX | нет, отдельный приёмник | в среднем 22 мс |
| Walksnail Avatar Mini V3 | 3.1–13 В (1–3S) | 4S и выше — только через BEC | то же | нет | в среднем 22 мс |
| HDZero Race V3 | 4–12 В, 5–6 Вт | BEC 5–12 В | белый TX → RX, жёлтый RX → TX | нет | модель: ≈ 3 мс + период кадра (14 мс при 90 к/с) |
| HDZero Freestyle V2 | 7–25 В, 6–15 Вт | BEC рекомендуется | жёлтый RX → TX, белый TX → RX | нет | то же |

Правила, которые следуют из таблицы:
- Модуль с верхним пределом 13 В от 4S напрямую не питать: у заряженного 3S LiHV 13.05 В, у 4S 16.8 В. HDZero прямо пишет, что, кроме Freestyle второй партии и новее, их VTX не рассчитаны на 6S VBAT, и рекомендует BEC: он гасит выбросы напряжения, которые убивают VTX. Площадка «10V/12V HD» на полётнике обычно подходит для любого модуля из таблицы, но её ток надо сверить с 13.5 Вт O4 Pro и 15 Вт Freestyle V2. Расчёт ветки — в `el-power-design`.
- TX↔RX всегда крест-накрест, логика 3.3 В. У DJI два провода земли: силовая и сигнальная. Обе идут на полётник.
- Управление с очков есть только у DJI. Жёлтый провод S.Bus подключается на S.Bus-пад полётника, `serialrx_provider = SBUS`, на F4 — пад с инвертором (`bf-ports`). Если управление идёт по ELRS, жёлтый провод не подключают, а приёмник ставят на свой UART с CRSF.
- SoftSerial для DisplayPort не годится: HDZero это прямо запрещает, а Betaflight вырезает MSP с SoftSerial-портов при проверке конфига (см. ниже).

{{diagram:bf-hd-wiring|Разобранный пример: ELRS на UART1, воздушный модуль на UART4 с маской 131073 = MSP + VTX_MSP; питание модуля по его спецификации — от VBAT или только от BEC.}}

### Сторона Betaflight: маска порта
Вкладка Ports хранит для каждого порта строку `serial <id> <маска> <msp_baud> <gps_baud> <telemetry_baud> <blackbox_baud>` (`id`: 0 = UART1 … 9 = UART10, 20 = USB VCP, 30/31 = SoftSerial, 40 = LPUART1). Маска — сумма битов `serialPortFunction_e` из `io/serial.h`. Для видео важны четыре бита: MSP = 1, VTX SmartAudio = 2048, VTX Tramp = 8192, **VTX_MSP = 131072** (`1 << 17`). Пункт Peripherals «VTX (MSP + DisplayPort)» вместе с включённым MSP даёт маску **131073**. Значение 131072 из аудита курса по исходнику (4.5 и 2025.12) подтверждено, но это один бит VTX_MSP. На порту должно стоять 131073.

Что прошивка делает с маской при загрузке (`io/serial.c`, `config/config.c`; логика одинакова в 4.5 и 2025.12):
1. `isSerialConfigValid()`: VTX_MSP в одиночку недопустим, только вместе с MSP или Serial RX. MSP может быть не больше чем на 3 портах, на VCP MSP обязателен. MSP и Serial RX на SoftSerial молча снимаются. При любом нарушении **весь** конфиг портов сбрасывается к умолчаниям платы, и приёмник «пропадает» вместе с OSD.
2. Порт для DisplayPort ищется так: первый порт, кроме VCP, у которого одновременно стоят MSP и VTX_MSP. Отдельной переменной для выбора порта больше нет. `displayport_msp_serial` существовала в 4.2–4.3 и удалена в 4.4 (в `settings.c` веток 4.4, 4.5 и 2025.12 её нет). Аудит называл её параметром 4.4 — это неточность. Инструкции DJI O3/O4 и старая quickstart Walksnail до сих пор её показывают с оговоркой «для 4.3». И на 4.5, и на 2025.12 команда `set displayport_msp_serial` вернёт ошибку `INVALID NAME`.
3. Скорость — поле `msp_baud`, 115200. HDZero поддерживает 115200 и 230400 (Race V3 — только 115200), DJI и Walksnail в инструкциях указывают 115200.

### Режим HD и канва
- `vcd_video_system = HD`. При HD `fc/init.c` берёт MSP-дисплей независимо от `osd_displayport_device`. Сам OSD должен быть включён (`feature OSD`, тумблер OSD в Configuration).
- `osd_displayport_device = MSP` (варианты `NONE`, `AUTO`, `MAX7456`, `MSP`, `FRSKYOSD`).
- Умолчания зависят от опций Cloud Build. Если в сборке есть «OSD (HD)» (`USE_OSD_HD`), то `vcd_video_system = HD`, `osd_displayport_device = MSP`, канва 53×20 (`OSD_HD_COLS/ROWS` в `osd.h`). Только «OSD (SD)» — `AUTO` и 30×16. В сборке без HD-опции включить HD нельзя: `displayport_msp.c` откатывает `HD` на `AUTO`. Если в сборке обе опции, умолчание — HD, и для аналоговой камеры надо вручную ставить `PAL`/`NTSC`/`AUTO`.
- Канву сообщают очки. Когда модуль присылает `MSP_SET_OSD_CANVAS`, полётник записывает `osd_canvas_width/height`. Если до этого он был не в HD/MSP, то сам переключается, сохраняет конфиг и **перезагружается**. Одна лишняя перезагрузка при первом подключении — норма. Прошивка HDZero VTX отправляет Betaflight режим `HD_5018`, то есть 50×18. Для DJI и Walksnail по умолчанию остаётся 53×20; реальный размер смотри в `get osd_canvas` после линка.
- Позиция элемента — 16 бит (`osd.h`): x — биты 0–4 плюс бит 10 (x до 63), y — биты 5–9, профили OSD 1–3 — биты 11–13, тип — биты 14–15. `OSD_POS(x,y) = (x & 31) | ((x << 5) & 0x400) | ((y & 31) << 5)`. При старте `osdInit()` прижимает элементы, вылезшие за канву, к последнему столбцу или строке. Ничего не переносит пропорционально, поэтому соседние элементы могут лечь друг на друга (шаг 3 практики).
- Шрифты: `displayport_msp_fonts` — четыре номера страниц шрифта для уровней важности (обычный, info, warning, critical), по умолчанию `0,1,2,3`. Так прошивка (4.5 и 2025.12) красит предупреждения, если в очках четырёхстраничный цветной шрифт Betaflight. С одностраничным шрифтом часть элементов пропадёт — тогда `set displayport_msp_fonts = 0,0,0,0` (документация msp-osd). В 4.3 это была `displayport_msp_attrs`.
- `displayport_msp_col_adjust/row_adjust` работают только в SD-режиме MSP-дисплея, при `HD` их не читают.

### Загрузочный логотип и шрифт: что хранит чип OSD, а что — очки
**Что рисует прошивка (4.5 и 2025.12).** При старте OSD `osdCompleteInitialization()` (`osd/osd.c`) чистит экран и вызывает `osdDrawLogo()`: 24 × 4 символа подряд, начиная с кода 160 (0xA0) до `SYM_END_OF_FONT` 255 (0xFF), с левым верхним углом в (`середина − 12`, `середина − 5`) канвы. Под логотипом — версия прошивки и, если собран CMS, подсказка входа в меню «MENU:THR MID / + YAW LEFT / + PITCH UP». Если в полётнике есть часы (RTC), ниже выводится строка даты и времени. Экран держится 4 с; газ или тангаж вверх (> 1750 мкс) в дизарме, а также тумблер режима переворота (FLIP OVER AFTER CRASH, в 2025.12 — CRASHFLIP) убирают его раньше. Логотипа как картинки в прошивке нет: это 96 символов шрифта, и в очках видно то, что лежит в ячейках 160–255 того шрифта, которым рисуют.

**Аналог: MAX7456 и совместимые.** Символ — 12 × 18 пикселей по 2 бита (`OSD_CHAR_WIDTH/HEIGHT`, `drivers/osd.h`), 54 значимых байта из 64 в записи. Весь шрифт, 256 символов, лежит в энергонезависимой памяти (NVM) самого чипа OSD, а не во flash полётника. Прошивка пишет туда только по команде `MSP_OSD_CHAR_WRITE` (`max7456WriteNvm()` в `drivers/max7456.c`; других вызовов в исходнике нет), поэтому перепрошивка полётника шрифт и логотип не трогает. Логотип 24 × 4 символа — картинка 288 × 72 пикселя.

**Betaflight Configurator 10.10, Font Manager.** Шрифт — файл `.mcm`: пресеты default, bold, large, extra_large, betaflight, digital, clarity, vision, impact, impact_mini или свой файл. Кнопка «Select custom image…» принимает PNG или BMP ровно 288 × 72 px из трёх цветов: 0,255,0 — зелёный, становится прозрачным (код пикселя 01), 0,0,0 — чёрный (00), 255,255,255 — белый (10). На любом другом пикселе, в том числе от сглаживания при экспорте, приложение отказывает и пишет его координаты (`src/js/LogoManager.js`). Картинка режется на 96 клеток и подставляется в символы 160–255 шрифта, **загруженного в приложение**. В чип она попадает только кнопкой «Upload Font»: та пишет все 256 символов по `MSP_OSD_CHAR_WRITE` и перезагружает полётник (`FONT.upload()` в `src/js/tabs/osd.js`). Отсюда правило: логотип живёт в памяти чипа как часть шрифта, и следующая заливка любого другого шрифта вернёт в 160–255 логотип из того шрифта. Порядок: выбрать шрифт → подставить логотип → Upload Font; ориентир курса — свой `.mcm` с логотипом сохрани рядом с `diff all` аппарата. Бери приложение той же версии, что прошивка: Configurator 10.10 рассчитан на API до 1.46 (4.5), а 2025.12 сообщает API 1.47 — для неё Betaflight App 2025.12, где Font Manager по исходнику я не проверял. Font Manager активен, только если OSD-устройство — MAX7456 или FrSky OSD и оно обнаружено (флаги `MSP_OSD_CONFIG` в `msp/msp.c`). При `osd_displayport_device = MSP` кнопка серая.

{{diagram:bf-osd-logo-grid|Логотип — это символы шрифта 160–255, 24 × 4 клетки по 12 × 18 px; Upload Font переписывает все 256 символов, поэтому новый шрифт приносит свой логотип.}}

**HD: DJI, Walksnail, HDZero и другие MSP DisplayPort.** Полётник отправляет те же коды 160–255, версию и подсказку CMS обычными символами по MSP, а картинку рисует шрифт очков (или VTX — где система держит шрифт, зависит от неё). Залить шрифт в HD-систему из Betaflight нельзя: в 4.5.3 у MSP-дисплея нет функции записи символа, а в 2025.12 она есть только под опцией `USE_MSP_DISPLAYPORT_FONT` (команда `MSP_DP_FONTCHAR_WRITE` = 7, в комментарии «New OSD chip works over MSP»), которую в исходниках 2025.12.5 не определяет ни `common_pre.h`, ни один таргет (это вывод по дереву исходников; опции Cloud Build не проверены); флаг связан с чипом AIRBOT THEIA OSD (`OSD_FLAGS_OSD_HARDWARE_AIRBOT_THEIA_OSD` в `msp/msp.c`). Поэтому на HD свой логотип — это правка шрифта на стороне очков по инструкции производителя. **Не проверено по исходникам Betaflight:** форматы и способ замены шрифта у DJI O3/O4, Walksnail, HDZero и WTFOS; есть ли в их стоковых шрифтах логотип Betaflight в 160–255; возможна ли своя картинка на стоковой прошивке DJI.

**Логотип при арме.** `osd_logo_on_arming`: OFF (по умолчанию), ON — при каждом арме, FIRST_ARMING — только при первом арме после включения. `osd_logo_on_arming_duration` — в десятых долях секунды, 5–50 (0.5–5 с), по умолчанию 5 = 0.5 с. Без логотипа надпись ARMED висит те же 0.5 с. Пока висит экран арма, остальные элементы OSD не рисуются: пока не наступит `resumeRefreshAt`, `osdProcessStats2()` ничего не делает, а автомат `osdUpdate()` пропускает отрисовку элементов (`osd/osd.c`). В 2025.12 добавлен `osd_arming_logo` (0–3, по умолчанию 0): уровень важности, которым рисуется логотип при арме. На MSP-дисплее он через `displayport_msp_fonts` выбирает страницу шрифта очков, поэтому в четырёхстраничном HD-шрифте можно показать при арме другую картинку со страницы 1–3 (есть ли она в конкретном шрифте, по исходникам не проверить); MAX7456 уровень игнорирует. Ориентир курса: на гоночном аппарате — OFF, на остальных FIRST_ARMING с 10–15 (1–1.5 с): на первом арме видно, тот ли аппарат и та ли прошивка, а дольше слепой экран на взлёте не нужен.

### Справочник: переменные и команды (2025.12; имена, умолчания и диапазоны те же, что в 4.5)
| Переменная / команда | Умолчание | Диапазон | Смысл |
|---|---|---|---|
| `serial <id> 131073 115200 …` | по плате | маска 32 бит | MSP + VTX_MSP: порт DisplayPort |
| `vcd_video_system` | `HD` при OSD (HD) в сборке, иначе `AUTO` | AUTO, PAL, NTSC, HD | HD = MSP-дисплей с канвой |
| `osd_displayport_device` | `MSP` при OSD (HD), иначе `AUTO` | NONE, AUTO, MAX7456, MSP, FRSKYOSD | устройство OSD |
| `osd_canvas_width` / `osd_canvas_height` | 53 / 20 (HD), 30 / 16 (SD) | 0–63 / 0–31 | сетка; переписывается очками |
| `displayport_msp_fonts` | `0,1,2,3` | 4 значения | страница шрифта по уровню важности |
| `displayport_msp_use_device_blink` | OFF | OFF, ON | мигание делает очко, а не FC |
| `displayport_msp_col_adjust` / `row_adjust` | 0 / 0 | −6…0 / −3…0 | только SD-режим MSP |
| `osd_framerate_hz` | 12 | 1–60 | частота обновления OSD |
| `osd_logo_on_arming` | OFF | OFF, ON, FIRST_ARMING | логотип на экране арма |
| `osd_logo_on_arming_duration` | 5 (0.5 с) | 5–50, в 0.1 с | сколько держать логотип при арме |
| `osd_arming_logo` (только 2025.12) | 0 | 0–3 | уровень важности (страница шрифта через `displayport_msp_fonts`) для логотипа при арме |
| `osd_*_pos` | центр, скрыт | 0–65535 | `(x & 31) + (y<<5) + ((x>>5)<<10) + (профили<<11)` |
| `osd_sys_*_pos` (`goggle_voltage`, `vtx_voltage`, `vtx_temp`, `bitrate`, `delay`, `lq`, `goggle_dvr`, `vtx_dvr`, `fan_speed`, `warnings`, `distance`) | скрыт | 0–65535 | элементы, которые рисуют сами очки (`USE_MSP_DISPLAYPORT`) |
| `vtx_power` | 0 | индекс таблицы | мощность MSP-VTX (HDZero) |
| `vtx_low_power_disarm` | OFF | OFF, ON, UNTIL_FIRST_ARM | при дизарме MSP-VTX получает индекс 1 (`vtx_msp.c`) |
| `status` | — | — | строка `OSD: MSP (53 x 20)` — тип и размер дисплея |
| `vtx_info` | — | — | что сообщил VTX |

`vcd_h_offset`/`vcd_v_offset` относятся только к аналоговому MAX7456, к HD отношения не имеют. Для `vtx_low_power_disarm` аудит писал, что к цифре это не относится. Это не так для VTX, управляемых по MSP (и в 4.5, и в 2025.12): `prepareMspFrame()` отправляет индекс мощности 1, пока аппарат не армлен, но только когда загружена VTX-таблица (иначе статус MSP-VTX не становится READY). HDZero заполняет таблицу сам. Есть ли MSP-VTX у DJI и Walksnail, зависит от прошивки модуля — проверяется вкладкой Video Transmitter.

### Сторона очков
- **DJI O3/O4.** По инструкции DJI режим Canvas работает с Betaflight 4.3+. Набор элементов и их места задаются в Betaflight, в меню очков отдельной раскладки нет. Мощность, канал, полоса и запись (`Record With`, `Auto Record on Takeoff`) настраиваются в меню очков, VTX-таблицы аналога не нужны. Порядок линковки: сначала модуль с очками, потом пульт.
- **Старые DJI FPV Air Unit/Vista.** Стоковая прошивка рисует собственный OSD DJI из данных MSP: до 24 элементов, прошивка v01.00.02.00 (2019). Порт — только MSP (маска 1). Полный OSD Betaflight через DisplayPort даёт неофициальный WTFOS с пакетом msp-osd. Его ставят на очки и на каждый модуль, а полётник настраивают как HD (маска 131073, `vcd_video_system = HD`).
- **Walksnail Avatar.** OSD — «Canvas mode». Полётник настраивается так же: Peripherals «VTX (MSP + DisplayPort)», `osd_displayport_device = MSP`, `vcd_video_system = HD`. Режим standby снижает мощность, пока аппарат не армлен.
- **HDZero.** VTX сам заполняет VTX-таблицу полётника. Мощность и канал задаются из Betaflight (вкладка Video Transmitter, CMS) или из меню VTX: `LP_MODE` (25 мВт до арма), `PIT_MODE` (P1MW = 0.1 мВт, 0MW), стик-команды выхода из 0 мВт. Режим `VTX PIT MODE` на тумблере (`bf-modes-osd`) и `vtx_low_power_disarm` доходят до VTX по тому же MSP. Синий светодиод мигает трижды после загрузки, если обмен MSP обнаружен. Записи на VTX нет, DVR — в очках.

### Порядок включения, нагрев, запись
- Антенну подключать до питания (Walksnail прямо запрещает включать без антенны).
- Сначала очки, потом АКБ аппарата. При подключении по USB сначала АКБ, потом USB: HDZero предупреждает, что VTX может не загрузиться, если АКБ подключить к полётнику, уже подключённому к ПК.
- Нагрев. DJI после включения держит модуль в режиме пониженной мощности до взлёта или начала записи, а при перегреве на земле отключает его. В полёте при перегреве останавливается запись, а при продолжении нагрева снижается качество. Время на столе от холодного старта при 25 °C без обдува: O4 Pro около 20 мин, O4 около 2.5 мин. Walksnail при перегреве попеременно мигает красным и зелёным. HDZero мигает тремя короткими: это защита от перегрева, у Freestyle при этом отключается RF до арма или переподключения питания. Все три производителя пишут: на столе нужен вентилятор. P1MW у HDZero тоже греет, для паузы — 0MW.
- Запись. O3 — во встроенную память модуля. O4 — по настройке `Record With` в очках, и запись не стартует, пока модуль на земле в режиме пониженной мощности. Walksnail — во встроенную память модуля (8 ГБ у Mini V3, 32 ГБ в комплекте HD Pro), 1080p/720p. HDZero — только DVR очков, запись того, что пришло по радио.

### Мощность и закон
EIRP по спецификациям. DJI O3/O4 Pro: FCC < 33 дБм (≈ 2 Вт), CE < 14 дБм (25 мВт), SRRC < 30 дБм. Walksnail: FCC < 30 дБм (Mini V3 — < 27 дБм), CE < 14 дБм, MIC < 25 дБм, а каналы 1, 2, 6, 7 в FCC-регионах попадают в любительский диапазон. HDZero: 25/200 мВт, 500 мВт и 1 Вт — только по любительской лицензии и отдельной прошивке. Режим (FCC/CE) выбирают в очках по правилам своей страны. В ЕС разрешён только CE, < 14 дБм. Больше мощности — больше нагрева и помех соседям, а дальности добавляет мало (`rf-link-budget`).

### INAV и ArduPilot — коротко
| | Betaflight 2025.12 | INAV 9.1 | ArduPilot 4.7 |
|---|---|---|---|
| Функция порта | VTX (MSP + DisplayPort), маска 131073 | MSP DisplayPort (`FUNCTION_MSP_OSD` = 1 << 25) | `SERIALn_PROTOCOL = 42` (DisplayPort); 33 — старый «DJI FPV» |
| Тип OSD | `osd_displayport_device = MSP` | выбор порта | `OSD_TYPE = 5` (MSP_DISPLAYPORT); 3 — MSP |
| Сетка | `vcd_video_system = HD`, канва от очков | `osd_video_system` = HDZERO, DJIWTF, AVATAR, BF43COMPAT, BFHDCOMPAT, DJI_NATIVE | задаёт полётник, на каждый экран: `OSDn_TXT_RES` 0 — 30×16 (по умолчанию: HD-очки покажут SD-сетку), 1 — 50×18, 2 — 60×22; `MSP_OPTIONS` бит 2 — символы Betaflight, бит 3 — INAV (бит 0 — только для протокола 33); полная таблица по системам — `ap-osd-video` |
| Скорость | 115200 | 115200 | `SERIALn_BAUD = 115` |

Какое значение INAV 9.1 (в 8.0.1 так же) ставить под систему: HDZero — HDZERO (50×18), Walksnail — AVATAR (53×20), DJI O4 и очки с INAV-шрифтом — DJI_NATIVE (53×20, в очках тип OSD «INAV»), DJI O3 на стоковой прошивке — BFHDCOMPAT (53×20, шрифт Betaflight, часть значков «?»), Air Unit/Vista под WTFOS — DJIWTF (60×22), старый DJI без WTFOS — BF43COMPAT (30×16).

Номера битов в масках у прошивок разные: 131072 в INAV — это `FUNCTION_VTX_FFPV`. Строки `serial` между прошивками не копируют.

### Чем отличается 4.5 и что дальше
Имена и диапазоны всех переменных из справочника в 4.5 и 2025.12 одинаковы. В 2025.12 `diff` пишет порты по именам (`serial UART4 131073 …`; в 4.5 — номерами, `serial 3 131073 …`, и 2025.12 такие строки принимает), добавлен бит `FUNCTION_GIMBAL` = 262144, а тип OSD (аналоговый или HD) — отдельная опция Cloud Build: без `USE_OSD_HD` в сборке DisplayPort не заработает при любой маске. В ветке разработки 2026.12 порты назначаются переменными `*_uart` (`msp_uart_2 = UART4`). Это ещё не выпуск.

### Место в системе

- **Получает:** питание модуля от VBAT или BEC по его спецификации (`el-power-design`); свободный аппаратный UART и маску MSP + VTX_MSP (`bf-ports`); опцию «OSD (HD)» в сборке (`bf-custom`); размер канвы — от очков.
- **Отдаёт:** команды MSP DisplayPort — очкам, которые рисуют OSD (`link-digital-video`, `bf-modes-osd`); индекс мощности и pit mode — VTX, управляемому по MSP (`link-vtx`).
- **Если ошибиться здесь:** на порту один бит VTX_MSP без MSP или MSP оказался на четвёртом порту → прошивка сбрасывает весь конфиг портов к умолчаниям, и вместе с OSD «пропадает» приёмник: арм запрещён флагом `RXLOSS` (`bf-ports`, `bf-arming-safety`). Модуль с пределом 13 В запитан от 4S напрямую → выбросы напряжения его убивают; расчёт ветки — в `el-power-design`.

## practice
### Шаг 1. Маски портов из исходника
Всё в лабораторной — Python, который повторяет логику прошивки. Скрипт и вывод сняты на исходнике 4.5.6; `isSerialConfigValid()`, поиск порта DisplayPort, `telemetryCheckRxPortShared()` и макросы `OSD_POS` в 2025.12 не изменились (в таблицу битов добавлен только GIMBAL = 1 << 18, в список приёмников с телеметрией на своём порту — MAVLINK), а строки `serial` в сценариях записаны номерами портов, как в `diff` 4.5. SITL здесь не помогает: в нём нет OSD и VTX. Файл `hd_osd_calc.py` состоит из трёх блоков: этот, блок шага 3 и `__main__` в конце шага 3. Первый блок раскладывает маску и проверяет конфиг портов. Таблица битов при запуске сверяется с `src/main/io/serial.h`.

```python
import re, sys

FUNC = {  # Betaflight 4.5 io/serial.h, serialPortFunction_e
    "MSP": 1 << 0, "GPS": 1 << 1, "TELEMETRY_FRSKY_HUB": 1 << 2, "TELEMETRY_HOTT": 1 << 3,
    "TELEMETRY_LTM": 1 << 4, "TELEMETRY_SMARTPORT": 1 << 5, "RX_SERIAL": 1 << 6,
    "BLACKBOX": 1 << 7, "TELEMETRY_MAVLINK": 1 << 9, "ESC_SENSOR": 1 << 10,
    "VTX_SMARTAUDIO": 1 << 11, "TELEMETRY_IBUS": 1 << 12, "VTX_TRAMP": 1 << 13,
    "RCDEVICE": 1 << 14, "LIDAR_TF": 1 << 15, "FRSKY_OSD": 1 << 16, "VTX_MSP": 1 << 17,
}
TLM_SHAREABLE = FUNC["TELEMETRY_FRSKY_HUB"] | FUNC["TELEMETRY_LTM"] | FUNC["TELEMETRY_MAVLINK"]
TLM_PORT = TLM_SHAREABLE | FUNC["TELEMETRY_HOTT"] | FUNC["TELEMETRY_SMARTPORT"]
SHARABLE_WITH_MSP = FUNC["BLACKBOX"] | TLM_PORT | FUNC["VTX_MSP"]
MAX_MSP_PORT_COUNT = 3                                   # msp/msp_serial.h
RX_TLM_SHARED = {"SPEKTRUM1024", "SPEKTRUM2048", "SBUS", "SUMD", "SUMH", "XB-B", "XB-B-RJ01", "IBUS"}
PORT_NAME = {20: "VCP", 30: "SOFTSERIAL1", 31: "SOFTSERIAL2", 40: "LPUART1",
             **{i: f"UART{i + 1}" for i in range(10)}}


def check_source(path):
    src = open(path, encoding="utf-8").read()
    found = {m.group(1): 1 << int(m.group(2))
             for m in re.finditer(r"FUNCTION_(\w+)\s*=\s*\(1 << (\d+)\)", src)}
    assert found == FUNC, f"table differs from {path}: {set(found.items()) ^ set(FUNC.items())}"
    print(f"function table == {path.split('/src/')[-1] if '/src/' in path else path}: {len(found)} bits OK")


def encode(*names):
    return sum(FUNC[n] for n in names)


def decode(mask):
    names = [n for n, b in FUNC.items() if mask & b]
    rest = mask & ~sum(FUNC.values())
    return names + ([f"UNKNOWN(0x{rest:X})"] if rest else [])


def rx_port_shared(mask, provider):            # telemetry.c telemetryCheckRxPortShared (4.5)
    if mask & FUNC["RX_SERIAL"] and mask & TLM_SHAREABLE and provider in RX_TLM_SHARED:
        return True
    if mask & FUNC["TELEMETRY_IBUS"] and mask & FUNC["RX_SERIAL"] and provider == "IBUS":
        return True
    return bool(mask & FUNC["RX_SERIAL"] and mask & FUNC["VTX_MSP"])   # USE_MSP_OVER_TELEMETRY


def validate(lines, provider="CRSF"):
    """Returns (ok, notes, displayport_port). Mirrors isSerialConfigValid() order of checks."""
    ports, notes = [], []
    for ln in lines:
        p = ln.split()
        pid, mask, msp_baud = int(p[1]), int(p[2]), int(p[3])
        if not 9600 <= msp_baud <= 1000000:
            notes.append(f"{ln}: CLI rejects msp baud {msp_baud} (allowed 9600..1000000)")
        ports.append((pid, mask, msp_baud))
    msp_ports = 0
    for pid, mask, _ in ports:
        name = PORT_NAME.get(pid, str(pid))
        if pid in (30, 31) and mask & (FUNC["MSP"] | FUNC["RX_SERIAL"]):
            notes.append(f"{name}: MSP/Serial RX silently removed (not allowed on SoftSerial)")
            mask &= ~(FUNC["MSP"] | FUNC["RX_SERIAL"])
        if mask & FUNC["MSP"]:
            msp_ports += 1
        elif pid == 20:
            return False, notes + ["VCP without MSP -> INVALID"], None
        bits = bin(mask).count("1")
        if mask & FUNC["VTX_MSP"] and bits == 1:
            return False, notes + [f"{name}: VTX_MSP alone -> INVALID (must share with MSP or Serial RX)"], None
        if bits > 1:
            if bits > bin(FUNC["MSP"] | SHARABLE_WITH_MSP).count("1"):
                return False, notes + [f"{name}: too many shared functions -> INVALID"], None
            if mask & FUNC["MSP"] and mask & SHARABLE_WITH_MSP:
                pass
            elif rx_port_shared(mask, provider):
                pass
            else:
                return False, notes + [f"{name}: {'+'.join(decode(mask))} cannot share a port -> INVALID"], None
    if msp_ports == 0 or msp_ports > MAX_MSP_PORT_COUNT:
        return False, notes + [f"{msp_ports} MSP ports (allowed 1..{MAX_MSP_PORT_COUNT}) -> INVALID"], None
    dp = next((pid for pid, mask, _ in sorted(ports)
               if pid != 20 and mask & FUNC["MSP"] and mask & FUNC["VTX_MSP"]), None)
    if dp is not None:
        baud = next(b for pid, _, b in ports if pid == dp)
        if baud != 115200:
            notes.append(f"{PORT_NAME[dp]}: MSP baud {baud}; DJI, Walksnail and HDZero Race V3 expect 115200")
    return True, notes, dp
```

Запуск: `python3 hd_osd_calc.py betaflight/src/main/io/serial.h` (клон ветки 4.5-maintenance; на `serial.h` из 2025.12.5 скрипт сообщит о лишнем бите GIMBAL). Начало вывода:

```text
function table == main/io/serial.h: 17 bits OK

== 1. masks
 131073 = MSP + VTX_MSP
 131072 = VTX_MSP
     64 = RX_SERIAL
 131201 = MSP + BLACKBOX + VTX_MSP
   2048 = VTX_SMARTAUDIO
encode(MSP, VTX_MSP) = 131073
```

Таблица из 17 битов совпала с исходником. Запиши в свои заметки маску своего порта видео и её разложение.

### Шаг 2. Пять конфигов портов: какой загрузится
Разобранный пример — 5″ 6S: ELRS на UART1, воздушный модуль на UART4. Пять вариантов `serial` прогоняются через `validate()`:

```text
== 2. port configs (serialrx_provider shown in brackets)
A good: ELRS UART1 + HD on UART4 [CRSF]: VALID; DisplayPort on UART4
B VTX bit only on UART4 [CRSF]: INVALID -> whole serial config reset to defaults
    UART4: VTX_MSP alone -> INVALID (must share with MSP or Serial RX)
C DJI SBUS on UART2, MSP only on UART4 [SBUS]: VALID; no DisplayPort port
D four MSP ports [CRSF]: INVALID -> whole serial config reset to defaults
    4 MSP ports (allowed 1..3) -> INVALID
E HD on UART4 at 230400 [CRSF]: VALID; DisplayPort on UART4
    UART4: MSP baud 230400; DJI, Walksnail and HDZero Race V3 expect 115200
```

Что из этого следует:
- B — маска 131072, взятая из таблицы битов без MSP. Прошивка сбросит **все** порты, и приёмник пропадёт вместе с OSD. Это самая неприятная ошибка: со стороны выглядит как «слетели настройки».
- C — стоковый старый DJI (Vista/Air Unit): порт только MSP, OSD рисует сама DJI. Для O3/O4 и WTFOS этот же конфиг означает «видео есть, OSD нет».
- E — конфиг загрузится, но Race V3 работает только на 115200. Другие HDZero сами перебирают 115200/230400, DJI и Walksnail по документации ждут 115200.
- D — MSP на VCP, UART1, UART2 и UART4: четвёртый порт с MSP недопустим.

### Шаг 3. Канва: из аналога в HD и между системами
Вторая часть файла переносит раскладку элементов. Функции `osd_pos`/`osd_xy` — это макросы `OSD_POS`/`OSD_X`/`OSD_Y`. `fw_clamp` повторяет то, что делает `osdInit()`. `edge_map` — собственное правило калькулятора, в прошивке его нет: элементы в крайних четвертях сохраняют расстояние до своего края, центральная половина сдвигается вместе с центром.

```python
def osd_pos(x, y, profiles=(1,), typ=0):
    v = (x & 31) | ((x << 5) & 0x400) | ((y & 31) << 5)      # OSD_POS(x, y): x bit 5 -> bit 10
    for p in profiles:
        v |= 1 << (p - 1 + 11)                               # OSD_PROFILE_FLAG(p)
    return v | ((typ & 3) << 14)                             # OSD_TYPE bits 14-15


def osd_xy(v):
    return (v & 31) | ((v & 0x400) >> 5), (v >> 5) & 31     # OSD_X(v), OSD_Y(v)


def osd_profiles(v):
    return [p for p in (1, 2, 3) if v & (1 << (p - 1 + 11))]


def fw_clamp(v, cols, rows):                                 # osd.c osdInit(): what the FC itself does
    x, y = osd_xy(v)
    keep = v & (0x3800 | 0xC000)                             # OSD_PROFILE_MASK | OSD_TYPE_MASK
    return keep | osd_pos(min(x, cols - 1), min(y, rows - 1), profiles=())


def edge_map(v, src, dst):
    """Own rule: outer quarters keep their distance to that edge, the middle half shifts with the centre."""
    (sc, sr), (dc, dr) = src, dst
    x, y = osd_xy(v)
    nx = x if x < sc / 4 else (dc - (sc - x) if x >= 3 * sc / 4 else x + (dc - sc) // 2)
    ny = y if y < sr / 4 else (dr - (sr - y) if y >= 3 * sr / 4 else y + (dr - sr) // 2)
    return (v & (0x3800 | 0xC000)) | osd_pos(nx, ny, profiles=())
```

Блок `__main__` — те же вызовы с данными примера:

```python
if __name__ == "__main__":
    if len(sys.argv) > 1:
        check_source(sys.argv[1])

    print("\n== 1. masks")
    for m in (131073, 131072, 64, 1 + 128 + 131072, 2048):
        print(f"{m:>7} = {' + '.join(decode(m))}")
    print("encode(MSP, VTX_MSP) =", encode("MSP", "VTX_MSP"))

    print("\n== 2. port configs (serialrx_provider shown in brackets)")
    cases = {
        "A good: ELRS UART1 + HD on UART4": (["serial 20 1 115200 57600 0 115200",
            "serial 0 64 115200 57600 0 115200", "serial 3 131073 115200 57600 0 115200"], "CRSF"),
        "B VTX bit only on UART4": (["serial 20 1 115200 57600 0 115200",
            "serial 0 64 115200 57600 0 115200", "serial 3 131072 115200 57600 0 115200"], "CRSF"),
        "C DJI SBUS on UART2, MSP only on UART4": (["serial 20 1 115200 57600 0 115200",
            "serial 1 64 115200 57600 0 115200", "serial 3 1 115200 57600 0 115200"], "SBUS"),
        "D four MSP ports": (["serial 20 1 115200 57600 0 115200", "serial 0 1 115200 57600 0 115200",
            "serial 1 1 115200 57600 0 115200", "serial 3 131073 115200 57600 0 115200"], "CRSF"),
        "E HD on UART4 at 230400": (["serial 20 1 115200 57600 0 115200",
            "serial 0 64 115200 57600 0 115200", "serial 3 131073 230400 57600 0 115200"], "CRSF"),
    }
    for title, (lines, prov) in cases.items():
        ok, notes, dp = validate(lines, prov)
        print(f"{title} [{prov}]: {'VALID' if ok else 'INVALID -> whole serial config reset to defaults'}"
              f"{'; DisplayPort on ' + PORT_NAME[dp] if dp is not None else ('; no DisplayPort port' if ok else '')}")
        for n in notes:
            print("   ", n)

    print("\n== 3. OSD positions: analog PAL 30x16 layout -> HD")
    sd = {  # element: (x, y) on the analog canvas, profile 1
        "osd_craft_name_pos": (11, 0), "osd_link_quality_pos": (23, 1),
        "osd_flymode_pos": (13, 14), "osd_avg_cell_voltage_pos": (1, 14),
        "osd_mah_drawn_pos": (1, 13), "osd_tim_2_pos": (23, 14), "osd_warnings_pos": (9, 10),
    }
    print(f"{'element':26}{'SD x,y':>8}{'value':>7}{'53x20 edge':>12}{'value':>7}{'50x18 edge':>12}{'value':>7}")
    hd53 = {}
    for name, (x, y) in sd.items():
        v = osd_pos(x, y)
        assert osd_xy(v) == (x, y) and osd_profiles(v) == [1]
        a, b = edge_map(v, (30, 16), (53, 20)), edge_map(v, (30, 16), (50, 18))
        hd53[name] = a
        print(f"{name:26}{x:>4},{y:<3}{v:>7}{'%d,%d' % osd_xy(a):>12}{a:>7}{'%d,%d' % osd_xy(b):>12}{b:>7}")

    print("\n== 4. firmware clamp: the 53x20 layout booted on HDZero (50x18) and on analog (30x16)")
    for name, v in hd53.items():
        h, s = fw_clamp(v, 50, 18), fw_clamp(v, 30, 16)
        print(f"{name:26} {'%d,%d' % osd_xy(v):>6} -> 50x18 {'%d,%d' % osd_xy(h):>6}   -> 30x16 {'%d,%d' % osd_xy(s):>6}")

    print("\n== 5. CLI for the 53x20 layout")
    for name, v in hd53.items():
        print(f"set {name} = {v}")
```

Исходные данные: раскладка аналогового PAL 30×16 из профиля 1. Вывод:

```text
== 3. OSD positions: analog PAL 30x16 layout -> HD
element                     SD x,y  value  53x20 edge  value  50x18 edge  value
osd_craft_name_pos          11,0     2059        22,0   2070        21,0   2069
osd_link_quality_pos        23,1     2103        46,1   3118        43,1   3115
osd_flymode_pos             13,14    2509       24,18   2648       23,16   2583
osd_avg_cell_voltage_pos     1,14    2497        1,18   2625        1,16   2561
osd_mah_drawn_pos            1,13    2465        1,17   2593        1,15   2529
osd_tim_2_pos               23,14    2519       46,18   3662       43,16   3595
osd_warnings_pos             9,10    2377       20,12   2452       19,11   2419

== 4. firmware clamp: the 53x20 layout booted on HDZero (50x18) and on analog (30x16)
osd_craft_name_pos           22,0 -> 50x18   22,0   -> 30x16   22,0
osd_link_quality_pos         46,1 -> 50x18   46,1   -> 30x16   29,1
osd_flymode_pos             24,18 -> 50x18  24,17   -> 30x16  24,15
osd_avg_cell_voltage_pos     1,18 -> 50x18   1,17   -> 30x16   1,15
osd_mah_drawn_pos            1,17 -> 50x18   1,17   -> 30x16   1,15
osd_tim_2_pos               46,18 -> 50x18  46,17   -> 30x16  29,15
osd_warnings_pos            20,12 -> 50x18  20,12   -> 30x16  20,12

== 5. CLI for the 53x20 layout
set osd_craft_name_pos = 2070
set osd_link_quality_pos = 3118
set osd_flymode_pos = 2648
set osd_avg_cell_voltage_pos = 2625
set osd_mah_drawn_pos = 2593
set osd_tim_2_pos = 3662
set osd_warnings_pos = 2452
```

Проверка вручную: LQ в точке (46, 1) даёт 46 & 31 = 14, бит 5 от x = 1 → 1024, y = 1 → 32, профиль 1 → 2048. Сумма 3118 — совпадает. Выводы:
1. При переходе из аналога в HD прошивка ничего не прижимает: 30×16 целиком помещается в 53×20, но вся раскладка остаётся в левом верхнем углу. Переставлять элементы надо самому, по таблице или в OSD-вкладке.
2. Раскладка под 53×20, загруженная на HDZero 50×18, ломается: `osdInit()` прижимает напряжение (1,18) к строке 17, и оно ложится на mAh (1,17). Под каждую систему нужна своя раскладка. Держи её в отдельном `diff`, OSD-профили для этого не годятся: канва у них общая.
3. Тот же HD-конфиг на аналоге: LQ и таймер прижимаются к столбцу 29, и текст обрезается правым краем.

### Шаг 4. Конфиг для трёх систем (процедура по документации)
Betaflight App: Ports → UART4 → Peripherals «VTX (MSP + DisplayPort)», MSP включён, 115200 → Save and Reboot; Configuration → OSD включён; OSD → Video Format HD. То же в CLI (общая часть для O3/O4, Walksnail, HDZero и DJI V1 с WTFOS):

```text
serial UART4 131073 115200 57600 0 115200
set osd_displayport_device = MSP
set vcd_video_system = HD
set displayport_msp_fonts = 0,1,2,3
save
```

На 4.5 первая строка пишется номером порта: `serial 3 131073 115200 57600 0 115200`. DJI с управлением от пульта DJI: добавить `serial UART2 64 115200 57600 0 115200` (в 4.5 — `serial 1 64 …`; UART2, на который заведён S.Bus-пад) и `set serialrx_provider = SBUS`. HDZero: VTX-таблицу не вводить, её загрузит VTX. Для гонок — `set vtx_low_power_disarm = UNTIL_FIRST_ARM`. Сохрани три `diff all` и сравни их построчно: различаться должны только приёмник, раскладка `osd_*_pos` и `vtx_*`.

### Переход на реальное железо
Пропеллеры сняты на всех шагах. Летать нужно только на шаге 6.
1. **Прозвонка до питания.** Мультиметр: + и − силового провода модуля — не КЗ. Напряжение на паде, к которому подключён модуль, измеряется при питании от АКБ через smoke stopper, но **с отсоединённым модулем**. Значение должно попасть в диапазон из таблицы: например, 9–12 В BEC для O4 и Race V3, но не VBAT 4S. Прозвонить TX модуля → RX полётника и наоборот, земли на GND.
2. **Стол с обдувом.** Антенна подключена, на модуль направлен вентилятор. Порядок: очки → АКБ → USB. Если модуль греется так, что сработала защита (LED, предупреждение в очках), стенд остановить. Время до срабатывания O4 без обдува — 2.5 мин, превышать его нельзя.
3. **Первый линк и OSD.** Линковка по инструкции системы. После загрузки: `status` показывает `OSD: MSP (… x …)`, `get osd_canvas` — размер от очков (HDZero 50×18). У HDZero синий LED мигнул 3 раза. В очках видны напряжение, LQ, режим. Арм без пропеллеров проверяет, что предупреждения (`ARMING_DISABLED`) рисуются, а у HDZero/MSP-VTX мощность выходит из LP.
4. **Мощность.** В CE-режиме выставить 25 мВт. У HDZero проверить вкладку Video Transmitter: тип MSP, мощность из таблицы.
5. **Запись.** 60 с записи на столе. Файл открывается на ПК, в нём видны OSD (если он пишется) и время. Отметь, куда идёт запись: модуль или очки.
6. **Полёт.** Висение 60 с, затем круг 2–3 минуты. Предупреждения OSD видны, запись включилась сама (`Auto Record on Takeoff` у DJI). Задержка измеряется методом из `link-digital-video`.

Прервать: запах, мигание защиты от перегрева, пропадание приёмника после сохранения Ports (признак сброса конфига), OSD мигает или пропадает в полёте.

Самопроверка: лабораторная выполнена, когда:
- **Расчёт (без железа)**: `hd_osd_calc.py` запущен против `serial.h` ветки 4.5 (строка `17 bits OK`; для 2025.12 отметь в заметках, что добавлен бит GIMBAL). Для своего аппарата в заметках лежат строка `serial` и разложение маски (сумма битов равна маске, как 131073 = MSP + VTX_MSP), вердикт `validate()` (VALID, DisplayPort на нужном UART), таблица `set osd_*_pos` под канву своей системы, где хотя бы одна позиция пересчитана вручную по образцу проверки LQ (46, 1) → 3118, и список элементов, которые прижал бы `osdInit()` на другой канве, — он совпадает с частью 4 вывода скрипта на твоей раскладке.
- **Железо**: заполнена таблица разводки (провод → пад, напряжение пада от АКБ при отсоединённом модуле), на столе работал обдув, `status` и `get osd_canvas` записаны, OSD виден в очках, есть 60-секундная запись с указанием носителя. Мощность выставлена по правилам своей страны, `diff all` после настройки сохранён в папке аппарата.

**Эталон для самопроверки.** Правильный результат расчёта: скрипт печатает `17 bits OK`, конфиг твоего аппарата — `VALID; DisplayPort on UART…` с нужным портом, а значения `osd_*_pos` разбираются обратно в те же x, y. Вердикт `INVALID -> whole serial config reset to defaults` чаще всего значит маску 131072 (VTX_MSP без MSP, вариант B) или четвёртый порт с MSP (вариант D). `VALID; no DisplayPort port` — на порту только MSP (вариант C): видео будет, OSD нет. При проверке другой канвы эталон — часть 4 вывода: раскладка 53×20 на 50×18 теряет строку 18 (напряжение ложится на mAh в строке 17), на 30×16 элементы правее столбца 29 прижимаются к нему и обрезаются.

{{diagram:bf-hd-no-osd|«Видео есть, OSD нет»: сначала маска 131073, затем HD-режим и OSD, затем обмен по UART и только потом настройки очков.}}

## diagnostics
- **Симптом:** видео есть, OSD в очках нет (вопрос № 11)
  - Возможная причина: маска порта 1 или 131072 вместо 131073; `vcd_video_system` не HD; OSD выключен; TX/RX не крест-накрест; порт — SoftSerial.
  - Что сделать: `serial` → маска 131073 на UART модуля, `get vcd_video_system`, `feature OSD`, прозвонка; дерево проверок ниже.
- **Симптом:** после сохранения Ports пропал приёмник, порты вернулись к умолчаниям
  - Возможная причина: VTX_MSP без MSP или четвёртый порт с MSP — `isSerialConfigValid()` сбросил весь конфиг портов.
  - Что сделать: `validate()` из практики, затем исправить маску и проверить число портов с MSP (≤ 3).
- **Симптом:** `set displayport_msp_serial = 3` → `INVALID NAME`
  - Возможная причина: переменная удалена в 4.4, инструкция написана под 4.3.
  - Что сделать: ничего вводить не нужно — порт определяется маской 131073.
- **Симптом:** OSD съехал в левый верхний угол или элементы налезают друг на друга
  - Возможная причина: раскладка от SD (30×16) или от другой HD-канвы; `osdInit()` только прижимает к краю.
  - Что сделать: раскладка под свою канву (`get osd_canvas`), отдельный `diff` на систему.
  - Последствия: напряжение, закрытое mAh, не видно в полёте.
- **Симптом:** часть элементов OSD или предупреждения не рисуются, остальные на месте
  - Возможная причина: `displayport_msp_fonts = 0,1,2,3` при одностраничном шрифте в очках.
  - Что сделать: цветной шрифт Betaflight в очки или `set displayport_msp_fonts = 0,0,0,0`.
- **Симптом:** при первом подключении очков полётник сам перезагрузился
  - Возможная причина: очки прислали `MSP_SET_OSD_CANVAS`, FC был не в HD/MSP — прошивка переключилась, сохранилась и перезагрузилась.
  - Что сделать: ничего, это штатно; проверить `get vcd_video_system` = HD.
- **Симптом:** модуль отключается или запись обрывается на столе
  - Возможная причина: перегрев без обдува; у O4 холодный старт без обдува — около 2.5 мин.
  - Что сделать: вентилятор, не держать включённым на земле; HDZero — 0MW вместо P1MW.
- **Симптом:** VTX HDZero не загрузился (нет синего LED) при подключённом USB
  - Возможная причина: АКБ подключена к полётнику, уже подключённому к ПК.
  - Что сделать: сначала АКБ, потом USB; питание VTX — в пределах спецификации.
- **Симптом:** DJI-пульт связан, но в Receiver ползунки стоят
  - Возможная причина: жёлтый S.Bus не на S.Bus-паде (F4 без инвертора), `serialrx_provider` не SBUS.
  - Что сделать: S.Bus-пад, Serial RX на этом UART, `serialrx_provider = SBUS` (`bf-ports`).
- **Симптом:** свой логотип пропал, при включении снова стандартный (аналог)
  - Возможная причина: залит другой шрифт — «Upload Font» переписывает все 256 символов, в том числе 160–255 с логотипом.
  - Что сделать: выбрать шрифт, заново подставить картинку 288 × 72, Upload Font; хранить свой `.mcm` с логотипом.
- **Симптом:** Font Manager серый или «Select custom image…» отказывает
  - Возможная причина: OSD-устройство — MSP (HD) или MAX7456 не обнаружен; картинка не 288 × 72 px или в ней есть пиксели не из трёх цветов (сглаживание, PNG с палитрой оттенков).
  - Что сделать: для HD шрифт меняется в очках; для аналога проверить `status` (тип OSD), экспортировать картинку без сглаживания строго в 0,255,0 / 0,0,0 / 255,255,255.
- **Симптом:** на аналоговом аппарате OSD нет или он дрожит (вопрос № 12)
  - Возможная причина: в сборке есть «OSD (HD)», и умолчание — `HD`/`MSP`; не та видеосистема у камеры.
  - Что сделать: `set vcd_video_system = PAL` (или NTSC/AUTO), `osd_displayport_device = MAX7456` или AUTO, центровка `vcd_h_offset`/`vcd_v_offset`.


## checklist
- Знаю диапазон питания своего модуля и откуда его брать — VBAT или только BEC
- TX/RX крест-накрест, обе земли на полётнике, не SoftSerial
- На порту модуля маска 131073 и 115200, MSP включён не больше чем на 3 портах
- `vcd_video_system = HD`, `osd_displayport_device = MSP`, OSD включён
- Знаю, что `displayport_msp_serial` удалена в 4.4
- Раскладка OSD сделана под канву своей системы, `displayport_msp_fonts` соответствует шрифту в очках
- Знаю, что логотип — символы 160–255 шрифта: на аналоге он в памяти MAX7456 и затирается заливкой шрифта, на HD — в шрифте очков
- На столе работает обдув, порядок включения: антенна → очки → АКБ → USB
- Запись проверена, мощность выставлена по правилам страны

## references
- Betaflight io/serial.h — serialPortFunction_e, тег 2025.12.5 (FUNCTION_GIMBAL = 1 << 18) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/io/serial.h | primary | A
- Betaflight io/serial.h — serialPortFunction_e (FUNCTION_VTX_MSP = 1 << 17), 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/io/serial.h | primary | A
- Betaflight io/serial.c — isSerialConfigValid(), 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/io/serial.c | primary | A
- Betaflight osd/osd.h — OSD_POS, OSD_HD_COLS/ROWS 53×20, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/osd/osd.h | primary | A
- Betaflight cli/settings.c — displayport_msp_*, vcd_video_system, osd_canvas_*, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/cli/settings.c | primary | A
- Betaflight cli/settings.c 4.3-maintenance — displayport_msp_serial, displayport_msp_attrs | https://raw.githubusercontent.com/betaflight/betaflight/4.3-maintenance/src/main/cli/settings.c | primary | A
- Betaflight App — OSD tab (HD 53×20, канва от VTX) | https://betaflight.com/docs/wiki/app/osd-tab | primary | A
- Betaflight osd/osd.c — osdDrawLogo, osd_logo_on_arming, osd_arming_logo, 2025.12.5 | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/osd/osd.c | primary | A
- Betaflight drivers/max7456.c — max7456WriteNvm (font NVM), 2025.12.5 | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/drivers/max7456.c | primary | A
- Betaflight Configurator 10.10 — LogoManager.js (288×72, three colours, PNG/BMP) | https://raw.githubusercontent.com/betaflight/betaflight-configurator/10.10.0/src/js/LogoManager.js | primary | A
- Betaflight Configurator 10.10 — tabs/osd.js (Font Manager, .mcm, Upload Font) | https://raw.githubusercontent.com/betaflight/betaflight-configurator/10.10.0/src/js/tabs/osd.js | primary | A
- DJI O3 Air Unit User Manual v1.0 (распиновка, Canvas mode, перегрев, линковка) | https://xcopter.com/download/DJI_O3_Air_Unit_User_Manual_v1.0_ENo.pdf | primary | A
- DJI O3 Air Unit specifications | https://www.cliftoncameras.co.uk/uploads/specifications/DJI%20O3%20Air%20Unit.pdf | primary | A
- DJI O4 Air Unit / O4 Air Unit Pro specs | https://www.dji.com/o4-air-unit/specs | primary | A
- DJI O4 Air Unit Series User Manual v1 (BEC ≥ 10/13.5 Вт, время на столе) | https://hobbydrone.cz/user/related_files/dji_o4_air_unit_series_user_manual_v1_en.pdf | primary | A
- DJI FPV Air Unit specs (7.4–17.6 В, < 28 мс) | https://www.dji.com/fpv/info | primary | A
- DJI Digital FPV System Release Notes (кастомный OSD, 24 элемента) | https://manuals.plus/m/21886e9a1f15ac666e592e9149600fb1e60f9d4a47d083ae5c8f773ecd562a25 | primary | B
- Walksnail Avatar HD Pro Kit specifications | https://www.caddxfpv.com/products/walksnail-avatar-hd-pro-kit-dual-antenna | primary | A
- Walksnail Avatar kit Quickstart guide V1.1 | https://cdn.shopify.com/s/files/1/0618/3020/1566/files/Avatar_kit_Quickstart_guide_EN_CN_V1.1.pdf | primary | A
- Walksnail Avatar HD Mini VTX V3 manual (питание 3.1–13 В, обдув на столе, CE) | https://www.rotorama.com/assets/docs/5f2b6df00100231feac11bb2a7480570/47716-1/walksnail-avatar-hd-mini-vtx-v3-manual-en.pdf | primary | A
- HDZero VTX docs — targets (питание, BEC vs VBAT, распиновка) | https://hd-zero.github.io/hdzero-vtx-docs/latest/vtx_targets | primary | A
- HDZero VTX docs — user manual (baud, LP_MODE, PIT_MODE, VTX table) | https://raw.githubusercontent.com/hd-zero/hdzero-vtx-docs/main/docs/vtx_user_manual.md | primary | A
- HDZero VTX docs — troubleshoot (перегрев, порядок USB/АКБ) | https://raw.githubusercontent.com/hd-zero/hdzero-vtx-docs/main/docs/vtx_troubleshoot.md | primary | A
- HDZero VTX firmware msp_displayport.c (MSP_SET_OSD_CANVAS, HD_5018) | https://raw.githubusercontent.com/hd-zero/hdzero-vtx/main/src/msp_displayport.c | primary | A
- Divimath — Latency analysis, analog vs HDZero (white paper) | https://www.helicomicro.com/wp-content/uploads/2022/09/WhitePaper-LatencyAnalysis-AnalogvsHDZero.pdf | primary | B
- fpv-wtf msp-osd README (WTFOS, displayport_msp_fonts, 4.3 vs 4.4) | https://raw.githubusercontent.com/fpv-wtf/msp-osd/main/README.md | secondary | B
- Caddx Vista unit specifications (retailer listing) | https://www.getfpv.com/caddx-vista-unit-for-dji-digital-hd-fpv-no-camera.html | secondary | B

## notes
Имена, умолчания и диапазоны Betaflight — из исходника 4.5.6, сверены с таблицей настроек 2025.12.5 (отличий в переменных справочника нет); маски проверены программой по `serial.h`, позиции — по `osd.h`. Питание, мощность и задержка — заявления производителей; задержка HDZero — оценка по модели Divimath. Логотип и шрифты: прошивка — `osd/osd.c`, `drivers/max7456.c`, `io/displayport_msp.c` (4.5.3 и 2025.12.5), приложение — Configurator 10.10.0 (`LogoManager.js`, `tabs/osd.js`). Не проверено: как менять шрифт и логотип на стороне HD-очков. Не проверено: канва, которую сообщают DJI O3/O4 и Walksnail (читай `get osd_canvas`); MSP-VTX у DJI и Walksnail; версия прошивки DJI, давшая старым очкам Canvas mode. Порядок «очки → аппарат» — практика, а не требование производителя.
