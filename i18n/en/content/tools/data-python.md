---
id: data-python
title: "Python for flight data analysis"
level: L2
readingTime: 55 min
firmware: "Betaflight 4.5.3 / 2025.12.5 · ArduPilot 4.7 (checked against 4.7.3; lab recorded on SITL 4.7.2) · Python 3.13: pandas 3.1.1, numpy 2.5.5, scipy 1.18.1, pymavlink 2.4.50"
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
source_hash: 5dc76402e026
---

## summary
Blackbox Explorer and MAVExplorer show plots; an engineer needs numbers that can be compared before/after and written into the tuning log. This module is the minimal stack: Python + pandas + numpy + scipy + matplotlib; how to read a Betaflight log (via `blackbox_decode` to CSV) and an ArduPilot log (`.bin` via pymavlink), how to find the real logging rate, how to compute a gyro spectrum with Welch's method without being fooled by resolution and aliasing, and how to write reusable metric functions: overshoot, rise and settling time, lag, bounce-back, loop jitter. The lab runs on a real ArduCopter 4.7.2 SITL log with a known 165 Hz "vibration" and roll steps: you can reproduce every number in it yourself and compare it with the reference.

## theory
### Stack and installation
```bash
python3 -m venv ~/uav-venv && source ~/uav-venv/bin/activate
pip install pandas numpy scipy matplotlib pymavlink
```
`blackbox_decode` comes from the betaflight/blackbox-tools repository (built with `make`) and turns a `.BFL` into a CSV with one row per logged frame.

Versions as of November 2026 (checked with `pip index versions`; pandas, numpy, scipy and pymavlink also by installing into a clean venv under Python 3.13, matplotlib from the index only): pandas 3.1.1, numpy 2.5.5, scipy 1.18.1, matplotlib 3.11.2, pymavlink 2.4.50. Install everything into a separate virtual environment (venv) and record the versions in `requirements.txt` (`pip freeze > requirements.txt`): an analysis script is as much a measuring instrument as a test stand, and six months from now it must give the same numbers on the same log.

The main change for old scripts is pandas 3.0. First, Copy-on-Write is always on. A chain like `df["gyroADC[0]"][mask] = 99` no longer changes anything in the original table (pandas issues a `ChainedAssignmentError` as a warning); the correct way is one step through `df.loc[mask, "gyroADC[0]"] = 99`. Second, text columns get the `str` dtype (StringDtype) by default instead of `object`. For numeric log fields you will not notice, but code that checked `dtype == object` to find text breaks. Both effects are shown in practice step 4 with real pandas 3.1.1 output.

| What | Where / how | Version, checked | Trap |
|---|---|---|---|
| `pd.read_csv(path, skipinitialspace=True)` | CSV from `blackbox_decode` | pandas 3.1.1 | the separator is `", "`: without `skipinitialspace` the column names start with a space |
| `df.loc[mask, col] = v` | any edit of a table | pandas ≥ 3.0 | the chain `df[col][mask] = v` does not work (Copy-on-Write) |
| `pd.merge_asof(a, b, on="t", direction="nearest", tolerance=…)` | joining messages logged at different rates | pandas 3.1.1 | both tables sorted by `t`; without `tolerance` it also joins across a gap in the log |
| `mavutil.mavlink_connection("x.bin")` + `recv_match(type=[...])` | reading DataFlash | pymavlink 2.4.50 | read all the types you need in one pass, not one pass per type |
| `msg.to_dict()` | message → table row | pymavlink 2.4.50 | the array fields `ISBD.x/y/z` arrive as `array('h')` |
| `scipy.signal.welch(x, fs, nperseg, noverlap, window)` | power spectral density | scipy 1.18.1 | Δf = fs / nperseg; for two logs, the same fs and nperseg |
| `scipy.signal.spectrogram` | spectrum over time | scipy 1.18.1 | a shorter window gives sharper time, coarser frequency |
| `blackbox_decode --unit-rotation deg/s` | gyro units | blackbox-tools, commit 49e18ca (Nov 23, 2026) | changes the column name to `gyroADC[0] (deg/s)` |
| `blackbox_high_resolution` | Betaflight 4.5.3, 2025.12.5 | OFF by default | when ON, `gyroADC`, `gyroUnfilt`, `rcCommand[0–3]`, `setpoint[0–2]` ×10 (not `setpoint[3]`, which is throttle ×1000) |
| `LOG_BITMASK` bits 0, 1, 7, 12, 18 | ArduCopter 4.7.2 | `ArduCopter/defines.h`, `Copter.cpp` | without bit 0, `RATE` is 10 Hz with bit 1, and not logged without bits 0 and 1; without bit 18, `IMU` is 25 Hz with bit 7; `PIDx` only with bit 12 |
| `INS_LOG_BAT_MASK`, `INS_LOG_BAT_CNT` | batch sampler `ISBH/ISBD` | ArduPilot 4.7.2, defaults 0 and 1024 | `ISBD.x / ISBH.mul` = rad/s; accel and gyro batches alternate (`ISBH.type` 0/1) |

