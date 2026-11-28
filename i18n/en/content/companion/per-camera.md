---
id: per-camera
title: "Cameras and video streams on a companion computer"
level: L3
readingTime: 60 min
firmware: ArduPilot · PX4 · OpenCV 5.0
status: published
added: 2026-11-08
tags:
  - camera
  - GStreamer
  - RTSP
  - OpenCV
  - latency
  - GSD
  - calibration
  - rolling shutter
related:
  - comp-raspberry
  - per-geometry
  - per-cv
  - link-vtx
next:
  - per-cv
source: content/companion/per-camera.md
source_hash: 9f00eb7239e2
---

## summary
Onboard vision starts with a frame that reached the program on time. This module is about the path camera → memory → algorithm → GCS: CSI versus USB, formats (MJPEG/YUV/H.264), capture in Python with minimal latency (libcamera/V4L2 through OpenCV or GStreamer), measuring the real latency and FPS, and sending the stream to QGroundControl over RTSP/UDP through GStreamer with hardware encoding. The second half is optics in numbers: focal length in pixels, field of view, GSD and pixels on target, blur from speed and from rotation, rolling shutter skew, and what to check in a calibration besides the RMS. Lab: optics calculations and a real OpenCV calibration on a synthetic checkerboard (no camera needed), then frames in OpenCV with an FPS measurement, an RTSP stream in QGC, and a measured latency.

## theory
### Cameras and interfaces
- **CSI** (Raspberry Pi Camera v2/v3, HQ; Jetson IMX219/IMX477): a direct interface to the ISP, minimal latency (1–2 frames), high frame rates (120 fps at low resolution), a short ribbon cable (up to ~30 cm without a repeater, which is a real constraint on a drone). Controlled through libcamera (Pi) / Argus (Jetson).
- **USB (UVC)**: any webcam; higher latency (buffers, the USB controller), often MJPEG only at high fps (decoding costs CPU), but the cable can be 3–5 m and you can swap cameras without drivers. Global shutter USB cameras (for example, OV9281-based ones) are for fast motion and VIO.
- **IP cameras/HDMI capture**: for heavy platforms; a latency of 100+ ms is fine for a picture for the operator, not for a control loop.
- **Shutter**: rolling (rows exposed at different times, "jello" under vibration and fast rotation; breaks VIO) versus global (the whole frame at once). For navigation, use global.
- **Formats**: YUV420 is raw and cheap for algorithms; MJPEG is compressed, every frame independent, decoded on the CPU; H.264/H.265 are for transmission and should be encoded in hardware (Pi 4: H.264 up to 1080p30; Jetson: NVENC).

{{diagram:camera-choice-tree|Choosing a camera starts with whether the frame goes into a control loop: a picture for the operator can live with an IP camera at 100+ ms, navigation needs a global shutter, and CSI versus USB is decided by the cable length, about 30 cm versus 3–5 m.}}

### Capture with minimal latency
Principles: (1) do not copy more than necessary, (2) a short buffer queue (1–2 frames), (3) take the **latest** frame, not the first one in the queue, (4) the resolution the task needs (a detector is fine with 640×480), (5) fixed exposure/gain, otherwise auto exposure causes jumps.

OpenCV + V4L2 (USB):
```python
import cv2, time
cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640); cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 60); cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
t0 = time.perf_counter(); n = 0
while True:
    ok, frame = cap.read()                 # with BUFFERSIZE=1 this is the latest frame
    if not ok: break
    n += 1
    if n % 60 == 0: print(f"{n / (time.perf_counter() - t0):.1f} fps")
```
Pi CSI: `picamera2` (`Picamera2().configure(create_video_configuration(main={"size": (640, 480), "format": "RGB888"}, buffer_count=2))`, `capture_array()`); Jetson: the GStreamer pipeline `nvarguscamerasrc ! nvvidconv ! video/x-raw,format=BGRx ! videoconvert ! video/x-raw,format=BGR ! appsink drop=true max-buffers=1` through `cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)`.

### Measuring latency
"Glass-to-glass": a stopwatch with milliseconds on a phone screen (or a blinking LED with a timer), the camera looks at it, the program shows the frame next to it; a photo of both gives the difference = capture + processing + display latency. For the stream to the GCS, do the same with the GCS screen. Typical values: CSI + OpenCV locally 30–60 ms; USB MJPEG 60–120 ms; RTSP H.264 to QGC over Wi-Fi 150–300 ms (the player buffering is the main contribution; reduce `latency` in QGC and in the GStreamer receiver).

Compute FPS from the time between frames, not from the declared value; detect drops from gaps in frame numbers/timestamps.

### Streaming to the GCS
GStreamer on board (Pi 4 with hardware H.264 through `v4l2h264enc`; Jetson with `nvv4l2h264enc`):
```bash
# UDP/RTP to the GCS (QGC: Video Source = UDP h.264, port 5600)
gst-launch-1.0 libcamerasrc ! video/x-raw,width=1280,height=720,framerate=30/1,format=NV12,interlace-mode=progressive \
  ! v4l2h264enc extra-controls="controls,repeat_sequence_header=1,video_bitrate=2000000" ! 'video/x-h264,level=(string)4' \
  ! h264parse ! rtph264pay config-interval=1 pt=96 ! udpsink host=192.168.1.10 port=5600 sync=false
```
On a Pi 5 (no hardware encoder) replace `v4l2h264enc` and the `video/x-h264,level=(string)4` caps after it with `x264enc tune=zerolatency speed-preset=ultrafast bitrate=2000`. An RTSP server (QGC: RTSP URL): `gst-rtsp-server` (`test-launch` from its examples) or `mediamtx` with the same pipeline; RTSP is convenient for several clients and reconnections, UDP gives the minimum latency. The bitrate follows the link budget (2–4 Mbit/s for 720p30 over Wi-Fi/4G; 0.5–1 Mbit/s at 480p for long-range links). More frequent keyframes (`iframe period` 1 s) mean faster recovery after losses.

