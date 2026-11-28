---
id: nav-indoor
title: "Without GNSS: optical flow, UWB, motion capture and external navigation in the EKF"
level: L3
readingTime: 50 min
firmware: ArduCopter 4.7 (checked against 4.7.3; the lab was captured on 4.6.3) · PX4 1.18 (parameters checked against v1.18.0)
status: published
tags:
  - ExternalNav
  - optical flow
  - UWB
  - motion capture
  - EK3_SRC
  - VISO_DELAY_MS
related:
  - est-alt-sources
  - ap-ekf
  - est-kalman
  - nav-resilience
  - ros2-ardupilot
  - ap-sitl
next:
  - per-visual-nav
source: content/estimation/nav-indoor.md
source_hash: 8249c6935450
---

## summary
Indoors, under a bridge and in a hangar there is no GNSS, yet Loiter, Guided and Auto still need a position. This module puts four ways of giving the EKF a position without satellites into one picture (optical flow with a rangefinder, UWB beacons, motion capture and an external pose over MAVLink) and works through the traps of the first launch: coordinate frames, delay and `VISO_DELAY_MS`, resets, arming without GPS, and the origin. The lab: ArduCopter 4.6.3 in SITL without GPS flies on `VISION_POSITION_ESTIMATE` generated from the truth with noise and lag; a delay sweep shows where the EKF starts rejecting data and what breaks first; separately, a source jump with and without `reset_counter`, swapped axes, and arming without an origin. Then the move to hardware: flow with a rangefinder in a room, UWB and mocap, with acceptance criteria.

## theory
### What exactly we are replacing
GNSS gives the EKF position, velocity, sometimes altitude and heading. Without it the inertial solution drifts by meters within seconds, so every one of these quantities has to come from somewhere else. Innovation gates and the "delayed time horizon" are covered in est-kalman, EKF health from `XKF4` in ap-ekf, and the signatures of a GNSS failure in nav-resilience; here only what is specific to flying without satellites.

| Source | What it gives the EKF | Accuracy / range | Heading | Where it breaks |
|---|---|---|---|---|
| Optical flow + rangefinder | XY velocity (no position, so it drifts) | 1–3% of distance traveled; height up to the rangefinder's range | compass or nothing | smooth floor, darkness, water, height |
| Beacons: UWB (Pozyx, Nooploop), ultrasonic (Marvelmind) | XY(Z) position from ranges to ≤ 4 anchors | 10–30 cm in line of sight | needs a compass | reflections, metal, anchors in one plane → poor Z |
| Motion capture (OptiTrack, Vicon, Nokov) | rigid-body position and attitude | 0.1–1 mm, 100–360 Hz | from mocap | leaving the volume, glare, network |
| On-board VIO / SLAM | position, velocity, attitude | 0.5–2% of distance traveled | from VIO | poor texture, resets (per-visual-nav) |

{{diagram:nav-indoor-sources|Four paths into EKF3 meet in one place, the EK3_SRC1_* set: each source has its own driver, its own delay and its own POSXY / VELXY / YAW values; pick the wrong row and you get "Need Position Estimate".}}

### EK3_SRC: who is responsible for what
The values (`AP_NavEKF_Source.cpp`, the same in 4.6.3 and 4.7.3): `EK3_SRC1_POSXY`: 0 None, 3 GPS, 4 Beacon, 6 ExternalNav; `EK3_SRC1_VELXY`: the same plus 5 OpticalFlow and 7 WheelEncoder; `EK3_SRC1_POSZ`: 0, 1 Baro, 2 RangeFinder, 3 GPS, 4 Beacon, 6 ExternalNav; `EK3_SRC1_VELZ`: 0, 3, 4, 6; `EK3_SRC1_YAW`: 0, 1 Compass, 2 GPS, 3 GPS with Compass Fallback, 6 ExternalNav, 8 GSF. `EK3_SRC_OPTIONS`: bit 0 FuseAllVelocities (cleared by default in 4.7, `EK3_SRC_OPTIONS = 0`; in 4.6 it was set, value 1), bit 1 AlignExtNavPosWhenUsingOptFlow, bit 3 UsePerCoreEKFSources (since 4.7: each EKF core gets its own source set). The three sets and the `RCx_OPTION = 90` switch are covered in est-alt-sources.

| Scenario | POSXY | VELXY | POSZ | VELZ | YAW |
|---|---|---|---|---|---|
| Flow + rangefinder | 0 | 5 | 1 (or 2 low over a flat floor) | 0 | 1 |
| UWB | 4 | 0 | 4 or 1 | 0 | 1 |
| Mocap / VIO through `VISO_*` | 6 | 6 if you send velocity; otherwise 0 | 6 | 6 or 0 | 6 |
| Mocap as pseudo-GPS (`GPS_INPUT`) | 3 | 3 | 3 | 3 | 2 |

Indoors, rebar makes the compass wrong by tens of degrees: with mocap, take heading from it as well (`EK3_SRC1_YAW = 6`, `COMPASS_USE = 0`); with flow and UWB the compass remains the weak spot.

