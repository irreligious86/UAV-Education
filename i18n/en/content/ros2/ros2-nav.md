---
id: ros2-nav
title: "Navigation and obstacle avoidance: maps, planners, setpoints"
level: L3
readingTime: 60 min
firmware: ArduPilot 4.7 (checked against 4.7.3; lab captured on SITL 4.7.2) · PX4 1.18 (parameters checked against v1.18.0)
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
source_hash: 02b0fc0f9aa1
---

## summary
An autopilot can fly to a point. To fly to a point **without crashing into things**, you need a map, a planner and a chain from the plan to the setpoints, plus an honest understanding of what the autopilot already does by itself (ArduPilot: BendyRuler and Dijkstra; PX4: collision prevention) and where you need your own logic on the companion computer. This module covers map representations (an occupancy grid with log-odds, a cost map, 3D voxels), global and local planning (A*, Dijkstra, weighted A*, reactive methods), obstacle inflation and path smoothing, the role of Nav2 and why it is "ground-based", and how a plan becomes GUIDED/Offboard setpoints with speed and altitude limits and timeouts. Lab: A* on a grid with tests and a comparison of expanded cells, ArduPilot 4.7.2 Dijkstra around an exclusion zone in SITL with a real track, then flying around an obstacle in Gazebo from lidar data.

## theory
### What the autopilot does without you
- **ArduPilot**: proximity sensors (`PRX1_TYPE`, including `2`, MAVLink `OBSTACLE_DISTANCE`) → **simple avoidance** (stop/slide in Loiter, `AVOID_ENABLE`, `AVOID_MARGIN`) and **object avoidance** in the automatic modes: `OA_TYPE = 1` BendyRuler (reactive, searches for a detour direction), `2` Dijkstra (on fence polygons, a global path around known exclusion zones), `3` both. Parameters `OA_MARGIN_MAX`, `OA_BR_LOOKAHEAD`.
- **PX4**: **collision prevention** in Position mode (`CP_DIST`, the minimum distance, from `OBSTACLE_DISTANCE`/ROS 2 `ObstacleDistance`) limits the velocity toward an obstacle.

This works and is flight-proven, so start with it. You need your own navigation on the companion computer when you have to build and keep a map (indoor flight, a forest), the path has to be globally optimal in an unknown environment, or there is a higher-level goal (survey an object, reach a point found by the camera).

### How it works inside ArduPilot 4.7.2
**Simple avoidance** does not plan a path; it limits the velocity or the lean angle. In Loiter and in Guided with velocity setpoints, the velocity toward an obstacle is limited so that the vehicle, decelerating at `AVOID_ACCEL_MAX` (3 m/s² by default), stops `AVOID_MARGIN` (2 m) away from it; `AVOID_BEHAVE = 0` means slide along the obstacle (the copter default), `1` means stop. If the vehicle is already inside the margin, it backs away at up to `AVOID_BACKUP_SPD` (0.75 m/s). AltHold and FlowHold have no position, so the lean angle is limited instead (to `AVOID_ANG_MAX`, 10°; in 4.6, `AVOID_ANGLE_MAX` in centidegrees), and only for obstacles closer than `AVOID_DIST_MAX` (5 m). `AVOID_ENABLE` defaults to 3, the "fence" and "proximity" bits (`AC_Avoid.cpp:43–123`, `AC_Avoid.h:19–22`).

**Object avoidance** is active in Auto, Guided and RTL: all three get their target through `get_oa_wp_destination()` (`mode_auto.cpp:923`, `mode_guided.cpp:448`, `mode_rtl.cpp:591`). The planner runs in a separate thread at 1 Hz (`OA_UPDATE_MS = 1000`), and a result older than 3 s is discarded (`OA_TIMEOUT_MS`, `AP_OAPathPlanner.cpp:34–35`). Both numbers limit the speed: in the 1 s between updates a vehicle at 5 m/s covers 5 m, so `OA_MARGIN_MAX` (5 m by default) must be no less than that distance plus the braking distance (a conclusion from the code). Changing `OA_TYPE` requires a reboot: until then arming is refused with "BendyRuler OA requires reboot" (`OA_TYPE = 1`), "Dijkstra OA requires reboot" (`2`) or "OA requires reboot" (`3`) (`AP_OAPathPlanner.cpp:124–145`).

