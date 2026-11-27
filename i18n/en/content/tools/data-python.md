---
id: data-python
title: "Python for Flight Data Analysis"
level: L2
readingTime: 40 min
firmware: Betaflight · ArduPilot · INAV
status: published
added: 2026-11-08
tags:
  - Python
  - pandas
  - logs
  - spectrum
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
Blackbox Explorer and MAVExplorer show plots; an engineer needs numbers you can compare before/after and put in a report. This module is a minimal stack: Python + pandas + numpy + scipy + matplotlib; how to read a Betaflight log (via `blackbox_decode` into CSV) and an ArduPilot log (`.bin` via pymavlink), how to build a gyro spectrum with Welch's method, and how to write reusable metric functions: overshoot, settling time, bounce-back, loop jitter. All the code works, with expected numbers.

## theory
### Stack and installation
```bash
python3 -m venv ~/uav-venv && source ~/uav-venv/bin/activate
pip install pandas numpy scipy matplotlib pymavlink
```
`blackbox_decode` comes from the betaflight/blackbox-tools repository (built with `make`); it turns a `.BFL` into a CSV with one row per PID loop.

### Reading logs
**Betaflight CSV**: columns `time (us)`, `gyroADC[0..2]` (deg/s; after the filters it is `gyroADC`, before them `gyroUnfilt` (a separate blackbox field in 4.5, enabled by field selection; `debug_mode = GYRO_SCALED` writes the unfiltered gyro into `debug[]`)), `setpoint[0..3]`, `motor[0..3]`, `rcCommand[0..3]`, `axisP/I/D/F[...]`, `eRPM[...]` with ESC telemetry.

```python
import pandas as pd, numpy as np
df = pd.read_csv("log.01.csv", skipinitialspace=True)
df.columns = [c.strip() for c in df.columns]
t = df["time (us)"].to_numpy() / 1e6
fs = 1 / np.median(np.diff(t))          # logging rate, Hz (8000/4000/2000)
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
For high-rate gyro data use `IMU` (usually 1 kHz with RAW IMU in `LOG_BITMASK`) or the batch samples `ISBH/ISBD` (up to several kHz for spectra; `INS_LOG_BAT_MASK`).

### Spectrum: why Welch and not a single FFT
An FFT of the whole log is noisy and depends on its length. Welch's method cuts the signal into overlapping windows, takes the FFT of each and averages them: an estimate of the power spectral density with controlled resolution (Δf = fs / nperseg).

```python
from scipy.signal import welch
f, pxx = welch(gyro_roll, fs=fs, nperseg=1024, noverlap=512, window="hann")
pxx_db = 10 * np.log10(pxx + 1e-12)
```
With fs = 8000 and nperseg = 1024 the resolution is 7.8 Hz; a motor peak at 250 Hz shows up as a bump 2–3 bins wide. Compare logs only with the same fs and nperseg. The segment for the spectrum is a hover or steady flight of 10–20 s, without full throttle (otherwise the peaks smear across frequencies).

### Spectrogram
```python
from scipy.signal import spectrogram
f, tt, S = spectrogram(gyro_roll, fs=fs, nperseg=512, noverlap=256)
# imshow(10*log10(S), aspect="auto", origin="lower", extent=[tt[0], tt[-1], f[0], f[-1]])
```
It shows whether the peaks move with RPM (motors) or stay put (resonance) — see the “Signals and Spectra” module.

### Step response metrics
From a setpoint → gyro pair on one axis:

- **Error** e(t) = setpoint − gyro.
- **Overshoot** — how far gyro flies past the setpoint after a step, in % of the step size.
- **Settling time** — after how many ms gyro stays within ±5% (or ±2%) of the setpoint.
- **Bounce-back** — after a sharp stick stop (setpoint → 0) gyro swings to the opposite side: the rebound amplitude in % of the peak value before the stop.
- **Delay** — the lag between setpoint and gyro at the cross-correlation maximum.

A convenient implementation doesn't search for steps by hand but builds a **step response** by deconvolution (like PID Toolbox): compute the impulse response of the setpoint→gyro system over windows and integrate it. Simpler for a start — pick the segments where |d setpoint/dt| is large and measure on them.

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
Reference values for a 5" (Betaflight): overshoot 5–15% is good; bounce-back < 10% is good, > 25% means too much D or poor mechanics.

{{diagram:step-metrics-anatomy|What the functions compute: overshoot — the overshoot above a normalized step, settling time — entering ±5 % for good, bounce-back — the rebound after the stick is released, in percent of the peak (the response shape is schematic).}}

{{diagram:chart-dpy-sitl-roll-step|A real roll step from the lab's ArduCopter 4.7.2 SITL log: the target (RDes) is acceleration-limited and rises for about 100 ms, the response (R) lags by 30 ms at the 50 % level and enters the ±5 % band after 202 ms without overshoot.}}

### Loop jitter
```python
dt = np.diff(t) * 1e6   # µs
print(dt.mean(), dt.std(), np.percentile(dt, 99.9))
```
At 8 kHz the mean is 125 µs and the std a few µs; std > 10 means an overloaded processor, gaps mean dropped log writes.

{{diagram:log-analysis-pipeline|A Python log analysis pipeline: CSV → DataFrame → common time axis → spectra and metrics → report.}}

## practice
### Step 1. Read
Your own log (Betaflight CSV or ArduPilot .bin) → DataFrame, fs computed, the first 5 rows and the column description printed.

### Step 2. Spectrum
Pick 10 s of hover, run `welch` on all three axes, plot in dB up to fs/2, label the peaks with their frequencies. Save a PNG.

### Step 3. Metrics
`step_metrics` and `bounce_back` on roll: a table of steps with overshoot and settle, the median bounce-back. Compare with the reference values.

### Step 4. Package
Put the functions into `uavlog.py` (read_bf, read_ap, spectrum, step_metrics, bounce_back) with docstrings; a second log runs through in three lines.

### Test on synthetic data before your own log
Before you trust the spectrum of your log, test the function on a signal with a known answer: a 210 Hz sine plus noise must give a peak exactly there.

```python
import numpy as np
from scipy.signal import welch

