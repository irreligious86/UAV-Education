---
id: inav-setup-wing
title: "INAV from scratch: a flying wing"
level: L2
readingTime: 50 min
firmware: INAV 9.1 (checked against 9.1.0)
status: published
added: 2026-11-10
tags:
  - INAV
  - fixed wing
  - setup from scratch
  - SITL
  - servos
related:
  - inav-intro
  - aero-wing
  - inav-gps
  - f-motors-esc
  - link-elrs
next:
  - inav-wing
  - inav-missions
source: content/inav/inav-setup-wing.md
source_hash: 27c6edf8e6e6
---

## summary
One aircraft — a 1.2 m flying wing with a single pusher motor — goes all the way from a blank flight controller to a logged first flight with RTH and a loiter over home. The order is the 17 setup steps of the course. What is already covered in other modules is a one-line action and a link here. Covered in detail is what the course did not have for INAV: servos (direction, center, endpoints, control throws), CG, the airplane motor/ESC, battery calibration, fixed-wing failsafe, autolaunch, the first throw, servo autotrim, fixed-wing autotune, RTH with a loiter and the `diff all` backup. The main path is INAV SITL; the steps that are possible only on hardware are collected in “Moving to real hardware”. The lab: a filled-in servo test table, the CG within the calculated range, a launch log, a recorded RTH loiter and a `diff all`.

## theory
### What the course already has and what this module adds
| Step | Where in detail | What is here |
|---|---|---|
| 1–2 firmware, platform, mixer | inav-intro, inav-wing | the CLI `smix` rules for a flying wing and an airplane |
| 3–5 ports, receiver, channels | link-elrs, link-protocols | the INAV actions: `receiver_type`, the range check |
| 6–8 motor, ESC | f-motors-esc | `motor_pwm_protocol`, PWM ESC calibration, `motorstop_on_low` |
| servos and control surfaces | — | direction, center, endpoints, throws in mm |
| 9 accelerometer, CG | aero-wing | the CG calculation and a check on a balance stand |
| 10 battery | — | `vbat_scale`, `current_meter_scale` with the proportion the right way round |
| 11–12 modes, failsafe | inav-intro, inav-wing | fixed-wing failsafe and its test |
| 13–14 OSD, GPS, RTH | inav-gps, link-vtx | fixed-wing RTH: a loiter instead of a landing |
| 15–17 flight, tuning, backup | inav-wing (briefly) | the throw procedure with abort criteria, autotrim, autotune, `diff all` |

The parallel module inav-setup-scratch takes the same path for a GPS quadcopter; the receiver and the battery are the same there, but here the steps are given in full — a wing needs them with corrections.

### SITL for a wing: what it can do
INAV SITL is the same firmware compiled for a PC; the Configurator has had the SITL tab since 6.1. The UARTs are replaced with TCP ports: UART1 — 5760, UART2 — 5761 and so on; the Configurator connects through “SITL” or TCP `127.0.0.1:5760`. Without a simulator SITL runs in “Configurator only” mode: you can go through the whole configuration (platform, mixer, servos, modes, failsafe, navigation, `diff all`) but not a flight — the sensors take their data from the simulator. For flying a wing the official documents name RealFlight 9.5S/Evolution (suitable for autolaunch and mixers) and X-Plane 11 (the “AR Wing” aircraft from the INAV-X-Plane-HITL project). Both are paid. An X-Plane subtlety: its internal mixer cannot be deactivated, so the documentation says to always select “Aircraft with tail” in INAV, even for a flying wing. In RealFlight the mixers in the model are deleted, and INAV does the mixing. The standard Configurator profile “RealFlight Flying Wing” passes `--chanmap=M01-01,S01-02,S02-03`: motor 1 → simulator channel 1, servos 1 and 2 → channels 2 and 3. The string is derived from the source `tabs/sitl.js`.

