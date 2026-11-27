---
id: ap-aux-tune
title: "Switches and knobs: RCx_OPTION, TUNE, and in-flight tuning"
level: L2
readingTime: 55 min
firmware: ArduCopter 4.7 (checked against 4.7.3; the SITL numbers in the practice were captured on 4.6.3)
status: published
added: 2026-11-18
tags:
  - ArduPilot
  - RCx_OPTION
  - aux
  - TUNE
  - switches
  - in-flight tuning
  - E-stop
related:
  - ap-setup-scratch
  - ap-tuning
  - ap-plane-tuning
  - ap-safety-fs
  - ap-osd-video
  - ap-lua
  - link-edgetx
next:
  - ap-tuning
source: content/ardupilot/ap-aux-tune.md
source_hash: e18d3186e4e0
---

## summary
The transmitter channels above the fourth are, in ArduPilot, switches and knobs with an assignable role: `RCx_OPTION` binds one of more than 130 auxiliary functions to a channel, and the `TUNE` parameter turns a knob into a control for a single gain right in flight. Using the ArduCopter and ArduPlane 4.7.2 source, this module works out how the firmware reads a switch (the 1200 and 1800 µs thresholds, the 200 ms debounce, what happens at power-up), which function numbers a copter and a plane actually need, which of them bring the vehicle down, how the value from a knob is calculated, and why it is not saved. After the module you can lay out switches without dangerous combinations and tune one gain within a narrow range. The lab is a calculation exercise with no hardware and no simulator: a timeline of switch events, knob values, and finding three errors in a layout.

## theory
### Two kinds of channels: mode and aux
- **The mode channel** is set by `FLTMODE_CH` (5 by default on Copter). It is a 6-position switch: boundaries at 1231, 1361, 1491, 1621, and 1750 µs divide the channel into positions 1–6, and the position selects `FLTMODE1`…`FLTMODE6`.
- **An aux channel** is any channel 1–16 with an `RCx_OPTION` other than 0. It is read as a three-position switch: LOW, MIDDLE, HIGH. The exceptions: `94` (VTX power) is read as a six-position switch, and `212–217` (gimbal axes) and `219`, `220` (tuning knobs) take the whole channel value.

One channel cannot be both: arming is refused with `PreArm: Mode channel and RC5_OPTION conflict`. One function on two channels gives `PreArm: Duplicate Aux Switch Options` (`AP_Arming.cpp`, lines 826–831).

On the transmitter side a switch is a channel mix on a switch source: EdgeTX outputs 988, 1500, and 2012 µs for the three positions, and a knob outputs the whole range (`link-edgetx`).

### How the firmware reads a switch
The `read_aux_all` task runs 10 times per second and only with a healthy RC link: on Copter the switches are not read at all during a radio failsafe.

| What | Value in 4.7.2 | Where in the source |
|---|---|---|
| A pulse counts as invalid | ≤ 800 or ≥ 2200 µs | `RC_MIN_LIMIT_PWM`, `RC_MAX_LIMIT_PWM` |
| LOW | < 1200 µs | `AUX_SWITCH_PWM_TRIGGER_LOW` |
| HIGH | > 1800 µs | `AUX_SWITCH_PWM_TRIGGER_HIGH` |
| MIDDLE | 1200…1800 µs inclusive | `read_3pos_switch` |
| Debounce time | 200 ms | `SWITCH_DEBOUNCE_TIME_MS` |
| Aux polling rate | 10 Hz (Copter and Plane) | `Copter.cpp:161`, `Plane.cpp:134` |
| Mode channel polling rate | 250 Hz on Copter, 7 Hz on Plane | `Copter.cpp:151`, `Plane.cpp:72` |
| Reversing a switch | `RCx_REVERSED = 1` **and** bit 7 (128) in `RC_OPTIONS` | `ALLOW_SWITCH_REV` |

There is no hysteresis: the "dead band" between the thresholds is the MIDDLE position. A channel sitting at 1795 µs is in the middle for the firmware, not high; a two-position switch with incomplete travel (1250…1750) never triggers.

A function is called **on a change** of position, not continuously. The new position has to hold for 200 ms: on the tick where it is first seen, the time is remembered; the function is called on the first tick where at least 200 ms have passed. With polling every 100 ms, 200–300 ms pass between the flick and the action. If the position changes again during that time (a three-position switch passing through the middle, a 180 ms glitch), the count starts over and the intermediate position is not executed.

Every call is logged as an `AUXF` message: `function` (the number), `pos` (0 LOW, 1 MIDDLE, 2 HIGH), `source` (0 INIT, 1 RC, 2 button, 3 MAVLink, 4 mission, 5 scripting), `index`, `result`. For some functions a line such as `RC7: MotorEStop HIGH` arrives in Messages. The same function can be triggered without a transmitter by the `MAV_CMD_DO_AUX_FUNCTION` command from a ground station and by the `DO_AUX_FUNCTION` mission item.

