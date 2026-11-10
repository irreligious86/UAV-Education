---
id: ap-intro
title: "Introduction to ArduPilot"
level: L2
readingTime: 20 min
firmware: ArduPilot 4.5+
status: published
added: 2026-11-07
tags:
  - ArduPilot
  - parameters
  - modes
related:
  - ap-sitl
  - bf-intro
next:
  - ap-sitl
source: content/ardupilot/ap-intro.md
source_hash: ec30b4a1bf2d
---

## summary
ArduPilot is an autopilot, not just a stabilizer. If Betaflight makes a quadcopter obedient under the sticks, ArduPilot knows where it is, where it is going and what to do without a pilot. This module explains how thinking in ArduPilot differs from Betaflight: parameters instead of CLI diffs, flight modes as levels of autonomy, the ground control station, pre-arm checks and hardware requirements. After it, the whole “Autonomy” track opens up.

## theory
### Versions and parameter names
The course is written for ArduPilot 4.5 and newer. In Copter 4.7 (stable since July 2026) some parameters were renamed and moved to SI units: `ARMING_SKIPCHK` → `ARMING_SKIPCHK` (the meaning is inverted: a list of checks to **skip**, 0 — all enabled), `WPNAV_*` → `WP_*` (m, m/s), `RTL_ALT` → `RTL_ALT_M` (m), `ATC_ACCEL_*_MAX` → `ATC_ACC_*_MAX` (°/s²), `PSC_ACCZ_*` → `PSC_D_ACC_*`. In Plane since 4.5 `ARSPD_FBW_MIN/MAX` → `AIRSPEED_MIN/MAX`. The modules give the new name with the old one in parentheses; when you update the firmware, old values are converted automatically, but you have to fix your own scripts and parameter files by hand.

### One codebase — many vehicles
ArduPilot is shared code with separate firmware per vehicle type: Copter (multirotors and helicopters), Plane (planes, wings and QuadPlane VTOL), Rover, Sub. The frame type within a firmware is set with parameters: for Copter that is `FRAME_CLASS` (1 — Quad, 2 — Hexa, 3 — Octa, 4 — OctaQuad, 7 — Tri…) and `FRAME_TYPE` (0 — Plus, 1 — X, 2 — V, 3 — H…).

{{diagram:ardupilot-fast-loop|How the ArduCopter loop works: sensors → EKF → mode controllers → rate controller → motors.}}

### Parameters
All configuration is parameters (there are more than a thousand of them). The key difference from Betaflight: a parameter change is written immediately, there is no `save` command. Some parameters require a reboot (frame type, protocols, enabling subsystems). The workflow:

1. Save the full parameter list to a file (`.param`) before making changes.
2. Change one logical block at a time.
3. Compare the parameter files before and after — like `diff all` in Betaflight.

### Flight modes
Modes are levels of autonomy. For Copter:

- **STABILIZE** — self-leveling, manual throttle. The basic mode, works without GPS.
- **ALT_HOLD** — plus altitude hold from the barometer.
- **LOITER** — plus position hold, needs GPS.
- **AUTO** — mission execution.
- **GUIDED** — commands from the ground control station or a script (the basis for companion computers).
- **RTL** and **LAND** — return to home and landing.

The rule: you choose the mode by which sensors you trust. No GPS — no LOITER, RTL or AUTO.

### Ground control station and MAVLink
You set up ArduPilot through a ground control station (GCS): Mission Planner, QGroundControl or the console-based MAVProxy. They all talk to the flight controller over MAVLink — the same protocol your companion computer will use later.

### Pre-arm checks
ArduPilot will not arm while something is wrong: the accelerometer or compass is not calibrated, there is no link, the EKF is bad, parameters are wrong. A `PreArm: ...` message in the GCS is a hint, not a nuisance. Disabling checks so that it “just flies” is the classic road to a crash.

### Hardware requirements
ArduPilot is noticeably heavier than Betaflight. On F4 controllers some features are not available: for example, Lua scripts need at least 2 MB of flash and do not work on F4. For complex platforms people use H7.

