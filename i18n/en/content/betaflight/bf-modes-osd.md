---
id: bf-modes-osd
title: "Modes and OSD"
level: L1
readingTime: 35 min
firmware: Betaflight 2025.12 (checked against 2025.12.5); the OSD bits are also checked against 4.5.3
status: published
added: 2026-11-07
tags:
  - modes
  - OSD
  - AUX
related:
  - link-protocols
  - bf-failsafe
  - bf-adjustments
  - bf-led-buzzer
  - bf-hd-osd-video
next:
  - bf-failsafe
source: content/betaflight/bf-modes-osd.md
source_hash: cd31db6b65a3
---

## summary
Modes are what you put on switches: arming, self-leveling, the beeper, the failsafe test, flip over after crash. The OSD is what you see in the goggles: voltage, time, link, warnings. This module explains how AUX channel ranges work, which modes are mandatory and which are dangerous, and how to build an OSD that warns you in advance instead of reporting what has already happened. It adds a working switch layout from several 7–10" drones, made so that the hands remember it, and the “machine” level of the OSD: which bits make up `osd_*_pos`, how the three OSD profiles work and how to change them from a switch, the bit numbers in `osd_warn_bitmask` and `osd_stat_bitmask` for 4.5 and 2025.12, and how `craft_name` differs from `pilot_name`. The lab is reading `aux` lines, thresholds and stick commands, then encoding and decoding positions and masks with a Python model of the `osd.h` macros (the run is in the text).

## theory
### How the Modes tab works
Every mode is bound to an AUX channel and a range of values (1000–2000 µs). When the switch is inside that range, the mode is active. Several modes can share one channel in different ranges (a three-position switch). The check is in the tab itself: move the switch and watch which mode is highlighted.

### Mandatory
- **ARM** — always a separate two-position switch, with no neighbors on the channel. On the bench — props off.
- **ANGLE** — self-leveling. Even if you fly ACRO, keep it on a switch: it saves you when you lose orientation (in Stage 2 failsafe ANGLE is turned on automatically, no switch is needed for that).
- **BEEPER** — to find the drone in the grass.
- **FAILSAFE** — a failsafe test from a switch (see the failsafe module), the STAGE1 mode.

### Useful
- **AIR MODE** — the PID controller works at zero throttle; for ACRO it is almost always enabled permanently (without a switch).
- **PREARM** — a second switch without which arming is impossible. A must for heavy drones.
- **FLIP OVER AFTER CRASH** — to turn over from the ground after a crash. Only when the drone is lying still and the props touch nothing.
- **HORIZON** — self-leveling that still allows flips; **ACRO TRAINER** — an angle limit in ACRO for training.
- **GPS RESCUE** — return to home by GPS (a separate switch and a separate setup).
- **BLACKBOX** — log only on a switch, if the flash is small.
- **OSD DISABLE**, **VTX PIT MODE**, **PARALYZE** — situational.

### An example layout
A layout from several drones of one team, the same on all of them so that there is nothing to think about in the air: ARM on AUX1, ANGLE on AUX3, FAILSAFE (STAGE1) on AUX6, BEEPER on AUX7, PREARM on AUX8. The rule: the same switches on every drone you fly.

{{lesson:bf-led-buzzer|What exactly BEEPER turns on, how to make it beep by itself on link loss through `rxfail`, and in what order to search for a crashed aircraft.}}

### OSD
The elements are selected in the OSD tab, and the position is stored in the `osd_*_pos` parameters. The minimum set for safety: voltage (average per cell — `osd_avg_cell_voltage_pos`), a timer, link quality / RSSI, the flight mode, warnings, `craft_name`. For long range — mAh drawn, GPS satellites, the direction and distance to home.

The warnings (`osd_warn_bitmask`): low voltage, failsafe, RXLOSS, arming disable flags. The voltage thresholds are set so that the warning arrives with a margin for the return, not in the last few percent; the numbers by chemistry and class and the check after landing are in `f-power` (“Voltage thresholds”).

The analog OSD (the MAX7456 chip) and the digital one (MSP DisplayPort for Walksnail/HDZero/DJI) are set up in the same tab, but the set of elements and the resolution differ.

### The `aux` command and mode logic
`aux <index> <mode id> <aux channel> <start> <end> <logic>`: the rule index, the mode id — the `permanentId` from `msp/msp_box.c` (ARM = 0, ANGLE = 1, HORIZON = 2, FAILSAFE = 27, PREARM = 36), not the number from the enum in `fc/rc_modes.h`, the AUX channel (0 = AUX1), a range of 900–2100 in steps of 25, logic 0 = OR, 1 = AND (the mode is active only if **all** the AND rules of that mode are met **at the same time** — this is how “ARM only if PREARM on the same channel” or two-switch combinations are made). The ranges for a three-position switch: 900–1300, 1300–1700, 1700–2100 — with a margin, so that jitter does not toggle modes at a boundary. A radio switch arrives over CRSF as ≈988 / 1500 / 2012 µs (±100 % of travel; the conversion in `crsfReadRawRC()` in `rx/crsf.c`: 172 → 988, 992 → 1500, 1811 → 2012), so 200–312 µs remain to the range boundary. `adjrange` is the same for in-flight adjustments (PID, rates, profile selection) from a switch or a pot; of the profiles only the rate, OSD and LED profiles are switched this way, and there is no adjustment for the PID profile (neither in 4.5 nor in 2025.12). The slots, the functions and the VTX on a switch (`vtx`) are in the bf-adjustments module.

