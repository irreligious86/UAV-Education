---
id: inav-missions
title: "INAV missions: waypoints and the CLI wp command"
level: L2
readingTime: 20 min
firmware: INAV 9.1 (checked against 9.1.0)
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
source_hash: a20cffcc9f5c
---

## summary
An INAV mission is a list of waypoints with actions that the aircraft executes in NAV WP mode. This module shows what a waypoint consists of, which actions exist (WAYPOINT, POSHOLD_TIME, RTH, JUMP, SET_POI, LAND), how to write a mission through the configurator and through the CLI with the `wp` command, where the altitude lives, and how INAV protects you from taking off with the “wrong” mission.

## theory
### Waypoint structure
In the CLI: `wp <n> <action> <lat> <lon> <alt> <p1> <p2> <p3> <flag>`.

- `lat`, `lon` — degrees × 10⁷ (123456789 = 12.3456789°).
- `alt` — centimeters; bit 0 of `p3` selects relative to home (0) or above mean sea level (1).
- `action`: 1 WAYPOINT, 3 POSHOLD_TIME, 4 RTH, 5 SET_POI, 6 JUMP, 7 SET_HEAD, 8 LAND.
- `p1`: for WAYPOINT and LAND — the speed to the waypoint (cm/s; multirotor only; used when 50 ≤ p1 ≤ `nav_max_auto_speed` (1000), above that it is clipped to `nav_max_auto_speed`, below 50 the aircraft flies at `nav_auto_speed`); for POSHOLD_TIME — the time in seconds; for RTH — p1 > 0 allows landing; for JUMP — the target index.
- `p2`: for POSHOLD_TIME — the speed to the waypoint (the same rules as for `p1` of WAYPOINT); for JUMP — the number of repeats.
- `p3` — a bitfield: bit 0 (1) — the altitude type, bits 1–4 (2, 4, 8, 16) — the user action 1–4 flags of this waypoint. `p3 = 6` — altitude relative to home, actions 1 and 2 set.
- `flag`: 0 — an ordinary waypoint, 165 (0xA5) — the last waypoint of the mission, 72 (0x48) — the waypoint takes the home coordinates instead of `lat`/`lon` (the same as a waypoint with `lat = lon = 0`). The CLI rejects any other flag.

Capacity: `NAV_MAX_WAYPOINTS` = 120 waypoints for all missions together (`target/common.h` 9.1.0); in 9.1.0 only FISHDRONEF4 sets its own value — 60, and there are no official builds of that target (`SKIP_RELEASES`). The waypoint number starts at 0 in the CLI and at 1 in Mission Control.

### JUMP rules: checked at arming
A JUMP error does not surface in flight: arming is blocked by the `NAV` flag (`navigationIsBlockingArming()`, `navigation.c` 9.1.0). The rules in CLI numbering (from 0):
1. A JUMP cannot be the first waypoint of a mission.
2. The target `p1` is the number of an existing waypoint: `p1` is less than the number of waypoints.
3. You cannot jump to an adjacent waypoint or to itself: for a JUMP with number n the targets n − 1, n and n + 1 are forbidden.
4. The target is a waypoint with coordinates: WAYPOINT, POSHOLD_TIME or LAND (not RTH, SET_POI, SET_HEAD or another JUMP).
5. `p2` (repeats) is not less than −1; −1 means forever.

The check: the list `wp 0 1 …`, `wp 1 1 …`, `wp 2 1 …`, `wp 3 6 0 0 0 0 2 0 0`, `wp 4 4 0 0 0 1 0 0 165` — a JUMP with number 3 to waypoint 0 twice, the rules are met. With `p1 = 2` (adjacent) arming is blocked. In Mission Control the numbers are one higher: there the same target is waypoint 1.

`wp load` loads the list from EEPROM, `wp save` saves it, `wp reset` clears it. When restoring from a backup (`inav-cli-backup`) the `wp` lines of a `diff all` go into RAM only: an ordinary `save` does not write them, and after a reboot the list will be the old one. The mission is saved by `wp save` before `save`; it validates the list (the last waypoint has flag 165) and at the same time writes all unsaved CLI settings to EEPROM itself — run it when the paste output has no red lines.

