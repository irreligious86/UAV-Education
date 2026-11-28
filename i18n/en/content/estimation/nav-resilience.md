---
id: nav-resilience
title: "Navigation and link resilience to interference"
level: L3
readingTime: 35 min
firmware: ArduPilot 4.7 (checked against 4.7.3) · INAV 9.1.0 (checked against the source) · PX4 1.18 (checked against v1.18.0)
status: published
added: 2026-11-08
tags:
  - GNSS
  - interference
  - failsafe
  - EKF
  - frequency planning
related:
  - est-gnss
  - ap-ekf
  - el-emi
  - est-alt-sources
  - rf-link-budget
next:
  - ap-ekf
source: content/estimation/nav-resilience.md
source_hash: 6bd43359dbe0
---

## summary
GNSS and the compass are the most vulnerable sensors on board: the satellite signal is weaker than thermal noise, and the Earth's magnetic field is weaker than the field of a power wire. Degradation can be accidental (construction sites, power lines, your own interference, multipath) or deliberate; the engineer designs the vehicle so that it **notices** the degradation and responds **safely**. The module is civilian: how to recognize the problem from logs (NSats, HDOP, innovations, GPS glitch, heading jumps), how to set up backup EKF sources and the behavior on GPS or compass loss, how to plan RC and video frequencies and power at a site with other people's transmitters, and how to test each scenario in SITL.