### Reading logs
**Betaflight CSV**: columns `time (us)`, `gyroADC[0..2]` (deg/s; after the filters, `gyroADC`; before them, `gyroUnfilt` (a separate blackbox field, enabled through field selection; in 4.5 the unfiltered gyro could also be written to `debug[]` with `debug_mode = GYRO_SCALED`, but 2025.12 has no such mode)), `setpoint[0..3]`, `motor[0..3]`, `rcCommand[0..3]`, `axisP/I/D/F[...]`, `eRPM[...]` with ESC telemetry.

```python
import pandas as pd, numpy as np
df = pd.read_csv("log.01.csv", skipinitialspace=True)
df.columns = [c.strip() for c in df.columns]
t = df["time (us)"].to_numpy() / 1e6
fs = 1 / np.median(np.diff(t))          # logging rate, Hz (8000/4000/2000)
gyro_roll = df["gyroADC[0]"].to_numpy()
```

How `blackbox_decode` names the columns and what units they are in comes from its source (`src/blackbox_decode.c`, commit 49e18ca). Time is in microseconds by default, so the column is called `time (us)`. The gyro is output "as logged" by default (`--unit-rotation raw`), and then the column name is just `gyroADC[0]`. Betaflight writes `gyro_scale = 1.0` into the log header and puts rounded degrees per second into the `gyroADC` field (`blackbox.c`, the line `lrintf(gyro.gyroADCf[i] * blackboxHighResolutionScale)`), so "raw" here already is °/s. If you pass `--unit-rotation deg/s`, the values stay the same (printed with two decimal places), but the column name becomes `gyroADC[0] (deg/s)`, and code using `df["gyroADC[0]"]` fails with a `KeyError`. The second trap is `blackbox_high_resolution = ON` (OFF by default in 4.5.3 and 2025.12.5): the firmware multiplies `gyroADC`, `gyroUnfilt`, `rcCommand[0–3]` and `setpoint[0–2]` by 10 (`setpoint[3]` is throttle ×1000 and is not scaled; `blackbox.c` 4.5.3, lines 1138–1157), and the `blackbox_decode` source does not take this setting into account. The check is the header line `H blackbox_high_resolution:1` in the `.BFL` itself (it is text, so `grep` finds it); if it is there, divide those columns (except `setpoint[3]`) by 10 yourself.

The CSV row rate equals the PID loop rate divided by `blackbox_sample_rate` (1/1, 1/2, 1/4, 1/8, 1/16; the default is 1/4, `blackbox.c`, `.sample_rate = BLACKBOX_RATE_QUARTER`): with an 8 kHz loop that is 2 kHz. But in your analysis take `fs` from the timestamps, not from the settings. An error in `fs` shifts every frequency in the spectrum by the same factor: on the synthetic data in step 1, a 210 Hz sine with `fs` set half as high "moves" to 105 Hz.

