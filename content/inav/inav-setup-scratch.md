---
id: inav-setup-scratch
title: "INAV с нуля: GPS-квадрокоптер"
level: L2
readingTime: 50 мин
firmware: INAV 7/8 (проверено на 8.0.1; имена параметров совпадают в 9.x)
status: published
added: 2026-11-10
tags:
  - INAV
  - настройка
  - SITL
  - failsafe
  - калибровка
related:
  - inav-intro
  - inav-gps
  - inav-missions
  - link-elrs
  - f-motors-esc
  - bf-modes-osd
next:
  - inav-missions
---

## summary
Один GPS-квадрокоптер проходит путь от пустой платы до записанного висения, POSHOLD и RTH — в порядке 17 шагов настройки. Остальные INAV-модули объясняют отдельные части: что такое RTH, как работает оценщик, как писать миссии. Здесь собрана вся цепочка, включая шаги, которых в курсе раньше не было: bind и карта каналов, протокол моторов, порядок и вращение моторов, калибровка ESC, калибровка напряжения и тока (`vbat_scale`, `current_meter_scale`, `current_meter_offset`), failsafe с процедурой RTH, наземные проверки навигации и первый полёт с критериями прерывания. Основной путь — INAV SITL: всё, что относится к конфигурации, делаешь без железа. Шаги, которые требуют реального железа, отдельно расписаны для стола и для поля. Лабораторная: `diff all` из SITL и с реального аппарата, расчёт калибровки АКБ, лог висения и записанный failsafe → RTH.

## theory
### Карта шагов: что, где и чем
{{diagram:inav-setup-flow|17 шагов идут строго по порядку: всё, что касается конфигурации, проверяется в SITL; bind, моторы, ESC и АКБ — только на столе без пропов; пропы ставятся на шаге 15, не раньше.}}

| # | Шаг | Где | INAV: вкладка / CLI | Подробно |
|---|---|---|---|---|
| 1 | Прошивка, бэкап старого конфига | SITL, стол | Firmware Flasher, `diff all` | inav-intro |
| 2 | Платформа, миксер | SITL | Mixer, `platform_type`, `mmix` | inav-intro |
| 3 | Порты UART | SITL | Ports, `serial` | здесь |
| 4 | Приёмник, bind | стол | Receiver, `receiver_type`, `serialrx_provider` | link-elrs |
| 5 | Карта каналов, концы, центры | SITL + стол | `map`, `rxrange`, `min_check`/`max_check` | здесь |
| 6 | Протокол моторов | стол | Outputs, `motor_pwm_protocol` | f-motors-esc |
| 7 | Порядок и вращение моторов | стол, без пропов | Outputs (тест моторов), Mixer Wizard | здесь |
| 8 | Калибровка ESC (только PWM) | стол, без пропов | Outputs, мастер-ползунок | здесь |
| 9 | Акселерометр, компас | стол, поле | Setup / Calibration, `align_mag` | inav-gps |
| 10 | Напряжение и ток | стол + полёт | `vbat_scale`, `current_meter_scale`, `current_meter_offset` | здесь |
| 11 | Режимы, арм, блокировки | SITL | Modes, `aux`, `status` | inav-intro |
| 12 | Failsafe: настроить и проверить | SITL + стол + поле | `failsafe_procedure = RTH` | здесь, bf-failsafe |
| 13 | OSD и видео | стол | OSD, `osd_video_system` | bf-modes-osd, link-vtx |
| 14 | GPS, дом, RTH | SITL + поле | `nav_rth_*` | inav-gps |
| 15 | Предполётная проверка, первое висение | поле | — | здесь |
| 16 | Первая настройка | поле | `nav_mc_hover_thr`, фильтры, EZ Tune | здесь, bf-filters |
| 17 | Лог, `diff all`, восстановление | SITL + поле | Blackbox, CLI | здесь |

### Что умеет INAV SITL, а что нет
SITL — это та же прошивка INAV, скомпилированная обычным gcc под ПК (`cmake -DSITL=ON`). Сборку можно запустить вручную или с вкладки SITL в Configurator. Датчики (гироскоп, акселерометр, баро, компас, GPS) работают в режиме FAKE: данные для них даёт симулятор. UART заменены TCP-портами: UART1 = 5760, UART2 = 5761 и так далее. Configurator подключается кнопкой «SITL» или по TCP `localhost:5760`.

