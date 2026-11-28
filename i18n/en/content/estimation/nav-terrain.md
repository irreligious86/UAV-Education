---
id: nav-terrain
title: "Terrain following: terrain data, rangefinder, TERRAIN_*, safety"
level: L2
readingTime: 40 min
firmware: ArduCopter 4.7 (checked against 4.7.3; the lab was captured on 4.6.3) · ArduPlane 4.7 · PX4 1.18 (parameters checked against v1.18.0)
status: published
tags:
  - terrain following
  - SRTM
  - rangefinder
  - RTL_ALT_TYPE
  - failsafe
related:
  - est-alt-sources
  - ap-missions
  - ap-safety-fs
  - ap-plane-tuning
  - aero-wing
next:
  - nav-resilience
source: content/estimation/nav-terrain.md
source_hash: 56ee4e23be87
---

## summary
"40 m above the ground" in hilly terrain means three reference frames and two sources of ground data: an on-board SRTM database and a rangefinder. This module covers how ArduPilot (and briefly PX4) follows terrain, what `TERRAIN_*`, `RNGFND*`, `SURFTRAK_*` and `RTL_ALT_TYPE` are responsible for, what happens without data, and why SRTM does not see trees. The lab is a SITL mission across Mount Majura (288 m of relief) with the database and with a rangefinder, a plot of the true height above ground from the log, a collision with the slope on an RTL with the wrong altitude type, and a terrain failsafe on rangefinder loss.

## theory
### Three altitudes
The barometer, GPS and rangefinder as altitude sources are covered in est-alt-sources; here is what "above the ground" means in terms of them. The frame of a mission item (the ap-missions module): `MAV_FRAME_GLOBAL` (0) is above mean sea level (AMSL); `MAV_FRAME_GLOBAL_RELATIVE_ALT` (3) is above the arming point; `MAV_FRAME_GLOBAL_TERRAIN_ALT` (10, "Terrain" in Mission Planner) is above the ground: `h_AGL = h_AMSL − h_terrain(lat, lon)`. Where to get `h_terrain` from is what the whole module is about.

| Source | What it measures | Range / accuracy | Where it lies |
|---|---|---|---|
| A terrain database on the SD card ("SRTM") | a surface model (DSM), not bare earth: SRTM is a radar survey from 2000; the terrain.ardupilot.org tiles are built from JAXA ALOS, 0–84° latitude; a `TERRAIN_SPACING` grid of 100 m | typically ±10 m; 35 m was observed at the top of a ski slope (ArduPilot documentation) | trees, buildings, quarries and spoil heaps newer than the survey |
| A downward rangefinder (lidar/radar) | the distance to the nearest surface below the vehicle | 7–200 m depending on the model; a lidar about ±6 cm up to 6 m, ~1% beyond | canopy and grass count as "ground," water and black asphalt for a lidar, tilt, cannot see ahead |

The database gives you the map in advance (you check the profile before the flight), the rangefinder gives the real surface, but only directly below.

### The on-board terrain database
`TERRAIN_ENABLE = 1` enables the database. The flight controller requests missing grid squares with a `TERRAIN_REQUEST` message, and the GCS (Mission Planner, QGC, MAVProxy `module load terrain`) answers with `TERRAIN_DATA` in blocks of 4×4 points; the data is written to `APM/TERRAIN/S36E149.DAT` (one file per degree, 2.5 MB at 100 m spacing) and stays on the SD card. The GCS SRTM3 database is 100 m; a `TERRAIN_SPACING` below 100 only wastes SD space. The state is in `TERRAIN_REPORT` (`pending`, `loaded`, `terrain_height`, `current_height`) and in the `TERR.TerrH/CHeight/Pending/Loaded/ROfs` log. While `pending != 0` or there is no height for home and the mission items, a terrain mission will not arm: `PreArm: waiting for terrain data` (`AP_Terrain::pre_arm_checks`).

