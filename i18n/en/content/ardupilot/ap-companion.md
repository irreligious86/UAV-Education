---
id: ap-companion
title: "Companion + ArduPilot: Control from Code"
level: L3
readingTime: 30 min
firmware: ArduPilot 4.5+
status: published
added: 2026-11-07
tags:
  - GUIDED
  - offboard
  - pymavlink
related:
  - comp-raspberry
  - ap-missions
next:
  - bf-custom
source: content/ardupilot/ap-companion.md
source_hash: ee44ca670ea8
---

## summary
GUIDED mode is the door through which a companion computer controls the vehicle: “fly to a point”, “hold a velocity”, “look over there”. This module shows how to set position and velocity targets from Python on the companion, how ArduPilot protects itself from a companion that goes silent or goes crazy, and how to build the control loop so that you can debug it safely in SITL. The result is a skeleton for the track's capstone: your own logic on board.

## theory
### GUIDED and its timeouts
In GUIDED the vehicle waits for targets from an external source. Targets can be:

- **position** — `SET_POSITION_TARGET_GLOBAL_INT` (86) with coordinates or `SET_POSITION_TARGET_LOCAL_NED` (84) in meters relative to home/the vehicle;
- **velocity** — the same messages with a `type_mask` bitmask that says “ignore position, use velocity”;
- **attitude/thrust** — `SET_ATTITUDE_TARGET` for advanced cases.

Velocity targets are valid for a limited time: if the companion goes silent, after a timeout (on the order of seconds, the `GUID_TIMEOUT` parameter) ArduPilot puts the vehicle into a hover. This is a protection you should rely on, not work around.

### Coordinate frame
`LOCAL_NED`: X is north, Y is east, Z is **down**. Climbing 10 m means Z = −10. Half of all offboard-code bugs are the sign of the Z axis. For targets relative to the vehicle's nose there is `MAV_FRAME_BODY_OFFSET_NED`.

### What the FC checks
The geofence (`FENCE_*`), speed and acceleration limits (`WP_*`, before 4.7 — `WPNAV_*`), the battery failsafe, EKF health. The companion can ask for anything — execution still stays within the FC's parameters. Hence the debugging rule: if the vehicle “doesn't listen”, first `STATUSTEXT`, then the limit parameters, and only then your own code.

### The control loop
A good companion loop:

1. Read the state (position, velocity, mode, armed) from telemetry at a set rate.
2. Compute a decision.
3. Send the target **regularly** (for example 5–10 Hz for velocity), even if it has not changed.
4. Check that the mode is still GUIDED: the pilot can take control with a switch at any moment, and the code must respect that.

### Companion code as a state machine
A script that “sent a command, slept 10 seconds, sent the next one” works in SITL and breaks in the field: the command was not accepted, the pilot switched modes, GPS dropped out. The reliable form is a state machine where every transition checks a condition and has a timeout:

| State | What it does | Next transition | If it fails |
|---|---|---|---|
| WAIT_READY | waits for a GPS fix and EKF OK in telemetry | ready | wait, send nothing |
| ARM_TAKEOFF | GUIDED, arm, `MAV_CMD_NAV_TAKEOFF`, waits for the ACK and altitude ≥ 90 % of the target | altitude reached | no altitude within 20 s → LAND |
| TASK | sends targets at 5–10 Hz, checks the mode every iteration | task done | mode is not GUIDED → PILOT |
| RETURN | `RTL` via a mode-change command | disarm | — |
| PILOT | **stays silent**, only reads telemetry | the pilot switched back to GUIDED and confirmed | — |

Skeleton:
```python
import time
from pymavlink import mavutil

class Mission:
    def __init__(self, m):
        self.m, self.state, self.t0 = m, "WAIT_READY", time.time()
        self.alt, self.mode, self.armed = 0.0, "", False

    def go(self, state):
        print(f"{self.state} -> {state}"); self.state, self.t0 = state, time.time()

    def read(self):
        while (msg := self.m.recv_match(blocking=False)) is not None:
            t = msg.get_type()
            if t == "GLOBAL_POSITION_INT": self.alt = msg.relative_alt / 1000
            elif t == "HEARTBEAT" and msg.type != mavutil.mavlink.MAV_TYPE_GCS:
                self.mode = mavutil.mode_string_v10(msg)
                self.armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)

    def step(self):
        self.read()
        if self.state in ("TASK", "ARM_TAKEOFF") and self.mode not in ("GUIDED", ""):
            return self.go("PILOT")                       # the pilot always wins
        if self.state == "ARM_TAKEOFF" and time.time() - self.t0 > 20 and self.alt < 9:
            self.m.set_mode(self.m.mode_mapping()["LAND"]); return self.go("PILOT")
        # ... the remaining transitions follow the table
```
Code like this is easy to test: replace `m` with a fake connection (as in `examples/mavlink/tests`) and check every row of the table, including “the pilot took control in the middle of TASK”.

