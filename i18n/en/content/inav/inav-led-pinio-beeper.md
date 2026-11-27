---
id: inav-led-pinio-beeper
title: "Lights, PINIO, the beeper and a camera trigger in INAV"
level: L2
readingTime: 60 min
firmware: INAV 9.1 (checked against 9.1.0)
status: published
added: 2026-11-20
tags:
  - INAV
  - LED strip
  - WS2812
  - PINIO
  - beeper
  - DShot beacon
  - camera trigger
  - CLI
related:
  - inav-mixer-vtol
  - inav-missions
  - inav-ipf
  - inav-osd-hd
  - inav-adjustments
  - inav-cli-backup
  - bf-led-buzzer
  - el-power-design
next:
  - inav-ipf
source: content/inav/inav-led-pinio-beeper.md
source_hash: 428d54e97363
---

## summary
A flight controller with INAV has three “utility” outputs: the LED pin (a WS2812 strip or plain PWM), up to four PINIO switches (VTX power, a camera switcher, a shutter) and the beeper, which the motors help over DShot. This module works through them from the INAV 9.1.0 source: the format of `led`, `color`, `mode_color` with all the function letters, the `led_pin_pwm_mode` modes and the `ledpinpwm` command, the USER1–4 mode numbers for `pinio_box1..4`, the full list of `beeper` conditions and the rules of the DShot beacon. Separately — what INAV has for a camera (RunCam control, mission user actions, logic conditions) and what it does not: a ready-made “shot every N meters” function does not exist in the firmware, and it is assembled from four rules. After this module you can read and write strip lines, build a PINIO setup and a distance-based shutter, predict when the aircraft will beep and calculate the strip current. The lab is a calculation exercise, without hardware.

## theory
### Three outputs and who controls them
This module is about the outputs of the flight controller that do not drive motors or servos: the LED strip and the LED pin, the PINIO pins, the beeper and beeping with the motors. The reading order: first the map of “which output is switched by what” (the table below); then the strip — hardware and the timer, the `led` line, colors; then the LED pin in PWM mode, PINIO with the USER modes and the path from logic to PINIO; at the end the beeper, the DShot beacon, lights and the camera. The section on overriding an RC channel with logic (operation 38) contains a safety warning: read it before you write the first rule. The output layout and the timers are in `inav-mixer-vtol`, the logic conditions themselves in `inav-ipf`, the user actions of waypoints in `inav-missions`.

| Output | What switches it | Where it is configured |
|---|---|---|
| LED pin: a WS2812 strip | firmware events (arm, battery, GPS, failsafe, sticks), the `LEDS OFF` mode | `feature LED_STRIP`, `led`, `color`, `mode_color` |
| LED pin: 24 kHz PWM | the `ledpinpwm` command, a logic condition with operation 52 | `led_pin_pwm_mode` |
| PINIO 1–4 | any mode of the Modes tab, usually USER1–4 | `pinio_box1..4`, `aux` |
| Beeper | 24 firmware conditions, the `BEEPER` mode | `beeper`, `beeper_pwm_mode` |
| Motors as a beeper | the same conditions, only while disarmed | `dshot_beeper_enabled`, `dshot_beeper_tone` |

A logic condition (`inav-ipf`) can drive only the LED pin directly. It reaches PINIO by a detour: with operation 38 it overrides the RC channel that carries the range of a USER mode. A mission action (a user action in `p3`, `inav-missions`) switches nothing by itself — it is only an operand for the logic.

{{diagram:inav-led-pinio-beeper-flow|A switch controls PINIO and the beeper through modes, a logic condition — the LED pin directly and PINIO through a channel override; a mission user action is visible only to the logic.}}

### The strip: hardware, the timer, the limits
A WS2812 has three wires: 5 V, GND, DIN. The driver (`drivers/light_ws2811strip.c`) sends 800 kHz from a 2.4 MHz timer through DMA and always transmits a frame for 128 LEDs (`LED_MAX_STRIP_LENGTH 128`; the same in 9.1.0 and in 8.0.1). The palette has 16 colors (`LED_CONFIGURABLE_COLOR_COUNT`). The strip task runs 100 times a second.

Power: the course assumes 0.06 A per LED at full white (`el-power-design`), about 20 mA per color channel (`bf-led-buzzer`). The INAV documentation advises separate power from as few as 20 LEDs. INAV has no overall brightness control like `ledstrip_brightness` in Betaflight: you reduce the current by lowering V in `color`. The colors of the warnings and the indicators are hard-coded at full brightness.

The timer. The strip is enabled only with `feature LED_STRIP`. The output is the `WS2811_PIN` of the board, as long as it has the `TIM_USE_LED` flag in the timer table; if the flag is removed, the first pin with this flag is taken. The conflict rule (`checkPwmTimerConflicts` in `drivers/pwm_mapping.c`): with the feature enabled, **every output on a timer that has a channel with the LED flag is skipped** when motors and servos are assigned. The command `timer_output_mode <timer> LED` sets the flag on all channels of the timer (`inav-mixer-vtol`) — that is how the strip is moved to a servo output on a board without a dedicated pad, but all the outputs of that timer are lost for motors and servos. Not enough outputs — arming is blocked by `PWMOUT`. One more check: if `WS2811_PIN` shares a timer with SoftSerial and both features are enabled, the firmware silently clears `LED_STRIP` at boot.

### The `led` line
`led <index> <x>,<y>:<directions>:<functions>:<color>` — index 0…127 in wiring order.

- **x, y** — 0…15, stored in 4 bits each (17 becomes 1). 0,0 is north-west, nose at the top.
- **Directions** — the letters `N E S W U D`; only the `F` function needs them.
- **Functions** — one base letter and any overlays; the letters can be entered in any order, and the CLI prints the base one first and the overlays in the order `T O B N I W E`.
- **Color** — a palette index 0…15 (16 and more becomes 0); for the `H` function — the RC channel number.

