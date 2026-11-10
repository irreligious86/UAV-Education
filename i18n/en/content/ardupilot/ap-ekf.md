---
id: ap-ekf
title: "EKF and Navigation"
level: L3
readingTime: 25 min
firmware: ArduPilot 4.5+
status: published
added: 2026-11-07
tags:
  - EKF3
  - navigation
  - GPS
related:
  - ap-missions
  - ap-logs
next:
  - ap-logs
source: content/ardupilot/ap-ekf.md
source_hash: 9fc6e76e75ef
---

## summary
The EKF is a filter that takes noisy and contradictory sensors and builds one consistent picture out of them: where the vehicle is, where it is going and how it is oriented. When ArduPilot “won't arm because of the EKF”, “drifts in LOITER” or “flies away on a GPS glitch”, the cause is almost always here. This module explains what the filter does, how to choose data sources, what variances and lane switching are, and how to read its health in the GCS and in logs. A real-world example: a HeeWing with no compass and an unstable GPS.

## theory
### Why a filter
A gyroscope is accurate over short intervals but drifts. GPS does not drift, but it is noisy and updates rarely. A barometer knows the altitude but lies in wind and when it heats up. A compass knows the heading but is afraid of current. The EKF (extended Kalman filter) predicts the state from the inertial sensors thousands of times per second and corrects the prediction with the infrequent GPS, baro and compass measurements, weighting them by their declared noise. A measurement too far from the prediction is rejected by the filter — that is how GPS glitches are handled.

### EKF3, DCM and lane switching
- `AHRS_EKF_TYPE = 3` — EKF3 is the main estimator; DCM (a simple complementary filter) runs in the background as a backup.
- Each IMU in `EK3_IMU_MASK` gets its own core (“lane”). The healthiest one is used; when one core degrades, the filter switches to another. `EK3_PRIMARY` selects the starting one.
- Plane and Rover fall back to DCM when the EKF is unhealthy; Copter does not — it has the EKF failsafe instead.

### Sources
Where position, velocity, altitude and heading come from is set by `EK3_SRC1_*`:

{{diagram:estimation-sources|EKF3 merges all the sensors into one estimate: the IMU drives the prediction, the other sources correct it through innovation gates.}}

- `EK3_SRC1_POSXY`: 0 — none, 3 — GPS, 4 — Beacon, 6 — ExternalNav.
- `EK3_SRC1_VELXY`: in addition 5 — OpticalFlow, 7 — WheelEncoder.
- `EK3_SRC1_POSZ`: 1 — Baro, 2 — RangeFinder, 3 — GPS.
- `EK3_SRC1_YAW`: 1 — Compass, 2 — GPS, 3 — GPS with fallback to compass, 8 — GSF (heading estimated from GPS velocity without a compass).

The `SRC2`/`SRC3` sets can be switched in flight with a switch — for example, GPS outdoors and optical flow indoors.

### Variances and failsafe
The filter estimates its own uncertainty for compass, velocity, position and height. When the normalized variance exceeds `FS_EKF_THRESH` (0.8 by default, 0.6 is strict, 1.0 is lenient), the EKF failsafe triggers with the `FS_EKF_ACTION` action: 1 — land if the mode requires position; 2 — AltHold; 3 — land from any mode. The same variances are used in pre-arm: “EKF variance” at arming is a signal of a bad compass or GPS, not a reason to raise the threshold.

### What requires position
LOITER, AUTO, GUIDED, RTL, PosHold need a healthy position estimate. STABILIZE, ALT_HOLD, ACRO do not. Hence the rule from the ArduPilot module: you choose the mode by which sensors you trust.

### Case: flying without a compass and without trusting GPS
A HeeWing T1 on a stock F405: there is no compass on board at all, and GPS behaved erratically during setup. Instead of forcing the EKF to work with an unreliable heading, the decision was to disable EKF3 and fly on DCM: the vehicle arms and is controlled in modes that do not need position (MANUAL, FBWA, ACRO, QSTABILIZE, QLAND), and altitude and position hold are deliberately not used. An alternative for the future, once GPS is stable: `EK3_SRC1_YAW = 8` (GSF) — heading from GPS without a compass, but it only becomes available while moving.

### How to read EKF health from the log
`XKF4` (per core): `SV`, `SP`, `SH`, `SM` — the square root of the test ratio, i.e. the ratio of the innovation to the allowed one (by the gates `EK3_VEL_I_GATE`, `EK3_POS_I_GATE`, `EK3_HGT_I_GATE`, `EK3_MAG_I_GATE`, in %): < 0.5 — healthy, around 1 — the measurement is on the edge of rejection, > 1 — rejected; `SS` — the solution status bitmask (which sources are in use); `PI` — the active core; `XKF3` — the innovations themselves (`IVN/IVE/IVD` velocity, `IPN/IPE/IPD` position, `IMX/IMY/IMZ` compass); `XKF2` — the estimated accelerometer bias, wind and magnetic field; `XKF1` — the state (angles, velocities, position) and gyro bias (`GX/GY/GZ`). The messages `EKF3 IMU0 … yaw re-aligned`, `… ground mag anomaly` are automatic resets (normal if rare, suspicious if frequent). For the math in detail see the “Kalman Filter” module; for practical degradation scenarios see “Navigation Robustness”.

