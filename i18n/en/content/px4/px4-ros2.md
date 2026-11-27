---
id: px4-ros2
title: "PX4 and ROS 2: uXRCE-DDS and offboard"
level: L4
readingTime: 45 min
firmware: PX4 1.18 (checked against the v1.17.0 source; v1.18.0 differences noted) · ROS 2 Humble (recommended by the v1.17 docs) / Jazzy · Micro XRCE-DDS Agent v2.4.2/v2.4.3
status: published
added: 2026-11-08
tags:
  - ROS 2
  - uXRCE-DDS
  - offboard
related:
  - px4-architecture
  - ap-companion
next:
  - px4-companion-jetson
source: content/px4/px4-ros2.md
source_hash: 0a7d761c07a7
---

## summary
PX4 can expose uORB topics directly in ROS 2: the uXRCE-DDS client on the flight controller and the agent on the companion computer carry messages both ways. ROS nodes get attitude, position and commands without a MAVLink wrapper. This module shows how the bridge works inside (where topic names with the `_vN` suffix come from, rates and QoS, how timestamps are translated), how to bring it up in SITL and on board, what `px4_msgs` is, how offboard control works (`OffboardControlMode` + `TrajectorySetpoint` + `VehicleCommand`), and the exact rule by which PX4 drops you out of Offboard when you go quiet. Lab: a script reads `dds_topics.yaml` and the PX4 1.17.0 message definitions, prints the topic names, rate caps and UART load, and computes when Offboard is lost; then your own offboard node in SITL.

## theory
### The uXRCE-DDS bridge
- The **client** `uxrce_dds_client` in PX4 publishes and subscribes to a limited set of uORB topics (listed in `dds_topics.yaml`).
- The **agent** `MicroXRCEAgent` on a companion computer or PC receives them over UDP or serial and exposes them in DDS, which means in ROS 2.
- On the ROS 2 side the messages come from the `px4_msgs` package; **the `px4_msgs` branch must match the PX4 version** (`release/1.17` for 1.17), or the definitions will not match. Since 1.16 messages are versioned: the topic of a message with a version above 0 gets a `_vN` suffix. In 1.17.0 these are the outgoing `vehicle_status_v1`, `vehicle_local_position_v1`, `battery_status_v1`, `home_position_v1`, `airspeed_validated_v1`, `arming_check_request_v1` and the incoming `vehicle_attitude_setpoint_v1`, `arming_check_reply_v1`; in 1.16 only `vehicle_status_v1`, and 1.15 has no suffixes. For mismatched versions there is the Message Translation Node (experimental since 1.16).

Topics appear in ROS 2 as `/fmu/out/*` (from PX4) and `/fmu/in/*` (to PX4). The client builds the name: the string from `dds_topics.yaml` plus `_vN` if the `.msg` sets `MESSAGE_VERSION` = N > 0 (`generate_topic_name()` in `src/modules/uxrce_dds_client/utilities.hpp`). So `VehicleLocalPosition.msg` (version 1) gives `/fmu/out/vehicle_local_position_v1`, and `TrajectorySetpoint.msg` (version 0) gives `/fmu/in/trajectory_setpoint` with no suffix. If a topic is not in `dds_topics.yaml`, it is not in ROS 2 either, however hard you look: 1.17.0 has 27 outgoing and 38 incoming topics, and `vehicle_angular_velocity`, for example, is commented out. To add a topic you edit `dds_topics.yaml` and rebuild the firmware; there is no parameter for it.

{{diagram:px4-dds-topic-naming|The _v1 suffix depends on the message version, not on the direction: the old name without the suffix goes silent after upgrading to 1.17.}}

The version changes with an incompatible field change, and the next release may bump it. In PX4 1.18.0 (released November 24, 2026, UTC) `VehicleStatus` became version 4 and the topic is `/fmu/out/vehicle_status_v4`; `vehicle_command_ack` got the `_v1` suffix, the `vehicle_attitude` cap dropped from 100 to 50 Hz, and `arming_check_request_v1` lost its 5 Hz cap (with no `rate_limit` it now runs at the default interval of 4 ms, up to 250 Hz); new outgoing topics were added (`vtx`, `input_rc`, `config_overrides_confirm_v1` and others), and the step 1 output for v1.18.0 gives the full list (checked with the lab below on the v1.17.0 and v1.18.0 tags). The lesson: do not type the topic name into a node by hand; build it from the message class's `MESSAGE_VERSION` constant, so updating `px4_msgs` together with the firmware changes the name by itself.

Inside, the client works like this (read from the `uxrce_dds_client` code, v1.17.0). On start it creates a session with the agent (key `UXRCE_DDS_KEY`, domain `UXRCE_DDS_DOM_ID`), then a DataWriter for each `publications` entry and a DataReader for each `subscriptions` entry. The client checks the link with pings: if the traffic in either direction is zero, it pings the agent once a second and after three missed replies (~3 s) tears down the session and creates it again (`checkConnectivity()`). `UXRCE_DDS_TX_TO` (3 s) drops the session if the client itself has sent nothing for that many seconds, `UXRCE_DDS_RX_TO` (default −1, disabled) if it has received nothing. So after an agent restart the client usually restores the session by itself, without rebooting the flight controller (read from the code, not tested on a bench); if `/fmu/in/*` topics do not get through after a restart, enable `UXRCE_DDS_RX_TO`. The client sends every topic in `publications` whether or not anyone in ROS 2 subscribes to it: the link load is set by the list in the firmware, not by your nodes.

