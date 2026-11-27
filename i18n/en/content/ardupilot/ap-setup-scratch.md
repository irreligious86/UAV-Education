---
id: ap-setup-scratch
title: "ArduPilot from scratch: Copter with Mission Planner / QGC"
level: L2
readingTime: 55 min
firmware: ArduCopter 4.7 (checked against 4.7.3; SITL outputs captured on Copter-4.6.3)
status: published
tags:
  - ArduPilot
  - setup from scratch
  - calibration
  - Mission Planner
  - SITL
related:
  - ap-intro
  - ap-sitl
  - ap-safety-fs
  - ap-tuning
  - ap-logs
  - ap-ekf
  - link-elrs
  - f-motors-esc
next:
  - ap-tuning
source: content/ardupilot/ap-setup-scratch.md
source_hash: bb173bde0618
---

## summary
One quadcopter, from a blank flight controller to a logged first hover, in a 17-step setup order: firmware with bootloader, the `SERIALn_PROTOCOL` port map, an ELRS receiver (`SERIALn_PROTOCOL = 23`, `RC_PROTOCOLS`), radio calibration, DShot or PWM with ESC calibration, Motor Test and `MOT_SPIN_ARM/MIN`, accelerometer and compass, battery monitor calibration against a multimeter and a charger, OSD, failsafe, a Stabilize → AltHold → Loiter hover, `MOT_THST_HOVER`, QuikTune/AutoTune, and a `.param` backup. The main path runs in SITL (`sim_vehicle.py`; parameter names are for Copter 4.7.2, outputs were captured on Copter-4.6.3); the steps that do not exist in the simulator are done on the bench with props off and in the field. The lab: a `.param` before and after, a hover log with `MOT_THST_HOVER` at 0.2–0.5, and logged RC and battery failsafes.

## theory
### The vehicle we use
The example for the whole module: an X quad on 7" props, 1.4 kg, a 6S LiPo of 4000 mAh, an H7 flight controller with a barometer and an SD card, a 4-in-1 ESC running BLHeli32/AM32, an ELRS receiver, a GPS with a compass on a mast, analog video. A 2806.5 motor with a 7×3.5 prop gives about 1200 g of thrust (module f-aero-props), T/W ≈ 4 × 1.2 / 1.4 = 3.4, and the expected hover throttle is `MOT_THST_HOVER` ≈ 1/3.4 ≈ 0.29.

Version: ArduCopter 4.7 (checked against the 4.7.2 source and parameters). Names that differ from 4.6 (the full table is in module ap-intro): `ARMING_SKIPCHK` (before 4.7 it was `ARMING_CHECK`, with the opposite meaning), `RTL_ALT_M` in meters (before 4.7 it was `RTL_ALT` in centimeters), `PSC_D_ACC_P/I` (before 4.7 they were `PSC_ACCZ_P/I`, with values 10 times larger). The SITL outputs in the practice section were captured on Copter-4.6.3 and are left unedited.

### The 17 steps and where each one is done
| # | Step | What it is in ArduCopter 4.7 | Where | Details |
|---|---|---|---|---|
| 1 | Firmware, backup | `_with_bl.hex` over DFU, then `.apj`; a `.param` before any change | bench, SITL | this module |
| 2 | Frame, orientation | `FRAME_CLASS`, `FRAME_TYPE`, `AHRS_ORIENTATION` | SITL | ap-intro |
| 3 | Ports | `SERIALn_PROTOCOL`: 2 MAVLink2, 5 GPS, 23 RCIN, 16 ESC Telemetry, 42 DisplayPort | SITL | this module |
| 4 | Receiver | `SERIALn_PROTOCOL = 23`, `RC_PROTOCOLS`, `RC_OPTIONS`, `RSSI_TYPE = 3`, bind | bench | link-elrs |
| 5 | Channels | `RCMAP_*`, calibration of `RCn_MIN/MAX/TRIM` | bench | this module |
| 6 | Motor protocol | `MOT_PWM_TYPE`, `SERVO_DSHOT_ESC`, `SERVO_BLH_*` | SITL, bench | f-motors-esc |
| 7 | Order, direction | Motor Test A–D, `SERVO_BLH_RVMASK` | SITL, bench | this module |
| 8 | ESCs, idle | `ESC_CALIBRATION` (PWM only), `MOT_SPIN_ARM/MIN` | bench | this module |
| 9 | Accel, compass | 6 positions, Onboard Mag Calibration | bench (SITL) | ap-ekf |
| 10 | Battery monitor | `BATT_MONITOR`, `BATT_VOLT_MULT`, `BATT_AMP_PERVLT`, `BATT_AMP_OFFSET` | SITL, bench | this module |
| 11 | Modes, arming | `FLTMODE_CH`, `FLTMODE1..6`, `RCx_OPTION`, pre-arm | SITL | ap-intro |
| 12 | Failsafe | `FS_THR_ENABLE/VALUE`, `BATT_FS_LOW_ACT/CRT_ACT` | SITL, bench | ap-safety-fs |
| 13 | OSD | `OSD_TYPE`: 1 MAX7456, 5 MSP DisplayPort | bench | this module |
| 14 | GPS, home, RTL | `GPS1_TYPE`, `RTL_ALT_M` | SITL | ap-ekf |
| 15 | First hover | Stabilize → AltHold → Loiter, `MOT_HOVER_LEARN = 2` | SITL → field | this module |
| 16 | First tune | notch, QuikTune or AutoTune | field | ap-tuning |
| 17 | Log and backup | `.BIN`, `.param`, file comparison | SITL, field | ap-logs |

{{diagram:ap-setup-flow|The 17 setup steps of ArduCopter 4.7: SITL covers more than half of the chain, while bind, radio and ESC calibration, OSD and tuning exist only on hardware, and the props go on only at step 15.}}

### The bootloader and the two file formats
ArduPilot on ChibiOS is installed in two stages. The first time, the board has no ArduPilot bootloader (it runs Betaflight or factory firmware), so you write `arducopter_with_bl.hex`, the bootloader plus the firmware, over DFU: hold BOOT, plug in USB, use STM32CubeProgrammer. A `.apj` file cannot be flashed this way: only the ArduPilot bootloader understands it. Every later update is a `.apj` loaded with Mission Planner (Install Firmware or Load custom firmware) or QGroundControl (Vehicle Setup → Firmware; plug the board in after you open the tab). The files are on firmware.ardupilot.org in the folder Copter → stable (or stable-4.7.2) → the board name, which matches its hwdef. The STM32 DFU bootloader is in ROM, so you can go back to Betaflight with the same DFU procedure; before you flash, save `diff all` from the Betaflight CLI.

