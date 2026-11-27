---
id: ap-vtol-modes
title: "VTOL modes and transitions in ArduPilot"
level: L3
readingTime: 60 min
firmware: ArduPlane 4.7 (checked against 4.7.3; the lab was captured on SITL 4.7.2)
status: published
added: 2026-11-23
tags:
  - QuadPlane
  - VTOL
  - modes
  - transition
  - Q-assist
  - failsafe
related:
  - ap-vtol-anatomy
  - ap-quadplane
  - ap-setup-plane
  - ap-missions
  - ap-safety-fs
  - aero-wing
  - px4-setup-vtol
  - inav-mixer-vtol
next:
  - ap-tuning
source: content/ardupilot/ap-vtol-modes.md
source_hash: 74070508296e
---

## summary
A QuadPlane has two sets of modes: the Q modes, in which the vehicle is a copter, and the fixed-wing modes, in which it is a plane that the VTOL motors help at low speed. Everything dangerous happens at the boundary, in the transitions, in Q-assist and in the stages of a VTOL landing, and the firmware does almost all of it by itself, on thresholds that you set. Working from the ArduPlane 4.7.2 source, this module goes through each Q mode and its Copter counterpart, what the VTOL motors do in each fixed-wing mode, the forward transition through the states `AIRSPEED_WAIT → TIMER → DONE`, the back transition and deceleration, every Q-assist trigger, the mission commands `NAV_VTOL_TAKEOFF`, `NAV_VTOL_LAND`, `DO_VTOL_TRANSITION` and the landing stages from the fixed-wing approach to touchdown, QRTL versus RTL, and the VTOL failsafes. The practice consists of real SITL QuadPlane 4.7.2 runs: a forward transition in 9.2 s and 159 m, cyclic Q-assist in CRUISE, a back transition into QLOITER with a 19 m climb, a mission with an airbrake stage, an airspeed sensor failure in the middle of a transition, and an RTL that changes to QRTL.

## theory
### Two groups of modes and the boundary between them
Who flies the vehicle in each mode is covered in `ap-vtol-anatomy`; one consequence matters here. On a QuadPlane, flipping the mode switch does not change the "character" of the vehicle as it does on a copter; it selects **which half is responsible for lift**. In a Q mode the VTOL motors provide it at any speed. In a fixed-wing mode the wing does, and the VTOL motors run only when the wing lacks airspeed (a transition) or when something has gone wrong (Q-assist). In MANUAL, ACRO and TRAINING the VTOL motors of a 4+1 are always off: these modes have no safety net.

The ArduPlane 4.7.2 mode numbers (`mode.h`) that you need for `FLTMODE1…6` and in the `MODE` log message: MANUAL 0, FBWA 5, FBWB 6, CRUISE 7, AUTO 10, RTL 11, LOITER 12, TAKEOFF 13, GUIDED 15, QSTABILIZE 17, QHOVER 18, QLOITER 19, QLAND 20, QRTL 21, QAUTOTUNE 22, QACRO 23, LOITER_ALT_QLAND 25.

### The Q modes and their Copter counterparts
| Q mode | ArduCopter counterpart | Throttle stick | Position | Arming in the mode | Notes |
|---|---|---|---|---|---|
| QSTABILIZE (17) | STABILIZE | direct motor throttle, curve `Q_THROTTLE_EXPO` (0.2) | no | yes | stick angles are limited by `Q_A_ANGLE_MAX` and the fixed-wing `ROLL_LIMIT_DEG`, `PTCH_LIM_*_DEG`; the takeoff mode when GPS is poor |
| QHOVER (18) | ALT_HOLD | vertical speed: up `Q_PILOT_SPD_UP` (2.5 m/s), down `Q_PILOT_SPD_DN` (0 uses the up value), acceleration `Q_PILOT_ACCEL_Z` (2.5 m/s²) | no | yes | after arming, the motors wait for throttle above 10 % (`throttle_wait`); at a tilt (roll and pitch combined) beyond twice `Q_A_ANGLE_MAX` it hands control to the fixed-wing controller for recovery |
| QLOITER (19) | LOITER | as QHOVER | yes, `Q_LOIT_*`, `Q_P_NE_*` | yes | in wind, with `Q_FWD_THR_USE` the forward motor helps hold position and the nose does not pitch down beyond `Q_FWD_PIT_LIM` (3°) |
| QLAND (20) | LAND | none (except bit 15 of `Q_OPTIONS`) | yes | no | descent at `Q_WP_SPD_DN` (1.5 m/s) down to `Q_LAND_FINAL_ALT` + 6 m, then a smooth slowdown to `Q_LAND_FINAL_SPD` (0.5 m/s) below `Q_LAND_FINAL_ALT` (6 m) |
| QRTL (21) | RTL | none | yes | no | `Q_RTL_ALT` (15 m), `Q_RTL_ALT_MIN` (10 m); far from home it flies as a plane and lands vertically |
| QAUTOTUNE (22) | AUTOTUNE | as QHOVER | per the Copter AutoTune library (**not verified** for Plane) | yes | tunes `Q_A_RAT_*`, `Q_A_ANG_*`, on the axes in `Q_AUTOTUNE_AXES`; not present in every build |
| QACRO (23) | ACRO | direct throttle | no | yes | `Q_ACRO_RLL_RATE` 360, `Q_ACRO_PIT_RATE` 180, `Q_ACRO_YAW_RATE` 90 deg/s |
| LOITER_ALT_QLAND (25) | — | none | yes | — | a fixed-wing LOITER descending to `Q_RTL_ALT`, then QLAND; battery failsafe action 6 |

Arming in QLAND and QRTL is not allowed (`_pre_arm_checks` returns false). Bit 18 of `Q_OPTIONS` allows arming only in VTOL modes (and in AUTO when the current nav command is `NAV_VTOL_TAKEOFF`): a guard against taking off in FBWA at full forward-motor throttle. In all Q modes the control surfaces work together with the motors: in QACRO through the fixed-wing ACRO rate controller (`mode_acro.run()`), in the others through `stabilize_roll()`/`stabilize_pitch()`.

### Fixed-wing modes on a VTOL: what the VTOL motors do
| Mode | VTOL motors | When they run | Trap |
|---|---|---|---|
| MANUAL, ACRO, TRAINING | 4+1: off; tiltrotor: the tilting motors point forward and work as forward motors | never | neither transition nor assistance; switching from a hover to MANUAL means a fall |
| FBWA, STABILIZE, AUTOTUNE | transition and Q-assist | airspeed below the threshold, attitude outside the limits, low altitude | a transition in FBWA near the ground with the throttle below half: no acceleration, you hang on the VTOL motors |
| FBWB, CRUISE | transition and Q-assist | the same | the throttle stick sets the airspeed: at zero it is `AIRSPEED_MIN`; if `Q_ASSIST_SPEED` is higher, assistance cycles on and off (step 2 of the practice) |
| AUTO | per the mission commands | `NAV_VTOL_*` are VTOL throughout; waypoints are fixed-wing with a transition | `NAV_TAKEOFF` and `NAV_LAND` on a QuadPlane execute as VTOL unless bits 1 and 2 of `Q_OPTIONS` are set |
| RTL | transition and Q-assist; near home, QRTL per `Q_RTL_MODE` | see the QRTL section | with `Q_RTL_MODE = 0` the plane loiters over home and does not land |
| LOITER, CIRCLE, TAKEOFF, GUIDED | transition and Q-assist | the same | `Q_GUIDED_MODE = 1` switches to VTOL flight and hovers when the GUIDED destination is reached |