### Rates, QoS and bandwidth
The `rate_limit` field in `dds_topics.yaml` caps the rate of each outgoing topic: the client calls `orb_set_interval()` with a period of 1000/`rate_limit` ms, truncated to whole milliseconds, and 10 ms without `rate_limit` (`UXRCE_DEFAULT_POLL_INTERVAL_MS`). So a topic without `rate_limit` goes out **no faster than 100 Hz**, even if uORB publishes it at 250 Hz, and the stock `dds_topics.yaml` of 1.17.0 has no values above 100, so every outgoing topic is capped at 100 Hz (your own `rate_limit: 200.` in a custom build would raise the cap): `vehicle_odometry` and `vehicle_attitude` up to 100 Hz, `vehicle_local_position_v1` up to 50, `vehicle_status_v1` up to 5, `battery_status_v1` up to 1 Hz. The real rate can be lower than the cap if the PX4 module publishes less often. In 1.18.0 the default interval is 4 ms (250 Hz), the period is rounded to the nearest millisecond, and `rate_limit: 0` (or `unlimited`) removes the cap (`generate_dds_topics.py`, `dds_topics.h.em`, v1.18.0).

QoS is hard-coded in the client: outgoing DataWriters are BEST_EFFORT, TRANSIENT_LOCAL, KEEP_LAST; incoming DataReaders are BEST_EFFORT, VOLATILE, KEEP_LAST. The DDS compatibility rules turn this into a simple rule: **a ROS 2 subscriber to `/fmu/out/*` must be BEST_EFFORT** (a RELIABLE subscriber is incompatible with a best-effort writer: the topic shows in `ros2 topic list`, but no data arrives), while a publisher to `/fmu/in/*` can be either. The ready-made profile is `qos_profile_sensor_data`.

Bandwidth is the main limit on a UART. An 8N1 byte takes 10 bits, so 921600 baud is 92160 bytes/s. A message's CDR size is computed field by field, with each field aligned to its own size (the same walk as in `Tools/msg/templates/ucdr/msg.h.em`): `VehicleOdometry` is 114 bytes, `VehicleLocalPosition` 216, `TrajectorySetpoint` 64, `OffboardControlMode` 15. On serial, each sample adds a submessage header and a WRITE_DATA header (4 + 4 bytes, padded to 4), and each serial message adds the XRCE header (4 bytes: PX4's session 0x81 carries no client key) and the framing (0x7E flag, addresses, length, CRC: 7 bytes), shared by the samples sent together: at most ~23 bytes per sample if every sample went alone, a pessimistic course estimate from the client source. If all 27 outgoing topics of 1.17.0 ran at their caps, that would be up to 107 495 bytes/s (upper bound), more than 921600 baud can carry. In practice some topics publish below their cap (`vehicle_command_ack` only on a command), but the margin is thin: `uxrce_dds_client status` shows the actual traffic (the `Payload tx` and `Payload rx` lines, in B/s). `Payload tx` counts only the CDR data, without the headers (up to ~23 bytes per sample) (`num_payload_sent += topic_size` in `dds_topics.h.em`): with every topic at its cap it would show ~78 900 bytes/s while up to ~107 500 go over the wire. So keep `Payload tx` below ~50 % of the chosen baud rate in bytes/s (a course guideline: with headers that is about 70 % of the line; at 921600, below ~46 000 bytes/s). Fixes: 1.5–3 Mbaud (the client accepts `-b` up to 3000000), Ethernet where available, or a trimmed `dds_topics.yaml` in your own build.

### Timestamps and timesync
The agent and PX4 have different clocks: Linux counts time from the epoch or from system start, PX4 from flight controller power-on. With `UXRCE_DDS_SYNCT = 1` (the default) the client measures the offset between them and translates the `timestamp` and `timestamp_sample` fields of every message: it adds the offset on the way out and subtracts it on the way in. For incoming messages the serialization template (`Tools/msg/templates/ucdr/msg.h.em`) has two rules: `timestamp = 0` is replaced by the arrival time (`hrt_absolute_time()`), and a timestamp "from the future" is clamped to the current PX4 time. A timestamp from the past is not corrected, and that is the trap. A node that takes its time from a clock running a second and a half behind (simulation time with `use_sim_time`, a wrong offset, timesync disabled) sends an `OffboardControlMode` that PX4 already sees as stale: Offboard is unavailable even though the stream runs at 10 Hz. To check, run `ros2 topic echo --once /fmu/out/timesync_status` and look for `timesync converged: true` in `uxrce_dds_client status`. The reliable option for your own nodes is to stamp with the node's clock after timesync has converged, or to send 0 and let PX4 stamp it.

### Offboard: three messages
1. **`OffboardControlMode`** tells PX4 *what* you control (position, velocity, acceleration, attitude, body rates, thrust and torque, direct actuators). It must stream **before** switching to Offboard and the whole time in it; the exit rule is below.
2. **`TrajectorySetpoint`** is the target itself: position/velocity/acceleration in NED (Z down!), yaw and yawspeed. A field set to NaN means "do not control this quantity": that is how you command, for example, velocity only, with `position = [NaN, NaN, NaN]`.
3. **`VehicleCommand`** carries commands: change mode (`VEHICLE_CMD_DO_SET_MODE` = 176, Offboard = base 1, custom 6), arm (`VEHICLE_CMD_COMPONENT_ARM_DISARM` = 400, param1 = 1). The acknowledgment is `VehicleCommandAck` on `/fmu/out/vehicle_command_ack`.

