---
id: des-thrust-stand
title: "Тяговый стенд: тензодатчик + HX711, ток, обороты, КПД"
level: L2
readingTime: 40 мин
firmware: ESP32 (Arduino core 2.x / 3.x), без автопилота
status: published
tags:
  - тяговый стенд
  - тензодатчик
  - HX711
  - силовая установка
  - измерения
related:
  - f-aero-props
  - f-motors-esc
  - el-measure
  - comp-esp32
  - f-safety
next:
  - aero-stability
---

## summary
Таблица тяги производителя снята на его ESC, его пропе и при его температуре; твоя связка может отличаться на 5–15 %, и узнать это можно только на стенде. Модуль учит собрать стенд на ESP32 (тензодатчик + HX711, INA226 для тока и напряжения, оптодатчик для оборотов), откалибровать его (масштаб, тара, дрейф, ползучесть), посчитать неопределённость, кривую г/Вт, C_T и коэффициент качества FM. Основной путь — обработка реалистичного набора данных по таблице T-Motor MN4006 KV380 + 15×5; в разделе про железо — сборка и калибровка настоящего стенда.

## theory
### Что меряет стенд и зачем
Минимум — четыре величины с одной меткой времени: тяга T, напряжение U, ток I, обороты n. Из них: P = U·I, удельная тяга T/P (г/Вт) и C_T. Датчик реактивного момента Q добавляет мощность на валу P_вал = 2π·n·Q, а с ней КПД привода и FM пропа.

{{diagram:stand-signal-chain|Стенд — это четыре канала с одной меткой времени. Безопасность (лимит тока, таймаут команды) живёт в ESP32 и не зависит ни от HX711, ни от ПК.}}

### Тензодатчик и HX711
Балочный тензодатчик — мост Уитстона из четырёх тензорезисторов. Выход пропорционален нагрузке и напряжению возбуждения: U_вых = S·U_exc·F/F_ном, где S — чувствительность в мВ/В. У типовой дешёвой балки (серия TAL220) S = 1.0 ± 0.15 мВ/В, нелинейность и гистерезис ±0.05 % FS, ползучесть ±0.1 % FS за 30 мин, температурный уход нуля ±0.2 % FS на 10 °C. Для балки на 5 кг это ±2.5 г нелинейности, ±5 г ползучести и ±10 г ухода нуля на 10 °C. Отсюда главное правило: тара до и после каждого прогона.

HX711 — 24-битный АЦП для моста. Канал A с усилением 128 даёт полную шкалу ±0.5·AVDD/128 (±20 мВ при 5 В). Скорость 10 или 80 отсчётов/с (вывод RATE), формат — дополнительный код, насыщение на 800000h / 7FFFFFh. Обычно мост питается от того же AVDD, поэтому измерение ратиометрическое и не зависит от точного напряжения: S·128·2²³ / 0.5 = 2 147 484 отсчёта на полную шкалу, то есть около 430 отсчётов/г для балки 5 кг. 24 импульса PD_SCK — данные, 25-й выбирает канал A×128. Ловушка в другом: если PD_SCK держится в высоком уровне дольше 60 мкс, чип уходит в power-down. Прерывание (Wi-Fi, другой ISR) посреди чтения портит отсчёт, поэтому чтение должно идти в критической секции.

### Калибровка: модель ошибок
Модель сырого отсчёта: raw = b + k·m + e_нелин + e_гист + e_полз(t) + e_дрейф(t) + шум.

- **Тара b** — среднее без нагрузки. Её дрейф (мотор и ESC греют балку) снимается нулём до и после прогона с линейной интерполяцией по времени.
- **Масштаб k** — МНК по 5–6 известным массам: k = Σ(m−m̄)(y−ȳ) / Σ(m−m̄)². Остатки после подгонки дают нелинейность.
- **Гистерезис** — разница показаний при той же массе на нагрузке и на разгрузке.
- **Ползучесть** — медленный рост показаний под постоянной нагрузкой: мала для ступени 10 с, заметна в прогоне на 30 мин.
- **Геометрия.** Калибруй силой вдоль оси пропа в точке приложения тяги: нить от оси мотора через блок на подшипнике к гирям или стенд, повёрнутый осью вверх. «Гиря на балку» в другом месте даёт ошибку плеча.

