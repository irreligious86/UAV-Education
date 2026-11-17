# ArduPilot migration 4.6.3 → 4.7.2 (Phase 0, step M1) — 2026-11-17

Scope: Copter/Plane 4.6.3 → 4.7.2 (stable; 4.7.0 21 Jul 2026, 4.7.1 31 Aug 2026, 4.7.2 11 Oct 2026).
Not committed, `scripts/publish.py` not run. `scripts/validate_content.py`: OK (140 articles, 140 quizzes, 0 errors).

## 1. Sources and method

| What | Where | Used for |
|---|---|---|
| Parameter metadata 4.6.3 | `/tmp/ardupilot-audit/copter-4.6.3.pdef.json`, `plane-4.6.3.pdef.json` | names, units, ranges, values, bitmasks |
| Parameter metadata 4.7.2 | `/tmp/ardupilot-audit/copter-4.7.2.pdef.json`; `plane-4.7.2.pdef.json` generated in this pass with `param_parse.py --vehicle ArduPlane --format json` from the `copter472` tree (tags `Copter-4.7.2` and `Plane-4.7.2` point at the same commit `fb77356`) | same |
| Source 4.7.2 | `/tmp/ardupilot-audit/copter472` | rename mapping and scale factors (the `PARAMETER_CONVERSION` tables), defaults, messages, release notes |
| Source 4.6.3 | `/tmp/ardupilot` (Copter-4.6.3), `/tmp/ardupilot-audit/plane463` | old side of each comparison |
| Firmware defaults 4.6.3 | `/tmp/ardupilot-audit/copter-sitl-defaults.csv` (1378 parameters) | default diff |
| Firmware defaults 4.7.2 | built in this pass: ArduCopter 4.7.2 SITL from a local clone of `copter472`, run with an empty defaults file, all 1351 parameters dumped over MAVLink | default diff |

Checks run over `content/` (`.md`, `quiz/*.json`, `tasks/*.json`, `pages/*.html`):

1. Every parameter-like token that exists in any of the four metadata files: 444 ArduPilot parameters are named in the course.
   Tokens that exist only in 4.6.3 were listed per file and migrated.
2. For the names present in both releases: units, ranges, values and bitmasks compared (section 3.3).
3. Defaults: the two SITL dumps compared for every name present in both, and for every renamed pair.
4. Log messages named in the course: field lists compared between the two trees (`@LoggerMessage` blocks).
5. No name used in the course exists only in `master`.

Limits of the method are in section 6.

## 2. Size of the diff

| Vehicle | 4.6.3 | 4.7.2 | Removed | Added |
|---|---|---|---|---|
| Copter | 4775 | 5687 | 217 | 1129 |
| Plane | 4850 | 5721 | 197 | 1068 |

Most additions are instance growth, not new functions: `MAV1..MAV32_*` (11 parameters each), `SIM_GPS1/3/4_*`, `SIM_IMUT*`,
`TEMP10..15_*`, `ARSPD3..6_*`, `INS_HNTC3/4_*`, `CC2_*`, `FOLLP_*`, `LTE_*`, `RK9_*`.

## 3. Full diff-derived table

### 3.1 Renamed or rescaled (Copter unless noted). "Course" = the old name was used in `content/`

