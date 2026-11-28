---
id: ros2-app-arch
title: "Onboard application architecture on ROS 2: nodes, lifecycle, watchdog"
level: L3
readingTime: 65 min
firmware: ROS 2 Jazzy · PX4 1.18 · ArduPilot 4.7
status: published
added: 2026-11-08
tags:
  - ROS 2
  - architecture
  - lifecycle
  - watchdog
  - deployment
  - QoS
  - executor
related:
  - ros2-basics
  - ros2-px4
  - eng-systems
  - comp-raspberry
next:
  - ros2-nav
source: content/ros2/ros2-app-arch.md
source_hash: 76e0f3b35d6e
---

## summary
A single node that does everything works only until the first bug in its least reliable part, usually perception. An onboard application has to survive a camera crash, a hung neural network and a process restart without losing control of the vehicle. This module gives you an architecture that achieves this: a split into bridge, perception, decision and safeguards; managed (lifecycle) nodes with explicit states; a data freshness watchdog with OK/DEGRADED/FAILSAFE levels and hysteresis; parameters and configuration; containers and autostart; debugging with bags and profiling. Lab: a skeleton of four nodes in which killing the perception node puts the system into DEGRADED and losing the position puts it into FAILSAFE, and tests check both. Without ROS you check the graph's QoS matrix with the RxO rule and an executor model that shows why a MultiThreadedExecutor without your own callback groups does not protect the setpoints from a hung inference.

## theory
### Four roles
| Role | What it does | What it does not do | Criticality |
|---|---|---|---|
| **Bridge** (uXRCE-DDS agent / AP_DDS / MAVROS) | translates the autopilot protocol into topics | makes no decisions | critical |
| **Perception** | camera/lidar → targets, obstacles, pose | does not command the vehicle | non-critical (degradation) |
| **Decision** (mission, state machine) | chooses setpoints from targets and state | does not read sensors directly | critical |
| **Safeguards** (watchdog, application geofence, battery) | watch freshness and limits, hold a veto | do not plan | critical |

{{diagram:ros2-graph|The four roles in the node graph: bridge, perception, decision, safeguards.}}

The direction rule: decision subscribes to perception and to the safeguards; the safeguards can stop decision; perception does not know about decision. No non-critical node may sit on the "autopilot status → setpoints" path.

### Managed nodes (lifecycle)
An ordinary node starts working as soon as it is launched. A lifecycle node (`rclpy.lifecycle` / `rclcpp_lifecycle`) goes through explicit states: **unconfigured → inactive → active → finalized**, with the transitions `configure`, `activate`, `deactivate`, `cleanup`, `shutdown`, each with its own callback that can return an error. What this gives you on board:
- configuration (open the camera, load the model) is separated from operation, so you see the error before takeoff;
- you can "pause" a node (deactivate) without killing the process, for example to turn perception off for landing;
- a manager (`nav2_lifecycle_manager` or your own) brings the system up in the right order and knows who failed to come up.

{{diagram:ros2-lifecycle|Lifecycle node states: configuration is separate from operation, and a pause does not kill the process.}}

The mechanics you need to know exactly (the managed nodes design document and the `rcl_lifecycle` implementation, jazzy branch):
- Besides the four primary states there are **transition** states: Configuring, Activating, Deactivating, CleaningUp, ShuttingDown and ErrorProcessing. While a transition callback runs, the node is in a transition state.
- A callback returns `TransitionCallbackReturn.SUCCESS`, `FAILURE` or `ERROR`. FAILURE in `on_configure` returns the node to Unconfigured, FAILURE in `on_activate` to Inactive (`default_state_machine.c`, the `ON_ACTIVATE_FAILURE` transition). ERROR and an unhandled exception lead to ErrorProcessing. From there a successful `on_error` returns the node to Unconfigured, and an unsuccessful one takes it to Finalized. The practical rule: "model file missing" is a FAILURE (you can fix it and retry), "camera driver crashed" is an ERROR.
- In the inactive state **only lifecycle publishers go silent** (`create_lifecycle_publisher`; `publish()` is wrapped in an "is it enabled" check). Timers, subscriptions and ordinary publishers keep running. That is why the timer is created in `on_activate` and destroyed in `on_deactivate`; otherwise a "paused" perception node keeps loading the CPU.
- A node can be controlled from outside: the services `/<node>/change_state`, `get_state`, `get_available_transitions` and the topic `/<node>/transition_event`; in the CLI, `ros2 lifecycle set /perception configure` and `ros2 lifecycle get /perception`. In a launch file this is done by `launch_ros.actions.LifecycleNode` and `LifecycleTransition`. Nav2 has a ready-made manager (`nav2_lifecycle_manager`): the parameters `node_names`, `autostart` (default `false`), `bond_timeout` (4.0 s). The node must hold a bond, as `nav2_util::LifecycleNode` does. A plain LifecycleNode from rclpy or rclcpp has no bond, so for your own nodes you set `bond_timeout: 0.0`, or the manager will not bring the system up ("unable to be reached … by bond"). If a bond breaks, the manager does a hard reset of the whole group (deactivate → cleanup).

