# PX4 migration 1.15 → 1.17.0 — 2026-11-17

Phase 0, step M3 of `docs/COURSE-PLAN-THEORY.md`. Target: tag **v1.17.0** (`/tmp/px4-audit-v1.17.0`). Previous releases:
**v1.15.4** (`/tmp/px4-audit`, the old course base) and **v1.16.2** (`/tmp/px4-audit-v1.16.2`). Nothing was committed,
`publish.py` was not run, `i18n/` and generated directories were not touched. `scripts/validate_content.py`: OK (140
articles, 140 quizzes) after the edits.

## 1. Method

- Parameters: every `module.yaml` / `params*.yaml` (loaded with `yaml.safe_load`, `${i}` instances expanded) and every
  `PARAM_DEFINE_INT32/FLOAT` with its comment block, for the three tags. 1987 / 2189 / 2200 source-defined names.
  Generated names (`*_CONFIG`, `SER_*_BAUD`, `PWM_*`) were read by hand in `serial_config` blocks and generators.
- Airframe defaults: `diff` of `rc.mc_defaults`, `rc.fw_defaults`, `rc.vtol_defaults`, `init.d-posix/rcS`,
  `4001_gz_x500`, `10040_sihsim_quadx`, `4001_quad_x`.
- Also diffed: `mavlink_receiver.cpp` message cases, `dds_topics.yaml`, `MESSAGE_VERSION` in `msg/versioned/`,
  `default.px4board` of fmu-v5/v5x/v6c/v6x/v6xrt, `battery.cpp`, `failsafe.cpp`, `param_translation.cpp`.
- Parser caveat: where a name is defined twice the first definition was compared. This produced two false rows
  (`CA_METHOD`, `CA_AIRFRAME` default "changed"); both were checked by hand and are unchanged (2 and 0).
- The in-tree `docs/en/releases/` of v1.17.0 has no `1.17.md` (only an unfinished `main.md`), so release notes were not a
  source; everything below is from source diffs.

## 2. Diff-derived table

### 2.1 Rows in the course (`content/px4/px4-intro.md`, «Переход 1.15 → 1.17», 39 rows)

