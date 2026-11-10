---
id: per-depth-avoid
title: "Depth and obstacle avoidance: sensors, OBSTACLE_DISTANCE, algorithms"
level: L4
readingTime: 45 min
firmware: ArduPilot · PX4 · companion
status: published
added: 2026-11-08
tags:
  - obstacle avoidance
  - stereo camera
  - lidar
  - OBSTACLE_DISTANCE
  - BendyRuler
related:
  - per-geometry
  - per-landing
  - ros2-nav
  - ap-missions
next:
  - per-mapping
source: content/companion/per-depth-avoid.md
source_hash: 19806270c373
---

## summary
Obstacle avoidance isn't a single feature but a chain with honest limitations at every link: the sensor doesn't see everything or everywhere, data arrives with a delay, the vehicle doesn't brake instantly, and the avoidance algorithm only works in some of the modes. This module covers depth sensors (stereo, ToF, lidar, radar) and their blind spots, turning a depth map into the 72 sectors of `OBSTACLE_DISTANCE`, the physics of braking — which gives you the maximum safe speed for a given sensor — and what the autopilots actually do: ArduPilot's simple avoidance (`AVOID_*`) in manual modes, the BendyRuler and Dijkstra planners (`OA_*`) in automatic ones, and Collision Prevention in PX4 (`CP_*`). Lab: a sector map from a depth map using `examples/perception/obstacles.py` and a SITL scenario where the vehicle has to stop in front of a wall at a given distance.

## theory
### Depth sensors and their honest limits
| Sensor | Range | Strengths | Where it goes blind |
|---|---|---|---|
| Stereo camera | 0.3–10 m (accuracy drops as Z²) | dense map, cheap | smooth single-color walls, darkness, glare, thin wires |
| ToF camera | 0.1–5 m | dense map, no texture needed | sunlight (IR washout), black surfaces |
| Single-beam lidar / rangefinder | up to 40–100+ m | precise, long range | only one direction |
| Spinning 2D lidar (360°) | 8–40 m | all-round view in a plane | everything above and below the plane: wires, branches |
| Radar | 30–100+ m | rain, fog, dust, night | low angular resolution, false reflections |

Two things you have to accept: (1) **almost nothing sees wires** — not stereo (no texture), not a 2D lidar (a thin target outside the plane), and radar sees only thick ones; (2) a forward sensor doesn't see what's to the side and behind, while the vehicle flies in every direction. So an avoidance system has to know where it is **not looking**, and must not treat “no data” as “clear”.

### OBSTACLE_DISTANCE: the common language
The `OBSTACLE_DISTANCE` message (ID 330) carries up to 72 distances in centimeters over equal sectors: `increment` (or `increment_f`) degrees per sector, `angle_offset` — the angle of the first sector, `frame` — usually `MAV_FRAME_BODY_FRD` (0° is forward, clockwise: 90° is right). Special values: `UINT16_MAX` (65535) — no data in this sector, `max_distance + 1` — nothing within range. The distinction is fundamental: the first means “I don't know”, the second means “I know it's clear”. For single sensors there's `DISTANCE_SENSOR` with an `orientation` field.

Depth map → sectors: each image column corresponds to the azimuth atan((u − c_x)/f_x); for each column you take the minimum depth within the working band of rows (excluding floor and sky), convert the depth along the optical axis into slant range (dividing by the cosine of the azimuth) and put it into its sector, keeping the minimum for each sector. Sectors outside the camera's field of view stay at 65535. This is what `depth_to_sectors()` in `examples/perception/obstacles.py` does.

{{diagram:sector-map|The OBSTACLE_DISTANCE sector map: 72 sectors of 5°, the camera fills only its own field of view; the rest is “no data”, not “clear”.}}

### Physics: how much room you need to stop
Stopping distance = distance covered during the delay + braking distance + margin:

d_stop = v·L + v²/(2a) + d_margin,

