---
id: math-prob-est
title: "Probability and estimation: noise, Gaussians, fusion"
level: L3
readingTime: 45 min
firmware: ArduPilot · PX4
status: published
added: 2026-11-08
tags:
  - probability
  - Gaussian
  - covariance
  - sensor noise
  - Allan deviation
related:
  - math-ode-dyn
  - est-kalman
  - est-sensors
next:
  - est-kalman
source: content/math/math-prob-est.md
source_hash: 2bbf780f5b85
---

## summary
The Kalman filter is not magic, it is two facts about Gaussian distributions applied a million times. This module gives you those facts and the language around them: a random variable, mean and variance, why sensor noise is treated as Gaussian, what independence and covariance are, what a covariance matrix looks like as an ellipse and what “EKF variance” in a failsafe message means. The central result is the optimal fusion of two measurements, which is exactly one Kalman step. Then — how noise behaves over time: white noise, random walk, ARW/VRW and Allan deviation, which is how you read an IMU datasheet and pick `EK3_GYRO_P_NSE`. Lab: gyro noise and bias from a recording, Allan deviation, and a numeric problem on fusion.

## theory
### Random variable, mean, variance
A sensor measurement is z = x + n: the true value plus noise. Noise is a random variable: we don't know the next value, but we know how the values are distributed. The mean μ = E[n] is the systematic part (bias); you can estimate it and subtract it. The variance σ² = E[(n − μ)²] is the spread; σ (the standard deviation) is in the same units as the measurement. Sample estimates over N samples: μ̂ = (1/N)Σzᵢ, σ̂² = (1/(N−1))Σ(zᵢ − μ̂)². For a gyro at rest μ̂ is the bias and σ̂ is the noise; both go into the sensor datasheet.

The mean of N independent samples has variance σ²/N: averaging 100 samples reduces σ by a factor of 10. That is the limit of what “just filtering” gives you — and the reason slow sensors (GPS at 5 Hz) can't be made accurate by averaging over 0.2 s.

### The Gaussian and why it is everywhere
The density of N(μ, σ²): p(x) = (1/(σ√(2π)))·exp(−(x − μ)²/(2σ²)). Within ±1σ lie 68 % of the values, ±2σ — 95 %, ±3σ — 99.7 %. The innovation gates in the EKF (`EK3_*_I_GATE`) are exactly “reject everything farther than kσ”. The Gaussian arises from the central limit theorem: the sum of many small independent contributions (thermal noise, vibration, quantization) is distributed almost normally, whatever the individual contributions look like. The second argument is practical: a Gaussian is fully described by two numbers, and linear operations on Gaussians give Gaussians. For a filter that means the state can be stored as (mean, covariance) rather than as a histogram.

Where the Gaussian model breaks: outliers (GPS multipath, a magnetic anomaly) — the tails are heavier than normal, hence the gates; quantization and saturation; noise that depends on the operating mode (vibration under throttle).

### Two measurements of the same thing
Measurements z₁ with variance σ₁² and z₂ with σ₂² of the same quantity x. The best (minimum-variance, unbiased) linear estimate weights them by inverse variances:

x̂ = (z₁/σ₁² + z₂/σ₂²) / (1/σ₁² + 1/σ₂²), 1/σ̂² = 1/σ₁² + 1/σ₂².

Rewritten with K = σ₁²/(σ₁² + σ₂²): x̂ = z₁ + K·(z₂ − z₁), σ̂² = (1 − K)·σ₁². Recognize it? z₁ is the prediction with uncertainty P, z₂ is the measurement with R, K is the Kalman gain, (z₂ − z₁) is the innovation. **One Kalman step is the fusion of two Gaussians.** Everything else in the EKF is how to get the prediction and its P from the previous state (model + process noise Q) and how to do the same for a vector.

{{diagram:gaussian-fusion|Fusing two Gaussian estimates: the result is always narrower than either of them and shifted toward the more accurate one.}}

### Vectors: covariance and the ellipse
For a state vector x (for example, position N, E) the covariance matrix is P = E[(x − μ)(x − μ)ᵀ]: the diagonal holds the variances of the components, the off-diagonal entries are covariances, that is, how strongly the errors are linked. The correlation ρ = P₁₂/(σ₁σ₂) ∈ [−1, 1]. Geometrically P is an uncertainty ellipse: the axes lie along the eigenvectors of P, the semi-axes are √(eigenvalues). A GPS ellipse stretched along N says that north is known worse than east (typical with poor satellite geometry). “EKF variance” in the ArduPilot failsafe is the normalized innovations (the √test ratio of velocity, position, compass — the same numbers as in `XKF4`) exceeding `FS_EKF_THRESH`: the filter honestly admits it doesn't know where it is.

A linear transform y = A·x carries the covariance as P_y = A·P·Aᵀ. This is the formula both for prediction (A = F, the model matrix) and for switching between coordinate frames (A = R — the covariance rotates together with the ellipse). Independence: zero covariance, P is diagonal; that is exactly what you assume when you set `EK3_*_NOISE` with one number per source.

### Noise over time: white, random walk, Allan deviation
White noise — the samples are independent; its integral is a **random walk**, whose σ grows as √t. For a gyro: the angular rate noise σ_g (°/s per sample) after integration gives an angle error σ_θ(t) = ARW·√t, where ARW = σ_g·√T_s (angle random walk, in °/√h in datasheets). For an accelerometer it is VRW: the velocity error grows as √t, the position error as t^1.5. This explains why without GPS an IMU-only position drifts by meters in seconds, while the gyro angle holds for minutes.

