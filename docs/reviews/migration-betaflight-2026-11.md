# Betaflight migration 4.5.3 → 2025.12 (Phase 0, step M2) — 2026-11-17

Scope: Betaflight 4.5.3 (previous significant release; course previously verified on tag 4.5.5 / branch 4.5.6) →
2025.12 line, latest patch 2025.12.5. The 2026.6 tags are not the target and are mentioned in the course only where a
student trips (ELRS 4 for SPI receivers, removed `gps_rescue_velocity_*`, IIM-42652 range).
Not committed, `scripts/publish.py` not run. `scripts/validate_content.py`: OK (140 articles, 140 quizzes, 0 errors).
`i18n/` and generated directories untouched. `content/link/link-elrs.md` untouched.

## 1. Sources and method

| What | Where | Used for |
|---|---|---|
| Source 4.5.3 | `/tmp/bf-migrate/bf453` (tag `4.5.3`, shallow, commit `0e533ba`) | old side of every comparison |
| Source 2025.12.5 | `/tmp/bf-migrate/bf2025` (tag `2025.12.5`, shallow, commit `7348054`, `version.h` 2025.12.5) | target |
| Source 4.5.5 | `/tmp/bf-migrate/bf455` (tag `4.5.5`, shallow) | patch-level check inside 4.5.x |
| 2025.12 release notes | betaflight.com `Betaflight-2025-12-Release-Notes` (fetched 2026-11-17) | App/PWA, calendar versioning, IST8310 address, gyro alignment note |
| Earlier notes | `betaflight-coverage-audit.md` §1.3, `factcheck/stage6-betaflight-A.md`, `-B.md`, `community-faq-coverage-2026-11.md` §6.3 | list of expected renames, community questions V3, V7–V12 |

Nothing was built. Checks (scripts in the session scratchpad, not in the repository):

1. `cli/settings.c` `valueTable[]` parsed in both trees (name, type, min/max or lookup table, PG, struct field;
   names resolved through `fc/parameter_names.h`): 683 → 759 parsed entries (the audit counted 760 raw lines).
2. Lookup tables in `settings.c` compared by content.
3. Every `PG_RESET_TEMPLATE` / `pgResetFn_*` / `resetPidProfile` block compared line by line; macros used in those
   blocks and in `settings.c` compared by value (`DYN_NOTCH_COUNT_MAX` 5 → 7, `PID_*_DEFAULT`, `D_MIN_DEFAULT` →
   `D_MAX_DEFAULT`).
4. `cli.c` command table, `featureNames[]`, `cliFeature()`, `cliSerial()`, `cliRcSmoothing()`, `cliStatus()` GPS line.
5. `fc/runtime_config.[ch]` (arming flags), `fc/rc_adjustments.[ch]`, `msp/msp_box.c` + `fc/rc_modes.h`,
   `io/beeper.[ch]`, `osd/osd.h` (warning and element enums), `io/serial.h`, `build/debug.c`, `io/ledstrip.h`.
6. Behaviour read in 2025.12.5 where the course states behaviour: `fc/rc.c` (RC smoothing, feedforward, throttle
   curve, rates), `flight/pid_init.c`, `flight/pid.c` (`pidLevel`, horizon, acro trainer, launch control, crash
   recovery, I-term limit), `flight/mixer.c` + `mixer_init.c` (crashflip, dynamic idle, mixing), `fc/core.c`
   (crashflip arming flow, runaway takeoff, new flags), `flight/failsafe.c` (RX_LOST condition), `io/beeper.c`
   (warning beeps, DShot beacon), `flight/servos.[ch]`, `io/serial.c` (`isSerialConfigValid`), `telemetry.c`,
   `sensors/voltage.c`, `current.c`, `io/gps.c` (spot checks only, see §6), `flight/position.c`, `flight/imu.c`.
7. 379 `set` variables are named somewhere in `content/`; names that exist only in 4.5.3 were listed per file and
   migrated (§5). After the sweep an old name appears only next to its new name, inside a labelled lab block, or in
   the migration table.

4.5.3 vs 4.5.5: `settings.c` identical. Outside drivers/targets the only user-visible difference is `noreboot` for
`save` / `exit` (4.5.4), confirmed in `cli.c`.

## 2. Size of the diff

