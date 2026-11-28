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
source_hash: 36e6881f1910
---

## summary
A model that gives 0.9 mAP and 60 frames per second on a laptop turns, on board, into 6 frames per second with throttling five minutes into the flight and silent degradation over snow. This module is about preventing that: a latency and energy budget derived from the task, not from the model; what quantization (FP16, INT8) is and what it costs; how to profile honestly (warm-up, percentiles, thermal behavior, the whole pipeline rather than just inference); how to evaluate a model on held-out data from **your own** conditions and pick a threshold for the cost of an error; and how to maintain a model across a fleet: versions, rollback, drift monitoring. Lab: profile the pipeline with `examples/perception/latency_bench.py` on your compute board and write a record with a verdict against the budget.

## theory
### A budget derived from the task
First what the task needs, then which model fits:
- **Latency**: tracking a target moving at 10 m/s needs ≤ 100–150 ms from frame to command (in 150 ms the target moves 1.5 m); for mapping and search, seconds are fine. Latency means p99, not the mean: one 500 ms frame in the middle of a maneuver is a lost target.
- **Rate**: a tracker between detections (the tracking module) lets you detect at 5–10 Hz and track at the camera rate.
- **Energy and heat**: a 10–15 W computer on a vehicle that uses 300 W to hover costs 3–5 % of the flight time; but in a closed enclosure with no airflow it will overheat and drop its clocks.
- **Mass**: a Jetson Orin Nano with a heatsink is 100–180 g; a Raspberry Pi 5 + an accelerator is 60–100 g.

A budget statement for a requirements spec: "detect class X with recall ≥ 0.9 at distances up to 50 m, p99 camera → bbox latency ≤ 80 ms, on computer Y at 35 °C, no throttling for 30 minutes".

### Where to compute
| Computer | What it accelerates | Typical path |
|---|---|---|
| CPU (Pi 5, x86) | nothing special | ONNX Runtime, OpenCV DNN, small models (YOLO-n at 320 px: from a few to about ten frames/s) |
| GPU (Jetson) | FP16/INT8 on CUDA and Tensor Cores | TensorRT from ONNX, several times faster than "raw" PyTorch |
| NPU/TPU (Hailo, Coral, built-in NPUs) | INT8 | vendor compiler, supported layers only |

The general rule: exporting to ONNX is the standard hand-off between the training framework and the inference engine. No engine supports every operator; an unsupported layer falls back to the CPU and eats the whole gain, and the profiler shows that right away.

### Quantization
Weights and activations are converted from FP32 to FP16 or INT8. INT8: a value x ≈ s·(q − z), where q is an 8-bit integer, s is the scale and z is the zero point, both chosen from the value range. The gain: 4 times less memory, 2–4 times the speed of FP32 on accelerators with integer units (NPU, Edge TPU, DSP), lower energy; on a Jetson GPU the gain over FP16 is modest or zero (figures in comp-jetson-nano). The cost: lost accuracy, typically 1–5 points of mAP50-95 with plain PTQ (YOLO26 on an Orin Nano Super: −1.8 to −4.7, comp-jetson-nano), more on small objects and in difficult conditions.
- **Post-training quantization (PTQ)**: the ranges are calibrated on 200–1000 **representative** frames. If you calibrate on daytime frames, the activation ranges at night are different, and accuracy drops more than it did in the test.
- **Quantization-aware training (QAT)**: quantization is simulated during fine-tuning; more accurate than PTQ, more expensive.
- FP16 on a GPU costs almost nothing in accuracy, so it is always the first step.

Check: the same held-out set before and after quantization, comparing metrics **per slice** (distance, lighting, background), not just the overall mAP.

### Profiling honestly
- **Warm-up**: the first 10–50 runs are slower (memory allocation, kernel compilation, clocks).
- **Percentiles**: p50, p95, p99, max. The mean hides the tails, and the tails break the control loop.
- **The whole pipeline**: frame capture → decoding → resize and normalization → inference → postprocessing (NMS) → tracker → sending the command. Inference can be half the time, not all of it.
- **Thermal behavior**: a 20–30 minute run inside the enclosure at a temperature close to the field one; log clocks and temperature (`tegrastats` on a Jetson, `vcgencmd measure_temp` and `get_throttled` on a Pi). If p99 after 20 minutes is twice as bad as in the first minute, the budget is not met.
- **Concurrent load**: video recording, MAVLink and ROS 2 run on board at the same time, so profile together with them.

{{diagram:edge-budget-verdict|The budget is met only if all three checks pass: p99 of the whole pipeline under load, 20–30 minutes in the enclosure without p99 doubling, and per-slice metrics after quantization.}}

### Evaluation: your own data and the cost of an error
A model trained on an open dataset sees the world "from eye level", while a drone camera looks from above, at an angle, at small objects with motion blur. So:
- **A held-out set from your own conditions**: frames from your vehicle, your camera, your altitudes and seasons that **did not take part** in training, split by flight (not by frame: neighboring frames of one flight are almost identical, and such a split inflates the metrics).
- **Slices**: metrics separately by distance, lighting, background. An overall mAP of 0.8 can hide a recall of 0.3 at distances > 50 m.
- **A threshold for the cost of an error**: in a search for a person a miss costs more than a false alarm, so a lower threshold, higher recall, and the operator checks the false alarms; for an automatic action on a target a false positive costs more, so a higher threshold plus confirmation over several frames and by the tracker.
- **Metrics the customer understands**: not only mAP but "93 of 100 people in the field found, 4 false alarms per minute".

