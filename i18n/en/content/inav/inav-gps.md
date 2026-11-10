---
id: inav-gps
title: "GPS, compass and RTH in INAV"
level: L2
readingTime: 25 min
firmware: INAV 7.0+
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
source_hash: 63581f4739c0
---

## summary
INAV navigation rests on three sensors: GPS gives position and velocity, the compass gives heading, the barometer gives altitude. This module covers how to connect and check them, how ALTHOLD, POSHOLD and RTH work under the hood, the five return altitude modes, safehomes, and what INAV does when GPS is lost in flight. RTH setup is the most important safety setting in INAV: it is also the failsafe.

## theory
### Three sensors and their roles
- **GPS** — horizontal position and velocity. A 3D fix is required; quality is the satellite count and HDOP in the OSD.
- **Compass** — heading. On a multirotor it is mandatory for POSHOLD and RTH: without heading the controller doesn't know which way to tilt the aircraft to fly north. Compass-dependent modes are blocked until it is calibrated.
- **Barometer** — altitude. On a multirotor it is mandatory for ALTHOLD/RTH.

On a wing, heading can be taken from the GPS ground course while moving, and the “heading reset” stick command lets you set it manually by pointing the aircraft north.

### ALTHOLD
Throttle controls vertical speed: stick up — climb, centered — hold. `nav_mc_althold_throttle` sets the neutral point: STICK (the stick position at the moment the mode is engaged), MID_STICK (50%) or HOVER (hover throttle `nav_mc_hover_thr`).

### POSHOLD
Full 3D hold using GPS. `nav_user_control_mode`: ATTI — the right stick sets the tilt, let go and a new point is recorded; CRUISE — the stick sets the speed and the controller works out the tilt itself.

### RTH and return altitude
Home is the point of the first arm (it can be replaced by a safehome). The main parameter is `nav_rth_alt_mode` (CLI values):

- `CURRENT` — return at the current altitude;
- `EXTRA` — current plus `nav_rth_altitude`;
- `FIXED` — climb/descend to `nav_rth_altitude` above the takeoff point;
- `MAX` — the maximum altitude reached in the flight;
- `AT_LEAST` — like FIXED, but climb only, no descent.

With `nav_rth_use_linear_descent = ON`, an aircraft that is above the RTH altitude descends gradually along the way so that it arrives home at `nav_rth_home_altitude` (descent starts at `nav_rth_linear_descent_start_distance`) — this saves energy. For terrain with trees and buildings `AT_LEAST` is a sensible default: the return is never lower than the set altitude. After arriving home a multirotor lands, a wing loiters or lands depending on the settings.

### Safehomes
Up to 8 points. On arming, the nearest enabled one within `safehome_max_distance` (200 m by default) is selected; during RTH it replaces home. `safehome_usage_mode`: OFF, RTH (any RTH) or RTH_FS (failsafe only).

### GPS loss in flight
If a required sensor is lost during RTH, INAV performs an emergency landing after a short timeout (like the LAND procedure). For wings (INAV 8.0+) there is a position estimate without GPS using the compass and barometer (`inav_allow_gps_fix_estimation`) — it is a safety net, not a GPS replacement.

### The INAV position estimator (instead of an EKF)
INAV does not use an EKF: position and velocity are computed by the `inav` complementary estimator with source **weights** — the same division of trust as in the “Attitude” module, only for position: `inav_w_xy_gps_p` = 1.0 (GPS position weight), `inav_w_xy_gps_v` = 2.0 (GPS velocity weight — velocity is trusted more, just as in the EKF), `inav_w_z_baro_p` = 0.35 (baro weight in altitude); optical flow/rangefinder/GPS altitude have their own weights. The estimate is considered valid as long as the uncertainty is below `inav_max_eph_epv` (1000 cm): with poor GPS the navigation modes drop out with a warning in the OSD. For short GPS dropouts there is `inav_allow_dead_reckoning = ON` (dead reckoning from the accelerometer, seconds, not minutes).

