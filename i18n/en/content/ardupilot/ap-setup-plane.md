---
id: ap-setup-plane
title: "ArduPlane from scratch: servos, control surfaces, airspeed, fixed-wing failsafe"
level: L2
readingTime: 65 min
firmware: ArduPlane 4.7 (checked against 4.7.3)
status: published
tags:
  - ArduPilot
  - ArduPlane
  - setup from scratch
  - airspeed
  - failsafe
  - elevons
related:
  - ap-setup-scratch
  - ap-outputs
  - ap-aux-tune
  - ap-plane-tuning
  - ap-quadplane
  - ap-safety-fs
  - aero-stability
  - aero-wing
  - inav-setup-wing
  - f-safety
  - ap-logs
  - ap-intro
next:
  - ap-plane-tuning
source: content/ardupilot/ap-setup-plane.md
source_hash: 9b2e650f6973
---

## summary
A plane on ArduPlane 4.7, from a blank flight controller to the first flight, in a 17-step order: output functions for a conventional tail, elevons and a V-tail, the `MIXING_GAIN` mixer, two checks of control surface direction (the stick in MANUAL and the response to tilting in FBWA), trimming, modes, throttle, the `ARSPD_*` airspeed sensor and flying without one, the airspeed and angle limits, the fixed-wing failsafe with tables of actions by current mode, arming, hand, bungee and runway takeoffs, and a plan for the first flight. The module is theoretical: the practice consists of calculations and reading parameter files with no flight controller and no SITL. The lab: surface pulse widths of three planes through the mixer, the RC failsafe timeline in five scenarios, an `ARSPD_RATIO` correction, and three mistakes in a parameter file.

## theory
### How setting up a plane differs from a copter
The common steps (firmware, ports, receiver, radio calibration, accelerometer, compass, battery monitor, OSD) are done as in `ap-setup-scratch`, except that the firmware file is `arduplane_with_bl.hex` and then `arduplane.apj`. Everything that has to do with the air is different:

- the frame has no motors: each output is assigned a control surface function, and the direction of each servo is checked twice;
- a plane has a stall speed, so you set airspeed and bank limits, and the failsafe does not "hover in place" but circles and returns;
- in automatic modes TECS controls the throttle, with an airspeed sensor or without one;
- takeoff is a throw or a ground roll, and the motor can start by itself.

{{lesson:ap-ahrs-choice|How a plane estimates wind and airspeed, when ArduPlane falls back to DCM, and why without an airspeed sensor the position error without GPS grows several times over.}}

Version: ArduPlane 4.7, checked against the 4.7.2 source (`ArduPlane/version.h`: "ArduPlane V4.7.2"). The differences between 4.7 and 4.6.3 in this topic: `FS_SHORT_TIMEOUT` was removed; `ARMING_SKIPCHK` replaces `ARMING_CHECK` (opposite meaning, table in `ap-intro`); the new AUTOLAND mode (number 26) and the "AUTOLAND" values in the failsafe actions; the new `TKOFF_THR_IDLE`. The airspeed and angle names with explicit units appeared earlier, in 4.5; the old names are given once below, because old guides and other people's parameter files are full of them.

Which firmware to take for a first wing: INAV is simpler and runs on cheap FPV flight controllers (`inav-setup-wing`); ArduPlane is for when you need missions, detailed logs, an airspeed sensor, a QuadPlane. In both cases the first aircraft is a 900–1100 mm foam flying wing or a high-wing pusher: they forgive a rough landing.

### The 17 steps and where each one is done
| # | Step | What it is in ArduPlane 4.7 | Where | Details |
|---|---|---|---|---|
| 1 | Firmware, backup | `arduplane_with_bl.hex`, then `.apj`; a `.param` before any change | bench | `ap-setup-scratch` |
| 2 | Layout, board orientation | `SERVOn_FUNCTION`, `AHRS_ORIENTATION` | bench | this module, `ap-outputs` |
| 3 | Ports | `SERIALn_PROTOCOL` | bench | `ap-setup-scratch` |
| 4 | Receiver | `SERIALn_PROTOCOL = 23`, `RC_PROTOCOLS`, bind | bench | `link-elrs` |
| 5 | Channels | `RCMAP_*`, `RCn_MIN/MAX/TRIM`, `RCn_REVERSED` | bench | this module |
| 6 | Throttle output | `SERVO3_MIN/MAX`, `THR_MIN/MAX`, `THR_SLEWRATE` | bench, prop off | this module |
| 7 | Surface direction | `SERVOn_REVERSED`, MANUAL and FBWA | bench | this module |
| 8 | ESC | range calibration of a PWM ESC | bench, prop off | this module |
| 9 | Accelerometer, level, compass | `AHRS_TRIM_X/Y`, `PTCH_TRIM_DEG` | bench | `ap-setup-scratch` |
| 10 | Battery monitor | `BATT_*` | bench | `ap-setup-scratch` |
| 11 | Modes, arming | `FLTMODE_CH`, `FLTMODE1..6`, `ARMING_*` | bench | this module |
| 12 | Failsafe | `THR_FAILSAFE`, `FS_SHORT_ACTN`, `FS_LONG_ACTN`, `BATT_FS_*` | bench, prop off | this module |
| 13 | OSD | `OSD_TYPE` | bench | `ap-osd-video` |
| 14 | GPS, home, return, airspeed | `RTL_ALTITUDE`, `RTL_RADIUS`, `ARSPD_*`, `AIRSPEED_*` | bench, field | this module |
| 15 | First flight | MANUAL → FBWA → RTL, `TKOFF_*` | field | this module |
| 16 | First tune | AUTOTUNE, TECS | field | `ap-plane-tuning` |
| 17 | Log and backup | `.BIN`, `.param` | field | `ap-logs` |

{{diagram:ap-setup-plane-flow|The 17 setup steps of ArduPlane 4.7: everything up to step 13 is done on the bench with the propeller off, GPS and the airspeed sensor are checked outdoors, and only steps 15–17 happen in the air.}}

### Outputs and control surface functions
The firmware computes three demands in units from −4500 to +4500: aileron (positive is roll right), elevator (positive is nose up), rudder (positive is nose right). Throttle runs from 0 to 100. What an output does with them is set by `SERVOn_FUNCTION`. The Plane defaults: output 1 is 4, output 2 is 19, output 3 is 70, output 4 is 21. Timer groups, update rate and servo power are in `ap-outputs`.

| Function | Number | What it receives |
|---|---|---|
| Aileron | 4 | the aileron demand; two ailerons on separate outputs both get function 4; check 2 shows whether one of them needs reversing (with mirrored servos it does not) |
| Elevator | 19 | the elevator demand |
| Rudder | 21 | the rudder demand |
| GroundSteering | 26 | steering with a nose wheel or tail wheel |
| Throttle | 70 | throttle; `ThrottleLeft` 73 and `ThrottleRight` 74 are two motors with differential thrust |
| ElevonLeft / ElevonRight | 77 / 78 | a mix of aileron and elevator |
| VTailLeft / VTailRight | 79 / 80 | a mix of elevator and rudder |
| Flap / FlapAuto | 2 / 3 | flaps: manual (a channel with `RCx_OPTION = 208`) and automatic plus manual |
| FlaperonLeft / FlaperonRight | 24 / 25 | ailerons plus flap |
| DifferentialSpoilerLeft1 / Right1 | 16 / 17 | the outer halves of split elevons (yaw without a fin) |
| DifferentialSpoilerLeft2 / Right2 | 86 / 87 | the inner halves |
| Airbrakes | 110 | airbrakes |

The elevon and V-tail mixer (`servos.cpp`, `channel_function_mixer`):

- left elevon = (elevator − aileron) × `MIXING_GAIN`, right elevon = (elevator + aileron) × `MIXING_GAIN`;
- left V-tail half = (elevator + rudder) × `MIXING_GAIN`, right = (elevator − rudder) × `MIXING_GAIN`;
- the result is limited to ±4500.

