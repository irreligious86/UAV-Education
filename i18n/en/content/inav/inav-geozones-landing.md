---
id: inav-geozones-landing
title: "Geozones, safehome, trackback and fixed-wing autoland in INAV"
level: L3
readingTime: 70 min
firmware: INAV 9.1 (checked against 9.1.0)
status: published
added: 2026-11-20
tags:
  - INAV
  - geozones
  - safehome
  - RTH
  - trackback
  - autoland
  - fixed wing
related:
  - inav-gps
  - inav-wing
  - inav-setup-wing
  - inav-missions
  - inav-cli-backup
  - inav-ipf
next:
  - inav-ipf
source: content/inav/inav-geozones-landing.md
source_hash: fa58660992d3
---

## summary
RTH from `inav-gps` answers the question “at what altitude to fly home”. This module answers the rest: where you must not fly (geozones), where to actually land (safehome), which way to return (trackback) and how a fixed wing builds a landing pattern with a glide slope instead of a spiral into the ground (`fwapproach` and `nav_fw_land_*`). Everything is worked through from the INAV 9.1.0 source: the CLI line formats, the units, the defaults, the geometry the code builds, and the cases where the protection silently turns itself off. The lab needs no hardware: decode the zones and decide what INAV does in eight aircraft positions, select a safehome, build the approach pattern for a given wind and find three errors in a config.

## theory
### Four mechanisms and what connects them
This module covers four add-ons to RTH: geozones, safehome, trackback and fixed-wing autoland. Read in order: first the common units and the coordinate conversion (this section), then geozones — the line format, the “inside” test, initialization and arming, the zone actions and their link to RTH; after them safehome and trackback, and at the end `fwapproach` and the approach geometry. The sections on zone actions and on aborting a landing contain warnings about cases where the automation takes control away or flies the aircraft down: read them before the first flight with zones. Basic RTH and home are in `inav-gps`, the old fixed-wing landing and the wind estimate in `inav-wing`, fixed-wing failsafe in `inav-setup-wing`, the rangefinder for the flare in `inav-sensors-extra`.

All four work on top of RTH and store coordinates the same way: **latitude and longitude are integers, degrees × 10⁷; altitudes are in centimeters**. 50.0012600° is written as `500012600`. Coordinates from maps with six decimal places are padded with a zero to seven.

Inside the firmware everything is converted to local centimeters from the first GPS fix point (`geoConvertGeodeticToLocal()` in `navigation_geo.c`):

- north: x = Δlat × 1.113195 cm;
- east: y = Δlon × 1.113195 × cos(origin latitude) cm.

Δlat and Δlon are differences of the integer values. One unit of latitude is 1.11 cm, one unit of longitude at latitude 50° is 0.716 cm. These two formulas solve all the practice of this module.

| Mechanism | CLI command | How many | Build condition |
|---|---|---|---|
| Geozones | `geozone`, `geozone vertex`, `feature GEOZONE` | 63 zones (id 0–62), 126 vertices for all of them | `USE_GEOZONE`: more than 512 KB of flash and GPS |
| Safehome | `safehome` | 8 (indexes 0–7) | `USE_SAFE_HOME`, present everywhere |
| Trackback | the `nav_rth_trackback_*` settings | 50 points, a ring buffer | everywhere |
| Fixed-wing approach | `fwapproach` | 17 slots: 0–7 for safehomes, 8–16 for missions | `USE_FW_AUTOLAND`, present everywhere |

The condition `MCU_FLASH_SIZE > 512` (`target/common.h`) cuts off the STM32F411 and F722: they have no `geozone` command at all. F405, F427, F745, F765, H743, AT32F435 have it.

### Geozones: the zone line and the vertex line
The zone format (exactly eight numbers, otherwise `Parse error`):

`geozone <id> <shape> <type> <min alt> <max alt> <sea level> <action> <vertex count>`

| Field | Values | What matters |
|---|---|---|
| shape | 0 — circular, 1 — polygon | a circle takes 2 vertices, a polygon — 3 or more |
| type | 0 — exclusive (NFZ, no-fly zone), 1 — inclusive (FZ, fly zone) | |
| min alt, cm | 0 — “from the ground, no action at the lower limit” | for the lower limit to work from the ground, use −1 or lower |
| max alt, cm | 0 — no upper limit | at run time it becomes INT32_MAX |
| sea level | 0 — relative to home altitude, 1 — above mean sea level | at initialization the home altitude is subtracted from both altitudes |
| action | 0 NONE, 1 AVOID, 2 POS_HOLD, 3 RTH | on a multirotor AVOID is replaced with POS_HOLD |
| vertex count | 1…126 | must match the number of `geozone vertex` lines |

The vertex format: `geozone vertex <zone id> <vertex idx> <lat> <lon>`. The vertices of a polygon are numbered from 0 **counterclockwise**, and the sides do not cross. For a circle vertex 0 is the center, and in vertex 1 the `lat` field holds the **radius in centimeters** (`geoZoneInit()`: `radius = geoZoneVertices(i)->lat`); `lon` is not used.

Service forms: `geozone` and `geozone vertex` without arguments print the tables, `geozone reset [id]` erases a zone with its vertices, `geozone vertex reset [zone [idx]]` — the vertices. The zone editor lives in the Configurator on the Mission Control tab (the Geozones button, saving — “Save Eeprom Geozones and reboot”). The documentation explicitly asks you not to edit zones by hand in the CLI: the editor checks the vertex order and crossings, the CLI does not. Reading the lines and moving them through `diff all` is fine (`inav-cli-backup`).

