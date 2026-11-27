---
id: inav-mixer-vtol
title: "The INAV mixer in full: mmix/smix, outputs and timers, flaperons, gimbals, mixer profiles and VTOL"
level: L2
readingTime: 75 min
firmware: INAV 9.1 (checked against 9.1.0)
status: published
added: 2026-11-18
tags:
  - INAV
  - mixer
  - mmix
  - smix
  - servos
  - timers
  - VTOL
  - gimbal
related:
  - inav-wing
  - inav-setup-wing
  - inav-setup-scratch
  - inav-ipf
  - bf-servos-pwm
  - payload-gimbal
  - ctl-allocation
  - ap-quadplane
next:
  - inav-ipf
source: content/inav/inav-mixer-vtol.md
source_hash: 0c7150d10285
---

## summary
The mixer is the last software layer between the controllers and the hardware: it turns three stabilization commands and throttle into numbers for every motor and every servo, and the microcontroller timers turn those into pulses on the pads. This module goes through all of it from the INAV 9.1.0 source: the platform types, the `mmix` lines (including throttle values of −1 and −1.05…−2), the `smix` rules and all 61 input sources, the `servo` command, the `servo_*` settings, the assignment of outputs to timers and `timer_output_mode`, the tables for elevons, a V-tail, flaperons and differential, gimbals and the head tracker, the two mixer profiles and the VTOL transition. The practice needs no hardware and no simulator: derive the `mmix` of a hex from the geometry and compare it with the preset, calculate servo pulses with the `servos.c` formula, lay out the outputs of a real MATEKF405TE board for 4 and 5 DShot motors and find three errors in a 4+1 VTOL config.

## theory
### Where the mixer sits
{{diagram:inav-mixer-signal-path|The motors get only the three PID commands and throttle; the servos — any of the 61 sources. After that the timer decides everything: one timer — one function.}}

The PID controllers output `axisPID[ROLL/PITCH/YAW]` in the range ±500. The motor mixer (`mixTable()`, `mixer.c`) adds them to throttle using the `mmix` table. The servo mixer (`servoMixer()`, `servos.c`) computes the servos from the `smix` rules and the `servo` parameters. The firmware has no ready-made tables: the presets “Quad X”, “Flying Wing” and the others live in the Configurator (`js/model.js`) and on loading simply write the `mmix`/`smix` lines. The theory of control allocation is in ctl-allocation; this is how it is written down by hand.

### Platform type
`platform_type` is stored in the mixer profile and enables a set of flags (`mixerUpdateStateFlags()`):

| Value | What it enables | Consequence |
|---|---|---|
| `MULTIROTOR` (default) | MULTIROTOR, ALTITUDE_CONTROL | multirotor PIDs and navigation, AIRMODE, HEADFREE |
| `TRICOPTER` | the same | plus `tri_unarmed_servo`: the tail servo works even when disarmed |
| `AIRPLANE` | AIRPLANE, FIXED_WING, ALTITUDE_CONTROL, MOVE_FORWARD_ONLY | fixed-wing PIDs, MANUAL, autolaunch, autotrim, autotune, FLAPERON with `has_flaps` |
| `ROVER`, `BOAT` | FIXED_WING, MOVE_FORWARD_ONLY, no ALTITUDE_CONTROL | no ALTHOLD and no AIRMODE, a throttle ceiling of 1850 instead of 2000 |
| `HELICOPTER` | the same flags as MULTIROTOR | there is no separate swashplate logic in `mixer.c` |

The documentation (`docs/Mixer.md`, the description of the setting) names MULTIROTOR, AIRPLANE and TRICOPTER as implemented. The details of the airplane platform are in inav-wing.

### `mmix`: motors
The syntax: `mmix <n> <throttle> <roll> <pitch> <yaw>`, `n` = 0…11 (`MAX_SUPPORTED_MOTORS` 12), and `mmix reset` erases the table. The formula (`mixer.c:537–540, 628`):

```text
motor[n] = pitch·P + roll·R − yaw·Y + constrain(throttle command · throttle)
```

P, R, Y are `axisPID`, ±500. The signs of the weights per `docs/Mixer.md`: a positive `roll` — the motor speeds up on a roll to the right (so it is on the left); a positive `pitch` — it speeds up when the nose goes down (it is at the rear); a positive `yaw` — it speeds up on a clockwise turn, that is, its prop spins counterclockwise. The minus before yaw in the formula is not a mistake: `rcCommand[YAW]` is the stick with the opposite sign (`fc_core.c:404`). The setting `motor_direction_inverted = ON` flips the sign of the whole yaw column at once (props-out), and the table does not have to be touched.

A line from the geometry: a motor on an arm at azimuth φ clockwise from the nose, all arms of the same length — `roll = −sin φ`, `pitch = −cos φ`. For Quad X (φ = 45°, 135°, 225°, 315°) that gives ±0.707; the preset scales the table to ±1 — the PIDs compensate for the common factor of an axis, and what matters is the ratios between the motors.

```text
mmix 0  1.000 -1.000  1.000 -1.000   # rear right, prop clockwise
mmix 1  1.000 -1.000 -1.000  1.000   # front right
mmix 2  1.000  1.000  1.000  1.000   # rear left
mmix 3  1.000  1.000 -1.000 -1.000   # front left
```

