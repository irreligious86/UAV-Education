---
id: rf-link-budget
title: "Бюджет радіолінку і дальність"
level: L2
readingTime: 30 хв
firmware: будь-яка прошивка
status: published
added: 2026-11-08
tags:
  - бюджет лінку
  - дальність
  - RSSI
  - дБ
related:
  - rf-antennas
  - link-elrs
  - link-vtx
next:
  - el-wiring
source: content/electronics/rf-link-budget.md
source_hash: af1b0ba8b7a6
---

## summary
«Чи долетить на 10 км?» — питання арифметики, а не віри. Бюджет лінку — це сума в децибелах: потужність передавача + підсилення антен − втрати в кабелях − загасання в просторі має бути вищою за чутливість приймача із запасом на завмирання. Модуль вчить рахувати це для RC і відео, переводити запас в очікувану дальність, виставляти поріг попередження RSSI і порівнювати розрахунок із польовим тестом — і показує, чому 900 МГц летить далі за 2.4 ГГц за тієї самої потужності, а відео 5.8 ГГц — слабка ланка.

## theory
### Децибели за п'ять хвилин
дБ — логарифмічна міра відношення: 3 дБ ≈ ×2 за потужністю, 10 дБ = ×10, 20 дБ = ×100. дБм — потужність відносно 1 мВт: 0 дБм = 1 мВт, 20 дБм = 100 мВт, 27 дБм = 500 мВт, 30 дБм = 1 Вт. **Подвоєння потужності передавача дає +3 дБ — те саме, що трохи краща антена.** Подвоєння дальності коштує 6 дБ (див. нижче).

### Загасання у вільному просторі (FSPL)
FSPL(дБ) = 20·log₁₀(d, км) + 20·log₁₀(f, МГц) + 32.44.

| Дальність | 915 МГц | 2.4 ГГц | 5.8 ГГц |
|---|---|---|---|
| 1 км | 91.7 | 100.0 | 107.7 |
| 5 км | 105.6 | 114.0 | 121.7 |
| 10 км | 111.7 | 120.0 | 127.7 |
| 30 км | 121.2 | 129.6 | 137.3 |

Кожне подвоєння дальності — +6 дБ; перехід 915 МГц → 2.4 ГГц коштує 8.4 дБ на тій самій дальності, → 5.8 ГГц ще 7.7 дБ. Це фізика апертури приймальної антени, а не «проникна здатність».

### Рівняння бюджету
**Pпр = Pпд + Gпд + Gпр − Lкаб − FSPL − Lдод**, запас M = Pпр − Sчутл.

- Pпд — потужність передавача в дБм.
- G — підсилення антен у dBi (диполь 2, патч 8, Yagi 12).
- Lкаб — пігтейли/кабелі (0.5–2 дБ).
- Lдод — поляризація (3 дБ лінійна↔колова), розузгодження, перешкоди, зона Френеля біля землі (низький політ біля поверхні — ще 6–20 дБ).
- S — чутливість приймача в дБм для цього режиму (в ELRS — з таблиці режимів: 2.4 ГГц 50 Гц −115, 150 Гц −112, 250 Гц −108, 500 Гц −105; 900 МГц 25 Гц −123, 50 Гц −120, 100 Гц −117, 200 Гц −112).

Запас M: 10–15 дБ — мінімум для надійного лінку із завмираннями (багатопроменевість, повороти апарата); 20 дБ — комфортно; 0 — межа, зв'язок рватиметься.

### Приклад RC: ELRS 2.4 ГГц, 250 Гц, 250 мВт
Pпд = 24 дБм, Gпд = 2 (диполь пульта), Gпр = 2 (диполь борту, але рахуємо 0 через орієнтацію), Lкаб = 1, поляризація ще −3 на кренах.
Pпр на 10 км = 24 + 2 + 0 − 1 − 120 − 3 = −98 дБм. S(250 Гц) = −108 → запас 10 дБ. Перемикання на 50 Гц (−115) дасть 17 дБ — або ту саму надійність на ~22 км. Підняти потужність до 1 Вт (+6 дБ) — те саме, що подвоїти дальність.

### Приклад відео: аналог 5.8 ГГц 800 мВт
Pпд = 29 дБм, конюшина на борту 2, патч на землі 8, кабелі −1.5, S типового аналогового приймача ≈ −90 дБм (відео починає шуміти задовго до втрати). На 5 км: 29 + 2 + 8 − 1.5 − 121.7 = −84 дБм → запас 6 дБ, картинка буде із завадами. Цифрові системи працюють до −100…−105 дБм, але різко рвуться біля порогу. Відео майже завжди обмежує дальність раніше за RC — звідси відео 900 МГц/1.2–1.3 ГГц для далеких польотів і спрямовані антени на землі.

