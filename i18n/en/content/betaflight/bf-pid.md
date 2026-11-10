---
id: bf-pid
title: "Data-Driven PID Tuning"
level: L2
readingTime: 30 min
firmware: Betaflight 4.5+
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
next:
  - bf-cli
source: content/betaflight/bf-pid.md
source_hash: b05992625bbe
---

## summary
“Crisper,” “softer,” “it wobbles,” “it runs hot” — pilot feelings that can be turned into numbers from the log so you can compare profiles honestly. This module gives you a working method: filters before PID, one parameter per step, four profiles in one flight, five per-maneuver metrics. The case study is an experiment on two identical 7" drones: four profiles, what matched the feelings, what didn't, and why the outcome was not a new PID but new filters.

## theory
### Order: filters first, then PID
PID amplifies everything that comes from the gyro, noise included. Tuning PID on bad filters is like tuning an amplifier against a background of interference. So: the RPM filter and the dynamic notch are working, the spectrum is clean (the filter and RPM filter modules), and only then — PID.

### Betaflight 4.3+ sliders
The simplified tuning mode turns groups of parameters at once:

- **Damping** (D) — resistance to fast movements, damps overshoot; higher — the motors heat up.
- **Tracking** (P and I) — how precisely it follows the stick and disturbances; higher — oscillations.
- **Stick Response** (FF) — response to fast stick movements; higher — overshoot at the end of a flip.
- **Dynamic Damping** (D max) — how much D can grow on fast moves.
- **Drift – Wobble** (I) — holding in turns and at zero throttle.
- **Master Multiplier** — everything at once; you touch it when the others run out of travel.

In the CLI these are `simplified_pi_gain`, `simplified_d_gain`, `simplified_feedforward_gain`, `simplified_dmax_gain` (in 2025.12 — `simplified_d_max_gain`), `simplified_i_gain`, `simplified_master_multiplier` plus `simplified_tuning apply`. There are four PID profiles and four rate profiles — switched from a switch or in the CLI with the `profile N` command.

{{widget:pid-sim}}

### Symptoms
- P too high — twitchy, overcorrects, fast oscillation. Too low — sluggish, slow wobble.
- I too high — “robotic,” low-frequency oscillation. Too low — drifts off, “skates like on ice.”
- D too low — bounce-back after flips, propwash on descents. Too high — hot motors, mushy response.
- FF too high — overshoot at the start of a flip, jitter on stick movements.

Check motor temperature after every change to D or the filters: a short flight, land, finger on the motor. If you can't hold it — roll back.

### Five per-maneuver metrics
A maneuver is a segment where |setpoint| is above a threshold (for example, 200 °/s) for longer than 50 ms. For each one:

| Feeling | Metric | How to compute |
|---|---|---|
| runs hot | **motor noise** | std of motor commands above 40 Hz, averaged over motors |
| shakes on descent | **propwash RMS** | gyro RMS in the 20–70 Hz band on descent segments |
| wobbles after a stop | **bounce-back** | opposite-sign gyro peak within 150 ms after the stop / maneuver amplitude, % |
| slow on the stick | **entry lag** | time from the start of setpoint movement to 50% on gyro, ms |
| undershoots / overshoots | **peak tracking** | max gyro / max setpoint, % |

The median over 10–20 maneuvers is robust; one bad snap ruins the mean. The classic step response (Blackbox Explorer; PID-Analyzer — not developed since 2019, PIDscope) works well on long freestyle logs, but on short logs of 1–2 minutes per profile it is noisy to ±40% — direct metrics are more honest.

### Case study: four profiles on two 7" drones
Two nearly identical 7" drones (same frame, motors, props, FC), brought to a common baseline. The four profiles differed only in sliders; filters were the same:

| | COOL | SHARP | WASH | FLOAT |
|---|---|---|---|---|
| Tracking | 1.00 | **1.15** | 1.00 | 1.00 |
| Damping | 1.00 | 1.00 | **1.20** | **0.85** |
| D max | 1.00 | 1.00 | **1.20** | 1.00 |
| Feedforward | 1.00 | **1.15** | 1.00 | **0.80** |

Result (drone A, medians): motor noise 16.1 / 23.3 / 18.0 / 14.6; bounce-back 6.0 / 8.5 / 9.4 / 14.9%; entry lag 38 / 31 / 40 / 44 ms.

- **SHARP “crisper”** — yes: lag is 7 ms lower. The price — motor noise +45%. That's P: it raises the gain at all frequencies.
- **FLOAT “softer”** — yes, the quietest. But bounce-back is almost 15%: after a stop the drone rolls back by 1/7 of the amplitude. Bad for filming.
- **WASH “didn't feel a difference”** — and the numbers confirmed it: propwash 0.97 of COOL, within the noise. At 1.4 kg on 7" props, propwash is aerodynamics, not underdamping. The profile was dropped.
- **The two “identical” drones gave different bounce-back on SHARP** (2.9% vs. 8.5%): on the second one the pilot flew harder, and D-max had time to kick in. The lesson about the method: compare profiles only within a single flight or normalize to the maneuver amplitude.