### Optical flow as a velocity source
The sensor outputs the angular rate of the image (rad/s); the velocity over the floor is `v = (flow − ω_gyro) · h` (est-alt-sources), so there is no flow without a rangefinder. Parameters: `FLOW_TYPE` (1 PX4Flow, 2 Pixart, 4 CXOF, 5 MAVLink, 6 DroneCAN, 7 MSP, 8 UPFLOW, 10 SITL), `FLOW_ORIENT_YAW` (centidegrees), `FLOW_POS_X/Y/Z`, the scale `FLOW_FXSCALER` / `FLOW_FYSCALER` in parts per thousand: the flow is multiplied by `1 + FXSCALER/1000`, range ±800. In the EKF: `EK3_FLOW_USE` (1 navigation, 2 terrain estimation only), `EK3_FLOW_DELAY` (10 ms by default, 0–250), `EK3_FLOW_M_NSE` (0.25 rad/s), `EK3_FLOW_I_GATE` (300 = 3σ), `EK3_FLOW_MAX` (2.5 rad/s; before 4.7, `EK3_MAX_FLOW`).

Two consequences. The EKF limits ground speed: `ekfGndSpdLimit = (EK3_FLOW_MAX − 1) · h`, which is 1.5 m/s at a height of 1 m. And flow gives no position (`POSXY = 0`): the EKF integrates velocity, the hold point creeps, and Loiter will not climb above `RNGFND1_MAX` (meters; before 4.7, `RNGFND1_MAX_CM` in centimeters).

### External position: three doors into one EKF
- **`VISO_TYPE = 1` (MAVLink).** Accepted messages: `VISION_POSITION_ESTIMATE`, `GLOBAL_VISION_POSITION_ESTIMATE`, `VICON_POSITION_ESTIMATE`, `ATT_POS_MOCAP` (position + attitude), `VISION_SPEED_ESTIMATE` and `ODOMETRY` (pose + velocity; only with `frame_id = MAV_FRAME_LOCAL_FRD` and `child_frame_id = MAV_FRAME_BODY_FRD`, otherwise the message is silently dropped). `VISO_TYPE = 2` is the T265, 3 is VOXL. Noise: the covariance from the message, but no lower than `VISO_POS_M_NSE` (0.2 m), `VISO_YAW_M_NSE` (0.2 rad), `VISO_VEL_M_NSE` (0.1 m/s); a `NaN` in `covariance[0]` means "take it from the parameters." The EKF accepts a pose no more often than once every 20 ms (`extNavIntervalMin_ms`), so sending faster than 50 Hz is pointless.
- **`GPS_INPUT` (`GPS1_TYPE = 14`).** A bridge turns the pose into lat/lon/alt and velocities; the EKF thinks it is GPS (`EK3_SRC1_* = 3`). Heading is the `yaw` field in centidegrees, where 0 means "no heading" and north is encoded as 36000. The delay is `GPS1_DELAY_MS`. The official Vicon example works this way; it also runs on boards with 1 MB of flash, but there is no `reset_counter` and no attitude.
- **AP_DDS (ROS 2).** The `/ap/tf` topic (`tf2_msgs/TFMessage`); only the `odom → base_link` transform is used; the conversion in the code is `x, −y, −z`, so the X axis of your `odom` must point to the EKF's "north." There is no jitter correction (a TODO in the code), the error is 0, and there are no resets. Setting up AP_DDS is covered in ros2-ardupilot. Through MAVROS: `/mavros/vision_pose/pose` (ENU) → `VISION_POSITION_ESTIMATE` (NED), with the conversion done by the plugin.

### Trap 1: coordinate frames
ArduPilot expects position in NED relative to the origin and attitude as "nose–right–down" (FRD). ROS and almost every mocap system output ENU / FLU, and OptiTrack defaults to Y up. ENU → NED: `N = y`, `E = x`, `D = −z`, `yaw_NED = π/2 − yaw_ENU`. An axis mistake is invisible on the ground: at (0, 0, 0) any axes agree, and pre-arm passes (step 5). There is one check before the props go on: carry the vehicle by hand 1 m forward along the hall's "north," 1 m to the right, and lift it by 0.5 m; `LOCAL_POSITION_NED` should show `x +1`, `y +1`, `z −0.5`, and a clockwise turn seen from above should increase yaw.

### Trap 2: time and delay
The EKF fuses a measurement with the state at the moment it was taken. It computes the measurement time as `t = t_received(after jitter correction) − VISO_DELAY_MS − half a filter step`. The message's `usec` field is used **only to remove jitter** (`JitterCorrection`: the fastest packet is assumed to have arrived with zero delay). The flight controller cannot learn the constant camera → tracking → network → UART delay from the timestamps, even with perfectly synchronized clocks; all of it goes into `VISO_DELAY_MS` (10 ms by default). The limit is hard: at initialization the EKF takes `min(VISO_DELAY_MS, 250)` and sizes the IMU buffer (the fusion horizon) for it, so 250 ms is the maximum. The parameter itself is subtracted from each packet's time immediately, without a reboot, but the timestamp cannot go deeper than the horizon allocated at boot (`MAX(timeStamp_ms, imuDataDelayed.time_ms)`), so reboot after increasing `VISO_DELAY_MS`. An uncompensated remainder Δτ makes the estimate lag by `e ≈ v · Δτ` and, worse, adds phase lag to the position loop.

### Trap 3: resets and jumps
SLAM after a loop closure, or mocap after recalibration, shifts the pose in a jump. To the EKF this is a glitch: measurements outside the gate are rejected (`XKF4.SP > 1`), and when the gate opens, the vehicle flies off to "correct" the error. The right way is to increment `reset_counter` in the same message: the EKF instantly moves the position (`posReset`), and the position controller shifts the target along with it. `GPS_INPUT`, `VICON_POSITION_ESTIMATE`, `ATT_POS_MOCAP` and `/ap/tf` have no counter. The gate: `(ΔN² + ΔE²) < (EK3_POS_I_GATE/100)² · (var_N + var_E)`, `var = P + VISO_POS_M_NSE²`; with 500 and σ = 0.2 m it is about 1.5 m.

