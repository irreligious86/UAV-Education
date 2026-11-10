---
id: bf-cli
title: "CLI and resource remapping in Betaflight"
level: L3
readingTime: 45 min
firmware: Betaflight 4.5+
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
source_hash: 9af6f291e217
---

## summary

The Betaflight command line (CLI) is a text interface that gives you access to the flight controller's configuration at a level the graphical interface doesn't offer. From the CLI you can change any parameter, including ones not exposed on the configurator tabs, check the hardware state, manage resources (microcontroller pins) and make backups.

The key practical goal of this article is to give you confident command of `resource` and pin remapping without reflashing, and to teach you to inspect what is in the firmware build and restore the configuration after a failure.

## theory

### CLI architecture

The CLI runs over a serial port (UART), using the same channel as the configurator (`MSP`, `MultiWii Serial Protocol`). To enter the CLI from a terminal (e.g. PuTTY/screen), send the `#` character — it switches the controller into command mode.

### Key commands and what they do

- Session control: `save`, `exit`, `batch start`, `batch end`
- Viewing the configuration: `get`, `diff`, `dump`, `status`, `version`
- Changing parameters: `set`, `feature`, `profile`, `rateprofile`
- Resource remapping: `resource`, `timer`
- Troubleshooting and debugging: `tasks`, `flash_info`, `dma`

### Diff vs Dump: what to use and when

`diff all` prints only the changed parameters. It is the main format for backups and for safe transfer within the same firmware version.

`dump all` prints a full snapshot of the configuration, including default values. It suits deep troubleshooting, but is dangerous to carry between different versions.

It is recommended to save separately:
- `diff all`
- `resource show`
- `status` (version/build)

### Resource remapping: concept and limits

The `resource` command manages the “function -> physical pin” binding:

```text
resource <FUNCTION> <INDEX> <PIN> 
resource MOTOR 1 B00 
resource MOTOR 5 NONE
```

- ADC resources (`ADC_BATT`, `ADC_CURR`, `ADC_RSSI`) can only be assigned to ADC pins.
- UARTs are limited by the controller's hardware blocks — not every pin can be used as a serial port.
- For DShot, timers and DMA are critical: a wrong pin/channel leaves the motors dead.

### Betaflight 4.5 specifics

Between versions, the names and logic of some parameters change:

- D-term naming: in 4.5 `d_roll` is the peak D and `d_min_roll` is the base; in 2025.12 it's the other way round: `d_roll` is the base and `d_max_roll` is the peak (`d_min_*` were removed).
- GPS rescue: some variables were reworked.
- Failsafe landing: differences in naming/behavior appeared.

Because of this, you can't mindlessly paste old backups into new firmware.

### Checking the build contents via BUILD KEY

In Betaflight 4.5+ `status` shows a `BUILD KEY`. Put it into the URL below and you get JSON with the list of enabled options (`Options`):

```text
https://build.betaflight.com/api/builds/<BUILD_KEY>/json
```

This helps diagnose missing features (e.g. GPS/LED/VTX) without reflashing.

