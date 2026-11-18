---
id: bf-led-buzzer
title: "Светодиоды, пищалка и маячки: LED_STRIP, `led` / `color` / `mode_color`, beeper, DShot beacon"
level: L2
readingTime: 40 мин
firmware: Betaflight 2025.12 (сверено с 2025.12.5); лабораторная снята на исходниках 4.5.6 и 2025.12
status: published
added: 2026-11-14
tags:
  - Betaflight
  - LED_STRIP
  - WS2812
  - beeper
  - DShot beacon
  - CLI
  - поиск аппарата
related:
  - bf-cli
  - bf-modes-osd
  - bf-adjustments
  - bf-failsafe
  - el-power-design
  - f-esc-firmware
next:
  - bf-hd-osd-video
---

## summary
Лента WS2812/SK6812, пищалка и DShot beacon («пищат моторы») показывают состояние аппарата и помогают найти его в траве. Модуль разбирает их по исходнику Betaflight 2025.12 (отличия 4.5 названы на месте): питание и уровень сигнала ленты, `resource LED_STRIP` и почему светодиод на таймере мотора ломает DShot, синтаксис `led`, палитру `color` с инвертированной насыщенностью, `mode_color`, профили RACE/BEACON/STATUS, все условия `beeper` и `beacon` — когда они срабатывают на самом деле. Лабораторная: Python-порт парсера и цветовой математики прошивки (сетка 16×16, бюджет тока, маски бипера, таймлайн маяка), затем стол без пропов: мультиметр до питания, ток ленты, проверка RX_LOST и маяка.

## theory
### Железо ленты
WS2812 (WS2811, SK6812) — светодиод со встроенным драйвером, три провода: **5 В, GND, DIN**. Пад LED на плате → `DIN` первого, `DOUT` → `DIN` следующего; номер = порядок по проводу с нуля. Две ленты параллельно от одного `DIN` показывают одно и то же.

- **Ток.** До 60 мА на светодиод при полном белом (≈ 20 мА на канал), 20 мА в среднем — грубое правило Adafruit. Документация Betaflight: NeoPixel Jewel 7 в белом ≈ 350 мА. 32 белых на 100 % — до ~1.9 А, почти 10 Вт.
- **Почему не от 5 В платы.** BEC полётника (1–3 А, смотри спецификацию) уже кормит приёмник, камеру, GPS. Длинная лента на белом просаживает шину — страдают приёмник и сам FC. Документация советует отдельный BEC (или половину ленты от другого BEC) с **общей землёй**.
- **Уровень.** DIN считает «1» от 0.7·VDD: при 5 В это 3.5 В, а пин MCU даёт 3.3 В. Решения: буфер 74AHCT125/74HCT245 от 5 В (Adafruit) или питание ленты ниже 4.7 В через диод в плюсе (3.3 / 0.7 = 4.71 В — рецепт документации Betaflight).
- **Обвязка (Adafruit).** Резистор 300–500 Ом в линии данных у первого светодиода, не у FC; конденсатор 500–1000 мкФ ≥ 6.3 В на питании ленты; на живой цепи — земля первой, данные последними.

### Сборка, ресурс, таймер
Cloud Build: опция `LED_STRIP`, `LED_STRIP_64` — 64 светодиода вместо 32 (на F411 сборка не пройдёт). Без опции `config.c` снимает `feature LED_STRIP` при каждой загрузке. Пин: `resource LED_STRIP 1 <пин>`, обычно уже задан конфигом платы.

Драйвер (`light_ws2811strip_hal.c`, на F4 — `light_ws2811strip_stdperiph.c`) забирает **таймер** пина и **поток DMA**, затем переписывает предделитель и период всего таймера под 800 кГц: бит 1.25 мкс, «1» ≈ 2/3 периода, «0» ≈ 1/3. Нет DMA или канал занят — инициализация молча возвращает false: лента тёмная, моторы целы.

Опасно, когда LED на **том же таймере, что и мотор**. У таймера одна база (PSC/ARR) на 4 канала, а DShot через DMA ставит свою: DSHOT600 = 12 МГц × 20 тиков (`pwm_output_dshot.c`). Лента инициализируется **после** моторов (`fc/init.c`) и перебивает предделитель, а DShot на каждом кадре переписывает период (ARR) под себя. Ломаются оба: мотор получает посылку не той скорости (ESC не стартует или пищит «нет сигнала»), лента — мусор. С `dshot_bitbang` (AUTO: на F4 — при bidirectional DShot, на остальных MCU — всегда, кроме PROSHOT) нужен таймер-метроном TIM1 или TIM8. `bbFindPacerTimer()` ищет его уже после ленты и обходит занятые. Если LED взял последний подходящий (на F411 есть только TIM1), моторам ставится `motorWriteNull`, и они не крутятся.