{{diagram:ap-aux-eval-flow|A switch is executed on a change of position after 200 ms; on the first receiver frame every function is executed except four: arming (153, 154, 165) and parachute release (22) only remember the position.}}

### What happens at power-up
There are two stages.

1. **Initialization** (`init_aux_all`, before flight). The position is read once; if the receiver has not delivered a frame yet, it counts as LOW. For "state" functions their action is called with the INIT source: `3`, `13`, `14`, `31`, `32`, `39`, `84`, `11`, `21`, `23`, `46`, `65`, `165`, `166–169`, `219`, `220`, and others. For "event" functions (modes, `153`, `81`, relays, `9`, scripting, `94`) nothing is done at this stage.
2. **The first receiver frame.** The remembered position of a channel is initially "none" (−1), so any current position counts as a change and is executed after 200 ms, LOW included. A relay switch in HIGH turns the relay on 200 ms after the link appears, and a `4` switch in HIGH tries to engage RTL.

The exception is the four functions for which `init_position_on_first_radio_read` returns `true`: `153` ArmDisarm, `154` ArmDisarm with AirMode, `165` Arm/E-Stop, and `22` parachute release. For them the first position read is only remembered. If you switch on the transmitter with the arming switch in HIGH, nothing happens; to arm, you have to lower the switch and raise it again.

### Functions by purpose
The numbers are checked against `enum class AUX_FUNC` in `RC_Channel.h` of the Copter-4.7.2 tag. "C" means available on Copter, "P" on Plane.

| Group | Number: function |
|---|---|
| Copter modes (HIGH engages; otherwise return to the mode channel, if that mode is still active) | 4 RTL, 16 AUTO, 18 LAND, 33 BRAKE, 42 SmartRTL, 52 ACRO, 55 GUIDED, 56 LOITER, 68 STABILIZE, 69 POSHOLD, 70 ALTHOLD, 72 CIRCLE, 99 AUTO RTL, 2 FLIP, 37 THROW, 151 TURTLE |
| Plane modes | 4 RTL, 16 AUTO, 51 MANUAL, 52 ACRO, 55 GUIDED, 56 LOITER, 72 CIRCLE, 77 TAKEOFF, 92 FBWA, 98 TRAINING, 108 QRTL, 150 CRUISE, 170 QSTABILIZE, 183 AUTOLAND (new in 4.7), 96 re-read the mode channel; the modes themselves, their numbers, and a plane's `FLTMODE_CH` are in `ap-setup-plane` |
| Arming and motors (C, P) | 153 ArmDisarm, 154 ArmDisarm with AirMode, 81 Disarm, 165 Arm/E-Stop, 31 Motor Emergency Stop, 32 Motor Interlock (C) |
| Waypoints and trims | 5 Save Trim (C), 7 Save WP (C), 24 reset the mission to the start, 58 clear the mission, 155 trims from the current surface positions (P) |
| Feel and pilot assistance (C) | 3 Simple, 13 Super Simple (middle is Simple, high is Super Simple), 152 Simple heading reset, 14 Acro Trainer (off / leveling / limited), 84 AirMode (also P), 39 Precision Loiter, 10 rangefinder, 40 object avoidance |
| Protection | 11 Fence, 21 parachute enable, 22 parachute release, 23 parachute 3-position, 29 landing gear (LOW deploys, HIGH retracts), 30 lost-vehicle sound, 46 allow RC override, 90 EKF source set, 65 disable GPS (for testing) |
| Camera and gimbal | 9 shutter, 166 video recording, 167 zoom, 168 manual focus, 169 autofocus, 102 camera mode, 175 lens, 174 tracking, 27 and 113 retract mount 1 and 2, 163 Mount Yaw Lock (Mount Lock in 4.6), 185 Roll/Pitch Lock and 186 POI Lock (new in 4.7), 212–217 axes of mount 1 and 2, 19 gripper |
| Relays | 28 relay 1, 34–36 relays 2–4, 66 and 67 relays 5 and 6 (HIGH turns on, MIDDLE and LOW turn off; `ap-outputs`) |
| Video | 94 VTX power (six positions), 78 and 79 RunCam |
| Tuning | 17 AUTOTUNE (C), 180 test the tuned gains, 107 fixed-wing autotune (P), 181 QuickTune (P), 182 AHRS AutoTrim (C, new in 4.7), 162 FFT notch tune, 219 and 220 tuning knobs (C) |
| Scripting | 300–315 Scripting1–16 (in 4.6.3, only 300–307), 316 stop (HIGH) or restart (LOW) all scripts |
| Other | 164 pause logging, 171 compass calibration (only while disarmed), 178 pause the mode |

The OSD screen is not on this list: it is switched by a separate channel, `OSD_CHAN`, with the `OSD_SW_METHOD` logic (`ap-osd-video`). Number `41` (arming from 4.1 and earlier) is still in the metadata, but on Copter it is automatically replaced with `154` at boot.

