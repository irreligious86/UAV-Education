---
id: inav-intro
title: "Introduction to INAV"
level: L1
readingTime: 20 min
firmware: INAV 9.1 (checked against 9.1.0)
status: published
added: 2026-11-08
tags:
  - INAV
  - navigation
related:
  - bf-intro
  - ap-intro
next:
  - inav-gps
source: content/inav/inav-intro.md
source_hash: d0914c88e729
---

## summary
INAV grew out of the same codebase as Betaflight but went in a different direction: navigation. It is the firmware for people who need position hold, return to home and missions on an inexpensive flight controller — and for fixed wings, which Betaflight does not support at all. This module explains where INAV sits between Betaflight and ArduPilot, what a Betaflight pilot will recognize, what is fundamentally different (platform, arming, navigation modes, safehomes) and how to prepare the first flight.

## theory
### Where INAV fits
- **Betaflight** — manual flight only, minimum latency.
- **INAV** — manual flight plus navigation: POSHOLD, RTH, missions, fixed-wing autolaunch, autoland. It runs on the same F4/F7/H7 boards, with the same configurator approach and a similar CLI.
- **ArduPilot** — a full autopilot with an EKF, Lua, companion computers, a thousand parameters and hardware requirements to match.

INAV is the compromise: navigation without moving to an H7 and without learning ArduPilot.

### Platform
The first decision is `platform_type`: MULTIROTOR, AIRPLANE, TRICOPTER (the values HELICOPTER, ROVER and BOAT are in the list but are not fully implemented). The platform determines the available modes, the mixer presets, whether flaps exist and the navigation logic. A fixed wing and a quadcopter behave like different firmware, even though it is one binary.

### What is familiar after Betaflight
The Ports, Receiver, Modes and OSD tabs, the CLI with `set`/`get`/`save`/`diff all`, Blackbox. A CRSF or SBUS receiver is connected the same way. The Configurator 9.x tab names that differ from Betaflight (`locale/en/messages.json`): the first tab after connecting is called **Status** (Setup in older versions and in older guides); accelerometer and compass calibration is a separate **Calibration** tab; aligning an external compass at an arbitrary angle is the **Alignment Tool** (`inav-gps`); PIDs and rates are on **Tuning**, filters on **Filtering**, plus **Advanced Tuning**, **Mission Control**, **Programming** and **JavaScript Programming** (`inav-ipf`).

### What is different
- **Arming with a switch only.** Stick arming was removed back in INAV 2.2. The fixed-wing exception: `fixed_wing_auto_arm` (OFF by default) with motorstop enabled arms on throttle above `min_check`, and the only way to disarm is a power cycle.
- **Arming is blocked without a GPS fix** if navigation modes are configured (`nav_extra_arming_safety` can bypass this, but that is a deliberate risk).
- **Navigation modes**: NAV ALTHOLD, NAV POSHOLD, NAV RTH, NAV WP, NAV CRUISE (for fixed wings). A multirotor needs a valid heading for POSHOLD and RTH: a calibrated compass or, without a compass (since 7.1), the GPS heading after a short straight-line flight; in 9.1 the heading can also be set on the ground — nose pointing north and the compass calibration stick command (see the section on moving to 9.1).
- **Home** is the arming point (the first arm by default: `inav_reset_home` = FIRST_ARM; EACH_ARM and NEVER also exist); **safehomes** are up to 8 predefined safe landing points. The nearest one within `safehome_max_distance` is selected at the moment of arming and replaces home when RTH is activated.
- **Failsafe** with the procedures DROP, LAND (emergency landing), RTH, NONE. RTH as the failsafe procedure is the main reason to run INAV.
- **Programming Framework** — logic conditions right in the firmware, without Lua.

