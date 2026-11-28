---
id: mav-sdk
title: "Libraries on top of MAVLink: pymavlink, MAVSDK, MAVROS — what to use when"
level: L3
readingTime: 55 min
firmware: ArduPilot 4.7 (checked against 4.7.3; lab recorded on SITL 4.7.2) · PX4 1.18 (parameters checked against v1.18.0) · MAVSDK 4.2.1 · pymavlink 2.4.50
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
source_hash: bc8d286c81e2
---

## summary
After four modules "on the wire" you can choose your tool deliberately. pymavlink gives direct access to every message; MAVSDK gives ready-made actions (`arm`, `takeoff`, `upload_mission`, offboard) on top of the same microservices; MAVROS is a MAVLink ↔ ROS bridge; DroneKit is historical and unmaintained. Since autumn 2026, MAVSDK for Python has a new architecture: the `mavsdk` 4.x package is a native binding to the C++ core, with no gRPC and no `mavsdk_server`, and with its own API; the old code lives on in the `mavsdk-grpc` package. The module compares the libraries by layer, covers the MAVSDK 4 asynchronous model (subscriptions, cancellation, timeouts), five pitfalls of MAVSDK + ArduPilot 4.7 found by running it in SITL, and what happens on a link loss at each level. The lab: a script on MAVSDK 4.2.1 against ArduCopter 4.7.2 SITL: connection, health, mission, takeoff in GUIDED, progress and RTL, with an analysis of the raw mission contents.

## theory
### Layers
| Layer | What it gives you | What it does not | When to use it |
|---|---|---|---|
| Raw protocol (mav-protocol) | everything | nothing ready-made | a driver on an MCU, your own dialect, debugging |
| **pymavlink** | codec, connections, `recv_match`, tlog | the dialog logic (missions, ACKs, retries are on you) | scripts, log analysis, tests, non-standard messages |
| **MAVSDK** (C++, Python, Kotlin, …) | actions and microservices: action, telemetry, mission, offboard, param, ftp, camera, gimbal | exotic firmware messages (through the `MavlinkDirect` plugin; `MavlinkPassthrough` is deprecated) | applications on a companion, automated flight tests |
| **MAVROS** | MAVLink ↔ ROS 1/2 topics/services, TF, setpoints | ROS independence; overhead | a ROS system with ArduPilot; for PX4 + ROS 2, uXRCE-DDS is preferred (the px4-ros2 module) |
| DroneKit-Python | — | not developed, problems with modern Python and firmware | reading old code only |

All the upper layers implement the same dialogs you wrote by hand: inside, `upload_mission()` is MISSION_COUNT/REQUEST_INT/ITEM_INT/ACK with retries. You need to understand the lower layer to read a tlog when the upper layer says "timeout" or, worse, silently does the wrong thing.

{{lesson:mav-services|The mission, parameter and command dialogs with ACKs and retries: what MAVSDK hides inside; without them you cannot read a tlog.}}

### MAVSDK 4: a native binding instead of gRPC
Up to and including version 3.x, `pip install mavsdk` installed MAVSDK-Python: an asynchronous wrapper that launched a bundled `mavsdk_server` process and talked to it over gRPC. Since MAVSDK v4, the `mavsdk` name on PyPI belongs to a different product: a native binding that calls the C++ core directly inside the Python process (ctypes) through the C wrapper `libcmavsdk`. PyPI releases: 3.17.4 on September 17, 2026 (the last of the old kind), 4.0.0 on September 22, 2026, 4.2.1 on November 17, 2026 (the lab was recorded on it; the core reports `MAVSDK v4.2.1`), 4.3.0 on November 27, 2026. The old gRPC client continues to be developed under the name `mavsdk-grpc` (imported as `mavsdk_grpc`, also 4.2.1).

What this means in practice:

- **No second process.** No `mavsdk_server`, no port 50051, no `grpcio` dependency. Fewer moving parts on the companion, but also less isolation: a crash in the core takes down the Python process.
- **Two interfaces from one package.** `mavsdk` is a synchronous, callback-based API, `mavsdk.asyncio` an asynchronous one. The asyncio wrapper moves blocking calls into a thread pool (`run_in_executor`), and callbacks from the core arrive on its own thread and are handed to the event loop with `call_soon_threadsafe` (read from the code of package 4.2.1, `mavsdk/asyncio/plugins/*`).
- **System discovery is separate from connecting.** `add_any_connection(url)` only opens the channel; the vehicle shows up through `first_autopilot(timeout_s)` or `get_systems()`. This matters when there is more than one vehicle on the network.
- **Plugins are constructed explicitly.** `drone.action.arm()` becomes `ActionAsync(drone).arm()`.
- **Subscribing and one-off reads are separate.** In the gRPC package, `telemetry.position()` was an endless stream; in 4.x the stream is `subscribe_position()`, and `position()` returns the latest value once. A loop `async for p in telemetry.position()` carried over "as is" will fail.

Old code does not break silently: the 4.x package intercepts imports of the old modules and calls to `System()` and prints a hint (checked: `TypeError: System is not constructed directly, get it from Mavsdk instead…`). Three ways forward: change the import to `import mavsdk_grpc as mavsdk` (touch nothing else), pin `mavsdk<4` in `requirements.txt` (no more updates), or rewrite on the native API, which wins on a companion: no extra process, and a synchronous variant for simple utilities.

| Before (gRPC, `mavsdk<4`) | After (`mavsdk.asyncio`, 4.x) |
|---|---|
| `drone = System()` | `sdk = Mavsdk(Configuration.create_with_component_type(ComponentType.GROUND_STATION))` |
| `await drone.connect(system_address=url)` | `await sdk.add_any_connection(url)` |
| implicit inside `connect()` | `drone = await sdk.first_autopilot(timeout_s)` → `System` or `None` |
| `drone.core.connection_state()` | `drone.is_connected_state()` |
| `drone.action`, `drone.telemetry` | `ActionAsync(drone)`, `TelemetryAsync(drone)` |
| `async for p in drone.telemetry.position()` | `async for p in tel.subscribe_position()` |
| `e._result.result` in `ActionError` | `e.result` |

The same scenario as in the old edition of this module (a three-waypoint mission, arm, start, progress, RTL), on the 4.x API:

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

In 4.x the `MissionItem` constructor takes keyword arguments with defaults (NaN for "not set"), so the long positional call from the gRPC version is no longer needed. This is the path for PX4; for ArduPilot this code is not enough, see the next section.

### MAVSDK and ArduPilot 4.7: five pitfalls
MAVSDK was historically written around PX4, and ArduPilot is supported by `if (autopilot == ArduPilot)` branches in the core. Running this module's lab against ArduCopter 4.7.2 SITL turned up five places where "works in the example" and "works with ArduPilot" diverge. All five are findings from the run, confirmed in the source of MAVSDK v4.2.1 and ArduPilot Copter-4.7.2.

**1. Telemetry streams are off by default.** In 4.7 the stream rate parameters moved from `SRn_*` to `MAVn_*` (`MAV1_EXT_STAT`, `MAV1_POSITION`, …), and for Copter their defaults are 0 (`libraries/GCS_MAVLink/GCS_MAVLink_Parameters.cpp`, the `APM_BUILD_COPTER_OR_HELI` block). A ground station requests the streams itself, so in Mission Planner everything looks "as before". A MAVSDK script that does not request them gets almost nothing but HEARTBEAT from ArduCopter; the first run of the lab without requests sat for 120 s with `global_pos=False`. The fix is to call `set_rate_*` before subscribing: `set_rate_health(2)` requests SYS_STATUS and EKF_STATUS_REPORT, `set_rate_position(5)` requests GLOBAL_POSITION_INT. For messages that have no `set_rate_*` of their own (MISSION_CURRENT, which mission progress depends on), use `MAV_CMD_SET_MESSAGE_INTERVAL` (511) through `MavlinkDirectAsync.send_command`. A request applies to the channel it arrived on.

