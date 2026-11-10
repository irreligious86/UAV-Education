---
id: mav-multi-vehicle
title: "Multiple vehicles: addressing, separation, formation and a supervisor"
level: L3
readingTime: 35 min
firmware: ArduPilot 4.5+ · PX4 1.15+ · MAVLink 2
status: published
tags:
  - fleet
  - multi-vehicle
  - separation
  - FOLLOW
related:
  - mav-routing
  - mav-sdk
  - ap-companion
  - ap-sitl
next:
  - eng-systems
source: content/companion/mav-multi-vehicle.md
source_hash: 815241c0ac05
---

## summary
A second vehicle in the air is not “the same thing, just twice.” New questions show up: addressing (who did the command go to), routing (how one GCS sees everyone), separation (how they avoid colliding with each other) and responsibility (who is in charge when one vehicle loses its link). This module is the theory base for the “Fleet telemetry” project: unique sysids and ports, running several vehicles in SITL, separation strategies by altitude, sector and time with a minimum-distance calculation, FOLLOW mode and formation from companion code, and a supervisor that watches distances and stops a conflict.

## theory
### Addressing and routing
- **A unique sysid** for every vehicle: ArduPilot — `MAV_SYSID` (before 4.7 — `SYSID_THISMAV`), PX4 — `MAV_SYS_ID`. Two vehicles with sysid 1 on the same network — the GCS sees “one” jumping vehicle, and commands go to both.
- **The GCS and scripts** are participants too: the GCS is usually 255, a second station or a supervisor needs its own sysid (for example 250). pymavlink identifies itself as 255 by default — set `source_system` for the supervisor.
- **target_system** in every command is the vehicle number. `target_system = 0` is a command to *everyone*; in a fleet that is a deliberate tool (a global stop), not a default value.
- **Routing**: each vehicle has its own link (a radio modem with a unique `NETID`, a separate UDP port), and everything is merged in mavlink-router or MAVProxy, which the GCS, supervisor and logger connect to (module `mav-routing`).
- **Failsafe on its own GCS**: the vehicle must know which GCS is “its own” (`MAV_GCS_SYSID`, before 4.7 — `SYSID_MYGCS`), otherwise another station's heartbeat keeps it “connected.”