### Requirements
Navigation means GPS (mandatory), a compass (strongly recommended for a multirotor: without one the heading comes only from GPS while moving, and a position hold without a compass lasts minutes) and a barometer (practically mandatory for a multirotor: without one altitude is held from GPS and the accelerometer only, noticeably worse). A fixed wing can estimate heading from GPS; a compass is desirable.

### Under the hood: an estimator, not an EKF
INAV computes position and altitude with a weighted complementary estimator (`inav_w_*`), not an EKF — simpler and lighter for an F4, but without automatic trust or distrust of sensors (the module “INAV: GPS and RTH”). Hence the requirements: a compass and a baro are practically mandatory for a multirotor (without a baro altitude comes from GPS only, without a compass heading exists only as GPS course while moving); GPS quality matters more than in ArduPilot, where the EKF “survives” bad frames.

### Why it will not arm: reading the OSD
The reason for the block is visible in three places: as text in the OSD (lines such as “WAITING FOR GPS FIX”, “AIRCRAFT IS NOT LEVEL”, “COMPASS NOT CALIBRATED” — the texts from `io/osd.h` 9.1.0, the same in 8.0.1), on the Status tab of the configurator and in the CLI with the `status` command (the `Arming disabled flags:` line). Typical reasons: no GPS fix with navigation modes configured (`nav_extra_arming_safety`), the accelerometer or compass is not calibrated, throttle is not at minimum, tilt is greater than `small_angle`, the arm switch was on at power-up, the CLI or the OSD menu is open, the first mission waypoint is farther than `nav_wp_max_safe_distance`, a sensor failure. The same principle as in Betaflight (the “Safety” module): you remove the cause, you do not bypass it.

The procedure: `status` → flag names → look the flag up in the full table of 24 flags (bit, name, what blocks) in `inav-cli-backup` → fix the cause → `status` again, until the line is empty. The flags whose cause is a setting rather than “wait” (conditions from `fc/fc_core.c` and `navigation.c` 9.1.0):

| Flag | What sets it | Setting | What to do |
|---|---|---|---|
| `NAV` | navigation modes are configured or failsafe may require RTH, and the position is not usable; a navigation mode is already switched on; the first mission waypoint is farther than `nav_wp_max_safe_distance` (100 m); a JUMP error | `nav_extra_arming_safety` = ALLOW_BYPASS (default) | wait for the fix; without a fix — arm with yaw held right (ALLOW_BYPASS only); a distant first waypoint — yaw right while arming with any value of the setting; turn the NAV switch off; fix the JUMP (`inav-missions`) |
| `ROLL/PITCH` | fixed wing, NAV LAUNCH enabled by a switch or by `feature FW_LAUNCH`, and the roll or pitch stick is not centered | channel centers (the threshold in the code is 10 `rcCommand` units after `deadband`, that is about 10 µs from center, `CONTROL_DEADBAND`) | release the sticks, check that the centers are 1500 ± 5 |
| `ANGLE` | tilt is greater than `small_angle` (25°) | `small_angle`, `align_board_*` | level the aircraft; if it sits level and the flag is still there, the board alignment is wrong |
| `NOPREARM` | the PREARM mode is assigned but not activated, or `prearm_timeout` (10 s) has elapsed | `prearm_timeout` | activate PREARM, then ARM within 10 s |
| `LANDED` | the landing detector registered a landing in any mode and disarmed (`nav_disarm_on_landing` = ON, default), or the multirotor is lying inverted (`nav_mc_inverted_crash_detection` > 0, needs a barometer) | — | turn the arm switch off, the flag clears by itself |
| `PWMOUT` | the outputs were not assigned: a servo on a motor timer, not enough timers, the mixer defines more motors or servos than there are outputs (a disabled `feature PWM_OUTPUT_ENABLE` does not set this flag — the outputs are simply silent) | `timer_output_mode`, the mixer | `status` prints `PWM output init error` with the reason; the timer map is in `inav-mixer-vtol` |
| `GEOZONE` | `feature GEOZONE` is enabled and the arming point is inside a no-fly zone | `geozone` | `inav-geozones-landing` |
| `DSHOTBEEPER` | the motors have just beeped on a DShot command | — | wait a fraction of a second; if it persists, turn the DShot beeper off |
| `SETTINGFAIL` | a setting is out of range; `status` prints its name further down | the named setting | correct it and `save` |

