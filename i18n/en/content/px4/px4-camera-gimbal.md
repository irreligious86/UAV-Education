---
id: px4-camera-gimbal
source: content/px4/px4-camera-gimbal.md
source_hash: ef0eb7764fe5
title: "PX4: gimbal, camera trigger and geotags"
level: L2
readingTime: 55 min
firmware: PX4 1.18 (checked against v1.18.0; the step 1 calculation tested in SITL v1.18.0, SIH)
status: published
added: 2026-11-22
tags:
  - PX4
  - gimbal
  - camera trigger
  - geotags
  - mapping
related:
  - payload-gimbal
  - per-mapping
  - per-camera
  - px4-outputs-servos
  - px4-hardware-peripherals
  - px4-safety-return
  - mav-services
next:
  - per-mapping
---

## summary
PX4 1.18.0 parameters and wiring for a gimbal and a survey camera: what `MNT_MODE_IN` and `MNT_MODE_OUT` select, how an angle becomes microseconds through `MNT_MIN_PITCH` / `MNT_MAX_PITCH`, `MNT_RANGE_ROLL` / `MNT_RANGE_YAW` and the output's `MIN`/`CENT`/`MAX`, which MAVLink Gimbal v2 messages the firmware accepts and sends, how `TRIG_MODE`, `TRIG_INTERFACE`, `TRIG_DISTANCE`, `TRIG_MIN_INTERVA` work, what the `CAM_CAP_FBACK` shutter feedback gives you, and which ULog topics carry the time and position of a frame. General gimbal theory is in `payload-gimbal`, GSD and overlap calculations are in `per-mapping`; here is only the PX4 side. After the module you can pick the wiring by gimbal and camera type and compute the gimbal servo pulse, the trigger distance and interval, and the geotag error from shutter delay. The lab needs no hardware and no simulator: four calculations and a parameter fragment with three errors; you check the answers against the reference on the page.

## theory
### What the module covers and how to read it
The module covers three PX4 subsystems: the `gimbal` module, the `camera_trigger` driver (shutter release) and the `camera_capture` driver (hot shoe feedback), plus what they put in the log for georeferencing. The gimbal comes first: where the command comes from, where it goes, how the pulse is computed and how the firmware acts as the gimbal manager. Then the camera: trigger modes and interfaces, distance-based capture, feedback and geotags. At the end, two selection tables and the differences across 1.15–1.18. In 1.18 the `gimbal` module changed the most: pitch limits became asymmetric, the `MNT_OFF_*` offsets were removed, and a setpoint filter `MNT_TAU` appeared, which changes both the pulse arithmetic and how the stick behaves. The manager / device roles and the protocol messages themselves are covered in `payload-gimbal` and `mav-services`, GSD and overlap in `per-mapping`: here they are only referenced.

### Three modules and when they start
All three modules are in the `px4_fmu-v6x_default` and `px4_fmu-v6c_default` builds (`CONFIG_MODULES_GIMBAL`, `CONFIG_DRIVERS_CAMERA_TRIGGER`, `CONFIG_DRIVERS_CAMERA_CAPTURE`, `CONFIG_MODULES_CAMERA_FEEDBACK` in `default.px4board`), but the `rcS` startup script starts them based on parameters:

| Module | Condition in `rcS` | What it does |
|---|---|---|
| `gimbal` | `MNT_MODE_IN` > −1 | accepts commands, computes angles, sends them to the output |
| `camera_trigger` and `camera_feedback` | `TRIG_MODE` > 0 | releases the shutter; publishes `camera_trigger` and `camera_capture` |
| `camera_capture` | `CAM_CAP_FBACK` > 0 | catches the edge from the hot shoe, publishes `camera_trigger` with `feedback = true` |

By default `MNT_MODE_IN` = −1 and `TRIG_MODE` = 0: neither the gimbal nor the trigger runs, and `gimbal status` in the console (`px4-console-params`) answers "not running". `MNT_MODE_IN`, `MNT_MODE_OUT` and all `TRIG_*` and `CAM_CAP_*` are read at startup: change them and reboot the board. The module rereads the other `MNT_*` on the fly. `camera_feedback` starts only together with the trigger: feedback without `TRIG_MODE` > 0 will not fill the `camera_capture` topic.

### Command source: `MNT_MODE_IN`
| Value | Source | When to choose it |
|---|---|---|
| −1 | disabled (default) | no gimbal |
| 0 | Auto: RC and MAVLink Gimbal v2 together | the pilot has the RC plus a ground station or a mission |
| 1 | RC only (AUX channels) | a simple servo gimbal, no ground station or missions |
| 2 | ROI only (protocol v1, to be deprecated) | do not choose for new projects |
| 3 | `DO_MOUNT_CONTROL` only (v1, to be deprecated) | do not choose for new projects |
| 4 | MAVLink Gimbal v2 only | control from a ground station, a mission or a companion; the RC does not steer the gimbal |
| 5 (since 1.18) | fixed world-frame attitude, no commands accepted | the gimbal holds pitch `MNT_FIXED_PITCH` (−90…90°, default 0), for example a camera that always looks at nadir |

The rule: you need the RC and something else, 0; the RC only, 1; software control only, 4. In mode 1 mission commands and ROI do not move the gimbal. In mode 0 whoever updated last is in control; to keep the RC from grabbing the gimbal by accident it needs a "large move": the channel must change by more than 0.25 on the −1…+1 scale (one eighth of full travel, 12.5 %) from the last accepted value, on any of the three axes. After such a move primary control goes to the autopilot, and the `GIMBAL_MANAGER_SET_ATTITUDE` stream from the ground station is ignored until the station takes control back with `DO_GIMBAL_MANAGER_CONFIGURE`.

A detail from the code: the `MAV_PROTOCOL_CAPABILITY_COMPONENT_IMPLEMENTS_GIMBAL_MANAGER` flag in `AUTOPILOT_VERSION` is set only with `MNT_MODE_IN` = 4; with 0 it is absent. How a particular ground station reacts to that cannot be seen in the PX4 tree (not verified).

### Where the command goes: `MNT_MODE_OUT`
| Value | Output | What PX4 computes |
|---|---|---|
| 0 | AUX: up to three PWM outputs with the Gimbal Roll / Pitch / Yaw functions | angles, stabilization (`MNT_DO_STAB`), limits, mapping to −1…+1 |
| 1 | MAVLink v1: `COMMAND_LONG` `DO_MOUNT_CONTROL` to `MNT_MAV_SYSID` / `MNT_MAV_COMPID` | angles in degrees after the limits (before 1.18 `MNT_OFF_*` were added to them) |
| 2 | MAVLink Gimbal v2: `GIMBAL_DEVICE_SET_ATTITUDE` | nothing: the quaternion, rates and lock flags go to the device as they are |

The output functions are in `output_functions.yaml`: Gimbal Roll 420, Gimbal Pitch 421, Gimbal Yaw 422. You assign them on the Actuators screen like any servo; timer groups, 50 Hz and servo power are in `px4-outputs-servos`.

Consequences that are easy to miss:

- `MNT_MIN_PITCH` / `MNT_MAX_PITCH`, `MNT_RANGE_ROLL` / `MNT_RANGE_YAW`, `MNT_TAU`, `MNT_DO_STAB`, `MNT_LND_P_MIN/MAX` **do not apply** to the v2 output: the angle calculation function is not called for it. Limits and stabilization are up to the gimbal itself.
- Only the v1 output reads `MNT_MAV_SYSID` and `MNT_MAV_COMPID`. In v2 the device address comes from the received `GIMBAL_DEVICE_INFORMATION`: the sender's compid and its own system id (`MAV_SYS_ID`). The `MNT_MAV_COMPID` description in the parameter reference mentions v2, but the code does not use it there.
- Until `GIMBAL_DEVICE_INFORMATION` arrives, the v2 output requests it once a second with `MAV_CMD_REQUEST_MESSAGE`, and in the other cycles keeps sending `GIMBAL_DEVICE_SET_ATTITUDE` with device id 0 (no component address; `gimbal/output_mavlink.cpp`, v1.17.0 and v1.18.0); a gimbal that expects messages addressed to its own component will not act on them. In `gimbal status` this is the "gimbal device compid not found" line.
- The MAVLink gimbal port: `MAV_n_CONFIG` = the port number, `MAV_n_MODE` = 10 (Gimbal). In this set PX4 sends `GIMBAL_DEVICE_SET_ATTITUDE` and `AUTOPILOT_STATE_FOR_GIMBAL_DEVICE` at 20 Hz and accepts only `HEARTBEAT`, `GIMBAL_MANAGER_SET_ATTITUDE`, `GIMBAL_MANAGER_SET_MANUAL_CONTROL`, `GIMBAL_DEVICE_INFORMATION` and `GIMBAL_DEVICE_ATTITUDE_STATUS`. Port numbers are in `px4-hardware-peripherals`.

