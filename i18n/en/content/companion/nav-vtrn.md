---
id: nav-vtrn
title: "Visual terrain navigation: frame against map, visual odometry and a return without GNSS"
level: L3
readingTime: 55 min
firmware: ArduPilot 4.7 (checked against 4.7.3; lab recorded on 4.6.3) · PX4 1.18 (parameters checked against v1.18.0)
status: published
added: 2026-11-14
tags:
  - visual navigation
  - map matching
  - visual odometry
  - GPS_INPUT
  - homography
  - EKF3
related:
  - per-geometry
  - per-visual-nav
  - per-cv
  - est-gnss
  - nav-resilience
next:
  - per-mapping
source: content/companion/nav-vtrn.md
source_hash: 8412fa43e4e3
---

## summary
GNSS is gone, and you still need to get home. A downward-looking camera gives two different measurements: **visual odometry** (VO), the shift between consecutive frames, which accumulates error, and **map matching**, a comparison of the frame with a georeferenced orthophoto, which gives absolute latitude and longitude, but not every time. The module builds the whole pipeline: rectifying the frame by altitude and heading, ORB/AKAZE features (and the learned SuperPoint/LightGlue), a homography with RANSAC, coordinates and their σ, coarse localization by a global descriptor (VPR), fusion with VO, and the input into the autopilot through `GPS_INPUT` (ArduPilot) or `VISION_POSITION_ESTIMATE`/`EKF2_EV_CTRL` (PX4). The lab: a Python test bench on a **synthetic** map with known ground truth, then a closed loop in ArduCopter 4.6.3 SITL: a 1.3 km route, of which 900 m and the landing happen after GNSS is switched off.

## theory
### Why odometry drifts and the map does not
VO adds up increments, so it also adds up their errors. Three sources:
- **scale**: meters = pixels · h / f (per-geometry); if the altitude is overestimated by e %, the path is overestimated by e %, an error Δ = D · e/100;
- **heading**: the shift is computed in the frame axes and rotated into NED; a heading error δψ gives a sideways drift of D · sin δψ, so 1° is 1.7 % of the path;
- **matching noise**: a random walk that grows as √N frames.

VIO (per-visual-nav) takes the scale from the accelerometer, but drift still accumulates with distance. Map matching works the other way around: each fix is independent, and its error does not depend on the distance flown (fractions of a meter at a GSD of 0.2–0.25 m), but a fix does not always come, and sometimes it lies. The conclusion is the same as for an inertial system and GNSS (est-gnss): **VO carries you between fixes, and the fixes reset the drift**.

| Source | What it gives | Error | When it fails |
|---|---|---|---|
| VO (mono + AGL) | a position increment in the frame axes | grows with distance: e % of scale + sin δψ | water, snow, motion blur |
| VIO | the same + scale from the IMU | grows with distance, more slowly | the same; a poor camera–IMU calibration |
| Map matching | absolute lat/lon, heading | bounded: GSD + the map's georeferencing | season, uniform terrain, an outdated map |
| VPR | "which tile am I on": hundreds of meters | coarse, no σ | similar fields; needs a geometric check |

### The frame-matching pipeline
{{diagram:vtrn-pipeline|The frame is rectified by AGL and heading, matched against a map window around the prediction, the homography goes through checks and only then updates the filter; the autopilot gets a smoothed 5 Hz estimate, not the raw fixes.}}

1. **Camera pointing down**, a global shutter or a short exposure; undistortion from the calibration (per-geometry). Tilt is compensated by a gimbal or by rotating the frame using `ATTITUDE`.
2. **Rectification**: a scale s = (h_AGL / f) / GSD_map and a rotation by the heading, so the frame becomes "north up, pixels like the map's". The features then only have to find a shift, not a scale and a rotation.
3. **Features.** ORB is FAST + rotated BRIEF, 32 bytes, Hamming distance; AKAZE is more robust to blur but slower and gives fewer points. The learned SuperPoint (a detector-descriptor) and LightGlue (a matcher): according to their papers, SuperPoint is more accurate than ORB at homography estimation on HPatches (illumination and viewpoint changes), and LightGlue is a fast learned matcher; check robustness to seasonal change on your own frames. The price is a GPU on board (per-edge-ml).
4. **Matching** only against map features within a 3σ window around the predicted position; Lowe's ratio test at 0.8.
5. **Homography + RANSAC** (`cv2.findHomography`, a 3 px threshold): 4 pairs per hypothesis, the number of iterations N = ln(1 − p) / ln(1 − w⁴), p = 0.99; with an inlier ratio w = 0.5 that is 72, with 0.2 it is 2900. Checks: inliers ≥ 15, homography scale 0.8–1.25 (otherwise the altitude is wrong or the match is false).
6. **Coordinates**: frame center → map pixel → meters → Δlat = N/R, Δlon = E/(R·cos lat). The homography's residual rotation is an absolute heading correction.
7. **Covariance**: σ ≈ 3 · RMS_inliers · GSD / √n + a fraction of the search window, with a floor of 0.5 m. This is a lower bound: a match against a repeating pattern gives a small RMS and a wrong point, which is why innovation gates sit on top of it.

