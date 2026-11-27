---
id: px4-outputs-servos
source: content/px4/px4-outputs-servos.md
source_hash: b797a933ed79
title: "PX4 outputs: functions, timers, servos, control surfaces, relays"
level: L2
readingTime: 50 min
firmware: PX4 1.18 (checked against v1.18.0)
status: published
added: 2026-11-18
tags:
  - PX4
  - outputs
  - servos
  - DShot
  - control allocation
related:
  - px4-setup-scratch
  - px4-safety-return
  - px4-intro
  - ctl-allocation
  - f-esc-firmware
  - bf-servos-pwm
next:
  - px4-safety-return
---

## summary
The Actuators screen in QGroundControl and what stands behind it in the PX4 1.18.0 code: how a value travels from the controller to the pin, which functions you can put on an output and under which numbers, what `PWM_AUX_MINn` / `MAXn` / `DISn` / `FAILn` / `CENTn` / `REV` / `TIMn` mean, why a servo and a DShot motor cannot share a timer group, how MAIN (IO) differs from AUX (FMU), how to describe control surfaces with `CA_SV_*`, and what PX4 uses instead of relays. After the module you can lay out motors, servos and a camera trigger across outputs from the board's `timer_config.cpp` and compute a servo pulse the way `mixer_module` does. The lab needs no hardware and no simulator: an output plan for fmu-v6x, a microsecond calculation, the signs of `CA_SV_CSn_TRQ_*` and a parameter set with errors; you check the answers against the reference on the page.

## theory
### The path of a value: from torque to pulse
PX4 has no single "motor mixer". The chain has four links:

1. **Controllers** output normalized torque on three axes and thrust.
2. **`control_allocator`** splits them across the actuators according to the `CA_*` geometry and publishes two topics: `actuator_motors` (0…1, −1…1 for reversible ones, NaN means "motor stopped") and `actuator_servos` (−1…+1). The math of the split is in the ctl-allocation module and is not repeated here.
3. **`mixer_module`** is a library inside every output driver. For each output it looks at the output's function, takes the value from the right source and converts −1…+1 into a number for the driver.
4. **The driver** (`pwm_out`, `dshot`, `px4io`, `uavcan`) passes the number to the MCU timer or onto the bus.

{{diagram:px4-outputs-pipeline|The allocator only knows "Motor 3" and "Servo 2"; which pin they end up on, with what limits and in which arming state, is decided by mixer_module inside the output driver.}}

Conversion to microseconds is `output_limit_calc_single()`:

- a NaN value → `DIS`;
- if the output's bit is set in `REV`, the value changes sign;
- the normal case: `µs = MIN + (v + 1) / 2 · (MAX − MIN)`, rounded (`lroundf`; in 1.18 already in the driver, `PWMOut.cpp`);
- **since 1.17**, if the function is Servo, Gimbal or Landing Gear Wheel and `CENTn` is set (800…2200): two lines, `v < 0` → `MIN + (v + 1) · (CENT − MIN)`, `v ≥ 0` → `CENT + v · (MAX − CENT)`.

For motors the allocator outputs 0…1, and `mixer_module` first stretches that to −1…+1 (`2·v − 1`), so 0 % thrust gives `MIN`, not `DIS`.

### Output functions
Each output gets one function: the `<prefix>_FUNCn` parameter. The numbers come from `output_functions.yaml`; a comment in the file forbids changing them, so they are the same in 1.15–1.17.

| Function | Number | Value source | Note |
|---|---|---|---|
| Disabled | 0 | — | no pulse at all |
| Constant Min / Constant Max | 1 / 2 | constant −1 / +1 | the output holds `MIN` or `MAX` |
| Motor 1…12 | 101…112 | `actuator_motors` | does not work in prearm |
| Servo 1…15 | 201…215 | `actuator_servos` | surfaces, then tilt servos; before 1.18 Servo 1…8 (201…208) |
| Peripheral via Actuator Set 1…6 | 301…306 | `MAV_CMD_DO_SET_ACTUATOR` | the PX4 "relay" |
| Landing Gear | 400 | the `landing_gear` topic | down −1, up +1 |
| Parachute | 401 | constant −1 | +1 on termination |
| RC Roll / Pitch / Throttle / Yaw / Flaps | 402…406 | `manual_control_setpoint` | RC channel passthrough |
| RC AUX 1…6 | 407…412 | `RC_MAP_AUX1…6` | AUX channel passthrough |
| Gimbal Roll / Pitch / Yaw | 420…422 | `gimbal_controls` | with `MNT_MODE_OUT` = 0 |
| Gripper | 430 | the `gripper` topic | release −1, grab +1 |
| Landing Gear Wheel | 440 | `landing_gear_wheel` | nose wheel |
| IC Engine Ignition / Throttle / Choke / Starter | 450…453 | internal combustion engine control | since 1.16 |
| Camera Trigger | 2000 | the `camera_trigger` driver | FMU pins only |
| Camera Capture | 2032 | input: camera feedback | FMU pins only |
| PPS Input | 2064 | PPS input from the GNSS | FMU pins only |
| RPM Input | 2070 | RPM sensor input | FMU pins only, since 1.16 |

The "Servo n" source is not a specific servo but the n-th actuator of type "servo" in the geometry: on a plane Servo 1 is the `CA_SV_CS0` surface; on a tiltrotor with four surfaces and two tilt servos, Servo 5 and 6 are the motor tilt (the allocator adds the surfaces first, then the tilts).