### Ток, напряжение, обороты
INA226 меряет падение на шунте (полная шкала ±81.92 мВ, LSB 2.5 мкВ) и напряжение шины (до 36 В, LSB 1.25 мВ). Регистр калибровки CAL = 0.00512 / (Current_LSB·R_шунт). С шунтом 2 мОм и Current_LSB = 1.25 мА выходит CAL = 2048 и полная шкала 40.96 А, а рассеивание шунта при 15 А — 0.45 Вт. Погрешность тока задаёт допуск шунта (обычно 1 %), а не АЦП. Напряжение меряй на входе ESC, а не на БП.

Обороты берут оптодатчиком (метка на колоколе, RPM = 60·10⁶ / (период_мкс · меток)) или из телеметрии ESC. Bidirectional DShot отдаёт eRPM, и механические обороты равны eRPM / (число полюсов / 2). У MN4006 24 полюса, значит делитель 12.

### Безразмерные величины
По определениям UIUC (Brandt & Selig): C_T = T / (ρ·n²·D⁴), C_P = P_вал / (ρ·n³·D⁵), n — об/с, D — м. Плотность воздуха ρ = p / (287.05·T_K), при 20 °C и 101.325 кПа это 1.204 кг/м³. Меряй её в день прогона: при 35 °C она на 5 % ниже, и тяга на тех же оборотах тоже.

Коэффициент качества (figure of merit) — доля идеальной мощности диска-актуатора в реальной мощности на валу:

**FM = P_ид / P_вал, P_ид = T^1.5 / √(2·ρ·A), A = π·D²/4.**

Через коэффициенты с n и D: FM = C_T^1.5 / (√(π/2)·C_P). Известную формулу C_T^1.5 / (√2·C_P) из вертолётных учебников можно брать только с вертолётными C_T и C_P, нормированными на Ω·R. Если подставить в неё пропеллерные коэффициенты, получишь FM на 11 % ниже правды. Без датчика момента у тебя есть только P_эл, и P_ид / P_эл = FM·η_привода — это системный КПД, а не качество пропа.

## practice
### Шаг 1. Набор данных
Основа — таблица T-Motor MN4006 KV380 с пропом 15×5 CF на 24 В: семь точек газа 50–100 %, ток, обороты, момент, тяга. Генератор строит по ней лог «стенда» с ошибками из теории: шум HX711, нелинейность, гистерезис 0.8 г, ползучесть 1.2 г, дрейф нуля +4 г, вибрации 0.8 % тяги, квантование INA226. Экземпляр мотора сделан «чуть хуже паспорта»: обороты на 1.5 % ниже (C_T тот же) и ток на 5 % выше (другой ESC). Задача обработки — это найти.

```python
#!/usr/bin/env python3
"""Synthetic thrust-stand log: T-Motor MN4006 KV380 + 15x5 CF @ 24 V (store.tmotor.com table)
plus realistic HX711 / INA226 / optical-tach errors. Reproducible: seed 42, stdlib only."""
import csv, math, random

R = random.Random(42)
# throttle %, current A, RPM, thrust g  -- manufacturer table, 15x5 CF, 24 V
TABLE = [(50, 3.1, 3746, 805), (55, 4.1, 4089, 959), (60, 4.8, 4358, 1093), (65, 5.8, 4634, 1236),
         (75, 8.3, 5215, 1561), (85, 10.7, 5627, 1823), (100, 15.0, 6177, 2228)]
K, OFS, FS = 431.7, 84213, 5000.0           # counts/g, zero unbalance (counts), cell capacity g
SPS = 10                                     # HX711 RATE=0

def raw(m_g, extra_g=0.0):                  # cell + HX711: nonlinearity <=0.03 %FS, noise 40 counts
    nl = 4 * 0.0003 * FS * (m_g / FS) * (1 - m_g / FS)
    return round(OFS + K * (m_g + nl + extra_g) + R.gauss(0, 40))

with open("calib.csv", "w", newline="") as f:          # 20 samples per weight, load up then down
    w = csv.writer(f); w.writerow(["dir", "ref_g", "raw"])
    for d, seq in (("up", [0, 100, 200, 500, 1000, 2000]), ("down", [1000, 500, 0])):
        for m in seq:
            for _ in range(20):
                w.writerow([d, m, raw(m, 0.8 if d == "down" and m else 0.0)])

with open("creep.csv", "w", newline="") as f:          # 1000 g left on for 600 s
    w = csv.writer(f); w.writerow(["t_s", "raw"])
    for i in range(600 * SPS):
        t = i / SPS
        w.writerow([t, raw(1000, 1.2 * (1 - math.exp(-t / 300)))])

# the specimen: 1.5 % lower RPM than the datasheet (C_T unchanged) and 5 % more current (other ESC)
with open("run.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["t_s", "thr", "raw", "volt", "amp", "rpm"])
    t, T_END = 0.0, 20 + len(TABLE) * 10 + 20
    def row(thr, thrust, amp, rpm):
        global t
        drift = 4.0 * t / T_END                              # zero drift +4 g (cell warms up)
        vib = R.gauss(0, 0.008 * thrust + 1.5) if thrust else 0.0
        a = amp + R.gauss(0, 0.015) if amp else R.gauss(0, 0.002)
        v = 24.0 - 0.02 * a + R.gauss(0, 0.005)
        r = rpm * (1 + R.gauss(0, 0.003)) if rpm else 0
        w.writerow([f"{t:.1f}", thr, raw(thrust, drift + vib), f"{round(v / 0.00125) * 0.00125:.5f}",
                    f"{round(a / 0.00125) * 0.00125:.5f}", round(r)])
        t += 1 / SPS
    for _ in range(20 * SPS): row(0, 0, 0, 0)                # pre-tare, motor stopped
    for thr, amp, rpm, thrust in TABLE:
        n = rpm * 0.985
        for _ in range(10 * SPS): row(thr, thrust * 0.985 ** 2, amp * 1.05, n)
    for _ in range(20 * SPS): row(0, 0, 0, 0)                # post-tare
print("calib.csv creep.csv run.csv written")
```