## theory
### Types of degradation and their log signature
| What is happening | GPS.NSats | GPS.HDop / GPA.HAcc | XKF4.SP/SV | Other signs |
|---|---|---|---|---|
| Partly blocked sky (a wall, a forest) | falls gradually | rises | rise somewhat | the position "wanders" by meters |
| Multipath | normal | HAcc jumps | SP spikes > 1 | position jumps, velocity normal |
| Wideband interference (your own electronics, someone else's transmitter) | drops sharply to 0–3 | HAcc → hundreds of m | SV and SP rise, then GPS glitch | coincides with a device switching on or approaching a site; satellite C/N0 falls (`GRAW`/u-center) |
| Spoofing | a "good" fix | "excellent" accuracy | SP/SV rise: the model disagrees with the measurement | a position jump with normal satellites; GPS velocity contradicts the accel; disagreement with baro/flow |
| Magnetic anomaly / compass interference | — | — | SM > 1, yaw reset in the `XKF` messages | the heading jumps, "toilet bowling," "Compass variance" |

The main tool is **disagreement between sources**: the EKF compares every measurement with the prediction from the inertial sensors. The inertial solution is immune to external interference, which is why the innovations rise first. The second tool is the signal quality at the receiver itself: the satellite count and the signal-to-noise ratio (per-satellite C/N0 in u-center; in ArduPilot, logging the raw GPS data with `GPS_RAW_DATA`). "Satellites normal, innovations rising" suggests spoofing or a wrong model; "no satellites" means jamming or a blocked sky.

{{lesson:ap-ahrs-choice|The `EK3_SRC*` source sets and switching from GPS to optical flow step by step; why the "EKF variance" failsafe fires with zero variances.}}

### What the firmware does by itself
- **ArduPilot**: GPS glitch protection (innovation gates; when the radial disagreement exceeds `EK3_GLITCH_RAD`, 25 m by default, the position and velocity are reset to GPS), lane switching between EKF cores, the **EKF failsafe** (`FS_EKF_ACTION`: 0 Report only, 1 Land if the mode requires position, 2 AltHold if it requires position, 3 Land from all modes; threshold `FS_EKF_THRESH`), the **GPS failsafe** through the EKF (on losing position in a mode that requires it, a switch to Land/AltHold), **yaw source fallback** (`EK3_SRC1_YAW = 3` GPS with Compass Fallback; the GSF yaw estimate from motion, `EK3_SRC1_YAW = 8` or automatically with `COMPASS_USE = 0`). Dead reckoning on the inertial sensors and wind gives acceptable accuracy for seconds on a copter without drag fusion (`EK3_DRAG_BCOEF_*`), tens of seconds on a plane with an airspeed sensor, not minutes.
- **PX4**: `EKF2_GPS_CHECK` (the GPS quality check mask), the accuracy threshold `COM_POS_FS_EPH`; on losing position in Position mode PX4 1.18 (like 1.17) falls back to Altitude by itself, and without an altitude estimate to Stabilized (before 1.17 this was chosen by `COM_POSCTL_NAVL`: 0 Altitude, 1 Land; the parameter is gone); in Mission and Hold, low position accuracy triggers `COM_POS_LOW_ACT` (since 1.16, Return by default; its threshold `COM_POS_LOW_EPH` is off by default); u-blox receivers have built-in jamming detection (its high-sensitivity mode is enabled in 1.18 by `GPS_UBX_JAM_DET`, default 1), and the state is the `jamming_state` field in `sensor_gps`.
- **INAV**: if there is no position for longer than `nav_position_timeout` (5 s; 0 disables it) in RTH/WP, Emergency Landing starts: a descent at `nav_emerg_landing_speed` (5 m/s) while the altitude is valid, until the landing detector (`nav_disarm_on_landing`); `failsafe_throttle` is used only when there is no altitude either; `failsafe_procedure` is the response to RC loss, not GPS loss; dead reckoning (`inav_allow_dead_reckoning`), `inav_allow_gps_fix_estimation` (fixed wing only: heading from the compass (without one the heading drifts quickly), altitude from the baro, airspeed from a pitot or the constant `fw_reference_airspeed`, plus the wind estimated before the loss; the fix and home must exist before takeoff).

{{diagram:gps-loss-ladder|Each firmware steps down the degradation ladder in its own way, but the last step is the same for all: a mode without position and a pilot who can fly it, and the choice of action depends on where you fly.}}

### Designing for resilience
1. **Reduce your own interference** (see the EMI module): in the course's experience, that is most real GPS problems.
2. **Backup EKF sources**: optical flow + rangefinder for low heights; baro as the POSZ backup; a second GPS with `GPS_AUTO_SWITCH`; compass + GPS yaw + GSF.
3. **A failsafe for the scenario**: what to do on position loss depends on the place. Over a field: AltHold and a manual landing. Over people: Land. Over water: do not count on the inertial solution to get you back to shore, it will not last; AltHold and a manual return to shore by eye or by video. Record the decision and its rationale in the engineering folder.
4. **Modes that do not depend on GPS are always available to the pilot**: Stabilize/AltHold on a switch, and the pilot knows how to use them, practiced in training.
5. **Geofence and altitude**: when position degrades, the geofence is useless; account for that in the site risk assessment.

### Planning frequencies and power at the site
- A table of occupied video channels and RC bands (the "Field operations" module): a new participant adds themselves to it instead of switching a transmitter on at random.
- RC: 2.4 GHz and 900 MHz degrade differently; 900 MHz holds range and obstacles better, 2.4 GHz is more crowded (Wi-Fi, other radios). Two receivers on two bands are a link backup.
- Power: the minimum the link budget requires (the "Link budget" module); extra watts jam your neighbors and heat the VTX; on the ground, minimum power (pit mode).
- Telemetry: a separate channel (900 MHz/4G/LTE) to monitor the vehicle's state if RC and video are lost.
- The legality of bands and power is covered in the "Regulations" module.

### What this module does not cover
Methods of creating interference, countering specific jamming systems, and circumventing restrictions are outside the course and illegal in most jurisdictions. The course teaches you to **detect and end the flight safely**, not to "push through."

{{diagram:degradation-signatures|How to tell the types of navigation degradation apart from the log: satellites and accuracy, EKF innovations, compass.}}

### Where it fits

- **Receives:** the satellite count, HDOP and the accuracy estimate (`est-gnss`); the `XKF4` normalized innovations (`ap-ekf`); the level of on-board interference (`el-emi`); the site's table of occupied frequencies (`ops-field`).
- **Provides:** the set of backup EKF sources and the action on position loss to the failsafe configuration (`ap-safety-fs`); a justified decision for the site to the engineering folder (`eng-method-101`); the GNSS row in the threat table (`f-remote-id-security`).
- **If you get this wrong:** the action on position loss chosen without regard to the place → over water the vehicle lands in the water, over people it hangs in AltHold with no pilot ready to fly it manually (`ap-safety-fs`; the recovery reflex is in `diag-troubleshooting`). Your own interference from the VTX or the companion computer taken for external jamming → the cause stays on board (`el-emi`).

## practice
### Step 1. Signatures in SITL
ArduPilot SITL, Loiter at 20 m:
- **GPS loss**: `SIM_GPS1_ENABLE = 0` (before 4.7, `SIM_GPS_DISABLE = 1`) for 30 s → what the vehicle does, when the EKF failsafe fires, how `XKF4.SP`, `XKF1.PN/PE` and the `MSG` messages behave.
- **GNSS altitude noise**: `SIM_GPS1_NOISE` (before 4.7, `SIM_GPS_NOISE`) = 5 m: in the simulator this is only a slow sinusoid on the GPS altitude (amplitude 5 m, period about 12.6 s), and the horizontal position is not noisy → `GPS.Alt` swings, and Loiter does not drift horizontally; the EKF height changes only if it comes from GPS (`EK3_SRC1_POSZ = 3`).
- **A position jump (glitch)**: `SIM_GPS1_GLTCH_X` (before 4.7, `SIM_GPS_GLITCH_X`) = 0.0005° (~55 m) → rejection by the gate; when the disagreement exceeds `EK3_GLITCH_RAD` (25 m by default) the EKF resets the position to GPS.
- **Compass fault**: `SIM_MAG1_OFS_X` (older: `SIM_MAG_OFS_X`) = 300 → `XKF4.SM`, Compass variance, yaw reset.
Record a table: scenario → signs → firmware response → time to the response.

### Step 2. Set up the response
`FS_EKF_ACTION`, `FS_EKF_THRESH`, `EK3_SRC1_YAW = 3`, `EK3_SRC2_*` with flow (if you have it), `GPS_AUTO_SWITCH`. Repeat the scenarios and compare the behavior. In PX4: `COM_POS_LOW_ACT` with the `COM_POS_LOW_EPH` threshold, `EKF2_GPS_CHECK` (before 1.17, also `COM_POSCTL_NAVL`).

### Step 3. Field check (civilian)
At a site where GPS is known to be poor (under a canopy, next to a building): on the ground, log NSats/HDOP/innovations; in flight, only AltHold/Stabilize, and watch the EKF status in the GCS. Practice the manual switch from Loiter to AltHold on an EKF message.

### Step 4. The site frequency plan
A table of participants: RC band, video channel, power, telemetry. Check the link budget for your power. Self-check: the lab is done when, for three SITL degradation scenarios, the table holds the log signs matching the signatures in the theory table, the firmware response and the time to it in seconds, and the chosen `FS_EKF_ACTION` and `EK3_SRC*` sources are recorded together with the flying site they follow from (over a field, AltHold and a manual landing; over people, Land).

**Reference for the self-check.**

| SITL scenario | What the log should show |
|---|---|
| GPS loss for 30 s | `GPS.NSats` drops to zero, `XKF4.SP/SV` rise, the EKF failsafe fires with the `FS_EKF_ACTION` action; on the inertial solution the position holds for seconds on a copter without drag fusion (tens of seconds on a plane with an airspeed sensor), not minutes |
| 5 m noise (altitude) | `GPS.Alt` swings by ±5 m with a period of about 12.6 s; `XKF4.SP` and horizontal Loiter barely change; with `EK3_SRC1_POSZ = 3`, `XKF4.SH` rises and the height "breathes" |
| A ~55 m jump | the outlier is rejected by the gate (`XKF4.SP` > 1); a disagreement beyond `EK3_GLITCH_RAD` (25 m) resets the position and velocity to GPS |
| Compass offset 300 | `XKF4.SM` > 1, "Compass variance," yaw reset |

Common wrong results: nothing happens on "GPS loss" (in versions before 4.7 the parameter is called `SIM_GPS_DISABLE`); the vehicle "does not react" to the EKF failsafe, because `FS_EKF_ACTION = 0` (Report only) is set or the mode does not require position.

## diagnostics
- **Symptom:** "EKF variance" and a switch to Land for no visible reason
  - Possible cause: compass/GPS disagreement from interference or multipath.
  - What to do: `XKF4.SM/SP` at the moment of the event; on-board EMI; yaw sources.
- **Symptom:** satellites disappear only over a particular spot
  - Possible cause: external interference or shielding (power lines, buildings, an industrial site).
  - What to do: mark the zone and do not fly GPS modes there; C/N0 telemetry.
- **Symptom:** GPS shows excellent accuracy, but Loiter wanders off
  - Possible cause: wrong data with a "good" fix (spoofing or a receiver fault), or the compass.
  - What to do: EKF innovations, a comparison with baro/flow, land in AltHold.
- **Symptom:** on GPS loss the vehicle sank or veered sharply
  - Possible cause: the failsafe action does not fit the scenario, the pilot is not ready for AltHold.
  - What to do: revisit `FS_EKF_ACTION`, train the manual modes.
- **Symptom:** RC drops out when a neighbor switches on their radio
  - Possible cause: a crowded band / the same binding phrase.
  - What to do: a frequency plan, a different band, a second receiver.

## references
- ArduPilot — EKF Failsafe | https://ardupilot.org/copter/docs/common-ekf-inav-failsafe.html | primary | A
- ArduPilot — EKF Source Selection and Switching | https://ardupilot.org/copter/docs/common-ekf-sources.html | primary | A
- PX4 — Safety (failsafe) configuration | https://docs.px4.io/main/en/config/safety.html | primary | A

## checklist
- I can tell a blocked sky, multipath, interference and source disagreement apart from the log
- I know what the EKF failsafe does and how it is set up on my vehicle
- I set up backup EKF sources and the yaw fallback
- I tested three degradation scenarios in SITL
- I drew up the site frequency plan, with power set by the link budget
