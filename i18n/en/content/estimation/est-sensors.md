---
id: est-sensors
title: "IMU sensors: physics, errors, calibration"
level: L2
readingTime: 35 min
firmware: ArduPilot 4.7 (checked against 4.7.3) · PX4 1.18 (checked against v1.18.0) · INAV 9.1.0 · Betaflight 2025.12.5
status: published
added: 2026-11-08
tags:
  - IMU
  - gyroscope
  - accelerometer
  - compass
  - calibration
related:
  - f-fc-sensors
  - el-emi
  - est-attitude
next:
  - est-attitude
source: content/estimation/est-sensors.md
source_hash: a91148344ed5
---

## summary
An autopilot knows only what its sensors tell it, and each of them lies in its own way. This module covers the physics of the MEMS gyroscope, accelerometer and magnetometer at the level an engineer needs: bias (zero offset), noise (ARW/VRW), temperature drift, scale error and misalignment; what exactly the 6-position accelerometer calibration and the compass calibration (hard/soft iron) calibrate; and how to measure gyro bias and noise yourself. The result is an "IMU passport" for your flight controller, with numbers.

## theory
### MEMS gyroscope
A vibrating proof mass inside the chip; when the package rotates, the Coriolis force deflects it perpendicularly, and a capacitive sensor measures the deflection, which is proportional to the angular rate. The output is three angular rates in °/s (or rad/s), with a typical range of ±2000 °/s (ICM42688: up to ±2000, 16 bits → 0.061 °/s per LSB).

Errors:
- **Bias** b, the output at zero rotation: several °/s "out of the box"; after zero calibration on the ground (ArduPilot at power-on (`INS_GYR_CAL = 1`, Start-up only), Betaflight at power-on) what remains is a **residual bias** of 0.01–0.1 °/s (bias instability proper is a few °/h; the rest is temperature and turn-on repeatability) that wanders with time and temperature. When you integrate ω to get an angle, a 0.05 °/s bias gives 3° per minute; that is why you cannot get the angle from the gyro alone.
- **Noise** is white and characterized by Angle Random Walk: ARW ≈ 0.1–0.5 °/√h for consumer MEMS; in a 1 kHz bandwidth that is ~0.1 °/s RMS. On a spectrum it is the flat floor that the motor peaks sit on.
- **Temperature drift** of the bias: 0.005–0.05 °/s per °C (ICM-42688-P: ±0.005); the board warming by 20 °C after power-on is a noticeable shift. ArduPilot: `INS_TCAL_*` (temperature calibration), IMU heating on the Cube and some H7 boards (`BRD_HEAT_TARG`, −1…80 °C, −1 disables it; the board sets the default: in ArduPilot 4.7.3 the Cube Orange, Pixhawk 6X and most boards with a heater use 45 °C, `HAL_IMU_TEMP_DEFAULT` in the hwdef). The rule (a course guideline): keep the board default, which is a target above the air temperature, so the IMU stays at one point; raise it only if in hot weather the IMU temperature in the log (`IMU.T`) is above the target, because then the heater stabilizes nothing. `BRD_HEAT_LOWMGN` > 0 blocks arming until the board has warmed up.
- **Scale and misalignment**: an error of 0.5–1% gives 2–4° over a 360° rotation; rarely calibrated (it needs a rate table).
- **g-sensitivity**: linear acceleration (vibration!) changes the output, one more way vibration corrupts the estimate.

### MEMS accelerometer
A proof mass on a spring; it measures **specific force**: at rest it reads +1 g up (the support reaction), in free fall 0. Hence the key fact: an accelerometer does not measure the acceleration of motion separately from gravity; in steady hover it sees ~1 g along the vehicle's "up," and in a coordinated turn also along "up" (which is why the bank angle from the accelerometer is wrong in a turn).