A perception node skeleton in rclpy (Jazzy). The API is checked against the rclpy source on the jazzy branch; the course sandbox has no ROS 2, so the code was not run:

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

### Freshness watchdog
Every input message has a maximum allowed age. The watchdog (`examples/ros2-docker/.../watchdog.py`, no ROS inside) keeps the time of the last message for each input and outputs a single system level:
- **OK**: everything is fresh;
- **DEGRADED**: a non-critical input (targets from the camera) is stale: the mission continues, the function (tracking) is suspended;
- **FAILSAFE**: a critical input (autopilot status, pose) is stale: decision stops commanding and requests a hold/landing.

**Hysteresis:** an input counts as recovered only if it has been fresh continuously for `recover_s` (for example, 1 s); otherwise a "flickering" camera will switch tracking on and off several times a second. The watchdog is a separate node with its own timer; it does not command the autopilot itself, but publishes the level that decision subscribes to. The last line of defense is the autopilot itself. PX4 uses `COM_OF_LOSS_T` to leave Offboard for the mode from `COM_OBL_RC_ACT`. ArduPilot stays in GUIDED and after `GUID_TIMEOUT` stops and hovers: in the log you see this as the target velocity dropping to zero, not as a failsafe event. If the whole application crashes, the vehicle will not keep flying on the last setpoint.

### Parameters and configuration
Everything that differs between vehicles (camera offsets, thresholds, rates, topic names) goes into YAML parameters passed through the launch file. The `add_on_set_parameters_callback` callback validates new values (range, type) and can reject them, so an operator in the field cannot set a 10 m threshold instead of 1 m. Secrets (VPN keys, cloud tokens) do not belong in ROS parameters, but in files with access permissions or in the service's environment variables.

The validation order in rclpy (Jazzy, `node.py`) is as follows. `add_pre_set_parameters_callback` can modify or extend the list before validation. `add_on_set_parameters_callback` answers with `SetParametersResult(successful=False, reason=...)`, and then the change is rejected as a whole. `add_post_set_parameters_callback` is called after the change is applied: that is where you rebuild whatever depends on the parameter. Ranges and "read only" are declared already in `declare_parameter` through a `ParameterDescriptor` (`floating_point_range`, `read_only=True`), so simple bounds need no callback of your own. The YAML for launch is `<node_name>: ros__parameters: {...}`, one file per vehicle: `quad_07.yaml` lives in git next to the autopilot config (`eng-ci-configs`).

### Processes, nodes and components
A process boundary is a failure boundary. A node that crashes with an exception or is killed by the OOM killer takes everything running in its process down with it. Hence the placement rule: **perception goes in its own process**, separate from decision and the safeguards. Then a `kill -9` of the detector in the lab gives DEGRADED, not silence across the whole vehicle.