| Item | 4.5.3 | 2025.12.5 | Notes |
|---|---|---|---|
| `set` variables (parsed) | 683 | 759 | −37, +113, 10 changed type/range/lookup |
| CLI commands | 59 | 59 | same set; `flash_read` argument order; `save`/`exit` `[noreboot]` already in 4.5.4 |
| Arming-disable flags | 26 | 29 | +`FLIP_SWITCH`(25) `ALT_HOLD_SW`(26) `POS_HOLD_SW`(27); `ARMSWITCH`(25) → `ARM_SWITCH`(28) |
| Adjustment functions (CLI) | 0–30 | 0–31 | +31 `LED_DIMMER`; labels `LED PROFILE`, `LED DIMMER` added |
| Mode permanentIds | 0–54 | 0–55 | +3 ALTHOLD, +11 POS HOLD, +55 CHIRP; 29 renamed `3D DISABLE` |
| Beeper conditions | 24 + ALL | 23 + ALL | `CRASH_FLIP` → `CRASHFLIP`, `RC_SMOOTHING_INIT_FAIL` removed, masks shift |
| OSD warnings | 19 | 19 | `RC_SMOOTHING` (bit 8) removed, bits 9–18 shift down, `POSHOLD_FAILED` at 18 |
| Debug modes | 90 | 100 | `GYRO_SCALED` removed, 4 renamed, 11 added |
| Serial functions | up to 1<<17 | +`GIMBAL` 1<<18 | `serial` prints/accepts port names |
| Features | 22 names | 22 names | −`RX_MSP` name, +`OPTICALFLOW`; `feature` prints Enabled/Available/Unavailable |

## 3. Migration table (course rows)

The table in `content/betaflight/bf-intro.md` (`### Переход 4.5.3 → 2025.12: что переименовано и изменилось`, 43 data
rows, preceded by an 8-step upgrade procedure) carries these rows. "Since" is 2025.12 for all rows except `noreboot`
(4.5.4); the first 2025.12 patch that carried each change was not determined (only 2025.12.5 was read).