{{diagram:bf-aux-ranges|The team layout on the AUX axis: the switch positions ≈988 / 1500 / 2012 µs lie 200–312 µs from the range boundaries, so jitter does not toggle a mode.}}

All the mode `permanentId` values of 2025.12 (`boxes[]` in `msp/msp_box.c`; the numbers 9, 10, 14, 16, 18, 21, 22, 38 belong to removed modes and are not used). The list differs from 4.5 in four lines: id 3 ALTHOLD and id 11 POS HOLD (in 4.5 these numbers are empty), id 55 CHIRP (absent in 4.5) and the name of id 29 — in 4.5 “3D DISABLE / SWITCH”. The Modes tab shows only the modes that are in the build and make sense for the configuration (for example, SERVO1–3 — only with servos):

| id | Mode | id | Mode |
|---|---|---|---|
| 0 | ARM | 32–34 | CAMERA CONTROL 1–3 (RunCam, bf-features-tour) |
| 1 | ANGLE | 35 | FLIP OVER AFTER CRASH (turtle) |
| 2 | HORIZON | 36 | PREARM |
| 3 | ALTHOLD (altitude hold, from 2025.12) | 55 | CHIRP (from 2025.12, ctl-sysid) |
| 11 | POS HOLD (GPS position hold, from 2025.12) | | |
| 4 | ANTI GRAVITY | 37 | GPS BEEP SATELLITE COUNT |
| 5 | MAG | 39 | VTX PIT MODE (link-vtx) |
| 6 / 7 | HEADFREE / HEADADJ | 40–43 | USER1–4 (PINIO: VTX/camera power) |
| 8 | CAMSTAB (servo gimbal, bf-servos-pwm) | 44 | PID AUDIO |
| 12 | PASSTHRU | 45 | PARALYZE |
| 13 | BEEPER | 46 | GPS RESCUE |
| 15 | LEDLOW (turn the LED strip off) | 47 | ACRO TRAINER |
| 17 | CALIB | 48 | VTX CONTROL DISABLE |
| 19 | OSD DISABLE | 49 | LAUNCH CONTROL |
| 20 | TELEMETRY | 50 | MSP OVERRIDE |
| 23–25 | SERVO1–3 | 51 | STICK COMMANDS DISABLE |
| 26 | BLACKBOX | 52 | BEEPER MUTE |
| 27 | FAILSAFE | 53 | READY |
| 28 | AIR MODE | 54 | LAP TIMER RESET |
| 29 | 3D DISABLE | 30 / 31 | FPV ANGLE MIX / BLACKBOX ERASE |

Turtle, launch control, 3D, acro trainer and the Angle/Horizon settings are covered in bf-features-tour, and the reasons for “will not arm” — in bf-arming-safety.

### Stick commands (while disarmed)
A second “keyboard” without a laptop: stick positions while disarmed (`processRcStickPositions()` in `fc/rc_controls.c`). LO — below `min_check` (1050), HI — above `max_check` (1900); throttle and yaw are the left stick in Mode 2. They do not work while armed, with the STICK COMMANDS DISABLE mode active, or while the arming disable flag `RUNAWAY` or `CRASH` is set.

| Action | Throttle | Yaw | Pitch | Roll |
|---|---|---|---|---|
| **Save the config** (including in-flight adjustments) | LO | LO (left) | LO (back) | HI (right) |
| Gyro calibration (+ reset of GPS home and the baro zero) | LO | LO | LO | center |
| PID profile 1 / 2 / 3 | LO | LO | center / HI / center | LO / center / HI |
| Accelerometer calibration | HI | LO | LO | center |
| Compass calibration | HI | HI | LO | center |
| Rate profile 1 / 2 / 3 / 4 (in ACRO) | HI | center | HI / LO / center / center | center / center / HI / LO |
| Accelerometer trims (in ANGLE/HORIZON), one step per command | HI | center | HI/LO — pitch | HI/LO — roll |
| VTX: band +/− | HI | LO | center | HI / LO |
| VTX: channel +/− | HI | HI | center | HI / LO |
| OSD menu (CMS) | **middle** | LO | HI | any |

The confirmation is beeps (a save — one beep, a PID profile — as many beeps as its number). The trims save themselves when the throttle leaves HI. A PID or rate profile change made with the sticks is **not saved** until the “Save” command is given — after the battery is reconnected the old profile returns. The trap: pitch slightly above 1050 turns “Save” into “PID profile 3”.