A homography assumes flat ground: a height difference Δh within the frame shifts points by a fraction Δh/h of the footprint, so over buildings and slopes you fly higher or use an elevation map.

### Coarse localization: VPR
If there is no prediction (a cold start, a minute over water), the search window is the whole map. Visual place recognition compresses each map tile into a single vector (NetVLAD, AnyLoc on DINOv2; a home-made miniature in the lab), the frame looks up the k nearest tiles, and geometry makes the decision: a homography around each candidate. VPR itself gives no coordinate and does not know when it is wrong.

### What breaks map matching
| Factor | Mechanism | What to do |
|---|---|---|
| Season, lighting, shadows | the tone of the fields changes, descriptors stop matching, w drops | a map from the same season; learned features; roads and buildings as anchors |
| Uniform terrain | water, snow, a flat field: no features, and VO goes blind too | a route along landmarks; an honest σ; a time limit without fixes |
| Low altitude | the footprint of 0.96·h is small, and the camera pixel is finer than the map pixel | matching only above a threshold; below it, optical flow and a rangefinder (nav-indoor) |
| High altitude | the GSD is coarser than the map's, haze | a longer focal length; a map with resolution to spare |
| Repeating patterns | crop rows, city blocks: false matches with a small RMS | a window from the prediction, gates, a scale check |
| Compute | on the x86 test bench: VO 13 ms, matching 22–107 ms, the whole map 248 ms | matching in a separate thread, latency accounted for |