- **BendyRuler** tries directions every 5° to the left and right of the bearing to the target, up to ±170°, and checks a segment of up to `OA_BR_LOOKAHEAD` (15 m; near the target no more than 2 m past it, and after failed searches the length is temporarily cut down to half) against the obstacle database `OA_DB_*` (up to `OA_DB_SIZE` = 100 points, each point lives `OA_DB_EXPIRE` = 10 s). So that the heading does not "jump" from one side of the obstacle to the other, a change of direction by more than `OA_BR_CONT_ANGLE` (75°) is accepted only if the margin to the obstacle in the new direction is at least `OA_BR_CONT_RATIO` (1.5) times the margin in the old one (`AP_OABendyRuler.cpp:381–405`). `OA_BR_TYPE = 2` searches for a detour vertically (`AP_OABendyRuler.cpp:28–37, 100–133` for the segment length and the choice of search, `141–236` for the horizontal search, `250` for the vertical one).
- **Dijkstra** knows only the fence: exclusion polygons and circles and the inclusion polygon. It moves each convex vertex outward along the angle bisector by `OA_MARGIN_MAX` and finds the shortest path over the visibility graph between these points (`AP_OADijkstra.cpp:420–490`). For a square zone this is an offset of 5/√2 = 3.54 m along each axis. Without an enabled fence (`FENCE_ENABLE = 1`, the "polygons" type in `FENCE_TYPE`) it silently returns "not required" (`AP_OADijkstra.cpp:61–64, 241–253`), and the vehicle flies straight. In Copter the vehicle stops at each intermediate point by default; bit 2 of `OA_OPTIONS` ("Allow fast waypoints", value 4) lets it fly through them without stopping.
- **`OA_TYPE = 3`**: Dijkstra plans the path around the known zones, and BendyRuler steers around what the sensor sees.

{{lesson:per-depth-avoid|Which depth sensor sees what, how a depth map becomes 72 `OBSTACLE_DISTANCE` sectors, and how to check stopping in front of a wall in SITL.}}

### PX4 1.17: what exists and what is gone
Collision prevention works **only in Position mode**, as the description of every one of its parameters says (`collisionprevention_params.c:50–86`). `CP_DIST` defaults to −1, that is, disabled; `CP_DELAY` = 0.4 s is the combined sensor and controller delay, which enters the braking distance calculation; `CP_GUIDE_ANG` = 30° is how far it may turn the setpoint toward a free sector; `CP_GO_NO_DATA = 0` forbids moving where the sensor does not see. In Mission and Offboard PX4 does not avoid obstacles. The PX4-Avoidance external planner interface with the `COM_OBS_AVOID` parameter existed in 1.15.4 (`commander_params.c:707`) and is already absent from the 1.16.2 and 1.17.0 trees (a conclusion from the code). So for PX4, avoidance in automatic flight is always your own node on the companion computer publishing `TrajectorySetpoint`.

### Map representations
- **Occupancy grid**, 2D: a cell holds the probability of being occupied (in ROS `nav_msgs/OccupancyGrid`: 0–100, −1 means unknown). It is updated along rangefinder/lidar beams: free along the beam, occupied at its end (log-odds, to accumulate evidence).
- **Cost map (costmap)**: occupancy + inflation + layers (static, obstacles, fences). Inflating by the vehicle radius plus a margin lets you plan for a point instead of a body.
- **3D**: OctoMap (an octree of voxels), ESDF/TSDF (a field of distances to the nearest obstacle: Voxblox, nvblox). For flight at different altitudes a 2D grid is not enough, but 2D at a fixed altitude is a good start.
- **Unknown = occupied** by default: fly only where you have already seen free space. Otherwise the planner will route the path "through a wall" it has not seen yet.