### The `feature` flags and what depends on the board
`feature list` prints the enabled features, `feature <name>` enables one, `feature -<name>` disables it, and `save` is required. In 9.1.0 there are 23 names (`fc/cli.c`), but not all of them do anything:

| `feature` | What it enables | When you need it |
|---|---|---|
| `PWM_OUTPUT_ENABLE` | signal output to the motors and servos | without it the outputs are silent; enable it after checking servo directions on the bench (`inav-mixer-vtol`) |
| `GPS` | GPS reception on the port with the GPS function | any navigation |
| `VBAT`, `CURRENT_METER` | voltage and current measurement | always, when the board has the sensors |
| `THR_VBAT_COMP` | raising the throttle as the battery discharges | only together with `VBAT` and a configured current sensor |
| `TX_PROF_SEL` | profile selection with the sticks | `inav-adjustments` |
| `BAT_PROF_AUTOSWITCH` | selecting the battery profile from the cell count detected from the voltage at plug-in | one aircraft flown on 4S and 6S |
| `GEOZONE` | geozones | `inav-geozones-landing`; only boards with more than 512 KB of flash |
| `TELEMETRY` | telemetry to the receiver (S.Port, SBUS2, HoTT and others) | `inav-telemetry-gcs` |
| `SOFTSERIAL` | software UARTs on spare pins | not enough hardware UARTs |
| `LED_STRIP` | an addressable LED strip | `inav-led-pinio-beeper` |
| `BLACKBOX`, `OSD` | logging, the OSD | usually already enabled by the target |
| `AIRMODE` | airmode always on, without the AIR MODE mode | enabled by default |
| `REVERSIBLE_MOTORS` | reversible motors (3D, boats, rovers) | only with ESCs that support reverse |
| `RSSI_ADC` | RSSI from an analog input | old receivers with an RSSI output |
| `DASHBOARD` | a small I²C OLED display | rarely |
| `FW_LAUNCH` | fixed-wing autolaunch without the NAV LAUNCH switch | `inav-wing` |
| `FW_AUTOTRIM` | continuous servo autotrim in flight; the SERVO AUTOTRIM mode then disappears from the list | `inav-wing` |
| `RPM_FILTERS`, `SUPEREXPO`, `VTX`, `TRANSPONDER` | nothing: in 9.1.0 the code does not read these bits (the `RPM_FILTERS` bit is additionally cleared at boot) | the RPM filter is enabled by `rpm_gyro_filter_enabled` and an ESC telemetry port (`inav-mc-tuning`), the VTX by a port with the VTX function |

What is cut out on small boards (`target/common.h` 9.1.0). The rule: check the MCU flash size of your board before you buy it.
- **512 KB of flash or less** (F411, F722): no geozones (`USE_GEOZONE`), FrSky SmartPort master, HoTT, FuriousFPV VTX, SUMD, Spektrum serial receivers (`USE_SERIALRX_SPEKTRUM`), SRXL telemetry, channels AUX15–AUX30 (channels 19–34) or the descriptions in `help`.
- **F411** in addition: one mixer profile (`MAX_MIXER_PROFILE_COUNT 1`), so a VTOL is impossible (`inav-mixer-vtol`). The F722 is an F7 and has two profiles.
- **CAN / DroneCAN**: not in INAV 9.1.0. `USE_DRONECAN` is defined in three H7 targets, but there is no driver in the source tree, so a CAN GPS or CAN ESC cannot be connected — that is a reason to choose ArduPilot (`el-dronecan`).

