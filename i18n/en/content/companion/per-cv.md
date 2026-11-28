---
id: per-cv
title: "Computer vision: from OpenCV to neural networks"
level: L4
readingTime: 45 min
firmware: ArduPilot 4.7 (checked against 4.7.3) · PX4 · OpenCV 4.x (checked against 4.14.0)
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
source_hash: c3792ac1957a
---

## summary
An onboard detector is not "just run YOLO". It is a choice between classical methods (color, contours, markers: cheap, predictable, brittle) and a neural network (robust, expensive, needs acceleration), followed by measurement: FPS on the target hardware, accuracy (precision/recall/mAP) on **your own** data, false positives and what they cost inside the control loop. The module walks both paths with code, shows how to run a model on a Jetson (TensorRT) and a Pi (NCNN/ONNX Runtime/Coral), and teaches you to judge the result honestly.

## theory
### Classical methods: when they are enough
- **Markers** (ArUco/AprilTag): a known object carrying a code → detection plus a 6DoF pose with subpixel accuracy, tens of FPS on a Pi, robust to lighting. The best choice for precision landing, calibration and control-loop tests (ArduPilot precision landing accepts AprilTag through a companion computer: `PLND_TYPE = 1` MAVLink, message `LANDING_TARGET`).
- **Color + contours**: HSV threshold → morphology → `findContours` → filter by area/shape. 2–5 ms per frame. Breaks when the lighting changes; thresholds are tuned on site.
- **Background/motion**: background subtraction (`createBackgroundSubtractorMOG2`) works only with a static camera; from a drone you need optical flow and motion compensation, which is hard.
- **Templates/features** (ORB + matching): for a known object; brittle under scale and rotation changes.

### Neural networks: detection
Single-shot detectors (the YOLO family, SSD, NanoDet) take a 320–640 px input and output boxes with a class and a confidence score, followed by NMS. Facts that matter on board:
- **Model size**: nano/small (2–10 M parameters) is the only realistic option on a Pi/Jetson Nano/Orin Nano; medium needs an Orin NX/AGX.
- **Acceleration**: on a Jetson, export to TensorRT (FP16/INT8, ×3–10 over PyTorch); on a Pi 4/5, NCNN or ONNX Runtime on the CPU (a nano model at 320 px: 5–15 fps on a Pi 5), a Coral USB Accelerator (INT8 models), and on a Pi 5 only (PCIe) a Hailo-8L (Raspberry Pi AI Kit / AI HAT+ 13 TOPS), a Hailo-8 (AI HAT+ 26 TOPS) or a Hailo-10H (AI HAT+ 2, 40 TOPS INT4) for tens of fps; ARM laptops/mini PCs with a GPU run any stack.
- **Fine-tuning** on your own data is mandatory: a model pretrained on COCO "sees" people and cars, but not your marker or object. 300–1000 labeled frames from the aircraft (different altitudes, lighting, backgrounds), augmentations, 50–100 epochs on a PC/Colab; export to ONNX → TensorRT/NCNN.
- **INT8 quantization**: ×2–4 faster than FP32 on hardware with integer units, −1–5 points of mAP50-95; the calibration set comes from your own data. The gain over FP16 depends on the board: 17–39 % on an Orin Nano Super and zero on the original Jetson Nano (comp-jetson-nano).

### Metrics that make sense
- **Precision** = TP/(TP+FP), the share of correct detections among everything found; **Recall** = TP/(TP+FN), the share of true objects that were found; the confidence threshold trades one for the other (the PR curve).
- **mAP@0.5** is the area under the PR curve at IoU ≥ 0.5; it is the standard, but on board two things matter more: recall at a fixed precision (the cost of an FP is a false maneuver!) and the **latency** of the full cycle (capture → inference → NMS → command).
- Evaluate on **held-out** frames from the aircraft, not on training frames, and separately per condition (altitude, lighting): a model that scores "0.9 on average" can drop to 0.5 at sunset.
- **FP analysis**: classify the false positives (similar object, shadow, frame edge, glare); each group has its own fix: more data, the threshold, a geometric filter (object size for the flight altitude), temporal filtering (the object must appear in N consecutive frames, i.e. a tracker).

