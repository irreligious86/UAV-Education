---
id: est-attitude
title: "Attitude: Euler angles, quaternions, complementary filter"
level: L3
readingTime: 60 min
firmware: Betaflight 2025.12.5 · INAV 9.1.0 · ArduPilot 4.7 (checked against 4.7.3) · PX4 1.18 (checked against v1.18.0)
status: published
added: 2026-11-08
tags:
  - attitude
  - quaternions
  - complementary filter
  - Mahony
  - Madgwick
  - AHRS
related:
  - est-sensors
  - data-python
  - est-kalman
  - ap-ekf
  - ap-ahrs-choice
next:
  - est-kalman
source: content/estimation/est-attitude.md
source_hash: 1239196e3b30
---

## summary
"Which way is up" is the first question an autopilot answers hundreds of times a second. The gyro gives a fast answer that drifts; the accelerometer gives a slow, noisy one that is fooled by any acceleration but does not drift; the compass gives heading. This module explains why Euler angles break (gimbal lock) and firmware runs on quaternions, how to integrate angular rate and what that costs in degrees, how the complementary filter, Mahony and Madgwick work, where the constant error `b/Kp` comes from, and what exactly runs in Betaflight, INAV, ArduPilot and PX4, with parameters and defaults from the source. The lab: a Python IMU model with bias, noise, vibration, acceleration bursts and a coordinated turn; five estimators are compared by the numbers, then the same filter runs on your own IMU recording against `ATT` from the log.

## theory
### Representing attitude
- **Euler angles** (roll φ, pitch θ, yaw ψ) are convenient for humans. The problem: at θ = ±90° roll and yaw merge (**gimbal lock**), and the equations for the angle rates divide by cos θ. For freestyle with loops that is unacceptable. So attitude is stored and integrated as a quaternion (or a matrix), and Euler angles are derived from it: for the OSD and the log (`ATT.Roll/Pitch/Yaw`), and in Betaflight also for the Angle/Horizon controller (`attitude.raw` in `pid.c`); ArduPilot and PX4 control attitude from the quaternion.
- **Rotation matrix (DCM)**: 3×3, its columns are the vehicle axes in the earth frame. No singularities, but 9 numbers with 6 constraints; it needs re-orthonormalization after integration.
- **Quaternion** q = (w, x, y, z), |q| = 1: 4 numbers, one constraint, no singularities, cheap multiplication. The standard in Betaflight, INAV, PX4 (`vehicle_attitude.q`) and EKF3 (states 0–3).

Quaternion to Euler (for output):
φ = atan2(2(wx + yz), 1 − 2(x² + y²)); θ = asin(2(wy − zx)); ψ = atan2(2(wz + xy), 1 − 2(y² + z²)).

Gimbal lock is not an abstraction. The yaw rate from the gyro is ψ̇ = (q·sin φ + r·cos φ) / cos θ. The factor 1/cos θ is 2.0 at 60°, 5.8 at 80°, 11.5 at 85° and 57.3 at 89° (lab output below): gyro noise of 0.1 °/s near vertical becomes 5.7 °/s of noise in ψ, and at 90° the formula divides by zero. The matrix and the quaternion are integrated without these formulas, so they have no singularity; Euler angles are computed only at the output.

{{widget:attitude-3d}}

### Integrating the gyro
The angular rate ω (in body axes) changes the quaternion: q̇ = ½ · q ⊗ (0, ω). Discretely, over a step Δt: q ← q ⊗ (cos(|ω|Δt/2), ω/|ω| · sin(|ω|Δt/2)), then normalize. Gyro alone means drift at the bias rate (0.05 °/s → 3°/min) plus accumulated noise.

The integration error budget has two terms. A constant bias b gives an angle that grows linearly: e = b·t. White noise with density N (°/s/√Hz) gives angle random walk: σ = N·√t. For a consumer MEMS part with an ARW of 0.3 °/√h (N = 0.005 °/s/√Hz, the middle of the range in `est-sensors`), noise over 120 s gives 0.055°, while an uncalibrated bias of 0.5 °/s gives 60°. Conclusion: gyro noise is almost harmless for attitude; the damage comes from bias. That is why firmware calibrates the gyro zero at power-on (the vehicle must be still) and also estimates the remaining bias in flight, with the filter's integrator or an EKF state.

### Accelerometer: tilt without drift, but it lies
The accelerometer measures specific force f = a − g (in body axes). At rest in the FRD frame it reads (0, 0, −g), and tilt is recovered without integration: φ = atan2(−f_y, −f_z), θ = atan2(f_x, √(f_y² + f_z²)). The error does not grow with time, but the accelerometer cannot tell gravity from acceleration. Three ways it lies:

1. **Linear acceleration.** A horizontal acceleration a_h tilts the measured "down" by atan(a_h/g). A copter accelerating at 4 m/s² tilts its thrust by 22°, and the accelerometer sees thrust along its own Z axis and reports "level." The magnitude |f| = √(4² + 9.81²) = 10.6 m/s² = 1.08 g: a "|a| close to 1 g" check does not catch this acceleration.
2. **Coordinated turn.** A plane in a 30° banked turn keeps the resultant force along its own Z axis; the accelerometer shows 0° of bank, with a magnitude of 1/cos 30° = 1.155 g. This is the main reason the horizon of a wing without GPS correction "floats up" in a long turn.
3. **Vibration.** Motors produce tens of m/s² at tens to hundreds of hertz (the motor rotation frequency, a course guideline: 50–150 Hz on large copters, ~200–350 Hz on 7-inch, 300–600 Hz on 5-inch quads). Firmware filters the accelerometer before attitude estimation: in Betaflight `acc_lpf_hz` = 25 Hz (PT2), and the |a| magnitude for the check is taken after the filter.

