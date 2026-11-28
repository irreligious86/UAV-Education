---
id: math-prob-est
title: "Probability and estimation: noise, Gaussians, fusion"
level: L3
readingTime: 45 min
firmware: ArduPilot (checked against 4.7.3) · PX4 (checked against v1.18.0)
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
source_hash: c491322974ab
---

## summary
The Kalman filter is not magic but two facts about Gaussian distributions applied a million times. This module gives you those facts and the language around them: a random variable, the mean and the variance, why sensor noise is treated as Gaussian, what independence and covariance are, what a covariance matrix looks like as an ellipse, and what "EKF variance" means in a failsafe message. The central result is the optimal fusion of two measurements, which is exactly one Kalman step. Then how noise behaves over time: white noise, random walk, ARW/VRW and the Allan deviation, which is how you read an IMU datasheet and pick `EK3_GYRO_P_NSE`. The lab: gyro noise and bias from a recording, the Allan deviation, and a numerical fusion problem.

## theory
### Random variable, mean, variance
A sensor measurement is z = x + n: the true value plus noise. The noise is a random variable: we do not know the next value, but we know how the values are distributed. The mean μ = E[n] is the systematic part (bias), which can be estimated and subtracted. The variance σ² = E[(n − μ)²] is the spread; σ (the standard deviation) is in the same units as the measurement. Sample estimates over N samples: μ̂ = (1/N)Σzᵢ, σ̂² = (1/(N−1))Σ(zᵢ − μ̂)². For a gyro at rest, μ̂ is the bias and σ̂ the noise; both go into the sensor datasheet.

The mean of N independent samples has variance σ²/N: averaging 100 samples reduces σ by a factor of 10. That is the limit of what "just filtering" buys you, and the reason why slow sensors (5 Hz GPS) cannot be made accurate by averaging over 0.2 s.

### The Gaussian and why it is everywhere
The density N(μ, σ²): p(x) = (1/(σ√(2π)))·exp(−(x − μ)²/(2σ²)). Within ±1σ lie 68 % of the values, within ±2σ 95 %, within ±3σ 99.7 %. The EKF innovation gates (`EK3_*_I_GATE`) are exactly "reject everything further than kσ." The Gaussian arises from the central limit theorem: the sum of many small independent contributions (thermal noise, vibration, quantization) is almost normally distributed, whatever the individual contributions look like. The second argument is practical: a Gaussian is fully described by two numbers, and linear operations on Gaussians give Gaussians. For a filter this means the state can be stored as (mean, covariance) rather than as a histogram.

Where the Gaussian model breaks down: outliers (GPS multipath, a magnetic anomaly), with tails heavier than normal, hence the gates; quantization and saturation; noise that depends on the operating mode (vibration under throttle).

### Two measurements of the same thing
Measurements z₁ with variance σ₁² and z₂ with σ₂² of the same quantity x. The best (minimum-variance, unbiased) linear estimate weights them by their inverse variances:

x̂ = (z₁/σ₁² + z₂/σ₂²) / (1/σ₁² + 1/σ₂²), 1/σ̂² = 1/σ₁² + 1/σ₂².

Rewritten with K = σ₁²/(σ₁² + σ₂²): x̂ = z₁ + K·(z₂ − z₁), σ̂² = (1 − K)·σ₁². Recognize it? z₁ is the prediction with uncertainty P, z₂ the measurement with R, K the Kalman gain, and (z₂ − z₁) the innovation. **One Kalman step is the fusion of two Gaussians.** Everything else in an EKF is about how to get the prediction and its P from the previous state (the model plus the process noise Q) and how to do the same for a vector.

{{diagram:gaussian-fusion|Fusing two Gaussian estimates: the result is always narrower than either of them and shifted toward the more accurate one.}}

### Vectors: covariance and the ellipse
For a state vector x (for example, position N, E) the covariance matrix is P = E[(x − μ)(x − μ)ᵀ]: the diagonal holds the variances of the components, the off-diagonal terms the covariances, that is, how strongly the errors are related. The correlation is ρ = P₁₂/(σ₁σ₂) ∈ [−1, 1]. Geometrically P is an uncertainty ellipse: its axes lie along the eigenvectors of P, with semi-axes √(eigenvalues). A GPS ellipse elongated along N says north is known worse than east (typical with poor satellite geometry). "EKF variance" in the ArduPilot failsafe means normalized innovations (the √test ratio of velocity, position and compass, the same numbers as in `XKF4`) that have exceeded `FS_EKF_THRESH`: the filter is honestly admitting it does not know where it is.

