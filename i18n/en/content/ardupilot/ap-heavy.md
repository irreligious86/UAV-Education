---
id: ap-heavy
title: "Heavy platforms: X8 and octo"
level: L3
readingTime: 25 min
firmware: ArduPilot 4.7 (checked against 4.7.3)
status: published
added: 2026-11-07
tags:
  - X8
  - OctaQuad
  - heavy lift
related:
  - ap-lua
  - f-physics
next:
  - ap-quadplane
source: content/ardupilot/ap-heavy.md
source_hash: d97c3812a8b4
---

## summary
An eight-motor vehicle with 15–17" props is a different animal from a five-inch quad: slow motors, huge inertia, a low thrust-to-weight ratio, and mistakes that cost an expensive payload. This module covers the coaxial X8 layout using a build on two Tarot Ironman 650 frames, thrust and vibration setup in ArduPilot, and verifying fault tolerance before the first flight with a payload.

## theory
### X8 (OctaQuad): pros and cons
An X8 has four arms with two coaxial motors on each: a top one and a bottom one that spin in opposite directions.

- **Pros:** eight motors in the footprint of a quadcopter; one motor failure does not bring the vehicle down; compact for transport.
- **Cons:** the bottom prop works in the wash of the top one, so a coaxial pair produces less thrust than two separate props. The guideline loss is about 15% (it depends on the props and the spacing between them).

In ArduPilot this is `FRAME_CLASS = 4` (OctaQuad) and `FRAME_TYPE = 1` (X). The motor order and directions must follow the OctaQuad X diagram in the documentation exactly.

### Example build
The course's training platform: two Tarot Ironman 650 frames, 8 Tarot 4008 380KV motors, 8 Flycolor 45A ESCs, a 6S Li-Ion pack. Low KV and large props are a bet on efficiency and flight time, not on agility. Li-Ion was chosen because the hover current is moderate.

### Thrust and the throttle curve
- `MOT_THST_HOVER` is the hover throttle; ArduPilot refines it in flight by itself. Altitude hold depends on it.
- `MOT_THST_EXPO` linearizes thrust. Large props usually need a higher value than five-inch props.
- `MOT_SPIN_ARM` and `MOT_SPIN_MIN` set the spin when armed and the minimum in flight: the motors must spin reliably but not lift the vehicle.
- The motor protocol, `MOT_PWM_TYPE`: DShot if the ESCs support it, otherwise PWM with an ESC calibration.

For starting values Mission Planner has the Initial Tune Parameter helper: it calculates the basic filters and limits from the prop size and the battery voltage.

### Vibration
Large, slow props produce low-frequency vibration that is harder to filter. With vibration the EKF starts to drift: in logs you see it as rising `VIBE` and accelerometer clipping, in flight as altitude loss or IMU failure messages. Fix it in this order of priority: prop and motor balancing, frame stiffness, flight controller damping, and only then filters. The harmonic notch filter (`INS_HNTCH_*`) tracks RPM through throttle or ESC telemetry and is the counterpart of Betaflight's RPM filter.

### Fault tolerance
The main reason to pick an octo is to survive a motor failure. That has to be tested, not assumed: in SITL with the motor failure applet (see the Lua module), then on the real vehicle at altitude with no payload.

