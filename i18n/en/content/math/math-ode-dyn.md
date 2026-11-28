---
id: math-ode-dyn
title: "Differential equations and dynamics: from the motor to the loop"
level: L3
readingTime: 50 min
firmware: Betaflight (checked against 2025.12.5) · ArduPilot (checked against 4.7.3) · PX4 (checked against v1.18.0)
status: published
added: 2026-11-08
tags:
  - differential equations
  - time constant
  - poles
  - discretization
  - transfer function
related:
  - math-linalg-rot
  - ctl-theory
  - bf-pid
  - ap-tuning
next:
  - math-prob-est
source: content/math/math-ode-dyn.md
source_hash: 28fc710f3f4c
---

## summary
PID tuning "by eye" ends where understanding *what exactly* you are tuning begins. This module gives the minimal toolkit: the first-order equation and the time constant (motor, filter, delay mixed up with inertia), the second-order equation and its three regimes (overdamped, critically damped, underdamped), poles as the "address" of a system's behavior on the complex plane, the transfer function as a way to combine blocks by multiplication, and the thing without which no formula ever makes it into firmware: discretization: Euler, Tustin, what gets lost at a 1/8000 s step and at 1/50 s. The lab: a numerical model of one quadrotor axis with a PID, which you compare with the `pid-sim` widget and with a real motor response from a log.

## theory
### The first-order equation
The most common model in a drone: τ·ẋ + x = K·u. That is how motor thrust responds to an ESC command, and how an RC filter output, a temperature or a capacitor charge behave. The solution for a unit step input u = 1 from zero: x(t) = K·(1 − e^(−t/τ)). In time τ the output covers 63 % of the way, in 3τ 95 %, in 5τ 99 %. The **time constant τ** is the only dynamic parameter; it is also called "motor delay," although it is not a delay but inertia: the motor starts responding immediately, but smoothly.

How to find τ from a log: on a command step, find the moment the response reaches 63 % of its steady-state value. For a 5" motor with a prop τ ≈ 15–30 ms, for a 15" one 80–150 ms. It is τ that limits how "aggressive" you can make the D-term: D amplifies high frequencies, and the motor cannot follow them anyway; it only heats up.

The frequency side of the same equation: it is a low-pass filter with cutoff frequency f_c = 1/(2πτ). A 100 Hz gyro filter is τ = 1.6 ms of "inertia" added to the loop.

### The second-order equation
ẍ + 2ζω₀·ẋ + ω₀²·x = ω₀²·u. Two parameters: the natural frequency ω₀ (rad/s) and the damping ratio ζ.
- ζ > 1: overdamped: creeps up slowly without overshoot.
- ζ = 1: critically damped: the fastest arrival without overshoot.
- 0 < ζ < 1: underdamped: overshoot and decaying oscillations at ω₀√(1 − ζ²); overshoot in percent ≈ 100·e^(−πζ/√(1 − ζ²)) (ζ = 0.5 → 16 %, ζ = 0.7 → 5 %).
- ζ = 0: sustained oscillations; ζ < 0: instability, the amplitude grows.

A quadrotor axis with a PD angle controller is exactly this equation: inertia J·θ̈ = torque, torque = K_p·(θ_target − θ) − K_d·θ̇. Then ω₀ = √(K_p/J), ζ = K_d/(2√(K_p·J)). This gives the rule every tuner knows without knowing the formula: raise P and the oscillations get faster and the overshoot grows; raise D and the overshoot drops. The I-term adds a third order and can turn ζ negative: low-frequency "I oscillations" with too much I.

### Poles: the address of behavior
Any linear equation with constant coefficients has solutions of the form e^(st); substituting gives the characteristic equation, and its roots s are the **poles**. A first-order system has one pole: s = −1/τ. A second-order one: s = −ζω₀ ± ω₀√(ζ² − 1).

Reading a pole map on the complex plane:
- A negative real part means stable; the further left, the faster it decays (decay time ≈ 4/|Re s|).
- The imaginary part is the oscillation frequency (rad/s).
- A pole in the right half-plane means instability: any error grows.
- A pole on the imaginary axis is the boundary: sustained oscillations (that is how a loop behaves with P raised until it self-oscillates).

{{diagram:pole-response|A pole map and the matching step responses: further left is faster, higher up is more oscillatory, right of zero is growth.}}

