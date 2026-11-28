---
id: per-depth-avoid
title: "Depth and obstacle avoidance: sensors, OBSTACLE_DISTANCE, algorithms"
level: L4
readingTime: 45 min
firmware: ArduPilot 4.7 (checked against 4.7.3) · PX4 1.18 (checked against v1.18.0) · companion
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
source_hash: 3d2e9780cff1
---

## summary
Obstacle avoidance is not a single feature but a chain with honest limits at every link: the sensor does not see everything everywhere, the data arrives late, the vehicle does not stop instantly, and the avoidance algorithm runs only in some modes. This module covers depth sensors (stereo, ToF, lidar, radar) and their blind spots, turning a depth image into the 72 sectors of `OBSTACLE_DISTANCE`, the physics of braking (which gives the maximum safe speed for a given sensor), and what the autopilots actually do: ArduPilot simple avoidance (`AVOID_*`) in pilot-controlled modes, the BendyRuler and Dijkstra path planners (`OA_*`) in automatic modes, and Collision Prevention in PX4 (`CP_*`). Lab: a sector map from a depth image with `examples/perception/obstacles.py`, and a SITL scenario where the vehicle must stop in front of a wall at a set distance.

## theory
### Depth sensors and their honest limits
| Sensor | Range | Strengths | Where it goes blind |
|---|---|---|---|
| Stereo camera | 0.3–10 m (accuracy falls as Z²) | dense map, cheap | smooth uniform walls, darkness, glare, thin wires |
| ToF camera | 0.1–5 m | dense map, no texture needed | sunlight (IR washout), black surfaces |
| Single-beam lidar / rangefinder | up to 40–100+ m | accurate, long range | one direction only |
| Spinning 2D lidar (360°) | 8–40 m | all-round view in a plane | everything above and below the plane: wires, branches |
| Radar | 30–100+ m | rain, fog, dust, night | low angular resolution, false reflections |

Two things you have to accept: (1) **almost nothing sees wires**: not stereo (no texture), not a 2D lidar (a thin target outside the scan plane), and radar only sees thick ones; (2) a forward sensor does not see what is to the side or behind, while the vehicle flies in every direction. So the avoidance system has to know where it is **not looking** and must not treat "no data" as "clear".

### OBSTACLE_DISTANCE: the common language
The `OBSTACLE_DISTANCE` message (ID 330) carries up to 72 distances in centimeters over equal sectors: `increment` (or `increment_f`) degrees per sector, `angle_offset` is the angle of the first sector, `frame` is usually `MAV_FRAME_BODY_FRD` (0° is forward, clockwise: 90° is right). Special values: `UINT16_MAX` (65535) means unknown/not used for that sector, `max_distance + 1` means no obstacle is present within range. The difference is fundamental: the first means "I don't know", the second means "I know it is clear". For single sensors there is `DISTANCE_SENSOR` with its `orientation` field.

Depth image → sectors: every image column has a bearing atan((u − c_x)/f_x); for each column take the minimum depth in the working band of rows (no floor, no sky), convert the depth along the optical axis into slant range (divide by the cosine of the bearing) and put it into its sector, keeping the minimum per sector. Sectors outside the camera field of view stay at 65535. That is what `depth_to_sectors()` in `examples/perception/obstacles.py` does.

{{diagram:sector-map|The OBSTACLE_DISTANCE sector map: 72 sectors of 5°, the camera fills only its own field-of-view sector; the rest is "no data", not "clear".}}

### Physics: how much distance you need to stop
Stopping distance = distance traveled during the latency + braking distance + margin:

d_stop = v·L + v²/(2a) + d_margin,

where L is the total latency (frame, processing, transmission, velocity loop; usually 0.2–0.5 s) and a is the deceleration actually achievable (limited by the lean angle and the acceleration parameters: 2–5 m/s² for a multicopter). This gives the maximum safe speed for a sensor with range R:

v_max = −a·L + √((a·L)² + 2a·(R − d_margin)).

Example: a stereo camera with a reliable range of 6 m, a 2 m margin, a = 3 m/s², L = 0.3 s → v_max ≈ 4.1 m/s. Fly faster and avoidance turns into hope. PX4 states it plainly: collision prevention may restrict the maximum speed if the sensor range is not large enough; in ArduPilot the same follows from `AVOID_ACCEL_MAX` and `AVOID_MARGIN`.

{{diagram:chart-avoid-stop-distance|v_max is where the stopping distance reaches the sensor range: with 6 m and a 2 m margin, a 0.3 s latency lowers the limit from 4.9 to 4.1 m/s, and 0.5 s lowers it to 3.6 m/s.}}