But the bias isn't constant either: it slowly wanders (bias instability, flicker). **Allan deviation** σ(τ) — the standard deviation of the difference of averages over adjacent windows of length τ — separates these contributions on one plot: a slope of −½ (white noise; ARW is read from it at τ = 1 s), a plateau (bias instability — the best achievable bias stability), a slope of +½ (rate random walk). This plot is what you use to pick the EKF process noise: `EK3_GYRO_P_NSE` is set in rad/s (default 0.015 — with a large margin over the datasheet noise density, because it covers vibration and model errors), `EK3_GBIAS_P_NSE` — from the +½ slope. PX4: `EKF2_GYR_NOISE`, `EKF2_GYR_B_NOISE`.

### What of this is in the autopilot parameters
| What | ArduPilot EKF3 | PX4 EKF2 |
|---|---|---|
| gyro noise σ (R part of the prediction) | `EK3_GYRO_P_NSE` | `EKF2_GYR_NOISE` |
| gyro bias random walk | `EK3_GBIAS_P_NSE` | `EKF2_GYR_B_NOISE` |
| GPS position σ | `EK3_POSNE_M_NSE` (+HDOP) | `EKF2_GPS_P_NOISE` |
| baro σ | `EK3_ALT_M_NSE` | `EKF2_BARO_NOISE` |
| gates (in σ) | `EK3_*_I_GATE` (%) | `EKF2_*_GATE` |

Raising `*_NSE` means telling the filter “this sensor is worse than you thought”: it will trust it less and, at the same time, reject it by the gates less often.

## practice
### Step 1. A gyro datasheet from a recording
Record 10–30 minutes of IMU at rest (`IMU` in the ArduPilot DataFlash log with a `LOG_BITMASK` that includes raw IMU; or `sensor_gyro` in a ulog; or Blackbox on the bench without arming). For each axis: bias, σ, a histogram with a Gaussian overlaid. Check the fraction of samples beyond ±3σ — for a Gaussian it is 0.3 %.

### Step 2. Allan deviation
```python
import numpy as np

def allan_dev(x, fs, taus):
    """Overlapping Allan deviation of a rate signal x (sampled at fs) for averaging times taus (s)."""
    theta = np.cumsum(x) / fs                       # integrate rate -> angle
    out = []
    for tau in taus:
        m = int(tau * fs)
        if m < 1 or 3 * m > len(theta): out.append(np.nan); continue
        d = theta[2*m:] - 2*theta[m:-m] + theta[:-2*m]
        out.append(np.sqrt(np.mean(d**2) / (2 * tau**2)))
    return np.array(out)
```
Plot it log-log for τ from 0.01 to 300 s. Find ARW (the value on the −½ slope at τ = 1 s) and bias instability (the minimum). Compare with the chip datasheet (ICM-42688: ~0.0028 °/s/√Hz). Convert to the units of `EK3_GYRO_P_NSE` (rad/s/√Hz).

### Step 3. Fusion by hand
The barometer gives 101.3 m with σ = 0.5 m, the rangefinder gives 100.2 m with σ = 0.1 m. Find the optimal estimate and its σ (answer: ≈100.24 m, σ ≈ 0.098 m). Then “break” the rangefinder: 95 m with the same σ. A filter with 3σ gates should reject the measurement — show why (an innovation of 6.3 m with S = √(0.5² + 0.1²) ≈ 0.51 m).

### Step 4. The ellipse
Generate 2000 points with P = [[4, 2.4], [2.4, 2.25]]; draw the cloud and the 2σ ellipse from the eigenvectors. Rotate the cloud by 45° and show that the covariance became R·P·Rᵀ.

The lab counts as done when you have the gyro datasheet, the Allan deviation plot with the ARW and bias instability you found, and the plots from steps 3–4.

## diagnostics
- **Symptom:** in the EKF logs the normalized innovations are always small, but the position “floats”
  - Possible cause: `*_NSE` are set too high — the filter barely trusts the measurements, the gates are wide.
  - What to do: lower the measurement noise to the real σ (from a recording at rest).
- **Symptom:** frequent GPS rejections by the gates despite good HDOP
  - Possible cause: `POSNE_M_NSE` is set too low, or vibration has spoiled the prediction (large P).
  - What to do: a realistic GPS σ is 0.5–1.5 m; deal with vibration first.
- **Symptom:** Allan deviation has no plateau and rises at large τ
  - Possible cause: temperature drift during the recording.
  - What to do: warm the sensor up for 10 min, record at a stable temperature; account for temp-cal.
- **Symptom:** “EKF variance” right after takeoff with no GPS problems
  - Possible cause: the position σ grows as t^1.5 (the variance P as t³) when there are no position measurements; the source isn't configured.
  - What to do: check `EK3_SRC1_POSXY` and that the source actually delivers data.

## references
- MIT OCW 6.041 — Probabilistic Systems Analysis | https://ocw.mit.edu/courses/6-041sc-probabilistic-systems-analysis-and-applied-probability-fall-2013/ | secondary | A
- IEEE Std 952 — Allan variance for gyros (summary in Kalibr wiki) | https://github.com/ethz-asl/kalibr/wiki/IMU-Noise-Model | secondary | A
- ArduPilot — EKF3 parameters (EK3_*_NSE, gates) | https://ardupilot.org/copter/docs/parameters.html#ek3-parameters | primary | A
- PX4 — EKF2 tuning and parameters | https://docs.px4.io/main/en/advanced_config/tuning_the_ecl_ekf.html | primary | A

## checklist
- I estimate a sensor's bias and σ from a recording and know how the σ of the mean depends on N
- I know the 68/95/99.7 rule and how the gates follow from it
- I perform the fusion of two measurements and see a Kalman step in it
- I read a covariance matrix as an ellipse and carry it through A·P·Aᵀ
- I tell white noise, random walk and bias instability apart; I read an Allan deviation plot
- I convert an IMU datasheet into EK3/EKF2 parameters
