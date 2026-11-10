---
id: ap-tuning
title: "ArduPilot tuning: AUTOTUNE, filters, ESC-based notch"
level: L3
readingTime: 40 min
firmware: ArduPilot
status: published
added: 2026-11-08
tags:
  - AUTOTUNE
  - harmonic notch
  - tuning
  - ArduPilot
related:
  - ap-logs
  - bf-filters
  - ctl-signals
  - ctl-theory
  - ap-heavy
next:
  - ap-safety-fs
source: content/ardupilot/ap-tuning.md
source_hash: 2bf448bc3b3b
---

## summary
Tuning ArduCopter isn't “run AUTOTUNE” — it's seven steps in the right order: parameters for the vehicle size → first stable flight → assessment → harmonic notch on motor noise → manual/QuikTune roll-pitch → AUTOTUNE axis by axis → input shaping for feel. This module walks through them with parameters and log checks (`ATT`, `RATE`, `VIBE`, spectra from batch sampling/raw IMU), explains what AUTOTUNE does internally (and why it needs noise below a threshold), and how to set up a notch tracking ESC telemetry or throttle. The lab is in SITL and in the field.

## theory
### Step 1. Parameters before the first flight
Starting values depend on prop size (the “Setting the Aircraft Up for Tuning” document): `INS_GYRO_FILTER` (80 Hz for 5", 40 for 10", 20 for 20" and larger), `ATC_RAT_*_FLTD/FLTE/FLTT` (D/E/T rate filters — half of the gyro filter for D), `MOT_THST_EXPO` (0.65 for 10", 0.55–0.6 for 5"), `MOT_SPIN_ARM/MIN`, `MOT_THST_HOVER` (it will learn, `MOT_HOVER_LEARN = 2`), `ATC_THR_MIX_MAN`, `PSC_D_ACC_P/I` (before 4.7 — `PSC_ACCZ_P/I`, in 4.7 the values are ×0.1) for the hover throttle, `ATC_INPUT_TC` (stick feel). For large/heavy vehicles — reduced initial PIDs (`ATC_RAT_RLL_P/I` 0.05–0.1 instead of 0.135, D 0.002–0.004).

### Steps 2–3. First flight and assessment
Stabilize/AltHold at minimum weight, full battery (“most agile configuration”). In the log: `RATE.RDes` vs `RATE.R` (requested vs actual) — tracking without oscillations; `ATT.DesRoll` vs `ATT.Roll`; `VIBE.VibeX/Y/Z` < 15–30 m/s², `Clip` = 0; `CTUN.ThO` (hover throttle, learned `MOT_THST_HOVER` 0.2–0.5). Oscillations right away → lower P/D by 30–50%, don't keep flying.

### Step 4. Harmonic notch
Motor noise gets into the D-term and heats the motors; a low-frequency LPF adds latency (the “Signals and spectra” module). A notch cuts only the motor frequencies:

1. **Find the frequency**: batch sampling (`INS_LOG_BAT_MASK = 1` — first IMU; `INS_LOG_BAT_OPT`: 0 — raw data before the filters, 2 — after the filters, 4 — before and after at 1 kHz) or, on H7 with 4.5+, raw IMU logging (`INS_RAW_LOG_OPT`); fly a hover + gentle maneuvers; spectrum in MAVExplorer/Filter Review Tool/your own Python.
2. **Enable**: `INS_HNTCH_ENABLE = 1`, reboot.
3. **Mode** (`INS_HNTCH_MODE`): 3 — ESC telemetry (the best, tracks each motor, needs ESC telemetry or BLHeli bidir DShot); 1 — throttle-based (`INS_HNTCH_REF` = hover throttle, `INS_HNTCH_FREQ` — the frequency at hover, scaled by √(throttle/ref); change REF when the payload changes); 4 — in-flight FFT (F7/H7, one filter); 0 — static.
4. **Bandwidth and depth**: `INS_HNTCH_BW` (≈ half of FREQ for throttle mode, narrower for ESC), `INS_HNTCH_ATT` (40 dB typical), `INS_HNTCH_HMNCS` (harmonics bitmask: 3 = 1st and 2nd, 7 = 1st–3rd; “three harmonics is usually safe”), `INS_HNTCH_OPTS` (bit 1 — multi-source, per motor; bit 2 — update at loop rate with bidir DShot; bit 5 — fall back to the minimum frequency on RPM loss; don't combine bits 0 and 4 (double/triple) — with both set, only double works).
5. **Verify**: a log with batch sampling after the filters (`INS_LOG_BAT_OPT = 2`), the motor peaks should drop by 20+ dB; the second set `INS_HNTC2_*` is for frame resonance (static).

### Step 5. Manual roll/pitch or QuikTune
Mandatory before AUTOTUNE: AUTOTUNE starts from the current values and aborts on noise. QuikTune (the Lua applet `VTOL-quicktune.lua`, enabled with the `QUIK_ENABLE` parameter, switch — `RCx_OPTION = 300` or `QUIK_RC_FUNC`) raises P/D until the first oscillation and backs off by `QUIK_GAIN_MARGIN` %. Manually: D until it oscillates → −30%, P until it oscillates → −30%, I = P.

### Step 6. AUTOTUNE
What it does: in AltHold/Loiter it applies a series of short “kicks” on one axis (twitches), measures the response and looks for the maximum rate D, then rate P (I = P), then angle P, aiming for the target overshoot. Parameters: `AUTOTUNE_AXES` (bitmask: 1 roll, 2 pitch, 4 yaw, 8 yaw-D; on large vehicles it's better to do one axis per flight), `AUTOTUNE_AGGR` (0.05–0.10, default 0.075 since 4.6 (0.1 in 4.5 and earlier); higher — more aggressive and more noise-tolerant, lower — more responsive), `AUTOTUNE_MIN_D` (lower limit for D — so it doesn't drop to zero on a noisy vehicle). Conditions: wind < 3 m/s, 20+ m of altitude and space, full battery, notch configured. The result is saved only when you disarm with the switch on / in AUTOTUNE mode (message “Saved gains for …”); `RCx_OPTION = 180` lets you switch between the old and new gains to compare. The `ATUN` log (overview) and `ATDE` (details of each twitch) show where it stopped; the GCS messages “Twitch”, “success 1/4” are in the log too. Sign of success: the final `ATC_RAT_*_D` are above `AUTOTUNE_MIN_D`.

### Step 7. Input shaping
`ATC_INPUT_TC` (0.15 smooth → 0.05 crisp), `ATC_ACC_R/P/Y_MAX` (°/s²; before 4.7 — `ATC_ACCEL_R/P/Y_MAX` in cdeg/s²), `ATC_RATE_R/P/Y_MAX`, `ATC_ANG_*_P` (AUTOTUNE sets them, you can soften them). This isn't stability — it's feel.

### What to check afterwards
`RATE.RDes/R` — response without overshoot > 10%; `RATE.ROut` (PID output) without saturation; `VIBE` hasn't gone up; motor temperature; the post-filter spectrum is clean; `PIDR.P/I/D` (per-axis PID logging with PID enabled in `LOG_BITMASK`) — the share of D noise.

{{diagram:ap-tuning-order|Tuning order: base parameters → harmonic notch → QuikTune or manual tuning → AUTOTUNE → input shaping, with a log after every step.}}

## practice
### Step 1. SITL
`sim_vehicle.py -v ArduCopter -f quad`: set the starting parameters for 10", AUTOTUNE roll (`AUTOTUNE_AXES = 1`) in AltHold; look at `ATUN` in the log and the final `ATC_RAT_RLL_*`. Repeat with `AUTOTUNE_AGGR = 0.05` — compare.

### Step 2. Notch in the field
Batch sampling before the filters → spectrum → hover frequency → `INS_HNTCH_*` (ESC mode if you have telemetry) → batch after the filters → before/after spectrum with numbers in dB.

### Step 3. QuikTune/manual
Roll-pitch up to the first oscillation, back off; check with the `RATE` log.

### Step 4. AUTOTUNE in the field
One axis per flight; save; a control flight with a log; compare `RATE.RDes/R` before/after.

### What you should get and what to record
- **Step 1 (SITL).** AUTOTUNE is enabled with a switch (`RCx_OPTION = 17`) in AltHold. The vehicle twitches the selected axis on its own until it's done, and the result is saved if you land and disarm with the switch in the on position. Record `ATC_RAT_RLL_P/I/D` and `ATC_ANG_RLL_P` before and after. `AUTOTUNE_AGGR` is the allowed overshoot during the search (0.05–0.10, default 0.075; in 4.5 and earlier — 0.1): with 0.05 the tune is softer and the D gains are lower. Compare the two sets of numbers and describe the difference in behavior.
- **Step 2 (notch).** The batch sampler is enabled with `INS_LOG_BAT_MASK = 1`, and the “before and after filters” mode with the `INS_LOG_BAT_OPT` options as described for the parameter in your version. The pre-filter spectrum shows the motor frequency at hover. After setting up `INS_HNTCH_*`, the peak at that frequency should drop. Record the frequency, the peak height before and after in dB, and the mode you chose (`INS_HNTCH_MODE`: throttle or ESC telemetry).
- **Step 3 (manual).** Raise P and D until the first oscillation — audible, or visible in `RATE` as `R` oscillating around `RDes` — and back off by 20–30 %. Record the value where the oscillation started and the one you chose.
- **Step 4 (field).** On the `RATE.RDes` and `RATE.R` plot after the tune, the actual follows the request without overshoot greater than 10–15 % and without oscillation. Record the maximum overshoot before and after on identical maneuvers.

The lab counts as done when AUTOTUNE on roll has been completed and the gains before and after are recorded, the notch has been set up from before/after spectra with numbers in dB, and a control flight confirms the result by `RATE.RDes/R`.

## diagnostics
- **Symptom:** AUTOTUNE aborts with “Failed to level” / won't start
  - Possible cause: wind, high vibration, a poor initial tune.
  - What to do: calm weather, notch, manual tune, AltHold stable for ≥ 1 min.
- **Symptom:** hot motors after AUTOTUNE
  - Possible cause: D is high with a noisy gyro.
  - What to do: notch/filters, `AUTOTUNE_MIN_D`, repeat.
- **Symptom:** the throttle-based notch “misses” with a payload
  - Possible cause: `INS_HNTCH_REF` was set for a different weight.
  - What to do: recalculate REF or use ESC mode.
- **Symptom:** a peak remains in the spectrum after the notch
  - Possible cause: frame resonance (not a motor) or a harmonic outside HMNCS.
  - What to do: a static `INS_HNTC2_*` on the resonance; HMNCS = 7.
- **Symptom:** mushy response despite a good tune
  - Possible cause: input shaping (`ATC_INPUT_TC` too large, ACCEL_MAX too small).
  - What to do: lower TC, raise ACCEL/RATE_MAX.

## references
- ArduPilot — Tuning Process Instructions | https://ardupilot.org/copter/docs/tuning-process-instructions.html | primary | A
- ArduPilot — Managing Gyro Noise with the Dynamic Harmonic Notch Filters | https://ardupilot.org/copter/docs/common-imu-notch-filtering.html | primary | A
- ArduPilot — AutoTune | https://ardupilot.org/copter/docs/autotune.html | primary | A

## checklist
- I know the seven tuning steps and their order
- Starting parameters are set for the vehicle size
- The notch is configured, before/after spectra captured
- AUTOTUNE done axis by axis, result verified with RATE
- I understand what AUTOTUNE does and why it fails on noise