`MIXING_GAIN` (0.5–1.2, default 0.5): at 0.5 the mixer never saturates, but one full demand gives half of the servo travel. At 1.0 the travel is full, but full roll together with full pitch hits the limit: (4500 + 4500) × 1.0 is clipped to 4500, and the second elevon gets 0. `MIXING_OFFSET` (default 0) boosts one input: a positive value multiplies the first input (aileron for elevons, rudder for a V-tail) by (100 + value) / 100, a negative one multiplies the elevator by (100 − value) / 100. The parameter description gives the unit as d%, but the code divides by 100: it is percent.

The demand then becomes a pulse width through `SERVOn_MIN`, `SERVOn_MAX`, `SERVOn_TRIM` (defaults 1100, 1900, 1500): for s > 0 the pulse = TRIM + ⌊s × (MAX − TRIM) / 4500⌋, for s < 0 it is TRIM − ⌊|s| × (TRIM − MIN) / 4500⌋; `SERVOn_REVERSED = 1` flips the sign of s. This arithmetic is worked through in `ap-outputs`.

### Control surface direction: two checks
The firmware convention: a positive demand and a rising pulse width on a non-reversed output must move the surface "up" (for ailerons, right one up and left one down; for the rudder, trailing edge to the right). Where the surface actually goes depends on how the servo is installed, so you check every surface by eye.

Check 1, the stick, in MANUAL mode (then repeat in FBWA):

| Stick | Conventional tail | Elevons | V-tail |
|---|---|---|---|
| roll right | right aileron up, left down | right elevon up, left down | ailerons as on a conventional plane |
| pitch stick back | elevator up | both elevons up | both halves up |
| rudder right | rudder trailing edge to the right | — | both trailing edges to the right: left half up, right half down |

Check 2, the autopilot response, in FBWA mode with the sticks centered, tilting the plane by hand:

| Tilt | Conventional tail | Elevons | V-tail |
|---|---|---|---|
| right wing down | right aileron down, left up; rudder to the left | right elevon down, left up | ailerons as on a conventional plane |
| nose up | elevator down | both elevons down | both halves down |
| nose down | elevator up | both elevons up | both halves up |

In FBWA the rudder gets a share of the aileron demand, `KFF_RDDRMIX` (default 0.5); the yaw damper `YAW2SRV_DAMP` defaults to 0, so the rudder does not respond when you yaw the nose by hand.

The order of fixing. First check 2: if a surface goes the wrong way, change `SERVOn_REVERSED` of that output (or the left and right functions are swapped). Then check 1: if the surfaces respond to the stick backwards, change `RCn_REVERSED` of the channel. Do not touch reversing in the transmitter. The most common cause of losing a plane on its first flight is a direction fixed for the stick through `RCn_REVERSED` or in the transmitter: in MANUAL everything is right, while in FBWA the autopilot amplifies a roll instead of removing it.

### Trimming and level
- `AHRS_TRIM_X`, `AHRS_TRIM_Y` (radians, ±0.1745, that is ±10°) are the difference between the board and the airframe; the level calibration writes them, with the plane in its level-flight attitude, usually nose 2–3° above the fuselage datum line.
- `PTCH_TRIM_DEG` (degrees, default 0; before 4.5 it was `TRIM_PITCH_CD` in centidegrees) is a pitch correction for when the plane loses or gains altitude at cruise throttle in FBWA with the sticks centered.
- `SERVO_AUTO_TRIM` (default 0): at 1 the firmware in flight shifts `SERVOn_TRIM` of the surfaces by 1 µs no more than twice a second toward the accumulated integrator, while the plane is flying nearly level (demanded roll and pitch within 7°, ground speed and airspeed at least 8 m/s, armed and flying) in FBWA or in auto-throttle modes. TRIM does not leave 40–60 % of the MIN–MAX range and is saved every 10 s. This does not replace mechanics: first set the linkages so that the surfaces are neutral at 1500 µs.
- `TRIM_THROTTLE` (%, default 45) is the level-flight throttle at `AIRSPEED_CRUISE`; without an airspeed sensor all throttle control depends on it.
- The center of gravity is checked before the first flight and matters more than any parameter: CG position and static margin are in `aero-stability` and `aero-wing`.

### Radio and modes
Radio calibration is as in `ap-setup-scratch`. After it, a rising pulse width must mean: roll channel to the right, pitch channel stick back, rudder channel to the right, throttle channel forward.

`FLTMODE_CH` on Plane defaults to 8 (on Copter, 5). Six positions by the channel pulse width: up to 1230, 1231–1360, 1361–1490, 1491–1620, 1621–1749, from 1750. The default values of `FLTMODE1..6`: RTL, RTL, FBWA, FBWA, MANUAL, MANUAL. `INITIAL_MODE` is the mode after power-up (MANUAL by default).

| No. | Mode | Who is in control |
|---|---|---|
| 0 | MANUAL | sticks straight to the surfaces, no stabilization and no throttle limits |
| 2 | STABILIZE | wings leveled when the sticks are released |
| 3 | TRAINING | manual control with attitude limits |
| 4 | ACRO | rate hold |
| 5 | FBWA | the stick sets roll and pitch within `ROLL_LIMIT_DEG`, `PTCH_LIM_*`; manual throttle |
| 6 | FBWB | altitude hold, TECS controls the throttle |
| 7 | CRUISE | FBWB with heading hold |
| 8 | AUTOTUNE | FBWA with gain tuning (`ap-plane-tuning`) |
| 1 | CIRCLE | circling in place with no GPS navigation |
| 12 | LOITER | a circle of radius `WP_LOITER_RAD` around a point |
| 11 | RTL | return and a loiter over home or a rally point |
| 10 | AUTO | mission |
| 13 | TAKEOFF | automatic takeoff and loiter |
| 15 | GUIDED | a point from the ground station |
| 24 | THERMAL | thermal soaring |
| 26 | AUTOLAND | automatic landing without a mission, new in 4.7 |

Numbers 17–23 and 25 are the QuadPlane modes (`ap-quadplane`), and 14 is AVOID_ADSB. The switch functions (`RCx_OPTION`: 77 TAKEOFF, 92 FBWA, 4 RTL, 183 AUTOLAND, 153 arming) are in `ap-aux-tune`.

### Throttle and motor
| Parameter | Default | Meaning |
|---|---|---|
| `THR_MIN` | 0 % | minimum throttle in all modes except MANUAL; a negative value enables reverse thrust |
| `THR_MAX` | 100 % | maximum throttle in the same modes |
| `THR_SLEWRATE` | 100 %/s | the throttle slew rate |
| `THR_PASS_STAB` | 0 | 1: in STABILIZE, FBWA and ACRO the throttle is a direct passthru from the stick, and `THR_MIN/MAX` do not apply |
| `TRIM_THROTTLE` | 45 % | cruise throttle |
| `THROTTLE_NUDGE` | 1 | the throttle stick above the middle adds airspeed (with a sensor) or throttle (without one) |
| `USE_REV_THRUST` | 2 | in which modes reverse thrust is allowed; 2 is only the landing approach in AUTO |

The throttle output is a 0–100 % range: pulse = `SERVO3_MIN` + throttle × (`SERVO3_MAX` − `SERVO3_MIN`) / 100. With `THR_MIN` < 0 the output becomes an "angle" of ±100 % around `SERVO3_TRIM`, and the ESC must be reversible.

A PWM ESC has to be taught its range once, with the propeller off: flight controller powered from USB, MANUAL mode, arm, throttle stick up, connect the battery, stick down after the ESC beeps. DShot needs no calibration (`ap-outputs`). The battery monitor and its calibration are step 10 in `ap-setup-scratch`, with the same formulas.

