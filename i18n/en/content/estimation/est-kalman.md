---
id: est-kalman
title: "The Kalman filter made simple, and the EKF"
level: L3
readingTime: 40 min
firmware: ArduPilot 4.7 (checked against 4.7.3) · PX4 1.18 (checked against v1.18.0)
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
source_hash: 652cf47ab776
---

## summary
EKF3 in ArduPilot and EKF2 in PX4 are the same technique repeated for 24 states. This module explains it in one dimension: prediction from a model, correction from a measurement, covariance as "how unsure am I," the Kalman gain as the trade-off between them, and the innovation as the "expected versus observed" difference. You implement a 1D altitude filter from a barometer and an accelerometer (~30 lines), see what it does with a baro outlier, and how this looks in the log: `XKF4.SV/SP/SH/SM` (normalized innovations), `XKF3` (innovations), `XKF1/XKF2` (states, bias).

{{lesson:ap-ahrs-choice|How this filter lives inside ArduPilot: a lane per IMU, innovation gates, source sets and the DCM backup, with real SITL logs.}}

## theory
### The problem
You have a motion model (how the state evolves on its own) and measurements (noisy, sometimes infrequent). You want a state estimate better than either one alone, plus an honest estimate of its uncertainty.

### One Kalman step (scalar)
State x (for example, altitude), uncertainty P (the variance of the estimate).
1. **Prediction**: x⁻ = f(x) (from the model: x + v·Δt), P⁻ = P + Q, where Q is the process noise ("how wrong the model can be over one step").
2. **Innovation**: y = z − h(x⁻), the measurement minus what you expected. S = P⁻ + R is its variance (R is the measurement noise).
3. **Gain**: K = P⁻ / S ∈ (0, 1). If the measurement is precise (small R), K → 1 and you trust the measurement; if the model is precise (small P⁻), K → 0 and you ignore the measurement.
4. **Correction**: x = x⁻ + K·y, P = (1 − K)·P⁻.

Everything else is the same scheme with vectors and matrices: P is the covariance matrix, H describes how the state becomes a measurement, K = P Hᵀ (H P Hᵀ + R)⁻¹. **Extended** (EKF) means the model is nonlinear (rotations through a quaternion), and it is linearized around the current point (Jacobians).

### Worked example: two steps by hand
The altitude is unknown: x = 0 m, P = 4 m² (σ = 2 m, "roughly, give or take two meters"). The barometer noise is R = 1 m².
1. A measurement z = 10 m arrives. Prediction without motion: x⁻ = 0, P⁻ = 4 (Q = 0). S = 4 + 1 = 5, K = 4/5 = 0.8. Innovation y = 10. x = 0 + 0.8·10 = **8 m**, P = 0.2·4 = **0.8 m²**. The measurement is four times more precise than our guess, and it got 80% of the weight.
2. A step passes, and the model allows a drift of Q = 0.1: P⁻ = 0.9. A measurement z = 9 m arrives: S = 1.9, K = 0.47, y = 1, x = 8 + 0.47 = **8.47 m**, P = 0.53·0.9 = **0.47 m²**.

The point: K dropped from 0.8 to 0.47 by itself, because the estimate became more precise. After a dozen measurements K will be ~0.1–0.3 and will stop falling: Q "pumps up" the uncertainty every step and R keeps it from reaching zero, so an equilibrium sets in. You can see this in the chart below.

### Q and R: what they mean and how to tune them
- **R** is the rated measurement noise: the barometer variance at rest, the σ² of the GPS position (it grows with HDOP). You can **measure** it: log on the ground, take the signal variance.
- **Q** is how far reality can depart from the model in one step: unmodeled accelerations, bias drift. You **cannot measure it directly**; it is a tuning knob.
- Q too small → the filter is "overconfident": K is small. This does harm when the model really is wrong by more than Q promises (an acceleration missing from the model input, a bias jump, vibration): the estimate lags reality, the innovations are systematically of one sign and NIS is above 1, and if the gates are narrow, measurements start being rejected and the filter diverges. As long as the model is accurate, an underestimated Q gives no sign of itself; the estimate is even a little smoother. That is why Q is checked during a maneuver or a disturbance, not on a quiet segment.
- Q too large → the filter is "nervous": K is close to 1, the estimate repeats the measurement noise, and the model adds nothing.
- The honesty check: the normalized innovation y/√S should be ~N(0, 1), so its square averages ≈ 1 (the NIS test). A mean of 5 means the filter underestimates its uncertainty (Q or R too small); 0.1 means it overestimates it.

