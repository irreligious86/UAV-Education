---
id: per-geometry
title: "Camera geometry: from a pixel to a point on the ground"
level: L3
readingTime: 45 min
firmware: ArduPilot 4.7 (checked against 4.7.3) · PX4 · companion
status: published
added: 2026-11-08
tags:
  - camera
  - calibration
  - pinhole
  - coordinate frames
  - georeferencing
related:
  - per-camera
  - math-linalg-rot
  - per-landing
  - per-mapping
next:
  - per-landing
source: content/companion/per-geometry.md
source_hash: b45e3cfa9205
---

## summary
The detector has found an object in the frame, in pixels (u, v). The autopilot needs a point in meters: "12 m north and 3 m west of me". Between the two sit the pinhole camera model, the intrinsic parameters (focal length and principal point), lens distortion, the camera mount on the frame and the vehicle attitude. This module builds the whole chain: checkerboard calibration and what its results mean, pixel → ray → intersection with the ground, back-projection as a check, stereo and baseline, PnP for known objects, and where along the chain accuracy is lost. The lab uses the ready-made library `examples/perception/camgeo.py` with a synthetic "ground → pixel → ground" check: if your chain does not close on synthetic data, it will be even further off on real video.

## theory
### The pinhole camera
An ideal camera projects a point P = (X, Y, Z) in the camera frame onto the image plane by similar triangles: x = X/Z, y = Y/Z (normalized coordinates), and then into pixels: u = f_x·x + c_x, v = f_y·y + c_y. The intrinsic matrix (camera matrix):

```
K = [[f_x,  0,  c_x],
     [ 0,  f_y, c_y],
     [ 0,   0,   1 ]]
```

f_x, f_y are the focal lengths **in pixels** (not millimeters): f_x = f_mm · W_px / sensor_width_mm. The link to the field of view: f_x = (W/2)/tan(HFOV/2). A 1280 px camera with an HFOV of 90° has f_x = 640 px. (c_x, c_y) is the principal point, usually close to the image center but not exactly on it. The OpenCV camera frame: x to the right in the image, y down in the image, z forward along the optical axis. Remember it: it differs from both FRD and ENU.

The key consequence: a single pixel gives you only a **ray**, a direction, not a point. The distance along the ray is unknown. To get a point you need extra information: the height above flat ground, a second camera (stereo), the known size of the object, or a rangefinder.

{{diagram:pixel-ground-chain|The "pixel → ground" chain: K⁻¹ and undistortion give a ray in the camera frame, the mount rotates it into FRD, the attitude into NED, and the intersection with the ground plane gives meters.}}

### Distortion
A real lens bends straight lines, especially a wide-angle FPV lens. The standard model (Brown–Conrady) in normalized coordinates: radial x_d = x·(1 + k₁r² + k₂r⁴ + k₃r⁶), where r² = x² + y², plus tangential terms (p₁, p₂) that arise because the lens is not exactly parallel to the image plane. Barrel distortion has k₁ < 0, pincushion has k₁ > 0. For a fisheye lens (> 120°) this model does not work and you need a separate one (`cv2.fisheye`, the Kannala–Brandt model).

The direction matters: the model describes how an ideal point gets **distorted**. We need the inverse: remove the distortion from a measured pixel. There is no closed-form formula, so it is solved iteratively (`cv2.undistortPoints`, or a fixed-point iteration x ← x_d / (1 + k₁r² + …), 5–20 iterations). At the edge of a wide-angle frame, the "forgot about distortion" error is tens of pixels, which means meters on the ground.

### Calibration
A checkerboard with a known square size is shot 20–40 times at different angles and distances, covering the whole frame, especially the edges. `cv2.calibrateCamera` finds K, the distortion coefficients and the board pose in every frame by minimizing the reprojection error (RMS). What to look at in the result:
- **Reprojection RMS** < 0.5 px is good, 0.5–1 is acceptable, > 1 means bad frames (blur, too little tilt, a board that is not flat).
- **f_x ≈ f_y** for square pixels; a mismatch of > 1–2 % is suspicious.
- **c_x, c_y** within ~5 % of the center.
- A calibration is valid for one specific resolution and focus. Switch the camera mode from 1080p to 720p with a crop and K is different. Autofocus and electronic image stabilization break the calibration; on board you turn them off.

### Camera mount (extrinsics)
The ray in the camera frame has to be rotated into the body frame FRD. For a camera on the nose looking forward: camera z = body x, camera x (right in the image) = body y, camera y (down in the image) = body z. A camera pitched down by an angle τ adds a rotation about the body y axis by −τ. A camera looking straight down (nadir) has τ = 90°: the top of the image points forward along the heading. Add the camera offset from the center of gravity (`PLND_CAM_POS_X/Y/Z` in ArduPilot exist exactly for this); at 50 m a 10 cm offset is negligible, at 1 m just before touchdown it is noticeable.