**ArduPilot .bin**:
```python
from pymavlink import mavutil
m = mavutil.mavlink_connection("flight.bin")
rows = {"ATT": [], "RATE": []}
while (msg := m.recv_match(type=list(rows))) is not None:   # one pass for all types
    rows[msg.get_type()].append(msg.to_dict())
att = pd.DataFrame(rows["ATT"]); att["t"] = att["TimeUS"] / 1e6
```
Each message type is its own table with its own rate, and the rate is set by `LOG_BITMASK`, not by the autopilot "in general." In ArduCopter 4.7.2 (`Copter.cpp`, `loop_rate_logging` and `twentyfive_hz_logging`), `RATE` and `ANG` are logged at the loop rate only with bit 0 (ATTITUDE_FAST); without it, at 10 Hz if bit 1 is set (ATTITUDE_MED, part of the default), and not at all without bits 0 and 1; `PIDx` additionally require bit 12 (PID). `IMU` is logged at the loop rate only with bit 18 (IMU_FAST), and with bit 7 alone (IMU, also in the default) at 25 Hz. In the lab log (`SCHED_LOOP_RATE = 400`, bits 0 and 18 set) the timestamps gave: `IMU` and `RATE` at 400.2 Hz, `ATT` at 10.0 Hz. So `ATT` is useless for both spectra and rise time: in the 100 ms between its rows a step has time to finish.

The units come from the format description in the log itself (`FMTU`) and from the source: `RATE.RDes/R` are °/s, `IMU.GyrX` is rad/s, `ATT.Roll` is degrees. With several IMUs, `IMU` comes as one table with an `I` column (the sensor index), and you have to filter it: the two sensors share timestamps, half of the dt intervals are zero, and `rate_stats` by median returns `inf` (by mean, twice the rate, 800 Hz). For spectra above half the loop rate there is the batch sampler: `INS_LOG_BAT_MASK = 1` (the first IMU) writes batches of `INS_LOG_BAT_CNT` = 1024 samples at the rate at which the driver delivers samples (1000 Hz in the lab; bit 0 of `INS_LOG_BAT_OPT` gives the full sensor rate, and the default is `INS_LOG_BAT_OPT = 0`): an `ISBH` header (batch number `N`, `type` 0 for the accelerometer, 1 for the gyro, multiplier `mul`, rate `smp_rate`) and 32 `ISBD` messages with 32 samples per axis. The value in rad/s = `ISBD.x / ISBH.mul`; accelerometer and gyro batches alternate, and there is a gap between batches, so compute Welch for each batch separately and average, or over the concatenated batches with a window equal to the batch length (or a divisor of it) and no overlap; otherwise some windows straddle a seam. For simplicity, the `spectrum` function in the lab uses 50 % overlap over the concatenation; this moved the peaks by no more than one bin, but for precise measurements use the no-overlap scheme.

`pd.merge_asof` helps join tables logged at different rates: each `ATT` row (10 Hz) gets the nearest `RATE` row (400 Hz) no further away than `tolerance`. On the lab log all 674 `ATT` rows found a match within 5 ms; if `RATE` had been filtered by mode and `ATT` had not, there would be hundreds of empty rows, and you see that immediately if you print the number of `NaN` after the join. Read speed: the 16.9 MB lab log (six message types, one pass) is read in 1.2 s. For logs of hundreds of MB, narrow `type=[...]` down to the messages you need, or export a CSV once with `mavlogdump.py --types RATE --format csv`.

{{lesson:ap-logs|What each LOG_BITMASK bit enables and what it costs in SD card space is covered there.}}

### Spectrum: why Welch and not a single FFT
An FFT of the whole log is noisy and depends on its length. Welch's method cuts the signal into overlapping windows, takes the FFT of each and averages them: an estimate of the power spectral density with controlled resolution (Δf = fs / nperseg).

```python
from scipy.signal import welch
f, pxx = welch(gyro_roll, fs=fs, nperseg=1024, noverlap=512, window="hann")
pxx_db = 10 * np.log10(pxx + 1e-12)
```
At fs = 8000 and nperseg = 1024 the resolution is 7.8 Hz; a motor peak at 250 Hz shows up as a bump 2–3 bins wide. Compare logs only with the same fs and nperseg. The segment for the spectrum is a hover or steady flight of 10–20 s, without full throttle (otherwise the peaks smear across frequencies).