Проверка: `resource`, `timer show` (рядом в одном `TIMn:` строки `LED_STRIP` и `MOTOR 4` — конфликт), `dma show` (`DMA2 Stream 7: LED_STRIP`). Перенос — `timer <пин> list`, затем `resource`/`timer`/`dma pin`, `save` (подробно в `bf-cli`).

### Строка `led`
`led <i> <x>,<y>:<направления>:<функции>:<цвет>`, i = 0…31. По `parseLedStripConfig()`:
- **x, y** 0…15 — `atoi` и маска 4 бита: 17 молча станет 1. 0,0 — северо-запад, нос сверху.
- **Направления** `N E S W U D`. Функция `F` берёт цвет **первого бита в порядке N,E,S,W,U,D**: «SE» = цвет E (DARK_VIOLET), а не S (RED).
- **Базовая функция** — одна: `C` цвет, `F` режим/ориентация, `A` арм, `L` заряд, `S` RSSI, `G` GPS, `R` кольцо тяги. Каждая базовая буква перезаписывает прежнюю.
- **Оверлеи** — любые: `T` по AUX, `Y` радуга, `O` сканер Ларсона, `B` мигание, `V` цвет по частоте VTX, `I` поворотники по стикам, `W` предупреждения. Блок функций ≤ 10 символов, иначе ошибка.
- **Цвет** — индекс палитры 0…15; 16 и больше молча станут 0.

Ловушка: строка, упакованная в ноль (`0,0::C:0`), **заканчивает ленту** — `updateLedCount()` считает до первой нулевой записи. Ноль в середине отрежет хвост.

Поведение функций в STATUS:
- `L`/`S`: оттенок = max(−30 + 1.5·процент, 0): красный ≤ 20 %, жёлтый 60 %, зелёный 100 %. Заряд считается по мАч при `bat_capacity` > 0, иначе по напряжению между `vbat_min_cell_voltage` и `vbat_max_cell_voltage` — датчик тока не обязателен.
- `A`: дизарм — зелёный, арм — синий.
- `W`: цикл 1.6 с из окон по 0.4 с: арм запрещён (зелёный), батарея не OK (красный, если задан датчик напряжения), failsafe (жёлтый/синий), переворот после краша (пурпурный). Цвета жёсткие. «Не OK» включает NOT_PRESENT: на USB без АКБ W мигает красным — норма.
- `B`: две вспышки по 100 мс каждые 1.5 с; `R`: в арме бегущий огонь, быстрее с газом.

### Палитра и `mode_color`
`color <i> <h>,<s>,<v>`: i 0…15, H 0…359, S и V 0…255. Насыщенность **инвертирована** (`hsvToRgb24()`: `sat = 255 − s`): S = 0 — чистый цвет, 255 — белый. Поэтому WHITE = `0,255,255`, RED = `0,0,255`. Число за пределом — ошибка, и цвет обнуляется в чёрный. Дефолт: 0 BLACK, 1 WHITE, 2 RED, 3 ORANGE, 4 YELLOW, 5 LIME_GREEN, 6 GREEN, 7 MINT_GREEN, 8 CYAN, 9 LIGHT_BLUE, 10 BLUE, 11 DARK_VIOLET, 12 MAGENTA, 13 DEEP_PINK, 14–15 чёрные.

`mode_color <режим> <функция> <цвет>`: режимы 0–5 (ORIENTATION, HEADFREE, HORIZON, ANGLE, MAG, BARO) × направления 0–5 — цвета для `F` (приоритет HEADFREE, MAG, HORIZON, ANGLE, иначе ORIENTATION; BARO не используется). Дефолт ORIENTATION: N WHITE, E DARK_VIOLET, S RED, W DEEP_PINK, U BLUE, D ORANGE. `mode_color 6 <0…7> <цвет>` — особые: дизарм, арм, анимация, фон, фон мигания, GPS без спутников / без фикса / фикс. `mode_color 7 0 <канал>` — канал оверлея `T` (дефолт 3, газ).

