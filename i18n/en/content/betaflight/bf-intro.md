---
id: bf-intro
title: "Introduction to Betaflight"
level: L1
readingTime: 25 min
firmware: Betaflight 2025.12 (checked against 2025.12.5)
status: published
tags:
  - Betaflight
  - getting started
  - configurator
  - setup
references:
  - title: "Getting Started — Betaflight Documentation"
    url: "https://betaflight.com/docs/wiki/getting-started"
    tier: primary
    stack: betaflight
  - title: "Betaflight 2025.12 Release Notes"
    url: "https://betaflight.com/docs/wiki/release/Betaflight-2025-12-Release-Notes"
    tier: primary
    stack: betaflight
  - title: "Betaflight 4.5 Release Notes"
    url: "https://www.betaflight.com/docs/wiki/release/Betaflight-4-5-Release-Notes"
    tier: primary
    stack: betaflight
  - title: "Betaflight Configurator — Official Web App"
    url: "https://app.betaflight.com"
    tier: primary
    stack: betaflight
  - title: "Betaflight Advanced Guide — iFlight"
    url: "https://help.iflight-rc.eu/en-US/betaflight-advanced-guide-951396"
    tier: secondary
    stack: betaflight
  - title: "Betaflight FAQ — How to Start"
    url: "https://www.betaflight.com/docs/wiki/guides/current/FAQ"
    tier: primary
    stack: betaflight
  - title: "Betaflight Configurator — Releases"
    url: "https://github.com/betaflight/betaflight-configurator/releases"
    tier: primary
    stack: betaflight
related:
  - bf-ports
  - bf-modes-osd
  - bf-cli
next:
  - bf-ports
source: content/betaflight/bf-intro.md
source_hash: a13ea98f5580
---

## summary

Betaflight is open-source firmware for multirotor flight controllers with a focus on **low-latency** control and flexible configuration. This article covers the chain from installing the configurator to the first safe flight.

**After reading you will be able to:**

- flash an FC and make a **backup** of the configuration (`diff all`);
- set up **ports, the receiver, modes** and sensor calibration;
- check the **motors and failsafe** before flying.

## theory

### What Betaflight is

Betaflight is a fork of **Cleanflight** (the successor of Baseflight / the STM32 port of MultiWii). The main emphasis of the stack is **performance**: minimum **latency** and a high gyro loop rate (up to **8 kHz**).

**Supported hardware:** flight controllers on **STM32** (F4, F7, H7, G4), **AT32F435**, **APM32** and **RP2350** (the last two — from 2025.12; 4.5 does not have them). **Firmware features:**

- multiple **PID** profiles;
- gyro and **D-term** filtering;
- digital ESC protocols (**DShot**, ProShot);
- **Blackbox** for logs;
- the **CLI** for precise configuration.

### Firmware architecture

The firmware is modular, and its tasks run in real time. **The main tasks:**

- **Gyro task** — reading the gyro (up to 8 kHz), the filters.
- **PID task** — the output to the motors from the **setpoint** vs **gyro** error.
- **RX task** — the receiver (CRSF, SBUS, ELRS and others).
- **Scheduler** — distributing time between the tasks.

**The PID loop:** the `pid_process_denom` setting defines the PID loop rate. Example: gyro at **8 kHz**, `pid_process_denom = 1` (the default) → PID at **8 kHz**; `= 2` → **4 kHz**. On an F4/G4 with bidirectional DShot and a gyro above 4 kHz the firmware itself raises the denom to at least 2 and changes DSHOT600 to DSHOT300.

### Firmware versions and compatibility

The course follows **Betaflight 2025.12** (checked against 2025.12.5). Starting with this branch the version number is calendar-based: year.month.patch. The previous significant branch is **4.5** (the course counts renames from 4.5.3; the latest release is 4.5.5, and the `4.5-maintenance` branch carries the number 4.5.6, but that is not a release: the `src/` code matches 4.5.5 except for the version number in `version.h`; the SITL in the module “Betaflight from scratch” is built from it). The 2026.6 tags exist, but they are not the course's target version. What 2025.12 added to 4.5:

- altitude and position hold (the ALTHOLD and POS HOLD modes), with a common autopilot `ap_*` for them and for GPS Rescue;
- disarm on impact at landing (`landing_disarm_threshold`), a new turtle (`crashflip_rate`);
- for wings: S-term, speed-based TPA, TPA curves;
- a chirp generator for system identification (the CHIRP mode);
- new gyros (IIM-42653, ICM-456xx), the APM32 and RP2350 platforms.

In its day the 4.5 branch brought M10 GPS and a reworked GPS Rescue, *Earth referencing* for Angle / Horizon, fonts for HD VTXs and an RPM filter with harmonic weights — all of that is kept in 2025.12.

