---
id: per-visual-nav
title: "Visual navigation: optical flow, VIO, an overview of SLAM"
level: L4
readingTime: 55 min
firmware: ArduPilot 4.7 (checked against 4.7.3; lab recorded on SITL 4.7.2) · PX4 1.18 (parameters checked against v1.18.0)
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
source_hash: d43724ca2556
---

## summary
Optical flow gives velocity, visual-inertial odometry (VIO) gives position and attitude without GPS, and SLAM adds a map. This module explains what each method computes and what to expect from it (drift, scale, failures), how to feed VIO into ArduPilot EKF3 as an external navigation source (`VISION_POSITION_ESTIMATE`/`ODOMETRY`, `EK3_SRC*` = ExternalNav, `VISO_*`) and into PX4 (`EKF2_EV_CTRL`, `vehicle_visual_odometry`), which cameras/modules do it out of the box (T265 class, stereo + IMU, ZED), and where the limits are: lighting, texture, dynamics, latency. Lab: ArduCopter 4.7.2 SITL on external navigation and three source failures with real numbers: a frozen pose, a stopped feed, a 5 m jump.

## theory
### Three levels
| Method | What it gives | From what | Drift | Load |
|---|---|---|---|---|
| Optical flow + rangefinder | velocity in the plane, position (by integration) | image shift between frames, height, gyro | the position drifts (integral of velocity), the velocity does not | a few % CPU, a dedicated sensor |
| VIO (visual-inertial odometry) | 6DoF position + attitude | feature tracks across frames + IMU (scale and dynamics) | 0.5–2% of the distance traveled; grows without loop closure | Pi 4/5 at the limit (mono, low resolution), Jetson yes; ready-made modules run on their own chip |
| SLAM | the same + a map + loop closure | VIO + place recognition, graph optimization | jumps at loop closure, bounded on average | Jetson/PC class |

Optical flow is covered in the module "Altitude and position without GPS". This one is about VIO/SLAM. A drift of 0.5–2 % of the path is a course guideline for good texture and calibration, not a guarantee: on a 200 m route that is 1–4 m.

### How VIO works
1. A feature detector (FAST/ORB/Shi-Tomasi) → tracking between frames (KLT) or descriptor matching.
2. Geometry: from point correspondences across several frames, the camera motion and the 3D points (triangulation). A monocular camera does not know the scale (everything could be twice as far and twice as large); the scale comes from the **IMU** (accelerations in m/s²) or from **stereo** (a known baseline).
3. Optimization: an EKF (MSCKF) or a sliding window (bundle adjustment: VINS-Mono/Fusion, OpenVINS, ORB-SLAM3 in VIO mode, Kimera).
4. Output: pose and velocity with covariance in the frame of the first image (the "odom" frame), at the camera rate (20–60 Hz) with a latency of 20–80 ms.

What breaks VIO: **too little texture** (a white wall, water, snow, featureless grass), **bad light** (night, glare, exposure changes), **fast rotation** (blur, features leaving the frame; a global shutter and the IMU help), **rolling shutter**, **moving objects** in the frame (people, cars; rejected by RANSAC), **bad calibration** (the camera intrinsics, distortion and, above all, the camera pose relative to the IMU and the time synchronization; a 5 ms timing error means noticeable drift).

### What VIO fundamentally cannot observe
A camera + IMU determine the scale, roll and pitch unambiguously: gravity gives the vertical, and accelerations in m/s² give meters. Four quantities are unobservable: the position x, y, z and the heading relative to the outside world. VIO knows them only relative to the first frame, and their error grows without bound; that is the drift. Three practical consequences follow.

- **Scale needs acceleration.** In a hover and in flight at constant velocity the accelerometer sees only gravity, and the scale of monocular VIO rests on past data. That is why initialization is done with motion (rock the vehicle, travel a few meters while accelerating), while stereo VIO gets its scale from the baseline even without motion.
- **Heading drifts just like position.** If you feed the VIO heading into EKF3 (`EK3_SRC1_YAW = 6`), the compass no longer holds the heading, and the angle wanders together with the VIO map. On a long flight the compass is the more stable heading source, if the magnetic environment allows it.
- **A timing error turns into an attitude and position error.** When rotating at 180°/s (π rad/s), a 5 ms offset between the camera and IMU timestamps assigns the frame a rotation of π × 0.005 = 0.016 rad ≈ 0.9°. A feature 3 m away then "moves" by 4.7 cm. The filter explains this with wrong motion, hence drift during maneuvers (course calculation, derived from the geometry).

