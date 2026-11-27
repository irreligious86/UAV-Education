---
id: bf-rates-rc
title: "Rates, RC smoothing and feedforward: from the stick to the setpoint"
level: L2
readingTime: 55 min
firmware: Betaflight 2025.12 (checked against 2025.12.5) and 4.5.3 (the FF pipeline, the RX rate estimate); the labs were captured on the 4.5.x sources (the 4.5-maintenance branch, 7dcc851; version.h 4.5.6, the latest release is 4.5.5) and 4.5.3
status: published
added: 2026-11-14
tags:
  - Betaflight
  - rates
  - RC smoothing
  - feedforward
  - ELRS
related:
  - bf-intro
  - bf-pid-reg-in-bf
  - bf-pid
  - bf-blackbox
  - bf-modes-osd
  - link-elrs
  - link-protocols
  - bf-cli
  - bf-adjustments
  - link-edgetx
next:
  - bf-pid
source: content/betaflight/bf-rates-rc.md
source_hash: 0e241887d6a6
---

## summary
This module follows a command from the stick to the setpoint — the desired angular rate that PID compares the gyro against. It covers channel calibration (`rxrange`), the formulas of the five rate types from `fc/rc.c`, the throttle curve, rate profiles, RC smoothing with its cutoff frequency chosen automatically from the receiver rate, and feedforward with its anti-jitter filters. The lab is a Python port of the firmware formulas. It converts rates between Actual, Betaflight and Quick while keeping the center and the maximum, and models the PT3 smoothing of a stick step on ELRS at 50…1000 Hz; a second script reproduces the 4.5.3 feedforward pipeline (jitter, duplicates, boost, the limit near the maximum rate) and teaches you to read `debug_mode = FEEDFORWARD`. Then on hardware: checking `rxrange`, reading `rc_smoothing_info` with a real link, and a blind comparison of rate profiles switched in flight.

## theory
### The chain from the stick to PID
The processing order (`rx/rx.c`, `fc/rc.c`, `flight/mixer.c`; the same in 4.5 and 2025.12):

1. The receiver delivers a channel in microseconds. CRSF/ELRS: 172…1811 → **988…2012 µs** (`rx/crsf.c`).
2. `rxrange` stretches the first four channels (after `map`) from `min…max` to 1000…2000. AUX channels are not scaled.
3. The validity check: outside `rx_min_usec`…`rx_max_usec` (885…2115) a channel is considered bad. It holds the last value for 300 ms, then gets the value from `rxfail`, and for channels 0–3 Betaflight declares signal loss (failsafe).
4. Roll/pitch/yaw: `rcCommand = rcData − mid_rc` with `deadband` (`yaw_deadband`) subtracted, limited to ±500. The deflection `x = rcCommand / (500 − deadband)` ∈ [−1; 1]. In this module “full travel” is from stop to stop, 1000 units of `rcCommand`; “half travel” is from center to stop, 500 units, x = 1.
5. `applyRates(x)` gives °/s, followed by the `*_rate_limit` limit (1998 by default). The result is rawSetpoint.
6. Feedforward is computed from rawSetpoint on every new RC packet.
7. RC smoothing (PT3) smooths the setpoint and feedforward at the PID loop rate. From there PID takes them.
8. Throttle: `(rcData − min_check)·1000/(2000 − min_check)` → the `thr_mid`/`thr_hover`/`thr_expo` curve → the throttle PT3 → `throttle_limit_*` in the mixer.

{{diagram:chart-bf-rates-curves|The center and the maximum do not yet define the stick feel. Actual 20/67/54 and Betaflight 1.01/0.70/0.01 agree to within 4 °/s. The default Actual 7/67/0 (70 → 670 °/s), with the same center and maximum in Betaflight, differs by up to 151 °/s in the middle of the travel.}}

### The five rate types (`rates_type`, ACTUAL by default)
Which type to choose: Actual — its center, maximum and expo are independent, it is the default, and the same type is set in the simulator so that the skill carries over (`ops-pilot-training`, the starting numbers are there too). Another type — only if you are carrying over someone else's profile: the numbers are not converted when the type is changed.

The values are stored as integers: `rc_rate`, `srate`, `expo` per axis `roll_`/`pitch_`/`yaw_`. Below, `x` is the stick deflection and `e = expo/100`. The formulas are taken from the `apply*Rates()` functions.

| Type | Formula, °/s | Center (slope at x→0) | Maximum (x = 1) |
|---|---|---|---|
| BETAFLIGHT | x' = x·\|x\|³·e + x·(1−e); 200·r·x' / (1 − \|x\|·s), r = rc_rate/100 (for r > 2: r += 14.54·(r−2)), s = srate/100 | 200·r·(1−e) | 200·r / (1−s) |
| ACTUAL | C·x + (M−C)·\|x\|·(x⁵·e + x·(1−e)), C = rc_rate·10, M = srate·10 | C | M |
| QUICK | R·x / (1 − c·k), R = rc_rate·2, k = (M/R − 1)/(M/R), c = \|x\|³·e + \|x\|·(1−e) | R | M = srate·10 |
| KISS | 2000·(rc_rate/1000)·(x³·e + x·(1−e)) / (1 − \|x\|·srate/100) | 2·rc_rate·(1−e) | 2·rc_rate / (1 − srate/100) |
| RACEFLIGHT | 10·rc_rate·x·(1 + e·(x²−1))·(1 + \|x\|·srate/100) | 10·rc_rate·(1−e) | 10·rc_rate·(1 + srate/100) |

Conclusions from the formulas:
- In Actual the three parameters are independent: center sensitivity, max rate, expo. In Quick the center (rc_rate·2) and the maximum (srate·10) are set directly, and the shape between them is set by expo together with the ratio M/R. In Betaflight, KISS and RaceFlight every number changes both the center and the maximum.
- In Betaflight expo does not touch the maximum but multiplies the slope at the center by (1 − e). Super rate raises the end of the curve with the hyperbola 1/(1 − |x|·s).
- The default is ACTUAL 7/67/0 (in both 4.5 and 2025.12): a center of 70 °/s and a maximum of 670 °/s. With expo = 0 the Actual curve is not linear: the quadratic term (M−C)·x·|x| gives 150 of the 185 °/s at half travel.
- QUICK with `quickrates_rc_expo = ON` applies expo to the stick itself, not only to the super factor.
- The limits per type (`validateAndFixRatesSettings`, `config/config.c`) clip the values when the config is loaded. rc_rate/srate: BETAFLIGHT 255/100, ACTUAL 200/200, QUICK 255/200, KISS 255/99, RACEFLIGHT 200/255. Expo is up to 100 everywhere. When `rates_type` is changed in the CLI the numbers are not converted: the same 7/67/0 in Betaflight gives 14 °/s at the center.

### Actual in the code: center, maximum, expo
The function from `fc/rc.c` 4.5.3, lines 209–219 (in 2025.12 the body is the same, only `static` was added):
```c
float applyActualRates(const int axis, float rcCommandf, const float rcCommandfAbs)
{
    float expof = currentControlRateProfile->rcExpo[axis] / 100.0f;
    expof = rcCommandfAbs * (power5(rcCommandf) * expof + rcCommandf * (1 - expof));
    const float centerSensitivity = currentControlRateProfile->rcRates[axis] * 10.0f;
    const float stickMovement = MAX(0, currentControlRateProfile->rates[axis] * 10.0f - centerSensitivity);
    const float angleRate = rcCommandf * centerSensitivity + stickMovement * expof;
    return angleRate;
}
```
The three numbers work as follows:
- `centerSensitivity` C = `rc_rate`·10 — the slope of the curve at zero (center sensitivity). The second term grows as x² and its derivative at zero is 0, so the sensitivity near the center is set by C alone.
- `stickMovement` = max(0, `srate`·10 − C) — the addition that raises the end to the maximum M = `srate`·10 (max rate). If `srate`·10 < C, the addition is zeroed: the curve is the straight line C·x, the maximum equals C, and `srate` is ignored.
- `expof` = |x|·(x⁵·e + x·(1 − e)). At e = 0 this is x·|x|, a parabola. At e = 1 it is x⁵·|x|: almost zero up to half travel, with a sharp rise near the end. Expo redistributes the addition along the travel and does not touch the ends of the curve (0 and M).

Worked numbers: the default 70/670/0 (`7/67/0`) and a “freestyle” 200/850/0.20 (`20/85/20`), with the stick at half travel (x = 0.5):
- 70/670/0: expof = 0.5·(0 + 0.5·1) = 0.25; setpoint = 0.5·70 + 600·0.25 = 35 + 150 = **185 °/s**.
- 200/850/0.20: expof = 0.5·(0.5⁵·0.2 + 0.5·0.8) = 0.5·(0.00625 + 0.4) = 0.203125; setpoint = 0.5·200 + 650·0.203125 = 100 + 132.0 = **232.0 °/s**.

The slope at the stop is the derivative at x = 1: C + (M − C)·(2 + 4e). That is 70 + 600·2 = 1270 and 200 + 650·2.8 = 2020 °/s per full travel, that is, **12.7 and 20.2 °/s per 1 % of travel**. At the center — 0.7 and 2.0 °/s per 1 %. At half travel the second profile is faster by only 47 °/s (25 %), near the center — almost three times, at the stop — by 180 °/s. That is why profiles are compared at three points (center, middle, maximum) and not by the maximum alone.

{{diagram:chart-bf-actual-two-profiles|The dashed line is the linear part C·x: for the default 70/670/0 almost all of the setpoint at mid-travel (150 of 185 °/s) comes from the quadratic addition, while for 200/850/0.20 the linear part is larger (100 of 232 °/s). That is why the second profile is sharper near the center, although the difference at mid-travel is only 47 °/s.}}

