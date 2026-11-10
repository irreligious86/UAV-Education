---
id: mav-sdk
title: "Libraries on top of MAVLink: pymavlink, MAVSDK, MAVROS — what and when"
level: L3
readingTime: 40 min
firmware: ArduPilot · PX4
status: published
added: 2026-11-08
tags:
  - MAVSDK
  - pymavlink
  - MAVROS
  - async
  - architecture
related:
  - mav-services
  - px4-ros2
  - ap-companion
next:
  - per-tracking
source: content/companion/mav-sdk.md
source_hash: 1c170941d38e
---

## summary
After four “on the wire” modules you can choose a tool deliberately. pymavlink is direct access to every message; MAVSDK gives you ready-made actions (`arm`, `takeoff`, `mission.upload`, offboard) on top of the same microservices, an asynchronous API and a C++ server; MAVROS is a MAVLink ↔ ROS bridge; DroneKit is historical and unmaintained. This module compares them by layer, shows the same mission in pymavlink and MAVSDK, takes apart MAVSDK's asynchronous model (subscriptions, cancellation, timeouts) and what happens on a link loss at each level. Lab: a mission and an offboard flight through MAVSDK in SITL, checking the behavior when the link drops.

## theory
### Layers
| Layer | What it gives you | What it doesn't | When to use it |
|---|---|---|---|
| Raw protocol (mav-protocol) | everything | nothing ready-made | a driver on an MCU, your own dialect, debugging |
| **pymavlink** | codec, connections, `recv_match`, tlog | the dialogue logic (missions, ACK, retries — on you) | scripts, log analysis, tests, non-standard messages |
| **MAVSDK** (C++, Python, …) | actions and microservices: action, telemetry, mission, offboard, param, ftp, camera, gimbal | exotic firmware messages (possible through `mavlink_passthrough`) | companion applications, automated flight tests |
| **MAVROS** | MAVLink ↔ ROS 1/2 topics/services, TF, setpoints | ROS independence; overhead | a ROS-based system with ArduPilot; for PX4 + ROS 2, uXRCE-DDS is preferred (the px4-ros2 module) |
| DroneKit-Python | — | not developed, problems with modern Python and firmware | reading old code only |

All the upper layers implement the same dialogues you wrote by hand: `mission.upload_mission()` is, inside, MISSION_COUNT/REQUEST_INT/ITEM_INT/ACK with retries. You need to understand the lower layer to read the tlog when the upper layer says “timeout.”

### MAVSDK: how it works
MAVSDK is a C++ core; the `mavsdk` Python package starts a bundled `mavsdk_server` (gRPC) and talks to it. Hence: (1) the API is asynchronous (`asyncio`); (2) telemetry streams are async generators; (3) errors are exceptions with the plugin's result code (`ActionError`, `MissionError`) — the same meaning as `MAV_RESULT`.

```python
import asyncio
from mavsdk import System
from mavsdk.mission import MissionItem, MissionPlan

async def main():
    drone = System()
    await drone.connect(system_address="udpin://0.0.0.0:14540")    # older releases: "udp://:14540"
    async for state in drone.core.connection_state():
        if state.is_connected:
            break
    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            break
    items = [MissionItem(lat, lon, 20, 5, True, float("nan"), float("nan"),
                         MissionItem.CameraAction.NONE, float("nan"), float("nan"),
                         float("nan"), float("nan"), float("nan"), MissionItem.VehicleAction.NONE)
             for lat, lon in [(47.3978, 8.5456), (47.3982, 8.5460), (47.3980, 8.5465)]]
    await drone.mission.upload_mission(MissionPlan(items))
    await drone.action.arm()
    await drone.mission.start_mission()
    async for p in drone.mission.mission_progress():
        print(f"{p.current}/{p.total}")
        if p.current == p.total:
            break
    await drone.action.return_to_launch()

asyncio.run(main())
```

The `MissionItem` constructor changes between MAVSDK versions (fields get added) — check the documentation for the version you have installed; that's the normal price of a high-level API.

### Async without surprises
- **Subscriptions are endless**: `async for x in telemetry.position()` won't end on its own. The way out is a `break` on a condition, or a separate task that you cancel.
- **Timeouts are your job**: “wait until GPS is ok” without `asyncio.wait_for(..., timeout)` will hang forever on a vehicle without GPS.
- **Parallel tasks**: telemetry, logging and control are separate `asyncio.create_task`s; an error in a task whose result is never `await`ed is lost silently.
- **One system — one owner**: two MAVSDK processes on the same port mean two mavsdk_servers with the same identifiers; separate them with a router and different compids.

