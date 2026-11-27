---
id: ap-outputs
title: "ArduPilot outputs: SERVOn_FUNCTION, timer groups, DShot/BDShot, BLHeli, servos, GPIO, and relays"
level: L2
readingTime: 60 min
firmware: ArduCopter 4.7 (checked against 4.7.3)
status: published
added: 2026-11-18
tags:
  - ArduPilot
  - SERVOn_FUNCTION
  - DShot
  - BDShot
  - BLHeli
  - timers
  - GPIO
  - relays
related:
  - ap-setup-scratch
  - ap-osd-video
  - ap-tuning
  - ap-heavy
  - ap-quadplane
  - ctl-allocation
  - f-esc-firmware
  - bf-servos-pwm
  - el-power-design
next:
  - ap-tuning
source: content/ardupilot/ap-outputs.md
source_hash: 0fa054c654b3
---

## summary
In ArduPilot every signal pad is "output n" with an assignable role, `SERVOn_FUNCTION`: a motor, a control surface, a transmitter channel passthrough, an LED strip, or a plain GPIO pin. This module follows the whole path on ArduCopter 4.7.2 from the function to the microcontroller's timer: the list of functions with their numbers, the `SERVOn_MIN/MAX/TRIM/REVERSED` range, the `SERVO_RATE` and `RC_SPEED` rates, the `MOT_PWM_TYPE` protocols, timer groups and the messages on a conflict, DShot and bidirectional DShot with the `SERVO_BLH_*` parameters, ESC telemetry, passthrough, the IOMCU coprocessor, the safety switch, GPIO, and relays. After the module you can lay out motors, servos, an LED strip, and relays across the outputs of a specific board so that the flight controller arms the first time. The lab is a calculation exercise with no hardware and no simulator: an output plan from the `hwdef` of the MatekH743 board, bitmasks, the servo pulse width in the firmware's integer arithmetic, and finding three errors in a parameter file.

## theory
### The pipeline: from function to pin
The signal on an output passes through four stages.

1. **Source.** The motor mixer (`ctl-allocation`), the surface controller, the gimbal, a Lua script, or a transmitter channel writes a value not "to output 3" but to a function: "Motor1", "Elevator", "Script1".
2. **`SRV_Channel`.** For every output whose `SERVOn_FUNCTION` equals that function, the value is converted to microseconds using `SERVOn_MIN/MAX/TRIM/REVERSED`. One function can be assigned to several outputs.
3. **`RCOutput`.** The board driver turns microseconds into what the protocol requires: a PWM pulse, a DShot frame, or an LED strip bit stream.
4. **Timer.** The channels of one hardware timer drive the pads. The protocol and the rate are set for the whole timer.

{{diagram:ap-outputs-pipeline|A value goes from the function through SRV_Channel and RCOutput to the timer. The range is set per output, but the protocol and rate are set for the whole timer, so layout errors show up at the last stage.}}

Changing `SERVOn_FUNCTION` requires a reboot. There are 16 outputs; `SERVO_32_ENABLE = 1` exposes the parameters of outputs 17–32.

### `SERVOn_FUNCTION`: functions by purpose
| Group | Values | What it does |
|---|---|---|
| Utility | −1 GPIO; 0 Disabled; 134 / 135 / 136 | −1 makes the pad a digital pin; 0 leaves the output free for `DO_SET_SERVO` and scripts; 134–136 constantly output `SERVOn_MIN`, `TRIM`, or `MAX` |
| Multicopter motors | 33–40 Motor1–8; 82–85 Motor9–12; 160–179 Motor13–32 (new in 4.7) | a mixer output; the motor number follows the frame diagram, not the pad number |
| Transmitter passthrough | 1 RCPassThru; 51–66 RCIN1–16; 140–155 RCIN1Scaled–16Scaled | 1 is the transmitter channel with the same number as the output; 51–66 are a chosen channel, with microseconds as received; 140–155 are a channel rescaled to the `SERVOn_MIN/TRIM/MAX` of this output |
| Payload | 6–9 Mount1 (yaw, pitch, roll, retract); 12–15 Mount2; 10 CameraTrigger; 27 Parachute; 28 Gripper; 29 LandingGear; 88 Winch | gimbal servos, camera shutter, parachute, gripper, landing gear, winch |
| Scripting | 94–109 Script1–16 | an output controlled from Lua (`ap-lua`) |
| LEDs and sound | 120–123 NeoPixel1–4; 129–131 ProfiLED1–3; 132 ProfiLEDClock; 138 / 139 Alarm | a strip takes a whole timer; so does a buzzer on an output |
| Plane | 4 Aileron; 19 Elevator; 21 Rudder; 70 Throttle; 2 / 3 Flap; 24 / 25 Flaperon; 77 / 78 Elevon; 79 / 80 V-tail; 41, 45–47, 75, 76 motor tilt | most of these functions are not in the Copter value list; assignment and the direction check are in `ap-setup-plane` |

On outputs 140–155 the position freezes on link loss; the bits of `SERVO_RC_FS_MSK` (bit 0 is RCIN1Scaled) send the selected outputs to `TRIM`.

### Output range: `SERVOn_MIN`, `MAX`, `TRIM`, `REVERSED`
| Parameter | Default | Range | Meaning |
|---|---|---|---|
| `SERVOn_MIN` | 1100 µs | 800–2200 | the lower pulse limit |
| `SERVOn_MAX` | 1900 µs | 800–2200 | the upper limit |
| `SERVOn_TRIM` | 1500 µs | 800–2200 | neutral for signed functions |
| `SERVOn_REVERSED` | 0 | 0 / 1 | reverses the direction |

