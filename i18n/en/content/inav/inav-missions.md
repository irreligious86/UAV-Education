---
id: inav-missions
title: "INAV Missions: Waypoints and CLI wp"
level: L2
readingTime: 20 min
firmware: INAV 7.0+
status: published
added: 2026-11-08
tags:
  - missions
  - waypoints
related:
  - inav-gps
  - ap-missions
next:
  - inav-wing
source: content/inav/inav-missions.md
source_hash: df5a988d82be
---

## summary
An INAV mission is a list of points with actions that the aircraft executes in NAV WP mode. This module shows what a point is made of, which actions exist (WAYPOINT, POSHOLD_TIME, RTH, JUMP, SET_POI, LAND), how to write a mission through the configurator and through the CLI with the `wp` command, where the altitude lives, and how INAV protects you from taking off with a “foreign” mission.

## theory
### Point structure
In the CLI: `wp <n> <action> <lat> <lon> <alt> <p1> <p2> <p3> <flag>`.

- `lat`, `lon` — degrees × 10⁷ (123456789 = 12.3456789°).
- `alt` — centimeters; bit 0 in `p3` sets whether it's relative to home (0) or above sea level (1).
- `action`: 1 WAYPOINT, 3 POSHOLD_TIME, 4 RTH, 5 SET_POI, 6 JUMP, 7 SET_HEAD, 8 LAND.
- `p1`: for WAYPOINT — speed to the point (cm/s; multirotor only and only if 50 < p1 < `nav_auto_speed`); for POSHOLD_TIME — time in seconds; for RTH — p1 > 0 allows landing; for JUMP — target index.
- `p2`: for POSHOLD_TIME — speed; for JUMP — number of repeats.
- `flag` of the last point — 165 (0xA5).

`wp load` loads the list from EEPROM, `wp save` saves it, `wp reset` clears it.

### Execution
NAV WP mode is enabled with a switch. The aircraft flies from point to point at `nav_auto_speed` (or the speed from `p1`); the waypoint acceptance radius is `nav_wp_radius`. JUMP gives you loops, SET_POI turns the camera toward a point of interest, LAND lands at the point.

### Protection against a foreign mission
If a mission is loaded whose first point is farther than `nav_wp_max_safe_distance`, arming is blocked. This protects against the “drove to a different field with yesterday's mission” scenario. The bypass is `nav_extra_arming_safety = ALLOW_BYPASS` plus the yaw stick while arming, and it really is a bypass.

### Multiple missions
The configurator can store several missions in one waypoint list and switch between them; Programming Framework operands for waypoints refer to the selected mission.

### Versus ArduPilot
In INAV a mission is simpler: no CONDITION commands, no DO commands as such (some actions go through user actions in `p3` and logic conditions), upload via MSP/CLI, and the MAVLink mission protocol (MISSION_COUNT/MISSION_ITEM) is supported in a simplified way. For surveying an area or flying a circuit it's enough; for complex logic — Programming Framework or ArduPilot.