### ArduPilot: two levels
**Simple avoidance** works in pilot-controlled modes (Loiter, PosHold and others; AltHold has a caveat at the end of this paragraph): the vehicle will not let itself get closer to an obstacle than `AVOID_MARGIN` (m), either sliding along it (`AVOID_BEHAVE = 0`, Slide) or stopping (`AVOID_BEHAVE = 1`, Stop). The sources are enabled by the bits of `AVOID_ENABLE`: 0 UseFence, 1 UseProximitySensor, 2 UseBeaconFence. In non-GPS modes (AltHold) the push-back is done by leaning: `AVOID_DIST_MAX` is the distance at which it starts, `AVOID_ANG_MAX` is the maximum lean angle (degrees; before ArduPilot 4.7 it was `AVOID_ANGLE_MAX` in centidegrees). Since 4.7 this part is left out of standard Copter builds: there is no avoidance in AltHold unless the firmware is built on the custom build server with that option; in Loiter and the other position modes everything works as before. There is an acceleration limit `AVOID_ACCEL_MAX` and back-away parameters (`AVOID_BACKUP_SPD`).

**Path planners (object avoidance, `OA_*`)** work in automatic modes (Auto, Guided, RTL): the vehicle changes its own path. `OA_TYPE`: 1 BendyRuler, 2 Dijkstra, 3 Dijkstra with BendyRuler.
- **BendyRuler** is local: it probes the bearings around the course out to `OA_BR_LOOKAHEAD` and picks the one closest to the destination whose clearance is larger than `OA_MARGIN_MAX`. It works with proximity sensors (through the obstacle database `OA_DB_*`) and with the fence. Fast, but it can get stuck in a "pocket".
- **Dijkstra** is global over a known map: it builds a path around the **polygon fence** (inclusion and exclusion zones), keeping the `OA_MARGIN_MAX` margin. It does not use sensors; it is meant for no-go zones known in advance.
- **Dijkstra with BendyRuler** combines a global path over the fences with local avoidance of whatever appears in flight.

The data source is `PRX1_TYPE` (2 MAVLink, in which case the companion sends `OBSTACLE_DISTANCE` or `DISTANCE_SENSOR`; there are also direct lidar drivers), with `PRX1_ORIENT` and `PRX1_YAW_CORR` for the mounting.

### PX4: Collision Prevention
It works on multicopters in Position mode (in PX4 1.18 only with `MPC_POS_MODE` = Acceleration based, which is the default). The data comes from `OBSTACLE_DISTANCE` sent by a companion, from rangefinders over MAVLink or from rangefinders on the flight controller; the data from all sensors is fused into 72 sectors around the vehicle, each holding the distance and when it was last observed, or a "no data" marker. Behavior: the velocity is reduced as the vehicle approaches and goes to zero at the minimum distance.
- `CP_DIST` is the minimum distance (a negative value disables the feature). It is measured to the **sensor**, not to the propeller tips: add half the span.
- `CP_DELAY` is the delay from the sensor data to the velocity response; it is taken into account when braking.
- `CP_GUIDE_ANG` is how many degrees to each side the vehicle may deviate from the commanded direction if there is more room there.
- `CP_GO_NO_DATA`: 0 (default) means **no movement into directions without data**; 1 allows it. That is the right philosophy: without a rear sensor you do not fly backward.

### Where avoidance is actually useful
Autopilot obstacle avoidance is reliable for **slow** flight in a known environment: inspection next to a structure, flying near trees at 2–3 m/s, preventing "the pilot didn't notice the wall in Loiter". It does not turn the vehicle into an autonomous machine for a forest at 10 m/s: that needs a 3D map, planning (the module on navigation in ROS 2) and sensors that see wires. An honest wording for a requirements spec: "prevents collisions with large obstacles within the sensor field of view at speeds up to v_max".

### Where it fits in the system

- **Takes in:** a stereo depth map with an error ∝ Z² (`per-geometry`); a delivery path for `OBSTACLE_DISTANCE` from a component (`mav-component`); the deceleration the vehicle can actually achieve.
- **Hands off:** 72 sectors of distances to ArduPilot proximity and PX4 Collision Prevention; v_max for the given sensor to the requirements spec and the mission speed (`ap-missions`); groundwork for 3D planning (`ros2-nav`).
- **If you get this wrong:** a sector without data sent as "clear" instead of 65535 → the autopilot steers the vehicle where the sensor is not looking; a wall scenario in the simulator catches it (`tools-gazebo`). The companion latency grew because of throttling → L is larger than calculated, d_stop is longer, and the old v_max is no longer safe (`per-edge-ml`).