### Execution
NAV WP mode is activated with a switch. The aircraft flies from waypoint to waypoint at `nav_auto_speed` (or the speed from `p1`), and the waypoint acceptance radius is `nav_wp_radius`. A mission saved with `wp save` does not get into memory by itself after power-up: `nav_wp_load_on_boot` = OFF, and it is loaded by `wp load` (a repeat `wp load` with a mission already loaded unloads it), by the button in Mission Control or by the load stick command (`inav-adjustments`). Set it to ON if the aircraft flies the same mission without a laptop in the field. JUMP gives loops, SET_POI points the camera at a point of interest, LAND lands at the waypoint.

### Protection against the wrong mission
If a mission is loaded whose first waypoint is farther than `nav_wp_max_safe_distance`, arming is blocked. This protects against the scenario “arrived at a different field with yesterday's mission”. The bypass is the yaw stick held right while arming (in Mode 2 the left stick down and right), regardless of `nav_extra_arming_safety`, and it is exactly that, a bypass; 0 in `nav_wp_max_safe_distance` (100 m by default) disables the check. `nav_extra_arming_safety = ALLOW_BYPASS` (the default in 9.1, as in 8.0) concerns a different block — arming without a GPS fix.

### Several missions (multi-mission)
Up to 9 missions sit one after another in a single waypoint list (`navigation.c`, `USE_MULTI_MISSION` is present in all targets): each ends with a waypoint with flag 165, and the end of the whole file is one more entry with flag 165 and the RTH action right after the last mission. Mission Control saves and loads such a file as a whole, and `wp save` writes it to EEPROM. `wp save` resets the selected mission to 1 (`navigation.c`), so select the mission again after saving. The active mission is `nav_wp_multi_mission_index` (1–9, default 1), and the OSD shows its number. There are four ways to select a mission:

| Method | When it works | How |
|---|---|---|
| CLI, Configurator | disarmed | `set nav_wp_multi_mission_index = 2`, `save` |
| Stick command | disarmed, throttle low | roll right — next, roll left — previous, yaw and pitch centered |
| `adjrange`, function 59 | armed, not in WP mode | the adjustment channel steps by 1 from 1 to the number of missions (`inav-adjustments`) |
| The MISSION CHANGE mode (id 59) | armed, with two or more missions | while the mode is active NAV WP does not start, and every activation of the NAV WP switch moves to the next mission in a cycle; turn MISSION CHANGE off and the selected mission is loaded |

The check before takeoff: the mission number in the OSD is the one you need, and its first waypoint is closer than `nav_wp_max_safe_distance`. Of the Programming Framework waypoint operands, the waypoint number, the action and the distance refer to the selected mission; the user-action operands 6–13 in 9.1.0 read `p3` by an index counted from the start of the whole list (`logic_condition.c`; read from the code, not checked in flight), so they are correct only for mission 1: with mission 2…9 selected they take the flags of the first mission's waypoints. Put camera/PINIO user actions only into the first mission of a multi-mission file, or check on the bench.

### User actions: how a mission waypoint controls PINIO
Bits 1–4 of `p3` do not switch anything by themselves. The chain in 9.1.0 is this: a bit in `p3` → a waypoint operand of type 7 (6–9 — the action is active on this leg) → a logic condition with operation 38 (Override RC Channel) overrides the channel that carries the range of the USER1–4 mode → the USER mode switches its PINIO (`pinio_box1..4`). Which leg is “flagged” is decided by the operand number (`logic_condition.c` 9.1.0): 6–9 read `p3` of the waypoint the aircraft is flying **from**, 10–13 — of the waypoint it is flying **to**. An example: waypoint 2 with `p3 = 2` (user action 1), the rule `logic 0 1 -1 1 7 6 0 1 0` (“action 1 active = 1”), the rule `logic 1 1 0 38 0 12 0 2000 0` (while rule 0 is true, channel 12 = 2000 µs), `aux` USER1 on channel 12 in the range 1700–2100, `pinio_box1` = 47 (USER1). PINIO1 is on over the leg from waypoint 2 to waypoint 3; with operand 10 instead of 6 — over the leg from waypoint 1 to waypoint 2. A walkthrough with a distance-based camera shutter and a bench check is in `inav-led-pinio-beeper`, the operation and operand numbers are in `inav-ipf`. In 9.1.0 operands 6–13 take `p3` by an index counted from the start of the whole waypoint list, so in a multi-mission file they are right only for mission 1 (read from the code, not checked in flight; see the multi-mission section above).