### The airspeed sensor
Do you need one? No: ArduPlane flies and lands without it. You need it for a QuadPlane (the transition relies on airspeed, `ap-quadplane`), for flying in strong wind, for a slow wing with little margin above stall, and for a precise automatic landing. For a first plane it adds tubing, a calibration and new failure modes.

| Parameter | Default | Values and meaning |
|---|---|---|
| `ARSPD_TYPE` | 1 on boards with the MS4525 driver, 2 in SITL, otherwise 0 | 0 None; 1 I²C MS4525D0; 2 Analog; 3, 4, 5 I²C MS5525 (auto, address 0x76, 0x77); 6 I²C SDP3X; 7, 9, 10, 11, 12 I²C DLVR for 5, 10, 20, 30, 60 inches of water; 8 DroneCAN; 13 NMEA water speed; 14 MSP; 15 ASP5033; 16 ExternalAHRS; 17, 18, 19 AUAV for 10, 5, 30 inches |
| `ARSPD_USE` | 0 | 0: display and log only; 1: use it for control; 2: use it only at zero throttle (a glider with the pitot tube behind the prop) |
| `ARSPD_BUS` | 1 | the I²C bus number; if the sensor is not found, try another number and reboot |
| `ARSPD_PIN` | 15 or per board | the ADC input of an analog sensor |
| `ARSPD_TUBE_ORDR` | 2 | 0, 1: a fixed tube order; 2: accept either |
| `ARSPD_RATIO` | 2 | the "pressure → airspeed" scale |
| `ARSPD_OFFSET` | 0 | the sensor zero, written by the calibration |
| `ARSPD_SKIP_CAL` | 0 | 0: calibrate the zero at every power-up; 1: use the saved one; 2: wait for a manual calibration |
| `ARSPD_AUTOCAL` | 0 | 1: fit `ARSPD_RATIO` in flight |
| `ARSPD_OPTIONS` | 11 | bit 0: disable the sensor on a mismatch with GPS speed; bit 1: re-enable it; bit 2: no voltage correction; bit 3: check against EKF3; bit 4: report the offset to the ground station |
| `ARSPD_WIND_MAX` | 0 m/s | the threshold for the airspeed/ground speed difference; 0 turns the threshold check off |
| `ARSPD_WIND_WARN` | 0 m/s | the warning threshold |

The main trap: `ARSPD_USE` defaults to 0. The sensor is connected and the airspeed shows in the OSD, but TECS and the bank limiting do not use it.

The formula (`AP_Airspeed.cpp`): V = √(Δp × `ARSPD_RATIO`), where Δp is the differential pressure in pascals with the zero subtracted. An ideal tube at sea level would give 2 / ρ = 2 / 1.225 = 1.63; the default of 2 allows for typical losses. Correcting against GPS speed: new `ARSPD_RATIO` = old × (V_true / V_indicated)². A normal result is between 1.5 and 3.0; outside that range look for a leak in the tubing or a poor tube location.

The zero at power-up: the tube is shielded from wind (a piece of foam) and the sensor has warmed up for a minute. Before arming, blow into the tube: the reading rises. In-flight calibration: `ARSPD_AUTOCAL = 1` (or a switch with `RCx_OPTION = 91`), five minutes of circles, then set it back to 0. The firmware keeps the value within 1.0–4.0 and saves it when it has moved more than 5 % from the stored one. `RCx_OPTION = 106` disables airspeed use in flight.

Without a sensor (`ARSPD_USE = 0` or `ARSPD_TYPE = 0`):

- TECS sets the throttle from pitch: `TRIM_THROTTLE` in level flight, linearly up to `THR_MAX` at a pitch of `PTCH_LIM_MAX_DEG` and down to `THR_MIN` at `PTCH_LIM_MIN_DEG`. The elevator holds altitude and nobody measures airspeed: it is whatever that throttle produces;
- stall prevention and surface speed scaling take an airspeed estimate from GPS and the wind estimate; it is wrong in gusts;
- `AIRSPEED_CRUISE` is no longer a demanded airspeed: `TRIM_THROTTLE` sets the cruise.

### Airspeeds, angles and stall prevention
| Parameter (4.7) | Name before 4.5 | Default | Selection rule |
|---|---|---|---|
| `AIRSPEED_MIN`, m/s | `ARSPD_FBW_MIN`, m/s | 9 | at least 1.2 × V_s; below 5 the pre-arm check fails with "AIRSPEED_MIN too low" |
| `AIRSPEED_CRUISE`, m/s | `TRIM_ARSPD_CM`, cm/s | 12 | between MIN and MAX, usually about 1.4 × V_s |
| `AIRSPEED_MAX`, m/s | `ARSPD_FBW_MAX`, m/s | 22 | just below the airspeed at `THR_MAX`, at least 1.5 × `AIRSPEED_MIN` |
| `AIRSPEED_STALL`, m/s | — | 0 | the measured V_s; 0 means `AIRSPEED_MIN` is used instead |
| `SCALING_SPEED`, m/s | — | 15 | the airspeed the gains are tuned at; set it before tuning |
| `ROLL_LIMIT_DEG`, ° | `LIM_ROLL_CD`, centidegrees | 45 | the bank limit; below 3 the pre-arm check fails |
| `PTCH_LIM_MAX_DEG`, ° | `LIM_PITCH_MAX`, centidegrees | 20 | the pitch-up limit |
| `PTCH_LIM_MIN_DEG`, ° | `LIM_PITCH_MIN`, centidegrees | −25 | the pitch-down limit |
| `RTL_ALTITUDE`, m | `ALT_HOLD_RTL`, cm | 100 | the return altitude above home; −1 is the current one |
| `WP_LOITER_RAD`, m | — | 60 | the loiter radius; negative is counterclockwise |
| `RTL_RADIUS`, m | — | 0 | the loiter radius in RTL; 0 means use `WP_LOITER_RAD` |

V_s is the stall speed, calculated in `aero-wing`. On a firmware update the values are converted automatically; the danger is a manual transfer from an old file: `TRIM_ARSPD_CM = 1400` written as `AIRSPEED_CRUISE` gives 1400 m/s, and `ALT_HOLD_RTL = 10000` as `RTL_ALTITUDE` gives 10 km.

`STALL_PREVENTION = 1` (the default) limits the demanded bank by load factor. The allowed load factor is n = (V / V_st)², where V_st is `AIRSPEED_STALL`, or `AIRSPEED_MIN` when that is zero; the bank limit = arccos(1 / n), but not less than 25° (with the `FLIGHT_OPTIONS` bit ENABLE_FULL_AERO_LF_ROLL_LIMITS, an airspeed sensor and `AIRSPEED_STALL` > 0 this 25° floor is dropped; the limit never goes below `LEVEL_ROLL_LIMIT`). An example: `AIRSPEED_MIN = 11`, V = 12 m/s: n = 1.19, a limit of 32.8° with `ROLL_LIMIT_DEG = 45`. TECS at the same time raises the minimum airspeed in a turn by a factor of √n. The radius of a steady turn: R = V² / (g × tan φ); 14 m/s and 45° give 20 m.

### The fixed-wing failsafe
Detecting RC loss (`radio.cpp`). `THR_FAILSAFE` (default 1): 0 Disabled; 1 Enabled; 2 means RC inputs are ignored on loss but no failsafe action is taken. A loss is one of two things: the throttle pulse width is not above `THR_FS_VALUE` (default 950; the receiver is set to output low throttle on loss), or there have been no valid frames for longer than `RC_FS_TIMEOUT` (default 1 s). The condition has to hold for 10 radio read cycles of 20 ms, another 0.2 s; then "Throttle failsafe on" appears, the roll, pitch and rudder inputs are replaced with neutral, and the throttle with zero. The idle throttle in the calibration must be 40–50 µs above `THR_FS_VALUE`, or the failsafe will trigger from the stick being down.

