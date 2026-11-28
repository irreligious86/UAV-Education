---
id: per-mapping
title: "Mapping: survey, georeferencing, photogrammetry"
level: L3
readingTime: 40 min
firmware: ArduPilot 4.7 (checked against 4.7.3) · PX4 1.18 (checked against v1.18.0) · companion
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
source_hash: a5d7ecc5ccc9
---

## summary
An orthomosaic and an elevation model are the most widespread civilian drone product, and also a place where quality is decided before takeoff. This module walks the whole pipeline: the requirement for the result (centimeters per pixel, accuracy) → altitude, overlap and speed calculation → a mission with distance-based triggering (`CAM1_TRIGG_DIST`, `DO_SET_CAM_TRIGG_DIST`) → georeferencing the frames from the log (`TRIG` versus `CAM`) → processing in OpenDroneMap → accuracy assessment on check points. Lab: the full cycle on an open dataset and the calculation of your own survey mission, verified in SITL.

## theory
### Start with the requirement
The customer does not need "a flyover" but a product with measurable properties:
- **GSD** (ground sample distance): how many centimeters of ground one pixel covers. For a cadastre 2–3 cm, for agricultural monitoring 5–10 cm, for an overview map 10–20 cm.
- **Accuracy**: relative (dimensions within the map) and absolute (coordinates versus reality). The first is set by the survey geometry, the second by georeferencing (the vehicle GNSS, RTK/PPK, ground control points).
- **Product**: orthophoto (GeoTIFF), DSM/DTM (surface/terrain model), point cloud, 3D model.

### GSD and altitude
GSD = H · w_sensor / (f · W_px). A 1" class camera (13.2 mm sensor width, 8.8 mm focal length, 5472 px) gives 2.74 cm/px at 100 m; to get 2 cm/px you need 73 m. The same formula through the FOV: footprint width = 2H·tan(HFOV/2), GSD = footprint / W_px. A 1280 px FPV camera with a 120° HFOV at 100 m gives 27 cm/px: practically useless for a map, not because it is "bad" but because of the field of view and the resolution.

Terrain changes the GSD: over a 30 m hill, flying 100 m above the takeoff point, the GSD at the top is 30 % better and the overlap is worse. For noticeable relief the mission is built to follow the terrain (terrain following on a DEM, `TERRAIN_ENABLE` and altitudes in the Terrain frame).

### Overlap
Photogrammetry finds the same point in several frames and recovers its 3D position from the different viewpoints (structure from motion). Hence the requirement: every ground point in 5–9 frames. Typical values: frontal overlap (along the survey line) 75–80 %, side overlap (between lines) 65–70 %; for forest, uniformly textured fields and water 85/75 % and more, because there are few reliable points there.

Calculation: distance between shots = footprint_along · (1 − frontal_overlap); distance between lines = footprint_across · (1 − side_overlap). At 100 m with an HFOV of 84° and a VFOV of 62°: the footprint is 180 × 120 m; at 80/70, a shot every 24 m and lines 54 m apart. Camera orientation: the long side of the frame across the line means fewer lines.

{{diagram:survey-overlap|Survey geometry: the frame footprint, the frontal overlap sets the trigger distance, the side overlap sets the distance between lines.}}

### Speed, shutter, interval
- **Motion blur**: during the exposure the vehicle must not move more than ~0.5 GSD. At 10 m/s and 1/1000 s the shift is 1 cm, which is borderline for a 2 cm GSD. Hence a short exposure (1/1000 and shorter) and a flight speed tied to the GSD.
- **Minimum camera interval**: if the camera needs 1.5 s to write a frame and the trigger distance is 24 m, the speed must not exceed 16 m/s. The `CAM1_INTRVAL_MIN` parameter stops the autopilot from triggering faster than the camera can keep up: the shot is postponed until the interval has elapsed (the frame is taken later and the trigger distance grows), and the vehicle does not slow down.
- **Wind**: lines across the wind mean a smaller difference in ground speed between the two directions.
- **Rolling shutter** distorts the geometry at speed; ODM can compensate for it (the `--rolling-shutter` option), but a global shutter is better.

### Distance-based triggering in ArduPilot
Camera: `CAM1_TYPE` (1 Servo, 2 Relay, 5/6 MAVLink cameras, 4 gimbals with a built-in camera). Distance-based triggering: `CAM1_TRIGG_DIST` (m) in the parameters or, better, the mission command `DO_SET_CAM_TRIGG_DIST` at the start of the survey leg and with zero at the end, so that you do not shoot the turns and the transit to the area. `CAM_AUTO_ONLY`: trigger only in Auto. `CAM_MAX_ROLL`: do not trigger when the roll is larger than set (the frames in a turn are oblique).