`TERRAIN_OFS_MAX` (30 m): at arming the database is shifted so that the home height matches GPS/baro (`TERR.ROfs`; +1.08 m in the lab), by no more than this value. `TERRAIN_MARGIN` (0.05) is the coordinate tolerance for accepting blocks from the GCS, not a safety height. The metadata unit is m, the description says "centi-meters"; by the code (`TERRAIN_LATLON_EQUAL`: `margin × 100` in units of 1e-7°) 0.05 ≈ 5 units ≈ 5.6 cm, so in practice it is meters. `TERRAIN_CACHE_SZ` (12 blocks of 32×28 at ≈1.8 kB) is the in-memory cache. 4.7 adds bit 2 of `TERRAIN_OPTIONS`, "Accept Old Terrain Data": tiles generated before 24 February 2026 contain errors from the old generator, and without the bit 4.7 will not arm ("terrain data expired, possible errors"); delete the `APM/TERRAIN` folder and download again.

### How Copter holds height above terrain
In AUTO a waypoint with the Terrain frame is an offset `terr_offset` above the EKF origin; the source is chosen by `AC_WPNav::get_terrain_source()`: **if a downward rangefinder is configured and `WP_RFND_USE = 1` (default 1; before 4.7 `WPNAV_RFND_USE`, like all the `WPNAV_*`), the rangefinder; otherwise the database, if `TERRAIN_ENABLE = 1`**. There is no fallback from the rangefinder to the database: an unhealthy rangefinder with `WP_RFND_USE = 1` means "no data." The rangefinder height is `distance × cos(tilt)` (`AP_SurfaceDistance`, tilt limited to 45°), then the `RNGFND_FILT` filter (0.5 Hz) and `SURFTRAK_TC` smoothing (1 s). Copter does not look ahead: the target changes with the ground below the vehicle, the climb is limited by `WP_SPD_UP` (2.5 m/s; before 4.7 `WPNAV_SPEED_UP`, 250 cm/s), the descent by `WP_SPD_DN` (1.5 m/s; before 4.7 `WPNAV_SPEED_DN`, 150 cm/s). When the altitude error exceeds half of `WP_TER_MARGIN` (10 m), the horizontal speed drops linearly down to 1% (`AC_PosControl::terrain_scaler_D_m`, in 4.6 `pos_offset_z_scaler`). The rule: on a slope `s` at speed `V` you need a climb of `V·s`; anything beyond `WP_SPD_UP` is lost height until TER_MARGIN applies the brakes.

In Loiter, AltHold and PosHold with a rangefinder, surface tracking works: `SURFTRAK_MODE` 1 is ground (the default), 0 off, 2 ceiling. The target is `CTUN.DSAlt`, the measurement `CTUN.SAlt`. Above `RNGFND1_MAX` (meters; before 4.7 `RNGFND1_MAX_CM`, centimeters) the sensor goes "OutOfRangeHigh," and tracking silently releases the target to baro altitude. The `copter_terrain_brake.lua` applet (`TERR_BRK_ENABLE`, `TERR_BRK_ALT`, `TERR_BRK_HDIST`) switches Loiter to BRAKE if the height above the database drops below a threshold.

### RTL and returning across a mountain
`RTL_ALT_TYPE = 0` (the default): `RTL_ALT_M` (before 4.7, `RTL_ALT` in centimeters) is above home, and the return altitude is `max(current, RTL_ALT_M)` with the `RTL_CONE_SLOPE` cone; a ridge higher than that between the vehicle and home means a collision. `RTL_ALT_TYPE = 1`: `RTL_ALT_M` is above terrain, with the source as in AUTO. Pre-arm with type 1: without a source, "RTL_ALT_TYPE is above-terrain but no terrain data"; with a rangefinder, "RTL_ALT_TYPE is above-terrain but RTL_ALT_M above RNGFND_MAX", so you need `RTL_ALT_M ≤ RNGFND1_MAX`. The documentation calls type 1 "not recommended": if there is no data at the moment of RTL, the flight controller reports "RTL: no terrain data, using alt-above-home" (with a rangefinder, "RTL: rangefinder unhealthy, using alt-above-home") and goes to `RTL_ALT_M` above home, across the ridge again. The compromise for hills: type 0 with `RTL_ALT_M` above the highest point on the way home plus a margin, or rally points beyond the ridge.