The short failsafe follows immediately. `FS_SHORT_TIMEOUT` (1.5 s in 4.6.3) was removed in 4.7: only `RC_FS_TIMEOUT` and the 0.2 s of the counter set the delay. The long one comes when more than `FS_LONG_TIMEOUT` has passed since the last valid frame (default 5 s, tested three times a second). During a landing (the LAND stage) the failsafe does not trigger.

Short, `FS_SHORT_ACTN` (default 0), the action by current mode (`events.cpp`):

| Mode at the time of the loss | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| MANUAL, STABILIZE, ACRO, TRAINING, FBWA, FBWB, CRUISE, AUTOTUNE | CIRCLE | CIRCLE | FBWA, throttle to minimum | none | FBWB |
| AUTO and AUTOLAND outside a landing, GUIDED, LOITER, THERMAL, AVOID_ADSB | no change | CIRCLE | FBWA, throttle to minimum | none | FBWB |
| CIRCLE, RTL, TAKEOFF | no change | no change | no change | none | no change |

Long, `FS_LONG_ACTN` (default 0), the action by the mode at the time of the long event, that is already after the short one:

| Mode at that time | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| the manual ones of the first row, CIRCLE, LOITER, THERMAL, TAKEOFF | RTL | RTL | FBWA (glide) | parachute | AUTO | AUTOLAND, or RTL if that fails |
| AUTO outside a landing, GUIDED, AVOID_ADSB | no change | RTL | FBWA | parachute | AUTO | AUTOLAND, or RTL if that fails |
| RTL | no change | no change | no change | no change | AUTO | AUTOLAND |
| AUTOLAND | no change | no change | no change | no change | no change | no change |

In TAKEOFF the long action is deferred until the initial climb is complete (except 2 and 3). A switch with `RCx_OPTION = 157` replaces the action for the first row with FBWA. The QuadPlane modes go to QLAND, QRTL or RTL per `Q_OPTIONS`.

Three consequences of the tables. First, "0 Continue" in the long failsafe applies only to AUTO and GUIDED; from the manual modes you get RTL. Second, `FS_SHORT_ACTN = 1` puts a mission into CIRCLE, and the long event finds the plane already in CIRCLE: with `FS_LONG_ACTN = 0` the mission does not continue, it is RTL. Third, if the link comes back before the long event, the mode is restored automatically ("Flight mode … restored"); after the long one it is not, and the pilot has to move the mode switch.

{{diagram:ap-setup-plane-fs-timeline|The ArduPlane 4.7 RC failsafe with FS_LONG_TIMEOUT = 5 s: the short action comes 1.2 s after the frames stop or 0.2 s after low throttle, the long one in the fifth second; a mission with FS_SHORT_ACTN = 1 ends in RTL even with FS_LONG_ACTN = 0.}}

The rest:

- `FS_GCS_ENABL` (default 0): 1 is no ground station HEARTBEAT for longer than `FS_LONG_TIMEOUT`; 2 is the same or a zero `remrssi` from the telemetry radio; 3 is like 1 but only in AUTO. The action is the long one.
- Battery: `BATT_FS_LOW_ACT`, `BATT_FS_CRT_ACT`: 0 Warn only, 1 RTL, 2 Land (the nearest landing sequence of the mission, otherwise RTL), 3 Terminate, 5 parachute, 7 AUTOLAND or RTL; 4 and 6 are for QuadPlane. The thresholds are as in `ap-setup-scratch`.
- `RTL_AUTOLAND` (default 0): 1 flies home and then goes to the landing sequence of the mission from `DO_LAND_START`; 2 goes to it directly; 3 uses `DO_LAND_START` only for a go-around; 4 goes through `DO_RETURN_PATH_START`. With 0 and a `DO_LAND_START` in the mission, arming is refused.
- Rally points: RTL goes to the nearest point within `RALLY_LIMIT_KM` (default 5 km) at its altitude; home is not included in the comparison while `RALLY_INCL_HOME = 0`. `RTL_CLIMB_MIN` (default 0): first climb this many meters with the bank limited to `LEVEL_ROLL_LIMIT`.
- RTL on a plane is a loiter over home: without `RTL_AUTOLAND` or AUTOLAND it circles until the battery is flat.
- Geofence: `FENCE_ENABLE` (0), `FENCE_TYPE` (the Plane default is 4, polygons only; bit 0 is the ceiling `FENCE_ALT_MAX`, bit 1 the circle `FENCE_RADIUS`, bit 3 the floor `FENCE_ALT_MIN`), `FENCE_ACTION` (0 Report Only, 1 RTL, 6 Guided, 7 Guided with manual throttle, 8 AUTOLAND or RTL), `FENCE_AUTOENABLE` (0 is off; 3 enables when armed; 1, after an auto takeoff, and 2 still work, but 4.7.2 prints "FENCE_AUTOENABLE is 1, will be removed in 4.7, use 3" once a minute, so use 3), `FENCE_RET_RALLY`. The Plane failsafe names and actions are collected in this section ("The fixed-wing failsafe"); `ap-safety-fs` is the companion module for Copter: the FMEA method and the ArduCopter failsafe map, with no plane parameters in it.

### Arming and pre-arm checks
- `ARMING_REQUIRE` (default 1): 0 means no arming is needed and the motor is ready right after power-up; 1 sends minimum throttle to the throttle output until armed; 2 sends no pulses until armed.
- `ARMING_RUDDER` (Plane default 1): 0 Disabled; 1 ArmingOnly; 2 ArmOrDisarm. The gesture: throttle at zero, rudder right for 3 s. With the value 1 you cannot disarm with the stick: you need a switch with `RCx_OPTION = 153` or the ground station.
- `ARMING_SKIPCHK = 0` means all checks are on (before 4.7, `ARMING_CHECK = 1`); bit 9 is the airspeed sensor check.

Checks that a copter does not have: "ROLL_LIMIT_DEG too small", "PTCH_LIM_MAX_DEG too small", "PTCH_LIM_MIN_DEG too large" (less than 3° in magnitude), "AIRSPEED_MIN too low" (less than 5), "Waiting for RC" (with `THR_FAILSAFE = 1` the receiver has not been seen even once), "Airspeed: 1 need pre-flight calibration" and "not healthy" (only with `ARSPD_USE` > 0), "DO_LAND_START set and RTL_AUTOLAND disabled", "In landing sequence".

### Takeoff
TAKEOFF mode: full throttle, a climb at pitch `TKOFF_LVL_PITCH`, bank limited to `LEVEL_ROLL_LIMIT` (5°) up to the altitude `TKOFF_LVL_ALT`, then flight to a point at distance `TKOFF_DIST` on the takeoff heading and a loiter at `TKOFF_ALT`. All of these parameters exist in 4.7.2:

| Parameter | Default | Meaning |
|---|---|---|
| `TKOFF_ALT` | 50 m | the loiter altitude after takeoff |
| `TKOFF_LVL_ALT` | 10 m | below it the wings are held level |
| `TKOFF_LVL_PITCH` | 15° | the climb pitch |
| `TKOFF_DIST` | 200 m | the distance to the loiter point |
| `TKOFF_GND_PITCH` | 5° | the pitch during the ground roll up to `TKOFF_ROTATE_SPD` |
| `TKOFF_THR_MINACC` | 0 m/s² | the forward acceleration that starts the countdown; 0 means no check |
| `TKOFF_THR_DELAY` | 2 (0.2 s) | the delay after the acceleration, in tenths of a second |
| `TKOFF_THR_MINSPD` | 0 m/s | the GPS ground speed needed to start the motor; 0 means no check |
| `TKOFF_ACCEL_CNT` | 1 | how many back-and-forth acceleration events are needed to start |
| `TKOFF_THR_MAX_T` | 4 s | how long to hold full throttle |
| `TKOFF_THR_MAX` | 0 % | maximum throttle during takeoff; 0 means `THR_MAX` |
| `TKOFF_THR_IDLE` | 0 % | the throttle after arming and before takeoff, new in 4.7 |
| `TKOFF_ROTATE_SPD` | 0 m/s | the rotation speed during the ground roll |
| `TKOFF_TDRAG_ELEV` | 0 % | elevator at the start of the ground roll: 100 for a taildragger |
| `TKOFF_TDRAG_SPD1` | 0 m/s | the speed at which the tail is released |
| `TKOFF_TIMEOUT` | 0 s | disarm if 4 m/s is not reached within this time |

