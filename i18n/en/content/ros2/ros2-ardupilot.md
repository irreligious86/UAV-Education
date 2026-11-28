---
id: ros2-ardupilot
title: "ROS 2 + ArduPilot: AP_DDS and MAVROS, one node, two routes"
level: L3
readingTime: 60 min
firmware: ArduPilot 4.7 (AP_DDS; checked against 4.7.3, lab captured on SITL 4.7.2) · ROS 2 Humble
status: published
added: 2026-11-08
tags:
  - ROS 2
  - ArduPilot
  - AP_DDS
  - MAVROS
  - GUIDED
related:
  - ros2-px4
  - ap-companion
  - mav-sdk
next:
  - per-tracking
source: content/ros2/ros2-ardupilot.md
source_hash: 0db90037d8f7
---

## summary
ArduPilot has two routes into ROS 2. **AP_DDS** is the DDS client built into the firmware (the same principle as uXRCE-DDS in PX4): `/ap/*` topics in ENU and standard ROS types, services for arming and mode changes, velocity control through `/ap/cmd_vel`. **MAVROS** is a MAVLink ↔ ROS bridge that works with any firmware and the full set of MAVLink functions, at the cost of an extra layer. This module takes both apart using the source and the documentation, compares them with the PX4 route, and shows how the same state machine from the ros2-px4 module flies a square on ArduPilot through AP_DDS. Everything about AP_DDS is checked against the Copter-4.7.2 source: the `DDS_*` parameters and their defaults (`DDS_ENABLE` is already 1 in a DDS-enabled build), the agent connection loop and the boot race with the companion computer, the full list of topics and services with QoS and rates, and the frame conversions, including the place where `base_link` in 4.7.2 does not behave per REP-103. Lab: checking whether your build has AP_DDS and a numerical check of the frame conversions (done), then a square in SITL through AP_DDS and through MAVROS with a latency comparison table; that procedure follows the ArduPilot documentation and was not run in the author's environment (no ROS 2 Humble).

## theory
### AP_DDS: how to connect it
The firmware contains the DDS client (`libraries/AP_DDS`, eProsima Micro XRCE-DDS Client); outside runs the micro-ROS agent (`micro_ros_agent`), which puts the data on the ROS 2 DDS network. The client is lightweight: it does not take part in DDS discovery itself, but creates the participant `ap`, publishers, subscribers and services through the agent.

{{diagram:uxrce-scheme|The same scheme as PX4: a client in the firmware, an agent on the companion computer, ordinary ROS 2 topics outside.}}