### RC control
`MNT_MAN_ROLL`, `MNT_MAN_PITCH`, `MNT_MAN_YAW` (0 disabled, 1…6 AUX1…AUX6) select the `aux1…aux6` field of the `manual_control_setpoint` topic. The field itself is filled by `RC_MAP_AUXn`, the receiver channel number (module `px4-rc-tuning`). You need both: `MNT_MAN_PITCH` = 2 with `RC_MAP_AUX2` = 0 gives a constant zero.

`MNT_RC_IN_MODE` selects what the stick position means:

| Value | Meaning | Arithmetic from `input_rc.cpp` |
|---|---|---|
| 0 | angle | pitch = aux · 90°, roll and yaw = aux · 179.99° |
| 1 (default) | angular rate | pitch: `MNT_RATE_PITCH` · aux, yaw: `MNT_RATE_YAW` · aux; roll rate is always 0 |

In rate mode the angle accumulates: θ(t) = θ₀ + `MNT_RATE_PITCH` · aux · t, until it hits `MNT_MIN_PITCH` or `MNT_MAX_PITCH`. At 30 °/s with the stick at half travel, 3 s adds up to 45°. Let the stick return to center and the gimbal stays where it stopped.

**The 1.18 trap: `MNT_TAU`.** The new setpoint filter (0.3 s by default) sits inside the same loop where the angle accumulates: on each step the filter passes not the whole increment `MNT_RATE_PITCH` · aux · dt but a fraction dt / (`MNT_TAU` + dt) of it (`output.cpp`, `_angle_outputs_filtered`). With the gimbal loop at 10 ms (the AUX poll timeout; a faster RC link wakes it more often and the fraction shrinks further) that is about 1/30: in SITL v1.18.0 (SIH) the stick at −1.0 with 30 °/s turned the gimbal at about 1 °/s, at −0.5 at 0.5 °/s; with `MNT_TAU` = 0, exactly 30 and 15 °/s. On hardware the fraction depends on the loop period; this was not tested on a flight controller. If you need the stick in rate mode, set `MNT_TAU` = 0 and let the servo smooth things out; in angle mode the filter only eases the gimbal to the setpoint (63 % in 0.3 s).

The selection rule: a potentiometer knob that does not spring back to center means angle mode (knob position = camera position); a spring-centered stick or a wheel means rate mode, otherwise the camera snaps back to zero as soon as you release the stick. Pick the rate by the task: 30 °/s covers the full ±45° travel in 3 s; for precise pointing on a long lens, 10…15 °/s.

Roll cannot be controlled from the RC in rate mode: the code shows it, and there is no `MNT_RATE_ROLL` parameter.

### From angle to microseconds
For the AUX output (`output.cpp`, `output_rc.cpp`, v1.18.0) the order of operations is:

1. The angle setpoint in degrees: from a command, from the integrated rate, or from the computation toward an ROI point.
2. An axis whose setpoint is given in the world frame (lock mode: `gimbal test`, the stick in angle mode, MAVLink commands with the lock flag) gets it only if stabilization is on for that axis: `MNT_DO_STAB` = 1 all axes, 2 yaw, 3 (since 1.18) pitch; then the vehicle angle is subtracted from the setpoint. **With `MNT_DO_STAB` = 0 such a setpoint does not reach the output in 1.18**: in SITL v1.18.0 `gimbal test pitch -30` left `gimbal_controls` at zero with 0 and gave −0.5 with 1. Setpoints in the vehicle frame (the stick in rate mode, ROI pitch, neutral) pass with any value.
3. Limits: pitch is clamp(θ, `MNT_MIN_PITCH`, `MNT_MAX_PITCH`) (−45 and +45 by default; the limits can be asymmetric); roll and yaw are ±`MNT_RANGE_ROLL`/2 and ±`MNT_RANGE_YAW`/2, as before.
4. On the ground (landed or maybe landed) pitch is additionally clamped to `MNT_LND_P_MIN`…`MNT_LND_P_MAX`.
5. The `MNT_TAU` filter (0.3 s): the output approaches the setpoint exponentially; the steady-state value is the same.
6. Normalization by half-axis (`OutputRC::anglesMappedToOutput`): θ ≥ 0 → c = θ / `MNT_MAX_PITCH`, θ < 0 → c = θ / |`MNT_MIN_PITCH`|; for roll and yaw c = θ / (`MNT_RANGE`/2). This is the `gimbal_controls` topic field, −1…+1.
7. `mixer_module`: µs = `MIN` + (c + 1)/2 · (`MAX` − `MIN`); with `PWM_AUX_CENTn` (FMU outputs, since 1.17) two lines: c < 0 → `CENT` + c · (`CENT` − `MIN`), c ≥ 0 → `CENT` + c · (`MAX` − `CENT`) (`px4-outputs-servos`).

Example: `MNT_MIN_PITCH` = −90, `MNT_MAX_PITCH` = 30, output 1000…2000 µs without `CENT`. Nadir, θ = −90°: c = −1, 1000 µs. θ = −45°: c = −0.5, 1250 µs. θ = +15°: c = 15/30 = 0.5, 1750 µs. Zero degrees always gives c = 0: the midpoint between `MIN` and `MAX`, or `CENT`.

Before 1.18 it worked differently: a single symmetric `MNT_RANGE_PITCH` (90 by default, c = θ / (`MNT_RANGE_PITCH`/2)) and a zero offset `MNT_OFF_*` added before normalization. On upgrade `MNT_RANGE_PITCH` migrates as `MNT_MAX_PITCH` = +range/2, `MNT_MIN_PITCH` = −range/2 (`param_translation.cpp`); `MNT_OFF_*` do not migrate, so you set the zero with the output trim (`PWM_AUX_CENTn`).

What follows from this:

- `MNT_MIN_PITCH` and `MNT_MAX_PITCH` are the angles the gimbal travels from zero to the `MIN` pulse and to the `MAX` pulse (or `CENT` → `MIN` and `CENT` → `MAX`). Measure them on the bench; a wrong value turns "−45°" into some other real angle.
- The limits also clamp the commands: with the −45…+45 defaults the −90° nadir is unreachable. Need nadir? `MNT_MIN_PITCH` = −90 (or lower); the upper limit does not change.
- You set the zero on the output: `PWM_AUX_CENTn` is the pulse at which the camera looks straight ahead. 1.18 has no separate angle offset.
- `MNT_DO_STAB`: a servo gimbal without its own controller, 1 (otherwise the camera tilts with the frame); a gimbal with its own IMU, 0; 2 when the gimbal holds roll and pitch itself but the autopilot must compensate yaw in lock mode; 3 (since 1.18) compensate pitch only. Remember item 2 above: the rule works per axis. With 0 in 1.18 the gimbal obeys only vehicle-frame setpoints; with 2, world-frame roll and pitch setpoints do not reach AUX (and the stick in angle mode always sends them that way, `input_rc.cpp`), with 3, roll ones do not (`output.cpp`, v1.18.0).
- `MNT_LND_P_MIN/MAX` (−90 and +90 by default, that is, no limit) are needed if on the ground the camera hits the dirt or the landing gear: for example −20 and +20.

When disarmed the gimbal output sits at `PWM_AUX_DISn`; with `COM_PREARM_MODE` = 2 the servo starts moving 5 s after boot. **The `gimbal test pitch -45` command and stick movement with prearm on really move the mechanism**: keep hands and cables out of its travel.

### MAVLink Gimbal v2 as PX4 implements it
The manager and device roles are described in `payload-gimbal`; here is what firmware 1.18.0 actually does.

