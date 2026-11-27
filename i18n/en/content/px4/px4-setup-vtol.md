---
id: px4-setup-vtol
source: content/px4/px4-setup-vtol.md
source_hash: ac557d93ac22
title: "PX4 from scratch: plane and VTOL"
level: L3
readingTime: 75 min
firmware: PX4 1.18 (checked against v1.18.0)
status: published
added: 2026-11-22
tags:
  - PX4
  - VTOL
  - plane
  - transition
  - quad-chute
  - airspeed
related:
  - px4-setup-scratch
  - px4-outputs-servos
  - px4-hardware-peripherals
  - px4-safety-return
  - px4-control
  - aero-wing
  - aero-stability
  - ap-setup-plane
  - ap-quadplane
  - inav-mixer-vtol
  - px4-rc-tuning
  - px4-console-params
next:
  - px4-safety-return
---

## summary
A plane and a VTOL on PX4 1.18, from choosing the airframe to the first transition, in the same 17 steps as the multirotor in `px4-setup-scratch`, plus everything a multirotor does not have: the `FW_AIRSPD_*` airspeed envelope and how it relates to the stall, TECS throttle and pitch, the fixed-wing rate loop with airspeed scaling, hand launch and runway takeoff, the mission landing pattern, fixed-wing autotune, the front and back transition as `vtol_att_control` implements them (completion conditions, flight without an airspeed sensor, timeouts), and quad-chute, with the exact trigger conditions from the source and what the vehicle does afterward. Every number you have to choose comes with a rule for choosing it. The practice needs no hardware and no simulator: the envelope from mass, wing area and C_Lmax, a transition timeline from an airspeed table, control surface signs, and three errors to find in a parameter file; you check your answers against the reference on the page.

## theory
### What is in the module and in what order to read it
First, how the plane and VTOL path differs from the multirotor across the 17 steps, and which airframe to pick. Then the fixed-wing part: the control modules, the airspeed envelope, throttle and pitch, the rate loop, flight without an airspeed sensor, takeoff, landing, autotune. Then VTOL: the front transition, the back transition, tiltrotor and tailsitter specifics, quad-chute, hover. At the end, a table of first values with rules, and a mapping to ArduPlane concepts. Outputs, servos and surface signs are covered in `px4-outputs-servos`, the airspeed sensor in `px4-hardware-peripherals`, failsafe and Return in `px4-safety-return`, the transition switch in `px4-rc-tuning`; here they are only used, not repeated.

### 17 steps: what changes for a plane and a VTOL
The order is the same as in `px4-setup-scratch` (which also covers the firmware, the receiver and power calibration). The differences:

| # | Step | What a plane / VTOL adds | Where | Details |
|---|---|---|---|---|
| 1 | Firmware, backup | — | bench | `px4-setup-scratch` |
| 2 | Airframe | `SYS_AUTOSTART` of a plane / VTOL, `CA_AIRFRAME`, rotor and surface geometry | bench | this module |
| 3 | Ports | airspeed sensor on I²C or CAN | bench | `px4-hardware-peripherals` |
| 4–5 | Receiver, radio | transition switch `RC_MAP_TRANS_SW`, autotune channel | bench | `px4-rc-tuning` |
| 6 | Motor protocol | lift motors on DShot, the pusher (or puller) motor and the servos on their own timer groups | bench | `px4-outputs-servos` |
| 7 | Motors and surfaces | order and direction of the lift motors; the direction of every surface | bench, no props | `px4-outputs-servos`, practice step 3 |
| 8 | ESC calibration | for a PWM ESC on the pusher motor | bench, no props | `px4-setup-scratch` |
| 9 | Sensors | plus airspeed sensor calibration | bench | `px4-hardware-peripherals` |
| 10 | Power | — | bench | `px4-setup-scratch` |
| 11 | Modes | Manual on a plane is direct control of the surfaces | bench | `px4-rc-tuning` |
| 12 | Failsafe | plus quad-chute and `COM_QC_ACT` | bench + field | this module, `px4-safety-return` |
| 13 | OSD, telemetry | — | bench | `px4-hardware-peripherals` |
| 14 | GPS, Return, mission | landing pattern, `MIS_TKO_LAND_REQ`, `RTL_TYPE` | bench | this module |
| 15 | First flight | VTOL: hover → transition → fixed-wing → back transition | field | this module |
| 16 | Tuning | MC per `px4-control`, then `FW_AT_*` | field | this module |
| 17 | Log, parameters | ULog of the first transition, `.params` | bench | `px4-console-params` |

{{diagram:px4-vtol-setup-flow|Of the 17 steps only the failsafe test, the first flight with a transition and tuning go to the field; everything else, including surface direction and a transition check on the ground, is done on the bench without propellers.}}

### Airframe and `CA_AIRFRAME`
The vehicle type comes from the airframe script (`ROMFS/px4fmu_common/init.d/airframes/`, v1.18.0): it sources `rc.fw_defaults` or `rc.vtol_defaults` and writes the geometry. The file number is the `SYS_AUTOSTART` value.

| `SYS_AUTOSTART` | File | `CA_AIRFRAME` | `VT_TYPE` | Default actuators |
|---|---|---|---|---|
| 2100 | `2100_standard_plane` | 1 Fixed-wing | — | 1 motor, left/right ailerons, elevator, rudder |
| 3000 | `3000_generic_wing` | 1 Fixed-wing | — | 1 motor, left/right elevons |
| 13000 | `13000_generic_vtol_standard` | 2 Standard VTOL | 2 Standard | 4 lift + 1 pusher, ailerons, elevator, rudder |
| 13100 | `13100_generic_vtol_tiltrotor` | 3 Tiltrotor VTOL | 1 Tiltrotor | 4 motors, 2 tilt servos, ailerons, V-tail |
| 13030 | `13030_generic_vtol_quad_tiltrotor` | 3 Tiltrotor VTOL | 1 | a variant with four tilting motors |
| 13200 | `13200_generic_vtol_tailsitter` | 4 Tailsitter VTOL | 0 Tailsitter | 2 motors, elevons |

The fifth rotor of the standard VTOL points forward, `13000_generic_vtol_standard`, lines 15–18:
```
param set-default CA_AIRFRAME 2
param set-default CA_ROTOR_COUNT 5
param set-default CA_ROTOR4_AX 1
param set-default CA_ROTOR4_AZ 0
```
and line 28: `param set-default VT_TYPE 2`. On a tailsitter (`13200_generic_vtol_tailsitter`, lines 32–34) the airframe itself unlocks the surfaces in hover and shortens the back transition:
```
param set-default VT_TYPE 0
param set-default VT_ELEV_MC_LOCK 0
param set-default VT_B_TRANS_DUR 5
```
The other `CA_AIRFRAME` values: 0 Multirotor, 5–6 Rover, 7 Motors (6DOF), 8 Multirotor with Tilt, 9 Custom, 10–12 helicopters, 13 Rover (Mecanum), 14–15 Spacecraft. Rotor positions (`CA_ROTORn_PX/PY`, axes `AX/AZ`, `KM`) and surfaces (`CA_SV_CSn_*`, `CA_SV_TLn_*`) are edited on the Actuators screen; the fields are explained in `px4-outputs-servos`. The airframe files 13000, 13100, 13200 are identical in 1.15.4–1.18.0; in 2100 and 3000 the `CA_AIRFRAME 1` line moved to `rc.fw_defaults` in 1.18. `rc.vtol_defaults` sets `SYS_HAS_NUM_ASPD` 1, `MIS_TKO_LAND_REQ` 2, `MIS_TAKEOFF_ALT` 20 m, `RTL_TYPE` 1, `WV_EN` 1; `rc.fw_defaults` sets `CA_AIRFRAME` 1 (since 1.18), `SYS_HAS_NUM_ASPD` 1, `MIS_TKO_LAND_REQ` 2, `RTL_TYPE` 1, `MIS_TAKEOFF_ALT` 25 m, `RTL_RETURN_ALT` and `RTL_DESCEND_ALT` 100 m, `COM_DISARM_PRFLT` −1 (and no `WV_EN`).

### Which type to choose
An engineering estimate, not a firmware rule (community question J5):