For VTX power the six positions are converted to a level: `round(N · (position + 1) / 6 − 1)`, where N is the number of available levels and the position is counted from zero. With three levels, positions 1–2 give the lowest, 3–4 the middle, and 5–6 the highest.

### Dangerous functions: the exact behavior
| Function | What the firmware does | Why it is dangerous |
|---|---|---|
| `31` Motor Emergency Stop | HIGH: `set_emergency_stop(true)`, so the motor and thrust outputs go to zero immediately, in any mode and at any altitude; the vehicle stays armed, and the `DISARM_DELAY` auto-disarm delay is halved. LOW clears the stop, MIDDLE changes nothing | A switch bumped in flight = a crash. If it goes back to LOW before the auto-disarm, the motors start again. While the stop is active, arming is refused: `Motors Emergency Stopped` |
| `153`, `154` ArmDisarm | HIGH arms with all the checks; LOW disarms; MIDDLE does nothing | Disarming with the switch does not check whether the vehicle is flying: the "in the air" block exists only for MAVLink and for the rudder stick (`AP_Arming_Copter.cpp:790–808`) |
| `81` Disarm | HIGH disarms with no in-flight check; while the switch is in HIGH, arming is refused: `Disarm Switch on` | The same as above |
| `165` Arm/E-Stop | HIGH clears the stop and arms; MIDDLE clears the stop; LOW stops the motors | Three states on one switch: LOW in flight kills the motors |
| `32` Motor Interlock | HIGH and MIDDLE allow the motors to spin, LOW stops them while armed | Made for helicopters; on a multicopter it acts as a second E-Stop |
| `22`, `23` parachute | HIGH: if `CHUTE_ENABLED = 1`, the vehicle is not on the ground, and it is above `CHUTE_ALT_MIN`, the motors are disarmed and the parachute is released; otherwise `Parachute: Landed` or `Parachute: Too low` | An accidental release = a landing under the canopy wherever the vehicle was. `23` has no first-frame protection: it relies on the vehicle being disarmed at power-up |
| `65`, `105`; `100`, `101`, `110` | 65 disables GPS, 105 disables GPS yaw; 100, 101, and 110 "kill" IMU 1, 2, and 3, all for failure testing | For the bench and SITL only |

The answer to the common question "the motors cut out in the air" starts with the log: the disarm event and the `AUXF` lines with functions 31, 81, 153, 165 show whether it was a switch (`ap-safety-fs`). The second half of the rule: a mode that needs no GPS (Stabilize or AltHold) must be on a known position of the mode channel, so you can switch to it during toilet bowling or a flyaway without looking at the transmitter.

### Copter: `TUNE` and the knob
The mechanism in 4.7.2 is the same as in 4.6.3: a channel with `RCx_OPTION = 219` (before 4.6, channel 6 was hard-coded), `TUNE` selects what to change, and `TUNE_MIN` and `TUNE_MAX` are the values at the ends of the travel. What changed in 4.7:

- a second knob appeared: `RCx_OPTION = 220` with the parameters `TUNE2`, `TUNE2_MIN`, `TUNE2_MAX`. The number 220 is not in the `RCx_OPTION` value list of the 4.7.2 metadata, so you enter it by hand;
- tuning is off when `TUNE_MIN` equals `TUNE_MAX` (in 4.6.3, only when both are zero);
- the `NIn` field was added to the `PTUN` log, and the value 60 appeared in the `TUNE` list.

The channel is looked up once at boot (`radio.cpp:35`), so a reboot is needed after assigning 219. The calculation runs 3 times per second:

```
n = 2 · ((PWM − RCx_MIN) / (RCx_MAX − RCx_MIN) − 0.5),  constrained to −1…+1
value = TUNE_MIN + (TUNE_MAX − TUNE_MIN) · (n + 1) / 2
```

`RCx_TRIM` and the dead zone are not involved. `RCx_REVERSED = 1` flips the sign of n, here without bit 7 in `RC_OPTIONS`. `TUNE_MIN` can be greater than `TUNE_MAX`: the knob then simply works the other way around.

