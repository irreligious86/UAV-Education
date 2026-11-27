---
id: bf-features-tour
title: "The other Betaflight modes and features: turtle, launch control, 3D, acro trainer, Angle/Horizon, dynamic idle, camera control"
level: L2
readingTime: 55 min
firmware: Betaflight 2025.12 (checked against 2025.12.5); the lab was captured on the 4.5.x sources (branch 4.5-maintenance, 7dcc851; version.h 4.5.6, the latest release is 4.5.5)
status: published
added: 2026-11-15
tags:
  - Betaflight
  - modes
  - turtle mode
  - dynamic idle
  - Angle
  - Horizon
  - launch control
  - 3D
related:
  - bf-modes-osd
  - bf-arming-safety
  - bf-pid-reg-in-bf
  - bf-pid
  - bf-rpm-filter
  - bf-rates-rc
  - f-esc-firmware
  - bf-setup-scratch
  - bf-adjustments
  - bf-ports
  - bf-cli
  - bf-led-buzzer
next:
  - bf-blackbox
source: content/betaflight/bf-features-tour.md
source_hash: a328442fe3a9
---

## summary
A reference on the Betaflight 2025.12 modes and features beyond basic setup: turtle mode, launch control, 3D, acro trainer, Angle and Horizon (the 4.5 revision, unchanged in 2025.12), dynamic idle and `MOTOR_STOP`, camera control, PARALYZE and USER1–4. For each feature: what the code does (file and function), the variables with defaults and ranges, when to enable it, the traps. There is a table of all modes with the `permanentId` for `aux` and a summary table of the `set` variables. The Python lab repeats the firmware math: the Angle law and Horizon strength, the dynamic idle controller on synthetic RPM, the motor outputs in turtle. On hardware: turtle on grass, launch control on the ground, 3D without props first.

## theory
### Modes: the `permanentId` table for `aux`
The `aux` format (`cli/cli.c`, the same in 4.5 and 2025.12): `aux <slot 0–19> <permanentId> <AUX channel, 0 = AUX1> <start> <end> <logic 0 OR / 1 AND> <linked mode>`. The second field is taken from `msp/msp_box.c`, not from `rc_modes.h`. The Modes tab shows only the modes allowed by `initActiveBoxIds()`: if a mode is missing, the condition in the right-hand column is not met.

| id | Mode | What it does | When it is visible |
|---|---|---|---|
| 0 / 1 / 2 | ARM / ANGLE / HORIZON | arming; self-leveling; the blended mode (below) | ARM always; ANGLE and HORIZON with an accelerometer |
| 4 | ANTI GRAVITY | enables anti-gravity with a switch | only if `feature ANTI_GRAVITY` is off (it is on by default) |
| 5 / 6 / 7 | MAG / HEADFREE / HEADADJ | heading hold; control relative to the pilot; a new “nose” for headfree | MAG with a compass; 6 and 7 with an accelerometer |
| 8 | CAMSTAB | servo gimbal stabilization | `feature SERVO_TILT` |
| 12 | PASSTHRU | manual control of the servos | airplane mixers only |
| 13 / 52 | BEEPER / BEEPER MUTE | turn the beeper on (finding it in grass) / mute it | always |
| 15 | LEDLOW | turns the LED strip off (`ledStripDisable()`) | `feature LED_STRIP` |
| 17 | CALIB | in-flight accelerometer calibration | `feature INFLIGHT_ACC_CAL` |
| 19 | OSD DISABLE | hides the OSD | always |
| 20 | TELEMETRY | telemetry runs only with the switch on | `feature TELEMETRY` |
| 23–25 | SERVO1–3 | airplane servo outputs | `mixer CUSTOMAIRPLANE` |
| 26 / 31 | BLACKBOX / BLACKBOX ERASE | logging only by the switch / erasing the flash | always; 31 with onboard flash |
| 27 | FAILSAFE | a failsafe test with a switch | always |
| 28 | AIR MODE | airmode with a switch | only if `feature AIRMODE` is off |
| 29 | 3D DISABLE (in 4.5 — “3D DISABLE / SWITCH”) | 3D: disable reversing, or reversing on a switch (below) | `feature 3D` |
| 30 | FPV ANGLE MIX | mixing of yaw and roll for the camera tilt `fpv_mix_degrees` | with an accelerometer |
| 32–34 | CAMERA CONTROL 1–3 | camera buttons over the RunCam Device Protocol (below) | always (`USE_RCDEVICE`) |
| 35 | FLIP OVER AFTER CRASH | turtle mode | only if DShot is selected |
| 36 | PREARM | the second arming key (bf-arming-safety) | always |
| 37 | GPS BEEP SATELLITE COUNT | the beeper counts the satellites | `feature GPS` |
| 39 / 48 | VTX PIT MODE / VTX CONTROL DISABLE | VTX pit mode / block changing the VTX from the OSD | with VTX support in the build |
| 40–43 | USER1–4 | switch the PINIO pins (power of the VTX, camera, BT module) | only if `pinio_box` refers to 40–43 |
| 44 | PID AUDIO | sound of the PID state | only in builds with `USE_PID_AUDIO` |
| 45 | PARALYZE | “paralyze” the aircraft until reboot (below) | always |
| 46 | GPS RESCUE | return home (bf-failsafe) | `feature GPS`, not 3D, not an airplane |
| 47 | ACRO TRAINER | an angle limit in ACRO (below) | an accelerometer and the ACRO_TRAINER build option |
| 49 | LAUNCH CONTROL | a start from a stand (below) | always (`USE_LAUNCH_CONTROL` in standard builds) |
| 50 | MSP OVERRIDE | channel override over MSP | `msp_override_channels_mask` ≠ 0 |
| 51 | STICK COMMANDS DISABLE | block stick commands (stick arming, saving, the camera menu) | always |
| 53 | READY | the READY text in the OSD before arming (for racing) | always |
| 54 | LAP TIMER RESET | reset of the GPS lap timer | builds with `USE_GPS_LAP_TIMER` |

Numbers 0–54 are the same in 4.5 and 2025.12. 2025.12 added id 3 ALTHOLD (altitude hold), id 11 POS HOLD (GPS position hold) and id 55 CHIRP (the chirp generator, `ctl-sysid`) — each is visible only with the corresponding build option; 4.5 does not have these numbers. ALTHOLD and POS HOLD, when on, block arming (the `ALT_HOLD_SW`, `POS_HOLD_SW` flags). USER1–4 are at 40–43, and the name is set through `box_user_N_name` (up to 16 characters, also present in 4.5).

{{lesson:bf-led-buzzer|BEEPER, BEEPER MUTE and LEDLOW from this table: the beeper conditions from the source, `rxfail` for BEEPER turning on by itself and the motor beacon.}}

**PARALYZE (45)** is a “sticky” mode (`fc/rc_modes.c`). It can be triggered only if the switch has been off at least once later than 5 s after startup (`STICKY_MODE_BOOT_DELAY_US`): a switch that is on at startup does nothing. Once triggered, the `PARALYZE` flag blocks arming, and without arming, stick commands, adjustments and the OSD menu are disabled. It is cleared only by a reboot. It does not disarm in the air. The purpose is racing: a crashed aircraft will not be armed by accident while it is carried off the track.

**USER1–4 and PINIO.** On many boards a PINIO pin switches the power of the VTX or camera. The link: `set pinio_box = 40,255,255,255` (PINIO1 follows USER1, 255 — not assigned), then `aux` with id 40. `pinio_config` (1 — output, +128 — inversion) is set in the board target.

### Turtle mode (FLIP OVER AFTER CRASH)
The aircraft is on its back, the motors spin in reverse, and the stick selects which side pushes. The 2025.12 code: `tryArm()` and `updateArmingStatus()` in `fc/core.c`, `applyCrashFlipModeToMotors()` in `flight/mixer.c` (in 4.5 — `applyFlipOverAfterCrashModeToMotors()`; the algorithm there is different, and it is covered in step 3 of the practice).