### Calibrations that are plain formulas
The analog battery monitor in `AP_BattMonitor_Analog.cpp`: V = (V_pin − `BATT_VLT_OFFSET`) × `BATT_VOLT_MULT`, I = (V_pin − `BATT_AMP_OFFSET`) × `BATT_AMP_PERVLT`. It follows that:

- new `BATT_VOLT_MULT` = old × V_multimeter / V_GCS;
- new `BATT_AMP_OFFSET` = old + I₀ / `BATT_AMP_PERVLT`, where I₀ is the reading at zero current;
- new `BATT_AMP_PERVLT` = old × I_clamp / I_GCS = old × mAh_charger / mAh_flight_controller.

Zero first, slope second: a scale fitted with a wrong zero is correct at one point only.

{{diagram:chart-ap-batt-cal|Worked example: the sensor actually outputs 0.0125 V + I/44 A/V. With the stock 0 V and 40 A/V the GCS shows 0.50 A at rest and 9.59 A at 10 A on the clamp meter; an offset of 0.0125 V removes the zero error (9.09 A), and the scale 40 × 10/9.09 = 44 gives an exact 10.0 A.}}

Motors: output = `MOT_SPIN_MIN` + (`MOT_SPIN_MAX` − `MOT_SPIN_MIN`) × r, where r is the thrust after the `MOT_THST_EXPO` linearization; PWM = `MOT_PWM_MIN` + output × (`MOT_PWM_MAX` − `MOT_PWM_MIN`). `MOT_THST_HOVER` (0.125–0.6875, default 0.35) is the motor thrust needed to hover as a fraction of the maximum, so it is ≈ 1 / (T/W). A value of 0.2–0.5 corresponds to a T/W from 5 down to 2: below that the throttle is too twitchy, above it there is no margin for maneuvers and wind.

### Why it will not arm: `ARMING_SKIPCHK` and the PreArm messages
While the vehicle is disarmed, the firmware runs the pre-arm checks once a second, and at the moment of the arm command it runs them again together with the final arming checks. The reason for a refusal arrives as text in a STATUSTEXT message (`AP_Arming.cpp`, `check_failed`). The prefix tells you when, not what: `PreArm:` is the background run, and the text repeats once every 30 s, or immediately if the checks have just started failing, but no sooner than 4 s after the previous display; `Arm:` is the same text in response to an arming attempt, plus the final checks that do not run in the background (throttle, lean angle, mode, duplicate `RCx_OPTION`). So a message listed below as `PreArm: X` arrives as `Arm: X` on an arming attempt. Mission Planner shows the text on the HUD and in the Messages tab, QGC in its message window. No parameter reports the reason: `ARMING_SKIPCHK` only selects which groups of checks to skip.

`ARMING_SKIPCHK` (since 4.7, default 0, skip nothing) is a bitmask of the groups **to skip**. 4.6 had `ARMING_CHECK` with the opposite meaning: a mask of checks to perform, 1 = all. On the first boot of 4.7 the firmware converts the old value itself (`AP_Arming::init`): `ARMING_CHECK = 1` (and any value with bit 0 set) → 0, `ARMING_CHECK = 0` → −1, any other mask → its inverse over bits 1–20.

| Bit | Value | Group (name in the GCS) | What it checks |
|---|---|---|---|
| 1 | 2 | Barometer | baro health; on Copter also the difference between baro and EKF altitude (`Altitude disparity`) |
| 2 | 4 | Compass | health, calibration, offsets, field strength, consistency between compasses |
| 3 | 8 | GPS lock | fix, HDOP, consistency of the receivers with each other and with the AHRS, home position |
| 4 | 16 | INS | gyros and accelerometers: health, calibration, consistency; lean angle at the moment of arming |
| 5 | 32 | Parameters | conflicting parameters: `FS_THR_VALUE`, `FRAME_CLASS`, `PILOT_SPD_UP`, `PSC`/`ATC` |
| 6 | 64 | RC Channels | RC present, calibration, throttle above the failsafe threshold; at arming, throttle low and duplicate `RCx_OPTION` |
| 7 | 128 | Board voltage | board supply from `BRD_VBUS_MIN` (4.3 V) to 5.8 V |
| 8 | 256 | Battery Level | monitor healthy, voltage and capacity above `BATT_ARM_VOLT/MAH` and the failsafe thresholds |
| 9 | 512 | Airspeed | ArduPlane only; the Copter description has no such bit |
| 10 | 1024 | Logging Available | the log is being written, an SD card is present |
| 11 | 2048 | Hardware safety switch | the safety switch has been pressed |
| 12 | 4096 | GPS Configuration | the GPS has accepted the configuration from the flight controller |
| 13 | 8192 | System | parameter storage, main loop rate, terrain and ADS-B memory, CAN |
| 14 | 16384 | Mission | required mission items, rally |
| 15 | 32768 | Rangefinder | rangefinder |
| 16 | 65536 | Camera | camera and mount |
| 17 | 131072 | AuxAuth | external arming authorization (script, companion computer) |
| 18 | 262144 | VisualOdometry | visual odometry |
| 19 | 524288 | FFT | FFT for the harmonic notch |
| 20 | 1048576 | — (OSD) | present in `AP_Arming.h` but not in the parameter description: the GCS shows no checkbox for it |

A value of −1 skips every group, including future ones, and arming produces `Warning: Arming Checks Disabled`. The mandatory checks remain even then: the position and altitude estimate for the selected mode (`AHRS: …`, `Need Position Estimate`, `Need Alt Estimate`, `EKF … variance`), a radio calibration in progress, two ports with the receiver protocol, the motor checks and `Motor Interlock`, and at arming the AHRS and compass health and whether the mode allows arming (`AP_Arming_Copter::arm_checks`). With −1 the firmware no longer checks the throttle, the lean angle, the safety switch or E-Stop. The rule: leave the mask alone; read the whole message and remove the cause. Skipping one group is a temporary bench measure (for example, bit 10 with no SD card), and afterwards the value goes back to 0.

Seventeen messages of a first build (the strings come from `AP_Arming.cpp` and `AP_Arming_Copter.cpp` at tag Copter-4.7.2; "—" in the bit column means the check cannot be disabled with the mask):