| Old (4.5.3) | New (2025.12.5) | Change |
|---|---|---|
| `d_min_roll/pitch/yaw` 30/34/0 | `d_roll/pitch/yaw` 30/34/0 | `d_*` is now base D |
| `d_roll/pitch/yaw` 40/46/0 | `d_max_roll/pitch/yaw` 40/46/0 | peak D renamed; `d_max_gain` 37, `d_max_advance` 20 unchanged |
| `simplified_dmax_gain` | `simplified_d_max_gain` | name |
| `iterm_limit` 400 | — | removed |
| `iterm_windup` 85, 30–100 | 80, 20–100 | meaning changed: I cap as % of `pidsum_limit` |
| `dshot_idle_value` 550 | `motor_idle` 550 | name; brushed default 700; also sets PWM idle |
| `min_throttle` 1070 | — | removed |
| `dyn_idle_start_increase` 50 | — | removed; pre-takeoff limit = `motor_idle` |
| `feedforward_averaging` OFF / `feedforward_smooth_factor` 25 | 2_POINT / 65 | defaults; smoothing is a PT1 normalised to 250 Hz |
| — | `feedforward_yaw_hold_gain` 15, `feedforward_yaw_hold_time` 100 | new |
| `rc_smoothing_feedforward_cutoff` | — | removed; FF uses the setpoint cutoff |
| — | `thr_hover` 50 | throttle curve is two Bezier segments through (`thr_mid`, `thr_hover`) |
| `tpa_mode` PD/D | + PDS | `tpa_low_rate` signed and `tpa_curve_*`/`tpa_speed_*` only with USE_WING |
| `angle_limit` 10–85 | 10–80 | range; `angle_pitch_offset` (WING) |
| `dyn_notch_count` 0–5 | 0–7 | range |
| `debug_mode` GYRO_SCALED | — (field `gyroUnfilt`) | removed; DUAL_GYRO_* → MULTI_GYRO_*, D_MIN → D_MAX, GPS_RESCUE_THROTTLE_PID → AUTOPILOT_ALTITUDE |
| `failsafe_off_delay` 10 (0.1 s), 0–200 | `failsafe_landing_time` 60 (s), 0–250 | name, unit, default |
| `gps_rescue_throttle_hover/min/max` 1275/1100/1700 | `ap_hover_throttle` 1275 (1100–1700), `ap_throttle_min` 1100 (1050–1400), `ap_throttle_max` 1700 (1400–2000) | shared autopilot PG |
| `gps_rescue_throttle_p/i/d` 15/15/20 | `ap_altitude_p/i/d/f` 15/15/15/15 (0–200) | shared altitude controller |
| `gps_rescue_landing_alt` 4 (1–15) | `ap_landing_altitude_m` 4 (0–200) | name, range |
| `gps_rescue_disarm_threshold` 20 | 30 | default |
| `gps_rescue_velocity_p/i/d`, `gps_rescue_yaw_p` 0–255 | 0–200 | range |
| `gps_provider` NMEA/UBLOX/MSP | + VIRTUAL | GPS baud table gains 230400 |
| `mag_declination` 0–3599 | −300…300 | type and range |
| — | `alt_hold_*`, `pos_hold_*`, `ap_position_*`, `ap_max_angle` | new modes ALTHOLD, POS HOLD |
| — | `landing_disarm_threshold` 0 | new |
| — | `prearm_allow_rearm` OFF | new |
| `ARMSWITCH` bit 25 (26 flags) | `ARM_SWITCH` bit 28 (29 flags) | + FLIP_SWITCH, ALT_HOLD_SW, POS_HOLD_SW |
| beeper `CRASH_FLIP`, `RC_SMOOTHING_INIT_FAIL` | `CRASHFLIP`, — | ALL 24 → 23 |
| OSD warning `RC_SMOOTHING` (bit 8) | — | `osd_warn_bitmask` bits shift; `POSHOLD_FAILED` bit 18 |
| `crashflip_expo` 35 | `crashflip_rate` 0 (0–250), `crashflip_auto_rearm` OFF | different turtle algorithm; RACE_PRO defaults 30 / ON |
| `launch_control_mode` NORMAL | PITCHONLY | default |
| adjustments 0–30 | + 31 LED_DIMMER | |
| mode 29 "3D DISABLE / SWITCH" | "3D DISABLE" | + ids 3, 11, 55 |
| `serial 2 64 …` | `serial UART3 64 …` | names printed, legacy numbers accepted |
| `save`, `exit` | `[noreboot]` | since 4.5.4 |
| `flash_read <length> <address>` | `<address> <length>` | |
| `gyro_to_use` | `gyro_enabled_bitmask`, `gyro_N_enabled` | `gyro_1_*`/`gyro_2_*` alignment and bus variables removed |
| `dshot_edt` OFF/ON | OFF/ON/FORCE | |
| `expresslrs_rate_index`, `expresslrs_switch_mode` | — | removed |
| `serialrx_provider` | + MAVLINK | |
| `blackbox_device` | + VIRTUAL | + `blackbox_disable_attitude`, `blackbox_disable_servos` |
| serial function mask | + GIMBAL 262144 | |
| IST8310 I2C 0x0C | 0x0E | driver default |
| Betaflight Configurator 10.10 | Betaflight App 2025.12 | from release notes |

Behaviour changes found while reading 2025.12.5 that are not `set` renames and are now stated in the modules:

- `feature` / `feature list` print three lines (Enabled / Available / Unavailable); enabling an unbuilt feature answers `Unavailable`.
- `rc_smoothing_info` prints four lines ("RC Smoothing: ON", "Active setpoint and FF cutoff"); RX-rate outlier rule
  20 %, cutoffs updated every 3rd valid sample, estimate held on signal loss, interval window 800…65 500 µs.
- Feedforward: linear jitter attenuator `min(1, ((Δ+Δprev)/2 + 1)/(1 + jitter))`, PT1 smoothing with
  τ = 4 ms·s/(1−s), yaw hold instead of boost/limit on yaw, duplicate-packet interpolation off for CRSF.
- Arming warning beeps: 4 fast beeps before the code (`WARNING_FLASH_COUNT − 1`), 5 in 4.5.
- RX_LOST beeper: `!receivingRxData && !usbCableIsInserted()` (4.5: armed or was ever armed).
- DShot beacon: single 450 ms interval, RX_LOST beacon suppressed with USB, RX_SET beacon only with a live link.
- Crashflip: reverting the switch while armed disarms and sets `FLIP_SWITCH` (auto-rearm OFF) or continues armed with
  normal spin direction (ON); power linear above a 15 % deadband, stop below 2 %, full stick = 2047; OSD texts
  `CRASHFLIP SW` / `>CRASH FLIP<`.
