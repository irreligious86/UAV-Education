---
id: payload-gimbal
title: "Gimbals and payloads: MAVLink Gimbal v2, camera, payload drop"
level: L3
readingTime: 35 min
firmware: ArduPilot 4.7 (checked against 4.7.3) · PX4 1.18 (checked against v1.18.0)
status: published
tags:
  - mount
  - gimbal
  - payload
  - camera
related:
  - mav-component
  - mav-services
  - ap-missions
  - per-camera
  - per-mapping
next:
  - per-mapping
source: content/companion/payload-gimbal.md
source_hash: 003ae597c284
---

## summary
Inspection, mapping, tracking: in every project of the course the camera has to look where the task needs it, not wherever the vehicle happens to be pointing. That is the gimbal's job, and today the usual way to talk to it is MAVLink Gimbal Protocol v2. This module covers who in the system is the "manager" and who is the "device", how to connect a gimbal to ArduPilot (`MNT1_*`) and PX4 (`MNT_*`), how to control it from the transmitter, from a mission and from companion code, how to tie the camera (`CAM1_*`) to distance-based capture, and how not to lose the vehicle together with a dropped payload, from the center of gravity to testing the release mechanism.

## theory
### Why a gimbal, and which one
- **Stabilization.** A brushless gimbal holds the camera using its own IMU, damping vibration and body tilt; in wind the vehicle banks 10–20°, the picture does not.
- **Pointing.** The camera looks at a point (ROI) regardless of the vehicle heading: orbiting a tower, tracking a target, nadir for mapping.
- **Types.** A servo gimbal (two servos, cheap, pointing with no or rough stabilization), a brushless gimbal with its own controller (SimpleBGC/STorM32 and similar), a "smart" gimbal with a camera (Siyi, ViewPro, Gremsy and others) with its own protocol or MAVLink.

### Gimbal Protocol v2: manager and device
The old protocol (`MOUNT_CONTROL`, `DO_MOUNT_CONTROL`) sent commands straight to the gimbal: the transmitter, the GCS and the companion fought over who sent the last command. In v2 the roles are separated:
- **Gimbal device**: the gimbal itself: motors, IMU, stabilization. It accepts `GIMBAL_DEVICE_SET_ATTITUDE` and reports its orientation in `GIMBAL_DEVICE_ATTITUDE_STATUS` (quaternion, flags, errors).
- **Gimbal manager**: usually the autopilot. It knows the vehicle attitude, turns "look at a point" into angles, decides who is in control right now (primary/secondary control) and sends commands to the device.
- **Clients**: the GCS, the companion, a mission, the transmitter send commands to the manager: `MAV_CMD_DO_GIMBAL_MANAGER_PITCHYAW` or a stream of `GIMBAL_MANAGER_SET_PITCHYAW` (ArduPilot; as a stream PX4 accepts only `GIMBAL_MANAGER_SET_ATTITUDE`), and taking control is done with `MAV_CMD_DO_GIMBAL_MANAGER_CONFIGURE`.

The angle flags matter: yaw can be set "relative to the vehicle" (follow) or "relative to north" (lock). Orbiting an object needs lock or an ROI, otherwise the camera turns along with the vehicle.