Same philosophy as GUIDED in ArduPilot: the companion streams advice, the autopilot watches the timeout and the pilot can always take over.

### What exactly PX4 checks, and what happens when the link breaks
The documentation states the rule as "PX4 exits Offboard if the `OffboardControlMode` rate drops below about 2 Hz". The code is more precise (`HealthAndArmingChecks/checks/offboardCheck.cpp`, v1.17.0): the Offboard signal counts as available if the last message has at least one flag set **and** its `timestamp` is younger than `COM_OF_LOSS_T` (1.0 s by default). On top of that there are estimator conditions: the `position` flag needs a valid local position, `velocity` a valid velocity, `acceleration` (and since 1.18.0 also `attitude`) a valid attitude. Three conclusions follow from the code. First: the exit time is the timestamp of the last message plus `COM_OF_LOSS_T`; a 10 Hz node stopped at 5.0 s last sent at 4.9 s, and PX4 leaves Offboard at 5.9 s. Second: "2 Hz" is a margin, not a threshold: at 2 Hz one missed message gives a gap of exactly 1.0 s, and with delivery latency the signal is already lost. Third: a node that stalls for 1.2 s (heavy inference in the same process) drops out of Offboard at any rate, so keep the publishing timer in a separate thread or process.

What happens next is set by `COM_OBL_RC_ACT`: 0 Position (the default), 1 Altitude, 2 Stabilized (Manual before 1.16), 3 Return, 4 Land, 5 Hold, 6 Terminate, 7 Disarm. The switch is done by `checkModeFallback()` in `failsafe.cpp`. In 1.17, if Position, Altitude or Stabilized is selected and there is no manual control at that moment, PX4 executes the RC loss action `NAV_RCL_ACT` (default 2, Return; 1.15 and 1.16 had no such check; 1.18 does the same, and with the new `NAV_RCL_ACT` = 7 "Hold mode (no failsafe)" it takes Hold instead of the manual mode, `failsafe.h`, v1.18.0). For a vehicle without a radio, controlled only by the companion, it makes sense to set `COM_OBL_RC_ACT` = 4 (Land) or 3 (Return) right away: in 1.17 without manual control PX4 replaces Position with `NAV_RCL_ACT` anyway, but in 1.16 and earlier, and in 1.17 with a live radio and no pilot, Position means hovering in place until the battery runs out.

Two neighboring protections get confused with this one. `NAV_DLL_ACT` (GCS link loss, default 0, disabled, timeout `COM_DL_LOSS_T` = 10 s) triggers on the MAVLink heartbeat from the ground station; the companion's DDS link plays no part in it. Bit 2 of `COM_RCL_EXCEPT` and bit 2 of `COM_DLL_EXCEPT` disable the reaction to RC and GCS loss in Offboard mode; set them only if the companion really has to fly without a radio and a ground station, and `COM_OBL_RC_ACT` is set to something safe.

{{diagram:px4-offboard-loss-timeline|PX4 exits Offboard COM_OF_LOSS_T after the timestamp of the last message (4.9 → 5.9 s); with timestamps from the past Offboard is never available, even with a 10 Hz stream.}}

{{lesson:ros2-px4|There these three messages are built into a mission state machine with pilot takeover handling and debugging from bag files.}}

### Versus MAVLink/MAVSDK
MAVLink through MAVSDK is simpler for simple jobs and needs no ROS. uXRCE-DDS is for when you need the ROS ecosystem (navigation, vision, planning), low latency and access to internal topics. The price is the tie to the firmware version: MAVLink messages stay stable for years, while `px4_msgs` changes with every release.

### Setting up the bridge on a real vehicle
PX4: `UXRCE_DDS_CFG` = TELEM2 (value 102), `SER_TEL2_BAUD` = 921600 (also the TELEM2 default); on the companion: `MicroXRCEAgent serial --dev /dev/ttyTHS1 -b 921600` (Jetson; the port name depends on the board and JetPack, `ttyTHS0` or `ttyTHS1`, checked with a loopback in px4-companion-jetson) or `udp4 -p 8888` for SITL/Wi-Fi/Ethernet. Use an agent from the v2.x branches: the PX4 1.17 documentation gives v2.4.3 for Jazzy and v2.4.2 for Humble and Foxy, and v3.x does not work with the stock PX4 client (1.18 can be built for it with `UXRCE_DDS_CLIENT_USE_DDS_V3`). For Ethernet, `UXRCE_DDS_CFG` = 1000, the agent address is `UXRCE_DDS_AG_IP` as an int32 (192.168.1.2 → −1062731518), the port is `UXRCE_DDS_PRT` (8888). Check: `ros2 topic list | grep fmu`, `ros2 topic hz /fmu/out/vehicle_odometry` (expect up to 100 Hz). If there are no topics: the port is taken by MAVLink (`MAV_1_CONFIG` on the same TELEM2 is a conflict), the baud rate, `uxrce_dds_client status` in the PX4 console.

Three more parameters solve "topics not visible" on systems with several participants. `UXRCE_DDS_DOM_ID` must match the nodes' `ROS_DOMAIN_ID` (in SITL the `rcS` script copies `ROS_DOMAIN_ID` from the environment itself). `UXRCE_DDS_NS_IDX` = N (since 1.17) adds a namespace: topics become `/uav_N/fmu/...`. With several flight controllers on one agent, each needs its own `UXRCE_DDS_KEY` (the session key, default 1), or the sessions push each other out.