### Як перетворити бюджет на поріг RSSI
Правило ELRS: попередження, коли RSSI на ~8–10 дБ вище за чутливість режиму; критичний failsafe-поріг — біля чутливості. Для 2.4 ГГц 250 Гц: попередження −98…−100 дБм, при −105 — розвертатися. В EdgeTX — голосове попередження за RSSI dBm і за LQ (<70% на 250 Гц — привід тривожитися).

### Чому розрахунок не збігається з полем
Багатопроменевість (відбиття від землі складаються в протифазі), перешкоди в зоні Френеля (радіус першої зони на 2.4 ГГц на 5 км — ~12 м: летіти низько біля землі — втрачати 6–20 дБ), завади на борту (знижують ефективну чутливість), реальна орієнтація антен. Тому тест дальності — обов'язковий, а запас 10–15 дБ — мінімум.

{{diagram:chart-link-two-ray|Пример модуля на 2.4 ГГц: при полёте на 10 м отражение от земли съедает 10 дБ на 5 км, и предупреждение −98 дБм наступает на 3.9 км вместо 10 км; на 120 м излом уходит за 5.9 км, остаются только короткие провалы.}}

{{diagram:link-budget-chain|Розібраний приклад бюджету: ELRS 2.4 ГГц, 250 мВт, 10 км — прийнята потужність −98 дБм проти чутливості −108 дБм дає запас 10 дБ.}}

{{diagram:chart-link-margin|Прийнята потужність за формулою вільного простору проти порогів чутливості ELRS (таблиця модуля link-elrs). Запас — відстань від кривої до порогу; для реального польоту потрібно 10–15 дБ на завмирання, повороти антен і корпус апарата.}}

{{widget:link-margin}}

## practice
### Крок 1. Таблиця бюджету RC
Для свого лінку: потужність, режим і його чутливість, антени, кабелі. Порахувати запас на 1, 3, 5, 10 км. Знайти дальність, де запас = 12 дБ, — це твоя робоча межа.

### Крок 2. Таблиця бюджету відео
Те саме для відеосистеми з реальною чутливістю приймача/окулярів. Порівняти межі: що відмовляє першим.

### Крок 2a. Скрипт бюджету (код і вивід як у вихідному модулі)

