---
id: per-camera
title: "Cameras and video streaming on the companion"
level: L3
readingTime: 35 min
firmware: ArduPilot · PX4
status: published
added: 2026-11-08
tags:
  - camera
  - GStreamer
  - RTSP
  - OpenCV
  - latency
related:
  - comp-raspberry
  - per-cv
  - link-vtx
next:
  - per-cv
source: content/companion/per-camera.md
source_hash: 123e3eec0657
---

## summary
Onboard vision starts with a frame that reached the program on time. This module is about the path camera → memory → algorithm → GCS: CSI versus USB, formats (MJPEG/YUV/H.264), capture in Python with minimal latency (libcamera/V4L2 via OpenCV or GStreamer), measuring the real latency and FPS, and sending the stream to QGroundControl over RTSP/UDP via GStreamer with hardware encoding. Lab: frames in OpenCV with an FPS measurement, an RTSP stream in QGC, measured latency.

## theory
### Cameras and interfaces
- **CSI** (Raspberry Pi Camera v2/v3, HQ; Jetson IMX219/IMX477): a direct interface to the ISP, minimal latency (1–2 frames), high frame rate (120 fps at low resolution), a short ribbon cable (up to ~30 cm without a repeater — on a drone that's a constraint). Controlled via libcamera (Pi) / Argus (Jetson).
- **USB (UVC)**: any webcam; higher latency (buffers, the USB controller), often only MJPEG at high fps (decoding costs CPU), but the cable can be 3–5 m and you can swap cameras without drivers. Global shutter USB cameras (for example, OV9281-based) are for fast motion and VIO.
- **IP cameras/HDMI capture**: for heavy platforms; latency of 100+ ms — fine as video for the operator, not for a control loop.
- **Shutter**: rolling (rows exposed at different times — “jello” under vibration and fast rotation; breaks VIO) versus global (the whole frame at once). For navigation — global.
- **Formats**: YUV420 — raw, cheap for algorithms; MJPEG — compressed, every frame independent, decoded on the CPU; H.264/H.265 — for transmission, encode in hardware (Pi 4: H.264 up to 1080p30; Jetson: NVENC).

### Low-latency capture
Principles: (1) don't make extra copies, (2) a short buffer queue (1–2 frames), (3) take the **latest** frame, not the first one in the queue, (4) resolution to suit the task (640×480 is enough for a detector), (5) fixed exposure/gain — otherwise auto exposure causes jumps.

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
Pi CSI: `picamera2` (`Picamera2().configure(create_video_configuration(main={"size": (640, 480), "format": "RGB888"}, buffer_count=2))`, `capture_array()`); Jetson: the GStreamer pipeline `nvarguscamerasrc ! nvvidconv ! video/x-raw,format=BGRx ! appsink` via `cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)`.

### Measuring latency
“Glass-to-glass”: a stopwatch with milliseconds on a phone screen (or a blinking LED with a timer), the camera looks at it, the program shows the frame next to it — take a photo of both: the difference = capture + processing + display latency. For the stream to the GCS — the same with the GCS screen. Typical values: CSI + OpenCV locally 30–60 ms; USB MJPEG 60–120 ms; RTSP H.264 to QGC over Wi-Fi 150–300 ms (player buffering is the main contributor; reduce `latency` in QGC and the GStreamer receiver).

Count FPS from the time between frames, not from the advertised value; count drops from the gaps in frame numbers/timestamps.

### Streaming to the GCS
GStreamer on board (Pi 4, hardware H.264 via `v4l2h264enc`; Jetson — `nvv4l2h264enc`):
```bash
# UDP/RTP to the GCS (QGC: Video Source = UDP h.264, port 5600)
gst-launch-1.0 libcamerasrc ! video/x-raw,width=1280,height=720,framerate=30/1 \
  ! videoconvert ! v4l2h264enc extra-controls="controls,repeat_sequence_header=1,video_bitrate=2000000" \
  ! h264parse ! rtph264pay config-interval=1 pt=96 ! udpsink host=192.168.1.10 port=5600 sync=false
```
RTSP server (QGC: RTSP URL): `gst-rtsp-server` (`test-launch` from the examples) or `mediamtx` with the same pipeline; RTSP is convenient for multiple clients and reconnections, UDP gives minimal latency. Bitrate according to the link budget (2–4 Mbit/s for 720p30 over Wi-Fi/4G; for long-range links 0.5–1 Mbit/s at 480p). More frequent keyframes (`iframe period` 1 s) — faster recovery after losses.

### The camera and the autopilot
Frame time has to be matched to flight data: the frame timestamp (monotonic clock) + MAVLink `SYSTEM_TIME`/`TIMESYNC` to sync with the FC; the camera's offset and orientation relative to the IMU (`CAM_*`/extrinsics) — for any geometry (VIO, tracking). The companion is powered from its own BEC (see the peripherals module), the camera and its ribbon cable are kept away from power wires.

{{diagram:glass-to-glass|What makes up the video stream latency from light on the sensor to the screen (typical shares; measure your own chain).}}

## practice
### Step 1. Capture
USB or CSI: the code above, 640×480, fixed exposure; 30 s — average FPS, drops. Compare BUFFERSIZE 1 and 4.

### Step 2. Glass-to-glass latency
Stopwatch on a phone → photo “screen vs OpenCV window” ×5 → average. Then with display via `cv2.imshow` turned off (capture + a timestamp on the frame only) — estimate the share of display.

More precise and without photos — a flashing screen. The camera looks at a window that the program toggles between black and white; latency = the moment the camera saw the change minus the moment of the switch (the same clock, so no synchronization is needed):
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
Aim the camera so the window fills almost the whole frame; the result also includes the monitor's own latency (5–20 ms) — that doesn't get in the way when comparing options (USB versus CSI, MJPEG versus YUYV, BUFFERSIZE 1 versus 4).

### Step 3. Stream to QGC
GStreamer UDP H.264 to QGC; glass-to-glass latency to the GCS screen; bitrate versus quality/latency (2 Mbit vs 8 Mbit).

Orders of magnitude for tuning: 1280×720 at 30 fps and 2 Mbit/s is ~8 KB per frame on average; a keyframe (I-frame) is 5–10 times larger, and on a weak link it's exactly that frame that arrives late or gets lost. Hence the low-latency settings: a short keyframe interval (0.5–1 s), `config-interval=1` in `rtph264pay` (the stream parameters are repeated — a receiver that connects later starts decoding right away), no B-frames.

### Step 4. RTSP
mediamtx or gst-rtsp-server; connect from QGC and VLC at the same time. Lab: FPS measured, latency measured with the flashing screen (median and p95) for two capture options, RTSP in QGC, bitrate and keyframe interval justified.

## diagnostics
- **Symptom:** latency grows over time
  - Possible cause: the algorithm is slower than the FPS — the buffer queue piles up.
  - What to do: BUFFERSIZE 1, take the latest frame, lower the resolution/FPS, skip frames.
- **Symptom:** “jello”/bending during motion
  - Possible cause: rolling shutter + vibration.
  - What to do: damp the camera, global shutter, shorter exposure.
- **Symptom:** the stream stutters in QGC
  - Possible cause: bitrate above the link throughput, packet loss without keyframes.
  - What to do: lower bitrate, more frequent iframes, check Wi-Fi/the link budget.
- **Symptom:** the CSI camera isn't detected
  - Possible cause: ribbon cable/connector, length, overlay not enabled.
  - What to do: `rpicam-hello --list-cameras` (before Raspberry Pi OS Bookworm — `libcamera-hello`), a shorter ribbon cable, the `dtoverlay` config.
- **Symptom:** auto exposure “flickers” when the vehicle tilts
  - Possible cause: AE reacts to the sky/ground.
  - What to do: fixed exposure/gain or a limited range.

## references
- Raspberry Pi — Camera software (libcamera, picamera2) | https://raspberrypi.com/documentation/computers/camera_software.html | primary | A
- GStreamer — Documentation | https://gstreamer.freedesktop.org/documentation/ | secondary | B
- QGroundControl — Video settings (UDP/RTSP sources) | https://docs.qgroundcontrol.com/Stable_V5.0/en/qgc-user-guide/settings_view/video.html | primary | A

## checklist
- I know the difference between CSI/USB, rolling/global shutter and the formats
- Capture with a 1-frame queue and fixed exposure
- FPS and glass-to-glass latency measured
- An H.264 stream to QGC over UDP and RTSP works
- I understand where latency is lost in the chain and how to reduce it