### The maximum rate by aircraft class
The starting rates by style (freestyle, racing, filming) are in `ops-pilot-training`, and all of them are for a 5". The same maximum does not suit a heavy aircraft: its angular acceleration α = ΔT·L / I is 10–20 times lower: for a 5" 75 rad/s² (≈ 4300 °/s², the `f-physics` estimate) … 125 rad/s² (`f-mechanics`), for a 15" X8 — about 6.7 rad/s², that is, 380 °/s² (`f-mechanics`). A setpoint that the frame cannot reach in time keeps the motors saturated, accumulates I and gives a bounce at the end of the maneuver.

**The rule (a course estimate).** The maximum M is no higher than what the aircraft reaches in 0.25–0.5 s: M ≤ α × (0.25…0.5 s). For a 5" the calculation uses the lower, cautious estimate α = 75 rad/s²: 1070–2150 °/s — the default 670 °/s is below this bound, and freestyle rates fit within it (with α = 125 rad/s² the bound would be 1790–3580 °/s); for an X8 with 380 °/s² — 95–190 °/s. The α of your own aircraft is an estimate per `f-mechanics` or from a log: the steepest slope of the gyro trace on a sharp full-stick input. In Actual the maximum is `srate` × 10, and if it is below the center C = `rc_rate` × 10, the curve becomes a straight line with a maximum of C (the section “Actual in the code”), so on an X8 both are reduced: for example, a center of 100 and a maximum of 150 °/s — `roll_rc_rate = 10`, `roll_srate = 15`.

**The check from a log.** Full stick in roll and pitch at a safe height: the gyro catches up with the setpoint without a prolonged lag, `motor[]` does not sit at 0 or 100 % for longer than a fraction of a second, the I term does not grow toward the end of the movement, and there is no bounce (the symptom is in the diagnostics). If not — lower the maximum by 20–30 %.

### Throttle: `thr_mid`, `thr_hover`, `thr_expo`, `throttle_limit_*`
The throttle curve is a table of 12 points. In 2025.12 (`initRcProcessing()`) it is built from two quadratic Bezier curves that meet at the point (`thr_mid`, `thr_hover`): the stick position `thr_mid` gives the output `thr_hover` (both in percent, the defaults are 50 and 50). With `thr_expo = 0` the result is two straight segments: (0, 0) → (`thr_mid`, `thr_hover`) → (100, 100); with equal `thr_mid` and `thr_hover` it is a single straight line. With expo both segments bend so that the curve flattens around the hover point: at `thr_expo = 100` the tangent there is horizontal. This gives a softer throttle around hover, and the point is placed where the aircraft actually hovers. Where to start (a course guideline): `thr_expo` = 0 until the point (`thr_mid`, `thr_hover`) matches the hover from the log; then, if the altitude is hard to hold in hover, — `thr_expo` 20–50 in steps of 10. The check — the throttle spread in hover in the log became smaller, while full throttle in a punch-out is still 100 %. In 4.5 there is no `thr_hover` variable, the curve was computed by a different formula (`tmp = 10·i − mid`, output = `10·mid + tmp·(100 − expo + expo·tmp²/y²)/10`), and with `thr_expo = 0` **`thr_mid` had no effect at all**.

`throttle_limit_type` (OFF/SCALE/CLIP) with `throttle_limit_percent` (25…100) works in the mixer. SCALE multiplies the throttle by the percentage. CLIP cuts the throttle off at the top. It is a limiter for a training aircraft and indoor flights, set per rate profile.

### Rate profiles and switching
There are **four** rate profiles (in both 4.5 and 2025.12) (`CONTROL_RATE_PROFILE_COUNT 4`, indices 0–3). A profile contains everything in the table below marked “profile”: the type, the rates, `thr_*`, `throttle_limit_*`, `*_rate_limit`, the name. The ways to switch:
- The CLI `rateprofile` (without an argument it prints the current one) and `rateprofile 2`. The variables in `set`/`get` refer to the **current** profile. `diff rates` prints only the current profile, `diff all` — all four.
- Adjustments, function **12** RATE_PROFILE: `adjrange <i> 0 <aux> 900 2100 12 <aux> 0 0`. The 900…2100 range is divided into three positions of 400 µs (0, 1, 2), and a profile change is accompanied by position+1 beeps. With `rate_6pos_switch = ON` there are six positions, but positions 5–6 point to the non-existent indices 4–5, and the profile does not change. It works in flight.
- Stick commands, only while disarmed and in ACRO: throttle up + pitch up / pitch down / roll right / roll left → profiles 1/2/3/4. In ANGLE/HORIZON the same combinations trim the accelerometer.
- The OSD element `osd_rate_profile_name_pos`; the name is set in `rateprofile_name` (up to 8 characters).
The PID profile is not switched this way: Adjustments has no PID-profile function.

{{lesson:bf-adjustments|All the `adjrange` functions with their CLI numbers, the select mode, the beeps and why an in-flight adjustment is not saved by itself.}}

### Channel endpoints: `rxrange` and why 988–2012

The syntax: `rxrange <0..3> <min> <max>`, where channels 0–3 are roll, pitch, yaw, throttle after `map`, and min and max lie within 750…2250. Without arguments the command prints the current values, and `rxrange reset` sets the default 1000 2000. The scaling: `1000 + (raw − min)·1000/(max − min)`.

With ELRS/CRSF without calibration the stick reaches 2012. `rcCommand` is limited to 500, so the full rate is reached already at 2000 µs, and the last 12 of the 512 µs from center to stop (≈ 2.3 % of half travel) are dead. The same goes for throttle: `constrain(rcData, min_check, 2000)`. At the bottom 988 < `min_check` 1050, so arming is not affected. The solution is `rxrange 0 988 2012` for all four channels. Then full stick travel gives exactly 1000…2000, and the center is 1500 ± 1.

{{lesson:link-edgetx|Why the radio outputs 988 / 1500 / 2012 µs: the Inputs → Mixes → Outputs formulas and the conversion of percent to CRSF units.}}

The input thresholds (the FAQ question “min_check vs min_command”): `min_check` 1050 and `max_check` 1900 are the throttle and stick thresholds for arming and stick commands. Throttle below `min_check` is treated as zero. `mid_rc` 1500 is the stick center. `rx_min_usec`/`rx_max_usec` 885/2115 is the signal validity window. `min_command` and `motor_idle` (before 2025.12 — `dshot_idle_value`) are motor outputs and have nothing to do with RC. `deadband`/`yaw_deadband` (0…32/0…100) cut out a zone at the center. They are needed only for worn gimbals, because they narrow the stick travel.

### RC smoothing: a PT3 at the measured receiver rate
Without smoothing the setpoint changes in steps once per packet: at 50 Hz — once every 20 ms. The D term and feedforward turn every step into a spike on the motors. Hence the “notchy” feel, the heat and the shake at the link rate. That is why `rc_smoothing = ON` by default. It is a PT3 filter at the PID loop rate for the setpoint (roll/pitch/yaw) and for the throttle; in 2025.12 feedforward is filtered with the same cutoff as the setpoint (in 4.5 FF had its own cutoff).

The automatic mode applies to each cutoff frequency whose `*_cutoff = 0` (the default). In 2025.12 (`updateRcRefreshRate()`, `shouldUpdateSmoothing()`, `rcSmoothingSetFilterCutoffs()` in `fc/rc.c`):
- the packet interval is limited to the window 800…65,500 µs; the rate is smoothed by a first-order filter with k = 0.1;
- an outlier is a sample that differs from the smoothed rate by more than 20 % (a lost packet, a telemetry slot): it does not go into the estimate. Three outliers in a row of the same sign are treated as a change of packet rate, and the estimate takes the new value at once;
- the cutoffs are recalculated on every 3rd accepted sample: `cutoff = max(15, f_rx · 1.5 / (1 + auto_factor/10))` Hz, and the result is stored as an integer (the fractional part is dropped). With `rc_smoothing_auto_factor = 30` this is 0.375 · f_rx;
- on signal loss the last estimate is held.

In 4.5 the details differ (a window of 950…65,500 µs, a start after 1 s, a different outlier criterion), and the cutoff formula is the same — it is covered below, in the subsection on 4.5.3.

A manual cutoff (`rc_smoothing_setpoint_cutoff`, `rc_smoothing_throttle_cutoff`, Hz; 4.5 also had `rc_smoothing_feedforward_cutoff`, removed in 2025.12) fixes the frequency. It is set for unstable links: Crossfire without lock, jumping between 50 and 150 Hz, is kept at 20–30 Hz per the 4.3 notes. Per the same 4.3 notes: factor 30 is the norm, 20 — for racing at 250/500 Hz, 90–120 — for cinematic filming. Turning `rc_smoothing` off is not recommended.

Reading `rc_smoothing_info` (the line format is from `cliRcSmoothing()` 2025.12.5, the values for ELRS 500 Hz are calculated; in 4.5 there are five lines — the first is `# RC Smoothing Type: FILTER`, the setpoint and FF cutoffs are on separate lines, and the unit is written `hz`):
```
# Detected Rx frequency: 500Hz
# RC Smoothing: ON
# Active setpoint and FF cutoff: 187Hz (auto)
# Active throttle cutoff: 187Hz (auto)
```
`NO SIGNAL` means that the interval was not measured (no link, or USB without a receiver). A rate far below the packet rate indicates lost packets or a wrongly chosen ELRS mode. `(manual)` means that the cutoff was set by hand. The same numbers are written to the Blackbox header (`rc_smoothing_active_cutoffs_ff_sp_thr`; in 2025.12 there are two values — setpoint and throttle), and `debug_mode = RC_SMOOTHING_RATE` logs the interval and the rate estimate.