### Ready-made solutions
- Modules with onboard VIO (the Intel RealSense T265 class, discontinued but the principle is the same; ModalAI VOXL; ZED (stereo + IMU, needs a GPU machine); Luxonis OAK-D (stereo, VIO in firmware)): they output the pose over USB/UART, and the companion translates it into MAVLink.
- Open software: VINS-Fusion, OpenVINS, ORB-SLAM3, Kimera-VIO, for ROS/ROS 2, camera + IMU with synchronization (a hardware trigger is ideal).

### Into the autopilot
**ArduPilot** (EKF3 ExternalNav): the companion sends MAVLink `VISION_POSITION_ESTIMATE` (position + angles, 20–50 Hz) and/or `VISION_SPEED_ESTIMATE`, or `ODOMETRY` (everything together, with covariances); parameters `VISO_TYPE = 1` (MAVLink), `VISO_POS_*` (camera offset from the IMU), `VISO_ORIENT`, `VISO_DELAY_MS` (source latency); sources `EK3_SRC1_POSXY = 6`, `EK3_SRC1_VELXY = 6` (only if the companion sends a velocity, `VISION_SPEED_ESTIMATE` or `ODOMETRY`; with `VISION_POSITION_ESTIMATE` alone, as in the lab below, set 0, as in `nav-indoor`), `EK3_SRC1_POSZ = 6` (or baro 1), `EK3_SRC1_YAW = 6` (or the compass); `EK3_SRC2_*` is a backup set on GPS, switched with a switch/script; with bit 1 of `EK3_SRC_OPTIONS` (AlignExtNavPosWhenUsingOptFlow), while the EKF flies on optical flow the ExternalNav position is pulled toward its estimate so that switching to ExternalNav causes no jump (`AP_NavEKF_Source.cpp:136–139`). Check: `XKF4.SP/SV` are normal, the `VISP`/`VISV` log messages are present, the `XKF1` position follows the source.
**PX4** (EKF2): `EKF2_EV_CTRL` (a bitmask: horizontal position, vertical position, velocity, yaw), `EKF2_EV_DELAY`, `EKF2_EV_POS_*` (offset), `EKF2_HGT_REF`; the ROS 2 topic `/fmu/in/vehicle_visual_odometry` (uXRCE-DDS) or MAVLink `ODOMETRY` through MAVROS `/mavros/odometry/out`. Coordinate frames: PX4 expects FRD/NED, ROS gives FLU/ENU, so a conversion is mandatory (MAVROS does it itself with the right frame_id values).

Details people trip over on the first run:

- **ArduPilot accepts `ODOMETRY` only with `frame_id = MAV_FRAME_LOCAL_FRD` and `child_frame_id = MAV_FRAME_BODY_FRD`.** Any other pair is silently dropped, with no message and no `VISP` record (`GCS_Common.cpp:4062–4066`). The autopilot itself rotates the velocity from `ODOMETRY` from body FRD into NED.
- **Measurement noise.** If `covariance[0]` of `VISION_POSITION_ESTIMATE` is NaN, EKF3 uses `VISO_POS_M_NSE` (default 0.2 m) and `VISO_YAW_M_NSE` (0.2 rad). A covariance that is sent is clamped from below by these parameters: position from `VISO_POS_M_NSE` to 100 m, angle from `VISO_YAW_M_NSE` to 1.5 rad (`AP_VisualOdom_MAV.cpp:42–43`). The velocity noise is always taken from `VISO_VEL_M_NSE`, whatever the VIO sends (`:79`). So a VIO that understates its covariance will not make EKF3 more confident than the parameters allow; what makes the filter overconfident is a `VISO_POS_M_NSE` that is too small (the gates narrow and honest noise gets rejected), while one that is too large makes it follow the source slowly. In PX4 with `EKF2_EV_NOISE_MD = 0` the same logic applies: the noise comes from the message, with `EKF2_EVP_NOISE` as the lower bound.
- **`reset_counter`.** When SLAM closes a loop or VIO reinitializes, the pose jumps. A changed `reset_counter` (usually +1; the EKF reacts to any change of the value, `AP_VisualOdom_Backend.cpp:83–90`) tells the EKF "this is a reset, not motion", and the filter moves its estimate in one step instead of rejecting it (checked in `nav-indoor`).
- **By default PX4 fuses nothing:** `EKF2_EV_CTRL = 0`. For position, height, velocity and yaw you need 15. `EKF2_EV_DELAY` defaults to 0 ms and takes effect after a reboot. `EKF2_HGT_REF` defaults to 1 (GNSS); without GPS you set 0 (baro) or 3 (vision). The "only over a flat surface" restriction applies to the rangefinder (2): it measures the height above whatever is below it, so the reference height rises and falls with the terrain; the z from VIO lives in its own coordinate frame and does not follow the terrain (but it drifts like any VIO coordinate). Among the generic `rc.*_defaults` sets, only the underwater and spacecraft vehicles have 15 by default (`rc.uuv_defaults`, `rc.sc_defaults`); some individual airframe configurations, for example `70000_atmos` and the simulation one `1013_gazebo-classic_iris_vision`, also set 15.