### The recipes you need most often (commands from `cli/cli.c`)
| Task | Command |
|---|---|
| Find the version, target / BUILD KEY | `version` / `status` |
| CPU load, arming flags, gyro rate | `status`, `tasks` |
| Move a motor to another pad | `resource MOTOR 3 B01` → `save` (`resource show all` — what's in use) |
| Change the motor order without resoldering | `resource` pair swap, or “Motor direction/remap” on the Motors tab |
| Reverse one motor's direction (DShot commands) | `dshotprog 0 21` (21 — reversed, 20 — normal; on some ESCs 7/8 — direction 1/2), then `dshotprog 0 12` (save settings); motors without props, index from 0 (255 — all motors) |
| Check DShot telemetry | `dshot_telemetry_info` |
| Timers/DMA (motor, LED, serial conflicts) | `timer`, `dma show` |
| Reset to defaults without saving / with saving | `defaults nosave`, `defaults` |
| Enter the DFU bootloader | `bl` (or `bl rom`) |
| Flash as a USB drive (pulling logs) | `msc` |
| Flash/configure ESCs | `serialpassthrough`/`escprog` via the ESC configurator |
| Batch-load a diff without intermediate reboots | `batch start` … `batch end` → `save` |
| Channel ranges, stick map | `rxrange`, `map AETR1234` |
| Profiles | `profile 1`, `rateprofile 2` (Betaflight has no `battery_profile` command) |
| Beeper/sound test, sensors | `beeper`, `play_sound`, `gyroregisters` (detected sensors are in the `status` output) |
| Board signature and identification | `board_name`, `manufacturer_id`, `mcu_id`, `signature` |

### Worked example: the motor 2 pad burned off
An F405 board, the M2 pad came off. `resource show all` — free timer pads: `LED_STRIP 1 A08`. Check `timer A08 list` — there's a timer with DMA; `resource LED_STRIP 1 NONE`, `resource MOTOR 2 A08`, `timer A08 AF1` (if needed), `dma pin A08 0`, `save`; Motors tab — motor 2 spins in the right position, without props; `diff all` into the repo with a comment. If the pad's timer conflicts with the other motors' DShot (one DMA group), `dma show` will reveal it, and bitbang DShot (`dshot_bitbang = ON`) works around some conflicts.

{{diagram:bf-resource-remap|Moving a motor to another pad: check the timer and DMA, free the old resource, assign the new one, save and check on the Motors tab.}}

## practice

### Getting into the CLI

1. Connect the flight controller over USB and open Betaflight Configurator.
2. Go to the CLI tab.
3. Click `Connect` if the connection didn't come up automatically.

The terminal alternative:
- connect to the port (`/dev/ttyACM0` on Linux or `COMx` on Windows);
- set the baud rate to `115200`;
- send the `#` character.

### Making a full backup

Before any changes, save the current state:

```text
status
version
diff all
resource show
timer show
```

Save the output to a file — it gives you:
- the version and build;
- the list of changed parameters;
- resource assignments;
- the timer configuration.

### Viewing and changing parameters

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

### Motor remapping: a full example

Scenario: the FC is rotated 90° clockwise without changing the orientation in the firmware.

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

### Checking build options via BUILD KEY

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

### Restoring the configuration from a backup

1. Do a reset:

```text
defaults
```

2. After the reboot, enter the CLI again.
3. Paste the backup commands in parts (not as one huge block).
4. Check the critical parameters for your firmware version.
5. Run `save`.

## diagnostics

- **Symptom:** The CLI doesn't respond, commands don't execute.
  - Possible cause: wrong CLI entry (`#` not sent), a port conflict, wrong baud rate.
  - What to do: make sure the CLI tab is active, close other applications that access the COM port, check the MSP baud rate on the port (`serial`/Ports tab) and the terminal baud rate (for USB VCP it doesn't matter).

- **Symptom:** After pasting a backup, the drone behaves incorrectly.
  - Possible cause: a firmware version mismatch.
  - What to do: compare the `version` from the backup with the current version, restore via `diff all` rather than `dump all`, and check the critical parameters by hand.

- **Symptom:** Remapping produces `also used by MOTOR` errors.
  - Possible cause: a temporary resource overlap during sequential assignment.
  - What to do: first clear the assignments (`resource MOTOR N none`), then assign the new ones, and save with `save`.

- **Symptom:** After remapping, the motors don't work or work incorrectly.
  - Possible cause: wrong pin, a timer/DMA conflict, no DShot support on the chosen pin.
  - What to do: run `resource show` and `timer show`, check them against the board pinout and the functions each pin supports.

- **Symptom:** The `save` command hangs or the controller doesn't reboot.
  - Possible cause: an unstable USB connection, power, a corrupted configuration.
  - What to do: reconnect power and USB, check the cable; if it happens again, run `defaults` and restore step by step.

- **Symptom:** You can't get the BUILD KEY or the URL returns an error.
  - Possible cause: an old Betaflight version (< 4.4, before Cloud Build), the key wasn't copied completely, a wrong URL.
  - What to do: make sure the version is 4.5+, copy the key again, and if needed try the alternative endpoint `.../<BUILD_KEY>/log`.

## references

- Betaflight CLI Documentation | https://betaflight.com/docs/wiki/guides/current/Cli | primary | A
- Betaflight Resource Remapping Guide | https://www.betaflight.com/docs/wiki/guides/current/Resource-remapping | primary | A
- Betaflight 4.5 CLI Command Reference | https://betaflight.com/docs/wiki/guides/archive/Betaflight-4.5-CLI-commands | primary | A
- How to Check Betaflight Build Options | https://oscarliang.com/check-betaflight-build-options/ | secondary | B
