---
id: px4-rc-tuning
source: content/px4/px4-rc-tuning.md
source_hash: a328681be4c5
title: "PX4: modes on switches, AUX channels and in-flight tuning (RC_MAP_PARAM)"
level: L2
readingTime: 55 min
firmware: PX4 1.18 (checked against v1.18.0)
status: published
added: 2026-11-22
tags:
  - PX4
  - transmitter
  - flight modes
  - switches
  - in-flight tuning
related:
  - px4-setup-scratch
  - px4-safety-return
  - px4-outputs-servos
  - px4-hardware-peripherals
  - px4-control
  - px4-ros2
  - link-edgetx
  - link-elrs
  - ap-aux-tune
  - inav-adjustments
next:
  - px4-control
---

## summary
Everything in PX4 1.18.0 that sits between a receiver channel and a firmware action: how `rc_update` turns microseconds into −1…+1, at which boundaries the mode channel splits into the six `COM_FLTMODE1…6` slots, how the individual switches work (arm, kill, Return, VTOL transition, landing gear) and what the sign of the `RC_*_TH` thresholds means, how a channel goes straight to an output through `RC_MAP_AUXn`, and how a transmitter knob changes a parameter in flight through `RC_MAP_PARAM1…3`. After the module you can name the mode slot and the state of every switch from a table of pulses, compute the parameter value under a knob and the Acro rate with the formula from the source, and build a switch layout for your vehicle. The lab needs no hardware and no simulator: four calculations with a reference on the page.

## theory
### What the module covers and in what order to read it
The module describes one chain: channel → normalization → three consumers (sticks, switches, parameter tuning). Read it in this order: normalization and mode slots first, since every calculation rests on them; then the individual switches and the choice of control source; then AUX and knob tuning; at the end, the parameters the pilot feels in the sticks and a layout table for three vehicle types. Arming, kill and failsafe are covered in detail in `px4-safety-return`, outputs in `px4-outputs-servos`; here is only what the transmitter does. The transmitter side is in `link-edgetx` and `link-elrs`. The equivalents in other firmware: `ap-aux-tune` (ArduPilot) and `inav-adjustments` (INAV).

### The path of a channel: from receiver to command
The receiver driver publishes `input_rc`: up to 18 channels in microseconds. On every message the `rc_update` module does three things:

1. normalizes each channel by `RCn_MIN/TRIM/MAX/REV` into the −1…+1 range (`rc_channels`);
2. collects the sticks, flaps and six AUX into `manual_control_input`, and the switch positions into `manual_control_switches`;
3. no more than once a second, recomputes the parameters bound to the `RC_MAP_PARAMn` knobs.

Next, `manual_control` picks the source (the RC or a MAVLink joystick, `COM_RC_IN_MODE`), catches stick gestures and turns a switch position change into an `action_request`, which `commander` executes.

{{diagram:px4-rc-flow|Switches, mode slots and tuning knobs are handled only by rc_update; a MAVLink joystick reaches manual_control bypassing it, so the joystick has none of them.}}

Three properties of this chain explain the "strange" behavior:

- **Switches act on edges.** A command goes out only when the position changes. The first packet received is only remembered: an arm switch left on when power is applied does not arm. The mode from the slot is applied at once, though, but only while the vehicle is disarmed.
- **After a link loss and recovery** the positions are remembered again without any action: in the air the mode stays whatever the failsafe chose until you flick a switch.
- **Protection against garbage.** Positions are published when two packets in a row gave the same result; the first 100 ms after the signal returns are ignored; the signal counts as lost if there are fewer than four channels.

Switches are processed only when the active control source is the RC. When you fly with the QGC joystick, the slots, kill and the transmitter's arm switch stay silent.

### Calibration and channel normalization
Radio calibration in QGC (the "Radio" step in `px4-setup-scratch`) writes:

| Parameter | Default | Range | Meaning |
|---|---|---|---|
| `RC_CHAN_CNT` | 0 | 0…18 | how many channels the GCS saw during calibration; 0 means not calibrated |
| `RC_MAP_ROLL`, `RC_MAP_PITCH`, `RC_MAP_YAW`, `RC_MAP_THROTTLE` | 0 | 0…18 | stick channel number; 0 means not assigned |
| `RCn_MIN` | 1000 µs | 800…1500 | low end of channel n |
| `RCn_TRIM` | 1500 µs | 800…2200 | center |
| `RCn_MAX` | 2000 µs | 1500…2200 | high end |
| `RCn_REV` | 1 | −1 / 1 | −1 flips the sign |

The RC counts as calibrated when `RC_CHAN_CNT` > 0 and at least one of the four sticks is assigned. The `RCn_DZ` parameters (a per-channel deadzone, 10 µs on channels 1–8) were removed in 1.17: there is now a single deadzone, `MAN_DEADZONE`, and it is applied in the modes, not in the channel.

The formula from `rc_update.cpp` is piecewise linear through three points (min, −1), (trim, 0), (max, +1):

```
v ≤ MIN        → −1
MIN < v ≤ TRIM → (v − TRIM) / (TRIM − MIN)
TRIM < v ≤ MAX → (v − TRIM) / (MAX − TRIM)
v > MAX        → +1
RCn_REV < 0    → the result gets a minus sign
```

The code computes a segment as `a = (y₂ − y₁)/(x₂ − x₁)`, `b = y₁ − a·x₁`, `y = a·v + b`. Example: a channel with 1000/1500/2000, pulse 1620 µs. Upper segment: a = 1/500 = 0.002, b = 0 − 0.002·1500 = −3, y = 0.002·1620 − 3 = **0.24**. Channel 988/1500/2012, pulse 1100: a = 1/512, y = (1100 − 1500)/512 = **−0.781**.

Two caveats. The halves of the scale are scaled separately: if `TRIM` is not in the middle, the same shift in microseconds gives a different value up and down. And for the throttle channel the firmware itself replaces `TRIM` with (MIN + MAX)/2 if QGC wrote `TRIM` = `MIN`.