| Message | Bit | Cause | What to do |
|---|---|---|---|
| `PreArm: RC not found` | 6 | with `FS_THR_ENABLE` ≠ 0: no RC frame and no override has arrived since boot | port `SERIALn_PROTOCOL = 23`, `RC_PROTOCOLS`, RX↔TX, bind (step 4) |
| `PreArm: Throttle below failsafe` | 6 | with `FS_THR_ENABLE` ≠ 0: the throttle input is below `FS_THR_VALUE` (975): the transmitter is off, or the receiver in failsafe outputs low throttle | switch on the transmitter; radio calibration (step 5) |
| `PreArm: Throttle radio min too high` (`… radio max too low`, the same for Roll/Pitch/Yaw) | 6 | one of the four primary channels has `RCn_MIN` > 1300 or `RCn_MAX` < 1700 µs: the calibration was saved without the end positions | Radio Calibration with the sticks at full travel |
| `PreArm: Check FS_THR_VALUE` | 5 | with `FS_THR_ENABLE` ≠ 0: `RC3_MIN` ≤ `FS_THR_VALUE` + 10 or `FS_THR_VALUE` < 910 | `FS_THR_VALUE` at least 10 µs below `RC3_MIN` (step 12) |
| `Arm: Duplicate Aux Switch Options`, `Arm: Mode channel and RC5_OPTION conflict` (on an arming attempt only) | 6 | one function on two channels; a function assigned to the flight mode channel `FLTMODE_CH` | one function, one channel (`ap-aux-tune`) |
| `PreArm: 3D Accel calibration needed` | 4 | the accelerometer is not calibrated | Accel Calibration (step 9) |
| `PreArm: Gyros inconsistent`, `PreArm: Accels inconsistent` | 4 | the IMUs disagree: the board was moved during startup, it is warming up, or an IMU is faulty | reboot while stationary; if it persists, suspect the IMU |
| `PreArm: Compass not calibrated` | 2 | the compass used for yaw has no calibration | Onboard Mag Calibration (step 9, `ap-sensors`) |
| `PreArm: Compass calibrated requires reboot` | — | the calibration succeeded, the values take effect after a reboot | reboot |
| `PreArm: Compass offsets too high` | 2 | the length of the offset vector exceeds `COMPASS_OFFS_MAX` (1800) | move metal and power wires away from the compass, recalibrate |
| `PreArm: Check mag field: 1050, max 875, min 185` | 2 | the field strength is outside 185–875 mG (530 mG ± 65 %) | calibrate outdoors, away from rebar and cars |
| `PreArm: Compasses inconsistent` | 2 | the compasses report different headings: most often the orientation of the external one is wrong | `COMPASS_ORIENTn` or `COMPASS_AUTO_ROT = 2` and a repeat calibration; for a surplus compass, `COMPASS_USEn = 0` |
| `PreArm: High GPS HDOP` | 3 | HDOP is above `GPS_HDOP_GOOD` (140 = 1.4) in a mode that requires GPS | wait under open sky; move the GPS away from the VTX |
| `PreArm: AHRS: EKF3 still initialising`, `PreArm: Need Position Estimate` | — | the EKF has not converged; a mode that needs position (Loiter, PosHold, Auto) is selected with no position estimate | wait for "EKF3 IMU0 is using GPS" (step 14) or arm in Stabilize/AltHold |
| `PreArm: Battery 1 below minimum arming voltage` (`… low voltage failsafe`) | 8 | the voltage is below `BATT_ARM_VOLT` or already below the failsafe threshold | charge; check `BATT_VOLT_MULT` (step 10) |
| `PreArm: Hardware safety switch`, `Arm: Safety Switch` | 11 / — | the safety switch has not been pressed | press it; on a board with no switch, `BRD_SAFETY_DEFLT = 0` (`ap-outputs`) |
| `Arm: Throttle too high`, `Arm: Leaning` | 6 / 4 | the throttle is above the deadband around center (any mode) or not at zero in a manual-throttle mode (Stabilize, Acro); the lean angle exceeds `ATC_ANGLE_MAX` (30°) | throttle to zero; set the vehicle level, Calibrate Level |

Self-check: from the message text you find the table row and the bit; if there is a bit, `ARMING_SKIPCHK` with that bit removes the message but not the cause. For example, with `Compass offsets too high` the EKF still gets a bad heading (`ap-ekf`).

### Place in the system

- **Receives:** motor-and-prop thrust → T/W → the expected `MOT_THST_HOVER` (`f-aero-props`); the motor protocol (`f-motors-esc`); the receiver and bind (`link-elrs`); the 4.7 parameter names (`ap-intro`).
- **Provides:** a calibrated accelerometer, compass and battery monitor to the EKF and the failsafes (`ap-ekf`, `ap-safety-fs`); a learned hover throttle as the starting point for tuning (`ap-tuning`); the first log and the before/after `.param` (`ap-logs`).
- **If you get it wrong here:** you fit the current scale with a wrong zero → the sensor is correct at one point → the consumed mAh are wrong → the `BATT_LOW_MAH` failsafe triggers at the wrong time (`ap-safety-fs`). A poor compass calibration → "EKF variance" at arming and in Loiter (`ap-ekf`).

## practice
Starting SITL for the whole section (module ap-sitl explains the installation). The frame `-f X` is Quad X; `-f quad` gives Plus (`FRAME_TYPE = 0`), so do not mix them up.

```bash
sim_vehicle.py -v ArduCopter -f X --console --map -w
# Mission Planner / QGC: UDP 14550 (MAVProxy forwards there by itself)
# without MAVProxy, for your own script: sim_vehicle.py -v ArduCopter -f X -w --no-mavproxy  -> tcp:127.0.0.1:5760
```

All outputs below come from a pymavlink script run (the commands are the same ones the Mission Planner buttons send) against SITL built from tag Copter-4.6.3: the `./waf copter` build took 12 min 24 s on 2 cores. In 4.7.2 only `RTL_ALT` (now `RTL_ALT_M`, meters) and `ARMING_CHECK` (now `ARMING_SKIPCHK`) are named differently, and the full list has a different number of parameters.

### Step 1. Firmware and backup
In SITL the firmware is a build; on hardware it is DFU and `_with_bl.hex` (see the theory). Right after the first connection save the full list: Mission Planner → Config → Full Parameter List → Save to file, QGC → Parameters → Tools → Save to file, MAVProxy `param save 00_defaults.param`.

