---
id: ap-missions
title: "Missions and Planning"
level: L2
readingTime: 25 min
firmware: ArduPilot 4.5+
status: published
added: 2026-11-07
tags:
  - missions
  - AUTO
  - waypoints
related:
  - ap-sitl
  - ap-ekf
next:
  - ap-ekf
source: content/ardupilot/ap-missions.md
source_hash: 2c8780dcaaa0
---

## summary
A mission in ArduPilot is a list of commands the flight controller executes on its own in AUTO mode: take off, fly through waypoints, take a picture, come back. This module explains what a mission is made of, how navigation commands differ from DO and CONDITION commands, how altitude is calculated, where home is, and what happens when the link is lost mid-route. Practice is in SITL, following the “route separately, scenario separately” pattern.

## theory
### Three types of commands
- **NAV** — where to fly. `NAV_TAKEOFF` (22), `NAV_WAYPOINT` (16), `NAV_LOITER_TIME` (19), `NAV_RETURN_TO_LAUNCH` (20), `NAV_LAND` (21). The mission goes from one NAV command to the next.
- **DO** — what to do along the way without changing the route: `DO_CHANGE_SPEED` (178), `DO_SET_SERVO` (183), `DO_SET_CAM_TRIGG_DIST` (206), `DO_JUMP` (177) for loops.
- **CONDITION** — wait for a condition before the next DO command: `CONDITION_DELAY` (112), `CONDITION_DISTANCE`.

The numbers in parentheses are MAV_CMD codes: that's how the commands look in a mission file and in MAVLink.

### Altitude
Every waypoint has a reference frame. For missions you almost always use altitude **relative to home** (`MAV_FRAME_GLOBAL_RELATIVE_ALT`, code 3): “100 m” means 100 m above the arming point. Absolute altitude above sea level (`MAV_FRAME_GLOBAL`, 0) is rarely needed and easily leads to an error of hundreds of meters. Altitude above terrain requires terrain data.

### Home
For Copter, the home point is where the aircraft armed. RTL returns there, not to where the pilot is standing. If you took off from the roof of a car and then drove somewhere else — home stayed at the old spot. In the GCS you can reset home before takeoff.

### Starting and resuming
A Copter mission usually starts with `NAV_TAKEOFF`. Switching to AUTO on the ground with the aircraft armed starts the takeoff once the pilot raises the throttle (or immediately, if bit 1 “Allow Takeoff Without Raising Throttle” is set in `AUTO_OPTIONS`); in SITL — `rc 3 1500`. By default, when you re-enter AUTO the mission continues from the current command; the `MIS_RESTART` parameter makes it start from the first one.

### Failsafe during a mission
Loss of the radio link during AUTO behaves per `FS_THR_ENABLE` (RTL, Land, SmartRTL…), and continuing the mission is enabled by bit 0 of `FS_OPTIONS`. For autonomous beyond-visual-line-of-sight flights this decision is made before takeoff, not after the fact. GCS loss is a separate parameter, `FS_GCS_ENABLE`. The battery failsafe (`BATT_FS_LOW_ACT`, `BATT_FS_CRT_ACT`) overrides the mission.

### Mission file
GCSs save the mission to a text file in the `QGC WPL 110` format: one line per command — index, current flag, frame, command code, four parameters, latitude, longitude, altitude, autocontinue flag. Such a file is convenient to keep in git next to the parameters.

### Commands worth knowing by heart
NAV: `NAV_WAYPOINT` (p1 — delay at the waypoint, s), `NAV_TAKEOFF` (alt), `NAV_LAND`, `NAV_RETURN_TO_LAUNCH`, `NAV_LOITER_TIME/TURNS/UNLIM`, `NAV_SPLINE_WAYPOINT` (spline), `NAV_DELAY`; DO: `DO_SET_SERVO`, `DO_SET_RELAY`, `DO_DIGICAM_CONTROL`, `DO_SET_CAM_TRIGG_DIST` (a shot every N m — the basis of photogrammetry), `DO_CHANGE_SPEED`, `DO_SET_ROI` (point the gimbal/nose), `DO_JUMP` (a loop, with a counter), `DO_LAND_START` (the entry point of the landing sequence for a failsafe), `DO_SET_HOME`; CONDITION: `CONDITION_DELAY`, `CONDITION_DISTANCE`, `CONDITION_YAW`. Execution parameters: `WP_SPD` (m/s horizontal), `WP_SPD_UP/DN`, `WP_RADIUS_M` (acceptance radius), `WP_ACC` (before 4.7 — `WPNAV_SPEED` in cm/s, `WPNAV_SPEED_UP/DN`, `WPNAV_RADIUS`, `WPNAV_ACCEL`), `WP_YAW_BEHAVIOR` (nose along the course or not), `MIS_RESTART` (0 — resume from the last command when entering Auto, 1 — from the start), `MIS_OPTIONS` (bit 0 — clear the mission on reboot; bit 1 — use distance to landing in the battery failsafe (Plane only); bit 2 — continue after landing), `RTL_*` for the end of the mission.

### Altitudes: three frames and one mistake
Relative (above home, `MAV_FRAME_GLOBAL_RELATIVE_ALT`, the default), absolute (above sea level — wrong if you take off somewhere else), terrain (above ground from SRTM data via the GCS or from a rangefinder, `TERRAIN_ENABLE`, the “Terrain” frame on waypoints and `WP_RFND_USE`/`RTL_ALT_TYPE`). The classic crash: a mission with absolute altitudes, made for a different site 300 m higher — the aircraft tries to dive into the ground or climb into the sky. The rule: relative altitudes, and check the altitude-above-terrain profile in the GCS.

