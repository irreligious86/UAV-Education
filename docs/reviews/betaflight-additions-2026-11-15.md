# Betaflight additions — 2026-11-15

Implements `docs/reviews/betaflight-coverage-audit.md` §6.2 (items 1–10) and fixes the autopilot speed-limit advice in
`content/companion/per-tracking.md`. Nothing was committed and `scripts/publish.py` was not run.

Sources:
- Betaflight `4.5-maintenance` at `7dcc851` (`version.h` 4.5.6), local clone; `2025.12-maintenance` at `5b88201` for 2025.12 notes.
- betaflight.com docs repo at `357535a` (`docs/wiki/app/*.md`) for Configurator tab names and the Betaflight App connection options.
- ArduCopter `Copter-4.6.3` (`version.h`: "ArduCopter V4.6.3"), files fetched from `raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.6.3/…`.
- PX4 `main` at `caf75ad3c1` (2026-11-08), local clone. This is not a release tag.

Known audit errors respected:
- The HD port value is 131073 (MSP 1 + VTX_MSP 131072).
- 4.5 has 4 rate profiles.
- `displayport_msp_serial` does not exist in 4.4 or 4.5.
- The `bf-failsafe` "1.5 s in 4.3/4.4" sentence is left unchanged.

Correction to the audit found while implementing: §2 says `diff master` = "everything except the profiles". In 4.5
`printConfig()` (`cli/cli.c` L6188–6380), plain `diff` and `diff master` are the same mask (`DUMP_MASTER`). Both also print
the **current** PID profile and the **current** rate profile (the `else` branch at L6373–6376). Only `diff all` prints all 4 + 4.
The module states the source behaviour.

New reference lessons are linked by id in prose only, with no front-matter changes: bf-adjustments, bf-rates-rc, bf-arming-safety,
bf-hd-osd-video, bf-led-buzzer, bf-servos-pwm, bf-gps-setup and bf-features-tour.

Structure:
- `##` sections are unchanged in every file, and so are the directives.
- One code fence was added, in `bf-cli` (the `feature list` output, 30 → 32 fence lines).
- New `###` subsections were added in `bf-cli` (2), `bf-modes-osd` (1), `bf-ports` (2) and `link-vtx` (1). Everything else is
  paragraphs, bullets or tables inside existing subsections.
- No quiz or task JSON needed a change. They were checked by grep for `diff`, serial masks, `vtx_power`, alarms and
  `WPNAV_*`, and none contradicts the additions.

`python3 scripts/validate_content.py` after the edits reports only "module not in manifest" errors for other authors'
quizzes (comp-jetson-nano, nav-indoor, nav-rtk, nav-terrain, nav-vtrn, per-vision-pipeline, and bf-servos-pwm, which a
parallel author is writing now). None of them is in the files
edited here.

## Changes