### Reference: parameters and interfaces (PX4 1.17.0)
| Parameter / interface | Default | Values, unit | What it does |
|---|---|---|---|
| `UXRCE_DDS_CFG` | 0 (disabled) | 101 TELEM1, 102 TELEM2, 1000 Ethernet… | client port |
| `SER_TEL2_BAUD` | 921600 | baud | TELEM2 baud rate |
| `UXRCE_DDS_DOM_ID` | 0 | integer | DDS domain = `ROS_DOMAIN_ID` |
| `UXRCE_DDS_KEY` | 1 | ≠ 0, unique | session key on the agent |
| `UXRCE_DDS_PRT` | 8888 | 0–65535 | agent UDP port (Ethernet) |
| `UXRCE_DDS_AG_IP` | 2130706433 (127.0.0.1) | int32 | agent IP (Ethernet) |
| `UXRCE_DDS_PTCFG` | 0 | 0 Default, 1 Localhost-only, 2 Custom participant | participant on the agent |
| `UXRCE_DDS_SYNCT` | 1 | 0/1 | timestamp translation |
| `UXRCE_DDS_SYNCC` | 0 | 0/1 | set the PX4 system clock from the agent |
| `UXRCE_DDS_TX_TO` / `RX_TO` | 3 / −1 | s (< 1 disables) | drop the session if the client has sent / received nothing for that many seconds; a lost agent is caught by 3 missed pings |
| `UXRCE_DDS_NS_IDX` | −1 | −1…9999 (since 1.17) | `uav_N` namespace |
| `UXRCE_DDS_FLCTRL` | — | 0/1 | hardware flow control; **1.18.0 only** |
| `COM_OF_LOSS_T` | 1.0 | 0–60 s | Offboard signal timeout |
| `COM_OBL_RC_ACT` | 0 (Position) | 0–7 | action on Offboard loss |
| `NAV_RCL_ACT` | 2 (Return) | 1–7 (7 since 1.18) | RC loss; since 1.17 also the substitute for 0–2 above |
| `NAV_DLL_ACT` / `COM_DL_LOSS_T` | 0 / 10 | action / s | GCS (MAVLink) loss |
| `COM_RCL_EXCEPT`, `COM_DLL_EXCEPT` | 0 | bit 2 = Offboard | failsafe exceptions; bit 1 is every auto mode in 1.18 (Hold in 1.17) |
| `rate_limit` in `dds_topics.yaml` | none → 10 ms (100 Hz) | Hz | rate cap of an outgoing topic; ≤ 100 in stock |
| `MicroXRCEAgent serial --dev <port> -b <baud>` / `udp4 -p 8888` | — | agent v2.4.x | the companion side |
| `uxrce_dds_client status` | — | PX4 console | link, `Payload tx/rx`, timesync |

### Coordinate frames: the main source of errors
PX4 works in NED (north-east-down) and FRD (forward-right-down); ROS 2 (REP-103) in ENU and FLU. `TrajectorySetpoint.position = [x, y, z]` is NED: z = −10 means 10 m up. Conversions: ENU→NED: (x, y, z) → (y, x, −z); FLU→FRD: (x, y, z) → (x, −y, −z); heading: yaw_NED = π/2 − yaw_ENU (ENU measures heading from east counterclockwise, NED from north clockwise). The `px4_ros_com` package has conversion utilities; MAVROS does it for you. A sign error in z is the classic "the vehicle flew into the ground on takeoff in the simulator".

{{lesson:math-linalg-rot|If you do the ENU↔NED conversion and the heading quaternions yourself rather than with a utility, the rotation math is worked through there without sign errors.}}

### A minimal offboard node (Python, rclpy)
```python
import rclpy
from rclpy.node import Node
from px4_msgs.msg import OffboardControlMode, TrajectorySetpoint, VehicleCommand
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy

class Offboard(Node):
    def __init__(self):
        super().__init__("offboard_min")
        qos = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                         history=HistoryPolicy.KEEP_LAST, depth=1)   # PX4 publishes best-effort
        self.mode_pub = self.create_publisher(OffboardControlMode, "/fmu/in/offboard_control_mode", qos)
        self.sp_pub = self.create_publisher(TrajectorySetpoint, "/fmu/in/trajectory_setpoint", qos)
        self.cmd_pub = self.create_publisher(VehicleCommand, "/fmu/in/vehicle_command", qos)
        self.n = 0
        self.create_timer(0.1, self.step)                               # 10 Hz > 2 Hz minimum

    def cmd(self, command, p1=0.0, p2=0.0):
        m = VehicleCommand(command=command, param1=p1, param2=p2, target_system=1, target_component=1,
                           source_system=1, source_component=1, from_external=True,
                           timestamp=int(self.get_clock().now().nanoseconds / 1000))
        self.cmd_pub.publish(m)

    def step(self):
        now = int(self.get_clock().now().nanoseconds / 1000)
        self.mode_pub.publish(OffboardControlMode(position=True, timestamp=now))
        self.sp_pub.publish(TrajectorySetpoint(position=[0.0, 0.0, -5.0], yaw=0.0, timestamp=now))  # 5 m up (NED)
        if self.n == 10:                                                # after 1 s of setpoints
            self.cmd(VehicleCommand.VEHICLE_CMD_DO_SET_MODE, 1.0, 6.0)  # Offboard
            self.cmd(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 1.0)
        self.n += 1

rclpy.init(); rclpy.spin(Offboard())
```
The safeguards from the "Tracking" module (limits, watchdog, the `COM_OF_LOSS_T` = 1 s timeout and the `COM_OBL_RC_ACT` action) are mandatory here too. The `timestamp` here comes from the node's clock; that works as long as timesync has converged and the node is not on simulation time (see the timestamps section above).