### Trap 4: arming and the origin
Without GPS the EKF has no lat/lon origin, and without one there is no "home": pre-arm answers `AHRS: waiting for home`. The GCS or a script sets the origin with a `SET_GPS_GLOBAL_ORIGIN` message (lat/lon in 1e-7°, altitude in mm), once: a second attempt gives `EKF3: origin already set`, and only a reboot changes it. The coordinates must be plausible (the magnetic declination comes from them) but not precise. Beacons take the origin from `BCN_LATITUDE/LONGITUDE/ALT` on their own. `AHRS_OPTIONS` bit 3 records the origin (in `AHRS_ORIGIN_LAT/LON/ALT`), and bit 4 restores it at boot without GPS; both bits are new in 4.7. The rest of pre-arm: `VisOdom: not healthy` if no pose has arrived for 300 ms; `Need Position Estimate` if the EKF has not taken the source yet. There is no need to skip checks with `ARMING_SKIPCHK` (before 4.7, `ARMING_CHECK`): in the lab, arming in Loiter passes with `ARMING_CHECK = 1` and `GPS1_TYPE = 0`.

### UWB beacons
`BCN_TYPE`: 1 Pozyx, 2 Marvelmind (ultrasonic, handled by the same beacon library), 3 Nooploop (10 is SITL), connected over UART with `SERIALx_PROTOCOL = 13`. No more than four anchors (`AP_BEACON_MAX_BEACONS = 4`): that is one room or hall, not a warehouse. The anchors go in a rectangle; the origin is the anchor with the lowest ID (Pozyx) or anchor 0 (Nooploop); `BCN_ORIENT_YAW` is the compass heading from the origin to the second anchor. In the EKF: `EK3_BCN_M_NSE` (1 m), `EK3_BCN_I_GTE` (500), `EK3_BCN_DELAY` (50 ms; for Nooploop the documentation sets 20). The compass is mandatory: the EKF starts using beacons only after yaw alignment. Anchors at one height do not observe Z; then use `EK3_SRC1_POSZ = 1`. Since 4.7 the beacon driver is in the standard build only on boards with more than 2 MB of program space (`AP_BEACON_ENABLED`): ordinary boards with 2 MB of flash do not have it, and you need your own build (custom build server).

### Mocap through ROS 2
The chain: cameras → tracking software (Motive, Tracker) → network (NatNet / VRPN) → a ROS 2 node publishing the rigid body's `PoseStamped` → MAVROS `vision_pose` or AP_DDS `/ap/tf` → the flight controller. Each link has its own delay (the author's estimates, except the camera): camera and tracking 5–10 ms (the OptiTrack PrimeX 22 is rated at 2.8 ms per camera, plus reconstruction in software), Wi-Fi 5–50 ms with outliers, UART at 921600 about 1.4 ms per packet (`VISION_POSITION_ESTIMATE` in MAVLink 2 ≈ 130 bytes × 10 bits). A 300 ms Wi-Fi outlier means "source unhealthy" to the EKF; the bridge must stop publishing when the mocap loses the rigid body, not repeat the last pose (per-visual-nav, source failure). Put the rigid-body center at the IMU or set `VISO_POS_X/Y/Z`.

### PX4 in brief
EKF2 (1.18): `EKF2_EV_CTRL` is a bitmask (0 horizontal position, 1 vertical position, 2 velocity, 3 yaw; the default is 0, off, and you set the bits you need; in 1.15 the default was 15), `EKF2_HGT_REF` (0 baro, 1 GPS, 2 range sensor, 3 vision), `EKF2_EV_DELAY` (0 ms by default, maximum 300) with the overall `EKF2_DELAY_MAX` of 200 ms, `EKF2_GPS_CTRL = 0` turns GNSS off. Flow: `EKF2_OF_CTRL = 1` (the default since 1.16; in 1.15 it was 0), `EKF2_OF_DELAY` 20 ms, a rangefinder is mandatory. `VISION_POSITION_ESTIMATE` and `ODOMETRY` (pose `frame_id` `MAV_FRAME_LOCAL_NED` or `LOCAL_FRD`; `LOCAL_ENU`/`LOCAL_FLU` are converted by the receiver, but their covariance is not rotated) are accepted at 30–50 Hz; `VICON_POSITION_ESTIMATE` and `GLOBAL_VISION_POSITION_ESTIMATE` are not supported.

Flow with a rangefinder on PX4 is a chain of three links, and every one is off by default except EKF2 (v1.18.0; the drivers start from `rc.sensors` and `rcS` only when their parameter is set, all after a reboot):

