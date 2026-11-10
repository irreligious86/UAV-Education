---
id: math-ode-dyn
title: "Differential Equations and Dynamics: From the Motor to the Loop"
level: L3
readingTime: 50 min
firmware: Betaflight · ArduPilot · PX4
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
source_hash: c4589e535ee6
---

## summary
PID tuning “by eye” ends where understanding *what exactly* you are tuning begins. This module gives you the minimal toolkit: the first-order equation and the time constant (motor, filter, delay mixed with inertia), the second-order equation and its three regimes (overdamped, critically damped, underdamped), poles as the “address” of a system's behavior on the complex plane, the transfer function as a way to assemble blocks by multiplication, and — the thing without which no formula ever makes it into firmware — discretization: Euler, Tustin, what you lose at a 1/8000 s step and at 1/50 s. Lab: a numerical model of one quadcopter axis with a PID, which you will compare with the `pid-sim` widget and with a real motor response from a log.

## theory
### The first-order equation
The most common model in a drone: τ·ẋ + x = K·u. This is how motor thrust responds to an ESC command, and how an RC filter output, temperature or a capacitor's charge behave. The solution for a step input u = 1 from zero: x(t) = K·(1 − e^(−t/τ)). In time τ the output covers 63 % of the way, in 3τ — 95 %, in 5τ — 99 %. **The time constant τ** is the only dynamics parameter; it's also called “motor delay”, although it isn't a delay but inertia: the motor starts responding immediately, just smoothly.

How to find τ from a log: on a command step, find the moment where the response reaches 63 % of the steady-state value. For a 5" motor with a prop τ ≈ 15–30 ms, for a 15" — 80–150 ms. It's τ that limits how “aggressive” you can make the D-term: D amplifies high frequencies, and the motor can't follow them anyway — it just heats up.

The frequency side of the same equation: it's a low-pass filter with cutoff frequency f_c = 1/(2πτ). A 100 Hz gyro filter means τ = 1.6 ms of “inertia” added to the loop.

### The second-order equation
ẍ + 2ζω₀·ẋ + ω₀²·x = ω₀²·u. Two parameters: the natural frequency ω₀ (rad/s) and the damping ratio ζ.
- ζ > 1 — overdamped: creeps up slowly without overshoot.
- ζ = 1 — critically damped: the fastest arrival without overshoot.
- 0 < ζ < 1 — underdamped: overshoot and decaying oscillations at frequency ω₀√(1 − ζ²); overshoot in percent ≈ 100·e^(−πζ/√(1 − ζ²)) (ζ = 0.5 → 16 %, ζ = 0.7 → 5 %).
- ζ = 0 — undamped oscillations; ζ < 0 — instability, the amplitude grows.

A quadcopter axis with an angle P controller is exactly this equation: inertia J·θ̈ = torque, torque = K_p·(θ_target − θ) − K_d·θ̇. Then ω₀ = √(K_p/J), ζ = K_d/(2√(K_p·J)). This gives the rule every tuner knows without knowing the formula: raise P — the oscillations get faster and the overshoot grows; raise D — the overshoot drops. The I-term, in turn, adds a third order and can turn ζ negative — low-frequency “I oscillations” with too much I.

### Poles: the address of behavior
Any linear equation with constant coefficients has solutions of the form e^(st); substituting gives the characteristic equation, and its roots s are the **poles**. A first-order system has one pole: s = −1/τ. A second-order one: s = −ζω₀ ± ω₀√(ζ² − 1).

Reading a pole map on the complex plane:
- A negative real part — stable; the further left, the faster it decays (settling time ≈ 4/|Re s|).
- The imaginary part is the oscillation frequency (rad/s).
- A pole in the right half-plane — instability: any error grows.
- A pole on the imaginary axis — the boundary: undamped oscillations (this is how a loop behaves with P raised until it self-oscillates).

{{diagram:pole-response|A pole map and the corresponding step responses: further left — faster, higher — more oscillatory, right of zero — growth.}}

### The transfer function
For linear systems with zero initial conditions, differentiation in time turns into multiplication by s (the Laplace transform). First order: G(s) = K/(τs + 1). Second order: G(s) = ω₀²/(s² + 2ζω₀s + ω₀²). PID: C(s) = K_p + K_i/s + K_d·s. Blocks are combined by multiplication (in series) and by the closed-loop formula: T(s) = C·G/(1 + C·G). The closed-loop poles are the roots of 1 + C(s)G(s) = 0: this is where the “right” PID values live. A pure delay (packet transport, a filter) is e^(−sL): it doesn't change the amplitude, but it shifts the phase by ω·L, and that's exactly what makes the loop unstable at high gains. Phase margin is how much more delay you can add before self-oscillation; on a well-tuned 5" combat quad it's 40–60°.

### Discretization: formulas for firmware
The controller runs in ticks with period T_s (Betaflight — PID loop 4–8 kHz, ArduPilot — 400 Hz, PX4 rate loop — up to 1 kHz). Derivatives and integrals are replaced with differences:
- **Backward Euler**: ẋ ≈ (xₖ − xₖ₋₁)/T_s; ∫x ≈ Σ xₖ·T_s. Simple, but it adds a T_s/2 delay and distorts frequencies above f_s/10.
- **Tustin (bilinear)**: s → (2/T_s)·(z − 1)/(z + 1). It preserves stability and the frequency response more accurately; all Betaflight filters (`biquad`) and PT1 are discretized exactly this way or through the exact RC filter formula.
- A first-order PT1 in code: yₖ = yₖ₋₁ + k·(xₖ − yₖ₋₁), where k = T_s/(τ + T_s) — this is the backward Euler transform, practically exact when f_c ≪ f_s. In Betaflight — `pt1FilterGain()`.
- What breaks with a large T_s: the Nyquist frequency f_s/2 — everything above it folds back (aliases); the derivative of noise grows as 1/T_s; with T_s comparable to τ, forward Euler can make a stable system unstable. Rule: the loop period should be no more than τ/10 of the fastest process the loop has to handle.

