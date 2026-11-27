---
id: bf-cli
title: "The CLI and resource remapping in Betaflight"
level: L3
readingTime: 45 min
firmware: Betaflight 2025.12 (checked against 2025.12.5)
status: published
tags:
  - CLI
  - resource
  - remapping
  - backup
  - Betaflight
references:
  - title: "Betaflight CLI Documentation"
    url: "https://betaflight.com/docs/wiki/guides/current/Cli"
    tier: primary
    stack: betaflight
  - title: "Betaflight Resource Remapping Guide"
    url: "https://www.betaflight.com/docs/wiki/guides/current/Resource-remapping"
    tier: primary
    stack: betaflight
  - title: "Betaflight 4.5 CLI Command Reference"
    url: "https://betaflight.com/docs/wiki/guides/archive/Betaflight-4.5-CLI-commands"
    tier: primary
    stack: betaflight
  - title: "How to Check Betaflight Build Options"
    url: "https://oscarliang.com/check-betaflight-build-options/"
    tier: secondary
    stack: betaflight
related:
  - bf-custom
  - bf-ports
next:
  - bf-custom
source: content/betaflight/bf-cli.md
source_hash: 6da8547fb07e
---

## summary

The Betaflight command line interface (CLI) is a text interface that gives access to the flight controller configuration at a level the graphical interface does not reach. From the CLI you can change any setting, including those not exposed in the configurator tabs, check the hardware state, manage resources (microcontroller pins) and make backups.

The key practical goal of this article is to give you a confident working knowledge of `resource` and pin remapping without reflashing, and to teach you how to find out what a firmware build contains and how to restore a configuration after a failure.

## theory

### CLI architecture

The CLI runs over a serial port (UART), using the same channel as the configurator (`MSP`, `MultiWii Serial Protocol`). To enter the CLI from a terminal (for example, PuTTY/screen) you send the `#` character — it switches the controller into command mode.

### Key commands and what they are for

- Session control: `save`, `exit`, `batch start`, `batch end`
- Viewing the configuration: `get`, `diff`, `dump`, `status`, `version`
- Changing settings: `set`, `feature`, `profile`, `rateprofile`
- Resource remapping: `resource`, `timer`
- Diagnostics and debugging: `tasks`, `flash_info`, `dma`

### Diff vs Dump: what to use and when

`diff all` prints only the settings that were changed. It is the main format for backups and for a safe transfer within one firmware version.

`dump all` prints a complete snapshot of the configuration, including default values. It suits deep diagnostics but is dangerous for a transfer between different versions.

It is recommended to save separately:
- `diff all`
- `resource show`
- `status` (version/build)

### `diff`/`dump` scopes and flags
The syntax (the same in 4.5 and 2025.12): `diff [master|profile|rates|hardware|all] {defaults|bare}`, and `dump` takes the same words (`printConfig()` in `cli/cli.c`). What goes into the output:

| Command | What it prints | Wrapper |
|---|---|---|
| `diff` = `diff master` | the common settings (resource, timer, dma, feature, serial, mixer, beeper, map, led, aux, adjrange, rxrange, vtxtable, vtx, rxfail, all master-level `set` lines) **plus only the current** PID profile and **only the current** rate profile | `batch start` … `batch end`, without `defaults nosave` and without `save` |
| `diff profile` | only the current PID profile | no wrapper |
| `diff rates` | only the current rate profile | no wrapper |
| `diff hardware` | resource, timer, dma, feature, serial and the “hardware” `set` lines (`blackbox_device`, sensor buses…), without profiles | `batch` |
| `diff all` | everything from `master`, `mcu_id` and `signature`, **all 4 PID profiles and all 4 rate profiles**, and at the end — a return to the active profiles (`profile N`, `rateprofile N`) | `batch start`, `defaults nosave`, …, `save` (without `batch end`: it is printed only for `diff`/`dump` without `all`) |
| the `defaults` flag | adds to every changed line a commented-out line with the default value | — |
| the `bare` flag | removes `batch`/`defaults nosave`/`save`, `mcu_id`, `signature` and the restoring of the profile selection | — |