### The transfer function
For linear systems with zero initial conditions, time differentiation becomes multiplication by s (the Laplace transform). First order: G(s) = K/(τs + 1). Second order: G(s) = ω₀²/(s² + 2ζω₀s + ω₀²). PID: C(s) = K_p + K_i/s + K_d·s. Blocks combine by multiplication (in series) and by the closed-loop formula T(s) = C·G/(1 + C·G). The closed-loop poles are the roots of 1 + C(s)G(s) = 0: that is where the "right" PID values live. A pure delay (packet transport, a filter) is e^(−sL): it does not change the magnitude but rotates the phase by ω·L, and it is what makes the loop unstable at high gains. The phase margin is how much more phase lag (that is, delay of PM/ω_c at the crossover frequency ω_c) can be added before self-oscillation; for a race 5" with a good tune it is 40–60° (course guideline).

### Discretization: formulas for firmware
The controller runs in ticks with period T_s (Betaflight: PID loop 4–8 kHz; ArduPilot: 400 Hz; PX4 rate loop: 800 Hz by default, up to 2 kHz via `IMU_GYRO_RATEMAX`). The derivative and integral are replaced by differences:
- **Backward Euler**: ẋ ≈ (xₖ − xₖ₋₁)/T_s; ∫x ≈ Σ xₖ·T_s. Simple, but it introduces a T_s/2 delay and distorts frequencies above f_s/10.
- **Tustin (bilinear)**: s → (2/T_s)·(z − 1)/(z + 1). It preserves stability and the frequency response more accurately; Betaflight's `biquad` filters are discretized this way (the RBJ cookbook formulas, bilinear with prewarping), while its PT1 uses backward Euler (next item).
- A first-order PT1 in code: yₖ = yₖ₋₁ + k·(xₖ − yₖ₋₁), where k = T_s/(τ + T_s); this is the backward Euler transform, practically exact for f_c ≪ f_s. In Betaflight it is `pt1FilterGain()`.
- What breaks with a large T_s: the Nyquist frequency f_s/2, above which everything folds back; the derivative of noise grows as 1/T_s; with T_s comparable to τ, forward Euler can make a stable system unstable. The rule: the loop period should be no more than τ/10 of the fastest process the loop must follow.

{{diagram:chart-pt1-discrete-phase|The larger the step, the further the discrete PT1 phase moves from the continuous −26.6°; forward Euler goes first and is unstable for T_s > 2τ ≈ 3.18 ms.}}

### Delay versus inertia
People confuse them, but they are different: inertia (τ) is a smooth response that starts immediately; delay (L) is nothing happening, then an exact copy of the input. A loop with inertia can be "pushed" with gain almost without limit; a loop with delay cannot: as the gain K grows the phase margin is eaten up, and the loop oscillates whatever you do. For a 5": L ≈ 2–4 ms (filters + RC) with τ ≈ 20 ms. That is why the mantra "fewer filters, sharper drone" holds exactly until the noise starts heating the motors.

Where exactly the limit lies is computed from the open loop L(s) = C(s)·G(s): sustained oscillations begin when L(jω) = −1 at some frequency, that is, the phase is −180° at magnitude 1 (this frequency is the phase crossover). For a P rate controller, a motor and inertia with friction, L(s) = K_p·e^(−sL) / ((τs + 1)(Js + b)), and the two conditions separate:
- phase: atan(ω·J/b) + atan(ω·τ) + ω·L = π, which gives the oscillation frequency ω_cr; it does not depend on K_p;
- magnitude: K_p,cr = √(1 + (ω_cr·τ)²) · √((J·ω_cr)² + b²).

The axis inertia contributes almost exactly 90° (atan(ωJ/b) for ω ≫ b/J), so the rest falls on atan(ω·τ) + ω·L ≈ π/2: that is the loop's "total delay," the motor inertia and the pure delay together. Without delay (L = 0) the two arctangents never add up to 180° at any frequency: there is no boundary, and as K_p grows the damping only weakens. Numbers for the lab model (τ = 20 ms, J = 1, b = 0.2, L = 5 ms): ω_cr ≈ 96 rad/s, K_p,cr ≈ 209; the phase builds up as 89.9° (inertia) + 62.5° (motor) + 27.6° (delay).