Errors: bias (tens of mg, that is a 1–3° horizon error without calibration), scale (1–2%), axis misalignment, temperature drift, **clipping** (saturation at ±16 g from impacts and vibration, `VIBE.Clip` in ArduPilot), and vibration aliasing into the passband.

### 6-position accelerometer calibration
The vehicle is placed on 6 faces (±X, ±Y, ±Z up). In each the truth is known: exactly +1 g on one axis, 0 on the others. The six measurements give a system for 3 biases + 3 scales (that is what ArduPilot does: `INS_ACCOFFS` + `INS_ACCSCAL`, an axis-aligned ellipsoid without cross terms, so misalignment is not calibrated; `INS_ACC*_ID` is only the sensor identifier). Betaflight calibrates only the zero, from a single (level) position; the scale error remains, but for Acro that does not matter. The rule: calibrate at the temperature you fly at; repeat after a hard impact.

### Magnetometer
It measures the magnetic field (µT or mG) on three axes; heading is the projection of the Earth's field (~25–65 µT, inclination up to 70° at mid-latitudes, a large vertical component, which is why the heading is wrong without knowing roll and pitch).

- **Hard iron** is a constant field from magnetized parts and steady currents on board: it shifts the measurement sphere away from the origin. It is calibrated as an offset (`COMPASS_OFS_*`); the "compass dance" is rotating the vehicle about all axes to fill the sphere.
- **Soft iron** is ferromagnetic material that distorts the field: the sphere becomes an ellipsoid. It is calibrated as a matrix (`COMPASS_DIA_*`, `COMPASS_ODI_*`).
- **Current interference** (see the EMI module) depends on throttle → `compassmot`, `COMPASS_MOT_*`.
- The compass orientation relative to the FC (`COMPASS_ORIENT`) is a common mistake with an external compass; ArduPilot can detect it automatically during calibration.

### Compass calibration: which method, and how to check it
The input is three questions: can you rotate the vehicle by hand; does the field depend on current (the length of `MAG` in the log changes with throttle); which firmware. The order is always the same: mechanics first (compass on a mast, away from power wires, see `el-emi`), then orientation, then calibration, and only the remaining interference is subtracted in software.

| Situation | ArduPilot 4.7.3 | PX4 1.18.0 | INAV 9.1.0 |
|---|---|---|---|
| External compass orientation | `COMPASS_AUTO_ROT = 2` (default): checks and fixes it after calibration | `SENS_MAG_AUTOROT = 1` (default) | manual: `align_mag` in 90° steps or `align_mag_roll/pitch/yaw` in tenths of a degree |
| You can rotate the vehicle | rotation calibration, threshold `COMPASS_CAL_FIT = 16` for the first compass if it is external; 32 for internal and the others | calibration in QGC, `SENS_MAG_SIDES = 63`, all six sides (`CAL_MAG_SIDES` is kept for legacy QGC) | `mag_calibration_time` = 30 s (20–120); writes `magzero_*` (offsets) and `maggain_*` (per-axis scale) |
| You cannot rotate it | Large Vehicle MagCal (`MAV_CMD_FIXED_MAG_CAL_YAW`, a known heading): offsets only | the same command; `commander calibrate mag quick` without a heading assumes the nose points north | no equivalent in the source |
| Current interference | CompassMot (Copter only, not helicopters; spins the motors with props on) or MagFit from a log with current | `CAL_MAG_COMP_TYP`: 1 throttle-based, 2/3 current-based from battery 0/1; the `CAL_MAGn_XCOMP/YCOMP/ZCOMP` coefficients are computed by `mag_compensation.py` from a ULog | no current compensation, only moving the compass |

MagFit (ArduPilot, WebTools MAGFit or MAVExplorer) fits the parameters to an already recorded flight using the Earth field model. The documentation's requirements: several full turns, at least a few minutes of log, segments on the ground and in hand excluded; offsets are usually enough. The result is accepted if the heading deviation after fitting is under 10°; if the heading correction exceeds 20°, look for a different fault first. MagFit does not replace the rotation calibration before flight. A worked example with numbers is in `ap-sensors`.

