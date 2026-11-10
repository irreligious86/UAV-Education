---
id: ros2-from-ros1
title: "From ROS 1 to ROS 2: reading old projects and porting them"
level: L3
readingTime: 30 min
firmware: PX4 · ArduPilot
status: published
added: 2026-11-08
tags:
  - ROS 1
  - ROS 2
  - migration
  - MAVROS
  - catkin
related:
  - ros2-basics
  - ros2-ardupilot
next:
  - ros2-app-arch
source: content/ros2/ros2-from-ros1.md
source_hash: a1ec2f4af0ee
---

## summary
ROS 1 Noetic reached end of support in May 2025, but half of the open drone projects, papers and tutorials are on ROS 1: MAVROS 1, catkin workspaces, XML launch files, `rospy`. This module teaches you to read such a project quickly (“what matters here and what depends on what”), to know how ROS 1 concepts map to ROS 2, to decide whether to port or run side by side through a bridge, and to port a small package. Lab: porting a ROS 1 node to ROS 2 while preserving its behavior, verified on recorded data.

## theory
### How ROS 2 differs in substance
| ROS 1 | ROS 2 | What it changes |
|---|---|---|
| `roscore` (master) — a central name server | no master, DDS discovery | no single point of failure; you need domains/discovery limits |
| TCPROS/UDPROS | DDS with QoS | you have to think about QoS (module ros2-basics) |
| `rospy`, `roscpp` | `rclpy`, `rclcpp` | a different API, but the same ideas |
| catkin, `catkin_make`/`catkin build` | ament, `colcon build` | a different build, `package.xml` format 3 |
| XML launch (`.launch`) | Python/XML/YAML launch (`.launch.py`) | logic in the launch file |
| parameters in a global server | parameters per node | `rosparam` → `ros2 param` against a specific node |
| `rosbag` (`.bag`) | `ros2 bag` (SQLite3/MCAP) | converters exist (rosbags) |
| `tf` | `tf2` (also existed in ROS 1) | almost unchanged |
| nodelets | components (composable nodes) | several nodes in one process without copying |
| MAVROS 1 | MAVROS 2 (`mavros` in ROS 2) | the same plugins, different service names/QoS |

### How to read a ROS 1 project in 30 minutes
1. **The root**: `package.xml`/`CMakeLists.txt` — dependencies (which sensors, whether it's MAVROS, whether it's OpenCV).
2. **Launch files** (`launch/*.launch`) — what gets started, with which parameters and remaps. This is the “system diagram”.
3. **Nodes** (`scripts/*.py`, `src/*.cpp`): find `init_node`, `Subscriber`, `Publisher`, `Service`, `Timer`/`Rate`. Draw the graph: what it listens to, what it publishes.
4. **Parameters** (`config/*.yaml`, `rospy.get_param`) — what is configurable.
5. **Messages** (`msg/`, `srv/`) — custom types.
6. **MAVROS specifics**: `/mavros/setpoint_*`, `/mavros/set_mode`, `/mavros/cmd/arming` — where the project controls the vehicle and in which coordinate frame.

The result is a node graph (as in ros2-basics) and a list of external dependencies. With it, you can see what the port will cost.

### Port or bridge
- **ros1_bridge** — a bidirectional bridge for topics/services between ROS 1 and ROS 2 with both running. It requires a compatible build (the same message types on both sides), historically Noetic + Foxy/Humble from source. Now that Noetic support has ended, this is a temporary solution.
- **Porting** — the right path for living code. The order: messages → library code without ROS (pull it out!) → nodes → launch → tests on recorded data.
- **Running ROS 1 in a container** — to “see how it used to work” and to record reference data before porting.

