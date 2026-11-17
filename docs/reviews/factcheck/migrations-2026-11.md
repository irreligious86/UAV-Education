# Fact-check: firmware migrations (commit b227dff), 2026-11

STATUS: COMPLETE.

Independent, read-only check of the four migration tables and of statements swept by commit b227dff, against the
source trees on disk. Nothing was built or run. Nothing under `content/`, `data/`, `assets/`, `i18n/` was edited.
Line numbers refer to the committed state (`git show b227dff:<path>`); `content/link/link-elrs.md` and several INAV
files have later uncommitted edits by another editor and were read from the commit.

Sources:

- ArduPilot: `/tmp/ardupilot-audit/copter472` (tag Copter-4.7.2 / Plane-4.7.2), `/tmp/ardupilot` (Copter-4.6.3),
  `/tmp/ardupilot-audit/plane463`, `copter-4.6.3.pdef.json`, `copter-4.7.2.pdef.json`, `plane-4.6.3.pdef.json`,
  `plane-4.7.2.pdef.json`, `copter-sitl-defaults.csv` (4.6.3), `copter-4.7.2-sitl-defaults.csv`.
- Betaflight: `/tmp/bf-migrate/bf453` (4.5.3), `bf455` (4.5.5), `bf2025` (2025.12.5).
- PX4: `/tmp/px4-audit` (v1.15.4), `/tmp/px4-audit-v1.16.2`, `/tmp/px4-audit-v1.17.0`.
- ExpressLRS: `/tmp/elrs-migrate/elrs41` (4.1.0), `elrs36` (3.6.4), `docs` (docs repository, 2026-11-09).

## 1. Findings

Severity: **error** (statement contradicts source), **imprecise** (true in the main case, wrong or incomplete at the
edge), **ok-but-unverifiable** (nothing on disk contradicts it, nothing on disk proves it).