### Профили и яркость
- **STATUS** (дефолт) — всё, что выше.
- **RACE** — вся лента в `ledstrip_race_color`; BLACK = цвет по частоте VTX.
- **BEACON** — мигание `ledstrip_beacon_color`, период `ledstrip_beacon_period_ms` 500, горит `ledstrip_beacon_percent` 50 % → **2 вспышки/с** (документация пишет «раз в секунду» — код с ней расходится).

В RACE и BEACON при активном failsafe (stage 2, держится после failsafe-дизарма до возврата связи) или режиме BEEPER лента мигает цветом `ledstrip_visual_beeper_color` с периодом `BEACON_FAILSAFE_PERIOD_US = 250`. Имя и комментарий «2Hz» врут: значение идёт в `millis() %`, это 250 мс — **4 вспышки/с**. `ledstrip_visual_beeper = ON` действует только в RACE/BEACON; в STATUS W-светодиоды мигают с пищалкой всегда, когда нет предупреждений.

`ledstrip_brightness` 5…100 умножает V (`v·brightness/100`) — ток падает пропорционально. Режим LEDLOW (id 15) гасит ленту.

Профиль с пульта: `adjrange` с функцией 30 (LED_PROFILE), выбор из 3: < 1300 мкс RACE, 1300–1699 BEACON, ≥ 1700 STATUS. Бипа нет, в EEPROM не пишется. На OSD элемент Adjustment range показывает метку «LED PROFILE»; яркость с пульта — функция 31 LED_DIMMER (выбор, 100 позиций, метка «LED DIMMER»). Обе метки и функция 31 появились в 2025.12. В 4.5 метки **нет**: `adjustmentLabels[]` кончается на «OSD PROFILE», и элемент читает указатель за концом массива — текст непредсказуем.

### Пищалка
Активная пищалка пищит от постоянного тока; пин MCU её не тянет, на плате стоит транзисторный ключ (пады обычно BZ+ — питание, BZ− — ключ). Пассивной нужен `beeper_frequency` — ШИМ 50 % на таймере пина; 0 — активная.

`beeper_inversion` проверяй по коду, не по имени: `systemBeep()` пишет в пин `inverted ? on : !on`. ON — «пищать» = высокий уровень (база NPN-ключа), OFF — низкий. `beeper_od` = ON — открытый сток. Дефолт от платы: с `BEEPER_INVERTED` в конфиге — ON/OFF, без него — OFF/ON.

`beeper` — список выключенных, `beeper list` — все, `beeper -ИМЯ` / `beeper ИМЯ`, `ALL`. Имя сравнивается **по префиксу без регистра**, берётся первое совпадение в таблице: `beeper -RX` выключит RX_LOST. Выключенное условие молчит в пищалке и визуальном бипере; DShot-маяк управляется отдельно (`beacon`).

| Условие | Когда звучит (2025.12) |
|---|---|
| GYRO_CALIBRATED | 3 сигнала после калибровки гиро при старте |
| RX_LOST | нет RC-данных **и** не вставлен USB (`flight/failsafe.c`); в 4.5 условие другое — нет RC-данных и аппарат в арме или армился после включения; 0.5 с звук / 0.5 с пауза |
| RX_LOST_LANDING | SOS в арме при посадке failsafe / GPS Rescue |
| ARMING, DISARMING | арм без фичи GPS; дизарм |
| ARMING_GPS_FIX / _NO_FIX | арм с GPS: спутников ≥ `gps_rescue_min_sats` / меньше |
| BAT_LOW, BAT_CRIT_LOW | состояние батареи WARNING / CRITICAL (по напряжению, с `use_consumption_alerts` — и по мАч); пищит только при `use_vbat_alerts` |
| GPS_STATUS | число спутников при режиме GPS BEEP SATELLITE COUNT (фикс, > 4) |
| RX_SET | режим BEEPER |
| ACC_CALIBRATION / _FAIL | калибровка акселерометра (и старт калибровки компаса) |
| READY_BEEP | один раз в дизарме, когда GPS готов |
| MULTI_BEEPS | подтверждения: save, профили, подстройки, коды запрета арма |
| DISARM_REPEAT, ARMED | стик дизарма удерживается; армлен с MOTOR_STOP без airmode, газ внизу |
| SYSTEM_INIT, BLACKBOX_ERASE | загрузка; стирание флеша окончено |
| ON_USB | особое: если **выключено** и батареи нет — молчит всё |
| CRASHFLIP (в 4.5 — CRASH_FLIP) | активен переворот после краша |
| CAM_CONNECTION_OPEN/CLOSE | эмуляция кнопок RunCam |
| RC_SMOOTHING_INIT_FAIL (только 4.5) | в арме фильтры RC smoothing не готовы; в 2025.12 условие удалено |