- **Requirements.** The mode is visible only with DShot. When arming with the mode on, the FC sends all ESCs DShot command 21 `SPIN_DIRECTION_REVERSED`, and on disarm — 20 `SPIN_DIRECTION_NORMAL`: the ESC firmware must execute them (Bluejay, BLHeli_32, AM32 — check on the bench). Bidirectional DShot is not needed. With `feature 3D` the commands are not sent; the mixer simply uses the reverse half of the range.
- **Entry.** First the turtle switch, then ARM. The `ANGLE` and `GPS` flags are not set while the mode is on. OSD: before arming `CRASHFLIP SW`, after — `>CRASH FLIP<` (in 4.5 — `CRASH FLIP SWITCH` and `> CRASH FLIP <`), and the beeper beeps.
- **Exit.** Disarm, turtle off, ARM again — this works in any version. In 2025.12 you can also turn the turtle switch off without touching ARM: with `crashflip_auto_rearm = OFF` (the default) the FC disarms itself and sets the `FLIP_SWITCH` flag, which is cleared only by a manual disarm (lower ARM), after which you arm again; with `crashflip_auto_rearm = ON` the aircraft stays armed and the motors switch to normal rotation — the props will spin forward immediately, so get your hands and face out of the way beforehand. In 4.5 turning the switch off while armed changes nothing: the state is reset only by a disarm. With a forgotten switch the aircraft spins its motors in reverse after arming and will not take off.
- **The stick.** Roll — the pair of motors on one side, pitch — the front or rear pair, a diagonal (within 30° of the bisector) — a single motor, yaw dominant — a diagonal pair. The motors of the “other side” stand still or spin at `crashflip_motor_percent`. The stick deadband is 15 %; above it, the power in 2025.12 equals the stick deflection (linear, no curve), and an output below 2 % of the range means stop. 4.5 had the `crashflip_expo` curve (35): x' = (1 − e)·x + e·x³, e = expo/100, and a stop below “minimum + 20” DShot; `crashflip_expo` was removed in 2025.12.
- **Auto-stop (`crashflip_rate`, from 2025.12).** 0 (the default) — off, the motors pull for as long as you hold the stick. With a value above 0 the power is reduced by two factors: by rotation rate (no attenuation up to half of the `crashflip_rate` × 10 °/s threshold, then linearly down to zero at the threshold) and, if there is an accelerometer, by the angle traveled (zero after turning about 90° from the initial attitude). The aircraft stops pushing once it is already flipping over. In a RACE_PRO build the defaults are different: `crashflip_rate = 30`, `crashflip_auto_rearm = ON`.
- **Why the motors get hot.** In turtle `motorRangeMax = motorOutputHigh`: full stick is full throttle (2047; in 4.5 — 2027 because of the subtracted deadband). The prop is jammed against the grass, the rotor is almost stalled, there is no back-EMF, and the current is limited only by the winding resistance. There is no timer in either 4.5 or 2025.12 (with `crashflip_rate = 0`). The rule: bursts of 0.5–1 s; if it has not flipped in 3 attempts — walk.
- Runaway takeoff is not checked in turtle, and arming in turtle re-enables the protection for the next takeoff.

Carrying settings over from 4.5: 2025.12 will not accept the line `set crashflip_expo = …` from an old `diff` (`INVALID NAME`); `crashflip_motor_percent` carries over as is.

### Launch control
A race start: the aircraft sits on its battery or a stand, tilted forward, and holds the angle until throttle is applied. The code: `canUseLaunchControl()` and `processRx()` in `fc/core.c`, `applyLaunchControl()` in `flight/pid.c`.

- **Conditions.** Mode 49 is on **at the moment of arming**, arming is with a switch, the mode is ACRO, there is no `feature 3D`, and with `MOTOR_STOP` — airmode as well. While launch is active, airmode is treated as enabled.
- **What the PID does.** The stick commands a rate of 100 °/s·2·x with travel limited to ±50 % (in `NORMAL` and `FULL` — on all three axes, in `PITCHONLY` — pitch only): 100 °/s is reached at half travel and does not depend on your rates. Set the angle, release the stick, and I holds the position with its own gain `launch_control_gain` (40). D and feedforward are disabled. `NORMAL`: yaw is not held (the yaw I is zeroed). `FULL`: yaw is held as well, with the yaw I limited to ±50. `PITCHONLY`: only the pitch P and I work, I does not go negative, and the front motors are clamped at minimum in the mixer so that the aircraft does not slide off the stand.
- **The start.** Throttle above `launch_trigger_throttle_percent` (20 %) — I is reset, launch is over, and the aircraft flies in ordinary ACRO. `launch_angle_limit` > 0 (needs an accelerometer) prevents a forward tilt greater than the set value. Within 10° of the limit the tilt rate smoothly drops to 5 °/s.
- **Repeating.** `launch_trigger_allow_reset = ON` — after a disarm, toggle the mode switch; `OFF` — only a reboot. Before the start, arming and disarming can be repeated. OSD: `LAUNCH 25` (the pitch), blinking within 10 % of the threshold.

The default is `launch_control_mode = PITCHONLY` (in 4.5 the default was `NORMAL`); the rest of the launch control logic did not change in 2025.12.

### 3D (reversible motors)
`feature 3D`: throttle at center is zero, down is reverse thrust, up is forward. This is **not** the bidirectional DShot from bf-rpm-filter: the ESC has to be in Bidirectional (3D) mode (f-esc-firmware). Betaflight does not switch the ESC itself: that is done in the ESC configurator or with `dshotprog 255 10 12` (3D_MODE_ON + save), if the ESC firmware supports it.

- **DShot.** The split is set by the protocol (`drivers/dshot.c`): 48–1047 — reverse, 1048–2047 — forward, 0 — stop. `3d_deadband_low/high`, `3d_neutral`, `3d_limit_low/high` are **not used** with DShot: they are endpoints for PWM/OneShot (`analogInitEndpoints()` in `drivers/motor.c`). The idle `motor_idle` (before 2025.12 — `dshot_idle_value`) applies in both directions.
- **The stick.** `3d_deadband_throttle` (50 µs) is the deadband around `mid_rc` and the “throttle down” for arming: arming only at 1451–1549 µs. Inside the band the mixer keeps the direction the stick entered from. After a change of direction, I is zeroed for 250 ms. A switch disarm is instant (`processRx`).
- **Mode 29.** `3d_switched_mode = OFF`: the mode disables reversing, the whole stick travel is forward. `ON`: the switch selects the direction, and the stick travel is from zero to full throttle in that direction.
- **What gets disabled:** dynamic idle (its code is in the “not 3D” branch), `MOTOR_STOP`, launch control, GPS Rescue, the turtle commands.

### Acro trainer
ACRO with roll and pitch limited to the angle `acro_trainer_angle_limit` (20°), `applyAcroTrainer()` in `flight/pid.c`. It does not act in ANGLE, HORIZON or GPS Rescue. It needs an accelerometer and the ACRO_TRAINER build option in Cloud Build: without it there is no mode 47, and `set acro_trainer_*` gives `INVALID NAME`. When the angle is past the limit and the stick pulls further — setpoint = (limit − angle)·`acro_trainer_gain`/10 (no more than ±1000 °/s), and I is zeroed. Before the limit, the angle is predicted `acro_trainer_lookahead_ms` (50 ms) ahead, with the window proportional to the gyro rate up to 500 °/s, and when the prediction goes past the limit the setpoint brakes in advance. The stick in the opposite direction lifts the restriction. A flip is impossible by design.

### Angle and Horizon (the 4.5 revision, also in effect in 2025.12)
The code is `pidLevel()` and `calcHorizonLevelStrength()` in `flight/pid.c`, the gains are in `flight/pid_init.c`. The Angle law:

- Target = `angle_limit` · setpoint / max_rate, where setpoint is the ACRO setpoint from your rates and max_rate is the rate at full stick. **The shape of the rates sets the shape of Angle:** with the defaults (Actual 7/67/0) half stick is 185 out of 670 °/s, that is 16.6°, not 30° (step 1 of the practice).
- Rate = (target − angle) · `angle_p_gain`/10: 5 °/s per degree at 50. Plus `angle_feedforward` (50) from stick movement, smoothed by a PT3 (`angle_feedforward_smoothing_ms` 80 ms ≈ 2 Hz). The sum passes through a 50 Hz PT3 and becomes the setpoint of the rate loop.
- `angle_earth_ref` (100): yaw in Angle is multiplied by cos(target angle), and part of it is transferred into roll and pitch — a turn around the Earth's vertical. 0 is the old behavior.
- `level_race_mode = ON` (OFF by default) — Angle on roll only, pitch in ACRO (the racing “NFE” mode).

Horizon: setpoint = acro·(1 − s) + angle·s, where s = `horizon_level_strength`/100 · (1 − inclination/`horizon_limit_degrees`) · (1 − stick/`horizon_limit_sticks`), with the factors no less than 0 and the inclination being the larger of |roll|, |pitch|. At 75/135/75: level and stick centered — s = 0.75; stick at 75 % or inclination ≥ 135° — s = 0, pure ACRO, which is why a flip goes through without a “fight” on its back. The rise of s is smoothed by a PT1 `horizon_delay_ms` (500 ms), the fall is instant. `horizon_ignore_sticks = ON` removes the dependence on the stick.