- Dynamic idle: limit before throttle is first raised = `motor_idle × 0.0001`.
- I-term limit = `iterm_windup` % × `pidsum_limit` (80 % × 500 = 400 on roll/pitch, same number as the old `iterm_limit`).
- Unchanged and now stated as such: rates formulas, `pidLevel`/Horizon/acro trainer/launch control maths (for
  multirotors), runaway takeoff logic, `rc_adjustments.c` logic, servo maths, `isSerialConfigValid`, OSD position
  macros, battery ADC formulas, mixer functions, `vtx_*`, RPM filter and filter defaults, OSD alarm defaults.

## 4. Full `set` diff (including names the course does not use)

**(course)** marks names used in `content/`.

### 4.1 Removed (37)

- `gyro_to_use` { TABLE_GYRO }
- `rc_smoothing_feedforward_cutoff` { 0, UINT8_MAX } **(course)**
- `min_throttle` { PWM_PULSE_MIN, PWM_PULSE_MAX } **(course)**
- `dshot_idle_value` { 0, 2000 } **(course)**
- `failsafe_off_delay` { 0, 200 } **(course)**
- `crashflip_expo` { 0, 100 } **(course)**
- `gps_rescue_landing_alt` { 1, 15 } **(course)**
- `gps_rescue_throttle_min` { 1000, 2000 }
- `gps_rescue_throttle_max` { 1000, 2000 }
- `gps_rescue_throttle_hover` { 1000, 2000 } **(course)**
- `gps_rescue_throttle_p` { 0, 255 }
- `gps_rescue_throttle_i` { 0, 255 }
- `gps_rescue_throttle_d` { 0, 255 }
- `iterm_limit` { 0, 500 } **(course)**
- `d_min_roll` { 0, D_MIN_GAIN_MAX } **(course)**
- `d_min_pitch` { 0, D_MIN_GAIN_MAX } **(course)**
- `d_min_yaw` { 0, D_MIN_GAIN_MAX }
- `dyn_idle_start_increase` { 10, 255 } **(course)**
- `simplified_dmax_gain` { 0, SIMPLIFIED_TUNING_MAX } **(course)**
- `gyro_1_bustype` { TABLE_BUS_TYPE }
- `gyro_1_spibus` { 0, SPIDEV_COUNT }
- `gyro_1_i2cBus` { 0, I2CDEV_COUNT }
- `gyro_1_i2c_address` { 0, I2C_ADDR7_MAX }
- `gyro_1_sensor_align` { TABLE_ALIGNMENT }
- `gyro_1_align_roll` minmax = { -3600, 3600 }
- `gyro_1_align_pitch` minmax = { -3600, 3600 }
- `gyro_1_align_yaw` minmax = { -3600, 3600 }
- `gyro_2_bustype` { TABLE_BUS_TYPE }
- `gyro_2_spibus` { 0, SPIDEV_COUNT }
- `gyro_2_i2cBus` { 0, I2CDEV_COUNT }
- `gyro_2_i2c_address` { 0, I2C_ADDR7_MAX }
- `gyro_2_sensor_align` { TABLE_ALIGNMENT }
- `gyro_2_align_roll` minmax = { -3600, 3600 }
- `gyro_2_align_pitch` minmax = { -3600, 3600 }
- `gyro_2_align_yaw` minmax = { -3600, 3600 }
- `expresslrs_rate_index` { 0, 3 } **(course)**
- `expresslrs_switch_mode` { TABLE_SWITCH_MODE } **(course)**

### 4.2 Added (113)