The check: throttle 1500, a roll request of +100 → the right motors at 1400, the left at 1600, and the aircraft rolls right.

The `throttle` column is not only a throttle scale:

| `throttle` | Behavior (`mixer.c:636–644`) |
|---|---|
| 0 < t ≤ 1 | an ordinary motor |
| 0 | an empty line: `mmix`, `diff` and the motor count stop at the first such line |
| −1.05 < t < 0 (written as −1) | the motor is stopped but the line is occupied — a “placeholder” so that the following lines are not lost |
| −2.0 ≤ t ≤ −1.05 | stopped; with MIXER TRANSITION active it spins at `−t × 1000` µs regardless of the stick (−1.2 → 1200, which is 20 % of the range). Does not work with `REVERSIBLE_MOTORS`. Below −2.0 the motor is stopped and never spins (`mixer.c`) |

The number of motors is counted over both profiles: a motor “exists” if its `throttle` ≠ 0 in at least one of them (`mixer.c:117–137`).

### `smix`: servo rules
The syntax: `smix <rule> <servo> <input> <weight> <speed> <lc>`. `rule` 0…35 (`MAX_SERVO_RULES`), `servo` 0…17, `weight` −1000…1000 %, `speed` 0…255, `lc` — the number of a logic condition −1…63 (−1 — the rule always works; a false condition zeroes the input of the rule, see inav-ipf). Rules for the same servo are summed. The table is read up to the first rule with weight 0. `speed` limits the rate of change of the input: `speed × 10` units per second, 0 — no limit; with weight 100 and standard endpoints that is the “10 µs/s per unit” from the documentation.

The input sources (`inputSource_e`, `servos.h:26–89`) — 9.1.0 has 61 of them, id 0…60:

| id | Source | Value |
|---|---|---|
| 0, 1, 2 | stabilized roll, pitch, yaw | `axisPID`, ±500; in MANUAL — the sticks |
| 3 | stabilized throttle | the throttle command − 1500; −500 when disarmed |
| 4–7 | RC roll, pitch, yaw, throttle | the channel − 1500, bypassing stabilization |
| 8–11, 15–22, 42–43 | RC CH5–CH8, CH9–CH16, CH17–CH18 | the channel − 1500 |
| 44–59 | RC CH19–CH34 | only boards with > 512 KB of flash (`USE_34CHANNELS`) |
| 12, 13 | GIMBAL PITCH, GIMBAL ROLL | pitch ±90° and roll ±180° → ±500; only with the CAMSTAB mode, otherwise 0 |
| 14 | FEATURE FLAPS | `flaperon_throw_offset` with the FLAPERON mode, otherwise 0 |
| 23, 24 | roll “+” and “−” | the positive and negative halves of input 0 |
| 25, 26 / 27, 28 | the same for pitch / yaw | the halves of inputs 1 and 2 |
| 29 | MAX (“Fixed Value (µs)” in the Configurator) | always 500 |
| 30–37 | GVAR 0–7 | IPF global variables, ±1000 |
| 38 | MIXER TRANSITION | 500 while the transition is active, otherwise 0 |
| 39, 40, 41 | head tracker pan, tilt, roll | PWM − 1500; 0 without a device and in GIMBAL CENTER |
| 60 | MIXER_SWITCH_HELPER | internal, appeared in 9.x: the firmware creates such rules itself on a profile switch so that the `speed` limiter finishes smoothly |

The sign of input 2 is opposite to the yaw stick — for the same reason as in `mmix`.

### `servo` and the servo settings
`servo <n> <min> <max> <mid> <rate>`: `min`/`max` 500…2500 µs (default 1000/2000), `mid` between them (1500), `rate` −125…125 % (100). The formula (`servos.c:443–497`, the division is integer, the fractional part is dropped):

```text
sum = Σ trunc(input · weight / 100)          # all the rules of this servo
s   = trunc(sum · rate / 100)
s   = trunc(s · (max − mid) / 500)  if s > 0,  otherwise  trunc(s · (mid − min) / 500)
out = constrain(mid + s, min, max)
```

A sum of ±500 takes the servo exactly to `max`/`min` — the endpoints scale the travel, they do not clip it. Clipping starts when the sum of the rules goes beyond ±500 (the sum of the weights is more than 100). Reversing: a negative `rate` reverses the whole servo, the sign of a weight — one axis (the rule for choosing is in inav-setup-wing). A servo without rules in the current profile sits at `mid`.

After the formula the `servo_lpf_hz` filter is applied and then the `min`/`max` limit once more. The outputs are physically assigned consecutively from the lowest to the highest servo number used across both profiles (`servos.c:147–172, 294–300`): rules for servos 1, 2 and 6 take six outputs, three of them wasted. Servo power (a separate BEC, stall current, common ground) is in bf-servos-pwm and is not repeated here.

### Outputs and timers
An S output on the board is a channel of a hardware timer. A timer has one counter and one period for all its channels: a servo timer is set to a period of `1 MHz / servo_pwm_rate` (`pwm_output.c:738`), a motor timer — to the DShot bit rate or the OneShot frame rate. So a motor and a servo on the same timer are incompatible, and INAV assigns functions to whole timers (`pwm_mapping.c:273–369`):

