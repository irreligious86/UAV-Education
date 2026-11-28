---
id: ros2-from-ros1
title: "From ROS 1 to ROS 2: reading old projects and porting them"
level: L3
readingTime: 45 min
firmware: ROS 2 Humble · Jazzy · Lyrical · ROS 1 Noetic (EOL) · PX4 · ArduPilot
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
source_hash: 06593181b99e
---

## summary
ROS 1 Noetic reached end of life on May 31, 2025, yet half of the open drone projects, papers and tutorials are on ROS 1: MAVROS 1, catkin workspaces, XML launch files, `rospy`. This module teaches you to read such a project quickly ("what matters here and what depends on what"), to know how ROS 1 concepts map to ROS 2, to decide whether to port or to run side by side through a bridge, and to port a small package. It gives the status of the distributions as of November 2026 and how to choose a target, what replaced `roscore` (DDS discovery, domains, RMW), which implicit ROS 1 behaviors you now have to set explicitly through QoS, and how the build (catkin → colcon) and launch files carry over. Lab (done without ROS installed): a ROS 1 bag with the reference output of the old node → `rosbags-convert` → a ROS 2 bag in MCAP → the ported logic with pytest and a comparison of the outputs; plus a QoS compatibility check on typical MAVROS 2 cases.

## theory
### What really differs in ROS 2
| ROS 1 | ROS 2 | What it changes |
|---|---|---|
| `roscore` (master), the central name service | no master, DDS discovery | no single point of failure; you need domains/limited discovery |
| TCPROS/UDPROS | DDS with QoS | you have to think about QoS (module ros2-basics) |
| `rospy`, `roscpp` | `rclpy`, `rclcpp` | a different API, but the same ideas |
| catkin, `catkin_make`/`catkin build` | ament, `colcon build` | a different build, `package.xml` format 3 |
| XML launch (`.launch`) | Python/XML/YAML launch (`.launch.py`) | logic in the launch file |
| parameters on a global server | parameters belong to each node | `rosparam` → `ros2 param` against a specific node |
| `rosbag` (`.bag`) | `ros2 bag` (MCAP by default since Iron, SQLite3 as an option) | converters exist (rosbags) |
| `tf` | `tf2` (also existed in ROS 1) | almost unchanged |
| nodelets | components (composable nodes) | several nodes in one process without copying |
| MAVROS 1 | MAVROS 2 (`mavros` in ROS 2) | the same plugins, different service names/QoS |

### Version status as of November 2026 and choosing a target
ROS 1 Noetic reached end of life on May 31, 2025, the same day as the end of standard support for Ubuntu 20.04; the last package sync was on May 29, 2025. After EOL there will be no fixes in the binary packages. In December 2025 Open Robotics announced the decommissioning of the ROS 1 infrastructure: the build.ros.org build farm (which is to redirect to build.ros2.org once it is shut down) and the internal repositories.ros.org; packages already built remain on packages.ros.org. You can read and run an old project in a container on Ubuntu 20.04, but developing it further on ROS 1 means piling up debt.

| Distribution | Release | End of support | Ubuntu (Tier 1) | Status on November 26, 2026 |
|---|---|---|---|---|
| Noetic (ROS 1) | May 2020 | May 31, 2025 | 20.04 | EOL |
| Foxy | June 5, 2020 | June 20, 2023 | 20.04 | EOL |
| Humble (LTS) | May 23, 2022 | May 2027 | 22.04 | supported, six months to EOL |
| Iron | May 23, 2023 | December 4, 2024 | 22.04 | EOL |
| Jazzy (LTS) | May 23, 2024 | May 2029 | 24.04 | supported |
| Kilted | May 23, 2025 | December 2026 (REP 2000 says November 2026) | 24.04 | in its last weeks |
| Lyrical (LTS) | May 22, 2026 | May 2031 | 26.04 (24.04 is Tier 3, source only) | supported, the newest LTS |

How to choose a target for porting a drone project. The target is set not by the newest distribution but by the "narrowest" dependency. AP_DDS in ArduPilot 4.7 officially supports only Humble (`ros2-ardupilot`), the PX4 documentation (main) recommends Jazzy on Ubuntu 24.04, while the release documentation up to and including v1.18 recommends Humble on 22.04 (`ros2-px4`), and MAVROS 2.17.0 is released for Humble, Jazzy, Kilted and Lyrical (rosdistro, November 2026). Hence the course rule: ArduPilot through AP_DDS means Humble, but with a plan to move before May 2027; PX4 or MAVROS means Jazzy; Lyrical is for a new project if every package you need is already released for it (check `distribution.yaml` in rosdistro). Kilted is not a porting target: its support ends in December 2026.