### Output parameters
The prefix depends on the board. On a board with an IO processor (Pixhawk 6X, 6C) the IO outputs are `PWM_MAIN_*` and the FMU outputs are `PWM_AUX_*`. On a board without IO and with its own firmware (Kakute H7, Pixhawk 6U) the FMU outputs are called `PWM_MAIN_*`, and there is no `PWM_AUX_*`. The exception is boards without IO that run the firmware of an "older sibling" with IO (the Pixhawk 6C Mini on fmu-v6c): there the FMU outputs stay `PWM_AUX_*`, even though the case says MAIN. Go by the tabs of the Actuators screen, not by the case. DroneCAN outputs are the separate `UAVCAN_EC_*` and `UAVCAN_SV_*` sets (module el-dronecan).

| Parameter | Default | Range | What it does |
|---|---|---|---|
| `PWM_AUX_FUNCn` | 0 | numbers from the function table | function of output n |
| `PWM_AUX_DISn` | 1000 | 800…2200 µs | value when disarmed and on kill |
| `PWM_AUX_MINn` | 1000 | 800…1400 µs | value at −1 |
| `PWM_AUX_MAXn` | 2000 | 1600…2200 µs | value at +1 |
| `PWM_AUX_CENTn` | −1 | −1, 800…2200 µs | servo center; −1 means a straight line from MIN to MAX. **New in 1.17**; on IO outputs (`PWM_MAIN_CENTn` on a board with IO) since 1.18 |
| `PWM_AUX_FAILn` | −1 | −1, 800…2200 µs | value on flight termination; −1 means by function |
| `PWM_AUX_REV` | 0 | bitmask | bit n−1 reverses the range of output n |
| `PWM_AUX_TIMn` | 400 | −8, −7, −6 (since 1.18), −5, −4, −3, −1, 50, 100, 200, 400, any > 0 | protocol of the timer group with index n |

`FAILn` = −1 means "by function": Constant Min → `MIN`, Constant Max and Parachute → `MAX`, Servo → value 0 (the midpoint between `MIN` and `MAX`, or `CENT`), everything else, motors included, → `DIS`. `TIMn` values: −8 BDShot150, −7 BDShot300, −6 BDShot600 (bidirectional, since 1.18), −5 DShot150, −4 DShot300, −3 DShot600, −1 OneShot, 50/100/200/400 PWM at that rate in hertz; any other positive number is a custom PWM rate. Changing `TIMn` requires a reboot. 1.15 also had −2 = DShot1200; 1.16 removed that value.

If `MIN` is set higher than `MAX`, the firmware silently swaps them: you cannot reverse a servo that way; that is what `REV` is for.

### What the firmware sets by itself
Not QGC but the driver (`PWMOut::update_params`, the same in `px4io`), at the moment an output's function changes from Disabled to Motor or Servo while the firmware is running. The first pass after boot is skipped: the automation leaves alone functions that an airframe file already wrote or that were saved before the reboot. The flip side: when you load a parameter file into fresh firmware, the functions also change "on the fly", and the driver may write its own numbers into motor `MIN`/`MAX` and servo `DIS` over the values from the file; the result depends on the order in which the parameters arrive. After loading, compare these three parameters with the file. What gets written:

- **Motor** → `MINn` = 1100, `MAXn` = 1900. `DISn` stays 1000.
- **Servo** → `DISn` = 1500. `MINn` and `MAXn` stay 1000 and 2000, `CENTn` −1. The group rate switches from 400 to 50 Hz only if no output in that group had a function before and `TIMn` was exactly 400.

Hence a common mistake: a servo added to a group that already had a motor stays at 400 Hz. An analog servo at 400 Hz heats up and buzzes.

### Timer groups, MAIN and AUX
Several outputs hang off one hardware timer: a shared counter and a shared period. That is why the protocol and rate are set per group, not per output, with one `TIMn` parameter. The group layout is hard-coded in `boards/<vendor>/<board>/src/timer_config.cpp`, and QGC draws the groups from that data. DShot is available only in groups whose timer has a DMA channel described in `timer_config.cpp`; for the others the DShot values are not shown in the `TIMn` list.

{{diagram:px4-outputs-timers-v6x|fmu-v6x has three FMU output groups, 4 + 2 + 2, and the first two can do DShot; three servos and a camera trigger do not fit into the remaining four outputs, so the third servo has to move to MAIN.}}

| | MAIN on a board with IO (`px4io`) | AUX, the FMU outputs (`pwm_out`, `dshot`) |
|---|---|---|
| Protocols | PWM 50…400 Hz, OneShot | PWM, OneShot, DShot150/300/600, since 1.18 BDShot150/300/600 |
| DShot, bidirectional DShot | no | yes, in groups with DMA |
| Camera Trigger / Capture, PPS, RPM | no | yes |
| `CENTn` (since 1.17) | since 1.18 | yes |
| Latency | higher: the value goes FMU → IO over UART | lower |
| If the FMU hangs while armed | after 0.5 s the IO outputs `FAILn` by itself (with `CBRK_FLIGHTTERM` = 0) | no backup: the FMU drives the outputs itself |

Where to connect ESCs on a Pixhawk with two rows of outputs: DShot only to AUX (on the Pixhawk 6X case that is "FMU PWM OUT", MAIN is "I/O PWM OUT"); PWM ESCs can go to MAIN too, but the documentation recommends AUX for its lower latency. Plane servos are often kept on MAIN: the DShot layout does not touch them there, but `CENTn` appeared there only in 1.18.

