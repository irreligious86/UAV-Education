---
id: ap-notify
title: "LEDs and buzzer in ArduPilot: NTF_*, NeoPixel/ProfiLED, buzzer, DShot beacon"
level: L2
readingTime: 45 min
firmware: ArduCopter 4.7 (checked against 4.7.3)
status: published
added: 2026-11-22
tags:
  - ArduPilot
  - AP_Notify
  - NTF_LED_TYPES
  - NeoPixel
  - ProfiLED
  - buzzer
  - DShot beacon
related:
  - ap-outputs
  - ap-aux-tune
  - ap-safety-fs
  - ap-setup-scratch
  - ap-lua
  - ap-osd-video
  - el-power-design
  - bf-led-buzzer
  - inav-led-pinio-beeper
  - px4-hardware-peripherals
next:
  - ap-osd-video
source: content/ardupilot/ap-notify.md
source_hash: 8601ace304cf
---

## summary
The LED and the buzzer are the only things that report the state of the flight controller when there is neither a ground station nor an OSD nearby: whether it has passed the pre-arm checks, whether it has a position, whether a failsafe has triggered. Working from the ArduCopter 4.7.2 source, this module goes through the `AP_Notify` library: every `NTF_*` parameter, the bits of `NTF_LED_TYPES` and `NTF_BUZZ_TYPES`, the table of colors and rhythms exactly as the sequences in `RGBLed.h` define it, the tunes from `ToneAlarm.cpp`, NeoPixel and ProfiLED strips on outputs 120–123 and 129–132, LEDs driven from a Lua script, motor beeps over DShot, and the lost vehicle sound. After the module you can name the vehicle state and your action from a color and a rhythm, build the masks for specific hardware, and place a strip so that it does not disable your servos. The lab is a calculation exercise with no hardware and no simulator: masks, six LED patterns, a strip plan for a MatekH743, and three mistakes in a parameter file.

## theory
### What is in the module and in what order to read it
First the structure of `AP_Notify` and the overall table of `NTF_*` parameters. Then the LEDs: the bits of `NTF_LED_TYPES`, the color table of the RGB LED, boards with one or two plain LEDs, NeoPixel and ProfiLED strips, and color control from a script and over MAVLink. Then sound: the two different buzzer drivers, the table of tunes, motor beeps over DShot and finding a crashed vehicle. At the end come the I2C display, a selection table by vehicle class, and the differences between 4.7 and 4.6. Timer groups are not repeated here: they are covered in `ap-outputs`, and this module only refers to them. The same topic in other firmware: `bf-led-buzzer` (Betaflight), `inav-led-pinio-beeper` (INAV), `px4-hardware-peripherals` (PX4); their colors and tunes are their own, and you cannot carry them over from memory.

### How `AP_Notify` is built
The library has three layers.

1. **Flags and events.** The rest of the firmware knows nothing about colors or tunes. It sets state flags (`initialising`, `armed`, `pre_arm_check`, `pre_arm_gps_check`, `failsafe_radio`, `failsafe_battery`, `failsafe_gcs`, `ekf_bad`, `gps_glitching`, `vehicle_lost` and others) and one-shot events (`arming_failed`, `user_mode_change`, `failsafe_mode_change`, `waypoint_complete`, `mission_complete`).
2. **Devices.** At boot the LED drivers are created from the bits of `NTF_LED_TYPES`, then the display and the sound drivers. Each driver reads the same flags 50 times a second and decides by itself what to show.
3. **Hardware.** A GPIO pin, an I2C bus, an output with a strip, a DShot command, a DroneCAN node.

Two practical conclusions follow. First, all RGB devices (the board LED, the I2C LED in a GPS module, a NeoPixel strip, ESC LEDs) show **the same thing**, because they inherit one class, `RGBLed`. Second, the set of devices is assembled once at boot, so a change of `NTF_LED_TYPES`, `NTF_BUZZ_TYPES`, `NTF_BUZZ_PIN` or `NTF_LED_LEN` needs a reboot.

{{diagram:ap-notify-paths|All devices read the flags and events at once: RGB LEDs of any type show one sequence, while motor beeps and ESC LEDs work only when disarmed.}}

### The `NTF_*` parameters
| Parameter | Default | Values | Meaning and selection rule |
|---|---|---|---|
| `NTF_LED_TYPES` | board dependent: 123079 in SITL; 257 or 455 on many boards with a pad for a strip | bitmask, bits 0–19 | which LED drivers to create. Add a bit only for hardware that is actually fitted |
| `NTF_LED_BRIGHT` | 3 | 0 Off, 1 Low, 2 Medium, 3 High | brightness of RGB devices. When USB is connected the brightness is never higher than Low, whatever the setting. For a strip on the flight controller BEC use 1 or 2 |
| `NTF_LED_OVERRIDE` | 0 | 0 Standard, 1 MAVLink / Scripting / AP_Periph, 2 OutbackChallenge, 3 TrafficLight | the color source. 0 if the pilot watches the LED; 3 if people work around the vehicle; 1 only together with a script or ground station commands |
| `NTF_LED_LEN` | 1 | 1–32 | the number of LEDs in the strip on each NeoPixel or ProfiLED output. Set the actual count |
| `NTF_BUZZ_TYPES` | 5 on boards with CAN, otherwise 1 | bitmask: bit 0 Built-in buzzer, bit 1 DShot, bit 2 DroneCAN | which buzzers are active; 0 turns sound off entirely |
| `NTF_BUZZ_PIN` | −1 unless the board sets its own | GPIO pin number | an active buzzer on an arbitrary pin. The driver treats −1 and 0 as no buzzer |
| `NTF_BUZZ_ON_LVL` | 1 | 0 LowIsOn, 1 HighIsOn | the pin level at which the buzzer on `NTF_BUZZ_PIN` sounds |
| `NTF_BUZZ_VOLUME` | 100 % | 0–100 | the volume of the tunes (a multiplier of the PWM duty cycle); it has no effect on the `NTF_BUZZ_PIN` buzzer |
| `NTF_DISPLAY_TYPE` | 0 | 0 Disable, 1 ssd1306, 2 sh1106, 10 SITL | the I2C display |
| `NTF_OREO_THEME` | 0 | 0 Disabled, 1 Aircraft, 2 Rover | the 3DR Solo LEDs; the parameter does not exist in ordinary builds |

