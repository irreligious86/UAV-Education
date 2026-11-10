---
id: per-mapping
title: "Mapping: survey, georeferencing, photogrammetry"
level: L3
readingTime: 40 min
firmware: ArduPilot · PX4 · companion
status: published
added: 2026-11-08
tags:
  - photogrammetry
  - GSD
  - overlap
  - OpenDroneMap
  - georeferencing
related:
  - per-geometry
  - ap-missions
  - est-gnss
  - per-visual-nav
next:
  - per-edge-ml
source: content/companion/per-mapping.md
source_hash: c743ebc96ce5
---

## summary
An orthomosaic and an elevation model are the most widespread “civilian” product of a drone, and also a place where quality is decided before takeoff. This module walks through the whole pipeline: the requirement for the result (centimeters per pixel, accuracy) → calculating altitude, overlaps and speed → a mission with distance-based triggering (`CAM1_TRIGG_DIST`, `DO_SET_CAM_TRIGG_DIST`) → georeferencing frames from the log (`TRIG` versus `CAM`) → processing in OpenDroneMap → accuracy assessment against checkpoints. The lab is the full cycle on an open dataset plus planning your own survey mission and checking it in SITL.

## theory
### Start with the requirement
The client doesn't need a “flyover” but a product with measurable properties:
- **GSD** (ground sample distance): how many centimeters of ground fit in one pixel. For cadastral work 2–3 cm, for agricultural monitoring 5–10 cm, for an overview map 10–20 cm.
- **Accuracy**: relative (dimensions within the map) and absolute (coordinates versus reality). The first is determined by the survey geometry, the second by georeferencing (vehicle GNSS, RTK/PPK, ground control points).
- **Product**: orthophoto (GeoTIFF), DSM/DTM (surface/terrain model), point cloud, 3D model.

### GSD and altitude
GSD = H · w_sensor / (f · W_px). A 1" class camera (sensor width 13.2 mm, focal length 8.8 mm, 5472 px) at 100 m gives 2.74 cm/px; to get 2 cm/px you need 73 m. The same formula via FOV: footprint width = 2H·tan(HFOV/2), GSD = footprint / W_px. A 1280 px FPV camera with a 120° HFOV at 100 m gives 27 cm/px: for mapping it's practically useless, and not because it's “bad,” but because of its field of view and resolution.

Terrain changes GSD: over a 30 m hill, flying at 100 m above the takeoff point, the GSD at the summit is 30 % better, and the overlap is worse. For significant terrain the mission is built to follow the terrain (terrain following on a DEM, `TERRAIN_ENABLE` and altitudes in the Terrain frame).

### Overlap
Photogrammetry finds the same point in several frames and reconstructs its 3D position from different viewpoints (structure from motion). Hence the requirement: every ground point should appear in 5–9 frames. Typical values: forward overlap (along the survey line) 75–80 %, side overlap (between lines) 65–70 %; forest, a field with uniform texture, water need 85/75 % and more, because there are few reliable points there.

Calculation: distance between shots = footprint_along · (1 − forward_overlap); distance between lines = footprint_across · (1 − side_overlap). At 100 m with an HFOV of 84° and a VFOV of 62°: footprint 180 × 120 m; at 80/70, a shot every 24 m and lines 54 m apart. Camera orientation: long side of the frame across the survey line means fewer lines.

{{diagram:survey-overlap|Survey geometry: the frame footprint; forward overlap sets the trigger spacing, side overlap sets the distance between survey lines.}}

### Speed, shutter speed, interval
- **Motion blur**: during the exposure the vehicle must not move more than ~0.5 GSD. At 10 m/s and a 1/1000 s shutter the shift is 1 cm, which is borderline for a 2 cm GSD. Hence a fast shutter (1/1000 and faster) and a flight speed tied to the GSD.
- **Minimum camera interval**: if the camera needs 1.5 s to write a frame and the trigger spacing is 24 m, the speed must not exceed 16 m/s. The `CAM1_INTRVAL_MIN` parameter won't let you shoot faster than the camera can keep up; the trigger is then postponed until the interval expires (the frame is taken later, the spacing grows), and the vehicle does not slow down.
- **Wind**: survey lines across the wind give a smaller difference in ground speed between the outbound and return legs.
- A **rolling shutter** at speed distorts the geometry; ODM can compensate for it (the `--rolling-shutter` option), but a global shutter is better.

