---
id: per-edge-ml
title: "ML on board: budget, quantization, evaluation, maintenance"
level: L4
readingTime: 40 min
firmware: companion
status: published
added: 2026-11-08
tags:
  - edge ML
  - quantization
  - profiling
  - ONNX
  - MLOps
related:
  - per-cv
  - per-tracking
  - px4-companion-jetson
  - comp-raspberry
next:
  - per-tracking
source: content/companion/per-edge-ml.md
source_hash: 9c6107ba94d6
---

## summary
A model that gives 0.9 mAP and 60 frames per second on a laptop turns into 6 frames with throttling five minutes into the flight on board, plus silent degradation over snow. This module is about how not to let that happen: a latency and energy budget derived from the task, not from the model; what quantization (FP16, INT8) is and what it costs you; how to profile honestly (warm-up, percentiles, thermal behavior, the whole pipeline, not just inference); how to evaluate the model on held-out data from **your own** conditions and pick a threshold for the cost of an error; and how to maintain a model across a fleet — versions, rollback, drift monitoring. Lab: profiling the pipeline with the `examples/perception/latency_bench.py` tool on your compute module and a report with a verdict against the budget.

## theory
### A budget from the task
First what the task needs, then which model fits:
- **Latency**: tracking a target at 10 m/s requires ≤ 100–150 ms from frame to command (in 150 ms the target moves 1.5 m); for mapping and search, seconds are no problem. Latency means p99, not the average: a single 500 ms frame in the middle of a maneuver is a lost target.
- **Rate**: a tracker between detections (see the tracking module) lets you detect at 5–10 Hz and track at the camera rate.
- **Energy and heat**: a 10–15 W compute module on a vehicle that uses 300 W to hover costs 3–5 % of flight time; but in a closed enclosure with no airflow it will overheat and drop its clocks.
- **Mass**: a Jetson Orin Nano with a heatsink is 100–180 g; a Raspberry Pi 5 + an accelerator is 60–100 g.

A budget statement for the spec: “detection of class X with recall ≥ 0.9 at distances up to 50 m, p99 latency camera → bbox ≤ 80 ms, on compute module Y at 35 °C, with no throttling for 30 minutes”.

### Where to compute
| Compute | What it accelerates | Typical path |
|---|---|---|
| CPU (Pi 5, x86) | nothing special | ONNX Runtime, OpenCV DNN, small models (YOLO-n at 320 px — a few to ten frames/s) |
| GPU (Jetson) | FP16/INT8 on CUDA and tensor cores | TensorRT from ONNX — many times faster than “raw” PyTorch |
| NPU/TPU (Hailo, Coral, built-in NPUs) | INT8 | its own compiler, supported layers only |

General rule: exporting to ONNX is the standard bridge between the training framework and the execution engine. No engine supports every operation; an unsupported layer falls back to the CPU and eats the whole gain — the profiler shows this right away.

### Quantization
Weights and activations are converted from FP32 to FP16 or INT8. INT8: a value x ≈ s·(q − z), where q is an 8-bit integer, s is the scale and z is the zero point, chosen from the range. The gain: 4 times less memory, 2–4 times higher speed on accelerators with integer units, lower energy. The cost: an accuracy loss, usually 0.5–2 mAP points, but more on small objects and in difficult conditions.
- **Post-training quantization (PTQ)**: range calibration on 200–1000 **representative** frames. If you calibrate on daytime frames, the activation ranges at night are different — and accuracy drops more than it did in testing.
- **Quantization-aware training (QAT)**: simulating quantization during fine-tuning; more accurate than PTQ, more expensive.
- FP16 on a GPU is almost free in terms of accuracy — it's always the first step.

Verification: the same held-out set before and after quantization, comparing metrics **by slice** (distance, lighting, background), not just the overall mAP.

### Profiling honestly
- **Warm-up**: the first 10–50 runs are slower (memory allocation, kernel compilation, clocks).
- **Percentiles**: p50, p95, p99, max. The average hides the tails; the tails break the control loop.
- **The whole pipeline**: frame capture → decoding → resize and normalization → inference → postprocessing (NMS) → tracker → sending the command. Inference is sometimes half the time, not all of it.
- **Thermal behavior**: a 20–30 minute run inside the enclosure, at a temperature close to field conditions; log clocks and temperature (`tegrastats` on a Jetson, `vcgencmd measure_temp` and `get_throttled` on a Pi). If p99 after 20 minutes is twice as bad as in the first minute, the budget isn't met.
- **Concurrent load**: on board, video recording, MAVLink and ROS 2 all run at the same time — profile together with them.

### Evaluation: your own data and the cost of an error
A model trained on an open dataset sees the world “from eye level”, while a drone camera looks from above, at an angle, with small objects and motion blur. Therefore:
- **A held-out set from your own conditions**: frames from your vehicle, your camera, your altitudes and seasons that **did not take part** in training, split by flight (not by frame — neighboring frames from one flight are nearly identical, and such a split inflates the metrics).
- **Slices**: metrics separately by distance, lighting, background. An overall mAP of 0.8 can hide a recall of 0.3 at distances > 50 m.
- **A threshold for the cost of an error**: in a search for a person, a miss costs more than a false alarm — lower threshold, higher recall, the operator checks the false alarms; in an automatic action on a target, a false positive costs more — higher threshold, plus confirmation over several frames and by the tracker.
- **Metrics the customer understands**: not just mAP, but “out of 100 people in the field, 93 were found, 4 false alarms per minute”.