**Important:** the **4.5 → 2025.12** transition (like 4.4 → 4.5 before it) requires a **Full Chip Erase** and setting things up section by section. Old **CLI dumps** are **incompatible** line for line because of renames, ranges and changed meanings of settings — see the table at the end of the theory.

### The Betaflight ecosystem

Besides the firmware there is the configurator. From **2025.12** it is **Betaflight App**: a web application and PWA (`https://app.betaflight.com`) that works through **WebUSB / WebSerial**, with a version number that matches the firmware (before 2025.12 — Betaflight Configurator 10.10, a separate program with its own numbering; a web version was already available for 4.5). There is a native application for Android. In the course the word “configurator” means Betaflight App; the tab names are the same.

### Target, unified target and Cloud Build
Firmware is built for a **target** — a description of the board: the processor, which pins go where (`resource`), which gyro is on which SPI bus. Since 4.3 almost all boards are **unified targets**: one binary per processor family (for example, `STM32F405`) plus a text board config (`board_name`, `manufacturer_id`, a set of `resource`/`set` lines) that the configurator loads when flashing. Cloud Build (4.4+) builds the binary on a server with the selected set of features: the receiver protocol, the OSD (analog `USE_OSD_SD` and/or HD `USE_OSD_HD`), GPS, the magnetometer, telemetry, LED, servos or the WING package, altitude and position hold — what you did not select is not in the firmware (the typical causes of “the receiver is silent” and “the OSD disappeared after 2025.12”). `version` in the CLI shows the version, target, date and git revision of the build; the `BUILD KEY` (the key for reproducing the build) is printed by `status`, and build.betaflight.com returns the list of options for that key.

### What the scheduler does every 125 µs
`fc/tasks.c` describes the tasks with a period and a priority; `scheduler/scheduler.c` selects them. The critical ones: `GYRO` (reading, filters) and `PID` (`taskMainPidLoop`: RC command → PID → mixer → DShot) — at the gyro rate / `pid_process_denom`. The rest get what is left: `RX` (receiving and processing frames, event-driven), `SERIAL`, `BATTERY_*`, `GPS`, `OSD` (per `osd_framerate_hz`), `BLACKBOX`, `TELEMETRY`, `LED_STRIP`. The CLI `tasks` command shows the actual period, the average and maximum time of every task and the CPU load; `status` — the gyro rate, the load and the arming flags. Overload (> 85–90% on an F4 at 8 kHz) means skipped tasks, jitter and the `LOAD` flag: the fix is `pid_process_denom = 2` or disabling features.

### The setup map: what lives where
| What | Where in the configurator | Key CLI settings |
|---|---|---|
| Ports and devices | Ports | `serial`, `resource`, `serialrx_provider` |
| Receiver, channels | Receiver | `map`, `serialrx_provider`, `rxrange`, `rc_smoothing_*` |
| Rates, expo, throttle curve | PID Tuning → Rateprofile Settings | `rates_type`, `roll_rc_rate`, `roll_srate`, `roll_expo`, `thr_mid`, `thr_expo`, `rateprofile` (bf-rates-rc) |
| Modes on switches | Modes | `aux` |
| In-flight adjustments | Adjustments | `adjrange` (bf-adjustments) |
| Video transmitter | Video Transmitter | `vtxtable`, `vtx_band`, `vtx_channel`, `vtx_power`, `vtx` — the VTX on a switch (link-vtx, bf-adjustments) |
| LED strip | LED Strip | `led`, `color`, `mode_color`, `ledstrip_*` (bf-led-buzzer) |
| Ready-made sets of settings | Presets | no settings of their own: a preset is a block of CLI commands from the community repository; apply on top of the defaults, `diff all` before and after |
| Motors, ESCs, protocol | Motors | `motor_pwm_protocol`, `dshot_bidir`, `motor_poles`, `motor_idle` (before 2025.12 — `dshot_idle_value`) |
| PID, filters, FF | PID Tuning | `set p_roll`… `simplified_*`, `gyro_lpf*`, `rpm_filter_*` |
| OSD | OSD | `osd_*_pos`, `osd_warn_bitmask` |
| Blackbox | Blackbox | `blackbox_device`, `blackbox_sample_rate`, `debug_mode` |
| Failsafe | Failsafe | `failsafe_procedure`, `failsafe_delay`, `rxfail` |
| Firmware | Firmware Flasher | — |
Profiles: up to 4 PID profiles (`profile`) and 4 rate profiles (`rateprofile`) — one “calm”, one “racing”. With a switch/adjustment in flight only the rate profile is switched; the PID profile — on the ground while disarmed (sticks, the OSD menu, `profile N`).