```text
== step 1: backup
params received: 1397 of 1397
  FRAME_CLASS = 1        FRAME_TYPE = 1        MOT_PWM_TYPE = 0
  SERIAL2_PROTOCOL = 2   RC_PROTOCOLS = 1      RC_OPTIONS = 32
  BATT_MONITOR = 4       BATT_VOLT_MULT = 10.1 BATT_AMP_PERVLT = 17
  FS_THR_ENABLE = 1      FS_THR_VALUE = 975    BATT_FS_LOW_ACT = 0
```

`BATT_FS_LOW_ACT = 0` by default: a low battery only produces a warning. Write that down; we fix it at step 12.

### Step 2. Frame and orientation
`FRAME_CLASS = 1` (Quad), `FRAME_TYPE = 1` (X); for frames with the Betaflight motor order, `FRAME_TYPE = 12` (BetaFlightX). `AHRS_ORIENTATION` is for a board mounted with its arrow not pointing forward. Both frame parameters require a reboot. The firmware and SITL defaults differ: on a blank board `FRAME_CLASS = 0` (Undefined: arming is blocked and the motors are not set up) and `FRAME_TYPE = 1`, while `copter.parm`, which `sim_vehicle.py` loads, sets `FRAME_CLASS = 1` and `FRAME_TYPE = 0`, and on top of that the `-f X` option selects X. So on hardware you always set the frame yourself.

### Step 3. Port map
`SERIALn` is a logical number; the board's hwdef ties it to a physical UARTx (the UART table in the board description on ardupilot.org). A typical layout for the example: SERIAL0 is USB, SERIAL1 is telemetry (2, MAVLink2), SERIAL3 is GPS (5), SERIAL4 is DisplayPort (42) or ESC Telemetry (16), SERIAL6 is the receiver (23). A port protocol takes effect after a reboot.

### Step 4. The ELRS receiver
The port: `SERIALn_PROTOCOL = 23` (RCIN); leave the baud rate alone, the firmware sets it itself. `RC_PROTOCOLS = 512` (bit 9, CRSF; 1 = all protocols enabled) avoids incorrect detection. `RC_OPTIONS` = 32 (the default) + 512 (bit 9, suppress the CRSF mode/rate message for ELRS) + 8192 (bit 13, use 420 kbaud for ELRS) = 8736. `RSSI_TYPE = 3` takes RSSI/LQ from the receiver protocol.

```text
  set SERIAL2_PROTOCOL = 23   set RC_PROTOCOLS = 512   set RC_OPTIONS = 8736   set RSSI_TYPE = 3
  after reboot SERIAL2_PROTOCOL = 23   RC_PROTOCOLS = 512   RC_OPTIONS = 8736
```

SITL feeds RC through its own channel, so after the check put back `RC_PROTOCOLS = 1`, `SERIAL2_PROTOCOL = 2`. Bind and the link check are hardware only (link-elrs).

### Step 5. Channels and radio calibration
In SITL the channels are already calibrated (`RC1..8_MIN/MAX` = 1000/2000 in the default SITL parameters, `copter.parm`, which `sim_vehicle.py` loads; the firmware on a blank board has 1100/1900), so this step is done on hardware: Mission Planner → Radio Calibration or QGC → Radio, all sticks and switches to their end positions, then center. The default channel order is AETR (`RCMAP_ROLL/PITCH/THROTTLE/YAW` = 1/2/3/4).

### Step 6. Motor protocol
`MOT_PWM_TYPE`: 0 Normal (PWM), 1 OneShot, 2 OneShot125, 4/5/6/7 are DShot150/300/600/1200; a reboot is required. For DShot: `SERVO_DSHOT_ESC = 1` (BLHeli32/AM32/Kiss) or 2 (BLHeli_S/BlueJay), `SERVO_BLH_AUTO = 1` (pass-thru on all motors: BLHeliSuite32 or AM32 Configurator, for BLHeli_S use BLHeliSuite/JESC; the web ESC Configurator works since 4.5, but the connection through ArduPilot is unstable; you need DShot, a pressed or disabled safety switch, and outputs that are not on the IOMCU), bidirectional DShot is `SERVO_BLH_BDMASK` (a bitmask of outputs, 15 = outputs 1–4) and `SERVO_BLH_POLES` (default 14). `SERVO_DSHOT_ESC` 3 and 4 are the same ESC types with EDT (ESC temperature, voltage and current in the BDShot return channel); set them only when the ESC firmware has EDT. `SERVO_BLH_BDMASK` exists only in a build whose timers have DMA assigned for receive: if it is missing from the parameter list and the board has a `-bdshot` variant (MatekH743-bdshot, CubeOrange-bdshot), flash that one; its timer layout is different, so you redo the output plan. `RC_SPEED` (490 Hz) is the update rate of PWM motors only; it is not used with DShot. Timer groups, EDT and pass-thru are covered in full in module `ap-outputs`. SITL accepts the parameter, but the build has no `SERVO_BLH_*`:

```text
  set MOT_PWM_TYPE = 6   set SERVO_DSHOT_ESC = 1
  SERVO_BLH_AUTO: no such parameter in the SITL build (no BLHeli pass-through)
  after reboot MOT_PWM_TYPE = 6
```

The outputs of one timer group must be of one type: DShot and PWM do not mix within a group.

### Step 7. Motor order: Motor Test
The Motor Test letters go clockwise from the first motor to the right of the nose, not by output number. For Quad X the motor numbers are: 1 front right (CCW), 2 rear left (CCW), 3 front left (CW), 4 rear right (CW). A 10 % test for 2 s (`MAV_CMD_DO_MOTOR_TEST`; MAVProxy `motortest 1 0 10 2`):

```text
  idle SERVO1-4 = [1000, 1000, 1000, 1000]
  seq 1 (A): ack 0, SERVO1-4 = [1100, 1000, 1000, 1000] -> output [1]
  seq 2 (B): ack 0, SERVO1-4 = [1000, 1000, 1000, 1100] -> output [4]
  seq 3 (C): ack 0, SERVO1-4 = [1000, 1100, 1000, 1000] -> output [2]
  seq 4 (D): ack 0, SERVO1-4 = [1000, 1000, 1100, 1000] -> output [3]
```

A → output 1, B → 4, C → 2, D → 3: around the circle front right → rear right → rear left → front left. 10 % throttle = 1000 + 0.10 × 1000 = 1100 µs. Write down the table "button → output → position → direction": on hardware you fill it in by eye. The same outputs are visible in Mission Planner on the SETUP → Mandatory Hardware → Servo Output screen: for each output it shows the function (`SERVOn_FUNCTION`), Min/Trim/Max, Reverse, and a live bar of the current pulse. "A motor is in the wrong position" is resolved here: you move function 33–36 (Motor1–4) to the right output, you do not change the letter in Motor Test. The check is a repeat Motor Test that gives the same table A→1, B→4, C→2, D→3.