```text
$ python3 gen_stand_data.py
calib.csv creep.csv run.csv written
$ wc -l *.csv
   181 calib.csv
  6001 creep.csv
  1101 run.csv
```

### Шаг 2. Калибровка, ползучесть, дрейф
Один скрипт: блоки 1–3 — калибровка и точки, блок 4 — неопределённость (шаг 4).

```python
#!/usr/bin/env python3
"""Thrust-stand processing: calibration, creep, drift, g/W, C_T, uncertainty."""
import csv, math, statistics as st
from collections import defaultdict

rd = lambda fn: list(csv.DictReader(open(fn)))
RHO, D = 1.204, 15 * 0.0254                    # 20 C, 101.325 kPa; 15" prop
DS = {50: (805, 74), 55: (959, 98), 60: (1093, 115), 65: (1236, 139),   # datasheet: g, W
      75: (1561, 199), 85: (1823, 257), 100: (2228, 360)}

# 1. calibration: least squares raw = b + k*m on the loading branch
g = defaultdict(list)
for r in rd("calib.csv"): g[(r["dir"], int(r["ref_g"]))].append(int(r["raw"]))
up = sorted((m, st.mean(v)) for (d, m), v in g.items() if d == "up")
xm, ym = st.mean(m for m, _ in up), st.mean(y for _, y in up)
k = sum((m - xm) * (y - ym) for m, y in up) / sum((m - xm) ** 2 for m, _ in up)
b = ym - k * xm
res = [(y - b - k * m) / k for m, y in up]
hyst = max((st.mean(g[("down", m)]) - st.mean(g[("up", m)])) / k for m in (500, 1000))
noise = st.stdev(g[("up", 0)]) / k
print(f"k = {k:.2f} counts/g, offset = {b:.0f}, max residual = {max(map(abs, res)):.2f} g, "
      f"hysteresis = {hyst:.2f} g, noise = {noise:.2f} g")

# 2. creep: last 60 s vs first 30 s under 1000 g
c = [int(r["raw"]) for r in rd("creep.csv")]
creep = (st.mean(c[-600:]) - st.mean(c[:300])) / k
print(f"creep 1000 g / 10 min = {creep:+.2f} g")

# 3. run: zero before/after, linear drift correction, steady 2..10 s of each step
run = rd("run.csv")
zero = [r for r in run if r["thr"] == "0"]
pre = [r for r in zero if float(r["t_s"]) < 20]; post = [r for r in zero if float(r["t_s"]) >= 20]
z0, z1 = st.mean(int(r["raw"]) for r in pre), st.mean(int(r["raw"]) for r in post)
t0, t1 = st.mean(float(r["t_s"]) for r in pre), st.mean(float(r["t_s"]) for r in post)
print(f"zero drift over run = {(z1 - z0) / k:+.2f} g")
GW = sorted((t, t / p) for t, p in DS.values())      # datasheet g/W vs thrust
def gw_ds(T):                                       # linear interpolation, extrapolate at the ends
    (a, fa), (b, fb) = next(((p, q) for p, q in zip(GW, GW[1:]) if T <= q[0]), GW[-2:])
    return fa + (fb - fa) * (T - a) / (b - a)
steps = defaultdict(list)
for r in run:
    if r["thr"] != "0": steps[int(r["thr"])].append(r)
print("thr   T,g    I,A    P,W   g/W   rpm    C_T    T/T_ds  gW/gW_ds(same T)")
out = []
for thr, rows in sorted(steps.items()):
    rows = rows[20:]                                   # drop 2 s of spool-up
    tm = st.mean(float(r["t_s"]) for r in rows)
    zt = z0 + (z1 - z0) * (tm - t0) / (t1 - t0)
    T = (st.mean(int(r["raw"]) for r in rows) - zt) / k
    sT = st.stdev(int(r["raw"]) for r in rows) / k
    I = st.mean(float(r["amp"]) for r in rows); V = st.mean(float(r["volt"]) for r in rows)
    n = st.mean(float(r["rpm"]) for r in rows) / 60
    ct = T / 1000 * 9.80665 / (RHO * n ** 2 * D ** 4)
    Tds, Pds = DS[thr]
    out.append((thr, T, sT, len(rows), I, V))
    print(f"{thr:3d} {T:7.1f} {I:6.2f} {V*I:6.1f} {T/(V*I):5.2f} {n*60:5.0f} {ct:.4f} "
          f"{T/Tds:6.3f} {T/(V*I)/gw_ds(T):7.3f}")

# 4. uncertainty budget for the 50 % point (standard uncertainties, g)
thr, T, sT, N, I, V = out[0]
u = {"noise+vibration s/sqrt(N/5)": sT / math.sqrt(N / 5),
     "scale factor (weights 0.05 %)": T * 0.0005 / math.sqrt(3),
     "nonlinearity (max residual)": max(map(abs, res)) / math.sqrt(3),
     "drift correction (half)": abs(z1 - z0) / k / 2 / math.sqrt(3),
     "creep": abs(creep) / math.sqrt(3), "hysteresis": abs(hyst) / 2 / math.sqrt(3)}
for name, val in u.items(): print(f"  {name:31s} {val:5.2f} g")
uT = math.sqrt(sum(v * v for v in u.values()))
uI = 0.01 / math.sqrt(3)                               # shunt 1 % tolerance dominates
ugw = math.sqrt((uT / T) ** 2 + uI ** 2)
print(f"T = {T:.0f} g, U(k=2) = {2*uT:.1f} g ({200*uT/T:.2f} %); g/W = {T/(V*I):.2f} +/- {2*ugw*T/(V*I):.2f} (k=2)")
```

