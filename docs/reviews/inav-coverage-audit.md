# INAV coverage audit: CLI, settings, Configurator tabs, adjustments, popular questions, hardware integration

Date: 2026-11-15. Scope: the INAV track (`content/inav/*.md`, 7 modules: `inav-intro`, `inav-gps`, `inav-missions`,
`inav-wing`, `inav-ipf`, `inav-setup-scratch`, `inav-setup-wing`, plus their quiz and task banks), INAV mentions elsewhere
(found by grep: `link-digital-video`, `est-alt-sources`, `nav-resilience`, `el-redundancy`, `aero-wing`, `aero-stability`,
`f-mechanics`, `diag-troubleshooting`, `bf-servos-pwm`, `bf-hd-osd-video`, `bf-gps-setup`, `bf-setup-scratch`,
`content/pages/setup-cards.html`, `compare.html`). The goal is the one the owner set for Betaflight: close the INAV topic, so
that a student can do everything common from the course alone. I did not edit any course content. Method and structure follow
`docs/reviews/betaflight-coverage-audit.md`.

Legend used throughout: **✓** explained (meaning and usage given, module id) · **~** mentioned only (the name appears, but there
is no usable explanation) · **✗** absent. Priority: **A** must-know for anyone who builds and flies an INAV quad or wing ·
**B** useful, a good student should know it · **C** niche.

---

## 1. Method and sources

### 1.1 Firmware and Configurator sources (read locally, nothing built)

| Source | Version | How |
|---|---|---|
| `iNavFlight/inav`, tag `8.0.1`, commit `ae47bcb` (2025-03-28) | **8.0.1**, the course base | the existing checkout `/tmp/inavsrc/inav8` (`git describe` = 8.0.1) |
| `iNavFlight/inav`, tag `9.1.0`, commit `e519b69` (2026-07-07) | **9.1.0**, the newest firmware tag (tags seen: 9.0.0, 9.0.1, 9.1.0; there is no 9.1.1 firmware tag) | `git clone --depth 1 -b 9.1.0` into `/tmp/inav-audit/inav9` |
| `iNavFlight/inav`, branch `maintenance-10.x`, commit `ae6ace4` (2026-11-10) | 10.x development | the existing checkout `/tmp/inavsrc/inav`, used only to check that bidirectional DShot is still absent |
| `iNavFlight/inav-configurator`, tags `8.0.1` (`6f3b20f`) and `9.1.0` (`bd18782`) | Configurator 8.0.1 / 9.1.0 (a 9.1.1 Configurator tag also exists) | shallow clones, `/tmp/inav-audit/cfg8`, `cfg9`: `index.html`, `tabs/*`, `js/model.js`, `locale/en/messages.json` |

Files I read, in full or in the relevant parts (8.0.1, and 9.1.0 wherever I claim a difference): `fc/settings.yaml` (all
settings), `fc/cli.c` (`cmdTable[]`, `featureNames[]`, `outputModeNames[]`, the print formats of `aux`, `serial`, `adjrange`,
`mmix`, `smix`, `servo`, `wp`, `safehome`, `geozone`, `fwapproach`, `logic`, `gvar`, `pid`, `osd_custom_elements`,
`osd_layout`, `timer_output_mode`, `led`, `color`, `mode_color`, and `cliDiff`, `cliResource`, `cliWaypoints`,
`cliServo`, `cliServoMix`, `cliAdjustmentRange`), `fc/rc_adjustments.[ch]`, `fc/rc_controls.c` (stick commands),
`fc/fc_core.c` (arming checks), `fc/fc_msp_box.c` (mode ids), `fc/runtime_config.[ch]` (arming flags), `fc/fc_tasks.c`,
`io/serial.h`, `io/piniobox.[ch]`, `io/displayport_msp_osd.c`, `io/osd.h`, `io/ledstrip.h`, `flight/servos.[ch]`,
`flight/mixer_profile.h`, `flight/pid_autotune.c`, `flight/imu.c`, `navigation/navigation.[ch]`,
`navigation/navigation_pos_estimator.c`, `programming/logic_condition.[ch]`, `programming/global_variables.[ch]`,
`programming/pid.h`, `sensors/battery.[ch]`, `target/common.h`, `cmake/stm32*.cmake`, and the docs `Cli.md`, `Settings.md`,
`Mixer.md`, `MixerProfile.md`, `VTOL.md` (headings), `Servo.md`, `Servo Gimbal.md`, `Serial Gimbal.md`,
`ESC and servo outputs.md`, `LedStrip.md`, `LED pin PWM.md`, `OSD.md`, `DJI compatible OSD.md`, `Navigation.md`,
`Failsafe.md`, `Battery.md` (8 and 9), `VTx.md`, `Programming Framework.md` (8 and 9), `Safehomes.md`, `Geozones.md`,
`GPS_fix_estimation.md`, `Inflight Adjustments.md`, `Backup and Restore.md` (9.1 only), `javascript_programming/index.md`
(9.1 only).

Setting counts, defaults and ranges were taken with a YAML parser from `settings.yaml` (name, group, `default_value`, `min`,
`max`, `table` values, `condition`). Course coverage was measured by a whole-token search of every course file. Every default
quoted below for an A/B setting was read from that parse, and the A/B ones were also checked by eye in `settings.yaml`.
Defaults written `:target` in the YAML come from the target or from a header; where I give a number for them I name the header
(`VBAT_SCALE_DEFAULT 1100`, `CURRENT_METER_SCALE 400` in `sensors/battery.h`).

**Not built and not run.** I did not build SITL or any target, so no default here comes from a running firmware. I did not
rerun the labs in `inav-setup-scratch` or `inav-setup-wing`. Docs and code disagree in a few places. I always follow the
code and say so.

### 1.2 Web sources

| Source | Status |
|---|---|
| `raw.githubusercontent.com` | works (reachability checked) |
| `git ls-remote` / `git clone` against github.com | works (tag list, clones) |
| github.com HTML, GitHub API | not used (blocked per brief); release notes therefore **not read**, so the 9.x change list below is derived from source and doc diffs |
| Web search (standard) | used only to place popular questions; hits: inavflight.github.io "Something is disabled — Reasons", INAV wiki (Getting started, Fixed Wing Guide, Mixer Tab, Navigation modes), IntoFPV threads, GitHub discussions, Oscar Liang "Setup iNav on an FPV drone", dronedj 2025-03 on DJI goggles native INAV OSD (links in §5) |
| Reddit, IntoFPV and Oscar Liang pages themselves | not fetched; the frequency evidence comes from search hit lists only |

Evidence classes in §5, as in the Betaflight audit: **O** official docs page or INAV wiki page dedicated to the topic,
**L** Oscar Liang guide, **F** several IntoFPV threads in the search results, **G** GitHub issue/discussion found. These
classes give an order of frequency, not a measurement.

### 1.3 Version note: 8.0.1 base, 9.x differences

Course modules say "INAV 7.0+" (`inav-intro`, `inav-gps`, `inav-missions`, `inav-wing`, `inav-ipf`) or "INAV 7/8 (проверено на
8.0.1; имена параметров совпадают в 9.x)" (`inav-setup-scratch`). Checked against 9.1.0, that claim is true for every setting
name the INAV track uses, but several **defaults** differ, and some names that the track does not use were renamed. Here is what
changes from 8.0.1 to 9.1.0, all from source diffs:

- **CLI**: 61 → 62 commands. New: `bind_msp_rx <port>` ("initiate binding for MSP receivers (mLRS)"). Nothing removed.
  `diff`/`dump` scopes are unchanged (`master|battery_profile|control_profile|mixer_profile|rates|all`).
- **Settings**: 665 → 677. Removed: `controlrate_profile`, `mixer_pid_profile_linking`, `reboot_character`,
  `osd_pan_servo_pwm2centideg`. Renamed or replaced: `controlrate_profile` → `use_control_profile` (battery profile picks a
  control profile), `mixer_pid_profile_linking` → `mixer_control_profile_linking`, `osd_pan_servo_pwm2centideg` →
  `osd_pan_servo_range_decadegrees`, PG `PG_CONTROL_RATE_PROFILES` → `PG_CONTROL_PROFILES`. Added: `acc_temp_correction`,
  `baro_temp_correction` (temperature drift compensation, 51 = auto-calibrate), `apa_pow` (airspeed-based PID attenuation
  for wings), `tpa_pitch_compensation` = 8, `nav_fw_alt_use_position`, `blackbox_arm_control`, `mavlink_sysid` = 1,
  `mavlink_autopilot_type` (GENERIC/ARDUPILOT), `osd_adsb_warning_style`, `stats_flight_count`,
  `transition_pid_mmix_multiplier_roll/pitch/yaw` (VTOL transition).
- **Changed defaults** (8.0.1 → 9.1.0): `gps_ublox_use_galileo` OFF → **ON**, `gps_ublox_use_beidou` OFF → **ON**,
  `gps_ublox_nav_hz` 10 → **8**, `inav_w_z_baro_v` 0.1 → 0.35, `inav_w_z_gps_p` 0.2 → 0.35, `inav_w_z_gps_v` 0.1 → 0.35,
  `fw_tpa_time_constant` 1500 → 2000, `nav_fw_pos_z_ff` 10 → 30, `pitot_lpf_milli_hz` 350 → 3000; ranges: `tpa_rate` max
  100 → 200, `osd_snr_alarm` max 99 → 30. New table values: ICM45686 (acc), QMC5883P (mag), MS5525 (pitot), SMARTPORT as a
  voltage/current meter source.
- **MSP RC override**: `USE_MSP_RC_OVERRIDE` is commented out in 8.0.1 `target/common.h` (so the MSP RC OVERRIDE mode and
  `msp_override_channels` need a custom build). 9.1.0 enables it for all targets.
- **Programming framework**: operations 0–54 and flight operands 0–45 have the same numbers in both versions. 9.1 adds
  operation 55 `Set Gimbal Sensitivity`, 56 `Override Minimum Ground Speed`, and flight operands 46–49 (minimum ground speed,
  horizontal wind speed, wind direction, relative wind offset). Configurator 9.1 adds a **JavaScript Programming** tab that
  transpiles JavaScript into logic conditions (`docs/javascript_programming/`).
- **Configurator 9.1**: automatic `diff all` backup before flashing and a restore with migration of renamed settings across
  majors (`docs/Backup and Restore.md`, 9.1 docs only). LED strip presets, and Firmware Flasher backup/restore buttons.
- **MSP2 additions** (`navigation.h`): set active WP index and set cruise heading from a GCS/companion.
- **Targets**: 192 → 248 target directories. F411 is still supported in both (17 targets); AT32F43x 7 → 14; H743 31 → 51.
  `USE_DRONECAN` is defined in three 9.1 H7 targets, but no DroneCAN driver exists in the tree, so I treat CAN as not
  supported.
- **Not changed**: adjustments (`rc_adjustments.h` function list identical), mode ids (`fc_msp_box.c`), serial function bits
  (`io/serial.h`), arming flags, `smix` inputs (9.1 adds an internal `INPUT_MIXER_SWITCH_HELPER` = 60).

Build-size gating that the course never mentions (`target/common.h`, both versions): on MCUs with ≤ 512 KB flash (F411, F722)
`USE_GEOZONE`, `USE_VTX_FFPV`, SmartPort master and HoTT are left out. F411 also gets `MAX_MIXER_PROFILE_COUNT 1`, so no VTOL.
CLI help texts are skipped there too. So **geozones need F405/F7x5/H7/AT32 (> 512 KB)**, and VTOL needs anything but F411.

---

## 2. Commands and Configurator

### 2.1 CLI commands (8.0.1): all 61

Source: `cmdTable[]` in `src/main/fc/cli.c` at 8.0.1. Brackets show the `#ifdef` a command depends on. For coverage I
grepped every course file for the command written as a command (in backticks or at the start of a line) and checked each hit
by hand.

