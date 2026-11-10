---
id: bf-pid-reg-in-bf
title: "PID-налаштування в Betaflight"
level: L2
readingTime: 25 хв
firmware: Betaflight 4.5+
status: published
tags:
  - PID
  - tuning
  - Betaflight
  - Blackbox
references:
  - title: "Betaflight PID Tuning Guide"
    url: "https://betaflight.com/docs/wiki/guides/current/PID-Tuning-Guide"
    tier: primary
    stack: betaflight
  - title: "Betaflight DShot RPM Filtering"
    url: "https://betaflight.com/docs/wiki/guides/current/DSHOT-RPM-Filtering"
    tier: primary
    stack: betaflight
related:
  - bf-filters
  - bf-blackbox
next:
  - bf-cli
source: content/betaflight/bf-pid-reg-in-bf.md
source_hash: afbfb4abd3e9
---

## summary

PID-регулятор — ядро стабілізації в Betaflight. Стаття пояснює фізичний зміст коефіцієнтів P, I, D, їхню взаємодію, вплив на поведінку дрона та методи налаштування з використанням Blackbox. Після вивчення читач зможе діагностувати типові проблеми (осциляції, bounce-back, перегрів моторів) і цілеспрямовано коригувати параметри, уникаючи хаотичного підбору.

## theory

PID-регулятор (Proportional-Integral-Derivative) отримує від гіроскопа кутову швидкість за осями roll, pitch, yaw і мінімізує помилку між бажаною (setpoint, від стиків або навігації) і поточною швидкістю обертання. Вихід регулятора (PID sum) через мікшер перетворюється на сигнали для моторів.

**P-term (пропорційний)** реагує на поточну помилку: що більша помилка, то сильніша корекція. Визначає основну жорсткість дрона. Недолік: не може повністю усунути статичну помилку (дрейф). При завищенні викликає швидкі осциляції (20–50 Гц).

**I-term (інтегральний)** накопичує помилку в часі, усуваючи постійне відхилення (дрейф від вітру, зміщення центру мас). Працює повільніше за P. При завищенні викликає повільні плавні осциляції (1–5 Гц) і ефект wind-up. Параметр `iterm_limit` (у 2025.12 — `iterm_windup`) обмежує максимальне значення I-term.

**D-term (диференціальний)** реагує на швидкість зміни помилки, діючи як демпфер. Пригнічує коливання, викликані P-термом. Критично чутливий до шуму гіроскопа. Без фільтрації створює високочастотний шум, що перегріває мотори. Правило: D-term налаштовується після P-term; збільшення P вимагає збільшення D.

**Специфіка Betaflight 4.5+:**

- **Feedforward** — незалежний канал керування, що подає сигнал прямо на мотори на основі швидкості руху стика. Пришвидшує відгук без збільшення P-term.
- **TPA (Throttle PID Attenuation)** — зниження PID-коефіцієнтів на високих обертах. У BF 4.5+ за замовчуванням `tpa_mode = D` (знижує тільки D-term); доступний і `PD`.
- **RPM Filtering** — використання даних з ESC для пригнічення шуму від пропелерів. Створює вузькі фільтри на частоті обертання моторів, дозволяючи піднімати D-term.

### Формула, як вона реалізована у `flight/pid.c`
Для кожної осі в кожному циклі (на частоті PID): помилка e = setpoint − gyro (відфільтрований);
- P = Kp·e;
- I += Ki·e·dt з обмеженням `iterm_limit` (анти-windup) і «релаксацією» (нижче);
- D = −Kd·d(gyro_D)/dt — похідна **від гіроскопа**, а не від помилки (рух стика не створює удару по D), після D-фільтрів (модуль «Фільтри»), з множником `d_min`-логіки;
- FF = Kff·d(setpoint)/dt з усередненням/згладжуванням (`feedforward_averaging`, `feedforward_smooth_factor`, `feedforward_jitter_factor`, `feedforward_boost` — додаток від другої похідної, `feedforward_max_rate_limit`);
- сума → TPA → `pidSum` → мікшер.
Коефіцієнти з конфігуратора («45») множаться на масштаби в `pid_init.c` (P ≈ 0.032, I ≈ 0.244, D ≈ 0.00053, FF ≈ 0.0138) — це і є «безрозмірність» Betaflight; фізичний зміст відновлюється тільки через відгук (модуль «Теорія керування»).