Functions come in two types. An **angle** function (surfaces, scripting outputs, RCINnScaled) takes a number s from −4500 to +4500, with neutral at `TRIM`. A **range** function (a plane's flap and throttle, from 0 to 100) takes s from 0 to H, with zero at `MIN`. The formulas from `SRV_Channel.cpp`, where ⌊ ⌋ means dropping the fractional part:

- angle, s > 0: PWM = TRIM + ⌊s · (MAX − TRIM) / 4500⌋;
- angle, s ≤ 0: PWM = TRIM − ⌊|s| · (TRIM − MIN) / 4500⌋;
- range: PWM = MIN + ⌊s · (MAX − MIN) / H⌋.

`REVERSED = 1` flips the sign of s for an angle and replaces s with H − s for a range. The input is constrained to the limits first. The fraction is truncated, not rounded; the two halves of the travel, up and down, differ if `TRIM` is not in the middle. Arming is refused with `SERVOn_MIN` > `TRIM` or `SERVOn_MAX` < `TRIM`. On DShot outputs the firmware itself keeps `MIN`/`MAX` at 1000/2000 and `TRIM` at 1000 (1500 for reversible ones).

### Motor rate and protocol
| Parameter | Default | Range | What it affects |
|---|---|---|---|
| `SERVO_RATE` | 50 Hz | 25–400 | all PWM outputs except the "fast" groups |
| `RC_SPEED` | 490 Hz | 50–490 | a copter's PWM motors; on main processor outputs no more than 400 Hz takes effect; not used for DShot. On a QuadPlane, `Q_RC_SPEED` |
| `MOT_PWM_TYPE` | 0 | 0–9 | the motor protocol; needs a reboot. On a QuadPlane, `Q_M_PWM_TYPE` |

| `MOT_PWM_TYPE` | Protocol | What follows from it |
|---|---|---|
| 0 | Normal PWM | a 1000–2000 µs pulse at the `RC_SPEED` rate; needs an ESC calibration |
| 1 | OneShot | the same pulse, but one per controller loop |
| 2 | OneShot125 | a 125–250 µs pulse, one per loop |
| 3 | Brushed | a duty cycle for brushed motors; the `RC_SPEED` default becomes 16000 Hz |
| 4 / 5 / 6 / 7 | DShot150 / 300 / 600 / 1200 | a digital frame, no calibration needed, `MOT_PWM_MIN/MAX` are fixed at 1000/2000; the group's timer needs a DMA channel |
| 8 / 9 | PWMRange / PWMAngle | PWM, but each motor's limits are taken from `SERVOn_MIN/MAX` (and `TRIM`) |

A group that contains a PWM motor switches entirely to the motor rate, and `SERVO_RATE` no longer changes it. An analog servo in such a group gets 400 Hz without a single warning and overheats.

### Timer groups
A timer has one counter and one prescaler, so all its channels run in one mode and with one period. A group is the outputs of one timer. The firmware's rules:

- DShot or an LED strip on any output switches the whole group to that mode. The other outputs of the group with ordinary functions are **disabled**, and arming is refused with the message `PreArm: SERVO5_FUNCTION=28 on disabled channel`. The exceptions, for which there is no failure: motors, the other functions that E-Stop stops (throttle 70, 73, 74, 81, starter 69, EngineRunEnable 30, helicopter rotors 31 and 32), the strip outputs themselves (120–123, 129–132), and the scripting outputs 94–109.
- **Hence a dangerous case: a strip in the same group as motors.** The strip switches the group to its own mode, the motors of that group get a strip signal instead of DShot, and the pre-arm check is silent, because motor outputs are excluded from it. Arming succeeds, and the motor does not start or stops. This is a conclusion from reading `RCOutput.cpp` and `AP_Arming.cpp` and was not tested on hardware. Put a strip only in a group without motors: find its output in the board's group table (below) and make sure no output of that group has a motor function (`ap-notify`).
- An output with function −1 is removed from the group at boot, so a GPIO can sit next to DShot.
- A buzzer (138, 139) takes the whole timer.
- If the timer has no DMA or no prescaler could be found, Messages gets a line such as `Chan 11 to 12, DS600: failed to match clock speed` (other endings: `failed to allocate DMA`, `failed, no DMA`), and the group stays on PWM.

Where to get the group layout. The first source is the board's `hwdef.dat` in the source tree: the `Pxx TIMn_CHm TIMn PWM(k) GPIO(g)` lines give the pad, the timer, the output number, and the pin number. The second is the banner shown when a ground station connects: after `RCOut:` come "mode:outputs" pairs, for example `DS600:1-4 PWM:5-8`; it shows the final mode of every output (the labels: `PWM`, `OneS`, `OS125`, `Brush`, `DS150`–`DS1200`, `NeoP`, `ProfiLED`). The third is the `@SYS/timers.txt` file, which you download over MAVFTP: one line per timer with the fields `CLK`, `MODE`, `FREQ`, `TGT`. It has no output numbers; you match them through the `hwdef`.

{{diagram:ap-outputs-timer-map|MatekH743, standard firmware: five groups. DShot motors on outputs 1–4 take all of TIM8 and TIM5, so outputs 5 and 6 are lost for servos; servos go to TIM4, and the strip to output 13.}}

### DShot, bidirectional DShot, and EDT
| Parameter | Default | Values | Meaning |
|---|---|---|---|
| `SERVO_DSHOT_ESC` | 0 | 0 None; 1 BLHeli32/Kiss/AM32; 2 BLHeli_S/BlueJay; 3 and 4 are the same with EDT | the ESC type: bit widths and the command set. With 0, no DShot commands are sent at all |
| `SERVO_DSHOT_RATE` | 0 | 0 is 1 kHz; 1–4 are multiples of the loop rate | the frame rate. The firmware does not go below 800 Hz: with a 400 Hz loop, values 1 and 2 give 800 Hz, 3 gives 1200, and 4 gives 1600 |
| `SERVO_BLH_AUTO` | 0 | 0 / 1 | enable passthrough and telemetry for all motors |
| `SERVO_BLH_MASK` | 0 | output mask | the same for outputs outside the mixer: a cruise motor, a rover |
| `SERVO_BLH_OTYPE` | 0 | 1 OneShot, 2 OneShot125, 3 Brushed, 4–7 DShot150–1200 | the protocol for the outputs in `SERVO_BLH_MASK` |
| `SERVO_BLH_BDMASK` | 0 | output mask | bidirectional DShot; the parameter exists only in builds that support it |
| `SERVO_BLH_POLES` | 14 | 1–127 | the motor pole count, for converting to RPM |
| `SERVO_BLH_TRATE` | 10 Hz | 0–500 | the telemetry request rate over the separate wire, per ESC |
| `SERVO_BLH_3DMASK` | 0 | output mask | reversible (3D) ESCs |
| `SERVO_BLH_RVMASK` | 0 | output mask | reversed rotation direction through a DShot command |
| `SERVO_BLH_PORT` | 0 | 0 is USB, 1–5 are the MAVLink ports in order | the port passthrough works through |
| `SERVO_BLH_TMOUT` | 0 s | 0–300 | after how many seconds of silence the port goes back to MAVLink; 0 means no timeout |

In all the masks bit 0 is output 1, and the value is the sum of 2^(n − 1). The reverse and 3D commands are sent once a second and only while disarmed.

**Bidirectional DShot (BDShot)** returns the rotation speed over the signal wire in the gap after every frame. It needs: ESC firmware that supports it (BLHeli32, AM32, Bluejay), bits in `SERVO_BLH_BDMASK`, and an ArduPilot build in which the timer has a DMA channel for receiving. In the 4.7.2 tree 133 boards have the `BIDIR` tag in their main `hwdef` (SpeedyBeeF405WING, KakuteH7v2, speedybeef4v4), and 35 boards have a separate build with the `-bdshot` suffix (MatekH743-bdshot, MatekF405-TE-bdshot, CubeOrange-bdshot, Pixhawk6X-bdshot). The ordinary build of those boards has no `SERVO_BLH_BDMASK`, except Pixhawk6X and Pixhawk6C: their ordinary build already has BDShot on the IOMCU MAIN outputs (`HAL_WITH_IO_MCU_BIDIR_DSHOT`), and `-bdshot` moves it to the main processor's outputs. The timer layout in `-bdshot` is different: on MatekH743-bdshot outputs 1–2 are on TIM3, 3–4 on TIM2, 5–6 on TIM5, and the receiver can be connected only through a UART.

**EDT** (Extended DShot Telemetry, `SERVO_DSHOT_ESC` 3 or 4) adds the ESC's temperature, voltage, current, and a stress indicator to the same return channel. Do not enable it without ESC firmware that has EDT.

Sources of ESC telemetry:

| Source | What it gives | What to set |
|---|---|---|
| BDShot | RPM at the frame rate | `SERVO_BLH_BDMASK`, `SERVO_BLH_POLES` |
| EDT on top of BDShot | temperature, voltage, current, stress | `SERVO_DSHOT_ESC = 3` or 4 |
| ESC telemetry wire | RPM, voltage, current, temperature, mAh | the RX of a port with `SERIALn_PROTOCOL = 16`, `SERVO_BLH_TRATE` |
| DroneCAN | the same over the bus | `el-dronecan` |

RPM: the ESC reports the electrical frequency E in units of 100 eRPM, and the firmware calculates RPM = ⌊E · 200 / `SERVO_BLH_POLES`⌋. In the log this is the `ESC` message with the fields `Instance`, `RPM`, `RawRPM`, `Volt`, `Curr`, `Temp`, `CTot`, `MotTemp`, `Err` (the share of bad BDShot replies, %), and `EDT2` with the fields `Stress`, `MaxStress`, `Status`. `ESC_TELEMETRY` goes to the ground; `ESC_TLM_MAV_OFS` shifts the numbering. The harmonic notch filter needs the RPM (`INS_HNTCH_MODE = 3`, `ap-tuning`, `ap-heavy`): a wrong pole count moves the filter off the noise.

### BLHeli passthrough
The flight controller becomes a bridge between the ESC configuration program and the signal wire (`f-esc-firmware`). The conditions, per the source:

- `SERVO_BLH_AUTO = 1` or a nonzero `SERVO_BLH_MASK`, then a reboot: without that the protocol handler is not installed;
- the vehicle is disarmed: requests are ignored while armed;
- the ESC is on a main processor output: IOMCU outputs are not switched to serial mode;
- the program connects to the port from `SERVO_BLH_PORT`, and the ground station is disconnected during that time.

SITL has no `SERVO_BLH_*` parameters. Compatibility of specific versions of the configuration programs cannot be checked from the source (see notes).

### IOMCU and the safety switch
Boards of the Pixhawk and Cube family have a second microcontroller, the IOMCU. Its eight outputs (MAIN) are outputs 1–8, and the main processor's outputs (AUX, FMU) start at 9. On boards without an IOMCU, such as MatekH743, all outputs belong to the main processor.

| | IOMCU (MAIN 1–8) | Main processor |
|---|---|---|
| Groups | fixed: 1–2, 3–4, 5–8 | per the board's `hwdef` |
| DShot | only with `BRD_IO_DSHOT = 1` (a different coprocessor firmware, since 4.5); DShot150–600; with DShot the other MAIN outputs are disabled | DShot150–1200 on groups with DMA |
| BDShot | only on boards where the `hwdef` declares it (Pixhawk6X, Pixhawk6C) | `BIDIR` in the `hwdef` or a `-bdshot` build |
| Passthrough | no | yes |
| GPIO | pins 101–108 | usually pins from 50 |

`BRD_IO_DSHOT` exists only on boards for which that coprocessor firmware is built; `BRD_IO_ENABLE = 0` disables the IOMCU altogether.

Until it is pressed, the safety switch blocks the signal on outputs that are not in `BRD_SAFETY_MASK`. On Copter that is only the motors by default.

| Parameter | Default | Meaning |
|---|---|---|
| `BRD_SAFETY_DEFLT` | 1 on boards with a switch or an IOMCU, otherwise 0 | 1 means the outputs are blocked after boot until the switch is held for about a second |
| `BRD_SAFETYOPTION` | 3 | bit 0 lets the switch disable safety, bit 1 lets it enable safety, bit 2 makes the switch active when armed, bit 3 forces safety on when the vehicle disarms |
| `BRD_SAFETY_MASK` | 0 in the parameter table, but Copter substitutes its own default at boot: all outputs 1–14 except the motor ones (for a quadcopter with motors on 1–4 that is 16383 − 15 = 16368) | the outputs that work even with safety on. By default that is everything that is not a motor: gimbal servos, a gripper, a parachute move even with safety on. To make safety hold all outputs, write 0 explicitly |

While safety is on, the outputs that are not in `BRD_SAFETY_MASK` are silent (on Copter, by default, the motors): there is no PWM pulse, no DShot frames are sent, and arming is refused with `PreArm: Hardware safety switch`. The mask default is computed in `ArduCopter/radio.cpp` as "not motors" among outputs 1–14; until a frame is selected and there are no motors, it is 16383. The substitution applies only while the parameter has not been saved: the firmware does not touch a stored value, 0 included. Before working next to a vehicle that has a switch, read `BRD_SAFETY_MASK`: every set bit is an output that moves with safety on. If there is no switch and the parameter is 1, the outputs are "dead": set `BRD_SAFETY_DEFLT = 0`.

### Servos: rate and power
An analog servo needs 50 Hz; a digital one tolerates 200–333 Hz, so check its datasheet. The rate is set per group, so fast and slow servos go on different timers. Do not power servos from the flight controller's 5 V; you need a separate BEC with margin for the stall current: the calculation is in `el-power-design`, and the pulse anatomy and a bench check are in `bf-servos-pwm`. On some boards `BRD_PWM_VOLT_SEL` selects a 3.3 or 5 V signal amplitude.

### GPIO and relays
To make a pad a digital pin, set `SERVOn_FUNCTION = -1` or a bit in `SERVO_GPIO_MASK` and reboot the flight controller. The `BRD_PWM_COUNT` parameter, which used to split the outputs into PWM and GPIO, has been gone since Copter 4.2.0, although forums still recommend it. The pin number is set by `GPIO(g)` in the `hwdef`: on most boards main processor output 1 is 50, and the rest follow in order; MAIN on the IOMCU is 101–108; separate pins such as `PINIO1` on MatekH743 have their own numbers (81, 82) and do not need function −1. The numbering depends on the board, so check the `hwdef`. A pin's signal is a 3.3 V logic level and a few milliamps; the load is switched by a transistor or a ready-made relay module (`el-power-design`).

| Parameter | Default | Values |
|---|---|---|
| `RELAYn_FUNCTION` | 0 | 0 None; 1 Relay; 3 Parachute; 4 Camera; on Plane also 2 Ignition and 9 ICE Starter |
| `RELAYn_PIN` | −1, unless the board sets its own | the pin number; 1000–1015 are DroneCAN nodes |
| `RELAYn_DEFAULT` | 0 | 0 Off, 1 On, 2 NoChange at boot |
| `RELAYn_INVERTED` | 0 | 1 means "on" is a low level |

There are six relays. Before 4.5 the parameters were called `RELAY_PIN`, `RELAY_PIN2` … `RELAY_PIN6` and `RELAY_DEFAULT`; `RELAYn_FUNCTION` appeared in 4.5.0. Manual control works only with function 1:

- a switch: `RCx_OPTION` = 28 (relay 1), 34, 35, 36 (relays 2–4), 66, 67 (relays 5–6); on only in the high position (the thresholds and the first receiver frame are covered in `ap-aux-tune`);
- `MAV_CMD_DO_SET_RELAY`: the first parameter is the relay number from zero (0 is `RELAY1`), the second is 0 for off, 1 for on, anything else toggles; `DO_REPEAT_RELAY` gives a series;
- `MAV_CMD_DO_SET_SERVO`: the output number from one and the pulse in microseconds. It works on outputs with functions 0, 1, 22, 23, 28, 51–66, 140–155; on the others you get `ServoRelayEvent: Channel 7 is already in use`.

If `RELAYn_PIN` points to a pad that has not been switched to GPIO, arming is refused with `PreArm: RELAY1_PIN=58, set SERVO9_FUNCTION=-1`.

### Plane, QuadPlane, and moving from 4.6 to 4.7
Fixed-wing surfaces, `SERVO_AUTO_TRIM`, and in-flight tuning are in `ap-plane-tuning`; the motor and tilt servo layout of a QuadPlane and the analysis of the "motor on a servo channel" accident are in `ap-quadplane`. Setting up a plane from scratch (surface functions, the elevon and V-tail mixers, the two direction checks) is in `ap-setup-plane`.

Nothing in this area was renamed between 4.6.3 and 4.7.2 (the general table is in `ap-intro`). The Motor13–32 functions (160–179) were added, the `BRD_SAFETY_MASK` bit list was extended from 14 to 32 outputs (the Copter default is still computed over outputs 1–14 only, and the firmware reads only the low 16 bits of the mask), and `MOT_IDLE_SEC` appeared.

### Place in the system
- **Receives:** thrust requirements and motor numbers from the mixer (`ctl-allocation`), the pad map and the order of first setup from `ap-setup-scratch`, the ESC firmware and its capabilities from `f-esc-firmware`, and the servo power calculation from `el-power-design` and `bf-servos-pwm`.
- **Provides:** the signal to motors and servos; ESC RPM, current, and temperature to the notch filter (`ap-tuning`, `ap-heavy`) and to logs; GPIO pins and relays to the payload and to missions; the free UARTs remain for the OSD (`ap-osd-video`).
- **If you get it wrong here:** a servo in a group with DShot blocks arming, and in a group with PWM motors it silently burns out at 400 Hz; a wrong `SERVO_BLH_POLES` or BDShot mask moves the filter off the noise, and the vibration comes back in `ap-tuning`; an error in the motor numbers flips the vehicle on takeoff (`ap-setup-scratch`, `ap-quadplane`); counting on the safety switch to hold all outputs lets you down: a gripper or a parachute servo moves with safety on until 0 is written to `BRD_SAFETY_MASK`.

## practice
The lab is a calculation exercise: you need neither a flight controller nor a simulator. All parameter files below are a training example assembled by hand; they are not a dump from a real vehicle. Every answer follows from the tables and formulas in the theory.

The input data is the output table of the MatekH743 board from the Copter-4.7.2 source, the file `libraries/AP_HAL_ChibiOS/hwdef/MatekH743/hwdef.dat`, lines 145–157:

```
PB0  TIM8_CH2N TIM8  PWM(1)  GPIO(50)
PB1  TIM8_CH3N TIM8  PWM(2)  GPIO(51)
PA0  TIM5_CH1  TIM5  PWM(3)  GPIO(52)
PA1  TIM5_CH2  TIM5  PWM(4)  GPIO(53)
PA2  TIM5_CH3  TIM5  PWM(5)  GPIO(54)
PA3  TIM5_CH4  TIM5  PWM(6)  GPIO(55)
PD12 TIM4_CH1 TIM4 PWM(7) GPIO(56)
PD13 TIM4_CH2 TIM4 PWM(8) GPIO(57)
PD14 TIM4_CH3 TIM4 PWM(9) GPIO(58)
PD15 TIM4_CH4 TIM4 PWM(10) GPIO(59)
PE5  TIM15_CH1 TIM15 PWM(11) GPIO(60)
PE6  TIM15_CH2 TIM15 PWM(12) GPIO(61)
PA8 TIM1_CH1 TIM1 PWM(13) GPIO(62) # for WS2812 LED
```

All five timers of this build have a DMA channel, and the board has no IOMCU and no safety switch.

### Step 1. An output plan and three conflicts
The task: a quadcopter, four motors with DShot600, two analog 50 Hz servos (a gripper, function 28, and a gimbal tilt, function 7), a NeoPixel strip (120), and one relay.

(a) Write out the groups: which outputs are on which timer. (b) The motors are on outputs 1–4. Which outputs can no longer be given to servos? (c) Make a working plan. (d) Find the conflicts in the plan below, and for each name the message with which the firmware refuses to arm.

```
# training example, assembled by hand (a wrong plan)
MOT_PWM_TYPE,6
SERVO1_FUNCTION,33
SERVO2_FUNCTION,34
SERVO3_FUNCTION,35
SERVO4_FUNCTION,36
SERVO5_FUNCTION,28
SERVO7_FUNCTION,7
SERVO8_FUNCTION,120
SERVO9_FUNCTION,0
RELAY1_FUNCTION,1
RELAY1_PIN,58
```

Result. (a) TIM8 has outputs 1, 2; TIM5 has 3, 4, 5, 6; TIM4 has 7, 8, 9, 10; TIM15 has 11, 12; TIM1 has 13. (b) Outputs 5 and 6: they are on TIM5 together with motors 3 and 4, and the whole group runs DShot. (c) Motors 1–4; the gripper on 7 and the gimbal on 8 (TIM4, 50 Hz); the relay on output 9: `SERVO9_FUNCTION = -1`, `RELAY1_PIN = 58`; the strip on 13 (TIM1, alone in its group). Servos on 11 and 12 are a correct option too. (d) There are three conflicts:

| Line | Why it does not work | Message |
|---|---|---|
| `SERVO5_FUNCTION,28` | output 5 is in the TIM5 group with DShot motors, so it is disabled | `PreArm: SERVO5_FUNCTION=28 on disabled channel` |
| `SERVO8_FUNCTION,120` | the strip switches TIM4 to its own mode and disables the servo on output 7 | `PreArm: SERVO7_FUNCTION=7 on disabled channel` |
| `RELAY1_PIN,58` with `SERVO9_FUNCTION,0` | pin 58 is output 9, and it has not been switched to GPIO | `PreArm: RELAY1_PIN=58, set SERVO9_FUNCTION=-1` |

### Step 2. Bitmasks
Build: (a) `SERVO_BLH_BDMASK` for motors on outputs 1–4; (b) the same for a hexacopter with motors on outputs 1, 2, 3, 4, 7, 8; (c) `SERVO_BLH_MASK` for two cruise motors on outputs 9 and 10; (d) `BRD_SAFETY_MASK` so that outputs 7, 8, and 13 work with safety on. Decode: (e) `SERVO_BLH_RVMASK = 10`; (f) `SERVO_GPIO_MASK = 304`; (g) `BRD_SAFETY_MASK = 16383`.

Result: (a) 1 + 2 + 4 + 8 = 15; (b) 15 + 64 + 128 = 207; (c) 256 + 512 = 768; (d) 64 + 128 + 4096 = 4288; (e) 10 = 8 + 2, outputs 2 and 4; (f) 304 = 256 + 32 + 16, outputs 5, 6, and 9; (g) 16383 = 2^14 − 1, outputs 1 through 14. That is the number Copter substitutes by itself until a frame is selected; with motors on outputs 1–4 its default is 16383 − 15 = 16368, that is, outputs 5–14.

### Step 3. A servo pulse in the firmware's arithmetic
A surface servo (the "angle" type, full travel 4500): `SERVOn_MIN = 1000`, `SERVOn_MAX = 1900`, `SERVOn_TRIM = 1520`. Find the pulse for s = +1500, s = −1500, s = +1500 with `REVERSED = 1`, and s = +6000.

A flap servo (the "range" type, H = 100): `MIN = 1100`, `MAX = 1950`. Find the pulse for s = 33 and for s = 33 with `REVERSED = 1`.

Result. Angle: 1500 · 380 / 4500 = 126.67 → 126, so the pulse is 1520 + 126 = **1646**; 1500 · 520 / 4500 = 173.33 → 173, so the pulse is 1520 − 173 = **1347**; the reversal flips the sign, giving the same **1347**; 6000 is constrained to 4500, giving **1900**. Range: 33 · 850 / 100 = 280.5 → 280, so the pulse is **1380**; with the reversal s = 67: 67 · 850 / 100 = 569.5 → 569, so the pulse is **1669**. The sum 1380 + 1669 = 3049, not 3050: both fractions were truncated.

### Step 4. Three errors in a parameter file
A quadcopter on MatekH743-bdshot, motors on outputs 1–4, ESCs with BLHeli32, 12N14P motors (14 poles). Motors 2 and 4 have to be reversed with a DShot command, and the filter needs the RPM of all four. A gripper on output 7, and a relay on output 9 from a switch on channel 8. Find the lines because of which the vehicle will not arm or will not work as intended.

```
# training example, assembled by hand
MOT_PWM_TYPE,6
RC_SPEED,490
SERVO_RATE,50
SERVO_DSHOT_ESC,0
SERVO_DSHOT_RATE,2
SERVO_BLH_AUTO,1
SERVO_BLH_BDMASK,3
SERVO_BLH_POLES,14
SERVO_BLH_RVMASK,10
SERVO7_FUNCTION,28
SERVO7_MIN,1600
SERVO7_TRIM,1500
SERVO7_MAX,1900
SERVO9_FUNCTION,-1
RELAY1_FUNCTION,1
RELAY1_PIN,58
RC8_OPTION,28
BRD_SAFETY_DEFLT,0
INS_HNTCH_MODE,3
```

Result: there are exactly three errors. (1) `SERVO_DSHOT_ESC = 0`: DShot commands are not sent, so `SERVO_BLH_RVMASK = 10` does not reverse motors 2 and 4; it must be 1. (2) `SERVO_BLH_BDMASK = 3`: RPM comes only from motors 1 and 2; it must be 15. (3) `SERVO7_MIN = 1600` is greater than `SERVO7_TRIM = 1500`: arming is refused with `PreArm: SERVO7_MIN is greater than SERVO7_TRIM`. The rest is correct: `RC_SPEED` is not used with DShot, `SERVO_DSHOT_RATE = 2` with a 400 Hz loop gives 800 Hz, the relay on pin 58 with output 9 in GPIO mode and switch function 28 is set up properly, and `BRD_SAFETY_DEFLT = 0` is what a board without a switch needs (`BRD_SAFETY_MASK` has no effect without a switch).

In addition: the ESC reports E = 1470 (147 000 eRPM). The RPM with 14 poles: 1470 · 200 / 14 = **21000 RPM**, that is, 350 Hz. If `SERVO_BLH_POLES` were 12, the firmware would calculate 24500 RPM (408 Hz) and put the filter 58 Hz above the real noise.

### Moving to real hardware
The propellers are off for the whole check; servos and the strip are powered from a separate BEC, not from the flight controller's 5 V.

1. Save the full parameter list to a file. Find your board's `hwdef.dat` and write out the groups as in step 1.
2. Assign the functions, reboot the flight controller, and read the `RCOut:` line in Messages: the mode of every output must match the plan.
3. Download `@SYS/timers.txt` over MAVFTP and compare the `MODE` field of every timer with the plan.
4. Motor Test at 5–10%: motor order and direction (`ap-setup-scratch`). With BDShot, record a short log on the bench: in the `ESC` message the `RPM` field is nonzero for every motor, and `Err` is close to zero.
5. Relay: flick the switch and measure the level on the pad with a multimeter.
6. Passthrough: disarmed, the ground station disconnected, and the ESC configuration program sees all four ESCs.

On hardware the work is done when the `RCOut:` line matches the plan, Messages has no `Chan … failed` lines and no `PreArm` failures about outputs, every motor reports RPM, and the relay changes the level on the pad.

Self-check: the lab is done when:
- step 1: the groups are {1, 2}, {3, 4, 5, 6}, {7, 8, 9, 10}, {11, 12}, {13}; outputs 5 and 6 are lost for servos; exactly three conflicts are found in the wrong plan (output 5, the strip on output 8, pin 58 without GPIO), and the three messages from the table are named;
- step 2: the values 15, 207, 768, 4288 and the decodings "2 and 4", "5, 6, and 9", "1–14" match exactly;
- step 3: 1646, 1347, 1347, 1900, 1380, and 1669 µs match exactly, with no tolerance;
- step 4: exactly three errors are found (ESC type 0, mask 3 instead of 15, `MIN` greater than `TRIM`); the RPM of 21000 and 350 Hz match exactly, and for 12 poles 24500 RPM and 408 Hz (tolerance ±1 Hz).

**Reference for the self-check.** The correct result is the numbers and lines from the four items above. Typical mistakes: (1) in step 3 you got 1647 and 1381: the fraction was rounded, while the firmware truncates it; or you got 1670 for the reversed flap, calculated as `MIN + MAX − 1380`, when you have to substitute s = 67 again. (2) In step 1 the servos were left on outputs 5 and 6 because "the motors are only on 1–4": the mode is set per timer, and TIM5 is shared by outputs 3–6; or the strip was put on the free output 9 or 10 next to the servos, where it disables them too. (3) In step 2 the mask for outputs 9 and 10 came out as 1536: the weight 2^n was used instead of 2^(n − 1). (4) In step 4 `RC_SPEED = 490` or `BRD_SAFETY_DEFLT = 0` was named as an error: the first has no effect with DShot, and the second is mandatory for a board without a switch; or the RPM came out as 10500: E was multiplied by 100 and divided by the number of poles, not by the number of pole pairs.

## diagnostics
- **Symptom:** arming is refused: `PreArm: SERVOn_FUNCTION=… on disabled channel`.
  Possible cause: the output is in the same timer group as a DShot motor or a NeoPixel/ProfiLED strip and has been disabled by the firmware.
  What to do: write out the groups from `hwdef.dat`, move the servo to a group without digital outputs, reboot; check the `RCOut:` line.
- **Symptom:** after boot Messages has a `Chan x to y, …: failed, no DMA` line (or `failed to allocate DMA`, `failed to match clock speed`), and the motors on those outputs do not respond to DShot.
  Possible cause: the group's timer did not get a DMA channel; on some boards it is taken by another peripheral.
  What to do: move the motors to groups where DShot comes up; for a strip choose the output marked for LEDs in the `hwdef`; replace DShot1200 with DShot600.
- **Symptom:** a servo hums and gets hot although there are no errors.
  Possible cause: it is in the same group as a PWM motor, and the group runs at the motor rate (up to 400 Hz) instead of `SERVO_RATE`; or `SERVO_RATE` is too high for an analog servo.
  What to do: put motors and servos on different timers; keep 50 Hz for analog servos.
  Consequences: overheating and a servo failure in flight.
- **Symptom:** the motors do not respond to Motor Test, and the ESCs beep "no signal".
  Possible cause: `BRD_SAFETY_DEFLT = 1` on a board without a switch, or the switch was not pressed; no reboot after changing `MOT_PWM_TYPE`; motors on MAIN of a board with an IOMCU using DShot without `BRD_IO_DSHOT = 1`.
  What to do: check Messages for `PreArm: Hardware safety switch`; hold the switch for about a second or set `BRD_SAFETY_DEFLT = 0`; for an IOMCU set `BRD_IO_DSHOT` or move the motors to AUX.
- **Symptom:** the safety switch has not been pressed, the motors are silent, but a gimbal servo, a gripper, or a parachute servo moves.
  Possible cause: this is the Copter default: `BRD_SAFETY_MASK` was never set, and the firmware substituted "all outputs 1–14 except the motor ones" (16368 with motors on 1–4).
  What to do: read `BRD_SAFETY_MASK` and break it into bits; if safety must hold all outputs, write 0 and reboot; if you need some servos in the pre-flight check, leave only their bits.
  Consequences: a gripper or a parachute actuates on the ground with safety on.
- **Symptom:** the `SERVO_BLH_BDMASK` parameter is not in the list.
  Possible cause: a build without bidirectional DShot: the board has a separate `-bdshot` variant; or this is SITL.
  What to do: flash the `-bdshot` variant for your board and redo the output plan, because its timers and available UARTs are different.
- **Symptom:** BDShot is enabled, but in `ESC` the `RPM` field is zero or `Err` is tens of percent.
  Possible cause: the mask has no bit for that output; the ESC firmware has no bidirectional DShot; long signal wires without a shared ground.
  What to do: check `SERVO_BLH_BDMASK` bit by bit; update the ESC (`f-esc-firmware`); run a ground next to the signal; try the slower DShot300.
  In the log: `ESC.Err` rises with throttle, which is interference from the power wiring.
- **Symptom:** the RPM in the log is 15–20% off from what you expect, and the notch filter does not remove the peak.
  Possible cause: `SERVO_BLH_POLES` does not equal the number of motor magnets.
  What to do: count the magnets on the bell, set the value, and reboot; compare the frequency `RPM / 60` with the peak in the spectrum (`ap-tuning`).
- **Symptom:** a motor spins the wrong way, and `SERVO_BLH_RVMASK` does not help.
  Possible cause: `SERVO_DSHOT_ESC = 0`, so commands are not sent; the protocol is not DShot; the output is neither a motor nor in `SERVO_BLH_MASK`.
  What to do: set ESC type 1 or 2 and reboot; the command goes out while disarmed within a few seconds. Otherwise swap two motor wires or change the direction in the ESC program.
- **Symptom:** passthrough does not see the ESCs.
  Possible cause: `SERVO_BLH_AUTO = 0` and an empty `SERVO_BLH_MASK`; the vehicle is armed; the ESCs are on IOMCU outputs; a ground station is connected to the port; the ESCs are not powered from the battery.
  What to do: set `SERVO_BLH_AUTO`, reboot, close the ground station, connect the battery (propellers off). The passthrough code is in every build for ChibiOS boards, including an F405 with 1 MB of flash, so on "racing" boards the cause is one of the conditions above, not a cut-down firmware.
- **Symptom:** the relay does not click, and arming is refused: `PreArm: RELAY1_PIN=58, set SERVO9_FUNCTION=-1` or `RELAY1_PIN=… invalid`.
  Possible cause: the pad has not been switched to GPIO; the pin number is from a different board; forum advice about `BRD_PWM_COUNT`, which has not existed since 4.2.
  What to do: set function −1 on the output named in the message and reboot; take the pin number from `GPIO(g)` in your board's `hwdef`.
- **Symptom:** the relay is set up and there are no failures, but the switch and `DO_SET_RELAY` have no effect.
  Possible cause: `RELAYn_FUNCTION` is not 1; the switch is in the middle position (only the high one turns it on); the command uses a relay number from one instead of from zero.
  What to do: check the function, the switch position on the radio page, and the first parameter of the command.
- **Symptom:** `DO_SET_SERVO` in a mission does not move the servo, and Messages shows `ServoRelayEvent: Channel n is already in use`.
  Possible cause: the output has a function that the firmware controls itself.
  What to do: set the output's function to 0 or to a channel passthrough (1, 51–66); for a gripper use the gripper command.

## checklist
- The groups are written out from the `hwdef.dat` of exactly the build that is flashed (the ordinary and `-bdshot` builds differ)
- Groups with DShot and a strip have no servos or other PWM functions
- The strip is not in the same group as motors (the absence of a `PreArm` does not prove that)
- PWM motors and analog servos do not share a timer
- `MOT_PWM_TYPE` and `SERVO_DSHOT_ESC` are set, and there was a reboot after the change
- `SERVO_BLH_BDMASK` covers all the motors, and `SERVO_BLH_POLES` equals the number of magnets
- The `RCOut:` line in Messages matches the plan, and there are no `Chan … failed` lines
- `BRD_SAFETY_DEFLT` matches the board: 0 without a switch
- On a board with a switch, `BRD_SAFETY_MASK` has been read and broken into bits: with safety on, only the outputs you chose yourself move (0 means none)
- Every relay has `RELAYn_FUNCTION`, `RELAYn_PIN`, and function −1 on the corresponding output
- `SERVOn_MIN` ≤ `SERVOn_TRIM` ≤ `SERVOn_MAX` on every output with a function
- Servos and the strip are powered from a separate BEC with a shared ground

## references
- ArduPilot Copter-4.7.2 SRV_Channel.h (SERVOn_FUNCTION function numbers) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/SRV_Channel/SRV_Channel.h | primary | A
- ArduPilot Copter-4.7.2 SRV_Channel.cpp (MIN/MAX/TRIM/REVERSED, conversion to microseconds) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/SRV_Channel/SRV_Channel.cpp | primary | A
- ArduPilot Copter-4.7.2 SRV_Channels.cpp (SERVO_RATE, SERVO_DSHOT_RATE, SERVO_DSHOT_ESC, SERVO_GPIO_MASK) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/SRV_Channel/SRV_Channels.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_HAL_ChibiOS RCOutput.cpp (groups, rates, DShot, error messages, timers.txt, safety) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_HAL_ChibiOS/RCOutput.cpp | primary | A
- ArduPilot Copter-4.7.2 hwdef MatekH743 (the output and timer table) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_HAL_ChibiOS/hwdef/MatekH743/hwdef.dat | primary | A
- ArduPilot Copter-4.7.2 AP_BLHeli.cpp (SERVO_BLH_*, passthrough, eRPM conversion) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_BLHeli/AP_BLHeli.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_Motors_Class.cpp (MOT_PWM_TYPE and output modes) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_Motors/AP_Motors_Class.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_Arming.cpp (pre-arm output checks) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_Arming/AP_Arming.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_Relay.cpp and AP_Relay_Params.cpp (RELAYn_*, pin checks) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_Relay/AP_Relay.cpp | primary | A
- ArduPilot Copter-4.7.2 ArduCopter radio.cpp (the BRD_SAFETY_MASK default: all non-motor outputs 1–14) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/ArduCopter/radio.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_BoardConfig.cpp (BRD_SAFETY_*, BRD_IO_DSHOT, BRD_PWM_VOLT_SEL) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_BoardConfig/AP_BoardConfig.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_ESC_Telem LogStructure.h (the ESC and EDT2 messages) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_ESC_Telem/LogStructure.h | primary | A
- ArduPilot Copter-4.7.2 ReleaseNotes.txt (BRD_PWM_COUNT removed in 4.2.0, RELAYx_FUNCTION and DShot on the IOMCU in 4.5.0) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/ArduCopter/ReleaseNotes.txt | primary | A
- DShot and Bi-directional DShot — ArduPilot Copter | https://ardupilot.org/copter/docs/common-dshot-escs.html | primary | A
- BLHeli32, AM32 and BLHeli_S ESCs (passthrough) — ArduPilot | https://ardupilot.org/copter/docs/common-blheli32-passthru.html | primary | A

## notes
Everything the module describes as "per the source" was checked in the tree of the Copter-4.7.2 tag; the numbers "133 boards with `BIDIR`" and "35 `-bdshot` builds" are a count over the `hwdef` directory of that tag. Three things are not confirmed by the source and are taken as common practice: the working rates of digital servos (200–333 Hz; check the datasheet of the specific servo), the set of ESC configuration programs compatible with passthrough, and the names of ground station screens (in Mission Planner the outputs are configured on the Servo Output page). The ArduPilot wiki pages in the reference list could not be opened while the module was being prepared; no facts were taken from them.