A camera trigger assigned to an output takes the whole timer: the other outputs of that group cannot be used for a motor, a servo or frame capture.

### DShot and ESC telemetry
| Parameter | Default | Meaning |
|---|---|---|
| `DSHOT_MIN` | 0.055 | minimum command when armed, fraction of full (in 1.15–1.16 the unit is labeled %) |
| `PWM_AUX_TIMn` = −6 / −7 / −8 | — | bidirectional DShot (BDShot600 / 300 / 150): eRPM over the signal wire, selected **per timer group** (since 1.18; in 1.16–1.17 the global `DSHOT_BIDIR_EN`), needs a reboot |
| `DSHOT_BIDIR_EDT` | 0 | Extended DShot Telemetry (since 1.18): ESC temperature, voltage and current arrive in the eRPM frames; reboot |
| `DSHOT_TEL_CFG` | 0 (Disabled) | UART port for ESC telemetry over a separate wire; port numbers are in `px4-hardware-peripherals` |
| `DSHOT_3D_ENABLE` | 0 | 3D mode: the range is split into two directions, `DSHOT_MIN` is set to 0 |
| `DSHOT_3D_DEAD_L` / `DSHOT_3D_DEAD_H` | 1000 / 1000 | 3D deadband in 0…1999 units |
| `DSHOT_MOT_POL1…12` | 14 | number of rotor magnets, per motor: eRPM → RPM conversion (before 1.18 a single `MOT_POLE_COUNT`; on upgrade its value is copied into all 12) |
| `CA_R_REV` | 0 | mask of reversible motors (bit 0 is Motor 1) |

What you need to know:

- In a DShot group the `MINn` / `MAXn` / `DISn` / `FAILn` parameters have no effect: the driver uses its own values 1…1999, "stop" = 0, minimum = `DSHOT_MIN` × 1999 (109 at 0.055).
- All DShot groups run at one speed. If two groups have different ones selected, the 1.18 driver prints "Mixed DShot frequencies across timers, using freq: …" and takes the speed of the last group (in 1.17, "Only supporting a single frequency" and it corrects the parameter).
- **Bidirectional DShot.** 1.15 does not have it at all, only UART telemetry (`DSHOT_TEL_CFG`). In 1.16–1.17 it was enabled by `DSHOT_BIDIR_EN`, and the STM32 code then kept DShot only on the timer with index 0 (AUX1–4 on fmu-v6x and fmu-v6c; motors 5–6 of a hexacopter got no signal). In 1.18 the protocol is chosen per group: `PWM_AUX_TIMn` = −6/−7/−8 for BDShot600/300/150. The STM32 driver triggers the groups one after another in a loop, each with its own DMA channel, and in each cycle reads the reply of one channel of the group, round-robin (`dshot.c`, `up_dshot_init`): RPM is updated for every motor, but less often the more outputs the group has. The "timer 0 only" limitation is gone; a group without DMA (`DMA{…}` in `timer_config.cpp`) still cannot do DShot. Whether a particular board and ESC work, check with `dshot status` on the bench (not tested on hardware).
- With `DSHOT_BIDIR_EDT` = 1 (1.18) bidirectional DShot carries temperature, voltage and current besides RPM (Extended DShot Telemetry, if the ESC supports it: Bluejay, AM32; stock BLHeli_S has neither bidirectional DShot nor EDT). Without EDT, RPM comes over the signal wire and the rest over UART telemetry.
- RPM is computed in integers: `RPM = eRPM / (DSHOT_MOT_POLn / 2)` (`DShot.cpp`, v1.18.0; before 1.18 the shared `MOT_POLE_COUNT`). With the wrong pole count the RPM in `esc_status` is off by exactly the ratio of pole pairs, and the dynamic notch lands on the wrong frequency.

What the protocols are and what eRPM means is in the f-esc-firmware module.

### Servos and control surfaces: `CA_SV_*`
The surfaces are described in the Geometry block of the same screen. Indices start at zero: `CA_SV_CS0_*` is the surface driven by the Servo 1 function.

| Parameter | Default | Values |
|---|---|---|
| `CA_SV_CS_COUNT` | 0 | 0…8 surfaces |
| `CA_SV_CSn_TYPE` | 0 | 1 Left Aileron, 2 Right Aileron, 3 Elevator, 4 Rudder, 5 Left Elevon, 6 Right Elevon, 7 Left V-Tail, 8 Right V-Tail, 9 Left Flap, 10 Right Flap, 11 Airbrake, 12 Custom, 13 Left A-tail, 14 Right A-tail, 15 Single Channel Aileron, 16 Steering Wheel, 17 Left Spoiler, 18 Right Spoiler |
| `CA_SV_CSn_TRQ_R` / `_TRQ_P` / `_TRQ_Y` | 0 | roll / pitch / yaw effectiveness; QGC fills them in by type |
| `CA_SV_CSn_TRIM` | 0 | −1…1: neutral offset. In 1.17 replaced by `CENTn` for PWM servos |
| `CA_SV_CSn_FLAP` | 0 | −1…1: deflection with flaps fully extended |
| `CA_SV_CSn_SPOIL` | 0 | −1…1: deflection with spoilers fully extended |
| `CA_SVn_SLEW` | 0 | 0…10 s for full travel of servo n; 0 means no limit |
| `CA_SV_TL_COUNT` | 0 | 0…4 tilt servos |
| `CA_SV_TLn_MINA` / `_MAXA` | 0 / 90 | −90…90°: tilt angle at the servo minimum and maximum; 0 is up |
| `CA_SV_TLn_TD` | 0 | 0 tilts toward the front, 90 toward the right |
| `CA_SV_TLn_CT` | 1 | 0 None, 1 Yaw, 2 Pitch, 3 Yaw and Pitch: whether the tilt is used for control |