{{diagram:px4-offboard-seq|Offboard from ROS 2: OffboardControlMode and TrajectorySetpoint stream before the mode switch, then the mode and arm commands; on a link break, the failsafe.}}

### Place in the system

- **Takes in:** uORB topics through `uxrce_dds_client` (`px4-architecture`); the on-board port and baud rate `UXRCE_DDS_CFG` (`px4-companion-jetson`); QoS and the ROS 2 axis conventions (`ros2-basics`).
- **Hands on:** `/fmu/out/*` to ROS 2 nodes; `TrajectorySetpoint` to the position controller (`px4-control`); the three Offboard messages to the state machine (`ros2-px4`) and the tracking loop (`per-tracking`).
- **If you get it wrong here:** you send an ENU setpoint without converting to NED → z with an "up" sign drives the vehicle into the ground on takeoff (`math-linalg-rot`). The node stalls on inference longer than `COM_OF_LOSS_T` → PX4 exits Offboard per `COM_OBL_RC_ACT`, which looks like a spontaneous mode change from the outside (`ros2-app-arch`). The topic name is typed by hand → after a firmware upgrade to 1.18 `vehicle_status_v1` goes silent and the node treats the status as stale (`ros2-px4`).

## practice
### Step 1. The bridge on paper: names, rates, load, timeout
This step runs on any computer with Python 3 and internet access, with no ROS and no simulator. The script downloads `dds_topics.yaml` and the `.msg` files it needs for the chosen PX4 tag from GitHub, builds the ROS names with suffixes, computes the CDR message sizes with the same field walk as the PX4 generator, the rate cap from `rate_limit` and the UART load, and then the moment the Offboard signal is lost under the `offboardCheck.cpp` rule. Save it as `px4_dds_lab.py`:
```python
import math, re, sys, urllib.request

TAG = sys.argv[1] if len(sys.argv) > 1 else "v1.17.0"
RAW = f"https://raw.githubusercontent.com/PX4/PX4-Autopilot/{TAG}/"
SIZE = {"bool": 1, "char": 1, "int8": 1, "uint8": 1, "int16": 2, "uint16": 2,
        "int32": 4, "uint32": 4, "float32": 4, "int64": 8, "uint64": 8, "float64": 8}
MSG = {}

def get(rel):
    try:
        return urllib.request.urlopen(RAW + rel, timeout=20).read().decode()
    except Exception:
        return None

def msg(name):                       # -> (MESSAGE_VERSION, [(type, count)])
    if name not in MSG:
        ver, fields = 0, []
        for line in (get(f"msg/versioned/{name}.msg") or get(f"msg/{name}.msg")).splitlines():
            s = line.split("#")[0].strip()
            m = re.match(r"uint32\s+MESSAGE_VERSION\s*=\s*(\d+)", s)
            ver = int(m.group(1)) if m else ver
            if s and "=" not in s:
                t = s.split()[0]
                n = int(t[t.index("[") + 1:-1]) if "[" in t else 1
                fields.append((t.split("[")[0].split("/")[-1], n))
        MSG[name] = (ver, fields)
    return MSG[name]

def cdr(name, off=0):                # same walk as Tools/msg/templates/ucdr/msg.h.em
    for t, n in msg(name)[1]:
        if t in SIZE:
            off += (SIZE[t] - off % SIZE[t]) & (SIZE[t] - 1)
            off += SIZE[t] * n
        else:
            for _ in range(n):
                off = cdr(t, off)
    return off

sec, rows = None, []
for line in get("src/modules/uxrce_dds_client/dds_topics.yaml").splitlines():
    s = line.split("#")[0].strip()
    if re.match(r"^[a-z_]+:$", s):
        sec = s[:-1]
    elif s.startswith("- topic:"):
        rows.append([sec, s.split(":", 1)[1].strip(), None, None])
    elif s.startswith("type:"):
        rows[-1][2] = s.split("::")[-1]
    elif s.startswith("rate_limit:"):
        rows[-1][3] = float(s.split(":")[1])

total = 0
for sec, topic, typ, r in rows:
    ver = msg(typ)[0]
    name = topic + (f"_v{ver}" if ver else "")
    if sec == "publications":
        cap = 1000 / (int(1e3 / r) if r else 10)          # orb_set_interval in whole ms, 10 ms default
        total += cap * (cdr(typ) + 23)                    # +23 B XRCE/serial overhead (course estimate)
    if ver or typ in ("TrajectorySetpoint", "OffboardControlMode", "VehicleOdometry"):
        print(f"{name:40s} v{ver}  {cdr(typ):4d} B" + (f"  cap {cap:5.1f} Hz" if sec == "publications" else ""))
print(f"out {sum(r[0] == 'publications' for r in rows)}, in {sum(r[0] != 'publications' for r in rows)}; "
      f"all /fmu/out at caps: {total:.0f} B/s vs {921600 // 10} B/s on UART 921600")

LOSS_T = 1.0                                              # COM_OF_LOSS_T, s
for hz, stop, shift in ((10, 5.0, 0.0), (2, 5.0, 0.0), (10, 99.0, -1.5)):
    last = math.floor((stop - 1e-9) * hz) / hz + shift    # timestamp PX4 sees for the last message
    print(f"{hz:2d} Hz, stop {stop:4.1f} s, stamp shift {shift:+.1f} s -> " +
          ("never available" if shift <= -LOSS_T else f"signal lost at {last + LOSS_T:.1f} s"))
```
Running `python3 px4_dds_lab.py v1.17.0` gave (2026-11-26):
```
/fmu/out/arming_check_request_v1         v1    16 B  cap   5.0 Hz
/fmu/out/battery_status_v1               v1   176 B  cap   1.0 Hz
/fmu/out/vehicle_local_position_v1       v1   216 B  cap  50.0 Hz
/fmu/out/vehicle_odometry                v0   114 B  cap 100.0 Hz
/fmu/out/vehicle_status_v1               v1    80 B  cap   5.0 Hz
/fmu/out/airspeed_validated_v1           v1    44 B  cap  50.0 Hz
/fmu/out/home_position_v1                v1    60 B  cap   5.0 Hz
/fmu/in/arming_check_reply_v1            v1   227 B
/fmu/in/offboard_control_mode            v0    15 B
/fmu/in/trajectory_setpoint              v0    64 B
/fmu/in/vehicle_attitude_setpoint_v1     v1    40 B
/fmu/in/vehicle_mocap_odometry           v0   114 B
/fmu/in/vehicle_visual_odometry          v0   114 B
out 27, in 38; all /fmu/out at caps: 107495 B/s vs 92160 B/s on UART 921600
10 Hz, stop  5.0 s, stamp shift +0.0 s -> signal lost at 5.9 s
 2 Hz, stop  5.0 s, stamp shift +0.0 s -> signal lost at 5.5 s
10 Hz, stop 99.0 s, stamp shift -1.5 s -> never available
```
Read the output as a map of the bridge. The first seven lines are exactly the names to subscribe to in 1.17.0; `vehicle_local_position` has the suffix, `vehicle_odometry` does not. The total line shows that all outgoing topics at their caps do not fit into 921600 baud: 107 495 versus 92 160 bytes/s, or 117 % (~78 900 bytes/s of it is CDR data, which is what `Payload tx` shows); on a real vehicle watch `Payload tx`. The last three lines are the Offboard exit rule: last message plus 1 s, and "never available" with timestamps from the past. Then run `python3 px4_dds_lab.py v1.18.0`: the output shows `/fmu/out/vehicle_status_v4` instead of `_v1` and `/fmu/out/vehicle_command_ack_v1`, and the total grows to 117 077 bytes/s (31 outgoing topics); that is what a firmware upgrade looks like to a node with hard-coded names. The script applies the 1.17 rate rule (10 ms default, truncation); with the 1.18.0 rule (4 ms default, rounding) the same 31 topics at their caps come to 198 077 bytes/s.