### Step 8. Idle speed: MOT_SPIN_ARM and MOT_SPIN_MIN
Armed in Stabilize with the throttle at zero:

```text
  armed=True, throttle stick low: SERVO1-4 = [1100, 1100, 1100, 1100]
```

That is `MOT_PWM_MIN` + `MOT_SPIN_ARM` × (2000 − 1000) = 1000 + 0.10 × 1000. The real values are found on the bench from the point where the motors start to spin (see the hardware section). ESC calibration does not exist in SITL.

### Step 9. Accelerometer and compass
In SITL the sensors are "calibrated" by the standard parameters; MAVProxy has `accelcal` and `magcal`, but it is better to learn this on a board: USB is enough, no battery needed. Two parameters decide whether the firmware accepts a compass calibration: `COMPASS_CAL_FIT` (default 16; 4 Very Strict, 8 Strict, 32 Relaxed) is the fitness limit, used as is for an external compass in the first slot and doubled for the others; `COMPASS_AUTO_ROT` (default 2) checks the orientation of an external compass at the end of the calibration and corrects `COMPASS_ORIENT`. The rule: when the calibration fails, look at the location and the orientation first, and use `COMPASS_CAL_FIT = 32` last; the details are in `ap-sensors`.

### Step 10. Battery monitor
SITL models a 3DR Power Brick sensor: V_pin = V / 10.1, I_pin = I / 17. So a wrong multiplier shows up exactly as on hardware. In a hover (there is current only with the motors running):

```text
  SIM_BATT_VOLTAGE = 12.6 V; GCS: 12.600 V, 28.10 A
  BATT_VOLT_MULT 11.0 -> GCS 13.722 V; new = 11.0 * 12.6 / 13.722 = 10.101
  BATT_VOLT_MULT 10.1 -> GCS 12.600 V
  current in hover: PERVLT 17 -> 28.10 A, 20 -> 33.09 A, back to 17 -> 28.10 A
```

The voltage and current readings are directly proportional to the multiplier (33.09 / 28.10 = 1.178 ≈ 20/17), and the formula from the theory holds to the third digit. Write down the reference (here `SIM_BATT_VOLTAGE`), the reading, the calculation and the check.

### Step 11. Modes and arming
`FLTMODE_CH = 5`, with position boundaries at 1230/1360/1490/1620/1749 µs. A three-position switch gives ≈ 1000/1500/2000 µs, that is positions 1, 4 and 6, so set the modes in pairs: `FLTMODE1 = FLTMODE2 = 0` (Stabilize), `FLTMODE3 = FLTMODE4 = 2` (AltHold), `FLTMODE5 = FLTMODE6 = 5` (Loiter). Arm with a switch, `RCx_OPTION = 153` (ArmDisarm), or with the stick (`ARMING_RUDDER = 2`); the emergency stop is `RCx_OPTION = 31` (Motor Emergency Stop). Leave `ARMING_SKIPCHK = 0` alone (before 4.7, `ARMING_CHECK = 1`). If arming fails, look up the `PreArm: …` text from Messages in the table of the theory section "Why it will not arm": it gives the bit, the cause and the step where the cause is removed. In SITL check three lines yourself (a run on SITL Copter-4.7.2, `copter.parm`, RC through override, throttle at 1000 µs): `RC5_OPTION = 153` with `FLTMODE_CH = 5` and an arming attempt; then `RC5_OPTION = 0`, `FS_THR_VALUE = 1000` with `RC3_MIN = 1000`; then `FS_THR_VALUE = 975` and a throttle override of 950 µs:

```text
RC5_OPTION=153:     ['Arm: Mode channel and RC5_OPTION conflict']
FS_THR_VALUE=1000:  ['Arm: Check FS_THR_VALUE']
  40 s idle:        ['PreArm: Check FS_THR_VALUE', 'PreArm: Check FS_THR_VALUE']
throttle 950:       ['Arm: Throttle below failsafe', 'Arm: Radio failsafe on',
                     'PreArm: Throttle below failsafe', 'PreArm: Radio failsafe on']
```

The first line is a final check that does not run in the background; the second is the same parameter check at arming and in the background once every 30 s; the third is two causes at once, and neither goes away while the throttle is below `FS_THR_VALUE`. After the run put back `FS_THR_VALUE = 975`, `RC5_OPTION = 0`.

### Step 12. Failsafe
RC: `FS_THR_ENABLE = 1` (RTL), `FS_THR_VALUE = 975`, `RC_FS_TIMEOUT = 1` s. Battery for SITL: `BATT_LOW_VOLT = 11.0`, `BATT_LOW_TIMER = 5`, `BATT_FS_LOW_ACT = 2` (RTL). A SITL trap: an RC override from the GCS or a script counts as live RC and masks `SIM_RC_FAIL`; release the override, which times out after `RC_OVERRIDE_TIME` = 3 s.

The output was captured on Copter-4.6.3; in 4.7.2 `RTL_ALT = 1500` (cm) is called `RTL_ALT_M = 15` (m).

```text
== step 12: RC failsafe (SIM_RC_FAIL=1) in Loiter
  mode after 1.7 s: RTL; texts: ['Radio Failsafe']
  alt 8 s into RTL: 12.6 m (RTL_ALT = 1500 cm)
  RC restored, texts: ['Radio Failsafe Cleared']
== step 12: battery failsafe in Loiter
  mode RTL; texts: ['Battery 1 is low 10.80V used 917 mAh', 'Battery Failsafe']
  disarmed after 29 s more
```

On the ground the same `SIM_RC_FAIL = 1` produced "Radio Failsafe - Disarming": an armed vehicle on the ground disarms immediately on RC loss, and that is what you verify on the bench. The full failure matrix is in module ap-safety-fs.