### Worked example: metrics from the counts
Held-out set: 200 frames containing 250 objects. At a confidence threshold of 0.5 the detector output 230 boxes: 210 matched the labels at IoU ≥ 0.5 (TP), 20 were false (FP), and 40 objects were missed (FN).
- Precision = TP / (TP + FP) = 210/230 = **0.91**: of what was found, 91 % is real.
- Recall = TP / (TP + FN) = 210/250 = **0.84**: of what was there, 84 % was found.
- IoU = intersection area / union area of the two boxes; 0.5 means "matched", 0.75 means "matched tightly".

A threshold of 0.3 gives, say, precision 0.80 and recall 0.93; a threshold of 0.7 gives 0.96 and 0.70. The cost of an error picks the point, not how nice the number looks: in a search for a person a miss costs more than a false alarm (lower threshold, the operator checks the false alarms); for an automatic action on a target it is the other way round (higher threshold plus confirmation over several frames).

{{diagram:chart-cv-threshold|Raising the threshold lifts precision (0.80 → 0.91 → 0.96) and drops recall (0.93 → 0.84 → 0.70): the cost of an error picks the point, a low threshold for a person search, a high one plus multi-frame confirmation for an action on a target.}}

### A tracker on top of the detector
Per-frame detection is noisy and expensive. A tracker (SORT/ByteTrack: a Kalman filter + IoU matching) gives stable IDs, smooths the boxes, survives missed detections and lets you detect only on every 2nd–3rd frame. The control loop takes its commands from the tracker, not from the raw detector.

### The onboard pipeline
Capture (a thread, latest frame) → preprocessing (resize, letterbox, normalization; on the GPU or in hardware where possible) → inference → NMS → tracker → publishing (a ROS 2 topic / MAVLink / ZeroMQ) with the frame timestamp. Profile every stage (`time.perf_counter`); typical proportions on a Jetson Orin Nano for YOLO-nano at 640: capture 3 ms, preprocessing 2, TensorRT FP16 inference 8–12, postprocessing 2 → 15–20 ms, 50 fps in theory, 30 with headroom. Inference time depends on the model and the board power mode: this is an order-of-magnitude estimate, not a measurement; YOLO26n on an Orin Nano Super takes 4.57 ms (TensorRT FP16, inference only, Ultralytics benchmark, comp-jetson-nano).

{{diagram:cv-pipeline|The onboard vision pipeline: the detector at 5–10 Hz, the tracker at the camera rate, quality metrics and p99 latency as requirements.}}

### Where it fits in the system

- **Takes in:** the latest frame with a timestamp (`per-camera`); the accelerator and the latency budget (`per-edge-ml`); labeled frames from your own aircraft for fine-tuning.
- **Hands off:** boxes with confidence → to the tracker → a stable target ID to the tracking loop (`per-tracking`); the marker pose to precision landing (`per-landing`); the target pixel to the geometry step (`per-geometry`).
- **If you get this wrong:** a confidence threshold picked for a pretty mAP instead of the cost of an error → a false target becomes a false maneuver of the aircraft (`per-tracking`). Commands taken from the raw detector without a tracker → misses and box jumps go straight into the velocity and the aircraft jerks; assembling the pipeline is covered in `per-vision-pipeline`.

## practice
### Step 1. Classical methods
ArUco: detect a marker from the camera, print the id and the corners, measure FPS. Since OpenCV 4.7 the API is different: the old `cv2.aruco.Dictionary_get`/`DetectorParameters_create` from articles are gone, and the free function `cv2.aruco.detectMarkers` survives only in the contrib build as a deprecated wrapper:
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
An HSV detector for a colored object: thresholds picked from the histogram, area/shape filtering; measure FPS and false positives when the light changes.