1. In `target.c` every output is tagged: `TIM_USE_OUTPUT_AUTO` (motor or servo), `TIM_USE_LED`, `TIM_USE_BEEPER`.
2. `timer_output_mode <timer> <AUTO|MOTORS|SERVOS|LED>` forces the function of all outputs of a timer. The number is the index in the timer table. On F4, F7 and AT32 it is the TIM number minus 1; on H7 that holds only up to TIM8, after which TIM12 → 8, TIM13 → 9, TIM14 → 10, TIM15 → 11, TIM16 → 12, TIM17 → 13 (`timer_stm32h7xx.c`). It is safer to look at the Mixer tab: “Timer N” = index + 1. The CLI hint lists only three values, but the parser accepts `LED` (`cli.c:3194`). What happens to the other outputs of a timer with the LED strip enabled is in `inav-led-pinio-beeper`.
3. In AUTO the firmware goes down the table from the top and takes whole timers for motors until there are enough motor outputs for the mixer. The remaining AUTO timers become servo timers.
4. The motors of the mixer take the motor outputs in order, the servos — the servo outputs in order.
5. Not enough — arming is blocked by the `PWMOUT` flag, and `status` prints `PWM output init error` with the reason, for example `Not enough servo outputs/timers`.

The consequence: a fifth motor on a four-channel timer eats all four outputs. The `resource` command in INAV only shows the resources in use; you cannot move a function to another pin as in Betaflight — only `timer_output_mode` or your own build with an edited `target.c`. There is no `output_mode` setting in 9.1.0 — neither the setting itself nor a value table in `settings.yaml`: the modes `AUTO`, `MOTORS`, `SERVOS`, `LED` are defined by an enum in `flight/mixer.h` and are changed only with the `timer_output_mode` command.

On the Mixer tab the table “Output Groups (Timers)” colors the outputs of one timer with one color and labels them `S5 (Timer 2)`; the row under it shows the assigned function. The Outputs tab shows the current values of the motors and servos and edits `min`/`mid`/`max`/`rate`. Until `feature PWM_OUTPUT_ENABLE` (“Enable motor and servo output”) is enabled, there are no pulses on the pads.

`servo_protocol = SBUS` outputs the servos not to the pads but to a UART with the `SERVO_SERIAL` function (4194304), up to 18 channels; `SBUS_PWM` — both there and to the pads. `docs/ESC and servo outputs.md` warns: on some boards there are no servo outputs at all in a multirotor configuration.

### Fixed wing: elevons, V-tail, flaperons, differential
The tables from the Configurator 9.1.0 presets (the rules are numbered consecutively from 0, `speed` 0, `lc` −1):

| Layout | Servo: input × weight |
|---|---|
| Flying Wing | 1: roll 50, pitch 50; 2: roll −50, pitch 50 |
| Airplane | 1: pitch 100; 2: roll 100; 3: roll 100; 4: yaw 100 |
| V-tail | 1 and 2: roll 100; 3: pitch 50, yaw −50; 4: pitch −50, yaw −50 |

An elevon with weights 50 + 50 reaches its endpoint only with full commands on both axes at once. Flaperons: `set has_flaps = ON` makes the FLAPERON mode (id 34) available, and input 14 outputs `flaperon_throw_offset` (200 µs, 50…450). The lines `smix 4 2 14 100 20 -1` and `smix 5 3 14 -100 20 -1` lower both ailerons; `speed 20` stretches the deployment over 200 / (20 × 10) = 1.0 s. The firmware has no separate “flap modes” — positions are made with a radio channel (inputs 8–11) or with several rules with logic conditions. Aileron differential is built from the halves 23/24 instead of input 0: weight 100 on the half that raises the aileron and 60 on the one that lowers it; on the mirrored servo the weights are swapped. Which half raises depends on how the servo is mounted; check on the bench.

### Gimbals and the head tracker
**A servo gimbal** is two rules with inputs 12 and 13. They are non-zero only with the CAMSTAB mode (id 8) active. Input 12 gives 500 / 90 = 5.56 units per degree of pitch, input 13 — 2.78 units per degree of roll. For a servo with 11.11 µs/° a 1 : 1 compensation requires a weight of 200 in pitch and 400 in roll; the sign — from a tilt test.

**A serial gimbal** (since INAV 8, the Walksnail GM protocol): the GIMBAL port function (67108864). The radio channels are set by `gimbal_pan_channel`, `gimbal_tilt_channel`, `gimbal_roll_channel` (0 — none), the sensitivity by `gimbal_sensitivity` (−16…15), the center trim by `gimbal_pan_trim`, `gimbal_tilt_trim`, `gimbal_roll_trim` (±500). The modes: GIMBAL LEVEL TILT (65), GIMBAL LEVEL ROLL (66), GIMBAL CENTER (67), GIMBAL HEADTRACKER (68). The mixer does not control a serial gimbal.

**Head tracker**: `headtracker_type` = NONE / SERIAL / MSP, the GIMBAL_HEADTRACKER port function (134217728), the ratios `headtracker_pan_ratio`, `headtracker_tilt_ratio`, `headtracker_roll_ratio` (0…5, default 1). `gimbal_serial_single_uart = ON` shares one UART: TX — to the gimbal, RX — to the tracker. An ordinary servo turret is moved by the tracker through inputs 39–41. The choice and mechanics of gimbals are in payload-gimbal.

