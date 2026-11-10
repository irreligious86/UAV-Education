---
id: ctl-sysid
title: "System Identification: Chirp, Frequency Response, a Model for Tuning"
level: L4
readingTime: 40 min
firmware: ArduCopter 4.5+ · Python 3 + NumPy
status: published
tags:
  - identification
  - chirp
  - frequency response
  - model
related:
  - ctl-theory
  - ctl-signals
  - ap-tuning
  - bf-blackbox
next:
  - ap-tuning
source: content/tools/ctl-sysid.md
source_hash: d6cde7f16ed3
---

## summary
Tuning “by eye,” and even AUTOTUNE, answers the question “which gains,” but not “why.” System identification answers it: you feed the vehicle a known signal (a chirp — a sine wave with rising frequency), record the response, compute the frequency response, and fit a model with meaningful parameters to it — the motor time constant, the delay, the gain. With a model, tuning becomes a calculation: phase margin, crossover frequency, what a filter will cost. This module covers the chirp and the requirements for the experiment, the SYSID mode in ArduCopter, estimating the frequency response from spectra, fitting a first-order-plus-delay model, and using the model to choose gains. The code is checked on synthetic data first, then on a SITL log.

## theory
### Why a model
- A controller is tuned for a plant. The plant of a copter's rate loop is “torque command → angular rate”: the body inertia, the motor time constant (prop spin-up), the delays (filters, ESC, the computation loop).
- A model of the form G(s) = K·e^(−sτ) / (Ts + 1) (or with an integrator, to go to the angle) describes this chain with three numbers. Knowing them, you can compute the phase margin for any gains, see how much phase a new filter will “eat,” and compare two vehicles objectively.
- The “Control Theory” module gave you the language (transfer functions, margins); here you learn how to get a model from a flight.

### The chirp and the requirements for the experiment
- A **chirp** is a sine wave whose frequency rises from f₀ to f₁ over the recording time. An exponential (logarithmic) chirp spends the same time on every octave — convenient for a logarithmic frequency axis.
- **Frequency range**: from below the expected loop bandwidth (1–2 Hz) to above the crossover frequency (30–60 Hz for small copters), but below the frequencies where the noise and frame resonances are.
- **Amplitude**: large enough for the signal to be above the noise, and small enough not to drive the motors into saturation and nonlinearity. The sign of saturation is motors at their limit in the log.
- **Duration**: tens of seconds — more periods at low frequencies, a more accurate estimate.
- **Closed loop.** The vehicle flies with the controllers running, so input and output are coupled through the controller. It matters where the signal is injected and what is taken as the “input”: you estimate the ratio of the output to the actual signal at the plant input (for example, to the controller/mixer output), not to the setpoint.

### SYSID mode in ArduCopter
- A mode “like STABILIZE” that injects a chirp at a selected point in the loop and writes the data to the log (`SIDD` messages — time-domain data, `SIDS` — settings).
- `SID_AXIS` — where to inject (angle, rate or mixer on roll/pitch/yaw, etc.; the values are per the list for your version). While `SID_AXIS = 0`, you can't enter the mode; in addition, the vehicle must be airborne, and you can switch to SYSID for axes 1–13 only from a manual-throttle mode (STABILIZE, ACRO), and for axes 14–19 only from LOITER.
- `SID_MAGNITUDE` — amplitude, `SID_F_START_HZ` and `SID_F_STOP_HZ` — the range, `SID_T_REC` — recording duration, `SID_T_FADE_IN`/`SID_T_FADE_OUT` — smooth ramp-up and ramp-down of the amplitude.
- Safety: altitude, open space, the pilot ready to take over by switching modes; start with a small amplitude, and in SITL first.
- Betaflight and PX4: Betaflight since 2025.12 has a `CHIRP` mode (build option `USE_CHIRP`, parameters `chirp_*`, the settings are written to the Blackbox header); 4.5 has no built-in chirp (analysis is done from Blackbox with manual disturbances); in PX4 the copter autotune identifies the model online by itself, and for manual identification there are signal generators in test builds — see the documentation for your version.