### ArduPilot: `MNT1_*`
| What | Parameter | Comment |
|---|---|---|
| Mount type | `MNT1_TYPE` | ArduPilot 4.7.3: 0 None, 1 Servo, 2 3DR Solo, 3 Alexmos Serial, 4 SToRM32 MAVLink, 5 SToRM32 Serial, 6 MAVLink (Gremsy, AVT), 7 BrushlessPWM, 8 Siyi, 9 Scripting, 10 Xacti, 11 Viewpro, 12 Topotek, 13 CADDX, 14 XFRobot (new in 4.7; in 4.6 the list ended at 13). While it is 0 the other `MNT1_*` are hidden; reboot after changing it |
| Default mode | `MNT1_DEFLT_MODE` | 0 Retracted, 1 Neutral, 2 MavLink Targeting, 3 RC Targeting, 4 GPS Point, 5 SysID Target, 6 Home Location; the default is 3, so after boot the gimbal listens to the transmitter |
| Limits | `MNT1_PITCH_MIN/MAX`, `MNT1_YAW_MIN/MAX`, `MNT1_ROLL_MIN/MAX` | the gimbal mechanics, in degrees |
| Transmitter: angle or rate | `MNT1_RC_RATE` | 0: the stick sets the angle, > 0: the rate in °/s |
| Transmitter channels | `RCx_OPTION` | 212 Mount1 Roll, 213 Mount1 Pitch, 214 Mount1 Yaw, 163 Mount Yaw Lock (heading hold; before 4.7, "Mount Lock") |
| Servo gimbal | `SERVOn_FUNCTION` | 6 Mount1Yaw, 7 Mount1Pitch, 8 Mount1Roll |
| Smart gimbal port | `SERIALn_PROTOCOL` | 8 = Gimbal (Siyi, ViewPro and others); for a MAVLink gimbal, MAVLink2 |

Wiring by type, as a selection rule (the full table of drivers and parameters is in `ap-payload`):

| `MNT1_TYPE` | Where to connect | What else to set |
|---|---|---|
| 1 Servo, 7 BrushlessPWM | flight controller outputs | `SERVOn_FUNCTION` 6/7/8 (yaw/pitch/roll); with 1 the flight controller subtracts the vehicle tilt itself, with 7 the gimbal stabilizes itself |
| 3 Alexmos Serial | UART | `SERIALn_PROTOCOL = 7`, the 115 baud setting is applied automatically |
| 5 SToRM32 Serial, 8 Siyi, 11 Viewpro, 12 Topotek, 13 CADDX, 14 XFRobot | UART: FC TX → gimbal RX, RX → TX, common ground | `SERIALn_PROTOCOL = 8` (Gimbal); the camera in the gimbal is `CAM1_TYPE = 4` (Mount) |
| 4 SToRM32 MAVLink, 6 MAVLink | a MAVLink2 port | the gimbal is component 154; a Gremsy/AVT camera is `CAM1_TYPE = 6` |
| 10 Xacti | DroneCAN | `CAM1_TYPE = 4` |

Check: after a reboot there is no `PreArm: Mount: …`, and the stick of the channel with `RCx_OPTION = 213` moves the tilt in mode 3.

A MAVLink gimbal must show up as a separate component (`MAV_COMP_ID_GIMBAL`, 154), visible in the GCS MAVLink inspector. No component, no control.

### PX4: `MNT_*`
The order for PX4 1.18 (checked against v1.18.0; the full walkthrough with the "angle → µs" arithmetic and the differences from 1.17 is in `px4-camera-gimbal`):

1. **Starting the module.** `MNT_MODE_IN` defaults to −1: the `gimbal` module does not start at all (the condition in `rcS` is `MNT_MODE_IN` > −1), and `gimbal status` answers "not running". Values: 0 Auto (transmitter and MAVLink Gimbal v2 together), 1 transmitter only, 2 and 3 protocol v1 (being deprecated, do not choose), 4 MAVLink Gimbal v2 only, 5 (since 1.18) a fixed angle `MNT_FIXED_PITCH`, commands are not accepted. The rule: transmitter plus something else, 0; transmitter only, 1; only the GCS, a mission or the companion, 4. The parameter is read at startup, so reboot.
2. **Output.** `MNT_MODE_OUT`: 0 AUX, servos on outputs with the functions Gimbal Roll / Pitch / Yaw = 420 / 421 / 422 (the Actuators screen, 50 Hz, see `px4-outputs-servos`); 2 MAVLink Gimbal v2 for a gimbal with its own controller. Also needs a reboot.
3. **The port for a MAVLink gimbal.** `MAV_n_CONFIG` = the port, `MAV_n_MODE` = 10 (Gimbal); the gimbal must send `GIMBAL_DEVICE_INFORMATION` (usually from component 154): until it does, PX4 requests it once a second and sends the `GIMBAL_DEVICE_SET_ATTITUDE` setpoints without a component address (target component 0), and `gimbal status` prints "gimbal device compid not found".
4. **Transmitter.** `MNT_MAN_PITCH` (and `_ROLL`, `_YAW`) = AUX number 1…6, and `RC_MAP_AUXn` with the same n = the receiver channel number; you need both, otherwise the axis gets a constant zero. `MNT_RC_IN_MODE`: 0 the stick sets the angle, 1 (default) the rate `MNT_RATE_PITCH` = 30 °/s.
5. **Check.** `gimbal status`: the module is alive; `gimbal test pitch -45`: the gimbal tilts down by 45° (keep hands and cables out of the range of motion; for the AUX output in 1.18 only with `MNT_DO_STAB` ≠ 0, otherwise the angle from `gimbal test` does not reach the output). It does not tilt down to nadir: `MNT_MIN_PITCH` is above −90 (default −45; before 1.18 the same came from `MNT_RANGE_PITCH` = 90). The stick in rate mode creeps barely at all: in 1.18 the culprit is the `MNT_TAU` filter (0.3 s); for stick control set it to 0.