### Versions and compatibility
The course is checked against INAV 9.1.0: names and defaults are given for 9.1, and the previous form is in parentheses at first mention. H7/F7 are recommended, F4 is supported with memory limitations (some features are cut out in the targets). The configurator must match the firmware by major version: INAV 9.x needs Configurator 9.x. A `diff all` moves between major versions only through a review — settings get renamed (in 8.0 `nav_use_midthr_for_althold` → `nav_mc_althold_throttle`; in 9.0 — the table below).

The 8.0 → 9.1 upgrade procedure (release notes 9.0.0 and 9.1.0):
1. Install INAV Configurator 9.1. On the old firmware save a `diff all` to a file (the CLI or the Diff All → Save to File buttons), with the version and the date in the file name. Configurator 9.1 saves an auto-backup itself before flashing (Firmware Flasher → Open Backups), but your own file is safer.
2. Flash 9.1 **with Full chip erase**. This is mandatory when moving between major versions.
3. Paste the old diff into the CLI. The CLI marks the lines that do not exist in 9.1 in red: `### ERROR: Invalid name`. Write them down and correct them in a copy of the file using the table below.
4. Type `defaults`, after the reboot paste the corrected diff and save. If there are several profiles, paste in two parts: first up to the end of the `# master` block and `save`, then the rest from `# control_profile 1`. Configurator 9.1 can do steps 3–4 itself: after flashing with Full chip erase it offers to restore the backup and shows the 8 → 9 migration window (renames and warnings); compare the result with your own `diff all` anyway.
5. What does not carry over by itself. A diff stores only what differed from the defaults, so everything you never touched silently gets the new 9.x defaults: the GPS constellations and update rate, the altitude estimator weights `inav_w_z_*`, `nav_fw_pos_z_ff`. The new OSD elements (throttle gauge, minimum ground speed) need an updated font.
6. Before you connect the battery for the first time, remove the props and check the motor and servo outputs on the Outputs tab — the 9.0 release notes require this. Then go through the ground check from step 3b.
7. If you had raised `nav_mc_pos_z_p` or `nav_mc_vel_z_p` above the defaults (50 and 100), set them back or retune: the 9.1 estimator relies more on the accelerometer, and the old raised values cause throttle oscillation in RTH, WP and CRUISE.

{{diagram:inav-upgrade-8-to-9|Upgrading 8.0 → 9.1: after Full chip erase you do steps 3–4 by hand or with the Configurator migration window, but either way everything untouched gets the 9.x defaults, and raised nav_mc_pos_z_p / nav_mc_vel_z_p must be set back.}}

### Moving from 8.0 to 9.1: what was renamed and what changed
The table was produced by comparing `settings.yaml`, `logic_condition.h`, `runtime_config.h`, `osd.h`, `cli.c` and `msp_protocol.h` of the tags 8.0.1, 9.0.0 and 9.1.0. There were 665 settings, now there are 677: 4 removed, 16 added. By section: master 505 → 511, control profile 123 → 126, mixer profile 9 → 12, battery profile 28 → 28. The Configurator migration window (`8_to_9.json`) warns that the default of `ahrs_acc_ignore_rate` changed from 20 to 15; in `settings.yaml` it is 15 in both 8.0.1 and 9.1.0 — the firmware has no such change. The arming-disabled flags and their names in `status` did not change.

