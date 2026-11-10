---
id: ros2-px4
title: "ROS 2 + PX4: uXRCE-DDS, an Offboard Node as a State Machine"
level: L3
readingTime: 50 min
firmware: PX4
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
source_hash: b3f16c84cb6d
---

## summary
The px4-ros2 module showed that PX4 “speaks” ROS 2 through the uXRCE-DDS bridge and that an offboard flight is three messages. Here you learn how to turn that into a node you can trust with a vehicle: `px4_msgs` message versions and the `_v<N>` suffixes, time synchronization, the Offboard rules (a “proof of life” stream > 2 Hz, setpoints before the mode switch), and most importantly, the flight logic as a **state machine** with no ROS inside, testable with plain pytest. The node becomes a thin wrapper: collect observations → step the state machine → execute the action. Lab: a square in Gazebo with safeguards (position loss, stale status, pilot intervention), a test of the state machine against a toy vehicle model, and a flight replay from a bag.

## theory
### The uXRCE-DDS bridge
Inside PX4 runs the **client** `uxrce_dds_client`: it publishes the selected uORB topics and subscribes to incoming ones according to the list in `dds_topics.yaml` (in the PX4 sources). Outside runs the **agent** `MicroXRCEAgent`, which exposes these topics on the DDS network as ordinary ROS 2 topics `/fmu/out/*` (from PX4) and `/fmu/in/*` (to PX4). The transport is UDP (SITL: the agent on port 8888, the client starts automatically) or a serial port (`UXRCE_DDS_CFG` selects the port on a real flight controller). Unlike MAVLink, there are no “protocol messages” here — these are the PX4 uORB structures themselves, hence the requirement: **`px4_msgs` on the ROS side must match the PX4 version**.

{{diagram:uxrce-scheme|PX4 and ArduPilot connect to ROS 2 with the same scheme: “client in the firmware — agent on the companion.”}}

### Message versions
Starting with PX4 v1.16, some messages have a version (`MESSAGE_VERSION` in the definition), and their topics are published with a suffix: `/fmu/out/vehicle_status_v1`. To keep old nodes compatible with new firmware and vice versa there is a translator node (PX4 ROS 2 Message Translation Node). Practice for your own nodes: compute the topic name from the message class's `MESSAGE_VERSION` instead of typing it by hand — as done in `px4_offboard_square.py`:

```python
def topic(base, msg_cls):
    v = getattr(msg_cls, "MESSAGE_VERSION", 0)
    return base if v == 0 else f"{base}_v{v}"
```

### Offboard rules
1. The external controller must continuously send `OffboardControlMode` (which setpoints are active: position, velocity, acceleration, attitude, body_rate…) at **more than 2 Hz** — this is the “proof of life.” The actual setpoints go in `TrajectorySetpoint` (position/velocity/acceleration/yaw, unused fields = NaN).
2. The stream must be running **before** the switch to Offboard (and before arming in Offboard), otherwise PX4 refuses.
3. If the stream stops for longer than `COM_OF_LOSS_T`, PX4 leaves Offboard and switches to the mode set in `COM_OBL_RC_ACT` (Position, Altitude, Manual, Return, Land).
4. Commands are `VehicleCommand` on `/fmu/in/vehicle_command`: arm with `VEHICLE_CMD_COMPONENT_ARM_DISARM` (param1 = 1), mode with `VEHICLE_CMD_DO_SET_MODE` (param1 = 1 — custom, param2 = 6 — Offboard), land with `VEHICLE_CMD_NAV_LAND`. The acknowledgement comes on `/fmu/out/vehicle_command_ack`; the state is in `VehicleStatus.arming_state`, `nav_state`.
5. Coordinates in `TrajectorySetpoint` are **NED, local**, with the origin at the EKF initialization point; altitude is negative.

### Flight logic as a state machine
A typical mistake is logic in callbacks: “status arrived → if armed → send mode.” Such code can't be tested, can't be reproduced, and behaves unpredictably when messages are lost. The right way: a pure class `OffboardFSM` (`examples/ros2-docker/.../offboard_fsm.py`) with a single method `step(obs) → action`, no ROS and no time pulled “out of thin air”:

- **Observations** `Obs`: time, age of the last status, position validity, armed, mode, NED position, whether landed.
- **Action** `Action`: setpoint, arm/mode/land requests, a note.
- **States**: WAIT_READY → STREAM_SETPOINTS (≥ 1 s of setpoints before the mode request) → ARMING → OFFBOARD → TAKEOFF → SQUARE → LAND → DONE.
- **Safeguards checked in every active state**: status stale (> 1 s) → ABORT; position invalid → ABORT; step timeout → ABORT; pilot switched the mode themselves → DONE with no commands (don't “fight” the human).

The ROS node does only I/O: it builds `Obs` from the latest messages on a 20 Hz timer, calls `step`, publishes setpoints and (rate-limited) commands. The same state machine is used for ArduPilot (the ros2-ardupilot module) — only the wrapper changes.

{{diagram:offboard-fsm|Offboard node state machine: a linear scenario plus safeguards that lead to landing or hand control back to the pilot.}}

### Testing without a simulator
`test_offboard_fsm.py` runs the state machine against a toy vehicle model (arms on request, enters Offboard only if setpoints have been flowing for ≥ 0.5 s, flies to the setpoint at 2 m/s, lands): it checks the full scenario, the “setpoints before mode” order, and the reaction to position loss, stale status and pilot intervention. That's five tests in 50 ms — you can run them on every commit (in this course, in CI), and only then go to Gazebo.

### Gazebo and SITL
`make px4_sitl gz_x500` — the x500 quadcopter in Gazebo Harmonic; the PX4 documentation (main) recommends ROS 2 Jazzy on Ubuntu 24.04; on Ubuntu 22.04, Humble (the same is stated in the v1.16/v1.17 release documentation). Agent: `MicroXRCEAgent udp4 -p 8888`. For repeatable tests — headless (`HEADLESS=1`) and a fixed world. QGroundControl connects over UDP 14550 in parallel — it's handy for watching modes and aborting the flight.

## practice
### Step 1. Test the state machine
```bash
cd examples/ros2-docker/ws/src/uav_ros2_labs
python -m pytest -q test/test_offboard_fsm.py
```
Add your own test: battery (a new field `battery_low` in `Obs`) → ABORT. Test first, then code.

### Step 2. A square in Gazebo
```bash
docker compose --profile px4 up        # or natively: MicroXRCEAgent + make px4_sitl gz_x500
ros2 launch uav_ros2_labs px4_square.launch.py
```
The node log shows the state transitions; QGC shows the mode changes; `/tmp/px4_flight.csv` holds the trajectory. Plot it: a 10 × 10 m square at 5 m.

### Step 3. Safeguards in the simulator
During SQUARE: (a) switch the mode to Hold in QGC — the node must go to DONE and stop sending commands; (b) stop the node (Ctrl+C) — PX4 must leave Offboard after `COM_OF_LOSS_T` and perform the configured action (write down which one); (c) stop the agent — the node will see a stale status and go to ABORT, but its commands will no longer get through: what will PX4 do?

### Step 4. Replay from a bag
Record a bag of the flight (`/fmu/out/vehicle_status_v1`, `/fmu/out/vehicle_local_position_v1` (in PX4 v1.16 — without the suffix; take the name from `MESSAGE_VERSION`) and your `/fmu/in/*`), then replay only `/fmu/out/*` and start the node: it must go through the same transitions (the commands go “nowhere”). This is how you debug the logic on the bench.

The lab counts as done when your own state machine test passes, you have a plot of the square, the results of the three safeguard scenarios are written up, and the bag replay works.

## diagnostics
- **Symptom:** PX4 refuses to switch to Offboard
  - Possible cause: OffboardControlMode was not streaming before the mode request or is sent at less than 2 Hz; no valid local position.
  - What to do: STREAM_SETPOINTS ≥ 1 s; a 10–20 Hz timer; check xy_valid/z_valid.
- **Symptom:** the node doesn't see `/fmu/out/vehicle_status`
  - Possible cause: the version suffix (`_v1`) or RELIABLE QoS.
  - What to do: the name from MESSAGE_VERSION; the BEST_EFFORT profile.
- **Symptom:** the vehicle goes up and down “the wrong way round”
  - Possible cause: altitude given as positive in NED.
  - What to do: z = −altitude; test the conversions.
- **Symptom:** after the pilot switches to Position, the vehicle “jerks” back into Offboard
  - Possible cause: the node keeps sending the mode request.
  - What to do: detect the intervention and stop sending commands (the DONE state).

## references
- PX4 — ROS 2 user guide | https://docs.px4.io/main/en/ros2/user_guide.html | primary | A
- PX4 — uXRCE-DDS middleware | https://docs.px4.io/main/en/middleware/uxrce_dds.html | primary | A
- PX4 — Offboard mode (2 Hz proof of life, COM_OF_LOSS_T) | https://docs.px4.io/main/en/flight_modes/offboard.html | primary | A
- PX4 — ROS 2 message translation node (versioned topics) | https://docs.px4.io/main/en/ros2/px4_ros2_msg_translation_node.html | primary | A
- PX4 — px4_msgs | https://github.com/PX4/px4_msgs | primary | A

## checklist
- I can explain the roles of the uXRCE-DDS client and agent and why px4_msgs must match the firmware
- I build topic names that account for message versions
- I follow the Offboard rules: stream > 2 Hz, setpoints before the mode, NED
- I keep the flight logic in a pure state machine and test it without ROS
- I verify safeguards in SITL: pilot intervention, node death, agent loss
- I debug the node by replaying a bag
