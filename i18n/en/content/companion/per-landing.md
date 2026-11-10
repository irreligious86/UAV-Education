---
id: per-landing
title: "Precision landing on a marker: ArUco, LANDING_TARGET, PLND"
level: L4
readingTime: 45 min
firmware: ArduPilot · PX4 · companion
status: published
added: 2026-11-08
tags:
  - precision landing
  - ArUco
  - AprilTag
  - LANDING_TARGET
  - PLND
related:
  - per-geometry
  - per-camera
  - mav-services
  - ap-companion
next:
  - per-depth-avoid
source: content/companion/per-landing.md
source_hash: f90ad0fb6781
---

## summary
GPS lands the vehicle to within a meter or two; a charging station, the bed of a truck or a small pad needs 10–15 cm. Precision landing closes the loop through a camera: a marker (ArUco/AprilTag or an IR-LOCK infrared beacon) → marker pose relative to the camera → direction to the target in the vehicle frame → the autopilot descends while holding position over the target. This module goes through every link: which markers and why nested ones, how to turn a marker pose into a `LANDING_TARGET` message and what its fields mean, how ArduPilot uses it (`PLND_*`, the target filter, retries) and PX4 (`PLD_*`, Required/Opportunistic modes), and, most importantly, what the system does when the marker disappears at 3 m and at 0.5 m. The lab is SITL with a camera in Gazebo or on recorded video, landing error over 10 approaches.

## theory
### How the target is marked
- **IR-LOCK**: an IR beacon + a dedicated camera that outputs the beacon's coordinates in the frame. Works at night and in sunlight (narrow IR filter), gives no heading. Supported by autopilots directly (`PLND_TYPE = 2` in ArduPilot; the standard path in PX4).
- **ArUco / AprilTag**: black-and-white square coded markers. The detector finds the 4 corners with subpixel accuracy, and knowing the marker side length, `solvePnP` gives the full pose: position and heading. They need light and contrast; they work with any camera via a companion. AprilTag (family 36h11) is more robust against false detections, ArUco is faster and ships with OpenCV out of the box (`cv2.aruco`).
- **Nested marker**: a large marker (80 cm) for acquisition from 10–15 m and a small one (10–15 cm) inside or next to it for the last meter, when the large one no longer fits in the frame. Without it the landing loses the target at ~1 m, exactly when it's needed most.

Marker size and acquisition range: the marker should span ≥ 20–30 pixels per side. At f = 600 px, a 0.5 m side gives 30 px at 10 m. So the large marker is for altitude, the small one is for near the ground.

### From pixels to LANDING_TARGET
`LANDING_TARGET` (ID 149) is a message from the companion to the autopilot. Key fields:
- `angle_x`, `angle_y`: the angular offset of the target from the optical axis along the x and y axes of the **image** (rad). This is the minimal variant: the autopilot itself converts the angles to meters using its altitude (rangefinder!) and attitude.
- `distance`: distance to the target (m), if known (from PnP or a rangefinder).
- `size_x`, `size_y`: the angular size of the target.
- `frame`: the coordinate frame (usually `MAV_FRAME_BODY_FRD` for the angle version).
- Extended version: `position_valid = 1` and the fields `x, y, z`, the target position in meters in the given frame, plus `q`, the target orientation. You fill it in when PnP gives a full pose. With `position_valid = 1`, ArduPilot requires `distance > 0` (otherwise the message is dropped) and doesn't use `q`; PX4 accepts only `x, y, z` in `MAV_FRAME_LOCAL_NED`.
- `time_usec`: the **frame exposure** time on the companion's monotonic clock (not the send time). ArduPilot doesn't require clock synchronization: its jitter correction (`correct_offboard_timestamp_usec_to_ms`) estimates the offset between the companion's clock and its own from the fastest messages. A consequence worth understanding: the **variable** part of the latency (processing taking 30 ms one time, 90 ms the next) gets removed this way, but the **constant** part is indistinguishable from a clock offset, so you set it with the `PLND_LAG` parameter. Without a correct timestamp and `PLND_LAG`, 50–100 ms of camera latency turns into oscillation over the target.

Angles for a downward camera: angle_x = atan(x_n), angle_y = atan(y_n), where (x_n, y_n) are the normalized coordinates of the marker center after undistortion. The function `landing_target_angles()` in `examples/perception/camgeo.py` does exactly that.

{{diagram:landing-loop|The precision landing loop: camera → detector → pose → LANDING_TARGET with the exposure timestamp → target filter in the autopilot → position loop during descent.}}

