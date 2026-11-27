---
id: px4-control
title: "PX4 control loops and tuning"
level: L3
readingTime: 25 min
firmware: PX4 1.18 (checked against v1.18.0)
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
source_hash: 39c8102c9983
---

## summary
Multicopter control in PX4 is a cascade of three loops (position → attitude → angular rate) plus control allocation, which distributes torques to the motors. This module shows which parameter belongs to which loop, how the rate controller form differs (a K multiplier instead of a plain P), what manual tuning from the step response looks like, and why autotune is the right answer for most frames. If you come from Betaflight, there is a mapping table.

## theory
### The cascade
1. **Position controller** (`MPC_*`): position error → desired velocity (`MPC_XY_P`, `MPC_Z_P`), velocity error → desired acceleration/tilt (`MPC_XY_VEL_P_ACC` and others). The hover throttle `MPC_THR_HOVER` and the velocity limits `MPC_XY_VEL_MAX`, `MPC_Z_VEL_MAX_UP/DN` live here too.
2. **Attitude controller** (`MC_ROLL_P`, `MC_PITCH_P`, `MC_YAW_P`): attitude error → desired angular rate. P only.
3. **Rate controller** (`MC_ROLLRATE_P/I/D/K`, the same for PITCH and YAW, plus `MC_*RATE_FF`): angular rate error → torque. The fastest loop; it defines how the vehicle "feels".
4. **Control allocation**: torques and thrust → motor commands from the geometry in `CA_AIRFRAME`, `CA_ROTOR_COUNT`, `CA_ROTOR<n>_PX/PY/KM`.

### The rate controller form
PX4 uses the parallel form with a common K gain: output = K × (P·e + I·∫e + D·de/dt). `MC_ROLLRATE_K` scales all three at once, so the first step of coarse tuning is K, not P. Betaflight has no such multiplier; the Master Multiplier slider plays that role there.

### Mapping from Betaflight
| Betaflight | PX4 |
|---|---|
| P/I/D roll (rate) | `MC_ROLLRATE_P/I/D` (× `MC_ROLLRATE_K`) |
| Feedforward | `MC_ROLLRATE_FF` |
| Angle mode strength | `MC_ROLL_P` |
| Gyro filters | `IMU_GYRO_CUTOFF`, `IMU_DGYRO_CUTOFF`, notch `IMU_GYRO_NF*_FRQ` |
| Throttle hover / air mode | `MPC_THR_HOVER`, `MC_AIRMODE` |

### Autotune
For most frames the documentation recommends autotune outright: it is faster and usually gives a good result. It identifies a model from the responses in a hover and applies the rate gains and attitude P it finds; `MC_AT_APPLY` controls when they are applied (in the air, after disarm, or not at all, logging only). Tune manually when autotune cannot cope: unusual frames, heavy vibration, large vehicles.

### Manual tuning from the step response
Order: filters → rate (K, then D, then I) → attitude P → position. One step: Acro or Stabilized, sharp short stick inputs, a log, then `vehicle_rates_setpoint` vs. `vehicle_angular_velocity` in Flight Review. Overshoot: lower K or raise D; slow response: raise K; drift: raise I. Disable `MC_AIRMODE` while tuning; change gains by 20–30 % per iteration, 5–10 % for the final touch. Same method and same metrics as in the module on PID from data.

### Defaults and what they mean
`MC_ROLLRATE_P` = 0.15, `I` = 0.2, `D` = 0.003, `K` = 1.0, `FF` = 0 (the output is normalized torque per 1 rad/s of error); `MC_ROLL_P` = 4.0 (angular rate per radian of attitude error → 1/s; 6.5 before 1.17), `MC_YAW_P` = 2.8; position: `MPC_XY_P` = 0.95 (1/s), velocity → acceleration `MPC_XY_VEL_P_ACC` = 1.8, `I_ACC` = 0.4, `D_ACC` = 0.2; `MPC_Z_P` = 1.0. Hover throttle `MPC_THR_HOVER` = 0.5 (normalized), refined by the hover thrust estimator (`HTE_*`). Filters: `IMU_GYRO_CUTOFF` = 40 Hz, `IMU_DGYRO_CUTOFF` = 20 Hz (30 before 1.17), loop rate `IMU_GYRO_RATEMAX` = 800 Hz on a multicopter (the airframe raises the parameter default of 400), static notch `IMU_GYRO_NF0_FRQ`/`BW` (0 = off, BW 20 Hz), dynamic notch from ESC RPM `IMU_GYRO_DNF_EN` (bitmask: bit 0 ESC RPM, bit 1 onboard FFT `IMU_GYRO_FFT_EN`), `IMU_GYRO_DNF_MIN` = 25 Hz. Air mode `MC_AIRMODE` (0 Disabled, 1 Roll/Pitch, 2 Roll/Pitch/Yaw). All differences between the 1.15/1.16 and 1.17 defaults are in the upgrade table in px4-intro.