| # | File | Line | Statement | What source says | Severity |
|---|---|---|---|---|---|
| 1 | `assets/widgets/elrs-calc.js` | 23 | D250 has `kind: T("DVDA (пакет ×2)")` | `elrs41/src/src/common.cpp:85` — `RATE_FLRC_2G4_250HZ_DVDA`, interval 1000 µs, `numOfSends` = 4. D500 (`common.cpp:84`) = 2, so line 24 is right. 900 MHz D50 (`common.cpp:15`) = 4 | error |
| 2 | `content/px4/px4-architecture.md` | 61 | «`listener vehicle_angular_velocity` — частота ~400 Гц?» | `px4-audit-v1.17.0/ROMFS/px4fmu_common/init.d/rc.mc_defaults:13-16`: `if param compare IMU_GYRO_RATEMAX 400` → `param set-default IMU_GYRO_RATEMAX 800`. Parameter default 400 (`imu_gyro_parameters.c:150`) applies only to non-multicopter airframes. Line 28 of the same module already says 800 Hz | error (internal inconsistency) |
| 3 | `content/betaflight/bf-intro.md` | 159 | «`tpa_mode` PD / D → PD / D / PDS — добавлено PDS; в сборке WING ещё `tpa_curve_*`…» | `bf2025/src/main/cli/settings.c`, `lookupTableTpaMode[]`: `"PD", "D", #ifdef USE_WING "PDS", #endif`. On a multirotor build `set tpa_mode = PDS` is rejected; PDS exists only in WING builds, together with `tpa_curve_*` | error |
| 4 | `content/link/link-elrs.md` | 164 | «…3 с для 250 и 200 Гц, 3.5 с для 150 и 100 Гц…» (`DisconnectTimeoutMs`) | `elrs41/src/src/common.cpp:55-56` (LR1121): 900 MHz 250Hz and 200Hz Full have 3500 ms. 3000 ms holds for 2.4 GHz 250Hz (`:68`, `:100`) and 900 MHz 200Hz (`:18`, `:57`) | imprecise |
| 5 | `content/ardupilot/ap-intro.md` | 70 | «`SR0_*` … `SR6_*` → `MAV1_*` … `MAV7_*`» | Mapping SRn → MAV(n+1) is right (`ArduCopter/Parameters.h:210-229`, `k_param_gcs0_unused…gcs6_unused`). 4.7.2 defines `MAV1_*…MAV32_*` (`libraries/GCS_MAVLink/GCS.cpp:77-232`, pdef groups MAV1…MAV32); how many are visible depends on the board's channel count | imprecise |
| 6 | `content/ardupilot/ap-intro.md` | 30 | «Что не переносится: … `AVOID_ANGLE_MAX` — уклонение наклоном убрано из стандартных сборок» | Feature gating is right: `AC_Avoidance_config.h:30-31` `AP_AVOIDANCE_ALTHOLD_ENABLED 0`, and `AVOID_ANG_MAX` is absent from the 4.7.2 SITL dump. But on a custom build with the option the value **is** converted: `AC_Avoid.cpp:142-153`, ×0.01 | imprecise |
| 7 | `content/px4/px4-intro.md` | 76 | «…хранятся только значения, которые ты менял. Всё, что стояло на умолчании, после прошивки молча получает умолчание 1.17» | Confirmed in substance: `src/lib/parameters/parameters.cpp:103-105` (layers `firmware_defaults` → `runtime_defaults` → `user_config`), `param_export_internal()` `:1061-1105` skips every value equal to the current default. Edge: a value the user set **explicitly equal** to the old default is not stored either and also moves to the new default; a value changed by calibration or autotune is stored although the user did not type it | imprecise |
| 8 | `content/betaflight/bf-intro.md` | 182 | «`save noreboot`, `exit noreboot` — с 4.5.4» | Absent in 4.5.3 `cli/cli.c`, present in 4.5.5 `cli/cli.c:3588, 4248, 6514`. No 4.5.4 tree on disk, so "4.5.4" vs "4.5.5" cannot be decided | ok-but-unverifiable |
| 9 | `content/link/link-elrs.md` | 223 | «В Betaflight 2026.6 (сверено с 2026.6.2) появился вариант сборки `USE_ELRSV4` (опция `ELRSV4`) с `ELRS_OTA_VERSION_ID 4`» | No 2026.6 Betaflight tree on disk. The 2025.12.5 half is confirmed: `bf2025/src/main/rx/expresslrs_common.h:36` `#define ELRS_OTA_VERSION_ID 3`, used in the CRC initialiser (`rx/expresslrs.c:631, 939`) | ok-but-unverifiable |
| 10 | `content/betaflight/bf-intro.md` | 193 (paragraph after the table), 146 (checklist item 8), 169 | 2026.6 statements: `gps_rescue_velocity_*` removed, IIM-42652 range fix, ELRS 4 for SPI receivers | Same: no 2026.6 source | ok-but-unverifiable |
| 11 | `content/link/link-elrs.md` | 214, 217 | «Полоса телеметрии около +30 %…»; Dynamic Power «среднее + 0.5 σ вместо + 1.5 σ» | 4.1 side confirmed: `elrs41/src/src/dynpower.cpp:217` `snr_stat_mean + snr_stat_stdev / 2`. No 4.0.0 tree on disk for the «+1.5 σ» side; +30 % is from release notes only | ok-but-unverifiable |
| 12 | `content/ardupilot/ap-intro.md` | 28 | LittleFS logs erased by the upgrade | Not in source; 4.7.2 release notes contain only the opposite fix (`ArduCopter/ReleaseNotes.txt:533`). Text already labels it as a developer report | ok-but-unverifiable |

### Proposed replacement text (Russian) for each error

**#1** `assets/widgets/elrs-calc.js:23` — replace the D250 label only:

```
{ name: "D250", rate: 250, sens: -104, kind: T("DVDA (пакет ×4)") },
```

(line 24, D500 «DVDA (пакет ×2)», stays.)

**#2** `content/px4/px4-architecture.md:61` — replace the line with:

```
1. `listener vehicle_angular_velocity` — частота около `IMU_GYRO_RATEMAX` (у мультиротора 800 Гц, умолчание параметра для остальных — 400)? если заметно ниже — перегрузка (`top`).
```

**#3** `content/betaflight/bf-intro.md:159` — replace the row with:

```
| `tpa_mode` PD / D | PD / D; в сборке WING — ещё PDS | на коптере набор значений не менялся; PDS, `tpa_curve_*`, `tpa_speed_*` и отрицательные значения `tpa_low_rate` есть только в сборке WING (на коптере `tpa_low_rate` по-прежнему 0–100, умолчание 20) | 2025.12 |
```