Nothing in this group was renamed between 4.6 and 4.7.

### The bits of `NTF_LED_TYPES` and `NTF_BUZZ_TYPES`
The value of a mask is the sum of 2^n over the bits that are set.

| Bit | Weight | Driver | When to set it |
|---|---|---|---|
| 0 | 1 | Built-in LED | the LEDs on the board itself |
| 1 / 2 | 2 / 4 | ToshibaLED: internal / external I2C bus | the RGB LED in older GPS modules |
| 3 | 8 | PCA9685, external bus | a PCA9685 expansion board |
| 4 | 16 | Oreo LED | 3DR Solo only |
| 5 | 32 | DroneCAN | the LED in a GPS module on the CAN bus |
| 6 / 7 | 64 / 128 | NCP5623: external / internal bus | the RGB LED in current I2C GPS modules |
| 8 | 256 | NeoPixel | a WS2812B or SK6812 strip |
| 9 | 512 | ProfiLED | a ProfiLED strip with a clock line |
| 10 | 1024 | Scripting | the color is not output but handed to a script: `LED:get_rgb()` |
| 11 | 2048 | DShot | LEDs on the ESCs through DShot commands |
| 12 | 4096 | ProfiLED_SPI | only boards whose `hwdef` defines it |
| 13 / 14 | 8192 / 16384 | LP5562: external / internal bus | per the GPS module documentation |
| 15 / 16 | 32768 / 65536 | IS31FL3195: external / internal bus | per the GPS module documentation |
| 17 | 131072 | DiscreteRGB | three separate pins, defined in the `hwdef` |
| 18 | 262144 | NeoPixelRGB | a strip with RGB color order (WS2811): set it instead of bit 8 if red shows as green |
| 19 | 524288 | ProfiLED_IOMCU | new in 4.7: an LED through the IO coprocessor on CubeBlack, CubeOrange, CubeYellow |

The default of a generic build is bit 0 plus all the I2C drivers: 1 + 2 + 4 + 64 + 128 + 8192 + 16384 + 32768 + 65536 = 123079. That is why the I2C LED of a GPS module usually works with no configuration. Bit 5 (DroneCAN) is not part of the default and is added by hand. Boards with a pad for a strip often set their own default: 257 (bit 0 and NeoPixel) or 455 (257 plus ToshibaLED and NCP5623).

`NTF_BUZZ_TYPES`: bit 0 is the built-in buzzer, bit 1 is motor beeps over DShot, bit 2 is a buzzer on a DroneCAN node. In the source, bit 0 is not tested separately: the built-in buzzer sounds for any nonzero mask, and 0 disables it together with everything else. The rule: 1 if there is only the board buzzer; 3 to add motor beeps; keep bit 2 if the GPS module is on CAN and has its own buzzer.

### RGB LED colors: the table of states
A sequence is ten steps of 100 ms, a cycle of exactly 1 s (`RGBLed.cpp`: `step = (millis()/100) % 10`). The rows are in priority order: the firmware tests the conditions from top to bottom and takes the first that matches.

| No. | State | Pattern over 1 s | What to do |
|---|---|---|---|
| 1 | Initialising (gyro calibration at boot) | red and blue alternate every 0.1 s | do not touch or move the vehicle |
| 2 | Save trim, ESC calibration, compass calibration, temperature calibration | red, blue, green for 0.1 s each, three times, then 0.1 s dark | finish the procedure |
| 3 | Leak detected (ArduSub) | 0.5 s yellow, 0.5 s white | — |
| 4 | EKF bad (`ekf_bad`) | 0.5 s yellow, 0.5 s red | do not select position-controlled modes, land manually (`ap-ekf`, `ap-safety-fs`) |
| 5 | GPS glitch (`gps_glitching`) | 0.5 s yellow, 0.5 s blue | the same; wait for recovery |
| 6 | Radio, battery or GCS failsafe | 0.5 s yellow, 0.5 s dark | the LED does not tell which one: read the ground station message and listen to the tune |
| 7 | Armed, 3D fix and a valid position | solid green | — |
| 8 | Armed with no fix or no position | solid blue | RTL, Loiter and Auto are not available |
| 9 | Disarmed, pre-arm checks failing | a double yellow flash: 0.2 s on, 0.2 s dark, 0.2 s on, 0.4 s dark | read `PreArm: …` in Messages; do not disable the checks |
| 10 | Disarmed, ready, a fix of DGPS level or better (RTK included) | green, 0.1 s on and 0.1 s dark | you may arm in any mode |
| 11 | Disarmed, ready, 3D fix | green, 0.5 s on and 0.5 s dark | you may arm in any mode |
| 12 | Disarmed, ready, but no fix or no position | blue, 0.5 s on and 0.5 s dark | arm only in modes that need no position |

Clarifications from the source.

- Rows 3–6 apply both armed and disarmed: flashing yellow in flight is always a failure of one of four kinds.
- A "valid position" means the AHRS returns a location and has its origin set. Rows 10 and 11 additionally need the `pre_arm_gps_check` flag.
- When armed, the pre-arm checks are not shown: row 9 is possible only when disarmed.
- In Plane the `armed` flag is also set when arming is not required (`ARMING_REQUIRE = 0`), and `pre_arm_gps_check` is always true.

{{diagram:ap-notify-led-states|Twelve states in priority order, each cell is 100 ms. Only the failures have yellow in the first half of the second, and only failing checks have the double yellow flash.}}

The other values of `NTF_LED_OVERRIDE`:

| Value | What it shows |
|---|---|
| 2 OutbackChallenge | solid red is armed, solid green is disarmed; nothing else |
| 3 TrafficLight | armed: red 0.5 / 0.5 s; disarmed with the safety switch not suppressing outputs: yellow; disarmed with outputs suppressed: green. A 0.5 / 0.5 s rhythm means the checks pass, 0.1 / 0.1 s means they fail. A board with no safety switch never shows green |
| 1 MAVLink / Scripting | only a script and the `LED_CONTROL` message set the color; until they do, the LED is dark |

