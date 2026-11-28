---
id: per-landing
title: "Precision landing on a marker: ArUco, LANDING_TARGET, PLND"
level: L4
readingTime: 45 min
firmware: ArduPilot 4.7 (checked against 4.7.3) · PX4 1.18 (checked against v1.18.0) · companion
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
source_hash: 0dbced3e16b5
---

## summary
GPS lands a vehicle to within a meter or two; a charging station, a truck bed or a small pad needs 10–15 cm. Precision landing closes the loop through a camera: a marker (ArUco/AprilTag or an IR-LOCK infrared beacon) → the marker pose relative to the camera → the direction to the target in the vehicle frame → the autopilot descends while holding over the target. This module covers every link: which markers and why nested ones, how to turn the marker pose into a `LANDING_TARGET` message and what its fields mean, how ArduPilot uses it (`PLND_*`, the target filter, landing retries) and how PX4 does (`PLD_*`, Required/Opportunistic modes), and, most importantly, what the system does when the marker disappears at 3 m and at 0.5 m. Lab: SITL with a camera in Gazebo or on recorded video, the landing error over 10 approaches.

## theory
### How the target is marked
- **IR-LOCK**: an IR beacon + a dedicated camera that outputs the beacon coordinates in the frame. Works at night and in sunlight (narrow IR filter), gives no heading. Supported by the autopilots directly (`PLND_TYPE = 2` in ArduPilot; the standard path in PX4).
- **ArUco / AprilTag**: black-and-white square markers carrying a code. The detector finds the 4 corners with subpixel accuracy, and given the marker side length `solvePnP` returns the full pose: position and heading. They need light and contrast and work with any camera through a companion computer. AprilTag (the 36h11 family) is more resistant to false detections; ArUco is faster and ships with OpenCV (`cv2.aruco`).
- **Nested marker**: a large marker (80 cm) for acquisition from 10–15 m and a small one (10–15 cm) inside or next to it for the last meter, when the large one no longer fits in the frame. Without it the landing loses the target at about 1 m, exactly when it is needed most.

Marker size and acquisition range: the marker side should span ≥ 20–30 pixels. At f = 600 px a 0.5 m side gives 30 px at 10 m. So the large marker is for altitude and the small one is for the ground.

### From pixels to LANDING_TARGET
`LANDING_TARGET` (ID 149) is a message from the companion to the autopilot. The key fields:
- `angle_x`, `angle_y`: the angular offset of the target from the optical axis along the x and y axes of the **image** (rad). This is the minimal variant: the autopilot converts the angles into meters itself using its own altitude (rangefinder!) and attitude.
- `distance`: the distance to the target (m), if known (from PnP or a rangefinder).
- `size_x`, `size_y`: the angular size of the target.
- `frame`: the coordinate frame (usually `MAV_FRAME_BODY_FRD` for the angle variant).
- The extended variant: `position_valid = 1` and the fields `x, y, z` give the target position in meters in the specified frame, plus `q`, the target orientation. You fill it in when PnP gives a full pose. With `position_valid = 1` ArduPilot requires `distance > 0` (otherwise the message is dropped) and does not use `q`; according to its documentation PX4 accepts only `x, y, z` in `MAV_FRAME_LOCAL_NED` (in the 1.18 code it turns the angle variant with `position_valid = 0` into an `irlock_report`, as if from IR-LOCK, with the receive time instead of `time_usec`).
- `time_usec`: the **frame exposure** time on the companion's monotonic clock (not the send time). ArduPilot does not require clock synchronization: its jitter correction (`correct_offboard_timestamp_usec_to_ms`) estimates the offset between the companion clock and its own from the fastest messages. A consequence worth understanding: the **variable** part of the latency (processing that takes 30 ms one time and 90 ms the next) is removed this way, while the **constant** part is indistinguishable from the clock offset, so you set it with the `PLND_LAG` parameter. Without a correct timestamp and `PLND_LAG`, a 50–100 ms camera latency turns into oscillation over the target.

Angles for a downward camera: angle_x = atan(x_n), angle_y = atan(y_n), where (x_n, y_n) are the normalized coordinates of the marker center after undistortion. The `landing_target_angles()` function in `examples/perception/camgeo.py` does exactly that.

{{diagram:landing-loop|The precision landing loop: camera → detector → pose → LANDING_TARGET with the exposure timestamp → target filter in the autopilot → position loop during descent.}}