- **gyro** (9): `gyro_enabled_bitmask`, `gyro_1_enabled`, `gyro_2_enabled`, `gyro_3_enabled`, `gyro_4_enabled`, `gyro_5_enabled`, `gyro_6_enabled`, `gyro_7_enabled`, `gyro_8_enabled`
- **blackbox** (2): `blackbox_disable_attitude`, `blackbox_disable_servos`
- **other** (12): `motor_idle` (course), `failsafe_landing_time` (course), `thr_hover` (course), `prearm_allow_rearm` (course), `simplified_d_max_gain` (course), `landing_disarm_threshold` (course), `yaw_type`, `angle_pitch_offset` (course), `i2c0_pullup`, `i2c0_clockspeed_khz`, `scheduler_debug_task`, `stats_save_move_limit`
- **crashflip** (2): `crashflip_rate` (course), `crashflip_auto_rearm` (course)
- **alt** (2): `alt_hold_climb_rate`, `alt_hold_deadband`
- **pos** (2): `pos_hold_without_mag`, `pos_hold_deadband`
- **s** (3): `s_pitch`, `s_roll`, `s_yaw`
- **chirp** (8): `chirp_lag_freq_hz`, `chirp_lead_freq_hz`, `chirp_amplitude_roll`, `chirp_amplitude_pitch`, `chirp_amplitude_yaw`, `chirp_frequency_start_deci_hz`, `chirp_frequency_end_deci_hz`, `chirp_time_seconds`
- **d** (3): `d_max_roll` (course), `d_max_pitch` (course), `d_max_yaw`
- **feedforward** (2): `feedforward_yaw_hold_gain` (course), `feedforward_yaw_hold_time` (course)
- **tpa** (14): `tpa_speed_type`, `tpa_speed_basic_delay`, `tpa_speed_basic_gravity`, `tpa_speed_adv_prop_pitch`, `tpa_speed_adv_mass`, `tpa_speed_adv_drag_k`, `tpa_speed_adv_thrust`, `tpa_speed_max_voltage`, `tpa_speed_pitch_offset`, `tpa_curve_type`, `tpa_curve_stall_throttle`, `tpa_curve_pid_thr0`, `tpa_curve_pid_thr100`, `tpa_curve_expo`
- **spa** (9): `spa_roll_center`, `spa_roll_width`, `spa_roll_mode`, `spa_pitch_center`, `spa_pitch_width`, `spa_pitch_mode`, `spa_yaw_center`, `spa_yaw_width`, `spa_yaw_mode`
- **mavlink** (7): `mavlink_min_txbuff`, `mavlink_ext_status_rate`, `mavlink_rc_chan_rate`, `mavlink_pos_rate`, `mavlink_extra1_rate`, `mavlink_extra2_rate`, `mavlink_extra3_rate`
- **osd** (3): `osd_arming_logo`, `osd_debug2_pos`, `osd_lidar_dist_pos`
- **opticalflow** (4): `opticalflow_hardware`, `opticalflow_rotation`, `opticalflow_lpf`, `opticalflow_flip_x`
- **ap** (14): `ap_landing_altitude_m`, `ap_hover_throttle`, `ap_throttle_min`, `ap_throttle_max`, `ap_altitude_p`, `ap_altitude_i`, `ap_altitude_d`, `ap_altitude_f`, `ap_position_p`, `ap_position_i`, `ap_position_d`, `ap_position_a`, `ap_position_cutoff`, `ap_max_angle`
- **gimbal** (17): `gimbal_roll_rc_gain`, `gimbal_pitch_rc_thr_gain`, `gimbal_pitch_rc_low_gain`, `gimbal_pitch_rc_high_gain`, `gimbal_yaw_rc_gain`, `gimbal_roll_gain`, `gimbal_roll_offset`, `gimbal_roll_limit`, `gimbal_pitch_gain`, `gimbal_pitch_offset`, `gimbal_pitch_low_limit`, `gimbal_pitch_high_limit`, `gimbal_yaw_gain`, `gimbal_yaw_offset`, `gimbal_yaw_limit`, `gimbal_stabilisation`, `gimbal_sensitivity`

Defaults of the added names that matter to the course: `motor_idle` 550; `failsafe_landing_time` 60; `crashflip_rate` 0,
`crashflip_auto_rearm` OFF; `thr_hover` 50; `prearm_allow_rearm` OFF; `alt_hold_climb_rate` 50, `alt_hold_deadband` 20;
`pos_hold_without_mag` OFF, `pos_hold_deadband` 5; `d_max_*` 40/46/0; `feedforward_yaw_hold_gain` 15, `_time` 100;
`landing_disarm_threshold` 0; `ap_landing_altitude_m` 4, `ap_hover_throttle` 1275, `ap_throttle_min` 1100,
`ap_throttle_max` 1700, `ap_altitude_p/i/d/f` 15, `ap_position_p/i/d/a` 30, `ap_position_cutoff` 80, `ap_max_angle` 50;
`chirp_*` 3/30/230/230/180/2/6000/20; `mavlink_min_txbuff` 35, rates 2/1/2/2/2/1; `stats_save_move_limit` 20;
`tpa_curve_*` CLASSIC/30/200/70/20; `tpa_speed_*` BASIC/1000/50/370/1000/1000/2000/2520/0; `yaw_type` RUDDER;
`gimbal_*` as in `gimbalTrackConfig` reset.