| Old (4.6.3) | New (4.7.2) | Change | Release | Course |
|---|---|---|---|---|
| `ARMING_CHECK` (bitmask of enabled checks, 1 = all) | `ARMING_SKIPCHK` (bitmask of skipped checks, 0 = none skipped, −1 = skip all) | inverted; converted on boot (`AP_Arming::init`) | 4.7.0 | yes |
| `ANGLE_MAX` (cdeg, 3000) | `ATC_ANGLE_MAX` (deg, 30); Plane `Q_ANGLE_MAX` → `Q_A_ANGLE_MAX` | name, ×0.01 | 4.7.0 | yes |
| `ATC_ACCEL_R/P/Y_MAX` (cdeg/s², 110000/110000/27000) | `ATC_ACC_R/P/Y_MAX` (deg/s², 1100/1100/270) | name, ×0.01 | 4.7.0 | yes (wildcard) |
| `ATC_SLEW_YAW` (cdeg/s, 6000) | `ATC_RATE_WPY_MAX` (deg/s, 60) | name, ×0.01 | 4.7.0 | no |
| `RTL_ALT` (cm, 1500) | `RTL_ALT_M` (m, 15) | name, ×0.01 | 4.7.0 | yes |
| `RTL_ALT_FINAL`, `RTL_CLIMB_MIN` (cm) | `RTL_ALT_FINAL_M`, `RTL_CLIMB_MIN_M` (m) | name, ×0.01 | 4.7.0 | `RTL_ALT_FINAL` |
| `RTL_SPEED` (cm/s) | `RTL_SPEED_MS` (m/s) | name, ×0.01 | 4.7.0 | no |
| `WPNAV_SPEED`, `_SPEED_UP`, `_SPEED_DN` (cm/s, 1000/250/150) | `WP_SPD`, `WP_SPD_UP`, `WP_SPD_DN` (m/s, 10/2.5/1.5) | name, ×0.01 | 4.7.0 | yes |
| `WPNAV_RADIUS` (cm, 200) | `WP_RADIUS_M` (m, 2) | name, ×0.01 | 4.7.0 | yes |
| `WPNAV_ACCEL`, `_ACCEL_Z`, `_ACCEL_C` (cm/s², 250/100/0) | `WP_ACC`, `WP_ACC_Z`, `WP_ACC_CNR` (m/s², 2.5/1/0) | name, ×0.01 | 4.7.0 | `ACCEL`, `ACCEL_Z` |
| `WPNAV_JERK`, `WPNAV_RFND_USE`, `WPNAV_TER_MARGIN` | `WP_JERK`, `WP_RFND_USE`, `WP_TER_MARGIN` | prefix only | 4.7.0 | yes |
| `LAND_SPEED`, `LAND_SPEED_HIGH` (cm/s, 50/0) | `LAND_SPD_MS`, `LAND_SPD_HIGH_MS` (m/s, 0.5/0) | name, ×0.01 | 4.7.0 | no |
| `LAND_ALT_LOW` (cm, 1000) | `LAND_ALT_LOW_M` (m, 10) | name, ×0.01 | 4.7.0 | yes |
| `PILOT_SPEED_UP`, `PILOT_SPEED_DN` (cm/s, 250/0) | `PILOT_SPD_UP`, `PILOT_SPD_DN` (m/s, 2.5/0) | name, ×0.01 | 4.7.0 | no |
| `PILOT_ACCEL_Z` (cm/s², 250) | `PILOT_ACC_Z` (m/s², 2.5) | name, ×0.01 | 4.7.0 | no |
| `PILOT_TKOFF_ALT` (cm) | `PILOT_TKO_ALT_M` (m) | name, ×0.01 | 4.7.0 | no |
| `LOIT_SPEED` (cm/s, 1250) | `LOIT_SPEED_MS` (m/s, 12.5) | name, ×0.01 | 4.7.0 | no |
| `LOIT_ACC_MAX`, `LOIT_BRK_ACCEL`, `LOIT_BRK_JERK` (500/250/500) | `LOIT_ACC_MAX_M`, `LOIT_BRK_ACC_M`, `LOIT_BRK_JRK_M` (5/2.5/5) | name, ×0.01 | 4.7.0 | no |
| `PHLD_BRAKE_ANGLE` (cdeg, 3000), `PHLD_BRAKE_RATE` | `PHLD_BRK_ANGLE` (deg, 30), `PHLD_BRK_RATE` (deg/s, 8) | name; angle ×0.01 | 4.7.0 | no |
| `CIRCLE_RADIUS` (cm, 1000) | `CIRCLE_RADIUS_M` (m, 10) | name, ×0.01 | 4.7.0 | no |
| `PSC_POSXY_P`, `PSC_VELXY_P/I/D/FF/FLTD/FLTE` | `PSC_NE_POS_P`, `PSC_NE_VEL_P/I/D/FF/FLTD/FLTE` | name only | 4.7.0 | `VELXY_P` |
| `PSC_POSZ_P`, `PSC_VELZ_P/I/D/FF/FLTD/FLTE` | `PSC_D_POS_P`, `PSC_D_VEL_P/I/D/FF/FLTD/FLTE` | name only | 4.7.0 | no |
| `PSC_ACCZ_P/I/D` (0.5/1/0) | `PSC_D_ACC_P/I/D` (0.05/0.1/0) | name, ×0.1 | 4.7.0 | `P`, `I` |
| `PSC_ACCZ_FF/FLTT/FLTE/FLTD/SMAX/PDMX/D_FF/NEF/NTF` | `PSC_D_ACC_*` | name only | 4.7.0 | no |
| `PSC_VELXY_IMAX`, `PSC_VELZ_IMAX` (1000) | `PSC_NE_VEL_IMAX`, `PSC_D_VEL_IMAX` (10) | name, ×0.01 | 4.7.0 | no |
| `PSC_ACCZ_IMAX` (800) | `PSC_D_ACC_IMAX` (0.8) | name, ×0.001 | 4.7.0 | no |
| `PSC_JERK_XY`, `PSC_JERK_Z` | `PSC_NE_JERK`, `PSC_D_JERK` (4.7.0: `PSC_JERK_NE/D`) | name, twice | 4.7.0, 4.7.1 | `JERK_XY` |
| `PSC_ACC_XY_FILT` | removed | — | 4.7.0 | no |
| Plane `Q_P_POSXY/VELXY/POSZ/VELZ/ACCZ_*`, `Q_P_JERK_XY/Z`, `Q_P_ACC_XY_FILT` | `Q_P_NE_POS/NE_VEL/D_POS/D_VEL/D_ACC_*`, `Q_P_NE/D_JERK` | same rules and factors as `PSC_*` | 4.7.0, 4.7.1 | wildcard `Q_P_*` |
| Plane `Q_WP_SPEED/_UP/_DN`, `Q_WP_RADIUS`, `Q_WP_ACCEL/_Z/_C` | `Q_WP_SPD/_UP/_DN`, `Q_WP_RADIUS_M`, `Q_WP_ACC/_Z/_CNR` | name, ×0.01 | 4.7.0 | no |
| Plane `Q_LOIT_SPEED`, `Q_LOIT_ACC_MAX`, `Q_LOIT_BRK_ACCEL`, `Q_LOIT_BRK_JERK` | `Q_LOIT_SPEED_MS`, `Q_LOIT_ACC_MAX_M`, `Q_LOIT_BRK_ACC_M`, `Q_LOIT_BRK_JRK_M` | name, ×0.01 | 4.7.0 | no |
| Plane `Q_A_ACCEL_R/P/Y_MAX`, `Q_A_SLEW_YAW` | `Q_A_ACC_R/P/Y_MAX`, `Q_A_RATE_WPY_MAX` | name, ×0.01 | 4.7.0 | no |
| `SR0_*` … `SR6_*` (10 stream rates each) | `MAV1_*` … `MAV7_*` (up to `MAV32_*`), plus `MAVn_OPTIONS` | name and numbering (`SRn` → `MAV(n+1)`); **no value conversion in source** (`k_param_gcsN_unused`) | 4.7.0 | `SR1_*`, `SR2_*`, wildcards |
| `SERIALn_OPTIONS` bit 10 (no MAVLink forward), bit 12 (ignore stream-rate requests) | `MAVn_OPTIONS` bit 1, bit 2 | converted once; a leftover old bit fails pre-arm | 4.7.0 | bit 10 |
| `SYSID_THISMAV` | `MAV_SYSID` | name | 4.7.0 | yes |
| `SYSID_MYGCS` | `MAV_GCS_SYSID` (new `MAV_GCS_SYSID_HI`) | name | 4.7.0 | yes |
| `SYSID_ENFORCE` | `MAV_OPTIONS` bit 0 | parameter became a bit | 4.7.0 | no |
| `TELEM_DELAY` | `MAV_TELEM_DELAY` | name | 4.7.0 | no |
| `RNGFNDn_MIN_CM`, `RNGFNDn_MAX_CM` (cm) | `RNGFNDn_MIN`, `RNGFNDn_MAX` (m) | name, ×0.01 | 4.7.0 | yes |
| `RNGFNDn_GNDCLEAR` (cm) | `RNGFNDn_GNDCLR` (m) | name, ×0.01 | 4.7.0 | yes |
| `EK3_MAX_FLOW` | `EK3_FLOW_MAX` | name | 4.7.0 | yes |
| `AVOID_ANGLE_MAX` (cdeg) | `AVOID_ANG_MAX` (deg) | name, ×0.01; only in builds with `AP_AVOIDANCE_ALTHOLD_ENABLED` (absent from the standard SITL dump) | 4.7.0 | no (behaviour: `per-depth-avoid`) |
| `ARM_C_RTL_ALT` | `ARM_C_RTL_ALT_M` | name | 4.7.0 | no |
| `CAM_RC_TYPE/FEATURES/CONTROL/BT_DELAY/BTN_DELAY/MDE_DELAY` | `CAM1_RC_*` (`_BTN_DELY`, `_MDE_DELY`), `CAM1_TYPE = 8` RunCam | RunCam became a camera backend | 4.7.0 | no |
| `AROT_AS_ACC_MAX`, `AROT_FW_V_FF/P`, `AROT_TARG_SP` | `AROT_XY_ACC_MAX`, `AROT_FWD_*`, `AROT_FWD_SP_TARG` | autorotation rework (heli) | 4.7.0 | no |
| `FLOW_HGT_OVR`, `PLND_ORIENT`, `ARSPD_OFF_PCNT`, `VIEP_*` | removed (Copter metadata) | — | 4.7.0 | no |
| Plane `FS_SHORT_TIMEOUT` | removed | short failsafe simplified | 4.7.0 | no |
| Plane `GLIDE_SLOPE_MIN`, `GLIDE_SLOPE_THR` | `ALT_SLOPE_MIN`, `ALT_SLOPE_MAXHGT` | name | 4.7.0 | no |
| SITL `SIM_GPS_DISABLE`, `SIM_GPS2_DISABLE` | `SIM_GPS1_ENABLE`, `SIM_GPS2_ENABLE` | inverted | 4.7.0 | yes |
| SITL `SIM_GPS_*` (first receiver, no index): `_NOISE`, `_GLITCH_X/Y/Z`, `_ACC`, `_HDG`, `_POS_X/Y/Z`, `_BYTELOSS`, `_DRIFTALT`, `_LOCKTIME`, `_LAG_MS`, `_HZ`, `_NUMSATS`, `_TYPE`, `_JAM`, `_VERR_*`, `_ALT_OFS` | `SIM_GPS1_*` (`_GLTCH_X/Y/Z`, `_BYTELOS`, `_DRFTALT`, `_LCKTIME`) | index added, some names shortened | 4.7.0 | yes |
| SITL `SIM_PLD_ALT_LIMIT`, `SIM_PLD_DIST_LIMIT` | `SIM_PLD_ALT_LMT`, `SIM_PLD_DIST_LMT` | name | 4.7.0 | no |