### Maintenance across a fleet
A model is an artifact just like firmware and needs the same discipline:
- **The version** of the model, the training data and the thresholds — in the metadata and in the log of every flight (without this, investigating an incident is impossible).
- **Rollback**: the previous verified version is stored on board; switching is done with a parameter, not by reflashing.
- **Acceptance of a new version**: a run on a fixed regression set with slices; worse on any critical slice — it doesn't get rolled out.
- **Drift monitoring**: the confidence distribution, the number of detections per minute of flight, the share of frames without detections — compare them against a baseline; a sharp change is a signal (a new season, a dirty lens, a different camera).
- **Collecting hard examples**: frames with low confidence and errors from the field go into the next labeling cycle. That is the MLOps loop on board.

{{diagram:edge-mlops|The onboard ML loop: field data → labeling → training → quantization and acceptance by slice → rollout with a version and rollback → drift monitoring → data again.}}

## practice
### Step 1. Pipeline profile
On your compute module (a Pi, a Jetson, or a laptop as a reference), run `latency_bench.py` with the toy load, then replace it with your own model via `bench(fn, ...)` — ONNX Runtime or OpenCV DNN, YOLO-n at 320 and 640 px:

```python
import numpy as np, onnxruntime as ort
import latency_bench as lb   # examples/perception

sess = ort.InferenceSession("yolo_n_320.onnx", providers=["CPUExecutionProvider"])
name = sess.get_inputs()[0].name
img = np.random.rand(1, 3, 320, 320).astype(np.float32)
r = lb.summarize(lb.bench(lambda x: sess.run(None, {name: x}), img, runs=300), budget_ms=80)
print(r)
```
Then measure the whole pipeline on a video file: decoding + preprocessing + inference + NMS. Compare the share taken by inference.

### Step 2. Heat and quantization
Run the pipeline continuously for 20 minutes, logging p99 per minute and temperature/clocks. Then the same in FP16 (GPU) or INT8 (PTQ on 300 frames from your own flights). A table: accuracy on the held-out set, p50/p99, temperature, energy (if you have a USB wattmeter).

### Step 3. Evaluation by slice
Label 200 frames from your own flights (different altitudes and lighting), split by flight. Compute precision/recall for the slices “closer than 30 m / farther than 30 m” and “day / dusk”. Choose a threshold for a specific task and justify it by the cost of an error.

The lab counts as done when you have a pipeline profile with percentiles, a 20-minute thermal run, a before/after quantization table and an evaluation by slice with a justified threshold.

## diagnostics
- **Symptom:** 30 frames/s on the bench, 12 after 10 minutes in flight
  - Possible cause: throttling in an enclosure without airflow.
  - What to do: airflow from the props or a fan, a heatsink, a temperature and clock log, the power mode.
- **Symptom:** after INT8 the model “went blind” at dusk
  - Possible cause: PTQ calibration on daytime frames only.
  - What to do: a calibration set covering all conditions; QAT; a check by slice.
- **Symptom:** excellent test metrics, lots of misses in the field
  - Possible cause: a split by frame instead of by flight; the test isn't from your own conditions.
  - What to do: a held-out set split by flight and conditions, slices by distance.
- **Symptom:** occasional 300–500 ms frames among 40 ms ones
  - Possible cause: the garbage collector, writes to the memory card, CPU contention, an unsupported layer on the CPU.
  - What to do: the engine profiler, core isolation, writing in a separate thread, p99 in the budget.
- **Symptom:** after a model update, investigating a flight is impossible
  - Possible cause: the model and threshold version isn't written to the log.
  - What to do: the version in the metadata and in the log of every flight, keep the previous version for rollback.

## references
- ONNX Runtime — Performance tuning | https://onnxruntime.ai/docs/performance/ | primary | A
- ONNX Runtime — Quantize ONNX models | https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html | primary | A
- NVIDIA — TensorRT documentation | https://docs.nvidia.com/deeplearning/tensorrt/latest/index.html | primary | A
- Jacob et al. — Quantization and Training of Neural Networks for Efficient Integer-Arithmetic-Only Inference | https://arxiv.org/abs/1712.05877 | secondary | A
- Google — Rules of Machine Learning (M. Zinkevich) | https://developers.google.com/machine-learning/guides/rules-of-ml | secondary | A

## checklist
- I derive the latency, rate and energy budget from the task
- I choose the compute module and engine and understand the cost of unsupported layers
- I quantize a model and check its accuracy by slice
- I profile honestly: warm-up, percentiles, the whole pipeline, thermal behavior
- I evaluate on my own held-out data split by flight
- I choose a threshold for the cost of an error
- I maintain model versions, rollback and drift monitoring across the fleet