### Step 13. OSD
`OSD_TYPE = 1` for MAX7456 (analog), 5 for MSP DisplayPort (DJI O3, Walksnail, HDZero) together with `SERIALn_PROTOCOL = 42` on the VTX port; `OSD_CHAN` is the screen-switching channel, `OSDn_ENABLE` enables additional screens. For DisplayPort the flight controller sets the text grid, separately for each screen: `OSDn_TXT_RES` 0 is 30×16 (the default), 1 is 50×18, 2 is 60×22; with 0, HD goggles show the coarse SD grid. `MSP_OPTIONS` (default 0): do not set bit 0 for DisplayPort, bit 2 (4) selects the Betaflight font indexes in the goggles (stock DJI O3/O4), bit 3 (8) the INAV font indexes; reboot after a change. Ready-made "port, `OSD_TYPE`, `MSP_OPTIONS`" triples for each system are in module `ap-osd-video`. The OSD window in SITL needs a build with SFML (`sim_vehicle.py --osd`), so here you only set the parameter and check it on the goggles.

### Step 14. GPS and RTL
SITL has a GPS from the start (`GPS1_TYPE = 1`): wait for "EKF3 IMU0 is using GPS", without which Loiter will not engage. `RTL_ALT_M` is in meters, default 15 (before 4.7, `RTL_ALT` in centimeters, 1500); set it above the tallest obstacles of the site.

### Step 15. Hover: Stabilize → AltHold → Loiter
```text
  Stabilize liftoff: throttle stick 1510 us, alt 1.0 m, SERVO1-4 [1622, 1622, 1621, 1622]
  AltHold 20 s, stick centred: 6.7 -> 6.7 m
  Loiter 30 s: alt 6.7 m, SERVO1-4 [1591, 1590, 1590, 1591], MOT_THST_HOVER = 0.361
  MOT_THST_HOVER after flight = 0.429
```

In AltHold the altitude did not move by even 0.1 m, and `MOT_THST_HOVER` is learned automatically (`MOT_HOVER_LEARN = 2`): 0.39 → 0.361 in Loiter and 0.429 by the end of the flight on a battery sagged to 10.8 V. Checking the formula: at 0.361 and `MOT_THST_EXPO` 0.65, r = 0.523, the output is 0.15 + 0.8 × 0.523 = 0.569, PWM ≈ 1569 µs against 1590 in the log; the difference comes from voltage compensation (`MOT_BAT_VOLT_MAX` = 12.8 in SITL) and the position-hold corrections. The first attempt of this run crashed: the throttle override timed out after 3 s, and in AltHold "throttle at zero" means descending at the maximum rate, hence "SIM Hit ground at 2.49 m/s".

### Step 16. First tune
Tuning in SITL is pointless: there are no vibrations (`VIBE` = 0), and the PIDs do not transfer to a real vehicle (ap-sitl). The order on hardware is in ap-tuning; a short version follows below.

### Step 17. Log and .param
```text
VIBE p95 X/Y/Z: 0.0 / 0.0 / 0.0 m/s^2, clip total 0
CTUN.ThH in flight: first 0.390, last 0.429; MOT_THST_HOVER in log 0.429
events:
    141.6 s  ERR Subsys=5 ECode=1      141.6 s  MODE RTL (reason 3)
    151.9 s  ERR Subsys=5 ECode=0      167.8 s  ERR Subsys=6 ECode=1
    167.8 s  MODE RTL (reason 4)
```

ERR Subsys 5 is radio, 6 is battery; MODE reasons 3 and 4 are RADIO_FAILSAFE and BATTERY_FAILSAFE. The course checker `check_lab_log.py --lab failsafe` on this log: PASS (reaction 0.0 s). `--lab hover` returned FAIL on battery sag (13.72 → 10.80 V), which we caused ourselves in steps 10 and 12, so record a separate clean log for the hover check (`--lab hover`). The second `.param` after setup and its comparison with the first one (Mission Planner → Compare Params or a `diff` of the two files) is ArduPilot's "diff all".

### Moving to real hardware
The props stay off until item 11. Connect the battery only when an item requires it; the flight controller runs on USB.