| `TUNE` | What changes (4.7.2 names) | Unit of the value |
|---|---|---|
| 1 | `ATC_ANG_RLL_P` and `ATC_ANG_PIT_P` | — |
| 3 | `ATC_ANG_YAW_P` | — |
| 4 / 5 / 21 | `ATC_RAT_RLL_P/I/D` and `ATC_RAT_PIT_P/I/D` together | — |
| 49 / 50 / 51 | `ATC_RAT_RLL_P` / `I` / `D` | — |
| 46 / 47 / 48 | `ATC_RAT_PIT_P` / `I` / `D` | — |
| 6 / 26 / 56 | `ATC_RAT_YAW_P` / `D` / `FLTE` | —, —, Hz |
| 55 | `MOT_YAW_HEADROOM` | PWM |
| 14 | `PSC_D_POS_P` (before 4.7, `PSC_POSZ_P`) | — |
| 7 | `PSC_D_VEL_P` | — |
| 34 / 35 / 36 | `PSC_D_ACC_P/I/D` (before 4.7, `PSC_ACCZ_*`, with values 10 times larger) | — |
| 12 | `PSC_NE_POS_P` | — |
| 22 / 28 | `PSC_NE_VEL_P` / `I` | — |
| 10 | waypoint speed | **cm/s**, although `WP_SPD` is in m/s in 4.7 |
| 60 | `LOIT_SPEED_MS` | m/s |
| 59 | the lean angle limit of the position controller (it overrides `PSC_ANGLE_MAX`; the parameter itself does not change) | degrees |
| 25 / 40 | Acro rates: roll and pitch / yaw | deg/s |
| 45 | `ATC_INPUT_TC` | s |
| 39 | the Circle rate | deg/s |
| 38 | magnetic declination | degrees |
| 58 | the System ID signal magnitude | — |
| 13, 52–54 | helicopter only: external gyro, FF per axis | — |

**What is saved.** Nothing. The value is written to the in-memory copy of the parameter (`set_kP`): the ground station shows it if you re-read the parameters, but after a reboot the saved value comes back. To keep what you found: without touching the knob, re-read the parameters, write the value from the ground station, then set `TUNE = 0`. If you simply set `TUNE = 0` in flight, the gain stays at the knob's last value until a reboot.

**Log.** `PTUN`: `Param` (the number from `TUNE`), `TunVal` (the value set), `TunMin`, `TunMax`, `NIn` (n from −1 to +1). The knob also leaves `AUXF` records with function 219 every time it crosses 1200 and 1800 µs; there is no action behind them.

**The low-position trap.** Tuning works on the ground and while disarmed too. A knob left at the bottom sets the gain to `TUNE_MIN` a third of a second after the link appears. The course audit reproduced this in SITL on 4.6.3: an `ATC_RAT_RLL_P` of 0.135 with a range of 0.05…0.25 became 0.05 without a single movement, 63% lower. During a radio failsafe the calculation stops, and the value freezes at the last one.

{{diagram:chart-ap-aux-tune-knob|The value is linear between RC6_MIN and RC6_MAX and is clamped beyond them: a knob at the bottom gives TUNE_MIN = 0.05 instead of the saved 0.135, and the only way back to 0.135 is the 1440 µs position.}}

### Plane: `TUNE_PARAM` and the selector
Plane has a different mechanism, the `AP_Tuning` library. It is relative: the knob multiplies the starting value instead of setting an absolute one.

| Parameter | Default | Meaning |
|---|---|---|
| `TUNE_CHAN` | 0 (disabled) | the knob channel, 5–16 |
| `TUNE_CHAN_MIN`, `TUNE_CHAN_MAX` | 1000, 2000 µs | the knob travel (not `RCx_MIN/MAX`) |
| `TUNE_PARAM` | 0 | a single parameter (1–26 are the QuadPlane VTOL gains, `Q_A_*` and `Q_P_*`, 50–57 the wing: `RLL_RATE_P/I/D/FF`, `PTCH_RATE_P/I/D/FF`) or a set, 101–110 |
| `TUNE_SELECTOR` | 0 | the selector switch channel, preferably spring-loaded; HIGH is ≥ 1700, LOW is ≤ 1300 µs |
| `TUNE_RANGE` | 2 | the factor by which the value changes toward the ends; the firmware does not accept less than 1.1 |
| `TUNE_MODE_REVERT` | 1 | revert unsaved values on a mode change |
| `TUNE_ERR_THRESH` | 0.15 | the oscillation warning threshold; in the 4.7.2 tree the variable is declared but never read |

The sets: 101 is roll D and PI, then pitch D and PI; 102 and 103 are the same for one axis; 104 is yaw P, I, D; 105 is the roll and pitch angle P; 106 is velocity P and I; 107 is vertical acceleration P, I, D; 108–110 are D and P for one axis. The source also has sets 111–113 for the wing, which are not in the metadata.

The logic (polled at 10 Hz):

1. After a parameter is selected, the knob has to pass **through the middle** (within ±1% of the travel of the middle, ±10 µs with the default 1000…2000, or across it): until then the value does not change.
2. Above the middle: `center · (1 + c · (RANGE − 1))`; below it: `center / RANGE + (c + 1) · (center − center / RANGE)`, where c goes from −1 to +1. With `RANGE = 2` and a center of 0.3 the ends give 0.15 and 0.6.
3. The selector, held in HIGH and released: shorter than 0.2 s is ignored; 0.2–2 s makes the current value the new center (`Tuning: recentered`); 2–5 s moves to the next parameter of the set (`Tuning: started …`).
4. A hold longer than 5 s, if the value has changed: the set's parameters are saved (`Tuning: Saved`).
5. A flight mode change with `TUNE_MODE_REVERT = 1` reverts what was not saved (`Tuning: reverted`).

