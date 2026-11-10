---
id: bf-failsafe
title: "Failsafe: стадії, процедури й тест тумблером"
level: L1
readingTime: 20 хв
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
source: content/betaflight/bf-failsafe.md
source_hash: 2a1cc24bc80b
---

## summary
Failsafe — то є то, що дрон робить, коли щез зв'язок із пультом. У Betaflight 4.3+ то двостадійний процес: коротка «захисна» Stage 1, потім Stage 2 з вибраною процедурою (DROP, AUTO-LAND або GPS_RESCUE). Модуль пояснює, як то влаштовано, як вибрати процедуру під свій дрон і як безпечно перевірити failsafe тумблером, а не вимикати пульт у повітрі.

## theory
### Як Betaflight розуміє, що зв'язок пропав
Як 100 мс нема валідних пакетів, сигнал вважається втраченим. Ще 300 мс тримаються останні значення, а тоді вмикається Stage 1. Відлік до Stage 2 іде від останнього доброго пакета.

{{diagram:failsafe-stages|Часова діаграма failsafe: виявлення втрати, коротке утримання, Stage 1 і Stage 2.}}

### Stage 1 — захисний інтервал
Триває `failsafe_delay` (у десятих частках секунди: 15 = 1.5 с; дефолт 1.5 с (так само в 4.3–4.4; між 4.4 і 4.5 змінився `failsafe_recovery_delay`: 1.0 → 0.5 с)). За замовчуванням стіки в центрі, газ на нулі, положення тумблерів тримаються. Значення для кожного каналу задаються в Configurator (Channel fallback) або командою `rxfail`. Як зв'язок вернувся під час Stage 1, керування вертається миттєво.

### Stage 2 — процедура
Вибирається параметром `failsafe_procedure`:

- `DROP` (дефолт) — миттєвий дизарм, мотори стоп. Повторний арм можливий після `failsafe_recovery_delay` стабільного зв'язку (0.5 с за замовчуванням у 4.5) і вимкненого тумблера ARM.
- `AUTO-LAND` — стіки в центрі, газ на `failsafe_throttle`, режими Stage 1 застосовано, через `failsafe_off_delay` — дизарм. Повторний арм — після `failsafe_recovery_delay` стабільного зв'язку, так само як у DROP.
- `GPS_RESCUE` — треба GPS: дрон летить додому й сідає. Аби вернути керування, треба зв'язок протягом `failsafe_recovery_delay` і відхилення стіків більше за `failsafe_stick_threshold` (30% ходу стіка).

Тонкощі: як газ був на мінімумі ≥10 с перед Stage 2, спрацьовує простий дизарм (крім GPS Rescue). Stage 2 не може бути перші 5 с після завантаження.

### Що вибрати
DROP — чесний вибір для фрістайлу над безпечною зоною: дрон падає поруч, а не відлітає гет кудись. AUTO-LAND з газом трохи нижче зависання дає контрольоване зниження — розумно для важких 7–10" і польотів над людьми/технікою, але треба підібрати `failsafe_throttle` під конкретний дрон. У Stage 2 (AUTO-LAND і GPS Rescue) Betaflight сам вмикає ANGLE, як є акселерометр; fallback каналу ANGLE впливає лиш на Stage 1.

### Тест тумблером: failsafe_switch_mode
Режим FAILSAFE на AUX-каналі дає змогу викликати failsafe і не вимикати пульт:

- `STAGE1` — зразу Stage 1, AUX-канали лишаються активними. Тримаєш тумблер довше за `failsafe_delay` — перехід у Stage 2. Відпустив — керування вернулося. То найчесніший тест: він повторює справжню втрату зв'язку.
- `STAGE2` — зразу вибрана процедура Stage 2, відпустив — керування вернулося.
- `KILL` — миттєвий дизарм. Один гліч каналу = падіння. Не для польотів, бай там як зручно.