```text
$ python3 process_stand.py
k = 432.01 counts/g, offset = 84254, max residual = 0.15 g, hysteresis = 0.81 g, noise = 0.06 g
creep 1000 g / 10 min = +0.97 g
zero drift over run = +3.29 g
```

Разбор. k = 432.01 отсчёта/г совпадает с оценкой из теории (≈ 430). Остаток после подгонки 0.15 г: нелинейность на диапазоне 0–2 кг меньше шума вибраций. Гистерезис 0.81 г и ползучесть +0.97 г за 10 мин видны, но малы. Дрейф нуля +3.29 г за прогон — уже 0.4 % от тяги в первой точке. Без поправки по нулю «после» вся кривая уехала бы вверх.

### Шаг 3. Кривая г/Вт и C_T
```text
thr   T,g    I,A    P,W   g/W   rpm    C_T    T/T_ds  gW/gW_ds(same T)
 50   780.7   3.25   77.9 10.03  3689 0.0798  0.970   0.907
 55   931.6   4.30  102.9  9.05  4027 0.0799  0.971   0.907
 60  1058.3   5.04  120.4  8.79  4290 0.0800  0.968   0.918
 65  1198.2   6.09  145.4  8.24  4564 0.0800  0.969   0.910
 75  1515.7   8.72  207.6  7.30  5138 0.0799  0.971   0.914
 85  1768.6  11.23  267.1  6.62  5539 0.0802  0.970   0.913
100  2161.9  15.75  373.1  5.79  6085 0.0812  0.970   0.914
```

Сравнивать с паспортом надо при равной тяге, а не при равном «газе»: процент газа зависит от калибровки ESC. Последний столбец — г/Вт стенда к г/Вт таблицы на той же тяге. C_T = 0.080 постоянен по точкам и совпадает с паспортным (0.0798 на 50 %, 0.0813 на 100 % по таблице): проп и канал тяги в порядке, тяга ниже на 3 % только потому, что ниже обороты. При этом г/Вт стабильно на 8–9 % ниже паспорта, и это уже электрическая часть: ESC, провода, напряжение. Это не шум, потому что неопределённость г/Вт ±1.3 % (шаг 4).

