---
id: inav-mc-tuning
title: "Multirotor tuning in INAV: PIDs, rates, filters, EZ Tune and navigation PIDs"
level: L2
readingTime: 70 min
firmware: INAV 9.1 (checked against 9.1.0)
status: published
added: 2026-11-19
tags:
  - INAV
  - PID
  - filters
  - EZ Tune
  - rates
  - navigation
  - Blackbox
related:
  - inav-setup-scratch
  - inav-gps
  - inav-missions
  - inav-cli-backup
  - inav-mixer-vtol
  - bf-pid
  - bf-filters
  - bf-rpm-filter
  - ctl-theory
  - est-alt-sources
  - math-ode-dyn
next:
  - inav-missions
source: content/inav/inav-mc-tuning.md
source_hash: 29b517b79e06
---

## summary
In INAV the PID, rate and filter numbers look like those in Betaflight but are computed differently: `roll_rate = 20` is 200 °/s, the RPM filter is fed by ESC telemetry over a UART and not by bidirectional DShot, and above stabilization there are four more navigation controllers with their own scales. This module works through all of that from the INAV 9.1.0 source: how an integer from `diff` turns into a gain, the stick curve formula, the filter chain in the order it is applied, every `ez_*` setting and the formulas by which EZ Tune rewrites the PIDs and filters, the multirotor navigation PIDs and the tuning order for a GPS copter with the Blackbox fields for each step. The practice needs no hardware and no simulator: compute the gains and the rate from a `diff` fragment, apply the EZ Tune formulas to three sets of sliders, choose a setting and a direction from altitude and position hold symptoms, and find three errors in a config.

## theory
### Where the settings live
A control profile (`control_profile 1…3`) holds 126 settings in three groups: 91 PID settings (`mc_*`, `fw_*`, `nav_mc_*`, `dterm_lpf_*`, `smith_predictor_*`), 25 rate, expo and TPA settings, 10 EZ Tune settings. In older guides the command is called `profile` — 9.1 has no such command, type `control_profile` (in the 8.0.1 source the rate group was called `PG_CONTROL_RATE_PROFILES`, in 9.x — `PG_CONTROL_PROFILES`; the setting names did not change). The details of profiles and `diff` are in `inav-cli-backup`.

Three things are not in the profile, and people trip over this:
- the gyro filters (`gyro_*`, `dynamic_gyro_notch_*`, `setpoint_kalman_*`, `rpm_gyro_*`) and `looptime` — common to all profiles;
- `nav_mc_hover_thr` — in the battery profile (`battery_profile`);
- the navigation limits (`nav_mc_bank_angle`, the speeds, `nav_mc_braking_*`) — common.

### The rate loop: from an integer to a gain
`pid_type = AUTO` (the values are `NONE`, `PID`, `PIFF`, `AUTO`) selects the PID controller with Control Derivative on a multirotor and PIFF on an airplane, rover and boat. The controller works in °/s and computes in float; the integers from the profile are divided by the constants of `flight/pid.h`:

```text
kP  = mc_p_*  / 31      units / (°/s)       P = kP · (setpoint − gyro)
kI  = mc_i_*  / 4       units / (°/s · s)   I += kI · error · dt
kD  = mc_d_*  / 1905    units / (°/s²)      D = −kD · d(gyro)/dt · dBoost
kCD = mc_cd_* / 7270    units / (°/s²)      CD = kCD · d(setpoint)/dt
```

“Units” are `axisPID` units: the sum is limited to ±500 in roll and pitch and ±400 in yaw, and ±500 is the full travel of an axis in the mixer (`inav-mixer-vtol`). CD is the counterpart of Betaflight feedforward: it responds to stick movement, not to the error; the setpoint signal before it is smoothed by the PT3 `mc_cd_lpf_hz` (30 Hz). D is computed from the gyro only.

| Axis | P | I | D | CD | kP | kI | kD | kCD |
|---|---|---|---|---|---|---|---|---|
| Roll, pitch (`mc_*_roll`, `mc_*_pitch`) | 40 | 30 | 23 | 60 | 1.290 | 7.5 | 0.01207 | 0.00825 |
| Yaw (`mc_*_yaw`) | 85 | 45 | 0 | 60 | 2.742 | 11.25 | 0 | 0.00825 |

The range of each number is 0…255. An example: an error of 50 °/s with `mc_p_roll = 40` gives P = 64.5 units, that is, 13 % of the travel. The scales are the same in 8.0.1.

What else affects the rate loop:

| Setting | Default (range) | What it does |
|---|---|---|
| `mc_iterm_relax` | `RP` (`OFF`, `RP`, `RPY`) | weakens the accumulation of I while the setpoint changes quickly: the factor is max(0, 1 − the HF part of the setpoint / 40 °/s) |
| `mc_iterm_relax_cutoff` | 15 Hz (1…100) | the cutoff of the filter that separates the “fast” part of the setpoint |
| `pid_iterm_limit_percent` | 33 % (0…200) | the I ceiling: 33 % of the axis limit — ±165 units in roll and pitch, ±132 in yaw |
| `iterm_windup` | 50 % (0…90) | the growth of I slows down when the spread of the motor commands takes more than this share of the range, and stops at 100 % |
| `d_boost_min`, `d_boost_max` | 0.5 (0…1), 1.25 (1…3) | the D multiplier: on a sharp stick movement it drops toward min, on a disturbance it grows toward max |
| `d_boost_max_at_acceleration` | 7500 °/s² (1000…16000) | the gyro acceleration at which the multiplier reaches max |
| `antigravity_gain`, `antigravity_accelerator` | 1 and 1 (1…20) | I boost on a sharp throttle change; 1 — off |
| `antigravity_cutoff_lpf_hz` | 15 Hz (1…30) | the filter that extracts the “sharpness” of the throttle |
| `tpa_rate` | 0 (0…200; 0…100 in 8.0.1) | attenuation of P, D and CD above `tpa_breakpoint`; it does not touch I. **On a multirotor — no more than 100:** above that the factor at high throttle becomes negative, and P and D change sign |
| `tpa_breakpoint` | 1500 (1000…2000) | the throttle at which TPA starts |
| `tpa_on_yaw` | `OFF` | extend TPA to yaw |
| `rate_accel_limit_roll_pitch`, `rate_accel_limit_yaw` | 0 and 10000 °/s² (up to 500000) | a limit on the rate of change of the setpoint; ≤ 50 — off |
| `yaw_lpf_hz` | 0 Hz (0…200) | a PT1 on yaw P |
| `looptime` | 500 µs (up to 9000) | the period of the PID task: 2 kHz. The gyro is sampled by a separate 4 kHz task |