{{diagram:ros2-distro-timeline|Support windows by year: in November 2026 Humble (until May 2027), Jazzy, Lyrical and the outgoing Kilted are alive; Noetic and the bridge to it are already past the line.}}

### What replaced `roscore`: DDS, domains, RMW
In ROS 1 a node first registered with the master (`roscore`), asked it who publishes the topic it needs, and only then opened a direct TCP connection. If the master went down, new nodes could not find each other. ROS 2 has no master: every process is a DDS participant that announces itself over UDP multicast and listens to the announcements of others (discovery). The upside is no single point of failure; the downside is that every node on the network sees everyone, and you have to limit that.

There are three ways to limit it. The **domain** `ROS_DOMAIN_ID`: participants in different domains do not see each other; the safe range is 0–101 (the ROS 2 documentation also lists 215–232 as safe on Linux; the rest overlap with the ephemeral ports). The **discovery range** `ROS_AUTOMATIC_DISCOVERY_RANGE` (introduced in Iron, so it exists in Jazzy and later, but not in Humble; `LOCALHOST` means this machine only, `SUBNET` is the default) replaced the deprecated `ROS_LOCALHOST_ONLY=1` from Humble. The **middleware implementation (RMW)**: the default is `rmw_fastrtps_cpp` (eProsima Fast DDS) in every supported distribution; there are also Cyclone DDS, Connext and, since Kilted, `rmw_zenoh_cpp` at Tier 1. Communication between different DDS implementations (Fast DDS and Cyclone DDS often do connect over the common RTPS protocol) is not guaranteed, and `rmw_zenoh_cpp` does not talk to the DDS RMWs at all, so `RMW_IMPLEMENTATION`, the domain and the distribution must match on board and on the laptop. ROS 1 had none of these settings, so in a ported project you have to set them explicitly in the launch file or in the service environment.

### QoS: what was implicit in ROS 1
ROS 1 almost always transported over TCPROS, which is essentially "reliable", with a `queue_size` queue, and a "latched" (`latch=True`) publisher handed its last message to a late subscriber. In ROS 2 these properties became QoS policies, and they are set separately on the publisher and on the subscriber. A connection is made only if the subscriber requests no more than the publisher offers (the "request vs offered" model).

| Policy | Publisher | Subscriber | Connection |
|---|---|---|---|
| Reliability | best effort | best effort | yes |
| | best effort | reliable | **no** |
| | reliable | best effort / reliable | yes |
| Durability | volatile | transient local | **no** |
| | transient local | volatile | yes, new messages only |
| | transient local | transient local | yes, new messages and the last stored one ("latched") |

The default profile is keep last 10, reliable, volatile; the sensor data profile is keep last 5, best effort, volatile (`rmw/qos_profiles.h`). The ROS 1 counterparts: `queue_size` ≈ depth, TCPROS ≈ reliable, `latch=True` ≈ transient local **on both sides**. The main trap when porting drone nodes: MAVROS 2 publishes telemetry (`~/pose`, velocities) with `SensorDataQoS`, that is best effort, while the ported node subscribes with the default profile (reliable): no connection, no error, no data. MAVROS 2 publishes `/mavros/state` with transient local (the publisher is created in `plugins/sys_status.cpp` with the `StateQoS()` profile from `mavros/qos.hpp`), so a default subscription to it works. To check, run `ros2 topic info -v <topic>`: it shows the profiles of all publishers and subscribers.

{{lesson:ros2-basics|Nodes, topics, QoS and discovery in ROS 2 from scratch: the foundation the port builds on.}}

### Build and launch: catkin → colcon, XML → Python
**Build.** catkin is replaced by ament (the package build system) and colcon (the workspace build tool). A Python package is now an ordinary setuptools package: in `package.xml` (format 3; format 2 is also accepted) `<build_type>ament_python</build_type>`, with the nodes declared as `console_scripts` in `setup.py`; a C++ package is `ament_cmake`. Commands: `colcon build --symlink-install` instead of `catkin_make` (with `--symlink-install`, edits to Python code need no rebuild), `colcon build --packages-select <pkg>` for a single package, `source install/setup.bash` instead of `devel/setup.bash`, `colcon test` and `colcon test-result --verbose` for tests. There is no `devel/` directory any more: only `build/`, `install/`, `log/`.