{{lesson:ap-ahrs-choice|How to set up EKF3 for external navigation and switch GPS ↔ VIO with source sets; why boards with 1 MB of flash cannot accept VIO at all.}}

| Parameter | Where | Default | Range / values |
|---|---|---|---|
| `VISO_TYPE` | ArduPilot 4.7.2 | 0 | 1 MAVLink, 2 IntelT265, 3 VOXL |
| `VISO_POS_X/Y/Z` | ArduPilot | 0 m | −5…5 m, from the center of gravity to the camera |
| `VISO_ORIENT` | ArduPilot | 0 (Forward) | 2 Right, 4 Back, 6 Left, 24 Up, 25 Down |
| `VISO_DELAY_MS` | ArduPilot | 10 ms | 0–250 ms |
| `VISO_POS_M_NSE` / `VISO_YAW_M_NSE` / `VISO_VEL_M_NSE` | ArduPilot | 0.2 m / 0.2 rad / 0.1 m/s | position and angle: the value used for NaN and the lower bound of a sent covariance; velocity: always the parameter |
| `VISO_QUAL_MIN` | ArduPilot | 0 | −1…100 %; only `ODOMETRY` has a `quality` field, `VISION_POSITION_ESTIMATE` arrives with quality 0 and is dropped entirely when `VISO_QUAL_MIN` > 0 |
| `EK3_SRC1_POSXY/VELXY/POSZ/YAW` | ArduPilot | 3 / 3 / 1 / 1 (GPS, GPS, baro, compass) | 6 ExternalNav |
| `EK3_POS_I_GATE` | ArduPilot | 500 (5σ) | the position innovation gate |
| `FS_EKF_ACTION` / `FS_EKF_THRESH` | ArduPilot Copter | 1 (Land) / 0.8 | the response to growing EKF variances |
| `EKF2_EV_CTRL` | PX4 1.18.0 | 0 | bits 0 horizontal position, 1 vertical position, 2 3D velocity, 3 yaw |
| `EKF2_EV_DELAY` | PX4 | 0 ms | 0–300 ms, reboot required |
| `EKF2_EV_NOISE_MD` | PX4 | 0 | 0 EV reported variance (parameters as the lower bound); 1 EV noise parameters only |
| `EKF2_EVP_NOISE` / `EKF2_EVV_NOISE` / `EKF2_EVA_NOISE` | PX4 | 0.1 m / 0.1 m/s / 0.1 rad | position, velocity, angle noise |
| `EKF2_EVP_GATE` / `EKF2_EVV_GATE` | PX4 | 5 / 3 σ | position and velocity gates |
| `EKF2_EV_QMIN` | PX4 | 0 | 0–100, threshold on the quality field |
| `EKF2_HGT_REF` | PX4 | 1 (GNSS) | 0 baro, 2 range sensor, 3 vision |