### 3.2 Same name, changed default (SITL dumps, all 1300+ common names compared)

| Parameter | 4.6.3 | 4.7.2 | Course |
|---|---|---|---|
| `ATC_INPUT_TC` (Copter; Plane `Q_A_INPUT_TC` 0.2 → 0.15 from source) | 0.15 | 0.10 | yes (`ap-tuning`, `ap-intro`) |
| `EK3_SRC_OPTIONS` | 1 | 0 | yes (`nav-indoor`, `est-alt-sources`) |
| `LOG_MAV_RATEMAX` | 0 | 10 | no |

No other common parameter changed its default in the Copter SITL dump.

### 3.3 Same name, changed values / bitmask / range (only parameters named in the course)

| Parameter | Change | Action |
|---|---|---|
| `FS_EKF_ACTION` | new value 0 "Report only" | `ap-safety-fs`, `ap-ekf`, `ap-intro` |
| `FS_EKF_THRESH` | value 0 = disabled documented; range 0–1 | none (course tells not to touch it) |
| `EK3_SRC_OPTIONS` | new bit 3 UsePerCoreEKFSources | `nav-indoor`, `ap-intro` |
| `AHRS_OPTIONS` | new bits 3, 4 (record / reuse origin) | already in `nav-indoor`; wording made target-primary |
| `TERRAIN_OPTIONS` | new bits 1 (Disable Disk), 2 (Accept Old Terrain Data) | already in `nav-terrain` |
| Plane `TERRAIN_FOLLOW` | new bit 12 AUTOLAND | `nav-terrain` |
| `FLOW_TYPE` | new value 10 SITL (in metadata) | `nav-indoor` |
| `RCx_OPTION` | 163 "Mount Lock" → "Mount Yaw Lock"; new 185, 186, 182, 103, 104, 183 (Plane AUTOLAND), 308–316 | `payload-gimbal` (163) |
| `BATT_FS_LOW_ACT` / `BATT_FS_CRT_ACT` | 0 renamed "Warn only"; Plane adds 7 AUTOLAND or RTL | none (course already says "warning") |
| `FS_THR_ENABLE`, `FS_GCS_ENABLE`, `FS_DR_ENABLE` | value 6 text now "DO_LAND_START/DO_RETURN_PATH_START or RTL" | none |
| Plane `FENCE_ACTION` | new 8 AUTOLAND if possible else RTL | none |
| Plane `SID_AXIS` | values regrouped (VTOL 1–13, fixed wing 20+) | none (`ctl-sysid` says "by the list of your version") |
| `RNGFND1_TYPE` | 20/25 renamed, new 45–48 | none |
| `MNT1_TYPE`, `CAM1_TYPE`, `BATT_MONITOR`, `GPS_AUTO_CONFIG`, `GPS_DRV_OPTIONS`, `GPS1_GNSS_MODE`, `ARSPD_TYPE`, `INS_HNTCH_OPTS`, `BRD_OPTIONS`, `DID_OPTIONS`, `RC_PROTOCOLS`, `SERIALn_PROTOCOL`, `AHRS_EKF_TYPE` | added values/bits only | none |
| `MOT_SPIN_ARM/MIN/MAX`, `RC_FS_TIMEOUT`, `RTL_CONE_SLOPE`, `SERIAL_PASSTIMO`, `FOLL_DIST_MAX`, `SERIALn_BAUD` | range metadata only | none |
| `WP_NAVALT_MIN` | unit `m` added to metadata; applies to take-off only | none |