### How 4.5.3 measures the receiver rate
1. **The frame timestamp.** The protocol driver records the moment each RC frame is received (`lastRcFrameTimeUs`, for CRSF — in `rx/crsf.c:395`). `rxGetFrameDelta()` (`rx/rx.c:1025`) returns the difference between two frames. `updateRcRefreshRate()` (`fc/rc.c:264`) limits it to the window 950…65,500 µs (`RX_INTERVAL_MIN_US`/`MAX_US`) and marks an interval outside the window as invalid. This is also where `currentRxRateHz` = 10⁶/interval comes from, which is used to compute the setpoint speed for FF.
2. **The guard time.** For the first 1000 ms after power-up no samples are taken (`rc.c:412`), so that the PID loop has time to settle.
3. **Sample selection.** A sample is accepted if the interval changed by less than 7/8 of the previous one (`rc.c:418`). One ELRS telemetry slot doubles the interval (2000 → 4000 µs, a change of 2000 > 1750) — such a sample is rejected. The return to normal (4000 → 2000, a change of 2000 < 3500) is accepted.
4. **Smoothing and recalculation.** The accepted rate goes into a first-order filter with k = 0.1 (`rc.c:424`). The cutoffs are computed on the first accepted sample and then on every 4th (a counter 3 → 0, `rc.c:436`). There are three cutoffs: setpoint and FF — from `rc_smoothing_auto_factor`, throttle — from `_throttle`; the formula is the same max(15, ⌊f·1.5/(1 + factor/10)⌋).
5. **Signal loss.** Only the counter is reset (`rc.c:444`); the rate estimate itself remains. The very first good sample after recovery recalculates the cutoffs at once.

The lab (step 4, section 6) runs this algorithm with a telemetry slot in every 8th packet. At 500 Hz the cutoff reaches 187 ± 1 Hz 1.13 s after power-up, at 50 Hz — 18 ± 1 Hz only after ≈ 1.7 s (1.68 s). The first sample after the guard time is always rejected: `previousRxIntervalUs` is 0 until then. The first cutoff at 50 Hz is 15 Hz: the filter starts from zero, and the first estimate is 0.1·50 = 5 Hz.

### ELRS 50 Hz versus 500 Hz
The packet rate changes both the smoothing and FF. The numbers are from the labs of this module (4.5.3, factor 30, the stick moves at 1500 units of `rcCommand` per second, that is, half travel in 0.33 s):

| Quantity | 50 Hz | 500 Hz |
|---|---|---|
| Packet period | 20 ms | 2 ms |
| Auto cutoff of the setpoint and FF PT3 | 18 Hz | 187 Hz |
| Time to 50 % of a stick step | 22 ms | 2.1 ms |
| `rcCommand` step per packet | 30 | 3 |
| FF jitter multiplier (`jitter_factor` 7, 4.5.3) | 1.00 | 0.67 |
| FF smoothing τ, `smooth_factor` 25 (4.5.3) | 6.7 ms | 0.67 ms |
| FF smoothing τ, `smooth_factor` 65 (2025.12) | 7.4 ms | 7.4 ms |

Conclusions. At 50 Hz the PT3 itself cuts FF with its 18 Hz cutoff, and the jitter multiplier on an ordinary movement is 1.00: by the lab's calculation the jitter filter and smooth change almost nothing here. The 4.3 Tuning Notes say the same: at 50 Hz the steps are large and there is almost no jitter problem. At 500 Hz the 187 Hz cutoff lets gimbal noise through, and the step per packet is small: the 4.5.3 jitter filter removes a third of FF on an ordinary movement. A smoothing of 25 “per packet” at 500 Hz gives only 0.67 ms. The 4.3 Tuning Notes ask for smooth 65–70 at 500 Hz (the “per packet” scale, τ ≈ 3.7–4.7 ms) and 2_POINT. In 2025.12 65 and 2_POINT became the defaults, but smooth is normalized to 250 Hz (a comment in `pid_init.c`): τ = 7.4 ms on any link, so at 500 Hz the smoothing is twice as strong as in the 4.3 advice. The connection between the 4.3 advice and the new default is the author's inference; it is not in the code.

{{lesson:link-elrs|Packet rate, telemetry and the D250/D500/F1000 modes — where the packet rate that Betaflight measures comes from.}}

### Feedforward: the setpoint derivative with jitter protection (2025.12)
`calculateFeedforward()` runs on every new RC packet. In 2025.12:
- speed = Δsetpoint · f_rx (°/s²); on a duplicate packet the first iteration extrapolates the previous speed, and the following ones zero it. Extrapolation is off for CRSF/ELRS over UART (`feedforwardInterpolate` is false with `serialrx_provider = CRSF`);
- `feedforward_jitter_factor` 7 (0…20): multiplier = min(1, ((Δ + Δprev)/2 + 1) / (1 + 7)), where Δ is the change of `rcCommand` per packet. With a step of 7 units (0.7 % of full travel) or more FF passes in full, and with a still stick 1/8 remains;
- `feedforward_smooth_factor` 65 (0…95): a PT1 on the setpoint speed with the time constant τ = 4 ms · s/(1 − s), s = 65/100, that is, 7.4 ms. The number is normalized to 250 Hz: at any packet rate the smoothing in time is the same (in 4.5 it was a “per packet” coefficient, 25 by default);
- `feedforward_boost` 15 (0…50): an addition from the setpoint acceleration (the second derivative, smoothed by the same PT1) that compensates for motor spin-up; roll and pitch only;
- `feedforward_max_rate_limit` 90 (0…200): on roll/pitch, FF of the same sign as the setpoint is limited to (max_rate − |setpoint|)·90 and goes to zero at the stop. It removes the overshoot at the end of a flip, when the stick has reached the stop;
- yaw: instead of boost and the limit — a hold: `feedforward_yaw_hold_gain` 15 (0…100) · (setpoint − its PT1 with the time constant `feedforward_yaw_hold_time` 100 ms, 10…250; with time < 100 the gain automatically grows by 150/(time + 50)). 4.5 does not have these variables;
- `feedforward_transition` 0 (0…100): attenuates FF linearly to zero while |x| is below transition/100;
- `feedforward_averaging` 2_POINT (OFF / 2_POINT / 3_POINT / 4_POINT): a moving average over packets, as the last step (the 4.5 default is OFF);
- the result passes through the PT3 with the setpoint cutoff and is multiplied by `Kf = 0.013754 · f/100`, where `f_roll`/`f_pitch`/`f_yaw` = 120/125/120.

ELRS packet rate and FF. The intervals from `common.cpp` (ELRS 4.1.0, the same in 3.x): LoRa 2.4 GHz 50/150/250/500 Hz — 20,000/6666/4000/2000 µs, F500 — 2000, F1000 — 1000. D250/D500 send every packet 4×/2× at a 1000 µs interval, that is, they give 250/500 Hz of new data. The telemetry slot (by default from 1:16 at 50 Hz to 1:128 at 500 Hz/F1000, configurable down to 1:2) periodically takes the place of an RC packet, and the FC sees a double interval. The higher the rate, the smaller the `rcCommand` step per packet: the jitter filter attenuates FF more on slow movements (the lab, step 3), and gimbal noise gets into FF more. The 4.3 Tuning Notes (the smooth numbers there are in the “per packet” scale of 4.3–4.5; in 2025.12 the scale is normalized to 250 Hz): for 500 Hz `feedforward_smooth_factor` 65–70 and `feedforward_averaging = 2_POINT`, for 250 Hz — 2_POINT and smooth 35–40 (40–50 elsewhere in the document), for Crossfire 150 — 3_POINT. There is no official number for F1000; the 500 Hz settings as a start are an extrapolation — check with Blackbox. For motors twitching with still sticks the same notes advise jitter 10–12 and a test flight with FF = 0.

### Feedforward in 4.5.3: the pipeline step by step
`processRcCommand()` (`fc/rc.c:628`) on every new packet computes x = `rcCommand`/(500 − deadband), `applyRates`, the `*_rate_limit` limit, and calls `calculateFeedforward()` for each of the three axes (`rc.c:499–626`). The coefficients are prepared by `pid_init.c:414–424`. The order of the steps is as in the code:

1. **Setpoint speed** (`rc.c:522`, `551`): v = (sp − sp_prev)·f_rx, °/s². Here f_rx = 10⁶/the interval of the current packet. This is FF itself: “how fast the pilot is moving the stick”.
2. **Duplicates** (`rc.c:545–571`). If `rcCommand` has not changed, the first such packet gets the previous speed plus the previous acceleration (the acceleration — only if |sp| < 0.95·max), and the second and later ones get zero. A packet with movement after a duplicate computes the speed over two intervals, and its acceleration is zeroed. It cures the sawtooth from repeated packets, when the radio updates the channels less often than the link sends. The lab model: the channels change once per 4 ms at 500 Hz, that is, every second packet is a repeat. This happens if the mixer is not synchronized with the module: 4 ms is only the default EdgeTX mixer period (`mixer_scheduler.h`). With ELRS/CRSF, EdgeTX adjusts the mixer period to the packet rate of the module (`crossfireSetupMixerScheduler`, `pulses/crossfire.cpp`), and there are almost no repeats. In the lab, without this logic FF jumps +9000/−6300 °/s², and with it the zigzag is 1.6 %. *2025.12: for `serialrx_provider = CRSF` extrapolation is off, and the threshold is 0.90·max.*
3. **`feedforward_smooth_factor`** 25 (0…95): a PT1 on the speed, k = 1 − 25/100 = 0.75 per packet (`pid_init.c:418`, `rc.c:573`). The time constant τ = T·s/(1 − s) = T/3: 1.33 ms at 250 Hz, 0.67 ms at 500 Hz. It cures FF steps from an uneven packet rate and channel quantization. *2025.12: τ = 4 ms·s/(1 − s) on any link, 65 by default.*
4. **`feedforward_boost`** 15 (0…50): acceleration = Δv·f_rx·0.01, smoothed with the same k, × 0.1·boost × the jitter multiplier (`rc.c:582`, `pid_init.c:422`). In total boost/1000·Δv·f_rx. It compensates for the motor spin-up delay at the start of a sharp movement. In 4.5.3 it works on all three axes. In the lab, on a 40 ms stick snap boost gives 11,000 of the peak 29,400 °/s². *2025.12: roll/pitch only; on yaw `feedforward_yaw_hold_*` instead.*
5. **`feedforward_transition`** 0 (0…100): at |x| < tr/100 FF is multiplied by |x|·100/tr (`rc.c:597`). Transition 30 at x = 0.15 gives ×0.5. It removes the sharpness near the center for smooth filming. *2025.12: the same.*
6. **`feedforward_averaging`** OFF (OFF, 2_POINT, 3_POINT, 4_POINT): a moving average of FF over the last 2…4 packets (`rc.c:603`, `common/filter.c:327`). It damps the zigzag from alternating packets at the cost of a delay of ≈ (N − 1)/2 packet periods for a window of N. *2025.12: 2_POINT by default, executed last.*
7. **`feedforward_jitter_factor`** 7 (0…20): the multiplier is computed at the start (`rc.c:535`) and applied here (`rc.c:607`). If the step per packet Δ = |Δ`rcCommand`| < j, multiplier = 1 − m², where m = max(0, 1 − (Δ + Δprev)/(2j)); at Δ ≥ j the multiplier is 1. Boost is multiplied by it twice, in step 4 and here. It suppresses FF from finger tremor and gimbal noise with a still stick: at Δ = 0 for two packets in a row FF = 0. In the lab at 1500 units/s the multiplier is 1.00 at 150 Hz, 0.67 at 500 Hz and 0.38 at 1000 Hz. *2025.12: the linear min(1, ((Δ + Δprev)/2 + 1)/(1 + j)), 1/8 with a still stick, not 0.*
8. **`feedforward_max_rate_limit`** 90 (0…200), roll/pitch only: if FF points the same way as the setpoint, |FF| ≤ (max_rate − |sp|)·90 (`rc.c:611`). The value enters the formula as is, without division by 100. It cures the overshoot at the end of a flip: the stick has reached the stop, but FF keeps pushing. In the lab, without the limit, on the packet where the setpoint reached 670 °/s FF = 40,500 °/s² (F ≈ 668, more than the `pidsum_limit` of 500), and on the next packet another 29,250 (F ≈ 483); with a limit of 90 — zero. *2025.12: the same formula, but before transition and averaging.*
9. **Smoothing and gain.** `feedforwardRaw` passes through the PT3 with the FF cutoff in every PID loop (`rc.c:480`). Then `pid.c:1014` takes it as `pidSetpointDelta`, and `pid.c:1081` gives F = Kf·FF, where Kf = 0.013754·F/100 (`pid_init.c:277`, `pid.h:50`). The F defaults (`pid.h:62–64`): **`f_roll` 120, `f_pitch` 125, `f_yaw` 120** (0…1000, `F_GAIN_MAX`), Kf = 0.0165 for 120. In slider mode F is recalculated from the default × master × `simplified_feedforward_gain`/100, and for pitch also × `simplified_pitch_pi_gain`/100 (`config/simplified_tuning.c:60`). On axes under Angle and during launch control FF is zeroed (`pid.c:1000–1015`, `1080`). *2025.12: the F defaults are the same 120/125/120.*

{{diagram:flow-bf-ff-pipeline|Every filter in the pipeline cures its own problem: extrapolation and the PT1 — steps from packets, jitter — the tremor of a still stick (in any position), max_rate_limit — the overshoot near the maximum rate. The PT3 and the multiplication by Kf already run at the PID loop rate.}}

### What was different in 4.5
- `rc_smoothing_feedforward_cutoff` existed: FF had its own cutoff, and `rc_smoothing_info` printed “Active FF cutoff” on a separate line.
- The RX rate estimate: an outlier is an interval change of more than 7/8 of the previous one, the cutoffs are recalculated on every 4th sample, and on signal loss only the counter is reset.
- The FF defaults: `feedforward_averaging = OFF`, `feedforward_smooth_factor = 25` (a per-packet coefficient: 1 − 25/100 = 0.75); the jitter multiplier was computed as 1 − (1 − (Δ+Δprev)/(2·7))² and only at Δ < 7.
- Boost acted on yaw too; duplicate extrapolation worked for all protocols, including CRSF; the order of the steps: boost → transition → averaging → jitter → limit.
- `feedforward_yaw_hold_gain` and `feedforward_yaw_hold_time` did not exist.
- `thr_hover` did not exist: the throttle curve was the table `tmp = 10·i − mid`, output = `10·mid + tmp·(100 − expo + expo·tmp²/y²)/10`; with `thr_expo = 0` the result was a straight line, and `thr_mid` had no effect at all.
- There were `expresslrs_rate_index`/`expresslrs_switch_mode` (SPI ELRS), removed in 2025.12.
- The rate formulas, the default ACTUAL 7/67/0 and the four profiles are the same in 4.5 and 2025.12.

### Reference table (2025.12; the 4.5.3 differences are in the cells)
| Variable / command | Default | Range | Meaning |
|---|---|---|---|
| `rates_type` | ACTUAL | BETAFLIGHT, RACEFLIGHT, KISS, ACTUAL, QUICK | the curve model (profile) |
| `roll_rc_rate`, `pitch_rc_rate`, `yaw_rc_rate` | 7 | 1…255 (the type limit) | Actual: center ×10 °/s; Betaflight: RC rate ×0.01; Quick: center ×2 °/s |
| `roll_srate`, `pitch_srate`, `yaw_srate` | 67 | 0…255 (the type limit) | Actual/Quick: maximum ×10 °/s; Betaflight: super rate ×0.01 |
| `roll_expo`, `pitch_expo`, `yaw_expo` | 0 | 0…100 | expo ×0.01 |
| `quickrates_rc_expo` | OFF | OFF/ON | Quick: expo on the stick |
| `roll_rate_limit`, `pitch_rate_limit`, `yaw_rate_limit` | 1998 | 200…1998 | the setpoint limit, °/s |
| `thr_mid` / `thr_hover` / `thr_expo` | 50 / 50 / 0 | 0…100 | the throttle curve through the point (mid, hover); `thr_hover` — from 2025.12, in 4.5 mid has no effect without expo |
| `throttle_limit_type` / `throttle_limit_percent` | OFF / 100 | OFF, SCALE, CLIP / 25…100 | the throttle limit |
| `rateprofile_name` | empty | 1…8 characters | the name for the OSD |
| `rateprofile` | 0 | 0…3 | CLI: select the rate profile |
| `rate_6pos_switch` | OFF | OFF/ON | 6 positions for function 12 |
| `rxrange <ch> <min> <max>` | 1000 2000 | 750…2250, ch 0…3 | CLI: calibration of the channel endpoints |
| `mid_rc` | 1500 | 1200…1700 | the stick center |
| `min_check` / `max_check` | 1050 / 1900 | 750…2250 | the thresholds for arming and stick commands |
| `rx_min_usec` / `rx_max_usec` | 885 / 2115 | 750…2250 | the channel validity window |
| `deadband` / `yaw_deadband` | 0 / 0 | 0…32 / 0…100 | the dead zone at the center, µs |
| `airmode_start_throttle_percent` | 25 | 0…100 | air mode activates after this throttle |
| `rc_smoothing` | ON | OFF/ON | PT3 smoothing of RC |
| `rc_smoothing_auto_factor` / `_auto_factor_throttle` | 30 / 30 | 0…250 | higher → a lower cutoff, smoother, slower |
| `rc_smoothing_setpoint_cutoff` / `_throttle_cutoff` | 0 / 0 | 0…255 Hz | 0 = auto; the setpoint cutoff applies to FF too (4.5 had a separate `rc_smoothing_feedforward_cutoff`) |
| `rc_smoothing_feedforward_cutoff` | 0 | 0…255 Hz | 4.5 only: the PT3 cutoff for FF, 0 = auto from `rc_smoothing_auto_factor`; removed in 2025.12 |
| `rc_smoothing_debug_axis` | ROLL | ROLL, PITCH, YAW, THROTTLE | written only to the Blackbox header; it does not affect the `debug_mode = RC_SMOOTHING` fields in 4.5.3 and 2025.12 |
| `rc_smoothing_info` | — | — | CLI: the RX rate and the active cutoffs |
| `feedforward_transition` | 0 | 0…100 | FF × \|x\|·100/tr at \|x\| < tr/100 |
| `feedforward_averaging` | 2_POINT | OFF, 2_POINT, 3_POINT, 4_POINT | FF averaging (OFF by default in 4.5) |
| `feedforward_smooth_factor` | 65 | 0…95 | FF smoothing, a PT1 with τ = 4 ms · s/(1 − s) (25 by default in 4.5, a per-packet coefficient) |
| `feedforward_jitter_factor` | 7 | 0…20 | the threshold of the `rcCommand` step per packet; 4.5.3: 1 − (1 − ΣΔ/2j)² at Δ < j, 2025.12: linear |
| `feedforward_boost` | 15 | 0…50 | the contribution of the setpoint acceleration, boost/1000·Δv·f_rx; roll/pitch (4.5.3 — all axes) |
| `feedforward_max_rate_limit` | 90 | 0…200 | roll/pitch: \|FF\| ≤ (max_rate − \|sp\|)·value |
| `feedforward_yaw_hold_gain` / `feedforward_yaw_hold_time` | 15 / 100 | 0…100 / 10…250 ms | the yaw FF hold (from 2025.12) |
| `f_roll` / `f_pitch` / `f_yaw` | 120 / 125 / 120 | 0…1000 | the FF gain (PID profile), Kf = 0.013754·F/100 |
| `simplified_feedforward_gain` | 100 | 0…200 | the slider: F = default × master × gain/100 |
| `angle_feedforward` / `angle_feedforward_smoothing_ms` | 50 / 80 | 0…200 / 10…250 ms | FF in Angle mode (a separate path, PT3) |
| `debug_mode` | NONE | FEEDFORWARD, FEEDFORWARD_LIMIT, RC_SMOOTHING, RC_SMOOTHING_RATE, RX_TIMING, RC_INTERPOLATION … | what is written to the Blackbox debug[] fields |