### Source failure
VIO can silently output garbage (tracking lost → the pose "freezes" or jumps). Safeguards: (1) the companion watches the tracking status and **stops sending** when tracking is lost (the EKF goes to inertial-only, then failsafe/dead reckoning); (2) the EKF gates (`EK3_POS_I_GATE`, default 500, five sigma) reject **jumps**, a measurement far from the prediction; a "frozen" pose that keeps arriving is not caught by the gates: with every measurement the filter is pulled to the same point, the innovation stays small, the EKF believes the vehicle is stationary while the real vehicle drifts away (and even a source rejected by the gates is accepted again by the EKF after the position timeout, 7 s without velocity measurements, 10 s with them, resetting the position to it). The autopilot itself judges the "health" of the visual source only by whether messages arrive (no older than 300 ms); it does not check the content; the exception is the `quality` field of `ODOMETRY`: when it is below `VISO_QUAL_MIN`, the measurement is not passed to the EKF; (3) a backup source set (GPS/flow) and `FS_EKF_ACTION`; (4) a pilot with AltHold on a switch. Check it all in SITL before the field.

{{diagram:vio-failure-tree|Of the four VIO failure scenarios only one is dangerous, a frozen pose arriving at the usual rate: the gates do not catch it, so the companion must stop publishing on its own.}}

### What SITL showed: three failures in numbers
The lab below runs three failures on ArduCopter 4.7.2 SITL without GPS, hovering in Loiter in a 3 m/s wind, each for 20 s. We distinguish two quantities: the **gap**, how far the EKF estimate is from the truth, and the **drift**, how far the real vehicle has moved from the point where it was hovering. The results confirm the theory and refine it in one place.

- **Frozen pose.** The normalized position innovation (`XKF4.SP`) did not rise above 0.01 during the whole 20 s, while the wind carried the vehicle 6.2 m away (in another run with a different heading at takeoff, 9.9 m); the estimate stands still all that time, so the gap equals the drift. Worse, when the source came back to life and sent the truth again, the gates rejected the truth (`SP` = 4.7): it was 7 m away from the estimate. For another 7.4 s the vehicle kept moving away, the gap reached 13.7 m and the drift 15 m, and only then did the EKF reset the position to the source. That is exactly the reacquisition timeout (7 s without velocity measurements).
- **Stopped feed.** After 7.9 s EKF3 reported "EKF variance", the failsafe switched the vehicle to Land, and after 15 s came "stopped aiding". By touchdown (18.4 s) the vehicle had drifted 6.0 m from the hover point, and the estimate was off by 4.9 m: Land without a position descends vertically and holds the horizontal only on inertial navigation. This is the best of the three outcomes, because the autopilot **knows** it has no position.
- **5 m jump.** `SP` jumped to 3.4 and the gates rejected the measurements. But not forever: after about 4.5 s the ratio fell below 1, the jump was accepted, the estimate moved by 5 m, and the vehicle lurched toward the old point and went 3.2 m the other way. The most likely mechanism: while the source is being rejected, the position variance in the filter grows and the ratio falls; in this run the moment of acceptance coincided with an EKF3 core switch (lane switch), so the mechanism is not isolated (an inference from the log). The refinement to the theory: the gates protect against a jump for seconds, not for good. Only `reset_counter` (or stopping the feed) protects against a permanent offset after a VIO reinitialization.

The course rule for the companion: a freeze detector is mandatory. A live VIO pose is noisy and never repeats to the millimeter; a frozen one repeats exactly: if the pose has not moved 1 mm in 0.5 s, stop publishing. The EKF velocity is no good for this check: with a frozen pose the EKF itself believes the vehicle is stationary. If the number of tracked features falls below a threshold or the covariance rises above one, stop as well. It is better for the autopilot to go into failsafe than to stand confidently at a place that does not exist; in SITL with the detector the freeze ended in Land after 8.4 s (step 6). The detector does not reduce the drift (in 20 s the wind carries the vehicle the same 6 m away), but the vehicle lands instead of continuing to "hover" and then jumping 15 m.

{{diagram:chart-vio-fault-gap|A frozen pose gives a 6.3 m gap in 20 s with SP ≤ 0.01 and another 7 s of drifting after the failure ends; a stopped feed is the only failure after which the autopilot lands on its own, after 7.9 s.}}

{{diagram:visual-nav-levels|The three levels of visual navigation and how each one enters the autopilot.}}

### Where it fits in the system

- **Takes in:** global shutter frames and an IMU with common synchronization (`per-camera`); the camera calibration and its pose relative to the IMU (`per-geometry`); the FLU/ENU ↔ FRD/NED conversion (`math-linalg-rot`).
- **Hands off:** `VISION_POSITION_ESTIMATE` or `ODOMETRY` as an external source to EKF3 and EKF2 (`ap-ekf`, `est-kalman`); a position for Loiter and Guided without GNSS (`nav-indoor`).
- **If you get this wrong:** VIO lost tracking but the companion keeps sending a "frozen" pose → the EKF believes it and the vehicle drifts away; the EKF gates and failsafe are in `ap-ekf`. The ENU → NED conversion is forgotten → the axes are mixed up and the vehicle goes sideways at the first correction; the coordinate-frame traps are collected in `nav-indoor`.