### Step 2. The ROS 2 environment (on your machine)
```
# ROS 2 Humble (Ubuntu 22.04, recommended by the PX4 v1.17 docs) or Jazzy (Ubuntu 24.04), sourced
mkdir -p ~/ws_px4/src && cd ~/ws_px4/src
git clone -b release/1.17 https://github.com/PX4/px4_msgs.git      # branch matching your PX4 version
git clone https://github.com/PX4/px4_ros_com.git
cd .. && colcon build && source install/setup.bash
```

Agent: `MicroXRCEAgent udp4 -p 8888` (built from source on the v2.4.3 branch for Jazzy or v2.4.2 for Humble, or the snap from the `--edge` channel; the stable snap, according to the PX4 documentation, fails when creating topics). Steps 2–5 were not run on the course authors' server (no ROS 2 and no space for a SITL build); the criteria below come from the documentation and the v1.17.0 code.

### Step 3. SITL with the client
`make px4_sitl gz_x500`: in SITL the uXRCE-DDS client starts on its own (`uxrce_dds_client start -t udp -p 8888` in `rcS`) and looks for the agent on 8888. Check: `ros2 topic list` shows `/fmu/out/vehicle_attitude` and others; `ros2 topic echo /fmu/out/vehicle_local_position_v1` (`/fmu/out/vehicle_local_position` without the suffix before 1.17). In the PX4 console, `uxrce_dds_client status` shows `Running, connected`, `timesync converged: true` and `Payload tx` in B/s: compare it with the step 1 total without headers (~78 900 bytes/s if every topic runs at its cap).

### Step 4. The offboard example
Run the example from `px4_ros_com` (offboard control): the node sends `OffboardControlMode` + `TrajectorySetpoint` for 10 cycles, then switches the mode and arms through `VehicleCommand`, and after that holds a point at 5 m. Read the code: the order "stream first, then the mode" is the key.

### Step 5. Your own node
Write a Python node (`rclpy`) that holds the quadcopter at 3 m and every 10 s moves the target around a circle of radius 5 m. Check: stop the node, and after ~1 s (`COM_OF_LOSS_T`, 1 s by default) PX4 exits Offboard (in SITL it switches per `COM_OBL_RC_ACT`; without a radio, since 1.17, per `NAV_RCL_ACT`).