Режим BEEPER MUTE (id 52) глушит всё, включая RX_LOST и маяк. Из-за переименования CRASH_FLIP → CRASHFLIP и удаления RC_SMOOTHING_INIT_FAIL строки `beeper -CRASH_FLIP` и `beeper -RC_SMOOTHING_INIT_FAIL` из `diff` 4.5 в 2025.12 дадут ошибку.

### DShot beacon и поиск аппарата
ESC пищит обмотками мотора по DShot-команде BEACON1…5 (`beeper_dshot_beacon_tone`, дефолт 1); нужен протокол DShot. Условия — только RX_LOST и RX_SET, и **по умолчанию оба выключены** (`DEFAULT_DSHOT_BEACON_OFF_FLAGS = DSHOT_BEACON_ALLOWED_MODES`): включай `beacon RX_LOST`.

`beeperUpdate()` шлёт команду только при `!areMotorsRunning()` (не в арме, не при тесте моторов), не раньше 1.2 с после дизарма, не во время попытки арма и не чаще раза в 450 мс (`DSHOT_BEACON_MODE_INTERVAL_US`). RX_LOST-маяк молчит при вставленном USB, RX_SET-маяк работает только при живом приёме. В 4.5 интервалов было два — 450 мс (RX_SET) и 950 мс (RX_LOST), а условий про USB и приём не было. В арме маяк прошивка не пустит. Но ESC пищит до ~250 мс (комментарий в коде), и при RX_SET обмотки под током до половины времени: моторы и ESC греются, батарея садится — минутами на столе не держи.

Поиск: в 2025.12 RX_LOST звучит при любой потере RC-данных без USB (в 4.5 — только если после включения был арм). После падения выключи пульт — пищалка и маяк. Лента в RACE/BEACON мигает 4 Гц, только если failsafe успел сработать в воздухе: при потере связи в дизарме он не активируется. Пульт ещё на связи — тумблер BEEPER (пищалка, маяк при `beacon RX_SET`, лента 4 Гц). Отлетела батарея — выручит только автономная пищалка со своим аккумулятором.

### Справочная таблица
| Переменная / команда | Дефолт (2025.12 и 4.5) | Диапазон | Смысл |
|---|---|---|---|
| `feature LED_STRIP` | вкл. на ненастроенной плате | — | задача ленты, 60 Гц |
| `resource LED_STRIP 1 <пин>` | конфиг платы | пин с таймером и DMA | выход данных |
| `led <i> x,y:dir:fn:col` | все 0 | i 0–31 | раскладка; ноль = конец |
| `color <i> h,s,v` | палитра выше | 0–15; 359/255/255 | S инвертирована |
| `mode_color <m> <f> <c>` | см. выше | m 0–7 | режимы, особые, AUX |
| `ledstrip_profile` | STATUS | RACE/BEACON/STATUS | профиль |
| `ledstrip_race_color` | ORANGE | 14 имён | BLACK = по VTX |
| `ledstrip_beacon_color` | WHITE | 14 имён | цвет BEACON |
| `ledstrip_beacon_period_ms` | 500 | 50–10000 | период BEACON |
| `ledstrip_beacon_percent` | 50 | 0–100 | доля «горит» |
| `ledstrip_beacon_armed_only` | OFF | OFF/ON | BEACON только в арме |
| `ledstrip_visual_beeper` | OFF | OFF/ON | лента с пищалкой (RACE/BEACON) |
| `ledstrip_visual_beeper_color` | WHITE | 14 имён | и цвет failsafe-мигания |
| `ledstrip_brightness` | 100 | 5–100 | V × процент |
| `ledstrip_grb_rgb` | GRB | GRB/RGB/GRBW | GRBW: SK6812 RGBW, W = min(R,G,B) |
| `ledstrip_rainbow_delta` / `_freq` | 0 / 120 | 0–359 / 1–2000 | оверлей `Y` |
| `beeper [-]ИМЯ` | всё включено | 23 условия + ALL (в 4.5 — 24) | пищалка |
| `beacon [-]ИМЯ` | оба выключены | RX_LOST, RX_SET | DShot beacon |
| `beeper_dshot_beacon_tone` | 1 | 1–5 | тон BEACONn |
| `beeper_inversion`, `beeper_od` | от платы | OFF/ON | активный уровень, открытый сток |
| `beeper_frequency` | 0 | 0–16000 | 0 — активная, иначе ШИМ, Гц |
| режимы `aux` | — | 13 BEEPER, 15 LEDLOW, 37 GPS BEEP SAT. COUNT, 52 BEEPER MUTE | тумблеры |

