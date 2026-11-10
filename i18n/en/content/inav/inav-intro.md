---
id: inav-intro
title: "Introduction to INAV"
level: L1
readingTime: 20 min
firmware: INAV 7.0+
status: published
added: 2026-11-08
tags:
  - INAV
  - navigation
related:
  - bf-intro
  - ap-intro
next:
  - inav-gps
source: content/inav/inav-intro.md
source_hash: f1445c3a46b5
---

## summary
INAV grew out of the same codebase as Betaflight but went in a different direction: navigation. It is the firmware for people who need position hold, return to home and missions on an inexpensive flight controller — and for wings, which Betaflight doesn't support at all. This module explains where INAV sits between Betaflight and ArduPilot, what in it will be familiar to a Betaflight pilot, what is fundamentally different (platform, arming, navigation modes, safehomes) and how to prepare for the first flight.

## theory
### Where INAV fits
- **Betaflight** — manual flight only, minimal latency.
- **INAV** — manual flight plus navigation: POSHOLD, RTH, missions, wing auto-launch, auto-landing. It runs on the same F4/F7/H7 boards, with the same configurator approach and a similar CLI.
- **ArduPilot** — a full-featured autopilot with an EKF, Lua, companion computers, a thousand parameters and hardware requirements.

INAV is a compromise: navigation without moving to H7 and without learning ArduPilot.

### Platform
The first decision is `platform_type`: MULTIROTOR, AIRPLANE, TRICOPTER (the values HELICOPTER, ROVER, BOAT are in the list but not fully implemented). The platform determines the available modes, mixer presets, whether there are flaps, and the navigation logic. A wing and a quadcopter behave like different firmwares, even though it is one binary.

### What's familiar after Betaflight
The Ports, Receiver, Modes, OSD tabs, the CLI with `set`/`get`/`save`/`diff all`, Blackbox. A CRSF or SBUS receiver is connected the same way.

### What's different
- **Arming by switch only.** Stick arming was removed back in INAV 2.2.
- **Arming is blocked without a GPS fix** if navigation modes are configured (`nav_extra_arming_safety` can bypass this, but it is a deliberate risk).
- **Navigation modes**: NAV ALTHOLD, NAV POSHOLD, NAV RTH, NAV WP, NAV CRUISE (for wings). On a multirotor, POSHOLD and RTH require a calibrated compass.
- **Home** is the point of the first arm; **safehomes** are up to 8 predefined safe landing points; during RTH the nearest of them within `safehome_max_distance` replaces home.
- **Failsafe** with the DROP, LAND (emergency landing), RTH, NONE procedures. RTH as a failsafe is the main reason to run INAV.
- **Programming Framework** — logic conditions right in the firmware, without Lua.

### Requirements
Navigation means GPS (mandatory), a compass (on a multirotor, mandatory for POSHOLD/RTH), a barometer (on a multirotor, practically mandatory: without it altitude is held only by GPS and the accelerometer, noticeably worse). On a wing, heading can be estimated from GPS; a compass is desirable.

### Under the hood: an estimator, not an EKF
INAV computes position and altitude with a weighted complementary estimator (`inav_w_*`) rather than an EKF — simpler and lighter for F4, but without automatic trust/distrust of sensors (module “INAV: GPS and RTH”). Hence the requirements: compass and baro are mandatory for a multirotor; GPS quality matters more than in ArduPilot, where the EKF “rides out” bad samples.

### Why it won't arm: read the OSD
The reason for the arming block is visible in three places: as text in the OSD (lines like “NAVIGATION SAFETY”, “AIRCRAFT IS NOT LEVEL” — the exact wording depends on the version), on the configurator's Setup tab, and in the CLI with the `status` command (a line with the arming-disable flags). Typical reasons: no GPS fix with navigation modes configured (`nav_extra_arming_safety`), accelerometer or compass not calibrated, throttle not at minimum, tilt greater than `small_angle`, arm switch on at power-up, CLI or OSD menu open, the first mission waypoint farther than `nav_wp_max_safe_distance`, a sensor failure. Same principle as in Betaflight (module “Safety”): you fix the cause, you don't work around it.

### Versions and compatibility
INAV 7/8 — H7/F7 are recommended, F4 is supported with memory limitations (some features are cut out in the targets); the configurator must match the firmware's major version exactly; `diff all` carries over between major versions only after review — parameters get renamed (`nav_use_midthr_for_althold` → `nav_mc_althold_throttle`). A firmware update = a full backup + a `diff` comparison + sensor recalibration.