Optional wording for the imprecise items:

- **#4** `link-elrs.md:164`: «…3 с для 250 Гц на 2.4 ГГц и 200 Гц на 900 МГц, 3.5 с для 150 и 100 Гц и для режимов 900 МГц 250Hz и 200Hz Full на LR1121…».
- **#5** `ap-intro.md:70`, second cell: «`MAV1_*` … `MAV7_*` (с единицы: `SR0` → `MAV1`, `SR1` → `MAV2`; всего групп `MAVn_*` столько, сколько MAVLink-каналов у платы)».
- **#6** `ap-intro.md:30`: «…`AVOID_ANGLE_MAX` — уклонение наклоном убрано из стандартных сборок (в сборке с этой опцией значение переносится в `AVOID_ANG_MAX`)».
- **#7** `px4-intro.md:76`: «…но хранятся только значения, которые отличаются от умолчания. Всё, что совпадало с умолчанием — в том числе выставленное тобой вручную в то же число, — после прошивки молча получает умолчание 1.17…».

## 2. Priority 3 — claims the editors flagged as unverified or inferred

| Claim | Verdict | Source |
|---|---|---|
| ArduPilot `SRn_*` → `MAVn_*` has no value conversion | confirmed | `copter472/ArduCopter/Parameters.h:210-229` (`k_param_gcsN_unused // unused in ArduPilot-4.7`); no reference to these keys anywhere else in the tree; the GCS conversion block `ArduCopter/Parameters.cpp:1292-1302` converts only `MAV_SYSID`, `MAV_GCS_SYSID`, `MAV_OPTIONS`, `MAV_TELEM_DELAY` |
| `PSC_D_ACC_P/I/D` = old × 0.1 | confirmed | `libraries/AC_AttitudeControl/AC_PosControl.cpp:1885-1891` `convert_old_parameters_scaled(conversion_info_01, …, 0.1, 0)` |
| `PSC_*_VEL_IMAX` × 0.01, `PSC_D_ACC_IMAX` × 0.001 | confirmed | `AC_PosControl.cpp:1903-1917` |
| `PSC_D_ACC_P` default 0.05, `PSC_D_ACC_I` 0.1 vs 4.6 `PSC_ACCZ_P` 0.5, `PSC_ACCZ_I` 1.0 | confirmed | `AC_PosControl.cpp:58, 75` (Copter), 4.6.3 SITL dump 0.5 / 1; 4.7.2 SITL dump 0.05 / 0.1 |
| Rule `PSC_D_ACC_P = 0.1 × MOT_THST_HOVER`, `PSC_D_ACC_I = 0.2 × MOT_THST_HOVER` | consistent with source; wording in `ap-setup-scratch.md:232` and `ap-tuning.md:29` is accurate | The rule is not stated anywhere in the 4.7.2 tree, but it equals the 4.6 rule times the conversion factor, the defaults scale the same way (0.35 hover → 0.05 / 0.1 is the old 0.5 / 1.0 × 0.1), and the shipped frame files follow it (`Tools/Frame_params/Holybro-X500v2-bdshot.param:37-38` 0.03 / 0.06, `Holybro-QAV250.param:51-52` 0.0084 / 0.0168, `Hexsoon-td860.param:34-35` 0.0185 / 0.037 — I = 2 × P everywhere). Not checked against the 4.7 online tuning page |
| Betaflight `osd_warn_bitmask` shift | confirmed | `osd/osd.h` enums: 4.5.3 bit 8 `RC_SMOOTHING`, bits 9–18 `FAIL_SAFE…LOAD`; 2025.12.5 bits 8–17 `FAIL_SAFE…LOAD`, bit 18 `POSHOLD_FAILED` |
| 4 vs 5 arming warning beeps | confirmed | 4.5.3 `io/beeper.c:327` loops `count < WARNING_FLASH_COUNT` (5, `drivers/system.h:49`); 2025.12.5 `io/beeper.c:332` `beep_multiBeepsAdd(i, WARNING_FLASH_COUNT - 1, …)` = 4 |
| RX_LOST beeper condition | confirmed | 4.5.3 `flight/failsafe.c:251` `!receivingRxData && (armed \|\| ARMING_FLAG(WAS_EVER_ARMED))`; 2025.12.5 `flight/failsafe.c:252` `!receivingRxData && !usbCableIsInserted()` |
| Throttle curve through (`thr_mid`, `thr_hover`) | confirmed | `bf2025/src/main/fc/rc.c:824-862`: two quadratic Bézier segments (0,0)→(thrMid,thrHover)→(1,1); with expo 0 the control points lie on the chords (straight lines). Default `thrHover8 = 50` (`fc/controlrate_profile.c:65`) |
| PX4 `RC_CRSF_PRT_CFG` on fmu-v6x default build | confirmed | `px4-audit-v1.17.0/boards/px4/fmu-v6x/default.px4board:44` `CONFIG_COMMON_RC=y`, no `CONFIG_DRIVERS_RC_INPUT`; `src/drivers/rc/Kconfig:2-8` selects `crsf_rc`, `dsm_rc`, `ghst_rc`, `sbus_rc`; `src/drivers/rc/crsf_rc/module.yaml:5`. 1.15.4 and 1.16.2 boards have `CONFIG_DRIVERS_RC_INPUT=y` (line 43). Same for fmu-v5x and fmu-v6xrt; fmu-v5 has both; fmu-v6u still `rc_input` |
| `BAT1_V_LOAD_DROP` removed (1.16) | confirmed | present `px4-audit/src/lib/battery/module.yaml:42`, used `battery.cpp:233`; absent from 1.16.2 and 1.17.0 `module.yaml`; 1.17 compensates only when `current_a > FLT_EPSILON` (`battery.cpp:223-231`) |
| `COM_POSCTL_NAVL` removed (1.17) | confirmed | `commander_params.c:510` (1.15.4), `:465` (1.16.2), absent in 1.17.0; fallback PosCtl → AltCtl → Stabilized in `failsafe/failsafe.cpp:683-695` |
| `EKF2_EV_CTRL` 15 → 0, `EKF2_OF_CTRL` 0 → 1, `EKF2_AGP_CTRL` 1 → 0 (all 1.16) | confirmed | 1.15.4 `ekf2/module.yaml:518, 692, 1312`; 1.16.2 and 1.17.0 `params_external_vision.yaml:5`, `params_optical_flow.yaml:5`, `params_aux_global_position.yaml:5`; `EKF2_AGP_MODE` only in 1.17 (`:17`) |
| SITL `COM_LOW_BAT_ACT` 2 → 3 (1.16) | confirmed | `ROMFS/px4fmu_common/init.d-posix/rcS:183` (1.15.4) = 2; `:191` (1.16.2) and `:190` (1.17.0) = 3; firmware default 0 in all three |
| Firmware update keeps stored parameters, untouched ones take new defaults | confirmed, with the nuance in finding #7 | `src/lib/parameters/parameters.cpp:103-105, 1061-1105` |
| «~400 Гц» vs 800 Hz in `px4-architecture.md` | error, finding #2 | — |
| Widget label «DVDA (пакет ×2)» for D250/D500 | D500 right (×2), D250 wrong (×4), finding #1 | `elrs41/src/src/common.cpp:84-85`; LR1121 DK500 / DK250 likewise 2 / 4 (`:42-43`) |
| ELRS 3.x ↔ 4.x incompatible by any binding method | confirmed | `elrs41/src/include/targets.h:8` `OTA_VERSION_ID 4`, `elrs36/src/include/common.h:20` = 3; mixed into the CRC initialiser (`lib/OTA/OTA.cpp:38`), into the FHSS seed (`OTA.cpp:44`, `UID[5]^OTA_VERSION_ID`) and used as the bind-mode CRC initialiser (`src/tx_main.cpp:1018`, `src/rx_main.cpp:1672`) |
| Betaflight 2025.12 SPI receiver is ELRS 3 | confirmed | `bf2025/src/main/rx/expresslrs_common.h:36` |

