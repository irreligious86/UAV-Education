---
id: ap-vtol-anatomy
title: "Inside a QuadPlane: where the plane is and where the copter is"
level: L2
readingTime: 50 min
firmware: ArduPlane 4.7 (checked against 4.7.3; the lab was captured on SITL 4.7.2)
status: published
added: 2026-11-23
tags:
  - QuadPlane
  - VTOL
  - ArduPlane
  - parameters
  - tuning
related:
  - ap-setup-plane
  - ap-plane-tuning
  - ap-tuning
  - ap-quadplane
  - ap-vtol-modes
  - ap-outputs
  - px4-setup-vtol
  - inav-mixer-vtol
next:
  - ap-quadplane
source: content/ardupilot/ap-vtol-anatomy.md
source_hash: b2eaa56a0f74
---

## summary
A QuadPlane is not "a copter bolted onto a plane". It is the single ArduPlane firmware, which creates a second set of controllers from the ArduCopter libraries when `Q_ENABLE = 1`. What confuses a newcomer is not the complexity but the addresses: an "it oscillates" symptom can live in `Q_A_RAT_*`, in `RLL_RATE_*`, or in the transition, and each of those three fixes is useless or dangerous when applied to the wrong half. This module splits the aircraft into the plane half, the copter half, and what only a VTOL has: a large table of subsystems, a map of parameter prefixes with the parameter counts in 4.7.2 and where to find them in Mission Planner and QGC, the "hidden until enabled" rule, the tuning order, and above all a table and a tree for "which side do I tune this symptom from". The practice uses ArduPlane 4.7.2 SITL (the `quadplane` model) and the source: what the firmware assigns to the outputs by itself after `Q_ENABLE`, sorting eight symptoms by side, and finding errors in a parameter file.

## theory
### One firmware, two sets of controllers
A QuadPlane exists only in ArduPlane: there is no separate "VTOL firmware". While `Q_ENABLE = 0` it is the ordinary plane from `ap-setup-plane`. With `Q_ENABLE = 1` the `QuadPlane::setup()` function (`ArduPlane/quadplane.cpp`) creates the copter objects in memory once, and they are the same classes that run in ArduCopter:

| Object in ArduPlane | Prefix in Plane | The same in ArduCopter 4.7 | What it does |
|---|---|---|---|
| `AP_MotorsMulticopter` | `Q_M_` (25 parameters) | `MOT_` (24) | the lift motor mixer, the thrust curve, hover throttle |
| `AC_AttitudeControl_TS` (derived from `AC_AttitudeControl_Multi`) | `Q_A_` (61) | `ATC_` (61) | hover angles and rates |
| `AC_PosControl` | `Q_P_` (32) | `PSC_` (32) | hover position and altitude |
| `AC_WPNav` | `Q_WP_` (10) | `WP_` (12) | waypoints in a VTOL mode |
| `AC_Loiter` | `Q_LOIT_` (7) | `LOIT_` (7) | position hold in QLOITER |
| `AC_WeatherVane` | `Q_WVANE_` (9) | `WVANE_` | turning the nose into the wind |
| `QAutoTune` | `Q_AUTOTUNE_` (4) | `AUTOTUNE_` | hover autotune |

The numbers are how many parameters have that prefix in the ArduPlane 4.7.2 definitions and in ArduCopter 4.7.2 SITL (the count is step 2 of the practice; the ArduCopter definitions themselves list a few more, `MOT_` 25 and `ATC_` 66, because of helicopter and other frame-specific entries). The matches 61 = 61 and 32 = 32 are no accident: it is the same code with a `Q_` prefix. So everything you know about copter tuning from `ap-tuning` carries over to QuadPlane hover one to one, allowing for the names.

The plane half does not go anywhere: `RLL_RATE_*`, `PTCH_RATE_*`, `RLL2SRV_*`/`PTCH2SRV_*` (the fixed-wing angle and rate loops), `TECS_*` (height and speed through throttle and pitch), `NAVL1_*` (track; ArduPlane 4.7 has only L1, and NPFG belongs to PX4), `AIRSPEED_*`, and `ARSPD_*`. Shared by both halves: state estimation (AHRS and EKF), GPS, the barometer, the battery monitor, the receiver, `SERVOn_FUNCTION`, the mission, logging, and the failsafe framework.

Who is in control at any moment is decided by the mode (`QuadPlane::update()`):

- **Q modes** (QSTABILIZE, QHOVER, QLOITER, QLAND, QRTL, QACRO, QAUTOTUNE): the copter set drives the lift motors. The control surfaces are not dead: QSTABILIZE, QHOVER, QLOITER (and through it QLAND), QRTL, and QAUTOTUNE also call the fixed-wing `stabilize_roll()`/`stabilize_pitch()`, and QACRO calls the fixed-wing ACRO rate loop (`mode_q*.cpp`), so the ailerons move in hover, which is normal and not an error.
- **MANUAL, ACRO, TRAINING**: the transition is forced to "complete" and the copter set does not run: on a 4+1 the lift motors are shut down (`SHUT_DOWN`), on a tilt-rotor the tilting motors go forward and work as cruise motors on stick throttle (`Tiltrotor::continuous_update()`), and the fixed ones are stopped. The exception is a tailsitter, whose motors are the forward thrust.
- **The other fixed-wing modes** (FBWA, FBWB, CRUISE, AUTO, RTL, LOITER, GUIDED, TAKEOFF…): the plane set is in control, and the copter set comes on only in the transition and for assistance (Q-assist). The details per mode are in `ap-vtol-modes`.