Choosing `nperseg` trades resolution against estimate noise. A long window gives narrow bins, but there are fewer windows in the recording and little to average; a short one gives a smooth curve, but two close peaks merge. On the lab batch log (1000 Hz, 33 gyro batches) `nperseg = 256` gave Δf = 3.91 Hz and a peak at 164.1 Hz, `nperseg = 1024` gave Δf = 0.98 Hz and a peak at 166.0 Hz; the injected frequency was 165 Hz, so both answers are correct to within one or two bins. The course guideline: Δf no coarser than 5 Hz for finding motor peaks, and no fewer than 8–10 windows per estimate.

The second limit is the Nyquist frequency fs/2: everything above it does not disappear but folds back. A component f sampled at fs appears at |f − k·fs| for the nearest integer k. The 400 Hz `IMU` log honestly showed 166.1 Hz, because 165 < 200. A 250 Hz motor peak in such a log would appear at |250 − 400| = 150 Hz: a phantom that leads to a misplaced notch. That is why motor noise is looked for in the batch sampler at the sensor rate or in Betaflight's `gyroUnfilt` at 2 kHz, not in the 400 Hz `IMU`, let alone the 10 Hz `ATT`.

### Spectrogram
```python
from scipy.signal import spectrogram
f, tt, S = spectrogram(gyro_roll, fs=fs, nperseg=512, noverlap=256)
# imshow(10*log10(S), aspect="auto", origin="lower", extent=[tt[0], tt[-1], f[0], f[-1]])
```
It shows how the peaks move with RPM (motors) or stay put (resonance); see the "Signals and spectra" module.

### Step-response metrics
From a setpoint → gyro pair on one axis:

- **Error** e(t) = setpoint − gyro.
- **Overshoot**: how far the gyro goes past the setpoint after a step, as a % of the step size.
- **Rise time**: from 10 % to 90 % of the step; it characterizes speed, so do not confuse it with lag.
- **Settling time**: after how many ms the gyro stays within ±5% (or ±2%) of the setpoint.
- **Bounce-back**: after a sharp stick stop (setpoint → 0) the gyro swings the opposite way: the rebound amplitude as a % of the peak value before the stop.
- **Lag**: the delay between setpoint and gyro, from the maximum of the cross-correlation or, more simply, from the moments both cross 50 % of the step.

A convenient implementation does not hunt for steps by hand but builds the **step response** by deconvolution (as PID Toolbox does): compute the impulse response of the setpoint→gyro system over windows and integrate it. Simpler to start with: pick the segments where the setpoint changes level quickly and measure on them.

How to find steps: by level, not by derivative. In Betaflight the setpoint follows the stick almost instantly, and a threshold on |d setpoint/dt| works. In ArduPilot the rate target is limited by the acceleration `ATC_ACC_R_MAX` (in 4.7 in °/s², 1100 in the lab; before 4.7, `ATC_ACCEL_R_MAX` in centidegrees/s²): over a nominal 2.5 ms sample it grows by no more than 1100 × 0.0025 ≈ 2.75 °/s (the log maximum is about 4 °/s, because the interval between samples reaches 3.3 ms), and it takes about 0.1 s to reach 112 °/s. A derivative threshold on such a log finds not a single step, which is exactly what happened to the first version of the function. More robust: the event is the moment |setpoint| crosses a threshold (60 °/s), the window starts at the last point before it where |setpoint| was below 2 % of the threshold, and the target is the median setpoint on the plateau.

```python
def step_metrics(t, sp, gy, thr_dps=60.0, win_s=0.45):
    """Steps of the rate setpoint (|sp| rises from <2 % to >thr): overshoot %, rise 10-90 %,
    settle into +-5 % (ms), lag at 50 %. Detects by level, not by d(sp)/dt."""
    res, hi = [], np.abs(sp) > thr_dps
    for k in np.where(hi[1:] & ~hi[:-1])[0] + 1:
        i = k - np.argmax(np.abs(sp[k::-1]) < 0.02 * thr_dps)      # back to the quiet start
        j = np.searchsorted(t, t[i] + win_s)
        base, target = sp[i], np.median(sp[k:j])
        step = target - base
        r, q = (gy[i:j] - base) / step, (sp[i:j] - base) / step
        tt = (t[i:j] - t[i]) * 1000
        out = np.abs(r - 1) > 0.05
        last_out = np.where(out)[0][-1] if out.any() else -1
        res.append({"t_s": round(t[i], 2), "step_dps": round(step),
                    "overshoot_pct": max(0.0, r.max() - 1) * 100,
                    "rise_ms": tt[np.argmax(r >= 0.9)] - tt[np.argmax(r >= 0.1)],
                    "settle_ms": tt[last_out + 1] if last_out + 1 < len(tt) else np.nan,
                    "lag_ms": tt[np.argmax(r >= 0.5)] - tt[np.argmax(q >= 0.5)]})
    return pd.DataFrame(res)
```