Assistance in fixed-wing modes is possible at all only when starting the VTOL motors is safe: auto throttle is not suppressed, or the stick throttle is above zero, or the vehicle is flying (`VTOL_Assist::should_assist()`). On the ground with the throttle at zero they do not start by themselves.

### The forward transition step by step
A forward transition begins when you (or the mission) switch from a Q mode to a fixed-wing mode other than MANUAL, ACRO or TRAINING. The logic is `SLT_Transition::update()` in `quadplane.cpp`, with three states that are also logged as `QTUN.Trn`:

1. **AIRSPEED_WAIT (Trn = 0).** The message "Transition started airspeed X". The VTOL motors hold altitude as in a hover (`hold_hover`) while the forward motor accelerates the vehicle. For this time TECS is switched to synthetic airspeed, and the roll and pitch integrators of the fixed-wing controllers are reset every loop, since they do not decide anything yet. Bit 0 of `Q_OPTIONS` (Level Transition) stops the 4+1 VTOL motors from being used for climb and keeps the wings within `LEVEL_ROLL_LIMIT`. On a tiltrotor the motors tilt no further than `Q_TILT_MAX` (45°) in this phase, at the rate `Q_TILT_RATE_DN` (default 0, in which case `Q_TILT_RATE_UP`, 40 deg/s, is used).
2. **The change to TIMER.** The condition (verbatim from the code): `have_airspeed && aspeed > AIRSPEED_MIN && !assisted_flight`. The last term matters: while the airspeed is below `Q_ASSIST_SPEED`, Q-assist considers assistance necessary and the state cannot leave AIRSPEED_WAIT. So **the transition completes at the higher of `AIRSPEED_MIN` and `Q_ASSIST_SPEED`**, and the documentation says the same: "AIRSPEED_MIN, or Q_ASSIST_SPEED if that is higher". The message is "Transition airspeed reached X".
3. **TIMER (Trn = 1).** The VTOL motor throttle is reduced linearly from its last value to 0 (not below 1 %) over `Q_TRANSITION_MS` (5000 ms, constrained to 500…30000), and the copter throttle mix goes from 0.5 to 0. A tiltrotor finishes tilting its motors fully forward during this time. It ends when `Q_TRANSITION_MS` has elapsed **and** the tilt has been reached: "Transition done", `Trn = 2`, and the VTOL motors are shut down (`SHUT_DOWN`).

`Q_TRANSITION_MS` is neither a timeout nor "the time without an airspeed sensor": the parameter description in 4.7.2 reads "Transition time in milliseconds after minimum airspeed is reached". The transition timeout is the separate `Q_TRANS_FAIL` (s, default 0, no limit): if AIRSPEED_WAIT lasts longer, you get "Transition failed, exceeded time limit" and the mode changes per `Q_TRANS_FAIL_ACT`: 0 is QLAND (the default), 1 is QRTL, −1 is a warning only. Bit 19 of `Q_OPTIONS` completes the transition instead, but only on a tiltrotor and only with a ground speed above half of `AIRSPEED_MIN`.

**Where the airspeed comes from.** `have_airspeed` is supplied by `AP_AHRS::airspeed_EAS()`: with `ARSPD_USE = 1` and a healthy sensor it is the sensor (if `AHRS_WIND_MAX` > 0, its reading is constrained to the band "ground speed ± `AHRS_WIND_MAX`"); with no sensor it is the synthetic airspeed, "ground speed minus wind". EKF3 provides the wind for it only while the vehicle is "flying forward": during a transition and during Q-assist ArduPlane clears that flag (`Plane::update_fly_forward()`), EKF3 stops estimating wind (without `EK3_DRAG_*`), and the AHRS takes the DCM estimate based on GPS. With no GPS and no sensor there is no estimate at all, and the transition **never** leaves AIRSPEED_WAIT: the VTOL motors hold the vehicle until the battery runs out or `Q_TRANS_FAIL` triggers. Bit 12 of `Q_OPTIONS` disables speed-based Q-assist when the airspeed estimate is synthetic.

{{lesson:ap-ahrs-choice|During a transition EKF3 has to trust the airspeed sensor and its own wind estimate: work out when it rejects them and what Q_ASSIST_SPEED sees then.}}

A **tailsitter** completes the forward transition on angle, not on airspeed: pitch beyond `Q_TAILSIT_ANGLE` (45°), or roll beyond max(45°, `ROLL_LIMIT_DEG` + 5°), "Transition FW done, roll error", or on a timeout of 1.5 × (angle + initial pitch) / `Q_TAILSIT_RAT_FW`, "Transition FW done, timeout" (`tailsitter.cpp`). The default of `Q_TAILSIT_RAT_FW` in the parameter table is 50 deg/s, but if you have never set it, the firmware writes `Q_TAILSIT_ANGLE` / (`Q_TRANSITION_MS` / 2000) into it once when the tailsitter is enabled, which with the defaults is 45 / 2.5 = 18 deg/s; check the actual value in the parameter list.

**Real SITL 4.7.2 numbers** (the `quadplane` model, step 1 of the practice): FBWA at full throttle at an altitude of 62 m; airspeed 18.3 m/s after 4.2 s, "Transition done" another 5.0 s later, 9.2 s and 159 m over the ground in total; the speed at the end is 28 m/s. The acceleration up to the threshold takes about 35 m.

{{diagram:chart-vtol-forward-transition|SITL 4.7.2: the threshold that ends the acceleration is not AIRSPEED_MIN 13 m/s but Q_ASSIST_SPEED 18 m/s (4.2 s); the VTOL motors reduce throttle while still accelerating, as the wing starts to carry the load, and after the threshold the Q_TRANSITION_MS = 5 s timer takes them down to shutdown, for a total of 9.2 s and 159 m.}}

### The back transition and deceleration
**From a fixed-wing mode to a Q mode with the switch.** The VTOL motors start immediately, the forward throttle goes to zero, and the copter controller starts braking by pitching the nose up. How sharply is decided by `Q_A_ANGLE_MAX` (30°) and `Q_BACKTRANS_MS` (3000 ms): on planes with separate lift motors (SLT) and on tiltrotors, the pitch limit in position-controlled modes grows from the last fixed-wing pitch (not below 0) to min(`Q_A_ANGLE_MAX`, `PTCH_LIM_MAX_DEG`) over that time (`SLT_Transition::set_VTOL_roll_pitch_limit()`). The firmware default of `PTCH_LIM_MAX_DEG` is 20°; the SITL `quadplane.parm` has 30°. In SITL, from CRUISE at 28 m/s into QLOITER: the pitch grew to 29.5° in 3.6 s (maximum 29.7°), the vehicle stopped in 6.1 s and 91 m, and **gained 19 m of altitude**: at speed the wing keeps lifting while the nose is up. Hence the rule: do a back transition with the switch only with altitude to spare above you (airspace ceiling, cloud base) and not above cruise speed.

**In a mission and in QRTL the deceleration is planned.** Here the firmware calculates the stopping distance in advance (`QuadPlane::stopping_distance_m()`):