| # | Command | What it does (one line) | Course | Pri |
|---|---|---|---|---|
| 1 | `adjrange` | in-flight adjustment ranges `<idx 0–19> <slot 0–3> <range ch> <start> <end> <function> <adj ch>` | ✗ (INAV) | B |
| 2 | `assert` | show stored assert info [USE_ASSERT] | ✗ | C |
| 3 | `aux` | mode ranges `aux <idx> <permanentId> <aux ch> <start> <end>` | ✓ inav-setup-scratch (ids table) | A |
| 4 | `batch` | `batch start`/`end` — apply a pasted block [USE_CLI_BATCH] | ~ inav-setup-scratch ("от `batch start` до `save`") | B |
| 5 | `beeper` | `list`, `[-]name` — buzzer conditions [BEEPER or USE_DSHOT] | ✗ | B |
| 6 | `bind_rx` | bind **SRXL2** receiver only [USE_SERIALRX_SRXL2] (not CRSF, unlike Betaflight) | ✗ | C |
| 7 | `bootlog` | boot events [USE_BOOTLOG] | ✗ | C |
| 8 | `color` | LED palette `color <i> <h>,<s>,<v>` [USE_LED_STRIP] | ✗ | B |
| 9 | `mode_color` | LED colour per mode/special function `mode_color <mode> <fn> <colour>` [USE_LED_STRIP] | ✗ | C |
| 10 | `cli_delay` | delay in ms between CLI lines | ✗ | C |
| 11 | `defaults` | reset to defaults and reboot (`defaults noreboot`) | ✗ | A |
| 12 | `dfu` | reboot to DFU bootloader | ✗ | B |
| 13 | `diff` | changes from default; scopes `master\|battery_profile\|control_profile\|mixer_profile\|rates\|all`, flag `showdefaults` | ✓ inav-setup-scratch (`diff all` only; that plain `diff` = **master only**, without any profile, is not said. Correction 2026-11-18: wrong — plain `diff` prints master plus the active control, mixer and battery profile (cli.c `printConfig`, `else` branch of `if (dumpMask & DUMP_ALL)`, same in 8.0.1 and 9.1.0); only the non-active profiles are missing; see docs/reviews/factcheck/theory-wave3.md) | A |
| 14 | `dump` | full config, same scopes | ✗ | B |
| 15 | `eleres_bind` | bind EleRes RX [USE_RX_ELERES] | ✗ | C |
| 16 | `exit` | leave CLI and reboot | ✗ | B |
| 17 | `feature` | `list`, `[-]name`; 23 features (§2.3) | ~ (`feature FW_LAUNCH`, `FW_AUTOTRIM` used; list never shown) | A |
| 18 | `blackbox` | `list`, `[-]field` — which Blackbox field groups are logged [USE_BLACKBOX] | ✗ | B |
| 19 | `flash_erase` | erase log flash [USE_FLASHFS] | ✗ | B |
| 20 | `flash_info` | flash size/usage [USE_FLASHFS] | ✗ | B |
| 21 | `flash_read` | raw read [USE_FLASH_TOOLS] | ✗ | C |
| 22 | `flash_write` | raw write [USE_FLASH_TOOLS] | ✗ | C |
| 23 | `fwapproach` | FW autoland approach per safehome/WP `fwapproach <idx> <approach alt> <land alt> <direction> <hdg1> <hdg2> <sealevel>` [USE_FW_AUTOLAND] | ✗ | B |
| 24 | `get` | read settings by substring | ✓ inav-setup-wing | A |
| 25 | `geozone` | zones `geozone <id> <shape> <type> <minalt> <maxalt> <sealevel> <action> <vertices>`, `geozone vertex …`, `reset` [USE_GEOZONE] | ✗ | B |
| 26 | `gpspassthrough` | USB ↔ GPS UART bridge (u-center) [USE_GPS] | ✗ (INAV) | B |
| 27 | `gpssats` | per-satellite table (u-blox) [USE_GPS] | ✗ | B |
| 28 | `help` | list commands | ✗ | B |
| 29 | `led` | LED layout `led <i> <x>,<y>:<dirs>:<functions+overlays>:<colour>` (up to 128 LEDs) [USE_LED_STRIP] | ✗ | B |
| 30 | `ledpinpwm` | raw PWM 0–100 % on the LED pin (with `led_pin_pwm_mode`) [USE_LED_STRIP] | ✗ | C |
| 31 | `map` | RC channel order (`map AETR`) | ✓ inav-setup-scratch | A |
| 32 | `memory` | memory usage | ✗ | C |
| 33 | `mmix` | motor mixer rows `mmix <i> <thr> <roll> <pitch> <yaw>`, `reset`; throttle −1…−2 = VTOL tricks | ✓ inav-setup-scratch, inav-setup-wing | A |
| 34 | `motor` | get/set one motor output | ✗ | B |
| 35 | `msc` | reboot as USB mass storage [USE_USB_MSC] | ✗ | B |
| 36 | `play_sound` | play beeper sequence | ✗ | C |
| 37 | `control_profile` | select control (PID+rates) profile 1–3 | ✗ | A |
| 38 | `mixer_profile` | select mixer profile 1–2 (VTOL) | ~ inav-setup-wing (seen in `diff all`) | A |
| 39 | `battery_profile` | select battery profile 1–3 | ✗ | B |
| 40 | `resource` | **view only** — which pin is used by what (INAV cannot reassign pins from the CLI) | ✗ | B |
| 41 | `rxrange` | per-channel input scaling `rxrange <ch> <min> <max>` | ~ inav-setup-scratch (named in the step table) | B |
| 42 | `safehome` | `safehome <n> <enabled> <lat×1e7> <lon×1e7>`, `reset` [USE_SAFE_HOME] | ✗ (concept ✓, command ✗) | A |
| 43 | `save` | save and reboot | ✓ | A |
| 44 | `serial` | `serial <id> <function mask> <msp baud> <gps baud> <telemetry baud> <peripheral baud>` | ✓ inav-setup-scratch (bit values for 5 functions) | A |
| 45 | `serialpassthrough` | USB ↔ any UART `<id> [baud] [mode] [options]` (flash ELRS RX, configure GPS/VTX) [USE_SERIAL_PASSTHROUGH] | ✗ (INAV) | B |
| 46 | `servo` | endpoints `servo <n> <min> <max> <middle> <rate −125…125>` | ✓ inav-setup-wing | A |
| 47 | `logic` | logic condition `<rule> <enabled> <activator> <op> <A type> <A> <B type> <B> <flags>`, `reset` [USE_PROGRAMMING_FRAMEWORK] | ✓ inav-ipf (syntax; operation/operand numbers withheld) | A |
| 48 | `gvar` | global variable `<gvar> <default> <min> <max>`, `reset` | ~ inav-ipf (named, syntax absent) | B |
| 49 | `pid` | programming PID `<#> <enabled> <sp type> <sp value> <meas type> <meas value> <P> <I> <D> <FF>` | ✗ (concept named in inav-ipf) | B |
| 50 | `osd_custom_elements` | custom OSD element `<#> <3 × type,value> <visibility type,value> "<text>"` (8 elements) | ✗ | B |
| 51 | `set` | change a setting | ✓ | A |
| 52 | `smix` | servo mixer `<rule> <servo> <input> <rate −1000…1000> <speed> <logic condition id \| −1>`, `reset` | ✓ inav-setup-wing | A |
| 53 | `sd_info` | SD card state [USE_SDCARD] | ✗ | C |
| 54 | `showdebug` | debug fields | ✗ | C |
| 55 | `status` | MCU, sensors, CPU, arming disable flags | ✓ inav-intro, inav-setup-scratch | A |
| 56 | `tasks` | per-task rate/load | ✗ | B |
| 57 | `temp_sensor` | DS18B20/LM75 temperature sensor list [USE_TEMPERATURE_SENSOR] | ✗ | C |
| 58 | `version` | firmware, target, date, git rev | ✗ (INAV) | A |
| 59 | `wp` | waypoints `wp <n> <action> <lat> <lon> <alt> <p1> <p2> <p3> <flag>`, `load`/`save`/`reset` | ✓ inav-missions | A |
| 60 | `osd_layout` | element position per layout `osd_layout <layout 0–3> <item> <col> <row> <V\|H>` [USE_OSD] | ✗ | B |
| 61 | `timer_output_mode` | force a timer to `AUTO\|MOTORS\|SERVOS\|LED` | ✓ inav-setup-wing (LED value not mentioned) | A |
| 9.1 | `bind_msp_rx` | bind an MSP receiver (mLRS) on `<port>` | ✗ | C |

**Totals (8.0.1): 61 commands, ✓ 14, ~ 5, ✗ 42.** By priority: **A 20** (✓ 14, ~ 2: `feature` and `mixer_profile`, ✗ 4:
`defaults`, `version`, `safehome`, `control_profile`), **B 27** (✓ 0, ~ 3: `batch`, `rxrange` and `gvar`, ✗ 24), **C 14** (all ✗).

Two INAV-specific traps are missing from the course:
1. **`diff` without arguments prints only `master`.** (Correction 2026-11-18: wrong — plain `diff` prints master plus the active control, mixer and battery profile (cli.c `printConfig`, `else` branch of `if (dumpMask & DUMP_ALL)`, same in 8.0.1 and 9.1.0); only the non-active profiles are missing; see docs/reviews/factcheck/theory-wave3.md.) `cliDiff` starts with `dumpMask = DUMP_MASTER`, so no
   `control_profile`, `mixer_profile` or `battery_profile` blocks are printed. A backup made with `diff` loses the PIDs, the
   rates, `platform_type`, `mmix`/`smix` (these sit in the mixer profile) and the battery settings. `diff all` prints every profile:
   for each one it emits `control_profile N` / `mixer_profile N` / `battery_profile N` (1-based) followed by that profile's
   lines, and at the end it re-selects the active profiles.
2. **`resource` cannot remap pins in INAV.** It only lists them (`cliResource` prints the IO table). Moving a function to
   another pad goes through `timer_output_mode` and the Mixer/Outputs tab, or through a custom target. A student who has
   learned Betaflight's `resource MOTOR 1 B00` will look for a command that does not exist.

### 2.2 Configurator tabs (8.0.1; 9.1 additions marked)

Names come from `locale/en/messages.json`. The first tab is labelled **Status** (internally `setup`), and **Welcome** is the
landing page (internally `landing`, not autoland).

| Tab | What a student must do there | Course | Pri |
|---|---|---|---|
| Firmware Flasher (9.1: + Backup/Restore Config, auto-backup) | pick target, Full chip erase, flash; 9.1 auto-backup/migration | ✓ inav-setup-scratch | A |
| Status | attitude model, sensor status, arming flags, GPS/battery summary | ~ (called "Setup"; arming reasons listed in inav-intro) | A |
| Calibration | acc 6-position, compass, opflow scale, ACC zero/gain | ~ inav-setup-scratch ("Setup / Calibration") | A |
| Alignment Tool | board and **compass** alignment with a 3D preview (custom `align_mag_roll/pitch/yaw`) | ✗ | A |
| Ports | UART functions and bauds | ✓ inav-setup-scratch | A |
| Configuration | features, platform, GPS protocol, VTX, battery/current meters, receiver type, failsafe-related, gimbal channels (8+) | ~ | A |
| Mixer | platform, presets, motor/servo rules, Motor Mixer Wizard, **timer → output map**, mixer profiles | ✓ inav-setup-scratch/wing (single profile only) | A |
| Outputs | ESC protocol, servo endpoints/reverse/rate, motor test, servo refresh rate | ✓ inav-setup-scratch/wing | A |
| Receiver (+ MSP receiver window) | RX type/provider, channel map, RSSI source, RC smoothing | ✓ inav-setup-scratch | A |
| Modes | `aux` ranges, AND/OR logic (`mode_range_logic_operator`) | ✓ (AND/OR not mentioned) | A |
| Adjustments | `adjrange` slots | ✗ | B |
| Failsafe | procedure, delays, throttle, FW angles, min distance, mission delay | ✓ inav-setup-scratch/wing | A |
| GPS | provider, SBAS, Galileo/BeiDou/GLONASS, rate, dyn model, map, satellites | ~ (protocol/baud only) | A |
| Tuning (PIDs, Rates/Expo, Filtering, Other filters, Mechanics, **Ez Tune**) | PID/FF per axis, level, nav PIDs (mag/altitude/GPS), rates, filters | ~ (EZ Tune named; MC PIDs/rates in INAV units not explained) | A |
| Advanced Tuning | nav general/MC/FW settings, launch, RTH, landing, braking, autoland, geozones | ~ (most RTH/launch values named in CLI form) | A |
| Programming (Logic conditions, Global variables, Programming PID, status) | IPF | ✓ inav-ipf | A |
| JavaScript Programming (9.1) | JS → logic conditions | ✗ | B |
| OSD | video system, element layout, 4 layouts, alarms, custom elements, stats, font upload | ~ (video system and a minimum element list) | A |
| LED Strip (9.1: + presets) | layout, functions, colours | ✗ | B |
| Mission Control | waypoints, multi-mission, **safehomes**, **FW approach**, **geozones** editor, elevation | ✓ inav-missions (waypoints only) | A |
| Sensors | live gyro/acc/mag/baro/rangefinder/pitot graphs | ✗ | B |
| Tethered Logging / Blackbox | serial log to PC / onboard flash/SD, rates, erase, MSC | ~ ("Blackbox включён") | B |
| CLI | — | ✓ | A |
| SITL | start SITL, simulator profiles (RealFlight/X-Plane), serial-to-UART | ✓ inav-setup-scratch/wing | A |
| Search, Debug trace, Options, Documentation & Support | settings search, debug log, app options | ✗ | C |

**Totals: 28 tabs/windows in 8.0.1 (counting Tethered Logging and Blackbox separately, and the four utility pages), plus 1 new
in 9.1.** A 19: ✓ 11, ~ 7, ✗ 1 (Alignment Tool). B 5: ✗ 3 (Adjustments, LED Strip, Sensors), ~ 2 (Tethered Logging,
Blackbox). C 4: ✗. The 9.1 JavaScript Programming tab (B) is ✗.

### 2.3 Features (`feature list`, `cli.c featureNames[]`)
THR_VBAT_COMP, VBAT, TX_PROF_SEL, BAT_PROF_AUTOSWITCH, GEOZONE, SOFTSERIAL, GPS, RPM_FILTERS, TELEMETRY, CURRENT_METER,
REVERSIBLE_MOTORS, RSSI_ADC, LED_STRIP, DASHBOARD, BLACKBOX, TRANSPONDER, AIRMODE, SUPEREXPO, VTX, PWM_OUTPUT_ENABLE, OSD,
FW_LAUNCH, FW_AUTOTRIM (23). The course names FW_LAUNCH and FW_AUTOTRIM. Missing and worth one line each:
**PWM_OUTPUT_ENABLE** (without it, no output reaches motors or servos), **GEOZONE**, **BAT_PROF_AUTOSWITCH**, **TX_PROF_SEL**
(enables stick selection of profiles, §4.5), **THR_VBAT_COMP**, **RPM_FILTERS**, **REVERSIBLE_MOTORS**, **TELEMETRY**,
**SOFTSERIAL**, **AIRMODE**.

### 2.4 Modes (`aux` permanent ids, `fc_msp_box.c`)
The course gives 6 of the 60 ids (ARM 0, ANGLE 1, NAV ALTHOLD 3, NAV RTH 10, NAV POSHOLD 11, FAILSAFE 27). The full table,
unchanged in 9.1, is: 0 ARM, 1 ANGLE, 2 HORIZON, 3 NAV ALTHOLD, 5 HEADING HOLD, 6 HEADFREE, 7 HEADADJ, 8 CAMSTAB, 10 NAV RTH,
11 NAV POSHOLD, 12 MANUAL, 13 BEEPER, 15 LEDS OFF, 16 LIGHTS, 19 OSD OFF, 20 TELEMETRY, 21 AUTO TUNE, 26 BLACKBOX, 27 FAILSAFE,
28 NAV WP, 29 AIR MODE, 30 HOME RESET, 31 GCS NAV, 32 FPV ANGLE MIX, 33 SURFACE, 34 FLAPERON, 35 TURN ASSIST, 36 NAV LAUNCH,
37 SERVO AUTOTRIM, 39–41 CAMERA CONTROL 1–3, 42–44 OSD ALT 1–3, 45 NAV COURSE HOLD, 46 MC BRAKING, 47 USER1, 48 USER2,
49 LOITER CHANGE, 50 MSP RC OVERRIDE, 51 PREARM, 52 TURTLE, 53 NAV CRUISE, 54 AUTO LEVEL TRIM, 55 WP PLANNER, 56 SOARING,
57 USER3, 58 USER4, 59 MISSION CHANGE, 60 BEEPER MUTE, 61 MULTI FUNCTION, 62 MIXER PROFILE 2, 63 MIXER TRANSITION,
64 ANGLE HOLD, 65 GIMBAL LEVEL TILT, 66 GIMBAL LEVEL ROLL, 67 GIMBAL CENTER, 68 GIMBAL HEADTRACKER. Some modes appear only under
a condition: SERVO AUTOTRIM only without `feature FW_AUTOTRIM`, MSP RC OVERRIDE only with `USE_MSP_RC_OVERRIDE`, FLAPERON only with
`has_flaps`.

---

## 3. Settings (8.0.1): 665

Source: `src/main/fc/settings.yaml` at 8.0.1 (9.1.0: 677). About a fifth carry a `condition:` (`USE_*`) and are missing on
targets built without that feature.

