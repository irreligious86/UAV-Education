---
id: bf-led-buzzer
title: "LEDs, the beeper and beacons: LED_STRIP, `led` / `color` / `mode_color`, beeper, DShot beacon"
level: L2
readingTime: 50 min
firmware: Betaflight 2025.12 (checked against 2025.12.5); the labs were captured on the 4.5 sources (tag 4.5.3 and the 4.5-maintenance branch numbered 4.5.6 — not a release) and 2025.12
status: published
added: 2026-11-14
tags:
  - Betaflight
  - LED_STRIP
  - WS2812
  - beeper
  - DShot beacon
  - rxfail
  - CLI
  - finding the aircraft
related:
  - bf-cli
  - bf-modes-osd
  - bf-adjustments
  - bf-failsafe
  - el-power-design
  - f-esc-firmware
next:
  - bf-hd-osd-video
source: content/betaflight/bf-led-buzzer.md
source_hash: 9531b0bab2f5
---

## summary
A WS2812/SK6812 strip, the beeper and the DShot beacon (“the motors beep”) show the state of the aircraft and help to find it in the grass. This module goes through them from the Betaflight 2025.12 source (the 4.5 differences are named where they occur): the power, current and signal level of the strip, `resource LED_STRIP` and why an LED on a motor's timer breaks DShot, the `led` syntax, the `color` palette with inverted saturation, `mode_color`, the RACE/BEACON/STATUS profiles; all the `beeper` conditions with their priorities and sounds, the exact code of RX_LOST / RX_LOST_LANDING and the role of the WAS_EVER_ARMED flag, `rxfail` for the BEEPER switch, `beacon` and the procedure for finding a crashed aircraft. The labs: a Python port of the firmware's parser and color math (the 16×16 grid, the current budget, the beeper masks, the beacon timeline) and a second script — the condition table from the source, `rxfail`, “who beeps after a crash” in four scenarios; then the bench without props: a multimeter before power, the strip current, and checks of RX_LOST, rxfail and the beacon.

## theory
### The strip hardware
The WS2812 (WS2811, SK6812) is an LED with a built-in driver and three wires: **5 V, GND, DIN**. The LED pad on the board → `DIN` of the first one, `DOUT` → `DIN` of the next; the number = the order along the wire, from zero. Two strips in parallel from one `DIN` show the same thing.

- **Current (a course guideline).** Up to 60 mA per LED at full white (≈ 20 mA per channel at a value of 255), 20 mA on average — Adafruit's rule of thumb. The Betaflight documentation: a NeoPixel Jewel 7 in white ≈ 350 mA. The estimate: I ≈ N · 3 · 20 mA · V / 255, where V = 255 · `ledstrip_brightness` / 100 (integer math, as in the firmware); in Python — `n*3*20*(255*b//100)/255`. 16 white LEDs at 100 % — 960 mA, 32 — 1.92 A, almost 10 W.
- **The BEC check (a course guideline).** Margin = I_BEC − I_other − I_strip, and it must be no less than 20 % of (I_BEC − I_other). Example: a 2 A BEC, the receiver, camera and GPS at 0.9 A, 16 white LEDs at 0.96 A → a margin of +140 mA against the required 220 mA → the strip goes on a separate BEC. The 4 Hz failsafe blinking with a 50 % duty cycle gives half on average, but the peak is the full current.
- **Why not from the board's 5 V.** The flight controller's BEC (1–3 A, see the specification) already feeds the receiver, camera and GPS. A long strip in white sags the rail — the receiver and the FC itself suffer. The documentation advises a separate BEC (or half of the strip from another BEC) with a **common ground**.
- **Signal level.** DIN reads a “1” from 0.7·VDD: at 5 V that is 3.5 V, while an MCU pin gives 3.3 V. The solutions: a 74AHCT125/74HCT245 buffer powered from 5 V (Adafruit), or powering the strip below 4.7 V through a diode in the positive lead (3.3 / 0.7 = 4.71 V — the recipe from the Betaflight documentation).
- **Supporting parts (Adafruit).** A 300–500 Ω resistor in the data line at the first LED, not at the FC; a 500–1000 µF ≥ 6.3 V capacitor across the strip's supply; on a live circuit — ground first, data last.

### Build, resource, timer
Cloud Build: the `LED_STRIP` option; `LED_STRIP_64` — 64 LEDs instead of 32 (on an F411 the build will fail). Without the option `config.c` clears `feature LED_STRIP` on every boot. The pin: `resource LED_STRIP 1 <pin>`, usually already set by the board config.

The driver (`light_ws2811strip_hal.c`, on F4 — `light_ws2811strip_stdperiph.c`) takes the pin's **timer** and a **DMA stream**, then rewrites the prescaler and period of the whole timer for 800 kHz: a 1.25 µs bit, a “1” ≈ 2/3 of the period, a “0” ≈ 1/3. No DMA, or the channel is taken — initialization silently returns false: the strip is dark, the motors are unharmed.

It is dangerous when the LED is on the **same timer as a motor**. A timer has one time base (PSC/ARR) for its 4 channels, and DShot through DMA sets its own: DSHOT600 = 12 MHz × 20 ticks (`pwm_output_dshot.c`). The strip is initialized **after** the motors (`fc/init.c`) and overrides the prescaler, while DShot rewrites the period (ARR) for itself on every frame. Both break: the motor gets a frame at the wrong rate (the ESC does not start or beeps “no signal”), and the strip gets garbage. With `dshot_bitbang` (AUTO: on F4 — with bidirectional DShot, on other MCUs — always, except PROSHOT) a pacer timer, TIM1 or TIM8, is needed. `bbFindPacerTimer()` looks for it after the strip and skips the ones in use. If the LED took the last suitable one (an F411 has only TIM1), the motors are given `motorWriteNull`, and they do not spin.

The check: `resource`, `timer show` (the lines `LED_STRIP` and `MOTOR 4` next to each other under one `TIMn:` — a conflict), `dma show` (`DMA2 Stream 7: LED_STRIP`). Moving it — `timer <pin> list`, then `resource`/`timer`/`dma pin`, `save` (details in `bf-cli`).

### The `led` line
`led <i> <x>,<y>:<directions>:<functions>:<color>`, i = 0…31. Per `parseLedStripConfig()`:
- **x, y** 0…15 — `atoi` and a 4-bit mask: 17 silently becomes 1. 0,0 is the north-west, with the nose at the top.
- **Directions** `N E S W U D`. The `F` function takes the color of the **first bit in the order N,E,S,W,U,D**: “SE” = the color of E (DARK_VIOLET), not S (RED).
- **The base function** — one: `C` color, `F` flight mode/orientation, `A` arm state, `L` battery, `S` RSSI, `G` GPS, `R` thrust ring; 2025.12 added `P` GPS bar, `E` battery bar, `U` altitude (4.5 does not have them). Each base letter overwrites the previous one.
- **Overlays** — any number: `T` by AUX, `Y` rainbow, `O` Larson scanner, `B` blink, `V` color by VTX frequency, `I` indicators from the sticks, `W` warnings. The function block is ≤ 10 characters, otherwise an error.
- **Color** — a palette index 0…15; 16 and above silently become 0.

The trap: a line that packs into zero (`0,0::C:0`) **ends the strip** — `updateLedCount()` counts up to the first zero entry. A zero in the middle cuts off the tail.

