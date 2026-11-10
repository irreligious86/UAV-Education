---
id: est-kalman
title: "The Kalman Filter, Plainly Explained, and EKF"
level: L3
readingTime: 40 min
firmware: ArduPilot · PX4
status: published
added: 2026-11-08
tags:
  - Kalman filter
  - EKF
  - innovations
  - covariance
related:
  - est-attitude
  - ap-ekf
  - data-python
next:
  - est-gnss
source: content/estimation/est-kalman.md
source_hash: 91ce4504afc9
---

## summary
EKF3 in ArduPilot and EKF2 in PX4 are the same trick repeated for 24 states. This module explains it in one dimension: prediction from the model, correction from the measurement, covariance as “how unsure I am,” the Kalman gain as the compromise between the two, and the innovation as the “expected vs. observed” difference. You implement a 1D altitude filter from barometer and accelerometer (~30 lines), see what it does when the barometer produces an outlier, and how this looks in the log: `XKF4.SV/SP/SH/SM` (normalized innovations), `XKF3` (innovations), `XKF1/XKF2` (states, bias).

## theory
### The problem
You have a motion model (how the state evolves on its own) and measurements (noisy, sometimes infrequent). You want a state estimate better than either of the two alone, plus an honest estimate of its uncertainty.

### One Kalman step (scalar)
State x (e.g., altitude), uncertainty P (variance of the estimate).
1. **Prediction**: x⁻ = f(x) (from the model: x + v·Δt), P⁻ = P + Q, where Q is the process noise (“how wrong the model can be over one step”).
2. **Innovation**: y = z − h(x⁻) — the measurement minus what you expected. S = P⁻ + R is its variance (R is the measurement noise).
3. **Gain**: K = P⁻ / S ∈ (0, 1). If the measurement is accurate (small R), K → 1 and you trust the measurement; if the model is accurate (small P⁻), K → 0 and you ignore the measurement.
4. **Correction**: x = x⁻ + K·y, P = (1 − K)·P⁻.

Everything else is the same scheme with vectors and matrices: P is the covariance matrix, H describes how the state turns into a measurement, K = P Hᵀ (H P Hᵀ + R)⁻¹. **Extended** (EKF) means the model is nonlinear (rotations via a quaternion), and it is linearized around the current point (Jacobians).

### Worked example: two steps by hand
Altitude is unknown: x = 0 m, P = 4 m² (σ = 2 m — “roughly, give or take two meters”). The barometer has noise R = 1 m².
1. A reading z = 10 m arrives. Prediction with no motion: x⁻ = 0, P⁻ = 4 (Q = 0). S = 4 + 1 = 5, K = 4/5 = 0.8. Innovation y = 10. x = 0 + 0.8·10 = **8 m**, P = 0.2·4 = **0.8 m²**. The measurement is four times more precise than our guess — and it got 80 % of the weight.
2. One step passes, and the model allows drift Q = 0.1: P⁻ = 0.9. A reading z = 9 m arrives: S = 1.9, K = 0.47, y = 1, x = 8 + 0.47 = **8.47 m**, P = 0.53·0.9 = **0.47 m²**.

The point: K dropped from 0.8 to 0.47 on its own, because the estimate got more precise. After a dozen measurements K will be ~0.1–0.3 and stop falling: Q “pumps up” the uncertainty every step, R keeps it from reaching zero, and an equilibrium sets in. That is exactly what the chart below shows.

### Q and R: what they mean and how to tune them
- **R** is the rated measurement noise: barometer variance at rest, the σ² of GPS position (grows with HDOP). You can **measure** it: log on the ground, take the signal variance.
- **Q** is how far reality can drift from the model in one step: unmodeled accelerations, bias drift. You **cannot measure it directly** — it is a tuning knob.
- Q too small → the filter is “overconfident”: K is small, the estimate lags behind maneuvers, innovations are systematically large, and if the gates are narrow, measurements start getting rejected and the filter diverges.
- Q too large → the filter is “jittery”: K is close to 1, the estimate repeats the measurement noise, and the model is pointless.
- Honesty check: the normalized innovation y/√S should be ~N(0, 1), i.e., its square should average ≈ 1 (the NIS test). A mean of 5 means the filter underestimates its uncertainty (Q or R too small); 0.1 means it overestimates it.

