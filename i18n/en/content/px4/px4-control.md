---
id: px4-control
title: "PX4 control loops and tuning"
level: L3
readingTime: 25 min
firmware: PX4 1.14+
status: published
added: 2026-03-21
tags:
  - PID
  - autotune
  - control allocation
related:
  - px4-architecture
  - bf-pid
next:
  - px4-ros2
source: content/px4/px4-control.md
source_hash: b80149855b5e
---

## summary
Multirotor control in PX4 is a cascade of three loops: position → attitude → angular rate, plus the distribution of torques across the motors. This module explains which parameter belongs to which loop, how the forms of the rate controller differ (a K multiplier versus a plain P), what manual tuning from the step response looks like, and why for most frames the right answer is autotune. For those coming from Betaflight — a mapping table.

## theory
### The cascade
1. **Position controller** (`MPC_*`): the position error gives the desired velocity (`MPC_XY_P`, `MPC_Z_P`), the velocity error gives the desired acceleration/tilt (`MPC_XY_VEL_P_ACC` and others). The hover throttle `MPC_THR_HOVER` and the speed limits `MPC_XY_VEL_MAX`, `MPC_Z_VEL_MAX_UP/DN` also live here.
2. **Attitude controller** (`MC_ROLL_P`, `MC_PITCH_P`, `MC_YAW_P`): the angle error gives the desired angular rate. P only.
3. **Rate controller** (`MC_ROLLRATE_P/I/D/K`, the same for PITCH and YAW, plus `MC_*RATE_FF`): the angular-rate error gives a torque. The fastest loop; it defines how the vehicle “feels”.
4. **Control allocation**: torques and thrust → motor commands according to the geometry `CA_AIRFRAME`, `CA_ROTOR_COUNT`, `CA_ROTOR<n>_PX/PY/KM`.

### The form of the rate controller
PX4 uses a parallel form with a common multiplier K: output = K × (P·e + I·∫e + D·de/dt). `MC_ROLLRATE_K` scales all three at once, so the first step of coarse tuning is K, not P. Betaflight has no such multiplier; in the sliders its role is played by the Master Multiplier.

### Mapping from Betaflight
| Betaflight | PX4 |
|---|---|
| P/I/D roll (rate) | `MC_ROLLRATE_P/I/D` (× `MC_ROLLRATE_K`) |
| Feedforward | `MC_ROLLRATE_FF` |
| Angle mode strength | `MC_ROLL_P` |
| Gyro filters | `IMU_GYRO_CUTOFF`, `IMU_DGYRO_CUTOFF`, notch `IMU_GYRO_NF*_FRQ` |
| Throttle hover / air mode | `MPC_THR_HOVER`, `MC_AIRMODE` |

### Autotune
For most frames the documentation explicitly recommends autotune: it is faster and usually gives a good result. It identifies the model from the responses in hover and applies the rate gains it found; applying is controlled by `MC_AT_APPLY` (immediately, after landing or manually). Manual tuning is for when autotune can't cope: non-standard frames, heavy vibration, large vehicles.

### Manual tuning from the step response
The order: filters → rate (K, then D, then I) → attitude P → position. A step: Acro or Stabilized, sharp short stick movements, a log, a plot of `vehicle_rates_setpoint` versus `vehicle_angular_velocity` in Flight Review. Overshoot — lower K or more D; slow response — more K; drift — more I. The same method and the same metrics as in the module on data-driven PID.

### Defaults and what they mean
`MC_ROLLRATE_P` = 0.15, `I` = 0.2, `D` = 0.003, `K` = 1.0, `FF` = 0 (the output is a dimensionless torque per 1 rad/s of error); `MC_ROLL_P` = 4.0 (angular rate per radian of angle error → 1/s), `MC_YAW_P` = 2.8; position: `MPC_XY_P` = 0.95 (1/s), velocity → acceleration `MPC_XY_VEL_P_ACC` = 1.8, `I_ACC` = 0.4, `D_ACC` = 0.2; `MPC_Z_P` = 1.0. The hover throttle `MPC_THR_HOVER` = 0.5 (normalized) — refined by the hover thrust estimator (`HTE_*`). Filters: `IMU_GYRO_CUTOFF` = 40 Hz, `IMU_DGYRO_CUTOFF` = 20 Hz, the static notch `IMU_GYRO_NF0_FRQ`/`BW` (0 = off, BW 20 Hz), the dynamic one by ESC RPM `IMU_GYRO_DNF_EN` (a bitmask: bit 0 — by ESC RPM, bit 1 — by the onboard FFT `IMU_GYRO_FFT_EN`), `IMU_GYRO_DNF_MIN` = 25 Hz. Air mode `MC_AIRMODE` (0 off, 1 roll/pitch, 2 + yaw).

Units matter: the error is in rad/s, the output is a fraction of the maximum torque. P = 0.15 means an error of 1 rad/s (57°/s) gives 15% of the torque. Comparison with Betaflight (dimensionless “45”) is only qualitative, via the module “Control theory” (ζ, phase margin).