**Build.** AP_DDS is compiled only with the `--enable-DDS` option (`Tools/ardupilotwaf/boards.py`: without it `AP_DDS_ENABLED=0`, unless the board's hwdef enables it). The build needs the `microxrceddsgen` generator on the `PATH` (`libraries/AP_DDS/wscript` looks for it as mandatory) and the submodules `modules/Micro-XRCE-DDS-Client` and `modules/Micro-CDR`. The generator is ArduPilot's fork `Micro-XRCE-DDS-Gen`: branch `v4.7.0` for ArduPilot 4.7 and later, `v4.5.1` before 4.7 (ArduPilot dev wiki, "Install ROS 2"). Per the same page the only supported ROS 2 version is Humble (as of November 2026); the agent is `micro-ROS-Agent`, branch `humble` (`Tools/ros2/ros2.repos`). A regular SITL build does not have these parameters: in SITL 4.7.2 built without the option, `DDS_ENABLE` answers "no such parameter", and the binary contains not a single `rt/ap/` string (checked in the practice). This is the first check when "there are no topics".

**Transport.** UDP: `DDS_UDP_PORT` (default 2019) and the agent address `DDS_IP0`…`DDS_IP3`; the default is 127.0.0.1 in SITL and 192.168.144.2 on ChibiOS boards (`AP_DDS_config.h`). UDP on hardware needs ArduPilot's network stack (`AP_NETWORKING_ENABLED`: Ethernet on the board or PPP over a UART); otherwise use a serial port: `SERIALn_PROTOCOL = 45` (DDS XRCE) and the baud rate `SERIALn_BAUD` (115 in `dds_serial.parm` of the `ardupilot_sitl` package). One port, one protocol: a UART used for DDS no longer carries MAVLink, so a companion computer with ROS 2 and a MAVLink router takes two FC ports, or Ethernet.

| Parameter (4.7.2) | Default | Range | What it does |
|---|---|---|---|
| `DDS_ENABLE` | 1 (if DDS is compiled in) | 0, 1; reboot | enables the client; 0 turns it off without touching the build |
| `DDS_UDP_PORT` | 2019 | 1–65535 | agent port |
| `DDS_IP0`…`DDS_IP3` | 127.0.0.1 (SITL), 192.168.144.2 (ChibiOS) | octets | agent address |
| `DDS_DOMAIN_ID` | 0 | 0–232 | `ROS_DOMAIN_ID` of the agent side (0 = the ROS 2 default, same as an unset ROS_DOMAIN_ID) |
| `DDS_TIMEOUT_MS` | 1000 ms | 1–10000 | how long to wait for the agent's reply to a ping |
| `DDS_MAX_RETRY` | 10 | 0–100; 0 = no limit | pings per batch before the "exiting" message |
| `SERIALn_PROTOCOL` | — | 45 = DDS XRCE | DDS over a UART |

All `DDS_*` parameters require a reboot (`@RebootRequired: True` in `AP_DDS_Client.cpp`). The `ardupilot_sitl` package has ready-made sets: `dds_udp.parm` (`DDS_ENABLE 1`, `DDS_UDP_PORT 2019`) and `dds_serial.parm` (`DDS_ENABLE 1`, `SERIAL1_BAUD 115`, `SERIAL1_PROTOCOL 45`). The ArduPilot-specific message types are in the `ardupilot_msgs` package (`Tools/ros2/ardupilot_msgs`): the messages `Status`, `GlobalPosition`, `Rc`, `Airspeed` and the services `ArmMotors`, `ModeSwitch`, `Takeoff`; the package branch must match the firmware.

### The connection loop and the boot race
The AP_DDS thread (`AP_DDS_Client::main_loop`, 4.7.2) pings the agent after initializing the transport: each ping waits `DDS_TIMEOUT_MS` for a reply, and a batch is `DDS_MAX_RETRY` pings. If a whole batch goes unanswered, `DDS: No ping response, exiting` goes to the GCS, and the loop **continues** (`continue`) despite the word "exiting": with the defaults the client tries again every 10 s, forever. With `DDS_MAX_RETRY = 0` it pings without batches and prints `No ping response, retrying` after every failed ping, once a second, which floods the GCS messages. After a reply the session and the entities are created (`DDS: Initialization passed`); inside the session the client pings the agent every 500 ms (`DELAY_PING_MS`), and after three misses in a row (> 2) it prints `No ping response, disconnecting` and goes back to pinging. All of this is read from the code; the "exiting, but carries on" behavior is worth seeing once in SITL.

The practical consequence is a boot race. The FC is ready within seconds, a Raspberry Pi with the agent within tens of seconds. If the agent comes up at second 35 (the course's reference figure for a Pi with a systemd service), the GCS manages to show three "exiting" messages (at 12, 22 and 32 s), and the session is created on the first ping after the agent starts. This is not a configuration error; the error is to conclude from these messages that DDS "is down" and start changing parameters.

{{diagram:ros2-ap-dds-boot-race|The ArduPilot client pings the agent in batches of 10 × 1 s and prints "exiting" after each one, but does not give up: an agent that comes up at second 35 connects on the next ping.}}

### What AP_DDS publishes and accepts
The full 4.7.2 list comes from `AP_DDS_Topic_Table.h` and `AP_DDS_Service_Table.h`; the rates come from the delays in `AP_DDS_config.h` (a message is published when more than the delay has passed since the previous one, so 33 ms gives ≈ 30 Hz). The DDS topic name `rt/ap/…` appears in ROS 2 as `/ap/…`; the service request `rq/ap/get_parametersRequest` appears as the service `/ap/get_parameters`.

| Topic/service | Type | Rate, QoS | Purpose |
|---|---|---|---|
| `/ap/pose/filtered` | `geometry_msgs/PoseStamped` | ≈ 30 Hz, BEST_EFFORT | local pose from the EKF relative to home, ENU (the firmware writes `base_link` into `header.frame_id`) |
| `/ap/twist/filtered` | `geometry_msgs/TwistStamped` | ≈ 30 Hz, BEST_EFFORT | velocity |
| `/ap/geopose/filtered`, `/ap/navsat` | `geographic_msgs/GeoPoseStamped`, `sensor_msgs/NavSatFix` | ≈ 30 Hz / per GPS update, BEST_EFFORT | global pose, GNSS (`frame_id` = receiver number) |
| `/ap/gps_global_origin/filtered` | `geographic_msgs/GeoPointStamped` | 1 Hz, BEST_EFFORT | EKF origin |
| `/ap/goal_lla` | `geographic_msgs/GeoPointStamped` | 5 Hz, RELIABLE + TRANSIENT_LOCAL | current navigation target |
| `/ap/battery` | `sensor_msgs/BatteryState` | 1 Hz, BEST_EFFORT | battery |
| `/ap/status` | `ardupilot_msgs/Status` | on change, otherwise 2 Hz; RELIABLE + TRANSIENT_LOCAL | armed, mode, flying, external_control, failsafe |
| `/ap/rc`, `/ap/airspeed` | `ardupilot_msgs/Rc`, `ardupilot_msgs/Airspeed` | 10 Hz / ≈ 30 Hz, BEST_EFFORT | RC input; airspeed |
| `/ap/imu/experimental/data` | `sensor_msgs/Imu` | 200 Hz, BEST_EFFORT | IMU, experimental |
| `/ap/tf_static`, `/ap/clock`, `/ap/time` | tf2, `rosgraph_msgs/Clock`, `builtin_interfaces/Time` | once (RELIABLE + TRANSIENT_LOCAL) / 100 Hz (RELIABLE) | GPS mounts relative to `base_link`, clock for sim time |
| `/ap/cmd_vel` (in) | `geometry_msgs/TwistStamped` | BEST_EFFORT | velocity in GUIDED; frame `map` (ENU) or `base_link` |
| `/ap/cmd_gps_pose` (in) | `ardupilot_msgs/GlobalPosition` | BEST_EFFORT | global target in GUIDED (frame `map`) |
| `/ap/joy`, `/ap/tf` (in) | `sensor_msgs/Joy`, `tf2_msgs/TFMessage` | BEST_EFFORT | joystick; external odometry through TF |
| `/ap/arm_motors`, `/ap/mode_switch`, `/ap/prearm_check`, `/ap/experimental/takeoff` | services | — | arming, mode (Copter mode number: GUIDED = 4, LAND = 9), prearm (`std_srvs/Trigger`), takeoff |
| `/ap/set_parameters`, `/ap/get_parameters` | `rcl_interfaces` services | — | ArduPilot parameters as ROS 2 parameters |

Important: AP_DDS converts ENU ↔ NED itself, and for `cmd_vel` it goes by `header.frame_id` (`map` is world ENU, `base_link` is the body). Position: x_ENU = east = y_NED, y_ENU = north = x_NED, z_ENU = −z_NED; orientation: a permutation of the quaternion components and a 90° rotation about z, so that a heading "north" becomes 90° in ENU. The yaw rate in `cmd_vel` is inverted (ROS: counterclockwise is positive). Any other `frame_id` (for example, `odom`) is silently dropped. So unlike PX4, your ROS node lives in ROS conventions, with one caveat. For `base_link` the 4.7.2 code inverts only z (`{x, y, -z}`), leaves y as it is and rotates the vector with the FRD body matrix (`AP_DDS_ExternalControl.cpp`, the same in master as of November 2026): per REP-103 `linear.y > 0` is to the left, but according to the code the vehicle goes to the right. This conclusion is read from the code and checked numerically in the practice (step 2), but not in flight; before using `base_link` for sideways motion, check the sign in SITL, and the safe route is to send velocities in `map`.

Two more facts from the code. `cmd_vel` and `cmd_gps_pose` setpoints are accepted only if the vehicle is in GUIDED (or in AUTO on a NAV_GUIDED item) and armed (`AP_ExternalControl_Copter::ready_for_external_control`); otherwise they are silently dropped. The `external_control` field in `/ap/status` is always `true` in 4.7.2 ("To be filled after PR#28429" in `AP_DDS_Client.cpp`), so you cannot rely on it. QoS: poses and velocities are BEST_EFFORT; `/ap/status`, `/ap/goal_lla` and `tf_static` are RELIABLE + TRANSIENT_LOCAL (a BEST_EFFORT subscriber is compatible with both; `tf_static` is easier to read with `--qos-durability transient_local`, as in the README).

### The order of operations in ArduPilot
ArduCopter arms only in a mode that allows arming (GUIDED does) and only after the pre-arm checks. Takeoff in GUIDED is a separate command (the takeoff service is the counterpart of `MAV_CMD_NAV_TAKEOFF` and calls `AP_Vehicle::start_takeoff`); without it a vehicle on the ground ignores horizontal setpoints. The sequence in the node: GUIDED → arm → takeoff(alt) → velocity/position setpoints → LAND. The timeout for velocity setpoints in GUIDED is `GUID_TIMEOUT` (seconds, 3 s by default, `ArduCopter/Parameters.cpp` 4.7.2): if `cmd_vel` stops arriving, the vehicle stops. `cmd_vel` goes into the same VelAccel submode (`set_vel_NED_ms` → `set_vel_accel_NED_m`) as `SET_POSITION_TARGET_LOCAL_NED` with a velocity mask, so the measurement from the ap-companion module carries over one to one: the speed starts dropping 3.2–3.3 s after the last setpoint, and the vehicle is stopped (< 0.2 m/s) after 4.3 s. It is the same "proof of life" principle as Offboard in PX4.

{{diagram:ap-dds-guided-seq|Order matters: GUIDED, arm, a separate takeoff, and only then a cmd_vel stream in the map frame; go quiet and after GUID_TIMEOUT the vehicle stops.}}

### MAVROS
MAVROS is a node that holds the MAVLink connection and dispatches it to plugins: `/mavros/state` (connection, armed, mode), `/mavros/local_position/pose`, `/mavros/setpoint_position/local`, `/mavros/setpoint_velocity/cmd_vel`, the services `/mavros/cmd/arming`, `/mavros/set_mode`, `/mavros/cmd/takeoff`, `/mavros/mission/push`, parameters, geofences, and full access to any MAVLink message through `mavros_msgs/Mavlink`. It also converts ENU ↔ NED. Launch: `ros2 launch mavros apm.launch fcu_url:=udp://:14550@` (a connection to SITL or to a router on the companion computer).

When MAVROS is better than AP_DDS: you need functionality that AP_DDS does not have (missions, parameters, camera, arbitrary MAVLink messages); the fleet is mixed (one codebase for ArduPilot and PX4 over MAVLink); the firmware has no DDS. When AP_DDS is better: fewer layers and less latency, standard ROS types, no MAVLink traffic on the companion computer for the ROS part.

### Comparing the routes
| | PX4 uXRCE-DDS | ArduPilot AP_DDS | MAVROS |
|---|---|---|---|
| What goes over the wire | uORB structures over XRCE | DDS client, standard ROS types | MAVLink |
| Frames on the ROS side | NED/FRD (you convert) | ENU/FLU (the firmware converts) | ENU/FLU (MAVROS converts) |
| Version compatibility | px4_msgs = PX4 version, _vN suffixes | ardupilot_msgs from the same branch | MAVLink dialect, stable |
| Feature coverage | everything in dds_topics.yaml | the /ap/* set, growing | almost all of MAVLink |
| External control | Offboard, stream > 2 Hz | GUIDED, `GUID_TIMEOUT` | GUIDED/Offboard through setpoint_* |

### One state machine, two wrappers
`ap_dds_square.py` uses the same `OffboardFSM` as the PX4 node. The differences are only in the wrapper: observations come from `/ap/status` and `/ap/pose/filtered` (ENU → NED for the state machine), the "external control mode" is GUIDED, the arm request becomes "GUIDED first, then arm", the climb to altitude after arming is the takeoff service (in the TAKEOFF state), and the state machine's position setpoints become velocities (a P controller limited to 3 m/s) on `/ap/cmd_vel` in the `map` frame. The safeguard logic and all the state machine tests stay valid.

### Place in the system

- **Receives:** a firmware build with `--enable-DDS` and a free FC UART or Ethernet (`ap-companion`); pose and velocity from the EKF as `/ap/pose/filtered` and `/ap/twist/filtered` (`ap-ekf`); the GUIDED rules and `GUID_TIMEOUT` (`ap-companion`); the `OffboardFSM` state machine (`ros2-px4`); for MAVROS, a MAVLink stream (`mav-sdk`).
- **Provides:** `/ap/cmd_vel` to GUIDED mode; `/ap/*` topics in ENU and standard ROS types to planning (`ros2-nav`) and the application nodes (`ros2-app-arch`).
- **If you get it wrong here:** `cmd_vel` carries `frame_id` `base_link` instead of `map` → the velocity is interpreted in body axes → the plan from `ros2-nav` takes the vehicle the wrong way (and in 4.7.2 sideways commands in `base_link` also have the opposite sign). The agent on the companion computer starts later than the FC → the GCS shows "DDS: No ping response, exiting", which is easy to mistake for a failure, although the client will connect by itself. Setpoints start before the takeoff command → the vehicle on the ground ignores them, and the state machine waits for altitude until it times out; the GUIDED order of operations is in `ap-companion`.

## practice
Steps 1–3 were run in the author's environment (ArduPilot 4.7.2, Python 3); steps 4–7 need ROS 2 Humble and a SITL build with `--enable-DDS`, which that environment did not have, so their commands are taken from the ArduPilot dev wiki and `libraries/AP_DDS/README.md` 4.7.2 and marked as not run. The self-check criteria below are split the same way.

### Step 1. Does your build have AP_DDS
Before looking for a bug in ROS, make sure the client is compiled in at all. Two ways: the `DDS_ENABLE` parameter (in the ground station, or with the audit script from the ap-companion module) and the DDS topic strings in the SITL binary:

```bash
strings build/sitl/bin/arducopter | grep -c "rt/ap/"      # stock 4.7.2 SITL build (./waf copter)
# 0
# param audit of the same SITL (companion_lab.py from ap-companion):
# DDS_ENABLE        = None
```

Zero strings and a missing parameter mean a build without `--enable-DDS`. In a DDS build `strings` finds the names from `AP_DDS_Topic_Table.h` (`rt/ap/pose/filtered` and others), and `DDS_ENABLE` equals 1 without any setup.

### Step 2. Frame conversions, by the numbers
The script reproduces the AP_DDS 4.7.2 formulas (`AP_DDS_Client.cpp` for `/ap/pose/filtered`, `AP_DDS_ExternalControl.cpp` for `/ap/cmd_vel`) and runs them on simple cases where the answer is known in advance. For `base_link` it assumes level flight (rotation by heading only), as the code does through `body_to_earth`.

```python
"""Re-implementation of the AP_DDS frame conversions of ArduPilot 4.7.2 (AP_DDS_Client.cpp,
AP_DDS_ExternalControl.cpp) to check by numbers what a ROS 2 node sends and receives."""
import math

def qmul(a, b):
    w1, x1, y1, z1 = a; w2, x2, y2, z2 = b
    return (w1*w2 - x1*x2 - y1*y2 - z1*z2, w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2, w1*z2 + x1*y2 - y1*x2 + z1*w2)

def yaw_q(yaw):                                   # rotation about z (NED: about Down)
    return (math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2))

def q_yaw_deg(q):
    w, x, y, z = q
    return math.degrees(math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)))

# /ap/pose/filtered: position NED -> ENU, orientation NED -> ENU with a 90 deg z rotation
def pose_out(pos_ned, q_ned):
    pos_enu = (pos_ned[1], pos_ned[0], -pos_ned[2])
    aux = (q_ned[0], q_ned[2], q_ned[1], -q_ned[3])
    return pos_enu, qmul(aux, (math.sqrt(2) * 0.5, 0, 0, math.sqrt(2) * 0.5))

# /ap/cmd_vel in: frame "map" (ENU) or "base_link"
def cmd_vel_in(frame, lin, yaw_rate_ros, heading_ned):
    if frame == "map":
        v_ned = (lin[1], lin[0], -lin[2])
    elif frame == "base_link":
        body = (lin[0], lin[1], -lin[2])          # as in 4.7.2: only z is negated
        c, s = math.cos(heading_ned), math.sin(heading_ned)
        v_ned = (c * body[0] - s * body[1], s * body[0] + c * body[1], body[2])   # body_to_earth, level flight
    else:
        return None                                # any other frame_id is ignored (returns false)
    return v_ned, -yaw_rate_ros

print("pose: vehicle 10 m north, 5 m east, 20 m up, heading north (NED yaw 0)")
p, q = pose_out((10, 5, -20), yaw_q(0))
print(f"  /ap/pose/filtered position ENU = {p}, ENU yaw = {q_yaw_deg(q):.1f} deg")
p, q = pose_out((0, 0, -20), yaw_q(math.radians(90)))
print(f"  heading east (NED yaw 90): ENU yaw = {q_yaw_deg(q):.1f} deg")

print("cmd_vel frame 'map': linear (x=1 east, y=2 north, z=0.5 up), angular.z = 0.3 rad/s (CCW)")
v, r = cmd_vel_in("map", (1, 2, 0.5), 0.3, 0)
print(f"  -> NED velocity {v} (north, east, down), yaw rate {r} rad/s (NED, CW positive)")

for hdg in (0, 90):
    print(f"cmd_vel frame 'base_link', heading {hdg} deg: linear.y = +1 (REP-103: to the LEFT)")
    v, _ = cmd_vel_in("base_link", (0, 1, 0), 0, math.radians(hdg))
    print(f"  -> NED velocity ({v[0]:.2f}, {v[1]:.2f}, {v[2]:.2f})")
print("cmd_vel frame 'odom' ->", cmd_vel_in("odom", (1, 0, 0), 0, 0))
```

```text
pose: vehicle 10 m north, 5 m east, 20 m up, heading north (NED yaw 0)
  /ap/pose/filtered position ENU = (5, 10, 20), ENU yaw = 90.0 deg
  heading east (NED yaw 90): ENU yaw = 0.0 deg
cmd_vel frame 'map': linear (x=1 east, y=2 north, z=0.5 up), angular.z = 0.3 rad/s (CCW)
  -> NED velocity (2, 1, -0.5) (north, east, down), yaw rate -0.3 rad/s (NED, CW positive)
cmd_vel frame 'base_link', heading 0 deg: linear.y = +1 (REP-103: to the LEFT)
  -> NED velocity (0.00, 1.00, 0.00)
cmd_vel frame 'base_link', heading 90 deg: linear.y = +1 (REP-103: to the LEFT)
  -> NED velocity (-1.00, 0.00, 0.00)
cmd_vel frame 'odom' -> None
```

Reading it. Pose: 10 m north and 5 m east in NED became (5, 10, 20) in ENU, with x east, y north, z up; a heading "north" is 90° in ENU and "east" is 0°, as REP-103 requires. `cmd_vel` in `map`: (1 east, 2 north, 0.5 up) → NED (2, 1, −0.5), and a yaw rate of 0.3 rad/s counterclockwise → −0.3 in NED. `base_link`, `linear.y = +1`: at heading 0° the vehicle gets a velocity to the east (to the right), at heading 90° to the south (also to the right), although per REP-103 +y is to the left. That is the caveat from the theory. `frame_id = odom` → None: the setpoint is dropped.

### Step 3. The boot race, by calculation
Given: the FC initializes DDS at second 2, `DDS_TIMEOUT_MS = 1000`, `DDS_MAX_RETRY = 10`, the agent on the companion computer is ready at second 35. A batch is 10 × 1 s = 10 s, so the "exiting" messages come at 12, 22 and 32 s, that is ⌊(35 − 2) / 10⌋ = 3 of them; the session is created on the first ping after 35 s. With `DDS_MAX_RETRY = 40` a batch lasts 40 s: an agent that comes up at second 35 connects within the first batch, and there is no "exiting" at all (it would appear at second 42 only if the agent were still missing by then). If the agent drops out in flight, the client notices after 3 missed pings at 500 ms, within 1.5–2 s depending on the phase (the ping reply is checked on the next cycle).

### Step 4. SITL with DDS and the agent (not run here)
Natively, per the ArduPilot dev wiki ("Install ROS 2", "ROS 2 with SITL"; ROS 2 Humble on Ubuntu 22.04), for ArduPilot 4.7.x:

```bash
mkdir -p ~/ardu_ws/src && cd ~/ardu_ws
vcs import --recursive --input https://raw.githubusercontent.com/ArduPilot/ardupilot/master/Tools/ros2/ros2.repos src
(cd src/ardupilot && git checkout Copter-4.7.2 && git submodule update --init --recursive)   # match firmware and ardupilot_msgs
sudo apt update && rosdep update && source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -r -y
sudo apt install default-jre
git clone --recurse-submodules --branch v4.7.0 https://github.com/ardupilot/Micro-XRCE-DDS-Gen.git
(cd Micro-XRCE-DDS-Gen && ./gradlew assemble) && export PATH=$PATH:$PWD/Micro-XRCE-DDS-Gen/scripts
colcon build --packages-up-to ardupilot_sitl && source install/setup.bash
ros2 launch ardupilot_sitl sitl_dds_udp.launch.py transport:=udp4 synthetic_clock:=True wipe:=False model:=quad \
  speedup:=1 slave:=0 instance:=0 \
  defaults:=$(ros2 pkg prefix ardupilot_sitl)/share/ardupilot_sitl/config/default_params/copter.parm,$(ros2 pkg prefix ardupilot_sitl)/share/ardupilot_sitl/config/default_params/dds_udp.parm \
  sim_address:=127.0.0.1 master:=tcp:127.0.0.1:5760 sitl:=127.0.0.1:5501
# second terminal
source ~/ardu_ws/install/setup.bash
ros2 node list                      # /ap
ros2 topic list | grep /ap/
ros2 topic echo /ap/status --once
ros2 service call /ap/mode_switch ardupilot_msgs/srv/ModeSwitch "{mode: 4}"
ros2 service call /ap/arm_motors ardupilot_msgs/srv/ArmMotors "{arm: True}"
ros2 service call /ap/experimental/takeoff ardupilot_msgs/srv/Takeoff "{alt: 10.5}"
```

The course's Docker variant is `examples/ros2-docker` (`docker compose --profile ardupilot up --build`). By hand without the launch file: the agent `ros2 run micro_ros_agent micro_ros_agent udp4 -p 2019`, SITL `sim_vehicle.py -v ArduCopter --enable-DDS` with `DDS_ENABLE 1`. Expected (per the 4.7.2 README): the node `/ap`, the services `/ap/arm_motors`, `/ap/mode_switch`, `/ap/prearm_check`, `/ap/experimental/takeoff`; in MAVProxy, `DDS: Initialization passed`. Abort criterion: if `/ap` is not in `ros2 node list` within 60 s of the agent starting, compare `DDS_DOMAIN_ID` with `ROS_DOMAIN_ID` and the agent port with `DDS_UDP_PORT`, rather than rebuilding.

### Step 5. A square through AP_DDS (not run here)
`ros2 launch uav_ros2_labs ap_square.launch.py`. Compare the state machine transitions in the log with the modes in Mission Planner/QGC. Plot the trajectory from `/tmp/ap_flight.csv`. Stop the node in the middle of the square and measure in the ArduPilot log how long it takes the vehicle to stop; compare that with `GUID_TIMEOUT`.

### Step 6. The same square through MAVROS (not run here)
Write a wrapper `mavros_square.py` (the same state machine): `/mavros/state` → armed/mode, `/mavros/local_position/pose` → position, `/mavros/setpoint_position/local` → setpoints, the services `cmd/arming`, `set_mode` (custom_mode "GUIDED"), `cmd/takeoff`. Confirm that you did not have to touch the state machine tests.

### Step 7. Comparison (not run here)
Measure the "setpoint → velocity change in the pose" latency for AP_DDS and MAVROS (from the timestamps in a bag) and the CPU load of the agent and of MAVROS, and fill in the table from the theory with your own numbers.


### What you should get and what to record
- **Square through AP_DDS.** The state machine transitions in the node log match the modes in the ground station (GUIDED for the whole square), and the trajectory from the CSV is a square with corners within a couple of meters of the target points. Save the plot.
- **GUID_TIMEOUT.** After you stop the node in the middle of the square, the vehicle stops and hovers after `GUID_TIMEOUT` (3 s by default). The time from the last setpoint to the stop in the ArduPilot log should match the parameter ± the setpoint publishing period.
- **MAVROS.** The same state machine passes the same tests through the wrapper. If the behavior differs, look for the difference in the frames and units of the topics, not in the state machine.
- **Comparison table:** the "setpoint → start of velocity change" latency (median and maximum over 20+ setpoints) and the CPU load of the AP_DDS agent and of MAVROS. Record your own numbers: they depend on the machine and the build, and other people's numbers will not help you.

### Moving to real hardware
Per the AP_DDS 4.7.2 README (the Pixhawk 6X section), DDS over a UART: firmware built with `./waf configure --board <board> --enable-DDS`, the parameters `DDS_ENABLE 1`, `SERIALn_PROTOCOL 45`, `SERIALn_BAUD 115` on a free port, a reboot; on the companion computer, `ros2 run micro_ros_agent micro_ros_agent serial -b 115200 -D /dev/serial/by-id/<port>`. The order: (1) bench, props off: the GCS shows `DDS: Initialization passed`, `ros2 topic hz /ap/pose/filtered` ≈ 30 Hz; abort criterion: "No ping response" for longer than two minutes after the agent starts, so check TX/RX, the baud rate on both sides and that the port is not taken by MAVLink; (2) bench: the `mode_switch` (4) and `arm_motors` services return success, and `cmd_vel` is ignored while disarmed; (3) field, a pilot with a transmitter and a LOITER/RTL switch, a geofence: take off with the service to 5 m, `cmd_vel` 1 m/s in `map` to the north for 3 s, then silence; acceptance: the vehicle moves north and stops after `GUID_TIMEOUT` ± 0.5 s; abort criterion: any motion in the wrong direction, and the pilot takes over.

Self-check: the lab is done when **(doable without ROS)** in step 1 you have determined whether your build has AP_DDS (`strings … | grep -c "rt/ap/"` > 0 and `DDS_ENABLE` = 1: it does; 0 and "no such parameter": it does not); the step 2 script gives exactly: ENU pose (5, 10, 20), headings 90.0° and 0.0°, NED velocity (2, 1, −0.5) with a yaw rate of −0.3, for `base_link` at headings 0° and 90°, (0, 1, 0) and (−1, 0, 0), and None for `odom`; the step 3 calculation gives 3 "exiting" messages and 1.5–2 s to detect that the agent is gone. **(With ROS 2 Humble and a DDS build)** the square has been flown through AP_DDS: the trajectory from `/tmp/ap_flight.csv` is a square with corners within a couple of meters of the target points, and the state machine transitions match the modes in the ground station; the time from the last setpoint to the start of braking in the ArduPilot log is `GUID_TIMEOUT` (3 s) ± 0.5 s, as in the ap-companion measurement (3.2–3.3 s); the MAVROS wrapper passes the same state machine tests without changing them; the comparison table is filled with the median and maximum latency over 20+ setpoints and the CPU load for AP_DDS and MAVROS. On hardware, the three criteria from the previous subsection.

**Reference for the self-check.** The correct result: one state machine and one set of tests, two wrappers, and the only differences are in the frames and units of the topics; the step 2 script prints exactly the output above. Typical wrong results: (1) the vehicle flies "east instead of north": a setpoint in ENU was sent as NED (or the other way round), or the wrong `frame_id`; (2) a sideways command in `base_link` goes right instead of left: that is how the 4.7.2 code behaves (y is not inverted), not a bug in the node; switch to `map`; (3) `cmd_vel` setpoints are ignored on the ground: takeoff in GUIDED was not done, or the vehicle is not armed; (4) the GCS shows three "DDS: No ping response, exiting" messages and you decided that DDS is broken: that is the boot race, and the client will connect by itself; (5) for MAVROS you had to change the state machine tests: logic has leaked from the state machine into the wrapper.

## diagnostics
- **Symptom:** there are no `/ap/*` topics
  - Possible cause: SITL built without `--enable-DDS`, `DDS_ENABLE = 0`, the agent on a different port or in a different domain.
  - What to do: a DDS build; port 2019; the same `ROS_DOMAIN_ID`/`DDS_DOMAIN_ID`.
- **Symptom:** `arm_motors` returns false
  - Possible cause: the mode does not allow arming, or the pre-arm checks have not passed.
  - What to do: GUIDED first; `/ap/prearm_check`; STATUSTEXT in the GCS.
- **Symptom:** `cmd_vel` setpoints are ignored on the ground
  - Possible cause: takeoff in GUIDED was not done.
  - What to do: call the takeoff service, wait for the altitude, then send velocities.
- **Symptom:** the GCS keeps showing "DDS: No ping response, exiting", and there are no topics
  - Possible cause: the agent has not started yet (the companion computer boots more slowly than the FC), the wrong address/port (`DDS_IP0..3`, `DDS_UDP_PORT`), or a DDS UART at a different baud rate.
  - What to do: wait for the agent to start, since the client keeps trying every `DDS_TIMEOUT_MS × DDS_MAX_RETRY` (10 s); check the address, port and baud rate; do not rebuild the firmware.
  - What the log shows: a message every 10 s with the defaults, then `DDS: Initialization passed`.
- **Symptom:** `DDS_ENABLE` is not in the parameter list
  - Possible cause: the firmware or SITL was built without `--enable-DDS`.
  - What to do: build with `--enable-DDS` and `microxrceddsgen` on the PATH (Gen v4.7.0 for 4.7); check with `strings … | grep rt/ap/`.
- **Symptom:** a sideways setpoint in `base_link` goes the opposite way
  - Possible cause: in 4.7.2, for `base_link` only z is inverted, and y is treated as "to the right" (read from the code of `AP_DDS_ExternalControl.cpp`).
  - What to do: send velocities in `map` (ENU) and rotate the vector in the node; for `base_link`, check the sign in SITL.
- **Symptom:** the node relies on `/ap/status.external_control`, and it is always true
  - Possible cause: in 4.7.2 the field is not filled in (the code says "To be filled after PR#28429").
  - What to do: judge external control by `mode` (GUIDED = 4) and `armed`.
- **Symptom:** the vehicle flies "east instead of north"
  - Possible cause: a setpoint in ENU was sent as NED (or the other way round), the wrong frame_id.
  - What to do: frame_id `map` for world ENU; convert only at the boundary.

## references
- ArduPilot — AP_DDS README (setup, topics, services) | https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_DDS/README.md | primary | A
- ArduPilot — ROS 2 with ArduPilot (dev docs) | https://ardupilot.org/dev/docs/ros2.html | primary | A
- ArduPilot — AP_DDS topic and service tables (source) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/AP_DDS | primary | A
- ArduPilot Copter-4.7.2 — AP_DDS_Client.cpp (DDS_* params, main_loop, QoS use) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_DDS/AP_DDS_Client.cpp | primary | A
- ArduPilot Copter-4.7.2 — AP_DDS_ExternalControl.cpp (cmd_vel frames) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_DDS/AP_DDS_ExternalControl.cpp | primary | A
- ArduPilot Copter-4.7.2 — AP_DDS_Topic_Table.h / AP_DDS_config.h | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_DDS/AP_DDS_Topic_Table.h | primary | A
- ArduPilot dev wiki — Install ROS 2 (Humble only, Micro-XRCE-DDS-Gen v4.7.0) | https://ardupilot.org/dev/docs/ros2.html | primary | A
- ArduPilot dev wiki — ROS 2 with SITL (sitl_dds_udp.launch.py) | https://ardupilot.org/dev/docs/ros2-sitl.html | primary | A
- MAVROS | https://github.com/mavlink/mavros | primary | A
- ArduPilot — Copter commands in Guided mode | https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html | primary | A

## checklist
- I connect ArduPilot to ROS 2 through AP_DDS (parameters, agent, SITL build)
- I know the /ap/* topics and services and which frames they use
- I keep the order GUIDED → arm → takeoff → setpoints → LAND and know GUID_TIMEOUT
- I use MAVROS where AP_DDS falls short
- I compare the PX4/AP_DDS/MAVROS routes by facts and measurements
- I check that AP_DDS is compiled in before looking for bugs in ROS
- I understand the client's connection loop and do not mistake the boot race for a failure
- I send `cmd_vel` in `map`; `base_link` for sideways motion only after checking the sign
- I reuse one state machine for different autopilots