The trap: `diff` without `all` loses three profiles out of four. A backup “with profile 2 for Li-Ion” made with `diff` while profile 1 is active will be pasted back without profile 2. For a backup — only `diff all`; for comparing versions — `diff all defaults` (you can see what default a changed setting had). The `defaults` and `bare` flags do not work together: only the first one is processed.

{{diagram:bf-diff-scopes|A plain diff writes only the active PID and rate profile; all 4 + 4 profiles, mcu_id and the wrapper with save are only in diff all.}}

### All CLI commands
The priority A/B commands (`cmdTable[]` in `cli/cli.c`, 59 in total — the set is the same in 4.5 and 2025.12; only the argument order of `flash_read` changed: `<address> <length>` in 2025.12, `<length> <address>` in 4.5; commands behind an `#ifdef` are not present in every build):

| Command | What it does |
|---|---|
| `adjrange` | configure adjustment ranges — the in-flight adjustment slots (bf-adjustments) |
| `aux` | configure modes on AUX channels (bf-modes-osd) |
| `batch start` / `batch end` | apply a pasted block as one batch of commands |
| `beacon` | enable/disable the DShot beacon (the motors beep) for a condition: `beacon list`, `beacon RX_LOST`, `beacon -RX_LOST` (bf-led-buzzer) |
| `beeper` | enable/disable the beeper for a condition: `beeper list`, `beeper -BAT_LOW` (bf-led-buzzer) |
| `bind_rx` | initiate binding for RX SPI, SRXL2 or CRSF (ELRS); without support — `Not supported.` |
| `bl` | reboot into the bootloader (`bl rom`; on boards with external flash — `bl flash`) |
| `color`, `led`, `mode_color` | the palette, the layout and the mode colors of the LED strip (bf-led-buzzer) |
| `defaults` | reset to defaults and reboot; `defaults nosave` — without writing |
| `diff`, `dump` | the configuration: changes from default / complete (the table above) |
| `dma` | DMA assignments: `dma show`, `dma <device> <index> list` |
| `dshot_telemetry_info` | eRPM and DShot telemetry errors per motor |
| `dshotprog` | raw DShot commands to the ESCs: `dshotprog <index\|255> <command>…` |
| `exit` | exit the CLI and reboot; `exit noreboot` (from 4.5.4) |
| `feature` | list and toggle features: `feature`, `feature list`, `feature GPS`, `feature -GPS` |
| `flash_erase`, `flash_info` | erase / show info on the onboard flash chip for Blackbox (bf-blackbox) |
| `get`, `set` | read (a substring search: `get gps_rescue`) / change a setting |
| `gpspassthrough` | a USB ↔ GPS UART bridge for u-center; to leave it — replug USB/power (bf-gps-setup) |
| `help` | the command list, `help <string>` — a search |
| `map` | the RC channel order (`map AETR1234`) |
| `mixer`, `mmix` | the frame type (`mixer list`, `mixer QUADX`) / a custom motor mixer |
| `motor` | a motor value while disarmed, like a slider on the Motors tab: `motor 0 1100` (index from 0, 255 — all, 1000–2000), **without props** |
| `msc` | reboot into USB mass storage mode (downloading logs from flash/SD) |
| `profile`, `rateprofile` | select PID profile 0–3 / rate profile 0–3 (bf-rates-rc) |
| `rc_smoothing_info` | the current RC smoothing operational settings: the detected RX rate, the setpoint/FF/throttle cutoffs (bf-rates-rc) |
| `resource` | pins: `resource`, `resource show all`, `resource MOTOR 1 B00`, `… none` |
| `rxfail`, `rxrange` | the channel values in Stage 1 failsafe (bf-failsafe) / the RX channel ranges |
| `save` | save and reboot; `save noreboot` (from 4.5.4) |
| `sd_info` | the SD card state (`Not configured` / `None inserted` / `Startup failed` / the card parameters) |
| `serial` | the functions and baud rates of the serial ports (bf-ports) |
| `serialpassthrough` | a USB ↔ any UART bridge: flashing an ELRS receiver, configuring a GPS/VTX (below) |
| `servo`, `smix` | the servo endpoints and the servo mixer (bf-servos-pwm) |
| `simplified_tuning` | `apply` / `disable` — recalculate PIDs and filters from the sliders |
| `status`, `tasks`, `version` | the status and BUILD KEY / task stats / the version |
| `timer` | pin timers: `timer show`, `timer <pin> list` |
| `vtx`, `vtx_info`, `vtxtable` | the VTX on a switch / what the VTX reported / the table of frequencies and power levels (link-vtx, bf-adjustments) |

