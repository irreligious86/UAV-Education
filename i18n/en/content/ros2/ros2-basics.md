---
id: ros2-basics
title: "ROS 2 on board: nodes, topics, QoS, tf2, bag"
level: L3
readingTime: 50 min
firmware: ROS 2 Jazzy (Humble differences noted) · PX4 1.18 (checked against v1.18.0) · ArduPilot 4.7 (checked against 4.7.3)
status: published
added: 2026-11-08
tags:
  - ROS 2
  - QoS
  - tf2
  - rosbag
  - launch
related:
  - math-linalg-rot
  - px4-ros2
  - mav-sdk
next:
  - ros2-px4
source: content/ros2/ros2-basics.md
source_hash: 1907bb80bd97
---

## summary
ROS 2 is not a "drone library". It is a way to build onboard software out of independent processes that talk over DDS. What it gives a UAV is ready-made nodes (cameras, lidars, SLAM, Nav2), shared message types and debugging tools: recording and replaying all traffic, the node graph, visualization. What it costs is complexity: QoS, coordinate frames, time. This module covers exactly the part of ROS 2 that every offboard node needs before it can fly: the node graph, topics/services/actions, parameters and launch, QoS and why a subscription to PX4 with the default profile stays silent, REP-103/105 and `tf2`, simulation time and `ros2 bag`. Lab: a telemetry logger node, recording and replaying a bag, and reproducing a QoS incompatibility yourself. The environment is `examples/ros2-docker/`.

## theory
### The graph: nodes, topics, services, actions
- A **node** is a process, or part of one, with a name, parameters and interfaces. Design rule: one node, one responsibility (bridge, perception, decision, safety).
- A **topic** is a one-to-many stream of messages of one type; publishers and subscribers do not know about each other. Telemetry, setpoints, images.
- A **service** is request/response (`ArmMotors`, `ModeSwitch`). The semantics are synchronous, but inside a node you call it asynchronously (`call_async`), or you can deadlock your own executor.
- An **action** is a long-running goal with feedback and cancellation (`NavigateToPose` in Nav2). It is topics and services assembled into a protocol.
- **Parameters** are typed node settings (`ros2 param set /node alt 7.0`) with a callback that validates changes.

DDS finds the participants on the network by itself (discovery) within one `ROS_DOMAIN_ID`. With a companion computer and a laptop on the same Wi-Fi, this means that unless you use different domains or filters, the laptop will "see" the vehicle's topics and can publish to them. For field flights use a separate domain, or better, `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` (Jazzy; in Humble, `ROS_LOCALHOST_ONLY=1`) on board plus a bridge to the outside for only the topics you need.

{{diagram:ros2-graph|The course system as a graph: the autopilot bridge, logger, state machine, perception and watchdog are separate nodes.}}

### QoS: why the subscription is silent
Every publisher and subscription has a QoS profile: **reliability** (RELIABLE/BEST_EFFORT), **durability** (VOLATILE/TRANSIENT_LOCAL: whether a late-joining subscription gets the last message), **history/depth** (how many samples to keep), deadline, lifespan, liveliness. A connection is made only when the profiles are **compatible**, and an incompatibility does not raise an error: the subscription simply receives nothing (an "incompatible QoS" warning may show up in the log).

The main rule: a BEST_EFFORT publisher + a RELIABLE subscription = no connection. PX4 publishes `/fmu/out/*` as BEST_EFFORT (and TRANSIENT_LOCAL), while a ROS 2 subscription is RELIABLE by default. That is why you subscribe to PX4 with `qos_profile_sensor_data` (BEST_EFFORT) or an explicit `QoSProfile`. Why BEST_EFFORT for telemetry: when a packet is lost over Wi-Fi, retransmitting a stale position is useless; you need the next one. It is the same logic as UDP versus TCP in the mav-routing module.

To check: `ros2 topic info -v /fmu/out/vehicle_status_v4` (PX4 1.18; `_v1` in 1.16–1.17) shows the profiles of both sides.

{{diagram:ros2-qos|Reliability compatibility: a BEST_EFFORT publisher does not connect to a RELIABLE subscription, silently.}}