### 3.4 New in 4.7 that a student is likely to meet

| New | Meaning | Course |
|---|---|---|
| `LOIT_OPTIONS` (default 1) | coordinated turns in Loiter; 0 = 4.6 behaviour | `ap-intro` |
| `AUTOTUNE_GMBK` (0.25) | gain-margin back-off after AutoTune | `ap-tuning`, `ap-intro` |
| `FOLL_TIMEOUT` (3 s) | was hard-coded | `per-vision-pipeline` + quiz |
| Plane mode `AUTOLAND` (26), `AUTOLAND_*` | landing without a mission | `aero-wing`, `ap-intro` |
| `AHRS_ORIGIN_LAT/LON/ALT` | stored origin | `nav-indoor` |
| `MOT_IDLE_SEC`, `FSTRATE_ENABLE/DIV`, `TUNE2*`, `THROW_ALT_ACSND/DCSND`, `FENCE_MARGIN_XY`, `FENCE_NTF_FREQ`, `FENCE_ALT_MIN_TP/MAX_TP`, `STAT_DISTFLWN`, `STAT_FLTCNT`, `BARO1_THST_SCALE`, `INS_HNTC3/4_*`, `PARAM_LOCK_ENAB`, `THR_KILL_*`, Plane `GUIDED_TIMEOUT`, `CLIMB_SLOPE_HGT`, `FWD_BAT_THR_CUT`, `TKOFF_THR_IDLE`, `Q_THRST_LOSS_OPT`, `Q_TKOFF_RPM_MIN/MAX`, `TECS_THR_ERATE` | not referenced | not added |

