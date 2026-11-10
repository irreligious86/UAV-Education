---
id: ros2-nav
title: "Navigation and obstacle avoidance: maps, planners, setpoints"
level: L3
readingTime: 45 min
firmware: PX4 · ArduPilot
status: published
added: 2026-11-08
tags:
  - navigation
  - planning
  - A*
  - obstacle avoidance
  - Nav2
related:
  - ros2-app-arch
  - mav-component
  - per-visual-nav
next:
  - ros2-from-ros1
source: content/ros2/ros2-nav.md
source_hash: 5e677a226b42
---

## summary
The autopilot knows how to fly to a point. To fly to a point **without crashing into things**, you need a map, a planner and a chain from the plan to setpoints — and an honest understanding of what the autopilot can already do on its own (ArduPilot: BendyRuler and Dijkstra, PX4: collision prevention) and where you need your own logic on the companion. This module covers map representations (occupancy grid, costmap, 3D voxels), global and local planning (A*, Dijkstra, reactive methods), obstacle inflation and path smoothing, the role of Nav2 and why it's “ground-based”, and how a plan turns into GUIDED/Offboard setpoints with velocity and altitude limits. Lab: A* on a grid with tests, then flying around an obstacle in Gazebo using lidar data.

## theory
### What the autopilot can do without you
- **ArduPilot**: proximity sensors (`PRX1_TYPE`, including MAVLink `OBSTACLE_DISTANCE`) → **simple avoidance** (stop/slide in Loiter, `AVOID_ENABLE`, `AVOID_MARGIN`) and **object avoidance** in automatic modes: `OA_TYPE = 1` BendyRuler (reactive, searches for a way around), `2` Dijkstra (over polygon geofences, a global path around known no-go zones), `3` a combination. Parameters `OA_MARGIN_MAX`, `OA_BR_LOOKAHEAD`.
- **PX4**: **collision prevention** in Position mode (`CP_DIST` — the minimum distance, from `OBSTACLE_DISTANCE`/ROS 2 `ObstacleDistance`), limits velocity toward the obstacle.

This works and has been flight-tested — start with it. You need your own navigation on the companion when: the map has to be built and stored (indoor flight, a forest), the path must be globally optimal in an unknown environment, or there is a higher-level goal (survey an object, fly to a point found by the camera).

### Map representations
- **Occupancy grid**, 2D: a cell holds the probability of being occupied (in ROS `nav_msgs/OccupancyGrid`: 0–100, −1 — unknown). It's updated from rangefinder/lidar rays: along the ray — free, at the end — occupied (log-odds, to accumulate evidence).
- **Costmap**: occupancy + inflation + layers (static, obstacles, geofences). Inflating by the vehicle radius plus a margin lets you plan for a point rather than for a body.
- **3D**: OctoMap (an octree of voxels), ESDF/TSDF (a field of distances to the nearest obstacle: Voxblox, nvblox). For flight at different altitudes a 2D grid isn't enough, but 2D at a fixed altitude is a good start.
- **Unknown = occupied** by default: fly only where you've already seen that it's free. Otherwise the planner will route the path “through a wall” it hasn't seen yet.