### Distance-based triggering in ArduPilot
Camera: `CAM1_TYPE` (1: servo, 2: relay, 5/6: MAVLink cameras, 4: gimbals with a built-in camera). Distance-based triggering: `CAM1_TRIGG_DIST` (m) in the parameters or, better, the mission command `DO_SET_CAM_TRIGG_DIST` at the start of the survey segment and with zero at its end, so you don't shoot the turns and the transit to the polygon. `CAM_AUTO_ONLY`: shoot only in Auto. `CAM_MAX_ROLL`: don't shoot when the roll exceeds the given value (frames in a turn are oblique).

Two messages in the log, and the difference between them is fundamental:
- `TRIG`: the moment the autopilot **sent** the shutter command.
- `CAM`: the moment the shutter **actually** fired, if hot-shoe feedback is connected (`CAM1_FEEDBAK_PIN`, `CAM1_FEEDBAK_POL`).
Between them is the camera delay, tens to hundreds of milliseconds; at 10 m/s that's meters. Without feedback, the frame coordinates are an estimate.

### Georeferencing
Options in order of increasing accuracy:
1. **Vehicle GNSS in EXIF** (a camera with its own GPS, or writing coordinates from the log into EXIF by time): 2–5 m absolute error. The relative accuracy of the map can still be at the centimeter level.
2. **Coordinates from the `CAM` log** with shutter feedback + interpolation of the position to the moment of the frame: 1–3 m.
3. **RTK/PPK**: camera center coordinates accurate to 2–5 cm; PPK needs raw GNSS measurements recorded on board and at the base station.
4. **Ground control points (GCPs)**: 5–10 targets with RTK-measured coordinates, spread evenly over the area and across elevations. They give an absolute accuracy of 1–3 GSD regardless of the onboard GNSS. Another 3–5 **checkpoints** are left out of processing and serve for an honest assessment.

Matching frames to the log: by image number (`Img` in `CAM`/`TRIG`) and time. A typical error is a one-frame shift (the camera missed a trigger); you catch it by comparing the number of frames on the memory card with the number of log entries.

### Processing: OpenDroneMap
ODM (and its web front end WebODM) is an open pipeline: feature detection and matching → structure from motion (camera poses, sparse cloud) → dense cloud (multi-view stereo) → mesh and texture → DSM/DTM → orthophoto. Running it in Docker: `docker run -ti --rm -v $(pwd)/datasets:/datasets opendronemap/odm --project-path /datasets project`. Key options: `--orthophoto-resolution` (cm/px, no finer than the GSD), `--dsm`, `--dtm`, `--gcp` (ground control point file), `--feature-quality`, `--pc-quality`. The ODM report (`report.pdf`) contains the reprojection error, the number of matched points and the coverage; reading it is mandatory.

### Accuracy assessment
RMSE over the checkpoints: √(Σ (Δx² + Δy²)/n) for horizontal, separately for vertical. Rules: points used as GCPs are not included in the assessment; the vertical error is usually 1.5–3 times the horizontal one; you may claim an accuracy only based on checkpoints. The result of a good survey with GCPs is 1–2 GSD horizontally and 2–3 GSD vertically.

{{diagram:chart-gsd-altitude|GSD versus altitude for three cameras: 1" and 4/3 almost coincide, while a small 1/2.3" sensor at the same altitude gives a ~30 % larger pixel on the ground.}}

{{widget:gsd-calc}}

