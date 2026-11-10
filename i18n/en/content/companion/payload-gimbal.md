---
id: payload-gimbal
title: "Gimbals and payload: MAVLink Gimbal v2, camera, drop"
level: L3
readingTime: 35 min
firmware: ArduPilot 4.5+ · PX4 1.15+
status: published
tags:
  - gimbal
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
source_hash: 01805bd541c9
---

## summary
Inspection, mapping, tracking — in every project of the course the camera has to look where the task needs it to, not where the vehicle happens to be pointing. That is the gimbal's job, and these days you talk to it over MAVLink Gimbal Protocol v2. This module covers who is the “manager” and who is the “device” in the system, how to connect a gimbal to ArduPilot (`MNT1_*`) and PX4 (`MNT_*`), how to control it from the radio, from a mission and from companion code, how to tie the camera (`CAM1_*`) to distance-based image capture, and how not to drop the vehicle along with the released payload — from the center of mass to testing the release mechanism.

## theory
### Why a gimbal and which one
- **Stabilization.** A brushless gimbal holds the camera using its own IMU, soaking up vibration and body tilt; the vehicle banks 10–20° in the wind, the picture doesn't.
- **Pointing.** The camera looks at a point (ROI) independently of the vehicle's heading: orbiting a tower, tracking a target, nadir for mapping.
- **Types.** Servo gimbal (two servos, cheap, pointing without stabilization or only rough), brushless gimbal with its own controller (SimpleBGC/STorM32 and similar), “smart” gimbal with a built-in camera (Siyi, ViewPro, Gremsy and others) with its own protocol or MAVLink.

### Gimbal Protocol v2: manager and device
The old protocol (`MOUNT_CONTROL`, `DO_MOUNT_CONTROL`) sent commands straight to the gimbal: the radio, the GCS and the companion fought over who sent the last command. In v2 the roles are separated:
- **Gimbal device** — the gimbal itself: motors, IMU, stabilization. It accepts `GIMBAL_DEVICE_SET_ATTITUDE` and reports its attitude in `GIMBAL_DEVICE_ATTITUDE_STATUS` (quaternion, flags, errors).
- **Gimbal manager** — usually the autopilot. It knows the vehicle's attitude, turns “look at this point” into angles, decides who is in control right now (primary/secondary control), and hands commands to the device.
- **Clients** — GCS, companion, mission, radio — send commands to the manager: `MAV_CMD_DO_GIMBAL_MANAGER_PITCHYAW` or a stream of `GIMBAL_MANAGER_SET_PITCHYAW`, and take control with `MAV_CMD_DO_GIMBAL_MANAGER_CONFIGURE`.

The angle flags matter: yaw can be set “relative to the vehicle” (follow) or “relative to north” (lock). To orbit an object you need lock or ROI, otherwise the camera turns along with the vehicle.

### ArduPilot: `MNT1_*`
| What | Parameter | Comment |
|---|---|---|
| Gimbal type | `MNT1_TYPE` | servo, Brushless PWM, SToRM32, Siyi, ViewPro, Gremsy/MAVLink, etc. — value from the list for your version |
| Default mode | `MNT1_DEFLT_MODE` | 0 retract, 1 neutral, 2 MAVLink, 3 RC, 4 GPS point, 5 SysID, 6 Home |
| Limits | `MNT1_PITCH_MIN/MAX`, `MNT1_YAW_MIN/MAX`, `MNT1_ROLL_MIN/MAX` | gimbal mechanics, in degrees |
| Radio: angle or rate | `MNT1_RC_RATE` | 0 — the stick sets the angle, > 0 — rate in °/s |
| Radio channels | `RCx_OPTION` | 212 Mount1 Roll, 213 Mount1 Pitch, 214 Mount1 Yaw, 163 Mount Lock (heading hold) |
| Servo gimbal | `SERVOn_FUNCTION` | 6 Mount1 Yaw, 7 Mount1 Pitch, 8 Mount1 Roll |
| Smart gimbal port | `SERIALn_PROTOCOL` | 8 = Gimbal (Siyi, ViewPro, etc.); for a MAVLink gimbal — MAVLink 2 |