Units matter: the error is in rad/s and the output is a fraction of the maximum torque. P = 0.15 means an error of 1 rad/s (57 deg/s) gives 15% torque. Comparing with Betaflight (dimensionless "45") only works qualitatively, through the "Control theory" module (ζ, phase margin).

### Defaults for every axis (v1.17.0; the same in v1.18.0)
1.18 adds an optional feed-forward to the attitude loop from a second-order reference model: `MC_REF_FF` (0…1, default 0, the old behavior), natural frequency `MC_REF_W_N` (50 rad/s) and the cap `MC_REF_FF_MAX` (100 deg/s) (`mc_att_control_params.yaml`, v1.18.0). The table below is without it.

How to read it: start from the axis and the cascade level; the table gives the number a generic airframe starts from (4001 Generic Quadcopter does not override the gains; ready-made airframes for specific frames can); check that `param show MC_ROLLRATE*` (and `MC_PITCHRATE*`, `MC_YAWRATE*`; `*` is only allowed at the end of the filter) in the console matches the table as long as you have changed nothing.

| Level | Roll | Pitch | Yaw | Unit |
|---|---|---|---|---|
| rate P / I / D | 0.15 / 0.2 / 0.003 | 0.15 / 0.2 / 0.003 | 0.2 / 0.1 / 0 | torque fraction per rad/s |
| rate K / FF | 1.0 / 0 | 1.0 / 0 | 1.0 / 0 | — |
| integrator limit (`MC_RR_INT_LIM`, `MC_PR_INT_LIM`, `MC_YR_INT_LIM`) | 0.30 | 0.30 | 0.30 | torque fraction |
| attitude P (`MC_ROLL_P`, `MC_PITCH_P`, `MC_YAW_P`) | 4.0 (6.5 before 1.17) | 4.0 (6.5 before 1.17) | 2.8 | 1/s |
| angular rate limit in attitude modes (`MC_ROLLRATE_MAX`, `MC_PITCHRATE_MAX`, `MC_YAWRATE_MAX`) | 220 | 220 | 200 | deg/s |

Yaw is different on purpose: D = 0, a higher P, a lower I, and `MC_YAW_WEIGHT` = 0.4 (0…1) lowers the priority of yaw relative to roll and pitch in the attitude loop; it does not change the `MC_YAW_P` gain itself. The reason: a multicopter has much less control torque in yaw (it comes from the difference in propeller reaction torques), and yaw is not critical for hovering.

The vertical and horizontal position loops (`mc_pos_control`):

| Parameter | Default | What it sets |
|---|---|---|
| `MPC_Z_P` | 1.0 1/s | altitude error → vertical velocity setpoint |
| `MPC_Z_VEL_P_ACC` / `I_ACC` / `D_ACC` | 4.0 / 2.0 / 0 | vertical velocity error → acceleration (m/s² per m/s) |
| `MPC_XY_VEL_P_ACC` / `I_ACC` / `D_ACC` | 1.8 / 0.4 / 0.2 | the same horizontally |
| `MPC_ACC_HOR` | 3 m/s² | acceleration in auto modes; in manual modes only with `MPC_POS_MODE` = 4 (Acceleration based, the default) |
| `MPC_ACC_UP_MAX` / `MPC_ACC_DOWN_MAX` | 4 / 3 m/s² | vertical acceleration limits |
| `MPC_JERK_AUTO` | 4 m/s³ | jerk in auto modes: lower means smoother Mission and Return |
| `MPC_JERK_MAX` | 8 m/s³ | jerk in Position and Altitude (only with `MPC_POS_MODE` = 4); the maximum of 500 effectively removes the limit |
| `MPC_VEL_MANUAL` | 10 m/s | velocity at full stick in Position (must be below `MPC_XY_VEL_MAX` = 12) |

The order "rate first, then attitude, then velocity, then position" applies to this table as well: if the vehicle wobbles in Position, check `MPC_XY_VEL_P_ACC` first, not `MPC_XY_P`. Since 1.16 (and in 1.17) `MPC_POS_MODE` has two values, since 3 Smoothed velocity from 1.15 was removed: 0 Direct velocity (stick straight to velocity, for tuning the velocity loop) and 4 Acceleration based.