The gimbal is a separate trap: if the camera is stabilized, its orientation is the gimbal's orientation, not the vehicle's. In that case the chain uses the gimbal angles from `GIMBAL_DEVICE_ATTITUDE_STATUS` (or `MOUNT_STATUS`), not `ATTITUDE`.

### Pixel → point on the ground
The full chain:
1. (u, v) → normalized coordinates: x_d = (u − c_x)/f_x, y_d = (v − c_y)/f_y.
2. Remove the distortion → (x, y); the ray in the camera frame r_c = (x, y, 1), normalized.
3. Into FRD: r_b = R_bc · r_c.
4. Into NED: r_n = R_nb(φ, θ, ψ) · r_b, where R_nb = Rz(ψ)·Ry(θ)·Rx(φ).
5. Intersect with the ground plane h meters below the camera: t = h / r_n,z; point = t · r_n. If r_n,z ≤ 0, the ray points at the horizon or above it and there is no point on the ground.
6. Convert to latitude/longitude: Δlat = N / R_Earth, Δlon = E / (R_Earth · cos lat), R ≈ 6 378 137 m.

Example: a nadir camera, f = 800 px, altitude 100 m, the object 80 px above the image center in level flight → 100·80/800 = 10 m ahead along the heading. With 10° of roll, the same point in the image center moves 100·tan 10° = 17.6 m sideways: **attitude matters more than it seems**, and a 1° attitude error at 100 m is 1.7 m on the ground.

### Error budget
The error of the ground point is the sum of:
- **Attitude:** δ_ground ≈ h · δθ / cos²(angle from nadir). 1° at 100 m straight down is 1.7 m; looking 60° away from nadir it is 7 m.
- **Altitude:** the point scales proportionally: a 5 % altitude error → a 5 % range error. Barometric altitude relative to the takeoff point ≠ height above terrain; on a slope this is the dominant error, fixed with a rangefinder or a DEM.
- **Synchronization:** the frame is taken at time t but ATT is sampled at t + 50 ms; at an angular rate of 100°/s that is 5°, or 9 m at 100 m. A frame timestamp and attitude interpolated to it are mandatory.
- **Calibration and pixel:** 1 px at f = 800 at 100 m is 12.5 cm; usually the smallest contribution.

The conclusion worth remembering: on drones, georeferencing accuracy is limited by timing and attitude, not by the camera.

### Stereo and known size
**Stereo:** two cameras separated by a baseline B. A point appears shifted by a disparity of d pixels; depth Z = f·B/d. The depth error grows as Z²: δZ = Z²·δd/(f·B). A camera with f = 400 px and B = 5 cm (a typical embedded module) at δd = 0.25 px gives ±0.3 m at 5 m and ±1.25 m at 10 m, which is why stereo cameras for obstacle avoidance are useful at ranges of a few meters.

**Known size:** an object H_m tall spans h_px pixels → Z ≈ f·H/h_px. This is how you estimate the range to a person, a car, a marker.

**PnP:** the 3D geometry of the object is known (the corners of an ArUco marker with a 20 cm side) and so are their pixels → `cv2.solvePnP` recovers the full camera pose relative to the object. This is the basis of precision landing (next module): the marker gives both position and heading.

### Camera and IMU in time
Everything above assumes the attitude is known exactly at the moment of exposure. A rolling shutter (most cheap sensors) reads out the rows one after another over 10–30 ms: under rotation the frame gets skewed, and different rows correspond to different attitudes. Georeferencing needs a global shutter or a low angular rate at the moment of capture, a hardware frame timestamp (the camera trigger in the log, `CAM`/`TRIG` in ArduPilot), and ATT interpolated to that timestamp.

{{diagram:chart-stereo-error|Stereo depth error grows with the square of the distance: with a 5 cm baseline it already exceeds a meter at 10 m. A wider baseline or a closer target are the only ways to improve it.}}

### Where it fits in the system

- **Takes in:** the target pixel (`per-cv`); the attitude at the moment of exposure, `ATTITUDE` or the gimbal angles (`payload-gimbal`); the height above ground (`est-alt-sources`); rotation matrices (`math-linalg-rot`).
- **Hands off:** a point on the ground in NED and in latitude/longitude to tracking and mapping (`per-tracking`, `per-mapping`); the angles and pose of the marker for `LANDING_TARGET` (`per-landing`).
- **If you get this wrong:** attitude taken 50 ms after the frame at 100°/s → 9 m of error at 100 m; it looks like a "bad detector" but the fix is a timestamp (`per-vision-pipeline`). Barometric altitude instead of height above terrain on a slope → the range scales with an error; you need a rangefinder or a terrain elevation map (`nav-terrain`).