The motor in TAKEOFF and during a takeoff in AUTO is inhibited until this chain has passed (`takeoff.cpp`): a 3D GPS fix → forward acceleration of at least `TKOFF_THR_MINACC` → the `TKOFF_THR_DELAY` pause → GPS speed above `TKOFF_THR_MINSPD` → pitch between −30° and +45°, roll up to 30°. With the defaults there are no acceleration or speed checks: with a 3D fix the motor starts 0.2 s after arming in TAKEOFF. The GPS speed condition must be met within `TKOFF_THR_DELAY` + 0.1 s of the acceleration trigger; otherwise the GCS shows "Timeout AUTO" and the chain starts over.

| Method | `TKOFF_THR_MINACC` | `TKOFF_THR_DELAY` | `TKOFF_THR_MINSPD` | Ground roll |
|---|---|---|---|---|
| hand launch | 15 | 2 or more | 4 for a pusher prop | `TKOFF_ROTATE_SPD = 0`, `TKOFF_TDRAG_* = 0` |
| catapult | 20 | 5 | 0–4 | the same |
| bungee | 15 | 50 (5 s, until the bungee releases) | 0–4 | the same |
| runway | 0 | 2 | 0 | `TKOFF_ROTATE_SPD` 10–30 % above V_s; `GROUND_STEER_ALT`; for a taildragger `TKOFF_TDRAG_ELEV = 100` |

A hand launch for the first time: into the wind, full throttle (or TAKEOFF with the start conditions configured), nose 10–15° above the horizon, a level push forward and not upward; after the throw your hand moves away to the side of the prop. Land into the wind on a long shallow glide path and cut the throttle before the flare. Automatic landing is in `ap-plane-tuning`.

### The first flight and the logs
1. Before the flight: CG (`aero-stability`), both surface checks, a failsafe check on the ground with the propeller off, a 3D fix, the pitot tube clear. The site and people per `f-safety`.
2. MANUAL: takeoff, climb to 50–80 m, trimming. Abort and land if the plane needs more than half of the stick travel to fly level or oscillates in pitch: that is the CG.
3. FBWA at altitude: sticks released, the plane levels itself. If roll or pitch builds up by itself, go to MANUAL at once and land: an output is reversed or the board orientation is wrong.
4. FBWA for 2–3 minutes with `SERVO_AUTO_TRIM = 1`, then AUTOTUNE per `ap-plane-tuning`.
5. RTL from the switch at a distance of 150–200 m: the plane turns toward home, goes to `RTL_ALTITUDE` and enters a loiter. If it heads off to the side or loses altitude, MANUAL or FBWA and land.
6. Abort criteria for any stage: airspeed below `AIRSPEED_MIN`, altitude below 30 m in an automatic mode, any surface movement you do not understand.

In the log after the flight (`ap-logs`): `ATT` has the demanded and actual roll and pitch; `ARSP.Airspeed` against `GPS.Spd`; `CTUN.ThO` is the cruise throttle for `TRIM_THROTTLE`; `MODE` and the failsafe messages; `RCOU` shows whether the surfaces run into `SERVOn_MIN/MAX`.

### Place in the system

- **Receives:** V_s, cruise and CG position (`aero-wing`, `aero-stability`); the output arithmetic and servo power (`ap-outputs`); the common steps of firmware, ports, receiver and battery monitor (`ap-setup-scratch`); the 4.7 parameter names (`ap-intro`).
- **Provides:** a plane with correct surface directions, airspeed limits and a verified failsafe to tuning (`ap-plane-tuning`); the fixed-wing half of the setup to QuadPlane (`ap-quadplane`); the Plane failsafe tables of the section "The fixed-wing failsafe" as the plane counterpart of the Copter failure map and the FMEA method (`ap-safety-fs`, which covers Copter only); the first log (`ap-logs`).
- **If you get it wrong here:** a reversed output with a correct stick shows only in FBWA and breaks AUTOTUNE and RTL (`ap-plane-tuning`); an `AIRSPEED_MIN` that is too low gives a stall in the RTL turn and in a QuadPlane transition (`ap-quadplane`); `ARSPD_USE = 0` leaves TECS without airspeed, and people look for the "bad altitude tune" in the wrong place.

## practice
The lab is a calculation exercise: you need neither a flight controller nor a simulator. All parameter files below are a training example assembled by hand; they are not an export from a real vehicle. Every answer follows from the formulas and tables of the theory; the numbers were checked with a script that reproduces the arithmetic of firmware 4.7.2.

Common data for steps 1 and 2. RC inputs: `RCn_MIN = 1000`, `RCn_MAX = 2000`, `RCn_TRIM = 1500`, not reversed, expo `MAN_EXPO_*` = 0. In MANUAL the demand = 4500 × (pulse − 1500) / 500, that is 9 units per microsecond. The "mechanics" note says where the surface goes as the pulse width rises: that is a property of the servo installation, and you can only see it by eye.

### Step 1. Surface pulse widths of three planes
For each plane find the pulse width of each output and the surface direction in two cases.

The "stick" case, MANUAL: roll channel 1750 µs, pitch channel 1700 µs, rudder channel 1800 µs (plane B has no rudder connected).

The "tilt" case, FBWA, sticks centered: the plane was banked to the right and its nose raised; the controllers output an aileron demand of −1400 and an elevator demand of −1000 (the numbers are given by the problem: in real life they depend on the gains), `KFF_RDDRMIX = 0.5`.

```
# training example, assembled by hand: plane A, conventional tail
SERVO1_FUNCTION,4     # left aileron;  mechanics: pulse rises, surface down
SERVO1_MIN,1100
SERVO1_TRIM,1500
SERVO1_MAX,1900
SERVO1_REVERSED,0
SERVO5_FUNCTION,4     # right aileron; mechanics: pulse rises, surface down
SERVO5_MIN,1100
SERVO5_TRIM,1520
SERVO5_MAX,1900
SERVO5_REVERSED,1
SERVO2_FUNCTION,19    # elevator;      mechanics: pulse rises, surface down
SERVO2_MIN,1000
SERVO2_TRIM,1480
SERVO2_MAX,2000
SERVO2_REVERSED,1
SERVO4_FUNCTION,21    # rudder; mechanics: pulse rises, trailing edge right
SERVO4_MIN,1100
SERVO4_TRIM,1500
SERVO4_MAX,1900
SERVO4_REVERSED,0
```

```
# training example, assembled by hand: plane B, flying wing
MIXING_GAIN,0.5
MIXING_OFFSET,0
SERVO1_FUNCTION,77    # left elevon;  mechanics: pulse rises, surface up
SERVO1_MIN,1000
SERVO1_TRIM,1500
SERVO1_MAX,2000
SERVO1_REVERSED,0
SERVO2_FUNCTION,78    # right elevon; mechanics: pulse rises, surface down
SERVO2_MIN,1000
SERVO2_TRIM,1500
SERVO2_MAX,2000
SERVO2_REVERSED,1
```

```
# training example, assembled by hand: plane C, V-tail (ailerons as on A)
MIXING_GAIN,0.5
SERVO2_FUNCTION,79    # left half;  mechanics: pulse rises, surface up
SERVO2_MIN,1100
SERVO2_TRIM,1500
SERVO2_MAX,1900
SERVO2_REVERSED,0
SERVO4_FUNCTION,80    # right half; mechanics: pulse rises, surface up
SERVO4_MIN,1100
SERVO4_TRIM,1540
SERVO4_MAX,1900
SERVO4_REVERSED,0
```