### Camera and autopilot
The frame time has to be matched with the flight data: a frame timestamp (monotonic clock) + MAVLink `SYSTEM_TIME`/`TIMESYNC` to synchronize with the FC; the offset and orientation of the camera relative to the IMU (`CAM_*`/extrinsics) for any geometry (VIO, tracking). The companion is powered from its own BEC (the peripherals module), and the camera and its ribbon cable are kept away from power wiring.

{{diagram:glass-to-glass|What makes up the video latency from light on the sensor to the screen (typical shares; measure your own chain).}}

### Sensor and lens: focal length, field of view, pixel
You choose a camera for a task by three numbers. The first is the **pixel size p** (the sensor pitch, µm). The second is the lens **focal length f** (mm). The third is the **mode resolution** W×H that the algorithm actually runs at. Everything else follows from them:
- active sensor width w = W_full·p;
- horizontal field of view HFOV = 2·atan(w / 2f);
- focal length in pixels f_px = f / p_mode, where p_mode is the effective pixel of the chosen mode. With 2×2 binning it doubles; with a crop it stays the same, but the field of view narrows.

Why f_px is the number that matters: it is the factor that converts angles into pixels. GSD, blur and rolling shutter skew are all computed through it, and the same quantity sits in the calibration matrix K (`per-geometry`).

| Camera (Raspberry Pi, datasheet; shutter per sensor) | Sensor | Pixel | Active area | f | HFOV datasheet / formula | Shutter |
|---|---|---|---|---|---|---|
| Camera Module 2 | IMX219 (from November 2026, IMX355) | 1.12 µm | 3.68 × 2.76 mm | 3.04 mm | 62.2° / 62.4° | rolling |
| Camera Module 3 | IMX708, 4608×2592 | 1.4 µm | 6.45 × 3.63 mm | 4.74 mm | 66° / 68.5° | rolling |
| Camera Module 3 Wide | IMX708 | 1.4 µm | 6.45 × 3.63 mm | 2.75 mm | 102° / 99.1° | rolling |
| HQ Camera | IMX477 | 1.55 µm | 6.287 × 4.712 mm | C/CS lens | depends on lens | rolling |
| Global Shutter Camera | IMX296, 1456×1088 | 3.45 µm | 6.3 mm diagonal | C/CS lens | with 6 mm: 45.4° (formula) | global |

For CM3 and CM3 Wide the datasheet and the formula disagree by 2.5–3° in opposite directions (for CM3 the formula is larger than the datasheet, for Wide it is smaller); for CM2 by 0.2°. Likely reasons (an inference; the datasheet does not explain it): lens distortion (on a wide-angle lens the barrel widens the real angle) and a rounded "nominal" f. That is why f_px for geometry comes from calibration, not from the datasheet. The datasheet is good for choosing a camera; calibration is for calculations. For CM3 in the 2304×1296 mode (2×2 binning, effective pixel 2.8 µm; `rpicam-hello --list-cameras` shows the list of modes), the datasheet f gives f_px = 4.74 mm / 2.8 µm = 1693 px, while the datasheet HFOV of 66° gives (2304/2)/tan 33° = 1774 px. That is almost a 5 % difference, and only a calibration tells you which number is right for your unit.

### GSD, footprint and pixels on the object
For a camera looking straight down (nadir) from a height h above flat ground:
- **GSD** (ground sample distance, meters per pixel) = h·p_mode / f;
- **footprint** = W·GSD × H·GSD;
- **pixels on the object** = object size / GSD.

CM3, 2304×1296, f = 4.74 mm: at 30 m GSD = 1.77 cm/px, footprint 41 × 23 m; at 50 m, 2.95 cm/px, 68 × 38 m; at 100 m, 5.91 cm/px, 136 × 77 m. An object 0.5 m wide spans 28, 17 and 8 px at 30, 50 and 100 m, and with the wide-angle CM3 Wide (2.75 mm) 16, 10 and 5 px. A detector needs at least 20–30 px along the shorter side of the object (a course guideline). So searching for half-meter targets with a CM3 fits within heights up to 30–40 m. A wide angle gives a bigger footprint, but the targets "melt" in it: choosing a lens is a trade-off between the area covered and the pixels on target, and it is settled by the requirement, not by taste (`eng-method-101`). With a tilted camera the GSD grows toward the top of the frame. Across the viewing direction GSD ≈ R·p/f, where R is the range along the ray; along the viewing direction the ground pixel is longer by another factor of 1/cos θ (θ is the angle of the ray from vertical): GSD_along ≈ h·p/(f·cos²θ). At θ = 45° that is another ×1.41 over the across value.

### Exposure and motion blur
During the exposure time t the image moves, and a point is smeared into a streak:
- from translation at speed v: blur_px = v·t / GSD;
- from rotation at an angular rate ω across the optical axis (roll and pitch for a nadir camera, yaw for a forward camera): blur_px = ω·t·f_px.