### OSD: set up for meaning, not for looks
- **OSD profiles** (`osd_profile`, up to 3) — on a switch: a “minimum” for racing, a “full” one for long range, an “empty” one for recording.
- **Warnings** (`osd_warn_bitmask`): ARMING_DISABLE, BATTERY_WARNING/CRITICAL, FAIL_SAFE, LINK_QUALITY, RSSI, CORE_TEMP, GPS_RESCUE_*, OVER_CAP — enable all except the noisy ones; `osd_cap_alarm`, `osd_alt_alarm`, `osd_rssi_alarm`, `osd_link_quality_alarm` are the thresholds. The defaults (`pgResetFn_osdConfig()` in `osd/osd.c`, the same in 4.5 and 2025.12): `osd_rssi_alarm` 20 %, `osd_link_quality_alarm` 80 %, `osd_cap_alarm` 2200 mAh, `osd_alt_alarm` 100 (m, or feet with `osd_units = IMPERIAL`); for CRSF/ELRS also `osd_rssi_dbm_alarm` −60 dBm and `osd_rsnr_alarm` 4 dB; `osd_core_temp_alarm` 70 °C (the MCU temperature: lockups have been reported above 80 °C); `osd_esc_temp_alarm`, `osd_esc_rpm_alarm`, `osd_esc_current_alarm` and `osd_distance_alarm` are off by default. A threshold works only if the warning itself is enabled: by default all warnings are enabled **except** RSSI, LINK_QUALITY, RSSI_DBM, RSNR and OVER_CAP — these have to be enabled in `osd_warn_bitmask` (the OSD tab → Warnings). Do not carry the numeric mask from 4.5 over to 2025.12: the RC_SMOOTHING warning (bit 8) was removed, bits 9–18 moved down by one, and bit 18 is the new POSHOLD_FAILED. `osd_cap_alarm` is exactly mAh, not a percentage: for a different battery it has to be changed.
- **Post-flight statistics** — the page that appears in the goggles after a disarm. Its content is set by `osd_stat_bitmask` (a bit mask; it is easier to tick the boxes in the OSD tab → Post Flight Statistics). Enabled by default: maximum speed, minimum voltage, minimum RSSI, maximum current, mAh used, the Blackbox state and log number, timer 2, and the full-throttle time and count and the average throttle (the last three — in builds with `USE_RC_STATS`). Separately — the aircraft's “odometer” counters: `stats_total_flights`, `stats_total_time_s`, `stats_total_dist_m` (distance — only with GPS). They are off while `stats_min_armed_time_s` = −1; with a value N ≥ 0 a flight longer than N seconds is added to the counters and saved 0.5 s after the disarm (`fc/stats.c`). The save is skipped if the config has unsaved changes (for example, in-flight adjustments) — the counters live in the same EEPROM as the whole config.
- **Voltage**: show the average per cell (`osd_avg_cell_voltage_pos`) and set `vbat_warning_cell_voltage` by the sag under load and `vbat_min_cell_voltage` as the critical level: LiPo 4–6S — 3.5 / 3.3 V (the defaults), Li-Ion — 3.3 / 3.0 V, a 1S whoop — 3.3–3.4 / 3.1–3.2 V (an estimate); punch-outs are filtered out by `vbat_duration_for_warning` (tenths of a second, start with 20), not by lowering the threshold — the table and the reasons are in `f-power`; `vbat_sag_compensation` is not an indication: it cuts the top of the motor range on a fresh battery (from 4.20 V down to `vbat_warning_cell_voltage`) so that the response does not drift as the battery discharges (`bf-pid-reg-in-bf`).
- **Link**: LQ and RSSI dBm from CRSF (not `rssi_channel`), an LQ < 70% warning on 250 Hz ELRS (the “Link budget” module).
- **Timer**: `osd_tim1`/`osd_tim2` (source, precision, alarm) — from arming; for Li-Ion, mAh drawn matters more.
- HD (MSP DisplayPort): `osd_displayport_device`, the default canvas is 53×20 (`OSD_HD_COLS`/`OSD_HD_ROWS` in `osd/osd.h`), but the HD system reports its own canvas over MSP (`MSP_SET_OSD_CANVAS`) and the firmware adjusts `osd_canvas_width/height` to it (each manufacturer has its own size) — elements outside the canvas are not displayed in analog mode.

{{lesson:bf-hd-osd-video|The port mask, `osd_video_system`, the canvases and fonts by system, the 288×72 boot logo — everything HD goggles need except the layout itself.}}

### Element position: what is inside `osd_*_pos`
Every OSD element is one 16-bit variable `osd_<element>_pos` (0–65535, `OSD_POSCFG_MAX = UINT16_MAX`). The bit layout is set by the macros in `osd/osd.h`; it is the same in 4.5.3 and 2025.12 (2025.12 only added parentheses to the macros):

| Bits | Field | Constant in `osd.h` | Values |
|---|---|---|---|
| 0–4 | x, the low 5 bits | `OSD_POSITION_XY_MASK` = 31 | 0–31 |
| 5–9 | y (the row) | `OSD_POSITION_BITS` = 5 | 0–31 |
| 10 | x, bit 5 — the HD extension | `OSD_POSITION_BIT_XHD` = 10 | x up to 63 |
| 11 / 12 / 13 | visible in OSD profile 1 / 2 / 3 | `OSD_PROFILE_BITS_POS` = 11, `OSD_PROFILE_FLAG(p) = 1 << (p − 1 + 11)` | 2048 / 4096 / 8192 |
| 14–15 | display variant (type 1–4) | `OSD_TYPE_MASK` = 0xC000 | 0–3 |