| Task | Type | Why | Cost |
|---|---|---|---|
| First VTOL, mapping, delivery up to 2–3 kg | Standard (4+1) | the transition is just accelerating on the pusher motor; a failed transition ends as a hover on healthy lift motors | 4 motors in fixed-wing flight are dead weight and drag |
| Long flights where aerodynamics matter | Tiltrotor | the hover motors also work in fixed-wing flight | tilt mechanics, loaded servos, a harder back transition |
| Minimum mass, a small vehicle, calm air | Tailsitter | no extra motors or servos | the worst of all in wind when hovering and landing, the hardest to tune |
| Plane only, with a field or a catapult | 2100 / 3000 | no VTOL part at all | needs a runway, a hand launch or a catapult |

After choosing, check that the lift motor thrust at full mass is no less than for a multirotor of the same size (`des-sizing`) and that the CG is within the range from `aero-stability`. The same types in ArduPilot are in `ap-quadplane`, in INAV in `inav-mixer-vtol`.

### Fixed-wing control modules since 1.17
Since 1.17 the fixed-wing part is split differently than in 1.15–1.16. The contents of `rc.fw_apps`:

| Module (1.17.0 and later) | What it does | Parameter groups | In 1.15 / 1.16 |
|---|---|---|---|
| `fw_rate_control` | rate loop, airspeed scaling, manual modes | `FW_RR_*`, `FW_PR_*`, `FW_YR_*`, `FW_MAN_*_SC`, `FW_USE_AIRSPD`, `FW_ARSP_SCALE_EN` | the same |
| `fw_att_control` | attitude loop | `FW_R_TC`, `FW_P_TC`, `FW_*_RMAX`, `FW_PSP_OFF`, `FW_MAN_R_MAX/P_MAX` | the same |
| `fw_mode_manager` | modes, takeoff, landing, launch detector, NPFG | `FW_LND_*`, `FW_TKO_*`, `FW_LAUN_*`, `RWTO_*`, `FW_P_LIM_*`, `FW_R_LIM`, `FW_THR_MIN/MAX/IDLE`, `NPFG_*` | part of `fw_pos_control` |
| `fw_lat_lon_control` (directory `fw_lateral_longitudinal_control`) | TECS and lateral acceleration | `FW_T_*`, `FW_THR_SLEW_MAX`, `FW_GND_SPD_MIN` | part of `fw_pos_control` |
| `fw_performance_model` library | envelope and throttle | `FW_AIRSPD_*`, `FW_THR_TRIM`, `FW_THR_ASPD_MIN/MAX`, `FW_T_CLMB_MAX`, `FW_T_SINK_MIN`, `WEIGHT_*` | the same |

The parameter names survived the split. Changes found by comparing the three trees: 1.16 removed `FW_SPOILERS_DESC` and added `FW_T_F_ALT_ERR`, `FW_T_THR_LOW_HGT`, `LNDFW_ROT_MAX`; 1.17 removed `FW_AT_SYSID_AMP` (the autotune excitation amplitude), `RWTO_HDG`, `RWTO_NPFG_PERIOD`, `NPFG_EN_MIN_GSP`, `NPFG_GSP_MAX_TK`, `NPFG_TRACK_KEEP`, `NPFG_WIND_REG` and added `FW_AIRSPD_FLP_SC`; the autotune defaults changed, `FW_AT_SYSID_F1` 20 → 10 Hz and `FW_AT_SYSID_TYPE` 0 (Step) → 1 (Linear sine sweep). All `VT_*` parameters have the same names and defaults in these three releases. 1.18 removed `FW_AT_START`, added `FW_GC_EN`, `FW_GC_GAIN_MIN` and `FW_LAUN_CS_LK_DY`, changed the default of `VT_PITCH_MIN` and `VT_LND_PITCH_MIN` to 0° from −5°, and lets `FW_RR_FF`, `FW_PR_FF`, `FW_YR_FF` go down to −10. In the console and in `top`, TECS has been the `fw_lat_lon_control` process since 1.17, not `fw_pos_control`.

### Airspeed envelope
All airspeeds are calibrated (CAS), in m/s, `performance_model_params.yaml`:

| Parameter | Default | Meaning in the code |
|---|---|---|
| `FW_AIRSPD_STALL` | 7 | stall airspeed: the lower bound of control surface scaling and of the airspeed sensor checks |
| `FW_AIRSPD_MIN` | 10 | minimum commanded airspeed; below it TECS accelerates more aggressively; `STALL` > `MIN` gives the error "Invalid configuration: FW_AIRSPD_STALL higher FW_AIRSPD_MIN" |
| `FW_AIRSPD_TRIM` | 15 | default cruise and the reference airspeed of control surface scaling |
| `FW_AIRSPD_MAX` | 20 | maximum commanded airspeed |
| `FW_AIRSPD_FLP_SC` | 1.0 | 0.5…1: factor on MIN and STALL with full flaps (since 1.17) |
| `WEIGHT_BASE` / `WEIGHT_GROSS` | −1 / −1 kg | with both > 0, MIN, STALL, TRIM and the transition airspeed are multiplied by √(GROSS/BASE), the ratio limited to 0.5…2 |

**Banked turn.** `fw_lat_lon_control` passes TECS a minimum airspeed of `FW_AIRSPD_MIN · √n`, where n = 1/cos φ from the current bank angle (since 1.18; 1.17 used the bank setpoint; `PerformanceModel.cpp:147–151`, `FwLateralLongitudinalControl.cpp:613–621`). This is the same physics as in `aero-wing`: V_s(φ) = V_s · √n. With `FW_R_LIM` = 50°, n = 1.556 and √n = 1.247: the minimum airspeed at full bank is a quarter higher than in straight flight.

**Rule for choosing** (the margins are from `aero-wing`: minimum safe airspeed ≥ 1.2–1.3 V_s, cruise 1.3–1.6 V_s; the PX4 parameter description only asks for "some margin between the stall speed and minimum airspeed", the VTOL docs for a transition airspeed "comfortably above your airframes stall speed"):
- `FW_AIRSPD_STALL` = V_s (calculated as in `aero-wing` or measured), rounded up to 0.5;
- `FW_AIRSPD_MIN` = 1.25 V_s, rounded up to 0.5;
- `FW_AIRSPD_TRIM` = max(1.5 V_s; `FW_AIRSPD_MIN` · √n at `FW_R_LIM`), rounded up to 0.5, so that a full-bank turn never needs more than cruise airspeed;
- `FW_AIRSPD_MAX`: about 0.9 of the level-flight airspeed at `FW_THR_MAX` (an engineering estimate: it leaves throttle for climbing and for a headwind).

After the first flight, check: in the `airspeed_validated` log, on a straight leg at `TRIM`, throttle is close to `FW_THR_TRIM`; when you slow down gently in Altitude mode, the vehicle does not start to wallow before `FW_AIRSPD_MIN` (if it does, V_s was underestimated: raise all four values).

### Throttle, pitch and TECS
| Parameter | Default | Module | Rule |
|---|---|---|---|
| `FW_THR_TRIM` | 0.6 | performance model | throttle at `FW_AIRSPD_TRIM` in level flight; take it from the first flight's log |
| `FW_THR_MIN` / `FW_THR_MAX` | 0 / 1 | mode manager | MIN > 0 only if the motor must not stop in a descent |
| `FW_THR_IDLE` | 0 | mode manager | throttle on the ground in auto modes, while waiting for the launch and in the flare |
| `FW_P_LIM_MIN` / `FW_P_LIM_MAX` | −30 / 30° | mode manager | pitch setpoint limits in every altitude-controlled mode |
| `FW_R_LIM` | 50° (35…75) | mode manager | bank limit; the envelope's √n depends on it |
| `FW_PSP_OFF` | 0° | att control | pitch in level flight at cruise; on a VTOL it is blended in during the transition |
| `FW_T_CLMB_MAX` | 5 m/s | performance model | climb rate at `FW_THR_MAX` and `TRIM`, near the end of the battery |
| `FW_T_SINK_MIN` | 2 m/s | performance model | descent rate at `FW_THR_MIN` at the same airspeed |
| `FW_T_SINK_MAX` | 5 m/s | lat-lon control | descent rate limit |
| `FW_T_ALT_TC` / `FW_T_TAS_TC` | 5 / 5 | lat-lon control | time constants of the altitude and airspeed errors |
| `FW_T_SPDWEIGHT` | 1 | mode manager | 0 controls altitude only, 2 airspeed only (gliders) |

