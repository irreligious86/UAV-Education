---
id: est-sensors
title: "IMU Sensors: Physics, Errors, Calibration"
level: L2
readingTime: 35 min
firmware: any firmware
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
source_hash: 79e03bf3c00b
---

## summary
The autopilot knows about the world only what its sensors tell it, and each of them lies in its own way. This module covers the physics of the MEMS gyroscope, accelerometer and magnetometer at the level an engineer needs: bias (zero offset), noise (ARW/VRW), temperature drift, scale error and non-orthogonality; what exactly the 6-position accelerometer calibration and the compass calibration (hard/soft iron) calibrate, and how to measure gyro bias and noise yourself. The result is an “IMU datasheet” for your own flight controller, with numbers.

## theory
### MEMS gyroscope
A vibrating mass inside the chip; when the body rotates, the Coriolis force deflects it perpendicularly, and a capacitive sensor measures the deflection, which is proportional to angular rate. The output is three angular rates in °/s (or rad/s), with a typical range of ±2000 °/s (ICM42688: up to ±2000, 16 bits → 0.061 °/s per LSB).

Errors:
- **Bias** b — the output at zero rotation: a few °/s “out of the box”; after zero calibration on the ground (ArduPilot — at power-up (`INS_GYR_CAL = 1`, Start-up only), Betaflight — at power-up) what remains is **bias instability** of 0.01–0.1 °/s, which wanders with time and temperature. When you integrate ω to get an angle, a 0.05 °/s bias gives 3° per minute — that's why you can't get the angle from the gyro alone.
- **Noise** — white, characterized by Angle Random Walk: ARW ≈ 0.1–0.5 °/√h for consumer MEMS; in a 1 kHz bandwidth that's ~0.1 °/s RMS. On a spectrum it's the flat floor that the motor peaks sit on.
- **Temperature drift** of the bias: 0.01–0.05 °/s per °C; the board warming up by 20 °C after power-up causes a noticeable shift. ArduPilot: `INS_TCAL_*` (temperature calibration), IMU heating on the Cube/some H7 boards (`BRD_HEAT_TARG`).
- **Scale and non-orthogonality**: a 0.5–1% error — over a 360° rotation that's a 2–4° error; rarely calibrated (you need a rate table).
- **g-sensitivity**: linear acceleration (vibration!) changes the output — yet another path by which vibration corrupts the estimate.

### MEMS accelerometer
A proof mass on a spring; it measures **specific force**: at rest it reads +1 g upward (the support reaction force), in free fall — 0. Hence the key fact: the accelerometer does not measure motion acceleration separately from gravity; in a steady hover it sees ~1 g along the vehicle's “up,” and in a coordinated turn — also along “up” (which is why the roll angle from the accelerometer is wrong in a turn).

Errors: bias (tens of mg, i.e., a 1–3° horizon error without calibration), scale (1–2%), axis non-orthogonality, temperature drift, **clipping** (saturation at ±16 g from impacts and vibration — `VIBE.Clip` in ArduPilot), vibration aliasing into the band.

### 6-position accelerometer calibration
The vehicle is placed on 6 faces (±X, ±Y, ±Z up). In each one the truth is known: exactly +1 g on one axis, 0 on the others. From the six measurements you solve a system for 3 biases + 3 scales (ArduPilot also solves for non-orthogonality during `INS_ACC*_ID` calibration via Mission Planner). Betaflight calibrates only the zero from a single position (level) — the scale error remains, but for Acro it doesn't matter. Rule: calibrate at the temperature you fly at; after a hard crash, redo it.

### Magnetometer
Measures the magnetic field (µT or mGauss) on three axes; the heading is the projection of the Earth's field (~25–65 µT, inclination up to 70° at mid-latitudes — a large vertical component, which is why the heading is wrong without knowing roll/pitch).

- **Hard iron** — a constant field from magnetized parts and DC currents on board: it shifts the measurement sphere away from the origin. Calibrated as an offset (`COMPASS_OFS_*`); the “compass dance” — rotating about all axes to fill the sphere.
- **Soft iron** — ferromagnetic materials distort the field: the sphere becomes an ellipsoid. Calibrated with a matrix (`COMPASS_DIA_*`, `COMPASS_ODI_*`).
- **Current-induced interference** (see the EMI module): depends on throttle → `compassmot`, `COMPASS_MOT_*`.
- Compass orientation relative to the FC (`COMPASS_ORIENT`) — a common mistake with an external compass; ArduPilot can detect it automatically during calibration.