The flip side is copying. A 1280×720 RGB frame takes 2.76 MB, and at 30 frames/s inter-process transport over DDS moves about 83 MB/s. For heavy streams C++ has **composition**. The nodes are written as components (`rclcpp_components`, the `RCLCPP_COMPONENTS_REGISTER_NODE` macro) and loaded into one container: `component_container` (one thread), `component_container_mt` (MultiThreadedExecutor), `component_container_isolated` (its own executor per component). In a launch file this is done by `ComposableNodeContainer` and `ComposableNode` with `extra_arguments=[{"use_intra_process_comms": True}]`. Inside the process a message is passed by pointer, without serialization. rclpy has no component mechanism (a conclusion from the documentation: composition is described only for rclcpp), so Python nodes are separate processes. A typical layout: the camera driver and the detector in one C++ container (a shared failure is acceptable, both are perception); decision, the watchdog and the bridge in their own processes.

### Executors and callback groups
The executor decides which ready callback runs and on which thread. The options:
- `SingleThreadedExecutor` (the default in `rclpy.spin`): one thread, callbacks run strictly one after another;
- `MultiThreadedExecutor(num_threads)`: a thread pool. In rclpy the default number of threads is the number of cores available to the process (`os.sched_getaffinity`; `executors.py`, jazzy branch);
- event-driven: `rclcpp::experimental::executors::EventsExecutor`, and in rclpy `rclpy.experimental.EventsExecutor` (experimental; it appeared in Kilted and was backported to Jazzy with rclpy 7.1.4, April 2025; Humble does not have it); Lyrical adds `rclcpp::executors::EventsCBGExecutor` for rclcpp, which is multithreaded and, per the release notes, uses 10–15 % less CPU than the Single/MultiThreaded executors.

Whether callbacks run in parallel is decided by **callback groups**. A `MutuallyExclusiveCallbackGroup` runs its callbacks one at a time; a `ReentrantCallbackGroup` lets them run concurrently, including the same callback. The main trap: a node has a default group, and it is **MutuallyExclusive** (`node.py`: `_default_callback_group = MutuallyExclusiveCallbackGroup()`). If you just swap the executor for a MultiThreaded one and do not spread the callbacks over groups, nothing changes: the inference and the setpoint timer stay in the same mutually exclusive group. The model from the lab (step 3) shows this in numbers. A single-threaded executor and a MultiThreaded one with the default group give the same maximum setpoint gap, 402 ms, and 19 % of the timer ticks are skipped. A separate group for the inference restores an even 50 ms.

{{diagram:ros2-executor-gaps|In one group with the inference, the 20 Hz setpoint timer waits: a 400 ms stall breaks the setpoint stream for 400 ms; with the inference in its own group on a second thread, the step stays an even 50 ms.}}

Two caveats for Python. First: rclpy threads are ordinary Python threads. Pure Python code holds the GIL, so there is no parallelism; numpy and onnxruntime release the GIL while they compute, and then threads help. Second: for heavy perception a separate process is more reliable. A 402 ms gap does not exceed `COM_OF_LOSS_T` (PX4 1.17/1.18, 1.0 s by default) or `GUID_TIMEOUT` (3 s), but a stall of more than a second while loading a model or collecting garbage already takes PX4 out of Offboard (`ros2-px4`), and ArduPilot stops the vehicle in GUIDED after 3 s.

### QoS by topic class
Compatibility is computed with the "requested versus offered" (RxO) model. There is a connection only if for **every** policy the subscriber requests no more than the publisher offers: reliability (BEST_EFFORT < RELIABLE), durability (VOLATILE < TRANSIENT_LOCAL), deadline (the requested one no shorter than the offered one), liveliness (AUTOMATIC < MANUAL_BY_TOPIC) and lease duration. An incompatibility raises no exception: an "incompatible QoS" warning goes to the log, the subscriber stays silent, and both sides get `requested/offered incompatible QoS` events. The basics and the `topic info -v` diagnostics are covered in `ros2-basics`; here we choose the profile by the topic's role.

{{lesson:ros2-basics|QoS from scratch: why a RELIABLE subscription to a BEST_EFFORT PX4 publisher is silent and how to see it in `ros2 topic info -v`.}}