### Coordinate frames: REP-103 and REP-105
ROS lives in **ENU** (world) and **FLU** (body), per REP-103; autopilots live in NED/FRD. This is the main source of integration bugs (module math-linalg-rot): x and y swap, z changes sign, yaw is ψ_enu = 90° − ψ_ned, and ROS stores quaternions as (x, y, z, w). REP-105 defines the standard frames: `map` (global, no drift, may jump), `odom` (continuous, drifts), `base_link` (the body). The bridges handle this differently: AP_DDS publishes directly in ENU/FLU (poses with `frame_id = base_link`, and it accepts `cmd_vel` setpoints in `map` or `base_link`), while PX4 uXRCE-DDS publishes in NED/FRD, as PX4 uses internally, and the conversion is on your side.

`tf2` is a tree of transforms between frames over time: "where was the camera relative to `map` at the moment of the frame". A node publishes `TransformStamped` to `/tf` (dynamic) and `/tf_static` (sensor mounts), and a consumer asks `lookup_transform(target, source, time)`. A camera on a bracket is a static transform `base_link → camera_link`, set once in the launch file.

### Time
Every message with a header has `header.stamp`. In simulation time comes from `/clock` (the parameter `use_sim_time:=true`); otherwise the nodes and the bag live in different times, and `tf2` refuses to give transforms "from the future". PX4 uses its own timestamps in microseconds (`timestamp`) and synchronizes them with the agent; ArduPilot publishes `/ap/time` and `/ap/clock`.

### Launch and parameters
A launch file (Python) starts a set of nodes with parameters, namespaces and topic remapping (`remappings`). This is what runs on board at startup: systemd service → `ros2 launch`. Parameters live in a YAML file, not in the code, so the same package works on two different vehicles.

### ros2 bag
`ros2 bag record -o run1 /topic1 /topic2` writes traffic to a file (the default storage is MCAP in Jazzy and SQLite3 in Humble; the `-s` option selects the format); `ros2 bag play run1` replays it, and your nodes cannot tell the replay from a flight. This is the main debugging tool: record a flight with a bug, then replay it and fix the node on the bench as many times as you like. Recording every topic including cameras on board quickly eats disk and CPU: record compressed images or at a reduced rate.

### Place in the system

- **Receives:** topics from the autopilot bridge: `/fmu/out/*` in NED with BEST_EFFORT (`ros2-px4`) or `/ap/*` in ENU (`ros2-ardupilot`); `/clock` time in simulation (`tools-gazebo`); axis conventions (`math-linalg-rot`).
- **Provides:** the node graph, QoS, `tf2` and bags to the application architecture (`ros2-app-arch`) and navigation (`ros2-nav`); the static transform `base_link → camera_link` to camera geometry (`per-geometry`).
- **If you get it wrong here:** a RELIABLE subscription to `/fmu/out/*` → no connection and no error → the node never gets the status, and the state machine does not start (`ros2-px4`). `use_sim_time` not set → `tf2` refuses transforms → the planner has no pose (`ros2-nav`).

## practice
### Step 1. Environment
```bash
cd examples/ros2-docker
docker compose build ros
docker compose run --rm ros bash
ros2 doctor --report | head -20
```
The image is built and checked in CI on ROS 2 Jazzy (Ubuntu 24.04 inside the container, so the host can also be on 22.04). The build with `ROS_DISTRO=humble` currently fails: the humble branch of micro-ROS-Agent does not compile against Fast-CDR 2.x. If Docker is not available, install ROS 2 Jazzy on Ubuntu 24.04 (or Humble on 22.04) following the official instructions and build `ws/` with `colcon build`.

### Step 2. The graph by hand
In two terminals run `ros2 run demo_nodes_py talker` and `listener`; look at `ros2 node list`, `ros2 topic info -v /chatter`, `ros2 topic hz`. Then publish to a topic with BEST_EFFORT (`ros2 topic pub --qos-reliability best_effort ...`) and subscribe with RELIABLE (`ros2 topic echo --qos-reliability reliable ...`): no connection. Switch the subscriber to best_effort and it appears. Save the `topic info -v` output for both cases.