### Observability: what the filter can learn at all
You can estimate only what affects the measurements. The Z accelerometer bias is visible because the baro "catches" the altitude drift. Heading without a compass is unobservable in hover: GPS velocity is zero, and you can turn 180° with the same measurements. That is why ArduPilot runs a separate heading estimator from GPS velocity during motion (GSF), and with `COMPASS_USE = 0` the EKF waits until the vehicle accelerates. The practical rule: if a state is unobservable, its P grows, and you see it in the log before you see it in flight.

### Delays: the filter lives in the past
GPS arrives with a delay of 100–200 ms, and so do optical flow and external navigation. EKF3 and EKF2 therefore run the filter on a "delayed time horizon": a measurement is fused with the state at the moment it was taken, and for the control loops the current state is predicted forward from the IMU (the output predictor). A wrong delay (`GPS1_DELAY_MS`, `EK3_FLOW_DELAY`) is the classic reason why innovations grow during maneuvers and drop in hover.

### Why this beats a complementary filter
A complementary filter is a Kalman filter with a fixed K. A real Kalman filter adjusts K by itself: when GPS gives poor data (a large R from HDOP), trust drops; when there have been no measurements for a while, P grows and the first measurement is taken with a large weight. And it estimates **sensor biases** as states, the job that Ki does blindly in a complementary filter.

### Innovations and gates
An innovation y with variance S gives the normalized quantity y²/S. In ArduPilot, `XKF4.SV/SP/SH/SM` (velocity, position, height, compass) are the square root of the test ratio, that is, the ratio "innovation / largest allowed innovation" itself, where the allowance is set by the gates (`EK3_VEL_I_GATE`, `EK3_HGT_I_GATE`, `EK3_MAG_I_GATE`, as a percentage of σ): < 1 means the measurement is accepted, > 1 means it is **rejected**. A healthy flight shows values < 0.5. This protects against GPS and compass outliers: one bad sample will not break the estimate. But if measurements stay outside the gates, the filter "drifts off" on the model until it resets (a lane switch, a reset, an EKF failsafe).

### What is in the EKF3 state vector
24 states: quaternion (4), NED velocity (3), NED position (3), gyro bias (3), accelerometer bias (3), earth magnetic field NED (3), body magnetic field (3), NE wind (2). Measurements: GPS position/velocity, baro, compass, airspeed, rangefinder, optical flow, external navigation, beacons, wheel encoders. Several **cores (lanes)**, one per IMU; the active one is chosen by the smallest error (`XKF4.PI`, `NKF`→`XKF`).

{{diagram:estimation-sources|EKF3 inputs and outputs: what the filter takes from the sensors and what it gives to the control loops.}}

### Parameters worth touching
`EK3_GPS_CHECK`, `EK3_*_M_NSE` (R per source), `EK3_*_I_GATE`, `EK3_ACC_P_NSE/GYRO_P_NSE` (Q), `EK3_SRCn_*` (sources). Everything else only after reading the code and the logs, not before.

{{diagram:chart-kalman-1d|A Kalman filter on a constant value: the first measurements move the estimate at once (K close to 1), then the gain falls, the estimate settles and the ±√P band narrows. Q = 0: the model is sure the value does not change.}}

{{widget:kalman-1d}}

### Where it fits

- **Receives:** IMU readings for the prediction step (`est-sensors`); GPS measurements with an accuracy estimate and delay (`est-gnss`); baro, rangefinder and flow (`est-alt-sources`); the language of variances and covariances (`math-prob-est`).
- **Provides:** the estimate of attitude, velocity, position and sensor biases to the control loops; the `XKF4` normalized innovations to filter health diagnostics (`ap-ekf`) and the EKF failsafe (`ap-safety-fs`).
- **If you get this wrong:** a wrong measurement delay (`GPS1_DELAY_MS`, `EK3_FLOW_DELAY`) → innovations grow during maneuvers and drop in hover, and measurements fall outside the gates (`ap-ekf`). Measurements staying outside the gates because of compass or GPS interference → the filter drifts off on the model until a reset or an EKF failsafe: a landing where nobody expected it (`nav-resilience`, `ap-safety-fs`).