### Parameters people actually tune
`EK3_GPS_CHECK` (GPS quality checks before trusting it), `GPS1_DELAY_MS`/`EK3_FLOW_DELAY`/`EK3_HGT_DELAY` (measurement delay, ms), `EK3_ALT_SOURCE`→`EK3_SRC1_POSZ`, `EK3_RNG_USE_HGT` (% of height for the rangefinder), `EK3_GLITCH_RAD` (25 m: beyond that — reset to GPS), `EK3_MAG_CAL` (when to calibrate the field in flight), `EK3_FLOW_USE`, `EK3_SRC_OPTIONS`. Measurement noise (`EK3_*_M_NSE`) and process noise (`EK3_*_P_NSE`) — only after you understand the Kalman module, and with before/after logs.

### Worked example: “EKF variance” in Loiter over a parking lot
`XKF4.SM` = 1.3 and rising with throttle, `MAG.MagZ` correlates with `CTUN.ThO`, `GPS.NSats` 14, `SP` 0.2 → the compass is affected by the power wires (the parking lot's metal is secondary). Solution: compassmot/moving the compass onto a mast (the “Interference” module), `EK3_SRC1_YAW = 3` (GPS with fallback to compass) as insurance; leave `FS_EKF_THRESH` alone.

## practice
### Checking EKF health
1. In Mission Planner — the EKF window (a button on the HUD): the variance bars should be green and low.
2. In MAVProxy: the `EKF3 IMU0 ...` messages at startup — wait for “using GPS” before arming in position modes.
3. Pre-arm “EKF compass variance” or “EKF velocity variance” — look for the cause in the compass (interference, calibration) or GPS (few satellites, HDOP).

### Lab in SITL: a GPS glitch
1. Take off in LOITER to 20 m.
2. Inject a glitch with the simulator's `SIM_GPS*` parameters (current names: `param show SIM_GPS*`).
3. Watch: the vehicle should hold on inertia and reject the measurement; an `ERR` with the GPS subsystem will appear in the log.
4. Make the glitch stronger until the EKF failsafe triggers and make sure `FS_EKF_ACTION` does what you chose.

### Lab: sources
Switch `EK3_SRC1_YAW` from 1 to 8 in SITL and see how the heading behaves on the ground and after the vehicle starts moving.

### What you should end up with and what to record
- **A small glitch** (a GNSS position jump of a few meters): the EKF rejects the measurement, and the vehicle holds on inertia and the other sensors. In the log, an `ERR` with the GPS subsystem (`Subsys` 11, `ECode` 2 — `GPS_GLITCH`; after recovery — `ECode` 0), and in `XKF3` or `XKF4` the normalized position innovation grows. The vehicle's position in `POS` barely twitches — record by how much.
- **A large and long glitch:** the innovations do not come back, the variances rise above the `FS_EKF_THRESH` threshold, the EKF failsafe triggers (subsystem 17), and the `FS_EKF_ACTION` action runs (1 — land, 2 — AltHold, both only if the current mode requires position; 3 — land from any mode, even from STABILIZE). Record the time from the start of the glitch to the failsafe and what the vehicle did.
- **Heading without a compass.** `EK3_SRC1_YAW = 8` — heading from the GSF estimator, which derives it from GNSS motion. On the ground the heading is undefined or inaccurate; after the flight starts it converges within seconds of movement. Compare with `EK3_SRC1_YAW = 1` (compass): how many seconds and meters of flight GSF needed.

The lab counts as done when the glitch is injected with `SIM_*` parameters and the log has an `ERR` for the GPS subsystem, the vehicle held on inertia (with the deviation recorded), and the EKF failsafe was triggered on purpose and the `FS_EKF_ACTION` action verified.

## diagnostics
- **Symptom:** pre-arm “EKF compass variance”
  - Possible cause: interference from power wires, a bad calibration, the compass in the GPS module is rotated.
  - What to do: calibrate in a clean spot, move the compass away, check the orientation.
- **Symptom:** in LOITER the vehicle slowly drifts or “circles” (toilet-bowls)
  - Possible cause: a heading error (compass) with good GPS.
  - What to do: check the discrepancy between compass and GPS heading in the log, recalibrate.
- **Symptom:** a sudden lurch to the side in position modes
  - Possible cause: a GPS glitch accepted by the filter.
  - What to do: look at `ERR`/GPS in the log, HDOP and the satellite count, the GPS antenna.
- **Symptom:** EKF failsafe and a landing in the middle of a flight
  - Possible cause: variances above the threshold — vibration, compass or GPS.
  - What to do: analyze the log (the next module), do not raise `FS_EKF_THRESH` blindly.

## references
- Extended Kalman Filter (EKF) — ArduPilot | https://ardupilot.org/copter/docs/common-apm-navigation-extended-kalman-filter-overview.html | primary | A
- EKF Failsafe — ArduPilot Copter | https://ardupilot.org/copter/docs/common-ekf-inav-failsafe.html | primary | A
- EKF source parameters (AP_NavEKF_Source.cpp, GitHub) | https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_NavEKF/AP_NavEKF_Source.cpp | primary | A

## checklist
- I know which modes require position
- I can view EKF variances in the GCS
- I understand what `EK3_SRC1_*` sets
- I fix EKF pre-arm failures at the cause, not with the threshold
- I ran a GPS glitch and an EKF failsafe in SITL