The behavior of the functions in STATUS:
- `L`/`S`: hue = max(−30 + 1.5·percent, 0): red at ≤ 20 %, yellow at 60 %, green at 100 %. The charge is computed from mAh with `bat_capacity` > 0, otherwise from the voltage between `vbat_min_cell_voltage` and `vbat_max_cell_voltage` — a current sensor is not required.
- `A`: disarmed — green, armed — blue.
- `W`: a 1.6 s cycle of 0.4 s windows: arming blocked (green), battery not OK (red, if a voltage sensor is configured), failsafe (yellow/blue), flip over after crash (purple). The colors are hard-coded. “Not OK” includes NOT_PRESENT: on USB without a battery W blinks red — that is normal.
- `B`: two 100 ms flashes every 1.5 s; `R`: while armed a running light, faster with throttle.

### The palette and `mode_color`
`color <i> <h>,<s>,<v>`: i 0…15, H 0…359, S and V 0…255. Saturation is **inverted** (`hsvToRgb24()`: `sat = 255 − s`): S = 0 is the pure color, 255 is white. That is why WHITE = `0,255,255` and RED = `0,0,255`. A number out of range is an error, and the color is zeroed to black. The defaults: 0 BLACK, 1 WHITE, 2 RED, 3 ORANGE, 4 YELLOW, 5 LIME_GREEN, 6 GREEN, 7 MINT_GREEN, 8 CYAN, 9 LIGHT_BLUE, 10 BLUE, 11 DARK_VIOLET, 12 MAGENTA, 13 DEEP_PINK, 14–15 black.

`mode_color <mode> <function> <color>`: modes 0–5 (ORIENTATION, HEADFREE, HORIZON, ANGLE, MAG, BARO) × directions 0–5 — the colors for `F` (priority HEADFREE, MAG, HORIZON, ANGLE, otherwise ORIENTATION; BARO is not used). The ORIENTATION defaults: N WHITE, E DARK_VIOLET, S RED, W DEEP_PINK, U BLUE, D ORANGE. `mode_color 6 <0…7> <color>` — the special colors: disarmed, armed, animation, background, blink background, GPS no satellites / no fix / fix. `mode_color 7 0 <channel>` — the channel of the `T` overlay (3 by default, throttle).

### Profiles and brightness
- **STATUS** (the default) — everything above.
- **RACE** — the whole strip in `ledstrip_race_color`; BLACK = color by VTX frequency.
- **BEACON** — blinking in `ledstrip_beacon_color`, period `ledstrip_beacon_period_ms` 500, lit for `ledstrip_beacon_percent` 50 % → **2 flashes/s** (the documentation says “once a second” — the code disagrees with it).

In RACE and BEACON, with failsafe active (stage 2; it persists after a failsafe disarm until the link returns) or in BEEPER mode, the strip blinks in the color `ledstrip_visual_beeper_color` with a period of `BEACON_FAILSAFE_PERIOD_US = 250` and a 50 % duty cycle (`applySimpleProfile()`). The name and the comment “2Hz” are misleading: the value goes into `millis() %`, so it is 250 ms — **4 flashes/s**. `ledstrip_visual_beeper = ON` acts only in RACE/BEACON; in STATUS the W LEDs always blink with the beeper when there are no warnings.

`ledstrip_brightness` 5…100 multiplies V (`v·brightness/100`) — the current drops in proportion. The LEDLOW mode (id 15) turns the strip off.

The profile from the radio: `adjrange` with function 30 (LED_PROFILE), a select of 3: < 1300 µs RACE, 1300–1699 BEACON, ≥ 1700 STATUS. There is no beep, and nothing is written to EEPROM. In the OSD the Adjustment range element shows the label “LED PROFILE”; brightness from the radio is function 31 LED_DIMMER (select, 100 positions, the label “LED DIMMER”). Both labels and function 31 appeared in 2025.12. In 4.5 there is **no** label: `adjustmentLabels[]` ends at “OSD PROFILE”, and the element reads a pointer past the end of the array — the text is unpredictable.

### The beeper: hardware and CLI
An active buzzer sounds from DC; an MCU pin cannot drive it, so the board has a transistor switch (the pads are usually BZ+ — supply, BZ− — the switch). A passive one needs `beeper_frequency` — 50 % PWM on the pin's timer; 0 means an active buzzer.

Check `beeper_inversion` by the code, not by the name: `systemBeep()` writes `inverted ? on : !on` to the pin. ON — “beep” = high level (the base of an NPN switch), OFF — low. `beeper_od` = ON — open drain. The default comes from the board (`pg/beeper_dev.c`): with `BEEPER_INVERTED` in the config — ON/OFF, without it — OFF/ON. The current values of all three — `get beeper`.

The mask of disabled conditions is stored in `beeper_off_flags`, but it is not a `set` variable — it is changed by the `beeper` command (or by the Configurator over MSP, `MSP_SET_BEEPER_CONFIG`). The default is 0: everything is enabled.
- `beeper` — a `Disabled:` line with the list of disabled conditions (or `none`).
- `beeper list` — `Available:`, all the names of the current version.
- `beeper -NAME` disables, `beeper NAME` enables, `beeper -ALL` / `beeper ALL` — all at once; in a `diff` a disabled condition looks like `beeper -RX_LOST`.
- The name is compared **by prefix, case-insensitively**, and the first match in the table is taken: `beeper -RX` will disable RX_LOST.

Modes on switches (`aux`, ids per `msp_box.c`): **13 BEEPER** — while it is active, `beeperUpdate()` requests RX_SET every 10 ms, and the beeper sounds continuously 0.1 s / 0.1 s; **52 BEEPER MUTE** — `beeper()` immediately silences everything, including RX_LOST, and with it the RX_LOST beacon; the RX_SET beacon in 2025.12 (the BEEPER switch with the link alive) is not silenced by MUTE; **37 GPS BEEP SATELLITE COUNT** — the number of satellites (with the GPS feature); **15 LEDLOW** — turns the strip off.

### Conditions, priorities, sound
The mask bit = `1 << (number in beeperMode_e − 1)` (`BEEPER_GET_FLAG`), not the row number in the table. The priority is the second field of `beeperTable[]`, 0 being the highest. The sound comes from the `beep_*` arrays (the unit is 10 ms): “+500 −500” is 500 ms of sound, 500 ms of pause; there is no repeat inside a sequence, the calling code repeats it. The table is the output of the step 6 script on the 4.5.3 and 2025.12.5 sources.