### Complementary filter
The idea: trust the gyro at high frequencies and the accelerometer (gravity) at low frequencies. The simplest form, on angles: φ ← α·(φ + ω_x·Δt) + (1 − α)·φ_acc, where α = τ/(τ + Δt). The time constant τ splits the bands: faster than τ is the gyro, slower is the accelerometer. The price is a constant error: a bias b shifts the estimate by e = b·τ (with τ = 2 s and b = 0.58 °/s, 1.17°; the lab shows 1.18°).

The Mahony algorithm does the same on the quaternion, without the Euler singularities:
1. Predict "down" in body axes from the current q: v = R(q)ᵀ · (0, 0, 1).
2. The measured "down" is the normalized accelerometer with a minus sign: −a/|a| (the accelerometer measures specific force; at rest in FRD it reads (0, 0, −g)).
3. The error is the cross product e = (−a/|a|) × v (small when they agree; its direction is the correction axis).
4. Correct the angular rate: ω' = ω + Kp·e + Ki·∫e (Ki is the gyro bias estimate!).
5. Integrate ω' into q.

Kp sets the time constant of "trust" in the accelerometer: τ ≈ 1/Kp; Kp = 0.5 → ~2 s, the Betaflight default 0.25 → 4 s. Without an integrator (Ki = 0) the bias is not subtracted but balanced by the correction: in steady state Kp·e = b, so the tilt settles with a constant error **e = b/Kp** (in radians). With b = 0.58 °/s and Kp = 0.25 that is 2.33°, exactly the maximum error in the lab. The Ki integrator finds the bias in roll and pitch (in the lab 0.489 and −0.296 against the true 0.5 and −0.3 °/s), but not in yaw: gravity is parallel to the Z axis, and in level flight the error e has no Z component.

During maneuvers |a| ≠ 1 g and the accelerometer lies; the standard protection is to skip or weaken the correction when | |a| − g | is large, and not to integrate the bias during fast rotation. Betaflight uses the accelerometer only when 0.9 g < |a| < 1.1 g and stops the integrator above 20 °/s; ArduPilot DCM compares acceleration with the derivative of GPS velocity and scales the correction with the `AHRS_GPS_GAIN` parameter. The compass is added the same way for the yaw axis: the error between the measured and expected direction of the horizontal field component.

Choosing Kp is a trade-off, and it has a minimum. A small Kp makes the filter slow to forget bias and gyro errors; a large one drags the estimate after every false "down" during acceleration. In the lab, the RMS error over the whole flight with the magnitude gate is 10.5° at Kp = 0.05, 2.8° at 0.25, 2.5° at 0.5, 4.8° at 2.5 and 6.1° at 10. Without the gate the minimum moves to Kp ≈ 0.1 (5.6°), because the turn pulls the estimate toward a false horizon.

{{diagram:chart-attitude-kp-sweep|The tilt estimate error has a minimum in Kp: on the left it comes from gyro drift (the b/Kp error), on the right from trusting a false "down" during acceleration; the |a| magnitude gate moves the minimum from 0.1 to 0.25–0.5 and halves the error.}}

### Mahony and Madgwick
Both filters are complementary, both run on the quaternion, and either is enough for a microcontroller AHRS. The difference is how the correction is computed.

- **Mahony** (2008) is a PI controller on the direction error: the correction is proportional to the cross product and is added to the angular rate before integration. Two gains: Kp (the time constant) and Ki (the bias estimate). The error behaves linearly: double Kp and the constant error from bias halves.
- **Madgwick** (2010) is a gradient-descent step on the function f(q) = v(q) − (−a/|a|): −β·∇f/|∇f| is added to the gyro-derived quaternion derivative. The gradient is normalized, so the correction always has the same size whatever the size of the error: β is in units of the quaternion derivative, that is ≈ 2β rad/s in angular rate (q̇ = ½·q⊗ω). The author sets β = √(3/4)·ω̄_β, where ω̄_β is the expected gyro error; in the `ahrs` 0.4.0 library the IMU default is 0.033. The basic version has no bias integrator: a bias up to β is compensated, but it still leaves a nonzero error.

In the lab, Madgwick with β = 0.05 is more accurate in hover (0.11° against 1.95° for Mahony with Ki = 0), because β = 0.05 (≈ 0.1 rad/s = 5.7 °/s in angular rate) covers the 0.58 °/s bias with almost no error, but in the turn it is as wrong as Mahony without the gate (15.4°): both accept the false "down" the same way. None of Betaflight, INAV, ArduPilot or PX4 uses Madgwick (a conclusion from the code: it is absent from their 2025.12.5 / 9.1.0 / 4.7.3 / 1.18.0 source trees); Madgwick shows up in Arduino libraries and in ROS (`imu_filter_madgwick` from the `imu_tools` package).