### Terrain failsafe
The general failsafe logic is in ap-safety-fs; terrain has its own, with two triggers (`ArduCopter/events.cpp`, `mode_auto.cpp`). The first is a timeout: the mode requires terrain (AUTO, Guided, RTL) and `update_wpnav()` gets no height for longer than `FS_TERRAIN_TIMEOUT_MS` = 5000 ms (the documentation says 2 s; the code in 4.6.3 and 4.7 says 5 s). The second is immediate: the next mission command with the Terrain frame cannot set a target (`wp_start()` returned false). The outcome is the same: a "Failsafe: Terrain …" message (in 4.7 the text depends on the source: "data missing" for the database, "Rangefinder Unhealthy" for the rangefinder, "Unavailable" with no source; in 4.6.3 it is always "Failsafe: Terrain data missing"), `ERR Subsys 23 ECode 1`, RTL (`MODE.Rsn = 11`), and on the ground a disarm; an RTL that loses terrain restarts through `restart_without_terrain()` and goes to `RTL_ALT_M` above home. The action is not configurable; there are no bits for it in `FS_OPTIONS`.

### Hazards that are not in the parameters
- **Trees and buildings.** The database is a DSM: canopy and roofs are only partly in it, and the 100 m grid smooths out anything smaller than 50 m. A 25 m forest + a 10 m error = 35 m of your margin. The documentation: on SRTM, no lower than 60 m.
- **Holes in the data.** The original SRTM has voids on steep slopes and over water; the server tiles are filled, but a suspiciously flat patch in the middle of mountains in the profile is a reason not to trust it.
- **Rangefinder over water and grass.** A lidar over water loses the return → `NoData` → with `WP_RFND_USE = 1`, a terrain failsafe after 5 s (or immediately at a waypoint change); over tall grass the "ground" rises to the height of the grass. A radar altimeter (24 GHz, e.g. Ainstein US-D1, Nanoradar NRA24) works over water.
- **Tiles not loaded.** In the field without internet, pre-arm will not pass, and if mission items lie beyond the edge of the loaded data, you get a failsafe in the air.
- **Tilt.** At 29° of pitch the rangefinder sees 45.5 m where the ground is at 39.9 m; there is a correction, but `RNGFND1_MAX` needs a margin of `H / cos θ`.

### Plane and PX4
ArduPlane: `TERRAIN_FOLLOW` is a bitmask (default 0, off; bit 0, value 1, all modes; bits 1–11 FBWB, Cruise, Auto, RTL, Avoid_ADSB, Guided, Loiter, Circle, QRTL, QLand, QLoiter; since 4.7 bit 12 AUTOLAND) selecting where altitude is taken above terrain; mission items are still set by their own frame; `TERRAIN_LOOKAHD` (2000 m): the plane looks ahead along its course and starts climbing before the hill, because its climb is limited by its thrust-to-weight ratio (aero-wing, ap-plane-tuning). Copter has no `TERRAIN_FOLLOW` parameter in either 4.6 or 4.7: only the item frame, `SURFTRAK_MODE` and `RTL_ALT_TYPE`.

PX4 1.18: there is no on-board terrain database, and following works only on a rangefinder, in Position/Altitude: `MPC_ALT_MODE` 0 is altitude from the EKF, 1 Terrain following (on the distance-to-ground estimate), 2 Terrain hold (the default, as in 1.15: above the ground while the horizontal speed is below `MPC_HOLD_MAX_XY`, 0.8 m/s). With the sensor out of range PX4 silently switches to EKF altitude (checked on 1.15). QGroundControl builds terrain-relative missions from its own map; PX4 itself knows nothing about terrain in a mission.