### A worked example: the order of the first setup
Firmware (Cloud Build: CRSF, OSD HD, GPS if present) → the default `resource`/target → Ports (the receiver UART) → Receiver (CRSF, checking the channels and the AETR `map`) → Motors (DShot600, `motor_poles`, `dshot_bidir`, direction without props) → Modes (ARM, ANGLE, BEEPER, FAILSAFE) → Failsafe (DROP for the first flight) → OSD (voltage, LQ, timer, warnings) → Blackbox (2 kHz) → `diff all` into the repository (the “CI” module). The first flight is on the default PIDs: out of the box Betaflight flies a 5" better than most manual tunes by a beginner; tuning comes after the logs.

{{diagram:bf-setup-map|The order of the first setup: backup → Ports → Receiver → Modes → Motors (without propellers) → OSD → PID and filters from a log.}}

### The 4.5.3 → 2025.12 transition: what was renamed and changed
This section is the transition checklist and the course's single table: the other modules refer here. The table was obtained by comparing `cli/settings.c`, `cli/cli.c`, `fc/runtime_config.c`, `io/beeper.c`, `msp/msp_box.c`, `osd/osd.h` and the PG defaults at the tags 4.5.3 and 2025.12.5. The settings table did not change between 4.5.3 and 4.5.5; the only notable difference within 4.5.x is the `noreboot` argument (from 4.5.4).

The update procedure and the traps:

1. On the old firmware save `diff all` and `dump all` to a file, write down the output of `version` and `status` (the board name, the BUILD KEY), and take screenshots of the Modes, OSD and Failsafe tabs. Download the Blackbox logs: Full chip erase will wipe them.
2. Check that the board is in the target list for 2025.12 in the Firmware Flasher. Leave an unsupported board on 4.5.x: a “foreign” target gives wrong `resource` assignments (the typical complaint is that the throttle only reaches 30 %).
3. Work in **Betaflight App** (`https://app.betaflight.com`) of the same version as the firmware: from 2025.12 the app number matches the firmware number. Configurator 10.10 is designed for 4.5.
4. In Cloud Build select everything you use: the receiver protocol, the OSD (analog and/or HD), GPS, the magnetometer, LED Strip, SERVOS or the WING package, altitude and position hold. No OSD after flashing — the wrong OSD option in the build.
5. Flash with **Full chip erase**. Do not paste the whole old `diff all`: lines with removed names give `INVALID NAME`, and lines whose name survived with a different meaning (`d_roll`, `iterm_windup`, `osd_warn_bitmask`, `beeper`) silently give a different result. Carry things over section by section, checking against the table.
6. Not carried over at all: the D component of the PID (the meaning of `d_*` is reversed), the numeric masks of `osd_warn_bitmask` and the beeper (the `beeper_off_flags` field in MSP), the bit numbers of the arming flags, `failsafe_off_delay` (different units), the GPS Rescue throttle (`gps_rescue_throttle_*`), the gyro alignment `gyro_1_sensor_align`.
7. After setup: `status` without extra arming flags, a motor test without props, a failsafe check on the bench, the first flight on the 2025.12 default PIDs.
8. A board with a built-in ELRS SPI receiver under 2025.12 stays on ELRS 3 (`ELRS_OTA_VERSION_ID 3` in the 2025.12.5 source): it will not link with a transmitter on ELRS 4. ELRS 4 support for SPI receivers appears only in 2026.6; until then — a transmitter on 3.x for this model or a separate receiver on a UART.