**Log-odds.** The probability p is stored as L = ln(p/(1 − p)): then each measurement is an addition, not a multiplication. A beam hitting a cell adds l_hit = ln(p_hit/(1 − p_hit)), a beam passing through it adds l_miss = ln(p_miss/(1 − p_miss)), and back again p = 1 − 1/(1 + e^L). With p_hit = 0.7 and p_miss = 0.4, three hits give p = 0.927, and the next two misses bring it back to 0.850 (computed in step 2). L is clamped from above and below (the course guideline is ±3.5, that is p from 0.03 to 0.97): otherwise a cell seen occupied 200 times will not become free when the obstacle leaves.

**Resolution and memory.** A 100 × 100 m 2D grid with 0.25 m cells is 160 000 cells, at one byte per cell 160 kB. A dense 100 × 100 × 30 m 3D grid with 0.2 m voxels is 37.5 million voxels; that is why 3D uses an octree (empty space is stored in large nodes) or TSDF/ESDF only around the vehicle. A cell must be smaller than the margin to the obstacle, or inflating by one cell eats the whole corridor.

### Global planning
**A\*** on a grid: a shortest-path search from start to goal with a heuristic (an estimate of the remaining distance). If the heuristic does not overestimate (it is admissible), the path is optimal. For an 8-connected grid it is the octile distance `(dx + dy) + (√2 − 2)·min(dx, dy)`. Cutting a corner diagonally between two occupied cells is forbidden. **Dijkstra** is A* with a zero heuristic (slower, but the same solution). For large 3D spaces there are sampling-based methods (RRT*, PRM).

The price of the heuristic shows in the number of expanded cells. On a 60 × 40 grid with a wall, Dijkstra expanded 2290 cells and A* 785, with the same path of 35.94 m. **Weighted A\*** (heuristic × w, w > 1) expands even fewer, but the heuristic now overestimates and optimality is lost: the path is guaranteed to be no longer than w × the optimal one, but it is not guaranteed to be optimal either. In a "forest" with 25 % of the cells occupied, w = 2 expanded 86 cells instead of 462, but the path came out 37.85 m instead of 33.56 m, 13 % longer. The course rule: w > 1 only when the plan must be delivered within a fixed time on a weak CPU, and only for the global level, which gets replanned anyway.

The raw A* path is a "staircase" of cells. **Smoothing** (shortcut): drop intermediate points while the straight segment is free; then apply the dynamics limits (velocity, acceleration, jerk) when building the trajectory.

**Inflation.** Inflation radius = the vehicle radius to the prop tips + 2σ of the position error + a margin. For a vehicle with a 0.6 m radius and a 0.4 m margin on a 0.5 m grid that is 2 cells: in the lab the path grew from 35.94 to 37.94 m, and after the shortcut it became 36.80 m in two segments. Binary inflation (occupied/free) gives a path hugging the edge of the inflated zone; a costmap with a cost that decays around the obstacle pushes the path further away if there is room.

### Local planning and reaction
The global plan is built from a map that is already outdated by the time you fly. The local level reacts to what is visible now: vector fields (VFH), the dynamic window (DWA), MPC, or simply "stop and replan". Rates: global 0.5–2 Hz, local 10–20 Hz, setpoints 20–50 Hz. The layers should be separate nodes (module ros2-app-arch), and the last line of defense is the autopilot (simple avoidance / collision prevention) and the fence.

{{diagram:planning-layers|The navigation layers and their rates; the last line of defense is the autopilot.}}

### Nav2 and drones
Nav2 is the ROS 2 navigation stack: the BT navigator (behavior trees), planners (NavFn, Smac, Theta*), controllers (DWB, Regulated Pure Pursuit, MPPI, Graceful, Rotation Shim), costmap layers, the collision monitor, the velocity smoother, recovery behaviors (the `nav2_*` packages in the navigation2 repository). It is designed for ground robots (2D, nonholonomic models). For a multicopter at a constant altitude you can use it (a holonomic model, `cmd_vel` → GUIDED/Offboard velocities), but 3D planning, altitude and flight dynamics are outside its scope. Many drone projects take the costmap layers and the BT ideas from Nav2 and write their own planner or take one from research stacks (for example, EGO-Planner, Fast-Planner, for experienced users).