Multirotor TPA: factor = (100 − `tpa_rate` · (throttle − breakpoint) / (2000 − breakpoint)) / 100 at a throttle from the breakpoint to 1999; at exactly 2000 — (100 − min(`tpa_rate`, 100)) / 100.

**Warning: on a multirotor `tpa_rate` is no more than 100.** The range up to 200 in 9.x exists for the airplane branch, where the factor is clamped to 0.3…2.0. The multirotor branch has no lower bound: the factor passes through zero at a throttle of breakpoint + (2000 − breakpoint) · 100 / `tpa_rate` and is negative beyond that. An example for `tpa_rate` = 150 and breakpoint 1500: at throttle 1700 the factor is (100 − 150 · 200 / 500) / 100 = 0.40; around 1833 it is zero — P, D and CD are off; at 1900 — (100 − 150 · 400 / 500) / 100 = −0.20, at 1999 — −0.50. A negative factor flips the sign of P, D and CD: the controller amplifies the error instead of removing it, and at high throttle the aircraft shakes and flips itself; I meanwhile works as usual and does not save it. With `tpa_rate` = 200 the zero comes already at throttle 1750, and at 1999 the factor is almost −1. The CLI accepts such a value silently. And exactly 100 is not a safe maximum: at full throttle the factor is 0, and there is no P and D stabilization. The in-flight adjustment is limited to the same 0…200: function 54 in `adjrange` on a multirotor can take `tpa_rate` beyond 100 right in the air (`inav-adjustments`). `apa_pow` and `tpa_pitch_compensation`, new in 9.x, apply to an airplane.

### Rates and expo
`roll_rate`, `pitch_rate` (4…180) and `yaw_rate` (1…180) are set in tens of °/s: the default 20 is 200 °/s at full stick. A number from Betaflight cannot be carried over here. `rc_expo` = 70 and `rc_yaw_expo` = 20 (0…100) change only the shape of the curve. The formula from `fc/rc_curves.c`, with s the stick deflection from −1 to 1 after the deadband (`deadband` = 2) and e = expo / 100:

```text
rcCommand = lrint(500 · s · (1 − e · (1 − s²)))        −500…500, an integer
ω = rcCommand / 500 · rate · 10                        °/s
```

At the defaults half stick gives 119 / 500 · 200 = 47.6 °/s, not 100: an expo of 70 flattens the center strongly. `manual_roll_rate`, `manual_pitch_rate`, `manual_yaw_rate` (in percent) and `manual_rc_expo` work only in MANUAL mode, which a multirotor does not have, — leave them alone. `thr_mid` = 50 and `thr_expo` = 0 set the throttle curve.

### ANGLE and HORIZON
The angle loop is a single P: rate setpoint = angle error × `mc_p_level` / 6.56, limited by the rate of the axis. At the default 20 that is 3.05 1/s: an error of 10° gives 30.5 °/s. The other two numbers are neither I nor D:

| Setting | Default | Meaning |
|---|---|---|
| `mc_p_level` | 20 | the leveling strength, 1/s after dividing by 6.56 |
| `mc_i_level` | 15 | the cutoff of the PT1 on the rate setpoint, Hz; 0 — no filter |
| `mc_d_level` | 75 | HORIZON: the stick deflection in % from which control is purely by rate; below it — a blend with ANGLE |
| `max_angle_inclination_rll`, `max_angle_inclination_pit` | 450 (100…900) | the angle limit in decidegrees: 450 = 45° |

### Filters in the order they are applied
{{diagram:inav-mc-filter-chain|By default three stages work after the anti-alias filter: a 60 Hz PT1, the dynamic notch and Kalman; the RPM filter, the 3D notch and the Smith predictor are off, and D additionally passes through its own 110 Hz PT2.}}

The order is taken from `gyroUpdate()`, `gyroFilter()` and `pidController()`.

| # | Stage | Settings (default, range) | Note |
|---|---|---|---|
| 1 | Anti-alias PT1 | `gyro_anti_aliasing_lpf_hz` 250 (0…1000) | the only filter at the gyro rate; do not change it |
| 2 | RPM notch | `rpm_gyro_filter_enabled` OFF, `rpm_gyro_harmonics` 1 (1…3), `rpm_gyro_min_hz` 100 (30…200), `rpm_gyro_q` 500 (1…3000, Q = 5.0) | a notch per motor and harmonic, updated at 500 Hz |
| 3 | LULU | `gyro_lulu_enabled` OFF, `gyro_lulu_sample_count` 3 | a nonlinear outlier filter |
| 4 | Main LPF PT1 | `gyro_main_lpf_hz` 60 (0…500), `gyro_filter_mode` STATIC (`OFF`, `STATIC`, `DYNAMIC`, `ADAPTIVE`) | the main source of delay; `DYNAMIC` moves the cutoff with throttle between `gyro_dyn_lpf_min_hz` 200 and `gyro_dyn_lpf_max_hz` 500, `ADAPTIVE` — with noise within `gyro_adaptive_filter_min_hz` 50 and `gyro_adaptive_filter_max_hz` 150 |
| 5 | Dynamic notch | `dynamic_gyro_notch_enabled` ON, `dynamic_gyro_notch_q` 120 (Q = 1.2), `dynamic_gyro_notch_min_hz` 50 (30…250) | up to three peaks per axis from the FFT |
| 6 | 3D notch | `dynamic_gyro_notch_mode` 2D (`2D`, `3D`), `dynamic_gyro_notch_3d_q` 200 | in 3D mode — one more notch on the first peak |
| 7 | Kalman | `setpoint_kalman_enabled` ON, `setpoint_kalman_q` 100 (1…1000) | a gyro filter that eases its smoothing when the setpoint is far from the measurement; a larger q — less delay |
| 8 | Smith predictor | `smith_predictor_delay` 0 ms (0…8; 0 — off), `smith_predictor_strength` 0.5, `smith_predictor_lpf_hz` 50 | compensates for the filter delay, already inside the PID |
| 9 | D-term LPF | `dterm_lpf_hz` 110 (0…500), `dterm_lpf_type` PT2 (`PT1`, `BIQUAD`, `PT2`, `PT3`, `LULU`) | the D branch only |

