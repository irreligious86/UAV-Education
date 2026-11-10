---
id: ros2-basics
title: "ROS 2 for the aircraft: nodes, topics, QoS, tf2, bag"
level: L3
readingTime: 50 min
firmware: PX4 · ArduPilot
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
source_hash: 17265f1f6d76
---

## summary
ROS 2 isn't a “library for drones”, it's a way to build onboard software out of independent processes that talk over DDS. Its value for UAVs is ready-made nodes (cameras, lidars, SLAM, Nav2), common message types and debugging tools: recording and replaying all traffic, the node graph, visualization. Its price is complexity: QoS, coordinate frames, time. This module gives you exactly the part of ROS 2 without which no offboard node will ever fly: the node graph, topics/services/actions, parameters and launch, QoS and why a subscription to PX4 “with defaults” stays silent, REP-103/105 and `tf2`, simulation time and `ros2 bag`. Lab: a telemetry logger node, recording and replaying a bag, and working through a QoS incompatibility hands-on. The environment is `examples/ros2-docker/`.

## theory
### The graph: nodes, topics, services, actions
- A **node** is a process or part of a process with a name, parameters and interfaces. Design rule: one node — one responsibility (bridge, perception, decision, safeguard).
- A **topic** is a “one-to-many” stream of messages of one type; publishers and subscribers don't know about each other. Telemetry, setpoints, images.
- A **service** is request-response (`ArmMotors`, `ModeSwitch`). The semantics are synchronous, but inside a node you must call it asynchronously (`call_async`), otherwise you can block your own executor.
- An **action** is a long-running goal with feedback and cancellation (`NavigateToPose` in Nav2). It's topics + services assembled into a protocol.
- **Parameters** are typed node settings (`ros2 param set /node alt 7.0`), with a validation callback on change.

DDS finds participants on the network by itself (discovery) within a single `ROS_DOMAIN_ID`. On an aircraft with a companion and a laptop on the same Wi-Fi network, this means: without separate domains or filters, the laptop will “see” the vehicle's topics and be able to publish to them. For field flights — a separate domain, or better, `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` (Jazzy; in Humble — `ROS_LOCALHOST_ONLY=1`) on board and a bridge to the outside only for the topics you need.

{{diagram:ros2-graph|The training system as a graph: the bridge to the autopilot, the logger, the state machine, perception and the watchdog are separate nodes.}}

### QoS: why the subscription is silent
Every publisher and subscriber has a QoS profile: **reliability** (RELIABLE/BEST_EFFORT), **durability** (VOLATILE/TRANSIENT_LOCAL — whether a late subscriber gets the last message), **history/depth** (how much to keep), deadline, lifespan, liveliness. A connection is established only with **compatible** profiles, and an incompatibility doesn't raise an error — the subscriber simply receives nothing (an “incompatible QoS” warning may show up in the log).

The main rule: BEST_EFFORT publisher + RELIABLE subscriber = no connection. PX4 publishes `/fmu/out/*` as BEST_EFFORT (and TRANSIENT_LOCAL), while a ROS 2 subscriber is RELIABLE by default. That's why you subscribe to PX4 with the `qos_profile_sensor_data` profile (BEST_EFFORT) or an explicit `QoSProfile`. Why BEST_EFFORT for telemetry: when a packet is lost over Wi-Fi, resending an old position is useless, you need the next one — the same logic as UDP versus TCP in the mav-routing module.

Check: `ros2 topic info -v /fmu/out/vehicle_status_v1` shows the profiles of both sides.