## practice
### Step 1. SITL on external navigation
The scripts are in `examples/sitl-nav-labs/` (with a README). `run_lab.sh` starts ArduCopter 4.7.2 SITL (`arducopter -w -S --model + --speedup 1`) with `Tools/autotest/default_params/copter.parm` plus the lab file and saves a run folder with the log. The `extnav.parm` file: GPS off, all EKF3 sources on ExternalNav, a 3 m/s wind from the south so that the estimate error turns into real drift:

```text
# per-visual-nav: ExternalNav only (ArduCopter 4.7.2 SITL)
SIM_GPS1_ENABLE 0
GPS1_TYPE 0
AHRS_EKF_TYPE 3
EK3_ENABLE 1
EK2_ENABLE 0
VISO_TYPE 1
VISO_DELAY_MS 50
VISO_POS_M_NSE 0.2
VISO_YAW_M_NSE 0.2
EK3_SRC1_POSXY 6
EK3_SRC1_VELXY 0
EK3_SRC1_POSZ 6
EK3_SRC1_VELZ 0
EK3_SRC1_YAW 6
COMPASS_USE 0
COMPASS_USE2 0
COMPASS_USE3 0
FS_EKF_ACTION 1
LOG_DISARMED 0
SIM_WIND_SPD 3
SIM_WIND_DIR 180
```

The pose source is `vio_fault_feed.py` (162 lines, pymavlink), built like the bridge from `nav-indoor`: it reads the `SIM_STATE` truth at 50 Hz, converts it to NED from the first point, adds 2 cm of noise and a 50 ms delay on the flight controller clock, and sends `VISION_POSITION_ESTIMATE` at 30 Hz with `covariance[0] = NaN`. Then an automatic sequence: `SET_GPS_GLOBAL_ORIGIN` → a 25 s wait → arm in Loiter → takeoff in Guided to 3 m → Loiter. After 10 s of hovering one failure is switched on for 20 s, followed by 15 s of observation. Once a second it prints the truth, the EKF estimate (`LOCAL_POSITION_NED`), `gap` (the estimate versus the truth), `drift` (how far the vehicle has moved from the point where it was hovering on entering Loiter) and `ratio`, the `pos_horiz_variance` from `EKF_STATUS_REPORT`, which in ArduPilot is √(position innovation ratio), the same as `XKF4.SP` (`AP_NavEKF3_Outputs.cpp:504`). The failure core (condensed from `vio_fault_feed.py:108–127`, without the `--detector` branch):

```python
while queue and queue[0][0] <= t_boot:          # deliver lagged samples (FC time)
    s = queue.popleft()[1]
    if fault_on and args.fault == "stop":
        continue                                  # companion went silent
    if fault_on and args.fault == "freeze":
        s = (s[0],) + last_pose[1:]               # fresh timestamp, frozen pose
    elif fault_on and args.fault == "jump":
        s = (s[0], s[1] + args.jump) + s[2:]      # relocalisation jump north
    else:
        last_pose = s
    t_us, n, e, d, r, p, y = s
    m.mav.vision_position_estimate_send(t_us, n, e, d, r, p, y, [float("nan")] + [0.0] * 20, 0)
```

### Step 2. Baseline hover
The first 10 s of every run are a control without a failure: the gap between the estimate and the truth is 0.00–0.04 m, the ratio 0.00–0.04. If you see more than 0.1 m and more than 0.3, look for a delay or axis error (`nav-indoor`) and do not move on to the failures.

### Step 3. Frozen pose
`./run_lab.sh freeze extnav.parm "" vio_fault_feed.py --fault freeze --fault-at 10 --fault-len 20`. Output (every fifth line during the failure and the lines after it):