`FW_T_CLMB_MAX` and `FW_T_SINK_MIN` are measured, not chosen: wrong values make TECS demand the impossible and lose airspeed in a climb.

### Rate loop and airspeed scaling
| Axis | P | I | FF | Integrator limit |
|---|---|---|---|---|
| Roll `FW_RR_*` | 0.05 | 0.1 | 0.5 | `FW_RR_IMAX` 0.2 |
| Pitch `FW_PR_*` | 0.08 | 0.1 | 0.5 | `FW_PR_IMAX` 0.4 |
| Yaw `FW_YR_*` | 0.05 | 0.1 | 0.3 | `FW_YR_IMAX` 0.2 |

D defaults to 0 on all three axes; the units are %/rad/s. Attitude loop: `FW_R_TC` and `FW_P_TC` are 0.4 s each, the rate limits are `FW_R_RMAX` 70, `FW_P_RMAX_POS/NEG` 60, `FW_Y_RMAX` 50 deg/s.

Airspeed scaling (`FW_ARSP_SCALE_EN` = 1, `FixedwingRateControl.cpp:155–201`): s = `FW_AIRSPD_TRIM` / max(V, `FW_AIRSPD_STALL`). The whole loop output is multiplied by s², and a positive FF gain is divided by s beforehand (a negative FF is not scaled, since 1.18): as a result the P, I and D contributions grow as s² and the FF contribution as s. At half the airspeed the P part deflects the surfaces four times as much, because the moment from a surface falls as V². Since 1.18 rate gain compression, `FW_GC_EN` (default 1), works on top of this: under high-frequency oscillation it reduces the loop output, down to a factor of `FW_GC_GAIN_MIN` (0.3). With no airspeed sensor in use V = `FW_AIRSPD_TRIM`, and on a VTOL in hover `FW_AIRSPD_STALL`. `FW_ARSP_SCALE_EN` = 0 is only for vehicles without aerodynamic control surfaces (an autogyro).

Trim: `TRIM_ROLL/PITCH/YAW` (−0.5…0.5, `commander_params.yaml`) are added to the loop output with the same s² factor, and `FW_DTRIM_*_VMIN/VMAX` change the trim as airspeed goes up and down. The mechanical neutral of a surface is `PWM_*_CENTn` (since 1.17) or `CA_SV_CSn_TRIM`, not both: the trap with resetting `TRIM` is in `px4-outputs-servos`. In Manual the stick command is multiplied by `FW_MAN_R_SC`, `FW_MAN_P_SC`, `FW_MAN_Y_SC` (default 1): these are the surface throws in manual mode; the angle limits in Stabilized are `FW_MAN_R_MAX` 45° and `FW_MAN_P_MAX` 30°.

### Flying without an airspeed sensor
`FW_USE_AIRSPD` = 1 feeds the sensor airspeed into surface scaling, the coordinated turn, TECS, the takeoff logic and the VTOL transition (`fw_rate_control_params.yaml:5`). You can do without the sensor (question J6): `SYS_HAS_NUM_ASPD` = 0 and `FW_USE_AIRSPD` = 0 (or `ASPD_PRIMARY` = 0, groundspeed minus windspeed, see `px4-hardware-peripherals`). The PX4 docs call this experimental and for experienced pilots only. Their procedure: a reference flight with the sensor in calm air; `FW_THR_TRIM` from the highest throttle in a turn or a climb, plus about 10 %; `VT_TRANS_MIN_TM` from the transition time in the log, plus 30 %; `VT_FW_MIN_ALT` 15–20 m. One limitation stays: nothing measures the stall margin in flight, so a plane without a sensor needs a larger gap between cruise and V_s, not a smaller one.

### Hand, catapult and runway takeoff
| Parameter | Default | Meaning |
|---|---|---|
| `FW_LAUN_DETCN_ON` | 0 | launch detector; at 0 the motor starts in Takeoff right after arming |
| `FW_LAUN_AC_THLD` | 30 m/s² | threshold on the norm of the body acceleration (before 1.18, on the forward acceleration) |
| `FW_LAUN_AC_T` | 0.05 s | how long it must last |
| `FW_LAUN_MOT_DEL` | 0 s | motor delay after detection; until then throttle = `FW_THR_IDLE` |
| `FW_TKO_AIRSPD` | −1 | climbout airspeed; ≤ 0 means `FW_AIRSPD_MIN` |
| `FW_TKO_PITCH_MIN` | 10° | minimum pitch during the climbout |
| `MIS_TAKEOFF_ALT` | 25 m (FW), 20 m (VTOL) | altitude after which Takeoff switches to Hold |
| `RWTO_TKOFF` | 0 | runway takeoff; needs `FW_W_EN` = 1 (wheel steering) |
| `RWTO_MAX_THR` / `RWTO_RAMP_TIME` | 1.0 / 2 s | ground roll throttle and its ramp-up time |
| `RWTO_ROT_AIRSPD` / `RWTO_ROT_TIME` | −1 (0.9 · `FW_TKO_AIRSPD`) / 1 s | airspeed and duration of the rotation (nose up) |
| `RWTO_PSP` / `RWTO_NUDGE` | 0° / 1 | pitch during the ground roll; nudging the wheel with the yaw stick |
| `FW_WING_SPAN` / `FW_WING_HEIGHT` | 3 / 0.5 m | near the ground the bank is limited so a wingtip does not strike |

**Safety.** With `FW_LAUN_DETCN_ON` = 0 the motor starts spinning as soon as you arm in Takeoff: if you hold the plane in your hands, the detector must be on and the propeller must point away from you. 30 m/s² for 0.05 s is about 3 g: a firm throw, not a shake. `RWTO_HDG` was removed in 1.17.

### Mission landing
The landing pattern is a `MAV_CMD_NAV_LOITER_TO_ALT` item followed by a `MAV_CMD_NAV_LAND` item; their positions define the glide slope. If it is steeper than `FW_LND_ANG` (5°, 1…45), a plane mission is rejected at upload (a VTOL does not run this check). `MIS_TKO_LAND_REQ` = 2 (the FW and VTOL default) requires a landing in every mission; the full list of values is in `px4-safety-return`.

| Parameter | Default | Meaning |
|---|---|---|
| `FW_LND_AIRSPD` | −1 | approach airspeed; ≤ 0 means `FW_AIRSPD_MIN`; below MIN only with `FW_AIRSPD_FLP_SC` < 1 |
| `FW_LND_EARLYCFG` | 0 | 1: flaps and landing airspeed already on the loiter-down circle |
| `FW_LND_FLALT` | 0.5 m | minimum flare altitude |
| `FW_LND_FL_TIME` | 1 s | the flare starts at max(`FW_LND_FLALT`, `FW_LND_FL_TIME` · descent rate) |
| `FW_LND_FL_SINK` | 0.25 m/s | sink rate in the flare, throttle down to `FW_THR_IDLE` |
| `FW_LND_FL_PMIN` / `_PMAX` | 2.5 / 15° | pitch limits in the flare |
| `FW_LND_TD_TIME` | −1 | time from flare start until the pitch is clamped to `RWTO_PSP`; −1 disables it |
| `FW_LND_USETER` | 1 | 0: no terrain; 1: terrain (rangefinder) only to trigger the flare; 2: the glide slope relative to terrain too |
| `FW_LND_ABORT` | 3 | bit 0: abort if terrain is not found; bit 1: if the terrain estimate times out |
| `FW_FLAPS_LND_SCL` / `FW_FLAPS_TO_SCL` | 1 / 0 | flap setting for landing and takeoff |

Example: an approach at 2 m/s down gives a flare at max(0.5; 1 · 2) = 2 m. A manual go-around is `MAV_CMD_DO_GO_AROUND`. Land mode on a plane is a circling descent over the current position, for emergencies only.

### Fixed-wing autotune
The `fw_autotune_attitude_control` module starts on both a plane and a VTOL. You start it with the Start AutoTune button in QGC (the `MAV_CMD_DO_AUTOTUNE_ENABLE` command; the `FW_AT_START` "button" parameter was removed in 1.18) or with a switch: `FW_AT_MAN_AUX` = n takes the `RC_MAP_AUXn` channel, and a value > 0.5 starts identification (channel setup is in `px4-rc-tuning`). A mode change or turning the switch off aborts autotune ("Autotune aborted before finishing"); the docs say moving the sticks stops it too, but the fixed-wing module code has no such check. If an axis does not converge within 30 s, the module moves on to the next one.