### 3.5 Logs and code names

| Item | 4.6.3 | 4.7.2 | Course |
|---|---|---|---|
| Copter `CTUN.CRt`, `CTUN.DCRt` | int16, cm/s with multiplier | float, m/s | not used; in the `ap-intro` table |
| `GEN` (RichenPower) | `GEN` | `RICH` | not used; in the table |
| `BARO.Health` → `BARO.H`, `XKF5.offset` → `TOfs`/`BOf`, `RTC` fields, `MSG.ID/Seq`, `VER.IMI/ICI`, `UART.RxDp` | — | — | none of these fields is used |
| `PSCN/PSCE/PSCD` | metres in both releases | — | no change |
| `AC_PosControl::pos_offset_z_scaler` | — | `terrain_scaler_D_m` | `nav-terrain` |
| `AC_PosControl::input_vel_accel_xy` | — | `input_vel_accel_NE_m` | `per-tracking` |
| Pre-arm text for RTL above terrain with rangefinder | — | "RTL_ALT_TYPE is above-terrain but RTL_ALT_M above RNGFND_MAX" | `nav-terrain` |
| `failsafe_terrain_on_event()` calls in `mode_auto.cpp` | 8 | 10 (the module said 11) | `nav-terrain` corrected |

### 3.6 Renames expected by the brief that do not exist in 4.7.2