Result. The stick demands: aileron 9 × 250 = +2250, elevator 9 × 200 = +1800, rudder 9 × 300 = +2700.

| Plane, output | Stick: output demand → pulse → surface | Tilt: output demand → pulse → surface |
|---|---|---|
| A, left aileron | +2250 → 1500 + 200 = **1700** → down | −1400 → 1500 − 124 = **1376** → up |
| A, right aileron (reversed) | −2250 → 1520 − 210 = **1310** → up | +1400 → 1520 + 118 = **1638** → down |
| A, elevator (reversed) | −1800 → 1480 − 192 = **1288** → up | +1000 → 1480 + 115 = **1595** → down |
| A, rudder | +2700 → 1500 + 240 = **1740** → right | −700 → 1500 − 62 = **1438** → left |
| B, left elevon | (1800 − 2250) × 0.5 = −225 → **1475** → down | (−1000 + 1400) × 0.5 = +200 → **1522** → up |
| B, right elevon (reversed) | (1800 + 2250) × 0.5 = +2025, after reversing −2025 → **1275** → up | −1200, after reversing +1200 → **1633** → down |
| C, left half | (1800 + 2700) × 0.5 = +2250 → **1700** → up | (−1000 + 0) × 0.5 = −500 → **1456** → down |
| C, right half | (1800 − 2700) × 0.5 = −450 → 1540 − 44 = **1496** → down | −500 → 1540 − 48 = **1492** → down |

Fractions are dropped: 1400 × 400 / 4500 = 124.4 → 124; 1400 × 380 / 4500 = 118.2 → 118; 1000 × 520 / 4500 = 115.6 → 115; 700 × 400 / 4500 = 62.2 → 62; 200 × 500 / 4500 = 22.2 → 22; 1200 × 500 / 4500 = 133.3 → 133; 500 × 400 / 4500 = 44.4 → 44; 500 × 440 / 4500 = 48.9 → 48. All directions agree with the two tables of the theory: the three files are set up correctly. For plane C the rudder input to the V-tail mixer in the "tilt" case was taken as zero to show the pure pitch response; with the −700 share from the ailerons the halves would get −850 and −150.

In addition for plane B, the "stick" case: with `MIXING_GAIN = 1.0` the demands are −450 and +4050 and the pulses **1450** and **1050**; with `MIXING_GAIN = 0.5` and `MIXING_OFFSET = 20` the aileron becomes 2250 × 1.2 = 2700, the demands are −450 and +2250, and the pulses **1450** and **1250**.

### Step 2. Reversed surfaces in a wrong file
Plane D, a V-tail and two ailerons. Find the outputs with a wrong `SERVOn_REVERSED`, write the correct values, and say what the pilot sees in MANUAL (stick back, 1700 µs; roll right, 1750 µs) and in FBWA (nose raised, elevator demand −1000).

```
# training example, assembled by hand: plane D (wrong file)
MIXING_GAIN,0.5
SERVO1_FUNCTION,4     # left aileron;    mechanics: pulse rises, surface down
SERVO1_REVERSED,0
SERVO5_FUNCTION,4     # right aileron;   mechanics: pulse rises, surface down
SERVO5_REVERSED,0
SERVO2_FUNCTION,79    # left half;  mechanics: pulse rises, surface down
SERVO2_REVERSED,0
SERVO4_FUNCTION,80    # right half; mechanics: pulse rises, surface up
SERVO4_REVERSED,1
# all four outputs have MIN 1100, TRIM 1500, MAX 1900
```

Result. Three outputs are wrong: `SERVO5_REVERSED` must be 1, `SERVO2_REVERSED` must be 1, `SERVO4_REVERSED` must be 0. Only output 1 is right.

- Stick back: both halves get (1800 + 0) × 0.5 = +900. Output 2: 1500 + 80 = 1580, the pulse rose, surface down. Output 4, reversed: 1500 − 80 = 1420, the pulse fell, surface down. Both halves go down instead of up.
- Roll right: both ailerons get +2250 → 1700, both down. There is no roll; the ailerons act as flaps.
- FBWA, nose up: the demand is −500. Output 2: 1456, surface up; output 4: 1544, surface up. The autopilot increases the pitch instead of removing it.

If you "fix" pitch through `RC2_REVERSED = 1`, the stick works correctly in MANUAL while the FBWA response stays reversed: that is exactly why check 2 comes first.

### Step 3. The failsafe timeline
Parameters: `THR_FAILSAFE = 1`, `THR_FS_VALUE = 950`, `RC_FS_TIMEOUT = 1`, `FS_LONG_TIMEOUT = 5`, the radio is read 50 times a second. The last valid frame is at t = 0. For each scenario write down what happens and when.

| Scenario | Mode | What the receiver does | `FS_SHORT_ACTN` | `FS_LONG_ACTN` |
|---|---|---|---|---|
| 1 | FBWA | stops sending frames | 0 | 0 |
| 2 | FBWA | sends frames with throttle at 900 µs | 0 | 0 |
| 3 | AUTO, mission | stops sending frames | 0 | 0 |
| 4 | AUTO, mission | stops sending frames | 1 | 0 |
| 5 | FBWA | stops sending frames, the link returns at t = 3.0 s | 0 | 1 |

Result.

| Scenario | Short event | Long event | Outcome |
|---|---|---|---|
| 1 | t ≈ 1.2 s (1.0 + 0.2): CIRCLE | t from 5.0 to 5.33 s: RTL | "0 Continue" from a manual mode gives RTL |
| 2 | t ≈ 0.2 s: CIRCLE | t from 5.0 to 5.33 s: RTL | low throttle is detected a second earlier |
| 3 | t ≈ 1.2 s: the mode does not change, message "RC Short Failsafe On" | the mode does not change | the mission continues |
| 4 | t ≈ 1.2 s: CIRCLE | the plane is already in CIRCLE → RTL | the mission is aborted although `FS_LONG_ACTN = 0` |
| 5 | t ≈ 1.2 s: CIRCLE | does not occur | t ≈ 3.1 s (four cycles after the return): "Flight mode FBWA restored" |

The plane spends 5.0 − 1.2 = 3.8 s in CIRCLE in scenarios 1 and 4, and 4.8 s in scenario 2. The long event is tested three times a second, hence the spread of up to 0.33 s. In scenario 5 the counter is reset from 10 to 3 when the link returns and reaches zero in four cycles of 20 ms.

### Step 4. Airspeed, limits and bank
A flying wing of 2 kg, area 0.4 m², V_s = 8.5 m/s (the calculation from `aero-wing`).

(a) `ARSPD_RATIO = 2.0`. In FBWA you flew two straight legs in opposite directions in light wind: GPS ground speed 17.0 and 19.0 m/s, indicated airspeed 16.2 m/s on both. Find the differential pressure and the new `ARSPD_RATIO`.

(b) Check the set `AIRSPEED_MIN = 11`, `AIRSPEED_CRUISE = 14`, `AIRSPEED_MAX = 20` against the rules in the theory table.

(c) `STALL_PREVENTION = 1`, `AIRSPEED_STALL = 0`, `ROLL_LIMIT_DEG = 45`. What bank does the firmware allow at 12, 14 and 11 m/s?

(d) What bank does a loiter of `WP_LOITER_RAD = 60` need at 14 m/s, and what radius do you get at 45°?