| Parameter | Default (1.17–1.18) | Meaning |
|---|---|---|
| `FW_AT_AXES` | 3 | bits: 0 roll, 1 pitch, 2 yaw |
| `FW_AT_APPLY` | 2 | 0: log only, 1: after disarm, 2: right away in the air |
| `FW_AT_SYSID_TYPE` | 1 Linear sine sweep | 0 Step, 2 Logarithmic sine sweep; 0 in 1.16 |
| `FW_AT_SYSID_F0` / `_F1` | 1 / 10 Hz | frequency range; `F1` = 20 in 1.16 |
| `FW_AT_SYSID_TIME` | 10 s | duration per axis |

Rule: run the first autotune with `FW_AT_APPLY` = 1, in Hold or Position, at an altitude with a margin for a stall, in wind below a third of cruise airspeed; apply "in the air" only after the first result has been checked. A VTOL is tuned in hover first (`px4-control`), then in fixed-wing flight.

### Front transition: how the code does it
The transition switch, the `MAV_CMD_DO_VTOL_TRANSITION` command or a mission item sets the "FW" request. The `MAV_CMD_DO_VTOL_TRANSITION` command (and the mission item) to FW is rejected in Takeoff, Land, RTL and Orbit; a request from the **switch** is not covered by this check (`vtol_att_control_main.cpp`). Entering RTL cancels a front transition in progress, but only at the moment of entry.

**Caution: the transition switch in Land and RTL.** If you flip the transition switch to FW during a landing or a return in multirotor mode, the firmware starts a front transition: the pusher motor goes to `VT_F_TRANS_THR` near the ground. Rule: while the vehicle is in Land or RTL (and in Takeoff), the transition switch stays in MC; before you engage Land or RTL from the radio, put the switch back to MC first; on the radio, make the transition switch a two-position one without a spring, and do not place it next to the mode switch. If RTL started as a failsafe while the switch was in FW, leave the switch alone until landing or until you take over in a manual mode. A standard VTOL (`standard.cpp`, `vtol_type.cpp`, v1.18.0) goes through it like this:

1. **Spin-up.** The pusher throttle rises at `VT_PSHER_SLEW` (0.33 1/s) to `VT_F_TRANS_THR` (1.0); with `VT_PSHER_SLEW` = 0, at once. The lift motors carry the vehicle at weight 1.
2. **Blending.** Once airspeed ≥ `VT_ARSP_BLEND` (8 m/s) and more than `VT_TRANS_MIN_TM` (2 s) has passed, the multirotor weight is w = 1 − (V − BLEND) / (TRANS − BLEND). The same w scales down the lift motor thrust; pitch moves smoothly to `FW_PSP_OFF` · (1 − w). `VT_ARSP_BLEND` = 0: by the parameter description this disables blending, but in the code (1.17 and 1.18) blending runs from `VT_TRANS_MIN_TM` on as w = 1 − V / `VT_ARSP_TRANS`, and the early "airspeed not increasing" timeout stops working, which leaves only `VT_TRANS_TIMEOUT`.
3. **Completion.** With a sensor: time > `VT_TRANS_MIN_TM` **and** V ≥ `VT_ARSP_TRANS` (10 m/s, multiplied by √(`WEIGHT_GROSS`/`WEIGHT_BASE`)). Without a sensor: time > `VT_F_TR_OL_TM` (6 s). The lift motors stop, and over 1 s throttle passes from the pusher motor to TECS.
4. **Timeout.** Quad-chute if time > `VT_TRANS_TIMEOUT` (15 s), and with a sensor even earlier: time > `VT_F_TR_OL_TM` while V is still < `VT_ARSP_BLEND`.

Without a sensor the weight changes with time: w = clamp(2 · (1 − t / `VT_TRANS_MIN_TM`), 0, 1). The lift motors start fading out at half of `VT_TRANS_MIN_TM` and are off by its end, although the vehicle becomes a fixed-wing only at `VT_F_TR_OL_TM`. That is why without a sensor `VT_TRANS_MIN_TM` comes from a reference flight instead of staying at 2 s.

All three times are multiplied by (ρ₀/ρ)^1.5, with ρ limited to 0.7…1.5 kg/m³ (`getFrontTransitionTimeFactor`): at ρ = 1.0 the factor is 1.36, and the 15 s timeout becomes 20.3 s. The firmware itself raises `VT_ARSP_TRANS` to `VT_ARSP_BLEND` and `VT_F_TR_OL_TM` to `VT_TRANS_MIN_TM` if they are set lower. A standard VTOL does not read `VT_F_TRANS_DUR` (5 s) in 1.17 and 1.18: it sets the tilt of a tiltrotor and the rotation of a tailsitter, so the docs' advice to "consider reducing the transition duration (`VT_F_TRANS_DUR`) if you are not using an airspeed sensor" does not apply to a 4+1. An "MC" request during a front transition immediately returns to hover with the pusher motor off.

{{diagram:chart-px4-vtol-transition|In the worked example the transition completes at 8.6 s, when airspeed reaches VT_ARSP_TRANS = 11.5 m/s; the pusher motor is at 0.9 already by 2.7 s, while the lift motors start losing weight only at 6.25 s, after VT_ARSP_BLEND and VT_TRANS_MIN_TM.}}

### Back transition and deceleration
An "MC" request in fixed-wing flight: the pusher motor stops at once, and the lift motor weight ramps up over `VT_B_TRANS_RAMP` (3 s, no longer than `VT_B_TRANS_DUR`). In modes with climb rate control the Transition flight task pitches the nose up to decelerate at `VT_B_DEC_MSS` (2 m/s², 0.5…10); the integrator gain `VT_B_DEC_I` (0.1) sets how aggressively. Since 1.18 in these modes the roll setpoint also moves from the fixed-wing one to the multirotor one with the same weight over `VT_B_TRANS_RAMP` (in 1.17 roll came from the fixed-wing setpoint for the whole transition). If the landing point is ahead (since 1.18 also only with a horizontal position uncertainty eph < 10 m), the deceleration setpoint is v² / (2 · d), but no more than 2 · `VT_B_DEC_MSS`. The transition ends when the speed along the body axis (from GPS, or airspeed without it) is < `MPC_XY_CRUISE` (5 m/s), or after `VT_B_TRANS_DUR` (10 s), or on the ground.

A mission starts the transition before `VTOL_LAND` at a distance R = v² / (2 · `VT_B_DEC_MSS`) (`mission_block.cpp`), where v is the groundspeed: 16 m/s and 2 m/s² give 64 m. By the code the transition already ends at 5 m/s: (16² − 5²) / 4 = 57.75 m in (16 − 5) / 2 = 5.5 s, which is less than `VT_B_TRANS_DUR`, so the timeout does not get in the way. If the real deceleration is weaker than `VT_B_DEC_MSS`, the vehicle overshoots the point; adjust it from the log.

### Tiltrotor and tailsitter
**Tiltrotor** (`tiltrotor.cpp`). Phase 1: tilt from `VT_TILT_MC` (0) to `VT_TILT_TRANS` (0.4) over `VT_F_TRANS_DUR`, thrust no less than 0.25; it completes on the same airspeed and time conditions **and** tilt ≥ `VT_TILT_TRANS`. Phase 2: tilt to `VT_TILT_FW` (1.0) over `VT_TRANS_P2_DUR` (0.5 s). Back: after 0.5 s of throttle ramp-down the motors tilt up to `VT_TILT_MC` over `VT_BT_TILT_DUR` (1 s); it ends when the tilt is back and (speed < `MPC_XY_CRUISE` or time > `VT_B_TRANS_DUR`). The tilt 0…1 is normalized; the angles come from `CA_SV_TLn_MINA/MAXA` (`px4-outputs-servos`). An "FW" request during the back transition immediately returns to fixed-wing mode.