- "`FS_*` timeouts with `_MS`": there is no such rename in 4.7.2. `FS_GCS_TIMEOUT`, `FS_DR_TIMEOUT`, `RC_FS_TIMEOUT`,
  Plane `FS_LONG_TIMEOUT` keep their names. `FS_TERRAIN_TIMEOUT_MS` is a compile-time constant (5000 ms in both releases).
- `RTL_LOIT_TIME` stays in milliseconds; `RTL_CONE_SLOPE`, `PSC_ANGLE_MAX`, `WP_YAW_BEHAVIOR`, `WP_NAVALT_MIN` are unchanged.

## 4. What was written

- `content/ardupilot/ap-intro.md`: section «Версии и имена параметров» rewritten for 4.7.2; new `###` subsection
  «Переход 4.6 → 4.7: что переименовано и изменилось» inside `## theory`: 7 numbered lines of procedure and traps, a
  52-row table (old | new | what changed | since), and a list of frequently asked names that did not change.
- Policy applied everywhere: new name is primary, old name once in brackets with the unit; existing "in 4.7 this is X" notes
  inverted; numbers converted where the unit changed.
- Pasted output from 4.6.3 left untouched, with one line above the block where the block shows a name that differs:
  `ap-setup-scratch` (step 12), `nav-indoor` (parameter block; the note also covers the following output),
  `nav-rtk` (step 1), `nav-vtrn` (step 6). `quiz/nav-terrain.json` keeps its 4.6.3 log fragment; the note is in `explain`.
- `tasks/nav-terrain.json` task `terrain-vmax`: `{up}` is now in m/s (`[1.5, 2.0, 2.5, 3.0]`), formula `up/(s/100)`;
  same answers as before. No answer index or option count changed in any quiz.
- `ap-sitl`: one prose line after the clone command telling the student to check out tag `Copter-4.7.2`
  (the plain clone is `master`).

### Files changed (53 files, 191 edit operations, 224 string replacements)