1. **Firmware.** Save `diff all` from Betaflight. DFU, `arducopter_with_bl.hex` for your board, STM32CubeProgrammer. Mission Planner sees the board → save `00_defaults.param`.
2. **Frame and ports.** `FRAME_CLASS = 1`, `FRAME_TYPE = 1` or 12; `SERIALn_PROTOCOL` from the board's UART table; reboot; Mission Planner → Messages shows no errors.
3. **Receiver.** `SERIALn_PROTOCOL = 23`, `RC_PROTOCOLS = 512`, `RC_OPTIONS = 8736`, `RSSI_TYPE = 3`. Bind (an ELRS binding phrase or bind mode); switch on the transmitter before the receiver. Radio Calibration: the sticks move in the right direction, the endpoints are ≈ 988…2012 µs with ELRS. Switch off the transmitter: the channels freeze and Mission Planner shows a failsafe; with the transmitter off, the throttle must be at least 10 µs below `FS_THR_VALUE`, and with it on and the stick down, at least 10 µs above.
4. **Motor protocol.** DShot: `MOT_PWM_TYPE = 6`, `SERVO_DSHOT_ESC`, `SERVO_BLH_AUTO = 1`, reboot; no ESC calibration is needed, the range is fixed. PWM ESCs: `MOT_PWM_TYPE = 0` and an ESC calibration: `ESC_CALIBRATION = 3`, disconnect USB and the battery, connect the battery, press the safety switch (if fitted), wait for the tune and the beeps that count the cells, disconnect the battery. The alternative from the documentation: throttle up, connect the battery, reconnect it, throttle down after two beeps.
5. **Motor Test** on battery power, 10 % (if a motor does not spin, 15 %): A–D clockwise from the front right, directions CCW/CW per the frame diagram. Wrong direction: with DShot use `SERVO_BLH_RVMASK` or the ESC configurator, with PWM swap two motor wires. Wrong position: `SERVOn_FUNCTION` (33–36 = Motor1–4) or resoldering, never "change the letter".
6. **Idle.** In Motor Test raise the % until all four start reliably: a threshold of 6 % → `MOT_SPIN_ARM` = (6 + 2)/100 = 0.08, `MOT_SPIN_MIN` ≥ `MOT_SPIN_ARM` + 0.03 = 0.11. Arm with the props off: all motors spin evenly and none is stopped.
7. **Accel and compass.** Accel Calibration is 6 positions plus Calibrate Level on a level table. Onboard Mag Calibration outdoors, away from cars and rebar: rotate until every side has pointed down, Fitness at Default, three rising tones, reboot. If the internal compass gets in the way of the mast-mounted one, use `COMPASS_USE2 = 0` (or `COMPASS_USE3`), but the number here is a priority, not "the internal one": first match `COMPASS_PRIO1_ID…3_ID` against the compass list in the GCS. CompassMot comes later, with the props flipped and the vehicle tied down: < 30 % is good, 31–60 % is a gray zone, > 60 % means move the compass.
8. **Battery monitor.** `BATT_MONITOR = 4`, pins and scales from the board description. (a) Zero: USB, battery disconnected, the GCS shows I₀ → `BATT_AMP_OFFSET` = old + I₀/`BATT_AMP_PERVLT`. (b) Voltage: battery connected, multimeter on the balance lead; Mission Planner → Battery Monitor → Measured battery voltage, or the formula; the target is an error < 0.02 V per cell (0.12 V on 6S). (c) Current: a clamp meter on the power lead at ~10 A (Motor Test at 30–40 % with no props will not draw 10 A, so use a hover and a mAh comparison). (d) mAh: after a flight compare `BAT.CurrTot` with the figure the charger put back; an example is 1186 against 1310 mAh with `BATT_AMP_PERVLT` 40 → 40 × 1310/1186 = 44.2. The target is a difference < 5 %.
9. **Modes and failsafe on the bench.** Modes in pairs (`FLTMODE1/2` Stabilize, `3/4` AltHold, `5/6` Loiter): check on the Flight Modes tab that each switch position highlights the right mode; the arming switch, E-Stop. A 6S LiPo battery: `BATT_LOW_VOLT = 21.6` (3.6 V per cell under load), `BATT_CRT_VOLT = 21.0` (3.5 V per cell), `BATT_FS_LOW_ACT = 2` (RTL), `BATT_FS_CRT_ACT = 1` (Land), `BATT_CAPACITY = 4000`, `BATT_LOW_MAH = 1000`, `BATT_ARM_VOLT = 22.1`; the Initial Tune Parameter screen of item 11 writes the same voltages for 6S with a minimum of 3.3 V per cell; `MOT_BAT_VOLT_MAX = 25.2`, `MOT_BAT_VOLT_MIN = 19.8`. A test with the props off: Stabilize, arm, throttle at zero, switch off the transmitter → immediate disarm.
10. **OSD and video.** `OSD_TYPE = 1` (analog) or `5` + `SERIALn_PROTOCOL = 42` (digital); the goggles show voltage, mode, RSSI/LQ.
11. **Preflight check.** Starting tune parameters from the prop size and cell count (Mission Planner → SETUP → Mandatory Hardware → Initial Tune Parameter, ap-tuning), `MOT_THST_HOVER = 0.25`, `ATC_THR_MIX_MAN = 0.1`, `MOT_HOVER_LEARN = 2`, `LOG_DISARMED = 0`, an SD card is present. Props on: blade direction per Motor Test, nuts tight. A 20 × 20 m site with no people, wind < 5 m/s, an observer.
12. **First hover.** Stabilize: arm → disarm → arm (a disarm check), raise the throttle slowly until liftoff, land at once and disarm. Then a hover at 1 m with stick deflections of ±5°. Then Stabilize up to 5 m → AltHold for ≥ 30 s with no inputs → landing; `PSC_D_ACC_P` = 0.1 × `MOT_THST_HOVER`, `PSC_D_ACC_I` = 0.2 × `MOT_THST_HOVER` (the rule was verified on 4.6: `PSC_ACCZ_P` = `MOT_THST_HOVER`, `PSC_ACCZ_I` = 2 × `MOT_THST_HOVER`; for 4.7 it is rescaled by the conversion factor 0.1 from the 4.7.2 source). Then Loiter for 30 s: the vehicle stays within a 1–2 m circle. Abort criteria: a jerk or a spin at liftoff means throttle to zero and disarm (motor order or direction); audible or visible oscillation means land and reduce all of `ATC_RAT_RLL/PIT_P/I/D` by −50 %; toilet bowling in Loiter means switch to AltHold and land (compass); "PreArm"/"EKF variance" means do not take off.
13. **First tune.** `INS_LOG_BAT_MASK = 1`, a 30 s hover → the harmonic notch from the spectrum (ap-tuning). Then QuikTune: `VTOL-quicktune.lua` in `APM/scripts`, `SCR_ENABLE = 1`, reboot, `QUIK_ENABLE = 1`, a switch with `RCx_OPTION = 300`; Loiter at 3 m, switch to the middle to tune, up to save. Lua is built only when the flash is larger than 1 MB (`AP_Scripting_config.h`): an F405 with 1 MB has no scripting, so use AutoTune there (`RCx_OPTION = 17`, `AUTOTUNE_AXES = 1` for roll, AltHold/Loiter, saved on disarm with the switch still on).
14. **Log and backup.** Download the `.BIN` (Mission Planner → DataFlash Logs), run `check_lab_log.py --lab hover`, save `01_after_setup.param` and compare it with `00_defaults.param`.

Hardware acceptance: Motor Test matches the frame diagram in position and direction; voltage error < 0.02 V per cell, mAh within 5 % of the charger; the RC failsafe disarms on the ground and gives RTL or Land in the air at 5 m; `MOT_THST_HOVER` is 0.2–0.5; `VIBE` p95 < 30 m/s², `Clip` = 0.

Self-check: the lab is done when:
- SITL: `00_defaults.param` and `01_after_setup.param` are saved and compared, the Motor Test table (A→1, B→4, C→2, D→3) is written down, the `BATT_VOLT_MULT` calibration is calculated and verified, the three arming refusals of step 11 were obtained with the same texts as in the output (`Arm: Mode channel and RC5_OPTION conflict`, `Check FS_THR_VALUE`, `Throttle below failsafe`) and the parameters were put back, the SITL log has `ERR Subsys=5` and `Subsys=6` with a change to RTL, and `MOT_THST_HOVER` from the log is within 0.2–0.5;
- hardware: the `.param` after setup is committed together with the `.BIN` of the first hover (60 s, Stabilize → AltHold → Loiter), `MOT_THST_HOVER` is 0.2–0.5, `VIBE` p95 < 30 m/s² with no clipping, the RC and battery failsafes are in the log (battery: with a `BATT_LOW_VOLT` threshold just below the present hover voltage), the voltage error is < 0.02 V per cell, and the mAh are within 5 %.

## diagnostics
- **Symptom:** Mission Planner does not see the board after flashing a Betaflight board
  - Possible cause: a `.apj` or a `.hex` without the bootloader was flashed, or the board is not in DFU.
  - What to do: DFU (BOOT + USB), `arducopter_with_bl.hex`, STM32CubeProgrammer; from then on only `.apj`.