**Tailsitter** (`tailsitter.cpp`): a 90° rotation at a rate of (π/2) / `VT_F_TRANS_DUR`; back until the pitch rises above −15° or `VT_B_TRANS_DUR` runs out. Differential thrust in fixed-wing flight, `VT_FW_DIFTHR_EN` (bits 0 yaw, 1 roll, 2 pitch; default 0) with the factors `VT_FW_DIFTHR_S_R/P` 1.0 and `_S_Y` 0.1, works on a tailsitter and a tiltrotor (on a tiltrotor yaw only).

### Quad-chute: the conditions from the source
Quad-chute is a forced switch to hover. The checks run in fixed-wing flight and in both transitions, only when the vehicle is armed, not landed and below `VT_FW_QC_HMAX` (0 means no limit; height above ground from a rangefinder, otherwise above home, otherwise above the local origin), `vtol_type.cpp:207–229`. The order of the checks (`getQuadchuteReason`, lines 344–371):

| Reason | Parameter (default) | Condition in the code | Message |
|---|---|---|---|
| Minimum altitude | `VT_FW_MIN_ALT` (0 = off) | altitude above the local origin < threshold | "…minimum altitude breach" |
| Uncommanded descent | `VT_QC_ALT_LOSS` (0) | altitude-controlled mode, the vehicle is below the TECS reference and has lost more than the threshold from the highest altitude reached since it went below the reference | "…uncommanded descent detection" |
| Altitude loss in transition | `VT_QC_T_ALT_LOSS` (**20 m**) | front transition or 5 s after it, altitude-controlled mode, more than the threshold below the altitude at transition start | "…loss of altitude during transition" |
| Pitch | `VT_FW_QC_P` (0) | absolute pitch > threshold, deg | "…maximum pitch angle exceeded" |
| Roll | `VT_FW_QC_R` (0) | absolute roll > threshold, deg | "…maximum roll angle exceeded" |
| Transition timeout | `VT_TRANS_TIMEOUT`, `VT_F_TR_OL_TM` | see step 4 of the front transition | "…transition timeout" |
| External command | — | `MAV_CMD_DO_VTOL_TRANSITION`, param1 = MC, param2 = 1 | "…external command" |

Out of the box only the timeout and the altitude loss in transition are active. `VT_FW_MIN_ALT`, `VT_FW_QC_P`, `VT_FW_QC_R` also apply in the back transition (on a tailsitter, since 1.18, the pitch and roll limits are checked only in fixed-wing mode and in the fixed-wing frame): the deceleration pitch must stay below `VT_FW_QC_P`, and a back transition below `VT_FW_MIN_ALT` triggers quad-chute by itself.

**What happens next.** The `fixed_wing_system_failure` flag is set: a standard VTOL goes to hover at once with the pusher at 0; QGC shows "Quad-chute triggered". Commander applies `COM_QC_ACT` (0 Return, −1 Warning only, 1 Land, 2 Hold) only if the pilot was in Mission, Hold, Takeoff or VTOL Takeoff (`failsafe.cpp:575–582`); in Position, Altitude and Stabilized the vehicle simply stays a multirotor in the same mode. A VTOL Return in hover flies like a multirotor (`px4-safety-return`). The flag stays until the next request to transition to FW, and on the ground it blocks arming: "VTOL fixed-wing system failure detected. Verify reason for failure, and reboot the vehicle once confirmed safe".

**What quad-chute will not save.** A failure of the lift motors or their power: there is nothing to switch to. Too little battery to hover: hovering at cruise altitude far from home is the most expensive mode in energy, hence `VT_FW_QC_HMAX` and a battery reserve. A stall below the altitude at which the multirotor can still stop the fall. A wrong surface direction: in hover the surfaces are locked, but by the time quad-chute fires the vehicle may already be upside down. An attitude sensor failure: both halves fly on the same estimate.

### VTOL hover: surfaces, forward thrust, weathervane
- `VT_ELEV_MC_LOCK` = 1 (default; 0 on a tailsitter): in hover the surfaces stay locked. So you can check their direction only in fixed-wing mode; on the bench without arming the transition to FW completes at once (`can_transition_on_ground`), and arming in fixed-wing mode is not allowed (`CBRK_VTOLARMING`, `px4-safety-return`).
- `VT_FWD_THRUST_EN` (0; 1 except landing, 2/3 above `MPC_LAND_ALT1/2`, 4 always, 5/6 above ALT1/2 and except landing) and `VT_FWD_THRUST_SC` (0.7): when the hover controller wants to pitch the nose below `VT_PITCH_MIN` (0°, −5° before 1.18; during a landing `VT_LND_PITCH_MIN`, 0°, −5° before 1.18), the rest of the forward acceleration goes to the pusher motor, up to 0.9, and the nose is held at `VT_PITCH_MIN` (before 1.18 no lower than 0° whatever the parameter); since 1.18 a pusher command below 0.02 in hover means a stopped motor. The nose does not dip into the wind, and the wing does not push the vehicle down. Only in modes with climb rate control.
- `WV_EN` (0 as a parameter, 1 on a VTOL), `WV_ROLL_MIN` 1°, `WV_GAIN` 1 Hz, `WV_YRATE_MAX` 90 deg/s: in Position and in auto modes the nose turns into the wind instead of the automatic heading, in auto modes only while the navigator gives no heading of its own: a waypoint heading (param4 of the item), an ROI, heading alignment before a transition or on mission resume win over the wind, and weathervane is off for that leg (`FlightTaskAuto.cpp`).
- `NAV_FORCE_VT` = 1: a mission `NAV_LAND` item and Descend mode in fixed-wing flight are flown as a transition to hover; 0 means a fixed-wing landing.
- `VT_SPOILER_MC_LD` (0): the spoiler setting for a landing in hover.

### First values: rules for choosing
| What to choose | Rule | Why | Check after the flight |
|---|---|---|---|
| `VT_ARSP_TRANS` | = `FW_AIRSPD_MIN` (≥ 1.25 V_s) | lower than that, the vehicle becomes a fixed-wing with less than 25 % margin above the stall; the firmware does not check this | after the transition completed, airspeed did not drop below `FW_AIRSPD_MIN` and the altitude held |
| `VT_ARSP_BLEND` | 1.1 V_s, rounded up to 0.5, no closer than 1 m/s to TRANS | below V_s the wing does not carry the weight, so the lift motors need full thrust | in the log the weight w fell smoothly, without an altitude drop |
| `VT_F_TRANS_THR`, `VT_PSHER_SLEW` | the first time, high throttle (0.9–1.0) and the default slew | the docs: "better off setting the value higher than lower"; a slow spin-up stays longer in the transition | the transition time is comfortably shorter than `VT_F_TR_OL_TM` |
| `VT_F_TR_OL_TM` | with a sensor: time to `VT_ARSP_BLEND` × 1.5; without: transition time of the reference flight × 1.3 | with a sensor this is the "airspeed not increasing" timeout, without one it is when the lift motors stop | with a sensor, a margin of ≥ 2 s before it fires |
| `VT_TRANS_TIMEOUT` | ≥ `VT_F_TR_OL_TM` + 3 s | otherwise, without a sensor, the timeout fires before completion | — |
| `VT_FW_MIN_ALT` | 15–20 m, and at least 10 m below the transition start altitude | time for the multirotor to stop a fall; a transition below the threshold triggers quad-chute by itself | not a single false trigger on the approach |
| `VT_FW_QC_R` | `FW_R_LIM` + 15° | above any commanded bank with a margin for gusts | the maximum absolute roll in the log is 10° below the threshold |
| `VT_FW_QC_P` | the larger of `FW_P_LIM_MAX` and the absolute value of `FW_P_LIM_MIN`, plus 15° | above the commanded angles and the deceleration pitch | the maximum absolute pitch, including the back transition, is 10° below |
| `VT_QC_ALT_LOSS` | 15–20 m | more than the normal altitude error in a turn and a climb | the largest TECS altitude error in the log is less than half the threshold |
| `COM_QC_ACT` | 0 Return (default) or 1 Land over a safe field | the battery must last for a hover back home | hover consumption from the log × time to home < the remaining charge |

The rules for `VT_ARSP_BLEND`, `VT_F_TR_OL_TM`, `VT_TRANS_TIMEOUT` and the quad-chute thresholds are this module's engineering estimate; the rule for `VT_FW_MIN_ALT` and the 30 % margin come from the PX4 docs on flying without an airspeed sensor.

