---
id: ap-safety-fs
title: "Fault tolerance: failsafe, geofence, flight FMEA"
level: L3
readingTime: 40 min
firmware: ArduPilot
status: published
added: 2026-11-08
tags:
  - failsafe
  - geofence
  - FMEA
  - ArduPilot
related:
  - ap-missions
  - ap-lua
  - nav-resilience
  - el-redundancy
  - eng-method-101
next:
  - ap-heavy
source: content/ardupilot/ap-safety-fs.md
source_hash: 11f9b2c648f9
---

## summary
ArduPilot has seven independent failsafes (radio, GCS, battery, EKF, dead reckoning, vibration, geofence) plus pre-arm checks, and each one has an action, a threshold and exceptions. This module treats them as a system: what exactly triggers, in what order, and how they interact (for example, a low battery during an RTL triggered by radio loss); how to run an FMEA of your own platform (failure → how you notice it → what to do → how to verify); and how to **verify every scenario in SITL before you fly**. The lab is an FMEA table with 10+ failures and a test log.

## theory
### ArduCopter failsafe map
| Failsafe | Trigger | Parameters | Actions (values) |
|---|---|---|---|
| Radio (RC) | the receiver stopped outputting frames (no pulses) or the throttle channel ≤ `FS_THR_VALUE` (PWM, 910–1100) | `FS_THR_ENABLE`, `FS_THR_VALUE` | 0 off, 1 RTL, 3 Land, 4 SmartRTL/RTL, 5 SmartRTL/Land, 6 DO_LAND_START or RTL, 7 Brake/Land |
| GCS | no heartbeat from the ground station for > `FS_GCS_TIMEOUT` (5 s by default) | `FS_GCS_ENABLE`, `FS_GCS_TIMEOUT` | 0 off, 1 RTL, 3 SmartRTL/RTL, 4 SmartRTL/Land, 5 Land, 6 DO_LAND_START or RTL, 7 Brake/Land (numbering differs from `FS_THR_ENABLE`); relevant for Guided/telemetry |
| Battery low | voltage < `BATT_LOW_VOLT` (with the `BATT_LOW_TIMER` timer) or remaining capacity < `BATT_LOW_MAH` | `BATT_FS_LOW_ACT` | 0 warning, 1 Land, 2 RTL, 3 SmartRTL/RTL, 4 SmartRTL/Land, 5 Terminate, 6 DO_LAND_START/RTL, 7 Brake/Land |
| Battery critical | < `BATT_CRT_VOLT` / `BATT_CRT_MAH` | `BATT_FS_CRT_ACT` | the same, usually Land |
| EKF | variances > `FS_EKF_THRESH` | `FS_EKF_ACTION` | 0 message, 1 Land if the mode requires position, 2 AltHold, 3 Land always |
| Dead reckoning | the EKF lost its position/velocity sources and is running on wind estimates | `FS_DR_ENABLE`, `FS_DR_TIMEOUT` | Land / RTL / SmartRTL… |
| Vibration | accelerometer clipping, altitude error | `FS_VIBE_ENABLE` | modified altitude estimation and control |
| Geofence | leaving the circle/polygon/altitude limit | `FENCE_ENABLE`, `FENCE_TYPE`, `FENCE_ACTION`, `FENCE_ALT_MAX`, `FENCE_RADIUS`, `FENCE_MARGIN` | 0 message, 1 RTL/Land, 2 Land always, 3 SmartRTL/RTL, 4 Brake/Land, 5 SmartRTL/Land |
| Options | what to do instead of the default action | `FS_OPTIONS` (bitmask) | continue Auto on RC loss (bit 0), continue Auto on GCS loss (bit 1), Guided on RC loss (bit 2), continue landing (bit 3), pilot-controlled modes on GCS loss (bit 4) |

Plus the **pre-arm checks** (`ARMING_SKIPCHK` in 4.7+, `ARMING_CHECK` before that): compass, GPS, INS, parameters, voltage, geofence — disable them one at a time and only when you understand why.

### How they interact
- Priority: **critical battery** overrides everything (Land); a low battery during a radio-loss RTL triggers the battery action (usually RTL as well, but it can be Land — set it deliberately).
- RTL requires position: during an EKF failsafe the action degrades to Land/AltHold.
- RTL first climbs to `RTL_ALT_M` (in 4.6 and earlier — `RTL_ALT` in cm; the minimum altitude above home for the return, 15 m by default; if the vehicle is already higher, it returns at its current altitude), flies home, loiters for `RTL_LOIT_TIME`, and lands (`RTL_ALT_FINAL = 0`). Obstacles taller than RTL_ALT_M mean a collision; the altitude geofence is yet another limiter.
- SmartRTL returns along the path it flew (stored points, `SRTL_POINTS`) — good in a forest or between buildings, but it needs the point memory not to overflow.
- Geofence: on a breach — the action; `FENCE_MARGIN` and an early warning; the pre-arm check won't let you arm outside the fence.
- `FS_OPTIONS` “continue Auto on RC loss” is for BVLOS missions with an authorization; without one, keep it off.

