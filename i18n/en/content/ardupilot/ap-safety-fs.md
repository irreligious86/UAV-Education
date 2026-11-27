---
id: ap-safety-fs
title: "Fault tolerance: failsafes, geofence, flight FMEA"
level: L3
readingTime: 40 min
firmware: ArduPilot 4.7 (checked against 4.7.3)
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
source_hash: 66570c55e809
---

## summary
ArduPilot has seven independent failsafes (radio, GCS, battery, EKF, dead reckoning, vibration, geofence) plus the pre-arm checks, and each has an action, a threshold, and exceptions. This module treats them as a system: what exactly triggers, in what order, and how they interact (for example, a low battery during an RTL caused by radio loss), how to run an FMEA of your platform (failure → how to detect it → what to do → how to test it), and how to **test every scenario in SITL before flying**. The lab is an FMEA table with 10+ failures and a test log.

## theory
### ArduCopter failsafe map
| Failsafe | Trigger | Parameters | Actions (values) |
|---|---|---|---|
| Radio (RC) | the receiver stops sending frames (no pulses) or the throttle channel is below `FS_THR_VALUE` for 3 consecutive reads (PWM, 910–1100) | `FS_THR_ENABLE`, `FS_THR_VALUE` | 0 Disabled, 1 RTL, 3 Land, 4 SmartRTL or RTL, 5 SmartRTL or Land, 6 DO_LAND_START or RTL, 7 Brake or Land |
| GCS | no heartbeat from the ground station for > `FS_GCS_TIMEOUT` (5 s by default) | `FS_GCS_ENABLE`, `FS_GCS_TIMEOUT` | 0 Disabled, 1 RTL, 3 SmartRTL or RTL, 4 SmartRTL or Land, 5 Land, 6 DO_LAND_START or RTL, 7 Brake or Land (the numbering differs from `FS_THR_ENABLE`); relevant for Guided and telemetry control |
| Low battery | voltage < `BATT_LOW_VOLT` (with the `BATT_LOW_TIMER` timeout) or remaining capacity < `BATT_LOW_MAH` | `BATT_FS_LOW_ACT` | 0 Warn only, 1 Land, 2 RTL, 3 SmartRTL or RTL, 4 SmartRTL or Land, 5 Terminate, 6 DO_LAND_START or RTL, 7 Brake or Land |
| Critical battery | voltage < `BATT_CRT_VOLT` (the same `BATT_LOW_TIMER` timeout) or remaining capacity < `BATT_CRT_MAH` | `BATT_FS_CRT_ACT` | the same values; the default is 0, warn only, so you set the action explicitly (usually 1 Land) |
| EKF | variances > `FS_EKF_THRESH` | `FS_EKF_ACTION` | 0 Report only (added in 4.7), 1 Land if the mode requires position, 2 AltHold, 3 Land always |
| Dead reckoning | the EKF has lost its position and velocity sources and relies only on wind estimates (the message is `Dead Reckoning started`) | `FS_DR_ENABLE` (default 2), `FS_DR_TIMEOUT` (default 30 s, 0–120) | 0 Disabled, 1 Land, 2 RTL, 3 SmartRTL or RTL, 4 SmartRTL or Land, 6 DO_LAND_START or RTL; only in modes that require position; after `FS_DR_TIMEOUT` dead reckoning ends and the EKF failsafe triggers |
| Vibration | EKF vertical velocity and position innovations both positive with high velocity variance for 1 s (a symptom of clipping/aliasing) | `FS_VIBE_ENABLE` | modified altitude estimation and control (`ERR` FAILSAFE_VIBE, "Vibration compensation ON") |
| Geofence | leaving the circle, polygon, or altitude limit | `FENCE_ENABLE`, `FENCE_TYPE`, `FENCE_ACTION`, `FENCE_ALT_MAX`, `FENCE_RADIUS`, `FENCE_MARGIN` | 0 Report Only, 1 RTL or Land, 2 Always Land, 3 SmartRTL or RTL or Land, 4 Brake or Land, 5 SmartRTL or Land |
| Options | what to do instead of the default action | `FS_OPTIONS` (bitmask) | continue if in Auto on RC failsafe (bit 0), continue if in Auto on GCS failsafe (bit 1), continue if in Guided on RC failsafe (bit 2), continue if landing (bit 3), continue if in pilot controlled modes on GCS failsafe (bit 4) |