**Field safety.** Do the first transition no lower than 20 m (PX4 docs: "at least 20 meters above ground"), into the wind, from a stable hover, with 50–100 m of room to accelerate. Before the flight, have a plan for each of the three phases: what you do if something goes wrong in hover, in the transition, in fixed-wing flight. The battery needs a reserve for hovering at landing.

### PX4 and ArduPlane: concept mapping
| Concept | PX4 1.18 | ArduPlane 4.7 |
|---|---|---|
| Enable VTOL | airframe 13000 / 13100 / 13200, `VT_TYPE` | `Q_ENABLE`, `Q_TILT_ENABLE`, `Q_TAILSIT_ENABLE` |
| Envelope | `FW_AIRSPD_STALL/MIN/TRIM/MAX` | `AIRSPEED_STALL`, `AIRSPEED_MIN`, `AIRSPEED_CRUISE`, `AIRSPEED_MAX` |
| Use the sensor | `FW_USE_AIRSPD` | `ARSPD_USE` |
| End of transition | `VT_ARSP_TRANS` or `VT_F_TR_OL_TM` | `AIRSPEED_MIN` or `Q_TRANSITION_MS` |
| Transition failure | `VT_TRANS_TIMEOUT` → quad-chute, `COM_QC_ACT` | `Q_TRANS_FAIL`, `Q_TRANS_FAIL_ACT` |
| Back transition deceleration | `VT_B_DEC_MSS` | `Q_TRANS_DECEL` |
| Lift motor assistance | none; only quad-chute (a mode change) | `Q_ASSIST_SPEED`, `Q_ASSIST_ANGLE`, `Q_ASSIST_ALT` (no mode change) |
| Forward thrust in hover | `VT_FWD_THRUST_EN/SC` | `Q_FWD_THR_USE`, `Q_FWD_THR_GAIN` |
| Weathervane | `WV_EN` | `Q_WVANE_ENABLE` |
| Bank limit | `FW_R_LIM` | `ROLL_LIMIT_DEG` |
| Launch detector | `FW_LAUN_AC_THLD` | `TKOFF_THR_MINACC` |

The main difference: in ArduPlane the lift motors help the wing without a mode change, while PX4 only has a full switch to hover. ArduPlane setup is in `ap-setup-plane` and `ap-quadplane`.

### Place in the system

- **Takes in:** V_s from mass, wing area and C_Lmax (`aero-wing`) and the CG (`aero-stability`); the validated airspeed `airspeed_validated` (`px4-hardware-peripherals`); outputs and surface signs (`px4-outputs-servos`); the transition switch (`px4-rc-tuning`).
- **Gives out:** the `FW_AIRSPD_*` envelope to TECS and to surface scaling; the quad-chute flag to commander, which picks `COM_QC_ACT` and Return (`px4-safety-return`); transition thresholds and times to the first flight's log.
- **If you get it wrong here:** `VT_ARSP_TRANS` below 1.2 V_s → once the lift motors stop the wing stalls, quad-chute fires on altitude loss, and the log gets "loss of altitude during transition" (`px4-safety-return`). `FW_AIRSPD_TRIM` above the real cruise → s = TRIM/V > 1, the P part on the surfaces is boosted s² times → the surfaces act more sharply than designed, with roll oscillation at cruise (`px4-control`).

## practice
Four exercises on paper or with a calculator; all the numbers were computed by a script and are given in the reference. Air density ρ = 1.225 kg/m³, g = 9.81 m/s², parameter airspeeds are rounded up to 0.5 m/s.

### Step 1. Envelope from mass and wing
A standard VTOL: mass 4.5 kg, wing area 0.75 m², C_Lmax = 1.2, `FW_R_LIM` = 50°. Level airspeed at full throttle in calm air is 24 m/s.

(a) V_s by the formula from `aero-wing`. (b) `FW_AIRSPD_STALL`, `FW_AIRSPD_MIN`, `FW_AIRSPD_TRIM`, `FW_AIRSPD_MAX` by the rules in "Airspeed envelope". (c) The load factor and stall speed in a 50° and a 30° bank; the minimum airspeed TECS will hold in a 50° bank. (d) `VT_ARSP_TRANS` and `VT_ARSP_BLEND` from the first values table. (e) With a payload the mass became 5.4 kg, `WEIGHT_BASE` = 4.5, `WEIGHT_GROSS` = 5.4: at what airspeed will the transition complete?

Result. (a) V_s = √(2 · 4.5 · 9.81 / (1.225 · 0.75 · 1.2)) = √80.08 = **8.95 m/s**. (b) STALL = **9.0**; MIN: 1.25 · 8.95 = 11.19 → **11.5**; TRIM: 1.5 · 8.95 = 13.42, but 11.5 · 1.247 = 14.34 → max → **14.5**; MAX: 0.9 · 24 = 21.6 → down to 0.5 → **21.5**. (c) 50°: n = 1/cos 50° = **1.556**, V_s(50°) = 8.95 · 1.247 = **11.16 m/s**; 30°: n = **1.155**, V_s = **9.62 m/s**; TECS in a 50° bank: 11.5 · 1.247 = **14.34 m/s**. (d) TRANS = MIN = **11.5**; BLEND: 1.1 · 8.95 = 9.84 → **10.0** (1.5 m/s below TRANS, so the rule holds). (e) 11.5 · √(5.4/4.5) = **12.60 m/s**.

### Step 2. Transition timeline
Parameters (a worked example, assembled by hand):
```
VT_ARSP_BLEND     10.0
VT_ARSP_TRANS     11.5
VT_TRANS_MIN_TM    4.0
VT_F_TR_OL_TM      8.0
VT_TRANS_TIMEOUT  15.0
VT_PSHER_SLEW      0.33
VT_F_TRANS_THR     0.9
VT_B_DEC_MSS       2.0
VT_B_TRANS_DUR    10.0
MPC_XY_CRUISE      5.0
```
Airspeed after flipping the switch (ρ = 1.225, time factor 1):

| t, s | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| V, m/s | 0 | 1.5 | 3.5 | 5.5 | 7.2 | 8.6 | 9.8 | 10.6 | 11.2 | 11.7 | 12.1 |

Find, treating airspeed as linear between samples: (a) when the pusher motor reaches its target throttle; (b) when blending starts, and the weight w at 7 and 8 s; (c) when the transition completes; (d) the same without an airspeed sensor (`FW_USE_AIRSPD` = 0): when the lift motors lose their weight and when the vehicle becomes a fixed-wing; (e) variant B, a weak pusher motor, at 8.0 s V = 9.2 m/s: what happens, and when; (f) variant C, no sensor and `VT_F_TR_OL_TM` = 18: what happens; (g) a back transition from a groundspeed of 16 m/s: at what distance before the landing point the mission starts it, and when and where it ends by the code.

### Step 3. Surface signs and a reversed servo
The sign convention and the `CA_SV_CSn_TRQ_*` coefficients are derived in `px4-outputs-servos` (practice step 3, airframes 3000 and 2100): a positive command is trailing edge (TE) up, rudder to the right; elevons: left = −roll + pitch, right = +roll + pitch.

(a) Fill in the table for a standard VTOL with ailerons and for a wing with elevons: roll stick right, pitch stick back, yaw stick right (Manual); in Stabilized, push the nose down by hand, push the right wing down by hand.

(b) Wing geometry (a worked example, assembled by hand):
```
CA_SV_CS_COUNT   2
CA_SV_CS0_TYPE   5
CA_SV_CS0_TRQ_R  0.5
CA_SV_CS0_TRQ_P  0.5
CA_SV_CS1_TYPE   6
CA_SV_CS1_TRQ_R  0.5
CA_SV_CS1_TRQ_P  0.5
PWM_AUX_FUNC5    201
PWM_AUX_FUNC6    202
PWM_AUX_REV      0
```
Find the geometry error. (c) The geometry was fixed. On the bench, after a transition to FW without arming, in Manual you see: roll right gives both TEs down; pitch back gives the left TE up and the right TE down. Which servo is reversed, and what number goes into `PWM_AUX_REV`?