### What was different in 4.6
Before 4.7 the same parameters had other names: `WPNAV_RFND_USE`, `WPNAV_SPEED`, `WPNAV_SPEED_UP`, `WPNAV_SPEED_DN` (cm/s), `WPNAV_TER_MARGIN` → `WP_RFND_USE`, `WP_SPD`, `WP_SPD_UP`, `WP_SPD_DN` (m/s), `WP_TER_MARGIN`; `RNGFND1_MIN_CM/MAX_CM` (cm) → `RNGFND1_MIN/MAX` (m); `RNGFND1_GNDCLEAR` (cm) → `RNGFND1_GNDCLR` (m); `RTL_ALT` (cm) → `RTL_ALT_M` (m). Only in 4.7: `TERRAIN_OPTIONS` bit 2 and the pre-arm check on old DAT files; per the 4.7.0-beta6 release notes (PR 32943) the terrain failsafe also fires when a mission item's terrain altitude cannot be retrieved: a `wp_start()` failure triggered it in 4.6.3 too, and in 4.7.3 (as in 4.7.2) `mode_auto.cpp` adds checks on retrieving the item itself (10 calls to `failsafe_terrain_on_event()` against 8). The source selection and the 5-second timeout are the same. The lab below was captured on 4.6.3: the numbers in the outputs do not depend on parameter names.

### Where it fits

- **Receives:** altitude from the baro, GPS and rangefinder (`est-alt-sources`); the frame of every mission item (`ap-missions`); terrain tiles from the GCS over telemetry.
- **Provides:** the height-above-ground target to the position controller in AUTO and RTL; the terrain failsafe to the overall failure scheme (`ap-safety-fs`); the height margin over trees and structures to mission planning (`ap-missions`).
- **If you get this wrong:** `RTL_ALT_TYPE = 0` and a ridge higher than `RTL_ALT_M` between the vehicle and home → on RTL from any failsafe, a collision with the slope (`ap-safety-fs`). A lidar over water with `WP_RFND_USE = 1` → no data, a terrain failsafe and RTL after 5 s; `ERR` Subsys 23 in the log (`ap-logs`). Tiles not loaded before leaving → the terrain mission will not arm.

## practice
SITL from the Copter-4.6.3 tag (build: the ap-sitl module), ArduCopter launched directly: `arducopter -S -I 2 --model + --speedup 8 --defaults copter.parm -w --home -35.238,149.150,588,90`. Home is at the western foot of Mount Majura (Canberra), 588 m by SRTM; the summit, 876 m, is 2.9 km to the east; the eastern valley, 625 m, is 4.5 km away. The mission: `NAV_TAKEOFF` to 40 m (frame 3), three `NAV_WAYPOINT` items in frame 10 at 40 m (the slope (1.4 km), the summit, the valley), and `NAV_RETURN_TO_LAUNCH`.

The terrain.ardupilot.org server was unreachable from the container (the proxy answered 403), so `TERRAIN_DATA` was served by my own script, following the `install_terrain_handlers_context()` algorithm from `Tools/autotest/vehicle_test_suite.py`, from the SRTM3 tiles stored in the ArduPilot repository (`Tools/autotest/tilecache/srtm/S36E149.hgt.zip`, read by `MAVProxy...mp_elevation.ElevationModel(cachedir, offline=True)`). With internet access MAVProxy does the same: `module load terrain`, then `terrain status` and `terrain check <lat> <lon>`.

### Step 1. No data, no arming
`TERRAIN_ENABLE = 1`, `RNGFND1_TYPE = 0`, the mission uploaded, and the GCS does not answer `TERRAIN_REQUEST`:

```text
  [  42.3 s] PreArm: waiting for terrain data
  TERRAIN_REPORT: spacing=0 pending=336 loaded=0 terrain_height=0.0 current_height=588.1
== now serving terrain tiles (SRTM3 from Tools/autotest/tilecache/srtm)
  TERRAIN_REPORT: spacing=100 pending=0 loaded=392 terrain_height=587.0 current_height=1.1  (served 392 TERRAIN_DATA)
  ARM result: 0
```