| Item | 1.15.4 | 1.16.2 | 1.17.0 | Source |
|---|---|---|---|---|
| `BATn_V_LOAD_DROP` | 0.1 | removed | — | `lib/battery/module.yaml`, `battery.cpp` |
| `BATn_R_INTERNAL` default | 0.005 | −1 | −1 (online RLS estimate, start 0.005 Ω/cell; no correction without current) | `battery.cpp`, `battery.h` |
| `BAT_N_CELLS`, `BAT_V_EMPTY`, `BAT_V_CHARGED`, `BAT_V_LOAD_DROP` | present | removed | — | param diff |
| `COM_ARM_BAT_MIN` | 0 | −1 | −1 | `commander_params.c` |
| `DSHOT_BIDIR_EN` | absent | added | present | `drivers/dshot/module.yaml` |
| `DSHOT_MIN` unit | % | % | norm (default 0.055 unchanged) | same |
| `msp_osd` | DJI legacy MSP | MSP DisplayPort + `OSD_RC_STICK` | same as 1.16 | audit §1.4; 1.16→1.17 diff of `msp_osd.cpp` (first 400 lines) empty |
| `EKF2_EV_CTRL` | 15 | 0 | 0 | `params_external_vision.yaml` |
| `EKF2_OF_CTRL` | 0 | 1 | 1 | `params_optical_flow.yaml` |
| `EKF2_AGP_CTRL` / `EKF2_AGP_MODE` | 1 / — | 0 / — | 0 / added | `params_aux_global_position.yaml` |
| `EKF2_GPS_CHECK` | 245 (max 511) | 1023 (bit 9 Spoofing) | 2047 (bit 10 fix type, `EKF2_REQ_FIX` = 3) | `params_gnss.yaml` |
| `EKF2_TERR_MASK` | present | removed | — | param diff |
| `COM_ARM_EKF_HGT/POS/VEL/YAW`, `COM_POS_FS_DELAY` | present | removed | — | param diff |
| `COM_POS_LOW_ACT` | absent | 3 | 3 (`COM_POS_LOW_EPH` −1 existed in 1.15) | `commander_params.c` |
| `COM_DLL_EXCEPT` | absent | 0 | 0 | same |
| `COM_POSCTL_NAVL` | 0 | 0 | removed; Position → Altitude → Stabilized hard-coded | `failsafe.cpp` `checkModeFallback` |
| `COM_FLTT_LOW_ACT` | 3 | 3 | 0 | `commander_params.c` |
| `COM_RC_IN_MODE` | 0…4 | 0…4 | 0…8, labels "MAVLink" | same |
| `COM_OBL_RC_ACT` value 2 label; RC-less fallback | Manual | Stabilized | Stabilized; Pos/Alt/Stab fallback without manual control → `NAV_RCL_ACT` | `commander_params.c`, `failsafe.cpp` |
| `COM_FLTMODEn` | …13 | …13 | + 16 Altitude Cruise | `commander/module.yaml` |
| `RC_MAP_ACRO_SW/MAN_SW/POSCTL_SW/RATT_SW/STAB_SW` | present | removed | — | param diff |
| `MPC_HOLD_DZ` → `MAN_DEADZONE` | `MPC_HOLD_DZ` | `MPC_HOLD_DZ` | `MAN_DEADZONE` 0.1 | `manual_control_params.c`, `releases/main.md` |
| `MPC_XY_MAN_EXPO`, `MPC_Z_MAN_EXPO`, `MPC_YAW_EXPO` | present | present | removed | param diff, `releases/main.md` |
| `RC1_DZ`…`RC18_DZ` | present | present | removed | param diff |
| `MC_ROLL_P`, `MC_PITCH_P` | 6.5 | 6.5 | 4.0 | `mc_att_control_params.c` |
| `IMU_DGYRO_CUTOFF` | 30 | 30 | 20 | `imu_gyro_parameters.c` |
| `MPC_YAWRAUTO_MAX` / `MPC_YAWRAUTO_ACC` | 45 / 60 | 45 / 60 | 60 / 20 | param diff |
| `GPS_UBX_DYNMODEL` for multicopters | 6 (`rc.mc_defaults`) | 6 | 7 (override removed; parameter default 7 in all three) | `rc.mc_defaults`, `gps/params.c` |
| `MAV_PROTO_VER` | 0 | 0 (SITL 2) | 2 | `mavlink_params.c`, `rcS` |
| `MIS_PD_TO` → `MIS_COMMAND_TOUT` | `MIS_PD_TO` | `MIS_COMMAND_TOUT` | same | param diff |
| `MIS_DIST_1WP` | 900 | 10000 | 10000 | param diff |
| `COM_OBS_AVOID`, `TRAJECTORY_REPRESENTATION_*`, `COLLISION` | present | removed | — | param diff, `mavlink_receiver.cpp` |
| `SDLOG_MODE` −1 → `SDLOG_BACKEND` | — | — | `SDLOG_BACKEND` added (default 3); −1 translated on import | `logger/module.yaml`, `param_translation.cpp` |
| `msg/VehicleCommand.msg` | `msg/` | `msg/versioned/` | `msg/versioned/` | tree |
| `/fmu/out/vehicle_status` | no suffix | `_v1` | `_v1` | `MESSAGE_VERSION` |
| `vehicle_local_position`, `battery_status`, `home_position`, `airspeed_validated`, `arming_check_request`, in: `vehicle_attitude_setpoint` | no suffix | no suffix | `_v1` | `MESSAGE_VERSION` |
| `UXRCE_DDS_RX_TO`/`TX_TO`; `UXRCE_DDS_NS_IDX` | absent | added; absent | present; added | `uxrce_dds_client/module.yaml` |
| fmu-v6x default build RC drivers | `rc_input` | `rc_input` | `COMMON_RC` (`crsf_rc`, `sbus_rc`, `dsm_rc`, `ghst_rc`), no `rc_input` | `boards/px4/fmu-v6x/default.px4board` |
| SITL `COM_LOW_BAT_ACT`; `gz_x500` `NAV_DLL_ACT` | 2; 0 | 3; 2 | 3; 2 | `init.d-posix/rcS`, `4001_gz_x500` |