### Step 2. Data and fine-tuning
Shoot 300+ frames of the object from the aircraft or by hand in different conditions; label them (CVAT/LabelImg/Roboflow); train a nano model (Ultralytics/NanoDet) on a PC; export to ONNX. The held-out set is 20%.

### Step 3. On board
Jetson: ONNX → TensorRT FP16 (`trtexec`), inference from Python; Pi: NCNN/ONNX Runtime or Coral/Hailo. Profile per stage, and measure FPS with the camera (not from a file!).

### Step 4. Evaluation
Precision/recall/mAP on the held-out set, per condition; a precision–recall curve over 5 thresholds and the chosen threshold justified by the cost of an error (as in the worked example); FPs classified; a tracker on top (ByteTrack/SORT) and ID stability on video.

### How to measure and what to record
- **FPS with the camera, not from a file:** capture, preprocessing and inference together. A per-stage profile (ms per frame) shows the bottleneck. Often it is not the network but copying and resizing the frame.
- **Precision and recall on the held-out set.** Example: the held-out frames contain 100 objects; the detector found 90 of them and fired 10 more times on empty background. Precision = 90 / (90 + 10) = 0.90, recall = 90 / 100 = 0.90. Raising the confidence threshold usually raises precision and lowers recall.
- **Choose the threshold through the cost of an error.** If a false positive sends the aircraft after the wrong target while a miss only means another pass, pick a high-precision threshold even at the cost of recall. Record the curve over 5 thresholds and the chosen point with a one-sentence justification.
- **False positives by class:** glare, shadows, similar objects, motion blur. For each class: an example frame and a fix (data into training, a size or shape filter, a tracker with confirmation over several frames).
- **ArUco:** the marker id and corners are stable with a static camera. If the corners "jump", the marker is too small in the frame or the camera is not calibrated (the "Camera" module).

Self-check: the lab is done when the model runs on board with FPS measured with the camera per stage, precision/recall are computed on the held-out set (20 %, never used in training) the same way as in the example (90 / (90 + 10) = 0.90 and 90 / 100 = 0.90), the curve is taken over 5 thresholds, the threshold is chosen and justified by the cost of an error, and the false positives are classified with a fix for each class.

## diagnostics
- **Symptom:** 30 fps from a file, 8 fps from the camera
  - Possible cause: capture/conversion on the CPU, frame copies.
  - What to do: profile the stages, preprocess in hardware, lower the resolution.
- **Symptom:** mAP 0.9 on validation, blind in the field
  - Possible cause: the validation set comes from the same distribution as the training set; the field is different.
  - What to do: held-out frames from other conditions, collect more data.
- **Symptom:** false positives on shadows/glare
  - Possible cause: too few negative examples.
  - What to do: add "empty" frames with shadows to training, temporal filtering.
- **Symptom:** accuracy dropped sharply after INT8
  - Possible cause: poor quantization calibration.
  - What to do: a calibration set from your own data, FP16 as a compromise.
- **Symptom:** the object ID keeps changing
  - Possible cause: no tracker or weak association.
  - What to do: ByteTrack, detection on every frame for tests.

## references
- OpenCV — ArUco marker detection tutorial | https://docs.opencv.org/4.x/d5/dae/tutorial_aruco_detection.html | primary | A
- NVIDIA — TensorRT documentation | https://docs.nvidia.com/deeplearning/tensorrt/latest/index.html | primary | A
- ArduPilot — Precision Landing (companion with AprilTag/IR-LOCK) | https://ardupilot.org/copter/docs/precision-landing-with-irlock.html | primary | A

## checklist
- I know when classical methods (markers, color) are enough and when a network is needed
- I fine-tuned a nano model on my own data and exported it
- The model runs on board with acceleration, FPS measured from the camera
- Precision/recall per condition, threshold chosen by the cost of an FP
- FPs classified, a tracker smooths the detections