{{diagram:firmware-choice|Where INAV sits among firmwares: GPS navigation and wings without the complexity of ArduPilot/PX4.}}

## practice
### Step 1. Platform and mixer
1. Flash the board with INAV using the correct target.
2. Mixer tab: choose `platform_type` and a preset (Quad X, Flying Wing…), apply, save.
3. With props off, check the outputs: motors and servos respond to the correct sticks.

### Step 2. Sensors
1. Accelerometer calibration (6 positions).
2. Compass: calibrate in an open area, check the orientation (`align_mag`).
3. GPS on a UART; in Configuration — the protocol (usually UBLOX) and baud rate.

### Step 3. Modes
ARM — a separate switch. ANGLE — the base mode. NAV ALTHOLD, NAV POSHOLD, NAV RTH — on a three-position switch in order of increasing autonomy. For a wing: MANUAL must be on a separate switch.

### Step 3b. Checking the estimator on the ground (before the first takeoff)
INAV flies where it thinks it is flying; you can check that without props:
1. **Compass**: the aircraft on level ground, nose pointing north (by a phone compass) — heading in the OSD ±10°. Turn it 90°, 180°, 270° — the heading follows. An error in one direction means interference or a wrong `align_mag`.
2. **Home and arrow**: after the fix, home is recorded; carry the aircraft 20–30 m away — the distance to home in the OSD matches your steps, the home arrow points back where you came from. If the arrow points off to the side, the heading is wrong and RTH will fly the wrong way.
3. **Altitude**: lift the aircraft 2 m (at arm's length/on a ladder) — the altitude in the OSD changes by ~2 m and comes back. A drift of a meter per minute at rest means the baro is in direct sunlight or an airflow.
4. **Satellites**: 3D fix, ≥ 10 satellites, HDOP in the OSD ≤ 1.5–2 before the first navigation flight.

| Check | Normal | If not |
|---|---|---|
| Heading at the cardinal points | ±10° on all four | `align_mag`, recalibrate away from metal, relocate the compass |
| Distance to home when carried | ±2 m over 20 m | wait for a better fix, check the GPS antenna |
| Altitude when lifted 2 m | 2 ± 0.5 m | cover the baro with foam, check the housing |

### Step 4. First flight
1. In an open area, wait for a 3D fix (satellite count in the OSD).
2. Arm, ANGLE, a short hover / circuit.
3. Switch to ALTHOLD, then POSHOLD. Watch how well it holds.
4. RTH at a short distance and low altitude, ready to take over.

## diagnostics
- **Symptom:** won't arm, even though everything is configured
  - Possible cause: no GPS fix with navigation modes configured, or the compass isn't calibrated.
  - What to do: look up the reason in the OSD/configurator, wait for a fix, calibrate the compass.
- **Symptom:** in POSHOLD it “circles” or drifts away
  - Possible cause: the compass — calibration, orientation, interference from power wires.
  - What to do: recalibrate, move it to a mast, check `align_mag`.
- **Symptom:** RTH heads the wrong way
  - Possible cause: home was recorded in the wrong place (armed somewhere else) or a safehome kicked in.
  - What to do: check the home point in the OSD after arming, and the safehome list.
- **Symptom:** in MANUAL the wing is uncontrollable
  - Possible cause: reversed servos or the wrong mixer preset.
  - What to do: check the control surface directions on the bench.
- **Symptom:** after an INAV update some settings “disappeared”
  - Possible cause: renamed parameters in the diff weren't applied.
  - What to do: read the CLI output when loading the diff, read Settings.md for the new version, recalibrate.

## references
- INAV Getting Started | https://github.com/iNavFlight/inav/blob/master/docs/Getting%20Started.md | primary | A
- INAV Navigation | https://github.com/iNavFlight/inav/blob/master/docs/Navigation.md | primary | A
- INAV Controls (arming) | https://github.com/iNavFlight/inav/blob/master/docs/Controls.md | primary | A
- INAV Safehomes | https://github.com/iNavFlight/inav/blob/master/docs/Safehomes.md | primary | A

## checklist
- I understand where INAV sits between Betaflight and ArduPilot
- `platform_type` and the mixer match the aircraft
- The accelerometer and compass are calibrated, the estimator is checked on the ground (heading, home, altitude)
- I can find the reason for an arming block in the OSD, the configurator and `status`
- ARM is on a separate switch, navigation modes in increasing order
- The first RTH was tested close and low
