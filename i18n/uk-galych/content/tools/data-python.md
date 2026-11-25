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

{{diagram:step-metrics-anatomy|Что считают функции: overshoot — перелёт над нормированной ступенькой, время установления — вход в ±5 % навсегда, bounce-back — отскок после отпущенного стика в процентах от пика (форма отклика условная).}}

{{diagram:chart-dpy-sitl-roll-step|Реальная ступенька крена из лабораторного лога ArduCopter 4.7.2 SITL: цель (RDes) ограничена по ускорению и растёт около 100 мс, отклик (R) отстаёт на 30 мс на уровне 50 % и входит в коридор ±5 % через 202 мс без перелёта.}}

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

Код і вивід лабораторної (дослівно з вихідного модуля):

```python
"""Fly ArduCopter 4.7.2 SITL: GUIDED takeoff 30 m, ACRO roll steps, LAND. Leaves logs/00000001.BIN.
Usage: python3 -I make_log.py <arducopter> <copter.parm> <workdir>
"""
import os, subprocess, sys, time
from pymavlink import mavutil

ardu, parm, work = sys.argv[1:4]
os.makedirs(work, exist_ok=True)
extra = os.path.join(work, "lab.parm")
open(extra, "w").write("""LOG_BITMASK 267741
LOG_DISARMED 0
INS_LOG_BAT_MASK 1
INS_LOG_BAT_OPT 0
SIM_GYR1_RND 20
SIM_VIB_FREQ_X 165
SIM_VIB_FREQ_Y 165
SIM_VIB_FREQ_Z 165
ACRO_TRAINER 0
FS_THR_ENABLE 0
""")
I = 23                                    # instance 23: TCP 5990, away from other SITLs
sitl = subprocess.Popen([ardu, "-S", "--model", "+", "--speedup", "1", "-I", str(I), "-w",
                         "--defaults", f"{parm},{extra}", "--home", "50.45,30.52,100,0"],
                        cwd=work, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    time.sleep(2)
    m = mavutil.mavlink_connection(f"tcp:127.0.0.1:{5760 + 10 * I}")
    m.wait_heartbeat(timeout=30)

    def rc(roll=1500, thr=1500):
        m.mav.rc_channels_override_send(m.target_system, m.target_component,
                                        roll, 1500, thr, 1500, 0, 0, 0, 0)

    def wait_text(txt, timeout=120):
        t_end = time.time() + timeout
        while time.time() < t_end:
            msg = m.recv_match(type="STATUSTEXT", blocking=True, timeout=1)
            if msg and txt in msg.text:
                return msg.text
        raise TimeoutError(txt)

    m.mav.request_data_stream_send(m.target_system, m.target_component,
                                   mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)
    wait_text("using GPS", 180)           # "EKF3 IMU0 is using GPS"
    m.set_mode("GUIDED")
    for _ in range(60):                   # pre-arm checks may need a few more seconds
        m.arducopter_arm()
        time.sleep(1)
        m.recv_match(type="HEARTBEAT", blocking=True, timeout=2)
        if m.motors_armed():
            break
    m.mav.command_long_send(m.target_system, m.target_component,
                            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, 30)
    t_end = time.time() + 40
    while time.time() < t_end:
        pos = m.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=1)
        if pos and pos.relative_alt > 29000:
            break
    rc()                                  # sticks centred before ACRO
    time.sleep(1)
    m.set_mode("ACRO")
    time.sleep(2)
    for k in range(6):                    # 6 pairs: +step, short pause, -step back to level
        for pwm, dur in ((1700, 0.5), (1500, 0.3), (1300, 0.5), (1500, 1.5)):
            t_end = time.time() + dur
            while time.time() < t_end:
                rc(roll=pwm)
                time.sleep(0.02)
    m.set_mode("LAND")
    m.motors_disarmed_wait()
    print("landed and disarmed")
finally:
    sitl.terminate()
    sitl.wait()
logs = sorted(os.listdir(os.path.join(work, "logs")))
bins = [f for f in logs if f.endswith(".BIN")]
print("log:", bins[-1], os.path.getsize(os.path.join(work, "logs", bins[-1])), "bytes")
# output:
# landed and disarmed
# log: 00000001.BIN 16875520 bytes
```