where L is the total delay (frame, processing, transmission, velocity loop — usually 0.2–0.5 s), a is the deceleration you can actually achieve (limited by the lean angle and the acceleration parameters: 2–5 m/s² for a multicopter). From this, the maximum safe speed for a sensor with range R is:

v_max = −a·L + √((a·L)² + 2a·(R − d_margin)).

Example: a stereo camera with a reliable range of 6 m, a 2 m margin, a = 3 m/s², L = 0.3 s → v_max ≈ 4.1 m/s. Fly faster and avoidance turns into hope. PX4 says outright that sensor range limits speed; in ArduPilot the same follows from `AVOID_ACCEL_MAX` and `AVOID_MARGIN`.

### ArduPilot: two levels
**Simple avoidance** — in pilot-controlled modes (Loiter, AltHold, etc.): the vehicle won't let you get closer to an obstacle than `AVOID_MARGIN` (m), either sliding along it (`AVOID_BEHAVE = 0`, Slide) or stopping (`AVOID_BEHAVE = 1`, Stop). Sources are enabled by `AVOID_ENABLE` bits: 0 — geofence, 1 — proximity sensors, 2 — beacons. In non-GPS modes `AVOID_DIST_MAX` applies — the distance at which the push-back begins. There's an acceleration limit `AVOID_ACCEL_MAX` and back-away parameters (`AVOID_BACKUP_SPD`).

**Path planners (object avoidance, `OA_*`)** — in automatic modes (Auto, Guided, RTL): the vehicle changes its own trajectory. `OA_TYPE`: 1 — BendyRuler, 2 — Dijkstra, 3 — Dijkstra with BendyRuler.
- **BendyRuler** — local: it “probes” directions around the course out to `OA_BR_LOOKAHEAD` and picks the one closest to the target where the clearance is greater than `OA_MARGIN_MAX`. It works with proximity sensors (through the obstacle database `OA_DB_*`) and the geofence. Fast, but it can get stuck in a “pocket”.
- **Dijkstra** — global over a known map: it builds a path around a **polygon geofence** (inclusion and exclusion zones), keeping a margin of `OA_MARGIN_MAX`. It doesn't use sensors — it's for no-go zones known in advance.
- **Dijkstra + BendyRuler** — a global path around geofences plus local avoidance of whatever shows up in flight.

The data source is `PRX1_TYPE` (2 — MAVLink, in which case the companion sends `OBSTACLE_DISTANCE` or `DISTANCE_SENSOR`; there are also direct lidar drivers), with `PRX1_ORIENT` and `PRX1_YAW_CORR` for the mounting.

### PX4: Collision Prevention
Works on multicopters in Position mode (some versions require a specific value of `MPC_POS_MODE` — check the documentation for your version). Data: `OBSTACLE_DISTANCE` from the companion, rangefinders over MAVLink or connected to the controller; the data is merged into sectors around the vehicle, and where they overlap the minimum distance is taken. Behavior: speed is reduced on approach and goes to zero at the minimum distance.
- `CP_DIST` — the minimum distance (a negative value means disabled). It's measured to the **sensor**, not to the prop tips — add half the span.
- `CP_DELAY` — the delay from sensor data to the velocity response; it's taken into account when braking.
- `CP_GUIDE_ANG` — how many degrees to each side the vehicle may deflect the commanded direction if it's clearer there.
- `CP_GO_NO_DATA` — 0 (default): **you can't move in directions with no data**; 1 — you can. That's the right philosophy: without a rear sensor you don't fly backward.

### Where avoidance is actually useful
Autopilot obstacle avoidance is reliable for **slow** flight in a known environment: inspection near a structure, flying near trees at 2–3 m/s, preventing “the pilot didn't notice the wall in Loiter”. It doesn't turn the vehicle into an autonomous machine for a forest at 10 m/s: for that you need a 3D map, planning (the ROS 2 navigation module) and sensors that see wires. An honest wording for the spec: “prevents collisions with large obstacles in the sensor's field of view at speeds up to v_max”.