| Direction | Message or command | Behavior |
|---|---|---|
| accepts | `GIMBAL_MANAGER_SET_ATTITUDE` | only from whoever has primary control; silently ignores everyone else |
| accepts | `GIMBAL_MANAGER_SET_MANUAL_CONTROL` | the same; normalized rates are multiplied by `MNT_RATE_PITCH` / `MNT_RATE_YAW` |
| accepts | `MAV_CMD_DO_GIMBAL_MANAGER_PITCHYAW` | from the primary control owner `ACCEPTED`; from others `DENIED` |
| accepts | `MAV_CMD_DO_GIMBAL_MANAGER_CONFIGURE` | assigns primary control: 0…255 an id, −1 leave unchanged, −2 the autopilot, −3 release |
| accepts | `DO_SET_ROI_LOCATION`, `DO_SET_ROI_WPNEXT_OFFSET`, `DO_SET_ROI_NONE` | through `navigator` → the `vehicle_roi` topic; primary control is not checked |
| accepts | `DO_MOUNT_CONTROL`, `DO_MOUNT_CONFIGURE` | kept for old missions |
| sends | `GIMBAL_MANAGER_STATUS` | 0.5 Hz in the Normal and Onboard sets; carries the current control owner |
| sends | `GIMBAL_MANAGER_INFORMATION` | on `MAV_CMD_REQUEST_MESSAGE`; for the AUX output the limits come from `MNT_MIN/MAX_PITCH` and ±`MNT_RANGE_ROLL/YAW`/2 in radians (1.17 sent degrees and full travel) |
| sends | `GIMBAL_DEVICE_SET_ATTITUDE` | to the device: 20 Hz in the Gimbal set, 5 Hz in Normal and Onboard |
| sends | `GIMBAL_DEVICE_ATTITUDE_STATUS` | 5 Hz in Normal and Onboard (1 Hz in 1.17); for the AUX output the autopilot builds it itself with device id 1 |

What is missing: there is no `GIMBAL_MANAGER_SET_PITCHYAW` handler in 1.17.0 or 1.18.0, so send a stream of angles through `GIMBAL_MANAGER_SET_ATTITUDE` or with the `DO_GIMBAL_MANAGER_PITCHYAW` command. Secondary control is not implemented (always 0 in the status), and the manager serves a single device.

A typical companion mistake: sending `DO_GIMBAL_MANAGER_PITCHYAW` without taking control first. The answer is `DENIED`, and the console shows "GIMBAL_MANAGER_PITCHYAW from … denied". First `DO_GIMBAL_MANAGER_CONFIGURE` with your own sysid and compid in param1 and param2, then the angles. Check with `gimbal status`, the "Primary control: sysid/compid" line; to set the owner by hand, `gimbal primary-control <sysid> <compid>`.

If the last setpoint was a rate and updates stopped for 2 s, the rate is zeroed (since 1.16): the gimbal will not keep spinning after a link loss.

{{diagram:px4-gimbal-flow|MNT_MODE_IN selects the command source, MNT_MODE_OUT the channel to the gimbal; PX4 computes limits, filtering and stabilization only for the AUX and MAVLink v1 outputs.}}

### The gimbal in a mission
- **ROI.** `DO_SET_ROI_LOCATION` points the gimbal at a location: yaw is the absolute bearing to it, pitch comes from the height difference. `DO_SET_ROI_WPNEXT_OFFSET` points at the current waypoint with offsets, `DO_SET_ROI_NONE` returns to neutral.
- **`MIS_MNT_YAW_CTL`** (default 0). With 0 a multicopter with an active ROI turns its nose to the point itself, and the gimbal adds the pitch. With 1 the vehicle flies nose along the track, and only the gimbal looks at the point. The rule: a two-axis gimbal without a yaw axis, 0; a three-axis one, 1 if flying nose-forward matters. The parameter has no effect on a plane.
- **`MIS_YAW_ERR`** (12°) and **`MIS_YAW_TMT`** (−1, disabled) do not configure the gimbal: they are the heading tolerance and timeout for accepting a waypoint. But with `MIS_MNT_YAW_CTL` = 0 they are exactly what decides when a vehicle turning toward an ROI counts as turned.
- **`DO_GIMBAL_MANAGER_PITCHYAW` in a mission** goes out on behalf of the autopilot, so the autopilot must have primary control: put `DO_GIMBAL_MANAGER_CONFIGURE` before it in the mission (`navigator` takes control by itself only for the deprecated `DO_MOUNT_CONTROL`). After the command the mission waits `MIS_COMMAND_TOUT` seconds (0 by default) so the gimbal can settle before capture starts.
- **Mission end, RTL and Land.** `navigator` takes control, sends the gimbal the neutral flag and releases control (since 1.17 with a 250 ms delay).

### `MNT_*` reference
| Parameter | Default | Range | Meaning |
|---|---|---|---|
| `MNT_MODE_IN` | −1 | −1…5 | command source; reboot |
| `MNT_MODE_OUT` | 0 | 0…2 | output: AUX / MAVLink v1 / v2; reboot |
| `MNT_MAN_ROLL`, `_PITCH`, `_YAW` | 0 | 0…6 | AUX number for the axis, 0 disabled |
| `MNT_RC_IN_MODE` | 1 | 0…1 | 0 angle, 1 angular rate |
| `MNT_RATE_PITCH`, `MNT_RATE_YAW` | 30 °/s | 1…90 | rate at full deflection |
| `MNT_MIN_PITCH` / `MNT_MAX_PITCH` (since 1.18) | −45° / +45° | — | pitch travel from zero to the output's `MIN` and `MAX`, and the command limit (AUX); before 1.18 `MNT_RANGE_PITCH` 90° |
| `MNT_RANGE_ROLL` | 90° | 1…720 | full roll travel between `MIN` and `MAX` (AUX), symmetric |
| `MNT_RANGE_YAW` | 360° | 1…720 | the same for yaw |
| `MNT_TAU` (since 1.18) | 0.3 s | ≥ 0 | setpoint filter time constant (AUX); 0 means no filter |
| `MNT_FIXED_PITCH` (since 1.18) | 0° | −90…90 | pitch in `MNT_MODE_IN` = 5 |
| `MNT_DO_STAB` | 0 | 0…3 | 0 off, 1 all axes, 2 yaw in lock, 3 (since 1.18) pitch in lock |
| `MNT_LND_P_MIN` / `MNT_LND_P_MAX` | −90° / +90° | −90…90 | pitch limits on the ground |
| `MNT_MAV_SYSID` / `MNT_MAV_COMPID` | 1 / 154 | — | gimbal address for the v1 output |
| `MIS_MNT_YAW_CTL` | 0 | 0…1 | who turns toward the ROI in yaw |

The 1.15.4, 1.16.2 and 1.17.0 trees have no `MNT_TAU` parameter: setpoint smoothing appeared only in 1.18. `MNT_OFF_ROLL`, `MNT_OFF_PITCH`, `MNT_OFF_YAW` and `MNT_RANGE_PITCH` from older guides are removed in 1.18 (`gimbal_params.yaml`, v1.18.0).

### Choosing the gimbal setup
| Gimbal | `MNT_MODE_OUT` | Wiring | Source (`MNT_MODE_IN`) | What to check afterwards |
|---|---|---|---|---|
| Two servos, no controller of its own | 0, `MNT_DO_STAB` = 1 | signal to the outputs with functions 420 / 421, servo power from a separate BEC | 1 RC only; 0 RC and mission | `gimbal test pitch -45`: the pulse matches the calculation; it does not hit the ground when landed |
| Brushless with a controller and a PWM input | 0, `MNT_DO_STAB` = 0 | output 421 → the controller's "pitch" input, common ground | 0 or 1; the stick in rate mode with `MNT_TAU` = 0 | tilting the frame does not change the camera angle; the stick gives the expected angle. In 1.18 with `MNT_DO_STAB` = 0, world-frame setpoints do not pass (`gimbal test`, the stick in angle mode, lock commands); check on the bench that the commands you need move the gimbal |
| MAVLink gimbal (Gimbal v2 device) | 2 | UART: TX↔RX, ground; `MAV_n_MODE` = 10 | 4, or 0 with the RC | `gimbal status`: "gimbal device compid found"; the ground station sees `GIMBAL_DEVICE_ATTITUDE_STATUS` |
| MAVLink gimbal that understands only `DO_MOUNT_CONTROL` | 1 | UART; `MNT_MAV_SYSID` / `MNT_MAV_COMPID` = gimbal address | 0 or 4 | the gimbal follows `gimbal test`; angles in degrees |