## 3. Priority 4 — sample of 40 swept statements outside the intro modules

All 40 confirmed. `csv` = `/tmp/ardupilot-audit/copter-4.7.2-sitl-defaults.csv`.

ArduPilot (10)

| File:line | Statement | Source |
|---|---|---|
| `content/ardupilot/ap-missions.md:47` | `WP_SPD` 10, `WP_SPD_UP/DN` 2.5 / 1.5, `WP_RADIUS_M` 2, `WP_ACC` 2.5 | csv |
| `content/ardupilot/ap-safety-fs.md:46` | `RTL_ALT_M` default 15 m | csv; conversion `ArduCopter/mode_rtl.cpp:65` |
| `content/ardupilot/ap-tuning.md:47` | `AUTOTUNE_GMBK` 0.25, P and D reduced by that fraction | csv, pdef description |
| `content/ardupilot/ap-tuning.md:50` | `ATC_INPUT_TC` 0.10 in 4.7, 0.15 in 4.6 | `AC_AttitudeControl.cpp:16` vs 4.6.3 `:16` |
| `content/ardupilot/ap-heavy.md:50` | `ATC_ACC_R/P_MAX` 500–700 °/s² = 50 000–70 000 cdeg/s²; `PSC_D_ACC_P` ≈ 0.036 vs 0.36 | units from pdef; factor `AC_PosControl.cpp:1891` |
| `content/companion/comp-mavlink.md:54, 123` | `SR2_EXTRA1` = `MAV3_EXTRA1`; `MAV2_EXTRA1` default 0; EXTRA1 carries ATTITUDE | csv, pdef `MAV1_EXTRA1` |
| `content/companion/per-tracking.md:41` | `WP_ACC` 2.5, `WP_ACC_Z` 1, `PSC_NE_JERK` 5 (4.6 `PSC_JERK_XY`) | csv; rename `ReleaseNotes.txt:85` |
| `content/estimation/nav-indoor.md:43, 55` | `EK3_SRC_OPTIONS` 0 in 4.7 (1 in 4.6); `EK3_FLOW_DELAY` 10, `EK3_FLOW_M_NSE` 0.25, `EK3_FLOW_I_GATE` 300, `EK3_FLOW_MAX` 2.5 | both csv files; `AP_NavEKF3.cpp:312` |
| `content/estimation/nav-terrain.md:44` | climb limited by `WP_SPD_UP` 2.5, descent `WP_SPD_DN` 1.5; slowdown starts above half of `WP_TER_MARGIN` (10 m) | csv; `AC_PosControl.cpp:439` |
| `tasks/nav-terrain.json` `terrain-vmax` | V = `WP_SPD_UP` / slope; recomputed all 8 variants by hand: 4.2857, 8.5714, 10, 5, 7.5, 15, 4.4444, 8.3333 — match; solution example 2.5 / 0.35 = 7.14 | arithmetic |