A linear transformation y = A·x carries the covariance as P_y = A·P·Aᵀ. This is the formula both for prediction (A = F, the model matrix) and for changing coordinate frames (A = R: the covariance rotates together with the ellipse). Independence means zero covariance and a diagonal P; that is exactly what you assume when you set `EK3_*_M_NSE`/`EK3_*_P_NSE` (in PX4, `EKF2_*_NOISE`) as one number per source.

{{diagram:cov-ellipse-rotation|A 45° rotation turns the 2σ ellipse by the same 45°: the eigenvalues do not change, while the component variances become 0.725 and 5.525.}}

### Noise over time: white, random walk, Allan deviation
In white noise the samples are independent; its integral is a **random walk**, whose σ grows as √t. For a gyro: rate noise σ_g (°/s per sample), once integrated, gives an angle error σ_θ(t) = ARW·√t, where ARW = σ_g·√T_s (angle random walk, given in °/√h in datasheets). For an accelerometer it is VRW: the velocity error grows as √t, the position error as t^1.5. This explains why position from the IMU alone drifts by meters within seconds without GPS, while the angle from the gyro holds for minutes.

But the bias is not constant either: it slowly wanders (bias instability, flicker). The **Allan deviation** σ(τ), the standard deviation of the difference between averages over adjacent windows of length τ, separates these contributions on one plot: a slope of −½ (white noise; ARW is read off it at τ = 1 s), a plateau (bias instability, the best achievable bias stability), a slope of +½ (rate random walk). This plot is what you use to choose the EKF process noise: `EK3_GYRO_P_NSE` is set in rad/s (default 0.015, with a large margin over the datasheet noise density, because it also covers vibration and model errors), and `EK3_GBIAS_P_NSE` from the +½ slope. PX4: `EKF2_GYR_NOISE`, `EKF2_GYR_B_NOISE`.

### What of this is in the autopilot parameters
| What | ArduPilot EKF3 | PX4 EKF2 |
|---|---|---|
| gyro noise σ (part of Q, the process noise in the prediction) | `EK3_GYRO_P_NSE` | `EKF2_GYR_NOISE` |
| gyro bias random walk | `EK3_GBIAS_P_NSE` | `EKF2_GYR_B_NOISE` |
| GPS position σ | `EK3_POSNE_M_NSE` (+HDOP) | `EKF2_GPS_P_NOISE` |
| baro σ | `EK3_ALT_M_NSE` | `EKF2_BARO_NOISE` |
| gates (in σ) | `EK3_*_I_GATE` (%) | `EKF2_*_GATE` |

Raising `*_NSE` tells the filter "this sensor is worse than you thought": it will trust it less and, at the same time, reject it by the gates less often.

### Where it fits

- **Takes in:** gyro and accelerometer noise and bias from the datasheet and from a recording at rest (`est-sensors`); the GPS position scatter and its dependence on satellite geometry (`est-gnss`).
- **Hands off:** the Kalman step as the fusion of two Gaussians to the filter (`est-kalman`); the meaning of innovation gates and "EKF variance" to reading EKF health (`ap-ekf`); the Allan deviation to choosing `EK3_GYRO_P_NSE` and `EKF2_GYR_NOISE`.
- **If you get this wrong:** you set `*_M_NSE` too low ("the sensor is better than it is") → the computed innovation spread (P + R) is smaller than the real one → the filter chases the noise, and ordinary measurement noise falls outside the gates and is rejected → "EKF variance" and an EKF failsafe in flight (`ap-ekf`, `ap-safety-fs`). You treated GPS errors as Gaussian where there is multipath → heavy-tailed outliers; how to recognize them is in `nav-resilience`.

## practice
### Step 1. A gyro datasheet from a recording
Record 10–30 minutes of IMU data at rest (`IMU` in ArduPilot DataFlash, or, with the raw IMU bit in `LOG_BITMASK`, raw `GYR`/`ACC` at the sensor rate; or `sensor_gyro` in a ulog; or Blackbox on the bench without arming). For each axis: bias, σ, a histogram with a Gaussian overlaid. Check the fraction of samples beyond ±3σ; for a Gaussian it is 0.3 %.

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
Plot it log-log for τ from 0.01 to 300 s. Find the ARW (the value on the −½ slope at τ = 1 s) and the bias instability (the minimum). Compare with the chip datasheet (ICM-42688: ~0.0028 °/s/√Hz). Convert it to rad/s/√Hz (0.0028 °/s/√Hz = 4.9·10⁻⁵ rad/s/√Hz) and then to an rms rate in rad/s over the sensor bandwidth (× √bandwidth, e.g. × √200 ≈ 7·10⁻⁴ rad/s), the units of `EK3_GYRO_P_NSE` (rad/s): the default 0.015 is about 20 times larger, the margin for vibration and model errors.