The formula: `value = (x & 31) + ((x >> 5) << 10) + (y << 5) + profile bits + (variant << 14)`. Bit 10 was added for the 53×20 HD canvas: for x ≤ 31 (the whole analog screen is 30 columns) the values are the same as before it. There is no separate “enabled” bit — an element is hidden if no profile bit is set. The defaults (`pgResetFn_osdElementConfig()` in `osd/osd.c`): all elements are hidden near the center — 341 = (21, 10) in a build with OSD (HD), 234 = (10, 7) in a build with OSD (SD) only; the exceptions are the crosshairs, the artificial horizon, the horizon sidebars, the camera frame and the up/down reference: they have their own default positions (also hidden); only `osd_warnings_pos` is enabled, in all three profiles — 14772 = (20, 13) or 14665 = (9, 10). The variant is `OSD_ELEMENT_TYPE_1…4` (`osd/osd_elements.h`): for altitude (`osd_altitude_pos`) type 2 is whole meters without tenths (in 2025.12 types 3–4 are the same above mean sea level), for battery usage (`osd_battery_usage_pos`) — a bar or a percentage, for the GPS coordinates — different formats; in the OSD tab this is a drop-down list next to the element.

How Betaflight Configurator 10.10 writes it (`src/js/tabs/osd.js`; the packing in Betaflight App for 2025.12 was not checked against its source): internally the application stores the position as `canvas_width × y + x`, and before sending packs it into the same bits (`OSD.msp.helpers.pack.position`) and sends `MSP_SET_OSD_CONFIG` — the element number (1 byte) and the 16-bit value; the firmware puts it into `item_pos[]` as is (`msp/msp.c`). That is why a `diff` after the OSD tab contains exactly the numbers that the formula and the Python model of the practice give, while the internal index 53 × y + x must not be pasted into the CLI: 53 × 18 + 46 = 1000 will be read as (8, 31) without a single profile bit, that is, “hidden”. CMS (OSD → ACTIVE ELEM) changes only the profile bits: “X-X” — visible in profiles 1 and 3; a position cannot be set from the menu.

{{diagram:bf-osd-pos-bits|A worked example: the cell voltage at (40, 17), visible in profiles 1 and 3, is 8 + 544 + 1024 + 2048 + 8192 = 11816; without bit 10 the element moves to column 8.}}

### OSD profiles: visibility and switching from a switch
A profile is not a separate layout but a visibility mask: the position and variant of an element are shared by all three profiles, and only bits 11–13 differ. The active profile is `osd_profile` (1–3, 1 by default). The firmware turns it into the mask `1 << (osd_profile − 1)` and draws an element if its profile bit matches the mask (`setOsdProfile()`, `osdElementVisible()` in `osd/osd.c`). The profile names are `osd_profile_1_name`, `osd_profile_2_name`, `osd_profile_3_name` (up to 16 characters, empty by default); there is no `osd_profile_name` variable, and the `osd_profile_name_pos` element shows the name of the active profile. Profiles exist in any build with OSD (`USE_OSD_PROFILES` in `target/common_pre.h`).

Where to switch: the CLI `set osd_profile = 2`; the OSD tab → “Active OSD Profile” (the “Preview for” selector — its App 2025.12 label — changes only the preview in the application); CMS → OSD → OSD PROFILE (1–3); in the air — `adjrange` with select function **29** (OSD_PROFILE). 29 is the number for the CLI: the index in the `defaultAdjustmentConfigs[]` array plus 1 (OSD_PROFILE is element [28]; the array lacks the four enum functions ROLL/PITCH_RC_RATE/EXPO, so from PID_AUDIO on the CLI number = enum − 4). The enum value `ADJUSTMENT_OSD_PROFILE` = 33, and `adjrange … 33` lands on the zero entry of the array (the NONE function) and does nothing — in both 4.5 and 2025.12 (`fc/rc_adjustments.c`, the table is in bf-adjustments). The channel is divided into 3 parts of 400 µs: 900–1299 → profile 1, 1300–1699 → 2, 1700–2099 → 3. A working line for the layout of this module (a course guideline: the OSD profile on a three-position, non-momentary switch AUX4, channel index 3), slot 3: `adjrange 3 0 3 900 2100 29 3 0 0` — the slot is always active, and the adjustment channel is the same AUX4. A switch at ≈988 / 1500 / 2012 µs gives profiles 1 / 2 / 3 with a margin of 200–312 µs to the boundaries.

{{lesson:bf-adjustments|All the `adjrange` functions with their CLI and enum numbers, the select mode and saving adjustments with the sticks are there.}}

Why the slot range is exactly 900–2100: only for such a “permanent” slot does the firmware not mark the config dirty (`setConfigDirtyIfNotPermanent()`). With a narrow range the unsaved-changes flag is set on any change of the adjustment channel value while the slot is active (and at the moment the range is entered), even if the profile did not change — and the `stats_total_*` counters will not be written after such a flight. An OSD profile change does not beep, is not written to Blackbox and is not shown by the adjustment range element; the confirmation is the `osd_profile_name_pos` element placed in all three profiles: it shows the profile name, or `OSD_1`…`OSD_3` if the names are empty. After a reboot the saved `osd_profile` applies at first, but an active slot sets the profile from the switch on the very first RC frame.

A course guideline: profile 1 — full (cell voltage, mAh, LQ, RSSI dBm, timer, mode, warnings, name), profile 2 — a racing minimum (voltage, LQ, timer, warnings), profile 3 — warnings only, for a clean recording. Keep `osd_warnings_pos` in all three profiles, as by default: an “empty” profile without warnings hides both the critical voltage and `FAILSAFE`.

