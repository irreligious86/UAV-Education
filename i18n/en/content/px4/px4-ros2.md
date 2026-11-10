---
id: px4-ros2
title: "PX4 and ROS 2: uXRCE-DDS and offboard"
level: L4
readingTime: 30 min
firmware: PX4 1.15+ / ROS 2 Jazzy (Humble as a fallback)
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
source_hash: df1e92027766
---

## summary
In PX4 you can expose uORB topics directly to ROS 2: the uXRCE-DDS client on the flight controller and the agent on the companion computer pass messages in both directions. This gives ROS nodes access to attitude, position and commands without a MAVLink wrapper. This module shows how to bring up the bridge in SITL, what `px4_msgs` is, how offboard control works (`OffboardControlMode` + `TrajectorySetpoint` + `VehicleCommand`) and why PX4 kicks you out of Offboard if you go quiet.

## theory
### The uXRCE-DDS bridge
- The **client** `uxrce_dds_client` in PX4 publishes/subscribes to a limited set of uORB topics (the list is `dds_topics.yaml`).
- The **agent** `MicroXRCEAgent` on the companion or a PC receives them over UDP or serial and exposes them in DDS — that is, in ROS 2.
- On the ROS 2 side the messages come from the `px4_msgs` package; **the `px4_msgs` branch must match the PX4 version**, otherwise the definitions don't match. For mismatched versions there is a message translation node.

The topics show up in ROS 2 as `/fmu/out/*` (from PX4) and `/fmu/in/*` (to PX4).

### Offboard: three messages
1. **`OffboardControlMode`** — tells PX4 *what* you control (position, velocity, acceleration, attitude, rates). It must be streamed **before** switching to Offboard and the whole time you are in it; below ~2 Hz PX4 exits Offboard.
2. **`TrajectorySetpoint`** — the target itself: position/velocity in NED (Z points down!), yaw.
3. **`VehicleCommand`** — commands: change mode (`VEHICLE_CMD_DO_SET_MODE`, Offboard = base 1, custom 6), arm (`VEHICLE_CMD_COMPONENT_ARM_DISARM`). The acknowledgment is `VehicleCommandAck`.

Same philosophy as GUIDED in ArduPilot: the companion gives advice as a stream, the autopilot watches the timeout, and the pilot can always take over.

### Versus MAVLink/MAVSDK
MAVLink via MAVSDK is simpler for simple tasks and doesn't require ROS. uXRCE-DDS is for when you need the ROS ecosystem (navigation, vision, planning), low latency and access to internal topics.

### Setting up the bridge on a real aircraft
PX4: `UXRCE_DDS_CFG` = TELEM2 (port), `SER_TEL2_BAUD` = 921600; on the companion: `MicroXRCEAgent serial --dev /dev/ttyTHS1 -b 921600` (Jetson) or `udp4 -p 8888` for SITL/Wi-Fi. Check: `ros2 topic list | grep fmu`, `ros2 topic hz /fmu/out/vehicle_odometry` (expect tens to hundreds of Hz). If there are no topics: the port is taken by MAVLink (`MAV_1_CONFIG` on the same TELEM2 — a conflict), the baud rate, `uxrce_dds_client status` in the PX4 console.

### Coordinate frames — the main source of bugs
PX4 works in NED (north-east-down) and FRD (forward-right-down); ROS 2 (REP-103) uses ENU and FLU. `TrajectorySetpoint.position = [x, y, z]` is NED: z = −10 means 10 m up. Conversions: ENU→NED: (x, y, z) → (y, x, −z); FLU→FRD: (x, y, z) → (x, −y, −z). The `px4_ros_com` package has conversion utilities; MAVROS does it for you. A sign error in z is the classic “the vehicle dove into the ground on takeoff in the simulator”.

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
The safeguards from the “Tracking” module (limits, watchdog, the `COM_OF_LOSS_T` = 1 s timeout and the `COM_OBL_RC_ACT` action) are mandatory here too.

{{diagram:px4-offboard-seq|Offboard from ROS 2: a stream of OffboardControlMode and TrajectorySetpoint before the mode switch, then the mode and arm commands; on a link loss — failsafe.}}