### Mode slots: `RC_MAP_FLTMODE` and `COM_FLTMODE1…6`
`RC_MAP_FLTMODE` (0 disabled, 1…18 a channel) splits one channel into six slots. For each slot the `COM_FLTMODEn` parameter assigns a mode; −1 (the default) means the slot is empty, and switching to it does nothing. The code computes the slot number like this (v is the normalized value; the result drops the fractional part):

```
slot = int( ((v + 1.05)·6 + 1/6) / 2.1 + 1/6 ) + 1,   at most 6
```

The boundaries do not fall at 1/6 of the range: the slot step is 0.35, and the first and last slots are narrower than the rest.

| Slot | Normalized v | Pulse at 1000/1500/2000, µs | EdgeTX channel weight for the middle of the slot |
|---|---|---|---|
| 1 | below −0.786 | up to 1106 | −100 % |
| 2 | −0.786 … −0.436 | 1107…1281 | −61 % |
| 3 | −0.436 … −0.086 | 1282…1456 | −26 % |
| 4 | −0.086 … +0.264 | 1457…1631 | +9 % |
| 5 | +0.264 … +0.614 | 1632…1806 | +44 % |
| 6 | +0.614 and above | from 1807 | +100 % |

{{diagram:chart-px4-rc-mode-slots|The channel center falls into slot 4: a three-position switch selects slots 1, 4 and 6, a two-position one 1 and 6; slots 2, 3 and 5 are reachable only with a mixed channel.}}

Selection rules:

- **A two-position switch**: fill in `COM_FLTMODE1` and `COM_FLTMODE6`.
- **A three-position switch**: slots 1, 4 and 6. You will never get the mode in slot 3: this is the most common mistake.
- **Six modes**: mix a two-position and a three-position switch into one channel on the transmitter with the weights from the last column (how to do that is in `link-edgetx`). The middle of slot 4 is not 0 % but +9 %.
- **Momentary buttons**: `RC_MAP_FLTM_BTN`, a bitmask of channels (bit 0 is channel 1); works only if `RC_MAP_FLTMODE` = 0. The lowest channel in the mask is slot 1, up to six in total. A button triggers at a value above 0.5 (75 % of travel), held for 50 ms.

The transmitter does not "hold" the mode: a failsafe, the GCS or a separate switch can change the mode, and the slot is applied again only on the next flick.

### Which modes you can put in a slot
The `COM_FLTMODEn` value list is the same for all vehicle types; the columns on the right follow the 1.17 documentation sections for each type.

| Value | Mode | Multirotor | Plane | Note |
|---|---|---|---|---|
| 0 | Manual | like Stabilized | direct control surface control | no stabilization on a plane |
| 8 | Stabilized | yes | yes | manual throttle |
| 6 | Acro | yes | yes | rates, manual throttle |
| 1 | Altitude | yes | yes | needs altitude |
| 16 | Altitude Cruise | yes | no | added in 1.17 |
| 2 | Position | yes | yes | needs position |
| 9 | Position Slow | yes | no | — |
| 3 | Mission | yes | yes | — |
| 4 | Hold | yes | yes | a loiter circle on a plane |
| 5 | Return | yes | yes | — |
| 10 / 11 | Takeoff / Land | yes | yes | — |
| 12 | Follow Me | yes | no | — |
| 13 | Precision Land | yes | no | — |
| 7 | Offboard | yes | yes | needs a setpoint stream |
| 100…107 | External Mode 1…8 | yes | yes | ROS 2 modes, see `px4-ros2` |

A VTOL uses the column of the phase it is flying in. The `navStateFromParam` function also accepts 14 (Orbit) and 15 (VTOL Takeoff), but they are not in the parameter's value list, so QGC will not offer them.

What changed: in 1.15 and 1.16 the list is the same (up to 13 and 100…107); 1.17 added 16, Altitude Cruise. The separate mode switches `RC_MAP_ACRO_SW`, `RC_MAP_MAN_SW`, `RC_MAP_POSCTL_SW`, `RC_MAP_RATT_SW`, `RC_MAP_STAB_SW` existed in 1.15 and were removed in 1.16; `RC_MAP_MODE_SW` remains only so that the firmware can reset it to 0 with the warning "RC_MAP_MODE_SW deprecated".

The rule for choosing a slot's mode: in the position your hand finds without looking (an end position), put a mode that works without GPS and compass, Altitude or Stabilized. When the vehicle goes astray in Position ("toilet bowling", a GPS glitch), that is the mode that saves it.

### Individual switches and the `RC_*_TH` thresholds
Each function is a "channel + threshold" pair. Channel 0 means not assigned. The normalized value is converted into a travel fraction `p = 0.5·v + 0.5` (0 bottom, 1 top) and compared with the threshold:

- a **positive** threshold: on when p > threshold;
- a **negative** threshold: on when p < |threshold|.

The default for all of them is 0.75, that is, on in the top quarter of travel (v > 0.5, above 1750 µs at 1000/1500/2000). The mirror threshold for a switch that turns "on" downward is **−0.25**, not −0.75: at −0.75 the function is on over the lower three quarters of travel, that is, in both the low and the middle position.

| Channel | Threshold | When on | When off |
|---|---|---|---|
| `RC_MAP_ARM_SW` | `RC_ARMSWITCH_TH` | arm | disarm |
| `RC_MAP_KILL_SW` | `RC_KILLSWITCH_TH` | kill: outputs to disarmed | kill released |
| `RC_MAP_TERM_SW` (1.17) | 0.75, not configurable | flight termination, irreversible | nothing |
| `RC_MAP_RETURN_SW` | `RC_RETURN_TH` | Return mode | the mode from the current slot |
| `RC_MAP_LOITER_SW` | `RC_LOITER_TH` | Hold mode | the mode from the current slot |
| `RC_MAP_OFFB_SW` | `RC_OFFB_TH` | Offboard mode | the mode from the current slot |
| `RC_MAP_TRANS_SW` | `RC_TRANS_TH` | VTOL transition to plane | transition to multirotor |
| `RC_MAP_GEAR_SW` | `RC_GEAR_TH` | landing gear up | landing gear down |
| `RC_MAP_ENG_MOT` | `RC_ENG_MOT_TH` | helicopter main rotor on | off |
| `RC_MAP_PAY_SW` | `RC_PAYLOAD_TH`, `RC_PAYLOAD_MIDTH` (1.17, 0.25) | payload power on | off (in the middle position too) |