Then there are the **pre-arm checks** (`ARMING_SKIPCHK` is a bitmask of checks to **skip**, 0 means all enabled; before 4.7 it was `ARMING_CHECK`, a mask of enabled checks, 1 meaning all): compass, GPS, INS, parameters, voltage, geofence. Disable them one at a time and only when you understand why. The table of bits and of seventeen common `PreArm:` messages with cause and fix is in `ap-setup-scratch` ("Why it won't arm").

ArduPlane is built differently: RC loss is caught by `THR_FAILSAFE` with the `THR_FS_VALUE` threshold, and the action is split into a short one (`FS_SHORT_ACTN`) and a long one (`FS_LONG_ACTN` after `FS_LONG_TIMEOUT`); the action table and the timeline are in `ap-setup-plane` ("Fixed-wing failsafe"). The rest of this module is Copter only.

### How they interact
- Priority: a **critical battery** overrides everything (Land); a low battery during an RTL caused by radio loss takes the battery action (usually also RTL, but it can be Land; choose it deliberately).
- RTL requires position: on an EKF failsafe the action degrades to Land or AltHold.
- RTL first climbs to `RTL_ALT_M` (meters; before 4.7 it was `RTL_ALT` in centimeters; the minimum altitude above home for the return, 15 m by default; if the vehicle is already higher, it returns at its current altitude). Near home the climb is limited by the `RTL_CONE_SLOPE` cone (default 3): h_ret = min(max(`RTL_ALT_M`, h), max(3·d, h)), where d is the distance to home, so directly above home there is no climb (worked through in `ap-sitl`). It then flies home, loiters for `RTL_LOIT_TIME`, and lands (`RTL_ALT_FINAL_M = 0`; before 4.7, `RTL_ALT_FINAL` in cm). Over obstacles higher than RTL_ALT_M that means a collision; the altitude fence is one more limiter.
- SmartRTL returns along the path already flown (a point memory, `SRTL_POINTS`). It is good in forest and between buildings, but the memory must not fill up.
- Geofence: a breach triggers the action; `FENCE_MARGIN` is the distance the automatic modes keep from the fence (a warning on entering it needs `FENCE_OPTIONS` bit 2); the pre-arm check does not let you arm outside the fence.
- The `FS_OPTIONS` "continue if in Auto on RC failsafe" bit is for BVLOS missions flown under an authorization; without one, leave it off.

### Geofence: types, enabling, polygons
`FENCE_TYPE` is a bitmask, 7 by default: bit 0 (1) is the max altitude `FENCE_ALT_MAX` (100 m), bit 1 (2) is the circle `FENCE_RADIUS` centered on home (300 m, 30–10000), bit 2 (4) is the inclusion/exclusion circles and polygons uploaded from the ground station, bit 3 (8) is the min altitude `FENCE_ALT_MIN` (default −10 m, range −100…100). The floor is not in the default, and even when configured it is enabled only once the vehicle has climbed above `FENCE_ALT_MIN`; otherwise you could not take off.

There are three ways to enable it; choose one:
- `FENCE_ENABLE = 1`: the fence is enabled from boot, including on the ground before arming;
- `FENCE_AUTOENABLE = 3` (AutoEnableOnlyWhenArmed): it is enabled on arming and disabled on disarming; for a copter this is the practical value. In ArduCopter 4.7.2, values 1 and 2 take effect only after a takeoff commanded in Guided (`mode_guided.cpp`, `auto_enable_fence_after_takeoff`), and never after a manual takeoff;
- a switch with `RCx_OPTION = 11` (Fence): enabling in the air, not persisted (`ap-aux-tune`).