The line `led <i> 0,0:::` clears the entry. The LEDs are counted up to the first empty entry: `0,0::C:0` is also zero and cuts the strip off.

| Letter | Base function | What it shows |
|---|---|---|
| `C` | Color | a color from the palette |
| `F` | Flight mode | the mode color from `mode_color` by direction |
| `A` | Arm state | disarmed — special color 0, armed — special color 1 |
| `L` | Battery | a hue by the charge percentage: 329 (pink) at 0 %, 359 (red) at 20 %, 119 (green) at 100 %; WARNING — blinks at 1 Hz, CRITICAL — at 4 Hz |
| `S` | RSSI | the same scale by RSSI; below 50 % it blinks slowly, below 20 % — fast |
| `G` | GPS | no satellites — special color 5; a fix — blinks with color 7 by the number of satellites; satellites without a fix — with color 6 on a background of 5 |
| `R` | Thrust ring | a running light, faster with throttle; while disarmed every second LED is lit |
| `H` | Channel | a hue by the value of an RC channel, the channel number is in the color field |

| Letter | Overlay | Action |
|---|---|---|
| `T` | Throttle | shifts the hue of the base color with throttle (while armed) |
| `O` | Larson scanner | a “scanning eye”: changes the brightness |
| `B` | Blink | two short flashes in its own color, the rest of the time — special color 4 |
| `N` | Blink on landing | the same, but only while armed with the throttle below 50 % |
| `I` | Indicator | orange turn indicators from the sticks |
| `W` | Warnings | a 1.6 s cycle of 0.4 s windows: arming disabled — green, battery not OK (needs `feature VBAT`) — red, failsafe — yellow/blue, a sensor failure — blue |
| `E` | Strobe | two flashes of special color 8 on top of the base |

Two peculiarities of 9.1.0, both visible only in the code (`io/ledstrip.c`):

- **Quadrants.** South is `y ≥ ⌈height/2⌉`, east is `x ≥ ⌈width/2⌉`, while north and west, because of `MIN(…, 0)` in `determineOrientationLimits`, are only the row `y = 0` and the column `x = 0`. The exception is a grid of one row (all LEDs have `y = 0`): there “north” is all the LEDs, because −1 is written to an unsigned byte as 255; the same for a grid of one column and “west”. On a multirotor the `I` indicator and the `F` color with the N/W directions work only if the front LEDs are in `y = 0` and the left ones in `x = 0`. For `F` the directions `U` or `D` are more reliable: they do not need a quadrant.
- **Fixed wing and rover.** The indicator looks only at roll: stick right — the `I` LEDs with `x ≥ 8` blink, left — those with `x < 8`. The deadband is ±25 `rcCommand` units, and the rate of 2.5–25 Hz grows with the deflection.

### `color` and `mode_color`
`color <index> <h>,<s>,<v>` — index 0…15, H 0…359, S and V 0…255. The saturation is inverted (`sat = 255 − s`): S = 0 is a pure color, S = 255 is white. A value out of range is a parse error, and the color is zeroed. The default palette: 0 BLACK, 1 WHITE (`0,255,255`), 2 RED (`0,0,255`), 3 ORANGE, 4 YELLOW, 5 LIME_GREEN, 6 GREEN, 7 MINT_GREEN, 8 CYAN, 9 LIGHT_BLUE, 10 BLUE, 11 DARK_VIOLET, 12 MAGENTA, 13 DEEP_PINK (hues in steps of 30°), 14–15 black.

`mode_color <mode> <index> <color>`:

| Mode | Name | Index |
|---|---|---|
| 0 | ORIENTATION (no others) | direction 0…5: N, E, S, W, U, D |
| 1 | HEADFREE | the same |
| 2 | HORIZON | the same |
| 3 | ANGLE | the same |
| 4 | MAG (HEADING HOLD) | the same |
| 5 | BARO (NAV ALTHOLD) | the same |
| 6 | LOITER (NAV POSHOLD) — new in 9.x | the same |
| 7 | special colors (mode 6 in 8.0.1) | 0 disarmed (GREEN), 1 armed (BLUE), 2 animation (not used), 3 background (BLACK), 4 blink background (BLACK), 5 GPS without satellites (RED), 6 GPS without a fix (ORANGE), 7 GPS with a fix (GREEN), 8 strobe (WHITE) |

The mode priority for `F`: HEADFREE, LOITER, MAG, BARO, HORIZON, ANGLE, otherwise ORIENTATION.

**A migration trap.** In 8.0.1 the special colors were mode 6, in 9.1.0 mode 6 is LOITER and the special colors are 7. The line `mode_color 6 1 2` from an 8.x dump changes the “east” color of the LOITER mode in 9.1.0, and `mode_color 6 6 3` and higher give a parse error. When moving a config (`inav-cli-backup`) replace 6 with 7 in these lines. `docs/LedStrip.md` of the 9.1.0 tag still gives the old numbers.

### The LED pin as PWM: `led_pin_pwm_mode` and `ledpinpwm`
The same pin can output 24 kHz PWM with a duty cycle of 0…100 %: 0 and 100 % are an extra discrete output, and intermediate values through an RC filter give a voltage (emulation of the camera menu joystick, the `osd_joystick_*` settings). `feature LED_STRIP` is required.

| `led_pin_pwm_mode` | Strip | Idle level | What for |
|---|---|---|---|
| `SHARED_LOW` (default) | works | low | the strip; PWM temporarily suspends its updates |
| `SHARED_HIGH` | works | high between frames | the strip plus the OSD joystick |
| `LOW` | does not work | low | the pin as a switch, off at boot |
| `HIGH` | does not work | high | the pin as a switch, on at boot |

According to the documentation, in any mode the pin holds a low level for about 2 s at boot. The CLI commands: `ledpinpwm <0…100>` — turn PWM on, `ledpinpwm` without an argument — turn it off (in `LOW`/`HIGH` the pin returns to its idle level). It takes effect at once and is not written to EEPROM. In flight the same is done by a logic condition with operation **52** (LED Pin PWM): operand A 0…100 is the duty cycle, any other value — stop. The rule is executed only while its activator is true and turns nothing off by itself: for “off” you need a second rule with A = 0.