### RTH step by step (multirotor)
1. Check `nav_min_rth_distance` (500 cm): if closer, it just lands in place.
2. Climb/descend to the RTH altitude according to `nav_rth_alt_mode` (`nav_rth_altitude` = 1000 cm = 10 m by default); `nav_rth_climb_first` (OFF / ON / ON_FW_SPIRAL for wings) — climb first, then turn: for forests ON is mandatory.
3. Fly home at `nav_auto_speed` (500 cm/s); sanity check `nav_rth_abort_threshold` (50000 cm): if the distance to home grows, RTH is aborted into an emergency landing (a sign of a wrong home point/compass).
4. Over home: `nav_rth_home_altitude` (0 = don't change), then `nav_rth_allow_landing` (NEVER / ALWAYS / FS_ONLY): land or hover.
The hover throttle for the altitude controller is `nav_mc_hover_thr` (1300): set it from the real hover throttle in the log/OSD, otherwise ALTHOLD “drops” when engaged.

### Worked example: RTH setup for a 7" in wooded terrain
`nav_rth_alt_mode = AT_LEAST`, `nav_rth_altitude = 6000` (60 m, above the tallest trees plus margin), `nav_rth_climb_first = ON`, `nav_rth_use_linear_descent = ON`, `nav_rth_home_altitude = 1500` (hover at 15 m, land manually), `nav_rth_allow_landing = FS_ONLY` (land by itself only on failsafe), `safehome_usage_mode = RTH_FS`, a safehome in a clearing. Test: RTH by switch 100 m from home at 30 m altitude — the aircraft first climbs to 60 m, then flies; log/OSD — altitude and distance.

{{diagram:inav-rth-steps|Multirotor RTH in INAV step by step, including the minimum distance check and the emergency landing when moving away from home.}}

## practice
### Step 1. Connection
1. GPS on a free UART; in Ports — the GPS role; in Configuration — the protocol (UBLOX) and baud rate per the module's documentation.
2. Compass over I2C (usually in the same housing as the GPS). Mount it on a mast, away from the power wires.
3. In the configurator: GPS reports satellites, the compass reports a heading that turns along with the aircraft in the right direction.

### Step 2. Compass calibration
In an open area, with no metal nearby, rotate it around all axes for the duration of the calibration. Check `align_mag`: when you rotate the aircraft clockwise, the heading in the configurator increases.

### Step 3. RTH
```
set nav_rth_alt_mode = AT_LEAST
set nav_rth_altitude = 5000
set nav_rth_allow_landing = ALWAYS
save
```

Altitude is in centimeters: 5000 = 50 m. Landing is controlled by `nav_rth_allow_landing`; for wings it's usually `FS_ONLY` or NEVER with loitering.

### Step 4. Test
1. Wait for a 3D fix, note home in the OSD.
2. Fly out 30–50 m, engage RTH with the switch. The aircraft should climb, return and land (multirotor).
3. Repeat with a safehome, if you use one.
4. Record HDOP, satellites and behavior in the log.

## diagnostics
- **Symptom:** no fix or few satellites
  - Possible cause: the antenna is covered, interference from the VTX/power wiring, wrong port or baud rate.
  - What to do: clear view of the sky, move the GPS out, check the UART and protocol.
- **Symptom:** in POSHOLD the aircraft drifts in a spiral
  - Possible cause: compass heading error.
  - What to do: calibration, `align_mag`, eliminate interference.
- **Symptom:** RTH climbs “into the sky”
  - Possible cause: `nav_rth_alt_mode = EXTRA` with a large `nav_rth_altitude`, or `MAX` after a high flight.
  - What to do: choose `AT_LEAST` and a reasonable altitude.
- **Symptom:** on RTH it landed somewhere other than home
  - Possible cause: a safehome kicked in.
  - What to do: check the list and `safehome_usage_mode`.
- **Symptom:** ALTHOLD engages and the aircraft drops/jumps
  - Possible cause: `nav_mc_hover_thr` is far from the real hover throttle; `nav_mc_althold_throttle` = STICK with the stick off center.
  - What to do: set hover_thr from the OSD/log, use MID_STICK or HOVER.
- **Symptom:** RTH aborted into a landing midway
  - Possible cause: `nav_rth_abort_threshold` — the distance to home was growing (wrong compass/home).
  - What to do: compass calibration, check the home point before takeoff (OSD).
- **Symptom:** navigation modes “flicker” and switch off
  - Possible cause: the position estimate is invalid (eph > `inav_max_eph_epv`).
  - What to do: GPS quality (satellites, HDOP), antenna, interference; don't raise the threshold “to make it work”.

## references
- INAV Navigation | https://github.com/iNavFlight/inav/blob/master/docs/Navigation.md | primary | A
- INAV Safehomes | https://github.com/iNavFlight/inav/blob/master/docs/Safehomes.md | primary | A
- INAV GPS fix estimation | https://github.com/iNavFlight/inav/blob/master/docs/GPS_fix_estimation.md | primary | A
- INAV settings reference (settings.yaml) | https://github.com/iNavFlight/inav/blob/master/src/main/fc/settings.yaml | primary | A

## checklist
- GPS gets a 3D fix, the compass is calibrated and correctly oriented
- `nav_rth_alt_mode` and `nav_rth_altitude` are chosen for the terrain
- Safehomes are set up or deliberately disabled
- RTH has been tested with the switch at a short distance
- HDOP and satellites are recorded in the log