Two CLI traps in 9.1.0. The id check is written as `idx > MAX_GEOZONES_IN_CONFIG`, so `geozone 63 …` is accepted although the array ends at 62: do not use id 63. And number the zones consecutively from 0: `geoZoneInit()` in places indexes the working array with the zone number from the config, and gaps break the altitude handling.

### When the aircraft is “inside” a zone
`isInGeozone()` checks the plan view first, then the altitude:

- circle: the distance to the center is **less than** the radius;
- polygon: a ray crossing test (`isPointInPloygon()`), and a point on a side also counts as inside;
- altitude: `(z ≥ min or min = 0) and z ≤ max`, z being the altitude above the home point.

Three consequences follow. An NFZ with `min alt = 3000` has no effect on the ground: you can stand under it, arm and fly below 30 m. An FZ with a 120 m ceiling is already “not yours” at 125 m: the aircraft is considered outside the FZ. And an FZ with a non-zero `min alt` does not contain the takeoff point, so arming will be forbidden — the setting `geozone_safehome_as_inclusive` exists for exactly this case.

### Initialization and arming
The zones are converted to local coordinates **once** — when the position estimate first becomes valid (`geozoneUpdate()` → `geoZoneInit()`), so a reboot is needed after editing zones. At that moment:

- an inclusive zone that the aircraft is not in and whose nearest vertex is more than 2 km away (`GEOZONE_INCLUSE_IGNORE_DISTANCE`) is disabled until the next power-up;
- if the sum of `vertex count` over all zones does not equal the number of vertices actually stored, **the geozone task is turned off entirely**, without a message. One lost vertex line removes all the protection.

Arming is blocked by the `GEOZONE` flag in the `status` line (`ARMING_DISABLED_GEOZONE`, “NO FLY ZONE” in the OSD), only with `feature GEOZONE` enabled. The rule of `geozoneIsBlockingArming()`: inside any NFZ — forbidden; otherwise inside some FZ — allowed; otherwise, if at least one FZ is still active, — forbidden. The flag is in the list of blocks that an emergency arm overrides (`ARMING_DISABLED_EMERGENCY_OVERRIDE`): after it the geozones no longer hold you.

### Zone actions: modes and messages
Actions are executed only in the ANGLE, HORIZON, NAV CRUISE and NAV COURSE HOLD modes (`isNonGeozoneModeFromBoxInput()`). In ACRO and MANUAL INAV does not intervene: `geozoneUpdate()` returns before the warning text is set, and only the OSD elements with the distance to the border change on the screen (the documentation promises warnings — in the 9.1.0 code there are none in these modes). According to `docs/Geozones.md` actions are also disabled in a mission (NAV WP): a route through an NFZ will fly through the NFZ (route planning is in `inav-missions`). The code has no separate mission check — the same rule applies, “none of the four boxes is active”, so do not keep ANGLE on together with NAV WP if you are counting on the zones staying silent in a mission; what the navigation state machine does with a zone request in that combination has not been traced to the end in the source. During fixed-wing autolaunch the check is skipped.

| Situation (ANGLE mode) | What INAV does | OSD message |
|---|---|---|
| a border ahead on the current course, the action is still far away | nothing, only a warning with the distance | LEAVING FZ IN … · ENTERING NFZ IN … |
| the course crosses a border closer than the trigger distance, the action is AVOID | the wing “bounces” off the border like a ball off a cushion; if the NFZ ceiling is less than `geozone_avoid_altitude_range` away — it flies over the top at the ceiling + 2 × the margin | AVOIDING FENCE BREACH |
| the same, the action is POS_HOLD | position hold (a wing — a loiter turned away from the border) | AVOIDING FENCE BREACH |
| the same, the action is RTH | a forced RTH by the failsafe procedure | AVOIDING FENCE BREACH |
| the aircraft is already inside an NFZ with an action ≠ NONE | it flies out to the nearest border | FLY OUT NFZ |
| the aircraft is outside all FZs, the nearest FZ has an action ≠ NONE | a return to the zone by the shortest path | RETURN TO FZ |
| the aircraft is inside a zone, less than `geozone_safe_altitude_distance` from its ceiling or floor | a move to the limit altitude ∓ 1.25 of the margin (12.5 m from the ceiling or floor at the default), only in ANGLE and HORIZON; further climb or descent is blocked | REACHED ZONE ALTITUDE LIMIT |
| the aircraft is above the FZ ceiling (or below its non-zero floor) by less than the margin | **a descent on the current course toward altitude 0 — see the trap below** | REACHED ZONE ALTITUDE LIMIT |
| the aircraft is above the FZ ceiling by the margin or more | a return to the zone: a descent to the ceiling − 1.5 of the margin on the current course | RETURN TO FZ |

### A 9.1.0 trap: the thin layer above the FZ ceiling
**Read in the code, not verified in flight.** The “REACHED ZONE ALTITUDE LIMIT” branch in `geozoneUpdate()` is checked before the return to the zone. It needs three conditions: ANGLE or HORIZON mode, an action ≠ NONE for the zone under the aircraft, and a vertical distance to the limit that is greater than zero but less than `geozone_safe_altitude_distance` (10 m). It assigns a target altitude only to an aircraft that is inside an FZ (or outside an NFZ). If the aircraft is already **above the FZ ceiling by less than 10 m** — or below its non-zero floor by the same amount — it is “outside the FZ” by the altitude rule, none of the assignments is executed, and the target stays at zero: 0 cm, the altitude of the home point. The code then sets a target a kilometer ahead on the current course at altitude 0 and locks the sticks for 2.5 s. The maneuver ends when the altitude has reached 0 ± 2 m, the 30 s timeout has expired or a stick is moved after the 2.5 s. If the descent runs at the `nav_fw_auto_climb_rate` limit (default 500 cm/s), that is up to 150 m of altitude lost in 30 s — more than the zone ceiling in the practice of this module. At 10 m above the ceiling and higher the return to the zone triggers instead, with a sensible target (the ceiling − 15 m).