**The RPM filter and DShot.** INAV 9.1.0 has no bidirectional DShot. RPM comes over a separate ESC telemetry wire: a UART with function 262144 (“ESC output/telemetry” in the Configurator), 115200 baud, a 10-byte frame. The firmware polls the motors one at a time, so on a quadcopter the RPM of each motor is updated no more than about 290 times a second (a frame takes 0.87 ms, and there are four motors), on an octocopter — half as often; the real rate depends on the ESC. In Betaflight the eRPM of every motor arrives in every loop. The consequence: the INAV notch lags behind sharp throttle changes, and you should not remove the dynamic notch after enabling the RPM filter. The filter is initialized only if the ESC telemetry port is open: without it `rpm_gyro_filter_enabled = ON` silently does nothing. `motor_poles` (14) must match the motor.

The difference from Betaflight in one table (the theory of filters and PIDs is in bf-filters, bf-rpm-filter and bf-pid; the Betaflight values are for 2025.12):

| What | INAV 9.1.0 | Betaflight 2025.12 |
|---|---|---|
| P / I / D scale | 1/31, 1/4, 1/1905 | 0.032029, 0.244381, 0.000529 — the same to within 3 % |
| Default roll PIDs | 40 / 30 / 23, CD 60 | 45 / 80 / 30 (D max 40), FF 120 |
| Rates | `roll_rate` in tens of °/s | the ACTUAL model and others, °/s |
| Main gyro LPF | PT1 60 Hz | LPF1 dynamic, 250…500 Hz |
| Dynamic notch | 3 peaks, Q 1.2, from 50 Hz | 3 notches, Q 3.0, from 100 Hz |
| RPM source | ESC telemetry over a UART | bidirectional DShot (`dshot_bidir`) |
| RPM harmonics | 1 | 3 |
| Feedforward | `mc_cd_*` | `feedforward` |
| Sliders | `ez_*` | `simplified_*` |

The INAV defaults are designed for a heavy GPS aircraft: a low cutoff, small I and D. On a 5-inch copter, without raising `gyro_main_lpf_hz`, the aircraft is sluggish — that is not a PID error.

### EZ Tune
EZ Tune is not autotuning. It is ten numbers in the profile and the formulas of `flight/ez_tune.c`, which with `ez_enabled = ON` rewrite the PIDs, rates and filters. The recalculation happens at boot, on a profile change and when the sliders are written from the Configurator, so a manual `set mc_p_roll` or `set gyro_main_lpf_hz` with EZ Tune enabled lives until the first reboot. EZ Tune is in the profile, but the gyro filters are common: the filter value is set by the profile that is active at boot.

| Setting | Default (range) | What it writes |
|---|---|---|
| `ez_enabled` | OFF | enables the recalculation |
| `ez_filter_hz` | 110 (the CLI accepts 20…300; the hard limit is 255, the rule is below) | `gyro_main_lpf_hz` = F; `dterm_lpf_hz` = max(F − 5, 50), type PT2; `dynamic_gyro_notch_min_hz` = max(F · 0.667, 50); `smith_predictor_delay` = 1000 / (2π · F) ms; `setpoint_kalman_q` = 200 for F < 150, otherwise 200 + 200 · (F − 150) / 150 |
| `ez_response` | 100 (0…200) | roll P = 40 · R / 100 |
| `ez_stability` | 100 (0…200) | roll I = 75 · S / 100 |
| `ez_damping` | 100 (0…200) | roll D = 23 · D / 100 |
| `ez_aggressiveness` | 100 (0…200) | roll CD = 100 · A / 100 |
| `ez_axis_ratio` | 110 (25…175) | pitch = the roll value · ratio / 100 |
| `ez_rate` | 100 (0…200) | `roll_rate` = `pitch_rate` = 30 + 60 · rate / 200; `yaw_rate` is 10 lower; `rc_expo` = `rc_yaw_expo` = 40 + 60 · rate / 200 |
| `ez_expo` | 100 (0…200) | in 9.1.0 the firmware does not read it: expo is computed from `ez_rate` |
| `ez_snappiness` | 0 (0…100) | `d_boost_min` = 1 − snappiness / 100 |

Yaw is computed from its own base of 45 / 80 / 0 / 100 with half the sensitivity: value = base · (1 + (slider − 100) / 200). The fractional part is dropped everywhere; the computation is in float32, so occasionally the result is one less than the exact value (response 150 and ratio 105 give a pitch P of 62, not 63). Besides the formulas, EZ Tune always enables RC smoothing, the dynamic notch with Q 250 in 3D mode, Kalman and the STATIC filter mode.

What you get with the sliders at their defaults:

| Setting | Without EZ Tune | EZ Tune, all sliders at default |
|---|---|---|
| Roll P / I / D / CD | 40 / 30 / 23 / 60 | 40 / 75 / 23 / 100 |
| Pitch P / I / D / CD | 40 / 30 / 23 / 60 | 44 / 82 / 25 / 110 |
| Yaw P / I / D / CD | 85 / 45 / 0 / 60 | 45 / 80 / 0 / 100 |
| `roll_rate` / `yaw_rate` | 20 / 20 | 60 / 50 |
| `rc_expo` | 70 | 70 |
| `gyro_main_lpf_hz` / `dterm_lpf_hz` | 60 / 110 | 110 / 105 |
| `dynamic_gyro_notch_min_hz`, Q, mode | 50, 120, 2D | 73, 250, 3D |
| `setpoint_kalman_q` | 100 | 200 |
| `smith_predictor_delay` | 0 | 1.45 ms |
| `d_boost_min` | 0.5 | 1.0 |