### Frequency response from spectra
For a linear system Y(f) = H(f)·U(f). The estimate is H = (Y·U*) / |U|², averaged over frequency bands: divide the cross-spectrum by the input spectrum. Averaging over a band suppresses noise; where there is little energy in the input (outside the chirp), the estimate is meaningless.
- **Coherence** (the quality of the estimate) — how much of the output is explained linearly by the input: close to 1 — good; dropping — noise, nonlinearity, another input (wind, pilot).
- The result is points on a Bode plot: gain in dB and phase in degrees.

### Fitting the model
Model G(s) = K·e^(−sτ) / (Ts + 1):
- at low frequencies the gain ≈ K;
- at the corner frequency 1/(2πT) the gain is −3 dB, the phase −45° (without delay);
- the delay τ doesn't change the gain but adds −360°·f·τ of phase, growing with frequency. So T is seen from the gain, τ from the “extra” phase at high frequencies.

The fit minimizes the difference between the complex H and G over the points (grid search over T and τ, K analytically). On the module's example (T = 20 ms, τ = 10 ms, noise on the output) the fit returns T = 20 ms and τ ≈ 9 ms: the model is continuous while the data are discrete with a 2.5 ms step, so half a step of delay gets “lost.”

{{diagram:chart-sysid-bode|Frequency response from a chirp: points computed from spectra and a first-order-plus-delay model; the gain corner is at 8 Hz, and the phase drops off because of the delay.}}

### Model → tuning
- **Phase margin.** For a proportional controller Kp the open loop is L = Kp·G. The crossover frequency is where |L| = 1; the phase margin is 180° + ∠L at it. The larger Kp, the higher the crossover frequency and the smaller the margin because of the delay.
- **The cost of a filter.** A low-pass filter with frequency f_c adds approximately −arctan(f/f_c) of phase: at a 20 Hz loop crossover, an 80 Hz filter takes away ~14°. This is the “filters eat the margin” from the “Filters” module — now as a number.
- **Comparing vehicles and changes.** New props, motors, frame — a new model: you can see whether the time constant or the delay changed, and how much in gains it costs.

## practice
### Step 1. Synthetic check
The identification and fitting code; first on data with a known answer:
```python
import numpy as np

def identify(u, y, fs, f_lo=1.0, f_hi=40.0, nbins=30):
    """Frequency response y/u in log-spaced bins (cross-spectrum / auto-spectrum)."""
    U, Y = np.fft.rfft(u), np.fft.rfft(y)
    f = np.fft.rfftfreq(len(u), 1 / fs)
    edges = np.geomspace(f_lo, f_hi, nbins + 1)
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        k = (f >= lo) & (f < hi)
        if k.any():
            H = np.sum(Y[k] * np.conj(U[k])) / np.sum(np.abs(U[k]) ** 2)
            out.append((np.sqrt(lo * hi), H))
    return np.array([o[0] for o in out]), np.array([o[1] for o in out])

def fit_first_order_delay(fq, H):
    """Grid search K, T, tau for K e^{-s tau} / (T s + 1)."""
    s = 2j * np.pi * fq
    best = None
    for T in np.arange(0.002, 0.1, 0.001):
        for tau in np.arange(0.0, 0.05, 0.0005):
            G = np.exp(-s * tau) / (T * s + 1)
            K = np.real(np.vdot(G, H) / np.vdot(G, G))
            err = np.sum(np.abs(H - K * G) ** 2)
            if best is None or err < best[0]:
                best = (err, K, T, tau)
    return best[1:]

if __name__ == "__main__":          # synthetic check: chirp through a known plant
    fs, dur = 400.0, 20.0
    t = np.arange(0, dur, 1 / fs)
    k = 40.0 ** (1 / dur)
    u = np.sin(2 * np.pi * (k ** t - 1) / np.log(k))
    a, d = np.exp(-1 / (fs * 0.02)), int(0.01 * fs)
    y = np.zeros_like(u)
    for i in range(1, len(u)):
        y[i] = a * y[i - 1] + (1 - a) * (u[i - d] if i >= d else 0)
    y += np.random.default_rng(1).normal(0, 0.02, len(y))
    fq, H = identify(u, y, fs)
    K, T, tau = fit_first_order_delay(fq, H)
    print(f"K = {K:.2f}, T = {T * 1000:.0f} ms, τ = {tau * 1000:.1f} ms")
# K = 1.00, T = 20 ms, τ = 9.0 ms
```
Change the noise (0.02 → 0.2) and the duration (20 → 5 s) and write down how the estimation error of T and τ changes.

