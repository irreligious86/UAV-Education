---
id: ctl-sysid
title: "System identification: chirp, frequency response, a model for tuning"
level: L4
readingTime: 40 min
firmware: ArduCopter 4.5+ (checked against 4.7.3) · Betaflight 2025.12.5 · PX4 1.18 (checked against v1.18.0) · Python 3 + NumPy
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
source_hash: 655f31299f2d
---

## summary
Tuning by eye, and even AUTOTUNE, answers the question "which gains" but not "why." System identification answers it: you feed the vehicle a known signal (a chirp, a sine wave with rising frequency), record the response, compute the frequency response and fit a model with meaningful parameters to it: the motor time constant, the delay, the gain. With a model, tuning becomes a calculation: phase margin, crossover frequency, what a filter will cost. This module covers the chirp and the requirements for the experiment, the SYSID mode in ArduCopter, estimating the frequency response from spectra, fitting a first-order-plus-delay model, and using the model to choose gains. The code is checked on synthetic data first, then on a SITL log.

## theory
### Why a model
- A controller is tuned to its plant. The plant of a copter's rate loop is "torque command → angular rate": the airframe inertia, the motor time constant (spinning up the prop), delays (filters, ESC, the computation loop).
- A model of the form G(s) = K·e^(−sτ) / (Ts + 1) (or with an integrator, to go to angle) describes this chain with three numbers. Knowing them, you can compute the phase margin for any gains, see how much phase a new filter will "eat," and compare two vehicles objectively.
- The "Control theory" module gave you the language (transfer functions, margins); here you learn how to get a model from a flight.

### The chirp and the requirements for the experiment
- A **chirp** is a sine wave whose frequency rises from f₀ to f₁ over the recording. An exponential (logarithmic) chirp spends the same time on every octave, which suits a logarithmic frequency axis.
- **Frequency range**: from below the expected loop bandwidth (1–2 Hz) to above the crossover frequency (30–60 Hz for small copters), but below the frequencies of noise and frame resonances.
- **Amplitude**: large enough for the signal to stand above the noise, and small enough not to drive the motors into saturation and nonlinearity. The sign of saturation is motors at their limits in the log.
- **Duration**: tens of seconds; more periods at low frequencies give a more accurate estimate.
- **Closed loop.** The vehicle flies with its controllers running, so input and output are coupled through the controller. It matters where the signal is injected and what you take as the "input": you estimate the ratio of the output to the actual signal at the plant input (for example, the controller/mixer output), not to the setpoint.

### SYSID mode in ArduCopter
- A mode "like STABILIZE" that injects a chirp at a chosen point in the loop and writes the data to the log (`SIDD` messages are the time data, `SIDS` the settings).
- `SID_AXIS` selects where to inject (angle, rate or mixer on roll/pitch/yaw, and more; check the value list for your version). While `SID_AXIS = 0` the mode cannot be entered; in addition the vehicle must be flying, and you can switch into SYSID for axes 1–13 only from a mode with manual throttle (STABILIZE, ACRO), and for axes 14–19 only from LOITER.
- `SID_MAGNITUDE` is the amplitude, `SID_F_START_HZ` and `SID_F_STOP_HZ` the range, `SID_T_REC` the recording length, `SID_T_FADE_IN`/`SID_T_FADE_OUT` the smooth ramp-up and ramp-down of the amplitude.
- Safety: altitude, open space, a pilot ready to take over by switching modes; start with a small amplitude, in SITL first.
- Betaflight and PX4: Betaflight since 2025.12 has a `CHIRP` mode (build option `USE_CHIRP`, `chirp_*` parameters, settings written to the Blackbox header); 4.5 has no built-in chirp (analysis from Blackbox with manual disturbances); in PX4 the multicopter autotune (`MC_AT_EN`) injects its own signal and identifies the model online, and the fixed-wing autotune can inject a step or a linear/logarithmic sine sweep (`FW_AT_SYSID_TYPE`).