Enabling EZ Tune with untouched sliders is already a different tune: a rate of 600 °/s instead of 200, I 2.5 times larger, a gyro cutoff almost twice as high. The starting “Filter Hz” values from the Configurator 9.1 tooltip: 110 for 5 inches, 90 for 7, 75 for 10, 60 for 12. Two peculiarities of the 9.1.0 code. The Configurator tooltip promises a separate Expo slider, but `ezTuneUpdate()` takes `ez_rate` for expo in both formulas. 

**The rule: `ez_filter_hz` is no more than 255, although the CLI accepts up to 300.** The delay for the Smith predictor is computed by a function with an 8-bit argument, and what is left of the number is the remainder of the division by 256. 300 turns into 44 and gives 3.6 ms instead of 0.53. 256 turns into 0 — a division by zero, and the delay is infinite; 257, 258, 259 and 260 give 159, 80, 53 and 40 ms. The Smith predictor buffer is 65 samples, that is, no more than 32 ms at a `looptime` of 500, and the firmware does not check the length: already 40 ms is 79 samples, the write goes past the end of the buffer and corrupts the neighboring variables of the PID controller. This is memory corruption in the stabilization task without a single message: the behavior of the aircraft is unpredictable. From 261 the buffer is intact, but the delay is still wrong (at 261 — 31.8 ms instead of 0.61). The same code is in 8.0.1.

### Multirotor navigation PIDs
{{diagram:inav-mc-nav-cascade|Navigation does not drive the motors directly: position gives velocity, velocity gives acceleration and an angle, and after that the same ANGLE and rate loops work, so the outer loops are tuned only after the inner ones.}}

The cascade structure is covered in ctl-theory; here are its numbers. The navigation units are centimeters and cm/s.

| Setting | Default | Scale | Meaning |
|---|---|---|---|
| `nav_mc_pos_xy_p` | 65 | / 100 → 0.65 1/s | position error → desired velocity: 1 m of error = 0.65 m/s |
| `nav_mc_vel_xy_p` | 40 | / 20 → 2.0 1/s | velocity error → acceleration: 1 m/s = 2 m/s² |
| `nav_mc_vel_xy_i` | 15 | / 100 | wind compensation |
| `nav_mc_vel_xy_d` | 100 | / 100 | damping on the measured velocity; the filter `nav_mc_vel_xy_dterm_lpf_hz` is 2 Hz |
| `nav_mc_vel_xy_ff` | 40 | / 100 | acceleration from the desired velocity itself |
| `nav_mc_pos_z_p` | 50 | / 100 → 0.5 1/s | altitude error → vertical velocity |
| `nav_mc_vel_z_p` | 100 | / 66.7 → 1.5 µs/(cm/s) | vertical velocity error → throttle correction |
| `nav_mc_vel_z_i` | 50 | / 20 → 2.5 | holds the difference between `nav_mc_hover_thr` and the real hover throttle |
| `nav_mc_vel_z_d` | 10 | / 100 | damping |
| `nav_mc_heading_p` | 60 | / 30 → 2 (°/s)/° | heading error → yaw rate, with the ceiling `heading_hold_rate_limit` of 90 °/s |

The range of each is 0…255, and all of them are in the control profile. The scales are the same in 8.0.1.

**Altitude.** Throttle = `nav_mc_hover_thr` (1300, range 1000…2000) + the output of the vertical velocity controller smoothed by a 4 Hz filter. If hover_thr is far from the real hover throttle, I holds the difference, and when ALTHOLD is enabled the aircraft sags or jumps until I has built up. The desired velocity comes from a sqrt controller: linear near the target (`nav_mc_pos_z_p`), farther away — along a square root with an acceleration limit, and the ceiling is `nav_mc_manual_climb_rate` (200 cm/s) under stick control and `nav_mc_auto_climb_rate` (500 cm/s) in RTH and a mission (both 10…2000). The gains will not raise this ceiling. `nav_mc_althold_throttle` (`STICK`, `MID_STICK`, `HOVER`) selects which throttle stick position counts as zero velocity.

**Position.** The desired velocity is limited by `nav_manual_speed` (750 cm/s) under stick control and by `nav_auto_speed` (500) in RTH and a mission; `nav_max_auto_speed` (1000) is the ceiling of the speed set in a mission waypoint itself (all 10…2000, inav-missions). The acceleration is limited to 980 cm/s² with a jerk of 1700 cm/s³ and is converted to an angle: θ = atan(a / g), no more than `nav_mc_bank_angle` (35°, 15…45). Hence the limit a = g · tan 35° = 6.87 m/s². The navigation angle is additionally clipped by `max_angle_inclination_*`: if that is smaller than `nav_mc_bank_angle`, the smaller one applies. `nav_mc_pos_expo` (10) softens the desired velocity near the target.

**Stopping.** When the stick is released, the target is placed ahead: the current position + velocity × `nav_mc_pos_deceleration_time` / 100 (120 → 1.2 s, range 0…255). If the aircraft needs more room, it overshoots the target and comes back. The MC BRAKING mode (it needs `nav_user_control_mode = CRUISE` and the mode enabled on a switch) instead fixes the point at once and brakes harder:

| Setting | Default | Meaning |
|---|---|---|
| `nav_mc_braking_speed_threshold` | 100 cm/s | braking engages above this speed |
| `nav_mc_braking_disengage_speed` | 75 cm/s | and ends below this one |
| `nav_mc_braking_timeout` | 2000 ms | or on time |
| `nav_mc_braking_boost_factor` | 100 % | the acceleration boost in the boost phase |
| `nav_mc_braking_boost_speed_threshold`, `nav_mc_braking_boost_disengage_speed` | 150 and 100 cm/s | the limits of the boost phase |
| `nav_mc_braking_boost_timeout` | 750 ms | the limit of its duration |
| `nav_mc_braking_bank_angle` | 40° (15…60) | the angle limit in the boost phase |