{{diagram:compass-cal-choice-tree|In ArduPilot two questions set the compass calibration method: can you rotate the vehicle, and does the field depend on throttle; current interference is subtracted by CompassMot or MagFit only after the mechanics are sorted.}}

How to check that the calibration worked:
- the field magnitude stays constant within ±5% at any orientation (Step 4);
- ArduPilot: the offset vector length is below `COMPASS_OFFS_MAX` = 1800, the difference from the field model is below `ARMING_MAGTHRESH` = 100 mG horizontally (vertically, twice that, 200 mG); CompassMot interference is below 30% (`ap-sensors`);
- INAV: all `magzero_*` at zero and `maggain_*` = 1024 means there is no calibration or it failed.

### Barometer (briefly; more in the altitude module)
Pressure → altitude via the standard atmosphere; errors: temperature drift, airflow from the props, weather (a drift of 1–3 m in half an hour), solar heating. Good MEMS baros resolve ~10 cm, with ~0.5 m of noise unfiltered.

### What the firmware does with raw data
ArduPilot: `INS_GYRO_FILTER`/`INS_ACCEL_FILTER` (a 20 Hz LPF for the accel by default), notches, then EKF3 estimates the gyro and accelerometer biases **in flight** (EKF states: `XKF1.GX/GY/GZ` is the gyro bias, `XKF2.AX/AY/AZ` the accel bias). Betaflight: filters and the complementary attitude filter (the Attitude module).

{{lesson:ap-ahrs-choice|Which IMU EKF3 picks, how lanes work and what happens when one accelerometer starts lying: the switch in SITL takes 0.75 s.}}

{{diagram:imu-error-model|The MEMS error model: calibration removes scale and misalignment, the EKF estimates bias, and mechanics and filters handle noise and vibration.}}

### Where it fits

- **Receives:** raw chip data over SPI and I²C (`f-fc-sensors`); frame vibration, through the gyro's g-sensitivity and accelerometer clipping (`f-frame-mech`); magnetic interference from currents (`el-emi`) and the battery current to subtract it, via CompassMot or MagFit (`ap-sensors`).
- **Provides:** calibrated gyro, accelerometer and compass to the attitude filter and the EKF (`est-attitude`, `est-kalman`); the gyro to the filters before the PID (`bf-filters`); the barometer to the altitude sources (`est-alt-sources`).
- **If you get this wrong:** a wrong `COMPASS_ORIENT` on an external compass → the measured field disagrees with the attitude, the heading jumps, and Loiter toilet-bowls (`nav-resilience`, `ap-ekf`). An accelerometer not recalibrated after an impact → the horizon is off by degrees and the vehicle drifts sideways in a self-leveling mode (`est-attitude`). Clipping from vibration → the EKF loses altitude (`ap-logs`).

## practice
### Step 1. Gyro noise and bias at rest
Log 60 s on the ground without motors (ArduPilot: `LOG_DISARMED = 1`, `IMU`; Betaflight: blackbox with `blackbox_mode = ALWAYS` or on a switch). For the three axes: the mean (the bias after zero calibration) and the std (the noise). Expected: |bias| < 0.1 °/s, std 0.05–0.3 °/s at 1 kHz.

### Step 2. Temperature drift
The same log right after powering a cold board and after 10 minutes of warm-up: the shift of the mean. If it is > 0.2 °/s, enable or check temperature calibration or heating.

### Step 3. Accelerometer calibration
6-position through Mission Planner / QGC (ArduPilot), or level + calibration in Betaflight. Check: level (a spirit level on the frame!) gives `AHRS` roll/pitch ≤ 0.5°; on its side, 90 ± 1°.