d_stop = V² / (2 · `Q_TRANS_DECEL`), `Q_TRANS_DECEL` = 2 m/s² by default (0.2…5).

The airbrake stage begins when d_stop + 2·V remains to the destination (a two-second allowance for motor spin-up). The SITL example: V = 19.2 m/s → 19.2² / 4 + 2 · 19.2 = 92.2 + 38.4 = 130.6 m; the log has "VTOL airbrake v=19.2 d=130 sd=130". The same `Q_TRANS_DECEL` sets the target closing speed in the next stage: V_target = √(2 · `Q_TRANS_DECEL` · d).

The arming check "VTOL land too short, min X m" fails when `NAV_VTOL_LAND` (or `NAV_LAND`) comes right after a `NAV_WAYPOINT` that is closer than 0.75 · V² / (2 · `Q_TRANS_DECEL`), where V is `TECS_LAND_ARSPD` or, if that is not set, `AIRSPEED_CRUISE`. For SITL (25 m/s, 2 m/s²) that is 117 m.

A tailsitter also does the back transition on angle: `Q_TAILSIT_ANG_VT` (0 means use `Q_TAILSIT_ANGLE`) and the rate `Q_TAILSIT_RAT_VT` (50 deg/s).

### Q-assist: when the VTOL motors step in by themselves
Q-assist (`VTOL_Assist::should_assist()`) starts the VTOL motors in a fixed-wing mode without a mode change, which is the main difference from the PX4 quad-chute (`px4-setup-vtol`). There are three triggers plus a forced one:

| Trigger | Parameter (default) | Condition in the code | Delay | Message |
|---|---|---|---|---|
| airspeed | `Q_ASSIST_SPEED` (0: arming is refused; −1: transitions only) | an airspeed estimate exists and is below the threshold | **none**, immediate | only "Transition started airspeed X" (any trigger prints it) |
| altitude | `Q_ASSIST_ALT` (0 is off), m above ground (the rangefinder, if the `RNGFND_LANDING` bitmask has bit 0 All or bit 2 Assist; terrain with `TERRAIN_FOLLOW = 1`; otherwise above home) | below the threshold | `Q_ASSIST_DELAY` (0.5 s) | "Alt assist X m" |
| angle | `Q_ASSIST_ANGLE` (30°) | roll or pitch is outside the fixed-wing limits by more than 5° **and** the attitude error is greater than `Q_ASSIST_ANGLE` | `Q_ASSIST_DELAY` | "Angle assist r=.. p=.." |
| forced | a switch with `RCx_OPTION = 82` in the high position, or bit 7 of `Q_OPTIONS` | always | — | "QAssist: Force enabled" |

All of this is disabled if `Q_ASSIST_SPEED ≤ 0` (except the forced one), if the vehicle is disarmed, if switch 82 is low ("QAssist: Disabled"), during the flare of a fixed-wing landing, and on a tailsitter with control surfaces and no vectored thrust (`Tailsitter::is_control_surface_tailsitter()`). Altitude and angle assistance is released 2 × `Q_ASSIST_DELAY` after the condition has cleared. `Q_ASSIST_OPTIONS`: bit 0 disables the forced fixed-wing controller recovery at a roll or pitch beyond 2 × `Q_A_ANGLE_MAX`, bit 1 disables spin recovery (rudder and neutral elevator with the VTOL motors running, `output_spin_recovery()`).

{{diagram:vtol-qassist-tree|Q-assist checks in turn: whether it is disabled, whether it is needed and whether starting the motors is safe, then airspeed (immediately), altitude and angle (after the Q_ASSIST_DELAY delay); any "yes" branch starts the VTOL motors without a mode change.}}

**How to choose `Q_ASSIST_SPEED`.** The documentation: 3 m/s below the minimum airspeed you fly at, and 5 m/s below it with no airspeed sensor. The minimum flight airspeed is `AIRSPEED_MIN` (≥ 1.2 V_s, `aero-wing`). So a sensible pair is `AIRSPEED_MIN` = 1.2…1.3 V_s, `Q_ASSIST_SPEED` = `AIRSPEED_MIN` − 3 m/s, but not below V_s. If the two conflict (a low V_s, for example 9 m/s → `AIRSPEED_MIN` 11, `Q_ASSIST_SPEED` 8 < V_s), take `Q_ASSIST_SPEED` ≈ V_s and raise `AIRSPEED_MIN`. It must not be set above `AIRSPEED_MIN`: FBWB and CRUISE at zero throttle hold exactly `AIRSPEED_MIN`, and assistance would switch on and off endlessly, draining the battery (step 2 of the practice).

### VTOL in a mission
| Command | ID | What it does | Important fields and bits |
|---|---|---|---|
| `NAV_VTOL_TAKEOFF` | 84 | a vertical takeoff to the altitude of the item | bit 3 of `Q_OPTIONS`: the altitude is in the frame of the command, not above the current location; `Q_TKOFF_FAIL_SCL` switches to QLAND if the takeoff takes too long; `Q_TKOFF_ARSP_LIM` switches to QLAND in strong wind |
| `NAV_TAKEOFF` | 22 | on a QuadPlane, the same as `NAV_VTOL_TAKEOFF` | bit 1 of `Q_OPTIONS` allows a fixed-wing takeoff |
| `NAV_WAYPOINT` | 16 | fixed-wing flight; if the vehicle was hovering before it, a forward transition | — |
| `DO_VTOL_TRANSITION` | 3000 | param1 = 3 (MC): fly the following waypoints as a copter; 4 (FW): as a plane | works only in AUTO: "VTOL transition only in AUTO" |
| `NAV_VTOL_LAND` | 85 | a VTOL landing at the item | param1 = 1: a fixed-wing loiter-down approach before the landing; bit 4 of `Q_OPTIONS`: always use that approach |
| `NAV_LAND` | 21 | on a QuadPlane, the same as `NAV_VTOL_LAND` | bit 2 of `Q_OPTIONS` allows a fixed-wing landing |

**The stages of a VTOL landing** are the `poscontrol` state in `quadplane.cpp`, logged as `QPOS.State` and reported in messages:

1. **APPROACH** ("VTOL approach d=…"): fixed-wing L1 navigation and TECS toward the landing point; the target airspeed is lowered smoothly from `AIRSPEED_CRUISE` (more than 60 s from the braking point) to the approach speed (less than 20 s), which is `TECS_LAND_ARSPD` or, if that is not set (−1), (`AIRSPEED_CRUISE` + `AIRSPEED_MIN`) / 2; in SITL (25 + 13) / 2 = 19 m/s (`QuadPlane::get_land_airspeed_ms()`).
2. **AIRBRAKE** ("VTOL airbrake v d sd"): from the distance d_stop + 2V the VTOL motors spin up as an airbrake and the nose does not go below the horizon; 1 s minimum. A tailsitter skips this stage.
3. **POSITION1** ("VTOL position1 …"): the copter position controller decelerates toward the point along the profile √(2·`Q_TRANS_DECEL`·d). It is entered from AIRBRAKE when the airspeed is below max(`AIRSPEED_MIN` − 2, `Q_ASSIST_SPEED`), or the closing is in the wrong direction, too fast or too slow, or the attitude error exceeds 10°. "VTOL Overshoot" means the vehicle passed the point and is coming back.
4. **POSITION2** ("VTOL position2 started"): closer than 10 m and slower than 9 m/s, precise positioning.
5. **LAND_DESCEND** ("Land descend started"): a descent at 1.5 m/s.
6. **LAND_FINAL** ("Land final started"): below `Q_LAND_FINAL_ALT` (6 m) at 0.5 m/s, then "Land complete".