### From plan to setpoints
1. A path in the `map` frame (ENU) → intermediate points every 1–3 m.
2. Limits: the maximum speed near obstacles (it depends on the sensor range and the braking distance: v ≤ √(2·a·d); with a reaction delay t_r the vehicle first covers v·t_r and only then brakes over v²/(2·a), so the condition is v·t_r + v²/(2·a) ≤ d, which gives v ≤ −a·t_r + √((a·t_r)² + 2·a·d); here d is the reliable sensor range minus the margin), the altitude within a corridor (above the ground by the rangefinder and below the fence), and yaw along the direction of travel if the camera must look forward.
3. Sending: PX4 takes `TrajectorySetpoint` (position and/or velocity, NED, so convert!), ArduPilot takes `/ap/cmd_vel` (ENU, frame `map`) or position targets through MAVROS.
4. Monitoring: deviation from the path > threshold → stop and replan; goal unreachable → hold and report to the operator.

**Timeouts are part of the contract.** ArduPilot velocity setpoints in Guided live for `GUID_TIMEOUT` = 3 s: if the node goes quiet, the vehicle stops. PX4 considers Offboard lost after `COM_OF_LOSS_T` = 1 s without the stream. A position target in ArduPilot Guided goes through object avoidance only if `GUID_OPTIONS` has bit 6, "Waypoint navigation used for position targets" (value 64); without it the position goes straight to the position controller, and Dijkstra/BendyRuler never see it (`mode_guided.cpp:670–672`).

| Parameter / API | Where | Default | What it does |
|---|---|---|---|
| `AVOID_ENABLE` | ArduPilot 4.7.2 | 3 (fence + proximity) | bitmask of simple avoidance sources |
| `AVOID_MARGIN` | ArduPilot | 2 m | the distance to stop at in Loiter/Guided |
| `AVOID_BEHAVE` | ArduPilot Copter | 0 slide (1 stop) | behavior at an obstacle |
| `AVOID_ACCEL_MAX` | ArduPilot | 3 m/s² | deceleration used for the braking distance |
| `AVOID_DIST_MAX` / `AVOID_ANG_MAX` (4.6: `AVOID_ANGLE_MAX`, centidegrees) | ArduPilot Copter | 5 m / 10° | range and lean angle limit in AltHold |
| `OA_TYPE` | ArduPilot | 0 (1 BendyRuler, 2 Dijkstra, 3 both) | object avoidance in Auto/Guided/RTL, needs a reboot |
| `OA_MARGIN_MAX` | ArduPilot | 5 m | margin; Dijkstra's offset of the zone vertices |
| `OA_BR_LOOKAHEAD` | ArduPilot | 15 m | length of the segment BendyRuler checks |
| `OA_DB_SIZE` / `OA_DB_EXPIRE` | ArduPilot | 100 points / 10 s | BendyRuler obstacle database |
| `OA_OPTIONS` bit 2 | ArduPilot Copter | off | fly through Dijkstra intermediate points without stopping |
| `GUID_OPTIONS` bit 6 / `GUID_TIMEOUT` | ArduPilot Copter | off / 3 s | position targets through WPNav (and OA) / velocity setpoint timeout |
| `CP_DIST` / `CP_DELAY` / `CP_GUIDE_ANG` | PX4 1.17.0 | −1 (off) / 0.4 s / 30° | collision prevention, Position mode only |
| `COM_OF_LOSS_T` | PX4 1.17.0 | 1 s | loss of the Offboard stream |
| `/fmu/in/trajectory_setpoint`, `/fmu/in/obstacle_distance` | PX4 uXRCE-DDS | — | setpoints and obstacles from ROS 2 |
| `nav_msgs/OccupancyGrid` | ROS 2 | −1 unknown, 0–100 | occupancy grid |