336 blocks are waiting for home and the mission items; after 392 `TERRAIN_DATA` packets, `pending = 0`; `terrain_height` is 587.0 against 588 m for home by GPS, `TERR.ROfs = 1.08` m: that is `TERRAIN_OFS_MAX` at work. Record the number of blocks and the load time for your own mission.

### Step 2. A mission on the terrain database
`RTL_ALT_TYPE = 0`, `RTL_ALT_M = 15` (in the 4.6.3 run, `RTL_ALT = 1500`). Telemetry every 40 s (`AGL_db` is `current_height` from `TERRAIN_REPORT`, `AGL_srtm` is `GLOBAL_POSITION_INT.alt` minus an interpolation of the raw tile in Python):

```text
  t= 419.8 AUTO lon=149.16316 AMSL= 654.3 relH=  66.3 terrDB= 614.5 AGL_db= 39.8 AGL_srtm= 39.8
  t= 541.3 AUTO lon=149.17653 AMSL= 773.9 relH= 185.9 terrDB= 738.4 AGL_db= 35.5 AGL_srtm= 35.0
  t= 581.5 AUTO lon=149.18001 AMSL= 865.8 relH= 277.8 terrDB= 833.0 AGL_db= 32.9 AGL_srtm= 28.8
  t= 662.3 AUTO lon=149.18605 AMSL= 831.8 relH= 243.7 terrDB= 783.8 AGL_db= 48.3 AGL_srtm= 46.8
  [ 837.0 s] Mission: 5 RTL
  t= 903.5 AUTO lon=149.19320 AMSL= 666.6 relH=  78.5 terrDB= 643.4 AGL_db= 23.2 AGL_srtm= 24.2
  [ 933.0 s] EKF3 lane switch 1
  t= 943.8 AUTO lon=149.18997 AMSL= 666.6 relH=  78.5 terrDB= 666.6 AGL_db=  0.0 AGL_srtm=  1.5
```

On the gentle section (0–1.7 km, a 3% grade) the true height is 40.5 m (39.0–41.6). On the climb to the summit (2.5–2.85 km, 35% on average, 45% in places) at 10 m/s the ground would rise at 3.5 m/s, while `WP_SPD_UP` gives 2.5: the vehicle falls behind, `WP_TER_MARGIN` cuts the ground speed to 6.4 m/s, and the minimum is 23.5 m above the raw SRTM (`CTUN.TAlt` at that moment is 33.6: the 100 m grid smooths the slope by 10 m). On the 40% descent `WP_SPD_DN` of 1.5 m/s limits things: up to 52 m instead of 40, and the speed drops to 4.7 m/s. RTL from the valley: the current 78.5 m above home exceeds `RTL_ALT_M`, the target is 666.6 m AMSL, and the eastern slope at 3.63 km is higher; the "EKF3 lane switch" at 933 s is the impact with the ground in the simulator. On a real vehicle it is a crash.

{{diagram:chart-terrain-profile|The profile from the log: AUTO holds 40 m above terrain, but RTL with RTL_ALT_TYPE 0 from the valley flies at 666.6 m AMSL and runs into the slope at 3.63 km; RTL_ALT_TYPE 1 with a rangefinder returns across the summit.}}