Bit 16 of `Q_OPTIONS` disables the APPROACH and AIRBRAKE stages (straight to POSITION1); `Q_APPROACH_DIST`: if the destination is closer than this distance, APPROACH and AIRBRAKE are skipped, straight to POSITION1; if at the start of the landing the destination is closer than 1.5 × d_stop(`AIRSPEED_CRUISE`), the approach is skipped as well, straight to airbrake. Bit 17 lets the pilot reposition with the sticks during the descent.

**The fixed-wing approach** (param1 = 1) adds the `VTOLApproach` stages from `commands_logic.cpp` before all this: LOITER_TO_ALT, a loiter of radius `Q_FW_LND_APR_RAD` (0 means `WP_LOITER_RAD`) around the point down to its altitude → selection of an approach heading into the wind ("Selected an approach path of …") → ENSURE_RADIUS → WAIT_FOR_BREAKOUT (leaving the loiter) → APPROACH_LINE ("Starting VTOL land approach path") → the normal VTOL landing. The change to the landing happens when the vehicle passes the point d_stop short of the target on the approach line. If the loiter radius is smaller than d_stop, the vehicle joins the line already inside the stopping distance and overshoots the point; in SITL with `WP_LOITER_RAD` 60 m and 25 m/s: "VTOL airbrake v=25.6 d=62 sd=164", then "VTOL Overshoot" and 34 s of flying back. Hence a course rule (derived in this module from the code and the run; the ArduPilot documentation does not state it): `Q_FW_LND_APR_RAD` ≥ V² / (2·`Q_TRANS_DECEL`) at the speed the vehicle loiters at before the approach (the cruise 25 m/s in the run).

{{diagram:vtol-landing-stages|A VTOL landing in a mission is a chain of fixed-wing and copter stages: L1 and TECS up to the stopping distance, airbrake with the VTOL motors, then the copter position controller; the numbers are from the SITL 4.7.2 run at 19.2 m/s and Q_TRANS_DECEL = 2.}}

### QRTL versus RTL
`Q_RTL_MODE` (default 0):

| Value | What RTL does | When to choose it |
|---|---|---|
| 0 | a fixed-wing RTL: a loiter over home at `RTL_ALTITUDE`, no landing | only with `RTL_AUTOLAND` and a landing sequence in the mission |
| 1 | fixed-wing flight toward home, then QRTL once home is closer than max(`RTL_RADIUS` or `WP_LOITER_RAD`, d_stop) | the main choice for a VTOL |
| 2 | fixed-wing flight toward home, a loiter of radius `Q_FW_LND_APR_RAD` descending to `Q_RTL_ALT`, an approach into the wind, then QRTL | landing into the wind on a confined site |
| 3 | any RTL becomes QRTL at once | short flights close to home |

QRTL by itself: if the VTOL motors are already running, the vehicle first climbs in a hover along a "cone" to max(`Q_RTL_ALT` · d / max(R, d), `Q_RTL_ALT_MIN`), where R = 1.5 × max(`WP_LOITER_RAD`, `RTL_RADIUS`), and the firmware constrains `Q_RTL_ALT_MIN` to the range from `Q_LAND_FINAL_ALT` to `Q_RTL_ALT` (beyond R it climbs to the full `Q_RTL_ALT`); if home is closer than R, it returns in a hover at its current altitude (no higher than `Q_RTL_ALT`). An example: `WP_LOITER_RAD` 60 m → a radius of 90 m; at 50 m from home the target is max(15 · 50 / 90, 10) = max(8.3, 10) = 10 m. Farther out it flies as a plane, with the landing stages of the previous section. RTL goes to the nearest rally point if there is one. Arming is refused if `Q_RTL_MODE` ≠ 0 and `RTL_AUTOLAND` ≠ 0 at the same time.

In SITL with `Q_RTL_MODE = 1`, an RTL from ~700 m at 25 m/s: "MODE QRTL" and right away "VTOL airbrake v=25.2 d=158 sd=158"; the switch happened at the stopping distance 25.2² / 4 = 158.8 m, because that is greater than the 60 m radius; touchdown after 40 s, "Land complete" after 46 s, 0.0 m from home.

### VTOL failsafes
| Event | Mode at the time of the event | What ArduPlane 4.7.2 does |
|---|---|---|
| RC loss (short and long) | QSTABILIZE, QHOVER, QLOITER, QACRO, QAUTOTUNE | QLAND; bit 5 of `Q_OPTIONS`: QRTL; bit 20: RTL (overrides bit 5) |
| RC loss | QLAND, QRTL, LOITER_ALT_QLAND | no change |
| RC loss, long | AUTO on `NAV_VTOL_TAKEOFF` | QLAND |
| RC loss | AUTO in a landing stage (VTOL included) | no change (`failsafe_in_landing_sequence()`) |
| RC loss | FBWA, FBWB, CRUISE (including mid-transition) | per the `FS_SHORT_ACTN`/`FS_LONG_ACTN` tables from `ap-setup-plane`: CIRCLE, then RTL; the VTOL motors help through Q-assist |
| battery | any | `BATT_FS_*_ACT`: 4 is QLAND, 6 is LOITER_ALT_QLAND (from a Q mode, QLAND at once); these two actions change the mode immediately, even in the middle of an AUTO landing, so the vehicle lands where it is; only actions 1 RTL, 2 Land and 7 AUTOLAND-or-RTL check "already landing" |
| EKF | a Q mode with position control, AUTO in VTOL flight | AUTO in VTOL flight → QLAND; a pilot Q mode with position control → QHOVER; fixed-wing modes, no change |
| a transition that drags on | AIRSPEED_WAIT longer than `Q_TRANS_FAIL`, including continuous Q-assist in cruise | `Q_TRANS_FAIL_ACT`: 0 QLAND, 1 QRTL, −1 warning |
| loss of VTOL motor thrust | VTOL | "Potential VTOL Thrust Loss", the mixer stops counting on the failed motor; `Q_THRST_LOSS_OPT` = 0 runs the detection everywhere, bit 0 disables it, bit 1 runs it in VTOL modes only |