{{diagram:chart-delay-gain-limit|The boundary K_p falls roughly in inverse proportion to the delay, while τ_m barely moves it: the curves for 20 and 100 ms almost coincide; without delay there is no limit.}}

### Where it fits

- **Takes in:** the time constant of the motor with prop from a step in the log (`data-python`); the axis moment of inertia (`f-mechanics`); the firmware loop period and the filter cutoff frequencies (`bf-filters`).
- **Hands off:** poles, ζ and transfer functions to control theory (`ctl-theory`); the first-order-plus-delay model to identification (`ctl-sysid`); discretization and the Nyquist frequency to reading spectra (`ctl-signals`).
- **If you get this wrong:** you took delay for inertia → P is raised where the limit is set by the delay → the loop oscillates with any gains (`ctl-theory`). You moved a formula into companion code with a 1/50 s step without recomputing it and ignored a 100–300 ms delay → the allowable gain is several times lower than computed, and the tracking loop oscillates (`per-tracking`).

## practice
### Step 1. One axis with a PID in numpy
The model: J·θ̈ = M − b·θ̇, the motor as a first-order lag with τ_m, a PID on angular rate with a discrete step T_s and a PT1 D-term filter. Between the controller and the motor there is a pure delay `delay` (ESC communication, filters, computation time): the command reaches the motor `delay` seconds later. By default it is zero, which is the "inertia only" loop; with it, the loop gains a gain limit. The second function, `ring`, measures oscillation in the signal: the frequency and the ratio of swings one period apart (less than 1 decays, 1 is the boundary, more than 1 grows; `(0, 0)` means no oscillation).

```python
import numpy as np

def sim_axis(kp, ki, kd, tau_m=0.02, J=1.0, b=0.2, Ts=1/2000, T=1.0, d_cut=100.0, setpoint=1.0, delay=0.0):
    """One rate axis: PID -> transport delay -> first-order motor -> inertia. Returns t, rate, motor command."""
    n = int(T / Ts); t = np.arange(n) * Ts; nd = int(round(delay / Ts))   # delay in whole samples
    rate = np.zeros(n); u = np.zeros(n); m = 0.0; integ = 0.0; d_f = 0.0; prev = 0.0
    k_d = Ts / (1 / (2 * np.pi * d_cut) + Ts)                       # PT1 gain for the D-term filter
    for k in range(1, n):
        err = setpoint - rate[k - 1]
        integ += err * Ts
        d_raw = -(rate[k - 1] - prev) / Ts; prev = rate[k - 1]       # derivative on measurement
        d_f += k_d * (d_raw - d_f)
        u[k] = kp * err + ki * integ + kd * d_f
        u_del = u[k - nd] if k > nd else 0.0                          # command reaches the motor nd samples later
        m += (u_del - m) * Ts / tau_m                                 # motor: first-order lag
        acc = (m - b * rate[k - 1]) / J
        rate[k] = rate[k - 1] + acc * Ts
    return t, rate, u

def ring(t, y, t0=0.0):
    """Oscillation in y after t0: (frequency in rad/s, swing ratio per period: < 1 decays, > 1 grows)."""
    s = np.diff(y[t >= t0], 2); tt = t[t >= t0][1:-1]               # 2nd difference removes offset and slow drift
    e = np.where(np.diff(np.sign(np.diff(s))) != 0)[0] + 1          # indices of local extrema
    swing = np.abs(np.diff(s[e])); te = tt[e][:-1]                  # peak-to-trough swings, one per half-period
    keep = swing > 1e-9 * np.ptp(y); swing = swing[keep]; te = te[keep]     # drop swings lost in rounding noise
    if len(swing) < 4: return 0.0, 0.0                              # nothing that can be called an oscillation
    return np.pi / np.mean(np.diff(te)), np.exp(2 * np.mean(np.diff(np.log(swing))))
```

Without delay (do not set `delay`). Plot the step response for (kp, ki, kd) = (1, 0, 0), (3, 0, 0), (3, 0, 0.05), (3, 5, 0.05) and compare the behavior with the widget in the ctl-theory module at the same parameters. Then kp = 50: measure the overshoot and the oscillation frequency (`ring(t, rate)`) and compare them with the poles computed from the second-order formula. Raise kp to 500 and 5000 and confirm there is no boundary: the swing ratio grows but stays below 1.