### Frequency response from spectra
For a linear system Y(f) = H(f)·U(f). The estimate is H = (Y·U*) / |U|², averaged over frequency bands: divide the cross-spectrum by the input auto-spectrum. Averaging over a band suppresses noise; where the input has little energy (outside the chirp), the estimate is meaningless.
- **Coherence** (estimate quality) is how much of the output is explained linearly by the input: close to 1 is good; a drop means noise, nonlinearity, or another input (wind, the pilot).
- The result is points on a Bode plot: magnitude in dB and phase in degrees.

### Fitting the model
Model G(s) = K·e^(−sτ) / (Ts + 1):
- at low frequencies the magnitude ≈ K;
- at the corner frequency 1/(2πT) the magnitude is −3 dB and the phase −45° (without delay);
- the delay τ does not change the magnitude but adds −360°·f·τ of phase, growing with frequency. So T shows up in the magnitude, and τ in the "extra" phase at high frequencies.

Fitting means minimizing the difference between the complex H and G over the points (a grid search over T and τ, with K found analytically). On the module's example (T = 20 ms, τ = 10 ms, noise on the output) the fit returns T = 20 ms and τ ≈ 9 ms: the model is continuous while the data is discrete with a 2.5 ms step, so half a step of delay is "lost."

{{diagram:chart-sysid-bode|Frequency response from a chirp: the points computed from spectra and the first-order-plus-delay model; the magnitude corner is at 8 Hz, and the phase drops because of the delay.}}

### Model → tuning
- **Phase margin.** For a proportional controller Kp the open loop is L = Kp·G. The crossover frequency is where |L| = 1; the phase margin is 180° + ∠L there. The larger Kp, the higher the crossover frequency and the less margin is left because of the delay.
- **The cost of a filter.** A low-pass filter with cutoff f_c adds roughly −arctan(f/f_c) of phase: at a 20 Hz loop crossover an 80 Hz filter takes ~14°. That is the "filters eat the margin" from the "Filters" module, now as a number.
- **Comparing vehicles and changes.** New props, motors, frame: a new model. You can see whether the time constant or the delay changed, and what that costs in gains.

{{diagram:chart-sysid-phase-margin|With the step 1 model, the phase margin falls as the crossover frequency rises: at 20 Hz it is 47°, an 80 Hz LPF takes 14°, a 40 Hz LPF 27°, and above ~32 Hz there is no margin even without a filter.}}

### Where it fits

- **Takes in:** the language of transfer functions and margins (`ctl-theory`); the chirp recording in the log, `SIDD` and `SIDS` (`ap-logs`); spectral estimates (`ctl-signals`); a safe first run in `ap-sitl`.
- **Hands off:** a model with K, T and τ for computing gains and phase margin instead of trial and error (`ap-tuning`, `bf-pid`); the cost of a filter in degrees of phase (`bf-filters`).
- **If you get this wrong:** you set the chirp amplitude too high → the motors saturate → the model describes the nonlinearity, and gains computed from it cause oscillations in flight (`ap-tuning`). You took the setpoint as the "input" instead of the signal at the plant input → you got a response with the controller inside it → the phase margin is computed wrong (`ctl-theory`).

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
Change the noise (0.02 → 0.2) and the duration (20 → 5 s) and record how the error of the T and τ estimates changes.

### Step 2. Phase margin from the model
For the model you found, compute the crossover frequency and phase margin for several Kp (numerically: |Kp·G(j2πf)| = 1). Add a low-pass filter 1/(s/(2π·f_c) + 1) with f_c = 80 and 40 Hz and record how many degrees of margin it costs. Then do the same for the ArduCopter gyro filter: it is a second-order (Butterworth) filter, and its phase at frequency f is −atan2(√2·r, 1 − r²), where r = f/f_c. Compute it at 20 Hz for `INS_GYRO_FILTER` = 20 Hz (the Copter default) and 10 Hz: you should get −90° and about −137°, a difference of about 47°.

### Step 3. SYSID in SITL
ArduCopter SITL: `SID_AXIS` set to rate or mixer on roll (per the list for your version), a small amplitude, `SID_F_START_HZ = 1`, `SID_F_STOP_HZ = 30`, `SID_T_REC = 20`. Take off, hover in STABILIZE (entering from GUIDED or ALT_HOLD is refused for axes 1–13), switch to SYSID, record to the end, exit. From the log take the plant input, `RATE.ROut` (the controller output together with the injected chirp; `SIDD.Targ` is the chirp alone, and with it you get a "setpoint → output" estimate), and the roll rate (`SIDD.Gx` or `RATE.R`), resample them to a common rate and run them through the step 1 code. Record K, T, τ.

