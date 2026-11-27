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

```python
"""ros2-nav lab: Dijkstra vs A* vs weighted A*, inflation, shortcut, unknown cells, log-odds.
Run from examples/ros2-docker/ws/src/uav_ros2_labs:  python3 nav_lab.py"""
import heapq, math, random, sys
sys.path.insert(0, ".")
from uav_ros2_labs.grid_planner import inflate, line_free, path_length, shortcut


def search(grid, s, g, w):
    """8-connected grid search; w = heuristic weight (0 Dijkstra, 1 A*, >1 weighted A*)."""
    def h(c):
        dx, dy = abs(c[0] - g[0]), abs(c[1] - g[1])
        return (dx + dy) + (math.sqrt(2) - 2) * min(dx, dy)
    free = lambda c: 0 <= c[0] < len(grid[0]) and 0 <= c[1] < len(grid) and grid[c[1]][c[0]] == 0
    openq, best, parent, closed = [(w * h(s), 0.0, s)], {s: 0.0}, {}, set()
    while openq:
        _, gc, c = heapq.heappop(openq)
        if c in closed:
            continue
        closed.add(c)
        if c == g:
            p = [c]
            while c in parent:
                c = parent[c]; p.append(c)
            return p[::-1], len(closed)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                n = (c[0] + dx, c[1] + dy)
                if (dx, dy) == (0, 0) or not free(n):
                    continue
                if dx and dy and not (free((c[0] + dx, c[1])) and free((c[0], c[1] + dy))):
                    continue
                ng = gc + math.hypot(dx, dy)
                if ng < best.get(n, math.inf):
                    best[n], parent[n] = ng, c
                    heapq.heappush(openq, (ng + w * h(n), ng, n))
    return None, len(closed)


W, H = 60, 40                          # 0.5 m cells -> 30 x 20 m
grid = [[0] * W for _ in range(H)]
for y in range(0, 30):                 # wall from the bottom edge, gap at the top
    grid[y][30] = 1
S, G = (5, 5), (55, 5)
print("1) search on the raw grid, 0.5 m cells")
for name, w in (("Dijkstra  w=0  ", 0), ("A*        w=1  ", 1), ("weighted  w=2  ", 2)):
    p, n = search(grid, S, G, w)
    print(f"   {name} expanded {n:5d} cells, path {path_length(p) * 0.5:6.2f} m")

forest = random.Random(1)                                # 25 % random obstacles, seed 1
fg = [[1 if forest.random() < 0.25 else 0 for _ in range(W)] for _ in range(H)]
fg[5][5] = fg[35][55] = 0
print("   'forest' 60x40, 25 % occupied, (5,5) -> (55,35):")
for name, w in (("Dijkstra  w=0  ", 0), ("A*        w=1  ", 1), ("weighted  w=2  ", 2)):
    p, n = search(fg, (5, 5), (55, 35), w)
    print(f"   {name} expanded {n:5d} cells, path {path_length(p) * 0.5:6.2f} m")

print("2) inflation for a 0.6 m radius + 0.4 m margin = 2 cells")
gi = inflate(grid, 2)
p0, _ = search(grid, S, G, 1)
p1, _ = search(gi, S, G, 1)
s1 = shortcut(gi, p1)
print(f"   raw {path_length(p0) * 0.5:.2f} m, inflated {path_length(p1) * 0.5:.2f} m, "
      f"inflated+shortcut {path_length(s1) * 0.5:.2f} m in {len(s1) - 1} segments, straight {math.dist(S, G) * 0.5:.2f} m")
print(f"   shortcut stays free: {all(line_free(gi, a, b) for a, b in zip(s1, s1[1:]))}")

print("3) unseen cells: the gap at the top was never observed (-1)")
gu = [row[:] for row in grid]
for y in range(30, 40):
    gu[y][30] = -1
blocked = [[0 if v == 0 else 1 for v in row] for row in gu]       # unknown = occupied
optim = [[0 if v in (0, -1) else 1 for v in row] for row in gu]   # unknown = free
print(f"   unknown=occupied: path {'found' if search(blocked, S, G, 1)[0] else 'none -> hold and explore'}")
po, _ = search(optim, S, G, 1)
thru = [c for c in po if gu[c[1]][c[0]] == -1]
print(f"   unknown=free: path {path_length(po) * 0.5:.2f} m, crosses {len(thru)} unseen cells at x=30, y={thru[0][1]}..{thru[-1][1]}")

print("4) log-odds occupancy: p_hit = 0.7, p_miss = 0.4 per beam")
l_hit, l_miss = math.log(0.7 / 0.3), math.log(0.4 / 0.6)
l = 0.0
for k, z in enumerate("HHHMM", 1):
    l += l_hit if z == "H" else l_miss
    print(f"   beam {k} {'hit ' if z == 'H' else 'miss'}  L = {l:+.3f}  p = {1 - 1 / (1 + math.exp(l)):.3f}")
```

