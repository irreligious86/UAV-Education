---
id: ap-ekf
title: "EKF and navigation"
level: L3
readingTime: 25 min
firmware: ArduPilot 4.7 (checked against 4.7.3)
status: published
added: 2026-11-07
tags:
  - EKF3
  - navigation
  - GPS
related:
  - ap-missions
  - ap-logs
  - ap-ahrs-choice
next:
  - ap-ahrs-choice
source: content/ardupilot/ap-ekf.md
source_hash: 117eb1e892ce
---

## summary
The EKF is the filter that turns noisy, contradictory sensors into one consistent picture: where the vehicle is, where it is going, and how it is oriented. When ArduPilot "won't arm because of the EKF", "drifts in LOITER", or "flies off on a GPS glitch", the cause is almost always here. This module explains what the filter does, how to choose its data sources, what variances and lane switching are, and how to read its health in the GCS and in logs. The practical example is a HeeWing with no compass and an unstable GPS.

{{lesson:ap-ahrs-choice|How to choose between EKF3 and DCM, set up source sets, and work out why the EKF is complaining: a long lesson with GPS, IMU, and compass failure runs in SITL.}}

## theory
### Why a filter
A gyro is accurate over short intervals but drifts. GPS does not drift, but it is noisy and updates slowly. A barometer knows the altitude but is wrong in wind and when it heats up. A compass knows the heading but is disturbed by current. The EKF (extended Kalman filter) predicts the state from the inertial sensors hundreds of times per second and corrects that prediction with the infrequent GPS, baro, and compass measurements, weighting each by its stated noise. A measurement that is too far from the prediction is rejected, and that is how GPS glitches are handled.

### EKF3, DCM, and lane switching
- `AHRS_EKF_TYPE = 3` selects EKF3 as the main estimator; DCM (a simple complementary filter) runs in the background as the backup.
- Each IMU in `EK3_IMU_MASK` gets its own core ("lane"). The healthiest one is used; when one core degrades, the filter switches to another. `EK3_PRIMARY` selects the core used on startup.
- The fallback to DCM depends on the vehicle type. Copter has none; it has the EKF failsafe instead. Plane (and VTOL) falls back to DCM when EKF3 is unhealthy or loses navigation (position). On Rover in 4.7 the default `AHRS_OPTIONS = 3` disables the fallback on loss of navigation: it goes to DCM only if EKF3 is unhealthy or has no attitude.

The exact fallback conditions, whether EKF2 is still alive, and which estimator and source set to choose for your vehicle are covered in the `ap-ahrs-choice` module.

### Sources
`EK3_SRC1_*` sets where position, velocity, height, and yaw come from:

{{diagram:estimation-sources|EKF3 fuses all sensors into one estimate: the IMU drives the prediction, and the other sources correct it through innovation gates.}}

- `EK3_SRC1_POSXY`: 0 None, 3 GPS, 4 Beacon, 6 ExternalNav.
- `EK3_SRC1_VELXY`: the same plus 5 OpticalFlow and 7 WheelEncoder.
- `EK3_SRC1_POSZ`: 1 Baro, 2 RangeFinder, 3 GPS.
- `EK3_SRC1_YAW`: 1 Compass, 2 GPS, 3 GPS with Compass Fallback, 8 GSF (a yaw estimate from GPS velocity, without a compass).

The `SRC2`/`SRC3` sets are selected in flight with a switch, for example GPS outdoors and optical flow indoors.

### Variances and the failsafe
The filter estimates its own uncertainty in compass, velocity, position, and height. When two of the compass, velocity and position variances exceed `FS_EKF_THRESH` (0.8 Default, 0.6 Strict, 1.0 Relaxed), or velocity alone exceeds twice it (without healthy optical flow), or there is no position estimate, for about 1 s (10 checks at 10 Hz; height is not used here), the EKF failsafe triggers with the action from `FS_EKF_ACTION`: 0 reports only (this value appeared in 4.7); 1 switches to Land if the current mode requires position; 2 switches to AltHold; 3 switches to Land from all modes. The pre-arm check is stricter: any single variance above the threshold, height included, blocks arming; "EKF variance" when arming points to a bad compass or GPS and is not a reason to raise the threshold.

### What requires position
LOITER, AUTO, GUIDED, RTL, and PosHold need a healthy position estimate. STABILIZE, ALT_HOLD, and ACRO do not. Hence the rule from the ArduPilot intro module: you choose a mode by which sensors you trust.