CM3 at 50 m (GSD 2.95 cm/px, f_px 1693), 10 m/s and a 90°/s turn:

| Exposure | Blur from 10 m/s | Blur from 90°/s |
|---|---|---|
| 1/2000 s | 0.17 px | 1.33 px |
| 1/1000 s | 0.34 px | 2.66 px |
| 1/500 s | 0.68 px | 5.32 px |
| 1/250 s | 1.35 px | 10.6 px |
| 1/60 s | 5.64 px | 44.3 px |

The conclusion that surprises beginners: at altitude it is **rotation that blurs, not flight**. Translational blur drops below 0.5 px already at 1/677 s, while a 90°/s rotation gives 1.3 px even at 1/2000 s. So for vision, smooth maneuvers and damping matter more than speed. For feature tracking (VIO, optical flow) keep the blur ≤ 0.5–1 px (a course guideline); a detector of large objects tolerates a few pixels.

{{diagram:camera-motion-blur|Blur grows linearly with exposure, but a 90°/s rotation blurs eight times more than 10 m/s of flight at 50 m: at 1/500 s that is 5.3 px versus 0.7 px.}}

A short exposure is not free. With the same light, halving t means doubling the gain. Photon shot noise is set by the number of collected electrons N, SNR = √N, so half the light means an SNR √2 times lower (−3 dB). At dusk you cannot get a short exposure with acceptable noise, and then a large pixel helps (3.45 µm on the GS Camera versus 1.4 µm on the CM3 is 6 times the area; versus 2.8 µm in 2×2 binning, 1.5 times) or a fast lens. Auto exposure on board is capped in time (for example, no longer than 2 ms) and separately in gain: otherwise, when the camera tilts toward the ground, AE lengthens the exposure and the blur "breathes" from frame to frame.

### Rolling and global shutter in numbers
A rolling shutter sensor reads the rows out one after another. The frame readout time t_r is no longer than the frame period: at 60 frames/s t_r ≤ 16.7 ms (the exact value comes from the sensor or driver documentation). The top and bottom of the frame are captured t_r apart, and under motion the frame is skewed:
- for a rotation across the optical axis (roll and pitch for a nadir camera, yaw for a forward camera) the skew is up to ω·t_r·f_px: 90°/s, f_px 1693 → up to 89 px at 30 frames/s and up to 44 px at 60 frames/s;
- from translation at altitude up to v·t_r/GSD: 10 m/s at 50 m → up to 11.3 px at 30 frames/s.

For a detector, a skew of tens of pixels is a distortion of shape. For VIO and geometry it is a systematic error that the filter will take for motion, which is why navigation cameras use a global shutter (the IMX296 in the table above, the OV9281 among USB cameras). Vibration with a period comparable to t_r turns the skew into "jello": straight lines bend in waves. That is fixed with mechanics, not software (`per-fpv-footage`, `f-frame-mech`).

### Distortion and calibration: what to check in the result
The Brown–Conrady distortion model, the `cv2.calibrateCamera` procedure and the use of K in the "pixel → ground" chain are covered in `per-geometry`. Here is the check you do right after a calibration. The lab (step 2) runs it on synthetic data where the truth is known: f = 900 px, k₁ = −0.28.
- **A small reprojection RMS does not yet mean the calibration is right.** 25 nearly frontal views (board tilt up to 3°) gave an RMS of 0.42 px, but f_x = 919.6 ± 79.0 px: a 2 % error with a 9 % uncertainty. On frontal views, focal length and distance to the board cannot be told apart. `cv2.calibrateCameraExtended` returns the standard deviations of the parameters (`stdDeviationsIntrinsics`), and those are what you look at: σ(f_x) should be below 1 % of f_x (a course guideline).
- **Board tilt up to 40°** gave f_x = 899.4 ± 0.8 px and k₁ = −0.2793 with an RMS of 0.30 px.
- **The frame edge is extrapolation.** Even a good calibration is off by 4.5 px at the frame corner (1270, 710): the board never reached it. Without a distortion model the error at the same point is 160 px. Views where the board reaches the corners are worth more than a dozen views in the center.
- **A calibration is tied to the mode.** f_px in the 2304×1296 mode is half of what it is in 4608×2592; a crop moves the principal point. Autofocus (the CM3 has it) changes f, so on board the focus is fixed (`LensPosition` in picamera2, which works only with `AfMode` = Manual: `set_controls({"AfMode": controls.AfModeEnum.Manual, "LensPosition": x})`) and the calibration is done at that position.

{{lesson:per-geometry|How the calibration is used: pixel → ray → point on the ground, the error budget of the chain and the synthetic round-trip check.}}

### Reference table: formulas and tools

| Quantity | Formula / tool | Module example |
|---|---|---|
| Field of view | HFOV = 2·atan(W·p / 2f) | CM3: 2·atan(6.45/9.48) = 68.5° |
| Focal length in pixels | f_px = f / p_mode = (W/2)/tan(HFOV/2) | 4.74 mm / 2.8 µm = 1693 px |
| GSD (nadir) | h·p_mode / f | 50 m → 2.95 cm/px |
| Pixels on the object | size / GSD | 0.5 m at 50 m → 17 px |
| Blur from speed | v·t / GSD | 10 m/s, 1/500 s → 0.68 px |
| Blur from rotation | ω·t·f_px | 90°/s, 1/500 s → 5.3 px |
| Rolling shutter skew | ω·t_r·f_px, t_r ≤ 1/fps | 90°/s, 30 frames/s → 89 px |
| Noise when shortening the exposure | SNR ∝ √(light) | t/2 → SNR/√2 (−3 dB) |
| Calibration | `cv2.findChessboardCorners`, `cornerSubPix`, `calibrateCameraExtended` | OpenCV 5.0.0 (PyPI `opencv-python-headless`, current 5.1.0.95) |
| Pi modes and focus | `rpicam-hello --list-cameras`; picamera2 `LensPosition` | Raspberry Pi OS Bookworm and later |