```python
"""uavlog.py - read an ArduPilot DataFlash .bin into pandas and compute the module's metrics.
Tested: Python 3.13, pandas 3.1.1, numpy 2.5.5, scipy 1.18.1, pymavlink 2.4.50, ArduCopter 4.7.2 SITL.
Paste step_metrics() and bounce_back() from the theory section into this file unchanged.
"""
import sys
import numpy as np
import pandas as pd
from pymavlink import mavutil
from scipy.signal import welch


def read_ap(path, types):
    """One pass over the log -> {type: DataFrame}, time column t in seconds."""
    rows = {t: [] for t in types}
    log = mavutil.mavlink_connection(path)
    while (msg := log.recv_match(type=types)) is not None:
        rows[msg.get_type()].append(msg.to_dict())
    out = {}
    for t, r in rows.items():
        df = pd.DataFrame(r).drop(columns="mavpackettype", errors="ignore")
        if "TimeUS" in df:
            df["t"] = df["TimeUS"] / 1e6
        out[t] = df
    return out


def rate_stats(t):
    """Logging rate from timestamps, not from settings: median dt, jitter, gaps."""
    dt = np.diff(t) * 1e6
    return {"fs_hz": float(1e6 / np.median(dt)), "dt_mean_us": float(dt.mean()),
            "dt_std_us": float(dt.std()), "dt_p999_us": float(np.percentile(dt, 99.9)),
            "gaps": int((dt > 2 * np.median(dt)).sum())}


def batch_gyro(isbh, isbd, axis="x"):
    """ISBH/ISBD batch sampler -> list of (sample_rate, ndarray rad/s) gyro batches."""
    out = []
    for _, h in isbh[isbh["type"] == 1].iterrows():           # type 1 = gyro, 0 = accel
        d = isbd[isbd["N"] == h["N"]].sort_values("seqno")
        x = np.concatenate([np.asarray(v, float) for v in d[axis]]) / h["mul"]
        if len(x) == h["smp_cnt"]:
            out.append((h["smp_rate"], x))
    return out


def spectrum(x, fs, nperseg):
    f, p = welch(x - x.mean(), fs=fs, nperseg=nperseg, noverlap=nperseg // 2, window="hann")
    return f, 10 * np.log10(p + 1e-12)


# paste def step_metrics(...) and def bounce_back(...) from the theory section here


if __name__ == "__main__":
    d = read_ap(sys.argv[1], ["RATE", "IMU", "ISBH", "ISBD", "MODE", "ATT"])
    print("pandas", pd.__version__, "| numpy", np.__version__, "| rows:",
          {k: len(v) for k, v in d.items()})
    imu = d["IMU"][d["IMU"]["I"] == 0]
    for name, t in (("IMU", imu["t"].to_numpy()), ("RATE", d["RATE"]["t"].to_numpy()),
                    ("ATT", d["ATT"]["t"].to_numpy())):
        print(f"{name:5s}", {k: round(v, 1) for k, v in rate_stats(t).items()})

    acro = d["MODE"].loc[d["MODE"]["Mode"] == 1, "t"].iloc[0]            # 1 = ACRO
    land = d["MODE"].loc[d["MODE"]["Mode"] == 9, "t"].iloc[0]            # 9 = LAND
    r = d["RATE"][(d["RATE"]["t"] > acro) & (d["RATE"]["t"] < land)]
    m = step_metrics(r["t"].to_numpy(), r["RDes"].to_numpy(), r["R"].to_numpy())
    print(m.round(1).to_string(index=False))
    print("median:", m[["overshoot_pct", "rise_ms", "settle_ms", "lag_ms"]].median().round(1).to_dict())
    bb = bounce_back(r["t"].to_numpy(), r["RDes"].to_numpy(), r["R"].to_numpy())
    print("bounce-back %:", bb.round(1), "median", round(float(np.median(bb)), 1))

    att = pd.merge_asof(d["ATT"][["t", "Roll"]], d["RATE"][["t", "RDes", "R"]], on="t",
                        direction="nearest", tolerance=0.005)
    print("merge_asof ATT(10 Hz) + RATE(400 Hz):", len(att), "rows,",
          int(att["R"].isna().sum()), "without a RATE sample within 5 ms")

    batches = batch_gyro(d["ISBH"], d["ISBD"])
    fs_b = batches[0][0]
    x = np.concatenate([b for _, b in batches])
    for nps in (256, 1024):
        f, p = spectrum(x, fs_b, nps)
        k = np.argmax(p[f > 20]) + np.argmax(f > 20)
        print(f"batch gyro X: {len(batches)} batches, fs={fs_b:.0f} Hz, nperseg={nps}: "
              f"df={fs_b / nps:.2f} Hz, peak {f[k]:.1f} Hz, {p[k]:.1f} dB")
    f, p = spectrum(imu["GyrX"].to_numpy(), rate_stats(imu["t"].to_numpy())["fs_hz"], 1024)
    k = np.argmax(p[f > 20]) + np.argmax(f > 20)
    print(f"IMU GyrX at 400 Hz: peak {f[k]:.1f} Hz (165 Hz injected; Nyquist 200 Hz)")
```