```text
[   49.9s] >>> fault ON (freeze)
[   54.1s] t+ 14.1 truth N  -0.07 E  +0.15 | est N  -0.01 E  +0.00 | gap  0.16 | drift  0.15 m | ratio 0.01 | LOITER FAULT
[   59.1s] t+ 19.2 truth N  -0.31 E  +0.94 | est N  -0.01 E  +0.00 | gap  0.99 | drift  0.97 m | ratio 0.01 | LOITER FAULT
[   64.1s] t+ 24.2 truth N  -0.73 E  +2.78 | est N  -0.01 E  +0.00 | gap  2.87 | drift  2.85 m | ratio 0.01 | LOITER FAULT
[   69.2s] t+ 29.3 truth N  -1.36 E  +6.12 | est N  -0.01 E  -0.00 | gap  6.27 | drift  6.24 m | ratio 0.01 | LOITER FAULT
[   69.9s] <<< fault OFF
[   70.2s] t+ 30.3 truth N  -1.49 E  +6.99 | est N  -0.01 E  -0.00 | gap  7.15 | drift  7.12 m | ratio 4.68 | LOITER
[   76.3s] t+ 36.3 truth N  -2.24 E +13.51 | est N  -0.03 E  +0.01 | gap 13.68 | drift 13.67 m | ratio 1.52 | LOITER
[   77.3s] t+ 37.3 truth N  -2.30 E +14.81 | est N  -2.32 E +14.55 | gap  0.26 | drift 14.96 m | ratio 0.04 | LOITER
```

The estimate stays at (−0.01, 0.00), the truth moves away, the ratio does not grow. After the failure ends the honest data is rejected (4.68 → 1.52), and only 7.4 s later does the estimate jump to the source. `python3 logsum.py sitl-run/freeze/logs/00000001.BIN`: the maxima of `XKF4.SP` (core 0) in 5 s windows from arming: 0.00 in all windows of the failure, 4.76 and 1.92 after it, 0.05 after the reset.

### Step 4. Stopped feed
`--fault stop`. The key lines:

```text
[   49.9s] >>> fault ON (stop)
[   57.8s] MSG EKF variance
[   57.8s] MSG EKF Failsafe: changed to Land Mode
[   64.9s] MSG EKF3 IMU0 stopped aiding
[   68.3s] MSG SIM Hit ground at 0.488822 m/s
[   69.2s] t+ 29.3 truth N  +5.59 E  -2.10 | est N  +1.70 E  +0.83 | gap  4.87 | drift  5.97 m | ratio 0.01 | LAND FAULT
[   70.0s] MSG EKF3 IMU0 is using external nav data
```

Failsafe after 7.9 s, touchdown after 18.4 s, a drift of 6.0 m from the hover point, and the EKF estimate was off by 4.9 m. When the source came back, the EKF took it at once ("is using external nav data") and moved the position.

### Step 5. A 5 m jump
`--fault jump --jump 5`. The ratio is 3.41 0.2 s after the jump and 1.13 after 4.3 s; after 5.3 s the estimate is already +5.49 m to the north, and after 6.3 s the truth is at −3.17 m: the vehicle lurched by 3.2 m. Until the end of the failure the estimate and the truth differ by 5.0 m (the estimate follows the offset source). The reverse jump at the end of the failure behaves the same way: 3.31 → 0.99 in 4.5 s, then accepted. From the `XKF4.SP` log: 3.40 and 0.41 for the first jump, 3.39 and 0.44 for the second.

### Step 6. Freeze detector on the companion
A live pose never repeats to the millimeter: the VIO noise (2 cm in the bridge) changes it in every frame. A frozen pose repeats exactly. So the simplest detector in the bridge is "the pose has not moved more than 1 mm in 0.5 s → stop publishing; it moved → publish again" (the `--detector` flag, about ten lines). Step 3 repeated with the detector:

```text
[   49.9s] >>> fault ON (freeze)
[   50.4s] detector: pose frozen 0.5 s, stop publishing
[   58.3s] MSG EKF variance
[   58.3s] MSG EKF Failsafe: changed to Land Mode
[   65.4s] MSG EKF3 IMU0 stopped aiding
[   68.8s] MSG SIM Hit ground at 0.490478 m/s
[   70.0s] detector: pose moves again, publishing
[   70.3s] t+ 30.3 truth N  +6.14 E  -1.97 | est N  +6.13 E  -1.97 | gap  0.01 | drift  6.45 m | ratio 0.04 | LAND
```