Без симулятора SITL работает в режиме «Configurator only»: миксер, порты, режимы, failsafe и `diff all` настраиваются как на настоящей плате, но аппарат не летит. Полёт даёт только внешний симулятор: RealFlight 9.5S / Evolution или X-Plane. Для квадрокоптера реально подходит только RealFlight (платный, Windows): плагин INAV-X-Plane-HITL поддерживает только платформу Airplane. Чего SITL не умеет в принципе:
- **DShot.** В SITL нет `USE_DSHOT`, и `config.c` при загрузке молча меняет DSHOT300 на MULTISHOT — это проверено ниже, в шаге 6.
- **Bind, вращение моторов, ESC, делитель напряжения, шунт тока, компас на реальном корпусе.** Всё это физика конкретного аппарата, в SITL её нет.
- **Аналоговое OSD.** Есть только MSP DisplayPort через INAV-Sim-OSD.

### Калибровка АКБ: формулы из исходника
`src/main/sensors/battery.c` (INAV 8.0.1) считает:
- напряжение: `V = ADC · vbat_scale · 3300 / (4095 · 1000)`, то есть показания **прямо пропорциональны** `vbat_scale`. Отсюда **new = old × V_мультиметр / V_INAV**;
- ток: `I = (U_датчика − offset) / scale`. `current_meter_scale` задаётся в 0.1 мВ/А (400 = 40 мВ/А). Показания **обратно пропорциональны** scale, поэтому **new = old × мА·ч_INAV / мА·ч_зарядки** — это формула из docs/Battery.md;
- смещение: в коде из напряжения датчика вычитается `offset × 100` мкВ, так что фактическая единица `current_meter_offset` — 0.1 мВ, хотя Settings.md пишет «millivolts». На практике удобнее считать в токе: offset убирает из показаний `offset / scale` ампер. Поправка: **new_offset = old_offset + (I_INAV − I_амперметр) × scale**.

Порядок: сначала scale по мА·ч (полёт с расходом больше 50 % ёмкости), потом offset по току покоя и контрольный полёт. Ток в полёте в 20–40 раз больше тока покоя, поэтому ошибка offset почти не влияет на расчёт scale.

### Failsafe в INAV
Failsafe срабатывает, если пропали кадры по любому из каналов крена, тангажа, газа или рыскания, если канал вышел за `rx_min_usec`…`rx_max_usec` (885…2115) или если включён режим FAILSAFE. Срабатывание идёт через `failsafe_delay` = 5 (0.5 с), дальше выполняется процедура `failsafe_procedure`: LAND (по умолчанию), DROP, RTH или NONE. Для GPS-квадрокоптера выбирай RTH. Важно знать четыре вещи:
- **RTH требует GPS, компас и баро.** Если какого-то датчика нет в момент срабатывания, сразу начинается аварийная посадка со скоростью `nav_emerg_landing_speed` (500 см/с).
- **`failsafe_throttle_low_delay`** (0 = выключено): если газ долго был внизу, аппарат считается стоящим на земле и просто дизармится.
- **`failsafe_min_distance`** с `failsafe_min_distance_procedure` (по умолчанию DROP): вблизи дома работает другая процедура. Оставь 0, пока не понимаешь, зачем это нужно.
- **Выход из failsafe.** При `failsafe_stick_threshold` = 50 RTH не прерывается, пока ты не двинешь стик больше чем на 50 µs. Так связь на краю зоны покрытия не дёргает аппарат туда-обратно.

Приёмник должен при потере связи перестать слать каналы. ELRS по CRSF так и делает. PWM/SBUS-приёмник настраивают на «no pulses» и проверяют, что он не держит последние значения (подробно — модули link-elrs и bf-failsafe).

## practice
### Шаг 1. Собрать и запустить SITL, сохранить исходный конфиг
Самый быстрый путь — вкладка SITL в Configurator 7/8: Start, затем Connect через «SITL». Чтобы видеть, что происходит внутри, собери SITL сам: на gcc 13.3 сборка заняла 19 секунд.

