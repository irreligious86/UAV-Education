---
id: ctl-signals
title: "Signals and spectra: what the gyro sees"
level: L2
readingTime: 35 min
firmware: any firmware (checked against Betaflight 2025.12.5 and ArduPilot 4.7.3)
status: published
added: 2026-11-08
tags:
  - spectrum
  - aliasing
  - notch
  - filters
related:
  - data-python
  - bf-filters
  - bf-rpm-filter
  - f-frame-mech
next:
  - bf-blackbox
source: content/tools/ctl-signals.md
source_hash: 04900abf42ad
---

## summary
The Betaflight and ArduPilot filters are signal processing, and tuning them by gut feel means tuning blind. This module gives the minimum of theory you need to read a spectrum: sampling and the Nyquist frequency, aliasing (why 10 kHz interference shows up as 2 kHz), what a spectrum and a spectrogram are, how to find motor harmonics and tell them apart from a frame resonance, and what LPF and notch filters do in both the frequency domain (attenuation) and the time domain (delay). With Python code and the link to eRPM.

## theory
### Sampling and Nyquist
The gyro is sampled at a rate fs (Betaflight: 8 kHz on F4/F7/H7 with MPU6000/ICM42688; ArduPilot: 1–8 kHz via `INS_GYRO_RATE`, with batch logging up to the full sensor rate). The Nyquist–Shannon sampling theorem: frequencies up to **fs/2** can be represented without distortion. Everything above "folds back" (aliasing): a signal at frequency f > fs/2 appears at |f − k·fs|. Example: fs = 8 kHz, 10 kHz interference → seen as 2 kHz. A worse example: the gyro runs at 4 kHz but data reaches the log at 1 kHz, so a 600 Hz motor harmonic shows up in the log at 400 Hz (the ArduPilot `IMU` message is written even less often: at the main loop rate, 400 Hz on Copter, only with the `IMU_FAST` bit of `LOG_BITMASK`; with the default bitmask, at 25 Hz). Hence: compute spectra only from data with a known fs, use batch logging for frequencies above 500 Hz, and the gyro's hardware anti-aliasing filter (configurable on the ICM42688) is a must.

### Spectrum: what is on the axes
The horizontal axis is frequency (Hz), the vertical axis is power (dB or deg²/s²/Hz). "A peak at 250 Hz, 20 dB above the noise" means 100 times the power of the background. Welch's method averages over time, which suits a stationary segment (hover). A **spectrogram** is the spectrum over time: color is power, the vertical axis is frequency; you can see the peaks move with throttle.

### Resolution: frequency versus time
A spectrum over N samples resolves frequencies in steps of Δf = fs/N and describes a segment N/fs long. At 8 kHz with N = 512: Δf ≈ 15.6 Hz over 64 ms; with N = 4096: Δf ≈ 2 Hz, but over half a second, so a peak that "moved" with throttle smears into a band. For hover, use long windows (fine frequency resolution); for a spectrogram of maneuvers, short ones. The Hann window (the default in `scipy.signal.welch`) reduces "leakage" of a strong peak's power into neighboring frequencies; without a window, a false "skirt" that looks like noise appears around a motor harmonic.

### Motor harmonics
The motor fundamental is f₁ = RPM/60. With ESC telemetry, Betaflight computes it from eRPM: RPM = eRPM / (pole pairs); a 2207 usually has 7 pole pairs (14 magnets) → `motor_poles = 14`. On a spectrogram these are sloped lines, repeating at 2f₁, 3f₁ (blades, imbalance). Four motors give four close lines that merge into a band. Check: take eRPM from the log at the same moment, compute f₁ and compare it with the peak position; a match within ±5 Hz confirms it is a motor.

### Resonance versus motors
- A **horizontal** peak on the spectrogram (independent of throttle) is a resonance of the frame, mount or wiring. Fixed with mechanics or a static notch.
- A **sloped** peak (tracking eRPM) is a motor. Fixed with the RPM filter (it tracks on its own) or balancing.
- A broad "cushion" at the bottom, 20–80 Hz, that grows during sharp moves is prop wash and aerodynamics; it cannot be filtered without losing response, and is treated with the D-term and mechanics.

