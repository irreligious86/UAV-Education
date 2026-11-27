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
from mavsdk.asyncio import Mavsdk, Configuration, ComponentType
from mavsdk.asyncio.plugins.action import ActionAsync
from mavsdk.asyncio.plugins.telemetry import TelemetryAsync
from mavsdk.asyncio.plugins.mission import MissionAsync, MissionItem, MissionPlan

async def main():
    cfg = Configuration.create_with_component_type(ComponentType.GROUND_STATION)
    async with Mavsdk(cfg) as sdk:
        await sdk.add_any_connection("udpin://0.0.0.0:14540")      # older gRPC package: drone.connect(...)
        drone = await sdk.first_autopilot(timeout_s=10.0)
        if drone is None:
            raise SystemExit("no autopilot in 10 s")
        tel, act, mis = TelemetryAsync(drone), ActionAsync(drone), MissionAsync(drone)
        async def ready():
            async for h in tel.subscribe_health():
                if h.is_global_position_ok and h.is_home_position_ok:
                    return
        await asyncio.wait_for(ready(), 120)                        # never wait without a timeout
        items = [MissionItem(latitude_deg=lat, longitude_deg=lon, relative_altitude_m=20, speed_m_s=5,
                             is_fly_through=True, vehicle_action=MissionItem.VehicleAction.NONE)
                 for lat, lon in [(47.3978, 8.5456), (47.3982, 8.5460), (47.3980, 8.5465)]]
        await mis.upload_mission(MissionPlan(items))
        await act.arm()
        await mis.start_mission()
        async for p in mis.subscribe_mission_progress():
            print(f"{p.current}/{p.total}")
            if p.current == p.total:
                break
        await act.return_to_launch()

asyncio.run(main())
```

The `MissionItem` constructor changes between MAVSDK versions (fields get added) — check the documentation for the version you have installed; that's the normal price of a high-level API.

{{diagram:mav-sdk-ap-startup-seq|A MAVSDK script against ArduCopter 4.7 first requests the streams (there are none by default), then waits for health from EKF_STATUS_REPORT, and on a mission upload loses seq 0 to home — hence the placeholder item.}}

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

{{diagram:mav-offboard-loss-timeline|After kill -9 of the script, PX4 leaves Offboard after 1 s, while ArduPilot keeps flying at the previous velocity for 3 s more and only then stops, staying in GUIDED.}}

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

### Step 5. MAVSDK 4.2.1 against ArduCopter 4.7.2 SITL (run log)
The Russian source walks through this run in detail (five ArduPilot pitfalls, decoded raw mission). Install, script and its real output:

```bash
python3 -m venv venv && ./venv/bin/pip install mavsdk==4.2.1 pymavlink
./venv/bin/python -c "import mavsdk; print(mavsdk.__version__)"
# 4.2.1
./venv/bin/python -c "from mavsdk import System; System()"
# TypeError: System is not constructed directly, get it from Mavsdk instead. Since v4, the 'mavsdk' package
# is the native MAVSDK binding ... To keep the old API, install 'mavsdk-grpc' ...
```

```python
"""MAVSDK-Python 4.x lab against ArduCopter 4.7.2 SITL: connect, health, GUIDED arm, takeoff,
telemetry subscription, mission upload + progress, RTL. Every wait has a timeout."""
import asyncio, json, sys, time
from mavsdk import log_subscribe, LogLevel
from mavsdk.asyncio import Mavsdk, Configuration, ComponentType
from mavsdk.asyncio.plugins.action import ActionAsync
from mavsdk.asyncio.plugins.telemetry import TelemetryAsync, FlightMode
from mavsdk.asyncio.plugins.mission import MissionAsync, MissionItem, MissionPlan, MissionError
from mavsdk.asyncio.plugins.mission_raw import MissionRawAsync
from mavsdk.asyncio.plugins.mavlink_direct import MavlinkDirectAsync, MavlinkMessage