| Was (8.0.1) | Now (9.1.0) | What changed | Since release |
|---|---|---|---|
| `controlrate_profile` | `use_control_profile` | a battery profile setting: which control profile to switch to together with it (0 — keep the current one); name only | 9.0 |
| `mixer_pid_profile_linking` | `mixer_control_profile_linking` | name only; ON — the control profile follows the mixer profile (VTOL) | 9.0 |
| `osd_pan_servo_pwm2centideg` | `osd_pan_servo_range_decadegrees` | the name; the number is the same (a 180° servo needs 18, range −36…36) | 9.0 |
| `smix` inputs 0…59 | 0…60 | the new input 60 is the internal `MIXER_SWITCH_HELPER`: its value is always 0, and the firmware creates such rules itself on a mixer profile switch so that the `speed` limiter finishes smoothly; the numbers 0…59 did not shift | 9.x (present in 9.1.0) |
| `reboot_character` | — | removed | 9.0 |
| `profile` in older guides | `control_profile` | the CLI command is already called `control_profile` in 8.0.1; in 9.1 the documentation (`docs/Cli.md`) was brought in line with this name, and an error appears only if you type `profile` from an old guide | 9.1 (documentation) |
| `gps_ublox_use_galileo` = OFF, `gps_ublox_use_beidou` = OFF | ON, ON | the default; GLONASS is still OFF | 9.1 |
| `gps_ublox_nav_hz` = 10 | 8 | the default; the GPS tab of Configurator 9.1 has presets for M8, M9 and M10 with module auto-detection, and they set the constellations and the update rate | 9.1 |
| `inav_w_z_baro_v` 0.1, `inav_w_z_gps_p` 0.2, `inav_w_z_gps_v` 0.1 | 0.35, 0.35, 0.35 | the defaults of the altitude estimator weights; `inav_w_z_baro_p` stayed at 0.35 | 9.0 |
| `nav_fw_pos_z_ff` = 10 | 30 | the default; the new `nav_fw_alt_use_position` (OFF — fixed-wing altitude control by vertical velocity, ON — by position) | 9.0 |
| `pitot_lpf_milli_hz` = 350 (max 10000) | 3000 (max 50000) | the default and the limit of the airspeed filter | 9.0 |
| `fw_tpa_time_constant` = 1500, `tpa_rate` up to 100 | 2000, up to 200 | the default and the limit; the new `apa_pow` (0 — off; PID scaling by airspeed) and `tpa_pitch_compensation` (8) | 9.0 |
| `osd_snr_alarm` up to 99 | up to 30 | the limit | 9.0 |
| `vbat_meter_type`, `current_meter_type` | + the value `SMARTPORT` | voltage and current from a SmartPort sensor | 9.0 |
| — | `blackbox_arm_control` = 0 | 0…60 — keep logging for that many seconds after disarm; −1 — log from power-up | 9.0 |
| altitude corrections from the barometer and GPS — on every estimator step | once per sensor update (`updateDt`) | between updates the estimate runs on the accelerometer; raised `nav_mc_vel_z_p` / `nav_mc_pos_z_p` cause throttle oscillation (`inav-mc-tuning`) | 9.x (present in 9.1.0) |
| the `PG_CONTROL_RATE_PROFILES` group | `PG_CONTROL_PROFILES` | only the group name in the source; the setting names and the `control_profile` command are the same | 9.x (present in 9.1.0) |
| — | `acc_temp_correction`, `baro_temp_correction` = 0 | temperature correction of the accelerometer and the barometer; 51 starts the auto calibration | 9.0 |
| — | `mavlink_sysid` = 1, `mavlink_autopilot_type` = GENERIC | the System ID and the autopilot type in MAVLink telemetry (GENERIC or ARDUPILOT) | 9.0 |
| — | `osd_adsb_warning_style`, `stats_flight_count`, `transition_pid_mmix_multiplier_roll/pitch/yaw` | the ADS-B warning style, the flight counter, the PID multipliers in the VTOL transition mode | 9.0 |
| the OSD element `OSD_VARIO_NUM` | `OSD_VERTICAL_SPEED_INDICATOR` | the name; the new elements are the throttle gauge and minimum ground speed | 9.0 |
| logic conditions: operations 0–54, flight operands 0–45 | the same numbers + operations 55, 56 and operands 46–49 | 55 Set Gimbal Sensitivity, 56 Override Minimum Ground Speed; the operands: minimum ground speed, wind speed and direction, relative wind offset. Old rules carry over unchanged | 9.0 |
| the Programming tab | + the JavaScript Programming tab | Configurator 9: JavaScript code is transpiled into the same logic conditions; marked as beta | 9.0 |
| the stick command Calibrate Mag (throttle high, yaw right, pitch back) | Calibrate Compass / Zero Yaw | without a compass on a multirotor the same command on the ground sets the heading to 0° (north) and marks it valid: POSHOLD and a mission are available right after takeoff | 9.1 |
| `osd_video_system = HDZERO`: a 50×18 grid with an automatic 30×16 sub-mode | always 50×18 | the sub-mode was removed; the values of `osd_video_system` are the same | 9.1 |
| servo autotrim (`feature FW_AUTOTRIM`) | + an I-term check | the servo midpoint moves only while the I-term is stable; the setting `servo_autotrim_iterm_rate_limit` existed only in 9.1.0-RC1 — it is not in 9.1.0 | 9.1 |
| — | the CLI command `bind_msp_rx` | binding an MSP receiver (mLRS) | 9.1 |
| MSP v1: `MSP_STATUS` (101), `MSP_STATUS_EX` (150), `MSP_ANALOG` (110), `MSP_MISC`, `MSP_DEBUG` and 14 more commands | marked deprecated | they work but will be removed in INAV 10; the replacements are `MSP2_INAV_STATUS`, `MSP2_INAV_ANALOG` and others. `MSP_RC` (105) and `MSP_SET_RAW_RC` (200) are not affected | 9.1 |
| moving the diff by hand | auto-backup and migration in the Configurator | Firmware Flasher 9.1: the buttons Backup Config, Restore Config, Open Backups; the files `js/migration/7_to_8.json` and `8_to_9.json` | 9.1 |
| `mode_color 6 <0…8> <color>` — the special colors of the strip (disarmed, armed, GPS…) | `mode_color 7 <0…8> <color>`; mode 6 is the new LOITER (NAV POSHOLD) with six directions | when moving a config replace 6 with 7: otherwise the lines with index 0…5 recolor LOITER, and 6…8 give a parse error (`inav-led-pinio-beeper`) | 9.x (present in 9.1.0) |
| MSP RC Override only in a custom build, `msp_override_channels` up to 65535 | in stock firmware, up to 4294967295 (32 channels) | `USE_MSP_RC_OVERRIDE` is enabled in `target/common.h`; the mask is 32 bits (`inav-telemetry-gcs`) | 9.x (present in 9.1.0) |
| `pitot_hardware`: NONE, AUTO, MS4525, ADC, VIRTUAL, FAKE, MSP, DLVR-L10D | + `MS5525`; a GPS-based pitot check with fallback to virtual airspeed | a new sensor; while armed the reading is compared with the computed speed (a 30–200 % corridor), and on failure the airspeed is computed from GPS and wind (`inav-sensors-extra`) | 9.x (present in 9.1.0) |
| CRSF: the `FM` string contains `AIR`; the frames Attitude, Battery, FM, GPS, Vario | `AIR` removed; `GEO`, `TURT`, `WRTH`, `LOTR` added; new frames 0x09, 0x0A, 0x0C, 0x0D (baro altitude, airspeed, RPM, temperature) | fix the radio scripts and voice alerts that parse the `FM` string (`inav-telemetry-gcs`) | 9.x (present in 9.1.0) |
| MAVLink: HEARTBEAT in the `mavlink_extra2_rate` stream, `COMMAND_INT` is not handled | HEARTBEAT and SYSTEM_TIME once a second, separately; `COMMAND_INT` with `MAV_CMD_DO_REPOSITION` | the HEARTBEAT rate no longer depends on extra2; the ground station can command “fly here” | 9.x (present in 9.1.0) |
| — | `MSP2_INAV_SET_WP_INDEX` (0x2221), `MSP2_INAV_SET_CRUISE_HEADING` (0x2223), `MSP2_INAV_SET_AUX_RC` (0x2230), `MSP2_RX_BIND` (0x3001) | new MSP2 commands; `SET_AUX_RC` holds CH13…CH32 until reboot — do not put safety modes on these channels (`inav-telemetry-gcs`) | 9.x (present in 9.1.0) |
| the DShot beacon beeps the motors even on conditions turned off with the `beeper` command | a disabled condition is silent on the motors too | `beeper -RX_LOST` now turns off both lost-model signals — the beeper and the motors | 9.x (present in 9.1.0) |
| SmartPort, sensor 470 (modes): five digits | seven digits (the A and B digits were added) | fix the Lua scripts that parse 470 digit by digit | 9.x (present in 9.1.0) |
| optical flow corrects the estimate at the estimator loop period | at its own interval between sensor packets (`opflow.updateDt`) | the behavior of the flow-based position estimator; no settings change (`inav-sensors-extra`) | 9.x (present in 9.1.0) |