The boundary between the halves is the transition. While the airspeed is low, the lift motors hold the aircraft; once the airspeed is reached, their throttle ramps linearly to zero over `Q_TRANSITION_MS` (5000 ms), and the copter throttle mix factor goes down with it.

{{diagram:vtol-anatomy-controllers|One set of sensors and one state estimate feed two sets of controllers: the Q modes drive the lift motors, the fixed-wing modes drive the surfaces and the cruise throttle, and the transition and Q-assist are the only place where both run.}}

The attitude and airspeed estimate is shared by both halves, and it matters more in the transition than anywhere else: without an airspeed sensor the end of the transition is decided by the AHRS synthetic airspeed, which is ground speed minus the wind estimate. While the lift motors are running, ArduPlane clears the "fly forward" flag (`update_fly_forward()`), EKF3 stops estimating wind, and `AP_AHRS::_airspeed_EAS()` takes the estimate from DCM using GPS: in the log `XKF2.VWN/VWE` = 0, and the wind and airspeed are in `DCM.VWN/VWE` and `DCM.SAs` (the analysis and a run are in `ap-vtol-modes`). Without GPS there is no such estimate at all, and a transition in a fixed-wing mode never completes.

{{lesson:ap-ahrs-choice|Why a QuadPlane without an airspeed sensor completes the transition on the EKF3 synthetic airspeed from GPS and wind, and what is left of that logic on DCM without GPS.}}

### The big table: plane, copter, and VTOL only
| Subsystem | On a plane (ArduPlane) | On a copter (the Q side) | VTOL only |
|---|---|---|---|
| State estimation | shared: AHRS, EKF3 or DCM | the same | without an airspeed sensor the transition waits for the AHRS synthetic airspeed from GPS (from DCM during the transition) |
| Rate loop | `RLL_RATE_*`, `PTCH_RATE_*`, `YAW_RATE_*` → surfaces | `Q_A_RAT_RLL_*`, `Q_A_RAT_PIT_*`, `Q_A_RAT_YAW_*` → motors | both run in the transition, and the fixed-wing integrators are reset until the airspeed is reached |
| Angle loop | `RLL2SRV_TCONST`, `PTCH2SRV_TCONST`, the limits `ROLL_LIMIT_DEG`, `PTCH_LIM_*_DEG` | `Q_A_ANG_RLL_P`, `Q_A_ANG_PIT_P`, `Q_A_ANGLE_MAX` (30°) | in the Q modes the stick angles are also limited by the fixed-wing limits; bit 14 of `Q_OPTIONS` uses `Q_A_ANGLE_MAX` exclusively |
| Horizontal navigation | L1: `NAVL1_PERIOD`, `NAVL1_DAMPING`, `WP_LOITER_RAD` | `Q_P_NE_*`, `Q_WP_*`, `Q_LOIT_*` | landing stages: a fixed-wing approach, then `Q_P_NE_*` to the point |
| Height and speed | TECS: `TECS_*`, `AIRSPEED_MIN/CRUISE/MAX` | `Q_P_D_*`, `Q_PILOT_SPD_UP/DN`, `Q_WP_SPD_UP/DN` | `Q_ASSIST_ALT`: assistance when the aircraft drops below the threshold |
| Throttle | `THR_MIN`, `THR_MAX`, `TRIM_THROTTLE`, the Throttle output (70) | `Q_M_THST_HOVER` (0.35), `Q_M_THST_EXPO` (0.65), `Q_M_SPIN_ARM/MIN/MAX` (0.10/0.15/0.95) | the lift motor throttle ramps to zero over `Q_TRANSITION_MS` in the transition |
| Outputs | Throttle (70), Aileron (4), Elevator (19), Rudder (21), elevons and V-tail | Motor1…Motor8 (33…40), ordered by `Q_FRAME_CLASS`/`Q_FRAME_TYPE` | tilt servos (41, 75, 76) on a tilt-rotor; on a tailsitter the motors and the forward thrust are the same thing |
| Arming | `ARMING_*`, the plane checks | checks of the motors and the `Q_A`, `Q_P` controllers | "Q_ASSIST_SPEED is not set", "quadplane needs SCHED_LOOP_RATE >= 100", "VTOL land too short", "unset one of RTL_AUTOLAND or Q_RTL_MODE" |
| Failsafe | `FS_SHORT_ACTN`, `FS_LONG_ACTN`, `BATT_FS_*` | — | in the Q modes an RC failsafe → QLAND (or QRTL/RTL with bits 5 and 20 of `Q_OPTIONS`); battery: actions 4 QLand and 6 Loiter to QLand |
| Takeoff | TAKEOFF, `TKOFF_*`, a hand launch or a runway | QHOVER/QLOITER, `NAV_VTOL_TAKEOFF` | a `NAV_TAKEOFF` in a mission is executed as a VTOL takeoff unless bit 1 of `Q_OPTIONS` is set |
| Landing | `NAV_LAND`, `LAND_*`, the flare | QLAND, `Q_LAND_FINAL_ALT` (6 m), `Q_LAND_FINAL_SPD` (0.5 m/s) | deceleration with `Q_TRANS_DECEL` (2 m/s²), the airbrake stage; a `NAV_LAND` is executed as a VTOL landing without bit 2 |
| Autotune | AUTOTUNE: `AUTOTUNE_LEVEL`, `AUTOTUNE_AXES` | QAUTOTUNE: `Q_AUTOTUNE_AXES`, `Q_AUTOTUNE_AGGR` | the transition is not tuned automatically, only by hand from a log |
| Log | `CTUN`, `TECS`, `NTUN`, `ATT`, `RCOU` | `QTUN` (25 Hz, only while the lift motors are active), `MOTB`, `RATE` | `QTUN.Trn` is the transition state, `QTUN.Ast` the assistance bits, `QPOS` the landing stage |