| Old (4.5.3) | New (2025.12) | What changed | Since which release |
|---|---|---|---|
| `d_min_roll`, `d_min_pitch`, `d_min_yaw` (base 30 / 34 / 0) | `d_roll`, `d_pitch`, `d_yaw` (base 30 / 34 / 0) | in 2025.12 `d_*` is the base D; `d_min_*` were removed | 2025.12 |
| `d_roll`, `d_pitch`, `d_yaw` (peak 40 / 46 / 0) | `d_max_roll`, `d_max_pitch`, `d_max_yaw` (peak 40 / 46 / 0) | the peak D got its own name; `d_max_gain` 37 and `d_max_advance` 20 are unchanged; in 2026.6 the defaults are `d_max_gain` 0 and `d_max_advance` 35: D rises toward the peak only from stick speed, not from the gyro (propwash) | 2025.12 |
| `simplified_dmax_gain` | `simplified_d_max_gain` | the name only | 2025.12 |
| `iterm_limit` (400) | — | removed; the I ceiling is now set by `iterm_windup` | 2025.12 |
| `iterm_windup` 85, 30–100 | `iterm_windup` 80, 20–100 | a different meaning: it was “the motor saturation threshold above which I is attenuated”, it became “the I ceiling in % of `pidsum_limit`” | 2025.12 |
| `dshot_idle_value` (550) | `motor_idle` (550) | the name; the units are the same (×0.01 %), 0–2000 | 2025.12 |
| `min_throttle` (1070) | — | removed; for brushed motors the default `motor_idle` = 700 | 2025.12 |
| `dyn_idle_start_increase` (50) | — | removed; the limit of the increase before airmode is taken from `motor_idle` | 2025.12 |
| `feedforward_averaging` OFF, `feedforward_smooth_factor` 25 | 2_POINT and 65 | new defaults; `feedforward_yaw_hold_gain` (15) and `feedforward_yaw_hold_time` (100) were added | 2025.12 |
| `rc_smoothing_feedforward_cutoff` | — | removed; the FF cutoff is calculated together with the setpoint | 2025.12 |
| `tpa_mode` PD / D | PD / D; in a WING build — also PDS | on a copter the set of values did not change; PDS, `tpa_curve_*`, `tpa_speed_*` and negative `tpa_low_rate` values exist only in a WING build (on a copter `tpa_low_rate` is still 0–100, default 20) | 2025.12 |
| `angle_limit` 10–85 | `angle_limit` 10–80 | the default 60 did not change; `angle_pitch_offset` was added in a WING build | 2025.12 |
| `dyn_notch_count` 0–5 | `dyn_notch_count` 0–7 | the range | 2025.12 |
| `debug_mode = GYRO_SCALED` | the log field `gyroUnfilt` | the mode was removed; `DUAL_GYRO_*` → `MULTI_GYRO_*`, `D_MIN` → `D_MAX`, `GPS_RESCUE_THROTTLE_PID` → `AUTOPILOT_ALTITUDE`; TPA, S_TERM, SPA, TASK, GIMBAL, WING_SETPOINT, AUTOPILOT_POSITION, CHIRP, OPTICALFLOW, FLASH_TEST_PRBS, MAVLINK_TELEMETRY were added | 2025.12 |
| `failsafe_off_delay` (10 = 1 s; 0–200, tenths of a second) | `failsafe_landing_time` (60 s; 0–250, seconds) | the name, units and default; convert the value: old ÷ 10 | 2025.12 |
| `gps_rescue_throttle_hover` / `_min` / `_max` (1275 / 1100 / 1700) | `ap_hover_throttle` (1275; 1100–1700), `ap_throttle_min` (1100; 1050–1400), `ap_throttle_max` (1700; 1400–2000) | common autopilot variables: they are used by GPS Rescue, ALTHOLD and POS HOLD; in 2026.6 `ap_throttle_max` defaults to 1900, and `ap_hover_throttle` accepts 0–1700 | 2025.12 |
| `gps_rescue_throttle_p` / `_i` / `_d` (15 / 15 / 20) | `ap_altitude_p` / `_i` / `_d` / `_f` (15 / 15 / 15 / 15) | the altitude loop is common; range 0–200; in 2026.6 the defaults are 30 / 30 / 30 / 30, and `altitude_lpf` and `altitude_d_lpf` go up to 5000 (was up to 1000) | 2025.12 |
| `gps_rescue_landing_alt` (4 m; 1–15) | `ap_landing_altitude_m` (4 m; 0–200) | the name and range | 2025.12 |
| `gps_rescue_disarm_threshold` 20 | 30 | the default; in 2026.6 the variable was removed | 2025.12 |
| `gps_rescue_velocity_p/i/d`, `gps_rescue_yaw_p` 0–255 | 0–200 | the range; in 2026.6 `gps_rescue_velocity_p/i/d` were removed, `gps_rescue_yaw_p` stayed (20; 0–200) | 2025.12 |
| `gps_provider` NMEA / UBLOX / MSP | + VIRTUAL | GPS in SITL; the auto-baud search knows 230400 | 2025.12 |
| `mag_declination` 0–3599 | −300…300 | still tenths of a degree; west declination is written as negative | 2025.12 |
| — | `alt_hold_climb_rate` (50), `alt_hold_deadband` (20), `pos_hold_deadband` (5), `pos_hold_without_mag` (OFF), `ap_position_*`, `ap_max_angle` (50) | the new modes ALTHOLD (id 3) and POS HOLD (id 11); in 2026.6 `pos_hold_without_mag` was removed (POS HOLD needs a heading from GPS or from the compass with `trust_mag = ON`, OFF by default), `ap_position_cutoff` 80 → 30 with a range of 10–50 instead of 10–250 | 2025.12 |
| — | `landing_disarm_threshold` (0 = off; 0–250) | disarm on impact at landing | 2025.12 |
| — | `prearm_allow_rearm` (OFF) | re-arm without toggling PREARM | 2025.12 |
| the arming flag `ARMSWITCH`, bit 25 (26 in total) | `ARM_SWITCH`, bit 28 (29 in total) | bits 25–27 hold the new `FLIP_SWITCH`, `ALT_HOLD_SW`, `POS_HOLD_SW`; decode a hex mask with the table for your version | 2025.12 |
| `beeper` … `CRASH_FLIP`, `RC_SMOOTHING_INIT_FAIL` | `CRASHFLIP`; `RC_SMOOTHING_INIT_FAIL` was removed | the number of `ALL` 24 → 23; the numeric beeper mask (MSP) is shifted — carry it over by names | 2025.12 |
| the OSD warning `RC_SMOOTHING` (bit 8 of `osd_warn_bitmask`) | — | removed; bits 9–18 moved down by one, and bit 18 is the new `POSHOLD_FAILED` | 2025.12 |
| `crashflip_expo` (35; 0–100) | `crashflip_rate` (0; 0–250), `crashflip_auto_rearm` (OFF) | a different turtle algorithm; the sound and the warning `CRASH_FLIP` → `CRASHFLIP` | 2025.12 |
| `launch_control_mode` NORMAL | PITCHONLY | the default | 2025.12 |
| adjustments 0–30 | + 31 `LED_DIMMER` | the `SIMPLIFIED_MASTER_MULTIPLIER` function from the documentation is absent in 2025.12 | 2025.12 |
| mode id 29 “3D DISABLE / SWITCH” | “3D DISABLE” | id 3 ALTHOLD, 11 POS HOLD, 55 CHIRP were added; the other permanentId values are the same | 2025.12 |
| `serial 2 64 …` (port number) | `serial UART3 64 …` (port name) | `diff` writes names; the old numbers are accepted (0 = UART1) | 2025.12 |
| `save`, `exit` — always with a reboot | `save noreboot`, `exit noreboot` | an optional argument | 4.5.4 |
| `flash_read <length> <address>` | `flash_read <address> <length>` | the argument order | 2025.12 |
| `gyro_to_use` FIRST / SECOND / BOTH | `gyro_enabled_bitmask`, `gyro_1_enabled` … `gyro_8_enabled` | up to 8 gyros; `gyro_1_sensor_align`, `gyro_1_align_*`, `gyro_2_*` were removed — after the update check that the arrow on the board points forward and that `align_board_*` are correct | 2025.12 |
| `dshot_edt` OFF / ON | OFF / ON / FORCE | a new value | 2025.12 |
| `expresslrs_rate_index`, `expresslrs_switch_mode` | — | removed (the ELRS SPI receiver) | 2025.12 |
| `serialrx_provider` … SPEK1024 | + MAVLINK | a new receiver protocol | 2025.12 |
| `blackbox_device` NONE / SPIFLASH / SDCARD / SERIAL | + VIRTUAL | `blackbox_disable_attitude`, `blackbox_disable_servos` were added | 2025.12 |
| port: functions up to 131072 | + GIMBAL = 262144 | the serial gimbal `gimbal_*` | 2025.12 |
| the IST8310 compass, I2C address 0x0C | 0x0E | the compass “disappeared” after the update — `set mag_i2c_address = 12` | 2025.12 |
| Betaflight Configurator 10.10 | Betaflight App 2025.12 | a web application and PWA; the version matches the firmware | 2025.12 |