### Global planning
**A\*** on a grid: a search for the shortest path from start to goal with a heuristic (an estimate of the remaining distance). If the heuristic never overestimates (it's admissible), the path is optimal. For an 8-connected grid — the octile distance `(dx + dy) + (√2 − 2)·min(dx, dy)`. No “cutting the corner” diagonally between two occupied cells. **Dijkstra** is A* with a zero heuristic (slower, but the same solution). For large 3D spaces — sampling-based methods (RRT*, PRM).

The raw A* path is a cell-by-cell “staircase”. **Smoothing** (shortcut): drop intermediate points as long as the straight segment is free; then apply the dynamics limits (velocity, acceleration, jerk) when building the trajectory.

### Local planning and reaction
The global plan is built from a map that is already out of date by flight time. The local layer reacts to what is visible right now: vector fields (VFH), dynamic window (DWA), MPC, or simply “stop and replan”. Rates: global — 0.5–2 Hz, local — 10–20 Hz, setpoints — 20–50 Hz. The layers should be separate nodes (module ros2-app-arch), and the last line of defense is the autopilot (simple avoidance / collision prevention) and the geofence.

{{diagram:planning-layers|Navigation layers and their rates; the last line of defense is the autopilot.}}

### Nav2 and drones
Nav2 is the ROS 2 navigation stack: the BT navigator (behavior trees), planners (NavFn, Smac), controllers (DWB, MPPI), costmap layers, recovery. It's designed for ground robots (2D, non-holonomic models). For a multicopter at constant altitude you can use it (holonomic model, `cmd_vel` → GUIDED/Offboard velocities), but 3D planning, altitude and flight dynamics are beyond its scope. Many drone projects take the costmap layers and the BT ideas from Nav2, and write their own planner or take one from research stacks (for example, EGO-Planner, Fast-Planner — for the experienced).

### From plan to setpoints
1. A path in the `map` frame (ENU) → intermediate points spaced 1–3 m apart.
2. Limits: the maximum velocity near obstacles (depends on the sensor range and the braking distance: v ≤ √(2·a·d)), altitude within a corridor (above the ground by rangefinder and below the geofence), yaw along the direction of travel if the camera must look forward.
3. Sending: PX4 — `TrajectorySetpoint` (position and/or velocity, NED — convert!), ArduPilot — `/ap/cmd_vel` (ENU, frame `map`) or position targets via MAVROS.
4. Execution monitoring: deviation from the path > threshold → stop and replan; goal unreachable → hold and notify the operator.

## practice
### Step 1. A* with tests
```bash
cd examples/ros2-docker/ws/src/uav_ros2_labs
python -m pytest -q test/test_grid_planner.py
```
Read `grid_planner.py`: inflation, the octile heuristic, the no-corner-cutting rule, shortcut. Add a test: the path with inflation is longer than the path without it, but not shorter than the straight line.

### Step 2. Braking distance
For a vehicle with a maximum deceleration of 3 m/s² and a lidar with a reliable range of 8 m, calculate the maximum safe velocity with a 2 m margin and a 0.3 s reaction delay. Compare with the simple avoidance parameters of your firmware.

### Step 3. Flying around an obstacle in Gazebo
A world with a pillar in the path of the square. Option A (no code of your own): ArduPilot SITL with proximity from a simulated lidar, `OA_TYPE = 1`, a mission through the pillar — record the BendyRuler trajectory. Option B (your own node): an occupancy grid from `/scan` or `OBSTACLE_DISTANCE`, A* + shortcut, setpoints via the state machine from ros2-px4. Compare the trajectories and the time.

### Step 4. Unknown space
Repeat step 3 with `unknown_is_free=True` and `False`: show where the “optimistic” planner routes the path through space it hasn't seen yet, and why that is dangerous.

The lab counts as done when your own planner test passes, the safe velocity has been calculated, you have the avoidance trajectories (at least option A) and an analysis of unknown space.

## diagnostics
- **Symptom:** the path runs right next to the obstacle, the vehicle clips it
  - Possible cause: no inflation, or the radius is smaller than the vehicle size + position error.
  - What to do: inflation = radius + 2σ of position + margin.
- **Symptom:** the vehicle “jerks”, replanning every 100 ms changes the path
  - Possible cause: the global planner runs at the local planner's rate, a noisy map.
  - What to do: global plan at 1 Hz, hysteresis on path changes, a map filter (log-odds).
- **Symptom:** the vehicle flies into an unknown area and loses the obstacle from its field of view
  - Possible cause: unknown is treated as free; the sensor isn't looking where you're flying.
  - What to do: unknown = occupied; yaw along the direction of travel.
- **Symptom:** the setpoints along the path lead the wrong way
  - Possible cause: an ENU path was sent to PX4 as NED.
  - What to do: convert at the boundary (frames.py), test on a known point.

## references
- ArduPilot — Object avoidance (BendyRuler, Dijkstra) | https://ardupilot.org/copter/docs/common-object-avoidance-landing-page.html | primary | A
- PX4 — Collision prevention | https://docs.px4.io/main/en/computer_vision/collision_prevention.html | primary | A
- Nav2 documentation | https://docs.nav2.org/ | primary | A
- OctoMap | https://octomap.github.io/ | primary | A
- Hart, Nilsson, Raphael — A formal basis for the heuristic determination of minimum cost paths (A*) | https://ieeexplore.ieee.org/document/4082128 | secondary | A

## checklist
- I know what BendyRuler/Dijkstra and collision prevention can do without my own code
- I can tell an occupancy grid, a costmap and 3D representations apart; unknown means occupied
- I implement A* with an admissible heuristic, inflation and smoothing
- I separate global and local planning by rates and roles
- I turn a path into setpoints with velocity limits based on braking distance
- I understand where Nav2 is useful for a drone and where it isn't