### What changes for a Betaflight pilot
- Parameter files, not diffs.
- Not “flash it and fly”, but calibrations (accelerometer, compass, radio, ESC) and pre-arm.
- DataFlash logs (`.bin`) are recorded almost always and contain everything: from vibration to EKF decisions.
- Tuning more often starts with AUTOTUNE rather than manual PID.

### Copter modes by number (`FLTMODE1..6`, values from `Parameters.cpp`)
0 Stabilize, 1 Acro, 2 AltHold, 3 Auto, 4 Guided, 5 Loiter, 6 RTL, 7 Circle, 9 Land, 11 Drift, 13 Sport, 14 Flip, 15 AutoTune, 16 PosHold, 17 Brake, 18 Throw, 20 Guided_NoGPS, 21 Smart_RTL, 22 FlowHold, 23 Follow, 24 ZigZag, 25 SystemID, 27 Auto RTL, 28 Turtle. Six positions of the `FLTMODE_CH` channel (PWM boundaries 1230/1360/1490/1620/1749) + any modes on `RCx_OPTION`. Groups by sensor requirements: without position — Stabilize, Acro, AltHold (baro), Land (partially), FlowHold (flow); with position — Loiter, PosHold, Auto, Guided, RTL, Smart_RTL, Circle, Follow, ZigZag, Brake. The first flight of any build is Stabilize → AltHold → Loiter, in that order.

### First setup order (Mission Planner / QGC)
1. Firmware for the board type (`hwdef`), choosing the frame class/type (`FRAME_CLASS`, `FRAME_TYPE`).
2. Calibrations: accelerometer (6 positions), level, compass (in the field), radio (`RC1..4_MIN/MAX/TRIM`), ESC (`MOT_PWM_TYPE` DShot — no calibration needed), voltage/current sensor (`BATT_MONITOR`, `BATT_VOLT_MULT`, `BATT_AMP_PERVLT` against a wattmeter).
3. Modes on switches, `RCx_OPTION` (ARM/DISARM, Motor E-Stop, EKF source set…).
4. Failsafe (the “Fault Tolerance” module), geofence, `RTL_ALT_M`.
5. Starting tuning parameters by prop size (the “ArduPilot Tuning” module): `INS_GYRO_FILTER`, `ATC_RAT_*_FLT*`, `MOT_THST_EXPO`, `ATC_INPUT_TC`, `PSC_D_ACC_*` (before 4.7 — `PSC_ACCZ_*`).
6. Logs (`LOG_BITMASK`), `LOG_DISARMED` for ground measurements.
7. Motor test (Mission Planner → Optional Hardware → Motor Test) with props off: order and direction per the frame type diagram.

### Worked example: moving a pilot over from Betaflight
“Why won't it arm?” — `ARMING_SKIPCHK` reports the reason as text (compass, GPS, INS, parameters, RC not calibrated); “why doesn't it hold altitude in Stabilize?” — because Stabilize = Betaflight Angle, altitude is held by AltHold; “where are the rates?” — `ACRO_RP_RATE`/`ACRO_Y_RATE`, `ACRO_RP_EXPO`; “where is the PID?” — `ATC_RAT_RLL_P/I/D/FF/FLTD/FLTE/FLTT` (rate) and `ATC_ANG_RLL_P` (angle); “where are the filters?” — `INS_GYRO_FILTER`, `INS_HNTCH_*`; “where is Blackbox?” — DataFlash on the SD card, Log Review; “where is diff all?” — Full Parameter List → Save/Compare, or `param save` in MAVProxy.

## practice
### A first look with no risk
1. Do the SITL module: everything below can be done in the simulator.
2. Open the full parameter list in the GCS and find `FRAME_CLASS`, `FRAME_TYPE`, `ARMING_SKIPCHK`, `FS_THR_ENABLE`.
3. Save the parameters to a file with the date in its name.
4. Switch modes STABILIZE → ALT_HOLD → LOITER in SITL and see which ones need GPS.

