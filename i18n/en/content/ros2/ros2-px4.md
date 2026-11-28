---
id: ros2-px4
title: "ROS 2 + PX4: uXRCE-DDS, an offboard node as a state machine"
level: L3
readingTime: 50 min
firmware: PX4 1.18 (checked against v1.18.0; 1.16–1.17 suffixes noted) · ROS 2 Jazzy / Humble
status: published
added: 2026-11-08
tags:
  - ROS 2
  - PX4
  - uXRCE-DDS
  - Offboard
  - state machine
related:
  - ros2-basics
  - px4-ros2
  - mav-sdk
next:
  - ros2-ardupilot
source: content/ros2/ros2-px4.md
source_hash: 872b39963888
---

## summary
The px4-ros2 module showed that PX4 "speaks" ROS 2 through the uXRCE-DDS bridge and that offboard flight comes down to three messages. This module shows how to turn that into a node you can trust with the vehicle: `px4_msgs` message versions and the `_v<N>` suffixes, time synchronization, the Offboard rules (a "proof of life" stream > 2 Hz, setpoints before the mode switch), and above all the flight logic as a **state machine** with no ROS inside, tested with plain pytest. The node becomes a thin wrapper: collect observations → step the state machine → execute the action. Lab: a square in Gazebo with safeguards (lost position, stale status, pilot takeover), a test of the state machine against a toy vehicle model, and a flight replayed from a bag.

## theory
### The uXRCE-DDS bridge
PX4 runs the **client** `uxrce_dds_client`: it publishes selected uORB topics and subscribes to incoming ones according to `dds_topics.yaml` (in the PX4 source). Outside runs the **agent** `MicroXRCEAgent`, which presents these topics on the DDS network as ordinary ROS 2 topics `/fmu/out/*` (from PX4) and `/fmu/in/*` (into PX4). The transport is UDP (SITL: the agent on port 8888, the client starts automatically) or a serial port (`UXRCE_DDS_CFG` selects the port on a real flight controller). Unlike MAVLink, there are no "protocol messages" here: these are PX4's uORB structures as they are, hence the requirement: **`px4_msgs` on the ROS side must match the PX4 version**.

{{diagram:uxrce-scheme|PX4 and ArduPilot connect to ROS 2 with the same scheme: a client in the firmware, an agent on the companion computer.}}

### Message versions
Since PX4 v1.16 some messages have a version (`MESSAGE_VERSION` in the definition), and their topics are published with a suffix: `/fmu/out/vehicle_status_v1` (in 1.18 already `_v4`). For compatibility of old nodes with new firmware and vice versa there is a translator node (the PX4 ROS 2 Message Translation Node). The practice for your own nodes: derive the topic name from the message class's `MESSAGE_VERSION` instead of typing it by hand, as `px4_offboard_square.py` does:

```python
def topic(base, msg_cls):
    v = getattr(msg_cls, "MESSAGE_VERSION", 0)
    return base if v == 0 else f"{base}_v{v}"
```

### Offboard rules
1. The external controller must continuously send `OffboardControlMode` (which setpoints are active: position, velocity, acceleration, attitude, body_rate…) at a rate well **above 2 Hz** (the documentation says 2 Hz; in the code PX4 declares the signal lost when the timestamp of the last message is older than `COM_OF_LOSS_T`, see `px4-ros2`). This is the "proof of life". The actual setpoints go in `TrajectorySetpoint` (position/velocity/acceleration/yaw, unused fields = NaN).
2. The stream must be running **before** the switch to Offboard (and before arming in Offboard), or PX4 will refuse.
3. If the stream stops for longer than `COM_OF_LOSS_T`, PX4 leaves Offboard and switches to the mode set by `COM_OBL_RC_ACT` (Position, Altitude, Stabilized, Return, Land, Hold, Terminate, Disarm; value 2 was called Manual before 1.16). Since 1.17, if Position, Altitude or Stabilized is selected and there is no manual control, `NAV_RCL_ACT` is executed (in 1.18 with `NAV_RCL_ACT` = 7 that is Hold).
4. Commands are `VehicleCommand` on `/fmu/in/vehicle_command`: arm with `VEHICLE_CMD_COMPONENT_ARM_DISARM` (param1 = 1), mode with `VEHICLE_CMD_DO_SET_MODE` (param1 = 1 for custom, param2 = 6 for Offboard), land with `VEHICLE_CMD_NAV_LAND`. The acknowledgment arrives on `/fmu/out/vehicle_command_ack` (in 1.18 the message has version 1, so the topic is `/fmu/out/vehicle_command_ack_v1`); the state is in `VehicleStatus.arming_state` and `nav_state`.
5. Coordinates in `TrajectorySetpoint` are **local NED**, with the origin at the EKF initialization point; altitude is negative.

