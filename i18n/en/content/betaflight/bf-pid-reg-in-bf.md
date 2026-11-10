---
id: bf-pid-reg-in-bf
title: "PID Tuning in Betaflight"
level: L2
readingTime: 25 min
firmware: Betaflight 4.5+
status: published
tags:
  - PID
  - tuning
  - Betaflight
  - Blackbox
references:
  - title: "Betaflight PID Tuning Guide"
    url: "https://betaflight.com/docs/wiki/guides/current/PID-Tuning-Guide"
    tier: primary
    stack: betaflight
  - title: "Betaflight DShot RPM Filtering"
    url: "https://betaflight.com/docs/wiki/guides/current/DSHOT-RPM-Filtering"
    tier: primary
    stack: betaflight
related:
  - bf-filters
  - bf-blackbox
next:
  - bf-cli
source: content/betaflight/bf-pid-reg-in-bf.md
source_hash: afbfb4abd3e9
---

## summary

The PID controller is the core of stabilization in Betaflight. This article explains the physical meaning of the P, I, D coefficients, how they interact, how they affect the drone's behavior, and how to tune them using Blackbox. After studying it, you will be able to diagnose typical problems (oscillations, bounce-back, motor overheating) and adjust parameters deliberately instead of guessing at random.

## theory

The PID controller (Proportional-Integral-Derivative) gets the angular rate on the roll, pitch, yaw axes from the gyro and minimizes the error between the desired rate (setpoint, from the sticks or navigation) and the current rotation rate. The controller output (PID sum) is converted into motor signals by the mixer.

**P-term (proportional)** reacts to the current error: the bigger the error, the stronger the correction. It defines the drone's basic stiffness. Drawback: it cannot fully eliminate steady-state error (drift). Too high, and it causes fast oscillations (20–50 Hz).

**I-term (integral)** accumulates error over time, eliminating a constant offset (drift from wind, a shifted center of mass). It works slower than P. Too high, and it causes slow floaty oscillations (1–5 Hz) and wind-up. The `iterm_limit` parameter (in 2025.12 — `iterm_windup`) limits the maximum I-term value.

**D-term (derivative)** reacts to the rate of change of the error, acting as a damper. It suppresses oscillations caused by the P-term. It is critically sensitive to gyro noise. Without filtering it produces high-frequency noise that overheats the motors. The rule: D-term is tuned after P-term; raising P requires raising D.

**Betaflight 4.5+ specifics:**

- **Feedforward** — an independent control path that feeds a signal straight to the motors based on how fast the stick moves. It speeds up the response without raising the P-term.
- **TPA (Throttle PID Attenuation)** — reduces the PID coefficients at high throttle. In BF 4.5+ the default is `tpa_mode = D` (reduces only the D-term); `PD` is also available.
- **RPM Filtering** — uses data from the ESC to suppress noise from the propellers. It creates narrow filters at the motors' rotation frequency, letting you raise the D-term.