### Plain board LEDs and the safety switch LED
On a board with no RGB LED, bit 0 enables one of two drivers. Colors encode nothing here, only the rhythm does.

| State | Two LEDs (for example MatekH743: green and blue) | One LED: 100 ms step, 3.2 s cycle |
|---|---|---|
| Initialising | the first flickers rapidly | 0.1 s on / 0.1 s dark |
| Disarmed, checks failing | the first gives a double flash | two flashes per cycle: 0.9 s and 0.4 s |
| Disarmed, ready | the first gives even single flashes | 1.5 s on, 1.7 s dark |
| Armed | the first is solid | solid |
| Failsafe | when armed the first blinks: battery at about 1 Hz, radio or GCS at about 2 Hz | 0.4 s on / 0.4 s dark, priority above armed |
| GPS | the second: dark with no fix, with a fix a series of flashes equal to the number of satellites minus 6 | not shown |

On the MatekH743 the first LED is green and the second is blue (`hwdef.dat`, lines 92–99).

The LED in the safety switch is driven separately from `AP_Notify`: a 100 ms step and a 1.6 s cycle. Outputs blocked: four 0.1 s flashes 0.1 s apart and a 0.9 s pause; block released: solid. What exactly the switch blocks is covered in `ap-outputs`.

### NeoPixel and ProfiLED as a status LED
A strip on a flight controller output becomes one more RGB device: all of its LEDs show the color from the table of states at the same time.

1. The output: `SERVOn_FUNCTION` = 120–123 (NeoPixel1–4), or 129–131 (ProfiLED1–3) plus one output set to 132 (ProfiLEDClock). Without an output with function 132 a ProfiLED strip does not start, and the clock line must be in the same timer group as the data.
2. The type: bit 8 or 18 (NeoPixel) or bit 9 (ProfiLED) in `NTF_LED_TYPES`.
3. The length: `NTF_LED_LEN`.
4. A reboot. In the `RCOut:` line of the banner the output must get the mode `NeoP` or `ProfiLED` (`ap-outputs`).

Limitations.

- **Timer group.** A strip switches the whole timer to its mode; ordinary outputs of the same group (servos, PWM) are disabled with the message `PreArm: SERVOn_FUNCTION=… on disabled channel`. The rules and the group layout are in `ap-outputs`. Put the strip on an output that the `hwdef` marks for LEDs, or in a group with nothing else in it.
- **Warning: a strip in a group with motors.** Never put a strip in a group with DShot motors: there is one timer and it has one mode, so a motor of that group gets the strip signal instead of DShot. The strip sets its mode again on every update, so DShot does not win it back. The pre-arm check does **not** catch this: motor outputs are excluded from it, arming succeeds, and the motor does not start or stops. This conclusion comes from reading `RCOutput.cpp` and `AP_Arming.cpp` and was not tested on hardware. How to avoid it: before you assign function 120–123 or 129–132, find the output in the group table of your board (`ap-outputs`, the `RCOut:` line of the banner) and make sure no output of that group has a motor function (33–40, 82–85, 160–179); on the MatekH743 that is output 13 (TIM1) or 11–12 (TIM15).
- **Length.** The documented range of `NTF_LED_LEN` is 1–32. The software limit of the serial LED library is 128 LEDs per output (126 for ProfiLED), which scripts need.
- **Power.** The course uses 0.06 A per LED at full white and a BEC of at least 1.5 × the sum of the branch currents (`el-power-design`); one color channel draws about 20 mA (`bf-led-buzzer`). The table of states uses one channel (red, green, blue) or two (yellow); white occurs only in ArduSub and in scripts. `NTF_LED_BRIGHT` sets the brightness byte of the strip: 1 is 51, 2 is 127, 3 is 255 out of 255. Size the supply by the course rule and not by yellow: one script with white, and a budget based on "actual use" no longer holds.
- **Signal level.** The pad outputs 3.3 V, while an LED powered from 5 V needs at least 0.7 · 5 = 3.5 V (`bf-led-buzzer`). If the strip flickers or stays dark, the ArduPilot documentation suggests a silicon diode in the positive supply of the strip.
- **A board with no assigned output.** In 4.7 a board can define the strip output directly in its `hwdef`; the strip then works without function 120.

### LEDs from a script and over MAVLink
Scripts need `SCR_ENABLE = 1` (how to enable them and where the files go is in `ap-lua`). There are three ways.

| What you need | Tool | Condition |
|---|---|---|
| Your own color on all status devices | `notify:handle_rgb(r, g, b, rate_hz)`; `rate_hz = 0` is solid, otherwise it blinks at that rate | `NTF_LED_OVERRIDE = 1` |
| Your own strip with individual pixels | `serialLED:set_num_neopixel(chan, n)` (also `set_num_neopixel_rgb`, `set_num_profiled`), `serialLED:set_RGB(chan, i, r, g, b)`, `serialLED:send(chan)` | a strip output with function 94–109 (Script1–16); `chan` is the output number 1–16; `i` is the LED index from zero, −1 means all |
| Drawing the standard state on your own strip | `LED:get_rgb()` returns the current status color | bit 10 in `NTF_LED_TYPES` |

`SRV_Channels:find_channel(94)` returns the output number from zero, so `serialLED` gets the result plus 1. The scripting outputs 94–109 are among the exceptions of the "disabled channel" check (`ap-outputs`), but the strip occupies the timer in exactly the same way.

The ready-made applet `leds_on_a_switch.lua` does not change the color: with a switch on `RCx_OPTION = 300` it changes `NTF_LED_BRIGHT`; the low position turns the LEDs off, the middle one sets brightness Low, the high one sets full brightness.

Over MAVLink the color is set by the `LED_CONTROL` message: three RGB bytes and an optional fourth, the blink rate in hertz. It too works only with `NTF_LED_OVERRIDE = 1`. A tune is played by the `PLAY_TUNE` message (id 258) or by `notify:play_tune()` from a script; the string length in the firmware is up to 99 characters. Firmware 4.7.2 does not handle `PLAY_TUNE_V2`.

### Sound: two drivers and the table of tunes
The firmware has two independent buzzers.