{{diagram:inav-wp-user-action-chain|A p3 bit switches PINIO only through the chain logic condition → channel override → USER mode → pinio_box; operand 6 flags the leg from the waypoint, operand 10 — the leg to the waypoint.}}

### Compared with ArduPilot
An INAV mission is simpler: there are no CONDITION commands and no DO commands as such (some actions go through the user actions in `p3` and logic conditions), upload is over MSP/CLI, and the MAVLink mission protocol (MISSION_COUNT/MISSION_ITEM) is supported in a simplified form (what exactly the handler accepts is in `inav-telemetry-gcs`). For surveying an area and flying a route that is enough; for complex logic use the Programming Framework or ArduPilot.

### Execution and protection settings
`nav_auto_speed` (500 cm/s) — the default speed, `nav_wp_radius` (100 cm) — the waypoint acceptance radius (larger for a fixed wing, 1000–3000), `nav_wp_max_safe_distance` (100 m; 0 — off) — a first waypoint farther than this from the arming point → arming is blocked (“yesterday's mission at a new field”). A multirotor slows down and turns at a waypoint (`nav_mc_wp_slowdown` = ON); OFF — it turns on the move. Speed: `nav_auto_speed` (500 cm/s) by default, the waypoint's `p1` — no higher than `nav_max_auto_speed` (1000 cm/s); both settings are multirotor only. A fixed wing flies at cruise throttle and passes a waypoint according to `nav_fw_wp_turn_smoothing`: OFF (default) — it flies to the acceptance radius and only then turns, ON — it enters a loiter turn so that the waypoint lies on the arc, ON-CUT — it cuts the corner and does not reach the waypoint itself. For waypoint photography — OFF or ON; ON-CUT — when smoothness matters more than hitting the point.

### A worked example: surveying a 200×100 m area
Altitude 60 m, 70% side overlap with a camera horizontal FOV of 84° (the swath across the track ≈ 2·60·tan42° ≈ 108 m) → the line spacing is 108 × (1 − 0.7) ≈ 32 m → 4 flight lines for 100 m of width; the waypoints: WAYPOINT ×8 with `p1` = 0 (the speed is `nav_auto_speed` = 5 m/s), RTH at the end with `p1` = 1 (landing allowed). The time: ~1 km of path / 5 m/s ≈ 3.5 min + the turns. In the CLI that is 9 `wp` lines, the last with flag 165. The camera trigger is a logic condition on a user action from `p3`: the action itself switches nothing, a rule with operation 38 overrides the channel of the USER mode, and PINIO follows the mode (`inav-led-pinio-beeper`); or interval shooting on the camera itself. Check the mission on the map in the configurator: no waypoint over people or a road, the altitude above the trees.

### What happens when something breaks during a mission
- **RC loss in NAV WP**: `failsafe_mission_delay` decides (0–600 s, −1; default 0). 0 — the failsafe procedure (`failsafe_procedure`, usually RTH) starts immediately, as without a mission; N — the mission continues for another N seconds, and if the link has not come back, the procedure starts; −1 — the procedure does not start at all, the mission runs to the end, and after that its last waypoint applies (RTH with landing or a hold). −1 is chosen for missions beyond link range, and then the last waypoint must be RTH. Check that the RTH altitude is above the obstacles along the whole route.
- **GPS loss**: navigation modes are impossible; after `nav_position_timeout` (5 s) without a position estimate the aircraft switches to an emergency landing at `nav_emerg_landing_speed` (in detail in `inav-gps`). A mission over water or forest needs an altitude margin and a clear plan of “where it comes down”.
- **Low battery**: plan the mission for 60–70 % of the capacity and watch the OSD warnings; do not count on the firmware to abort the mission in time by itself.
- **The pilot turned NAV WP off**: the aircraft returns to the mode selected by the switches; what happens when it is turned on again — resume or start over — is set by `nav_wp_mission_restart`.

{{diagram:inav-mission-flow|The life cycle of an INAV mission: waypoints, loading, saving, starting with WP mode and the behavior after the last waypoint.}}

### Place in the system

- **Receives:** the position estimate and home (`inav-gps`); the speed `nav_auto_speed` and the acceptance radius `nav_wp_radius`; the failsafe procedure (`inav-setup-scratch`); for a fixed wing — passing waypoints on an arc and a larger radius (`inav-wing`).
- **Provides:** the route to NAV WP mode; the mission waypoints as logic condition operands (`inav-ipf`); the arming block if the first waypoint is farther than `nav_wp_max_safe_distance` (`inav-intro`).
- **If you get it wrong here:** the route is planned without regard to the RTH altitude → on RC loss the mission does not continue, failsafe triggers, and the aircraft returns below the obstacles (`inav-gps`, `inav-setup-scratch`). You arrived at a different field with yesterday's mission → arming is blocked, and the reason can be read in the OSD and `status` (`inav-intro`); the yaw stick bypass removes the protection, not the error.

## practice
### Step 1. A mission in the configurator
1. The Mission Control tab: place 3–4 waypoints, altitude 30 m relative to home.
2. The last one is RTH with landing (or without, for a fixed wing).
3. Save to the FC (Save mission to FC) and to a file.

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

Waypoint 2 is POSHOLD_TIME 20 s, waypoint 3 is RTH with landing, the last flag is 165.

### Step 2b. A CLI generator from a list of coordinates
Converting degrees to “× 10⁷” and to centimeters by hand is a sure way to be off by an order of magnitude. The script:
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
Paste the output into the CLI, then compare it with what the Mission Control tab shows. A difference in the coordinates in the 7th decimal place is normal rounding; in the 1st–2nd — an error in the lat/lon order.

### Step 3. Flight
1. A 3D fix, home recorded, the mission loaded (`wp` shows the list).
2. Arm, ANGLE, take off by hand to a safe altitude.
3. Activate NAV WP with the switch. Watch the waypoints being passed in the OSD.
4. At any moment — turn NAV WP off and take control.

### Lab
Write one mission in two ways (the configurator and the CLI through the generator) and compare the `wp` output — it must match. A check of the generator on the coordinates from step 2b: the first `wp` line after `wp reset` is `wp 0 1 504500000 305200000 3000 0 0 0 0`, the last waypoint is `wp 3 4 0 0 0 1 0 0 165`; if latitude and longitude are swapped, the point moves already in the 1st–2nd decimal place. Run it with POSHOLD_TIME and RTH. For each waypoint of the route write down what happens on RC loss and GPS loss right there (the RTH altitude above the obstacles, the place of the emergency landing).

## diagnostics
- **Symptom:** it does not arm with a mission loaded
  - Possible cause: the first waypoint is farther than `nav_wp_max_safe_distance`.
  - What to do: rewrite the mission for the current location or reset it.
- **Symptom:** the aircraft flies to the waypoints but does not land at the end
  - Possible cause: the RTH has p1 = 0 (landing not allowed) or `nav_rth_allow_landing` = NEVER.
  - What to do: set p1 = 1 and check `nav_rth_allow_landing`.
- **Symptom:** the mission altitude is wrong
  - Possible cause: bit 0 in p3 (absolute altitude) or centimeters confused with meters.
  - What to do: check `p3` and the units of `alt`.
- **Symptom:** `wp` shows an empty list after a reboot
  - Possible cause: `wp save` was not run.
  - What to do: save and check `wp load`.
- **Symptom:** the aircraft flies past the waypoints
  - Possible cause: `nav_wp_radius` is too small for the speed (especially a fixed wing).
  - What to do: a larger radius, a lower speed at the waypoints.

## references
- INAV Navigation — NAV WP and `wp` CLI | https://github.com/iNavFlight/inav/blob/master/docs/Navigation.md | primary | A
- INAV Controls — arming safety | https://github.com/iNavFlight/inav/blob/master/docs/Controls.md | primary | A

## checklist
- I understand the waypoint fields and units (degrees × 10⁷, centimeters)
- The last waypoint has flag 165
- The mission is rewritten for the current field, arming is not blocked
- NAV WP is on a switch, control comes back instantly
- The mission is saved to a file and to the FC