{{diagram:ros2-qos|Reliability compatibility: a BEST_EFFORT publisher doesn't connect to a RELIABLE subscriber — silently.}}

### Coordinate frames: REP-103 and REP-105
ROS lives in **ENU** (world) and **FLU** (body) — REP-103; autopilots live in NED/FRD. This is the main source of integration bugs (module math-linalg-rot): x/y swap places, z changes sign, yaw ψ_enu = 90° − ψ_ned, quaternions in ROS are stored as (x, y, z, w). REP-105 defines the standard frames: `map` (global, drift-free, can jump), `odom` (continuous, drifts), `base_link` (body). The bridges handle this differently: AP_DDS publishes directly in ENU/`map`/`base_link`, PX4 uXRCE-DDS publishes in NED/FRD, as inside PX4, and the conversion is on your side.

`tf2` is a tree of transforms between frames over time: “where was the camera relative to `map` at the moment of the frame”. A node publishes `TransformStamped` to `/tf` (dynamic) and `/tf_static` (sensor mounts), and a consumer asks `lookup_transform(target, source, time)`. A camera on a bracket is the static transform `base_link → camera_link`; you set it once in the launch file.

### Time
Every message with a header has a `header.stamp`. In simulation, time runs from `/clock` (the parameter `use_sim_time:=true`), otherwise the nodes and the bag live in different times, and `tf2` refuses to give transforms “from the future”. PX4 uses its own timestamps in microseconds (`timestamp`) and synchronizes them with the agent; ArduPilot publishes `/ap/time` and `/ap/clock`.

### Launch and parameters
A launch file (Python) starts a set of nodes with parameters, namespaces and topic remapping (`remappings`). This is what runs on board at startup: systemd service → `ros2 launch`. Parameters go in a YAML file, not in the code — so that the same package works on two different vehicles.

### ros2 bag
`ros2 bag record -o run1 /topic1 /topic2` writes the traffic to a file (in Jazzy the default is MCAP, in Humble — SQLite3; the format is set with the `-s` flag); `ros2 bag play run1` replays it, and your nodes can't tell the replay from a flight. This is the main debugging tool: you recorded a flight with a bug — replay it and fix the node on the bench as many times as you like. Recording all topics with cameras on board quickly eats disk and CPU: record compressed images or at a reduced rate.

## practice
### Step 1. Environment
```bash
cd examples/ros2-docker
docker compose build ros
docker compose run --rm ros bash
ros2 doctor --report | head -20
```
The image is built and tested in CI on ROS 2 Jazzy (Ubuntu 24.04 inside the container, so the host can be on 22.04 as well). A build with `ROS_DISTRO=humble` currently fails: the humble branch of micro-ROS-Agent doesn't compile with Fast-CDR 2.x. If Docker isn't available — install ROS 2 Jazzy on Ubuntu 24.04 (or Humble on 22.04) following the official instructions and build `ws/` with `colcon build`.

### Step 2. The graph by hand
In two terminals, `ros2 run demo_nodes_py talker` and `listener`; look at `ros2 node list`, `ros2 topic info -v /chatter`, `ros2 topic hz`. Then publish to a topic with BEST_EFFORT (`ros2 topic pub --qos-reliability best_effort ...`) and subscribe with RELIABLE (`ros2 topic echo --qos-reliability reliable ...`) — no connection. Change the subscriber to best_effort — it appears. Record the output of `topic info -v` in both cases.

### Step 3. Telemetry logger
Start PX4 SITL (`docker compose --profile px4 up`) or ArduPilot SITL with DDS. Run `ros2 run uav_ros2_labs telemetry_logger --ros-args -p source:=px4`. Read the code: the subscription QoS, the write timer independent of the message rate, the NED→ENU conversion for PX4 (and its absence for AP_DDS — it's already in ENU). Change the subscription QoS to RELIABLE and confirm that the CSV stops growing.

### Step 4. Bag: record and replay
Record 60 s of flight into a bag, stop SITL, replay the bag and run the logger again — the CSV should come out the same (up to the start moment). That's “debugging without the vehicle”.

### Step 5. tf2
Publish the camera's static transform (`ros2 run tf2_ros static_transform_publisher --x 0.1 --z -0.05 --pitch 0.5 --frame-id base_link --child-frame-id camera_link`) and query `ros2 run tf2_ros tf2_echo base_link camera_link`. Explain why a positive pitch means “the camera looks down” in FLU.

The lab counts as done when you have shown the QoS effect (topic info output), obtained the logger CSV in SITL and from the bag, and explained the camera transform.

## diagnostics
- **Symptom:** `ros2 topic echo /fmu/out/...` is silent, even though `topic list` shows it
  - Possible cause: QoS — a RELIABLE subscription to a BEST_EFFORT publisher; or the `_v1` version suffix is missing.
  - What to do: `--qos-reliability best_effort`; check the exact topic name.
- **Symptom:** a laptop on the same network “interferes” with the vehicle's topics
  - Possible cause: a shared ROS_DOMAIN_ID and open discovery.
  - What to do: your own domain, localhost-only on board, an explicit bridge to the outside.
- **Symptom:** tf2 “extrapolation into the future” when replaying a bag
  - Possible cause: the nodes run on system time, the bag on recording time.
  - What to do: `ros2 bag play --clock` and `use_sim_time:=true` on all nodes.
- **Symptom:** the vehicle flies “sideways” after the coordinate conversion
  - Possible cause: ENU/NED or FLU/FRD mixed up, or the quaternion component order.
  - What to do: conversion tests (`frames.py`), a check on a stationary vehicle with a known heading.

## references
- ROS 2 Jazzy — Concepts (nodes, topics, services, actions) | https://docs.ros.org/en/jazzy/Concepts.html | primary | A
- ROS 2 — About Quality of Service settings (compatibility table) | https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Quality-of-Service-Settings.html | primary | A
- REP-103 — Standard units and coordinate conventions | https://www.ros.org/reps/rep-0103.html | primary | A
- REP-105 — Coordinate frames for mobile platforms | https://www.ros.org/reps/rep-0105.html | primary | A
- PX4 — ROS 2 user guide (QoS for /fmu/out topics) | https://docs.px4.io/main/en/ros2/user_guide.html | primary | A

## checklist
- I can tell a topic, a service, an action and a parameter apart and pick the right one
- I can explain QoS compatibility and why a subscription to PX4 requires BEST_EFFORT
- I know REP-103/105 and where the bridge converts frames and where it doesn't
- I use tf2 for sensor mounts
- I manage time (sim time) and record/replay bags
- I isolate the vehicle's ROS 2 from outside participants on the network
