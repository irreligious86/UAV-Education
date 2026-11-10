---
id: ctl-signals
title: "Signals and Spectra: What the Gyro Sees"
level: L2
readingTime: 35 min
firmware: any firmware
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
source_hash: f49913b9c249
---

## summary
Betaflight and ArduPilot filters are signal processing, and tuning them by intuition means tuning blind. This module gives you the minimum theory without which you can't read a spectrum: sampling and the Nyquist frequency, aliasing (why 10 kHz interference shows up as 2 kHz), what a spectrum and a spectrogram are, how to find motor harmonics and tell them apart from frame resonance, and what LPF and notch filters do in both the frequency domain (attenuation) and the time domain (delay). With Python code and the link to eRPM.

## theory
### Sampling and Nyquist
The gyro is sampled at a rate fs (Betaflight: 8 kHz on F4/F7/H7 with MPU6000/ICM42688; ArduPilot: 1–4 kHz with batch logging up to 8 kHz). The Kotelnikov–Nyquist theorem: frequencies up to **fs/2** can be represented without distortion. Anything above “folds over” (aliasing): a signal of frequency f > fs/2 appears at |f − k·fs|. Example: fs = 8 kHz, 10 kHz interference → seen as 2 kHz. A worse example: ArduPilot logs the IMU at 1 kHz while sampling internally at 4 kHz — a motor harmonic at 600 Hz ends up at 400 Hz in the log. Hence: spectra only from data with a known fs, batch logging for frequencies above 500 Hz, and the gyro's hardware anti-aliasing filter (configurable on the ICM42688) is mandatory.

### Spectrum: what's on the axes
The horizontal axis is frequency (Hz), the vertical axis is power (dB or deg²/s²/Hz). “A peak at 250 Hz, 20 dB above the noise” means 100 times more power than the background. The Welch spectrum averages over time — good for a steady segment (hover). A **spectrogram** is the spectrum over time: color is power, the vertical axis is frequency; you can see the peaks move with throttle.

### Resolution: frequency versus time
A spectrum over N samples resolves frequencies in steps of Δf = fs/N and describes a segment of duration N/fs. 8 kHz and N = 512: Δf ≈ 15.6 Hz over 64 ms; N = 4096: Δf ≈ 2 Hz, but over half a second — a peak that “moved” with throttle smears into a band. For hover you use long windows (fine frequency resolution), for a spectrogram of maneuvers — short ones. The Hann window (the default in `scipy.signal.welch`) reduces the “leakage” of a strong peak's power into neighboring frequencies; without a window, a false “skirt” that looks like noise appears around the motor harmonic.

### Motor harmonics
The motor fundamental is f₁ = RPM/60. Betaflight with ESC telemetry computes it from eRPM: RPM = eRPM / (pole pairs); a 2207 typically has 7 pairs (14 magnets) → `motor_poles = 14`. On the spectrogram these are sloped lines, repeated at 2f₁, 3f₁ (blades, imbalance). Four motors give four close lines that merge into a band. Check: take the eRPM from the log at the same moment, compute f₁, compare with the peak position — a match within ±5 Hz confirms it's a motor.

### Resonance versus motors
- A peak that is **horizontal** on the spectrogram (independent of throttle) is a resonance of the frame/mount/wires. Fixed with mechanics or a static notch.
- A **sloped** peak (tracks eRPM) is a motor. Fixed with the RPM filter (it tracks on its own) or balancing.
- A broad “cushion” at the bottom, 20–80 Hz, growing with sharp moves — propwash and aerodynamics; it can't be filtered without losing response; it's addressed with D-term and mechanics.

### What a filter does — two points of view
**A 1st-order LPF (PT1)** with cutoff frequency fc: in the frequency domain −3 dB at fc, then −20 dB/decade (×10 in frequency = ×0.1 in amplitude). In the time domain — **delay**: the group delay at low frequencies ≈ 1/(2π·fc); a 100 Hz PT1 delays the useful signal by ~1.6 ms. PT2/PT3 (cascades) cut steeper (−40/−60 dB/decade) but delay more. Betaflight: `gyro_lpf1_static_hz`, `dterm_lpf1_static_hz`, throttle-based dynamic LPF; ArduPilot: `INS_GYRO_FILTER`, `ATC_RAT_*_FLTD/FLTE/FLTT`.