| Topic class | Reliability | Durability | History / depth | Deadline | Example and source |
|---|---|---|---|---|---|
| Sensor stream (camera, IMU, detector targets) | BEST_EFFORT | VOLATILE | KEEP_LAST 1–5 | period × 2 (course guideline) | `qos_profile_sensor_data`: BEST_EFFORT, VOLATILE, depth 5 (`rmw/qos_profiles.h`) |
| Autopilot telemetry | as the bridge offers | as the bridge offers | KEEP_LAST 1–5 | — | PX4 `/fmu/out/*`: BEST_EFFORT + TRANSIENT_LOCAL (`uxrce_dds_client/utilities.hpp:79-80`); AP `/ap/pose/filtered`: BEST_EFFORT, VOLATILE, depth 5 |
| Setpoints and commands to the autopilot | BEST_EFFORT (receiving side) | VOLATILE | KEEP_LAST 1 | — | PX4 reader `/fmu/in/*`: BEST_EFFORT, VOLATILE (`utilities.hpp:136-137`); AP `/ap/cmd_vel`: BEST_EFFORT, depth 5 |
| State "for late joiners" (watchdog level, mission mode) | RELIABLE | TRANSIENT_LOCAL | KEEP_LAST 1 | — | AP `/ap/status`: RELIABLE + TRANSIENT_LOCAL, depth 1 (`AP_DDS_Topic_Table.h:324-331`) |
| Parameters, services | RELIABLE | VOLATILE | 1000 / 10 | — | `qos_profile_parameters` depth 1000; services are VOLATILE so that a restarted server does not receive old requests |

Why. A stale setpoint or frame is useless: RELIABLE redelivery only adds latency when Wi-Fi drops packets. The system level, on the contrary, is needed even by a late subscriber: a decision node restarted by systemd after 2 s must learn at once that the level is FAILSAFE right now, not wait for the next change. TRANSIENT_LOCAL is for exactly that, and it works only if **both** sides set it. Deadline is a freshness detector built into DDS: a subscription with `deadline = 0.2 s` gets a "requested deadline missed" event if no targets arrive for 0.2 s. It is a good input for the watchdog, but not a replacement for it: deadline has no hysteresis. The RxO rule implies a trap: a publisher with a deadline of 0.2 s and a subscriber that requested 0.15 s do not connect at all.

### ROS 2 distributions as of November 2026

| Distribution | Release | End of support | Tier 1 platform | For onboard use now |
|---|---|---|---|---|
| Humble Hawksbill (LTS) | May 2022 | May 2027 | Ubuntu 22.04 | maintenance of old projects only |
| Jazzy Jalisco (LTS) | May 2024 | May 2029 | Ubuntu 24.04 | the main choice; the course's `examples/ros2-docker` runs on it |
| Kilted Kaiju | May 2025 | November–December 2026 | Ubuntu 24.04 | do not start: support is ending |
| Lyrical Luth (LTS) | May 22, 2026 | May 2031 | Ubuntu 26.04 | new projects, if the companion image is already on 26.04 |

The dates follow the Distributions page of the ROS 2 documentation and REP 2000; Lyrical is not in REP 2000 yet, so its platform follows the Supported Platforms page. For Kilted they disagree: the page says December 2026, REP 2000 says November 2026. Nodes from different distributions are not required to talk to each other, so the companion computer, a ground station with ROS and the bag player must run the same distribution.

### Deployment
- **Container**: an image with ROS 2, the dependencies and your package; the image version = the onboard software version. `docker compose` with `restart: unless-stopped` and `network_mode: host` (DDS discovery inside containers on a bridge network is harder).
- **Autostart**: a systemd service that runs `ros2 launch` (or compose) after the network and after the serial port appears (`After=`, `BindsTo=dev-ttyAMA0.device`).
- **Logs**: `ros2 bag record` of the key topics, split into files (`-d/--max-bag-duration` in seconds, `-b/--max-bag-size` in bytes; circular deletion of old files with `--max-bag-files` arrived in rosbag2 for Lyrical and requires one of the two previous flags; Humble, Jazzy and Kilted do not have it, so there a script of your own or a systemd timer cleans up the disk) + journald; after an incident, download the bag together with the autopilot log.
- **Time**: chrony/NTP on the companion computer and synchronization with the autopilot (TIMESYNC/uXRCE); otherwise the bag and the autopilot log cannot be aligned.