{{diagram:gimbal-control-paths|In ArduPilot the gimbal listens to the transmitter right after boot (MNT1_DEFLT_MODE = 3), in PX4 the gimbal module is not even started by default (MNT_MODE_IN = −1), and a MAVLink gimbal without GIMBAL_DEVICE_INFORMATION gets setpoints with no address.}}

### Camera: capture on command and by distance
- ArduPilot: `CAM1_TYPE` is how the shutter is triggered: 1 Servo, 2 Relay, 4 through the mount driver (Siyi, Topotek, Viewpro, Xacti: the camera inside a "smart" gimbal), 5 MAVLink (`DO_DIGICAM_CONTROL`), 6 MAVLink Camera v2, 7 Scripting, 8 RunCam; details in `ap-payload`. `CAM1_TRIGG_DIST` or the mission command `DO_SET_CAM_TRIGG_DIST`: a shot every N meters. Every shot is logged (`CAM`) with its coordinates, which is the basis of georeferencing in mapping.
- MAVLink Camera Protocol v2: `MAV_CMD_IMAGE_START_CAPTURE`, `MAV_CMD_VIDEO_START_CAPTURE`, and the reply `CAMERA_IMAGE_CAPTURED` with the coordinates and the image index.
- Mission: `DO_SET_ROI_LOCATION` to look at a point, `DO_SET_ROI_NONE` to release it, `DO_GIMBAL_MANAGER_PITCHYAW` to set the angles; for nadir, pitch −90°.

### Payload: mass, center of gravity, drop
- **Center of gravity.** A payload under the frame lowers the CG and shifts it forward/backward, which changes the throttle balance between the motors. Rule: after installing the payload, look at the motor outputs in a hover in the log; a spread of more than ~10 % between front and rear means move the payload or the battery.
- **Mass and tuning.** +30 % of mass means more hover throttle and different inertia; check `MOT_THST_HOVER` (ArduPilot) after the first flights and, if the difference is noticeable, run autotune with the payload.
- **Drop.** The payload leaves, the mass drops in a step, and the vehicle "jumps". Drop with altitude to spare, in a hover, in an altitude-holding mode. ArduPilot: `GRIP_ENABLE = 1`, `GRIP_TYPE` (1 Servo, 2 EPM: an electropermanent magnet that holds the load without power and switches on a pulse), the `MAV_CMD_DO_GRIPPER` command in a mission or from the transmitter (`RCx_OPTION` 19, Gripper).
- **Payload failure.** The gimbal can go into an error state (overheating, a jammed motor): the flags in `GIMBAL_DEVICE_ATTITUDE_STATUS`. Flight safety in a mission must not depend on the gimbal.

