---
id: data-python
title: "Python для аналізу польотних даних"
level: L2
readingTime: 40 хв
firmware: Betaflight · ArduPilot · INAV
status: published
added: 2026-11-08
tags:
  - Python
  - pandas
  - логи
  - спектр
related:
  - tools-overview
  - bf-blackbox
  - ap-logs
next:
  - ctl-signals
source: content/tools/data-python.md
source_hash: 85f0b483c55d
---

## summary
Blackbox Explorer і MAVExplorer показують графіки, але інженерові треба числа, які си можна порівняти до/після і покласти у звіт. Модуль дає мінімальний стек: Python + pandas + numpy + scipy + matplotlib; як прочитати лог Betaflight (через `blackbox_decode` у CSV) і ArduPilot (`.bin` через pymavlink), як побудувати спектр гіроскопа методом Велча і як написати функції метрик, щоб потім їх файно використовувати знов: overshoot, час встановлення, bounce-back, джитер петлі. Вшитко код — робочий, з очікуваними числами.

## theory
### Стек і встановлення
```bash
python3 -m venv ~/uav-venv && source ~/uav-venv/bin/activate
pip install pandas numpy scipy matplotlib pymavlink
```
`blackbox_decode` береш з репозиторію betaflight/blackbox-tools (збирається `make`), він перетворює `.BFL` на CSV з одним рядком на цикл PID.

### Читання логів
**Betaflight CSV**: колонки `time (us)`, `gyroADC[0..2]` (град/с, після фільтрів — `gyroADC`, до — `gyroUnfilt` (окреме поле blackbox у 4.5, вмикається вибором полів; `debug_mode = GYRO_SCALED` пише нефільтрований гіроскоп у `debug[]`)), `setpoint[0..3]`, `motor[0..3]`, `rcCommand[0..3]`, `axisP/I/D/F[...]`, `eRPM[...]`, як є ESC-телеметрія.

```python
import pandas as pd, numpy as np
df = pd.read_csv("log.01.csv", skipinitialspace=True)
df.columns = [c.strip() for c in df.columns]
t = df["time (us)"].to_numpy() / 1e6
fs = 1 / np.median(np.diff(t))          # частота логування, Гц (8000/4000/2000)
gyro_roll = df["gyroADC[0]"].to_numpy()
```

**ArduPilot .bin**:
```python
from pymavlink import mavutil
m = mavutil.mavlink_connection("flight.bin")
rows = []
while (msg := m.recv_match(type="ATT")) is not None:
    rows.append(msg.to_dict())
att = pd.DataFrame(rows); att["t"] = att["TimeUS"] / 1e6
```
Для гіроскопа на високій частоті бери `IMU` (зазвичай 1 кГц при `LOG_BITMASK` з RAW IMU) або batch-семпли `ISBH/ISBD` (до кількох кГц для спектрів; `INS_LOG_BAT_MASK`).

### Спектр: чому Велч, а не один FFT
FFT цілого логу є шумний і залежить від довжини. Метод Велча ріже сигнал на вікна, що ся перекривають, бере FFT кожного й усереднює: виходить оцінка спектральної густини з контрольованою роздільною здатністю (Δf = fs / nperseg).

```python
from scipy.signal import welch
f, pxx = welch(gyro_roll, fs=fs, nperseg=1024, noverlap=512, window="hann")
pxx_db = 10 * np.log10(pxx + 1e-12)
```
При fs = 8000 і nperseg = 1024 роздільна здатність 7.8 Гц; пік мотора на 250 Гц видно як горб завширшки 2–3 біни. Порівнювати логи — лиш за однакових fs і nperseg. Сегмент для спектра бери з зависання або рівного польоту 10–20 с, без газу в підлогу (бо інакше піки ся розмажуть по частотах).