```bash
git clone --depth 1 -b 8.0.1 https://github.com/iNavFlight/inav.git && cd inav
mkdir build_SITL && cd build_SITL && cmake -GNinja -DSITL=ON .. && ninja
./inav_8.0.1_SITL          # в отдельной папке: там появится eeprom.bin
```

```text
INAV 8.0.1 SITL (ae47bcba)
[SIM] No interface specified. Configurator only.
[EEPROM] Unable to load eeprom.bin
[SOCKET] Bind TCP 0.0.0.0:5760 to UART1
[SOCKET] Unable to bind socket
```

Вторая строка с bind — это UART2 (порт 5761): его занял другой процесс, у меня это был Betaflight SITL. Для Configurator хватает UART1. Перед любыми изменениями сохрани `diff all` — на реальной плате это бэкап старого конфига перед прошивкой. `status` на чистом SITL показывает `GYRO=FAKE, ACC=FAKE, BARO=FAKE, MAG=FAKE` и строку `Arming disabled flags: CAL ACC RX CLI`.

### Шаг 2–3. Миксер и порты
Пресет Quad X на вкладке Mixer — это четыре строки `mmix`. Configurator берёт их из `js/model.js`, а CLI выводит ровно так:

```text
mmix 0  1.000 -1.000  1.000 -1.000      # 1: задний правый, CW
mmix 1  1.000 -1.000 -1.000  1.000      # 2: передний правый, CCW
mmix 2  1.000  1.000  1.000  1.000      # 3: задний левый, CCW
mmix 3  1.000  1.000 -1.000 -1.000      # 4: передний левый, CW
```

Колонки: газ, крен, тангаж, рыскание. Знак рыскания показывает направление вращения: мотору 1 при команде «рыскание по часовой» нужно замедлиться (−1), значит, он крутится по часовой (CW). Это раскладка «пропы внутрь»; для «пропы наружу» ставь `motor_direction_inverted = ON`.

Порты задаются командой `serial <n> <функции> <msp> <gps> <telem> <periph>`, функции — это битовая маска: MSP = 1, GPS = 2, RX_SERIAL = 64, BLACKBOX = 128, MSP_OSD (DisplayPort) = 33554432. В SITL я включил MSP на UART3 (`serial 2 1 115200 115200 0 115200`), и после перезагрузки появился порт `Bind TCP 0.0.0.0:5762 to UART3`. На реальной плате обычно так: `serial 1 64 …` — приёмник на UART2, `serial 2 2 …` — GPS на UART3.

### Шаг 4–5. Приёмник и карта каналов — проверка в SITL
В SITL приёмник подключают через `receiver_type = MSP`. Скрипт на Python 50 раз в секунду шлёт в порт 5762 `MSP_SET_RAW_RC` (код 200) в порядке AETR: крен 1500, тангаж 1500, газ 1000, рыскание 1500, AUX1 1000. Обратно он читает `MSP_RC` (105) — каналы уже после `map`, во внутреннем порядке INAV: крен, тангаж, рыскание, газ.

```text
### 1. no RC source
Arming disabled flags: CAL NAV ACC RX CLI
### 2. MSP RC at 50 Hz
Arming disabled flags: CAL NAV ACC CLI
MSP_RC ch1-8: (1500, 1500, 1500, 1000, 1000, 1000, 1500, 1500)
### 3. RC stopped 2 s ago
Arming disabled flags: CAL NAV ACC RX CLI
```

Флаг `RX` исчезает, пока идут кадры, и возвращается через 0.5 с после их пропажи — это та же логика, по которой срабатывает failsafe. С `map AETR` газ (четвёртое значение) равен 1000, как и задумано. Если ошибиться и поставить `map TAER`, получится:

```text
MSP_RC ch1-8: (1500, 1000, 1500, 1500, 1000, 1000, 1500, 1500)
```

Газ теперь 1500, а тангаж 1000. Такой аппарат не заармится (флаг `THR`), а если обойти блокировку — сорвётся с места. Для ELRS/CRSF правильная карта — AETR, это значение по умолчанию.

### Шаг 6. Протокол моторов: то, чего SITL не умеет
После `set motor_pwm_protocol = DSHOT300` и `save` SITL отвечает так:

```text
motor_pwm_protocol = MULTISHOT
```

