---
id: bf-failsafe
title: "Failsafe: стадии, процедуры и тест по свитчу"
level: L1
readingTime: 20 мин
firmware: Betaflight 4.5+
status: published
added: 2026-11-07
tags:
  - failsafe
  - safety
related:
  - bf-modes-osd
  - link-elrs
next:
  - bf-rpm-filter
---

## summary
Failsafe — то, что дрон делает, когда пропала связь с пультом. В Betaflight 4.3+ это двухстадийный процесс: короткая «защитная» Stage 1, затем Stage 2 с выбранной процедурой (DROP, AUTO-LAND или GPS_RESCUE). Модуль объясняет, как это устроено, как выбрать процедуру под свой дрон и как безопасно проверить failsafe тумблером, не выключая пульт в воздухе.

## theory
### Как Betaflight понимает, что связь потеряна
Если 100 мс нет валидных пакетов, сигнал считается потерянным. Ещё 300 мс удерживаются последние значения, после чего включается Stage 1. Отсчёт до Stage 2 идёт от последнего хорошего пакета.

{{diagram:failsafe-stages|Временная диаграмма failsafe: детекция потери, короткое удержание, Stage 1 и Stage 2.}}

### Stage 1 — защитный интервал
Длится `failsafe_delay` (в десятых долях секунды: 15 = 1.5 с; дефолт 1.5 с в 4.5, 1.0 с в 4.4). По умолчанию стики в центре, газ на нуле, положения тумблеров удерживаются. Значения для каждого канала задаются в Configurator (Channel fallback) или командой `rxfail`. Если связь вернулась во время Stage 1, управление возвращается мгновенно.

### Stage 2 — процедура
Выбирается параметром `failsafe_procedure`:

- `DROP` (дефолт) — мгновенный дизарм, моторы стоп. Повторный арм возможен после ≥3 с стабильной связи и выключенного тумблера ARM.
- `AUTO-LAND` — стики в центре, газ на `failsafe_throttle`, режимы Stage 1 применены, через `failsafe_off_delay` — дизарм. Повторный арм блокируется минимум на 30 с связи.
- `GPS_RESCUE` — нужен GPS: дрон летит домой и садится. Для возврата управления нужна связь `failsafe_recovery_delay` и отклонение стиков больше 30°.

Тонкость: если газ был на минимуме ≥10 с перед Stage 2, срабатывает простой дизарм (кроме GPS Rescue). Stage 2 невозможен первые 5 с после загрузки.

### Что выбрать
DROP — честный выбор для фристайла над безопасной зоной: дрон падает рядом, а не улетает. AUTO-LAND с газом чуть ниже висения даёт контролируемое снижение — разумно для тяжёлых 7–10" и полётов над людьми/техникой, но требует подобрать `failsafe_throttle` под конкретный дрон. AUTO-LAND без самовыравнивания бессмыслен: в Stage 1 на fallback-каналах должен включаться ANGLE.

### Тест тумблером: failsafe_switch_mode
Режим FAILSAFE на AUX-канале позволяет вызвать failsafe не выключая пульт:

- `STAGE1` — сразу Stage 1, AUX-каналы остаются активны. Держишь тумблер дольше `failsafe_delay` — переход в Stage 2. Отпустил — управление вернулось. Это самый честный тест: он повторяет реальную потерю связи.
- `STAGE2` — сразу выбранная процедура Stage 2, отпускание возвращает управление.
- `KILL` — мгновенный дизарм. Один глитч канала = падение. Не для полётов.

### Параметры целиком (CLI)
`failsafe_delay` (десятые секунды, Stage 1), `failsafe_off_delay` (десятые, время AUTO-LAND до дизарма), `failsafe_throttle` (газ AUTO-LAND, 1000–2000), `failsafe_throttle_low_delay` (десятые: если газ был ниже минимума дольше этого — просто дизарм; 0 = выкл), `failsafe_procedure` (DROP / AUTO-LAND / GPS-RESCUE), `failsafe_switch_mode` (STAGE1 / KILL / STAGE2), `failsafe_recovery_delay` (десятые, сколько связь должна быть стабильной до возврата), `failsafe_stick_threshold` (%, отклонение стика для выхода из GPS Rescue). Значения каналов на Stage 1 — `rxfail <channel> <mode> [value]`: `a` (auto: центр/мин газа), `h` (hold — удерживать последнее), `s <value>` (set — фиксированное значение, например 1700 на канале ANGLE). Проверка: `rxfail` без аргументов печатает таблицу.

### GPS Rescue: что нужно, чтобы он работал
GPS с fix ≥ `gps_rescue_min_sats` (8 по умолчанию) **до арма** (дом записывается при арме), `gps_rescue_min_start_dist` (минимальная дистанция, ближе — просто посадка/DROP логика), высота возврата `gps_rescue_alt_mode` (MAX_ALT / FIXED_ALT / CURRENT_ALT) и `gps_rescue_return_alt`, скорости `gps_rescue_ground_speed`, `gps_rescue_ascend_rate/descend_rate`, снижение и посадка `gps_rescue_descent_dist` (дистанция, с которой начинается снижение), `gps_rescue_descend_rate`, `gps_rescue_disarm_threshold` (дизарм при ударе), `gps_rescue_initial_climb`; без компаса курс берётся по GPS в движении — поэтому Rescue сначала набирает высоту и летит, «нащупывая» курс; с компасом (`mag_hardware`) надёжнее. Санитарные проверки (`gps_rescue_sanity_checks`) прерывают Rescue, если расстояние растёт или аппарат падает. Тест — только на открытой площадке, тумблером GPS RESCUE на умеренной высоте и дистанции, с пальцем на тумблере режима и наблюдателем; `gps_rescue_allow_arming_without_fix` оставить OFF — иначе Rescue без дома бесполезен.