What SITL cannot do: bind and the radio link, the direction and ESC of the real motor, servo mechanics (slop, hard stops, throws in mm), CG, voltage and current calibration, a real throw. Those steps are done on hardware.

### Servos in INAV: smix → servo → output
The chain: a rule `smix <n> <servo> <input> <weight> <speed> <lc>` takes an input (0 — stabilized roll, 1 — pitch, 2 — yaw) and multiplies it by the weight (−1000…1000 %); rules with the same servo number are summed. Then `servo <n> <min> <max> <mid> <rate>`: `mid` is the center (1500 µs by default), `min`/`max` limit the travel, `rate` is −125…125 % — a negative one reverses the whole servo. Hence the reversing rule:
- the surface is wrong **on both axes** (both roll and pitch) — reverse the servo: `rate` with a minus sign;
- it is wrong **on one axis** — change the sign of the weight of that axis in `smix` for this servo only.

Reversing on the radio is forbidden: stabilization will go one way and the stick the other. The center is first set mechanically (the servo arm perpendicular to the pushrod, the pushrod adjusted), and only the remainder with `mid`. Servo autotrim moves exactly `mid`; the continuous `feature FW_AUTOTRIM` limits it to 1300–1700 µs, and the SERVO AUTOTRIM mode has no such limit (`servos.c`).

Servo signal and power — three rules (`settings.yaml` 9.1.0):
- **The outputs are enabled.** While `feature PWM_OUTPUT_ENABLE` is off, neither the motor nor the servos get a signal, and a failed output assignment blocks arming with the `PWMOUT` flag (`status` prints the line `PWM output init error` with the reason). Enable it after the output map on the Mixer tab matches the wiring.
- **Rate and filter.** `servo_pwm_rate` = 50 Hz (50–498) is safe for any servo; 330 Hz is only for digital servos rated for it, otherwise an analog servo heats up and buzzes. `servo_lpf_hz` = 20 Hz (0–400, 0 — the filter is off) smooths the command. The rule from the comment in `servos.c`: the cutoff below half of `servo_pwm_rate` — at 50 Hz everything above 25 Hz is distorted anyway; if you raise the servo rate, you can raise the cutoff too. The rate is one for all servos.
- **Power.** A stalled servo draws amps, and the flight controller's BEC also feeds the receiver, the camera and the GPS; a 5 V sag reboots the MCU in the air. The current calculation and the choice of a separate BEC are in `bf-servos-pwm` (the section on servo power is the same for any firmware). The bench check: both servos stalled at the diagonal stick extreme for 10 s — the flight controller does not reboot, the receiver does not lose the link, and the servo rail voltage in the OSD or on a voltmeter does not sag noticeably below the BEC rating.

### Battery calibration: the direction of the proportion
In the source `battery.c` the voltage is proportional to `vbat_scale`, and the current is inversely proportional to `current_meter_scale` (current = microvolts / scale). So:
- `vbat_scale_new = vbat_scale_old × V_multimeter / V_OSD`;
- `current_meter_scale_new = current_meter_scale_old × mAh_FC / mAh_charger` — the formula from `docs/Battery.md`. The flight controller counted less than the charger put in → scale **decreases**.

### Loiter and bank angle
Over home a wing does not hover but loiters with the radius `nav_fw_loiter_radius` (7500 cm by default), and the direction is `fw_loiter_direction` (RIGHT). A coordinated turn needs a bank of tan φ = V²/(g·R). The bank is limited by `nav_fw_bank_angle` (35°). If the required bank is greater, the wing cannot hold the radius and flies a circle wider than the set one.

{{diagram:chart-inav-loiter-bank|At 15 m/s a radius of 75 m requires 17° of bank, and a radius of 30 m — 37°: that is more than nav_fw_bank_angle = 35°, and the circle will come out wider than set. Reduce the radius only together with the speed.}}