{{diagram:gimbal-manager|Gimbal Protocol v2: the clients (GCS, companion, transmitter, mission) command the manager in the autopilot; the manager commands the gimbal and gets its orientation back.}}

### Where it fits in the system

- **Takes in:** the vehicle attitude (the gimbal manager in the autopilot turns "look at a point" into angles); commands from the transmitter, the mission and the companion (`mav-services`, `ap-missions`); a separate compid and route (`mav-routing`).
- **Hands off:** `GIMBAL_DEVICE_ATTITUDE_STATUS`, the camera orientation for georeferencing (`per-geometry`); distance-based shots with a `CAM` record in the log (`per-mapping`); keeping the target in the frame (`per-tracking`).
- **If you get this wrong:** the payload shifted the center of gravity → the front and rear motor outputs differ by more than ~10 %, the control margin shrinks; visible in `RCOU` (`ap-logs`), the cause is covered in `ctl-allocation`. `ATTITUDE` used in the geometry instead of the gimbal angles → the ground point is wrong even though the detector works (`per-geometry`).

## practice
### Step 1. Connection and component
Connect a gimbal (SITL will do: ArduPilot SITL has a simulated gimbal, `MNT1_TYPE = 1` with servos, or a MAVLink gimbal as described in the SITL documentation). Set `MNT1_TYPE` and the limits, reboot. In the MAVLink inspector find `GIMBAL_DEVICE_ATTITUDE_STATUS` (for servo and serial gimbals the autopilot itself sends it as component 1; a separate component 154 appears only with a MAVLink gimbal). Record the message rate.

### Step 2. Transmitter
`RC6_OPTION = 213` (pitch), `RC8_OPTION = 214` (yaw), `MNT1_RC_RATE = 0`. Check that the stick sets the angle and the limits are respected. Switch to `MNT1_RC_RATE = 30`: now the stick sets the rate. Decide which is more convenient for the operator and write it down.

### Step 3. From companion code
Python + pymavlink: send a `COMMAND_LONG` with `MAV_CMD_DO_GIMBAL_MANAGER_PITCHYAW` (param1 pitch, param2 yaw, param5 flags, param7 the device id, 0 = all).

```python
from pymavlink import mavutil
m = mavutil.mavlink_connection("udpin:0.0.0.0:14550"); m.wait_heartbeat()
def look(pitch, yaw, lock_yaw=False):
    flags = mavutil.mavlink.GIMBAL_MANAGER_FLAGS_YAW_LOCK if lock_yaw else 0
    m.mav.command_long_send(m.target_system, m.target_component,
        mavutil.mavlink.MAV_CMD_DO_GIMBAL_MANAGER_PITCHYAW, 0,
        pitch, yaw, float("nan"), float("nan"), flags, 0, 0)
    print(m.recv_match(type="COMMAND_ACK", blocking=True, timeout=3))
look(-90, 0)          # nadir
look(-30, 45, True)   # 45° from north, held while the vehicle turns
```
Check that `COMMAND_ACK` = ACCEPTED and the orientation in `GIMBAL_DEVICE_ATTITUDE_STATUS`. Turn the vehicle in yaw in both modes and describe the difference. On PX4, without a prior `MAV_CMD_DO_GIMBAL_MANAGER_CONFIGURE` (taking control with your sysid/compid) the answer will be `DENIED`: commands are accepted only from the source that has control (`px4-camera-gimbal`).

### Step 4. A mission with an ROI and capture
Mission: takeoff → `DO_SET_ROI_LOCATION` on the object → three waypoints around the object → `DO_SET_CAM_TRIGG_DIST` 5 m on the straight leg (param3 = 1: first shot immediately) → `DO_SET_ROI_NONE` → RTL. After the flight (SITL) find the `CAM` messages in the log and count whether the number of shots matches ⌈leg length / 5 m⌉: the first shot is on the command, then every 5 m with a small overshoot, so a shot exactly at the end of the leg already falls past it. Without param3 = 1 there is no first shot: the firmware only remembers the point (`ap-payload`).

