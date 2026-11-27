---
id: bf-pid
title: "Tuning PID from data"
level: L2
readingTime: 30 min
firmware: Betaflight 2025.12 (checked against 2025.12.5)
status: published
added: 2026-11-07
tags:
  - PID
  - tuning
  - Blackbox
related:
  - bf-pid-reg-in-bf
  - bf-filters
  - bf-blackbox
  - bf-tuning-method
  - bf-motor-balance
next:
  - bf-cli
source: content/betaflight/bf-pid.md
source_hash: ba2a0db04a9a
---

## summary
“Sharper”, “softer”, “it wobbles”, “it runs hot” — these are a pilot's impressions, and they can be turned into numbers from the log so that profiles are compared fairly. This module gives a working method: filters before PID, one parameter per step, four profiles — four short flights in a row with one program, five metrics computed per maneuver. The case is an experiment on two identical 7" quads: four profiles, what matched the impressions and what did not, and why the outcome was not a new PID but new filters.

## theory
### The order: filters first, then PID
PID amplifies everything that comes from the gyro, including noise. Choosing PID gains on bad filters is tuning an amplifier against a background of interference. So: the RPM filter and the dynamic notch are working, the spectrum is clean (the modules on filters and the RPM filter), and only then — PID.

{{lesson:bf-motor-balance|Even before the filters come the mechanics: the motor medians from the log reveal an offset center of gravity, a weak motor and a yaw imbalance that PID only “holds with current”.}}

### The Betaflight 4.3+ sliders
The simplified tuning mode moves groups of parameters at once:

- **Damping** (D) — resistance to fast movements, damps overshoot; higher — the motors run hot.
- **Tracking** (P and I) — how accurately the aircraft follows the stick and rejects disturbances; higher — oscillations.
- **Stick Response** (FF) — the reaction to fast stick movements; higher — overshoot at the end of a flip.
- **Dynamic Damping** (D max) — how much D may rise on fast movements.
- **Drift - Wobble** (I) — holding in turns and at zero throttle.
- **Master Multiplier** — everything at once; it is touched when the others run out of travel.

In the CLI these are `simplified_pi_gain`, `simplified_d_gain`, `simplified_feedforward_gain`, `simplified_d_max_gain` (before 2025.12 — `simplified_dmax_gain`), `simplified_i_gain`, `simplified_master_multiplier` plus `simplified_tuning apply`. There are four PID profiles and four rate profiles. Only the rate profile can be switched in flight (the `RATE PROFILE` adjustment). The PID profile is changed only on the ground while disarmed: with the sticks, through the OSD menu, in Betaflight App or in the CLI with the `profile N` command (N = 0–3) — there is neither a mode nor an adjustment for it.

{{widget:pid-sim}}

### Symptoms
- P too high — twitchy, overcorrects, fast oscillation. Too low — sluggish, slow wobble.
- I too high — “robotic”, low-frequency oscillation. Too low — drifts, “slides as if on ice”.
- D too low — bounce-back after flips, propwash in descents. Too high — hot motors, a mushy response.
- FF too high — overshoot at the start of a flip, shake on stick movements.

Check the motor temperature after every change of D or the filters: a short flight, land, a finger on a motor. If you cannot hold it — roll back.

### Five metrics per maneuver
A maneuver is a segment where |setpoint| is above a threshold (for example, 200 °/s) for longer than 50 ms. For each:

| Impression | Metric | How to compute it |
|---|---|---|
| runs hot | **motor noise** | the std of the motor commands above 40 Hz, averaged over the motors |
| shakes in descents | **propwash RMS** | the gyro RMS in the 20–70 Hz band over the descent segments |
| wobbles after a stop | **bounce-back** | the gyro peak of the opposite sign within 150 ms after the stop / the maneuver amplitude, % |
| slow on the stick | **entry lag** | the time from the start of the setpoint movement to 50% on the gyro, ms |
| undershoots / overshoots | **peak tracking** | max gyro / max setpoint, % |

The median over 10–20 maneuvers is robust; the mean is spoiled by one bad snap. The classic step response (Blackbox Explorer; PID-Analyzer — not developed since 2019, PIDscope) is good on long freestyle logs, but on short logs of 1–2 minutes per profile it is noisy to ±40% — direct metrics are more honest.

### A case: four profiles on two 7" quads
Two almost identical 7" quads (the same frame, motors, props, FC), brought to a common baseline. The four profiles differed only in the sliders, with identical filters; each profile had its own short flight, four flights in a row with one program:

| | COOL | SHARP | WASH | FLOAT |
|---|---|---|---|---|
| Tracking | 1.00 | **1.15** | 1.00 | 1.00 |
| Damping | 1.00 | 1.00 | **1.20** | **0.85** |
| D max | 1.00 | 1.00 | **1.20** | 1.00 |
| Feedforward | 1.00 | **1.15** | 1.00 | **0.80** |