| | Tunes (`AP_ToneAlarm`) | Active buzzer (`Buzzer`) |
|---|---|---|
| What is connected | the BUZZ pad of a board whose `hwdef` has an `ALARM` pin (PWM), or an output with `SERVOn_FUNCTION` = 138 Alarm or 139 Alarm Inverted; motor beeps and DroneCAN belong here too | an active buzzer (with a built-in oscillator) on the `NTF_BUZZ_PIN` pin |
| What it plays | tunes with notes (the table below) | an on/off pattern in 100 ms steps |
| Parameters | `NTF_BUZZ_TYPES`, `NTF_BUZZ_VOLUME` | `NTF_BUZZ_PIN`, `NTF_BUZZ_ON_LVL` |

How to choose. If the board has a BUZZ pad, connect the buzzer to it and configure nothing. If it has none, use either an active buzzer on a free GPIO pin (through a MOSFET, or a three-pin buzzer: the parameter description requires this explicitly) or function 138 on a free output; such an output occupies a whole timer (`ap-outputs`).

The patterns of the active buzzer: gyro calibration at boot finished, seven short beeps; arming, continuous for 3 s; disarming and an arming failure, one 0.1 s beep; checks passed, three short beeps and one long 1 s beep; EKF bad, a "long, medium, short, short" series; battery failsafe, a single beep repeating every 3.3 s; lost vehicle, a double beep repeating every 3.3 s.

The tunes of `ToneAlarm.cpp` (the name is as in the source, without the `AP_NOTIFY_TONE_` prefix):

| Event | Tune | What it sounds like |
|---|---|---|
| Boot | `STARTUP` | a long startup tune |
| Boot with no SD card | `NO_SDCARD` | instead of the startup tune, three notes B, G, G |
| Pre-arm checks passed | `QUIET_READY_OR_FINISHED` | three rising notes |
| Checks stopped passing (after they had passed) | `QUIET_NOT_READY_OR_NOT_FINISHED` | three falling notes |
| Arming | `QUIET_ARMING_WARNING` | one low tone of about 3 s |
| Disarming | `QUIET_NEU_FEEDBACK` | one short tone |
| Arming failed | `QUIET_NEG_FEEDBACK` | two low tones |
| Mode changed on the pilot's command | `LOUD_NEU_FEEDBACK` when armed, `QUIET_NEU_FEEDBACK` when disarmed | one tone |
| Mode change refused | `LOUD_NEG_FEEDBACK` / `QUIET_NEG_FEEDBACK` | two tones, repeated |
| A failsafe changed the mode (armed) | `LOUD_ATTENTION_NEEDED` | four identical high tones |
| Radio or GCS loss while disarmed | `QUIET_NEG_FEEDBACK` | two low tones |
| Link restored | `LOUD_POS_FEEDBACK` / `QUIET_POS_FEEDBACK` | two rising tones |
| Battery failsafe | `LOUD_BATTERY_ALERT_CTS` | rapid high tones with no pauses, **repeated until disarm** |
| EKF failsafe (Copter) | `EKF_ALERT` | high tones in groups of four, repeated |
| Waypoint reached | `LOUD_WP_COMPLETE` | two short tones |
| Mission or AutoTune complete (armed) | `LOUD_READY_OR_FINISHED` | three rising notes, loud |
| Parachute released | `LOUD_ATTENTION_NEEDED` | four high tones |
| Lost vehicle | `LOUD_VEHICLE_LOST_CTS` | a long high tone, repeated |
| Waiting for the throw (Throw mode) | `WAITING_FOR_THROW` | three notes and a pause, repeated |
| Compass calibration running | `QUIET_CALIBRATING_CTS` | an occasional short tone, repeated |
| Calibration saved / failed | `QUIET_READY_OR_FINISHED` / `QUIET_NEG_FEEDBACK` | three rising notes / two low tones |
| Power shutdown | `QUIET_SHUTDOWN` | a short fast tune |

The loud tunes (`LOUD_`) are written an octave above the base octave, the quiet ones (`QUIET_`) below it. A repeating tune is interrupted by any other tune and resumes after 2 s. The tune `LOUD_LAND_WARNING_CTS` is in the source table, but nothing in 4.7.2 calls it.

### DShot: motor beeps, ESC LEDs and finding a crashed vehicle
**Motor beeps.** With bit 1 of `NTF_BUZZ_TYPES` set, each note of a tune goes to all ESCs as a DShot command: a frequency below 1047 Hz is `BEEP1`, below 1175 is `BEEP2`, below 1319 is `BEEP3`, below 1397 is `BEEP4`, above that `BEEP5`. The conditions, from `AP_HAL_ChibiOS/Util.cpp` and `RCOutput_serial.cpp`:

- `SERVO_DSHOT_ESC` is not 0 (at 0 no DShot commands are sent at all, see `ap-outputs`);
- the motors are on DShot (`MOT_PWM_TYPE` 4–7);
- the vehicle is **disarmed**: when armed, beep commands are dropped, because the motors are busy producing thrust.

Beeps do not depend on `SERVO_BLH_AUTO` or on pass-thru. The reversal and 3D commands from the `SERVO_BLH_RVMASK` and `SERVO_BLH_3DMASK` masks go through the same queue but with priority: beeps and LEDs wait behind them.

A beep does not spin the motors: the sound comes from the rotor vibrating in place. But only a powered ESC can make a sound, which means the vehicle is live and can be armed, so the propellers are off for bench setup.

**ESC LEDs.** Bit 11 of `NTF_LED_TYPES` sends the commands `LED0`–`LED2` (blue, red, green; on/off only). It works when disarmed and only with `SERVO_DSHOT_ESC` = 1 or 3 (BLHeli32, Kiss, AM32); for BLHeli_S and BlueJay (2 and 4) the commands are not sent.

**Lost vehicle.** Three things set the `vehicle_lost` flag:

