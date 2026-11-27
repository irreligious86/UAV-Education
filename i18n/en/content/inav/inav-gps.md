---
id: inav-gps
title: "GPS, compass and RTH in INAV"
level: L2
readingTime: 25 min
firmware: INAV 9.1 (checked against 9.1.0)
status: published
added: 2026-03-21
tags:
  - GPS
  - compass
  - RTH
related:
  - inav-intro
  - ap-ekf
next:
  - inav-missions
source: content/inav/inav-gps.md
source_hash: cbf644c667f3
---

## summary
INAV navigation rests on three sensors: GPS provides position and velocity, the compass provides heading, the barometer provides altitude. This module covers how to connect and check them, how ALTHOLD, POSHOLD and RTH work inside, the five RTH altitude modes, safehomes and what INAV does when GPS is lost in flight. The RTH setup is the most important safety setup in INAV: it is also the failsafe.

## theory
### Three sensors and their roles
- **GPS** — horizontal position and velocity. A 3D fix is required; the quality is the satellite count and HDOP in the OSD.
- **Compass** — heading. A multirotor needs it for POSHOLD and RTH: without a heading the controller does not know which way to tilt the aircraft to fly north. If a compass is connected, arming is blocked until it is calibrated. Without a compass (since 7.1) the navigation modes become available only after the heading has been obtained from GPS by flying in a straight line; in 9.1 it can be set on the ground: point the nose north and give the compass calibration stick command (throttle high, yaw right, pitch back). Without a compass the position holds for a few minutes, then the heading drifts and the “toilet bowl” begins.
- **Barometer** — altitude. Strongly recommended on a multirotor for ALTHOLD/RTH: without it altitude is taken from GPS and held noticeably worse. How `inav_default_alt_sensor` (default GPS; BARO, GPS_ONLY, BARO_ONLY) splits the trust between baro and GPS is covered in `inav-sensors-extra`.

A fixed wing can get its heading from the GPS ground course while moving: INAV uses it with a 3D fix, at least 6 satellites and a ground speed of 3 m/s or more. Until the first acceleration there is no heading. The 9.1 “heading = north” stick command works only on a multirotor without a compass; a plane has no way to set the heading by hand.

### GPS receiver setup: the 9.1.0 table and what to do when there is no fix
INAV configures u-blox modules itself at every power-up: you do not need to write anything to the receiver in u-center beforehand, and whatever you wrote will be overwritten. The values from `settings.yaml` 9.1.0:

| Setting | Default in 9.1.0 | Values | When to touch it |
|---|---|---|---|
| `gps_provider` | UBLOX | UBLOX, MSP, FAKE | MSP — the position is sent by an external device over MSP; FAKE — SITL only |
| `gps_auto_config` | ON | ON / OFF | OFF — only if the module is configured by hand and must stay that way |
| `gps_auto_baud` | ON | ON / OFF | — |
| `gps_auto_baud_max_supported` | 230400 | 9600 … 921600 | M8 — up to 460800, M10 — up to 921600 |
| `gps_ublox_use_galileo` / `_beidou` / `_glonass` | ON / ON / OFF (in 8.x Galileo and BeiDou were OFF) | ON / OFF | each constellation is enabled at the expense of the others (the description in `settings.yaml`): a u-blox M8 module receives no more than three at once, an M10 — four |
| `gps_ublox_nav_hz` | 8 (10 in 8.x) | 5–200 | an M9 at 10 Hz or higher tracks only 16 satellites, below 10 Hz — 32 |
| `gps_sbas_mode` | NONE | AUTO, EGNOS, WAAS, MSAS, GAGAN, SPAN, NONE | EGNOS in Europe, WAAS in the USA; AUTO chooses by itself |
| `gps_dyn_model` | AIR_2G | PEDESTRIAN … AIR_4G, SEA, MOWER | AIR_4G — an aggressive aerobatic aircraft; PEDESTRIAN and AUTOMOTIVE on a fast aircraft cause flyaways |
| `gps_min_sats` | 6 | 5–10 | the minimum for a fix, not for navigation |

