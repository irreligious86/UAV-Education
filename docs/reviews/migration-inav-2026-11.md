# INAV migration 8.0.1 → 9.1.0 — 2026-11-17

Step M4 of `docs/COURSE-PLAN-THEORY.md`. Previous release: tag **8.0.1** (`/tmp/inavsrc/inav8`, Configurator 8.0.1 in
`/tmp/inav-audit/cfg8`). Target: tag **9.1.0** (`/tmp/inav-audit/inav9`, commit e519b69b; Configurator 9.1.0 in
`/tmp/inav-audit/cfg9`). Nothing was committed, `publish.py` was not run, `i18n/` and generated directories were not
touched. `scripts/validate_content.py`: OK (140 articles, 140 quizzes) after the edits. No SITL build was run: all
pasted lab output stays on 8.0.1 and is labelled.

## 1. Method and sources

- `src/main/fc/settings.yaml` of 8.0.1 and 9.1.0 loaded with `yaml.safe_load`; names, `default_value`, `min`, `max`,
  `table`, and all `tables` compared. To date each change, `settings.yaml` of 8.0.0, 9.0.0 and 9.0.1 and
  `logic_condition.h` of 9.0.0 were fetched from raw.githubusercontent.com. Counts: 665 (8.0.0 = 8.0.1) → 677
  (9.0.0 = 9.0.1 = 9.1.0): 4 removed, 16 added.
- Every setting name that occurs in `content/inav/*`, the INAV quiz/task banks, `setup-cards.html` and the INAV
  sentences of 12 other modules (128 names) was looked up in both releases: only `gps_ublox_nav_hz` and
  `gps_ublox_use_galileo` differ; none was renamed or removed.
- Diffed: `fc/runtime_config.h` (arming flags), `fc/cli.c` (commands, `armingDisableFlagNames`, `outputModeNames`),
  `programming/logic_condition.h`, `io/osd.h`, `fc/fc_msp_box.c`, `io/serial.h`, `msp/msp_protocol*.h`,
  `navigation/navigation*.c`, `flight/imu.c`, `io/gps.c`, `fc/rc_controls.c`, `flight/servos.[ch]`,
  `flight/pid_autotune.c`, `sensors/battery.c`, `fc/config.c`, `io/displayport_msp_osd.c`, `fc/fc_core.c`,
  `cmake/sitl.cmake`, and 24 files under `docs/`.
- Configurator: `tabs/` listing, `tabs/sitl.js`, `tabs/gps.js`, `js/model.js`, `js/migration/*.json`,
  `locale/en/messages.json`.
- Release notes: `9.0.0-Release-Notes.md`, `9.1.0-Release-Notes.md`, `GPS-and-Compass-setup.md` from a clone of
  `iNavFlight/inav.wiki` (the GitHub API returned 403). Release notes were used for the upgrade procedure and
  for intent; every row below is from source unless marked RN.

## 2. Diff-derived table (full)

**C** = row is in the course table (`content/inav/inav-intro.md`, «Переход 8.0 → 9.1: что переименовано и
изменилось», 26 rows).