### Step 3. The same mission with a rangefinder
`RNGFND1_TYPE = 100` (SITL), `RNGFND1_MAX = 60`, `RNGFND1_MIN = 0.1`, `WP_RFND_USE = 1`, `RTL_ALT_TYPE = 1`, `RTL_ALT_M = 40` (in the 4.6.3 run, `RNGFND1_MAX_CM = 6000`, `RNGFND1_MIN_CM = 10`, `WPNAV_RFND_USE = 1`, `RTL_ALT = 4000`). The "waiting for terrain data" pre-arm did not appear: the source is the rangefinder, so the database is not required (`AP_Arming_Copter::terrain_database_required`). The log at 395 s: `RFND.Dist = 45.51`, `ATT.Pitch = −28.9°`, `CTUN.SAlt = 39.85`; 45.51·cos 28.9° = 39.8, so the tilt correction works. The minimum on the climb is 19.9 m true, 3.6 m worse than the database: the `RNGFND_FILT` and `SURFTRAK_TC` lag is added. `SAlt` meanwhile showed 30.9: the SITL rangefinder measures to the same 100 m grid that is in the database (`SIM_Aircraft::ground_height_difference`), so it "sees" the same smoothed slope. A real lidar would have shown the real 20 m, and that is the only way it is better here. RTL with type 1: 27–49 m above terrain across the summit, landing at home, "SIM Hit ground at 0.50 m/s".

{{diagram:chart-terrain-agl|The true height above ground along the route: on the gentle section the database holds 39–41.6 m and the rangefinder 37.5–41 m; on the 35% climb at 10 m/s the WP_SPD_UP limit drops the height to ≈24 m (database) and ≈20 m (rangefinder), and on the 40% descent WP_SPD_DN raises it to ≈51 m (chart points every ~100 m; the full log gives 23.5, 19.9 and 52 m). The cure is speed, not the sensor.}}

The `plot_agl.py` script reads the `.BIN` through `pymavlink.DFReader` (`SIM.Alt/Lat/Lng`, `CTUN.TAlt/SAlt/DAlt`, `TERR.*`, `RFND.Dist/Stat`), computes the true AGL as `SIM.Alt − SRTM(lat, lon)` and plots with `matplotlib`. On hardware use `GPS.Alt` instead of `SIM`, with the same tile.

### Step 4. Losing the rangefinder
`RNGFND1_MAX = 25` (on 4.6.3, `RNGFND1_MAX_CM = 2500`), the rest as in step 3, `RTL_ALT_TYPE = 0`:

```text
t=287.8 RFND.Stat 4 -> 3  Dist=25.0  CTUN.Alt=23.8      # OutOfRangeHigh during the climb to 40 m
t=296.0 MSG Mission: 2 WP                                 # the first Terrain-frame item
t=296.0 MSG Failsafe: Terrain data missing
t=296.0 ERR Subsys 23 ECode 1
t=296.0 MODE Mode 6 Rsn 11                                # RTL, reason TERRAIN_FAILSAFE
```

The database was loaded (`loaded = 392`), but the source is the rangefinder, and there is no fallback. While `NAV_TAKEOFF` (frame 3) was running, terrain was not required; at 296.0 s the mission moved to the first terrain item, `wp_start()` got no height, and the failsafe fired in the same second, without the 5-second timeout. The vehicle switched to RTL and landed. For missions above the sensor's range, use `WP_RFND_USE = 0`.

### Moving to real hardware
1. **Tiles at home.** The mission in Mission Planner with internet, the flight controller connected (`TERRAIN_ENABLE = 1`), `pending = 0`, `loaded = N` in `TERRAIN_REPORT` (MAVLink Inspector); the mission elevation profile (right-click on the Flight Plan map → Map Tool → Elevation Graph) and MAVProxy `terrain check <lat> <lon>` for the extreme points. The alternative is tiles from terrain.ardupilot.org in `APM/TERRAIN` on the SD card. Acceptance: `TERRAIN_REPORT.pending = 0` in the field without internet.
2. **The rangefinder on the bench, props off.** `RNGFND1_TYPE` per model, `RNGFND1_ORIENT = 25`, `RNGFND1_MIN/MAX` per the datasheet (TFmini-S: 0.1/12 m), `RNGFND1_GNDCLR` the sensor height when landed, in meters (connection: est-alt-sources); `RNGFND1_MIN` must be below it, otherwise on the ground the sensor is "unhealthy" and the terrain failsafe disarms right after arming. Hold the vehicle by hand over a floor, grass, dark tiles and a bucket of water: `RFND.Dist` against a tape measure at 0.5 / 1 / 2 / 4 m, status 4 (Good) everywhere except water; at a 30° tilt `CTUN.SAlt` stays put, `RFND.Dist` × 1/cos 30° = 1.15. Acceptance: error ≤ 3% or 5 cm, no `NoData` over grass.
3. **The first flight over terrain**, with a spotter: Loiter at 15–20 m over a slope without trees, `SURFTRAK_MODE = 1`, `TERR_BRK_ENABLE = 1` and `TERR_BRK_ALT = 10` (the applet works on the terrain database and only farther than `TERR_BRK_HDIST`, 100 m, from home), `RTL_ALT_TYPE = 0`, `RTL_ALT_M` above the ridge + 30 m, a battery for a full return. Slowly (≤ 3 m/s) up the slope and down, with `CTUN.SAlt` and `DSAlt` in telemetry. Abort (AltHold and return) if: `SAlt` differs from your eye estimate by more than 5 m; the rangefinder status is not 4 for longer than 2 s; any `Failsafe`; less than 10 m above the ground by eye. Only then AUTO with terrain items at 60 m, `WP_SPD` 5 m/s, grades up to 15%.

