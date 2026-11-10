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