A skeleton (structured like the `px4_ros_com` example; check the topic names against `ros2 topic list` for your PX4 version):
```python
import math
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
from px4_msgs.msg import OffboardControlMode, TrajectorySetpoint, VehicleCommand

QOS = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                 history=HistoryPolicy.KEEP_LAST, depth=1)

class Circle(Node):
    def __init__(self):
        super().__init__("circle")
        self.mode_pub = self.create_publisher(OffboardControlMode, "/fmu/in/offboard_control_mode", QOS)
        self.sp_pub = self.create_publisher(TrajectorySetpoint, "/fmu/in/trajectory_setpoint", QOS)
        self.cmd_pub = self.create_publisher(VehicleCommand, "/fmu/in/vehicle_command", QOS)
        self.ticks = 0
        self.create_timer(0.1, self.tick)                       # 10 Hz, well above the 2 Hz minimum

    def now_us(self):
        return self.get_clock().now().nanoseconds // 1000

    def command(self, cmd, p1=0.0, p2=0.0):
        m = VehicleCommand(command=cmd, param1=p1, param2=p2, target_system=1, target_component=1,
                           source_system=1, source_component=1, from_external=True, timestamp=self.now_us())
        self.cmd_pub.publish(m)

    def tick(self):
        self.mode_pub.publish(OffboardControlMode(position=True, timestamp=self.now_us()))
        a = 2 * math.pi * (self.ticks // 100) / 6               # next point on the circle every 10 s
        sp = TrajectorySetpoint(timestamp=self.now_us())
        sp.position = [5.0 * math.cos(a), 5.0 * math.sin(a), -3.0]   # NED: z = -3 is 3 m up
        sp.yaw = float(a + math.pi)
        self.sp_pub.publish(sp)
        if self.ticks == 10:                                    # stream first, then switch mode and arm
            self.command(VehicleCommand.VEHICLE_CMD_DO_SET_MODE, 1.0, 6.0)   # custom mode 6 = Offboard
            self.command(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 1.0)
        self.ticks += 1

def main():
    rclpy.init(); rclpy.spin(Circle())

if __name__ == "__main__":
    main()
```
What to check in the log: in the `.ulg`, `trajectory_setpoint` steps every 10 s, `vehicle_local_position` catches up within 2–4 s with no more than 0.5 m of overshoot (a course guideline); on `Ctrl+C` of the node, the mode changes `COM_OF_LOSS_T` after the last `offboard_control_mode` timestamp (a gap of 1.0 ± 0.1 s in the log with SITL in real time; with `PX4_SIM_SPEED_FACTOR` ≠ 1, `rcS` multiplies the timeout by that factor).

### Moving to real hardware
Bring the bridge up on board in three passes, with the propellers off until the last one. (1) On the bench, props off, flight controller and companion powered: `uxrce_dds_client status` shows `connected`, `ros2 topic hz /fmu/out/vehicle_odometry` shows a rate no higher than 100 Hz, `Payload tx` is below 50 % of the chosen baud rate in bytes/s (a course guideline: `Payload tx` does not count headers, with them that is about 70 % of the line; at 921600, below ~46 000 bytes/s). If it is higher, raise the baud rate or trim the topic list. (2) Same place: the node streams, the mode switches to Offboard **without arming** (skip the arm in the code), then `Ctrl+C`: after ~1 s `listener failsafe_flags` shows `offboard_control_signal_lost: True` and QGC reports Offboard as unavailable; the mode itself stays, because failsafe actions run only when armed (`framework.cpp`). The `COM_OBL_RC_ACT` action is tested armed, in SITL (the check in the lab above). (3) Flight: the pilot holds the radio with a Position mode switch, the first test is a 2 m hover in an open area; the abort is a mode switch by the pilot, tested before takeoff. Abort criteria: any altitude deviation from the setpoint above 0.5 m (a course guideline), a mode change nobody commanded, `timesync converged: false`.

### Lab
Self-check: the lab is done when (no-simulator path) your step 1 run for v1.17.0 gave the same seven `/fmu/out/*_v1` names and `vehicle_odometry`, "out 27, in 38", the total of 107495 B/s and the 5.9 s and 5.5 s moments, and the run for v1.18.0 showed `vehicle_status_v4`; (SITL path) the node holds 3 m and every 10 s moves the target around a 5 m circle, in the `.ulg` `trajectory_setpoint` steps every 10 s and `vehicle_local_position` catches up within 2–4 s with no more than 0.5 m of overshoot (a course guideline), and after `Ctrl+C` of the node PX4 exits Offboard 1.0 ± 0.1 s after the last timestamp (SITL in real time), with the mode it switched to written in your notes; (hardware) the three passes from the subsection above are done without hitting any abort criterion.

**Reference answer for the self-check.** A correct result: the order "stream `OffboardControlMode` + `TrajectorySetpoint` first, then the mode and arming", the 3 m altitude given as z = −3, BEST_EFFORT subscribers, topic names built from `MESSAGE_VERSION`. Typical wrong results: (1) PX4 will not enter Offboard: the setpoints did not stream before the command, the timestamps are from the past (simulation time, timesync not converged) or there is no valid local position with the `position` flag; (2) the vehicle flies up instead of down, or takes off "into the ground": the z sign in NED; (3) `ros2 topic list` is empty: the agent is not running on 8888, the wrong agent branch (v3.x), or `UXRCE_DDS_DOM_ID` ≠ `ROS_DOMAIN_ID`; (4) in a `rate_limit` exercise (say, 60 Hz) you got 60 Hz instead of 62.5: you forgot that the 16.67 ms period is truncated to 16 ms; in step 1 the rounding makes no difference, since every 1.17.0 cap divides 1000 evenly.