### What runs in the firmware
- **Betaflight 2025.12.5**: `imuMahonyAHRSupdate()` in `src/main/flight/imu.c`, Mahony on the quaternion. `imu_dcm_kp` = 2500 (divided by 10000 → 0.25), `imu_dcm_ki` = 0: bias is not estimated in flight; the gyro calibration at power-on does that job. Kp is not constant: while disarmed it is ×10 (2.5) for fast convergence; after any movement (gyro > 15 °/s on any axis, or |a| outside the window) it runs at the normal Kp until the vehicle has been still for 250 ms (every such movement restarts the count), then 500 ms at ×100 (the horizon reset after a crash), then ×10 again. The ATTITUDE task runs at 100 Hz in Acro and at the accelerometer rate divided by `imu_process_denom` (2) in Angle, Horizon, Alt Hold and Pos Hold. Without a compass, yaw is pulled toward the GPS course over ground (COG) in any mode when there is a fix and enough satellites, with a weight derived from ground speed, the yaw stick, roll and pitch (`imuCalcGroundspeedGain()`); in GPS Rescue the weight is set by Rescue itself. Without GPS and compass, yaw drifts; for Acro that does not matter.
- **INAV 9.1.0**: the same class of filter (`imuMahonyAHRSupdate` in `flight/imu.c`) plus compass and GPS course: `ahrs_dcm_kp` = 2000 (0.2), `ahrs_dcm_ki` = 50 (0.005), separate `ahrs_dcm_kp_mag` / `ahrs_dcm_ki_mag`, an accelerometer weight that falls linearly from 1 to 0 between 10 and 20 °/s (`ahrs_acc_ignore_rate` 15 ± `ahrs_acc_ignore_slope` 5, only when armed; aimed mainly at the centripetal acceleration of a wing in a turn), and inertia compensation `ahrs_inertia_comp_method` = ADAPTIVE.
- **ArduPilot 4.7.3**: the primary estimator is **EKF3** (`AHRS_EKF_TYPE` = 3), where attitude is part of a 24-state vector together with velocity, position and sensor biases. DCM always runs as a backup: `AHRS_RP_P` = 0.2, `AHRS_YAW_P` = 0.2, Ki = 0.0087 and 0.01 (constants in the code), the integrator stops above 20 °/s, and P is boosted up to ×10 during rotation at 50–500 °/s. A steady-state Kalman filter with constant noise degenerates into a complementary filter with constant gains; the EKF, in contrast, changes its gains according to the covariance.
- **PX4 1.18.0**: EKF2 (`EKF2_EN` = 1); attitude is the nominal quaternion plus 3 rotation error states in the 24-dimensional error-state vector, output in `vehicle_attitude`. The `attitude_estimator_q` module (a complementary filter on the quaternion) is still in the tree, but it is marked "unsupported" and disabled (`ATT_EN` = 0); `SYS_MC_EST_GROUP` was removed in 2024.

{{lesson:ap-ahrs-choice|How ArduPilot chooses between EKF3, DCM and EKF2, when it falls back to DCM on its own, and where it gets heading without a compass, with SITL experiments.}}

| Firmware | Algorithm | Parameter | Default | Meaning |
|---|---|---|---|---|
| Betaflight 2025.12.5 | Mahony | `imu_dcm_kp` | 2500 (0…32000) | Kp × 10000; 0.25 → τ ≈ 4 s |
| Betaflight 2025.12.5 | Mahony | `imu_dcm_ki` | 0 | Ki × 10000; 0 means bias is not estimated in flight |
| Betaflight 2025.12.5 | accelerometer filter | `acc_lpf_hz` | 25 Hz | PT2 before attitude estimation |
| Betaflight 2025.12.5 | task rate | `imu_process_denom` | 2 (1…4) | accelerometer rate divider in Angle/Horizon/Alt Hold/Pos Hold |
| Betaflight 2025.12.5 | arming | `small_angle` | 25° | the largest tilt at which you can arm |
| INAV 9.1.0 | Mahony | `ahrs_dcm_kp`, `ahrs_dcm_ki` | 2000, 50 | 0.2 and 0.005 |
| INAV 9.1.0 | Mahony | `ahrs_acc_ignore_rate` | 15 °/s | the weight falls from 1 to 0 over 10–20 °/s (slope 5) |
| ArduPilot 4.7.3 | selection | `AHRS_EKF_TYPE` | 3 | EKF3; 0 means DCM (Plane/Rover only) |
| ArduPilot 4.7.3 | DCM | `AHRS_RP_P`, `AHRS_YAW_P` | 0.2, 0.2 | Kp for roll/pitch and for heading |
| ArduPilot 4.7.3 | DCM | `AHRS_GPS_GAIN` | 1.0 | weight of the GPS acceleration correction |
| PX4 1.18.0 | EKF2 | `EKF2_EN` | 1 | the primary estimator |
| PX4 1.18.0 | Q filter | `ATT_EN`, `ATT_W_ACC`, `ATT_W_GYRO_BIAS` | 0, 0.2, 0.1 | unsupported; accelerometer and bias weights |

