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
source_hash: bc09a4c0a4b6
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
3. The error is the cross product e = (−a/|a|) × v (small when they agree; its direction is the correction axis).
4. Correct the angular rate: ω' = ω + Kp·e + Ki·∫e (Ki is the gyro bias estimate!).
5. Integrate ω' into q.

Kp sets the time constant of “trust” in the accelerometer: τ ≈ 1/Kp; Kp = 0.5 → ~2 s. During maneuvers |a| ≠ 1 g — the accelerometer lies; the standard protection is to reduce Kp when | |a| − g | is large (ArduPilot DCM: `AHRS_GPS_GAIN`, using GPS for centripetal correction; Betaflight: `imu_dcm_kp`, disabling correction under large accelerations). The compass is added the same way for the yaw axis: the error between the measured and expected direction of the field's horizontal component.

{{diagram:chart-attitude-kp-sweep|Ошибка оценки наклона имеет минимум по Kp: слева её делает дрейф гироскопа (ошибка b/Kp), справа — доверие ложному «низу» при разгоне; защита по модулю |a| сдвигает минимум с 0.1 к 0.25–0.5 и вдвое уменьшает ошибку.}}

### What this is in firmware
- **Betaflight**: a Mahony-like quaternion filter, `imu_dcm_kp` (default 2500 → 0.25 after scaling), `imu_dcm_ki`; without a compass yaw drifts — irrelevant for Acro, and GPS Rescue uses the GPS course.
- **INAV**: the same class of filter + compass and GPS course, corrections that account for acceleration from GPS.
- **ArduPilot**: DCM (a matrix, with correction from GPS velocity) as the fallback; the primary one is **EKF3**, where attitude is part of the state vector together with velocity, position and sensor biases. A complementary filter is an EKF with constant, non-adaptive gains.
- **PX4**: EKF2 (`ekf2`), attitude in `vehicle_attitude`.

### Why yaw is special
Gravity carries no information about heading: without a compass or GPS course, yaw drifts with the gyro Z bias. In a hover that's ~3°/min, unnoticeable; over 10 minutes it's 30°, and Loiter will spiral (the “toilet bowl” is the classic symptom). Yaw sources: compass (interference), GPS course while moving (not in a hover), dual GPS (moving baseline), EKF-GSF (estimation from motion, ArduPilot `EK3_SRC1_YAW = 8`), external navigation.

{{diagram:complementary-filter|Complementary filter: the gyro integral is accurate over a short interval, the accelerometer angle over a long one; the weights α and 1 − α blend them.}}

{{diagram:attitude-mahony-loop|Цикл Mahony в Betaflight: гироскоп интегрируется всегда, а поправка Kp·e от акселерометра включается только после фильтра 25 Гц и проверки 0.9–1.1 g; Ki в Betaflight по умолчанию 0.}}

## practice

Calculation lab (no hardware): `att_lab.py` simulates 120 s of IMU data with gyro bias, noise, vibration, sprints and a coordinated turn and compares five estimators. The script and its real output:

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