### 4.3 Changed type, range or lookup (10)

| Name | 4.5.3 | 2025.12.5 |
|---|---|---|
| `dshot_edt` | OFF/ON | OFF/ON/FORCE |
| `mag_declination` | uint16 0–3599 | int16 −300…300 |
| `gps_rescue_velocity_p/i/d`, `gps_rescue_yaw_p` | 0–255 | 0–200 |
| `iterm_windup` | 30–100 | 20–100 |
| `angle_limit` | 10–85 | 10–80 |
| `tpa_low_rate` | uint8 0–100 | int8, min `TPA_LOW_RATE_MIN` (0, or −128 with USE_WING) |
| `led_inversion` | mask of `STATUS_LED_NUMBER` | mask of `STATUS_LED_COUNT` (no user-visible change) |
| `dyn_notch_count` | 0–5 | 0–7 (macro) |

### 4.4 Lookup tables

`acc_hardware`: −ADXL345, MMA8452, BMA280, LSM303DLHC; +IIM42653, ICM45605, ICM45686, ICM40609D, IIM42652.
`gyro_hardware`: −L3G4200D, MPU3050; + the same five. `blackbox_device` +VIRTUAL. `gps_provider` +VIRTUAL.
`rangefinder_hardware` +MTF01, MTF02, MTF01P, MTF02P, TFNOVA. `serialrx_provider` +MAVLINK. `tpa_mode` +PDS.
`cpu_overclock` +3 entries. New tables: DSHOT_EDT, OPTICALFLOW_HARDWARE (NONE, MT), SPA_MODE. Removed: GYRO
(FIRST/SECOND/BOTH).

### 4.5 Default changes among names present in both

`d_roll` 40 → 30, `d_pitch` 46 → 34 (meaning inverted), `iterm_windup` 85 → 80, `launch_control_mode` NORMAL →
PITCHONLY, `feedforward_averaging` OFF → 2_POINT, `feedforward_smooth_factor` 25 → 65, `gps_rescue_disarm_threshold`
20 → 30; `yaw_motors_reversed` and `align_mag`/`mag_align_*` now take board-config macros (`YAW_MOTORS_REVERSED`,
`MAG_ALIGN*`). Removed from reset code: `alt_hold_deadband` 40 / `alt_hold_fast_change` 1 in `rcControlsConfig`
(internal, no CLI name in 4.5.3).

## 5. Files changed (54 files, 495 edits)

An edit is one exact-string replacement (a replaced paragraph or table row counts once).

| Edits | File |
|---|---|
| 45 | `content/betaflight/bf-arming-safety.md` |
| 44 | `content/betaflight/bf-features-tour.md` |
| 35 | `content/betaflight/bf-setup-scratch.md` |
| 32 | `content/betaflight/bf-rates-rc.md` |
| 30 | `content/betaflight/bf-adjustments.md` |
| 27 | `content/betaflight/bf-gps-setup.md` |
| 24 | `content/betaflight/bf-intro.md` |
| 22 | `content/betaflight/bf-led-buzzer.md` |
| 22 | `content/betaflight/bf-pid-reg-in-bf.md` |
| 19 | `content/betaflight/bf-hd-osd-video.md` |
| 19 | `content/betaflight/bf-servos-pwm.md` |
| 11 | `content/betaflight/bf-cli.md` |
| 11 | `content/pages/setup-cards.html` |
| 11 | `content/quiz/bf-rates-rc.json` |
| 9 | `content/betaflight/bf-modes-osd.md` |
| 9 | `content/betaflight/bf-ports.md` |
| 9 | `content/quiz/bf-features-tour.json` |
| 8 | `content/betaflight/bf-blackbox.md` |
| 8 | `content/betaflight/bf-filters.md` |
| 8 | `content/quiz/bf-arming-safety.json` |
| 8 | `content/quiz/bf-led-buzzer.json` |
| 7 | `content/betaflight/bf-failsafe.md` |
| 7 | `content/betaflight/bf-pid.md` |
| 7 | `content/quiz/bf-gps-setup.json` |
| 4 | `content/betaflight/bf-cli-automation.md` |
| 4 | `content/quiz/bf-adjustments.json` |
| 4 | `content/quiz/bf-hd-osd-video.json` |
| 4 | `content/quiz/bf-servos-pwm.json` |
| 4 | `content/quiz/bf-setup-scratch.json` |
| 4 | `content/tasks/bf-features-tour.json` |
| 3 | `content/tasks/bf-gps-setup.json` |
| 2 | `content/betaflight/bf-custom.md` |
| 2 | `content/betaflight/bf-rpm-filter.md` |
| 2 | `content/companion/fw-reading.md` |
| 2 | `content/design/ctl-allocation.md` |
| 2 | `content/foundation/f-esc-firmware.md` |
| 2 | `content/foundation/f-safety.md` |
| 2 | `content/link/link-digital-video.md` |
| 2 | `content/link/link-vtx.md` |
| 2 | `content/quiz/bf-cli-automation.json` |
| 2 | `content/quiz/bf-filters.json` |
| 2 | `content/tasks/bf-adjustments.json` |
| 2 | `content/tasks/bf-arming-safety.json` |
| 2 | `content/tasks/bf-rates-rc.json` |
| 1 | `content/foundation/diag-troubleshooting.md` |
| 1 | `content/foundation/f-fc-sensors.md` |
| 1 | `content/quiz/bf-blackbox.json` |
| 1 | `content/quiz/bf-ports.json` |
| 1 | `content/quiz/f-safety.json` |
| 1 | `content/tasks/bf-hd-osd-video.json` |
| 1 | `content/tasks/bf-servos-pwm.json` |
| 1 | `content/tasks/bf-setup-scratch.json` |
| 1 | `content/tools/ctl-theory.md` |
| 1 | `content/tools/data-python.md` |