### Warnings and statistics: the bit numbers
`osd_warn_bitmask` and `osd_stat_bitmask` are 32-bit numbers (`VAR_UINT32`), and bit N is item N of the enum `osdWarningsFlags_e` / `osd_stats_e` in `osd/osd.h`. There are no separate CLI variables per warning or statistics item — only these two masks. The OSD tab sends the warnings in the common `MSP_SET_OSD_CONFIG` packet twice — as a 16-bit copy for old APIs followed by the 32-bit word (the firmware takes the last one), and the statistics items one at a time (number, on/off, “screen 0”). To set bit N: `mask | (1 << N)`, to clear it: `mask & ~(1 << N)`.

| Bit | Warning in 4.5.3 | Warning in 2025.12 |
|---|---|---|
| 0–4 | ARMING_DISABLE, BATTERY_NOT_FULL, BATTERY_WARNING, BATTERY_CRITICAL, VISUAL_BEEPER | the same |
| 5 | CRASH_FLIP | CRASHFLIP |
| 6 / 7 | ESC_FAIL / CORE_TEMPERATURE | the same |
| 8 | RC_SMOOTHING | FAIL_SAFE |
| 9 | FAIL_SAFE | LAUNCH_CONTROL |
| 10 | LAUNCH_CONTROL | GPS_RESCUE_UNAVAILABLE |
| 11 | GPS_RESCUE_UNAVAILABLE | GPS_RESCUE_DISABLED |
| 12 | GPS_RESCUE_DISABLED | RSSI (off) |
| 13 | RSSI (off) | LINK_QUALITY (off) |
| 14 | LINK_QUALITY (off) | RSSI_DBM (off) |
| 15 | RSSI_DBM (off) | OVER_CAP (off) |
| 16 | OVER_CAP (off) | RSNR (off) |
| 17 | RSNR (off) | LOAD |
| 18 | LOAD | POSHOLD_FAILED |
| **default** | **270335** (0x41FFF) | **397311** (0x60FFF) |

A mask from 4.5 is not carried over to 2025.12. An example from the run of the practice: in 4.5, LINK_QUALITY and RSSI_DBM were added to the default — 319487. Pasted into 2025.12, this mask will enable RSSI, RSSI_DBM and OVER_CAP, disable LOAD, and leave LINK_QUALITY off. For 2025.12 the same intent is `set osd_warn_bitmask = 421887` (397311 + 8192 + 16384).

Statistics — the list is the same in 4.5.3 and 2025.12; **bold** — enabled by default, with an asterisk — enabled only in a build with `USE_RC_STATS` (present in any build with OSD); in a RACE_PRO build the defaults that remain are MIN_BATTERY, TIMER_2 and the three items with an asterisk:

| Bit | Item | Bit | Item | Bit | Item |
|---|---|---|---|---|---|
| 0 | RTC_DATE_TIME | 11 | MAX_ALTITUDE | 22 | TOTAL_DIST |
| 1 | TIMER_1 | **12** | **BLACKBOX** | 23 | MIN_RSSI_DBM |
| **2** | **TIMER_2** | **13** | **BLACKBOX_NUMBER** | 24 | WATT_HOURS_DRAWN |
| **3** | **MAX_SPEED** | 14 | MAX_G_FORCE | 25 | MIN_RSNR |
| 4 | MAX_DISTANCE | 15 | MAX_ESC_TEMP | 26 | BEST_3_CONSEC_LAPS |
| **5** | **MIN_BATTERY** | 16 | MAX_ESC_RPM | 27 | BEST_LAP |
| 6 | END_BATTERY | 17 | MIN_LINK_QUALITY | 28* | FULL_THROTTLE_TIME |
| 7 | BATTERY | 18 | FLIGHT_DISTANCE | 29* | FULL_THROTTLE_COUNTER |
| **8** | **MIN_RSSI** | 19 | MAX_FFT | 30* | AVG_THROTTLE |
| **9** | **MAX_CURRENT** | 20 | TOTAL_FLIGHTS | | |
| **10** | **USED_MAH** | 21 | TOTAL_TIME | | |

The default `osd_stat_bitmask` = 1879062316 (with `USE_RC_STATS`), without it — 14124. A course guideline for ELRS: add MIN_LINK_QUALITY (17) and MIN_RSSI_DBM (23) — 1879062316 + 131072 + 8388608 = 1887581996.

### `craft_name`, `pilot_name` and where they are visible
| Variable | Length | Where it is visible |
|---|---|---|
| `craft_name` | up to 16 characters, empty by default | the `osd_craft_name_pos` element (in upper case; with an empty name — the text “CRAFT_NAME”); the name in Betaflight App and in the old DJI OSD (`MSP_NAME`); the Blackbox log header “Craft name”; the `# name:` line at the start of a `diff` |
| `pilot_name` | up to 16 characters, empty by default | only the `osd_pilot_name_pos` element (when empty — “PILOT_NAME”) and the `MSP2_GET_TEXT` request |

There is no `display_name` variable in 4.5 and 2025.12: 4.3 had `name` and `display_name` (the `osd_display_name_pos` element), and 4.4 renamed them to `craft_name` and `pilot_name`. A `set display_name = …` line from an old backup will give `INVALID NAME`. `osd_craftname_msgs = ON` (OFF by default; in the code — “for systems where the OSD is limited to the MSP field”; apparently this is old DJI without DisplayPort — an inference, not from the source) makes the firmware write LQ, RSSI dBm and warnings into `craft_name` in RAM, so that the goggles show them in the name field (`osd/osd_elements.c`, inside `osdElementWarnings()`). The write happens only while the warnings element is visible in the active profile. Any `save` (with the sticks, from the CLI, or the autosave of the `stats_total_*` counters after a flight) will write that text to EEPROM in place of the name — after the mode is turned off the name has to be set again.