{{diagram:inav-wing-setup-flow|Seven of the fourteen blocks are done in SITL; servos, CG, battery, the throw and autotune — only on hardware, and the prop goes on only after the failsafe test and the control surface direction test.}}

### Place in the system

- **Receives:** the calculated position of the center of gravity (`aero-wing`); the receiver and channels (`link-elrs`); the motor and ESC (`f-motors-esc`); the modes, autolaunch and fixed-wing failsafe (`inav-wing`).
- **Provides:** verified directions, centers and throws of the control surfaces — to stabilization and autolaunch (`inav-wing`); a calibrated battery; the loiter radius and bank — to fixed-wing RTH (`inav-gps`); a `diff all`.
- **If you get it wrong here:** a servo is reversed on the radio and not in `servo` or `smix` → the stick works correctly, but stabilization deflects the surface the opposite way: a reversed elevon ends the flight in the first second of the launch (`inav-wing`); the same rule and the same two checks for ArduPlane are in `ap-setup-plane`. A loiter radius smaller than `nav_fw_bank_angle` allows at this speed → the circle over home comes out wider than set (`inav-gps`).

## practice
### Step 1. Firmware, backup and starting SITL
On hardware: before flashing save the `diff all` of the old firmware to a file (if it ran INAV or Betaflight), flash the target of your board with Full chip erase, with a Configurator of the same major version as the firmware. In SITL: the SITL tab → the profile “[Standard] Configurator” (in Configurator 8.x its name had a typo — “Confgurator”) → Start → Connect. The console message from the SITL.md documentation (not run here):

```
INAV 6.1.0 SITL
[SYSTEM] Init...
[SIM] No interface specified. Configurator only.
[EEPROM] Loaded 'eeprom.bin' (32768 of 32768 bytes)
[SOCKET] Bind TCP :: port 5760 to UART1
[SOCKET] Bind TCP :: port 5761 to UART2
[SOCKET] ::1 connected to UART1
```

For flight — the profile “[Standard] RealFlight Flying Wing” (RealFlight with RealFlight Link enabled) or X-Plane with the “AR Wing” aircraft.

### Step 2. Platform and mixer
The Mixer tab: the Airplane platform, the “Flying Wing” preset, Load and apply. The same result in the CLI — the preset rules from `js/model.js` of Configurator 9.1.0 (the same in 8.0.1):

```
set platform_type = AIRPLANE
mmix reset
mmix 0 1.0 0.0 0.0 0.0
smix reset
smix 0 1 0 50 0 -1
smix 1 1 1 50 0 -1
smix 2 2 0 -50 0 -1
smix 3 2 1 50 0 -1
save
```

Elevon 1 gets +50 % roll and +50 % pitch, elevon 2 — −50 % roll and +50 % pitch: with full roll and full pitch the sum does not exceed 100 %. For an airplane with a tail the preset is “Airplane”: the elevator is 100 % pitch (servo 1), the ailerons are 100 % roll on servos 2 and 3, the rudder is 100 % yaw (servo 4). Check on the Mixer diagram which output the servo physically needs: in INAV 7+ the outputs of one timer must have the same function, and `timer_output_mode` switches a whole timer to AUTO, MOTORS, SERVOS or LED (an output for an LED strip).

### Step 3. Ports
Ports: the receiver's UART → Serial RX, the GPS UART → GPS, with digital video — MSP DisplayPort. In SITL UART1 and UART2 are already taken by MSP; a receiver on a USB adapter goes to UART3 by default (the profile's `serialUart: 3`).

### Step 4. Receiver and channels (hardware or an adapter only)
`receiver_type = SERIAL`, `serialrx_provider = CRSF` for ELRS, bind — per the link-elrs module. The Receiver tab: roll, pitch, yaw, throttle — 1000…2000 ± 10 µs at the extremes, center 1500 ± 5. A channel outside `rx_min_usec` (885) / `rx_max_usec` (2115) is considered lost. On signal loss the receiver must stop sending channels (“no pulses” mode), not hold the last values.