The "Log" row is your main sorting tool: if there are `QTUN` records at the moment in question, the copter half was running; if there are none, a pure plane was flying (`quadplane.cpp`: QTUN is logged "if motors are active, or have been active in the last quarter second").

### Parameter prefixes and where to find them
Of the 5722 parameters of ArduPlane 4.7.2, 231 with the `Q_` prefix belong to QuadPlane. Memorize the map and the Full Parameter List stops being intimidating:

| Prefix | What is inside | Side | Typical names |
|---|---|---|---|
| `Q_` with no subgroup (53, including the `Q_ASSIST_` and `Q_TRANS*` rows below) | enabling, frame, modes, transition, assistance, landing, RTL | VTOL | `Q_ENABLE`, `Q_FRAME_CLASS`, `Q_OPTIONS`, `Q_RTL_MODE`, `Q_LAND_FINAL_ALT` |
| `Q_A_` | hover angle and rate loops | copter | `Q_A_RAT_RLL_P`, `Q_A_ANG_PIT_P`, `Q_A_ANGLE_MAX` |
| `Q_P_` | hover position and altitude (in 4.7, `Q_P_NE_*` and `Q_P_D_*`) | copter | `Q_P_NE_VEL_P`, `Q_P_D_ACC_P` |
| `Q_M_` | the VTOL mixer and motors | copter | `Q_M_THST_HOVER`, `Q_M_SPIN_MIN`, `Q_M_PWM_TYPE` |
| `Q_WP_`, `Q_LOIT_`, `Q_WVANE_` | waypoints, loiter, weathervaning in hover | copter | `Q_WP_SPD_DN` (1.5 m/s), `Q_LOIT_SPEED_MS`, `Q_WVANE_GAIN` |
| `Q_TILT_` (10) | tilt-rotor motor tilt | VTOL only | `Q_TILT_ENABLE`, `Q_TILT_MAX` (45°), `Q_TILT_RATE_UP` (40 deg/s) |
| `Q_TAILSIT_` (20) | tailsitter | VTOL only | `Q_TAILSIT_ENABLE`, `Q_TAILSIT_ANGLE` (45°) |
| `Q_ASSIST_` (5) | assistance from the lift motors in fixed-wing modes | VTOL only | `Q_ASSIST_SPEED` (0 means arming is refused), `Q_ASSIST_ANGLE` (30°), `Q_ASSIST_DELAY` (0.5 s) |
| `Q_TRANS*` (5) | transitions | VTOL only | `Q_TRANSITION_MS` (5000), `Q_TRANS_DECEL` (2.0), `Q_TRANS_FAIL` (0), `Q_TRANS_FAIL_ACT` (0), `Q_TRAN_PIT_MAX` (3°) |
| `RLL_RATE_`, `PTCH_RATE_`, `RLL2SRV_`, `PTCH2SRV_` | the fixed-wing loops | plane | `RLL_RATE_P`, `PTCH2SRV_TCONST` |
| `TECS_`, `NAVL1_` | energy and track | plane | `TECS_CLMB_MAX`, `NAVL1_PERIOD` |
| `AIRSPEED_`, `ARSPD_` | the airspeed envelope and the sensor | plane, but the transition depends on them | `AIRSPEED_MIN`, `ARSPD_USE` |
| no prefix | throttle, limits, modes, failsafe | plane | `THR_MAX`, `ROLL_LIMIT_DEG`, `FLTMODE1`, `FS_LONG_ACTN` |

The names `AIRSPEED_MIN` and `AIRSPEED_CRUISE` apply from 4.5; in older QuadPlane guides you will meet `ARSPD_FBW_MIN` and `TRIM_ARSPD_CM`, which are the same parameters (`ap-setup-plane`).

**Where to look in the ground station.** Mission Planner has no separate "QuadPlane" screen; everything goes through parameters:

- Mission Planner (the menu paths follow the Mission Planner documentation and were **not opened** in this check): Config → Full Parameter List has a search box: type `Q_A_RAT` and you get hover only, `RLL_RATE` and you get the wing only. Config → Full Parameter Tree shows the same parameters as a tree by prefix (`Q` → `A`, `M`, `P`…). Setup → Mandatory Hardware → Servo Output shows `SERVOn_FUNCTION` for all outputs at once: the lift motors appear as Motor1…Motor8.
- QGroundControl: Vehicle Setup → Parameters, with the search box at the top and the groups on the left. QGC does not split fixed-wing and hover tuning into separate screens for ArduPlane (as of November 2026, **not verified** in every QGC build), so use the prefix search.
- Any station: test the lift motors with Motor Test (`MAV_CMD_DO_MOTOR_TEST`, which QuadPlane handles in ArduPlane) with the propellers off.