### Step 3. Telemetry logger
Start PX4 SITL (`docker compose --profile px4 up`) or ArduPilot SITL with DDS. Run `ros2 run uav_ros2_labs telemetry_logger --ros-args -p source:=px4`. Read the code: the subscription QoS, the write timer that is independent of the message rate, the NED→ENU conversion for PX4 (and its absence for AP_DDS, which is already in ENU). Change the subscription QoS to RELIABLE and confirm that the CSV stops growing.

### Step 4. Bag: record and replay
Record 60 s of flight into a bag, stop SITL, replay the bag and run the logger again: the CSV should come out the same (up to the start moment). That is "debugging without the vehicle".

### Step 5. tf2
Publish the static camera transform (`ros2 run tf2_ros static_transform_publisher --x 0.1 --z -0.05 --pitch 0.5 --frame-id base_link --child-frame-id camera_link`) and query it with `ros2 run tf2_ros tf2_echo base_link camera_link`. Explain why a positive pitch means "the camera looks down" in FLU.

Self-check: the lab is done when the `topic info -v` output is saved for both cases and shows that the connection is missing exactly with a BEST_EFFORT publisher and a RELIABLE subscriber, the logger CSV is produced in SITL and stops growing with a RELIABLE subscription, the CSV from the bag matches the CSV from SITL up to the start moment, `tf2_echo base_link camera_link` returns the offsets you set (x = 0.1, z = −0.05) and pitch 0.5, and your explanation of the pitch sign matches the reference below.

**Reference for the self-check.** In FLU the x axis points forward, y to the left, z up; a positive rotation about y by the right-hand rule tilts the x axis toward −z, that is, down, so a positive pitch means "the camera looks down". Typical wrong results: (1) `ros2 topic echo` is silent although the topic is in the list: a RELIABLE subscription to a BEST_EFFORT publisher, or the version suffix (`_v1`, `_v4`, …) is missing / wrong; (2) during bag replay tf2 reports "extrapolation into the future": the nodes run on system time; use `ros2 bag play --clock` and `use_sim_time:=true`.

## diagnostics
- **Symptom:** `ros2 topic echo /fmu/out/...` is silent although `topic list` shows the topic
  - Possible cause: QoS, a RELIABLE subscription to a BEST_EFFORT publisher; or the version suffix (`_v1`, `_v4`, …) is missing / wrong.
  - What to do: `--qos-reliability best_effort`; check the exact topic name.
- **Symptom:** a laptop on the same network "interferes" with the vehicle's topics
  - Possible cause: a shared ROS_DOMAIN_ID and open discovery.
  - What to do: your own domain, localhost-only on board, an explicit bridge to the outside.
- **Symptom:** tf2 "extrapolation into the future" during bag replay
  - Possible cause: the nodes run on system time, the bag on recording time.
  - What to do: `ros2 bag play --clock` and `use_sim_time:=true` on every node.
- **Symptom:** the vehicle flies "sideways" after a coordinate conversion
  - Possible cause: ENU/NED or FLU/FRD mixed up, or the quaternion component order.
  - What to do: conversion tests (`frames.py`), a check on a stationary vehicle with a known heading.

## references
- ROS 2 Jazzy — Concepts (nodes, topics, services, actions) | https://docs.ros.org/en/jazzy/Concepts.html | primary | A
- ROS 2 — About Quality of Service settings (compatibility table) | https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Quality-of-Service-Settings.html | primary | A
- REP-103 — Standard units and coordinate conventions | https://www.ros.org/reps/rep-0103.html | primary | A
- REP-105 — Coordinate frames for mobile platforms | https://www.ros.org/reps/rep-0105.html | primary | A
- PX4 — ROS 2 user guide (QoS for /fmu/out topics) | https://docs.px4.io/v1.18/en/ros2/user_guide.html | primary | A

## checklist
- I can tell a topic, a service, an action and a parameter apart and pick the right one
- I can explain QoS compatibility and why a subscription to PX4 needs BEST_EFFORT
- I know REP-103/105 and where the bridge converts frames and where it does not
- I use tf2 for sensor mounts
- I manage time (sim time) and record/replay bags
- I isolate the vehicle's ROS 2 from other participants on the network