### ArduPilot: PLND
Enabling: `PLND_ENABLED = 1`, source `PLND_TYPE` (1 MAVLink from a companion, 2 IR-LOCK, 3/4 SITL). Landing on the target works in LAND, in the landing phase of RTL, and in a mission on a LAND command. The parameters that decide the outcome:
- `PLND_EST_TYPE`: 0 RawSensor, 1 KalmanFilter (the target filter smooths and survives short dropouts; recommended).
- `PLND_CAM_POS_X/Y/Z`: the camera position relative to the vehicle center; `PLND_YAW_ALIGN`: the camera rotation relative to the nose (in centidegrees).
- `PLND_LAG`: the measurement lag (s), used to line up with the history of inertial data.
- `PLND_XY_DIST_MAX`: if the horizontal error is larger than this, the vehicle does not descend but first centers over the target.
- `PLND_STRICT`: what to do when the target is lost: 0 land vertically right away (not strict); 1 (default) keep descending for another `PLND_TIMEOUT` s, then retry the landing, and if the target is still not found, hover for 7 s (time to take over) and land vertically; 2 the same retry, but never land without the target, hover instead (very strict). That is how `AC_PrecLand_StateMachine` works in ArduPilot 4.7.
- `PLND_TIMEOUT`: how many seconds (default 4) to keep descending without the target before a retry (with STRICT 1 and 2); `PLND_RET_MAX`: how many retries per mode (default 4; 0 means no retries, go straight to hovering or landing according to STRICT); `PLND_RET_BEHAVE`: where to go back to (the last location where the target was detected, or toward its estimated location).
- `PLND_ALT_MIN`: below this height (by rangefinder) the landing continues even without the target: at 50 cm the camera often no longer sees the whole marker, and abandoning the landing there is more dangerous than finishing it. `PLND_ALT_MAX`: above this height a missing target is not yet treated as a problem.

In practice a rangefinder is mandatory: both for converting angles into meters and for `PLND_ALT_MIN/MAX`.

{{diagram:precland-lost-target|With no target, the rangefinder height decides: above PLND_ALT_MAX it is not yet a problem, below PLND_ALT_MIN the landing continues, and in between PLND_STRICT decides: 0 lands right away, 1 and 2 retry after PLND_TIMEOUT and differ only in whether they land without the target.}}

### PX4: precision landing
The standard path is the IR-LOCK infrared beacon: the `irlock` driver → `landing_target_estimator` → the `landing_target_pose` topic. Newer versions add the Vision Target Estimator for visual targets; check the documentation for your version for the supported sources (including targets sent by a companion over MAVLink). The modes are set by `param2` of the `MAV_CMD_NAV_LAND` command: 0 normal landing, 1 **Opportunistic** (precision landing only if the beacon is visible when landing is initiated), 2 **Required** (if it is not visible, search for it). Parameters:
- `PLD_HACC_RAD`: the horizontal acceptance radius: while the offset is larger, the vehicle approaches horizontally instead of descending.
- `PLD_FAPPR_ALT`: the final approach altitude: below it the descent continues even if the target is lost.
- `PLD_SRCH_ALT`, `PLD_SRCH_TOUT`, `PLD_MAX_SRCH`: the search altitude, the search timeout and the number of search attempts.
- `PLD_BTOUT`: how long the beacon may go unobserved before a search starts (Required) or a normal landing (Opportunistic).

Note the logic both autopilots share: above a threshold, losing the target is a reason to stop and search; below it, keep going. That is not a coincidence but the only sensible answer to the physics: near the ground the camera goes blind from its own shadow and the short range, and climbing away from 30 cm is riskier than landing.

### Landing phases and timing
A typical sequence from 10 m: acquire the target (large marker) → center over the target until the error is < `XY_DIST_MAX` → descend at 0.5–1 m/s while holding → switch to the small marker at 2–3 m → final descent at 0.3 m/s → touchdown. With a 30 frames/s camera, 60 ms of latency and a 0.5 m/s descent, the vehicle drops 3 cm between the frame and the command. Wind does not push the vehicle off by "wind × latency": the autopilot's inertial loop holds the position, and the camera only refines where the target is. But for that the target filter has to compare the measurement with the vehicle position **at the time of the frame**, hence the exposure timestamp (removes the jitter) and `PLND_LAG` (the constant part of the latency, used by ArduPilot to pick the attitude and position from its history). In the ArduPilot log you see it in the `PL` message: `Heal` (precision landing healthy), `TAcq` (acquired), `pX/pY` (estimated target position), `mX/mY/mZ` (measurement), `LastMeasMS`.

### What breaks precision landing
- Glare and the vehicle's shadow on the marker on a sunny day: a matte material and a marker in the shade do not always help; IR-LOCK is more robust.
- A marker rotated relative to the frame is no problem for ArUco, but the PnP heading is noisy at low altitude; do not rotate the vehicle to follow the marker heading below 1–2 m.
- A sign or axis error in `LANDING_TARGET`: the vehicle moves away from the target and "spirals"; this is the first thing to check in SITL.
- The rangefinder sees the marker, the grass or the vehicle's own landing gear: check `RFND` in the log over the last meter.

### Where it fits in the system

- **Takes in:** the marker pose from PnP and the angles from the optical axis (`per-geometry`); a frame with the exposure timestamp (`per-camera`); the height from the rangefinder (`est-alt-sources`).
- **Hands off:** `LANDING_TARGET` to the autopilot: landing on the target in LAND, in the landing phase of RTL and in a mission (`ap-missions`); 10–15 cm accuracy instead of a meter or two with GPS.
- **If you get this wrong:** signs or axes in `LANDING_TARGET` mixed up → the vehicle "spirals" away from the target; caught first in the simulator (`tools-gazebo`). `PLND_LAG` does not match the real camera latency → oscillation over the target that looks like a bad position tune; the latency is measured per stage in `per-vision-pipeline`.