### The "hidden until enabled" rule
`Q_ENABLE`, `Q_TILT_ENABLE`, `Q_TAILSIT_ENABLE`, and `Q_WVANE_ENABLE` are declared with the `AP_PARAM_FLAG_ENABLE` flag: while the value is 0, the whole group behind them is invisible to the station and has no effect. Three rules follow:

1. After setting `Q_ENABLE = 1`, reboot the flight controller and refresh the parameter list (Refresh Params). The ArduPilot documentation speaks of a refresh; the default output functions, per the documentation, are assigned "on boot". The copter objects are created once (`initialised`), so `Q_FRAME_CLASS` and `Q_FRAME_TYPE` take effect only after a reboot.
2. The same applies after `Q_TILT_ENABLE = 1` or `Q_TAILSIT_ENABLE = 1`. Without a reboot arming fails with "tiltrotor setup not complete, reboot" or "tailsitter setup not complete, reboot"; with both at once, "set TAILSIT_ENABLE 0 or TILT_ENABLE 0".
3. Load a parameter file with `Q_*` only **after** enabling and rebooting, otherwise the station does not find those names and silently skips them.

**The first-enable trap.** With `Q_FRAME_CLASS = 1` (Quad, the default) `setup()` assigns Motor1…Motor4 to outputs 5…8, but only where `SERVOn_FUNCTION = 0` and only if that function is not yet on any output (`SRV_Channels::set_aux_channel_default()`). If output 5 has a servo whose function was never set, after the reboot the servo receives a motor signal. It is the same class of error as in the HeeWing case in `ap-quadplane`: the "output → device" map comes first, then `Q_ENABLE`.

### Frame: class and type
`Q_FRAME_CLASS` (default 1): 1 Quad, 2 Hexa, 3 Octa, 4 OctaQuad, 5 Y6, 7 Tri (tilt tricopter), 10 Single/Dual (tailsitter), 14 Deca, 15 and 17 a matrix from Lua. The value 12, DodecaHexa, is in the parameter's value list, but `QuadPlane::setup()` in 4.7.2 does not support it: you get the configuration error "Unsupported Q_FRAME_CLASS 12". `Q_FRAME_TYPE` (default 1): 0 Plus, 1 X, 2 V, 3 H, 4 V-Tail, 5 A-Tail, 10–11 Y6, 12 BetaFlightX, 13 DJIX, 14 ClockwiseX, 15 I, 16–17 NYT, 18 BetaFlightXReversed, 19 Y4. The meaning is the same as for a copter's `FRAME_CLASS`/`FRAME_TYPE`: motor order and rotation. A 4+1 is a Quad X plus a separate cruise motor on the Throttle output (70); a tilt-rotor adds `Q_TILT_*`, a tailsitter adds `Q_TAILSIT_*`. Choosing the layout is covered in `ap-quadplane`.

### What is tuned like a copter and what like a plane
The two halves are tuned with different tools and in different modes:

| What | Tool | The mode you tune in | What changes | Details |
|---|---|---|---|---|
| motor noise filter | the harmonic notch, `INS_HNTCH_*` | QHOVER, a hover | the gyro filter, shared by both halves | `ap-tuning` |
| hover rate loop | QAUTOTUNE or manual P/D | QAUTOTUNE, starting from QSTABILIZE | `Q_A_RAT_*`, `Q_A_ANG_*`, `Q_A_ACC_*_MAX` | `ap-tuning` |
| hover throttle | `Q_M_HOVER_LEARN = 2` (the default) | QHOVER/QLOITER | `Q_M_THST_HOVER` | `ap-tuning` |
| hover altitude and position | manual adjustment | QHOVER, then QLOITER | `Q_P_D_*`, `Q_P_NE_*` | `ap-tuning` |
| fixed-wing rate loop | AUTOTUNE | AUTOTUNE, or FBWA with the switch | `RLL_RATE_*`, `PTCH_RATE_*`, `*_TCONST` | `ap-plane-tuning` |
| energy and track | from test flights | FBWA, then AUTO/LOITER | `TECS_*`, `NAVL1_*` | `ap-plane-tuning` |
| transition and assistance | by hand from a log (`QTUN`, `ARSP`) | FBWA ↔ QHOVER at altitude | `Q_TRANSITION_MS`, `Q_ASSIST_*`, `AIRSPEED_MIN`, `Q_TILT_RATE_*` | `ap-vtol-modes` |

**Order.** The ArduPilot VTOL tuning documentation starts with the rate P in QSTABILIZE, then altitude in QHOVER, then QLOITER, then AUTO. On top of that come the course rule "inner loop before outer loop" (`ap-plane-tuning`) and a safety rule: a Q mode is your recovery mode, so hover must be tuned **before** the first transition. The result:

1. On the bench: outputs and directions of both halves (`ap-setup-plane`, `ap-quadplane`).
2. Hover: notch → `Q_A_RAT_*` (QAUTOTUNE) → hover throttle → `Q_P_D_*` → `Q_P_NE_*`.
3. The first transition at ≥ 60 m with an airspeed margin (`ap-quadplane`, `ap-vtol-modes`).
4. The wing: AUTOTUNE → TECS → L1, taking off and landing in VTOL every time.
5. The transition and Q-assist last, when both halves are already stable.