### Mixer profiles
There are two profiles (`MAX_MIXER_PROFILE_COUNT`); on the F411 and other boards with up to 512 KB of flash, except F7, — one, and VTOL is not available there (`target/common.h:206–222`). The command `mixer_profile 1|2` selects the profile for editing and saves the selection.

| Stored in the mixer profile | Common to both |
|---|---|
| `platform_type`, `motor_direction_inverted`, `has_flaps`, `motorstop_on_low`, `model_preview_type` | `timer_output_mode`, the motor and servo protocols and rates |
| `mixer_control_profile_linking`, `mixer_automated_switch`, `mixer_switch_trans_timer`, `tailsitter_orientation_offset`, `transition_pid_mmix_multiplier_*` | `servo` (min, max, mid, rate) |
| the `mmix` and `smix` tables | board alignment, ports, modes |

Without the `MIXER PROFILE 2` mode a profile change requires a reboot. With it (id 62) the profile changes in flight: the mode is active — profile 2, otherwise profile 1. `mixer_control_profile_linking = ON` makes the control profile follow the mixer profile (before 9.0 the setting was called `mixer_pid_profile_linking`); the documentation recommends ON in both profiles. With OFF the airplane will fly on the multirotor PIDs.

### VTOL: the transition and its limitations
INAV supports three layouts (`docs/VTOL.md`): a separate pusher motor (“4+1” — the simplest to set up), tilting motors (tilt-rotor) and a tailsitter (`tailsitter_orientation_offset = ON` in the hover profile: a 90° pitch rotation of the orientation, and +45° to the ANGLE target in the transition). The comparison with ArduPilot, where VTOL is one parameter set `Q_ENABLE`, `Q_FRAME_CLASS`, `Q_TRANSITION_MS`, `Q_ASSIST_SPEED`, `Q_TILT_TYPE`, is in ap-quadplane.

The `MIXER TRANSITION` mode (id 63) enables “transition mixing” in the current profile: input 38 becomes 500, the motors with a `throttle` of −1.05…−2 spin up, and the PID commands in `mmix` are multiplied by `transition_pid_mmix_multiplier_roll/pitch/yaw` / 1000. The typical three-position switch from the documentation: airplane — multirotor with transition — multirotor.

What was verified against `mixer_profile.c`:
- The transition is **time-based, not airspeed-based**: an airspeed sensor takes no part in the transition logic.
- A profile change is rejected while sensor calibration is in progress, the CLI is open or any navigation mode is active, including ALTHOLD (`navState` is not IDLE).
- Transition mixing works only without navigation or in ALTHOLD; in POSHOLD, RTH and a mission input 38 is 0.
- In failsafe the switches are not read; only the automated transition is left.

The automated transition: `mixer_automated_switch = ON` in the multirotor profile — on RTH, if home is farther than 3 × `nav_fw_loiter_radius` (225 m at the default 7500 cm), the aircraft holds altitude, enables transition mixing for `mixer_switch_trans_timer` × 0.1 s and switches to the airplane profile. `ON` in the airplane profile — before the RTH landing it switches back; the timer is taken from the current profile. A mandatory condition — the `MIXER PROFILE 2` mode is assigned to a channel.

The requirements of the documentation: `airmode_type` is not `THROTTLE_THRESHOLD`; a compass for navigation in the multirotor profile; each profile is first flown separately; bench checks without props; the feature is called experimental. Switching to the airplane profile without airspeed is an immediate stall.

### A worked example: 4+1
A quadcopter X plus a pusher motor, an airplane tail. Profile 1 is the airplane, profile 2 is the hover:

```text
mixer_profile 1                        mixer_profile 2
set platform_type = AIRPLANE           set platform_type = MULTIROTOR
set mixer_control_profile_linking = ON set mixer_control_profile_linking = ON
set mixer_automated_switch = ON        set mixer_automated_switch = ON
                                       set mixer_switch_trans_timer = 40
mmix 0 -1.000 0 0 0                    mmix 0 1.000 -1.000  1.000 -1.000
mmix 1 -1.000 0 0 0                    mmix 1 1.000 -1.000 -1.000  1.000
mmix 2 -1.000 0 0 0                    mmix 2 1.000  1.000  1.000  1.000
mmix 3 -1.000 0 0 0                    mmix 3 1.000  1.000 -1.000 -1.000
mmix 4  1.000 0 0 0                    mmix 4 -1.300 0 0 0
smix 0 1 1 100 0 -1                    smix 0 1 1 50 0 -1
smix 1 2 0 100 0 -1                    smix 1 2 0 50 0 -1
smix 2 3 0 100 0 -1                    smix 2 3 0 50 0 -1
smix 3 4 2 100 0 -1
```

{{diagram:inav-vtol-transition-timeline|In the hover profile the pusher motor is stopped, in the transition it gives a fixed 1300 µs for 4.0 s, and only after the profile change does it follow the stick.}}