**2. On ArduPilot, position health comes from the EKF, not from the GPS.** For ArduPilot, `is_global_position_ok` is computed from the EKF_STATUS_REPORT flags: while the vehicle is disarmed, `EKF_POS_HORIZ_ABS` or the predicted `EKF_PRED_POS_HORIZ_ABS` is enough; after arming, only `EKF_POS_HORIZ_ABS`, and not in constant position mode (`telemetry_impl.cpp`, `process_ekf_status_report`). That is more correct than the GPS flag in SYS_STATUS (ArduPilot sets it as soon as the receiver is alive), but it means: without the EKF_STATUS_REPORT stream the flag is based on the GPS, and with it, it honestly waits for the EKF. In the run, `home=True` came at 20.0 s, `armable` (the `MAV_SYS_STATUS_PREARM_CHECK` bit) at 23.5 s, and `global_pos` at 42.0 s, after "EKF3 IMU0 is using GPS".

**3. Item seq 0 is home.** ArduPilot keeps the home position in mission item 0 and overwrites whatever was uploaded there. The Mission plugin sends the first `MissionItem` to exactly seq 0, so without a placeholder item the first waypoint is lost: in the first run, two of the three waypoints were flown, and seq 0 contained the home coordinates when downloaded. The fix is to put a placeholder first (for example, a copy of the first waypoint) or to work through `MissionRaw` with an explicit home.

**4. Downloading a mission with the Mission plugin is not supported.** On ArduPilot, `download_mission()` returns `UNSUPPORTED` (core log: `Waypoint frame 0 not supported`: home in seq 0 is stored in the MAV_FRAME_GLOBAL frame). The raw path, `MissionRawAsync(drone).download_mission()`, works and shows the truth: every `MissionItem` with a speed has become two items, `MAV_CMD_NAV_WAYPOINT` (16) and `MAV_CMD_DO_CHANGE_SPEED` (178), so the 4 plan items became 8 items. An unpleasant detail: after the failed `download_mission()` the plugin forgot the uploaded plan, and progress showed `-1/0` even though MISSION_CURRENT kept coming; uploading again restored normal progress `1/4 … 4/4` (a finding from the run).

**5. The modes have PX4 names.** MAVSDK telemetry reports `FlightMode` from the PX4 vocabulary: ArduCopter's GUIDED arrives as `OFFBOARD`, AUTO as `MISSION`, STABILIZE as `STABILIZED`, and `Hold` becomes BRAKE when you switch to it (not LOITER, which takes the vertical from the throttle stick and descends without a pilot; a comment in `system_impl.cpp`). `action.arm()` arms in the current mode, and on ArduPilot `action.takeoff()` itself switches to GUIDED and sends `MAV_CMD_NAV_TAKEOFF` with the altitude from `set_takeoff_altitude()` (`action_impl.cpp`, `takeoff_async_apm`). If the vehicle is in AUTO, RTL or LAND, `arm()` first switches it to Hold, which is BRAKE.

{{diagram:mav-sdk-ap-startup-seq|A MAVSDK script against ArduCopter 4.7 first requests the streams (there are none by default), then waits for health from EKF_STATUS_REPORT, and on mission upload loses seq 0 to home, hence the placeholder item.}}

### Asynchrony without surprises
- **Subscriptions are endless**: `async for x in tel.subscribe_position()` never ends on its own. Ways out: a `break` on a condition, `asyncio.wait_for` around the coroutine with the loop, or a separate task that you cancel. When you leave the generator, the 4.x wrapper unsubscribes in the core by itself (a `finally` block with `unsubscribe_*`).
- **Timeouts are yours**: "wait until GPS is OK" without `asyncio.wait_for(..., timeout)` hangs forever on a vehicle without GPS, or, as pitfall 1 above showed, on ArduPilot without the requested streams.
- **The queue is unbounded**: every subscription in the 4.x wrapper is an `asyncio.Queue()` with no limit (read from the package code). A slow consumer of a 50 Hz stream does not lose data; it piles it up in memory and processes older and older values. If you only need the latest sample, read it with the one-off method (`await tel.position()`) or drain the queue yourself.
- **Concurrent tasks**: telemetry, logging and control are separate `asyncio.create_task` calls; an exception in a task whose result nobody `await`s is lost silently.
- **One system, one owner of the channel**: two processes on the same UDP port or the same SITL TCP port get in each other's way (the SITL TCP port accepts one client: the second script in the run got `no autopilot in 10 s`). Separate the clients with a router and different compids (`mav-routing`).

