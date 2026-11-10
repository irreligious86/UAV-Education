---
id: per-cv
title: "Computer vision: from OpenCV to neural networks"
level: L4
readingTime: 45 min
firmware: ArduPilot · PX4
status: published
added: 2026-11-08
tags:
  - OpenCV
  - YOLO
  - detection
  - Jetson
  - metrics
related:
  - per-camera
  - per-tracking
  - per-visual-nav
next:
  - per-visual-nav
source: content/companion/per-cv.md
source_hash: 73867148b361
---

## summary
An onboard detector isn't “just run YOLO” — it's a choice between classical methods (color, contours, markers — cheap, predictable, fragile) and a neural network (robust, expensive, needs acceleration), followed by measurement: FPS on the target hardware, accuracy (precision/recall/mAP) on **your own** data, false positives and their cost in the control loop. This module goes through both branches with code, shows how to run a model on a Jetson (TensorRT) and a Pi (NCNN/ONNX Runtime/Coral), and teaches you to evaluate the result honestly.

## theory
### Classical methods: when they're enough
- **Markers** (ArUco/AprilTag): a known object with a code → detection + a 6DoF pose with subpixel accuracy, dozens of FPS on a Pi, robust to lighting. For precision landing, calibration and control-loop tests they're the best choice (ArduPilot precision landing supports AprilTag via a companion, `PLND_TYPE = 1` MAVLink `LANDING_TARGET`).
- **Color + contours**: HSV threshold → morphology → `findContours` → filter by area/shape. 2–5 ms per frame. Breaks when lighting changes; thresholds have to be calibrated on site.
- **Background/motion**: background subtraction (`createBackgroundSubtractorMOG2`) — only for a stationary camera; from a drone — optical flow and motion compensation, which is hard.
- **Templates/features** (ORB + matching): for a known object; fragile under scale and rotation.

### Neural networks: detection
Single-pass detectors (the YOLO family, SSD, NanoDet) — 320–640 px input, the output is boxes with a class and confidence, followed by NMS. Facts for onboard use:
- **Model size**: nano/small (2–10 million parameters) is the only realistic option on a Pi/Jetson Nano/Orin Nano; medium — Orin NX/AGX.
- **Acceleration**: Jetson — export to TensorRT (FP16/INT8, ×3–10 over PyTorch); Pi 4/5 — NCNN or ONNX Runtime on the CPU (a nano model at 320 px: 5–15 fps on a Pi 5), Coral USB (INT8 models) or Hailo-8L (Pi AI Kit, 13 TOPS) or Hailo-8 (AI HAT+ 26 TOPS) — dozens of fps; ARM laptops/mini PCs with a GPU — any stack.
- **Fine-tuning** on your own data is mandatory: a model pretrained on COCO “sees” people and cars, but not your marker/object. 300–1000 labeled frames from the vehicle (different altitudes, lighting, backgrounds), augmentations, 50–100 epochs on a PC/Colab; export to ONNX → TensorRT/NCNN.
- **INT8 quantization** — ×2 in speed, −1–3% mAP; a calibration set from your own data.

### Metrics that make sense
- **Precision** = TP/(TP+FP) — the share of correct ones among those found; **Recall** = TP/(TP+FN) — the share found among the true ones; the confidence threshold moves one at the expense of the other (the PR curve).
- **mAP@0.5** — the area under the PR curve at IoU ≥ 0.5; the standard, but onboard what matters more is recall at a fixed precision (the cost of an FP is a false maneuver!) and the **latency** of the full cycle (capture → inference → NMS → command).
- Evaluate on **held-out** frames from the vehicle, not on the training ones; separately by conditions (altitude, lighting) — a model that's “0.9 on average” can give 0.5 at sunset.
- **FP analysis**: classify false positives (a similar object, a shadow, the frame edge, a glare) — each group has its own cure: data, threshold, a geometric filter (object size given the flight altitude), temporal filtering (the object must appear in N frames in a row — a tracker).

### Worked example: metrics from the counts
Held-out set: 200 frames with 250 objects in them. At a confidence threshold of 0.5 the detector produced 230 boxes: 210 matched the labels at IoU ≥ 0.5 (TP), 20 were false (FP), 40 objects were missed (FN).
- Precision = TP / (TP + FP) = 210/230 = **0.91** — of what was found, 91 % is real.
- Recall = TP / (TP + FN) = 210/250 = **0.84** — of what was there, 84 % was found.
- IoU = the area of intersection / the area of union of the boxes; 0.5 — “matched”, 0.75 — “matched precisely”.

A threshold of 0.3 gives, say, precision 0.80 and recall 0.93; a threshold of 0.7 — 0.96 and 0.70. Which one to choose is decided by the cost of an error, not by how pretty the number is: in a search for a person a miss costs more than a false alarm (lower threshold, the operator checks the false alarms), in an automatic action on a target it's the other way around (higher threshold plus confirmation over several frames).

### A tracker on top of the detector
A detector on every frame is noisy and expensive. A tracker (SORT/ByteTrack: Kalman + IoU matching) gives stable IDs, smooths, survives misses and lets you detect on every 2nd–3rd frame. For the control loop, commands come from the tracker, not from the raw detector.