### Place in the system

- **Receives:** the channels in microseconds and the packet rate from the receiver (`link-elrs`, `link-protocols`); the channel validity window, shared with failsafe (`bf-failsafe`); the rate profile number from Adjustments (`bf-adjustments`).
- **Provides:** the setpoint — the desired angular rate — and feedforward to the controller (`bf-pid-reg-in-bf`); the curve shape — to Angle mode (`bf-features-tour`); the maximum yaw rate — to the yaw spin recovery threshold in AUTO mode (`bf-arming-safety`).
- **If you get it wrong here:** you turned `rc_smoothing` off → the setpoint steps pass into D and feedforward, and the motors get spikes at the link rate and heat up; in the spectrum it looks like noise that people then try to cure with filters (`bf-filters`, `bf-blackbox`). You changed `rates_type` without converting the numbers → 7/67/0 in the Betaflight type gives 14 °/s at the center: the aircraft is sluggish, as with a low P from `bf-pid`.

## practice
### Step 1. A port of the formulas and a rate converter
The rate functions are ported from `fc/rc.c` 4.5 line by line; the formula did not change in 2025.12 (the diff of the `apply*Rates()` functions between 4.5.3 and 2025.12.5 is empty). The converter keeps the center (the slope at zero) and the maximum of the target Actual profile. It finds the remaining shape parameter (expo for Betaflight and Quick) by a search over 0…100, minimizing the RMS difference over 101 stick points. The values are rounded to integers, as the firmware stores them. The full script is 189 lines; the core is below:

```python
def bf_rates(x, rc_rate, srate, expo):            # applyBetaflightRates
    a = abs(x)
    if expo:
        e = expo / 100
        x = x * a**3 * e + x * (1 - e)
    r = rc_rate / 100
    if r > 2.0:
        r += 14.54 * (r - 2.0)                    # RC_RATE_INCREMENTAL
    rate = 200.0 * r * x
    if srate:
        rate *= 1.0 / min(max(1.0 - a * srate / 100, 0.01), 1.0)
    return rate

def actual_rates(x, rc_rate, srate, expo):        # applyActualRates
    a = abs(x)
    e = expo / 100
    ex = a * (x**5 * e + x * (1 - e))
    centre = rc_rate * 10.0
    stick = max(0.0, srate * 10.0 - centre)
    return x * centre + stick * ex

def quick_rates(x, rc_rate, srate, expo, rc_expo=False):   # applyQuickRates
    a = abs(x)
    rcr = rc_rate * 2
    max_dps = max(srate * 10, rcr)
    e = expo / 100
    sfc = (max_dps / rcr - 1) / (max_dps / rcr)
    if rc_expo:
        curve = x**3 * e + x * (1 - e)
        sf = 1 / min(max(1 - a * sfc, 0.01), 1)
        return max(-1998, min(1998, curve * rcr * sf))
    curve = a**3 * e + a * (1 - e)
    sf = 1 / min(max(1 - curve * sfc, 0.01), 1)
    return max(-1998, min(1998, x * rcr * sf))
```

The output of `python3 rates_lab.py`:
```
== default 4.5 profile: ACTUAL 7/67/0 ==
centre 71 deg/s, max 670 deg/s, 50% stick 185 deg/s

== converter, target ACTUAL rc_rate=20 srate=67 expo=54 (centre 200, max 670 deg/s) ==
BETAFLIGHT rc_rate=101 srate= 70 expo=  1  RMS   2.5 deg/s
QUICK      rc_rate=100 srate= 67 expo=  0  RMS   2.5 deg/s
stick  ACTUAL  BETAFL   QUICK
 0.10      22      22      22
 0.25      64      61      61
 0.50     158     154     154
 0.75     317     317     317
 0.90     490     490     488
 1.00     670     673     670
centre   200     200     200
max |BF-Actual| = 4 deg/s at stick 0.42
max |Quick-Actual| = 4 deg/s at stick 0.42

== converter, target ACTUAL rc_rate=7 srate=67 expo=0 (centre 70, max 670 deg/s) ==
BETAFLIGHT rc_rate=208 srate=  3 expo= 89  RMS  95.4 deg/s
QUICK      rc_rate= 35 srate= 67 expo=  0  RMS 143.7 deg/s
stick  ACTUAL  BETAFL   QUICK
 0.10      13       7       8
 0.25      55      20      23
 0.50     185      73      63
 0.75     390     242     160
 0.90     549     455     325
 1.00     670     669     670
centre    71      71      70
max |BF-Actual| = 151 deg/s at stick 0.71
max |Quick-Actual| = 245 deg/s at stick 0.83
```
The analysis. Actual 200/670/0.54 converts to Betaflight 1.01/0.70/0.01 and Quick 100/67/0 with a difference of up to 4 °/s — the pilot will not feel it. The default 70/670/0 does not convert like that: an Actual curve with low expo is close to a parabola, while super rate gives a hyperbola that lies low and shoots up near the end. Matching the center and the maximum is not enough, which is why the converter prints the RMS and the maximum error. The slope at the center matched the formula from the table: 200·1.01·0.99 = 200.

### Step 2. PT3 smoothing of a stick step
The calculation was done with the 4.5 code; the cutoff formula and `pt3FilterGain` did not change in 2025.12, so the numbers of this step are valid for 2025.12 too.

The stick goes sharply from center to stop (the setpoint 0 → 670 °/s) at the moment t = 0. The first packet with the new value arrives after T/2, where T is the packet period. The PID loop is 8 kHz, a PT3 with `pt3FilterGain` (cutoff × 1.961459177, as in `common/filter.c`), the automatic cutoff at factor 30. “Ripple” is the maximum of d(setpoint)/dt during a smooth 100 ms stick movement to the stop, divided by the ideal slope. It is a measure of the stepping that D and FF will see.

```
== RC smoothing (rc_smoothing_auto_factor = 30), step 0 -> 670 deg/s, PID loop 8 kHz ==
link        rx_Hz  cutoff_Hz  t50_ms  t90_ms  | OFF: t50  ripple ON  ripple OFF
CRSF 50        50        18    22.0    34.1  |     10.0      1.36      161.0
ELRS 150      150        56     7.2    11.2  |      3.4      1.37       54.0
ELRS 250      250        93     4.2     6.8  |      2.0      1.36       33.0
ELRS 500      500       187     2.1     3.5  |      1.0      1.33       17.0
ELRS F1000   1000       375     1.0     1.8  |      0.5      1.29        9.0

auto_factor sweep at ELRS 250 Hz:
factor   0: cutoff 375 Hz, t50   2.5 ms, t90   3.3 ms, ripple 4.13
factor  10: cutoff 187 Hz, t50   3.1 ms, t90   4.5 ms, ripple 2.28
factor  30: cutoff  93 Hz, t50   4.2 ms, t90   6.8 ms, ripple 1.36
factor  60: cutoff  53 Hz, t50   6.1 ms, t90  10.2 ms, ripple 1.10
factor  90: cutoff  37 Hz, t50   7.9 ms, t90  13.9 ms, ripple 1.04
factor 120: cutoff  28 Hz, t50   9.8 ms, t90  17.6 ms, ripple 1.02
```
The auto mode keeps the stepping constant (≈ 1.3–1.4 at factor 30) and makes the delay proportional to the packet period: going from 50 to 500 Hz cuts the time to 50 % from 22 to 2.1 ms. Without smoothing the delay is half as long, but the setpoint derivative is 9–161 times the norm — impulses into D and FF. Factor 120 at 250 Hz gives 9.8 ms: that is the price of “cinematic” smoothness.

{{diagram:chart-bf-rc-smoothing-step|Auto smoothing with factor 30 (a cutoff of 0.375·f_rx) leaves the delay proportional to the packet period: to 50 % of the step in 22 ms at 50 Hz, 7.2 ms at 150 Hz, 2.1 ms at 500 Hz and 1.0 ms at F1000. An unsmoothed step at 50 Hz arrives earlier, but all at once.}}

### Step 3. The jitter filter, throttle and throttle limit
The output was captured with the 4.5 formulas; in 2025.12 the jitter multiplier is linear (min(1, ((Δ+Δprev)/2 + 1)/(1 + jitter))), and the throttle curve is built through the point (`thr_mid`, `thr_hover`) — the numbers of this step will be different for 2025.12.

```
== feedforward_jitter_factor = 7: same slow stick move (half travel in 0.5 s) ==
   50 Hz: rcCommand delta  20.0/packet -> FF x 1.00
  150 Hz: rcCommand delta   6.7/packet -> FF x 1.00
  250 Hz: rcCommand delta   4.0/packet -> FF x 0.82
  500 Hz: rcCommand delta   2.0/packet -> FF x 0.49
 1000 Hz: rcCommand delta   1.0/packet -> FF x 0.27

== throttle curve: rcCommand[THROTTLE] (us) vs stick % ==
stick   mid50/expo0  mid50/expo50  mid40/expo50
  10%         1100          1172          1166
  30%         1300          1384          1347
  40%         1400          1448          1400
  50%         1500          1500          1451
  60%         1600          1552          1510
  90%         1900          1828          1820

throttle_limit_percent = 80:  stick 50% / 90% / 100%
OFF  : 50% / 90% / 100%
SCALE: 40% / 72% / 80%
CLIP : 50% / 80% / 80%
```
The same slow movement (half travel in 0.5 s) leaves 27 % of FF on F1000 and 100 % at 50 Hz. A high rate with the default jitter 7 makes smooth movements “softer”, and that is not a tuning mistake. The throttle curve confirms the theory for 4.5: `thr_mid` 40 without expo would give a straight line, while with expo 50 the 40 % point became fixed (1400), and the throttle around it flattened.