## practice
### Step 1. Detector and pose
On a recorded landing video (or one shot from above with a phone over a printed 15 cm marker), detect the marker with `cv2.aruco.ArucoDetector` and estimate the pose with `solvePnP` using the calibration from the geometry module. Plot the distance to the marker and compare it with a tape measure at three heights. Note the height at which the marker is lost (side < 20 px): that is the boundary for the nested marker.

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
In SITL without Gazebo, feed a synthetic target: compute the target pixel from a given ground point with `ground_to_pixel`, using the current ATT and the altitude from telemetry. Switch the vehicle to LAND from 10 m. In the log check `PL`: `TAcq = 1`, `pX/pY` converge to zero as the vehicle centers, `LastMeasMS` keeps updating.

### Step 3. Failures
Repeat the landing 10 times with a random initial offset of 2–4 m and wind (`SIM_WIND_SPD = 4`). Record the touchdown error. Then "drop" the target for 6 s (longer than `PLND_TIMEOUT` = 4 s, otherwise STRICT 1 and 2 have no time to diverge) at a height of 4 m and at 0.5 m with `PLND_STRICT` = 0, 1, 2; describe the behavior and compare it with the parameter documentation.

Self-check: the lab is done when you have a plot of the marker range and at each of the three heights it differs from the tape measure by no more than Z/w (Z is the range, w is the marker side in the frame in pixels: a 1 px corner error changes the range by 1/w of its value; at f = 600 px and a 15 cm marker w = 90/Z, so about 1 cm at 1 m, 4 cm at 2 m and 10 cm at 3 m) and by no less than 2 cm (a tape measure to the lens is not more accurate than that); if the discrepancy is the same percentage at all heights, the marker side is set wrong or the calibration was made at a different resolution; the height at which the marker is lost is recorded (side < 20 px; at f = 600 px and 15 cm that is 600 · 0.15 / 20 = 4.5 m), the `PL` log shows `TAcq = 1` and `pX/pY` converging to zero, 9 of the 10 landings had an error ≤ 15 cm, and the table of target-loss behavior for the three values of `PLND_STRICT` matches the parameter description: 0 lands vertically, 1 retries, 2 does not land and hovers.

## diagnostics
- **Symptom:** over the target the vehicle spirals or moves away from it
  - Possible cause: the axes/signs of angle_x/angle_y are mixed up, or `PLND_YAW_ALIGN` is not accounted for.
  - What to do: in SITL move the target north and the vehicle must go north; check each axis separately.
- **Symptom:** oscillation over the target that grows during the descent
  - Possible cause: camera latency without an exposure timestamp, or a wrong `PLND_LAG`.
  - What to do: `time_usec` = the exposure time on the companion's monotonic clock; measure the constant camera → autopilot latency and set it in `PLND_LAG`.
- **Symptom:** the landing is abandoned in the last meter
  - Possible cause: the marker does not fit in the frame and there is no nested marker; `PLND_ALT_MIN` = 0 or the rangefinder is wrong.
  - What to do: a nested marker, check `RFND`, set `PLND_ALT_MIN`.
- **Symptom:** the target is not accepted: `PL.TAcq` stays 0 and `LastMeasMS` does not change (no `PL` at all means `PLND_ENABLED = 0`)
  - Possible cause: `PLND_TYPE` is not 1; an unsupported `frame` (ArduPilot takes only `MAV_FRAME_BODY_FRD`/`LOCAL_FRD` and says "Plnd: Frame not supported" once); `position_valid = 1` with `distance = 0`; `MAV_OPTIONS` bit 0 is set while the companion's sysid is neither `MAV_SYSID` nor within `MAV_GCS_SYSID`…`MAV_GCS_SYSID_HI` (PX4 does not filter by sysid); no rangefinder.
  - What to do: look for "Plnd: Frame not supported" in Messages, send with the vehicle's own sysid (as in the lab) or clear `MAV_OPTIONS` bit 0, a rate ≥ 10 Hz (ArduPilot drops a measurement older than 1 s), check that a rangefinder is present.

## references
- MAVLink — LANDING_TARGET | https://mavlink.io/en/messages/common.html#LANDING_TARGET | primary | A
- ArduPilot — Precision Landing and Loiter | https://ardupilot.org/copter/docs/precision-landing-with-irlock.html | primary | A
- ArduPilot — AC_PrecLand source (PLND_* parameters, MAVLink backend) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/AC_PrecLand | primary | A
- PX4 — Precision Landing | https://docs.px4.io/main/en/advanced_features/precland.html | primary | A
- OpenCV — Detection of ArUco markers | https://docs.opencv.org/4.x/d5/dae/tutorial_aruco_detection.html | primary | A

## checklist
- I choose a marker and its size for the acquisition height; I know why a nested marker is needed
- I get the marker pose with PnP and check it with a tape measure
- I fill in LANDING_TARGET: angles, distance, coordinate frame, exposure time
- I configure PLND_* (or PLD_*) and understand the logic of the height thresholds
- I check the behavior on target loss above and below the threshold
- I measure the landing error over a series of approaches