### 2.2 Re-checked facts from `px4-fixes-2026-11-15.md` (state in 1.17.0)

| Fact | 1.17.0 | Course now |
|---|---|---|
| `IMU_DGYRO_CUTOFF` | 20 (was 30) | 20 primary, "до 1.17 — 30" |
| Bidirectional DShot | `DSHOT_BIDIR_EN` since 1.16; H7 boards / FMU outputs only (docs `peripherals/dshot.md`) | bidir primary, UART telemetry as the 1.15 note |
| `BAT1_V_LOAD_DROP` / `BAT1_R_INTERNAL` | removed / −1 | theory rewritten for the 1.17 formula; quiz and task rebuilt on `R·I` |
| `RTL_RETURN_ALT` override | 30 m, `RTL_DESCEND_ALT` 10 m in `rc.mc_defaults`; parameter 60 — unchanged | unchanged |
| `NAV_DLL_ACT` | 0 (gz_x500 SITL airframe sets 2 since 1.16) | unchanged + table row |
| `MC_AT_EN` | 0, SITL 1 — unchanged | unchanged |
| `IMU_GYRO_RATEMAX` | 400, multicopter 800, max 2000 — unchanged | unchanged |
| `COM_RC_LOSS_T` 0.5, `COM_FAIL_ACT_T` 5, `NAV_RCL_ACT` 2, `COM_DISARM_LAND` 2, `COM_DISARM_PRFLT` 10, `COM_OF_LOSS_T` 1, `COM_LOW_BAT_ACT` 0, `COM_CPU_MAX` 95 | unchanged | unchanged |
| `msp_osd` | DisplayPort since 1.16 | noted in `px4-setup-scratch` step 12 and the card |
| `EKF2_*` | see 2.1 | `nav-indoor`, `nav-vtrn` updated |
| uXRCE-DDS | `UXRCE_DDS_CFG` unchanged; three new parameters; `_v1` topics | `px4-ros2`, `px4-companion-jetson` updated |
| SITL targets | `make px4_sitl gz_x500` and `make px4_sitl sihsim_quadx` both exist in 1.17 (SIH gained `sihsim_hex`, `sihsim_standard_vtol`, `sihsim_rover_ackermann`) | unchanged |
| `MAV_1_CONFIG` default Disabled, `SER_TEL1_BAUD` 57600, `SER_TEL2_BAUD` 921600, `MAV_0_RATE` 1200 | unchanged | unchanged |
| `failure rc_signal off` | no handler for `FAILURE_UNIT_SYSTEM_RC_SIGNAL` in 1.17 sources either | wording changed from "1.15" to "1.15 run, no handler in 1.17" |

### 2.3 Rows not used in the course (compact)

- **Removed in 1.16 (35):** above, plus `FW_SPOILERS_DESC`, `MOT_SLEW_MAX`, `PD_GRIPPER_EN`, 12 × `RDD_*` (old rover).
- **Added in 1.16 (237 by this parser; the audit counted 236):** 85 × `CA_THRUSTER*`, `ICE_*`, `VTQ_*`, `RO_*`/`RA_*`/`RD_*`/`RM_*`
  rover, `SIM_GZ_SV_*`, `MAV_n_HL_FREQ`, `MPC_VEL_LP`, `MPC_VEL_NF_FRQ/BW`, `MC_YAW_TQ_CUTOFF`, `NAV_MIN_GND_DIST`, `RC_GHST_TEL_EN`,
  `SENS_FLOW_SCALE`, `BATn_I_OVERWRITE`, `CA_MAX_SVO_THROW`, `COM_MODE_ARM_CHK`, `COM_RAM_MAX`, `EKF2_RNG_FOG` (multicopter
  airframe sets 1.0), `EKF2_VEL_LIM`, `EKF2_GPS_YAW_OFF`, `SYS_PARAM_VER`, `SYS_HAS_NUM_OF`, `MC_ORBIT_YAW_MOD`.