### Flight logic as a state machine
A typical mistake is putting the logic in callbacks: "status arrived → if armed → send mode". Such code cannot be tested or reproduced and behaves unpredictably under message loss. The right way: a pure class `OffboardFSM` (`examples/ros2-docker/.../offboard_fsm.py`) with a single method `step(obs) → action`, no ROS and no time "out of thin air":

- **Observations** `Obs`: time, age of the last status, position validity, armed, mode, NED position, whether landed.
- **Action** `Action`: a setpoint, arm/mode/land requests, a note.
- **States**: WAIT_READY → STREAM_SETPOINTS (≥ 1 s of setpoints before the mode request) → ARMING → OFFBOARD → TAKEOFF → SQUARE → LAND → DONE.
- **Safeguards checked in every active state**: status stale (> 1 s) → ABORT; position invalid → ABORT; step timeout → ABORT; the pilot switched the mode → DONE with no commands (do not "fight" the human).

The ROS node only does I/O: it builds `Obs` from the latest messages on a 20 Hz timer, calls `step`, publishes the setpoints and (rate-limited) the commands. The same state machine is used for ArduPilot (module ros2-ardupilot); only the wrapper changes.

{{diagram:offboard-fsm|The offboard node state machine: a linear scenario plus safeguards that lead to landing or hand control back to the pilot.}}

### Testing without a simulator
`test_offboard_fsm.py` runs the state machine against a toy vehicle model (it arms on request, enters Offboard only if setpoints have been streaming for ≥ 0.5 s, flies toward the setpoint at 2 m/s, lands): it checks the full scenario, the "setpoints before the mode" order, and the reaction to lost position, stale status and pilot takeover. That is five tests in 50 ms; you can run them on every commit (in this course, in CI), and only then go to Gazebo.

### Gazebo and SITL
`make px4_sitl gz_x500` is the x500 quadcopter in Gazebo Harmonic; the PX4 documentation (main) recommends ROS 2 Jazzy on Ubuntu 24.04; on Ubuntu 22.04, Humble (the release documentation for v1.16–v1.18 recommends exactly Humble on Ubuntu 22.04). The agent: `MicroXRCEAgent udp4 -p 8888`. For repeatable tests use headless mode (`HEADLESS=1`) and a fixed world. QGroundControl connects over UDP 14550 in parallel; it is handy for watching modes and interrupting the flight.

### Place in the system

- **Receives:** the `/fmu/out/*` topics and the Offboard rules (`px4-ros2`); QoS and time (`ros2-basics`); `px4_msgs` of the same version as the firmware (`px4-intro`); a world for flying the square (`tools-gazebo`).
- **Provides:** the `OffboardControlMode` and `TrajectorySetpoint` stream to the PX4 position controller (`px4-control`); the `OffboardFSM` state machine to the ArduPilot wrapper (`ros2-ardupilot`); the "decision" role to the application architecture (`ros2-app-arch`).
- **If you get it wrong here:** the topic name is typed by hand and the firmware is updated → `vehicle_status` is published with a version suffix (`_v1` in 1.16–1.17, `_v4` in 1.18) → the status is "stale" → the state machine goes to ABORT on the ground (`px4-intro`). The stream stops for longer than `COM_OF_LOSS_T` → PX4 executes `COM_OBL_RC_ACT`, and since 1.17 without manual control, `NAV_RCL_ACT` (`px4-setup-scratch`).

## practice
### Step 1. State machine test
```bash
cd examples/ros2-docker/ws/src/uav_ros2_labs
python -m pytest -q test/test_offboard_fsm.py
```
Add your own test: battery (a new field `battery_low` in `Obs`) → ABORT. Test first, then code.