### Where it fits in the system

- **Takes in:** power and the companion computer (`comp-raspberry`, `comp-jetson-nano`); the autopilot time through `SYSTEM_TIME`/`TIMESYNC` (`mav-services`); the bitrate from the link budget (`rf-link-budget`).
- **Hands off:** a fresh frame with a timestamp to the detector (`per-cv`); the camera offset and orientation relative to the IMU to the geometry (`per-geometry`); an H.264 stream to QGC.
- **If you get this wrong:** the program takes the first frame in the queue instead of the latest → the detector works on a stale picture and the tracking loop oscillates (`per-tracking`). Rolling shutter under vibration and fast rotation → "jello", VIO loses features (`per-visual-nav`); the source of the vibration is tracked down in `f-frame-mech`.

## practice
Steps 1–2 need no camera: optics calculations and a real OpenCV calibration on a checkerboard rendered in code. They were run in the course sandbox (Python 3.13, NumPy 2.5, OpenCV 5.0.0: `pip install opencv-python-headless==5.0.0.93`), and the output is pasted unedited. Step 2 needs OpenCV 5.x: `cv2.undistortPoints(..., criteria=...)` does not exist in 4.x (TypeError "unexpected keyword argument 'criteria'"; on 4.x use `cv2.undistortPointsIter(pix, K_true, D_true, None, None, criteria)`); a newer 5.x may differ in the last digits (5.1.0.95: σ(f_x) 78.5 instead of 79.0 in run B). Steps 3–6 need a camera and a companion computer.

### Step 1. Optics in numbers
The script computes the field of view, f_px, GSD and footprint, the blur and the rolling shutter skew, and the pixels on a 0.5 m object from the Raspberry Pi datasheet data. Plug in your own camera (sensor width, mode resolution, pixel, f), and the height and speed of your task.

```python
"""per-camera: sensor/lens arithmetic with the module's worked numbers."""
import math
cams = {  # name: (sensor width mm, W px full, pixel um, focal mm)   -- RPi camera docs, hardware table
    "CM3 (IMX708) 4.74 mm": (6.45, 4608, 1.4, 4.74),
    "CM3 Wide 2.75 mm": (6.45, 4608, 1.4, 2.75),
    "GS (IMX296) + 6 mm": (1456 * 3.45e-3, 1456, 3.45, 6.0),
}
for name, (sw, wpx, pu, f) in cams.items():
    hfov = 2 * math.degrees(math.atan(sw / 2 / f))
    print(f"{name}: sensor {sw:.2f} mm, HFOV {hfov:.1f} deg, f_px(full {wpx}) {f / (pu * 1e-3):.0f}")
# CM3 in the 2304x1296 mode (2x2 binning, full field of view): effective pixel 2.8 um
W, Hh, p, f = 2304, 1296, 2.8e-6, 4.74e-3
fpx = f / p
print(f"\nCM3 2304x1296: f_px = {fpx:.0f} px; check via HFOV 66 deg (docs): {(W/2)/math.tan(math.radians(33)):.0f} px")
for h in (30, 50, 100):
    gsd = h * p / f
    print(f"  h={h:3d} m: GSD {gsd*100:.2f} cm/px, footprint {W*gsd:.0f} x {Hh*gsd:.0f} m")
h = 50; gsd = h * p / f
print(f"\nmotion blur at h=50 m, v=10 m/s (GSD {gsd*100:.2f} cm/px):")
for t in (1/2000, 1/1000, 1/500, 1/250, 1/60):
    print(f"  t=1/{1/t:.0f} s: translation {10*t/gsd:.2f} px, rotation 90 deg/s: {math.radians(90)*t*fpx:.2f} px")
t_max = 0.5 * gsd / 10
print(f"  t_exp for <=0.5 px at 10 m/s: {t_max*1e3:.2f} ms = 1/{1/t_max:.0f} s")
for fps in (30, 60):
    tr = 1 / fps
    print(f"rolling shutter, readout <= 1/{fps} s: roll/pitch 90 deg/s -> skew top-to-bottom up to {math.radians(90)*tr*fpx:.0f} px; "
          f"10 m/s at 50 m -> {10*tr/gsd:.1f} px")
# object 0.5 m wide: pixels on target
for h in (30, 50, 100):
    print(f"0.5 m object at {h} m: {0.5/(h*p/f):.0f} px  (wide lens 2.75 mm: {0.5/(h*p/2.75e-3):.0f} px)")
```