Betaflight (10)

| File:line | Statement | Source |
|---|---|---|
| `content/betaflight/bf-arming-safety.md:212` | `iterm_windup` 80 % × `pidsum_limit` 500 = 400 | `flight/pid_init.c:445`, `flight/pid.h:37`, `flight/pid.c:144` |
| `content/betaflight/bf-features-tour.md:88, 161` | `crashflip_rate` × 10 °/s, no attenuation below half, linear to zero; attitude attenuator to zero at ~90° | `flight/mixer.c:335-370` |
| `content/betaflight/bf-features-tour.md:136` | ground limit of dynamic idle = `motor_idle` (5.5 %), was `dyn_idle_start_increase` 50 = 5 % | `flight/mixer_init.c:358` vs 4.5.3 `:340` |
| `content/betaflight/bf-rates-rc.md:110` | `feedforward_smooth_factor` 65 → τ = 4 ms · s/(1 − s) = 7.4 ms | `flight/pid_init.c:554-556` (`rxDt = 1/250`); 4·0.65/0.35 = 7.43 |
| `content/betaflight/bf-rates-rc.md:113, 159` | `feedforward_yaw_hold_gain` 15 (0–100), `_time` 100 (10–250) | `cli/settings.c:1362-1363`, `flight/pid.c:244-245` |
| `content/betaflight/bf-failsafe.md:42` | `failsafe_landing_time` 60 s, 0–250; `landing_disarm_threshold` 0–250, default 0; condition «стики в центре и нулевой газ или ALT_HOLD» | `flight/failsafe.c:76`, `cli/settings.c:989, 1422`, `flight/pid.c:945-964` |
| `content/betaflight/bf-setup-scratch.md:86, 317` | `motor_idle` 550 → 48 + 0.055 · 1999 ≈ 158; `gps_rescue_return_alt` 30, ground speed 750, `ap_hover_throttle` 1275 | `pg/motor.c`, `pg/gps_rescue_multirotor.c:43-44`, `pg/autopilot_multirotor.c:37` |
| `content/betaflight/bf-pid-reg-in-bf.md:133` | `tpa_mode` D, `tpa_rate` 65, `tpa_breakpoint` 1350, `tpa_low_rate` 20, `tpa_low_breakpoint` 1050, `tpa_low_always` OFF | `flight/pid.c:228-236` |
| `quiz/bf-led-buzzer.json` (USB question) and `quiz/bf-rates-rc.json:74-82` | RX_LOST silent with USB in 2025.12; curve with `thr_mid = thr_hover = 40`, expo 0 is one straight line | `flight/failsafe.c:252`; `fc/rc.c:844-862` |
| `quiz/bf-arming-safety.json` (beep code) and `tasks/bf-arming-safety.json` `beeper-bit` | code = 5·long + short, bit = code − 1; 1 long + 3 short → bit 7 THROTTLE; all 8 task variants recomputed (2, 12, 13, 0, 7, 3, 1, 17) | `fc/core.c:664-668` (`ffs`), `io/beeper.c:325-343`, `fc/runtime_config.h` |