| Condition | Bit 4.5 / 2025.12 | Prio. | Sound, ms | When it sounds |
|---|---|---|---|---|
| GYRO_CALIBRATED | 0 | 0 | 3 × (+200 −100) | after gyro calibration at startup; compass calibration succeeded |
| RX_LOST | 1 | 1 | +500 −500 | link loss; the condition by version is in the subsection below |
| RX_LOST_LANDING | 2 | 2 | SOS | while armed in the AUTO-LAND or GPS Rescue failsafe phase |
| DISARMING | 3 | 3 | +150 −50 +150 −50 | disarm |
| ARMING | 4 | 4 | +300 −50 +50 −50 | arm without the GPS feature |
| ARMING_GPS_FIX | 5 | 5 | +50 −50 +150 −50 +50 −50 +150 −300 | arm with GPS, satellites ≥ `gps_rescue_min_sats` |
| ARMING_GPS_NO_FIX | 23 / 22 | 6 | 3 × (+300 −50) | arm with GPS, fewer satellites |
| BAT_CRIT_LOW | 6 | 7 | +500 −20 | battery CRITICAL (with `use_vbat_alerts`) |
| BAT_LOW | 7 | 8 | +250 −500 | battery WARNING (with `use_vbat_alerts`; with `use_consumption_alerts` — by mAh as well) |
| GPS_STATUS | 8 | 9 (sounds as MULTI_BEEPS, 14) | n × (+50 −100), the last pause 500 | mode 37: the number of satellites with a fix, > 4; the GPS_STATUS bit only allows the start, the sound is gated by the MULTI_BEEPS bit |
| RX_SET | 9 | 10 | +100 −100 | BEEPER mode (13); also — the HEADADJ confirmation |
| ACC_CALIBRATION / _FAIL | 10 / 11 | 11 / 12 | 2 × (+50 −50) / +200 −150 +350 −50 | accelerometer calibration, start and failure of compass calibration |
| READY_BEEP | 12 | 13 | a melody, 7 notes | once while disarmed, when GPS is ready |
| MULTI_BEEPS | 13 | 14 | assembled on the fly | confirmations (save, profiles, adjustments) and arming disable codes |
| DISARM_REPEAT | 14 | 15 | −1000 +100 | the disarm stick is being held |
| ARMED | 15 | 16 | −2450 +100 −50 | armed with MOTOR_STOP without airmode, throttle down |
| SYSTEM_INIT | 16 | 17 | 10 × 25 ms at boot | boot (`fc/init.c`, bypassing the queue) |
| ON_USB | 17 | 18 | — | special: if it is **disabled** and there is no battery — everything is silent |
| BLACKBOX_ERASE | 18 | 19 | 2 × (+50 −50) | the flash erase is finished |
| CRASHFLIP (in 4.5 — CRASH_FLIP) | 19 | 20 | +200 −150 +350 −50 | flip over after crash is active |
| CAM_CONNECTION_OPEN / CLOSE | 20 / 21 | 21 / 22 | short trills | RunCam button emulation |
| RC_SMOOTHING_INIT_FAIL (4.5 only) | 22 | 23 | 3 × (+100 −100) +500 −250 | armed while the RC smoothing filters are not ready; removed in 2025.12 |

How `beeper()` picks the sound (the same in 4.5 and 2025.12): a request with a priority number ≥ the current one (0 is the highest) is ignored — the same mode is not restarted, BAT_LOW (8) will not interrupt RX_LOST (1), and RX_LOST will interrupt anything except gyro calibration. An important detail: a bit in `beeper_off_flags` only prevents the sound from being turned on (`BEEP_ON`), while the sequence still runs — and **occupies the queue**. A disabled `beeper -RX_LOST` is silent, but BAT_LOW and RX_SET still will not get through, and the DShot beacon on RX_LOST (controlled by `beacon`, not `beeper`) will keep working.

Because of the CRASH_FLIP → CRASHFLIP rename and the removal of RC_SMOOTHING_INIT_FAIL, the lines `beeper -CRASH_FLIP` and `beeper -RC_SMOOTHING_INIT_FAIL` from a 4.5 `diff` give an error in 2025.12, and a mask with bit 23 means nothing in 2025.12: ARMING_GPS_NO_FIX moved to bit 22.

### RX_LOST, RX_LOST_LANDING and WAS_EVER_ARMED
Both conditions are set by `failsafeUpdateState()` (`flight/failsafe.c`), which the scheduler calls every 10 ms. The RX_LOST condition in the two versions:

```c
// 4.5.3, flight/failsafe.c:251
if (!receivingRxData && (armed || ARMING_FLAG(WAS_EVER_ARMED))) { beeperMode = BEEPER_RX_LOST; }
// 2025.12.5, flight/failsafe.c:252
if (!receivingRxData && !usbCableIsInserted()) { beeperMode = BEEPER_RX_LOST; }
```

What is behind the words:
- **`receivingRxData`** is `rxLinkState == FAILSAFE_RXLINK_UP`. After 100 ms (4.5) / 150 ms (2025.12, `RXLOSS_TRIGGER_INTERVAL`) without packets only RXLOSS appears in the OSD; `receivingRxData` becomes false `failsafe_delay` (15 = 1.5 s by default, no less than 100 ms) after the last good packet, and RX_LOST starts at the same time as Stage 2 does on an armed aircraft. When the link returns, RX_LOST continues for another `failsafe_recovery_delay`, until `rxLinkState` becomes UP. At boot the state is already DOWN, but the function does not run for the first 5 s (`FAILSAFE_POWER_ON_DELAY_US`): power up the aircraft without the radio — RX_LOST no sooner than 5 s.
- **`WAS_EVER_ARMED`** is set by `disarm()` (`fc/core.c:440`; in 2025.12 — `core.c:498`, `crashFlipModeActive`) — on disarm, not on arm, and **not** after a disarm from flip over after crash (`!flipOverAfterCrashActive`). The flag lives in RAM: an FC reboot clears it. That is why in 4.5 “turned the radio off on the bench — silence” (there was no arm), and an aircraft whose FC rebooted from an impact or a bouncing connector is **silent** after the crash.
- **`usbCableIsInserted()`** (`drivers/usb_io.c`) is the USB detect pin **or** an established VCP connection to a computer. With a computer RX_LOST is silent on any board; from a USB charger (no communication with a host) — only if the board has a USB detect pin, otherwise it sounds. For a test, disconnect USB and restart the FC from the battery (a course estimate, not verified on hardware: on an F4 without VBUS sensing the VCP state may not reset right after the cable is pulled). From here on in the module “the RX_LOST condition” refers to this subsection.

RX_LOST_LANDING (SOS) is set only in the `FAILSAFE_LANDING` (AUTO-LAND) and `FAILSAFE_GPS_RESCUE` phases and only `if (armed)` (`failsafe.c:354`, `:378`). With DROP the phase is `FAILSAFE_LANDED` immediately → disarm → then RX_LOST. After the disarm at the end of AUTO-LAND, RX_LOST (priority 1) immediately overrides SOS (2).

{{lesson:bf-failsafe|The failsafe stages, `failsafe_delay` and the DROP / AUTO-LAND / GPS Rescue procedures, which set the moment and the kind of signal here.}}

### `rxfail` and the BEEPER switch
`rxfail <channel> <a|h|s> [µs]` sets what the FC substitutes into a channel when it is invalid (`rx/rx.c`, `getRxfailValue()`). The channel is an index 0…17 after `map`: 0–3 are roll, pitch, yaw, throttle; **AUXn = 3 + n** (AUX4 = 7, AUX7 = 10). The modes from `rxFailsafeModesTable[]` (`cli/cli.c`):
- `a` (auto) — channels 0–3 only: sticks at `mid_rc`, throttle at `rx_min_usec` (in 3D — the middle). For AUX — `###ERROR IN rxfail: PARSING FAILED###`.
- `h` (hold) — the last good value; on a switch-triggered failsafe — the current one. The default for all AUX channels.
- `s <µs>` (set) — a fixed value, for any channel. It is stored in steps of 25 µs from 750: value = 750 + 25·⌊(v − 750)/25⌋ after limiting to 750–2250. `s 1990` becomes 1975, `s 2500` silently becomes 2250 (the “value out of range” error is unreachable). Without a number — `INVALID ARGUMENT COUNT`, a number after `h` — `PARSING FAILED`, channel 18 and above — `CHANNEL NOT BETWEEN 0 AND 17`.
- `rxfail` without arguments prints all 18 lines, `rxfail 10` — one.