### Safety during development
- Everything goes to SITL first. The same code, the same port, only a different address.
- A pilot with a radio and a switch set to LOITER/RTL — always, even when it “definitely works”.
- The geofence is enabled and tested.
- The first real tests use position targets only, at low altitude; velocity comes later.

### Example: velocity in GUIDED (pymavlink)
```python
from pymavlink import mavutil
m = mavutil.mavlink_connection("tcp:127.0.0.1:5762"); m.wait_heartbeat()
m.set_mode(m.mode_mapping()["GUIDED"]); m.arducopter_arm(); m.motors_armed_wait()
m.mav.command_long_send(m.target_system, m.target_component, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0,0,0,0,0,0, 10)
import time; time.sleep(10)
for _ in range(50):                          # 10 s at 5 Hz: forward 1 m/s in body frame
    m.mav.set_position_target_local_ned_send(
        0, m.target_system, m.target_component, mavutil.mavlink.MAV_FRAME_BODY_OFFSET_NED,
        0b0000111111000111,                    # use velocity only (bits: ignore pos x/y/z, acc, yaw, yaw_rate)
        0,0,0,  1.0,0.0,0.0,  0,0,0,  0,0)
    time.sleep(0.2)
# stop sending -> after GUID_TIMEOUT (3 s default) the copter stops and hovers
```
The full starter project (a square, a failsafe test, CI) is `examples/sitl-pymavlink` in the course repository. `GUID_TIMEOUT` = 3.0 s by default (range 0.1–5); `GUID_OPTIONS` bits: 0 — allow arming from the radio in GUIDED, 2 — ignore pilot yaw, 6 — waypoint navigation for position targets, 7 — weathervaning.

### Worked example: “the vehicle doesn't move on a velocity command”
Checks in order: (1) the mode is GUIDED (`HEARTBEAT.custom_mode`); (2) `type_mask` — is velocity masked out; (3) the send rate is ≥ 2 Hz (3 s timeout); (4) `WP_SPD` (before 4.7 — `WPNAV_SPEED`)/`PSC_*` do not limit it to zero; (5) the geofence is not holding it at the boundary; (6) `STATUSTEXT` — “EKF needs position” and the like. In 80% of cases it is (1) or (2).

{{diagram:guided-timeout|A velocity target in GUIDED is valid for GUID_TIMEOUT (3 s by default): the companion must repeat it more often, otherwise the vehicle stops and hovers.}}

## practice
### Step 1. Takeoff and a position target (SITL)
```python
import time
from pymavlink import mavutil

m = mavutil.mavlink_connection("tcp:127.0.0.1:5762")  # on the drone: tcp:127.0.0.1:5760 via router
m.wait_heartbeat()

def ack(cmd):
    a = m.recv_match(type="COMMAND_ACK", blocking=True, timeout=3)
    assert a and a.command == cmd and a.result == 0, f"command {cmd} failed: {a}"

m.set_mode(m.mode_mapping()["GUIDED"])
m.mav.command_long_send(m.target_system, m.target_component,
    mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 1, 0, 0, 0, 0, 0, 0)
ack(400)
m.mav.command_long_send(m.target_system, m.target_component,
    mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, 10)
ack(22)
time.sleep(8)

# fly 20 m north, 0 east, stay at 10 m: LOCAL_NED, Z is DOWN
POS_ONLY = 0b0000_1111_1111_1000  # use x,y,z; ignore velocity, accel, yaw
m.mav.set_position_target_local_ned_send(
    0, m.target_system, m.target_component,
    mavutil.mavlink.MAV_FRAME_LOCAL_NED, POS_ONLY,
    20, 0, -10,  0, 0, 0,  0, 0, 0,  0, 0)
```