## practice
### Step 1. The sector map
Take a depth map: one you recorded from a depth camera in Gazebo (`examples/ros2-docker`, the depth image topic → numpy), a frame from an open RGB-D dataset, or a synthetic one — a numpy array with a “wall” and a “pole” (as in `tests/test_perception.py`). Build the 72 sectors with `depth_to_sectors()`, draw a polar plot, mark the “no data” sectors. Check: a wall to the right of the frame center gives a sector with an azimuth of 5–40°, and the 180° sector (behind) is 65535, not “clear”.

### Step 2. The speed budget
For your sensor (the datasheet range multiplied by 0.7 — the real one), a 2 m margin and the measured delay, compute v_max with the `max_safe_speed()` function. Then find what delay cuts v_max in half. Write down the conclusion: which pays off more to improve — range or delay.

### Step 3. SITL: stop in front of a wall
ArduPilot SITL: `PRX1_TYPE = 10` (the built-in SITL proximity sensor) or `PRX1_TYPE = 2` with your own `OBSTACLE_DISTANCE` sender (a wall 15 m to the north, expressed as sectors from the current position and heading); `AVOID_ENABLE` with bit 1, `AVOID_MARGIN = 3`. In Loiter, give full forward stick — the vehicle should stop at ~3 m. Check `AVOID_BEHAVE` 0 and 1. Then in Auto with `OA_TYPE = 1`, put a waypoint behind the “wall” — watch how BendyRuler goes around it, and at what `OA_BR_LOOKAHEAD` it starts getting stuck.

The lab counts as done when you have the polar plot of the sectors, the speed budget calculation, and SITL logs with a stop in front of the obstacle in Loiter and avoidance in Auto.

## diagnostics
- **Symptom:** the vehicle doesn't react to an obstacle even though the companion is sending data
  - Possible cause: `PRX1_TYPE` isn't 2, wrong `frame` or `angle_offset`, rate < 5 Hz, sysid mismatch.
  - What to do: check `PRX` in the log and the Proximity tab in Mission Planner — are the sectors visible.
- **Symptom:** the vehicle is “afraid” of a direction where there's nothing
  - Possible cause: 0 or a garbage value in the sector instead of 65535; reflections from the frame and landing legs.
  - What to do: 65535 for “no data”, mask out your own airframe, `min_distance`.
- **Symptom:** avoidance works in Loiter but not in a mission
  - Possible cause: `OA_TYPE = 0`, or Dijkstra selected without a polygon geofence.
  - What to do: BendyRuler for sensors; Dijkstra — only for geofences.
- **Symptom:** in PX4 the vehicle won't fly backward or sideways
  - Possible cause: no data in those sectors with `CP_GO_NO_DATA = 0` — that's by design.
  - What to do: add sensors or deliberately allow movement without data.
- **Symptom:** it stops too late
  - Possible cause: the delay was underestimated, v_max for the sensor range was exceeded.
  - What to do: measure the delay, limit the speed in the mode, increase the margin.

## references
- MAVLink — OBSTACLE_DISTANCE | https://mavlink.io/en/messages/common.html#OBSTACLE_DISTANCE | primary | A
- ArduPilot — Object Avoidance (landing page) | https://ardupilot.org/copter/docs/common-object-avoidance-landing-page.html | primary | A
- ArduPilot — BendyRuler | https://ardupilot.org/copter/docs/common-oa-bendyruler.html | primary | A
- ArduPilot — AC_Avoidance source (AVOID_*, OA_*) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/AC_Avoidance | primary | A
- PX4 — Collision Prevention | https://docs.px4.io/main/en/computer_vision/collision_prevention | primary | A

## checklist
- I know the limits of each type of depth sensor, especially for wires
- I can tell “no data” from “clear” in OBSTACLE_DISTANCE
- I can build a sector map from a depth map
- I can compute the stopping distance and the maximum safe speed
- I understand the difference between simple avoidance, BendyRuler and Dijkstra and where each one works
- I can set up CP_* in PX4 and understand the policy for moving without data