## practice
### Step 1. Calibration
Print a 9×6 checkerboard (25 mm squares) and glue it to a rigid backing. Record a 60 s video with your onboard camera at the working resolution, slowly moving the board across the whole frame and tilting it up to 45°. Extract 30 sharp frames and run `cv2.findChessboardCorners` + `cornerSubPix` + `calibrateCamera`. Record K, the distortion coefficients, the RMS and σ(f_x) from `calibrateCameraExtended`. Compare f_x with the formula from the HFOV in the camera datasheet: a mismatch within ~5 % is normal because the datasheet angle is rounded (a course guideline).

### Step 2. Synthetic check of the chain
```python
import math, numpy as np
import camgeo as cg   # examples/perception

K = cg.K_matrix(800, 800, 640, 360)
R = cg.R_bc_for_mount(70)                          # camera pitched down 70°
roll, pitch, yaw, alt = math.radians(5), math.radians(-3), math.radians(30), 60.0

# a known ground point -> pixel -> back to ground: must close to millimetres
u, v = cg.ground_to_pixel(25.0, -8.0, K, roll, pitch, yaw, alt, R_bc=R, k1=-0.12, k2=0.02)
print(u, v, cg.pixel_to_ground(u, v, K, roll, pitch, yaw, alt, R_bc=R, k1=-0.12, k2=0.02))
```
Then introduce errors one at a time: roll +1°, altitude +5 %, distortion forgotten, a 50 ms time offset at an angular rate of 60°/s. For each, compute how far the ground point moves: that is your error budget. Put it in a table.

### Step 3. Real-world check
Place two conspicuous objects in a field at known coordinates (a phone GNSS receiver, or a tape measure from the takeoff point). Shoot them from 30–50 m while logging (ATT, GPS, altitude) and frame timestamps. Compute the coordinates of the objects from the frame and compare them with the measured ones. Expect an error of a few meters; if it is tens of meters, look for a coordinate-frame or timing mistake, not a calibration problem.

Self-check: the lab is done when you have a calibration with RMS < 1 px, σ(f_x) < 1 % and f_x within ~5 % of (W/2)/tan(HFOV/2) from the camera datasheet (RMS alone is not enough: with a poor set of views it is low while f_x drifts, see per-camera; a course guideline), the chain from step 2 closes (it returns the point 25.0, −8.0 to within millimeters), the error budget table from step 2 agrees in order of magnitude with the formulas from the theory (1° of roll: h·δθ/cos², about 1 m at 60 m near nadir and more away from it; altitude +5 %: 5 % of the point's range; 50 ms at 60°/s is 3° of attitude; the timing and attitude rows are larger than the calibration row), and on the real data from step 3 the error is a few meters (tens of meters: look for a coordinate-frame or timing mistake).

## diagnostics
- **Symptom:** ground points are mirrored relative to the heading
  - Possible cause: the camera and body frames are mixed up (image x ≠ body y) or the roll sign is wrong.
  - What to do: the test "object on the right of the image at yaw = 0 → positive E"; a synthetic round trip.
- **Symptom:** the error grows toward the edges of the frame
  - Possible cause: distortion not removed, or a calibration for a different resolution.
  - What to do: check the calibration resolution, apply undistortion to the points.
- **Symptom:** during maneuvers the point wanders by meters, in a hover it is stable
  - Possible cause: the frame and the attitude are out of sync.
  - What to do: a hardware timestamp, ATT interpolation, a global shutter or a lower angular rate.
- **Symptom:** a systematic range error on a slope
  - Possible cause: altitude relative to the takeoff point instead of height above terrain.
  - What to do: a rangefinder or a DEM; intersect the ray with the terrain instead of a plane.
- **Symptom:** calibration RMS > 1 px
  - Possible cause: blurry frames, too few tilted views, a board that is not flat, stabilization or autofocus enabled.
  - What to do: reshoot with a shorter exposure, a rigid board, EIS/AF turned off.

## references
- OpenCV — Camera Calibration tutorial | https://docs.opencv.org/4.x/dc/dbb/tutorial_py_calibration.html | primary | A
- OpenCV — Camera calibration and 3D reconstruction (calib3d) | https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html | primary | A
- R. Szeliski — Computer Vision: Algorithms and Applications (2nd ed., free) | https://szeliski.org/Book/ | secondary | A
- ArduPilot — Precision landing parameters (PLND_CAM_POS_*) | https://ardupilot.org/copter/docs/parameters.html#plnd-parameters | primary | A
- MAVLink — GIMBAL_DEVICE_ATTITUDE_STATUS | https://mavlink.io/en/messages/common.html#GIMBAL_DEVICE_ATTITUDE_STATUS | primary | A

## checklist
- I understand why a pixel gives a ray and not a point
- I can read K: focal length in pixels, principal point, link to HFOV
- I remove distortion in the right direction and know where it matters
- I calibrate a camera and judge the quality by RMS and how plausible K is
- I build the camera → FRD → NED → ground chain and check it with a synthetic round trip
- I know the error budget: attitude, altitude, timing, pixel
- I know when to use stereo, a known size or PnP