### Step 5. Motor and ESC (bench, no prop)
An airplane ESC with ordinary PWM — `motor_pwm_protocol = STANDARD`; BLHeli_S/AM32 — `DSHOT300`. The default is `ONESHOT125`, and many airplane ESCs do not understand it. Only PWM/OneShot ESCs need calibration: remove the prop, enable motor control on the Outputs tab, the Master slider to maximum, connect the battery, after the ESC tones lower the slider to minimum. Check `get motorstop_on_low` and `get throttle_idle`: in 9.1 the defaults are ON and 8 % (unchanged since 8.0; in 7.1.2 — OFF and 15 %). ON is convenient for a wing: at minimum throttle the motor is stopped, and your fingers are safe during the throw. Check the direction with a strip of paper behind the motor: at low throttle the airflow goes backward, away from the wing. If not — swap any two motor wires (or enable reverse in the ESC).

### Step 6. Servos: direction, center, endpoints, throws
The test is in MANUAL (no stabilization), then in ANGLE. Before that set the mechanical center: all servos at 1500 in Outputs, the servo arms perpendicular to the pushrods. Then fill in the table (this is the first artifact of the lab):

| Input | Left elevon | Right elevon | Result |
|---|---|---|---|
| roll stick right | down | up | ✓ / reversed |
| pitch stick back | up | up | ✓ / reversed |
| ANGLE, roll the wing right | up | down | ✓ / reversed |
| ANGLE, lower the nose | up | up | ✓ / reversed |

The last two rows check stabilization: the surfaces must oppose the tilt. Endpoints: give full roll plus full pitch and adjust `min`/`max` so that the servo does not hit a stop (it buzzes under load — so it is stalled), for example `servo 2 1100 1900 1500 -100`. Measure the throws with a ruler at the trailing edge of the elevon: h = c·sin δ. The calculation for an elevon with a 60 mm chord (actual script output):

```
elevon  8 deg -> 8.4 mm at trailing edge
elevon 12 deg -> 12.5 mm at trailing edge
elevon 15 deg -> 15.5 mm at trailing edge
```

Take the throws from the wing's manual; if there is none, the guideline for the first flight is ±12° in roll. Reduce them through `manual_roll_rate`/`manual_pitch_rate` for MANUAL and through `roll_rate`/`pitch_rate` for the stabilized modes. Do not cut `min`/`max` instead of the throws: then the sum of roll and pitch gets clipped.

### Step 7. Accelerometer, board alignment and CG
Accelerometer calibration — 6 positions (inav-intro). Board alignment: on the Status tab the model must follow the tilts of the wing; if the board is mounted rotated, you need `align_board_yaw` (decidegrees, 900 = 90°). Put the wing in its flight attitude per the manual: roll and pitch on Status are 0 ± 1°. The level-flight pitch in ANGLE is later adjusted with `fw_level_pitch_trim` (degrees, + = nose higher).

The CG is calculated from the geometry (the formulas are in the aero-wing module). The wing: span 1.20 m, root chord 280 mm, tip chord 170 mm, the tip leading edge 200 mm behind the root one. The script `wing_setup.py` (actual script output):

```
CG at 15% MAC: 126 mm from root LE
CG at 18% MAC: 133 mm from root LE
CG at 20% MAC: 138 mm from root LE
MAC = 229 mm at y = 276 mm, MAC LE = 92 mm behind root LE
```

Mark 126–138 mm on the root chord and aim for 133 mm. Balance with the battery, GPS and camera installed; the forward end of the range is safer for the first flight.

### Step 8. Battery
A 4S2P Li-Ion 21700 pack, 6000 mAh:

```
set bat_cells = 4
set vbat_max_cell_voltage = 420
set vbat_warning_cell_voltage = 330
set vbat_min_cell_voltage = 300
set battery_capacity = 6000
set battery_capacity_warning = 1500
set battery_capacity_critical = 900
```

