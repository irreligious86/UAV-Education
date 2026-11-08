---
id: ap-tuning
title: "Тюнинг ArduPilot: AUTOTUNE, фильтры, notch по ESC"
level: L3
readingTime: 40 мин
firmware: ArduPilot
status: published
added: 2026-11-08
tags:
  - AUTOTUNE
  - harmonic notch
  - тюнинг
  - ArduPilot
related:
  - ap-logs
  - bf-filters
  - ctl-signals
  - ctl-theory
  - ap-heavy
next:
  - ap-safety-fs
---

## summary
Тюнинг ArduCopter — не «запустить AUTOTUNE», а семь шагов в правильном порядке: параметры под размер аппарата → первый стабильный полёт → оценка → гармонический notch по шуму моторов → ручной/QuikTune roll-pitch → AUTOTUNE по осям → input shaping под ощущение. Модуль проходит их с параметрами и проверкой по логу (`ATT`, `RATE`, `VIBE`, спектры из батч-сэмплинга/raw IMU), объясняет, что AUTOTUNE делает внутри (и почему он требует шума ниже порога), и как настроить notch с трекингом по ESC-телеметрии или газу. Лабораторная в SITL и в поле.

## theory
### Шаг 1. Параметры до первого полёта
Стартовые значения зависят от размера пропа (документ «Setting the Aircraft Up for Tuning»): `INS_GYRO_FILTER` (20 Гц для 10"+, 40 для 7", 80 для 5"), `ATC_RAT_*_FLTD/FLTE/FLTT` (D/E/T фильтры рейтов — половина от гиро-фильтра для D), `MOT_THST_EXPO` (0.65 для 10", 0.55–0.6 для 5"), `MOT_SPIN_ARM/MIN`, `MOT_THST_HOVER` (обучится, `MOT_HOVER_LEARN = 2`), `ATC_THR_MIX_MAN`, `PSC_ACCZ_P/I` под газ висения, `ATC_INPUT_TC` (ощущение стиков). Для больших/тяжёлых — заниженные начальные PID (`ATC_RAT_RLL_P/I` 0.05–0.1 вместо 0.135, D 0.002–0.004).

### Шаг 2–3. Первый полёт и оценка
Stabilize/AltHold на минимальном весе, полной АКБ («most agile configuration»). В логе: `RATE.RDes` vs `RATE.R` (запрос vs факт) — отслеживание без осцилляций; `ATT.DesRoll` vs `ATT.Roll`; `VIBE.VibeX/Y/Z` < 15–30 м/с², `Clip` = 0; `CTUN.ThO` (газ висения, обученный `MOT_THST_HOVER` 0.2–0.5). Осцилляции сразу → P/D вниз на 30–50%, не лететь дальше.

### Шаг 4. Гармонический notch
Шум моторов попадает в D-term и греет моторы; LPF с низкой частотой добавляет задержку (модуль «Сигналы и спектры»). Notch режет только частоты моторов:

1. **Найти частоту**: батч-сэмплинг (`INS_LOG_BAT_MASK = 1` — первый IMU; `INS_LOG_BAT_OPT`: 0 — сырые данные до фильтров, 2 — после фильтров, 4 — до и после на 1 кГц) или на H7 с 4.5+ — raw IMU logging (`INS_RAW_LOG_OPT`); полёт висение + мягкие манёвры; спектр в MAVExplorer/Filter Review Tool/своём Python.
2. **Включить**: `INS_HNTCH_ENABLE = 1`, перезагрузка.
3. **Режим** (`INS_HNTCH_MODE`): 3 — ESC-телеметрия (лучший, следит за каждым мотором, нужна телеметрия ESC или BLHeli bidir DShot); 1 — по газу (`INS_HNTCH_REF` = газ висения, `INS_HNTCH_FREQ` — частота на висении, пересчитывается с √(газ/ref); менять REF при смене нагрузки); 4 — FFT в полёте (F7/H7, один фильтр); 0 — статический.
4. **Полоса и глубина**: `INS_HNTCH_BW` (≈ половина FREQ для режима по газу, уже для ESC), `INS_HNTCH_ATT` (40 дБ типично), `INS_HNTCH_HMNCS` (битмаска гармоник: 3 = 1-я и 2-я, 7 = 1–3; «три гармоники обычно безопасно»), `INS_HNTCH_OPTS` (бит 1 — multi-source, по мотору; бит 2 — обновление на частоте петли при bidir DShot; бит 5 — откат на минимальную частоту при потере RPM; биты 0/1/4 не совмещать).
5. **Проверить**: лог с батч-сэмплингом после фильтров (`INS_LOG_BAT_OPT = 2`), пики моторов должны уйти на 20+ дБ; второй набор `INS_HNTC2_*` для резонанса рамы (статический).

### Шаг 5. Ручной roll/pitch или QuikTune
Обязательно до AUTOTUNE: AUTOTUNE стартует с текущих значений и прерывается при шуме. QuikTune (Lua-скрипт `quicktune.lua`, тумблер `QUIK_ENABLE`) поднимает P/D до первого звона и откатывает на `QUIK_GAIN_MARGIN` %. Вручную: D до звона → −30%, P до звона → −30%, I = P.

### Шаг 6. AUTOTUNE
Что делает: в AltHold/Loiter даёт серию коротких «пинков» по одной оси (twitch), измеряет отклик и ищет максимальные rate D, потом rate P (I = P), потом angle P, добиваясь заданного overshoot. Параметры: `AUTOTUNE_AXES` (битмаска: 1 roll, 2 pitch, 4 yaw, 8 yaw-D; лучше по одной оси за полёт на больших аппаратах), `AUTOTUNE_AGGR` (0.05–0.10, начинать с 0.10 по умолчанию; выше — агрессивнее и терпимее к шуму, ниже — отзывчивее), `AUTOTUNE_MIN_D` (нижняя граница D — чтобы не ушёл в ноль при шумном аппарате). Условия: ветер < 3 м/с, 20+ м высоты и пространства, АКБ полная, notch настроен. Результат сохраняется только при дизарме с включённым тумблером/в режиме AUTOTUNE (сообщение «Saved gains for …»); `RCx_OPTION = 180` позволяет переключаться между старыми и новыми коэффициентами для сравнения. Лог `ATUN` (обзор) и `ATDE` (детали каждого twitch) — видно, где остановился; GCS-сообщения «Twitch», «success 1/4» тоже в логе. Признак успеха: итоговые `ATC_RAT_*_D` выше `AUTOTUNE_MIN_D`.

### Шаг 7. Input shaping
`ATC_INPUT_TC` (0.15 плавно → 0.05 остро), `ATC_ACCEL_R/P/Y_MAX`, `ATC_RATE_R/P/Y_MAX`, `ATC_ANG_*_P` (AUTOTUNE ставит, можно смягчить). Это не устойчивость — это ощущение.

### Что смотреть после
`RATE.RDes/R` — отклик без перелёта > 10%; `RATE.ROut` (выход PID) без насыщения; `VIBE` не вырос; температура моторов; спектр после фильтров чистый; `PIDR.P/I/D` (логирование PID по оси при `LOG_BITMASK` с PID) — доля D-шума.

## practice
### Шаг 1. SITL
`sim_vehicle.py -v ArduCopter -f quad`: выставить стартовые параметры под 10", AUTOTUNE roll (`AUTOTUNE_AXES = 1`) в AltHold; посмотреть `ATUN` в логе, итоговые `ATC_RAT_RLL_*`. Повторить с `AUTOTUNE_AGGR = 0.05` — сравнить.

### Шаг 2. Notch в поле
Батч-сэмплинг до фильтров → спектр → частота на висении → `INS_HNTCH_*` (ESC-режим если есть телеметрия) → батч после фильтров → спектр до/после с числами в дБ.

### Шаг 3. QuikTune/ручной
Roll-pitch до первого звона, откат; лог `RATE` — проверка.

### Шаг 4. AUTOTUNE в поле
По одной оси за полёт; сохранить; контрольный полёт с логом; сравнение `RATE.RDes/R` до/после. Лабораторная: AUTOTUNE по roll выполнен, notch настроен со спектрами до/после, проверка по логу.

## diagnostics
- **Симптом:** AUTOTUNE прерывается «Failed to level»/не стартует
  - Возможная причина: ветер, высокие вибрации, плохой начальный тюн.
  - Что сделать: штиль, notch, ручной тюн, AltHold стабилен ≥ 1 мин.
- **Симптом:** после AUTOTUNE горячие моторы
  - Возможная причина: D высокое при шумном гироскопе.
  - Что сделать: notch/фильтры, `AUTOTUNE_MIN_D`, повторить.
- **Симптом:** notch по газу «промахивается» с грузом
  - Возможная причина: `INS_HNTCH_REF` под другой вес.
  - Что сделать: пересчитать REF или ESC-режим.
- **Симптом:** в спектре пик остался после notch
  - Возможная причина: резонанс рамы (не мотор) или гармоника вне HMNCS.
  - Что сделать: `INS_HNTC2_*` статический на резонанс; HMNCS = 7.
- **Симптом:** ватный отклик при хорошем тюне
  - Возможная причина: input shaping (`ATC_INPUT_TC` велик, ACCEL_MAX мал).
  - Что сделать: уменьшить TC, поднять ACCEL/RATE_MAX.

## references
- ArduPilot — Tuning Process Instructions | https://ardupilot.org/copter/docs/tuning-process-instructions.html | primary | A
- ArduPilot — Managing Gyro Noise with the Dynamic Harmonic Notch Filters | https://ardupilot.org/copter/docs/common-imu-notch-filtering.html | primary | A
- ArduPilot — AutoTune | https://ardupilot.org/copter/docs/autotune.html | primary | A

## checklist
- Знаю семь шагов тюнинга и их порядок
- Стартовые параметры выставлены по размеру аппарата
- Notch настроен, спектры до/после сняты
- AUTOTUNE выполнен по оси, результат проверен по RATE
- Понимаю, что AUTOTUNE делает и почему падает при шуме