In the hover motors 0–3 stabilize and the pusher is stopped; the control surfaces work at half weight — the documentation advises keeping them so that you can recover from a dive at speed. In the transition the pusher gives −(−1.3) × 1000 = 1300 µs. After the profile change motors 0–3 are stopped with the −1 placeholders, the pusher follows the throttle, and servo 4 (the rudder) gets a rule. For a tilt-rotor, instead of the fifth motor there is a tilt servo: in the airplane profile `smix … 5 29 -100 0 -1` (1000 µs, forward), in the multirotor profile `smix … 5 29 100 0 -1` (2000 µs, up) plus `smix … 5 38 -100 150 -1`: in the transition the sum is 500 − 500 = 0, and the servo gets to 1500 µs (45°) in 500 / 1500 = 0.33 s.

### Reference table
| Setting | Default | Range | Where |
|---|---|---|---|
| `platform_type` | MULTIROTOR | 6 values | mixer profile |
| `has_flaps` | OFF | OFF/ON | mixer profile |
| `motorstop_on_low` | ON | OFF/ON | mixer profile |
| `motor_direction_inverted` | OFF | OFF/ON | mixer profile |
| `mixer_control_profile_linking` (`mixer_pid_profile_linking` before 9.0) | OFF | OFF/ON | mixer profile |
| `mixer_automated_switch` | OFF | OFF/ON | mixer profile |
| `mixer_switch_trans_timer` | 0 | 0…200, × 0.1 s | mixer profile |
| `tailsitter_orientation_offset` | OFF | OFF/ON | mixer profile |
| `transition_pid_mmix_multiplier_roll/pitch/yaw` (new in 9.x) | 1000 | −5000…5000, 1000 = ×1 | mixer profile |
| `servo_protocol` | PWM | PWM, SBUS, SBUS_PWM | master |
| `servo_pwm_rate` | 50 Hz | 50…498 | master; above 50 — digital servos only |
| `servo_center_pulse` | 1500 µs | 1000…2000 | master |
| `servo_lpf_hz` | 20 Hz | 0…400, 0 — off | master |
| `flaperon_throw_offset` | 200 µs | 50…450 | master |
| `tri_unarmed_servo` | ON | OFF/ON | master |
| `motor_pwm_protocol` | ONESHOT125 | STANDARD … DSHOT600 | master |
| `throttle_idle` | 8 % | 0…30 | battery profile; idle at 1080 µs |

There are no settings with the prefix `mixer_vtol_` in 9.1.0: the whole of VTOL is the rows of the table above.

### Place in the system
- **Receives:** `axisPID` from the controllers (their scales and tuning are in `inav-mc-tuning`; ctl-allocation explains why the table is the way it is), the receiver channels and the modes CAMSTAB, FLAPERON, MIXER PROFILE 2 and MIXER TRANSITION, GVARs and conditions from inav-ipf, the timer map of the board from `target.c`.
- **Provides:** motor values to the ESC drivers and pulses to the servos of control surfaces, tilt mechanisms and the gimbal (payload-gimbal); on a profile change — the navigation platform type and the control profile number (inav-wing, inav-setup-scratch).
- **If you get it wrong here:** a wrong sign in `mmix` looks like a flip on takeoff, a servo on a motor timer — like the `PWMOUT` arming block, disabled profile linking — like an airplane oscillating on copter PIDs, a zero transition timer — like a stall on RTH.

## practice
All four steps are solved on paper or in twenty lines of Python; the answers are fully determined by the formulas and tables of this module. The reference numbers were produced by a script that repeats the integer arithmetic of `servos.c` and the algorithm of `pwm_mapping.c` of the 9.1.0 tree.

### Step 1. The `mmix` of a hex from the geometry
Hex X: six arms of the same length, azimuths clockwise from the nose and the prop rotation (top view):

| Motor | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| Azimuth | 150° | 30° | 210° | 330° | 90° | 270° |
| Prop | CCW | CCW | CW | CW | CW | CCW |

Write six `mmix` lines (`roll = −sin φ`, `pitch = −cos φ`, three decimal places, no scaling). Then calculate the motor values at throttle 1500, `axisPID` roll +100, pitch −60, yaw 0: `motor = 1500 + trunc(pitch·P + roll·R)`.

### Step 2. Servo pulses with differential and flaperons
The configuration:

```text
servo 3 1100 1900 1520 100
servo 4 1000 2000 1480 -100
smix 0 3 23 100 0 -1
smix 1 3 24 60 0 -1
smix 2 3 14 100 20 -1
smix 3 4 23 60 0 -1
smix 4 4 24 100 0 -1
smix 5 4 14 -100 20 -1
```

`flaperon_throw_offset = 200`. Calculate the steady-state pulses of servos 3 and 4 for five cases: A — roll +300, FLAPERON off; B — roll −300, off; C — roll +300, on; D — roll −300, on; E — roll +400, on. Mark where the `min`/`max` limit applied. How many seconds after FLAPERON is turned on does input 14 reach 200?

### Step 3. The MATEKF405TE timers
The table from `src/main/target/MATEKF405TE/target.c` (INAV 9.1.0, lines 28–42):

