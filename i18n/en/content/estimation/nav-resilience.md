---
id: nav-resilience
title: "Navigation and Link Resilience to Interference"
level: L3
readingTime: 35 min
firmware: ArduPilot · INAV · PX4
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
source_hash: 1b73236b97e5
---

## summary
GNSS and the compass are the most vulnerable sensors on board: the satellite signal is weaker than thermal noise, and the Earth's magnetic field is weaker than the field of a power wire. Degradation can be accidental (construction sites, power lines, your own interference, multipath) or intentional; the engineer designs the vehicle so that it **notices** the degradation and reacts to it **safely**. This module is civilian: how to recognize the problem from logs (NSats, HDOP, innovations, GPS glitch, heading jumps), how to set up backup EKF sources and the behavior on GPS/compass loss, how to plan RC/video frequencies and power at a site with other people's transmitters, and how to test every scenario in SITL.

## theory
### Types of degradation and their log signature
| What's happening | GPS.NSats | GPS.HDop / GPA.HAcc | XKF4.SP/SV | Other signs |
|---|---|---|---|---|
| Partial sky obstruction (wall, forest) | drops gradually | grows | creep up | position “wanders” by meters |
| Multipath | normal | HAcc jumps | SP spikes > 1 | position jumps, velocity normal |
| Wideband interference (your own electronics, someone else's transmitter) | drops sharply to 0–3 | HAcc → hundreds of m | SV, SP grow, then GPS glitch | coincides with a device switching on/approaching a site; satellite C/N0 drops (`GRAW`/u-center) |
| Spoofing | “good” fix | “excellent” accuracy | SP/SV grow: the model disagrees with the measurement | position jump with normal satellites; GPS velocity contradicts accel; disagreement with baro/flow |
| Magnetic anomaly/compass interference | — | — | SM > 1, yaw reset in `XKF` messages | heading jumps, “toilet bowling,” “Compass variance” |

The main tool is **source disagreement**: the EKF compares every measurement with the prediction from the inertial sensors. The inertial sensors aren't affected by external interference — that's why innovations grow first. The second tool is signal quality at the receiver itself: the number of satellites and the signal-to-noise ratio (per-satellite C/N0 in u-center; in ArduPilot — raw GPS data logging, `GPS_RAW_DATA`). The combination “satellites normal, innovations growing” suggests spoofing or a wrong model; “no satellites” suggests jamming or an obstructed sky.

### What the firmware does on its own
- **ArduPilot**: GPS glitch protection (innovation gates; when the radial disagreement exceeds `EK3_GLITCH_RAD`, 25 m by default, position and velocity are reset to GPS), lane switching between EKF cores, **EKF failsafe** (`FS_EKF_ACTION`: 0 message only, 1 Land if the mode requires position, 2 AltHold if it requires position, 3 Land from any mode; threshold `FS_EKF_THRESH`), **GPS failsafe** via the EKF (on loss of position in a mode that requires it — switch to Land/AltHold), **yaw source fallback** (`EK3_SRC1_YAW = 3` GPS with compass fallback; GSF yaw estimation from motion — `EK3_SRC1_YAW = 8` or automatically with `COMPASS_USE = 0`). Dead reckoning from inertial sensors and wind gives tens of seconds of acceptable accuracy, not minutes.
- **PX4**: `EKF2_GPS_CHECK` (GPS quality check bitmask), accuracy threshold `COM_POS_FS_EPH`; loss-of-position failsafe `COM_POSCTL_NAVL` (0 — RC available: switch to Altitude/Stabilized; 1 — no RC: Descend or flight termination); u-blox receivers have built-in jamming detection (a sensitivity parameter in the GPS driver), and the state is published in the `sensor_gps` message.
- **INAV**: if there is no position for longer than ~2 s in RTH/WP — Emergency Landing (descent in ANGLE at `failsafe_throttle`, motors cut after `failsafe_off_delay`); `failsafe_procedure` is the reaction to RC loss, not GPS loss; dead reckoning (`inav_allow_dead_reckoning`), `inav_allow_gps_fix_estimation` (estimation without a fix for a wing, based on airspeed + compass).

### Designing for resilience
1. **Reduce your own interference** (see the EMI module): this accounts for 80% of real GPS problems.
2. **Backup EKF sources**: optical flow + rangefinder for low altitudes; baro as the POSZ backup; a second GPS with `GPS_AUTO_SWITCH`; compass + GPS yaw + GSF.
3. **A failsafe that fits the scenario**: what to do on loss of position depends on the location. Over a field: AltHold and a manual landing. Over people: Land. Over water: continuing to shore on inertial navigation — don't count on it, it won't last. The decision is recorded in the engineering folder with its rationale.
4. **GPS-independent modes are always available to the pilot**: Stabilize/AltHold on a switch, and the pilot knows how to use them — this is practiced in training.
5. **Geofence and altitude**: when position degrades, the geofence is useless — account for this in the site risk assessment.

### Frequency and power planning at the site
- A table of occupied video channels and RC bands (the “Field Operations” module): a new participant adds themselves to it instead of switching on a transmitter at random.
- RC: 2.4 GHz and 900 MHz degrade differently; 900 MHz handles range and obstacles better, 2.4 GHz is more crowded (Wi-Fi, other radios). Two receivers on two bands give a backup link.
- Power: the minimum that's sufficient per the link budget (the “Link Budget” module) — extra watts jam your neighbors and heat the VTX; on the ground — minimum power (pit mode).
- Telemetry: a separate channel (900 MHz/4G/LTE) for monitoring status if RC and video are lost.
- Legality of bands and power — the “Regulations” module.

### What's out of scope
Methods of creating interference, countering specific jamming systems, bypassing restrictions — outside this course and illegal in most jurisdictions. The course teaches you to **detect and safely end the flight**, not to “punch through.”

{{diagram:degradation-signatures|How to tell types of navigation degradation apart from the log: satellites and accuracy, EKF innovations, compass.}}

## practice
### Step 1. Signatures in SITL
ArduPilot SITL, Loiter at 20 m:
- **GPS loss**: `SIM_GPS1_ENABLE = 0` (older versions: `SIM_GPS_DISABLE = 1`) for 30 s → what the vehicle does, when the EKF failsafe triggers, how `XKF4.SP`, `XKF1.PN/PE` and the messages in `MSG` behave.
- **GNSS noise**: `SIM_GPS1_NOISE` (older: `SIM_GPS_NOISE`) = 5 m → innovations, Loiter drift.
- **Position jump (glitch)**: `SIM_GPS1_GLTCH_X` (older: `SIM_GPS_GLITCH_X`) = 0.0005° (~50 m) → rejection by the gates; when the disagreement exceeds `EK3_GLITCH_RAD` (25 m by default), the EKF resets the position to GPS.
- **Compass fault**: `SIM_MAG1_OFS_X` (older: `SIM_MAG_OFS_X`) = 300 → `XKF4.SM`, Compass variance, yaw reset.
Fill in a table: scenario → signs → firmware reaction → time to reaction.

### Step 2. Configure the reaction
`FS_EKF_ACTION`, `FS_EKF_THRESH`, `EK3_SRC1_YAW = 3`, `EK3_SRC2_*` with flow (if you have it), `GPS_AUTO_SWITCH`. Repeat the scenarios and compare the behavior. In PX4: `COM_POSCTL_NAVL`, `EKF2_GPS_CHECK`.

### Step 3. Field test (civilian)
At a site where GPS is known to be poor (under a canopy/next to a building): on the ground — log NSats/HDOP/innovations; in flight — only AltHold/Stabilize, watch the EKF status in the GCS. Practice a manual switch from Loiter to AltHold on an EKF message.

### Step 4. Site frequency plan
A table of participants: RC band, video channel, power, telemetry. Check the link budget for your power level. Lab: three degradation scenarios in SITL described from the log; source and failsafe parameters justified.

## diagnostics
- **Symptom:** “EKF variance” and a switch to Land for no visible reason
  - Possible cause: compass/GPS disagreement — interference or multipath.
  - What to do: `XKF4.SM/SP` at the moment of the event; onboard EMI; yaw sources.
- **Symptom:** satellites drop out only over a specific spot
  - Possible cause: external interference or shielding (power lines, buildings, an industrial facility).
  - What to do: mark the zone, don't fly GPS modes there; C/N0 telemetry.
- **Symptom:** GPS shows excellent accuracy, but Loiter drifts off
  - Possible cause: bad data with a “good” fix (spoofing or a receiver error), or the compass.
  - What to do: EKF innovations, comparison with baro/flow, land in AltHold.
- **Symptom:** on GPS loss the vehicle sagged/shot off abruptly
  - Possible cause: the failsafe action doesn't fit the scenario, the pilot isn't ready for AltHold.
  - What to do: revisit `FS_EKF_ACTION`, train the manual modes.
- **Symptom:** RC drops out when a neighbor switches on their radio
  - Possible cause: an overloaded band / identical binding phrase.
  - What to do: frequency plan, a different band, a second receiver.

## references
- ArduPilot — EKF Failsafe | https://ardupilot.org/copter/docs/common-ekf-inav-failsafe.html | primary | A
- ArduPilot — EKF Source Selection and Switching | https://ardupilot.org/copter/docs/common-ekf-sources.html | primary | A
- PX4 — Safety (failsafe) configuration | https://docs.px4.io/main/en/config/safety.html | primary | A

## checklist
- I can tell sky obstruction, multipath, interference and source disagreement apart from the log
- I know what the EKF failsafe does and how it's configured on my vehicle
- I set up backup EKF sources and yaw fallback
- Three degradation scenarios tested in SITL
- The site frequency plan is drawn up, power is set per the link budget