- **Other 1.16 changes:** `BAT_CRIT_THR` max 0.25 → 0.5, `BAT_EMERGEN_THR` max 0.1 → 0.5, `COM_RCL_EXCEPT` max 31 → 7 (→ 31 again in
  1.17 with bits External Mode and Altitude Cruise), `CA_Rn_SLEW`/`CA_SVn_SLEW` unit s, `SIH_LOC_LAT0/LON0` unit deg·1e7 → deg,
  `PD_GRIPPER_TO` 3 → 1, `rc.fw_defaults` drops `COM_POS_FS_DELAY 5` and `EKF2_GPS_CHECK 21`, SITL drops `CBRK_SUPPLY_CHK`,
  DDS topics `vehicle_trajectory_*`, `differential_drive_setpoint` removed, `distance_sensor`, `home_position`,
  `vehicle_land_detected`, `vtol_vehicle_status` added.
- **Removed in 1.17 (144):** 85 × `CA_THRUSTER*`, `ASPD_FALLBACK_GW` (→ `ASPD_FALLBACK`), `EKF2_RNG_A_IGATE`, `FW_AT_SYSID_AMP`,
  18 × `GND_*`, `NPFG_EN_MIN_GSP`, `NPFG_GSP_MAX_TK`, `NPFG_TRACK_KEEP`, `NPFG_WIND_REG`, `RWTO_HDG`, `RWTO_NPFG_PERIOD`,
  `RD_/RM_MAX_THR_YAW_R`, `RD_/RM_MISS_SPD_GAIN`, 6 × `UUV_*`.
- **Added in 1.17 (155):** `EKF2_GPS_MODE`, `EKF2_REQ_FIX`, `GPS_CFG_WIPE`, `MAV_S_MODE`, `MAV_S_FORWARD`, `MC_NN_*`, `RC_MAP_TERM_SW`,
  `RC_PAYLOAD_MIDTH`, `SENS_BAR_AUTOCAL`, `SIM_GZ_EN_*`, `SYS_HF_MAV`, `UAVCAN_ESC_IFACE`, `PWM_VOLT_SEL`, `ZENOH_DOMAIN_ID`,
  `SC_*`/`SPC_*` (spacecraft), `MS_*`, `SBG_*`, `CORE_*`, `UUV_*`, `FW_AIRSPD_FLP_SC`.
- **Other 1.17 changes:** `EKF2_MIN_RNG` 0.1 → 0.01, `ASPD_WERR_THR` 0.55 → 2, `FW_AT_SYSID_F1` 20 → 10, `FW_AT_SYSID_TYPE` 0 → 1,
  `ICE_EN` true → false, `INA238_SHUNT` 0.0003 → 0.0005, `MC_YAWRATE_K` min 0 → 0.01, `NAV_LOITER_RAD` range ±10000,
  `SDLOG_PROFILE` max 4095 (bit 11 High rate sensors), `SENS_BOARD_*_OFF` range ±45, several `FW_*` max limits removed,
  `rc.fw_defaults`/`rc.vtol_defaults` drop `COM_POS_FS_EPH 50`, DDS topics `transponder_report`, `wind`,
  `gimbal_device_attitude_status`, fixed-wing and rover setpoints, `landing_gear` added.

## 3. Files changed (42 files, 151 replacements: 115 targeted + 36 link re-pins)