### Step 4. Three errors in a parameter file
The owner plans to do the first flights without a sensor and enable it later (a worked example, assembled by hand). Reference flight with the sensor: the transition took 8.6 s, as in step 2. V_s = 9.0 m/s.
```
FW_AIRSPD_STALL    9.0
FW_AIRSPD_MIN     11.5
FW_AIRSPD_TRIM    14.5
FW_R_LIM          50
FW_USE_AIRSPD      0
SYS_HAS_NUM_ASPD   0
VT_ARSP_BLEND      8.0
VT_ARSP_TRANS      9.5
VT_TRANS_MIN_TM    2.0
VT_F_TR_OL_TM      3.0
VT_TRANS_TIMEOUT  15.0
VT_FW_MIN_ALT      0
VT_QC_ALT_LOSS     0
VT_QC_T_ALT_LOSS   0
VT_FW_QC_P         0
VT_FW_QC_R         0
COM_QC_ACT         0
NAV_FORCE_VT       1
WV_EN              1
```
Find three errors, and for each one give the rule from the theory and the corrected value.

Self-check: the lab is done when:
- step 1: V_s = 8.95 ± 0.02 m/s; STALL 9.0, MIN 11.5, TRIM 14.5, MAX 21.5 exactly; n 1.556 and 1.155 ± 0.002; V_s in a turn 11.16 and 9.62 ± 0.02 m/s; 14.34 ± 0.02 m/s; TRANS 11.5, BLEND 10.0; 12.60 ± 0.02 m/s;
- step 2: 2.73 ± 0.02 s; 6.25 ± 0.02 s, w = 0.60 and 0.20; 8.60 ± 0.02 s; without a sensor, the weight goes from 2.0 s down to 0 by 4.0 s, fixed-wing at 8.0 s; variant B, quad-chute on the timeout at 8.0 s; variant C, quad-chute at 15.0 s; 64.0 m, 5.5 s, 57.75 ± 0.1 m;
- step 3: all ten table cells match the reference; the error is the sign of `CA_SV_CS0_TRQ_R`; AUX6 is reversed, `PWM_AUX_REV` = 32;
- step 4: exactly the three errors from the reference are found, each with a value corrected by its rule.

**Reference for the self-check.**

| Step | Correct result | Typical mistake and its cause |
|---|---|---|
| 1 | see the step 1 "Result" | TRIM 13.5: the turn was not checked, and at 50° TECS will demand 14.34 m/s; V_s in a turn 13.9: the load factor was used without the square root |
| 2a | 0.9 / 0.33 = 2.73 s | 3.0 s: the slew was read as "3 s to full throttle", while the target throttle is 0.9 |
| 2b | V = 10.0 between 6 and 7 s: 6 + (10 − 9.8)/0.8 = 6.25 s (t > 4 s holds); w(7) = 1 − 0.6/1.5 = 0.60; w(8) = 1 − 1.2/1.5 = 0.20 | blending from 4 s: the V ≥ BLEND condition was forgotten |
| 2c | V = 11.5 between 8 and 9 s: 8 + 0.3/0.5 = 8.60 s | 9 s: the first whole sample above 11.5 was taken |
| 2d | w = clamp(2 · (1 − t/4)): 1 until 2 s, 0.5 at 3 s, 0 at 4 s; fixed-wing at 8.0 s | "the lift motors run until 8 s": without a sensor the weights are counted from `VT_TRANS_MIN_TM` |
| 2e | at 8.0 s time > OL while V = 9.2 < BLEND 10 → quad-chute "transition timeout", hover, in Mission `COM_QC_ACT` | "quad-chute at 15 s": the early check with a sensor was forgotten |
| 2f | OL 18 > TIMEOUT 15: quad-chute at 15.0 s, the transition never completes | "fixed-wing at 18 s": the timeout fires before completion |
| 2g | R = 16²/(2 · 2) = 64.0 m; down to 5 m/s in 5.5 s over 57.75 m; 5.5 < 10, so the timeout does not interfere | 72 m: a deceleration of 4 m/s² was used; an end at zero speed (64 m): the transition ends at `MPC_XY_CRUISE` |
| 3a | Ailerons: roll right, left TE down, right TE up; elevator, stick back, TE up; yaw right, rudder right. Elevons: roll right, left down, right up; stick back, both up. Stabilized: nose down → elevator (both elevons) TE up; right wing down → a left roll is needed → left TE up, right TE down | in Stabilized the surfaces were deflected "in the direction of the tilt": the loop counters the tilt, it does not follow it |
| 3b | `CA_SV_CS0_TRQ_R` = 0.5 on the left elevon, it must be −0.5: with identical rows roll and pitch cannot be told apart | "the error is in `PWM_AUX_REV`": mechanics are fixed with REV, while the geometry sign follows from the rule |
| 3c | The right elevon must go up for roll right and up for stick back; you see the opposite in both cases → AUX6 → bit 5 → `PWM_AUX_REV` = 32 | 64: bit n−1 is output n; "the left one is reversed": both of its motions are correct |
| 4 | (1) `VT_ARSP_TRANS` 9.5 < `FW_AIRSPD_MIN` 11.5 (1.06 V_s): once the sensor is enabled the transition ends almost at stall speed; fix it to 11.5. (2) All quad-chute thresholds are off, including `VT_QC_T_ALT_LOSS` (default 20): nothing catches a stall in the transition, and without a sensor that is the main risk; `VT_QC_T_ALT_LOSS` 20, `VT_FW_MIN_ALT` 15–20, `VT_FW_QC_R` 65. (3) Without a sensor `VT_F_TR_OL_TM` = 3.0: the vehicle becomes a fixed-wing at 3 s, while it really took 8.6 s to accelerate; `VT_TRANS_MIN_TM` = 2 fades the lift motors out by 2 s. Fix: `VT_TRANS_MIN_TM` ≈ 8.6 · 1.3 = 11.2; the firmware would then raise `VT_F_TR_OL_TM` to 11.2, so set 11.2 explicitly, and `VT_TRANS_TIMEOUT` ≥ 14.2 (15 works) | "`VT_ARSP_BLEND` 8 is below V_s": by the rule BLEND ≈ 1.1 V_s = 10, but this is not an error that prevents flight; "`NAV_FORCE_VT` = 1 is wrong": it means landing in hover, the default |

### Moving to real hardware
Propellers stay off until item 7. Servos are powered from a separate BEC.

1. Steps 1–5, 8–10 and 13 as in `px4-setup-scratch`; the airframe from this module's table; a backup `00_defaults.params`.
2. Outputs and timer groups as in `px4-outputs-servos`; motors one at a time with a slider at 10 %, order and direction against the Actuators geometry. Pusher motor: propeller off, ESC calibrated, throttle from QGC; make sure the slider really drives the pusher motor.
3. Surfaces: transition to FW without arming (switch), `COM_PREARM_MODE` = 2 for the duration of the check; the step 3 table for your layout in Manual and Stabilized; fix only with `PWM_*_REV`. Restore `COM_PREARM_MODE`.
4. Airspeed sensor: calibrate as in `px4-hardware-peripherals`; blow into the tube, and the airspeed in `listener airspeed_validated` goes up.
5. Transition check on the bench: without arming, flip the switch FW ↔ MC; the messages and `vtol_vehicle_status` change, and the surfaces lock in MC with `VT_ELEV_MC_LOCK` = 1.
6. Envelope and thresholds from the first values table, with your vehicle's numbers; the `.params` go into the repository.
7. Field: propellers back on; hover in Position for 2 min (tuning per `px4-control`); transition at 20 m or higher, into the wind; 2–3 circuits as a fixed-wing in Hold; back transition on a straight leg.
8. After the flight: the ULog, the checks from the first values table, `01_after_first_transition.params`.

Hardware criteria: the surface table matched in Manual and Stabilized; the transition completed without quad-chute, and the altitude dropped by less than half of `VT_QC_T_ALT_LOSS` during it; the maximum absolute roll and pitch are 10° below the thresholds; airspeed after the transition never dropped below `FW_AIRSPD_MIN`. These criteria are for the bench and the field and are not part of the self-check above.

## diagnostics
- **Symptom:** QGC shows "Invalid configuration: FW_AIRSPD_STALL higher FW_AIRSPD_MIN".
  - Possible cause: `FW_AIRSPD_STALL` > `FW_AIRSPD_MIN`, often after recalculating V_s without recalculating MIN.
  - What to do: MIN = 1.25 V_s, TRIM and `VT_ARSP_TRANS` by the same rules.
