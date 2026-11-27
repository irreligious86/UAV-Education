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

{{diagram:mavlink-mission-seq|The aircraft drives a mission upload: it requests every command by number itself and asks again for a lost reply.}}

{{diagram:mission-jump-order|The execution order of the step 4 mission: DO commands fire at leg boundaries, DO_JUMP with a repeat of 1 gives a second pass of A–B, and without an RTL at the end the aircraft hovers in AUTO.}}

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

SITL run of this step (ArduCopter 4.7.2); walkthrough and expected output are in the Russian source.

```python
"""Mission lab: upload, download to a QGC WPL 110 file and fly a mission with DO_CHANGE_SPEED and DO_JUMP
in ArduCopter 4.7.2 SITL; no RTL at the end, to see what the copter does when the list runs out.
Usage: python3 mission_lab.py ~/ardupilot   (run from an empty folder)"""
import math, subprocess, sys, time
from pymavlink import mavutil

AP, C = sys.argv[1], mavutil.mavlink
sitl = subprocess.Popen([AP + "/build/sitl/bin/arducopter", "--model", "+", "--speedup", "10", "-w",
                         "--defaults", AP + "/Tools/autotest/default_params/copter.parm",
                         "--home", "-35.363261,149.165230,584,353"], stdout=open("sitl.out", "w"), stderr=subprocess.STDOUT)
time.sleep(1)
m = mavutil.mavlink_connection("tcp:127.0.0.1:5760"); m.wait_heartbeat()
m.mav.command_long_send(1, 1, C.MAV_CMD_SET_MESSAGE_INTERVAL, 0, 33, 200000, 0, 0, 0, 0, 0)  # GLOBAL_POSITION_INT 5 Hz
LAT0, LON0, K = -35.363261, 149.165230, 111319.5   # home and metres per degree (latitude)
ROUTE = {"A": (100, 0), "B": (100, 100), "C": (0, 100), "D": (0, 0)}   # data: north_m, east_m


def nav(cmd, n=0, e=0, alt=20.0, p=(0, 0, 0, 0)):
    lat, lon = LAT0 + n / K, LON0 + e / (K * math.cos(math.radians(LAT0)))
    return [cmd, *p, int(lat * 1e7), int(lon * 1e7), alt]


def do(cmd, *p):
    return [cmd, *p, *[0] * (4 - len(p)), 0, 0, 0]


plan = [nav(C.MAV_CMD_NAV_WAYPOINT, alt=0),           # 0: home, the vehicle overwrites it
        nav(C.MAV_CMD_NAV_TAKEOFF),                    # 1
        do(C.MAV_CMD_DO_CHANGE_SPEED, 1, 5, -1),       # 2: ground speed 5 m/s, throttle unchanged
        nav(C.MAV_CMD_NAV_WAYPOINT, *ROUTE["A"]),      # 3
        nav(C.MAV_CMD_NAV_WAYPOINT, *ROUTE["B"]),      # 4
        do(C.MAV_CMD_DO_JUMP, 3, 1),                   # 5: back to 3, repeat once
        do(C.MAV_CMD_DO_CHANGE_SPEED, 1, 10, -1),      # 6: 10 m/s
        nav(C.MAV_CMD_NAV_WAYPOINT, *ROUTE["C"]),      # 7
        nav(C.MAV_CMD_NAV_WAYPOINT, *ROUTE["D"])]      # 8: last item, no RTL after it
F = C.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT
while m.recv_match(type="GLOBAL_POSITION_INT", blocking=True).time_boot_ms < 10000:
    pass                                                  # right after boot the upload is refused (ACK 4 = MAV_MISSION_NO_SPACE)
m.mav.mission_count_send(1, 1, len(plan))                 # upload: the vehicle pulls each item by seq
while (r := m.recv_match(type=["MISSION_REQUEST_INT", "MISSION_REQUEST", "MISSION_ACK"], blocking=True)).get_type() != "MISSION_ACK":
    c, p1, p2, p3, p4, x, y, z = plan[r.seq]
    m.mav.mission_item_int_send(1, 1, r.seq, F, c, 0, 1, p1, p2, p3, p4, x, y, z)
print(f"upload: MISSION_ACK type {r.type} (0 = MAV_MISSION_ACCEPTED)")
m.mav.mission_request_list_send(1, 1)                     # download: we pull each item by seq
n = m.recv_match(type="MISSION_COUNT", blocking=True).count
with open("mission.waypoints", "w") as f:
    f.write("QGC WPL 110\n")
    for s in range(n):
        m.mav.mission_request_int_send(1, 1, s)
        i = m.recv_match(type="MISSION_ITEM_INT", blocking=True)
        f.write(f"{i.seq}\t{int(s == 0)}\t{i.frame}\t{i.command}\t{i.param1:g}\t{i.param2:g}\t{i.param3:g}\t{i.param4:g}"
                f"\t{i.x / 1e7:.7f}\t{i.y / 1e7:.7f}\t{i.z:g}\t{i.autocontinue}\n")
m.mav.mission_ack_send(1, 1, 0)
print(open("mission.waypoints").read(), end="")
m.set_mode("GUIDED")
while not m.motors_armed():
    m.arducopter_arm(); m.recv_match(type="HEARTBEAT", blocking=True); m.recv_match(type="HEARTBEAT", blocking=True)
m.set_mode("AUTO")
m.mav.command_long_send(1, 1, C.MAV_CMD_MISSION_START, 0, 0, 0, 0, 0, 0, 0, 0)  # throttle stays low in this SITL
t0, last, v, t = None, None, [], 0.0
while True:
    r = m.recv_match(type=["STATUSTEXT", "GLOBAL_POSITION_INT"], blocking=True)
    if r.get_type() == "GLOBAL_POSITION_INT":
        t = r.time_boot_ms / 1000; t0 = t0 or t
        v.append(math.hypot(r.vx, r.vy) / 100)
    elif r.text.startswith(("Mission:", "Reached")):
        t0 = t0 or t
        leg = f"  leg {t - last:5.1f} s, top speed {max(v):4.1f} m/s" if r.text.startswith("Reached") and last else ""
        print(f"[{t - t0:6.1f} s] {r.text}{leg}")
        if r.text.startswith("Reached"):
            last, v = t, []
        elif last is None and "WP" in r.text:
            last, v = t, []
        if r.text == "Reached command #8":
            break
end = t
while (r := m.recv_match(type="GLOBAL_POSITION_INT", blocking=True)).time_boot_ms / 1000 < end + 20:
    pass
hb = m.recv_match(type="HEARTBEAT", blocking=True)
print(f"+20 s after the last item: mode {mavutil.mode_string_v10(hb)}, armed {bool(hb.base_mode & 128)}, "
      f"alt {r.relative_alt / 1000:.1f} m, speed {math.hypot(r.vx, r.vy) / 100:.2f} m/s")
sitl.terminate()
```