| Link | Parameter | Default | What to set |
|---|---|---|---|
| Flow driver (I²C/SPI) | `SENS_EN_PMW3901`, `SENS_EN_PAA3905`, `SENS_EN_PAW3902`, `SENS_EN_PX4FLOW` | 0 | 1 for your sensor |
| Flow driver (UART, ThoneFlow) | `SENS_TFLOW_CFG` | 0 | the sensor's port |
| Flow over CAN or MAVLink | `UAVCAN_SUB_FLOW` (CAN); MAVLink `OPTICAL_FLOW_RAD` needs no separate enabling | 0 | 1 for a CAN module (`el-dronecan`) |
| Rangefinder (I²C) | `SENS_EN_VL53L1X`, `SENS_EN_SF1XX` (model number 1…7; in 1.18, 1…9, adding GRF250 and GRF500), `SENS_EN_LL40LS` (1 PWM, 2 I²C) | 0 | 1 / model / interface |
| Rangefinder (UART) | `SENS_TFMINI_CFG`, `SENS_SF0X_CFG` and other `SENS_*_CFG` | 0 | the port; the driver list is in `px4-hardware-peripherals` |
| Flow mounting | `SENS_FLOW_ROT` (0 means the sensor X axis points forward, in 45° steps), `EKF2_OF_POS_X/Y/Z` | 0 | rotation and lens offset from the center of mass |
| Flow scale | `SENS_FLOW_SCALE` (since 1.16; 0.5…1.5) | 1.0 | a correction if the distance traveled by flow systematically disagrees with a tape measure |
| Sensor limits | `SENS_FLOW_MINHGT` / `SENS_FLOW_MAXHGT`, `SENS_FLOW_MAXR` | 0.08 m / 100 m, 8 rad/s | per the datasheet: when navigating on flow, the height setpoint will not rise above `MAXHGT`, and flow above `MAXR` is not fused |
| EKF2 fusion | `EKF2_OF_CTRL`; `EKF2_RNG_CTRL` | 1 (since 1.16, before that 0); 1 (conditional mode) | on 1.15, set 1 by hand; on 1.16+ flow is fused as soon as it is present |

If a `SENS_EN_*` parameter is missing in QGC, the driver is not in the board's build: for example, the default builds of fmu-v5, fmu-v6c and fmu-v6x v1.18.0 contain no flow driver at all (in v1.17.0 fmu-v6c and fmu-v5 had them); then use flow over CAN, MAVLink or your own build. The rule: the input is the sensor and the bus; the decision is a row of the table; the check after a reboot is that `listener vehicle_optical_flow` and `listener distance_sensor` show fresh messages and `listener estimator_status_flags` shows `cs_opt_flow: True`. On 1.16+ the `EKF2_OF_CTRL` = 1 default has a downside: flow connected "just to try it" on a vehicle with GPS will also be fused; if you do not need it, set 0. Adjust the `SENS_FLOW_SCALE` scale last: first `SENS_FLOW_ROT` and the rangefinder height, because a rotation error looks like a scale error on one axis.

### Where it fits

- **Receives:** velocity from flow and height from the rangefinder (`est-alt-sources`); the pose from VIO or SLAM (`per-visual-nav`); the motion-capture pose through ROS 2 (`ros2-ardupilot`); innovation gates and the delayed time horizon (`est-kalman`).
- **Provides:** position, velocity and heading to the `EK3_SRC1_*` set, which Loiter, Guided and Auto rely on without GNSS (`ap-ekf`); a stable position for control from a companion computer (`ap-companion`).
- **If you get this wrong:** a pose sent in ENU instead of NED → pre-arm passes on the ground, and in flight the vehicle moves away from the target; you catch it by carrying the vehicle by hand before fitting the props. A SLAM jump without `reset_counter` → `XKF4.SP` above 1, measurements rejected, then a lurch to "correct" the error (`ap-ekf`, `per-visual-nav`). `VISO_DELAY_MS` set too low → the estimate lags and the position loop gets phase lag (`est-kalman`).

## practice
The bench: ArduCopter from the Copter-4.6.3 tag (build: ap-sitl), launched directly, as its own instance `-I 1` (MAVLink on TCP 5770): `arducopter -w -S -I 1 --model + --speedup 1 --home -35.363261,149.165230,584,353 --defaults defaults.parm`. Parameters on top of `copter.parm`:

The parameters and outputs below were captured on Copter-4.6.3; in 4.7.3 `ARMING_CHECK 1` is called `ARMING_SKIPCHK 0`, and in 4.6.3 the simulator GPS is disabled by `SIM_GPS_DISABLE 1` (the name `SIM_GPS1_ENABLE` is from 4.7; in the 4.6.3 run the `SIM_GPS1_ENABLE 0` line was ignored as unknown, and GPS was disabled through the driver: `GPS1_TYPE 0`).

```text
SIM_GPS1_ENABLE 0      GPS1_TYPE 0          AHRS_EKF_TYPE 3
VISO_TYPE 1            VISO_DELAY_MS 50     VISO_POS_M_NSE 0.2   VISO_YAW_M_NSE 0.2
EK3_SRC1_POSXY 6       EK3_SRC1_VELXY 0     EK3_SRC1_POSZ 6      EK3_SRC1_VELZ 0    EK3_SRC1_YAW 6
COMPASS_USE 0          COMPASS_USE2 0       COMPASS_USE3 0
ARMING_CHECK 1         FS_EKF_ACTION 1
```