Self-check: the lab is done when (SITL): you have three logs (database, rangefinder, rangefinder loss); on the true-AGL plot you named the minimum on the climb, it is close to the module's run (about 24 m with the database, about 20 m with the rangefinder), and the explanation agrees with step 2: a 35% slope at 10 m/s needs a 3.5 m/s climb, while `WP_SPD_UP` gives 2.5; the output shows the "waiting for terrain data" pre-arm, and it disappears after loading (`pending = 0`); the collision with the slope at `RTL_ALT_TYPE = 0` is reproduced, and you found an `RTL_ALT_M` above the ridge with which RTL gets through; the terrain failsafe is found in the log by `ERR Subsys 23` and `MODE Rsn 11`. (Hardware): `TERRAIN_REPORT.pending = 0` in the field; a bench table for the rangefinder with error ≤ 3%; a Loiter log over a slope with `SAlt` within ±2 m of `DSAlt`, and no abort criterion triggered.

## diagnostics
- **Symptom:** `PreArm: waiting for terrain data`, and `TERRAIN_REPORT.pending` does not decrease
  - Possible cause: the GCS does not support `TERRAIN_DATA` or has no internet; `TERRAIN_SPACING` differs from the server's.
  - What to do: Mission Planner/QGC/MAVProxy (`module load terrain`) with internet, or tiles on the SD card in `APM/TERRAIN`; `TERRAIN_SPACING = 100`.
- **Symptom:** `PreArm: terrain data expired, possible errors` after updating to 4.7
  - Possible cause: DAT files from the old server (before 24.02.2026).
  - What to do: delete `APM/TERRAIN` and download again.
- **Symptom:** "Failsafe: Terrain Rangefinder Unhealthy" (in 4.6, "Failsafe: Terrain data missing") and RTL in AUTO, although the tiles are loaded
  - Possible cause: the source is the rangefinder (`WP_RFND_USE = 1`), and it went beyond `RNGFND1_MAX` or lost the return (water).
  - What the log shows: `RFND.Stat` 3 (OutOfRangeHigh) or 1 (NoData) 5 s before `ERR Subsys 23 ECode 1`, or at the moment of "Mission: N WP"; `MODE.Rsn = 11`.
  - What to do: `WP_RFND_USE = 0` for heights above the sensor's range; radar over water.
- **Symptom:** a disarm seconds after arming in AUTO with "Failsafe: Terrain Rangefinder Unhealthy" (in 4.6, "Failsafe: Terrain data missing")
  - Possible cause: on the ground the rangefinder reads less than `RNGFND1_MIN` (status 2, OutOfRangeLow) and is considered unhealthy.
  - What to do: `RNGFND1_MIN` below the sensor's mounting height (documentation: 5 cm).