`RC_MAP_PAY_SW` works only on boards that define `PAYLOAD_POWER_EN` (in the 1.17 tree, ark/fpv). Since 1.18, if the channel is assigned, payload power is off after boot until the switch explicitly turns it on (`ManualControl.cpp`, v1.18.0). `RC_MAP_FLAPS` is not a switch but a proportional channel: a plane takes `max(flaps, 0)`, so the lower half of travel means "flaps retracted".

Dangerous assignments, at the point of use:

- `RC_MAP_ARM_SW` starts the motors; `RC_MAP_KILL_SW` and `RC_MAP_TERM_SW` stop them in the air; `RC_MAP_TRANS_SW` puts a VTOL into plane mode (this request is not blocked in Land and RTL, see `px4-setup-vtol`); `RC_MAP_GEAR_SW` moves the landing gear; the Return switch makes the vehicle fly home.
- Functions that act "both ways" (arm, kill, transition, gear) must not go on a momentary button or on a channel shared with something else.

### Arm, kill and termination from the transmitter
The full arming sequence and the motor state table are in `px4-safety-return`. Here is only the transmitter behavior.

- **Arm switch.** `COM_ARM_SWISBTN` = 0: arm on the "on" edge, disarm on the "off" edge. `COM_ARM_SWISBTN` = 1: the channel is a button, and holding it for 1 s toggles arm ↔ disarm (hard-coded in `ManualControl.cpp` in 1.18; before 1.18 the `COM_RC_ARM_HYST` parameter, 1000 ms, 100…1500). Re-arming with the switch (not the button and not the gesture) within 5 s after a disarm skips the preflight checks: a safeguard against an accidental disarm in the air.
- **Stick gesture.** `MAN_ARM_GESTURE` = 1 (default). As soon as `RC_MAP_ARM_SW` is assigned, the firmware itself writes `MAN_ARM_GESTURE` = 0 with the message "Arm stick gesture disabled if arm switch in use". It will not turn it back on by itself.
- **Arming conditions from the transmitter.** In modes with manual throttle the throttle must be below −0.8, in altitude-holding modes no higher than +0.2; otherwise "Arming denied: throttle not in safe position". Before 1.18 the messages differed ("high throttle", "throttle above center"), and in automatic modes arming from the transmitter was rejected ("switch to manual mode first"); 1.18 has no such separate check (`Commander.cpp`, v1.18.0).
- **Disarm in the air.** Rejected ("Disarming denied: not landed"), except on a multirotor in a manual-throttle mode when the command came from the transmitter (switch, button, gesture). In 1.18 this cannot be turned off: the `COM_DISARM_MAN` parameter (before 1.18, default 1) was removed, and the condition is hard-coded in `Commander.cpp`. So in Stabilized and Acro a bumped arm switch stops the motors in flight.
- **Kill.** The outputs go to disarmed at once, and the vehicle stays armed. Flip the switch back within 5 s and the motors start again, including on the ground next to your hands. Later, it disarms. In 1.18 these 5 s are hard-coded (`Commander.cpp`); before 1.18 `COM_KILL_DISARM` set them.
- **Kill by gesture.** `MAN_KILL_GEST_T` (−1 disabled, up to 15 s): the left stick to the lower left and the right stick to the lower right, held for the set time. Since 1.18, while the gesture is held, all four sticks are zeroed (throttle to −1), and during the arm gesture throttle and yaw are: holding a gesture sends no false commands to the controller.
- **Termination.** `RC_MAP_TERM_SW` appeared in 1.17: the outputs go to their failsafe values, the parachute is commanded, and only a reboot cancels it.

The rule: arm and kill are two different two-position latching switches; kill sits under a guard or on a switch you do not touch when changing modes.

### Manual control source: `COM_RC_IN_MODE`
`manual_control` accepts several sources (the RC and up to six MAVLink channels with a joystick) and picks one.

| Value | Behavior | When to set it |
|---|---|---|
| 0 | RC only; requires calibration | the vehicle flies only with a transmitter |
| 1 | MAVLink only; RC checks disabled | SITL, flying from a GCS joystick |
| 2 | either; switches only when the current one is lost | RC and joystick as mutual backup |
| 3 (default) | the first valid one until reboot | factory setting |
| 4 | manual control disabled | a fully autonomous vehicle |
| 5 | priority: RC, then MAVLink 1, 2 | the RC is primary, the joystick a backup |
| 6 | priority: MAVLink 1, 2, then RC | the joystick is primary |
| 7 | RC, then MAVLink 2, 1 | like 5, different channel order |
| 8 | MAVLink 2, 1, then RC | like 6, different channel order |

Values 5…8 were added in 1.17; 1.15 and 1.16 have only 0…4, and the labels said "Joystick" instead of "MAVLink". The rule: if there is no joystick at all, set 0, so that a QGC virtual joystick switched on by accident does not become the "first valid" source before the RC. With value 3 that is exactly what happens, and then the transmitter switches stay silent until a reboot.

Related parameters:

- `COM_RC_LOSS_T` (0.5 s): after how long without packets the source counts as lost; what happens next (`NAV_RCL_ACT`, `COM_RCL_EXCEPT`) is in `px4-safety-return`.
- `MAN_OVERRIDE_SPD` (1 /s, −1…10; negative disables it): stick takeover on a multirotor and a VTOL in hover mode, in all automatic modes and in Offboard. What is compared is not the deflection but the smoothed speed of stick movement (a 0.05 s filter): the takeover triggers when it exceeds `MAN_OVERRIDE_SPD` units of the −1…+1 scale per second (with the default 1, half the full end-to-end travel per second) and the stick moves the same way for three frames in a row, on any of the four sticks, throttle included (`ManualControl.cpp`, `MovingDiff.hpp`, v1.18.0). A stick moved slowly will not take over, however far you deflect it. Before 1.18 there were two parameters: `COM_RC_OVERRIDE` (bit 0 auto modes, bit 1 Offboard; Offboard was not overridden by default) and `COM_RC_STICK_OV` (a threshold of 0.01·30 = 0.3 /s, a 0.1 s filter). On upgrade only `COM_RC_OVERRIDE` = 0 migrates, to `MAN_OVERRIDE_SPD` = −1.

### AUX channels: passthrough and function inputs
`RC_MAP_AUX1…6` (0…18) put the normalized channel into the `aux1…aux6` fields of the `manual_control_setpoint` topic. From there it has three consumers:

- **an output.** The RC AUX 1…6 functions (numbers 407…412) on the Actuators screen: the knob moves a servo or a relay directly. On RC loss such an output goes to its disarmed value. Details are in `px4-outputs-servos`;
- **a gimbal.** `MNT_MAN_PITCH`, `MNT_MAN_ROLL`, `MNT_MAN_YAW` select an AUX as the manual gimbal control input (`px4-hardware-peripherals`, `px4-camera-gimbal`);
- **plane autotune.** `FW_AT_MAN_AUX` = n takes the `RC_MAP_AUXn` channel: a value above 0.5 starts the identification, and flipping the switch back stops it.

An RC AUX output sits at its disarmed value when disarmed, and with `COM_PREARM_MODE` = 2 it starts following the knob 5 s after boot (`px4-outputs-servos`): when you put an AUX on a payload drop or a gripper, check the knob position before applying power.

Multirotor autotune is not started from a switch: `MC_AT_EN` = 1, reboot, and start from QGC (the `MAV_CMD_DO_AUTOTUNE_ENABLE` command); applying is `MC_AT_APPLY` (1 after disarm). The names `MC_AT_EN`, `MC_AT_APPLY`, `FW_AT_APPLY`, `FW_AT_MAN_AUX` are the same in 1.15–1.18; the "button" parameters `MC_AT_START` and `FW_AT_START` were removed in 1.18, so the start is by command only (`migrate_param_file.py`, the REMOVED list). The procedure is in `px4-control`.

### In-flight tuning: `RC_MAP_PARAM1…3`
With a knob or slider on the transmitter you can change a parameter without landing. The setup has two independent halves.

1. **The knob channel**: the `RC_MAP_PARAM1`, `RC_MAP_PARAM2` or `RC_MAP_PARAM3` parameter (0…18; QGC → Radio, the "Additional Radio setup:" list). Three knobs at most. The channel is normalized by its own `RCn_MIN/TRIM/MAX`, like any other.
2. **The binding to a parameter** is not a parameter but a MAVLink `PARAM_MAP_RC` message from the GCS: parameter name, knob number, `param_value0`, `scale`, `param_value_min`, `param_value_max`. In QGC: Parameters → pick the parameter → Advanced settings → **Set RC to Param**. To remove all bindings: Tools → Clear all RC to Param (a message with index −2).

PX4 keeps the binding in the `rc_parameter_map` topic, that is, in RAM. The formula from `set_params_from_rc()`:

```
param = clamp(value0 + scale · rc,  value_min,  value_max)
```

`rc` is the normalized knob value, −1…+1. The knob center (`RCn_TRIM`) gives `value0`, the ends `value0 ± scale`, clipped to min and max.

Example: `MC_ROLLRATE_K`, value0 = 1.0, scale = 0.3, min = 0.6, max = 1.3. Knob at center: 1.0; fully up: 1.0 + 0.3 = 1.3; fully down: 0.7 (it will not reach min 0.6: scale sets the span); at rc = 0.5: 1.15.

How it works over time:

- recalculation happens no more than **once a second**, and only if the knob moved; armed or not does not matter;
- at the moment of binding the knob value is compared with zero: if the knob is not centered, within a second the parameter **jumps** to `value0 + scale·rc`. Center the knob before pressing Set RC to Param;
- the source is only `input_rc` (the receiver or `RC_CHANNELS_OVERRIDE`). The QGC joystick (`MANUAL_CONTROL`) gives no tuning knobs;
- a noisy potentiometer causes a parameter write every second.

Which binding fields the QGC dialog offers and whether it resends the binding after a reconnect cannot be determined from the PX4 source; check it on your QGC version.

### What to turn with a knob and what survives a reboot
The value goes into the parameter with an ordinary `param_set()`, so it **is saved**: autosave writes it to storage within 0.3…2 s, and on boards that keep parameters in the microcontroller's internal flash the write is postponed until disarm. **The binding is not saved**: after a reboot `RC_MAP_PARAMn` is in place, but the knob changes nothing until the GCS sends `PARAM_MAP_RC` again. The parameter stays wherever the knob last left it. Betaflight is the other way round: the binding is stored, and the value has to be saved separately (`inav-adjustments` and `ap-aux-tune` show how INAV and ArduPilot do it).

Limitations that follow from the code:

- the code writes a floating-point number into the parameter without checking the type, so you can bind only FLOAT parameters. An integer one (`MC_AIRMODE`, `MC_AT_APPLY`, any INT32 `COM_*`) gets garbage;
- the firmware does not check the limits from the parameter's description: the only protection is `value_min` and `value_max` in the binding. Always set them;
- there is no OSD and no sound: the value shows up in QGC and in the log (`parameter_update`).

| What you tune | Parameter | Default and range | A sensible binding |
|---|---|---|---|
| Overall rate loop gain | `MC_ROLLRATE_K`, `MC_PITCHRATE_K` | 1.0 (0.01…5) | value0 = current, scale 0.3, min 0.6, max 1.4 |
| Rate loop P | `MC_ROLLRATE_P`, `MC_PITCHRATE_P` | 0.15 (0.01…0.5 / 0.6) | scale 0.05, min 0.08, max 0.25 |
| Rate loop D | `MC_ROLLRATE_D`, `MC_PITCHRATE_D` | 0.003 (0…0.01) | scale 0.002, min 0.001, max 0.006 |
| Yaw rate loop P | `MC_YAWRATE_P` | 0.2 (0…0.6) | scale 0.1, min 0.1, max 0.35 |