### Worked example: surveying a 300×200 m area
Mission Planner → Survey (Grid): camera (sensor, focal length), altitude 80 m, overlap 75/65% → the planner calculates the spacing between survey lines and `DO_SET_CAM_TRIGG_DIST` itself; speed 8 m/s (based on camera exposure: motion blur ≤ 1 px → v·t_exp ≤ GSD); `NAV_TAKEOFF` 80, survey lines, `DO_SET_CAM_TRIGG_DIST 0` at the end, `NAV_RETURN_TO_LAUNCH`. Checks: the altitude profile, mission time vs. battery capacity (`BATT_LOW_MAH` with margin for RTL + capacity margin for the return), a geofence around the area. A run in SITL with the same mission file is mandatory.

{{diagram:mission-alt-frames|Choosing the altitude frame in a mission: Relative for flat ground, Terrain for varying terrain, Absolute when altitude above sea level is given.}}

## practice
### Step 1. A mission in SITL via the GCS
1. Start SITL: `sim_vehicle.py -v ArduCopter --console --map`.
2. In Mission Planner (Plan) or QGC (Plan), set TAKEOFF 20 m, three waypoints, RTL.
3. Write the mission to the aircraft, save the `.waypoints` file.
4. Arm, AUTO mode, watch. Then try switching to LOITER mid-route and back to AUTO.

### Step 2. The same mission from code
The route is data, the scenario is commands. An example of uploading a route via pymavlink:

```python
from pymavlink import mavutil

ROUTE = [  # (lat, lon, alt_m) — data only, no commands here
    (-35.3630, 149.1652, 30),
    (-35.3625, 149.1660, 30),
    (-35.3632, 149.1668, 30),
]

m = mavutil.mavlink_connection("tcp:127.0.0.1:5762")
m.wait_heartbeat()
FRAME = mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT  # 6

def item(seq, cmd, lat=0, lon=0, alt=0, p1=0):
    return m.mav.mission_item_int_encode(
        m.target_system, m.target_component, seq, FRAME, cmd,
        0, 1, p1, 0, 0, 0, int(lat * 1e7), int(lon * 1e7), alt)

items = [item(0, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT), item(1, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, alt=20)]  # seq 0 = home
items += [item(i + 1, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, *wp) for i, wp in enumerate(ROUTE)]
items.append(item(len(items), mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH))

m.waypoint_clear_all_send()
m.waypoint_count_send(len(items))
for _ in items:
    req = m.recv_match(type=["MISSION_REQUEST", "MISSION_REQUEST_INT"], blocking=True)
    m.mav.send(items[req.seq])
ack = m.recv_match(type="MISSION_ACK", blocking=True)
print("mission upload:", ack.type)  # 0 = MAV_MISSION_ACCEPTED
```

A mission upload is a dialog: the aircraft requests each waypoint by its index, so you can't send them in one “batch.”

### Step 3. Scenarios on top of a route
Write three scenarios that take the route as a parameter: “fly through,” “fly through and take a photo at every waypoint” (`DO_DIGICAM_CONTROL`), “fly through with a motor failure at the second waypoint” (the switch from the Lua module). One route — three scenarios with no edits to the coordinates.

**Automatic log check:** `check_lab_log.py <log.bin> --lab mission` — AUTO engaged, ≥ 3 navigation commands, “Reached” messages, RTL/LAND at the end, satellites ≥ 6, no EKF/GPS errors.

## diagnostics
- **Symptom:** AUTO doesn't start, the aircraft just sits there
  - Possible cause: the mission isn't uploaded, `NAV_TAKEOFF` isn't the first command, or the aircraft isn't armed.
  - What to do: read the mission back from the aircraft, check the first command and the GCS messages.
- **Symptom:** the aircraft flies 100 m higher than expected
  - Possible cause: absolute altitude instead of relative.
  - What to do: check the frame of every waypoint in the mission file.
- **Symptom:** RTL returns somewhere other than where the pilot is
  - Possible cause: home is the arming location.
  - What to do: reset home before takeoff after relocating.
- **Symptom:** the mission upload hangs
  - Possible cause: sending waypoints without waiting for requests, or a wrong `seq`.
  - What to do: answer `MISSION_REQUEST(_INT)` by index, check `MISSION_ACK`.
- **Symptom:** in Auto the aircraft dove into the ground/climbed after a change of site
  - Possible cause: absolute altitudes in the mission.
  - What to do: relative/terrain; check the altitude profile in the GCS.
- **Symptom:** after a landing in the mission the aircraft doesn't disarm or keeps going
  - Possible cause: `MIS_OPTIONS` bit 2 (ContinueAfterLand), `LAND_*`.
  - What to do: set it deliberately; verify in SITL.

## references
- Planning a Mission with Waypoints and Events — ArduPilot Copter | https://ardupilot.org/copter/docs/common-planning-a-mission-with-waypoints-and-events.html | primary | A
- Copter Mission Command List — ArduPilot | https://ardupilot.org/copter/docs/mission-command-list.html | primary | A
- MAVLink Mission Protocol | https://mavlink.io/en/services/mission.html | primary | A
- MAVLink common message set (common.xml) | https://github.com/mavlink/mavlink/blob/master/message_definitions/v1.0/common.xml | primary | A

## checklist
- I know the difference between NAV, DO and CONDITION commands
- All mission waypoints use relative altitude
- I understand where home is and how to reset it
- Radio/GCS/battery failsafes are configured before an autonomous flight
- The mission is uploaded from code as a request–response dialog
- The route is stored separately from the scenario