### Place in the system

- **Receives:** ranges from a lidar or a depth camera (`per-depth-avoid`); the pose in `map` from the bridge (`ros2-ardupilot`, `ros2-px4`); the fence and the autopilot's own avoidance as the last line of defense (`ap-safety-fs`).
- **Provides:** setpoints: `TrajectorySetpoint` in NED for PX4 or `/ap/cmd_vel` in ENU for ArduPilot; a speed limit near obstacles from the braking distance; the path to trajectory generation with dynamics limits (`ctl-guidance`).
- **If you get it wrong here:** you treated unknown cells as free → the path goes "through a wall" not seen yet → a collision; only the autopilot's line of defense is left (`per-depth-avoid`). You sent a path from ENU to PX4 without converting to NED → the vehicle flies the wrong way and at the wrong altitude (`px4-ros2`).

## practice
### Step 1. A* with tests
```bash
cd examples/ros2-docker/ws/src/uav_ros2_labs
python -m pytest -q test/test_grid_planner.py
```
Read `grid_planner.py`: inflation, the octile heuristic, the no-corner-cutting rule, shortcut. Add a test: the path with inflation is longer than the path without it, but not shorter than the straight line. Output on a clean examples tree (Python 3, pytest): `8 passed in 0.03s`; with your test it should become 9.

### Step 2. Expanded cells, inflation, unknown cells, log-odds
The script below goes next to the package (`examples/ros2-docker/ws/src/uav_ros2_labs/nav_lab.py`) and imports `inflate`, `shortcut`, `line_free`, `path_length` from it. It has its own search so that it can count expanded cells and vary the heuristic weight w: 0 is Dijkstra, 1 is A*, 2 is weighted A*. A 60 × 40 grid of 0.5 m cells (30 × 20 m), a wall at x = 30 from the bottom edge up to y = 29, a gap at the top.

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

Output (Python 3.13):

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

How to read this. Dijkstra and A* gave the same path, but A* expanded a third as many cells: that is the value of an admissible heuristic. Weighted A* lost nothing at the wall, but in the "forest" it lost 4.3 m: a heuristic with weight 2 overestimates, and the first path found does not have to be the shortest. Inflation made the path 2 m longer, the shortcut won back 1.14 m of that and left two straight segments, which is what you hand to the trajectory generator, not 70 cells. In item 3 the "optimist" routes the path through cell (30, 30), which nobody has seen: if there is a wall there, the vehicle finds out only on approach. The "pessimist" finds no path and says so honestly: hold position and explore further.

### Step 3. Braking distance
For a vehicle with a maximum deceleration of 3 m/s² and a lidar with a reliable range of 8 m, compute the maximum safe speed with a 2 m margin and a 0.3 s reaction delay. Compare with your firmware's simple avoidance parameters: in ArduPilot the deceleration is set by `AVOID_ACCEL_MAX` (3 m/s²) and the margin by `AVOID_MARGIN` (2 m); in PX4 the delay is `CP_DELAY` (0.4 s). Recompute the same speed for t_r = 0.4 s.

### Step 4. ArduPilot Dijkstra in SITL around an exclusion zone
You do not need Gazebo: Dijkstra works from the fence, and you can load one into plain SITL. The scripts are in `examples/sitl-nav-labs/` (with a README): `run_lab.sh` starts ArduCopter 4.7.2 SITL (`arducopter -w --model + --speedup 1`) with `copter.parm` plus the lab's parameter file and saves a run folder with the log. The `oa.parm` parameters:

```text
OA_TYPE 2
FENCE_ENABLE 1
FENCE_TYPE 4
GUID_OPTIONS 64
WP_SPD 5
```