{{diagram:chart-bf-horizon-strength|In Horizon (4.5 and 2025.12) leveling fades linearly toward a 135° inclination and toward 75 % of stick travel: at half stick near level only a third of the strength remains (0.25 of 0.75), and upside down the aircraft flies as in ACRO.}}

Renames 4.4 → 4.5: `level_limit` (55, up to 90) → `angle_limit` (60; up to 85 in 4.5, up to 80 in 2025.12); `angle_level_strength` → `angle_p_gain`; `horizon_transition` → `horizon_limit_sticks`; `horizon_tilt_effect` and `horizon_tilt_expert_mode` → `horizon_limit_degrees`; `roll_level_expo`/`pitch_level_expo` were removed, and the rates play their role. An old `diff all` from 4.4 will not apply these lines. 2025.12 added `angle_pitch_offset` (only in a WING build), and in POS HOLD mode the angle requested by the stick is limited to half of `ap_max_angle`.

One more feature from this group (it appeared in 4.5) is EZ landing: with `mixer_type = EZLANDING` the mixer limits the “throttle raise for the sake of the PID” (what airmode does) at low throttle, with the sticks near center and low GPS speed. The thresholds are `ez_landing_threshold/limit/speed` (25/15/50). The aircraft bounces less on landing. Without this mixer type the variables do nothing.

### Dynamic idle and MOTOR_STOP
Without dynamic idle the lower limit of a motor is `motor_idle` (550 = 5.5 % of the DShot range; before 2025.12 — `dshot_idle_value`), and RPM is not controlled: in a flat drop the airflow from below slows the props down to the desync threshold. Dynamic idle (`calculateThrottleAndCurrentMotorEndpoints()` in `mixer.c`) reads the RPM of the slowest motor over bidirectional DShot and uses a PID controller to raise the **lower limit of all motors**:

- the target: `dyn_idle_min_rpm` × 100 RPM (30 → 3000 RPM = 50 rev/s), 0 by default — off;
- P = error (rev/s) · `dyn_idle_p_gain` · 0.00015, I = Σ error · `dyn_idle_i_gain` · 0.01 · dT (I comes down slowly: the error is limited to −0.1 rev/s), D — from the smoothed (~20 ms) RPM with a gain of `dyn_idle_d_gain` · 3·10⁻⁷ · f_PID;
- the increase is limited by `dyn_idle_max_increase` (150 = 15 %) after the throttle has first been raised above the airmode threshold, and before that, that is on the ground, by the value of `motor_idle` (550 = 5.5 %). In 4.5 the limit on the ground was set by a separate variable, `dyn_idle_start_increase` (50 = 5 %); 2025.12 does not have it;
- with dynamic idle enabled, `motor_idle` **does not act** as a floor: the lower limit becomes 48 (0 %) plus the increase, and the throttle does not go below 1 %. In 2025.12 `motor_idle` still remains the limit of the increase on the ground (the item above); in 4.5 `dshot_idle_value` was ignored completely;
- `dshot_bidir = ON` and `motor_poles` are required. Without telemetry `mixerInitProfile()` silently zeroes the target: there is no error, and no feature either. The feature does not work in 3D;
- all `dyn_idle_*` settings are stored in the PID profile: another profile may have 0.

The documentation advises 30–40 for a 5″. Before enabling dynamic idle on whoops, first choose `motor_idle` so that the motors start reliably (the comment in `mixer_init.c` of 2025.12).

{{diagram:chart-bf-dyn-idle|The controller from mixer.c on a synthetic motor: with a static idle of 5.5 % the slowest motor sags to 2100 RPM in a flat drop, while dynamic idle adds 6.3 % of thrust and holds 3000; on the ground the same controller lowers the idle from 6100 to 3000 RPM.}}

{{lesson:bf-pid-reg-in-bf|Dynamic idle in the overall throttle path next to `thrust_linear`, `vbat_sag_compensation`, TPA and anti-gravity — with the formulas from `mixer.c` and `pid.c` and a calculation lab.}}

**`feature MOTOR_STOP`**: the motors are stopped at throttle below `min_check`, but only without airmode, without 3D and outside GPS Rescue (`mixTable()`). Airmode is enabled by default, so for most people `MOTOR_STOP` does nothing. `auto_disarm_delay` is tied to it (bf-arming-safety). In flight a stopped motor starts with a delay — for freestyle and racing that is harmful.

### Anti-gravity and I-term relax — briefly
**Anti-gravity** (`anti_gravity_gain` 80, 0–250; `anti_gravity_cutoff_hz` 5, 2–50; `anti_gravity_p_gain` 100, 0–250; `feature ANTI_GRAVITY` is on). The derivative of the throttle is filtered by a PT2 with emphasis on the lower part of the travel and temporarily speeds up the accumulation of I on roll and pitch, plus it gives a boost to P with the sticks near center. This counters the nose dip on a sharp throttle punch. Tuning and logs are in bf-pid-reg-in-bf.

**I-term relax** (`iterm_relax = RP`, `iterm_relax_type = SETPOINT`, `iterm_relax_cutoff = 15`, 1–50). On a fast stick movement the accumulation of I is suspended so that after a flip I does not “carry” the aircraft past the angle (bounce-back). It is disabled in launch control and crash recovery. Details are in bf-pid-reg-in-bf and bf-pid.

### Camera control: the camera menu from the radio
**RunCam Device Protocol** (`io/rcdevice*.c`, always in the build). The camera (RunCam Split, Micro Swift 3, Racer 2, some Caddx models) is on a UART TX+RX, port function RunCam Device (bit 16384). At startup the FC polls it `rcdevice_init_dev_attempts` = 6 times at 1000 ms intervals. Modes 32–34 act on the edge of the switch: 1 — the Wi-Fi button (not while armed), 2 — power or recording (in flight too), 3 — change mode (not while armed). The camera menu is operated with the sticks while disarmed (`rcdevice_cam.c`): throttle at 1350–1650, roll and pitch centered, yaw > 1920 — enter; in the menu roll and pitch beyond 1080/1920 are the arrows, yaw right is Enter, yaw left is exit. The Betaflight menu (CMS) is a different gesture: yaw left + pitch up.

**Joystick emulation** (`drivers/*/camera_control.c`) is for cameras with a single OSD wire and a resistive keypad (the HS1177 and its relatives). The CAMERA_CONTROL build option, `resource CAMERA_CONTROL <a pin with a timer>`, a 150–600 Ω resistor in series. A key press is imitated by the voltage U = U_ref · R_key / (R_int + R_key): `camera_control_ref_voltage` 330 (3.3 V), `camera_control_internal_resistance` 470 (47 kΩ), `camera_control_button_resistance` 450,270,150,68,0 (×100 Ω: Enter, Left, Up, Right, Down), a press lasts `camera_control_key_delay` 180 ms. The sticks while disarmed (`rc_controls.c`): throttle in the middle + yaw right — Enter, roll and pitch — the arrows, throttle down + pitch up — “Up” for 2 s.

