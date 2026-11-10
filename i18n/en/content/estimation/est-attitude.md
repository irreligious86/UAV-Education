---
id: est-attitude
title: "Attitude: Euler angles, quaternions, complementary filter"
level: L3
readingTime: 40 min
firmware: any firmware
status: published
added: 2026-11-08
tags:
  - attitude
  - quaternions
  - complementary filter
  - AHRS
related:
  - est-sensors
  - data-python
  - est-kalman
  - ap-ekf
next:
  - est-kalman
source: content/estimation/est-attitude.md
source_hash: 9c8396264f5f
---

## summary
“Which way is up” is the first question an autopilot answers a thousand times per second. The gyro gives a fast but drifting answer; the accelerometer a slow and noisy one, but without drift; the compass gives heading. This module explains why Euler angles break (gimbal lock) and firmware lives on quaternions, how to integrate angular rate, how a complementary filter works (in Python, ~40 lines) and how it relates to ArduPilot's DCM and to Mahony/Madgwick in Betaflight/INAV. Lab: your own filter on an IMU recording against `ATT` from the log.

## theory
### Representing attitude
- **Euler angles** (roll φ, pitch θ, yaw ψ) — convenient for humans. The problem: at θ = ±90° roll and yaw merge (**gimbal lock**), and the equations for the angle rates contain a division by cos θ. For freestyle with loops that's unacceptable. They're used only for output (`ATT.Roll/Pitch/Yaw`).
- **Rotation matrix (DCM)** — 3×3, the columns are the aircraft axes in the earth frame. No singularities, but 9 numbers with 6 constraints; it needs orthonormalization after integration.
- **Quaternion** q = (w, x, y, z), |q| = 1 — 4 numbers, one constraint, no singularities, cheap multiplication. The standard in Betaflight (since 3.x), INAV, PX4 (`vehicle_attitude.q`), EKF3 (states 0–3).

Quaternion → Euler conversion (for output):
φ = atan2(2(wx + yz), 1 − 2(x² + y²)); θ = asin(2(wy − zx)); ψ = atan2(2(wz + xy), 1 − 2(y² + z²)).

{{widget:attitude-3d}}

### Integrating the gyro
Angular rate ω (in body axes) changes the quaternion: q̇ = ½ · q ⊗ (0, ω). Discretely over a step Δt: q ← q ⊗ (cos(|ω|Δt/2), ω/|ω| · sin(|ω|Δt/2)), then normalize. Gyro only → drift at the bias rate (0.05 °/s → 3°/min) plus accumulated noise.

### Complementary filter
The idea: trust the gyro at high frequencies and the accelerometer (gravity) at low frequencies. The Mahony algorithm:
1. Predict “down” in body axes from the current q: v = R(q)ᵀ · (0, 0, 1).
2. The measured “down” is the normalized accelerometer with a minus sign: −a/|a| (the accelerometer measures specific force; at rest in FRD it reads (0, 0, −g)).
3. The error is the cross product e = a × v (small when they agree; its direction is the correction axis).
4. Correct the angular rate: ω' = ω + Kp·e + Ki·∫e (Ki is the gyro bias estimate!).
5. Integrate ω' into q.

Kp sets the time constant of “trust” in the accelerometer: τ ≈ 1/Kp; Kp = 0.5 → ~2 s. During maneuvers |a| ≠ 1 g — the accelerometer lies; the standard protection is to reduce Kp when | |a| − g | is large (ArduPilot DCM: `AHRS_GPS_GAIN`, using GPS for centripetal correction; Betaflight: `imu_dcm_kp`, disabling correction under large accelerations). The compass is added the same way for the yaw axis: the error between the measured and expected direction of the field's horizontal component.

### What this is in firmware
- **Betaflight**: a Mahony-like quaternion filter, `imu_dcm_kp` (default 2500 → 0.25 after scaling), `imu_dcm_ki`; without a compass yaw drifts — irrelevant for Acro, and GPS Rescue uses the GPS course.
- **INAV**: the same class of filter + compass and GPS course, corrections that account for acceleration from GPS.
- **ArduPilot**: DCM (a matrix, with correction from GPS velocity) as the fallback; the primary one is **EKF3**, where attitude is part of the state vector together with velocity, position and sensor biases. A complementary filter is an EKF with constant, non-adaptive gains.
- **PX4**: EKF2 (`ekf2`), attitude in `vehicle_attitude`.

### Why yaw is special
Gravity carries no information about heading: without a compass or GPS course, yaw drifts with the gyro Z bias. In a hover that's ~3°/min, unnoticeable; over 10 minutes it's 30°, and Loiter will spiral (the “toilet bowl” is the classic symptom). Yaw sources: compass (interference), GPS course while moving (not in a hover), dual GPS (moving baseline), EKF-GSF (estimation from motion, ArduPilot `EK3_SRC1_YAW = 8`), external navigation.

{{diagram:complementary-filter|Complementary filter: the gyro integral is accurate over a short interval, the accelerometer angle over a long one; the weights α and 1 − α blend them.}}

## practice
### Step 1. Recording the IMU
ArduPilot: a log with `IMU` (gyro, accel) and `ATT`; `LOG_BITMASK` with IMU_RAW isn't needed — 50–400 Hz IMU is enough. Betaflight: blackbox with `debug_mode = ATTITUDE` (it logs the angles), or use gyro + accel from a regular log. A 2–3 minute flight with tilts and hovering.