How you get into this layer: a climb in ACRO or MANUAL (the zones do not act there) and a switch to ANGLE just above the ceiling; or a thermal or a gust carries the aircraft above the ceiling in ANGLE. The rules: do not enable ANGLE or HORIZON in the 10-meter layer above the FZ ceiling — first descend below the ceiling in ACRO or MANUAL; on the message “REACHED ZONE ALTITUDE LIMIT” with the nose going down, switch to ACRO or MANUAL at once — that ends the action without waiting 2.5 s; set the FZ ceiling with a margin above the working altitude so that you do not end up near it.

### The trigger distance and the geozone settings
The trigger distance is not `geozone_detection_distance`. That setting defines how far ahead on the course INAV looks for a crossing and starts warning. The action starts when less than 1.5 × `nav_fw_loiter_radius` is left to the crossing point for a fixed wing (112.5 m at the default) or `geozone_mr_stop_distance` for a multirotor. The sticks are locked for 2.5 s; POS_HOLD and RTH are released by moving a stick after those 2.5 s. **Geozone actions take control away from the pilot** — make the first flight with zones at altitude and with a finger on the ACRO or MANUAL switch.

| Setting | Default | Range | Meaning |
|---|---|---|---|
| `geozone_detection_distance` | 50000 cm | 0–1000000 | the distance from which a geozone is detected on the course |
| `geozone_avoid_altitude_range` | 5000 cm | 0–1000000 | if the NFZ ceiling is closer than this — fly over the top |
| `geozone_safe_altitude_distance` | 1000 cm | 0–10000 | the vertical distance to be kept from the ceiling and the floor |
| `geozone_safehome_as_inclusive` | OFF | OFF · ON | the nearest safehome is a circular FZ with the radius `safehome_max_distance` |
| `geozone_safehome_zone_action` | NONE | NONE · AVOID · POS_HOLD · RTH | the action of that zone |
| `geozone_mr_stop_distance` | 15000 cm | 0–100000 | how far before the border a multirotor stops |
| `geozone_no_way_home_action` | RTH | RTH · EMRG_LAND | what to do if no course home is found |

### Geozones and RTH
When RTH is activated (`navOnEnteringState_NAV_STATE_RTH_HEAD_HOME`), `geozoneCheckForNFZAtCourse()` is called. If the straight line home crosses an NFZ or leaves an FZ, `calcRthCourse()` builds a detour: the candidates are the zone vertices moved away from the border by 2/3 of the trigger distance (outward for an NFZ, inward for an FZ; 75 m for a fixed wing at the defaults) and fly-over points above an NFZ at the ceiling + 2 × the margin; the path is chosen with Dijkstra's algorithm, where a meter of altitude costs as much as two meters of path. In the OSD — “AVOIDING NO FLY ZONES”. The arrival altitude at home is limited to the FZ ceiling minus the margin.

If no path is found: `geozone_no_way_home_action = RTH` (default) — **fly home in a straight line, ignoring the zones**; `EMRG_LAND` — an emergency landing on the spot. Choose deliberately: the first violates the prohibition, the second puts the aircraft down wherever it is. If RTH is activated outside an FZ or inside an NFZ, no detour is built at all. The pilot can cancel the detour by flipping the RTH switch twice within 1 s.

### Safehome
`safehome <n> <enabled> <lat> <lon>` — three arguments after the index; `safehome reset` erases all eight. The settings: `safehome_max_distance` = 20000 cm (0–65000), `safehome_usage_mode` = RTH (OFF · RTH · RTH_FS).

The selection is made by `findNearestSafeHome()` at the moment home is recorded — that is, on arming (before the first arm the point is updated continuously). The **nearest enabled** safehome no farther than `safehome_max_distance` from the current position is taken; the others do not exist for this flight. Home remains the arming point. When RTH starts, `checkSafeHomeState()` replaces home with the safehome (“DIVERTING TO SAFEHOME” in the OSD), and after leaving RTH it restores the arming point. There is no replacement if the mode is `OFF`, if it is `RTH_FS` and RTH was activated with the switch, if a trackback is in progress or if the aircraft is closer than `nav_min_rth_distance` to home. A safehome has no altitude: the altitude of the landing point is set by `fwapproach`.

### RTH trackback
`nav_rth_trackback_mode`: OFF (default), ON (any RTH), FS (failsafe RTH only). `nav_rth_trackback_distance` = 500 **m** (50–2000) — a rare navigation setting in meters.

Recording (`rthTrackBackUpdate()` in `rth_trackback.c`) runs whenever the mode is not OFF, the aircraft is in the air and not in RTH. The first point — when home is more than 50 m away. After that a point is saved if the altitude changed by more than 10 m, or the GPS course by more than 45° (no more often than every 10 m of path), or after ten 10-meter steps the aircraft has moved more than 20 m off the straight line. Without a valid heading — every 20 m. A fixed wing in a loiter saves one point and pauses the recording. There are 50 points; the 51st overwrites the oldest one.