Это `#if !defined(USE_DSHOT)` в `fc/config.c`. Вывод: протокол, порядок и вращение моторов, калибровку ESC проверяют только на столе (раздел про железо ниже).

### Шаг 10. Калибровка АКБ — расчёт
Это пример с реального 4S 1500 мА·ч (числа повторяются в разделе про железо). Мультиметр на балансире показывает 16.42 В, `status` в INAV — 15.95 В при `vbat_scale` = 1100. После полёта INAV насчитал 1120 мА·ч, а зарядное вернуло 1030 мА·ч. Ток покоя (FC, приёмник, VTX) по амперметру лабораторного блока питания — 0.45 А, INAV показывает 0.69 А.

```python
old_vs, v_meter, v_inav = 1100, 16.42, 15.95
new_vs = round(old_vs * v_meter / v_inav)                  # V ∝ scale
old_cs, mah_inav, mah_charger = 400, 1120, 1030
new_cs = round(old_cs * mah_inav / mah_charger)            # I ∝ 1/scale
old_off, i_inav, i_meter = 0, 0.69, 0.45
new_off = round(old_off + (i_inav - i_meter) * new_cs)     # offset/scale = амперы
```

```text
vbat_scale 1100 -> 1132; after: 16.414 V, error 1.5 mV/cell
current_meter_scale 400 -> 435 (mAh error before +8.7 %)
current_meter_offset 0 -> 104 (removes 0.24 A)
```

{{diagram:chart-inav-vbat-cal|При vbat_scale 1100 напряжение занижено на 90–120 мВ на банку: OSD покажет «посадку» позже реальной. После 1132 ошибка 1.5 мВ на банку во всём диапазоне 4S, потому что ошибка делителя пропорциональна напряжению и исправляется одним коэффициентом.}}

### Шаг 11–12, 14. Режимы, failsafe, RTH — конфиг и проверка в SITL
```text
aux 0 0 0 1700 2100        # ARM: AUX1 вверху
aux 1 1 1 900 2100         # ANGLE: всегда включён на AUX2
aux 2 11 1 1300 1700       # NAV POSHOLD: AUX2 в середине
aux 3 10 1 1700 2100       # NAV RTH: AUX2 вверху
set failsafe_procedure = RTH
set nav_rth_altitude = 3000            # 30 м; AT_LEAST, climb_first ON, landing ALWAYS — уже по умолчанию
set bat_cells = 4
set battery_capacity = 1500
set battery_capacity_warning = 450
set battery_capacity_critical = 300
set vbat_scale = 1132
set current_meter_scale = 435
set current_meter_offset = 104
set nav_mc_hover_thr = 1380
```

Второе число в `aux` — постоянный id режима, а не порядковый номер: ARM = 0, ANGLE = 1, NAV ALTHOLD = 3, NAV RTH = 10, NAV POSHOLD = 11, FAILSAFE = 27 (таблица в `fc_msp_box.c`). Без симулятора SITL не армится: в `status` остаются флаги `CAL NAV ACC`, то есть датчики калибруются, нет GPS-фикса, акселерометр не откалиброван. Значит, полный тест «выключил пульт → RTH → посадка» в SITL проходит только с RealFlight. В этом случае перед RTH отлети на 100 м, выключи передачу RC и измерь расстояние точки посадки от дома по карте Configurator. Без RealFlight в SITL проверяешь цепочку до срабатывания: пропадание RC даёт флаг `RX` (шаг 4–5), процедура RTH стоит в конфиге.

### Шаг 17. diff all и проверка восстановления
`diff all` после настройки (фрагмент):

```text
# master
set acc_hardware = FAKE
set mag_hardware = FAKE
set baro_hardware = FAKE
set receiver_type = MSP
set motor_pwm_protocol = MULTISHOT
set failsafe_procedure = RTH
set vbat_scale = 1132
set current_meter_scale = 435
set current_meter_offset = 104
set gps_provider = FAKE
set nav_rth_altitude = 3000
```