### Step 2. Your own filter
```python
import numpy as np
def qmul(a, b):
    w1,x1,y1,z1 = a; w2,x2,y2,z2 = b
    return np.array([w1*w2-x1*x2-y1*y2-z1*z2, w1*x2+x1*w2+y1*z2-z1*y2,
                     w1*y2-x1*z2+y1*w2+z1*x2, w1*z2+x1*y2-y1*x2+z1*w2])
def down_body(q):          # gravity direction in body frame from quaternion (w,x,y,z)
    w,x,y,z = q
    return np.array([2*(x*z - w*y), 2*(w*x + y*z), w*w - x*x - y*y + z*z])
def mahony(gyro, acc, dt, kp=0.5, ki=0.01):
    q = np.array([1.0, 0, 0, 0]); ib = np.zeros(3); out = []
    for g, a in zip(gyro, acc):                 # g in rad/s, a in m/s^2 (body frame)
        an = np.linalg.norm(a)
        if an > 1e-3:
            a_u = -a / an; v = down_body(q)   # accel measures specific force (-g at rest, FRD)
            e = np.cross(a_u, v)
            trust = 1.0 if abs(an - 9.81) < 2.0 else 0.0   # ignore accel during hard manoeuvres
            ib += ki * e * dt * trust
            g = g + (kp * e * trust) + ib
        n = np.linalg.norm(g)
        if n > 1e-9:
            dq = np.concatenate([[np.cos(n*dt/2)], g/n*np.sin(n*dt/2)])
            q = qmul(q, dq); q /= np.linalg.norm(q)
        w,x,y,z = q
        out.append([np.degrees(np.arctan2(2*(w*x+y*z), 1-2*(x*x+y*y))),
                    np.degrees(np.arcsin(np.clip(2*(w*y-z*x), -1, 1)))])
    return np.array(out)
```
Run it on your own recording; plot roll/pitch against `ATT.Roll/Pitch` (ArduPilot) or the angles from the debug log.

### Step 3. Experiments
- Ki = 0: watch the slow drift under a constant bias.
- Kp = 0: gyro only — drift.
- Kp = 5: the accelerometer “pulls” during maneuvers — errors while accelerating.
- Compare the RMS error relative to ATT for the three Kp values.

### Step 4. Yaw
Integrate gyro Z without correction — record the drift over a minute; compare with `ATT.Yaw`. Explain where the firmware gets its heading from. Lab: the filter is implemented, compared with ATT, the yaw drift is explained.

### What you should get and what to record
- **Comparison with ATT.** In a hover and during smooth tilts your filter should track the autopilot's `ATT.Roll` and `ATT.Pitch` closely: a difference of a few degrees, with no systematic drift. Calculate the RMS of the difference in roll and pitch and record it.
- **Hard maneuvers.** During hard accelerations the accelerometer reads more than just gravity, so the filter stops trusting it (`trust = 0`) and integrates only the gyro for that time. Find such a segment and see how the error grows while trust is off.
- **kp and ki.** Increase `kp` 10× — the estimate starts jittering along with accelerometer vibration. Decrease it 10× — it slowly creeps away with the gyro drift. Record both observations: this is the whole point of a complementary filter.
- **Yaw without a compass.** Gravity is parallel to the yaw axis, so the accelerometer tells you nothing about heading. The heading error is the integral of the gyro bias: at a 0.5 °/s bias that's 30° per minute. Estimate your gyro's bias from a stationary segment of the log and calculate the expected drift over a flight.

The lab counts as done when the filter is implemented and run on an IMU recording, the comparison with `ATT` produced numbers (RMS of the difference in roll and pitch), the `kp` experiments are described, and the yaw drift is explained and estimated from the gyro bias.

## diagnostics
- **Symptom:** the OSD horizon drifts after hard maneuvers and slowly comes back
  - Possible cause: the gyro accumulated error, Kp is small — slow recovery.
  - What to do: normal for Acro; for Angle — raise Kp moderately, check vibrations.
- **Symptom:** Loiter moves in a spiral, the heading in the OSD doesn't match the real one
  - Possible cause: yaw drift / a bad compass.
  - What to do: compass, GPS yaw, GSF; check for interference.
- **Symptom:** your own filter diverges from ATT by 5–10° during maneuvers
  - Possible cause: no compensation for centripetal acceleration.
  - What to do: add correction from GPS velocity or reduce trust in the accel when |a| ≠ g.
- **Symptom:** NaN in the quaternion
  - Possible cause: normalization skipped or acc = 0.
  - What to do: check norms, guard divisions.

## references
- ArduPilot — EKF (Extended Kalman Filter) overview | https://ardupilot.org/copter/docs/common-apm-navigation-extended-kalman-filter-overview.html | primary | A
- PX4 — Using the ECL EKF (attitude/state estimation) | https://docs.px4.io/main/en/advanced_config/tuning_the_ecl_ekf.html | primary | A
- Mahony et al., "Nonlinear Complementary Filters on the Special Orthogonal Group" (IEEE TAC 2008) — the original source of the algorithm | https://hal.archives-ouvertes.fr/hal-00488376 | primary | A

## checklist
- I can explain gimbal lock and why firmware runs on quaternions
- I understand how the complementary filter's Kp/Ki split trust between the gyro and the accelerometer
- I implemented the filter and compared it with ATT from the log
- I know where yaw comes from and why it drifts without a compass
- I understand how the complementary filter relates to the EKF