The selection rule: with a knob, only a coefficient whose smooth change gives a smooth change in behavior, and one axis at a time; start with `K`, which scales P, I and D together. Never `CA_*`, the `PWM_*` output parameters, `SYS_*`, `EKF2_*`, `IMU_*CUTOFF`: some need a reboot, and others drop the vehicle instantly with a wrong value. After the session write down the value you found, remove the binding and set `RC_MAP_PARAMn` back to 0.

### What the pilot feels in the sticks
These parameters do not change stability, but they change the response to the stick.

| Parameter | Default | Range | What it sets |
|---|---|---|---|
| `MPC_MAN_TILT_MAX` | 35° | 1…70 | tilt at full stick: Stabilized, Altitude, Altitude Cruise |
| `MPC_MAN_Y_MAX` | 150 °/s | 0…400 | yaw rate at full stick: Stabilized, Altitude, Position |
| `MPC_VEL_MANUAL` | 10 m/s | 3…20 | speed at full stick in Position |
| `MPC_VEL_MAN_SIDE`, `MPC_VEL_MAN_BACK` | −1 | −1…20 | the same sideways and backward; −1 means as `MPC_VEL_MANUAL` |
| `MPC_XY_VEL_MAX` | 12 m/s | 0…20 | ceiling for all velocity modes |
| `MPC_Z_VEL_MAX_UP` / `MPC_Z_VEL_MAX_DN` | 3 / 1.5 m/s | 0.5…8 / 0.5…4 | vertical speed at full stick |
| `MAN_DEADZONE` (before 1.17, `MPC_HOLD_DZ`) | 0.1 | 0…1 | deadzone around center |
| `MPC_THR_CURVE` | 0 | 0 / 1 / 2 | throttle in Stabilized: 0 stick center = hover thrust estimate, 1 linear, 2 center = `MPC_THR_HOVER` |
| `MPC_THR_HOVER` | 0.5 | 0.1…0.9 (before 1.18, 0.1…0.8) | hover thrust: initial value of the estimate and the stick center with `MPC_THR_CURVE` = 2 |
| `MPC_MANTHR_MIN` | 0.08 | 0…0.5 (before 1.18, 0…1) | thrust with the throttle stick at the bottom in Stabilized |
| `MC_AIRMODE` | 0 | 0 / 1 / 2 | 1 roll and pitch, 2 plus yaw |
| `MC_ACRO_R_MAX`, `MC_ACRO_P_MAX`, `MC_ACRO_Y_MAX` | 100 °/s | 0…1800 | Acro rate at full stick |
| `MC_ACRO_EXPO`, `MC_ACRO_EXPO_Y` | 0 | 0…1 | Acro expo |
| `MC_ACRO_SUPEXPO`, `MC_ACRO_SUPEXPOY` | 0 | 0…0.95 | Acro superexpo |

The Acro rate from `Functions.hpp` (x is the stick −1…+1, e expo, g superexpo):

```
expo(x)  = (1 − e)·x + e·x³
rate     = expo(x) · (1 − g) / (1 − |x|·g) · MC_ACRO_x_MAX
```

At full stick the multiplier is 1 for any e and g: only `MC_ACRO_x_MAX` sets the maximum. Expo and superexpo soften the center. There is no deadzone in Acro. The 100 °/s default suits a calm vehicle; for FPV flying it is raised several times over, so check the rates with the calculation from step 3 of the practice.

What changed in 1.17: `MPC_XY_MAN_EXPO`, `MPC_Z_MAN_EXPO`, `MPC_YAW_EXPO` were removed, and in the holding modes the expo is fixed at 0.6; `MPC_HOLD_DZ` was renamed `MAN_DEADZONE`.

Selection rules. Always leave `MPC_THR_CURVE` = 0, except on vehicles with very low hover thrust: there the upper half of the stick gets abrupt, so set 1 (that is what the parameter description says). `MC_AIRMODE` = 1 is for FPV and acro (control authority at zero throttle); 2 requires an arm switch: with `MAN_ARM_GESTURE` = 1 the firmware itself lowers it to 1 ("Yaw Airmode requires disabling the stick arm gesture"). Turn airmode off while tuning the PID.

### Switch layout: three cases
| Function | FPV quadcopter, ELRS 16 channels | Camera multirotor with a GCS | Plane / VTOL |
|---|---|---|---|
| Arm | `RC_MAP_ARM_SW` = 5, two-position | stick gesture, `RC_MAP_ARM_SW` = 0 | gesture or switch |
| Modes (`RC_MAP_FLTMODE`), slots 1 / 4 / 6 | Altitude / Stabilized / Acro | Altitude / Position / Mission | Stabilized / Position / Mission |
| Kill | `RC_MAP_KILL_SW`, latching | `RC_MAP_KILL_SW`, under a guard | `RC_MAP_KILL_SW` |
| Return | `RC_MAP_RETURN_SW`, if there is GPS | `RC_MAP_RETURN_SW` | `RC_MAP_RETURN_SW` |
| Special | knob → `RC_MAP_PARAM1` while tuning | knob → `RC_MAP_AUX1` (gimbal) | `RC_MAP_TRANS_SW`, `RC_MAP_FLAPS`, `FW_AT_MAN_AUX` while tuning |
| `COM_RC_IN_MODE` | 0 | 0 or 5 | 0 or 5 |
| `MC_AIRMODE` | 1 (or 2) | 0 | — |

Why:

- **FPV, ELRS.** In the Hybrid and Wide switch modes channel 5 is sent as a single bit, and ELRS itself treats it as the arm flag (`link-elrs`), so in PX4 arming goes on the same channel 5. You need an arm switch: FPV pilots fly manual-throttle modes, where an instant disarm after a crash matters, and only a switch allows `MC_AIRMODE` = 2.
- **Camera work.** Arm by gesture: in Position you cannot disarm in the air with a switch anyway, and a bumped switch in Stabilized is a crashed vehicle. Mission in one end slot, Altitude in the other end slot as the rescue mode without GPS. Return on a separate switch: it overrides the slot, and after you turn it off the mode goes back to the slot.
- **Plane / VTOL.** Manual (0) on a plane is direct control surface control; put it in a slot only deliberately and never in the middle one. Before arming the transition switch is in the "multirotor" position. Kill on a plane sends every output to its disarmed value, both the motor and the servos: that is gliding without control, not a landing.

What to check afterwards, without propellers:

1. QGC → Flight Modes: on a flick the expected slot lights up, not the neighboring one.
2. Console (`px4-console-params`): `listener manual_control_switches`: `mode_slot` takes exactly the values you filled in; assigned switches show 3 (off) and 1 (on), unassigned ones 0.
3. `listener rc_channels` for the normalized values; `rc_update status` for the MIN/MAX/TRIM/REV table the module sees.
4. Kill: the message "Kill engaged", and on release "Kill disengaged".
5. Reboot with the arm switch in the "on" position: no arming.

### Place in the system
- **Takes in:** receiver channels in microseconds from the RC driver (`px4-setup-scratch`, `link-elrs`, `link-edgetx`), the knob-to-parameter binding as a `PARAM_MAP_RC` message from the GCS, the parameter set through the console and QGC (`px4-console-params`).
- **Gives out:** sticks and AUX to the control loops and the RC AUX outputs (`px4-control`, `px4-outputs-servos`), arm, kill and mode change requests to `commander` (`px4-safety-return`), manual gimbal control to `px4-hardware-peripherals`.
- **If you get it wrong here:** a mode in slot 3 with a three-position switch means "the transmitter does not switch modes"; a wrong threshold sign means kill or Return is permanently on, which looks like an arming failure or a spontaneous return in `px4-safety-return`; a forgotten knob binding means "drifting" gains in `px4-control`.

## practice
An exercise without hardware or a simulator: paper or an editor and a calculator. All answers follow from the theory formulas, and you check them against the reference at the end.

### Step 1. Normalization, slot and switches
A parameter fragment (a teaching example, put together by hand):

```
RC_CHAN_CNT       16
RC_MAP_ROLL       1
RC_MAP_PITCH      2
RC_MAP_THROTTLE   3
RC_MAP_YAW        4
RC_MAP_ARM_SW     5
RC_ARMSWITCH_TH   0.75
RC_MAP_FLTMODE    6
COM_FLTMODE1      8
COM_FLTMODE4      1
COM_FLTMODE6      2
RC_MAP_KILL_SW    7
RC_KILLSWITCH_TH  0.75
RC7_REV           -1
RC_MAP_RETURN_SW  8
RC_RETURN_TH      -0.25
RC_MAP_PARAM1     9
RC1…RC4           MIN 1000  TRIM 1500  MAX 2000
RC5…RC8           MIN 988   TRIM 1500  MAX 2012
RC9               MIN 1000  TRIM 1480  MAX 1990
```

Channel pulses at three moments in time, µs:

| Channel | A | B | C |
|---|---|---|---|
| 1 roll | 1500 | 1620 | 1500 |
| 2 pitch | 1500 | 1400 | 1850 |
| 3 throttle | 1000 | 1560 | 1300 |
| 4 yaw | 1500 | 1500 | 1450 |
| 5 | 988 | 2012 | 2012 |
| 6 | 988 | 1500 | 1840 |
| 7 | 2012 | 2012 | 988 |
| 8 | 2012 | 2012 | 1100 |
| 9 | 1480 | 1735 | 1200 |

A worked example, moment B, channel 1: 1620 > TRIM, so (1620 − 1500)/(2000 − 1500) = **0.24**. Channel 6: 1500 = TRIM → 0; slot = int(((0 + 1.05)·6 + 0.1667)/2.1 + 0.1667) + 1 = int(3.246) + 1 = **4** → `COM_FLTMODE4` = 1, Altitude.

Compute for each moment yourself: the normalized values of channels 1–4 and 9; the slot and the mode; the state of arm, kill and Return (for each write down p = 0.5·v + 0.5 and the comparison with the threshold). Separately answer: what are the motors doing at moment C?

### Step 2. The parameter under the knob
The GCS sent a binding: knob 1 → `MC_ROLLRATE_K`, value0 = 1.0, scale = 0.5, min = 0.7, max = 1.3. The knob channel is the ninth one from step 1.

A worked example: pulse 1735 → rc = (1735 − 1480)/(1990 − 1480) = 0.5 → 1.0 + 0.5·0.5 = **1.25**, within 0.7…1.3.

Compute the parameter value for pulses 1000, 1200, 1480 and 1990 µs. Then answer: the pilot landed with the pulse at 1735, disarmed and rebooted the flight controller. What is `MC_ROLLRATE_K` after boot, what happens if you turn the knob, and what happens in the first second after the GCS sends the same binding while the knob is at 1990?

### Step 3. Acro rate
`MC_ACRO_R_MAX` = 720, `MC_ACRO_EXPO` = 0.6, `MC_ACRO_SUPEXPO` = 0.7.

A worked example, x = 0.5: expo = 0.4·0.5 + 0.6·0.125 = 0.275; multiplier = (1 − 0.7)/(1 − 0.5·0.7) = 0.3/0.65 = 0.4615; rate = 0.275·0.4615·720 = **91.4 °/s**.

Compute the rate at x = 0.25, 0.75 and 1.0. Then the same x = 0.5 with the factory settings (all three parameters at their defaults) and with `MC_ACRO_EXPO` = 0.6 and no superexpo.

### Step 4. Layout and three errors
Task A. Pick one of the three cases from the last theory table and write down the full parameter set: channels, `COM_FLTMODE1/4/6`, thresholds, `COM_RC_IN_MODE`, `COM_ARM_SWISBTN`. Check it against the rules: arm and kill on different latching channels; an end slot holds a mode without GPS; exactly the slots the switch can reach are filled.

