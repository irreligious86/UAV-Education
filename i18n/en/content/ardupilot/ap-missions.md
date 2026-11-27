---
id: ap-missions
title: "Missions and planning"
level: L2
readingTime: 35 min
firmware: ArduPilot 4.7 (checked against 4.7.3; the lab was captured on SITL 4.7.2)
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
source_hash: 26d4647a0ac2
---

## summary
A mission in ArduPilot is a list of commands that the flight controller executes by itself in AUTO mode: take off, fly the waypoints, take a picture, come back. This module explains what a mission is made of, how navigation commands differ from DO and CONDITION commands, how altitude is defined, where home is, and what happens when the link is lost in the middle of a route. The practice runs in SITL on the "route separate from scenario" pattern.

## theory
### Three types of commands
- **NAV**: where to fly. `NAV_TAKEOFF` (22), `NAV_WAYPOINT` (16), `NAV_LOITER_TIME` (19), `NAV_RETURN_TO_LAUNCH` (20), `NAV_LAND` (21). A mission moves from one NAV command to the next.
- **DO**: what to do along the way without changing the route: `DO_CHANGE_SPEED` (178), `DO_SET_SERVO` (183), `DO_SET_CAM_TRIGG_DIST` (206), `DO_JUMP` (177) for loops.
- **CONDITION**: wait for a condition before the next DO command: `CONDITION_DELAY` (112), `CONDITION_DISTANCE`.

The numbers in parentheses are MAV_CMD codes: that is how the commands appear in a mission file and in MAVLink.

### How the list is executed
The mission is stored in the flight controller as a numbered list, and `seq` 0 is always home: on upload the vehicle puts its own home location there, and until home is set it returns zeros (in the download in step 4, line 0 is `0.0000000 0.0000000`). The real commands start at `seq` 1, and the number of commands including home is the read-only parameter `MIS_TOTAL`.

The executor (`libraries/AP_Mission/AP_Mission.cpp`, `advance_current_nav_cmd`) keeps one current NAV command and one current DO command. When the NAV command is complete (an intermediate waypoint with no delay: when the trajectory target has reached the waypoint; a waypoint with a stop: when the vehicle is within `WP_RADIUS_M`; a takeoff: when the altitude is reached), it moves forward through the list: it starts any DO command it meets and makes the next NAV command current. So a DO command placed **after** NAV number N runs at the moment of arrival at waypoint N, that is, it applies to the leg to the next waypoint. In the step 4 run you can see this in the lines `Mission: 2 ChangeSpeed` and `Mission: 3 WP` in the same second, right after the takeoff completes. A CONDITION command holds the following DO commands until its condition is met, but it does not stop the flight to the current waypoint.

### DO_JUMP and DO_CHANGE_SPEED
`DO_JUMP` (177): `param1` is the number of the command to jump to (`seq`), `param2` is how many times to repeat, with −1 meaning forever. A repeat count of 1 means the section between the target and the jump is flown **twice**: the first time in sequence, the second after the jump. In the run: waypoints 3→4, `Mission: 5 Jump 1/1`, 3→4 again, then the jump is skipped and the mission goes on to command 6. The jump counters are reset when the mission is started again, and a finite counter is also zeroed after its loop completes, so if you send the mission back to the start of the loop it runs again (bit 3 of `MIS_OPTIONS`, DontZeroCounter, turns that off, but it is not listed among the options for Copter); the number of `DO_JUMP` commands tracked in one mission is up to 100 on boards in the ≥ 500 kB memory class and 15 on the rest (`AP_Mission.h:29–33`). The target can also be a DO command: it executes, and the flight continues to the NAV command after it; a target of 0 or ≥ `MIS_TOTAL` ends the mission. A `DO_JUMP` with −1 and no exit is an endless circuit until the battery runs down; the only ways out of such a loop are a mode change, by the pilot or the GCS, or a failsafe (battery, RC, GCS) or geofence action.

`DO_CHANGE_SPEED` (178): `param1` is the speed type (0 airspeed, 1 ground speed, 2 climb, 3 descent), `param2` is the speed in m/s, `param3` is the throttle in percent (−1 means no change; Copter ignores it). On Copter, types 0 and 1 both change the horizontal speed `WP_SPD`, and 2 and 3 change `WP_SPD_UP` and `WP_SPD_DN` (`ArduCopter/mode_auto.cpp:1991`); a value ≤ 0 is ignored. The new speed applies until the end of the mission or the next `DO_CHANGE_SPEED`, and the `WP_SPD` parameter itself does not change.