### Check before the first real flight
1. Frame type and motor order verified with props off (Motor Test).
2. Calibrations done: accelerometer, compass (if present), radio, ESC.
3. Radio and battery failsafes set up.
4. No `PreArm` messages.
5. The first flight is in STABILIZE, low, then ALT_HOLD.

**Automatic check of the first hover:** `examples/sitl-pymavlink/check_lab_log.py <log.bin> --lab hover` — vibration p95 < 30, no clipping, hover throttle 0.2–0.6, attitude tracking p99 < 10°, battery sag < 15%.

### What you should end up with and what to record
- **Parameters.** `FRAME_CLASS = 1` (Quad), `FRAME_TYPE = 1` (X) — that is the default frame in SITL. `FS_THR_ENABLE` — the action on loss of radio signal (default 1 — RTL). Pre-arm checks in Copter 4.7 are set by `ARMING_SKIPCHK` (in earlier versions — `ARMING_CHECK` with the inverted meaning). For each parameter, write down its value and one sentence on what it does.
- **Parameter file:** `2026-11-09_sitl-quad.param`. Save it before any changes — it is your rollback point.
- **Modes.** STABILIZE works right away: the stick sets the angle, throttle is yours. ALT_HOLD holds altitude from the barometer, but horizontally the vehicle drifts. LOITER holds a point and needs a position estimate (GPS and a converged EKF). If you switch to LOITER before GPS has a fix, the mode will not engage and the GCS will show a refusal. Write down which message came in — this checks that you understand how modes depend on sensors.
- **Automatic hover check.** The script prints the passed and failed items. Run it on a SITL log (everything should pass) and save the output next to the log.

The lab counts as done when the parameters are saved to a dated file, `FRAME_CLASS` and `FRAME_TYPE` are found and explained, and the STABILIZE → ALT_HOLD → LOITER sequence is done with a record of what each mode holds and why LOITER depends on GPS.

## diagnostics
- **Symptom:** `PreArm: ...` and the drone won't arm
  - Possible cause: an unfinished calibration or a wrong parameter; the message text names the subsystem.
  - What to do: read the whole message, fix the cause rather than disabling the checks (`ARMING_SKIPCHK` in 4.7+, `ARMING_SKIPCHK` in 4.6 and earlier).
- **Symptom:** nothing changed after changing a parameter
  - Possible cause: the parameter requires a reboot.
  - What to do: reboot the flight controller and re-read the value.
- **Symptom:** LOITER/RTL are unavailable
  - Possible cause: no GPS fix or the EKF is not ready.
  - What to do: wait for a 3D fix, check the EKF status in the GCS.
- **Symptom:** Lua scripts don't start on the flight controller
  - Possible cause: an F4 board or not enough memory.
  - What to do: check the processor series; scripts need F7/H7.
- **Symptom:** “PreArm: Compass not calibrated / inconsistent”
  - Possible cause: calibration not done, or the internal and external compasses disagree (interference).
  - What to do: calibrate in the field, disable the internal one (`COMPASS_USE2 = 0`) when there is an external one on a mast.
- **Symptom:** “PreArm: Check fence” / “Need 3D Fix”
  - Possible cause: the geofence is enabled, GPS has no fix.
  - What to do: wait for a fix (`GPS_HDOP_GOOD`), or temporarily fly without the geofence, only in modes that do not need position.

## references
- Frame Class and Type Configuration — ArduPilot Copter | https://ardupilot.org/copter/docs/frame-type-configuration.html | primary | A
- Pre-Arm Safety Checks — ArduPilot Copter | https://ardupilot.org/copter/docs/common-prearm-safety-checks.html | primary | A
- Choosing an Autopilot — ArduPilot Copter | https://ardupilot.org/copter/docs/common-autopilots.html | primary | A
- Lua Scripts — ArduPilot | https://ardupilot.org/copter/docs/common-lua-scripts.html | primary | A

## checklist
- I understand the Copter/Plane difference and what `FRAME_CLASS` and `FRAME_TYPE` set
- I save the parameters to a file before making changes
- I know which modes need GPS
- I don't disable pre-arm checks just to take off
- I know my FC's processor series and the F4 limitations