**An airspeed sensor failure in the middle of a transition.** The dangerous case is a sensor that lies plausibly: it reads 2–3 m/s at a real 25 (a blocked pitot tube). The transition does not leave AIRSPEED_WAIT, the VTOL motors keep running at a speed where they are no longer needed, and speed-based Q-assist believes the vehicle is on the edge of a stall. In SITL (`SIM_ARSPD_FAIL = 3`, `Q_TRANS_FAIL = 8`): in 8 s the ground speed grew to 27.6 m/s, then "Transition failed, exceeded time limit" and QLAND, with braking, a 20 m climb and a landing. With `Q_TRANS_FAIL = 0` (the default) there is no timeout at all, and the vehicle keeps flying "assisted" by the VTOL motors until the battery is flat. The sensor protection, `ARSPD_OPTIONS` bit 0 (disable use of the sensor on an airspeed/ground speed mismatch), looks at a difference from GPS speed greater than `ARSPD_WIND_MAX` (default 0, off; see `ap-setup-plane`) and at consistency with EKF3 (bit 3, `ARSPD_WIND_GATE` = 5); in the run with defaults it did not act within 8 s. A second run with `ARSPD_WIND_MAX = 10` and `Q_TRANS_FAIL = 0`: "Airspeed 1 warning 10.7m/s air to gnd speed diff" after 3.1 s, "Airspeed sensor 1 failure. Disabling" after 9.3 s (`ARSPD_USE` became 0), yet the transition did not complete in the following 20 s of flight at 30 m/s either, and the VTOL motors kept running. The log of that run shows why synthetic airspeed did not pick the transition up: during a transition EKF3 does not estimate wind (`XKF2.VWN = VWE = 0`, see "Where the airspeed comes from"), the AHRS takes the DCM estimate, and DCM had already "learned" a wind of 18.4 m/s from the false sensor (`DCM.VWN`), so after the sensor was disabled the synthetic airspeed was 10.8…12.3 m/s (`CTUN.As`, `DCM.SAs`) at a ground speed of 30 m/s, below both `AIRSPEED_MIN` 13 and `Q_ASSIST_SPEED` 18.

Hence a course rule (derived from the code and the runs; the ArduPilot documentation gives no number): always set `Q_TRANS_FAIL`, to roughly twice the time the transition takes to reach the airspeed threshold in your log (4.2 s in SITL → 8–10 s; the parameter range is 0…20 s). But the timer counts **any** continuous stay in AIRSPEED_WAIT, and Q-assist in cruise also puts the transition into AIRSPEED_WAIT: a SITL run with `Q_ASSIST_ALT = 120` at 77 m in FBWA at 30 m/s and `Q_TRANS_FAIL = 5` gave "Alt assist 76.6m", "Transition started airspeed 30.1", and exactly 5.0 s later "Transition failed, exceeded time limit" and QLAND in the middle of cruise. So `Q_TRANS_FAIL` also has to be longer than the longest assistance episode you expect (a low pass with `Q_ASSIST_ALT`), and with permanently forced assistance (bit 7 of `Q_OPTIONS` or switch 82 high) the code would trigger it on every flight (**not verified** in SITL). Set `ARSPD_WIND_MAX` for the sake of the warning and of disabling the sensor, but do not count on it to save the transition.

If instead the sensor reads too **high** (the pitot tube sits in the wash of the VTOL props), the transition completes too early, the VTOL motors shut down at a speed below stall, and Q-assist (if `Q_ASSIST_SPEED` relies on the same sensor) does not start. That is the "nose drop right after Transition done" scenario; the tube placement is covered in `ap-plane-tuning`.

### Which mode in which phase of flight
| Phase | Mode | Why | What not to do |
|---|---|---|---|
| first takeoff, hover tuning | QSTABILIZE, then QHOVER | no dependence on GPS or the EKF position | QLOITER before the compass is verified |
| a normal manual takeoff | QHOVER or QLOITER | altitude holds itself | FBWA from the ground, hanging in a transition near the ground |
| automatic takeoff | AUTO with `NAV_VTOL_TAKEOFF` | `Q_TKOFF_FAIL_SCL`, `Q_TKOFF_ARSP_LIM` protect you | `NAV_TAKEOFF` with bit 1 and no fixed-wing landing gear |
| manual forward transition | FBWA, throttle > 50 %, at ≥ 60 m altitude (`ap-quadplane`) | surfaces and throttle are under the pilot's control | FBWB/CRUISE with the throttle at zero; MANUAL has no safety net |
| cruise | FBWA, CRUISE, AUTO | the wing; the VTOL motors are stopped | keeping `Q_ASSIST_SPEED` above the minimum cruise airspeed |
| return | RTL with `Q_RTL_MODE` = 1 or 2 | fast as a plane, lands by itself | `Q_RTL_MODE = 0` without `RTL_AUTOLAND`, an endless loiter |
| manual landing | QHOVER or QLOITER from ≥ 30 m altitude, then QLAND | a back transition with altitude to spare | a Q mode at high speed near the airspace ceiling: it gains 15–20 m |
| automatic landing | AUTO with `NAV_VTOL_LAND`, or QRTL | the airbrake and POSITION1 stages are computed from `Q_TRANS_DECEL` | `NAV_VTOL_LAND` closer than 0.75·d_stop after a waypoint |
| something went wrong in cruise | QHOVER (if you do not trust the EKF) or QLOITER | the copter half holds the vehicle at any speed | MANUAL for the sake of "direct control" |

### Place in the system

- **Receives:** the boundary "who controls what in which mode" and where to look for a symptom (`ap-vtol-anatomy`); V_s and `AIRSPEED_MIN` (`aero-wing`, `ap-setup-plane`); the fixed-wing RC failsafe tables (`ap-setup-plane`); the mission and its commands (`ap-missions`).
- **Provides:** the transition thresholds, `Q_ASSIST_*`, `Q_TRANS_FAIL`, `Q_RTL_MODE` and the reference numbers of a first transition from SITL to the bring-up and the first flight (`ap-quadplane`); `QTUN.Trn`, `QTUN.Ast`, `QPOS.State` to log analysis (`ap-logs`).
- **If you get it wrong here:** `Q_ASSIST_SPEED` above `AIRSPEED_MIN` → in CRUISE at low throttle the VTOL motors cycle on and off → the battery drains sooner than planned and its failsafe triggers (`ap-safety-fs`). `Q_TRANS_FAIL = 0` with a blocked pitot tube → the transition never completes and the VTOL motors pull for the whole flight (`ap-quadplane`).

## practice
All outputs below are real SITL runs of ArduPlane 4.7.2 (`./waf plane`, `arduplane --model quadplane --defaults Tools/autotest/default_params/quadplane.parm`, speedup 4×). A pymavlink script changed modes and sent RC overrides; the time comes from `time_boot_ms`, so it is simulator time. The columns: mode, airspeed `asp`, ground speed `gs`, altitude `alt`, forward-motor throttle `thr` in %, the mean PWM of the VTOL motors (outputs 5–8) `vtol_pwm`, pitch. The SITL default parameters: `AIRSPEED_MIN` 13, `AIRSPEED_CRUISE` 25, `Q_ASSIST_SPEED` 18, `Q_TRANSITION_MS` 5000, `Q_TRANS_DECEL` 2. The key fragment of the script for steps 1–3:

```python
    RC[2] = 2000
    mode('FBWA')
    t_start = S['t']; lat0, lon0 = S['lat'], S['lon']
    wait_until(lambda: False, 25, sample=0.5)
    print('         FBWA forward transition window: %.1f s' % (S['t'] - t_start))
    RC[2] = 1000
    mode('CRUISE')
    wait_until(lambda: False, 40, sample=1.0)
```

### Step 1. Forward transition in FBWA
A hover in QLOITER at 62 m, throttle stick to maximum, mode FBWA:

```text
  69.73  >>>> set mode FBWA
  69.73  MODE FBWA
  69.73  MSG  Transition started airspeed 0.7   [asp 0.7 gs 0.0 alt 62.5]
  70.73  ---- FBWA       asp   0.6  gs   2.2  alt   62.5  thr  89  vtol_pwm   1705  pitch  -0.1
  71.73  ---- FBWA       asp   6.3  gs   8.2  alt   62.6  thr 100  vtol_pwm   1652  pitch  -0.2
  72.73  ---- FBWA       asp  11.8  gs  13.6  alt   62.8  thr 100  vtol_pwm   1517  pitch  -0.4
  73.83  ---- FBWA       asp  17.1  gs  18.5  alt   62.9  thr 100  vtol_pwm   1248  pitch  -0.7
  73.93  MSG  Transition airspeed reached 18.3   [asp 17.9 gs 19.3 alt 62.9]
  74.73  ---- FBWA       asp  20.5  gs  21.7  alt   63.0  thr 100  vtol_pwm   1172  pitch  -0.6
  76.73  ---- FBWA       asp  25.4  gs  26.1  alt   64.7  thr 100  vtol_pwm   1172  pitch   0.2
  78.83  ---- FBWA       asp  27.9  gs  28.5  alt   67.6  thr 100  vtol_pwm   1172  pitch   0.2
  78.93  MSG  Transition done   [asp 28.1 gs 28.6 alt 67.9]
  79.83  ---- FBWA       asp  28.6  gs  29.2  alt   69.0  thr 100  vtol_pwm   1000  pitch  -0.6
```

Read it like this. The threshold is 18.3 m/s, not `AIRSPEED_MIN` 13: between 13 and 18 m/s speed-based Q-assist was active, and the state could not leave AIRSPEED_WAIT. From "started" to "reached" it took 4.2 s; the mean acceleration from the start of motion (70.23, 0.4 m/s) to 18.5 m/s over 3.6 s is about 5 m/s². The timer is exactly 5.0 s (`Q_TRANSITION_MS`). The VTOL motors drop from 1705 to 1172 while still in the acceleration phase (the wing starts to carry the load) and to 1000 after "done"; by the threshold they are already near minimum, so the linear throttle reduction over the timer is barely visible in the PWM. Integrating `gs` over the samples gives 35 m to the threshold and 159 m to "done". The altitude rose by 5 m during the transition. A lower bound for planning the site: d ≥ V_thr² / (2·a) + V_thr · T, where V_thr = max(`AIRSPEED_MIN`, `Q_ASSIST_SPEED`), T = `Q_TRANSITION_MS`: 18² / (2 · 5) + 18 · 5 = 32.4 + 90 = 122 m. SITL produced 159 m because the vehicle kept accelerating to 28 m/s during the timer, so the formula gives a lower bound.

### Step 2. Q-assist in CRUISE with the throttle at zero
From 30 m/s: CRUISE, throttle stick to minimum (the demanded airspeed = `AIRSPEED_MIN` 13):

```text
 111.83  ---- CRUISE     asp  18.5  gs  18.6  alt   95.1  thr  24  vtol_pwm   1000  pitch  -0.6
 112.43  MSG  Transition started airspeed 17.9   [asp 18.0 gs 18.1 alt 95.1]
 112.83  ---- CRUISE     asp  17.8  gs  18.1  alt   95.1  thr  45  vtol_pwm   1166  pitch  -2.1
 113.13  MSG  Transition airspeed reached 18.0   [asp 17.9 gs 18.4 alt 94.9]
 118.13  MSG  Transition done   [asp 18.6 gs 18.9 alt 98.7]
 119.83  MSG  Transition started airspeed 17.9   [asp 18.0 gs 18.0 alt 99.7]
 121.13  MSG  Transition airspeed reached 18.0   [asp 17.9 gs 18.5 alt 99.9]
 126.13  MSG  Transition done   [asp 18.9 gs 19.3 alt 102.9]
 128.23  MSG  Transition started airspeed 18.0   [asp 18.1 gs 18.0 alt 103.2]
 129.43  MSG  Transition airspeed reached 18.1   [asp 18.0 gs 18.6 alt 102.3]
 134.43  MSG  Transition done   [asp 19.2 gs 19.6 alt 104.4]
 136.83  MSG  Transition started airspeed 17.9   [asp 18.1 gs 18.0 alt 104.0]
```

Assistance starts instantly at 17.9 m/s (the speed trigger has no delay), the VTOL motors push the vehicle back above 18, then 5 s of timer again, and 1.7–2.4 s later it starts over: four cycles in 25 s. CRUISE faithfully holds the demanded 13 m/s, and Q-assist faithfully refuses to let the airspeed drop below 18. The conclusion: `Q_ASSIST_SPEED` must be below `AIRSPEED_MIN` (SITL is set the other way on purpose; on your own vehicle it is a mistake).

### Step 3. Back transition into QLOITER with the switch
From 27.7 m/s in CRUISE: QLOITER:

```text
 149.93  MODE QLOITER
 150.43  ---- QLOITER    asp  27.8  gs  28.1  alt   87.8  thr   0  vtol_pwm   1160  pitch   1.7
 151.53  ---- QLOITER    asp  24.1  gs  22.3  alt   91.6  thr   0  vtol_pwm   1156  pitch  12.7
 152.43  ---- QLOITER    asp  19.3  gs  16.8  alt   96.9  thr   0  vtol_pwm   1161  pitch  21.6
 153.53  ---- QLOITER    asp  13.2  gs  10.6  alt  103.4  thr   0  vtol_pwm   1167  pitch  29.5
 154.93  ---- QLOITER    asp   6.8  gs   6.1  alt  107.3  thr   1  vtol_pwm   1175  pitch  24.5
 156.03  ---- QLOITER    asp   2.7  gs   2.0  alt  105.3  thr  66  vtol_pwm   1779  pitch  18.3
         QLOITER: groundspeed < 1 m/s after 6.3 s
```

The pitch grows at about 9° per second up to 29.7°: that is the `Q_BACKTRANS_MS` 3000 ms envelope up to min(`Q_A_ANGLE_MAX` 30°, `PTCH_LIM_MAX_DEG` 30° from `quadplane.parm`); with the firmware default `PTCH_LIM_MAX_DEG` of 20° the limit for the first 3 s would be 20°. The braking comes from the wing at a high angle of attack, so the VTOL motors are almost at idle (1160) down to 6 m/s, and the altitude rises from 87.8 to 107.3 m, a gain of 19.5 m. The distance is 91 m in 6.1 s (down to 2 m/s), an average of about 4.2 m/s², twice as hard as `Q_TRANS_DECEL`: with the switch you do not get the planned deceleration of a mission.

### Step 4. Mission: landing stages and a check of the formula
The mission: `NAV_VTOL_TAKEOFF` to 40 m → two waypoints at 60 m, 800 m from home → `NAV_VTOL_LAND` at home:

```text
  44.43  MSG  Transition started airspeed 0.4   [asp 0.1 gs 0.0 alt 40.2]
  48.93  MSG  Transition airspeed reached 18.3   [asp 18.0 gs 19.0 alt 42.4]
  53.93  MSG  Transition done   [asp 23.5 gs 23.9 alt 45.0]
  90.43  MSG  Mission: 4 VTOLLand   [asp 25.0 gs 25.3 alt 59.9]
  90.43  MSG  VTOL approach d=859.7   [asp 25.0 gs 25.3 alt 59.9]
 130.03  MSG  VTOL airbrake v=19.2 d=130 sd=130 h=60.2   [asp 18.9 gs 19.2 alt 60.2]
 131.63  MSG  VTOL position1 v=18.0 d=99.8 h=60.3 dc=19.1   [asp 18.0 gs 18.0 alt 60.3]
 139.03  MSG  VTOL position2 started v=6.5 d=9.5 h=60.6   [asp 6.9 gs 6.6 alt 60.6]
 144.33  MSG  Land descend started   [asp 0.2 gs 1.1 alt 60.3]
 183.33  MSG  Land final started   [asp 0.7 gs 0.1 alt 6.0]
 201.13  MSG  Land complete   [asp 0.3 gs 0.0 alt 0.2]
 202.03  landed 0.1 m from home
```