- a switch with `RCx_OPTION = 30` (Lost Copter Sound; in Plane, Lost Plane Sound): the high position turns it on, the low one turns it off, the middle one changes nothing (the switch thresholds are in `ap-aux-tune`);
- a stick gesture in Copter: disarmed, throttle at zero, roll and pitch both above 4000 out of 4500, held for 1 s; Messages shows `Locate Copter alarm`. The sound lasts only while the sticks are held: release them and it is silent. The gesture is disabled if a switch with function 30 is assigned;
- the ground station command `MAV_CMD_DO_AUX_FUNCTION` with function 30, or a tune through `PLAY_TUNE`.

What this means for a search (the question "how do I find a crashed drone"). The switch and the gesture work only while the receiver delivers channels: on a lost link the firmware does not read switches. The ground station command needs live telemetry. Motor beeps need a disarmed vehicle and a battery on board. ArduPilot has no automatic "link lost, start beeping" beacon like Betaflight's (`bf-led-buzzer`): the battery failsafe tune stops at disarm (only the active buzzer on `NTF_BUZZ_PIN` keeps repeating the battery signal). So a vehicle that flies beyond visual line of sight also needs a self-powered beacon with its own battery, and the last coordinates come from the telemetry of the transmitter or the ground station.

### The I2C display
`NTF_DISPLAY_TYPE` enables a monochrome 128 × 64 display at I2C address 0x3C: 1 is the SSD1306 controller, 2 is the SH1106. When disarmed it refreshes twice a second and shows these lines: the last message, the mode, the battery voltage, the fix type and satellite count, `Prearm: passed / failed`, `EKF: ok / fail`. When armed only one line remains, `>>>>> ARMED! <<<<<`, and communication with the display stops. A display is useful on a large vehicle prepared without a laptop; on an FPV copter the OSD gives the same information (`ap-osd-video`).

### What to choose: a decision table
| Vehicle | Indication | Masks | What to check afterwards |
|---|---|---|---|
| 5" on a small board | the board LEDs; 2–4 NeoPixel LEDs on the LED pad if it is on a separate timer; a buzzer on the BUZZ pad and motor beeps; switch 30 | `NTF_LED_TYPES` 257, `NTF_BUZZ_TYPES` 3, `SERVO_DSHOT_ESC` ≠ 0 | in the `RCOut:` line the strip output is in `NeoP` mode; no `PreArm … on disabled channel`; when disarmed the motors play the startup tune |
| 7–10" for long-range flights | the same plus a strip visible from below (it shows the fix before takeoff), plus a self-powered beacon | 257 and 3; `NTF_LED_BRIGHT` from the BEC calculation | the BEC calculation with a 1.5 margin; switch 30 starts the beeps when disarmed; the self-powered beacon triggers when the battery is disconnected |
| A large multirotor with a GPS module | the RGB LED of the GPS module (I2C is the default, for CAN add bit 5); the module buzzer; a safety switch with its own LED; with people working nearby, `NTF_LED_OVERRIDE = 3` | the board default, for CAN + 32; `NTF_BUZZ_TYPES` 5 | the color on the module matches the table of states; the switch LED: flashing means outputs blocked, solid means released |
| Plane | the GPS module LED or a strip; a buzzer; switch 30 (Lost Plane Sound) | as for the board; motor beeps only if the ESC is on DShot | remember `ARMING_REQUIRE = 0`: the LED shows "armed" right after boot |

After any change: reboot, then compare the LED pattern with the table of states in three situations: right after power-up, after the checks pass, and with the transmitter off.

### What changed between 4.6.3 and 4.7.2
A comparison of the `libraries/AP_Notify` directories and the metadata files of the two releases:

- bit 19 `ProfiLED_IOMCU` was added; on CubeBlack, CubeOrange and CubeYellow it is part of the default, so there the default `NTF_LED_TYPES` is 123079 + 524288 = 647367;
- a board can define a NeoPixel strip output in its `hwdef` (a default mask), and the strip works without `SERVOn_FUNCTION = 120`;
- the driver sets for Linux boards were moved from common code into the board definitions;
- the names, ranges and defaults of all `NTF_*` parameters, the color sequences and the table of tunes did not change. The general 4.7 rename table is in `ap-intro`.

### Place in the system
- **Receives:** the pre-arm check and armed flags (`ap-setup-scratch`), the radio, battery and GCS failsafe flags and the EKF state (`ap-safety-fs`), the timer group and the output for a strip and the ESC type `SERVO_DSHOT_ESC` (`ap-outputs`), the position of switch 30 (`ap-aux-tune`), the BEC current (`el-power-design`).
- **Provides:** to the pilot, the vehicle state without a ground station or OSD; to scripts, the status color and control of a strip (`ap-lua`); to a search, the sound of a crashed vehicle.
- **If you get it wrong here:** a strip in one group with a servo disables the servo, and `PreArm … on disabled channel` blocks arming (`ap-outputs`); a strip with no power budget pulls the 5 V rail down and the receiver or GPS reboots (`el-power-design`); flashing yellow taken for "no GPS" is a missed failsafe (`ap-safety-fs`); relying on motor beeps after a lost link leaves the vehicle silent in the grass.

## practice
The lab is a calculation exercise: you need neither a flight controller nor a simulator, and no firmware was built or run for this work. All parameter files below are a training example assembled by hand; they are not an export from a real vehicle. Every answer follows from the tables of the theory.

### Step 1. The `NTF_LED_TYPES` and `NTF_BUZZ_TYPES` masks
Build `NTF_LED_TYPES`: (a) the board LEDs and a WS2812B strip; (b) the board LEDs, an NCP5623 LED in a GPS module on the external I2C bus, and the LED of a GPS module on CAN; (c) the board LEDs, a WS2811 strip with RGB color order, and handing the color to a script. Build `NTF_BUZZ_TYPES`: (d) the board buzzer and motor beeps; (e) the same plus a buzzer on a DroneCAN node.

Decode: (f) `NTF_LED_TYPES = 123079`; (g) `NTF_LED_TYPES = 455`; (h) `NTF_LED_TYPES = 2305`; (i) `NTF_LED_TYPES = 647367`; (j) `NTF_BUZZ_TYPES = 5`.