### Step 4. Change and compare
Change the gyro filter (`INS_GYRO_FILTER` halved: from the 20 Hz default to 10 Hz) and repeat step 3. Compare τ and the phase at 20 Hz before and after; does it match the step 2 estimate?

Self-check: the lab is done when the step 1 code on synthetic data prints `K = 1.00, T = 20 ms, τ = 9.0 ms` (the plant has T = 20 ms and τ = 10 ms; half a sampling step is "lost"), you have recorded how the T and τ errors change with noise 0.2 and a 5 s duration, the phase margin is computed for several Kp and with the 80 and 40 Hz filters, with the 80 Hz filter costing about 14° and the 40 Hz one about 27° at a 20 Hz crossover (arctan(f/f_c)), K, T and τ are obtained from the SITL log, and after lowering `INS_GYRO_FILTER` from 20 to 10 Hz the phase at the frequency-response point nearest 20 Hz dropped by 40–55° (the step 2 calculation gives 47° exactly at 20 Hz; points at 18–22 Hz give 42–50°). If the shift is about 18°, you used the first-order formula arctan(f/f_c), but the gyro filter is second-order; if there is no shift, the parameter did not take effect or you are comparing different frequencies.

**Reference answer for self-check.** Correct result: a larger Kp means a higher crossover frequency and less phase margin; a lower filter cutoff leaves even less margin. Typical wrong results: (1) the model from SITL describes the closed loop, not the plant: the input was `SIDD.Targ` (the chirp alone), which gives a "setpoint → output" estimate; use `RATE.ROut`; (2) the frequency-response points "jump around" at the edges: outside the chirp range (1–30 Hz) the input has little energy, and the estimate is meaningless there; (3) SYSID cannot be entered: `SID_AXIS = 0`, or you did not switch from STABILIZE.

## diagnostics
- **Symptom:** the frequency-response points "jump around"
  - Possible cause: small amplitude relative to the noise, a short recording, wind or pilot input.
  - What to do: a larger amplitude (without saturation), a longer recording, calm weather, hands off the sticks.
- **Symptom:** the phase drops without limit at high frequencies
  - Possible cause: the real delay is larger than the model's, filters, a frame resonance.
  - What to do: evaluate the model in the range where it applies; handle resonances separately (notch).
- **Symptom:** the model fits well, but the gains computed from it make the vehicle oscillate
  - Possible cause: a "setpoint → output" estimate instead of "plant input → output" in the closed loop.
  - What to do: use the actual signal into the plant (the controller/mixer output) as the input.
- **Symptom:** the motors hit their limits during the chirp
  - Possible cause: too large an amplitude, low thrust headroom.
  - What to do: lower `SID_MAGNITUDE`, check the hover throttle.
- **Symptom:** the vehicle will not enter SYSID
  - Possible cause: `SID_AXIS = 0`, parameters not refreshed, the vehicle on the ground, or the switch was not made from a manual-throttle mode (for axes 14–19, not from LOITER).
  - What to do: set the axis, refresh the parameters in the ground station.

## references
- ArduPilot — System Identification mode | https://ardupilot.org/copter/docs/systemid-mode.html | primary | A
- ArduPilot — mode_systemid.cpp (parameters and logging) | https://github.com/ArduPilot/ardupilot/blob/master/ArduCopter/mode_systemid.cpp | primary | A
- Tischler, Remple — Aircraft and Rotorcraft System Identification (AIAA) | https://arc.aiaa.org/doi/book/10.2514/4.861352 | primary | A
- NumPy — Discrete Fourier Transform (numpy.fft) | https://numpy.org/doc/stable/reference/routines.fft.html | primary | B

## checklist
- I can explain why a plant model is needed and what its parameters are
- I can plan a chirp: range, amplitude, duration, injection point
- I can set up and safely run SYSID in ArduCopter
- I can estimate the frequency response from spectra and understand coherence
- I can fit a first-order-plus-delay model and check it on synthetic data
- I can compute the phase margin and the cost of a filter from the model