Check the numbers yourself: approach speed 19 m/s = (25 + 13) / 2; airbrake from 19.2²/(2·2) + 2·19.2 = 130.6 m, 130 in the log; POSITION1 1.6 s later, when the airspeed fell to 18.0 = max(13 − 2, 18); POSITION2 at 9.5 m and 6.5 m/s (the conditions are < 10 m and < 9 m/s); from 60.3 to 6.0 m in 39 s ≈ 1.4 m/s (`Q_WP_SPD_DN` 1.5 with a slowdown near the boundary); the final stage 6.0 m → touchdown in 11.5 s ≈ 0.5 m/s (`Q_LAND_FINAL_SPD`).

### Step 5. The airspeed sensor stuck at 3 m/s
`SIM_ARSPD_FAIL = 3` (the sensor reads 2.6 m/s), `Q_TRANS_FAIL = 8`, from QLOITER at 60 m into FBWA at full throttle:

```text
  64.83  MSG  Transition started airspeed 2.6   [asp 2.6 gs 0.0 alt 60.1]
  68.83  ---- FBWA       asp   2.6  gs  18.1  alt   62.0  thr 100  vtol_pwm   1310  pitch  -0.7
  70.83  ---- FBWA       asp   2.6  gs  24.3  alt   62.7  thr 100  vtol_pwm   1158  pitch  -0.1
  72.83  MODE QLAND
  72.83  MSG  Transition failed, exceeded time limit   [asp 2.6 gs 27.6 alt 65.2]
  76.83  ---- QLAND      asp   2.6  gs   8.9  alt   83.6  thr   0  vtol_pwm   1166  pitch  29.6
  79.43  ---- QLAND      asp   2.6  gs   0.7  alt   81.4  thr  55  vtol_pwm   1711  pitch  14.2
 149.33  MSG  Land complete   [asp 2.6 gs 0.0 alt 0.1]
```

Exactly 8.0 s after "started": QLAND. In that time the vehicle flew 128 m and accelerated to 27.6 m/s over the ground, and while braking in QLAND it climbed from 65 to 85.8 m. Without `Q_TRANS_FAIL` the "failed" line would never have appeared. A control run with `ARSPD_WIND_MAX = 10` and `Q_TRANS_FAIL = 0`:

```text
  64.73  MSG  Transition started airspeed 2.6   [asp 2.6 gs 0.0 alt 60.2]
  67.83  MSG  Airspeed 1 warning 10.7m/s air to gnd speed diff   [asp 2.6 gs 14.5 alt 61.9]
  74.03  MSG  Airspeed sensor 1 failure. Disabling   [asp 2.6 gs 28.8 alt 67.1]
  94.83  ---- FBWA       asp   2.6  gs  30.7  alt  101.7  thr 100  vtol_pwm   1154  pitch  -0.0
  ARSPD_USE now 0.0
```

The sensor is disabled, but "Transition airspeed reached" still did not arrive in 30 s: the VTOL motors ran for the whole stretch. In the log of this run (`.BIN`): `CTUN.As` after "Disabling" is 10.8 m/s and 12.3 m/s by 94 s, `DCM.VWN` = 18.4 m/s, `XKF2.VWN` = 0; the synthetic DCM airspeed is biased low by the wind "learned" from the false sensor.

### Step 6. RTL with `Q_RTL_MODE = 1`
The mission took the vehicle 700+ m away; mode RTL at 25 m/s:

```text
  75.23  MODE RTL
 103.83  MODE QRTL
 103.83  MSG  VTOL airbrake v=25.2 d=158 sd=158 h=32.0   [asp 24.9 gs 25.2 alt 32.1]
 104.83  MSG  VTOL position1 v=23.9 d=135.5 h=31.7 dc=19.1   [asp 24.3 gs 24.0 alt 31.6]
 113.43  MSG  VTOL position2 started v=6.8 d=9.9 h=34.7   [asp 7.1 gs 7.0 alt 34.7]
 149.63  MSG  Land complete   [asp 0.7 gs 0.0 alt 0.2]
 150.03  landed 0.0 m from home
```

The RTL → QRTL switch is at 158 m = 25.2² / 4 = 158.8 m (the stopping distance is greater than the 60 m radius). Compare with step 4: at 25 m/s airbrake would have started from 158.8 + 50.4 = 209 m, but QRTL enters airbrake at once, because inside 1.5 × d_stop(`AIRSPEED_CRUISE`) = 234 m no approach is flown.

### Moving to real hardware
The order on a real vehicle, after the bring-up and a confident hover per `ap-quadplane`, with propellers on only at the flight step, and the site and people per `f-safety`:

1. On the ground, props off, armed in QSTABILIZE: switch to FBWA; the log shows "Transition started" and the VTOL motors keep running. In MANUAL, on a 4+1 they stop.
2. Check the parameters before the flight: `Q_ASSIST_SPEED` = `AIRSPEED_MIN` − 3 m/s (not below V_s), `Q_TRANS_FAIL` ≈ 2 × the expected time to the threshold (course rule) and longer than the longest Q-assist episode, `Q_TRANS_FAIL_ACT` = 0 or 1, `ARSPD_WIND_MAX` set, `Q_RTL_MODE` = 1 and `RTL_AUTOLAND` = 0.
3. The first transition: at ≥ 60 m altitude, into the wind, throttle > 50 % in FBWA; the fallback plan is QHOVER.
4. After the flight, in the log: `QTUN.Trn` 0 → 1 → 2, the times 0 → 1 and 1 → 2, `ARSP.Airspeed` against `GPS.Spd` over the whole transition, and `QTUN.Ast` all zeros outside the transition.

Hardware criteria: the transition completed (`Trn = 2`) no later than `Q_TRANS_FAIL`; the timer time matched `Q_TRANSITION_MS` ±0.2 s; after "Transition done" the airspeed did not drop below `AIRSPEED_MIN`; `QTUN.Ast` = 0 in cruise; the back transition into QHOVER was started with at least 20 m of altitude to spare below the ceiling.

Self-check: the lab is done when (SITL) for step 1 you have identified the threshold 18.3 m/s and the reason it is "not 13", the time 4.2 + 5.0 = 9.2 s and the distance 159 ± 10 m; for step 2 you have explained the cycle and stated the rule `Q_ASSIST_SPEED` < `AIRSPEED_MIN`; for step 3 you have written down the altitude gain 19.5 ± 1 m and the braking distance 91 ± 5 m; for step 4 the airbrake formula gave 130.6 m against 130 in the log, and the POSITION1 threshold is 18 m/s; for step 5 you have named the time 8 s and the action QLAND per `Q_TRANS_FAIL_ACT` = 0; for step 6, 158.8 m. For hardware, use the criteria of the subsection above.