### A worked example: a layout for a team
The same layout as in the example above, with ranges: AUX1 ARM (1700–2100); AUX3 the mode: ACRO (900–1300, nothing active) / ANGLE (1300–1700) / HORIZON (1700–2100); AUX6 FAILSAFE STAGE1 (1700–2100) — for the ground test and the first flights; AUX7 BEEPER (1700–2100); AUX8 PREARM (1700–2100, logic AND with ARM on the same drones from 7" up). On the free channels: AUX2 BLACKBOX (1700–2100) with a small flash; AUX4 — OSD profile 1/2/3 with the line `adjrange 3 0 3 900 2100 29 3 0 0` (the theory above). It is written in the aircraft record and in the radio model; the same on all aircraft.

{{diagram:bf-modes-layout|An example layout of modes over the AUX channels.}}

### Place in the system

- **Receives:** the AUX channels from the receiver (`link-protocols`, `link-elrs`); voltage and current from calibrated sensors (`bf-setup-scratch`); LQ and RSSI dBm from CRSF (`link-elrs`); the canvas size of the HD system (`bf-hd-osd-video`).
- **Provides:** the mode states — to arming and failsafe (`bf-arming-safety`, `bf-failsafe`); the stick commands for saving and profiles (`bf-adjustments`); the warnings by which the pilot decides to return.
- **If you get it wrong here:** the LINK_QUALITY and RSSI_DBM warnings are not enabled in `osd_warn_bitmask` (they are off by default) → the thresholds are set, but the goggles show nothing right up to failsafe; the link margin is in `link-elrs`. ELRS takes the arm state from CH5, while in Modes ARM is on another channel → the module considers the aircraft disarmed and in flight keeps the reduced Dynamic Power level (`link-elrs`).

## practice
### Step 1. The switch layout
1. On the radio: assign the switches to channels AUX1…AUX8 (CH5…CH12).
2. In Modes: ARM — AUX1, the range on the upper position only.
3. ANGLE — a separate switch; FAILSAFE — STAGE1 on a three-position switch; BEEPER; PREARM, if needed.
4. In the tab — check that every switch turns on only its own mode.
5. `diff all` — save it. Write the layout into the drone's log and repeat it on the others.

**Exercise without hardware: read `aux`.** The first table holds the layout from the worked example, written as `aux <index> <mode id> <aux channel> <start> <end> <logic>` commands (a teaching example, assembled by hand). Take the mode id from the `permanentId` table in the theory; the channel counts from zero: 0 = AUX1. For every line write down the mode, the AUX channel and the range; then answer what is active on AUX3 at 1000, 1500 and 2000 µs.

| Line |
|---|
| `aux 0 0 0 1700 2100 0` |
| `aux 1 1 2 1300 1700 0` |
| `aux 2 2 2 1700 2100 0` |
| `aux 3 27 5 1700 2100 0` |
| `aux 4 13 6 1700 2100 0` |
| `aux 5 36 7 1700 2100 0` |
| `aux 6 26 1 1700 2100 0` |

In the second table the author wanted the same layout but made mistakes in five lines (a teaching example, assembled by hand). Find the mistakes and write down what will happen in each case.

| Line |
|---|
| `aux 0 0 0 1700 2100 0` |
| `aux 1 1 2 1300 1750 0` |
| `aux 2 2 2 1700 2100 0` |
| `aux 3 28 5 1700 2100 0` |
| `aux 4 13 0 900 1300 0` |
| `aux 5 36 8 1700 2100 0` |
| `aux 6 26 1 1710 2100 0` |

### Step 2. OSD
1. Select the elements: cell voltage, timer, LQ/RSSI, mode, warnings, name.
2. Arrange them so that the center of the screen stays free.
3. The voltage warning thresholds — from the `f-power` table for your chemistry and class (LiPo 4–6S: warning 3.5 V per cell under load, critical 3.3 V, delay 2 s). The check after landing on the warning: the charger put back no more than 0.8 of the capacity, and the resting voltage is no lower than 3.5–3.6 V per cell.
4. Check in the goggles on the bench without props: all the elements are visible and do not overlap.

**Exercise without hardware: thresholds and stick commands.** Answer in writing, relying only on the theory of the module. (1) The OSD config is at defaults, the link is ELRS: LQ dropped to 60 %, RSSI is −75 dBm. Which link warnings will appear in the goggles, and what has to be changed? (2) `osd_cap_alarm` is left at the default, the OVER_CAP warning is enabled. When will it appear on a 1300 mAh battery and when on a 5000 mAh battery? (3) While disarmed you give the “Save the config” command, but pitch stopped at 1060 µs. Which command will be executed and how many beeps will sound?

### Step 3. Positions and masks: the calculation per `osd.h`
A model of the macros `OSD_POS`, `OSD_X`, `OSD_Y`, `OSD_PROFILE_FLAG` and `OSD_TYPE` is two functions (the full lab `bf-modes-osd.pos_lab.py` from the course working folder, stage 6, checks the constants against `osd.h` of the 4.5.3 and 2025.12.5 trees, prints the bit tables and compares a Python copy of the Configurator 10.10 packer (`OSD.msp.helpers.pack.position`) with the firmware macros — there are no differences):

```python
def osd_pos(x, y, profiles=(), variant=0):          # OSD_POS + OSD_PROFILE_FLAG, osd/osd.h
    v = (x & 31) | ((x << 5) & 0x400) | ((y & 31) << 5)
    for p in profiles:
        v |= 1 << (p - 1 + 11)
    return v | (variant << 14)

def osd_decode(v):                                   # OSD_X, OSD_Y, profile bits, OSD_TYPE
    x = (v & 31) | ((v & 0x400) >> 5)
    return x, (v >> 5) & 31, [p for p in (1, 2, 3) if v >> (p + 10) & 1], v >> 14

print(osd_pos(40, 17, profiles=(1, 3)))              # avg cell voltage, HD 53x20
print(osd_decode(21665))
print(osd_decode(341), osd_decode(14772))            # defaults of an HD build
```

```text
11816
(33, 5, [2], 1)
(21, 10, [], 0) (20, 13, [1, 2, 3], 0)
```

The first line is the example from the theory (the bit diagram). The second: 21665 is an element at (33, 5), visible only in profile 2, variant 1. The third is the defaults of an HD build: any element — hidden at (21, 10), the warnings — (20, 13) in all profiles.

**Exercise without hardware: positions, masks, the switch.** Calculate it yourself (by hand or with the functions above) and compare with the reference. (a) The LQ element on the 53×20 canvas in column 46, row 18, visible only in profile 2: what number goes into `set osd_link_quality_pos = …`? (b) A `diff` has `set osd_warnings_pos = 14772`: where is the element and in which profiles is it visible? (c) On 2025.12 the LINK_QUALITY and RSSI_DBM warnings have to be added to the default: what is the `osd_warn_bitmask` value? (d) Write the `adjrange` line for the OSD profile on the three-position switch AUX4 (slot 3), and which profile there will be at 988, 1500 and 2012 µs.

### Step 4. The ground test
Without props: arm/disarm, ANGLE (the model in the configurator levels out), the beeper, the failsafe switch (`FAILSAFE` in the OSD). Only after that — to the field.

Self-check: the lab is complete when:
- the first table is decoded as: ARM — AUX1 1700–2100; ANGLE — AUX3 1300–1700; HORIZON — AUX3 1700–2100; FAILSAFE — AUX6 1700–2100; BEEPER — AUX7 1700–2100; PREARM — AUX8 1700–2100; BLACKBOX — AUX2 1700–2100;
- for AUX3 you got: 1000 µs — no mode is active (ACRO), 1500 — ANGLE, 2000 — HORIZON;
- exactly five mistakes are found in the second table — in the lines with indices 1, 3, 4, 5 and 6;
- the answers of step 3: (a) 5710; (b) x = 20, y = 13, profiles 1, 2, 3; (c) 421887; (d) `adjrange 3 0 3 900 2100 29 3 0 0`, profiles 1 / 2 / 3; the functions `osd_pos`/`osd_decode` on your computer print the same three lines as the output above;
- the answers to the three questions of step 2: (1) none; (2) on 1300 mAh — never, on 5000 mAh — after 2200 mAh, that is, at 44 % of the capacity; (3) “PID profile 3”, three beeps instead of one;
- on hardware (if you have it): in the Modes tab every switch highlights only its own mode, and `diff all` contains the same `aux` lines as the first table, with a seventh field `0` added (linkedTo; the firmware prints 7 fields, and the 6-field form is accepted for compatibility), up to your own channels.

**Reference for self-check.** The mistakes of the second table: index 1 — the ANGLE range 1300–1750 overlaps HORIZON 1700–2100, and at 1700–1750 µs both modes are active at once; index 3 — id 28 is AIR MODE, not FAILSAFE (27): the failsafe test switch tests nothing; index 4 — BEEPER is put on AUX1, that is, ARM got a neighbor on the channel, and the beeper is on the whole time the arm switch is down; index 5 — channel 8 is AUX9, not AUX8 (7): PREARM will never turn on from the switch written in the layout; index 6 — 1710 is not a multiple of the step of 25. The answers of step 2: (1) the thresholds `osd_link_quality_alarm` 80 % and `osd_rssi_dbm_alarm` −60 dBm are both crossed, but LINK_QUALITY and RSSI_DBM are not enabled in `osd_warn_bitmask` by default — the goggles show nothing until you enable them; (2) 2200 mAh is exactly mAh, not a percentage: 2200 > 1300, and 2200/5000 = 0.44; (3) pitch at 1060 is above `min_check` 1050, so it is “center”, and the combination “throttle LO, yaw LO, pitch center, roll HI” is PID profile 3. Step 3: (a) 46 & 31 = 14, bit 5 of x → 1024, 18 × 32 = 576, profile 2 → 4096; 14 + 1024 + 576 + 4096 = 5710. Typical mistakes from the lab run: x added whole (46 + 576 + 4096 = 4718) — bit 5 of x lands in y, and the element is read as (14, 19); the profile taken as `1 << (p + 11)` — 9806, the element ends up in profile 3; the application's internal index 53 × 18 + 46 = 1000 pasted in — that is (8, 31) without profile bits, the element is hidden. (b) 14772 is the default `osd_warnings_pos` of an HD build. (c) 397311 + 8192 + 16384 = 421887; if the bit numbers are taken from 4.5 (14 and 15), RSSI_DBM and OVER_CAP will be enabled, and LINK_QUALITY will not. (d) function 29, not 33 (the enum); the position width is 400 µs. Frequent wrong answers: the AUX channel read without the offset (channel 2 written as AUX2 — it is actually AUX3); the mode id taken as the ordinal number in the Modes tab list, not the `permanentId`; in question (1) the answer “both warnings will appear” — a threshold does not work without the warning enabled.

## diagnostics
- **Symptom:** arming does not work, the OSD shows `ARM_SWITCH` (before 2025.12 — `ARMSWITCH`) or `NOPREARM`
  - Possible cause: the ARM switch was on when power was applied, or PREARM is not on.
  - What to do: turn ARM off and on again, check PREARM.
- **Symptom:** a mode is turned on by the wrong switch
  - Possible cause: the channel or the range is mixed up.
  - What to do: the check in the Modes tab; the Receiver tab — which channel moves.
- **Symptom:** no OSD in the goggles
  - Possible cause: OSD is not enabled in Configuration, the wrong type (analog/digital), the UART is not set up for DisplayPort.
  - What to do: check the OSD type and Ports.
- **Symptom:** the voltage warning comes too late
  - Possible cause: the threshold was calculated for the resting voltage.
  - What to do: raise the threshold to account for the sag under load.
- **Symptom:** a mode “flickers” at a switch boundary
  - Possible cause: a range without a margin, channel jitter.
  - What to do: ranges with a 100 µs margin, check in the Receiver tab.
- **Symptom:** the OSD elements “moved” after the switch to HD
  - Possible cause: the positions were set for the analog canvas.
  - What to do: arrange them again for the HD canvas (`get osd_canvas`); an OSD profile will not help here — the position is shared by the three profiles.
- **Symptom:** an element is enabled in the OSD tab but is missing in the goggles, or disappears at the flick of a switch
  - Possible cause: the profile bit of the active profile is not set (bits 11–13), or `adjrange` changed `osd_profile`.
  - What to do: `get osd_profile`, in the OSD tab enable the element for all the profiles needed; check the value with `osd_decode()`.
- **Symptom:** after a manual `set osd_*_pos = …` the element ended up somewhere else or disappeared
  - Possible cause: x > 31 was written without splitting it into bits 0–4 and 10; the index 53 × y + x from the application was pasted; the profile bit is shifted by one.
  - What to do: recalculate with the formula from the theory; the check — `osd_decode()` returns the intended x, y and profiles.
- **Symptom:** after a `diff` was carried from 4.5 to 2025.12 the LQ warning disappeared, but RSSI or OVER_CAP appeared
  - Possible cause: the `osd_warn_bitmask` line was carried over as a number; in 2025.12 RC_SMOOTHING was removed and bits 9–18 moved down by one.
  - What to do: enable the warnings again in the OSD tab of the application of the same version as the firmware (Betaflight App for 2025.12; Configurator 10.10 labels the bits by the 4.5 list — its bit 8 is RC_SMOOTHING), or recalculate the mask from the 2025.12 table.
- **Symptom:** `set display_name = …` or `set name = …` from an old backup gives `INVALID NAME`
  - Possible cause: these are 4.3 variables; from 4.4 they are called `pilot_name` and `craft_name`.
  - What to do: replace the names in the backup, check `get craft_name`.

## references
- Auxiliary (Modes) tab — Betaflight App | https://betaflight.com/docs/wiki/app/auxiliary-tab | primary | A
- OSD tab — Betaflight App | https://betaflight.com/docs/wiki/app/osd-tab | primary | A
- Mode box names (msp_box.c, GitHub) | https://github.com/betaflight/betaflight/blob/master/src/main/msp/msp_box.c | primary | A
- Arming Sequence & Safety — Betaflight Documentation | https://www.betaflight.com/docs/wiki/guides/current/Arming-Sequence-And-Safety | primary | A
- osd.h — OSD_POS, OSD_PROFILE_FLAG, warnings and stats enums, Betaflight 2025.12.5 | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/osd/osd.h | primary | A
- osd.h — the same, Betaflight 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/osd/osd.h | primary | A
- osd.c — pgResetFn_osdConfig / osdElementConfig, osdElementVisible, Betaflight 2025.12.5 | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/osd/osd.c | primary | A
- rc_adjustments.c — OSD_PROFILE select adjustment, Betaflight 2025.12.5 | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/fc/rc_adjustments.c | primary | A
- Betaflight Configurator 10.10 — tabs/osd.js (position packing, MSP_SET_OSD_CONFIG) | https://raw.githubusercontent.com/betaflight/betaflight-configurator/10.10.0/src/js/tabs/osd.js | primary | A

## checklist
- ARM is on a separate switch, with no neighbors on the channel
- ANGLE, BEEPER, FAILSAFE are assigned
- The layout is the same on all my drones and is written down
- In the OSD: cell voltage, timer, LQ, mode, warnings
- The voltage thresholds account for the sag
- `osd_warnings_pos` is visible in all three OSD profiles; the OSD profile on a switch — function 29, slot 900–2100
- `osd_warn_bitmask` is calculated for your firmware version, LINK_QUALITY and RSSI_DBM are enabled
- The ground test without props is passed