### Debugging and profiling
- Replaying a bag into the decision and safeguard nodes (module ros2-basics) is the main tool.
- `ros2 topic hz/bw/delay`: rate, bandwidth and delay relative to `header.stamp`.
- Profiling: `top`/`htop` per process, `py-spy record` for Python nodes, `ros2_tracing` (LTTng) for callback latencies; on a Jetson, `tegrastats` (CPU/GPU/temperature).
- Executor: heavy callbacks (the neural network) go into a separate callback group (`MutuallyExclusiveCallbackGroup`) with a `MultiThreadedExecutor`; otherwise the 20 Hz setpoint timer waits for the inference to finish.

### API reference table (Jazzy; differences in other distributions noted)

| What | rclpy | rclcpp / CLI | Note |
|---|---|---|---|
| Lifecycle node | `rclpy.lifecycle.LifecycleNode` (alias `Node`) | `rclcpp_lifecycle::LifecycleNode` | callbacks `on_configure/activate/deactivate/cleanup/shutdown/error` |
| Transition result | `TransitionCallbackReturn.SUCCESS / FAILURE / ERROR` | `CallbackReturn::SUCCESS / FAILURE / ERROR` | FAILURE in activate → Inactive, ERROR → ErrorProcessing |
| Publisher that goes silent in Inactive | `create_lifecycle_publisher` | `create_publisher` on a lifecycle node | timers and subscriptions do not pause by themselves |
| Controlling transitions | service `/<node>/change_state` | `ros2 lifecycle set/get/list/nodes` | launch: `LifecycleNode`, `LifecycleTransition` |
| Manager | — | `nav2_lifecycle_manager` | `autostart` = false, `bond_timeout` = 4.0 s (0.0 for nodes without a bond) |
| Executors | `SingleThreadedExecutor`, `MultiThreadedExecutor(num_threads)` | `rclcpp::executors::*` | rclpy: threads = number of available cores |
| Event-driven executor | `rclpy.experimental.EventsExecutor` (Kilted; Jazzy since rclpy 7.1.4) | `rclcpp::experimental::executors::EventsExecutor` (experimental); `rclcpp::executors::EventsCBGExecutor` (Lyrical) | not in rclpy for Humble |
| Callback groups | `MutuallyExclusiveCallbackGroup`, `ReentrantCallbackGroup` | the same in `rclcpp::CallbackGroupType` | a node's default group is MutuallyExclusive |
| Composition | none | `rclcpp_components`, `component_container(_mt/_isolated)` | `use_intra_process_comms: True` |
| QoS profiles | `qos_profile_sensor_data`, `QoSProfile(depth=10)` | `rclcpp::SensorDataQoS()`, `rclcpp::QoS(10)` | default is RELIABLE, VOLATILE, KEEP_LAST 10 |
| Parameter validation | `add_pre_set_/add_on_set_/add_post_set_parameters_callback` | the same in rclcpp | `ParameterDescriptor(read_only, floating_point_range)` |
| Recording a bag | — | `ros2 bag record -d 60 -b 500000000` | `--max-bag-files` only since Lyrical |

### Place in the system

- **Receives:** the autopilot status and pose through the bridge (`ros2-px4`, `ros2-ardupilot`); targets from the perception node (`per-cv`); time synchronized with the autopilot.
- **Provides:** setpoints from the decision node to the bridge and on to the autopilot; the OK/DEGRADED/FAILSAFE level to decision; a bag of the key topics for analysis together with the autopilot log (`ros2-basics`). The last line of defense stays with the autopilot: the Offboard and GUIDED timeouts.
- **If you get it wrong here:** the inference in one executor with the setpoint timer → the 20 Hz stream breaks → PX4 leaves Offboard (`ros2-px4`). No time synchronization between the companion computer and the autopilot → the bag and the autopilot log cannot be aligned, and incident analysis is impossible (`ap-logs`).

## practice
Steps 1–3 are plain Python; they were run in the course sandbox and the output is pasted unedited. Steps 4–6 need ROS 2 Jazzy and SITL (`examples/ros2-docker`): the sandbox where this module was written has no ROS 2, so their result is described as expected, and the criteria are given for checking on your own machine.

