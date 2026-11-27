---
id: el-power-design
title: "Схемотехніка живлення борту"
level: L2
readingTime: 35 хв
firmware: будь-яка прошивка
status: published
added: 2026-11-08
tags:
  - живлення
  - BEC
  - конденсатор
  - захист
related:
  - f-power
  - el-measure
  - el-wiring
next:
  - el-measure
source: content/electronics/el-power-design.md
source_hash: 5ed30d1d2160
---

## summary
Борт — то кілька шин живлення з різними вимогами: силова шина моторів витримує просідання й пульсації, а польотник, приймач, GPS і камера — гет ні. Модуль вчить порахувати струми по гілках, вибрати BEC за струмом і напругою, переріз проводів за струмом і довжиною, зрозуміти, звідки ся беруть просідання й пульсації і чому низькоESR-конденсатор на шині — не опція, а частина схеми. Окремо — захист: smoke stopper, запобіжник, переполюсування.

## theory
### Карта споживачів
Заки вибирати компоненти, намалюй дерево живлення: АКБ → силова шина → (ESC ×4…8, BEC 5 В, BEC 9–12 В) → споживачі. Типові струми:

{{diagram:power-tree|Дерево живлення: від АКБ до силової шини й окремих BEC; кожен споживач — зі своїм струмом.}}

| Споживач | Напруга | Типовий струм |
|---|---|---|
| FC + гіроскоп | 5 В (внутр. 3.3) | 0.1–0.2 А |
| Приймач ELRS | 5 В | 0.1–0.3 А (TX-модуль на борту до 0.5) |
| GPS із компасом | 5 В (3.3) | 0.05–0.1 А |
| Цифрова відеосистема (air unit) | 9–12 В | 0.5–1.2 А, піки вищі |
| Аналоговий VTX 800 мВт–1 Вт | 9–12 В / 5 В | 0.4–0.7 А |
| Серви (крило) | 5–6 В / 7.4 В | 0.5–1 А кожна під час руху |
| Companion (Pi 4/5) | 5 В | 1–3 А, піки до 5 |
| Підсвітка/LED | 5 В | 0.06 А на світлодіод |

Додай 50% запасу: BEC 5 В на борту з GPS, приймачем і FC без companion — 1 А вистачить, а з Raspberry — треба окремий BEC на 3–5 А.

### Лінійний vs імпульсний BEC
- **Лінійний (LDO)** — скидає зайву напругу в тепло: при 6S (25 В) → 5 В і 0.5 А розсіює 10 Вт. Не надається для високих напруг і струмів, зате без пульсацій — файний для гіроскопа та RF.
- **Імпульсний (buck)** — ККД 85–95%, але дає пульсації на частоті перетворення (сотні кГц) і їхні гармоніки; поганий buck коло приймача — і LQ пропадає. На польотниках стоїть buck 5 В / 9 В із фільтруванням.
- Добрий прийом: buck до 5.5–6 В, потім LDO до 5 В для чутливої частини (так зроблено на багатьох FC: 3.3 В для гіроскопа через LDO).

### Просідання та внутрішній опір
Напруга під навантаженням U = E − I·Rвн. Rвн АКБ 6S Li-Ion 4P ≈ 20–40 мОм на комірку → 30–60 мОм на пакет (R × 6 / 4); при 60 А просідання 1.8–3.6 В. До того проводи: 12 AWG ≈ 5.2 мОм/м, 14 AWG ≈ 8.3, 16 AWG ≈ 13.2. 20 см туди-назад 14 AWG при 60 А — 0.2 В, то мало; але XT60-роз'єм з окисненими контактами може дати й більше.

Просідання небезпечне не само по собі, а тим, що BEC на польотнику дістає вхідну напругу нижчу за поріг (деякі buck ся вимикають нижче 7–8 В на 2S) — і FC перезавантажується просто в польоті.

### Пульсації та конденсатор
ESC комутують обмотки з частотою в десятки кГц, струм у проводах від АКБ смикається. Індуктивність проводів L (≈1 мкГн на метр) перетворює dI/dt на викиди напруги: U = L·dI/dt. То є **пульсації та шпильки** на силовій шині, які лізуть у живлення FC, у гіроскоп (шум у логу) і у відео (смуги). Рішення — низькоESR електроліт або полімерний конденсатор просто на силових падах ESC/PDB: 470–1000 мкФ на 35 В для 4S, 1000 мкФ на 50 В для 6S (запас ≥ 30% за напругою). Він працює як локальне джерело: віддає енергію на фронті й гасить викид. Виводи короткі — бо інакше індуктивність виводів зводить ефект нанівець.