On RTH the aircraft flies back through the points, not descending below the altitude at which the trackback started, and switches to a normal RTH when the points run out or **the straight-line distance from the place where the trackback started** exceeds `nav_rth_trackback_distance`. Moving the roll stick cancels the trackback, but not during failsafe. Trackback is not used in an RTH from a mission. The point: on a link loss behind a hill, return to where the link was instead of flying home through the hill.

### Fixed-wing autoland: `fwapproach`
`fwapproach <index> <approach alt> <land alt> <direction> <heading1> <heading2> <sea level>` — exactly six numbers after the index.

| Field | Values | What matters |
|---|---|---|
| index | 0–7 — for the safehome with the same index; 8–16 — for missions 1–9 (the landing point is the last waypoint of the mission) | the slot of the selected safehome is empty → no autoland |
| approach alt, cm | the altitude of the loiter and of the first leg | relative to home altitude or above sea level |
| land alt, cm | the altitude of the landing point | the same |
| direction | 0 LEFT, 1 RIGHT | the side of the pattern relative to the main heading |
| heading1, heading2 | −360…360 | 0 — the direction is disabled; **plus — landing in the opposite direction is also allowed, minus — only this one**; north is written as 360 |
| sea level | 0 · 1 | with 1 the home altitude above sea level is subtracted from both altitudes |

Autoland is used if `nav_rth_allow_landing` allows landing (`inav-gps`), the platform is an airplane and the slot has at least one non-zero heading. Otherwise the old landing from `inav-wing` is performed: a downward spiral and `nav_fw_land_dive_angle`. `nav_rth_fs_landing_delay` (0–1800 s, default 0) holds the aircraft in a loiter over home before landing on a failsafe RTH; the wait is cut short when the battery reaches the warning level.

| Setting | Default | Range | Meaning |
|---|---|---|---|
| `nav_fw_land_approach_length` | 35000 cm | 100–100000 | L: from the landing point to the last turn |
| `nav_fw_land_final_approach_pitch2throttle_mod` | 100 % | 100–400 | a multiplier of `nav_fw_pitch2thr` on final approach with the pitch down: 200 pulls the throttle back twice as hard |
| `nav_fw_land_glide_alt` | 200 cm | 100–5000 | below it — the motor is off, the pitch is fixed |
| `nav_fw_land_glide_pitch` | 0° | −15…45 | the pitch in the glide, plus — nose up |
| `nav_fw_land_flare_alt` | 150 cm | 0–10000 | the flare altitude, **only with a working rangefinder** |
| `nav_fw_land_flare_pitch` | 8° | −15…45 | the pitch in the flare |
| `nav_fw_land_max_tailwind` | 140 cm/s | 0–3000 | the wind speed threshold below which the wind is ignored |
| `nav_fw_launch_land_abort_deadband` | 100 | 2–250 | the roll or pitch stick deflection that aborts the landing |

The autolaunch settings `nav_fw_launch_*` are in `inav-wing`.

### What the code builds: states and geometry
The states of `fwAutolandState_t` (operand 41 in `inav-ipf`): 0 idle, 1 loiter, 2 downwind, 3 base leg, 4 final approach, 5 glide, 6 flare.

1. **A climb or descent to approach alt** over the landing point (tolerance 150 cm or `nav_wp_enforce_altitude` if it is greater than 0).
2. **Loiter**: 30 s (`FW_LAND_LOITER_MIN_TIME`) are counted from the start of the landing sequence, that is, they include the climb or descent of item 1; during this time the wind estimator gathers data. While there is no wind estimate or no heading is suitable, the timer restarts and the wing keeps circling.
3. **Choosing the heading.** The direction the wind is blowing “from” = the estimator angle + 180°. If the wind speed is below `nav_fw_land_max_tailwind`, heading1 is taken (heading2 if it is 0) without regard to the wind. Otherwise, for each heading, `calcFinalApproachHeading()`: if it is a headwind (the angle between the heading and the “from” direction is no more than 90°) — the heading itself is suitable; if not and the heading is positive — the opposite one is suitable; if it is negative — the heading is discarded. Of the two that remain, the one closer to the “from” direction is chosen. Both discarded — another 30 s of loiter.
4. **Three points** (`navOnEnteringState_NAV_STATE_FW_LANDING_LOITER`), everything in centimeters, H being the chosen landing heading:
   - h_fa = approach alt / 3 × 2 in integers: 5000 gives 3332, not 3333;
   - `WP_FINAL_APPROACH` = the landing point moved by L along the heading H + 180°, altitude h_fa;
   - `WP_LAND` = the landing point moved by L **forward** along the heading H, altitude land alt − h_fa — that is, underground beyond the landing point;
   - `WP_TURN` = `WP_FINAL_APPROACH` moved by max(4 × `nav_fw_loiter_radius`, L / 2) along the heading |configured heading| − 90° (LEFT) or + 90° (RIGHT), altitude approach alt. The **configured** heading of the slot is used, not the actual one: when landing in the opposite direction the pattern stays on the same side of the strip, and the turn to final changes from right to left.
5. **Downwind**: a flight to `WP_TURN` at approach alt. **Base leg**: to `WP_FINAL_APPROACH`. **Final approach**: to `WP_LAND`. On each leg the target altitude goes linearly from the altitude at the start of the leg to the altitude of the point and reaches it when 10 % of the leg length is left.
6. **Glide**: altitude ≤ land alt + `nav_fw_land_glide_alt` — the motor stopped or at idle, heading H, pitch `nav_fw_land_glide_pitch`.
7. **Flare**: the rangefinder is working and altitude ≤ land alt + `nav_fw_land_flare_alt` — pitch `nav_fw_land_flare_pitch`. Without a rangefinder (`inav-sensors-extra`) there is no flare state: the wing glides to touchdown. Then the landing detector and the disarm (`nav_disarm_on_landing`).