The rule: if the gimbal can act as a Gimbal v2 device, set 2; then the gimbal handles limits and stabilization itself and PX4 stays the manager. If it cannot, AUX. The 1.17.0 and 1.18.0 trees have no vendor-specific drivers (Siyi, Gremsy, STorM32): only generic MAVLink v1 / v2 works. Which of the two roles a particular model supports, and from which firmware version, check in the vendor's documentation (not verified).

### Camera trigger: mode and interface
`TRIG_MODE` decides when to shoot:

| Value | Mode | When to choose it |
|---|---|---|
| 0 | disabled (driver not running) | no camera |
| 1 | time based, on command | a timelapse over a mission segment, turned on by `DO_TRIGGER_CONTROL` |
| 2 | time based, always on | bench tests, VIO synchronization; **shoots from boot, including on the ground** |
| 3 | distance based, always on | capture without a mission; shoots on the way to the area too |
| 4 | distance based, on command | mapping: QGC Survey turns capture on and off with mission commands |

The rule: area mapping means 4. Overlap is set in meters on the ground, so a time-based mode in wind gives different spacing on the upwind and downwind legs.

`TRIG_INTERFACE` decides what releases the shutter:

| Value | Interface | Signal | What you configure |
|---|---|---|---|
| 1 | GPIO | a level on a pin, 3.3 V | `TRIG_POLARITY` (0 active low, idle high; 1 the reverse), `TRIG_ACT_TIME` |
| 2 | Seagull MAP2 | PWM, two outputs | levels hard-coded in the driver; camera power and keep-alive |
| 3 | MAVLink | no pin | the `CAMERA_TRIGGER` stream on the right channel |
| 4 (default) | Generic PWM | a servo pulse | `TRIG_PWM_NEUTRAL` → `TRIG_PWM_SHOOT` for `TRIG_ACT_TIME` |

The pin is assigned with the **Camera Trigger (2000)** output function on the Actuators screen. The `TRIG_PINS` and `TRIG_PINS_EX` parameters from older guides do not exist in the 1.15–1.17 trees. The driver looks for function 2000 in `PWM_AUX_FUNCn` on a board with an IO processor (fmu-v6x, fmu-v6c) and in `PWM_MAIN_FUNCn` on a board without one. The trigger does not work on IO outputs (MAIN on the Pixhawk 6X), and on the FMU it takes the whole timer group (`px4-outputs-servos`).

**Safety.** In GPIO mode the pin goes to its idle level right after the driver starts: with `TRIG_POLARITY` = 0 that is high. If that output drives not a camera but a relay or a drop mechanism, a polarity mistake will fire it at boot. Check the level with a multimeter before you connect the load.

### Distance-based capture: what the driver does
The driver loop runs every 50 ms. In modes 3 and 4 it takes the horizontal position from `vehicle_local_position` and compares the distance from the last shot's position with `TRIG_DISTANCE`.

- The first frame is taken right after capture is enabled, as soon as the position is valid.
- The distance is a straight line in the XY plane, not the path flown.
- Because of the 50 ms step the actual spacing lies between D and D + v · 0.05 s: at 12 m/s that is up to +0.6 m.
- `TRIG_MIN_INTERVA` is the minimum interval between releases, ms. If the next release comes earlier, it is **skipped, not delayed**: the distance reference point has already moved, so a whole frame drops out and the spacing doubles. In ArduPilot (`per-mapping`, `ap-payload`, `CAM1_INTRVAL_MIN`) the release is delayed instead, so the behavior differs.
- `MAV_CMD_DO_SET_CAM_TRIGG_DIST`: param1 > 0 writes the new value to `TRIG_DISTANCE` and enables capture; 0 pauses; −1 disables. param2 > 0 changes `TRIG_ACT_TIME` only in GPIO mode. param3 > 0 takes one frame immediately.
- `MAV_CMD_DO_TRIGGER_CONTROL`: param1 = 1 / 0 enables and disables, param2 = 1 resets the frame counter, param3 = 1 / 0 pauses and resumes.
- The driver does not handle `MAV_CMD_IMAGE_START_CAPTURE`. `navigator` turns a single shot (param3 = 1) into `DO_DIGICAM_CONTROL`, which the driver executes and numbers; a series (param3 = 0 or > 1) goes to the camera component (compid from param1, otherwise 100), and those frames do not appear in the trigger topics.
- On leaving a mission `navigator` pauses the trigger, and if a series was running it sends `IMAGE_STOP_CAPTURE`.

The trap: `DO_SET_CAM_TRIGG_DIST` enables capture in any mode. With `TRIG_MODE` = 1 a Survey mission starts a timer with period `TRIG_INTERVAL` (40 ms by default), and the camera fires at a rate limited only by `TRIG_MIN_INTERVA`.

Each release publishes the `camera_trigger` topic (`timestamp`, `timestamp_utc`, `seq`, `feedback = false`). The `seq` counter is 32-bit. A `camera_trigger test` shot is neither numbered nor logged.

### `TRIG_*` and `CAM_CAP_*` reference
| Parameter | Default | Range | Meaning |
|---|---|---|---|
| `TRIG_MODE` | 0 | 0…4 | capture mode |
| `TRIG_INTERFACE` | 4 (3 in SITL) | 1…4 | release method |
| `TRIG_INTERVAL` | 40 ms | 4…10000 | period in modes 1 and 2 |
| `TRIG_DISTANCE` | 25 m | ≥ 0 | spacing in modes 3 and 4 |
| `TRIG_MIN_INTERVA` | 1 ms | 1…10000 | minimum between releases |
| `TRIG_ACT_TIME` | 40 ms | 0.1…3000 | pulse duration; at least 40 ms in the PWM modes |
| `TRIG_POLARITY` | 0 | 0…1 | GPIO active level |
| `TRIG_PWM_SHOOT` / `TRIG_PWM_NEUTRAL` | 1900 / 1500 µs | 1000…2000 | pulses for interface 4 |
| `CAM_CAP_FBACK` | 0 | 0…1 | enable feedback |
| `CAM_CAP_MODE` | 0 | 0…2 | 0 edge timestamp; 1 / 2 mid-exposure (active high / low) |
| `CAM_CAP_EDGE` | 0 | 0…1 | 0 falling, 1 rising (for mode 0) |
| `CAM_CAP_DELAY` | 0 ms | 0…100 | subtracted from the edge time: strobe delay from the start of exposure |

Every parameter in the table is read when the driver starts: reboot the board after a change (`CAM_CAP_DELAY` has no reboot flag in the metadata, but it is read in the same place). Set `TRIG_MIN_INTERVA` to the camera's minimum cycle from its spec sheet: the default of 1 ms protects nothing.

### Shutter feedback: `camera_capture`
The release command and the actual shutter are separated by the camera's delay. The hot shoe signal (the flash contact, through an optocoupler) goes to an FMU output with the **Camera Capture (2032)** function; `CAM_CAP_FBACK` = 1 starts the driver. On the edge (`CAM_CAP_EDGE`) the timer records the time, the driver subtracts `CAM_CAP_DELAY` and publishes the same `camera_trigger` topic, but with `feedback = true` and its own `seq` counter.