The result (drone A, four flights, medians): motor noise 16.1 / 23.3 / 18.0 / 14.6; bounce-back 6.0 / 8.5 / 9.4 / 14.9%; entry lag 38 / 31 / 40 / 44 ms.

- **SHARP “sharper”** — yes: the lag is 7 ms shorter. The price is +45% motor noise. That is P: it raises the gain at all frequencies.
- **FLOAT “softer”** — yes, the quietest. But bounce-back is almost 15%: after a stop the drone rolls back by 1/7 of the amplitude. That is bad for filming.
- **WASH “felt no difference”** — and the numbers confirmed it: propwash is 0.97 of COOL, within the noise. At 1.4 kg under 7" props propwash is aerodynamics, not underdamping. The profile was dropped.
- **Two “identical” drones gave a different bounce-back for SHARP** (2.9% against 8.5%): on the second one the pilot flew more sharply, and D max had time to kick in. The conclusion about the method: compare profiles only within one series of flights (one pilot, one program, one charge window) or normalize by the maneuver amplitude.

**The outcome:** COOL is the best compromise. Sharpness was restored not through P but through the filters: `simplified_gyro_filter_multiplier` 1.00 → 1.10 and `dyn_notch_q` 400 → 450, with PID as in COOL. That is how the CRISP profile appeared. The first proposal was more aggressive (1.25 and one notch); it was rejected in favor of small steps: 1.10 → a flight → 1.20 on success.

### The tuning protocol (from data, not from impressions)
1. **Baseline**: the 2025.12 defaults (D: `d_roll` 30 — the base, `d_max_roll` 40 — the peak; in 4.5 the same numbers were called `d_min_roll` and `d_roll`), the filters per the “Filters” module, a clean spectrum, cool motors. Log A: 30 s of hover + 10 maneuvers with a sharp stop in roll/pitch + 3 descents with propwash.
2. **The metrics** from log A (`data-python`: `step_metrics`, `bounce_back`, motor noise, propwash RMS) — into a table.
3. **One slider per flight**: Damping ±0.1 → a log → the metrics; then Tracking ±0.1; then Stick Response. The acceptance criterion: the target metric improved, the others did not get worse, the motors are no hotter.
4. **A profile for the task**: a racing one (higher Tracking, higher Stick Response) and a calm one (higher Damping) are different `profile` slots; the choice is made on the ground (with the sticks while disarmed, the OSD menu, `profile N`): the PID profile is not switched in flight.
5. **Recording**: `diff all` + a table “what — why — metrics before/after” into the repository (the “CI” module).
One flight — one change. Two changes per flight make the log useless.

{{lesson:bf-tuning-method|How to prove that profile B is better than A and that it did not just seem so: the ABBA order, how many flights are needed and a permutation test on the logs.}}

### Metric guidelines for a 5" 6S
| Metric | Good | Tolerable | Problem |
|---|---|---|---|
| overshoot | 3–10% | 10–20% | > 20% (P/FF) |
| bounce-back | < 8% | 8–15% | > 15% (D, delay) |
| entry lag (to 50%) | 20–35 ms | 35–50 | > 50 (FF, filters) |
| settle (±5%) | < 80 ms | 80–150 | > 150 |
| motor noise (std > 40 Hz) | low, stable | grows with D | “grass” on the motor traces |
| motor temperature | warm | hot to the touch for 5 s | cannot keep a finger on |
For 7–10" all the times are ×1.5–2, overshoot is lower (inertia), and bounce-back is more sensitive to delay (a course estimate: the moment of inertia grows faster than the torque from the motors, `f-mechanics`; there is no source with numbers). For whoops and X8 there are no guidelines: the reference is the aircraft's own best log, and the rule “±0.1 of a slider per flight” compares against it.

TPA (the formula and the guideline — `bf-pid-reg-in-bf`, “TPA”): D is attenuated above `tpa_breakpoint` (1350 by default). On a heavy aircraft that hovers above 1350 (a hover throttle of more than 35 %), D is attenuated already in hover: at 1500 — ×0.85 with the defaults. If there is not enough D in hover and small maneuvers (bounce-back, propwash) and there are no oscillations at high throttle — raise `tpa_breakpoint` above the hover throttle (a course guideline); the check is `debug_mode = TPA` (the factor × 1000) ≈ 1000 in hover.

### What not to do
Do not tune in wind > 5 m/s (I and the position metrics lie); do not change PID and the filters in one flight; do not copy someone else's `diff all` wholesale (different motors, props, mass, delays); do not “cure” mechanics with the D term.

{{diagram:bf-tuning-loop|Tuning from data: filters first, then one change → a flight with the program → the metrics → a decision or a rollback.}}

### Place in the system