## practice
### Step 1. Open dataset
Download an open image dataset (ODM publishes test datasets at github.com/OpenDroneMap, for example `odm_data_aukerman`). Process it in ODM with the default parameters, then with `--orthophoto-resolution` equal to the dataset's GSD. Open the orthophoto and DSM in QGIS. Read the report: average number of matches, reprojection error, areas with low overlap.

### Step 2. Experiment
Remove every second image (simulating a forward overlap lower by ~half of the original) and process again. Compare: coverage, holes, reprojection error, accuracy against checkpoints if the dataset has them. State your conclusion in one sentence.

### Step 3. Your own mission
For your camera and a GSD requirement of 3 cm, use the functions `gsd_cm()`, `footprint_m()`, `survey_spacing()` from `examples/perception/camgeo.py` to calculate the altitude, trigger spacing and distance between lines at 80/70 overlap. Check the motion blur and camera interval limits and choose a speed. Build the polygon in Mission Planner (Survey Grid) or QGC and compare it with your calculation. Run the mission in SITL with `DO_SET_CAM_TRIGG_DIST`: the number of `TRIG` entries in the log should match the calculated number of shots, give or take the turns.

### Step 4 (optional). Linear inspection
For a linear asset (power line, pipeline), use the starter for project #6 `examples/inspection`: `plan.py` builds a parallel route that shoots only over the inspected segment, `geotag.py` matches photos to `CAM` entries by time (estimating the camera clock offset) and shows why matching by order breaks after the first missed trigger.

The lab counts as done when you have an orthophoto and DSM from the dataset with the report analyzed, the conclusion of the overlap experiment and a planned mission verified in SITL by the `TRIG` count.

## diagnostics
- **Symptom:** holes and “smeared” areas in the orthophoto
  - Possible cause: insufficient overlap or uniform texture (field, water, forest).
  - What to do: overlap of 85/75 and more, higher altitude, fly at a different time of day.
- **Symptom:** the map is shifted by several meters
  - Possible cause: georeferencing from the onboard GNSS only, without RTK/GCPs.
  - What to do: GCPs with RTK coordinates or PPK; assess against checkpoints.
- **Symptom:** the log has fewer shots than there are files on the card (or vice versa)
  - Possible cause: missed triggers, frames taken in turns, no feedback.
  - What to do: `CAM1_FEEDBAK_PIN`, `DO_SET_CAM_TRIGG_DIST` only on the survey lines, `CAM_MAX_ROLL`.
- **Symptom:** blurry frames on one direction of the survey lines
  - Possible cause: a tailwind increases ground speed, the shutter speed is too slow.
  - What to do: survey lines across the wind, a faster shutter, a lower speed.
- **Symptom:** an elevation model with “steps” along the survey lines
  - Possible cause: frame time and position out of sync, rolling shutter at speed.
  - What to do: coordinates from `CAM` with feedback, the rolling shutter option in ODM, a lower speed.

## references
- OpenDroneMap — documentation | https://docs.opendronemap.org/ | primary | A
- ArduPilot — Camera shutter configuration (CAM1_*) | https://ardupilot.org/copter/docs/common-camera-shutter-with-servo.html | primary | A
- ArduPilot — AP_Camera source (CAM1_TRIGG_DIST, feedback, CAM/TRIG logs) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/AP_Camera | primary | A
- MAVLink — MAV_CMD_DO_SET_CAM_TRIGG_DIST | https://mavlink.io/en/messages/common.html#MAV_CMD_DO_SET_CAM_TRIGG_DIST | primary | A
- QGIS — documentation | https://docs.qgis.org/latest/en/docs/ | secondary | A

## checklist
- I translate the client's requirement into GSD and accuracy
- I calculate altitude, trigger spacing and line spacing from the overlap
- I check the limits from motion blur, camera interval and wind
- I set up distance-based triggering and understand the difference between TRIG and CAM
- I choose the georeferencing method for the required accuracy and place GCPs and checkpoints
- I process a dataset in ODM and read the report
- I assess accuracy against checkpoints
