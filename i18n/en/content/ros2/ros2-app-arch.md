---
id: ros2-app-arch
title: "Onboard ROS 2 application architecture: nodes, lifecycle, watchdog"
level: L3
readingTime: 45 min
firmware: PX4 · ArduPilot
status: published
added: 2026-11-08
tags:
  - ROS 2
  - architecture
  - lifecycle
  - watchdog
  - deployment
related:
  - ros2-px4
  - eng-systems
  - comp-raspberry
next:
  - ros2-nav
source: content/ros2/ros2-app-arch.md
source_hash: 086713db5f3e
---

## summary
A single node that does everything works exactly until the first error in its least reliable part — usually perception. An onboard application must survive a camera dropout, a hung neural network and a process restart without losing control of the vehicle. This module gives you an architecture that makes that possible: a split into bridge, perception, decision and safeguards; managed nodes (lifecycle) with explicit states; a data-freshness watchdog with OK/DEGRADED/FAILSAFE levels and hysteresis; parameters and configuration; containers and autostart; debugging from bags and profiling. Lab: a four-node skeleton in which killing the perception node puts the system into DEGRADED and losing position puts it into FAILSAFE, verified by tests.

## theory
### Four roles
| Role | What it does | What it doesn't do | Criticality |
|---|---|---|---|
| **Bridge** (uXRCE-DDS agent / AP_DDS / MAVROS) | translates the autopilot protocol into topics | makes no decisions | critical |
| **Perception** | camera/lidar → targets, obstacles, pose | doesn't command the vehicle | non-critical (degradation) |
| **Decision** (mission, state machine) | picks setpoints from targets and state | doesn't read sensors directly | critical |
| **Safeguards** (watchdog, application geofence, battery) | watch freshness and limits, have veto power | don't plan | critical |

{{diagram:ros2-graph|Four roles in the node graph: bridge, perception, decision, safeguards.}}

The direction rule: decision subscribes to perception and to the safeguards; the safeguards can stop decision; perception knows nothing about decision. No non-critical node may sit on the “autopilot status → setpoints” path.

### Managed nodes (lifecycle)
A regular node starts working as soon as it is launched. A lifecycle node (`rclpy.lifecycle` / `rclcpp_lifecycle`) goes through explicit states: **unconfigured → inactive → active → finalized**, with the transitions `configure`, `activate`, `deactivate`, `cleanup`, `shutdown`, each with its own callback that can return an error. What this gives you on board:
- configuration (open the camera, load the model) is separated from operation — you see the error before takeoff;
- a node can be “paused” (deactivate) without killing the process — for example, to turn perception off during landing;
- a manager (`nav2_lifecycle_manager` or your own) brings the system up in the right order and knows who failed to come up.