```text
pandas 3.1.1 | numpy 2.5.5 | rows: {'RATE': 26994, 'IMU': 53988, 'ISBH': 67, 'ISBD': 2119, 'MODE': 4, 'ATT': 674}
IMU   {'fs_hz': 400.2, 'dt_mean_us': 2500.0, 'dt_std_us': 28.7, 'dt_p999_us': 3332.0, 'gaps': 0}
RATE  {'fs_hz': 400.2, 'dt_mean_us': 2500.0, 'dt_std_us': 28.7, 'dt_p999_us': 3332.0, 'gaps': 0}
ATT   {'fs_hz': 10.0, 'dt_mean_us': 99999.6, 'dt_std_us': 177.3, 'dt_p999_us': 100793.0, 'gaps': 0}
 t_s  step_dps  overshoot_pct  rise_ms  settle_ms  lag_ms
62.1       112            0.0    120.0      202.4    30.0
62.7      -115            0.0    137.4        NaN    35.0
64.9       112            0.0    117.5      203.3    32.5
65.5      -116            0.0    144.9        NaN    35.0
67.7       112            0.0    120.0      207.4    30.0
68.4      -115            0.0    144.9        NaN    35.0
70.5       112            0.0    120.0      204.9    30.0
71.2      -115            0.0    142.4        NaN    35.0
73.4       111            0.0    117.5      202.4    30.0
74.0      -116            0.0    144.9        NaN    35.0
76.2       112            0.0    120.0      207.4    30.0
76.8      -115            0.0    139.9        NaN    35.0
median: {'overshoot_pct': 0.0, 'rise_ms': 128.7, 'settle_ms': 204.1, 'lag_ms': 33.7}
bounce-back %: [2.1 2.2 1.9 2.1 1.8 2.2 1.8 2.2 1.8 2.2 1.9 2.2] median 2.1
merge_asof ATT(10 Hz) + RATE(400 Hz): 674 rows, 0 without a RATE sample within 5 ms
batch gyro X: 33 batches, fs=1000 Hz, nperseg=256: df=3.91 Hz, peak 164.1 Hz, -26.9 dB
batch gyro X: 33 batches, fs=1000 Hz, nperseg=1024: df=0.98 Hz, peak 166.0 Hz, -22.6 dB
IMU GyrX at 400 Hz: peak 166.1 Hz (165 Hz injected; Nyquist 200 Hz)
```

```python
import io
import pandas as pd

csv = "time (us), gyroADC[0], setpoint[0]\n0, 1, 0\n125, 2, 0\n250, 3, 300\n"
df = pd.read_csv(io.StringIO(csv), skipinitialspace=True)
print(pd.__version__, list(df.columns))
df["gyroADC[0]"][df["setpoint[0]"] > 0] = 99           # chained assignment: no effect in pandas 3
print(df["gyroADC[0]"].tolist())
df.loc[df["setpoint[0]"] > 0, "gyroADC[0]"] = 99       # one-step .loc: works
print(df["gyroADC[0]"].tolist())
# output (python3 -W ignore; without it pandas also prints ChainedAssignmentError):
# 3.1.1 ['time (us)', 'gyroADC[0]', 'setpoint[0]']
# [1, 2, 3]
# [1, 2, 99]
```

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