### The onboard pipeline
Capture (a stream, the latest frame) → preprocessing (resize, letterbox, normalization — on the GPU/in hardware where possible) → inference → NMS → tracker → publishing (a ROS 2 topic / MAVLink / ZeroMQ) with the frame timestamp. Profile every stage (`time.perf_counter`); typical proportions on a Jetson Orin Nano for YOLO-nano 640: capture 3 ms, preprocessing 2, TensorRT FP16 inference 8–12, postprocessing 2 → 15–20 ms, 50 fps in theory, 30 with margin.

{{diagram:cv-pipeline|The onboard vision pipeline: the detector at 5–10 Hz, the tracker at the camera rate, quality metrics and p99 latency as requirements.}}

## practice
### Step 1. Classical methods
ArUco — detect a marker from the camera, print the id and corners, FPS. Since OpenCV 4.7 the API is different (the old `cv2.aruco.detectMarkers` from articles doesn't work):
```python
import cv2, time
dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
detector = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())
cap = cv2.VideoCapture(0)
t0, n = time.perf_counter(), 0
while n < 300:
    ok, frame = cap.read()
    if not ok:
        break
    corners, ids, _ = detector.detectMarkers(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
    if ids is not None:
        c = corners[0][0]
        print(ids.ravel()[0], "centre px:", c.mean(axis=0).round(1))
    n += 1
print(f"{n / (time.perf_counter() - t0):.1f} FPS")
```
An HSV detector for a colored object: thresholds picked from the histogram, area/shape filtering; FPS and false positives when the light changes.

### Step 2. Data and fine-tuning
Shoot 300+ frames of the object from the vehicle/by hand in different conditions; label them (CVAT/LabelImg/Roboflow); train a nano model (Ultralytics/NanoDet) on a PC; export to ONNX. Held-out set — 20%.

### Step 3. On board
Jetson: ONNX → TensorRT FP16 (`trtexec`), inference in Python; Pi: NCNN/ONNX Runtime or Coral/Hailo. A per-stage profile, FPS with the camera (not from a file!).

### Step 4. Evaluation
Precision/recall/mAP on the held-out set, by conditions; a precision–recall curve over 5 thresholds and the chosen threshold justified by the cost of an error (as in the worked example); FPs classified; a tracker on top (ByteTrack/SORT) — ID stability on video.

### How to measure and what to write down
- **FPS with the camera, not from a file:** capture, preprocessing and inference together. A per-stage profile (ms per frame) will show where the bottleneck is. Often it's not the neural network but copying and resizing the frame.
- **Precision and recall on the held-out set.** Example: the held-out frames contain 100 objects, the detector found 90 of them and also fired 10 times on empty space. Precision = 90 / (90 + 10) = 0.90, recall = 90 / 100 = 0.90. Raising the confidence threshold usually raises precision and lowers recall.
- **Choosing the threshold through the cost of an error.** If a false positive sends the vehicle after the wrong target, while a miss only means another pass, pick a high-precision threshold, even at the cost of recall. Write down the curve over 5 thresholds and the chosen point with a one-sentence justification.
- **False positives by class:** glare, shadows, similar objects, motion blur. For each class — an example frame and a measure: data into training, a size or shape filter, a tracker with confirmation over several frames.
- **ArUco:** the marker id and corners are stable with a stationary camera. If the corners “jump”, the marker is too small in the frame or the camera isn't calibrated (the “Camera” module).

The lab counts as done when the model runs on board with FPS measured with the camera per stage, precision/recall are computed on the held-out set with a chosen threshold and justification, and the false positives are classified with a measure for each class.

## diagnostics
- **Symptom:** 30 fps on a file, 8 fps from the camera
  - Possible cause: capture/conversion on the CPU, frame copies.
  - What to do: a per-stage profile, hardware preprocessing, a lower resolution.
- **Symptom:** mAP 0.9 on validation, but in the field it doesn't see anything
  - Possible cause: validation from the same distribution as training; the field is different.
  - What to do: held-out frames from other conditions, collect more data.
- **Symptom:** false positives on shadows/glare
  - Possible cause: too few negative examples.
  - What to do: add “empty” frames with shadows to training, temporal filtering.
- **Symptom:** accuracy dropped badly after INT8
  - Possible cause: poor quantization calibration.
  - What to do: a calibration set from your own data, FP16 as a compromise.
- **Symptom:** the object ID keeps jumping
  - Possible cause: no tracker or weak matching.
  - What to do: ByteTrack, detection on every frame for tests.

## references
- OpenCV — ArUco marker detection tutorial | https://docs.opencv.org/4.x/d5/dae/tutorial_aruco_detection.html | primary | A
- NVIDIA — TensorRT documentation | https://docs.nvidia.com/deeplearning/tensorrt/latest/index.html | primary | A
- ArduPilot — Precision Landing (companion with AprilTag/IR-LOCK) | https://ardupilot.org/copter/docs/precision-landing-with-irlock.html | primary | A

## checklist
- I know when classical methods (markers, color) are enough and when a network is needed
- I fine-tuned a nano model on my own data and exported it
- The model runs on board with acceleration, FPS measured from the camera
- Precision/recall by conditions, the threshold chosen by the cost of an FP
- FPs classified, a tracker smooths the detections