### PINIO and the USER modes
PINIO is up to four pins (`PINIO_COUNT 4`) defined in `target.h` as `PINIO1_PIN`…`PINIO4_PIN`; 109 boards out of 232 have them in 9.1.0 (71 out of 176 in 8.0.1). PINIO cannot be moved to another pin without a custom build.

`pinio_box1`…`pinio_box4` (0…255, default 255 — “none”, unless the board set its own) is the **permanent id of the mode** that the pin follows. Most often this is USER:

| Mode | Permanent id for `aux` and `pinio_box` | The `boxId` number in `rc_modes.h` (do not enter it) | The “flight mode” operand in logic (type 3) |
|---|---|---|---|
| USER1 | 47 | 37 | 9 |
| USER2 | 48 | 38 | 10 |
| USER3 | 57 | 48 | 12 |
| USER4 | 58 | 49 | 13 |

The numbers are not consecutive: 49 is LOITER CHANGE, 37 is SERVO AUTOTRIM. Any other mode will do as well: several boards set `pinio_box` to ARM (id 0) out of the box, and the pin is active while armed. The setting by itself switches nothing — the mode needs a range: `aux <line> <id> <channel, AUX1 = 0> <start> <end>`, the limits are 900…2100 in steps of 25, and the end is not included. `pinio_box*` is read at boot: a reboot is needed after `save`.

The levels (`drivers/pinio.c`): at initialization the pin is low, with the mode active — high; on boards with `PINIOn_FLAGS PINIO_FLAGS_INVERTED` it is the other way round. What that means for the load (VTX on or off) depends on the board circuit — check with a multimeter. During failsafe the channels hold their last values, so the USER mode and the pin do not change.

**Safety.** A switch on the VTX power in flight means losing the picture with a single flick; put it on a two-position switch that you cannot bump, and check its position before takeoff. In logic the USER1–4 modes are read with operands 9, 10, 12, 13 of type 3 (“flight mode”).

### Logic → PINIO: operation 38 and why you cannot trust it blindly
There is no “enable USER” operation. Operation 21 (Set IO Port) writes to an I²C IO expander, not to PINIO. The working path is operation **38** (Override RC Channel): operand A is the channel number (1 = roll, 5 = AUX1), B is a value of 1000…2000; while the rule is active, `rxGetChannelValue` returns the overridden value, and the `aux` range on this channel activates the mode. Take a channel that has nothing on it on the radio (it holds 1500). The logic is evaluated 10 times a second and does not run while the CLI is open.

**Safety: operation 38 overrides any channel.** The code takes the channel as `constrain(A − 1, 0, 33)` and the value as `constrain(B, 1000, 2000)` (`programming/logic_condition.c`) and does not check what channel it is. The override is read by the same function `rxGetChannelValue` through which the firmware gets the sticks and the positions of the mode switches, so it acts on everything at once and holds while the rule is active — armed and disarmed, with a live receiver and without one. The channel numbers here are internal and do not depend on the `map` setting: 1 — roll, 2 — pitch, 3 — yaw, **4 — throttle**, 5 — AUX1. Hence — which channels must not be the target of a rule:

- **1…4 (the sticks).** The rule takes the axis away from the pilot. Channel 4 with the value 2000 is full throttle for as long as the rule is true; a single digit separates the harmless channel 12 from the throttle (4 instead of 12 is the same mistake as `14` → `4`).
- **The channel of the ARM switch.** An override into the ARM range arms the aircraft without the pilot; an override outside the range disarms it in the air; and while the rule holds the channel in the range, you cannot disarm with the switch.
- **The channels of modes that safety depends on:** FAILSAFE, RTH, MANUAL, `MSP RC OVERRIDE`. By overriding such a channel a rule enables or blocks the mode for the pilot.
- **Operand A that is not a constant.** Zero and negative numbers are constrained to channel 1: a rule that takes the channel number from an unset variable overrides roll.

The rule: the target of operation 38 is only an AUX channel that has nothing on it on the radio and carries a single range — that of the USER mode you need; the channel number is written as a number. Test every new rule without propellers: on the Receiver tab, with the rule active, exactly one channel must change — the intended one, and the bars of the sticks and of the ARM channel must still follow the radio.

### Mission actions (user actions)
Bits 1–4 of the `p3` field of a waypoint (`NAV_WP_USER1…4`, values 2, 4, 8, 16; bit 0 is the altitude type) are visible only to the logic, as operands of type 7: 6–9 — “action 1–4 is active on this leg” (`p3` of the waypoint the aircraft is flying from is taken), 10–13 — the same for the waypoint it is flying to. USER modes and user actions are different things: the first is a switch and PINIO, the second is a flag on a leg of the route. In a multi-mission file operands 6–13 are right only for mission 1: in 9.1.0 they index the whole waypoint list (read from the code, not checked in flight; details are in `inav-missions`).

### The beeper: `beeper` and the conditions
`beeper` — the list of disabled ones; `beeper list` — all the names; `beeper -NAME` disables, `beeper NAME` enables; `ALL` — all at once; `PREFERED` stores and restores a set. The name is compared case-insensitively by the typed beginning, and the first match in the table is taken: `beeper -RX` disables RX_LOST. By default everything is enabled.