## practice
### Step 1. A 1D altitude filter
State: [h, v, b], altitude, vertical velocity, accelerometer bias. Model: h += v·dt, v += (a − b)·dt. Measurement: baro h_b with R = 0.3² m².

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
Generate the truth (climb at 2 m/s, hover, descend), an accel with a 0.2 m/s² bias and noise, and a baro with 0.3 m noise. Check: the h estimate is smoothed, v is close to the truth, b converges to 0.2. The `make` generator can do one more thing you will need in step 1b: from second 20 it adds a `bias_step` jump to the accelerometer readings that the filter model knows nothing about. `report` runs the filter and prints the numbers for the whole flight and separately for the 20–30 s window.

```python
def make(bias_step=0.0, seed=0, dt=0.01, n=6000):
    """Truth and sensors, 100 Hz, 60 s: climb 2 m/s, hover, descend. Accel bias 0.2 m/s^2 (+ bias_step from t = 20 s)."""
    t = np.arange(n) * dt
    v_true = np.where(t < 10, 2.0, np.where(t < 40, 0.0, -1.0))
    h_true = np.cumsum(v_true) * dt
    a_true = np.gradient(v_true, dt)
    rng = np.random.default_rng(seed)
    acc = a_true + 0.2 + rng.normal(0, 0.3, n) + bias_step * (t >= 20)
    baro = h_true + rng.normal(0, 0.3, n)
    return t, h_true, acc, baro

def report(bias_step=0.0, **kw):
    """Run the filter; print whole-flight numbers, then the numbers of the 20..30 s window."""
    t, h_true, acc, baro = make(bias_step)
    est, nu = kf_alt(acc, baro, 0.01, **kw)
    err = est[:, 0] - h_true; w = (t >= 20) & (t < 30)
    print("bias:", est[-1, 2].round(3), "RMS h error:", np.sqrt(np.mean(err ** 2)).round(3),
          "NIS mean:", np.mean(nu ** 2).round(2),
          "| 20-30 s: mean error:", err[w].mean().round(3), "max |error|:", np.abs(err[w]).max().round(2),
          "NIS mean:", np.mean(nu[w] ** 2).round(2), "rejected:", int(np.sum(nu[w] ** 2 >= 9)))

report()
```
Expected: a bias of about 0.2 by the end of the flight, an altitude error well below the 0.3 m baro noise, a mean NIS of about 1. With `seed=0` it prints `bias: 0.202 RMS h error: 0.044 NIS mean: 1.0 | 20-30 s: mean error: 0.014 max |error|: 0.1 NIS mean: 0.95 rejected: 1`.

### Step 1b. The Q and R knobs
Four settings: the baseline `report()`, `report(q_acc=5)` (×10), `report(q_acc=0.05)` (×0.1), `report(r_baro=0.9)` (×10). Run each on three signals: quiet (`bias_step` not set), with an accelerometer error jump `bias_step=0.5`, and with a jump `bias_step=1.0`, for example `report(0.5, q_acc=0.05)`. The jump is a model error, exactly what Q is supposed to cover: from second 20 the accelerometer reads 0.5 or 1 m/s² high (this is what vibration after a change in motor regime or sensor warm-up does), while the filter expects only slow drift from the bias (`q_bias`).

On the quiet signal the model is almost exact: the accelerometer measures the maneuvers itself, so little depends on `q_acc` there, and the time for the v estimate to reach 1.8 m/s is the same (0.21 s) for any `q_acc`; this metric does not distinguish the Q knob. Three numbers in the 20–30 s window, right after the jump, do: the mean h error (the systematic lag of the estimate, in meters), the maximum |error| and the mean NIS. For an honest filter the mean NIS over the window's 1000 samples lies within 1 ± 0.09 (95%), and over the whole flight (6000 samples) within 1 ± 0.04. The last column is how many of the window's measurements the 3σ gate rejected.

