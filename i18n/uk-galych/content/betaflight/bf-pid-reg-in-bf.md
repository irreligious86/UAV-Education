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

PID-регулятор — то є ядро стабілізації в Betaflight. Стаття пояснює фізичний зміст коефіцієнтів P, I, D, як вони ся між собою взаємодіють, як впливають на поведінку дрона і як їх налаштовувати з Blackbox. Після того читач зможе діагностувати типові біди (осциляції, bounce-back, перегрів моторів) і цілеспрямовано правити параметри, а не крутити все навмання.

## theory

PID-регулятор (Proportional-Integral-Derivative) отримує від гіроскопа кутову швидкість за осями roll, pitch, yaw і мінімізує помилку між бажаною (setpoint, від стиків або навігації) і поточною швидкістю обертання. Вихід регулятора (PID sum) через мікшер перетворюється на сигнали для моторів.

**P-term (пропорційний)** реагує на поточну помилку: що більша помилка, то сильніша корекція. Він визначає основну жорсткість дрона. Біда в тому, що статичної помилки (дрейфу) він гет не прибере. Як його перекрутити — маєш швидкі осциляції (20–50 Гц).

**I-term (інтегральний)** накопичує помилку в часі й прибирає постійне відхилення (дрейф від вітру, зміщення центру мас). Працює повільніше за P. Як його завищити — дістанеш повільні плавні осциляції (1–5 Гц) і ефект wind-up. Параметр `iterm_limit` (у 2025.12 — `iterm_windup`) обмежує максимальне значення I-term.

**D-term (диференціальний)** реагує на швидкість зміни помилки й працює як демпфер. Він гасить коливання, які розгойдує P-терм. До шуму гіроскопа він фест чутливий: без фільтрації дає високочастотний шум, що перегріває мотори. Правило: D-term налаштовується після P-term; більший P — то й більший D.

**Специфіка Betaflight 4.5+:**

- **Feedforward** — незалежний канал керування, що подає сигнал просто на мотори на основі швидкості руху стика. Пришвидшує відгук без збільшення P-term.
- **TPA (Throttle PID Attenuation)** — зниження PID-коефіцієнтів на високих обертах. У BF 4.5+ за замовчуванням `tpa_mode = D` (знижує лише D-term); доступний і `PD`.
- **RPM Filtering** — дані з ESC ідуть на придушення шуму від пропелерів. Створюються вузькі фільтри на частоті обертання моторів, і D-term можна піднімати.