```text
1) search on the raw grid, 0.5 m cells
   Dijkstra  w=0   expanded  2290 cells, path  35.94 m
   A*        w=1   expanded   785 cells, path  35.94 m
   weighted  w=2   expanded   537 cells, path  35.94 m
   'forest' 60x40, 25 % occupied, (5,5) -> (55,35):
   Dijkstra  w=0   expanded  1778 cells, path  33.56 m
   A*        w=1   expanded   462 cells, path  33.56 m
   weighted  w=2   expanded    86 cells, path  37.85 m
2) inflation for a 0.6 m radius + 0.4 m margin = 2 cells
   raw 35.94 m, inflated 37.94 m, inflated+shortcut 36.80 m in 2 segments, straight 25.00 m
   shortcut stays free: True
3) unseen cells: the gap at the top was never observed (-1)
   unknown=occupied: path none -> hold and explore
   unknown=free: path 35.94 m, crosses 1 unseen cells at x=30, y=30..30
4) log-odds occupancy: p_hit = 0.7, p_miss = 0.4 per beam
   beam 1 hit   L = +0.847  p = 0.700
   beam 2 hit   L = +1.695  p = 0.845
   beam 3 hit   L = +2.542  p = 0.927
   beam 4 miss  L = +2.136  p = 0.894
   beam 5 miss  L = +1.731  p = 0.850
```

```text
OA_TYPE 2
FENCE_ENABLE 1
FENCE_TYPE 4
GUID_OPTIONS 64
WP_SPD 5
```

```text
$ ./run_lab.sh oa oa.parm "" oa_dijkstra_lab.py
home -35.363261 149.165230
fence upload ack type 0
DO_FENCE_ENABLE ack result 4
FENCE_ENABLE = 1
armed, takeoff 10 m
goal 80 m north sent
time 31.8 s, path 87.0 m vs straight 80.0 m, max |E| 13.7 m, min clearance to square 3.6 m
$ python3 oadj.py sitl-run/oa/logs/00000001.BIN
OADJ State 0 point 0/0 OA -35.362542 149.165230
OADJ State 2 point 1/4 OA -35.363023 149.165379
OADJ State 2 point 2/4 OA -35.362780 149.165379
```

```text
$ ./run_lab.sh oa_nofence_enable oa_nofence.parm "" oa_dijkstra_lab.py
DO_FENCE_ENABLE ack result 4
FENCE_ENABLE = 0
time 21.2 s, path 80.4 m vs straight 80.0 m, max |E| 0.0 m, min clearance to square -1.0 m
$ ./run_lab.sh oa_nofence oa_nofence.parm "" oa_dijkstra_lab.py --no-enable
FENCE_ENABLE = 0
time 21.2 s, path 80.4 m vs straight 80.0 m, max |E| 0.0 m, min clearance to square -1.0 m
```

{{diagram:chart-nav-oa-dijkstra-track|Трек SITL совпал с планом Dijkstra до 0.5 м по длине: вершины зоны вынесены на 5/√2 = 3.54 м, путь 87.0 м вместо 80 м и 31.8 с вместо 21.2 с из-за остановок в углах.}}

{{diagram:chart-nav-brake-speed|Задержка реакции 0.3 с срезает безопасную скорость при d = 6 м с 6.0 до 5.2 м/с, а забытый запас добавляет ещё ошибку до 6.9 м/с.}}

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