```python
#!/usr/bin/env python3
"""Link budget lab for module rf-link-budget (stdlib only).

Inputs = the module's worked example: ExpressLRS 2.4 GHz, 250 Hz (sensitivity -108 dBm,
ELRS 4.1 src/src/common.cpp:100), 250 mW, dipole on the radio, 0 dBi effective on board,
1 dB cables, 3 dB polarisation loss. Run: python3 link_lab.py
"""
import math

C = 299_792_458.0
F_MHZ = 2440.0             # middle of the 2.4 GHz ISM band
LAM = C / (F_MHZ * 1e6)    # wavelength, m


def dbm(mw):               # mW -> dBm
    return 10 * math.log10(mw)


def fspl(d_km, f_mhz=F_MHZ):
    return 20 * math.log10(d_km) + 20 * math.log10(f_mhz) + 32.44


def two_ray_excess(d_m, ht, hr, gamma=-1.0):
    """Extra loss (dB) of direct + ground-reflected ray vs free space, flat ground, reflection gamma."""
    direct = math.hypot(d_m, hr - ht)
    refl = math.hypot(d_m, hr + ht)
    dphi = 2 * math.pi * (refl - direct) / LAM
    # field sum normalised to the direct ray (path-length amplitude difference included)
    re = 1 + gamma * (direct / refl) * math.cos(dphi)
    im = gamma * (direct / refl) * math.sin(-dphi)
    return -20 * math.log10(math.hypot(re, im))


def sens_from_noise(bw_hz, nf_db, snr_db):
    return -174 + 10 * math.log10(bw_hz) + nf_db + snr_db


P_TX = dbm(250)
G_TX, G_RX, L_CAB, L_POL = 2.0, 0.0, 1.0, 3.0
S = -108.0
EIRP = P_TX + G_TX - L_CAB

print(f"1) 250 mW = {P_TX:.1f} dBm; EIRP = {EIRP:.1f} dBm; 100 mW = {dbm(100):.1f} dBm; 1 W = {dbm(1000):.1f} dBm")
print("2) Budget vs distance (free space):")
print("   d_km  FSPL_dB  Prx_dBm  margin_dB")
for d in (1, 2, 5, 10, 15):
    prx = P_TX + G_TX + G_RX - L_CAB - L_POL - fspl(d)
    print(f"   {d:4}  {fspl(d):7.1f}  {prx:7.1f}  {prx - S:9.1f}")
for m in (12, 0):
    budget = P_TX + G_TX + G_RX - L_CAB - L_POL - S - m
    d = 10 ** ((budget - 20 * math.log10(F_MHZ) - 32.44) / 20)
    print(f"   distance with margin {m:2} dB: {d:5.1f} km")

print("3) Sensitivity from noise: S = -174 + 10lg(BW) + NF + SNR_min, NF = 6 dB")
# SX127x LoRa demodulator SNR per SF: datasheet Rev.7 Table 13; ELRS 900 MHz uses BW 500 kHz
for sf, snr, elrs, name in ((6, -5.0, -112, "200 Hz"), (7, -7.5, -117, "100 Hz"),
                            (8, -10.0, -120, "50 Hz"), (9, -12.5, -123, "25 Hz")):
    s = sens_from_noise(500e3, 6, snr)
    print(f"   SF{sf} BW500k: formula {s:6.1f} dBm, ELRS 4.1 table {elrs} dBm ({name}), diff {elrs - s:+.1f} dB")

print("4) First Fresnel zone radius at mid-path, 2.44 GHz:")
for d in (1, 5, 10):
    r = math.sqrt(LAM * d * 1000 / 4)
    print(f"   {d:3} km: r1 = {r:5.1f} m, 60 % clearance = {0.6 * r:5.1f} m")

print("5) Radio horizon d = sqrt(2*k*R*h), k = 4/3, R = 6371 km:")
for h1, h2 in ((2, 30), (2, 120), (10, 120)):
    k_r = 4 / 3 * 6371e3
    d = (math.sqrt(2 * k_r * h1) + math.sqrt(2 * k_r * h2)) / 1000
    print(f"   ground {h1:3} m, aircraft {h2:3} m: {d:5.1f} km")

print("6) Two-ray ground reflection, ground antenna 1.5 m, gamma = -1:")
for hr in (10, 30, 120):
    dc = 4 * 1.5 * hr / LAM
    row = "  ".join(f"{d}km {two_ray_excess(d * 1000, 1.5, hr):+5.1f}" for d in (1, 2, 5, 10))
    print(f"   aircraft {hr:3} m: breakpoint {dc / 1000:5.2f} km | extra loss vs FSPL: {row}")

print("7) ELRS 4.1 dynamic power (src/src/dynpower.cpp:166-252):")
S_FLRC = -104.0   # F1000/F500/D500/D250 have no SNR thresholds -> RSSI branch (common.cpp:94-97)
print(f"   FLRC/DVDA (S {S_FLRC:.0f}): RSSI branch, raise below {S_FLRC + 15:.0f} dBm, "
      f"lower above {S_FLRC + 21:.0f} dBm with LQ_avg >= 95")
print(f"   LoRa 250 Hz (S {S:.0f}): SNR branch, SNR raise gated by RSSI <= {S + 21:.0f} dBm or LQ_avg <= 95; "
      f"course warning S+10 = {S + 10:.0f} dBm")
```

```text
1) 250 mW = 24.0 dBm; EIRP = 25.0 dBm; 100 mW = 20.0 dBm; 1 W = 30.0 dBm
2) Budget vs distance (free space):
   d_km  FSPL_dB  Prx_dBm  margin_dB
      1    100.2    -78.2       29.8
      2    106.2    -84.2       23.8
      5    114.2    -92.2       15.8
     10    120.2    -98.2        9.8
     15    123.7   -101.7        6.3
   distance with margin 12 dB:   7.8 km
   distance with margin  0 dB:  30.9 km
3) Sensitivity from noise: S = -174 + 10lg(BW) + NF + SNR_min, NF = 6 dB
   SF6 BW500k: formula -116.0 dBm, ELRS 4.1 table -112 dBm (200 Hz), diff +4.0 dB
   SF7 BW500k: formula -118.5 dBm, ELRS 4.1 table -117 dBm (100 Hz), diff +1.5 dB
   SF8 BW500k: formula -121.0 dBm, ELRS 4.1 table -120 dBm (50 Hz), diff +1.0 dB
   SF9 BW500k: formula -123.5 dBm, ELRS 4.1 table -123 dBm (25 Hz), diff +0.5 dB
4) First Fresnel zone radius at mid-path, 2.44 GHz:
     1 km: r1 =   5.5 m, 60 % clearance =   3.3 m
     5 km: r1 =  12.4 m, 60 % clearance =   7.4 m
    10 km: r1 =  17.5 m, 60 % clearance =  10.5 m
5) Radio horizon d = sqrt(2*k*R*h), k = 4/3, R = 6371 km:
   ground   2 m, aircraft  30 m:  28.4 km
   ground   2 m, aircraft 120 m:  51.0 km
   ground  10 m, aircraft 120 m:  58.2 km
6) Two-ray ground reflection, ground antenna 1.5 m, gamma = -1:
   aircraft  10 m: breakpoint  0.49 km | extra loss vs FSPL: 1km  -2.8  2km  +2.5  5km +10.3  10km +16.3
   aircraft  30 m: breakpoint  1.47 km | extra loss vs FSPL: 1km  -3.5  2km  -5.2  5km  +1.0  10km  +6.8
   aircraft 120 m: breakpoint  5.86 km | extra loss vs FSPL: 1km  +5.0  2km  -6.0  5km  -5.7  10km  -4.0
7) ELRS 4.1 dynamic power (src/src/dynpower.cpp:166-252):
   FLRC/DVDA (S -104): RSSI branch, raise below -89 dBm, lower above -83 dBm with LQ_avg >= 95
   LoRa 250 Hz (S -108): SNR branch, SNR raise gated by RSSI <= -87 dBm or LQ_avg <= 95; course warning S+10 = -98 dBm
```