The `examples/sitl-nav-labs/extnav_feed.py` script (pymavlink, 185 lines; `indoor.parm`, `analyze.py`, `timeline.py`, `truth_at.py` and the run commands are in the same folder and its README) plays the mocap bridge: it reads `SIM_STATE` at 50 Hz (the `lat_int/lon_int` fields: the float fields lose about a meter), converts it to NED from the first point, adds 2 cm of Gaussian noise, holds each sample in a queue for `--lag` ms by the flight controller's clock, and sends `VISION_POSITION_ESTIMATE` at 30 Hz with `covariance[0] = NaN`. Then it runs automatically: `SET_GPS_GLOBAL_ORIGIN` → 25 s wait → Loiter, arm → Guided, take off to 2 m → hover 15 s → a 4 × 4 m square at 1.5 m/s → Loiter 10 s → Land. It needs `MAVLINK20=1`: `covariance` and `reset_counter` are MAVLink 2 extension fields. `analyze.py` reads the `.BIN` through `pymavlink.DFReader` and compares `XKF1.PN/PE` with the `SIM.Lat/Lng` truth.

### Step 1. Arming without GPS and without an origin
Run with `--no-origin`:

```text
[    5.6s] EKF3 IMU0 is using external nav data
[   29.9s] -> mode LOITER, arming (ARMING_CHECK=1, no GPS)
[   29.9s] COMMAND_ACK arm: result 4
[   29.9s] Arm: AHRS: waiting for home
[   30.4s] PreArm: AHRS: waiting for home
```

The EKF already uses external navigation, but without a lat/lon reference there is no "home." On hardware this is the first failure you will see.

### Step 2. Baseline flight: 50 ms delay, `VISO_DELAY_MS = 50`
```text
[    4.9s] -> SET_GPS_GLOBAL_ORIGIN sent
[    4.9s] EKF3 IMU0 origin set
[    5.6s] EKF3 IMU0 yaw aligned
[    5.6s] EKF3 IMU0 is using external nav data
[    5.6s] EKF3 IMU0 initial pos NED = -0.0,-0.0,0.0 (m)
[   29.9s] COMMAND_ACK arm: result 0
[   29.9s] -> ARMED, GUIDED takeoff 2.0 m
[   40.0s] -> hover 15.0 s   truth +0.00 -0.03 -1.98  est -0.01 -0.02 -1.98
[   55.0s] -> square 4.0 m at 1.5 m/s
[   69.0s] -> square done, LOITER 10 s
[   83.4s] SIM Hit ground at 0.499274 m/s
XKF1 vs truth in flight: horiz mean 0.013 p95 0.029 max 0.044 m | vert mean 0.030 max 0.052 m (n=556)
XKF3 |IPN,IPE| in flight: mean 0.021 max 0.081 m; |IPD| max 0.060 m
XKF4 in flight: SP mean 0.01 max 0.05; samples with SP>1: 0/556; SH max 0.06; TS!=0: 556
VISP: 1402 msgs, ignored 0; last PErr 0.20000000298023224 AErr 0.20000000298023224
```

The heading aligned to the external yaw without a compass, and arming in Loiter passed with all checks. The estimate error is 1.3 cm with 2 cm of source noise: the filter averages. `VISP.PErr = 0.2` (float32) confirms that `VISO_POS_M_NSE` was used instead of the `NaN`.