URL = sys.argv[1] if len(sys.argv) > 1 else "tcpout://127.0.0.1:5830"
T0 = time.monotonic()
# keep only warnings/errors of the C++ core; print autopilot STATUSTEXT ourselves
log_subscribe(lambda lvl, msg, f, l: lvl < LogLevel.WARN)
def log(*a): print(f"[{time.monotonic()-T0:6.1f} s]", *a, flush=True)

async def first(gen, cond, timeout, what):
    """First item of an endless subscription that satisfies cond, or TimeoutError."""
    async def run():
        async for x in gen:
            if cond(x):
                return x
    try:
        return await asyncio.wait_for(run(), timeout)
    except asyncio.TimeoutError:
        raise TimeoutError(f"{what}: no result in {timeout} s") from None

async def main():
    cfg = Configuration.create_with_component_type(ComponentType.GROUND_STATION)
    async with Mavsdk(cfg) as sdk:
        log("MAVSDK", await sdk.version())
        await sdk.add_any_connection(URL)
        drone = await sdk.first_autopilot(timeout_s=10.0)
        if drone is None:
            raise TimeoutError("no autopilot in 10 s")
        log("autopilot:", (await drone.autopilot_type()).name, "sysid", await drone.get_system_id(),
            "vehicle:", (await drone.vehicle_type()).name)
        tel, act, mis = TelemetryAsync(drone), ActionAsync(drone), MissionAsync(drone)
        # ArduCopter 4.7: MAVn_* stream rates default to 0 -> ask for what we subscribe to
        await tel.set_rate_health(2.0)        # SYS_STATUS + EKF_STATUS_REPORT
        await tel.set_rate_position(5.0)      # GLOBAL_POSITION_INT
        # Mission progress comes from MISSION_CURRENT (id 42): no MAVSDK set_rate_* for it -> raw command
        ack = await MavlinkDirectAsync(drone).send_command(MavlinkMessage(
            message_name="COMMAND_LONG", system_id=245, component_id=190, target_system_id=1, target_component_id=1,
            fields_json=json.dumps({"target_system": 1, "target_component": 1, "command": 511,   # SET_MESSAGE_INTERVAL
                                    "param1": 42, "param2": 500000})))                       # 42 = MISSION_CURRENT, 2 Hz
        log("rates requested: health 2 Hz, position 5 Hz, MISSION_CURRENT 2 Hz -> ack", json.loads(ack.fields_json)["result"])
        last = None
        def ready(h):
            nonlocal last
            k = (h.is_global_position_ok, h.is_home_position_ok, h.is_armable)
            if k != last:
                log(f"health: global_pos={k[0]} home={k[1]} armable={k[2]}"); last = k
            return k[0] and k[1]
        await first(tel.subscribe_health(), ready, 120, "health")

        home = await tel.home()
        wp = lambda dn: MissionItem(latitude_deg=home.latitude_deg + dn / 111_320, longitude_deg=home.longitude_deg,
                                        relative_altitude_m=20, speed_m_s=5, is_fly_through=True,
                                        vehicle_action=MissionItem.VehicleAction.NONE)
        # ArduPilot keeps seq 0 for home and overwrites it: without a placeholder the first point is lost
        plan = MissionPlan([wp(0)] + [wp(dn) for dn in (40, 80, 120)])
        t = time.monotonic(); await mis.upload_mission(plan)
        log(f"mission uploaded: {len(plan.mission_items)} items in {time.monotonic()-t:.2f} s")
        try:
            await mis.download_mission()
        except MissionError as e:
            log("Mission.download_mission ->", e.result.name)   # ArduPilot item 0 = home
            await mis.upload_mission(plan)                       # the failed download dropped the plan: upload again
            log("re-uploaded after the failed download")
        raw = await MissionRawAsync(drone).download_mission()
        for it in raw:
            log(f"  raw seq={it.seq} frame={it.frame} cmd={it.command} x={it.x} y={it.y} z={it.z:.1f}")

        await act.set_takeoff_altitude(10.0)
        await act.arm(); log("armed in", FlightMode(await tel.flight_mode()).name)
        await act.takeoff(); log("takeoff accepted, mode now", FlightMode(await tel.flight_mode()).name, "(= ArduCopter GUIDED)")
        p = await first(tel.subscribe_position(), lambda p: p.relative_altitude_m > 9.0, 40, "climb to 9 m")
        log(f"altitude {p.relative_altitude_m:.1f} m reached")

        await mis.start_mission(); log("mission started, mode:", FlightMode(await tel.flight_mode()).name, "(= AUTO)")
        n = 0
        async def progress():
            async for pr in mis.subscribe_mission_progress():
                log(f"progress {pr.current}/{pr.total}")
                if pr.current == pr.total:
                    return
        async def pos_log():
            nonlocal n
            async for p in tel.subscribe_position():
                n += 1
        async def raw_current():
            async for msg in MavlinkDirectAsync(drone).subscribe_message("MISSION_CURRENT"):
                f = json.loads(msg.fields_json)
                if f["seq"] != getattr(raw_current, "seq", None):
                    raw_current.seq = f["seq"]; log(f"MISSION_CURRENT seq={f['seq']} total={f.get('total')} state={f.get('mission_state')}")
        logger = asyncio.create_task(pos_log()); rc = asyncio.create_task(raw_current())
        await asyncio.wait_for(progress(), 150); rc.cancel()
        logger.cancel()
        log(f"position samples received during mission: {n}")
        await act.return_to_launch(); log("RTL sent, mode:", FlightMode(await tel.flight_mode()).name)
        await first(tel.subscribe_armed(), lambda a: not a, 120, "disarm after RTL")
        log("landed and disarmed")