### Multiple vehicles in SITL
- ArduPilot: `sim_vehicle.py -v Copter --count 3 --auto-sysid --location CMAC --auto-offset-line 90,10 --mcast --map --console` — three copters in a line 10 m apart, sysid 1…3; `--mcast` lets MAVLink flow between vehicles (without it the follower in FOLLOW from step 4 won't hear the leader). Only one vehicle type per command. Without offsetting the start point, they all spawn in the same place.
- PX4: instances are started with the `-i N` flag; sysid and ports shift by instance number — see the Multi-Vehicle Simulation section of the docs for your version.

### Separation: don't rely on luck
Minimum distance is built from errors and reaction time:
- **Position error**: GNSS without RTK — on the order of 1–3 m horizontally and worse vertically; for two vehicles the errors add up.
- **Detection and reaction delay**: telemetry (0.2–1 s), the supervisor's decision, braking time.
- **Closing speed**: two vehicles flying toward each other at 10 m/s each — 20 m/s closing speed. With 0.5 s of telemetry + 0.5 s of decision + ~1.5 s of braking, ~50 m is covered in that time; add position errors and the minimum trigger distance is around 60 m. Hence the rule: the faster the vehicles, the earlier the supervisor has to step in.

Strategies, from simple to complex:
1. **Altitude layers** — each vehicle has its own altitude with a separation of ≥ 10 m plus altitude error. Works as long as the vehicles don't change altitude (takeoff and landing are handled separately, one at a time).
2. **Sectors and corridors** — each vehicle in its own geofence (`FENCE_*` on each), transitions through dedicated corridors.
3. **Time separation** — takeoff, landing and passing shared points on a schedule.
4. **Supervisor** — watches pairwise distances in real time and stops a conflict (LOITER/BRAKE for the lower-priority one).
5. **Built-in avoidance** — ArduPilot can avoid aircraft via ADS-B (`AVD_*`, `ADSB_VEHICLE` messages); feeding it your own fleet's positions from the companion is a working technique that you need to verify in SITL before flying.

### Formation
- **FOLLOW (ArduPilot)** — the follower holds an offset from the leader: `FOLL_ENABLE = 1`, `FOLL_SYSID` — the leader's sysid, `FOLL_OFS_X/Y/Z` — offset in meters, `FOLL_OFS_TYPE` — 0 north-east-down, 1 relative to the leader's heading, `FOLL_DIST_MAX` — beyond this the follower stops following and holds position. The follower needs the leader's positions: `GLOBAL_POSITION_INT` over the shared MAVLink bus (better — `FOLLOW_TARGET` from a Lua script on the leader).
- **Formation from code** — the companion sends each vehicle in GUIDED its own target (`SET_POSITION_TARGET_GLOBAL_INT`) at 2–4 Hz: formation center + the vehicle's offset. More flexible than FOLLOW, but all the logic is yours, including behavior on loss of link to the companion.

### One failure is not everyone's failure
- Each vehicle on its own must have failsafes for link, battery and geofence; the supervisor is an extra layer, not a replacement.
- RTL of several vehicles to one point means a collision over home. Use different `RTL_ALT_M` (before 4.7 — `RTL_ALT`) or different return points (rally) for each vehicle.
- Regulations: one pilot controlling several vehicles requires a separate authorization in many countries — check before flying.

{{diagram:multi-vehicle|Fleet: the GCS and supervisor connect to the router, each vehicle has its own sysid, link and altitude layer; the follower in FOLLOW follows vehicle 2.}}

## practice
### Step 1. Three vehicles in SITL
Start three copters with the command from the theory. In MAVProxy (`vehicle 1`, `vehicle 2`, …) or in the GCS, make sure three sysids are visible. Give each its own `RTL_ALT_M` (30/40/50 m) and its own altitude layer.

### Step 2. Routing
Set up mavlink-router (or MAVProxy `--out`) so the GCS, supervisor and logger receive the stream from all three. Write down the layout: sysids, ports, who connects where.

### Step 3. Supervisor
The script watches pairwise distances and switches the lower-numbered vehicle to LOITER on a conflict:
```python
import math, time
from pymavlink import mavutil

m = mavutil.mavlink_connection("udpin:0.0.0.0:14560", source_system=250)
MIN_H, MIN_V, STALE = 15.0, 5.0, 2.0          # m, m, s
LOITER = 5                                     # custom mode ArduCopter
pos, held = {}, set()

def sep(a, b):
    dn = (b[0] - a[0]) * 111_320
    de = (b[1] - a[1]) * 111_320 * math.cos(math.radians(a[0]))
    return math.hypot(dn, de), abs(b[2] - a[2])

while True:
    msg = m.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=1)
    if msg is None:
        continue
    pos[msg.get_srcSystem()] = (msg.lat / 1e7, msg.lon / 1e7, msg.relative_alt / 1000, time.time())
    now = time.time()
    live = sorted(k for k, v in pos.items() if now - v[3] < STALE)
    for i, a in enumerate(live):
        for b in live[i + 1:]:
            h, v = sep(pos[a], pos[b])
            if h < MIN_H and v < MIN_V and b not in held:
                print(f"conflict {a}-{b}: {h:.1f} m / {v:.1f} m → LOITER for {b}")
                m.mav.command_long_send(b, 1, mavutil.mavlink.MAV_CMD_DO_SET_MODE, 0,
                    mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, LOITER, 0, 0, 0, 0, 0)
                held.add(b)
```
Stage a conflict: two vehicles in GUIDED flying toward each other at the same altitude. Check that the supervisor triggers, and record the distance at the moment it triggers and the minimum distance after it.

### Step 4. FOLLOW
Vehicle 3: `FOLL_ENABLE = 1` (reload parameters), `FOLL_SYSID = 2`, `FOLL_OFS_X = -10`, `FOLL_OFS_Z = -5` (5 m higher), `FOLL_OFS_TYPE = 1`. Vehicle 2 flies a mission, vehicle 3 is in FOLLOW mode. Record the follower's lag from the log on straights and turns. Then shut down vehicle 2 (or its link) and describe how the follower behaves.

### Step 5. Distance calculation
For your speeds and telemetry delay, calculate the supervisor's minimum trigger distance (as in the theory) and compare it with the result of step 3.

The lab is passed when three vehicles are visible with unique sysids and their own RTL altitudes, the routing layout is written down, the supervisor stops a conflict with a measured distance, FOLLOW is set up and the behavior on loss of the leader is described, and the minimum-distance calculation is done.

## diagnostics
- **Symptom:** in the GCS one vehicle “jumps” between two places
  - Possible cause: two vehicles with the same sysid.
  - What to do: unique `MAV_SYSID`/`MAV_SYS_ID`, reboot, `--auto-sysid` in SITL.
- **Symptom:** a command went to the wrong vehicle or to all of them
  - Possible cause: `target_system` left at default or 0, the script took `target_system` from the first heartbeat.
  - What to do: an explicit sysid in every command, check for `COMMAND_ACK` from the right sysid.
- **Symptom:** the vehicle doesn't go into failsafe when it loses its GCS
  - Possible cause: it's being kept alive by the heartbeat of another station or the supervisor.
  - What to do: `MAV_GCS_SYSID` (before 4.7 — `SYSID_MYGCS`), separate sysids for helper scripts.
- **Symptom:** all vehicles on RTL converge over home
  - Possible cause: the same altitude and return point.
  - What to do: different RTL altitudes and rally points, land one at a time.
- **Symptom:** the follower in FOLLOW stays in place
  - Possible cause: `FOLL_SYSID` not set, the leader is farther than `FOLL_DIST_MAX`, the leader's positions don't reach the follower.
  - What to do: check the parameters and that the leader's `GLOBAL_POSITION_INT` is routed to the follower.

## references
- ArduPilot — Copter Follow mode | https://ardupilot.org/copter/docs/follow-mode.html | primary | A
- ArduPilot — Using SITL (multiple vehicles) | https://ardupilot.org/dev/docs/using-sitl-for-ardupilot-testing.html | primary | A
- MAVProxy — Multiple vehicles | https://ardupilot.org/mavproxy/docs/getting_started/multi.html | primary | A
- PX4 — Multi-vehicle simulation | https://docs.px4.io/main/en/sim_gazebo_gz/multi_vehicle_simulation.html | primary | A

## checklist
- I assign unique sysids to vehicles and helper scripts
- I run several vehicles in SITL and bring them into one GCS
- I calculate the minimum distance accounting for position errors and delays
- I choose a separation strategy: layers, sectors, time, supervisor
- I set up FOLLOW and understand what happens when the leader is lost
- I separate the vehicles' RTL by altitude and return points
