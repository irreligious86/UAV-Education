---
id: ctl-theory
title: "Control Theory: Stability, Margins, Cascades"
level: L3
readingTime: 40 min
firmware: any firmware
status: published
added: 2026-11-08
tags:
  - control theory
  - stability
  - PID
  - cascade
related:
  - ctl-signals
  - bf-pid-reg-in-bf
  - bf-pid
  - px4-control
next:
  - bf-pid
source: content/tools/ctl-theory.md
source_hash: d0b183be76ed
---

## summary
PID tuning without theory is trial and error. This module explains, at a level sufficient for an engineer, what closed-loop stability is, why delay eats the phase margin and leads to oscillations at high P, how the step response relates to poles and damping (and why bounce-back is an underdamped pole), and why the autopilot builds an angle → angular rate cascade with an inner loop several times faster than the outer one. The formulas are kept to a minimum, and each one is tied to what you see in the PID simulator and in the log.

## theory
### Plant, controller, loop
The plant is the vehicle: the input is the motor command, the output is the angular rate. The controller is the PID: the input is the error (setpoint − gyro), the output is the command. The closed loop: the output affects the input through the measurement. The whole point of the theory is to predict the behavior of the loop without closing it.

### A first-approximation model of one axis
The motor torque creates angular acceleration: J·ω̇ = M − b·ω, where J is the moment of inertia and b is the aerodynamic damping. The transfer function from torque to ω is a first-order lag 1/(J·s + b) — a “leaky integrator”: ω grows as long as torque is applied. Plus the **delays**: the motor (current/RPM, τ ≈ 10–30 ms for a 5"), the gyro and D filters (1–5 ms), the loop period and the ESC protocol (0.1–0.5 ms). The total pure delay T_d is the main enemy.

### Stability and phase margin
A loop with a P controller: at low P it's sluggish, at high P it oscillates, at even higher P the oscillations diverge. The boundary is where the loop gain equals 1 at the frequency where the phase shift reaches −180°. A pure delay T_d gives a phase shift of −360°·f·T_d: at 50 Hz with T_d = 5 ms that's −90°, and the plant pole adds another −90° — and there's your −180°. Therefore:

- **Phase margin** — how many degrees remain to −180° at the frequency where the gain = 1. 45–60° is a good tune (small overshoot); 20–30° — ringing and bounce-back; 0 — sustained oscillations.
- The delay T_d eats the margin linearly with frequency: the faster you want the loop (higher P), the more you lose. Doubling the delay at the same P loses ~half the margin.
- Hence the limit “P no higher than the delay allows.” Reducing the delay (higher filter cutoffs, an RPM notch instead of a wide LPF, a fast ESC protocol, light props) is the only way to raise P without oscillations.

### Step response, poles, damping
A second-order closed loop is described by its natural frequency ωₙ and damping ζ:
- ζ > 1 — overdamped, slow;
- ζ ≈ 0.7 — fast with ~5% overshoot; this is the goal;
- ζ = 0.4 — ~25% overshoot, ringing;
- ζ → 0 — oscillations.

**Overshoot ≈ exp(−π·ζ/√(1−ζ²))**: 0.7 → 4.6%, 0.5 → 16%, 0.3 → 37%. Settling time ≈ 4/(ζ·ωₙ). Bounce-back after the stick stops is the same underdamped pole, just excited by a “downward” step: large bounce-back = low ζ = either too little D, or too much P/delay. The D-term increases the damping (ζ) — that's why “lots of D” removes the bounce, but D amplifies noise ∝ frequency, and the D filters add delay, which again reduces the margin. That's the tuning trade-off.

### I-term: steady-state error and windup
I removes steady-state error (wind, asymmetry). It pays in phase: an integrator gives −90° at low frequencies, so too much I means slow oscillations (0.5–3 Hz, “wandering”). Windup is I accumulating while the outputs are saturated (stick at the endpoint, motors at the ceiling): firmware limits it (`iterm_limit`, `iterm_relax`, in ArduPilot `ATC_RAT_*_IMAX`).

### Feedforward
FF applies a command proportional to the derivative of the setpoint, bypassing the error: the output starts moving before the error has built up. It doesn't affect stability (it's outside the loop), but too much of it gives overshoot on sharp stick moves. Good FF means low response delay at the same P.

### Cascade: angle → rate
The outer loop (angle) computes the desired angular rate from the angle error; the inner loop (rate) tracks it. The rule: the inner loop must be 3–10 times faster than the outer one (in bandwidth), otherwise the outer loop “sees” the dynamics of the inner one and the cascade oscillates. In ArduPilot: `ATC_ANG_RLL_P` (outer, ~4.5–12) and `ATC_RAT_RLL_P/I/D` (inner); on top of that, the position loop (`PSC_*`) is slower still. In Betaflight angle mode: `angle_p_gain` (default 50) on top of the rate PID. In PX4: `MC_ROLL_P` → `MC_ROLLRATE_P/I/D`. Autotune tunes the inner loop first, then the outer one — for the same reason.