### Glide slope, aborting and the conditions for an accurate approach
The final leg of length 2L loses 2 × h_fa − land alt over 0.9 × 2L, hence the glide slope:

tan γ = (2 × h_fa − land alt) / (1.8 × L).

With land alt = 0 the target line meets the ground at 0.9 L from `WP_FINAL_APPROACH` — 0.1 L **before** the safehome, and the motor is cut even earlier. At the defaults (approach 50 m, L = 350 m) γ = 6.0°, and the motor is cut 54 m before the point. Do not place the safehome at the start of the strip but where an overshoot and an undershoot are equally safe.

{{diagram:chart-inav-autoland-top|The approach pattern from the practice: a loiter over the safehome, downwind to WP_TURN, base to WP_FINAL_APPROACH and a final leg of length 2L whose target lies beyond the landing point.}}

{{diagram:chart-inav-autoland-profile|The target altitude reaches the goal 10 % before the end of the leg, so the glide slope is steeper than h_fa / L: 5.3° instead of 4.8°, and the line touches the ground 40 m before the safehome.}}

**Aborting.** Before the flare state a roll or pitch stick deflection greater than `nav_fw_launch_land_abort_deadband` aborts the landing: the aircraft returns to RTH (or to the mission), climbs and **loiters without another landing attempt** until RTH is activated again. In the flare you cannot abort — only by changing the mode. A loss of heading or position on the approach leads to an emergency landing.

**What an accurate approach needs** (`docs/Fixed Wing Landing.md`): `nav_fw_wp_tracking_accuracy` greater than 0 (the default is 0 — the wing flies to the point without lining up with the strip axis), `nav_wp_radius` no more than 1000 cm, a tuned `nav_fw_pitch2thr`.

### What changed between 8.0 and 9.1
A comparison of the 8.0.1 and 9.1.0 trees: `navigation_geozone.c`, the settings `geozone_*`, `safehome_*`, `nav_rth_trackback_*`, `nav_fw_land_*`, the parsing of the `geozone`, `safehome`, `fwapproach` commands and the whole autoland state machine are **identical**. There is one difference: in `rthTrackBackSetNewPosition()` of 9.1 the target after the last trackback point is no longer set from index −1 (in 8.0.1 the memory before the point array was read). Geozones appeared in 8.0, fixed-wing autoland in 7.1.

### Place in the system
- **Receives:** the position, home and the RTH altitudes (`nav_rth_alt_mode`, `nav_rth_allow_landing`) from `inav-gps`; the wind estimate, `nav_fw_loiter_radius`, `nav_fw_pitch2thr` and the old landing from `inav-wing`; RTH as the failsafe procedure from `inav-setup-wing`; the mission number from `inav-missions`.
- **Provides:** the arming-disabled flag `GEOZONE` in `status` (`inav-cli-backup`); the replaced home and the detour route — to the RTH state machine; the landing state — to logic operand 41 (`inav-ipf`) for deploying flaps.
- **If you get it wrong here:** a `vertex count` mismatch silently turns off all the zones, and RTH flies through the forbidden area; a `fwapproach` that is not in the slot of the selected safehome gives a spiral instead of an approach (`inav-wing`); `geozone_no_way_home_action = EMRG_LAND` puts the aircraft down far from home at the first dead end.

## practice
The lab needs no hardware and no simulator: all the answers are derived from the formulas and rules of the theory. The configs below are a **teaching example assembled by hand** from the 9.1.0 names and formats. You need a calculator and a sheet of graph paper.

The arming point and the origin of the local coordinates: 50.0000000° N, 30.0000000° E (`500000000`, `300000000`). cos 50° = 0.64279, so north N = Δlat × 0.01113195 m, east E = Δlon × 0.0071555 m.

### Step 1. Decode the zones
```
feature GEOZONE
geozone 0 1 1 0 12000 0 1 4
geozone 1 0 0 0 8000 0 2 2
geozone 2 0 0 3000 0 0 3 2
geozone vertex 0 0 499982000 299958000
geozone vertex 0 1 499982000 300042000
geozone vertex 0 2 500054000 300042000
geozone vertex 0 3 500036000 299958000
geozone vertex 1 0 500031500 300014000
geozone vertex 1 1 12000 0
geozone vertex 2 0 499991000 299979000
geozone vertex 2 1 6000 0
```

For each zone write down the shape, the type, the altitude range in meters, the action. Convert the vertices to local meters. Zone 0 has a slanted northern side: find its equation N(E).

### Step 2. Eight positions
The other `geozone_*` settings are at their defaults, the platform is a fixed wing. For each position determine: which zones the aircraft is in (taking altitude into account) and what INAV does.

| No. | lat | lon | altitude, m | state |
|---|---|---|---|---|
| 1 | 500000000 | 300000000 | 0 | on the ground, an arming attempt |
| 2 | 500031500 | 300021000 | 50 | flying in ANGLE |
| 3 | 500031500 | 300021000 | 100 | flying in ANGLE |
| 4 | 500046800 | 299994600 | 60 | flying in ANGLE |
| 5 | 500046800 | 300021000 | 60 | flying in ANGLE |
| 6 | 499990100 | 299981800 | 0 | on the ground, an arming attempt |
| 7 | 499990100 | 299981800 | 40 | flying in ACRO |
| 8 | 500000000 | 300000000 | 135 | flying in ANGLE after a climb in ACRO |