Unchanged between 8.0.1 and 9.1.0 are all the settings the course names in the other INAV modules: `nav_rth_*`, `nav_fw_launch_*`, the `nav_fw_*` throttle and angle settings, `failsafe_*`, `safehome_*`, the fixed-wing autoland settings `nav_fw_land_*` and the geozone settings `geozone_*`, `vbat_scale` and `current_meter_*`, the values of `osd_video_system`, the mode ids in `aux`.

{{diagram:firmware-choice|Where INAV sits among the firmware: GPS navigation and fixed wing without the complexity of ArduPilot/PX4.}}

### Place in the system

- **Receives:** a configuration that is familiar after Betaflight — ports, receiver, modes, CLI (`bf-intro`, `bf-ports`); the sensors without which there is no navigation: GPS, compass, barometer (`inav-gps`).
- **Provides:** the choice of `platform_type`, which determines the modes, the mixer and the navigation (`inav-wing`, `inav-setup-scratch`); the arming and home rules for RTH and missions (`inav-gps`, `inav-missions`); the 8.0 → 9.1 upgrade procedure.
- **If you get it wrong here:** raised `nav_mc_pos_z_p` or `nav_mc_vel_z_p` left in place after the upgrade to 9.x → the estimator relies more on the accelerometer, and the throttle oscillates in altitude hold, in RTH and on a mission (`inav-gps`). You bypassed the arming block without a GPS fix → home — the arming point — is recorded without a fix, and RTH as the failsafe procedure has nothing to rely on (`inav-setup-scratch`).