### Offboard and GUIDED
High-level control from the companion: in PX4 — Offboard mode (MAVSDK `offboard.set_velocity_ned(...)`, then `offboard.start()`; setpoints must be sent continuously at > 2 Hz, otherwise PX4 exits Offboard on timeout), in ArduPilot — GUIDED with `SET_POSITION_TARGET_LOCAL_NED` (MAVSDK offboard also works with ArduPilot through the same messages; support for the set of fields may differ). The safety rule from the comp-intro module: the companion advises, the autopilot decides; if the companion goes silent, the vehicle must switch to safe behavior on its own — and this is verified by a test, not by faith.

### What happens on a link loss
| Level | Behavior |
|---|---|
| pymavlink | `recv_match` returns None on timeout; the decision is yours |
| MAVSDK | `connection_state` → `is_connected = False` (on loss of heartbeat, ~3 s); actions fail with an error; offboard setpoints don't get through |
| Autopilot | GCS failsafe (if enabled and the link is with the GCS), exit from Offboard/GUIDED on setpoint timeout (PX4 `COM_OF_LOSS_T`, ArduPilot — `GUID_TIMEOUT` for velocity/acceleration setpoints) |

Design it so that safety is provided by the lower level (the autopilot), and the upper level only restores operation.

{{diagram:mav-sdk-layers|pymavlink, MAVSDK and MAVROS are different levels of abstraction over the same MAVLink.}}

## practice
### Step 1. One mission, two tools
Upload the same 5-waypoint mission to PX4 SITL (or ArduPilot SITL) twice: with your own client from mav-services (pymavlink) and through MAVSDK. Record a tlog of both sessions (MAVProxy or mavlink-router) and compare the message sequences: what does MAVSDK send in addition (version requests, intervals, `MISSION_CLEAR_ALL`)?

### Step 2. Mission flight with progress
The script above: arm, mission, progress, RTL. Add timeouts to every wait and CSV telemetry recording in a separate task.

### Step 3. Offboard square
NED velocities for 5 s in each of four directions in Offboard (PX4) or GUIDED (ArduPilot). Then “kill” the script in the middle of the square (`kill -9`) and record from the log how long it took and which mode the autopilot switched to. Compare with the value of the timeout parameter.

### Step 4. Link drop
Between SITL and the script, apply `tc netem loss 100%` for 5 s during the mission. What did MAVSDK do (`connection_state`), what did the autopilot do, and did the script recover after the link came back without a restart? Improve the script so it recovers.

The lab is passed when you have the tlog comparison of the two clients, a mission with progress and timeouts, an offboard square with the “killed” script test, and a link-drop scenario with recovery.

## diagnostics
- **Symptom:** a MAVSDK script hangs at startup
  - Possible cause: waiting for `health` without a timeout on a vehicle without GPS/home; the wrong connection address (udpin vs udpout, syntax version).
  - What to do: `asyncio.wait_for`; check the address and the MAVSDK version.
- **Symptom:** PX4 exits Offboard immediately
  - Possible cause: setpoints weren't sent before `offboard.start()`, or they're sent less often than 2 Hz.
  - What to do: send an initial setpoint before starting; a separate task at 10–20 Hz.
- **Symptom:** `upload_mission` sometimes fails with a timeout over the radio
  - Possible cause: losses on a slow link, too few retries by default.
  - What to do: upload over a fast link/through the companion; look at the tlog to see which item was lost.
- **Symptom:** two scripts interfere with each other
  - Possible cause: both occupy the same port or the same compid.
  - What to do: a router with separate endpoints, different compids.

## references
- MAVSDK — Guide and Python API | https://mavsdk.mavlink.io/main/en/ | primary | A
- MAVSDK-Python (source, examples) | https://github.com/mavlink/MAVSDK-Python | primary | A
- MAVROS | https://github.com/mavlink/mavros | primary | A
- PX4 — Offboard mode (timeouts, COM_OF_LOSS_T) | https://docs.px4.io/main/en/flight_modes/offboard.html | primary | A
- ArduPilot — Copter commands in Guided mode | https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html | primary | A

## checklist
- I choose the layer (raw protocol, pymavlink, MAVSDK, MAVROS) for the task and explain why
- I understand the MAVSDK architecture (server, gRPC, async) and where to look for an error
- I write async code with timeouts and task cancellation
- I control the vehicle in Offboard/GUIDED and know the setpoint timeouts
- I check the system's behavior on a link loss and on the “death” of a script
