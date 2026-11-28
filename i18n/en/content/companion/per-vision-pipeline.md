---
id: per-vision-pipeline
title: "Onboard machine vision end to end: calibration → detection → tracking → georeferencing → command"
level: L3
readingTime: 55 min
firmware: ArduCopter 4.7 (checked against 4.7.3; lab recorded on 4.6.3) · PX4 1.18 (parameters checked against v1.18.0)
status: published
tags:
  - machine vision
  - pipeline
  - latency
  - georeferencing
  - GUIDED
  - interlocks
related:
  - per-camera
  - per-geometry
  - per-cv
  - per-tracking
  - per-edge-ml
  - per-landing
next:
  - per-tracking
source: content/companion/per-vision-pipeline.md
source_hash: 2182287a4fdc
---

## summary
The perception modules take the links one at a time: the frame (per-camera), geometry (per-geometry), the detector (per-cv), the tracking loop (per-tracking), profiling (per-edge-ml). Here they are assembled into a "light on the sensor → command to the autopilot" pipeline, where every stage has a latency budget and a described failure. After the module you can measure glass-to-command by stage, evaluate a detector and a tracker by slices, turn a detection into a point on the ground with an honest timestamp, and close the loop through the autopilot so that a lost target, a hung process or a false target ends in a hover rather than a flyaway. The lab: the pipeline on a synthetic flight (40 s, 1200 frames) with a log of latencies and target coordinates, then a replay in ArduCopter SITL with GUIDED tracking, FOLLOW mode, and checks of the timeouts and the geofence.

## theory
### The pipeline and its budget
The exposure timestamp travels with the frame through every stage: it is used to pick the attitude and to compute the age of the data.

| Stage | What it does | Typical latency | Failure → what the next stage must see |
|---|---|---|---|
| Sensor | exposure + readout | 10–30 ms | overexposure, blur → no detections |
| Capture | V4L2/CSI → memory | 1–10 ms; USB MJPEG +10–20 | frame did not arrive → age grows, watchdog |
| Undistort | a point or the whole frame | ≈ 0.02 / 1–5 ms | wrong calibration → a systematic error at the edges |
| Detector | bbox + confidence | HSV 1–5 ms; YOLO-n on a CPU 25–300 ms (x86 and 320 px in the lab, a Pi 5 and 640 px at Ultralytics), several times less with an accelerator (per-edge-ml) | a miss or a false target |
| Tracker | association, ID, prediction | < 1 ms | an ID switch → the target "jumps" |
| Georeferencing | pixel → ray → ground | < 1 ms | ray above the horizon → `None`, not a point |
| Command | velocity/target, interlocks | < 1 ms | NaN, an outlier → discard |
| Link + FC | MAVLink, the autopilot loop | 3–20 ms | dropout → autopilot timeout |

The sum is the glass-to-command latency `T_d`. It, not the FPS, limits the loop gain: `K_p,max ≈ π/(2·T_d)` without the vehicle dynamics (the derivation is in per-tracking). The budget is allocated from the task (per-edge-ml).

{{diagram:vision-pipeline-budget|The budget from the lab: on 2 x86 cores the whole pipeline with the HSV detector takes 3.3 ms (p95), and the 36 ms of glass-to-command come from the sensor and the link; with YOLO11n on the CPU it is 65 ms, and inference becomes the main item.}}

### Capture: V4L2, CSI, GStreamer
The interfaces are in per-camera. Three things matter for the pipeline. **A fresh frame, not a queue:** `appsink drop=true max-buffers=1` in GStreamer or `CAP_PROP_BUFFERSIZE = 1` in OpenCV, otherwise you process a frame that is a second old. **Raw format:** `v4l2src device=/dev/video0 ! video/x-raw,width=640,height=480,framerate=30/1 ! videoconvert ! appsink drop=true max-buffers=1`; on a Pi with CSI the source is `libcamerasrc`, on a Jetson `nvarguscamerasrc` (comp-jetson-nano). **The timestamp:** a V4L2 buffer timestamp usually runs on `CLOCK_MONOTONIC` (the `V4L2_BUF_FLAG_TIMESTAMP_MONOTONIC` flag) and with most drivers is taken when the last pixel of the frame is received (`TSTAMP_SRC_EOF`); a few take the start of exposure (`TSTAMP_SRC_SOE`). The middle of the exposure is in neither, so check the buffer flags of your camera. The difference is nearly constant: you measure it once and subtract it. `time.time()` after `cap.read()` is a processing timestamp, not a frame timestamp.