### Barometer (briefly; more in the altitude module)
Pressure → altitude via the standard atmosphere; errors: temperature drift, prop airflow, weather (1–3 m drift in half an hour), solar heating. Resolution of good MEMS baros is ~10 cm, noise ~0.5 m unfiltered.

### What the firmware does with raw data
ArduPilot: `INS_GYRO_FILTER`/`INS_ACCEL_FILTER` (20 Hz LPF for accel by default), notches, then EKF3 estimates gyro and accelerometer bias **in flight** (EKF states: `XKF1.GX/GY/GZ` — gyro bias, `XKF2.AX/AY/AZ` — accel bias). Betaflight — filters and a complementary attitude filter (the “Attitude” module).

{{diagram:imu-error-model|MEMS error model: calibration removes scale and misalignment, the EKF estimates the bias, and mechanics and filters deal with noise and vibration.}}

## practice
### Step 1. Gyro noise and bias at rest
A 60 s log on the ground, motors off (ArduPilot: `LOG_DISARMED = 1`, `IMU`; Betaflight: blackbox with `blackbox_mode = ALWAYS` or via a switch). For each of the three axes: the mean (bias after zero calibration) and the std (noise). Expected: |bias| < 0.1 °/s, std 0.05–0.3 °/s at 1 kHz.

### Step 2. Temperature drift
The same log right after powering up a cold board and again after 10 minutes of warm-up: the shift in the mean. If it's > 0.2 °/s, enable/check temperature calibration or heating.

### Step 3. Accelerometer calibration
6-position via Mission Planner / QGC (ArduPilot) or level + calibration in Betaflight. Check: level (with a spirit level on the frame!), `AHRS` roll/pitch ≤ 0.5°; on its side — 90 ± 1°.

### Step 4. Compass: hard iron
Before calibration: record `MAG.MagX/Y/Z` while slowly rotating 360° level → a circle on the MagX–MagY plot; the center of the circle = the hard-iron offset. After calibration, `COMPASS_OFS_*` should roughly match the center you found. Record the field magnitude |B| — it should be constant within ±5% at any orientation. Lab: an IMU datasheet with bias/noise, the accel calibration result and the hard-iron offset.

## diagnostics
- **Symptom:** the OSD horizon is tilted at rest
  - Possible cause: accelerometer bias / calibration on an uneven surface.
  - What to do: 6-position calibration on a level surface.
- **Symptom:** heading drift after compass calibration
  - Possible cause: calibration near metal/indoors, wrong `COMPASS_ORIENT`.
  - What to do: calibrate in the field, check the orientation, is |B| constant?
- **Symptom:** EKF variances grow after warm-up
  - Possible cause: temperature drift of the gyro bias.
  - What to do: `INS_TCAL`, heating, let the board warm up before arming.
- **Symptom:** `VIBE.Clip` > 0
  - Possible cause: the accelerometer saturates from vibration/impacts.
  - What to do: mechanics, damping, accel range.
- **Symptom:** the heading is wrong when tilted
  - Possible cause: the compass isn't tilt-compensated (no attitude estimate) or soft iron.
  - What to do: full calibration with the matrix, check that attitude is being computed.

## references
- ArduPilot — Accelerometer Calibration | https://ardupilot.org/copter/docs/common-accelerometer-calibration.html | primary | A
- ArduPilot — Compass Calibration | https://ardupilot.org/copter/docs/common-compass-calibration-in-mission-planner.html | primary | A
- ArduPilot — IMU Temperature Calibration | https://ardupilot.org/copter/docs/common-imutempcal.html | primary | A

## checklist
- I know what bias, noise, temperature drift and scale are
- I understand that the accelerometer measures specific force, not motion acceleration
- I measured the gyro bias and noise of my FC
- I performed a 6-position calibration and checked the horizon
- I estimated the compass hard-iron offset and checked that |B| is constant
