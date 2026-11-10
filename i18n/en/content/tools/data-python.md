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