### Undistort: the frame or a point
A full `cv2.remap` of 640×480 took 0.9 ms (p50) in the lab, and on a single-board computer it will be several times more, so measure it; `cv2.undistortPoints` for one point takes about 0.02 ms. Distortion usually does not bother a bbox detector, and geometry needs only the corrected point; a full undistort is justified for lines and markers near the edge of the frame. A side effect (with a number, in the lab): remap stretches objects near the edges, and the size gate lets the wrong things through.

### A detector for the task
| Task | Detector | What you get |
|---|---|---|
| Your own marker, landing | ArUco/AprilTag (per-landing) | pose and ID, almost no false positives; needs contrast and ≥ 20 px per marker |
| A bright object of known color and size | HSV + contours + an area gate from AGL | < 1 ms; goes blind in shadow and blur, but it stays silent rather than lying |
| People, cars, arbitrary classes | YOLO-n, fine-tuned on your own frames (per-cv) | robust to lighting and blur; 25–300 ms on a CPU, produces confident false targets |

A target of diameter `D` at altitude `h` takes up `s = D·f/h` pixels; below 8–10 px a neural network is unreliable, and area gates become meaningless. You choose by slices (lighting, blur, occlusion, background), not by average mAP: a miss costs a second of hovering, a false target costs a flight to the wrong place.

### The tracker and ID persistence
- **SORT:** a constant-velocity Kalman filter per object + the Hungarian algorithm on IoU; hundreds of Hz, but the ID is lost when the detector misses.
- **ByteTrack:** a second association pass for low-confidence detections: a target in shadow stays in its track, while the background is filtered out.
- **KCF, CSRT** (OpenCV): single-object template trackers between runs of a slow detector. KCF is fast but does not follow scale; CSRT is more accurate and slower. Both silently "drift" onto the background, so the detector rechecks them every 5–10 frames.

The autopilot needs one object with an ID that survives misses. Four rules: track confirmation (3 frames in the lab), life without detections `max_age` (15 frames = 0.5 s), an association gate (30 px), and target lock: keep the selected ID, and after a loss take a new track only within a radius of the last position (better in meters on the ground: pixels depend on altitude and roll).