**Bounce-back**:
```python
def bounce_back(t, sp, gy, thr_dps=60.0, win_s=0.3):
    """After |sp| drops from >thr to ~0: reversal of gyro against the old direction, % of peak.
    The window ends where the next manoeuvre starts, or the next stick input counts as bounce."""
    out, hi, quiet = [], np.abs(sp) > thr_dps, np.abs(sp) < 0.1 * thr_dps
    for k in np.where(~hi[1:] & hi[:-1])[0] + 1:
        peak = np.median(sp[max(0, k - 40):k])
        q0 = k + np.argmax(quiet[k:])                       # setpoint back near zero
        nxt = q0 + np.argmax(~quiet[q0:]) if (~quiet[q0:]).any() else len(sp)
        j = min(np.searchsorted(t, t[k] + win_s), nxt)
        out.append(100 * max(0.0, (-np.sign(peak) * gy[k:j]).max()) / abs(peak))
    return np.array(out)
```
Course guidelines for a 5" (Betaflight): overshoot of 5–15% is good; bounce-back < 10% is good, > 25% means too much D or poor mechanics.

The bounce-back window must end where the next maneuver begins. In the lab, after the right step the stick stays centered for 0.3 s, then comes the left step. With a fixed 0.3 s window the first version of the function counted a 15–20 % rebound after every right step and 2 % after the left one: that was not a rebound but the start of the next command. With the window cut at the next departure of the setpoint from zero, all 12 values fell within 1.8–2.2 %. One rule for every metric: look at what landed in the window before you trust the number, and record the median over 10–20 events, not the best one.

{{diagram:step-metrics-anatomy|What the functions compute: overshoot is the excursion above the normalized step, settling time is entering ±5 % for good, bounce-back is the rebound after the stick is released as a percentage of the peak (the response shape is illustrative).}}

How to read the result on a real log. An ArduCopter roll step in SITL (the first of six right steps in the lab): the target rises to 112 °/s in about 100 ms, `R` crosses 50 % 30 ms after the target, goes from 10 to 90 % in 120 ms, enters the ±5 % band at 202 ms and stays in it; there is no overshoot. For the left steps the settling time is `NaN`: a steady-state error of about 5 % sits right on the edge of the band. This is not a failure of the function but a signal to choose the band deliberately and record it next to the number.

{{diagram:chart-dpy-sitl-roll-step|A real roll step from the lab ArduCopter 4.7.2 SITL log: the target (RDes) is acceleration-limited and rises for about 100 ms, the response (R) lags by 30 ms at the 50 % level and enters the ±5 % band after 202 ms with no overshoot.}}

### Loop jitter
```python
dt = np.diff(t) * 1e6   # us
print(dt.mean(), dt.std(), np.percentile(dt, 99.9))
```
At 8 kHz the mean is 125 µs with a std of a few µs; std > 10 means an overloaded CPU, and missing frames mean the recording dropped out (a course guideline for Betaflight on F7/H7). The lab ArduCopter SITL log at 400 Hz: mean 2500.0 µs, std 28.7 µs, 99.9th percentile 3332 µs, no gaps longer than two periods. A gap (`dt` larger than two median periods) breaks the spectrum: Welch over a segment with a hole gives false energy at low frequencies, so segments for spectra are chosen between gaps.

{{diagram:log-analysis-pipeline|The Python log-analysis pipeline: CSV → DataFrame → a common time axis → spectra and metrics → report.}}