### What this means for tuning
1. First reduce the delay (mechanics, filters), then raise P.
2. P — until ringing starts, then back off by 20–30% (phase margin).
3. D — until bounce-back is < 10% and the motors don't heat up.
4. I — until the drift disappears, without “wandering.”
5. The outer loop — after the inner one.

Where the total delay T_d comes from and which link weighs the most — compute it for your own setup:

{{widget:link-latency}}

{{diagram:angle-rate-cascade|The “angle → angular rate” cascade: the outer P on angle sets the setpoint for the inner PID on the gyro.}}

{{diagram:chart-step-responses|Step response of a second-order system: ζ = 0.7 gives ~5 % overshoot and fast settling — the target for the rate loop; ζ = 0.3 rings, ζ = 1 is sluggish.}}

## practice
### Step 1. Simulator: the P limit at two delays
In the interactive PID simulator (the “PID Controller in Betaflight” module): with a 2 ms delay, raise P until sustained oscillations start, and write down P_max and the frequency; with a 5 ms delay, repeat. Expected: P_max is noticeably lower, and the oscillation frequency is lower.

### Step 2. ζ from overshoot
From the log (`data-python` → `step_metrics`): overshoot → ζ via the formula; settling time → ωₙ. Compare two axes.

### Step 3. Bounce-back ↔ D
Take logs before/after changing D by 20%: the median bounce-back and the motor noise. Explain them through ζ and delay.

### Step 4. Cascade
ArduPilot SITL: raise `ATC_ANG_RLL_P` from 4.5 to 15 with a standard rate tune — observe the angle oscillations; explain them by the ratio of the bandwidths.

### Numbers to check yourself
- **ζ from overshoot** (second order): ζ = −ln(OS) / √(π² + ln²(OS)). 10 % overshoot → ζ ≈ 0.59; 25 % → ζ ≈ 0.40. Below 0.4 the response rings, above 0.8 it's sluggish.
- **ωₙ from settling time** (2 %): t_s ≈ 4 / (ζ·ωₙ). Example: t_s = 40 ms with ζ = 0.6 → ωₙ ≈ 4 / (0.6 · 0.04) ≈ 167 rad/s ≈ 27 Hz.
- **Delay versus the P limit** (step 1): as the delay grows, the allowable P drops, and the frequency of the sustained oscillations goes down — at 5 ms it's noticeably lower than at 2 ms. Write down both P_max values and both frequencies: their ratio is what each millisecond of filter delay “costs.”

### What you should get and what to record
- **Step 2:** a table per axis — overshoot, t_s, ζ, ωₙ. The axis with the lower ζ is a candidate for more D or less P.
- **Step 3:** +20 % D usually reduces bounce-back (higher damping) but raises motor noise. Record both quantities: the decision is a trade-off, not “more D is always better.”
- **Step 4:** with `ATC_ANG_RLL_P = 15` the outer angle loop becomes too fast relative to the inner rate loop, and the vehicle oscillates in angle. The default of 4.5 keeps the cascade bandwidths separated. Record the oscillation frequency from the `ATT` log.

The lab counts as done when P_max and the oscillation frequency are found in the simulator at two delays, ζ and ωₙ are computed from the log for two axes, the link between bounce-back and damping is explained with logs before and after the D change, and the report fits on one page.

## diagnostics
- **Symptom:** fast oscillations (20–60 Hz) when raising P
  - Possible cause: the phase margin is used up because of delay.
  - What to do: reduce the delay (filters/mechanics) or P.
- **Symptom:** slow oscillations at 0.5–3 Hz
  - Possible cause: I too high, or the outer loop faster than allowed.
  - What to do: reduce I / ANG_P, check for windup.
- **Symptom:** bounce-back despite a good response
  - Possible cause: low ζ — too little D or too much delay in the D filters.
  - What to do: raise D, raise the D-LPF, check the noise.
- **Symptom:** overshoot only on sharp stick moves
  - Possible cause: too much FF.
  - What to do: reduce FF / smooth FF.
- **Symptom:** autotune produced a strange outer loop
  - Possible cause: the inner loop wasn't tuned before it.
  - What to do: rate first, then angle.

## references
- ArduPilot — Tuning Process Instructions (rate → angle, filters first) | https://ardupilot.org/copter/docs/tuning-process-instructions.html | primary | A
- PX4 — Multicopter PID Tuning Guide (cascaded controllers) | https://docs.px4.io/main/en/config_mc/pid_tuning_guide_multicopter.html | primary | A
- Betaflight — PID Tuning Guide | https://betaflight.com/docs/wiki/guides/current/PID-Tuning-Guide | primary | A

## checklist
- I can explain the phase margin and how delay eats it
- I linked overshoot and bounce-back to the damping ζ
- I found the P limit at two delays in the simulator
- I understand why the inner loop must be faster than the outer one
- I know the tuning order: delay → P → D → I → outer loop