The list of features for `feature` is the `featureNames[]` array in `cli/cli.c`; `feature list` prints the list of names. The output below was captured on 4.5; in 2025.12 `feature` and `feature list` print three lines — `Enabled:`, `Available:` and `Unavailable:` (features that are not in the build), the name `RX_MSP` is no longer in the list, and `OPTICALFLOW` was added:

```text
Available: RX_PPM INFLIGHT_ACC_CAL RX_SERIAL MOTOR_STOP SERVO_TILT SOFTSERIAL GPS RANGEFINDER TELEMETRY 3D RX_PARALLEL_PWM RX_MSP RSSI_ADC LED_STRIP DISPLAY OSD CHANNEL_FORWARDING TRANSPONDER AIRMODE RX_SPI ESC_SENSOR ANTI_GRAVITY
```

In 2025.12, features missing from the build (LED_STRIP, SERVO_TILT, GPS depend on the Cloud Build options) go into the `Unavailable:` line, and an attempt to enable such a feature answers `Unavailable <name>`. In 4.5 the `Available:` list was printed from the whole table of names, and the presence of a name did not mean that the feature was in the build (the BUILD KEY check is below).

### Resource remapping: the concept and the limits

The `resource` command manages the “function -> physical pin” mapping:

```text
resource <FUNCTION> <INDEX> <PIN> 
resource MOTOR 1 B00 
resource MOTOR 5 NONE
```

- ADC resources (`ADC_BATT`, `ADC_CURR`, `ADC_RSSI`) can be assigned only to ADC pins.
- A UART is tied to the controller's hardware blocks — not every pin can be used as a serial port.
- For DShot the timers and DMA are critical: a wrong pin/channel results in motors that do not work.

### Betaflight 2025.12 specifics (what changed after 4.5)

The names and logic of some settings change between versions:

- D-term naming: in 2025.12 `d_roll` is the base D and `d_max_roll` is the peak (in 4.5 it is the other way around: `d_roll` is the peak, `d_min_roll` is the base; `d_min_*` were removed).
- GPS rescue: the throttle and the altitude loop moved to the shared `ap_*` settings (`ap_hover_throttle` — `gps_rescue_throttle_hover` before 2025.12).
- Failsafe landing: `failsafe_landing_time` in seconds (before 2025.12 — `failsafe_off_delay` in tenths of a second).
- `serial`: `diff` writes port names (`serial UART3 64 …`); the numbers from 4.5 (`serial 2 64 …`) are accepted.

Because of this, old backups must not be pasted blindly into new firmware. The full table is in the module “Introduction to Betaflight”, section “The 4.5.3 → 2025.12 transition: what was renamed and changed”.

### Checking what a firmware build contains with the BUILD KEY

`status` (4.5 and 2025.12) shows the `BUILD KEY`. Put it into the URL below to get a JSON with the list of enabled options (`Options`):

```text
https://build.betaflight.com/api/builds/<BUILD_KEY>/json
```

This helps to diagnose missing features (for example, GPS/LED/VTX) without reflashing.