| Name | When it sounds (9.1.0) |
|---|---|
| RUNTIME_CALIBRATION | sensor calibration has finished (the gyro at startup) |
| HW_FAILURE | a sensor failure (`isHardwareHealthy`), repeats |
| RX_LOST | no RC data **and** there was an arm after power-up: 0.5 s of sound, 0.5 s of pause |
| RX_LOST_LANDING | SOS while armed, while failsafe is flying RTH or a landing |
| DISARMING · ARMING · ARMING_GPS_FIX | disarm; arming without a position estimate; arming with a valid position estimate |
| BAT_CRIT_LOW · BAT_LOW | battery CRITICAL / WARNING — while armed, before the first arm or in failsafe |
| RX_SET | the `BEEPER` mode without a GPS fix (or with fewer than 5 satellites) |
| MULTI_BEEPS | counted beeps: the number of satellites in the `BEEPER` mode, arming disabled, `save`, profiles, adjustments (`inav-adjustments`), a flight mode change |
| ACTION_SUCCESS · ACTION_FAIL | compass calibration finished; the mission reset stick command |
| READY_BEEP | once, when the position estimate first becomes valid |
| ARMED | a multirotor armed with MOTOR_STOP, throttle low: a short beep every 2.6 s |
| SYSTEM_INIT | the beeps at power-up |
| ON_USB | special: if it is **disabled**, `feature VBAT` is enabled and there is no battery — everything is silent |
| LAUNCH_MODE · LAUNCH_MODE_LOW_THROTTLE · LAUNCH_MODE_IDLE_START | fixed-wing autolaunch: waiting for the throw; the throttle is not raised; the motor is about to start |
| CAM_CONNECTION_OPEN · CAM_CONNECTION_CLOSED | entering and leaving the RunCam camera menu |
| GPS_STATUS · DISARM_REPEAT | the names exist, but nothing calls them in 9.1.0 |

A beep higher in the table interrupts the current one; an equal or lower one waits for the end of the sequence. A disabled condition still “plays” silently. The `BEEPER MUTE` mode (id 60) silences everything.

The `BEEPER` mode (id 13) is finding the aircraft with a switch. With `feature GPS`, a fix and at least 5 satellites it counts out the satellites: n = min(satellites, 10) beeps of 50 ms with a 100 ms pause and a 500 ms pause at the end, that is, T = 50·n + 100·(n − 1) + 500 ms; otherwise — the short RX_SET beeps. On a link loss after a flight the aircraft calls by itself: RX_LOST.

Hardware: without `BEEPER_INVERTED` in `target.h` the pin is open drain, and “beep” = a low level; with it — push-pull, and “beep” = a high level. `beeper_pwm_mode = ON` is PWM for a passive beeper (2500 Hz unless the board set another value); enable it only if the board supports it.

### Motors as a beeper (DShot beacon)
`dshot_beeper_enabled` (ON by default) and `dshot_beeper_tone` (1…5, default 1). Unlike Betaflight there is no separate `beacon` list: at the start of every beeper sound `beeperUpdate` sends the motors the beacon command if all of this holds at once:

1. the motor protocol is DShot;
2. `areMotorsRunning()` is false — **not armed** and the motors are stopped (including no motor test in progress);
3. the guard pause since the previous command has passed: 360 ms for tones 1–2, 380 ms for 3–4, 1120 ms for 5;
4. the condition is not disabled with the `beeper` command and the sound is not a “pause” — this was added in 9.x (present in 9.1.0); in 8.0.1 the motors beeped on disabled conditions too.

Until the pause has expired, arming is disabled by the `DSHOTBEEPER` flag (“MOTOR BEEPER ACTIVE” on the OSD, `inav-osd-hd`). The propellers do not spin during this, but the windings heat up — do not leave the beacon on for hours.

### LIGHTS
The code has the `LIGHTS` mode (id 16) and the settings `failsafe_lights` (ON), `failsafe_lights_flash_period` (1000 ms, 40…65535), `failsafe_lights_flash_on_time` (100 ms, 20…65535): a separate pin `LIGHTS_PIN` is turned on with a switch and flashes in failsafe. But all of this is under `USE_LIGHTS`, and no board in the 9.1.0 and 8.0.1 trees defines this macro. Official builds have neither the mode nor the settings — only a custom build does. Make headlights with PINIO or the LED pin. The `LEDS OFF` mode (id 15, internal name `BOXLEDLOW`) exists with `feature LED_STRIP` and turns the whole strip off.

### The camera: what exists and what does not
| Task | INAV 9.1.0 |
|---|---|
| A “camera trigger” function with a distance or time interval | **no**: there is no `USE_CAMERA_CONTROL` macro, no settings and no handling of MAVLink commands for shooting |
| A “take a picture” command at a mission waypoint | **no**; there are only user actions as logic operands |
| RunCam camera buttons | **yes**: the modes CAMERA CONTROL 1–3 (id 39, 40, 41) over the RunCam Device Protocol (port function 1024) — Wi-Fi, power (on a Split — start/stop recording), change mode; they trigger when the mode is activated, 1 and 3 — only while disarmed |
| The camera menu | **yes**: 5 buttons over the RunCam protocol or with a voltage from the LED pin (`osd_joystick_enabled`, `led_pin_pwm_mode = SHARED_HIGH`) |
| A distance-based shutter | **assembled** from logic: the remainder of the trip distance → a pulse → PINIO (operation 38) or the LED pin (operation 52); a shutter servo — through `smix` with a GVAR input (`inav-mixer-vtol`) |

The recipe for “every N meters”. Flight operand 2 is the trip distance in meters: the integral of the horizontal speed from the navigation estimate; it accumulates only while armed, and circles in LOITER count too. Operation 40 (MODULUS) gives the remainder of the division by N; the comparison “remainder < W” opens a window W meters wide; operation 47 (EDGE) turns the rising edge into a pulse of a set length. You cannot compare the remainder with zero: at 12 m/s the distance grows by 1.2 m per logic tick, and the needed value is skipped. The window must last at least two ticks: **W ≥ 0.2 s · v**. The number of shots on a leg of length L started at a distance d₀: **n = ⌊(d₀ + L) / N⌋ − ⌊d₀ / N⌋** — the shots are tied to the distance since arming, not to the start of the leg. The formula holds if the leg started outside the window (the remainder of d₀ modulo N is no less than W); otherwise a shot is added at the very start.

### Differences from Betaflight
The Betaflight names are from `bf-led-buzzer` and the 2025.12 tree.