The procedure if the fix does not come or comes after 10 minutes:
1. **The link to the module.** `status` in the CLI, the `Sensor status` line: `GPS=OK` — the module answers; `UNAVAILABLE` or `FAILING` — the wrong UART, the wrong port function, or TX/RX swapped. The baud rate is taken from Ports: auto-configuration switches the module to it, and `gps_auto_baud_max_supported` limits the baud rates the firmware tries while searching for the module.
2. **The sky.** The `gpssats` command (the command list is in `inav-cli-backup`) prints the u-blox satellites with their signal level. If satellites are visible but weak and disappear when the VTX is on, that is interference from the VTX or the power wires: move the module away, check with the VTX off.
3. **Constellations and update rate.** Few satellites with a good signal — check that the constellations are enabled for your module; for an M9 use a rate below 10 Hz.
4. **Cold start.** The first fix of a new module without a backup battery takes minutes; a repeat fix with a live battery takes seconds. If it is slow every time, the module has no backup power.
5. **u-center.** If you need direct access to the module (to update the module firmware, to read its config): `gpspassthrough`, then u-center on the flight controller's COM port; the only way out is a power cycle.

The check: in an open area, 1–3 minutes after a cold start, there is a 3D fix, at least 10 satellites and an HDOP of no more than 2 (the same norms as in `inav-setup-scratch` before the first hover).

### A compass on a mast and at an angle
The compass alignment is set in two ways, and they do not add up:
- `align_mag` — presets in 90° steps (CW0, CW90 … CW270FLIP); they work together with `align_board_*`;
- `align_mag_roll`, `align_mag_pitch`, `align_mag_yaw` — arbitrary angles in tenths of a degree (−1800…3600, default 0). If any of the three is not 0, the firmware assumes the compass is externally mounted and **ignores** both `align_board_*` and `align_mag` (the description in `settings.yaml`). These three numbers are what the Alignment Tool tab of Configurator 9.x writes (`tabs/magnetometer.js` reads and writes exactly `align_mag_roll/pitch/yaw`): you set the angles so that the module model on the screen sits the way the module sits on the aircraft.

The procedure: the module on a mast at 45° → Alignment Tool → save → compass calibration → a check at the four cardinal points: the heading in the Configurator matches a paper compass within ±10° (the same norm as in the ground check of `inav-setup-scratch`), and the heading does not move noticeably when the aircraft is tilted. An error of exactly 90° or 180° is a wrong yaw rotation; a heading that is right on a level aircraft but drifts when it is tilted is a wrong roll or pitch of the module.

### ALTHOLD
The throttle controls the vertical speed: stick up — climb, centered — hold. `nav_mc_althold_throttle` sets the neutral point: STICK (the stick position at the moment the mode is enabled), MID_STICK (50%) or HOVER (the hover throttle `nav_mc_hover_thr`).

### POSHOLD
Full 3D hold on GPS. `nav_user_control_mode`: ATTI — the right stick sets the tilt, and when you release it a new point is recorded; CRUISE — the stick sets the speed, and the controller works out the tilt itself.

### RTH and the return altitude
Home is the point of the first arm (`inav_reset_home`, see above; it may be replaced by a safehome). The main setting is `nav_rth_alt_mode` (CLI values):

- `CURRENT` — return at the current altitude;
- `EXTRA` — the current altitude plus `nav_rth_altitude`;
- `FIXED` — climb/descend to `nav_rth_altitude` above the takeoff point;
- `MAX` — the maximum altitude of the flight;
- `AT_LEAST` — like FIXED, but climb only, no descent.

With `nav_rth_use_linear_descent = ON` an aircraft that is above the RTH altitude descends gradually en route so as to arrive home at `nav_rth_home_altitude` (the descent starts at `nav_rth_linear_descent_start_distance`) — this saves energy. For terrain with trees and buildings `AT_LEAST` is a sensible default: the return is never lower than the set value. After arriving home a multirotor lands, a fixed wing loiters or lands depending on the setup.

### Home: when it is recorded and when it moves
While the aircraft is disarmed and the position estimate is usable, home is continuously overwritten with the current point. After that `inav_reset_home` decides (default FIRST_ARM): FIRST_ARM — home is fixed by the first arm after power-up, and a repeat arm (for example, after landing in a field) does not move it; EACH_ARM — every arm records a new home; NEVER — home is the first usable position after power-up. Arming in the air after an accidental disarm (emergency rearm) does not reset home even with EACH_ARM. In flight the HOME RESET mode (id 30) moves home to the current point — except during failsafe, RTH, a mission and autoland. The zero altitude is set by the separate `inav_reset_altitude` with the same values. The check: before takeoff the distance to home in the OSD is 0–2 m; after a repeat arm 50 m from the place of the first one it is 50 m (FIRST_ARM) or 0 (EACH_ARM).