| File | Edits | File | Edits |
|---|---|---|---|
| `ardupilot/ap-intro.md` | 10 | `estimation/nav-terrain.md` | 17 (50 replacements) |
| `ardupilot/ap-setup-scratch.md` | 13 | `estimation/nav-indoor.md` | 16 |
| `ardupilot/ap-safety-fs.md` | 6 | `estimation/nav-rtk.md` | 10 |
| `ardupilot/ap-tuning.md` | 5 | `estimation/est-alt-sources.md` | 6 |
| `ardupilot/ap-sitl.md` | 4 | `estimation/nav-resilience.md` | 3 |
| `ardupilot/ap-heavy.md` | 2 | `companion/per-vision-pipeline.md` | 7 |
| `ardupilot/ap-companion.md` | 2 | `companion/per-tracking.md` | 6 |
| `ardupilot/ap-missions.md` | 2 | `companion/nav-vtrn.md` | 4 |
| `ardupilot/ap-ekf.md` | 2 | `companion/mav-routing.md` | 3 |
| `ardupilot/ap-quadplane.md` | 2 | `companion/mav-services.md` | 3 |
| `ardupilot/aero-wing.md` | 2 | `companion/comp-intro.md` | 2 |
| `ardupilot/ap-logs.md` | 1 | `companion/comp-mavlink.md` | 2 |
| `ardupilot/ap-lua.md` | 1 | `companion/mav-component.md` | 2 |
| `ardupilot/ap-plane-tuning.md` | 1 | `companion/per-depth-avoid.md` | 2 |
| `pages/setup-cards.html` (ArduCopter card and its link text only) | 6 | `companion/payload-gimbal.md` | 2 |
| `betaflight/bf-hd-osd-video.md` (ArduPilot column header, front-matter segment) | 2 | `companion/eng-ci-configs.md` | 1 |
| `design/des-sizing.md` | 4 | `companion/fw-reading.md` | 1 |
| `design/ctl-allocation.md` | 2 | `companion/mav-multi-vehicle.md` | 1 |
| `design/aero-stability.md` | 1 | `companion/comp-raspberry.md` | 1 |
| `electronics/el-peripherals.md` | 2 | `companion/comp-jetson-nano.md` | 1 |
| `electronics/el-dronecan.md` | 1 | `foundation/f-physics.md` | 1 |
| `electronics/el-kicad.md` | 1 | `tools/ctl-guidance.md` | 1 |
| `quiz/nav-terrain.json` | 10 | `tasks/nav-terrain.json` | 6 |
| `quiz/nav-indoor.json` | 3 | `tasks/nav-indoor.json` | 2 |
| `quiz/mav-routing.json` | 2 | `quiz/comp-mavlink.json` | 1 |
| `quiz/ap-companion.json` | 1 | `quiz/nav-resilience.json` | 1 |
| `quiz/per-vision-pipeline.json` | 1 | | |

Checked, no edit needed (already new-primary or no renamed item): `foundation/f-safety.md`, `foundation/diag-troubleshooting.md`,
`link/link-telemetry-radios.md`, `tools/ctl-theory.md`, `quiz/ap-intro.json`, `quiz/ap-safety-fs.json`,
`quiz/mav-multi-vehicle.json`.

Front matter `firmware:` → 4.7: all 14 modules in `content/ardupilot/`; the ArduPilot segment only in `nav-indoor`,
`nav-terrain`, `nav-rtk`, `nav-vtrn`, `per-vision-pipeline`, `comp-jetson-nano`, `comp-raspberry`, `payload-gimbal`,
`mav-multi-vehicle`, `des-sizing`, `ctl-allocation`, `aero-stability`, `el-kicad`, `el-dronecan`, `bf-hd-osd-video`.
Other firmware segments on those lines were not touched.

## 5. Left on the old release, with the reason

| Item | Where | Reason |
|---|---|---|
| All pasted SITL output and the numbers derived from it | `ap-setup-scratch`, `nav-indoor`, `nav-terrain`, `nav-rtk`, `nav-vtrn`, `per-vision-pipeline`, `comp-jetson-nano` | captured on Copter-4.6.3; Phase 2 re-runs the labs. Front matter says so |
| Rule `PSC_D_ACC_P = 0.1 × MOT_THST_HOVER`, `PSC_D_ACC_I = 0.2 × MOT_THST_HOVER` | `ap-setup-scratch`, `ap-tuning`, `ap-heavy`, setup card | the documented rule was verified for 4.6 (`PSC_ACCZ_P = MOT_THST_HOVER`); the 4.7 form is that rule times the ×0.1 conversion factor from source, and is marked so in `ap-setup-scratch`. Not checked against the 4.7 tuning documentation |
| "GUIDED velocity targets are not limited by `WP_SPD`" | `per-tracking`, `per-vision-pipeline` | measured on 4.6.3; for 4.7.2 only the code path was read (`velaccel_control_run` → `input_vel_accel_NE_m`, acceleration and jerk limits only). Text states both |
| Source links to `Copter-4.6.3` in reference lists | `nav-indoor`, `nav-terrain`, `nav-rtk`, `nav-vtrn`, `per-tracking`, `per-vision-pipeline`, `comp-jetson-nano`, `ap-setup-scratch` | they document what the lab ran on. `ap-setup-scratch`, `des-sizing`, `ctl-allocation` got a 4.7.2 link |
| Diagram `ap-setup-flow` title "ArduCopter 4.6 с нуля", and the same words in its caption | `scripts/diagrams/s6_ap_setup_scratch.py`, `ap-setup-scratch` | diagram build is not allowed in this pass; the steps themselves are unchanged |
| Diagram `chart-terrain-agl` | `nav-terrain` | caption now says `WP_SPD_UP` / `WP_SPD_DN`; the image was not rebuilt and may carry the old labels |
| `firmware:` "ArduPilot 4.5+" or unversioned "ArduPilot" | modules outside the track where the field carries no lab version: `link/*`, `tools/*`, `ros2/*`, `math/*`, `foundation/f-esc-firmware`, `f-remote-id-security`, `betaflight/bf-custom`, most `companion/mav-*`, `per-*` | not modules of this track; their ArduPilot parameter names were swept, the field was left for the owner of the file |
| `i18n/` and generated directories | — | out of scope by the brief |