{{diagram:chart-stand-gpw|Стенд даёт г/Вт на 8–9 % ниже таблицы T-Motor при той же тяге, а C_T совпадает: проп в норме, потери в приводе. Разница в 6–7 раз больше неопределённости ±1.3 %.}}

Применение. Квадрокоптеру 3.5 кг нужно 880 г на мотор. По паспорту это ток 3.1 + (880 − 805)/(959 − 805)·1.0 ≈ 3.6 А, то есть 86 Вт и 10.2 г/Вт. По стенду — около 9.4 г/Вт (интерполяция между 780.7 и 931.6 г), и время висения будет на 8 % меньше паспортного расчёта.

### Шаг 4. Бюджет неопределённости
```text
  noise+vibration s/sqrt(N/5)      2.08 g
  scale factor (weights 0.05 %)    0.23 g
  nonlinearity (max residual)      0.09 g
  drift correction (half)          0.95 g
  creep                            0.56 g
  hysteresis                       0.23 g
T = 781 g, U(k=2) = 4.7 g (0.61 %); g/W = 10.03 +/- 0.13 (k=2)
```

Систематические вклады — равномерные (делим на √3), итог — корень из суммы квадратов. Вибрационные отсчёты коррелированы, поэтому эффективное N впятеро меньше (80 → 16). Доминируют вибрация и дрейф: улучшать надо балансировку пропа и прогрев, а не разрядность АЦП. В г/Вт главный вклад — допуск шунта 1 %.

### Шаг 5. FM и КПД привода по паспортному моменту
Датчика момента на стенде нет, но в таблице T-Motor есть столбец момента. По нему можно разделить потери пропа и привода:

```python
import math
RHO, D = 1.204, 15 * 0.0254
A = math.pi * D ** 2 / 4
# datasheet 15x5 @ 24 V: throttle, thrust g, power W (electric), rpm, torque N*m
for thr, Tg, Pel, rpm, tau in [(50, 805, 74, 3746, 0.15), (75, 1561, 199, 5215, 0.29), (100, 2228, 360, 6177, 0.40)]:
    T, n = Tg / 1000 * 9.80665, rpm / 60
    Psh = tau * 2 * math.pi * n                      # shaft power
    Pid = T ** 1.5 / math.sqrt(2 * RHO * A)          # ideal induced power (actuator disk)
    CT, CP = T / (RHO * n**2 * D**4), Psh / (RHO * n**3 * D**5)
    print(f"{thr:3d}%  P_shaft={Psh:5.1f} W  eta_drive={Psh/Pel:.2f}  P_ideal={Pid:5.1f} W  "
          f"FM={Pid/Psh:.2f}  FM(CT,CP)={CT**1.5/(math.sqrt(math.pi/2)*CP):.2f}  "
          f"wrong CT^1.5/(sqrt2*CP)={CT**1.5/(math.sqrt(2)*CP):.2f}  FM*eta={Pid/Pel:.2f}")
```

```text
 50%  P_shaft= 58.8 W  eta_drive=0.80  P_ideal= 42.3 W  FM=0.72  FM(CT,CP)=0.72  wrong CT^1.5/(sqrt2*CP)=0.64  FM*eta=0.57
 75%  P_shaft=158.4 W  eta_drive=0.80  P_ideal=114.3 W  FM=0.72  FM(CT,CP)=0.72  wrong CT^1.5/(sqrt2*CP)=0.64  FM*eta=0.57
100%  P_shaft=258.7 W  eta_drive=0.72  P_ideal=194.9 W  FM=0.75  FM(CT,CP)=0.75  wrong CT^1.5/(sqrt2*CP)=0.67  FM*eta=0.54
```

Выходит, что FM пропа 0.72–0.75 (момент в таблице дан двумя значащими цифрами, отсюда ±3–4 %), а мотор с ESC отдают на вал 72–80 % электрической мощности. На полном газе КПД привода падает до 0.72: потери в меди растут как I². Строка `wrong` показывает, что даёт вертолётная формула с пропеллерными коэффициентами.

### Шаг 6. Прошивка стенда (ESP32, PlatformIO)
`platformio.ini`: `platform = espressif32`, `board = esp32dev`, `framework = arduino`, `monitor_speed = 115200`. HX711 читается вручную, без библиотеки, чтобы было видно критическую секцию. Безопасность работает на своём таймере каждые 100 мс: отвалился HX711 — газ всё равно сбросится.