### Why yaw is special
Gravity carries no heading information: without a compass or GPS course, yaw drifts with the Z gyro bias. In hover that is ~3°/min, unnoticeable; over 10 minutes it is 30°, and Loiter starts moving in a spiral ("toilet bowling" is the classic symptom). The complementary filter's integrator will not find the Z bias: in the lab the estimate is 0.006 °/s against the true 0.2. Yaw sources: the compass (interference), GPS course while moving (not in hover; for a vehicle that flies forward, a plane or a rover, ArduPilot DCM switches to the GPS course above 3 m/s if the compass disagrees with it by more than 45° for longer than 2 s while the wind is below 80% of ground speed; on a copter DCM always uses the compass), dual GPS (moving baseline), EKF-GSF (an estimate from motion, ArduPilot `EK3_SRC1_YAW = 8`), external navigation.

{{diagram:complementary-filter|Complementary filter: the gyro integral is accurate over short intervals, the accelerometer angle over long ones; the weights α and 1 − α blend them.}}

{{diagram:attitude-mahony-loop|The Mahony loop in Betaflight: the gyro is always integrated, while the Kp·e correction from the accelerometer is applied only after the 25 Hz filter and the 0.9–1.1 g check; Ki in Betaflight defaults to 0.}}

### Where it fits

- **Receives:** angular rate, specific force and the magnetic field (`est-sensors`); GPS course and velocity (`est-gnss`); quaternion and rotation-matrix operations (`math-linalg-rot`).
- **Provides:** attitude: the quaternion to the attitude controller (ArduPilot, PX4) and navigation, Euler angles to the OSD, the log and the Betaflight Angle/Horizon controller; the same computation inside the EKF goes to `est-kalman` and `ap-ekf`.
- **If you get this wrong:** yaw has no working source (a compass with interference, no GPS course in hover), so the heading drifts with the gyro bias, about 30° accumulates over 10 minutes, and Loiter moves in a spiral (`nav-resilience`, tree 6 in `diag-troubleshooting`). The filter trusts the accelerometer during a maneuver, so in a turn the horizon is pulled toward a false "up"; you see it when comparing with `ATT` from the log (`ap-logs`).

## practice
The main path is a calculation without hardware: a Python IMU model with a known true attitude, in which every mechanism from the theory is visible. Then the same filter runs on your own recording.

### Step 1. Sensor model and five estimators
The script simulates 120 s of flight at 250 Hz: hover 0–20 s, smooth tilts of ±20°/±15° (20–60 s), 4 m/s² acceleration bursts (60–80 s), a coordinated turn banked 30° at 15 m/s (80–100 s), then hover again. Gyro: truth + bias (0.5, −0.3, 0.2) °/s + noise of 0.005 °/s/√Hz. Accelerometer: specific force + 2 m/s² vibration at 117 Hz from second 5 + noise; before the estimators, a 25 Hz PT2, like `acc_lpf_hz` in Betaflight. The error is the angle between the true and estimated "down," that is, the tilt error without heading. Only the Python 3 standard library.