Front matter `firmware:` → `Betaflight 2025.12 (сверено с 2025.12.5)` in all 21 `content/betaflight/*` modules (with
"лабораторная снята на 4.5.6" where a lab is kept on 4.5), and in the Betaflight part of `link-vtx`,
`link-digital-video`, `f-esc-firmware`, `ctl-allocation`. `related` / `next` untouched. No code fence added or removed;
note lines are prose above the block. Quiz answer indexes and option counts unchanged; task formulas unchanged.

Quiz items whose wording had to change to keep the keyed answer true on 2025.12:

- `quiz/bf-rates-rc.json` "thr_mid = 40, thr_expo = 0": now states `thr_mid = 40`, `thr_hover = 40` (the old stem is
  false on 2025.12 because the curve passes through (`thr_mid`, `thr_hover`)); `rc_smoothing_info` fragment rewritten
  to the 2025.12 four-line format.
- `quiz/bf-led-buzzer.json` "never armed, TX off": now "battery + USB connected" (RX_LOST no longer needs a prior arm,
  it needs USB absent); beacon question says 450 ms.
- `quiz/bf-features-tour.json` dynamic idle fragment uses `motor_idle`.
- `quiz/bf-arming-safety.json`, `tasks/bf-arming-safety.json`: "5 fast beeps" → "series of fast beeps (4 in 2025.12)".

Files outside the list in the brief that carried Betaflight names and got a targeted one- or two-string edit:
`companion/fw-reading.md`, `design/ctl-allocation.md`, `tools/ctl-theory.md`, `tools/data-python.md`,
`foundation/diag-troubleshooting.md`, `foundation/f-safety.md`, `quiz/f-safety.json`.

## 6. Left on 4.5 (labelled), with reason