The log is the `PRTN` message: `Set`, `Parm`, `Value`, `CenterValue`. Tuning the wing itself is covered in `ap-plane-tuning`.

### Scripts, QuikTune, and AUTOTUNE on a switch
- **Scripts.** `RCx_OPTION = 300…315` do nothing by themselves; a script reads the position with `rc:get_aux_cached(300)`, which gives 0, 1, 2, or `nil` while the function has never been called (that is, for the first 200 ms after the link appears). The details are in `ap-lua`.
- **QuikTune.** In Copter 4.7.2 this is still the Lua script `VTOL-quicktune.lua`: `QUIK_ENABLE = 1`, and the switch is the function from `QUIK_RC_FUNC` (300 by default); LOW stops and restores the original values, MIDDLE tunes, HIGH saves. The QuickTune built into the firmware (`AP_Quicktune`, the `QWIK_*` parameters, function `181`) is built only into Plane for QuadPlane; the Copter 4.7.2 code does not have it.
- **AUTOTUNE.** `17` engages AutoTune mode in HIGH and returns to the mode from the mode channel in the other positions; `180` switches between the tuned and the original gains after the tune. On Plane the fixed-wing autotune is `107`. The procedure itself is in `ap-tuning`.

### Safely tuning one gain
1. Write down the current value from the ground station. The range is ±20% around it: for `ATC_RAT_RLL_D = 0.0036` that is `TUNE_MIN = 0.00288`, `TUNE_MAX = 0.00432`. Then the middle of the travel equals the original value, and the low-position trap costs only 20%.
2. One axis, one number: `51` (roll D), not `21`, which writes one number to both axes and wipes out the difference left by AutoTune.
3. Knob to the middle before applying power; after boot, check in the ground station that the value equals the original.
4. Tune in a mode that uses this gain: there is no point turning `14` in Stabilize.
5. After landing, write the value you found from the ground station, set `TUNE = 0`, reboot, and confirm that it stayed.

### Place in the system
- **Receives:** channels and their ranges from the receiver and the radio calibration (`ap-setup-scratch`), the transmitter's switch and knob layout (`link-edgetx`), and the starting gains and the tuning order from `ap-tuning` and `ap-plane-tuning`.
- **Provides:** mode, arming, and motor stop commands to the safety logic (`ap-safety-fs`); switch positions to scripts (`ap-lua`), relays and the camera (`ap-outputs`), and VTX power (`ap-osd-video`); the tuned gains to the control loops.
- **If you get it wrong here:** a bumped `31` or `153` switch looks like a "motor failure" in the log and sends the search off to `ap-safety-fs`; a knob left at the bottom lowers a gain, and people start treating the sluggish control in `ap-tuning`; a switch that was not actually reversed triggers in the opposite position.

## practice
The lab is a calculation exercise: you need neither a flight controller nor a simulator. All parameter files below are a training example assembled by hand; they are not a dump from a real vehicle. Every answer follows from the tables and formulas in the theory. An assumption for the timing: aux is read exactly at the 0, 100, 200 ms marks and so on, with mark 0 being the first receiver frame; in the real firmware the tick drifts by a few milliseconds.

```
# training example, assembled by hand
FLTMODE_CH,5
RC_OPTIONS,32
RC6_MIN,1100
RC6_MAX,1900
RC6_TRIM,1500
RC6_REVERSED,0
RC6_OPTION,219
RC7_OPTION,153
RC8_OPTION,31
RC9_OPTION,4
RC10_OPTION,28
RC11_OPTION,22
TUNE,4
TUNE_MIN,0.05
TUNE_MAX,0.25
ATC_RAT_RLL_P,0.135
ATC_RAT_PIT_P,0.135
```

### Step 1. Timeline of switch events
At the moment of the first frame the channels are: CH7 = 2000, CH8 = 1000, CH9 = 2000, CH10 = 1500, CH11 = 2000. Then the pilot moves the switches (time in ms from the first frame):

| t, ms | Channel | New value, µs |
|---|---|---|
| 1030 | CH7 | 1000 |
| 2050 | CH7 | 2000 |
| 3020 | CH10 | 1810 |
| 4010 | CH8 | 1900 |
| 4190 | CH8 | 1000 |
| 5010 | CH10 | 1795 |
| 6040 | CH9 | 1200 |
| 7070 | CH8 | 1850 |

Write the list of function calls for channels 7–11 as it would appear in `AUXF`: time, function number, position. Separately, name the functions that do nothing on the first frame. The timing rule: the first polling mark not earlier than the change, plus 200 ms.

Result: nine calls:

| t, ms | Function | Position | What it means |
|---|---|---|---|
| 200 | 31 | LOW | the motor stop is cleared |
| 200 | 4 | HIGH | an attempt to engage RTL right after the link appears |
| 200 | 28 | MIDDLE | relay 1 is off |
| 1300 | 153 | LOW | disarm (the vehicle is disarmed anyway) |
| 2300 | 153 | HIGH | arm with the checks |
| 3300 | 28 | HIGH | relay 1 is on |
| 5300 | 28 | MIDDLE | relay 1 is off: 1795 µs is no longer HIGH |
| 6300 | 4 | MIDDLE | 1200 µs is not LOW yet; return to the mode channel if RTL is active |
| 7300 | 31 | HIGH | the motors are stopped, and the vehicle is armed |