### Typical code replacements (Python)
| ROS 1 (rospy) | ROS 2 (rclpy) |
|---|---|
| `rospy.init_node("n")` | `rclpy.init(); node = Node("n")` |
| `rospy.Subscriber("/t", T, cb)` | `node.create_subscription(T, "/t", cb, qos)` |
| `rospy.Publisher("/t", T, queue_size=10)` | `node.create_publisher(T, "/t", 10)` |
| `rospy.Rate(20); while not rospy.is_shutdown(): ... rate.sleep()` | `node.create_timer(0.05, tick); rclpy.spin(node)` |
| `rospy.get_param("~alt", 5.0)` | `node.declare_parameter("alt", 5.0); node.get_parameter("alt").value` |
| `rospy.ServiceProxy("/s", S)(req)` | `cli = node.create_client(S, "/s"); cli.call_async(req)` |
| `rospy.Time.now()` | `node.get_clock().now()` |
| `rospy.loginfo(...)` | `node.get_logger().info(...)` |

The main shift in thinking: **the `while` loop with `rate.sleep()` is replaced by a timer and callbacks**, and a synchronous service call inside a callback by an asynchronous one, otherwise the node will block itself (the same executor services the response).

### MAVROS 1 → MAVROS 2
The topic names are mostly the same (`/mavros/state`, `/mavros/local_position/pose`, `/mavros/setpoint_position/local`), but: telemetry QoS is sensor data; some services and parameters have been renamed; launch is `ros2 launch mavros apm.launch fcu_url:=...` (or `px4.launch`). For PX4 in ROS 2, people usually move from MAVROS to uXRCE-DDS (module ros2-px4); for ArduPilot — to AP_DDS where its features are enough (module ros2-ardupilot).

{{diagram:ros1-migration|What to do with an old ROS 1 project: a temporary bridge, a port, MAVROS 2, or a rewrite based on its ideas.}}

## practice
### Step 1. Reading the project
Take an open ROS 1 drone project (for example, the offboard example from the PX4 documentation for ROS 1 / MAVROS, or any repository with MAVROS 1). In 30 minutes, draw the node graph, the list of dependencies and where the project controls the vehicle.

### Step 2. Reference data
If you can, run the project in a ROS 1 Noetic container with SITL and record a `rosbag` of the node's inputs and outputs. If not, use a bag from open sources or synthetic inputs.

### Step 3. Porting
Port one node (up to ~200 lines): the logic without ROS goes into a separate module with pytest tests (like `offboard_fsm.py`), the node is a thin `rclpy` wrapper. Convert the bag to the ROS 2 format (the `rosbags` package: `rosbags-convert`) and check that the outputs of the ported node match the reference ones.

### Step 4. Report
A table: what was replaced, how many lines of logic became testable without ROS, what behavior differences were found (usually QoS and time).

The lab counts as done when you have the graph of the original project, the ported node with logic tests and a comparison of the outputs on the same data.

## diagnostics
- **Symptom:** the ported node “hangs” on a service call
  - Possible cause: a synchronous call in a callback of a single-threaded executor.
  - What to do: call_async + handling the future, or a separate callback group.
- **Symptom:** the node doesn't receive MAVROS 2 telemetry
  - Possible cause: QoS (sensor data on the publisher) or a different topic name.
  - What to do: `ros2 topic info -v`, the subscription profile.
- **Symptom:** parameters “don't apply”
  - Possible cause: in ROS 2 a parameter must be declared (`declare_parameter`) and passed to a specific node.
  - What to do: declare it in the constructor, YAML with the node name in launch.
- **Symptom:** ros1_bridge doesn't pass your custom message type
  - Possible cause: the bridge was built without this type or the definitions differ.
  - What to do: build the bridge from source with both workspaces; better yet — port.

## references
- ROS 2 — Migration guide from ROS 1 | https://docs.ros.org/en/jazzy/How-To-Guides/Migrating-from-ROS1.html | primary | A
- ros1_bridge | https://github.com/ros2/ros1_bridge | primary | A
- rosbags (bag conversion, pure Python) | https://gitlab.com/ternaris/rosbags | primary | A
- MAVROS (ROS 2 branch) | https://github.com/mavlink/mavros | primary | A

## checklist
- I know how ROS 1 concepts map to ROS 2 and what changes in substance
- I read a ROS 1 project through its launch files and draw the node graph
- I choose between a bridge and a port
- I replace the rate.sleep loop with a timer, synchronous services with asynchronous ones
- I verify the port on reference recorded data