**The estimator.** The navigation PIDs work not with GPS and the barometer but with the estimate of position and velocity (est-alt-sources). In 9.0 the defaults of the altitude weights changed: `inav_w_z_baro_v` 0.1 → 0.35, `inav_w_z_gps_p` 0.2 → 0.35, `inav_w_z_gps_v` 0.1 → 0.35; `inav_w_z_baro_p` stayed at 0.35, and the horizontal `inav_w_xy_gps_p` = 1.0 and `inav_w_xy_gps_v` = 2.0 did not change. At the same time the corrections from the barometer and GPS started to be applied once per sensor update, and between them the estimate runs on the accelerometer: the 9.x estimator relies more on the accelerometer, and `nav_mc_vel_z_p` and `nav_mc_pos_z_p` raised for 8.x cause throttle oscillation (inav-intro). The weights are not a remedy for oscillation: PIDs first.

### The tuning order for a GPS copter
You tune from the inside out: an outer loop cannot be faster than the inner one (math-ode-dyn, ctl-theory).

| Step | What you tune | What to look at in Blackbox | The sign of “done” |
|---|---|---|---|
| 1 | `nav_mc_hover_thr` | `rcCommand[3]` in a steady hover in ANGLE | the value is written to the battery profile |
| 2 | Filters | `gyroRaw` and `gyroADC`, `gyroPeakRoll[0…2]` | the noise in `gyroADC` is small, the motors after a hover are warm, not hot |
| 3 | Rate: P, D, then I and CD | `axisRate[n]` (setpoint) and `gyroADC[n]`; `axisP`, `axisI`, `axisD`, `axisF` | the gyro follows the setpoint without overshoot or oscillation |
| 4 | ANGLE: `mc_p_level` | `attitude[0,1]` after the stick is released | a return to level without rocking |
| 5 | Altitude: `nav_mc_vel_z_*`, then `nav_mc_pos_z_p` | `navTgtVel[2]` and `navVel[2]`, `navTgtPos[2]` and `navPos[2]`, `mcVelAxisP[2]`, `mcVelAxisI[2]`, `mcVelAxisOut[2]` | the throttle does not “breathe”, the altitude is within ±0.5 m |
| 6 | Position: `nav_mc_vel_xy_*`, then `nav_mc_pos_xy_p`, stopping | `navTgtVel[0,1]` and `navVel[0,1]`, `navTgtPos` and `navPos`, `mcPosAxisP`, `mcVelAxisOut[0,1]`, `navTgtHdg` | it stops without coming back and holds the point in wind |

By default Blackbox logs the groups `NAV_PID`, `NAV_POS`, `MAG`, `ACC`, `ATTI`, `RC_DATA`, `RC_COMMAND`, `MOTORS`, `SERVOS`; `gyroRaw` and the FFT peaks are enabled with the commands `blackbox GYRO_RAW` and `blackbox PEAKS_R` (`PEAKS_P`, `PEAKS_Y`). Reading logs is in bf-blackbox, preparing the aircraft is in `inav-setup-scratch`.

A spiral in POSHOLD with a growing radius (toilet bowl) is not a PID problem. The acceleration is computed in north–east axes and rotated into the aircraft axes by the current heading; a heading error rotates the correction, and the aircraft flies past the point along an arc. The fix is the compass (alignment, calibration, interference — inav-gps), and in the air — an immediate switch to ANGLE with a switch whose position you know without looking.

### Place in the system
- **Receives:** an assembled and calibrated aircraft and the first hover log (`inav-setup-scratch`); the position and velocity estimate from the estimator (`est-alt-sources`, `inav-gps`); the `mmix` table through which the ±500 units of each axis go out (`inav-mixer-vtol`); the theory of cascades and stability margins (`ctl-theory`, `math-ode-dyn`).
- **Provides:** tuned rate and ANGLE loops to all modes; the navigation PIDs and limits — to RTH and missions (`inav-gps`, `inav-missions`); the profile values — to the backup (`inav-cli-backup`).
- **If you get it wrong here:** a raised `nav_mc_vel_z_p` shows up as throttle oscillation in RTH and a mission; an RPM filter without an ESC telemetry port — as hot motors with the filter “enabled”; `nav_mc_bank_angle` greater than `max_angle_inclination_*` — as drifting off the point in wind; a rate carried over from Betaflight without conversion is rejected by the CLI or makes the aircraft uncontrollably sharp.

## practice
No hardware or simulator is needed: a calculator is enough. All the numbers below were produced by a script that repeats the arithmetic of `ez_tune.c`, `rc_curves.c` and `pid.c`; the config fragments are teaching examples assembled by hand from the 9.1.0 names, not the output of a real aircraft.

### Step 1. Gains and the rate from a `diff` fragment
A teaching example assembled by hand:

```text
# control_profile
control_profile 1

set mc_p_pitch = 48
set mc_i_pitch = 36
set mc_d_pitch = 27
set mc_cd_pitch = 70
set mc_p_roll = 44
set mc_i_roll = 33
set mc_d_roll = 25
set mc_p_level = 26
set max_angle_inclination_rll = 350
set max_angle_inclination_pit = 350
set tpa_rate = 20
set tpa_breakpoint = 1600
set rc_expo = 60
set roll_rate = 36
set pitch_rate = 36
set yaw_rate = 25
```

Find: a) kP, kI, kD and kCD of roll and pitch; b) the roll P term at an error of 50 °/s and its share of the limit; c) the roll rate at full stick and at 60 % of the travel; d) by what factor TPA attenuates P and D at throttle 1800 and what happens to I; e) the rate setpoint in ANGLE at an angle error of 10° and the angle limit in degrees. `diff` prints only the differences from the defaults: what is not in it is taken from the defaults table.

### Step 2. EZ Tune: three sets of sliders
Calculate the values EZ Tune writes for sets A, B and C and fill in the table (the PIDs of the three axes, the rates, expo, five filter values, `d_boost_min`). Drop the fractional part.