- **Receives:** a clean spectrum after the filters and the RPM filter (`bf-filters`, `bf-rpm-filter`); a log with the setpoint, the gyro and the motors (`bf-blackbox`); the metric functions (`data-python`).
- **Provides:** the slider values and PID profiles — to the controller (`bf-pid-reg-in-bf`); the table “what — why — metrics before/after” and `diff all` — to the repository (`eng-ci-configs`).
- **If you get it wrong here:** you raised Tracking for sharpness → the noise of the motor commands grew (by 45 % in the case), and the motors run hot; the right path turned out to be through the filters (`bf-filters`). You set Damping too high → hot motors and a mushy response; the check is the temperature after a short flight and `axisD` in the log (`bf-blackbox`). You changed PID and the filters in one flight → the log is useless, and the cause of the change cannot be found.

## practice
### Step 1. The baseline
The filters are clean, the RPM filter is working, the sliders are at 1.00, `diff all` is saved with the date. This is the control profile.

### Step 2. Four profiles
In profiles 1–4 set variants that differ in one or two sliders. They cannot be switched from a switch: `fc/rc_adjustments.c` (4.5 and 2025.12) has an adjustment for the rate, OSD and LED profiles but none for the PID profile, and there is no such mode either. The PID profile is changed only on the ground while disarmed:

- **with the sticks** (Mode 2: the left stick — throttle down and yaw left, and with the right stick): roll left — profile 1, pitch forward — profile 2, roll right — profile 3 (`fc/rc_controls.c`); the confirmation is as many beeps as the number. There is no stick command for profile 4;
- **the OSD menu** (throttle in the middle + yaw left + pitch forward): PROFILE → PID PROF — this works for profile 4 too;
- Betaflight App or the CLI `profile 0`…`profile 3`.

A choice made with the sticks or through the menu without SAVE lasts until the battery is reconnected: after power-up the saved profile returns, so check the number (the beeps or the OSD element with the PID profile name) before every takeoff.

If the comparison has to be made in one flight, the honest alternative is rate profiles: they are switched in the air by the `RATE PROFILE` adjustment (function 12 in `adjrange`). But a rate profile holds only the rates, expo, the throttle curve and `throttle_limit`; PID, the sliders, D max and FF live in the PID profile and cannot be moved there.

### Step 3. The flight program
The same for all the profiles: 20 s of hover, 10 sharp snaps in roll, 10 in pitch, three descents at zero throttle. Four short flights in a row, one per profile: land, disarm, switch the profile, check the number, take off. One charge window: every flight on a fresh battery from one batch, charged the same way, landing at the same voltage per cell. Shift the order of the profiles in the next series (1-2-3-4 → 2-3-4-1), so that wind and motor heating do not always fall on the same profile. After every flight — an entry in `session_notes.md`: the order, the wind, the impressions, the motor temperature.

### Step 4. The metrics
Analyze the log in Python (`orangebox` for reading, `scipy` for the spectra). Cut off the first and last 3 s, compute the noise on segments with 25–60% throttle, and do not use logs with more than 1% of frames lost. Compare the medians. Check yourself against the table “Metric guidelines for a 5" 6S” in the theory (bounce-back < 8% — good, > 15% — a problem; overshoot 3–10% — good, > 20% — a problem). A profile wins if the target metric improved, the others did not get worse, and the motors are no hotter. A difference within the noise — like the 0.97 of WASH in the worked case — does not count as a win.

### Step 5. One step at a time
The winning profile is the new baseline. The next change is a single, small one, with a flight and a log. Going back takes one stick command on the ground: the control profile stays in its slot.

## diagnostics
- **Symptom:** the step response “jumps” between neighboring maneuvers
  - Possible cause: a short log, a smooth flying style, ANGLE mode.
  - What to do: direct metrics per maneuver, medians, ACRO for the test.
- **Symptom:** the motors are hot after a profile with high D
  - Possible cause: D amplifies the residual noise.
  - What to do: restore D, improve the filters, then repeat.
- **Symptom:** propwash does not go away with D
  - Possible cause: the aerodynamics of a heavy drone under small props.
  - What to do: different props/weight, TPA, do not push D up.
- **Symptom:** two identical drones give different numbers
  - Possible cause: a de facto different flight program.
  - What to do: compare profiles within one series of flights with one program and one charge window, normalize by the amplitude.

## references
- PID Tuning Guide — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/PID-Tuning-Guide | primary | A
- PID Tuning tab — Betaflight App | https://betaflight.com/docs/wiki/app/pid-tuning-tab | primary | A
- Betaflight settings reference (settings.c, GitHub) | https://github.com/betaflight/betaflight/blob/master/src/main/cli/settings.c | primary | A
- PID-Analyzer — step response tool (legacy, unmaintained since 2019) | https://github.com/Plasmatree/PID-Analyzer | secondary | C

## checklist
- The filters are set up before PID, the spectrum is clean
- The control profile is saved and stays in its slot
- The profiles differ in one or two sliders
- One flight program for all the profiles, entries in session_notes
- The metrics are medians over the maneuvers, not means
- One step at a time, with a log