### Observability: what the filter can learn at all
You can only estimate what affects the measurements. The Z accelerometer bias is visible because the baro “catches” the altitude drift. Heading without a compass is unobservable in a hover: GPS velocity is zero, and you can turn 180° — the measurements are the same. That is why ArduPilot runs a separate heading estimator based on GPS velocity in motion (GSF), and with `COMPASS_USE = 0` the EKF waits for the vehicle to pick up speed. Rule of thumb: if a state is unobservable, its P grows, and you see it in the log before you see it in flight.

### Delays: the filter lives in the past
GPS arrives with a 100–200 ms delay, and so do optical flow and external navigation. EKF3 and EKF2 therefore run the filter on a “delayed time horizon”: a measurement is fused with the state at the moment it was taken, and for the control loops the current state is propagated forward using the IMU (output predictor). A wrong delay (`GPS1_DELAY_MS`, `EK3_FLOW_DELAY`) is the classic reason innovations grow during maneuvers and drop in a hover.

### Why this beats a complementary filter
A complementary filter is a Kalman filter with a fixed K. A real Kalman filter adjusts K itself: when GPS gives bad data (large R from HDOP), trust drops; when there have been no measurements for a while, P grows and the very first measurement is accepted with a large weight. And it estimates **sensor biases** as states — what Ki does blindly in a complementary filter.

### Innovations and gates
An innovation y with variance S gives the normalized quantity y²/S. In ArduPilot, `XKF4.SV/SP/SH/SM` (velocity, position, height, compass) are the square root of the test ratio, i.e., the ratio “innovation / maximum allowed innovation” itself, where the allowance is set by the gates (`EK3_VEL_I_GATE`, `EK3_HGT_I_GATE`, `EK3_MAG_I_GATE`, in percent of σ): < 1 — the measurement is accepted, > 1 — it is **rejected**. A healthy flight shows values < 0.5. This is protection against GPS and compass outliers: one bad sample won't break the estimate. But if measurements are consistently outside the gates, the filter “drifts away” on the model until it resets (lane switch, reset, EKF failsafe).

### What's in the EKF3 state vector
24 states: quaternion (4), NED velocity (3), NED position (3), gyro bias (3), accelerometer bias (3), Earth field NED (3), body field (3), NE wind (2). Measurements: GPS position/velocity, baro, compass, airspeed, rangefinder, optical flow, external navigation, beacons, wheel encoders. Several **cores (lanes)** — one per IMU; the active one is chosen by the lowest error (`XKF4.PI`, `NKF`→`XKF`).

{{diagram:estimation-sources|EKF3 inputs and outputs: what the filter takes from the sensors and what it hands to the control loops.}}

### Parameters worth touching
`EK3_GPS_CHECK`, `EK3_*_NOISE` (R per source), `EK3_*_I_GATE`, `EK3_ACC_P_NSE/GYRO_P_NSE` (Q), `EK3_SRCn_*` (sources). Everything else — after reading the code and the logs, not before.

{{diagram:chart-kalman-1d|Kalman filter on a constant value: the first measurements move the estimate right away (K close to 1), then the gain drops, the estimate settles, and the ±√P band narrows. Q = 0: the model is certain the value does not change.}}

{{widget:kalman-1d}}

## practice
### Step 1. A 1D altitude filter
State: [h, v, b] — altitude, vertical velocity, accelerometer bias. Model: h += v·dt, v += (a − b)·dt. Measurement: baro h_b with R = 0.3² m².

```python
import numpy as np
def kf_alt(acc_z, baro, dt, q_acc=0.5, r_baro=0.3**2, q_bias=1e-4):
    """1D altitude filter: state [h, v, accel_bias]; predict with accel, correct with baro."""
    x = np.array([baro[0], 0.0, 0.0]); P = np.diag([1.0, 1.0, 0.1]); h = np.array([1.0, 0, 0])
    F = np.array([[1, dt, -0.5*dt*dt], [0, 1, -dt], [0, 0, 1]]); B = np.array([0.5*dt*dt, dt, 0])
    Q = np.diag([0, (q_acc*dt)**2, q_bias*dt]); out = []; innov = []
    for a, z in zip(acc_z, baro):
        x = F @ x + B * a; P = F @ P @ F.T + Q                        # predict
        y = z - h @ x; S = h @ P @ h + r_baro                         # innovation and its variance
        if y * y / S < 9:                                             # 3-sigma gate
            K = P @ h / S; x = x + K * y; P = (np.eye(3) - np.outer(K, h)) @ P
        out.append(x.copy()); innov.append(y / np.sqrt(S))
    return np.array(out), np.array(innov)
```
Generate the ground truth (climb at 2 m/s, hover, descent), accel with a 0.2 m/s² bias and noise, baro with 0.3 m noise. Check: the h estimate is smoothed, v is close to the truth, b converges to 0.2.