A motor is bound to a tilt servo with `CA_ROTORn_TILT` (0 none, 1…4 Tilt 1…4).

**Deflection sign.** There is one definition, in the documentation (Control Surface Deflection Convention) and in the `module.yaml` comment: a positive command deflects a horizontal surface trailing edge up (ailerons, elevons, elevator), a vertical one to the right (rudder), a mixed one up/right (V-tail and A-tail). Flaps, spoilers and the airbrake work in one direction: 0 retracted, 1 full deflection. You match the servo mechanics to this rule with the `REV` bit, not with signs in the geometry.

**Coefficients.** `TRQ_*` is a column of the effectiveness matrix: what torque a positive deflection produces. Torques are in FRD axes: roll "+" is right wing down, pitch "+" is nose up, yaw "+" is nose right. The sign follows from the rule, the magnitude is 1/N, where N is the number of surfaces on the axis. For elevons B = [[−0.5, 0.5], [0.5, 0.5]], and the inverse gives the mix: left = −roll + pitch, right = +roll + pitch. Double the coefficients and the deflections halve: the numbers sit in a matrix that gets inverted.

**Neutral.** Before 1.17 the neutral offset was set by `CA_SV_CSn_TRIM`, in normalized units, before reversal and conversion to microseconds. 1.17 added `CENTn` in microseconds for PWM servos on FMU outputs. You cannot combine them: if at least one `PWM_MAIN_CENTn` or `PWM_AUX_CENTn` differs from −1, the firmware zeroes every nonzero `CA_SV_CSn_TRIM` and prints the warning "…TRIM is reset to 0 as PWM CENTER is used". The conversion formula from the documentation: `CENT = MIN + (MAX − MIN) / 2 · (1 + TRIM)`. On IO outputs `CENTn` appeared only in 1.18 (`px4io/module.yaml`); in 1.17 `TRIM` remains there.

Servo power is as in the bf-servos-pwm module: a separate BEC on the servo rail, common ground, and the flight controller's 5 V rail does not feed the servo. On a Pixhawk the positive rail of the output header is not powered from the power module: without a BEC the servo gets nothing.

### Disarmed, prearmed, armed, failsafe
| State | When | Motors | Servos and other functions |
|---|---|---|---|
| Disarmed | not armed, prearm off | `DIS` | `DIS` |
| Prearmed | `COM_PREARM_MODE` = 1 and the safety button pressed; = 2 always, 5 s after boot | `DIS` | working value |
| Armed | armed | working value | working value; NaN → `DIS` |
| Kill, lockdown | kill switch; waiting for the throw in throw launch | `DIS` | `DIS` |
| Termination | flight termination | `FAIL` (`DIS` by default) | `FAIL` (servo at the midpoint, parachute at `MAX`) |

On PWM and IO, for the first 0.5 s after arming each output ramps smoothly from `DIS` to the working value; DShot has no ramp. `COM_PREARM_MODE` defaults to 0: when disarmed the servo sits at `DIS`, the sticks do not move it, and the payload outputs stay silent too. On a plane you set 2 to check the control surfaces before takeoff. When and how termination is triggered, and how it differs from kill, is in the px4-safety-return module. `FAILn` is not a reaction to RC loss: on RC loss the outputs keep working, and the flight mode changes.

### Payload: what replaces relays
PX4 has no relay parameters like ArduPilot (`RELAYn_*`, module `ap-outputs`). Every payload is a function on an output.

| Task | Function | Controlled by | Setup |
|---|---|---|---|
| A drop, lights, power from a mission or a companion | Peripheral via Actuator Set 1…6 | `MAV_CMD_DO_SET_ACTUATOR` (187): param1…6 = −1…1, NaN means leave unchanged, param7 = 0 | until the first command the output sits at `DIS` |
| A switch on the transmitter | RC AUX 1…6 | the channel from `RC_MAP_AUXn` | on RC loss the output goes to `DIS` |
| Gripper | Gripper | `MAV_CMD_DO_GRIPPER` (211): param2 = 0 release, 1 grab | `PD_GRIPPER_TYPE` = 0 (Servo), `PD_GRIPPER_TO` = 1 s (in 1.15 3 s, and it needs `PD_GRIPPER_EN` = 1, removed in 1.16) |
| Landing gear | Landing Gear | the `RC_MAP_GEAR_SW` switch, takeoff and landing automation | up = `MAX`, down = `MIN` |
| Parachute | Parachute | flight termination | `MIN` in flight, `MAX` on termination |

An on/off logic output comes from PWM: `MIN` and `MAX` are the two states, and a switch or relay with a PWM input sits outside. In a mission, Peripheral outputs are the "Set actuator" item in QGC; PX4 does not wait for the action and goes straight to the next waypoint. Two limitations: when disarmed and without prearm the command is stored, but the output stays at `DIS`; the `payload_deliverer` gripper module is not built into every firmware: in 1.17.0 it is in the fmu-v5x, ARK FMUv6X and SITL builds, but px4/fmu-v6x and fmu-v6c do not have it (you enable it with your own build via `boardconfig`).

### Testing without arming: `actuator_test`
The syntax from the command's source:

- `actuator_test set -m <1…8> -v <value> [-t <seconds>]` for a motor; `-s <1…8>` for a servo; `-f <function number>` for any function.
- The value is −1…1; for a motor 0…1 (0 = `MIN`, not `DIS`). Without `-t` the command holds the output until you press Enter.
- `actuator_test iterate-motors` runs every motor in turn at 15 % for 0.4 s; `iterate-servos` deflects every servo to +0.3.

While a test is running the other outputs sit at `DIS`; the servo's trim is added to its value. The test has no effect when armed or on kill. The QGC sliders send `MAV_CMD_ACTUATOR_TEST` (310), and commander answers **DENIED** in two cases: the vehicle is armed; there is a safety button and it has not been pressed (`Commander.cpp`, `handleCommandActuatorTest`). In QGC this is the message "Actuator test command denied". The `COM_MOT_TEST_EN` test switch (before 1.18, default 1) is gone: the test is always allowed. The timeout of a single command over MAVLink is no more than 3 s. The console `actuator_test` publishes the command directly and bypasses these checks, so take the propellers off before you use it. Output state: `pwm_out status`, `dshot status`, `px4io status`.

### Place in the system

- **Takes in:** the effectiveness matrix from the allocator (`ctl-allocation`); the armed, prearmed, kill, termination flags from commander (`px4-safety-return`); the ESC protocol and eRPM (`f-esc-firmware`); the first pass over the Actuators screen (`px4-setup-scratch`); UART port numbers and enabling the DroneCAN outputs (`px4-hardware-peripherals`); the servo power layout (`bf-servos-pwm`).
- **Gives out:** pulses and DShot frames to the motors and servos; RPM in `esc_status` for the dynamic notch and the motor failure detector (`px4-control`); payload outputs for missions and the companion; `FAILn` values for flight termination (`px4-safety-return`).
- **If you get it wrong here:** a servo in a DShot group or at 400 Hz means a control surface failure in flight; a wrong `CA_SV_CSn_TRQ_*` sign or an extra `REV` bit means stabilization rocks the plane (`ctl-allocation`); a `DSHOT_MOT_POLn` that does not match the motor means the notch misses and the gyro sees vibration (`px4-control`); an unchecked parachute `FAILn` means termination will not deploy the canopy (`px4-safety-return`). Versions are in the table in `px4-intro`.

## practice
An exercise without hardware or a simulator. You need paper or an editor and a calculator; all answers follow from the theory tables, and you check them against the reference at the end.

### Step 1. Output plan from `timer_config.cpp`
The board is px4/fmu-v6x (Pixhawk 6X). Lines 59–77 of `boards/px4/fmu-v6x/src/timer_config.cpp` (v1.17.0; the file did not change in v1.18.0):
```
constexpr io_timers_t io_timers[MAX_IO_TIMERS] = {
	initIOTimer(Timer::Timer5, DMA{DMA::Index1}),
	initIOTimer(Timer::Timer4, DMA{DMA::Index1}),
	initIOTimer(Timer::Timer12),
	initIOTimer(Timer::Timer1),
	initIOTimer(Timer::Timer2),
};

constexpr timer_io_channels_t timer_io_channels[MAX_TIMER_IO_CHANNELS] = {
	initIOTimerChannel(io_timers, {Timer::Timer5, Timer::Channel4}, {GPIO::PortI, GPIO::Pin0}),
	initIOTimerChannel(io_timers, {Timer::Timer5, Timer::Channel3}, {GPIO::PortH, GPIO::Pin12}),
	initIOTimerChannel(io_timers, {Timer::Timer5, Timer::Channel2}, {GPIO::PortH, GPIO::Pin11}),
	initIOTimerChannel(io_timers, {Timer::Timer5, Timer::Channel1}, {GPIO::PortH, GPIO::Pin10}),
	initIOTimerChannel(io_timers, {Timer::Timer4, Timer::Channel2}, {GPIO::PortD, GPIO::Pin13}),
	initIOTimerChannel(io_timers, {Timer::Timer4, Timer::Channel3}, {GPIO::PortD, GPIO::Pin14}),
	initIOTimerChannel(io_timers, {Timer::Timer12, Timer::Channel1}, {GPIO::PortH, GPIO::Pin6}),
	initIOTimerChannel(io_timers, {Timer::Timer12, Timer::Channel2}, {GPIO::PortH, GPIO::Pin9}),
	initIOTimerChannelCapture(io_timers, {Timer::Timer1, Timer::Channel2}, {GPIO::PortE, GPIO::Pin11}),
};
```
How to read it. The order of lines in the second array is the output number: the first line is AUX1, the eighth AUX8, the ninth the CAP1 capture input. The order of lines in the first array is the timer index in the `PWM_AUX_TIMn` name. `DMA{…}` in a timer line means "DShot possible".

Task A. Make a table of the groups: timer, outputs, `TIMn` parameter, whether DShot is available. Then lay out: 4 DShot600 motors, 3 servos at 50 Hz, one camera trigger. Do not use the CAP1 input. The board has IO: outputs MAIN1–8 are available (groups MAIN1–2, MAIN3–4, MAIN5–8, PWM and OneShot only).

Task B. Find four conflicts in the plan (a teaching example, put together by hand):
```
PWM_AUX_TIM0   -3
PWM_AUX_TIM1   50
PWM_AUX_TIM2   -3
PWM_AUX_FUNC1  101
PWM_AUX_FUNC2  102
PWM_AUX_FUNC3  103
PWM_AUX_FUNC4  201
PWM_AUX_FUNC5  202
PWM_AUX_FUNC6  2000
PWM_AUX_FUNC7  104
PWM_AUX_FUNC8  203
```

