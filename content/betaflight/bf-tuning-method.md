---
id: bf-tuning-method
title: "Метод A/B: тюнинг как эксперимент"
level: L2
readingTime: 45 мин
firmware: Betaflight 4.5 (сверено с исходником 4.5.3); отличия 2025.12 отмечены
status: published
added: 2026-11-25
tags:
  - Betaflight
  - тюнинг
  - Blackbox
  - A/B
  - статистика
related:
  - bf-pid
  - bf-blackbox
  - bf-motor-balance
  - bf-adjustments
  - bf-filters
  - data-python
  - math-prob-est
next:
  - bf-adjustments
---

## summary
«С новым D стало мягче» — гипотеза, а не результат. Модуль превращает сравнение двух настроек в эксперимент: одно изменение, одна программа полёта, порядок ABBA в одном окне условий, метрики лога с точными определениями и минимальная статистика — разброс, отношение эффекта к стандартной ошибке, перестановочный тест (permutation test). Разобрано, что Betaflight 4.5 переключает в полёте: профиль рейтов — да, PID-профиль — штатно нет, один PID-коэффициент — да, абсолютным слотом `adjrange`. Лабораторная — скрипт на Python: CSV от `blackbox_decode` → манёвры → пять метрик → вердикт с p. На синтетике с известным эффектом (−15 % пропвоша) одна пара полётов ничего не решает, пять пар в порядке ABBA эффект находят, тот же объём блоками AAAAA BBBBB его теряет.

## theory
### Почему один полёт ничего не доказывает
Метрика пропвоша по двум полётам одной и той же настройки отличается на 5–15 % (ориентир курса; в модели лабораторной CV ≈ 8 %): другой порыв, другая банка, пилот раньше подхватил газ. Один полёт A против одного полёта B не даёт оценить разброс внутри плеча, и разницу в 13 % не отличить от шума. В лабораторной одна пара полётов показывает −32 % по перелёту и −33 % по запасу моторов, хотя B их не меняет вообще.

Ощущения — источник гипотез, а не решение. Пилот, который знает, что включил «новый лучший» профиль, летит и оценивает иначе (плацебо). В кейсе `bf-pid` (по одному полёту на профиль) лог поддержал «чётче» у SHARP и показал цену +45 % шума на моторах, которую руками не почувствуешь; по меркам этого модуля это гипотеза для A/B на 4–5 полётах на плечо.

Смешивающие факторы (confounders) меняются вместе с настройкой и сами сдвигают метрику:

| Фактор | Как искажает | Как держать |
|---|---|---|
| АКБ: заряд, просадка | на пустой банке растут задержка и пропвош | одна партия, одинаковый заряд и посадочное напряжение; ABBA; `vbat_sag_compensation` одинаковый |
| Нагрев моторов и ESC | метрики дрейфуют к концу сессии | одинаковая пауза между полётами, ABBA |
| Ветер | пропвош и ошибка слежения | до 5 м/с (`bf-pid`), запись в журнал, ABBA |
| Пропы | зазубрина или другая партия меняют вибрации | одни пропы на сессию; сменил — сессия заново |
| Пилот | разная резкость манёвров | одна программа, один пилот, слепой выбор |
| Аппарат | у «одинаковых» дронов разные ЦТ и моторы | A и B на одном аппарате (`bf-motor-balance`) |

{{lesson:bf-motor-balance|Перекос моторов и смещённый ЦТ сдвигают все метрики сильнее, чем шаг слайдера: сначала механика, потом A/B.}}

### Дизайн эксперимента
1. **Гипотеза** с целевой метрикой и порогом — до полётов. Пример: «B (`d_roll`/`d_pitch` 40/46 → 46/52 в 4.5) снизит пропвош не меньше чем на 10 %, не подняв шум на висении больше чем на 10 %». Заранее записанный порог не даёт потом выбрать метрику, которая «получилась».
2. **Одно изменение.** A — контроль без правок, B отличается одним параметром или слайдером.
3. **Программа полёта** одна для всех полётов (ниже), каждый манёвр кормит свою метрику.
4. **Порядок.** ABA: среднее двух A гасит линейный дрейф. ABBA ABBA…: плечи получают почти одинаковый дрейф. ABAB тоже работает, но у B всегда на полёт больше дрейфа. Блоки AAAAA BBBBB — худший вариант: весь дрейф сессии ложится на разницу.
5. **A/A-тест.** A против A той же программой показывает собственный шум метрики. Если он сравним с ожидаемым эффектом, нужно больше полётов или крупнее шаг.
6. **Слепой выбор.** Профиль на земле ставит помощник, пилот не знает, что летит, и записывает оценку 1–5 до разбора лога.

{{diagram:bf-ab-order|Число полётов одинаковое, решает порядок: в блоках AAAAA BBBBB дрейф ветра добавил B лишние +15 % пропвоша и съел эффект −15 %, в порядке ABBA дрейф разделился почти поровну (+13.2 % и +13.8 %).}}

Программа полёта (около 30 с, повторяется в каждом полёте; пороги разметки — ориентиры курса, ими пользуется скрипт лабораторной):

| Манёвр | Как | Метрика | Как скрипт находит участок |
|---|---|---|---|
| Висение | 5 с на 1.5–2 м, стики в центре | шум гироскопа | \|setpoint\| < 20 °/с по всем осям, газ 1300–1600, ≥ 2 с |
| Броски по крену | 5 рывков на полный стик по 0.25 с, пауза 0.75 с, знак чередуется | ошибка слежения, перелёт | \|setpoint[0]\| > 200 °/с дольше 50 мс |
| Панч | газ 100 % на 1–1.5 с | запас моторов | `rcCommand[3]` > 1900 дольше 0.3 с |
| Спуски | 3 раза: газ в ноль на 1–1.5 с, подхват на 70 % | пропвош | `rcCommand[3]` < 1150 дольше 0.5 с |

Первые и последние 3 с лога отбрасываются (взлёт и посадка), как в `bf-pid`.

### Как переключать A и B в Betaflight 4.5
Лучшие условия у A и B в одном полёте: одна банка, один ветер. Что умеет прошивка (проверено по исходнику):