- **Symptom:** in Loiter over a slope the height above ground drops without the pilot touching the throttle
  - Possible cause: the rangefinder went out of range and surface tracking released the target to baro altitude; or `SURFTRAK_MODE = 0`.
  - What to do: stay below `RNGFND1_MAX` with a margin of `H / cos θ`; `TERR_BRK_ENABLE = 1`.
- **Symptom:** on the climb AGL is 10–20 m below the target and the vehicle slows down
  - Possible cause: grade × speed exceeds `WP_SPD_UP`; `WP_TER_MARGIN` applies the brakes.
  - What to do: lower `WP_SPD` or raise `WP_SPD_UP`; a higher target on steep sections.
- **Symptom:** RTL flies into the ridge between the vehicle and home
  - Possible cause: `RTL_ALT_TYPE = 0` and `RTL_ALT_M` below the ridge relative to home; or type 1, but "RTL: no terrain data, using alt-above-home".
  - What to do: `RTL_ALT_M` ≥ the ridge's height above home + 30 m; rally points beyond the ridge.
- **Symptom:** over a forest the rangefinder shows 20 m, the database 45 m
  - Possible cause: this is not an error: the rangefinder sees the canopy, SRTM an averaged surface.
  - Consequences: a mission on the database passes 20 m above the canopy with a 45 m target.
  - What to do: a database target ≥ 60 m over forest, or the rangefinder as the source.

## checklist
- Three altitude frames; `h_AGL` from the database and from the rangefinder
- The terrain source with `WP_RFND_USE = 1`; no fallback to the database
- Tiles loaded before the flight, `pending = 0`
- `RTL_ALT_TYPE` and `RTL_ALT_M` set for the highest ridge on the way home
- Limits: SRTM ≥ 60 m, trees, water, `WP_SPD_UP` against the grade
- The terrain failsafe in the log: `ERR 23`, `MODE.Rsn 11`, `RFND.Stat`

## references
- ArduPilot Copter — Terrain Following (parameters, failsafe, SRTM, tile loading) | https://ardupilot.org/copter/docs/terrain-following.html | primary | A
- ArduPilot source — AP_Terrain parameters and pre-arm checks (`libraries/AP_Terrain/AP_Terrain.cpp`) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/AP_Terrain/AP_Terrain.cpp | primary | A
- ArduPilot source — terrain source selection and margin (`libraries/AC_WPNav/AC_WPNav.cpp`) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/AC_WPNav/AC_WPNav.cpp | primary | A
- ArduPilot source — terrain failsafe (`ArduCopter/events.cpp`, `config.h` FS_TERRAIN_TIMEOUT_MS) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/ArduCopter/events.cpp | primary | A
- ArduPilot source — RTL altitude type (`ArduCopter/mode_rtl.cpp`) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/ArduCopter/mode_rtl.cpp | primary | A
- ArduPilot source — Copter 4.7 release notes (WPNAV→WP, TERRAIN_OPTIONS, terrain failsafe) | https://github.com/ArduPilot/ardupilot/blob/master/ArduCopter/ReleaseNotes.txt | primary | A
- ArduPilot source — autotest terrain handler and SRTM3 tiles (`Tools/autotest/vehicle_test_suite.py`) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/Tools/autotest/vehicle_test_suite.py | primary | B
- PX4 — Terrain Following/Holding (MPC_ALT_MODE) | https://docs.px4.io/v1.17/en/flying/terrain_following_holding.html | primary | A
- PX4 — Parameter Reference (MPC_ALT_MODE, MPC_HOLD_MAX_XY) | https://docs.px4.io/v1.17/en/advanced_config/parameter_reference.html | primary | A
- ArduPilot Terrain Generator — the tile source (JAXA ALOS, SRTM1 30 m / SRTM3 100 m, 0–84° latitude) | https://terrain.ardupilot.org/ | primary | B
- ArduPilot Lua applet copter_terrain_brake (`libraries/AP_Scripting/applets/copter_terrain_brake.md`) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/AP_Scripting/applets/copter_terrain_brake.md | primary | B