### Step 2. Servo pulse
The elevator is Servo 2 on output MAIN2 of a plane (an IO output, `PWM_MAIN_CENT2` = −1, not set): `PWM_MAIN_MIN2` = 1050, `PWM_MAIN_MAX2` = 1900, `PWM_MAIN_DIS2` = 1500, `PWM_MAIN_FAIL2` = −1, `CA_SV_CS1_TRIM` = 0.08. The allocator outputs `v = clamp(TRIM + u, −1, 1)`, where u is the loop command.

A worked example, u = +0.40, `REV` bit cleared: v = 0.48; µs = 1050 + (0.48 + 1) / 2 · 850 = 1050 + 629 = **1679**. In the code's arithmetic the same thing is written as a = 850 / 2 = 425, b = 1050 + 425 = 1475, µs = 425 · 0.48 + 1475 = 1679.

Compute it yourself and write it down:

1. u = 0 (neutral), u = −1.0, u = +1.0, no reversal.
2. The same u = 0 and u = +0.40 with `PWM_MAIN_REV` = 2.
3. What is on the output when disarmed with `COM_PREARM_MODE` = 0, and with `COM_PREARM_MODE` = 2 and u = 0.
4. What is on the output on flight termination, and on kill.
5. The servo was moved to an FMU output (PX4 1.17). What must `PWM_AUX_CENTn` be to keep the same neutral, what happens to `CA_SV_CS1_TRIM`, and how many microseconds does u = +0.40 give?

### Step 3. Signs of `CA_SV_CSn_TRQ_*`
Derive the sign of each coefficient from the rule "a positive command moves the trailing edge up (a vertical surface to the right)" and the FRD axes. The reasoning for the left aileron: edge up → the left wing loses lift → the left wing goes down → that is a roll to the left, negative → `TRQ_R` < 0. Fill in the table for: the left and right elevon (roll and pitch), the elevator, the rudder, the left and right half of a V-tail (pitch and yaw). The magnitude is 1/N.

Then compare with the PX4 airframe files (the `ROMFS/px4fmu_common/init.d/airframes/` directory, v1.17.0). `3000_generic_wing`, lines 17–23:
```
param set-default CA_SV_CS_COUNT 2
param set-default CA_SV_CS0_TYPE 5
param set-default CA_SV_CS0_TRQ_P 0.5
param set-default CA_SV_CS0_TRQ_R -0.5
param set-default CA_SV_CS1_TYPE 6
param set-default CA_SV_CS1_TRQ_P 0.5
param set-default CA_SV_CS1_TRQ_R 0.5
```
`2100_standard_plane`, lines 16–24:
```
param set-default CA_SV_CS_COUNT 4
param set-default CA_SV_CS0_TYPE 1
param set-default CA_SV_CS0_TRQ_R -0.5
param set-default CA_SV_CS1_TRQ_R 0.5
param set-default CA_SV_CS1_TYPE 2
param set-default CA_SV_CS2_TRQ_P 1
param set-default CA_SV_CS2_TYPE 3
param set-default CA_SV_CS3_TRQ_Y 1
param set-default CA_SV_CS3_TYPE 4
```
`13100_generic_vtol_tiltrotor`, lines 36–41 (V-tail):
```
param set-default CA_SV_CS2_TYPE 7
param set-default CA_SV_CS2_TRQ_P 0.5
param set-default CA_SV_CS2_TRQ_Y 0.5
param set-default CA_SV_CS3_TYPE 8
param set-default CA_SV_CS3_TRQ_P 0.5
param set-default CA_SV_CS3_TRQ_Y -0.5
```

### Step 4. The `REV` mask and three errors
A parameter fragment of a flying wing on fmu-v6x (a teaching example, put together by hand). The servos are analog, rated for 50 Hz.
```
CA_AIRFRAME        1
CA_SV_CS_COUNT     2
CA_SV_CS0_TYPE     5
CA_SV_CS0_TRQ_R   -0.5
CA_SV_CS0_TRQ_P    0.5
CA_SV_CS1_TYPE     6
CA_SV_CS1_TRQ_R   -0.5
CA_SV_CS1_TRQ_P    0.5
PWM_AUX_TIM0      -3
PWM_AUX_TIM1       400
PWM_AUX_TIM2       50
PWM_AUX_FUNC1      101
PWM_AUX_FUNC5      201
PWM_AUX_FUNC6      202
PWM_AUX_FUNC7      2000
PWM_AUX_FUNC8      301
PWM_AUX_REV        48
PWM_AUX_DIS5       1500
PWM_AUX_DIS6       1500
PWM_AUX_FAIL5      -1
```
Do three things: decode `PWM_AUX_REV` = 48 into output numbers; write the mask for the case where outputs 2, 3 and 5 need reversing; find three configuration errors and name, for each, the rule from the theory that it breaks.

### Moving to real hardware
Only after all four steps check out. The propellers stay off until the end of the procedure.

1. Servos from a separate BEC on the output rail, ground common with the flight controller. The DShot ESC signal wire goes to AUX.
2. In QGC → Actuators assign the functions per your plan, reboot the board (`TIMn` change), and check in `pwm_out status` and `dshot status` that each group got its protocol.
3. With a slider or `actuator_test set -s 1 -v 0.3 -t 2` send a positive command to each surface: the edge should go up (the rudder to the right). If it goes the wrong way, fix it with the `REV` bit, not the `TRQ` sign.
4. End stops: lower `MAXn` and raise `MINn` until the servo stops buzzing at the extremes. Neutral is `CENTn` (FMU, since 1.17) or `TRIM`.
5. Motors: `actuator_test set -m 1 -v 0.1 -t 1` one at a time; order and direction as in px4-setup-scratch.