### ArduPilot: PLND
Enabling it: `PLND_ENABLED = 1`, source `PLND_TYPE` (1: MAVLink from a companion, 2: IR-LOCK, 3/4: SITL). Landing on the target works in LAND, during the landing phase of RTL and in a mission on a LAND command. The parameters that decide the outcome:
- `PLND_EST_TYPE`: 0 is raw measurements, 1 is a Kalman filter on the target (smooths and survives short dropouts, recommended).
- `PLND_CAM_POS_X/Y/Z`: camera position relative to the vehicle center; `PLND_YAW_ALIGN`: camera rotation relative to the nose (in centidegrees).
- `PLND_LAG`: measurement latency (s), to align with the history of inertial data.
- `PLND_XY_DIST_MAX`: if the horizontal error is larger than this, the vehicle doesn't descend but first aligns itself over the target.
- `PLND_STRICT`: what to do when the target is lost: 0 is land vertically (not strict), 1 is retry the approach (default), 2 is don't land, hover (very strict).
- `PLND_TIMEOUT`: how many seconds to keep descending without a target before the STRICT decision; `PLND_RET_MAX`: how many retries; `PLND_RET_BEHAVE`: where to return to (the last place the target was seen, or its estimate).
- `PLND_ALT_MIN`: below this altitude (by rangefinder) the landing continues even without a target: at 50 cm the camera often can no longer see the whole marker, and abandoning the landing there is more dangerous than finishing it. `PLND_ALT_MAX`: above this altitude a missing target isn't considered a problem yet.

In practice a rangefinder is mandatory: both for converting angles to meters and for `PLND_ALT_MIN/MAX`.