### The recipes needed most often (commands from `cli/cli.c`)
| Task | Command |
|---|---|
| Find out the version, target / BUILD KEY | `version` / `status` |
| CPU load, arming flags, gyro rate | `status`, `tasks` |
| Move a motor to another pad | `resource MOTOR 3 B01` → `save` (`resource show all` — what is in use) |
| Change the motor order without resoldering | swap pairs with `resource`, or “Reorder motors” / “Motor direction” on the Motors tab |
| Reverse the direction of one motor (DShot commands) | `dshotprog 0 8` (7 — `SPIN_DIRECTION_1`, 8 — `SPIN_DIRECTION_2`: a permanent direction in the ESC), then `dshotprog 0 12` (save settings); commands 20/21 are the temporary reversal for turtle, and the firmware sends them itself; motors without props, index from 0 (255 — all motors) |
| Check DShot telemetry | `dshot_telemetry_info` |
| Timers/DMA (motor, LED, serial conflicts) | `timer`, `dma show` |
| Reset to defaults without saving / with | `defaults nosave`, `defaults` |
| Enter the DFU bootloader | `bl` (or `bl rom`) |
| Flash as a USB drive (downloading logs) | `msc` |
| Flash/configure an ESC | `serialpassthrough`/`escprog` through an ESC configurator |
| Spin one motor from the CLI (without props!) | `motor 0 1100` … `motor 0 1000`; `motor 255 1000` — all motors |
| Bind an ELRS/CRSF receiver without a button | `bind_rx` (if the build has `USE_RX_BIND`; otherwise — the binding phrase or 3 power cycles of the receiver) |
| Configure a GPS in u-center through the FC | `gpspassthrough` → close the Configurator → u-center on the same COM port; to leave — replug USB |
| Flash an ELRS receiver through the FC | `serialpassthrough <UART id> <baud>`: the id as in `serial` (UART1 = 0; in 2025.12 a name also works — `UART1`); normally ELRS Configurator does this itself with the Betaflight passthrough flashing method — the Betaflight Configurator is closed meanwhile |
| Erase the Blackbox flash / check the SD card | `flash_erase` (wait for the dots to finish) / `sd_info` |
| Which RX rate RC smoothing detected | `rc_smoothing_info` (with the receiver connected and working) |
| Batch-load a diff without intermediate reboots | `batch start` … `batch end` → `save` |
| Channel ranges, stick map | `rxrange`, `map AETR1234` |
| Profiles | `profile 1`, `rateprofile 2` (Betaflight has no `battery_profile` command) |
| Beeper/sound test, sensors | `beeper`, `play_sound`, `gyroregisters` (the detected sensors are in the `status` output) |
| Board signature and identification | `board_name`, `manufacturer_id`, `mcu_id`, `signature` |

### A worked example: the motor 2 pad burned out
An F405 board, the M2 pad came off. `resource show all` — the free timer pads: `LED_STRIP 1 A08`. Checking with `timer A08 list` — there is a timer with DMA; `resource LED_STRIP 1 NONE`, `resource MOTOR 2 A08`, `timer A08 AF1` (if needed), `dma pin A08 0`, `save`; the Motors tab — motor 2 spins in the right position, without props; `diff all` into the repository with a comment. If the pad's timer conflicts with the DShot of the other motors (one DMA group) — `dma show` will show it, and bitbang DShot (`dshot_bitbang = ON`) works around some of the conflicts.

{{diagram:bf-resource-remap|Moving a motor to another pad: check the timer and DMA, free the old resource, assign the new one, save and check on the Motors tab.}}

### Place in the system

- **Receives:** the same serial channel as the configurator (`bf-intro`); the build contents — the CLI will not enable features that are not in the firmware (`bf-custom`); the timer and DMA map of the specific board.
- **Provides:** `diff all` as a backup and as material for scripts (`bf-cli-automation`); pin assignments through `resource` for motors, servos and the LED strip (`bf-servos-pwm`, `bf-led-buzzer`); `status` with the arming flags (`bf-arming-safety`).
- **If you get it wrong here:** a backup was made with `diff` without `all` → three PID profiles and three rate profiles out of four are lost, and the profile the tuning was done for will not come back after a restore (`bf-pid`, `bf-rates-rc`). A motor was moved to a pad whose timer or DMA conflicts with the DShot of the others → the motors do not work or the `DSHOT_BBANG` flag stays set (`bf-arming-safety`).