```text
CM3 (IMX708) 4.74 mm: sensor 6.45 mm, HFOV 68.5 deg, f_px(full 4608) 3386
CM3 Wide 2.75 mm: sensor 6.45 mm, HFOV 99.1 deg, f_px(full 4608) 1964
GS (IMX296) + 6 mm: sensor 5.02 mm, HFOV 45.4 deg, f_px(full 1456) 1739

CM3 2304x1296: f_px = 1693 px; check via HFOV 66 deg (docs): 1774 px
  h= 30 m: GSD 1.77 cm/px, footprint 41 x 23 m
  h= 50 m: GSD 2.95 cm/px, footprint 68 x 38 m
  h=100 m: GSD 5.91 cm/px, footprint 136 x 77 m

motion blur at h=50 m, v=10 m/s (GSD 2.95 cm/px):
  t=1/2000 s: translation 0.17 px, rotation 90 deg/s: 1.33 px
  t=1/1000 s: translation 0.34 px, rotation 90 deg/s: 2.66 px
  t=1/500 s: translation 0.68 px, rotation 90 deg/s: 5.32 px
  t=1/250 s: translation 1.35 px, rotation 90 deg/s: 10.64 px
  t=1/60 s: translation 5.64 px, rotation 90 deg/s: 44.32 px
  t_exp for <=0.5 px at 10 m/s: 1.48 ms = 1/677 s
rolling shutter, readout <= 1/30 s: roll/pitch 90 deg/s -> skew top-to-bottom up to 89 px; 10 m/s at 50 m -> 11.3 px
rolling shutter, readout <= 1/60 s: roll/pitch 90 deg/s -> skew top-to-bottom up to 44 px; 10 m/s at 50 m -> 5.6 px
0.5 m object at 30 m: 28 px  (wide lens 2.75 mm: 16 px)
0.5 m object at 50 m: 17 px  (wide lens 2.75 mm: 10 px)
0.5 m object at 100 m: 8 px  (wide lens 2.75 mm: 5 px)
```

Compare with the theory: GSD 2.95 cm/px at 50 m, blur 0.68 / 5.32 px at 1/500 s, skew 89 px at 30 frames/s. Then solve the selection problem: you need to find a 0.5 m object, and the detector needs ≥ 20 px. A CM3 at 50 m gives 17 px, which is too few. Options: a height ≤ 42 m (0.5 / 20 = 2.5 cm/px → h = 0.025·4.74/0.0028 = 42 m) or the full resolution 4608×2592 (34 px at 50 m, but four times as many pixels for inference). The wide-angle CM3 Wide gives 10 px at the same height and does not work at all.

### Step 2. Calibration on a synthetic board
A camera with a known truth: 1280×720, f = 900 px, principal point (652, 355), barrel distortion k₁ = −0.28, k₂ = 0.09. Every frame is rendered by inverse mapping. For each pixel the distortion is removed, a ray is built, its intersection with the plane of a 9×6 board (25 mm squares) is found, and the color of that square is taken. Then a little blur and noise with σ = 2. After that comes the real pipeline: `findChessboardCorners` → `cornerSubPix` → `calibrateCameraExtended` (k₃ fixed). Three calibration runs: (A) 25 views with a board tilt up to 40°; (B) 25 nearly frontal views, up to 3°; (C) as A, but with a 7 px horizontal motion blur; and a check without a distortion model. The run takes about 20 s.