## practice
### Step 1. Sector map
Take a depth image: one you recorded from a depth camera in Gazebo (`examples/ros2-docker`, depth image topic → numpy), a frame from an open RGB-D dataset, or a synthetic numpy array with a "wall" and a "pole" (as in `tests/test_perception.py`). Build the 72 sectors with `depth_to_sectors()`, draw a polar plot and mark the "no data" sectors. Check: a wall to the right of the image center gives a sector with a bearing of 5–40°, and sector 180° (behind) is 65535, not "clear".

### Step 2. Speed budget
For your sensor (the datasheet range multiplied by 0.7 is the real one), a 2 m margin and the measured latency, compute v_max with `max_safe_speed()`. Then find the latency that cuts v_max in half. Write down the conclusion: which pays off more to improve, range or latency.

### Step 3. SITL: stop in front of a wall
ArduPilot SITL: `PRX1_TYPE = 10` (the built-in SITL proximity sensor) or `PRX1_TYPE = 2` with your own `OBSTACLE_DISTANCE` sender (a wall 15 m to the north, as sectors computed from the current position and heading); `AVOID_ENABLE` with bit 1, `AVOID_MARGIN = 3`. In Loiter give full forward stick: the vehicle must stop at ~3 m. Check `AVOID_BEHAVE` 0 and 1. Then in Auto with `OA_TYPE = 1` put a waypoint behind the "wall", watch BendyRuler go around it, and find the `OA_BR_LOOKAHEAD` at which it starts getting stuck.

Self-check: the lab is done when, on the polar plot, the wall to the right of the image center lands in sectors with a bearing of 5–40° and sector 180° equals 65535, not "clear"; `max_safe_speed()` on the example data from the theory (6 m range, 2 m margin, a = 3 m/s², L = 0.3 s) gives ≈ 4.1 m/s, after which v_max for your own sensor and the latency that halves it are computed; in the SITL logs the vehicle in Loiter at full stick stops ~3 m from the wall (`AVOID_MARGIN = 3`), BendyRuler goes around it in Auto, and the `OA_BR_LOOKAHEAD` at which it starts getting stuck is recorded.

## diagnostics
- **Symptom:** the vehicle does not react to an obstacle although the companion is sending data
  - Possible cause: `PRX1_TYPE` is not 2, a wrong `angle_offset` (ArduPilot 4.7 does not read the `frame` field: the sectors are always relative to the body), messages arrive less often than once every 0.5 s (the `AP_Proximity_MAV` timeout is 500 ms).
  - What to do: check `PRX` in the log and the Proximity view in Mission Planner: are the sectors visible.
- **Symptom:** the vehicle is "afraid" of a direction where there is nothing
  - Possible cause: a garbage value instead of 65535 in the sector, or 0 (PX4 treats 0 as an obstacle touching the sensor, ArduPilot discards 0); reflections from the frame and the legs.
  - What to do: 65535 for "no data", mask out your own airframe, `min_distance`.
- **Symptom:** avoidance works in Loiter but not in a mission
  - Possible cause: `OA_TYPE = 0`, or Dijkstra selected without a polygon fence.
  - What to do: BendyRuler for sensors; Dijkstra only for fences.
- **Symptom:** in PX4 the vehicle will not fly backward or sideways
  - Possible cause: no data in those sectors with `CP_GO_NO_DATA = 0`, which is by design.
  - What to do: add sensors, or deliberately allow movement without data.
- **Symptom:** it stops too late
  - Possible cause: the latency was underestimated, v_max for the sensor range was exceeded.
  - What to do: measure the latency, limit the speed in the mode, increase the margin.

## references
- MAVLink — OBSTACLE_DISTANCE | https://mavlink.io/en/messages/common.html#OBSTACLE_DISTANCE | primary | A
- ArduPilot — Object Avoidance (landing page) | https://ardupilot.org/copter/docs/common-object-avoidance-landing-page.html | primary | A
- ArduPilot — BendyRuler | https://ardupilot.org/copter/docs/common-oa-bendyruler.html | primary | A
- ArduPilot — AC_Avoidance source (AVOID_*, OA_*) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/AC_Avoidance | primary | A
- PX4 — Collision Prevention | https://docs.px4.io/main/en/computer_vision/collision_prevention.html | primary | A

## checklist
- I know the limits of each type of depth sensor, especially for wires
- I tell "no data" from "clear" in OBSTACLE_DISTANCE
- I build a sector map from a depth image
- I compute the stopping distance and the maximum safe speed
- I understand the difference between simple avoidance, BendyRuler and Dijkstra and where each one works
- I configure CP_* in PX4 and understand the policy for movement without data