| Where | What stays on 4.5 | Reason / label |
|---|---|---|
| `bf-setup-scratch` SITL lab (build, MSP bridge, arming/failsafe script and output) | built and run on SITL 4.5.6; flag list ends with `ARMSWITCH`; `min_throttle` 1070 idle | pasted output; note lines above blocks; Phase 2 re-run. Known 2025.12 SITL differences stated (target path, virtual GPS and Blackbox) |
| `bf-arming-safety` lab step 1 output | masks with `ARMSWITCH` at bit 25, "5 fast" | pasted output; 2025.12 masks given in prose |
| `bf-arming-safety` lab step 2 (runaway) | script written against 4.5.6 | logic unchanged in 2025.12.5 (stated); I cap 400 is `iterm_limit` in the script, `iterm_windup × pidsum_limit` in 2025.12 |
| `bf-adjustments` lab | run on 4.5.6 source; D steps start from 40/46 | logic identical except LED_DIMMER (stated); 2025.12 would start from 30/34 |
| `bf-rates-rc` lab step 3 (jitter filter, throttle curve) | 4.5 formulas | both formulas differ in 2025.12; labelled. Steps 1 and 2 are valid for 2025.12 (formulas unchanged) |
| `bf-features-tour` lab step 3 (turtle) and task `crashflip-dshot` | 4.5 algorithm with `crashflip_expo` | algorithm replaced in 2025.12; labelled; task statement says "Betaflight 4.5" |
| `bf-features-tour` lab step 2 (dynamic idle) | 5 % pre-airmode limit | 2025.12 uses `motor_idle` (5.5 %); labelled |
| `bf-led-buzzer` lab | run on 4.5.6 (+2025.12 tree for one comparison line) | RX_LOST timeline (950 ms, armed-before condition) is 4.5; labelled |
| `bf-hd-osd-video` lab | 4.5.6 `serial.h`, numeric port ids in scenarios | logic unchanged; 2025.12 adds the GIMBAL bit and prints names; labelled |
| `bf-servos-pwm` lab | 4.5.6 source and `4.5-config` board file | servo maths unchanged; driver paths moved to `src/platform/STM32/` |
| `bf-gps-setup` auto-configuration walk-through, OSD-element table, PDOP statement, UBX lab | read from `io/gps.c` 4.5.6 | fallback rule 4: `io/gps.c` differs in 1,755 diff lines (mostly reformatting); only named points were re-checked on 2025.12.5 (baud table, VIRTUAL, `pg/gps.c` defaults, `GPS_MIN_SAT_COUNT`, model switch on first fix, CFG-GNSS condition, `gps_auto_baud` only in `status`, `gpsTrust`, distance formula, COG heading threshold). Marked «проверено на 4.5.6» |
| `bf-arming-safety` flag table rows 1–25 "when set" | conditions read on 4.5.6 | names, bits, defaults re-checked on 2025.12.5; per-flag set/clear code not re-read (except BST, CLI, new flags). Stated in the table intro |

## 7. Open questions / not verified

1. **Cloud Build option names.** That OSD type (analog/HD), magnetometer, altitude/position hold are separate
   options in the 2025.12 Flasher follows from `target/common_pre.h` (they are defined only outside `CLOUD_BUILD`) and
   from the community reports in the FAQ study; the exact labels in the App UI and the build-server defaults were not
   read. The course names them generically.
2. **Betaflight App** statements (PWA, version = firmware version, Bluetooth/Wi-Fi paths) come from the release notes
   and the docs repo notes of the earlier audit, not from App source.
3. **"Since which release"**: every 2025.12 row says 2025.12; whether a change landed in 2025.12.0 or in a later patch
   was not determined (only 2025.12.5 was cloned).
4. **`setup-cards.html`, Betaflight card, step 4** still says "Bind ELRS … версии 3.x на TX и RX совпадают". This is an
   ExpressLRS statement (M5 editor); left untouched. It should be reconciled with the SPI-receiver note now in
   `bf-intro` and `bf-ports`.
5. **SITL 2025.12**: the list "what SITL lacks" in `bf-setup-scratch` is 4.5.6. `target.h` of 2025.12.5 shows virtual
   GPS and Blackbox enabled and OSD/serial RX/VTX still undefined; nothing was run.
6. **2026.6 statements** (ELRS 4 for SPI, removed `gps_rescue_*` variables, `trust_mag`, IIM-42652 range) are taken
   from the owner's brief and the FAQ study (release notes); the 2026.6 source was not read. `ELRS_OTA_VERSION_ID 3`
   in 2025.12.5 was confirmed in `rx/expresslrs_common.h`.
7. **Warning-beep preamble**: 2025.12.5 `beeperWarningBeeps()` emits `WARNING_FLASH_COUNT − 1` = 4 fast beeps (4.5
   emits 5). Read from source only; not heard on hardware.
8. **`mag_declination` sign** (west negative) is the usual convention and matches the new signed range; the Configurator
   field was not checked.
9. Diagram assets were not edited (not under `content/`). Confirmed stale: `assets/diagrams/bf-arming-flag-groups.svg`
   is titled "Betaflight 4.5: 26 флагов…" and shows `ARMSWITCH` without the three new flags; the caption in
   `bf-arming-safety` now says 26 / 29. Other Betaflight diagrams (`chart-bf-horizon-strength`, `chart-bf-adj-step-timing`,
   `chart-bf-rc-smoothing-step`, `bf-gps-boot-flow`) were not opened.
10. `bf-cli` reference list still links the archived "Betaflight 4.5 CLI Command Reference" page (kept as the old-side
    reference; the current CLI page is already listed).