| Slider | A | B (7 inches, long range) | C (5 inches, lively) |
|---|---|---|---|
| `ez_filter_hz` | 110 | 90 | 160 |
| `ez_axis_ratio` | 110 | 120 | 105 |
| `ez_response` | 100 | 80 | 115 |
| `ez_damping` | 100 | 120 | 90 |
| `ez_stability` | 100 | 100 | 112 |
| `ez_aggressiveness` | 100 | 60 | 150 |
| `ez_rate` | 100 | 60 | 150 |
| `ez_snappiness` | 0 | 0 | 40 |

Then answer: which sliders in set B changed pitch D from 25 to 33; which slider in C changed `setpoint_kalman_q`; why in B roll I stayed at 75 while pitch I rose to 90.

### Step 3. Symptom → setting and direction
For each case name one setting, the direction of the change and the reason from the loop structure.

1. POSHOLD. You fly at 10 m/s and release the stick. The aircraft stops after 16 m, then comes back 4 m. `nav_mc_pos_deceleration_time = 120`.
2. RTH. The climb to the return altitude goes at 1.5 m/s, with the throttle around 1600 out of 2000. The `diff` has `nav_mc_auto_climb_rate = 150`.
3. POSHOLD. The aircraft circles around the point, and the radius grows from 2 to 6 m in 20 s. It flies normally in ANGLE. In the log `navTgtPos` is constant, and `navPos` traces a spiral.
4. ALTHOLD after an upgrade from 8.0. The altitude oscillates by ±0.5 m with a period of about 1 s, and `rcCommand[3]` swings by ±150 around 1480. In the `diff`: `nav_mc_vel_z_p = 150`, `nav_mc_hover_thr` is not set.

### Step 4. Three errors in a config
A teaching example assembled by hand. A 7-inch quadcopter, the owner came from Betaflight. Find three errors and the consequences of each.

```text
serial 1 2 115200 115200 0 115200
serial 2 64 115200 115200 0 115200
set looptime = 500
set gyro_main_lpf_hz = 110
set rpm_gyro_filter_enabled = ON
set motor_pwm_protocol = DSHOT300
set nav_mc_bank_angle = 40
set nav_manual_speed = 1000

# control_profile
control_profile 1

set mc_p_roll = 55
set max_angle_inclination_rll = 300
set max_angle_inclination_pit = 300
set ez_enabled = ON
set ez_filter_hz = 90
set ez_response = 80
```

### Moving to real hardware
The order is the same as in the table “The tuning order for a GPS copter”. The props come off for the whole time you work with the CLI and go on only before the flight. Before the first flight after changing PIDs or filters: a `diff all` backup (`inav-cli-backup`), the ANGLE switch in a known position, an altitude of no more than 3 m, after 30 seconds of hover — land and check the motors by hand. Hot motors mean that the filters let noise through: restore the previous cutoff. Change one group of settings per flight. The criteria for hardware: in the hover log `gyroADC` follows `axisRate` without oscillation; in ALTHOLD the altitude holds within ±0.5 m; after the stick is released in POSHOLD the aircraft does not come back by more than 1 m.

Self-check: the lab is done when:
- step 1: kP, kI, kD, kCD of roll and pitch match the reference to the third significant digit; the rate at 60 % stick is 133 °/s (±1); the TPA factor is 0.90; the ANGLE setpoint is 39.6 °/s (±0.2);
- step 2: all the numbers of tables B and C match the reference (integers exactly, `smith_predictor_delay` to ±0.01 ms), and the sliders for the three questions are named;
- step 3: in each of the four cases the same setting and the same direction as in the reference are named, with the reason;
- step 4: three errors are named, and for the third the acceleration limit of 5.66 m/s² (±0.05) is calculated;
- (hardware, if you have an aircraft) the three criteria from the section on moving to hardware are met.

**Reference for the self-check.**

Step 1. Roll: kP = 44 / 31 = 1.419, kI = 33 / 4 = 8.25, kD = 25 / 1905 = 0.01312, kCD = 60 / 7270 = 0.00825 (the `diff` has no `mc_cd_roll` — the default 60 applies). Pitch: 1.548, 9.0, 0.01417, 0.00963. P at 50 °/s = 71 units, which is 14 % of 500. Full stick — 360 °/s. At 60 %: rcCommand = 500 · 0.6 · (1 − 0.6 · (1 − 0.36)) = 184.8 → 185, ω = 185 / 500 · 360 = 133.2 °/s. TPA at 1800: (100 − 20 · 200 / 400) / 100 = 0.90 — P and D are multiplied by 0.9 (roll kP 1.277), I does not change. ANGLE: 10 · 26 / 6.56 = 39.6 °/s, the angle limit is 35°. Typical errors: kI = 1.06 — I was divided by 31, like P; a rate of 36 °/s — the factor of 10 was forgotten; 216 °/s at 60 % — expo was forgotten; I was multiplied by 0.9 too — in the multirotor branch TPA does not act on I.

Step 2.

| Setting | A | B | C |
|---|---|---|---|
| Roll P / I / D / CD | 40 / 75 / 23 / 100 | 32 / 75 / 27 / 60 | 46 / 84 / 20 / 150 |
| Pitch P / I / D / CD | 44 / 82 / 25 / 110 | 38 / 90 / 33 / 72 | 48 / 88 / 21 / 157 |
| Yaw P / I / D / CD | 45 / 80 / 0 / 100 | 40 / 80 / 0 / 80 | 48 / 84 / 0 / 125 |
| `roll_rate` = `pitch_rate` / `yaw_rate` | 60 / 50 | 48 / 38 | 75 / 65 |
| `rc_expo` = `rc_yaw_expo` | 70 | 58 | 85 |
| `gyro_main_lpf_hz` / `dterm_lpf_hz` | 110 / 105 | 90 / 85 | 160 / 155 |
| `dynamic_gyro_notch_min_hz` | 73 | 60 | 106 |
| `setpoint_kalman_q` | 200 | 200 | 213 |
| `smith_predictor_delay`, ms | 1.45 | 1.77 | 0.99 |
| `d_boost_min` | 1.0 | 1.0 | 0.6 |