{{diagram:chart-power-lc-filter|LC-фильтр 22 мкГн + 470 мкФ ослабляет пульсации ESC на 24 кГц на десятки дБ, но на резонансе 1.6 кГц усиливает: низкий ESR даёт +11 дБ подъёма, ESR 0.15 Ом гасит его ценой ослабления на высоких частотах.}}

### Захист
- **Smoke stopper** — лампочка або резистор/обмежувач струму в розрив плюса під час першого ввімкнення. Як є КЗ — лампочка світиться, а борт не димить.
- **Запобіжник** — на великих апаратах на силовій шині (не на моторах — струм там завеликий та імпульсний) і на шині companion.
- **Переполюсування** — XT60/XT30 захищають геометрією, але як спаяв навпаки — плата гине за секунду. Діод Шотткі послідовно (спад 0.3–0.5 В) або P-MOSFET в ідеальному діоді для низьковольтних гілок.
- **Роз'єми** (правило курсу — паспорти Amass, посилання в джерелах): тривалий струм — «рекомендований струм» паспорта для твого калібру проводу при перегріві ≤ 60 K, короткочасний (до 1 хв) — не вище паспортного миттєвого. XT30 — 15 А на 18 AWG (20 А на 16 AWG), до 30 А короткочасно; XT60 — 30 А тривало і 60 А миттєво на 12 AWG (паспорт V1.2 умов не вказує; Holybro для 12 AWG дає ті самі 30 А за 4 год і 60 А за 1 хв при перегріві < 60 K); XT90 — 45 А на 12 AWG, 50 А на 10 AWG, 55 А на 8 AWG, до 60 А за 1 хв (номінал за UL1977 — 30 А; 40 А трапляється лише в описах продавців); AS150 — 75 А на 8 AWG, це максимум із каталогу Amass при перегріві < 85 K, хвилинного струму каталог не дає. Каталог старший за паспорти й для XT пише інші цифри (XT30 20 А, XT60 35 А, XT90 45 А — максимум при < 85 K); для XT курс бере паспорти. Роз'єм, перевантажений за струмом (номінал нижчий за реальний струм), гріється, нагрітий — окиснюється, окиснений — гріється ще фест.

### Перерізи
{{widget:wire-drop}}

Правило для коротких відрізків на борту: 12 AWG до ~60–80 А, 14 AWG до ~40–50 А, 16 AWG до ~25 А, 18 AWG до ~15 А, 20–22 AWG — сигнальні та 5-вольтові гілки до 2–3 А. Критерії — нагрів ізоляції й допустиме просідання; довгі проводи на крилі — на розмір більші.

## practice
### Крок 1. Дерево живлення
Намалюй дерево для своєї збірки зі струмами на кожній гілці (за таблицею та даташитами). Суму 5 В і суму 9–12 В — окремо.

### Крок 2. Вибір BEC і перерізів
Для кожної гілки: тип BEC (buck/LDO), номінал ≥ 1.5 × сума, вхідна напруга із запасом на повністю заряджений 6S (25.2 В). Переріз проводу — за таблицею.

Розрахункова лабораторна (без заліза): `power_lab.py` рахує живлення 7″ 6S: гілки BEC, переріз силового дроту й роз'єми, напругу конденсатора шини, LC-фільтр відео для чотирьох ESR, кидок струму й передзаряд, захист від переполюсовки. Скрипт і його реальний вивід:

```python
# power_lab.py — power distribution design for a 7" 6S quad: BEC sizing, wire drop,
# capacitor, LC filter for analog video, inrush and precharge.  python3 power_lab.py
import math

V_FULL, V_NOM, V_MIN = 25.2, 22.2, 18.0      # 6S: full, nominal, empty under load (3.0 V/cell)
# --- 1. BEC branches: (name, volts, amps typical, amps peak)
B5 = [("FC + gyro", 5, 0.2, 0.2), ("ELRS RX", 5, 0.15, 0.3), ("GPS + compass", 5, 0.1, 0.1),
      ("LED x4", 5, 0.24, 0.24)]
B12 = [("analog VTX 800 mW", 12, 0.6, 0.7), ("FPV camera", 12, 0.1, 0.15)]
for name, br, eta in (("5 V", B5, 0.88), ("12 V", B12, 0.90)):
    v = br[0][1]; i_typ = sum(b[2] for b in br); i_pk = sum(b[3] for b in br)
    rating = 1.5 * i_pk
    p_out = v * i_pk
    print(f"BEC {name}: typ {i_typ:.2f} A, peak {i_pk:.2f} A -> rating >= {rating:.2f} A; "
          f"buck input at {V_MIN} V: {p_out / (eta * V_MIN):.2f} A, at {V_FULL} V: {p_out / (eta * V_FULL):.2f} A")
    print(f"   LDO instead from {V_FULL} V: {(V_FULL - v) * i_pk:.1f} W of heat "
          f"(buck loss {p_out * (1 / eta - 1):.2f} W)")

# --- 2. Main lead: AWG -> resistance, drop and heat, 2 x 0.15 m, cruise 35 A, punch 80 A
def awg_ohm_per_m(n, t=20.0):
    d = 0.127e-3 * 92 ** ((36 - n) / 39)                  # ASTM B258 diameter, m
    return 1.724e-8 * (1 + 0.00393 * (t - 20)) / (math.pi * d * d / 4)
for n in (10, 12, 14, 16):
    r = awg_ohm_per_m(n) * 0.30
    print(f"{n} AWG: {awg_ohm_per_m(n) * 1e3:5.2f} mOhm/m; 0.30 m loop {r * 1e3:4.2f} mOhm; "
          f"35 A: {35 * r:.3f} V {35 * 35 * r:4.1f} W; 80 A: {80 * r:.3f} V "
          f"({80 * r / V_NOM * 100:.1f} % of {V_NOM} V) {80 * 80 * r:4.1f} W; at 80 C {awg_ohm_per_m(n, 80) / awg_ohm_per_m(n):.3f}x")
for r_c in (0.3e-3, 1.0e-3, 3.0e-3):                       # one connector pair: good, worn, burnt
    print(f"connector {r_c * 1e3:.1f} mOhm at 35 A: {35 * 35 * r_c:4.2f} W, at 80 A: {80 * 80 * r_c:5.2f} W")

# --- 3. Bus capacitor and spike U = L di/dt
L_wire = 1e-6 * 0.30                                      # ~1 uH per metre of lead (loop 0.30 m)
for di, dt in ((30, 10e-6), (30, 1e-6)):
    print(f"spike without cap: L={L_wire * 1e6:.2f} uH, {di} A in {dt * 1e6:g} us -> {L_wire * di / dt:.1f} V")
print(f"cap voltage: 1.3 x {V_FULL} = {1.3 * V_FULL:.1f} V minimum; 50 V gives {50 / V_FULL:.2f}x full charge")

# --- 4. LC filter for the 12 V video branch: L = 22 uH (DCR 0.05 Ohm), C = 470 uF
L, C, DCR = 22e-6, 470e-6, 0.05
f0 = 1 / (2 * math.pi * math.sqrt(L * C)); Z0 = math.sqrt(L / C)
def gain_db(f, esr):
    w = 2 * math.pi * f
    zc = esr + 1 / complex(0, w * C)                      # capacitor with its ESR
    return 20 * math.log10(abs(zc / (zc + DCR + complex(0, w * L))))
print(f"LC: f0 = {f0:.0f} Hz, Z0 = sqrt(L/C) = {Z0:.3f} Ohm, DC drop at 0.85 A {0.85 * DCR * 1e3:.0f} mV")
for esr in (0.01, 0.05, 0.15, 0.25):                     # polymer ... ordinary electrolytic
    pk = max(gain_db(f0 * k / 100, esr) for k in range(30, 300))
    print(f"   ESR {esr:.2f} Ohm: Q = {Z0 / (DCR + esr):.2f}, peak {pk:+.1f} dB, "
          f"24 kHz {gain_db(24e3, esr):6.1f} dB, 48 kHz {gain_db(48e3, esr):6.1f} dB")

# --- 5. Inrush at plug-in and precharge
C_bus = 1000e-6 + 4 * 10e-6                               # bulk cap + 4 x 10 uF ceramics on ESCs
R_loop = 0.012 + 0.0025 + 0.020                           # LiPo pack + lead + cap ESR, Ohm
E = 0.5 * C_bus * V_FULL ** 2
print(f"inrush: I_peak <= {V_FULL / R_loop:.0f} A (resistive limit), energy in cap {E:.2f} J, "
      f"same {E:.2f} J lost in the contacts and wires while charging")
for Rp in (5.0, 10.0):
    tau = Rp * C_bus
    print(f"precharge {Rp:g} Ohm: I_peak {V_FULL / Rp:.1f} A, tau {tau * 1e3:.1f} ms, 5tau {5 * tau * 1e3:.0f} ms, "
          f"P_peak {V_FULL ** 2 / Rp:.0f} W")
# --- 6. Reverse polarity on a 2 A branch
print(f"reverse protection 2 A: Schottky 0.4 V -> {0.4 * 2:.1f} W; P-MOSFET 10 mOhm -> {2 * 2 * 0.010:.2f} W")
```