| What | INAV 9.1.0 | Betaflight 2025.12 |
|---|---|---|
| Strip length | 128 | 32 (64 with a build option) |
| `led` overlays | `T O B N I W E` | `T Y O B V I W` |
| The letter `T` | a hue by throttle | a color by an AUX channel |
| Base functions beyond `C F A L S G R` | `H` — a channel | `P`, `E`, `U` — GPS, battery and altitude bars |
| The letter `E` | the “strobe” overlay | the “battery bar” base function |
| Special colors in `mode_color` | mode 7 | mode 6 |
| RACE/BEACON profiles, `ledstrip_brightness` | no | yes |
| Moving the pin | not possible, only `timer_output_mode` | `resource LED_STRIP 1 <pin>` |
| The LED pin as PWM | `led_pin_pwm_mode`, `ledpinpwm`, operation 52 | no |
| USER1–4, id | 47, 48, 57, 58 | 40, 41, 42, 43 |
| PINIO | `pinio_box1..4`, pins from the board | the array `pinio_box`, `pinio_config`, `resource PINIO` |
| BEEPER MUTE, id | 60 | 52 |
| DShot beacon | all enabled conditions, `dshot_beeper_enabled` | a separate `beacon` command, only RX_LOST and RX_SET, off by default |
| CAMERA CONTROL 1–3, id | 39, 40, 41 | 32, 33, 34 |

### Place in the system

- **Receives:** the timer of the LED pin and the output layout (`inav-mixer-vtol`); 5 V with a current margin (`el-power-design`); the arm, battery, GPS and failsafe states; the mode ranges on the AUX channels; the flags of mission legs in `p3` (`inav-missions`); the logic rules (`inav-ipf`).
- **Provides:** the color and blinking of the strip — to the pilot and an observer; the PINIO switches — to VTX power, a camera switcher, a shutter; the sound of an arming block and of finding the aircraft; the `DSHOTBEEPER` flag — to the arming blocks (`inav-cli-backup`); the `led`, `beeper`, `aux`, `logic` lines — to `diff all`.
- **If you get it wrong here:** `timer_output_mode … LED` on the servo timer → the servos are gone, arming is blocked by `PWMOUT`, and you end up looking for the cause in the mixer (`inav-mixer-vtol`). The `boxId` number 37 instead of 47 in `pinio_box1` → the VTX switches on SERVO AUTOTRIM. A strip of 24 LEDs on the flight controller's BEC → a 5 V sag, reboots of the receiver and the GPS (`el-power-design`).

## practice
The lab is a calculation exercise: no flight controller and no simulator. All the configurations below are a teaching example assembled by hand, not the output of a real aircraft. The numbers were computed with a script using the formulas of the module.

### Step 1. The strip: decode and write
A fixed wing, 8 LEDs, the default palette, `feature VBAT` enabled.

```
led 0 0,7::WIA:0
led 1 1,7::AI:0
led 2 7,7::G:0
led 3 8,7::L:0
led 4 14,7::AI:0
led 5 15,7::AIW:0
led 6 7,15::CE:2
led 7 8,15::CB:10
mode_color 7 0 4
mode_color 7 1 2
mode_color 7 7 8
color 14 30,0,128
```

Answer: (a) what the CLI prints for line 0; (b) the color of LEDs 0, 1, 4, 5 while disarmed and while armed; (c) which ones blink orange with the roll stick to the right; (d) what 2 and 3 show with a GPS fix and a battery WARNING, and which other LEDs react to WARNING; (e) what 6 and 7 do; (f) what color is stored in cell 14.

Then write six lines for a quadcopter: LEDs 0–3 under the arms in the corners of the grid in wiring order — front left, front right, rear right, rear left; 4 and 5 on the tail at the points 7,15 and 8,15. All four arms show the arm state and the indicators, the two rear ones also the warnings; 4 — GPS, 5 — the battery charge.

Answer. (a) `led 0 0,7::AIW:0` — the base letter first, the overlays in table order. (b) Disarmed — yellow (special color 0 = 4), armed — red (special 1 = 2). (c) 4 and 5: they have `I` and `x ≥ 8`; LED 3 at `x = 8` has no `I` overlay. (d) 2 blinks cyan (special 7 = CYAN) by the number of satellites; 3 blinks at 1 Hz in the charge color; 0 and 5 (`W`) blink red in their 0.4 s window out of 1.6 s. (e) 6 — red with two white flashes (`E`), 7 — two blue flashes on a black background (`B`). (f) Orange at half brightness: H = 30, S = 0 (pure), V = 128.

The lines for the quadcopter:

```
led 0 0,0::AI:0
led 1 15,0::AI:0
led 2 15,15::AIW:0
led 3 0,15::AIW:0
led 4 7,15::G:0
led 5 8,15::L:0
```

The corners are not chosen by chance: north is only `y = 0`, west is only `x = 0`. With the coordinates 1,1 the front left LED would not fall into any quadrant, and the indicator on it would not blink.

### Step 2. PINIO and a distance-based shutter
A board with PINIO1 (the VTX power switch) and PINIO2 (a free pad, through an optocoupler to the camera shutter), both non-inverted. AUX3 is a two-position switch, and CH12 (AUX8) has nothing on it on the radio. The goal: the VTX is switched on with the switch; on mission legs with user action 1 the camera shoots every 30 m of distance, with a 300 ms pulse (in fact 0.3–0.4 s: the duration is rounded up to the 100 ms logic tick). The ground speed is 12 m/s.

Write the `pinio_box`, `aux`, `logic` lines. Then calculate for a leg of L = 800 m started at a trip distance of d₀ = 1248 m: the number of shots, the distance from the start of the leg to the first and to the last shot, the time interval, the duration of the window; and the number of shots at N = 25 m and N = 40 m.

Answer:

```
set pinio_box1 = 47
set pinio_box2 = 48
aux 5 47 2 1700 2100
aux 6 48 7 1700 2100
logic 0 1 -1 1 7 6 0 1 0
logic 1 1 0 40 2 2 0 30 0
logic 2 1 0 3 4 1 0 3 0
logic 3 1 -1 47 4 2 0 300 0
logic 4 1 3 38 0 12 0 2000 0
save
```