### Parameter reference (2025.12)
| Parameter | Default | Range | Meaning |
|---|---|---|---|
| `crashflip_motor_percent` | 0 | 0–100 % | the share for the motors of the “other side” in turtle |
| `crashflip_rate` | 0 | 0–250 (×10 °/s) | turtle auto-stop by rate and angle, 0 — off (from 2025.12; in 4.5 its place is taken by `crashflip_expo` 35, 0–100 — the stick curve) |
| `crashflip_auto_rearm` | OFF | OFF/ON | stay armed when the turtle switch is turned off (from 2025.12) |
| `launch_control_mode` | PITCHONLY | NORMAL / PITCHONLY / FULL | what is held (in 4.5 the default is NORMAL) |
| `launch_trigger_throttle_percent` | 20 | 0–90 % | the start throttle |
| `launch_angle_limit` | 0 | 0–80° | the forward tilt limit (0 — none) |
| `launch_control_gain` | 40 | 0–200 | the position-hold I |
| `launch_trigger_allow_reset` | ON | OFF/ON | repeat through the switch |
| `3d_deadband_throttle` | 50 | 1–100 µs | the stick deadband around `mid_rc` |
| `3d_deadband_low` / `_high`, `3d_neutral`, `3d_limit_low` / `_high` | 1406 / 1514, 1460, 1000 / 2000 | 750–1500 / 1500–2250, 750–2250, 750–1500 / 1500–2250 | PWM only: the reversing boundaries, the pulse while disarmed, the end pulses |
| `3d_switched_mode` | OFF | OFF/ON | mode 29 selects the direction |
| `acro_trainer_angle_limit` | 20 | 10–80° | the angle limit |
| `acro_trainer_lookahead_ms` / `_gain` | 50 / 75 | 10–200 ms / 25–255 | the prediction; the stiffness (/10) |
| `acro_trainer_debug_axis` | ROLL | ROLL/PITCH | the axis for debug |
| `angle_limit` | 60 | 10–80° | the angle at full stick (in 4.5 — up to 85°) |
| `angle_p_gain` | 50 | 0–200 | °/s per degree of error ×10 |
| `angle_feedforward` / `_smoothing_ms` | 50 / 80 | 0–200 / 10–250 ms | FF from the stick and its smoothing |
| `angle_earth_ref` | 100 | 0–100 % | the Earth-referenced turn in Angle |
| `horizon_level_strength` | 75 | 0–100 | the leveling strength near level |
| `horizon_limit_sticks` | 75 | 10–200 % | the stick position at which leveling = 0 |
| `horizon_limit_degrees` | 135 | 10–250° | the inclination at which leveling = 0 |
| `horizon_ignore_sticks` | OFF | OFF/ON | do not attenuate by the stick |
| `horizon_delay_ms` | 500 | 10–5000 ms | the smoothness of the leveling build-up |
| `level_race_mode` | OFF | OFF/ON | Angle on roll only |
| `ez_landing_threshold` / `_limit` / `_speed` | 25 / 15 / 50 | 0–200 / 0–75 / 0–250 | EZ landing (`mixer_type = EZLANDING`) |
| `dyn_idle_min_rpm` | 0 | 0–200 (×100 RPM) | the dynamic idle target, 0 = off |
| `dyn_idle_p_gain` / `_i_gain` / `_d_gain` | 50 / 50 / 50 | 1–250 / 1–250 / 0–250 | the controller gains |
| `dyn_idle_max_increase` | 150 | 10–255 (×0.1 %) | the limit of the increase after airmode |
| `motor_idle` | 550 | 0–2000 (×0.01 %) | the static idle (before 2025.12 — `dshot_idle_value`); with dynamic idle — the limit of the increase on the ground |
| `dyn_idle_start_increase` | — | — | 4.5 only: 50, 10–255 (×0.1 %), the limit of the increase before airmode; removed in 2025.12 |
| `anti_gravity_gain` / `_cutoff_hz` / `_p_gain` | 80 / 5 / 100 | 0–250 / 2–50 / 0–250 | anti-gravity |
| `iterm_relax` / `_type` / `_cutoff` | RP / SETPOINT / 15 | OFF…RPY_INC / GYRO, SETPOINT / 1–50 | I-term relax |
| `camera_control_mode` | HARDWARE_PWM | HARDWARE_PWM / SOFTWARE_PWM / DAC | the emulation method (SOFTWARE_PWM — with a capacitor) |
| `camera_control_ref_voltage` / `_key_delay` | 330 / 180 | 200–400 (×10 mV) / 100–500 ms | the OSD pin voltage; the press |
| `camera_control_internal_resistance` / `_button_resistance` | 470 / 450,270,150,68,0 | 10–1000 / array (×100 Ω) | the camera's resistor; the buttons Enter…Down |
| `camera_control_inverted` | OFF | OFF/ON | output inversion |
| `rcdevice_init_dev_attempts` / `rcdevice_init_dev_attempt_interval` | 6 / 1000 | 0–10 / 0–5000 ms | polling the camera at startup |
| `rcdevice_protocol_version` / `rcdevice_feature` | 0 / 0 | 0–1 / 0–65535 | the protocol version, the feature mask |
| `pinio_box` | 255,255,255,255 | `permanentId` | which mode drives PINIO1–4 |
| `box_user_1_name` … `_4_name` | empty | up to 16 characters | the names of USER1–4 |

Features: `feature 3D`, `feature MOTOR_STOP`, `feature ANTI_GRAVITY` (on), `feature AIRMODE` (on).

### Place in the system

- **Receives:** the `permanentId` values and AUX ranges (`bf-modes-osd`); the RPM of the slowest motor over bidirectional DShot for dynamic idle (`bf-rpm-filter`); the shape of the rates — it sets the shape of Angle (`bf-rates-rc`); the DShot motor-reversal commands that the ESC firmware must execute (`f-esc-firmware`).
- **Provides:** modes that change the setpoint and the lower motor limit for the PID and the mixer (`bf-pid-reg-in-bf`); the `PARALYZE` and `FLIP_SWITCH` flags and the arming block with ALTHOLD and POS HOLD on (`bf-arming-safety`).
- **If you get it wrong here:** you enabled dynamic idle without `dshot_bidir` → the target is silently zeroed: no error, and no feature either; it is checked with telemetry — `dshot_telemetry_info` (`bf-cli`), and bidir setup is in `bf-rpm-filter`. You left the turtle switch on → after arming the motors spin in reverse and the aircraft does not take off; it looks like the motor direction error from `bf-setup-scratch`.

## practice
The main path is Python that repeats the firmware math line by line: the same formulas, constants and 4.5 defaults (Betaflight SITL is not built here). What of this holds for 2025.12: step 1 (Angle, Horizon) — the formulas did not change in 2025.12; step 2 (dynamic idle) — the controller is the same, but the limit before takeoff there is `motor_idle` (5.5 %), not `dyn_idle_start_increase` (5 %); step 3 (turtle) — the 4.5 algorithm, which was replaced in 2025.12 (there is no `crashflip_expo` curve and no subtraction of 20 DShot units). The aircraft and motor models are teaching stand-ins, and they are marked as such. The three blocks below are pasted together into a single file, `lab.py`.

### Step 1. The Angle law and Horizon strength from `pidLevel()`
The goal: to see that the rates change Angle, that `angle_p_gain` is a time constant, and how the 4.5 Horizon blends ACRO and Angle.

```python
# bf-features-tour lab: Betaflight 4.5 maths reproduced from the source (4.5-maintenance 7dcc851; version.h says 4.5.6, not a release; src/ equals 4.5.5 except the version number in version.h).
# Part 1: Angle/Horizon setpoint law (flight/pid.c pidLevel, calcHorizonLevelStrength; flight/pid_init.c gains).
import math

def pt1_gain(f, dt):                      # common/filter.c pt1FilterGain
    w = 2 * math.pi * f * dt
    return w / (w + 1)

def pt3_gain(f, dt):                      # pt3FilterGain: cutoff shifted by CUTOFF_CORRECTION_PT3
    return pt1_gain(f * 1.961459177, dt)

RC_RATE, SRATE, EXPO = 7, 67, 0           # 4.5 default rates: Actual, roll_rc_rate 7, roll_srate 67, roll_expo 0

def actual_rate(x, rc=RC_RATE, sr=SRATE, ex=EXPO):   # fc/rc.c applyActualRates
    e = ex / 100
    expof = abs(x) * (x ** 5 * e + x * (1 - e))
    centre = rc * 10
    return x * centre + max(0, sr * 10 - centre) * expof

ANGLE_LIMIT, ANGLE_P = 60, 50             # angle_limit, angle_p_gain (pid[PID_LEVEL].P)
def angle_target(x, rc=RC_RATE, sr=SRATE):           # pidLevel: angleLimit * setpoint / maxRcRate
    return ANGLE_LIMIT * actual_rate(x, rc, sr) / actual_rate(1.0, rc, sr)

print("Part 1a. Angle target vs stick (angle_limit 60)")
print(" stick | setpoint 7/67 | target 4.5 defaults | target if rc_rate = srate (linear) | 4.4 level_limit 55 * stick")
for x in (0.1, 0.25, 0.5, 0.75, 1.0):
    print(f"  {x:4.2f} | {actual_rate(x):6.1f} deg/s  | {angle_target(x):6.1f} deg          |"
          f" {angle_target(x, 67, 67):6.1f} deg                          | {55 * x:5.1f} deg")

def angle_step(stick, p_gain=ANGLE_P, T=1.0, dt=125e-6, tau_rate=0.030):
    """Roll axis, stick step at t = 0. angleRate = (target - angle) * P/10 -> PT3 50 Hz (ATTITUDE_CUTOFF_HZ)
    -> rate setpoint. Inner rate loop: synthetic first-order lag tau_rate (stand-in for the rate PID + quad)."""
    k = pt3_gain(50, dt); s1 = s2 = s3 = 0.0
    gain = p_gain / 10.0                  # pid_init.c: angleGain = pid[PID_LEVEL].P / 10
    target = angle_target(stick)
    angle = rate = 0.0; t = 0.0; t63 = t90 = None; peak = 0.0; peak_rate = 0.0
    while t < T:
        cmd = (target - angle) * gain     # deg/s per deg of error
        s1 += k * (cmd - s1); s2 += k * (s1 - s2); s3 += k * (s2 - s3)
        rate += (s3 - rate) * dt / tau_rate
        angle += rate * dt; t += dt
        peak = max(peak, angle); peak_rate = max(peak_rate, rate)
        if t63 is None and angle >= 0.632 * target: t63 = t
        if t90 is None and angle >= 0.9 * target: t90 = t
    return target, t63, t90, peak, peak_rate

print("\nPart 1b. Step response: stick 0 -> 50 %, inner rate loop tau 30 ms (synthetic)")
for p in (25, 50, 100):
    tg, t63, t90, pk, pr = angle_step(0.5, p)
    print(f"  angle_p_gain {p:3d}: target {tg:5.1f} deg, 63 % at {t63*1e3:4.0f} ms, 90 % at {t90*1e3:4.0f} ms,"
          f" overshoot {max(0, pk - tg):4.1f} deg, peak rate {pr:5.0f} deg/s")

def horizon_strength(incl_deg, stick, level=75, lim_sticks=75, lim_deg=135, ignore_sticks=False):
    """calcHorizonLevelStrength (steady state, horizon_delay_ms PT1 not applied)."""
    s = max((lim_deg - incl_deg) / lim_deg, 0.0)
    ls = lim_sticks / 100
    s *= max((ls - stick) / ls, 1.0 if ignore_sticks else 0.0)
    return s * min(level / 100, 1.0)

print("\nPart 1c. Horizon level strength (4.5 defaults: level 75, limit_sticks 75, limit_degrees 135)")
print(" inclination |" + "".join(f" stick {x:4.2f} |" for x in (0, 0.25, 0.5, 0.75)))
for inc in (0, 30, 60, 90, 135, 180):
    print(f"   {inc:5d} deg |" + "".join(f"    {horizon_strength(inc, x):5.3f}   |" for x in (0, 0.25, 0.5, 0.75)))

dt = 125e-6
kh = pt1_gain(1e3 / (2 * math.pi * 500), dt)   # horizon_delay_ms 500 -> PT1 at 0.318 Hz on increases
st, t = 0.0, 0.0
while True:
    st += kh * (0.75 - st); t += dt
    if st >= 0.632 * 0.75: break
print(f"  horizon_delay_ms 500: after the stick returns to centre, strength reaches 63 % of 0.75 in {t*1e3:.0f} ms")
for a in (10, 30, 45):
    print(f"  angle_earth_ref 100, angle target {a:2d} deg: yaw setpoint x {math.cos(math.radians(a)):.3f}")
```