```python
# att_lab.py — attitude estimation lab: simulated IMU, five estimators, numbers.
# python3 att_lab.py   (pure Python 3, no packages)
import math, random

G, FS, T = 9.81, 250, 120.0           # gravity, IMU rate Hz, flight length s
DT = 1.0 / FS
BIAS = [math.radians(b) for b in (0.5, -0.3, 0.2)]   # gyro bias, deg/s -> rad/s
ARW = math.radians(0.005)             # gyro noise density, rad/s/sqrt(Hz)
VIB = 2.0                             # accel vibration amplitude, m/s^2 (motors on)

def truth(t):
    """True roll, pitch, yaw (rad) and earth-frame linear acceleration (NED, m/s^2)."""
    r = p = y = 0.0; acc = (0.0, 0.0, 0.0)
    if 20 <= t < 60:                                  # smooth tilts, little acceleration
        r = math.radians(20) * math.sin(2 * math.pi * 0.2 * (t - 20))
        p = math.radians(15) * math.sin(2 * math.pi * 0.13 * (t - 20))
    elif 60 <= t < 80:                                # sprints: 4 m/s^2 forward/back, 1 s pulses
        a = 4.0 if int(t) % 4 == 0 else (-4.0 if int(t) % 4 == 2 else 0.0)
        p = -math.atan2(a, G); acc = (a, 0.0, 0.0)  # nose down to accelerate forward
    elif 80 <= t < 100:                               # coordinated turn: bank 30 deg, V = 15 m/s
        r = math.radians(30); w = G * math.tan(r) / 15.0
        y = w * (t - 80)
        acc = (-G * math.tan(r) * math.sin(y), G * math.tan(r) * math.cos(y), 0.0)
    return r, p, y, acc

def euler_to_q(r, p, y):
    cr, sr, cp, sp, cy, sy = (math.cos(r / 2), math.sin(r / 2), math.cos(p / 2),
                              math.sin(p / 2), math.cos(y / 2), math.sin(y / 2))
    return [cr*cp*cy + sr*sp*sy, sr*cp*cy - cr*sp*sy, cr*sp*cy + sr*cp*sy, cr*cp*sy - sr*sp*cy]

def qmul(a, b):
    w1, x1, y1, z1 = a; w2, x2, y2, z2 = b
    return [w1*w2 - x1*x2 - y1*y2 - z1*z2, w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2, w1*z2 + x1*y2 - y1*x2 + z1*w2]

def qnorm(q):
    n = math.sqrt(sum(c * c for c in q)); return [c / n for c in q]

def down_body(q):                      # earth "down" (0,0,1) seen in body axes, q = body->earth
    w, x, y, z = q
    return [2*(x*z - w*y), 2*(w*x + y*z), w*w - x*x - y*y + z*z]

def rot_to_body(q, v):                 # earth vector -> body axes (R^T v)
    w, x, y, z = q
    R = [[1-2*(y*y+z*z), 2*(x*y-w*z), 2*(x*z+w*y)],
         [2*(x*y+w*z), 1-2*(x*x+z*z), 2*(y*z-w*x)],
         [2*(x*z-w*y), 2*(y*z+w*x), 1-2*(x*x+y*y)]]
    return [sum(R[i][k] * v[i] for i in range(3)) for k in range(3)]

def integrate(q, g):                   # exact rotation by g*DT, then renormalise
    n = math.sqrt(sum(c * c for c in g))
    if n < 1e-12: return q
    s = math.sin(n * DT / 2) / n
    return qnorm(qmul(q, [math.cos(n * DT / 2), g[0] * s, g[1] * s, g[2] * s]))

def cross(a, b):
    return [a[1]*b[2] - a[2]*b[1], a[2]*b[0] - a[0]*b[2], a[0]*b[1] - a[1]*b[0]]

def make_imu(seed=1):
    rnd = random.Random(seed); out = []
    prev = euler_to_q(*truth(0)[:3])
    for i in range(int(T * FS)):
        t = i * DT
        r, p, y, acc = truth(t)
        q = euler_to_q(r, p, y)
        dq = qmul([prev[0], -prev[1], -prev[2], -prev[3]], q)   # body rate from q(t-dt) -> q(t)
        if dq[0] < 0: dq = [-c for c in dq]
        ang = 2 * math.acos(max(-1.0, min(1.0, dq[0])))
        s = math.sin(ang / 2)
        rate = [0.0, 0.0, 0.0] if s < 1e-12 else [dq[k + 1] / s * ang / DT for k in range(3)]
        prev = q
        gyro = [rate[k] + BIAS[k] + rnd.gauss(0, ARW * math.sqrt(FS)) for k in range(3)]
        f = rot_to_body(q, [acc[0], acc[1], acc[2] - G])        # specific force = a - g (NED)
        vib = VIB * math.sin(2 * math.pi * 117 * t) if t >= 5 else 0.0   # motors spin up at 5 s
        accel = [f[0] + 0.3 * vib + rnd.gauss(0, 0.05), f[1] + 0.3 * vib + rnd.gauss(0, 0.05),
                 f[2] + vib + rnd.gauss(0, 0.05)]
        out.append((t, q, gyro, accel))
    return out

def tilt_err(qt, qe):                  # angle between true and estimated "down", deg
    a, b = down_body(qt), down_body(qe)
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))))

def acc_tilt_q(a):                     # roll/pitch from accelerometer only (yaw = 0)
    r = math.atan2(-a[1], -a[2]); p = math.atan2(a[0], math.hypot(a[1], a[2]))
    return euler_to_q(r, p, 0.0)

def run(imu, kind, kp=0.25, ki=0.0, gate=(0.9, 1.1), beta=0.05, tau=2.0, lpf=25.0):
    q = [1.0, 0, 0, 0]; ib = [0.0, 0.0, 0.0]; rp = [0.0, 0.0]; errs = []; ib60 = None
    k = 1.0 if not lpf else DT / (DT + 1 / (2 * math.pi * lpf * 1.553774))  # PT2 = 2 x PT1
    s1 = list(imu[0][3]); s2 = list(imu[0][3])
    for t, qt, g, a in imu:
        s1 = [s1[i] + k * (a[i] - s1[i]) for i in range(3)]     # accel low-pass, as acc_lpf_hz
        s2 = [s2[i] + k * (s1[i] - s2[i]) for i in range(3)]
        a = s2
        an = math.sqrt(sum(c * c for c in a))
        if kind == "gyro":
            q = integrate(q, g)
        elif kind == "accel":
            q = acc_tilt_q(a)
        elif kind == "compl":          # first-order complementary filter on roll/pitch angles
            alpha = tau / (tau + DT)
            ar = math.atan2(-a[1], -a[2]); ap = math.atan2(a[0], math.hypot(a[1], a[2]))
            rp = [alpha * (rp[0] + g[0] * DT) + (1 - alpha) * ar,
                  alpha * (rp[1] + g[1] * DT) + (1 - alpha) * ap]
            q = euler_to_q(rp[0], rp[1], 0.0)
        elif kind == "mahony":
            use = gate is None or gate[0] * G < an < gate[1] * G
            if use and an > 1e-3:
                e = cross([-c / an for c in a], down_body(q))
                if math.sqrt(sum(c * c for c in g)) < math.radians(20):   # SPIN_RATE_LIMIT
                    ib = [ib[j] + ki * e[j] * DT for j in range(3)]
                g = [g[j] + kp * e[j] + ib[j] for j in range(3)]
            elif ki > 0:
                g = [g[j] + ib[j] for j in range(3)]
            q = integrate(q, g)
        elif kind == "madgwick":       # gradient step on f(q) = down_body(q) - measured down
            w, x, y, z = q
            qd = [0.5 * c for c in qmul(q, [0.0] + list(g))]
            if an > 1e-3:
                m = [-c / an for c in a]; d = down_body(q)
                f = [d[0] - m[0], d[1] - m[1], d[2] - m[2]]
                J = [[-2*y, 2*z, -2*w, 2*x], [2*x, 2*w, 2*z, 2*y], [2*w, -2*x, -2*y, 2*z]]
                s = [sum(J[i][j] * f[i] for i in range(3)) for j in range(4)]
                sn = math.sqrt(sum(c * c for c in s))
                if sn > 1e-12: qd = [qd[j] - beta * s[j] / sn for j in range(4)]
            q = qnorm([q[j] + qd[j] * DT for j in range(4)])
        errs.append((t, tilt_err(qt, q)))
        if ib60 is None and t >= 60: ib60 = list(ib)
    return errs, ib60

def stats(errs, t0, t1):
    e = [v for t, v in errs if t0 <= t < t1]
    return math.sqrt(sum(v * v for v in e) / len(e)), max(e)

SEG = [("hover 0-20", 0, 20), ("tilts 20-60", 20, 60), ("sprint 60-80", 60, 80),
       ("turn 80-100", 80, 100), ("hover 100-120", 100, 120)]

if __name__ == "__main__":
    imu = make_imu()
    print("gimbal lock: Euler-rate factor 1/cos(theta) =",
          ", ".join(f"{d} deg: {1 / math.cos(math.radians(d)):.1f}" for d in (60, 80, 85, 89)))
    print("bias 0.5 deg/s -> yaw/tilt drift", 0.5 * 60, "deg/min; noise only, 120 s:",
          f"{math.degrees(ARW) * math.sqrt(T):.3f} deg (N*sqrt(t))")
    cases = [("gyro only", dict(kind="gyro")),
             ("accel only", dict(kind="accel")),
             ("complementary tau=2s", dict(kind="compl")),
             ("Mahony BF kp=0.25 ki=0", dict(kind="mahony")),
             ("Mahony kp=0.25 ki=0.02", dict(kind="mahony", ki=0.02)),
             ("Mahony kp=0.25 no gate", dict(kind="mahony", gate=None)),
             ("Madgwick beta=0.05", dict(kind="madgwick"))]
    print(f"{'tilt error RMS / max, deg':26s}" + "".join(f"{s[0]:>15s}" for s in SEG))
    res = {}
    for name, kw in cases:
        errs, ib = run(imu, **kw); res[name] = (errs, ib)
        print(f"{name:26s}" + "".join("{:7.2f}/{:<7.2f}".format(*stats(errs, a, b)) for _, a, b in SEG))
    ib = res["Mahony kp=0.25 ki=0.02"][1]
    print("Mahony ki=0.02 bias estimate at t=60 s, deg/s:", [round(-math.degrees(c), 3) for c in ib],
          "true:", [0.5, -0.3, 0.2])
    print("kp sweep (Mahony, gate 0.9-1.1 g, ki=0): kp -> RMS whole flight / max, deg")
    for kp in (0.02, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0):
        e1, _ = run(imu, "mahony", kp=kp)
        e2, _ = run(imu, "mahony", kp=kp, gate=None)
        print(f"  kp={kp:<5} gate: {stats(e1, 0, T)[0]:5.2f}/{stats(e1, 0, T)[1]:5.2f}"
              f"   no gate: {stats(e2, 0, T)[0]:5.2f}/{stats(e2, 0, T)[1]:5.2f}")
```