Hardware criteria: each output has the protocol from the plan; a positive command deflects each surface per the rule; at the extremes the servo does not bind (idle current does not rise); disarmed with `COM_PREARM_MODE` = 0 the surfaces sit at the `DIS` neutral.

Self-check: the lab is done when
- step 1: the table has three FMU groups 4 + 2 + 2 and the CAP1 group, with DShot marked for two; the plan has no group with two protocols, and all four conflicts are named in the "wrong" plan;
- step 2: all numbers match the reference within ±1 µs;
- step 3: the signs of all ten coefficients match the three airframe files;
- step 4: the mask is decoded into outputs 5 and 6, the reverse task gave 22, and exactly three errors are found with their rules.

The hardware criteria from the previous paragraph are not part of this self-check; they are for the bench.

**Reference for the self-check.**

| Step | Correct result | Typical mistake and its cause |
|---|---|---|
| 1A | Groups: Timer5, AUX1–4, `TIM0`, DShot; Timer4, AUX5–6, `TIM1`, DShot; Timer12, AUX7–8, `TIM2`, no DShot; Timer1, CAP1, `TIM3`. Plan: Motor 1–4 on AUX1–4 (`TIM0` = −3); Servo 1–2 on AUX5–6 (`TIM1` = 50); the trigger on AUX7, AUX8 empty; Servo 3 on MAIN1 (`PWM_MAIN_TIM0` = 50). The mirror layout also works: the trigger on AUX5, the servos on AUX7–8 and MAIN | All three servos and the trigger on AUX5–8: the trigger takes a whole group, leaving one two-output group for three servos |
| 1B | (1) Servo 1 on AUX4 in the DShot600 group; (2) `TIM2` = −3, but Timer12 has no DMA, so neither `dshot` nor `pwm_out` takes AUX7–8 and Motor 4 gets no signal; (3) the trigger on AUX6 in the same group as Servo 2; (4) Servo 3 on AUX8 in the same group as Motor 4 | Only (1) found: groups counted as four outputs each instead of from `timer_config.cpp` |
| 2.1 | u = 0 → 1509; u = −1.0 → v = −0.92 → 1084; u = +1.0 → v clamped to 1 → 1900 | 1475 at u = 0: the trim forgotten; 1934 at u = +1: the ±1 clamp forgotten |
| 2.2 | u = 0 → 1441; u = +0.40 → 1271 | 1509 at u = 0: reversal mirrors around (MIN + MAX)/2 = 1475, and the trim changes sign too |
| 2.3 | `COM_PREARM_MODE` = 0 → 1500 (`DIS`); = 2 → 1509 | 1500 in both cases: in prearm the servo already gets its working value |
| 2.4 | Termination: value 0 → 1475; kill → 1500 | 1509 on termination: the trim is not part of the default value; 1500 on termination: `DIS` is kill |
| 2.5 | `CENT` = 1050 + 425 · 1.08 = 1509; the firmware resets `CA_SV_CS1_TRIM` to 0; u = +0.40 → 1509 + 0.4 · 391 = 1665 | 1679: computed with a single line; with `CENT` the upper half of the travel is shorter |
| 3 | Left elevon: R −0.5, P +0.5; right: R +0.5, P +0.5. Elevator P +1. Rudder Y +1. Left V-tail: P +0.5, Y +0.5; right: P +0.5, Y −0.5 | The V-tail yaw sign swapped: for the left half "up" is also to the right, the force on the tail is to the left, and the nose goes right (+) |
| 4 | 48 = 32 + 16 → bits 5 and 4 → outputs 6 and 5. Outputs 2, 3, 5 → 2 + 4 + 16 = 22. Errors: `CA_SV_CS1_TRQ_R` = −0.5 on the right elevon (it must be +0.5; otherwise the roll and pitch rows are proportional and roll cannot be separated from pitch); `PWM_AUX_TIM1` = 400 with analog servos on AUX5–6; `PWM_AUX_FUNC8` = 301 in the camera trigger's group | 48 → outputs 4 and 5: bit n−1 is output n. `PWM_AUX_FAIL5` = −1 is not an error: it means "by function" |

## diagnostics
- **Symptom:** the servo heats up, buzzes or twitches right after the function is assigned.
  - Possible cause: the group stayed at 400 Hz (it already had a function) or is set to DShot.
  - What to do: the group's `PWM_AUX_TIMn` = 50, reboot; put the motor and the servo in different groups.
- **Symptom:** after enabling bidirectional DShot, motors 5 and 6 are silent, or there is no RPM in `esc_status`.
  - Possible cause: in 1.18 BDShot is selected for only one group (every motor group needs `PWM_AUX_TIMn` = −6…−8); in 1.16–1.17 bidirectional worked only on the timer with index 0 (the first four FMU outputs on H7); 1.15 does not have it; the group has no DMA; the ESC does not support it.
  - What you see in the log: `esc_status.esc_rpm` = 0 while spinning, `dshot status` shows BDShot not on every group.
  - What to do: in 1.18, −6/−7/−8 in the `TIMn` of every motor group, reboot; in 1.16–1.17, motors on the first four FMU outputs, and for a hexa or an octo, UART telemetry (`DSHOT_TEL_CFG`); check the firmware version against the table in px4-intro.