asyncio.run(main())
```

```text
[   0.0 s] MAVSDK v4.2.1
[   0.9 s] autopilot: ARDUPILOT sysid 1 vehicle: MULTICOPTER
[   1.1 s] rates requested: health 2 Hz, position 5 Hz, MISSION_CURRENT 2 Hz -> ack 0
[   1.9 s] health: global_pos=False home=False armable=False
[  20.0 s] health: global_pos=False home=True armable=False
[  23.5 s] health: global_pos=False home=True armable=True
[  42.0 s] health: global_pos=True home=True armable=True
[  42.1 s] mission uploaded: 4 items in 0.09 s
[09:25:53|Error] Waypoint frame 0 not supported (mission_impl.cpp:709)
[  42.1 s] Mission.download_mission -> UNSUPPORTED
[  42.2 s] re-uploaded after the failed download
[  42.3 s]   raw seq=0 frame=0 cmd=16 x=-353632610 y=1491652299 z=584.1
[  42.3 s]   raw seq=1 frame=0 cmd=178 x=0 y=0 z=0.0
[  42.3 s]   raw seq=2 frame=3 cmd=16 x=-353629017 y=1491652299 z=20.0
[  42.3 s]   raw seq=3 frame=0 cmd=178 x=0 y=0 z=0.0
[  42.3 s]   raw seq=4 frame=3 cmd=16 x=-353625424 y=1491652299 z=20.0
[  42.3 s]   raw seq=5 frame=0 cmd=178 x=0 y=0 z=0.0
[  42.3 s]   raw seq=6 frame=3 cmd=16 x=-353621830 y=1491652299 z=20.0
[  42.3 s]   raw seq=7 frame=0 cmd=178 x=0 y=0 z=0.0
[  42.3 s] armed in STABILIZED
[  42.3 s] takeoff accepted, mode now OFFBOARD (= ArduCopter GUIDED)
[  50.8 s] altitude 9.2 m reached
[  50.8 s] mission started, mode: MISSION (= AUTO)
[  51.0 s] progress 1/4
[  51.0 s] MISSION_CURRENT seq=2 total=7 state=3
[  61.5 s] progress 2/4
[  61.5 s] MISSION_CURRENT seq=4 total=7 state=3
[  69.5 s] progress 3/4
[  69.5 s] MISSION_CURRENT seq=6 total=7 state=3
[  80.0 s] progress 4/4
[  80.0 s] position samples received during mission: 146
[  80.0 s] RTL sent, mode: RETURN_TO_LAUNCH
[ 137.0 s] landed and disarmed
```

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