```text
BEC 5 V: typ 0.69 A, peak 0.84 A -> rating >= 1.26 A; buck input at 18.0 V: 0.27 A, at 25.2 V: 0.19 A
   LDO instead from 25.2 V: 17.0 W of heat (buck loss 0.57 W)
BEC 12 V: typ 0.70 A, peak 0.85 A -> rating >= 1.27 A; buck input at 18.0 V: 0.63 A, at 25.2 V: 0.45 A
   LDO instead from 25.2 V: 11.2 W of heat (buck loss 1.13 W)
10 AWG:  3.28 mOhm/m; 0.30 m loop 0.98 mOhm; 35 A: 0.034 V  1.2 W; 80 A: 0.079 V (0.4 % of 22.2 V)  6.3 W; at 80 C 1.236x
12 AWG:  5.21 mOhm/m; 0.30 m loop 1.56 mOhm; 35 A: 0.055 V  1.9 W; 80 A: 0.125 V (0.6 % of 22.2 V) 10.0 W; at 80 C 1.236x
14 AWG:  8.28 mOhm/m; 0.30 m loop 2.49 mOhm; 35 A: 0.087 V  3.0 W; 80 A: 0.199 V (0.9 % of 22.2 V) 15.9 W; at 80 C 1.236x
16 AWG: 13.17 mOhm/m; 0.30 m loop 3.95 mOhm; 35 A: 0.138 V  4.8 W; 80 A: 0.316 V (1.4 % of 22.2 V) 25.3 W; at 80 C 1.236x
connector 0.3 mOhm at 35 A: 0.37 W, at 80 A:  1.92 W
connector 1.0 mOhm at 35 A: 1.23 W, at 80 A:  6.40 W
connector 3.0 mOhm at 35 A: 3.68 W, at 80 A: 19.20 W
spike without cap: L=0.30 uH, 30 A in 10 us -> 0.9 V
spike without cap: L=0.30 uH, 30 A in 1 us -> 9.0 V
cap voltage: 1.3 x 25.2 = 32.8 V minimum; 50 V gives 1.98x full charge
LC: f0 = 1565 Hz, Z0 = sqrt(L/C) = 0.216 Ohm, DC drop at 0.85 A 42 mV
   ESR 0.01 Ohm: Q = 3.61, peak +11.2 dB, 24 kHz  -45.6 dB, 48 kHz  -54.7 dB
   ESR 0.05 Ohm: Q = 2.16, peak +7.1 dB, 24 kHz  -36.1 dB, 48 kHz  -42.4 dB
   ESR 0.15 Ohm: Q = 1.08, peak +2.9 dB, 24 kHz  -26.8 dB, 48 kHz  -32.9 dB
   ESR 0.25 Ohm: Q = 0.72, peak +1.4 dB, 24 kHz  -22.4 dB, 48 kHz  -28.5 dB
inrush: I_peak <= 730 A (resistive limit), energy in cap 0.33 J, same 0.33 J lost in the contacts and wires while charging
precharge 5 Ohm: I_peak 5.0 A, tau 5.2 ms, 5tau 26 ms, P_peak 127 W
precharge 10 Ohm: I_peak 2.5 A, tau 10.4 ms, 5tau 52 ms, P_peak 64 W
reverse protection 2 A: Schottky 0.4 V -> 0.8 W; P-MOSFET 10 mOhm -> 0.04 W
```