### Step 2. Run it and read the result
`python3 att_lab.py` (3 s on an ordinary laptop; the seed is fixed, so the numbers reproduce to the last digit). The actual output:

```text
gimbal lock: Euler-rate factor 1/cos(theta) = 60 deg: 2.0, 80 deg: 5.8, 85 deg: 11.5, 89 deg: 57.3
bias 0.5 deg/s -> yaw/tilt drift 30.0 deg/min; noise only, 120 s: 0.055 deg (N*sqrt(t))
tilt error RMS / max, deg      hover 0-20    tilts 20-60   sprint 60-80    turn 80-100  hover 100-120
gyro only                    6.72/11.66    24.06/34.54    40.27/45.81    45.92/47.36    53.17/58.83  
accel only                   0.37/0.95      0.52/1.38     15.70/32.70    30.01/30.76     0.42/0.93   
complementary tau=2s         1.07/1.18      1.20/1.53      4.58/7.95     32.40/35.31     5.44/24.87  
Mahony BF kp=0.25 ki=0       1.95/2.33      2.30/2.39      3.03/4.34      4.02/5.18      2.95/5.08   
Mahony kp=0.25 ki=0.02       1.26/1.64      0.29/0.70      2.16/4.47      2.25/2.79      0.93/2.67   
Mahony kp=0.25 no gate       1.95/2.33      2.30/2.39      3.16/4.69     15.54/18.78     4.75/15.27  
Madgwick beta=0.05           0.11/0.25      0.15/0.32      3.29/6.35     15.43/20.61     1.58/9.74   
Mahony ki=0.02 bias estimate at t=60 s, deg/s: [0.489, -0.296, 0.006] true: [0.5, -0.3, 0.2]
kp sweep (Mahony, gate 0.9-1.1 g, ki=0): kp -> RMS whole flight / max, deg
  kp=0.02  gate: 19.47/26.81   no gate: 17.39/23.34
  kp=0.05  gate: 10.51/13.78   no gate:  8.94/12.27
  kp=0.1   gate:  5.85/ 8.31   no gate:  5.59/11.92
  kp=0.25  gate:  2.84/ 5.18   no gate:  6.93/18.78
  kp=0.5   gate:  2.48/ 7.23   no gate:  9.69/24.44
  kp=1.0   gate:  3.30/12.58   no gate: 11.60/27.89
  kp=2.5   gate:  4.81/19.74   no gate: 12.94/29.57
  kp=5.0   gate:  5.65/21.95   no gate: 13.41/29.91
  kp=10.0  gate:  6.07/22.31   no gate: 13.62/30.05
```