When this takes effect: for 300 ms (`MAX_INVALID_PULSE_TIME_MS`) from the last good packet the last value is held, then all channels get their `rxfail` values. This works **while disarmed too** — the failsafe state has nothing to do with it — and right after boot without the radio (after 300 ms). In Stage 2 the FC replaces the sticks itself (center and `failsafe_throttle`), while the AUX channels still follow `rxfail`.

An example — the `bf-modes-osd` layout, BEEPER on AUX7 in the 1700–2100 range: `rxfail 10 s 2000`, `save`. About 0.3 s after link loss the BEEPER mode turns on by itself: RX_SET +100 −100, the strip in RACE/BEACON blinks at 4 Hz, and in 4.5 with `beacon RX_SET` the motors beep as well. What to expect by version (the scenarios of step 6):
- **An ordinary crash** (there was an arm, the battery is in place): after `failsafe_delay` RX_LOST arrives — priority 1 against 10 for RX_SET, and from then on you hear the RX_LOST rhythm. Until it arrives (0.3 s … `failsafe_delay`) RX_SET sounds, and after that rxfail changes only the strip.
- **The FC rebooted from the impact** (WAS_EVER_ARMED cleared): 4.5 without rxfail is silent, with rxfail it beeps from 0.3 s, and the motor beacon — from 1.24 s (times of the step 6 model, from boot). 2025.12 gives RX_LOST from 5 s anyway; rxfail adds sound right away and the strip blinking. The RX_SET beacon in 2025.12 works only with the link alive (`failsafeIsReceivingRxData()`), so here the motors beep only on RX_LOST.

Precautions: there must be no other modes on this channel in this range — `s 2000` will also turn on FLIP OVER AFTER CRASH and PREARM on link loss if they are there (check `aux`). Without the radio, the board on the bench beeps 0.1/0.1 s — that means the setting works. A test without turning the radio off: the FAILSAFE switch (STAGE1) applies `s` immediately and passes channels in `h` through at their current values.

### The DShot beacon and the ESC beacon
The ESC beeps with the motor windings on the DShot command BEACON1…5 (`beeper_dshot_beacon_tone`, 1 by default); the DShot protocol is required. The conditions are only RX_LOST and RX_SET, and **both are off by default** (`DEFAULT_DSHOT_BEACON_OFF_FLAGS = DSHOT_BEACON_ALLOWED_MODES`; in RACE_PRO builds RX_SET is on): enable `beacon RX_LOST`. The `beacon` syntax is the same as for `beeper`.

`beeperUpdate()` sends the command only with `!areMotorsRunning()` (not while armed, not during a motor test), no sooner than 1.2 s after a disarm (`DSHOT_BEACON_GUARD_DELAY_US`), not during an arming attempt and no more often than once per 450 ms (`DSHOT_BEACON_MODE_INTERVAL_US`). In 2025.12 the RX_LOST beacon runs while the RX_LOST sequence is sounding and there is no USB, and RX_SET — while the BEEPER mode is active and the link is alive; in practice once per ~0.45 s. In 4.5 there were two intervals — 450 ms (RX_SET) and 950 ms (RX_LOST), the check ran only at the moments the beeper toggled (in practice ~0.5 and ~1.0 s), there were no conditions about USB and the link, and the beacon followed the **current** sequence: with `beacon RX_SET` without `beacon RX_LOST`, RX_LOST displaces RX_SET, and the motors are silent. The firmware will not let the beacon through while armed. The ESC beeps for up to ~250 ms (the comment in the code), and the windings carry current about half of the time (a course estimate: ~250 ms out of 450–520 ms; in 2025.12 the same with RX_LOST too): the motors and ESCs heat up and the battery drains — do not keep it going for minutes on the bench.

Bluejay's own beacon (beacon delay, 10 min without throttle by default) runs off the stream of DShot frames with zero throttle, and a disarmed FC sends them even without the radio — so it also sounds after link loss, but only with the FC and the battery alive.

