---
id: ap-tuning
title: "Tuning ArduPilot: AutoTune, filters, ESC-driven notch"
level: L3
readingTime: 40 min
firmware: ArduPilot 4.7 (checked against 4.7.3)
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
source_hash: d7f4eb0a386a
---

## summary
Tuning ArduCopter does not mean "run AutoTune". It means seven steps in the right order: parameters for the size of the vehicle → first stable flight → evaluation → harmonic notch on the motor noise → manual or QuikTune roll/pitch tune → AutoTune axis by axis → input shaping for feel. This module walks through them with the parameters and a log check for each (`ATT`, `RATE`, `VIBE`, spectra from batch sampling or raw IMU logging), explains what AutoTune does internally (and why it needs the noise to be below a threshold), and shows how to set up a notch that tracks ESC telemetry or throttle. The lab runs in SITL and in the field.

## theory
### Step 1. Parameters before the first flight
The starting values depend on the prop size (the "Setting the Aircraft Up for Tuning" page): `INS_GYRO_FILTER` (80 Hz for 5", 40 for 10", 20 for 20" and larger), `ATC_RAT_*_FLTD/FLTE/FLTT` (the D, error and target filters of the rate controllers; for D use half the gyro filter), `MOT_THST_EXPO` (0.65 for 10", 0.55 for 5"), `MOT_SPIN_ARM/MIN`, `MOT_THST_HOVER` (it is learned with `MOT_HOVER_LEARN = 2`), `ATC_THR_MIX_MAN`, `PSC_D_ACC_P/I` (before 4.7 these were `PSC_ACCZ_P/I`; the scaling in 4.7 is 10 times smaller: 0.1 and 0.2 of the hover throttle instead of 1 and 2) matched to the hover throttle, `ATC_INPUT_TC` (stick feel). For large or heavy vehicles start with reduced PID gains (`ATC_RAT_RLL_P/I` 0.05–0.1 instead of 0.135, D 0.002–0.004).

### Steps 2–3. First flight and evaluation
Fly Stabilize or AltHold at minimum weight with a full battery (the "most agile configuration"). In the log: `RATE.RDes` vs `RATE.R` (desired vs achieved rate) should track without oscillation; compare `ATT.DesRoll` with `ATT.Roll`; `VIBE.VibeX/Y/Z` < 15–30 m/s² (30 is the general limit in the documentation, 15 is the goal for large props), `Clip` = 0; `CTUN.ThO` (hover throttle; a learned `MOT_THST_HOVER` of 0.2–0.5). If it oscillates right away, cut P and D by 30–50% and do not fly on.

### Step 4. Harmonic notch
Motor noise gets into the D term and heats the motors; a low-pass filter with a low cutoff adds delay (see the "Signals and spectra" module). A notch removes only the motor frequencies:

1. **Find the frequency**: batch sampling (`INS_LOG_BAT_MASK = 1` selects the first IMU; `INS_LOG_BAT_OPT`: 0 logs raw pre-filter data, 2 samples post-filtering, 4 samples pre- and post-filter at 1 kHz) or, on an H7 with 4.5+, raw IMU logging (`INS_RAW_LOG_OPT`); fly a hover with gentle maneuvers; view the spectrum in MAVExplorer, the Filter Review Tool, or your own Python.
2. **Enable it**: `INS_HNTCH_ENABLE = 1`, then reboot.
3. **Mode** (`INS_HNTCH_MODE`): 3 is ESC Telemetry (the best one: it tracks every motor and needs ESC telemetry or BLHeli bidirectional DShot); 1 is Throttle (`INS_HNTCH_REF` = hover throttle, `INS_HNTCH_FREQ` is the frequency in hover, and the center frequency is rescaled by √(throttle/ref); change REF when the payload changes); 4 is Dynamic FFT in flight (F7/H7; only one of `INS_HNTCH` and `INS_HNTC2` may use mode 4); 0 is Fixed.
4. **Bandwidth and depth**: `INS_HNTCH_BW` (about half of FREQ, in throttle mode and with ESC telemetry alike; much narrower, ≈ FREQ / number of motors, with Multi-Source), `INS_HNTCH_ATT` (40 dB is typical), `INS_HNTCH_HMNCS` (harmonics bitmask: 3 = 1st and 2nd, 7 = 1–3; "three harmonics are usually safe"), `INS_HNTCH_OPTS` (bit 1 is Multi-Source, one notch per motor; bit 2 updates at loop rate with bidirectional DShot; bit 5 uses the minimum frequency on RPM source failure; do not combine bits 0 and 4 (double and triple notch), because with both set only the double notch is applied).
5. **Verify**: take a log with post-filter batch sampling (`INS_LOG_BAT_OPT = 2`); the motor peaks should drop by 20+ dB; the second set, `INS_HNTC2_*`, is for a frame resonance (fixed frequency).

### Step 5. Manual roll/pitch tune or QuikTune
This is mandatory before AutoTune: AutoTune starts from the current gains and aborts when the signal is noisy. QuikTune (the Lua applet `VTOL-quicktune.lua`, enabled with `QUIK_ENABLE`, with the switch set by `RCx_OPTION = 300` or `QUIK_RC_FUNC`) raises P and D until the first oscillation and backs them off by `QUIK_GAIN_MARGIN` %. By hand: raise D until it oscillates → −30%, raise P until it oscillates → −30%, I = P on roll and pitch.

### Step 6. AutoTune
What it does: in AltHold or Loiter it commands a series of short twitches on one axis, measures the response, and looks for the highest rate D, then rate P (I = P on roll and pitch, I = 0.1·P on yaw), then angle P that still give the target overshoot. Parameters: `AUTOTUNE_AXES` (bitmask: 1 roll, 2 pitch, 4 yaw, 8 yaw D; on large vehicles tune one axis per flight), `AUTOTUNE_AGGR` (0.05–0.10, default 0.075 since 4.6 (0.1 in 4.5 and earlier); higher is more aggressive and more tolerant of noise, lower gives a softer tune), `AUTOTUNE_MIN_D` (the lower bound for D, so it does not go to zero on a noisy vehicle), `AUTOTUNE_GMBK` (new in 4.7, default 0.25: the tuned P and D gains are reduced by this fraction for extra stability margin, so the result on 4.7 is softer than on 4.6; 0 applies no reduction). Conditions: wind < 3 m/s, 20+ m of altitude and clear space, a full battery, the notch already set up. The result is saved only if you disarm with the switch on or in AUTOTUNE mode (the message is "AutoTune: Saved gains for …"); `RCx_OPTION = 180` lets you switch between the original and the tuned gains to compare them. The `ATUN` (summary) and `ATDE` (detail of every twitch) log messages show where it stopped; the GCS progress messages, such as "AutoTune: Roll Rate D Up 25%", are in the log too. A sign of success: the final `ATC_RAT_*_D` values are above `AUTOTUNE_MIN_D` × (1 − `AUTOTUNE_GMBK`) (0.000375 by default), because the saved D is already reduced by GMBK.

### Step 7. Input shaping
`ATC_INPUT_TC` (0.15 is smooth → 0.05 is sharp; the Copter 4.7 default is 0.10, in 4.6 it was 0.15), `ATC_ACC_R/P/Y_MAX` (deg/s²; before 4.7 these were `ATC_ACCEL_R/P/Y_MAX` in cdeg/s²), `ATC_RATE_R/P/Y_MAX`, `ATC_ANG_*_P` (AutoTune sets them; you can soften them). None of this is about stability. It is about feel.

### What to look at afterwards
`RATE.RDes/R`: a response with no more than 10% overshoot; `RATE.ROut` (the PID output) without saturation; `VIBE` has not grown; motor temperature; a clean post-filter spectrum; `PIDR.P/I/D` (per-axis PID logging when PID is set in `LOG_BITMASK`) for the share of D-term noise.

{{diagram:ap-tuning-order|Tuning order: basic parameters → harmonic notch → QuikTune or manual tune → AutoTune → input shaping, with a log after every step.}}

### Place in the system

- **Receives:** the noise spectrum from batch sampling (`ctl-signals`, `data-python`); RPM from ESC telemetry or bidirectional DShot for the notch (`f-motors-esc`); the learned `MOT_THST_HOVER` and the first log (`ap-setup-scratch`).
- **Provides:** `ATC_RAT_*` and `ATC_ANG_*` to the rate and angle loops that the position modes run on top of; the harmonic notch to heavy vehicles (`ap-heavy`); QuikTune and AutoTune to the VTOL side of a QuadPlane (`ap-quadplane`).
- **If you get it wrong here:** you lowered the low-pass filter instead of adding a notch → the delay ate the phase margin → oscillation at the same P (`ctl-theory`). You ran AutoTune without a notch → noise in the D term → an aborted tune or D stuck at `AUTOTUNE_MIN_D` × (1 − `AUTOTUNE_GMBK`), hot motors; you can see it in `ATUN` and `PIDR` (`ap-logs`).

## practice
### Step 1. SITL
`sim_vehicle.py -v ArduCopter -f quad`: set the starting parameters for 10" props, run AutoTune on roll (`AUTOTUNE_AXES = 1`) in AltHold; look at `ATUN` in the log and at the final `ATC_RAT_RLL_*`. Repeat with `AUTOTUNE_AGGR = 0.05` and compare.

### Step 2. Notch in the field
Pre-filter batch sampling → spectrum → frequency in hover → `INS_HNTCH_*` (ESC telemetry mode if you have telemetry) → post-filter batch sampling → before/after spectra with numbers in dB.

### Step 3. QuikTune or manual
Roll and pitch up to the first oscillation, then back off; check with the `RATE` log.

### Step 4. AutoTune in the field
One axis per flight; save; a check flight with a log; compare `RATE.RDes/R` before and after.

### What you should get and what to record
- **Step 1 (SITL).** AutoTune is switched on with an RC switch (`RCx_OPTION = 17`) in AltHold. The vehicle twitches the selected axis by itself until it finishes, and the result is saved if you land and disarm with the switch in the on position. Record `ATC_RAT_RLL_P/I/D` and `ATC_ANG_RLL_P` before and after. `AUTOTUNE_AGGR` is the bounce back accepted during the search (0.05–0.10, default 0.075; 0.1 in 4.5 and earlier): with 0.05 the tune is softer and the D gains are lower. Compare the two pairs of numbers and describe the difference in behavior.
- **Step 2 (notch).** The batch sampler is enabled with `INS_LOG_BAT_MASK = 1`, and pre- and post-filter sampling is selected with the `INS_LOG_BAT_OPT` options as described for your version. The pre-filter spectrum shows the motor frequency in hover. After you set `INS_HNTCH_*`, the peak at that frequency should drop. Record the frequency, the peak height before and after in dB, and the mode you chose (`INS_HNTCH_MODE`: throttle or ESC telemetry).
- **Step 3 (manual).** Raise P and D until the first oscillation, audible or visible in `RATE` as `R` swinging around `RDes`, then back off by 20–30%. Record the value where the oscillation started and the value you chose.
- **Step 4 (field).** On the plot of `RATE.RDes` and `RATE.R` after the tune, the achieved rate follows the desired rate with no more than 10–15% overshoot and no oscillation. Record the maximum overshoot before and after on identical maneuvers.

Self-check: the lab is done when AutoTune on roll has run twice in SITL, with the default `AUTOTUNE_AGGR` and with 0.05, `ATC_RAT_RLL_P/I/D` and `ATC_ANG_RLL_P` are recorded before and after and the D gain came out lower with 0.05, the notch is set up from before/after spectra with the hover motor frequency, the peak height in dB before and after and `INS_HNTCH_MODE` recorded and the peak lower afterwards, the manual tune has the value where the oscillation started and the chosen value 20–30% below it recorded, and in the check flight `RATE.R` follows `RATE.RDes` with no oscillation and no more than 10–15% overshoot, with the maximum overshoot before and after recorded on identical maneuvers.

**Reference for the self-check.** A correct result: after every step you have a "before and after" pair of numbers, and "after" is better. Typical wrong results: (1) the gains did not change after AutoTune, because the result is saved only if you land and disarm with the switch in the on position; (2) the peak is still in the spectrum after the notch, because it is a frame resonance and not a motor, or a harmonic outside `INS_HNTCH_HMNCS`; (3) AutoTune does not start or aborts because of wind, high vibration, or a poor initial tune.

## diagnostics
- **Symptom:** AutoTune aborts with "AutoTune: Failed to level, please tune manually" or does not start
  - Possible cause: wind, high vibration, a poor initial tune.
  - What to do: calm air, a notch, a manual tune, AltHold stable for ≥ 1 min.
- **Symptom:** hot motors after AutoTune
  - Possible cause: high D with a noisy gyro.
  - What to do: notch and filters, `AUTOTUNE_MIN_D`, then repeat.
- **Symptom:** the throttle-based notch misses with a payload
  - Possible cause: `INS_HNTCH_REF` was set for a different weight.
  - What to do: recalculate REF or use ESC telemetry mode.
- **Symptom:** a peak is still in the spectrum after the notch
  - Possible cause: a frame resonance (not a motor) or a harmonic outside HMNCS.
  - What to do: a fixed `INS_HNTC2_*` notch on the resonance; HMNCS = 7.
- **Symptom:** a mushy response with a good tune
  - Possible cause: input shaping (`ATC_INPUT_TC` is high, `ATC_ACC_*_MAX` is low).
  - What to do: reduce TC, raise ACC and RATE_MAX.

## references
- ArduPilot — Tuning Process Instructions | https://ardupilot.org/copter/docs/tuning-process-instructions.html | primary | A
- ArduPilot — Managing Gyro Noise with the Dynamic Harmonic Notch Filters | https://ardupilot.org/copter/docs/common-imu-notch-filtering.html | primary | A
- ArduPilot — AutoTune | https://ardupilot.org/copter/docs/autotune.html | primary | A

## checklist
- I know the seven tuning steps and their order
- The starting parameters are set for the size of the vehicle
- The notch is set up and the before/after spectra are taken
- AutoTune has been run on an axis and the result checked in RATE
- I understand what AutoTune does and why it fails when the signal is noisy