### Safehomes
Up to 8 points. On arming, the nearest enabled one within `safehome_max_distance` (200 m by default) is selected; on RTH it replaces home. `safehome_usage_mode`: OFF, RTH (any RTH) or RTH_FS (failsafe only). The cases where home is not replaced, as well as geozones, returning along your own track (trackback) and the fixed-wing landing approach from `fwapproach`, are in `inav-geozones-landing`.

### Losing GPS in flight
The rule from `navigation.c` 9.1.0: if the position estimate is lost completely (not even dead reckoning is left) for longer than `nav_position_timeout` (5 s, 0–10; 0 — wait forever), RTH and a mission switch to an emergency landing: a descent at `nav_emerg_landing_speed` (500 cm/s) on the altitude estimate until the landing detector triggers. CRUISE and COURSE HOLD in this case simply switch off and hand control back to the pilot. With `nav_position_timeout = 0` a failsafe RTH without a position lands immediately where it is. If the altitude estimate is lost as well, there is no rate-controlled descent: the controller holds the fixed throttle `failsafe_throttle` (`navigation_multicopter.c`). `failsafe_off_delay` (20 s) is the time limit of the failsafe LAND procedure and has nothing to do with losing GPS (`inav-setup-scratch`, `nav-resilience`). A mission on RC loss is a separate rule: `failsafe_mission_delay` (0 — the failsafe procedure immediately, N — after N s, −1 — the mission runs to the end), in detail in `inav-missions`. For a fixed wing (INAV 8.0+) there is GPS fix estimation from the compass and the barometer (`inav_allow_gps_fix_estimation`) — that is a safety net, not a replacement for GPS.

{{diagram:inav-gps-loss-modes|Without a position RTH and a mission wait for nav_position_timeout and land the aircraft, CRUISE and COURSE HOLD hand control back to the pilot; at 0 a failsafe RTH lands immediately, and without an altitude estimate only failsafe_throttle is left.}}

### The INAV position estimator (instead of an EKF)
INAV does not use an EKF: position and velocity are computed by the complementary estimator `inav` with source **weights** — the same split of trust as in the “Attitude” module, only for position: `inav_w_xy_gps_p` = 1.0 (the weight of GPS position), `inav_w_xy_gps_v` = 2.0 (the weight of GPS velocity — velocity is trusted more, as in an EKF), `inav_w_z_baro_p` = 0.35 (the baro weight in altitude); optical flow, the rangefinder and GPS altitude have weights of their own. In 9.0 the defaults of three altitude weights were raised: `inav_w_z_baro_v`, `inav_w_z_gps_p` and `inav_w_z_gps_v` = 0.35 (in 8.0 — 0.1, 0.2 and 0.1). The 9.1 estimator relies more on the accelerometer, so frame vibration degrades the hold more noticeably than before. The estimate is considered valid while the uncertainty is below `inav_max_eph_epv` (1000 cm): with poor GPS the navigation modes drop out with a warning in the OSD. For short GPS outages — `inav_allow_dead_reckoning = ON` (dead reckoning on the accelerometer, seconds, not minutes).

### RTH step by step (multirotor)
1. The `nav_min_rth_distance` check (500 cm): closer than that — it simply lands on the spot.
2. Climb/descent to the RTH altitude per `nav_rth_alt_mode` (`nav_rth_altitude` = 1000 cm = 10 m by default); `nav_rth_climb_first` (OFF / ON / ON_FW_SPIRAL for a fixed wing) — climb first, then turn: mandatory ON in a forest.
3. The flight home at `nav_auto_speed` (500 cm/s); the sanity check `nav_rth_abort_threshold` (50000 cm): if the distance to home is increasing, RTH aborts into an emergency landing (a sign of a wrong home or compass).
4. Over home: `nav_rth_home_altitude` (0 = do not change), then `nav_rth_allow_landing` (NEVER / ALWAYS / FS_ONLY): land or hover.
The hover throttle for the altitude controller is `nav_mc_hover_thr` (1300): set it from the real hover throttle in the log/OSD, otherwise ALTHOLD sags when it is enabled.

### A worked example: RTH setup for a 7" in wooded terrain
`nav_rth_alt_mode = AT_LEAST`, `nav_rth_altitude = 6000` (60 m, above the tallest trees plus a margin), `nav_rth_climb_first = ON`, `nav_rth_use_linear_descent = ON`, `nav_rth_home_altitude = 1500` (hover at 15 m, land by hand), `nav_rth_allow_landing = FS_ONLY` (land by itself only on failsafe), `safehome_usage_mode = RTH_FS`, a safehome in a clearing. The check: RTH from the switch 100 m from home at 30 m of altitude — the aircraft first climbs to 60 m, then flies; the log/OSD — altitude and distance.

