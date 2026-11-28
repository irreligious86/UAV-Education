---
id: ctl-theory
title: "Control theory: stability, margins, cascades"
level: L3
readingTime: 40 min
firmware: any firmware (names checked against ArduPilot 4.7.3, PX4 v1.18.0, Betaflight 2025.12.5)
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
source_hash: 196319d45252
---

## summary
PID tuning without theory is trial and error. This module explains, at a level sufficient for an engineer, what closed-loop stability is, why delay eats phase margin and leads to oscillations at high P, how the step response relates to poles and damping (and why bounce-back is an underdamped pole), and why the autopilot builds an angle → angular rate cascade with an inner loop several times faster than the outer one. The formulas are minimal, and each is tied to what you see in the PID simulator and in the log.

## theory
### Plant, controller, loop
The plant is the vehicle: its input is the motor command, its output the angular rate. The controller is a PID: its input is the error (setpoint − gyro), its output the command. A closed loop: the output affects the input through the measurement. The whole point of the theory is to predict the loop's behavior without closing it.

### A first approximation of one axis
Motor torque produces angular acceleration: J·ω̇ = M − b·ω, where J is the moment of inertia and b the aerodynamic damping. The transfer function from torque to ω is a first-order lag 1/(J·s + b), a "leaky integrator": ω grows while torque is applied. On top of that come **delays**: the motor (current/RPM, τ ≈ 10–30 ms for a 5"), the gyro and D filters (1–5 ms), the control loop period and the ESC protocol (0.1–0.5 ms). The total pure delay T_d is the main enemy.

### Stability and phase margin
A loop with a P controller: sluggish at low P, oscillating at high P, diverging at even higher P. The boundary is where the open-loop gain (loop gain) equals 1 at the frequency at which the phase shift reaches −180°. A pure delay T_d gives a phase shift of −360°·f·T_d: at 50 Hz with T_d = 5 ms that is −90°, and the plant pole adds another −90°, which makes −180°. Hence:

- **Phase margin** is how many degrees are left to −180° at the frequency where the gain = 1. 45–60° is a good tune (a little overshoot); 20–30° means ringing and bounce-back; 0 means sustained oscillations.
- The delay T_d eats the margin linearly with frequency: the faster you want the loop (higher P), the more you lose. Doubling the delay at the same P doubles the phase it eats at the crossover frequency (−360°·f_c·T_d): if the delay already took 45° of a 90° budget, nothing is left.
- Hence the limit "P no higher than the delay allows." Reducing the delay (higher filter cutoffs, an RPM notch instead of a wide LPF, a fast ESC protocol, light props) is the only way to raise P without oscillations.

### Step response, poles, damping
A second-order closed loop is described by its natural frequency ωₙ and damping ratio ζ:
- ζ > 1: overdamped, slow;
- ζ ≈ 0.7: fast with ~5% overshoot; this is the target;
- ζ = 0.4: ~25% overshoot, ringing;
- ζ → 0: oscillations.

**Overshoot ≈ exp(−π·ζ/√(1−ζ²))**: 0.7 → 4.6%, 0.5 → 16%, 0.3 → 37%. Settling time ≈ 4/(ζ·ωₙ). Bounce-back after the stick stops is the same underdamped pole, only excited by a "downward" step: large bounce-back = low ζ = either too little D or too much P/delay. The D-term raises the damping (ζ), which is why "more D" removes the bounce, but D amplifies noise ∝ frequency, and the D filters add delay, which lowers the margin again. That is the tuning trade-off.

### I-term: steady-state error and windup
I removes steady-state error (wind, asymmetry). It pays in phase: an integrator gives −90° at low frequencies, so too much I causes slow oscillations (0.5–3 Hz, "wandering"). Windup is I accumulating while the outputs are saturated (stick at the end stop, motors at the ceiling): the firmware limits it (in Betaflight 2025.12, `iterm_windup` and `iterm_relax`; `iterm_limit` existed up to and including 4.5; in ArduPilot, `ATC_RAT_*_IMAX`).

### Feedforward
FF feeds a command proportional to the derivative of the setpoint, bypassing the error: the output starts moving before the error builds up. It does not affect stability (it is outside the loop), but too much of it gives overshoot on sharp stick moves. Good FF means a short response delay at the same P.

### Cascade: angle → rate
The outer (angle) loop computes the desired angular rate from the angle error; the inner (rate) loop tracks it. The rule: the inner loop must be 3–10 times faster than the outer one (in bandwidth), otherwise the outer loop "sees" the inner loop's dynamics and the cascade oscillates. In ArduPilot: `ATC_ANG_RLL_P` (outer, ~4.5–12) and `ATC_RAT_RLL_P/I/D` (inner); above them the position loop (`PSC_*`), slower still. In Betaflight angle mode: `angle_p_gain` (default 50) on top of the rate PID. In PX4: `MC_ROLL_P` → `MC_ROLLRATE_P/I/D`. Autotune tunes the inner loop first, then the outer one, for the same reason.

### What this means for tuning
1. First reduce the delay (mechanics, filters), then raise P.
2. P until ringing starts, then back off 20–30% (phase margin).
3. D until bounce-back is < 10% and the motors do not get hot.
4. I until the drift is gone, without "wandering."
5. The outer loop after the inner one.

Where the total delay T_d comes from and which link weighs the most: compute it for your own setup:

{{widget:link-latency}}

{{diagram:angle-rate-cascade|The angle → angular rate cascade: an outer P on angle sets the setpoint for the inner PID on the gyro.}}

{{diagram:chart-step-responses|Step response of a second-order system: ζ = 0.7 gives ~5 % overshoot and fast settling, the target for the rate loop; ζ = 0.3 rings, ζ = 1 is sluggish.}}

### Where it fits

- **Takes in:** the delays of the chain: the motor and ESC protocol (`f-motors-esc`), the gyro and D filters (`bf-filters`); the vehicle's moment of inertia (`f-mechanics`); poles and damping as a tool (`math-ode-dyn`).
- **Hands off:** the order "delay first, then P" and the target ζ ≈ 0.7 to tuning (`bf-pid`, `ap-tuning`, `px4-control`); the phase margin under delay to the camera tracking loop (`per-tracking`).
- **If you get this wrong:** you raised P without reducing the delay → a phase margin of 20–30° → ringing and bounce-back that you can measure in the log (`data-python`). The outer loop is not 3–10 times slower than the inner one → the cascade oscillates, and the wobble in angle mode is mistakenly treated through the rate PID (`px4-control`).

## practice
### Step 1. Simulator: the P limit at two delays
In the interactive PID simulator (the "PID controller in Betaflight" module): with a 2 ms delay, raise P until sustained oscillations start, and record P_max and the frequency; repeat with a 5 ms delay. Expected: P_max is noticeably lower, and so is the oscillation frequency.

### Step 2. ζ from overshoot
From the log (`data-python` → `step_metrics`): overshoot → ζ by the formula; settling time → ωₙ. Compare two axes.

### Step 3. Bounce-back ↔ D
Take logs before/after changing D by 20%: the median bounce-back and the motor noise. Explain it through ζ and delay.

### Step 4. Cascade
ArduPilot SITL: raise `ATC_ANG_RLL_P` from 4.5 to 15 (deliberately above the documented 3–12 range) with a stock rate tune and watch the angle oscillate; explain it through the ratio of bandwidths.

### Numbers for self-check
- **ζ from overshoot** (second order): ζ = −ln(OS) / √(π² + ln²(OS)). 10 % overshoot → ζ ≈ 0.59; 25 % → ζ ≈ 0.40. Below 0.4 the response rings, above 0.8 it is sluggish.
- **ωₙ from settling time** (2 %): t_s ≈ 4 / (ζ·ωₙ). Example: t_s = 40 ms at ζ = 0.6 → ωₙ ≈ 4 / (0.6 · 0.04) ≈ 167 rad/s ≈ 27 Hz.
- **Delay versus the P limit** (step 1): as the delay grows, the allowable P falls and the frequency of the sustained oscillations drops; at 5 ms it is noticeably lower than at 2 ms. Write down both P_max values and both frequencies: their ratio is what each millisecond of filter delay "costs."

### What you should get and what to record
- **Step 2:** a table per axis: overshoot, t_s, ζ, ωₙ. The axis with the lower ζ is a candidate for more D or less P.
- **Step 3:** +20 % D usually lowers the bounce-back (more damping) but raises the motor noise. Record both: the decision is a trade-off, not "more D is always better."
- **Step 4:** with `ATC_ANG_RLL_P = 15` (above the documented 3–12 range, on purpose) the outer angle loop becomes too fast relative to the inner rate loop, and the vehicle oscillates in angle. The default of 4.5 keeps the cascade bandwidths apart. Record the oscillation frequency from the `ATT` log.

Self-check: the lab is done when P_max and the oscillation frequency are found in the simulator at delays of 2 and 5 ms and both numbers are lower at 5 ms, ζ and ωₙ are computed from the log for two axes, your formulas on the self-check numbers give the same ζ ≈ 0.59 at 10 % overshoot and ωₙ ≈ 167 rad/s at t_s = 40 ms and ζ = 0.6, the median bounce-back and motor noise are recorded before and after the 20 % D change, the oscillation frequency at `ATC_ANG_RLL_P = 15` is taken from `ATT`, and your notes with all the numbers fit on one page.

**Reference answer for self-check.** The correct explanation of step 3: +20 % D gives more damping, lower bounce-back, higher motor noise; the decision is a trade-off. Of step 4: the outer angle loop became too fast relative to the inner rate loop, and the cascade bandwidths are no longer separated. Typical wrong results: (1) at 5 ms P_max came out no lower than at 2 ms: P_max was not taken at the onset of sustained oscillations; (2) an axis has ζ below 0.4 while your notes say "axis is fine": such a response rings, and it is a candidate for more D or less P.

## diagnostics
- **Symptom:** fast oscillations (20–60 Hz) when raising P
  - Possible cause: the phase margin is used up because of delay.
  - What to do: reduce the delay (filters/mechanics) or P.
- **Symptom:** slow oscillations at 0.5–3 Hz
  - Possible cause: too much I, or the outer loop faster than allowable.
  - What to do: lower I / ANG_P, check for windup.
- **Symptom:** bounce-back with an otherwise good response
  - Possible cause: low ζ: too little D or too much delay in the D filters.
  - What to do: raise D, raise the D LPF, check the noise.
- **Symptom:** overshoot only on sharp stick moves
  - Possible cause: too much FF.
  - What to do: lower FF / smooth FF.
- **Symptom:** autotune produced a strange outer loop
  - Possible cause: the inner loop was not tuned before it.
  - What to do: rate first, then angle.

## references
- ArduPilot — Tuning Process Instructions (rate → angle, filters first) | https://ardupilot.org/copter/docs/tuning-process-instructions.html | primary | A
- PX4 — Multicopter PID Tuning Guide (cascaded controllers) | https://docs.px4.io/v1.17/en/config_mc/pid_tuning_guide_multicopter.html | primary | A
- Betaflight — PID Tuning Guide | https://betaflight.com/docs/wiki/guides/current/PID-Tuning-Guide | primary | A

## checklist
- I can explain phase margin and how delay eats it
- I have linked overshoot and bounce-back to the damping ratio ζ
- I have found the P limit at two delays in the simulator
- I understand why the inner loop must be faster than the outer one
- I know the tuning order: delay → P → D → I → outer loop