### Step 1. Watchdog tests
```bash
cd examples/ros2-docker/ws/src/uav_ros2_labs
python -m pytest -q test/test_watchdog.py
```
Result in the sandbox (Python 3.13): `5 passed in 0.01s`. Take apart `test_hysteresis_on_flapping_input`. The `targets` input disappeared for 1 s and came back for 0.5 s, and the level is still DEGRADED; after another 0.6 s it is OK. Explain why.

### Step 2. The QoS matrix of your graph without ROS
Before running the nodes, check whether they will connect. The script below implements the RxO rules from the ROS 2 documentation (reliability, durability, deadline, liveliness, lease duration). The bridge profiles come from the source: PX4 1.17/1.18 `uxrce_dds_client/utilities.hpp`, ArduPilot 4.7.2 `AP_DDS_Topic_Table.h`. Add every topic of your application to `cases` with the profiles you intend to set.

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

Two of the NO lines are familiar from `ros2-basics`: a default (RELIABLE) subscriber to BEST_EFFORT telemetry. The third is an architectural mistake from this module: the watchdog publishes the level with the default profile (VOLATILE), while the decision node requested TRANSIENT_LOCAL so that it learns the current level right after a restart. There is no connection at all. The fix is TRANSIENT_LOCAL on the publisher. The fourth is the deadline: the subscriber wants messages more often than the publisher promises. Setpoints to PX4 from a default (RELIABLE) publisher do connect: RELIABLE offers more than BEST_EFFORT requests.

### Step 3. An executor model: who waits for whom
The model is not rclpy but its rules in 46 lines: N threads; as in rclpy (`_wait_for_ready_callbacks`), ready timers are taken before ready subscriptions, and among equals the oldest first; a mutually exclusive group runs one callback at a time, an overdue timer fires once (missed periods are not caught up), and the camera is KEEP_LAST 1. The load: a 20 Hz setpoint timer (1 ms), a 10 Hz watchdog, inference at 15 frames/s at 60 ms each, and every 3 s a 400 ms stall (garbage collection, lazy model loading). 30 s of model time.

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

The first two lines are identical: the second thread sits idle because all the callbacks are in the default group, and it is MutuallyExclusive. The maximum setpoint gap of 402 ms is the 400 ms stall plus the rest of a step: right after the stall the timer runs before the next frame. 115 of the 600 timer ticks are skipped. Even without stalls (replace `k % 45 == 0` with `False`) a 60 ms callback in one group with a 50 ms timer eats 63 of 600 ticks: the gap reaches 67 ms, and the p99 lateness is 43 ms. A separate group for the inference restores an even 50 ms step with no skips. The 45 lost frames are the same in every variant: in 30 s there are nine stalls, each skips five frames, and KEEP_LAST 1 drops them, so after a stall the detector takes a fresh frame instead of working through a queue. Experiment yourself. With `threads=1` and different groups the gap is 402 ms again: without a second thread, groups do not help. With 80 ms inference (slower than the camera: 66.7 ms per frame) 102 frames are already lost, while setpoints with a separate group still go out at a 50 ms step.

### Step 4. A skeleton of four nodes
Build a package `uav_app` with the nodes `bridge_monitor` (subscribes to the autopilot status/pose), `perception_stub` (publishes targets at 10 Hz, crashes on command), `watchdog_node` (a wrapper around `watchdog.py` that publishes the level and the reasons), `decision_node` (the state machine from ros2-px4, subscribed to the level). A launch file with parameters from YAML. The QoS profiles come from the theory table and are checked with step 2: the watchdog level is RELIABLE + TRANSIENT_LOCAL, the targets use `qos_profile_sensor_data`; `perception_stub` is a lifecycle node following the skeleton from the theory, with the inference callback in its own group.

### Step 5. Perception and position failures
In SITL: start a tracking mission (`perception_stub` provides a target), then `kill -9` the perception process → the level is DEGRADED, the vehicle holds position, and the mission does not abort in an emergency; bring the node back up → OK after `recover_s`. Then stop the bridge (the agent) → FAILSAFE, decision stops the setpoints; confirm in the autopilot log that its own timeout fired (PX4 leaves Offboard; ArduPilot stops in GUIDED and the target velocity goes to zero). Additionally: `ros2 lifecycle set /perception_stub deactivate`: the targets stop being published without killing the process, and the level is DEGRADED; `activate`: OK again after `recover_s`.