**A notch** centered at fₙ with a width (Q): a deep dip only around fₙ, little delay outside the band. Narrow (high Q) — precise, but misses when RPM changes; wide — more robust, but delays more. The RPM notch is narrow because it knows the frequency; the dynamic notch searches for the peak itself (Betaflight `dyn_notch_count/q/min_hz/max_hz`; ArduPilot's harmonic notch `INS_HNTCH_*` with tracking by throttle, RPM or FFT).

The price of any filter is delay; the price of delay is stability margin (the “Control Theory” module). The goal of filter tuning: minimum delay with motor noise below the level that heats the motors (D-term noise).

### Ballpark numbers
5" 6S hover: f₁ ≈ 250–350 Hz, peaks 20–30 dB above the background before filtering, ≤ 5 dB after the RPM notch. The delay of the gyro LPF + D LPF chain in a good 5" tune is 1–2 ms; with “heavy” filtering it's 4–6 ms, and that's already noticeable in bounce-back.

{{diagram:peak-diagnosis|How to identify a peak in the gyro spectrum by how it behaves with throttle, and how to deal with it.}}

{{diagram:chart-gyro-spectrum|A model gyro spectrum: at the bottom, the vehicle's motion (the useful signal), motor harmonic peaks (moving with throttle), a narrow frame resonance peak (staying put) and the noise floor.}}

{{diagram:chart-aliasing|Aliasing at 1 kHz sampling: everything above 500 Hz “folds” into the 0–500 Hz band — a 700 Hz vibration looks like 300 Hz in the data. That's why the anti-aliasing filter must come before sampling, not after.}}

## practice
### Step 0. Practice on synthetic data
Before trusting your own log analysis, check it on a signal where the answer is known:
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
Expected: `peaks (Hz): [179, 218, 500]` — ~180 Hz is the frame (the Welch grid step ≈ 3.9 Hz), around 220 Hz is the motor (over 2 s the RPM rose from 200 to ~260 Hz, so the peak is smeared), around 500 Hz is the edge of the smeared second harmonic; on the spectrogram `S` (plot `pcolormesh(t2, f2, 10*log10(S))`, 0–1000 Hz) the motor lines are sloped and the 180 Hz line is horizontal. If your code shows something else, the bug is in the code, not in the drone.

### Step 1. Spectrogram
From `data-python`: a `spectrogram` of roll with nperseg=512 for 8 kHz (Δf 15 Hz, Δt 32 ms). Display it with a dB color scale, 0–1000 Hz.

### Step 2. Harmonics ↔ eRPM
Take `eRPM[0..3]` at 5 moments in time, compute f₁ = eRPM/(poles/2)/60, and plot them as points on the spectrogram. A match means motors; find 2f₁.

### Step 3. Resonance
Find a horizontal peak. If there is one — frequency, width, amplitude; link it to the mechanics (the “Frame and Vibration” module). If not — make sure all peaks are sloped.

### Step 4. The filter, numerically
Model a 100 Hz PT1 and a 250 Hz notch with Q=5 in Python (`scipy.signal.butter`/`iirnotch`), plot the magnitude response and the group delay; apply them to the gyro from the log (`lfilter`) and plot the spectrum before/after. Lab: the analysis is verified on synthetic data, the log harmonics are matched to eRPM, the resonance is separated, and the effect of the filters is shown with a before/after spectrum.

## diagnostics
- **Symptom:** peaks in the log don't match eRPM
  - Possible cause: wrong `motor_poles`, aliasing due to a low logging fs.
  - What to do: check the number of magnets, log at the full rate.
- **Symptom:** a peak remains after the RPM filter
  - Possible cause: it's a resonance (doesn't track throttle) or a harmonic above `rpm_filter_harmonics`.
  - What to do: spectrogram; a static notch or mechanics; more harmonics.
- **Symptom:** mushy response, bounce-back grew after adding filters
  - Possible cause: cutoff frequencies too low — large delay.
  - What to do: raise fc, replace PT1 → notch where the noise is narrowband.
- **Symptom:** “noise” below 100 Hz grows during maneuvers
  - Possible cause: propwash; it can't be filtered.
  - What to do: mechanics, D-term, don't lower the filters.

## references
- Betaflight — Deep Dive (Filtering, Aliasing and Gyro Sync) | https://betaflight.com/docs/wiki/guides/current/Deep-Dive | primary | A
- ArduPilot — Managing Gyro Noise with the Harmonic Notch Filter | https://ardupilot.org/copter/docs/common-imu-notch-filtering.html | primary | A
- SciPy — scipy.signal.spectrogram | https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.spectrogram.html | primary | A

## checklist
- I know what fs/2 is and what aliasing looks like
- I can read a spectrogram: sloped lines are motors, horizontal ones are resonance
- I matched peaks to eRPM via the pole count
- I understand the PT1 delay ≈ 1/(2π·fc) and why a notch is used
- I modeled a filter in Python and saw the spectrum before/after