```cpp
// Thrust stand: HX711 (thrust) + INA226 (V, I) + optical tach (RPM) + ESC PWM. CSV at 10 Hz.
#include <Arduino.h>
#include <Wire.h>

const int HX_DOUT = 16, HX_SCK = 17, ESC_PIN = 25, TACH_PIN = 27;
const float I_LIMIT = 16.0f;          // A: MN4006 KV380 peak 16 A (180 s); fuse 20 A in series
const uint32_t CMD_TIMEOUT_MS = 500;  // no command from the PC -> throttle 0
const int RAMP_PER_TICK = 2;          // % per 100 ms tick = 20 %/s
const uint8_t INA = 0x40;
const int TACH_PPR = 1;               // reflective marks per revolution

portMUX_TYPE hxMux = portMUX_INITIALIZER_UNLOCKED;
volatile uint32_t tachPeriodUs = 0, tachLastUs = 0;
bool armed = false; int thrCmd = 0, thrOut = 0; uint32_t lastCmdMs = 0;

int32_t hx711Read() {                 // call only when DOUT is low (data ready)
  uint32_t v = 0;
  portENTER_CRITICAL(&hxMux);         // PD_SCK high > 60 us = power-down: no interrupts here
  for (int i = 0; i < 25; i++) {      // 24 data bits + 25th pulse: channel A, gain 128
    digitalWrite(HX_SCK, HIGH); delayMicroseconds(1);
    if (i < 24) v = (v << 1) | digitalRead(HX_DOUT);
    digitalWrite(HX_SCK, LOW);  delayMicroseconds(1);
  }
  portEXIT_CRITICAL(&hxMux);
  if (v & 0x800000) v |= 0xFF000000;  // sign-extend 24-bit two's complement
  return (int32_t)v;
}

void inaWrite(uint8_t reg, uint16_t val) {
  Wire.beginTransmission(INA); Wire.write(reg); Wire.write(val >> 8); Wire.write(val & 0xFF);
  Wire.endTransmission();
}
int16_t inaRead(uint8_t reg) {
  Wire.beginTransmission(INA); Wire.write(reg); Wire.endTransmission(false);
  Wire.requestFrom(INA, (uint8_t)2);
  return (int16_t)((Wire.read() << 8) | Wire.read());
}

void IRAM_ATTR tachIsr() { uint32_t now = micros(); tachPeriodUs = now - tachLastUs; tachLastUs = now; }

void escWriteUs(int us) {             // 50 Hz, 16-bit: 1 us = 65536 / 20000 counts
  uint32_t duty = ((uint32_t)us * 65536UL + 10000UL) / 20000UL;
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(ESC_PIN, duty);
#else
  ledcWrite(0, duty);
#endif
}

void safetyTick(float amps) {         // runs every 100 ms
  if (millis() - lastCmdMs > CMD_TIMEOUT_MS) thrCmd = 0;
  if (armed && amps > I_LIMIT) { armed = false; Serial.println("#TRIP overcurrent"); }
  int target = armed ? thrCmd : 0;
  if (!armed) thrOut = 0;             // disarm cuts immediately, ramp only upwards
  else thrOut += constrain(target - thrOut, -100, RAMP_PER_TICK);
  escWriteUs(1000 + thrOut * 10);
}

void handleSerial() {                 // "arm", "disarm", "t55" (throttle %), sent >= 2 Hz by the PC
  if (!Serial.available()) return;
  String s = Serial.readStringUntil('\n'); s.trim();
  lastCmdMs = millis();
  if (s == "arm" && thrOut == 0) armed = true;
  else if (s == "disarm") armed = false;
  else if (s.startsWith("t")) thrCmd = constrain(s.substring(1).toInt(), 0, 100);
}

void setup() {
  Serial.begin(115200);
  pinMode(HX_SCK, OUTPUT); digitalWrite(HX_SCK, LOW); pinMode(HX_DOUT, INPUT);
  pinMode(TACH_PIN, INPUT_PULLUP); attachInterrupt(TACH_PIN, tachIsr, FALLING);
  Wire.begin();
  inaWrite(0x00, 0x4527);             // AVG 16, VBUSCT = VSHCT = 1.1 ms, continuous
  inaWrite(0x05, 2048);               // CAL = 0.00512 / (1.25 mA * 2 mOhm)
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttach(ESC_PIN, 50, 16);
#else
  ledcSetup(0, 50, 16); ledcAttachPin(ESC_PIN, 0);
#endif
  escWriteUs(1000);
  Serial.println("ms,thr,raw,volt,amp,rpm");
}

void loop() {
  handleSerial();
  static uint32_t tSafe = 0; static float volt = 0, amp = 0;
  if (millis() - tSafe >= 100) {      // safety runs on its own clock: a dead HX711 must not stop it
    tSafe += 100;
    volt = inaRead(0x02) * 0.00125f; amp = inaRead(0x04) * 0.00125f;
    safetyTick(amp);
  }
  if (digitalRead(HX_DOUT) == LOW) {  // HX711 RATE=0: a new sample every 100 ms
    int32_t raw = hx711Read();
    uint32_t per = tachPeriodUs;
    float rpm = (per && micros() - tachLastUs < 500000UL) ? 60e6f / (per * TACH_PPR) : 0;
    Serial.printf("%lu,%d,%ld,%.3f,%.3f,%.0f\n", millis(), thrOut, (long)raw, volt, amp, rpm);
  }
}
```