### Step 4. Compass: hard iron
Before calibration: record `MAG.MagX/Y/Z` during a slow 360° rotation while level → a circle on the MagX–MagY plot; the center of the circle is the hard-iron offset. After calibration `COMPASS_OFS_*` should roughly match the center you found. Record the field magnitude |B|: it should be constant ±5% at any orientation. Self-check: the lab is done when the IMU passport records, within the expected values: gyro |bias| < 0.1 °/s and std 0.05–0.3 °/s on each axis, a mean shift after warm-up of no more than 0.2 °/s, a horizon after accelerometer calibration of ≤ 0.5° and 90 ± 1° on the side, the center of the MagX–MagY circle roughly matching `COMPASS_OFS_*`, and a field magnitude |B| constant within ±5% during rotation.

**Reference for the self-check.** Before calibration the MagX–MagY circle is shifted from the origin; that is the hard iron; after calibration its center is near zero. Common wrong results: a gyro bias of several °/s is the "out of the box" value, meaning the zero calibration at power-on did not happen; a 1–3° horizon error means the accelerometer bias is not calibrated or the level was not resting on the frame; an ellipse instead of a circle with |B| wandering by more than ±5% is soft iron or current interference, which an offset alone does not fix; a mean shift after warm-up above 0.2 °/s is temperature drift (0.005–0.05 °/s per °C over a 20 °C warm-up), and you need temperature calibration or heating.

## diagnostics
- **Symptom:** the OSD horizon is tilted at rest
  - Possible cause: accelerometer bias, or calibration on an uneven surface.
  - What to do: 6-position calibration on a level surface.
- **Symptom:** heading drift after compass calibration
  - Possible cause: calibration near metal or indoors, a wrong `COMPASS_ORIENT`.
  - What to do: calibrate in the open, check the orientation; is |B| constant?
- **Symptom:** EKF variances grow after warm-up
  - Possible cause: temperature drift of the gyro bias.
  - What to do: `INS_TCAL`, heating, let the board warm up before arming.
- **Symptom:** `VIBE.Clip` > 0
  - Possible cause: the accelerometer saturates from vibration or impacts.
  - What to do: mechanics, damping, accel range.
- **Symptom:** the heading is wrong when tilted
  - Possible cause: the compass is not tilt-compensated (no attitude estimate), or soft iron.
  - What to do: a full calibration with the matrix; check that attitude is being computed.

## references
- ArduPilot — Accelerometer Calibration | https://ardupilot.org/copter/docs/common-accelerometer-calibration.html | primary | A
- ArduPilot — Compass Calibration | https://ardupilot.org/copter/docs/common-compass-calibration-in-mission-planner.html | primary | A
- ArduPilot — IMU Temperature Calibration | https://ardupilot.org/copter/docs/common-imutempcal.html | primary | A
- ArduPilot — Compass Calibration with MagFit (accessed 2026-11-22) | https://ardupilot.org/copter/docs/common-magfit.html | primary | A
- ArduPilot Copter-4.7.3 libraries/AP_Compass/AP_Compass.cpp (CAL_FIT, AUTO_ROT, OFFS_MAX) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.3/libraries/AP_Compass/AP_Compass.cpp | primary | A
- PX4 v1.18.0 sensor_params_mag.yaml and mag_compensation.py (SENS_MAG_SIDES, CAL_MAG_COMP_TYP, compensation from a ULog) | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/modules/sensors/sensor_params_mag.yaml | primary | A
- INAV 9.1.0 src/main/fc/settings.yaml (align_mag, magzero, maggain, mag_calibration_time) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/settings.yaml | primary | A

## checklist
- I know what bias, noise, temperature drift and scale are
- I understand that an accelerometer measures specific force, not the acceleration of motion
- I measured the bias and noise of my FC's gyro
- I did a 6-position calibration and checked the horizon
- I estimated the compass hard-iron offset and checked that |B| is constant
- I choose the compass calibration method from three inputs (rotation, current interference, firmware) and check the result against the thresholds