### Step 2. A velocity target, sent regularly
```python
VEL_ONLY = 0b0000_1111_1100_0111  # use vx,vy,vz; ignore position, accel, yaw
t_end = time.time() + 5
while time.time() < t_end:
    hb = m.recv_match(type="HEARTBEAT", blocking=False)
    if hb and hb.type != mavutil.mavlink.MAV_TYPE_GCS and mavutil.mode_string_v10(hb) != "GUIDED":
        print("pilot took over, stop sending"); break
    m.mav.set_position_target_local_ned_send(
        0, m.target_system, m.target_component,
        mavutil.mavlink.MAV_FRAME_LOCAL_NED, VEL_ONLY,
        0, 0, 0,  1.0, 0, 0,  0, 0, 0,  0, 0)   # 1 m/s north
    time.sleep(0.2)                              # 5 Hz, inside GUID_TIMEOUT
```

Stop sending and the vehicle will hover by itself. That is the timeout test: run it on purpose.

### Step 2b. The state machine on a fake connection
Finish the transitions from the table and a test: the fake returns a HEARTBEAT with LOITER mode in the middle of TASK — the state machine must move to PILOT and not send a single further target. Second test: altitude does not increase for 20 s after takeoff — the state machine commands LAND. Both tests go into CI, as in the `examples/sitl-pymavlink` starter.

### Step 3. The capstone skeleton
Assemble it from the track's modules: a Raspberry Pi with a router → a Python service → GUIDED logic (for example, “circle a point of interest and come back”), an ESP32 showing the state. Passing criterion: the scenario works in SITL, the protocol and the behavior on companion failure are documented, a real flight happens only with a geofence and a pilot.

### What you should end up with and what to record
- **Position.** After a `POS_ONLY` target the vehicle flies to the point and hovers there, it does not come back: a position target does not need a stream. Record the arrival time and the position error at the end (`GLOBAL_POSITION_INT` against the target).
- **Velocity and timeout.** `VEL_ONLY` targets are sent at 5–10 Hz. Stop sending — after `GUID_TIMEOUT` (3 s by default) the vehicle stops and hovers. Record from the log the time from the last target to the stop: it should match the parameter.
- **Mode change by the pilot.** Switch the mode to LOITER in the middle of the task: the code sees this in `HEARTBEAT.custom_mode`, moves to the PILOT state and does not send a single further target. Check: in MAVLink Inspector after the switch there is no `SET_POSITION_TARGET_*` from the companion.
- **Geofence.** `FENCE_ENABLE = 1`, type — altitude and circle, radius 50 m, action RTL. Send a target outside the circle: depending on the version the target is rejected, or the vehicle flies to the boundary and goes into RTL. Record what exactly happened for you and keep the log — it is proof that the protection works even without your code.

The lab counts as done when takeoff and a position target are executed in SITL, velocity targets are sent at 5–10 Hz and the timeout is tested on purpose with the timing from the log, the code stops sending targets when the pilot changes the mode, and the geofence is enabled and tested.

## diagnostics
- **Symptom:** the vehicle does not respond to targets
  - Possible cause: not GUIDED, not armed, `type_mask` ignores the fields you need.
  - What to do: check the mode and armed state in the heartbeat, the mask, `STATUSTEXT`.
- **Symptom:** it flies up instead of down (or the other way around)
  - Possible cause: the sign of Z in NED.
  - What to do: Z down is positive; climbing is a negative Z.
- **Symptom:** it hovers after a couple of seconds even though the command was sent
  - Possible cause: the velocity target was sent once, the timeout fired.
  - What to do: send it regularly (5–10 Hz).
- **Symptom:** it stops at a boundary without reaching the target
  - Possible cause: the geofence or the `WPNAV_*` limits.
  - What to do: check `FENCE_*` and the FC messages — this is a protection, not a bug.

## references
- Copter Commands in Guided Mode — ArduPilot Dev | https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html | primary | A
- MAVLink SET_POSITION_TARGET_LOCAL_NED (common.xml) | https://mavlink.io/en/messages/common.html#SET_POSITION_TARGET_LOCAL_NED | primary | A
- Guided Mode — ArduPilot Copter | https://ardupilot.org/copter/docs/ac2_guidedmode.html | primary | A

## checklist
- All targets go to SITL first
- The sign of Z in NED is checked
- Velocity targets are sent regularly, the timeout is tested on purpose
- The code respects a mode change by the pilot
- The geofence is enabled, the pilot has a switch set to LOITER/RTL
- The behavior on companion failure is documented