**Totals: 665 settings. 103 are named in INAV-track files, and 156 anywhere in the course.** The "anywhere" count includes
Betaflight modules that use the same names (`vtx_power`, `deadband`, `motor_poles`…) in a Betaflight context, so it overstates
INAV coverage. As in the Betaflight audit, "named" is only an upper bound on "explained". In the INAV track a named setting
almost always comes with its meaning and its default.

| Group (PGs merged) | Settings | Named in INAV track | Named anywhere |
|---|---|---|---|
| 1 Gyro, filters, IMU, sensors (acc/mag/baro/pitot/rangefinder/opflow), alignment, RPM filter | 85 | 10 | 15 |
| 2 PID profile (MC/FW PIDs, nav PIDs, iterm, D-boost, antigravity, Smith predictor), autotune, EZ Tune | 103 | 4 | 5 |
| 3 Rates (control rate profile) | 23 | 4 | 11 |
| 4 RC input, receiver, RC controls | 28 | 6 | 12 |
| 5 Motors, mixer profile, servos, 3D | 23 | 4 | 13 |
| 6 Battery meters, battery profiles, power limits | 42 | 20 | 21 |
| 7 Failsafe, arming, failsafe lights | 20 | 9 | 11 |
| 8 GPS | 11 | 2 | 6 |
| 9 Position estimator | 23 | 7 | 9 |
| 10 Navigation (general, MC, FW, RTH, WP, launch, safehome) | 98 | 36 | 37 |
| 11 FW autoland | 7 | 0 | 0 |
| 12 Geozones | 7 | 0 | 0 |
| 13 OSD (incl. DJI legacy, OSD joystick, stats) | 117 | 1 | 7 |
| 14 VTX | 12 | 0 | 5 |
| 15 Telemetry, serial, ESC sensor, SmartPort master | 31 | 0 | 0 |
| 16 Blackbox, log, system, time | 15 | 0 | 4 |
| 17 LED pin, beeper, PINIO | 8 | 0 | 0 |
| 18 Gimbal, headtracker | 12 | 0 | 0 |

The rest of this section lists every **uncovered A/B** setting with its meaning and its 8.0.1 default (9.1 changes marked). I
summarise hardware-only and very fine-grained settings (`gyro_zero_*`, `acczero_*`, `maggain_*`, `osd_hud_*`, `sim_*`
SMS telemetry, `frsky_*`) instead of listing them.

### 3.1 Gyro, filters, IMU, sensors (85 / named 10)
Covered: `gyro_main_lpf_hz` = 60, `dynamic_gyro_notch_enabled` = ON, `rpm_gyro_filter_enabled`, `align_mag`, `align_board_yaw`,
`mag_calibration_time` = 30, `small_angle` = 25, the `*_hardware` selectors.
Uncovered A/B:
- `align_board_roll`/`align_board_pitch` = 0 (decidegrees, −1800…3600): a tilted FC, a wing with an angled mount. **A**
- `align_mag_roll`/`_pitch`/`_yaw` = 0 (decidegrees): custom compass alignment, which is what the Alignment Tool writes. The
  `align_mag` presets (CW90FLIP…) do not cover a GPS mast mounted at 45°. **A**
- `mag_declination` = 0 (only with `inav_auto_mag_decl = OFF`), `mag_to_use` (dual mag). **B**
- `gyro_filter_mode` = STATIC (OFF/STATIC/DYNAMIC/ADAPTIVE), `gyro_dyn_lpf_min_hz`/`_max_hz` = 200/500,
  `gyro_adaptive_filter_*` (8.0 adaptive LPF), `dynamic_gyro_notch_q` = 120, `_min_hz` = 50, `_mode` = 2D (2D/3D),
  `setpoint_kalman_enabled` = ON, `setpoint_kalman_q` = 100, `gyro_anti_aliasing_lpf_hz` = 250. **B** (filter chain for MC
  tuning)
- `rpm_gyro_harmonics` = 1, `rpm_gyro_min_hz` = 100, `rpm_gyro_q` = 500; **RPM data come from serial ESC telemetry, not
  bidirectional DShot** (§6.11). **B**
- `looptime` = 500 µs (2 kHz). This is the INAV equivalent of Betaflight's PID loop rate, and it is named only outside the
  track. **B**
- `acc_lpf_hz` = 15, `acc_notch_hz` = 0. `ahrs_dcm_kp` = 2000, `ahrs_dcm_kp_mag` = 2000, `ahrs_acc_ignore_rate` = 15 °/s,
  `ahrs_inertia_comp_method` = ADAPTIVE, `ahrs_gps_yaw_windcomp` = ON. **B** for the `ahrs_*` set: "horizon drifts in long turns"
  on wings.
- `rangefinder_hardware` = NONE (SRF10, VL53L0X/L1X, MSP, BENEWAKE, US42, TOF10120_I2C, TERARANGER_EVO, USD1_V0, NRA),
  `rangefinder_median_filter` = OFF; `opflow_hardware` = NONE (CXOF/MSP), `opflow_scale` = 10.5, `align_opflow` = CW0FLIP. These
  are named in `est-alt-sources`, and their setup is ✗. **B**
- `pitot_hardware` = NONE (AUTO, MS4525, ADC, VIRTUAL, MSP, DLVR-L10D; 9.1 + MS5525), `pitot_scale` = 1.0,
  `pitot_lpf_milli_hz` = 350 (9.1: 3000). **B**
- `baro_cal_tolerance` = 150; 9.1 `baro_temp_correction`, `acc_temp_correction`. **C**