### Leg time
The trajectory generator accelerates the vehicle at no more than `WP_ACC` (2.5 m/s²) to the leg speed v and decelerates before the waypoint, and the acceleration changes no faster than the jerk `WP_JERK` (1 m/s³, `AC_WPNav.cpp:37`). For a leg of length d with a stop at each end, when d is noticeably longer than v²/a:

t ≈ d / v + v / a + a / J,

where J = `WP_JERK`. Without the last term you get a trapezoidal speed profile, a teaching model with no jerk limit (it is what the module's problem calculates).

For 100 m with stops: at 5 m/s ≈ 20 + 2 + 2.5 = 24.5 s, at 10 m/s ≈ 10 + 4 + 2.5 = 16.5 s. An independent run in SITL 4.7.2 with a stop at every waypoint (waypoints with a 3 s delay) gave 24.1–24.6 s and 16.8–16.9 s of movement. In step 4 the intermediate waypoints are flown **without stopping**, so it does not test the formula: the legs there are shorter, 20.6–21.6 s at 5 m/s (≈ d/v plus the turn) and 14.0–14.8 s at 10 m/s, with the first leg after takeoff at 23.2 s. This is a course guideline for the time budget: to the sum of the legs add takeoff, landing, wind, and a 10–20% margin.

### End of the mission
If the last command is an ordinary waypoint and not `NAV_RETURN_TO_LAUNCH` or `NAV_LAND`, Copter **stays in AUTO** when the list ends and holds position (`ModeAuto::exit_mission`: `loiter_start()`); if the position is bad it switches to LAND, and if the vehicle is already on the ground it disarms. In the run, 20 s after the last waypoint: mode AUTO, 20.0 m, armed, speed 0.01 m/s. A vehicle hovering in AUTO burns battery until the battery failsafe triggers, hence the rule (a course guideline): the last command of a mission is `NAV_RETURN_TO_LAUNCH` or `NAV_LAND`. `MIS_OPTIONS` bit 2 (ContinueAfterLand) lets the mission continue after a `NAV_LAND` in the middle of the list, for delivery with a landing.

### Upload and download are a dialog
Upload uses the MAVLink Mission protocol: the client sends `MISSION_COUNT`, then the **vehicle** requests every command by number (ArduPilot 4.7 still sends the older `MISSION_REQUEST(seq)`; the spec and other autopilots use `MISSION_REQUEST_INT`, so accept both), the client answers with `MISSION_ITEM_INT`, and at the end the vehicle sends `MISSION_ACK` (0 is `MAV_MISSION_ACCEPTED`). Download is the mirror image: the client sends `MISSION_REQUEST_LIST`, receives `MISSION_COUNT`, requests every command itself, and answers with `MISSION_ACK` at the end. The coordinates in `MISSION_ITEM_INT` are integers in degrees × 10⁷, and the altitude is a float in meters; frame 3/6 is relative to home. An observation from the run: in the first seconds after SITL starts an upload can be refused, so the step 4 script waits 10 s on the firmware clock.

{{diagram:mavlink-mission-seq|The vehicle drives a mission upload: it requests every command by number itself and re-requests a lost answer.}}

### Reference: mission commands and parameters (Copter 4.7.2)
| Command / parameter | Code / default | Parameters or meaning | Trap |
|---|---|---|---|
| `NAV_WAYPOINT` | 16 | p1 is the delay at the waypoint, s; lat/lon/alt | with no delay the waypoint is flown without stopping |
| `NAV_TAKEOFF` | 22 | alt is the takeoff altitude | on the ground in AUTO you need throttle or `AUTO_OPTIONS` bit 1 |
| `NAV_LAND` | 21 | lat/lon = 0 means in place | without `MIS_OPTIONS` bit 2 the mission ends on it |
| `NAV_RETURN_TO_LAUNCH` | 20 | — | altitude by the RTL rules, including the cone |
| `DO_JUMP` | 177 | p1 is the target `seq`, p2 the repeats, −1 forever | N repeats = N + 1 passes |
| `DO_CHANGE_SPEED` | 178 | p1 is the type 0…3, p2 m/s, p3 throttle % or −1 (Copter ignores it) | applies until the end of the mission |
| `CONDITION_DELAY` | 112 | p1 in s | holds DO commands, not the flight |
| `MIS_TOTAL` | read-only | number of commands including home | |
| `MIS_RESTART` | 0 | 0 Resume Mission, 1 Restart Mission when entering AUTO | |
| `MIS_OPTIONS` | 0 | Copter: bit 0 Clear Mission on reboot, bit 2 ContinueAfterLand | |
| `WP_SPD`, m/s | 10 | horizontal speed (before 4.7, `WPNAV_SPEED`, cm/s) | `DO_CHANGE_SPEED` overrides it |
| `WP_ACC`, m/s² | 2.5 | acceleration (before 4.7, `WPNAV_ACCEL`, cm/s²) | part of t ≈ d/v + v/a + a/J |
| `WP_JERK`, m/s³ | 1 | jerk, the rate of change of acceleration | adds ≈ a/J to a leg with stops |
| `WP_RADIUS_M`, m | 2 | the "reached" radius for a waypoint with a stop; for fly-through waypoints, the corner-cutting radius (before 4.7, `WPNAV_RADIUS`, cm) | intermediate waypoints with no delay are not checked against the radius |
| `AUTO_OPTIONS` | 0 | bit 0 Allow Arming in AUTO, bit 1 Allow Takeoff Without Raising Throttle | for scripts and SITL |

### Altitude
Every waypoint has a reference frame. For missions you almost always use altitude **relative to home** (`MAV_FRAME_GLOBAL_RELATIVE_ALT`, code 3): "100 m" means 100 m above the arming location. Absolute altitude above mean sea level (`MAV_FRAME_GLOBAL`, 0) is rarely needed and easily leads to an error of hundreds of meters. Altitude above terrain needs terrain data.

### Home
The home location for Copter is where the vehicle armed. RTL returns there, not to where the pilot is standing. If you launched from the roof of a car and drove off, home stayed in the old place. You can reset home in the GCS before takeoff.

### Starting and resuming
A Copter mission normally starts with `NAV_TAKEOFF`. Switching to AUTO on the ground with the vehicle armed starts the takeoff once the pilot raises the throttle (or right away, if bit 1 of `AUTO_OPTIONS`, "Allow Takeoff Without Raising Throttle", is set); in SITL use `rc 3 1500`. By default, when you enter AUTO again the mission resumes from the current command; the `MIS_RESTART` parameter makes it restart from the first one.

### Failsafe in a mission
RC loss during AUTO follows `FS_THR_ENABLE` (RTL, Land, SmartRTL…), and continuing the mission is enabled with bit 0 of `FS_OPTIONS`. For autonomous flights beyond visual line of sight you make that decision before takeoff, not after the fact. GCS loss has its own parameter, `FS_GCS_ENABLE`. The battery failsafe (`BATT_FS_LOW_ACT`, `BATT_FS_CRT_ACT`) overrides the mission.

{{lesson:ap-safety-fs|Which failsafe action to choose for an autonomous mission and how to test it in SITL before the flight.}}

### Mission file
Ground stations save a mission as a text file in the `QGC WPL 110` format: one line per command with the number, the current flag, the frame, the command code, four parameters, latitude, longitude, altitude, and the autocontinue flag. A file like that is convenient to keep in git next to the parameters.

### Commands worth knowing by heart
NAV: `NAV_WAYPOINT` (p1 is the delay at the waypoint, s), `NAV_TAKEOFF` (alt), `NAV_LAND`, `NAV_RETURN_TO_LAUNCH`, `NAV_LOITER_TIME/TURNS/UNLIM`, `NAV_SPLINE_WAYPOINT` (spline), `NAV_DELAY`; DO: `DO_SET_SERVO`, `DO_SET_RELAY`, `DO_DIGICAM_CONTROL`, `DO_SET_CAM_TRIGG_DIST` (a picture every N m, the basis of photogrammetry), `DO_CHANGE_SPEED`, `DO_SET_ROI` (point the gimbal or the nose), `DO_JUMP` (a loop, with a counter), `DO_LAND_START` (the entry point of a landing sequence for failsafes), `DO_SET_HOME`; CONDITION: `CONDITION_DELAY`, `CONDITION_DISTANCE`, `CONDITION_YAW`. Execution parameters: `WP_SPD` (horizontal m/s, default 10), `WP_SPD_UP/DN` (2.5 and 1.5 m/s), `WP_RADIUS_M` (waypoint radius, 2 m), `WP_ACC` (2.5 m/s²) (before 4.7, `WPNAV_SPEED`, `WPNAV_SPEED_UP/DN`, `WPNAV_RADIUS`, `WPNAV_ACCEL` in cm/s, cm, and cm/s²), `WP_YAW_BEHAVIOR` (face the next waypoint or not), `MIS_RESTART` (0 resumes from the last command run when entering Auto, 1 restarts from the beginning), `MIS_OPTIONS` (bit 0 clears the mission on reboot; bit 1 uses the distance to land in the battery failsafe (Plane only); bit 2 continues after land), `RTL_*` for the end of the mission.

### Altitudes: three frames and one mistake
Relative (above home, `MAV_FRAME_GLOBAL_RELATIVE_ALT`, the default), absolute (above mean sea level, wrong as soon as the takeoff site changes), terrain (above terrain from SRTM data supplied by the GCS or from a rangefinder: `TERRAIN_ENABLE`, the "Terrain" frame on waypoints, and `WP_RFND_USE`/`RTL_ALT_TYPE`). The classic crash: a mission with absolute altitudes, planned for a different site 300 m higher, so the vehicle tries to go underground or into the sky. The rule (a course guideline): relative altitudes, checked in the GCS with a terrain elevation profile.

{{diagram:mission-jump-order|Execution order of the step 4 mission: DO commands run at leg boundaries, a DO_JUMP with a repeat count of 1 gives a second A–B pass, and with no RTL at the end the vehicle hovers in AUTO.}}

### Worked example: surveying a 300×200 m area
Mission Planner → Survey (Grid): camera (sensor, focal length), altitude 80 m, overlap 75/65% → the planner calculates the line spacing and `DO_SET_CAM_TRIGG_DIST` itself; speed 8 m/s (from the camera's exposure time: blur ≤ 1 px → v·t_exp ≤ GSD); `NAV_TAKEOFF` 80, the survey lines, `DO_SET_CAM_TRIGG_DIST 0` at the end, `NAV_RETURN_TO_LAUNCH`. Checks: the elevation profile, the mission time against the battery capacity (`BATT_LOW_MAH` with a margin for RTL plus reserve capacity for the return), a geofence around the area. A run in SITL with the same mission file is mandatory.

{{diagram:mission-alt-frames|Choosing the altitude frame in a mission: Relative for a flat area, Terrain when the terrain varies, Absolute when an altitude above mean sea level is specified.}}

### Place in the system

- **Receives:** position and the home location from the EKF, since AUTO needs a healthy estimate (`ap-ekf`); the actions on link loss and low battery (`ap-safety-fs`); terrain data for terrain altitudes (`nav-terrain`).
- **Provides:** waypoints and the `WP_SPD` and `WP_ACC` limits to the trajectory generator (`ctl-guidance`); `DO_SET_CAM_TRIGG_DIST` to the survey (`per-mapping`); the mission file to the run in `ap-sitl`.
- **If you get it wrong here:** absolute altitudes in a mission planned for a different site → the vehicle heads underground or into the sky; you catch that with the elevation profile and a run in `ap-sitl`. A mission time longer than the battery capacity allows → the battery failsafe overrides the mission in the middle of the route (`ap-safety-fs`); where the sag comes from is in `f-power`.

## practice
### Step 1. A mission in SITL through the GCS
1. Start SITL: `sim_vehicle.py -v ArduCopter --console --map`.
2. In Mission Planner (Plan) or QGC (Plan) place a TAKEOFF to 20 m, three waypoints, and an RTL.
3. Write the mission to the vehicle and save the `.waypoints` file.
4. Arm, switch to AUTO, and watch. Then try switching to LOITER in the middle of the route and back to AUTO.

### Step 2. The same mission from code
The route is data, the scenario is commands. An example of uploading a route with pymavlink:

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
items += [item(i + 2, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, *wp) for i, wp in enumerate(ROUTE)]  # seq 2, 3, 4: after home (0) and TAKEOFF (1)
items.append(item(len(items), mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH))

m.waypoint_clear_all_send()
m.waypoint_count_send(len(items))
for _ in items:
    req = m.recv_match(type=["MISSION_REQUEST", "MISSION_REQUEST_INT"], blocking=True)
    m.mav.send(items[req.seq])
ack = m.recv_match(type="MISSION_ACK", blocking=True)
print("mission upload:", ack.type)  # 0 = MAV_MISSION_ACCEPTED
```

A mission upload is a dialog: the vehicle requests every item by number itself, so you cannot send them in one batch.

### Step 3. Scenarios on top of a route
Write three scenarios that take the route as a parameter: "fly it", "fly it and take a photo at every waypoint" (`DO_DIGICAM_CONTROL`), "fly it with a motor failure at the second waypoint" (the switch from the Lua module). One route, three scenarios, and no coordinate edits.

### Step 4. DO_JUMP, DO_CHANGE_SPEED, and the end of the list: a SITL run
This step was run on ArduCopter 4.7.2 SITL (the `+` frame, `--speedup 10`, pymavlink 2.4.50) with no MAVProxy and no GCS. The route is a 100 × 100 m square at 20 m, the `ROUTE` dictionary (data); the plan is a list of commands (the scenario): takeoff, a speed of 5 m/s, waypoints A and B, a `DO_JUMP` to A with a repeat count of 1, a speed of 10 m/s, waypoints C and D. There is deliberately **no** RTL at the end, so you can see what Copter does when the list runs out. The script uploads the mission, downloads it back into a `QGC WPL 110` file, flies it, and prints the time of every leg and the top speed on it. Run it with `mkdir run && cd run && python3 ../mission_lab.py ~/ardupilot`; it takes about 1 min of real time.

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

Output of the run (2026-11-26):

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

What to read in the output. `MISSION_ACK type 0` means the upload was accepted. The downloaded file matches the plan: `seq` 2 is `178 1 5 -1` (ground speed 5 m/s, throttle unchanged), `seq` 5 is `177 3 1` (jump to 3, repeat 1), and the waypoint coordinates are home plus 100 m (−35.3623626 = −35.3632610 + 100 / 111319.5; ArduPilot itself uses the spherical constant of 111318.845 m per degree, a difference in the seventh decimal place). Line 0 is zeros: home was not yet set at the time of the upload. The order flown is 3, 4, `Jump 1/1`, 3, 4, 6, 7, 8, so one repeat gave two A–B passes. The speed on the legs after `DO_CHANGE_SPEED 5` is 5.0 m/s and after `DO_CHANGE_SPEED 10` it is 9.9 m/s, although `WP_SPD` = 10 the whole time. Legs without a stop last about d/v plus the turn; the formula from the theory is for a leg with stops. The last line shows the vehicle hovering in AUTO at 20 m: without `NAV_RETURN_TO_LAUNCH` the mission is "over", but the flight is not.

**Automatic log check:** `check_lab_log.py <log.bin> --lab mission` checks that AUTO was engaged, there are ≥ 3 navigation commands, there are "Reached" messages, there is an RTL/LAND at the end, satellites ≥ 6, and there are no EKF/GPS errors.

**Reference for the self-check.** Step 2: the script prints `mission upload: 0`, which is `MAV_MISSION_ACCEPTED`; if it hangs on the upload, the items were sent in one batch without waiting for the requests: the vehicle requests each one by number itself; if it prints 13 (`MAV_MISSION_INVALID_SEQUENCE`), the `seq` field of an item does not match its position in the list: the waypoints start at seq 2, after home and TAKEOFF. Step 3: all three scenarios receive the same `ROUTE` as a parameter, and there is not a single coordinate in the scenario code, so changing the route requires no scenario edits. The automatic check passes on every item for the log of every run: AUTO engaged, at least three navigation commands, "Reached" present, RTL/LAND at the end. Step 4, typical wrong results: (1) after the jump waypoints 3–4 are flown three times, because `param2` is 2 (N repeats give N + 1 passes); (2) the speed on the first leg is 10 m/s instead of 5, because `DO_CHANGE_SPEED` was placed after waypoint A and not before it, so it applies only from the next leg; (3) the vehicle "hung" after waypoint D, which is not a fault but the end of a list with no RTL; (4) the upload was refused, because the script sent `MISSION_COUNT` in the first seconds after SITL started.

Self-check: the lab is done when in step 2 the script prints `mission upload: 0`; in step 3 three scenarios use one `ROUTE` with no coordinates in the code; in step 4 you get `MISSION_ACK type 0`, the downloaded file matches the plan table line by line (codes 16, 22, 178, 16, 16, 177, 178, 16, 16), the order of `Reached` is 3, 4, 3, 4, 7, 8, the speed on legs 3–4 is 5.0 ± 0.2 m/s and on legs 7–8 it is 10 ± 0.3 m/s, the time of the 100-meter legs is 20–23 s at 5 m/s and 13.5–15.5 s at 10 m/s, and 20 s after waypoint 8 the mode is AUTO with the vehicle armed at 20 ± 0.5 m; if you add `NAV_RETURN_TO_LAUNCH` at the end and run it again, the vehicle lands at home and disarms.

## diagnostics
- **Symptom:** AUTO does not start, the vehicle sits there
  - Possible cause: the mission is not loaded, `NAV_TAKEOFF` is not the first command, or the vehicle is not armed.
  - What to do: read the mission back from the vehicle, check the first command and the GCS messages.
- **Symptom:** the vehicle flies 100 m higher than expected
  - Possible cause: absolute altitude instead of relative.
  - What to do: check the frame of every waypoint in the mission file.
- **Symptom:** RTL returns to a place where the pilot is not
  - Possible cause: home is the arming location.
  - What to do: reset home before takeoff after moving.
- **Symptom:** the mission upload hangs
  - Possible cause: items sent without waiting for the requests, or a wrong `seq`.
  - What to do: answer `MISSION_REQUEST(_INT)` by number, check `MISSION_ACK`.
- **Symptom:** in Auto the vehicle went into the ground or into a climb after a change of site
  - Possible cause: absolute altitudes in the mission.
  - What to do: relative or terrain altitudes; check the elevation profile in the GCS.
- **Symptom:** after the last waypoint the vehicle hovers in place in AUTO
  - Possible cause: there is no `NAV_RETURN_TO_LAUNCH`/`NAV_LAND` at the end of the mission; at the end of the list Copter switches to holding position within AUTO.
  - What to do: make the last command RTL or LAND; right now, switch to RTL.
  - Consequences: hovering until the battery failsafe.
- **Symptom:** a `DO_JUMP` loop is flown one time more or fewer than you expected
  - Possible cause: `param2` is the number of repeats, not passes; N repeats = N + 1 passes; −1 is forever.
  - What to do: count the passes from `Mission: N Jump k/N` in the GCS messages.
- **Symptom:** `DO_CHANGE_SPEED` "has no effect" on the leg you wanted
  - Possible cause: a DO command runs when the previous NAV command completes, so it affects the leg **after** the waypoint it follows.
  - What to do: place it before the NAV waypoint of the leg that needs the new speed; verify from the speed in the log.
- **Symptom:** after a landing in the mission the vehicle does not disarm or carries on
  - Possible cause: `MIS_OPTIONS` bit 2 (ContinueAfterLand), `LAND_*`.
  - What to do: set it deliberately; test in SITL.

## references
- Planning a Mission with Waypoints and Events — ArduPilot Copter | https://ardupilot.org/copter/docs/common-planning-a-mission-with-waypoints-and-events.html | primary | A
- Copter Mission Command List — ArduPilot | https://ardupilot.org/copter/docs/mission-command-list.html | primary | A
- MAVLink Mission Protocol | https://mavlink.io/en/services/mission.html | primary | A
- MAVLink common message set (common.xml) | https://github.com/mavlink/mavlink/blob/master/message_definitions/v1.0/common.xml | primary | A
- AP_Mission.cpp (MIS_* parameters, DO_JUMP, command execution), Copter-4.7.2 | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_Mission/AP_Mission.cpp | primary | A
- mode_auto.cpp (DO_CHANGE_SPEED, end of mission), Copter-4.7.2 | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/ArduCopter/mode_auto.cpp | primary | A

## checklist
- I know the difference between NAV, DO, and CONDITION commands
- Every waypoint in the mission uses relative altitude
- I understand where home is and how to reset it
- The radio, GCS, and battery failsafes are configured before an autonomous flight
- The mission is uploaded from code as a request–response dialog
- The route is stored separately from the scenario
- The last command of the mission is RTL or LAND
- The number of `DO_JUMP` loop passes and the placement of `DO_CHANGE_SPEED` are tested in SITL