| File | Targeted | Links | What |
|---|---|---|---|
| `content/px4/px4-intro.md` | 11 | (2 in targeted) | `firmware:`; new `###` «Переход 1.15 → 1.17…» (6 procedure lines, 39-row table, "unchanged" line); defaults inverted |
| `content/px4/px4-control.md` | 9 | (4) | `firmware:`; `MC_ROLL_P`, `IMU_DGYRO_CUTOFF`, DShot notes inverted; pointer to the table |
| `content/px4/px4-architecture.md` | 6 | (4) | `firmware:`; `msg/versioned/` primary |
| `content/px4/px4-ros2.md` | 7 | (3) | `firmware:`; `_v1` topics primary; `NAV_RCL_ACT` fallback note |
| `content/px4/px4-companion-jetson.md` | 4 | (2) | `firmware:`; versioned topic list |
| `content/px4/px4-setup-scratch.md` | 27 | (13) | `firmware:`; RC drivers for 1.17; battery formula; SITL `COM_LOW_BAT_ACT` 3; four "вывод снят на v1.15.4" notes; OSD; references |
| `content/quiz/px4-intro.json` | 1 | | filter question inverted |
| `content/quiz/px4-setup-scratch.json` | 6 | | Q1 on `crsf_rc`/`RC_CRSF_PRT_CFG`; Q5 1.17; Q6 rebuilt on `R·I` (same options, answer index 2, same numbers) |
| `content/tasks/px4-setup-scratch.json` | 4 | | `soc-load`: statement, solution and ranges of `u` (now current, 5–20 A) and `d` (now Ω, 0.003–0.006); formula string unchanged |
| `content/pages/setup-cards.html` | 8 | | PX4 card only: heading, nav link, version line, steps 3, 4, 12, 13, PX4 token in the footer |
| `content/estimation/nav-indoor.md` | 4 | 1 | `EKF2_EV_CTRL` 0, `EKF2_OF_CTRL` 1; PX4 part of `firmware:`; source ref |
| `content/estimation/nav-resilience.md` | 2 | 0 | `COM_POSCTL_NAVL` replaced by 1.17 behaviour and `COM_POS_LOW_ACT` |
| `content/estimation/nav-rtk.md`, `quiz/nav-rtk.json` | 2 + 1 | 2 | version labels (values unchanged in 1.17) |
| `content/estimation/nav-terrain.md` | 4 | 2 | version labels; out-of-range behaviour marked "проверено на 1.15" |
| `content/companion/nav-vtrn.md`, `quiz/nav-vtrn.json` | 6 + 3 | 1 | `EKF2_EV_CTRL`/`EKF2_AGP_CTRL` defaults; `GPS_INPUT` still unhandled in 1.17 |
| `content/companion/per-vision-pipeline.md` | 3 | 2 | version labels, source ref |
| `content/companion/comp-jetson-nano.md` | 2 | 0 | version label, source ref |
| `content/companion/payload-gimbal.md`, `mav-multi-vehicle.md`, `content/electronics/el-dronecan.md` | 1 each | 1 each | PX4 part of `firmware:` (statements verified unchanged) |
| `content/design/ctl-allocation.md` | 1 | 3 | PX4 part of `firmware:` |
| `content/ros2/ros2-px4.md` | 1 | 4 | `COM_OBL_RC_ACT` value list |
| Links only (1 each): `ardupilot/ap-plane-tuning.md`, `companion/comp-intro.md`, `mav-component.md`, `mav-sdk.md`, `per-depth-avoid.md`, `per-landing.md`, `per-tracking.md`, `per-visual-nav.md`, `estimation/est-attitude.md`, `est-kalman.md`, `foundation/f-mechanics.md`, `math/math-prob-est.md`, `pages/resources.html`, `ros2/ros2-basics.md`, `ros2-nav.md`, `tools/ctl-guidance.md`, `ctl-theory.md`, `tools-gazebo.md` | 0 | 18 | `docs.px4.io/main` → `/v1.17` |

Structure: no `## ` section added or removed, no directive changed, code-fence counts unchanged, no code block edited.
Quiz option counts and answer indexes unchanged.

## 4. Links

Each distinct docs path was fetched once under `/v1.17/` with WebFetch (curl does not get through the session proxy).
Confirmed (title "… | PX4 Guide (v1.17)"): all paths used in the course except those below.