### 3.2 PID profile, autotune, EZ Tune (103 / named 4)
Covered: `fw_ff_roll`/`fw_ff_pitch` (autotune), `fw_level_pitch_trim`, `ez_enabled`. **This is the largest gap.** No
multirotor PID, nav PID or filter in the PID group is named, and the course sends INAV MC tuning to the Betaflight modules,
whose units and defaults differ.
- MC rate PIDs: `mc_p_roll`/`mc_i_roll`/`mc_d_roll`/`mc_cd_roll` = 40/30/23/60, pitch 40/30/23/60, yaw 85/45/0/60
  (`cd` = control derivative, INAV's feedforward); level `mc_p_level`/`mc_i_level`/`mc_d_level` = 20/15/75. **A**
- FW PIDs: `fw_p_roll`/`fw_i_roll`/`fw_d_roll`/`fw_ff_roll` = 5/7/0/50, pitch 5/7/0/50, yaw 6/10/0/60, level 20/5/75. **A**
- `max_angle_inclination_rll`/`_pit` = 450 (decidegrees, 45°): the Angle-mode limit. **A**
- `dterm_lpf_hz` = 110, `dterm_lpf_type` = PT2, `mc_cd_lpf_hz` = 30, `yaw_lpf_hz` = 0. **B**
- `mc_iterm_relax` = RP, `mc_iterm_relax_cutoff` = 15, `iterm_windup` = 50, `pid_iterm_limit_percent` = 33,
  `antigravity_gain` = 1 (= off), `antigravity_accelerator` = 1, `d_boost_min`/`_max` = 0.5/1.25, `pid_type` = AUTO. **B**
- Nav PIDs (multirotor): `nav_mc_pos_z_p` = 50, `nav_mc_vel_z_p/i/d` = 100/50/10, `nav_mc_pos_xy_p` = 65,
  `nav_mc_vel_xy_p/i/d/ff` = 40/15/100/40, `nav_mc_heading_p` = 60. These are what you change when ALTHOLD bobs or POSHOLD
  overshoots. **A** for `nav_mc_vel_z_*` and `nav_mc_vel_xy_*`, B for the rest.
- Nav PIDs (wing): `nav_fw_pos_z_p/i/d/ff` = 30/5/10/10 (9.1 ff 30), `nav_fw_alt_control_response` = 40,
  `nav_fw_pos_xy_p/i/d` = 75/5/8, `nav_fw_pos_hdg_*`. **B**
- Wing extras: `fw_reference_airspeed` = 1500 cm/s, `fw_turn_assist_yaw_gain`/`_pitch_gain` = 1, `fw_level_pitch_gain` = 5,
  `fw_iterm_lock_*`, `fw_yaw_iterm_freeze_bank_angle` = 0. **B**
- `fw_autotune_rate_adjustment` = AUTO (FIXED/LIMIT/AUTO; rates are not changed when tuning in ANGLE),
  `fw_autotune_min_stick` = 50 %, `fw_autotune_max_rate_deflection` = 90. **B**. These explain why autotune "did nothing" in ANGLE.
- EZ Tune: `ez_filter_hz` = 110, `ez_axis_ratio` = 110, `ez_response`/`ez_damping`/`ez_stability`/`ez_aggressiveness`/
  `ez_rate`/`ez_expo` = 100, `ez_snappiness` = 0. Only `ez_enabled` is named. **B**
- `smith_predictor_*` (delay 0 = off), `heading_hold_rate_limit` = 90, `rate_accel_limit_*`. **C**

### 3.3 Rates (23 / named 4)
Covered: `roll_rate`/`pitch_rate` (named as the wing's throw reducer), `manual_roll_rate`/`manual_pitch_rate`.
- **Units**: `roll_rate`/`pitch_rate`/`yaw_rate` = 20 means **10 °/s per unit, so 200 °/s**. The course never says this. **A**
- `rc_expo` = 70, `rc_yaw_expo` = 20, `manual_rc_expo` = 35, `manual_rc_yaw_expo` = 20, `manual_yaw_rate` = 100 (%). **A**
- `thr_mid` = 50, `thr_expo` = 0. **B**
- `tpa_rate` = 0, `tpa_breakpoint` = 1500, `tpa_on_yaw` = OFF, `fw_tpa_time_constant` = 1500 ms (9.1: 2000). On wings TPA
  attenuates P, I, D and FF together. 9.1 adds `apa_pow` (airspeed-based attenuation) and `tpa_pitch_compensation`. **B**
- `rate_dynamics_*` (center/end sensitivity, correction, weight). **C**
- 9.1: this whole group is part of the **control profile** (`PG_CONTROL_PROFILES`).

### 3.4 RC input, receiver, RC controls (28 / named 6)
Covered: `receiver_type`, `serialrx_provider`, `min_check` = 1100, `max_check` = 1900, `rx_min_usec` = 885, `rx_max_usec` = 2115.
- `serialrx_inverted` = OFF, `serialrx_halfduplex` = AUTO: SBUS on F4, FPort, SmartPort. Named only in Betaflight modules. **A**
- `rssi_source` = AUTO (NONE/AUTO/ADC/CHANNEL/PROTOCOL/MSP), `rssi_channel` = 0, `rssi_min`/`rssi_max` = 0/100. **B**
- `rc_filter_auto` = ON, `rc_filter_lpf_hz` = 50, `rc_filter_smoothing_factor` = 30: INAV's RC smoothing. **B**
- `deadband` = 2, `yaw_deadband` = 2, `pos_hold_deadband` = 10, `alt_hold_deadband` = 50 µs: why stick input does not
  move the aircraft in POSHOLD/ALTHOLD. **B**
- `airmode_type` = STICK_CENTER (THROTTLE_THRESHOLD, STICK_CENTER_ONCE), `airmode_throttle_threshold` = 1150. MixerProfile.md
  says THROTTLE_THRESHOLD must not be used on VTOL. **B**
- `mode_range_logic_operator` = OR. **B**
- `msp_override_channels` = 0: needs `USE_MSP_RC_OVERRIDE`, which is off in 8.0.1 and on in 9.1 (§1.3). **B**
- `srxl2_*`, `spektrum_sat_bind`, `sbus_sync_interval` = 3000. **C**

### 3.5 Motors, mixer profile, servos, 3D (23 / named 4)
Covered: `platform_type`, `motor_pwm_protocol` = ONESHOT125, `motor_direction_inverted`, `motorstop_on_low` = ON.
- `has_flaps` = OFF (it unlocks the FLAPERON mode) and `flaperon_throw_offset` = 200 µs (passed to `smix` input 14). **B**
- `mixer_automated_switch` = OFF, `mixer_switch_trans_timer` = 0 (ds), `mixer_pid_profile_linking` = OFF
  (9.1: `mixer_control_profile_linking`), `tailsitter_orientation_offset` = OFF, `model_preview_type`; 9.1
  `transition_pid_mmix_multiplier_*` = 1000. These are the VTOL settings. **A** for VTOL builds
- `servo_pwm_rate` = 50 Hz (50–498), `servo_center_pulse` = 1500, `servo_lpf_hz` = 20, `servo_protocol` = PWM (SBUS/SBUS_PWM:
  servo data out of a UART with serial function `SERVO_SERIAL` 4194304), `servo_autotrim_rotation_limit` = 15,
  `tri_unarmed_servo` = ON. In the INAV track all of these are ✗; `servo_pwm_rate` and `servo_lpf_hz` appear in the
  `bf-servos-pwm` comparison table. **B**
- `motor_pwm_rate` = 16000 (applies to OneShot/Multishot/brushed, `ESC and servo outputs.md`), `min_command` = 1000,
  `motor_poles` = 14 (RPM from ESC telemetry). **B**
- `3d_deadband_low`/`_high`/`3d_neutral` = 1406/1514/1460, `3d_deadband_throttle` = 50 + `feature REVERSIBLE_MOTORS`
  (rovers, boats). **C**

### 3.6 Battery meters, battery profiles, power limits (42 / named 20)
Covered in depth: `vbat_scale` (default 1100, `sensors/battery.h`), `current_meter_scale` (400), `current_meter_offset`,
`current_meter_type`, `bat_cells`, `vbat_min/warning/max_cell_voltage` = 330/350/420, `battery_capacity*`,
`throttle_idle` = 8, `failsafe_throttle`, `nav_mc_hover_thr`, `nav_fw_*_thr`, `nav_fw_launch_thr`.
- `bat_cells` = 0 means **auto-detect** using `vbat_cell_detect_voltage` = 425 (per-cell upper bound). This should be stated next to
  the explicit `set bat_cells = 4`. **B**
- `battery_capacity_unit` = MAH (MWH lets warnings use energy, which suits Li-ion), `bat_voltage_src` = RAW (SAG_COMP:
  sag-compensated voltage for alarms), `vbat_meter_type` = ADC (ESC; 9.1 + SMARTPORT). **B**
- `cruise_power`, `idle_power` (0.01 W), `rth_energy_margin` = 5 %: remaining time and distance, and the "RTH home with x %
  left" estimate, all on the OSD. **B**
- `throttle_scale` = 1.0 (per battery profile), `turtle_mode_power_factor` = 55. **B/C**
- **Battery profiles**: 3 (`MAX_BATTERY_PROFILE_COUNT`). They hold cell voltages, capacity, `throttle_idle`, `throttle_scale`,
  `failsafe_throttle`, the hover/cruise/launch throttles and `controlrate_profile` (9.1: `use_control_profile`). They switch
  automatically by cell count with `feature BAT_PROF_AUTOSWITCH`. The course uses all these settings but never says they are
  per profile. **B**
- `limit_cont_current`, `limit_burst_current`, `limit_burst_current_time`, `limit_burst_current_falldown_time`,
  `limit_cont_power`, `limit_burst_power`, … (all 0 = off; units dA, dW, ds) and `limit_pi_p`/`limit_pi_i` = 100/100,
  `limit_attn_filter_cutoff` = 1.2 [USE_POWER_LIMITS]. The 9.1 `Battery.md` documents them with different defaults
  (`limit_pi_i` 15, cutoff 50 Hz) and ranges (0–2000) than both YAMLs (`limit_pi_i` 100, cutoff 1.2, max 4000/40000). This is
  doc drift, and the YAML wins. **B**

### 3.7 Failsafe, arming (20 / named 9)
Covered: `failsafe_delay` = 5, `failsafe_procedure` = LAND, `failsafe_throttle_low_delay` = 0, `failsafe_stick_threshold` = 50,
`failsafe_fw_*`, `failsafe_min_distance*`, `failsafe_throttle`.
- `failsafe_recovery_delay` = 5 (0.5 s), `failsafe_off_delay` = 200 (20 s, the LAND descent time limit before disarm). **A**
- `failsafe_mission_delay` = 0 s (−1 = never start the failsafe procedure during a WP mission, which lets a mission run out
  of RC range). **B**
- `failsafe_gps_fix_estimation_delay` = 7 s. **B**
- `disarm_always` = ON, `switch_disarm_delay` = 250 ms, `prearm_timeout` = 10000 ms (PREARM mode 51), `fixed_wing_auto_arm` = OFF
  (arm on throttle; needs motorstop and no arm switch). **B**
- `failsafe_lights` = ON (+ flash period/on time). **C**

### 3.8 GPS (11 / named 2)
Covered: `gps_provider`, `gps_min_sats` = 6.
- `gps_ublox_use_galileo` = OFF (**9.1: ON**), `gps_ublox_use_beidou` = OFF (**9.1: ON**), `gps_ublox_use_glonass` = OFF,
  `gps_sbas_mode` = NONE, `gps_ublox_nav_hz` = 10 (**9.1: 8**), `gps_dyn_model` = AIR_2G, `gps_auto_config` = ON,
  `gps_auto_baud` = ON, `gps_auto_baud_max_supported` = 230400 (M8 up to 460800, M10 up to 921600, per the description). This is
  the whole answer to "GPS takes forever / M10 setup", and none of it is in the INAV track. **A**

### 3.9 Position estimator (23 / named 7)
Covered: `inav_auto_mag_decl`, `inav_allow_dead_reckoning`, `inav_allow_gps_fix_estimation`, `inav_w_xy_gps_p`/`_v`,
`inav_w_z_baro_p`, `inav_max_eph_epv`.
- `inav_default_alt_sensor` = GPS (BARO, GPS_ONLY, BARO_ONLY): which altitude source wins when baro and GPS disagree. This is
  also the answer to "INAV without a barometer" (§7.3 E8). **A**
- `inav_reset_home` = FIRST_ARM (NEVER, EACH_ARM), `inav_reset_altitude` = FIRST_ARM. These govern a re-arm after a mid-air
  disarm. **B**
- `inav_w_z_baro_v` = 0.1, `inav_w_z_gps_p` = 0.2, `inav_w_z_gps_v` = 0.1 (all three **0.35 in 9.1**), `inav_w_z_res_v`,
  `inav_w_xy_res_v` = 0.5, `inav_w_acc_bias` = 0.01, `inav_baro_epv` = 100, `inav_gravity_cal_tolerance` = 5. **B**
- `inav_max_surface_altitude` = 200 cm, `inav_w_z_surface_p`/`_v` = 3.5/6.1: rangefinder surface tracking. **B**

### 3.10 Navigation (98 / named 36): best-covered group
Covered: RTH altitude modes, linear descent, climb-first, landing, abort threshold, home altitude, `nav_min_rth_distance`, the
safehome settings, `nav_user_control_mode`, `nav_mc_althold_throttle`, `nav_wp_*` basics, `nav_extra_arming_safety`, the main
`nav_fw_*` launch, loiter and throttle values.
Uncovered A/B:
- `nav_rth_trackback_mode` = OFF (ON / FS), `nav_rth_trackback_distance` = 500 m: RTH retraces the flown path first. It is a
  popular INAV feature and is absent from the course. **A**
- `nav_position_timeout` = 5 s: GPS loss → emergency landing. `nav-resilience` says "~2 с" (§7.3). **A**
- `nav_rth_climb_ignore_emerg` = OFF, `nav_rth_climb_first_stage_mode` = AT_LEAST and `_altitude` = 0,
  `nav_rth_alt_control_override` = OFF, `nav_rth_tail_first` = OFF, `nav_rth_fs_landing_delay` = 0 s. **B**
- `nav_max_altitude` = 0 (off), `nav_mc_bank_angle` = 35°, `nav_mc_auto_climb_rate` = 500, `nav_mc_manual_climb_rate` = 200 cm/s,
  `nav_max_auto_speed` = 1000, `nav_manual_speed` = 750 cm/s. **A** for `nav_mc_bank_angle` and `nav_max_auto_speed` (the latter is
  the real upper bound of waypoint `p1` speed, §7.3 E1)
- Landing: `nav_disarm_on_landing` = ON, `nav_land_detect_sensitivity` = 5, `nav_landing_bump_detection` = OFF,
  `nav_land_minalt_vspd`/`_maxalt_vspd` = 50/200 cm/s, `nav_land_slowdown_minalt`/`_maxalt` = 500/2000 cm,
  `nav_auto_disarm_delay` = 1000 ms, `nav_mc_inverted_crash_detection` = 0. **B**
- Waypoints: `nav_wp_load_on_boot` = OFF, `nav_wp_enforce_altitude` = 0, `nav_wp_multi_mission_index` = 1 (1–9),
  `nav_mission_planner_reset` = ON (WP PLANNER mode), `nav_fw_wp_turn_smoothing` = OFF (ON / ON-CUT),
  `nav_fw_wp_tracking_accuracy` = 0, `nav_fw_wp_tracking_max_angle` = 60. **B**
- `nav_overrides_motor_stop` = ALL_NAV (OFF_ALWAYS, OFF, AUTO_ONLY). This explains why the motor spins at zero throttle in NAV
  modes. **B**
- `nav_max_terrain_follow_alt` = 100 cm (the SURFACE mode ceiling; 0–1000). **B**
- MC braking (`nav_mc_braking_*`, MC BRAKING mode), `nav_mc_pos_deceleration_time` = 120, `nav_mc_pos_expo` = 10. **C/B**
- `nav_cruise_yaw_rate` = 60, `nav_min_ground_speed` = 7 m/s (wing), `nav_use_fw_yaw_control` = OFF,
  `nav_fw_allow_manual_thr_increase` = OFF, `nav_fw_soaring_motor_stop` = OFF / `_pitch_deadband` = 5 (SOARING mode). **B**
- `fw_min_throttle_down_pitch` = 0 (decidegrees of automatic nose-down at zero throttle in ANGLE), `nav_fw_pitch2thr_smoothing` = 6,
  `nav_fw_pitch2thr_threshold` = 50, `nav_fw_auto_climb_rate` = 500, `nav_fw_manual_climb_rate` = 300. **B**
- Launch: `nav_fw_launch_detect_time` = 40 ms, `nav_fw_launch_spinup_time` = 100 ms, `nav_fw_launch_end_time` = 3000 ms,
  `nav_fw_launch_min_time` = 0, `nav_fw_launch_manual_throttle` = OFF, `nav_fw_launch_wiggle_to_wake_idle` = 0,
  `nav_fw_launch_land_abort_deadband` = 100. **B**

### 3.11 FW autoland (7 / 0)
`nav_fw_land_approach_length` = 35000 cm, `nav_fw_land_glide_alt` = 200 cm, `nav_fw_land_flare_alt` = 150 cm,
`nav_fw_land_glide_pitch` = 0°, `nav_fw_land_flare_pitch` = 8°, `nav_fw_land_final_approach_pitch2throttle_mod` = 100 %,
`nav_fw_land_max_tailwind` = 140 cm/s, plus the `fwapproach` slots (up to `MAX_SAFE_HOMES + 9` = 17: 8 safehome slots plus 9 for
waypoint missions). `inav-wing` gives only `nav_fw_land_dive_angle` = 2 and a pointer to `Fixed Wing Landing.md`. All **B**.

### 3.12 Geozones (7 / 0), new in INAV 8
`geozone_detection_distance` = 50000 cm, `geozone_avoid_altitude_range` = 5000, `geozone_safe_altitude_distance` = 1000,
`geozone_safehome_as_inclusive` = OFF, `geozone_safehome_zone_action` = NONE (AVOID/POS_HOLD/RTH), `geozone_mr_stop_distance` =
15000, `geozone_no_way_home_action` = RTH (EMRG_LAND); `feature GEOZONE`; up to 63 zones / 126 vertices; > 512 KB flash only.
All **B** (A for anyone flying near restricted airspace).

### 3.13 OSD (117 / named 1)
Covered: `osd_video_system`.
- `osd_rssi_alarm` = 20, `osd_link_quality_alarm` = 70, `osd_rssi_dbm_alarm` = 0, `osd_snr_alarm` = 4, `osd_time_alarm` = 10 min,
  `osd_alt_alarm` = 100 m, `osd_dist_alarm` = 1000 m, `osd_neg_alt_alarm` = 5 m, `osd_current_alarm` = 0,
  `osd_imu_temp_alarm_*`, `osd_esc_temp_alarm_*`, `osd_airspeed_alarm_*`. **B**
- `osd_units` = METRIC, `osd_crsf_lq_format` = TYPE1, `osd_main_voltage_decimals` = 1, `osd_stats_energy_unit` = MAH,
  `osd_home_position_arm_screen` = ON, `osd_arm_screen_display_time` = 1500. **B**
- HD: `osd_msp_displayport_fullframe_interval` = 10 ds, `osd_highlight_djis_missing_font_symbols` = ON,
  `enable_broken_o4_workaround` = OFF [USE_DJI_HD_OSD], `osd_row_shiftdown`. **B**
- Layouts: 4 layouts (OSD ALT 1–3 modes; `osd_failsafe_switch_layout` = OFF), `osd_layout` command, IPF op 32. **B**
- Artificial horizon and HUD: `osd_camera_uptilt` = 0, `osd_camera_fov_h`/`_v` = 135/85, `osd_ahi_*`, `osd_hud_*` (radar,
  homing, WP display), `osd_crosshairs_style`, sidebars. **C**
- Switch indicators `osd_switch_indicator_*` (4 named channel indicators). **C**
- `osd_pan_servo_*` (pan-servo home arrow correction; renamed in 9.1). **C**
- Stats: `stats` = OFF (odometer), `stats_total_time`/`_dist`/`_energy` (9.1 + `stats_flight_count`). **B**

### 3.14 VTX (12 / 0 in the INAV track)
`vtx_band` = 1, `vtx_channel` = 1, `vtx_power` = 1 (power **level index**, mW depends on the VTX), `vtx_low_power_disarm` = OFF
(ON / UNTIL_FIRST_ARM), `vtx_pit_mode_chan` = 1, `vtx_max_power_override` = 0, `vtx_frequency_group` = 5G8 (2G4, 1G3),
`vtx_halfduplex` = ON, `vtx_smartaudio_early_akk_workaround` = ON, `vtx_smartaudio_alternate_softserial_method` = ON,
`vtx_smartaudio_stopbits` = 2, `vtx_softserial_shortstop` = OFF. INAV has **no `vtxtable`** (built-in band tables;
SmartAudio, Tramp and MSP VTX). The `link-vtx` lesson is written for Betaflight tables. All **B**, `vtx_power` **A**.

### 3.15 Telemetry, serial, ESC sensor (31 / 0)
- `telemetry_inverted` = OFF, `telemetry_halfduplex` = ON (S.Port), `smartport_fuel_unit` = MAH, `report_cell_voltage` = OFF,
  `telemetry_switch` = OFF; `ltm_update_rate` = NORMAL. **B**
- MAVLink: `mavlink_version` = 2, `mavlink_radio_type` = GENERIC (ELRS, SIK), rates `mavlink_ext_status_rate` = 2,
  `_rc_chan_rate` = 1, `_pos_rate` = 2, `_extra1/2/3_rate` = 2/2/1, `mavlink_min_txbuffer` = 33. 9.1 adds `mavlink_sysid`,
  `mavlink_autopilot_type`. **B**
- `esc_sensor_listen_only` = OFF (BLHeli32 auto telemetry). **B**
- `ibus_telemetry_type`, HoTT, SIM (SMS) telemetry `sim_*`, `smartport_master_*`. **C**

### 3.16 Blackbox, system (15 / 0)
`blackbox_rate_num`/`_denom` = 1/1 (log every loop at 2 kHz), `blackbox_device` (target), the `blackbox` command for field
groups, `debug_mode` = NONE, `i2c_speed` = 400KHZ, `name` (craft name, used for DJI messages), `pilot_name`, `tz_offset`,
`tz_automatic_dst`. 9.1 adds `blackbox_arm_control` (−1…60 s after disarm). **B**

### 3.17 LED pin, beeper, PINIO (8 / 0)
`led_pin_pwm_mode` = SHARED_LOW, `dshot_beeper_enabled` = ON, `dshot_beeper_tone` = 1, `beeper_pwm_mode` = OFF,
`pinio_box1..4` = 255 (none; board `config.c` files often set USER1/USER2, e.g. JHEMCUF722, FLYWOOH743PRO). All **B**, see §6.

### 3.18 Gimbal, headtracker (12 / 0), new in INAV 8
`gimbal_pan_channel`/`_tilt_channel`/`_roll_channel` = 0, `gimbal_sensitivity` = 0 (−16…15), `gimbal_*_trim` = 0,
`gimbal_serial_single_uart` = OFF, `headtracker_type` = NONE (SERIAL, MSP), `headtracker_*_ratio` = 1. **B**

### 3.19 Most valuable uncovered settings (top 25)
`mc_*` PID defaults and `max_angle_inclination_*`; the rate units (`roll_rate` × 10 °/s) and `rc_expo`; `nav_mc_vel_z_*` and
`nav_mc_vel_xy_*`; `gps_ublox_use_galileo`/`_beidou`, `gps_sbas_mode`, `gps_ublox_nav_hz` (9.1 default changes);
`nav_rth_trackback_*`; `nav_position_timeout`; `inav_default_alt_sensor`; `align_mag_roll/pitch/yaw`, `align_board_roll/pitch`;
`serialrx_inverted`/`_halfduplex`; `failsafe_recovery_delay`, `failsafe_off_delay`, `failsafe_mission_delay`; `vtx_power`,
`vtx_low_power_disarm`; `has_flaps`/`flaperon_throw_offset`; `mixer_automated_switch`/`mixer_switch_trans_timer`;
`servo_pwm_rate`, `servo_protocol`; `nav_overrides_motor_stop`; `nav_max_auto_speed`; `nav_fw_land_*`; `geozone_*`;
`pinio_box*`; `osd_*_alarm`; `mavlink_radio_type`; `bat_cells = 0` auto-detect and battery profiles.

---

## 4. In-flight adjustments and on-a-switch mechanisms

### 4.1 What the course says now
Nothing about INAV adjustments. In-flight changes come up in two places only: `inav-wing` and `inav-setup-wing` (autotune and
servo autotrim, saved after disarm with the save stick command), and `inav-ipf` (set VTX power by distance). The Adjustments
tab, `adjrange`, stick commands other than save, profile switching and OSD-menu tuning are all absent.

### 4.2 How INAV adjustments work (8.0.1, `fc/rc_adjustments.[ch]`, identical in 9.1)
- **20 ranges** (`MAX_ADJUSTMENT_RANGE_COUNT 20`) and **4 slots** (`MAX_SIMULTANEOUS_ADJUSTMENT_COUNT 4`), so at most 4
  adjustments are live at once. Betaflight has 30 ranges and no slot field.
- `adjrange <index 0–19> <slot 0–3> <range channel> <start> <end> <function> <adjustment channel>`. Both channels are
  0-based AUX indices (AUX1 = 0). Start and end run 900–2100 in steps of 25.
- **Step mode only.** Every function in `defaultAdjustmentConfigs[]` is `ADJUSTMENT_MODE_STEP`. Select mode is compiled
  only with `USE_INFLIGHT_PROFILE_ADJUSTMENT`, which is commented out in `rc_adjustments.h`. There is no absolute
  (center/scale) mode, unlike Betaflight. A pot therefore behaves like a 3-position switch.
- Thresholds: the channel above `1500 + 200` steps up, below `1500 − 200` steps down (`PWM_RANGE_MIDDLE ± 200`; the doc says
  `mid_rc`). While the switch is held, the step repeats **every 500 ms** (`RESET_FREQUENCY_2HZ`). Returning to centre resets
  the timer, so tapping is faster than holding. Beeps: `beeperConfirmationBeeps(2)` for up and `(1)` for down.
- **The CLI number is the enum value.** The table index is `function − 1`, so, unlike Betaflight, the numbers in the docs table
  are the numbers you type. `Inflight Adjustments.md` says "Adjustment function 0 – 56", but 8.0.1 has **0–60**: the doc is
  stale.
- If the range channel leaves start–end, the slot keeps its state and goes on applying. The doc warns: "ensure that you define
  enough ranges to cover the range channel's usable range".
- **Not saved automatically.** Save after disarm with the stick command (throttle low, yaw left, pitch low, roll right:
  `rc_controls.c` → `saveConfigAndNotify()`), or from the Configurator. Each change is written to Blackbox as an
  `INFLIGHT_ADJUSTMENT` event.
- **Function 22 RATE_PROFILE is a placeholder** ("Unused, placeholder for compatibility"). INAV cannot switch control
  profiles with `adjrange` (only with stick commands, IPF op 42 `Set Profile`, a battery profile, or the CLI).

### 4.3 Function table (8.0.1 = 9.1.0; step size in brackets when ≠ 1)
| # | Function | # | Function | # | Function |
|---|---|---|---|---|---|
| 1 | RC_RATE | 21 | YAW_FF | 41 | POS_XY_D |
| 2 | RC_EXPO | 22 | RATE_PROFILE (placeholder) | 42 | POS_Z_P |
| 3 | THROTTLE_EXPO | 23 | PITCH_RATE | 43 | POS_Z_I |
| 4 | PITCH_ROLL_RATE | 24 | ROLL_RATE | 44 | POS_Z_D |
| 5 | YAW_RATE | 25 | RC_YAW_EXPO | 45 | HEADING_P |
| 6 | PITCH_ROLL_P | 26 | MANUAL_RC_EXPO | 46 | VEL_XY_P |
| 7 | PITCH_ROLL_I | 27 | MANUAL_RC_YAW_EXPO | 47 | VEL_XY_I |
| 8 | PITCH_ROLL_D | 28 | MANUAL_PITCH_ROLL_RATE | 48 | VEL_XY_D |
| 9 | PITCH_ROLL_FF | 29 | MANUAL_ROLL_RATE | 49 | VEL_Z_P |
| 10 | PITCH_P | 30 | MANUAL_PITCH_RATE | 50 | VEL_Z_I |
| 11 | PITCH_I | 31 | MANUAL_YAW_RATE | 51 | VEL_Z_D |
| 12 | PITCH_D | 32 | NAV_FW_CRUISE_THR (10) | 52 | FW_MIN_THROTTLE_DOWN_PITCH_ANGLE (5) |
| 13 | PITCH_FF | 33 | NAV_FW_PITCH2THR | 53 | VTX_POWER_LEVEL |
| 14 | ROLL_P | 34 | ROLL_BOARD_ALIGNMENT (5) | 54 | TPA |
| 15 | ROLL_I | 35 | PITCH_BOARD_ALIGNMENT (5) | 55 | TPA_BREAKPOINT (5) |
| 16 | ROLL_D | 36 | LEVEL_P | 56 | NAV_FW_CONTROL_SMOOTHNESS |
| 17 | ROLL_FF | 37 | LEVEL_I | 57 | FW_TPA_TIME_CONSTANT (5) |
| 18 | YAW_P | 38 | LEVEL_D | 58 | FW_LEVEL_TRIM |
| 19 | YAW_I | 39 | POS_XY_P | 59 | NAV_WP_MULTI_MISSION_INDEX |
| 20 | YAW_D | 40 | POS_XY_I | 60 | NAV_FW_ALT_CONTROL_RESPONSE |

### 4.4 Worked examples a lesson can use (syntax from source, not run here)
```
# Wing field trim: AUX3 (=2) 3-pos selects, AUX4 (=3) momentary adjusts; one slot (0)
adjrange 0 0 2  900 1300 32 3     # pos 1: nav_fw_cruise_thr, step 10
adjrange 1 0 2 1300 1700 58 3     # pos 2: fw_level_pitch_trim
adjrange 2 0 2 1700 2100 33 3     # pos 3: nav_fw_pitch2thr
# Quad nav tuning, second slot on AUX5 (=4) momentary, enabled only while AUX6 (=5) high
adjrange 3 1 5 1700 2100 49 4     # VEL_Z_P: althold bobbing
adjrange 4 1 5  900 1700  0 4     # rest of AUX6 range: nothing (covers the range, see 4.2)
# VTX power up/down on AUX7 (=6) momentary, always active
adjrange 5 2 6 900 2100 53 6
```
Note: adjusted values show on the OSD only through the elements the pilot has placed. The INAV 8 OSD has no dedicated
"adjustment" element of the Betaflight kind. **Unverified**: I did not search `osd.c` for an adjustment-display element.

### 4.5 The other in-flight mechanisms a lesson must cover (all ✗ now)
- **Stick commands**, disarmed (`rc_controls.c`, 8.0.1):
  - gyro calibration: throttle low, yaw left, pitch low, roll centre;
  - save: throttle low, yaw left, pitch low, roll right;
  - acc calibration: throttle high, yaw left, pitch low;
  - compass calibration: throttle high, yaw right, pitch low;
  - acc trim, 2 per step: throttle high plus pitch or roll;
  - WP list save / load / reset: throttle low, pitch high, roll left / roll right; throttle low, pitch low, roll right;
  - multi-mission index up / down: throttle low, roll right / roll left;
  - control profile 1/2/3: throttle low, yaw left plus roll left / pitch up / roll right;
  - battery profile 1/2/3: throttle high, yaw left plus the same three.

  Both profile selections need `feature TX_PROF_SEL`. **There is no "heading reset" stick command** (see §7.3 E2).
- **Programming framework** as tuning-on-a-switch: op 42 Set Profile, op 25/30/31 VTX power/band/channel, op 23 throttle scale,
  op 32 OSD layout, op 38 RC override, op 41 loiter radius, op 55 gimbal sensitivity (9.1). This is the INAV equivalent of
  Betaflight's `vtx` command. INAV has no `vtx` CLI command.
- **Modes as switches**: MIXER PROFILE 2, MIXER TRANSITION, LOITER CHANGE, MISSION CHANGE, OSD ALT 1–3, AUTO TUNE,
  SERVO AUTOTRIM, AUTO LEVEL TRIM (54), TURN ASSIST, FPV ANGLE MIX, USER1–4 (PINIO).
- **OSD stick menu (CMS)**: PIDs, rates, nav and VTX from the goggles (`USE_CMS`, `CMS_MENU_OSD` in `common.h`); while it is
  open, arming is blocked (`CMS` flag).

### 4.6 What a full lesson needs
The two-channel/slot model, step-only behaviour and its timing, the CLI-number = enum note, the 0–60 table and the stale-doc
warning, covering the range channel, no auto-save plus the save stick command, the Blackbox event, what adjustments cannot do
(profiles) and what IPF and stick commands do instead, the CMS menu. Dangers: live changes in flight, combined
functions changing two axes, a switch not centred at power-up keeps stepping. Lab: module `inav-adjustments` (§7.1).

---

## 5. Popular questions (58)

Evidence: O = official doc/wiki page, L = Oscar Liang guide, F = several IntoFPV threads in search results, G = GitHub
discussion/issue. Sources: [inavflight.github.io "Something is disabled — Reasons"](https://inavflight.github.io/docs/quickstart/Something-is-disabled----Reasons),
[INAV wiki Getting started](https://github.com/iNavFlight/inav/wiki/Getting-started-with-iNav),
[INAV wiki Fixed Wing Guide](https://github.com/iNavFlight/inav/wiki/Fixed-Wing-Guide),
[INAV wiki Mixer Tab](https://github.com/iNavFlight/inav/wiki/Mixer-Tab),
[INAV wiki Navigation modes](https://github.com/iNavFlight/inav/wiki/Navigation-modes),
[Oscar Liang — setup iNav on an FPV drone](https://oscarliang.com/setup-inav-fpv-drone),
IntoFPV: [arming](https://intofpv.com/printthread.php?tid=26283), [toilet bowl](https://intofpv.com/printthread.php?tid=18169),
[servos not working (F411 WSE)](https://intofpv.com/t-matek-f411-wse-servos-not-working),
[no INAV OSD on DJI O3](https://intofpv.com/t-psa-no-inav-osd-on-dji-o3),
[no OSD on DJI N3 / O4](https://intofpv.com/t-no-osd-in-dji-n3-goggles-o4-air-unit-stuck-in-low-power-mode);
[GitHub discussion #9750 (VTOL)](https://www.github.com/iNavFlight/inav/discussions/9750),
[dronedj 2025-03: DJI goggles add INAV OSD support for O4](https://dronedj.com/2025/03/07/dji-goggles-inav-fpv-o4/) (secondary,
not read in full), INAV docs in the repo. I could not read reaction counts.

| # | Question | How common | Short correct answer (8.0.1 unless marked) | Course now |
|---|---|---|---|---|
| 1 | Why won't it arm? | O F F | `status` → "Arming disabled flags"; 24 names (`runtime_config.c`): GEOZONE, FS, ANGLE, CAL, OVRLD, NAV, COMPASS, ACC, ARMSW, HWFAIL, BOXFS, RX, THR, CLI, CMS, OSD, ROLL/PITCH, AUTOTRIM, OOM, SETTINGFAIL, PWMOUT, NOPREARM, DSHOTBEEPER, LANDED | ~ inav-intro (causes listed, no flag table) |
| 2 | "Navigation is unsafe" / NAV flag | O F | `navigationIsBlockingArming()`: (a) nav modes assigned or failsafe may need nav, and position not trusted → blocked; with `nav_extra_arming_safety = ALLOW_BYPASS` (the 8.0.1 **default**) arm with yaw right; (b) a nav mode switch already on; (c) first WP farther than `nav_wp_max_safe_distance` (bypass: yaw right, independent of the setting); (d) invalid JUMP | ✓ inav-intro, inav-missions ((b) and (d) missing) |
| 3 | ROLL/PITCH flag on a wing | F | NAV LAUNCH enabled and roll/pitch stick not centred (`fc_core.c`) | ✗ |
| 4 | Toilet-bowling in POSHOLD | O F F | compass: interference, alignment (`align_mag`, Alignment Tool), calibration; then `nav_mc_vel_xy_*` | ✓ inav-gps, inav-setup-scratch (nav PIDs ✗) |
| 5 | How do I align a compass on a mast at an angle? | O F | Alignment Tool, `align_mag_roll/pitch/yaw` (decidegrees), check heading at 4 points | ~ (`align_mag` only) |
| 6 | Acc calibration fails / ACC flag | O | Calibration tab 6 positions, or stick command throttle high, yaw left, pitch low (single position) | ~ |
| 7 | GPS no fix / M10 config | O F | `gps_auto_config` ON, `gps_ublox_use_galileo`/`_beidou` (OFF in 8, **ON in 9.1**), `gps_sbas_mode`, `gps_ublox_nav_hz` (10; 9.1: 8), `gps_dyn_model` AIR_2G, `gps_auto_baud_max_supported`; check with `gpssats`; u-center via `gpspassthrough` | ✗ |
| 8 | RTH altitude modes | O F | `nav_rth_alt_mode` CURRENT/EXTRA/FIXED/MAX/AT_LEAST, `nav_rth_altitude`, climb first | ✓ inav-gps |
| 9 | RTH trackback | O | `nav_rth_trackback_mode` OFF/ON/FS, `nav_rth_trackback_distance` 500 m | ✗ |
| 10 | Safehomes setup | O | Mission Control or `safehome <n> 1 <lat> <lon>`, selected at arming, `safehome_max_distance` 200 m, `safehome_usage_mode` | ~ (concept ✓, command ✗) |
| 11 | Failsafe → RTH and testing it | O F | `failsafe_procedure = RTH`, `failsafe_delay` 0.5 s, RX "no pulses", TX-off test | ✓ inav-setup-scratch |
| 12 | Glider disarms in failsafe | O | `failsafe_throttle_low_delay = 0` (default in 8) | ✓ inav-setup-wing |
| 13 | Several missions on one FC | O | multi-mission: Mission Control multi-mission file, `nav_wp_multi_mission_index` 1–9, MISSION CHANGE mode (59), stick command, adjrange 59, OSD shows the index | ~ inav-missions (one paragraph) |
| 14 | Will the mission continue if RC is lost? | O | `failsafe_mission_delay`: 0 = failsafe procedure at once, N s delay, −1 = continue the mission | ~ (behaviour right, setting not named) |
| 15 | Geozones / no-fly zones | O | INAV 8+, > 512 KB flash, `feature GEOZONE`, Mission Control editor, `geozone` CLI, actions AVOID/HOLD/RTH, RTH path planning | ✗ |
| 16 | Autolaunch tuning | O F | `nav_fw_launch_*` | ✓ inav-wing, inav-setup-wing |
| 17 | Fixed-wing autoland | O | `nav_rth_allow_landing`, `fwapproach` per safehome, `nav_fw_land_*`, wind-based direction | ~ inav-wing (one paragraph) |
| 18 | Wing autotune | O F | AUTO TUNE over ANGLE/ACRO/HORIZON; FF and (not in ANGLE) rates; restores the values from at most 5 s earlier when switched off; save by stick | ✓ inav-wing, inav-setup-wing |
| 19 | Servo reversed — where to fix? | O F | `smix` weight sign per axis or `servo` rate sign, never on the TX | ✓ inav-setup-wing |
| 20 | Servos don't move / motor on a servo pad | O F G | Mixer tab timer map, `timer_output_mode`, PWM_OUTPUT_ENABLE, board docs ("some boards have no servos in MR"), `resource` view-only | ~ (`timer_output_mode` named) |
| 21 | Flaperons / flaps | O | `has_flaps = ON`, FLAPERON mode (34), `smix` input 14 FEATURE FLAPS, `flaperon_throw_offset` 200 | ✗ |
| 22 | VTOL setup | O G | 2 mixer profiles (not F411), MIXER PROFILE 2 / MIXER TRANSITION modes, `mmix` −1…−2 throttle, `smix` input 38, `mixer_automated_switch`, `mixer_switch_trans_timer`, profile linking, `docs/VTOL.md` | ✗ |
| 23 | Tailsitter | O | `tailsitter_orientation_offset`, MixerProfile.md | ✗ (C) |
| 24 | Logic condition examples (VTX by distance, RTH by voltage) | O F | ops/operands tables | ✓ inav-ipf (numbers withheld) |
| 25 | Programming PID | O | `pid <#> …`, output as operand type 6 | ✗ |
| 26 | Custom OSD elements | O | `osd_custom_elements`, 8 elements, text + up to 3 values | ✗ |
| 27 | No OSD in DJI O3/O4 / Walksnail / HDZero goggles | F F F G | serial function MSP DisplayPort (`MSP_OSD`, 1<<25), 115200; `osd_video_system`: HDZERO 50×18, AVATAR 53×20 (Walksnail), BFHDCOMPAT 53×20 (DJI O3, Betaflight characters only), DJI_NATIVE 53×20 (newer DJI firmware), DJIWTF 60×22 (WTFOS on legacy DJI); goggles in custom/canvas OSD mode | ~ (inav-setup-scratch step 8 lists only DJIWTF/AVATAR/HDZERO; bf-hd-osd-video table complete) |
| 28 | OSD layouts on a switch | O | 4 layouts, OSD ALT 1–3 modes, `osd_layout`, IPF op 32 | ✗ |
| 29 | LED strip | O | `feature LED_STRIP`, `led`, `color`, `mode_color`, up to 128 LEDs, `timer_output_mode <t> LED` | ✗ |
| 30 | PINIO: camera switch / VTX power on a switch | O F | `pinio_box1..4` = USER1–4 ids 47/48/57/58, target defines PINIOx_PIN | ✗ |
| 31 | VTX power by switch / pit mode / low power on the bench | O F | adjrange 53, IPF op 25, `vtx_low_power_disarm`, `vtx_pit_mode_chan` | ~ (IPF only) |
| 32 | Battery voltage/current calibration | O F | `vbat_scale`, `current_meter_scale`/`_offset` formulas | ✓ inav-setup-scratch |
| 33 | Battery profiles, auto-switch 4S/6S | O | 3 profiles, `feature BAT_PROF_AUTOSWITCH`, stick commands | ✗ |
| 34 | Li-ion settings | F | cell voltages, `battery_capacity_unit = MWH`, `bat_voltage_src = SAG_COMP` | ~ inav-setup-wing (cell voltages only) |
| 35 | Remaining flight time / "can I make it home" | O | `cruise_power`, `idle_power`, `rth_energy_margin`, OSD elements | ✗ |
| 36 | Rates/expo in INAV | O | `roll_rate` × 10 °/s (20 = 200 °/s), `rc_expo` 70, manual rates % | ~ |
| 37 | Multirotor PID tuning in INAV | O F | `mc_*` defaults, EZ Tune sliders, `dterm_lpf_hz`, iterm relax, antigravity | ~ (EZ Tune named; Betaflight modules referenced) |
| 38 | Filters | O | `gyro_main_lpf_hz` 60, dyn notch, adaptive LPF, Kalman, RPM filter | ~ |
| 39 | Does INAV support bidirectional DShot / RPM filter? | G F | **No bidirectional DShot** in 8.0.1, 9.1.0 or 10.x at `ae6ace4`; RPM via serial ESC telemetry (`ESC_SENSOR` function 262144), `motor_poles`, `feature RPM_FILTERS` | ✗ ("ESC-телеметрия оборотов" only) |
| 40 | Motor order / direction | O F | Quad X order, Motor Mixer Wizard, `motor_direction_inverted` | ✓ inav-setup-scratch |
| 41 | Which ESC protocol? | O | default ONESHOT125; DSHOT300 for BLHeli_S/32/AM32; STANDARD for many plane ESCs | ✓ |
| 42 | ALTHOLD drops or jumps on engage | O F | `nav_mc_hover_thr` from a log, `nav_mc_althold_throttle` | ✓ inav-gps, inav-setup-scratch |
| 43 | INAV without a barometer? | F | 8.0.1 code accepts GPS altitude (`inav_default_alt_sensor`, GPS_ONLY); docs still say baro is required for MC RTH; worse altitude | ~ (inconsistent, §7.3 E8) |
| 44 | Terrain following / SURFACE mode | O | SURFACE mode (33) + rangefinder, `inav_max_surface_altitude` 200 cm, `nav_max_terrain_follow_alt` 100 cm; 9.1 OSD shows "(SURFACE)" / "(!SURFACE UNRELIABLE!)" | ✗ |
| 45 | Optical flow + rangefinder (MSP combo sensor) | O F | `opflow_hardware = MSP`, `rangefinder_hardware = MSP`, serial function MSP on that UART, `opflow_scale`, Calibration tab | ~ est-alt-sources (names only) |
| 46 | Airspeed sensor | O | `pitot_hardware`, I²C MS4525/DLVR or ADC, `pitot_scale`, `osd_speed_source = AIR`, `fw_reference_airspeed` | ✗ |
| 47 | Telemetry on the radio (CRSF/SmartPort/LTM) | O F | CRSF: same UART, `feature TELEMETRY`; S.Port: function 32, `telemetry_inverted`/halfduplex on F4; LTM 16 | ✗ |
| 48 | MAVLink to Mission Planner/QGC, ELRS MAVLink | O G | function `TELEMETRY_MAVLINK` 256, `mavlink_*_rate`, `mavlink_radio_type = ELRS`; 9.1 `mavlink_sysid`, `mavlink_autopilot_type` | ✗ |
| 49 | Configure from a phone / Bluetooth | F | MSP over a UART with a BT/ESP32 bridge; mwp, apps | ✗ |
| 50 | Upgrading 7 → 8 → 9 | O F | full `diff all`, compare renamed settings; 9.1 Configurator auto-backup + migration | ~ inav-intro |
| 51 | `diff` vs `diff all` | O | plain `diff` = master only, profiles lost. Correction 2026-11-18: wrong — plain `diff` prints master plus the active control, mixer and battery profile (cli.c `printConfig`, `else` branch of `if (dumpMask & DUMP_ALL)`, same in 8.0.1 and 9.1.0); only the non-active profiles are missing; see docs/reviews/factcheck/theory-wave3.md | ✗ |
| 52 | Motor stop / idle / airmode | O | `motorstop_on_low`, `throttle_idle` 8 %, `nav_overrides_motor_stop`, `airmode_type` | ~ |
| 53 | Turtle mode | O | TURTLE mode (52), DShot, `turtle_mode_power_factor` 55 | ✗ (C) |
| 54 | Companion/GCS control (MSP RC override) | O G | `receiver_type = MSP` or MSP RC OVERRIDE mode + `msp_override_channels` (8.0.1: custom build; 9.1: standard) | ✗ (SITL uses `receiver_type = MSP`) |
| 55 | Stick commands | O | §4.5 | ~ (save only) |
| 56 | Course hold / cruise / heading hold modes | O | NAV COURSE HOLD (45), NAV CRUISE (53), HEADING HOLD (5), ANGLE HOLD (64), `nav_cruise_yaw_rate` | ~ (NAV CRUISE named) |
| 57 | Home moves after a mid-air re-arm | O | `inav_reset_home` FIRST_ARM / EACH_ARM / NEVER, HOME RESET mode (30) | ✗ |
| 58 | Launch doesn't start the motor | O F | detection thresholds, `nav_fw_launch_detect_time`, idle throttle, wiggle-to-wake | ✓ inav-wing (diagnostics) |

**Totals: 58 questions. ✓ 14, ~ 20, ✗ 24** (✗: 3, 7, 9, 15, 21, 22, 23, 25, 26, 28, 29, 30, 33, 35, 39, 44, 46, 47, 48, 49, 51,
53, 54, 57).

---

## 6. Hardware integration

Question: can a student **connect and configure** it from the course alone? Verdict: **Yes / Partly / No**.

### 6.1 Servos: **Partly** (wing yes, everything else no)
**Exists**: `inav-setup-wing` ("Сервы в INAV: смикс → servo → выход", step 6 and the servo test table): the `smix`/`servo`
syntax and ranges (verified: rate −125…125, smix rate −1000…1000, `conditionId` −1…63), reversal rules, endpoints, throws in mm,
autotrim. `bf-servos-pwm` has the INAV comparison row.
**Missing**: servo power (BEC, current, common ground; Betaflight's `bf-servos-pwm` has it, but the INAV track does not link
it), `servo_pwm_rate` = 50 (50–498) and digital servos, `servo_lpf_hz` = 20, `servo_protocol` SBUS out of a UART (function
4194304), `MAX_SUPPORTED_SERVOS` 18, servos on a **multirotor** (gimbal tilt, gripper/drop on an RC channel through `smix`
inputs 8–11/15–22, or on a GVAR through inputs 30–37 from IPF), the timer map in the Mixer tab, `feature PWM_OUTPUT_ENABLE`,
and the fact that some boards expose no servo outputs in MR mode (`ESC and servo outputs.md`).
**Proposal**: `inav-mixer-vtol` (§7.1), plus a servo-power cross-link to `bf-servos-pwm`. **Lab**: SITL: a quad with one extra
servo rule `smix 0 4 8 100 0 -1` (RC CH5 → servo 4), read the servo value over MSP (`MSP_SERVO`) as AUX5 moves; a second rule
gated by a logic condition. **«Переход на реальное железо»**: a drop servo on a free pad of a real board, BEC current measured
at stall, `timer_output_mode` check.

### 6.2 RGB LED strips: **No**
**Exists**: nothing in the INAV track (`bf-led-buzzer` is Betaflight-only).
**Missing**: WS2812 wiring and power (`LedStrip.md`: separate supply above 20 LEDs), **up to 128 LEDs** (`LED_MAX_STRIP_LENGTH`;
Betaflight 32), `feature LED_STRIP`, the LED pad and its timer (`timer_output_mode <timer> LED`), `led <i> <x>,<y>:<dirs>:<functions+overlays>:<colour>`
(doc examples `led 0 0,15:SD:AWI:0`, `led 4 7,7::C:1`, thrust ring `led 0 2,2::R:13`), `color`, `mode_color`, the LED Strip tab
(9.1 presets), LEDS OFF mode (15), LIGHTS mode (16) with `failsafe_lights`, `led_pin_pwm_mode` and `ledpinpwm` (LED pin as a PWM/GPIO
output), IPF op 52 LED pin PWM.
**Proposal**: `inav-led-pinio-beeper` (§7.1). **Lab**: Configurator-first (no LEDs in SITL): build a 16-LED wing layout in the
LED tab, export the `led`/`color` lines and decode each field; on the bench, measure strip current at full white vs the profile.

### 6.3 PWM outputs and timers: **Partly**
**Exists**: `inav-setup-wing` and `bf-servos-pwm`: "один таймер — одна функция", `timer_output_mode AUTO|MOTORS|SERVOS`.
`f-motors-esc`: protocols.
**Missing**: the `LED` value of `timer_output_mode`, that `resource` is view-only (no remapping), the Mixer tab's timer
colouring, `motor_pwm_rate` = 16000 for OneShot/Multishot/brushed, `servo_pwm_rate`, DShot support without bidirectional
telemetry, `feature PWM_OUTPUT_ENABLE`, and the custom-target route (a `target.h` change and a rebuild, which `fw-build-*` will
cover).
**Proposal**: theory section «Выходы, таймеры и функции в INAV» in `inav-mixer-vtol`. **Lab**: from a real board's `target.c`
(e.g. MATEKF405, `timerHardware[]`), tabulate outputs → timers; assign 4 motors + 2 servos + LED legally and confirm in the
Mixer tab.

### 6.4 Digital video and HD OSD: **Partly**
**Exists**: `inav-setup-scratch` step 8 ("HD: функция MSP_OSD на UART VTX и `osd_video_system = DJIWTF`, AVATAR или HDZERO");
`bf-hd-osd-video` "INAV и ArduPilot — коротко" (all 9 `osd_video_system` values, `FUNCTION_MSP_OSD` = 1 << 25, 115200, the
"131072 in INAV is `FUNCTION_VTX_FFPV`" warning); `link-digital-video` ("тип OSD — по документации своей системы").
**Missing**: the system → value map with canvas sizes (from `displayport_msp_osd.c`): HDZERO 50×18; AVATAR, BFHDCOMPAT and
DJI_NATIVE 53×20; DJIWTF 60×22; BF43COMPAT 30×16 (it is not in the 8.0.1 switch block, so I inferred it from `OSD.md` "DJI OSD
30×16"; **unverified**). DJI O3 needs **BFHDCOMPAT** (Betaflight character set, "partial" per `OSD.md`). Newer DJI goggle
firmware supports **DJI_NATIVE** (O4, "YES (TBC)" in `OSD.md`). The old `FUNCTION_DJI_HD_OSD` (1 << 21) is for the legacy DJI
FPV air unit without WTFOS. Also missing: `enable_broken_o4_workaround`, `osd_msp_displayport_fullframe_interval`, VTX
control over MSP for HDZero (`USE_VTX_MSP`), `name` used for DJI messages (`dji_use_name_for_messages`), and wiring and power,
which can reuse `bf-hd-osd-video`.
**Proposal**: `inav-osd-hd` (§7.1) or a large addition to `inav-setup-scratch`. **Lab**: SITL plus INAV-Sim-OSD or a
Configurator OSD preview: set each `osd_video_system`, compare the layout grid; on the bench, one HD system.

### 6.5 Camera gimbals: **No**
**Exists**: `bf-servos-pwm` table row "источники smix 12/13 (тангаж/крен подвеса)".
**Missing**: servo gimbal (`Servo Gimbal.md`): `smix` inputs 12/13 are non-zero **only while CAMSTAB mode (8) is active**
(`servos.c`: `IS_RC_MODE_ACTIVE(BOXCAMSTAB)`), weight for scaling and sign. Serial gimbal (INAV 8, Walksnail GM protocol,
`Serial Gimbal.md`): serial function GIMBAL (1 << 26), `gimbal_pan/tilt/roll_channel`, `gimbal_sensitivity`, trims, modes 65–68
(GIMBAL LEVEL TILT / LEVEL ROLL / CENTER / HEADTRACKER). Headtracker: function `GIMBAL_HEADTRACKER` (1 << 27),
`headtracker_type` SERIAL/MSP, `gimbal_serial_single_uart`, and `smix` inputs 39–41 (headtracker pan/tilt/roll, already in
8.0.1) for a servo gimbal driven by a headtracker. Also `osd_pan_servo_*` for a pan-servo camera.
**Proposal**: section «Подвесы и headtracker в INAV» in `inav-mixer-vtol`, plus a cross-link from `payload-gimbal`. **Lab**:
SITL: two `smix` rules from inputs 12/13 to servos, toggle CAMSTAB, tilt the SITL attitude (or read with the FDM paused), read
`MSP_SERVO`; hardware: a tilt servo or a Walksnail GM on a UART.

### 6.6 GPS/compass: **Partly**
**Exists**: `inav-gps` and `inav-setup-scratch` cover the UART, protocol, compass on I²C, calibration, `align_mag`,
declination auto, ground checks. These are good.
**Missing**: §3.8 (constellations, SBAS, rate, dynamic model, auto-baud, 9.1 defaults), `gpssats`, `gpspassthrough`, the
Alignment Tool and custom mag alignment, `mag_hardware` choice for common chips (QMC5883L, IST8310, 9.1 QMC5883P), the
**I²C speed** (`i2c_speed`), the compass-on-a-separate-I²C-bus question, GPS fix estimation for wings (`inav_allow_gps_fix_estimation`,
`failsafe_gps_fix_estimation_delay`). **Addition** to `inav-gps` (§7.2).

### 6.7 Rangefinder and optical flow: **No** (names only)
**Exists**: `est-alt-sources` names `opflow_hardware`, `opflow_scale`, `rangefinder_hardware`, the flow weights.
**Missing**: supported devices (§3.1), the MSP combo sensors (`rangefinder_hardware = MSP`, `opflow_hardware = MSP` on a UART with
MSP), the SURFACE mode and its limits, opflow calibration on the Calibration tab, landing and terrain use, OSD AGL.
**Proposal**: `inav-sensors-extra` (§7.1). **Lab**: SITL `rangefinder_hardware = FAKE` (the table has FAKE) — **unverified**
that SITL feeds it from a simulator; otherwise a bench test with a VL53L1X: AGL in the Sensors tab vs a tape measure.

### 6.8 Airspeed sensor: **No**
**Missing**: `pitot_hardware` (MS4525, DLVR-L10D on I²C; ADC analogue; VIRTUAL = estimated from GPS and wind; 9.1 MS5525),
`pitot_scale`, `pitot_lpf_milli_hz`, the airspeed OSD and `osd_speed_source`, its use in `fw_reference_airspeed`, TPA/APA
(9.1 `apa_pow`), GPS fix estimation. **Proposal**: in `inav-sensors-extra`. **Lab**: hardware (blow test, compare with GPS
speed in calm air on a straight run both ways).

### 6.9 Telemetry radios: **No**
**Missing**: serial functions (MAVLink 256, LTM 16, SmartPort 32, IBUS 512, HoTT 8), MAVLink rates and `mavlink_radio_type`
(ELRS MAVLink, SiK), CRSF telemetry on the RX UART, connecting Mission Planner/QGC or mwp, MSP-over-Bluetooth.
**Proposal**: `inav-telemetry-gcs` (§7.1). **Lab**: SITL: enable MAVLink on UART2 (TCP 5761), connect QGroundControl or MAVProxy,
read HEARTBEAT/GPS_RAW_INT rates against `mavlink_pos_rate`; then LTM to mwp.

### 6.10 ESC telemetry: **No**
**Missing**: INAV 8.0.1/9.1.0 have **no bidirectional DShot** (no `USE_DSHOT_TELEMETRY`; also absent in maintenance-10.x at
`ae6ace4`). RPM and temperature come from the **ESC telemetry wire** (serial function `ESCSERIAL` 262144, used for ESC_SENSOR), with
`esc_sensor_listen_only` (BLHeli32 auto telemetry), `motor_poles`, `feature RPM_FILTERS`, `rpm_gyro_*`. Also missing: the
`vbat_meter_type`/`current_meter_type = ESC` options. **Addition** to `inav-setup-scratch` step 11 and to the tuning module.

### 6.11 CAN / DroneCAN: **No** (not applicable)
INAV 8.0.1 has no CAN support. 9.1.0 defines `USE_DRONECAN` in three H7 targets (TBS_LUCID_H7_V3, TBS_LUCID_H7_OEM, AEDROXH7),
but the tree contains no DroneCAN driver. One sentence in `inav-intro` is enough: "CAN-периферия — это ArduPilot/PX4".

### 6.12 Relays / PINIO: **No**
**Missing**: PINIO (`PINIO_COUNT` 4; pins only where the target defines `PINIOx_PIN`, 71 targets in 8.0.1), `pinio_box1..4`
(permanent id, 255 = none; many boards preset USER1 = VTX power, USER2 = camera switch), USER1–4 modes, WP user actions (bits 1–4
of `p3` → USER1–4 during a mission; logic operands 6–13), IPF reading USER modes. The `inav-missions` example says "Триггер
камеры — через PINIO/user action по `p3`" but gives no setup.
**Proposal**: `inav-led-pinio-beeper`. **Lab**: SITL: a mission with `p3 = 2` on one WP, logic condition "WP USER1 action" →
GVAR, observe in the Programming tab; hardware: switch a camera rail on USER1 and measure it with a multimeter.

### 6.13 Buzzer: **No**
**Missing**: `beeper` list/conditions, BEEPER mode (13), BEEPER MUTE (60), DShot beeper (`dshot_beeper_enabled`,
`dshot_beeper_tone`, the DSHOTBEEPER arming flag), `beeper_pwm_mode`. In `inav-led-pinio-beeper`.

### 6.14 Camera trigger: **No**
INAV has no camera-trigger function. The ways are: WP user action → USER mode → PINIO, a servo through `smix` on a GVAR set by
IPF (distance or time interval with TIMER/DELTA), RunCam Device Protocol (`RCDEVICE` 1024, CAMERA CONTROL 1–3 modes) for
record start/stop. This belongs in `inav-led-pinio-beeper` or `inav-missions` with one worked example, "photo every 30 m
along a survey": IPF using `Trip distance` (flight operand 2) and MODULUS (op 40).

### 6.15 Summary
New modules covering these: `inav-mixer-vtol` (6.1, 6.3, 6.5), `inav-osd-hd` (6.4), `inav-led-pinio-beeper` (6.2, 6.12–6.14),
`inav-sensors-extra` (6.7, 6.8), `inav-telemetry-gcs` (6.9). Additions: `inav-gps` (6.6), `inav-setup-scratch` (6.10, 6.11).

---

## 7. Proposed changes

### 7.1 New modules (ordered by value)

Every module follows `content/article-template.md`: summary, theory, practice ≥ 150 words with a lab and an acceptance line,
diagnostics, checklist, references ≥ 2, quiz bank (8), glossary terms, diagram. SITL-first, then «Переход на реальное
железо». INAV SITL limits (from `inav-setup-scratch`, not re-checked): no DShot (silently becomes MULTISHOT), no analogue OSD,
sensors FAKE, flight only with RealFlight/X-Plane. So LED, buzzer and real-OSD labs are Configurator and bench labs. New ids
go into `data/curriculum.json`, `data/content-manifest.json`, `data/glossary.json` and the quiz banks, per `content/README.md`.

| # | id | Title (ru) | Pri | Scope | Lab |
|---|---|---|---|---|---|
| 1 | `inav-mixer-vtol` | «Миксер INAV целиком: mmix/smix, выходы и таймеры, флапероны, подвесы, mixer profiles и VTOL» | A | `mmix` (incl. −1/−2 throttle), `smix` all inputs (0–59 in 8.0.1: stabilized 0–3 and ±halves 23–28, RC 4–11/15–22/42–59, gimbal 12/13, flaps 14, GVAR 30–37, transition 38, headtracker 39–41), `servo`, `servo_*` settings, `timer_output_mode` incl. LED, `resource` view-only, PWM_OUTPUT_ENABLE, flaperons, servo gimbal + CAMSTAB, serial gimbal/headtracker, mixer profiles, MIXER PROFILE 2 / TRANSITION, `mixer_automated_switch`, profile linking (9.1 rename), F411 limit, tailsitter note | **SITL**: VTOL-like config with two mixer profiles; switch MIXER PROFILE 2 by MSP RC; dump `mixer_profile 1/2` from `diff all`; read `MSP_SERVO`/`MSP_MOTOR` before/after MIXER TRANSITION (`smix … 38 45 150`). **Железо**: a tilt servo or drop servo on a free pad, timer map table, BEC stall current |
| 2 | `inav-cli-backup` | «CLI INAV: все команды, diff/dump и профили, бэкап, восстановление и переезд 7 → 8 → 9» | A | the §2.1 table (A/B), `diff` = master trap, scopes, `showdefaults`, profile blocks, `defaults`, `version`, `status` flags table (24), `tasks`, `feature list`, `batch`, 9.1 auto-backup and migration, list of renamed settings 8 → 9 (§1.3) | **SITL**: config with 3 control profiles + 2 mixer profiles; `diff` vs `diff all` line counts; erase `eeprom.bin`, restore from `diff`, show what is lost; script that converts an 8.0.1 `diff all` to 9.1 names. **Железо**: back up a real FC, flash 9.1 with Full chip erase, restore, compare |
| 3 | `inav-osd-hd` | «OSD в INAV: аналог и HD (DJI O3/O4, Walksnail, HDZero), раскладки, тревоги, свои элементы» | A | §6.4 map, serial functions, alarms (§3.13), 4 layouts + OSD ALT modes + `osd_layout`, `osd_custom_elements`, stats, CMS menu, DJI name messages | **SITL**: SITL + INAV-Sim-OSD (MSP DisplayPort) — check each `osd_video_system`, record the grid; `osd_custom_elements` with GVAR. **Железо**: one HD system wired, OSD visible, layout switch on a 3-pos switch |
| 4 | `inav-mc-tuning` | «Настройка мультиротора в INAV: PID, рейты, фильтры, EZ Tune и навигационные PID» | A | §3.2/3.3 defaults and units, `looptime`, filter chain, RPM filter via ESC telemetry (no bidir DShot), EZ Tune sliders → the PIDs they write, `nav_mc_vel_z_*`/`vel_xy_*`, `nav_mc_bank_angle`, braking | **SITL**: EZ Tune slider sweep, read the resulting `mc_*`/filter values over CLI and tabulate; **Железо**: Blackbox of an ALTHOLD step and POSHOLD stick release before/after a `nav_mc_vel_z_p` change |
| 5 | `inav-adjustments` | «Подстройки в полёте INAV: adjrange, стик-команды, профили, OSD-меню» | B | §4 entirely | **SITL**: three `adjrange` rows (cruise thr step 10, VTX power, VEL_Z_P), Python MSP RC sender (reuse the `inav-setup-scratch` script) holds the channel, read the value via CLI every 500 ms, show repeat timing and "not saved" after restart without save. **Железо**: wing cruise-throttle trim in flight, stick save, `diff all` before/after |
| 6 | `inav-geozones-landing` | «Геозоны, safehome, trackback и автопосадка крыла в INAV 8» | B | `geozone` CLI and editor, actions, RTH path planning, flash limit; `safehome` CLI; `nav_rth_trackback_*`; `fwapproach`, `nav_fw_land_*`; `nav_rth_fs_landing_delay` | **SITL** (X-Plane or RealFlight for flight; config-only otherwise): define an inclusive + exclusive zone in CLI, arm-blocking test (GEOZONE flag) by placing home inside an NFZ via FAKE GPS — **unverified** that FAKE GPS position can be set without a simulator; autoland approach config check. **Железо**: wing with one safehome + fwapproach, autoland recorded |
| 7 | `inav-sensors-extra` | «Дополнительные датчики INAV: дальномер и SURFACE, оптический поток, пито, температура» | B | §6.7, §6.8, `temp_sensor`, `inav_default_alt_sensor` and flying without baro | **Железо-first** (bench): VL53L1X/MSP combo sensor, opflow calibration, pitot blow test; SITL part: FAKE rangefinder if it produces data (verify) |
| 8 | `inav-telemetry-gcs` | «Телеметрия и связь INAV: CRSF/SmartPort/LTM/MAVLink, MSP RC, Bluetooth и наземные станции» | B | §6.9, §3.15, MSP RC override (8 vs 9.1), `receiver_type = MSP`, mLRS `bind_msp_rx` (9.1), 9.1 MSP2 WP index / cruise heading | **SITL**: MAVLink on TCP 5761 to MAVProxy/QGC, rates vs settings; MSP RC override with a Python script (9.1 SITL). **Железо**: ELRS MAVLink or SiK radio to QGC |
| 9 | `inav-led-pinio-beeper` | «Свет, PINIO, пищалка и триггер камеры в INAV» | B | §6.2, §6.12–6.14, LIGHTS/LEDS OFF, `ledpinpwm`, IPF op 52 | **Configurator/bench**: LED layout, PINIO on USER1 by switch and by WP user action (SITL mission + logic operand), buzzer conditions; photo-every-N-metres logic |

### 7.2 Additions to existing modules (ordered by value)

1. **`inav-ipf`, theory and practice.** Replace "Номера операций и операндов … меняются между релизами" with real numbers
   (stable 8.0.1 → 9.1.0, §1.3). Add tables: operand types 0–7, the key flight operands (0 arm timer s, 1 home distance m,
   2 trip distance m, 4 vbat 0.01 V, 5 cell voltage 0.01 V, 7 mAh, 8 sats, 12 altitude cm, 14 throttle %, 22 is RTH, 24 is
   failsafe, 29 LQ uplink), flight-mode operands 0–16, waypoint operands 0–13, and ops 0–54 (+55/56 in 9.1). Then write the
   practice block out: `logic 0 1 -1 2 2 1 0 100 0` and `logic 1 1 0 25 0 3 0 0 0`. Add `gvar <i> <default> <min> <max>`
   (int32 bounds, default ±32767), the `pid` command and operand type 6, `osd_custom_elements`, the 10 Hz task
   (`TASK_PERIOD_HZ(10)`, already stated, ✓), and the 9.1 JavaScript Programming tab with the same VTX example in JS.
2. **`inav-setup-scratch` step 8 and `setup-cards.html` step 13**: the full HD map (§6.4). Add DJI O3 = BFHDCOMPAT, DJI
   O4/native = DJI_NATIVE, and DJIWTF only for WTFOS.
3. **`inav-setup-scratch` step 11**: no bidirectional DShot; RPM filter via the ESC telemetry wire (`ESCSERIAL` 262144),
   `motor_poles`, `feature RPM_FILTERS`; give the MC PID defaults (§3.2) and the rate units, and point to `inav-mc-tuning`.
4. **`inav-gps`**: GPS configuration block (§3.8 with 9.1 defaults), `gpssats`/`gpspassthrough`, custom mag alignment and the
   Alignment Tool, `nav_rth_trackback_*`, `nav_position_timeout` = 5 s, `failsafe_mission_delay`, `inav_default_alt_sensor`,
   `inav_reset_home`; fix E2 and E8.
5. **`inav-intro`**: the full arming-flag table (24, §5 #1) with cause → setting → fix (including ROLL/PITCH = NAV LAUNCH +
   sticks, LANDED, DSHOTBEEPER, PWMOUT, GEOZONE); the 23 features (§2.3); the build gating (> 512 KB for geozones, F411 has no
   VTOL); "no CAN"; the Configurator tab names (Status, Calibration, Alignment Tool).
6. **`inav-missions`**: fix E1 and E9; `nav_max_auto_speed`, `nav_wp_load_on_boot`, `nav_fw_wp_turn_smoothing`,
   multi-mission in full (index, MISSION CHANGE, stick commands, adjrange 59), WP user actions → USER1–4 → PINIO with a worked
   example, the JUMP validity rules (`navigation.c`: first WP can't be JUMP, no jumping to adjacent WPs, target must be
   WAYPOINT/HOLD_TIME/LAND), `NAV_MAX_WAYPOINTS` 120 (some targets 60), the `wp` flag 72 (0x48, HOME).
7. **`inav-wing`**: flaperons (§5 #21), `fw_min_throttle_down_pitch`, `nav_fw_soaring_*`, `fw_autotune_*` settings (why ANGLE
   tuning keeps rates), the autoland block (`fwapproach`, `nav_fw_land_*`), `apa_pow`/`tpa_pitch_compensation` (9.1); fix E10.
8. **`inav-setup-wing`**: the `LED` value of `timer_output_mode`, `servo_pwm_rate`/`servo_lpf_hz`, a servo power paragraph or
   a link to `bf-servos-pwm`, PWM_OUTPUT_ENABLE, the ROLL/PITCH arming flag in diagnostics.
9. **`nav-resilience`**: fix E3.
10. **`link-vtx` (or `inav-intro`)**: one INAV paragraph, no VTX tables, `vtx_power` is a level index,
    `vtx_low_power_disarm`, `vtx_frequency_group`, adjrange 53, IPF ops 25/30/31.
11. **`est-alt-sources`**: the SURFACE mode and the two surface limits; the MSP combo-sensor setting.

With 7.1 and 7.2 done, the projected coverage is: CLI A+B 47/47 ✓ (C at least ~), every Configurator A tab ✓, every A/B
setting in §3 named with its meaning and its default, and 58/58 popular questions answered.

### 7.3 Factual errors and outdated statements in existing modules

| # | Module, place | Quote | Problem | Source |
|---|---|---|---|---|
| E1 | `inav-missions`, theory "Структура точки" | "`p1`: для WAYPOINT — скорость к точке (см/с; только мультиротор и только если 50 < p1 < `nav_auto_speed`)" | Speed is used if **50 ≤ p1 ≤ `nav_max_auto_speed`** (1000 cm/s), and a larger value is clamped to `nav_max_auto_speed`, so it is not bounded by `nav_auto_speed`. The same per-point speed applies to LAND (p1) and POSHOLD_TIME (**p2**) | `navigation.c` `getActiveSpeed()` |
| E2 | `inav-gps`, theory "Три датчика" | "стик-команда «сброс курса» позволяет задать его вручную, направив аппарат на север" | No such stick command in 8.0.1. `rc_controls.c` has gyro/acc/mag calibration, save, trims, WP save/load/reset, multi-mission, profile selection only. Remove it or name the real mechanism (wing heading from GPS course once moving; `imu.c` `canUseCOG`) | `fc/rc_controls.c` 8.0.1, `flight/imu.c` |
| E3 | `nav-resilience`, theory INAV bullet | "если позиции нет дольше ~2 с в RTH/WP — Emergency Landing (снижение в ANGLE на `failsafe_throttle`, моторы выключаются через `failsafe_off_delay`)" | The timeout is `nav_position_timeout` = **5 s** (0 = disable). Nav emergency landing descends at `nav_emerg_landing_speed` while altitude is valid and ends at landing detection (`nav_disarm_on_landing`). `failsafe_throttle`/`failsafe_off_delay` belong to the RC-failsafe **LAND** procedure when altitude sensors are missing | `settings.yaml` (`nav_position_timeout`), `navigation.c` lines ~2779–2780, `Failsafe.md` (LAND) |
| E4 | `inav-setup-scratch` step 8; `setup-cards.html` step 13 | "HD (DJI, Walksnail, HDZero): функция MSP_OSD на UART VTX и `osd_video_system = DJIWTF`, AVATAR или HDZERO" | DJIWTF (60×22) is for WTFOS on the legacy DJI system. **DJI O3 needs BFHDCOMPAT** (53×20, Betaflight characters), and newer DJI firmware/O4 uses **DJI_NATIVE**. A DJI O3/O4 user following the module gets a wrong canvas | `io/displayport_msp_osd.c` (mode switch), `docs/OSD.md` table, `DJI compatible OSD.md` |
| E5 | `inav-setup-wing` step 2; `bf-servos-pwm` INAV row | "`timer_output_mode` переключает таймер целиком в MOTORS или SERVOS"; "`timer_output_mode <timer> AUTO\|MOTORS\|SERVOS`" | Incomplete: 8.0.1 also has **LED** (`outputModeNames[]` = AUTO, MOTORS, SERVOS, LED) | `fc/cli.c` |
| E6 | `inav-ipf`, practice step 2 | "Номера операций и операндов — из таблиц … они меняются между релизами, поэтому в модуле не зашиты" | From 8.0.1 to 9.1.0 the numbers are append-only: ops 0–54 and flight operands 0–45 are unchanged. The module can and should give them (`logic_condition.h`). Keep the advice to check the version's docs | `programming/logic_condition.h` 8.0.1 vs 9.1.0 |
| E7 | `inav-ipf`, theory "Модель" | "GVAR — глобальные переменные, целые от −32768 до 32767" | That is only the default min/max of each GVAR. `gvar <i> <default> <min> <max>` sets bounds as int32 | `programming/global_variables.[ch]` (`int32_t min/max`, reset to `INT16_MIN/MAX`) |
| E8 | `inav-gps` "Три датчика"; `inav-intro` "Что под капотом" | "Барометр — высота. У мультиротора обязателен для ALTHOLD/RTH"; "компас и баро обязательны для мультиротора" | Overstated, and inconsistent with `inav-intro` "Требования" ("практически обязателен"). In 8.0.1, `canActivateAltHoldMode()` needs only `estAltStatus ≥ EST_USABLE`, GPS altitude counts (`inav_default_alt_sensor` = GPS, GPS_ONLY option), and heading can come from GPS course (`isImuHeadingValid()`). The docs (`Failsafe.md`) still list the baro as required for MC RTH. Suggested wording: "strongly recommended; without it altitude comes from GPS and is much worse". Flight behaviour without baro is **not verified** here | `navigation.c` 4378–4391, `navigation_pos_estimator.c` 563–577, `flight/imu.c` 881–884 |
| E9 | `inav-missions`, "Защита от чужой миссии" | "Обход — `nav_extra_arming_safety = ALLOW_BYPASS` плюс yaw-стик при арме" | For the first-WP-distance block, yaw right bypasses it **regardless** of `nav_extra_arming_safety`. `ALLOW_BYPASS` matters only for the missing-position block, and it is already the 8.0.1 default | `navigation.c` `navigationIsBlockingArming()` |
| E10 | `inav-wing`, diagnostics "в loiter крыло «валится»" | "`max_angle` по расчёту V_s в вираже" | There is no `max_angle` setting. The limit is `nav_fw_bank_angle` (35°), as `inav-setup-wing` says correctly | `settings.yaml` |
| E11 | `inav-intro`, "Что иначе" | "**Дом** — точка первого арма; **safehomes** — … при RTH ближайшая из них в пределах `safehome_max_distance` заменяет дом" | Imprecise: the safehome is **selected at arming** and used when RTH starts (`Safehomes.md`; `inav-gps` says this correctly). Home also depends on `inav_reset_home` (FIRST_ARM default; EACH_ARM, NEVER) | `docs/Safehomes.md`, `settings.yaml` |
| E12 | `inav-intro`, "Что иначе" | "**Арм только тумблером.** Арм стиками удалён ещё в INAV 2.2" | No stick arming in 8.0.1 is correct. Two gaps: `fixed_wing_auto_arm` (arm on throttle) exists, and the "2.2" is **unverified** (no tags before 8 were read) | `settings.yaml`, `fc/rc_controls.c` |
| E13 | `inav-setup-scratch` frontmatter | "имена параметров совпадают в 9.x" | True for every name the track uses, but defaults that the module relies on changed in 9.1: Galileo/BeiDou ON, `gps_ublox_nav_hz` 8, `inav_w_z_*`. Worth a "9.x" note | §1.3 |
| E14 | `inav-intro`, `inav-gps`, `inav-missions`, `inav-wing`, `inav-ipf` frontmatter | "firmware: INAV 7.0+" | Their content was checked against 8.0.1 (the factcheck reports cite 8.0.0/8.0.1); geozones, the serial gimbal and FW autoland approach are 8-only. Suggest "INAV 8 (7.x отличия отмечены)" | — |
| E15 | `nav-resilience`, INAV bullet | "`inav_allow_gps_fix_estimation` (оценка без fix для крыла по airspeed+компасу)" | Per `GPS_fix_estimation.md`: baro + compass (recommended) with a pitot if present, otherwise an assumed constant airspeed; a GPS fix and home must exist before takeoff | `docs/GPS_fix_estimation.md` |

No errors found in: the `inav-wing` and `inav-setup-wing` launch, loiter, throttle and failsafe defaults (all match
`settings.yaml` 8.0.1), autotune scope (FF + rates; `pid_autotune.c` restores the gains of at most 5 s ago on exit), servo
autotrim (2 s, save on disarm, the 1300–1700 clamp only in the continuous `FW_AUTOTRIM` path), `smix`/`servo` syntax and
ranges, the flying-wing preset (`js/model.js`), `motorstop_on_low` ON / `throttle_idle` 8 in 8.0.1. In `inav-setup-scratch`:
serial function bits (MSP 1, GPS 2, RX_SERIAL 64, BLACKBOX 128, MSP_OSD 33554432), mode ids, failsafe defaults (`failsafe_delay`
5, LAND default, `failsafe_stick_threshold` 50, `failsafe_min_distance_procedure` DROP), `min_check` 1100, `max_check` 1900,
`rx_min/max_usec` 885/2115, `gps_min_sats` 6, `mag_calibration_time` 30, `nav_mc_hover_thr` 1300, the `vbat_scale` /
`current_meter_scale` defaults (1100 / 400) and formulas. In `inav-gps`: RTH modes and defaults, safehome default 200 m and
modes, estimator weights (8.0.1 values), `nav_rth_abort_threshold` 50000 cm (it trips when distance to home grows 500 m above
the minimum seen, `navigation.c` ~3186). In `inav-missions`: `wp` format, actions 1/3/4/5/6/7/8, flag 165, `p3` bit 0 =
altitude mode, `wp load/save/reset`. In `inav-ipf`: 64 logic conditions, 8 GVARs, 4 PIDs, 10 Hz, ops DELAY/STICKY/EDGE/TIMER/DELTA
exist, cell voltage in 0.01 V, GVAR 0–3 OSD elements.

---

## Appendix: counts

- CLI commands in 8.0.1: **61** (9.1.0: 62) — ✓ 14, ~ 5, ✗ 42; A 20 (✓ 14), B 27 (✓ 0), C 14.
- Configurator tabs: 28 (+1 in 9.1) — A 19: ✓ 11, ~ 7, ✗ 1.
- Settings in 8.0.1: **665** (9.1.0: 677; −4 removed/renamed, +16 added, 17 changed default/range/table) — named in the INAV
  track 103, anywhere in the course 156. The number with both a meaning and a default was not measured automatically; 103 is
  the upper bound.
- Modes: 60 permanent ids, 6 named in the course. Features: 23, 2 named. Arming flags: 24, about 6 explained.
- Adjustments: 60 functions, 20 ranges, 4 slots; 0 explained.
- Popular questions: **58** — ✓ 14, ~ 20, ✗ 24.
- Hardware topics: 14 — Yes 0, Partly 4 (servos, PWM/timers, HD video, GPS/compass), No 9, not applicable 1 (CAN).
- Factual problems flagged: 15 (E1–E4, E6, E9, E10 errors; E5, E7, E8, E11, E15 imprecise; E12–E14 version and
  verification notes).