**Launch.** ROS 2 reads launch files in Python, XML and YAML, but ROS 1 XML is not compatible one to one (the launch file migration guide): the `type` attribute is now `exec`, `ns` is now `namespace`, `required="true"` is now `on_exit="shutdown"`, `$(find pkg)` is now `$(find-pkg-share pkg)`, `<rosparam>` has been replaced with a `from` attribute in `<param>` tags, and there are no global parameters: every parameter belongs to a node. The minimal port is XML with these replacements; you need a Python launch file once logic appears: conditions, loops over vehicles, computed parameters. An example Python launch for the ported node: `Node(package="descent_guard", executable="guard", name="guard", parameters=[{"k": 0.5}], remappings=[("pose", "/mavros/local_position/pose")])` inside `LaunchDescription([...])`.

### How to read a ROS 1 project in 30 minutes
1. **Root**: `package.xml`/`CMakeLists.txt` give the dependencies (which sensors, whether it is MAVROS, whether it is OpenCV).
2. **Launch files** (`launch/*.launch`): what starts, with which parameters and remaps. This is the "system diagram".
3. **Nodes** (`scripts/*.py`, `src/*.cpp`): find `init_node`, `Subscriber`, `Publisher`, `Service`, `Timer`/`Rate`. Draw the graph: what it listens to, what it publishes.
4. **Parameters** (`config/*.yaml`, `rospy.get_param`): what can be configured.
5. **Messages** (`msg/`, `srv/`): custom types.
6. **MAVROS specifics**: `/mavros/setpoint_*`, `/mavros/set_mode`, `/mavros/cmd/arming`: where the project controls the vehicle and in which frame.

The result is a node graph (as in ros2-basics) and a list of external dependencies. With these, you know what the port will cost.

### Port or bridge
- **ros1_bridge** is a bidirectional bridge of topics/services between ROS 1 and ROS 2 while both are running. The bridge is C++ and knows only the types it was built with: it knows the standard interfaces even in a regular source build, but your own types only if it was built against both workspaces. A binary package existed up to and including Foxy/Galactic. As of November 2026 no ROS 2 distribution has a binary `ros1_bridge` package (rosdistro: Humble has a release repository entry without a version; Jazzy, Kilted and Lyrical have no release), and the bridge README says it plainly: Ubuntu 24.04 has no ROS 1, so there is no bridge; full support is Ubuntu 20.04 only (Noetic), and on 22.04 it is a source build without official ROS 1 support. In practice the bridge is a temporary crutch in a 20.04 container, not a way forward.
- **Porting** is the right way for living code. The order: messages → ROS-free library code (extract it!) → nodes → launch → tests on recorded data.
- **Running ROS 1 in a container** is for "seeing how it worked" and for recording reference data before the port.

### Data: bag files and the reference
Bag files recorded in ROS 1 are the main asset of a port: they are how you check that the new node behaves like the old one. The pure Python package `rosbags` (0.11.11, released November 27, 2026; the lab below was captured on 0.11.10, and 0.11.11 gives the same output) reads and writes ROS 1 and ROS 2 bags without ROS installed, and `rosbags-convert --src old.bag --dst new_dir --dst-storage mcap` converts one format to the other. The types themselves change in the conversion: in ROS 2 `std_msgs/Header` has no `seq` field, and time is `builtin_interfaces/Time` with the fields `sec` and `nanosec`, not `rospy.Time` with `secs`/`nsecs`; the converter drops `seq` by itself. Your own message types (`msg/`) must be registered in the `rosbags` typestore, or the converter cannot parse them. Outputs are compared by recording time: a timer in ROS 2 must tick on the same grid as `rospy.Rate` in the old node, or the number of outputs and their times will not match. These are the "timing differences" that the lab shows in numbers.

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

The main change in thinking: **the `while` loop with `rate.sleep()` is replaced by a timer and callbacks**, and a synchronous service call inside a callback by an asynchronous one; otherwise the node deadlocks itself (the same executor has to deliver the response).