### Место в системе

- **Получает:** таймер и поток DMA пина `LED_STRIP` (`bf-cli`); 5 В от отдельного BEC с общей землёй (`el-power-design`); состояния арма, батареи и failsafe (`bf-arming-safety`); функции 30 и 31 подстроек для профиля и яркости (`bf-adjustments`).
- **Отдаёт:** коды запрета арма звуком; сигнал RX_LOST и DShot beacon для поиска упавшего аппарата; цвет и мигание ленты по состоянию — пилоту и наблюдателю.
- **Если ошибиться здесь:** LED на одном таймере с мотором → лента перебивает предделитель, DShot идёт не той скорости, ESC не стартует; выглядит как неисправный регулятор, а ищется через `timer show` (`bf-cli`, `bf-servos-pwm`). Длинная лента на белом от 5 В полётника → шина проседает, страдают приёмник и сам FC (`el-power-design`).

## practice
SITL Betaflight здесь собрать нельзя, а ленты и пищалки в SITL и нет. Основной путь — скрипт `bf-led-buzzer.led_lab.py` (рабочая папка курса, этап 6): таблицы берутся из исходника, логика повторяет прошивку. Ток — модель «20 мА на канал при 255», на железе её проверяют амперметром.

Вывод шагов 1–5 снят на исходнике 4.5.6 (второй аргумент — дерево 2025.12 — нужен только для строки сравнения в шаге 4). Разбор `led`, палитра и маски в 2025.12 считаются так же; отличаются таблица условий пищалки, три новые базовые функции ленты (`P`, `E`, `U`) и тайминг маяка в шаге 5 (в 2025.12 интервал 450 мс и для RX_LOST, а RX_LOST звучит и без предшествующего арма).

```
python3 -I bf-led-buzzer.led_lab.py ~/src/betaflight-4.5/src/main ~/src/betaflight-2025.12/src/main --svg grid.svg
```

### Шаг 1. Разбор строк `led`
Ядро — порт `parseLedStripConfig()`:

```python
    x, y = int(out[0] or 0) & 0xF, int(out[1] or 0) & 0xF   # atoi, then CALCULATE_LED_XY masks 4 bits
    d = sum(1 << i for i, c in enumerate(DIRS) if c in out[2])
    fn, ov = 0, 0
    for ch in out[3]:
        if ch in FUNCS:
            fn = FUNCS.index(ch)          # every base letter overwrites: the last one wins
        if ch in OVLS:
            ov |= 1 << OVLS.index(ch)
    col = int(out[4] or 0)
    col = 0 if col >= 16 else col
    packed = ((x << 4) | y) | (fn << 8) | (ov << 12) | (col << 22) | (d << 26)
```

```text
led 3 14,1:EN:FW:0       -> 0x0C0401E1  prints 'led 3 14,1:NE:FW:0'
led 4 14,14:SE:FW:0      -> 0x180401EE  prints 'led 4 14,14:ES:FW:0'
led 10 0,0::C:0          -> 0x00000000  prints 'led 10 0,0::C:0'
strip length = 10 (updateLedCount stops at the first all-zero entry; led 10 0,0::C:0 is that terminator)
  1,1:NW:FCW:0           -> '1,1:NW:CW:0'  packed 0x24040011
  17,1::C:2              -> '1,1::C:2'  packed 0x00800011
  3,3::C:16              -> '3,3::C:0'  packed 0x00000033
  1,1:NW:FWIOBYTVACL:0   -> PARSE ERROR (cliShowParseError)
```

`led` печатает направления в порядке NESWUD, базовую функцию первой — так выглядит `diff`. «FCW» молча стал «CW», x = 17 — единицей, цвет 16 — нулём; ошибку дал только блок из 11 символов.