### Offboard and GUIDED
High-level control from a companion: in PX4, Offboard mode (`OffboardAsync.set_velocity_ned(...)`, then `start()`; setpoints must be streamed continuously faster than 2 Hz, otherwise PX4 leaves Offboard on the timeout); in ArduPilot, GUIDED with `SET_POSITION_TARGET_LOCAL_NED` (the MAVSDK Offboard plugin also works with ArduPilot through the same messages, and for ArduPilot `FlightMode.OFFBOARD` is GUIDED; support for particular field combinations may differ). The safety rule from the comp-intro module: the companion advises, the autopilot decides; when the companion goes silent, the vehicle must fall back to safe behavior on its own, and that is verified by a test, not taken on faith.

{{lesson:ap-companion|GUIDED timeouts by target type, the port parameters, and measuring the stop after the companion goes silent, on ArduPilot 4.7.2 SITL.}}

### What happens on a link loss
| Level | Behavior |
|---|---|
| pymavlink | `recv_match` returns None on timeout; what to do is your decision |
| MAVSDK 4.x | `is_connected_state()` reports `False` after the autopilot heartbeat disappears; actions fail with an error; offboard setpoints do not get through |
| Autopilot | GCS failsafe (if enabled and the link is to the GCS); PX4 leaves Offboard after `COM_OF_LOSS_T` (default 1 s) into the `COM_OBL_RC_ACT` mode (default 0, Position; without RC, the `NAV_RCL_ACT` action, default 2, Return); ArduPilot stays in GUIDED and after `GUID_TIMEOUT` (default 3 s; only for velocity, acceleration and attitude targets) zeroes the target: with velocity targets the vehicle stops, with attitude targets it levels out |

Design it so that safety is provided by the lower level (the autopilot), and the upper level only restores operation.

{{diagram:mav-offboard-loss-timeline|After a kill -9 of the script, PX4 leaves Offboard after 1 s, while ArduPilot keeps flying at the previous velocity for another 3 s and only then stops, staying in GUIDED.}}

{{diagram:mav-sdk-layers|pymavlink, MAVSDK and MAVROS are different levels of abstraction over the same MAVLink.}}

### Reference: packages, calls, versions
| What | Value (checked) | Source |
|---|---|---|
| `mavsdk` (PyPI) | 4.2.1, native binding, `import mavsdk` / `mavsdk.asyncio` | PyPI, package 4.2.1 |
| `mavsdk-grpc` | 4.2.1, old API, `import mavsdk_grpc as mavsdk` | PyPI; MAVSDK v4.2.1 README |
| last `mavsdk` of the old kind | 3.17.4 (`pip install "mavsdk<4"`) | PyPI |
| `pymavlink` | 2.4.50 | PyPI |
| Connection URLs | `udpin://0.0.0.0:14540`, `tcpout://127.0.0.1:5760`, `serial:///dev/ttyUSB0:57600` | migration.md, the `add_any_connection` docstring, the run |
| `first_autopilot(timeout_s)` | `System` or `None`; 0 checks once, < 0 waits forever | `mavsdk/asyncio/mavsdk.py` |
| `TelemetryAsync.set_rate_health(hz)` | SYS_STATUS (+ EKF_STATUS_REPORT for ArduPilot) | `telemetry_impl.cpp` |
| `MavlinkDirectAsync.send_command()` | COMMAND_LONG/INT from JSON, waits for COMMAND_ACK, retries by itself | `mavlink_direct.py` |
| `MissionRawAsync.download_mission()` | a list of raw items: `seq`, `frame`, `command`, `x`/`y` (degrees·10⁷), `z` | the run |
| ArduCopter: streams | `MAVn_RAW_SENS … MAVn_ADSB`, Copter default 0; before 4.7, `SRn_*` | `GCS_MAVLink_Parameters.cpp` |
| ArduCopter: own sysid | `MAV_SYSID` (before 4.7, `SYSID_THISMAV`) | the run, `ArduCopter/Parameters.cpp` |