### PX4: precision landing
The standard path is the IR-LOCK beacon: the `irlock` driver → `landing_target_estimator` → the `landing_target_pose` topic. Newer versions add a Vision Target Estimator for visual targets; check the documentation for your version for the supported sources (including targets coming from a companion over MAVLink). The modes are set by `param2` of the `MAV_CMD_NAV_LAND` command: 0 is a normal landing, 1 is **Opportunistic** (precise only if the beacon is visible at the start of the landing), 2 is **Required** (if it isn't visible, search). Parameters:
- `PLD_HACC_RAD`: horizontal acceptance radius: while the offset is larger, the vehicle approaches horizontally instead of descending.
- `PLD_FAPPR_ALT`: final approach altitude: below it the descent continues even if the target is lost.
- `PLD_SRCH_ALT`, `PLD_SRCH_TOUT`, `PLD_MAX_SRCH`: search altitude, search time and number of attempts.
- `PLD_BTOUT`: how long the beacon may go unobserved before a search starts (Required) or a normal landing begins (Opportunistic).

Note the common logic in both autopilots: above a threshold, losing the target is a reason to stop and search; below it, keep going. This isn't a coincidence but the only sensible answer to the physics: near the ground the camera goes blind from the vehicle's own shadow and proximity, and climbing away from 30 cm is riskier than landing.

### Landing phases and timing
A typical sequence from 10 m: target acquisition (large marker) → alignment over the target until the error is < `XY_DIST_MAX` → descent at 0.5–1 m/s while holding position → switch to the small marker at 2–3 m → final descent at 0.3 m/s → touchdown. A 30 fps camera with 60 ms latency and a 0.5 m/s descent: between the frame and the command the vehicle drops 3 cm. Wind doesn't push the vehicle off by “wind × latency”: position is held by the autopilot's inertial loop, the camera only refines where the target is. But for that, the target filter has to compare the measurement with the vehicle position **at the moment of the frame**, hence the exposure timestamp (removes jitter) and `PLND_LAG` (the constant part of the latency, used by ArduPilot to pull attitude and position from history). In the ArduPilot log you see this in the `PL` message: `Heal` (target healthy), `TAcq` (acquired), `pX/pY` (target position estimate), `mX/mY/mZ` (measurement), `LastMeasMS`.

### What breaks precision landing
- Glare and the vehicle's shadow on the marker on a sunny day: a matte material and a marker in the shade don't always save you; IR-LOCK is more robust.
- The marker is rotated relative to the frame: not a problem for ArUco, but the heading from PnP is noisy at low altitude; don't rotate the vehicle to follow the marker heading below 1–2 m.
- A sign or axis error in `LANDING_TARGET`: the vehicle moves away from the target and flies a “spiral.” This is the first thing to check in SITL.
- The rangefinder picks up the marker, grass or the vehicle's own landing gear legs: check `RFND` in the log over the last meter.

## practice
### Step 1. Detector and pose
On a recorded landing video (or one shot from above with a phone over a printed 15 cm marker), find the marker with `cv2.aruco.ArucoDetector` and estimate the pose with `solvePnP` using the calibration from the geometry module. Plot the distance to the marker and compare it with a tape measure at three heights. Note the height at which the marker is lost (side < 20 px): that's the boundary for the nested marker.

### Step 2. LANDING_TARGET in SITL
Run ArduPilot SITL with `PLND_ENABLED = 1`, `PLND_TYPE = 1`, `PLND_EST_TYPE = 1` and a rangefinder (`RNGFND1_TYPE = 100`, SITL). Write a sender:

```python
import math, time
from pymavlink import mavutil
import camgeo as cg   # examples/perception

m = mavutil.mavlink_connection("udpin:127.0.0.1:14550", source_system=1, source_component=mavutil.mavlink.MAV_COMP_ID_ONBOARD_COMPUTER)
m.wait_heartbeat()   # udpin learns the sender's address only from the first packet
K = cg.K_matrix(600, 600, 320, 240)

def send_target(u, v, t_exposure_s, distance_m=0.0):
    ax, ay = cg.landing_target_angles(u, v, K)
    m.mav.landing_target_send(int(t_exposure_s * 1e6), 0, mavutil.mavlink.MAV_FRAME_BODY_FRD,
                              ax, ay, distance_m, 0.0, 0.0)
```
In SITL without Gazebo, feed a synthetic target: compute the target pixel from a given ground point with `ground_to_pixel` using the current ATT and altitude from telemetry. Switch the vehicle to LAND from 10 m. In the log check `PL`: `TAcq = 1`, `pX/pY` converge to zero during alignment, `LastMeasMS` keeps updating.

### Step 3. Failures
Repeat the landing 10 times with a random initial offset of 2–4 m and wind (`SIM_WIND_SPD = 4`). Record the touchdown error. Then “drop” the target for 3 s at 4 m and at 0.5 m with `PLND_STRICT` = 0, 1, 2: describe the behavior and compare it with the parameter documentation.

The lab counts as done when you have a plot of marker-based range versus the tape measure, 10 landings with an error ≤ 15 cm in 9 of them, and a table of the target-loss behavior for the three values of `PLND_STRICT`.

## diagnostics
- **Symptom:** the vehicle flies a spiral over the target or moves away from it
  - Possible cause: the angle_x/angle_y axes/signs are mixed up, or `PLND_YAW_ALIGN` isn't accounted for.
  - What to do: in SITL move the target north; the vehicle must go north. Check each axis separately.
- **Symptom:** oscillation over the target that grows during descent
  - Possible cause: camera latency without an exposure timestamp, or a wrong `PLND_LAG`.
  - What to do: `time_usec` = exposure time on the companion's monotonic clock; measure the constant camera → autopilot latency and set it in `PLND_LAG`.
- **Symptom:** the landing is abandoned in the last meter
  - Possible cause: the marker doesn't fit in the frame, there's no nested marker; `PLND_ALT_MIN` = 0 or the rangefinder is lying.
  - What to do: a nested marker, check `RFND`, set `PLND_ALT_MIN`.
- **Symptom:** the target isn't accepted, there's no `PL` in the log
  - Possible cause: `PLND_TYPE` isn't 1, the messages come from the wrong system, no rangefinder.
  - What to do: check the sender's sysid/compid, a rate of ≥ 10 Hz, that a rangefinder is present.

## references
- MAVLink — LANDING_TARGET | https://mavlink.io/en/messages/common.html#LANDING_TARGET | primary | A
- ArduPilot — Precision Landing and Loiter | https://ardupilot.org/copter/docs/precision-landing-with-irlock.html | primary | A
- ArduPilot — AC_PrecLand source (PLND_* parameters, MAVLink backend) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/AC_PrecLand | primary | A
- PX4 — Precision Landing | https://docs.px4.io/main/en/advanced_features/precland | primary | A
- OpenCV — Detection of ArUco markers | https://docs.opencv.org/4.x/d5/dae/tutorial_aruco_detection.html | primary | A

## checklist
- I pick a marker and size for the acquisition altitude; I know why a nested marker is needed
- I get the marker pose via PnP and verify it with a tape measure
- I fill in LANDING_TARGET: angles, distance, coordinate frame, exposure time
- I configure PLND_* (or PLD_*) and understand the logic of the altitude thresholds
- I check the behavior on target loss above and below the threshold
- I measure the landing error over a series of approaches