### Шаг 2. Сетка и цвета
Раскладка: 0–3 на передних лучах (NW/NE), 4–7 на задних, 8–9 в центре с `L`. Цвета в STATUS при дизарме и 100 % заряда:

```text
  led 3: fn F dirs NE hsv (0, 255, 255) -> rgb (255, 255, 255)   60.0 mA
  led 4: fn F dirs ES hsv (270, 0, 255) -> rgb (127, 0, 255)   30.0 mA
  led 6: fn F dirs SW hsv (0, 0, 255) -> rgb (255, 0, 0)   20.0 mA
  led 8: fn L dirs    hsv (120, 0, 255) -> rgb (0, 255, 0)   20.0 mA
  total 380 mA (model, 20 mA per channel at 255)
  L function at battery  20 %: hue   0 -> rgb (255, 0, 0)
quadrants (updateDimensions): north y<=7, south y>=8, west x<=7, east x>=8
```

{{diagram:bf-led-grid-layout|Раскладка лабораторной так, как её покажет прошивка: «SE» на задних правых даёт фиолетовый, а не красный — F берёт первый бит направления в порядке N,E,S,W; исправление — направление `S`.}}

Задние правые фиолетовые — ловушка порядка направлений. Исправление: `led 4 14,14:S:FW:0`, `led 5 13,13:S:FW:0`.

### Шаг 3. Бюджет тока
```text
  10 LEDs all WHITE, brightness 100 % -> rgb (255, 255, 255) ->    600 mA (3.00 W at 5 V)
  32 LEDs all WHITE, brightness 100 % -> rgb (255, 255, 255) ->   1920 mA (9.60 W at 5 V)
  32 LEDs all WHITE, brightness  30 % -> rgb (76, 76, 76) ->    572 mA (2.86 W at 5 V)
  GRBW (SK6812 RGBW) white at 100 %: R,G,B + W=min(r,g,b) all on -> 80 mA per LED in the model
  budget: BEC 2.0 A - other 5 V loads 0.9 A - strip 1920 mA = -820 mA for 32 LEDs at 100 % -> separate 5 V BEC
```

BEC 2 А и 0.9 А прочих нагрузок — пример, подставь свои. Считай худший случай — белый на 100 %: BEACON, визуальный бипер и failsafe дают белый в поле.

{{diagram:chart-bf-led-current|Ток ленты растёт линейно с ledstrip_brightness: 32 белых светодиода на 100 % (1.92 А) не помещаются в запас BEC 1.1 А, на 30 % — помещаются (572 мА).}}

### Шаг 4. Маски бипера
Бит = `1 << (enum − 1)` по `beeperMode_e`, а не по таблице:

```text
    'beeper -RX' -> Disabled RX_LOST
    'beeper -ARM' -> Disabled ARMING
  beeper_off_flags = 0x00020013 -> off: ['GYRO_CALIBRATED', 'RX_LOST', 'ARMING', 'ON_USB']
    'beacon RX_LOST' -> Enabled RX_LOST
  dshotBeaconOffFlags = 0x00000200 -> beacon fires on: ['RX_LOST']
  decode 0x00800000: ['ARMING_GPS_NO_FIX']
  2025.12: removed ['CRASH_FLIP', 'RC_SMOOTHING_INIT_FAIL'], added ['CRASHFLIP']; ARMING_GPS_NO_FIX bit 23 -> 22
```

`beeper -RX`, набранное «для краткости», выключило самый нужный сигнал. Маски между 4.5 и 2025.12 не переносимы — переноси именами (и помни, что имя CRASH_FLIP в 2025.12 пишется CRASHFLIP).

### Шаг 5. Таймлайн RX_LOST и маяка
Модель `beeperUpdate()` на 100 Гц, `beacon RX_LOST` включён; «TX off» — момент, когда прошивка признала потерю сигнала:

```text
  A) never armed since power-up, TX off at 0 s: buzzer starts 0 times, DShot beacons 0
  B) armed 0 s, disarmed 1.0 s, TX off 1.5 s: buzzer on at [1.5, 2.51, 3.52, 4.53, 5.54] s
     DShot beacon at [2.5, 3.51, 4.52, 5.53] s (guard 1200 ms after disarm, interval > 950 ms)
  C) armed and TX off at 1.5 s (still armed): buzzer 2 starts, DShot beacons 0 (motors running)
  D) BEEPER switch on, disarmed: buzzer on at [0.0, 0.21, 0.42, 0.63, 0.84, 1.05, 1.26, 1.47] ... s
     DShot beacon at [0.0, 0.52, 1.04, 1.57, 2.09, 2.62] s (interval > 450 ms)
```