## 6. Not verified / open questions

1. **LittleFS log erase on upgrade.** Comes from the 4.7.0 release thread via the FAQ report (V14). The 4.7.2 release notes
   only say the opposite fix ("boards with small flash-based sdcard logging do not erase all logs on boot"). `ap-intro`
   states it as a developer report, not verified from source.
2. **"Update Mission Planner / QGC".** Same origin (V13); not verifiable from the firmware tree.
3. **Downgrade to 4.6.** The text says values changed under the new names do not convert back. This follows from the
   one-way conversion code; it was not tested on a board.
4. **Plane defaults.** No Plane SITL was built. Plane-only parameters named in the course (66) were compared at source level
   (definition lines in `ArduPlane/` and the fixed-wing libraries): no default changed. A full Plane default dump is still missing.
5. **`SRn_*` values are not migrated.** Concluded from the absence of any conversion for the old `SR0..SR6` keys in 4.7.2
   (`k_param_gcsN_unused`, "SR0 through SR6 was here"). Not tested by upgrading a parameter store.
6. **`nav-indoor` parameter block** lists `SIM_GPS1_ENABLE 0`, a name that does not exist in 4.6.3 (there it is
   `SIM_GPS_DISABLE`). The block was left as pasted and the note above it says so; the lab is unaffected because
   `GPS1_TYPE 0` disables the receiver anyway. To be settled when the lab is re-run.
7. **`EK3_SRC_OPTIONS` default 1 → 0** may change numbers in the `nav-indoor` and `est-alt-sources` labs on re-run.
8. **`ATC_INPUT_TC` 0.15 → 0.10 and coordinated Loiter turns** will change stick-feel descriptions and any Loiter lab output.
9. **firmware.ardupilot.org folder name** `stable-4.7.2` in `ap-setup-scratch` follows the existing naming pattern; the
   server was not opened in this pass. The text offers `stable` first.
10. **Depth of the "сверено с 4.7.2" label.** It means: every ArduPilot parameter name, unit, default (Copter), value list
    and log field named in the module was checked against 4.7.2 by the diffs in section 1, plus the specific source facts
    listed in this report. Prose about algorithms that names no parameter (EKF internals, TECS, L1, mission logic) was not
    re-read against 4.7.2 source line by line.
11. **Other vehicles.** Rover, Sub, Heli and AP_Periph changes are not covered; the course does not use them.

## 7. Artifacts

- `/tmp/ardupilot-audit/plane-4.7.2.pdef.json` — generated Plane 4.7.2 metadata.
- Session scratchpad `/tmp/claude-0/-home-claude/5eb82644-9f61-54ed-8ad3-a66cf9a59c5c/scratchpad/`:
  `copter472-sitl-defaults.csv` (4.7.2 firmware defaults), `ap472/` (clone with the built SITL binary
  `build/sitl/bin/arducopter`), `pdiff.txt` (raw metadata diff), `edits.log` (every replacement, old and new string).
  The scratchpad is not durable; copy the CSV and the binary if Phase 2 needs them.