### Execution and safety parameters
`nav_auto_speed` (500 cm/s) — default speed, `nav_wp_radius` (100 cm) — waypoint acceptance radius (bigger for a wing, 1000–3000), `nav_wp_max_safe_distance` (100 m; 0 — disable) — first point farther than this from the arming location → arming blocked (“yesterday's mission on a new field”). A wing passes points along an arc, a multirotor stops at them; `nav_mc_wp_slowdown` controls braking at the point.

### Worked example: surveying a 200×100 m area
Altitude 60 m, 70% side overlap between frames with a camera horizontal FOV of 84° (coverage across the pass ≈ 2·60·tan42° ≈ 108 m) → spacing between passes 108 × (1 − 0.7) ≈ 32 m → 4 passes over the 100 m width; points: WAYPOINT ×8 with `p1` = 0 (speed `nav_auto_speed` = 5 m/s), and at the end RTH with `p1` = 1 (landing allowed). Time: ~1 km of path / 5 m/s ≈ 3.5 min + turns. In the CLI that's 9 `wp` lines, the last one with flag 165. Camera trigger — via PINIO/user action through `p3`, or interval shooting on the camera itself. Check the mission on the configurator map: no point over people/a road, altitude above the trees.

### What happens when something breaks during a mission
- **RC loss in NAV WP**: the INAV failsafe kicks in (`failsafe_procedure`, usually RTH); by default it does **not** continue the mission — that's the pilot's decision, not the firmware's. Make sure the RTH altitude clears obstacles along the whole route.
- **GPS loss**: navigation modes become impossible — the aircraft goes into an emergency landing (`nav_emerg_landing_speed`). A mission over water or forest needs altitude margin and a clear plan for “where it will come down”.
- **Low battery**: plan the mission for 60–70 % of capacity and watch the OSD warnings; don't count on the firmware aborting the mission in time on its own.
- **The pilot switched NAV WP off**: the aircraft returns to the mode selected by the switch; what happens when you switch it back on — continue or start over — is set by `nav_wp_mission_restart`.

{{diagram:inav-mission-flow|INAV mission lifecycle: points, upload, save, start with WP mode and behavior after the last point.}}

## practice
### Step 1. A mission in the configurator
1. Mission Control tab: place 3–4 points, altitude 30 m relative to home.
2. The last one — RTH with landing (or without, for a wing).
3. Save to the FC (Save to FC) and to a file.

### Step 2. The same mission in the CLI
```
wp reset
wp 0 1 505000000 304000000 3000 0 0 0 0
wp 1 1 505005000 304005000 3000 0 0 0 0
wp 2 3 505010000 304000000 3000 20 0 0 0
wp 3 4 0 0 0 1 0 0 165
wp save
wp
```

Point 2 — POSHOLD_TIME 20 s, point 3 — RTH with landing, last flag 165.

### Step 2b. A CLI generator from a list of coordinates
Converting degrees to “× 10⁷” and centimeters by hand is a sure way to be off by an order of magnitude. A script:
```python
def wp_cli(points, alt_m=30, rth_land=True):
    # points: [(lat, lon), ...] in degrees -> INAV CLI lines; altitude relative to home
    lines = ["wp reset"]
    for i, (lat, lon) in enumerate(points):
        lines.append(f"wp {i} 1 {round(lat * 1e7)} {round(lon * 1e7)} {round(alt_m * 100)} 0 0 0 0")
    n = len(points)
    lines.append(f"wp {n} 4 0 0 0 {1 if rth_land else 0} 0 0 165")   # RTH, last point flag 0xA5
    lines += ["wp save", "wp"]
    return "\n".join(lines)

print(wp_cli([(50.4500000, 30.5200000), (50.4505000, 30.5205000), (50.4510000, 30.5200000)]))
```
Paste the output into the CLI, then compare it with what the Mission Control tab shows. A difference in the coordinates at the 7th decimal place is normal rounding; at the 1st–2nd, it's swapped lat/lon order.

### Step 3. Flight
1. 3D fix, home recorded, mission loaded (`wp` shows the list).
2. Arm, ANGLE, take off manually to a safe altitude.
3. Enable NAV WP with the switch. Watch the points being passed in the OSD.
4. At any moment — switch NAV WP off and take back control.

### Lab
Write one mission two ways (configurator and CLI via the generator), compare the `wp` output — it should match. Run it with POSHOLD_TIME and RTH. For each point of the route, write down what will happen on RC and GPS loss exactly there (RTH altitude above obstacles, emergency landing spot).

## diagnostics
- **Symptom:** won't arm with a mission loaded
  - Possible cause: the first point is farther than `nav_wp_max_safe_distance`.
  - What to do: rewrite the mission for the current location or reset it.
- **Symptom:** the aircraft goes to the points but doesn't land at the end
  - Possible cause: RTH has p1 = 0 (landing not allowed) or `nav_rth_allow_landing` = NEVER.
  - What to do: set p1 = 1 and check `nav_rth_allow_landing`.
- **Symptom:** the mission altitude is wrong
  - Possible cause: bit 0 in p3 (absolute altitude) or mixing up centimeters and meters.
  - What to do: check `p3` and the `alt` units.
- **Symptom:** `wp` shows an empty list after a reboot
  - Possible cause: `wp save` wasn't run.
  - What to do: save and check with `wp load`.
- **Symptom:** the aircraft flies past the points
  - Possible cause: `nav_wp_radius` is too small for the speed (especially on a wing).
  - What to do: bigger radius, lower speed at the points.

## references
- INAV Navigation — NAV WP and `wp` CLI | https://github.com/iNavFlight/inav/blob/master/docs/Navigation.md | primary | A
- INAV Controls — arming safety | https://github.com/iNavFlight/inav/blob/master/docs/Controls.md | primary | A

## checklist
- I understand the point fields and units (degrees × 10⁷, centimeters)
- The last point has flag 165
- The mission is rewritten for the current field, arming isn't blocked
- NAV WP is on a switch, control comes back instantly
- The mission is saved to a file and to the FC