Без платы логику проверяют на ПК: тот же `main.cpp` собирается `g++ -std=c++17` с подменой Arduino API (stubs) и симуляторами HX711 и INA226; в тесте безопасности HX711 всё время «не готов». Вывод:

```text
HX711 decode:
  sent         0 -> read         0
  sent         1 -> read         1
  sent        -1 -> read        -1
  sent   8388607 -> read   8388607
  sent  -8388608 -> read  -8388608
  sent    421646 -> read    421646
Safety (HX711 not ready the whole time):
  t= 500 ms thrOut=10% ESC=1100 us
  t= 900 ms thrOut=18% ESC=1180 us
  t=1300 ms thrOut=26% ESC=1260 us
  t=1700 ms thrOut=34% ESC=1340 us
  700 ms without commands: thrOut=0% ESC=1000 us
  re-armed: thrOut=20%
  serial> #TRIP overcurrent
  17 A: armed=0 thrOut=0% ESC=1000 us
```

Знак расширяется верно на границах шкалы, рампа держит 20 %/с, тишина 500 мс и ток 17 А сбрасывают газ — при мёртвом HX711.

### Переход на реальное железо
Железо: ESP32 DevKit, балка 5 кг (запас 2.2× к 2228 г), HX711 с RATE = 0, INA226 с шунтом 2 мОм в минусе, оптодатчик, ESC с PWM-входом, предохранитель 20 А, БП 24 В с лимитом тока или 6S. Конец лопасти 15" на 6177 об/мин идёт со скоростью π·0.381·103 ≈ 123 м/с: обломок пропа — это пуля.

1. **Механика, пропа нет.** Стенд на двух струбцинах, поток от балки и от людей, до стен, пола и потолка ≥ 1–2 диаметра пропа (ближе рециркуляция меняет тягу). Вокруг диска — кольцо или сетка. Плоскость вращения — запретная зона, работаешь в очках.
2. **Электрика, пропа нет.** Первое включение через smoke stopper или БП с лимитом 2 А. Проверь, что INA226 показывает напряжение БП ±0.05 В по мультиметру, а ток растёт при газе, а не падает (полярность шунта). Проверь направление вращения и обороты на 20 % газа по оптодатчику и по тахометру.
3. **Калибровка, пропа нет.** Прогрей 15 мин. Нагружай гирями 0–100–200–500–1000–2000 г вдоль оси пропа (блок на подшипнике), потом разгружай. По 20 отсчётов на точку. Посчитай k, остатки и гистерезис скриптом шага 2. Оставь 1000 г на 10 мин — это ползучесть.
4. **Аварийные пути, пропа нет.** Выдерни USB — газ должен уйти в 0 за 0.5 с. Временно поставь `I_LIMIT` = 1 А — должен быть `#TRIP`. Вынь провод DOUT HX711 — безопасность должна работать дальше.
5. **Прогон, проп установлен (только здесь).** Затяни гайку, убедись в направлении. Пульт скрипта на ПК шлёт команду ≥ 2 Гц. Нуль 20 с, затем 7 ступеней по 10 с (50…100 %), снова нуль 20 с. Аварийный выключатель питания ESC держишь в руке. На 100 % экземпляр из примера берёт 15.75 А — почти лимит 16 А (паспортный пик — 16 А на 180 с), поэтому верхнюю ступень держи не дольше 10 с. Запиши температуру и давление и посчитай ρ.
6. **Обработка** — тем же скриптом. Сравнение с таблицей — при равной тяге.

Критерии железа: остаток калибровки ≤ 3 г, дрейф нуля ≤ 5 г и учтён, ≥ 5 точек газа, C_T постоянен в пределах ±5 %, расхождение г/Вт с паспортом при равной тяге объяснено с U (k = 2).