```text
Part 1a. Angle target vs stick (angle_limit 60)
 stick | setpoint 7/67 | target 4.5 defaults | target if rc_rate = srate (linear) | 4.4 level_limit 55 * stick
  0.10 |   13.0 deg/s  |    1.2 deg          |    6.0 deg                          |   5.5 deg
  0.25 |   55.0 deg/s  |    4.9 deg          |   15.0 deg                          |  13.8 deg
  0.50 |  185.0 deg/s  |   16.6 deg          |   30.0 deg                          |  27.5 deg
  0.75 |  390.0 deg/s  |   34.9 deg          |   45.0 deg                          |  41.2 deg
  1.00 |  670.0 deg/s  |   60.0 deg          |   60.0 deg                          |  55.0 deg

Part 1b. Step response: stick 0 -> 50 %, inner rate loop tau 30 ms (synthetic)
  angle_p_gain  25: target  16.6 deg, 63 % at  401 ms, 90 % at  873 ms, overshoot  0.0 deg, peak rate    36 deg/s
  angle_p_gain  50: target  16.6 deg, 63 % at  205 ms, 90 % at  410 ms, overshoot  0.0 deg, peak rate    67 deg/s
  angle_p_gain 100: target  16.6 deg, 63 % at  112 ms, 90 % at  184 ms, overshoot  0.1 deg, peak rate   122 deg/s

Part 1c. Horizon level strength (4.5 defaults: level 75, limit_sticks 75, limit_degrees 135)
 inclination | stick 0.00 | stick 0.25 | stick 0.50 | stick 0.75 |
       0 deg |    0.750   |    0.500   |    0.250   |    0.000   |
      30 deg |    0.583   |    0.389   |    0.194   |    0.000   |
      60 deg |    0.417   |    0.278   |    0.139   |    0.000   |
      90 deg |    0.250   |    0.167   |    0.083   |    0.000   |
     135 deg |    0.000   |    0.000   |    0.000   |    0.000   |
     180 deg |    0.000   |    0.000   |    0.000   |    0.000   |
  horizon_delay_ms 500: after the stick returns to centre, strength reaches 63 % of 0.75 in 500 ms
  angle_earth_ref 100, angle target 10 deg: yaw setpoint x 0.985
  angle_earth_ref 100, angle target 30 deg: yaw setpoint x 0.866
  angle_earth_ref 100, angle target 45 deg: yaw setpoint x 0.707
```

What you see:
- **1a.** Full stick is the same 60°, but half stick is only 16.6°. The “dead” center in Angle is the rates, not `angle_p_gain`. A linear Angle comes from `roll_rc_rate` = `roll_srate`, but that changes ACRO too; a separate rate profile is switched through `adjrange` (bf-adjustments).
- **1b.** `angle_p_gain` 50 is a time constant of about 1/5 s (63 % in 205 ms). Doubling it speeds things up 1.8 times, not 2: the 50 Hz PT3 and the inner loop get in the way. There is no overshoot. The milliseconds are those of the model; the ratios carry over.
- **1c.** This is the chart from the theory. On its back Horizon does not level; after a flip 63 % of the strength builds up in 0.5 s.

### Step 2. Dynamic idle on synthetic RPM
The controller is from `calculateThrottleAndCurrentMotorEndpoints()`, the gains are from `mixerInitProfile()` (PID 8 kHz), the RPM filter is the PT1 `rpm_filter_lpf_hz` 150 Hz (`dshot.c`). The motor is a simplified model: 26000·√u RPM (u is the fraction of the DShot range), an inertia of 40 ms, and in a flat drop the airflow from below takes away 4000 RPM. The scenario: 0–0.3 s armed on the ground (airmode not latched), 0.3–0.8 s a climb at 35 %, throttle to zero, 0.9–1.6 s a flat drop.

