---
id: data-python
title: "Python для анализа полётных данных"
level: L2
readingTime: 40 мин
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
---

## summary
Blackbox Explorer и MAVExplorer показывают графики; инженеру нужны числа, которые можно сравнить до/после и положить в отчёт. Модуль — минимальный стек: Python + pandas + numpy + scipy + matplotlib; как прочитать лог Betaflight (через `blackbox_decode` в CSV) и ArduPilot (`.bin` через pymavlink), как построить спектр гироскопа методом Уэлча, и как написать переиспользуемые функции метрик: overshoot, время установления, bounce-back, джиттер петли. Весь код — рабочий, с ожидаемыми числами.

## theory
### Стек и установка
```bash
python3 -m venv ~/uav-venv && source ~/uav-venv/bin/activate
pip install pandas numpy scipy matplotlib pymavlink
```
`blackbox_decode` — из репозитория betaflight/blackbox-tools (собирается `make`), превращает `.BFL` в CSV с одной строкой на цикл PID.

### Чтение логов
**Betaflight CSV**: колонки `time (us)`, `gyroADC[0..2]` (град/с, после фильтров — `gyroADC`, до — `gyroUnfilt` (отдельное поле blackbox в 4.5, включается выбором полей; `debug_mode = GYRO_SCALED` пишет нефильтрованный гироскоп в `debug[]`)), `setpoint[0..3]`, `motor[0..3]`, `rcCommand[0..3]`, `axisP/I/D/F[...]`, `eRPM[...]` при ESC-телеметрии.

```python
import pandas as pd, numpy as np
df = pd.read_csv("log.01.csv", skipinitialspace=True)
df.columns = [c.strip() for c in df.columns]
t = df["time (us)"].to_numpy() / 1e6
fs = 1 / np.median(np.diff(t))          # частота логирования, Гц (8000/4000/2000)
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
Для гироскопа на высокой частоте — `IMU` (обычно 1 кГц при `LOG_BITMASK` с RAW IMU) или batch-сэмплы `ISBH/ISBD` (до нескольких кГц для спектров; `INS_LOG_BAT_MASK`).

### Спектр: почему Уэлч, а не один FFT
FFT всего лога — шумный и зависит от длины. Метод Уэлча режет сигнал на перекрывающиеся окна, берёт FFT каждого и усредняет: оценка спектральной плотности с контролируемым разрешением (Δf = fs / nperseg).

```python
from scipy.signal import welch
f, pxx = welch(gyro_roll, fs=fs, nperseg=1024, noverlap=512, window="hann")
pxx_db = 10 * np.log10(pxx + 1e-12)
```
При fs = 8000 и nperseg = 1024 разрешение 7.8 Гц; пик мотора на 250 Гц виден как бугор шириной 2–3 бина. Сравнивать логи — только при одинаковых fs и nperseg. Сегмент для спектра — висение или ровный полёт 10–20 с, без газа в пол (иначе пики размазываются по частотам).

### Спектрограмма
```python
from scipy.signal import spectrogram
f, tt, S = spectrogram(gyro_roll, fs=fs, nperseg=512, noverlap=256)
# imshow(10*log10(S), aspect="auto", origin="lower", extent=[tt[0], tt[-1], f[0], f[-1]])
```
Показывает, как пики едут с оборотами (моторы) или стоят (резонанс) — модуль «Сигналы и спектры».

### Метрики переходного процесса
По паре setpoint → gyro на одной оси:

- **Ошибка** e(t) = setpoint − gyro.
- **Overshoot** — насколько gyro перелетает setpoint после ступеньки, в % от величины ступеньки.
- **Время установления** — через сколько мс gyro остаётся в ±5% (или ±2%) от setpoint.
- **Bounce-back** — после резкой остановки стика (setpoint → 0) gyro уходит в противоположную сторону: амплитуда отскока в % от пикового значения перед остановкой.
- **Задержка** — лаг между setpoint и gyro по максимуму кросс-корреляции.

Удобная реализация — не искать ступеньки вручную, а строить **step response** деконволюцией (как PID Toolbox): считать импульсную характеристику системы setpoint→gyro по окнам и интегрировать. Проще для начала — отобрать участки, где |d setpoint/dt| большой, и мерить на них.

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
Ориентиры для 5" (Betaflight): overshoot 5–15% — хорошо; bounce-back < 10% — хорошо, > 25% — много D или плохая механика.

### Джиттер петли
```python
dt = np.diff(t) * 1e6   # мкс
print(dt.mean(), dt.std(), np.percentile(dt, 99.9))
```
Для 8 кГц среднее 125 мкс, std единицы мкс; std > 10 — перегруженный процессор, пропуски — обрыв записи.

{{diagram:log-analysis-pipeline|Конвейер анализа лога на Python: CSV → DataFrame → общая ось времени → спектры и метрики → отчёт.}}

## practice
### Шаг 1. Прочитать
Свой лог (Betaflight CSV или ArduPilot .bin) → DataFrame, fs посчитана, первые 5 строк и описание колонок выведены.

### Шаг 2. Спектр
Выбрать 10 с висения, `welch` по трём осям, график в дБ до fs/2, пики подписаны частотами. Сохранить PNG.

### Шаг 3. Метрики
`step_metrics` и `bounce_back` на roll: таблица шагов с overshoot и settle, медиана bounce-back. Сравнить с ориентирами.

### Шаг 4. Пакет
Сложить функции в `uavlog.py` (read_bf, read_ap, spectrum, step_metrics, bounce_back) с docstring; второй лог прогоняется в три строки. Лабораторная: DataFrame, Welch, функция bounce-back проверена на двух логах.

## diagnostics
- **Симптом:** спектры двух логов нельзя сравнить
  - Возможная причина: разные fs или nperseg, разные режимы полёта.
  - Что сделать: одинаковые параметры, один и тот же режим (висение).
- **Симптом:** step_metrics пустой
  - Возможная причина: в логе нет резких движений стиков или порог не под fs.
  - Что сделать: полёт с резкими остановками стика, порог подобрать по гистограмме d setpoint.
- **Симптом:** пики спектра размазаны
  - Возможная причина: обороты менялись внутри окна.
  - Что сделать: ровный участок, спектрограмма вместо Welch.
- **Симптом:** pymavlink читает очень долго
  - Возможная причина: лог в сотни МБ, чтение в Python по сообщению.
  - Что сделать: фильтр `type=[...]`, `mavlogdump.py --format csv` для разовой выгрузки.

## references
- Betaflight blackbox-tools (blackbox_decode) | https://github.com/betaflight/blackbox-tools | primary | A
- pymavlink — DataFlash log reading (mavutil) | https://github.com/ArduPilot/pymavlink | primary | A
- SciPy — scipy.signal.welch | https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html | primary | A

## checklist
- Лог прочитан в DataFrame, fs определена
- Спектр Уэлча построен с подписанными пиками
- Overshoot, settle и bounce-back посчитаны функциями
- Функции собраны в модуль и работают на втором логе
- Понимаю, почему Уэлч, а не один FFT