### Спектрограма
```python
from scipy.signal import spectrogram
f, tt, S = spectrogram(gyro_roll, fs=fs, nperseg=512, noverlap=256)
# imshow(10*log10(S), aspect="auto", origin="lower", extent=[tt[0], tt[-1], f[0], f[-1]])
```
Ади, вона показує, як піки їдуть з обертами (мотори) або стоять на місці (резонанс) — докладно в модулі «Сигнали та спектри».

### Метрики перехідного процесу
За парою setpoint → gyro на одній осі:

- **Похибка** e(t) = setpoint − gyro.
- **Overshoot** — наскільки gyro перелітає setpoint після сходинки, у % від величини сходинки.
- **Час встановлення** — за скільки мс gyro ся втримує в межах ±5% (або ±2%) від setpoint.
- **Bounce-back** — після різкої зупинки стіка (setpoint → 0) gyro йде в протилежний бік: амплітуда відскоку в % від пікового значення перед зупинкою.
- **Затримка** — лаг між setpoint і gyro за максимумом крос-кореляції.

Зручно не шукати сходинки руками, а будувати **step response** деконволюцією (як PID Toolbox): рахувати імпульсну характеристику системи setpoint→gyro за вікнами й інтегрувати. Для початку простіше відібрати ділянки, де |d setpoint/dt| великий, і міряти на них.

```python
def step_metrics(sp, gy, fs, thr=200.0):
    """Find fast setpoint steps (deg/s per sample threshold) and measure response."""
    d = np.diff(sp)
    idx = np.where(np.abs(d) > thr / fs * 1000)[0]
    res = []
    for i in idx:
        seg_sp, seg_gy = sp[i:i + int(0.25 * fs)], gy[i:i + int(0.25 * fs)]
        if len(seg_gy) < 10: continue
        target = seg_sp[-1]; base = sp[i]
        step = target - base
        if abs(step) < 50: continue
        resp = (seg_gy - base) / step            # normalised 0→1
        overshoot = max(0.0, resp.max() - 1.0) * 100
        inside = np.abs(resp - 1.0) < 0.05
        settle = next((k for k in range(len(inside)) if inside[k:].all()), None)
        res.append({"t": i / fs, "step": step, "overshoot_pct": overshoot,
                    "settle_ms": None if settle is None else 1000 * settle / fs})
    return pd.DataFrame(res)
```

**Bounce-back**:
```python
def bounce_back(sp, gy, fs, big=200.0):
    """After setpoint returns to ~0 from a large value (> big deg/s), measure gyro reversal (% of peak)."""
    out = []
    hi = np.abs(sp) > big
    for i in range(1, len(sp)):
        if hi[i - 1] and not hi[i]:
            peak = sp[i - 1]
            win = gy[i:i + int(0.2 * fs)]
            rev = -np.sign(peak) * win
            out.append(100 * max(0.0, rev.max()) / abs(peak))
    return np.array(out)
```
Орієнтири для 5" (Betaflight): overshoot 5–15% — файно; bounce-back < 10% — файно, > 25% — забагато D або погана механіка.

### Джитер петлі
```python
dt = np.diff(t) * 1e6   # мкс
print(dt.mean(), dt.std(), np.percentile(dt, 99.9))
```
Для 8 кГц середнє 125 мкс, std — одиниці мкс; std > 10 — процесор перевантажений, пропуски — запис ся обірвав.

{{diagram:log-analysis-pipeline|Конвеєр аналізу логу на Python: CSV → DataFrame → спільна вісь часу → спектри й метрики → звіт.}}

## practice
### Крок 1. Прочитати
Свій лог (Betaflight CSV або ArduPilot .bin) → DataFrame, fs пораховано, перші 5 рядків і опис колонок виведено.

### Крок 2. Спектр
Вибрати 10 с зависання, `welch` по трьох осях, графік у дБ до fs/2, піки підписані частотами. Зберегти PNG.

### Крок 3. Метрики
`step_metrics` і `bounce_back` на roll: таблиця кроків з overshoot і settle, медіана bounce-back. Порівняти з орієнтирами.