### Maintaining a model across a fleet
A model is an artifact just like firmware and needs the same discipline:
- **Version** of the model, the training data and the thresholds: in the metadata and in the log of every flight (without it, incident analysis is impossible).
- **Rollback**: the previous verified version is kept on board; switching is done with a parameter, not by reflashing.
- **Acceptance of a new version**: a run on a fixed regression set with slices; worse on any critical slice means it does not ship.
- **Drift monitoring**: the confidence distribution, detections per minute of flight, the share of frames without detections, compared against a reference; a sharp change is a signal (a new season, a dirty lens, a different camera).
- **Collecting hard examples**: low-confidence frames and errors from the field go into the next labeling cycle. That is the MLOps loop on board.

{{diagram:edge-mlops|The on-board ML loop: field data → labeling → training → quantization and per-slice acceptance → rollout with a version and rollback → drift monitoring → data again.}}

### Where it fits in the system

- **Takes in:** the latency and recall requirement from the task (`per-tracking`); power, cooling and the power mode of the computer (`comp-jetson-nano`, `comp-raspberry`); frames from your own flights.
- **Hands off:** the p99 pipeline latency to the loop gain calculation (`per-tracking`); a quantized model with a version and a threshold (`per-cv`); the watts and grams of the computer to the vehicle budget (`des-sizing`).
- **If you get this wrong:** the profile was taken during the first minute on the bench → after 20 minutes in the enclosure throttling doubles p99 and the tracking loop loses the target (`per-tracking`). INT8 calibrated on daytime frames → at night accuracy drops more than in the test, and the overall mAP hides it; per-slice metrics are in `per-cv`.

## practice
### Step 1. Pipeline profile
On your computer (a Pi, a Jetson, or a laptop as the reference) run `latency_bench.py` with the toy workload, then replace it with your own model through `bench(fn, ...)`: ONNX Runtime or OpenCV DNN, YOLO-n at 320 and 640 px:

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
Run the pipeline for 20 minutes continuously, logging p99 per minute and the temperature/clocks. Then do the same in FP16 (GPU) or INT8 (PTQ on 300 frames from your own flights). Table: accuracy on the held-out set, p50/p99, temperature, energy (if you have a USB power meter).

### Step 3. Per-slice evaluation
Label 200 frames from your own flights (different altitudes and lighting), split by flight. Compute precision/recall for the slices "closer than 30 m / farther than 30 m" and "day / dusk". Pick a threshold for a specific task and justify it by the cost of an error.

Self-check: the lab is done when you have a pipeline profile with p50/p95/p99/max and the inference share, a 20-minute thermal run with p99 per minute (p99 in the twentieth minute twice as bad as in the first means the budget is not met), a before/after quantization table (the guideline from the theory: FP16 on a GPU costs almost nothing in accuracy, INT8 usually loses 1–5 points of mAP50-95; a loss well beyond that, or a collapse on one slice, means you should check which frames were used for calibration) and a per-slice evaluation with a threshold justified by the cost of an error; the verdict compares your p99 with the task budget (≤ 80 ms in the theory example).

## diagnostics
- **Symptom:** 30 frames/s on the bench, 12 in flight after 10 minutes
  - Possible cause: throttling in an enclosure without airflow.
  - What to do: prop wash or a fan, a heatsink, a temperature and clock log, the power mode.
- **Symptom:** after INT8 the model went "blind" at dusk
  - Possible cause: PTQ calibrated on daytime frames only.
  - What to do: a calibration set from all conditions; QAT; per-slice checks.
- **Symptom:** excellent test metrics, many misses in the field
  - Possible cause: a split by frame instead of by flight; a test set not from your own conditions.
  - What to do: a held-out set split by flight and condition, slices by distance.
- **Symptom:** rare 300–500 ms frames among 40 ms ones
  - Possible cause: the garbage collector, writes to the memory card, CPU contention, an unsupported layer running on the CPU.
  - What to do: the engine profiler, core isolation, recording in a separate thread, p99 in the budget.
- **Symptom:** after a model update the flight cannot be analyzed
  - Possible cause: the model and threshold versions are not written to the log.
  - What to do: the version in the metadata and in the log of every flight, keep the previous version for rollback.

## references
- ONNX Runtime — Performance tuning | https://onnxruntime.ai/docs/performance/ | primary | A
- ONNX Runtime — Quantize ONNX models | https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html | primary | A
- NVIDIA — TensorRT documentation | https://docs.nvidia.com/deeplearning/tensorrt/latest/index.html | primary | A
- Jacob et al. — Quantization and Training of Neural Networks for Efficient Integer-Arithmetic-Only Inference | https://arxiv.org/abs/1712.05877 | secondary | A
- Google — Rules of Machine Learning (M. Zinkevich) | https://developers.google.com/machine-learning/guides/rules-of-ml | secondary | A

## checklist
- I derive the latency, rate and energy budget from the task
- I choose the computer and the engine and understand the cost of unsupported layers
- I quantize a model and check accuracy per slice
- I profile honestly: warm-up, percentiles, the whole pipeline, thermal behavior
- I evaluate on my own held-out data split by flight
- I pick the threshold for the cost of an error
- I keep versions, rollback and drift monitoring for the model across the fleet
