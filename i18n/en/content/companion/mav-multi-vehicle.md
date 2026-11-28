---
id: mav-multi-vehicle
title: "Multiple vehicles: addressing, separation, formation, and a supervisor"
level: L3
readingTime: 35 min
firmware: ArduPilot 4.7 (checked against 4.7.3) · PX4 1.18 (parameters checked against v1.18.0) · MAVLink 2
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
source_hash: 969d56a0e0a5
---

## summary
A second vehicle in the air is not "the same thing, twice". New questions appear: addressing (who the command went to), routing (how one GCS sees all of them), separation (how they avoid hitting each other), and responsibility (who answers when one vehicle loses its link). This module is the theory behind the "Fleet telemetry" project: unique sysids and ports, running several vehicles in SITL, separation strategies by altitude, sector, and time with a minimum-distance calculation, FOLLOW mode and formation flying from companion code, and a supervisor that watches the distances and stops a conflict.

## theory
### Addressing and routing
- **A unique sysid** on every vehicle: ArduPilot `MAV_SYSID` (`SYSID_THISMAV` before 4.7), PX4 `MAV_SYS_ID`. Two vehicles with sysid 1 on one network: the GCS sees "one" vehicle that jumps around, and commands go to both.
- **The GCS and scripts** are participants too: a GCS is usually 255, and a second station or a supervisor needs its own sysid (250, for example). pymavlink identifies itself as 255 by default, so set `source_system` for the supervisor.
- **target_system** in every command is the vehicle number. `target_system = 0` is a command to *everyone*; in a fleet that is a deliberate tool (a common stop), not a default value.
- **Routing**: every vehicle has its own link (a telemetry radio with a unique `NETID`, a separate UDP port), and everything is merged in mavlink-router or MAVProxy, which the GCS, the supervisor, and the logger connect to (the `mav-routing` module).
- **Failsafe on its own GCS**: a vehicle must know which GCS is "its own" (`MAV_GCS_SYSID`, `SYSID_MYGCS` before 4.7); otherwise another station's heartbeat keeps it "connected".

### Several vehicles in SITL
- ArduPilot: `sim_vehicle.py -v Copter --count 3 --auto-sysid --location CMAC --auto-offset-line 90,10 --mcast --map --console` gives three copters in a line 10 m apart, sysid 1…3; `--mcast` passes MAVLink between the vehicles (without it, the follower in FOLLOW from step 4 never hears the leader). Only one vehicle type per command. Without a start-point offset, they all spawn in the same place.
- PX4: start each instance with `-i N`; it sets `MAV_SYS_ID = N + 1` and shifts the UDP ports by N (offboard 14540 + N, 18570 + N towards the GCS), see Multi-Vehicle Simulation in the docs for your version.

### Separation: do not rely on luck
The minimum distance is made up of errors and reaction time:
- **Position error**: GNSS without RTK is on the order of 1–3 m horizontally, and worse vertically; for two vehicles the errors add up.
- **Detection and reaction delay**: telemetry (0.2–1 s), the supervisor's decision, the braking time.
- **Closing speed**: two vehicles head-on at 10 m/s each close at 20 m/s. With 0.5 s of telemetry + 0.5 s of decision + ~1.5 s of braking, ~50 m are covered in that time; with position errors (3 m for each vehicle, the upper end of the range above, +6 m in total) the minimum trigger distance is 56 m, that is, about 60 m. The lab's threshold `MIN_H = 15` m, with the same 0.5 + 0.5 + 1.5 s, is only enough up to (15 − 6) / (2 · 2.5) = 1.8 m/s per vehicle. Hence the rule: the faster the vehicles, the earlier the supervisor must step in.