The calibration is done on hardware (Moving, B4). An example with the numbers from the script: multimeter 16.42 V, OSD 16.08 V, the old `vbat_scale` 1100 → 1100 × 16.42 / 16.08 = **1123**. After the flight the flight controller counted 2860 mAh, the charger put in 3180 → 250 × 2860 / 3180 = **225**.

### Step 9. Modes and arming
Modes (SITL verifies the assignments): ARM — a separate two-position switch; MANUAL — a separate switch, always available; a three-position switch — ANGLE / NAV CRUISE / NAV RTH; NAV LAUNCH — a separate switch (or `feature FW_LAUNCH`, and then the launch is enabled on every arm); AUTO TUNE and SERVO AUTOTRIM — on a free channel (SERVO AUTOTRIM appears in the list only without `feature FW_AUTOTRIM`). Look up the reason for an arming block in `status` (inav-intro).

### Step 10. Failsafe
```
set failsafe_procedure = RTH
set failsafe_delay = 5
set failsafe_throttle_low_delay = 0
set failsafe_fw_roll_angle = -200
set failsafe_fw_pitch_angle = 100
set failsafe_fw_yaw_rate = -45
```

`failsafe_delay` is in tenths of a second: 5 = 0.5 s (the firmware adds a fixed 200 ms, so failsafe activates 0.7 s after the last valid frame). `failsafe_throttle_low_delay = 0` is mandatory for a wing: otherwise in a glide at zero throttle failsafe decides that the aircraft is on the ground and simply disarms it in the air (Failsafe.md). The last three lines are the default values for the LAND spiral (without GPS RTH turns into an emergency landing): −20° of bank to the left, a 10° dive, −45 °/s. They are written out explicitly so that they get into `diff all` as a deliberate decision. In SITL with a simulator failsafe is triggered with the FAILSAFE mode switch. On hardware — by turning the radio off (B6).

### Step 11. OSD, GPS, RTH and the loiter
GPS and compass — inav-gps; OSD — inav-intro and link-vtx (the minimum: voltage, mAh, satellites, the distance and arrow to home, the mode, throttle). Fixed-wing RTH:

```
set nav_rth_alt_mode = AT_LEAST
set nav_rth_altitude = 5000
set nav_rth_climb_first = ON
set nav_rth_allow_landing = NEVER
set nav_fw_loiter_radius = 6000
set fw_loiter_direction = RIGHT
```

`NEVER` — over home the wing loiters and does not land. You land by hand. The same prohibition also turns off the `fwapproach` landing: even with a filled-in slot the wing stays in the circle (`inav-geozones-landing`). A radius of 60 m at a 15 m/s cruise requires 20.9° of bank (tan φ = 225 / (9.81·60)) — there is margin to 35° even in wind.

### Step 12. Autolaunch
The default values are covered in inav-wing. For a 1.2 m, 1.6 kg wing:

```
set nav_fw_launch_thr = 1700
set nav_fw_launch_motor_delay = 500
set nav_fw_launch_climb_angle = 18
set nav_fw_launch_timeout = 5000
set nav_fw_launch_max_altitude = 3000
set nav_fw_launch_max_angle = 45
save
```

The 500 ms delay — the propeller of a pusher wing starts when the hand is already behind. `nav_fw_launch_max_altitude = 3000` ends the launch at 30 m. In RealFlight SITL practice the throw itself: arm in NAV LAUNCH, throw, climb, exit to ANGLE with the sticks.

### Step 13. Backup of the SITL part
`diff all` in the CLI → the file `inav-wing-sitl.txt`. Check that it has `mixer_profile 1` with `platform_type` and `smix`, the `servo` block, `failsafe_*`, `nav_fw_*`. This is the template for hardware: move it to the board and recalibrate the sensors, the battery and the servos.

### Moving to real hardware
Safety: the prop stays off until F2. Connect the battery only while holding the wing; wear safety glasses when working with the motor.