Acro rates and expo for an FPV pilot (`MC_ACRO_R_MAX` and others, default 100 deg/s, several times slower than what you are used to in Betaflight), stick response in Position (`MPC_VEL_MANUAL`, `MPC_MAN_Y_MAX`, `MAN_DEADZONE`) and in-flight gain adjustment from a radio knob (`RC_MAP_PARAM1…3`, QGC → Parameters → Set RC to Param) are covered in `px4-rc-tuning`. The rule for this module: a radio knob adjusts one parameter per flight (`MC_ROLLRATE_K` / `MC_PITCHRATE_K` or `MPC_XY_VEL_P_ACC`), and after landing you confirm the value with a step response recording, as in step 4.

### Autotune in more detail
`MC_AT_EN` = 1 enables the `mc_autotune_attitude_control` module (the default on a flight controller is 0: set 1 and reboot; SITL sets 1 itself); you start it from QGC (PID Tuning → Start AutoTune), and multicopter autotune has no radio switch (`FW_AT_MAN_AUX` is for fixed-wing only), in Altitude/Position, hovering in calm air; the module injects an excitation signal of amplitude `MC_AT_SYSID_AMP` (0.7) on each axis, identifies a model of the rate loop and computes the gains: it writes `MC_*RATE_P/I/D` (setting the `MC_*RATE_K` multiplier to 1.0) and `MC_ROLL_P`/`MC_PITCH_P`/`MC_YAW_P` (`saveGainsToParams()` in `src/modules/mc_autotune_attitude_control/mc_autotune_attitude_control.cpp`); `MC_AT_APPLY` (0 do not apply, logging only; 1 apply after disarm; 2 apply in the air) defaults to 1. Then a check flight and Flight Review: a response with no more than 10% overshoot, D without noise. Autotune does not tune the filters and does not cure vibration; do those **before** it (look at the spectrum!).

{{diagram:px4-tune-order-flow|Filters come before everything; autotune replaces manual rate and attitude P tuning, and the velocity and position loops are tuned after it, velocity first.}}

### Worked example: 7" 6S, 1.4 kg
Start: Generic Quad airframe, `CA_ROTOR_COUNT` = 4, check `IMU_GYRO_RATEMAX` = 800 Hz (the airframe already raised it from 400), `IMU_GYRO_CUTOFF` 40 → 80, `IMU_DGYRO_CUTOFF` 20 → 40 (the default was 30 before 1.17); eRPM from the ESCs: bidirectional DShot (in 1.18 `PWM_AUX_TIMn` = −6/−7/−8 for the motor group; in 1.16–1.17 `DSHOT_BIDIR_EN` = 1; works on supported boards and FMU outputs) or ESC telemetry over UART (`DSHOT_TEL_CFG`, the only option in 1.15), `IMU_GYRO_DNF_EN` = 1; `MPC_THR_HOVER` gets refined by the HTE; first flight in Stabilized, `MC_ROLLRATE_K` 1.0 → 0.7 if it wobbles; autotune; `MPC_XY_VEL_MAX` to suit the job. Log → Flight Review: rate tracking, spectrum, `vehicle_torque_setpoint` without saturation.

{{diagram:px4-cascade|The PX4 cascade: position → velocity → attitude → angular rate → allocator, with the parameters of each level.}}

### Place in the system

- **Takes in:** the filtered gyro `vehicle_angular_velocity` and the EKF2 estimate (`px4-architecture`); ESC RPM for the dynamic notch (`f-motors-esc`); the `CA_*` geometry (`px4-setup-scratch`); the theory of cascades and phase margin (`ctl-theory`).
- **Hands on:** torques and thrust to control allocation (`ctl-allocation`); the response to position and velocity setpoints to Offboard mode (`px4-ros2`); a log for the same step response metrics as in `bf-pid`.
- **If you get it wrong here:** you run autotune with vibration and no filters → noise in D, hot motors; look at the spectrum first (`ctl-signals`). You upgrade the firmware while on defaults → `MC_ROLL_P` silently becomes 4.0 instead of 6.5 → a softer attitude loop, Offboard setpoints are tracked differently; the upgrade table is in `px4-intro`.

## practice
### Step 1. Allocation first
Props off: in QGC Actuators, the geometry matches the frame and each motor spins in the right direction in the test.

### Step 2. Filters from the log
Fly with a log, then Flight Review → gyro spectrogram. Set `IMU_GYRO_CUTOFF` and `IMU_DGYRO_CUTOFF` to cut the motor noise without touching the control band.

### Step 3. Autotune
`MC_AT_EN` = 1 and a reboot (the default on a flight controller is 0), then QGC → PID Tuning → Start AutoTune. Multicopter autotune has no radio switch. Hover, start, do not touch the sticks until it finishes, land. Check that the new `MC_*RATE_*` values were applied.