### Step 3. Fusion by hand
The barometer gives 101.3 m with σ = 0.5 m, the rangefinder 100.2 m with σ = 0.1 m. Find the optimal estimate and its σ (answer: ≈100.24 m, σ ≈ 0.098 m). Then "break" the rangefinder: 95 m with the same σ. A filter with 3σ gates should reject the measurement; check by calculation why (an innovation of 6.3 m with S = √(0.5² + 0.1²) ≈ 0.51 m).

### Step 4. The ellipse
Generate 2000 points with P = [[4, 2.4], [2.4, 2.25]]; plot the cloud and the 2σ ellipse from the eigenvectors. Rotate the cloud by 45° and confirm that the sample covariance has become R·P·Rᵀ.

Self-check: the lab is done when the gyro datasheet has bias and σ recorded for each axis and the fraction of samples beyond ±3σ is close to 0.3 %, the ARW (on the −½ slope at τ = 1 s) and the bias instability (the minimum) are found on the Allan deviation plot and the ARW is compared with the chip datasheet, the step 3 fusion gave ≈ 100.24 m and σ ≈ 0.098 m, and the sample covariance of the rotated cloud matched R·P·Rᵀ from the reference below.

**Reference answer for self-check.** Step 3: the broken rangefinder is rejected because an innovation of 6.3 m with S ≈ 0.51 m is more than 12·S, while the gate is 3·S ≈ 1.5 m. Step 4: P has eigenvalues 5.68 and 0.57 (the semi-axes of the 2σ ellipse are 2√5.68 ≈ 4.8 and 2√0.57 ≈ 1.5), the major axis is at 35° to x₁, the correlation is ρ = 2.4 / (2 · 1.5) = 0.8; for a 45° rotation R·P·Rᵀ = [[0.725, 0.875], [0.875, 5.525]]: the same eigenvalues, the axis at 80°; the sample covariance of 2000 points differs from this by a few percent. Typical wrong results: the fraction beyond ±3σ is noticeably larger than 0.3 %: the recording contains more than white noise (the sensor was not at rest, or there was drift); the Allan deviation has no plateau and rises at large τ: temperature drift during the recording; warm the sensor up for 10 minutes and repeat.

## diagnostics
- **Symptom:** the normalized innovations in the EKF logs are always small, but the position "floats"
  - Possible cause: the `*_NSE` values are too high: the filter barely trusts the measurements, and the gates are wide.
  - What to do: lower the measurement noise toward the real σ (from a recording at rest).
- **Symptom:** frequent GPS rejections by the gates despite good HDOP
  - Possible cause: `POSNE_M_NSE` is too low, or vibration has spoiled the prediction (large P).
  - What to do: a realistic GPS σ is 0.5–1.5 m; deal with vibration first.
- **Symptom:** the Allan deviation has no plateau and rises at large τ
  - Possible cause: temperature drift during the recording.
  - What to do: warm the sensor up for 10 min, record at a stable temperature; account for temp-cal.
- **Symptom:** "EKF variance" right after takeoff with no GPS problems
  - Possible cause: the position σ grows as t^1.5 (the variance P as t³) when there are no position measurements; the source is not configured.
  - What to do: check `EK3_SRC1_POSXY` and that the source is actually delivering data.

## references
- MIT OCW 6.041 — Probabilistic Systems Analysis | https://ocw.mit.edu/courses/6-041sc-probabilistic-systems-analysis-and-applied-probability-fall-2013/ | secondary | A
- IEEE Std 952 — Allan variance for gyros (summary in Kalibr wiki) | https://github.com/ethz-asl/kalibr/wiki/IMU-Noise-Model | secondary | A
- ArduPilot — EKF3 parameters (EK3_*_NSE, gates) | https://ardupilot.org/copter/docs/parameters.html#ek3-parameters | primary | A
- PX4 — EKF2 tuning and parameters | https://docs.px4.io/v1.17/en/advanced_config/tuning_the_ecl_ekf.html | primary | A

## checklist
- I can estimate a sensor's bias and σ from a recording and know how the σ of the mean depends on N
- I know the 68/95/99.7 rule and how gates follow from it
- I can fuse two measurements and see a Kalman step in it
- I read a covariance matrix as an ellipse and carry it through A·P·Aᵀ
- I can tell white noise, random walk and bias instability apart; I can read an Allan deviation plot
- I can translate an IMU datasheet into EK3/EKF2 parameters