QAUTOTUNE exists in builds with `QAUTOTUNE_ENABLED`; on boards with 1 MB of flash (F405) some features are cut, and the QuikTune Lua script is not available there, so check the mode list of your build (**not verified** for every board).

### Which side to tune this symptom from
The main question in any QuadPlane debugging is: **who was controlling the aircraft at the moment of the symptom?** The answer comes from three facts: the mode (`MODE` in the log), the airspeed relative to `AIRSPEED_MIN` and `Q_ASSIST_SPEED`, and whether `QTUN` is present (the lift motors are active). Then use the table:

| Symptom | When you see it | Who was in control | Side | What to adjust |
|---|---|---|---|---|
| fast shaking, roll oscillation in hover | a Q mode, airspeed around 0 | motors | copter | notch, `Q_A_RAT_RLL_P/D`, QAUTOTUNE |
| roll oscillation in FBWA at cruise | a fixed-wing mode, no `QTUN` | surfaces | plane | `RLL_RATE_*`, AUTOTUNE |
| altitude wanders by ±10 m in AUTO at cruise | a fixed-wing mode | fixed-wing throttle and pitch | plane | `TECS_*` |
| altitude drifts in QHOVER | a Q mode | motors | copter | `Q_M_THST_HOVER`, `Q_P_D_*` |
| it drifts away in QLOITER | a Q mode | motors | copter + estimation | `Q_P_NE_*`, the compass and the EKF |
| a roll or a nose drop at the start of the transition | FBWA right after a Q mode, airspeed below the threshold | both | VTOL | surface directions, `Q_OPTIONS` bit 0, `Q_TILT_RATE_UP`, cruise motor throttle |
| a sag after "Transition done" | airspeed around `AIRSPEED_MIN` | surfaces | VTOL + plane | `AIRSPEED_MIN` relative to V_s, `Q_TRANSITION_MS`, `Q_ASSIST_SPEED` |
| the lift motors come on at cruise | a fixed-wing mode, `QTUN.Ast` ≠ 0 | both | VTOL | `Q_ASSIST_SPEED` below the real minimum airspeed, the `ARSPD_RATIO` calibration |
| the ailerons move in hover | a Q mode | the surfaces stabilize too | — | normal: in the Q modes fixed-wing stabilization runs together with the motors |

{{diagram:vtol-symptom-side-tree|First the mode and whether QTUN is present, then the airspeed relative to the thresholds: hover is tuned like a copter, cruise without the lift motors like a plane, and anything that happened in the transition or with Q-assist active is fixed with the VTOL parameters.}}

Why so strict: fixing the "wrong" half is not merely useless. If you raise `Q_A_RAT_RLL_P` because of an oscillation at cruise, you get shaking in hover and fix nothing on the wing, because at cruise the lift motors are stopped. If you raise `RLL_RATE_P` because of shaking in hover, you spoil the wing and the shaking stays, because in hover the motors hold roll and the surfaces do almost nothing at zero airspeed.

### The cost of hover: why the copter half must work only briefly
The lift motors carry the whole weight directly; the wing carries it with the benefit of L/D. A shaft power estimate from momentum theory (actuator disk, `f-aero-props`): P_hov = (m·g)^1.5 / (FM · √(2·ρ·A)), where A = n·π·D²/4 is the total area of n propellers of diameter D and FM is the propeller figure of merit (typically 0.5–0.7 for small propellers, Leishman). Cruise: P_cr = m·g·V / ((L/D) · η_p), where η_p is the efficiency of the cruise propeller.

Worked example: m = 6 kg, four 15″ propellers (D = 0.381 m, A = 0.456 m²), FM = 0.6, ρ = 1.225 kg/m³ → P_hov = 58.86^1.5 / (0.6 · √(2 · 1.225 · 0.456)) = 427 / 0.6 = 712 W. The same aircraft at a 20 m/s cruise with L/D = 10 and η_p = 0.6 → P_cr = 6 · 9.81 · 20 / (10 · 0.6) = 196 W. Hover costs 3.6 times more (not counting motor and ESC losses). A wing with S = 0.6 m² and C_Lmax = 1.2 gives V_s = √(2·m·g / (ρ·S·C_Lmax)) = 11.6 m/s, and `AIRSPEED_MIN` ≥ 1.2 · V_s = 13.9 m/s (`aero-wing`). Two engineering conclusions follow: minutes of hover weigh three times as much as minutes of cruise in the battery calculation, and every extra Q-assist cycle (`ap-vtol-modes`) is a sudden expense at hover level.