With delay: `sim_axis(kp, 0, 0, T=3, delay=0.005)`. Find the kp at which sustained oscillations begin: bisect the kp interval until `ring(t, rate, t0=0.5)` gives a ratio of 1.00 ± 0.01. Measure the frequency at the boundary and compare both numbers with ω_cr and K_p,cr from the −180° phase condition (the "Delay versus inertia" section; solve the phase equation by trying values of ω or with `scipy.optimize.brentq`). Repeat for `delay` 0.002 and 0.010 and record how the boundary depends on the delay.

### Step 2. Motor τ from a log
Take a Blackbox log with a sharp stick move (or `RCOU`/`ESC` from ArduPilot with eRPM telemetry). On the segment with the motor command step, plot eRPM against time; find the 63 % time, which is τ_m. Plug the τ_m you found into the step 1 model (`tau_m=...`) and, with kp = 3, `delay=0.005`, T = 3, raise kd. "Ringing" here is measurable: `ring(t, rate)` shows an oscillation at a frequency several times higher than 1/τ_m, and the swing ratio one period apart has reached 0.5 (noticeable ringing: after three periods an eighth of the swing remains) and then 1 (the ringing does not decay). Record both kd values and the ringing frequency; compute what fraction of the command swing the motor turns into thrust at that frequency: 1/√(1 + (ω·τ_m)²). If you do not have your own log, take τ_m = 0.02 and check against the reference.

### Step 3. Discretization
Implement a 100 Hz PT1 filter (τ = 1/(2π·100) = 1.59 ms) with the single recurrence yₖ = yₖ₋₁ + k·(xₖ − yₖ₋₁) and three versions of the coefficient: forward Euler k = T_s/τ, backward Euler k = T_s/(τ + T_s), the exact formula k = 1 − e^(−T_s/τ). Steps: T_s = 1/8000, 1/1000 and 1/250. Feed in a 50 Hz sine 2 s long: at the slowest step there are five samples per period, and the Nyquist frequency of 125 Hz is above the signal. (A 1/100 step is no good for this experiment: 50 Hz is exactly the Nyquist frequency, the samples sin(π·k) are all zero, and there is nothing to compare.) Measure the output amplitude and phase over the last second (50 whole periods): a = 2·mean(y·sin(2π·50·t)), c = 2·mean(y·cos(2π·50·t)), amplitude √(a² + c²), phase atan2(c, a). Compare them with the analytic values for the continuous filter |G| = 1/√(1 + (f/f_c)²), φ = −atan(f/f_c). At T_s = 1/250, confirm that forward Euler is unstable: this is the case f_c > f_s/π, that is, T_s > 2τ = 1/(π·100) ≈ 3.18 ms (the pole 1 − 2π·f_c·T_s goes past −1; for f_c > f_s/(2π), that is, T_s > τ = 1.59 ms, it is already negative, giving alternating-sign "ringing"). For it, feed in a unit step instead of the sine and write down the first five samples.

Self-check: the lab is done when the plots for steps 1 and 3 are made and their numbers match the reference below within the stated tolerances; the boundary kp at a 5 ms delay is found in the model and agrees with the −180° phase-condition calculation; τ_m is found as the 63 % time on a step (15–30 ms is expected for a 5" motor with a prop, 80–150 ms for a 15") and two kd values, for noticeable and for sustained ringing, are recorded for it; the model's oscillation frequency is explained through the poles (the imaginary part of a pole is the frequency in rad/s, the real part the decay rate) or, in the loop with delay, through the frequency at which the open-loop phase is −180°.

**Reference answer for self-check.** All the numbers come from the step 1 code with default parameters (τ_m = 0.02, J = 1, b = 0.2, T_s = 1/2000); the model has no random quantities, so your numbers should match up to rounding.

Step 1, no delay. With P alone the steady-state value is below the setpoint, kp/(kp + b), that is, ≈ 0.83 at kp = 1 and ≈ 0.94 at kp = 3 (within T = 1 s the response does not reach it yet: 0.58 and 0.90; increase T to 10); with ki = 5 the response reaches 1. The "motor + inertia + P" loop is second order: at kp = 50 you get ζ ≈ 0.5, a peak of 1.155 at a steady state of 0.996, that is, an overshoot of ≈ 16 %, and oscillations at ≈ 43.5 rad/s (period ≈ 0.145 s), the same as the imaginary part of the poles −25.1 ± 43.4j; the swing ratio one period apart is ≈ 0.026. At kp = 500 `ring` gives 157 rad/s and a ratio of 0.36, at kp = 5000 504 rad/s and 0.73 (by the second-order formula: ζ = 0.159 and 0.050, ratio e^(−2πζ/√(1 − ζ²)) = 0.36 and 0.73): the oscillations decay more and more slowly, but the ratio never reaches 1; without delay there is no boundary kp.