Pitch D in B: 23 · 120 / 100 = 27.6, then · 1.20 = 33.12 → 33 — two sliders are at work, `ez_damping` and `ez_axis_ratio`. `setpoint_kalman_q` in C is changed by `ez_filter_hz`: 160 ≥ 150, so 200 + 200 · 10 / 150 = 213. I in B: `ez_stability` = 100, so roll stayed at 75, and pitch = 75 · 1.20 = 90 — `ez_axis_ratio` raised it. Typical errors: a pitch D of 32 — the fraction of roll was dropped first (27) and then it was multiplied by 1.2; yaw calculated like roll (P = 36 instead of 40 in B) — the half sensitivity was forgotten; `rc_expo` left at 70 in all sets — expo depends on `ez_rate`.

Step 3.

| Case | Setting and direction | Reason |
|---|---|---|
| 1 | `nav_mc_pos_deceleration_time` ↑ to 160 or higher | the target is placed 10 · 1.2 = 12 m ahead, and the aircraft needs 16 m: it passes the target and comes back. 16 m / 10 m/s = 1.6 s. The alternative is the MC BRAKING mode |
| 2 | `nav_mc_auto_climb_rate` ↑ (default 500) | the ceiling of the desired vertical velocity is 150 cm/s; the throttle is not at the limit, so there is thrust in reserve. The `nav_mc_vel_z_*` gains do not raise the ceiling |
| 3 | leave the PIDs alone; the compass: alignment, calibration, interference | a heading error rotates the acceleration correction relative to the direction to the point. In the air — ANGLE at once |
| 4 | `nav_mc_vel_z_p` ↓ to 100; `nav_mc_hover_thr` = 1480 | 150 / 66.7 = 2.25 µs per cm/s against 1.5: the inner altitude loop is overtuned, and the 9.x estimator relies more on the accelerometer, so the old margin is gone. A hover_thr of 1300 makes I hold 180 µs |

Typical errors: in case 1 raising `nav_mc_pos_xy_p` — the target stays at 12 m, and the return becomes sharper; in case 3 lowering `nav_mc_vel_xy_p` — the spiral becomes slower but does not go away; in case 4 changing the `inav_w_z_*` weights instead of the PIDs.

Step 4. 1) `rpm_gyro_filter_enabled = ON`, but no port has function 262144: the filter is not initialized, and DShot in INAV does not return RPM. You need an ESC telemetry wire to the RX of a free UART and `serial <n> 262144 …`. 2) `ez_enabled = ON` together with a manual `mc_p_roll = 55` and `gyro_main_lpf_hz = 110`: at boot EZ Tune writes roll P = 40 · 80 / 100 = 32 and a cutoff of 90 Hz. You have to change `ez_response` and `ez_filter_hz` or turn EZ Tune off. 3) `nav_mc_bank_angle = 40` with `max_angle_inclination_*` = 300: navigation is limited to 30°, the acceleration limit is g · tan 30° = 5.66 m/s² instead of 8.23 — in strong wind the aircraft drifts off the point, and ANGLE will not give more than 30° either. Not errors: `DSHOT300`, `looptime = 500` (the default; a real `diff` would not have this line), `nav_manual_speed = 1000`. A typical miss is to call the absence of `dshot_bidir` an error: INAV has no such setting.

## diagnostics
- **Symptom:** after moving settings from Betaflight the CLI answers `set roll_rate = 670` with an error
  - Possible cause: INAV rates are set in tens of °/s, range 4…180.
  - What to do: 670 °/s is `roll_rate = 67`; work out expo again with the `rc_curves.c` formula.
- **Symptom:** `profile 2` — the CLI does not know such a command
  - Possible cause: the guide was written for old versions.
  - What to do: `control_profile 2`; for the battery and mixer profiles — `battery_profile`, `mixer_profile`.
- **Symptom:** PIDs set in the CLI went back to other values after a reboot
  - Possible cause: `ez_enabled` is on, and EZ Tune recalculates the PIDs, rates and filters at every boot.
  - What to do: change the `ez_*` sliders or `set ez_enabled = OFF`, and then tune by hand.
- **Symptom:** the RPM filter is enabled, but the motor peaks are still in the gyro spectrum, and the motors are hot
  - Possible cause: no port with function 262144, or the ESC does not send telemetry; a wrong `motor_poles`.
  - In the log: `gyroPeakRoll[0]` moves together with the throttle, `gyroADC` is noisy.
  - What to do: check the RPM with the OSD element “Motor RPM from ESC telemetry” (the Outputs tab of Configurator 9 does not show RPM) and the ESC temperatures in `status`; until it is fixed turn `rpm_gyro_filter_enabled` off and keep the dynamic notch.
- **Symptom:** at mid throttle the aircraft flies normally, but in a sharp climb or at full throttle it starts to shake and flips
  - Possible cause: `tpa_rate` is greater than 100 — above a throttle of breakpoint + (2000 − breakpoint) · 100 / `tpa_rate` the TPA factor is negative, and P and D work with the opposite sign.
  - In the log: at a high `rcCommand[3]` the sign of `axisP` is opposite to the sign of the error `axisRate − gyroADC`, and the oscillation grows.
  - What to do: on the ground `set tpa_rate` to no more than 100 (0 to start with); check that the value was not carried over from an airplane profile.
  - Consequences: a flip and a crash at full throttle, that is, on takeoff or when avoiding an obstacle.
- **Symptom:** after `set ez_filter_hz` above 255 stabilization behaves unpredictably: jitter, jerks, the aircraft does not hold level
  - Possible cause: `ez_filter_hz` = 256…260 — a Smith predictor delay from 40 ms to infinite with a buffer of 65 samples (32 ms at a `looptime` of 500): the write goes past its end (certainly at 258–260) and corrupts the memory of the PID controller; 261…300 — the buffer is intact, but the delay is wrong.
  - What to do: do not take off; `set ez_filter_hz` to no more than 255, `save`, reboot; check that `get smith_predictor_delay` shows less than 8.
  - Consequences: memory corruption in the stabilization task, a crash without error messages.
- **Symptom:** the aircraft is sluggish, “floats” behind the stick, slow oscillation in a descent
  - Possible cause: the 60 Hz cutoff and the default PIDs are designed for a heavy aircraft; a large filter delay.
  - What to do: raise `gyro_main_lpf_hz` (or `ez_filter_hz`) in steps of 10–20 Hz, watching the motor temperature; then P.