### Case: flying with no compass and no trust in the GPS
A HeeWing T1 on its stock F405: there is no compass on board at all, and the GPS was unstable during setup. Instead of forcing the EKF to work with an unreliable heading, the decision was to disable EKF3 and fly on DCM: the aircraft arms and is controlled in the modes that need no position (MANUAL, FBWA, ACRO, QSTABILIZE, QLAND), and altitude and position hold are deliberately not used. The alternative for later, once the GPS is stable: `EK3_SRC1_YAW = 8` (GSF), which gives a heading from GPS without a compass, but only once the aircraft is moving.

### Reading EKF health in a log
`XKF4` (per core): `SV`, `SP`, `SH`, `SM` are the square root of the test ratio, that is, the ratio of the innovation to the allowed one (set by the gates `EK3_VEL_I_GATE`, `EK3_POS_I_GATE`, `EK3_HGT_I_GATE`, `EK3_MAG_I_GATE`, in %): < 0.5 is healthy, around 1 the measurement is on the edge of rejection, > 1 it is rejected; `SS` is the filter solution status bitmask (which sources are in use); `PI` is the primary core index; `XKF3` holds the innovations themselves (`IVN/IVE/IVD` velocity, `IPN/IPE/IPD` position, `IMX/IMY/IMZ` magnetic field); `XKF2` holds the estimated accelerometer bias, the wind, and the magnetic field; `XKF1` holds the state (angles, velocities, position) and the gyro bias (`GX/GY/GZ`). Messages such as `EKF3 IMU0 yaw aligned` and `EKF3 IMU0 MAG0 ground mag anomaly, yaw re-aligned` are automatic resets (normal when rare, suspicious when frequent). The math is covered in the "Kalman filter" module, and practical degradation scenarios in "Navigation resilience".