### Параметри повністю (CLI)
`failsafe_delay` (десяті секунди, Stage 1), `failsafe_off_delay` (десяті, час AUTO-LAND до дизарму; у 2025.12 замінений на `failsafe_landing_time` у секундах, дефолт 60), `failsafe_throttle` (газ AUTO-LAND, 1000–2000), `failsafe_throttle_low_delay` (десяті: як газ був нижче мінімуму довше за то — просто дизарм; дефолт 100 = 10 с; 0 — дизарм за будь-якого низького газу в момент втрати зв'язку), `failsafe_procedure` (DROP / AUTO-LAND / GPS-RESCUE), `failsafe_switch_mode` (STAGE1 / KILL / STAGE2), `failsafe_recovery_delay` (десяті, скільки зв'язок мусить бути стабільним до повернення), `failsafe_stick_threshold` (%, відхилення стіка для виходу з GPS Rescue). Значення каналів на Stage 1 — `rxfail <channel> <mode> [value]`: `a` (auto: центр/мін газу), `h` (hold — тримати останнє), `s <value>` (set — фіксоване значення, наприклад 1700 на каналі ANGLE). Перевірка: `rxfail` без аргументів друкує таблицю.

### GPS Rescue: що треба, аби він працював
GPS із fix ≥ `gps_rescue_min_sats` (8 за замовчуванням) **до арму** (дім записується під час арму), `gps_rescue_min_start_dist` (мінімальна дистанція, ближче — просто логіка посадки/DROP), висота повернення `gps_rescue_alt_mode` (MAX_ALT / FIXED_ALT / CURRENT_ALT) і `gps_rescue_return_alt`, швидкості `gps_rescue_ground_speed`, `gps_rescue_ascend_rate/descend_rate`, зниження й посадка `gps_rescue_descent_dist` (дистанція, з котрої починається зниження), `gps_rescue_descend_rate`, `gps_rescue_disarm_threshold` (дизарм при ударі), `gps_rescue_initial_climb`; без компаса курс береться з GPS у русі — тому Rescue спершу набирає висоту й летить, «намацуючи» курс; з компасом (`mag_hardware`) надійніше. Санітарні перевірки (`gps_rescue_sanity_checks`) переривають Rescue, як відстань росте або апарат падає. Тест — лиш на відкритому майданчику, тумблером GPS RESCUE на помірній висоті й дистанції, з пальцем на тумблері режиму та зі спостерігачем; `gps_rescue_allow_arming_without_fix` лишити OFF — інакше Rescue без дому ніц не вартий.

### Розібраний приклад: 7" long range
`failsafe_procedure = GPS-RESCUE`, `failsafe_delay = 10` (1 с: на 250 Гц то 250 втрачених пакетів — явна втрата), `gps_rescue_min_sats = 8`, `gps_rescue_alt_mode = MAX_ALT` (вернутися на максимальній висоті польоту + запас), `gps_rescue_return_alt = 50`, `gps_rescue_ground_speed = 1000` (10 м/с), `gps_rescue_descend_rate = 150`, `rxfail 5 s 1700` (канал ANGLE), ELRS: failsafe «no pulses» у приймачі (інакше Stage 1 не почнеться), попередження LQ в OSD. Перевірка: на землі без пропів — вимкнути пульт: без арму failsafe не запускається, в OSD буде лиш `RXLOSS`; стадії перевіряти тумблером FAILSAFE в армі без пропів; у полі — тумблером на 30 м висоти й 60 м від дому, спостерігач, готовність перехопити.

## practice
### Крок 1. Глянути теперішні значення
Не зубри дефолти — читай їх із конкретного контролера:

```
get failsafe
rxfail
```