### Разобранный пример: 7" long range
`failsafe_procedure = GPS-RESCUE`, `failsafe_delay = 10` (1 с: на 250 Гц это 250 потерянных пакетов — явная потеря), `gps_rescue_min_sats = 8`, `gps_rescue_alt_mode = MAX_ALT` (вернуться на максимальной высоте полёта + запас), `gps_rescue_return_alt = 50`, `gps_rescue_ground_speed = 1000` (10 м/с), `gps_rescue_descend_rate = 150`, `rxfail 5 s 1700` (канал ANGLE), ELRS: failsafe «no pulses» в приёмнике (иначе Stage 1 не начнётся), предупреждение LQ в OSD. Проверка: на земле без пропов — выключить пульт, в OSD «FAILSAFE», через 1 с «RESCUE» (без арма — только индикация); в поле — тумблером на 30 м высоты и 60 м от дома, наблюдатель, готовность перехватить.

## practice
### Шаг 1. Посмотреть текущие значения
Не заучивай дефолты — читай их с конкретного контроллера:

```
get failsafe
rxfail
```

### Шаг 2. Настроить AUTO-LAND с тестом по тумблеру
Пример из практики (7", тумблер failsafe на AUX6):

```
set failsafe_procedure = AUTO-LAND
set failsafe_switch_mode = STAGE1
set failsafe_delay = 15
set failsafe_throttle = 1250
set failsafe_off_delay = 100
save
```

Затем во вкладке Modes повесь FAILSAFE на тумблер, а в Channel fallback для канала ANGLE поставь значение, включающее ANGLE. Иначе на AUTO-LAND дрон снижается без выравнивания.

### Шаг 3. Подобрать газ failsafe по логу
1. Сделай полёт с висением и логом Blackbox.
2. Найди медианный газ висения (поле `rcCommand[3]` или motor average).
3. Поставь `failsafe_throttle` чуть ниже висения — цель около 1 м/с снижения. У тяжёлого 10" это может быть 1350, у лёгкого 7" — 1250: значение индивидуально.

### Шаг 4. Тест
1. Без пропов: арм, тумблер failsafe, убедись, что в OSD `FAILSAFE`, моторы ведут себя как ожидалось, после отпускания управление возвращается.
2. С пропами, на высоте 5–10 м над мягкой поверхностью: в ANGLE включить тумблер на 2–3 с, отпустить. Повторить с удержанием дольше `failsafe_delay`.
3. Записать в журнал дрона дату теста и параметры.

## diagnostics
- **Симптом:** после failsafe дрон не армится, в OSD `NOT_DISARMED`
  - Возможная причина: тумблер ARM остался включённым.
  - Что сделать: выключить и снова включить ARM после `failsafe_recovery_delay`.
- **Симптом:** на AUTO-LAND дрон кувыркается или уходит в сторону
  - Возможная причина: в Stage 1 не включается ANGLE (fallback канала режима не настроен).
  - Что сделать: настроить Channel fallback / `rxfail` для канала ANGLE.
- **Симптом:** на AUTO-LAND дрон набирает высоту
  - Возможная причина: `failsafe_throttle` выше газа висения (например, после смены АКБ или пропов).
  - Что сделать: пересчитать газ висения по свежему логу.
- **Симптом:** RXLOSS / failsafe в обычном полёте
  - Возможная причина: слабый линк (антенна приёмника, packet rate, мощность TX).
  - Что сделать: смотреть RSSI/LQ в логе, см. модуль про ExpressLRS.
- **Симптом:** при выключении пульта аппарат продолжает лететь по последним стикам
  - Возможная причина: приёмник не в режиме «no pulses»/cut — Stage 1 не начинается.
  - Что сделать: настроить failsafe приёмника (ELRS: по умолчанию «no pulses»; FrSky — выбрать), проверить без пропов.
- **Симптом:** GPS Rescue летит не домой / «сходит с ума»
  - Возможная причина: дом записан при плохом fix, нет компаса и мало скорости для курса по GPS, магнитные помехи.
  - Что сделать: армить после fix с 8+ спутниками, компас на мачте, проверить `gps_rescue_sanity_checks`.
- **Симптом:** после возврата связи управление не возвращается
  - Возможная причина: `failsafe_recovery_delay` + требование отклонить стики (`failsafe_stick_threshold`).
  - Что сделать: отклонить стик > порога; снизить recovery_delay умеренно.

## references
- Failsafe — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/failsafe | primary | A
- Failsafe tab — Betaflight App | https://betaflight.com/docs/wiki/app/failsafe-tab | primary | A
- What's Failsafe and How to Setup — Oscar Liang | https://oscarliang.com/failsafe-rx-fc-naze32-frsky-d4rii/ | secondary | B

## checklist
- Выбрана процедура Stage 2 и понятно, почему именно она
- FAILSAFE назначен на тумблер с `failsafe_switch_mode = STAGE1`
- Для AUTO-LAND: fallback включает ANGLE, газ подобран по логу
- Тест без пропов пройден
- Тест в воздухе на безопасной высоте пройден
- Параметры failsafe записаны в журнал дрона