### Step 2. Phase margin from the model
For the model you found, compute the crossover frequency and the phase margin for several Kp values (numerically: |Kp·G(j2πf)| = 1). Add a low-pass filter 1/(s/(2π·f_c) + 1) with f_c = 80 and 40 Hz and write down how many degrees of margin it costs.

### Step 3. SYSID in SITL
ArduCopter SITL: `SID_AXIS` — rate or mixer on roll (per the list for your version), small amplitude, `SID_F_START_HZ = 1`, `SID_F_STOP_HZ = 30`, `SID_T_REC = 20`. Take off, hover in STABILIZE (entry from GUIDED or ALT_HOLD is not allowed for axes 1–13), switch to SYSID, record to the end, exit. From the log take the plant input — `RATE.ROut` (the controller output together with the injected chirp; `SIDD.Targ` is the chirp alone, and with it you get a “setpoint → output” estimate) — and the roll rate (`SIDD.Gx` or `RATE.R`), resample them to a common rate and run them through the step 1 code. Write down K, T, τ.

### Step 4. Change and compare
Change the gyro filter (`INS_GYRO_FILTER` halved) and repeat step 3. Compare τ and the phase at 20 Hz before and after; does it match the step 2 estimate?

The lab counts as done when the synthetic check recovers the parameters with an assessment of the effect of noise and duration, the phase margin is computed for several Kp values and filters, a model from SITL is obtained, and the effect of the gyro filter is measured and compared with the calculation.

## diagnostics
- **Symptom:** the frequency response points “jump around”
  - Possible cause: small amplitude relative to the noise, a short recording, wind or pilot intervention.
  - What to do: larger amplitude (without saturation), a longer recording, calm weather, hands off the sticks.
- **Symptom:** at high frequencies the phase drops off without limit
  - Possible cause: the real delay is larger than in the model, filters, frame resonance.
  - What to do: evaluate the model in the range where it applies; handle resonances separately (notch).
- **Symptom:** the model fits well, but the gains based on it make the vehicle oscillate
  - Possible cause: a “setpoint → output” estimate instead of “plant input → output” in a closed loop.
  - What to do: take the actual signal into the plant (the controller/mixer output) as the input.
- **Symptom:** the motors hit their limits during the chirp
  - Possible cause: amplitude too large, low thrust margin.
  - What to do: reduce `SID_MAGNITUDE`, check the hover throttle.
- **Symptom:** it won't enter SYSID mode
  - Possible cause: `SID_AXIS = 0`, parameters not refreshed, the vehicle is on the ground, or the switch isn't from a manual-throttle mode (for axes 14–19 — not from LOITER).
  - What to do: set the axis, refresh the parameters in the GCS.

## references
- ArduPilot — System Identification mode | https://ardupilot.org/copter/docs/systemid-mode.html | primary | A
- ArduPilot — mode_systemid.cpp (parameters and logging) | https://github.com/ArduPilot/ardupilot/blob/master/ArduCopter/mode_systemid.cpp | primary | A
- Tischler, Remple — Aircraft and Rotorcraft System Identification (AIAA) | https://arc.aiaa.org/doi/book/10.2514/4.861352 | primary | A
- NumPy — Discrete Fourier Transform (numpy.fft) | https://numpy.org/doc/stable/reference/routines.fft.html | primary | B

## checklist
- I can explain why a plant model is needed and what its parameters are
- I plan a chirp: range, amplitude, duration, injection point
- I configure and safely run SYSID in ArduCopter
- I estimate the frequency response from spectra and understand coherence
- I fit a first-order-plus-delay model and check it on synthetic data
- I compute the phase margin and the cost of a filter from the model