### Крок 4. Пакет
Скласти функції в `uavlog.py` (read_bf, read_ap, spectrum, step_metrics, bounce_back) з docstring; другий лог має ся проганяти у три рядки.

### Перевірка на синтетиці до свого логу
Заки повіриш спектру свого логу, перевір функцію на сигналі з відомою відповіддю: синус 210 Гц плюс шум мусить дати пік рівно там.

```python
import numpy as np
from scipy.signal import welch

fs = 2000.0                                     # 8 kHz loop, blackbox 1/4
t = np.arange(0, 10, 1 / fs)
x = 5 * np.sin(2 * np.pi * 210 * t) + np.random.default_rng(0).normal(0, 1, t.size)
f, p = welch(x, fs=fs, nperseg=int(fs))        # 1 s windows -> 1 Hz resolution
print(f"peak at {f[np.argmax(p)]:.0f} Hz")      # expect 210
```

### Що має вийти і що записати
- **Крок 1.** `fs` рахуєш за часовими мітками логу, а не береш з налаштувань: у Betaflight то частота циклу, поділена на дільник запису Blackbox (8 кГц / 4 = 2 кГц), в ArduPilot — частота повідомлення, яке читаєш. Схибиш у `fs` — і всі частоти спектра ся зсунуть у стільки ж разів.
- **Крок 2.** Роздільна здатність за частотою дорівнює `fs / nperseg`. Піки моторів 5" на зависанні зазвичай лежать у сотнях герц, а їхні гармоніки видно на кратних частотах. Підпиши частоти піків і порівняй з обертами моторів із модуля про RPM-фільтр, як bidir DShot увімкнено.
- **Крок 3.** Орієнтири для 5" з теорії: overshoot 5–15 % — файно, bounce-back менше 10 % — файно, більше 25 % — забагато D або погана механіка. Запиши медіану по 10–20 кроках, а не той один крок, що найліпше трафився.
- **Крок 4.** Другий лог проганяється трьома рядками: `read_*`, `spectrum`, `bounce_back`. Як щось мусиш правити руками, то функція ще не готова.

Лабораторна зараховується, коли лог прочитано в DataFrame з порахованою `fs`, спектр Велча побудовано по трьох осях з підписаними піками й перевірено на синтетиці, функція bounce-back дала медіану на двох логах і її порівняно з орієнтирами.

## diagnostics
- **Симптом:** спектри двох логів ніяк не порівняти
  - Можлива причина: різні fs або nperseg, різні режими польоту.
  - Що зробити: однакові параметри, один і той самий режим (зависання).
- **Симптом:** step_metrics порожній
  - Можлива причина: у логу нема різких рухів стіків або поріг не підібраний під fs.
  - Що зробити: політ із різкими зупинками стіка, поріг підібрати за гістограмою d setpoint.
- **Симптом:** піки спектра розмазані
  - Можлива причина: оберти мінялися всередині вікна.
  - Що зробити: рівна ділянка, спектрограма замість Welch.
- **Симптом:** pymavlink читає фест довго
  - Можлива причина: лог на сотні МБ, читання в Python по одному повідомленню.
  - Що зробити: фільтр `type=[...]`, `mavlogdump.py --format csv` для разового вивантаження.

## references
- Betaflight blackbox-tools (blackbox_decode) | https://github.com/betaflight/blackbox-tools | primary | A
- pymavlink — DataFlash log reading (mavutil) | https://github.com/ArduPilot/pymavlink | primary | A
- SciPy — scipy.signal.welch | https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html | primary | A

## checklist
- Лог прочитано в DataFrame, fs визначено
- Спектр Велча побудовано з підписаними піками
- Overshoot, settle і bounce-back пораховано функціями
- Функції зібрано в модуль, і вони працюють на другому логу
- Розумію, чому Велч, а не один FFT