```python
"""per-camera lab: real OpenCV calibration on checkerboard images rendered in code.

Truth: 1280x720 camera, f = 900 px, c = (652, 355), k1 = -0.28, k2 = 0.09 (barrel, wide lens).
Board 9x6 inner corners, 25 mm squares. Each view: random pose -> exact projection with distortion
-> image rendered by inverse mapping (every output pixel -> undistort -> ray -> board plane).
"""
import sys
import numpy as np, cv2
cv2.setNumThreads(1)                             # deterministic results (course rule: reproducible numbers)

W, H = 1280, 720
K_true = np.array([[900.0, 0, 652.0], [0, 900.0, 355.0], [0, 0, 1]])
D_true = np.array([-0.28, 0.09, 0.0, 0.0, 0.0])
COLS, ROWS, SQ = 9, 6, 0.025                     # inner corners, square size m
obj = np.zeros((ROWS * COLS, 3), np.float32)
obj[:, :2] = np.mgrid[0:COLS, 0:ROWS].T.reshape(-1, 2) * SQ

# undistorted normalized coords of every output pixel (fixed for the camera)
uu, vv = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
pix = np.stack([uu.ravel(), vv.ravel()], 1).reshape(-1, 1, 2)
norm = cv2.undistortPoints(pix, K_true, D_true, criteria=(cv2.TERM_CRITERIA_COUNT | cv2.TERM_CRITERIA_EPS, 40, 1e-9)).reshape(-1, 2)
rays = np.hstack([norm, np.ones((norm.shape[0], 1))])

def render(rvec, tvec, blur_px=0.0, noise=2.0, rng=None):
    R, _ = cv2.Rodrigues(rvec)
    n = R[:, 2]; d = n @ tvec.ravel()                      # board plane in camera frame: n.X = d
    s = d / (rays @ n)                                     # ray scale to hit the plane
    P = rays * s[:, None] - tvec.ravel()
    B = P @ R                                              # board coordinates
    i = np.floor(B[:, 0] / SQ + 1); j = np.floor(B[:, 1] / SQ + 1)
    inside = (B[:, 0] > -SQ) & (B[:, 0] < COLS * SQ) & (B[:, 1] > -SQ) & (B[:, 1] < ROWS * SQ) & (s > 0)
    img = np.full(W * H, 128.0)
    img[inside] = np.where(((i + j) % 2 == 0)[inside], 30.0, 225.0)
    img = img.reshape(H, W)
    img = cv2.GaussianBlur(img, (0, 0), 0.7)
    if blur_px > 0:                                        # horizontal motion blur
        k = np.zeros((1, int(blur_px) | 1)); k[:] = 1.0 / k.size
        img = cv2.filter2D(img, -1, k)
    img += rng.normal(0, noise, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)

def views(rng, n, tilt_deg, spread=1.0):
    out = []
    while len(out) < n:
        rvec = np.deg2rad(rng.uniform(-tilt_deg, tilt_deg, 3)) * np.array([1, 1, 0.3])
        z = rng.uniform(0.35, 0.7)
        cx, cy = (COLS - 1) * SQ / 2, (ROWS - 1) * SQ / 2
        R, _ = cv2.Rodrigues(rvec)
        target = np.array([rng.uniform(-0.45, 0.45) * spread * z, rng.uniform(-0.25, 0.25) * spread * z, z])
        tvec = (target - R @ np.array([cx, cy, 0])).reshape(3, 1)
        pts, _ = cv2.projectPoints(obj, rvec, tvec, K_true, D_true)
        p = pts.reshape(-1, 2)
        if p[:, 0].min() < 20 or p[:, 0].max() > W - 20 or p[:, 1].min() < 20 or p[:, 1].max() > H - 20:
            continue
        out.append((rvec, tvec))
    return out

def calibrate(name, n, tilt, seed, blur=0.0, spread=1.0):
    rng = np.random.default_rng(seed)
    objp, imgp, cov = [], [], np.zeros((H // 40, W // 40), bool)
    for rvec, tvec in views(rng, n, tilt, spread):
        img = render(rvec, tvec, blur, rng=rng)
        ok, c = cv2.findChessboardCorners(img, (COLS, ROWS), cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE)
        if not ok:
            continue
        c = cv2.cornerSubPix(img, c, (5, 5), (-1, -1), (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 50, 1e-3))
        objp.append(obj); imgp.append(c)
        for u, v in c.reshape(-1, 2):
            cov[int(v) // 40, int(u) // 40] = True
    flags = cv2.CALIB_FIX_K3
    rms, K, D, rv, tv, sdi, sde, per = cv2.calibrateCameraExtended(objp, imgp, (W, H), None, None, flags=flags)
    sd = sdi.ravel()
    print(f"[{name}] views used {len(objp)}/{n}, coverage {cov.mean()*100:.0f}% of 40px cells")
    print(f"  RMS reprojection {rms:.3f} px")
    print(f"  fx {K[0,0]:.1f} (+-{sd[0]:.1f})  fy {K[1,1]:.1f}  cx {K[0,2]:.1f} (+-{sd[2]:.1f})  cy {K[1,2]:.1f}   truth 900/900/652/355")
    print(f"  k1 {D.ravel()[0]:+.4f} k2 {D.ravel()[1]:+.4f}   truth -0.2800 +0.0900")
    # what the error does at the frame corner: undistort the true corner pixel with both models
    corner = np.array([[[1270.0, 710.0]]])
    a = cv2.undistortPoints(corner, K_true, D_true, P=K_true).ravel()
    b = cv2.undistortPoints(corner, K, D, P=K_true).ravel()
    print(f"  corner pixel (1270,710) after undistort: error {np.hypot(*(a-b)):.2f} px vs truth")
    return K, D

if __name__ == "__main__":
    calibrate("A: 25 views, tilt up to 40 deg", 25, 40, 1)
    calibrate("B: 25 views, nearly frontal (tilt 3 deg)", 25, 3, 2)
    calibrate("C: 25 views, tilt 40, 7 px motion blur", 25, 40, 3, blur=7)
    # ignoring distortion entirely: how far is a corner-of-frame point?
    corner = np.array([[[1270.0, 710.0]]])
    a = cv2.undistortPoints(corner, K_true, D_true, P=K_true).ravel()
    print(f"no distortion model: corner pixel (1270,710) really maps to ({a[0]:.1f},{a[1]:.1f}) -> error {np.hypot(1270-a[0],710-a[1]):.1f} px")
```

```text
[A: 25 views, tilt up to 40 deg] views used 25/25, coverage 55% of 40px cells
  RMS reprojection 0.297 px
  fx 899.4 (+-0.8)  fy 900.2  cx 653.2 (+-1.4)  cy 352.7   truth 900/900/652/355
  k1 -0.2793 k2 +0.0874   truth -0.2800 +0.0900
  corner pixel (1270,710) after undistort: error 4.51 px vs truth
[B: 25 views, nearly frontal (tilt 3 deg)] views used 25/25, coverage 63% of 40px cells
  RMS reprojection 0.415 px
  fx 919.6 (+-79.0)  fy 919.5  cx 649.6 (+-2.4)  cy 353.0   truth 900/900/652/355
  k1 -0.2976 k2 +0.1057   truth -0.2800 +0.0900
  corner pixel (1270,710) after undistort: error 17.29 px vs truth
[C: 25 views, tilt 40, 7 px motion blur] views used 25/25, coverage 55% of 40px cells
  RMS reprojection 0.318 px
  fx 899.6 (+-1.2)  fy 899.4  cx 654.0 (+-1.7)  cy 356.4   truth 900/900/652/355
  k1 -0.2808 k2 +0.0929   truth -0.2800 +0.0900
  corner pixel (1270,710) after undistort: error 5.51 px vs truth
no distortion model: corner pixel (1270,710) really maps to (1409.0,789.9) -> error 160.3 px
```