On the first frame `153` (CH7) and `22` (CH11) do nothing: the HIGH position is only remembered. The parachute is not triggered once in the whole timeline. The 180 ms pulse on CH8 (4010–4190) is not executed: HIGH is seen at the 4100 mark, and at the 4200 mark the channel is back in LOW.

### Step 2. The value from the knob
With the formula from the theory, find `ATC_RAT_RLL_P` for CH6 = 2000, 1000, 1500, 1750, 1300 µs; for 1750 µs with `RC6_REVERSED = 1`; the knob position at which the value equals the saved 0.135; and the value after a reboot if the knob was left at 1000 µs, and if `TUNE = 0` was written before the reboot.

Result. 2000 µs → n = +1 (clamped) → **0.25**; 1000 → n = −1 → **0.05**; 1500 → n = 0 → **0.15**; 1750 → (1750 − 1100) / 800 = 0.8125 → 0.05 + 0.2 · 0.8125 = **0.2125**; 1300 → 0.25 → **0.10**. With the reversal 1750 µs gives 0.05 + 0.2 · 0.1875 = **0.0875**. For 0.135: the fraction is (0.135 − 0.05) / 0.2 = 0.425, so the position is 1100 + 0.425 · 800 = **1440 µs**. After a reboot 0.135 is loaded, and on the first good frame a knob at 1000 µs sets **0.05**; with `TUNE = 0` it stays **0.135**. Pitch gets the same numbers: `TUNE = 4` writes to both axes.

The series 0.25 / 0.05 / 0.15 / 0.2125 and the return to 0.135 after a restart were measured by the course audit in SITL on Copter 4.6.3. Here the same numbers are obtained by calculation from the 4.7.2 code (`norm_input_ignore_trim` and `linear_interpolate` did not change in this part); the series was not measured again in SITL 4.7.2.

### Step 3. Three errors in a layout
A quadcopter; the pilot wants: arming on CH5, RTL on CH7, a motor stop on CH9 with "down means stop" (the channel is reversed for that), tuning of the roll and pitch P with the knob on CH6, and the pitch D with a second knob on CH12. Find the three assignments with which the vehicle will not arm or is dangerous.

```
# training example, assembled by hand
FLTMODE_CH,5
RC_OPTIONS,32
RC5_OPTION,153
RC6_OPTION,219
RC6_MIN,1100
RC6_MAX,1900
RC7_OPTION,4
RC8_OPTION,28
RC9_OPTION,31
RC9_REVERSED,1
RC10_OPTION,300
RC11_OPTION,94
RC12_OPTION,220
SCR_ENABLE,1
TUNE,4
TUNE_MIN,0
TUNE_MAX,0.5
TUNE2,48
TUNE2_MIN,0.0029
TUNE2_MAX,0.0043
ATC_RAT_RLL_P,0.135
ATC_RAT_PIT_P,0.135
ATC_RAT_PIT_D,0.0036
```

Result: there are exactly three errors. (1) `RC5_OPTION = 153` with `FLTMODE_CH = 5`: arming is refused with `PreArm: Mode channel and RC5_OPTION conflict`; move the arming function or change `FLTMODE_CH`. (2) `RC9_REVERSED = 1` with `RC_OPTIONS = 32`: bit 7 (128) is not set, so the switch reversal has no effect, and the motors are stopped by the "up" position, not "down" as the pilot intended; it needs `RC_OPTIONS = 160`. (3) `TUNE_MIN = 0`, `TUNE_MAX = 0.5`: the knob at the bottom gives P = 0 on roll and pitch, and at the top 0.5, which is 3.7 times the original; the original 0.135 is reached only at 1100 + 0.135 / 0.5 · 800 = 1316 µs. You need a ±20% range: 0.108…0.162. The rest is correct: `220` is the second knob of 4.7, `TUNE2 = 48` changes only the pitch D within 0.0029…0.0043 (about ±20% of 0.0036), `300` goes with `SCR_ENABLE = 1`, and `94` and `28` are each assigned once.

### Moving to real hardware
The propellers are off until item 4.

1. On the ground station's radio page, write down the value of every switch in every position: LOW must be below 1200 and HIGH above 1800 µs. For the knob, write its end values to `RCx_MIN` and `RCx_MAX` (the radio calibration).
2. Assign the functions and reboot. Messages must not contain `PreArm` failures about `OPTION`.
3. Flick every switch and check the line in Messages or the `AUXF` record in the log. Power up with the arming switch in HIGH: it must not arm.
4. Tuning: follow the procedure from the theory, a ±20% range, the knob in the middle before applying power. Hover at 2–3 m in a mode that uses the gain; after landing, `PTUN.TunVal` in the log changes only within `TunMin…TunMax`.