{{diagram:inav-rth-steps|Multirotor RTH in INAV step by step, including the minimum distance check and the emergency landing when the aircraft moves away from home.}}

### Place in the system

- **Receives:** position and velocity from GPS (`est-gnss`), heading from the compass, altitude from the barometer; the hover throttle `nav_mc_hover_thr` from the first flight (`inav-setup-scratch`); the platform choice (`inav-intro`).
- **Provides:** the position estimate and home — to the POSHOLD and RTH modes, to missions (`inav-missions`) and to failsafe with the RTH procedure (`inav-setup-scratch`).
- **If you get it wrong here:** an RTH altitude below the obstacles or `nav_rth_climb_first = OFF` in a forest → on a link loss during a mission the aircraft heads home into the trees (`inav-missions`). A wrong home or compass → the distance to home grows and RTH aborts into an emergency landing. `nav_mc_hover_thr` not set from the real hover → ALTHOLD sags when it is enabled (`inav-setup-scratch`).

## practice
### Step 1. Connection
1. GPS on a free UART; in Ports — the GPS role and the baud rate from the module documentation; on the GPS tab — the protocol (UBLOX). In 9.1 Galileo and BeiDou are enabled by default and the rate `gps_ublox_nav_hz` = 8 Hz (before 9.1 — the constellations off, 10 Hz); the preset on the GPS tab of Configurator 9.1 picks the constellations and the rate for an M8, M9 or M10.
2. The compass on I2C (usually in the same housing as the GPS). Put it on a mast, away from the power wires.
3. In the configurator: the GPS reports satellites, the compass reports a heading that turns the right way together with the aircraft.

### Step 2. Compass calibration
In an open area, with no metal nearby, rotate the aircraft around all axes for the duration of the calibration. Check `align_mag`: when the aircraft is turned clockwise, the heading in the configurator increases.

### Step 3. RTH
```
set nav_rth_alt_mode = AT_LEAST
set nav_rth_altitude = 5000
set nav_rth_allow_landing = ALWAYS
save
```

The altitude is in centimeters: 5000 = 50 m. For landing — `nav_rth_allow_landing`; for a fixed wing it is usually `FS_ONLY` or NEVER with loitering.

**An exercise without hardware: what RTH will do.** All the answers follow from the theory of this module; work them out on paper.

1. `nav_rth_altitude = 5000`, the highest altitude of the flight is 95 m. Fill in a 2 × 5 table: at what altitude the aircraft heads home if RTH is activated at 30 m and at 70 m, for each of the five values of `nav_rth_alt_mode` (CURRENT, EXTRA, FIXED, MAX, AT_LEAST).
2. Convert to meters and answer. The defaults: `nav_min_rth_distance` = 500, `nav_auto_speed` = 500, `nav_rth_abort_threshold` = 50000, `inav_max_eph_epv` = 1000. What does a multirotor do if RTH is activated 3 m from home and 8 m from home? How many seconds does the flight home from 600 m take? At what position uncertainty do the navigation modes drop out?
3. A safehome is defined and enabled, `safehome_max_distance` is at the default, `safehome_usage_mode = RTH_FS`. Where does the aircraft go in four cases: armed 150 m from the safehome and RTH from the switch; the same arm and a failsafe RTH; armed 250 m from the safehome and a failsafe RTH; armed at 150 m but `safehome_usage_mode = OFF`, a failsafe RTH?
4. Does the aircraft have a heading: a fixed wing without a compass, 3D fix, 5 satellites, 12 m/s; a fixed wing, 8 satellites, 2 m/s; a fixed wing, 8 satellites, 4 m/s; a multirotor with a compass connected but not calibrated — what about arming?

### Step 4. Test
1. Wait for a 3D fix, note home in the OSD.
2. Fly 30–50 m away, activate RTH from the switch. The aircraft should climb, return and land (multirotor).
3. Repeat with a safehome if you use one.
4. Record HDOP, the satellites and the behavior in the log.