### Step 4. Feedforward 4.5.3 in Python and `debug_mode = FEEDFORWARD`
The script `ff_lab.py` (228 lines) ports `applyActualRates` and `calculateFeedforward()` from `fc/rc.c` 4.5.3 line by line, with the coefficients from `pid_init.c:414–424`. The simplifications: one axis (roll); `rcCommand` is a smooth ramp (real CRSF is quantized in steps of ≈ 0.62 µs); the RC smoothing PT3 at the output is not modeled. The script prints `feedforwardRaw` — exactly what debug FEEDFORWARD[3] records (×0.1). The core (abridged: without the debug lines and the extrapolation switch):

```python
def step(self, rc_command, setpoint, deflection_abs, interval_us):
    interval_us = min(max(interval_us, 950), 65500)        # RX_INTERVAL_MIN/MAX_US
    rx_interval, rx_rate = interval_us * 1e-6, 1e6 / interval_us
    dabs = abs(rc_command - self.prev_rc); self.prev_rc = rc_command
    speed = setpoint - self.prev_sp; self.prev_sp = setpoint
    zero_acc, jitter_att = 1.0, 1.0
    if self.jit and dabs < self.jit:                        # rc.c:535
        j = max(1.0 - (dabs + self.prev_dabs) / (2 * self.jit), 0.0)
        jitter_att = 1.0 - j * j
    self.prev_dabs = dabs
    if dabs:                                                # movement
        if self.prev_dup:
            rx_rate = 1.0 / (rx_interval + self.prev_interval); zero_acc = 0.0
        speed *= rx_rate; self.prev_dup = False
    else:                                                   # duplicate packet
        if not self.prev_dup:
            speed = self.prev_speed + (self.prev_acc if abs(setpoint) < 0.95 * self.max_rate else 0.0)
        else:
            speed = 0.0; self.prev_speed = 0.0
        zero_acc = 0.0; self.prev_dup = True
    self.prev_interval = rx_interval
    speed = self.prev_speed + self.k * (speed - self.prev_speed)          # k = 1 - smooth/100
    acc = (speed - self.prev_speed) * rx_rate * 0.01; self.prev_speed = speed
    acc = self.prev_acc + self.k * (acc - self.prev_acc); self.prev_acc = acc * zero_acc
    ff = speed + acc * self.boost * jitter_att * zero_acc                 # boost = 0.1 * feedforward_boost
    if self.tr and deflection_abs < self.tr: ff *= deflection_abs * self.tr_inv
    if self.win > 1: ff = self._avg(ff)                                   # feedforward_averaging
    ff *= jitter_att
    if self.mrl and ff * setpoint > 0.0:                                  # max rate limit, roll/pitch
        limit = (self.max_rate - abs(setpoint)) * self.mrl
        ff = max(-limit, min(limit, ff)) if limit > 0.0 else 0.0
    return ff
```