**Reference for the self-check.** A correct analysis: the transition in SITL completes at max(`AIRSPEED_MIN`, `Q_ASSIST_SPEED`) = 18 m/s; `Q_TRANSITION_MS` is the time after the threshold, not a timeout; airbrake is V²/(2·`Q_TRANS_DECEL`) + 2V. Typical wrong results: (1) "the transition takes 5 s": the AIRSPEED_WAIT phase (4.2 s) is forgotten, the full time is 9.2 s; (2) an airbrake distance of 92 m: the 2V = 38.4 m allowance is forgotten; (3) "QLOITER decelerates at `Q_TRANS_DECEL`": with the switch, the deceleration is set by `Q_BACKTRANS_MS` and `Q_A_ANGLE_MAX`, while `Q_TRANS_DECEL` is the planned one in a mission and in QRTL.

## diagnostics
- **Symptom:** after switching to FBWA the VTOL motors do not shut down and "Transition airspeed reached" does not appear
  - Possible cause: the airspeed does not reach max(`AIRSPEED_MIN`, `Q_ASSIST_SPEED`); the airspeed sensor is stuck, or there is neither a sensor nor GPS (no airspeed estimate).
  - In the log: `QTUN.Trn = 0` all the time; `ARSP.Airspeed` does not grow while `GPS.Spd` does.
  - What to do: QHOVER; check the pitot tube and `ARSPD_USE`; set `Q_TRANS_FAIL` and `ARSPD_WIND_MAX`.
- **Symptom:** a roll or an "uncontrolled" turn at the very start of a transition (4+1)
  - Possible cause: both controllers work during AIRSPEED_WAIT, so a reversed aileron or elevator shows up only now; forward-motor torque; climbing on the VTOL motors.
  - What to do: check the surface directions in FBWA on the bench (`ap-setup-plane`); bit 0 of `Q_OPTIONS` (Level Transition); transition with throttle > 50 % to accelerate.
- **Symptom:** a sink and a nose drop right after "Transition done"
  - Possible cause: `AIRSPEED_MIN` is below 1.2 V_s, or the sensor reads high (the pitot tube is in the wash of the VTOL props), or `Q_TRANSITION_MS` is too short.
  - What to do: recalculate V_s (`aero-wing`), move the tube, compare `ARSP.Airspeed` with `GPS.Spd` on opposite headings; increase `Q_TRANSITION_MS` to 5000–8000.
- **Symptom:** in cruise, "Transition started airspeed …" every few seconds
  - Possible cause: `Q_ASSIST_SPEED` is above the airspeed the mode holds (CRUISE/FBWB at low throttle hold `AIRSPEED_MIN`).
  - In the log: `QTUN.Ast` with bit 2 (airspeed).
  - What to do: `Q_ASSIST_SPEED` = `AIRSPEED_MIN` − 3 m/s, not below V_s.
- **Symptom:** "Angle assist r=… p=…" in an ordinary turn
  - Possible cause: `ROLL_LIMIT_DEG` is smaller than the bank actually used (for example in AUTOTUNE), and the attitude error exceeds `Q_ASSIST_ANGLE`.
  - What to do: make `ROLL_LIMIT_DEG` consistent with your turns; if needed, raise `Q_ASSIST_ANGLE` or `Q_ASSIST_DELAY`.
- **Symptom:** on switching to QHOVER in cruise the vehicle pitches up sharply and gains 15–20 m
  - Possible cause: normal braking on the wing: pitch up to `Q_A_ANGLE_MAX` over `Q_BACKTRANS_MS`.
  - What to do: transition at a lower speed and with altitude to spare; for a smoother entry, increase `Q_BACKTRANS_MS`.
  - Consequences: busting the airspace ceiling or entering cloud.
- **Symptom:** a VTOL landing in a mission overshoots the point ("VTOL Overshoot")
  - Possible cause: the real deceleration is weaker than `Q_TRANS_DECEL`, a tailwind, or an approach loiter radius smaller than the stopping distance.
  - What to do: reduce `Q_TRANS_DECEL` (for example 2 → 1.5); `Q_FW_LND_APR_RAD` ≥ V²/(2·`Q_TRANS_DECEL`) (course rule); approach into the wind.
- **Symptom:** arming is refused with "VTOL land too short, min X m"
  - Possible cause: the landing point is too close to the preceding `NAV_WAYPOINT`.
  - What to do: move the preceding waypoint farther than 0.75·V²/(2·`Q_TRANS_DECEL`), or set `TECS_LAND_ARSPD` below cruise.
- **Symptom:** RTL loiters over home and does not land
  - Possible cause: `Q_RTL_MODE = 0` and no `RTL_AUTOLAND` with a landing sequence.
  - What to do: `Q_RTL_MODE = 1` (or 2 for an approach into the wind).

## checklist
- `Q_ASSIST_SPEED` = `AIRSPEED_MIN` − 3 m/s (− 5 with no sensor), not below V_s and not above `AIRSPEED_MIN`
- `Q_TRANS_FAIL` is set (≈ 2 × the time to the threshold, a course rule, and longer than the longest Q-assist episode), `Q_TRANS_FAIL_ACT` is chosen, `ARSPD_WIND_MAX` is not 0
- I understand that `Q_TRANSITION_MS` is counted after the airspeed threshold
- `Q_RTL_MODE` = 1 or 2, `RTL_AUTOLAND` = 0
- The `Q_OPTIONS` bits for the RC failsafe in Q modes are chosen deliberately (the default is QLAND)
- `NAV_VTOL_LAND` is farther than 0.75·d_stop from the preceding waypoint; the approach loiter radius ≥ d_stop (course rule)
- A back transition with the switch only with 20 m of altitude to spare above

## references
- ArduPilot 4.7.2 — ArduPlane/quadplane.cpp: SLT_Transition::update(), vtol_position_controller(), stopping_distance_m(), Q_* parameters | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/ArduPlane/quadplane.cpp | primary | A
- ArduPilot 4.7.2 — ArduPlane/VTOL_Assist.cpp: should_assist() | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/ArduPlane/VTOL_Assist.cpp | primary | A
- ArduPilot 4.7.2 — ArduPlane/commands_logic.cpp: verify_landing_vtol_approach() | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/ArduPlane/commands_logic.cpp | primary | A
- ArduPilot 4.7.2 — ArduPlane/mode_rtl.cpp, mode_qrtl.cpp: Q_RTL_MODE, QRTL | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/ArduPlane/mode_qrtl.cpp | primary | A
- ArduPilot 4.7.2 — ArduPlane/events.cpp, ekf_check.cpp: failsafe in Q modes | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/ArduPlane/events.cpp | primary | A
- ArduPilot 4.7.2 — ArduPlane/tailsitter.cpp: transition_fw_complete() | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/ArduPlane/tailsitter.cpp | primary | A
- Flying QuadPlane — ArduPilot Plane docs (the threshold "AIRSPEED_MIN, or Q_ASSIST_SPEED if that is higher") | https://ardupilot.org/plane/docs/quadplane-flying.html | primary | A
- MAVLink common.xml — MAV_CMD_NAV_VTOL_TAKEOFF (84), MAV_CMD_NAV_VTOL_LAND (85), MAV_CMD_DO_VTOL_TRANSITION (3000) | https://mavlink.io/en/messages/common.html | primary | A