Проверка бэкапа: я стёр `eeprom.bin`, вставил в CLI все 56 командных строк diff (от `batch start` до `save`) и снова снял `diff all`. Все строки `set`, `aux`, `mmix`, `serial` совпали. Бэкап, который никогда не восстанавливали, — это ещё не бэкап. Важно: **не переноси SITL-diff на настоящую плату целиком**. Строки `*_hardware = FAKE`, `receiver_type = MSP`, `gps_provider = FAKE` и `serial` для TCP нужны только в SITL. С реального аппарата снимают свой diff.

### Переход на реальное железо
Безопасность: пропы сняты до шага «Первое висение». Первую подачу питания делай через smoke stopper или лабораторный блок с ограничением 1–2 А. Аппарат лежит на столе, перед ним никого нет.

**1. Прошивка.** Сохрани `diff all` старой прошивки в файл. В Firmware Flasher выбери target своей платы и сделай Full chip erase. Configurator должен совпадать с прошивкой по мажорной версии. После прошивки — миксер Quad X (Load and apply) и `align_board_*`, если плата повёрнута.

**2. Приёмник и каналы.** Bind ELRS: binding phrase или bind-режим, как в link-elrs. Дальше `receiver_type = SERIAL`, `serialrx_provider = CRSF`, на UART приёмника функция RX_SERIAL (64). На вкладке Receiver каждый стик двигает свою полоску. Нормы:
| Положение | Норма | Если нет |
|---|---|---|
| Газ внизу | < `min_check` (1100); у ELRS обычно около 988 | концы (limits) на пульте |
| Газ вверху | > `max_check` (1900) | концы на пульте |
| Центр крена, тангажа, рыскания | 1500 ± 5 | subtrim на пульте, триммеры в 0 |
| AUX1 (ARM) | две позиции: < 1300 и > 1700 | микшер пульта |