```python
# Part 2: dynamic idle controller (flight/mixer.c calculateThrottleAndCurrentMotorEndpoints; mixer_init.c gains)
#         on a synthetic motor (the motor model is NOT from Betaflight, it is a stand-in to close the loop).
PID_HZ = 8000; DT = 1 / PID_HZ
def dyn_idle_gains(min_rpm=30, p=50, i=50, d=50, max_inc=150, start_inc=50):   # mixer_init.c mixerInitProfile
    return dict(min_rps=min_rpm * 100 / 60, P=p * 0.00015, I=i * 0.01 * DT, D=d * 0.0000003 * PID_HZ,
                max_inc=max_inc * 0.001, start_inc=start_inc * 0.001, k_delay=800 * DT / 20)

g = dyn_idle_gains()
print("\nPart 2a. Dynamic idle gains (dyn_idle_min_rpm 30, P/I/D 50, max 150, start 50; PID 8 kHz)")
print(f"  target {g['min_rps']:.1f} rps = {g['min_rps']*60:.0f} rpm; P {g['P']:.4f} /rps; I {g['I']:.3e} /rps per loop;"
      f" D {g['D']:.3f}; limits {g['max_inc']*100:.0f} % (airmode) / {g['start_inc']*100:.0f} % (before airmode)")
for rpm in (2900, 2500, 2000, 1500, 1000):
    err = g['min_rps'] - rpm / 60
    p_term = err * g['P']
    print(f"  slowest motor {rpm:4d} rpm: error {err:5.2f} rps -> P alone {p_term*100:5.2f} % of motor range"
          f" (cap {min(p_term, g['max_inc'])*100:5.2f} %)")

RPM_MAX = 26000.0                          # synthetic motor: rpm_ss = 26000 * sqrt(u) - inflow brake
IDLE = 0.055                               # dshot_idle_value 550 = 5.5 %
def motor_rpm_ss(u, inflow):
    return max(0.0, RPM_MAX * math.sqrt(max(u, 0.0)) - inflow)

def scenario(t):                           # (mixer output of the slowest motor 0..1, inflow brake rpm, airmode latched)
    if t < 0.3: return 0.0, 0.0, False     # armed on the ground, throttle low, airmode not latched
    if t < 0.8: return 0.35, 0.0, True     # take-off and climb (airmode latches above 25 % throttle)
    if 0.9 <= t < 1.6: return 0.0, 4000.0, True   # throttle chop, flat drop: air from below slows the props
    return 0.0, 0.0, True

def run_idle(dyn, T=2.0, g=g, tau_motor=0.040, rpm_lpf_hz=150):
    k_rpm = pt1_gain(rpm_lpf_hz, DT)       # dshot.c motorFreqLpf (rpm_filter_lpf_hz 150)
    rpm = motor_rpm_ss(IDLE, 0); f_rps = rpm / 60; prev = f_rps; I = 0.0; inc = 0.0
    rows = []; t = 0.0; n = 0; lowest = 1e9
    while t < T:
        m, inflow, airmode = scenario(t)
        if dyn:
            max_inc = g['max_inc'] if airmode else g['start_inc']
            min_rps = f_rps
            err = g['min_rps'] - min_rps
            min_rps = prev + g['k_delay'] * (min_rps - prev)          # PT1 delay for D (~20 ms)
            d_term = (prev - min_rps) * g['D']; prev = min_rps
            p_term = err * g['P']
            err = max(-0.1, err)                                      # "I rises fast, falls slowly"
            I = min(max(I + err * g['I'], 0.0), max_inc)
            inc = min(max(p_term + I + d_term, 0.0), max_inc)
            low = 0.0                                                 # motorOutputLow = DSHOT_MIN_THROTTLE
            m = max(m, 0.01)                                          # throttle = MAX(throttle, 0.01)
            u = low + inc * (1 - low) + m * (1 - low - inc * (1 - low))
        else:
            u = IDLE + m * (1 - IDLE)                                 # static idle: floor = dshot_idle_value
            p_term = d_term = 0.0
        rpm += (motor_rpm_ss(u, inflow) - rpm) * DT / tau_motor
        f_rps += k_rpm * (rpm / 60 - f_rps)
        if t > 0.2: lowest = min(lowest, rpm)
        if n % 800 == 0: rows.append((t, rpm, u, inc, p_term, I))
        t += DT; n += 1
    return rows, lowest

print("\nPart 2b. Slowest motor, synthetic flight: ground idle 0-0.3 s, climb 0.3-0.8 s, chop + flat drop 0.9-1.6 s")
st_rows, st_low = run_idle(False)
dy_rows, dy_low = run_idle(True)
print("   t s | static idle 5.5 %: rpm  drive | dynamic idle 30: rpm  drive  increase  P term  I term")
for a, b in zip(st_rows, dy_rows):
    print(f"  {a[0]:4.1f} | {a[1]:21.0f} {a[2]*100:5.1f} % | {b[1]:19.0f} {b[2]*100:5.1f} %  {b[3]*100:6.2f} %"
          f"  {b[4]*100:6.2f} %  {b[5]*100:5.2f} %")
print(f"  lowest rpm after 0.2 s: static idle {st_low:.0f}, dynamic idle {dy_low:.0f} (target 3000)")
```

```text
Part 2a. Dynamic idle gains (dyn_idle_min_rpm 30, P/I/D 50, max 150, start 50; PID 8 kHz)
  target 50.0 rps = 3000 rpm; P 0.0075 /rps; I 6.250e-05 /rps per loop; D 0.120; limits 15 % (airmode) / 5 % (before airmode)
  slowest motor 2900 rpm: error  1.67 rps -> P alone  1.25 % of motor range (cap  1.25 %)
  slowest motor 2500 rpm: error  8.33 rps -> P alone  6.25 % of motor range (cap  6.25 %)
  slowest motor 2000 rpm: error 16.67 rps -> P alone 12.50 % of motor range (cap 12.50 %)
  slowest motor 1500 rpm: error 25.00 rps -> P alone 18.75 % of motor range (cap 15.00 %)
  slowest motor 1000 rpm: error 33.33 rps -> P alone 25.00 % of motor range (cap 15.00 %)

Part 2b. Slowest motor, synthetic flight: ground idle 0-0.3 s, climb 0.3-0.8 s, chop + flat drop 0.9-1.6 s
   t s | static idle 5.5 %: rpm  drive | dynamic idle 30: rpm  drive  increase  P term  I term
   0.0 |                  6098   5.5 % |                6087   1.0 %    0.00 %  -38.72 %   0.00 %
   0.1 |                  6098   5.5 % |                2999   1.3 %    0.30 %    0.00 %   0.00 %
   0.2 |                  6098   5.5 % |                2999   1.3 %    0.34 %    0.01 %   0.32 %
   0.3 |                  6098   5.5 % |                3000   1.3 %    0.33 %    0.00 %   0.33 %
   0.4 |                 15326  38.6 % |               14369  35.0 %    0.00 %  -141.73 %   0.00 %
   0.5 |                 16081  38.6 % |               15299  35.0 %    0.00 %  -153.71 %   0.00 %
   0.6 |                 16143  38.6 % |               15375  35.0 %    0.00 %  -154.69 %   0.00 %
   0.7 |                 16148  38.6 % |               15381  35.0 %    0.00 %  -154.77 %   0.00 %
   0.8 |                 16117   5.5 % |               15342   1.0 %    0.00 %  -154.77 %   0.00 %
   0.9 |                  6904   5.5 % |                3634   1.0 %    0.00 %   -8.42 %   0.00 %
   1.0 |                  2491   5.5 % |                2997   7.3 %    6.32 %    0.04 %   6.26 %
   1.1 |                  2130   5.5 % |                3000   7.2 %    6.31 %    0.00 %   6.31 %
   1.2 |                  2100   5.5 % |                3000   7.2 %    6.31 %    0.00 %   6.31 %
   1.3 |                  2098   5.5 % |                3000   7.2 %    6.31 %    0.00 %   6.31 %
   1.4 |                  2098   5.5 % |                3000   7.2 %    6.31 %    0.00 %   6.31 %
   1.5 |                  2098   5.5 % |                3000   7.2 %    6.31 %    0.00 %   6.31 %
   1.6 |                  2098   5.5 % |                3000   7.2 %    6.31 %    0.00 %   6.31 %
   1.7 |                  5770   5.5 % |                3408   1.7 %    0.71 %   -5.10 %   5.81 %
   1.8 |                  6071   5.5 % |                3371   1.7 %    0.67 %   -4.65 %   5.31 %
   1.9 |                  6095   5.5 % |                3334   1.6 %    0.64 %   -4.19 %   4.81 %
   2.0 |                  6097   5.5 % |                3297   1.6 %    0.60 %   -3.72 %   4.31 %
  lowest rpm after 0.2 s: static idle 2098, dynamic idle 2734 (target 3000)
```

Analysis:
- **2a.** A shortfall of 100 RPM is 1.25 % of thrust from P alone; P alone reaches the 15 % limit (`dyn_idle_max_increase`) at a shortfall of 1200 RPM (the motor at 1800). During a long desync this protects the other motors.
- **2b, ground.** The controller **lowers** the idle: 3000 RPM at 1.3 % of thrust versus 6100 at 5.5 %. Before airmode the increase is no more than 5 %.
- **2b, the drop.** The static idle sags to 2100 RPM, while dynamic idle holds 3000 at the cost of a 6.3 % increase — I holds it, and P at zero error is ≈ 0. The dip to 2734 RPM is the filter delay and the motor inertia.
- **2b, afterwards.** I comes down slowly (−0.1 rev/s in the error), but the negative P cancels the increase at once.

### Step 3. Turtle: what each motor gets
The output was captured on the 4.5 algorithm; in 2025.12 the function is called `applyCrashFlipModeToMotors()`, there is no `crashflip_expo`, the power equals the stick deflection above the 15 % deadband, and full stick gives 2047. A port of `applyFlipOverAfterCrashModeToMotors()` for QUADX (`mixerQuadX`: M1 rear right, M2 front right, M3 rear left, M4 front left), without dynamic idle, `dshot_idle_value` 5.5 % → a lower limit of 157.9.