### Механізми, яких немає в підручнику з PID
- **I-term relax** (`iterm_relax = RP`, `iterm_relax_type = SETPOINT`, `iterm_relax_cutoff = 15`): під час швидких рухів стика накопичення I призупиняється — інакше після фліпу I «довозить» зайвий поворот (bounce-back одного з типів). Cutoff нижчий → релакс агресивніший.
- **I-term rotation** (`iterm_rotation`): під час обертання по yaw накопичені I по roll/pitch повертаються разом з рамою.
- **Anti-gravity** (`anti_gravity_gain`, `anti_gravity_p_gain`, `anti_gravity_cutoff_hz`): тимчасово піднімає I (і P) при різких змінах газу — проти «клювка» при ударі по газу.
- **D_min / D_max** (4.5: `d_min_*` — база, `d_*` — пік; 2025.12: `d_*` — база, `d_max_*` — пік; плюс `d_max_gain`, `d_max_advance`): D низький у спокійному польоті (менше шуму/нагріву), зростає на швидких рухах і пропвоші за гіроскопом/setpoint.
- **TPA** (`tpa_mode = D` за замовчуванням у 4.5, `tpa_rate`, `tpa_breakpoint`; у 4.5+ є і `tpa_low_*` для низького газу): знижує D (або PD) вище точки газу — на високому газі тяга лінійніша, а шум вищий.
- **Thrust linearization** (`thrust_linear`) і **throttle boost**: компенсація нелінійності тяги від газу і короткочасне посилення відгуку газу.
- **Air mode**: PID працює і на нульовому газі (`feature AIRMODE` або режим AIR MODE), з мінімальним idle (`dshot_idle_value`; у 2025.12 — `motor_idle`) — інакше на спуску без газу апарат некерований.

### Розібраний приклад: звідки bounce-back
Лог: після різкої зупинки стика по roll гіроскоп іде на −18% від амплітуди маневру. Перевіряємо по черзі: (1) D-фільтри не надто низькі (затримка) — `dterm_lpf1_dyn_max_hz` 150 → ок; (2) D достатньо? слайдер Damping 1.0 → 1.15 — bounce-back 18 → 11%, мотори теплі; (3) I-relax увімкнений (`iterm_relax = RP`) — так; (4) механіка — спектр чистий. Підсумок: Damping 1.15, запис у таблицю рішень. Якби мотори грілися — шлях був би зворотний: фільтри/механіка, а не D.

{{diagram:bf-pid-terms|PID у Betaflight: P та I від помилки, D — за гіроскопом (з d_min), FF — від похідної setpoint; усе складається в pidSum.}}

## practice

{{widget:pid-sim}}


**Підготовка**

Апаратні вимоги: ESC з підтримкою RPM Filtering (BLHeli_32 або Bluejay), польотний контролер F7/H7, карта пам'яті SD для Blackbox (мінімум 4 ГБ).

Програмні вимоги: Betaflight Configurator 10.10+, Blackbox Explorer.

**Налаштування перед тюнінгом**

1. Увімкни RPM Filtering: у вкладці Motors увімкни **Bidirectional DShot** і задай Motor poles (RPM-фільтр увімкнеться сам); `rpm_filter_q = 500` — значення за замовчуванням (CLI).
2. Налаштуй Blackbox: вибери частоту запису 2 кГц, увімкни логування gyro_scaled, pid, setpoint, motor.
3. Встанови базові параметри фільтрації:
set gyro_lpf2_static_hz = 300
set gyro_lpf2_type = PT2
set dterm_lpf2_static_hz = 150
set dterm_lpf2_type = PT2
set dyn_notch_max_hz = 600
set dyn_notch_q = 250
save

text

**Покрокове налаштування**