Two messages in the log, and the difference between them is fundamental:
- Without feedback the log has only `CAM`, and that is the moment the autopilot **sent** the trigger.
- With feedback (`CAM1_FEEDBAK_PIN`, `CAM1_FEEDBAK_POL`) there are two records: `TRIG` is the trigger moment, `CAM` is the moment the shutter **actually** fired, from the hot shoe signal.
Between them is the camera latency, tens to hundreds of milliseconds; at 10 m/s that is meters. Without feedback the frame coordinates are an estimate. The ArduPilot camera parameters, commands and survey errors are covered in detail in `ap-payload`.

In PX4 the same is done by the `camera_trigger` driver (`TRIG_MODE`, `TRIG_DISTANCE`, `TRIG_INTERVAL`) and `camera_capture` (feedback), with the ULog records `camera_trigger` and `camera_capture`; the details are in `px4-camera-gimbal`. Note the difference: PX4 skips a trigger that comes too early, while ArduPilot postpones it.

### Georeferencing
The options, in order of increasing accuracy:
1. **Vehicle GNSS in EXIF** (a camera with its own GPS, or coordinates from the log written into EXIF by time): 2–5 m of absolute error. The relative accuracy of the map can still be at the centimeter level.
2. **Coordinates from the `CAM` log** with shutter feedback + the position interpolated to the frame time: 1–3 m.
3. **RTK/PPK**: camera center coordinates accurate to 2–5 cm; PPK needs raw GNSS observations recorded on board and on the base station.
4. **Ground control points (GCPs)**: 5–10 targets with RTK-measured coordinates, spread evenly over the area and over the elevations. They give an absolute accuracy of 1–3 GSD regardless of the onboard GNSS. Another 3–5 **check** points are not used in processing and serve for an honest assessment.

Matching frames to the log: by image number (`Img` in `CAM`/`TRIG`) and by time. A typical error is an offset of one frame (the camera missed a trigger); you catch it by comparing the number of frames on the memory card with the number of log records.

### Processing: OpenDroneMap
ODM (and its web front end WebODM) is an open pipeline: feature detection and matching → structure from motion (camera poses, sparse cloud) → dense cloud (multi-view stereo) → mesh and texture → DSM/DTM → orthophoto. Running it in Docker: `docker run -ti --rm -v $(pwd)/datasets:/datasets opendronemap/odm --project-path /datasets project`. Key options: `--orthophoto-resolution` (cm/px, no finer than the GSD), `--dsm`, `--dtm`, `--gcp` (the ground control point file), `--feature-quality`, `--pc-quality`. The ODM report (`report.pdf`) contains the reprojection error, the number of matched points and the coverage; reading it is mandatory.

### Accuracy assessment
RMSE over the check points: √(Σ (Δx² + Δy²)/n) for the horizontal error, and separately for the vertical. Rules: points used as GCPs are not included in the assessment; the vertical error is usually 1.5–3 times the horizontal one; you can state an accuracy only from check points. The result of a good survey with GCPs is 1–2 GSD horizontally and 2–3 GSD vertically.

{{diagram:chart-gsd-altitude|GSD versus altitude for three cameras: 1" and 4/3 almost coincide, while the small 1/2.3" sensor gives a ~30 % larger ground pixel at the same altitude.}}

{{widget:gsd-calc}}

### Where it fits in the system

- **Takes in:** the GSD and accuracy requirement; the camera parameters and footprint (`per-geometry`); distance-based triggering in the mission (`ap-missions`); GNSS, RTK or PPK coordinates (`est-gnss`, `nav-rtk`).
- **Hands off:** the altitude, trigger distance, line spacing and speed limit to the mission; frames with coordinates to OpenDroneMap; a georeferenced orthophoto as a reference map for frame matching (`nav-vtrn`).
- **If you get this wrong:** over a hill without terrain following, the height above ground is lower than planned → not enough overlap, holes in the map; you find out only back home, and the fix is in `nav-terrain`. Coordinates taken from `CAM` without shutter feedback (the moment the trigger was sent, not the shutter) → a shift of meters at 10 m/s, the absolute accuracy of the map drops; only the check points reveal it.