### Numbers for the course platform (X8, 2×Tarot 650, 4008/4006-class 380KV motors calculated from the MN4006 table, 15×5, 6S Li-Ion, ~6 kg)
From the "Propeller aerodynamics" module: hover ≈ 880 g of thrust per motor including the coaxial loss, ~3.6–3.9 A per motor, ~30 A for the pack; a 6S 20 Ah Li-Ion → ~32 min of hover; `MOT_THST_HOVER` ≈ 0.35–0.4, which is a fraction of maximum thrust and not the % throttle on the thrust stand (52% in the table): 880 g out of a ~2230 g maximum at 24 V ≈ 0.39, and with voltage compensation the maximum is taken at `MOT_BAT_VOLT_MAX` (25.2 V, ~2450 g) → ≈ 0.36; `MOT_HOVER_LEARN` will learn the exact value; `MOT_THST_EXPO` 0.65–0.7 (15"); `INS_GYRO_FILTER` ≈ 30 Hz (between 40 Hz for 10" and 20 Hz for 20"); `ATC_RAT_*_FLTD` 15 (half the gyro filter, as in ap-tuning); starting `ATC_RAT_RLL_P/I` 0.08, D 0.003, `ATC_ANG_RLL_P` 4.5; `ATC_ACC_R/P_MAX` ≈ 500–700 deg/s² (before 4.7 this was `ATC_ACCEL_R/P_MAX` in cdeg/s², 50 000–70 000; slower than a 5"); `PSC_D_ACC_P` ≈ 0.1 × hover throttle (≈ 0.036; before 4.7 `PSC_ACCZ_P` ≈ hover throttle, 0.36: the parameter's scaling in 4.7 is 10 times smaller). Arm wiring is 12 AWG with XT90 connectors (see the "Redundancy" module). The fundamental motor frequency in hover is ~60–70 Hz (per the MN4006 table, 880 g ≈ 3900 RPM ≈ 65 Hz): use `INS_HNTCH_*` with ESC telemetry, `INS_HNTCH_HMNCS = 7` (harmonics 1–3 up to 200 Hz), and an `INS_HNTCH_FREQ` minimum of 50.

### Motor failure: what the mixer does
`AP_MotorsMatrix::output_armed_stabilizing()` allocates roll and pitch first, then yaw (which is given at least `MOT_YAW_HEADROOM`), and throttle gets what is left after the `MOT_YAW_HEADROOM` reserve (200 by default, in PWM units reserved for yaw). When one motor of an X8 fails, its coaxial partner and the opposite pair take the load; you see a slight sag and higher `RCOU` on the neighboring channels. The test: the `motor_failure_test.lua` applet (`MOT_STOP_BITMASK`, a Scripting1 switch), first in SITL (`-f octa-quad`), then in the field at 20+ m with no payload and a spotter.

### Operating a large vehicle
The pre-arm routine gets longer: 8 props (tightness, cracks), 8 ESCs (heat after the previous flight), Li-Ion cell-group balance, a GPS fix with 14+ satellites, the geofence, a 30 m radius area with no people, a buzzer, and a carrying strap. Any change in mass (payload, battery) → `MOT_THST_HOVER` changes (it relearns) and `PSC_D_ACC_*` needs a check (before 4.7, `PSC_ACCZ_*`). Log every flight; `VIBE` < 15 is the working goal on large props, and > 30 (the general limit in the documentation, see ap-logs) means go and find the cause.

### The compass on a large vehicle
You cannot calibrate a 6 kg X8 by rotating it in every direction, and 30 A for the pack next to the flight controller makes the internal compass useless. The procedure for a vehicle like this (details and formulas are in `ap-sensors`):

1. **Mast and orientation.** The compass sits in the GPS module on a mast, as far from the power wiring as possible. You set its orientation by hand before any calibration: `COMPASS_ORIENT` (the rotation of the external compass relative to the frame); `COMPASS_AUTO_ROT = 2` checks it only on completion of a rotation calibration, which you do not do here.
2. **Priorities.** Put the mast compass in slot 1: `COMPASS_PRIO1_ID` = its ID from the GCS compass list, then reboot. Disable the internal one with `COMPASS_USEn = 0` for **its slot**; find the slot number from `COMPASS_PRIOn_ID`, do not assume "2 = internal". Otherwise you get `PreArm: Compasses inconsistent` or a heading that wanders at full throttle.
3. **Large Vehicle MagCal.** The vehicle is on a level area away from metal, motors off, the nose on a known **true** heading; `COMPASS_SCALE = 0`; send the `MAV_CMD_FIXED_MAG_CAL_YAW` command (Large Vehicle MagCal in Mission Planner). It writes the offsets (`OFS`), resets `DIA` to 1 and `ODI` to 0, and does not check the orientation, so with a wrong orientation it writes garbage without an error.
4. **First flight for a log** in AltHold: several full 360° turns, a few minutes.
5. **MagFit** on that log (WebTools or MAVExplorer): offsets, then `DIA`/`ODI` and current-based `COMPASS_MOT_*` if a residual remains. Accept it if the residual heading deviation is < 10°; if the fitted heading differs from the EKF heading by more than 20°, the orientation or the GPS is wrong, so do not write the parameters.

Verification: in hover with a full payload the magnitude of the `MAG` field changes with current by less than 5–10%, there is no toilet bowling in Loiter, and `XKF4.SM` (the compass variance) stays below the `FS_EKF_THRESH` threshold (0.8).

{{diagram:x8-layout|X8: four arms with coaxial pairs; when a motor fails, its coaxial partner and the opposite pair take the load, and the throttle margin in hover is the margin for a failure.}}

### Place in the system

- **Receives:** thrust and current per motor from the thrust table (`f-aero-props`), which give the `MOT_THST_HOVER` estimate; wire gauges and arm connectors (`el-redundancy`); the order for setting up filters and the notch (`ap-tuning`).
- **Provides:** the hover throttle and `MOT_THST_EXPO` to altitude hold; the fundamental motor frequency to `INS_HNTCH_*` (`ap-tuning`); the motor failure scenario to the `motor_failure_test.lua` applet (`ap-lua`) and to SITL (`ap-sitl`).
- **If you get it wrong here:** unbalanced large props → low-frequency vibration → rising `VIBE` and clipping → the EKF drifts and the vehicle loses altitude (`ap-logs`, `ap-ekf`). An overloaded vehicle → higher hover throttle → no margin left for a motor failure; you check that with the failure test before flying with a payload (`ap-lua`).

## practice
### Step 1. SITL first
```
sim_vehicle.py -v ArduCopter -f octa-quad --console --map
```

Practice takeoff, LOITER, RTL, and a motor failure before you touch the hardware.

### Step 2. Configuring the real frame
1. `FRAME_CLASS = 4`, `FRAME_TYPE = 1`, reboot.
2. With the props off, run Motor Test on every motor: order and direction per the OctaQuad X diagram.
3. Calibrate the ESCs (for PWM) or select DShot.
4. Run Initial Tune Parameter with the prop size and the cell count.
5. Check: all props are the same model, with the correct direction and tightness.

### Step 3. First flights
1. Hover low in STABILIZE, then ALT_HOLD, with logging.
2. Analyze the log: `VIBE` (vibration and clipping), the actual hover throttle, current and battery sag.
3. Only then AutoTune, one axis at a time, in calm weather.
4. The motor failure test: at altitude, with no payload, ready to take over control.

### What you should get and what to record
- **SITL.** The `octa-quad` frame in SITL is the same OctaQuad: eight motors, four coaxial pairs. An octo survives one motor failure (`SIM_ENGINE_FAIL` is the motor mask, `SIM_ENGINE_MUL = 0`): the vehicle rolls, the remaining motors make up the thrust, and the position holds. Record the maximum roll and the `RCOU` motor outputs before and after the failure.
- **Motor Test.** The motors are lettered A, B, C… clockwise starting from the front right. Each letter is a specific motor on the OctaQuad X diagram, and the direction is as shown on the diagram. The "letter → motor → direction → OK" table goes into the vehicle's records.
- **T/W with the coaxial correction.** The thrust of a pair is not twice the thrust of one motor: the guideline loss is about 15%. Example: 8 motors with 3000 g of maximum thrust each give 24 kg on paper and ≈ 20.4 kg with the correction; at a takeoff mass of 9 kg, T/W ≈ 2.3. Without the correction you overestimate the margin.
- **First log.** Vibration (median below 30 m/s², clipping 0), hover throttle (the learned `MOT_THST_HOVER` for this build is calculated as ≈ 0.35–0.4; above 0.5 the thrust margin is small), battery sag at hover throttle. Compare the hover current with the calculation from the theory (~3.6–3.9 A per motor for the module's example).

Self-check: the lab is done when a motor failure has been run in SITL on the `octa-quad` frame with the vehicle holding position and the maximum roll and `RCOU` before and after recorded, Motor Test with the props off matched the OctaQuad X diagram for every letter (the "letter → motor → direction → OK" table has no empty rows), T/W is calculated with the coaxial correction of about 15% and your formula gives the same ≈ 20.4 kg and T/W ≈ 2.3 for the module's example (8 motors at 3000 g, 9 kg), and in the first log the `VIBE` median is below 30 m/s², clipping is 0, the hover throttle is below 0.5, and the hover current is compared with the calculation from the theory.

**Reference for the self-check.** A correct result: an octo survives one motor failure with a roll, then the remaining motors make up the thrust and the position holds. Typical wrong results: (1) T/W for the module's example came out ≈ 2.7 because the coaxial correction was forgotten (24 kg instead of 20.4), so the margin is overestimated; (2) hover throttle above 0.5 means the thrust margin is small and the T/W calculation is worth rechecking.

## diagnostics
- **Symptom:** the vehicle loses altitude in ALT_HOLD for no apparent reason
  - Possible cause: vibration; the EKF stops trusting the accelerometer.
  - What to do: look at `VIBE` and clipping in the log, balance the props and motors.
- **Symptom:** a constant yaw rotation in hover
  - Possible cause: a tilted motor or different props in the coaxial pairs.
  - What to do: check motor alignment and that the props are the same model and pitch.
- **Symptom:** hover throttle (`MOT_THST_HOVER`, `CTUN.ThO`) above 0.5
  - Possible cause: overloaded once the coaxial loss is counted: this is a fraction of thrust, and 0.5 is T/W 2 (`f-physics`, "Hover throttle"; the same limit is used in `des-sizing`).
  - What to do: recalculate T/W with the coaxial correction, reduce weight.
- **Symptom:** after a motor failure the vehicle spins and loses control
  - Possible cause: not enough thrust margin or the wrong motor order.
  - What to do: repeat the test in SITL, check Motor Test and the thrust margin.

## references
- Connect ESCs and Motors — ArduPilot Copter | https://ardupilot.org/copter/docs/connect-escs-and-motors.html | primary | A
- Frame Class and Type Configuration — ArduPilot Copter | https://ardupilot.org/copter/docs/frame-type-configuration.html | primary | A
- Motor failure test applet — ArduPilot (GitHub) | https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_Scripting/applets/motor_failure_test.md | primary | A

## checklist
- `FRAME_CLASS`/`FRAME_TYPE` match the frame, Motor Test passed with the props off
- T/W is calculated with the coaxial correction
- Initial Tune Parameter has been applied
- The first log is checked for vibration and hover throttle
- A motor failure is tested in SITL before the real test