Rule 0: mission operand 6 (user action 1 on this leg) equals 1. Rule 1 (activator 0): the distance (flight operand 2) modulo 30. Rule 2 (activator 0): the result of rule 1 is less than 3 — a 3 m window. Rule 3: EDGE on rule 2, a 300 ms pulse — 0.3–0.4 s at the output, because EDGE is checked once every 100 ms with a strict comparison and holds “true” for four ticks. Rule 4 (activator 3): channel 12 = 2000 → the range of the line `aux 6` activates USER2 → PINIO2. Check operand A of rule 4 twice: it must be 12, not 4 (throttle) and not the number of the ARM channel. In the mission the waypoint from which the survey leg starts has `p3 = 2` (or 3 with absolute altitude).

The numbers: n = ⌊2048 / 30⌋ − ⌊1248 / 30⌋ = 68 − 41 = **27 shots**; the first at a distance of 1260 m — **12 m** from the start of the leg, the last at 2040 m — **792 m**; the interval is 30 / 12 = **2.5 s**; the window is 3 / 12 = **0.25 s** (2–3 logic ticks, the condition W ≥ 0.2 · 12 = 2.4 m is met); the leg lasts 800 / 12 ≈ 66.7 s. At N = 25 m — 81 − 49 = **32 shots**, at N = 40 m — 51 − 31 = **20 shots**.

### Step 3. When it beeps
A quadcopter, DSHOT300 motors, `dshot_beeper_enabled = ON`, tone 1, `feature GPS`, MOTOR_STOP enabled. The `BEEPER` mode is on AUX4, `BEEPER MUTE` is not assigned. In the config:

```
beeper -SYSTEM_INIT
beeper -ARMED
beeper -BAT_LOW
```

For each event say whether the beeper sounds and whether the motors beep.

| No. | Event | Beeper | Motors |
|---|---|---|---|
| 1 | power-up | no: SYSTEM_INIT is disabled | no |
| 2 | while disarmed the position estimate becomes valid for the first time | yes: READY_BEEP | yes |
| 3 | arming with a valid position estimate | yes: ARMING_GPS_FIX | no: already armed |
| 4 | armed, throttle low, the motors are stopped | no: ARMED is disabled | no |
| 5 | battery WARNING in flight | no: BAT_LOW is disabled | no |
| 6 | a link loss in flight, failsafe flies RTH | yes: SOS (RX_LOST_LANDING) | no: armed |
| 7 | landing, disarm, the radio is still off | yes: RX_LOST, once a second | yes |
| 8 | the radio is on, the `BEEPER` switch, a fix, 12 satellites | yes: 10 beeps, a 1.9 s cycle | yes |
| 9 | the same, 7 satellites; the same, 4 satellites | 7 beeps, a 1.45 s cycle; the short RX_SET beeps | yes; yes |

In addition: how long after the last beacon command in event 8 can you arm? Answer: after 360 ms (tone 1); until then the `DSHOTBEEPER` flag is set.

### Step 4. The strip current and three errors
A fixed wing: a strip of 24 LEDs, a 5 V 2 A flight controller BEC, other 5 V loads — 0.55 A. The course model: 0.06 A per LED on white, a BEC rating ≥ 1.5 × the sum (`el-power-design`).

Calculate: the strip current, the sum, the required rating; how many LEDs this BEC can handle; what separate BEC the strip needs.

Answer. The strip is 24 × 0.06 = **1.44 A**, the sum is 1.99 A, and 1.5 × 1.99 = **2.98 A** is needed — a 2 A BEC is not enough. It has 2 / 1.5 − 0.55 = 0.78 A left, that is, ⌊0.78 / 0.06⌋ = **13 LEDs**. A separate BEC for the strip: 1.5 × 1.44 = **2.16 A**, the nearest is 3 A, with a common ground.

{{diagram:chart-inav-led-budget|At 0.06 A per LED the strip hits the margin of a 2 A BEC (0.78 A after the other loads) at 13 LEDs; 24 LEDs draw 1.44 A and require a separate BEC.}}

Now the config of the same wing (an F7, the elevon servos on outputs S3 and S4, both on TIM3, no other free servo outputs):

```
feature LED_STRIP
timer_output_mode 2 LED
set pinio_box1 = 37
aux 5 47 2 1700 2100
beeper -RX_LOST
```

Find three errors and say how each one shows up.

Answer. (a) `timer_output_mode 2 LED`: index 2 on an F7 is TIM3; both of its channels get the LED flag and are skipped with `LED_STRIP` enabled, no outputs are left for the elevons — arming is blocked by the `PWMOUT` flag. (b) `pinio_box1 = 37`: 37 is the `boxId` number of USER1, while permanent id 37 is SERVO AUTOTRIM; the USER1 switch does not touch the pin, and the VTX switches when autotrim is activated. 47 is needed. (c) `beeper -RX_LOST`: after a crash with a link loss both the beeper and the motors are silent (in 9.1.0 the beacon respects disabled conditions) — the aircraft cannot be found in the grass by ear.

### Moving to real hardware
The propellers stay off for all items.
1. Save a `diff all`. Check with `get pinio_box` what the board set by itself.
2. PINIO: a multimeter on the pad, the switch in both positions — write down the level in each and after a reboot. Only then connect the VTX.
3. The strip: `feature LED_STRIP`, one line `led 0 0,0::C:2`, `save` — the first LED is red. The Outputs tab shows the same motors and servos as before enabling it; `status` does not contain `PWMOUT`.
4. Current: an ammeter in series with the 5 V of the strip, everything white (`C:1`) — compare with 0.06 A × the number of LEDs.
5. The beeper: turn the radio off after an arm and a disarm on the bench — RX_LOST and motor beeps once a second; the `BEEPER` switch — the satellite count.
6. The shutter: the Programming tab, replace the distance operand with a GVAR and change it by hand — a pulse of 0.3–0.4 s on PINIO2 (a multiple of the 100 ms logic tick). At the same time only CH12 changes on the Receiver tab: the rule does not touch channels 1…4 or the ARM channel.