**Bench, no prop**
- **B1. Bind and channels.** Step 4. Write down the extreme and center values of the four channels.
- **B2. Motor.** Protocol, PWM ESC calibration, direction with a strip of paper (step 5). Write down the throttle at which the motor starts spinning reliably.
- **B3. Servos.** The whole table of step 6, endpoints without stalling, throws with a ruler in mm (±1 mm from the calculated ones).
- **B4. Battery.** A multimeter on the balance lead or on the XT60 under the pack, with the flight controller powered from it: `vbat_scale` by the formula, repeat until the error is < 0.05 V per cell (< 0.2 V on 4S). Current: fly until you have used more than 50 % of the capacity, then compare the OSD mAh with the charger's, recalculate `current_meter_scale` and repeat until the difference is < 5 %. Without a current sensor — `current_meter_type = VIRTUAL` per Battery.md.
- **B5. CG.** The wing on your fingers at the points 133 mm from the root leading edge: it hangs level or slightly nose down. Write down the actual point.
- **B6. Failsafe.** Arm in ANGLE, throttle 30 %, turn the radio off: after about 0.7–0.8 s the OSD shows FAILSAFE. Without a GPS fix this is the LAND spiral (surfaces: roll left, nose down). With a fix it is RTH. Turn the radio on, move the sticks — control is back. If arming without a fix is blocked by the navigation check (`nav_extra_arming_safety`), do the test outdoors after the fix.
- **B7. Autolaunch on the ground.** NAV LAUNCH, arm, the wing in your hand, a sharp forward movement: after 0.5 s the motor goes to the launch throttle (visible in the OSD and in Outputs).
- **B8. Estimator.** Compass and GPS per the inav-intro table (step 3b): a 3D fix, ≥ 10 satellites, HDOP ≤ 2, home recorded.

**Field**
- **F1. Preflight check.** Control surfaces per the table (MANUAL and ANGLE), the battery full, the CG, the prop tight, the failsafe procedure in the OSD, wind ≤ 5 m/s, the throw into the wind, a site with no people in the direction of the throw.
- **F2. First throw.** The prop goes on now. ANGLE + NAV LAUNCH, arm, a firm level throw with the nose slightly up. Abort criteria: in the first 2 s the wing banks more than 45° or dives — MANUAL at once, throttle to zero, glide straight ahead. It does not climb within 5 s at full throttle — throttle to zero, land and check the CG and the throws. After climbing 30–50 m — a circuit in ANGLE at a quarter throttle.
- **F3. Servo autotrim.** Straight and level flight in ANGLE. Activate SERVO AUTOTRIM and hold for 2 s (the firmware averages the servo outputs, per `servos.c`), leave the switch on, land, disarm — the new `mid` values are saved. If you turn the switch off before disarming, the old centers come back. The alternative is `feature FW_AUTOTRIM`: continuous trimming in level flight outside MANUAL, saved on disarm; in 9.1 it moves the center only while the I-term is stable (it does not trim in turbulence or in a turn).
- **F4. Autotune.** At an altitude of ≥ 50 m activate AUTO TUNE on top of ANGLE and for 3–5 minutes give sharp full deflections on one axis at a time. Do not land in AUTO TUNE. The source `pid_autotune.c` 9.1.0 changes only FF and the rates and does not touch P and I (the code is the same in 8.0.1, but the documentation still promised PIFF; it was corrected in 9.1). The rates change only in ACRO/HORIZON and only if `fw_autotune_rate_adjustment` is not FIXED; in ANGLE only FF is tuned. Save after disarming with the stick command (throttle low, yaw left, pitch down, roll right). Write down `fw_ff_roll`, `fw_ff_pitch` and the rates before and after.
- **F5. RTH and the loiter.** Fly 200–300 m away at an altitude of 40 m and activate NAV RTH: the wing climbs to 50 m, turns around and loiters over home. Measure the radius on the OSD (the distance to home oscillates around 60 m). Then once — a failsafe by turning the radio off at 300 m: RTH must activate by itself.
- **F6. Backup.** Download the blackbox log, take a `diff all` after autotune and autotrim, and save both next to the servo table.