Result. (a) The GPS mean is (17.0 + 19.0) / 2 = 18.0 m/s: opposite legs cancel the wind. Δp = 16.2² / 2.0 = **131.2 Pa**. The new value is 2.0 × (18.0 / 16.2)² = **2.47**; check: √(131.2 × 2.47) = 18.0 m/s. It is inside the range 1.5–3.0. (b) 1.2 × 8.5 = 10.2 → `AIRSPEED_MIN` is an integer, so 11 fits; 1.5 × 11 = 16.5 ≤ 20, fits; 14 lies between 11 and 20 and above the guide value 1.4 × 8.5 = 11.9, fits. (c) 12 m/s: n = (12 / 11)² = 1.19, arccos(1 / 1.19) = **32.8°**; 14 m/s: n = 1.62, 51.9°, so `ROLL_LIMIT_DEG` applies, **45°**; 11 m/s: n = 1, the lower bound, **25°**. (d) tan φ = 14² / (9.81 × 60) = 0.333, φ = **18.4°**; at 45° R = 196 / 9.81 = **20 m**.

### Step 5. Three mistakes in a parameter file
The same wing: a pusher prop, hand launch in TAKEOFF mode, an MS4525 sensor is fitted and is meant to control airspeed, and the receiver stops sending frames on link loss. Find the lines that make the plane dangerous or make it work differently from what was intended.

```
# training example, assembled by hand
THR_FAILSAFE,1
THR_FS_VALUE,950
RC3_MIN,940
RC3_MAX,2010
RC_FS_TIMEOUT,1
FS_SHORT_ACTN,0
FS_LONG_ACTN,1
FS_LONG_TIMEOUT,5
ARSPD_TYPE,1
ARSPD_USE,0
ARSPD_RATIO,2.2
ARSPD_AUTOCAL,0
AIRSPEED_MIN,11
AIRSPEED_CRUISE,14
AIRSPEED_MAX,20
ROLL_LIMIT_DEG,45
PTCH_LIM_MAX_DEG,20
PTCH_LIM_MIN_DEG,-25
STALL_PREVENTION,1
TKOFF_THR_MINACC,0
TKOFF_THR_MINSPD,0
TKOFF_THR_DELAY,2
TKOFF_ALT,50
ARMING_REQUIRE,1
ARMING_RUDDER,1
ARMING_SKIPCHK,0
RTL_ALTITUDE,100
RTL_AUTOLAND,0
```

Result: there are exactly three mistakes. (1) `RC3_MIN = 940` is below `THR_FS_VALUE = 950`: the throttle stick at the bottom is detected as a link loss, and 0.2 s later the plane goes into CIRCLE; raise the idle throttle in the transmitter to 990–1000 µs and recalibrate, or lower the threshold to 40–50 µs below idle. (2) `ARSPD_USE = 0`: the sensor only displays airspeed; it must be 1. (3) `TKOFF_THR_MINACC = 0` and `TKOFF_THR_MINSPD = 0`: in TAKEOFF the motor starts 0.2 s after arming, while the plane is still in your hand; for a throw with a pusher prop use 15 and 4. The rest is correct: `FS_SHORT_ACTN = 0` with `FS_LONG_ACTN = 1` give CIRCLE and RTL, the airspeeds were checked in step 4, `ARSPD_RATIO = 2.2` is within 1.5–3.0, `ARSPD_AUTOCAL = 0` after the calibration, `ARMING_RUDDER = 1` is the Plane default, `RTL_ALTITUDE = 100` is in meters, and `RTL_AUTOLAND = 0` with no `DO_LAND_START` in the mission is acceptable.

### Moving to real hardware
The propeller stays off until item 8. The servos are powered from a separate BEC.

1. The common steps 1–5, 9, 10, 13 per `ap-setup-scratch` with the file `arduplane_with_bl.hex`; save `00_defaults.param`.
2. Assign `SERVOn_FUNCTION` from the table and reboot. Set the linkages so that the surfaces are neutral at `SERVOn_TRIM = 1500`; limit the end points with `SERVOn_MIN/MAX` so that no servo binds.
3. Check 2 (FBWA, tilting by hand), then check 1 (MANUAL, sticks). Write a table "surface, expected, observed" for all six rows of your layout; fix things only with `SERVOn_REVERSED` and `RCn_REVERSED`.
4. Throttle: `THR_FS_VALUE` 40–50 µs below idle; calibrate a PWM ESC.
5. Failsafe on the ground: arm in FBWA and switch off the transmitter; the messages show "Throttle failsafe on" and "RC Short Failsafe: switched to Circle", and in the sixth second RTL. On a stationary plane the throttle in CIRCLE and RTL stays at zero: the firmware keeps it suppressed while the altitude differs from home by less than 10 m and the GPS speed is below 5 m/s (with an airspeed sensor in use, releasing the suppression also needs an airspeed of 5 m/s). A jump in GPS speed or a 10 m barometer drift releases the suppression without warning, and the motor immediately gets the throttle of the automatic mode, which is why the propeller is off. Switch the transmitter on and move the mode switch.
6. Airspeed sensor: cover the tube, power up, wait for the calibration; blow into it and the reading goes above 6 m/s; set `ARSPD_USE = 1` only after that.
7. CG per `aero-stability`; weigh the plane and recalculate V_s.
8. Propeller on. The first flight follows the plan from the theory, with the abort criteria written down on paper.
9. After the flight: the `.BIN`, `01_after_setup.param`, a comparison with the original.

Hardware acceptance: the six rows of the surface table matched in FBWA and in MANUAL; the failsafe on the ground gave CIRCLE and then RTL; in the log of the first flight `ARSP.Airspeed` differs from the mean `GPS.Spd` over two opposite legs by less than 10 %; in RTL the plane entered a loiter over home at `RTL_ALTITUDE` ± 15 m.

Self-check: the lab is done when:
- step 1: all sixteen pulse widths match exactly, 1700, 1310, 1288, 1740, 1475, 1275, 1700, 1496 for the stick and 1376, 1638, 1595, 1438, 1522, 1633, 1456, 1492 for the tilt, and the surface directions agree with the tables of the theory;
- step 2: outputs 5, 2 and 4 are named with the correct reverse values 1, 1 and 0 and the pulses 1580, 1420, 1456, 1544;
- step 3: the short event at 1.2 s (0.2 s in scenario 2) with a tolerance of 0.05 s, the long one at 5.0–5.4 s; the final modes are RTL, RTL, AUTO, RTL, FBWA;
- step 4: 131.2 ± 0.5 Pa, 2.47 ± 0.01, bank 32.8°, 45° and 25° with a tolerance of 0.2°, 18.4 ± 0.2° and 20 ± 0.5 m;
- step 5: exactly three lines are found: `RC3_MIN`, `ARSPD_USE`, and the pair `TKOFF_THR_MINACC`/`TKOFF_THR_MINSPD`;
- hardware: the four acceptance conditions of the previous paragraph are met, and both parameter files and the log are in your repository.

**Reference for the self-check.** The correct result is the "Result" tables of steps 1–5. Typical wrong ones: (1) a pulse of 1710 instead of 1310 for the right aileron of A: `SERVO5_REVERSED = 1` was forgotten; 1300 instead of 1310: neutral was taken as 1500 and not `SERVO5_TRIM = 1520`; (2) 1450 and 1050 instead of 1475 and 1275 for the elevons: `MIXING_GAIN = 0.5` was skipped; 1725 for the left elevon: "elevator − aileron" and "elevator + aileron" were swapped; (3) in scenario 4 the answer "the mission continues": the action was taken by the mode at the time of the link loss and not at the time of the long event; in scenario 1 a short event at 1.5 s: that is `FS_SHORT_TIMEOUT` from 4.6, which does not exist in 4.7; (4) `ARSPD_RATIO` 2.22 instead of 2.47: the speed ratio was not squared.

## diagnostics
- **Symptom:** in MANUAL the surfaces respond to the sticks correctly, in FBWA the plane rolls over or pitches up
  - Possible cause: the direction was fixed through `RCn_REVERSED` or reversing in the transmitter instead of `SERVOn_REVERSED`; the left and right elevons are swapped; a wrong `AHRS_ORIENTATION`.
  - What to do: MANUAL at once and land; on the bench, check 2 against the table, then check 1.
  - In the log: `ATT.Roll` moves away from `ATT.DesRoll` while `RCOU` of the output grows in the same direction.
  - Consequences: loss of the plane in the first seconds of FBWA, RTL or AUTOTUNE.