Not affected and carried over as is: `aux`, `adjrange` (function numbers 0–30), `rxrange`, `map`, `vtxtable`, `led`, `color`, `mode_color`, the rates (`rates_type`, `*_rc_rate`, `*_srate`, `*_expo`), the filters (`gyro_lpf*`, `dterm_lpf*`, `rpm_filter_*`, `dyn_notch_*` except the upper bound of the notch count), `failsafe_delay`, `failsafe_procedure`, `failsafe_throttle`, `vbat_*`, `ibata_*`. The 2026.6 differences are not covered in the course, except for the ones people trip over: ELRS 4 for SPI receivers, the corrected range of the IIM-42652 gyro (per the 2026.6 release notes the PIDs are effectively doubled after the update) and the “in 2026.6” notes in the table above (from the source of tag 2026.6.2). A `diff all` from 2025.12 will not load into 2026.6 completely: `set` answers `INVALID NAME` to removed names (`cli/cli.c`). 15 variables were removed: `gps_rescue_velocity_p/i/d`, `gps_rescue_max_angle`, `gps_rescue_roll_mix`, `gps_rescue_pitch_cutoff`, `gps_rescue_imu_yaw_gain`, `gps_rescue_use_mag`, `gps_rescue_disarm_threshold`, `pos_hold_without_mag`, `abs_control_gain/limit/error_limit/cutoff`, `transient_throttle_limit`. The new arming flag `AUTOPILOT_SW` moves `ARM_SWITCH` to bit 29 (`bf-arming-safety`).