```c
    DEF_TIM(TIM8,  CH4,  PC9,  TIM_USE_OUTPUT_AUTO,   0, 0), // S1 D(2,7,7) UP217
    DEF_TIM(TIM8,  CH3,  PC8,  TIM_USE_OUTPUT_AUTO,   0, 0), // S2 D(2,2,0) UP217
    DEF_TIM(TIM1,  CH3N, PB15, TIM_USE_OUTPUT_AUTO,   0, 0), // S3 D(2,6,0) UP256
    DEF_TIM(TIM1,  CH1,  PA8,  TIM_USE_OUTPUT_AUTO,   0, 1), // S4 D(2,1,6) UP256

    DEF_TIM(TIM2,  CH4,  PB11, TIM_USE_OUTPUT_AUTO,   0, 0), // S5 D(1,7,3) UP173
    DEF_TIM(TIM2,  CH3,  PB10, TIM_USE_OUTPUT_AUTO,   0, 0), // S6 D(1,1,3) UP173
    DEF_TIM(TIM2,  CH2,  PB3,  TIM_USE_OUTPUT_AUTO,   0, 0), // S7 D(1,6,3) UP173
    DEF_TIM(TIM2,  CH1,  PA15, TIM_USE_OUTPUT_AUTO,   0, 0), // S8 D(1,5,3) UP173

    DEF_TIM(TIM12, CH1,  PB14, TIM_USE_OUTPUT_AUTO,   0, 0), // S9  DMA NONE
    DEF_TIM(TIM13, CH1,  PA6,  TIM_USE_OUTPUT_AUTO,   0, 0), // S10 DMA NONE
    DEF_TIM(TIM4,  CH1,  PB6,  TIM_USE_OUTPUT_AUTO,   0, 0), // S11 D(1,0,2)

    DEF_TIM(TIM3,  CH4,  PB1,  TIM_USE_LED,    0, 0), // 2812LED  D(1,2,5)
```

DShot requires DMA: TIM12 and TIM13 do not have it (`timer_def_stm32f4xx.h:71, 74`), and a DShot motor on S9 or S10 will not start: the target is built with `USE_DSHOT_DMAR`, the output initialization returns an error, `status` shows `PWM output init error`, and arming is blocked by the `PWMOUT` flag.

a) A quadcopter, 4 motors on DShot300, all timers AUTO. Which outputs go to the motors, and which and how many to the servos?

b) The 4+1 VTOL from the worked example: 5 motors on DShot300 and 4 servos. The owner soldered it like this: motors 0–3 on S1–S4, the pusher on S5, the servos on S6, S7, S8 and S9, all timers AUTO. Find the conflicts, write down what the firmware will actually do, and propose two `timer_output_mode` commands after which everything works on DShot. Where do the pusher motor and the servos have to be resoldered?

### Step 4. Three errors in a VTOL config
The same 4+1 aircraft, but the hover profile is written differently (profile 1 is as in the worked example):

```text
mixer_profile 2
set platform_type = MULTIROTOR
set mixer_control_profile_linking = OFF
set mixer_automated_switch = ON
set mixer_switch_trans_timer = 4
mmix 0 1.000 -1.000  1.000 -1.000
mmix 1 1.000 -1.000 -1.000  1.000
mmix 2 1.000  1.000  1.000  1.000
mmix 3 1.000  1.000 -1.000 -1.000
mmix 4 -1.000 0 0 0
smix 0 1 1 50 0 -1
smix 1 2 0 50 0 -1
smix 2 3 0 50 0 -1
```

First, for the **correct** config from the theory, fill in the table: what motors 0–3, motor 4, servo 1 (with a pitch `axisPID` of +200) and servo 4 output in three states — hover, transition (MIXER TRANSITION active), the airplane profile. Then find three errors in the config above. The owner wanted: a 4 s acceleration with the pusher motor at 30 % and its own PIDs in each profile.

### Moving to real hardware
On the bench, props off. Save a `diff all`. On the Mixer tab compare the timer colors with your table from the `target.c` of your board and assign `timer_output_mode`; after a reboot `status` must not contain `PWM output init error`, and the `PWMOUT` flag must be absent. Turn on “Enable motor and servo output” and on the Outputs tab check every servo: center, endpoints without stalling or buzzing, direction by the rule from inav-setup-wing. Power the servos from a separate BEC (bf-servos-pwm). For a VTOL: flip the three-position switch and watch in Outputs that the pusher motor shows exactly `−throttle × 1000` in the transition and that the hover motors are stopped after the profile change. Abort if: any motor spins in an unexpected switch state, a servo buzzes at its stop, the flight controller reboots when the servos move.

Self-check: the lab is done when:
- step 1: the six `mmix` lines match the reference to the third decimal place, and the six motor values to ±1;
- step 2: the ten pulses match the reference to ±1 µs, the limit is found in exactly one case, the deployment time is 1.0 s;
- step 3: 7 servo outputs are named for 4 motors, both conflicts are found for the 4+1 and the final layout matches the reference;
- step 4: the state table matches the reference and all three errors are named with their consequences;
- (hardware, if you have a board) `status` has no `PWM output init error`, and the pusher motor shows the calculated value in the transition.

**Reference for the self-check.**

Step 1. The lines match the “Hex X” preset from `js/model.js` of Configurator 9.1.0:

```text
mmix 0 1.000 -0.500  0.866  1.000
mmix 1 1.000 -0.500 -0.866  1.000
mmix 2 1.000  0.500  0.866 -1.000
mmix 3 1.000  0.500 -0.866 -1.000
mmix 4 1.000 -1.000  0.000 -1.000
mmix 5 1.000  1.000  0.000  1.000
```

The motors: 1399, 1501, 1499, 1601, 1400, 1600 (for motors 1 and 2 the sum ±1.96 is truncated to ±1). If you got 1359, 1462, 1538, 1641, 1440, 1560 — a yaw of +40 got into the calculation, but in the task it is 0. Typical errors: all the roll signs are reversed — `+sin φ` was taken (a right motor must slow down on a roll to the right); pitch ±1.000 instead of ±0.866 — the table was scaled per axis, but the preset normalizes to the arm length; yaw with the opposite sign — it was mixed up that the “+” goes to a prop that spins counterclockwise.

Step 2.

| Case | Servo 3, µs | Servo 4, µs |
|---|---|---|
| A | 1748 | 1308 |
| B | 1369 | 1792 |
| C | 1900 | 1500 |
| D | 1535 | 2000 |
| E | 1900 (calculated 1976, limited by `max`) | 1442 |

Input 14 reaches 200 in 200 / (20 × 10) = 1.0 s. Typical errors: 1820 for servo 3 in case A — the endpoints were taken as 1000/2000 and the factor (1900 − 1520) / 500 = 0.76 was forgotten; 1667 for servo 4 in case A — the `rate` of −100 was forgotten; servo 4 “out of range” in case D — the sum −300 − 200 = −500 gives +500 after the reverse, which is exactly `max`, and there is no clipping.

Step 3. a) The motors — S1, S2 (TIM8), S3, S4 (TIM1); the servos — S5–S8 (TIM2), S9 (TIM12), S10 (TIM13), S11 (TIM4), 7 in total. b) Conflict 1: the fifth motor on S5 takes the whole of TIM2, S5–S8 become motor outputs, and the servos are left with S9, S10, S11 — three outputs for four servos, the error `Not enough servo outputs/timers` and the `PWMOUT` flag; the servos on S6–S8 get no pulses. Conflict 2: if you give TIM2 to the servos with one command, the fifth motor lands on S9 (TIM12) without DMA — DShot does not work there. The solution: `timer_output_mode 1 SERVOS` (TIM2) and `timer_output_mode 3 MOTORS` (TIM4). The result: motors on S1–S4 and S11, servo outputs S5–S10; resolder the pusher motor to S11 and servos 1–4 to S5–S8. Typical errors: “6 outputs for the servos with five motors in AUTO” — it was forgotten that a timer is taken as a whole; `timer_output_mode 2 SERVOS` — the TIM number instead of the index (TIM2 → 1).

Step 4.

| Output | Hover (profile 2) | Transition | Airplane (profile 1) |
|---|---|---|---|
| Motors 0–3 | throttle + stabilization | throttle + stabilization | stopped (−1.000) |
| Motor 4 | stopped | 1300 µs | throttle from the stick |
| Servo 1, pitch +200 | 1600 µs | 1600 µs | 1700 µs |
| Servo 4 | 1500 µs (no rules) | 1500 µs | follows yaw |

The errors: 1) `mmix 4 -1.000` is a placeholder, and the motor will not spin up in the transition; 30 % needs −1.300. 2) `mixer_switch_trans_timer = 4` is 0.4 s, not 4 s; 40 is needed. Together with the first error an automated RTH will switch to the airplane profile with almost no airspeed — a stall. 3) `mixer_control_profile_linking = OFF`: the linking is checked in the profile being switched to, so on the return to the hover the control profile stays the airplane one — a multirotor on fixed-wing PIDs. Typical misses: calling the half `smix` weights an error (that is a recommendation of the documentation) or the absence of a rule for servo 4 in profile 2 (a servo without rules sits at `mid`).

## diagnostics
- **Symptom:** the copter flips on takeoff right after liftoff
  - Possible cause: the `mmix` lines do not match the real motor positions, the outputs are mixed up, the motors spin the wrong way or the props are on the wrong motors; props-out without `motor_direction_inverted = ON`.
  - What to do: without props spin the motors one at a time on the Outputs tab and compare the position and the direction with the table; recalculate the line from the azimuth (`roll = −sin φ`, `pitch = −cos φ`).
  - Consequences: if only the yaw sign is wrong — not a flip but a fast spin around the vertical axis.
- **Symptom:** it does not arm, `status` has the `PWMOUT` flag
  - Possible cause: there were not enough timers for the motors or the servos; a DShot motor landed on a timer without DMA.
  - What to do: `status` → the `PWM output init error` line; recalculate the layout from `target.c`, assign `timer_output_mode`, or change `motor_pwm_protocol`.
- **Symptom:** a servo does not move although there is an `smix` rule
  - Possible cause: `feature PWM_OUTPUT_ENABLE` is not enabled; the servo is connected to a pad of a motor timer; a rule with weight 0 precedes the rule, and the table ended at it; the logic condition of the rule is false.
  - What to do: the Mixer tab — the output function; `smix` without arguments — the rules in sequence; check the condition on the Programming tab.