- **Symptom:** QGC says "command denied" on a motor slider.
  - Possible cause: the vehicle is armed; there is a safety button and it has not been pressed; in 1.17 and earlier also `COM_MOT_TEST_EN` = 0 (1.18 has no such parameter).
  - What to do: disarm, press safety (or `CBRK_IO_SAFETY` = 22027 on a board without a button); from the console, `actuator_test set -m 1 -v 0.1 -t 1`.
- **Symptom:** on the ground the control surfaces do not respond to the sticks.
  - Possible cause: `COM_PREARM_MODE` = 0: when disarmed the output sits at `DIS`.
  - What to do: `COM_PREARM_MODE` = 2 (or 1 with a safety button); test with the sliders.
- **Symptom:** in Stabilized the plane rocks more than in Manual, or rolls when you pull back on the stick.
  - Possible cause: a surface moves against the sign rule, and it was fixed with the `TRQ` sign instead of `REV`; the elevons have the `TRQ_R` sign swapped.
  - What to do: slider up → edge up on every surface; signs as in step 3.
- **Symptom:** after updating to 1.17 a surface trim disappeared, and QGC shows a warning about `TRIM is reset`.
  - Possible cause: at least one `CENTn` is set, so the firmware zeroed every `CA_SV_CSn_TRIM`.
  - What to do: move the trim into `CENTn` with the formula `MIN + (MAX − MIN)/2 · (1 + TRIM)` for each servo on the FMU.
- **Symptom:** a DShot ESC is connected to MAIN on a Pixhawk with IO, and the motors do not initialize.
  - Possible cause: the IO can do only PWM and OneShot.
  - What to do: move the ESC to AUX (FMU PWM OUT) and reassign the functions.
- **Symptom:** the RPM in `esc_status` does not agree with the KV calculation, and the dynamic notch does not help.
  - Possible cause: this motor's `DSHOT_MOT_POLn` (before 1.18, `MOT_POLE_COUNT`) does not equal the number of magnets.
  - What to do: count the magnets on the bell; 12 poles instead of 14 give an error of 7/6.
- **Symptom:** a Peripheral via Actuator Set output does not respond to the command.
  - Possible cause: param7 (the index) is not 0; the value is in microseconds instead of −1…1; the output is in a group taken by the trigger or DShot.
  - What to do: param1…6 within −1…1, param7 = 0; check the timer group.

## checklist
- The board's timer groups are written down from `timer_config.cpp` or the Actuators screen before soldering.
- Each group has one protocol: DShot motors separately, 50 Hz servos separately, the camera trigger in its own group.
- DShot and bidirectional DShot only on FMU outputs; in 1.18 BDShot (−6/−7/−8) is set on every motor group (in 1.16–1.17 with `DSHOT_BIDIR_EN` = 1, motors only on the first four).
- After assigning Servo you checked: `DISn` = 1500, the group's `TIMn` = 50.
- Every surface moves per the sign rule; the mechanics are fixed with the `REV` bit.
- `MINn` / `MAXn` are matched to the end stops, the neutral is `CENTn` or `TRIM`, but not both.
- `FAILn` is checked for the parachute and the control surfaces; `COM_PREARM_MODE` is a deliberate choice.
- Each motor's `DSHOT_MOT_POLn` equals its number of magnets.
- The servos are powered from a separate BEC, with common ground.

## references
- PX4 Guide v1.17: Actuator Configuration and Testing | https://docs.px4.io/v1.17/en/config/actuators | primary | A
- PX4 Guide v1.17: DShot ESCs | https://docs.px4.io/v1.17/en/peripherals/dshot | primary | A
- PX4 Guide v1.17: Generic Actuator Control | https://docs.px4.io/v1.17/en/payloads/generic_actuator_control | primary | A
- PX4 Guide v1.17: Arm, Disarm, Prearm Configuration | https://docs.px4.io/v1.17/en/advanced_config/prearm_arm_disarm | primary | A
- PX4 Guide v1.17: Cameras Connected to Flight Controller Outputs | https://docs.px4.io/v1.17/en/camera/fc_connected_camera | primary | A
- PX4 Guide v1.17: PWM Servos and ESCs (servo rail power) | https://docs.px4.io/v1.17/en/peripherals/pwm_escs_and_servo | primary | A
- PX4-Autopilot v1.18.0: src/lib/mixer_module/output_functions.yaml | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/lib/mixer_module/output_functions.yaml | primary | A
- PX4-Autopilot v1.18.0: src/lib/mixer_module/mixer_module.cpp | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/lib/mixer_module/mixer_module.cpp | primary | A
- PX4-Autopilot v1.18.0: src/drivers/pwm_out/PWMOut.cpp | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/drivers/pwm_out/PWMOut.cpp | primary | A
- PX4-Autopilot v1.18.0: boards/px4/fmu-v6x/src/timer_config.cpp | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/boards/px4/fmu-v6x/src/timer_config.cpp | primary | A
- PX4-Autopilot v1.17.0: src/modules/control_allocator/module.yaml | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/control_allocator/module.yaml | primary | A

## notes
The 1.17 documentation lags behind the code in places: the Actuators page says the function list is "correct for v1.15" (no IC Engine or RPM Input) and lists 12 of the 18 surface types, and the "do not use `CA_SV_CSn_TRIM` for PWM servos" note is in the allocator's `module.yaml` but not in the parameter reference. Where they disagree, the v1.17.0 tag source wins.