PX4 (10)

| File:line | Statement | Source (v1.17.0) |
|---|---|---|
| `content/px4/px4-control.md:49` | `MC_ROLLRATE_P/I/D` 0.15 / 0.2 / 0.003, `MC_ROLL_P` 4.0, `MC_YAW_P` 2.8 | `mc_rate_control_params.c:51, 63, 88`, `mc_att_control_params.c:53, 79` |
| `content/px4/px4-control.md:49` | `MPC_XY_P` 0.95, `MPC_XY_VEL_P/I/D_ACC` 1.8 / 0.4 / 0.2, `MPC_Z_P` 1.0, `MPC_THR_HOVER` 0.5 | `multicopter_position_control_gain_params.c:45-137`, `…_control_params.c:49` |
| `content/px4/px4-control.md:49` | `IMU_GYRO_CUTOFF` 40, `IMU_DGYRO_CUTOFF` 20 (30 before 1.17), `IMU_GYRO_DNF_MIN` 25 | `imu_gyro_parameters.c:128, 172, 222` |
| `content/px4/px4-architecture.md:28, 55` | `IMU_INTEG_RATE` 200 Hz; `COM_CPU_MAX` 95 % | `imu_parameters.c:50`, `commander_params.c:762` |
| `content/px4/px4-setup-scratch.md:37` | SITL: `COM_RC_IN_MODE` 1, `COM_LOW_BAT_ACT` 3, `SYS_FAILURE_EN` 1, `MC_AT_EN` 1, `SDLOG_MODE` 1 | `init.d-posix/rcS:170, 177, 180, 187, 190` |
| `content/px4/px4-setup-scratch.md:104, 122` | `COM_DISARM_PRFLT` 10 s, `COM_DISARM_LAND` 2 s, `COM_FAIL_ACT_T` 5 s, `NAV_RCL_ACT` 2 | `commander_params.c:227, 243, 311, 616` |
| `content/companion/per-tracking.md:48` | `MPC_XY_VEL_MAX` 12, `MPC_Z_VEL_MAX_UP/DN` 3 / 1.5, `MPC_TILTMAX_AIR` 45°, `GF_ACTION` 2 | `…_limits_params.c:47, 64, 81, 96`, `geofence_params.c:62` |
| `content/foundation/diag-troubleshooting.md:106-108` | `NAV_RCL_ACT` 6 disarm / 5 terminate / default 2; `COM_KILL_DISARM` 5 s; `COM_LKDOWN_TKO` 3 s | `commander_params.c:606-616, 747, 805` |
| `content/estimation/nav-indoor.md:83`, `nav-resilience.md:42` | `EKF2_EV_DELAY` 0, max 300; `COM_POS_LOW_ACT` since 1.16, default Return; `COM_POS_LOW_EPH` −1 | `params_external_vision.yaml:19-26`, `commander_params.c:948, 968` |
| `tasks/px4-setup-scratch.json` `soc-load` | SoC = (V_cell + I·R − 3.6) / 0.45; recomputed six variants by hand: 0.3289, 0.3111, 0.6622, 0.8667, 0.5, 0.8667 — match; solution example 3.6 + 9.8·0.005 → 0.109 | `src/lib/battery/battery.cpp:213-237` (`math::interpolate(…, v_empty, v_charged, 0, 1)`), `module.yaml` `V_CHARGED` 4.05 |