- **Symptom:** high-frequency jitter, the motors are hot after 30 s of hover
  - Possible cause: the filter cutoff is too high, D or P is large.
  - In the log: `axisD` is noisy with an amplitude comparable to `axisP`.
  - What to do: restore the cutoff, lower `mc_d_*` or `ez_damping`; check the props and the flight controller mounting.
- **Symptom:** when ALTHOLD is enabled the aircraft sags or jumps
  - Possible cause: `nav_mc_hover_thr` is far from the real hover throttle; `nav_mc_althold_throttle = STICK` with the stick not at the hover position.
  - In the log: after the mode is enabled `mcVelAxisI[2]` slowly moves to a large constant value.
  - What to do: write the hover throttle from `rcCommand[3]`; `MID_STICK` or `HOVER` if you prefer.
- **Symptom:** the throttle “breathes” in ALTHOLD, RTH and a mission
  - Possible cause: `nav_mc_vel_z_p` or `nav_mc_pos_z_p` are raised, often after an upgrade from 8.x.
  - What to do: restore 100 and 50, then change `nav_mc_vel_z_p` in steps of 10–20 %.
- **Symptom:** after the stick is released in POSHOLD the aircraft overshoots and comes back
  - Possible cause: the stop target is closer than the real braking distance.
  - What to do: raise `nav_mc_pos_deceleration_time`; or `nav_user_control_mode = CRUISE` and the MC BRAKING mode.
- **Symptom:** the aircraft circles in POSHOLD, and the radius grows
  - Possible cause: a heading error — the compass, not the PIDs.
  - What to do: switch to ANGLE at once and land; check the alignment and calibration of the compass and interference from the power wires.
  - Consequences: if you continue, the spiral accelerates into a flyaway.
- **Symptom:** in wind the aircraft drifts off the point although the angle is small
  - Possible cause: `nav_mc_bank_angle` or `max_angle_inclination_*` limit the angle; the acceleration g · tan θ is not enough.
  - In the log: `attitude` sits at the limit, `navVel` does not catch up with `navTgtVel`.
  - What to do: raise the smaller of the two limits, making sure there is enough thrust to hold altitude at that angle.

## checklist
- A `diff all` backup is taken before the changes, the props are off while working with the CLI
- `nav_mc_hover_thr` is written to the battery profile from the hover log
- The rates are checked: the number × 10 = °/s; `manual_*` were not touched
- It is decided who owns the PIDs: EZ Tune or manual values, not both at once
- `tpa_rate` is no more than 100, `ez_filter_hz` is no more than 255
- The RPM filter is enabled only with working ESC telemetry and a correct `motor_poles`
- `nav_mc_bank_angle` is no greater than `max_angle_inclination_*`
- Rate and ANGLE are tuned before the navigation PIDs; one group was changed per flight
- The ANGLE switch is in a known position for getting out of POSHOLD

## references
- pid.h — P/I/D/CD scales, limits, INAV 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/flight/pid.h | primary | A
- pid.c — the multirotor rate controller, TPA, ANGLE/HORIZON, D-boost, INAV 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/flight/pid.c | primary | A
- ez_tune.c — the EZ Tune formulas, INAV 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/flight/ez_tune.c | primary | A
- rc_curves.c — the expo curve, INAV 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/fc/rc_curves.c | primary | A
- control_profile.c — the contents of the rate and TPA group, INAV 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/fc/control_profile.c | primary | A
- gyro.c — the order of the gyro filters, INAV 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/sensors/gyro.c | primary | A
- rpm_filter.c — the RPM notch, INAV 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/flight/rpm_filter.c | primary | A
- esc_sensor.c — ESC telemetry over a UART, motor polling, INAV 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/sensors/esc_sensor.c | primary | A
- kalman.c — the gyro Kalman filter, INAV 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/flight/kalman.c | primary | B
- smith_predictor.c — Smith predictor, INAV 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/flight/smith_predictor.c | primary | B
- navigation_multicopter.c — the altitude and position loops, braking, INAV 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/navigation/navigation_multicopter.c | primary | A
- navigation.c — the navigation PID scales (navPidInit), speeds, INAV 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/navigation/navigation.c | primary | A
- sqrt_controller.c — the altitude controller, INAV 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/navigation/sqrt_controller.c | primary | B
- fp_pid.c — the common navigation PID, INAV 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/common/fp_pid.c | primary | B
- blackbox.c — the log field names, INAV 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/blackbox/blackbox.c | primary | A
- settings.yaml — defaults and ranges, INAV 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/fc/settings.yaml | primary | A
- INAV PID Controller — INAV docs 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/docs/INAV%20PID%20Controller.md | primary | A
- Control Profiles — INAV docs 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/docs/Control%20Profiles.md | primary | B
- Navigation — INAV docs 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/docs/Navigation.md | primary | B
- messages.json — the tooltips of the Ez Tune tab, Configurator 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav-configurator/9.1.0/locale/en/messages.json | primary | B
- pid.h — PID scales and defaults, Betaflight 2025.12.5 | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/flight/pid.h | primary | B

## notes
The documents in the 9.1.0 tag lag behind the code in places. `docs/Settings.md` describes `looptime` with a recommendation of 3500 µs and `dynamic_gyro_notch_min_hz` with a “default of 150” — the defaults in `settings.yaml` are 500 and 50. `docs/Navigation.md` names the setting `nav_use_midthr_for_althold`, which does not exist in 9.1.0: it is replaced by `nav_mc_althold_throttle`. `docs/INAV PID Controller.md` speaks of two LPFs on D — in `pid.c` 9.1.0 there is one D filter. The `feature` name table in `cli.c` still has the name `RPM_FILTERS`, but the code does not check this flag: the RPM filter is enabled by `rpm_gyro_filter_enabled` and an ESC telemetry port. The estimate “no more than 290 times a second per motor” was derived from the frame length and the port baud rate; this module did not measure the real rate of a particular ESC.
