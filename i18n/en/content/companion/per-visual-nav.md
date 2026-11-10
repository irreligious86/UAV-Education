---
id: per-visual-nav
title: "Visual navigation: optical flow, VIO, SLAM overview"
level: L4
readingTime: 40 min
firmware: ArduPilot · PX4
status: published
added: 2026-11-08
tags:
  - VIO
  - SLAM
  - optical flow
  - ExternalNav
  - EKF
related:
  - per-cv
  - est-alt-sources
  - est-kalman
  - ap-ekf
next:
  - per-tracking
source: content/companion/per-visual-nav.md
source_hash: c897b7fa703c
---

## summary
Optical flow gives you velocity, visual-inertial odometry (VIO) gives you position and attitude without GPS, and SLAM adds a map on top. This module explains what each method computes and what to expect from it (drift, scale, failures), how to feed VIO as an external navigation source into ArduPilot's EKF3 (`VISION_POSITION_ESTIMATE`/`ODOMETRY`, `EK3_SRC*` = ExternalNav, `VISO_*`) and PX4 (`EKF2_EV_CTRL`, `vehicle_visual_odometry`), which cameras/modules do it out of the box (T265 class, stereo + IMU, ZED), and where the limits are: lighting, texture, dynamics, latency. The lab is external navigation in SITL with a source failure drill.

## theory
### Three levels
| Method | What it gives | From what | Drift | Load |
|---|---|---|---|---|
| Optical flow + rangefinder | velocity in the horizontal plane, position (by integrating) | image shift between frames, height, gyro | position drifts (integral of velocity), velocity does not | a few % CPU, dedicated sensor |
| VIO (visual-inertial odometry) | position + attitude, 6DoF | feature-point tracks across frames + IMU (scale and dynamics) | 0.5–2% of distance traveled; grows without loop closure | Pi 4/5 — at the limit (mono, low resolution), Jetson — yes; off-the-shelf modules — on their own chip |
| SLAM | the same + a map + loop closure | VIO + place recognition, graph optimization | jumps on loop closure, bounded on average | Jetson/PC class |

Optical flow is covered in the module “Height and position without GPS”. Here it's VIO/SLAM.

### How VIO works
1. Feature detector (FAST/ORB/Shi-Tomasi) → tracking between frames (KLT) or descriptor matching.
2. Geometry: from point correspondences across several frames you get the camera motion and the 3D points (triangulation). A mono camera does not know scale (everything could be twice as far away and twice as big) — scale comes from the **IMU** (accelerations in m/s²) or **stereo** (known baseline).
3. Optimization: EKF (MSCKF) or a sliding window (bundle adjustment: VINS-Mono/Fusion, OpenVINS, ORB-SLAM3 in VIO mode, Kimera).
4. Output: pose and velocity with covariance in the coordinate frame of the first frame (the “odom” frame), at the camera rate (20–60 Hz) with 20–80 ms latency.

What breaks VIO: **too little texture** (white wall, water, snow, featureless grass), **bad light** (night, glare, exposure changes), **fast rotation** (motion blur, features fly out of the frame — global shutter and the IMU help), **rolling shutter**, **dynamic objects** in the frame (people, cars — rejected by RANSAC), **bad calibration** (camera intrinsic matrix, distortion, and above all the camera pose relative to the IMU and time synchronization; a 5 ms timing error means noticeable drift).

### Off-the-shelf solutions
- Modules with onboard VIO (Intel RealSense T265 class — discontinued, but the principle is the same; ModalAI VOXL; ZED (stereo + IMU, needs a GPU machine); Luxonis OAK-D (stereo, VIO in firmware)): they output the pose over USB/UART, and the companion translates it into MAVLink.
- Open-source software: VINS-Fusion, OpenVINS, ORB-SLAM3, Kimera-VIO — on ROS/ROS 2, camera + IMU with synchronization (a hardware trigger is ideal).

### Into the autopilot
**ArduPilot** (EKF3 ExternalNav): the companion sends MAVLink `VISION_POSITION_ESTIMATE` (position + angles, 20–50 Hz) and/or `VISION_SPEED_ESTIMATE`, or `ODOMETRY` (everything together, with covariances); parameters `VISO_TYPE = 1` (MAVLink), `VISO_POS_*` (camera offset from the IMU), `VISO_ORIENT`, `VISO_DELAY_MS` (source latency); sources `EK3_SRC1_POSXY = 6`, `EK3_SRC1_VELXY = 6`, `EK3_SRC1_POSZ = 6` (or baro 1), `EK3_SRC1_YAW = 6` (or compass); `EK3_SRC2_*` is a backup set on GPS, switched by a switch/script; with `EK3_SRC_OPTIONS` bit 1, ExternalNav is aligned with optical flow on switchover. To check: `XKF4.SP/SV` within normal range, `VISP`/`VISV` log messages, the `XKF1` position follows the source.
**PX4** (EKF2): `EKF2_EV_CTRL` (bitmask: horizontal position, vertical, velocity, yaw), `EKF2_EV_DELAY`, `EKF2_EV_POS_*` (offset), `EKF2_HGT_REF`; the ROS 2 topic `/fmu/in/vehicle_visual_odometry` (uXRCE-DDS) or MAVLink `ODOMETRY` via MAVROS `/mavros/odometry/out`. Coordinate frames: PX4 expects FRD/NED, ROS gives FLU/ENU — conversion is mandatory (MAVROS does it itself with correct frame_id values).