ExpressLRS (10)

| File:line | Statement | Source (4.1.0) |
|---|---|---|
| `content/link/link-elrs.md:30` | D500 sends each packet twice, D250 four times | `src/src/common.cpp:84-85` |
| `content/link/link-elrs.md:164` | disconnect 2.5 s (500, 333, FLRC), 3.5 s (150, 100), 4 s (50), 6 s (25) | `common.cpp:18-22, 94-103` (the 3 s part — finding #4) |
| `content/link/link-elrs.md:122-125` | Dynamic Power: RSSI up within 15 dB, down beyond 21 dB, 5 readings, LQ 20 % / 50 % / 85 % / 95 %, SNR statistics at LQ ≥ 99 % | `src/src/dynpower.cpp:17-28, 198` |
| `content/link/link-elrs.md:122` | 250 Hz table SNR thresholds 3 and 9.5 dB | `common.cpp:100` |
| `content/link/link-elrs.md:129`, `quiz/link-elrs.json` | 1:128 at 250 Hz → 128/250 s ≈ 0.5 s | arithmetic; `TLM_RATIO_1_128` |
| `content/link/link-elrs.md:212` | LR1121: 16 modes in 3.x, 20 in 4.x (added K1000, DK250 on 2.4; 25Hz, D50 on 900) | `elrs36/src/src/common.cpp` (16 rows), `elrs41/src/src/common.cpp:32-51` |
| `content/link/link-elrs.md:213` | RFMD numbers: 3.x 250 Hz = 7, 4.x 2.4 GHz 250 Hz = 27, 900 from 0, dual 100–101 | `elrs36/src/include/common.h:82-101`, `elrs41/src/include/common.h:83-115` |
| `content/link/link-elrs.md:215` | `TQly` window 25 → 100 | `elrs36/src/src/tx_main.cpp:78` `LQCALC<25>`, `elrs41/src/src/tx_main.cpp:79` `LQCALC<100>` |
| `content/link/link-elrs.md:145, 150` | ArduPilot MAVLink mode `SERIALn_PROTOCOL = 2`, `RSSI_TYPE = 5`, streams `MAVn_ADSB/PARAMS/RAW_CTRL`; CRSF mode 23, `RSSI_TYPE = 3`, `RC_OPTIONS` bits 9 and 13, `RC_PROTOCOLS = 512` | `copter-4.7.2.pdef.json` (value lists and bitmasks) |
| `quiz/link-elrs.json` (last 6 questions) | −108 dBm at 250 Hz, thresholds same as 3.x; 3.6 ↔ 4.1 do not link; SPI receiver options; save `hardware.json` (SPIFFS → LittleFS) | `common.cpp:100` vs `elrs36 common.cpp:92`; `targets.h:8`; LittleFS used in 6 files of 4.1, none in 3.6 |

## 4. Counts

| Table | Rows checked | Confirmed | Errors | Imprecise | Unverifiable |
|---|---|---|---|---|---|
| ArduPilot, `ap-intro.md` lines 38-89 | 52 | 51 | 0 | 1 (#5) | 0 |
| Betaflight, `bf-intro.md` lines 149-191 | 43 | 41 | 1 (#3) | 0 | 1 (#8, release only) |
| PX4, `px4-intro.md` lines 84-123 | 40 | 40 | 0 | 0 | 0 |
| ELRS packet-mode table, `link-elrs.md` lines 43-59 | 17 | 17 | 0 | 0 | 0 |
| ELRS migration table, `link-elrs.md` lines 201-221 | 21 | 13 | 0 | 0 | 8 |
| Sample of swept statements | 40 | 40 | 0 | 0 | 0 |
| **Total** | **213** | **202** | **1** | **1** | **9** |

Outside the tables: 2 errors (#1 widget, #2 `px4-architecture`), 3 imprecise (#4, #6, #7), 3 unverifiable prose items
(#9, #10, #12). Overall: 3 errors, 5 imprecise.

What "checked" means per table:

- ArduPilot: every old name exists in the 4.6.3 metadata and is absent from 4.7.2, every new name the reverse; units
  from metadata; defaults from the two SITL dumps (Copter) and from source defines (Plane `Q_A_INPUT_TC` 0.2 → 0.15,
  `AC_AttitudeControl.cpp:11` vs 4.6.3); scale factors and the existence of a conversion from the `convert_*` code;
  bit numbers from `@Bitmask`; releases from `ArduCopter/ReleaseNotes.txt` (4.7.0 21 Jul 2026, 4.7.1 31 Aug 2026,
  4.7.2 11 Oct 2026; `PSC_JERK_NE/D` → `PSC_NE/D_JERK` in 4.7.1, lines 77 and 85).
- Betaflight: names by diffing the `cli/settings.c` tables (37 removed, 131 added; 4.5.3 and 4.5.5 identical), ranges
  from the table entries, defaults from the PG reset templates, enums from `runtime_config.h`, `beeper.c`, `osd.h`,
  `debug.c`, `msp_box.c`, `serial.h`, `compass_ist8310.c:47` (0x0C → 0x0E).
- PX4: definitions and defaults in all three tags, airframe overrides in `rc.mc_defaults`, SITL `rcS` and airframe
  4001, board files, `param_translation.cpp:145-163`, `msg/versioned/*.msg` `MESSAGE_VERSION`, `dds_topics.yaml`.
- ELRS mode table: interval, sensitivity, `Std` telemetry ratio and RFMD number of every row against
  `ExpressLRS_AirRateConfig` / `ExpressLRS_AirRateRFperf` for SX127x, LR1121 and SX128x and the `expresslrs_RFrates_e` enum.
- ELRS migration table, confirmed from source: OTA version, platforms, targets (`src/targets/*.ini`), file system,
  Lua script names (`src/lua`), Full Res `12ch Mixed` channel mapping (`lib/OTA/OTA.cpp:245-246` vs 3.6 `:229-230`),
  `Wide` 128/64 (3.6 `OTA.cpp:166`), LR1121 mode count, RFMD numbering, `TQly` window, Dynamic Power 4.1 side, Bind
  Phrase Manager needing 4.1 (docs blog 2026-11-08, `RxTxEndpoint.cpp:78-80`), default baud 420000
  (`lib/OPTIONS/options.cpp:197`). Not traced (8 rows): `Arm using` / EdgeTX 2.11.0, Full Res `8ch` arm duplication
  into CH14, Antenna Mode negotiation, `RF Band` menu, telemetry +30 %, MAVLink protocol auto-switch and Yaapu, Web UI
  layout, receiver outputs list, "Telemetry Lost" delay. Nothing found that contradicts them.

## 5. Could not check

- Betaflight 2026.6 (all statements about `ELRSV4`, removed `gps_rescue_velocity_*`, IIM-42652): no source on disk.
- Betaflight 4.5.4 and ELRS 4.0.0: not on disk, so "since 4.5.4" and the 4.0 vs 4.1 split of ELRS rows rest on
  release notes.
- EdgeTX (`Arm using = Switch`, 2.11.0), Betaflight App / Cloud Build option labels, Mission Planner / QGC behaviour,
  LittleFS log erase on ArduPilot upgrade, ArduPilot downgrade behaviour: not in the firmware trees.
- Plane defaults: no Plane SITL dump; Plane rows were checked by name and unit in metadata and by source defines only.
- Anything that needs a run: lab outputs captured on the previous releases were not re-checked (they are labelled
  with their release in the modules).
- `FRAME_CLASS` reads 0 in both SITL dumps (they were taken without the `copter.parm` defaults file), so the
  `ap-intro` practice statement "`FRAME_CLASS = 1` in SITL" could not be confirmed from the dumps.