A — «выключил пульт на столе, а он молчит»: не было арма. B — первый маяк не раньше 2.2 с (дизарм + 1.2), затем раз в ~1 с. C — в арме маяка нет. D — тумблер BEEPER: маяк каждые ~0.52 с.

### Шаг 6. Конфиг
```
feature LED_STRIP
led 4 14,14:S:FW:0
led 10 0,0::C:0
set ledstrip_brightness = 30
beacon RX_LOST
aux 3 13 3 1700 2100 0 0
adjrange 5 0 4 900 2100 30 4 0 0
save
```

Остальные `led` — из шага 2. `aux 3 13 3 …` — BEEPER на AUX4 вверху; `adjrange … 30 …` — профиль ленты трёхпозиционным AUX5. Пока слот активен, движение AUX5 перебивает `set ledstrip_profile`. Индексы `aux`/`adjrange` бери свободные.

### Переход на реальное железо
**Пропы сняты, АКБ через ограничитель тока.**
1. До питания, мультиметром: 5 В↔GND ленты — не КЗ; GND ленты↔GND FC и DIN↔пад LED — звонятся; DIN↔5 В — нет.
2. `resource`, `timer show`, `dma show`: LED_STRIP не делит таймер с MOTOR. Каждый мотор крутится во вкладке Motors.
3. Амперметр в плюс ленты (предел 10 А). Все `led` временно `C:1` (белый): ток на `ledstrip_brightness` 100 и 30, напряжение на ленте под нагрузкой. Ток покоя — с лентой, погашенной режимом LEDLOW.
4. Тумблер BEEPER — RX_SET и, с `beacon RX_SET`, моторы ~2 раза в секунду. BEEPER MUTE — тишина.
5. Армь без пропов, дизарм, отсоедини USB, выключи пульт: пищалка 0.5/0.5 с, моторы — не раньше 1.2 с после дизарма, примерно раз в 0.5 с (в 4.5 — раз в ~1 с); лента в RACE/BEACON не меняется (failsafe в дизарме не активен), 4 Гц даёт тумблер BEEPER. Через 2 мин потрогай моторы и ESC.
6. Селектор профиля — три профиля по очереди, на OSD метка «LED PROFILE» (в 4.5 метки нет).

**Прерывание:** запах, горячая лента или BEC, перезагрузка FC на белом, 5 В под нагрузкой ниже 4.75 В, мотор дёрнулся от маяка, горячие моторы после маяка. Снять питание; разнести таймеры или питание ленты.

**Полёт** (по желанию, ночью, яркость 30 %): 2 мин висения; просадка напряжения в OSD не больше, чем без ленты, + 0.1 В.

Самопроверка: лабораторная выполнена, когда:
- (расчёт) скрипт запущен на исходнике (укажи версию), вывод шагов 1–5 приложен, объяснено, почему «SE» дал фиолетовый и почему `0,0::C:0` обрезает ленту;
- (расчёт) для своей раскладки посчитан худший ток и запас BEC, выбор «от FC / отдельный BEC» обоснован;
- (железо) приложены `timer show` / `dma show` без конфликта LED–MOTOR и замеры тока на 100 и 30 % с объяснением расхождения с моделью;
- (железо) показано: RX_LOST только после арма, маяк не раньше 1.2 с после дизарма, BEEPER MUTE глушит всё.

## diagnostics
- **Симптом:** лента не горит
  - Возможная причина: в прошивке нет LED_STRIP (фича слетает после перезагрузки), первая строка `led` нулевая, у пина нет DMA/таймера, включён LEDLOW.
  - Что сделать: `feature`, `led`, `resource`, `timer show`, `dma show`, вкладка Modes; пересобрать с опцией.
- **Симптом:** после подключения ленты ESC пищит «нет сигнала», мотор не крутится
  - Возможная причина: LED на таймере мотора или занял TIM1/TIM8, нужный bitbang.
  - Что сделать: `timer show`; перенести LED на другой пад или сменить `dshot_bitbang_timer`; проверить моторы без пропов.