### Step 6. Autostart
Write a systemd unit (or compose with restart) for the companion computer: start after the network, restart on crash, circular bag recording. Reboot the machine/container and confirm that the system came up by itself: without a single manual command, `ros2 node list` shows all four nodes.

### Moving to real hardware
On a companion computer connected to the autopilot, **props removed**, powered from the battery through the standard BEC. (1) Start the system through systemd and run `ros2 topic hz` on the setpoints: 20 ± 1 Hz (course guideline). (2) Load the CPU (`stress-ng --cpu 0 --timeout 60s` or real inference at full resolution) and watch `ros2 topic hz` and `tegrastats`/`htop`: the setpoint rate must not drop below 18 Hz (course guideline: 10 % below nominal). If it drops, the heavy callback has not been moved into its own group or its own process. (3) `kill -9` the perception node: DEGRADED within the `max_age` of the targets input, OK `recover_s` after the restart. (4) Disconnect the bridge cable (UART/Ethernet): FAILSAFE on the companion computer, and in the autopilot log its own timeout: PX4 leaves Offboard after `COM_OF_LOSS_T` (1.0 s), ArduPilot stops after `GUID_TIMEOUT` (3 s) while staying in GUIDED. Stop and investigate if you see any of these: setpoints still going out after FAILSAFE, the autopilot not noticing the loss of the stream, not all four nodes coming up after a reboot. Only after all four checks pass: a tethered or low flight in Offboard/GUIDED with the mode switch on the transmitter ready.

Self-check: the lab is done when the watchdog tests pass and your explanation of `test_hysteresis_on_flapping_input` matches the reference below, the four-node skeleton handles both failures in SITL (logs saved): after `kill -9` of perception the level is DEGRADED, the vehicle holds position, and after the node returns the level is OK again after `recover_s`; after the bridge is stopped it is FAILSAFE, decision stops the setpoints and the autopilot log shows its own timeout; after a reboot the system comes up without manual commands; the step 2 script gives no NO lines on your own graph, and on the example it gives exactly four NO lines with the reasons reliability, reliability, durability, deadline; the step 3 model gives 402 / 402 / 50 ms maximum gap, 115 / 115 / 0 skipped ticks and 45 lost frames, and with `threads=1` and different groups, 402 ms again; on hardware the setpoint rate under CPU load is no lower than 18 Hz.

**Reference for the self-check.** After 0.5 s of recovery the level is still DEGRADED, because an input counts as recovered only if it has been fresh continuously for `recover_s` (for example, 1 s), and 0.5 s is less. Typical wrong results: (1) tracking switches on and off several times a second: there is no hysteresis, or `recover_s` is too small; (2) after a reboot the application does not start: the service starts before the network or the serial port appears (`After=`, `BindsTo=`); (3) when perception crashed, the mission aborted in an emergency: a non-critical node ended up on the "autopilot status → setpoints" path. (4) A MultiThreadedExecutor is in place, but the setpoints still break for the duration of the inference: the callbacks stayed in the node's default group (MutuallyExclusive). (5) After a restart the decision node "does not see" FAILSAFE until the level changes: the level publisher is VOLATILE; you need TRANSIENT_LOCAL on both sides.

## diagnostics
- **Symptom:** when the neural network hangs, the vehicle "hangs" with its setpoints
  - Possible cause: the inference and the setpoint timer share one executor thread.
  - What to do: separate callback groups, a MultiThreadedExecutor, or perception in a separate process.
- **Symptom:** tracking switches on and off several times a second
  - Possible cause: no recovery hysteresis on the input.
  - What to do: recover_s ≥ 0.5–1 s.
- **Symptom:** after the companion computer reboots, the application does not start
  - Possible cause: the service starts before the serial port/network appears.
  - What to do: systemd dependencies (After/BindsTo), connection retries in the bridge.
- **Symptom:** the bag and the autopilot log do not line up in time
  - Possible cause: the companion computer's clock is not synchronized.
  - What to do: chrony; use the autopilot's timestamps in the messages.