Self-check: the lab is done when:
- the altitude table: from 30 m — CURRENT 30, EXTRA 80, FIXED 50, MAX 95, AT_LEAST 50 m; from 70 m — CURRENT 70, EXTRA 120, FIXED 50, MAX 95, AT_LEAST 70 m;
- the conversion: 5 m, 5 m/s, 500 m, 10 m; 3 m from home — a landing on the spot, 8 m — a normal RTH; 600 m — 120 s; the modes drop out at an uncertainty above 10 m;
- safehome: from the switch — to the arming point; on failsafe at 150 m — to the safehome; at 250 m — to the arming point; with `OFF` — to the arming point;
- heading: no (too few satellites, at least 6 are needed); no (3 m/s or more is needed); yes; arming is blocked until the compass is calibrated;
- on hardware (if you have it): in the step 4 test the aircraft climbed to the altitude from your table for the selected `nav_rth_alt_mode` to within a few meters on the OSD, and HDOP and the satellite count are recorded in the log.

**Reference for the self-check.** The rules the table is filled in by: EXTRA — the current altitude plus `nav_rth_altitude` (30 + 50 and 70 + 50); FIXED — always 50 m, from 70 m the aircraft descends; AT_LEAST — like FIXED but climb only, so from 70 m it stays at 70; MAX — the highest altitude of the flight, independent of the current one. A safehome replaces home only if at arming it was closer than `safehome_max_distance` (200 m) and the usage mode allows this kind of RTH: `RTH_FS` — on failsafe only. Common wrong answers: AT_LEAST from 70 m written as 50 — that is the FIXED behavior, and AT_LEAST does not descend; EXTRA computed as 50 m — `nav_rth_altitude` is added to the current altitude, hence the symptom “RTH climbs into the sky”; `nav_rth_altitude = 5000` read as 5000 m or 5 m — the unit is the centimeter; for the fixed wing with 5 satellites the answer “there is a heading, the speed is high after all” — there are three conditions, and all of them must hold.

## diagnostics
- **Symptom:** no fix or few satellites
  - Possible cause: the antenna is obstructed, interference from the VTX/power wires, the wrong port or baud rate.
  - What to do: go through the procedure from the “GPS receiver setup” section: `status` (`GPS=OK`), `gpssats` with and without the VTX, the constellations and `gps_ublox_nav_hz` for the module.
- **Symptom:** in POSHOLD the aircraft drifts away in a spiral
  - Possible cause: a compass heading error.
  - What to do: calibration, `align_mag` or, for a module at an angle, `align_mag_roll/pitch/yaw` (Alignment Tool), remove the interference.
- **Symptom:** after a landing and a repeat arm RTH heads somewhere other than where you first took off today
  - Possible cause: `inav_reset_home = EACH_ARM` (home is the point of the last arm), or HOME RESET was activated in flight.
  - What to do: for flights with restarts in the field — FIRST_ARM (default); before takeoff check the distance to home in the OSD.
- **Symptom:** RTH climbs “into the sky”
  - Possible cause: `nav_rth_alt_mode = EXTRA` with a large `nav_rth_altitude`, or `MAX` after a high flight.
  - What to do: choose `AT_LEAST` and a sensible altitude.
- **Symptom:** on RTH it landed somewhere other than home
  - Possible cause: a safehome was used.
  - What to do: check the list and `safehome_usage_mode`.
- **Symptom:** ALTHOLD is enabled and the aircraft sags/jumps
  - Possible cause: `nav_mc_hover_thr` is far from the real hover throttle; `nav_mc_althold_throttle` = STICK with the stick off center.
  - What to do: set hover_thr from the OSD/log, use MID_STICK or HOVER.
- **Symptom:** RTH aborted into a landing midway
  - Possible cause: `nav_rth_abort_threshold` — the distance to home was increasing (a wrong compass/home).
  - What to do: compass calibration, check the home point before takeoff (OSD).
- **Symptom:** the navigation modes “flicker” and drop out
  - Possible cause: the position estimate is invalid (eph > `inav_max_eph_epv`).
  - What to do: GPS quality (satellites, HDOP), the antenna, interference; do not raise the threshold “to make it work”.

## references
- INAV Navigation | https://github.com/iNavFlight/inav/blob/master/docs/Navigation.md | primary | A
- INAV Safehomes | https://github.com/iNavFlight/inav/blob/master/docs/Safehomes.md | primary | A
- INAV GPS fix estimation | https://github.com/iNavFlight/inav/blob/master/docs/GPS_fix_estimation.md | primary | A
- INAV settings reference (settings.yaml) | https://github.com/iNavFlight/inav/blob/master/src/main/fc/settings.yaml | primary | A

## checklist
- The GPS gives a 3D fix, the compass is calibrated and correctly aligned
- `nav_rth_alt_mode` and `nav_rth_altitude` are chosen for the terrain
- Safehomes are configured or deliberately turned off
- RTH was tested from the switch at a short distance
- HDOP and the satellites are recorded in the log