## practice
### Step 1. Open dataset
Download an open image dataset (ODM publishes test datasets on github.com/OpenDroneMap, for example `odm_data_aukerman`). Process it in ODM with the default settings, then with `--orthophoto-resolution` equal to the dataset GSD. Open the orthophoto and the DSM in QGIS. Read the report: the average number of matches, the reprojection error, areas with low overlap.

### Step 2. Experiment
Remove every second image (simulating twice the trigger distance: frontal overlap o → 2o − 1, for example 80 % → 60 %) and process again. Compare: coverage, holes, reprojection error, accuracy on the control points if the dataset has them. State the conclusion in one sentence.

### Step 3. Your own mission
For your camera and a 3 cm GSD requirement, compute the altitude, the trigger distance and the line spacing at 80/70 overlap with the `gsd_cm()`, `footprint_m()` and `survey_spacing()` functions from `examples/perception/camgeo.py`. Check the motion blur and camera interval limits and choose the speed. Build the polygon in Mission Planner (Survey Grid) or QGC and compare it with your calculation. Run the mission in SITL with `DO_SET_CAM_TRIGG_DIST`: the number of `CAM` records in the log (without feedback there is no `TRIG`) must match the calculated number of shots, give or take the turns.

### Step 4 (optional). Linear inspection
For a linear asset (a power line, a pipeline) use the project 6 starter `examples/inspection`: `plan.py` builds a parallel route that triggers only over the inspected section, `geotag.py` matches photos to the `CAM` records by time (estimating the camera clock offset) and shows why matching by order breaks after the first missed trigger.

Self-check: the lab is done when you have an orthophoto and a DSM from the dataset, with the reprojection error, the number of matched points and the coverage taken from the ODM report; the 80 % → 60 % overlap experiment gave a comparison of coverage, holes and reprojection error and a one-sentence conclusion; and the mission is calculated and checked: the functions were first run on the theory example (100 m, HFOV 84° and VFOV 62°: a 180 × 120 m footprint, at 80/70 a shot every 24 m and lines 54 m apart), the blur is no more than ~0.5 GSD, the speed is no higher than the trigger distance / camera interval, and the number of `CAM` records in the SITL log matched the calculated number of shots, give or take the turns.

## diagnostics
- **Symptom:** holes and "swimming" areas in the orthophoto
  - Possible cause: insufficient overlap or uniform texture (field, water, forest).
  - What to do: overlap of 85/75 and more, a higher altitude, a flight at a different time of day.
- **Symptom:** the map is shifted by several meters
  - Possible cause: georeferencing from the onboard GNSS only, without RTK/GCPs.
  - What to do: GCPs with RTK coordinates, or PPK; assess on check points.
- **Symptom:** the log has fewer shots than there are files on the card (or the other way round)
  - Possible cause: missed triggers, frames taken in turns, no feedback.
  - What to do: `CAM1_FEEDBAK_PIN`, `DO_SET_CAM_TRIGG_DIST` only on the survey lines, `CAM_MAX_ROLL`.
- **Symptom:** blurred frames on one direction of the lines
  - Possible cause: a tailwind increases the ground speed, the exposure is long.
  - What to do: lines across the wind, a shorter exposure, a lower speed.
- **Symptom:** an elevation model with "steps" along the lines
  - Possible cause: the frame time and the position are out of sync, rolling shutter at speed.
  - What to do: coordinates from `CAM` with feedback, the rolling shutter option in ODM, a lower speed.

## references
- OpenDroneMap — documentation | https://docs.opendronemap.org/ | primary | A
- ArduPilot — Camera shutter configuration (CAM1_*) | https://ardupilot.org/copter/docs/common-camera-shutter-with-servo.html | primary | A
- ArduPilot — AP_Camera source (CAM1_TRIGG_DIST, feedback, CAM/TRIG logs) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/AP_Camera | primary | A
- MAVLink — MAV_CMD_DO_SET_CAM_TRIGG_DIST | https://mavlink.io/en/messages/common.html#MAV_CMD_DO_SET_CAM_TRIGG_DIST | primary | A
- QGIS — documentation | https://docs.qgis.org/latest/en/docs/ | secondary | A

## checklist
- I turn the customer's requirement into a GSD and an accuracy
- I compute the altitude, the trigger distance and the line spacing from the overlap
- I check the limits from motion blur, the camera interval and wind
- I set up distance-based triggering and understand the difference between TRIG and CAM
- I choose a georeferencing method for the required accuracy and place GCPs and check points
- I process a dataset in ODM and read the report
- I assess accuracy on check points