### Source failure
VIO can silently output garbage (tracking loss → the pose “freezes” or jumps). Protections: (1) the companion monitors the tracking status and **stops sending** on loss (the EKF falls back to inertial, then failsafe/dead reckoning); (2) EKF gates reject jumps; (3) a backup source set (GPS/flow) and `FS_EKF_ACTION`; (4) a pilot with AltHold on a switch. Test this in SITL before the field.

{{diagram:visual-nav-levels|Three levels of visual navigation and how each one enters the autopilot.}}

## practice
### Step 1. Calibration
Camera intrinsic calibration (`cv2.calibrateCamera` on a checkerboard, reprojection error < 0.5 px); for VIO, camera–IMU calibration (Kalibr) with the time offset. Write the parameters to the engineering folder.

### Step 2. VIO on the bench
OpenVINS or VINS-Fusion with a USB global-shutter camera + IMU (you can use the FC's IMU via MAVLink `RAW_IMU` at 200 Hz or a separate IMU); walk 10 m down a corridor and come back — the loop closure error in meters and in % of the path. Repeat in bad light and at a white wall — record the failure.

### Step 3. ExternalNav in SITL
ArduPilot SITL: a pymavlink script publishing `VISION_POSITION_ESTIMATE` from the **true SITL position** (`SIMSTATE`/`LOCAL_POSITION_NED`) with 5 cm of added noise and 50 ms of latency, at 30 Hz; `SIM_GPS1_ENABLE = 0`, `EK3_SRC1_* = 6`, `VISO_TYPE = 1`, `VISO_DELAY_MS = 50`. Take off in Loiter, hold, fly a square in Guided. Log: `XKF1` against truth, `XKF4`.

### Step 4. Failure
Stop publishing for 10 s in flight → EKF behavior (`XKF4`, messages), failsafe; then “garbage” (frozen pose) → gates; then the `EK3_SRC2` backup set on GPS enabled by a switch → recovery. Lab: ExternalNav source fed in, hold without GPS, failure drilled.

## diagnostics
- **Symptom:** the EKF does not accept VIO (XKF4.SP > 1 constantly)
  - Possible cause: camera coordinate frame/orientation, latency, scale.
  - What to do: VISO_ORIENT/POS, DELAY_MS, compare VISP with XKF1 axis by axis and sign by sign.
- **Symptom:** the position drifts while stationary
  - Possible cause: VIO without texture/light, bad camera–IMU calibration.
  - What to do: lighting/texture, recalibration, time offset.
- **Symptom:** the position jumps during a turn
  - Possible cause: tracking loss during fast rotation (rolling shutter).
  - What to do: global shutter, limit the yaw rate, shorter exposure.
- **Symptom:** after losing VIO the vehicle flew away
  - Possible cause: the companion kept sending a “frozen” pose.
  - What to do: tracking status → stop publishing; FS_EKF_ACTION; backup source set.
- **Symptom:** PX4 rejects odometry
  - Possible cause: frame (ENU vs NED), EKF2_EV_CTRL not set, no timestamp.
  - What to do: MAVROS frame_id, EV parameters, timesync.

## references
- ArduPilot — Non-GPS Navigation (landing page: VIO cameras, ExternalNav) | https://ardupilot.org/copter/docs/common-non-gps-navigation-landing-page.html | primary | A
- PX4 — Using Vision or Motion Capture Systems for Position Estimation (EKF2_EV_*) | https://docs.px4.io/main/en/ros/external_position_estimation.html | primary | A
- OpenVINS — repository and documentation (VIO, calibration requirements) | https://github.com/rpng/open_vins | primary | A

## checklist
- I understand the difference between flow / VIO / SLAM and their drift
- I know what breaks VIO: texture, light, dynamics, calibration, synchronization
- I fed ExternalNav into EKF3 (or EV into EKF2) and saw it accepted in the log
- Hold without GPS in SITL on an external source
- Source failure drilled: publishing stopped, gates, backup set