How to read it. In run A everything agrees with the truth within σ: f_x 899.4 ± 0.8, k₁ −0.2793. In run B the RMS is almost the same (0.42 px), but f_x is 20 px off with σ = 79 px. You cannot tell a "bad" calibration by the RMS alone; you have to look at the σ of the parameters. Multithreaded OpenCV changed σ in B by tenths of a pixel from run to run. That is why the script has `cv2.setNumThreads(1)`: the output matches to the last digit on every run (the reproducibility rule from `eng-method-101`). Run C shows that a symmetric 7 px blur barely hurts on synthetic data: the square corner shifts symmetrically. On a real camera blur comes together with the rolling shutter and changes the shape of the board, so blurred views are discarded. The last line is the price of a forgotten distortion model: 160 px at the frame corner.

### Moving to real hardware: calibrating your own camera
Print a 9×6 board with 25 mm squares and check with a ruler that a square is exactly 25.0 mm: printers scale, and an error in the square size goes into the translation scale t, not into K. Glue it to a rigid flat backing. Put the camera in its working mode (the same resolution and binning as in flight), turn autofocus off and fix the focus (`LensPosition`), and make the exposure short and fixed. Take 25–40 sharp views: tilt up to 40°, the board in every corner of the frame, different distances. Run the same pipeline with `calibrateCameraExtended`. Acceptance (a course guideline): RMS < 0.5 px (up to 1 px is acceptable), σ(f_x) < 1 % of f_x, f_x ≈ f_y within 1–2 %, f_x within ~5 % of the datasheet estimate (for a CM3 in 2304×1296, between 1693 and 1774 px), the principal point within ~5 % of the center. If σ(f_x) is large, add tilted views. If the RMS is large, throw out the blurred views and check that the board is flat. A camera on a drone: calibrate before installing it, or with the propellers removed and the battery disconnected.

### Step 3. Capture
USB or CSI: the code above, 640×480, fixed exposure; 30 s for the average FPS and drops. Compare BUFFERSIZE 1 and 4.

### Step 4. Glass-to-glass latency
A stopwatch on a phone → a photo of "screen vs OpenCV window" ×5 → the average. Then with display through `cv2.imshow` turned off (capture + a timestamp on the frame only), estimate the share of the display.

More accurate and without photos: a flashing screen. The camera looks at a window that the program switches between black and white; latency = the moment the camera saw the change minus the moment of the switch (the same clock, so no synchronization is needed):
```python
import cv2, numpy as np, time
cap = cv2.VideoCapture(0); cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
cv2.namedWindow("flash", cv2.WINDOW_NORMAL)
lat = []
for k in range(20):
    white = k % 2 == 0
    cv2.imshow("flash", np.full((400, 400), 255 if white else 0, np.uint8)); cv2.waitKey(1)
    t_switch = time.perf_counter()
    while True:
        ok, f = cap.read()
        if ok and (f.mean() > 128) == white:          # the camera now sees the new colour
            lat.append((time.perf_counter() - t_switch) * 1000); break
    time.sleep(0.3)
print(f"latency median {np.median(lat):.0f} ms, p95 {np.percentile(lat, 95):.0f} ms")
```
Point the camera so that the window fills almost the whole frame; the result also includes the latency of the monitor itself (5–20 ms), which does not matter when comparing options (USB versus CSI, MJPEG versus YUYV, BUFFERSIZE 1 versus 4).

### Step 5. Stream to QGC
GStreamer UDP H.264 to QGC; glass-to-glass latency to the GCS screen; bitrate versus quality/latency (2 Mbit vs 8 Mbit).

Orders of magnitude for tuning: 1280×720 at 30 frames/s and 2 Mbit/s is ~8 KB per frame on average; a keyframe (I-frame) is 5–10 times larger, and on a weak link it is the one that arrives late or gets lost. Hence the low-latency settings: a short keyframe interval (0.5–1 s), `config-interval=1` in `rtph264pay` (the stream parameters are repeated, so a receiver that connects later starts decoding right away), no B-frames.

### Step 6. RTSP
mediamtx or gst-rtsp-server; connect from QGC and VLC at the same time. Compare the FPS and the latency (median and p95 with the flashing screen) for the two capture variants, RTSP in QGC, the bitrate and the keyframe interval.

Self-check: the lab is done when, for the calculation part (steps 1–2, no camera), the step 1 script on the example data outputs GSD 2.95 cm/px at 50 m, blur 0.68 and 5.32 px at 1/500 s, skew 89 px at 30 frames/s, and for your own camera you have computed the GSD, the pixels on target and the exposure at which the translational blur is ≤ 0.5 px; the step 2 calibration gives f_x 899 ± 1 px, k₁ −0.279 ± 0.002 and an RMS of about 0.3 px in run A, σ(f_x) of the order of 80 px with an RMS of about 0.4 px in run B, and 160 px at the corner without a distortion model; the calibration of your own camera passes the acceptance from "Moving to real hardware" (RMS < 0.5–1 px, σ(f_x) < 1 %, f_x within 5 % of the datasheet). For the streaming part (steps 3–6, with a camera): FPS is computed from the time between frames, not taken from the declared value; the median latency is compared with the typical values from the theory (CSI + OpenCV locally 30–60 ms, USB MJPEG 60–120 ms, RTSP H.264 to QGC over Wi-Fi 150–300 ms) allowing for the 5–20 ms of the monitor; if it came out several times larger, look at `BUFFERSIZE` and the player buffering (`latency`); the bitrate is checked against the estimate (~8 KB per frame at 2 Mbit/s and 30 frames/s), and the keyframe interval is 0.5–1 s.