```text
upload: MISSION_ACK type 0 (0 = MAV_MISSION_ACCEPTED)
QGC WPL 110
0	1	0	16	0	0	0	0	0.0000000	0.0000000	0	1
1	0	3	22	0	0	0	0	-35.3632610	149.1652300	20	1
2	0	0	178	1	5	-1	0	0.0000000	0.0000000	0	1
3	0	3	16	0	0	0	0	-35.3623626	149.1652300	20	1
4	0	3	16	0	0	0	0	-35.3623626	149.1663315	20	1
5	0	0	177	3	1	0	0	0.0000000	0.0000000	0	1
6	0	0	178	1	10	-1	0	0.0000000	0.0000000	0	1
7	0	3	16	0	0	0	0	-35.3632610	149.1663315	20	1
8	0	3	16	0	0	0	0	-35.3632610	149.1652300	20	1
[   0.0 s] Mission: 1 Takeoff
[  11.4 s] Mission: 2 ChangeSpeed
[  11.4 s] Mission: 3 WP
[  34.6 s] Reached command #3  leg  23.2 s, top speed  5.0 m/s
[  34.6 s] Mission: 4 WP
[  55.2 s] Reached command #4  leg  20.6 s, top speed  5.0 m/s
[  55.2 s] Mission: 5 Jump 1/1
[  55.2 s] Mission: 3 WP
[  76.8 s] Reached command #3  leg  21.6 s, top speed  5.0 m/s
[  76.8 s] Mission: 4 WP
[  98.0 s] Reached command #4  leg  21.2 s, top speed  5.0 m/s
[  98.0 s] Mission: 6 ChangeSpeed
[  98.0 s] Mission: 7 WP
[ 112.0 s] Reached command #7  leg  14.0 s, top speed  9.9 m/s
[ 112.0 s] Mission: 8 WP
[ 126.8 s] Reached command #8  leg  14.8 s, top speed  9.9 m/s
+20 s after the last item: mode AUTO, armed True, alt 20.0 m, speed 0.01 m/s
```


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