- **Symptom:** a servo is connected to “its” output, but the neighboring one works
  - Possible cause: a gap in the servo numbers — the outputs are assigned consecutively from the lowest to the highest number.
  - What to do: renumber the servos without gaps.
- **Symptom:** the gimbal does not respond to tilt
  - Possible cause: the CAMSTAB mode is not active — inputs 12 and 13 are zero.
  - What to do: assign CAMSTAB to a channel or to a permanent range; choose the weight from the µs/° of the servo.
- **Symptom:** after pasting a `diff` the pusher motor disappeared
  - Possible cause: in the profile a line with `throttle` 0 preceded it — the `mmix` output stopped at it, and the motor line did not get into the backup.
  - What to do: write placeholders as −1.000; after a restore compare `mmix` in both profiles.
- **Symptom:** the profile switch has no effect
  - Possible cause: a navigation mode is active (including ALTHOLD), sensor calibration is running after power-up, the CLI is open or the board has one profile (F411).
  - What to do: switch in ANGLE or ACRO without navigation; check that `diff all` has a `mixer_profile 2` block.
- **Symptom:** the pusher motor spins in the hover at low throttle
  - Possible cause: `airmode_type = THROTTLE_THRESHOLD` — the documentation forbids it for VTOL.
  - What to do: `STICK_CENTER` or `STICK_CENTER_ONCE`.
- **Symptom:** on RTH the aircraft switched to the airplane and stalled
  - Possible cause: `mixer_switch_trans_timer` is small or 0, the pusher motor is written as a −1 placeholder.
  - What to do: measure the time to accelerate to a speed 20–30 % above stall in a manual transition and write it in tenths of a second.
  - Consequences: a loss of tens of meters of altitude; below that margin the automated transition must not be enabled.

## checklist
- The platform type is set in every mixer profile, the number of motors and servos is counted over both profiles
- Every `mmix` line is checked against the motor position and the prop direction; without props the motors are tested one at a time
- The servo numbers have no gaps, the sum of the weights on a servo does not take it beyond ±500 in normal flight
- The output layout is written out from `target.c`; no servo sits on a motor timer, DShot motors are only on timers with DMA
- `status` has no `PWM output init error`, `feature PWM_OUTPUT_ENABLE` is enabled after the servo check
- The servos are powered from a separate BEC, the `min`/`max` endpoints are set without stalling
- For a VTOL: control profile linking is ON in both profiles, `MIXER PROFILE 2` and `MIXER TRANSITION` are on a three-position switch, `airmode_type` is not THROTTLE_THRESHOLD
- Motor placeholders are −1.000, transition motors are from −1.05 to −2.0, the transition timer is in tenths of a second
- Each profile is flown separately before the first transition in the air; a `diff all` is saved

## references
- mixer.c — mixTable, the motor count, the platform flags, INAV 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/flight/mixer.c | primary | A
- servos.h — inputSource_e (0…60), MAX_SUPPORTED_SERVOS, INAV 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/flight/servos.h | primary | A
- servos.c — servoMixer, scaling and limiting, INAV 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/flight/servos.c | primary | A
- mixer_profile.c — hot profile switching, the automated transition, INAV 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/flight/mixer_profile.c | primary | A
- pwm_mapping.c — assignment of outputs to timers, INAV 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/drivers/pwm_mapping.c | primary | A
- cli.c — mmix, smix, servo, timer_output_mode, resource, INAV 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/fc/cli.c | primary | A
- settings.yaml — defaults and ranges, INAV 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/fc/settings.yaml | primary | A
- MATEKF405TE target.c — the timer table, INAV 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/target/MATEKF405TE/target.c | primary | A
- timer_def_stm32f4xx.h — DMA of the F4 timer channels, INAV 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/drivers/timer_def_stm32f4xx.h | primary | B
- fc_msp_box.c — the mode ids of CAMSTAB, FLAPERON, MIXER PROFILE 2, MIXER TRANSITION, GIMBAL, INAV 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/fc/fc_msp_box.c | primary | B
- model.js — the mixer presets of Configurator 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav-configurator/9.1.0/js/model.js | primary | A
- Mixer and platform type — INAV docs 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/docs/Mixer.md | primary | A
- MixerProfile — INAV docs 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/docs/MixerProfile.md | primary | A
- VTOL — INAV docs 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/docs/VTOL.md | primary | A
- ESC and servo outputs — INAV docs 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/docs/ESC%20and%20servo%20outputs.md | primary | B
- Servo Gimbal — INAV docs 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/docs/Servo%20Gimbal.md | primary | B
- Serial Gimbal — INAV docs 9.1.0 | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/docs/Serial%20Gimbal.md | primary | B

## notes
The documents `docs/VTOL.md` and `docs/MixerProfile.md` in the 9.1.0 tag still say `set mixer_pid_profile_linking = ON` — the 9.x firmware rejects this line; the setting is called `mixer_control_profile_linking`. The same documents give the range of the “transition” throttle as −2.0 < throttle < −1.0, while the condition in the code is `≤ −1.05` and `≥ −2.0`; the value −1.0 is a placeholder. The input table in `docs/Mixer.md` ends at id 29; inputs 30–60 are taken from `servos.h`.