`WP_SPD` is the route speed in m/s (in 4.7.2; before 4.7 it was `WPNAV_SPEED` in cm/s, 4.7.2 has no such parameter, and a `WPNAV_SPEED 500` line is silently ignored, so the vehicle flies at the default `WP_SPD`). The script `oa_dijkstra_lab.py` (128 lines, pymavlink) uploads through the mission protocol (`MISSION_COUNT` with `mission_type = MAV_MISSION_TYPE_FENCE`, four `MISSION_ITEM_INT` with the command `MAV_CMD_NAV_FENCE_POLYGON_VERTEX_EXCLUSION`, param1 = 4) a 20 × 20 m exclusion square: north 30…50 m, east −10…10 m. Then it tries to enable the fence with `MAV_CMD_DO_FENCE_ENABLE`, reads `FENCE_ENABLE` back, arms in Guided, takes off to 10 m and sends `SET_POSITION_TARGET_LOCAL_NED` 80 m to the north; the straight line goes through the center of the square. The track is recorded from `LOCAL_POSITION_NED` at 10 Hz. The run and its output:

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

The `OADJ` log has four path points (`TotPoints = 4`, `State = 2` means a path was found; the `State = 0` record logs NOT_REQUIRED with the OA point equal to the goal itself, 80 m north: AP_OADijkstra writes the destination unchanged whenever no detour is needed, e.g. on the final straight leg after the last intermediate point); the intermediate points converted to meters are (26.49 m north, 13.53 m east) and (53.54, 13.53). Checking against the theory: the vertices of the square are moved out by 5/√2 = 3.54 m along each axis, so the plan (0, 0) → (26.46, 13.54) → (53.54, 13.54) → (80, 0) is 29.72 + 27.07 + 29.72 = 86.5 m long, and 87.0 m was measured.

`DO_FENCE_ENABLE ack result 4` is `MAV_RESULT_FAILED`, and it is not random: the command fails if the autopilot does not yet hold a loaded fence of the required type (`fence->present()`, `GCS_Fence.cpp:28–31`), and polygons are loaded only for a fence that is already enabled. Here it does no harm, since `FENCE_ENABLE 1` is set from boot. The control runs with `oa_nofence.parm` (the same, but `FENCE_ENABLE 0`):

```text
$ ./run_lab.sh oa_nofence_enable oa_nofence.parm "" oa_dijkstra_lab.py
DO_FENCE_ENABLE ack result 4
FENCE_ENABLE = 0
time 21.2 s, path 80.4 m vs straight 80.0 m, max |E| 0.0 m, min clearance to square -1.0 m
$ ./run_lab.sh oa_nofence oa_nofence.parm "" oa_dijkstra_lab.py --no-enable
FENCE_ENABLE = 0
time 21.2 s, path 80.4 m vs straight 80.0 m, max |E| 0.0 m, min clearance to square -1.0 m
```

In both control runs the vehicle went through the square (`min clearance` −1 means "was inside"), and every `OADJ` record has `State = 0` ("not required"). This is a typical trap: `OA_TYPE` is set, but the planner sees no zone at all, and trying to enable the fence with a command after boot while the fence is disabled does not help. They also give the time of the straight flight: 21.2 s against 31.8 s with the detour; the extra 10.6 s come from 7 m of path and the stops at each intermediate point (bit 2 of `OA_OPTIONS` is off).

{{diagram:chart-nav-oa-dijkstra-track|The SITL track matched the Dijkstra plan to within 0.5 m in length: the zone vertices are moved out by 5/√2 = 3.54 m, the path is 87.0 m instead of 80 m and takes 31.8 s instead of 21.2 s because of the stops at the corners.}}

### Step 5. Flying around an obstacle in Gazebo
A world with a pillar on the square's path. Variant A (no code of your own): ArduPilot SITL with proximity from a simulated lidar, `OA_TYPE = 1`, a mission through the pillar; record the BendyRuler trajectory. Variant B (your own node): an occupancy grid from `/scan` or `OBSTACLE_DISTANCE`, A* + shortcut, setpoints through the state machine from ros2-px4. Compare the trajectories and times.

### Step 6. Unknown space
Repeat step 5 with `unknown_is_free=True` and `False`: find the place on the map where the "optimistic" planner routes the path through space not yet seen, and why that is dangerous.