### Step 5. Center of gravity with the payload
On a real vehicle (or by calculation from the masses): hover without the payload and with it, compare the average motor outputs (`RCOU`) front and rear. Record the spread in percent and the decision (move the payload/battery).

Self-check: the lab is done when the gimbal status (`GIMBAL_DEVICE_ATTITUDE_STATUS`) is visible in the GCS and its rate is recorded, the transmitter stick sets the angle with `MNT1_RC_RATE = 0` and the rate with 30 while respecting the limits, the code gets `COMMAND_ACK` = ACCEPTED (on PX4 after `DO_GIMBAL_MANAGER_CONFIGURE`) and the orientation in `GIMBAL_DEVICE_ATTITUDE_STATUS` matches the command, the number of `CAM` records in the mission log equals ⌈leg length / 5 m⌉ (or one or two fewer on a long leg, because the overshoot of the 50 Hz check accumulates), and the spread of the average `RCOU` of the front and rear motors with the payload is computed in percent (more than ~10 %: move the payload or the battery).

**Reference answer for the self-check.** The difference between the yaw modes in step 3: without the lock flag (follow) the angle is relative to the vehicle, and when the vehicle turns in yaw the camera turns with it; with `YAW_LOCK` the angle is relative to north, and the camera keeps looking the same way. Common mistake #1: the gimbal behaves the same in both modes, because the flag did not get through; check param5 and `COMMAND_ACK`. Common mistake #2: follow left on for an object orbit: the camera leaves the object on every turn; you need lock or an ROI.

## diagnostics
- **Symptom:** the gimbal does not respond to commands from the GCS
  - Possible cause: wrong `MNT1_TYPE`, a MAVLink gimbal without component 154, the port not set to MAVLink/Gimbal, the gimbal mode is RC instead of MAVLink.
  - What to do: the MAVLink inspector, `MNT1_DEFLT_MODE`, the port protocol, a reboot after changing the type.
- **Symptom:** the camera swings away when the vehicle turns
  - Possible cause: yaw in follow mode instead of lock.
  - What to do: the YAW_LOCK flag, Mount Yaw Lock from the transmitter (163) or an ROI.
- **Symptom:** the transmitter and companion commands "fight"
  - Possible cause: two clients without an explicit takeover of control.
  - What to do: `MAV_CMD_DO_GIMBAL_MANAGER_CONFIGURE`, a single point of control, an explicit switch on the transmitter.
- **Symptom:** fewer shots than expected
  - Possible cause: `CAM1_TYPE` does not match the wiring, `CAM1_TRIGG_DIST` is not set, the camera cannot keep up (the interval is shorter than the write time).
  - What to do: check the type and the `CAM` messages in the log, increase the distance or lower the speed.
- **Symptom:** after dropping the payload the vehicle climbs sharply
  - Possible cause: the step in mass, a drop in a mode without altitude hold.
  - What to do: drop in a hover in an altitude-holding mode, altitude to spare, check the response in SITL.

## references
- ArduPilot — Gimbal / Mount setup | https://ardupilot.org/copter/docs/common-cameras-and-gimbals.html | primary | A
- ArduPilot — Mount targeting and RC control | https://ardupilot.org/copter/docs/common-mount-targeting.html | primary | A
- MAVLink — Gimbal Protocol v2 | https://mavlink.io/en/services/gimbal_v2.html | primary | A
- MAVLink — Camera Protocol v2 | https://mavlink.io/en/services/camera.html | primary | A
- PX4 — Gimbal (Mount) configuration | https://docs.px4.io/main/en/advanced/gimbal_control.html | primary | A

## checklist
- I can explain the roles of the gimbal manager and the gimbal device in protocol v2
- I set up a gimbal in ArduPilot (`MNT1_*`) and know the PX4 equivalents
- I control the gimbal from the transmitter (angle/rate) and from code, checking the ACK
- I tell follow from lock in yaw and use an ROI in a mission
- I set up distance-based capture and find the shots in the log
- I check the center of gravity with the payload and drop the payload safely