How to read the table. The "gyro only" row is pure drift: 11.7° by second 20, 59° by the end (bias × time up to the turn; the turn rotates the accumulated error about the vertical, which is why it is not 0.583 × 120 = 70°). "accel only" is the most accurate in hover (0.37°), but during acceleration it is off by 22° (exactly atan(4/9.81); the 33° peak in the table is a transient sample at second 60, where the model jumps pitch from +14° to −22°), and in the turn it shows 30° of error, exactly the bank angle, because to an accelerometer a coordinated turn is indistinguishable from level. "Mahony BF" (Kp = 0.25, Ki = 0, the 0.9–1.1 g gate, as in Betaflight) keeps the error at 2–5° in every phase; the constant 1.95–2.33° in hover is b/Kp. The same filter without the gate is off by 18.8° in the turn: the 1.155 g magnitude passes unchecked. Ki = 0.02 removes the constant error (0.29° on the tilts) and finds the X and Y bias.

### Step 3. Check against the theory formulas
Compute by hand and compare with the output:
- the constant Mahony error without Ki: e = b/Kp, b = √(0.5² + 0.3²) = 0.583 °/s = 0.01018 rad/s; 0.01018 / 0.25 = 0.0407 rad = **2.33°**, and the hover maximum over 0–20 s in the output is 2.33;
- the constant error of the complementary filter on angles: e = b·τ = 0.583 × 2 = **1.17°**; the output maximum is 1.18;
- the false tilt during acceleration: atan(4/9.81) = **22.2°**, |f| = 1.08 g, inside the 0.9–1.1 window, so the Betaflight gate lets the acceleration through; the turn gives 1/cos 30° = **1.155 g**, outside the window, so it is rejected;
- gyro-only drift over 20 s: 0.583 × 20 = **11.7°**; the output maximum is 11.66.

### Step 4. Experiments
Change one argument at a time in `cases` and record the RMS in a table:
- Ki = 0 and Kp = 0: gyro only, drift like the "gyro only" row.
- Kp = 5: the accelerometer "pulls" during maneuvers; RMS over the flight is 5.65° against 2.84° at 0.25 (the kp sweep rows).
- `lpf=None`: remove the accelerometer filter; the 2 m/s² vibration knocks |a| out of the 0.9–1.1 g window, and the correction works only intermittently.
- `BIAS = [0.0, 0.0, 0.0]`: the constant Mahony error in hover should drop almost to zero; that is how gyro calibration at power-on works.

### Moving to real hardware
Props off for every step except the flight recording; fly in an open area, in Angle/Stabilize, for 2–3 minutes with tilts and hover.

**1. Recording the IMU.** ArduPilot: a log with `IMU` (gyro, accel) and `ATT`; `LOG_BITMASK` with IMU_RAW is not needed, 50–400 Hz IMU is enough (a course guideline). Betaflight 2025.12: the `imuQuaternion` field in the normal log (or `debug_mode = ATTITUDE` for angles) plus gyro and acc. Keep the vehicle still for 5 s after power-on, otherwise the gyro calibration will record the rotation as bias.
**2. Your own filter on the recording.** For arrays from a log, the same logic in numpy is convenient:

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
Run it on your recording; plot roll/pitch against `ATT.Roll/Pitch` (ArduPilot) or the angles from the debug log. Compute the RMS difference in roll and pitch.
**3. kp and ki.** Increase `kp` by a factor of 10 and the estimate starts jittering with the accelerometer vibration. Reduce it by a factor of 10 and it slowly creeps away with gyro drift. This is the same curve as the kp sweep in step 2.
**4. Yaw.** Integrate gyro Z without correction and record the drift over a minute; compare with `ATT.Yaw`. Estimate the bias from a still segment of the log (the mean of gyro Z over 5 s) and compute the expected drift over the flight: bias × time.

Hardware criteria: in hover and smooth tilts the RMS difference from `ATT.Roll`/`ATT.Pitch` is a few degrees, with no systematic drift; the drift of the gyro Z integral over a minute matches bias × 60 s within 30% (both thresholds are course guidelines). Stop the experiment if in Angle the OSD horizon differs from the real one by more than 5° on the ground (a course guideline); calibrate the accelerometer first (`est-sensors`).

Self-check: the lab is done when (calculation path) `att_lab.py` produced output matching the one above to the hundredths, and the four hand checks in step 3 agree with it: 2.33°, 1.17° (against 1.18), 22.2° and 1.155 g, 11.7°; in the step 4 experiment with `BIAS = [0.0, 0.0, 0.0]` the Mahony hover error dropped below 0.5°; (hardware) the RMS difference between your filter and `ATT` is a few degrees in hover and smooth tilts, and the yaw drift over a minute matched bias × 60 s within 30%.