## practice
### Step 1. Platform and mixer
1. Flash the board with INAV for the right target.
2. The Mixer tab: select `platform_type` and a preset (Quad X, Flying Wing…), apply, save.
3. With the props off check the outputs: the motors and servos respond to the right sticks.

### Step 2. Sensors
1. Accelerometer calibration (6 positions).
2. Compass: calibrate in an open area, check the alignment (`align_mag`).
3. GPS on a UART: the port and the baud rate are on the Ports tab, the protocol (usually UBLOX) on the GPS tab. In Configurator 9.1 the same tab has a preset for the module (M8, M9, M10 or Auto-detect GPS Type).

### Step 3. Modes
ARM — a dedicated switch. ANGLE — the basic mode. NAV ALTHOLD, NAV POSHOLD, NAV RTH — on a three-position switch in order of increasing autonomy. For a fixed wing: MANUAL must be on a separate switch.

### Step 3b. Checking the estimator on the ground (before the first takeoff)
INAV flies where it thinks it is flying; you can check that without props:
1. **Compass**: the aircraft on a level spot with the nose pointing north (by a phone compass) — the heading in the OSD is within ±10°. Turn it to 90°, 180°, 270° — the heading follows. An error in one direction means interference or a wrong `align_mag`.
2. **Home and the arrow**: home is recorded after the fix; carry the aircraft 20–30 m away — the distance to home in the OSD matches your paces, and the home arrow points to where you came from. If the arrow points sideways, the heading is wrong and RTH will fly the wrong way.
3. **Altitude**: raise the aircraft by 2 m (at arm's length or on a ladder) — the altitude in the OSD changes by ~2 m and comes back. A drift of a meter per minute at rest means the baro is in direct sunlight or in an airflow.
4. **Satellites**: a 3D fix, ≥ 10 satellites, HDOP in the OSD ≤ 1.5–2 before the first navigation flight.

| Check | Normal | If not |
|---|---|---|
| Heading at the cardinal points | ±10° on all four | `align_mag`, recalibrate away from metal, move the compass |
| Distance to home when carried | ±2 m over 20 m | wait for a better fix, check the GPS antenna |
| Altitude when raised by 2 m | 2 ± 0.5 m | cover the baro with foam, check the enclosure |

### Step 4. First flight
1. In an open area wait for a 3D fix (the satellite count in the OSD).
2. Arm, ANGLE, a short hover / a circuit.
3. Switch to ALTHOLD, then POSHOLD. Watch how it holds.
4. RTH at a short distance and low altitude, ready to take over.

## diagnostics
- **Symptom:** it does not arm although everything is configured
  - Possible cause: no GPS fix with navigation modes configured, or the compass is not calibrated.
  - What to do: read the reason in the OSD/configurator, wait for the fix, calibrate the compass.
- **Symptom:** in POSHOLD it circles (“toilet bowl”) or drifts away
  - Possible cause: the compass — calibration, alignment, interference from the power wires.
  - What to do: recalibrate, move it onto a mast, check `align_mag`.
- **Symptom:** RTH heads the wrong way
  - Possible cause: home was recorded in the wrong place (armed somewhere else) or a safehome was used.
  - What to do: check the home point in the OSD after arming and the list of safehomes.
- **Symptom:** in MANUAL the fixed wing is uncontrollable
  - Possible cause: reversed servos or the wrong mixer preset.
  - What to do: check the control surface directions on the bench.
- **Symptom:** after an INAV upgrade some settings “disappeared”
  - Possible cause: renamed settings in the diff were not applied (the red `### ERROR: Invalid name` lines), and untouched settings got the new defaults.
  - What to do: read the CLI output while loading the diff, correct the lines using the “Moving from 8.0 to 9.1” table and the Settings.md of the new version, recalibrate.

## references
- INAV Getting Started | https://github.com/iNavFlight/inav/blob/master/docs/Getting%20Started.md | primary | A
- INAV Navigation | https://github.com/iNavFlight/inav/blob/master/docs/Navigation.md | primary | A
- INAV Controls (arming) | https://github.com/iNavFlight/inav/blob/master/docs/Controls.md | primary | A
- INAV Safehomes | https://github.com/iNavFlight/inav/blob/master/docs/Safehomes.md | primary | A
- INAV 9.0.0 Release Notes (the upgrade procedure from 8.0, renamed settings) | https://github.com/iNavFlight/inav/wiki/9.0.0-Release-Notes | primary | A
- INAV 9.1.0 Release Notes (GNSS, heading without a compass, the estimator) | https://github.com/iNavFlight/inav/wiki/9.1.0-Release-Notes | primary | A
- INAV Backup and Restore (auto-backup and migration in Configurator 9.1) | https://github.com/iNavFlight/inav/blob/9.1.0/docs/Backup%20and%20Restore.md | primary | A
- INAV 9.1.0 settings.yaml | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/settings.yaml | primary | A

## checklist
- I understand where INAV sits between Betaflight and ArduPilot
- `platform_type` and the mixer match the aircraft
- The accelerometer and the compass are calibrated, the estimator is checked on the ground (heading, home, altitude)
- I can find the reason for an arming block in the OSD, the configurator and `status`
- ARM is on a dedicated switch, the navigation modes are ordered by increasing autonomy
- The first RTH was tested close and low