## practice

### Getting to the CLI

1. Connect the flight controller over USB and open Betaflight App (for 4.5 — Configurator 10.10).
2. Go to the CLI tab.
3. Click `Connect` if the connection did not come up automatically.

The alternative through a terminal:
- connect to the port (`/dev/ttyACM0` on Linux or `COMx` on Windows);
- set the baud rate to `115200`;
- send the `#` character.

### Making a full backup

Before any changes, save the state:

```text
status
version
diff all
resource show
timer show
```

Save the output to a file — it gives you:
- the version and build;
- the list of changed settings;
- the resource assignments;
- the timer configuration.

### Viewing and changing settings

Viewing:

```text
get gyro_
get acc
set dyn_notch_min_hz = 150
```

Changing:

```text
set dyn_notch_min_hz = 150
set dyn_notch_q = 250
save
```

For batch editing (fewer reboots):

```text
batch start
set gyro_lpf1_static_hz = 0
set gyro_lpf2_static_hz = 300
set dterm_lpf2_static_hz = 150
batch end
save
```

### Motor remapping: a complete example

The scenario: the FC is rotated 90° clockwise without changing the orientation in the firmware.

Step 1. Check the current assignments:

```text
resource show
```

Example output:

```text
A06: MOTOR 1
A07: MOTOR 2
A11: MOTOR 3
A12: MOTOR 4
```

Step 2. The current layout:

```text
         FRONT
4 (A12)        2 (A07)

3 (A11)        1 (A06)
         BACK
```

Step 3. The target layout after rotating the FC:

```text
         FRONT
3 (A11)        4 (A12)

1 (A06)        2 (A07)
         BACK
```

Step 4. Assign the new mapping:

```text
resource MOTOR 1 none
resource MOTOR 2 none
resource MOTOR 3 none
resource MOTOR 4 none
resource MOTOR 1 A07
resource MOTOR 2 A12
resource MOTOR 3 A06
resource MOTOR 4 A11
save
```

After `save` the controller reboots with the new layout.

**An exercise without hardware: the same aircraft, other rotations.** The initial assignments are the same: `A06` — MOTOR 1, `A07` — MOTOR 2, `A11` — MOTOR 3, `A12` — MOTOR 4. A motor number is tied to a position on the frame (the layout in step 2): 1 — rear right, 2 — front right, 3 — rear left, 4 — front left. On paper, write the `resource` block for two other board installations: (a) the FC is rotated 90° **counterclockwise**; (b) the FC is rotated 180°. The technique is the same as in steps 2–4: draw which position on the frame each pad has moved to, and assign the pad the motor number of that position.

Then find four errors in the sequence in the table. Its author was solving the same task as steps 1–4 (a 90° clockwise rotation) and finished with a backup (a training example, put together by hand):

| No. | What was entered in the CLI |
|---|---|
| 1 | `resource MOTOR 1 A07` |
| 2 | `resource MOTOR 2 A12` |
| 3 | `resource MOTOR 3 A06` |
| 4 | `resource MOTOR 4 A12` |
| 5 | `diff` — the output was saved to a file as a backup |

And lastly: using the table “`diff`/`dump` scopes and flags”, write down how many PID profiles and how many rate profiles end up in the file after `diff`, `diff all`, `diff profile` and `diff hardware`.

### Checking build options with the BUILD KEY

```text
status
```

Then open:

```text
https://build.betaflight.com/api/builds/<BUILD_KEY>/json
```

An example of the options section:

```json
"Options": [
  "CLOUD_BUILD",
  "USE_DSHOT",
  "USE_GPS",
  "USE_OSD",
  "USE_SERIALRX",
  "USE_SERIALRX_CRSF",
  "USE_TELEMETRY",
  "USE_VTX"
]
```

### Restoring a configuration from a backup

1. Do a reset:

```text
defaults
```

2. After the reboot, enter the CLI again.
3. Paste the commands from the backup in parts (not as one huge block).
4. Check the settings that are critical for your firmware version.
5. Run `save`.