```python
dt, n = 0.01, 6000                                   # 100 Hz, 60 s
t = np.arange(n) * dt
v_true = np.where(t < 10, 2.0, np.where(t < 40, 0.0, -1.0))
h_true = np.cumsum(v_true) * dt
a_true = np.gradient(v_true, dt)
rng = np.random.default_rng(0)
acc = a_true + 0.2 + rng.normal(0, 0.3, n)           # accel bias 0.2 m/s^2
baro = h_true + rng.normal(0, 0.3, n)
est, nu = kf_alt(acc, baro, dt)
print("bias:", est[-1, 2].round(3), "RMS h error:", np.sqrt(np.mean((est[:, 0] - h_true) ** 2)).round(3),
      "NIS mean:", np.mean(nu ** 2).round(2))
```
Expected: bias around 0.2 by the end of the flight, altitude error noticeably smaller than the 0.3 m baro noise, mean NIS around 1.

### Step 1b. The Q and R knobs
Run the same signal with `q_acc` ×10 and ×0.1, then with `r_baro` ×10. Record in a table: RMS h error, estimate lag at the start of the climb (how many ms until the v estimate reaches 1.8 m/s), mean NIS. Sum up in one line what each knob does — this is exactly what `EK3_ACC_P_NSE` and `EK3_ALT_M_NSE` do.

### Step 2. A barometer outlier
Insert a +5 m step lasting 1 s (prop wash/a door): without gates the estimate jumps; with gates the measurement is rejected, the normalized innovation is > 3, and the estimate follows the accelerometer. Make the step long (10 s): the filter eventually “gives up” — and that's how it should be (gates don't save you from a systematic error).

### Step 3. Connecting to the log
Take an ArduPilot log: `XKF4.SH` (normalized height innovation) and `XKF3.IPD` (position innovation, D) during takeoff/landing; `XKF2.AZ` is the accel Z bias estimate. Compare with what your own filter did. Lab: filter implemented, outlier shown, Q/R table filled in, XKF messages explained.

## diagnostics
- **Symptom:** `XKF4.SH` > 1 on takeoff
  - Possible cause: baro in the prop wash/airflow; the configured R (`EK3_ALT_M_NSE`) is too small to cover this error.
  - What to do: cover the baro with foam, `EK3_ALT_M_NSE`, a rangefinder as the height source near the ground.
- **Symptom:** position innovations grow, then “EKF variance” and a failsafe
  - Possible cause: GPS glitch/multipath, or the compass is lying and the model drifts off.
  - What to do: `GPS.NSats/HDOP`, `XKF4.SM`; EKF sources, GPS check.
- **Symptom:** your own filter diverges (P grows without bound)
  - Possible cause: all measurements are rejected by the gates after a systematic error.
  - What to do: temporarily widen the gates / reset to the measurement on a prolonged failure (like an EKF reset).
- **Symptom:** a lane switch in the log
  - Possible cause: one IMU is noisier (vibration) — the core using it accumulated error.
  - What to do: mechanics, check the IMU; fine if it's rare.

## references
- ArduPilot — EKF overview and lanes | https://ardupilot.org/copter/docs/common-apm-navigation-extended-kalman-filter-overview.html | primary | A
- ArduPilot — EKF3 source (AP_NavEKF3, state vector and fusion) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/AP_NavEKF3 | primary | A
- PX4 — ECL EKF tuning (innovations, gates, noise parameters) | https://docs.px4.io/main/en/advanced_config/tuning_the_ecl_ekf.html | primary | A
- Welch, Bishop — An Introduction to the Kalman Filter (UNC TR 95-041) | https://www.cs.unc.edu/~welch/media/pdf/kalman_intro.pdf | secondary | A
- R. Labbe — Kalman and Bayesian Filters in Python (open book, notebooks) | https://github.com/rlabbe/Kalman-and-Bayesian-Filters-in-Python | secondary | A

## checklist
- I can explain prediction, innovation, gain and correction
- I understand that covariance is a measure of uncertainty and K is a compromise
- I can compute a Kalman step by hand and explain what Q and R do
- I check filter honesty using normalized innovations (NIS)
- I understand observability and the EKF's delayed time horizon
- I implemented a 1D altitude filter with gates
- I showed the behavior on a short and a long baro outlier
- I can read XKF1–XKF4 in a log and understand what's there
