---
id: inav-cli-backup
title: "INAV CLI: all commands, diff/dump and profiles, backup, restore and migration 7 → 8 → 9"
level: L2
readingTime: 50 min
firmware: INAV 9.1 (checked against 9.1.0)
status: published
added: 2026-11-18
tags:
  - INAV
  - CLI
  - diff
  - backup
  - migration
related:
  - inav-intro
  - inav-setup-scratch
  - inav-mixer-vtol
  - inav-osd-hd
  - inav-ipf
  - bf-cli
  - bf-cli-automation
next:
  - inav-mixer-vtol
source: content/inav/inav-cli-backup.md
source_hash: e56c6ad29699
---

## summary
The INAV CLI is the only place where the configuration of the aircraft is visible as a whole and as text: 62 commands in 9.1.0, 677 settings, three kinds of profiles. This module goes through the commands with their arguments and dangers, shows what exactly `diff`, `diff all` and `dump` print and how they differ, what does not get into a backup, in what order a config is restored and what the red `### ERROR` lines mean. Separately — `status` with the 24 arming-disabled flags, `tasks`, `feature`, auto-backup and migration in Configurator 9.1, and the 7 → 8 → 9 migration table. The lab needs no hardware and no simulator: from a fragment of the `diff all` of an aircraft on 8.0.1 you mark up every line for 9.1, count what an ordinary `diff` would have lost, put the restore order together and decode a flag line from `status`.

## theory
### Entering the CLI and what it does to the aircraft
The CLI is opened with the `#` character on an MSP port (the CLI tab in the Configurator does this itself). While the CLI is open, the arming-disabled flag `CLI` is set, logic conditions (`inav-ipf`) are not executed, and the MSP OSD is not updated. There are three ways out, and all three reboot the flight controller: `save` (write and reboot), `exit` (reboot without writing), `defaults` (reset and reboot). `save` and `exit` have no `noreboot` argument in INAV — unlike Betaflight 2025.12 (`bf-cli`).

The CLI discards everything after `#` in a line, so a backup file with comments can be pasted as is. An error always starts with `### ERROR: ` (in Betaflight — `###ERROR IN`): the client from `bf-cli-automation` is ported to INAV by replacing this string and the exit logic.

### All INAV 9.1.0 commands
`cmdTable[]` of 9.1.0 has 62 commands (61 in 8.0.1; `bind_msp_rx` was added; none were removed). Some are not built into every firmware: the condition is in brackets. `help` prints the list; on boards with ≤ 512 KB of flash (F411, F722) — names only, without descriptions and arguments.