A MAVLink gimbal has to show up as a separate component (`MAV_COMP_ID_GIMBAL`, 154) — you can see it in the GCS MAVLink inspector. No component — no control.

### PX4: `MNT_*`
`MNT_MODE_IN` selects the command source (RC, MAVLink Gimbal v1/v2), `MNT_MODE_OUT` sets how PX4 drives the gimbal (AUX/PWM outputs or MAVLink Gimbal v2). For a MAVLink gimbal you need a port running MAVLink; servo outputs go through the Actuators tab. Details change between versions — check against the Gimbal (Mount) section of the PX4 docs.

### Camera: capture on command and by distance
- ArduPilot: `CAM1_TYPE` — how to fire the shutter (servo, relay, via the gimbal, MAVLink, MAVLink Camera v2). `CAM1_TRIGG_DIST` or the mission command `DO_SET_CAM_TRIGG_DIST` — a shot every N meters. Every shot is written to the log (`CAM`) with coordinates — that is the basis of georeferencing in mapping.
- MAVLink Camera Protocol v2: `MAV_CMD_IMAGE_START_CAPTURE`, `MAV_CMD_VIDEO_START_CAPTURE`, with the reply `CAMERA_IMAGE_CAPTURED` carrying coordinates and the frame index.
- Mission: `DO_SET_ROI_LOCATION` — look at a point, `DO_SET_ROI_NONE` — release it, `DO_GIMBAL_MANAGER_PITCHYAW` — set angles; for nadir — pitch −90°.

### Payload: mass, center of mass, drop
- **Center of mass.** A load under the frame lowers the CoM and shifts it forward/back — the throttle balance between motors changes. Rule: after installing the payload, look at the motor outputs at hover in the log; a spread of more than ~10 % between front and rear means move the payload or the battery.
- **Mass and tuning.** +30 % mass means higher hover throttle and different inertia; check `MOT_THST_HOVER` (ArduPilot) after the first flights and, if the difference is noticeable, run autotune with the payload.
- **Drop.** The load leaves — the mass drops in a step, the vehicle “jumps”. Drop with altitude to spare, in a hover, in a mode that holds altitude. ArduPilot: `GRIP_ENABLE = 1`, `GRIP_TYPE` (servo or electromagnet), the command `MAV_CMD_DO_GRIPPER` in a mission or from the radio (`RCx_OPTION` 19 — Gripper).
- **Payload failure.** The gimbal can go into an error state (overheating, a jammed motor) — flags in `GIMBAL_DEVICE_ATTITUDE_STATUS`. The mission must not depend on the gimbal for flight safety.

{{diagram:gimbal-manager|Gimbal Protocol v2: clients (GCS, companion, radio, mission) command the manager in the autopilot; the manager commands the gimbal and receives its attitude back.}}

## practice
### Step 1. Connection and the component
Connect a gimbal (SITL will do: ArduPilot SITL has a simulated gimbal, `MNT1_TYPE = 1` with servos or a MAVLink gimbal per the SITL docs). Set `MNT1_TYPE` and the limits, reboot. In the MAVLink inspector find `GIMBAL_DEVICE_ATTITUDE_STATUS` (for servo and serial gimbals the autopilot itself sends it, component 1; a separate component 154 only appears with a MAVLink gimbal). Write down the message rate.

### Step 2. Radio
`RC6_OPTION = 213` (pitch), `RC8_OPTION = 214` (yaw), `MNT1_RC_RATE = 0`. Check that the stick sets the angle and the limits are respected. Switch to `MNT1_RC_RATE = 30` — now the stick sets the rate. Decide which is more convenient for the operator and write it down.