### Step 3. Delay sweep
Seven runs: the transport delay `--lag` against `VISO_DELAY_MS` (the timestamps in the message are perfect here, the capture time by the flight controller's clock):

| Delay / `VISO_DELAY_MS`, ms | Δτ, ms | XKF1 error: mean / p95 / max, m | max innovation magnitude, m | `XKF4.SP` max | Square, s | Result |
|---|---|---|---|---|---|---|
| 50 / 50 | 0 | 0.013 / 0.029 / 0.044 | 0.08 | 0.05 | 14.0 | normal |
| 250 / 250 | 0 | 0.027 / 0.053 / 0.089 | 0.07 | 0.05 | 14.0 | normal |
| 150 / 50 | 100 | 0.066 / 0.242 / 0.280 | 0.13 | 0.08 | 14.0 | visible in the log |
| 250 / 50 | 200 | 0.158 / 0.514 / 0.644 | 0.28 | 0.19 | 18.8 | overshoots at the corners |
| 300 / 50 | 250 | 0.263 / 0.785 / 0.915 | 0.40 | 0.28 | 20.9 | oscillation, hovers at 1.71 m instead of 2 |
| 600 / 250 | 350 | 0.667 / 3.113 / 3.865 | 1.25 | 0.85 | 26.5 | swings up to 3.9 m, hovers at 1.31 m |
| 600 / 50 | 550 | 5.125 / 31.0 / 46.4 | 40.8 | 5.69 | — | crash |

{{diagram:chart-nav-indoor-lag|The error grows faster than the v·Δτ model: at 200 ms of uncompensated delay p95 is already 0.51 m instead of 0.30 m, because the position loop's oscillation adds to the estimate lag. A compensated 250 ms (250 / 250) is indistinguishable from 50 ms.}}

Three conclusions. **Compensated delay is almost free:** 250 / 250 flies like 50 / 50. **Timestamps do not save you:** in the 150–300 / 50 runs the `usec` field was exact, yet the error grew; only `VISO_DELAY_MS` works. **The EKF does not reject delay:** up to Δτ = 350 ms `SP` stays below 1, with not a single fusion rejection; the 5σ gate, about 1.5 m wide, lets through a lag of tens of centimeters, and it is the control that falls apart. Rejection began only at 550 ms:

```text
[   40.5s] -> hover 15.0 s   truth +0.01 -0.01 -0.56  est -0.04 -0.04 -1.56
[   71.4s] EKF3 lane switch 1
[   78.2s] SIM Hit ground at 1.426608 m/s
[   80.3s] EKF variance
[   80.3s] EKF Failsafe: changed to LAND Mode
XKF4 in flight: SP mean 0.87 max 5.69; samples with SP>1: 139/719; SH max 2.67; TS!=0: 719
```

Already in hover the altitude estimate (−1.56 m) diverged from the truth (−0.56 m): `POSZ = 6` lives with the same delay. The failsafe fired 2 s **after** hitting the ground. The working tuning method on hardware is the same as in the table: roll and pitch jerks in Loiter, `XKF3.IPN/IPE` in the log; change `VISO_DELAY_MS` in 20 ms steps (with a reboot) until the innovations are smallest.

### Step 4. A source jump: without `reset_counter` and with it
At second 5 of the hover the bridge starts sending a pose shifted by +2 m north (`--jump 2`). The log once per second (`timeline.py`), without a reset:

```text
    t   VISP.PX  XKF1.PN  XKF1.PE  XKF3.IPN  XKF3.IPE  XKF4.SP
  44.2    -0.04    -0.00    -0.01     -0.01     -0.02     0.02
  45.2     2.02    -0.01    -0.02     -2.00      0.03     1.36
  46.3     2.00    -0.01    -0.01     -1.99      0.03     1.12
  47.3     1.86     1.70    -0.05      0.08     -0.01     0.11
  48.4    -0.29     0.55    -0.05      0.38     -0.03     0.27
  49.4    -1.23    -0.85    -0.05      0.22      0.00     0.14
```

`SP = 1.36` with a 2.00 m innovation means the gate was 2.00 / 1.36 = 1.47 m, exactly what the formula gives with σ_P ≈ 0.06 m and σ_R = 0.2 m. Measurements were rejected for 1.7 s (17 samples with `SP > 1`) until P grew without corrections; then the EKF accepted the "new" position, the controller saw a 2 m error and threw the vehicle south: the truth was −2.64 m 3.5 s after the jump (a 0.6 m overshoot), and 9 s later the vehicle was still 0.6 m from the target. With `--jump-reset` (`reset_counter = 1` in the same packet):

```text
  44.2    -0.01    -0.01     0.00      0.00     -0.02     0.01
  45.2     2.01     2.04     0.01      0.04     -0.02     0.01
  46.3     2.03     2.01     0.02     -0.02      0.00     0.03
```

The estimate moved in one step, `SP` did not budge, and the true position stayed within ±0.07 m: the Loiter target moved together with the estimate.

### Step 5. Swapped axes
`--swap-xy`: the bridge sends (east, north) instead of (north, east), the classic ENU → NED mistake. On the ground everything is zero and arming passes. Then:

```text
    t   VISP.PX  XKF1.PN  XKF1.PE  XKF3.IPN  XKF3.IPE  XKF4.SP
  38.4    -0.25    -0.13     0.10      0.06     -0.06     0.06
  40.4    -1.51    -0.76     0.73      0.50     -0.46     0.52
  42.5    -8.23    -1.11     1.08      6.70     -6.62     5.52
  46.7   -29.64    -0.99     0.93     27.91    -27.80     5.34
  48.8   -45.64   -44.68    44.37      0.05     -0.10     0.06
  61.6  -177.88  -226.35   202.92    -47.55     43.41     6.10
  61.8                                                       EKF3 lane switch 1
```

The `SIM` truth at the same moments (`truth_at.py`):

```text
t= 48.0  truth N +39.46 E -39.64   XKF1 PN -39.91 PE +39.67
t=100.0  truth N +435.44 E -480.68   XKF1 PN -481.69 PE +436.38
```

The estimate is the truth mirrored about the diagonal, and any offset turns into positive feedback: the vehicle "corrects" the error by flying away from the target. The EKF rejects the measurements (`SP` 5–7), but after 7 s without position (`posRetryTimeNoVel_ms`) it resets to the source, and the cycle repeats. In 70 s it got 650 m from the takeoff point, **the EKF failsafe never fired**, and the messages show only `lane switch`. The conclusion for hardware: the filter will not protect you from wrong axes; only the hand check before takeoff does.

Flow in SITL (`FLOW_TYPE = 10`, `RNGFND1_TYPE = 100`) is step 3 of the est-alt-sources module; compare its `XKF1` drift with this bench.

### Moving to real hardware
**A. Flow + rangefinder in a room (at least 3 × 3 m, textured floor, light).** Example: a Matek 3901-L0X over MSP: `SERIALx_PROTOCOL = 32`, `FLOW_TYPE = 7`, `RNGFND1_TYPE = 32`, `RNGFND1_ORIENT = 25`; its rangefinder works up to 2 m, and for more height you need a separate lidar.
1. **Props off.** `LOG_DISARMED = 1`. In the GCS, `opt_m_x`, `opt_m_y`, `opt_qua` are nonzero; the rangefinder on the floor shows `RNGFND1_GNDCLR` ± 0.1 m (before 4.7, `RNGFND1_GNDCLEAR`, in cm), and held at 1 m it shows 1.0 ± 0.05 m.
2. **Scale calibration, props off.** Vehicle at eye level, roll ±15° back and forth within a second, 5–10 times; the same in pitch. In the log, `OF.flowX` against `OF.bodyX` and `IMU.GyrX`: the shapes match, and the scale is equalized with `FLOW_FXSCALER = (body/flow − 1) · 1000`. An inverted sign or no correlation means `FLOW_ORIENT_YAW` is wrong or the sensor does not face down.
3. **Hand walk, props off.** `EK3_SRC1_VELXY = 5`, `POSXY = 0`, `POSZ = 1`, `YAW = 1`, origin set from the GCS. Carry the vehicle at 1 m height in a straight line for 3 m and back: on the map it should move 3 ± 0.3 m the same way and come back within ±0.3 m.
4. **Props go on only here.** The first hover is in AltHold with `EK3_SRC1_VELXY = 0`: 30 s at 0.5–1.5 m; in the log `XKF5.rng` follows the height, and `OF.bodyX/Y` repeat the gyro. Then `VELXY = 5`, take off in Loiter to 1 m, finger on the AltHold switch, free space all around: on bad flow the vehicle reaches maximum tilt without warning. Abort on: drift over 1 m, wobbling, any `EKF variance`.

Acceptance: Loiter for 60 s at 1 m without sticks, drift no more than 0.5 m; `XKF5.FIX/FIY` without a systematic offset; after a 2 × 2 m square, return within ±0.5 m.

**B. UWB or mocap: what counts as ready.**
- UWB (4 anchors, a tag on UART): on the ground, within a minute the position jumps to `BCN_LATITUDE/LONGITUDE` and stays within ±0.3 m; `BCN.D0…D3` agree with a tape measure to 0.2 m at four points of the area; a hand walk around the perimeter reproduces the shape on the map; `XKF4.SP < 0.5`. Flight: AltHold → Loiter, hold within ±0.5 m.
- Mocap: the pose reaches the flight controller at ≥ 30 Hz with no gaps longer than 100 ms (`VISP` in the log, `LOG_DISARMED = 1`); the hand axis check from trap 1 has passed; `VISO_DELAY_MS` is tuned, `|XKF3.IPN/IPE| < 0.1 m` during jerks; covering the markers with a hand for 2 s gives `VisOdom: not healthy`, not a frozen pose; recalibrating the volume increments `reset_counter`. The first flight is tethered or in a net, Stabilize → AltHold → Loiter → Guided, with the Stabilize switch under your finger. Acceptance: a 60 s hover within ±5 cm of the point according to the mocap data.

Self-check: the lab is done when (SITL): the `AHRS: waiting for home` failure is reproduced, and arming in Loiter succeeds after `SET_GPS_GLOBAL_ORIGIN` without skipping checks (`ARMING_SKIPCHK = 0`; in the 4.6.3 run, `ARMING_CHECK = 1`); the baseline flight gave an `XKF1` error against the truth with p95 ≤ 0.05 m and `XKF4.SP < 0.2`; you built a sweep table of at least five points with Δτ, p95, max innovation and `SP`, and its rows land close to the step 3 table (a compensated 250 / 250 is indistinguishable from 50 / 50, and at Δτ = 200 ms p95 is about 0.5 m), you named the Δτ at which `SP > 1` appears (in the module's run, only at 550 ms) and wrote down why control breaks first (compare with the step 3 conclusion: the 5σ gate, about 1.5 m wide, lets through a lag of tens of centimeters); you have both logs of the 2 m jump: without `reset_counter`, rejection (`SP > 1` for about 1.7 s) and a lurch of the vehicle; with `reset_counter`, the estimate moved in one step and `SP` stayed near zero. (Hardware, if you have it): a table of `OF.flowX` / `OF.bodyX` before and after `FLOW_FXSCALER`; a log of the 3 m hand walk with an error ≤ 0.3 m; a 60 s Loiter on flow with drift ≤ 0.5 m; for UWB or mocap, the criteria of section B are met.

## diagnostics
- **Symptom:** `PreArm: AHRS: waiting for home` with the source working
  - Possible cause: no origin set; without GPS there is nobody to set it.
  - What to do: `SET_GPS_GLOBAL_ORIGIN` from the GCS ("Set EKF origin here") or from the bridge right after the stream starts; `AHRS_OPTIONS` bits 3 and 4 (since 4.7).
- **Symptom:** `PreArm: Need Position Estimate` or `VisOdom: not healthy`
  - Possible cause: the pose does not arrive (wrong port or sysid, a gap over 300 ms); `ODOMETRY` with a `frame_id` other than `MAV_FRAME_LOCAL_FRD`; `VISO_TYPE = 0`; `EK3_SRC1_POSXY` is not 6.
  - What the log shows: no `VISP` messages, or `Ign = 1` in them.
  - What to do: `LOG_DISARMED = 1`, find `VISP`; check `SERIALx_PROTOCOL = 2` (MAVLink 1 has no `covariance` or `reset_counter`) and the frame in the message.
- **Symptom:** right after takeoff the vehicle goes off in a diverging spiral, `XKF4.SP` 5–7, and the failsafe stays silent
  - Possible cause: swapped axes or a sign error (ENU instead of NED, yaw with a different zero).
  - What the log shows: `VISP.PX/PY` grow in a direction perpendicular or opposite to `XKF1.PN/PE`; EKF resets to the source every 7 s.
  - Consequences: in SITL, 650 m in 70 s; in a hall, the wall in a second.
  - What to do: Stabilize and land; the hand axis check without props.
- **Symptom:** in Loiter the vehicle oscillates, overshoots the points, sags in altitude; `SP` is normal
  - Possible cause: the source delay exceeds `VISO_DELAY_MS` (or `GPS1_DELAY_MS` for `GPS_INPUT`, `EK3_FLOW_DELAY` for flow).
  - What the log shows: `XKF3.IPN/IPE` grow during maneuvers and drop in hover, following the shape of the velocity.
  - What to do: measure the full delay, write it into `VISO_DELAY_MS`, reboot; over 250 ms, fix the pipeline (a wire instead of Wi-Fi), not the parameter.
- **Symptom:** a 1–3 m lurch in the middle of a hover, then decaying oscillation
  - Possible cause: the source changed the pose in a jump (loop closure, recalibration, losing and reacquiring the rigid body) without `reset_counter`.
  - What the log shows: a step in `VISP.PX/PY`, `XKF4.SP > 1` for 1–2 s, `VISP.Rst` unchanged.
  - What to do: the bridge increments `reset_counter`; for `GPS_INPUT` and `/ap/tf`, prevent jumps or switch to `VISION_POSITION_ESTIMATE`.
- **Symptom:** on flow, Loiter slowly creeps, in a circle or to one side
  - Possible cause: this is inherent: there is no position, velocity is integrated; it is worse with a wrong `FLOW_FXSCALER`, `FLOW_ORIENT_YAW` or a rangefinder error. A failure at height or speed means the rangefinder is out of range (`RFND.Stat` not 4) or the speed exceeds `(EK3_FLOW_MAX − 1) · h`.
  - What to do: scale calibration; a lidar with range to spare; accept a drift of 1–3% of distance traveled, or add a position source.
- **Symptom:** the UWB position jumps by 0.5–2 m near walls, and the height wanders
  - Possible cause: reflections, an anchor without line of sight; anchors in one plane.
  - What to do: anchors above head height and at different heights; `EK3_SRC1_POSZ = 1`; keep the flying area inside the anchor rectangle.

## checklist
- An `EK3_SRC1_*` table for my source; heading not from the compass if there is an alternative
- Axes checked by hand: forward, right, up, rotation
- The full delay measured and written into `VISO_DELAY_MS` (≤ 250 ms), then a reboot
- The origin is set automatically when the bridge starts
- The bridge stops sending when tracking is lost and increments `reset_counter` on a jump
- `LOG_DISARMED = 1` on the bench; `VISP`, `XKF3`, `XKF4.SP` reviewed before the props go on
- A switch to a mode without position (AltHold / Stabilize) under my finger

## references
- ArduPilot source — EKF source selection, EK3_SRCx values (`libraries/AP_NavEKF/AP_NavEKF_Source.cpp`, Copter-4.6.3) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/AP_NavEKF/AP_NavEKF_Source.cpp | primary | A
- ArduPilot source — receiving VISION_POSITION_ESTIMATE / ODOMETRY, origin, time correction (`libraries/GCS_MAVLink/GCS_Common.cpp`) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/GCS_MAVLink/GCS_Common.cpp | primary | A
- ArduPilot source — ExternalNav measurement time and the 250 ms delay limit (`AP_NavEKF3_Measurements.cpp`, `AP_NavEKF3_core.cpp`) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/AP_NavEKF3/AP_NavEKF3_Measurements.cpp | primary | A
- ArduPilot source — external odometry through DDS, `/ap/tf` (`libraries/AP_DDS/AP_DDS_External_Odom.cpp`) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/AP_DDS/AP_DDS_External_Odom.cpp | primary | A
- ArduPilot Copter — EKF Source Selection and Switching (sets, switch, EK3_SRC_OPTIONS) | https://ardupilot.org/copter/docs/common-ekf-sources.html | primary | A
- ArduPilot Copter — Non-GPS Navigation (list of systems, origin, AHRS_OPTIONS) | https://ardupilot.org/copter/docs/common-non-gps-navigation-landing-page.html | primary | A
- ArduPilot Copter — Optical Flow Sensor Testing and Setup (calibration, first flights) | https://ardupilot.org/copter/docs/common-optical-flow-sensor-setup.html | primary | A
- ArduPilot Copter — Vicon Positioning System (GPS_INPUT, GPS1_TYPE 14) | https://ardupilot.org/copter/docs/common-vicon-for-nongps-navigation.html | primary | A
- ArduPilot Copter — Pozyx / Nooploop Beacons (BCN_*, anchor layout) | https://ardupilot.org/copter/docs/common-nooploop.html | primary | A
- PX4 source — EKF2 parameters v1.18.0 (`src/modules/ekf2/module.yaml`, `params_external_vision.yaml`, `params_optical_flow.yaml`) | https://github.com/PX4/PX4-Autopilot/tree/v1.18.0/src/modules/ekf2 | primary | A
- PX4 Guide — Using Vision or Motion Capture Systems for Position Estimation | https://docs.px4.io/v1.17/en/ros/external_position_estimation.html | primary | A
- MAVLink common.xml — VISION_POSITION_ESTIMATE (102), SET_GPS_GLOBAL_ORIGIN (48), reset_counter | https://github.com/mavlink/mavlink/blob/master/message_definitions/v1.0/common.xml | primary | A

## notes
The lab numbers come from ArduCopter 4.6.3 SITL without wind; on hardware vibration widens P, and the Δτ thresholds shift. Parameter names in the text are for 4.7.3; in 4.6 `ARMING_SKIPCHK` was called `ARMING_CHECK` (with the opposite meaning), `RNGFND1_MAX` was `RNGFND1_MAX_CM` (cm), `EK3_FLOW_MAX` was `EK3_MAX_FLOW`; the `EK3_SRCx` and `VISO_*` values are the same. The UWB and mocap accuracies in the table are typical manufacturer values, not the author's measurements.