`camera_feedback` builds the `camera_capture` topic from it: with `CAM_CAP_FBACK` = 0 from the release commands, with 1 **only** from the feedback signals, and commands are discarded. The record holds `timestamp`, `timestamp_utc`, `seq`, `lat`, `lon`, `alt`, `ground_distance` and the quaternion `q` (gimbal orientation if its status is fresher than 1 s, otherwise the vehicle's). The position is the latest `vehicle_global_position` estimate at processing time, not interpolated to the frame time.

What this means in practice:

- Without feedback `camera_capture` holds the time and position of the **command**. The along-track error is v · τ, where τ is the "command → shutter" delay.
- With feedback the number of `camera_capture` records equals the number of frames actually taken. Misses show up as the difference between the number of `camera_trigger` records with `feedback = false` and with `feedback = true`.
- If the feedback wire breaks with `CAM_CAP_FBACK` = 1, `camera_capture` is empty. You then build geotags from `camera_trigger` and `vehicle_global_position`.
- `CAM_CAP_MODE` modes 1 and 2 are marked "not fully tested" in the source; in mode 1 the frame counter increments twice per frame. For geotags use mode 0.
- The driver treats a signal faster than 5 kHz as a fault and disables capture with the message "Hardware fault: Camera capture disabled".

### Log, MAVLink and geotags
- **ULog.** The full log has `camera_capture` and `camera_trigger`. `SDLOG_MISSION` = 2 (Geotagging) additionally writes a small "mission log" with just `camera_capture`; 1 adds `vehicle_global_position`, `vehicle_status`, `mission_result` too.
- **MAVLink.** `CAMERA_TRIGGER` (command time and number) goes out in the Onboard and Config (USB) sets; Normal does not have it. `CAMERA_IMAGE_CAPTURED` (from `camera_capture`: time, position, quaternion, number) is in Normal, Onboard and Config. On each event the same `CAMERA_TRIGGER` stream sends `MAV_CMD_IMAGE_START_CAPTURE` and `DO_DIGICAM_CONTROL` to components 100…105, which is how a MAVLink camera fires with `TRIG_INTERFACE` = 3. Hence the rule: the link to such a camera needs `MAV_n_MODE` = 2 (Onboard).
- **Matching.** Frame k on the memory card ↔ the record with `seq` = k − 1 (if the counter was reset before the survey). Compare the number of files and records first; if they differ, find the miss, otherwise every tag after it shifts by one step.
- **Delay correction without feedback.** t_frame = t_command + τ; take the position by interpolating `vehicle_global_position` at t_frame, or shift it along the track by v · τ. The correction removes a constant τ completely; the spread Δτ remains as an error of v · Δτ.
- **Tools.** The PX4 documentation suggests geotagging in QGroundControl: you point it at the log and the folder with frames. Which topic QGC reads and how it handles misses is outside the PX4 tree, not verified. A typical home-made pipeline: `pyulog` → CSV of the `camera_capture` topic → writing the positions into EXIF.

A question from the PX4 forum: "capture stops at exactly 255 frames". In the 1.17.0 and 1.18.0 driver the frame counters are 32-bit and there is no 255 limit; in the discussion on discuss.px4.io (PX4 1.15.4, a MAVLink camera) the cause was not found. How to investigate yourself: count the `camera_trigger` records in the log. If there are more than 255, PX4 kept commanding, and the problem is in the camera and its link.

### Capture arithmetic
Where footprint, GSD and overlap come from is in `per-mapping`. For the PX4 parameters you need four formulas:

- spacing: `TRIG_DISTANCE` = F · (1 − p), where F is the frame size on the ground along the track and p is the forward overlap;
- interval: T = `TRIG_DISTANCE` / v, where v is the groundspeed (higher on the downwind leg);
- condition: T ≥ max(`TRIG_MIN_INTERVA`, camera cycle); the speed limit is v_max = `TRIG_DISTANCE` / cycle;
- number of frames on a leg of length L: N = ⌊L / `TRIG_DISTANCE`⌋ + 1 (the first frame is at the start).

Example: F = 90 m, p = 80 % → 18 m; at 12 m/s T = 1.5 s; a 600 m leg gives 34 frames. If T comes out below `TRIG_MIN_INTERVA`, every other frame drops out and the overlap becomes 1 − 2 · 18 / 90 = 60 %.

{{diagram:chart-px4-trigger-interval|The interval between frames falls in inverse proportion to speed: with a 90 m frame and 80 % overlap a camera with a 1.2 s cycle stops keeping up above 15 m/s, and at 85 % already above 11 m/s.}}

### Choosing the trigger interface and feedback
| Camera | `TRIG_INTERFACE` | Wiring | What to check afterwards |
|---|---|---|---|
| A logic-level "trigger" input, an optocoupler, a relay | 1 | an FMU pin with function 2000 → the input, common ground; 3.3 V level | the idle level with a multimeter; `camera_trigger test` gives one frame |
| A remote release with a PWM input, an IR remote, a servo pressing a button | 4 | an FMU output with function 2000, like a servo | a frame at `TRIG_PWM_SHOOT`, idle at `TRIG_PWM_NEUTRAL`; `TRIG_ACT_TIME` ≥ 40 ms |
| Seagull MAP2 | 2 | two FMU outputs with function 2000 | the camera turns on and does not fall asleep |
| A MAVLink camera (a separate component) | 3 | UART or Ethernet, `MAV_n_MODE` = 2 | the camera responds to `IMAGE_START_CAPTURE`; `camera_trigger` grows in the log |

You need hot shoe feedback when v · Δτ exceeds the allowed frame position error, where Δτ is the spread of the camera delay (the constant delay itself is removed by the correction). Plain GNSS with a 1.5 m error at 12 m/s and a 40 ms spread: 0.48 m, so feedback is optional. RTK/PPK with a 3 cm budget at the same 12 m/s requires knowing the frame moment within 2.5 ms: you cannot do without the hot shoe. The second reason to fit it is counting the frames actually taken.

### Differences across 1.15–1.18
Comparing the 1.15.4, 1.16.2, 1.17.0 and 1.18.0 trees:

| What | 1.15 | 1.16 | 1.17 | 1.18 |
|---|---|---|---|---|
| Pitch limits and zero | `MNT_RANGE_PITCH`, `MNT_OFF_*` | the same | the same | `MNT_MIN_PITCH` / `MNT_MAX_PITCH`, zero by output trim; `MNT_RANGE_PITCH` migrates as ±range/2 |
| `MNT_TAU` setpoint filter | no | no | no | 0.3 s; slows the stick in rate mode |
| `MNT_DO_STAB` = 3, `MNT_MODE_IN` = 5 (`MNT_FIXED_PITCH`) | no | no | no | yes |
| World-frame setpoint with `MNT_DO_STAB` = 0 (AUX) | passes | passes | passes | does not pass (SITL v1.18.0) |
| `TRIG_*`, `CAM_CAP_*` parameters | the same | the same | the same | the same (descriptions moved to `.yaml`) |
| 2 s timeout for a rate setpoint | no | yes | yes | yes |
| `DO_GIMBAL_MANAGER_PITCHYAW`: param3 / param4 rates | passed through without converting °/s to rad/s | converted | converted | converted |
| `GIMBAL_MANAGER_INFORMATION` | fixed limits | from the device information or from `MNT_RANGE_*` | as in 1.16 | for AUX from `MNT_MIN/MAX_PITCH` and `MNT_RANGE_*`/2 in radians |
| `GIMBAL_DEVICE_ATTITUDE_STATUS` in Normal and Onboard | 1 Hz | 1 Hz | 1 Hz | 5 Hz |
| `gimbal test` | angles only | angles or rates (`pitchrate` and others) | as in 1.16 | as in 1.16; angles only with `MNT_DO_STAB` ≠ 0 |
| `PWM_AUX_CENTn` for the Gimbal functions | no | no | yes | yes |
| Gimbal neutral on leaving a mission | immediately | immediately | after 250 ms | after 250 ms |
| SITL model `gz_x500_gimbal` | no | yes | yes | yes |

The `camera_trigger` and `camera_capture` drivers and the `camera_feedback` module did not change in logic between 1.16.2 and 1.18.0 (1.18 only moved the parameter descriptions to `.yaml` and refactored the module base class); the `gimbal` module did not change between 1.16.2 and 1.17.0, and in 1.18.0 it was rewritten (the rows of the table above).

### Place in the system

- **Takes in:** AUX channels from `manual_control_setpoint` (`px4-rc-tuning`); FMU outputs and timer groups (`px4-outputs-servos`); the MAVLink port and stream set (`px4-hardware-peripherals`); ROI and mission commands from `navigator`; position and attitude from state estimation; the protocol roles (`payload-gimbal`, `mav-services`); the trigger distance (`per-mapping`).
- **Gives out:** pulses to the servos and `GIMBAL_DEVICE_SET_ATTITUDE` to the gimbal; the shutter release; the `camera_trigger` and `camera_capture` topics for georeferencing (`per-mapping`); camera orientation in `CAMERA_IMAGE_CAPTURED` (`per-camera`).
- **If you get it wrong here:** `TRIG_MIN_INTERVA` above the capture interval → every other frame drops out and the orthomosaic tears in `per-mapping`; an uncorrected shutter delay → the map shifts by v · τ; the trigger in a timer group with servos → the servos stop working (`px4-outputs-servos`); on RTL the gimbal goes to neutral, so capture "on the way home" is useless (`px4-safety-return`).

## practice
An exercise without hardware or a simulator. You need paper or an editor and a calculator. All answers follow from the formulas and tables in the theory, and you check them against the reference at the end. The `gimbal_controls` values for step 1 (except the pulses with `CENT`, which SITL does not have) were checked in SITL v1.18.0 (SIH): they matched the reference within 0.002.

### Step 1. Gimbal servo pulse and the stick
A two-axis servo gimbal, pitch on output AUX6 of an fmu-v6x board (a teaching example, put together by hand, PX4 1.18):
```
MNT_MODE_IN       1
MNT_MODE_OUT      0
MNT_DO_STAB       1
MNT_MIN_PITCH     -60
MNT_MAX_PITCH     60
MNT_TAU           0
MNT_LND_P_MIN     -20
MNT_LND_P_MAX     20
MNT_RC_IN_MODE    1
MNT_RATE_PITCH    30
MNT_MAN_PITCH     2
RC_MAP_AUX2       7
PWM_AUX_FUNC6     421
PWM_AUX_MIN6      1100
PWM_AUX_MAX6      1900
PWM_AUX_CENT6     1460
```
The frame is assumed level, so the `MNT_DO_STAB` = 1 tilt correction is zero (and without it, in 1.18 world-frame setpoints would not reach the output). `PWM_AUX_CENT6` = 1460 is the trim: at this pulse the camera on the bench looks straight ahead. `MNT_TAU` = 0 so that the stick in rate mode works at the rated speed. A worked example, in flight, setpoint θ = −30°: the −60…+60° limit does not kick in; c = −30 / 60 = −0.5; c < 0 → µs = 1460 + (−0.5) · (1460 − 1100) = 1460 − 180 = **1280**.

Compute it yourself:

1. The pulse in flight for θ = 0°, −45°, −75°, +70°.
2. The pulse for θ = −45° when the vehicle is armed and on the ground (or disarmed with `COM_PREARM_MODE` = 2).
3. Rate mode, starting angle 0°. The stick is held at −0.5 for 3 s: what angle? The stick is held at −1.0 for 4 s: what angle, and after how many seconds did it stop changing?
4. `MNT_RC_IN_MODE` was switched to 0. What angle does the stick give at −0.5, and at −1.0?
5. What `MNT_MIN_PITCH` value lets the gimbal accept a "nadir" command, what happens to the upper limit, and how many degrees per 1 µs does that give on the lower half of travel with the same `MIN` and `CENT`? And on the upper half?
6. `MNT_TAU` was set back to the 0.3 default. What happens to the answers of task 3, and why do the answers of tasks 1, 2 and 4 not change?

### Step 2. Trigger distance and interval
Given: the frame on the ground along the track F = 90 m (a number from the `per-mapping` calculation), forward overlap 80 %, groundspeed 12 m/s, minimum camera cycle per spec 1.2 s, `TRIG_MIN_INTERVA` = 1000 ms, leg length 600 m.

1. `TRIG_DISTANCE` and the interval between frames.
2. Does the interval satisfy `TRIG_MIN_INTERVA` and the camera cycle? What is the speed limit for this camera?
3. On the downwind leg the groundspeed is 16 m/s. What is the interval, and what happens to the frames?
4. How many frames on a 600 m leg? Give the ideal number and the lower bound given the 50 ms driver loop.
5. Someone set `TRIG_MIN_INTERVA` = 2000 ms. What do the spacing and overlap become at 12 m/s?

### Step 3. Geotag error from delay
The same survey, 12 m/s. The camera fires τ = 250 ms after the command, with a delay spread Δτ = ±40 ms. No feedback.

1. By how many meters, and in which direction from the true capture point, does the position from `camera_capture` lie?
2. How do you correct the position in processing, and what error remains after the correction?
3. Do you need hot shoe feedback if the allowed frame position error is 1.5 m? And if it is 3 cm (PPK)? For the second case compute the allowed timing error.

### Step 4. Three payloads and three errors
Part A. For each payload write down `MNT_MODE_IN`, `MNT_MODE_OUT`, `MNT_DO_STAB`, `TRIG_INTERFACE` and what the port or output is used for:

1. Two servos without a controller (roll and pitch); the operator turns pitch with a knob; the ground station does not control the gimbal. A camera with a remote release over a cable with a PWM input.
2. A brushless gimbal with its own controller and a PWM pitch input; both the stick and ROI in a mission are needed. An industrial camera with a logic-level trigger input and a strobe output; frame positions are needed at PPK accuracy.
3. A gimbal with a camera that announces itself as a Gimbal v2 device, on TELEM2; control only from the ground station and the mission. The camera is a MAVLink component on the same device.

Part B. A parameter fragment of a survey copter on fmu-v6x: `TRIG_DISTANCE` and the speed are from step 2, camera cycle 1.2 s (a teaching example, put together by hand). Find three errors and name the rule from the theory for each.
```
MNT_MODE_IN        1
MNT_MODE_OUT       0
MNT_MAN_PITCH      2
RC_MAP_AUX2        0
MNT_RC_IN_MODE     1
MNT_MIN_PITCH      -90
PWM_AUX_FUNC5      421
PWM_AUX_TIM1       50
PWM_MAIN_FUNC3     2000
TRIG_MODE          4
TRIG_INTERFACE     4
TRIG_DISTANCE      18
TRIG_MIN_INTERVA   2000
TRIG_ACT_TIME      40
CAM_CAP_FBACK      0
```

### Moving to real hardware
Only after all four steps check out. The propellers stay off until the end of the procedure.

1. Gimbal servos from a separate BEC, ground common with the flight controller (`px4-outputs-servos`). Assign functions 420…422, set `MNT_MODE_IN` and `MNT_MODE_OUT`, reboot the board.
2. Keep hands and cables out of the gimbal's travel. In the console: `gimbal status`, then `gimbal test pitch -30` (in 1.18 an angle from `gimbal test` passes only with `MNT_DO_STAB` ≠ 0). Disarmed, the servo moves only with prearm on (`COM_PREARM_MODE`); measure the pulse and compare it with the step 1 calculation.
3. Zero with `PWM_AUX_CENTn` (the pulse at which the camera looks ahead), end stops with the output's `MIN` / `MAX`; then `MNT_MIN_PITCH` / `MNT_MAX_PITCH` (and `MNT_RANGE_ROLL` / `_YAW`) from the measured travel from zero to the end stops. Check that on the ground the camera does not reach the dirt; otherwise set `MNT_LND_P_MIN` / `MNT_LND_P_MAX`.
4. Trigger: before connecting the camera, measure the idle level on the pin with a multimeter. `TRIG_MODE` = 4, reboot, `camera_trigger test`: one frame.
5. Feedback: `CAM_CAP_FBACK` = 1, function 2032, reboot; after ten test frames `camera_capture status` shows "Frame sequence : 10".
6. Fly one leg: the number of files on the memory card equals the number of `camera_capture` records in the log.

Hardware criteria: the pulse on `gimbal test` matches the calculation ±10 µs; `gimbal status` shows the expected input, output and control owner; the number of frames on the card equals the number of `camera_capture` records; the interval between neighboring records is no less than the camera cycle.

Self-check: the lab is done when
- step 1: five pulses match the reference ±1 µs, the rate mode and angle mode angles match exactly, the `MNT_MIN_PITCH` for nadir and the cost of a microsecond on both halves are named, and for task 6 the reason is named (the filter inside the accumulation loop);
- step 2: `TRIG_DISTANCE`, both intervals and the speed limit match the reference (±0.01), the frame count is 34 with a lower bound of 33, the overlap with the wrong `TRIG_MIN_INTERVA` is 60 %;
- step 3: the 3.0 m error and its direction, the ±0.48 m residual and the 2.5 ms tolerance match, and both feedback decisions are justified by the v · Δτ rule;
- step 4: the nine values of part A match the reference table, and part B has exactly three errors with their rules.

**Reference for the self-check.**

Step 1. Lower half: 60° over 360 µs (1460 → 1100), 6 µs/°; upper: 60° over 440 µs (1460 → 1900), 7.33 µs/°.

| Task | Answer |
|---|---|
| θ = 0° | c = 0 → 1460 µs (`CENT`) |
| θ = −45° | c = −0.75 → 1460 − 270 = 1190 µs |
| θ = −75° | clamped to −60°, c = −1 → 1100 µs |
| θ = +70° | clamped to +60°, c = +1 → 1900 µs |
| θ = −45° on the ground (armed or with prearm) | clamped to −20°, c = −0.333 → 1460 − 120 = 1340 µs; without arming or prearm the output is at `PWM_AUX_DISn` |
| stick −0.5, 3 s | −45° |
| stick −1.0, 4 s | −60°; the end stop is reached after 2 s |
| angle mode, −0.5 and −1.0 | −45° and −60° (−90° clipped by the limit) |
| nadir | `MNT_MIN_PITCH` = −90 (the +60 upper limit does not change); lower half 90° / 360 µs = 0.25 °/µs, upper 60° / 440 µs ≈ 0.136 °/µs |
| `MNT_TAU` = 0.3 | in rate mode the angle accumulates about 30 times slower (in SITL v1.18.0 the stick at −0.5 gave about 1.5° in 3 s instead of 45°): the filter sits inside the accumulation loop and passes a fraction dt / (τ + dt) of each increment. For angle setpoints (tasks 1, 2, 4) the filter only eases the gimbal in; the steady-state pulse is the same |

Step 2. `TRIG_DISTANCE` = 90 · 0.2 = 18 m; T = 18 / 12 = 1.5 s, which satisfies both 1.0 s and 1.2 s; v_max = 18 / 1.2 = 15 m/s. At 16 m/s T = 1.125 s: the `TRIG_MIN_INTERVA` = 1.0 s limit does not kick in (1.125 > 1.0), the command goes out, but a camera with a 1.2 s cycle cannot keep up, so frames are lost inside the camera, and without feedback the log does not show it; the cure is `TRIG_MIN_INTERVA` = 1200 and a speed no higher than 15 m/s. Frames: ⌊600 / 18⌋ + 1 = 34; with spacing up to 18.6 m, ⌊600 / 18.6⌋ + 1 = 33. With `TRIG_MIN_INTERVA` = 2000 ms: 1.5 s < 2 s, every other frame drops out, spacing 36 m, overlap 1 − 36 / 90 = 60 %.

Step 3. The error is 12 · 0.25 = 3.0 m; the recorded point lies **behind** the true one along the flight direction (the frame was taken later and farther on). Correction: frame time = command time + 0.25 s and interpolate the position, or shift 3.0 m forward along the track. Residual ±12 · 0.04 = ±0.48 m. With a 1.5 m tolerance: 0.48 < 1.5, a constant correction is enough. With a 3 cm tolerance: you must know the time within 0.03 / 12 = 2.5 ms; the 40 ms spread is 16 times larger, so feedback is mandatory.

Step 4, part A.

| Payload | `MNT_MODE_IN` | `MNT_MODE_OUT` | `MNT_DO_STAB` | `TRIG_INTERFACE` | Used |
|---|---|---|---|---|---|
| 1 | 1 | 0 | 1 | 4 | FMU outputs: 420, 421 and 2000 in a separate group |
| 2 | 0 | 0 | 0 | 1 | output 421; 2000 and 2032 on the FMU, `CAM_CAP_FBACK` = 1; in 1.18 the stick in rate mode (`MNT_RC_IN_MODE` = 1) with `MNT_TAU` = 0: world-frame angle setpoints do not pass with `MNT_DO_STAB` = 0 |
| 3 | 4 | 2 | no effect | 3 | TELEM2: `MAV_1_MODE` = 10 |

For payload 3 an honest answer has a caveat: the Gimbal set (10) does not include the `CAMERA_TRIGGER` stream that a MAVLink camera needs (the Onboard set, 2). On one port the two requirements cannot both be met without configuring streams by hand; how a particular device behaves you check on the bench.

Step 4, part B. (1) `RC_MAP_AUX2` = 0 with `MNT_MAN_PITCH` = 2: nobody fills the aux2 field, so the stick does nothing. (2) `PWM_MAIN_FUNC3` = 2000: on a board with IO the driver reads only `PWM_AUX_FUNCn`, so the trigger does not work on an IO output. (3) `TRIG_MIN_INTERVA` = 2000 ms with a 1.5 s interval: every other frame drops out; it should be 1200 (the camera cycle).

Typical wrong answers and their cause:

- θ = −45° → 1200 µs or θ = 0° → 1500 µs: computed with a single line 1100…1900 through the 1500 midpoint instead of two lines through `CENT` = 1460.
- θ = −45° on the ground → 1190 µs: the `MNT_LND_P_MIN` clamp forgotten.
- The old-style answer c = (θ + offset) / (range/2): 1.18 has no angle offset, the zero is set by `CENT`.
- 33 frames instead of 34: the first frame at the start of the leg forgotten.
- In part B, `MNT_MIN_PITCH` = −90 or `CAM_CAP_FBACK` = 0 called an error: both values are acceptable; −90 is exactly what nadir needs.

## diagnostics
- **Symptom:** `gimbal status` answers "not running", the gimbal is dead.
  - Possible cause: `MNT_MODE_IN` = −1 (the default), or the board was not rebooted after the change.
  - What to do: set 0, 1 or 4, reboot, repeat `gimbal status`.
- **Symptom:** `gimbal test pitch -45` is accepted, but the servo does not move.
  - Possible cause: the vehicle is disarmed and prearm is off, so the output is at `DIS`; function 421 is not assigned; the servo is in a timer group with DShot.
  - What to do: `COM_PREARM_MODE`, the Actuators screen, timer groups as in `px4-outputs-servos`. Keep your hands out of the travel before the test.
- **Symptom:** the gimbal does not reach nadir and stops at −45°.
  - Possible cause: `MNT_MIN_PITCH` = −45 (the default; before 1.18 `MNT_RANGE_PITCH` = 90), so the command is clipped to −45°.
  - What to do: `MNT_MIN_PITCH` = −90 and recompute the pulse mapping for the lower half of travel; the upper limit can stay.
- **Symptom:** the RC stick does not move the gimbal.
  - Possible cause: `RC_MAP_AUXn` = 0; in Auto mode the stick moves less than 0.25 on the −1…+1 scale (12.5 % of full travel); `MNT_MODE_IN` = 4.
  - What you see in the log: `manual_control_setpoint.aux2` is constantly 0, or it changes while `gimbal_controls` does not.
  - What to do: assign the channel, give the stick a large move, check the input mode.
- **Symptom:** a servo gimbal with `MNT_DO_STAB` = 1 and the stick in rate mode (`MNT_RC_IN_MODE` = 1) runs into the end stop when the frame is tilted.
  - Possible cause: not confirmed; from reading the 1.17.0 `output.cpp`, the frame tilt subtraction in this combination could accumulate from loop to loop (a possible firmware defect). In 1.18 this path was rewritten (`set_last_valid_setpoint` returns the frame angle into the stored setpoint); neither 1.17 nor 1.18 was run with a tilted frame.
  - What to do: before relying on this combination, check it on the bench: tilt the frame by 10°; the camera should return to the horizon and stop, not run into the end stop; if it runs away, `MNT_RC_IN_MODE` = 0.
- **Symptom:** after updating to 1.18 the stick in rate mode barely moves the gimbal (a degree per second instead of tens).
  - Possible cause: `MNT_TAU` = 0.3 (the 1.18 default): the filter inside the accumulation loop passes about 1/30 of each increment.
  - What you see in the log: `manual_control_setpoint.aux2` holds steady, `gimbal_controls` grows slowly and evenly.
  - What to do: `MNT_TAU` = 0, or angle mode (`MNT_RC_IN_MODE` = 0, with `MNT_DO_STAB` ≠ 0).
- **Symptom:** on 1.18 `gimbal test pitch …`, the stick in angle mode or a ground station command with the lock flag do not move the servo gimbal, while the stick in rate mode does.
  - Possible cause: `MNT_DO_STAB` = 0: in 1.18 a world-frame setpoint does not reach the AUX output (tested in SITL v1.18.0).
  - What to do: a servo gimbal without a controller, `MNT_DO_STAB` = 1 (or 3 for pitch); a gimbal with its own IMU, the stick in rate mode and `MNT_TAU` = 0, checked on the bench.
- **Symptom:** the companion gets `DENIED` for `DO_GIMBAL_MANAGER_PITCHYAW`.
  - Possible cause: another component has primary control (the RC, the ground station, the autopilot after a mission).
  - What to do: first `DO_GIMBAL_MANAGER_CONFIGURE` with your own ids; check `gimbal status` and `GIMBAL_MANAGER_STATUS`.
- **Symptom:** the MAVLink gimbal is silent, the status says "gimbal device compid not found".
  - Possible cause: the gimbal does not send `GIMBAL_DEVICE_INFORMATION` (does not support the v2 device role), TX and RX are swapped, the port baud rate is wrong, the gimbal's system id does not equal `MAV_SYS_ID`.
  - What to do: `mavlink status` on the port, check the wiring and baud rate; if it cannot do v2, `MNT_MODE_OUT` = 1.
- **Symptom:** half as many frames on the card as planned, the spacing doubled.
  - Possible cause: `TRIG_MIN_INTERVA` is above the D / v interval, so the driver skips releases.
  - What you see in the log: intervals between `camera_trigger` records of about 2 · D / v.
  - What to do: `TRIG_MIN_INTERVA` = the camera cycle, speed no higher than D / cycle.
- **Symptom:** the log has all the commands, but there are fewer frames.
  - Possible cause: the camera cannot keep up (the interval is shorter than its cycle), a short `TRIG_ACT_TIME`, wrong polarity.
  - What to do: lower the speed or increase the spacing; `TRIG_ACT_TIME` per the camera's spec; add feedback so misses show up in `camera_capture`.
- **Symptom:** the camera fires nonstop right after the Survey segment starts.
  - Possible cause: `TRIG_MODE` = 1 or 2: the mission command started a timer with `TRIG_INTERVAL` = 40 ms.
  - What to do: `TRIG_MODE` = 4, reboot.
- **Symptom:** the orthomosaic is shifted along the legs, and neighboring legs form a "comb".
  - Possible cause: the shutter delay is not corrected; the legs are flown in opposite directions, so the v · τ shift changes sign.
  - Consequences: without ground control points the error doubles where the legs meet.
  - What to do: correct the time by τ during geotagging, or use hot shoe feedback.
- **Symptom:** after enabling `CAM_CAP_FBACK` the `camera_capture` topic is empty.
  - Possible cause: function 2032 is not assigned ("No capture channel configured"), a wrong `CAM_CAP_EDGE`, no signal from the hot shoe, `TRIG_MODE` = 0.
  - What to do: `camera_capture status`: the "Capture enabled" and "Frame sequence" lines; check the signal with an oscilloscope.

## checklist
- `MNT_MODE_IN` and `MNT_MODE_OUT` are chosen from the table, the board is rebooted, `gimbal status` shows the expected input and output.
- For the AUX output: functions 420…422 are assigned, the zero is set with `PWM_AUX_CENTn`, `MNT_MIN_PITCH` / `MNT_MAX_PITCH` and `MNT_RANGE_ROLL` / `_YAW` equal the measured travel, nadir is reachable.
- `MNT_DO_STAB` matches the gimbal type: 1 for servos without a controller, 0 for a gimbal with its own IMU (in 1.18 that means vehicle-frame setpoints only); for the stick in rate mode `MNT_TAU` = 0.
- For the RC both `MNT_MAN_*` and `RC_MAP_AUXn` are set; angle / rate mode is chosen by the type of knob.
- **Before `gimbal test` and with prearm on, hands and cables are out of the travel; on the ground the camera does not hit the dirt (`MNT_LND_P_*`).**
- In the mission, `DO_GIMBAL_MANAGER_CONFIGURE` comes before `DO_GIMBAL_MANAGER_PITCHYAW`; `MIS_MNT_YAW_CTL` is chosen by the number of axes.
- Trigger: function 2000 on an FMU output in its own timer group; `TRIG_MODE` = 4 for surveys.
- **The idle level of the trigger pin is measured before connecting the load; the "always on" modes (2, 3) are not used with anything that must not fire on the ground.**
- `TRIG_DISTANCE` = F · (1 − p); the D / v interval on the downwind leg is no shorter than the camera cycle; `TRIG_MIN_INTERVA` = the camera cycle.
- The number of frames on the card is compared with the number of log records before geotagging.
- The shutter delay is measured and corrected, or feedback is fitted (`CAM_CAP_FBACK`, function 2032).
- I remember that on RTL and Land the gimbal goes to neutral and the trigger is paused.

## references
- PX4 Guide v1.17: Gimbal Configuration | https://docs.px4.io/v1.17/en/advanced/gimbal_control | primary | A
- PX4 Guide v1.17: Cameras Connected to Flight Controller Outputs | https://docs.px4.io/v1.17/en/camera/fc_connected_camera | primary | A
- PX4-Autopilot v1.18.0: src/modules/gimbal/gimbal_params.yaml | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/modules/gimbal/gimbal_params.yaml | primary | A
- PX4-Autopilot v1.18.0: src/modules/gimbal/output.cpp | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/modules/gimbal/output.cpp | primary | A
- PX4-Autopilot v1.18.0: src/modules/gimbal/output_rc.cpp | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/modules/gimbal/output_rc.cpp | primary | A
- PX4-Autopilot v1.18.0: src/modules/gimbal/input_mavlink.cpp | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/modules/gimbal/input_mavlink.cpp | primary | A
- PX4-Autopilot v1.18.0: src/drivers/camera_trigger/camera_trigger.cpp | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/drivers/camera_trigger/camera_trigger.cpp | primary | A
- PX4-Autopilot v1.18.0: src/drivers/camera_capture/camera_capture.cpp | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/drivers/camera_capture/camera_capture.cpp | primary | A
- PX4-Autopilot v1.18.0: src/modules/camera_feedback/CameraFeedback.cpp | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/modules/camera_feedback/CameraFeedback.cpp | primary | A
- PX4-Autopilot v1.17.0: src/modules/mavlink/streams/CAMERA_TRIGGER.hpp | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/mavlink/streams/CAMERA_TRIGGER.hpp | primary | A
- PX4-Autopilot v1.18.0: ROMFS/px4fmu_common/init.d/rcS | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/ROMFS/px4fmu_common/init.d/rcS | primary | A
- MAVLink: Gimbal Protocol v2 | https://mavlink.io/en/services/gimbal_v2.html | primary | A
- PX4 Discuss: Image Capture Stops at Exactly 255 Photos | https://discuss.px4.io/t/px4-qgc-camera-trigger-issue-image-capture-stops-at-exactly-255-photos/48258 | secondary | C

## notes
The behavior is described from reading the v1.18.0, v1.17.0, v1.16.2 and v1.15.4 tag sources; the practice numbers are computed with the formulas from `output.cpp`, `output_rc.cpp`, `mixer_module.cpp` and `camera_trigger.cpp`. Step 1 of the practice for 1.18 was run in SITL v1.18.0 (SIH, `sihsim_quadx`, no RC; the stick through MAVLink `MANUAL_CONTROL` messages with the aux2 field): `gimbal_controls` for θ = −30, 0, −45, −75, +70° and for −45° on the ground (`MNT_LND_P_*` ±20) matched c from the reference within 0.002; rate mode with `MNT_TAU` = 0 gave 15 °/s at aux −0.5, with 0.3 about 0.5 °/s; angle mode and `gimbal test` with `MNT_DO_STAB` = 0 did not change the output. In SITL `pwm_out_sim` has no `MIN`/`MAX`/`CENT` (output 1000…2000), so the pulses with `CENT` = 1460 are computed from `mixer_module.cpp`, not run. Not tested with a tilted frame or on hardware. Not verified on hardware or outside the PX4 tree: which topic the QGroundControl geotagging tool reads; the behavior of particular gimbals and cameras (Siyi, Gremsy, STorM32 and others); how ground stations react to the missing gimbal manager flag with `MNT_MODE_IN` = 0; in which release `TRIG_PINS` was removed (it is already gone in 1.15–1.18). The "command → shutter" delay and the step 2–3 intervals do not depend on the firmware version: the trigger driver did not change in logic in 1.18. The parameter reference description of `MNT_MAV_COMPID` disagrees with the code: where they disagree, the source wins. Check the combination of `MNT_DO_STAB` = 1 with the stick in rate mode (`MNT_RC_IN_MODE` = 1) on the bench before relying on it: from reading `output.cpp`, the frame tilt subtraction in it may accumulate (not run, a possible firmware defect).