### Where it fits

- **Takes in:** the command, parameter and mission dialogs that the SDK hides inside (`mav-services`); the stream through a router with its own compid (`mav-routing`); the autopilot heartbeat and the telemetry streams, which on ArduPilot 4.7 you have to request yourself.
- **Hands off:** actions and missions to the autopilot; Offboard and GUIDED setpoints (`px4-ros2`, `ap-companion`); the groundwork for the tracking loop (`per-tracking`).
- **If you get this wrong:** waiting for "GPS OK" without a timeout and without requesting the streams → the application hangs, setpoints stop, and the autopilot leaves Offboard on its own timeout (PX4) or stops in GUIDED (ArduPilot) (`ap-companion`). A mission without a placeholder item → on ArduPilot the first waypoint is silently replaced by home and the route is shorter than intended (`ap-missions`). Two MAVSDK processes on one port → identical IDs and unpredictable routing; separate them with a router and different compids (`mav-routing`).

## practice
### Step 1. Install MAVSDK 4 and make sure it is the right version
A separate virtual environment, so it does not mix with `mavsdk<4` from other projects. Check the version, and that the old `System()` call gives a hint rather than a cryptic error:

```bash
python3 -m venv venv && ./venv/bin/pip install mavsdk==4.2.1 pymavlink
./venv/bin/python -c "import mavsdk; print(mavsdk.__version__)"
# 4.2.1
./venv/bin/python -c "from mavsdk import System; System()"
# TypeError: System is not constructed directly, get it from Mavsdk instead. Since v4, the 'mavsdk' package
# is the native MAVSDK binding ... To keep the old API, install 'mavsdk-grpc' ...
```

The installed package has no `bin` directory with `mavsdk_server`, only `lib/libcmavsdk.so`, which is how it should be in 4.x.

### Step 2. SITL and a script with a timeout on every wait
ArduCopter 4.7.2 SITL (built with `./waf copter` or run through `sim_vehicle.py -v ArduCopter`) with the `copter.parm` parameters, home at CMAC (−35.363261, 149.165230). The run used instance `-I 7`, so the SERIAL0 TCP port is 5760 + 70 = 5830. The script below was run in full; every wait is wrapped in `first()` with a timeout, the streams are requested explicitly (pitfall 1), the mission has a placeholder item (pitfall 3), and the download goes through `MissionRaw` (pitfall 4).

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

The run output (MAVSDK 4.2.1, ArduCopter 4.7.2 SITL, November 25, 2026; the `[Error]` line is an ERROR-level log line from the MAVSDK core, which the filter lets through):

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

### Step 3. Read the raw mission and the progress
Analyze the output instead of taking it at its word. The coordinates in the raw items are degrees·10⁷: seq 2 differs from home in latitude by −353629017 − (−353632610) = 3593 units = 0.0003593°, which is 3593·10⁻⁷·111 320 m ≈ 40.0 m to the north; seq 4 is 7186 units ≈ 80.0 m, seq 6 is 10 780 units ≈ 120.0 m. The placeholder (0 m) went into seq 0 and was replaced by home: `frame=0` (MAV_FRAME_GLOBAL, altitude AMSL 584.1 m), while all the real waypoints are `frame=3` (MAV_FRAME_GLOBAL_RELATIVE_ALT, 20 m above home). The odd seq numbers are `cmd=178` (DO_CHANGE_SPEED), added by MAVSDK from `speed_m_s=5`. MISSION_CURRENT shows the raw seq (2, 4, 6) and `total=7` (8 items minus home: that is how the field is defined in common.xml), while the Mission plugin keeps its own count of plan items (1/4 … 4/4); `state=3` is MISSION_STATE_ACTIVE. 146 position samples in 80.0 − 50.8 = 29.2 s give 5.0 Hz, exactly the requested `set_rate_position(5)`.