### Where it fits

- **Takes in:** logs: CSV from `blackbox_decode` (`bf-blackbox`), DataFlash `.bin` (`ap-logs`), ULog via `pyulog` (`px4-intro`); what is logged and at what rate (`blackbox_sample_rate`, `LOG_BITMASK`, `INS_LOG_BAT_MASK`); what a spectrum and a spectrogram mean (`ctl-signals`).
- **Hands off:** "before/after" numbers (overshoot, rise and settling time, lag, bounce-back, spectra) to tuning (`bf-pid`, `ap-tuning`); spectral estimates to identification (`ctl-sysid`); functions that CI runs on logs from check flights (`eng-ci-configs`).
- **If you get this wrong:** you compared spectra with different fs and `nperseg` → the "improvement" was an artifact → filters get changed for nothing (`bf-filters`). You looked for motor noise in the 400 Hz `IMU` → a 250 Hz peak folded to 150 Hz → the notch is misplaced (`ctl-signals`, `ap-tuning`). You missed `blackbox_high_resolution` → every rate is 10 times too large → the "overshoot" and rates in the report are wrong (`bf-blackbox`).

## practice
The main path needs no hardware: synthetic data with a known answer, then a real ArduCopter 4.7.2 SITL log that you generate yourself. The log has two "answers" known in advance: a gyro vibration at 165 Hz (`SIM_VIB_FREQ_X/Y/Z = 165`, amplitude set by `SIM_GYR1_RND = 20` °/s × throttle) and twelve roll steps in ACRO (stick ±0.4 of travel, pairs of "right 0.5 s, pause 0.3 s, left 0.5 s, pause 1.5 s"). Everything below was run under Python 3.13 with the versions from the theory table; the output is pasted unedited.

### Step 1. Check the spectrum on synthetic data
Before you trust the spectrum of your own log, check the function on a signal with a known answer: a 210 Hz sine plus noise must give a peak exactly there. The second line is the same recording with the wrong `fs`: the peak moves by a factor of two.

```python
import numpy as np
from scipy.signal import welch

fs = 2000.0                                     # 8 kHz loop, blackbox 1/4
t = np.arange(0, 10, 1 / fs)
x = 5 * np.sin(2 * np.pi * 210 * t) + np.random.default_rng(0).normal(0, 1, t.size)
f, p = welch(x, fs=fs, nperseg=int(fs))        # 1 s windows -> 1 Hz resolution
print(f"peak at {f[np.argmax(p)]:.0f} Hz")      # expect 210
f, p = welch(x, fs=fs / 2, nperseg=int(fs))    # wrong fs: 1000 instead of 2000
print(f"wrong fs: peak at {f[np.argmax(p)]:.0f} Hz")
# output:
# peak at 210 Hz
# wrong fs: peak at 105 Hz
```

### Step 2. Generate a log in SITL
The script runs `arducopter` 4.7.2 (a built SITL, `build/sitl/bin/arducopter`) with the defaults from `Tools/autotest/default_params/copter.parm` plus its own parameters, takes off in GUIDED to 30 m, switches to ACRO, makes six pairs of steps through RC override and lands in LAND. `FS_THR_ENABLE = 0` is here only because RC comes from a MAVLink override rather than a transmitter; this config is not fit for the field, and CI catches that in the "CI and config versioning" module. Instance 23 (TCP 5990) is chosen to avoid colliding with another SITL on the machine. Run: `python3 -I make_log.py <arducopter> <copter.parm> run`, about 1.5 min.