- **Symptom:** "Quad-chute triggered due to transition timeout" on every transition.
  - Possible cause: with a sensor, airspeed did not reach `VT_ARSP_BLEND` within `VT_F_TR_OL_TM`; without a sensor, `VT_F_TR_OL_TM` > `VT_TRANS_TIMEOUT`; at high elevation all the times grew by a factor of (ρ₀/ρ)^1.5.
  - What you see in the log: `airspeed_validated.calibrated_airspeed_m_s` rises slowly, the pusher throttle is at `VT_F_TRANS_THR`.
  - What to do: raise `VT_F_TRANS_THR` or `VT_F_TR_OL_TM`, keep `VT_TRANS_TIMEOUT` ≥ OL + 3 s, check the airspeed sensor.
- **Symptom:** during a landing or a return (Land, RTL) the vehicle suddenly spins up the pusher motor and starts a front transition.
  - Possible cause: the transition switch was moved to (or left in) FW: a switch request is not blocked in Land and RTL, only the MAVLink command is rejected; the cancellation on RTL works only at the moment RTL is entered.
  - What you see in the log: `vtol_vehicle_status` goes into a transition while `vehicle_status.nav_state` is Land or RTL; `manual_control_switches.transition_switch` = FW.
  - What to do: put the switch back to MC; from now on keep it in MC the whole time the vehicle is in Land, RTL or Takeoff.
  - Consequences: spin-up near the ground, leaving the landing zone, quad-chute at low altitude.
- **Symptom:** without a sensor the vehicle sags right after the transition starts.
  - Possible cause: `VT_TRANS_MIN_TM` = 2 s by default: the lift motors lose their weight by 2 s, before there is any airspeed.
  - What to do: `VT_TRANS_MIN_TM` from the reference flight + 30 %.
  - Consequences: with `VT_QC_T_ALT_LOSS` = 0 nothing catches the sag.
- **Symptom:** "Quad-chute triggered due to maximum pitch angle exceeded" during the back transition.
  - Possible cause: the deceleration pitch is above `VT_FW_QC_P`; the check also applies in the back transition.
  - What to do: set `VT_FW_QC_P` 10° above the maximum deceleration pitch in the log, or reduce `VT_B_DEC_I`.
- **Symptom:** after a quad-chute it will not arm on the ground: "VTOL fixed-wing system failure detected".
  - Possible cause: the `fixed_wing_system_failure` flag stays until a new request to transition to FW.
  - What to do: find the cause in the log (the message names it), reboot the vehicle.
- **Symptom:** in Position after a quad-chute the vehicle hovers in place, and Return did not start.
  - Possible cause: `COM_QC_ACT` applies only in Mission, Hold, Takeoff and VTOL Takeoff.
  - What to do: this is how the code works; in manual modes the pilot selects Return.
- **Symptom:** in hover the surfaces do not move when you tilt the vehicle.
  - Possible cause: `VT_ELEV_MC_LOCK` = 1, which is how it should be.
  - What to do: check the surfaces in fixed-wing mode (a transition on the bench without arming).
- **Symptom:** the motor does not start on a throw; or it starts right on arming while you hold the plane.
  - Possible cause: `FW_LAUN_AC_THLD` is above the real throw; or `FW_LAUN_DETCN_ON` = 0.
  - What you see in the log: `launch_detection_status.launch_detection_state` stays in waiting.
  - What to do: enable the detector; keep the threshold no lower than 2 g, so that shaking does not start the motor.
- **Symptom:** a plane or VTOL mission is rejected at upload.
  - Possible cause: no landing with `MIS_TKO_LAND_REQ` = 2; for a plane without VTOL also a glide slope steeper than `FW_LND_ANG` ("Mission rejected: the landing glide slope is steeper than the vehicle setting of …"), a check a VTOL does not run.
  - What to do: add a landing or (on a plane) move the `LOITER_TO_ALT` point farther out.
- **Symptom:** the VTOL overshoots the landing point in the back transition.
  - Possible cause: the real deceleration is lower than `VT_B_DEC_MSS`; a tailwind.
  - What to do: compute the average deceleration from the log and put it into `VT_B_DEC_MSS`; approach into the wind.

## checklist
- The airframe was chosen from the type table, and the geometry matches the vehicle.
- `FW_AIRSPD_STALL/MIN/TRIM/MAX` were computed from V_s by the rules, and TRIM was checked for a turn at `FW_R_LIM`.
- `VT_ARSP_TRANS` ≥ `FW_AIRSPD_MIN`, `VT_ARSP_BLEND` ≈ 1.1 V_s.
- `VT_TRANS_TIMEOUT` ≥ `VT_F_TR_OL_TM` + 3 s; without a sensor, `VT_TRANS_MIN_TM` comes from the reference flight.
- The quad-chute thresholds are set, `VT_FW_MIN_ALT` is below the transition start altitude; `COM_QC_ACT` is chosen.
- The surfaces were checked in Manual and Stabilized after a transition on the bench, with the propellers off and the servos on a BEC.
- The pusher motor was checked without a propeller; with `FW_LAUN_DETCN_ON` = 0 the motor starts on arming, and this is accounted for.
- The transition switch is a two-position switch and sits in MC at takeoff, before Land and RTL and through the whole landing: the switch does not block a transition in these modes.
- First transition: ≥ 20 m, into the wind, a plan for the three phases, a battery reserve for hover.
- The ULog of the first transition and both `.params` files are saved.

## references
- PX4 v1.18.0 source, vtol_att_control/vtol_type.cpp (transition completion, quad-chute) | https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.18.0/src/modules/vtol_att_control/vtol_type.cpp | primary | A
- PX4 v1.18.0 source, vtol_att_control/standard.cpp (standard VTOL transition) | https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.18.0/src/modules/vtol_att_control/standard.cpp | primary | A
- PX4 v1.18.0 source, vtol_att_control/vtol_att_control_params.yaml | https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.18.0/src/modules/vtol_att_control/vtol_att_control_params.yaml | primary | A
- PX4 v1.18.0 source, fw_performance_model/performance_model_params.yaml (envelope) | https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.18.0/src/lib/fw_performance_model/performance_model_params.yaml | primary | A
- PX4 v1.18.0 source, fw_mode_manager/fw_mode_manager_params.yaml (takeoff, landing) | https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.18.0/src/modules/fw_mode_manager/fw_mode_manager_params.yaml | primary | A
- PX4 v1.18.0 source, fw_rate_control/FixedwingRateControl.cpp (airspeed scaling) | https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.18.0/src/modules/fw_rate_control/FixedwingRateControl.cpp | primary | A
- PX4 User Guide, Generic Standard VTOL (QuadPlane) Configuration & Tuning (transition tuning) | https://docs.px4.io/main/en/config_vtol/vtol_quad_configuration.html | primary | A
- PX4 User Guide, VTOL Without an Airspeed Sensor | https://docs.px4.io/main/en/config_vtol/vtol_without_airspeed_sensor.html | primary | A
- PX4 User Guide, Safety (Failsafe) Configuration: Quad-chute Failsafe | https://docs.px4.io/main/en/config/safety.html | primary | A
- PX4 User Guide, Mission Mode (Fixed-Wing): Mission Landing | https://docs.px4.io/main/en/flight_modes_fw/mission.html | primary | A

## notes
The firmware was not built or run in this pass: the transition and quad-chute behavior comes from reading the v1.18.0 source (differences from v1.17.0 are marked in the text), the docs from the `docs/en` directory of the same tag. Discrepancies between the docs and the code: the advice to reduce `VT_F_TRANS_DUR` without a sensor does not apply to a standard VTOL (`standard.cpp` does not read it); safety.md describes `VT_FW_MIN_ALT` as "above Home", while the code and the parameter description use the local origin. The parameters `VT_TILT_SPINUP`, `VT_FW_PERM_STAB`, `VT_MC_ON_FMU`, `VT_FW_ALT_ERR`, `VT_QC_HR_ERROR_I` do not exist in 1.15.4, 1.16.2, 1.17.0 or 1.18.0. The airspeed margins over V_s come from `aero-wing`; the other choice rules are marked as engineering estimates.