### Moving to real hardware
Start with Dijkstra on a fence: it does not depend on a sensor. The setup: a vehicle with GPS, `OA_TYPE = 2`, `FENCE_ENABLE = 1`, `FENCE_TYPE` with the polygons bit, a 20 × 20 m exclusion polygon over an empty field 40 m from the takeoff point, altitude 15 m, `WP_SPD` = 3 m/s (in 4.7 the speed is in m/s; before 4.7, `WPNAV_SPEED` in cm/s). Before the flight, check on the ground: there was a reboot after `OA_TYPE` was changed (otherwise arming is refused with "Dijkstra OA requires reboot"), the fence is loaded (`FENCE_TOTAL` > 0), and the zone is visible in the mission planner. The first flight is in Guided with the pilot on the Loiter switch. Abort criterion: the vehicle heads straight for the zone closer than `OA_MARGIN_MAX` → Loiter, then analyze `OADJ` (if `State = 0`, the planner does not see the zone). Acceptance: the track goes around the zone, the minimum distance to it in the log is no less than 3 m, and the intermediate `OADJ` points match the bisector calculation within the GPS error (1–2 m). BendyRuler with a lidar comes only after this, with an obstacle made of soft material and a speed of 1–2 m/s.

Self-check: the lab is done when (computation and SITL) your planner test passes (the path with inflation is longer than without it, but not shorter than the straight line; 9 tests of 9), the step 2 script gave the same numbers as above (2290 / 785 / 537 expanded cells, 35.94 m; in the "forest" 37.85 m against 33.56 m), the safe speed from step 3 matches the reference below, and in step 4 the path around the square is 86–88 m, `max |E|` is 13.5 ± 0.5 m, the minimum clearance is 3.5 ± 0.3 m, `OADJ` contains `State = 2`, and the control run with `FENCE_ENABLE 0` goes through the square in 20–22 s with `State = 0`; (Gazebo) the trajectories and times of flying around the pillar are recorded (at least variant A), and in step 6 the map shows the place where with `unknown_is_free=True` the path goes through cells not yet seen; (hardware) the acceptance criteria of the section above are met.

**Reference for the self-check.** Step 3: the distance covered during the reaction time plus the braking distance is no more than the range minus the margin: v·0.3 + v²/(2·3) = 8 − 2, which gives v ≈ 5.2 m/s; with `CP_DELAY` 0.4 s, v ≈ 4.9 m/s. Typical wrong answers: 6.0 m/s means the reaction delay was forgotten (v = √(2·a·d) with d = 6 m); ≈ 6.9 m/s means the 2 m margin was not subtracted either. Step 4: `max |E|` ≈ 10 m (half the square) + 3.54 m; if you got 15 m, you applied a 5 m offset along the axis, while Dijkstra moves the vertex 5 m along the bisector; if `max |E|` is 0 m and the path is 80–81 m, the fence was not enabled at boot and `OADJ.State = 0`; if the vehicle flew at 10 m/s instead of 5, the parameter file still had `WPNAV_SPEED`, which 4.7 does not have. Step 6: with `unknown_is_free=False` the planner goes only where free space has already been seen; the "optimistic" variant is dangerous because it routes the path "through a wall" not seen yet.

{{diagram:chart-nav-brake-speed|A 0.3 s reaction delay cuts the safe speed at d = 6 m from 6.0 to 5.2 m/s, and a forgotten margin adds a further error, up to 6.9 m/s.}}

## diagnostics
- **Symptom:** the path runs right next to an obstacle, and the vehicle clips it
  - Possible cause: no inflation, or a radius smaller than the vehicle size + the position error.
  - What to do: inflation = radius + 2σ of position + margin.
- **Symptom:** the vehicle "jerks", and replanning every 100 ms changes the path
  - Possible cause: the global planner runs at the local rate, a noisy map.
  - What to do: a 1 Hz global plan, hysteresis on path changes, a map filter (log-odds).