Лабораторная засчитывается, когда: (основной путь) генератор и обработка запущены и k, дрейф и таблица точек совпадают с приведёнными; бюджет неопределённости посчитан для одной точки; по C_T и г/Вт сделан вывод, где потери — в пропе или в приводе; FM посчитан из паспортного момента правильной формулой; (железо) выполнены пункты 1–6, аварийные пути проверены без пропа, выполнены критерии железа.

## diagnostics
- **Симптом:** редкие огромные скачки тяги (тысячи граммов) или значения около ±8388608
  - Возможная причина: прерывание (Wi-Fi, другой ISR) растянуло импульс PD_SCK дольше 60 мкс — HX711 ушёл в power-down или сдвинул биты.
  - Что сделать: чтение в `portENTER_CRITICAL`, Wi-Fi выключить на время прогона, отбрасывать отсчёты на границах шкалы.
  - Что видно в логе: одиночные выбросы на ровном сигнале.
- **Симптом:** при постоянной нагрузке показания медленно растут, ноль после прогона не совпадает с нулём до
  - Возможная причина: ползучесть балки и температурный уход нуля (±0.2 % FS на 10 °C — до ±10 г у балки 5 кг).
  - Что сделать: прогрев 15 мин, нуль до и после, линейная поправка по времени, короткие ступени.
- **Симптом:** тяга со знаком минус или растёт при снятии гири
  - Возможная причина: перепутаны A+ и A− или балка стоит вверх ногами; под мотором — перевёрнут проп или неверное вращение.
  - Что сделать: поменять провода сигнала или знак k, проверить проп и направление.
- **Симптом:** тяга на 10–20 % выше паспорта при нормальном токе
  - Возможная причина: калибровали в другой точке приложения силы (ошибка плеча), или блок с трением съел часть веса гирь; проп близко к полу или стене.
  - Что сделать: калибровать вдоль оси пропа, проверить гистерезис, отодвинуть стенд на 1–2 D.
- **Симптом:** C_T совпадает с паспортом, а г/Вт ниже на 5–15 %
  - Возможная причина: потери в приводе — другой ESC и тайминг, тонкие или длинные провода, напряжение меряется на БП, а не на ESC.
  - Что сделать: мерить U на входе ESC, сравнить с ESC из таблицы, проверить сечения.
  - Последствия: время висения будет меньше паспортного расчёта в той же пропорции.
- **Симптом:** обороты вдвое выше ожидаемых или C_T скачет от точки к точке
  - Возможная причина: оптодатчик ловит две метки или блики от лопастей, неверный `TACH_PPR` или делитель полюсов для eRPM.
  - Что сделать: одна матовая метка, экран от света, сверка с внешним тахометром.
- **Симптом:** мотор продолжает крутиться, когда завис ПК или отвалился датчик
  - Возможная причина: безопасность привязана к циклу чтения датчика или нет таймаута команды.
  - Что сделать: отдельный таймер безопасности, таймаут 0.5 с, аппаратный выключатель питания ESC.
  - Последствия: неуправляемый проп 15" — травма.

## checklist
- Стенд на струбцинах, проп за кольцом, до стен ≥ 1–2 D
- Лимит тока и таймаут проверены без пропа
- Калибровка вдоль оси пропа, k и остатки записаны
- Ноль до и после прогона, дрейф учтён
- г/Вт сравнено с паспортом при равной тяге, U (k = 2) указана

## references
- T-Motor — MN4006 KV380 Antigravity: specifications and test data | https://store.tmotor.com/product/mn4006-kv380-motor-antigravity-type.html | primary | A
- Avia Semiconductor — HX711 24-bit ADC for weigh scales, datasheet | https://cdn.sparkfun.com/datasheets/Sensors/ForceFlex/hx711_english.pdf | primary | A
- Texas Instruments — INA226 current/power monitor, datasheet | https://www.ti.com/lit/ds/symlink/ina226.pdf | primary | A
- HTC Sensor — TAL220F miniature load cell, datasheet | https://cdn.shopify.com/s/files/1/0761/6561/1847/files/TAL220F.pdf | primary | A
- Brandt, Selig — Propeller Performance Data at Low Reynolds Numbers (AIAA 2011-1255) | https://m-selig.ae.illinois.edu/pubs/BrandtSelig-2011-AIAA-2011-1255-LRN-Propellers.pdf | primary | A
- Espressif — Arduino-ESP32 LEDC API | https://docs.espressif.com/projects/arduino-esp32/en/latest/api/ledc.html | primary | A
- bogde/HX711 — Arduino library for HX711 (alternative to manual reading) | https://github.com/bogde/HX711 | primary | B