```python
# Part 3: crash flip motor outputs (flight/mixer.c applyFlipOverAfterCrashModeToMotors, QUADX mixer).
QUADX = [(-1.0, 1.0, -1.0), (-1.0, -1.0, 1.0), (1.0, 1.0, 1.0), (1.0, -1.0, -1.0)]  # roll, pitch, yaw: M1 RR, M2 FR, M3 RL, M4 FL
DSHOT_MIN, DSHOT_MAX = 48, 2047
def crashflip(roll, pitch, yaw, expo=35, motor_pct=0, idle=IDLE, yaw_reversed=False):
    low = DSHOT_MIN + idle * (DSHOT_MAX - DSHOT_MIN)          # motorOutputMin (no dynamic idle)
    rng = DSHOT_MAX - low                                     # motorRangeMax = motorOutputHigh while flipping
    f = 1 - expo / 100
    ex = lambda a: f * a + a ** 3 * (1 - f)
    ap, ar, ay = abs(pitch), abs(roll), abs(yaw)
    sp = 1 if pitch < 0 else -1; sr = 1 if roll < 0 else -1
    sy = (1 if yaw < 0 else -1) * (1 if yaw_reversed else -1)
    length = math.hypot(ap, ar); elen = math.hypot(ex(ap), ex(ar))
    if ay > max(ap, ar):
        length, elen, sr, sp = ay, ex(ay), 0, 0
    else:
        sy = 0
    cosphi = (ap + ar) / (math.sqrt(2) * length) if length > 0 else 0
    if cosphi < math.sqrt(3) / 2:
        if ar > ap: sp = 0
        else: sr = 0
    smin = f * 0.15 + 0.15 ** 3 * (1 - f)                     # CRASH_FLIP_STICK_MINF 0.15
    power = max(0.0, elen - smin) / (1 - smin)
    out = []
    for r, p, y in QUADX:
        v = sp * p + sr * r + sy * y
        if v < 0: v = -v * motor_pct / 100 if motor_pct > 0 else 0
        v = min(1.0, power * v)
        o = low + v * rng
        out.append(0 if o < low + 20 else round(o - 20))      # CRASH_FLIP_DEADBAND 20 -> DSHOT_CMD_MOTOR_STOP
    return out, power

print("\nPart 3. Crash flip DShot outputs (0 = stop; 48..2047 throttle), crashflip_expo 35, dshot_idle_value 5.5 %")
print("  stick (roll, pitch, yaw)       | M1 RR  M2 FR  M3 RL  M4 FL | flip power")
cases = [((0.10, 0, 0), {}), ((0.30, 0, 0), {}), ((0.60, 0, 0), {}), ((1.0, 0, 0), {}), ((0, 1.0, 0), {}),
         ((0, 0, 0.8), {}), ((0.7, 0.7, 0), {}), ((0.6, 0, 0), {"motor_pct": 30}), ((0.6, 0, 0), {"expo": 0})]
for (r, p, y), kw in cases:
    out, pw = crashflip(r, p, y, **kw)
    tag = (" " + ",".join(f"{k}={v}" for k, v in kw.items())) if kw else ""
    print(f"  ({r:4.2f}, {p:4.2f}, {y:4.2f}){tag:15s} | " + "  ".join(f"{o:5d}" for o in out) + f" | {pw:5.3f}")
```

```text
Part 3. Crash flip DShot outputs (0 = stop; 48..2047 throttle), crashflip_expo 35, dshot_idle_value 5.5 %
  stick (roll, pitch, yaw)       | M1 RR  M2 FR  M3 RL  M4 FL | flip power
  (0.10, 0.00, 0.00)                |     0      0      0      0 | 0.000
  (0.30, 0.00, 0.00)                |   360    360      0      0 | 0.117
  (0.60, 0.00, 0.00)                |   907    907      0      0 | 0.407
  (1.00, 0.00, 0.00)                |  2027   2027      0      0 | 1.000
  (0.00, 1.00, 0.00)                |     0   2027      0   2027 | 1.000
  (0.00, 0.00, 0.80)                |     0   1397   1397      0 | 0.666
  (0.70, 0.70, 0.00)                |     0   2027      0      0 | 0.793
  (0.60, 0.00, 0.00) motor_pct=30   |   907    907    369    369 | 0.407
  (0.60, 0.00, 0.00) expo=0         |  1138   1138      0      0 | 0.529
```

What you see: 10 % of stick is in the deadband. Roll right — the right pair, pitch forward — the front pair, a diagonal — M2 alone, yaw — M2+M3. Full stick is 2027 out of 2047, almost full throttle into a jammed prop. `crashflip_motor_percent = 30` spins up the second side at 30 % of the first. `crashflip_expo = 0` gives a power of 0.53 instead of 0.41 at 60 % of stick: expo softens the start of the travel but does not limit the maximum.

### Step 4. Configuration in the CLI (a procedure from the source, not run on hardware)
The line format is `cliAux()` (`cli/cli.c`), the values are from the mode table. An example layout: ARM on AUX1, ANGLE/HORIZON on a three-position AUX2, turtle on AUX3, launch control on AUX4, BEEPER on AUX5, PARALYZE on AUX6.

```text
aux 0 0 0 1700 2100 0 0
aux 1 1 1 1300 1700 0 0
aux 2 2 1 1700 2100 0 0
aux 3 35 2 1700 2100 0 0
aux 4 49 3 1700 2100 0 0
aux 5 13 4 1700 2100 0 0
aux 6 45 5 1700 2100 0 0
set dshot_bidir = ON
set motor_poles = 14
set dyn_idle_min_rpm = 30
set crashflip_motor_percent = 0
set crashflip_rate = 0
set launch_trigger_throttle_percent = 20
save
```

`dyn_idle_*` and `launch_*` are PID profile variables: they are written to the current profile (`profile`), and the other three PID profiles keep the defaults. After `save`, check `get dyn_idle_min_rpm` in every profile you fly with.

### Moving to real hardware
Props are off until item 3. The battery on the bench goes through a smoke stopper. Arm without Betaflight App connected (otherwise the `MSP` flag).

**1. The bench.** The Motors tab, sliders at ~1100: every motor shows RPM, DShot errors < 1 % (or CLI `dshot_telemetry_info`). The Modes tab: each switch highlights only its own mode. Turtle: the turtle switch, then ARM — the OSD shows `> CRASH FLIP <`, and it beeps. Roll right — only the right motors spin, and **in reverse** (a strip of tape on the bell). Disarm, turtle off, ARM — the motors spin forward again. Dynamic idle cannot be checked on the bench: an unloaded motor spins faster than the target even at 1 %. Its check is item 5.

**2. 3D — only without props, with a separate configuration.** The ESC in Bidirectional, `feature 3D`, `save`. Throttle to center, ARM. Up — the motors run forward, down — in reverse, center — idle in the direction the stick came from. Every motor in both directions, by number. ARM off — the motors stop instantly at any throttle. Symmetrical 3D props go on only after this.

**3. Turtle on grass, props on.** The aircraft on its back in the grass, people farther than 10 m. Turtle, ARM, roll toward the flip in bursts of 0.5–1 s; once it has flipped — disarm, turtle off, ARM. Abort: it has not flipped in three bursts (walk); a burning smell or a motor hot to the touch; after the flip the motors spin in reverse (the switch was forgotten — disarm).

**4. Launch control on a level area.** ACRO, the LAUNCH CONTROL switch, ARM — the OSD shows `LAUNCH 0`. With the pitch stick, tilt the aircraft onto its battery by 20–30° and release: the angle holds within ±5° for 5 s, and the motors do not spin up (if they do — `launch_control_gain` is too high). Smoothly add throttle: within 10 % of the threshold the OSD blinks, and above 20 % the aircraft leaves forward in ACRO. Abort: a tumble over the nose (a smaller angle or `launch_angle_limit`), the aircraft creeps along the ground, there is no `LAUNCH` in the OSD (see the conditions in the theory).

**5. Dynamic idle in flight.** `set dyn_idle_min_rpm = 30`, `debug_mode = DYN_IDLE`, Blackbox. Straight up, throttle to zero, a flat drop of 2–3 s. In the log debug[3] (the minimum RPM, rev/s ×10) is no lower than 450 (−10 % of 500), and the sum debug[0] + debug[1] + debug[2] (the P, I and D parts of the increase, ×10000) is less than 1500. There are no pops or dropouts on the exit from the drop.

**Self-check of the hardware part:** turtle on the bench spins the right motors in reverse, and after a disarm the direction is restored; on grass the flip takes ≤ 3 bursts without overheating. Launch control holds the angle for 5 s and starts at the throttle threshold. 3D is checked without props at four points (forward, reverse, center, disarm). The dynamic idle log shows the target being held in a flat drop: debug[3] no lower than 450, the sum debug[0] + debug[1] + debug[2] less than 1500.

Self-check: the lab is complete when:
- **The calculation path (Python):** the three parts of the script have been run, and the outputs match the ones shown. For step 1 you have calculated, for your own rates, the Angle target angle at 25/50/75 % of stick and the Horizon strength at a 45° inclination and 30 % stick. For step 2 you have found the minimum `dyn_idle_min_rpm` target at which the increase in the drop from the scenario hits 15 %, and you have written down why it is that one (the `increase` column shows 15.00 %, and the RPM stays below the target). For step 3 you have calculated the DShot output for your own `crashflip_expo` at 50 % of stick (the 4.5 algorithm) and, next to it, what 2025.12 gives at the same stick.
- **Configuration:** the `aux` lines for your own layout are written from the `permanentId` table, and `get dyn_idle_min_rpm` is checked in all the profiles in use.
- **Hardware:** the self-check of the hardware part above is done.