Self-check: the lab is done when:
- step 1: the six answers match, line 0 is written as `0,7::AIW:0`, the six quadcopter lines match character for character (calculation);
- step 2: the numbers 47 and 48, channel 12, operations 1, 40, 3, 47, 38 match; you got 27 shots, 12 m, 792 m, 2.5 s, 0.25 s, 32 and 20 shots (calculation, no tolerance);
- step 3: the nine rows of the table match, and 1.9 s, 1.45 s and 360 ms are named (calculation);
- step 4: you got 1.44 A, 2.98 A, 13 LEDs, 2.16 A within a tolerance of 0.02 A; the three lines and how they show up are named (calculation);
- hardware: the PINIO levels are written down for both switch positions and are the same after a reboot; the measured current of the white strip is no more than 0.06 A per LED; with the radio off after an arm the aircraft beeps.

**Reference for the self-check.** The correct result is the numbers and lines above. Typical errors: (1) in step 2 you got 26 shots — ⌊800 / 30⌋ was computed without d₀: the shots are tied to the distance since arming, not to the start of the leg; (2) `pinio_box2` has 49 or `aux` has 38: USER are 47, 48, 57, 58, while 37, 38, 48, 49 are the internal `boxId` values; (3) in step 3 “the motors beep” is marked in rows 3 and 6 — the beacon is sent only with `areMotorsRunning() = false`, that is, while disarmed; (4) in step 1 green was named for disarmed — that is the default color, and `mode_color 7 0 4` replaced it with yellow.

## diagnostics
- **Symptom:** the strip is dark although `led` lines are configured
  - Possible cause: no `feature LED_STRIP` (or the firmware cleared it because of a timer shared with SoftSerial); the `LEDS OFF` mode is active; the first `led` line is empty; `led_pin_pwm_mode` is `LOW` or `HIGH`; PWM is running after `ledpinpwm`.
  - What to do: `feature`, `led`, `get led_pin_pwm_mode`; `ledpinpwm` without an argument; check the range of mode 15 in `aux`.
- **Symptom:** after enabling the strip the servos or the motor are gone, arming is blocked by `PWMOUT`
  - Possible cause: the timer of these outputs has a channel with the LED flag (`timer_output_mode … LED`, or the board is laid out that way).
  - What to do: `timer_output_mode`, set `AUTO` back; the strip — on the stock LED pad (`inav-mixer-vtol`).
- **Symptom:** the LEDs flicker, the colors are wrong
  - Possible cause: a 3.3 V data level with the strip powered from 5 V; a power sag.
  - What to do: per the INAV documentation — lower the strip supply to 4.7 V or less (a diode in the supply line); a separate BEC, a common ground.
- **Symptom:** after moving a config from 8.x the arm and GPS colors went back to the old ones, and the `mode_color` lines gave errors
  - Possible cause: the special colors moved from mode 6 to mode 7.
  - What to do: replace 6 with 7 in the `mode_color 6 …` lines.
- **Symptom:** the arm and GPS colors set on the LED Strip tab are not applied
  - Possible cause: in Configurator 9.1.0 the special color buttons are tied to mode 6 — according to the source that is LOITER (a conclusion from reading the code, not verified on hardware).
  - What to do: set `mode_color 7 <index> <color>` in the CLI and check with the `mode_color` command.
- **Symptom:** the indicators on a quadcopter blink only on some of the arms
  - Possible cause: the front LEDs are not in the row `y = 0`, or the left ones are not in the column `x = 0`.
  - What to do: move the coordinates to the corners of the grid.
- **Symptom:** PINIO does not respond to the switch
  - Possible cause: `pinio_box` does not hold the permanent id; there is no `aux` line; there was no reboot; the board has no `PINIOn_PIN`.
  - What to do: `get pinio_box`, `aux`, the USER mode must be highlighted on the Modes tab; check the `target.h` of the board.
- **Symptom:** the VTX is on when the switch is “off”, and vice versa
  - Possible cause: an inverted PINIO or a board switch with reversed logic.
  - What to do: measure the level in both positions, flip the `aux` range.
- **Symptom:** after adding a rule with operation 38 the throttle, a stick or arming do not follow the radio: the motor spins up by itself, the aircraft cannot be disarmed with the switch or arms without it
  - Possible cause: operand A holds the number of a control channel — 1…4 (4 is throttle) or the channel of the ARM switch; or A is 0 and is constrained to channel 1. The override holds while the rule is active and does not depend on the state of the receiver.
  - What to do: remove the propellers; disable the rule (`logic N 0 …` or the Programming tab); change A to a free AUX channel; check on the Receiver tab that with the rule active only the one intended channel changes.
  - Consequences: full throttle or arming without a pilot command; no way to disarm with the switch.
- **Symptom:** the shutter does not fire on every interval
  - Possible cause: the window is shorter than two logic ticks at this speed; the remainder is compared with zero; the pulse is longer than the interval.
  - What to do: W ≥ 0.2 s · v; a pulse duration less than N / v.
- **Symptom:** the shutter does not fire at all although the rules are true
  - Possible cause: the override channel has no USER range; the CLI is open (the logic is stopped); `pinio_box2` is not set.
  - What to do: the Programming tab — the state of the rules, the Modes tab — USER2 highlighted.
- **Symptom:** the beeper is silent on USB
  - Possible cause: the ON_USB condition is disabled with `feature VBAT` and there is no battery; `BEEPER MUTE` is active.
  - What to do: `beeper ON_USB`; check the range of mode 60.
- **Symptom:** the beeper is weak or does not sound at all
  - Possible cause: `beeper_pwm_mode` does not match the type of the beeper or the board.
  - What to do: an active beeper — `OFF`; `ON` — only if the board supports PWM on the beeper pin.
