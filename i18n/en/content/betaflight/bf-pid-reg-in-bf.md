---
id: bf-pid-reg-in-bf
title: "PID tuning in Betaflight"
level: L2
readingTime: 40 min
firmware: Betaflight 2025.12 (checked against 2025.12.5)
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
  - bf-rpm-filter
  - bf-rates-rc
  - bf-tuning-method
  - bf-features-tour
next:
  - bf-cli
source: content/betaflight/bf-pid-reg-in-bf.md
source_hash: e69d91cbd6cd
---

## summary

The PID controller is the core of stabilization in Betaflight. This article explains the physical meaning of the P, I and D gains, how they interact, how they affect the behavior of the drone, and how to tune them using Blackbox. After working through it the reader will be able to diagnose the typical problems (oscillations, bounce-back, overheating motors) and adjust the parameters purposefully instead of by trial and error. A separate block covers the throttle path in the mixer — dynamic idle, `thrust_linear`, `vbat_sag_compensation`, TPA, anti-gravity and throttle boost — with formulas from the source code and a calculation lab.

## theory

The PID (Proportional-Integral-Derivative) controller receives the angular rate on the roll, pitch and yaw axes from the gyro and minimizes the error between the desired rate (the setpoint, from the sticks or from navigation) and the current rate of rotation. The controller output (the PID sum) is converted by the mixer into the motor signals.