The frozen pose has turned into the step 4 failure: the detector fired after 0.5 s, the failsafe and Land came 8.4 s after the start of the failure. The drift until touchdown is still 6.4 m, the same as without the detector over the same 20 s: in a 3 m/s wind, Land without a position holds the horizontal only on inertial navigation. The detector replaces "confidently standing in the wrong place" with "knows there is no position and lands" and removes the aftermath: without it the vehicle kept drifting for another 7 s after the end of the failure, up to 15 m. To avoid the drift as well you need a second source in `EK3_SRC2_*` (GPS or flow). The 1 mm and 0.5 s thresholds are a course guideline; with a real VIO lying still on a table, check that its own noise exceeds 1 mm, otherwise the detector will fire falsely, and then use the tracking status and the number of features that the VIO itself reports.

### Moving to real hardware
Calibration: the camera intrinsic calibration (`cv2.calibrateCamera` on a checkerboard, reprojection error < 0.5 px); for VIO, the camera–IMU calibration (Kalibr) with the time offset. Write the parameters into the engineering folder.

VIO on the bench: OpenVINS or VINS-Fusion with a USB global shutter camera + an IMU (you can use the flight controller IMU through MAVLink `RAW_IMU` at 200 Hz, or a separate IMU); walk 10 m down a corridor and come back, and record the closure error in meters and in % of the path. Repeat in bad light and next to a white wall, and record the failure.

Flight: first with the props removed, VIO + bridge running, carry the vehicle by hand around a 3 × 3 m square: `XKF1` must repeat the square with an error below 0.3 m, `VISP` without gaps. The first takeoff is indoors over a textured floor, at 1–1.5 m, with the pilot holding the AltHold switch (it does not depend on position). Abort criteria: a position discrepancy on the OSD/in the GCS of more than 0.5 m over 5 s of hovering, an "EKF variance" or "stopped aiding" message → AltHold and land manually. Frozen poses and jumps are tested only in SITL; on hardware, check only the stopped feed (turn the bridge off in a hover at 1 m with the pilot on AltHold). Acceptance: 60 s of Loiter with a drift of no more than 0.3 m, and when the bridge is stopped, an EKF message and Land/AltHold after 5–10 s, as in step 4.

Self-check: the lab is done when (SITL) the baseline hover gives a gap ≤ 0.05 m and a ratio ≤ 0.05; with a frozen pose the ratio stays at or below 0.05 during the failure, the drift at the end of 20 s is between 5 and 12 m (6.2 and 9.9 m in the module runs; the spread comes from the wind and the heading at takeoff) and equals the gap to within 0.1 m, after the failure the ratio is above 1 and the estimate resets after 6–8 s; with a stopped feed there is an "EKF variance" and a switch to Land within 5–10 s, and the drift until touchdown is a few meters (6.0 m in the run); with a 5 m jump the ratio is above 1 in the first second and below 1 after 3–6 s, after which the estimate and the truth differ by 5 ± 0.3 m; with the freeze detector from step 6, publishing stops 0.5 s after the freeze, "EKF variance" and Land come after 7–10 s (8.4 s in the run), the drift until touchdown is of the same order as in step 4 (6.4 m versus 6.0 m), and there is no further drifting after the end of the failure. (Hardware) the calibration reprojection error is < 0.5 px; the VIO closure error over 20 m of path is compared with the typical drift of 0.5–2 % of the path (0.1–0.4 m), the failure in bad light and next to a white wall is recorded; the flight acceptance criteria above are met.

**Reference answer for the self-check.**

| Failure | Correct (module run) | Typical mistake and cause |
|---|---|---|
| Frozen pose | `SP` ≤ 0.01, a drift of 6.2 m in 20 s (= the gap), after the failure `SP` 4.7 and a reset after 7.4 s, a drift of 15 m by the reset | `SP` rose above 1 right away: you sent a jump, not a frozen pose, or forgot to update the timestamp and the messages stopped being accepted as new |
| Stopped feed | "EKF variance" and Land after 7.9 s, a drift of 6.0 m until touchdown, a gap of 4.9 m | Land did not happen: `FS_EKF_ACTION = 0`, or the mode does not need a position (AltHold) |
| 5 m jump | `SP` 3.4 → below 1 in about 4.5 s, then a permanent offset of 5.0 m | The jump was accepted instantly: you changed `reset_counter`; that is right for a VIO reinitialization, but not for a fault |