- **Штатного способа переключить PID-профиль в полёте нет.** Функции нет в `fc/rc_adjustments.h`, режима — в `fc/rc_modes.h` (4.5.3 и 2025.12); `MSP_SELECT_SETTING` при арме PID-профиль молча игнорирует (`msp/msp.c`), стик-команды и вход в OSD-меню стиками работают только без арма. На земле: стиками (газ вниз + рыскание влево + крен влево / тангаж от себя / крен вправо → профили 1/2/3 в нумерации App, то есть `profile 0`/`1`/`2`, `fc/rc_controls.c`), OSD-меню, Betaflight App или `profile N` (N = 0–3; четвёртый профиль — только CLI, OSD или App). Сравнение PID-профилей — это отдельные полёты. Сами коэффициенты по MSP в полёте записать можно (`MSP_SET_PID`, `MSP_SET_PID_ADVANCED`, `MSP_SET_SIMPLIFIED_TUNING`, например Lua-скриптом пульта): только в RAM, без события в Blackbox — для A/B это не метод. В 4.5.3 есть ещё дыра: OSD-меню, открытое через CRSF-телеметрию, не проверяет арм и даёт сменить профиль в воздухе (в 2025.12 закрыто) — это опасно и методом не является.
- **Профиль рейтов — тумблером:** функция 12 RATE_PROFILE, режим выбора, 3 позиции (6 при `rate_6pos_switch = ON`, но профилей рейтов 4, позиции 5–6 ничего не делают): `adjrange 0 0 3 900 2100 12 3 0 0` для 3-позиционного AUX4. Только для рейтов, экспо и кривой газа: PID там нет.
- **Один PID-коэффициент — абсолютным слотом.** Если у шаговой функции задан `center`, значение берётся прямо из канала: `center + (rc − 1500) · scale / 500`, деление C отбрасывает дробь к нулю (`processContinuosAdjustments`). Двухпозиционный тумблер даёт ровно два значения:

```
# AUX4 (индекс 3), 2-позиционный тумблер: вниз = A, вверх = B (Betaflight 4.5)
adjrange 0 0 3 900 2100 20 3 43 3      # ROLL_D:  1000 -> 40, 2000 -> 46
adjrange 1 0 3 900 2100 17 3 49 3      # PITCH_D: 1000 -> 46, 2000 -> 52
```

20 и 17 — номера CLI функций ROLL_D и PITCH_D (номер CLI — позиция в `defaultAdjustmentConfigs[]` плюс 1, `bf-adjustments`). Комбинированная 8 PITCH_ROLL_D поставила бы обеим осям одно значение, а умолчания разные (40 и 46). Эндпоинты 988 и 2012 мкс дают −3.07 → −3 и +3.07 → +3, то есть 40 и 46; тумблер на 1100 мкс даст −2.4 → −2 и `d_roll` = 41. Диапазон 900–2100 — «всегда активен», и значение задаёт положение тумблера уже при включении. После эксперимента убери слоты и впиши выбранное значение через `set`.

Изменения пишутся событием `INFLIGHT_ADJUSTMENT` (код 13, `blackbox/blackbox.h`). В абсолютном режиме событие пишется при каждом изменении значения канала, даже если D не изменился: дрожащий канал (988 ↔ 989) засыпает `.event` повторами, граница A/B — первое событие с новым `value`. `blackbox_decode` кладёт события в `LOG00001.01.event` строками JSON: `{"name":"Inflight adjustment", "time":…, "data":{"adjustmentFunction":"ROLL_D","value":46}}`, время — тот же счётчик в микросекундах, что `time (us)` в CSV. Так находятся границы участков A и B. Действующий D в 4.5 показывает `debug_mode = D_MIN`: `debug[2]` — крен, `debug[3]` — тангаж, оба ×10 (`flight/pid.c`). В 2025.12 режим называется `D_MAX`, и поля другие: `debug[2]` — действующий D ×10 только по оси `gyro_filter_debug_axis`, `debug[3]` — множитель ×100. `d_roll` там база (30), верх — `d_max_roll` (40), и слот двигает базу: центр 43 поднял бы базу до 40/46 ≥ `d_max`, и динамический D выключился бы (он работает, только пока `d_max` > D, `flight/pid_init.c`). Для 2025.12 центр считай от базы: `adjrange 0 0 3 900 2100 20 3 33 3` (30/36) и `adjrange 1 0 3 900 2100 17 3 37 3` (34/40); верх `d_max_*` слотом не меняется (`bf-adjustments`).

Номера и имени профиля в заголовке лога нет, профиль узнаётся по значениям: `rollPID:45,80,40`, `d_min:…` (`grep -a rollPID LOG00001.BFL`). Перед взлётом проверяй профиль по OSD (`osd_pid_profile_name_pos`, имя — `profile_name`, до 8 символов).

### Метрики: точные определения
Пять метрик ощущений (motor noise, propwash RMS, bounce-back, entry lag, peak tracking) определены в `bf-pid`. Здесь пять величин для A/B, каждая сводится к одному числу на полёт:

| Метрика | Определение | Участок | Лучше |
|---|---|---|---|
| шум гироскопа | RMS `gyroADC[0]` и `gyroADC[1]` после полосового фильтра 100–250 Гц, °/с | висение | меньше |
| ошибка слежения (tracking error) | RMS(`setpoint[0]` − `gyroADC[0]`), °/с | бросок + 150 мс после | меньше |
| перелёт | (max gyro / max setpoint − 1) · 100 % в направлении броска | бросок + 150 мс | меньше (до нуля) |
| пропвош | RMS гироскопа крена и тангажа в полосе 20–70 Гц, °/с | от 0.3 с после сброса газа до 0.6 с после подхвата | меньше |
| запас моторов (headroom) | 100 % − 99-й перцентиль самого нагруженного мотора, % хода по заголовку `motorOutput` | панч | больше |
| температура моторов | вручную: ИК-термометр или палец в первые 30 с после посадки | после полёта | не выше A |

Значение полёта — медиана по манёврам: один кривой бросок не портит число. Полоса шума лежит выше полосы управления и пропвоша, поэтому лог нужен не реже 1 кГц (`blackbox_sample_rate` 1/8 при цикле PID 8 кГц; умолчание 1/4 даёт 2 кГц).