Task B. Find three dangerous assignments (a teaching example, put together by hand). The channel 6 switch is three-position; channel 7 is a momentary button; channel 8 is two-position, 988 µs in the low position.

```
RC_MAP_FLTMODE    6
COM_FLTMODE1      8
COM_FLTMODE4      1
COM_FLTMODE6      2
RC_MAP_ARM_SW     6
RC_ARMSWITCH_TH   0.75
COM_ARM_SWISBTN   0
RC_MAP_KILL_SW    7
RC_KILLSWITCH_TH  0.75
RC_MAP_RETURN_SW  8
RC_RETURN_TH      -0.75
```

For each error write down what will happen in flight or on the ground and how to fix it.

### Moving to real hardware
The propellers stay off until the last item.

1. Calibrate the radio in QGC, and write down the `RCn_MIN/TRIM/MAX` of the switch and knob channels.
2. Fill in the layout from task A. Go through the five checks from the end of the "Switch layout" section.
3. Capture the mode switch pulses with `listener input_rc` and compute the slots with the formula: they must match `mode_slot`.
4. Knob: assign `RC_MAP_PARAM1`, center the knob, bind `MC_ROLLRATE_K` with min and max, turn it and check `param show MC_ROLLRATE_K` once a second. Reboot: the value stayed, the knob does nothing.
5. With propellers only after kill has been checked twice. The first arming in an open area, the vehicle 5 m from people. In-flight tuning: hover in Altitude at 3–5 m, move the knob slowly, and at any oscillation, knob to center and land.

Hardware criteria: `mode_slot` matched the calculation in every position; after a reboot with the arm switch on there is no arming; the value under the knob changes no more than once a second and does not go beyond min and max.

Self-check: the lab is done when (the calculation part without hardware, the "Moving to real hardware" items only on the vehicle):

- the step 1 normalized values match the reference within ±0.005, the slots and modes exactly, the state of all three switches at three moments exactly;
- the four step 2 parameter values match within ±0.005, and the three reboot questions got the same answer as in the reference;
- the step 3 rates match within ±0.5 °/s;
- task B names the same three assignments, each with its consequence and fix; the task A layout passes the three checking rules.

**Reference for the self-check.**

Step 1:

| Quantity | A | B | C |
|---|---|---|---|
| Roll / pitch / throttle / yaw | 0 / 0 / −1 / 0 | 0.24 / −0.2 / 0.12 / 0 | 0 / 0.7 / −0.4 / −0.1 |
| Channel 9 (knob) | 0 | 0.5 | −0.583 |
| Channel 6 → slot → mode | −1 → 1 → Stabilized | 0 → 4 → Altitude | 0.664 → 6 → Position |
| Arm (channel 5) | p = 0, off | p = 1 > 0.75, on | on |
| Kill (channel 7, reversed) | v = −1, p = 0, off | off | v = +1, p = 1 > 0.75, on |
| Return (channel 8, threshold −0.25) | p = 1, not below 0.25, off | off | v = −0.781, p = 0.109 < 0.25, on |

At moment C the motors are stopped: kill sent the outputs to their disarmed values, even though the vehicle is armed and Return is selected. If the switch is not flipped back within 5 s, it disarms.

Step 2: 1000 → rc = −1 → 0.5 → clipped to **0.7**; 1200 → rc = −0.583 → **0.708**; 1480 → **1.0**; 1990 → 1.5 → clipped to **1.3**. After a reboot `MC_ROLLRATE_K` = 1.25 (the value was saved by autosave); turning the knob changes nothing, because the binding in RAM is gone; after a new binding with the knob at 1990 the parameter jumps from 1.25 to 1.3 within a second.

Step 3: x = 0.25 → **28.6**; 0.75 → **251.5**; 1.0 → **720**; factory settings, x = 0.5 → 0.5·100 = **50**; expo 0.6 without superexpo → 0.275·720 = **198**.

Step 4, task B: (1) `RC_MAP_ARM_SW` = `RC_MAP_FLTMODE` = 6: the top position (p = 1 > 0.75) is both slot 6 and arm; leaving Position downward is a disarm request, and in slot 1 (Stabilized) disarming in the air is allowed. The fix: arm on a separate channel. (2) Kill on a momentary button: release it and kill is cleared, so the motors start again as long as 5 s have not passed. The fix: a latching switch. (3) `RC_RETURN_TH` = −0.75: on when p < 0.75, and in the low position p = 0, so Return is permanently on. The fix: +0.75 (on when up) or −0.25 (on when down).

Typical wrong results and their cause:

- slot 3 at moment B: the range divided into six equal parts instead of the formula; the channel center always gives slot 4;
- Return "off" at moment C or kill "on" at moment A: the threshold sign or the channel reversal lost; first `RCn_REV`, then p, then the comparison;
- 0.5 and 1.5 in step 2: the min and max clipping forgotten; 0.71 instead of 0.708 at 1200: the knob computed from 1500 instead of its own `TRIM` = 1480;
- 360 °/s at x = 0.5 in step 3: the linear formula without expo and superexpo.

## diagnostics
- **Symptom:** a three-position switch selects only two modes, the middle position "does nothing"
  - Possible cause: the mode is written in `COM_FLTMODE2` or `COM_FLTMODE3`, while the channel center falls into slot 4.
  - What to do: `listener manual_control_switches`, look at `mode_slot` in each position, and fill in exactly those slots.
- **Symptom:** the transmitter switches do nothing, the sticks work
  - Possible cause: the active source is a MAVLink joystick (`COM_RC_IN_MODE` = 3 picked it first), and switches are processed only with the RC as the source.
  - What to do: `COM_RC_IN_MODE` = 0 or 5, turn off the virtual joystick in QGC, reboot.