In addition: (a) what changes in position 1 if the line `geozone vertex 0 3 …` disappears from the config? (b) what changes in position 8 if ANGLE is enabled not at 135 but at 125 m?

### Step 3. Select the safehome
```
safehome 0 1 500013000 300021000
safehome 1 1 499988000 300016000
safehome 2 0 500004500 300007000
safehome 3 1 500012600 299986000
```

Arming at the origin, `safehome_max_distance = 20000`. Calculate the distances and name the selected index. Where does the aircraft go with `safehome_usage_mode = RTH_FS` and RTH from the switch? What happens with `safehome_max_distance = 15000`?

### Step 4. Build the approach
Safehome 3 is selected; from here on count coordinates from it: the landing point is (0; 0), the first coordinate is north, the second is east, in meters. The config: `fwapproach 3 5000 0 1 270 -180 0`, `nav_fw_land_approach_length = 40000`, `nav_fw_loiter_radius = 7500`, the other `nav_fw_land_*` at their defaults, no rangefinder.

1. The wind blows from 120° at 5 m/s. Which landing heading does INAV choose?
2. Calculate h_fa, the coordinates and altitudes of `WP_FINAL_APPROACH`, `WP_LAND`, `WP_TURN`, and the length of the base leg.
3. Find the glide slope γ, the distance from `WP_FINAL_APPROACH` at which the target line touches the ground and at which the motor is cut. Where does the flare start?
4. The same wind but 1 m/s: which heading and what tailwind component?
5. Wind from 350°, 5 m/s: the heading and the coordinates of the three points.
6. The slot is replaced with `fwapproach 3 5000 0 1 -270 -180 0`, wind from 60°, 5 m/s. What happens?

### Step 5. Find three errors
```
feature GEOZONE
geozone 0 1 1 0 12000 0 1 4
geozone vertex 0 0 499982000 299958000
geozone vertex 0 1 499982000 300042000
geozone vertex 0 2 500054000 300042000
safehome 3 1 500012600 299986000
fwapproach 0 5000 0 1 270 -180 0
set nav_rth_allow_landing = NEVER
set safehome_usage_mode = RTH
```

The owner expects: the zone keeps the wing inside the field, and on RTH it lands at safehome 3 with an approach heading of 270° or 180°. Name three reasons why neither will happen. (The landing prohibition `nav_rth_allow_landing = NEVER` as a fixed-wing failsafe setting is covered in `inav-setup-wing`.)

### Moving to real hardware
The order, if you have a wing. The propeller stays off until item 4.

1. `status` on the bench with a GPS fix: there is no `GEOZONE` flag inside the FZ; move the zone in the editor so that home ends up outside, reboot — the flag appears. Put the zone back.
2. `geozone` and `geozone vertex`: the sum of the last numbers of the zones equals the number of vertex lines with zone id ≥ 0; the CLI prints `# N vertices free (Used M of 126)`.
3. After arming without the propeller the OSD shows, under the ARMED text, a blinking line `⌂ SAFEHOME n @ <distance>` (the first character is the home symbol from the OSD font; with `safehome_usage_mode = OFF` it is `SAFEHOME FOUND; MODE OFF` instead); n matches the index of the filled-in `fwapproach`. `docs/Safehomes.md` gives a different line — it is not in the 9.1.0 code.
4. The first flight: an altitude from 80 m, but no closer than 20 m to the FZ ceiling, ANGLE, approach the FZ border at a 45° angle; expect the turn no closer than 1.5 loiter radii. Keep a finger on the MANUAL switch: a geozone action takes control away. Do not enter ANGLE or HORIZON above the FZ ceiling: in the 10-meter layer above the ceiling the code flies the wing down toward altitude 0.
5. Autoland: the first time with a field length margin of at least L on both sides of the safehome and with no people on the axis; be ready to deflect a stick by more than `nav_fw_launch_land_abort_deadband` — after an abort the wing loiters and will not land by itself.

The criteria on hardware: the `GEOZONE` flag changes together with the position of the zone; the safehome number in the OSD matches the distance calculation; logic operand 41 went through the values 1 → 2 → 3 → 4 → 5. The operand itself is not visible on the screen: write it with a logic rule (operation 18, Set GVAR) to a global variable and put the element of that variable (GVAR 0…3) on the OSD; how to write rules is in `inav-ipf`.

Self-check: the lab is done when:
- step 1: zone 0 — a polygon, FZ, 0–120 m, AVOID, vertices (−200.4; −300.5), (−200.4; 300.5), (601.1; 300.5), (400.8; −300.5) m, the northern side N = 500.9 + 0.3334 × E; zone 1 — a circle, NFZ, 0–80 m, POS_HOLD, center (350.7; 100.2), radius 120 m; zone 2 — a circle, NFZ, from 30 m with no ceiling, RTH, center (−100.2; −150.3), radius 60 m (tolerance 0.2 m);
- step 2: all eight rows of the reference table match, and so does the answer about the missing vertex;
- step 3: the distances are 208.6, 175.9, 70.8 and 172.4 m (±0.3); safehome 3 is selected; from the switch with `RTH_FS` — to the arming point; with 15000 — no safehome is selected;
- step 4: heading 90°; h_fa = 3332 cm; `WP_FINAL_APPROACH` (0; −400) at 33.32 m, `WP_LAND` (0; +400) at −33.32 m, `WP_TURN` (300; −400) at 50 m, base 300 m; γ = 5.29° (±0.05); the ground at 360.0 m, the motor is cut at 338.4 m (±0.5), that is, 61.6 m before the safehome; there will be no flare; at 1 m/s — heading 270°, tailwind 0.87 m/s; with wind from 350° — heading 270°, points (0; +400), (0; −400), (300; +400); in item 6 — an endless loiter;
- step 5: the vertex count mismatch, the `fwapproach` slot and `nav_rth_allow_landing = NEVER` are named.