**P term (proportional)** reacts to the current error: the larger the error, the stronger the correction. It sets the basic stiffness of the drone. Its weakness: it cannot fully remove a steady-state error (drift). When too high it causes fast oscillations (tens of Hz; on a 5" roughly 30–80 Hz — a course estimate).

**I term (integral)** accumulates the error over time and removes a constant offset (drift from wind, an offset center of mass). It works more slowly than P. When too high it causes slow, wandering oscillations (1–5 Hz) and windup. In 2025.12 this is handled by `iterm_windup` (80 by default, range 20–100): it sets the I limit as a percentage of `pidsum_limit`. In 4.5 there were two variables and the meaning was different: `iterm_windup` (85 by default, %) reduced I accumulation as the motors approached saturation (a spread of motor commands above 85%), and `iterm_limit` (400 by default) was the absolute I-term limit. `iterm_limit` was removed in 2025.12; this is not a rename.

**D term (derivative)** reacts to the rate of change of the error and acts as a damper. It suppresses the oscillations caused by the P term. It is critically sensitive to gyro noise. Without filtering it produces high-frequency noise that overheats the motors. The rule: the D term is tuned after the P term; raising P requires raising D.

**Betaflight specifics (4.5 and 2025.12):**

- **Feedforward** — an independent control path that drives the motors directly from the speed of stick movement. It speeds up the response without raising the P term.
- **TPA (Throttle PID Attenuation)** — a reduction of the PID gains at high throttle. By default `tpa_mode = D` (only the D term is reduced); `PD` is also available, and from 2025.12 a WING build adds `PDS` (together with the S term; it does not exist on a multirotor).
- **RPM Filtering** — the use of data from the ESCs to suppress propeller noise. It places narrow filters at the motor rotation frequency, which allows a higher D term.

### The formula as implemented in `flight/pid.c`
For every axis in every loop (at the PID frequency): the error e = setpoint − gyro (filtered);
- P = Kp·e;
- I += Ki·e·dt with the `iterm_windup` limit (% of `pidsum_limit`; anti-windup) and “relax” (below); in 4.5 — a reduction of Ki by `iterm_windup` on motor saturation and a separate `iterm_limit`;
- D = −Kd·d(gyro_D)/dt — the derivative **of the gyro**, not of the error (stick movement produces no derivative kick), after the D filters (the “Filters” module), with the multiplier of the D max logic (before 2025.12 — `d_min`);
- FF = Kff·d(setpoint)/dt with averaging/smoothing (`feedforward_averaging`, `feedforward_smooth_factor`, `feedforward_jitter_factor`, `feedforward_boost` — an addition from the second derivative, `feedforward_max_rate_limit`);
- the sum → TPA → `pidSum` → the mixer.
The gains from the configurator (“45”) are multiplied by the scale factors in `pid_init.c` (P ≈ 0.032, I ≈ 0.244, D ≈ 0.00053, FF ≈ 0.0138) — this is the “dimensionlessness” of Betaflight; the physical meaning is recovered only through the response (the “Control theory” module). For FF the number from the configurator is additionally divided by 100: Kff = 0.0138 · `f_*` / 100 (`pidInitConfig()` in `flight/pid_init.c`, 2025.12.5; the same in 4.5).

### Mechanisms that are not in a PID textbook
- **I-term relax** (`iterm_relax = RP`, `iterm_relax_type = SETPOINT`, `iterm_relax_cutoff = 15`): during fast stick movements I accumulation is suspended — otherwise after a flip the I term adds extra rotation (one of the kinds of bounce-back). A lower cutoff → more aggressive relax.
- **I-term rotation** (`iterm_rotation`): during yaw rotation the accumulated roll/pitch I terms are rotated together with the frame.
- **Anti-gravity** (`anti_gravity_gain`, `anti_gravity_p_gain`, `anti_gravity_cutoff_hz`): temporarily boosts I (and P) on sharp throttle changes — against the nose dip on a throttle punch.
- **D max** (`d_*` — the base, `d_max_*` — the peak, plus `d_max_gain`, `d_max_advance`; in 4.5 it is the other way around: `d_min_*` — the base, `d_*` — the peak): D is low in calm flight (less noise/heat) and rises on fast movements and propwash, driven by the gyro/setpoint.
- **TPA** (`tpa_mode = D` by default, `tpa_rate`, `tpa_breakpoint`; from 4.5 there is also `tpa_low_*` for low throttle): reduces D (or PD) above a throttle point — at high throttle the thrust per unit of command (the loop gain) and the noise both grow.
- **Thrust linearization** (`thrust_linear`) and **throttle boost**: compensation for the nonlinearity of thrust versus throttle, and a short-term boost of the throttle response.
- **Air mode**: PID works at zero throttle as well (`feature AIRMODE` or the AIR MODE mode), with a minimum idle (`motor_idle`; before 2025.12 — `dshot_idle_value`) — otherwise in a zero-throttle descent the aircraft is uncontrollable.

### A worked example: where bounce-back comes from
A log: after a sharp stick stop in roll the gyro goes to −18% of the maneuver amplitude. Check in order: (1) the D filters are not too low (delay) — `dterm_lpf1_dyn_max_hz` 150 → OK; (2) is there enough D? the Damping slider 1.0 → 1.15 — bounce-back 18 → 11%, the motors are warm; (3) I-term relax is on (`iterm_relax = RP`) — yes; (4) the mechanics — the spectrum is clean. The result: Damping 1.15, an entry in the decision table. If the motors were running hot, the path would be the opposite: filters/mechanics, not D.

{{diagram:bf-pid-terms|PID in Betaflight: P and I from the error, D from the gyro (with D max), FF from the derivative of the setpoint; everything adds up to pidSum.}}

### The throttle path: what the mixer does with the throttle before the motors
In Betaflight the throttle does not go straight from the stick to the ESC. In 4.5.3 the functions `mixTable()` and `calculateThrottleAndCurrentMotorEndpoints()` (`flight/mixer.c`) take it through six main stages. Besides these there is the airmode throttle shift in `applyMixerAdjustment()`, the throttle overrides for yaw spin and GPS Rescue (`mixer.c:712–729`) and the RPM limiter (`mixer.c:682–686`). Almost all of their settings are PID-profile variables: each of the four profiles (`profile` in the CLI) has its own values. The references below are to the 4.5.3 source, and the 2025.12.5 differences are given on a separate line.

1. The throttle is converted to a fraction: `t = (rcCommand − 1000)/1000` plus the throttle angle correction (`mixer.c:219, 266`), then `throttle_limit` (`mixer.c:643–646`).
2. The anti-gravity filter and the TPA factor are computed from this t (`mixer.c:649, 652`). Throttle boost and dynamic idle do not affect them.
3. Throttle boost (`mixer.c:659–664`), after which the throttle is written to Blackbox (`mixer.c:668`).
4. With dynamic idle the throttle does not go below 1 % (`mixer.c:671–674`), and the `thrust_linear` compensation slightly reduces the throttle (`mixer.c:679`).
5. The PID correction for each motor is added to the throttle, and the throttle may be shifted by `applyMixerAdjustment()` (airmode); `thrust_linear` acts on the sum x (`mixer.c:398`).
6. x is converted to a DShot command inside the window from the lower to the upper limit. The lower limit is raised by dynamic idle, and the upper one is cut by `vbat_sag_compensation` (`mixer.c:245–262`).

All the numbers below come from the lab of this module: Python repeats the firmware formulas line by line, and the output is pasted into “Exercise 2”.

### Dynamic idle: an RPM controller, not an “idle throttle”
Without dynamic idle the lower limit is set by the static idle `dshot_idle_value` = 550, that is, 5.5 % of the range: 48 + 0.055 · 1999 = 157.9 in DShot units (`drivers/dshot.c:68`). Nothing controls the RPM in that case.

Dynamic idle is enabled in `mixerInitProfile()` (`flight/mixer_init.c:330–345`). If bidirectional DShot is working (`useDshotTelemetry`), the target is `dyn_idle_min_rpm` × 100 / 60 rev/s: 30 → 3000 RPM = 50 rev/s. Without telemetry the target is silently zeroed, and the function is off without any error. The same code resets the lower output limit to `DSHOT_MIN_THROTTLE` = 48 (`mixer_init.c:343`, `drivers/dshot.h:30`). So with dynamic idle enabled `dshot_idle_value` is **not** the floor: the log header will show `motorOutput:48,2047` instead of `158,2047` (`bf-motor-balance`). In 3D mode dynamic idle does not work at all: the controller is in the non-3D branch (`mixer.c:218–243`), and the floor is not reset.

In every PID loop (`mixer.c:221–243`) the controller takes four steps:
- it takes the lowest rotation frequency among the motors (`getMinMotorFrequencyHz()`, `drivers/dshot.c:330–335`; this is the rotation frequency in rev/s, eRPM · 100 / 60 / (`motor_poles`/2), passed through a PT1 with a cutoff of `rpm_filter_lpf_hz` = 150 Hz);
- it computes P = error · `dyn_idle_p_gain` · 0.00015 and I += error · `dyn_idle_i_gain` · 0.01 · dT. For I a negative error is limited to −0.1 rev/s: the increase grows quickly and decays slowly;
- it computes D from the RPM smoothed over about 20 ms, with the coefficient `dyn_idle_d_gain` · 3·10⁻⁷ · f_PID;
- it limits the sum P + I + D to the range from 0 to the limit and raises the lower limit: low = 48 + increase · (high − 48).

The limit of the increase depends on airmode. After the throttle has first passed `airmode_start_throttle_percent` (25 %, `fc/core.c:781–785`) following an arm, the limit is `dyn_idle_max_increase`/1000, that is, 15 %. Before that, on the ground, 4.5.3 applies `dyn_idle_start_increase`/1000 = 5 %. In 4.5.3 the switch goes through `isAirmodeActivated()` (`fc/core.c:781–788`), which latches only if airmode is enabled: without airmode the limit stays at 5 % for the whole flight. In 2025.12 the switch goes through `wasThrottleRaised()` (`mixer.c:231`, `fc/core.c:828–838`): a latch on the throttle threshold after arming, independent of airmode.

An example from the lab (PID at 8 kHz): the target is 50 rev/s, and the slowest motor is 10 rev/s short. P alone gives 7.5 % of the range, and I alone reaches the 15 % limit in 30 ms.

**Why bidirectional DShot is needed.** The controller compares the actual RPM with the target, and only the ESC knows the actual RPM. If `dshot_bidir = ON` but even one ESC has not sent eRPM, arming is blocked by the `DSHOT_TELEM` flag (`fc/core.c:365–370`). The telemetry setup and its diagnostics are in `bf-rpm-filter`.

{{lesson:bf-rpm-filter|Where eRPM comes from, what `Invalid` means in `dshot_telemetry_info`, and why without telemetry at boot dynamic idle and the RPM filter are silently off, while on its loss in flight they freeze at the last RPM.}}

**What it cures and what you pay.** In a flat fall and in a turn from high speed the airflow from below slows the props. With a static idle a motor sags to the desync threshold, and the next maneuver starts with a sluggish motor: hence propwash and jerks at the end of flips. Dynamic idle raises the lower limit of all the motors only when, and only as much as, the slowest of them has sagged. PID can now brake a fast-spinning motor with a command down to zero, not to 5.5 %.

The price:
- dependence on telemetry: without `dshot_bidir` the function is silently off. If eRPM stops arriving in flight, the controller works from the last received RPM (`telemetryData` is updated only by valid packets), and the increase may “freeze”. This is an inference from the code; it was not verified on an aircraft;
- a high target makes the aircraft “floaty”: braking is weaker and inverted hang time is shorter (the Dynamic Idle page in the Betaflight documentation);
- the controller's I may hold extra thrust, and the increase on the ground is limited only by `dyn_idle_start_increase` (`motor_idle` in 2025.12).

The Dynamic Idle page in the betaflight.com documentation (`docs/wiki/guides/current/Dynamic-Idle.md`) advises starting with 30–40 for a 5″, that is, 3000–4000 RPM. For 7–10″ a course guideline: start with the RPM that the motor shows at the static idle in the Motors tab without props, minus 20 %, and then adjust from a `debug_mode = DYN_IDLE` log. Only the idea of an RPM target is borrowed from the 4.2 section of that page; do not apply the `dshot_idle_value` floor from there to 4.3+.

2025.12: the controller formula is the same, but the limit switch is `wasThrottleRaised()` instead of airmode (see above), `dyn_idle_start_increase` is removed, and the limit on the ground is `motor_idle`/10000 (550 → 5.5 %, `mixer_init.c:358`). `dshot_idle_value` itself is renamed to `motor_idle`.

{{lesson:bf-features-tour|There the dynamic idle controller is run on a synthetic motor in a flat fall, and there is a flight check with debug DYN_IDLE.}}

### thrust_linear: more gain at low throttle
The formula (`flight/pid.c:338–342`, k = `thrust_linear`/100, `pid_init.c:392`): **output = x · (1 + k · (1 − x)²)**, where x is the throttle plus the PID correction, as a fraction of the motor range. Prop thrust grows roughly as the square of the RPM, so at low throttle 1 % of command hardly changes the thrust, and PID is “weak” there. Linearization raises the slope at zero to 1 + k (1.2 at 20, 1.4 at 40). At x = 1/3 the slope is 1 again, and above 1/3 it is **less** than 1: at 40 it drops to 0.87 at x = 2/3. This follows directly from the derivative 1 + k(1 − x)(1 − 3x).

So that the hover point does not move, the collective throttle is divided in advance by 1 + (k − k²/2)·(1 − t)² (`pid.c:328–335`, `pid_init.c:393`). The compensation is approximate. With a hover at 0.30 and `thrust_linear` = 40 the throttle after compensation is 0.2593, the output 0.3162 (+5.4 %), and the local slope ≈ 1.07 (for +1 % of correction — 1.06). The conclusion: on a 5″ that hovers at about 30 %, linearization changes almost nothing. It works in the zone x < 0.2: idle, falls, whoops, ESCs with 48–96 kHz PWM (`f-esc-firmware`). The description of the PID Tuning tab in the betaflight.com documentation (`docs/wiki/app/pid-tuning-tab.mdx`) calls 30–40 % a common value.

The price: above a third of the range PID authority is slightly reduced, and the low end of the throttle travel feels different. The motor balance analysis in `bf-motor-balance` assumes `thrust_linear` = 0.

{{diagram:chart-bf-thrust-linear|thrust_linear raises the slope of the command at zero to 1 + k, at x = 1/3 the slope is 1 again, and above that it is slightly below 1: the function is useful at low throttle and hardly touches the hover of a 5″.}}

### vbat_sag_compensation: cuts the top on a full battery
The constants are computed in `mixer_init.c:347–357`:
- the upper point `CELL_VOLTAGE_FULL_CV` = 420, that is, 4.20 V per cell. It is hard-coded (`sensors/battery.h:31`, with a TODO next to it to make it configurable);
- the lower point `vbat_warning_cell_voltage`, 350 by default;
- the range = 420 − 350 = 70;
- the coefficient = `vbat_sag_compensation`/100.

With the RPM limiter enabled the compensation does not work. It works only with the ADC voltage meter (`battery_meter = ADC`): the voltage for the compensation (`sagFiltered`) is filled only by the ADC meter (`sensors/voltage.c:188–191, 212`); with the ESC sensor it is 0, and the cut is 0 as well.

In every loop (`mixer.c:248–256`) the cell voltage under load is taken, smoothed by a PT1 (`getBatterySagCellVoltage()`; `vbat_sag_lpf_period` = 2 gives a 5 Hz cutoff, `sensors/voltage.c:232`):

- goodness = 1 − clamp((4.20 − V) / (4.20 − V_warn), 0, 1);
- cut = (4.20 − V_warn) / 4.20 · goodness · `vbat_sag_compensation`/100;
- high = motor_high − cut · (motor_high − motor_low).

The function adds nothing. It **takes away** the top of the range on a fresh battery, and the higher the voltage, the more. At 100 % and 4.20 V the cut is 16.7 %: 4.20 · 0.833 = 3.50 V, that is, the top behaves like a pack at `vbat_warning`. At 3.85 V the cut is 8.3 %, equivalent to 3.53 V. Below 3.50 V there is no cut. LiHV above 4.20 V is treated as 4.20 V. Hence “the same throttle for the whole flight”: the behavior of the aircraft stays close to a pack at `vbat_warning` all the time.

**Li-Ion.** Under load Li-Ion cells sag to 3.0–3.3 V by the end of a flight (an estimate), so with the default 3.50 V the compensation works only at the start of the flight (3.80 V → 7.1 %) and is zero after that. If `vbat_warning_cell_voltage` is lowered to 3.00 V, the range becomes 120, and the formula gives a cut of 28.6 % on a full pack, 19.0 % at 3.80 V and 7.1 % at 3.30 V. At the start of a flight the aircraft is noticeably weaker in a punch-out. The voltage is taken under load: in a punch-out it sags, and the cut decreases. With Li-Ion cells of high internal resistance this swing is larger, so the top of the range moves with the throttle. These are consequences of the formula; the course has not flight-tested them.

A course guideline for Li-Ion: `vbat_warning_cell_voltage` is set from the cell datasheet for the sake of the alarm, and the compensation is enabled only when you deliberately trade the top end for consistency. The check is `debug_mode = BATTERY`, where channel [2] shows goodness × 100 (`mixer.c:253`).

### TPA: attenuating D (or P and D) at high throttle
The formula (`pid_init.c:427–434`, `pid.c:280–296`), where t is the throttle fraction from step 1 of the path, before throttle boost:
- tbp = (`tpa_breakpoint` − 1000)/1000, no more than 0.99;
- TPA = 1 − `tpa_rate`/100 · max(t − tbp, 0) / (1 − tbp).

From the breakpoint to full throttle the factor falls linearly to 1 − `tpa_rate`/100. With the defaults 65 / 1350 that is 0.85 at 1500 and 0.35 at 2000: a roll D of 30 acts as 10.5 at full throttle. D is always multiplied by TPA (`pid.c:1057`), P — only with `tpa_mode = PD` (`pid.c:797`).

Below `tpa_low_breakpoint` the low-throttle TPA applies: lbp = 0.05 (no higher than tbp), TPA = 1 − `tpa_low_rate`/100 · (lbp − t)/lbp. That is 0.8 at zero and 0.9 at 1025, against D shake on the ground and at takeoff. The flag “the throttle has already passed lbp” is a static variable (`pid.c:282–291`). After the first pass the low-throttle TPA is turned off until a reboot: a disarm and a profile change do not bring it back. The pass also counts before arming: `mixTable()` runs every loop even while disarmed (`fc/core.c:1198`, `mixer.c:652`), so throttle above 1050 on the ground also removes the low-throttle TPA. Changing the pack (a power cycle) brings it back; arming again on the same pack does not. The exception is `tpa_low_always = ON`.

Why TPA at all: as the RPM grows, so do the thrust per unit of command — that is, the open-loop gain — and the noise. A course guideline: touch TPA only if the log shows oscillations exclusively at high throttle. Lower `tpa_breakpoint` first, then raise `tpa_rate`.

2025.12: the classic formula is the same (`getTpaFactorClassic()`). `debug_mode = TPA` was added (the factor × 1000). `tpa_low_rate` became signed: 0–100 on a multirotor, from −128 in a WING build. `tpa_curve_*`, `tpa_speed_*` and the `PDS` mode exist only in a WING build.

{{diagram:chart-bf-tpa-factor|TPA linearly reduces the D factor from tpa_breakpoint to 1 − tpa_rate/100 at full throttle (0.35 at the defaults); the low-throttle TPA (0.8 at zero) acts only until the first pass of 1050 after power-up, including throttle movement before arming.}}

### Anti-gravity and throttle boost
**Anti-gravity** works if `feature ANTI_GRAVITY` is enabled (it is on by default, `config/feature.c:35`) or the ANTI GRAVITY mode is active (`fc/core.c:1089`). The calculation is in `pid.c:298–317`: the throttle derivative |Δt| · f_PID is multiplied by (1 − t)², and on a throttle increase also by 0.5 · (1 − t). This concentrates the function at low throttle. Then comes a PT2 with a cutoff of `anti_gravity_cutoff_hz` = 5 Hz (`pid_init.c:258`) and multiplication by `anti_gravity_gain` = 80 (`pid.c:847`).

The result acts on two terms:
- 0.34 × this value is added to Ki (`itermAccelerator`, `pid.c:849, 992`); it does not act on yaw (`pid.c:989`);
- roll and pitch P is multiplied by 1 + AG · `anti_gravity_p_gain`/100 · 0.0034 and is attenuated when the setpoint is above 50 °/s (`pid.c:1114–1120`).

An example from the lab (PID at 8 kHz): throttle 0.20 → 0.60 in 50 ms gives a peak at which the pitch I grows 1.91 times faster than usual, and P × 1.19 with the sticks centered. It cures the nose dip on a punch-out and a throttle chop: an offset center of mass needs a new I, and it has to be built up faster.

**Throttle boost** (`mixer.c:659–664`): `t += throttle_boost/10 · (t − PT1(t, throttle_boost_cutoff))`. The default is 5 → × 0.5, a 15 Hz cutoff, τ = 10.6 ms. With PID at 8 kHz and the filter settled at 0.30, a throttle step 0.30 → 0.60 gives the motors 0.748 in the first loop, 0.659 after 10 ms and 0.604 after 40 ms. This is a lead that hides the motor spin-up delay. It concerns only the collective throttle: TPA and anti-gravity do not see it.

### Reference table: throttle, idle and related variables
| Variable | Default | Range | Meaning | 4.5.3 → 2025.12 |
|---|---|---|---|---|
| `dyn_idle_min_rpm` | 0 (off) | 0–200, ×100 RPM | the dynamic idle target; needs `dshot_bidir` | unchanged |
| `dyn_idle_p_gain` / `_i_gain` / `_d_gain` | 50 / 50 / 50 | 1–250 / 1–250 / 0–250 | the gains of the RPM controller | unchanged |
| `dyn_idle_max_increase` | 150 | 10–255, ×0.1 % | the limit of the increase after airmode starts | unchanged |
| `dyn_idle_start_increase` | 50 | 10–255, ×0.1 % | the limit of the increase before airmode starts | removed, `motor_idle` instead |
| `dshot_idle_value` | 550 | 0–2000, ×0.01 % | the static idle; not the floor with dynamic idle | renamed to `motor_idle` (550) |
| `airmode_start_throttle_percent` | 25 | 0–100, % | the throttle after which airmode “latches” until a disarm | unchanged |
| `thrust_linear` | 0 | 0–150, % | x·(1 + k(1 − x)²) | unchanged |
| `vbat_sag_compensation` | 0 | 0–150, % | the cut of the top from 4.20 V to `vbat_warning` | unchanged |
| `vbat_warning_cell_voltage` | 350 | 100–500, 0.01 V | the lower point of the compensation and the warning threshold | unchanged |
| `vbat_sag_lpf_period` | 2 | 1–255, ×0.1 s | the PT1 of the voltage for the compensation: 2 → 5 Hz | unchanged |
| `tpa_mode` | D | PD, D | what TPA attenuates | + `PDS` in WING only |
| `tpa_rate` | 65 | 0–100, % | the attenuation at full throttle | unchanged |
| `tpa_breakpoint` | 1350 | 1000–2000 | the throttle where TPA starts | unchanged |
| `tpa_low_rate` | 20 | 0–100, % | the attenuation at zero throttle | signed, from −128 in WING |
| `tpa_low_breakpoint` | 1050 | 1000–2000 | the top of the low-throttle TPA zone | unchanged |
| `tpa_low_always` | OFF | OFF, ON | OFF: only until the first pass of the point | unchanged |
| `tpa_curve_*`, `tpa_speed_*` | — | — | the hyperbolic curve and speed-based TPA | 2025.12 only, a WING build |
| `anti_gravity_gain` | 80 | 0–250 | the gain of the throttle derivative for I and P | unchanged |
| `anti_gravity_cutoff_hz` | 5 | 2–50, Hz | the PT2 of the throttle derivative | unchanged |
| `anti_gravity_p_gain` | 100 | 0–250, % | the share of the boost applied to P | unchanged |
| `throttle_boost` | 5 | 0–100, ×0.1 | the gain of the high-frequency part of the throttle | unchanged |
| `throttle_boost_cutoff` | 15 | 5–50, Hz | the PT1 cutoff for throttle boost | unchanged |

Sources: `cli/settings.c` 4.5.3 (lines 786, 851, 900, 912, 1111–1116, 1142–1143, 1210, 1227–1232, 1254–1260), the defaults — `flight/pid.c:142–229`, `pg/motor.c:77`, `sensors/battery.c:110, 131`, `pg/rx.c:103`. In 2025.12.5 — `cli/settings.c:962, 1367–1371, 1392–1397`.

### Place in the system

- **Receives:** the filtered gyro and the separately filtered signal for D (`bf-filters`); the setpoint and its derivative for feedforward (`bf-rates-rc`); the throttle position for TPA and anti-gravity; the motor eRPM for dynamic idle (`bf-rpm-filter`); the cell voltage for `vbat_sag_compensation`.
- **Provides:** `pidSum` — to the mixer and the motors; the P, I, D, F terms — to the log (`bf-blackbox`); the `pidSum` value whose threshold triggers the runaway protection (`bf-arming-safety`).
- **If you get it wrong here:** D is raised with a noisy gyro → the derivative amplifies the noise and the motors overheat; the fix is not here but in the filters and the mechanics (`bf-filters`, `f-frame-mech`). `iterm_windup` is carried over from 4.5 without recalculation → in 2025.12 it is the I limit, not the motor saturation threshold, and the I-term behavior changes silently; the migration table is in `bf-intro`.

## practice

{{widget:pid-sim}}


**Preparation**

Hardware requirements: ESCs that support RPM filtering (BLHeli_32 or Bluejay), an F7/H7 flight controller, an SD card for Blackbox (at least 4 GB).

Software requirements: Betaflight App 2025.12 (for 4.5 firmware — Configurator 10.10), Blackbox Explorer.

**Setup before tuning**

1. Enable RPM filtering: in the Motors tab enable **Bidirectional DShot** and set Motor poles (the RPM filter turns on by itself); `rpm_filter_q = 500` is the default (CLI).
2. Set up Blackbox: select a logging rate of 2 kHz. The gyro, PID, setpoint and motor fields are logged by default — check that the corresponding `blackbox_disable_*` = OFF. `GYRO_SCALED` from old instructions is a `debug_mode` value in 4.5 (it does not exist in 2025.12, where the raw gyro is written to the `gyroUnfilt` field); it is not needed for this tuning.
3. Set the basic filtering parameters:

```text
set gyro_lpf2_static_hz = 300
set gyro_lpf2_type = PT2
set dterm_lpf2_static_hz = 150
set dterm_lpf2_type = PT2
set dyn_notch_max_hz = 600
set dyn_notch_q = 250
save
```

{{lesson:bf-tuning-method|So that the steps below give a conclusion and not an impression: one variable per flight, a control flight, one maneuver program and a comparison of two logs by a script.}}

**Step-by-step tuning**

1. Determine the starting values (for a 5" frame with 2207–2306 motors): start from the 2025.12 defaults (`flight/pid.h`) — such a 5" already flies on them, and lowered numbers borrowed from someone else only take you away from the baseline for no reason. The CLI accepts one `name = value` pair per `set` command, one per line:

```text
set p_roll = 45
set i_roll = 80
set d_roll = 30
set d_max_roll = 40
set p_pitch = 47
set i_pitch = 84
set d_pitch = 34
set d_max_pitch = 46
set p_yaw = 45
set i_yaw = 80
set d_yaw = 0
save
```

In 2025.12 `d_roll`/`d_pitch` are the base D and `d_max_roll`/`d_max_pitch` the peak D. On 4.5 the same aircraft is set differently: `d_roll = 40`, `d_min_roll = 30`, `d_pitch = 46`, `d_min_pitch = 34` (there `d_*` is the peak and `d_min_*` the base); do not paste a block from one version into the other.

**The 2025.12 defaults** (`flight/pid.h`, `resetPidProfile()` in `flight/pid.c`; all of them are PID-profile parameters, and each of the 4 profiles has its own):

| Parameter | Roll | Pitch | Yaw | What it is |
|---|---|---|---|---|
| `p_*` | 45 | 47 | 45 | P |
| `i_*` | 80 | 84 | 80 | I |
| `d_*` | 30 | 34 | 0 | the base D in calm flight (in 4.5 this is `d_min_*`) |
| `d_max_*` | 40 | 46 | 0 | D max — the peak D on sharp movements (in 4.5 this is `d_*`); `d_max_gain` 37, `d_max_advance` 20 (in 2026.6 — 0 and 35: the peak comes from the stick only) |
| `f_*` | 120 | 125 | 120 | the feedforward gain (0 = FF is off on the axis); the tuning of FF itself — `feedforward_*` (bf-rates-rc) |

The rest of what is useful in this module:

- `pidsum_limit` = 500, `pidsum_limit_yaw` = 400 (range 100–1000): the mixer clips the P+I+D+F sum of each axis to this limit and then divides it by 1000 (`PID_MIXER_SCALING`, `flight/mixer.c`), so 500 is half of the motor range. If `axisP+I+D+F` on an axis hits the limit in the log, the axis is saturated; raising the limit without a log is not a good idea.
- TPA: `tpa_mode` = D (only D is attenuated), `tpa_rate` 65, `tpa_breakpoint` 1350. Low-throttle TPA (introduced in 4.5; unchanged on a multirotor in 2025.12): `tpa_low_rate` = 20, `tpa_low_breakpoint` = 1050, `tpa_low_always` = OFF. Below `tpa_low_breakpoint` D is attenuated linearly: at zero throttle — by 20 % (a factor of 0.8). With `tpa_low_always = OFF` this works only until the throttle first passes above the point after power-up (that is, on the first takeoff, or earlier — if the throttle was moved before arming), and from then on — until a reboot — the ordinary TPA applies (`pidUpdateTpaFactor()`).
- Dynamic idle: `dyn_idle_min_rpm` = 0 (off; the unit is 100 RPM, 30 → 3000 RPM), `dyn_idle_p_gain`/`_i_gain`/`_d_gain` = 50, `dyn_idle_max_increase` = 150 (up to +15 % of the motor range in the air); until the throttle is first raised above `airmode_start_throttle_percent` after arming, the limit of the increase is `motor_idle` (2025.12, `wasThrottleRaised()`). In 4.5 the limit before airmode activation was set by a separate `dyn_idle_start_increase` = 50, that is, +5 %, and without airmode enabled it held for the whole flight; the variable is removed in 2025.12. It works only with DShot telemetry (bidirectional DShot): the controller raises the lower throttle limit so that the slowest motor does not fall below the set RPM, and with `dyn_idle_min_rpm` > 0 `motor_idle` no longer sets the floor in the air (`mixerInitProfile()`, `flight/mixer_init.c`). It helps against propwash and desyncs on a throttle chop; it is tuned from a log (`debug_mode = DYN_IDLE`), not from a table.

2. Tuning the P term: make a sharp stick snap and return. In Blackbox look at the gyro trace (blue) and the setpoint (green). If after the stick stops the gyro crosses zero in the opposite direction (bounce-back), this is not “too little P”: check D/Damping (underdamping), I-term relax and the delay of the D filters, as in the worked example; raising P alone usually makes the bounce worse. If the gyro oscillates around the setpoint — P is high, reduce it by 5.

3. Tuning the D term: after tuning P make the same movement. Add the D-term trace. If the D term shakes with high-frequency noise — reduce D by 3–5. If after the movement the gyro shows decaying oscillations — increase D by 3.

4. Tuning the I term: hover in Angle/Horizon mode, tilt the drone slightly and return it to level. If the drone drifts slowly — increase I by 10. If it passes through neutral and rocks — reduce I by 10.

5. Tuning feedforward: make a series of fast stick movements. In Blackbox compare the setpoint and the gyro. With a large lag increase `feedforward_boost`. With overshoot reduce `feedforward_boost`.

6. Tuning TPA: do a punch-out (20% → 80% throttle). If a motor reaches 100% without backing off — check `tpa_rate`. With high-frequency ripple increase `tpa_rate` (percent, 0–100; 65 by default) to 70–80, and lower `tpa_breakpoint` below the default 1350 (for example, to 1250) so that TPA starts earlier.

**Final steps**

Save the final parameters: `diff all`. Make a short flight (2–3 minutes) and check the motor temperature. If the motors are hot, reduce the D term by 10–15%.

### Exercise without hardware: compute the PID terms by hand
The roll axis, the 2025.12 defaults from the table above: `p_roll` = 45, `i_roll` = 80, `d_roll` = 30, `d_max_roll` = 40, `f_roll` = 120; `pidsum_limit` = 500, `iterm_windup` = 80. The scale factors are from the section “The formula as implemented”: 0.032, 0.244, 0.00053 and 0.0138 (for FF there is also the division by 100). TPA and the filters take no part in the calculation. Compute on paper or in a spreadsheet:

1. P at an error of 50 °/s.
2. I after an error of 10 °/s has been held for 0.5 s (I starts from zero). Then — the I limit from `iterm_windup` and the time in which I reaches the limit at the same error; the yaw I limit (`pidsum_limit_yaw` = 400).
3. D when the filtered gyro accelerates by 2000 °/s per second — for the base `d_roll` and for the D max peak (effective D = `d_max_roll`).
4. FF when the setpoint goes from 0 to 670 °/s in 0.1 s (with the stick still, FF = 0).
5. The sum P + I + D from items 1–3 (the base D, FF = 0), its fraction of the motor range after the division by 1000, and the error at which P alone hits `pidsum_limit`.
6. A block from 4.5 is pasted into 2025.12: `set d_roll = 40` and `set d_min_roll = 30`. What will the CLI answer to the second line, what will D from item 3 become in calm flight, and by what factor has it grown?

Self-check: the lab is complete when your numbers match these to within 1 %:
- Kp = 1.44, P = 72;
- Ki = 19.52, I = 97.6; the I limit = 400 (roll, pitch) and 320 (yaw); the time to the limit is 2.05 s;
- Kd = 0.0159, D = −31.8; at the D max peak −42.4;
- Kff = 0.01656, FF = 111;
- the sum is 137.8, that is, 13.8 % of the motor range, and the axis is not saturated; P alone reaches 500 at an error of 347 °/s;
- item 6: `d_min_roll` — `INVALID NAME`; the base D became 40, and D from item 3 is −42.4 instead of −31.8 — 1.33 times larger;
- on hardware (if you have it): in the Blackbox log, at the moment when `setpoint` − `gyroADC` in roll equals your error, `axisP` differs from the computed Kp·e by no more than 5 %.

**Reference for self-check.** The calculation: gain = the number from the configurator × the scale factor, then P = Kp·e, I = Ki·e·t, D = −Kd·(the rate of change of the gyro), FF = Kff·(the rate of change of the setpoint); the I limit = `iterm_windup`/100 × `pidsum_limit` = 0.8 × 500. The sign of D is negative: the term opposes the acceleration. Frequent wrong answers: FF = 11,095 — the division of `f_roll` by 100 was forgotten; I = 195.2 — the error was multiplied by Ki but not by the time 0.5 s; P = 2250 — the number from the configurator was taken without the scale factor 0.032; D = +31.8 — the minus was lost, the derivative is taken of the gyro and subtracted; in item 6 the answer “D will return to 30 in calm flight” — in 2025.12 `d_roll` is already the base D, while `d_max_roll` stayed at 40, so there is no D max range any more and the noise and motor heating are higher.

### Exercise 2: the throttle path in numbers
No hardware is needed: Python repeats the 4.5.3 formulas from the section “The throttle path” (`thrust_linear` — `pid.c:328–342`, TPA — `pid.c:280–296` and `pid_init.c:427–434`, `vbat_sag` — `mixer.c:248–256`, the lower limit — `drivers/dshot.c:68` and `mixer_init.c:343`). The full version with dynamic idle, throttle boost and anti-gravity is in the module's lab; here is its core.

**Step 1.** Run the script:

```python
# Betaflight 4.5.3 throttle path: flight/pid.c, pid_init.c, mixer.c, mixer_init.c
def tl(x, k):                                   # pidApplyThrustLinearization
    return x * (1 + k * (1 - x) ** 2)

def tl_comp(t, k):                              # pidCompensateThrustLinearization
    return t / (1 + (k - 0.5 * k * k) * (1 - t) ** 2)

def tpa(thr, rate=65, bp=1350, low_rate=20, low_bp=1050, faded=True):
    t, tbp = (thr - 1000) / 1000, min((bp - 1000) / 1000, 0.99)
    lbp = min(max((low_bp - 1000) / 1000, 0.01), tbp)
    if t >= lbp or faded:                       # pidUpdateTpaFactor
        return 1 - rate / 100 / (1 - tbp) * max(t - tbp, 0)
    return 1 - low_rate / (100 * lbp) * (lbp - t)

def sag(cell_v, comp=100, warn=3.50):           # fraction of the top of the range cut by vbat_sag
    rng = 4.20 - warn
    good = 1 - min(max((4.20 - cell_v) / rng, 0), 1)
    return rng / 4.20 * good * comp / 100

print("TL 40: x=0.10 ->", round(tl(0.10, 0.4), 3), "| x=0.50 ->", round(tl(0.50, 0.4), 3))
t = tl_comp(0.30, 0.4)
print("TL 40, hover 0.30: throttle after compensation", round(t, 4), "output", round(tl(t, 0.4), 4))
for thr in (1000, 1500, 2000):
    print(f"TPA {thr}: before passing 1050 {tpa(thr, faded=False):.3f}, after {tpa(thr):.3f}")
for warn in (3.50, 3.00):
    print(f"sag 100, warn {warn:.2f}: 4.20 V -> {sag(4.20, 100, warn)*100:.1f} %,"
          f" 3.80 V -> {sag(3.80, 100, warn)*100:.1f} %, 3.30 V -> {sag(3.30, 100, warn)*100:.1f} %")
print("dyn idle 30 ->", 30 * 100 / 60, "rev/s; DShot lower limit:", round(48 + 0.055 * 1999, 1), "-> 48")
```

The output (Python 3, an actual run):

```text
TL 40: x=0.10 -> 0.132 | x=0.50 -> 0.55
TL 40, hover 0.30: throttle after compensation 0.2593 output 0.3162
TPA 1000: before passing 1050 0.800, after 1.000
TPA 1500: before passing 1050 0.850, after 0.850
TPA 2000: before passing 1050 0.350, after 0.350
sag 100, warn 3.50: 4.20 V -> 16.7 %, 3.80 V -> 7.1 %, 3.30 V -> 0.0 %
sag 100, warn 3.00: 4.20 V -> 28.6 %, 3.80 V -> 19.0 %, 3.30 V -> 7.1 %
dyn idle 30 -> 50.0 rev/s; DShot lower limit: 157.9 -> 48
```

**Step 2.** Substitute your own values and answer four questions:
1. By what factor does `thrust_linear` = 40 increase the command at x = 0.10 and at x = 0.50?
2. What will the D factor be at a throttle of 1750 with the TPA defaults and with `tpa_rate` 80 / `tpa_breakpoint` 1250?
3. What fraction of the top will `vbat_sag_compensation` = 100 cut on a fresh Li-Ion (4.20 V), if `vbat_warning_cell_voltage` = 300?
4. What will the lower limit of `motorOutput` in the log header be before and after `set dyn_idle_min_rpm = 30` with bidirectional DShot working?

Self-check: the lab is complete when the answers match the reference to within 1 %. This is checked without hardware. On hardware check two more things. After dynamic idle is enabled the Blackbox header has `motorOutput:48,2047`. In `debug_mode = BATTERY` channel [2] on a fresh LiPo with `vbat_sag_compensation` = 100 equals 100 (goodness 1.00) and falls to 0 by 3.50 V.

**Reference for self-check.**
- 1: 0.132/0.10 = 1.32 times at x = 0.10 and 0.55/0.50 = 1.10 times at x = 0.50. The local slope at x = 0.50 is 0.90 at the same time: the value is increased, but the sensitivity is lower.
- 2: 0.600 with the defaults and 0.467 with 80 / 1250.
- 3: 28.6 %.
- 4: 158 before (157.9 is rounded) and 48 after.

Frequent mistakes:
- In item 2, 1750 is substituted instead of the fraction 0.75, or the division by (1 − tbp) is forgotten: the result is 0.74 instead of 0.600.
- In item 3 the default range 4.20 − 3.50 is taken, giving 16.7 %.
- In item 4 the answer is “158 and 158”, treating `dshot_idle_value` as the floor with dynamic idle too. That happens only if telemetry is not working: then dynamic idle is silently off.

### Moving to real hardware: checking the throttle path
Props off, the battery connected, the aircraft secured.
1. `get dshot_bidir` = ON, and `dshot_telemetry_info` shows eRPM for all the motors.
2. `set dyn_idle_min_rpm = 30`, `save`. Arm on the bench, throttle at zero: the motors spin. A 10 s Blackbox capture; check for `motorOutput:48,2047` in the header.
3. The props go on only for the flight. 30 s of hover, then 2–3 s of a flat fall at zero throttle. If the aircraft “drops out” in the fall or the motors squeal — land immediately.

The criteria: in the `debug_mode = DYN_IDLE` log channel [3] (the minimum RPM, rev/s × 10) is no lower than 450 in the fall (a course guideline: −10 % of the target 500). After the flight the motors are no hotter than before the change.

## diagnostics

- **Symptom: Fast oscillations in hover (buzzing, shaking)**
- Possible cause: the P term is too high, insufficient gyro filtering.
- What to check/do: record a Blackbox log. If the gyro trace has frequent peaks in the same band (roughly 30–80 Hz on a 5") — reduce P by 20%. Check that the dynamic notch and RPM filtering are working.

- **Symptom: Bounce-back after a sharp movement**
- Possible cause: underdamping (too little D), I-term relax turned off, D-filter delay; raising P alone usually makes the bounce worse.
- What to check/do: in Blackbox find the gyro peak of the opposite sign after the stick stops. Raise Damping by 0.1–0.15, check `iterm_relax = RP` and whether the D filters are too low; if the motors run hot — filters and mechanics, not D.

- **Symptom: Slow, wandering oscillations (~1–3 Hz)**
- Possible cause: the I term is too high, wrong anti-windup.
- What to check/do: reduce I by 15–20%. Check `iterm_windup` (80 by default, the I limit in % of `pidsum_limit`); in 4.5 these were two variables with a different meaning — `iterm_windup` (85 by default) and `iterm_limit` (400 by default).

- **Symptom: Overheating motors**
- Possible cause: a high D term, insufficient D-term filtering.
- What to check/do: in Blackbox look at the D-term trace — if it looks like noise, reduce D by 20–30%. Lower `dterm_lpf2_static_hz` to 100–120 Hz.

- **Symptom: The drone veers off on a sharp throttle increase (punch-out)**
- Possible cause: wrong TPA settings, high P/D without attenuation.
- What to check/do: in Blackbox find the punch-out on the throttle trace. If the PID sum clips — increase `tpa_rate` or lower `tpa_breakpoint`.

- **Symptom: Gyro noise in the logs (a sawtooth trace)**
- Possible cause: mechanical vibration, RPM filtering not working.
- What to check/do: check that RPM filtering is working (the Motors tab should display the rotation speed). Lower `gyro_lpf2_static_hz` to 250–300 Hz.
- **Symptom:** after a throttle punch the aircraft dips its nose
  - Possible cause: I cannot keep up, anti-gravity is too low.
  - What to do: raise `anti_gravity_gain`, check `thrust_linear`.
- **Symptom:** the I term is visible in the log as a rise after a flip and extra rotation
  - Possible cause: I-term relax is off or the cutoff is high.
  - What to do: `iterm_relax = RP`, cutoff 10–15.
- **Symptom:** `dyn_idle_min_rpm` = 30, but propwash and desync in falls have not changed
  - Possible cause: bidirectional DShot is not working, and the dynamic idle target is silently zeroed (`mixerInitProfile()`); or the value is set in a different PID profile.
  - What you see in the log: the header `motorOutput:158,2047` instead of `48,2047`; all the `DYN_IDLE` debug channels are 0.
  - What to do: `dshot_telemetry_info`, `get dshot_bidir`, `profile` and `get dyn_idle_min_rpm` in the profile you fly (`bf-rpm-filter`).
- **Symptom:** after dynamic idle is enabled the aircraft is “floaty”, brakes flips poorly, and has short inverted hang time
  - Possible cause: the `dyn_idle_min_rpm` target is too high for these motors and props.
  - What to do: lower it in steps of 5 (500 RPM) and compare the logs of the fall.
- **Symptom:** D shake on the ground disappears only on the first takeoff after power-up; after landing and arming again on the same pack it returns
  - Possible cause: the low-throttle TPA (`tpa_low_*`) is turned off after the first pass of `tpa_low_breakpoint` — even if the throttle was raised before arming — and returns only after a reboot (which is what changing the pack does).
  - What to do: `set tpa_low_always = ON`; in parallel — the D filters (`bf-filters`).
- **Symptom:** oscillations only at full throttle, clean in hover
  - Possible cause: TPA is too weak for this setup: at high throttle the open-loop gain and the noise grow.
  - What you see in the log: in 2025.12 `debug_mode = TPA` [0] — the factor × 1000 (350 at full throttle with the defaults).
  - What to do: first lower `tpa_breakpoint` (1350 → 1250), then raise `tpa_rate` (65 → 80): at full throttle the factor becomes 0.20 instead of 0.35.
- **Symptom:** on Li-Ion after `vbat_sag_compensation` = 100 the aircraft is noticeably weaker in a punch-out at the start of the flight
  - Possible cause: `vbat_warning_cell_voltage` was lowered to 3.00 V, the compensation range became 1.20 V, and 28.6 % of the top is cut on a full pack.
  - Consequences: less thrust in a punch-out, and the top of the range moves with the sag under throttle.
  - What to do: compensation 0 or a smaller percentage; do not choose the warning threshold to suit the compensation.
- **Symptom:** the hover throttle is slightly higher than usual after `thrust_linear` is enabled
  - Possible cause: the throttle compensation is approximate: with a hover at 0.30 and `thrust_linear` = 40 the output is 0.316 (+5.4 %).
  - What to do: this is expected; if it bothers you, reduce `thrust_linear` to 20 (+1.5 %).

## references

- Betaflight PID Tuning Guide | https://betaflight.com/docs/wiki/guides/current/PID-Tuning-Guide | primary | A
- Betaflight DShot RPM Filtering | https://betaflight.com/docs/wiki/guides/current/DSHOT-RPM-Filtering | primary | A
- Betaflight Blackbox logging and usage | https://betaflight.com/docs/wiki/guides/current/Black-Box-logging-and-usage | primary | A
- Betaflight 4.5 mixer.c (the throttle path, dynamic idle, vbat sag, throttle boost) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/mixer.c | primary | A
- Betaflight 4.5 mixer_init.c (the dynamic idle and vbat sag constants) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/mixer_init.c | primary | A
- Betaflight 4.5 pid.c (TPA, anti-gravity, thrust linearization, the defaults) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/pid.c | primary | A
- Betaflight docs: Dynamic Idle | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/guides/current/Dynamic-Idle.md | primary | A
- Oscar Liang: Betaflight PID Tuning | https://oscarliang.com/betaflight-pid-tuning/ | secondary | B
- Joshua Bardwell: How to Tune PID with Blackbox | https://www.youtube.com/watch?v=YXpPajW9lCU | secondary | B