What you should get: a servo table without a single reversal in the result column; the CG within 126–138 mm; a voltage error < 0.05 V/cell; mAh within 5 % of the charger; the launch log shows the throw, the 0.5 s delay and the throttle going to 1700; an RTH loiter with a radius of 60 ± 15 m.

Self-check: the lab is done when:
- **SITL:** the file `inav-wing-sitl.txt` holds a `diff all` with `platform_type = AIRPLANE`, four `smix` rules, `failsafe_procedure = RTH`, `failsafe_throttle_low_delay = 0`, `nav_rth_allow_landing = NEVER` and the autolaunch settings; the CG (15–20 % MAC) and the throws in mm are calculated — for the wing from the example these are 126–138 mm and 8.4 / 12.5 / 15.5 mm for 8° / 12° / 15°; if you have RealFlight/X-Plane, an autolaunch log and a recording of the loiter over home are saved;
- **hardware:** the servo test table is filled in, and the result column has no reversals; the CG is marked and lies within the calculated range; voltage < 0.05 V/cell and mAh < 5 % after calibration; the bench failsafe test is recorded (FAILSAFE in the OSD after about 0.7–0.8 s); next to the servo table are saved the blackbox log of the first throw with autolaunch (it shows the throw, the 0.5 s delay and throttle 1700), the log of RTH with a loiter radius of 60 ± 15 m and the final `diff all` after autotune/autotrim.

**Reference for the self-check.** The servo table is right when in ANGLE the surfaces oppose the tilt: the wing rolled right — the left elevon up, the right down; the nose lowered — both up. The sticks work correctly but stabilization deflects the surface the opposite way — the reverse was done on the radio, not in `servo` or `smix`. The CG from your calculation for the wing from the example came out outside 126–138 mm — check that you measure from the leading edge of the root chord and that the 92 mm MAC offset is included. The wing disarms in the air in a glide at zero throttle — `failsafe_throttle_low_delay` is not 0. The distance to home in RTH does not oscillate around 60 m but drops to zero with a landing — `nav_rth_allow_landing` is not `NEVER`.

## diagnostics
- **Symptom:** on the throw the wing flips over at once
  - Possible cause: one elevon is reversed in roll, or stabilization helps the tilt.
  - What to do: go through the table of step 6 again, especially the ANGLE rows; reverse in `smix`/`servo`, not on the radio.
- **Symptom:** the motor does not spin on the Outputs tab, the ESC beeps in a loop
  - Possible cause: the ESC does not understand `ONESHOT125` (the default value) or is not calibrated.
  - What to do: `motor_pwm_protocol = STANDARD`, calibration per step 5.
- **Symptom:** a servo buzzes and heats up on the ground
  - Possible cause: it stalls on the sum of roll and pitch, `min`/`max` are wider than the mechanics; `servo_pwm_rate` is higher than an analog servo can take.
  - What to do: narrow `min`/`max`, check with full diagonal sticks; set `servo_pwm_rate = 50` back.
- **Symptom:** it does not arm, `status` has the `ROLL/PITCH` flag
  - Possible cause: NAV LAUNCH is enabled (by a switch or by `feature FW_LAUNCH`), and the roll or pitch stick is not centered — this includes subtrim or radio trims that shift the center (`fc_core.c`).
  - What to do: release the sticks; the centers on the Receiver tab are 1500 ± 5; radio trims to zero, trimming is done with the servos.
