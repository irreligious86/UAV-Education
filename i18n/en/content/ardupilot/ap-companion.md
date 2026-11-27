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

{{diagram:guided-silence-tree|Only velocity, acceleration and angle targets have a timeout: after a position target, a companion that goes silent leaves the aircraft flying to the point and hovering there.}}

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
```bash
./run_sitl.sh 8 > sitl8.log 2>&1 &      # arducopter -S --model + -I 8 -w --defaults copter.parm --home -35.363261,149.165230,584,353
sleep 2
mavproxy.py --master=tcp:127.0.0.1:5840 --out=udp:127.0.0.1:14650 --out=udp:127.0.0.1:14651 \
  --streamrate=-1 --daemon --non-interactive --state-basedir=./mp8 > mavproxy8.log 2>&1 &
sleep 4
python3 -u companion_lab.py udpin:127.0.0.1:14650
```

### Step 2. A velocity target, sent regularly
```python
"""ap-companion lab: ArduCopter 4.7.2 SITL -> MAVProxy (router) -> companion (this script, compid 191).
Param audit, GUIDED arm/takeoff with COMMAND_ACK, velocity stream at 5 Hz, then silence:
measure time from the last setpoint to the stop (GUID_TIMEOUT)."""
import math, sys, time
from pymavlink import mavutil

URL = sys.argv[1] if len(sys.argv) > 1 else "udpin:127.0.0.1:14650"
m = mavutil.mavlink_connection(URL, source_system=1, source_component=191)  # MAV_COMP_ID_ONBOARD_COMPUTER
hb = m.wait_heartbeat(timeout=20)
print(f"FC heartbeat: sysid={m.target_system} compid={m.target_component} autopilot={hb.autopilot} type={hb.type}")
L = mavutil.mavlink

def param(name, timeout=3):
    m.mav.param_request_read_send(m.target_system, m.target_component, name.encode(), -1)
    t = time.time() + timeout
    while time.time() < t:
        p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.5)
        if p and p.param_id == name:
            return p.param_value
    return None

print("--- param audit (4.7.2 names; None = no such parameter)")
for n in ["SERIAL1_PROTOCOL", "SERIAL1_BAUD", "SERIAL2_PROTOCOL", "SERIAL2_BAUD", "MAV1_EXT_STAT", "MAV2_POSITION",
          "MAV_SYSID", "MAV_GCS_SYSID", "SYSID_THISMAV", "SR0_EXT_STAT", "GUID_TIMEOUT", "GUID_OPTIONS",
          "FS_GCS_ENABLE", "FS_GCS_TIMEOUT", "DDS_ENABLE"]:
    v = param(n)
    print(f"{n:17s} = {v if v is None else round(v, 3)}")

def cmd(command, *p, timeout=3):
    m.mav.command_long_send(m.target_system, m.target_component, command, 0, *(list(p) + [0] * (7 - len(p))))
    a = m.recv_match(type="COMMAND_ACK", blocking=True, timeout=timeout,
                     condition=f"COMMAND_ACK.command=={command}")
    return None if a is None else a.result

state = {"mode": "", "armed": False, "alt": 0.0, "v": 0.0}
def pump(dt=0.0):
    end = time.time() + dt
    while True:
        msg = m.recv_match(blocking=dt > 0, timeout=max(0.01, end - time.time()))
        if msg is not None:
            t = msg.get_type()
            if t == "HEARTBEAT" and msg.get_srcComponent() == 1:
                state["mode"] = mavutil.mode_string_v10(msg)
                state["armed"] = bool(msg.base_mode & L.MAV_MODE_FLAG_SAFETY_ARMED)
            elif t == "LOCAL_POSITION_NED":
                state["alt"], state["v"] = -msg.z, math.hypot(msg.vx, msg.vy)
        if time.time() >= end and msg is None:
            return

# 4.7: MAVn_* stream rates are 0 by default -> ask for the message we control by, 10 Hz
print("SET_MESSAGE_INTERVAL LOCAL_POSITION_NED 10 Hz ACK =", cmd(L.MAV_CMD_SET_MESSAGE_INTERVAL, 32, 100000))
print("--- wait for EKF / GPS (pre-arm)")
t0 = time.time()
while time.time() - t0 < 90:
    m.set_mode(m.mode_mapping()["GUIDED"]); pump(1.0)
    if state["mode"] == "GUIDED":
        r = cmd(L.MAV_CMD_COMPONENT_ARM_DISARM, 1)
        if r == 0:
            break
print(f"GUIDED + arm ACK=0 after {time.time()-t0:.1f} s, mode={state['mode']}")
print("takeoff ACK =", cmd(L.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 10))
t0 = time.time()
while state["alt"] < 9.5 and time.time() - t0 < 30:
    pump(0.2)
print(f"alt {state['alt']:.1f} m after {time.time()-t0:.1f} s")

VEL_ONLY = 0b0000_1111_1100_0111
print("--- 2 m/s north at 5 Hz for 8 s, then silence")
t0 = time.time(); last = 0
while time.time() - t0 < 8:
    if state["mode"] != "GUIDED":
        print("pilot took over"); break
    m.mav.set_position_target_local_ned_send(0, m.target_system, m.target_component, L.MAV_FRAME_LOCAL_NED,
                                             VEL_ONLY, 0, 0, 0, 2.0, 0, 0, 0, 0, 0, 0, 0)
    last = time.time(); pump(0.2)
print(f"speed at last setpoint: {state['v']:.2f} m/s")
t_dec = t_stop = None; trace = []
while time.time() - last < 10:
    pump(0.1); dt = time.time() - last; trace.append((round(dt, 2), round(state["v"], 2)))
    if t_dec is None and state["v"] < 1.8: t_dec = dt
    if t_stop is None and state["v"] < 0.2: t_stop = dt
    if t_stop and dt > t_stop + 1: break
open("guided_timeout_trace.csv", "w").write("t_s,v_ms\n" + "".join(f"{a},{b}\n" for a, b in trace))
print("t after last setpoint, s : " + " ".join(f"{a:4.1f}" for a, _ in trace[4::5]))
print("ground speed, m/s        : " + " ".join(f"{b:4.2f}" for _, b in trace[4::5]))
print(f"speed < 1.8 m/s after {t_dec:.1f} s; < 0.2 m/s after {t_stop:.1f} s from the last setpoint; mode={state['mode']}")
print("--- pilot takeover: GCS (sysid 255, port 14651) switches to LOITER 3 s into a new velocity stream")
import threading
def gcs():
    g = mavutil.mavlink_connection("udpin:127.0.0.1:14651", source_system=255, source_component=190)
    g.wait_heartbeat(timeout=10); time.sleep(3.0)
    g.set_mode(g.mode_mapping()["LOITER"]); gcs.t = time.time()
threading.Thread(target=gcs, daemon=True).start()
t0 = time.time(); sent_after = 0; gcs.t = None; seen = None
while time.time() - t0 < 10:
    pump(0.2)
    if state["mode"] != "GUIDED":
        seen = seen or time.time()
        if time.time() - seen > 2: break
        continue                                   # PILOT state: read only, send nothing
    m.mav.set_position_target_local_ned_send(0, m.target_system, m.target_component, L.MAV_FRAME_LOCAL_NED,
                                             VEL_ONLY, 0, 0, 0, 0, 2.0, 0, 0, 0, 0, 0, 0)
    if gcs.t: sent_after += 1
print(f"mode {state['mode']} seen {seen - gcs.t:.2f} s after the GCS command; setpoints sent after it: {sent_after}")
m.set_mode(m.mode_mapping()["GUIDED"]); pump(1.0)
print("LAND ACK =", cmd(L.MAV_CMD_NAV_LAND, 0, 0, 0, 0, 0, 0, 0))
t0 = time.time()
while state["armed"] and time.time() - t0 < 60:
    pump(0.5)
print(f"disarmed after landing: {not state['armed']} ({time.time()-t0:.0f} s)")
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

### Step 6. ArduCopter 4.7.2 SITL run log
The stand (step 1 block: SITL -> MAVProxy router -> companion) and the lab script (step 2 block) were run; the Russian source explains every line of this output.

```text
FC heartbeat: sysid=1 compid=0 autopilot=3 type=2
--- param audit (4.7.2 names; None = no such parameter)
SERIAL1_PROTOCOL  = 2.0
SERIAL1_BAUD      = 57.0
SERIAL2_PROTOCOL  = 2.0
SERIAL2_BAUD      = 57.0
MAV1_EXT_STAT     = 0.0
MAV2_POSITION     = 0.0
MAV_SYSID         = 1.0
MAV_GCS_SYSID     = 255.0
SYSID_THISMAV     = None
SR0_EXT_STAT      = None
GUID_TIMEOUT      = 3.0
GUID_OPTIONS      = 0.0
FS_GCS_ENABLE     = 0.0
FS_GCS_TIMEOUT    = 5.0
DDS_ENABLE        = None
SET_MESSAGE_INTERVAL LOCAL_POSITION_NED 10 Hz ACK = 0
--- wait for EKF / GPS (pre-arm)
GUIDED + arm ACK=0 after 28.1 s, mode=GUIDED
takeoff ACK = 0
alt 9.5 m after 8.8 s
--- 2 m/s north at 5 Hz for 8 s, then silence
speed at last setpoint: 1.99 m/s
t after last setpoint, s :  0.7  1.2  1.7  2.2  2.7  3.2  3.7  4.2  4.7  5.2
ground speed, m/s        : 1.99 1.99 1.99 1.98 1.98 1.98 1.33 0.27 0.04 0.02
speed < 1.8 m/s after 3.5 s; < 0.2 m/s after 4.3 s from the last setpoint; mode=GUIDED
--- pilot takeover: GCS (sysid 255, port 14651) switches to LOITER 3 s into a new velocity stream
mode LOITER seen 0.08 s after the GCS command; setpoints sent after it: 0
LAND ACK = 0
disarmed after landing: True (13 s)
```

{{diagram:chart-ap-guided-silence-stop|The speed holds for the full 3 s of GUID_TIMEOUT after the last target and drops to zero in about a second of braking: below 0.2 m/s after 4.4 s.}}

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