### Flight FMEA
FMEA (Failure Mode and Effects Analysis) is a table: **failure → effect → how to detect it → severity (1–5) → probability (1–5) → detectability (1–5) → RPN = S·P·D → mitigation → verification**. Mitigations: redundancy (see the redundancy module), a failsafe action, a procedure (checklist), a limit (geofence, altitude), pilot training.

A minimum failure list for a copter: RC loss; GCS loss; low battery; GPS degradation; compass fault; motor/ESC failure; BEC failure/FC reboot; vibration/clipping; parameter error after an update; wind above the design limit; video loss (FPV); pilot error (wrong mode); collision with an obstacle during RTL; SmartRTL overflow; rangefinder failure during terrain following.

### What you can and should verify in SITL
Everything listed above except the mechanics: SITL supports `SIM_RC_FAIL` (RC loss), GCS disconnection (just close it), `SIM_BATT_VOLTAGE` (voltage), `SIM_GPS1_ENABLE`, `SIM_MAG1_OFS_*`, `SIM_ENGINE_FAIL`, `SIM_WIND_SPD/DIR`, and the geofence (set up the same way as in real life). Every test gets a log and a record: trigger, reaction time, action, outcome.

### Lua as the last line of defense
A script can watch conditions the standard failsafes don't cover (ESC temperature, disagreement between two GPS units, a mission timer) and act on them (`vehicle:set_mode`, a message, DO_LAND). It is an addition, not a replacement: the script itself can crash — hence `SCR_HEAP_SIZE`, error handling and a SITL test.

{{diagram:failsafe-map|ArduCopter failsafe map: event → parameter → typical action.}}

## practice
### Step 1. Configure
Write down every parameter from the table for your vehicle with a justification: why RTL and not Land; why `BATT_LOW_VOLT` has exactly that value (sag under load + a margin for an RTL from the geofence distance); `RTL_ALT_M` above the obstacles at your field; geofence radius/altitude per the regulations; `FS_OPTIONS` = 0 without a BVLOS authorization.

### Step 2. FMEA
A table of ≥ 10 failures following the template, with RPN; for every RPN above the threshold — a mitigation. Put it in your engineering folder.

### Step 3. SITL tests
For each failsafe: scenario → expected → observed → log. Mandatory: RC loss in Loiter and in Auto; GCS loss in Guided; low battery during RTL; EKF failsafe on GPS loss; altitude and radius geofence; motor failure on a hexa/X8 (if that is your platform).

### Step 4. Field check
Only after SITL: RC failsafe on the ground with props off (turn off the transmitter → motors disarm/message), then at 5 m altitude over a clear field — RC failsafe with a spotter; geofence — approach the boundary at low speed. Lab: FMEA, SITL test log, geofence verified.

**Automatic log check:** `python3 examples/sitl-pymavlink/check_lab_log.py <log.bin> --lab failsafe` (from the course repo) prints PASS/FAIL against the criteria: failsafe triggered (`ERR` Subsys 5), mode changed to RTL/LAND, reaction ≤ 5 s. Put the output in your test log.

## diagnostics
- **Symptom:** nothing happens when you turn off the transmitter
  - Possible cause: the receiver holds the last values (no “no pulses”/failsafe configured in the receiver), `FS_THR_ENABLE = 0`.
  - What to do: set the receiver to “no pulses” or a failsafe throttle value below `FS_THR_VALUE`; enable the FS.
- **Symptom:** RTL flew into a tree
  - Possible cause: `RTL_ALT_M` is below the obstacles.
  - What to do: set RTL_ALT_M from the tallest obstacle + a margin; keep the altitude geofence consistent with it.
- **Symptom:** low battery triggered right after takeoff
  - Possible cause: the threshold ignores voltage sag; `BATT_LOW_TIMER` is too short.
  - What to do: set the threshold from the voltage under load, a 10 s timer, or a mAh threshold.
- **Symptom:** in Auto, on RC loss, the vehicle switched to RTL in the middle of the mission
  - Possible cause: `FS_OPTIONS` bit 0 is not set — that is expected and correct without an authorization.
  - What to do: leave it; with an authorized BVLOS operation — enable it deliberately.
- **Symptom:** won't arm: “Fence requires position”
  - Possible cause: the geofence is enabled, GPS has no fix.
  - What to do: wait for a fix, or fly with the fence only when you have GPS.

## references
- ArduPilot — Failsafe (landing page) | https://ardupilot.org/copter/docs/failsafe-landing-page.html | primary | A
- ArduPilot — Radio Failsafe | https://ardupilot.org/copter/docs/radio-failsafe.html | primary | A
- ArduPilot — Battery Failsafe | https://ardupilot.org/copter/docs/failsafe-battery.html | primary | A
- ArduPilot — Geofence (Cylindrical/Polygon/Altitude) | https://ardupilot.org/copter/docs/common-ac2_simple_geofence.html | primary | A

## checklist
- I know every ArduCopter failsafe, its parameters and actions
- I understand the priorities and interactions (battery > radio, EKF degrades RTL)
- FMEA with ≥ 10 failures, RPN and mitigations, in the engineering folder
- Every failsafe verified in SITL with a log
- Geofence and RTL_ALT_M consistent with the field and the regulations