**Reference for the self-check.**

| No. | N; E, m | Inside (with altitude) | What INAV does |
|---|---|---|---|
| 1 | 0; 0 | zone 0 | arming is allowed |
| 2 | 350.7; 150.3 | zones 0 and 1 (50.1 m to the center) | it flies out of the NFZ, “FLY OUT NFZ” |
| 3 | 350.7; 150.3 | zone 0 only: 100 m is above the NFZ ceiling of 80 m | no return and no fly-out, flying over the NFZ is legal; a descent below 90 m runs into “REACHED ZONE ALTITUDE LIMIT” (a move to 92.5 m) |
| 4 | 521.0; −38.6 | none: the border at this longitude is N = 488.1 | a return to the zone, “RETURN TO FZ” |
| 5 | 521.0; 150.3 | zone 0: the border here is N = 551.0; 177.5 m to the center of zone 1 | no return and no fly-out; AVOID starts only if the course crosses the border closer than 112.5 m (the northern side is 28.5 m away along the perpendicular) |
| 6 | −110.2; −130.2 | zone 0; in plan view inside zone 2 (22.4 m), but the floor is 30 m | arming is allowed |
| 7 | −110.2; −130.2 | zones 0 and 2 | nothing: in ACRO there are neither actions nor a warning text |
| 8 | 0; 0 | none: 135 m is above the FZ ceiling of 120 m | a return to the zone with a descent to 105 m (120 − 1.5 × 10), “RETURN TO FZ” |

(a) Without the vertex line the sum of `vertex count` (4 + 2 + 2 = 8) does not equal the number of vertices (7): geozones are turned off entirely, arming is allowed, there is no protection. (b) At 125 m the aircraft is only 5 m above the ceiling — less than `geozone_safe_altitude_distance`. The “REACHED ZONE ALTITUDE LIMIT” branch triggers first, not the return to the zone; the aircraft is outside the FZ, so the target altitude in it stays 0: the wing flies down on the current course toward home altitude, for up to 30 s, with the sticks locked for the first 2.5 s. The right pilot action is ACRO or MANUAL at once. The boundary between the two answers is exactly 10 m above the ceiling: at 130 m and higher it is already a return to the zone.

Typical wrong answers and their cause. In position 8 at 125 m the answer “a descent to 105 m” is wrong: that is the return-to-zone formula, and the code does not get to it — the altitude limit branch is checked earlier. Positions 4 and 5 both written as “inside, there is nothing north of 601 m” — the zone was taken for a rectangle, but the side is slanted. East calculated without cos 50°: 42000 units give 467.5 m instead of 300.5, and safehome 0 “passes” on distance. In position 6 arming is “forbidden” — the altitude check was forgotten: an NFZ with a 30 m floor has no effect on the ground. The radius of zone 1 read as a latitude of 0.0012° — for a circle vertex 1 holds centimeters. In step 3 safehome 2 (70.8 m) was selected — it is disabled by the second number of the line. In step 4 h_fa = 3333 (the division is integer, by 3 first), γ = 4.76° (h_fa / L taken without the 0.9 factor and without the target underground), heading 270° with a 5 m/s wind (heading1 is positive, so the opposite heading 90° is allowed and it is a headwind), `WP_TURN` in the south (when landing in the opposite direction the side is counted from the configured 270°, not from 90°). In item 6 the answer “it lands with a tailwind” is wrong: both headings are negative, both are discarded, and the loiter timer restarts.

## diagnostics
- **Symptom:** `status` has the `GEOZONE` flag and the OSD shows “NO FLY ZONE” although the aircraft is standing in a fly zone
  - Possible cause: the FZ has a non-zero `min alt` or `sea level` is enabled with a wrong altitude — on the ground the aircraft is outside the altitude range; or the takeoff point is outside the polygon, closer than 2 km to a vertex.
  - What to do: `min alt = 0` for the takeoff zone or `geozone_safehome_as_inclusive = ON`; check the vertices in the editor.
- **Symptom:** zones are defined, but the aircraft crosses the border freely
  - Possible cause: `feature GEOZONE` is not enabled; the number of vertices does not match `vertex count` (the protection is off entirely); there was no reboot after editing; ACRO or MANUAL mode or a mission; the FZ was disabled because power was applied more than 2 km away from it.
  - What to do: compare the output of `geozone` and `geozone vertex`, reboot, test in ANGLE.
  - Consequences: RTH also flies without a detour.
- **Symptom:** the `geozone` command answers as unknown
  - Possible cause: a board with 512 KB of flash (F411, F722) — `USE_GEOZONE` is not built.
  - What to do: a board on an F405, F745, H743 or AT32F435.
- **Symptom:** near the border the wing suddenly turns around and does not respond to the sticks
  - Possible cause: the AVOID action, the sticks are locked for 2.5 s, the maneuver lasts up to 30 s.
  - What to do: switch to ACRO or MANUAL — the action ends at once.