- **Симптом:** мерцание, случайные цвета, горит только первый
  - Возможная причина: 3.3 В против 0.7·5 В, длинный провод данных, нет общей земли.
  - Что сделать: общая земля, резистор у ленты, буфер 74AHCT125 или диод в плюсе ленты.
- **Симптом:** зелёный горит красным; со второго светодиода «каша»
  - Возможная причина: `ledstrip_grb_rgb` (RGB/GRB) или лента RGBW.
  - Что сделать: один светодиод `C:6`; красный — сменить порядок; «каша» — GRBW.
- **Симптом:** горит только часть ленты
  - Возможная причина: нулевая `led` в середине или больше 32 без `LED_STRIP_64`.
  - Что сделать: найти `0,0::C:0` в `led`.
- **Симптом:** FC перезагружается или пропадает видео на белом
  - Возможная причина: просадка 5 В BEC.
  - Что сделать: замер под нагрузкой; отдельный BEC с общей землёй; яркость 30.
- **Симптом:** выключил пульт — аппарат молчит
  - Возможная причина: вставлен USB (2025.12) или не было арма после включения (4.5); `beeper -RX` или `-RX_LOST`; BEEPER MUTE; `-ON_USB` на USB-питании.
  - Что сделать: `beeper`, Modes, тест после арма без пропов.
- **Симптом:** моторы не пищат при потере сигнала
  - Возможная причина: `beacon` по умолчанию выключен; не DShot; < 1.2 с после дизарма; вставлен USB (в 4.5 USB маяку не мешал).
  - Что сделать: `beacon RX_LOST`, `get motor_pwm_protocol`, тест от батареи.
- **Симптом:** пищалка пищит постоянно с включения
  - Возможная причина: неверный `beeper_inversion` / `beeper_od`.
  - Что сделать: переключить, `save`, сверить с конфигом платы.

## checklist
- Худший ток (белый, 100 %, все светодиоды) посчитан, питание выбрано по нему
- Общая земля, резистор у первого светодиода, конденсатор на питании ленты
- `timer show` / `dma show`: LED_STRIP не делит таймер с MOTOR, моторы проверены
- Нет нулевой `led` в середине; светодиодов ≤ 32
- Направления у `F` выбраны с учётом порядка N,E,S,W
- `beeper` без сокращённых имён, RX_LOST включён, `beacon RX_LOST` включён
- BEEPER MUTE не на «забываемом» тумблере; RX_LOST проверен после арма без пропов

## references
- ledstrip.c — Betaflight 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/io/ledstrip.c | primary | A
- light_ws2811strip.c — Betaflight 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/drivers/light_ws2811strip.c | primary | A
- light_ws2811strip_hal.c (timer/DMA init) — Betaflight 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/drivers/stm32/light_ws2811strip_hal.c | primary | A
- beeper.c — Betaflight 2025.12.5 | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/io/beeper.c | primary | A
- failsafe.c — условие RX_LOST, Betaflight 2025.12.5 | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/flight/failsafe.c | primary | A
- beeper.c — Betaflight 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/io/beeper.c | primary | A
- beeper.h — conditions and DShot beacon constants, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/io/beeper.h | primary | A
- cli.c — led, color, mode_color, beeper, beacon, timer, dma | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/cli/cli.c | primary | A
- dshot_bitbang.c — pacer timer selection, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/drivers/stm32/dshot_bitbang.c | primary | A
- LED Strip — Betaflight docs | https://betaflight.com/docs/wiki/guides/current/LED-Strip-Functionality | primary | B
- Adafruit NeoPixel Überguide — powering and best practices | https://learn.adafruit.com/adafruit-neopixel-uberguide/power.md | secondary | B

## notes
Страница LED Strip на betaflight.com местами расходится с кодом (проверено на 4.5.6): BEACON мигает 2 раза в секунду, а не 1; `L` идёт от красного (≤ 20 %) к зелёному, а не от DEEP_PINK, и работает без датчика тока; «до трёх функций» — на деле одна базовая и любые оверлеи в пределах 10 символов. Базовые функции `P` (GPS-полоса), `E` (полоса заряда), `U` (высота) есть только с 2025.12. 60 мА на светодиод — ориентир Adafruit; у твоей ленты ток другой, поэтому замер в шаге 3 железа обязателен.