Result. (a) 1 + 256 = **257**; (b) 1 + 64 + 32 = **97**; (c) 1 + 262144 + 1024 = **263169**; (d) 1 + 2 = **3**; (e) 1 + 2 + 4 = **7**. (f) 123079 = 65536 + 32768 + 16384 + 8192 + 128 + 64 + 4 + 2 + 1, bits 0, 1, 2, 6, 7, 13, 14, 15, 16: the board LEDs and all the I2C drivers, which is the default of a generic build. (g) 455 = 256 + 128 + 64 + 4 + 2 + 1, bits 0, 1, 2, 6, 7, 8: the board, ToshibaLED, NCP5623 and NeoPixel. (h) 2305 = 2048 + 256 + 1, bits 0, 8, 11: the board, NeoPixel and the ESC LEDs. (i) 647367 = 123079 + 524288: bit 19 `ProfiLED_IOMCU` is added to the default, which is the Cube default in 4.7. (j) 5 = 4 + 1: the board buzzer and DroneCAN, no motor beeps.

### Step 2. Six patterns and four reverse problems
`NTF_LED_OVERRIDE = 0`, an RGB LED. Name the state and the action.

1. Red and blue replace each other every 0.1 s.
2. Every second, two yellow flashes of 0.2 s each.
3. Blue: 0.5 s on, 0.5 s off.
4. Green blinks fast: 0.1 s on, 0.1 s off.
5. In flight the LED is solid blue.
6. In flight: 0.5 s yellow, 0.5 s red.

Reverse problems, describe the pattern: (a) armed with a 3D fix and a valid position; (b) a compass calibration is running; (c) a battery failsafe triggered in flight; (d) in flight the EKF reports a GPS glitch.

Result.

| No. | State | Action |
|---|---|---|
| 1 | initialising | do not move the vehicle |
| 2 | disarmed, pre-arm checks failing | read `PreArm: …` in Messages and remove the cause |
| 3 | disarmed, checks passed, no fix or no position | wait for green, or arm only in a mode that needs no position |
| 4 | disarmed, ready, a fix of DGPS level or better | you may arm |
| 5 | armed with no fix or no position | do not switch to Loiter, RTL or Auto; fly manually |
| 6 | EKF bad | land manually in a mode that needs no position |

(a) Solid green. (b) Red, blue, green for 0.1 s each, three times in a row, and 0.1 s dark. (c) 0.5 s yellow, 0.5 s dark; the tune `LOUD_BATTERY_ALERT_CTS` repeats until disarm. The LED looks exactly the same on a radio loss and on a GCS loss. (d) 0.5 s yellow, 0.5 s blue.

### Step 3. A NeoPixel strip on a MatekH743 with DShot motors
The board and its timer groups come from the practice of `ap-outputs` (the standard build, `hwdef.dat` of Copter-4.7.2): TIM8 has outputs 1, 2; TIM5 has 3, 4, 5, 6; TIM4 has 7, 8, 9, 10; TIM15 has 11, 12; TIM1 has 13 (marked `for WS2812 LED` in the `hwdef`). Motors on outputs 1–4, DShot600. Servos on outputs 7 and 8. A WS2812B strip as the status LED. The 5 V BEC is rated for 2 A, and the other loads of the branch draw 0.9 A.

(a) Which output takes the strip, and which function do you assign to it? (b) Which outputs are ruled out, and why? (c) Which three `NTF_*` parameters do you write for a strip of 7 LEDs if the board LEDs are needed too? (d) How many LEDs can the BEC carry by the course rule? Do 8 pass? What BEC do 12 need? (e) What current do 8 LEDs draw in yellow at `NTF_LED_BRIGHT = 2` in the model "20 mA per channel at byte 255"?

Result. (a) Output 13, `SERVO13_FUNCTION = 120`: it is alone on TIM1, so the strip disables nothing. (b) Outputs 5 and 6 are on TIM5 together with motors 3 and 4: the timer would switch to the strip mode, motors 3 and 4 would lose DShot, and `PreArm` would not report it; arming would succeed and the vehicle would flip on takeoff. Outputs 9 and 10 are on TIM4 together with the servos: the strip would switch the timer to its mode and the servos on 7 and 8 would be disabled with `PreArm: SERVO7_FUNCTION=… on disabled channel`. Outputs 11 and 12 are acceptable as long as nothing else is on TIM15. (c) `NTF_LED_TYPES = 257`, `NTF_LED_LEN = 7`, `NTF_LED_BRIGHT` at 1 or 2. (d) The allowed sum for the branch is 2 / 1.5 = 1.333 A; that leaves 1.333 − 0.9 = 0.433 A for the strip; 0.433 / 0.06 = 7.2, so **7 LEDs**. For 8: 0.9 + 8 · 0.06 = 1.38 A, × 1.5 = 2.07 A > 2 A, so they do not pass. For 12: 0.9 + 0.72 = 1.62 A, × 1.5 = 2.43 A, so you need a 3 A BEC or a separate BEC for the strip. (e) 8 · 2 · 0.02 · 127 / 255 = **0.159 A**.

### Step 4. Three mistakes in a parameter file
A 7" copter on a MatekH743, motors on outputs 1–4, ESCs running Bluejay firmware. A strip of 8 WS2812B LEDs on output 13 is meant to show the standard status colors; there are no scripts on board. A buzzer on the BUZZ pad. You want motor beeps and the lost vehicle sound from a switch on channel 9. Find the lines that keep this from working.

```
# training example, assembled by hand
MOT_PWM_TYPE,6
SERVO_DSHOT_ESC,2
SERVO13_FUNCTION,120
NTF_LED_TYPES,257
NTF_LED_LEN,1
NTF_LED_BRIGHT,2
NTF_LED_OVERRIDE,1
NTF_BUZZ_TYPES,1
NTF_BUZZ_PIN,-1
NTF_BUZZ_VOLUME,100
RC9_OPTION,30
SCR_ENABLE,0
```

Result: there are exactly three mistakes. (1) `NTF_LED_LEN = 1`: only the first LED of the strip gets the color; it must be 8. (2) `NTF_LED_OVERRIDE = 1`: the RGB devices wait for a color from a script or the ground station, and there is none, so the strip is dark (the plain board LEDs of the MatekH743 do not depend on this parameter and blink as usual); it must be 0. (3) `NTF_BUZZ_TYPES = 1`: the DShot bit is missing and the motors do not beep; it must be 3. The rest is correct: `SERVO_DSHOT_ESC = 2` is BLHeli_S and BlueJay, and any nonzero value is enough for beeps; 257 is the board plus NeoPixel; output 13 is alone on TIM1; `NTF_BUZZ_PIN = -1` with a buzzer on the BUZZ pad is normal, since the tune driver serves the pad; `RC9_OPTION = 30` is the lost vehicle sound; `SCR_ENABLE = 0` is fine because there are no scripts.