1. Визнач стартові значення (для рами 5" з моторами 2207–2306):
set p_pitch = 45\nset i_pitch = 50\nset d_pitch = 25
set p_roll = 42, i_roll = 45, d_roll = 23
set p_yaw = 70, i_yaw = 50, d_yaw = 20
set d_min_roll = 20\nset d_min_pitch = 22\n# 2025.12: d_roll/d_pitch — базовий D, d_max_roll/d_max_pitch — піковий
save

text

2. Налаштування P-term: виконай різкий ривок стиком з поверненням. У Blackbox дивися графік gyro (синій) і setpoint (зелений). Якщо gyro перетинає setpoint у зворотний бік (bounce-back) — P низький, збільш на 10. Якщо gyro коливається навколо setpoint — P високий, зменш на 5.

3. Налаштування D-term: після налаштування P виконай той самий рух. Додай графік D-term. Якщо D-term тремтить високочастотним шумом — знизь D на 3–5. Якщо після руху gyro йде із загасаючими коливаннями — збільш D на 3.

4. Налаштування I-term: зависни в режимі Angle/Horizon, злегка нахили дрон і поверни в нуль. Якщо дрон повільно дрейфує — збільш I на 10. Якщо проходить нейтраль і розгойдується — зменш I на 10.

5. Налаштування Feedforward: виконай серію швидких рухів стиком. У Blackbox порівняй setpoint і gyro. При великому відставанні збільш `feedforward_boost`. При overshoot зменш `feedforward_boost`.

6. Налаштування TPA: виконай punch-out (20% → 80% газу). Якщо motor виходить на 100% без зниження — перевір `tpa_rate`. При високочастотній пульсації збільш `tpa_rate` (відсотки, 0–100; дефолт 65) до 70–80, знизь `tpa_breakpoint` до 1400.

**Завершальні кроки**

Збережи фінальні параметри: `diff all`. Виконай короткий політ (2–3 хвилини) і перевір температуру моторів. Якщо мотори гарячі, знизь D-term на 10–15%.

## diagnostics

- **Симптом: Швидкі осциляції на зависанні (дзижчання, тремтіння)**
- Можлива причина: завищений P-term, недостатня фільтрація гіроскопа.
- Що перевірити/зробити: зняти Blackbox. Якщо графік gyro має часті піки 50–100 Гц — зменшити P на 20%. Перевірити роботу dynamic notch і RPM filtering.

- **Симптом: Bounce-back після різкого руху**
- Можлива причина: низький P-term, високий D-term.
- Що перевірити/зробити: у Blackbox порівняти setpoint і gyro: gyro не доходить до setpoint. Збільшити P на 10%. Якщо bounce-back не зникає — перевірити D-term.

- **Симптом: Повільні плавні коливання (~1–3 Гц)**
- Можлива причина: завищений I-term, неправильний anti-windup.
- Що перевірити/зробити: зменшити I на 15–20%. Перевірити `iterm_limit` (дефолт 400; у 2025.12 — `iterm_windup`).

- **Симптом: Перегрів моторів**
- Можлива причина: високий D-term, недостатня фільтрація D-term.
- Що перевірити/зробити: у Blackbox подивитися графік D-term — якщо схожий на шум, знизити D на 20–30%. Знизити `dterm_lpf2_static_hz` до 100–120 Гц.

- **Симптом: Дрон відходить при різкому додаванні газу (punch-out)**
- Можлива причина: неправильне налаштування TPA, високий P/D без атенюації.
- Що перевірити/зробити: у Blackbox на графіку throttle знайти punch-out. Якщо PID sum кліпує — збільшити `tpa_rate` або знизити `tpa_breakpoint`.

- **Симптом: Шум на гіроскопі в логах (пилкоподібний графік)**
- Можлива причина: механічні вібрації, непрацюючий RPM Filtering.
- Що перевірити/зробити: перевірити роботу RPM Filtering (у вкладці Motors має відображатися частота обертання). Опустити `gyro_lpf2_static_hz` до 250–300 Гц.
- **Симптом:** після удару по газу апарат «клює» носом
  - Можлива причина: I не встигає, anti-gravity малий.
  - Що зробити: `anti_gravity_gain` вище, перевірити `thrust_linear`.
- **Симптом:** I-term видно в логу як зростання після фліпу і «довіз»
  - Можлива причина: I-term relax вимкнений або cutoff високий.
  - Що зробити: `iterm_relax = RP`, cutoff 10–15.

## references

- Betaflight PID Tuning Guide | https://betaflight.com/docs/wiki/guides/current/PID-Tuning-Guide | primary | A
- Betaflight DShot RPM Filtering | https://betaflight.com/docs/wiki/guides/current/DSHOT-RPM-Filtering | primary | A
- Betaflight Blackbox logging and usage | https://betaflight.com/docs/wiki/guides/current/Black-Box-logging-and-usage | primary | A
- Oscar Liang: Betaflight PID Tuning | https://oscarliang.com/betaflight-pid-tuning/ | secondary | B
- Joshua Bardwell: How to Tune PID with Blackbox | https://www.youtube.com/watch?v=YXpPajW9lCU | secondary | B