The output of `python3 ff_lab.py`. Sections 1 (the Actual table) and 5 (the smoothing τ) are omitted, and their numbers are given in the theory; in section 4 the lines for 52–60 ms, where all FF values are 0, are omitted:
```
== 2. jitter attenuator (4.5.3), stick ramp 1500 rcCommand/s, read at x = 0.5 ==
Kf = 0.013754 * f_roll/100 = 0.01650 (f_roll = 120)
 rate_Hz  delta/packet  jitter_att  speed_deg/s2  FF_raw  F_term
      50          30.0       1.000          1758    1920    31.7
     150          10.0       1.000          1950    2112    34.9
     250           6.0       0.980          1988    2103    34.7
     500           3.0       0.673          1985    1410    23.3
    1000           1.5       0.383          2005     791    13.1
jitter factor sweep at 500 Hz (delta 3.0/packet):
  feedforward_jitter_factor  0: jitter_att 1.000, FF_raw  2147
  feedforward_jitter_factor  5: jitter_att 0.840, FF_raw  1782
  feedforward_jitter_factor  7: jitter_att 0.673, FF_raw  1410
  feedforward_jitter_factor 10: jitter_att 0.510, FF_raw  1054
  feedforward_jitter_factor 12: jitter_att 0.438, FF_raw   899
  feedforward_jitter_factor 20: jitter_att 0.278, FF_raw   563

== 3. duplicates: ELRS 500 Hz, MODEL ASSUMPTION: channels change every 4 ms (mixer not synced), jitter 0 ==
  zigzag = mean |FF_i - (FF_i-1 + FF_i+1)/2| / mean FF, packets with stick 0.30...0.36
  4.5.3 interpolation, averaging OFF  : FF_raw  1254  1254  1297  1297  1340  1340 | zigzag 0.016
  4.5.3 interpolation, averaging 2_POINT: FF_raw  1232  1254  1276  1297  1319  1340 | zigzag 0.000
  no interpolation,   averaging OFF  : FF_raw  9025 -6286  9327 -6502  9629 -6718 | zigzag 11.257
  no interpolation,   averaging 2_POINT: FF_raw  1477  1369  1520  1412  1564  1456 | zigzag 0.085

== 4. fast flick 0 -> full stick in 40 ms, ELRS 250 Hz, Actual 70/670/0 ==
  max_rate_limit 90 vs 0, boost 15 vs 0; FF_raw in deg/s^2, debug = FEEDFORWARD[0..3], FEEDFORWARD_LIMIT[0..3]
  t_ms  setpoint  FF(lim90,b15)  FF(lim0)  FF(boost0)  boost_part  debug FEEDFORWARD       debug FF_LIMIT
     0         0              0         0           0           0  [0, 0, 0, 0]            [0, 670, 0, 0]
     4        13           1219      1219        1219           0  [130, 122, 122, 122]    [100, 670, 13, 1219]
     8        38          15605     15605        4992       10613  [380, 499, 1560, 1560]  [100, 670, 38, 15605]
    12        75          19820     19820        8186       11635  [750, 819, 1982, 1982]  [100, 670, 75, 19820]
    16       124          22716     22716       11234       11482  [1240, 1123, 2272, 2272]  [100, 670, 124, 22716]
    20       185          25588     25588       14246       11342  [1850, 1425, 2559, 2559]  [100, 670, 185, 25588]
    24       258          28530     28530       17249       11281  [2580, 1725, 2853, 2853]  [100, 670, 258, 28530]
    28       343          29430     31510       20250       11260  [3430, 2025, 3151, 2943]  [100, 670, 343, 29430]
    32       440          20700     34503       20700       11253  [4400, 2325, 3450, 2070]  [100, 670, 440, 20700]
    36       549          10890     37501       10890       11251  [5490, 2625, 3750, 1089]  [100, 670, 549, 10890]
    40       670              0     40500           0       11250  [6700, 2925, 4050, 0]   [100, 670, 670, 0]
    44       670              0     29250           0           0  [6700, 2925, 2925, 0]   [100, 670, 670, 0]
    48       670              0         0           0           0  [6700, 0, 0, 0]         [0, 670, 670, 0]
  lim90_b15: peak FF_raw  29430, FF at setpoint 670 =    0, F_term peak 485.7
  lim0_b15 : peak FF_raw  40500, FF at setpoint 670 = 29250, F_term peak 668.4
  lim90_b0 : peak FF_raw  20700, FF at setpoint 670 =    0, F_term peak 341.6

== 6. RX-rate estimator 4.5.3 (rc.c:370-452), telemetry slot every 8th packet ==
   50 Hz: first cutoff  15 Hz at   1040 ms, within 1 Hz of final 18 Hz at   1680 ms after power-up
  500 Hz: first cutoff  18 Hz at   1004 ms, within 1 Hz of final 187 Hz at   1132 ms after power-up
```
The analysis.
- **Jitter.** The same movement gives an F term of ≈ 32–35 at 50–250 Hz, 23 at 500 Hz and 13 at 1000 Hz. This is not “weak FF on ELRS” but the default jitter 7 with a step of 3 and 1.5 units per packet. The options for 500 Hz on 4.5.3 (the author's choice, check with Blackbox): raise `f_*` or lower jitter to 5 (a multiplier of 0.84). The 4.3 Tuning Notes allow 5 only for racing on a clean link. The downside: a lower jitter lets through more gimbal noise, so for motors twitching with a still stick (the first line of the diagnostics) you go the other way — 10–12.
- **Duplicates.** Without extrapolation every second packet gives zero speed, and boost turns that into ±9000 °/s². 2_POINT removes the zigzag almost entirely (0.085), but not to zero, as extrapolation does. That is how 2025.12 works with CRSF: there is no extrapolation, but there is averaging and a PT1 with τ 7.4 ms.
- **The flip.** Up to 24 ms the limit does not interfere. From 28 ms it cuts FF: (670 − 343)·90 = 29,430, and at the stop FF = 0. Without the limit, on the packet where the setpoint reached 670, FF = 40,500 °/s² (F ≈ 668, more than the `pidsum_limit` of 500), and on the next packet another 29,250 (F ≈ 483). That is the overshoot at the end of a flip.
- **The first packet after rest.** At 4 ms FF = 1219, although 13 °/s in 4 ms is 3250 °/s². The packets at rest were duplicates, so the speed is computed over two intervals (×0.5) and also passes through the PT1 (×0.75).

**How to read the same thing in Blackbox Explorer (4.5.3).** In the CLI: `set debug_mode = FEEDFORWARD`, `set blackbox_sample_rate = 1/1` (or 1/2 at 8 kHz), `save`. The channels are written only for roll — the axis is hard-coded (`axis == FD_ROLL`, `rc.c:527–624`). The values are updated once per packet, so on the graph they are steps with the period of the link:
- debug[0] — rawSetpoint × 10 (°/s·10), before RC smoothing;
- debug[1] — the smoothed setpoint speed × 0.1 (°/s² / 10), without boost;
- debug[2] — speed + boost × 0.1, before transition, averaging, jitter and the limit;
- debug[3] — the final FF before the PT3 × 0.1.

The difference debug[2] − debug[1] is boost. The ratio debug[3]/debug[2] is transition, averaging, the jitter multiplier and the limit. In the lab at 28 ms it is 2943/3151: the limit cut ≈ 7 % (6.6 %). `debug_mode = FEEDFORWARD_LIMIT` gives [0] the jitter multiplier in %, [1] the maximum rate of the axis, [2] the setpoint, [3] the final FF unscaled. The Debug Modes page describes the 4.3 layout: there debug[3] is “RC Command delta”; the field labels in Explorer may follow it (not verified). For 4.5.3 trust the numbers and this list, not the labels. *2025.12: eight fields — [0] setpoint ×1, [1] speed ×0.01, [2] boost ×0.01, [3] Δ`rcCommand` ×10, [4] jitter %, [5] the duplicate flag, [6–7] yaw; the axis is selected by `gyro_filter_debug_axis`.*

### Moving to real hardware
Props off until item 4. Before making changes, save `diff all` to a file.

**1. `rxrange` with the radio (the bench, the battery need not be connected).** In the Receiver tab or through `rxrange` without arguments, write down the extreme values of each of the four channels at full stick travel (trims at zero, EdgeTX limits ±100 %). For ELRS expect 988/1500/2012 ± 1. Then:
```
rxrange 0 988 2012
rxrange 1 988 2012
rxrange 2 988 2012
rxrange 3 988 2012
save
```
After the reboot the stops should show 1000 and 2000 ± 2, the center — 1500 ± 2, and the throttle at the bottom — below 1050. If a stop after `rxrange` falls outside 885…2115 (extended limits in the radio), the channel is considered invalid, and failsafe follows after 300 ms: return the limits to 100 %.

**2. `rc_smoothing_info` with a real link.** The battery is connected, props off, the link has been up for more than 2 s. Run `rc_smoothing_info` at every packet rate you use: 150, 250, 500 Hz, F1000 (ELRS Lua; write down the telemetry ratio). The norm — `Detected Rx frequency` within ±3 % of the packet rate (for D250/D500 — 250/500), the “setpoint and FF” cutoff = ⌊0.375·f⌋ ± 1 Hz, and both cutoff lines `(auto)` (in 4.5 there are three cutoff lines). If the rate is lower by 10 % or more, these are lost packets: check the antennas and LQ.

**3. Three profiles on a switch.** Profiles 0–2 are filled in a random order that you do not know until landing. No helper is needed — the order is chosen by a random number generator, and the mapping is in a file that you open only after the flight. The one-person procedure: (a) put the three rate sets from the example below into three files `x.txt`, `y.txt`, `z.txt` — each with only the lines `set rates_type`, `set roll_*`, the same `set pitch_*` and yaw, without `rateprofile N` and without the name; (b) shuffle the order without looking at the result: `python -c "import random; o=['x.txt','y.txt','z.txt']; random.shuffle(o); open('order.txt','w').write('\n'.join(o))"`; (c) in a script with the `cli(port, cmds)` function from `bf-cli-automation`, assemble the commands from `order.txt` and upload them without printing them to the screen: `cmds = []`, then for every pair `i, f` from `enumerate(open('order.txt').read().split())` — `cmds += [f'rateprofile {i}'] + open(f).read().splitlines() + [f'set rateprofile_name = P{i}']`, then `out = cli(port, cmds + ['adjrange 0 0 2 900 2100 12 2 0 0', 'save'])`, `open('load.log','w').write(out)` and `print(out.count('###ERROR'))` — it should print 0; (d) until landing do not open `order.txt` and `load.log` and do not open Rateprofile Settings; (e) after the flight and your notes open `order.txt`: line 1 is the file that went into profile P0, line 2 — into P1, line 3 — into P2. An example layout of the three sets (here with the names A/B/C; in the blind variant the names are P0/P1/P2):
```
rateprofile 0
set rates_type = ACTUAL
set roll_rc_rate = 20
set roll_srate = 67
set roll_expo = 54
set rateprofile_name = A
rateprofile 1
set rates_type = BETAFLIGHT
set roll_rc_rate = 101
set roll_srate = 70
set roll_expo = 1
set rateprofile_name = B
rateprofile 2
set rates_type = ACTUAL
set roll_rc_rate = 7
set roll_srate = 67
set roll_expo = 0
set rateprofile_name = C
adjrange 0 0 2 900 2100 12 2 0 0
save
```
This is an example layout; the order of the blocks is rearranged arbitrarily. `pitch_*` in every profile are the same numbers as `roll_*`. `rates_type` applies to all axes, so set yaw to feel the same: 20/67/54 in A and C, 101/70/1 in B. Otherwise yaw in B stays at 7/67/0, which in the Betaflight model is an RC rate of 0.07, and yaw is almost dead. AUX3 (index 2) is a 3-position switch. The bench check: in Betaflight App (PID Tuning → Rateprofile Settings) the maximum of all three profiles is 670 ± 7 °/s, and the OSD shows A/B/C. In the blind variant do not open Rateprofile Settings (the numbers would give the order away): the bench check is that the `###ERROR` count is 0 and the OSD shows P0/P1/P2 as the switch is moved, and the 670 °/s maximum is checked after the flight from Blackbox.

**4. The flight (the props go on here).** A field with a 50 × 50 m margin, ACRO mode, a height from 5 m, Blackbox ≥ 1 kHz. In every profile: 30 s of smooth passes, 5 each of rolls and flips, a series of fast stick stabs. Switch the profile only in level flight at hover throttle. Abort the flight and return the switch to position 1 if the aircraft does not hold level, if LQ is below 70 %, or if a flip does not come out into level flight. The pilot writes down which profiles are the same. The criteria: the pilot considers the profiles holding 20/67/54 and 101/70/1 the same and tells 7/67/0 apart. In Blackbox `setpoint[0]` at full stick is 670 ± 1 % in all three profiles. At half stick travel the setpoint differs by no more than 10 °/s between the “same” ones and by about 27 °/s for the third (158 against 185 °/s). To save the chosen profile: disarm, then a stick save or `save`.

**5. Debug FEEDFORWARD on the bench (4.5.3, props off, can be done before item 4).** `set debug_mode = FEEDFORWARD`, `set blackbox_mode = ALWAYS` (the log is recorded without arming, the motors do not spin), `set blackbox_sample_rate = 1/2`, `save`. Record 20 s: the roll stick still for 5 s, then 5 slow passes from center to stop (about 1 s each) and 5 sharp snaps. Restore `blackbox_mode = NORMAL` and `debug_mode = NONE`. The criteria in Explorer: with a still stick |debug[3]| ≤ 5 (≈ 50 °/s², the author's threshold for this check) most of the time (the jitter filter suppresses the tremor); at the stop debug[0] = max_rate × 10 ± 1 % (after `rxrange`); after the stick stops debug[1] falls to 0 within 1–2 packets; on a sharp snap near the stop debug[3] is noticeably smaller than debug[2] (the limit is working).

Self-check: the lab is complete when:
- **Calculation (the main path):** the script with the functions from `fc/rc.c` has been run, and its output matches the output in the module: the converter for the two Actual profiles (RMS 2.5 °/s and a maximum of 4 °/s for 200/670/0.54; RMS 95.4 and a maximum of 151 °/s for 7/67/0), the PT3 smoothing table for 50/150/250/500/1000 Hz (cutoffs 18/56/93/187/375 Hz) and the jitter filter calculation (FF × 1.00 at 50 Hz, × 0.27 at 1000 Hz).
- **Calculation (FF 4.5.3):** `ff_lab.py` has been run, and the output matches the module: Actual 185.0 and 232.0 °/s at x = 0.5; a jitter multiplier of 0.673 at 500 Hz and 0.383 at 1000 Hz at 1500 units/s; a zigzag of 0.016 / 11.257 with and without duplicate extrapolation; an FF peak on the flip of 29,430 with the limit and 40,500 without it, and on the first two packets at the stop without the limit — 40,500 and 29,250 °/s², with the limit — 0; a cutoff of 187 ± 1 Hz after 1.13 s (500 Hz) and 18 ± 1 Hz after 1.68 s (50 Hz).
- **Calculation:** you explained in writing, for yourself, why Actual 7/67/0 does not convert to Betaflight with an error below 20 °/s, and compared the text with the reference below.
- **Hardware:** `rxrange` is set, the stops are 1000/2000 ± 2. The `rc_smoothing_info` outputs for two packet rates are saved: the rate is within ±3 %, and the cutoff equals ⌊0.375·f⌋ ± 1 Hz.
- **Hardware:** the debug FEEDFORWARD log was recorded on the bench, and all four criteria of item 5 are met.
- **Hardware:** the blind comparison of the three profiles was carried out; the flight folder holds the Blackbox log and your notes, and after the order is revealed the criteria of item 4 are met: `setpoint[0]` at full stick is 670 ± 1 % in all three profiles, at half travel the “same” ones differ by no more than 10 °/s, and the third — by about 27 °/s (158 against 185 °/s).

**Reference for self-check.** The correct explanation: an Actual curve with low expo is close to a parabola, while super rate gives a hyperbola that lies low and shoots up near the end; the converter matches only the center and the maximum, so up to 151 °/s remains in the middle of the travel (stick 0.71). The explanation “expo was badly chosen” is wrong: the search over 0…100 already picked the best one (89), and the error is a property of the curve shape. If your RMS for 7/67/0 came out at about 2.5 °/s — the profile 200/670/0.54 (`rc_rate` 20) was given to the converter, not the default. If the PT3 cutoff is not 0.375·f — the calculation does not use factor 30. For FF 4.5.3: if the jitter multiplier at 500 Hz came out as 0.500 instead of 0.673 — the linear 2025.12 formula was used ((3 + 3)/2 + 1)/(1 + 7); if 0.429 — the square was forgotten: 1 − (1 − 6/14). The correct value is 1 − (1 − 6/14)² = 0.673. If on the flip FF at sp = 670 is not zero with a limit of 90 — the limit was multiplied by 0.9 instead of 90. If at 4 ms you have 2437 and not 1219 — it was not taken into account that the packets at rest were duplicates and the speed is computed over two intervals.

## diagnostics
- **Symptom:** the motors twitch and heat up with still sticks, and in Blackbox FF is noisy “grass”
  - Possible cause: gimbal noise or the noise of a 250–1000 Hz link gets into feedforward; on 2025.12 — a `feedforward_smooth_factor` that is too low or `averaging = OFF` in a config that was carried over; on 4.5 the default 25 is “per packet”, so at 500 Hz it gives only 0.67 ms, and averaging is off.
  - What to do: restore the 2025.12 defaults (65 and `2_POINT`; on 4.5 set them by hand for 500 Hz), `feedforward_jitter_factor` 10–12. A test flight with `f_roll`/`f_pitch` = 0: if it becomes clean, the problem is in FF.
  - What you see in the log: `debug_mode = FEEDFORWARD_LIMIT`, the field debug[3] (FF ×0.01 before averaging, the axis `gyro_filter_debug_axis`, roll by default; in 4.5 — `debug_mode = FEEDFORWARD`, debug[3], ×0.1) jumps with an almost constant rcCommand.
- **Symptom:** at the end of a flip or a roll the aircraft overshoots the maximum rate and bounces back
  - Possible cause: `feedforward_max_rate_limit = 0` or a `feedforward_boost` that is too high: FF keeps pushing at the stop (the lab: 40,500 and 29,250 °/s² on the first two packets at the stop, F ≈ 668 and 483).
  - What to do: restore the limit of 90 (the default), boost — no higher than the default 15 (10–15 is the author's guideline).
  - What you see in the log: on 4.5.3 in `debug_mode = FEEDFORWARD` debug[3] ≈ debug[2] at the stop; on 2025.12 in `FEEDFORWARD_LIMIT` debug[3] (FF ×0.01) does not fall when debug[2] (the setpoint) ≈ debug[1] (the max rate); the gyro is above the setpoint.
- **Symptom:** on 4.5.3 with ELRS 500 Hz / F1000 smooth movements lag, and FF is “weak”
  - Possible cause: jitter 7 with a step of 1.5–3 units per packet cuts FF to 0.38–0.67.
  - What to do: raise `f_roll`/`f_pitch` or lower `feedforward_jitter_factor` to 5 (the 4.3 Tuning Notes allow 5 only for racing on a clean link; a lower jitter lets through more gimbal noise — for motors twitching with a still stick you go the other way, 10–12); check debug[0] in `FEEDFORWARD_LIMIT` on smooth movements.
- **Symptom:** the stick is “mushy”, and the aircraft lags on fast movements
  - Possible cause: a low packet rate (50 Hz, an 18 Hz cutoff), a `rc_smoothing_auto_factor` that is too high, or a manual cutoff.
  - What to do: `rc_smoothing_info`; raise the packet rate, restore factor 30 and `*_cutoff = 0`.
- **Symptom:** at 50 Hz or with `rc_smoothing = OFF` the aircraft shakes finely and the motors are noisy
  - Possible cause: setpoint steps once per 20 ms, and D and FF amplify each one.
  - What to do: `rc_smoothing = ON`; for an unstable Crossfire — a manual cutoff of 20–30 Hz.
- **Symptom:** `rc_smoothing_info` shows `NO SIGNAL` or a rate far below the packet rate
  - Possible cause: no link, poor LQ, ELRS in a different mode, frequent interval outliers.
  - What to do: check the link and LQ in the Receiver tab, repeat 2 s after recovery.
- **Symptom:** the last millimeters of stick travel change nothing, the full rate comes “before the stop”
  - Possible cause: CRSF outputs 988–2012, and `rcCommand` is limited to ±500.
  - What to do: `rxrange <ch> 988 2012` for channels 0–3.
- **Symptom:** after `rates_type` was changed the aircraft became uncontrollably slow or fast
  - Possible cause: the numbers were not converted: Actual 7/67 in Betaflight is an RC rate of 0.07.
  - What to do: convert the profile with the converter, then check the maximum in PID Tuning → Rateprofile Settings.
- **Symptom:** the rate profile switch changes nothing in positions 5–6
  - Possible cause: `rate_6pos_switch = ON`, while there are only four profiles.
  - What to do: a 3-position switch, or ranges for the indices 0–3.
- **Symptom:** `thr_mid` was changed, but the throttle behaves the same
  - Possible cause: 4.5 firmware and `thr_expo = 0` — there the curve without expo is a straight line. In 2025.12 `thr_mid` has an effect without expo too, if it is not equal to `thr_hover`.
  - What to do: on 4.5 set `thr_expo` to 20–50; on 2025.12 check the `thr_mid`/`thr_hover` pair and the hover point in PID Tuning → Rateprofile Settings.
- **Symptom:** a `diff` after the setup does not contain the rates of the other profiles
  - Possible cause: `diff`/`diff rates` print only the current profile.
  - What to do: back up only through `diff all`.

## checklist
- `diff all` is saved before the changes
- `rxrange` is set for channels 0–3, the stops are 1000/2000, the center is 1500
- The rate type and the numbers are checked in PID Tuning → Rateprofile Settings: center, maximum, mid-travel
- When `rates_type` is changed the profile is converted with a check of the RMS error
- `rc_smoothing = ON`, and `rc_smoothing_info` shows the real link rate and `(auto)`
- The FF parameters match the packet rate (smooth, averaging, jitter)
- The rate profiles are named (`rateprofile_name`), and switching is checked on the bench
- After the flight the chosen profile is saved, and `diff all` with the date is in a file

## references
- Betaflight `fc/rc.c` (rates, RC smoothing, feedforward), 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/fc/rc.c | primary | A
- Betaflight `fc/controlrate_profile.c` (the rate defaults and limits) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/fc/controlrate_profile.c | primary | A
- Betaflight `pg/rx.c` (rc_smoothing, mid_rc, min_check, rx_min_usec) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/pg/rx.c | primary | A
- Betaflight `cli/cli.c` (rxrange, rateprofile, rc_smoothing_info) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/cli/cli.c | primary | A
- Betaflight `flight/pid.c` (the feedforward_* and f_* defaults) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/pid.c | primary | A
- Betaflight `rx/crsf.c` (172…1811 → 988…2012 µs) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/rx/crsf.c | primary | A
- Betaflight `fc/rc.c`, tag 4.5.3 (applyActualRates, calculateFeedforward, the RX rate estimate) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/fc/rc.c | primary | A
- Betaflight `flight/pid_init.c`, tag 4.5.3 (the FF coefficients, Kf) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/flight/pid_init.c | primary | A
- Betaflight `rx/rx.c`, tag 4.5.3 (rxGetFrameDelta) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/rx/rx.c | primary | A
- Betaflight `build/debug.c`, tag 4.5.3 (the debug_mode names) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/build/debug.c | primary | A
- Betaflight Debug Modes (the 4.3 FEEDFORWARD layout) | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/guides/current/Debug-Modes.md | primary | B
- Betaflight `fc/rc.c`, tag 2025.12.5 (smoothing, FF, the throttle curve) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/fc/rc.c | primary | A
- Betaflight `flight/pid_init.c`, tag 2025.12.5 (the normalization of feedforward_smooth_factor, yaw hold) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/flight/pid_init.c | primary | A
- Betaflight 4.3 Tuning Notes (PT3 RC smoothing, jitter reduction, ELRS 250/500 Hz) | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/tuning/4-3-Tuning-Notes.md | primary | A
- Betaflight Rate Calculator (the rate types, converters) | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/guides/current/Rate-Calculator.md | primary | B
- EdgeTX `pulses/crossfire.cpp` (crossfireSetupMixerScheduler: the mixer period from the module's packet rate) | https://raw.githubusercontent.com/EdgeTX/edgetx/main/radio/src/pulses/crossfire.cpp | primary | B
- ExpressLRS `common.cpp` (the packet intervals and repeats by mode) | https://raw.githubusercontent.com/ExpressLRS/ExpressLRS/master/src/src/common.cpp | primary | B

## notes
The `rc_smoothing_info` output in the theory is assembled from the `cliRcSmoothing()` format (2025.12.5) and the rates from the lab; it was not captured from a board. The FF advice for 250/500 Hz, jitter 10–12 / 5, factor 20 and 90–120, and a manual cutoff of 20–30 Hz are from the 4.3 Tuning Notes (checked against the text of the document on 2026-11-25); the mechanisms described there are in `rc.c` 4.5. The 2025.12 defaults (2_POINT, 65) match the advice for 500 Hz only by the number: the smooth scale in 2025.12 is different. No official recommendation was found for F1000. The thresholds and advice marked “the author's inference/guideline” were obtained from the calculations of the module, not from the documentation.