### Step 2. Square in Gazebo
```bash
docker compose --profile px4 up        # or natively: MicroXRCEAgent + make px4_sitl gz_x500
ros2 launch uav_ros2_labs px4_square.launch.py
```
The node log shows the state transitions; QGC shows the mode changes; `/tmp/px4_flight.csv` holds the trajectory. Plot it: a 10 × 10 m square at 5 m.

### Step 3. Safeguards in the simulator
During SQUARE: (a) switch the mode to Hold in QGC: the node should go to DONE and stop sending commands; (b) stop the node (Ctrl+C): PX4 should leave Offboard after `COM_OF_LOSS_T` and execute the configured action (write down which); (c) stop the agent: the node will see a stale status and go to ABORT, but its commands will no longer get through. What will PX4 do?

### Step 4. Replay from a bag
Record a bag of a flight (`/fmu/out/vehicle_status_v1` (in 1.18, `vehicle_status_v4`), `/fmu/out/vehicle_local_position_v1` (in PX4 v1.16 without the suffix; take the name from `MESSAGE_VERSION`) and your `/fmu/in/*`), then replay only `/fmu/out/*` and run the node: it should go through the same transitions (its commands go "nowhere"). This is how you debug logic on the bench.

Self-check: the lab is done when your state machine test passes (`battery_low` → ABORT, the test written before the code), the trajectory from `/tmp/px4_flight.csv` is a 10 × 10 m square at 5 m altitude, for the three safeguard scenarios you have written down what you observed and it matches the reference below, and when `/fmu/out/*` is replayed from the bag the node goes through the same state transitions as in flight.

**Reference for the self-check.** (a) Hold from QGC: the node goes to DONE and sends no more commands. (b) Ctrl+C: PX4 leaves Offboard after `COM_OF_LOSS_T` and executes the action from `COM_OBL_RC_ACT`. (c) Agent stopped: the node sees a stale status (> 1 s) and goes to ABORT, and PX4 stops receiving the stream and does the same as in (b). Typical wrong results: after a pilot takeover the vehicle "jerks" back into Offboard, because the node keeps sending the mode request; the vehicle moves in altitude "the wrong way", because the altitude was given as positive, while in NED z = −altitude.

## diagnostics
- **Symptom:** PX4 refuses to switch to Offboard
  - Possible cause: OffboardControlMode was not streaming before the mode request, or it streams slower than 2 Hz; no valid local position.
  - What to do: STREAM_SETPOINTS ≥ 1 s; a 10–20 Hz timer; check xy_valid/z_valid.
- **Symptom:** the node does not see `/fmu/out/vehicle_status`
  - Possible cause: the version suffix (`_v4` for vehicle_status in 1.18, `_v1` in 1.16–1.17) or RELIABLE QoS.
  - What to do: the name from MESSAGE_VERSION; a BEST_EFFORT profile.
- **Symptom:** the vehicle goes up and down "the wrong way"
  - Possible cause: altitude given as positive in NED.
  - What to do: z = −altitude; a conversion test.
- **Symptom:** after the pilot switches to Position, the vehicle "jerks" back into Offboard
  - Possible cause: the node keeps sending the mode request.
  - What to do: detect the takeover and stop sending commands (DONE state).

## references
- PX4 — ROS 2 user guide | https://docs.px4.io/v1.18/en/ros2/user_guide.html | primary | A
- PX4 — uXRCE-DDS middleware | https://docs.px4.io/v1.18/en/middleware/uxrce_dds.html | primary | A
- PX4 — Offboard mode (2 Hz proof of life, COM_OF_LOSS_T) | https://docs.px4.io/v1.18/en/flight_modes/offboard.html | primary | A
- PX4 — ROS 2 message translation node (versioned topics) | https://docs.px4.io/v1.18/en/ros2/px4_ros2_msg_translation_node.html | primary | A
- PX4 — px4_msgs | https://github.com/PX4/px4_msgs | primary | A

## checklist
- I can explain the roles of the uXRCE-DDS client and agent and why px4_msgs must match the firmware
- I build topic names with message versions in mind
- I follow the Offboard rules: a stream > 2 Hz, setpoints before the mode, NED
- I keep the flight logic in a pure state machine and test it without ROS
- I check the safeguards in SITL: pilot takeover, node death, agent loss
- I debug the node by replaying a bag