{{diagram:chart-fleet-min-separation|The trigger distance grows linearly with speed: at 10 m/s and 0.5 s of telemetry you need 56 m, while the lab's 15 m threshold is only enough up to 1.8 m/s.}}

Strategies, from simple to complex:
1. **Altitude layers**: each vehicle has its own altitude, with ≥ 10 m separation plus the altitude error. Works as long as the vehicles do not change altitude (takeoff and landing are handled separately, one at a time).
2. **Sectors and corridors**: each vehicle in its own geofence (`FENCE_*` on each), with transitions along dedicated corridors.
3. **Time separation**: takeoff, landing, and passing shared points on a schedule.
4. **Supervisor**: watches pairwise distances in real time and stops a conflict (LOITER/BRAKE for the lower-priority vehicle).
5. **Built-in avoidance**: ArduPilot can avoid aircraft using ADS-B (`AVD_*`, `ADSB_VEHICLE` messages); feeding it the positions of your own fleet from the companion is a workable technique that you must test in SITL before flying.

### Formation
- **FOLLOW (ArduPilot)**: the follower holds an offset from the leader: `FOLL_ENABLE = 1`, `FOLL_SYSID` is the leader's sysid, `FOLL_OFS_X/Y/Z` the offset in meters, `FOLL_OFS_TYPE` 0 for north-east-down or 1 relative to the leader's heading, `FOLL_DIST_MAX` the distance beyond which the follower stops following and holds position. The follower needs the leader's positions: `GLOBAL_POSITION_INT` over a shared MAVLink bus (better: `FOLLOW_TARGET` from a Lua script on the leader).
- **Formation from code**: the companion sends each vehicle in GUIDED its own target (`SET_POSITION_TARGET_GLOBAL_INT`) at 2–4 Hz: the formation center + the vehicle's offset. More flexible than FOLLOW, but all the logic is yours, including the behavior when the link to the companion is lost.

### One failure is not everyone's failure
- Every vehicle must have its own link, battery, and geofence failsafes; the supervisor is an extra layer, not a replacement.
- Several vehicles on RTL to the same point means a collision over home. Use a different `RTL_ALT_M` (`RTL_ALT` before 4.7) or different return points (rally) for each vehicle.
- Regulations: in many countries, one pilot controlling several vehicles needs a separate authorization; check before flying.

{{diagram:multi-vehicle|A fleet: the GCS and the supervisor connect to a router, each vehicle has its own sysid, link, and altitude layer; a follower in FOLLOW tracks vehicle 2.}}

### Where it fits in the system

- **Takes in:** a unique sysid and its own link for each vehicle (`mav-routing`); the GNSS position with its error (`est-gnss`); each vehicle's own failsafes (`ap-safety-fs`).
- **Puts out:** GUIDED targets for each vehicle (`ap-companion`); the supervisor's LOITER/BRAKE commands to the lower-priority vehicle; altitude layers and return points for the system documentation (`eng-systems`).
- **If you get this wrong:** two vehicles with the same sysid → the GCS sees one "jumping" vehicle, and a command goes to both (`mav-routing`). A vehicle that does not know "its own" GCS → another station's heartbeat keeps it "connected", and the GCS failsafe never triggers (`ap-safety-fs`).

## practice
### Step 1. Three vehicles in SITL
Start three copters with the command from the theory section. In MAVProxy (`vehicle 1`, `vehicle 2`, …) or in the GCS, confirm that three sysids are visible. Give each its own `RTL_ALT_M` (30/40/50 m) and its own altitude layer.

### Step 2. Routing
Set up mavlink-router (or MAVProxy `--out`) so that the GCS, the supervisor, and the logger all receive the streams of all three. Write down the layout: sysids, ports, who connects where.

### Step 3. Supervisor
A script watches pairwise distances and, on a conflict, switches the lower-priority vehicle of the pair to LOITER, the one with the larger sysid (the lab's rule: a lower number means a higher priority; in the code this is `b`, the second element of the sorted pair):
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
Set up a conflict: two vehicles in GUIDED flying head-on at the same altitude. Check that the supervisor triggers, and write down the distance at the moment it triggers and the minimum distance after that.

### Step 4. FOLLOW
Vehicle 3: `FOLL_ENABLE = 1` (refresh the parameters), `FOLL_SYSID = 2`, `FOLL_OFS_X = -10`, `FOLL_OFS_Z = -5` (5 m above), `FOLL_OFS_TYPE = 1`. Vehicle 2 flies a mission, vehicle 3 is in FOLLOW mode. Record the follower's lag from the log on straight legs and in turns. Then shut down vehicle 2 (or its link) and describe how the follower behaves.

### Step 5. The distance calculation
For your own speeds and telemetry delay, compute the supervisor's minimum trigger distance (as in the theory section) and compare it with the result of step 3.

Self-check: the lab is done when three vehicles are visible with unique sysids and their own RTL altitudes, the routing layout is written down, the supervisor stops the conflict (the "conflict …" line is printed at a distance under 15 m horizontally and 5 m vertically, the vehicle of the pair with the larger sysid is switched to LOITER while the one with the smaller sysid keeps flying, and the trigger distance and the minimum distance after it are recorded), FOLLOW is set up, the follower's lag on straight legs and in turns is recorded from the log and the behavior on losing the leader is described, and the minimum distance is computed with the scheme from the theory section and compared with step 3.

**Reference answer for self-check.** The calculation: closing speed × (telemetry + decision + braking) plus the position errors; check your formula against the numbers in the theory section: two vehicles at 10 m/s each, 0.5 + 0.5 + ~1.5 s give ~50 m of travel and about 60 m of minimum distance. If your computed distance is larger than the `MIN_H = 15` m threshold, a supervisor with that threshold steps in too late, and the minimum distance from step 3 should show it. Losing the leader: the leader's positions stop arriving, and the follower stops following and holds in place, the same symptom as in the troubleshooting section. Common mistake #1: the follower does not follow from the very start, because SITL was started without `--mcast` or `FOLL_SYSID` is not set. Common mistake #2: the calculation uses only the closing speed and the telemetry delay, without the braking time and the position errors, so the distance comes out too small.

## diagnostics
- **Symptom:** in the GCS, one vehicle "jumps" between two places
  - Possible cause: two vehicles with the same sysid.
  - What to do: unique `MAV_SYSID`/`MAV_SYS_ID`, a reboot, `--auto-sysid` in SITL.
- **Symptom:** a command went to the wrong vehicle, or to all of them
  - Possible cause: `target_system` left at its default or 0, or the script took `target_system` from the first heartbeat.
  - What to do: an explicit sysid in every command, and a check for the `COMMAND_ACK` from the right sysid.
- **Symptom:** a vehicle does not go into failsafe when it loses its own GCS
  - Possible cause: another station's or the supervisor's heartbeat keeps it connected.
  - What to do: `MAV_GCS_SYSID` (`SYSID_MYGCS` before 4.7), and separate sysids for helper scripts.
- **Symptom:** all vehicles on RTL converge over home
  - Possible cause: the same altitude and return point.
  - What to do: different RTL altitudes and rally points, landing one at a time.
- **Symptom:** the follower in FOLLOW stays put
  - Possible cause: `FOLL_SYSID` is not set, the leader is farther than `FOLL_DIST_MAX`, or the leader's positions do not reach the follower.
  - What to do: check the parameters, and check that the leader's `GLOBAL_POSITION_INT` is routed to the follower.

## references
- ArduPilot — Copter Follow mode | https://ardupilot.org/copter/docs/follow-mode.html | primary | A
- ArduPilot — Using SITL (multiple vehicles) | https://ardupilot.org/dev/docs/using-sitl-for-ardupilot-testing.html | primary | A
- MAVProxy — Multiple vehicles | https://ardupilot.org/mavproxy/docs/getting_started/multi.html | primary | A
- PX4 — Multi-vehicle simulation | https://docs.px4.io/v1.17/en/sim_gazebo_gz/multi_vehicle_simulation.html | primary | A

## checklist
- I assign unique sysids to vehicles and to helper scripts
- I run several vehicles in SITL and bring them into one GCS
- I compute the minimum distance accounting for position errors and delays
- I pick a separation strategy: layers, sectors, time, supervisor
- I set up FOLLOW and understand what happens when the leader is lost
- I separate the vehicles' RTL by altitude and return points