**Reference for self-check.** Checkpoints with the 4.5 defaults: the Angle target angle at 25/50/75 % of stick — 4.9° / 16.6° / 34.9°; the Horizon strength at a 45° inclination and 30 % stick — 0.300 (between the 30° and 60° rows of table 1c); turtle at 60 % of stick — 907 with `crashflip_expo = 35` and 1138 with 0, so your result for 50 % must be less than these numbers at the same expo. If you got 30° at half stick — a linear Angle (`rc_rate` = `srate`) was calculated, not your rates. If the dynamic idle increase in the drop is greater than 15 % — the `dyn_idle_max_increase` limit is not applied in the model; if it is greater than 5 % on the ground — the limit before airmode was not taken into account. For 2025.12 the correct answer for step 3 is “there is no `crashflip_expo` curve and no subtraction of 20 DShot units”, not the same number.

## diagnostics
- **Symptom:** the FLIP OVER AFTER CRASH mode is not in the Modes tab
  - Possible cause: the motor protocol is not DShot.
  - What to do: DSHOT300/600; without DShot turtle is impossible (in both 4.5 and 2025.12).
- **Symptom:** turtle is on, but on arming the motors spin forward or do not spin
  - Possible cause: the ESC does not execute DShot commands 20/21; the turtle switch was raised after ARM; the stick is in the 15 % deadband.
  - What to do: the order “turtle → ARM”, exit only by a disarm; check on the bench; update the ESC firmware (f-esc-firmware).
- **Symptom:** dynamic idle “does not work” although `dyn_idle_min_rpm` = 30
  - Possible cause: no eRPM (`dshot_bidir = OFF`, an ESC without bidir) — the target is silently zeroed; the value is in another PID profile; `feature 3D`.
  - What you see in the log: debug `DYN_IDLE` [0] is always 0.
  - What to do: `dshot_telemetry_info`, `profile`, `get dyn_idle`.
- **Symptom:** launch control does not engage (no `LAUNCH` in the OSD)
  - Possible cause: stick arming; ANGLE/HORIZON; `feature 3D`; `MOTOR_STOP` without airmode; the start has already happened with `launch_trigger_allow_reset = OFF`.
  - What to do: arm with a switch in ACRO; toggle the mode switch or reboot.
- **Symptom:** 3D does not arm, or editing `3d_deadband_low/high` changes nothing
  - Possible cause: the throttle is outside 1451–1549 µs; `3d_deadband_*` apply only to PWM, and with DShot the split is fixed.
  - What to do: throttle to center; the idle with DShot is `motor_idle` (before 2025.12 — `dshot_idle_value`), and it applies in both directions.
- **Symptom:** Angle is sluggish near stick center, Horizon does not level in steep turns
  - Possible cause: Angle follows the rates (16.6° at half stick by default); Horizon fades toward 75 % of stick and 135°.
  - What to do: raise `roll_rc_rate` or use a separate rate profile; for Horizon — `horizon_limit_sticks` > 100 or `horizon_ignore_sticks = ON`.
- **Symptom:** `set acro_trainer_angle_limit` gives `###ERROR IN set: INVALID NAME`, there is no ACRO TRAINER mode
  - Possible cause: a build without the ACRO_TRAINER option, or no accelerometer.
  - What to do: rebuild in Cloud Build with the option (bf-custom).
- **Symptom:** the camera menu does not open with the sticks
  - Possible cause: the aircraft is armed; STICK COMMANDS DISABLE; the throttle is not within 1350–1650; the camera did not respond at FC startup.
  - What to do: the RunCam Device port and TX↔RX; a larger `rcdevice_init_dev_attempts`; for the joystick — `resource CAMERA_CONTROL` and the `camera_control_internal_resistance` of your camera.
- **Symptom:** it does not arm, the `PARALYZE` flag, the switch is already off
  - Possible cause: the mode is “sticky”.
  - What to do: reboot the FC.

## checklist
- I know the `aux` format (7 fields) and find the `permanentId` in the table, not in `rc_modes.h`
- Turtle: DShot, the order “turtle → ARM”, exit through a disarm; short bursts, heating checked
- I understand `crashflip_motor_percent` from the motor outputs (step 3); I know that `crashflip_expo` exists only in 4.5, and that 2025.12 has `crashflip_rate` and `crashflip_auto_rearm`
- Launch control: the activation conditions and `launch_trigger_allow_reset` for my layout
- 3D: the ESC in Bidirectional, `3d_deadband_*` for PWM only, a check without props
- Acro trainer is in the build, the angle limit is set
- Angle follows the rates; Horizon fades toward 75 % of stick and 135°
- Dynamic idle: bidir DShot works, `dyn_idle_min_rpm` is set in all profiles, and with it `motor_idle` is only the limit of the increase on the ground
- I understand `MOTOR_STOP` without airmode as an exception, not the norm
- Camera control: the camera type is identified (UART or OSD wire), the menu opens while disarmed

## references
- Betaflight pid.c, 4.5-maintenance (pidLevel, calcHorizonLevelStrength, applyAcroTrainer, applyLaunchControl, profile defaults) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/pid.c | primary | A
- Betaflight pid_init.c, 4.5-maintenance (angleGain, horizon*, acroTrainer*, launchControlKi) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/pid_init.c | primary | A
- Betaflight mixer.c, 4.5-maintenance (3D, dynamic idle, crash flip, MOTOR_STOP) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/mixer.c | primary | A
- Betaflight mixer_init.c, 4.5-maintenance (dynamic idle gains, crashflip, launchControlMixer) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/mixer_init.c | primary | A
- Betaflight core.c, 4.5-maintenance (tryArm, disarm, canUseLaunchControl, PARALYZE, 3D) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/fc/core.c | primary | A
- Betaflight msp_box.c, 4.5-maintenance (mode permanentId values, initActiveBoxIds) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/msp/msp_box.c | primary | A
- Betaflight cli/settings.c, 4.5-maintenance (variable names and ranges) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/cli/settings.c | primary | A
- Betaflight dshot.c, 4.5-maintenance (DShot and 3D endpoints, motor RPM) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/drivers/dshot.c | primary | A
- Betaflight rcdevice_cam.c, 4.5-maintenance (camera buttons, menu sticks) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/io/rcdevice_cam.c | primary | A
- Betaflight rc_controls.c, 4.5-maintenance (camera control stick commands, 3D defaults) | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/fc/rc_controls.c | primary | A
- Betaflight mixer.c, tag 2025.12.5 (applyCrashFlipModeToMotors, crashflip_rate, dynamic idle) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/flight/mixer.c | primary | A
- Betaflight core.c, tag 2025.12.5 (crashflip_auto_rearm, FLIP_SWITCH, ALT_HOLD_SW, POS_HOLD_SW) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/fc/core.c | primary | A
- Betaflight cli/settings.c, tag 2025.12.5 (names, defaults and ranges) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/cli/settings.c | primary | A
- Betaflight docs: Dynamic Idle | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/guides/current/Dynamic-Idle.md | primary | A
- Betaflight docs: Launch Control | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/guides/current/Launch-Control.md | primary | A
- Betaflight docs: 3D Setup | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/guides/current/3D-Setup.md | primary | B
- Betaflight docs: Acro Trainer | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/guides/current/Acro-Trainer.md | primary | A
- Betaflight docs: RunCam Device Protocol | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/guides/current/RunCam-Device-Protocol.md | primary | B
- Betaflight docs: FPV Camera Control (joystick emulation) | https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/guides/current/FPV-Camera-Control-Joystick-Emulation.md | primary | B

## notes
Where the documentation disagrees with the source, the module follows the source:
- The Dynamic Idle page says that before airmode the increase is limited to a “fixed 4 %”. In 4.5 it is `dyn_idle_start_increase` = 50, that is 5 %, and in 2025.12 — `motor_idle`, 5.5 % by default. Do not apply the “4.2” section about tuning through `dshot_idle_value` to 4.3+: the value does not act as a floor.
- The 3D Setup page describes `3d_deadband_*` with no caveat about DShot. In the code they are used only in `analogInitEndpoints()`.
- The motor model (step 2) and the inner loop model (step 1) are for teaching. The RPM and millisecond figures on your aircraft will be different, while the controller logic is taken from the firmware line by line.