### Newcomer traps
- **`Q_ASSIST_SPEED = 0`.** The default is 0, and arming is refused: "Q_ASSIST_SPEED is not set". Set a positive value (the documentation: 3 m/s below the minimum airspeed you will fly at, or 5 m/s below without an airspeed sensor) or −1, which gives assistance only in transitions. A value above `AIRSPEED_MIN` raises the transition completion threshold to `Q_ASSIST_SPEED` (`ap-vtol-modes`).
- **Tuning hover from MANUAL.** In MANUAL, ACRO, and TRAINING the lift motors are off, so you cannot hover there.
- **Similar names, different meanings.** `ROLL_LIMIT_DEG` limits roll in QSTABILIZE too (bit 14 of `Q_OPTIONS` turns that off), `Q_A_ANGLE_MAX` is the hover lean angle (30°), and `Q_WP_SPD` and `WP_LOITER_RAD` belong to different halves.
- **`SCHED_LOOP_RATE`.** QuadPlane requires a main loop rate of at least 100 Hz: "quadplane needs SCHED_LOOP_RATE >= 100". With `Q_ENABLE = 1` the firmware changes the default to 300 by itself (`Parameters.cpp`), so the error appears only if the value was lowered by hand or loaded from the file of an ordinary plane (whose default is 50).
- **`Q_RTL_MODE` together with `RTL_AUTOLAND`**: arming is refused with "unset one of RTL_AUTOLAND or Q_RTL_MODE".
- **A copter parameter file.** `ATC_*` and `PSC_*` from ArduCopter do not load into ArduPlane; you need the same values under the names `Q_A_*` and `Q_P_*`. Besides, the motor mixer sees a different mass and inertia, so the copter values are only a starting point.

### Place in the system

- **Receives:** the plane half with verified surfaces, `AIRSPEED_MIN`, and failsafes (`ap-setup-plane`); the hover tuning method: notch, AUTOTUNE, hover throttle (`ap-tuning`); the fixed-wing tune: AUTOTUNE, TECS, L1 (`ap-plane-tuning`); the output map (`ap-outputs`).
- **Provides:** the address of every symptom, copter side or plane side, to bring-up and the first transition (`ap-quadplane`); the boundary of "who is in control in which mode" to the analysis of modes and transitions (`ap-vtol-modes`).
- **If you get it wrong here:** a wing oscillation is treated with `Q_A_RAT_*` → hover starts shaking and the cruise does not change; you can see it in the log from the absence of `QTUN` at the moment of the oscillation (`ap-logs`). `Q_ENABLE = 1` before the output map → Motor1 lands on the free output 5 with a servo by itself, and on the ground a motor spins up with no command (`ap-quadplane`).

## practice
The practice uses ArduPlane 4.7.2 SITL (built with `./waf plane`, the `quadplane` model, default parameters from `Tools/autotest/default_params/quadplane.parm`) and the source. Everything in the code blocks below is real output; you can reproduce it with `sim_vehicle.py -v ArduPlane -f quadplane` from `ap-sitl`.

### Step 1. What the firmware assigned by itself
Start SITL and read the parameters (through MAVProxy `param show`, a ground station, or pymavlink). The output of our run:

```text
  Q_ENABLE         1
  Q_FRAME_CLASS    1
  Q_FRAME_TYPE     1
  AIRSPEED_MIN     13
  AIRSPEED_CRUISE  25
  Q_ASSIST_SPEED   18
  Q_TRANSITION_MS  5000
  ARSPD_USE        1
  SERVO3_FUNCTION  70
  SERVO5_FUNCTION  33
  SERVO6_FUNCTION  34
  SERVO7_FUNCTION  35
  SERVO8_FUNCTION  36
  Q_M_THST_HOVER   0.35
```

`quadplane.parm` does not set a single `SERVOn_FUNCTION`, yet outputs 5–8 have 33–36 (Motor1–Motor4): `setup_default_channels(4)` assigned them for the Quad frame. Output 3 is the cruise throttle (70), and it belongs to the plane half. Note for yourself which outputs of your aircraft were free (function 0) before `Q_ENABLE`: that is exactly where the motors will land.

Notice the pair `AIRSPEED_MIN = 13` and `Q_ASSIST_SPEED = 18`: in SITL assistance comes on above the minimum airspeed. That is a deliberate setting of the test aircraft, but on your aircraft it would mean that the transition completes not at 13 but at 18 m/s, which you can see in the practice of `ap-vtol-modes`.

### Step 2. The prefix map with your own hands
The script counts parameters by prefix in the official ArduPlane 4.7.2 definitions file (`plane-4.7.2.pdef.json` from firmware.ardupilot.org):

```python
import json, sys
d = json.load(open(sys.argv[1]))
names = [n for g in d.values() for n in g]
for pre in ("Q_A_", "Q_P_", "Q_M_", "Q_TILT_", "Q_TAILSIT_", "Q_ASSIST_", "RLL_RATE_", "TECS_"):
    print(pre, sum(n.startswith(pre) for n in names))
```

```text
all parameters: 5722, Q_*: 231
Q_A_          61  e.g. Q_A_ACC_P_MAX, Q_A_ACC_R_MAX, Q_A_ACC_Y_MAX
Q_P_          32  e.g. Q_P_ANGLE_MAX, Q_P_D_ACC_D, Q_P_D_ACC_D_FF
Q_M_          25  e.g. Q_M_BAT_CURR_MAX, Q_M_BAT_CURR_TC, Q_M_BAT_IDX
Q_TILT_       10  e.g. Q_TILT_ENABLE, Q_TILT_FIX_ANGLE, Q_TILT_FIX_GAIN
Q_TAILSIT_    20  e.g. Q_TAILSIT_ANGLE, Q_TAILSIT_ANG_VT, Q_TAILSIT_DSKLD
Q_ASSIST_      5  e.g. Q_ASSIST_ALT, Q_ASSIST_ANGLE, Q_ASSIST_DELAY
RLL_RATE_     13  e.g. RLL_RATE_D, RLL_RATE_D_FF, RLL_RATE_FF
TECS_         34  e.g. TECS_APPR_SMAX, TECS_CLMB_MAX, TECS_FLARE_HGT
```