**Reference answer for the self-check.** The correct CM3 optics in 2304×1296: f_px ≈ 1693 px from the datasheet f (1774 px from the datasheet HFOV; the calibration tells you the truth), GSD = h·2.8 µm / 4.74 mm. Typical mistakes: (1) a GSD half the correct value (1.48 instead of 2.95 cm/px at 50 m): the 1.4 µm pixel of the full mode was used although the algorithm runs in 2×2 binning, so the target looks twice as large as the detector will see it; (2) "the blur is small, so 1/250 s is fine": only the translational blur was computed, while a 90°/s rotation gives 10.6 px; (3) a calibration that is "excellent, RMS 0.4 px" while f_x is 2 % off: all views are frontal and σ(f_x) was not checked; (4) the GSD is computed from the datasheet HFOV while K for the geometry comes from the calibration, and the numbers in one report disagree by 5 %: use one value, the calibrated one, in all calculations.

## diagnostics
- **Symptom:** the latency grows over time
  - Possible cause: the algorithm is slower than the FPS and the buffer queue builds up.
  - What to do: BUFFERSIZE 1, take the latest frame, lower the resolution/FPS, skip frames.
- **Symptom:** "jello"/bending under motion
  - Possible cause: rolling shutter + vibration.
  - What to do: damp the camera mount, a global shutter, a shorter exposure.
- **Symptom:** the stream stutters in QGC
  - Possible cause: a bitrate above the link capacity, packet loss without keyframes.
  - What to do: a lower bitrate, more frequent I-frames, check the Wi-Fi/link budget.
- **Symptom:** the CSI camera is not detected
  - Possible cause: the ribbon cable/connector, its length, the overlay not enabled.
  - What to do: `rpicam-hello --list-cameras` (before Raspberry Pi OS Bookworm, `libcamera-hello`), a shorter cable, the `dtoverlay` config.
- **Symptom:** the detector sees targets confidently at 20 m and loses them at 50 m
  - Possible cause: too few pixels on target at that height (0.5 m at 50 m with a CM3 in 2304×1296 is 17 px).
  - What to do: compute the pixels on target from the GSD (step 1); lower the height, raise the mode resolution or take a lens with a larger f.
- **Symptom:** frames are sharp on straight legs and blurred in turns
  - Possible cause: blur from rotation ω·t·f_px: at 1/500 s and 90°/s that is 5.3 px.
  - What to do: cap the exposure time (AE with a limit), turn more smoothly, limit the angular rate in the survey mode.
- **Symptom:** a calibration with a small RMS, but the ground points are off by percent of the range
  - Possible cause: frontal views, so f_x is poorly determined (large σ), or a calibration in a different mode/focus.
  - What to do: `calibrateCameraExtended`, check σ(f_x) < 1 %; calibrate in the working mode with `LensPosition` fixed.
- **Symptom:** f_x from the calibration differs by 5 % from the value computed from the datasheet HFOV
  - Possible cause: most likely the datasheet angle is rounded or includes the distortion (for a CM3: 1693 px from f versus 1774 px from the HFOV).
  - What to do: this is normal; if σ(f_x) is small, trust the calibration.
- **Symptom:** auto exposure "flickers" when the camera tilts
  - Possible cause: AE reacts to the sky/ground.
  - What to do: fixed exposure/gain, or a limited range.

## references
- Raspberry Pi — Camera software (libcamera, picamera2) | https://www.raspberrypi.com/documentation/accessories/camera-software.html | primary | A
- GStreamer — Documentation | https://gstreamer.freedesktop.org/documentation/ | secondary | B
- Raspberry Pi — Camera hardware (table: sensor, pixel, f, HFOV) | https://www.raspberrypi.com/documentation/accessories/camera.html | primary | A
- Raspberry Pi — Camera Module 3 (IMX708, 4608×2592, 1.4 µm) | https://www.raspberrypi.com/documentation/accessories/camera-module-3.html | primary | A
- OpenCV — Camera calibration tutorial (Python) | https://github.com/opencv/opencv/blob/5.x/doc/py_tutorials/py_calib3d/py_calibration/py_calibration.markdown | primary | A
- OpenCV — calib3d (calibrateCameraExtended, stdDeviationsIntrinsics) | https://docs.opencv.org/5.x/d9/d0c/group__calib3d.html | primary | A
- QGroundControl — Video settings (UDP/RTSP sources) | https://docs.qgroundcontrol.com/Stable_V5.0/en/qgc-user-guide/settings_view/video.html | primary | A

## checklist
- I know the differences between CSI/USB, rolling/global shutter and the formats
- Capture with a 1-frame queue and fixed exposure
- FPS and glass-to-glass latency measured
- An H.264 stream to QGC over UDP and RTSP works
- I understand where the latency is lost in the chain and how to reduce it
- I compute HFOV, f_px, GSD and pixels on target from the camera datasheet and the mode
- I choose the exposure from the blur from speed and from rotation
- I estimate the rolling shutter skew and know when a global shutter is needed
- I calibrate a camera and check the σ of the parameters, not just the RMS