### How a fix gets into the autopilot
**ArduPilot, path 1: `GPS_INPUT` (#232).** The companion pretends to be a receiver: `GPS2_TYPE = 14` (MAVLink), `gps_id = 1`. Fields: `lat/lon` (degE7), `fix_type` 3, `hdop`, `satellites_visible`, `vn/ve`, `horiz_accuracy`, `speed_accuracy`; whatever you do not need is disabled in `ignore_flags`. From the 4.6.3 source:
- `horiz_accuracy` becomes the EKF3 measurement noise, bounded below by `EK3_POSNE_M_NSE` (0.5 m) and above by 100 m, so an honest σ really changes the weight of the fix;
- the receiver is "healthy" when the average interval is < 215 ms: **you have to send at ≥ 5 Hz**, otherwise `PreArm: GPS 2: not healthy`;
- arming requires a 3D fix from every configured receiver and a disagreement between them of < 50 m;
- `GPS_AUTO_SWITCH = 1` (UseBest) picks the receiver with the best status, and on a tie the one with more satellites; for "vision" we report 8, so that a live GNSS (10–20) stays primary;
- `EK3_GPS_CHECK` before use: HDOP ≤ 2.5, satellites ≥ 6, hAcc ≤ 5 m, sAcc ≤ 1 m/s;
- a jump beyond the `EK3_POS_I_GATE` gate is rejected, and `EK3_GLITCH_RAD` (25 m) is the radius beyond which the filter resets to the GPS.

**Path 2: ExternalNav.** `VISION_POSITION_ESTIMATE` (#102: x, y, z in a local frame, `covariance[21]`, `reset_counter`) or `ODOMETRY`, `VISO_TYPE = 1`, `EK3_SRC2_POSXY = 6`; switching source sets with an `RCx_OPTION = 90` switch or `MAV_CMD_SET_EKF_SOURCE_SET` (per-visual-nav, nav-resilience). You need an origin and your own lat/lon → local meters conversion. `GPS_INPUT` is simpler for absolute fixes: global coordinates and automatic UseBest; ExternalNav separates the sources more honestly and does not disguise vision as GNSS in the logs.

**PX4.** The PX4 1.18 MAVLink receiver does not handle `GPS_INPUT` (nor did 1.15–1.17). External vision is `VISION_POSITION_ESTIMATE`/`ODOMETRY` in local NED, `EKF2_EV_CTRL` (bits: 0 horizontal position, 1 vertical position, 2 velocity, 3 yaw; default 0, it was 15 in 1.15), the noise from the message or `EKF2_EVP_NOISE` (`EKF2_EV_NOISE_MD`), the gate `EKF2_EVP_GATE` 5σ, `EKF2_EV_DELAY`. For absolute lat/lon there is a separate input: the `aux_global_position` topic (uXRCE-DDS `/fmu/in/aux_global_position`), in 1.18 up to four sources with the parameter sets `EKF2_AGP0…3_*`: `EKF2_AGP0_CTRL` bit 0 (default 0, the input is off; bit 1 is reserved), `EKF2_AGP0_ID`, which message `id` to accept (default 0; when migrating from 1.17 with the input enabled it is set to 1, the id that `GlobalPositionMeasurementInterface` sends), `EKF2_AGP0_NOISE` 1.0 m, `EKF2_AGP0_GATE` 3σ (`params_aux_global_position.yaml`, v1.18.0). Before 1.18 there was a single set: `EKF2_AGP_CTRL` (default 1 in 1.15), `EKF2_AGP_NOISE` 0.9 m, `EKF2_AGP_GATE` 3σ.

### Where it fits

- **Takes in:** height above ground and heading to rectify the frame (`est-alt-sources`); the calibration and the "pixel → meters" chain (`per-geometry`); a georeferenced orthophoto (`per-mapping`).
- **Hands off:** `GPS_INPUT` with an honest `horiz_accuracy` at no less than 5 Hz, or `VISION_POSITION_ESTIMATE`, into EKF3 (`ap-ekf`, `per-visual-nav`); a backup position source when GNSS is lost (`nav-resilience`).
- **If you get this wrong:** the altitude overestimated by e % → the VO path is overestimated by e %, the homography scale leaves 0.8–1.25, the fixes are rejected and drift accumulates; the filter's behavior is covered in `ap-ekf`. A false match on a repeating pattern with a small σ → the EKF gets a confident wrong point and the position jumps; gates and resets are covered in `ap-ekf`.

## practice
The sandbox has no satellite tiles and no frames of our own, so the map is **synthetic**: `vtrn_lab.py` draws a 4096×4096 px "orthophoto" at 0.25 m/px (1024×1024 m): fields with different textures, crop rows, roads, 900 tree clumps, 80 buildings and a 220 m lake with no texture; the georeferencing is nominal (corner at 55.7000° N, 37.5000° E). The camera sees the same terrain "on a different day": the tone of each field is changed by ±35 %, there is blur, 150 new tree clumps, and every frame gets random brightness, contrast and noise. VO, matching, RANSAC and the filter are real OpenCV 5.0 code, and the ground truth is known exactly. The synthetic data has no tilt, parallax, shadows or motion blur, so on real frames the numbers will be worse.

### Step 1. Camera, route, run
640×480, f = 500 px, AGL 100 m → GSD 0.2 m/px, a footprint of 128×96 m. 10 m/s, 2 Hz (95 % overlap), 460 frames, a closed route of 2295 m, the last leg across the lake. The altitude is "measured" with a +1.3 % error, and the heading is as from an AHRS: 0.5° noise and a slow drift.

```text
$ python3 vtrn_lab.py
synthetic map 4096x4096 px @ 0.25 m/px = 1024 m side, built in 13.9 s (SYNTHETIC DATA)
camera 640x480, f=500 px, AGL 100 m -> GSD 0.200 m/px, footprint 128x96 m; AGL estimate used: 101.33 m
map feature database (ORB): 51411 features, 1.6 MB, built in 0.3 s
VO: 459 steps, inliers median 151, 12.9 ms/step on this machine; failures 34
```

### Step 2. Odometry and its drift
Frame to frame: ORB (1500 points), ratio 0.8, a similarity transform with RANSAC; the shift of the frame center in pixels is multiplied by AGL/f and rotated by the heading:

```python
A, inl = cv2.estimateAffinePartial2D(p1, p2, method=cv2.RANSAC, ransacReprojThreshold=2.0)
c = np.array([W / 2, H / 2, 1.0])
tx, ty = -(A @ c - c[:2])              # scene shift at the frame center, px
gsd = agl_est / FX                     # m/px
forward, right = -ty * gsd, tx * gsd   # frame "up" is the flight direction
```

Three runs, pure VO error in meters:

| Run | 100 m | 500 m | 1000 m | 1500 m | 2295 m |
|---|---|---|---|---|---|
| AGL +1.3 %, AHRS heading | 1.0 | 4.1 | 4.8 | 4.8 | 5.9 |
| AGL +5 % (`--agl-bias 5`) | 4.6 | 17.8 | 20.8 | 10.9 | 27.9 |
| heading from frame rotation (`--yaw-from vo`) | 1.1 | 4.3 | 6.8 | 139.0 | 292.7 |

Write down: at +5 % the error on a straight line is exactly 4.6 % of the path; on a closed route the scale error partly cancels (10.9 m at 1500 m), which is a property of the closed route, not a merit of VO. The integrated heading holds for 1 km, then a single failure in a turn costs 293 m. Of the 34 VO failures, 26 are over the lake.

### Step 3. Map matching
Every 5 s the frame is rectified and searched for in a ±150 m window around the prediction:

```python
s = (agl_est / FX) / GSD_MAP                                  # camera px -> map px
Wr, Hr = int(W * s * 1.5), int(H * s * 1.5)                   # canvas with room for the rotation
M = cv2.getRotationMatrix2D((W / 2, H / 2), -(math.degrees(psi_pred) + 90), s)
M[0, 2] += Wr / 2 - W / 2; M[1, 2] += Hr / 2 - H / 2          # frame center -> canvas center
rect = cv2.warpAffine(frame, M, (Wr, Hr))                     # north up, map scale
Hm, inl = cv2.findHomography(pf, pw, cv2.RANSAC, 3.0)         # pf: frame, pw: map window
c = cv2.perspectiveTransform(np.float32([[[Wr / 2, Hr / 2]]]), Hm)[0, 0]
sc = math.sqrt(abs(Hm[0, 0] * Hm[1, 1] - Hm[0, 1] * Hm[1, 0]))   # accept if 0.8 < sc < 1.25
sigma = max(0.5, 3.0 * rms * GSD_MAP / math.sqrt(n_inl) + 0.004 * search_m)
rot = math.atan2(Hm[1, 0] - Hm[0, 1], Hm[0, 0] + Hm[1, 1])    # residual rotation = heading error
```

```text
map fixes attempted 45, succeeded 39; err median 0.10 m, p90 0.52 m, max 3.49 m; sigma reported median 0.70 m; inliers median 94; 69 ms per fix
map fix failures at frames [40, 150, 220, 240, 420, 430] (positions: [(465, 400), (420, 833), (102, 769), (101, 669), (665, 300), (715, 300)])
first fix: frame 10 -> x=315.0 y=400.0 m -> lat 55.696406 lon 37.505021, sigma 0.73 m, inliers 61/85
```

Two failures are over the lake; the other four are on land, where the window did not collect 15 inliers. The fix with a 3.49 m error is on the far shore of the lake, with a reported σ = 0.72 m, that is 4.8σ: the formula is optimistic when the inliers are bunched at the edge of the frame. AKAZE (`--detector akaze`) on the same frames: 24 fixes out of 45, but with a maximum error of 0.28 m: rarer, but cleaner.

### Step 4. Fusion and search without a prediction
A two-state filter: VO is the prediction (its noise grows as 3 % of the path since the last fix), a fix is the measurement with R = σ², a 3σ gate, and after three consecutive rejections a reset to the fix.

{{diagram:chart-vtrn-error-distance|Pure VO drifts by 6–293 m depending on the altitude and heading errors; the fix error does not grow with distance, and the fusion holds a 0.45 m median and goes out of tolerance only over the lake, where there is neither VO nor fixes.}}

```text
fused error: median 0.45 m, p90 1.34 m, max 7.43 m, final 0.82 m
VPR: 900 reference patches 96 m every 32 m, 320 floats each (1.2 MB); hand-made descriptor top-1 40 %, top-5 66 % of 92 queries (hit = within 64 m)
VPR top-5 + geometric verification: correct 63, wrong 2, no answer 27; 105 ms per query
brute force over the whole map (51411 features): correct 74, wrong 0, no answer 18; 248 ms per query
```

The 7.43 m maximum is dead reckoning over the lake, 12 s without VO or fixes. The home-made descriptor is weak (top-1 40 %); in real life you use a trained one, but even then geometry gives the answer. Over 1 km² a brute-force search is still feasible; over 100 km² the database holds 5 million features, and you cannot do without VPR.

### Step 5. SITL: the vision node as a second GPS
`sitl_vtrn.py` closes the loop on ArduCopter 4.6.3: from the simulator's true pose (`SIMSTATE`) it cuts a frame out of the same map (the camera is on a gimbal, so roll and pitch are not rendered), runs VO at 5 Hz, map matching every 2 s in a separate thread, and sends `GPS_INPUT` with `gps_id = 1`. The heading for VO is `ATTITUDE.yaw` plus the correction from the homography; AGL is the relative altitude with a +1.3 % error.

```text
$ arducopter -S --model + --speedup 1 -I 3 -w --defaults copter.parm --home 55.693712,37.504782,150,0
$ python3 sitl_vtrn.py tcp:127.0.0.1:5790
  set GPS2_TYPE = 14
  set GPS_AUTO_SWITCH = 1
  set GPS2_DELAY_MS = 100
  set EK3_SRC2_POSXY = 0
  set EK3_SRC2_VELXY = 5
  STATUSTEXT so far: ['GPS 2: specified as MAV', 'GPS 2: detected MAV', 'GPS 1: probing for u-blox at 230400 baud', 'GPS 1: detected u-blox', 'EKF3 IMU0 origin set', 'EKF3 IMU1 origin set']
    [   44 s] STATUSTEXT: Arming motors
  arm result 0 armed: True
    [   65 s] vision: AGL 40 m >= 40 m: TRACKING, start from the take-off point, sigma 15 m
```

On the ground the node sends the known takeoff point with `horiz_accuracy` 5 m, otherwise there is no arming. The first version sent raw fixes at 2 Hz and got `PreArm: GPS 2: not healthy`, arm result 4 (FAILED).

### Step 6. GNSS loss, a false fix, the return
The route: takeoff to 100 m, 400 m north on GNSS (vision in shadow mode), `SIM_GPS1_ENABLE = 0` (in the 4.6.3 run, `SIM_GPS_DISABLE = 1`), 250 m east and 400 m south on vision, then RTL.

The output was recorded on Copter-4.6.3; in 4.7.x `SIM_GPS_DISABLE = 1` is called `SIM_GPS1_ENABLE = 0`: `sitl_vtrn.py` checks which of the two the firmware has and stops with an error if the vehicle does not accept it.

```text
  A: reached in 43 s; EKF-vs-truth error mean 0.23 m, max 0.30 m; GPS2(vision)-vs-truth mean 2.19 m, max 3.38 m
  map fixes so far: 34 attempted, 32 matched, 32 accepted; error median 0.09 m, max 0.51 m; match time median 22 ms
== step 5: GNSS loss (SIM_GPS_DISABLE = 1), leg B: 250 m east on vision only
  B: reached in 29 s; EKF-vs-truth error mean 0.67 m, max 1.52 m; GPS2(vision)-vs-truth mean 2.18 m, max 3.20 m
  >>> fault on: vision output shifted 60 m east
    [  181 s] STATUSTEXT: GPS Glitch or Compass error
  >>> fault off
    [  195 s] STATUSTEXT: Glitch cleared
  C: reached in 43 s; EKF-vs-truth error mean 0.70 m, max 1.99 m; GPS2(vision)-vs-truth mean 7.62 m, max 61.12 m
  alt 44.4 m: MAV_CMD_SET_EKF_SOURCE_SET 2 (optical flow) -> result 0; 0.9 m from home, EKF err 0.8 m
    [  288 s] vision: AGL 40 m < 40 m: frame footprint too small, reporting NO FIX
  RTL on vision down to 45 m: EKF-vs-truth error mean 0.67 m, max 1.54 m
  disarmed after 120 s; touchdown 4.1 m from the take-off point (truth)
== summary: GPS_INPUT sent 1591; map fixes attempted 111, matched 104, accepted 104; fix error median 0.09 m, p90 0.22 m, max 0.61 m; match time median 29 ms, max 107 ms; VO failures 37 of 1096 frames while TRACKING
   vision estimate vs truth at frame time (TRACKING): median 0.44 m, p90 0.77 m, max 2.14 m; heading correction learned from the map +2.0 deg
```

What to write down. (1) The `GPS2(vision)-vs-truth` column of 2.2 m is the age of the measurement: `GPS2_RAW` describes the middle of the VO step, 0.2–0.3 s ago at 10 m/s; the error of the estimate itself at frame time is 0.44 m. (2) After the GNSS loss the EKF stays within 2 m of the truth. (3) The EKF did not accept the false +60 m for 4 s: the `EKF_GPS_GLITCHING` flag (0x8000) was set, the error grew from 0.4 to 1.8 m on inertial navigation and came back after `Glitch cleared`. (4) RTL brought the vehicle back to the takeoff point with an error of about 1 m at 100 m altitude; the last 45 m used the `EK3_SRC2` set (optical flow + rangefinder), with touchdown at 4.1 m. The dataflash log shows the same (`python3 dfsum.py sitl3/logs/00000001.BIN`, in `examples/nav-vtrn/`):

```text
on GPS2 (vision) from t = 127.7 s: 1498 XKF4 samples, SP max 8.13, SP median 0.04, SV max 0.95; samples with SP > 1: 42; |IPE| max 60.2 m
```

`GPS.U` switches from the first receiver to the second at 127.7 s; `XKF4.SP` (the ratio of the position innovation to the gate) is 0.04 in normal operation and above 1 only on the 42 samples of the false fix, where `XKF3.IPE` = 60 m.

### Step 7. Four ways to break it: real runs
- **Heading straight from `ATTITUDE`** (an early version on the route across the lake; now this is the `--no-map-yaw` flag): after the GNSS loss and a turn, the EKF heading drifted by 5°, the node's estimate slid sideways off the path by 2.4 m, and over the lake by 16 m; `EKF variance`, LAND.
- **Dead reckoning with no expiry** (the `--lake` route, an early version of the node): over the water the node kept sending `fix_type = 3` from the last velocity. The EKF followed it, `h_acc` grew to 35 m, and in 150 s the vehicle flew 1547 m away.
- **The same with a 2 s limit**: `no VO for 10 frames (2 s): BLIND, reporting NO FIX`, and 10 s later `EKF Failsafe: changed to LAND Mode`. An honest failure: a copter will not cross 220 m of water blind, so such stretches are removed from the route, or the altitude is raised so the footprint catches the shore.
- **Landing without a backup source** (a version without the `EK3_SRC2` set): below 40 m, VO on the stretched synthetic texture produces garbage: 49.9 m off the point at 21 m altitude, touchdown at 203.8 m.

### Moving to real hardware
1. **The map.** An orthophoto of an area of about 1×1 km: your own survey flight and photogrammetry (per-mapping), downsampled to 0.2–0.3 m/px, or a satellite tile. Check the georeferencing on 3–5 control points with GNSS/RTK coordinates: error ≤ 1 m. The feature database is built offline; record the survey date and season.
2. **Bench, props off.** A quadcopter with the camera pointing straight down (a global shutter or an exposure ≤ 1/1000 s), a calibration with a reprojection error ≤ 0.5 px (per-geometry), AGL from a rangefinder (`RNGFND1_ORIENT = 25`), not the barometer over the takeoff point; the frame timestamps converted to the autopilot's clock (`TIMESYNC`). The node on the desk sends `GPS_INPUT` at 5 Hz with the parking position; `GPS2_TYPE = 14`, the GCS shows a 3D Fix for GPS2, `PreArm` is clean.
3. **Recording, vision not in the loop** (`GPS2_TYPE = 0`, the node only records): Loiter and a manual flight at 60–120 m, 5–10 min, including a stretch without landmarks. Save the frames with timestamps, `ATTITUDE`, the rangefinder, `GPS_RAW_INT`.
4. **An offline replay** of the recording with the same code. Acceptance: median fix error against GNSS ≤ 3 m, p95 ≤ 10 m; no accepted fix with an error > 5σ; after more than 2 s without VO the node reports `fix_type = 1`; the longest stretch without fixes ≤ 30 s; the heading correction from the map within ±5° of the compass.
5. **Shadow mode in flight**: `GPS2_TYPE = 14`, GNSS primary (vision reports 8 "satellites"). Acceptance from the log: `GPS[1]` within 5 m of `GPS[0]` 95 % of the time, message interval 200 ± 45 ms.
6. **Live mode**, only after items 4 and 5, props on: altitude ≥ 60 m over a field with no people, a geofence, `FS_EKF_ACTION = 1`, the pilot ready to switch to AltHold. Do not jam the GNSS: `GPS_AUTO_SWITCH = 0` and `GPS_PRIMARY = 1` move the EKF onto vision, while the real receiver stays in the log as the reference. Abort on `EKF variance`, a `GPS Glitch` lasting more than 10 s, or a disagreement with GNSS of > 10 m.

Self-check: the lab is done when (SITL path): you have your own VO error table for the three runs that agrees with the step 2 table (at the end of the route, on the order of 6, 28 and 293 m), and an "error vs distance" plot with the causes of drift named (the AGL error: scale; the integrated heading: a failure in a turn; the lake: VO failures); the median fix error is ≤ 0.5 m, and a fix with an error > 3σ has been found; arming with `GPS2_TYPE = 14` succeeded, and after `SIM_GPS_DISABLE = 1` (4.6.3; `SIM_GPS1_ENABLE = 0` from 4.7) the route and RTL were completed with an EKF error against the truth of ≤ 3 m at working altitude; the false +60 m fix was rejected (`GPS Glitch`, `XKF4.SP` > 1 in the log), and at least one failure from step 7 has been reproduced. (Hardware): the offline replay of the recording meets the criteria of item 4, and shadow mode meets those of item 5; live mode is optional.

## diagnostics
- **Symptom:** `PreArm: GPS 2: not healthy`, arming refused, although `GPS2_RAW.fix_type = 3`
  - Possible cause: `GPS_INPUT` arrives less often than 5 Hz (for example, one raw fix every 0.5–5 s); the average interval is ≥ 215 ms.
  - What to do: send the filter's smoothed estimate at 5 Hz; on the ground, the known takeoff point with `fix_type = 3` (otherwise `GPS 2: Bad fix`).
- **Symptom:** on vision the vehicle slides sideways on straight legs, the node's gates reject fix after fix, then `EKF variance` and LAND
  - Possible cause: the EKF heading has drifted by degrees, and VO rotates the frame shift by it; such an error is not observable through velocity.
  - What the log shows: the difference `XKF1.Yaw − SIM.Yaw` is 5° (on hardware, compare against the heading from the fixes), and `GPS[1]` lags further and further across the path.
  - What to do: a heading correction from the homography's residual rotation on every fix that passes the checks, even if the position gate rejected it.
- **Symptom:** `GPS Glitch or Compass error` exactly at the entry to a textureless stretch
  - Possible cause: the node raised `speed_accuracy` above 1.5 m/s, and EKF3 treats such a receiver as unfit for flight (it recovers at < 1.0).
  - What to do: while the estimate is usable, sAcc ≤ 1.0; when it is not, an honest `fix_type = 1`, not "bad, but 3D".
- **Symptom:** the vehicle flies hundreds of meters away, with `GPS2 fix = 3`, `h_acc` of 40–120 m, and the EKF reporting no errors
  - Possible cause: the node went blind and sends dead reckoning at a constant velocity; the EKF follows the fiction, and the velocity gates have locked onto the stale value and do not let the revived VO through.
  - Consequences: in SITL, 1.5 km off the route in 150 s.
  - What to do: 2 s without VO → `fix_type = 1` and relocalization over the whole map; the gates open after 3 consecutive rejections; a geofence and `FS_EKF_ACTION = 1`.
- **Symptom:** on a straight line VO shows a constant percentage error from the first meter
  - Possible cause: a wrong AGL (the barometer over the takeoff point instead of the height above terrain), a wrong f after a resolution change.
  - What to do: a rangefinder; check the scale of the fix homography, which should be 1.00 ± 0.03.
- **Symptom:** a fix with σ of 0.5–0.7 m is off by 3–5 m
  - Possible cause: the inliers are bunched in a corner of the frame at the edge of a uniform area (a shoreline, a field boundary); the RMS is small and the geometry weak.
  - What to do: 3σ innovation gates, an inlier threshold, a requirement for inliers to be spread across the frame; do not raise a fix's weight beyond σ = 0.5 m.
- **Symptom:** when descending below 40–45 m the estimate "floats" and the vehicle drifts off the point
  - Possible cause: the frame footprint is smaller than the map feature window; on the test bench, a synthetic texture magnified 4–6 times.
  - Consequences: in SITL without a backup source, 50 m off at 20 m altitude and 204 m by touchdown.
  - What to do: below working altitude, the `EK3_SRC2` set with optical flow and a rangefinder, or a manual landing.

## checklist
- Causes of VO drift: scale (AGL), heading, noise; the budget between fixes
- Rectify → features → 3σ window → homography + RANSAC → checks → lat/lon, σ, heading
- VPR gives candidates, geometry gives the answer
- The autopilot gets a 5 Hz estimate with an honest `horiz_accuracy`; a blind node sends `fix_type = 1`
- Arming: a 3D fix from GPS2 on the ground, disagreement < 50 m
- The heading for VO is corrected from the map; the velocity and position of one measurement refer to the same instant
- Below working altitude, another source (`EK3_SRC2`: optical flow + rangefinder)
- Before a live flight: an offline replay of a recording and shadow mode

## references
- MAVLink common message set — GPS_INPUT (#232), VISION_POSITION_ESTIMATE (#102), GPS_INPUT_IGNORE_FLAGS | https://mavlink.io/en/messages/common.html | primary | A
- ArduPilot source — MAVLink GPS driver, GPS_INPUT handling (`libraries/AP_GPS/AP_GPS_MAV.cpp`) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.3/libraries/AP_GPS/AP_GPS_MAV.cpp | primary | A
- ArduPilot source — receiver health, UseBest, all_consistent (`libraries/AP_GPS/AP_GPS.cpp`) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.3/libraries/AP_GPS/AP_GPS.cpp | primary | A
- ArduPilot source — GPS pre-arm checks (`libraries/AP_Arming/AP_Arming.cpp`) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.3/libraries/AP_Arming/AP_Arming.cpp | primary | A
- ArduPilot source — GPS measurement noise and gates in EKF3 (`libraries/AP_NavEKF3/AP_NavEKF3_PosVelFusion.cpp`) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.3/libraries/AP_NavEKF3/AP_NavEKF3_PosVelFusion.cpp | primary | A
- ArduPilot Copter — EKF Source Selection and Switching (EK3_SRCn_*, RCx_OPTION 90, MAV_CMD_SET_EKF_SOURCE_SET) | https://ardupilot.org/copter/docs/common-ekf-sources.html | primary | A
- ArduPilot Copter — Non-GPS Navigation | https://ardupilot.org/copter/docs/common-non-gps-navigation-landing-page.html | primary | A
- PX4 source — EKF2_EV_*, EKF2_AGP_* parameters (`src/modules/ekf2/params_external_vision.yaml`, `params_aux_global_position.yaml`, v1.18.0) | https://github.com/PX4/PX4-Autopilot/tree/v1.18.0/src/modules/ekf2 | primary | A
- PX4 source — MAVLink receiver: VISION_POSITION_ESTIMATE, ODOMETRY (`src/modules/mavlink/mavlink_receiver.cpp`, v1.18.0) | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/modules/mavlink/mavlink_receiver.cpp | primary | A
- PX4 User Guide — Using PX4's Navigation Filter (EKF2): External Vision System (v1.18.0 docs source) | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/docs/en/advanced_config/tuning_the_ecl_ekf.md | primary | A
- OpenCV — Camera Calibration and 3D Reconstruction: findHomography, RANSAC | https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html | primary | A
- OpenCV — ORB (Oriented FAST and Rotated BRIEF) | https://docs.opencv.org/4.x/d1/d89/tutorial_py_orb.html | primary | A
- DeTone, Malisiewicz, Rabinovich — SuperPoint: Self-Supervised Interest Point Detection and Description (2018) | https://arxiv.org/abs/1712.07629 | primary | B
- Lindenberger, Sarlin, Pollefeys — LightGlue: Local Feature Matching at Light Speed (2023) | https://arxiv.org/abs/2306.13643 | primary | B
- Arandjelović et al. — NetVLAD: CNN architecture for weakly supervised place recognition (2016) | https://arxiv.org/abs/1511.07247 | primary | B
- Keetha et al. — AnyLoc: Towards Universal Visual Place Recognition (2023) | https://arxiv.org/abs/2308.00688 | primary | B