## diagnostics
- **Symptom:** the EKF does not accept VIO (XKF4.SP > 1 all the time)
  - Possible cause: the coordinate frame/camera orientation, the delay, the scale.
  - What to do: VISO_ORIENT/POS, DELAY_MS, compare VISP with XKF1 axis by axis and sign by sign.
- **Symptom:** the position drifts while stationary
  - Possible cause: VIO without texture/light, a bad camera–IMU calibration.
  - What to do: lighting/texture, recalibration, the time offset.
- **Symptom:** a position jump during a turn
  - Possible cause: tracking lost during fast rotation (rolling shutter).
  - What to do: a global shutter, limit the yaw rate, a shorter exposure.
- **Symptom:** after losing VIO the vehicle flew away
  - Possible cause: the companion kept sending a "frozen" pose.
  - What to do: tracking status → stop publishing; FS_EKF_ACTION; a backup source set.
- **Symptom:** PX4 rejects the odometry
  - Possible cause: the frame (ENU vs NED), EKF2_EV_CTRL not set, no timestamp.
  - What to do: the MAVROS frame_id, the EV parameters, timesync.
- **Symptom:** ArduPilot "does not see" `ODOMETRY`: no `VISP` in the log, the EKF does not report "using external nav data"
  - Possible cause: `frame_id` is not `MAV_FRAME_LOCAL_FRD` or `child_frame_id` is not `MAV_FRAME_BODY_FRD`, so the message is dropped without a warning.
  - What to do: set both fields; or send `VISION_POSITION_ESTIMATE`.
- **Symptom:** after the VIO "comes back", the vehicle keeps drifting for a few seconds, then the position jumps
  - What the log shows: `XKF4.SP` > 1 right after the recovery, then a reset after ~7 s.
  - Possible cause: there was a frozen pose before; the estimate went further from the truth than the gates allow.
  - What to do: a freeze detector on the companion (step 6), and on recovery, increment `reset_counter`.
- **Symptom:** a permanent position offset of a few meters after a VIO reinitialization
  - Possible cause: a jump without `reset_counter`: the gates rejected it for 4–5 s, then accepted it.
  - What to do: increment `reset_counter` on every reinitialization or loop closure.
- **Symptom:** PX4: the VIO position is there, but the height "moves" with the terrain under the vehicle
  - Possible cause: `EKF2_HGT_REF = 2` (range sensor) over an uneven surface: the reference height is the distance to whatever is under the vehicle.
  - What to do: `EKF2_HGT_REF = 0` (baro) or 3 (vision); a rangefinder as the reference only over a flat floor.

## references
- ArduPilot — Non-GPS Navigation (landing page: VIO cameras, ExternalNav) | https://ardupilot.org/copter/docs/common-non-gps-navigation-landing-page.html | primary | A
- ArduPilot 4.7.3 — AP_VisualOdom (VISO_* parameters, 300 ms timeout) | https://github.com/ArduPilot/ardupilot/tree/Copter-4.7.3/libraries/AP_VisualOdom | primary | A
- ArduPilot 4.7.3 — GCS_Common.cpp (handle_odometry, handle_vision_position_estimate) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.3/libraries/GCS_MAVLink/GCS_Common.cpp | primary | A
- PX4 — Using Vision or Motion Capture Systems for Position Estimation (EKF2_EV_*) | https://docs.px4.io/main/en/ros/external_position_estimation.html | primary | A
- PX4 v1.18.0 — params_external_vision.yaml | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/modules/ekf2/params_external_vision.yaml | primary | A
- OpenVINS — repository and documentation (VIO, calibration requirements) | https://github.com/rpng/open_vins | primary | A
- Qin, Li, Shen — VINS-Mono: A Robust and Versatile Monocular Visual-Inertial State Estimator (4 unobservable degrees of freedom) | https://arxiv.org/abs/1708.03852 | secondary | A

## checklist
- I understand the difference between flow / VIO / SLAM and their drift
- I know that VIO does not observe position and heading, and that scale needs acceleration
- I know what breaks VIO: texture, light, dynamics, calibration, synchronization
- I fed ExternalNav into EKF3 (or EV into EKF2) and saw it accepted in the log
- A hold without GPS in SITL on an external source
- I worked through the three failures in SITL and know why a frozen pose is worse than a stopped feed
- A freeze detector on the companion, `reset_counter` on reinitialization, a backup source set