Polygons are not entered as parameters: you draw them in Mission Planner on the Plan screen as "Fence Inclusion" (fly only inside) or "Fence Exclusion" (do not fly inside), then Upload; in QGC, use the Fence tab of the Plan view. The firmware maintains `FENCE_TOTAL` itself; do not update it manually. By default, several inclusion areas are intersected; bit 1 of `FENCE_OPTIONS` allows their union instead. Arming condition: with the circle or a polygon enabled you need a position estimate. Without one you get `PreArm: Fence requires position` (the fence's own check, `AC_Fence.cpp`; this also applies with `FENCE_AUTOENABLE = 3`), and with `FENCE_ENABLE = 1` in a mode that does not need GPS you also get `PreArm: Fence enabled, need position estimate` (`AP_Arming_Copter.cpp`).

Selection rule: `FENCE_ALT_MAX` goes below the permitted altitude by the braking margin; `FENCE_RADIUS` is less than the distance the vehicle can fly home on the battery left after `BATT_LOW_MAH`; `FENCE_MARGIN` (2 m, 1–10) is the distance the automatic modes keep from the fence. Test: in SITL approach the boundary in Loiter at 3 m/s; you get a switch to RTL at the boundary, a message in Messages, and an `ERR` for the fence subsystem in the log.

### Rally points and SmartRTL
A rally point is an alternate return location. If points are loaded on the vehicle (`RALLY_TOTAL` > 0), RTL does not necessarily fly home (`AP_Rally.cpp`): it takes the closest point; if every point is farther than `RALLY_LIMIT_KM` (default 0.3 km; 0 means no limit), it returns home; with `RALLY_INCL_HOME = 1` (the default) home is also a candidate, and whichever is closer is chosen. A copter lands at the chosen point. You place points in Mission Planner on the Plan screen (right-click → Rally Points → Set Rally Point, then upload them to the vehicle), and in QGC on the Rally tab. Rule: a leftover point from a different field is dangerous, so do not set `RALLY_LIMIT_KM` to zero, and clear the list after you move sites.

SmartRTL records the path as points: a new point is added when the vehicle has moved more than `SRTL_ACCURACY` (default 2 m, 0–10), up to `SRTL_POINTS` (300, 0–500; 0 disables the mode; 100 points take about 3 kB of RAM). The path is simplified periodically, but if there is no room for longer than the timeout you get `SmartRTL deactivated: buffer full`, and with a bad position `SmartRTL deactivated: bad position`; after that the "SmartRTL or RTL" actions perform RTL. The fix for a long, winding route is `SRTL_POINTS` 500 or `SRTL_ACCURACY` 3–5 m; the check: a `SmartRTL Low on space!` message in the flight log means there is no margin.

### Dead reckoning: the defaults
With the 4.7.2 defaults (`FS_DR_ENABLE = 2`, `FS_DR_TIMEOUT = 30`), when GPS is lost in Loiter or Auto the copter switches to RTL immediately and flies on dead reckoning for up to 30 s, then the EKF failsafe triggers (`FS_EKF_ACTION = 1`, Land). Dead reckoning on wind relies on a drag model: on a copter without an airspeed sensor the wind estimate comes only from `EK3_DRAG_BCOEF_X/Y` and `EK3_DRAG_MCOEF`, and those default to 0 (as the descriptions of those parameters say). So 30 s of dead reckoning on an unconfigured vehicle is 30 s of drifting with the wind; test it with `SIM_GPS1_ENABLE = 0` in SITL at a `SIM_WIND_SPD` of 5 m/s and record the deviation from the path in the test log.

### Flight FMEA
An FMEA (Failure Mode and Effects Analysis) is a table: **failure → effect → how to detect it → severity (1–5) → probability (1–5) → detectability (1–5) → RPN = S·P·D → mitigation → test**. Mitigations: redundancy (see the redundancy module), a failsafe action, a procedure (checklist), a limit (geofence, altitude), pilot training.

The scales and the threshold of this module (a course convention, not a standard): S runs from 1 "no consequences" to 5 "loss of the vehicle or harm to people"; P from 1 "practically never happens" to 5 "happens on almost every flight"; D from 1 "it reveals itself before any harm (pre-arm check, failsafe)" to 5 "undetectable before harm". RPN lies within 1–125. A mitigation is mandatory if RPN ≥ 27 (that is, 3·3·3, "medium" on all three scales) **or** S = 5 at any RPN. RPN sets the order in which to close risks and is not an absolute measure (`eng-systems` uses the same formula on 1–10 scales); after a mitigation you recalculate RPN, and it must drop through P or D.

A minimum list of failures for a copter: RC loss; GCS loss; low battery; GPS degradation; compass fault; motor or ESC failure; BEC failure or FC reboot; vibration and clipping; a parameter error after an update; wind above the design value; video loss (FPV); pilot error (wrong mode); collision with an obstacle in RTL; SmartRTL overflow; rangefinder failure during terrain following.

### What you can and should test in SITL
Everything listed except the mechanics: SITL supports `SIM_RC_FAIL` (RC loss), GCS disconnection (just close it), `SIM_BATT_VOLTAGE` (voltage), `SIM_GPS1_ENABLE`, `SIM_MAG1_OFS_*`, `SIM_ENGINE_FAIL`, `SIM_WIND_SPD/DIR`, and the geofence (set up as on the real vehicle). Every test gets a log and a record: trigger, reaction time, action, outcome.

### Lua as the last line of defense
A script can watch conditions that the standard failsafes do not cover (ESC temperature, disagreement between two GPS units, a mission timer) and act (`vehicle:set_mode`, a message, DO_LAND). It is an addition, not a replacement: the script itself can crash, hence `SCR_HEAP_SIZE`, error handling, and a test in SITL.

{{diagram:failsafe-map|ArduCopter failsafe map: event → parameter → typical action.}}

### Place in the system

- **Receives:** EKF variances (`ap-ekf`); voltage and remaining capacity from the battery monitor calibrated in `ap-setup-scratch`; receiver frames (`link-elrs`); the ground station heartbeat.
- **Provides:** the action (RTL, Land, SmartRTL) to the flight modes; the FMEA table and the test log to systems engineering (`eng-systems`); failure scenarios to `ap-sitl`; redundancy measures to `el-redundancy`.
- **If you get it wrong here:** an RTL action with unreliable navigation → RTL requires position → on an EKF failsafe it degrades to Land or AltHold wherever the vehicle happens to be (`ap-ekf`). `RTL_ALT_M` below the obstacles on the route → the failsafe triggered "correctly" and the return ended in a collision; heights above terrain are covered in `nav-terrain`.

## practice
### Step 1. Configure
Write out every parameter from the table for your vehicle with a justification: why RTL and not Land; why `BATT_LOW_VOLT` has this value (sag under load plus a margin for an RTL from the fence distance); `RTL_ALT_M` (m; in SITL 4.6.3 it is `RTL_ALT`, cm) above the obstacles of the site; fence radius and altitude per the rules; `FS_OPTIONS`: do not set bits 0–2 (continue in Auto or Guided on link loss) without a BVLOS authorization, and keep bit 4 from the default value of 16, otherwise with `FS_GCS_ENABLE` enabled a telemetry dropout sends a copter you are flying manually into RTL.

### Step 2. FMEA
A table of ≥ 10 failures on the template with RPN; for every row with RPN ≥ 27 or S = 5, a mitigation and the RPN after it. File it in the engineering folder.

### Step 3. SITL tests
For every failsafe: scenario → expected → observed → log. Mandatory: RC loss in Loiter and in Auto; GCS loss in Guided; low battery during RTL; EKF failsafe on GPS loss; geofence by altitude and by radius; motor failure on a hexa or an X8 (if that is your platform).

### Step 4. Field test
Only after SITL: RC failsafe on the ground with the props off (switch off the transmitter → motors disarm or a message appears), then at 5 m over a clear area an RC failsafe with a spotter; for the geofence, approach the boundary at low speed. Self-check: the lab is done when the FMEA has at least 10 failures, each with S, P, and D within 1–5 and RPN = S·P·D (from 1 to 125), every failure with RPN ≥ 27 or S = 5 has a mitigation and the RPN recalculated after it (lower than the original through P or D), every mandatory scenario of step 3 has all four columns filled in the SITL test log (scenario → expected → observed → log) with the observed result matching the expected one, and the geofence has been tested both by altitude and by radius.

**Automatic log check:** `python3 examples/sitl-pymavlink/check_lab_log.py <log.bin> --lab failsafe` (from the course repository) prints PASS/FAIL against the criteria: a failsafe triggered (`ERR` Subsys 5), the mode changed to RTL/LAND, and the reaction took ≤ 5 s. Put the output in the test log.

**Reference for the self-check.** A correct run: the log has `ERR` Subsys 5 and the mode changed to RTL or LAND within 5 s, so the checker prints PASS. Typical wrong results: (1) nothing happens when you switch off the transmitter, because the receiver holds the last values or `FS_THR_ENABLE = 0`; (2) the low battery failsafe triggers right after takeoff, because the threshold was chosen without allowing for sag under load; (3) on RC loss in Auto the vehicle went to RTL in the middle of the mission, which is not an error: bit 0 of `FS_OPTIONS` is not set, as it should be without a BVLOS authorization.

## diagnostics
- **Symptom:** nothing happens when you switch off the transmitter
  - Possible cause: the receiver holds the last values (no "no pulses" or failsafe setting in the receiver), `FS_THR_ENABLE = 0`.
  - What to do: set the receiver to "no pulses" or to a failsafe throttle value below `FS_THR_VALUE`; enable the failsafe.
- **Symptom:** RTL flew into a tree
  - Possible cause: `RTL_ALT_M` is below the obstacles.
  - What to do: set RTL_ALT_M from the tallest obstacle plus a margin; make the altitude fence consistent with it.
- **Symptom:** the low battery failsafe triggered right after takeoff
  - Possible cause: the threshold ignores sag; `BATT_LOW_TIMER` is too short.
  - What to do: a threshold based on voltage under load, a 10 s timer, or a mAh threshold.
- **Symptom:** in Auto, on RC loss, the vehicle went to RTL in the middle of the mission
  - Possible cause: `FS_OPTIONS` bit 0 is not set, which is expected and correct without an authorization.
  - What to do: leave it; with an authorized BVLOS operation, enable it deliberately.
- **Symptom:** it will not arm, with `PreArm: Fence requires position` or `PreArm: Fence enabled, need position estimate`
  - Possible cause: the circle or polygon fence is enabled (`FENCE_TYPE` bit 1 or 2) and the GPS has no fix.
  - What to do: wait for a fix, or fly with the fence only when you have GPS.

## references
- ArduPilot — Failsafe (landing page) | https://ardupilot.org/copter/docs/failsafe-landing-page.html | primary | A
- ArduPilot — Radio Failsafe | https://ardupilot.org/copter/docs/radio-failsafe.html | primary | A
- ArduPilot — Battery Failsafe | https://ardupilot.org/copter/docs/failsafe-battery.html | primary | A
- ArduPilot — Geofence (Cylindrical/Polygon/Altitude) | https://ardupilot.org/copter/docs/common-ac2_simple_geofence.html | primary | A

## checklist
- I know all the ArduCopter failsafes, their parameters, and their actions
- I understand the priorities and interactions (battery > radio, EKF degrades RTL)
- An FMEA of ≥ 10 failures with RPN and mitigations is in the engineering folder
- Every failsafe is tested in SITL with a log
- The geofence and RTL_ALT_M are consistent with the site and the rules