```python
"""Fly ArduCopter 4.7.2 SITL: GUIDED takeoff 30 m, ACRO roll steps, LAND. Leaves logs/00000001.BIN.
Usage: python3 -I make_log.py <arducopter> <copter.parm> <workdir>
"""
import os, subprocess, sys, time
from pymavlink import mavutil

ardu, parm, work = (os.path.abspath(a) for a in sys.argv[1:4])
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

The first version of the scenario held a 55° bank for 1.5 s between the right and left steps: in ACRO with "mid" throttle the vehicle lost altitude and hit the ground four times (`SIM Hit ground` in the `MSG` messages). That is why the pause between the steps in a pair is short and the takeoff altitude is 30 m: the maneuver scenario is part of the measurement, and it is checked against the log too.

### Step 3. Read the log and compute the metrics
`uavlog.py` is a module made of the theory functions plus `read_ap`, `rate_stats`, `batch_gyro` and `spectrum`. Run: `python3 -I uavlog.py run/logs/00000001.BIN`. The window for analyzing steps is between entering ACRO (`MODE.Mode = 1`) and LAND (`Mode = 9`).

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

What this checks. The message rates were obtained from the timestamps and match what follows from `LOG_BITMASK`: 400 Hz for `IMU` and `RATE`, 10 Hz for `ATT`. All twelve steps were found, six in each direction; the median is taken over all twelve, and `NaN` values do not enter the median. The batch-sampler spectrum found the injected 165 Hz at both `nperseg` values, and the difference in peak position (164.1 and 166.0 Hz) is within two bins. A bounce-back of about 2 % reflects the soft SITL controller with no rebound, not a "perfect tune": the SITL model does not reproduce the mechanics of your vehicle.

### Step 4. pandas 3: Copy-on-Write and the str dtype
Old recipes from the internet often edit a table through chained indexing. In pandas 3 this changes nothing, it only produces a `ChainedAssignmentError` warning.

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

### Step 5. Your own package
Put the functions into `uavlog.py` (`read_bf`, `read_ap`, `rate_stats`, `spectrum`, `step_metrics`, `bounce_back`) with docstrings and a `requirements.txt`; a second log then runs in three lines: `read_*`, `spectrum`, `step_metrics`. If anything had to be edited by hand for the second log, the function is not ready yet. For Betaflight, `read_bf` is the `pd.read_csv` from the theory plus a check of the `.BFL` header for `blackbox_high_resolution` and of the gyro column name with and without units.

### Moving to real hardware
Betaflight: record 20–30 s of hover and a series of sharp "stick to the end stop, release" moves on roll with the `gyroUnfilt` field, `blackbox_sample_rate = 1/2` or 1/4; props come off for any work on the bench and go on only before flying at the field. Decode with `blackbox_decode LOG00001.BFL` (without `--unit-rotation`, so the column names match the code) and check `H blackbox_high_resolution` in the header. ArduPilot: while tuning, `LOG_BITMASK` with bit 0, and for filters `INS_LOG_BAT_MASK = 1`; revert them after tuning, or the log grows several times over. Abort the session: any vibration or motor sound that was not there before the change means landing and analyzing the log before the next flight. Criteria on hardware: `fs` from the timestamps equals the loop rate divided by the logging divider to within 1 %; between two hovers with the same settings, the position of the main motor peak in the spectrum differs by no more than 2 bins; the metric medians over 10–20 steps from two flights with the same settings differ by no more than 10 %; otherwise the flight-to-flight scatter is larger than the effect you set out to measure.

Self-check: the lab is done when (SITL path) the synthetic data gives a peak at 210 Hz, and 105 Hz with `fs` set half as high; `rate_stats` on your log gives 400 ± 1 Hz for `IMU` and `RATE` and 10 ± 0.1 Hz for `ATT`; `step_metrics` finds 12 steps (6 of ~112 °/s and 6 of ~−115 °/s) with medians of overshoot 0 %, rise 129 ± 10 ms, settling 204 ± 15 ms, lag 34 ± 5 ms; bounce-back over all 12 events is 1.5–2.5 %; the batch-spectrum peak lies at 165 ± 2 Hz with `nperseg` 256 and 1024, and Δf is 3.91 and 0.98 Hz; the chained assignment in pandas 3 leaves `[1, 2, 3]`, while `.loc` gives `[1, 2, 99]`. On hardware, the three criteria from "Moving to real hardware."

**Reference answer for self-check.** The correct result is a 12-row table like the step 3 output, with differences in the last digit (RC override timing on another machine drifts by 1–2 samples). Typical wrong results: (1) the step table is empty: the steps were searched for with a threshold on d setpoint/dt, while the ArduPilot target grows by only 3–4 °/s per sample; (2) bounce-back of 15–20 % every other time: the window ran into the next step of the pair; (3) all spectrum peaks are shifted by the same factor: `fs` was taken from the settings rather than the timestamps, or `IMU.I` was not filtered, so `fs_hz` comes out as `inf` (median dt = 0); (4) a "vibration" peak at an unexpected frequency in the 400 Hz log: aliasing of a component above 200 Hz; look at the batch sampler.

## diagnostics
- **Symptom:** the spectra of two logs cannot be compared
  - Possible cause: different fs or nperseg, different flight modes.
  - What to do: the same parameters, the same mode (hover).
- **Symptom:** step_metrics is empty
  - Possible cause: there are no sharp stick moves in the log; or the threshold is on the setpoint derivative while the target is acceleration-limited (`ATC_ACC_R_MAX` in ArduPilot).
  - What to do: detect events by the |setpoint| level, as in the theory; fly with sharp stick stops; pick the threshold from a histogram of |setpoint|.
- **Symptom:** the spectrum peaks are smeared
  - Possible cause: the RPM changed within the window.
  - What to do: a steady segment, a spectrogram instead of Welch.
- **Symptom:** pymavlink takes very long to read
  - Possible cause: a log of hundreds of MB read message by message in Python; or a separate pass over the file for each type.
  - What to do: one pass with `type=[...]`, `mavlogdump.py --format csv` for a one-off export.
- **Symptom:** the rates in a Betaflight CSV are 10 times larger than expected
  - Possible cause: the log has `blackbox_high_resolution = ON`, and `blackbox_decode` does not account for it.
  - What the log shows: the line `H blackbox_high_resolution:1` in the `.BFL` header.
  - What to do: divide `gyroADC`, `gyroUnfilt`, `rcCommand[0–3]`, `setpoint[0–2]` by 10 (not `setpoint[3]`).
- **Symptom:** `KeyError: 'gyroADC[0]'` on a CSV that read fine yesterday
  - Possible cause: it was decoded with `--unit-rotation deg/s`, and the column is named `gyroADC[0] (deg/s)`.
  - What to do: find the column by prefix (`[c for c in df if c.startswith("gyroADC[0]")]`) or always decode with one command from the script.
- **Symptom:** an edit `df[...][...] = …` changes nothing, and the console shows `ChainedAssignmentError`
  - Possible cause: pandas 3, Copy-on-Write.
  - What to do: a single operation, `df.loc[mask, column] = value`.
- **Symptom:** a peak in the 400 Hz `IMU` at a frequency that does not exist in the mechanics
  - Possible cause: aliasing: a component f > 200 Hz appears at |f − 400|.
  - What to do: the batch sampler (`INS_LOG_BAT_MASK = 1`) at the sensor rate.

## references
- Betaflight blackbox-tools (blackbox_decode), Readme and src/blackbox_decode.c | https://github.com/betaflight/blackbox-tools | primary | A
- Betaflight — source code (src/main/blackbox/blackbox.c, 4.5.3 and 2025.12.5) | https://github.com/betaflight/betaflight | primary | A
- pymavlink — DataFlash log reading (mavutil) | https://github.com/ArduPilot/pymavlink | primary | A
- ArduPilot — source code (ArduCopter/Copter.cpp, defines.h; libraries/AP_InertialSensor/BatchSampler.cpp), 4.7.2 | https://github.com/ArduPilot/ardupilot | primary | A
- SciPy — scipy.signal.welch | https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html | primary | A
- pandas — Copy-on-Write and migrating to 3.0 | https://pandas.pydata.org/docs/dev/user_guide/migration.html | primary | A

## checklist
- The log is read into a DataFrame, and fs is determined from the timestamps
- A Welch spectrum is plotted with labeled peaks and Δf written next to it
- Motor noise is looked for in a recording whose sample rate is more than twice the peak frequency (batch sampler / gyroUnfilt)
- Overshoot, rise, settling, lag and bounce-back are computed by the functions, and the median is recorded
- The metric window does not run into the next maneuver
- The functions are collected into a module with requirements.txt and work on a second log
- I understand why Welch and not a single FFT