- **Symptom:** the vehicle flies into an unknown area and loses the obstacle from view
  - Possible cause: unknown is treated as free; the sensor does not look where the vehicle is going.
  - What to do: unknown = occupied; yaw along the direction of travel.
- **Symptom:** the path setpoints lead the wrong way
  - Possible cause: a path in ENU was sent to PX4 as NED.
  - What to do: convert at the boundary (frames.py), test on a known point.
- **Symptom:** `OA_TYPE = 2`, yet the vehicle flies through the exclusion zone
  - What the log shows: `OADJ.State = 0` in every record.
  - Possible cause: the fence is disabled (`FENCE_ENABLE = 0`), or `FENCE_TYPE` lacks the polygons bit; the zone is not loaded.
  - What to do: `FENCE_ENABLE = 1`, the polygons bit in `FENCE_TYPE`, check `FENCE_TOTAL`; repeat step 4.
- **Symptom:** in Guided a position target does not avoid the zone, although Auto does
  - Possible cause: `GUID_OPTIONS` without bit 6, so the position bypasses WPNav and object avoidance.
  - What to do: `GUID_OPTIONS` += 64, or send the targets through a mission/`DO_REPOSITION`.
- **Symptom:** arming is refused after you set `OA_TYPE`
  - What the log shows: PreArm "BendyRuler OA requires reboot", "Dijkstra OA requires reboot" or "OA requires reboot", depending on the value of `OA_TYPE`.
  - What to do: reboot the flight controller; `OA_TYPE` creates the planner threads at startup.
- **Symptom:** PX4 in Mission or Offboard flies into an obstacle although `CP_DIST` is set
  - Possible cause: collision prevention works only in Position mode; the PX4-Avoidance interface is gone in 1.16+.
  - What to do: avoidance on the companion computer (`TrajectorySetpoint`), collision prevention as the line of defense for manual flight.
- **Symptom:** the vehicle stops in Guided in the middle of the path when the navigation node restarts
  - Possible cause: no velocity setpoint stream for longer than `GUID_TIMEOUT` (3 s; in PX4, `COM_OF_LOSS_T` 1 s).
  - What to do: that is by design; keep the setpoint node separate from the planner and stream setpoints at 20–50 Hz.

## references
- ArduPilot — Object avoidance (BendyRuler, Dijkstra) | https://ardupilot.org/copter/docs/common-object-avoidance-landing-page.html | primary | A
- ArduPilot 4.7.2 — AC_Avoidance (AC_Avoid, AP_OAPathPlanner, AP_OABendyRuler, AP_OADijkstra) | https://github.com/ArduPilot/ardupilot/tree/Copter-4.7.2/libraries/AC_Avoidance | primary | A
- PX4 — Collision prevention | https://docs.px4.io/v1.17/en/computer_vision/collision_prevention.html | primary | A
- PX4 v1.17.0 — collisionprevention_params.c | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/lib/collision_prevention/collisionprevention_params.c | primary | A
- Nav2 documentation | https://docs.nav2.org/ | primary | A
- navigation2 — README (list of `nav2_*` packages) | https://github.com/ros-navigation/navigation2 | primary | A
- OctoMap | https://octomap.github.io/ | primary | A
- Hart, Nilsson, Raphael — A formal basis for the heuristic determination of minimum cost paths (A*) | https://ieeexplore.ieee.org/document/4082128 | secondary | A

## checklist
- I know what BendyRuler/Dijkstra and collision prevention do without my own code, and in which modes
- I know that Dijkstra sees only an enabled fence and moves its vertices out by `OA_MARGIN_MAX` along the bisector
- I can tell an occupancy grid, a costmap and 3D representations apart; unknown is occupied; log-odds with clamping
- I implement A* with an admissible heuristic, inflation and smoothing; I understand the price of weighted A*
- I separate global and local planning by rates and roles
- I turn a path into setpoints with speed limits from the braking distance and account for the timeouts
- I understand where Nav2 is useful for a drone and where it is not