(The output is from the full version of the script, with example names; the short version prints the same numbers.) In ArduCopter 4.7.2 SITL there are 61 `ATC_` parameters, 32 `PSC_`, and 24 `MOT_`: the same library. If your station shows noticeably fewer `Q_*` parameters than 231, the list was not refreshed after `Q_ENABLE`, or `Q_TILT_ENABLE`/`Q_TAILSIT_ENABLE` are off (their groups are then hidden: with `Q_TILT_ENABLE = 0` the only `Q_TILT_` parameter you see is `Q_TILT_ENABLE` itself).

### Step 3. Eight symptoms by side
For each symptom, decide from the "Which side to tune from" table which side it is and which parameter comes first:

1. A hover in QLOITER, frequent pitch shaking, throttle jerking in `QTUN`.
2. FBWA, 25 m/s, lift motors at minimum, a slow roll oscillation with a period of ~2 s.
3. Right after "Transition done" the aircraft loses 8 m, and the airspeed falls to 12 m/s with a V_s of 11 m/s.
4. CRUISE with zero throttle, the lift motors come on every few seconds, and the log shows `QTUN.Ast = 5`.
5. QHOVER, the stick centered, the aircraft slowly descends.
6. AUTO, a straight leg at cruise, the altitude oscillates by ±12 m with a period of 15 s.
7. In hover the ailerons deflect in a gust.
8. At the start of the transition from QHOVER to FBWA the aircraft rolls by 20°, although the cruise motors are fine.

### Step 4. Three errors in a parameter file
A fragment of the file of a 4+1 aircraft after "carrying the settings over from a copter":

```text
Q_ENABLE,1
Q_FRAME_CLASS,1
ATC_RAT_RLL_P,0.12
Q_ASSIST_SPEED,0
SERVO5_FUNCTION,4
RTL_AUTOLAND,1
Q_RTL_MODE,1
SCHED_LOOP_RATE,300
```

Find the three entries that will keep the aircraft from arming or make it dangerous on the bench, and the one that will simply not be applied.

### Moving to real hardware
On a real aircraft the steps are the same, but with the rule "propellers off until the step that needs them" (`f-safety`):

1. The "output → device" map is built before `Q_ENABLE` (the protocol in `ap-quadplane`). Write down which outputs have function 0.
2. `Q_ENABLE = 1`, reboot, Refresh Params. Check Servo Output: Motor1…Motor4 are where you expected, and those outputs physically have ESCs, not servos.
3. Motor Test with the props off: the order and rotation of every lift motor per the `Q_FRAME_CLASS`/`Q_FRAME_TYPE` frame diagram.
4. In QSTABILIZE on the bench, tilt the aircraft by hand: the motors on the side that went down speed up, and the surfaces oppose the tilt as well. In MANUAL the lift motors of a 4+1 do not spin at all, and on a tilt-rotor the tilting motors point forward.
5. Only after that, props on and a short hover in QSTABILIZE at 1–2 m.

Criteria for hardware: every output with a Motor1…Motor8 function is connected to an ESC; Motor Test spins the motors in the frame order; in MANUAL with the throttle raised the lift motors of a 4+1 are stopped (on a tilt-rotor they point forward); arming passes without "Q_ASSIST_SPEED is not set" and "setup not complete".

Self-check: the lab is done when (SITL and source) for step 1 you have written down outputs 5–8 with functions 33–36 and output 3 with function 70 and explained that `setup_default_channels` assigned them; for step 2 the numbers match the output above exactly (231 `Q_*`, 61 `Q_A_`, 32 `Q_P_`, 25 `Q_M_`); for step 3 all eight symptoms are assigned to a side as in the reference below; for step 4 exactly three errors and one inapplicable line are found. For hardware, use the criteria in the subsection above.

**Reference for the self-check.** Step 3: 1 is copter (notch, `Q_A_RAT_PIT_*`); 2 is plane (`RLL_RATE_*`, AUTOTUNE); 3 is VTOL + plane (`AIRSPEED_MIN` ≥ 1.2 V_s = 13.2 m/s and no lower; complete the transition with a margin); 4 is VTOL: bits 0 and 2 = speed assistance, with `Q_ASSIST_SPEED` above the airspeed CRUISE holds at zero throttle (`AIRSPEED_MIN`); 5 is copter (`Q_M_THST_HOVER`, `Q_P_D_*`); 6 is plane (`TECS_*`); 7 is normal; 8 is VTOL (surface and tilt directions, bit 0 of `Q_OPTIONS`). Step 4: the errors are `Q_ASSIST_SPEED,0` (arming: "Q_ASSIST_SPEED is not set"), the pair `RTL_AUTOLAND,1` + `Q_RTL_MODE,1` (arming: "unset one of RTL_AUTOLAND or Q_RTL_MODE"), and `SERVO5_FUNCTION,4`: output 5 has an aileron, so `set_aux_channel_default()` does not put Motor1 there, and arming fails with "Motors: no SERVOx_FUNCTION set to Motor1"; the inapplicable line is `ATC_RAT_RLL_P` (ArduPlane has no such parameter; you need `Q_A_RAT_RLL_P`). Typical wrong answers: (1) symptom 2 is assigned to the copter "because it is a QuadPlane": at cruise the lift motors are stopped and there is no `QTUN`; (2) symptom 7 is "fixed" by reversing the surfaces: it is the normal fixed-wing stabilization in a Q mode; (3) `SCHED_LOOP_RATE,300` is taken for an error: 300 ≥ 100, and it is the SITL value.