- **Symptom:** arming fails, “MOTOR BEEPER ACTIVE” on the OSD
  - Possible cause: the `BEEPER` switch is on, the motors are beeping, and the guard pause does not expire.
  - What to do: turn `BEEPER` off, wait 0.4–1.2 s.
- **Symptom:** a crashed aircraft does not beep
  - Possible cause: RX_LOST is disabled; there was no arm after power-up; the battery came off.
  - What to do: `beeper RX_LOST`; with the radio connected — the `BEEPER` switch; only a self-powered beeper helps against a lost battery.

## checklist
- [ ] A `diff all` is saved; in `mode_color` lines from 8.x mode 6 is replaced with 7
- [ ] The strip current on white is calculated, the BEC rating ≥ 1.5 × the sum; more than 13 LEDs on the 2 A BEC of the example means a separate BEC
- [ ] After enabling `LED_STRIP` the Outputs tab shows the same motors and servos
- [ ] The front LEDs of a multirotor are in `y = 0`, the left ones in `x = 0`; there is no empty `led` line in the middle
- [ ] `pinio_box` and `aux` have 47, 48, 57, 58, not 37, 38, 48, 49; there was a reboot after `save`
- [ ] The PINIO level is measured in both switch positions before the VTX is connected
- [ ] RX_LOST is enabled; the `BEEPER` mode is assigned; `BEEPER MUTE` is not on a random switch
- [ ] For the shutter: W ≥ 0.2 s · v, the pulse is shorter than N / v (bearing in mind that it lasts up to 0.4 s), the override channel is free on the radio
- [ ] In every rule with operation 38 operand A is a free AUX channel written as a number: not 1…4 (4 is throttle), not the ARM channel, not the FAILSAFE, RTH or MANUAL channel; checked without propellers on the Receiver tab

## references
- INAV 9.1.0 ledstrip.c and ledstrip.h (function letters, palette, modes, quadrants, 128 LEDs) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/io/ledstrip.c | primary | A
- INAV 9.1.0 light_ws2811strip.c (the frame, the LED pin modes, PWM) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/drivers/light_ws2811strip.c | primary | A
- INAV 9.1.0 cli.c (`led`, `color`, `mode_color`, `ledpinpwm`, `beeper`, `aux`, `logic`) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/cli.c | primary | A
- INAV 9.1.0 pwm_mapping.c (the conflict of the LED timer with motors and servos) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/drivers/pwm_mapping.c | primary | A
- INAV 9.1.0 fc_msp_box.c (permanent mode ids) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/fc_msp_box.c | primary | A
- INAV 9.1.0 piniobox.c and pinio.c (PINIO, the levels at boot) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/io/piniobox.c | primary | A
- INAV 9.1.0 beeper.c (conditions, priorities, the DShot beacon) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/io/beeper.c | primary | A
- INAV 9.1.0 logic_condition.h and logic_condition.c (operations 38, 40, 47, 52, operands) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/programming/logic_condition.c | primary | A
- INAV 9.1.0 lights.c (LIGHTS under `USE_LIGHTS`) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/io/lights.c | primary | A
- INAV 9.1.0 rcdevice_cam.c (CAMERA CONTROL 1–3) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/io/rcdevice_cam.c | primary | A
- INAV 9.1.0 settings.yaml (defaults and limits of the settings) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/settings.yaml | primary | A
- INAV 9.1.0 LED pin PWM.md | https://github.com/iNavFlight/inav/blob/9.1.0/docs/LED%20pin%20PWM.md | primary | A
- INAV 9.1.0 LedStrip.md (the `mode_color` numbers are outdated, see notes) | https://github.com/iNavFlight/inav/blob/9.1.0/docs/LedStrip.md | primary | B
- INAV 9.1.0 Programming Framework.md | https://github.com/iNavFlight/inav/blob/9.1.0/docs/Programming%20Framework.md | primary | A
- Betaflight 2025.12 msp_box.c (id USER1–4, BEEPER MUTE, CAMERA CONTROL) | https://github.com/betaflight/betaflight/blob/2025.12.5/src/main/msp/msp_box.c | primary | B

## notes
The firmware was not built or run: all the behavior was obtained by reading the source of INAV 9.1.0 (compared with the 8.0.1 tree) and of Configurator 9.1.0; it was not checked on hardware or in SITL. This concerns first of all three conclusions that are not in the documentation: the “north” and “west” quadrants only in `y = 0` and `x = 0`; the special color buttons of Configurator 9.1.0 write to mode 6 (LOITER); nothing calls the names GPS_STATUS and DISARM_REPEAT.

What changed since 8.0.1 in the files of this topic: `ledstrip.c/.h` — the LOITER mode was added, and the special colors moved from 6 to 7 (the version of the settings group did not change); `beeper.c` — the DShot beacon respects disabled conditions and is not sent on “pauses”; `logic_condition.h` — operations 55 and 56 and operands 46–49 were appended at the end, and the numbers 38, 40, 47, 52 are the same; PINIO pins on 109 boards instead of 71. `piniobox.c`, `pinio.c`, `light_ws2811strip.c`, `lights.c`, `rcdevice_cam.c`, `sound_beeper.c`, `rc_modes.h` did not change, and the permanent mode ids are the same. Release 9.0.0 was not checked separately, hence “9.x (present in 9.1.0)”.

Discrepancies between the 9.1.0 documentation and the code: `docs/LedStrip.md` — `mode_color 6 …` for the special colors (7 in the code) and “L requires a current sensor” (in the code, without one, the percentage is computed from the voltage); `docs/OSD Joystick.md` calls the command `led_pin_pwm`, while in `cli.c` it is `ledpinpwm`; `docs/LED pin PWM.md` speaks of 32 LEDs, and the driver sends 128.

The current of 0.06 A per LED is an upper estimate from `el-power-design`; the actual current depends on the LED type and is measured on the bench. The PINIO level before the firmware is initialized (bootloader, DFU) does not follow from the source and depends on the pull resistors of the board.