| # | §6.2 | File | Before → after (short) | Source (4.5 unless noted) |
|---|---|---|---|---|
| 1 | 1 | `content/betaflight/bf-cli.md` theory, new `### Области diff/dump и флаги` | none → table of `diff`/`diff master`/`profile`/`rates`/`hardware`/`all`, the `defaults` and `bare` flags, the `diff` vs `diff all` trap. `defaults` and `bare` together: only the first word is honoured | `cli/cli.c` `printConfig()` L6188–6213 (masks, `if/else if` for flags), L6221–6376 (sections, `defaults nosave` only for `DUMP_ALL\|DO_DIFF`, profile loops only under `DUMP_ALL`); `target/common_pre.h` L297–298 (`PID_PROFILE_COUNT 4`, `CONTROL_RATE_PROFILE_COUNT 4`) |
| 2 | 1 | `bf-cli.md` theory, new `### Все команды CLI` | none → one-line table of the A/B commands, with links to the new lessons | `cli/cli.c` `cmdTable[]` L6463–6616 (args strings; `bl [flash\|rom]` only with `USE_FLASH_BOOT_LOADER`; `bind_rx` only with `USE_RX_BIND`); `cliMotor()` L4005–4055 (range 1000–2000, index 255 = all, sets `motor_disarmed`); `cliRxBind()` L3434 ("Not supported."); `cliSdInfo()` L2386; `gpsEnablePassthrough()` `io/gps.c` L2484 (endless `serialPassthrough`) |
| 3 | 1 | `bf-cli.md` theory, `feature list` block (new `text` fence) | none → `Available: RX_PPM … ANTI_GRAVITY` (22 names) plus a note that the list comes from the name table, not from the build | `cli/cli.c` `featureNames[]` L233–240, `cliFeature()` L3284–3292 (skips empty slots) |
| 4 | 1 | `bf-cli.md` recipes table | +7 rows: `motor`, `bind_rx`, `gpspassthrough`, `serialpassthrough` (ELRS RX flashing; id as in `serial`), `flash_erase`/`sd_info`, `rc_smoothing_info` | `cli/cli.c` `cliSerialPassthrough()` L1409–1466 (`ports[0].id = atoi(tok)`), `cliFlashErase()` L2488, `cliRcSmoothing()` L4946 |
| 5 | 2 | `content/betaflight/bf-intro.md` "Карта настройки" | row "Приёмник, каналы, рейты \| Receiver" → split into Receiver (`map`, `serialrx_provider`, `rxrange`, `rc_smoothing_*`) and "PID Tuning → Rateprofile Settings" (rates). New rows: Adjustments, Video Transmitter, LED Strip, Presets | docs repo `wiki/app/pid-tuning-tab.mdx` ("Rateprofile Settings"), `receiver-tab.md` ("RC Smoothing", "Channel Map"), `presets-tab.md` ("short snippets of CLI commands"). The three §6.3 bf-intro errors were already fixed on 2026-11-15 (fixes log #11–15) |
| 6 | 3 | `content/betaflight/bf-pid-reg-in-bf.md` practice | none → "Значения по умолчанию 4.5" table (P/I/D, `d_min_*`, `d_min_gain` 37, `d_min_advance` 20, `f_*` 120/125/120) | `flight/pid.h` L62–65 (`PID_*_DEFAULT`, `D_MIN_DEFAULT`); `flight/pid.c` L187–189 |
| 7 | 3 | `bf-pid-reg-in-bf.md` practice | none → `pidsum_limit` 500 / `_yaw` 400 (100–1000, clamp in the mixer, /1000) | `flight/pid.h` L34–37; `flight/mixer.c` L623–637 |
| 8 | 3 | `bf-pid-reg-in-bf.md` practice | none → TPA defaults and 4.5 low-throttle TPA: `tpa_low_rate` 20, `tpa_low_breakpoint` 1050, `tpa_low_always` OFF. Factor 0.8 at zero throttle; with OFF it stops after the first pass above the breakpoint until reboot | `flight/pid.c` L221–229, `pidUpdateTpaFactor()` L280–295 (static `isTpaLowFaded` latch); `flight/pid_init.c` L430–434 |
| 9 | 3 | `bf-pid-reg-in-bf.md` practice | none → dynamic idle: `dyn_idle_min_rpm` 0 (×100 rpm), gains 50/50/50, `max_increase` 150 (15 %), `start_increase` 50 (5 % before air mode). Needs DShot telemetry. When active, the output floor goes to `DSHOT_MIN_THROTTLE`, so `dshot_idle_value` is no longer the floor | `flight/pid.c` L194–199; `flight/mixer_init.c` L329–344; `flight/mixer.c` L222–240; `build/debug.c` L87 (`DYN_IDLE`) |
| 10 | 4 | `content/betaflight/bf-modes-osd.md` theory, `aux` paragraph | 5 example ids → full table of 4.5 `permanentId` (0…54, removed ids listed) and links to bf-adjustments / bf-features-tour / bf-arming-safety | `msp/msp_box.c` `boxes[]` L50–104 |
| 11 | 4 | `bf-modes-osd.md` theory, new `### Стик-команды (на дизарме)` | none → table: save, gyro cal (+GPS home reset, baro zero), PID profiles 1–3, acc cal, mag cal, rate profiles 1–4 (ACRO), acc trims (ANGLE/HORIZON), VTX band/channel, CMS menu. Notes on when they are blocked, beeps, no auto-save of profile changes, and the "pitch 1060 turns save into profile 3" trap | `fc/rc_controls.c` `processRcStickPositions()` L230–390 (all `rcSticks ==` cases, `STICK_DELAY_MS` 50, RUNAWAY/CRASH guard, `BOXSTICKCOMMANDDISABLE`); `cms/cms.c` L1498 (`IS_MID(THROTTLE) && IS_LO(YAW) && IS_HI(PITCH)`, roll not checked); `config/config.c` L833 (save: 1 beep), L885 (profile: N+1 beeps); `fc/controlrate_profile.c` L82 (no save) |
| 12 | 4 | `bf-modes-osd.md` theory, OSD bullet "Предупреждения" | thresholds named → 4.5 defaults (`osd_rssi_alarm` 20, `osd_link_quality_alarm` 80, `osd_cap_alarm` 2200, `osd_alt_alarm` 100, `osd_rssi_dbm_alarm` −60, `osd_rsnr_alarm` 4, `osd_core_temp_alarm` 70; ESC/distance alarms off). The RSSI, LQ, RSSI_DBM, RSNR and OVER_CAP **warnings are off by default** | `osd/osd.c` `pgResetFn_osdConfig()` L337–397 (`osdWarnSetState(..., false)` L353–359) |
| 13 | 4 | `bf-modes-osd.md` theory, new OSD bullet "Статистика после полёта" | none → `osd_stat_bitmask` and its default set, `stats_total_*`, `stats_min_armed_time_s` = −1 (off), save 0.5 s after disarm, skipped if config is dirty | `osd/osd.c` L337–364; `cli/settings.c` L1505, L1751–1758; `pg/stats.c` L33; `fc/stats.c` L40, L58–72 (`if (!isConfigDirty())`), L88–108 |
| 14 | 5 | `content/betaflight/bf-setup-scratch.md` SITL output notes | `ANGLE` = "горизонт не оценён" → plus: on hardware the tilt sets it, `isUpright()` = attitude established **and** tilt < `small_angle` (25°, 0–180), and it is not set while FLIP OVER AFTER CRASH is active | `flight/imu.c` L118–122, L183, L856–863; `fc/core.c` L320–324; `cli/settings.c` L1008 |
| 15 | 5 | `bf-setup-scratch.md` hardware item 8 (step 10) | none → cell-count rule `V / vbat_max_cell_voltage + 1` (max 8) with the HV-LiPo / flat-6S failures; `force_battery_cell_count`; `vbat_detect_cell_voltage` 300; `vbat_full_cell_voltage` 410 (OSD `BATT < FULL`); `use_cbat_alerts`/`cbat_alert_percent` 10; `vbat_cutoff_percent` 100 (10 s ramp of throttle) | `sensors/battery.c` L108–130, L200–222, L294–326 (`LVC_AFFECT_TIME` L70); `sensors/battery.h` L35–38; `fc/rc.c` L721–722; `osd/osd_warnings.c` L414–415; `cli/settings.c` L898–909 |
| 16 | 5 | `bf-setup-scratch.md` hardware item 12 (step 14, GPS) | none → `gps_auto_config` ON, `gps_update_rate_hz` 10, `gps_ublox_flight_model` AIRBORNE_4G, `gps_ublox_use_galileo` OFF, `gps_sbas_mode` NONE (AUTO/EGNOS/WAAS/MSAS/GAGAN/NONE), `gps_set_home_point_once` OFF; Galileo ON and SBAS AUTO/regional advised; link to bf-gps-setup | `pg/gps.c` L34–48; `cli/settings.c` L205–207, L1020–1032; `io/gps.c` L1105 (autoConfig OFF skips config), L1249, L2295–2315 (SBAS/Galileo blocks) |
| 17 | 6 | `content/betaflight/bf-failsafe.md` theory, Stage 2 | none → `vtx_low_power_disarm` does not lower power while failsafe is active, so after DROP the VTX keeps flight power until the link returns (link-vtx) | `io/vtx.c` L131–135 (`!failsafeIsActive()`); `flight/failsafe.c` L387–415 (`active` cleared only in `RX_LOSS_RECOVERED`) |
| 18 | 6 | `bf-failsafe.md` theory, Stage 2 | none → 2025.12: `failsafe_landing_time` 60 s; AUTO-LAND via ALT_HOLD when an altitude source exists; `landing_disarm_threshold` (0–250, default 0, ×10 vs acc jerk, also active in ALT_HOLD); disarm otherwise at `failsafe_landing_time` or crash recovery | 2025.12 `flight/failsafe.c` L76, L349–366; `fc/core.c` L1043–1061; `flight/alt_hold_multirotor.c` L115–123; `flight/pid.c` L243, L946–970, L1206; `flight/pid_init.c` L581–582; `cli/settings.c` L1422 |
| 19 | 6 | `bf-failsafe.md` "дефолт 1.5 с (так же в 4.3–4.4…)" | **unchanged** (correct, see fixes log) | — |
| 20 | 7 | `content/betaflight/bf-ports.md` theory, after "Команда `serial`" | "точные значения — `serialPortFunction_e`" → full bit table (1…131072, 256 unused), examples incl. `serial 0 131073 …` for HD (MSP + VTX_MSP), CRSF telemetry has no own bit | `io/serial.h` L36–53 |
| 21 | 7 | `bf-ports.md` new `### Параметры приёмника, которые лежат не на вкладке Ports` | none → `serialrx_inverted` (relative to protocol default: SBUS ON = non-inverted; CRSF/FPort ON = inverted; F7/H7/G4 UART inverts, F4 needs `INVERTER` resource), `serialrx_halfduplex` (build-dependent default), `crsf_use_negotiated_baud` (420000 default, cached baud from the persistent object) | `rx/sbus.c` L199, `rx/fport.c` L410, `rx/crsf.c` L643–652; `drivers/stm32/serial_uart_hal.c` L59–60 (RXINV, built for F7/G4/H7 per `mk/mcu/*.mk`); `drivers/inverter.c`; `pg/rx.c` L70–76, L83–85, L116; `rx/crsf_protocol.h` L30; `telemetry/crsf.c` L121–131 |
| 22 | 7 | `bf-ports.md` new `### Настройка с телефона` | none → FC side = MSP on a UART (115200, ≤ 3 MSP ports); App side: web app Bluetooth (boards supported by SpeedyBee app and others), native Android app via USB and ELRS Wi-Fi TCP (2025.12.1+); DIY HC-05/ESP32 bridge only with an app that supports it | docs repo `wiki/app/index.mdx` L18, L34, L59–61, L91–103, L142 |
| 23 | 8 | `content/betaflight/bf-filters.md` practice Шаг 0 | none → F4/G4 bidir rewrite (DSHOT600 → 300, `pid_process_denom ≥ 2` if gyro > 4 kHz; F405 exempt at `cpu_overclock` ≥ 216 MHz). Consequence for logs: 1/4 → 1 kHz, Nyquist 500 Hz, use `1/2`. `LOAD` flag = > 10 ‰ late task starts per second; CPU % itself is not an arming limit | `config/config.c` `validateAndFixGyroConfig()` L642, L673–690; `target/STM32F405/target.h` L86–87, `STM32F411/target.h` L85, `STM32G47X/target.h` L82; `cli/settings.c` L360–363 (overclock table), L233–234 (sample rates); `fc/core.c` L326–331; `pg/scheduler.h` L35; `scheduler/scheduler.c` L574, L753–759 |
| 24 | 8 | `bf-filters.md` | the audit's "CPU load < 75 % (Oscar Liang)" was **not added**: the page could not be read here, and no firmware source has that number | — |
| 25 | 9 | `content/betaflight/bf-blackbox.md` theory "Параметры записи" | "`blackbox_disable_*` (acc, rc, gyrounfilt, rpm, gps…)" → table of all **14** `blackbox_disable_*` in 4.5 (audit said 13) with fields, value counts and conditions | `cli/settings.c` L817–839; `blackbox/blackbox.c` L98 (`fields_disabled_mask = 0`), `blackboxMainFields[]` (field counts), `testBlackboxConditionUncached()` L447–535 |
| 26 | 9 | `bf-blackbox.md` | none → `flash_info`, `flash_erase`, BLACKBOX ERASE mode (31), `sd_info` messages, `msc` (flash via emfat and SD; failure message) | `cli/cli.c` L2386–2420, L2488–2518, L6405–6427; `blackbox/blackbox.c` L1854; `msc/emfat*.c` |
| 27 | 9 | `bf-blackbox.md` | none → `INFLIGHT_ADJUSTMENT` events (step/absolute: all functions; select: rate profile and HORIZON_STRENGTH only) | `blackbox/blackbox.h` L54, `blackbox.c` L1702; `fc/rc_adjustments.c` L102 and the calls in `applyStep/Absolute/SelectAdjustment` |
| 28 | 10 | `content/link/link-vtx.md` theory, new `### Мощность, pit mode и VTX на тумблере в Betaflight 4.5` | none → `vtx_power` = 1-based table index (0 = unset, CLI 0–7), `vtx_low_power_disarm` OFF/ON/UNTIL_FIRST_ARM (not in failsafe), VTX PIT MODE handled only disarmed, `vtx_pit_mode_freq`, band/channel sent only disarmed, `vtx` slots and stick band/channel locked after first arm, VTX CONTROL DISABLE (SmartAudio/Tramp), `vtx` syntax and link to bf-adjustments, stick commands | `cli/settings.c` L419–421, L1547–1560; `drivers/vtx_table.h` L32, L52; `drivers/vtx_common.c` L95–100, L222–230; `io/vtx.c` L55–66, L115–150, L174–220; `io/vtx_control.c` L58–130; `io/vtx_smartaudio.c` L256, L499; `io/vtx_tramp.c` L180; `fc/rc_controls.c` VTX stick cases |
| 29 | 10 | `link-vtx.md` practice "Смена через CLI" (existing fence) | `set vtx_band/channel` → plus `set vtx_power = 1`, `set vtx_low_power_disarm = ON` | as #28 |

## per-tracking fix

| # | File | Before → after (short) | Source |
|---|---|---|---|
| 30 | `content/companion/per-tracking.md` theory "Интерфейсы" | "Ограничения автопилота: `WP_SPD` (до 4.7 — `WPNAV_SPEED`), `PSC_*`, `GUID_OPTIONS`" → ArduCopter does **not** limit speed for velocity targets. `WPNAV_SPEED` (4.7 `WP_SPD`) does not apply, and neither do `WPNAV_SPEED_UP/DN`. The author's SITL result (300 cm/s set, 6 m/s command → 6.1–6.2 m/s) is quoted. What does apply: `WPNAV_ACCEL` 250 cm/s², `WPNAV_ACCEL_Z` 100 cm/s², `PSC_JERK_XY` 5 m/s³, lean `PSC_ANGLE_MAX`/`ANGLE_MAX` 30° (an accel limit), `GUID_TIMEOUT`. `GUID_OPTIONS` has no speed limit. The fence (`FENCE_ENABLE` + `AVOID_ENABLE` bit 0, default 3) stops the vehicle `FENCE_MARGIN` (2 m) before circle/polygon/alt-max with ≤ 1 m/s² deceleration. `AVOID_BEHAVE` 0 slide / 1 stop. After a breach avoidance is skipped for that fence and `FENCE_ACTION` (default 1 RTL or Land) runs. Rule: the companion clamps v and a | see source lines below |
| 31 | same, PX4 Offboard | none → `MPC_XY_VEL_MAX` (12 m/s) and `MPC_Z_VEL_MAX_UP/DN` (3/1.5 m/s) do clamp, tilt `MPC_TILTMAX_AIR` 45°. Offboard velocity steps are not smoothed (no flight task). The geofence checks the current position and runs `GF_ACTION` (default 2 Hold), with no braking ahead of the fence | see below |
| 32 | same, "Защиты" item 1 | "Лимиты: v_max, a_max, высота, геозона включена" → limits are enforced **in the companion** (vector norm, Δv ≤ a_max·dt); autopilot second line: fence on, PX4 `MPC_XY_VEL_MAX` | as #30–31 |
| 33 | same, practice Шаг 4 | none → SITL checks: `WPNAV_SPEED = 300` with an unclamped 6 m/s command (≈ 6 m/s flown), clamped (≤ v_max), and a fence test (`FENCE_RADIUS` 30 m, stop at about `FENCE_MARGIN`, companion must detect "command but no motion") | as #30 |
| 34 | same, diagnostics | +2 symptoms: "faster than `WPNAV_SPEED` in GUIDED" and "stopped at the field edge with non-zero command" | as #30 |
| 35 | same, references | +ArduCopter 4.6.3 `mode_guided.cpp` (raw.githubusercontent, 200), + ArduPilot "Cylindrical Fence" page (read with WebFetch: "attempt to stop … only if Object Avoidance is set up") | — |

Source lines relied on (ArduCopter Copter-4.6.3):
- `ArduCopter/GCS_Mavlink.cpp` L1334–1341 and L1374–1375: the velocity-only `SET_POSITION_TARGET_LOCAL_NED` is checked by `sane_vel_or_acc_vector()`, which only rejects NaN or values above 1000 (L1168–1176). It then goes to `mode_guided.set_velaccel()`. `SET_POSITION_TARGET_GLOBAL_INT` takes the same path (L1477).
- `ArduCopter/mode_guided.cpp` L218–230, `pva_control_start()`: `pos_control->set_max_speed_accel_xy(wp_nav->get_default_speed_xy(), wp_nav->get_wp_acceleration())`. This is where WPNAV_SPEED is stored into `_vel_max_xy_cms`.
- `mode_guided.cpp` L795–847, `velaccel_control_run()`:
  - L809–815: the timeout `get_timeout_ms()` = `GUID_TIMEOUT` (L1163–1165, `Parameters.cpp` L1028, default 3.0).
  - L819–821: `copter.avoid.adjust_velocity(guided_vel_target_cms, …, pos_control->get_max_accel_xy_cmss(), …)`.
  - L830: `pos_control->input_vel_accel_xy(guided_vel_target_cms.xy(), …, false)`.
  - L838: `input_vel_accel_z(...)`.
  - The older `vel_control_run()` path (L770–771) is the same.
- `libraries/AC_AttitudeControl/AC_PosControl.cpp`:
  - L565–573, `input_vel_accel_xy()`, calls `shape_vel_accel_xy(vel, accel, _vel_desired.xy(), _accel_desired.xy(), _accel_max_xy_cmss, _jerk_max_xy_cmsss, _dt, limit_output)`. There is **no `_vel_max_xy_cms` argument**. Compare `input_pos_vel_accel_xy()` L580–588, which passes `_vel_max_xy_cms`.
  - L877–893, `input_vel_accel_z()`: only accel/jerk limits.
  - L644–730, `update_xy_controller()`: there is no velocity clamp, and acceleration is limited by lean angle (L706–710).
  - L1075–1085, `get_lean_angle_max_cd()`: `PSC_ANGLE_MAX` 0 → `ANGLE_MAX`, which defaults to 3000 cdeg (`config.h` L449–450).
  - L308–315 and `.h` L21: `PSC_JERK_XY` 5.
- `libraries/AC_WPNav/AC_WPNav.cpp` L7–13 and L25–70, `AC_WPNav.h` L16 and L88: the defaults SPEED 1000, ACCEL 250 and ACCEL_Z 100.
- `libraries/AC_Avoidance/AC_Avoid.cpp`:
  - L43–48 and `AC_Avoid.h` L16–19: `AVOID_ENABLE` default `STOP_AT_FENCE | USE_PROXIMITY_SENSOR` = 3.
  - L73: `AVOID_MARGIN` 2. L32–34 and L80: `AVOID_BEHAVE` default Slide for Copter.
  - L199–228: `adjust_velocity()` → `adjust_velocity_fence()`.
  - L137–167: needs bit `AC_AVOID_STOP_AT_FENCE` and limits accel to `AC_AVOID_ACCEL_CMSS_MAX` = 100 (`.h` L12).
  - L740–781: the circle fence needs it enabled and not breached, and uses `FENCE_MARGIN`.
  - L386–484: the alt-max fence in z.
  - L552–561 and L726–733: limits the velocity component toward the fence to `sqrt_controller(distance)`.
- `libraries/AC_Fence/AC_Fence.cpp`:
  - L54: `FENCE_ENABLE` default 0. L21–25 and L62: `FENCE_TYPE` default alt-max + circle + polygon.
  - L64–72: `FENCE_ACTION` default `RTL_AND_LAND`.
  - L31, L34, L89, L97: radius 300 m, margin 2 m.
  - The guided position destinations outside the fence are rejected in `mode_guided.cpp` L333–340 and L589–595.
- Version naming: `WP_SPD` exists on ArduPilot `master` (`AC_WPNav.cpp` `AP_GROUPINFO("SPD", 14, …, WP_SPD_DEFAULT)`). The course's "4.7" label for it follows `content/tools/ctl-guidance.md` and was not re-checked against a 4.7 tag.

PX4 (`main` caf75ad3c1):
- `src/modules/mc_pos_control/MulticopterPositionControl.cpp` L544–547 and L577: `max_speed_xy = MPC_XY_VEL_MAX` (min with EKF `vxy_max`) → `setVelocityLimits()`.
- `PositionControl/PositionControl.cpp` L127–141: `_positionControl()` constrains `_vel_sp.xy()` to `_lim_vel_horizontal` and z to up/down limits, also when the position setpoint is NaN.
- `multicopter_position_control_limits_params.yaml` L5–17 (`MPC_XY_VEL_MAX` default 12, "Absolute maximum for all velocity controlled modes"), and `MPC_Z_VEL_MAX_UP` 3, `_DN` 1.5, `MPC_TILTMAX_AIR` 45.
- `src/modules/flight_mode_manager/tasks/` has no Offboard task, so Offboard setpoints are not smoothed.
- `src/modules/navigator/geofence_params.yaml` L5–19: `GF_ACTION` default 2 = Hold. `navigator_main.cpp` `geofence_breach_check()` L1221 and following checks the current position.

## Left unverified

- The CPU-load "< 75 %" guideline (audit §5 #27, Oscar Liang) was not added (see #24).
- "3 power cycles" to enter ELRS bind mode and the ELRS Configurator flashing "через Betaflight passthrough" (`bf-cli` recipes) are ELRS-side behaviour. They were not checked in ELRS source here.
- Board-side BLE details (which boards the Betaflight web app reaches over Bluetooth) are as stated by the docs repo only.
- PX4 values are from `main`, not from a PX4 release. Parameter defaults may differ in a stable 1.15/1.16 tag.
- ArduPilot behaviour for the 4.6.3 SITL run (6.1–6.2 m/s) is the author's observation. The source reading above explains it, but SITL was not rerun here.