## diagnostics
- **Symptom:** after `Q_ENABLE = 1` the station shows no `Q_A_*` parameters at all
  - Possible cause: the parameter list was not refreshed, or there was no reboot.
  - What to do: reboot the flight controller, Refresh Params; then check the number of `Q_*` parameters (up to 231 in 4.7.2 with the subgroups enabled).
- **Symptom:** after enabling QuadPlane a servo on outputs 5–8 hums, or a motor on that output spins with no command
  - Possible cause: the output function was 0, and the firmware assigned Motor1…Motor4 there.
  - What to do: remove power, build the output map, set the functions of all outputs explicitly before `Q_ENABLE` (`ap-quadplane`).
  - Consequences: a motor on a servo channel is an injury on the bench.
- **Symptom:** arming is refused with "Q_ASSIST_SPEED is not set"
  - Possible cause: the default value of 0.
  - What to do: 3 m/s below the minimum airspeed you fly at (5 m/s below without a sensor), or −1.
- **Symptom:** arming is refused with "tiltrotor setup not complete, reboot"
  - Possible cause: `Q_TILT_ENABLE = 1` without a reboot.
  - What to do: reboot; if both tilt and tailsitter are enabled, keep one.
- **Symptom:** a roll oscillation at cruise does not change however much you adjust `Q_A_RAT_RLL_*`
  - Possible cause: you are adjusting the copter half, and at cruise the lift motors are off.
  - In the log: there are no `QTUN` records at the moment of the oscillation.
  - What to do: restore `Q_A_RAT_*` and tune `RLL_RATE_*` with AUTOTUNE (`ap-plane-tuning`).
- **Symptom:** a loaded "copter" parameter file was only partly applied
  - Possible cause: the names `ATC_*`, `PSC_*`, `MOT_*` do not exist in ArduPlane.
  - What to do: rename them to `Q_A_*`, `Q_P_*`, `Q_M_*` and treat the values as starting points only.
- **Symptom:** in QSTABILIZE you cannot roll the aircraft more than 45° although `Q_A_ANGLE_MAX` is larger
  - Possible cause: in the Q modes the stick is also limited by the fixed-wing limits `ROLL_LIMIT_DEG` and `PTCH_LIM_*_DEG`.
  - What to do: bit 14 of `Q_OPTIONS` uses `Q_A_ANGLE_MAX` exclusively, if you really need that.

## checklist
- The outputs with function 0 are known before `Q_ENABLE`; after enabling, Motor1…Motor8 are on ESCs only
- After `Q_ENABLE`, `Q_FRAME_*`, `Q_TILT_ENABLE`, `Q_TAILSIT_ENABLE`: a reboot and Refresh Params
- `Q_ASSIST_SPEED` is set (not 0) and is not above `AIRSPEED_MIN` without a reason
- For every symptom you first determine: the mode, the airspeed relative to the thresholds, whether `QTUN` is present
- Hover is tuned before the first transition; the wing (AUTOTUNE, TECS, L1) after it
- Copter parameters are carried over under the names `Q_A_*`, `Q_P_*`, `Q_M_*`

## references
- ArduPilot Copter-4.7.2 (Plane 4.7.2) — ArduPlane/quadplane.cpp: setup(), update(), the Q_* parameters | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/ArduPlane/quadplane.cpp | primary | A
- ArduPilot 4.7.2 — ArduPlane/AP_Arming_Plane.cpp: quadplane_checks() | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/ArduPlane/AP_Arming_Plane.cpp | primary | A
- ArduPilot 4.7.2 — ArduPlane/mode_qstabilize.cpp (fixed-wing stabilization in a Q mode) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/ArduPlane/mode_qstabilize.cpp | primary | A
- ArduPilot 4.7.2 — libraries/SRV_Channel/SRV_Channel_aux.cpp: set_aux_channel_default() | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/SRV_Channel/SRV_Channel_aux.cpp | primary | A
- ArduPlane 4.7.2 parameter definitions (apm.pdef.json) | https://firmware.ardupilot.org/Plane/stable-4.7.2/ | primary | A
- QuadPlane Parameters — ArduPilot Plane docs (Q_ENABLE and refresh) | https://ardupilot.org/plane/docs/quadplane-parameters.html | primary | A
- QuadPlane Frame Setup — ArduPilot Plane docs (motors on outputs 5–8) | https://ardupilot.org/plane/docs/quadplane-frame-setup.html | primary | A
- QuadPlane VTOL Tuning — ArduPilot Plane docs (order: QSTABILIZE → QHOVER → QLOITER → AUTO) | https://ardupilot.org/plane/docs/quadplane-vtol-tuning.html | primary | A