{{diagram:ros2-lifecycle|Lifecycle node states: configuration is separated from operation, pausing doesn't kill the process.}}

{{diagram:ros2-executor-gaps|In one group with inference the 20 Hz setpoint timer waits: a 400 ms hang breaks the setpoint stream for 400 ms; inference in its own group on a second thread leaves an even 50 ms step.}}

### Freshness watchdog
Every input message has a maximum allowed age. The watchdog (`examples/ros2-docker/.../watchdog.py`, no ROS inside) stores the time of the last message for each input and outputs a single system level:
- **OK** — everything is fresh;
- **DEGRADED** — a non-critical input (targets from the camera) is stale: the mission continues, the function (tracking) is suspended;
- **FAILSAFE** — a critical input (autopilot status, pose) is stale: decision stops commanding and requests a hold/landing.

**Hysteresis:** an input counts as recovered only if it stays fresh continuously for `recover_s` (for example, 1 s) — otherwise a “flickering” camera will switch tracking on and off several times a second. The watchdog is a separate node with its own timer; it doesn't command the autopilot itself, it publishes the level that decision subscribes to. The last line of defense is the autopilot itself (Offboard/GUIDED timeouts): if the whole application crashes, the vehicle still switches to a safe mode.

### Parameters and configuration
Everything that differs between vehicles (camera offsets, thresholds, rates, topic names) goes into YAML parameters passed through launch. The `add_on_set_parameters_callback` callback validates new values (range, type) and can reject them — that way an operator in the field can't set a threshold of 10 m instead of 1 m. Secrets (VPN keys, cloud tokens) don't go into ROS parameters, but into files with access permissions or into the service's environment variables.

### Deployment
- **Container**: an image with ROS 2, the dependencies and your package; image version = onboard software version. `docker compose` with `restart: unless-stopped` and `network_mode: host` (DDS discovery inside containers on a bridge network is harder).
- **Autostart**: a systemd service that runs `ros2 launch` (or compose) after the network is up and after the serial port appears (`After=`, `BindsTo=dev-ttyAMA0.device`).
- **Logs**: `ros2 bag record` of the key topics, split into files (`--max-bag-duration`, `--max-bag-size`; automatic deletion of old files with `--max-bag-files` exists only in newer rosbag2 versions, in Humble/Jazzy you have to clean up disk space yourself) + journald; after an incident — download the bag together with the autopilot log.
- **Time**: chrony/NTP on the companion, synchronization with the autopilot (TIMESYNC/uXRCE) — otherwise the bag and the autopilot log won't line up.

### Debugging and profiling
- Replaying a bag into the decision and safeguard nodes (module ros2-basics) is the main tool.
- `ros2 topic hz/bw/delay` — rate, bandwidth and latency relative to `header.stamp`.
- Profiling: `top`/`htop` per process, `py-spy record` for Python nodes, `ros2_tracing` (LTTng) for callback latencies; on a Jetson — `tegrastats` (CPU/GPU/temperature).
- Executor: heavy callbacks (the neural network) go into a separate callback group (`MutuallyExclusiveCallbackGroup`) with a `MultiThreadedExecutor`, otherwise the 20 Hz setpoint timer will wait for inference to finish.

## practice
### Step 1. Watchdog tests
```bash
cd examples/ros2-docker/ws/src/uav_ros2_labs
python -m pytest -q test/test_watchdog.py
```
Work through `test_hysteresis_on_flapping_input`: why the level is still DEGRADED after 0.5 s of recovery.

### Step 2. A four-node skeleton
Build a `uav_app` package with the nodes `bridge_monitor` (subscribes to autopilot status/pose), `perception_stub` (publishes targets at 10 Hz, crashes on command), `watchdog_node` (a wrapper around `watchdog.py`, publishes the level and the reasons), `decision_node` (the state machine from ros2-px4, subscribed to the level). A launch file with parameters from YAML.

### Step 3. Perception and position failures
In SITL: start a tracking mission (`perception_stub` provides a target), then `kill -9` the perception process → level DEGRADED, the vehicle holds position, the mission doesn't abort; bring the node back up → OK after `recover_s`. Then stop the bridge (the agent) → FAILSAFE, decision stops sending setpoints; confirm from the autopilot log that its own timeout fired.

### Step 4. Autostart
Write a systemd unit (or compose with restart) for the companion: start after the network, restart on crash, ring-buffer bag recording. Reboot the machine/container and show that the system came up on its own.

The lab counts as done when the watchdog tests pass, the four-node skeleton handles both failures in SITL (with logs) and you have a working autostart.

```python
import os
import rclpy
from rclpy.lifecycle import LifecycleNode, LifecycleState, TransitionCallbackReturn
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import PointStamped

class Perception(LifecycleNode):
    def __init__(self):
        super().__init__("perception")
        self.declare_parameter("model_path", "/opt/models/det.onnx")
        self.pub = None
        self.timer = None

    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        path = self.get_parameter("model_path").value
        if not os.path.exists(path):
            self.get_logger().error(f"model not found: {path}")
            return TransitionCallbackReturn.FAILURE          # back to Unconfigured, visible before take-off
        self.pub = self.create_lifecycle_publisher(PointStamped, "targets", qos_profile_sensor_data)
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.timer = self.create_timer(1 / 15, self.step)    # work starts only here
        return super().on_activate(state)                    # enables lifecycle publishers

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.destroy_timer(self.timer)                       # timers do NOT pause by themselves
        self.timer = None
        return super().on_deactivate(state)

    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.destroy_lifecycle_publisher(self.pub)
        self.pub = None
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: LifecycleState) -> TransitionCallbackReturn:
        if self.timer:                                       # shutdown may come straight from Active
            self.destroy_timer(self.timer)
            self.timer = None
        return TransitionCallbackReturn.SUCCESS

    def step(self):
        msg = PointStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        self.pub.publish(msg)

def main():
    rclpy.init()
    rclpy.spin(Perception())

if __name__ == "__main__":
    main()
```

```python
"""Request-vs-offered QoS check (rules: ROS 2 docs, 'QoS compatibilities'). No ROS needed."""
INF = float("inf")                      # "default" duration = unspecified = infinite
REL = {"best_effort": 0, "reliable": 1}
DUR = {"volatile": 0, "transient_local": 1}
LIV = {"automatic": 0, "manual_by_topic": 1}

def compatible(pub, sub):
    """pub offers, sub requests; returns list of reasons why there is NO connection."""
    why = []
    if REL[pub["rel"]] < REL[sub["rel"]]:
        why.append("reliability: BEST_EFFORT offered, RELIABLE requested")
    if DUR[pub["dur"]] < DUR[sub["dur"]]:
        why.append("durability: VOLATILE offered, TRANSIENT_LOCAL requested")
    if pub.get("deadline", INF) > sub.get("deadline", INF):
        why.append(f"deadline: offered {pub.get('deadline', INF)} s > requested {sub.get('deadline', INF)} s")
    if LIV[pub.get("liv", "automatic")] < LIV[sub.get("liv", "automatic")]:
        why.append("liveliness: AUTOMATIC offered, MANUAL_BY_TOPIC requested")
    if pub.get("lease", INF) > sub.get("lease", INF):
        why.append("lease duration: offered longer than requested")
    return why

DEFAULT = dict(rel="reliable", dur="volatile")            # rmw_qos_profile_default, depth 10
SENSOR = dict(rel="best_effort", dur="volatile")          # rmw_qos_profile_sensor_data, depth 5
cases = [
    # topic, publisher (offered), subscriber (requested)
    ("/fmu/out/vehicle_odometry  PX4 -> default sub", dict(rel="best_effort", dur="transient_local"), DEFAULT),
    ("/fmu/out/vehicle_odometry  PX4 -> sensor_data", dict(rel="best_effort", dur="transient_local"), SENSOR),
    ("/fmu/in/trajectory_setpoint default pub -> PX4", DEFAULT, dict(rel="best_effort", dur="volatile")),
    ("/ap/pose/filtered          AP  -> default sub", dict(rel="best_effort", dur="volatile"), DEFAULT),
    ("/ap/status                 AP  -> latched sub", dict(rel="reliable", dur="transient_local"),
     dict(rel="reliable", dur="transient_local")),
    ("/app/level  watchdog default -> latched sub", DEFAULT, dict(rel="reliable", dur="transient_local")),
    ("/app/targets 10 Hz, deadline 0.2 -> sub deadline 0.15", dict(SENSOR, deadline=0.2), dict(SENSOR, deadline=0.15)),
    ("/app/targets 10 Hz, deadline 0.2 -> sub deadline 0.5", dict(SENSOR, deadline=0.2), dict(SENSOR, deadline=0.5)),
]
for name, p, s in cases:
    why = compatible(p, s)
    print(f"{'OK ' if not why else 'NO '} {name}" + ("" if not why else "\n      " + "; ".join(why)))
```

```text
NO  /fmu/out/vehicle_odometry  PX4 -> default sub
      reliability: BEST_EFFORT offered, RELIABLE requested
OK  /fmu/out/vehicle_odometry  PX4 -> sensor_data
OK  /fmu/in/trajectory_setpoint default pub -> PX4
NO  /ap/pose/filtered          AP  -> default sub
      reliability: BEST_EFFORT offered, RELIABLE requested
OK  /ap/status                 AP  -> latched sub
NO  /app/level  watchdog default -> latched sub
      durability: VOLATILE offered, TRANSIENT_LOCAL requested
NO  /app/targets 10 Hz, deadline 0.2 -> sub deadline 0.15
      deadline: offered 0.2 s > requested 0.15 s
OK  /app/targets 10 Hz, deadline 0.2 -> sub deadline 0.5
```

```python
"""Executor model (not rclpy): N worker threads; like rclpy, ready timers are taken before ready
subscriptions, then the oldest first; a MutuallyExclusive
group runs one callback at a time; a node's default group is MutuallyExclusive; an overdue timer fires
once (missed periods are skipped), the camera subscription is KEEP_LAST 1."""
SOURCES = [("setpoint", 0.050, 0.001),        # 20 Hz timer, 1 ms
           ("watchdog", 0.100, 0.0005),       # 10 Hz timer
           ("inference", 1 / 15, 0.060)]      # camera 15 Hz, 60 ms per frame

def simulate(threads, group_of, T=30.0):
    jobs = []
    for name, per, cost in SOURCES:
        for k in range(round(T / per)):
            stall = name == "inference" and k > 0 and k % 45 == 0      # 400 ms stall every 3 s
            jobs.append((k * per, name, 0.400 if stall else cost))
    jobs.sort()
    free, busy, late, starts, skipped = [0.0] * threads, {}, [], [], {"setpoint": 0, "inference": 0}
    while jobs:
        w = min(range(threads), key=free.__getitem__)
        now = free[w]
        for src in ("setpoint", "watchdog", "inference"):
            due = [j for j in jobs if j[1] == src and j[0] <= now]
            for old in due[:-1]:                  # only the newest tick / frame survives
                jobs.remove(old)
                if src in skipped:
                    skipped[src] += 1
        ready = [j for j in jobs if j[0] <= now and busy.get(group_of[j[1]], 0) <= now]
        if not ready:                             # sleep until something can run
            free[w] = min(max(j[0], busy.get(group_of[j[1]], 0)) for j in jobs)
            continue
        ready.sort(key=lambda j: (j[1] == "inference", j[0]))    # timers first, then subscriptions
        t, name, cost = ready[0]
        jobs.remove(ready[0])
        free[w] = busy[group_of[name]] = now + cost
        if name == "setpoint":
            starts.append(now); late.append(now - t)
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    late.sort()
    return max(gaps), late[int(0.99 * len(late))], skipped["setpoint"], skipped["inference"]

for label, n, groups in [
        ("SingleThreadedExecutor, one default group", 1, dict(setpoint="A", watchdog="A", inference="A")),
        ("MultiThreaded(2), one default group", 2, dict(setpoint="A", watchdog="A", inference="A")),
        ("MultiThreaded(2), inference in own ME group", 2, dict(setpoint="A", watchdog="A", inference="B"))]:
    gap, p99, sp, fr = simulate(n, groups)
    print(f"{label:<45s} max gap {gap*1000:3.0f} ms  p99 late {p99*1000:3.0f} ms  "
          f"setpoints skipped {sp:3d}  frames dropped {fr}")
```

```text
SingleThreadedExecutor, one default group     max gap 402 ms  p99 late  43 ms  setpoints skipped 115  frames dropped 45
MultiThreaded(2), one default group           max gap 402 ms  p99 late  43 ms  setpoints skipped 115  frames dropped 45
MultiThreaded(2), inference in own ME group   max gap  50 ms  p99 late   0 ms  setpoints skipped   0  frames dropped 45
```

## diagnostics
- **Symptom:** when the neural network hangs, the vehicle “freezes” with its setpoints
  - Possible cause: inference and the setpoint timer are on the same executor thread.
  - What to do: separate callback groups, MultiThreadedExecutor, or perception as a separate process.
- **Symptom:** tracking switches on and off several times a second
  - Possible cause: no hysteresis on input recovery.
  - What to do: recover_s ≥ 0.5–1 s.
- **Symptom:** after the companion reboots, the application doesn't start
  - Possible cause: the service starts before the serial port/network appears.
  - What to do: systemd dependencies (After/BindsTo), connection retries in the bridge.
- **Symptom:** the bag and the autopilot log don't line up in time
  - Possible cause: the companion's clock isn't synchronized.
  - What to do: chrony, use the autopilot's timestamps in the messages.

## references
- ROS 2 — Managed nodes (lifecycle) design | https://design.ros2.org/articles/node_lifecycle.html | primary | A
- ROS 2 Jazzy — Executors and callback groups | https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Executors.html | primary | A
- ros2_tracing | https://github.com/ros2/ros2_tracing | primary | A
- Nav2 — lifecycle manager | https://api.nav2.org/nav2-jazzy/html/md_nav2_lifecycle_manager_README.html | primary | A

## checklist
- I split the application into bridge, perception, decision and safeguards with the right dependencies
- I use lifecycle nodes and understand their states
- I build a freshness watchdog with levels and hysteresis
- I move configuration into parameters with value validation
- I deploy in a container with autostart and ring-buffer bag recording
- I debug from bags and profile nodes, and spread heavy callbacks across groups