Self-check: the lab is complete when:
- the block for the 90° counterclockwise rotation gives `MOTOR 1 A11`, `MOTOR 2 A06`, `MOTOR 3 A12`, `MOTOR 4 A07`;
- the block for 180° gives `MOTOR 1 A12`, `MOTOR 2 A11`, `MOTOR 3 A07`, `MOTOR 4 A06`;
- each block has 9 lines, as in step 4: four `resource MOTOR N none` lines, four assignments, `save`; each of the four pads appears in the assignments exactly once;
- exactly four errors are found in the sequence from the table, and the consequence of each is written down (the reference is below);
- for the profiles you got: `diff` — 1 PID and 1 rate; `diff all` — 4 and 4; `diff profile` — 1 and 0; `diff hardware` — 0 and 0.

**Reference for self-check.** A check of the rotations without a hint: after 180° every motor gets the pad of its diagonal neighbor (1 ↔ 4, 2 ↔ 3), and the 90° counterclockwise rotation applied once more to its own result must give the block for 180°. The four errors in the table: there are no `resource MOTOR N none` lines before the assignments — `also used by MOTOR` messages will appear on entry; in line 4 pad `A12` is assigned a second time, and `A11` is assigned to nothing (it should be `resource MOTOR 4 A11`); there is no `save` — after a reboot the layout will remain the old one; the backup was made with `diff` without `all` — the file has one PID profile and one rate profile out of four. Common wrong answers: in task (a) you got the block from step 4 (`A07`, `A12`, `A06`, `A11`) — the board is rotated clockwise, not counterclockwise; in task (b) you got `A07`, `A06`, `A12`, `A11` — that is a “front ↔ rear” mirror, not a rotation: the left and right sides stayed in place; profiles are written in the answer about `diff hardware` — this scope contains only resource, timer, dma, feature, serial and the “hardware” `set` lines.

## diagnostics

- Symptom: the CLI does not respond, commands are not executed.
  - Possible cause: the CLI was not entered correctly (`#` was not sent), a port conflict, a wrong baud rate.
  - What to do: make sure the CLI tab is active, close other applications with access to the COM port, compare the MSP baud rate on the port (`serial`/the Ports tab) with the terminal baud rate (for USB VCP it does not matter).

- Symptom: after pasting a backup the drone does not work correctly.
  - Possible cause: a firmware version mismatch.
  - What to do: compare the `version` from the backup with the current version, restore from `diff all` and not from `dump all`, check the critical settings by hand.

- Symptom: `also used by MOTOR` errors appear during remapping.
  - Possible cause: a temporary overlap of resources during sequential assignment.
  - What to do: first clear the assignments (`resource MOTOR N none`), then assign the new ones and save with `save`.

- Symptom: after remapping the motors do not work or work incorrectly.
  - Possible cause: a wrong pin, a timer/DMA conflict, no DShot support on the selected pin.
  - What to do: run `resource show` and `timer show`, check them against the board pinout and the functions the pins support.

- Symptom: the `save` command hangs or the controller does not reboot.
  - Possible cause: an unstable USB connection, power, a corrupted configuration.
  - What to do: reconnect power and USB, check the cable, and if it happens again run `defaults` and restore step by step.

- Symptom: the BUILD KEY cannot be obtained or the URL returns an error.
  - Possible cause: an old Betaflight version (< 4.4, before Cloud Build), the key was not copied completely, a wrong URL.
  - What to do: make sure the version is no lower than 4.4, copy the key again, and if necessary try the alternative endpoint `.../<BUILD_KEY>/log`.

## references

- Betaflight CLI Documentation | https://betaflight.com/docs/wiki/guides/current/Cli | primary | A
- Betaflight Resource Remapping Guide | https://www.betaflight.com/docs/wiki/guides/current/Resource-remapping | primary | A
- Betaflight 4.5 CLI Command Reference | https://betaflight.com/docs/wiki/guides/archive/Betaflight-4.5-CLI-commands | primary | A
- How to Check Betaflight Build Options | https://oscarliang.com/check-betaflight-build-options/ | secondary | B