### Georeferencing and time
The "pixel → ray → `R_bc` → `R_nb(roll, pitch, yaw)` → intersection with the ground at `h`" chain is in per-geometry (`camgeo.pixel_to_ground`). Here: where to get the attitude and altitude **at the moment of exposure**:
- `ATTITUDE` (50 Hz via `MAV_CMD_SET_MESSAGE_INTERVAL`) and `GLOBAL_POSITION_INT` (10 Hz) carry `time_boot_ms`, the autopilot's clock. The frame carries the companion's clock.
- The clock offset comes from `TIMESYNC` (#111): the companion sends `ts1` = its own nanoseconds, `tc1 = 0`; the autopilot returns the same `ts1` and its own `tc1`. `offset = tc1 − (ts1 + RTT/2)`, and you take the median over 10+ exchanges. In SITL over TCP: RTT 4.8 ms, offset spread 2.5 ms.
- The attitude is interpolated between neighboring `ATTITUDE` messages to the frame timestamp; "the latest one received" at 50 Hz is up to 20 ms old, plus the link.
- The error from a time offset near nadir: `δ ≈ h·tan(ω·Δt)`. 15 m, 27 °/s, 100 ms gives 0.71 m, against a pixel footprint of 3.75 cm.
- `GLOBAL_POSITION_INT.relative_alt` is the height above the takeoff point, not above the ground under the target. On a slope you need a rangefinder (`DISTANCE_SENSOR`, corrected for tilt) or an elevation map.

### What to send the autopilot
| Interface | When | ArduPilot 4.7 | PX4 1.18 |
|---|---|---|---|
| `LANDING_TARGET` | precision landing, Precision Loiter | `PLND_ENABLED = 1`, `PLND_TYPE = 1`; the angles `angle_x/angle_y`, or `position_valid = 1`, frame `MAV_FRAME_BODY_FRD`, `distance > 0`; `PLND_LAG` (0.02–0.25 s) = your glass-to-command | with `position_valid = 1`, only `MAV_FRAME_LOCAL_NED` and `x, y, z`; with `position_valid = 0` the angles go through as `irlock_report`; `PLD_BTOUT`, `PLD_SRCH_ALT` |
| `SET_POSITION_TARGET_LOCAL_NED`, velocities | tracking with your own controller | GUIDED, `type_mask = 3527`; without updates, `GUID_TIMEOUT` (3 s) → velocity 0 | Offboard, a stream of ≥ 2 Hz; `COM_OF_LOSS_T`, action `COM_OBL_RC_ACT` |
| Target coordinates | tracking with the autopilot's controller | FOLLOW mode: `GLOBAL_POSITION_INT` or `FOLLOW_TARGET` from `FOLL_SYSID`; `FOLL_POS_P`, `FOLL_DIST_MAX`; the timeout is `FOLL_TIMEOUT`, 3 s (the parameter appeared in 4.7; in 4.6 the same 3 s are hard-coded) | Follow Me: `FOLLOW_TARGET`; `FLW_TGT_HT`, `FLW_TGT_DST` |

`LANDING_TARGET.time_usec` is the moment of exposure on the companion's clock: ArduPilot converts it to its own clock (`correct_offboard_timestamp_usec_to_ms`), PX4 through its own timesync. The details of `PLND_*` and the landing phases are in per-landing.

### Interlocks in three layers
1. **Companion:** a velocity limit `v_max`; a watchdog: no confirmed target for 0.5 s → an explicit zero velocity; a 3 s timeout → a LOITER request (only when a pilot with a radio holds the throttle at mid-stick; without a pilot, BRAKE or zero velocity in GUIDED, see below) and a latch: tracking resumes only on the operator's command; discard NaNs and jumps.
2. **Autopilot:** `GUID_TIMEOUT`; the geofence `FENCE_ENABLE`, `FENCE_TYPE`, `FENCE_RADIUS`, `FENCE_ALT_MAX`, `FENCE_ACTION`; `AVOID_ENABLE` (default 3) stops a GUIDED velocity `FENCE_MARGIN` (2 m) short of the fence boundary (`AVOID_MARGIN` is the margin to obstacles seen by rangefinders, not to the fence). In PX4: `GF_ACTION`, `GF_MAX_HOR_DIST`, `MPC_XY_VEL_MAX`.
3. **Pilot:** the mode switch breaks the loop; after a mode change the companion stops sending commands.

Two facts from the lab. ArduCopter does **not** limit the GUIDED velocity by the `WP_SPD` parameter (before 4.7, `WPNAV_SPEED`, cm/s): in the run on 4.6.3 with `WPNAV_SPEED = 300` (3 m/s), a 6 m/s command is executed as 6.1 m/s, and in the 4.7.3 source the velocity target path is the same, so the limit has to be on the companion. And LOITER holds altitude only with the throttle at mid-stick: without a pilot with a radio, the timeout must lead to BRAKE or stay at zero velocity in GUIDED.

### Where it fits

- **Takes in:** a frame with an exposure timestamp (`per-camera`); calibration and geometry (`per-geometry`); a detector and a tracker (`per-cv`); `ATTITUDE` and `TIMESYNC` from the autopilot (`mav-services`).
- **Hands off:** `LANDING_TARGET` to precision landing (`per-landing`); GUIDED velocity setpoints or target coordinates for FOLLOW (`per-tracking`); the measured glass-to-command, into `PLND_LAG` and the K_p limit.
- **If you get this wrong:** a `time.time()` timestamp after reading the frame instead of the buffer timestamp → the attitude is taken for the wrong moment, and the point on the ground "floats" during maneuvers (`per-geometry`). The target is lost and there is no watchdog → the companion keeps sending the last velocity, `GUID_TIMEOUT` never fires, and the vehicle flies until it hits the geofence (`ap-safety-fs`).

## practice
The code is in `examples/vision-pipeline/` (`gen_video.py`, `pipeline.py`, `score.py`, `sitl_follow.py`, `make_dataset.py`), the geometry from `examples/perception/camgeo.py`. Dependencies: `opencv-python`, `numpy`, `pymavlink`; for the YOLO branch, `ultralytics`. The numbers are from 2 cores of a 2.1 GHz Xeon, Python 3.13, OpenCV 5.0; SITL is ArduCopter 4.6.3 (the build is in ap-sitl), instance `-I 4`.

### Step 1. Data
`gen_video.py` draws a flight without a dataset: a 640×480 nadir camera, 30 fps, f = 400 px, distortion k1 = −0.10, k2 = 0.02, altitude 15 ± 0.5 m, roll ±8° at 0.5 Hz and pitch ±5° at 0.35 Hz (up to 27 °/s). The target is an orange disc R = 0.4 m (Ø 21 px) moving on a 6 m circle at 0.6 m/s. Distractions: an orange rock R = 0.3 m, shadows, an exposure dip down to 0.25 at 20–24 s, blur at 28–30 s, occlusion at 33–35 s. Alongside it writes `telemetry.csv` (`ATTITUDE` at 50 Hz, `GLOBAL_POSITION_INT` at 10 Hz, each with its own `time_boot_ms`) and `truth.csv` for scoring.

```text
$ python3 gen_video.py data
wrote 1200 frames, K: fx=400.0, k1=-0.1, k2=0.02, AGL≈15.0 m, HFOV=77.3°
```

### Step 2. The pipeline and latency by stage
`pipeline.py` for each frame: read → undistort → HSV detector (mask, contours, an area gate of 0.8–1.3 of the expected radius and a circle fill of ≥ 0.6) → tracker (Kalman + nearest neighbor, ID lock) → georeferencing with the telemetry interpolated to the frame timestamp → the command `v = 0.8·(n, e)`, limited to 2 m/s, with the states TRACK / HOLD / LOITER. Every stage is wrapped in `time.perf_counter()`, and one line per frame goes into `targets.csv`.

```text
$ python3 pipeline.py data --undistort frame
1200 frames @ 30 fps, detector=hsv, undistort=full frame, select=lock, att offset +0 ms
stage      p50 ms   p95 ms   max ms
cap          0.25     0.79     4.27
und          0.91     1.31     4.04
det          0.73     1.01     4.94
trk          0.04     0.08     1.19
geo          0.07     0.12     0.93
cmd          0.00     0.00     0.04
total        2.05     3.11     7.22
```

Record p95 and max, not the mean: a max of 7.2 ms at a p50 of 2.1 is the OS scheduler, and on board the tail is longer. `cap` here is mp4 decoding, not the camera; exposure and the link enter the budget as typical values until a bench measurement.

### Step 3. Scoring by slices
`score.py` compares `targets.csv` with `truth.csv`: a frame is correct if the target is visible and the point on the ground is within 1 m. Four runs (`--undistort frame|point`, `--select maxhits`, `--detector yolo`):

| Configuration | nominal P / R | dark P / R | blur P / R | occlusion, false frames | detector p50, ms |
|---|---|---|---|---|---|
| HSV, frame undistort | 0.91 / 0.91 | 1.00 / 0.03 | 1.00 / 0.05 | 37 | 0.73 |
| HSV, point undistort | 1.00 / 0.99 | 1.00 / 0.03 | 1.00 / 0.05 | 3 | 0.83 |
| the same, "max hits" track selection | 1.00 / 0.99 | 1.00 / 0.03 | 1.00 / 0.05 | 16 | 0.82 |
| YOLO11n, fine-tuned | 0.98 / 0.98 | 1.00 / 1.00 | 1.00 / 1.00 | 36 | 25.2 |

```text
$ python3 pipeline.py data --undistort point > /dev/null && python3 score.py data
slice                 TP    FP    FN  precision  recall
nominal              952     0     8       1.00    0.99
dark (gain 0.25)       3     0   117       1.00    0.03
motion blur            3     0    57       1.00    0.05
occluded               0     3     0       0.00    0.00
geo error on TP frames: mean 0.13 m, p95 0.20 m, max 0.43 m
track IDs used on TP frames: [1, 13, 18, 22]  (ID switches = 3)
interlock states: {'HOLD': 210, 'TRACK': 961, 'LOITER': 29}
```

How to read the table. **Frame undistort dropped nominal to 0.91:** the rock should take up 201 px², against a lower gate bound of 229 px², but after remap it passes the gate in 564 frames out of 1200 (without remap, in 119). After the occlusion at second 33, the tracker took the rock 93 px from the target's last position (the reacquisition radius is 100 px) and kept reporting its coordinates until the end of the recording: 77 false frames and 79 misses. The average over the recording hides this; the slice does not. **HSV goes blind in the dark and in blur** (recall 0.03–0.05), but produces no false points: the watchdog moves the loop to HOLD, which is a safe failure. **"Max hits" instead of a lock** gives 16 false frames during the occlusion against 3: the stationary rock accumulates hits. **YOLO** gets through shadow and blur, but during the occlusion it reports coordinates for 36 frames (1.2 s) while the target is not visible, and it costs 25 ms. A caveat: the network was fine-tuned on 240 frames of this same flight (192/48, 8 epochs, `imgsz 320`, mAP50 0.994), so this is a latency measurement, not a generalization result; an honest evaluation needs a different flight (per-cv). The three ID switches are one per each loss longer than `max_age`.

### Step 4. Time
The same run, but with the attitude taken at an offset (`--att-offset-ms`), as if the frame timestamp were wrong:

```text
$ for o in 0 50 100; do python3 pipeline.py data --undistort point --att-offset-ms $o > /dev/null; python3 score.py data | grep geo; done
geo error on TP frames: mean 0.13 m, p95 0.20 m, max 0.43 m
geo error on TP frames: mean 0.34 m, p95 0.50 m, max 0.76 m
geo error on TP frames: mean 0.58 m, p95 0.85 m, max 0.99 m
```

{{diagram:chart-vision-timesync|A 100 ms offset between the frame and ATTITUDE gives a 0.58 m mean error and 0.85 m at p95 at 15 m altitude, 4.5 times more than the whole rest of the chain (0.13 m). The measured p95 lies on the h·tan(ω·Δt) estimate.}}

The remaining 0.13 m at zero offset is the pixel (3.75 cm), the altitude at 10 Hz and the linear interpolation.

### Step 5. Replay in SITL: tracking and timeouts
```text
$ arducopter -w -S --model + -I 4 --speedup 1 --home -35.363261,149.165230,584,353 --defaults copter.parm
$ python3 sitl_follow.py tcp:127.0.0.1:5800 data/targets.csv
heartbeat from sysid 1, firmware: 4.6.3
== 0. TIMESYNC
   RTT median 4.81 ms, FC clock - companion clock = -2213530.2 ms (spread 2.52 ms)
…
== 3. GUIDED velocity follow (replay of targets.csv at 30 fps, commands at 10 Hz)
   t=  0.0s None->TRACK  v_fc=(+0.0,+0.0) m/s  alt=14.6 m  mode=GUIDED
   t= 20.6s TRACK->HOLD  v_fc=(-0.8,+0.2) m/s  alt=14.9 m  mode=GUIDED
   t= 23.2s HOLD->LOITER  v_fc=(-0.0,-0.0) m/s  alt=14.9 m  mode=LOITER
   t= 24.3s target is back, operator re-enables follow:   mode GUIDED
   t= 24.3s LOITER->TRACK  v_fc=(+0.0,-0.0) m/s  alt=14.9 m  mode=GUIDED
   t= 28.7s TRACK->HOLD  v_fc=(-0.7,-0.5) m/s  alt=14.9 m  mode=GUIDED
   t= 30.1s HOLD->TRACK  v_fc=(-0.0,-0.0) m/s  alt=14.9 m  mode=GUIDED
   t= 33.6s TRACK->HOLD  v_fc=(-0.6,-0.5) m/s  alt=14.9 m  mode=GUIDED
   t= 35.1s HOLD->TRACK  v_fc=(-0.0,-0.0) m/s  alt=14.9 m  mode=GUIDED
   sent 289 velocity setpoints; interlock states: TRACK=248, HOLD=41, LOITER=8
   |v| before first HOLD 0.97 m/s, 1.5-2.5 s after 0.03 m/s
== 4. FOLLOW mode: pipeline publishes the target as sysid 200 GLOBAL_POSITION_INT
   horizontal distance to target: start 18.8 m, t=10 s 13.9 m, mean over the last 5 s 1.5 m; |v| max 2.6 m/s, alt 14.9-15.0 m
   target stream stops (dark slice: the pipeline has nothing to publish)
   …
   +3 s: pos=(-4.2,+5.3) m v=(-0.4,-0.1) m/s mode=FOLLOW
   +4 s: pos=(-4.4,+5.3) m v=(-0.0,+0.0) m/s mode=FOLLOW
```

The output is abridged (omissions are marked "…"). The script sets `FENCE_ENABLE = 1`, `FENCE_TYPE = 3`, `FENCE_RADIUS = 60`, `FENCE_ALT_MAX = 30`, `FENCE_ACTION = 1`, `GUID_TIMEOUT = 3`, `FOLL_ENABLE = 1`, `FOLL_SYSID = 200`, `FOLL_POS_P = 0.3`, `FOLL_OFS_Z = -15`, takes off to 15 m and reads `targets.csv` in real time. This is a replay without feedback: it checks the command path and the interlocks, not the tracking quality. The exposure dip (20–24 s): 0.5 s after the last detection a zero velocity goes out (0.97 → 0.03 m/s), and after 3 s LOITER with the latch; the blur and the occlusion (2 s each) stay within HOLD. In FOLLOW the pipeline publishes the target coordinates as sysid 200 at 10 Hz: the vehicle closes 18.8 m down to 1.5 m, and when the stream stops, it stops by itself after 3 s: that is `AP_FOLLOW_TIMEOUT_MS`. The "pilot" in SITL is simulated by `RC_CHANNELS_OVERRIDE` with throttle at 1500: without it, LOITER descends after the timeout.

### Step 6. Autopilot interlocks
```text
== 5. speed limit and GUID_TIMEOUT: companion goes silent in GUIDED
   …
   6.0 m/s north commanded, +4 s: pos=(+17.3,+5.3) m v=(+6.1,+0.0) m/s mode=GUIDED
   1.5 m/s north commanded for 3 s: pos=(+30.1,+5.3) m v=(+1.4,-0.0) m/s mode=GUIDED; now silent
   …
   +3 s silence: pos=(+34.5,+5.3) m v=(+1.5,+0.0) m/s mode=GUIDED
   +4 s silence: pos=(+35.3,+5.3) m v=(+0.2,-0.0) m/s mode=GUIDED
   +5 s silence: pos=(+35.4,+5.3) m v=(+0.0,-0.0) m/s mode=GUIDED
== 6. geofence: companion keeps commanding 3 m/s north, FENCE_RADIUS = 60 m
   after 40 s: pos=(+58.0,+0.3) m v=(+0.0,-0.0) m/s mode=GUIDED
   fence shrinks to 30 m while the vehicle is outside it (the same as flying through a fence without avoidance)
   FC: Circle fence breached
   3 s later, still sending 3 m/s north: pos=(+54.4,+0.2) m v=(-2.6,-0.0) m/s mode=RTL
```

Three conclusions. `WPNAV_SPEED = 300` (the run on 4.6.3; in 4.7, `WP_SPD = 3`) did not limit the GUIDED velocity: 6.1 m/s. A companion that goes silent costs `GUID_TIMEOUT` seconds of flight at the last velocity: in the log, 5.3 m at 1.5 m/s (30.1 → 35.4 m), and at 6 m/s that would be 18 m, so your own 0.5 s watchdog is mandatory. For a GUIDED velocity the geofence works like a wall: the vehicle stopped at 58.0 m with a 60 m radius (`FENCE_MARGIN` 2 m) and stayed in GUIDED; a crossed boundary gives "Circle fence breached" and RTL, and the companion's commands are ignored after that.

### Moving to real hardware
1. **Calibration and timestamp.** A chessboard, 20+ frames, reprojection RMS < 1 px (per-geometry); `K` and `dist` go into `pipeline.py`. Measure the camera latency with an LED (per-camera): that is the correction to the frame timestamp.
2. **Bench, props off.** The companion and the camera on the frame, the frame on a stand, the camera pointing down 1.5 m above the floor (measured with a tape), a printed orange circle Ø 20 cm and a ruler on the floor. The autopilot on USB, `ATTITUDE` at 50 Hz. Record 60 s of video with frame timestamps and `telemetry.csv`, and run `pipeline.py`. Checks: the target at five points (center and four at 0.5 m): error ≤ 5 cm; rock the frame by hand ±10° at 1 Hz: the point stays within 8 cm, and fitting `--att-offset-ms` for the minimum error gives the residual time offset (it should be within ±10 ms); cover the target: a zero command after 0.5 s, and the LOITER request after 3 s is visible in the GCS; moving the target north gives `vn > 0`, east gives `ve > 0`. Acceptance: p95 and glass-to-command are recorded and fit the budget, `PLND_LAG` or `K_p` is set from the measured latency, and the signs are correct.
3. **Tether or low hover: the first step with props.** An open area, a 5 m tether to a weight or a hover at 3 m; `v_max` = 1 m/s, `K_p` = 0.3, `FENCE_RADIUS = 30`, `FENCE_ALT_MAX = 10`, battery ≥ 50 %. The pilot holds the throttle at mid-stick with a finger on the Loiter switch, and an observer watches the tether. The target is on a 3 m pole or an RC car, not held by hand; up to 1 m/s. Abort (Loiter from the radio, then land): oscillations grow for two periods in a row; the vehicle moves more than 1 m with the target stationary; the velocity is not zero 1 s after the target is covered; horizontal speed above 1.5 m/s; altitude off by 1 m; the tether goes taut; telemetry is lost; the companion throttles. Acceptance: three 60 s passes without any abort criterion triggering, lag behind the target ≤ 1 m, target covered → HOLD within ≤ 1 s and Loiter at the 3rd second, the companion and autopilot logs aligned by `TIMESYNC`.

Self-check: the lab is done when (SITL): you have a table of p50/p95/max by stage and a glass-to-command budget with your own numbers; scoring on the four slices for both undistort configurations, with the nominal drop explained by the size gate and the reacquisition, and after the fix nominal ≥ 0.95 / 0.95 and a ground error p95 < 0.3 m; the offsets 0 / 50 / 100 ms have been run and the growth of the error compared with `h·tan(ω·Δt)`; the `sitl_follow.py` output shows TRACK → HOLD after 0.5 s, LOITER after 3 s, the stop by `GUID_TIMEOUT` and by the FOLLOW timeout, the stop at the geofence and RTL on breaching it, and a velocity above `WP_SPD`. (Hardware): calibration RMS < 1 px; the bench table: error ≤ 5 cm at 1.5 m, a residual time offset within ±10 ms, the command signs; three tethered passes without abort criteria.

## diagnostics
- **Symptom:** the point on the ground "floats" by 0.5–1 m in step with the roll, although the target is stationary
  - Possible cause: the attitude is taken from the latest `ATTITUDE` rather than interpolated to the exposure timestamp; the frame timestamp is the time after `cap.read()`.
  - What the log shows: the error correlates with the angular rate, not with the angle.
  - What to do: the camera buffer timestamp + `TIMESYNC`, interpolation; fit the residual offset on the bench by rocking the frame.
- **Symptom:** after an occlusion or a shadow the vehicle confidently flies toward a rock, a shadow, someone else's car
  - Possible cause: reacquisition by pixels without a check on the ground; the size gates are too wide, or the frame is stretched by a full undistort.
  - What to do: score on the "after a loss" slice; undistort only the point; a reacquisition radius in meters around the prediction; after the timeout, a latch until the operator's command.
- **Symptom:** the command lags by a second or more, and the loop oscillates
  - Possible cause: a frame queue in the driver or GStreamer; inference is slower than the camera.
  - What to do: `drop=true max-buffers=1`; detection every 2–3 frames with the tracker in between; recompute `K_p` from the measured `T_d`.
- **Symptom:** the companion hung, and the vehicle flies on at the last velocity for another three seconds
  - Possible cause: this is the normal behavior of `GUID_TIMEOUT`; the watchdog was in the same process that hung.
  - Consequences: 18 m of travel at 6 m/s.
  - What to do: `GUID_TIMEOUT` of 0.5–1 s; the watchdog in a separate process or systemd; the geofence enabled.
- **Symptom:** 6 m/s was requested, and it flies at 6 m/s with `WP_SPD = 3`
  - Possible cause: `WP_SPD` does not limit `SET_POSITION_TARGET_LOCAL_NED` velocities (measured on ArduCopter 4.6.3, the 4.7.3 code is the same).
  - What to do: a `v_max` limit on the companion, a check in SITL before flight.
- **Symptom:** after the timeout the vehicle descends in LOITER
  - Possible cause: the throttle stick is down, or there is no radio.
  - What to do: the pilot holds the throttle at mid-stick; without a pilot, BRAKE or zero velocity in GUIDED.
- **Symptom:** "Plnd: Frame not supported", or PX4 reports "Landing target: coordinate frame … unsupported"
  - Possible cause: with `position_valid = 1`, ArduPilot accepts only `MAV_FRAME_BODY_FRD`, and PX4 only `MAV_FRAME_LOCAL_NED`.
  - What to do: a frame matching the stack; for ArduPilot the angles `angle_x/angle_y` and `distance` are simpler.
- **Symptom:** FOLLOW is engaged, but the vehicle stays where it is
  - Possible cause: the target is beyond `FOLL_DIST_MAX`; `FOLL_SYSID` does not match the sender; messages come less often than once every 3 s.
  - What to do: check the sysid and the stream rate; the default `FOLL_POS_P` of 0.1 gives a slow approach.

## checklist
- The exposure timestamp travels through the whole pipeline; the clocks are aligned with `TIMESYNC`
- p50/p95/max are measured by stage, and glass-to-command is summed up and compared with the task budget
- The detector and the tracker are scored by slices: lighting, blur, occlusion, "after a loss"
- Georeferencing: `ATTITUDE` interpolation, the AGL source named, the error from a time offset computed
- Interlocks in three layers: `v_max`, a 0.5 s watchdog, a 3 s timeout with a latch; `GUID_TIMEOUT`, the geofence; the pilot
- In SITL: a silent companion, a lost target, the geofence and the speed limit are tested

## references
- ArduPilot Dev — Copter Commands in Guided Mode (type_mask 3527, stop after 3 s) | https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html | primary | A
- ArduPilot source — GUIDED velocity control and timeout (`ArduCopter/mode_guided.cpp`, Copter-4.7.3) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.3/ArduCopter/mode_guided.cpp | primary | A
- ArduPilot source — AP_Follow: messages, FOLL_* parameters, 3 s timeout | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.3/libraries/AP_Follow/AP_Follow.cpp | primary | A
- ArduPilot source — LANDING_TARGET handling in the MAVLink backend (`AC_PrecLand_MAVLink.cpp`, `AC_PrecLand_Companion.cpp` before 4.7) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.3/libraries/AC_PrecLand/AC_PrecLand_MAVLink.cpp | primary | A
- ArduPilot source — fence avoidance for velocity commands (AVOID_ENABLE, FENCE_MARGIN) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.3/libraries/AC_Avoidance/AC_Avoid.cpp | primary | A
- ArduPilot Copter — Precision Landing and Loiter (PLND_*) | https://ardupilot.org/copter/docs/precision-landing-and-loiter.html | primary | A
- ArduPilot Copter — Follow Mode | https://ardupilot.org/copter/docs/follow-mode.html | primary | A
- MAVLink — Common message set (LANDING_TARGET, SET_POSITION_TARGET_LOCAL_NED, FOLLOW_TARGET, TIMESYNC) | https://mavlink.io/en/messages/common.html | primary | A
- MAVLink — Time Synchronization Protocol | https://mavlink.io/en/services/timesync.html | primary | A
- PX4 — Offboard Mode (2 Hz proof of life, COM_OF_LOSS_T, COM_OBL_RC_ACT; v1.18.0 docs source) | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/docs/en/flight_modes/offboard.md | primary | A
- PX4 — Precision Landing (LANDING_TARGET in MAV_FRAME_LOCAL_NED, PLD_*; v1.18.0 docs source) | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/docs/en/advanced_features/precland.md | primary | A
- PX4 source — `mavlink_receiver.cpp`, handle_message_landing_target (v1.18.0) | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/modules/mavlink/mavlink_receiver.cpp | primary | A
- Linux kernel — V4L2 buffer: timestamp, TIMESTAMP_MONOTONIC, TSTAMP_SRC_EOF/SOE | https://docs.kernel.org/userspace-api/media/v4l/buffer.html | primary | A
- OpenCV — Camera calibration With OpenCV | https://docs.opencv.org/4.x/d4/d94/tutorial_camera_calibration.html | primary | B
- Bewley et al. — Simple Online and Realtime Tracking (SORT), 2016 | https://arxiv.org/abs/1602.00763 | primary | B
- Zhang et al. — ByteTrack: Multi-Object Tracking by Associating Every Detection Box, 2021 | https://arxiv.org/abs/2110.06864 | primary | B
