---
id: ros2-ardupilot
title: "ROS 2 + ArduPilot: AP_DDS and MAVROS, one node — two routes"
level: L3
readingTime: 45 min
firmware: ArduPilot
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
source_hash: 284f391657ba
---

## summary
ArduPilot has two routes into ROS 2. **AP_DDS** is a DDS client built into the firmware (the same principle as uXRCE-DDS in PX4): `/ap/*` topics in ENU and standard ROS types, services for arming and mode changes, velocity control via `/ap/cmd_vel`. **MAVROS** is a MAVLink ↔ ROS bridge that works with any firmware and with the full set of MAVLink features, at the cost of an extra layer. This module takes both apart from the source code and documentation, compares them with the PX4 route and shows how the same state machine from the ros2-px4 module flies a square on ArduPilot via AP_DDS. Lab: a square in SITL via AP_DDS, then via MAVROS, and a comparison table of latency and convenience.

## theory
### AP_DDS: how to connect it
In the firmware there is a DDS client (`libraries/AP_DDS`); outside, there is a micro-ROS agent (`micro_ros_agent`) that exposes the data on the ROS 2 DDS network.

- Parameters: `DDS_ENABLE = 1`; UDP transport — `DDS_UDP_PORT` (default 2019) and the agent address `DDS_IP0..3`; serial transport — `SERIALn_PROTOCOL = 45` on the port you need. `DDS_DOMAIN_ID` is the ROS 2 domain.
- SITL: a build with DDS support (`./waf configure --board sitl --enable-DDS`), run `sim_vehicle.py -v ArduCopter --enable-DDS`, agent: `ros2 run micro_ros_agent micro_ros_agent udp4 -p 2019`.
- ArduPilot-specific message types come from the `ardupilot_msgs` package (in the ArduPilot repository, `Tools/ros2/ardupilot_msgs`): `Status`, `GlobalPosition`, the services `ArmMotors`, `ModeSwitch`, `Takeoff`.

{{diagram:uxrce-scheme|The scheme is the same as in PX4: a client in the firmware, an agent on the companion, regular ROS 2 topics outside.}}

### What AP_DDS publishes and accepts
| Topic/service | Type | Purpose |
|---|---|---|
| `/ap/pose/filtered` | `geometry_msgs/PoseStamped` | local pose from the EKF relative to home, ENU (the firmware writes `base_link` into `header.frame_id`) |
| `/ap/twist/filtered` | `geometry_msgs/TwistStamped` | velocity |
| `/ap/geopose/filtered`, `/ap/navsat` | `geographic_msgs/GeoPoseStamped`, `sensor_msgs/NavSatFix` | global pose, GNSS |
| `/ap/battery`, `/ap/status`, `/ap/rc` | `sensor_msgs/BatteryState`, `ardupilot_msgs/Status`, `ardupilot_msgs/Rc` | battery; armed, mode, flying, external_control, failsafe |
| `/ap/tf_static`, `/ap/clock`, `/ap/time` | tf2, time | mounts, clock for sim time |
| `/ap/cmd_vel` (input) | `geometry_msgs/TwistStamped` | velocity in GUIDED; frame `map` (ENU) or `base_link` |
| `/ap/cmd_gps_pose` (input) | `ardupilot_msgs/GlobalPosition` | global target in GUIDED |
| `/ap/arm_motors`, `/ap/mode_switch`, `/ap/prearm_check`, `/ap/experimental/takeoff` | services | arm, mode (Copter mode number: GUIDED = 4, LAND = 9), pre-arm, takeoff |

Important: AP_DDS converts ENU ↔ NED itself — for `cmd_vel` based on `header.frame_id` (`map` — world ENU, `base_link` — body). So unlike with PX4, your ROS node lives entirely within ROS conventions. QoS: poses and velocities are BEST_EFFORT, `/ap/status` and `tf_static` are RELIABLE + TRANSIENT_LOCAL (a BEST_EFFORT subscriber is compatible with both).

### The order of actions in ArduPilot
ArduCopter arms only in a mode that allows arming (GUIDED does) and only after the pre-arm checks. Takeoff in GUIDED is a separate command (the takeoff service = `MAV_CMD_NAV_TAKEOFF`); without it, the vehicle on the ground ignores horizontal setpoints. The sequence in the node: GUIDED → arm → takeoff(alt) → velocity/position setpoints → LAND. The velocity setpoint timeout in GUIDED is `GUID_TIMEOUT` (seconds): if `cmd_vel` stops arriving, the vehicle stops. This is the same “proof of life” principle as Offboard in PX4.

### MAVROS
MAVROS is a node that holds the MAVLink connection and distributes it across plugins: `/mavros/state` (connection, armed, mode), `/mavros/local_position/pose`, `/mavros/setpoint_position/local`, `/mavros/setpoint_velocity/cmd_vel`, the services `/mavros/cmd/arming`, `/mavros/set_mode`, `/mavros/cmd/takeoff`, `/mavros/mission/push`, parameters, geofences, full access to any MAVLink message via `mavros_msgs/Mavlink`. It also converts ENU ↔ NED. Launch: `ros2 launch mavros apm.launch fcu_url:=udp://:14550@` (connecting to SITL or to a router on the companion).

When MAVROS is better than AP_DDS: you need functionality that AP_DDS doesn't have (missions, parameters, camera, arbitrary MAVLink messages); you have a mixed fleet (one codebase for ArduPilot and PX4 via MAVLink); the firmware has no DDS. When AP_DDS is better: fewer layers and lower latency, standard ROS types, no MAVLink traffic on the companion for the ROS part.