### Moving to real hardware
The propellers are off for the whole check. Motor beeps and ESC LEDs work only with the main battery connected: the vehicle is live and can be armed, so keep the arming switch off and the throttle at zero. Power the strip from the BEC sized in step 3, not from the flight controller 5 V.

1. Save the full parameter list to a file. Write down the timer groups of the board from its `hwdef.dat` (`ap-outputs`).
2. Assign the strip output, `NTF_LED_TYPES`, `NTF_LED_LEN`, and reboot. In the `RCOut:` line the strip output must be in `NeoP` mode, and Messages must not show `PreArm … on disabled channel`.
3. Compare the patterns with the table of states: after power-up, alternating red and blue; indoors with no satellites, the double yellow flash or blue 0.5 / 0.5 s; outdoors with a fix, green; switch off the transmitter (with `FS_THR_ENABLE` enabled) and you get yellow 0.5 / 0.5 s.
4. Measure the strip current with a multimeter in series with the positive lead at `NTF_LED_BRIGHT = 3` and compare it with the calculation.
5. Set bit 1 in `NTF_BUZZ_TYPES` and reboot with the main battery connected: the motors must repeat the startup tune. Switch 30 high gives a long repeating tone, low gives silence.
6. If red and green are swapped, replace bit 8 with bit 18.

On hardware the work is done when the output mode in `RCOut:` matches the plan, the four patterns of item 3 match the table, the measured current does not exceed the calculated one, and the switch turns the sound on and off when disarmed.

Self-check: the lab is done when:
- step 1: the values 257, 97, 263169, 3, 7 match exactly; the decodings are bits "0, 1, 2, 6, 7, 13, 14, 15, 16", "0, 1, 2, 6, 7, 8", "0, 8, 11", "the default plus bit 19", "0 and 2";
- step 2: the six states match the result table, and the four reverse patterns are described with the same durations (0.1 s and 0.5 s);
- step 3: output 13 and function 120; outputs 5, 6, 9, 10 are ruled out; parameters 257, 7 and brightness 1 or 2; 7 LEDs; for 8, 2.07 A, which does not pass; for 12, 2.43 A; current 0.159 A (tolerance ±0.002 A);
- step 4: exactly three mistakes are found: `NTF_LED_LEN`, `NTF_LED_OVERRIDE`, `NTF_BUZZ_TYPES`.

**Reference for the self-check.** The correct result is the numbers and lines of the four items above. Typical mistakes: (1) in step 1 the strip came out as 256 or 8: bit 0 was forgotten, or the bit number was written instead of its weight; for (c) the result was 263425: bits 8 and 18 were both set, and only one of them is needed. (2) In step 2 pattern 3 was called "armed without GPS" and pattern 5 "ready without GPS": blinking means disarmed, solid means armed; pattern 6 was called "radio failsafe", but that one has a dark second half of the second, not a red one. (3) In step 3 the result was 22 LEDs: the BEC was divided by 0.06 without subtracting the other loads and without the 1.5 margin; the result was 0.32 A: the brightness byte 127 out of 255 was ignored. (4) In step 4 `SERVO_DSHOT_ESC = 2` or `NTF_BUZZ_PIN = -1` was called a mistake: the first is correct for Bluejay, the second does not interfere with the tune driver.

## diagnostics
- **Symptom:** after assigning the strip, arming is refused: `PreArm: SERVOn_FUNCTION=… on disabled channel`.
  Possible cause: the strip is in one timer group with a servo or another ordinary output and has switched the timer to its mode.
  What to do: write down the groups from `hwdef.dat` and move the strip to an output that is alone on its timer (`ap-outputs`).
- **Symptom:** after fitting the strip, arming succeeds with no refusals, but on takeoff one or two motors do not spin or stop; in the `RCOut:` line the motor outputs may show the mode `NeoP` instead of `DS600`.
  Possible cause: the strip is in the timer group of the motors: the group switched to the strip mode, the motors get the strip signal instead of DShot, and the pre-arm check excludes motor outputs and stays silent (from reading the code, not tested on hardware).
  What to do: **do not take off**; remove the strip function from that output, reboot, confirm in `RCOut:` that all motor outputs are in DShot mode again, and test the motors with the ground station motor test with the propellers off; move the strip to a group with no motors (`ap-outputs`).
  Consequences: the vehicle flips at liftoff or falls in flight.
- **Symptom:** the strip is completely dark.
  Possible cause: bit 8 or 18 is missing in `NTF_LED_TYPES`; there was no reboot; `NTF_LED_OVERRIDE = 1` with no script; `NTF_LED_BRIGHT = 0`; the timer of the output did not get a DMA channel.
  What to do: check the four parameters, reboot, read the `RCOut:` line: the output must have the mode `NeoP`.
- **Symptom:** only the first LED of the strip is lit.
  Possible cause: `NTF_LED_LEN = 1` (the default).
  What to do: write the actual number of LEDs and reboot.
- **Symptom:** the strip flickers with random colors.
  Possible cause: a 3.3 V signal at the edge of the LED threshold with a 5 V supply; a long data wire; no common ground.
  What to do: a common ground, a short wire, a diode in the positive supply of the strip, or a level shifter (`bf-led-buzzer`).
- **Symptom:** green shows instead of red, while yellow looks right.
  Possible cause: the strip has RGB color order, but bit 8 (GRB order) is set.
  What to do: clear bit 8, set bit 18.
- **Symptom:** with USB connected the strip and the board LED are dim.
  Possible cause: this is normal behavior: with USB the brightness is limited to Low.
  What to do: judge the brightness on battery power.