fs = 2000.0                                     # 8 kHz loop, blackbox 1/4
t = np.arange(0, 10, 1 / fs)
x = 5 * np.sin(2 * np.pi * 210 * t) + np.random.default_rng(0).normal(0, 1, t.size)
f, p = welch(x, fs=fs, nperseg=int(fs))        # 1 s windows -> 1 Hz resolution
print(f"peak at {f[np.argmax(p)]:.0f} Hz")      # expect 210
```

### What you should get and what to record
- **Step 1.** `fs` is computed from the log timestamps, not taken from the settings: for Betaflight it is the loop rate divided by the Blackbox logging divider (8 kHz / 4 = 2 kHz), for ArduPilot it is the rate of the message you read. An error in `fs` shifts every frequency in the spectrum by the same factor.
- **Step 2.** Frequency resolution equals `fs / nperseg`. The motor peaks of a 5" in hover usually lie in the hundreds of hertz, and their harmonics are visible at multiples. Label the peak frequencies and compare them with motor RPM from the RPM filter module if bidir DShot is enabled.
- **Step 3.** Reference values for a 5" from the theory: overshoot 5–15 % is good, bounce-back below 10 % is good, above 25 % means too much D or poor mechanics. Record the median over 10–20 steps, not the best step.
- **Step 4.** A second log runs through in three lines: `read_*`, `spectrum`, `bounce_back`. If you have to fix something by hand, the function isn't ready yet.

The lab counts as done when the log is read into a DataFrame with `fs` computed, the Welch spectrum is built for all three axes with labeled peaks and tested on synthetic data, and the bounce-back function has produced a median on two logs and been compared with the reference values.

Lab code and output (verbatim from the source module):

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
- **Symptom:** the spectra of two logs can't be compared
  - Possible cause: different fs or nperseg, different flight modes.
  - What to do: the same parameters, the same mode (hover).
- **Symptom:** step_metrics is empty
  - Possible cause: the log has no sharp stick movements, or the threshold doesn't match fs.
  - What to do: a flight with sharp stick stops; pick the threshold from a histogram of d setpoint.
- **Symptom:** the spectrum peaks are smeared
  - Possible cause: RPM changed within the window.
  - What to do: a steady segment, a spectrogram instead of Welch.
- **Symptom:** pymavlink takes very long to read
  - Possible cause: a log of hundreds of MB, read in Python message by message.
  - What to do: filter with `type=[...]`, use `mavlogdump.py --format csv` for a one-off export.

## references
- Betaflight blackbox-tools (blackbox_decode) | https://github.com/betaflight/blackbox-tools | primary | A
- pymavlink — DataFlash log reading (mavutil) | https://github.com/ArduPilot/pymavlink | primary | A
- SciPy — scipy.signal.welch | https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html | primary | A

## checklist
- Log read into a DataFrame, fs determined
- Welch spectrum built with labeled peaks
- Overshoot, settle and bounce-back computed by functions
- Functions collected into a module and working on a second log
- I understand why Welch and not a single FFT