### Comparing the routes
| | PX4 uXRCE-DDS | ArduPilot AP_DDS | MAVROS |
|---|---|---|---|
| What's on the wire | uORB structs over XRCE | DDS client, standard ROS types | MAVLink |
| Coordinate frame on the ROS side | NED/FRD (you convert yourself) | ENU/FLU (the firmware converts) | ENU/FLU (MAVROS converts) |
| Version compatibility | px4_msgs = PX4 version, _vN suffixes | ardupilot_msgs from the same branch | MAVLink dialect, stable |
| Feature coverage | everything in dds_topics.yaml | the /ap/* set, growing | almost all of MAVLink |
| External control | Offboard, stream > 2 Hz | GUIDED, `GUID_TIMEOUT` | GUIDED/Offboard via setpoint_* |

### One state machine, two wrappers
`ap_dds_square.py` uses the same `OffboardFSM` as the PX4 node. The only differences are in the wrapper: observations come from `/ap/status` and `/ap/pose/filtered` (ENU → NED for the state machine), the “external control mode” = GUIDED, the arm request becomes “GUIDED first, then arm”, after reaching altitude — the takeoff service, the state machine's position setpoints are turned into velocity (a P controller limited to 3 m/s) on `/ap/cmd_vel` in the `map` frame. The safeguard logic and all the state machine tests remain valid.

## practice
### Step 1. SITL with DDS
```bash
docker compose --profile ardupilot up --build    # or natively: waf configure --enable-DDS, sim_vehicle.py --enable-DDS
docker compose run --rm ros bash
ros2 topic list | grep /ap/
ros2 topic echo /ap/status --once
ros2 service call /ap/mode_switch ardupilot_msgs/srv/ModeSwitch "{mode: 4}"
```

### Step 2. A square via AP_DDS
`ros2 launch uav_ros2_labs ap_square.launch.py`. Compare the state machine transitions in the log with the modes in Mission Planner/QGC. Plot the trajectory from `/tmp/ap_flight.csv`. Stop the node in the middle of the square and measure from the ArduPilot log how long it took the vehicle to stop — compare with `GUID_TIMEOUT`.

### Step 3. The same square via MAVROS
Write a `mavros_square.py` wrapper (the same state machine): `/mavros/state` → armed/mode, `/mavros/local_position/pose` → position, `/mavros/setpoint_position/local` → setpoints, the services `cmd/arming`, `set_mode` (custom_mode "GUIDED"), `cmd/takeoff`. Confirm that you didn't have to touch the state machine tests.

### Step 4. Comparison
Measure the “setpoint → velocity change in the pose” latency for AP_DDS and MAVROS (from the timestamps in the bag), the CPU load of the agent and of MAVROS, and fill in the table from the theory section with your own numbers.


### What you should get and what to record
- **Square via AP_DDS.** In the node log, the state machine transitions match the modes in the GCS (GUIDED for the whole square), and the trajectory from the CSV is a square with corners within a couple of meters of the target points. Save the plot.
- **GUID_TIMEOUT.** After you stop the node in the middle of the square, the vehicle stops and hovers after `GUID_TIMEOUT` (3 s by default). The time from the last setpoint to the stop in the ArduPilot log should match the parameter ± the setpoint publishing period.
- **MAVROS.** The same state machine passes the same tests through the wrapper. If the behavior differs, look for the difference in the coordinate frames and units of the topics, not in the state machine.
- **Comparison table:** the “setpoint → start of velocity change” latency (median and maximum over 20+ setpoints) and the CPU load of the AP_DDS agent and of MAVROS. Record your own numbers: they depend on the machine and the build, someone else's won't help you.

The lab counts as done when the square has been flown via AP_DDS (plot, transitions), `GUID_TIMEOUT` has been checked, and you have a MAVROS wrapper with the same state machine and a comparison table with measurements.

## diagnostics
- **Symptom:** no `/ap/*` topics
  - Possible cause: SITL was built without `--enable-DDS`, `DDS_ENABLE = 0`, the agent is on a different port or in a different domain.
  - What to do: build with DDS; port 2019; the same `ROS_DOMAIN_ID`/`DDS_DOMAIN_ID`.
- **Symptom:** `arm_motors` returns false
  - Possible cause: the mode doesn't allow arming or the pre-arm checks haven't passed.
  - What to do: GUIDED first; `/ap/prearm_check`; STATUSTEXT in the GCS.
- **Symptom:** `cmd_vel` setpoints are ignored on the ground
  - Possible cause: takeoff in GUIDED wasn't performed.
  - What to do: the takeoff service, wait for the altitude, then the velocities.
- **Symptom:** the vehicle flies “east instead of north”
  - Possible cause: an ENU setpoint was sent as NED (or vice versa), wrong frame_id.
  - What to do: frame_id `map` for world ENU; convert only at the boundary.

## references
- ArduPilot — AP_DDS README (setup, topics, services) | https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_DDS/README.md | primary | A
- ArduPilot — ROS 2 with ArduPilot (dev docs) | https://ardupilot.org/dev/docs/ros2.html | primary | A
- ArduPilot — AP_DDS topic and service tables (source) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/AP_DDS | primary | A
- MAVROS | https://github.com/mavlink/mavros | primary | A
- ArduPilot — Copter commands in Guided mode | https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html | primary | A

## checklist
- I connect ArduPilot to ROS 2 via AP_DDS (parameters, agent, SITL build)
- I know the /ap/* topics and services and which frames they use
- I follow the order GUIDED → arm → takeoff → setpoints → LAND and know GUID_TIMEOUT
- I use MAVROS where AP_DDS falls short
- I compare the PX4/AP_DDS/MAVROS routes on facts and measurements
- I reuse a single state machine for different autopilots