| Command | Arguments | What it does | When it is dangerous |
|---|---|---|---|
| `help` | — | the command list | — |
| `version` | — | `# INAV/<target> <version> <date> / <time> (<git>)` and the GCC version | — |
| `status` | — | version, uptime, voltage, sensors, load, arming flags, OSD, VTX, GPS | — |
| `tasks` | — | the rate, time and load of every scheduler task | — |
| `get` | `[part of a name]` | the values of all settings whose name contains the substring, with the range | — |
| `set` | `<name> = <value>`; empty or `*` — the whole list | changes a setting in RAM until `save` | a value out of range is rejected, but whether it makes sense is not checked |
| `save` | — | a write to EEPROM and a reboot | in a batch with errors the first `save` refuses |
| `exit` | — | exit with a reboot, without writing | stops motors started with `motor` |
| `defaults` | `[noreboot]` | resets the whole configuration and writes it; without the argument — a reboot | erases everything at once, no `save` is needed |
| `batch` | `start` · `end` | batch mode: counts errors, `save` refuses when there are errors [USE_CLI_BATCH] | — |
| `diff` | `master` · `control_profile` · `mixer_profile` · `battery_profile` · `all`, then `[showdefaults]`; all optional | the differences from the defaults | without `all` — an incomplete backup |
| `dump` | the same | the whole configuration, including the defaults | when moving between versions it drags the old defaults along |
| `control_profile` | `[1…3]` | show or select the control profile (PIDs, rates, EZ Tune — their numbers are covered in `inav-mc-tuning`) | on a change of index it writes EEPROM at once |
| `mixer_profile` | `[1…2]` | the mixer profile (an F411 has one) | the same; changes the platform and the outputs |
| `battery_profile` | `[1…3]` | the battery profile | the same |
| `feature` | `list` · `<name>` · `-<name>` | the enabled features; enable; disable | the name is matched by the start of the string |
| `beeper`, `blackbox` | `list` · `<name>` · `-<name>` | the beeper conditions; the Blackbox field groups | — |
| `map` | `[AETR…]` | the channel order | a wrong map — throttle on a different stick |
| `rxrange` | `<channel> <min> <max>` | the range of a receiver channel | — |
| `aux` | `<No.> <mode id> <AUX> <from> <to>` | the mode ranges | ARM without a check of the switch |
| `adjrange` | `<No.> <slot> <AUX> <from> <to> <function> <adjustment AUX>` | in-flight adjustments (the format and the functions — `inav-adjustments`) | — |
| `serial` | `<id> <mask> <msp> <gps> <telem> <periph>`; `<id> +n` · `<id> -n` | UART functions and baud rates | removing MSP from the port you are connected through means losing the link to the Configurator |
| `mmix`, `smix` | mixer lines; `reset` | the motor and servo mixer of the active profile (`inav-mixer-vtol`) | `reset` erases the rules of the profile |
| `servo` | `<No.> <min> <max> <mid> <rate>` | the endpoints, center and rate of a servo | — |
| `timer_output_mode` | `[timer [mode]]`, mode `AUTO` · `MOTORS` · `SERVOS` · `LED` | the purpose of a timer | a motor on a servo output and vice versa |
| `motor` | `<No.> [1000…2000]` | a value on a motor output without arming | **the motor spins — only without props** |
| `resource` | — | view only: which pin is used for what | a pin cannot be reassigned |
| `safehome`, `fwapproach`, `geozone`, `wp` | their own lines; `reset`; `wp` also has `load`, `save` | safehomes, the landing approach, geozones [flash > 512 KB], the mission | `reset` erases the list |
| `logic`, `gvar`, `pid` | their own lines; `reset` | the programming framework (`inav-ipf`) | logic can change throttle and modes |
| `osd_layout`, `osd_custom_elements` | their own lines | the OSD layouts and custom elements (`inav-osd-hd`) | — |
| `led`, `color`, `mode_color`, `ledpinpwm` | their own lines | the LED strip and the LED pin [USE_LED_STRIP] | — |
| `temp_sensor` | its own lines | temperature sensors | — |
| `gpspassthrough`, `serialpassthrough` | —; `<id> [baud] [mode] [options]` | a USB ↔ UART bridge (u-center, receiver firmware) | the only way out is to disconnect power |
| `gpssats` | — | the u-blox satellite table | — |
| `bind_rx`, `bind_msp_rx`, `eleres_bind` | —; `<port>`; — | binding SRXL2; an mLRS MSP receiver (since 9.1); EleRes | — |
| `flash_info`, `flash_erase`, `sd_info` | — | the log flash and the SD card | `flash_erase` erases all Blackbox logs |
| `flash_read`, `flash_write` | `<length> <address>`; `<address> <text>` | raw access to the flash [USE_FLASH_TOOLS] | corrupts logs |
| `msc` | — | a reboot into USB mass storage mode | only if there is flash or an SD card |
| `dfu` | — | a reboot into the DFU bootloader | the flight controller “disappears” until it is flashed or reconnected |
| `bootlog`, `assert` [debug builds: USE_BOOTLOG, USE_ASSERT]; `memory`, `showdebug` (in every build) | — | the boot log, memory, debug | — |
| `cli_delay` | `<ms>`; empty — off | a pause between CLI lines | — |
| `play_sound` | `[No.]` | play a beeper sound | — |

Three traps for people coming from Betaflight. `resource` only shows the pins: functions are moved with `timer_output_mode` or a custom target. `bind_rx` does not bind CRSF/ELRS. `feature gp` will enable `GPS`: the name is matched by the first letters entered, so type names in full. There are 23 names, and the list is `feature list`; in a backup they look like `feature GPS` and `feature -AIRMODE`.

### `diff`, `diff all`, `dump`: what each one prints
A setting in `settings.yaml` belongs to one of the sections: master (`master`, 511 settings in 9.1.0), control profile (91 PID and navigation settings + 25 rates and TPA + 10 EZ Tune = 126), mixer profile (12 plus the `mmix`/`smix` rules), battery profile (28). There are 3, 2 and 3 profiles; an F411 has one mixer profile.