- **Symptom:** the elevons lack roll travel and the plane turns sluggishly
  - Possible cause: `MIXING_GAIN = 0.5`, so one demand gives half of the travel.
  - What to do: raise it to 0.7–1.0 or set `MIXING_OFFSET` to 20–50; check that the servo does not bind at full roll with full pitch.
- **Symptom:** the failsafe triggers with the throttle stick down
  - Possible cause: the idle pulse width is not above `THR_FS_VALUE`.
  - What to do: idle 40–50 µs above the threshold, recalibrate the radio.
  - In the log: "Throttle failsafe on" with `RCIN.C3` around 940–950.
- **Symptom:** the transmitter is off, yet the plane keeps flying with the sticks at neutral and does not return
  - Possible cause: `THR_FAILSAFE = 0` or 2; on loss the receiver holds the last values with the throttle above `THR_FS_VALUE`; `FS_SHORT_ACTN = 3` together with `FS_LONG_ACTN = 2`.
  - What to do: `THR_FAILSAFE = 1`, and "no pulses" or throttle below the threshold in the receiver; check on the ground with the propeller off.
- **Symptom:** the mission is aborted and the plane returns although `FS_LONG_ACTN = 0` is set
  - Possible cause: `FS_SHORT_ACTN = 1` put AUTO into CIRCLE, and the long event from CIRCLE gives RTL.
  - What to do: `FS_SHORT_ACTN = 0` if the mission has to continue without a link.
- **Symptom:** the OSD shows airspeed, but TECS holds airspeed poorly and the throttle moves only with pitch
  - Possible cause: `ARSPD_USE = 0`.
  - What to do: `ARSPD_USE = 1` after checking the zero and calibrating `ARSPD_RATIO`.
- **Symptom:** "PreArm: Airspeed: 1 need pre-flight calibration" or an airspeed of 3–5 m/s on the ground
  - Possible cause: the zero was taken in wind with the tube uncovered, or the sensor had not warmed up.
  - What to do: cover the tube, repeat the zero calibration (the preflight calibration command in the ground station), blow into it to check.
- **Symptom:** "Airspeed sensor 1 failure. Disabling" in flight
  - Possible cause: a difference from GPS speed greater than `ARSPD_WIND_MAX` or a failed EKF3 check: the tube came off or took in water, or `ARSPD_RATIO` is wrong.
  - What to do: you can continue, since the firmware has switched to the estimate from GPS and wind; after landing check the tubing and the scale.
- **Symptom:** the motor started right after arming in TAKEOFF
  - Possible cause: `TKOFF_THR_MINACC = 0` and `TKOFF_THR_MINSPD = 0`.
  - What to do: 15 and 4 for a throw; arm only just before the throw.
  - Consequences: a hand injured by the prop.
- **Symptom:** the motor stays silent after the throw
  - Possible cause: no 3D fix; the throw was weaker than `TKOFF_THR_MINACC`; the speed did not reach `TKOFF_THR_MINSPD` within 0.1 s after the pause; after a rudder arm the rudder was not returned to center ("Takeoff waiting for rudder release"); the plane was pitched up more than 45°.
  - What to do: wait for GPS, throw more level and harder, lower `TKOFF_THR_MINACC` to 10–12.
- **Symptom:** in the RTL turn the plane loses altitude and drops a wing
  - Possible cause: `AIRSPEED_MIN` is below 1.2 × V_s, `STALL_PREVENTION = 0`, or with no sensor `TRIM_THROTTLE` is too low.
  - What to do: recalculate V_s for the real mass, raise `AIRSPEED_MIN` and `TRIM_THROTTLE`, reduce `ROLL_LIMIT_DEG`.
- **Symptom:** RTL loiters over home until the battery is flat
  - Possible cause: that is by design: RTL does not land.
  - What to do: a landing sequence with `DO_LAND_START` and `RTL_AUTOLAND`, or `FS_LONG_ACTN = 5` and `BATT_FS_CRT_ACT = 7` (AUTOLAND), or land manually.

## checklist
- `arduplane` is flashed, `00_defaults.param` is saved
- `SERVOn_FUNCTION` is assigned per the layout, the surfaces are neutral at 1500 µs
- Check 2 (FBWA, tilting by hand) is passed for every surface
- Check 1 (MANUAL, sticks) is passed; transmitter reversing was not used
- Idle throttle is 40–50 µs above `THR_FS_VALUE`
- Failsafe on the ground with the propeller off: CIRCLE, then RTL
- `ARSPD_USE = 1` only after the zero check; `ARSPD_AUTOCAL` is back at 0
- `AIRSPEED_MIN` ≥ 1.2 × V_s, `AIRSPEED_MAX` ≥ 1.5 × `AIRSPEED_MIN`
- `TKOFF_THR_MINACC` and `TKOFF_THR_MINSPD` are set for the launch method
- CG is checked, the abort criteria of the first flight are written down
- The `.BIN` and `01_after_setup.param` are saved

## references
- ArduPilot source, tag Copter-4.7.2, directory ArduPlane (version.h "ArduPlane V4.7.2"; Parameters.cpp, servos.cpp, radio.cpp, events.cpp, system.cpp, takeoff.cpp, mode_takeoff.cpp, Attitude.cpp, AP_Arming_Plane.cpp) and libraries (AP_Airspeed, SRV_Channel, RC_Channel, AP_TECS, AC_Fence, AP_Rally) | https://github.com/ArduPilot/ardupilot/tree/Copter-4.7.2/ArduPlane | primary | A
- ArduPlane Release Notes (4.7.0: FS_SHORT_TIMEOUT removed; 4.5.0: airspeed and angle renames) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/ArduPlane/ReleaseNotes.txt | primary | A
- Normal 4 Channel Plane (surface direction checks) — ArduPilot Plane | https://ardupilot.org/plane/docs/guide-four-channel-plane.html | primary | A
- Elevon Planes — ArduPilot Plane | https://ardupilot.org/plane/docs/guide-elevon-plane.html | primary | A
- VTail Planes — ArduPilot Plane | https://ardupilot.org/plane/docs/guide-vtail-plane.html | primary | A
- Plane Failsafe Function — ArduPilot Plane | https://ardupilot.org/plane/docs/apms-failsafe-function.html | primary | A
- Using an Airspeed Sensor — ArduPilot Plane | https://ardupilot.org/plane/docs/airspeed.html | primary | A
- Calibrating an Airspeed Sensor — ArduPilot Plane | https://ardupilot.org/plane/docs/calibrating-an-airspeed-sensor.html | primary | A
- Automatic Takeoff — ArduPilot Plane | https://ardupilot.org/plane/docs/automatic-takeoff.html | primary | A
- TAKEOFF Mode — ArduPilot Plane | https://ardupilot.org/plane/docs/takeoff-mode.html | primary | A
- Arming Plane — ArduPilot Plane | https://ardupilot.org/plane/docs/arming-your-plane.html | primary | A
- ESC Calibration — ArduPilot Plane | https://ardupilot.org/plane/docs/common-esc-calibration.html | primary | A
- Starting up and calibrating Plane — ArduPilot Plane | https://ardupilot.org/plane/docs/starting-up-and-calibrating-arduplane.html | primary | A

## notes
- The "Plane Failsafe Function" page on ardupilot.org gives the short failsafe threshold as "more than 0.5 s"; in the 4.7.2 source it is `RC_FS_TIMEOUT` (1 s) plus 10 radio read cycles for missing frames, and only the 10 cycles for low throttle. The module follows the source.
- In the `MIXING_OFFSET` metadata the unit is given as d% and the range as −1000…1000; the code (`servos.cpp`) uses the value as percent.
- The "controller demand" numbers in the "tilt" case of step 1 are given by the problem statement and are not computed from PID gains.