**Outcome:** COOL is the best compromise. Crispness was brought back not through P but through the filters: `simplified_gyro_filter_multiplier` 1.00 → 1.10 and `dyn_notch_q` 400 → 450, PID as in COOL. That's how the CRISP profile came about. The first proposal was more aggressive (1.25 and a single notch); it was rejected in favor of small steps: 1.10 → flight → if successful, 1.20.

### Tuning protocol (by data, not by feel)
1. **Baseline**: 4.5 defaults, filters per the “Filters” module, clean spectrum, cold motors. Log A: 30 s hover + 10 maneuvers with a sharp stop on roll/pitch + 3 descents with propwash.
2. **Metrics** from log A (`data-python`: `step_metrics`, `bounce_back`, motor noise, propwash RMS) — into a table.
3. **One slider per flight**: Damping ±0.1 → log → metrics; then Tracking ±0.1; then Stick Response. Acceptance criterion: the target metric improved, the others didn't get worse, the motors aren't hotter.
4. **A profile for the job**: racing (higher Tracking, higher Stick Response) and calm (higher Damping) — different `profile`s, switched from a switch.
5. **Lock it in**: `diff all` + a “what — why — metrics before/after” table in the repository (the “CI” module).
One flight — one change. Two changes in one flight make the log useless.

### Metric reference values for 5" 6S
| Metric | Good | Tolerable | Problem |
|---|---|---|---|
| overshoot | 3–10% | 10–20% | > 20% (P/FF) |
| bounce-back | < 8% | 8–15% | > 15% (D, delay) |
| entry lag (to 50%) | 20–35 ms | 35–50 | > 50 (FF, filters) |
| settle (±5%) | < 80 ms | 80–150 | > 150 |
| motor noise (std > 40 Hz) | low, stable | grows with D | “grass” on the motor trace |
| motor temperature | warm | too hot to touch for 5 s | can't hold a finger on it |
For 7–10" all times are ×1.5–2, overshoot is lower (inertia), bounce-back is more sensitive to delay.

### What not to do
Don't tune in wind > 5 m/s (I and position metrics lie); don't change PID and filters in the same flight; don't copy someone else's whole `diff all` (different motors, props, weight, delays); don't “fix” mechanics with the D-term.

{{diagram:bf-tuning-loop|Data-driven tuning: filters first, then one change → scripted flight → metrics → decision or rollback.}}

## practice
### Step 1. Baseline
Filters clean, RPM filter working, sliders at 1.00, `diff all` saved with a date. This is the control profile.

### Step 2. Four profiles
In profiles 1–4 set up variants that differ by one or two sliders. Switch them from a switch (a mode or `adjustment`) so you can change them in the air.

### Step 3. Flight program
The same for all profiles: 20 s of hover, 10 sharp snaps on roll, 10 on pitch, three descents at zero throttle. Profiles one after another in a single flight. After each — a note in `session_notes.md`: order, wind, feel, motor temperature.

### Step 4. Metrics
Parse the log in Python (`orangebox` for reading, `scipy` for spectra). Trim the first and last 3 s, compute noise on segments with 25–60% throttle, discard logs with frame loss above 1%. Compare medians.

### Step 5. One step at a time
The winning profile becomes the new baseline. The next change — one, small, with a flight and a log. Going back is one flick of a switch: the control profile stays in its slot.

## diagnostics
- **Symptom:** step response “jumps” between neighboring maneuvers
  - Possible cause: short log, smooth flying style, ANGLE mode.
  - What to do: direct per-maneuver metrics, medians, ACRO for the test.
- **Symptom:** motors are hot after the high-D profile
  - Possible cause: D amplifies residual noise.
  - What to do: put D back, improve the filters, then repeat.
- **Symptom:** propwash doesn't respond to D
  - Possible cause: the aerodynamics of a heavy drone on small props.
  - What to do: different props/weight, TPA, don't crank up D.
- **Symptom:** two identical drones give different numbers
  - Possible cause: a de facto different flight program.
  - What to do: compare profiles within one flight, normalize to the amplitude.

## references
- PID Tuning Guide — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/PID-Tuning-Guide | primary | A
- PID Tuning tab — Betaflight App | https://betaflight.com/docs/wiki/app/pid-tuning-tab | primary | A
- Betaflight settings reference (settings.c, GitHub) | https://github.com/betaflight/betaflight/blob/master/src/main/cli/settings.c | primary | A
- PID-Analyzer — step response tool (legacy, unmaintained since 2019) | https://github.com/Plasmatree/PID-Analyzer | secondary | C

## checklist
- Filters tuned before PID, spectrum clean
- Control profile saved and kept in its slot
- Profiles differ by one or two sliders
- One flight program for all profiles, notes in session_notes
- Metrics are medians over maneuvers, not means
- One step at a time, with a log