On hardware the work is done when every switch gives the expected `AUXF` record with the right position, powering up with the arming switch in HIGH does not arm, and the gain you found reads the same after being written and a reboot.

Self-check: the lab is done when:
- step 1: you got exactly nine calls, the times 200, 200, 200, 1300, 2300, 3300, 5300, 6300, and 7300 ms match exactly (under the assumption about the ticks), and the functions and positions are as in the table; the functions not executed on the first frame are `153` and `22`; the 4010–4190 pulse is not on the list;
- step 2: 0.25, 0.05, 0.15, 0.2125, 0.10, and 0.0875 match within ±0.0001; the position for 0.135 is 1440 ± 1 µs; after a reboot, 0.05 with the knob at the bottom and 0.135 with `TUNE = 0`;
- step 3: exactly three errors are found: the conflict with the mode channel, the E-Stop reversal that has no effect, and the 0…0.5 range; `RC_OPTIONS = 160` and the position 1316 ± 1 µs are named.

**Reference for the self-check.** The correct result is the step 1 table, the step 2 numbers, and the three errors of step 3. Typical mistakes: (1) in step 1 the times came out as 1230, 2250, 3220, because 200 ms was added to the moment of the flick without rounding up to a polling mark; or the list has an arm at the 200 ms mark, forgetting that `153` only remembers the position on the first frame. (2) In step 1 the relay "stayed on" after 5010 ms, and RTL was "turned off as LOW" at 1200 µs: the thresholds are strict, and 1200 and 1800 µs inclusive are MIDDLE. (3) In step 2 you got 0.20 for 1750 µs: the 1000…2000 range was used instead of `RC6_MIN…RC6_MAX`; or you got 0.135 for 1500 µs: the middle of the travel equals the middle of `TUNE_MIN…TUNE_MAX`, not the saved value. (4) In step 3 `220` or `RC8_OPTION = 28` was named as an error: the first is a legitimate second knob, and the second is assigned once.

## diagnostics
- **Symptom:** a switch does nothing, and there is no `AUXF` record.
  Possible cause: the channel value does not go beyond 1200 or 1800 µs (incomplete travel, a mix with a 50% weight); it is the wrong channel; a radio failsafe is active.
  What to do: look at the channel value on the radio page in both positions; fix the mix on the transmitter (`link-edgetx`); check the channel number in `RCx_OPTION`.