### Крок 3. Пороги
Виставити в пульті попередження RSSI dBm = S + 10 і LQ; записати в паспорт апарата. Failsafe у прошивці перевірено.

### Крок 4. Польовий тест
Політ по прямій із записом RSSI/LQ у лог пульта або FC на 500 м, 1, 2 км (у дозволених межах і зоні). Порівняти виміряний RSSI з розрахунковою Pпр для тих самих дистанцій: різниця — твоя «поправка на реальність», зазвичай 5–10 дБ.

### Розібраний приклад і що записати
Приклад модуля: ELRS 2.4 ГГц, 250 мВт (24 дБм), антени 2 і 0 дБі, втрати 4 дБ (кабелі й поляризація), чутливість режиму 150 Гц −112 дБм. Втрати вільного простору на 1 км при 2440 МГц: 20·log10(1) + 20·log10(2440) + 32.44 ≈ 100.2 дБ. Прийнята потужність 24 + 2 + 0 − 4 − 100.2 ≈ −78 дБм, запас ≈ 34 дБ. Кожне подвоєння дистанції знімає 6 дБ: запас 12 дБ залишиться на ≈ 12–13 км — це теоретична межа у вільному просторі. Той самий розрахунок є у віджеті бюджету лінку вище.
- **Таблиця RC і відео:** дистанція, FSPL, прийнята потужність, запас. Познач дистанцію, де запас падає до 12 дБ. Зазвичай першим здається відео, а не RC — перевір, чи так у тебе.
- **Пороги в пульті.** Попередження за RSSI = чутливість + 10 дБ (тут −102 дБм) і за LQ. Запиши значення в паспорт апарата.
- **Польовий тест.** Виміряний RSSI на 500 м, 1 і 2 км зазвичай на 5–10 дБ гірший за розрахунок: земля, зона Френеля, корпус, орієнтація антен. Ця різниця — твоя поправка, віднімай її від розрахункової дальності для цього апарата.

Лабораторну зараховано, коли бюджет пораховано для RC і відео з дистанцією запасу 12 дБ, польовий тест дав таблицю «розрахунок проти вимірювання» з поправкою, а поріг попередження RSSI виставлено в пульті й записано в паспорт.

## diagnostics
- **Симптом:** RSSI падає швидше за розрахунок від самого початку
  - Можлива причина: втрати в кабелі/роз'ємі, поляризація, антена під карбоном.
  - Що зробити: перевірити КСХ, пігтейли, орієнтацію.
- **Симптом:** зв'язок рветься на одній і тій самій дальності при хорошому RSSI
  - Можлива причина: завади на борту знижують ефективну чутливість; LQ падає раніше.
  - Що зробити: дивитися LQ, модуль про завади.
- **Симптом:** у полі запас на 10 дБ гірший за розрахунок
  - Можлива причина: низький політ — перешкоди в зоні Френеля, багатопроменевість.
  - Що зробити: вища висота, антена на землі вище, спрямована антена.
- **Симптом:** відео зникло, RC тримається
  - Можлива причина: бюджет відео вичерпано раніше (очікувано на 5.8 ГГц).
  - Що зробити: патч на землі, потужність, інший діапазон; RTH при втраті відео.

## references
- ExpressLRS — Signal Health (sensitivity per mode, RSSI/LQ) | https://www.expresslrs.org/info/signal-health/ | primary | A
- ExpressLRS — Long Range Competition / range considerations | https://www.expresslrs.org/info/long-range/ | primary | A
- Free-space path loss — Wikipedia (formula and derivation) | https://en.wikipedia.org/wiki/Free-space_path_loss | secondary | B

## checklist
- Вмію переводити мВт у дБм і рахувати FSPL
- Бюджет RC і відео пораховано із запасом за дальністю
- Поріг попередження RSSI виставлено за чутливістю режиму
- Польовий тест зіставлено з розрахунком, поправку записано
- Знаю, що відео зазвичай обмежує дальність раніше за RC