### Step 4. Extension on your own machine: offboard and a channel dropout
Not run for this edition of the module; the criteria come from the theory. (a) NED velocities for 5 s in each of four directions through `OffboardAsync` (PX4: Offboard; ArduPilot: the same GUIDED). In the middle of the square, `kill -9` the script and measure from the log the time until the mode changes (PX4, compare with `COM_OF_LOSS_T` = 1 s) or until the stop in GUIDED (ArduPilot; the SITL 4.7.2 measurement in the ap-companion module: the speed starts to drop 3.2–3.3 s after the last target with `GUID_TIMEOUT` = 3 s, and the stop below 0.2 m/s comes after 4.3 s). (b) Between SITL and the script, `tc netem loss 100%` for 5 s during the mission: what `is_connected_state()` reported, what the autopilot did, and whether the script carried on without a restart.

### Moving to real hardware
The same script on the companion with the address `serial:///dev/ttyAMA0:921600` or, better, `udpin://0.0.0.0:14540` behind mavlink-router (the comp-raspberry module). Order: props off; run up to the `arm()` step and check that health arrives and that the streams are requested on this channel (Mission Planner's MAVLink Inspector shows the rates the script asked for); upload the mission and download it back through `MissionRaw`, and check the coordinates with the method from step 3. Props go on only for a flight flown by a pilot with a radio and a switch on LOITER/RTL, at 10 m altitude and with a geofence. Acceptance on hardware: the downloaded mission matches the uploaded one to within 0.5 m for every waypoint; progress reaches N/N; after RTL the vehicle disarms on its own.

Self-check: the lab is done when (SITL) `mavsdk.__version__` = 4.2.1 and the package has `lib/libcmavsdk.so` but no `mavsdk_server`; the script runs through to `landed and disarmed` without a single TimeoutError; the raw mission has 2·N items for N items with a speed, seq 0 is home with `frame=0`, and the latitude offsets of the waypoints, recomputed with the formula Δ·10⁻⁷·111 320, match the specified 40/80/120 m to within ±0.5 m; the plugin's progress goes 1/N … N/N, and MISSION_CURRENT goes through the even seq numbers; the position sample rate equals the requested one ±10 %. On hardware, the three acceptance criteria from the previous subsection are met as well.

**Reference answer for self-check.** A correct run looks like the step 2 output: health within 40–45 s after SITL starts (the EKF starts using GPS), 8 raw items for 4 plan items, progress 1/4 … 4/4, 5 Hz position. Typical wrong results: (1) `TimeoutError: health: no result in 120 s` with SITL alive: `set_rate_health`/`set_rate_position` were not called, and ArduCopter 4.7 streams default to 0; (2) of the three route waypoints only two are flown, and seq 0 contains the home coordinates: there is no placeholder item; (3) progress `-1/0` while MISSION_CURRENT is coming in: the plan was "forgotten" after the failed `download_mission()` and has to be uploaded again; (4) `no autopilot in 10 s` with SITL running: the TCP port is already taken by another client.

## diagnostics
- **Symptom:** the MAVSDK script hangs at startup or fails on the health timeout
  - Possible cause: on ArduPilot 4.7 the streams were not requested (`MAVn_*` = 0 on Copter); waiting for `health` without a timeout on a vehicle without GPS/home; the wrong connection address (udpin vs udpout).
  - What to do: `set_rate_health`, `set_rate_position` before subscribing; `asyncio.wait_for`; check the address and the MAVSDK version.
- **Symptom:** `ModuleNotFoundError`/`ImportError: No module named 'mavsdk.action'` or `TypeError: System is not constructed directly`
  - Possible cause: code written for the gRPC package (`mavsdk<4`) run with `mavsdk` 4.x.
  - What to do: `import mavsdk_grpc as mavsdk` after `pip install mavsdk-grpc`, or `mavsdk<4` in requirements, or rewrite using the mapping table.
- **Symptom:** on ArduPilot the route is shorter, the first waypoint is gone
  - Possible cause: seq 0 is taken by home, and the first `MissionItem` was overwritten.
  - What to do: a placeholder item first, or `MissionRaw` with an explicit home; verify by downloading through `MissionRaw`.
  - What the log shows: in the downloaded mission, seq 0 has `frame=0` and the home coordinates.
- **Symptom:** `download_mission()` → `UNSUPPORTED`, and after that progress `-1/0`
  - Possible cause: the Mission plugin does not accept home in MAV_FRAME_GLOBAL; the failed download reset the stored plan.
  - What to do: download through `MissionRawAsync`, upload the plan again.
- **Symptom:** PX4 leaves Offboard immediately
  - Possible cause: setpoints were not streamed before `offboard.start()`, or they come slower than 2 Hz.
  - What to do: send an initial setpoint before starting; a separate task at 10–20 Hz.
- **Symptom:** `upload_mission` sometimes fails with a timeout over the radio
  - Possible cause: losses on a slow link, too few retries by default.
  - What to do: upload over a fast link/through the companion; look in the tlog to see which item was lost.
- **Symptom:** two scripts interfere with each other, the second one does not see the autopilot
  - Possible cause: both use the same port (the SITL TCP port accepts one client) or the same compid.
  - What to do: a router with separate endpoints, different compids.

## references
- MAVSDK — Guide and Python API | https://mavsdk.mavlink.io/main/en/ | primary | A
- MAVSDK v4.2.1 — README (bindings, mavsdk-grpc) | https://github.com/mavlink/MAVSDK/blob/v4.2.1/README.md | primary | A
- MAVSDK v4.2.1 — Migrating from MAVSDK-Python (docs source) | https://github.com/mavlink/MAVSDK/blob/v4.2.1/docs/en/python/migration.md | primary | A
- MAVSDK v4.2.1 — telemetry_impl.cpp (ArduPilot health from EKF_STATUS_REPORT) | https://github.com/mavlink/MAVSDK/blob/v4.2.1/cpp/src/mavsdk/plugins/telemetry/telemetry_impl.cpp | primary | A
- MAVSDK v4.2.1 — action_impl.cpp (takeoff on ArduPilot) | https://github.com/mavlink/MAVSDK/blob/v4.2.1/cpp/src/mavsdk/plugins/action/action_impl.cpp | primary | A
- mavsdk on PyPI (release dates) | https://pypi.org/project/mavsdk/ | primary | A
- ArduPilot Copter-4.7.2 — GCS_MAVLink_Parameters.cpp (MAVn_* stream rates) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/GCS_MAVLink/GCS_MAVLink_Parameters.cpp | primary | A
- MAVSDK-Python (gRPC client, now mavsdk-grpc) | https://github.com/mavlink/MAVSDK-Python | primary | A
- MAVROS | https://github.com/mavlink/mavros | primary | A
- PX4 — Offboard mode (timeouts, COM_OF_LOSS_T; v1.18.0 docs source) | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/docs/en/flight_modes/offboard.md | primary | A
- ArduPilot — Copter commands in Guided mode | https://ardupilot.org/dev/docs/copter-commands-in-guided-mode.html | primary | A

## checklist
- I pick the layer (raw protocol, pymavlink, MAVSDK, MAVROS) for the task and can explain why
- I know which MAVSDK package is installed (native `mavsdk` 4.x or `mavsdk-grpc`) and port code using the mapping table
- On ArduPilot 4.7 I request the streams, put a placeholder item in seq 0 and download the mission through MissionRaw
- I write asynchronous code with timeouts and task cancellation, and remember that subscription queues are unbounded
- I control the vehicle in Offboard/GUIDED and know the setpoint timeouts
- I test how the system behaves on a link loss and when the script "dies"