**Reference for the self-check.** The key output numbers: Mahony as in Betaflight, 1.95/2.33° in hover and 4.02/5.18° in the turn; without the magnitude gate, 15.54/18.78° in the turn; Ki = 0.02 finds the bias [0.489, −0.296, 0.006] against the true [0.5, −0.3, 0.2], so Z is unobservable; the kp sweep minimum with the gate is Kp 0.25–0.5 (2.84 and 2.48°). Common wrong results: roll or pitch mirrors the truth or diverges by tens of degrees at once, which means the gyro was fed in °/s instead of rad/s or the accelerometer lacks the minus sign (FRD, −g at rest); "gyro only" does not drift, which means the bias was not added or was overwritten; Mahony without Ki gives 0° in hover instead of 2.33°, which means BIAS is zeroed, and then it is not a mistake but the step 4 experiment.

## diagnostics
- **Symptom:** the OSD horizon drifts off after hard maneuvers and slowly comes back
  - Possible cause: the gyro accumulated error and Kp is small, so recovery is slow (τ ≈ 1/Kp: 4 s with the Betaflight default).
  - What to do: normal for Acro; for Angle, raise Kp moderately and check vibration.
- **Symptom:** after power-on the Betaflight horizon is tilted and straightens out over a few seconds
  - Possible cause: the vehicle was moved during gyro calibration, so the bias was recorded wrong; before arming Kp is ×10, so the estimate converges, but in flight the b/Kp error remains.
  - What to do: power-cycle with the vehicle still; check `small_angle` (25°): arming is blocked at a larger tilt.
- **Symptom:** in a long turn without GPS a wing's horizon "floats up" toward zero bank
  - Possible cause: a coordinated turn; the accelerometer sees 1/cos φ g along the Z axis and shows level.
  - What to do: GPS acceleration compensation (`AHRS_GPS_GAIN` in DCM, EKF3 with GPS; in INAV, `ahrs_inertia_comp_method`); do not fly by the horizon without GPS for longer than the filter's time constant.
- **Symptom:** Loiter moves in a spiral, the OSD heading does not match the real one
  - Possible cause: yaw drift or a bad compass.
  - What to do: compass, GPS yaw, GSF; check for interference.
- **Symptom:** your filter differs from ATT by 5–10° during maneuvers
  - Possible cause: no compensation for centripetal acceleration.
  - What to do: add a GPS-velocity correction or reduce trust in the accel when |a| ≠ g.
- **Symptom:** your filter with Ki drifts off by tens of degrees after a minute of flight
  - Possible cause: the integrator accumulates false error during maneuvers (windup).
  - What to do: do not integrate during rotation faster than 20 °/s or with |a| outside the window, as in Betaflight and DCM; limit ∫e.
- **Symptom:** NaN in the quaternion
  - Possible cause: a missed normalization, or acc = 0.
  - What to do: check norms, guard the divisions.

## references
- Betaflight 2025.12.5 — `src/main/flight/imu.c` (Mahony, `imu_dcm_kp/ki`, the 0.9–1.1 g window, the Kp boost before arming) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/flight/imu.c | primary | A
- ArduPilot Copter-4.7.3 — `libraries/AP_AHRS/AP_AHRS_DCM.cpp` (DCM, Ki, SPIN_RATE_LIMIT, GPS course) | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.3/libraries/AP_AHRS/AP_AHRS_DCM.cpp | primary | A
- PX4 v1.18.0 — `attitude_estimator_q_params.yaml` (ATT_EN, weights) | https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.18.0/src/modules/attitude_estimator_q/attitude_estimator_q_params.yaml | primary | A
- INAV 9.1.0 — `src/main/fc/settings.yaml` (ahrs_dcm_kp/ki, ahrs_acc_ignore_rate) | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/fc/settings.yaml | primary | A
- ArduPilot — EKF (Extended Kalman Filter) overview | https://ardupilot.org/copter/docs/common-apm-navigation-extended-kalman-filter-overview.html | primary | A
- PX4 — Using the ECL EKF (attitude/state estimation) | https://docs.px4.io/v1.17/en/advanced_config/tuning_the_ecl_ekf.html | primary | A
- Mahony et al., "Nonlinear Complementary Filters on the Special Orthogonal Group" (IEEE TAC 2008), the original algorithm | https://hal.archives-ouvertes.fr/hal-00488376 | primary | A
- `ahrs` 0.4.0 (Python): Mahony and Madgwick implementations with formulas, β = √(3/4)·ω̄_β | https://pypi.org/project/AHRS/ | secondary | B

## checklist
- I can explain gimbal lock with a number: 1/cos θ = 11.5 at 85°
- I understand how the complementary filter's Kp/Ki split trust between gyro and accelerometer, and I can compute the b/Kp error
- I know the three ways the accelerometer lies: acceleration, coordinated turn, vibration
- I know what runs in Betaflight, INAV, ArduPilot and PX4, and their defaults
- I implemented a filter, ran the model and compared it with ATT from the log
- I know where yaw comes from and why Ki does not find the Z bias