- **Symptom:** arming is refused: `PreArm: Mode channel and RCn_OPTION conflict` or `Duplicate Aux Switch Options`.
  Possible cause: a function is assigned to the `FLTMODE_CH` channel; one function is on two channels (often after loading someone else's parameter file).
  What to do: dump all `RC*_OPTION` values and `FLTMODE_CH`, and remove the clashes.
- **Symptom:** you switched on the transmitter with the arming switch up, and the vehicle does not arm.
  Possible cause: the built-in first-frame protection for 153, 154, 165.
  What to do: lower the switch, wait half a second, raise it again; look for the reasons for a refusal in Messages.
- **Symptom:** the motors cut out in the air, and the log has no power errors.
  Possible cause: a 31, 81, 153, or 165 switch was bumped.
  In the log: an `AUXF` with that function and `source = 1` a fraction of a second before the disarm or motor stop event.
  What to do: move the function to a locking switch or to a two-position switch away from the mode switch; do not put E-Stop on a three-position switch next to one you use often.
  Consequences: a fall from any altitude.
- **Symptom:** arming is refused: `Motors Emergency Stopped` or `Disarm Switch on`.
  Possible cause: a 31 or 81 switch is in HIGH; for 31, the channel is reversed on the transmitter.
  What to do: put the switch back in LOW; check the channel direction.
- **Symptom:** `RCx_REVERSED = 1` does not reverse the switch.
  Possible cause: `RC_OPTIONS` does not have bit 7 (128).
  What to do: add 128 to the current `RC_OPTIONS` value or reverse the channel on the transmitter.
- **Symptom:** after power-up the vehicle is sluggish or oscillates although the settings were not changed.
  Possible cause: `TUNE` is not 0 and the knob is at an end, so the gain equals `TUNE_MIN` or `TUNE_MAX`.
  In the log: `PTUN` is logged from the moment the link appears, and `NIn` is −1 or +1.
  What to do: re-read the parameters and compare them with the saved file; set `TUNE = 0` and reboot.
- **Symptom:** the knob does not change the parameter.
  Possible cause: there was no reboot after assigning 219; `TUNE_MIN` equals `TUNE_MAX`; `RCx_MIN/MAX` are not calibrated to the knob travel; the value was not re-read in the ground station.
  What to do: reboot, check the range, refresh the parameters; look for `PTUN` in the log.
- **Symptom:** a gain found in flight was gone after a reboot.
  Possible cause: tuning writes only to RAM.
  What to do: after landing, without touching the knob, write the value from the ground station, then set `TUNE = 0`.
- **Symptom:** `TUNE = 10`, and the vehicle barely moves along the route in Auto.
  Possible cause: the range was given in m/s (for example 5…15), while function 10 takes cm/s: the speed became 0.05…0.15 m/s.
  What to do: set `TUNE_MIN` and `TUNE_MAX` in cm/s: 500…1500.
- **Symptom:** Plane: the knob has no effect after a parameter is selected, and there are no `Tuning:` messages.
  Possible cause: the knob did not pass through the middle; the selector is held in HIGH; `TUNE_CHAN_MIN/MAX` do not match the knob travel; for parameters 1–26 there is no QuadPlane.
  What to do: move the knob through the center, release the selector, compare the travel with 1000…2000 µs.
- **Symptom:** Plane: the values you found disappeared after a mode change.
  Possible cause: `TUNE_MODE_REVERT = 1` and the values were not saved.
  What to do: before changing the mode, hold the selector in HIGH for more than 5 s until the `Tuning: Saved` message.

## checklist
- Every switch has LOW below 1200 and HIGH above 1800 µs, checked on the radio page
- `FLTMODE_CH` does not coincide with any channel whose `RCx_OPTION` is not 0; no function is duplicated
- Functions 31, 81, 153, 165 are on switches that cannot be bumped by accident; their positions are written down
- A mode that needs no GPS (Stabilize or AltHold) is on a known position of the mode channel
- Reversed switches: either reversed on the transmitter, or bit 7 in `RC_OPTIONS`
- Powering up with the arming switch in HIGH has been tested: it does not arm
- Before tuning: the original value is written down, the range is ±20%, the knob is in the middle before applying power
- One axis, one `TUNE` number; the combined ones (4, 5, 21) only when roll and pitch are equal
- After tuning: the value is written from the ground station, `TUNE = 0`, a reboot, a check
- `AUXF` and `PTUN` are reviewed in the log after the flight

## references
- ArduPilot Copter-4.7.2 RC_Channel.h (AUX_FUNC numbers, the 1200/1800 thresholds, the 800/2200 limits) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/RC_Channel/RC_Channel.h | primary | A
- ArduPilot Copter-4.7.2 RC_Channel.cpp (200 ms debounce, read_aux, init_aux_function, six positions, AUXF, norm_input_ignore_trim) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/RC_Channel/RC_Channel.cpp | primary | A
- ArduPilot Copter-4.7.2 RC_Channel_Copter.cpp (Copter functions, initialization at boot) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/ArduCopter/RC_Channel_Copter.cpp | primary | A
- ArduPilot Copter-4.7.2 tuning.cpp (TUNE: the formula and the parameter list) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/ArduCopter/tuning.cpp | primary | A
- ArduPilot Copter-4.7.2 Parameters.cpp (TUNE, TUNE_MIN/MAX, TUNE2*) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/ArduCopter/Parameters.cpp | primary | A
- ArduPilot Copter-4.7.2 Log.cpp (the PTUN message) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/ArduCopter/Log.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_Arming.cpp and AP_Arming_Copter.cpp (switch checks, disarming) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_Arming/AP_Arming.cpp | primary | A
- ArduPilot Plane-4.7.2 AP_Tuning.cpp (TUNE_CHAN, the selector, PRTN) | https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.2/libraries/AP_Tuning/AP_Tuning.cpp | primary | A
- ArduPilot Plane-4.7.2 ArduPlane/tuning.cpp (TUNE_PARAM and the sets) | https://github.com/ArduPilot/ardupilot/blob/Plane-4.7.2/ArduPlane/tuning.cpp | primary | A
- ArduPilot Copter-4.7.2 VTOL-quicktune.lua (QUIK_RC_FUNC, the switch positions) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_Scripting/applets/VTOL-quicktune.lua | primary | A
- Auxiliary Functions — ArduPilot Copter | https://ardupilot.org/copter/docs/common-auxiliary-functions.html | primary | A
- Transmitter Based Tuning — ArduPilot Copter | https://ardupilot.org/copter/docs/common-transmitter-tuning.html | primary | A

## notes
All numbers, thresholds, and formulas were checked in the tree of the Copter-4.7.2 tag (which is also Plane-4.7.2); the differences from 4.6.3 by comparison with the 4.6.3 tree and with the parameter metadata of both releases. The SITL numbers (0.25 / 0.05 / 0.15 / 0.2125, the return to 0.135, the low-position trap) were measured by the course audit on Copter 4.6.3; for 4.7.2 they are obtained by calculation from the code and were not captured again in the simulator. The trigger times in the lab are a calculation for an ideal 100 ms tick. The 988 / 1500 / 2012 µs values for EdgeTX are taken from `link-edgetx` (EdgeTX 2.12.5) and were not rechecked here. The names of ground station screens are not confirmed by the source.