### Parameters you actually tune
`EK3_GPS_CHECK` (GPS quality checks before the filter trusts it), `GPS1_DELAY_MS`/`EK3_FLOW_DELAY`/`EK3_HGT_DELAY` (measurement delay, ms), `EK3_ALT_SOURCE`→`EK3_SRC1_POSZ`, `EK3_RNG_USE_HGT` (% of the rangefinder's maximum range), `EK3_GLITCH_RAD` (25 m: beyond it the states are reset to the GPS), `EK3_MAG_CAL` (when to learn the magnetic field in flight), `EK3_FLOW_USE`, `EK3_SRC_OPTIONS`. Touch the measurement noise (`EK3_*_M_NSE`) and process noise (`EK3_*_P_NSE`) only after you understand the Kalman module, and with before/after logs.

### Worked example: "EKF variance" in Loiter over a parking lot
`XKF4.SM` = 1.3 and rising with throttle, `MAG.MagZ` correlates with `CTUN.ThO`, `GPS.NSats` is 14, `SP` is 0.2 → the compass is affected by the power wiring (the metal of the parking structure is secondary). The fix: compassmot or moving the compass onto a mast (see the "Interference" module), with `EK3_SRC1_YAW = 3` (GPS with Compass Fallback) as insurance; leave `FS_EKF_THRESH` alone.

### Place in the system

- **Receives:** IMU readings for the prediction and GPS, baro, and compass for the correction, whose errors and calibrations are covered in `est-sensors` and `est-gnss`; the frame vibration level (`ap-heavy`) and compass interference from the power wiring (`el-emi`).
- **Provides:** position, velocity, and attitude to the LOITER, AUTO, GUIDED, and RTL modes (`ap-missions`, `ap-companion`); variances to the pre-arm checks and the EKF failsafe (`ap-safety-fs`); the `XKF1…XKF4` messages to the log (`ap-logs`).
- **If you get it wrong here:** a compass next to the power wiring → `XKF4.SM` rises with throttle → "EKF variance" in Loiter; you fix it by moving the compass (`el-emi`), not with the `FS_EKF_THRESH` threshold. No healthy position → RTL on radio loss degrades to Land or AltHold (`ap-safety-fs`).

## practice
### Checking EKF health
1. In Mission Planner, open the EKF status window from the HUD: the variance bars should be green and low.
2. In MAVProxy: watch the `EKF3 IMU0 ...` messages at startup and wait for "is using GPS" before arming in a mode that requires position.
3. On a pre-arm "EKF compass variance" or "EKF velocity variance", look for the cause in the compass (interference, calibration) or the GPS (few satellites, HDOP).

### SITL lab: GPS glitch
1. Take off in LOITER to 20 m.
2. Inject a glitch with the simulator's `SIM_GPS*` parameters (get the current names with `param show SIM_GPS*`).
3. Watch: the vehicle should hold on inertial data and reject the measurement; an `ERR` with the GPS subsystem appears in the log.
4. Increase the glitch until the EKF failsafe triggers and confirm that `FS_EKF_ACTION` does what you selected.

### Lab: sources
Switch `EK3_SRC1_YAW` from 1 to 8 in SITL and see how the heading behaves on the ground and once the vehicle starts moving.

### What you should get and what to record
- **A small glitch** (a GNSS position jump of a few meters): the EKF rejects the measurement, and the vehicle holds on inertial data and the remaining sensors. The log has an `ERR` with the GPS subsystem (`Subsys` 11, `ECode` 2, which is `GPS_GLITCH`; after recovery, `ECode` 0), and the normalized position innovation rises in `XKF3` or `XKF4`. The vehicle position in `POS` barely moves; record by how much.
- **A large, long glitch:** the innovations do not come back, the variances rise above `FS_EKF_THRESH`, the EKF failsafe triggers (subsystem 17), and the `FS_EKF_ACTION` action is carried out (1 is Land and 2 is AltHold, both only if the current mode requires position; 3 is Land from all modes, even from STABILIZE). Record the time from the start of the glitch to the failsafe and what the vehicle did.
- **Yaw without a compass.** `EK3_SRC1_YAW = 8` takes the yaw from the GSF estimator, which derives it from GNSS movement. On the ground the yaw is undefined or inaccurate; once the flight starts it converges within seconds of movement. Compare with `EK3_SRC1_YAW = 1` (compass): how many seconds and meters of flight GSF needed.

Self-check: the lab is done when the glitch was injected with the `SIM_GPS*` parameters and the log has an `ERR` with `Subsys` 11, `ECode` 2 (after recovery, `ECode` 0), with a small glitch the position in `POS` barely moved and the deviation is recorded as a number, the EKF failsafe was triggered deliberately (the log has an `ERR` for subsystem 17, the time from the start of the glitch to the trigger is recorded, and the vehicle did exactly what `FS_EKF_ACTION` specifies), and for `EK3_SRC1_YAW = 8` you recorded how many seconds and meters of flight GSF needed for the yaw to converge.

**Reference for the self-check.** A correct result: a small glitch gives `ERR` 11/2 with no mode change, a large, long one gives an `ERR` for subsystem 17 and the `FS_EKF_ACTION` action. Typical wrong results: (1) the variances rose but nothing happened, because you selected 1 or 2 and the current mode does not require position (STABILIZE, ALT_HOLD): only 3 lands from any mode; (2) with `EK3_SRC1_YAW = 8` the yaw on the ground is undefined or inaccurate, which is not an error: GSF derives the yaw from GNSS movement and converges only after the flight starts.

## diagnostics
- **Symptom:** pre-arm "EKF compass variance"
  - Possible cause: interference from the power wiring, a poor calibration, the compass in the GPS module mounted rotated.
  - What to do: calibrate in a clean location, move the compass away, check its orientation.
- **Symptom:** in LOITER the vehicle slowly drifts or circles ("toilet bowling")
  - Possible cause: a heading error (compass) with a good GPS.
  - What to do: check the difference between the compass heading and the GPS heading in the log, recalibrate.
- **Symptom:** a sudden lurch sideways in position modes
  - Possible cause: a GPS glitch accepted by the filter.
  - What to do: look at `ERR`/GPS in the log, HDOP and the satellite count, the GPS antenna.
- **Symptom:** EKF failsafe and a landing in the middle of a flight
  - Possible cause: variances above the threshold because of vibration, the compass, or the GPS.
  - What to do: analyze the log (next module); do not raise `FS_EKF_THRESH` blindly.

## references
- Extended Kalman Filter (EKF) — ArduPilot | https://ardupilot.org/copter/docs/common-apm-navigation-extended-kalman-filter-overview.html | primary | A
- EKF Failsafe — ArduPilot Copter | https://ardupilot.org/copter/docs/common-ekf-inav-failsafe.html | primary | A
- EKF source parameters (AP_NavEKF_Source.cpp, GitHub) | https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_NavEKF/AP_NavEKF_Source.cpp | primary | A

## checklist
- I know which modes require position
- I can view the EKF variances in the GCS
- I understand what `EK3_SRC1_*` sets
- I resolve EKF pre-arm failures by their cause, not with the threshold
- I have run a GPS glitch and the EKF failsafe in SITL