{{lesson:bf-pid|Пять метрик ощущений, ориентиры «хорошо/терпимо/проблема» для 5" и кейс с четырьмя профилями — там.}}

### Минимальная статистика
Единица повторения — полёт (или участок при переключении тумблером), а не манёвр: манёвры одного полёта делят батарею и ветер.

- **Эффект** Δ = x̄_B − x̄_A, в процентах от x̄_A.
- **Объединённый разброс** s_p = √[((n_A − 1)s_A² + (n_B − 1)s_B²) / (n_A + n_B − 2)], s — стандартное отклонение плеча. При одном полёте на плечо s не определено.
- **Стандартная ошибка разницы** SE = s_p · √(1/n_A + 1/n_B). **Ориентир курса:** эффект реален, если |Δ|/SE > 2 и перестановочный тест дал p < 0.05. При n = 5 само правило «2 SE» соответствует уровню около 0.08, так что решающим обычно становится p < 0.05.
- **Перестановочный тест.** Если B ничего не меняет, метки «A» и «B» случайны. Перебери все разбиения n_A + n_B чисел на две группы: p — доля разбиений, где |разница средних| не меньше наблюдённой. Нормальность не нужна, но есть предел: минимальное p = 2 / C(2n, n) при n полётах на плечо.

| n на плечо | разбиений C(2n, n) | минимальное p |
|---|---|---|
| 1 | 2 | 1.000 |
| 2 | 6 | 0.333 |
| 3 | 20 | 0.100 |
| 4 | 70 | 0.029 |
| 5 | 252 | 0.0079 |
| 6 | 924 | 0.0022 |

При трёх полётах на плечо p < 0.05 недостижим даже при идеальном разделении, при четырёх все B должны оказаться лучше всех A.

- **План:** n ≈ 16 · (CV/Δ)², CV — разброс от полёта к полёту, Δ — ожидаемый эффект, оба в долях среднего. Это около 80 % шанса поймать эффект правилом «2 SE» (16 ≈ 2 · (2 + 0.84)²), но не меньше 4. CV 8 %, Δ 15 % → 4.6 → 5 полётов. CV 12 %, Δ 10 % → 23.04 → 24: такой эффект за сессию не поймать, бери шаг крупнее.

{{diagram:chart-bf-ab-power|При разбросе 8 % эффект −15 % находится в 67 % серий при 4 полётах на плечо и в 92 % при 5; при 1–3 полётах — никогда, а сравнение A с A даёт ложную тревогу примерно в 5 % серий.}}

«Не доказано» не значит «эффекта нет»: шум +6 % в лабораторной на пяти парах не виден, по формуле для него нужно около 30 полётов на плечо (16 · (0.08/0.06)² = 28.4). Такие побочные эффекты страхует порог: моторы не горячее, чем у A.

### Справочная таблица (Betaflight 4.5)

| Команда / параметр | Умолчание | Диапазон | Роль в A/B |
|---|---|---|---|
| `profile N` | 0 | 0–3 | выбрать PID-профиль, только на земле |
| `rateprofile N` | 0 | 0–3 | выбрать профиль рейтов |
| `diff all` | — | — | бэкап всех профилей; `diff` — только текущие PID-профиль и профиль рейтов |
| `adjrange i 0 ch start end fn adjch center scale` | пусто | i 0–29 | 12 RATE_PROFILE, 17 PITCH_D, 20 ROLL_D, 8 PITCH_ROLL_D |
| `profile_name`, `osd_pid_profile_name_pos` | пусто, скрыт | до 8 символов | видеть в OSD, что летит |
| `d_roll` / `d_pitch` | 40 / 46 | 0–250 (слот подстройки — 0–200) | в 4.5 верх D (2025.12: база 30/34, верх `d_max_*`) |
| `d_min_roll` / `d_min_pitch` | 30 / 34 | 0–250 | база D в 4.5 |
| `blackbox_sample_rate` | 1/4 | 1/1 … 1/16 | ≥ 1 кГц |
| `blackbox_high_resolution` | OFF | OFF, ON | ON → gyro, setpoint, rcCommand ×10 |
| `debug_mode` | NONE | таблица | D_MIN (2025.12: D_MAX) — действующий D |
| `vbat_sag_compensation` | 0 | 0–150 % | одинаковый в A и B; только с ADC-датчиком напряжения |
| `auto_profile_cell_count` | 0 | −1…8 | ≠ 0 сам меняет PID-профиль: на время A/B — 0 |

Профиль в профиль копируют Betaflight App (`MSP_COPY_PROFILE`, 183) и OSD-меню (COPY PROF); CLI-команды нет ни в 4.5, ни в 2025.12. Бэкап — `diff all`, не `diff`: тот сохраняет только текущие PID-профиль и профиль рейтов.

### Кейс: два одинаковых 7" с разными профилями
Два 7-дюймовых квадрокоптера одной сборки, на первом профиль A, на втором B, по логам у B пропвош на 12 % меньше. Вывод «B лучше» не следует: аппарат и профиль меняются вместе. Масштаб показал кейс `bf-pid`: один профиль SHARP дал на двух таких дронах bounce-back 2.9 % и 8.5 % — по разбору `bf-pid`, из-за разной резкости пилотирования; разница «дрон/сессия» оказалась больше разницы профилей (6.0 и 8.5 % на одном дроне).

Правильный дизайн — перекрёстный (crossover): каждый аппарат летает оба профиля в своей сессии ABBA, эффект считается внутри аппарата (Δ₁, Δ₂). Совпали по знаку и прошли |Δ|/SE > 2 — эффект переносится. Δ₁ ≈ −15 %, а Δ₂ ≈ 0 — ищи причину во втором аппарате (баланс моторов, ЦТ, пропы), прежде чем копировать профиль. «A на одном, B на другом» годится только для поиска гипотез.

### Место в системе
- **Получает:** лог с `setpoint`, `gyroADC`, `motor`, `rcCommand` и события подстроек (`bf-blackbox`); выверенную механику (`bf-motor-balance`); чистый спектр (`bf-filters`); кандидатов на изменение и метрики ощущений (`bf-pid`); слоты подстроек для переключения в полёте (`bf-adjustments`).
- **Отдаёт:** решение «принять B / оставить A / летать ещё» с эффектом, разбросом и p — в журнал настройки и `diff all` в репозитории (`eng-ci-configs`); оценку шума метрики (A/A-тест) — для планирования следующих изменений (`bf-pid`).
- **Если ошибиться здесь:** профиль «победил» по одной паре полётов, хотя разница была шумом. Через неделю он «перестал работать», и пилот крутит PID дальше (`bf-pid`), каждый раз принимая ветер за эффект. Или профиль скопировали на второй аппарат, а там другой ЦТ, и B хуже A (`bf-motor-balance`).

## practice
Основной путь не требует железа. Скрипт режет CSV от `blackbox_decode` на манёвры по правилам из таблицы программы, считает метрики и печатает вердикт. Без своих логов он генерирует синтетические полёты с известной правдой: B снижает амплитуду пропвоша на 15 % и поднимает шум гироскопа на 6 %. Разброс: пропвош полёта ×e^N(0, 0.05), каждого спуска ×e^N(0, 0.08), шум ×e^N(0, 0.08); в сессиях ветер добавляет +3 % пропвоша на каждый следующий полёт. Нужен Python 3.8+ (`math.comb`), только стандартная библиотека.

### Шаг 1. Предел теста и план
Посчитай руками до полётов. Минимальное p = 2 / C(2n, n): n = 4 → 2/70 = 0.0286, n = 3 → 2/20 = 0.100. План n ≈ 16 · (CV/Δ)²: CV 8 %, Δ 15 % → 4.55 → 5 полётов; CV 10 %, Δ 20 % → 4.0 → 4. Меньше 4 полётов на плечо при этом тесте не имеют смысла ни при каком эффекте.

### Шаг 2. Скрипт
Сохрани как `ab_compare.py`. `make_flight` пишет CSV со столбцами `blackbox_decode` (`time (us)`, `rcCommand[3]`, `setpoint[0..3]`, `gyroADC[0..2]`, `motor[0..3]`), 1 кГц. Отклик гироскопа — звено второго порядка (16 Гц, демпфирование 0.55), пропвош — синус 30–45 Гц, нарастающий после сброса газа и затухающий с постоянной 0.2 с, начиная через 0.3 с после подхвата. Полосовой фильтр — биквад, прогнанный вперёд и назад, без сдвига фазы.

```python
#!/usr/bin/env python3
"""A/B comparison of Betaflight tunes from blackbox_decode CSVs (one value per flight, then statistics).

  python3 ab_compare.py --a A1.csv A2.csv ... --b B1.csv B2.csv ... [--target propwash] [--motor-range 158,2047]
  python3 ab_compare.py --a LOG.01.csv@40-95 --b LOG.01.csv@95-150     # windows (s from log start), in-flight A/B
  python3 ab_compare.py --demo                                         # synthetic flights with a known effect
Standard library only. Metrics per flight (medians over manoeuvres of the scripted program):
  noise     gyro roll+pitch RMS in 100-250 Hz on hover (|setpoint| < 20 deg/s, throttle 1300-1600, >= 2 s)
  track     RMS(setpoint - gyro) roll on each roll manoeuvre (|setpoint| > 200 deg/s for > 50 ms) + 150 ms after
  overshoot (max gyro / max setpoint - 1) * 100 % on the same windows, same sign as the setpoint
  propwash  gyro roll+pitch RMS in 20-70 Hz from 0.3 s into a dive (throttle < 1150 for >= 0.5 s) to 0.6 s after it
  headroom  100 % - 99th percentile of the highest motor output on a punch-out (throttle > 1900 for >= 0.3 s)
The first and last 3 s of every log are ignored (take-off, landing). Thresholds are course guidelines, not firmware values.
"""
import argparse, csv, itertools, math, os, random, re, statistics, sys, tempfile

LOWER_IS_BETTER = {"noise": True, "track": True, "overshoot": True, "propwash": True, "headroom": False}
UNIT = {"noise": "deg/s", "track": "deg/s", "overshoot": "%", "propwash": "deg/s", "headroom": "%"}
TRIM_S = 3.0


# ---------------------------------------------------------------- reading and segmenting
def read_csv(spec, scale=1.0):
    path, _, win = spec.partition("@")
    with open(path, newline="") as f:
        rd = csv.reader(f)
        head = [re.sub(r"\s*\(.*\)$", "", h.strip()) for h in next(rd)]
        need = ["time", "rcCommand[3]", "setpoint[0]", "setpoint[1]", "setpoint[2]", "gyroADC[0]", "gyroADC[1]"]
        need += [f"motor[{i}]" for i in range(4)]
        miss = [n for n in need if n not in head]
        if miss:
            sys.exit(f"{path}: no columns {miss}")
        pos = [head.index(n) for n in need]
        rows = [[float(r[p]) for p in pos] for r in rd if len(r) >= len(head)]
    c = {n: [r[k] for r in rows] for k, n in enumerate(need)}
    for n in need[1:7]:                                   # rcCommand, setpoint, gyro x10 with high resolution
        c[n] = [v / scale for v in c[n]]
    t0 = c["time"][0]
    c["t"] = [(v - t0) / 1e6 for v in c["time"]]
    lo, hi = (0.0, 1e9)
    if win:
        lo, hi = (float(x) for x in win.split("-"))
    keep = [i for i, t in enumerate(c["t"]) if max(lo, TRIM_S) <= t <= min(hi, c["t"][-1] - TRIM_S)]
    c["keep"] = set(keep)
    c["fs"] = (len(c["t"]) - 1) / (c["t"][-1] - c["t"][0])
    return c


def runs(c, cond, min_s):
    """Index ranges [i0, i1) where cond(i) holds for at least min_s seconds, inside the kept part."""
    out, start = [], None
    for i in range(len(c["t"]) + 1):
        ok = i < len(c["t"]) and i in c["keep"] and cond(i)
        if ok and start is None:
            start = i
        elif not ok and start is not None:
            if c["t"][i - 1] - c["t"][start] >= min_s:
                out.append((start, i))
            start = None
    return out


def bandpass(x, fs, f1, f2):
    """RBJ band-pass biquad (0 dB at the centre sqrt(f1*f2)), run forward and backward: no phase shift."""
    f0 = math.sqrt(f1 * f2)
    q = f0 / (f2 - f1)
    w = 2 * math.pi * f0 / fs
    al = math.sin(w) / (2 * q)
    b0, b2, a0, a1, a2 = al, -al, 1 + al, -2 * math.cos(w), 1 - al

    def run(s):
        y, x1, x2, y1, y2 = [], 0.0, 0.0, 0.0, 0.0
        for v in s:
            o = (b0 * v + b2 * x2 - a1 * y1 - a2 * y2) / a0
            x2, x1, y2, y1 = x1, v, y1, o
            y.append(o)
        return y
    return run(run(x)[::-1])[::-1]


def rms(xs):
    return math.sqrt(sum(v * v for v in xs) / len(xs)) if xs else float("nan")


def flight_metrics(c, lo, hi):
    fs, n = c["fs"], len(c["t"])
    thr, sp, g = c["rcCommand[3]"], c["setpoint[0]"], c["gyroADC[0]"]
    m = {}
    hover = runs(c, lambda i: max(abs(c[f"setpoint[{a}]"][i]) for a in range(3)) < 20 and 1300 <= thr[i] <= 1600, 2.0)
    hp = [bandpass(c[f"gyroADC[{a}]"], fs, 100, 250) for a in (0, 1)]
    m["noise"] = statistics.median([rms(hp[0][a:b] + hp[1][a:b]) for a, b in hover]) if hover else float("nan")
    man = runs(c, lambda i: abs(sp[i]) > 200, 0.05)
    tr, ov = [], []
    for a, b in man:
        b2 = min(n, b + int(0.15 * fs))
        tr.append(rms([sp[i] - g[i] for i in range(a, b2)]))
        s = 1 if sp[a] > 0 else -1
        ov.append((max(s * g[i] for i in range(a, b2)) / max(s * sp[i] for i in range(a, b)) - 1) * 100)
    m["track"] = statistics.median(tr) if tr else float("nan")
    m["overshoot"] = statistics.median(ov) if ov else float("nan")
    dives = runs(c, lambda i: thr[i] < 1150, 0.5)
    bp = [bandpass(c[f"gyroADC[{a}]"], fs, 20, 70) for a in (0, 1)]
    pw = []
    for a, b in dives:
        a2, b2 = a + int(0.3 * fs), min(n, b + int(0.6 * fs))
        pw.append(rms(bp[0][a2:b2] + bp[1][a2:b2]))
    m["propwash"] = statistics.median(pw) if pw else float("nan")
    punch = runs(c, lambda i: thr[i] > 1900, 0.3)
    hr = []
    for a, b in punch:
        top = sorted(max((c[f"motor[{k}]"][i] - lo) / (hi - lo) * 100 for k in range(4)) for i in range(a, b))
        hr.append(100 - top[int(0.99 * (len(top) - 1))])
    m["headroom"] = statistics.median(hr) if hr else float("nan")
    m["_count"] = (len(hover), len(man), len(dives), len(punch))
    return m


# ---------------------------------------------------------------- statistics
def perm_p(a, b, limit=20000, seed=7):
    """Two-sided permutation test on the difference of means: share of relabellings at least as extreme."""
    pool, na = a + b, len(a)
    obs = abs(statistics.fmean(b) - statistics.fmean(a))
    if math.comb(len(pool), na) <= limit:
        splits = itertools.combinations(range(len(pool)), na)
    else:
        rnd = random.Random(seed)
        splits = (rnd.sample(range(len(pool)), na) for _ in range(limit))
    hit = tot = 0
    for idx in splits:
        s = set(idx)
        xa = [pool[i] for i in s]
        xb = [pool[i] for i in range(len(pool)) if i not in s]
        hit += abs(statistics.fmean(xb) - statistics.fmean(xa)) >= obs - 1e-12
        tot += 1
    return hit / tot


def compare(a, b):
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    d = mb - ma
    if len(a) < 2 or len(b) < 2:
        return dict(ma=ma, mb=mb, d=d, rel=d / ma * 100, sp=float("nan"), se=float("nan"), z=float("nan"), p=perm_p(a, b))
    sp = math.sqrt(((len(a) - 1) * statistics.variance(a) + (len(b) - 1) * statistics.variance(b)) / (len(a) + len(b) - 2))
    se = sp * math.sqrt(1 / len(a) + 1 / len(b))
    return dict(ma=ma, mb=mb, d=d, rel=d / ma * 100, sp=sp, se=se, z=abs(d) / se if se else float("inf"), p=perm_p(a, b))


def verdict(r, lower_better):
    if math.isnan(r["se"]):
        return "no spread estimate (1 flight per arm)"
    if r["z"] <= 2 or r["p"] >= 0.05:
        return "within noise"
    better = (r["d"] < 0) == lower_better
    return "B better" if better else "B WORSE"


def report(title, A, B, target):
    print(f"== {title}: {len(A)} flight(s) A, {len(B)} flight(s) B, target metric '{target}'")
    print(f"  {'metric':9s} {'A mean':>8s} {'B mean':>8s} {'B-A':>7s} {'s_p':>6s} {'|d|/SE':>6s} {'p':>6s}  verdict")
    res = {}
    for k in LOWER_IS_BETTER:
        a, b = [f[k] for f in A], [f[k] for f in B]
        r = compare(a, b)
        res[k] = (r, verdict(r, LOWER_IS_BETTER[k]))
        print(f"  {k:9s} {r['ma']:8.2f} {r['mb']:8.2f} {r['rel']:+6.1f}% {r['sp']:6.2f} {r['z']:6.2f} {r['p']:6.3f}  {res[k][1]}")
    worse = [k for k, (r, v) in res.items() if v == "B WORSE"]
    if res[target][1] == "B better" and not worse:
        print(f"  DECISION: accept B ({target} {res[target][0]['rel']:+.1f} %, no side metric worse beyond noise)")
    elif res[target][1] == "B better":
        print(f"  DECISION: trade-off, B improves {target} but worsens {', '.join(worse)}: decide by the task")
    else:
        print(f"  DECISION: keep A, effect on {target} not shown; fly more pairs or drop the change")
    return res


# ---------------------------------------------------------------- synthetic flights
def lognorm(rnd, cv):
    return math.exp(rnd.gauss(0, cv))


def make_flight(path, arm, seed, slot=0, drift=0.0, fs=1000, dur=26.0, lo=158, hi=2047):
    """Scripted program: take-off, hover 2-6 s, five roll steps +-500 deg/s at 6.5-10.5 s, punch-out 12.3-13.5 s,
    three zero-throttle dives at 14, 17, 20 s (1.2 s cut, 0.8 s recovery at 1700), hover, landing.
    Arm B: propwash amplitude x0.85, gyro noise x1.06. drift: +share of propwash per flight slot (wind rising)."""
    rnd = random.Random(seed)
    pw_amp = 40.0 * (0.85 if arm == "B" else 1.0) * lognorm(rnd, 0.05) * (1 + drift * slot)
    noise = 3.0 * (1.06 if arm == "B" else 1.0) * lognorm(rnd, 0.08)
    zeta, wn = 0.55 * lognorm(rnd, 0.05), 2 * math.pi * 16 * lognorm(rnd, 0.04)
    dive_amp = [lognorm(rnd, 0.08) for _ in range(3)]
    dive_f = [rnd.uniform(30, 45) for _ in range(3)]
    punch_top = 93.0 * lognorm(rnd, 0.01)
    x = v = 0.0
    with open(path, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["loopIteration", "time (us)", "rcCommand[3]"] + [f"setpoint[{a}]" for a in range(4)]
                    + [f"gyroADC[{a}]" for a in range(3)] + [f"motor[{i}]" for i in range(4)])
        for n in range(int(dur * fs)):
            t = n / fs
            thr, sp, env, fpw, kd = 1450.0, 0.0, 0.0, 35.0, 0
            if t < 2:
                thr = 1000 + 225 * t
            elif 6.5 <= t < 11.5 and (t - 6.5) % 1.0 < 0.25:
                sp = 500.0 if int(t - 6.5) % 2 == 0 else -500.0
            elif 12.3 <= t < 13.5:
                thr = 2000.0
            elif 14 <= t < 22:
                kd = int((t - 14) // 3)
                u = (t - 14) - 3 * kd
                thr = 1000.0 if u < 1.2 else (1700.0 if u < 2.0 else 1450.0)
                env = 0 if u < 0.4 else (min(1, (u - 0.4) / 0.8) if u < 1.5 else math.exp(-(u - 1.5) / 0.2))
                fpw = dive_f[kd]
            elif t >= 24.5:
                thr = 1450 - 300 * (t - 24.5)
            acc = wn * wn * (sp - x) - 2 * zeta * wn * v              # second-order rate response
            v += acc / fs
            x += v / fs
            burst = pw_amp * dive_amp[kd] * env
            g0 = x + burst * math.sin(2 * math.pi * fpw * t) + rnd.gauss(0, noise)
            g1 = burst * math.sin(2 * math.pi * fpw * 1.07 * t + 1.3) + rnd.gauss(0, noise)
            base = punch_top if thr > 1900 else 8 + 0.085 * (thr - 1000)
            mot = []
            for s in (-1, -1, 1, 1):                                # roll signs of mixerQuadX
                p = base + s * 0.015 * (sp - g0) + rnd.gauss(0, 1.0)
                mot.append(int(round(lo + max(0.0, min(100.0, p)) / 100 * (hi - lo))))
            wr.writerow([n, int(t * 1e6), int(thr), round(sp), 0, 0, int(thr)] + [round(g0), round(g1), 0] + mot)


def demo():
    d = tempfile.mkdtemp(prefix="bfab_")
    gen = lambda name, arm, seed, slot=0, drift=0.0: (make_flight(os.path.join(d, name), arm, seed, slot, drift),
                                                     os.path.join(d, name))[1]
    met = lambda p: flight_metrics(read_csv(p), 158, 2047)
    print("Synthetic truth: B = propwash x0.85 (-15 %), gyro noise x1.06; flight-to-flight scatter as in real sessions")
    order = "ABBAABBAAB"
    sess = [(arm, met(gen(f"S1_{k:02d}{arm}.csv", arm, 100 + k, k, 0.03))) for k, arm in enumerate(order)]
    c = sess[0][1]["_count"]
    print(f"segments found in flight 1: hover {c[0]}, roll manoeuvres {c[1]}, dives {c[2]}, punch-outs {c[3]}")
    print("session 1, order " + order + ", wind rising +3 % propwash per flight:")
    print("  propwash per flight: " + "  ".join(f"{a}{k + 1} {m['propwash']:.2f}" for k, (a, m) in enumerate(sess)))
    report("1 flight per arm (A1, B2)", [sess[0][1]], [sess[1][1]], "propwash")
    report("5 flights per arm, ABBA order", [m for a, m in sess if a == "A"], [m for a, m in sess if a == "B"], "propwash")
    blk = [(arm, met(gen(f"S2_{k:02d}{arm}.csv", arm, 200 + k, k, 0.03))) for k, arm in enumerate("AAAAABBBBB")]
    report("5 flights per arm, blocked AAAAA BBBBB, same wind drift", [m for a, m in blk if a == "A"],
           [m for a, m in blk if a == "B"], "propwash")
    print("== power: draws from pools of 30 flights per arm (no drift), 400 draws with replacement per n, target propwash")
    pools = {arm: [met(gen(f"P_{arm}{k:02d}.csv", arm[0], 1000 * (i + 1) + k))["propwash"] for k in range(30)]
             for i, arm in enumerate(("A", "B", "A2"))}
    cv = statistics.stdev(pools["A"]) / statistics.fmean(pools["A"]) * 100
    print(f"  flight-to-flight CV of propwash in pool A: {cv:.1f} %")
    rnd = random.Random(42)
    print("  n/arm  B vs A: detected  median effect  5..95 % of estimates   A vs A2 (no effect): false alarm")
    for n in range(1, 9):
        det = fa = 0
        est = []
        for _ in range(400):
            a, b, a2 = (rnd.choices(pools[k], k=n) for k in ("A", "B", "A2"))
            r = compare(a, b)
            est.append(r["rel"])
            det += verdict(r, True) == "B better"
            fa += verdict(compare(a, a2), True) != "within noise" and n > 1
        est.sort()
        print(f"  {n:5d}  {det / 4:16.1f} % {statistics.median(est):+12.1f} % {est[20]:+9.1f} .. {est[379]:+6.1f} %"
              f" {fa / 4:27.1f} %")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a", nargs="*", default=[])
    ap.add_argument("--b", nargs="*", default=[])
    ap.add_argument("--target", default="propwash", choices=list(LOWER_IS_BETTER))
    ap.add_argument("--motor-range", default="158,2047", help="log header line motorOutput: low,high")
    ap.add_argument("--hires", action="store_true", help="blackbox_high_resolution = ON: rcCommand, setpoint, gyro x10")
    ap.add_argument("--demo", action="store_true")
    o = ap.parse_args()
    if o.demo or not (o.a and o.b):
        demo()
        sys.exit()
    lo, hi = (float(v) for v in o.motor_range.split(","))
    sc = 10.0 if o.hires else 1.0
    A = [flight_metrics(read_csv(p, sc), lo, hi) for p in o.a]
    B = [flight_metrics(read_csv(p, sc), lo, hi) for p in o.b]
    for name, S, files in (("A", A, o.a), ("B", B, o.b)):
        for m, p in zip(S, files):
            print(f"{name} {os.path.basename(p)}: " + "  ".join(f"{k} {m[k]:.2f}" for k in LOWER_IS_BETTER)
                  + f"  segments h/m/d/p {m['_count']}")
    report("own logs", A, B, o.target)
```

### Шаг 3. Прогон на синтетике
`python3 ab_compare.py --demo`. Генератор детерминирован (`random.Random(seed)`), прогон занимает около минуты, вывод должен совпасть до сотых:

```text
Synthetic truth: B = propwash x0.85 (-15 %), gyro noise x1.06; flight-to-flight scatter as in real sessions
segments found in flight 1: hover 1, roll manoeuvres 5, dives 3, punch-outs 1
session 1, order ABBAABBAAB, wind rising +3 % propwash per flight:
  propwash per flight: A1 18.20  B2 15.80  B3 16.04  A4 20.66  A5 22.48  B6 17.99  B7 18.25  A8 22.58  A9 24.50  B10 18.10
== 1 flight per arm (A1, B2): 1 flight(s) A, 1 flight(s) B, target metric 'propwash'
  metric      A mean   B mean     B-A    s_p |d|/SE      p  verdict
  noise         1.42     1.35   -5.4%    nan    nan  1.000  no spread estimate (1 flight per arm)
  track       108.43   106.74   -1.6%    nan    nan  1.000  no spread estimate (1 flight per arm)
  overshoot    12.00     8.20  -31.7%    nan    nan  1.000  no spread estimate (1 flight per arm)
  propwash     18.20    15.80  -13.2%    nan    nan  1.000  no spread estimate (1 flight per arm)
  headroom      5.29     3.55  -33.0%    nan    nan  1.000  no spread estimate (1 flight per arm)
  DECISION: keep A, effect on propwash not shown; fly more pairs or drop the change
== 5 flights per arm, ABBA order: 5 flight(s) A, 5 flight(s) B, target metric 'propwash'
  metric      A mean   B mean     B-A    s_p |d|/SE      p  verdict
  noise         1.37     1.35   -1.6%   0.12   0.29  0.778  within noise
  track       107.13   105.81   -1.2%   2.48   0.84  0.460  within noise
  overshoot    11.56    10.24  -11.4%   1.87   1.11  0.294  within noise
  propwash     21.68    17.23  -20.5%   1.88   3.73  0.016  B better
  headroom      3.90     4.54  +16.6%   1.17   0.88  0.460  within noise
  DECISION: accept B (propwash -20.5 %, no side metric worse beyond noise)
== 5 flights per arm, blocked AAAAA BBBBB, same wind drift: 5 flight(s) A, 5 flight(s) B, target metric 'propwash'
  metric      A mean   B mean     B-A    s_p |d|/SE      p  verdict
  noise         1.30     1.42   +8.8%   0.09   1.98  0.079  within noise
  track       105.03   105.91   +0.8%   1.54   0.90  0.444  within noise
  overshoot    12.68    11.84   -6.6%   1.49   0.89  0.413  within noise
  propwash     19.04    18.45   -3.1%   1.66   0.56  0.595  within noise
  headroom      4.30     3.78  -12.1%   0.80   1.03  0.333  within noise
  DECISION: keep A, effect on propwash not shown; fly more pairs or drop the change
== power: draws from pools of 30 flights per arm (no drift), 400 draws with replacement per n, target propwash
  flight-to-flight CV of propwash in pool A: 7.9 %
  n/arm  B vs A: detected  median effect  5..95 % of estimates   A vs A2 (no effect): false alarm
      1               0.0 %        -16.7 %     -29.4 ..   -3.4 %                         0.0 %
      2               0.0 %        -16.3 %     -26.5 ..   -7.1 %                         0.0 %
      3               0.0 %        -16.2 %     -24.3 ..   -7.9 %                         0.0 %
      4              67.2 %        -16.2 %     -23.0 ..   -8.9 %                         3.2 %
      5              92.5 %        -16.2 %     -22.3 ..  -10.1 %                         5.0 %
      6              98.8 %        -17.1 %     -22.8 ..  -11.2 %                         5.2 %
      7              99.8 %        -16.6 %     -22.6 ..  -11.4 %                         8.5 %
      8             100.0 %        -16.7 %     -21.0 ..  -11.6 %                         7.8 %
```

Разбор. **Одна пара**: пропвош −13.2 %, похоже на правду, но рядом overshoot −31.7 % и headroom −33.0 %, которые B не меняет. Без разброса внутри плеча эти числа не различить, p = 1.000. **ABBA, 5 + 5**: пропвош −20.5 %, |Δ|/SE = 3.73, p = 0.016, B принят. Шум +6 %, заложенный в B, остался «в пределах шума», его страхует правило про температуру моторов. −20.5 % при правде −15 % — обычный разброс серии: при n = 5 90 % оценок лежат от −22.3 до −10.1 %. **Блоки** с тем же ветром: −3.1 %, p = 0.595, эффект потерян — дрейф у A +6 %, у B +21 %. **Мощность**: при n ≤ 3 обнаружений 0 % (предел теста), при n = 4 — 67 %, при n = 5 — 92.5 %. Ложная тревога A против A2 около 5 % (3–8.5 %) — цена порога p < 0.05. Даже пулы по 30 полётов дают медиану −16…−17 %, а не ровно −15 %.

### Шаг 4. Свои логи
{{lesson:bf-blackbox|Запись лога, частота, поля `blackbox_disable_*` и расшифровка в CSV разобраны там: без полей `setpoint` и `motor` скрипту нечего считать.}}

`blackbox_decode LOG00001.BFL` даёт `LOG00001.01.csv` и `LOG00001.01.event`. При `grep -a blackbox_high_resolution LOG00001.BFL` = 1 запускай с `--hires`; диапазон моторов — `grep -a motorOutput LOG00001.BFL` → `--motor-range`. Отдельные полёты: `python3 ab_compare.py --a A1.csv A4.csv A5.csv A8.csv A9.csv --b B2.csv B3.csv B6.csv B7.csv B10.csv`. Тумблер в одном полёте: время события из `.event` минус первое `time (us)` CSV, делённое на 10⁶, — секунды от начала лога, их передаёшь окнами: `--a LOG.01.csv@40-75 LOG.01.csv@110-145 --b LOG.01.csv@75-110 …`; в каждом окне — вся программа. Строка `segments h/m/d/p` с нулём значит, что манёвр не распознан и его метрика будет `nan`.

### Переход на реальное железо
**Дома, пропы сняты.** `diff all` в файл с датой; механика (`bf-motor-balance`) и спектр (`bf-filters`) в порядке; гипотеза, метрика, порог и план n записаны в журнал. Отдельные полёты: B в соседнем PID-профиле, `profile_name` «A» и «B», имя профиля в OSD. Тумблер: два слота `adjrange` из теории, эндпоинты 1000/2000 во вкладке Receiver, `get d_roll` в обоих положениях (40 и 46), `debug_mode = D_MIN`. Лог не реже 1 кГц, flash очищена.

**Поле.** Ветер до 5 м/с, одна партия АКБ, одни пропы. Порядок ABBA ABBA AB, 5 полётов на плечо, одинаковая пауза (5 мин), посадка на одном напряжении (например, 3.6 В на банку под нагрузкой, ориентир курса). Перед взлётом — профиль по OSD (если ставит помощник, пилот не смотрит). После каждого полёта — строка в журнале:

| № | Время | Плечо | Профиль / значение | АКБ № и V покоя после | Ветер, м/с | Т моторов, °C | Оценка пилота 1–5 | Лог | Заметки |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 10:05 | A | profile 0 «A» | 3, 3.78 | 2–3 | 41 | 3 | LOG00001 | — |
| 2 | 10:12 | B | profile 1 «B» | 4, 3.77 | 3 | 44 | 4 | LOG00002 | порыв на 2-м спуске |

**Прерви полёт и садись, если:** появились осцилляции или «звон», которых у A не было; OSD показывает не тот профиль или не то значение; моторы после посадки не удержать пальцем 5 с (`bf-pid`) — тогда B отклоняется без статистики; задел что-то или сменил проп — сессия заново с A. После сессии: слоты `adjrange` удалены, принятое значение вписано через `set`, `diff all` «после» и вердикт скрипта — в журнале.

Самопроверка: лабораторная выполнена, когда:
- **Расчёт (основной путь):** минимальное p для n = 3, 4, 5 равно 0.100, 0.0286, 0.0079 (±0.0001); план для CV 8 %, Δ 15 % — 5 полётов.
- **Расчёт:** вывод `--demo` совпал с выводом выше: одна пара — p = 1.000 по всем метрикам; ABBA — пропвош −20.5 %, |Δ|/SE = 3.73, p = 0.016, `accept B`; блоки — −3.1 %, p = 0.595, `keep A`; мощность при n = 4 и 5 — 67.2 % и 92.5 %.
- **Расчёт:** ты своими словами записал, почему блоки потеряли эффект, а ABBA — нет, и сверил с эталоном ниже.
- **Железо:** сессия 5 + 5 полётов в порядке ABBA с заполненным журналом. Скрипт на твоих логах нашёл все сегменты в каждом полёте (h/m/d/p ≥ 1/1/1/1), вердикт записан вместе с |Δ|/SE и p, температура моторов в B не выше, чем в A.

**Эталон для самопроверки.** В блоках плечо B летало позже и получило от ветра на 15 % пропвоша больше, чем A (+21 % против +6 %), — почти ровно столько, сколько эффект (1.21/1.06 = +14.2 %, 0.85 · 1.142 = 0.97). В ABBA дрейф плеч +13.2 % и +13.8 %, эффект остаётся. Типичные ошибки. «На одной паре −13 %, значит работает» — без разброса это не отличить от −33 % по запасу моторов, который B не меняет. «Три полёта, p = 0.10, почти значимо» — при n = 3 меньше 0.10 не бывает, это предел теста. «Шум не вырос, раз within noise» — +6 % заложены в B, пять пар их просто не видят.

## diagnostics
- **Симптом:** вчерашний «лучший» профиль сегодня не лучше
  - Возможная причина: решение принято по одной паре полётов, разница была шумом или ветром.
  - Что сделать: A/A-тест для оценки шума метрики, затем 4–5 полётов на плечо в порядке ABBA.
- **Симптом:** скрипт пишет `nan` по одной метрике
  - Возможная причина: манёвр не попал в правило: спуск короче 0.5 с, броски слабее 200 °/с, панч ниже 1900, висение короче 2 с; или окно `@t0-t1` его обрезало.
  - Что видно в логе: в строке `segments h/m/d/p` ноль на месте манёвра.
  - Что сделать: лети по программе с запасом по длительности, проверь окна; при `blackbox_high_resolution = 1` запускай с `--hires`.
- **Симптом:** тумблер даёт `d_roll` 41 вместо 40 (положение A) или 45 вместо 46 (положение B)
  - Возможная причина: эндпоинты канала не доходят до 1000/2000 мкс, деление C отбрасывает дробную часть.
  - Что сделать: эндпоинты в пульте до 988–1000 и 2000–2012 мкс, проверка `get d_roll` в обоих положениях.
- **Симптом:** в полёте не получается переключить PID-профиль тумблером
  - Возможная причина: в 4.5 и 2025.12 такой функции нет, в режиме выбора `adjrange` умеет только профиль рейтов, OSD и LED, HORIZON_STRENGTH и PID_AUDIO (в 2025.12 ещё LED_DIMMER).
  - Что сделать: отдельные полёты с выбором профиля на земле или абсолютный слот на один коэффициент.
- **Симптом:** профиль сам меняется после смены АКБ
  - Возможная причина: `auto_profile_cell_count` ≠ 0 в одном из профилей.
  - Что сделать: на время эксперимента 0 во всех профилях, проверка имени профиля в OSD перед взлётом.
- **Симптом:** эффект на одном аппарате есть, на втором такого же нет
  - Возможная причина: аппараты отличаются механикой или пропами сильнее, чем профили.
  - Что сделать: перекрёстный дизайн, эффект внутри каждого аппарата; баланс моторов по логу (`bf-motor-balance`).

## checklist
- Механика и фильтры в порядке до эксперимента
- Гипотеза, целевая метрика, порог и план n записаны до полётов
- B отличается от A одним параметром; `diff all` до и после
- Одна программа полёта, одни пропы, одна партия АКБ, ветер до 5 м/с
- Порядок ABA или ABBA, не блоки; не меньше 4 полётов на плечо
- Профиль или значение проверены по OSD перед каждым взлётом
- Вердикт: |Δ|/SE > 2 и p < 0.05 по целевой метрике, побочные не хуже, моторы не горячее
- Слоты `adjrange` после эксперимента удалены, принятое значение вписано через `set`

## references
- Betaflight `fc/rc_adjustments.c`, 4.5.3 (defaultAdjustmentConfigs, режим выбора RATE_PROFILE, абсолютный режим, событие подстройки) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/fc/rc_adjustments.c | primary | A
- Betaflight `fc/rc_adjustments.h`, 4.5.3 (список функций, нет функции PID-профиля, 30 слотов) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/fc/rc_adjustments.h | primary | A
- Betaflight `cli/cli.c`, 4.5.3 (adjrange, diff, dump, profile, rateprofile) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/cli/cli.c | primary | A
- Betaflight `cli/settings.c`, 4.5.3 (blackbox_*, debug_mode, vbat_sag_compensation, d_roll, d_min_roll, имена профилей) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/cli/settings.c | primary | A
- Betaflight `blackbox/blackbox.c`, 4.5.3 (поля setpoint, gyroADC, motor; заголовки rollPID, d_min) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/blackbox/blackbox.c | primary | A
- Betaflight `fc/rc_controls.c`, 4.5.3 (выбор PID-профиля стиками на земле) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/fc/rc_controls.c | primary | A
- Betaflight `fc/rc_modes.h`, 4.5.3 (список режимов: режима PID-профиля нет) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/fc/rc_modes.h | primary | A
- Betaflight `msp/msp.c`, 4.5.3 (MSP_SELECT_SETTING игнорирует PID-профиль при арме; MSP_SET_PID без проверки арма; MSP_COPY_PROFILE) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/msp/msp.c | primary | A
- Betaflight `fc/rc_adjustments.c`, 2025.12-maintenance (те же номера 12, 17, 20; PID-профиля по-прежнему нет) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12-maintenance/src/main/fc/rc_adjustments.c | primary | A
- blackbox-tools `blackbox_decode.c` (файл .event, JSON события Inflight adjustment) | https://raw.githubusercontent.com/betaflight/blackbox-tools/master/src/blackbox_decode.c | primary | A
- PID Tuning Guide — Betaflight Documentation | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/guides/current/PID-Tuning-Guide.md | primary | B
- SciPy `stats/_resampling.py`, permutation_test (точный перебор разбиений, двустороннее p) | https://raw.githubusercontent.com/scipy/scipy/main/scipy/stats/_resampling.py | secondary | B

## notes
Пороги |Δ|/SE > 2, p < 0.05, 80 %, правила разметки манёвров, полосы 100–250 и 20–70 Гц, обрезка 3 с, посадочное напряжение и пауза — ориентиры курса, в прошивке их нет. n ≈ 16 · (CV/Δ)² — нормальное приближение. Числа практики получены на синтетике, CV пропвоша около 8 % — допущение модели; свой разброс меряется A/A-тестом. Строки журнала — пример заполнения, не данные сессии.