- **Symptom:** the servos and the motor do not respond either in MANUAL or on the Outputs tab, `status` has the `PWMOUT` flag or the outputs are silent without a flag
  - Possible cause: `feature PWM_OUTPUT_ENABLE` is off; a servo is on an output of a motor timer.
  - What to do: `feature PWM_OUTPUT_ENABLE`, `save`; the timer map and `timer_output_mode` — step 2 and `inav-mixer-vtol`.
- **Symptom:** after autotrim the wing flies worse
  - Possible cause: trimming in a turn or in turbulence; the CG is far from the calculated one, and autotrim compensates for it with the surfaces.
  - What to do: restore `mid` from `diff all`, check the CG, repeat in calm air.
- **Symptom:** during a glide at zero throttle the wing disarmed on a link loss
  - Possible cause: `failsafe_throttle_low_delay` is not 0.
  - What to do: `set failsafe_throttle_low_delay = 0`.
- **Symptom:** in RTH the wing flies a circle noticeably larger than `nav_fw_loiter_radius`
  - Possible cause: the required bank is greater than `nav_fw_bank_angle` (a small radius at a high speed, or wind).
  - What to do: a larger radius or a slower cruise; tan φ = V²/(g·R).
  - In the log: the bank sits at the 35° limit, the distance to home is greater than set.
- **Symptom:** the mAh in the OSD differs from the charger by 10–15 %
  - Possible cause: `current_meter_scale` was calculated with the proportion inverted.
  - What to do: scale × mAh_FC / mAh_charger; if the FC counted less — scale decreases.
- **Symptom:** SITL starts but nothing flies
  - Possible cause: “Configurator only” mode — the simulator is not selected or not connected.
  - What to do: the RealFlight/X-Plane profile, RealFlight Link enabled, the chanmap matches the mixer.

## references
- INAV Settings reference (Settings.md) | https://github.com/iNavFlight/inav/blob/master/docs/Settings.md | primary | A
- INAV SITL | https://github.com/iNavFlight/inav/blob/master/docs/SITL/SITL.md | primary | A
- INAV SITL with RealFlight | https://github.com/iNavFlight/inav/blob/master/docs/SITL/RealFlight.md | primary | A
- INAV Mixer and platform type | https://github.com/iNavFlight/inav/blob/master/docs/Mixer.md | primary | A
- INAV Servo configuration | https://github.com/iNavFlight/inav/blob/master/docs/Servo.md | primary | A
- INAV Battery monitoring | https://github.com/iNavFlight/inav/blob/master/docs/Battery.md | primary | A
- INAV Failsafe | https://github.com/iNavFlight/inav/blob/master/docs/Failsafe.md | primary | A
- INAV Airplane Autotune | https://github.com/iNavFlight/inav/blob/master/docs/Autotune%20-%20fixedwing.md | primary | A
- INAV source: servo autotrim (servos.c) | https://github.com/iNavFlight/inav/blob/master/src/main/flight/servos.c | primary | A
- INAV source: fixed-wing autotune (pid_autotune.c) | https://github.com/iNavFlight/inav/blob/master/src/main/flight/pid_autotune.c | primary | A
- INAV source: battery scaling (battery.c) | https://github.com/iNavFlight/inav/blob/master/src/main/sensors/battery.c | primary | A
- INAV Configurator: SITL profiles (tabs/sitl.js) | https://github.com/iNavFlight/inav-configurator/blob/master/tabs/sitl.js | primary | A

## checklist
- `platform_type = AIRPLANE`, the `smix` rules match the preset, reverses are done in INAV, not on the radio
- The servo table is filled in for MANUAL and ANGLE, the servos do not stall, the throws are measured in mm
- The CG is calculated and set at 15–20 % MAC
- `vbat_scale` and `current_meter_scale` are calibrated with the proportion the right way round
- `failsafe_procedure = RTH`, `failsafe_throttle_low_delay = 0`, failsafe is tested by turning the radio off
- Autolaunch is tested without the prop, the first throw is made with abort criteria set in advance
- Autotrim and autotune are saved after disarm, the `diff all` and the logs are kept together