## practice
### Step 1. Environment
```
# ROS 2 Jazzy (Ubuntu 24.04) installed and sourced; fallback option is Humble (22.04)
mkdir -p ~/ws_px4/src && cd ~/ws_px4/src
git clone https://github.com/PX4/px4_msgs.git      # branch matching your PX4 version
git clone https://github.com/PX4/px4_ros_com.git
cd .. && colcon build && source install/setup.bash
```

Agent: `MicroXRCEAgent udp4 -p 8888` (build from source or snap — see the documentation).

### Step 2. SITL with the client
`make px4_sitl gz_x500` — in SITL the uXRCE-DDS client starts on its own and looks for the agent on 8888. Check: `ros2 topic list` shows `/fmu/out/vehicle_attitude` and others; `ros2 topic echo /fmu/out/vehicle_local_position` (since PX4 1.17 — `/fmu/out/vehicle_local_position_v1`).

### Step 3. The offboard example
Run the example from `px4_ros_com` (offboard control): the node sends `OffboardControlMode` + `TrajectorySetpoint` for 10 cycles, then switches mode and arms via `VehicleCommand`, and after that holds a point at 5 m. Read the code: the order “stream first, then mode” is the key.

### Step 4. Your own node
Write a Python node (`rclpy`) that holds a quadcopter at 3 m altitude and every 10 s moves the target around a circle of 5 m radius. Check: stop the node — after ~1 s (`COM_OF_LOSS_T`, 1 s by default) PX4 exits Offboard (in SITL it switches to Hold/Land depending on the failsafe setting).

Skeleton (structure as in the `px4_ros_com` example; check the topic names against `ros2 topic list` for your PX4 version):
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
What to check in the log: in the `.ulg`, `trajectory_setpoint` steps every 10 s, `vehicle_local_position` catches up within 2–4 s with no overshoot greater than 0.5 m; on `Ctrl+C` of the node — a mode change after `COM_OF_LOSS_T`.

### Lab
The node works in SITL; the `.ulg` log shows `vehicle_local_position` against `trajectory_setpoint`; the behavior when the node stops is documented.

## diagnostics
- **Symptom:** `ros2 topic list` is empty
  - Possible cause: the agent isn't running, wrong port, `px4_msgs` version mismatch.
  - What to do: start the agent on 8888, check the `px4_msgs` branch.
- **Symptom:** it doesn't switch to Offboard
  - Possible cause: `OffboardControlMode` wasn't streamed before the command.
  - What to do: send the stream at ≥ 2 Hz in advance, then the mode.
- **Symptom:** it gets kicked out of Offboard in flight
  - Possible cause: the `OffboardControlMode` rate dropped below ~2 Hz.
  - What to do: the node's timer, check the companion's load.
- **Symptom:** it flies up instead of down
  - Possible cause: the sign of Z in NED.
  - What to do: Z is positive down, an altitude of 3 m is Z = −3.
- **Symptom:** PX4 won't enter Offboard
  - Possible cause: setpoints weren't sent for ≥ 1 s before the command, rate < 2 Hz, wrong QoS.
  - What to do: stream before the mode change, 10+ Hz, BEST_EFFORT QoS; `commander status`.
- **Symptom:** takeoff “into the ground” in SITL
  - Possible cause: the sign of z (NED).
  - What to do: z is negative up; check the ENU/NED conversion.

## references
- PX4 ROS 2 User Guide | https://docs.px4.io/main/en/ros2/user_guide.html | primary | A
- PX4 uXRCE-DDS | https://docs.px4.io/main/en/middleware/uxrce_dds.html | primary | A
- PX4 ROS 2 Offboard Control Example | https://docs.px4.io/main/en/ros2/offboard_control.html | primary | A
- px4_msgs (GitHub) | https://github.com/PX4/px4_msgs | primary | A
- px4_ros_com (GitHub) | https://github.com/PX4/px4_ros_com | primary | A

## checklist
- The agent and the client are connected, the topics are visible in ROS 2
- The `px4_msgs` branch matches the PX4 version
- The offboard example has been run and read
- Your own node keeps the `OffboardControlMode` stream at ≥ 2 Hz
- The behavior when the node stops has been checked
