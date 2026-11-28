---
id: est-gnss
title: "GNSS: як працює GPS, похибки, RTK"
level: L2
readingTime: 35 хв
firmware: будь-яка прошивка
status: published
added: 2026-11-08
tags:
  - GNSS
  - GPS
  - HDOP
  - RTK
  - u-blox
related:
  - f-fc-sensors
  - el-emi
  - est-kalman
  - nav-resilience
next:
  - ap-ekf
source: content/estimation/est-gnss.md
source_hash: aaf21f538f56
---

## summary
GPS для автопілота — не «точка на карті», а шумне вимірювання з відомою (і змінною) похибкою. Модуль пояснює, як приймач отримує псевдодальності й розв'язує позицію, звідки беруться похибки (іоносфера, багатопроменевість, геометрія супутників — HDOP), що дають кілька сузір'їв (GPS, GLONASS, Galileo, BeiDou), як вибрати приймач і антену, які налаштування u-blox важливі для польоту (частота, сузір'я, динамічна модель, SBAS), і що таке RTK/PPK, коли вони потрібні, а коли — ні. Лабораторна: якість GPS у різних умовах за логом.

## theory
### Принцип
Кожен супутник передає час і орбіту; приймач вимірює затримку сигналу → **псевдодальність** (відстань + похибка годинника приймача). Чотири невідомі (x, y, z, Δt) → мінімум 4 супутники; більше — краще (надлишковість, оцінка якості). Сигнал на вході ~−130 дБм — слабший за шум, виділяється кореляцією з відомим кодом.

### Похибки та їхні величини (одночастотний приймач, добрі умови)
| Джерело | Похибка | Як зменшити |
|---|---|---|
| Іоносфера | 2–5 м | двочастотність (L1+L5/L2), SBAS-корекція |
| Тропосфера | 0.5–1 м | модель |
| Орбіта/годинник супутника | 1–2 м | SBAS |
| Багатопроменевість (відбиття від будівель, землі, рами) | 1–10+ м, стрибками | антена з ground plane, вище над рамою, далеко від будівель |
| Геометрія (DOP) | множник ×1–×5 | багато супутників по всьому небу |
| Шум приймача | 0.3–1 м | добра антена, немає завад |

Разом: 1.5–3 м (CEP) у полі, 5–20 м у місті. **Швидкість** за доплером набагато точніша — 0.05–0.2 м/с; EKF спирається на неї більше, ніж на позицію.

### DOP: геометрія
HDOP (горизонтальний) — множник похибки від розташування супутників: усі супутники в одному боці неба → погано. < 1 — відмінно, 1–2 — добре, вище порогу — ArduPilot не армить у GPS-режимах (`GPS_HDOP_GOOD`, зберігається як HDOP × 100; за замовчуванням 140 = 1.4). Кількість супутників — грубий показник: 6 — мінімум, 12+ — норма з кількома сузір'ями.

### Сузір'я
GPS (США, L1 C/A), GLONASS (Росія), Galileo (ЄС, L1 + E5), BeiDou (Китай). Багатосузірний приймач (u-blox M8/M9/M10, F9P) бачить 20–30 супутників замість 8–10: кращий DOP, швидший fix, стійкіший в умовах часткового закриття неба. Ціна — обчислювальне навантаження й частота оновлення: M8 — 10 Гц з 2–3 сузір'ями, M9/M10 — до 25 Гц, F9P — 20 Гц RTK.

### Антена
Керамічний патч 25×25 мм на ground plane — стандарт; спіральні (helix) — колова поляризація, краще проти багатопроменевості, не потрібна земля. Правило: антена зверху, на щоглі, нічого металевого поруч, ground plane ≥ 40 мм для патча. Активна антена (з підсилювачем) — для довгого кабелю.

### Налаштування u-blox, які мають значення
- **Частота**: 5–10 Гц для коптера (ArduPilot `GPS_RATE_MS = 200`, у 4.6+ `GPS1_RATE_MS` → 5 Гц; більше не потрібно EKF і перевантажує UART/CPU).
- **Динамічна модель**: Airborne < 1g/2g/4g — фільтр усередині приймача під динаміку; Pedestrian/Automotive для дрона погані (згладжують і запізнюються). ArduPilot ставить `GPS_NAVFILTER`.
- **Сузір'я** (`GPS_GNSS_MODE`): GPS + Galileo + GLONASS або GPS + Galileo + BeiDou — не всі чотири одразу на M8 (частота падає).
- **SBAS** (`GPS_SBAS_MODE`): корекції WAAS/EGNOS — трохи точніше, але в деяких регіонах заважає; вмикати там, де є покриття.
- **Повідомлення**: UBX (бінарний) замість NMEA — компактніший, точніший, зі статусом якості; ArduPilot сам налаштовує приймач u-blox при `GPS_AUTO_CONFIG = 1`.

### RTK і PPK
**RTK** (Real-Time Kinematic): базова станція з відомою позицією передає поправки фази несної (RTCM) ровер-приймачу по радіо/4G; точність 1–3 см при fix (статус RTK Fixed), 10–50 см при float. На практиці потрібен двочастотний приймач (F9P, UM982) на обох кінцях (одночастотний L1 RTK, наприклад NEO-M8P, працює лише на коротких базах і довше фіксується), база в радіусі ~10–20 км, безперервний зв'язок. **PPK** — те саме, але постобробка за логами: потрібна для фотограмметрії, не для керування польотом.

Коли потрібен RTK: точна посадка, геодезія, moving baseline для курсу (два GPS → yaw без компаса: ArduPilot «GPS for yaw», база `GPS_TYPE = 17`, ровер `GPS_TYPE2 = 18`; у 4.6+ — `GPS1_TYPE`/`GPS2_TYPE`). Коли не потрібен: звичайний політ за точками (EKF і 2 м похибки достатньо), FPV. RTK не лікує багатопроменевість і втрату супутників під дахом.

{{diagram:chart-gnss-hdop-wall|Стена в 180° убирает 4 спутника из 10, а HDOP растёт с 0.82 до 3.48 — выше порога ArduPilot 1.4 и порога EKF3 2.5; число спутников падает медленно, геометрия — резко.}}

{{diagram:gnss-rtk-choice-tree|RTK нужен, только когда задаче нужны сантиметры в полёте; для полёта по точкам хватает 1.5–3 м обычного GNSS, для фотограмметрии — PPK.}}

### Як GPS входить в EKF
EKF отримує позицію, швидкість, їхні оцінки точності (`GPA.HAcc/VAcc/SAcc`) і затримку (`GPS1_DELAY_MS` ~ 100–200 мс — вимірювання «старе», EKF це враховує). Якість перевіряється (`EK3_GPS_CHECK`: HDOP, кількість супутників, дрейф швидкості на землі) до дозволу арму в режимах із GPS. Glitch-захист — ворота інновацій (модуль про Калмана).

{{diagram:rtk-chain|Звичайне рішення GNSS дає метри; поправки RTCM від бази на відомій точці дають RTK fix із сантиметровою точністю.}}

## practice
### Крок 1. Три умови
Лог на землі по 5 хвилин (`LOG_DISARMED = 1`): відкрите поле; біля стіни будинку; під деревами. З `GPS`: `NSats`, `HDop`, `Status`; з `GPA`: `HAcc`, `SAcc`. Таблиця: середнє й найгірше для кожної умови.

### Крок 2. Багатопроменевість
У другій умові побудувати позицію (`GPS.Lat/Lng` → метри) за 5 хвилин на місці: розкид і стрибки. Порівняти з полем. Зіставити стрибки з `XKF4.SP` у логу (нормована інновація позиції, √test ratio), якщо EKF працював.

### Крок 3. Налаштування
Перевірити `GPS_RATE_MS`, `GPS_GNSS_MODE`, `GPS_NAVFILTER` (або аналоги в INAV/Betaflight: `gps_ublox_use_galileo`, динамічна модель), `GPS_AUTO_CONFIG`. Записати в паспорт збірки.

### Крок 4. Оцінка потреби в RTK
Для своєї задачі — чи потрібен RTK? Обґрунтувати вимогами до точності (інженерна тека).

### Скрипт: розкид позиції на місці
```python
import math, sys
from pymavlink import DFReader

log = DFReader.DFReader_binary(sys.argv[1])
pts, worst_hdop, min_sats = [], 0.0, 99
while (m := log.recv_match(type="GPS")) is not None:
    if m.Status < 3:                      # no 3D fix yet
        continue
    pts.append((m.Lat, m.Lng))
    worst_hdop, min_sats = max(worst_hdop, m.HDop), min(min_sats, m.NSats)
lat0, lon0 = pts[0]
xy = [((la - lat0) * 111_320, (lo - lon0) * 111_320 * math.cos(math.radians(lat0))) for la, lo in pts]
cx, cy = sum(p[0] for p in xy) / len(xy), sum(p[1] for p in xy) / len(xy)
r = sorted(math.hypot(x - cx, y - cy) for x, y in xy)
print(f"{len(r)} fixes, median {r[len(r) // 2]:.2f} m, p95 {r[int(len(r) * 0.95)]:.2f} m, max {r[-1]:.2f} m, "
      f"worst HDOP {worst_hdop:.2f}, min sats {min_sats}")
```

### Що має вийти і що записати
- **Відкрите поле:** багато супутників (з кількома сузір'ями — 20 і більше), HDOP близько 1 і нижче, розкид на місці — метр–два. Це еталон, з яким порівнюються інші умови.
- **Біля стіни:** супутників менше, HDOP вищий, а головне — стрибки позиції на метри через відбитий сигнал (багатопроменевість). Розкид p95 і max зростуть у рази, хоча кількість супутників може залишитися пристойною. Саме тому «супутників багато» — не гарантія.
- **Під деревами:** сигнал ослаблений, фіксація втрачається частіше (`Status` падає), `HAcc` у `GPA` зростає.
- **Налаштування:** запиши фактичні значення параметрів GNSS своєї версії ArduPilot (у 4.6+ частина параметрів приймача — з префіксом `GPS1_`, наприклад `GPS1_TYPE`; звіряйся зі списком параметрів).

Лабораторну зараховано, коли HDOP, кількість супутників і розкид позиції записано для трьох умов, багатопроменевість показано стрибками позиції на логу біля стіни, налаштування приймача перевірено й записано в паспорт, а рішення щодо RTK обґрунтовано вимогами до точності.

```python
"""est-gnss lab: pseudorange least squares, DOP from geometry, open sky vs a wall.
Local ENU frame, satellites at 22 000 km slant range; UERE sigma 3 m; receiver clock bias 1 ms."""
import math
import numpy as np

C = 299_792_458.0
SKY = [(0, 75), (40, 30), (85, 50), (130, 20), (175, 60), (220, 35), (260, 15), (300, 45), (335, 25), (20, 10)]
#        azimuth, elevation in degrees: 10 satellites spread over the whole sky


def unit(az, el):
    a, e = math.radians(az), math.radians(el)
    return np.array([math.cos(e) * math.sin(a), math.cos(e) * math.cos(a), math.sin(e)])   # E, N, U


def dop(sats):
    G = np.array([np.append(-unit(az, el), 1.0) for az, el in sats])
    Q = np.linalg.inv(G.T @ G)
    return math.sqrt(Q[0, 0] + Q[1, 1]), math.sqrt(Q[2, 2]), math.sqrt(np.trace(Q[:3, :3])), math.sqrt(np.trace(Q))


def solve(sats, rng, sigma=3.0, bias_s=1e-3, iters=6):
    truth = np.zeros(3)
    pos = np.array([unit(az, el) * 22_000e3 for az, el in sats])
    rho = np.linalg.norm(pos - truth, axis=1) + C * bias_s + rng.normal(0, sigma, len(sats))
    x = np.array([100e3, -100e3, 0.0, 0.0])            # E, N, U, c*dt; start 141 km off, zero clock
    for k in range(iters):
        r = np.linalg.norm(pos - x[:3], axis=1)
        H = np.hstack([-(pos - x[:3]) / r[:, None], np.ones((len(sats), 1))])
        dx = np.linalg.lstsq(H, rho - (r + x[3]), rcond=None)[0]
        x += dx
        if np.linalg.norm(dx) < 1e-3:
            break
    return x, k + 1


rng = np.random.default_rng(42)
for name, sats in (("open sky, 10 sats", SKY),
                   ("wall to the south (az 90..270 blocked)", [s for s in SKY if not 90 <= s[0] <= 270]),
                   ("4 sats, all low in the north", [(300, 15), (335, 25), (20, 10), (40, 30)])):
    h, v, p, g = dop(sats)
    x, n = solve(sats, rng)
    print(f"{name}: {len(sats)} sats, HDOP {h:.2f} VDOP {v:.2f} PDOP {p:.2f}")
    print(f"   one fix: E {x[0]:+6.2f} N {x[1]:+6.2f} U {x[2]:+6.2f} m, clock {x[3] / C * 1e3:.6f} ms, {n} iterations")
    errs = np.array([solve(sats, rng)[0][:3] for _ in range(2000)])
    sh = math.sqrt(np.mean(errs[:, 0] ** 2 + errs[:, 1] ** 2))
    print(f"   2000 fixes: horizontal RMS {sh:.2f} m  vs  HDOP*UERE = {h * 3.0:.2f} m")
```

```text
open sky, 10 sats: 10 sats, HDOP 0.82 VDOP 1.29 PDOP 1.53
   one fix: E  -0.93 N  +0.10 U  +1.29 m, clock 0.999999 ms, 4 iterations
   2000 fixes: horizontal RMS 2.52 m  vs  HDOP*UERE = 2.47 m
wall to the south (az 90..270 blocked): 6 sats, HDOP 3.48 VDOP 4.07 PDOP 5.36
   one fix: E  +7.62 N +11.36 U +11.70 m, clock 1.000050 ms, 4 iterations
   2000 fixes: horizontal RMS 10.40 m  vs  HDOP*UERE = 10.45 m
4 sats, all low in the north: 4 sats, HDOP 3.98 VDOP 4.30 PDOP 5.86
   one fix: E  -4.13 N +22.34 U +10.57 m, clock 1.000067 ms, 4 iterations
   2000 fixes: horizontal RMS 12.03 m  vs  HDOP*UERE = 11.94 m
```

```text
[ 40.0s] Arm: AHRS: waiting for home
[ 40.4s] PreArm: AHRS: waiting for home
GPS_RAW_INT: fix 6, sats 5, HDOP 1.21, h_acc 0.30 m
NOT armed after 60 s
```

## diagnostics
- **Симптом:** довгий пошук супутників після ввімкнення
  - Можлива причина: холодний старт, антена під карбоном, завади від USB/камери.
  - Що зробити: щогла, ground plane, модуль про EMI; дати 1–2 хвилини.
- **Симптом:** HDOP > 2 при 15 супутниках
  - Можлива причина: супутники з одного боку (стіна, дах).
  - Що зробити: відкрите небо; не армити в GPS-режимах.
- **Симптом:** позиція стрибає на 10–30 м у місті
  - Можлива причина: багатопроменевість.
  - Що зробити: вище над рамою, helix-антена, не довіряти Loiter біля будівель.
- **Симптом:** «GPS glitch» у повідомленнях ArduPilot
  - Можлива причина: стрибок позиції/швидкості за ворота EKF.
  - Що зробити: лог `GPS`/`XKF4`, джерело завади, при повторенні — налаштування failsafe.
- **Симптом:** RTK не виходить у Fixed
  - Можлива причина: далеко від бази, поганий зв'язок RTCM, одночастотний приймач.
  - Що зробити: перевірити потік RTCM, відстань, антени обох кінців.

## references
- ArduPilot — GPS/Compass (landing page) | https://ardupilot.org/copter/docs/common-positioning-landing-page.html | primary | A
- ArduPilot — GPS for Yaw (moving baseline) | https://ardupilot.org/copter/docs/common-gps-for-yaw.html | primary | A
- u-blox — ZED-F9P Product Summary (RTK, update rates) | https://incremental-content.u-blox.com/sites/default/files/ZED-F9P_ProductSummary_UBX-17005151.pdf | primary | A

## checklist
- Розумію псевдодальність, HDOP і чому швидкість точніша за позицію
- Знаю головні джерела похибок та їхні величини
- Антена на щоглі з ground plane, далеко від завад
- Налаштування частоти/сузір'їв/моделі перевірено
- Виміряв якість GPS у трьох умовах і бачив багатопроменевість у логу