| signal | setting | RMS h error, whole flight | NIS, whole flight | mean h error, 20–30 s | max abs h error, 20–30 s | NIS, 20–30 s | rejected |
|---|---|---|---|---|---|---|---|
| quiet | baseline | 0.044 m | 1.00 | 0.014 m | 0.10 m | 0.95 | 1 |
| quiet | `q_acc` ×10 | 0.068 m | 0.99 | 0.018 m | 0.21 m | 0.94 | 1 |
| quiet | `q_acc` ×0.1 | 0.039 m | 1.01 | 0.016 m | 0.08 m | 0.96 | 2 |
| quiet | `r_baro` ×10 | 0.045 m | 0.10 | 0.005 m | 0.07 m | 0.10 | 0 |
| jump 0.5 | baseline | 0.079 m | 1.05 | 0.145 m | 0.30 m | 1.19 | 9 |
| jump 0.5 | `q_acc` ×10 | 0.070 m | 0.99 | 0.043 m | 0.19 m | 0.95 | 3 |
| jump 0.5 | `q_acc` ×0.1 | 0.120 m | 1.15 | 0.193 m | 0.56 m | 1.83 | 34 |
| jump 0.5 | `r_baro` ×10 | 0.183 m | 0.14 | 0.385 m | 0.61 m | 0.28 | 0 |
| jump 1.0 | baseline | 0.148 m | 1.22 | 0.300 m | 0.65 m | 2.19 | 46 |
| jump 1.0 | `q_acc` ×10 | 0.075 m | 1.00 | 0.066 m | 0.21 m | 0.97 | 3 |
| jump 1.0 | `q_acc` ×0.1 | 223 m | 630 | 11.2 m | 35.2 m | 652 | 792 |
| jump 1.0 | `r_baro` ×10 | 0.355 m | 0.24 | 0.765 m | 1.21 m | 0.86 | 0 |

The numbers are the output of `report` with `seed=0`; with the same seed yours should match to the last digit. State in one line what each knob does (this is exactly what `EK3_ACC_P_NSE` and `EK3_ALT_M_NSE` do), and separately: which number in the table shows that Q is too small, and why the quiet signal does not show it.

### Step 2. A barometer outlier
On the quiet signal (`t, h_true, acc, baro = make()`), insert a +5 m jump into `baro` for 1 s (prop wash, a door): without the gate the estimate jumps; with the gate the measurement is rejected, the normalized innovation is > 3, and the estimate follows the accelerometer. Make the jump long (10 s): the filter eventually "gives in," as it should (gates do not protect against a systematic error).

### Step 3. Connecting to the log
Take an ArduPilot log: `XKF4.SH` (the normalized height innovation) and `XKF3.IPD` (the down position innovation) during takeoff and landing; `XKF2.AZ` is the accel Z bias estimate. Compare with what your filter did. Self-check: the lab is done when the filter on the synthetic signal gives the expected result (a bias of about 0.2, an RMS altitude error well below 0.3 m, a mean NIS of about 1), the outlier is plotted with and without the gate, the step 1b table for the twelve runs comes from your own run and matches the one above (RMS h error, mean and maximum error in the 20–30 s window, mean NIS, number of rejected measurements), and `XKF4.SH`, `XKF3.IPD` and `XKF2.AZ` from your own log are compared with the normalized innovation and bias of your filter.