- **Symptom:** the LED flashes yellow in flight.
  Possible cause: a radio, battery or GCS failsafe; yellow with red is the EKF, yellow with blue is a GPS glitch.
  What to do: identify the kind from the tune and the ground station message; the procedure is in `ap-safety-fs`.
  Consequences: if you take it for "no GPS" and keep flying, the vehicle lands or goes to RTL somewhere you do not expect.
- **Symptom:** the motors do not beep although bit 1 of `NTF_BUZZ_TYPES` is set.
  Possible cause: `SERVO_DSHOT_ESC = 0`; the motors are not on DShot; the vehicle is armed; there was no reboot; the main battery is not connected.
  What to do: check `SERVO_DSHOT_ESC` and `MOT_PWM_TYPE`, reboot, listen when disarmed.
- **Symptom:** the switch with function 30 does not start the sound on a crashed vehicle.
  Possible cause: the link to the receiver is lost, so switches are not read; or the vehicle is still armed and the motor beeps are dropped (an ordinary buzzer still sounds).
  What to do: send function 30 or a tune from the ground station over telemetry; for the future, fit a self-powered beacon.
- **Symptom:** at boot, three notes instead of the startup tune.
  Possible cause: the `NO_SDCARD` tune: the firmware did not find the directory on the SD card.
  What to do: check the SD card; without it there are no logs (`ap-logs`).
- **Symptom:** the buzzer on `NTF_BUZZ_PIN` sounds all the time and goes silent on events.
  Possible cause: the on level is inverted.
  What to do: change `NTF_BUZZ_ON_LVL` and reboot.
- **Symptom:** the LED of a CAN GPS module is dark although the module works.
  Possible cause: bit 5 (DroneCAN) is not part of the default `NTF_LED_TYPES`.
  What to do: add 32 and reboot.

## checklist
- [ ] The full parameter list is saved before any change
- [ ] `NTF_LED_TYPES` is built for the actual hardware with no extra bits; a reboot followed the write
- [ ] The strip output is alone on its timer, **with no motor in its group** (the absence of a `PreArm` does not prove it: motors are excluded from the check); in `RCOut:` only the strip group has the mode `NeoP` or `ProfiLED`, and the motors have DShot; no `PreArm … on disabled channel`
- [ ] `NTF_LED_LEN` equals the number of LEDs; red and green are not swapped
- [ ] The strip current is calculated at 0.06 A per LED, and the BEC is at least 1.5 × the sum of the branch
- [ ] `NTF_LED_OVERRIDE = 0` unless a script or the ground station sets the color
- [ ] The table of states is verified on the vehicle: initialising, checks failing, ready, transmitter off
- [ ] I have memorized flashing yellow in flight as a failure, not as "no GPS"
- [ ] Motor beeps: `NTF_BUZZ_TYPES` with bit 1, `SERVO_DSHOT_ESC` ≠ 0; verified when disarmed **with the propellers off**, since the vehicle is live
- [ ] The switch `RCx_OPTION = 30` is verified: high is sound, low is silence; it neither arms nor spins the motors, but it works only with a live receiver link
- [ ] For flights beyond visual line of sight a self-powered beacon with its own battery is fitted
- [ ] On a vehicle with a safety switch: its LED flashing means outputs blocked, solid means the block is released and the motors can receive a signal

## references
- ArduPilot Copter-4.7.2: AP_Notify.cpp — NTF_* parameters, the set of drivers | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_Notify/AP_Notify.cpp | primary | A
- ArduPilot Copter-4.7.2: RGBLed.h — color sequences | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_Notify/RGBLed.h | primary | A
- ArduPilot Copter-4.7.2: ToneAlarm.cpp — tunes and events | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_Notify/ToneAlarm.cpp | primary | A
- ArduPilot Copter-4.7.2: Buzzer.cpp — active buzzer on a GPIO | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_Notify/Buzzer.cpp | primary | A
- ArduPilot Copter-4.7.2: AP_HAL_ChibiOS/Util.cpp — motor beeps over DShot | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_HAL_ChibiOS/Util.cpp | primary | A
- ArduPilot Copter-4.7.2: RCOutput_serial.cpp — the DShot command queue | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_HAL_ChibiOS/RCOutput_serial.cpp | primary | A
- ArduPilot Copter-4.7.2: AP_Scripting docs.lua — serialLED, notify, LED | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_Scripting/docs/docs.lua | primary | A
- MAVLink common.xml — the PLAY_TUNE message (id 258) | https://raw.githubusercontent.com/mavlink/mavlink/master/message_definitions/v1.0/common.xml | primary | A
- MAVLink ardupilotmega.xml — the LED_CONTROL message | https://raw.githubusercontent.com/mavlink/mavlink/master/message_definitions/v1.0/ardupilotmega.xml | primary | A
- ArduPilot wiki (page source): NeoPixel as a status LED, the diode in the supply | https://raw.githubusercontent.com/ArduPilot/ardupilot_wiki/master/common/source/docs/common-serial-led-neopixel.rst | primary | B
- ArduPilot wiki (page source): Buzzer | https://raw.githubusercontent.com/ArduPilot/ardupilot_wiki/master/common/source/docs/common-buzzer.rst | primary | B

## notes
- No firmware was built or run for this work: all behavior is described from reading the source at tag Copter-4.7.2 and the parameter metadata; the differences from 4.6.3 come from comparing the `libraries/AP_Notify` directories and the metadata files of the two releases.
- The "what it sounds like" descriptions in the table of tunes were written from the note strings in `ToneAlarm.cpp` and were not checked by ear. The durations for the plain board LEDs with two LEDs are approximate: the driver counts ticks of 60 ms while being called 50 times a second.
- Not tested on hardware: the behavior of a strip placed in one timer group with DShot motors (per the source, the whole group switches to the strip mode, a motor gets the strip signal, and the pre-arm check does not test motors, which is why the module states it as a prohibition and not as advice); motor beeps with the safety switch block active; `NTF_LED_LEN` values above 32.
- The 0.7 · VDD threshold for the data line comes from `bf-led-buzzer`; the ArduPilot documentation page names a worst case of 4.3 V with a 5 V supply, which does not change the diode recipe.
- The sites ardupilot.org and mavlink.io were unreachable while the module was prepared, so the links point to the source files of the same pages in the repositories.