- **Re-pinned with a changed path:** `v1.15/en/config/autotune.html` does not exist under v1.17 → `v1.17/en/config/autotune_mc.html`.
  Four directory URLs failed with the trailing-slash form under v1.17 but load as `index.html`, so they were pinned to
  `…/companion_computer/index.html`, `…/config_fw/index.html`, `…/dronecan/index.html`, `…/flight_modes_mc/index.html`.
  Two links without `.html` (`advanced_features/precland`, `computer_vision/collision_prevention`) were pinned to the confirmed
  `.html` form.
- **Left as they were:**
  - `docs.px4.io/main/en/config/motor_failure_detection` (`el-redundancy.md`) — fetch under v1.17 failed and the page is not
    in the v1.17.0 `docs/en/` tree. Whether it exists on `main` was not checked.
  - `docs.px4.io/main/en/config/safety.html` (`nav-resilience.md`) and `docs.px4.io/v1.15/en/config/safety.html`
    (`px4-setup-scratch.md`) — the fetch of `v1.17/en/config/safety.html` was blocked (permission request timed out) and was
    not retried. The page exists in the v1.17.0 `docs/en/config/safety.md` tree, so re-pinning is probably safe once fetched.
- GitHub source links moved from `v1.15.4` to `v1.17.0` only where the file exists in the v1.17.0 tree (EKF2 parameters
  moved from `module.yaml` to `params_*.yaml`, so those links now point to the `ekf2` directory).

## 5. Left on the old release

| Item | Why |
|---|---|
| All pasted SITL output in `px4-setup-scratch` (build log, `param show`, `actuator_test`, RC-loss and battery journals, autotune table, `param show-for-airframe`, HTE chart) | Run on v1.15.4; PX4 was not built or run in this pass. Labelled "снят на v1.15.4" with what differs in 1.17. Phase 2 re-runs it |
| Battery failsafe narrative in step 6 (0.109 → LOW) | It is the 1.15 `BAT1_V_LOAD_DROP` computation behind the pasted journal; the 1.17 numbers need a run |
| `git clone --branch v1.15.4` in the step 1 code block | The pasted output below depends on it; the note above gives `--branch v1.17.0` |
| `nav-terrain`: "sensor out of range → silently falls back to EKF height", and its quiz question labelled PX4 1.15 | Behaviour verified on 1.15 only; `MPC_ALT_MODE` values and default were verified for 1.17 |
| `firmware:` "PX4 1.15+" in `link/link-telemetry-radios.md`, `tools/tools-gazebo.md`, `tools/ctl-guidance.md`, `foundation/f-remote-id-security.md`, `content/article-template.md` | Outside the listed scope and not fully re-read; the single PX4 parameters they name (`MAV_SYS_ID`, `NPFG_*`, `gz_x500*`, `PX4_GZ_WORLD`) exist unchanged in 1.17 |

## 6. Open questions

1. **CRSF docs vs source.** The v1.17 "CRSF Telemetry" page still says CRSF needs a custom build without `rc_input`. The
   v1.17.0 `default.px4board` of fmu-v6x, fmu-v6xrt and fmu-v5x selects `COMMON_RC` and has no `rc_input`. The course follows
   the source. Not verified on hardware: whether SBUS on the RC IN port of an fmu-v6x still works through IO as before.
2. **`failure rc_signal off` in 1.17.** No handler in the sources; the exact console reply on 1.17 is unknown until a run.
3. **Battery simulator on 1.17.** Whether the SIH/gz battery simulator reports a current (which decides the load
   correction in the failsafe lab) was not traced.
4. **`COM_POS_FS_DELAY`.** The audit says the delay is now fixed at 1 s; this pass only confirmed the removal.
5. **`px4-architecture` worked example** says "`listener vehicle_angular_velocity` — частота ~400 Гц?" while the same module
   states 800 Hz for multicopters. Not a version issue, left unchanged.
6. **`px4_msgs` branch name** for 1.17 was not checked; the course keeps "ветка под версию PX4".
7. **msp_osd and goggles.** Still undocumented by PX4 which HD systems the DisplayPort driver works with.
8. `i18n/` copies of the edited modules are now behind the Russian text.