### What a filter does: two points of view
A **1st-order LPF (PT1)** with cutoff frequency fc: in the frequency domain, −3 dB at fc, then −20 dB/decade (×10 in frequency = ×0.1 in amplitude). In the time domain, **delay**: the group delay at low frequencies ≈ 1/(2π·fc); a 100 Hz PT1 delays the useful signal by ~1.6 ms. PT2/PT3 (cascades) roll off more steeply (−40/−60 dB/decade) but add more delay. Betaflight: `gyro_lpf1_static_hz`, `dterm_lpf1_static_hz`, a throttle-dependent dynamic LPF; ArduPilot: `INS_GYRO_FILTER`, `ATC_RAT_*_FLTD/FLTE/FLTT`.

A **notch** with center fₙ and width (Q): a deep dip only around fₙ, little delay outside the band. A narrow one (high Q) is precise but misses when the RPM changes; a wide one is more robust but adds more delay. An RPM notch is narrow because it knows the frequency; a dynamic notch finds the peak itself (Betaflight `dyn_notch_count/q/min_hz/max_hz`; ArduPilot's harmonic notch `INS_HNTCH_*` with tracking by throttle, RPM or FFT).

The price of any filter is delay, and the price of delay is stability margin (the "Control theory" module). The goal of filter tuning: minimum delay with motor noise below the level that heats the motors (D-term noise).

### Reference numbers (course guidelines, not firmware values)
5" 6S hover: f₁ ≈ 200–260 Hz (12–16 thousand rpm; 14,000 rpm ≈ 233 Hz, as in `f-physics`) (f₁ grows as √(thrust per motor): a heavier build runs higher), peaks 20–30 dB above the background before filtering, ≤ 5 dB after the RPM notch. The delay of the gyro LPF + D LPF chain on a good 5" tune is 1–2 ms; with "heavy" filtering it is 4–6 ms, and that already shows up as bounce-back.

{{diagram:peak-diagnosis|How to identify a peak in the gyro spectrum by how it behaves with throttle, and how to deal with it.}}

{{diagram:chart-gyro-spectrum|A model gyro spectrum: at the bottom, the vehicle's motion (the useful signal), motor harmonic peaks (moving with throttle), a narrow frame-resonance peak (staying put) and the noise floor.}}

{{diagram:chart-aliasing|Aliasing at a 1 kHz sample rate: everything above 500 Hz "folds" into the 0–500 Hz band, so a 700 Hz vibration looks like 300 Hz in the data. That is why the anti-aliasing filter must come before sampling, not after.}}

### Where it fits

- **Takes in:** raw gyro data with a known sample rate, from Blackbox (`bf-blackbox`) or ArduPilot batch sampling (`ap-logs`); eRPM from the ESC (`f-motors-esc`); mechanical sources of peaks (`f-frame-mech`).
- **Hands off:** the ability to read a spectrum to filter tuning (`bf-filters`, `ap-tuning`); the cost of a filter in milliseconds of delay to the stability-margin calculation (`ctl-theory`); spectrum code to `data-python`.
- **If you get this wrong:** you computed the spectrum from a 1 kHz log → a 600 Hz motor harmonic shows up at 400 Hz → the notch is placed at a frequency that does not exist (`ap-tuning`). You took a horizontal frame-resonance peak for a motor → the RPM filter does not catch it; it is fixed with mechanics (`f-frame-mech`).

## practice
### Step 0. Practice on synthetic data
Before trusting your analysis of a log, test it on a signal where you know the answer:
```python
import numpy as np
from scipy import signal
fs = 8000; t = np.arange(0, 10, 1 / fs)
rpm = np.interp(t, [0, 5, 10], [12000, 21000, 12000])          # throttle up and down
phase = 2 * np.pi * np.cumsum(rpm / 60) / fs                   # motor fundamental follows rpm
x = (2.0 * np.sin(phase) + 0.8 * np.sin(2 * phase)             # motor 1x and 2x
     + 1.0 * np.sin(2 * np.pi * 180 * t)                       # frame resonance, fixed
     + np.random.default_rng(0).normal(0, 0.5, t.size))        # noise floor
f, P = signal.welch(x[: 2 * fs], fs, nperseg=2048)             # first 2 s: near-steady
print("peaks (Hz):", sorted(int(v) for v in f[signal.find_peaks(10 * np.log10(P), prominence=10)[0]]))
f2, t2, S = signal.spectrogram(x, fs, nperseg=512, noverlap=384)
```
Expected: `peaks (Hz): [179, 218, 500]`: ~180 Hz is the frame (the Welch frequency bin is ≈ 3.9 Hz), around 220 Hz is the motor (within 2 s the RPM rose from 200 to ~260 Hz, so the peak is smeared), around 500 Hz is the edge of the smeared second harmonic; on the spectrogram `S` (plot `pcolormesh(t2, f2, 10*log10(S))`, 0–1000 Hz) the motor lines are sloped and the 180 Hz line is horizontal. If your code shows something else, the bug is in the code, not in the drone.

### Step 1. Spectrogram
From `data-python`: a `spectrogram` of roll with nperseg=512 for 8 kHz (Δf ≈ 15.6 Hz, a 64 ms window, a 32 ms time step with noverlap=256). Plot it with a dB color scale, 0–1000 Hz.

### Step 2. Harmonics ↔ eRPM
Take `eRPM[0..3]` at 5 moments in time, compute f₁ = eRPM·100/(poles/2)/60 (the raw Blackbox `eRPM` field is in units of 100 eRPM; Blackbox Explorer already shows RPM and Hz) and plot them as dots on the spectrogram. A match means motors; find 2f₁.

### Step 3. Resonance
Find a horizontal peak. If there is one: frequency, width, amplitude; relate it to the mechanics (the "Frame and vibration" module). If not, make sure all peaks are sloped.

### Step 4. The filter, numerically
Model a 100 Hz PT1 and a 250 Hz notch with Q=5 in Python (`scipy.signal.butter`/`iirnotch`), plot the magnitude response and group delay; apply them to gyro data from the log (`lfilter`) and plot the spectrum before/after. Self-check: the lab is done when the step 0 code on synthetic data prints `peaks (Hz): [179, 218, 500]`, the motor lines on the spectrogram are sloped and the 180 Hz line is horizontal; the f₁ = eRPM·100/(poles/2)/60 dots at five moments land on the sloped lines of the log spectrogram and 2f₁ is found; the horizontal peak is described by frequency, width and amplitude, or you have noted that all peaks are sloped; the magnitude response and group delay of the 100 Hz PT1 and the 250 Hz Q=5 notch are plotted, and the gyro spectrum after the filters is lower than the original around 250 Hz and above 100 Hz.

**Reference answer for self-check.** Correct result: the sloped lines follow the RPM (motors), the horizontal ones do not depend on RPM (frame resonance). Typical wrong results: (1) on synthetic data the peaks are not where expected: the bug is in the code, not in the drone; (2) the f₁ dots are off the lines by the same factor every time: the eRPM conversion used the wrong number of poles, or the raw eRPM was not multiplied by 100 (a factor of exactly 100).

## diagnostics
- **Symptom:** the peaks in the log do not match eRPM
  - Possible cause: wrong `motor_poles`, the raw Blackbox `eRPM` not multiplied by 100, aliasing from a low logging fs.
  - What to do: check the number of magnets, log at the full rate.
- **Symptom:** a peak remains after the RPM filter
  - Possible cause: it is a resonance (does not track throttle) or a harmonic above `rpm_filter_harmonics`.
  - What to do: a spectrogram; a static notch or mechanics; more harmonics.
- **Symptom:** mushy response, bounce-back grew after adding filters
  - Possible cause: cutoff frequencies too low, too much delay.
  - What to do: raise fc, replace PT1 with a notch where the noise is narrowband.
- **Symptom:** "noise" below 100 Hz grows during maneuvers
  - Possible cause: prop wash, which cannot be filtered.
  - What to do: mechanics, D-term, do not lower the filters.

## references
- Betaflight — Deep Dive (Filtering, Aliasing and Gyro Sync) | https://betaflight.com/docs/wiki/guides/current/Deep-Dive | primary | A
- ArduPilot — Managing Gyro Noise with the Harmonic Notch Filter | https://ardupilot.org/copter/docs/common-imu-notch-filtering.html | primary | A
- SciPy — scipy.signal.spectrogram | https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.spectrogram.html | primary | A

## checklist
- I know what fs/2 is and what aliasing looks like
- I can read a spectrogram: sloped lines are motors, horizontal ones are resonance
- I have matched peaks to eRPM through the number of poles
- I understand the PT1 delay ≈ 1/(2π·fc) and why a notch is used
- I have modeled a filter in Python and seen the spectrum before/after