### Крок 3. Конденсатор
Вибери ємність і напругу, припаяй на пади ESC/PDB виводами не довшими за 10–15 мм. Зніми лог зависання до/після: шум гіроскопа в смузі вище 300 Гц (спектр) мусить впасти.

### Крок 4. Захисти
Smoke stopper під час кожного першого ввімкнення після паяння. Перевір мультиметром, що нема КЗ між + і − до підключення АКБ (опір не має бути нижчий за сотні Ом; у конденсатора він спочатку росте).

### Крок 5. Виміряти (зв'язка з модулем вимірювань)
Просідання під навантаженням: напруга на АКБ без навантаження та під час зависання (з логу). Пульсації 5 В — осцилографом з AC-coupling: типово < 50–100 мВ p-p.

## diagnostics
- **Симптом:** FC перезавантажується при різкому газі
  - Можлива причина: просідання нижче порогу BEC або поганий контакт роз'єму.
  - Що зробити: лог VBAT, перевірити XT-роз'єм, конденсатор, ємніша/свіжіша АКБ.
- **Симптом:** смуги в аналоговому відео на газу
  - Можлива причина: пульсації силової шини лізуть у VTX.
  - Що зробити: конденсатор на силовій шині, живити VTX від фільтрованого BEC, LC-фільтр.
- **Симптом:** шум гіроскопа виріс після заміни ESC
  - Можлива причина: інша частота комутації, нема конденсатора.
  - Що зробити: конденсатор на пади, перевірити заземлення FC.
- **Симптом:** BEC гарячий
  - Можлива причина: лінійний BEC на високій вхідній напрузі або струм вищий за номінал.
  - Що зробити: перерахувати потужність розсіювання, buck замість LDO, розвантажити гілку.
- **Симптом:** приймач втрачає LQ, як увімкнеш відео
  - Можлива причина: імпульсний BEC або VTX коло антени приймача.
  - Що зробити: рознести, екран, живлення RX від окремого LDO.

## references
- Oscar Liang — Capacitors for noise filtering in mini quad | https://oscarliang.com/capacitors-mini-quad | secondary | B
- ArduPilot — Powering the Flight Controller | https://ardupilot.org/copter/docs/common-powering-the-pixhawk.html | primary | A
- INAV — Battery documentation | https://github.com/iNavFlight/inav/blob/master/docs/Battery.md | primary | A
- Amass — XT90H-M datasheet (UL1977 30 A; 60 A for 1 min; recommended 45/50/55 A on 12/10/8 AWG at 60 K rise) | https://atta.szlcsc.com/upload/public/pdf/source/20220706/D6369ADC773D7B5378E901BEE0D5B60C.pdf | primary | A
- Amass — XT60H-M datasheet V1.2 (30 A continuous, 60 A instantaneous, 12 AWG) | https://cdn.eicom.ru/media/PDF/XT60H-M.pdf | primary | A
- Amass — XT30UPB datasheet (UL1977 15 A; 30 A for 1 min; 15 A on 18 AWG, 20 A on 16 AWG at 60 K rise) | https://atta.szlcsc.com/upload/public/pdf/source/20230412/7B5DFEF57C9EA5273853390C734B3AC5.pdf | primary | A
- Amass — product catalogue (AS150: 75 A MAX, 8 AWG, rise < 85 K) | https://www.rcscomponents.kiev.ua/datasheets/Amas-cat1.pdf | primary | B
- Holybro — Connector & Wire Rating (XT60 12 AWG: 30 A for 4 h and 60 A for 1 min at < 60 K rise) | https://docs.holybro.com/power-module-and-pdb/power-module/connector-and-wire-rating | secondary | B

## checklist
- Дерево живлення намальоване зі струмами по гілках
- BEC вибрані за типом, струмом і вхідною напругою
- Перерізи проводів і роз'єми вибрані за струмом
- Конденсатор поставлено, ефект видно в спектрі
- Smoke stopper ставлю під час першого ввімкнення