### Step 4. Verification
Step response in Flight Review before and after: overshoot and settling time. If needed, adjust K/D by hand by 10–20%.

### What you should get and what to write down
- **Step 1.** In QGC → Actuators the frame diagram matches the real frame, and the test of each motor spins exactly that motor, in the direction shown in the picture. No amount of tuning fixes a mistake here.
- **Step 2.** On the gyro spectrogram in Flight Review the motor noise bands rise with throttle. The `IMU_GYRO_CUTOFF` cutoff frequency should be below those bands but well above the control band (a few to tens of hertz). Write down the values before and after, and the frequency of the motor band in a hover.
- **Step 3.** Autotune writes the new `MC_ROLLRATE_*`, `MC_PITCHRATE_*` gains only after it completes successfully. Compare them with the defaults and write down both versions.
- **Step 4.** Flight Review has a step response estimate for the rate loop. Write down the overshoot (%) and the rise time (ms) before and after.

### Lab
In SITL: record a step response with the default gains, deliberately double `MC_ROLLRATE_K`, record again, and explain the difference from the plot.

Expected picture: with `MC_ROLLRATE_K` doubled (the common multiplier of the loop's P, I and D) the response is faster and the overshoot larger, and the oscillation after the step takes longer to die out and has a higher frequency: the phase margin went down (the "Control theory" module). Give the steps as sharp roll stick inputs in Stabilized or Acro with the QGC virtual joystick, the same way in both flights.

Self-check: the lab is done when the frame diagram in Actuators matched the real one and in the props-off test each motor spins the right one in the right direction, the step response was recorded with the default gains and with `MC_ROLLRATE_K` doubled on identical sharp steps, with overshoot (%) and rise time (ms) numbers, and those numbers match the expected picture above: with K doubled the response is faster, the overshoot larger, the oscillation dies out more slowly and at a higher frequency.

**Reference answer for the self-check.** A correct explanation: `MC_ROLLRATE_K` is the common multiplier of the loop's P, I and D, and doubling it raises the gain and reduces the phase margin. Typical wrong results: (1) the two recordings barely differ: the steps were smooth or not the same, and you need sharp, identical roll stick inputs in Stabilized or Acro; (2) the overshoot came out smaller with K doubled: the recordings were mixed up or the wrong parameter was changed, so check the value of `MC_ROLLRATE_K` before the flight.

## diagnostics
- **Symptom:** fast oscillation after autotune
  - Possible cause: the noise was not filtered, so autotune fitted the gains to a noisy signal.
  - What to do: filters first, then autotune again.
- **Symptom:** the vehicle slowly "wobbles" in Position
  - Possible cause: the outer loop (`MPC_*`) is too aggressive for a weak inner loop.
  - What to do: rate/attitude first, then position.
- **Symptom:** hot motors
  - Possible cause: high D on a noisy gyro.
  - What to do: lower D, increase filtering, check the mechanics.
- **Symptom:** a motor spins the wrong way in the test
  - Possible cause: geometry or direction in Actuators.
  - What to do: fix `CA_ROTOR<n>_KM`/the direction, check again with the props off.
- **Symptom:** autotune aborts
  - Possible cause: wind, vibration, a starting tune that is too low, not enough altitude.
  - What to do: calm air, spectrum and notch before autotune, a lower `MC_ROLLRATE_K`, altitude 5+ m.
- **Symptom:** slow position oscillation in Position mode
  - Possible cause: `MPC_XY_P`/`MPC_XY_VEL_*` higher than the GPS quality and latency allow.
  - What to do: check the EKF (innovations), lower `MPC_XY_VEL_P_ACC`, then `MPC_XY_P`.

## references
- PX4 Multicopter PID Tuning Guide (Advanced) | https://docs.px4.io/v1.17/en/config_mc/pid_tuning_guide_multicopter.html | primary | A
- PX4 Multicopter PID Tuning Guide (Basic) | https://docs.px4.io/v1.17/en/config_mc/pid_tuning_guide_multicopter_basic.html | primary | A
- PX4 Autotuning (Multicopter) | https://docs.px4.io/v1.17/en/config/autotune_mc.html | primary | A
- PX4 Control Allocation | https://docs.px4.io/v1.17/en/concept/control_allocation.html | primary | A

## checklist
- I understand the position → attitude → rate → allocation cascade
- I know the role of `MC_*RATE_K` and how it differs from Betaflight
- Allocation checked with the props off
- Autotune done and the result checked against the step response
