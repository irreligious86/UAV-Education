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

{{diagram:ros2-distro-timeline|Support windows by year: in November 2026 Humble (until May 2027), Jazzy, Lyrical and the outgoing Kilted are alive; Noetic and the bridge to it are already past the line.}}

{{diagram:ros2-sync-call-deadlock|A synchronous cli.call() in a callback takes the executor's only thread: there is no one to deliver the reply, and timer ticks are lost; call_async() returns at once, and setpoints go out every 50 ms.}}

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

### Step 5. A worked port on a synthetic flight (done, without ROS)

Steps 1–4 need a real project and ROS; this step runs on any machine with Python 3 and shows the whole cycle on a small node. The “descent guard” node subscribes to the MAVROS pose and publishes a vertical speed 20 times per second: no faster than 1.5 m/s, below 2 m no faster than 0.3 m/s, on the ground 0. The old rospy node (for reading, not run):

```python
# ROS 1 (rospy) — the node being ported; shown for reading, not run (no ROS 1 here)
import rospy
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Float32
from descent_guard import descent_cmd

z = None
def on_pose(msg):
    global z
    z = msg.pose.position.z

rospy.init_node("descent_guard")
rospy.Subscriber("/mavros/local_position/pose", PoseStamped, on_pose)
pub = rospy.Publisher("/descent_guard/vz", Float32, queue_size=10)
rate = rospy.Rate(20)
while not rospy.is_shutdown():
    if z is not None:
        pub.publish(Float32(descent_cmd(z)))
    rate.sleep()
```

The logic without ROS is moved into a module and covered by tests — it carries over without a single change:

```python
"""ROS-free logic of the ported node: vertical speed command for a guarded descent (ENU, up positive)."""
def descent_cmd(z, z_land=0.0, k=0.5, v_max=1.5, slow_alt=2.0, v_slow=0.3):
    """z — altitude above the landing point, m. Returns vz, m/s (negative = down)."""
    err = z - z_land
    if err <= 0.05:
        return 0.0
    limit = v_slow if err < slow_alt else v_max
    return -min(k * err, limit)
```

```python
from descent_guard import descent_cmd
def test_high_altitude_is_limited():   assert descent_cmd(10.0) == -1.5
def test_proportional_zone():           assert descent_cmd(2.4) == -1.2
def test_slow_zone_below_2m():          assert descent_cmd(1.0) == -0.3
def test_stop_on_ground():              assert descent_cmd(0.03) == 0.0
```

The rclpy wrapper (syntax checked with `py_compile`; the author's environment has no ROS 2, so it was not run). Note the subscription QoS and the timer instead of a loop:

```python
# ROS 2 (rclpy) — thin wrapper around the same logic; syntax checked, not run (no ROS 2 here)
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Float32
from descent_guard import descent_cmd


class Guard(Node):
    def __init__(self):
        super().__init__("descent_guard")
        self.z = None
        # MAVROS 2 publishes pose with SensorDataQoS (best effort): a default (reliable) subscription gets nothing
        self.create_subscription(PoseStamped, "/mavros/local_position/pose", self.on_pose, qos_profile_sensor_data)
        self.pub = self.create_publisher(Float32, "/descent_guard/vz", 10)
        self.create_timer(0.05, self.tick)          # replaces rospy.Rate(20) + while loop

    def on_pose(self, msg):
        self.z = msg.pose.position.z

    def tick(self):
        if self.z is not None:
            self.pub.publish(Float32(data=descent_cmd(self.z)))


def main():
    rclpy.init()
    rclpy.spin(Guard())


if __name__ == "__main__":
    main()
```

Checking the behavior without ROS: the script writes a ROS 1 bag (pose at 30 Hz, a 10 s descent from 8 m at 1 m/s, plus the old node's reference output on a 20 Hz grid), converts it with `rosbags-convert` into a ROS 2 bag in MCAP with Jazzy types, reads it back and runs the logic two ways: as a timer on the same grid and “naively”, publishing right in the pose callback. All you need is `pip install rosbags pytest`.

```python
"""ros2-from-ros1 lab without ROS: ROS 1 bag (reference) -> rosbags-convert -> ROS 2 bag -> ported logic -> compare."""
import subprocess, sys, shutil
from pathlib import Path
from rosbags.rosbag1 import Writer as W1
from rosbags.highlevel import AnyReader
from rosbags.typesys import Stores, get_typestore
from descent_guard import descent_cmd
work = Path(sys.argv[1]); shutil.rmtree(work, ignore_errors=True); work.mkdir()
ts1 = get_typestore(Stores.ROS1_NOETIC)
Pose, Stamped, Hdr, Time = (ts1.types[n] for n in ("geometry_msgs/msg/Pose", "geometry_msgs/msg/PoseStamped",
                                                    "std_msgs/msg/Header", "builtin_interfaces/msg/Time"))
P, Q, F32 = ts1.types["geometry_msgs/msg/Point"], ts1.types["geometry_msgs/msg/Quaternion"], ts1.types["std_msgs/msg/Float32"]
NS = 1_000_000_000; T0 = 100 * NS
def alt(t): return max(0.0, 8.0 - 1.0 * t)          # descent from 8 m at 1 m/s (synthetic flight)
# 1) ROS 1 bag: pose at 30 Hz + output of the OLD node (rospy.Rate(20) loop, latest pose) as the reference
bag1 = work / "flight_ros1.bag"
with W1(bag1) as w:
    cp = w.add_connection("/mavros/local_position/pose", Stamped.__msgtype__, typestore=ts1)
    cc = w.add_connection("/descent_guard/vz", F32.__msgtype__, typestore=ts1)
    poses = [(T0 + i * NS // 30, alt(i / 30)) for i in range(300)]          # 10 s
    for t, z in poses:
        m = Stamped(Hdr(seq=0, stamp=Time(sec=t // NS, nanosec=t % NS), frame_id="map"),
                    Pose(P(x=0.0, y=0.0, z=z), Q(x=0.0, y=0.0, z=0.0, w=1.0)))
        w.write(cp, t, ts1.serialize_ros1(m, Stamped.__msgtype__))
    latest = None; j = 0
    for n in range(200):                                                     # while not shutdown: ... rate.sleep()
        tick = T0 + n * NS // 20
        while j < len(poses) and poses[j][0] <= tick: latest = poses[j][1]; j += 1
        if latest is not None:
            w.write(cc, tick, ts1.serialize_ros1(F32(data=descent_cmd(latest)), F32.__msgtype__))
# 2) convert to ROS 2 (MCAP, Jazzy message definitions)
bag2 = work / "flight_ros2"
r = subprocess.run(["rosbags-convert", "--src", str(bag1), "--dst", str(bag2), "--dst-storage", "mcap",
                    "--dst-typestore", "ros2_jazzy"], capture_output=True, text=True)
print("rosbags-convert exit", r.returncode, "->", sorted(p.name for p in bag2.iterdir()))
# 3) read the ROS 2 bag, run the ported node two ways
ts2 = get_typestore(Stores.ROS2_JAZZY)
pose_in, ref = [], []
with AnyReader([bag2], default_typestore=ts2) as rd:
    for c in rd.connections: print(f"  {c.topic:30s} {c.msgtype:28s} {c.msgcount} msgs")
    for c, t, raw in rd.messages():
        msg = rd.deserialize(raw, c.msgtype)
        (pose_in if c.topic.endswith("pose") else ref).append((t, msg.pose.position.z if c.topic.endswith("pose") else msg.data))
def timer_port():                      # node.create_timer(0.05, tick): latest pose, same 20 Hz grid
    out, latest, j = [], None, 0
    for n in range(200):
        tick = T0 + n * NS // 20
        while j < len(pose_in) and pose_in[j][0] <= tick: latest = pose_in[j][1]; j += 1
        if latest is not None: out.append((tick, descent_cmd(latest)))
    return out
def callback_port():                   # naive port: publish inside the pose callback (30 Hz)
    return [(t, descent_cmd(z)) for t, z in pose_in]
import struct
f32 = lambda v: struct.unpack("f", struct.pack("f", v))[0]     # Float32 on the wire
for name, out in (("timer port", timer_port()), ("callback port", callback_port())):
    same = len(out) == len(ref) and all(abs(f32(a[1]) - b[1]) < 1e-6 and a[0] == b[0] for a, b in zip(out, ref))
    print(f"{name:13s}: {len(out)} outputs vs {len(ref)} reference -> {'MATCH' if same else 'DIFFERENT'}")
```

The last script checks the ROS 2 documentation's QoS compatibility rules on typical porting cases:

```python
"""Request-vs-offered QoS rules from the ROS 2 docs (reliability, durability) applied to typical migration cases."""
RANK_REL = {"best_effort": 0, "reliable": 1}
RANK_DUR = {"volatile": 0, "transient_local": 1}
def compatible(pub, sub):
    """pub/sub: (reliability, durability). A subscription may request no more than the publisher offers."""
    return RANK_REL[pub[0]] >= RANK_REL[sub[0]] and RANK_DUR[pub[1]] >= RANK_DUR[sub[1]]
DEFAULT, SENSOR = ("reliable", "volatile"), ("best_effort", "volatile")
LATCHED = ("reliable", "transient_local")
cases = [
    ("MAVROS 2 telemetry (sensor data) -> port with default QoS", SENSOR, DEFAULT),
    ("MAVROS 2 telemetry (sensor data) -> port with sensor data", SENSOR, SENSOR),
    ("default publisher -> sensor-data subscriber", DEFAULT, SENSOR),
    ("ROS 1 latched map, ported as default -> late subscriber wants transient_local", DEFAULT, LATCHED),
    ("transient_local publisher -> default subscriber (no old samples)", LATCHED, DEFAULT),
]
for name, pub, sub in cases:
    print(f"{'OK ' if compatible(pub, sub) else 'NO '} {name}")
```

Output in the author's environment (Python 3.13, rosbags 0.11.10, pytest 9.2.0):

```text
$ python -m pytest -q test_descent_guard.py
4 passed in 0.01s
$ python migrate_lab.py ./work
rosbags-convert exit 0 -> ['flight_ros2.mcap', 'metadata.yaml']
  /mavros/local_position/pose    geometry_msgs/msg/PoseStamped 300 msgs
  /descent_guard/vz              std_msgs/msg/Float32         200 msgs
timer port   : 200 outputs vs 200 reference -> MATCH
callback port: 300 outputs vs 200 reference -> DIFFERENT
$ python qos_check.py
NO  MAVROS 2 telemetry (sensor data) -> port with default QoS
OK  MAVROS 2 telemetry (sensor data) -> port with sensor data
OK  default publisher -> sensor-data subscriber
NO  ROS 1 latched map, ported as default -> late subscriber wants transient_local
OK  transient_local publisher -> default subscriber (no old samples)
```

What this shows. The logic passed the tests and, on the converted bag, gave the same 200 values at the same moments as the reference — when the timer ticks on the grid of the old `rospy.Rate(20)`. The “naive” port into the callback gave 300 outputs: the output rate became the input rate (30 Hz), and the comparison with the reference fails — an example of a “timing difference” without a single error in the logic. A subscription with the default profile to MAVROS 2 telemetry (best effort) is incompatible; a transient local subscriber to a late “latched” topic gets anything only if the publisher is transient local too.

Self-check: the lab is done when **(step 5, without ROS)** the 4 tests pass, `rosbags-convert` exits with code 0 and creates `flight_ros2.mcap`, the ROS 2 bag has 300 pose messages and 200 reference ones, “timer port” gives 200 outputs and MATCH, “callback port” 300 and DIFFERENT, and `qos_check.py` prints NO for exactly two cases: sensor data → default and default → transient local; **(your own project, steps 1–4)** the graph of the original project is drawn (nodes, topics, dependencies and the place where the project controls the aircraft), the ported node is a thin `rclpy` wrapper around a ROS-free logic module, the logic tests pass under pytest, the ported node's outputs on the converted bag match the reference outputs from step 2, and in the step 4 table every behavior difference found is traced to its cause.

**Reference for the self-check.** The correct result: on the same inputs the old and the new node give the same outputs, and the differences are explained by QoS and timing. Typical wrong ones: (1) the ported node “hangs” on a service call — a synchronous call inside a callback, you need `call_async`; (2) the node gets no telemetry or parameters “are not applied” — the subscription is incompatible with the publisher's QoS or the parameter was not declared with `declare_parameter`; (3) a `while` loop with `rate.sleep()` is left in the node — in ROS 2 a timer and callbacks replace it; (4) in step 5 your “timer port” gave 199 or 201 outputs — the timer grid is shifted relative to the reference (it does not start at T0 or the step is not 50 ms); (5) `rosbags-convert` fails on your own type — the type is not registered in the typestore.

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