**3. Протокол и моторы.** Для BLHeli_S, BLHeli_32 и AM32: `motor_pwm_protocol = DSHOT300`, `throttle_idle` = 8 % (по умолчанию в 8.x, в 7.1 — 15 %; для 5" обычно хватает 5–8 %). PWM-ESC: STANDARD или ONESHOT125 плюс калибровка (п. 4). Тест: подключи АКБ, Outputs → включи тест моторов, по очереди подними каждый мотор до ~1100. Мотор, который откликается, должен стоять на месте с тем же номером на схеме Quad X: 1 — задний правый CW, 2 — передний правый CCW, 3 — задний левый CCW, 4 — передний левый CW. Вращение смотри по полоске скотча на колоколе. Неверный порядок исправляет Motor Mixer Wizard на вкладке Mixer: ты кликаешь положение каждого отзывающегося мотора. Неверное направление — реверс в ESC-конфигураторе или перестановка двух фазных проводов.

**4. Калибровка ESC (только PWM/OneShot).** Пропы сняты, АКБ отключена. Outputs → включи тест, мастер-ползунок в максимум (2000). Подключи АКБ, дождись сигнала максимума, затем мастер-ползунок в минимум (1000), дождись сигнала подтверждения, отключи АКБ. После этого все моторы должны трогаться с места одновременно, разброс на ~1050 — не больше одного-двух тиков. DShot-ESC калибровать не нужно: команда цифровая.

**5. Датчики.** Акселерометр — 6 положений на ровном столе. Компас: на улице, вдали от машины и арматуры, кнопка Calibrate Compass, `mag_calibration_time` = 30 с. Вращай аппарат по всем осям. Склонение берётся из GPS (`inav_auto_mag_decl = ON`). Затем наземная проверка курса, дома и высоты из inav-intro (шаг 3б): курс ±10° на четырёх сторонах света, дистанция до дома ±2 м на 20 м.

**6. АКБ.** Вольтметр на балансир → `vbat_scale` по формуле, допуск 50 мВ на банку. Ток покоя по амперметру лабораторного блока → `current_meter_offset`. Полёт с расходом больше 50 % ёмкости → зарядка → `current_meter_scale`. Контрольный полёт: расхождение мА·ч INAV и зарядки меньше 5 %. Затем `bat_cells`, `battery_capacity`, warning и critical — 30 % и 20 % ёмкости.

**7. Failsafe на столе.** Пропы сняты, АКБ подключена, пульт включён. Выключи пульт: на вкладке Receiver каналы замирают, в `status` появляется флаг `RX`, в OSD — предупреждение о failsafe. Включи пульт — флаг уходит. Армить на столе ради этого теста не нужно, процедуру RTH проверяют в поле.

**8. OSD и видео.** Аналог: `osd_video_system = AUTO` или PAL. HD (DJI, Walksnail, HDZero): функция MSP_OSD на UART VTX и `osd_video_system = DJIWTF`, AVATAR или HDZERO. Минимум элементов: напряжение, мА·ч, спутники, дистанция и стрелка домой, режим полёта, LQ/RSSI. Подробно — bf-modes-osd и link-vtx.

**9. Предполётная проверка и первое висение (пропы ставятся здесь).** Пропы проверь по направлению вращения. На площадке: 3D-фикс, не меньше 10 спутников (`gps_min_sats` = 6 — это минимум для фикса, а не для навигации), HDOP ≤ 2, дом записан. Blackbox включён. Арм в ANGLE, висение на 1–2 м 60 с. Прерывай и сажай, если:
- аппарат трясётся или осциллирует на висении;
- без стиков его сносит больше 1 м/с в штиль (подтримь акселерометр);
- газ висения выше 60 %;
- после 60 с хоть один мотор горячий.

Газ висения запиши из OSD или лога и поставь его в `nav_mc_hover_thr` (в примере 1380). Иначе ALTHOLD при включении «проваливается».

**10. POSHOLD и RTH.** На 5–10 м переключись в POSHOLD: в штиль аппарат держит точку ±1–2 м. «Кружение унитазом» (toilet bowl) — признак проблемы с компасом: вернись в ANGLE и сядь. RTH сначала тумблером с 30–50 м, потом со 100 м на высоте 20 м: аппарат набирает `nav_rth_altitude` (30 м), летит домой и садится. Расстояние точки посадки от дома измерь рулеткой или по последней точке лога. Затем failsafe-тест: на 50–100 м выключи пульт. Через 0.5 с должен начаться RTH. Включи пульт и двинь стик — управление возвращается.

**11. Первая настройка.** Для первых полётов хватает дефолтов INAV 8: `gyro_main_lpf_hz` = 60, динамический notch (`dynamic_gyro_notch_enabled = ON`). RPM-фильтр (`rpm_gyro_filter_enabled`) включай только при работающей ESC-телеметрии оборотов. Быстрый тюнинг — EZ Tune (`ez_enabled = ON`, ползунки response, damping, stability). PID трогай после разбора Blackbox, подробно — bf-filters и bf-pid.

**12. Бэкап.** CLI → `diff all` → сохрани в файл с датой и версией. Blackbox-лог первого висения сохрани рядом.

Лабораторная засчитывается, когда:
- **SITL**: собран или запущен SITL 7/8. `diff all` содержит Quad X (4 строки `mmix`), `aux` для ARM, ANGLE, POSHOLD и RTH, `failsafe_procedure = RTH` и рассчитанные `vbat_scale`, `current_meter_scale`, `current_meter_offset`. Флаг `RX` появляется при остановке RC (лог CLI приложен). Восстановление diff из файла проверено. Если есть RealFlight — RTH со 100 м садится не дальше 3 м от дома.
- **Железо**: таблица каналов заполнена, порядок и вращение моторов совпадают с Quad X. Ошибка напряжения меньше 50 мВ на банку, мА·ч INAV в пределах 5 % от зарядного. Записан Blackbox 60-секундного висения, `nav_mc_hover_thr` взят из него. RTH со 100 м садится не дальше 5 м от дома. Failsafe → RTH записан в лог или на видео OSD. `diff all` с реального аппарата сдан вместе с логом.

## diagnostics
- **Симптом:** SITL пишет `[SOCKET] Unable to bind socket`
  - Возможная причина: порт 5760/5761 занят другим SITL (INAV или Betaflight) или старым процессом.
  - Что сделать: закрыть процесс; Configurator подключается к UART1, поэтому ошибка на UART2 не мешает.
- **Симптом:** после `save` вместо DSHOT стоит MULTISHOT
  - Возможная причина: это SITL или target без `USE_DSHOT`; `config.c` подменяет протокол.
  - Что сделать: в SITL это нормально; на реальной плате проверить target и выход моторов.
- **Симптом:** не армится, в `status` есть флаг `RX`
  - Возможная причина: нет кадров приёмника — неверный UART, `serialrx_provider`, нет bind.
  - Что сделать: вкладка Receiver, Ports, повторить bind.
  - Что видно в логе: флаг пропадает, как только идут кадры (шаг 4–5).
- **Симптом:** в Receiver газ двигает другой канал, аппарат не армится с флагом `THR`
  - Возможная причина: неверный `map` (TAER вместо AETR).
  - Что сделать: `map AETR` для CRSF, проверить по полоскам Receiver.
- **Симптом:** при первом арме аппарат переворачивается или раскручивается на месте
  - Возможная причина: моторы не в том порядке или крутятся не в ту сторону для Quad X.
  - Что сделать: снять пропы, тест моторов, Motor Mixer Wizard, реверс в ESC.
  - Последствия: сломанные пропы и рамы; это ловится на столе за 5 минут.
- **Симптом:** OSD показывает «батарея пуста» намного раньше или позже реального
  - Возможная причина: не откалиброван `vbat_scale` или `current_meter_scale`; scale исправлен не в ту сторону.
  - Что сделать: напряжение — old × V_мультиметр / V_INAV; ток — old × мА·ч_INAV / мА·ч_зарядки.
- **Симптом:** ток покоя в OSD 0.3–1 А при выключенных моторах вместо реального
  - Возможная причина: не выставлен `current_meter_offset`.
  - Что сделать: new = old + (I_INAV − I_амперметр) × scale, перепроверить после изменения scale.
- **Симптом:** при выключении пульта аппарат садится на месте вместо RTH
  - Возможная причина: `failsafe_procedure` = LAND (по умолчанию), нет GPS-фикса или компаса, сработал `failsafe_min_distance` или аппарат ближе `nav_min_rth_distance` (5 м).
  - Что сделать: проверить процедуру и датчики, повторить тест дальше 50 м.
- **Симптом:** при включении ALTHOLD или POSHOLD аппарат проседает или подпрыгивает
  - Возможная причина: `nav_mc_hover_thr` (1300 по умолчанию) далёк от реального газа висения.
  - Что сделать: взять газ висения из Blackbox первого висения.

## checklist
- SITL запущен, Configurator подключён, исходный `diff all` сохранён
- Quad X, порты, приёмник, `map AETR` проверены (флаг `RX` ведёт себя как ожидается)
- Протокол, порядок и вращение моторов проверены на столе без пропов; PWM-ESC откалиброваны
- `vbat_scale`, `current_meter_scale`, `current_meter_offset` рассчитаны по формулам из исходника и проверены
- `failsafe_procedure = RTH`, failsafe проверен на столе и в поле
- Компас откалиброван, курс, дом и высота проверены на земле
- Висение 60 с с Blackbox, `nav_mc_hover_thr` из лога, POSHOLD и RTH проверены
- `diff all` с реального аппарата и лог сохранены, восстановление проверено

## references
- INAV SITL | https://github.com/iNavFlight/inav/blob/master/docs/SITL/SITL.md | primary | A
- INAV Building SITL | https://github.com/iNavFlight/inav/blob/master/docs/development/Building%20SITL.md | primary | A
- INAV Settings reference | https://github.com/iNavFlight/inav/blob/master/docs/Settings.md | primary | A
- INAV Battery (vbat_scale, current meter) | https://github.com/iNavFlight/inav/blob/master/docs/Battery.md | primary | A
- INAV battery.c (формулы напряжения и тока) | https://github.com/iNavFlight/inav/blob/master/src/main/sensors/battery.c | primary | A
- INAV Failsafe | https://github.com/iNavFlight/inav/blob/master/docs/Failsafe.md | primary | A
- INAV Mixer | https://github.com/iNavFlight/inav/blob/master/docs/Mixer.md | primary | A
- INAV Controls (стики, throttle_idle, min_check) | https://github.com/iNavFlight/inav/blob/master/docs/Controls.md | primary | A
- INAV Configurator (вкладки SITL, Mixer Wizard) | https://github.com/iNavFlight/inav-configurator | primary | A
- INAV-X-Plane-HITL setup (только Airplane) | https://github.com/RomanLut/INAV-X-Plane-HITL/blob/main/doc/setup.md | secondary | B