{{lesson:f-esc-firmware|The ESC beacon versus the DShot beacon: Bluejay's beacon delay and beacon strength, the behavior of AM32 and what each beeping source needs.}}

### Finding a crashed aircraft
| Source | Power | What must be alive | When it sounds | The battery was ejected |
|---|---|---|---|---|
| FC beeper: RX_LOST | the main battery through the FC's BEC | the FC | `failsafe_delay` after link loss, with the RX_LOST condition met (see above) | silent |
| FC beeper: the BEEPER switch or `rxfail … s` | the same | the FC; for the switch — the link | the switch — immediately; rxfail — 0.3 s after link loss | silent |
| DShot beacon | the main battery (ESC) | the FC, ESC, DShot | as RX_LOST / RX_SET, ≥ 1.2 s after a disarm; the intervals are in “The DShot beacon and the ESC beacon” | silent |
| ESC beacon (Bluejay) | the main battery | the ESC and the DShot stream from the FC | after the beacon delay without throttle (10 min by default), independent of the radio | silent |
| The strip in RACE/BEACON, 4 Hz | 5 V from the battery | the FC | failsafe is active (a loss in the air) or BEEPER mode | goes dark |
| A self-powered buzzer with its own cell | its own | nothing | power from the aircraft is gone | **beeps** |

{{diagram:bf-buzzer-find-tree|What beeps after a crash (2025.12): without the battery — only the self-powered buzzer; with the battery and the link — the BEEPER switch; without the link — RX_LOST and the motor beacon, if the FC does not see USB; the Bluejay beacon does not depend on USB.}}

The search procedure:
1. Do not turn the radio off right away. Remember the last frame and the direction; the VTX does not lower its power during failsafe (`bf-failsafe`) — the picture in the goggles helps you walk toward the signal.
2. The link is still there — the BEEPER switch: the beeper at 0.1/0.1 s, the strip at 4 Hz, the motors with `beacon RX_SET`.
3. There is no link or the aircraft is far away — turn the radio off. After `failsafe_delay` RX_LOST starts at 0.5/0.5 s (the condition is in the RX_LOST subsection), the motors — with `beacon RX_LOST`; `rxfail` on the BEEPER channel covers the case of an FC reboot.
4. Walk toward the sound, stopping to listen. Battery warnings cannot be heard behind RX_LOST (priority 8 against 1), and the beeper, the beacon and the strip drain the battery — search at once.
5. Silence with an intact aircraft means an ejected battery or a dead FC: only a self-powered buzzer will help.

### Reference table
| Variable / command | Default | Range | Meaning | 2025.12 versus 4.5 |
|---|---|---|---|---|
| `feature LED_STRIP` | on for an unconfigured board | — | the strip task, 60 Hz | the same |
| `resource LED_STRIP 1 <pin>` | the board config | a pin with a timer and DMA | the data output | the same |
| `led <i> x,y:dir:fn:col` | all 0 | i 0–31 (63 with LED_STRIP_64) | the layout; zero = the end | + the functions `P`, `E`, `U` |
| `color <i> h,s,v` | the palette above | 0–15; 359/255/255 | S is inverted | the same |
| `mode_color <m> <f> <c>` | see above | m 0–7 | modes, special colors, AUX | the same |
| `ledstrip_profile` | STATUS | RACE/BEACON/STATUS | the profile | the same; + function 31 LED_DIMMER and the OSD labels |
| `ledstrip_race_color` | ORANGE | 14 names | BLACK = by VTX | the same |
| `ledstrip_beacon_color` | WHITE | 14 names | the BEACON color | the same |
| `ledstrip_beacon_period_ms` | 500 | 50–10000 | the BEACON period | the same |
| `ledstrip_beacon_percent` | 50 | 0–100 | the “lit” share | the same |
| `ledstrip_beacon_armed_only` | OFF | OFF/ON | BEACON only while armed | the same |
| `ledstrip_visual_beeper` | OFF | OFF/ON | the strip with the beeper (RACE/BEACON) | the same |
| `ledstrip_visual_beeper_color` | WHITE | 14 names | also the color of the failsafe / BEEPER blinking | the same |
| `ledstrip_brightness` | 100 | 5–100 | V × percent | the same |
| `ledstrip_grb_rgb` | GRB | GRB/RGB/GRBW | GRBW: SK6812 RGBW, W = min(R,G,B) | the same |
| `ledstrip_rainbow_delta` / `_freq` | 0 / 120 | 0–359 / 1–2000 | the `Y` overlay | the same |
| `beeper [-]NAME`, `beeper list` | everything enabled (`beeper_off_flags` = 0) | 24 conditions + ALL | the beeper | 23 conditions: CRASHFLIP, no RC_SMOOTHING_INIT_FAIL; the ARMING_GPS_NO_FIX bit 23 → 22 |
| `beacon [-]NAME` | both disabled | RX_LOST, RX_SET | DShot beacon | a single 450 ms interval; RX_LOST — without USB, RX_SET — with the link alive |
| `beeper_dshot_beacon_tone` | 1 | 1–5 | the BEACONn tone | the same |
| `beeper_inversion`, `beeper_od` | from the board | OFF/ON | the active level, open drain | the same |
| `beeper_frequency` | 0 | 0–16000 | 0 — an active buzzer, otherwise PWM, Hz | the same |
| `rxfail <ch> a\|h\|s [µs]` | 0–3 `a`, AUX `h` | ch 0–17; 750–2250, step 25 | the channel value on link loss | the same |
| the RX_LOST condition | — | — | no RC data for longer than `failsafe_delay` | 4.5: while armed or after an arm; 2025.12: without USB |
| the `aux` modes | — | 13 BEEPER, 15 LEDLOW, 37 GPS BEEP SAT. COUNT, 52 BEEPER MUTE | switches | the same |

### Place in the system

- **Receives:** the timer and DMA stream of the `LED_STRIP` pin (`bf-cli`); 5 V from a separate BEC with a common ground (`el-power-design`); the arm, battery and link-loss states — `rxLinkState` and the failsafe phases (`bf-failsafe`, `bf-arming-safety`); adjustment functions 30 and 31 for the profile and brightness (`bf-adjustments`).
- **Provides:** arming disable codes by sound; RX_LOST, the DShot beacon and the strip blinking for finding a crashed aircraft; the strip color by state — to the pilot and the spotter.
- **If you get it wrong here:** the LED on the same timer as a motor → the strip overrides the prescaler, DShot runs at the wrong rate, the ESC does not start; it looks like a faulty ESC, and it is found through `timer show` (`bf-cli`, `bf-servos-pwm`). A long strip in white from the flight controller's 5 V → the rail sags, and the receiver and the FC itself suffer (`el-power-design`). `rxfail … s` on a channel that carries another mode as well will turn that mode on at every link loss (`bf-modes-osd`).

## practice
Betaflight SITL cannot be built here, and SITL has no strip or beeper anyway. The main path is two scripts (the course working folder, stage 6): `bf-led-buzzer.led_lab.py` (steps 1–5) and `bf-led-buzzer.lab2.py` (step 6). The tables are taken from the source, and the logic repeats the firmware. The current is the model “20 mA per channel at 255”; on hardware it is checked with an ammeter.

The output of steps 1–5 was captured on the source of the `4.5-maintenance` branch (commit `7dcc851`). Its `version.h` already says 4.5.6, but there is no such release: the latest release of the branch is 4.5.5. The `src/` code matches it except for the version number in `version.h`; apart from that only build files differ. From here on in the module this tree is called “4.5-maintenance”. The second argument of the script — the 2025.12 tree — is needed only for the comparison line in step 4. The parsing of `led`, the palette and the masks are computed the same way in 2025.12; what differs is the table of beeper conditions, the three new base functions of the strip (`P`, `E`, `U`), and the beacon timing and the RX_LOST condition in step 5 (covered in the theory). Step 6 was captured on 4.5.3 and 2025.12.5: the script reads `io/beeper.h`, `io/beeper.c`, `cli/cli.c`, `rx/rx.h`, and ports the logic of `flight/failsafe.c` and `rx/rx.c` by hand; beeper.c/.h, failsafe.c, rx.c/.h are the same in 4.5.3 and 4.5.5 (cli.c differs, but not in the `rxfail` code).

```
python3 -I bf-led-buzzer.led_lab.py ~/src/betaflight-4.5/src/main ~/src/betaflight-2025.12/src/main --svg grid.svg
```

### Step 1. Parsing `led` lines
The core is a port of `parseLedStripConfig()`:

```python
    x, y = int(out[0] or 0) & 0xF, int(out[1] or 0) & 0xF   # atoi, then CALCULATE_LED_XY masks 4 bits
    d = sum(1 << i for i, c in enumerate(DIRS) if c in out[2])
    fn, ov = 0, 0
    for ch in out[3]:
        if ch in FUNCS:
            fn = FUNCS.index(ch)          # every base letter overwrites: the last one wins
        if ch in OVLS:
            ov |= 1 << OVLS.index(ch)
    col = int(out[4] or 0)
    col = 0 if col >= 16 else col
    packed = ((x << 4) | y) | (fn << 8) | (ov << 12) | (col << 22) | (d << 26)
```

```text
led 3 14,1:EN:FW:0       -> 0x0C0401E1  prints 'led 3 14,1:NE:FW:0'
led 4 14,14:SE:FW:0      -> 0x180401EE  prints 'led 4 14,14:ES:FW:0'
led 10 0,0::C:0          -> 0x00000000  prints 'led 10 0,0::C:0'
strip length = 10 (updateLedCount stops at the first all-zero entry; led 10 0,0::C:0 is that terminator)
  1,1:NW:FCW:0           -> '1,1:NW:CW:0'  packed 0x24040011
  17,1::C:2              -> '1,1::C:2'  packed 0x00800011
  3,3::C:16              -> '3,3::C:0'  packed 0x00000033
  1,1:NW:FWIOBYTVACL:0   -> PARSE ERROR (cliShowParseError)
```

`led` prints the directions in the order NESWUD and the base function first — that is how a `diff` looks. “FCW” silently became “CW”, x = 17 — one, color 16 — zero; only the 11-character block gave an error.

### Step 2. The grid and the colors
The layout: 0–3 on the front arms (NW/NE), 4–7 on the rear ones, 8–9 in the center with `L`. The colors in STATUS while disarmed and at 100 % charge:

```text
  led 3: fn F dirs NE hsv (0, 255, 255) -> rgb (255, 255, 255)   60.0 mA
  led 4: fn F dirs ES hsv (270, 0, 255) -> rgb (127, 0, 255)   30.0 mA
  led 6: fn F dirs SW hsv (0, 0, 255) -> rgb (255, 0, 0)   20.0 mA
  led 8: fn L dirs    hsv (120, 0, 255) -> rgb (0, 255, 0)   20.0 mA
  total 380 mA (model, 20 mA per channel at 255)
  L function at battery  20 %: hue   0 -> rgb (255, 0, 0)
quadrants (updateDimensions): north y<=7, south y>=8, west x<=7, east x>=8
```

{{diagram:bf-led-grid-layout|The lab layout as the firmware will show it: “SE” on the rear right ones gives violet, not red — F takes the first direction bit in the order N,E,S,W; the fix is the direction `S`.}}

The rear right ones being violet is the direction-order trap. The fix: `led 4 14,14:S:FW:0`, `led 5 13,13:S:FW:0`.

### Step 3. The current budget
```text
  10 LEDs all WHITE, brightness 100 % -> rgb (255, 255, 255) ->    600 mA (3.00 W at 5 V)
  32 LEDs all WHITE, brightness 100 % -> rgb (255, 255, 255) ->   1920 mA (9.60 W at 5 V)
  32 LEDs all WHITE, brightness  30 % -> rgb (76, 76, 76) ->    572 mA (2.86 W at 5 V)
  GRBW (SK6812 RGBW) white at 100 %: R,G,B + W=min(r,g,b) all on -> 80 mA per LED in the model
  budget: BEC 2.0 A - other 5 V loads 0.9 A - strip 1920 mA = -820 mA for 32 LEDs at 100 % -> separate 5 V BEC
```

A 2 A BEC and 0.9 A of other loads are an example; substitute your own. Calculate the worst case — white at 100 %: BEACON, the visual beeper and failsafe give white in the field.

{{diagram:chart-bf-led-current|The strip current grows linearly with ledstrip_brightness: 32 white LEDs at 100 % (1.92 A) do not fit into a BEC margin of 1.1 A, at 30 % they do (572 mA).}}

### Step 4. The beeper masks
Bit = `1 << (enum − 1)` per `beeperMode_e`, not per the table:

```text
    'beeper -RX' -> Disabled RX_LOST
    'beeper -ARM' -> Disabled ARMING
  beeper_off_flags = 0x00020013 -> off: ['GYRO_CALIBRATED', 'RX_LOST', 'ARMING', 'ON_USB']
    'beacon RX_LOST' -> Enabled RX_LOST
  dshotBeaconOffFlags = 0x00000200 -> beacon fires on: ['RX_LOST']
  decode 0x00800000: ['ARMING_GPS_NO_FIX']
  2025.12: removed ['CRASH_FLIP', 'RC_SMOOTHING_INIT_FAIL'], added ['CRASHFLIP']; ARMING_GPS_NO_FIX bit 23 -> 22
```

`beeper -RX`, typed “for short”, disabled the most needed signal. Masks are not portable between 4.5 and 2025.12 — carry them over by names (and remember that the name CRASH_FLIP is written CRASHFLIP in 2025.12).

### Step 5. The RX_LOST and beacon timeline
A model of `beeperUpdate()` at 100 Hz, with `beacon RX_LOST` enabled; “TX off” is the moment the firmware recognized the signal loss:

```text
  A) never armed since power-up, TX off at 0 s: buzzer starts 0 times, DShot beacons 0
  B) armed 0 s, disarmed 1.0 s, TX off 1.5 s: buzzer on at [1.5, 2.51, 3.52, 4.53, 5.54] s
     DShot beacon at [2.5, 3.51, 4.52, 5.53] s (guard 1200 ms after disarm, interval > 950 ms)
  C) armed and TX off at 1.5 s (still armed): buzzer 2 starts, DShot beacons 0 (motors running)
  D) BEEPER switch on, disarmed: buzzer on at [0.0, 0.21, 0.42, 0.63, 0.84, 1.05, 1.26, 1.47] ... s
     DShot beacon at [0.0, 0.52, 1.04, 1.57, 2.09, 2.62] s (interval > 450 ms)
```

A — “turned the radio off on the bench, and it is silent”: there was no arm. B — the first beacon no sooner than 2.2 s (disarm + 1.2), then once per ~1 s. C — no beacon while armed. D — the BEEPER switch: a beacon every ~0.52 s.

### Step 6. Conditions, `rxfail` and “who beeps after a crash”
The script takes the beeper tables from both trees and ports `cliRxFailsafe()`, `beeper()`, `beeperUpdate()` (both versions), the RX_LOST condition and the 300 ms channel hold. 10 ms ticks, `failsafe_delay` = 15, both `beacon` conditions enabled. Section 1 of the output is the condition table in the theory, section 5 is the BEC example from “The strip hardware” (16 white LEDs, +140 mA against the 220 needed). To run it: `python3 -I bf-led-buzzer.lab2.py <4.5>/src/main <2025.12>/src/main`. Sections 2–4:

```text
== 2. beeper_off_flags
  beeper -RX_LOST, -BAT_LOW, -ON_USB -> 4.5 0x00020082, 2025.12 0x00020082
  decode 0x00800000: 4.5 ['ARMING_GPS_NO_FIX']  2025.12 []
  decode 0x00400000: 4.5 ['RC_SMOOTHING_INIT_FAIL']  2025.12 ['ARMING_GPS_NO_FIX']

== 3. rxfail (index 0..3 = roll, pitch, yaw, throttle; AUXn = 3 + n)
  rxfail 10            -> rxfail 10 h
  rxfail 10 a          -> ###ERROR IN rxfail: PARSING FAILED###
  rxfail 10 s          -> ###ERROR IN rxfail: INVALID ARGUMENT COUNT###
  rxfail 10 s 2000     -> rxfail 10 s 2000
  rxfail 7 s 1990      -> rxfail 7 s 1975
  rxfail 7 s 2500      -> rxfail 7 s 2250
  rxfail 3 a           -> rxfail 3 a
  rxfail 10 h 2000     -> ###ERROR IN rxfail: PARSING FAILED###
  rxfail 18 h          -> ###ERROR IN rxfail: CHANNEL NOT BETWEEN 0 AND 17###

== 4. beeper arbitration after link loss (10 ms ticks, failsafe_delay 15, beacon RX_LOST and RX_SET enabled)
  A crash, disarm 0 s, TX off 2 s, battery, no USB
    4.5      buzzer: first 3.49 s, sequences ['RX_LOST'] x9 in 12 s; DShot beacons 9 first (3.49, 'RX_LOST'); strip 4 Hz (RACE/BEACON) from None
    2025.12  buzzer: first 3.49 s, sequences ['RX_LOST'] x9 in 12 s; DShot beacons 19 first (3.49, 'RX_LOST'); strip 4 Hz (RACE/BEACON) from None
  B FC rebooted on impact: boot 0 s, no link, never armed
    4.5      buzzer: first None s, sequences [] x0 in 12 s; DShot beacons 0 first None; strip 4 Hz (RACE/BEACON) from None
    2025.12  buzzer: first 5.01 s, sequences ['RX_LOST'] x7 in 12 s; DShot beacons 16 first (5.01, 'RX_LOST'); strip 4 Hz (RACE/BEACON) from None
  C = B + rxfail <BEEPER ch> s 2000
    4.5      buzzer: first 0.3 s, sequences ['RX_SET'] x56 in 12 s; DShot beacons 21 first (1.24, 'RX_SET'); strip 4 Hz (RACE/BEACON) from 0.3
    2025.12  buzzer: first 0.3 s, sequences ['RX_LOST', 'RX_SET'] x30 in 12 s; DShot beacons 16 first (5.01, 'RX_LOST'); strip 4 Hz (RACE/BEACON) from 0.3
  D bench: USB in, never armed, TX off 2 s
    4.5      buzzer: first None s, sequences [] x0 in 12 s; DShot beacons 0 first None; strip 4 Hz (RACE/BEACON) from None
    2025.12  buzzer: first None s, sequences [] x0 in 12 s; DShot beacons 0 first None; strip 4 Hz (RACE/BEACON) from None

```

How to read it. A: RX_LOST starts 1.49 s after the last packet (that is `failsafe_delay`, not 100 ms), and there are 9 beacons in 8.5 s in 4.5 and 19 in 2025.12 (the intervals from the theory). B: the FC reboot erased WAS_EVER_ARMED — 4.5 is silent; 2025.12 starts at 5 s, when failsafe monitoring turns on. C: `rxfail … s 2000` on the BEEPER channel — sound and the strip from 0.3 s in both versions; the RX_SET beacon in 4.5 from 1.24 s (the 1.2 s guard from boot), while in 2025.12 the motors wait for RX_LOST — the RX_SET beacon needs a live link. D: on USB nothing beeps. Section 3: AUX does not accept `a`, and the value is quantized down in steps of 25 and clipped at 2250.

### Step 7. The config
```
feature LED_STRIP
led 4 14,14:S:FW:0
led 5 13,13:S:FW:0
led 10 0,0::C:0
set ledstrip_brightness = 30
beacon RX_LOST
aux 4 13 6 1700 2100 0 0
rxfail 10 s 2000
adjrange 5 0 4 900 2100 30 4 0 0
save
```

The layout is the same as in the theory and in `bf-modes-osd`. The other `led` lines are from step 2. `aux 4 13 6 …` — BEEPER on AUX7 up, the same rule index 4 as in `bf-modes-osd` (the `aux` channel counts from AUX1 = 0: 6 = AUX7); `rxfail 10 s 2000` — the same AUX7 (AUXn = 3 + n: 3 + 7 = 10): on link loss BEEPER will turn on by itself. `adjrange … 30 …` — the strip profile on the three-position AUX5 (free in the `bf-modes-osd` layout). While the slot is active, moving AUX5 overrides `set ledstrip_profile`. The `aux 4` line repeats the BEEPER rule from `bf-modes-osd` and overwrites nothing in that layout; the `adjrange 5` slot is also free there (the OSD profile is slot 3). In your own layout take free `aux`/`adjrange` indices; there must be no other modes on AUX7 in 1700–2100.

### Moving to real hardware
**Props off, the battery through a current limiter.**
1. Before power, with a multimeter: the strip's 5 V↔GND — no short; the strip's GND↔the FC's GND and DIN↔the LED pad — continuity; DIN↔5 V — none.
2. `resource`, `timer show`, `dma show`: LED_STRIP does not share a timer with MOTOR. Every motor spins in the Motors tab.
3. An ammeter in the strip's positive lead (the 10 A range). All `led` lines temporarily `C:1` (white): the current at `ledstrip_brightness` 100 and 30, and the voltage at the strip under load. The quiescent current — with the strip turned off by the LEDLOW mode.
4. The BEEPER switch — RX_SET and, with `beacon RX_SET`, the motors ~2 times a second. BEEPER MUTE — the beeper is silent; in 2025.12 the motors keep beeping on `beacon RX_SET` (MUTE does not silence them).
5. Arm without props, disarm, disconnect USB and restart the FC from the battery (in 4.5, arm and disarm again after the restart), turn the radio off: after `failsafe_delay` the beeper at 0.5/0.5 s, the motors — no sooner than 1.2 s after the disarm, at the interval from the theory; the strip in RACE/BEACON does not change (failsafe is not active while disarmed). After 2 min touch the motors and the ESCs.
6. With `rxfail 10 s 2000`: the radio on, the BEEPER switch off, turn on the FAILSAFE switch — the beeper at 0.1/0.1 s right away, the strip in RACE/BEACON blinks at 4 Hz. Then remove and apply power with the radio off: 0.1/0.1 s right after the startup signals (gyro calibration, with priority 0, overrides it for its duration); in 4.5 with `beacon RX_SET` — the motors as well. In 2025.12 without USB the rhythm will change to RX_LOST 0.5/0.5 after ~5 s — that is normal (priority 1 against 10).
7. The profile selector — the three profiles in turn, the label “LED PROFILE” in the OSD (4.5 has no label).

**Abort:** a smell, a hot strip or BEC, an FC reboot on white, 5 V under load below 4.75 V (a course guideline), a motor twitched from the beacon, hot motors after the beacon, another mode turned on during the rxfail test. Remove power; separate the timers or the strip's power; fix `aux`.

**Flight** (optional, at night, brightness 30 %): 2 min of hover; the voltage sag in the OSD is no more than without the strip + 0.1 V (a course guideline).

Self-check: the lab is complete when:
- (calculation) the first script has been run on the source (write down the version), the output of steps 1–5 is saved in your notes and matches the output in the module (on 4.5-maintenance: `strip length = 10`, `total 380 mA`, `beeper_off_flags = 0x00020013`), and you have written down in your own words why “SE” gave violet and why `0,0::C:0` cuts the strip short (compare with the reference below);
- (calculation) the second script printed the same lines of sections 2–4 as in step 6: the mask `0x00020082`, `rxfail 7 s 1990 -> rxfail 7 s 1975`, scenario B for 4.5 without sound, scenario C with the first sound at 0.3 s;
- (calculation) for your own layout the worst-case current is calculated (white at 100 %: 60 mA per LED in the model, 10 of them — 600 mA, 32 — 1920 mA) along with the BEC margin; a margin of less than 20 % of (I_BEC − I_other) means a separate BEC;
- (hardware) your notes contain `timer show` / `dma show` where LED_STRIP does not share a timer with MOTOR, and the current measurements at 100 and 30 % next to the model's numbers; 5 V under load is no lower than 4.75 V (a course guideline);
- (hardware) you heard for yourself and wrote down: RX_LOST `failsafe_delay` after turning the radio off, the beacon no sooner than 1.2 s after the disarm, BEEPER MUTE silences the beeper, and `rxfail` on the BEEPER channel gives sound without the radio right after boot.

**Reference for self-check.** “SE” is violet because the `F` function takes the first direction bit in the order N, E, S, W: for “SE” that is E, not S; the fix is the direction `S`. `led 10 0,0::C:0` packs into `0x00000000`, and `updateLedCount` stops at the first zero entry — everything after it is not part of the strip. If your current for 32 white LEDs at 30 % came out as 576 mA instead of 572 — the brightness was applied to the current, not to the channel value (76 out of 255). If the beacon in timeline B comes before 2.2 s — the 1200 ms guard after the disarm was not taken into account; if the beeper sounds in scenario A — the model does not check the 4.5 RX_LOST condition. In the second script: RX_LOST in scenario A at 2.1 s instead of 3.49 — the link loss was taken as 100 ms, not `failsafe_delay`; an RX_SET beacon in scenario C for 2025.12 — the live-link condition was left out; `rxfail 7 s 1990` = 1990 — the quantization down in steps of 25 was forgotten.

## diagnostics
- **Symptom:** the strip does not light up
  - Possible cause: the firmware has no LED_STRIP (the feature is cleared after a reboot), the first `led` line is zero, the pin has no DMA/timer, LEDLOW is on.
  - What to do: `feature`, `led`, `resource`, `timer show`, `dma show`, the Modes tab; rebuild with the option.
- **Symptom:** after the strip was connected the ESC beeps “no signal” and a motor does not spin
  - Possible cause: the LED is on a motor's timer, or it took the TIM1/TIM8 that bitbang needs.
  - What to do: `timer show`; move the LED to another pad or change `dshot_bitbang_timer`; check the motors without props.
- **Symptom:** flicker, random colors, only the first one lights up
  - Possible cause: 3.3 V against 0.7·5 V, a long data wire, no common ground.
  - What to do: a common ground, a resistor at the strip, a 74AHCT125 buffer or a diode in the strip's positive lead.
- **Symptom:** green lights up red; a “mess” from the second LED on
  - Possible cause: `ledstrip_grb_rgb` (RGB/GRB) or an RGBW strip.
  - What to do: one LED with `C:6`; red — change the order; a “mess” — GRBW.
- **Symptom:** only part of the strip lights up
  - Possible cause: a zero `led` in the middle, or more than 32 without `LED_STRIP_64`.
  - What to do: find `0,0::C:0` in `led`.
- **Symptom:** the FC reboots or the video drops out on white
  - Possible cause: sag of the 5 V BEC.
  - What to do: a measurement under load; a separate BEC with a common ground; brightness 30.
- **Symptom:** turned the radio off — the aircraft is silent
  - Possible cause: less than `failsafe_delay` has passed, or less than 5 s since power-up; the RX_LOST condition is not met (subsection “RX_LOST…”: USB, no arm in 4.5); `beeper -RX` or `-RX_LOST`; BEEPER MUTE; `-ON_USB` on USB power.
  - What to do: wait 2 s, `beeper`, Modes; disconnect USB and restart the FC from the battery, test after an arm without props.
- **Symptom:** after an impact the aircraft lies intact, the battery is in place, but it is silent (4.5)
  - Possible cause: the FC rebooted from the impact or a bouncing connector — WAS_EVER_ARMED is cleared, and RX_LOST does not sound in 4.5.
  - What to do: `rxfail <3 + n> s 2000` on the BEEPER channel (AUXn) or a move to 2025.12; during the search — turn on the radio and the BEEPER switch.
- **Symptom:** the board without the radio beeps short 0.1/0.1 s beeps right away
  - Possible cause: `rxfail … s` on the BEEPER channel — that is by design; or the BEEPER switch in `h` is stuck on.
  - What to do: turn the radio on; if it is a nuisance on the bench — the BEEPER MUTE switch, not removing rxfail.
- **Symptom:** `rxfail 10 a` → `###ERROR IN rxfail: PARSING FAILED###`
  - Possible cause: the `a` mode exists only for channels 0–3.
  - What to do: for AUX — `h` or `s <µs>`.
- **Symptom:** the motors do not beep on signal loss
  - Possible cause: `beacon` is off by default; not DShot; < 1.2 s after the disarm; the FC sees USB (2025.12, see the RX_LOST condition); in 4.5 only `beacon RX_SET` is enabled while RX_LOST is sounding; in 2025.12 the RX_SET beacon from rxfail does not work without the link.
  - What to do: `beacon RX_LOST`, `get motor_pwm_protocol`, a test from the battery.
- **Symptom:** the beeper sounds continuously from power-up
  - Possible cause: a wrong `beeper_inversion` / `beeper_od`.
  - What to do: toggle it, `save`, check against the board config (`get beeper`).

## checklist
- The worst-case current (white, 100 %, all LEDs) is calculated, the BEC margin is ≥ 20 %, and the power source is chosen from it
- A common ground, a resistor at the first LED, a capacitor across the strip's supply
- `timer show` / `dma show`: LED_STRIP does not share a timer with MOTOR, the motors are checked
- No zero `led` in the middle; ≤ 32 LEDs
- The directions for `F` are chosen with the order N,E,S,W in mind
- `beeper` without abbreviated names, RX_LOST is enabled, `beacon RX_LOST` is enabled
- On the BEEPER channel — `rxfail <3 + n> s 2000`, no other modes in that range
- BEEPER MUTE is not on a “forgettable” switch; RX_LOST is checked after an arm without props
- On aircraft flown over grass and forest — a self-powered buzzer

## references
- ledstrip.c — Betaflight 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/io/ledstrip.c | primary | A
- light_ws2811strip.c — Betaflight 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/drivers/light_ws2811strip.c | primary | A
- light_ws2811strip_hal.c (timer/DMA init) — Betaflight 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/drivers/stm32/light_ws2811strip_hal.c | primary | A
- beeper.c — Betaflight 2025.12.5 | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/io/beeper.c | primary | A
- beeper.h — Betaflight 2025.12.5 | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/io/beeper.h | primary | A
- failsafe.c — the RX_LOST condition, Betaflight 2025.12.5 | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/flight/failsafe.c | primary | A
- failsafe.c — the RX_LOST condition with WAS_EVER_ARMED, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/failsafe.c | primary | A
- rx.c — rxfail, getRxfailValue, the 300 ms hold, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/rx/rx.c | primary | A
- core.c — disarm() and WAS_EVER_ARMED, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/fc/core.c | primary | A
- beeper.c — Betaflight 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/io/beeper.c | primary | A
- beeper.h — conditions and DShot beacon constants, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/io/beeper.h | primary | A
- cli.c — led, color, mode_color, beeper, beacon, rxfail, timer, dma | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/cli/cli.c | primary | A
- dshot_bitbang.c — pacer timer selection, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/drivers/stm32/dshot_bitbang.c | primary | A
- LED Strip — Betaflight docs | https://betaflight.com/docs/wiki/guides/current/LED-Strip-Functionality | primary | B
- Adafruit NeoPixel Überguide — powering and best practices | https://learn.adafruit.com/adafruit-neopixel-uberguide/power.md | secondary | B

## notes
The LED Strip page on betaflight.com disagrees with the code in places (verified on 4.5-maintenance): BEACON blinks 2 times a second, not 1; `L` goes from red (≤ 20 %) to green, not from DEEP_PINK, and works without a current sensor; “up to three functions” is in fact one base function and any overlays within 10 characters. The base functions `P` (GPS bar), `E` (battery bar), `U` (altitude) exist only from 2025.12. 60 mA per LED is Adafruit's guideline; your strip's current is different, so the measurement in step 3 of the hardware part is mandatory. The scenarios of step 6 are a model: on a real FC the moment of the first sound shifts by the receiver task period (up to 100 ms) and by the scheduler phase.