{{diagram:bf-migrate-line-tree|A line of an old diff all is carried over only if the name, the meaning and the units are the same; the dangerous lines are those with the old name and a new meaning — they are accepted silently.}}

### Place in the system

- **Receives:** the board target and the set of Cloud Build options (`bf-custom`); the gyro at a rate of up to 8 kHz; receiver frames in the RX task (`bf-ports`, `link-protocols`).
- **Provides:** the order of the first setup and the “what lives where” map — to the other modules; the PID loop rate at which the filters and the controller run (`bf-filters`, `bf-pid-reg-in-bf`); the single table of 4.5 → 2025.12 renames (`bf-cli-automation`).
- **If you get it wrong here:** an old `diff all` was pasted whole after the update → lines with a surviving name (`d_roll`, `iterm_windup`, `beeper`) silently get a different meaning; it shows up as a changed tune (`bf-pid-reg-in-bf`) and different beeper signals (`bf-led-buzzer`). CPU overload on an F4 at 8 kHz → skipped tasks and the `LOAD` flag, arming is blocked (`bf-arming-safety`).

## practice

### Installing Betaflight App (the configurator)

**Option A — web (recommended for a PC):**

1. A **Chromium**-based browser (Chrome, Edge, Opera).
2. Open `https://app.betaflight.com`.
3. On the first connection of the FC, allow access to **USB**.

**Option B — offline or 4.5 firmware:**