{{diagram:ros2-sync-call-deadlock|A synchronous cli.call() in a callback occupies the executor's only thread: nobody can deliver the response and timer ticks are lost; call_async() returns at once, and setpoints go out every 50 ms.}}

### MAVROS 1 → MAVROS 2
The topic names are mostly the same (`/mavros/state`, `/mavros/local_position/pose`, `/mavros/setpoint_position/local`), but: telemetry QoS is sensor data; some services and parameters were renamed; the launch is `ros2 launch mavros apm.launch fcu_url:=...` (or `px4.launch`). For PX4 in ROS 2 people usually move from MAVROS to uXRCE-DDS (module ros2-px4), and for ArduPilot to AP_DDS where its features are enough (module ros2-ardupilot).

{{diagram:ros1-migration|What to do with an old ROS 1 project: a temporary bridge, a port, MAVROS 2, or a rewrite based on its ideas.}}

### Place in the system

- **Receives:** the old project: launch files, nodes, calls to `/mavros/*`; the concepts of QoS, timers and node parameters (`ros2-basics`); reference data recorded before the port.
- **Provides:** the node graph and the list of dependencies to the "bridge or port" decision; the ported node to the application architecture (`ros2-app-arch`); the choice of autopilot bridge: uXRCE-DDS (`ros2-px4`), AP_DDS (`ros2-ardupilot`) or MAVROS 2 (`mav-sdk`).
- **If you get it wrong here:** you left a synchronous service call inside a callback → the node deadlocks itself → setpoints stop going out → the autopilot leaves Offboard or stops on a timeout (`ros2-px4`). You ported MAVROS subscriptions without sensor data QoS → telemetry does not arrive (`ros2-basics`).

## practice
### Step 1. Reading the project
Take an open ROS 1 drone project (for example, the offboard example from the PX4 documentation for ROS 1 / MAVROS, or any repository with MAVROS 1). In 30 minutes, draw the node graph, the list of dependencies, and where the project controls the vehicle.

### Step 2. Reference data
If you can, run the project in a ROS 1 Noetic container with SITL and record a `rosbag` of the node's inputs and outputs. If not, use a bag from open sources or synthetic inputs.

### Step 3. The port
Port one node (up to ~200 lines): the ROS-free logic goes into a separate module with pytest tests (like `offboard_fsm.py` from the `ros2-px4` module), and the node becomes a thin `rclpy` wrapper. Convert the bag to the ROS 2 format (the `rosbags` package: `rosbags-convert`) and check that the outputs of the ported node match the reference.

### Step 4. The write-up
A table: what was replaced, how many lines of logic became testable without ROS, which behavior differences you found (usually QoS and time).

### Step 5. A worked port on a synthetic flight (done, without ROS)
Steps 1–4 need a real project and ROS; this step runs on any machine with Python 3 and shows the whole cycle on a small node. A "descent guard" node subscribes to the MAVROS pose and publishes a vertical speed 20 times a second: no faster than 1.5 m/s, below 2 m no faster than 0.3 m/s, on the ground 0. The old rospy node (for reading, not run):

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

The ROS-free logic is moved into a module and covered by tests; it carries over without a single change:

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

The rclpy wrapper (syntax checked with `py_compile`; the author's environment has no ROS 2, so it was not run). Note the subscription QoS and the timer instead of the loop:

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

Checking the behavior without ROS: the script writes a ROS 1 bag (pose at 30 Hz, a 10 s descent from 8 m at 1 m/s, plus the reference output of the old node on a 20 Hz grid), converts it with `rosbags-convert` into a ROS 2 bag in MCAP with Jazzy types, reads it back and runs the logic two ways: as a timer on the same grid and "naively", publishing directly in the pose callback. All you need is `pip install rosbags pytest`.

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

The last script applies the QoS compatibility rules from the ROS 2 documentation to typical porting cases:

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

What this shows. The logic passed its tests and produced, on the converted bag, the same 200 values at the same times as the reference, when the timer ticks on the grid of the old `rospy.Rate(20)`. The "naive" port into the callback produced 300 outputs: the output rate became the input rate (30 Hz), and the comparison with the reference fails. That is an example of a "timing difference" without a single error in the logic. A default-profile subscription to MAVROS 2 telemetry (best effort) is incompatible; on a late "latched" topic a transient local subscriber gets anything only if the publisher is transient local too.

Self-check: the lab is done when **(step 5, without ROS)** the 4 tests pass, `rosbags-convert` exited with code 0 and created `flight_ros2.mcap`, the ROS 2 bag holds 300 pose messages and 200 reference messages, "timer port" gives 200 outputs and MATCH, "callback port" 300 and DIFFERENT, and `qos_check.py` prints NO for exactly two cases: sensor data → default and default → transient local; **(your own project, steps 1–4)** the graph of the original project is drawn (nodes, topics, dependencies and the place where the project controls the vehicle), the ported node is a thin `rclpy` wrapper around a ROS-free logic module, the logic tests pass under pytest, the outputs of the ported node on the converted bag match the reference outputs from step 2, and in the step 4 table every behavior difference you found is attributed to a cause.

**Reference for the self-check.** The correct result: on the same inputs the old and the new node give the same outputs, and the differences are explained by QoS and time. Typical wrong results: (1) the ported node "hangs" on a service call: a synchronous call inside a callback, you need `call_async`; (2) the node gets no telemetry, or parameters "do not apply": the subscription is incompatible with the publisher's QoS, or the parameter was not declared with `declare_parameter`; (3) a `while` loop with `rate.sleep()` remained in the node: in ROS 2 it is replaced by a timer and callbacks; (4) in step 5 your "timer port" gave 199 or 201 outputs: the timer grid is shifted relative to the reference (it does not start at T0, or the step is not 50 ms); (5) `rosbags-convert` fails on your own type: the type is not registered in the typestore.

## diagnostics
- **Symptom:** the ported node "hangs" on a service call
  - Possible cause: a synchronous call in a callback of a single-threaded executor.
  - What to do: call_async plus handling the future, or a separate callback group.
- **Symptom:** the node gets no MAVROS 2 telemetry
  - Possible cause: QoS (sensor data on the publisher) or a different topic name.
  - What to do: `ros2 topic info -v`, the subscription profile.
- **Symptom:** parameters "do not apply"
  - Possible cause: in ROS 2 a parameter must be declared (`declare_parameter`) and passed to a specific node.
  - What to do: a declaration in the constructor, a YAML file with the node name in the launch file.
- **Symptom:** the nodes on board and on the laptop do not see each other, although the network is up
  - Possible cause: different `ROS_DOMAIN_ID`, `RMW_IMPLEMENTATION` or distribution; `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` on one of the machines; the Wi-Fi access point drops multicast.
  - What to do: `printenv | grep ROS` and `ros2 doctor --report` on both machines; align the domain and the RMW.
- **Symptom:** after converting the bag the comparison with the reference "almost matches": a different number of outputs
  - Possible cause: the ported node publishes in the input callback instead of on a timer with the grid of the old `rospy.Rate`.
  - What to do: a timer with the same period; compare by recording time, as in step 5.
- **Symptom:** `apt` cannot find `ros-<distro>-ros1-bridge`
  - Possible cause: there is no binary package in any supported ROS 2 distribution (rosdistro, November 2026), and Ubuntu 24.04 has no ROS 1.
  - What to do: an Ubuntu 20.04 container with Noetic and a bridge built from source, only as a temporary measure; porting is better.
- **Symptom:** ros1_bridge does not pass your own message type
  - Possible cause: the bridge was built without that type, or the definitions differ.
  - What to do: build the bridge from source against both workspaces; porting is better.

## references
- ROS 2 — Migration guide from ROS 1 | https://docs.ros.org/en/jazzy/How-To-Guides/Migrating-from-ROS1.html | primary | A
- ros1_bridge | https://github.com/ros2/ros1_bridge | primary | A
- rosbags (bag conversion, pure Python) | https://gitlab.com/ternaris/rosbags | primary | A
- MAVROS (ROS 2 branch) | https://github.com/mavlink/mavros | primary | A
- ROS 2 Documentation source — Distributions (release and EOL dates, November 2026) | https://github.com/ros2/ros2_documentation/blob/rolling/source/Releases.rst | primary | A
- REP 2000 — ROS 2 Releases and Target Platforms | https://github.com/ros-infrastructure/rep/blob/master/rep-2000.rst | primary | A
- ROS Noetic End-of-Life: May 31, 2025 — Open Robotics Discourse | https://discourse.openrobotics.org/t/ros-noetic-end-of-life-may-31-2025/43160 | primary | A
- ROS 2 Documentation (Lyrical) — Migrating launch files from ROS 1 | https://github.com/ros2/ros2_documentation/blob/lyrical/source/Migration-and-Upgrades/Migrating-from-ROS1/Migrating-Launch-Files.rst | primary | A
- ROS 2 Documentation — About Quality of Service settings (policy compatibility) | https://github.com/ros2/ros2_documentation/blob/rolling/source/ROS-Framework/interfaces/topics/About-Quality-of-Service-Settings.rst | primary | A
- ros2/rmw — qos_profiles.h (default and sensor data profiles) | https://github.com/ros2/rmw/blob/jazzy/rmw/include/rmw/qos_profiles.h | primary | A
- rosdistro — distribution.yaml (mavros 2.17.0, ros1_bridge without a release in Humble/Jazzy/Kilted/Lyrical) | https://github.com/ros/rosdistro/blob/master/jazzy/distribution.yaml | primary | A

## checklist
- I know how ROS 1 concepts map to ROS 2 and what really changes
- I choose the target distribution by the narrowest dependency (AP_DDS means Humble, PX4 means Jazzy) and know the EOL dates
- I set the domain, the RMW and the subscription QoS explicitly; I subscribe to MAVROS 2 telemetry with sensor data
- I read a ROS 1 project through its launch files and draw the node graph
- I choose between a bridge and a port
- I replace the rate.sleep loop with a timer, and synchronous services with asynchronous ones
- I check the port against recorded reference data