### Формула, як вона реалізована у `flight/pid.c`
Для кожної осі в кожному циклі (на частоті PID): помилка e = setpoint − gyro (відфільтрований);
- P = Kp·e;
- I += Ki·e·dt з обмеженням `iterm_limit` (анти-windup) і «релаксацією» (нижче);
- D = −Kd·d(gyro_D)/dt — похідна **від гіроскопа**, а не від помилки (рух стика не б'є по D), після D-фільтрів (модуль «Фільтри»), з множником `d_min`-логіки;
- FF = Kff·d(setpoint)/dt з усередненням/згладжуванням (`feedforward_averaging`, `feedforward_smooth_factor`, `feedforward_jitter_factor`, `feedforward_boost` — додаток від другої похідної, `feedforward_max_rate_limit`);
- сума → TPA → `pidSum` → мікшер.
Коефіцієнти з конфігуратора («45») множаться на масштаби в `pid_init.c` (P ≈ 0.032, I ≈ 0.244, D ≈ 0.00053, FF ≈ 0.0138) — то і є «безрозмірність» Betaflight; фізичний зміст ся відновлює лише через відгук (модуль «Теорія керування»).

### Механізми, яких нема в підручнику з PID
- **I-term relax** (`iterm_relax = RP`, `iterm_relax_type = SETPOINT`, `iterm_relax_cutoff = 15`): під час швидких рухів стика накопичення I призупиняється — інакше після фліпу I «довозить» зайвий поворот (bounce-back одного з типів). Cutoff нижчий → релакс агресивніший.
- **I-term rotation** (`iterm_rotation`): під час обертання по yaw накопичені I по roll/pitch повертаються разом з рамою.
- **Anti-gravity** (`anti_gravity_gain`, `anti_gravity_p_gain`, `anti_gravity_cutoff_hz`): на якийсь час піднімає I (і P) при різких змінах газу — проти «клювка», коли даєш по газу.
- **D_min / D_max** (4.5: `d_min_*` — база, `d_*` — пік; 2025.12: `d_*` — база, `d_max_*` — пік; плюс `d_max_gain`, `d_max_advance`): D низький у спокійному польоті (менше шуму/нагріву), росте на швидких рухах і пропвоші за гіроскопом/setpoint.
- **TPA** (`tpa_mode = D` за замовчуванням у 4.5, `tpa_rate`, `tpa_breakpoint`; у 4.5+ є і `tpa_low_*` для низького газу): знижує D (або PD) вище точки газу — на високому газі тяга лінійніша, а шум вищий.
- **Thrust linearization** (`thrust_linear`) і **throttle boost**: компенсація нелінійності тяги від газу і короткочасне посилення відгуку газу.
- **Air mode**: PID працює і на нульовому газі (`feature AIRMODE` або режим AIR MODE), з мінімальним idle (`dshot_idle_value`; у 2025.12 — `motor_idle`) — інакше на спуску без газу апарат некерований.

### Розібраний приклад: звідки bounce-back
Лог: після різкої зупинки стика по roll гіроскоп іде на −18% від амплітуди маневру. Перевіряємо по черзі: (1) D-фільтри не надто низькі (затримка) — `dterm_lpf1_dyn_max_hz` 150 → ок; (2) D досить? слайдер Damping 1.0 → 1.15 — bounce-back 18 → 11%, мотори теплі; (3) I-relax увімкнений (`iterm_relax = RP`) — так; (4) механіка — спектр чистий. Підсумок: Damping 1.15, запис у таблицю рішень. Якби мотори ся гріли — шлях був би зворотний: фільтри/механіка, а не D.

{{diagram:bf-pid-terms|PID у Betaflight: P та I від помилки, D — за гіроскопом (з d_min), FF — від похідної setpoint; усе складається в pidSum.}}

{{diagram:chart-bf-thrust-linear|thrust_linear поднимает наклон команды у нуля до 1 + k, при x = 1/3 наклон снова равен 1, выше он чуть меньше 1: функция полезна на малом газу и почти не трогает висение 5″.}}

{{diagram:chart-bf-tpa-factor|TPA линейно снижает множитель D от tpa_breakpoint до 1 − tpa_rate/100 на полном газу (0.35 при умолчаниях); TPA малого газа (0.8 на нуле) действует только до первого прохода 1050 после включения.}}

## practice

{{widget:pid-sim}}


**Підготовка**

Апаратні вимоги: ESC з підтримкою RPM Filtering (BLHeli_32 або Bluejay), польотний контролер F7/H7, карта пам'яті SD для Blackbox (мінімум 4 ГБ).

Програмні вимоги: Betaflight Configurator 10.10+, Blackbox Explorer.

**Налаштування перед тюнінгом**

1. Увімкни RPM Filtering: у вкладці Motors увімкни **Bidirectional DShot** і задай Motor poles (RPM-фільтр увімкнеться сам); `rpm_filter_q = 500` — значення за замовчуванням (CLI).
2. Налаштуй Blackbox: вибери частоту запису 2 кГц, увімкни логування gyro_scaled, pid, setpoint, motor.
3. Встанови базові параметри фільтрації:

```text
set gyro_lpf2_static_hz = 300
set gyro_lpf2_type = PT2
set dterm_lpf2_static_hz = 150
set dterm_lpf2_type = PT2
set dyn_notch_max_hz = 600
set dyn_notch_q = 250
save
```

**Покрокове налаштування**

1. Визнач стартові значення (для рами 5" з моторами 2207–2306):

```text
set p_roll = 45
set i_roll = 80
set d_roll = 40
set d_min_roll = 30
set p_pitch = 47
set i_pitch = 84
set d_pitch = 46
set d_min_pitch = 34
set p_yaw = 45
set i_yaw = 80
set d_yaw = 0
save
```

2. Налаштування P-term: дай різкий ривок стиком з поверненням. У Blackbox дивися графік gyro (синій) і setpoint (зелений). Як gyro перетинає setpoint у зворотний бік (bounce-back) — P низький, додай 10. Як gyro коливається довкола setpoint — P високий, зменш на 5.

3. Налаштування D-term: після P зроби той самий рух. Додай графік D-term. Якщо D-term тремтить високочастотним шумом — знизь D на 3–5. Якщо після руху gyro йде із загасаючими коливаннями — додай D на 3.

4. Налаштування I-term: зависни в режимі Angle/Horizon, злегка нахили дрон і верни в нуль. Якщо дрон помалу дрейфує — додай I на 10. Якщо проскакує нейтраль і ся розгойдує — зменш I на 10.

5. Налаштування Feedforward: зроби серію швидких рухів стиком. У Blackbox порівняй setpoint і gyro. При великому відставанні збільш `feedforward_boost`. При overshoot зменш `feedforward_boost`.

6. Налаштування TPA: зроби punch-out (20% → 80% газу). Якщо motor виходить на 100% без зниження — перевір `tpa_rate`. При високочастотній пульсації збільш `tpa_rate` (відсотки, 0–100; дефолт 65) до 70–80, знизь `tpa_breakpoint` до 1400.

**Завершальні кроки**

Збережи фінальні параметри: `diff all`. Зроби короткий політ (2–3 хвилини) і перевір температуру моторів. Як мотори гарячі — знизь D-term на 10–15%.


```python
# Тракт газа Betaflight 4.5.3: flight/pid.c, pid_init.c, mixer.c, mixer_init.c
def tl(x, k):                                   # pidApplyThrustLinearization
    return x * (1 + k * (1 - x) ** 2)

def tl_comp(t, k):                              # pidCompensateThrustLinearization
    return t / (1 + (k - 0.5 * k * k) * (1 - t) ** 2)

def tpa(thr, rate=65, bp=1350, low_rate=20, low_bp=1050, faded=True):
    t, tbp = (thr - 1000) / 1000, min((bp - 1000) / 1000, 0.99)
    lbp = min(max((low_bp - 1000) / 1000, 0.01), tbp)
    if t >= lbp or faded:                       # pidUpdateTpaFactor
        return 1 - rate / 100 / (1 - tbp) * max(t - tbp, 0)
    return 1 - low_rate / (100 * lbp) * (lbp - t)

def sag(cell_v, comp=100, warn=3.50):           # доля верха диапазона, которую срезает vbat_sag
    rng = 4.20 - warn
    good = 1 - min(max((4.20 - cell_v) / rng, 0), 1)
    return rng / 4.20 * good * comp / 100

print("TL 40: x=0.10 ->", round(tl(0.10, 0.4), 3), "| x=0.50 ->", round(tl(0.50, 0.4), 3))
t = tl_comp(0.30, 0.4)
print("TL 40, висение 0.30: газ после компенсации", round(t, 4), "выход", round(tl(t, 0.4), 4))
for thr in (1000, 1500, 2000):
    print(f"TPA {thr}: до прохода 1050 {tpa(thr, faded=False):.3f}, после {tpa(thr):.3f}")
for warn in (3.50, 3.00):
    print(f"sag 100, warn {warn:.2f}: 4.20 В -> {sag(4.20, 100, warn)*100:.1f} %,"
          f" 3.80 В -> {sag(3.80, 100, warn)*100:.1f} %, 3.30 В -> {sag(3.30, 100, warn)*100:.1f} %")
print("dyn idle 30 ->", 30 * 100 / 60, "об/с; нижняя граница DShot:", round(48 + 0.055 * 1999, 1), "-> 48")
```

```text
TL 40: x=0.10 -> 0.132 | x=0.50 -> 0.55
TL 40, висение 0.30: газ после компенсации 0.2593 выход 0.3162
TPA 1000: до прохода 1050 0.800, после 1.000
TPA 1500: до прохода 1050 0.850, после 0.850
TPA 2000: до прохода 1050 0.350, после 0.350
sag 100, warn 3.50: 4.20 В -> 16.7 %, 3.80 В -> 7.1 %, 3.30 В -> 0.0 %
sag 100, warn 3.00: 4.20 В -> 28.6 %, 3.80 В -> 19.0 %, 3.30 В -> 7.1 %
dyn idle 30 -> 50.0 об/с; нижняя граница DShot: 157.9 -> 48
```

## diagnostics

- **Симптом: Швидкі осциляції на зависанні (дзижчання, тремтіння)**
- Можлива причина: завищений P-term, замала фільтрація гіроскопа.
- Що перевірити/зробити: зняти Blackbox. Якщо графік gyro має часті піки 50–100 Гц — зменшити P на 20%. Перевірити, ци працюють dynamic notch і RPM filtering.

- **Симптом: Bounce-back після різкого руху**
- Можлива причина: низький P-term, високий D-term.
- Що перевірити/зробити: у Blackbox порівняти setpoint і gyro: gyro не доходить до setpoint. Збільшити P на 10%. Якщо bounce-back не щезає — перевірити D-term.

- **Симптом: Повільні плавні коливання (~1–3 Гц)**
- Можлива причина: завищений I-term, неправильний anti-windup.
- Що перевірити/зробити: зменшити I на 15–20%. Перевірити `iterm_limit` (дефолт 400; у 2025.12 — `iterm_windup`).

- **Симптом: Перегрів моторів**
- Можлива причина: високий D-term, замала фільтрація D-term.
- Що перевірити/зробити: у Blackbox глянути графік D-term — якщо він схожий на шум, знизити D на 20–30%. Знизити `dterm_lpf2_static_hz` до 100–120 Гц.

- **Симптом: Дрон відходить при різкому додаванні газу (punch-out)**
- Можлива причина: неправильне налаштування TPA, високий P/D без атенюації.
- Що перевірити/зробити: у Blackbox на графіку throttle знайти punch-out. Якщо PID sum кліпує — збільшити `tpa_rate` або знизити `tpa_breakpoint`.

- **Симптом: Шум на гіроскопі в логах (пилкоподібний графік)**
- Можлива причина: механічні вібрації, RPM Filtering не працює.
- Що перевірити/зробити: перевірити роботу RPM Filtering (у вкладці Motors має показуватися частота обертання). Опустити `gyro_lpf2_static_hz` до 250–300 Гц.
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