- **Symptom:** you installed a `MultiThreadedExecutor`, but the setpoints still break for the duration of the inference
  - Possible cause: all callbacks are in the node's default group, and it is MutuallyExclusive.
  - What to do: put the inference in its own `MutuallyExclusiveCallbackGroup` (the `callback_group=` argument of the subscription/timer) and check with the step 3 model; for pure Python, use a separate process (GIL).
- **Symptom:** a restarted decision node does not know the current level until it changes
  - Possible cause: the level is published VOLATILE; or TRANSIENT_LOCAL is set on one side only (on the subscriber only means no connection at all).
  - What to do: RELIABLE + TRANSIENT_LOCAL, depth 1 on both the publisher and the subscriber; check with `ros2 topic info -v`.
- **Symptom:** perception is in the Inactive state, but the CPU is still loaded
  - Possible cause: the timer or subscription was created in the constructor/`on_configure`, and in Inactive only lifecycle publishers go silent.
  - What to do: create the timer in `on_activate` and destroy it in `on_deactivate`.
- **Symptom:** the node does not go to Active, and `ros2 lifecycle get` shows unconfigured
  - Possible cause: `on_configure` returned FAILURE (no model file, the camera did not open), which is by design.
  - What to do: read the node log before takeoff; a manager with `autostart` must stop bringing the system up, not take off without perception.
- **Symptom:** a subscription with a deadline is silent, and the log says "incompatible QoS ... DEADLINE"
  - Possible cause: the subscriber requested a deadline shorter than the publisher offers.
  - What to do: subscriber deadline ≥ publisher deadline; check the pair with the step 2 script.

## references
- ROS 2 — Managed nodes (lifecycle) design | https://design.ros2.org/articles/node_lifecycle.html | primary | A
- ROS 2 Jazzy — Executors and callback groups | https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Executors.html | primary | A
- ROS 2 Jazzy — Quality of Service settings (RxO compatibility, QoS events) | https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Quality-of-Service-Settings.html | primary | A
- ROS 2 — Distributions (release and EOL dates) | https://docs.ros.org/en/rolling/Releases.html | primary | A
- REP 2000 — ROS 2 releases and target platforms | https://github.com/ros-infrastructure/rep/blob/master/rep-2000.rst | primary | A
- rclpy (jazzy) — executors.py, callback_groups.py, node.py, lifecycle/ | https://github.com/ros2/rclpy/tree/jazzy/rclpy/rclpy | primary | A
- rcl_lifecycle — default_state_machine.c (FAILURE/ERROR transitions) | https://github.com/ros2/rcl/blob/jazzy/rcl_lifecycle/src/default_state_machine.c | primary | A
- rmw — qos_profiles.h (sensor_data, default and parameters profiles) | https://github.com/ros2/rmw/blob/jazzy/rmw/include/rmw/qos_profiles.h | primary | A
- rosbag2 — ros2bag record verb (flags -d, -b, --max-bag-files) | https://github.com/ros2/rosbag2/blob/rolling/ros2bag/ros2bag/verb/record.py | primary | A
- PX4 v1.18 — uxrce_dds_client utilities.hpp (writer and reader QoS) | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/modules/uxrce_dds_client/utilities.hpp | primary | A
- ArduPilot 4.7.2 — AP_DDS_Topic_Table.h (QoS of the /ap/* topics) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_DDS/AP_DDS_Topic_Table.h | primary | A
- ros2_tracing | https://github.com/ros2/ros2_tracing | primary | A
- Nav2 — lifecycle manager | https://api.nav2.org/nav2-jazzy/html/md_nav2_lifecycle_manager_README.html | primary | A

## checklist
- I split the application into bridge, perception, decision and safeguards with the right dependencies
- I use lifecycle nodes and understand their states
- I build a freshness watchdog with levels and hysteresis
- I move configuration into parameters with value validation
- I deploy in a container with autostart and circular bag recording
- I debug with bags, profile the nodes and spread heavy callbacks over groups
- I choose QoS by topic class and check the pairs with the RxO rule before running
- I understand what a MultiThreadedExecutor without my own callback groups does and does not give
- I choose a distribution by its support window (Jazzy until 2029, Lyrical until 2031)