{{diagram:inav-cli-diff-scopes|An ordinary diff prints the master section and one active profile of each kind; all eight profile blocks and the defaults noreboot line come only from diff all. In the module's example that is 38 lines against 69.}}

| Command | What is in the output |
|---|---|
| `diff` or `diff master` | the version, `batch start`, the commands and the `set` lines of the master section, the **active** control, mixer and battery profile, `save`, `batch end` |
| `diff all` | the same, plus `defaults noreboot` at the start, all 3 + 2 + 3 profiles and three lines that restore the profile selection; `batch end` is not printed |
| `diff control_profile` (`mixer_profile`, `battery_profile`) | only the block of the active profile of that kind, without the version, `batch` and `save` |
| `dump`, `dump all` | the same scopes, but with all settings, including those equal to the default; no `defaults noreboot` |

Verified against `printConfig()`: with the `DUMP_MASTER` mask the branch “dump just the current profiles” is executed. Hence the trap: **`diff` looks like a full backup — it has PIDs, the mixer and the battery — but only of the active profiles.** It does not print the other profiles at all. On a VTOL with two mixer profiles that is half the aircraft. `diff` has no `defaults noreboot` either, so pasting it over someone else's config gives a mixture. A backup is `diff all` only.

Three more details from the source. The `rates` scope is in `help` but is not implemented: `diff rates` prints the same as `diff`. There is no `hex` flag. `showdefaults` is supposed to add the default as a `#…` comment before a changed line; for commands (`aux`, `serial`, `feature`) it does, but for `set` lines the 9.1.0 code prints the same current value in the comment (`cli.c`, `dumpPgValue`), so look up the default of a setting with the `get` command.

### How `diff all` is structured
The order of the blocks is fixed: the version line, `batch start`, `defaults noreboot`, then the commands (`timer_output_mode`, `servo`, `safehome`, `fwapproach`, `geozone`, `feature`, `beeper`, `blackbox`, `map`, `serial`, `led`, `aux`, `adjrange`, `rxrange`, `temp_sensor`, `wp`, `osd_layout`, `logic`, `gvar`, `pid`, `osd_custom_elements`), then `# master` with the `set` lines. Then come the profiles: each block is preceded by a selection command with a number from 1 — `control_profile 1`, `2`, `3`; `mixer_profile 1`, `2`; `battery_profile 1`, `2`, `3`. A block is printed even if nothing in it was changed: a single selection line remains. In a mixer block the `set` lines are followed by `mmix reset`, the `mmix` lines, `smix reset`, the `smix` lines. At the end — three lines that restore the original profile selection, and `save`. In total the file has 8 + 3 = 11 profile selection commands.

A profile selection command writes EEPROM by itself when the number changes (`setConfigProfileAndWriteEEPROM`). So a pasted `diff all` is partly saved even before `save`, and `exit` does not undo it — only `defaults` does.

### What a backup does not contain and what it contains unexpectedly
It does not contain: the firmware and its target (only the name in the version line); Blackbox logs on flash or SD; the analog OSD font (it is in the MAX7456 chip) and the goggles fonts (`inav-osd-hd`); the settings of the ESCs, the receiver, the GPS module, the VTX table of the air unit. Separately about the mission: the `wp` lines in a diff are the waypoints currently in the flight controller's memory; when pasted they also go into memory only. For the mission to survive a reboot, `wp save` is needed before `save` (`inav-missions`). Give it only when the paste has no red lines: `wp save` writes everything unsaved to EEPROM and bypasses the protection that makes `save` refuse when the batch has errors.

It does contain the calibrations, because they are ordinary settings of the master section: `acczero_x/y/z` and `accgain_x/y/z` (accelerometer), `magzero_*` and `maggain_*` (compass), `gyro_zero_*`, as well as `vbat_scale`, `current_meter_scale`, `current_meter_offset`. On the same board they come back together with the config. They must not be moved to another board: the aircraft will consider itself calibrated with someone else's zeros — remove these lines and calibrate again (`inav-setup-scratch`). The `stats_total_*` counters are in the diff too.

### Restoring and the red lines
{{diagram:inav-cli-restore-flow|Restoring is a loop of “paste, read the errors, fix the file, reset, paste again”; save is run only after a paste without a single ERROR line, and it all ends with a second diff all and a comparison.}}

The order: (1) take a `diff all`, the first line of the file is the version and the target; (2) edit a copy; (3) flash with Full chip erase (mandatory on a major version change) or run `defaults` on the same firmware; (4) paste the whole file; (5) read the output; (6) `save`; (7) take a `diff all` again and compare it with the file; (8) `status`, the outputs on the Outputs tab without props.

`batch start` turns on the error counter. With an active batch a `save` with errors does not write but prints `### ERROR: N ERRORS WERE DETECTED - Please review and fix before continuing!` and `PLEASE FIX ERRORS THEN 'SAVE'`, after which the batch is reset — a second `save` will write whatever is there. Do not do that: every rejected line is a setting left at its default.

| Line | Cause | What to do |
|---|---|---|
| `### ERROR: Invalid name` | the setting or feature name does not exist in this firmware: renamed or removed | find it in the migration table; rename or delete the line |
| `### ERROR: Invalid value. Allowed range: …` / `Allowed values: …` | the value is outside the new range or was removed from the list | choose the new value deliberately |
| `### ERROR: Unknown command, try 'help'` | the command was renamed (`profile`) or is not built into this target | replace it; for a feature that was cut out — delete the block |
| `### ERROR: Parse error`, `… must be between …` | the format or a limit of the command changed | check the format with `help` |

After fixing the file — `defaults`, and paste again from the start: that way no traces of the failed attempt are left in the config. The 9.0 release notes advise pasting a `diff all` with several profiles in two parts — up to the end of `# master` with `save`, then the profiles (`inav-intro`).

### `status`, `tasks`
`status` prints: the version line; uptime; the time; the voltage with the cell count and the battery state; the core clock and the detected sensors; `Sensor status` for eight sensors; the SD state; the stack and the configuration size (`config size` / `max available config`); I2C errors; ADC channels; `System load`, `cycle time`, `PID rate`, `RX rate`; then `Arming disabled flags:` with the names; the lines `OSD:` (type and grid), `VTX:`, a `GPS:` block for u-blox and, on a timer error, `PWM output init error`. The names go in bit order. A standard build does not print the hexadecimal mask (only a build with `CLI_MINIMAL_VERBOSITY`); the whole mask comes over MSP in `MSP2_INAV_STATUS` as the 32-bit `armingFlags`.

There are 24 flags, bits 6–30 without bit 17 (the name table has `PLACEHOLDER` in its place). The set is the same in 8.0.1.

| Bit | Name in `status` | What blocks | What to do |
|---|---|---|---|
| 6 | `GEOZONE` | `feature GEOZONE` is enabled, and a geozone forbids takeoff | leave the no-fly zone, check the zones |
| 7 | `FS` | the aircraft landed or was disarmed by failsafe, and the link is not yet considered stable | restore the link, wait, turn the arm switch off |
| 8 | `ANGLE` | tilt is greater than `small_angle` (25°) | level the aircraft; check the board alignment and the calibration |
| 9 | `CAL` | sensor calibration is in progress | wait without moving it |
| 10 | `OVRLD` | CPU overload | reduce the load: see `tasks` |
| 11 | `NAV` | no fix with navigation modes configured, a navigation mode is active, the first mission waypoint is too far away or a JUMP error; an explanation line follows below | wait for the fix, turn the mode off, fix the mission |
| 12 | `COMPASS` | a compass is present but not calibrated | calibrate |
| 13 | `ACC` | the accelerometer is needed but not calibrated | the 6-position calibration |
| 14 | `ARMSW` | the arm switch is on while another block is present | turn the switch off, remove the cause |
| 15 | `HWFAIL` | a sensor is selected but not found or returns garbage | `Sensor status`, wiring, `*_hardware` |
| 16 | `BOXFS` | the FAILSAFE mode is activated with a switch | turn it off |
| 18 | `RX` | no receiver data | turn the radio on, check the port and the protocol |
| 19 | `THR` | throttle is not at minimum | lower the stick, check `rxrange` and `min_check` |
| 20 | `CLI` | the CLI is open | `exit` or `save` |
| 21 | `CMS` | the CMS menu is open | leave the menu |
| 22 | `OSD` | the OSD menu is open | leave the menu |
| 23 | `ROLL/PITCH` | fixed-wing autolaunch is enabled, and the roll/pitch sticks are deflected | release the sticks |
| 24 | `AUTOTRIM` | the servo AUTOTRIM mode is active | turn the mode off |
| 25 | `OOM` | out of dynamic memory | simplify the configuration, `memory` |
| 26 | `SETTINGFAIL` | a setting is out of the allowed range; `### ERROR: Invalid setting: <name>` follows below | correct the named setting |
| 27 | `PWMOUT` | an output assignment error | `timer_output_mode`, `inav-mixer-vtol` |
| 28 | `NOPREARM` | the PREARM mode is assigned but not activated or has expired | activate PREARM before ARM |
| 29 | `DSHOTBEEPER` | the motors have just beeped over DShot | wait |
| 30 | `LANDED` | a landing was registered | turn the arm switch off |

`tasks` prints for every task its rate, the maximum and average execution time in microseconds and the load. The load is computed as (time × rate + 5000) / 1000 in tenths of a percent: 120 µs at 2000 Hz gives 24.5 %. The line `Total (excluding SERIAL)` is the sum without the SERIAL task.

### Configurator 9.1: auto-backup and migration
From the Configurator 9.1.0 source (`js/backup_restore.js`, `js/migration/`, `tabs/firmware_flasher*.js`):

- Before flashing over serial the Configurator enters the CLI, runs `diff all` and saves the file `UPDATE_inav_backup_<version>_<target>_<date>_<time>.txt`; the 10 latest auto-backups are kept. If the board is already in DFU or “No reboot sequence” is enabled, there will be no backup — the CLI is not available.
- The folder is `inav-backups` in the application data directory (`app.getPath('userData')`); the Open Backups button on the Firmware Flasher tab opens it (Open Backups Folder in the documentation). The document `Backup and Restore.md` calls the subfolder `backups` — trust the button.
- The file starts with a header: for a pre-flash auto-backup — `# INAV Auto-Backup (pre-flash)`, for a backup made with the Backup Config button — `# INAV Backup`; the rest is the same: `# Version: 8.0.1`, `# Board:`, `# Date:`, `# Craft:`. **The Configurator takes the version for migration only from the `# Version:` line.** A `diff all` saved by hand from the CLI has no such line — migration will not be applied to it until you add the line yourself.
- A restore is offered after flashing with Full chip erase: at the same major version — at once, on a major version change — after the migration preview window. Without Full chip erase, when flashing from a local file and when downgrading the major version the file is saved, but a restore is not offered.
- A restore sends the lines one at a time, skips comments, `save` and `exit`, and counts a reply with `### ERROR:`, `Invalid` or `Unknown command` as an error. Without errors — `save`. With errors — a “save anyway / abort” dialog; whatever you choose, take a `diff all` and compare.

What exactly `8_to_9.json` does: it replaces the word `controlrate_profile` with `use_control_profile`, renames `mixer_pid_profile_linking` → `mixer_control_profile_linking` and `osd_pan_servo_pwm2centideg` → `osd_pan_servo_range_decadegrees`, and shows two warnings (the defaults of the altitude estimator weights; `ahrs_acc_ignore_rate`). Its list of removed settings is empty: `reboot_character`, removed in 9.0, will remain a red line. The second warning is not confirmed by the source: `ahrs_acc_ignore_rate` is 15 in both 8.0.1 and 9.1.0.

### Migration 7 → 8 → 9: the lines for the CLI
The full 8.0 → 9.1 table with the defaults is in `inav-intro`; here is what breaks a file paste. The 7 → 8 column is taken from the 8.0.0 release notes and `7_to_8.json` of Configurator 9.1.0: a 7.x tree was not available, and only the absence of the old names and the presence of the new ones was checked against the 8.0.1 source.

| Was | Now | Transition | What to do with the line |
|---|---|---|---|
| the `profile` command | `control_profile` | 7 → 8 | rename |
| `gps_provider = UBLOX7` | `UBLOX` | 7 → 8 | replace the value |
| `nav_auto_climb_rate`, `nav_manual_climb_rate` | `nav_mc_auto_climb_rate` and `nav_fw_auto_climb_rate`; `nav_mc_manual_climb_rate` and `nav_fw_manual_climb_rate` | 7 → 8 | write the value to the setting of your platform |
| `nav_fw_wp_tracking_accuracy` | the same name, now the distance to the track line in meters | 7 → 8 | recalculate by hand |
| `osd_custom_elements` types 4, 5, 6, 7 | 9, 16, 7, 10 | 7 → 8 | renumber |
| `max_throttle`, `pidsum_limit`, `pidsum_limit_yaw`, `control_deadband`, `cpu_underclock`, `disarm_kill_switch`, `dji_workarounds`, `fw_iterm_limit_stick_position`, `gyro_anti_aliasing_lpf_type`, `gyro_hardware_lpf`, `gyro_main_lpf_type`, `gyro_use_dyn_lpf`, `inav_use_gps_no_baro`, `inav_use_gps_velned`, `ledstrip_visual_beeper`, `osd_stats_min_voltage_unit` | — | 7 → 8 | delete |
| `dynamic_gyro_notch_mode = 3D_*` | the values were removed | 7 → 8 | choose from the remaining ones |
| `controlrate_profile` | `use_control_profile` | 8 → 9 | rename |
| `mixer_pid_profile_linking` | `mixer_control_profile_linking` | 8 → 9 | rename |
| `osd_pan_servo_pwm2centideg` | `osd_pan_servo_range_decadegrees` | 8 → 9 | rename, the number is the same |
| `reboot_character` | — | 8 → 9 | delete |
| `inav_w_z_baro_v`, `inav_w_z_gps_p`, `inav_w_z_gps_v` with your own values | the names are the same, the defaults are 0.35 | 8 → 9 | review: the estimator was retuned |
| `osd_snr_alarm` > 30 | the limit is 30 | 8 → 9 | reduce |

The CLI command is called `control_profile` in both 8.0.1 and 9.1.0; `profile` gives `Unknown command`. The example in `docs/Cli.md` 9.1.0 says `control_profile 0` — the numbers start at 1, and zero is silently ignored. The 8.0 and 9.0 release notes mention a third-party online diff converter (mrd-rc.com); I have not checked how it works.

And the main thing that is in no file: a diff stores only the differences from the **old** defaults. Everything you did not change gets the new defaults after the migration (`gps_ublox_nav_hz` 10 → 8, `nav_fw_pos_z_ff` 10 → 30 and others — `inav-intro`).

### Place in the system
- **Receives:** the finished configuration of the aircraft — ports, modes, failsafe and calibrations from `inav-setup-scratch`, the mixer profiles from `inav-mixer-vtol`, the OSD layouts from `inav-osd-hd`, the `logic` rules from `inav-ipf`; the list of renames from `inav-intro`.
- **Provides:** a verified `diff all` file with the version — the basis for restoring, for moving to new firmware and for keeping in git (`eng-ci-configs`); the decoding of the arming flags — to the preflight check; scripting techniques — to the client from `bf-cli-automation`.
- **If you get it wrong here:** a backup from `diff` instead of `diff all` — after a restore the VTOL has no second mixer profile (`inav-mixer-vtol`); a missed red line — the profile linking is off, and the PIDs do not follow the mode; someone else's `acczero_*` — the horizon and navigation are wrong (`inav-gps`).

## practice
No hardware or simulator is needed: everything is solved from the tables of this module. The fragment below is a **teaching example assembled by hand** following the format of `printConfig()` and `settings.yaml` 8.0.1 (all the setting names were checked with a script against the 8.0.1 tree and sit in their own sections); it is not the output of a real aircraft. The aircraft is the “4+1” VTOL from `inav-mixer-vtol`: three control profiles, two mixer profiles, profiles 1/1/1 active.

### Step 1. Mark up the 69 lines for 9.1
The file has 91 lines: 69 command lines and 22 comments. For each command line decide: paste as is, rename (to what), delete or review.

```text
# version
# INAV/MATEKH743 8.0.1 <build date and time> (<git revision>)
# start the command batch
batch start
# reset configuration to default settings
defaults noreboot
# features
feature GPS
feature PWM_OUTPUT_ENABLE
# Ports
serial 1 2 115200 115200 0 115200
# Modes [aux]
aux 0 0 0 1700 2100
aux 1 62 2 1700 2100
aux 2 63 2 1300 1700
# master
set gps_ublox_use_galileo = ON
set reboot_character = 114
set inav_w_z_baro_v = 0.200
set osd_pan_servo_pwm2centideg = 18
set failsafe_procedure = RTH
set nav_rth_altitude = 5000
# control_profile
control_profile 1
set fw_p_pitch = 12
set fw_i_pitch = 9
set fw_ff_pitch = 70
set roll_rate = 30
# control_profile
control_profile 2
set mc_p_pitch = 44
set mc_i_pitch = 85
set mc_d_pitch = 28
set tpa_rate = 20
# control_profile
control_profile 3
set mc_p_pitch = 36
set rc_expo = 60
# mixer_profile
mixer_profile 1
set platform_type = AIRPLANE
set mixer_pid_profile_linking = ON
set mixer_automated_switch = ON
# Mixer: motor mixer
mmix reset
mmix 0 -1.000 0.000 0.000 0.000
mmix 1 -1.000 0.000 0.000 0.000
mmix 2 -1.000 0.000 0.000 0.000
mmix 3 -1.000 0.000 0.000 0.000
mmix 4 1.000 0.000 0.000 0.000
# Mixer: servo mixer
smix reset
smix 0 1 1 100 0 -1
smix 1 2 0 100 0 -1
smix 2 3 0 100 0 -1
smix 3 4 2 100 0 -1
# mixer_profile
mixer_profile 2
set mixer_pid_profile_linking = ON
set mixer_automated_switch = ON
set mixer_switch_trans_timer = 40
# Mixer: motor mixer
mmix reset
mmix 0 1.000 -1.000 1.000 -1.000
mmix 1 1.000 -1.000 -1.000 1.000
mmix 2 1.000 1.000 1.000 1.000
mmix 3 1.000 1.000 -1.000 -1.000
mmix 4 -1.300 0.000 0.000 0.000
# Mixer: servo mixer
smix reset
smix 0 1 1 50 0 -1
smix 1 2 0 50 0 -1
smix 2 3 0 50 0 -1
# battery_profile
battery_profile 1
set bat_cells = 4
set battery_capacity = 5000
# battery_profile
battery_profile 2
set bat_cells = 6
set battery_capacity = 8000
set controlrate_profile = 3
set nav_mc_hover_thr = 1420
# battery_profile
battery_profile 3
# restore original profile selection
control_profile 1
mixer_profile 1
battery_profile 1
# save configuration
save
```

Check your markup against the converter. Its rules are the three renames from `8_to_9.json`, one deletion and three “review” settings from the migration table. I ran it on this file:

```python
#!/usr/bin/env python3
"""INAV diff all 8.0.x -> 9.1: rename / drop / flag. Usage: convert_8_to_9.py old.txt > new.txt"""
import sys

RENAME = {  # settings.yaml 8.0.1 vs 9.1.0; the same three as Configurator js/migration/8_to_9.json
    "controlrate_profile": "use_control_profile",
    "mixer_pid_profile_linking": "mixer_control_profile_linking",
    "osd_pan_servo_pwm2centideg": "osd_pan_servo_range_decadegrees",
}
DROP = {"reboot_character"}                       # removed in 9.0, not in 8_to_9.json
REVIEW = {"inav_w_z_baro_v", "inav_w_z_gps_p", "inav_w_z_gps_v"}  # defaults changed, estimator retuned

out, log = [], []
for n, raw in enumerate(open(sys.argv[1], encoding="utf-8"), 1):
    line = raw.rstrip("\n")
    p = line.split()
    if len(p) >= 4 and p[0] == "set" and p[2] == "=":
        if p[1] in DROP:
            log.append(f"{n}: DROP   {line}")
            continue
        if p[1] in RENAME:
            log.append(f"{n}: RENAME {p[1]} -> {RENAME[p[1]]}")
            p[1] = RENAME[p[1]]
            line = " ".join(p)
        elif p[1] in REVIEW:
            log.append(f"{n}: REVIEW {line}")
    out.append(line)
print("\n".join(out))
cmds = [l for l in out if l.strip() and not l.startswith("#")]
print("\n".join(log), file=sys.stderr)
print(f"command lines out: {len(cmds)}, renamed: {sum('RENAME' in l for l in log)}, "
      f"dropped: {sum('DROP' in l for l in log)}, review: {sum('REVIEW' in l for l in log)}", file=sys.stderr)
```

The stderr output (the numbers are lines of the file including comments):

```text
18: DROP   set reboot_character = 114
19: REVIEW set inav_w_z_baro_v = 0.200
20: RENAME osd_pan_servo_pwm2centideg -> osd_pan_servo_range_decadegrees
42: RENAME mixer_pid_profile_linking -> mixer_control_profile_linking
59: RENAME mixer_pid_profile_linking -> mixer_control_profile_linking
82: RENAME controlrate_profile -> use_control_profile
command lines out: 68, renamed: 4, dropped: 1, review: 1
```

The result: 63 lines as is, 4 to rename, 1 to delete, 1 to review. All the names of the resulting file were checked with the same script against `settings.yaml` 9.1.0. The converter knows nothing about the 7 → 8 migration and does not replace reading the CLI output: it edits only `set` lines.

Add to your markup what is not in the file. `set gps_ublox_use_galileo = ON` equals the default in 9.1 — the line is harmless but redundant. The file has no `gps_ublox_nav_hz`, `gps_ublox_use_beidou` or `nav_fw_pos_z_ff` lines: in 8.0.1 they were at the defaults 10, OFF and 10, and in 9.1 they become 8, ON and 30. If you need the old behavior — add the lines yourself.

### Step 2. What `diff` would have lost
From the same file count how many command lines a `diff` without `all` would print with profiles 1/1/1 active and which lines of the `diff all` it lacks. Count in blocks: the header and commands, `# master`, each profile, the selection restore, `save`.

The breakdown: header and commands — 8 lines (`batch start`, `defaults noreboot`, 2 × `feature`, `serial`, 3 × `aux`), `master` — 6, control profiles — 5, 5 and 3, mixer profiles — 15 and 14, battery profiles — 3, 5 and 1, the restore — 3, `save` — 1; the sum is 69. `diff` prints everything except `defaults noreboot`, the inactive profiles and the restore: 7 + 6 + 5 + 15 + 3 + 1 = 37, plus `batch end` after `save` — 38. 32 lines are lost: 23 lines with settings (4 + 2 + 13 + 4), 5 profile selection commands, 3 restore lines and `defaults noreboot`. In terms of meaning — both multirotor PID sets, the whole hover mixer and the 6S battery profile: after such a “restore” the VTOL cannot hover.

### Step 3. The restore order and three errors
Put the steps in order:

- A. `save`.
- B. Paste the whole file into the CLI.
- C. Flash 9.1 with Full chip erase, props off.
- D. Take a `diff all` on 8.0.1, check the version line, save the file.
- E. Take a `diff all` again and compare it with the file; then `status` and the outputs.
- F. In a copy of the file rename and delete lines using the table.
- G. Read the output: not a single `### ERROR` line; otherwise — fix the file, `defaults`, paste again.

Then find three errors in this procedure: “(1) On 8.0.1 ran `diff` and saved the output. (2) Flashed 9.1 without Full chip erase so that the settings would stay. (3) Pasted the file, saw two `### ERROR: Invalid name` lines, typed `save` twice — the second time it saved. (4) Took a `diff all` and saved it as the new backup”.

### Step 4. A flag line
Below are lines composed following the format of `cliStatus()` (not the output of an aircraft). Name each cause of the block, the bits, the decimal and hexadecimal `armingFlags` mask, and say which flags will clear by themselves and which require work.

```text
Arming disabled flags: ANGLE NAV COMPASS ACC RX CLI
  WAITING FOR GPS FIX
```

### Moving to real hardware
The props stay off the whole time. On your board: `version`, then `diff all` → a file; count the profile blocks (there should be 3 + 2 + 3, on an F411 — 3 + 1 + 3). Prove the backup by doing: `defaults`, paste the file, `save`, `diff all` again — the files must match line by line, except `stats_*`. When moving to 9.1 run the converter or the Configurator migration, paste, get an output without `### ERROR`, compare `diff all`, check the outputs on the Outputs tab and the flags in `status`. The criterion on hardware: after leaving the CLI `status` has no flags other than those expected on the bench (`NAV` without a fix indoors, `RX` with the radio off).

Self-check: the lab is done when:
- step 1: you got 63 / 4 / 1 / 1 (as is / rename / delete / review), all four new names are given, the resulting file has 68 command lines, and the three “silent” defaults are listed (8, ON, 30);
- step 2: `diff all` — 69 lines, `diff` — 38, 32 lost, 23 of them with settings;
- step 3: the order is D → F → C → B → G → A → E, the errors in items (1), (2) and (3) are found;
- step 4: six flags, bits 8, 11, 12, 13, 18, 20, the mask 1325312 = 0x143900.

**Reference for the self-check.** Step 1: the renames are `osd_pan_servo_range_decadegrees`, `mixer_control_profile_linking` twice, `use_control_profile`; delete `reboot_character`; review `inav_w_z_baro_v`. Step 3: the errors are `diff` instead of `diff all`; no Full chip erase on a major version change; saving over errors (two settings were left at their defaults). Step 4: `CLI` clears after `exit`, `RX` — when you turn the radio on; `ANGLE` — level the aircraft (if it stands level, the cause is the board alignment or the calibration); `ACC` and `COMPASS` — calibrations, typical after a move to another board without the `acczero_*` and `magzero_*` lines; `NAV` with the explanation `WAITING FOR GPS FIX` — wait for a fix under an open sky. Typical wrong results: (1) in step 2 you got “all profiles are lost, `diff` = 14 lines” — you assumed that `diff` prints only `master`; it does print the active profiles. (2) 31 lost instead of 32 — `defaults noreboot` was forgotten, or `diff` came out as 37 — `batch end` was forgotten. (3) In step 1 three renames instead of four — the second mixer profile was missed: the setting is per profile and repeats in every block. (4) The mask 0x142900 or another — a bit is mixed up: `ACC` is 13, `COMPASS` is 12, there is no bit 17, `RX` is 18.

## diagnostics
- **Symptom:** after a restore the VTOL has no hover mode, the second mixer profile is empty
  - Possible cause: the backup was taken with `diff`, not `diff all` — it has only the active profiles.
  - What to do: look for an old `diff all` or a Configurator auto-backup (Firmware Flasher → Open Backups); otherwise build the profile again per `inav-mixer-vtol`.
- **Symptom:** red `### ERROR: Invalid name` lines on paste
  - Possible cause: the setting was renamed or removed in the new version; the file is from a different major version.
  - What to do: write the lines down, fix a copy of the file using the migration table, `defaults`, paste again. Yes, the 8 → 9 transition needs Full chip erase; red lines are not “fixed” by a repeated `save`.
- **Symptom:** `save` answers `N ERRORS WERE DETECTED` and does not reboot
  - Possible cause: the file starts with `batch start`, and there were errors during the paste.
  - What to do: scroll the output to the first `### ERROR`, fix the file; do not type `save` a second time.
- **Symptom:** `### ERROR: Unknown command, try 'help'` on the line `profile 1`
  - Possible cause: the file is from INAV 7 or the guide is old: since 8.0 the command is called `control_profile`.
  - What to do: replace `profile` with `control_profile` (numbers from 1).
- **Symptom:** Configurator 9.1 restored the file without the migration window, and errors remained in the CLI
  - Possible cause: the file has no `# Version: X.Y.Z` line (the file was saved by hand from the CLI), and the version was not recognized.
  - What to do: add the line `# Version: 8.0.1` at the start of the file or fix the names using the table.
- **Symptom:** after moving the config to another board the horizon is tilted, the compass is wrong, and there are no `ACC` and `COMPASS` flags
  - Possible cause: someone else's `acczero_*`, `accgain_*`, `magzero_*`, `maggain_*` were moved together with the diff.
  - What to do: calibrate the accelerometer and the compass again; in a file for another board delete these lines.
- **Symptom:** you pasted a file, changed your mind, typed `exit` — and some settings changed
  - Possible cause: the commands `control_profile`, `mixer_profile`, `battery_profile` write EEPROM themselves when the number changes.
  - What to do: `defaults` and a restore from your own backup.
- **Symptom:** after the 8 → 9 upgrade the aircraft behaves differently although there were no errors on paste
  - Possible cause: settings that were not in the diff got the new defaults (GPS, the altitude estimator, `nav_fw_pos_z_ff`).
  - What to do: check against the table in `inav-intro`, add the values you need to the file explicitly.
- **Symptom:** it does not arm, and the reason is unclear
  - Possible cause: one of the 24 flags; `ARMSW` appears on top of any other cause.
  - What to do: `status`, read the flags from left to right using the table, first remove the cause, then flip the switch; remember that `CLI` is always in the output.

## checklist
- The backup was taken with `diff all`, not `diff`; the file has 3 + 2 + 3 profile blocks
- The first line of the file is the version and the target; the file is named with the version and the date
- The backup was verified by a restore and a second `diff all`
- Before a major version change the file was fixed using the migration table
- Flashing with Full chip erase, props off
- A paste without a single `### ERROR` line, and only then `save`
- For another board the calibration lines are deleted
- After a restore: `status`, the outputs on Outputs, the calibrations, the new defaults

## references
- INAV 9.1.0 cli.c (the command table, printConfig, batch, save, status, tasks, feature) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/cli.c | primary | A
- INAV 9.1.0 settings.yaml (setting sections, names, defaults) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/settings.yaml | primary | A
- INAV 9.1.0 runtime_config.h (the arming-disabled flags) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/runtime_config.h | primary | A
- INAV 9.1.0 fc_core.c (the conditions that set the flags) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/fc_core.c | primary | A
- INAV 9.1.0 config.c (the EEPROM write on a profile change) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/config.c | primary | A
- INAV 9.1.0 docs/Cli.md | https://github.com/iNavFlight/inav/blob/9.1.0/docs/Cli.md | primary | A
- INAV 9.1.0 docs/Backup and Restore.md | https://github.com/iNavFlight/inav/blob/9.1.0/docs/Backup%20and%20Restore.md | primary | A
- INAV 8.0.1 cli.c (the commands and diff scopes for comparison) | https://github.com/iNavFlight/inav/blob/8.0.1/src/main/fc/cli.c | primary | A
- INAV Configurator 9.1.0 backup_restore.js (auto-backup, restore) | https://github.com/iNavFlight/inav-configurator/blob/9.1.0/js/backup_restore.js | primary | A
- INAV Configurator 9.1.0 migration/8_to_9.json | https://github.com/iNavFlight/inav-configurator/blob/9.1.0/js/migration/8_to_9.json | primary | A
- INAV Configurator 9.1.0 migration/7_to_8.json | https://github.com/iNavFlight/inav-configurator/blob/9.1.0/js/migration/7_to_8.json | primary | A
- INAV 9.0.0 release notes (the upgrade procedure from 8.0, Full chip erase) | https://github.com/iNavFlight/inav/releases/tag/9.0.0 | primary | A
- INAV 8.0.0 release notes (the 7 → 8 renames and removals) | https://github.com/iNavFlight/inav/releases/tag/8.0.0 | primary | A

## notes
The course audit (`docs/reviews/inav-coverage-audit.md`) claimed that `diff` without arguments prints only the `master` section. According to `printConfig()` in 8.0.1 and 9.1.0 that is not so: the active profiles are printed as well. The module follows the source. The CLI output in the module is composed from the format strings in the source; I did not capture it on a board or in SITL.