Step 1, with a 5 ms delay. At kp = 50 the overshoot grows from 16 % to 28 % (peak 1.277). Swing ratio one period apart (`t0=0.5`, T = 3): kp = 100 gives 0.32, 150 gives 0.62, 200 gives 0.94, 205 gives 0.975, 210 gives 1.008, 220 gives 1.08, 250 gives 1.29. Boundary: **kp ≈ 209 ± 2**, frequency **96–97 rad/s** (≈ 15.4 Hz, period ≈ 65 ms). The phase-condition calculation gives ω_cr = 96.2 rad/s and K_p,cr = 208.8: the model and the formula agree to better than 1 %.

| `delay` | ω_cr, calculated | K_p,cr, calculated | kp at boundary, model | frequency, model |
|---|---|---|---|---|
| 2 ms | 155.9 rad/s | 510.2 | 509.7 | 157 rad/s |
| 5 ms | 96.2 rad/s | 208.8 | 208.8 | 97 rad/s |
| 10 ms | 65.5 rad/s | 108.0 | 108.0 | 66 rad/s |

The tolerance for the model is ±1 % in kp and ±1 rad/s in frequency (the frequency is measured to within the T_s step). The conclusion you should reach: the gain limit is set by the delay; twice the delay gives roughly half the allowable kp; and τ_m barely moves it (at a 5 ms `delay` and τ_m = 15, 30, 100 ms the boundary is 211, 207, 206; only the frequency changes: 110, 80, 45 rad/s).

Step 2 (kp = 3, `delay=0.005`, T = 3, `ring(t, rate)`). For τ_m = 0.02: kd = 2 gives a ratio of 0.06, 3 gives 0.18, 4 gives 0.42, 5 gives 0.70, 5.5 gives 0.87, 6 gives 1.08; at kd = 0.05 and 1 `ring` returns `(0, 0)`, no oscillation. Noticeable ringing (ratio 0.5) is at **kd ≈ 4.3 ± 0.2**, sustained ringing at **kd ≈ 5.8 ± 0.1**, at a frequency of ≈ 263 rad/s (42 Hz), while the motor's cutoff frequency is 1/τ_m = 50 rad/s (8 Hz): the motor turns 19 % of the command swing into thrust, and the rest goes into heat.

| τ_m | kd, ratio 0.5 | kd, ratio 1 | ringing frequency | 1/√(1 + (ω·τ_m)²) |
|---|---|---|---|---|
| 15 ms | 3.4 | 4.57 | 271 rad/s (43 Hz) | 0.24 |
| 20 ms | 4.3 | 5.82 | 263 rad/s (42 Hz) | 0.19 |
| 30 ms | 6.3 | 8.34 | 254 rad/s (40 Hz) | 0.13 |
| 100 ms | 19.8 | 26.0 | 240 rad/s (38 Hz) | 0.04 |

For an intermediate τ_m, interpolate linearly between the rows (check: the model gives 7.08 at τ_m = 25 ms and 13.4 at 50 ms), tolerance ±3 %: the boundary kd grows almost in proportion to τ_m. The calculation for the continuous loop (solving 1 + C(s)·G(s) = 0 with kp = 3, the D term with its 100 Hz filter, the motor and the delay; the shortcut phase condition atan(ω·τ_m) + atan(ω/(2π·100)) + ω·L = π, which ignores kp, gives the same to 0.2 %) gives 4.68, 5.96, 8.53 and 26.6; the model is 2–2.5 % lower because the discrete derivative adds its own delay. The ringing frequency is set by the delay and the D-term filter and hardly depends on τ_m; the slower the motor, the smaller the fraction of that ringing it turns into thrust. Without delay (`delay` not set) there is no ringing even at kd = 20 (ratio 0.07).

Step 3: a 50 Hz sine through a continuous 100 Hz PT1: |G| = 0.894, φ = −26.6°. The discrete filters:

| T_s | method | k | pole 1 − k | amplitude | phase |
|---|---|---|---|---|---|
| 1/8000 | forward Euler | 0.0785 | 0.9215 | 0.902 | −24.5° |
| 1/8000 | backward Euler | 0.0728 | 0.9272 | 0.887 | −26.3° |
| 1/8000 | exact | 0.0755 | 0.9245 | 0.894 | −25.5° |
| 1/1000 | forward Euler | 0.628 | 0.372 | 0.957 | −10.1° |
| 1/1000 | backward Euler | 0.386 | 0.614 | 0.844 | −24.5° |
| 1/1000 | exact | 0.467 | 0.533 | 0.898 | −18.5° |
| 1/250 | forward Euler | 2.513 | −1.513 | grows without bound | — |
| 1/250 | backward Euler | 0.715 | 0.285 | 0.752 | −16.5° |
| 1/250 | exact | 0.919 | 0.081 | 0.940 | −4.5° |

Tolerance: ±0.002 in amplitude and ±0.1° in phase (the frequency-response formula of the recursive filter, H = k / (1 − (1 − k)·e^(−j·2π·f·T_s)), gives the same numbers). At 1/8000 all three methods are within 1 % in amplitude and about 2° in phase of the continuous filter; at 1/1000 the difference is already up to 7 % and 17°, at 1/250 up to 16 % and 22°. The discrete filter's phase is always smaller than calculated: the formula uses the current sample xₖ, and the "exact" coefficient makes the step response exact, not the phase. Forward Euler at T_s = 1/250 on a unit step (y₀ = 0): 2.513, −1.290, 4.465, −4.244, 8.936: the sign alternates, the deviation from 1 grows by a factor of 1.513 per step and is 63 at the tenth sample.

Typical wrong results: the numpy model is unstable although the analysis says "stable": the integration step is large relative to τ (you need T_s ≤ τ/10); the boundary kp is searched for without `delay`: there is none there; `ring` returns `(0, 0)` or a frequency of thousands of rad/s: there is no oscillation in the signal, or it is drowned in rounding noise, so do not read the ratio in that case; τ_m is outside the expected range: the 63 % was not measured from the steady-state value; the sine amplitude in step 3 is almost zero: the signal frequency landed on f_s/2.

## diagnostics
- **Symptom:** when P is raised, the loop oscillates at a frequency that does not depend on P
  - Possible cause: this is delay, not inertia: ω·L ≈ π/2; the frequency is set by the total delay.
  - What to do: reduce the delay (filters, RC smoothing) rather than turning P.
- **Symptom:** slow (1–2 Hz) wobbles with an otherwise good fast response
  - Possible cause: too much I: the third pole has moved to the right.
  - What to do: lower I or add anti-windup / an I limit.
- **Symptom:** the numpy model is unstable although the analysis says "stable"
  - Possible cause: the integration step is too large (forward Euler) relative to τ.
  - What to do: T_s ≤ τ/10 or an implicit scheme.
- **Symptom:** the D-term is noisy, the motors are hot, and the response is no sharper
  - Possible cause: D amplifies frequencies above 1/τ_m that the motor cannot follow.
  - What to do: a D-term filter at about 3/(2πτ_m) (course guideline), less D, an RPM filter.

## references
- MIT OCW 2.003 — Dynamics and Control I | https://ocw.mit.edu/courses/2-003sc-engineering-dynamics-fall-2011/ | secondary | A
- Åström, Murray — Feedback Systems (free online) | https://fbswiki.org/wiki/index.php/Feedback_Systems:_An_Introduction_for_Scientists_and_Engineers | secondary | A
- Betaflight — filter implementation (pt1FilterGain, biquad) | https://github.com/betaflight/betaflight/blob/master/src/main/common/filter.c | primary | A
- ArduPilot — AC_PID (derivative filter, integrator limit) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/AC_PID | primary | A

## checklist
- I find τ from a step response and know what it means for the D-term
- I tell the three second-order regimes apart and link ζ to overshoot
- I can read a pole map: what is stable, what is fast, what oscillates
- I can build a loop's transfer function and understand where the closed-loop poles come from
- I can discretize a filter and a controller and know when Euler breaks
- I can tell delay from inertia and know which one gain can fight