- **Symptom:** the RC channels do not move although the receiver shows a link
  - Possible cause: the wrong `SERIALn` (hwdef), `RC_PROTOCOLS` without bit 9, RX/TX not crossed, a UART without DMA on F4/F7.
  - What to do: check the board's UART table, try `RC_PROTOCOLS = 1`, receiver RX to board TX.
  - In the log: `RCIN` sits at constant values.
- **Symptom:** "Bad DShot" / the motors do not respond after `MOT_PWM_TYPE = 6`
  - Possible cause: no reboot, the output is on IOMCU MAIN (DShot only on AUX without `BRD_IO_DSHOT`), DShot and PWM are mixed in a timer group.
  - What to do: reboot, motors on DShot-capable outputs, uniform groups.
- **Symptom:** at liftoff the copter rolls sharply or spins
  - Possible cause: a motor is in the wrong position or spins the wrong way, the props are swapped.
  - What to do: throttle to zero, disarm; repeat Motor Test with the props off and compare with the frame diagram.
  - Consequences: a flip within the first 0.5 s, broken props.
- **Symptom:** after arming one motor does not spin or stutters
  - Possible cause: `MOT_SPIN_ARM` is below the starting threshold of that motor; with PWM, the ESCs are not calibrated.
  - What to do: find the threshold in Motor Test, `MOT_SPIN_ARM` = threshold + 0.02; ESC calibration for PWM.
- **Symptom:** the OSD voltage differs from the multimeter by 0.3–0.5 V
  - Possible cause: the default `BATT_VOLT_MULT` is for a different sensor.
  - What to do: new = old × V_multimeter / V_GCS, verify at two states of charge.
- **Symptom:** the flight controller counted 15–20 % fewer mAh than the charger put back
  - Possible cause: a wrong `BATT_AMP_PERVLT` or a zero offset.
  - What to do: first `BATT_AMP_OFFSET` from the zero reading, then the scale from the charger mAh.
  - Consequences: `BATT_LOW_MAH` triggers late and the vehicle lands on an empty battery.
- **Symptom:** in SITL `SIM_RC_FAIL = 1` does not trigger the failsafe
  - Possible cause: the GCS or a script is sending an RC override, which counts as live RC.
  - What to do: remove the override (it times out after `RC_OVERRIDE_TIME` = 3 s) and repeat.
- **Symptom:** in AltHold the copter lands by itself or falls
  - Possible cause: the throttle is below the deadband (in SITL, a timed-out throttle override), a wrong `MOT_THST_HOVER`, Z vibration.
  - What to do: center the throttle before switching, `MOT_HOVER_LEARN = 2`, `VIBE.VibeZ` < 30.
- **Symptom:** "PreArm: Compass not calibrated" or toilet bowling in Loiter
  - Possible cause: calibration indoors, interference from power wires, a wrong orientation of the external compass.
  - What to do: calibrate outdoors, run CompassMot, disable the internal compass.

## checklist
- The board is flashed with `_with_bl.hex`; from now on I update with `.apj` only
- `00_defaults.param` is saved before the first change
- The ports are assigned from the board's UART table, the receiver is on `SERIALn_PROTOCOL = 23`
- Motor Test: A→B→C→D clockwise, directions per the frame diagram, props off
- `MOT_SPIN_ARM` = threshold + 0.02, `MOT_SPIN_MIN` ≥ `MOT_SPIN_ARM` + 0.03
- Battery monitor: zero, voltage, current, mAh, in that order
- `BATT_FS_LOW_ACT` ≠ 0, the RC failsafe is verified on the ground and in SITL
- First hover Stabilize → AltHold → Loiter with abort criteria
- The `.BIN` and `01_after_setup.param` are saved and compared with the original

## references
- Loading Firmware onto boards without existing ArduPilot firmware — ArduPilot Copter | https://ardupilot.org/copter/docs/common-loading-firmware-onto-chibios-only-boards.html | primary | A
- Loading Firmware (boards with ArduPilot bootloader) — ArduPilot Copter | https://ardupilot.org/copter/docs/common-loading-firmware-onto-pixhawk.html | primary | A
- Crossfire and ELRS RC Systems — ArduPilot Copter | https://ardupilot.org/copter/docs/common-tbs-rc.html | primary | A
- DShot and Bi-directional DShot — ArduPilot Copter | https://ardupilot.org/copter/docs/common-dshot-escs.html | primary | A
- Connect ESCs and Motors (Motor Test) — ArduPilot Copter | https://ardupilot.org/copter/docs/connect-escs-and-motors.html | primary | A
- ESC Calibration — ArduPilot Copter | https://ardupilot.org/copter/docs/esc-calibration.html | primary | A
- Set Motor Range (MOT_SPIN_ARM / MOT_SPIN_MIN) — ArduPilot Copter | https://ardupilot.org/copter/docs/set-motor-range.html | primary | A
- Power Module Configuration in Mission Planner — ArduPilot Copter | https://ardupilot.org/copter/docs/common-power-module-configuration-in-mission-planner.html | primary | A
- Compass Calibration — ArduPilot Copter | https://ardupilot.org/copter/docs/common-compass-calibration-in-mission-planner.html | primary | A
- Radio Failsafe — ArduPilot Copter | https://ardupilot.org/copter/docs/radio-failsafe.html | primary | A
- Onscreen Display (OSD) — ArduPilot Copter | https://ardupilot.org/copter/docs/common-osd-overview.html | primary | A
- Initial Tuning Flight — ArduPilot Copter | https://ardupilot.org/copter/docs/initial-tuning-flight.html | primary | A
- QuikTune — ArduPilot Copter | https://ardupilot.org/copter/docs/quiktune.html | primary | A
- ArduPilot source, tag Copter-4.6.3 (AP_BattMonitor_Analog.cpp, AP_MotorsMulticopter.cpp, RC_Channels_VarInfo.h, AP_SerialManager.cpp) | https://github.com/ArduPilot/ardupilot/tree/Copter-4.6.3 | primary | A
- ArduPilot source, tag Copter-4.7.2 (4.7 names and defaults: ArduCopter/Parameters.cpp, mode_rtl.cpp, AP_Arming.cpp, AC_PosControl.cpp) | https://github.com/ArduPilot/ardupilot/tree/Copter-4.7.2 | primary | A
- Firmware tab — QGroundControl User Guide | https://docs.qgroundcontrol.com/master/en/qgc-user-guide/setup_view/firmware.html | primary | A
- ArduPilot setup — ExpressLRS documentation | https://www.expresslrs.org/quick-start/ardupilot-setup | secondary | A