- install Betaflight App as a PWA from the same address (the install button in the browser's address bar); the app updates itself from the network;
- for boards that stayed on 4.5.x — Configurator 10.10 from GitHub Releases: `https://github.com/betaflight/betaflight-configurator/releases` (Windows / macOS / Linux).

### Connecting the flight controller

1. A USB cable **with data lines** (not “charge only”).
2. In the configurator: the port (**COM*** / `/dev/ttyACM*`) → **Connect**.
3. If there is no port — drivers (**ImpulseRC Driver Fixer** or manually in Windows).

**The check:** the **Setup** tab — the 3D model follows the tilts. No reaction — the accelerometer or the connection.

### Backup (CLI)

Before any changes: the **CLI** tab → enter the command below → **Save to File**.

```text
diff all
```

`diff all` saves only the **differences from the defaults** — convenient for restoring. `dump all` is for deep diagnostics; it is not recommended for carrying a config **between major versions**.

### Updating the firmware (Firmware Flasher)

1. **Firmware Flasher** — the target board (often detected over USB).
2. The version — the latest of the **2025.12.x** branch (the course is checked against 2025.12.5); in Cloud Build select the receiver protocol, the OSD type, GPS and the other options you need.
3. Enable **Full chip erase** when changing branches (4.5 → 2025.12 — mandatory).
4. **Load Firmware [Online]** → **Flash Firmware**; do not disconnect USB until it is finished.
5. After the reboot — set everything up again or carry the config over from the backup section by section; do not paste a 4.5 backup whole (the section “The 4.5.3 → 2025.12 transition” in the theory).

### The Configuration tab

- **Mixer** — the frame type (**Quad X** for a typical FPV quad).
- **Board Alignment** — **Yaw Degrees** (App 2025.12 labels), if the FC is rotated on the frame.
- The **Power & Battery** tab — the voltage meter source for the voltage display.
- **ESC/Motor Features** — in the current app the DShot protocol, **Bidirectional DShot** and Motor Idle are set in the **Motors** tab.
- **MOTOR_STOP** (“Don't spin the motors when armed”) — if the motors must not spin at zero throttle after arming.

### The Ports tab

- **USB VCP** — a separate row in Ports (not UART1), and MSP is mandatory on it; UART1 is an ordinary hardware port.
- **UART2/3/4** — **Serial Rx** on the port the receiver is soldered to.
- **UART5** (an example) — **GPS**, at **57600** or **115200** baud.

### The Receiver tab

- **Serial (via UART)** receiver mode for CRSF / SBUS / FPORT.
- **Provider:** **CRSF** (ELRS, TBS), **SBUS** (FrSky, DJI and others).
- Sticks on the radio → the bars in the configurator must move.
- The range is **1000–2000** (center **1500**); otherwise **rxrange** in the CLI or the endpoints on the radio.
- **Channel Map** (for example **AETR**, **TAER**) if the channels are mixed up.

### The Modes tab

Assign **AUX** channels to modes. Briefly, what they mean:

- **ARM** — enables the motors (a 2-position switch is best).
- **ANGLE** — self-leveling, for learning.
- **HORIZON** — a hybrid of stabilization and acro.
- **ACRO** — the default; it has no separate row in the list.
- **BEEPER** — finding the drone.
- **GPS RESCUE** — if GPS is set up.

For every mode: **Add Range** → select the channel and the range of the switch position.

### Sensor calibration

- **Accelerometer:** **Setup**, a level surface → **Calibrate Accelerometer**.
- **Magnetometer:** **Calibrate Magnetometer** (the App 2025.12 label), ~30 s of rotation about the axes; check that it agrees with the real heading.

### ESCs and motors (without propellers!)

**Danger:** always **remove the propellers** before testing the motors.

1. **Motors** — enable **I understand the risks**.
2. **Motor 1** — check that it corresponds to the physical motor (in Betaflight Quad X: Motor 1 — rear right, 2 — front right, 3 — rear left, 4 — front left).
3. The rotation direction — per the frame diagram; fix it with the wires or in **BLHeli / Bluejay**.
4. A mismatch in order/direction is the typical cause of a flip on takeoff.

### Preflight check

- **ARM without props** — the motors spin at low RPM.
- **A forward tilt** — the front motors briefly add throttle (stabilization reacts).
- **Failsafe** — turn the radio off; the expected behavior (landing / **GPS Rescue**).
- **OSD** — voltage, timer, mode (if you use a video link).

### An exercise without hardware: carrying a `diff` from 4.5.3 to 2025.12
No board is needed — only the table “The 4.5.3 → 2025.12 transition” from the theory. Below are 13 lines from the backup of an aircraft on 4.5.3 (a training example, put together by hand). For every line write down one of four decisions and, where needed, the new line for 2025.12: **as is**; **rename**; **convert**; **do not carry over** (with the reason). Then count how many lines would give `INVALID NAME` if the block were pasted whole, and how many would silently get a different meaning.

| No. | Line from `diff all` on 4.5.3 |
|---|---|
| 1 | `set d_roll = 44` |
| 2 | `set d_min_roll = 33` |
| 3 | `set iterm_windup = 70` |
| 4 | `set iterm_limit = 350` |
| 5 | `set dshot_idle_value = 600` |
| 6 | `set failsafe_off_delay = 50` |
| 7 | `set gps_rescue_throttle_hover = 1300` |
| 8 | `set simplified_dmax_gain = 120` |
| 9 | `set osd_warn_bitmask = 8191` |
| 10 | `aux 0 0 0 1700 2100 0` |
| 11 | `serial 2 64 115200 57600 0 115200` |
| 12 | `set failsafe_delay = 10` |
| 13 | `set min_throttle = 1050` |

And two questions on the section “Firmware architecture”: (a) an 8 kHz gyro, `pid_process_denom = 2` — what are the PID rate and the loop period in microseconds? (b) an F405 board, `dshot_bidir = ON`, an 8 kHz gyro, and the config has `pid_process_denom = 1` and DSHOT600 — what will the firmware actually set?

Self-check: the lab is complete when:
- the decisions for the lines matched the reference table below — all 13;
- 7 lines would give `INVALID NAME` (2, 4, 5, 6, 7, 8, 13), 3 lines would silently change meaning (1, 3, 9), and 3 lines are carried over unchanged (10, 11, 12);
- (a) 4 kHz and 250 µs; (b) a denom of no less than 2, that is a 4 kHz PID, and DSHOT300;
- on hardware (if you have it): after carrying things over section by section `status` shows no extra arming flags, and `diff all` on 2025.12 contains no name from the left column of the rename table.

**Reference for self-check.**

| No. | Decision | Line for 2025.12 |
|---|---|---|
| 1 | rename: in 4.5 this is the peak D | `set d_max_roll = 44` |
| 2 | rename: in 4.5 this is the base D | `set d_roll = 33` |
| 3 | do not carry over: the name is the same, the meaning is different (it became the I ceiling in % of `pidsum_limit`) | leave the default 80 |
| 4 | do not carry over: the setting was removed | — |
| 5 | rename, the units are the same | `set motor_idle = 600` |
| 6 | convert: tenths of a second → seconds, 50 ÷ 10 | `set failsafe_landing_time = 5` |
| 7 | rename | `set ap_hover_throttle = 1300` |
| 8 | rename | `set simplified_d_max_gain = 120` |
| 9 | do not carry over as a number: the bits shifted | select the warnings again in the OSD tab |
| 10 | as is | `aux 0 0 0 1700 2100 0` |
| 11 | as is: the port number is accepted, and `diff` will write it as a name | `serial UART3 64 115200 57600 0 115200` |
| 12 | as is | `set failsafe_delay = 10` |
| 13 | do not carry over: the setting was removed | — |

Common wrong answers: line 1 is left as is — then the base D becomes 44 instead of 33, and this is the main trap of the transition; line 6 is carried over as the number 50 — a failsafe landing would last 50 s instead of 5; line 3 is classified as `INVALID NAME` — the name `iterm_windup` exists, so the CLI will accept it silently; line 11 is written as `serial UART2 …` — port numbers are counted from zero, and 2 is UART3.

## diagnostics
- **Symptom:** The configurator does not see the controller, the port does not appear
  - Possible cause: the drivers are not installed (Windows), a poor USB cable, a port conflict.
  - What to check/do: replace the cable with one that has data lines. On Windows install the drivers with ImpulseRC Driver Fixer. Restart the computer. Try another USB port.

- **Symptom:** The controller connects, but the 3D model does not react to movement
  - Possible cause: the accelerometer is not calibrated, the sensor is damaged.
  - What to check/do: calibrate the accelerometer on a level surface. If that does not help — check status in the CLI and make sure ACCEL is detected. Check the wires and the solder joints.

- **Symptom:** The drone does not arm, an error is blinking in the top right corner (for example, RXLOSS)
  - Possible cause: the receiver is not getting a signal, the port is not set up, a wrong protocol.
  - What to check/do: check that the correct UART is selected for Serial RX and the right protocol is selected (CRSF/SBUS). Make sure the radio is on and the receiver is linked (the indicator on the receiver is lit). In the Receiver tab check that the bars move.

- **Symptom:** The motors spin, but the drone does not take off or flips when it tries to
  - Possible cause: a wrong motor rotation direction, a wrong connection order, a wrong FC orientation.
  - What to check/do: on the Motors tab check the motor order (Motor 1 — rear right, Motor 2 — front right and so on). Check the rotation direction (by the marking on the propellers). Make sure the FC rotation angle (Yaw Degrees) is set correctly.

- **Symptom:** The sticks move in the configurator, but the values do not reach 1000–2000
  - Possible cause: the endpoints on the radio are set incorrectly.
  - What to check/do: in the radio settings adjust Travel/Endpoints to 1000–2000 µs. Alternatively use the CLI command rxrange for correction.

- **Symptom:** The drone arms, but the motors do not spin (with MOTOR_STOP off)
  - Possible cause: the motor idle is too low for startup.
  - What to check/do: 2025.12 has no `min_throttle` variable (4.5 had it, but it was not used with DShot): on the Motors tab raise Motor Idle (`motor_idle`, before 2025.12 — `dshot_idle_value`; 5.5% by default).
- **Symptom:** after flashing the receiver/GPS do not work although the wiring is correct
  - Possible cause: the feature is not included in the Cloud Build.
  - What to do: `status` → the BUILD KEY, and with it on build.betaflight.com — the list of build options (`version` prints only the version, target, date and git revision); reflash with the ones you need.
- **Symptom:** `LOAD` in the arming flags or CPU > 90%
  - Possible cause: an F4 at 8 kHz with all the features.
  - What to do: `pid_process_denom = 2`, disable LED/unneeded telemetry, `tasks` to find the heavy ones.

## references
- Getting Started — Betaflight Documentation | https://betaflight.com/docs/wiki/getting-started | primary | A
- Betaflight 2025.12 Release Notes | https://betaflight.com/docs/wiki/release/Betaflight-2025-12-Release-Notes | primary | A
- Betaflight 4.5 Release Notes | https://www.betaflight.com/docs/wiki/release/Betaflight-4-5-Release-Notes | primary | A
- Betaflight cli/settings.c, tag 2025.12.5 (the settings table) | https://github.com/betaflight/betaflight/blob/2025.12.5/src/main/cli/settings.c | primary | A
- Betaflight cli/settings.c, tag 4.5.3 | https://github.com/betaflight/betaflight/blob/4.5.3/src/main/cli/settings.c | primary | A
- Betaflight Configurator — Official Web App | https://app.betaflight.com | primary | A
- Betaflight CLI Documentation — Command Reference | https://betaflight.com/docs/wiki/guides/current/Cli | primary | A
- Betaflight Configurator — GitHub Releases | https://github.com/betaflight/betaflight-configurator/releases | primary | A
- Betaflight FAQ — How to Start | https://www.betaflight.com/docs/wiki/guides/current/FAQ | primary | A
- Betaflight Advanced Guide — iFlight | https://help.iflight-rc.eu/en-US/betaflight-advanced-guide-951396 | secondary | B
- GPS Rescue 4.5 — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/GPS-Rescue-v4-5 | primary | A
- Betaflight — Arming sequence and safety (arming flags) | https://www.betaflight.com/docs/wiki/guides/current/Arming-Sequence-And-Safety | secondary | B
- Joshua Bardwell — Betaflight Setup Tutorial | https://www.youtube.com/watch?v=xSzO6HP6yzs | secondary | B