### Delay versus inertia
People confuse them, but they're different: inertia (τ) is a smooth response that starts immediately; delay (L) is nothing happening, then an exact copy of the input. A loop with inertia can be “pushed” with gain almost without limit; a loop with delay can't: with gain K the phase margin gets eaten up, and at ω·L ≈ 1–1.5 rad the loop oscillates no matter what you do. For a 5": L ≈ 2–4 ms (filters + RC) with τ ≈ 20 ms. That's why the mantra “fewer filters — a sharper drone” holds right up to the moment the noise starts heating the motors.

## practice
### Step 1. One axis with a PID in numpy
Model: J·θ̈ = M − b·θ̇, the motor as a first-order system with τ_m, a PID on angular rate with a discrete step T_s and a PT1 D-term filter.

```python
import numpy as np

def sim_axis(kp, ki, kd, tau_m=0.02, J=1.0, b=0.2, Ts=1/2000, T=1.0, d_cut=100.0, setpoint=1.0):
    """One rate axis: PID -> first-order motor -> inertia. Returns t, rate, motor command."""
    n = int(T / Ts); t = np.arange(n) * Ts
    rate = np.zeros(n); u = np.zeros(n); m = 0.0; integ = 0.0; d_f = 0.0; prev = 0.0
    k_d = Ts / (1 / (2 * np.pi * d_cut) + Ts)                       # PT1 gain for the D-term filter
    for k in range(1, n):
        err = setpoint - rate[k - 1]
        integ += err * Ts
        d_raw = -(rate[k - 1] - prev) / Ts; prev = rate[k - 1]       # derivative on measurement
        d_f += k_d * (d_raw - d_f)
        u[k] = kp * err + ki * integ + kd * d_f
        m += (u[k] - m) * Ts / tau_m                                  # motor: first-order lag
        acc = (m - b * rate[k - 1]) / J
        rate[k] = rate[k - 1] + acc * Ts
    return t, rate, u
```

Plot the step response for (kp, ki, kd) = (1, 0, 0), (3, 0, 0), (3, 0, 0.05), (3, 5, 0.05). Find the kp at which undamped oscillations begin; measure their frequency and compare it with the poles computed from the second-order formula. Compare the behavior with the widget in the ctl-theory module using the same parameters.

### Step 2. Motor τ from a log
Take a Blackbox log with a sharp stick movement (or `RCOU`/`ESC` from ArduPilot with eRPM telemetry). On a motor command step, plot eRPM versus time; find the 63 % time — that's τ_m. Plug it into the step 1 model and show at what kd the model starts to “ring” at a frequency the motor can't follow.

### Step 3. Discretization
Implement a 100 Hz PT1 filter three ways (forward Euler k = T_s/τ, backward Euler k = T_s/(τ + T_s), the exact formula k = 1 − e^(−T_s/τ)) at T_s = 1/8000 and 1/100. Feed in a 50 Hz sine. Compare the amplitude and phase with the analytical |G| = 1/√(1 + (f/f_c)²), φ = −atan(f/f_c). At T_s = 1/100, show that forward Euler goes unstable when f_c > f_s/π (the pole 1 − 2π·f_c·T_s goes past −1; when f_c > f_s/(2π) it's already negative — alternating-sign “ringing”).

The lab is complete when you have the plots for steps 1 and 3, the τ_m you found, and an explanation of the oscillation frequency in terms of the poles.

## diagnostics
- **Symptom:** when you raise P, the loop oscillates at a frequency that doesn't depend on P
  - Possible cause: it's delay, not inertia: ω·L ≈ π/2; the frequency is set by the total delay.
  - What to do: reduce the delay (filters, RC smoothing) instead of cranking P.
- **Symptom:** slow (1–2 Hz) wobbles with a good fast response
  - Possible cause: too much I — the third pole has moved to the right.
  - What to do: lower I or add anti-windup/an I limit.
- **Symptom:** the numpy model is unstable even though the analysis says “stable”
  - Possible cause: the integration step is too large (forward Euler) relative to τ.
  - What to do: T_s ≤ τ/10 or an implicit scheme.
- **Symptom:** the D-term is noisy, the motors are hot, and the response is no sharper
  - Possible cause: D amplifies frequencies above 1/τ_m that the motor can't follow.
  - What to do: a D-term filter at ~1/(2πτ_m)·3, less D, an RPM filter.

## references
- MIT OCW 2.003 — Dynamics and Control I | https://ocw.mit.edu/courses/2-003sc-engineering-dynamics-fall-2011/ | secondary | A
- Åström, Murray — Feedback Systems (free online) | https://fbswiki.org/wiki/index.php/Feedback_Systems:_An_Introduction_for_Scientists_and_Engineers | secondary | A
- Betaflight — filter implementation (pt1FilterGain, biquad) | https://github.com/betaflight/betaflight/blob/master/src/main/common/filter.c | primary | A
- ArduPilot — AC_PID (derivative filter, integrator limit) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/AC_PID | primary | A

## checklist
- I find τ from a step response and know what it means for the D-term
- I tell the three second-order regimes apart and relate ζ to overshoot
- I read a pole map: what's stable, what's fast, what oscillates
- I assemble a loop's transfer function and understand where the closed-loop poles come from
- I discretize a filter and a controller and know when Euler breaks
- I tell delay from inertia and know which of them gain can fight