| # | Item | 8.0.1 | 9.1.0 | Since | Evidence | C |
|---|---|---|---|---|---|---|
| 1 | `controlrate_profile` (battery profile) | present, 0…3 | `use_control_profile` | 9.0 | settings.yaml; `8_to_9.json` | C |
| 2 | `mixer_pid_profile_linking` | present | `mixer_control_profile_linking` | 9.0 | settings.yaml | C |
| 3 | `osd_pan_servo_pwm2centideg` | −36…36, 180° servo = 18 | `osd_pan_servo_range_decadegrees`, same range and scale | 9.0 | settings.yaml descriptions | C |
| 4 | `reboot_character` | 82 | removed (`io/serial.h` field gone; Hayes `+++` escape added) | 9.0 | settings.yaml, serial.h | C |
| 5 | CLI `control_profile` | already `control_profile` (`cli.c` L4878) | same; `docs/Cli.md` changed `profile` → `control_profile`; source files `controlrate_profile.*` → `control_profile.*` | docs 9.1 (PR #11302) | cli.c both tags | C |
| 6 | `gps_ublox_use_galileo`, `gps_ublox_use_beidou` | OFF, OFF | ON, ON (`gps_ublox_use_glonass` stays OFF) | 9.1 | settings.yaml | C |
| 7 | `gps_ublox_nav_hz` | 10 | 8 (range 5…200 unchanged); Configurator GPS tab presets m8 / m9-precision / m9-sport / m10 / m10-highperf / manual, auto-detect by `hwVersion` | 9.1 | settings.yaml, `tabs/gps.js` | C |
| 8 | `inav_w_z_baro_v`, `inav_w_z_gps_p`, `inav_w_z_gps_v` | 0.1, 0.2, 0.1 | 0.35 each (`inav_w_z_baro_p` 0.35 unchanged) | 9.0 | settings.yaml | C |
| 9 | `nav_fw_pos_z_ff` | 10 | 30; new `nav_fw_alt_use_position` (OFF) | 9.0 | settings.yaml, `navigation.c` `navPidInit` | C |
| 10 | `pitot_lpf_milli_hz` | 350, max 10000 | 3000, max 50000 | 9.0 | settings.yaml | C |
| 11 | `fw_tpa_time_constant`, `tpa_rate` max | 1500, 100 | 2000, 200; new `apa_pow` (0, 0…200), `tpa_pitch_compensation` (8, 0…20) | 9.0 | settings.yaml | C |
| 12 | `osd_snr_alarm` max | 99 | 30 | 9.0 | settings.yaml | C |
| 13 | tables `voltage_sensor`, `current_sensor` | — | + `SMARTPORT` | 9.0 | settings.yaml, battery.c | C |
| 14 | `blackbox_arm_control` | — | 0 (−1…60) | 9.0 | settings.yaml, `fc_core.c processBlackbox` | C |
| 15 | `acc_temp_correction`, `baro_temp_correction` | — | 0 (−50…51; 51 = auto-calibration) | 9.0 | settings.yaml | C |
| 16 | `mavlink_sysid`, `mavlink_autopilot_type` | — | 1 (1…255); GENERIC / ARDUPILOT | 9.0 | settings.yaml | C |
| 17 | `osd_adsb_warning_style`, `stats_flight_count`, `transition_pid_mmix_multiplier_roll/pitch/yaw` | — | COMPACT; 0; 1000 | 9.0 | settings.yaml | C |
| 18 | OSD element 26 | `OSD_VARIO_NUM` | `OSD_VERTICAL_SPEED_INDICATOR`; new 167 `OSD_NAV_MIN_GROUND_SPEED`, 168 `OSD_THROTTLE_GAUGE` | 9.0 | `io/osd.h`, `docs/OSD.md` | C |
| 19 | Logic conditions | operations 0–54, flight operands 0–45 | unchanged + 55 `SET_GIMBAL_SENSITIVITY`, 56 `OVERRIDE_MIN_GROUND_SPEED`; operands 46–49 (min ground speed, wind speed, wind direction, relative wind offset); global flag bit 12 | 9.0 | `logic_condition.h` 8.0.1 / 9.0.0 / 9.1.0 | C |
| 20 | Configurator tabs | Programming | + JavaScript Programming (beta warning in the UI); + `firmware_flasher_restore.js`, `led_strip_presets.js` | 9.0 (JS tab), 9.1 (restore) | `tabs/`, `messages.json` | C |
| 21 | Stick command THR high, YAW high, PITCH low | Calibrate Mag | Calibrate Compass / Zero Yaw: with no compass, disarmed, not airplane — yaw set to 0 and heading trusted | 9.1 | `imu.c` L838–848, `isYawZeroResetAllowed()`, `docs/Controls.md` | C |
| 22 | `osd_video_system = HDZERO` | 50×18 with automatic 30×16 sub-mode | 50×18 only; value list unchanged | 9.1 | `displayport_msp_osd.c` | C |
| 23 | Servo autotrim (`FW_AUTOTRIM`) | no I-term check | trims only while I-term rate of change < 30 (`SERVO_AUTOTRIM_ITERM_RATE_LIMIT`); the setting `servo_autotrim_iterm_rate_limit` existed only in 9.1.0-RC1 | 9.1 | `servos.c`, `servos.h`, RN | C |
| 24 | CLI command `bind_msp_rx` | — | added | 9.1 | cli.c | C |
| 25 | MSP v1 | — | 19 commands commented DEPRECATED, removal in 10.0 (16, 17, 80, 81, 84, 85, 92–95, 101, 110, 114, 117, 150, 207, 241, 242, 254); 105 and 200 untouched | 9.1 | `msp_protocol.h` | C |
| 26 | Configurator backup | manual | auto-backup before flashing, restore with migration preview (`7_to_8.json`, `8_to_9.json`) | 9.1 | `docs/Backup and Restore.md`, `js/migration` | C |
| 27 | `msp_override_channels` max | 65535 | UINT32_MAX | 9.0 | settings.yaml | — |
| 28 | tables `acc_hardware`, `mag_hardware`, `pitot_hardware` | — | + ICM45686 (9.1), QMC5883P (9.0), MS5525 (9.1) | 9.0 / 9.1 | settings.yaml | — |
| 29 | `gimbal_pan_trim`, `gimbal_tilt_trim`, `gimbal_sensitivity` | no explicit type | `int16_t` / `int8_t` | 9.0 | settings.yaml | — |
| 30 | New MSP2 | — | `MSP2_INAV_SET_WP_INDEX` 0x2221, `SET_CRUISE_HEADING` 0x2223, `SET_AUX_RC` 0x2230, `SET_GVAR` 0x2214, `FULL_LOCAL_POSE` 0x2220, `GET_LINK_STATS` 0x2103, `LOGIC_CONDITIONS_CONFIGURED` 0x203C, `OSD_UPDATE_POSITION` 0x2118 | 9.x | `msp_protocol_v2_inav.h` | — |
| 31 | `updateArmingStatus()` | every loop | 200 Hz | 9.1 | `fc_core.c` | — |
| 32 | Throttle servo when disarmed | forced to `min_command` | computed through the mixer with throttle at minimum (fix for reversed throttle servos) | 9.1 | `servos.c` | — |
| 33 | Configurator SITL profile name | «[Standard] Confgurator» | «[Standard] Configurator»; channel maps unchanged | 9.x | `tabs/sitl.js` | in `inav-setup-wing` |
| 34 | `docs/Autotune - fixedwing.md` | said PIFF gains are learned | states FF only, rates only in ACRO/HORIZON and unless `fw_autotune_rate_adjustment = FIXED`; code unchanged | 9.1 | docs diff, `pid_autotune.c` | in `inav-setup-wing` |
| 35 | SITL docs | INAV-X-Plane-HITL | + INAV-X-Plane-XITL plugin; gcc 13 or later recommended | 9.1 | `docs/SITL/*`, `Building SITL.md` | in `inav-setup-scratch` |
| 36 | HITL flags | up to bit 9 | bits 10–14 (current sensor, RC input, rangefinder, failsafe, SITL mode), `SIMULATOR_MSP_VERSION_3` | 9.1 | `runtime_config.h` | — |

Unchanged (verified): arming flags enum and CLI names; flight-mode box ids (ARM 0, ANGLE 1, NAV ALTHOLD 3, NAV RTH 10,
NAV POSHOLD 11, FAILSAFE 27); serial function bits (`FUNCTION_MSP_OSD` 1 << 25, `FUNCTION_VTX_FFPV` 1 << 17);
`osd_video_system` values and grids; all `nav_rth_*`, `nav_fw_launch_*`, `nav_fw_land_*`, `geozone_*`, `failsafe_*`,
`safehome_*` settings; `wp` actions and flag 0xA5; 64 logic conditions, 8 GVAR, 4 programming PIDs, 10 Hz task;
`battery.c` voltage and current formulas; `#if !defined(USE_DSHOT)` → MULTISHOT in `config.c`; `model.js` presets
Quad X and Flying Wing; OSD arming messages.

## 3. Facts of `inav-fixes-2026-11-15.md` re-checked on 9.1.0

| Item | 9.1.0 | Course |
|---|---|---|
| E4 HD OSD map | same values and grids; HDZero 30×16 sub-mode removed; `enable_broken_o4_workaround` still present | wording inverted (9.1 primary) |
| E1 `getActiveSpeed()` rules | unchanged | unchanged |
| E2 GPS heading: 3D fix, ≥ 6 sats, ≥ 3 m/s; "no stick command for heading" | `isGPSHeadingValid()` unchanged; **a stick command now exists** for multirotors without a compass | `inav-gps`, `inav-intro` rewritten |
| E8 baro "strongly recommended" | `canActivateAltHoldMode()` and `inav_default_alt_sensor` unchanged | unchanged |
| E11 safehome / `inav_reset_home` | unchanged | unchanged |
| E12 `fixed_wing_auto_arm` | unchanged (`rc_controls.c` diff touches only throttle status) | unchanged |
| E3, E15 `nav_position_timeout` 5, `nav_emerg_landing_speed` 500, emergency landing, GPS fix estimation | unchanged (doc only spelling fixes) | unchanged |
| E9 first-WP block and yaw bypass, `nav_extra_arming_safety` ALLOW_BYPASS | unchanged | "дефолт в 9.1, как и в 8.0" |
| E10 `nav_fw_bank_angle` 35 | unchanged | unchanged |
| E5 `timer_output_mode` AUTO / MOTORS / SERVOS / LED | unchanged | header "INAV 9.1" |
| E6 `logic 0 1 -1 2 2 1 0 100 0`, `logic 1 1 0 25 0 3 0 0 0` | numbers valid | 9.1 primary, 8.0.1 as the note |
| E7 GVAR bounds | `global_variables.c` identical | unchanged |
| E13 defaults note in front matter | — | moved into the migration table and module text |
| `throttle_idle` 8, `motorstop_on_low` ON, `gyro_main_lpf_hz` 60, `failsafe_fw_*` −200 / 100 / −45, `mag_calibration_time` 30, `gps_min_sats` 6 | unchanged | "9.1 (так с 8.0)" |

## 4. Files changed (18 files, 67 replacements)

| File | Edits | What |
|---|---|---|
| `content/inav/inav-intro.md` | 8 | front matter; compass requirement (2 places); OSD arming texts; «Версии и совместимость» rewritten with the 7-step upgrade procedure; new `###` table (26 rows + "unchanged" line); diagnostics; practice step 2; +4 references |
| `content/inav/inav-gps.md` | 5 | front matter; compass bullet (magless navigation, 9.1 zero-yaw command); heading note for wings; `inav_w_z_*` defaults; GPS tab and 9.1 GNSS defaults |
| `content/inav/inav-ipf.md` | 4 | front matter; operations 55–56, operands 46–49, JavaScript Programming tab; step 2 inverted; diagnostics |
| `content/inav/inav-missions.md` | 2 | front matter; ALLOW_BYPASS note |
| `content/inav/inav-wing.md` | 2 | front matter; `nav_fw_alt_use_position`, `nav_fw_pos_z_ff`, `apa_pow`, `tpa_pitch_compensation` |
| `content/inav/inav-setup-scratch.md` | 17 | front matter; 4 "вывод снят на 8.0.1" notes; battery.c version; Configurator 9.1; GNSS defaults; OSD; references to 9.1.0; +1 reference |
| `content/inav/inav-setup-wing.md` | 6 | front matter; SITL profile name; `model.js` version; motorstop/idle wording; autotrim I-term check; autotune wording |
| `content/quiz/inav-intro.json`, `inav-ipf.json`, `inav-setup-scratch.json`, `inav-setup-wing.json` | 1, 1, 1, 2 | `explain` texts, one question stem ("INAV 9.1"), one distractor; answers and option counts unchanged |
| `content/pages/setup-cards.html` | 9 | INAV card and its wing variant only, plus the INAV part of the shared footnote |
| `content/betaflight/bf-hd-osd-video.md` | 3 | INAV part of `firmware:`, table header, one sentence |
| `content/betaflight/bf-servos-pwm.md` | 2 | table header "INAV 9.1", reference to 9.1.0 `settings.yaml` |
| `content/link/link-digital-video.md`, `content/design/aero-stability.md` | 1, 1 | INAV part of `firmware:` |
| `content/link/link-elrs.md`, `content/estimation/est-gnss.md` | 1, 1 | "(сверено с 9.1.0)"; Galileo default |

Quiz question counts: unchanged (8 in each of the 7 INAV banks). Task banks: not changed. Code fence counts:
unchanged in every edited module. Section structure, `related` / `next`: unchanged.

## 5. Left on 8.0.1

| Item | Where | Reason |
|---|---|---|
| SITL build commands and console output (`-b 8.0.1`, `./inav_8.0.1_SITL`, `INAV 8.0.1 SITL (ae47bcba)`), 19 s build time | `inav-setup-scratch` step 1 | pasted output depends on the command; note gives the 9.1.0 tag and file name (file name derived from `cmake/sitl.cmake`, not built) |
| `Arming disabled flags`, `MSP_RC` output, MULTISHOT reply, `diff all` fragment, "56 command lines" | `inav-setup-scratch` steps 4–6, 17 | lab output; phase 2 re-runs it |
| "INAV-X-Plane-HITL supports Airplane only" | `inav-setup-scratch` theory | marked "проверено на 8.0.1" |
| 8.0.1 release notes reference (DJI O4 / `DJI_NATIVE`) | `inav-setup-scratch` references | the fact comes from that release |
| `INAV 6.1.0 SITL` console sample | `inav-setup-wing` step 1 | quoted from `docs/SITL/SITL.md`, identical in 9.1.0 |

## 6. Could not verify / open questions

1. No 9.1.0 SITL was built or run: binary name, first console line and unchanged arming-flag output are inferred
   from source.
2. Whether INAV-X-Plane-XITL supports multirotors (its README was read; it does not say).
3. The Configurator 9.1 restore/migration flow was read from `docs/Backup and Restore.md` and `js/migration`, not
   exercised.
4. Release notes 9.0.0 and `8_to_9.json` say `ahrs_acc_ignore_rate` default went 20 → 15; in source it is 15 in
   8.0.1 already. Not put into the course.
5. `docs/reviews/community-faq-coverage-2026-11.md` V21 ("`profile` command not found — renamed to `control_profile`
   in 9.1") and row 6 ("`servo_autotrim_iterm_rate_limit` removed") do not match source: the CLI command is
   `control_profile` in 8.0.1 already, and that setting never existed in 8.0.1 or 9.1.0. The course table states
   the source-derived version; the FAQ study itself was not edited.
6. "RTH requires GPS, compass and baro" stays in `inav-setup-scratch`, the setup card and one quiz question because
   `docs/Failsafe.md` 9.1.0 still says so, while `imu.c` allows multirotor navigation with GPS-derived or zeroed
   heading. Both are now stated; flight behaviour without a compass was not tested.
7. `DJI_NATIVE` with an O3 air unit: still unverified (as in the 2026-11-15 notes).
8. Generic sentences in other tracks were left as they are: `f-fc-sensors` ("баро и компас для INAV/ArduPilot
   обязательны"), `est-alt-sources`, `nav-resilience`, `aero-wing`, `f-mechanics`, `diag-troubleshooting`
   (already on 9.1). Their INAV settings exist unchanged in 9.1.0.
9. `setup-cards.html` footnote still says "Copter-4.6.3" — ArduPilot part, not touched.
10. `docs/COURSE-PLAN-THEORY.md` still lists M4 as "in progress"; not edited.