### The formula as implemented in `flight/pid.c`
For each axis on every loop (at the PID rate): error e = setpoint − gyro (filtered);
- P = Kp·e;
- I += Ki·e·dt, limited by `iterm_limit` (anti-windup) and by “relax” (below);
- D = −Kd·d(gyro_D)/dt — the derivative **of the gyro**, not of the error (stick movement doesn't kick D), after the D filters (the “Filters” module), with a multiplier from the `d_min` logic;
- FF = Kff·d(setpoint)/dt with averaging/smoothing (`feedforward_averaging`, `feedforward_smooth_factor`, `feedforward_jitter_factor`, `feedforward_boost` — an addition from the second derivative, `feedforward_max_rate_limit`);
- sum → TPA → `pidSum` → mixer.
The coefficients from the configurator (“45”) are multiplied by the scale factors in `pid_init.c` (P ≈ 0.032, I ≈ 0.244, D ≈ 0.00053, FF ≈ 0.0138) — that's Betaflight's “dimensionlessness”; the physical meaning can be recovered only through the response (the “Control theory” module).

### Mechanisms you won't find in a PID textbook
- **I-term relax** (`iterm_relax = RP`, `iterm_relax_type = SETPOINT`, `iterm_relax_cutoff = 15`): during fast stick movements I accumulation is paused — otherwise after a flip I “carries” extra rotation (one of the kinds of bounce-back). Lower cutoff → more aggressive relax.
- **I-term rotation** (`iterm_rotation`): when rotating in yaw, the accumulated roll/pitch I is rotated together with the frame.
- **Anti-gravity** (`anti_gravity_gain`, `anti_gravity_p_gain`, `anti_gravity_cutoff_hz`): temporarily raises I (and P) on sharp throttle changes — against the “nose dip” when you punch the throttle.
- **D_min / D_max** (4.5: `d_min_*` — base, `d_*` — peak; 2025.12: `d_*` — base, `d_max_*` — peak; plus `d_max_gain`, `d_max_advance`): D is low in calm flight (less noise/heat) and rises on fast moves and propwash, based on gyro/setpoint.
- **TPA** (`tpa_mode = D` by default in 4.5, `tpa_rate`, `tpa_breakpoint`; 4.5+ also has `tpa_low_*` for low throttle): reduces D (or PD) above a throttle point — at high throttle thrust is more linear and noise is higher.
- **Thrust linearization** (`thrust_linear`) and **throttle boost**: compensation for the nonlinearity of thrust vs. throttle and a short-term boost of the throttle response.
- **Air mode**: PID works even at zero throttle (`feature AIRMODE` or the AIR MODE mode), with a minimum idle (`dshot_idle_value`; in 2025.12 — `motor_idle`) — otherwise the aircraft is uncontrollable when descending with no throttle.

### Worked example: where bounce-back comes from
Log: after a sharp roll stick stop the gyro overshoots to −18% of the maneuver amplitude. Check in order: (1) the D filters are not too low (delay) — `dterm_lpf1_dyn_max_hz` 150 → ok; (2) enough D? Damping slider 1.0 → 1.15 — bounce-back 18 → 11%, motors warm; (3) I-relax on (`iterm_relax = RP`) — yes; (4) mechanics — the spectrum is clean. Result: Damping 1.15, entry in the decision table. If the motors had been heating up, the path would be the opposite: filters/mechanics, not D.

{{diagram:bf-pid-terms|PID in Betaflight: P and I from the error, D from the gyro (with d_min), FF from the setpoint derivative; it all adds up into pidSum.}}

## practice

{{widget:pid-sim}}


**Preparation**

Hardware requirements: ESC with RPM Filtering support (BLHeli_32 or Bluejay), F7/H7 flight controller, SD card for Blackbox (at least 4 GB).

Software requirements: Betaflight Configurator 10.10+, Blackbox Explorer.

**Setup before tuning**

1. Enable RPM Filtering: in the Motors tab turn on **Bidirectional DShot** and set Motor poles (the RPM filter enables itself); `rpm_filter_q = 500` is the default value (CLI).
2. Set up Blackbox: choose a 2 kHz logging rate, enable logging of gyro_scaled, pid, setpoint, motor.
3. Set the baseline filtering parameters:
set gyro_lpf2_static_hz = 300
set gyro_lpf2_type = PT2
set dterm_lpf2_static_hz = 150
set dterm_lpf2_type = PT2
set dyn_notch_max_hz = 600
set dyn_notch_q = 250
save

text

**Step-by-step tuning**

1. Determine the starting values (for a 5" frame with 2207–2306 motors):
set p_pitch = 45\nset i_pitch = 50\nset d_pitch = 25
set p_roll = 42, i_roll = 45, d_roll = 23
set p_yaw = 70, i_yaw = 50, d_yaw = 20
set d_min_roll = 20\nset d_min_pitch = 22\n# 2025.12: d_roll/d_pitch — base D, d_max_roll/d_max_pitch — peak
save

text

2. P-term tuning: do a sharp stick snap and return. In Blackbox look at the gyro trace (blue) and setpoint (green). If gyro crosses setpoint in the opposite direction (bounce-back) — P is low, raise it by 10. If gyro oscillates around setpoint — P is high, lower it by 5.

3. D-term tuning: after tuning P, do the same move. Add the D-term trace. If the D-term trembles with high-frequency noise — lower D by 3–5. If after the move gyro shows decaying oscillations — raise D by 3.

4. I-term tuning: hover in Angle/Horizon mode, tilt the drone slightly and return to zero. If the drone drifts slowly — raise I by 10. If it overshoots neutral and starts swinging — lower I by 10.

5. Feedforward tuning: do a series of fast stick moves. In Blackbox compare setpoint and gyro. With a large lag, raise `feedforward_boost`. With overshoot, lower `feedforward_boost`.

6. TPA tuning: do a punch-out (20% → 80% throttle). If motor goes to 100% without being reduced — check `tpa_rate`. With high-frequency pulsing, raise `tpa_rate` (percent, 0–100; default 65) to 70–80 and lower `tpa_breakpoint` to 1400.

**Final steps**

Save the final parameters: `diff all`. Do a short flight (2–3 minutes) and check the motor temperature. If the motors are hot, lower the D-term by 10–15%.

## diagnostics

- **Symptom: Fast oscillations in hover (buzzing, shaking)**
- Possible cause: P-term too high, insufficient gyro filtering.
- What to do (check first): record Blackbox. If the gyro trace has frequent 50–100 Hz peaks — lower P by 20%. Check that the dynamic notch and RPM filtering are working.

- **Symptom: Bounce-back after a sharp move**
- Possible cause: P-term too low, D-term too high.
- What to do (check first): in Blackbox compare setpoint and gyro: gyro doesn't reach setpoint. Raise P by 10%. If bounce-back doesn't go away — check the D-term.

- **Symptom: Slow floaty oscillations (~1–3 Hz)**
- Possible cause: I-term too high, wrong anti-windup.
- What to do (check first): lower I by 15–20%. Check `iterm_limit` (default 400; in 2025.12 — `iterm_windup`).

- **Symptom: Motor overheating**
- Possible cause: D-term too high, insufficient D-term filtering.
- What to do (check first): in Blackbox look at the D-term trace — if it looks like noise, lower D by 20–30%. Lower `dterm_lpf2_static_hz` to 100–120 Hz.

- **Symptom: The drone wanders off on a sharp throttle punch (punch-out)**
- Possible cause: wrong TPA setup, high P/D without attenuation.
- What to do (check first): in Blackbox find the punch-out on the throttle trace. If PID sum is clipping — raise `tpa_rate` or lower `tpa_breakpoint`.

- **Symptom: Gyro noise in the logs (sawtooth trace)**
- Possible cause: mechanical vibration, RPM Filtering not working.
- What to do (check first): check that RPM Filtering works (the Motors tab should show the rotation frequency). Lower `gyro_lpf2_static_hz` to 250–300 Hz.
- **Symptom:** the aircraft “dips” its nose after a throttle punch
  - Possible cause: I can't keep up, anti-gravity too low.
  - What to do: raise `anti_gravity_gain`, check `thrust_linear`.
- **Symptom:** I-term shows up in the log as a rise after a flip and a “carry-through”
  - Possible cause: I-term relax is off or the cutoff is high.
  - What to do: `iterm_relax = RP`, cutoff 10–15.

## references

- Betaflight PID Tuning Guide | https://betaflight.com/docs/wiki/guides/current/PID-Tuning-Guide | primary | A
- Betaflight DShot RPM Filtering | https://betaflight.com/docs/wiki/guides/current/DSHOT-RPM-Filtering | primary | A
- Betaflight Blackbox logging and usage | https://betaflight.com/docs/wiki/guides/current/Black-Box-logging-and-usage | primary | A
- Oscar Liang: Betaflight PID Tuning | https://oscarliang.com/betaflight-pid-tuning/ | secondary | B
- Joshua Bardwell: How to Tune PID with Blackbox | https://www.youtube.com/watch?v=YXpPajW9lCU | secondary | B