- **Symptom:** after enabling ANGLE or HORIZON just above the FZ ceiling the wing flies straight down, the OSD shows “REACHED ZONE ALTITUDE LIMIT”, the sticks have no effect
  - Possible cause: the aircraft is above the FZ ceiling by less than `geozone_safe_altitude_distance` (or below a non-zero floor by the same amount); in this 9.1.0 branch the target altitude stays 0, and the maneuver lasts up to 30 s. The conclusion was drawn by reading `geozoneUpdate()` and was not verified in flight.
  - What to do: ACRO or MANUAL at once — the action ends; descend below the ceiling by hand and only then enable ANGLE. Raise the FZ ceiling above the working altitude.
  - Consequences: a loss of up to 150 m of altitude in 30 s at the default `nav_fw_auto_climb_rate` — at low altitude that is a collision with the ground.
- **Symptom:** on RTH the aircraft flies straight through a no-fly zone
  - Possible cause: no path was found and `geozone_no_way_home_action = RTH`; RTH was activated outside an FZ; the detour was canceled with a double flip of the switch.
  - What to do: simplify the zones (sides shorter than 500 m, passages wider than 2.5 loiter radii), decide whether `EMRG_LAND` is acceptable.
- **Symptom:** on RTH the wing lands in a spiral, not with an approach
  - Possible cause: `fwapproach` is not written in the slot of the selected safehome; both headings are 0 (north is 360); no safehome was selected because of `safehome_max_distance`; `safehome_usage_mode = RTH_FS`, and RTH was activated with the switch.
  - What to do: compare the number in the OSD message after arming with the `fwapproach` index.
- **Symptom:** the wing loiters over the safehome endlessly
  - Possible cause: no wind estimate; both headings are negative, and the wind is a tailwind for both; the landing was aborted with a stick; `nav_rth_allow_landing = NEVER`; `nav_rth_fs_landing_delay` is running.
  - What to do: make one of the headings positive; after an abort turn RTH off and on.
  - Consequences: the battery drains in the loiter.
- **Symptom:** touchdown long before the safehome point
  - Possible cause: that is how the glide slope is built: the target goes underground 0.1 L before the point, and the motor is cut at `nav_fw_land_glide_alt`.
  - What to do: move the safehome deeper into the strip, reduce L or approach alt, raise `nav_fw_land_glide_pitch`.
- **Symptom:** the approach is at an angle to the strip
  - Possible cause: `nav_fw_wp_tracking_accuracy = 0`, a large `nav_wp_radius`.
  - What to do: enable track-line tracking, `nav_wp_radius` down to 1000 cm.
- **Symptom:** on a link loss the aircraft first flies away from home
  - Possible cause: trackback is taking it back along its own track.
  - What to do: this is the intended behavior; limit `nav_rth_trackback_distance` or set the mode to OFF.

## checklist
- `feature GEOZONE` is enabled, the board has more than 512 KB of flash
- The zones were created in the editor and saved, and there was a reboot after saving
- The sum of `vertex count` equals the number of `geozone vertex` lines
- On the ground at the takeoff point there is no `GEOZONE` flag in `status`
- `geozone_no_way_home_action` is chosen deliberately
- The safehome number in the OSD after arming matches the `fwapproach` slot
- The `fwapproach` headings: not 0, the sign chosen by the obstacles, at least one positive
- `nav_rth_allow_landing` allows landing, `nav_fw_wp_tracking_accuracy` is greater than 0
- A clear strip of at least L on both sides of the safehome and room for `WP_TURN`
- The MANUAL switch is tested: it cancels both a geozone action and a landing
- The FZ ceiling is above the working altitude with a margin; ANGLE and HORIZON are not enabled in the 10-meter layer above the FZ ceiling (there the code flies the aircraft down toward altitude 0)

## references
- INAV 9.1.0 — navigation_geozone.c | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/navigation/navigation_geozone.c | primary | A
- INAV 9.1.0 — navigation.c (safehome, the autoland state machine, RTH) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/navigation/navigation.c | primary | A
- INAV 9.1.0 — rth_trackback.c | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/navigation/rth_trackback.c | primary | A
- INAV 9.1.0 — settings.yaml | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/settings.yaml | primary | A
- INAV 9.1.0 — cli.c (geozone, safehome, fwapproach) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/cli.c | primary | A
- INAV docs — Geozones | https://github.com/iNavFlight/inav/blob/9.1.0/docs/Geozones.md | primary | A
- INAV docs — Fixed Wing Landing | https://github.com/iNavFlight/inav/blob/9.1.0/docs/Fixed%20Wing%20Landing.md | primary | A
- INAV docs — Safehomes | https://github.com/iNavFlight/inav/blob/9.1.0/docs/Safehomes.md | primary | A

## notes
The firmware was not built or run: all the behavior was derived by reading the INAV 9.1.0 source and comparing it with 8.0.1; the numbers of the practice were computed with a script using the same formulas as the code. Not verified in flight: the zero target altitude of the “REACHED ZONE ALTITUDE LIMIT” branch for an aircraft above the FZ ceiling (position 8 of the practice; obtained by reading `geozoneUpdate()` and repeated with an independent model of that function), the actual touchdown point (it depends on the glide ratio of the airframe and on the wind), the behavior of geozone actions in mission mode (taken from `docs/Geozones.md`), the moment when the home altitude above sea level becomes known to the initialization of zones with `sea level = 1`. Discrepancies between the documentation and the 9.1.0 code: `docs/Geozones.md` names ids 0–63 and 127 vertices (the code has 63 zones and 126 vertices), `docs/Safehomes.md` gives the OSD line `H - DIST -> SAFEHOME n` (in the code it is `%c SAFEHOME %u @ %s`), `docs/Fixed Wing Landing.md` — a default of 200 for `nav_fw_land_flare_alt` and a lower pitch limit of 0 (150 and −15 in `settings.yaml`), `fwapproach` indexes 0–17 (there are 17 slots, indexes 0–16).