**Reference for the self-check.** The knobs in one line: Q (`q_acc`, `EK3_ACC_P_NSE` in the firmware) is how much you distrust the model, R (`r_baro`, `EK3_ALT_M_NSE` in the firmware) is how much you distrust the measurement. `q_acc` ×10 makes the estimate follow the baro noise more: on the quiet signal the RMS h error grows from 0.044 to 0.068 m, but the accelerometer error jump becomes barely noticeable (a mean error in the window of 0.04–0.07 m, NIS 0.95–0.97, within 1 ± 0.09). `q_acc` ×0.1 on the quiet signal gives an RMS even slightly below the baseline (0.039 m) and NIS around 1: the model is accurate, and the small Q gives no sign of itself. With the 0.5 m/s² jump the same small Q means lag: a mean error of 0.19 m against 0.15 m for the baseline and 0.04 m for ×10, a maximum of 0.56 m, a window NIS of 1.83, 1.7 times the 1.09 bound, and the gate rejected 34 measurements out of 1000. With the 1.0 m/s² jump the small-Q filter diverges: the last measurement is accepted at 22.5 s, after that the gate rejects everything, the estimate follows the accelerometer with the wrong bias, and the error is 7.9 m at second 25, 35 m at second 30 and over 600 m by the end of the flight; the bias estimate freezes at 0.41 instead of 1.2. The baseline survives the same jump (a maximum of 0.65 m, NIS 2.19: the filter is already dishonest, but measurements still get through), and ×10 does not notice it. `r_baro` ×10 tells the filter the baro is noisier than it is: the mean NIS falls far below 1 (0.10), the filter overestimates its uncertainty; with the jump it lags the most (0.39 and 0.77 m), while NIS stays below 1: an inflated R hides the model error, so NIS below 1 does not mean "all is well." With another seed the numbers shift: for the 0.5 jump on seeds 1–4 the whole-flight RMS is 0.074–0.079 m (baseline) and 0.105–0.117 m (×0.1), the window NIS 1.23–1.30 and 1.58–1.78; the order of the settings stays the same. The conclusion about Q: a small Q does harm exactly when the real model error is larger than the declared one; on a quiet segment you see it neither in the RMS nor in the NIS. A 1 s jump with the gate: normalized innovation > 3, measurements rejected, the estimate follows the accelerometer and does not jump by 5 m; a 10 s jump: the estimate eventually moves to the false +5 m. Common wrong results: NIS far from 1 already on the baseline run, which means variance and σ were mixed up (R = 0.3², not 0.3); the bias does not converge to 0.2, which means the sign of the bias in the model (v += (a − b)·dt) does not match the sign in the generator. In the log, `XKF4.SH` < 0.5 is a healthy flight, and > 1 means the height measurement was rejected by the gate.

## diagnostics
- **Symptom:** `XKF4.SH` > 1 on takeoff
  - Possible cause: the baro is in prop wash or in the airflow; the configured R (`EK3_ALT_M_NSE`) is not enough to cover this error.
  - What to do: cover the baro with foam, `EK3_ALT_M_NSE`, a rangefinder as the height source near the ground.
- **Symptom:** position innovations grow, then "EKF variance" and a failsafe
  - Possible cause: a GPS glitch or multipath, or a lying compass, and the model drifts away.
  - What to do: `GPS.NSats/HDOP`, `XKF4.SM`; EKF sources, GPS check.
- **Symptom:** your own filter diverges (P grows without bound)
  - Possible cause: all measurements are rejected by the gate after a systematic error.
  - What to do: widen the gate temporarily, or reset to the measurement after a prolonged rejection (like an EKF reset).
- **Symptom:** a lane switch in the log
  - Possible cause: one IMU is noisier (vibration), and the core using it accumulated error.
  - What to do: mechanics, check the IMU; it is normal if rare.

## references
- ArduPilot — EKF overview and lanes | https://ardupilot.org/copter/docs/common-apm-navigation-extended-kalman-filter-overview.html | primary | A
- ArduPilot — EKF3 source (AP_NavEKF3, state vector and fusion) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/AP_NavEKF3 | primary | A
- PX4 — ECL EKF tuning (innovations, gates, noise parameters) | https://docs.px4.io/v1.17/en/advanced_config/tuning_the_ecl_ekf.html | primary | A
- Welch, Bishop — An Introduction to the Kalman Filter (UNC TR 95-041) | https://www.cs.unc.edu/~welch/media/pdf/kalman_intro.pdf | secondary | A
- R. Labbe — Kalman and Bayesian Filters in Python (open book, notebooks) | https://github.com/rlabbe/Kalman-and-Bayesian-Filters-in-Python | secondary | A

## checklist
- I can explain prediction, innovation, gain and correction
- I understand that covariance measures uncertainty and K is the trade-off
- I can compute a Kalman step by hand and explain what Q and R do
- I check the filter's honesty with normalized innovations (NIS)
- I understand observability and the EKF's delayed time horizon
- I implemented a 1D altitude filter with a gate
- I showed the behavior with a short and a long baro outlier
- I can read XKF1–XKF4 in a log and understand what is there