### Autotune in more detail
`MC_AT_EN` = 1 enables the `mc_autotune_attitude_control` module; it is started from QGC (PID Tuning → Autotune) in Altitude/Position while hovering in calm air; the module injects an excitation with amplitude `MC_AT_SYSID_AMP` (0.7) on each axis, identifies the model of the rate loop and computes the gains; `MC_AT_APPLY` (0 — don't apply, 1 — after landing, 2 — immediately in flight) — the default is 1. Afterwards — a check flight and Flight Review: a response with no overshoot > 10%, D without noise. Autotune doesn't tune the filters and doesn't cure vibration — those are done **before** (spectrum!).

### Worked example: 7" 6S, 1.4 kg
Start: airframe Generic Quad, `CA_ROTOR_COUNT` = 4, `IMU_GYRO_RATEMAX` 400 → 800 Hz (H7), `IMU_GYRO_CUTOFF` 40 → 80, `IMU_DGYRO_CUTOFF` 20 → 40; eRPM over DShot (bidirectional DShot or ESC telemetry over UART — `DSHOT_TEL_CFG`), `IMU_GYRO_DNF_EN` = 1; `MPC_THR_HOVER` will be refined by the HTE estimator; first flight in Stabilized — `MC_ROLLRATE_K` 1.0 → 0.7 if it wobbles; autotune; `MPC_XY_VEL_MAX` to suit the task. Log → Flight Review: rate tracking, spectrum, `vehicle_torque_setpoint` without saturation.

{{diagram:px4-cascade|The PX4 cascade: position → velocity → attitude → angular rate → allocator, with the parameters of each level.}}

## practice
### Step 1. Allocation first
Props off: Actuators in QGC — the geometry matches the frame, and in the test each motor spins in the right direction.

### Step 2. Filters from the log
A flight with logging, Flight Review → gyro spectrogram. Set `IMU_GYRO_CUTOFF` and `IMU_DGYRO_CUTOFF` so that they cut motor noise without touching the control band.

### Step 3. Autotune
QGC → PID Tuning → Autotune, or a switch assigned to the autotune function. Hover, start, don't touch the sticks until it finishes, land. Check that the new `MC_*RATE_*` were applied.

### Step 4. Verification
Step response in Flight Review before and after: overshoot and settling time. If needed — manual adjustment of K/D by 10–20%.

### What you should get and what to write down
- **Step 1.** In QGC → Actuators the frame diagram matches the real one, and the test for each motor spins exactly that motor and in the direction shown in the picture. A mistake here can't be cured by any amount of tuning.
- **Step 2.** On the gyro spectrogram in Flight Review the motor noise bands rise together with throttle. The `IMU_GYRO_CUTOFF` cutoff frequency should be below those bands but noticeably above the control band (a few to tens of hertz). Write down the values before and after, and the frequency of the motor band in hover.
- **Step 3.** Autotune writes the new `MC_ROLLRATE_*`, `MC_PITCHRATE_*` gains only after it completes successfully. Compare them with the defaults and write down both versions.
- **Step 4.** Flight Review has an estimate of the step response of the angular-rate loop. Write down the overshoot (%) and the rise time (ms) before and after.

### Lab
In SITL: record the step response with the default gains, deliberately double `MC_ROLLRATE_K`, record again, explain the difference from the plot.

The expected picture: with a doubled `MC_ROLLRATE_K` (the common multiplier for the loop's P, I and D) the response is faster, the overshoot is larger, and the oscillations after the step take longer to die out and are at a higher frequency — the phase margin has decreased (module “Control theory”). Apply the steps as sharp roll stick movements in Stabilized or Acro with the QGC virtual joystick, the same way in both flights.

The lab counts as done when the allocation has been checked with props off, the step response has been recorded at the defaults and with a doubled `MC_ROLLRATE_K`, with overshoot and rise-time numbers, and the difference has been explained through the phase margin.

## diagnostics
- **Symptom:** fast oscillations after autotune
  - Possible cause: the noise isn't filtered, and autotune picked gains for a noisy signal.
  - What to do: filters, autotune again.
- **Symptom:** in Position the vehicle slowly “sways”
  - Possible cause: the outer loop (`MPC_*`) is too aggressive with a weak inner loop.
  - What to do: rate/attitude first, then position.
- **Symptom:** hot motors
  - Possible cause: high D on a noisy gyro.
  - What to do: lower D, increase filtering, check the mechanics.
- **Symptom:** a motor spins the wrong way in the test
  - Possible cause: the geometry or direction in Actuators.
  - What to do: fix `CA_ROTOR<n>_KM`/the direction, recheck with props off.
- **Symptom:** autotune aborts
  - Possible cause: wind, vibration, a starting tune that is too low, not enough altitude.
  - What to do: calm air, spectrum and notch before autotune, a lower `MC_ROLLRATE_K`, altitude 5+ m.
- **Symptom:** slow position oscillations in Position mode
  - Possible cause: `MPC_XY_P`/`MPC_XY_VEL_*` higher than GPS quality/latency allows.
  - What to do: check the EKF (innovations), lower `MPC_XY_VEL_P_ACC`, then `MPC_XY_P`.

## references
- PX4 Multicopter PID Tuning Guide (Advanced) | https://docs.px4.io/main/en/config_mc/pid_tuning_guide_multicopter.html | primary | A
- PX4 Multicopter PID Tuning Guide (Basic) | https://docs.px4.io/main/en/config_mc/pid_tuning_guide_multicopter_basic.html | primary | A
- PX4 Autotuning (Multicopter) | https://docs.px4.io/main/en/config/autotune_mc.html | primary | A
- PX4 Control Allocation | https://docs.px4.io/main/en/concept/control_allocation.html | primary | A

## checklist
- I understand the position → attitude → rate → allocation cascade
- I know the role of `MC_*RATE_K` and how it differs from Betaflight
- Allocation has been checked with props off
- Autotune has been run and the result checked against the step response