### Step 3. From companion code
Python + pymavlink: send a `COMMAND_LONG` with `MAV_CMD_DO_GIMBAL_MANAGER_PITCHYAW` (param1 — pitch, param2 — yaw, param5 — flags, param7 — device id, 0 = all).

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
look(-30, 45, True)   # 45° from north, hold while turning
```
Check that `COMMAND_ACK` = ACCEPTED and the attitude in `GIMBAL_DEVICE_ATTITUDE_STATUS`. Yaw the vehicle in both modes and describe the difference.

### Step 4. A mission with ROI and capture
Mission: takeoff → `DO_SET_ROI_LOCATION` on the object → three waypoints around the object → `DO_SET_CAM_TRIGG_DIST` 5 m on a straight leg → `DO_SET_ROI_NONE` → RTL. After the flight (SITL), find the `CAM` messages in the log and check whether the number of shots matches the leg length / 5 m.

### Step 5. Center of mass with a payload
On a real vehicle (or by calculation from the masses): hover without the payload and with it, compare the average motor outputs (`RCOU`) at the front and rear. Write down the spread in percent and the decision (move the load/battery).

The lab counts as done when the gimbal status (`GIMBAL_DEVICE_ATTITUDE_STATUS`) is visible in the GCS, the gimbal is controlled from the radio and from code with an ACK check, the mission with ROI and distance-based capture gives the expected number of frames in the log, and the balance with the payload is checked with numbers.

## diagnostics
- **Symptom:** the gimbal doesn't respond to commands from the GCS
  - Possible cause: wrong `MNT1_TYPE`, a MAVLink gimbal has no component 154, the port isn't in MAVLink/Gimbal mode, the gimbal mode is RC instead of MAVLink.
  - What to do: MAVLink inspector, `MNT1_DEFLT_MODE`, the port protocol, a reboot after changing the type.
- **Symptom:** the camera swings off to the side when the vehicle turns
  - Possible cause: yaw is in follow mode, not lock.
  - What to do: the YAW_LOCK flag, Mount Lock from the radio (163), or ROI.
- **Symptom:** radio and companion commands “fight”
  - Possible cause: two clients without an explicit control takeover.
  - What to do: `MAV_CMD_DO_GIMBAL_MANAGER_CONFIGURE`, a single point of control, an explicit switch on the radio.
- **Symptom:** fewer shots than expected
  - Possible cause: `CAM1_TYPE` doesn't match the wiring, `CAM1_TRIGG_DIST` isn't set, the camera can't keep up (the interval is shorter than the write time).
  - What to do: check the type and the `CAM` messages in the log, increase the distance or reduce the speed.
- **Symptom:** after the payload drop the vehicle climbs sharply
  - Possible cause: the step change in mass, a drop in a mode without altitude hold.
  - What to do: drop in a hover in an altitude-holding mode, with altitude to spare; check the response in SITL.

## references
- ArduPilot — Gimbal / Mount setup | https://ardupilot.org/copter/docs/common-cameras-and-gimbals.html | primary | A
- ArduPilot — Mount targeting and RC control | https://ardupilot.org/copter/docs/common-mount-targeting.html | primary | A
- MAVLink — Gimbal Protocol v2 | https://mavlink.io/en/services/gimbal_v2.html | primary | A
- MAVLink — Camera Protocol v2 | https://mavlink.io/en/services/camera.html | primary | A
- PX4 — Gimbal (Mount) configuration | https://docs.px4.io/main/en/advanced/gimbal_control.html | primary | A

## checklist
- I can explain the roles of gimbal manager and gimbal device in protocol v2
- I can set up a gimbal in ArduPilot (`MNT1_*`) and know the PX4 equivalents
- I can control the gimbal from the radio (angle/rate) and from code with an ACK check
- I can tell follow from lock in yaw and use ROI in a mission
- I can set up distance-based image capture and find the shots in the log
- I can check the center of mass with a payload and drop a load safely