- **Symptom:** arming is rejected, QGC shows "Kill engaged", or the vehicle goes into Return by itself
  - Possible cause: a wrong sign or value of the `RC_*_TH` threshold, or a reversed channel (`RCn_REV`).
  - What to do: compute p = 0.5·v + 0.5 for both positions and compare with the threshold; the mirror of 0.75 is −0.25.
- **Symptom:** the motors cut out in flight in Stabilized or Acro
  - Possible cause: the arm switch was bumped: in manual-throttle modes a disarm from the transmitter in the air is allowed (in 1.18 always; before 1.18 with `COM_DISARM_MAN` = 1); or kill.
  - What you see in the log: "Disarmed by RC switch" or "Kill engaged".
  - What to do: flip the switch back at once, since a re-arm within 5 s skips the checks; move arming to a switch you do not bump; for a camera vehicle, arm by gesture.
- **Symptom:** after assigning an arm switch, arming with the sticks stopped working
  - Possible cause: the firmware itself wrote `MAN_ARM_GESTURE` = 0.
  - What to do: this is normal; if the switch is removed (`RC_MAP_ARM_SW` = 0), set `MAN_ARM_GESTURE` = 1 back by hand.
- **Symptom:** the tuning knob does not change the parameter
  - Possible cause: the binding was lost after a reboot; the parameter is an integer; `RC_MAP_PARAMn` = 0; control comes from the joystick.
  - What to do: Set RC to Param again, check the parameter type and the knob channel in `listener rc_channels`.
- **Symptom:** the parameter jumped right after binding, and the vehicle started oscillating
  - Possible cause: the knob was not centered, and the parameter went to `value0 + scale·rc`.
  - Consequences: with a large scale, loss of stability.
  - What to do: center the knob before binding, keep scale no more than a third of value0, always set min and max.
- **Symptom:** the sticks do not take the vehicle over from Mission
  - Possible cause: the stick is moved slowly, since `MAN_OVERRIDE_SPD` is compared with the speed of movement (the default of 1 /s is stricter than the old 0.3 /s threshold); or `MAN_OVERRIDE_SPD` < 0 (that is also where an old `COM_RC_OVERRIDE` = 0 migrates); a plane has no takeover.
  - What to do: a sharp stick movement, or a mode change with a switch.

## checklist
- The propellers are off for the whole switch check
- Every filled `COM_FLTMODEn` matches a slot the switch actually reaches (`mode_slot`)
- An end slot holds a mode that works without GPS
- Arm and kill are different channels, both latching; kill restarts the motors when released within 5 s, so keep your hands away
- The sign and value of every `RC_*_TH` are checked by computing p for both positions
- `RC_MAP_TERM_SW` is not assigned without need: termination is irreversible
- Before arming, the VTOL transition switch is in the "multirotor" position; the Return switch is off
- RC AUX outputs with a payload drop or gripper: the knob position is checked before applying power
- `COM_RC_IN_MODE` = 0 if there is no joystick
- Knob binding: the parameter is FLOAT, min and max are set, the knob is centered; after the session the binding is removed, `RC_MAP_PARAMn` = 0, the value is written down

## references
- PX4 Guide v1.17: Radio Control Setup (Param Tuning Channels) | https://docs.px4.io/v1.17/en/config/radio | primary | A
- PX4 Guide v1.17: Flight Mode Configuration | https://docs.px4.io/v1.17/en/config/flight_mode | primary | A
- PX4 Guide v1.17: Finding/Updating Parameters | https://docs.px4.io/v1.17/en/advanced_config/parameters | primary | A
- PX4-Autopilot v1.18.0: src/modules/rc_update/rc_update.cpp | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/modules/rc_update/rc_update.cpp | primary | A
- PX4-Autopilot v1.18.0: src/modules/rc_update/params.yaml | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/modules/rc_update/params.yaml | primary | A
- PX4-Autopilot v1.18.0: src/modules/manual_control/ManualControl.cpp | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/modules/manual_control/ManualControl.cpp | primary | A
- PX4-Autopilot v1.18.0: src/modules/manual_control/ManualControlSelector.cpp | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/modules/manual_control/ManualControlSelector.cpp | primary | A
- PX4-Autopilot v1.18.0: src/modules/commander/module.yaml (COM_FLTMODEn) | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/modules/commander/module.yaml | primary | A
- PX4-Autopilot v1.18.0: src/modules/mavlink/mavlink_parameters.cpp (PARAM_MAP_RC) | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/modules/mavlink/mavlink_parameters.cpp | primary | A
- PX4-Autopilot v1.18.0: src/lib/mathlib/math/Functions.hpp (expo, superexpo, interpolate) | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/lib/mathlib/math/Functions.hpp | primary | A
- PX4-Autopilot v1.18.0: msg/RcParameterMap.msg | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/msg/RcParameterMap.msg | primary | A

## notes
- The firmware was not built or run in this pass: all behavior is derived from reading the v1.17.0 source and comparing with the v1.16.2 and v1.15.4 trees. The move to 1.18.0 comes from comparing `rc_update.cpp`, `ManualControl.cpp`, `ManualControlSelector.cpp`, `commander/module.yaml` of the v1.17.0 and v1.18.0 tags: the channel arithmetic, slots and thresholds did not change (`RCn_REV` became an integer type); stick takeover, arm button hold, disarm in the air, kill and autotune changed, as described above. The practice numbers were computed with a script that repeats the arithmetic of `rc_update.cpp` and `Functions.hpp`.
- Not verified: which binding fields the Set RC to Param dialog in QGC fills in and whether QGC resends the binding after a reconnect; how the vehicle behaves when a slot holds a mode its type does not have; how values 14 and 15 work in `COM_FLTMODEn`.
- The "Multirotor / Plane" columns in the mode table follow the `flight_modes_mc` and `flight_modes_fw` documentation sections of the v1.17.0 tree, not the code: the parameter does not distinguish vehicle types.
- The EdgeTX weights in the slot table are the middle of the slot on the normalized scale times 100; they hold when `RCn_MIN` and `RCn_MAX` are calibrated to the transmitter's −100 % and +100 %.