## diagnostics
- **Symptom:** `ros2 topic list` is empty
  - Possible cause: the agent is not running, the wrong port, an agent from the v3.x branch, `UXRCE_DDS_DOM_ID` not equal to `ROS_DOMAIN_ID`.
  - What to do: agent v2.4.x on 8888, `uxrce_dds_client status` in the PX4 console, check the domain.
- **Symptom:** the topic shows in `ros2 topic list`, but `ros2 topic echo` is silent
  - Possible cause: a RELIABLE subscriber against PX4's best-effort writer; the wrong `px4_msgs` branch (a different type definition).
  - What to do: `qos_profile_sensor_data` or `--qos-reliability best_effort`; `px4_msgs` from `release/1.17`.
- **Symptom:** after a firmware upgrade the node no longer sees the status
  - Possible cause: the version suffix changed (1.17 → 1.18: `vehicle_status_v1` → `vehicle_status_v4`) and the name was typed by hand.
  - What to do: build the name from `MESSAGE_VERSION`, update `px4_msgs` together with the firmware, or run the Message Translation Node.
- **Symptom:** PX4 will not enter Offboard although the stream runs at 10 Hz
  - Possible cause: `timestamp` values from the past (the node is on simulation time, timesync has not converged), no valid local position with the `position` flag, the stream did not run before the command.
  - What to do: `timesync converged: true` in `uxrce_dds_client status`, a timestamp of 0 or the node's clock after convergence; check `estimator_status_flags`; stream before the mode change.
  - What you see in the log: `offboard_control_mode` arrives, but `offboard_control_signal_lost` = true in `failsafe_flags`.
- **Symptom:** it drops out of Offboard in flight
  - Possible cause: a gap in the stream longer than `COM_OF_LOSS_T`: the node stalled on inference or garbage collection, or the UART is overloaded.
  - What to do: the publishing timer in a separate thread or process, `Payload tx` against the link capacity, the companion's load.
  - What you see in the log: a gap of ≥ 1 s in `offboard_control_mode` right before the mode change.
- **Symptom:** after Offboard loss the vehicle went to Return, although `COM_OBL_RC_ACT` = Position
  - Possible cause: since 1.17, with no manual control, `NAV_RCL_ACT` runs instead of Position (Return by default; Hold in 1.18 with `NAV_RCL_ACT` = 7).
  - What to do: this is by design; set the action you want directly in `COM_OBL_RC_ACT` (Land/Return/Hold) and `NAV_RCL_ACT`.
- **Symptom:** it flies up instead of down, or takes off "into the ground" in SITL
  - Possible cause: the Z sign in NED, an ENU setpoint without conversion.
  - What to do: Z is positive down, 3 m altitude is Z = −3; ENU→NED: (x, y, z) → (y, x, −z).
- **Symptom:** topics drop out at high rates, `Payload tx` near the limit
  - Possible cause: UART 921600 is saturated (all topics at their caps are 117 % of capacity).
  - What to do: 1.5–3 Mbaud, Ethernet or a trimmed `dds_topics.yaml` in your own build.

## references
- PX4 ROS 2 User Guide | https://docs.px4.io/v1.17/en/ros2/user_guide.html | primary | A
- PX4 uXRCE-DDS | https://docs.px4.io/v1.17/en/middleware/uxrce_dds.html | primary | A
- PX4 ROS 2 Offboard Control Example | https://docs.px4.io/v1.17/en/ros2/offboard_control.html | primary | A
- PX4-Autopilot v1.17.0 — dds_topics.yaml (topic list, rate_limit) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/uxrce_dds_client/dds_topics.yaml | primary | A
- PX4-Autopilot v1.17.0 — uxrce_dds_client module.yaml (UXRCE_DDS_* parameters) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/uxrce_dds_client/module.yaml | primary | A
- PX4-Autopilot v1.17.0 — offboardCheck.cpp (offboard signal rule) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/commander/HealthAndArmingChecks/checks/offboardCheck.cpp | primary | A
- PX4 ROS 2 Message Translation Node | https://docs.px4.io/v1.17/en/ros2/px4_ros2_msg_translation_node.html | primary | A
- px4_msgs (GitHub, branch release/1.17) | https://github.com/PX4/px4_msgs | primary | A
- px4_ros_com (GitHub) | https://github.com/PX4/px4_ros_com | primary | A
- eProsima Micro XRCE-DDS Agent | https://github.com/eProsima/Micro-XRCE-DDS-Agent | primary | A

## checklist
- Agent v2.4.x and the client are connected, the topics show in ROS 2, the domain matches
- The `px4_msgs` branch matches the PX4 version, topic names are built from `MESSAGE_VERSION`
- Subscribers to `/fmu/out/*` are BEST_EFFORT
- `Payload tx` is comfortably below the link capacity
- The node's timestamps are checked (timesync converged, not simulation time)
- My node streams `OffboardControlMode` with no gaps longer than `COM_OF_LOSS_T`
- `COM_OBL_RC_ACT` and `NAV_RCL_ACT` are chosen on purpose, and the behavior when the node stops is tested