### Крок 2. Налаштувати AUTO-LAND з тестом тумблером
Приклад із практики (7", тумблер failsafe на AUX6):

```
set failsafe_procedure = AUTO-LAND
set failsafe_switch_mode = STAGE1
set failsafe_delay = 15
set failsafe_throttle = 1250
set failsafe_off_delay = 100
save
```

Потім у вкладці Modes признач FAILSAFE на тумблер, а в Channel fallback для каналу ANGLE постав значення, котре вмикає ANGLE. То треба лиш для Stage 1: у Stage 2 ANGLE вмикається сам (треба відкалібрований акселерометр).

### Крок 3. Підібрати газ failsafe за логом
1. Зроби політ із зависанням і логом Blackbox.
2. Знайди медіанний газ зависання (поле `rcCommand[3]` або motor average).
3. Постав `failsafe_throttle` трохи нижче зависання — ціль десь 1 м/с зниження. У важкого 10" то може бути 1350, у легкого 7" — 1250: значення в кожного своє.

### Крок 4. Тест
1. Без пропів: арм, тумблер failsafe, пересвідчи-ся, що в OSD `FAILSAFE`, мотори поводяться як треба, а після відпускання керування вертається.
2. З пропами, на висоті 5–10 м над м'якою поверхнею: в ANGLE ввімкнути тумблер на 2–3 с, відпустити. Повторити з утриманням довше за `failsafe_delay`.
3. Записати в журнал дрона дату тесту й параметри.

## diagnostics
- **Симптом:** після failsafe дрон не армиться, в OSD `NOT_DISARMED`
  - Можлива причина: тумблер ARM лишився ввімкненим.
  - Що зробити: вимкнути й знов увімкнути ARM після `failsafe_recovery_delay`.
- **Симптом:** на AUTO-LAND дрон перекидається або йде вбік
  - Можлива причина: акселерометр вимкнено або не відкалібровано (ANGLE у Stage 2 вмикається сам лиш з ACC), або `failsafe_throttle` не підібрано.
  - Що зробити: налаштувати Channel fallback / `rxfail` для каналу ANGLE.
- **Симптом:** на AUTO-LAND дрон набирає висоту
  - Можлива причина: `failsafe_throttle` вищий за газ зависання (наприклад, після зміни АКБ або пропів).
  - Що зробити: перерахувати газ зависання за свіжим логом.
- **Симптом:** RXLOSS / failsafe у звичайному польоті
  - Можлива причина: слабкий лінк (антена приймача, packet rate, потужність TX).
  - Що зробити: дивитися RSSI/LQ у лозі, див. модуль про ExpressLRS.
- **Симптом:** як вимкнути пульт, апарат далі летить за останніми стіками
  - Можлива причина: приймач не в режимі «no pulses»/cut — Stage 1 не починається.
  - Що зробити: налаштувати failsafe приймача (ELRS: за замовчуванням «no pulses»; FrSky — вибрати), перевірити без пропів.
- **Симптом:** GPS Rescue летить не додому / «дуріє»
  - Можлива причина: дім записано за поганого fix, нема компаса й замала швидкість для курсу за GPS, магнітні завади.
  - Що зробити: армити після fix із 8+ супутниками, компас на щоглі, перевірити `gps_rescue_sanity_checks`.
- **Симптом:** зв'язок вернувся, а керування — ні
  - Можлива причина: `failsafe_recovery_delay` + вимога відхилити стіки (`failsafe_stick_threshold`).
  - Що зробити: відхилити стік > порога; помірно знизити recovery_delay.

## references
- Failsafe — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/Failsafe | primary | A
- Failsafe tab — Betaflight App | https://betaflight.com/docs/wiki/app/failsafe-tab | primary | A
- Betaflight — Failsafe tab | https://betaflight.com/docs/wiki/app/failsafe-tab | secondary | B

## checklist
- Вибрано процедуру Stage 2 і ясно, чом саме її
- FAILSAFE призначено на тумблер із `failsafe_switch_mode = STAGE1`
- Для AUTO-LAND: fallback вмикає ANGLE, газ підібрано за логом
- Тест без пропів пройдено
- Тест у повітрі на безпечній висоті пройдено
- Параметри failsafe записано в журнал дрона
