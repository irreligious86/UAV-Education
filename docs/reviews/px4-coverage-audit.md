# PX4 coverage audit: console, QGC Vehicle Setup, parameters, in-flight tuning, popular questions, hardware integration

Date: 2026-11-15. Scope: the PX4 track (`content/px4/*.md`, 6 modules: `px4-intro`, `px4-setup-scratch`, `px4-architecture`,
`px4-control`, `px4-ros2`, `px4-companion-jetson`), their quiz/task banks, the PX4 card in `content/pages/setup-cards.html`,
and every PX4 mention elsewhere: `design/ctl-allocation`, `electronics/el-dronecan`, `el-redundancy`, `estimation/nav-*`,
`companion/per-*`, `mav-*`, `payload-gimbal`, `nav-vtrn`, `comp-jetson-nano`, `ros2/ros2-*`, `math/*`, `tools/ctl-*`,
`link/link-telemetry-radios`. Method and depth follow `docs/reviews/betaflight-coverage-audit.md`; the lessons of
`factcheck/stage6-betaflight-A.md` / `-B.md` were applied (no behaviour inferred from a name, defaults taken from the
source of the stated version, version drift marked). No course content was edited.

Legend: **✓** explained (meaning and usage, module id) · **~** mentioned only · **✗** absent. Priority: **A** must-know to
set up and fly a PX4 multirotor (and the plane/VTOL basics the course already touches) · **B** useful · **C** niche.

---

## 1. Method and sources

### 1.1 Firmware source (read locally, nothing built or run)

| Source | Version | How |
|---|---|---|
| `PX4/PX4-Autopilot`, tag **v1.15.4** (commit `99c4040`) | reference | `git clone --depth 1 -b v1.15.4` into `/tmp/px4-audit` |
| `PX4/PX4-Autopilot`, tag **v1.16.2** | for the 1.16 notes | shallow clone `/tmp/px4-audit-v1.16.2`; this tag also carries the user guide (`docs/en/`, 1.16 text) |
| `PX4/PX4-Autopilot`, tag **v1.17.0** | only to check the course's "since 1.17" statements | shallow clone `/tmp/px4-audit-v1.17.0` |

Version note: the remote has tags `v1.16.0 … v1.16.2` and **`v1.17.0` (stable)**. The course is pinned to 1.15 (`px4-setup-scratch`
was run on v1.15.4), which is now two releases old. `px4-control` and `px4-ros2` already quote 1.17 values.

Parameter inventory. PX4 has no single settings table; parameters are defined in `module.yaml`, `params_*.yaml` (EKF2) and
`PARAM_DEFINE_*` blocks in `*_params.c`, plus two generators: `Tools/serial/generate_config.py` (`*_CONFIG` port
parameters and `SER_<port>_BAUD`) and `Tools/module_config/generate_params.py` (per-output `PWM_MAIN_FUNCn/MINn/MAXn/DISn/FAILn`,
`_REV`, `_TIMn`, `UAVCAN_EC_*`, `UAVCAN_SV_*`). I parsed the first three myself (YAML loaded with `safe_load`, C comments
by regex — none of PX4's scripts were executed) and added the generated names by reading the generators: 1979 source-defined
names + 258 generated names for a 16 MAIN + 8 AUX board = **2237** (a real board shows fewer: only compiled modules, only its
ports and outputs). Every default quoted below for an A/B parameter was then read by hand in the file named. Where a
parameter has several definitions or an airframe/board override, the override is stated.

Two traps found by the hand check, both of the kind the Betaflight fact-check warned about:
- **Airframe-class overrides.** `ROMFS/px4fmu_common/init.d/rc.mc_defaults` sets, for every multicopter airframe,
  `IMU_GYRO_RATEMAX 800` (if still 400), `NAV_ACC_RAD 2`, `RTL_RETURN_ALT 30`, `RTL_DESCEND_ALT 10`, `GPS_UBX_DYNMODEL 6`.
  `rc.fw_defaults` sets `RTL_RETURN_ALT 100`, `MIS_TAKEOFF_ALT 25`, `SYS_HAS_NUM_ASPD 1`, `COM_DISARM_PRFLT -1` and more. The
  parameter-reference default is not what a Generic Quadcopter actually gets.
- **SITL overrides** (`init.d-posix/rcS`): `COM_RC_IN_MODE 1`, `MC_AT_EN 1`, `SDLOG_MODE 1`, `SDLOG_PROFILE 131`,
  `SYS_FAILURE_EN 1`, `COM_LOW_BAT_ACT 2`, `TRIG_INTERFACE 3`, `IMU_GYRO_FFT_EN 1`, `CBRK_SUPPLY_CHK`, `COM_CPU_MAX -1`. The course
  already warns about this (`px4-setup-scratch`), correctly.

Console commands: `PRINT_MODULE_USAGE_*` blocks in `src/systemcmds/*` and the modules (224 module/command names in 1.15.4:
141 drivers, 32 system, 26 commands, 15 controllers, 4 estimators, 3 communication, 2 autotune, 1 simulation, 2 templates).
Which commands a board has depends on `boards/<vendor>/<board>/default.px4board` (checked for `px4/fmu-v6x`, `fmu-v6c`,
`fmu-v5`, `fmu-v5x`, `holybro/kakuteh7`, `matek/h743`, `cuav/x7pro`, `px4/sitl`).

### 1.2 Documentation

| Source | Status |
|---|---|
| PX4 User Guide, 1.16 text from `docs/en/` in the v1.16.2 tag (config/actuators, safety, radio, battery, prearm_arm_disarm, autotune, gimbal_control, peripherals/*, sensor/*, getting_started/tunes and led_meanings, releases/1.15 and 1.16, modules/*) | read locally |
| docs.px4.io/v1.15 | reachable with WebFetch; one page read (config/safety — headings and failsafe parameters match the 1.16 text) |
| QGroundControl user guide | `docs.qgroundcontrol.com` WebFetch **not answered** (permission request timed out) — read instead from `raw.githubusercontent.com/mavlink/qgroundcontrol/{Stable_V5.0,master}/docs/en/qgc-user-guide/setup_view/*.md` |
| discuss.px4.io, GitHub issues/reactions, Reddit | not fetched (GitHub HTML/API blocked in this session, Discourse not tried) |

Because no forum frequency could be read, §5 uses an evidence class instead of a count: **O** — the PX4 guide has a
dedicated page or section; **Q** — the QGC guide has a dedicated section; **S** — a source-level behaviour or trap found in
this audit that the docs do not state (or state wrongly). This is an ordering by documentation weight, not a measurement.

### 1.3 Documentation is behind the source in places

- `advanced_config/prearm_arm_disarm.md` (1.16 text) calls `COM_PREARM_MODE = 1` (Safety Switch) and `CBRK_IO_SAFETY = 0` "the
  default". In the 1.15.4 source `COM_PREARM_MODE` defaults to **0** (`commander_params.c:756`) and `CBRK_IO_SAFETY` to
  **22027** (circuit breaker engaged = safety switch not required). A board may override it in `rc.board_defaults`.
- QGC Stable 5.0 docs list the PX4 setup pages as Summary / Firmware / Airframe / Radio / Sensors / Flight Modes / Power /
  Motors / Safety / Tuning / Camera / Parameters (+ Joystick). The QGC `master` docs already describe a reorganised set
  (Actuators/Motors, Airframe, Battery, Collision, ESC, Failsafes, Flight Modes, PID Tuning, Ports, Radio, Return & Land,
  Sensors) for a release that is not stable yet. With PX4 ≥ 1.13 QGC 4.x/5.0 show **Actuators** in place of Motors.

### 1.4 What changes from 1.15 to 1.16 (and 1.17), as far as this audit is concerned

From a parameter diff of the three trees and `docs/en/releases/1.16.md`:
- **Removed in 1.16 (35 names):** `BATn_V_LOAD_DROP` (thrust-based load compensation removed; `BATn_R_INTERNAL` default becomes
  **−1** = estimated online), legacy `BAT_N_CELLS`/`BAT_V_*`, `COM_ARM_EKF_HGT/POS/VEL/YAW`, `COM_POS_FS_DELAY` (position-loss
  failsafe now fixed at 1 s), `COM_OBS_AVOID`, `MIS_PD_TO` (→ `MIS_COMMAND_TOUT`), `MOT_SLEW_MAX`, `PD_GRIPPER_EN`, the deprecated
  per-mode switches `RC_MAP_ACRO_SW`, `RC_MAP_MAN_SW`, `RC_MAP_POSCTL_SW`, `RC_MAP_RATT_SW`, `RC_MAP_STAB_SW`, `EKF2_TERR_MASK`, the old
  rover `RDD_*`.
- **Added in 1.16 that this course needs:** `DSHOT_BIDIR_EN` (**bidirectional DShot exists only from 1.16**; 1.15 has only
  serial ESC telemetry `DSHOT_TEL_CFG`), `COM_POS_LOW_ACT`, `COM_DLL_EXCEPT`, `COM_MODE_ARM_CHK`, `MAV_n_HL_FREQ`, `MPC_VEL_LP`,
  `MPC_VEL_NF_FRQ/BW`, `MC_YAW_TQ_CUTOFF`, `NAV_MIN_GND_DIST`, `OSD_RC_STICK`, `RC_GHST_TEL_EN`, `SENS_FLOW_SCALE`, `UXRCE_DDS_RX_TO`/`TX_TO`,
  `BATn_I_OVERWRITE`, `CA_MAX_SVO_THROW`.
- **Default changes 1.15 → 1.16:** `EKF2_OF_CTRL` 0 → **1** (optical flow on by default), `EKF2_GPS_CHECK` 245 → 1023,
  `EKF2_EV_CTRL` 15 → 0, `EKF2_AGP_CTRL` 1 → 0, `COM_ARM_BAT_MIN` 0 → −1, `MIS_DIST_1WP` 900 → 10000, `BATn_R_INTERNAL` 0.005 → −1.
- **msp_osd rewritten:** 1.15 sends DJI legacy MSP OSD elements (`MSP_NAME`, `MSP_STATUS`, `MSP_BATTERY_STATE`, … at a fixed
  115200 Bd); 1.16 sends **MSP DisplayPort** (`MSP_CMD_DISPLAYPORT` 182, heartbeat/clear/write/draw) and also VTX config
  (`MSP_GET_VTX_CONFIG`), with a new `OSD_RC_STICK` (forward sticks to the VTX menu when disarmed). Which goggles this
  works with (O3/O4, Walksnail, HDZero) is **not documented by PX4** — unverified.
- **uORB message versioning (1.16):** `msg/versioned/`; DDS topic names get `_vN` when the message version > 0 — in 1.16 only
  `VehicleStatus` (→ `/fmu/out/vehicle_status_v1`), in 1.17 also `VehicleLocalPosition`, `VehicleAttitudeSetpoint`,
  `BatteryStatus`, `HomePosition`, `AirspeedValidated`, `ArmingCheck*`, `Event`.
- **1.17 defaults the course quotes:** `MC_ROLL_P`/`MC_PITCH_P` 6.5 → **4.0**, `IMU_DGYRO_CUTOFF` 30 → **20**,
  `MPC_YAWRAUTO_MAX` 45 → 60, `COM_FLTT_LOW_ACT` 3 → 0, `MAV_PROTO_VER` 0 → 2; removed `MPC_HOLD_DZ`, `MPC_*_MAN_EXPO`,
  `MPC_YAW_EXPO`, `RCn_DZ` (→ `MAN_DEADZONE`), `COM_POSCTL_NAVL`.

---

## 2. Settings interface: console commands and QGC Vehicle Setup

### 2.1 The three ways to configure PX4

1. **QGC Vehicle Setup screens** (§2.3) — what most users use.
2. **QGC Parameters screen** — search, edit, "Save to file / Load from file" (`.params` text), "Reset all to firmware/airframe
   defaults", "Set RC to Param…" (in-flight tuning, §4), "Clear RC to Param", "Reboot".
3. **Console** — `nsh>` on the hardware (USB MAVLink shell = QGC → Analyze Tools → MAVLink Console, or the debug UART), `pxh>` in SITL.
   Plus `Tools/mavlink_shell.py` from the source tree.

Two PX4-specific rules the course should state once: **parameters are saved automatically** (`param_set()` → `ParamAutosave`,
`src/lib/parameters/autosave.cpp`: 300 ms after a change, deferred while armed on flash-backed boards) — there is no "save"
step as in Betaflight; and many changes need a **reboot** (`@reboot_required`: ports, outputs, protocol, `MC_AT_EN`, `SYS_*`).
Neither rule appears in the course. ✗

### 2.2 Console commands (1.15.4)

Source: `src/systemcmds/*` and module `print_usage()`. Board column: in `px4/fmu-v6x` default build (`default.px4board`).

| # | Command | What it does (one line) | Course | Pri |
|---|---|---|---|---|
| 1 | `param show [filter]`, `param set <n> <v>`, `param set-default`, `param reset <n>`, `param reset_all [excl]` | read/change parameters; `set-default` changes the default (airframe files) | ✓ px4-intro, px4-setup-scratch, px4-architecture | A |
| 2 | `param show-for-airframe` | only changed values, as `param set-default` lines — the PX4 "diff" | ✓ px4-setup-scratch | A |
| 3 | `param save/load/import <file>`, `param select` | BSON parameter file on SD; `import` merges, `load` overwrites | ~ px4-setup-scratch (save only) | B |
| 4 | `param status`, `param compare`, `param greater`, `param touch`, `param find/index` | storage state; script helpers used in `rc.*` | ✗ | C |
| 5 | `listener <topic> [-n N] [-i inst] [-r rate]` | print uORB messages | ✓ px4-architecture, px4-setup-scratch | A |
| 6 | `uorb top [filter]`, `uorb status` | topic rates / subscriber counts | ✓ px4-architecture (`top` form) | A |
| 7 | `top [once]` | CPU load and stack per task | ✓ px4-architecture | A |
| 8 | `work_queue status` | work-queue threads and their items | ✓ px4-architecture | B |
| 9 | `dmesg` | boot log buffer (sensor/driver detection) | ~ px4-intro (one diagnostic line) | A |
| 10 | `commander check` | run pre-flight/arming checks, print failures | ✓ px4-setup-scratch | A |
| 11 | `commander arm/disarm [-f]`, `takeoff`, `land`, `mode <manual\|acro\|offboard\|stabilized\|altctl\|posctl\|position:slow\|auto:mission\|auto:loiter\|auto:rtl\|auto:takeoff\|auto:land\|auto:precland\|ext1>`, `transition`, `lockdown on\|off` | vehicle control from the console | ~ px4-intro (`takeoff`, `land`) | A |
| 12 | `commander calibrate mag\|baro\|accel\|gyro\|level\|esc\|airspeed [quick]` | calibrations without QGC | ✗ | B |
| 13 | `commander set_ekf_origin`, `pair`, `poweroff` | EKF origin without GPS; pairing; power off | ✗ | C |
| 14 | `<module> status` (`sensors status`, `ekf2 status`, `gps status`, `rc_input status`, `crsf_rc status`, `mavlink status [streams]`, `logger status`, `uxrce_dds_client status`, `battery_status status`, `pwm_out status`, `dshot status`, `uavcan status`, `gimbal status`, `navigator status`, `control_allocator status`) | the standard first diagnostic of every module | ~ (`ekf2 status`, `rc_input status`, `crsf_rc status`, `uxrce_dds_client status`, `commander status` named; `sensors`, `gps`, `mavlink`, `logger`, `pwm_out`, `uavcan` status ✗) | A |
| 15 | `mavlink stream -d <dev> -s <MSG> -r <Hz>`, `mavlink start/stop` | change a stream rate / instance at run time | ✗ | B |
| 16 | `logger on/off` | force logging regardless of arming | ✗ | B |
| 17 | `gps reset cold\|warm\|hot` | reset the receiver | ✗ | C |
| 18 | `actuator_test set -m <1..8>\|-s <1..8>\|-f <func> -v <-1..1> [-t s]`, `iterate-motors`, `iterate-servos` | motor/servo test from the console (what QGC Actuators sliders do) | ✓ px4-setup-scratch (`set`) | A |
| 19 | `dshot reverse/normal/save -m <n>`, `3d_on/3d_off`, `beep1…5`, `esc_info -m <n>`, `telemetry <dev>` | DShot ESC commands (direction saved in the ESC) | ✓ px4-setup-scratch (`reverse`, `save`) | A |
| 20 | `failure <unit> <type> [-i inst]` (units: gyro, accel, mag, baro, gps, optical_flow, vio, distance_sensor, airspeed, battery, motor, servo, avoidance, rc_signal, mavlink_signal; types ok/off/stuck/garbage/wrong/slow/delayed/intermittent) | failure injection, needs `SYS_FAILURE_EN 1`; the CLI tool is compiled **only in the SITL build** (`CONFIG_SYSTEMCMDS_FAILURE` only in `boards/px4/sitl`) | ✓ px4-setup-scratch, ctl-allocation (SITL only — correct) | B |
| 21 | `tune_control play -t <1..19>` / `-m "<melody>"` / `stop` | play a system tune on the buzzer | ✗ | B |
| 22 | `led_control test\|on\|off\|blink\|breathe\|flash -c <colour>` | drive the RGB status LED | ✗ | C |
| 23 | `gimbal status`, `gimbal test roll\|pitch\|yaw <deg>`, `gimbal primary-control <sysid> <compid>` | gimbal manager test | ✗ | B |
| 24 | `ver all` (`hw`, `git`, `mcu`, `bdate`, `uri`) | firmware/board identity — the first line of any bug report | ✗ | A |
| 25 | `reboot [-b]` | reboot (`-b` to bootloader) | ✗ | B |
| 26 | `perf [reset]` | performance counters (driver timing, errors) | ✗ | C |
| 27 | `i2cdetect -b <bus>` | find an I²C device (rangefinder, airspeed, mag) | ✗ | B |
| 28 | `serial_passthru` | USB ↔ UART bridge (configure a GPS/receiver through the FC) — **not in the fmu-v6x default build**; availability per board unverified | ✗ | C |
| 29 | `mtd status`, `sd_bench`, `hardfault_log`, `bsondump`, `dumpfile`, `hist`, `nshterm`, `system_time`, `gpio`, `mft`, `bl_update`, `sd_stress`, `usb_connected`, `dyn`, `netman` | storage, crash logs, misc. tools | ✗ | C |
| 30 | `<module> start/stop` (e.g. `mc_rate_control stop`) | start/stop a module | ✓ px4-architecture | B |
| 31 | `uxrce_dds_client start -t serial\|udp …`, `MicroXRCEAgent` | DDS bridge | ✓ px4-ros2, px4-companion-jetson | A (for ROS 2) |

**Totals: 31 rows (≈ 60 command forms); ✓ 12, ~ 4, ✗ 15.** A-rows: 12 — ✓ 8 (`param`, `show-for-airframe`, `listener`,
`uorb top`, `top`, `commander check`, `actuator_test`, `dshot`), ~ 3 (`commander` control verbs, `dmesg`, `<module> status`),
✗ 1 (`ver all`).

### 2.3 QGC Vehicle Setup screens (QGC Stable 5.0 docs; PX4 page set)

| Screen | What it sets for PX4 (parameters) | Course | Pri |
|---|---|---|---|
| Summary | red/green overview of each page | ✗ | B |
| Firmware | flash PX4 stable/beta/custom `.px4`; board bootloader | ✓ px4-setup-scratch (hardware step 1) | A |
| Airframe | `SYS_AUTOSTART` → loads `init.d/airframes/<id>` defaults (geometry, gains); "Apply and Restart" resets parameters | ✓ px4-intro, px4-setup-scratch | A |
| Sensors | Compass, Gyroscope, Accelerometer, Level Horizon, **Airspeed**, **Set Orientations** (`SENS_BOARD_ROT`, `CAL_MAGn_ROT`), (compass power compensation is a separate procedure) | ✓ (four calibrations, `SENS_BOARD_ROT`); airspeed ✗; `CAL_MAGn_ROT` ✗ | A |
| Radio | calibrate (`RCn_MIN/TRIM/MAX/REV`, `RC_MAP_ROLL…THROTTLE`), Spektrum bind, **Copy Trims**, **AUX passthrough** (`RC_MAP_AUX1…`), **Param tuning channels** (`RC_MAP_PARAM1…3`) | ✓ calibration; trims ✗, AUX ✗, tuning channels ✗ | A |
| Flight Modes | `RC_MAP_FLTMODE` + `COM_FLTMODE1…6`, `RC_MAP_ARM_SW`, `RC_MAP_KILL_SW`, `RC_MAP_RETURN_SW`, `RC_MAP_LOITER_SW`, `RC_MAP_OFFB_SW` | ✓ fltmode, arm, kill; return/loiter/offboard switches ✗ | A |
| Power | `BAT1_N_CELLS`, `BAT1_V_CHARGED/EMPTY`, `BAT1_V_DIV` (Calculate), `BAT1_A_PER_V` (Calculate), Advanced "Voltage drop on full load" (`BAT1_V_LOAD_DROP` — gone in 1.16), ESC calibration, UAVCAN settings | ✓ px4-setup-scratch | A |
| Actuators (Motors) | geometry (`CA_*`), output functions per output (`PWM_MAIN_FUNCn`…), protocol per timer group (`PWM_MAIN_TIMn`), Disarmed/Min/Max/Failsafe per output, Reverse range (`PWM_MAIN_REV`), motor/servo test sliders, "Identify & assign motors", "Set Spin Direction" (DShot) | ✓ px4-setup-scratch, px4-control; servos/control surfaces ✗ (§6a) | A |
| Safety | the failsafe page: low battery, RC loss, data-link loss, geofence, Return settings, Land settings, kill-switch | ~ px4-intro (list); ✓ px4-setup-scratch for RC/battery only | A |
| Tuning (PID Tuning) | Autotune button, rate/attitude/velocity/position sliders and step plots | ✓ px4-control | A |
| Camera | `TRIG_*` (camera trigger), `CAM_CAP_*` | ✗ | B |
| Parameters | full list, files, reset, RC-to-param | ✓ (files); reset ~; RC-to-param ✗ | A |
| Joystick | use a gamepad (`COM_RC_IN_MODE`) | ~ px4-setup-scratch (`COM_RC_IN_MODE`), px4-intro (virtual joystick) | B |
| Analyze → MAVLink Console, Log Download, MAVLink Inspector | console, ULog download, live messages | ✓ console, log download; Inspector ✗ | A |
| Plan view: Geofence and Rally points | geofence polygons/circles, rally points used by `RTL_TYPE` | ✗ | B |

**Totals: 15 rows; ✓ 8 (several with ✗ sub-parts), ~ 3, ✗ 4.** The QGC master reorganisation (Ports, Battery, ESC, Failsafes,
Return & Land, Collision as separate pages) should be mentioned once with "names depend on the QGC version".

---

## 3. Parameters by group (1.15.4)

**Totals: 2237 names (1979 defined in source + 258 generated for a 16-MAIN/8-AUX board); 161 named somewhere in the course,
92 in the PX4 track.** About 385 are not user settings (`TC_*` thermal-compensation coefficients 236, `CAL_*` calibration
storage 149); about 600 belong to vehicles the course does not teach (rover, UUV, airship, VOXL, helicopter, Cyphal). Named ≠
explained: in the PX4 track a name usually comes with a meaning; in `nav-*`/`per-*` modules mostly yes as well.

| Group (prefix) | Total | Named anywhere | In PX4 track | Comment |
|---|---|---|---|---|
| `MPC_*` multicopter position | 61 | 13 | 10 | speeds/tilts/hover covered; landing, takeoff, jerk/acc, stick feel ✗ |
| `MC_*` multicopter rate/attitude | 50 | 14 | 13 | roll axis covered; acro rates, limits, yaw ✗ |
| `FW_*` fixed-wing | 125 | 3 | 0 | three TECS names in `ap-plane-tuning` only |
| `VT_*` VTOL | 34 | 0 | 0 | — |
| `COM_*` commander/failsafe/arming | 82 | 13 | 10 | RC loss, battery, disarm timers covered; arming checks, kill, DL loss, wind, flight time ✗ |
| `NAV_*` / `RTL_*` / `MIS_*` / `GF_*` | 13 / 11 / 8 / 5 | 2 / 1 / 1 / 2 | 2 / 1 / 1 / 1 | Return and Land configuration nearly absent |
| `EKF2_*` | 136 | 19 | 1 | taught in `nav-*` (EV, flow, AGP, GPS heading) — not in the PX4 track |
| `SENS_*` / `CAL_*` | 109 / 149 | 2 / 0 | 2 / 0 | sensor drivers (`SENS_EN_*`) and orientations ✗ |
| `IMU_*` gyro filters | 19 | 8 | 8 | covered |
| `BAT*` | 43 | 12 | 12 | covered (1.16 changes not marked) |
| `RC_MAP_*` / other `RC*` (`RCn_*`, `RC_*`) | 32 / 108 | 3 / 7 | 3 / 7 | stick mapping, AUX, param channels, thresholds ✗ |
| `MAV_*` | 37 | 7 | 4 | instance config ✓ for companion; modes, rate, forwarding partly |
| `SER_*` | 12 | 2 | 2 | — |
| `UXRCE_DDS_*` | 8 | 1 | 1 | only `UXRCE_DDS_CFG` |
| `CA_*` control allocation | 230 | 11 | 3 | rotors ✓ (`ctl-allocation`, `px4-*`); control surfaces / tilt servos ✗ |
| `PWM_*` outputs | 139 | 1 (+ families `PWM_MAIN_FUNCn`, `_TIMx`) | 1 | functions ✓; MIN/MAX/DIS/FAIL/REV per output ✗ |
| `DSHOT_*`, `MOT_*` | 5 + 2 | 3 | 1 | — |
| `UAVCAN_*` | 107 | 2 | 0 | `UAVCAN_ENABLE`, `UAVCAN_NODE_ID` in `el-dronecan` |
| `MNT_*`, `TRIG_*`, `CAM_*`, `OSD_*` | 19 / 9 / 4 / 6 | 2 / 0 / 0 / 0 | 0 | — |
| `SDLOG_*` | 10 | 2 | 2 | — |
| `ASPD_*`, `CBRK_*`, `SYS_*`, `LNDMC_*` | 18 / 6 / 22 / 5 | 0 / 0 / 2 / 0 | 0 / 0 / 2 / 0 | — |

Below: every **uncovered A/B** item, with meaning and 1.15.4 default (file in brackets; MC = value a multicopter airframe
actually gets from `rc.mc_defaults`).

### 3.1 `MPC_*` (61 / named 13)
- `MPC_XY_CRUISE` 5 m/s (auto modes speed), `MPC_VEL_MANUAL` 10 m/s (Position-mode max), `MPC_ACC_HOR` 3 m/s², `MPC_ACC_HOR_MAX` 5,
  `MPC_JERK_AUTO` 4 m/s³, `MPC_JERK_MAX` 8 — how fast missions and Position feel. **A** [`multicopter_*_params.c`]
- `MPC_TKO_SPEED` 1.5 m/s, `MPC_TKO_RAMP_T` 3 s, `MPC_TILTMAX_LND` 12°, `MPC_LAND_SPEED` 0.7 m/s, `MPC_LAND_ALT1` 10 m, `MPC_LAND_ALT2` 5 m,
  `MPC_LAND_CRWL` 0.3 m/s, `MPC_LAND_RC_HELP` 0 — takeoff/land behaviour. **A**
- `MPC_THR_MIN` 0.12, `MPC_THR_MAX` 1.0, `MPC_MANTHR_MIN` 0.08, `MPC_THR_CURVE` 0 (rescale to hover) — Stabilized throttle feel. **B**
- `MPC_MAN_Y_MAX` 150 °/s, `MPC_YAWRAUTO_MAX` 45 °/s (1.17: 60), `MPC_HOLD_DZ` 0.1 (removed 1.17), `MPC_HOLD_MAX_XY` 0.8 m/s (named in `nav-terrain`),
  `MPC_HOLD_MAX_Z` 0.6, `MPC_XY_MAN_EXPO` / `MPC_Z_MAN_EXPO` / `MPC_YAW_EXPO` 0.6 (removed 1.17) — stick feel. **B**
- `MPC_Z_VEL_P_ACC` 4, `MPC_Z_VEL_I_ACC` 2, `MPC_Z_VEL_D_ACC` 0 — vertical velocity loop (only the XY loop is given in `px4-control`). **B**
- `MPC_POS_MODE` 4 (acceleration-based; named in `per-depth-avoid`), `MPC_XY_ERR_MAX` 2, `MPC_VELD_LP` 5 Hz. **C**

### 3.2 `MC_*` (50 / named 14)
- `MC_PITCHRATE_*` and `MC_YAWRATE_P/I/D/K` (yaw P 0.2, I 0.1, K 1.0) — only roll is quoted; one table with all three axes. **A**
- `MC_ROLLRATE_MAX`/`MC_PITCHRATE_MAX` 220 °/s, `MC_YAWRATE_MAX` 200 °/s — rate limits in Stabilized/auto. **B**
- `MC_ACRO_R_MAX`/`_P_MAX`/`_Y_MAX` **100 °/s**, `MC_ACRO_EXPO` 0, `MC_ACRO_SUPEXPO` 0 (+ `_Y`) — Acro "rates" (the first thing a Betaflight
  pilot changes; 100 °/s is very slow for FPV). **A** for anyone coming from the FPV track
- `MC_RR_INT_LIM` 0.30 (and pitch/yaw), `MC_YAW_WEIGHT` 0.4, `MC_BAT_SCALE_EN` 0, `MC_MAN_TILT_TAU` 0 s. **B/C**
- `MC_AT_RISE_TIME` 0.14 s (autotune target), and **`MC_AT_EN` default 0 on hardware** — the autotune module is started only if
  `MC_AT_EN > 0` (`rc.mc_apps`), so it must be set to 1 and the board rebooted before the QGC button works. Named in `px4-control`,
  but the hardware procedure in `px4-setup-scratch` (step 15) does not say it. **A**

### 3.3 `FW_*` (125 / named 3) and `VT_*` (34 / 0)
The course has no PX4 plane or VTOL setup (`ap-plane-tuning` and `inav-setup-wing` are other firmwares). If a `px4-setup-vtol`
or plane module is added (§7), the A set is: `FW_AIRSPD_MIN` 10 / `_TRIM` 15 / `_MAX` 20 / `_STALL` 7 m/s, `FW_USE_AIRSPD` 1,
`FW_THR_TRIM` 0.6, `FW_THR_MAX` 1, `FW_R_LIM` 50°, `FW_P_LIM_MAX/MIN` ±30°, `FW_PSP_OFF` 0, `FW_RR_P` 0.05 / `FW_PR_P` 0.08 / `FW_YR_P` 0.05,
`FW_RR_FF`/`FW_PR_FF` 0.5, `FW_R_TC`/`FW_P_TC` 0.4 s, `FW_MAN_R_MAX` 45° / `_P_MAX` 30°, `FW_LAUN_DETCN_ON` 0, `FW_TKO_PITCH_MIN` 10°,
`FW_LND_ANG` 5°, `FW_LND_FLALT` 0.5 m, `FW_AT_START`/`FW_AT_MAN_AUX` (fixed-wing autotune; the only PX4 autotune with an RC switch),
`FW_FLAPS_TO_SCL`/`_LND_SCL`; VTOL: `VT_TYPE` 0, `VT_ARSP_TRANS` 10 m/s, `VT_ARSP_BLEND` 8, `VT_F_TRANS_DUR` 5 s, `VT_B_TRANS_DUR` 10 s,
`VT_TRANS_TIMEOUT` 15 s, `VT_FW_QC_P/R` 0 (quad-chute), `VT_FW_MIN_ALT` 0, `VT_FWD_THRUST_EN` 0, `VT_ELEV_MC_LOCK` 1, `VT_TILT_*`. All **B** for this
course (A only if a PX4 plane/VTOL module is written).

### 3.4 `COM_*` (82 / named 13)
- Arming checks: `COM_ARM_WO_GPS` 1 (arming without GPS allowed), `COM_ARM_MAG_STR` 2 (warning only), `COM_ARM_MAG_ANG` 60°,
  `COM_ARM_IMU_ACC` 0.7 m/s², `COM_ARM_IMU_GYR` 0.25 rad/s, `COM_ARM_SDCARD` 1 (warn), `COM_ARM_CHK_ESCS` 0, `COM_CPU_MAX` 95 %,
  `COM_ARM_BAT_MIN` 0 (1.16: −1), `COM_ARM_EKF_*` (removed 1.16), `COM_ARMABLE` 1 — the "why won't it arm" table. **A**
- Arming sequence: `COM_PREARM_MODE` **0**, `COM_FORCE_SAFETY` 0, `CBRK_IO_SAFETY` **22027** (safety switch not required), `MAN_ARM_GESTURE` 1
  (stick arming), `COM_RC_ARM_HYST` 1000 ms, `RC_ARMSWITCH_TH` 0.75, `COM_DISARM_MAN` 1, `COM_KILL_DISARM` 5 s (kill → disarm). **A**
- Failsafe: `NAV_DLL_ACT` **0 = disabled** (no GCS-loss failsafe by default; named in `px4-intro` without the default), `COM_DL_LOSS_T` 10 s,
  `COM_RCL_EXCEPT` 0 (bitmask: Mission/Hold/Offboard — RC loss ignored in those modes if set), `COM_POSCTL_NAVL` 0, `COM_POS_FS_EPH` 5 m
  (named in `nav-resilience`), `COM_POS_LOW_EPH` −1, `COM_FLTT_LOW_ACT` 3 (Return on low remaining flight time; 1.17: 0),
  `COM_FLT_TIME_MAX` −1, `COM_WIND_WARN`/`COM_WIND_MAX` −1, `COM_IMB_PROP_ACT` 0 (warning), `COM_QC_ACT` 0 (VTOL quad-chute → Return). **A/B**
- Override and modes: `COM_RC_OVERRIDE` 1 (bitmask: bit 0 = sticks override **auto** modes — on by default, except in the critical-battery
  reaction; bit 1 = override **offboard** — off by default; override switches to Position, else Altitude), `COM_RC_STICK_OV` 30 %, `COM_TAKEOFF_ACT` 0, `COM_HOME_EN` 1, `COM_MOT_TEST_EN` 1, `COM_SPOOLUP_TIME` 1 s, `COM_LKDOWN_TKO` 3 s,
  `COM_THROW_EN` 0, `COM_FLT_PROFILE` 0. **B**

### 3.5 `NAV_*`, `RTL_*`, `MIS_*`, `GF_*` (37 / named 6) — **largest A-gap after outputs**
- `RTL_RETURN_ALT` 60 m in the reference, **30 m for multicopters** (`rc.mc_defaults`; 100 m for planes), `RTL_DESCEND_ALT` 30 → **10 m (MC)**,
  `RTL_LAND_DELAY` 0 s (−1 = loiter forever), `RTL_MIN_DIST` 10 m, `RTL_CONE_ANG` 45°, `RTL_TYPE` 0 (closest safe point incl. rally points; 1
  mission landing/rally; 2 mission path; 3 closest of home/mission landing/rally), `RTL_PLD_MD` 0, `RTL_LOITER_RAD` 80 m, `RTL_TIME_FACTOR` 1.1. **A**
- `NAV_ACC_RAD` 10 m → **2 m (MC)**, `NAV_MC_ALT_RAD` 0.8 m, `NAV_LOITER_RAD` 80 m, `NAV_MIN_LTR_ALT` −1, `NAV_TRAFF_AVOID` 1, `NAV_FORCE_VT` 1. **B**
- `MIS_TAKEOFF_ALT` 2.5 m (named), `MIS_DIST_1WP` 900 m (1.16: 10000 — "mission rejected, first waypoint too far"), `MIS_TKO_LAND_REQ` 0,
  `MIS_YAW_TMT` −1 s, `MIS_YAW_ERR` 12°, `MIS_MNT_YAW_CTL` 0, `MIS_LND_ABRT_ALT` 30 m. **A/B**
- `GF_ACTION` 2 (Hold; named), `GF_MAX_HOR_DIST` 0 / `GF_MAX_VER_DIST` 0 (disabled), `GF_SOURCE` 0, `GF_PREDICT` 0, plus the geofence polygon
  drawn in QGC Plan (stored in `dataman`). **A**

### 3.6 `EKF2_*` (136 / named 19, 1 in the PX4 track)
The estimation track names GPS/EV/flow/AGP fusion well. Missing for setup:
- `EKF2_GPS_POS_X/Y/Z`, `EKF2_IMU_POS_X/Y/Z`, `EKF2_RNG_POS_*`, `EKF2_OF_POS_*` 0 m — antenna/sensor offsets. **A** for GPS on a mast
- `EKF2_REQ_NSATS` 6, `EKF2_REQ_EPH` 3 m, `EKF2_REQ_PDOP` 2.5, `EKF2_GPS_CHECK` 245 (bitmask; 1.16: 1023), `EKF2_GPS_DELAY` 110 ms —
  "EKF won't use GPS / Position unavailable". **A**
- `EKF2_MAG_TYPE` 0 (auto; 5 = none; named in a quiz only), `EKF2_MAG_CHECK` 1, `EKF2_DECL_TYPE` 3, `EKF2_MAG_DECL` 0, `EKF2_HGT_REF` 1 (GPS!) and
  `EKF2_BARO_CTRL` 1 — **height reference is GPS by default in 1.15** (named in `nav-indoor`, not in the PX4 track). **A/B**
- `EKF2_RNG_CTRL` 1 (conditional), `EKF2_RNG_A_HMAX` 5 m, `EKF2_MIN_RNG` 0.1 m, `EKF2_GND_EFF_DZ` 4 m, `EKF2_DRAG_CTRL` 0, `EKF2_MULTI_IMU` 0,
  `EKF2_MULTI_MAG` 0. **B**

### 3.7 `SENS_*` and `CAL_*` (258 / named 2)
- Orientation: `SENS_BOARD_ROT` (named), `SENS_BOARD_X_OFF`/`Y_OFF` 0° (fine level trim), `CAL_MAGn_ROT` −1 (internal) / 0…, `CAL_MAGn_PRIO`,
  `SENS_MAG_AUTOROT` 1 (named), `SENS_MAG_AUTOCAL` 1, `SENS_MAG_MODE` 1, `CAL_MAG_COMP_TYP` 0 (power compensation), `SYS_HAS_MAG`/`_GPS`/`_BARO` 1,
  `SYS_HAS_NUM_DIST` 0, `SYS_HAS_NUM_ASPD` 0 (planes: 1). **A**
- Driver enables (all default 0 = off; one per I²C sensor family): `SENS_EN_SF1XX`, `SENS_EN_LL40LS`, `SENS_EN_TRANGER`, `SENS_EN_VL53L1X`,
  `SENS_EN_TF02PRO`, `SENS_EN_MB12XX`, `SENS_EN_MS4525DO`, `SENS_EN_MS5525DS`, `SENS_EN_SDP3X`, `SENS_EN_ETSASPD`, `SENS_EN_ASP5033`,
  `SENS_EN_PMW3901`, `SENS_EN_PAA3905`, `SENS_EN_PAW3902`, `SENS_EN_PX4FLOW`, `SENS_EN_IRLOCK`, `SENS_EN_INA22x/238`, `SENS_EN_BATT`; serial ones by port
  parameter: `SENS_TFMINI_CFG`, `SENS_SF0X_CFG` (+ `SENS_EN_SF0X` model, default 1 = SF02), `SENS_EN_SF45_CFG`, `SENS_ULAND_CFG`,
  `SENS_LEDDAR1_CFG`, `SENS_CM8JL65_CFG`, `SENS_TFLOW_CFG`. The **"enable the driver, reboot, then it appears"** pattern is never taught. **A**
- `SENS_FLOW_ROT` 0, `SENS_FLOW_MINHGT` 0.08 m, `SENS_FLOW_MAXHGT` 100 m, `SENS_FLOW_MAXR` 8 rad/s, `SENS_DPRES_OFF` 0, `CAL_AIR_CMODEL` 0,
  `SENS_BARO_QNH` 1013.25, `SENS_GPS_MASK` 7 / `SENS_GPS_PRIME` 0 (dual GPS blending), `SENS_EN_THERMAL` −1, `SENS_EXT_I2C_PRB` 1. **B**

### 3.8 `IMU_*` (19 / named 8) — covered; one fix in §7.3 (`IMU_DGYRO_CUTOFF` = 30 in 1.15). Uncovered B: `IMU_GYRO_NF1_FRQ`,
`IMU_GYRO_DNF_HMC` 3, `IMU_GYRO_DNF_BW` 15 Hz, `IMU_GYRO_FFT_MIN/MAX` 30/150 Hz, `IMU_ACCEL_CUTOFF` 30 Hz, `IMU_GYRO_CAL_EN` 1.

### 3.9 `BAT*` (43 / named 12) — covered in depth (`px4-setup-scratch`). Missing: `BAT1_SOURCE` 0 (0 power module, 1 external,
2 **ESCs** — battery from ESC telemetry), `BAT2_SOURCE` −1 (second pack), `BAT1_V_CHANNEL`/`BAT1_I_CHANNEL` −1 (board default), `BAT_AVRG_CURRENT`
15 A (flight-time estimate), `BAT1_V_DIV`/`BAT1_A_PER_V` default **−1 = board default** (the course's 18.0/36.0 are example values — say so).
1.16: `BATn_V_LOAD_DROP` removed and `BATn_R_INTERNAL` = −1 (online estimate) — not marked in the course. **B**

### 3.10 `RC_MAP_*` and `RC*` (140 / named 10)
- `RC_MAP_ROLL/PITCH/YAW/THROTTLE` 0 (set by calibration), `RCn_REV` 1, `RCn_DZ` 10 µs (ch 1–8) / 0 (9–18; removed in 1.17), `RC_CHAN_CNT`. **A**
- `RC_MAP_RETURN_SW`, `RC_MAP_LOITER_SW`, `RC_MAP_OFFB_SW`, `RC_MAP_GEAR_SW`, `RC_MAP_TRANS_SW`, `RC_MAP_FLAPS`, `RC_MAP_PAY_SW`, `RC_MAP_FLTM_BTN`
  (mode buttons), `RC_*_TH` thresholds 0.75. **B**
- `RC_MAP_AUX1…6` (passthrough to outputs with function RC AUX 1–6 = 407–412, and the inputs for `MNT_MAN_*`), `RC_MAP_PARAM1…3` (§4). **A**
- `RC_MAP_FAILSAFE` / `RC_FAILS_THR` 0 µs — detect failsafe on receivers that send a "failsafe value" on a channel (old PWM/PPM receivers). **B**
- `RC_RSSI_PWM_CHAN` 0. **C**; `RC_CRSF_TEL_EN` (named), `RC_GHST_TEL_EN` (1.16). **B**

### 3.11 `MAV_*`, `SER_*`, `UXRCE_DDS_*`, `GPS_*` (70 / named 16)
- `MAV_0_CONFIG` default **TELEM1**, `MAV_1_CONFIG` and `MAV_2_CONFIG` default **0 (disabled)** (`mavlink/module.yaml`: `[TEL1, "", ""]`), `MAV_0_MODE` 0
  (Normal), `MAV_1_MODE` **2 (Onboard)**, `MAV_n_RATE` 1200 / 0 / 0 **B/s** (0 = baud/20), `MAV_0_FORWARD` 1 / others 0, `MAV_n_FLOW_CTRL` 2,
  `MAV_0_RADIO_CTL` 1 (SiK RADIO_STATUS throttling), `MAV_PROTO_VER` 0, `MAV_SYS_ID` 1, `MAV_COMP_ID` 1, `MAV_TYPE` (2 for MC). **A**
- `SER_TEL1_BAUD` 57600, `SER_TEL2_BAUD` 921600, `SER_TEL3/4_BAUD` 57600, `SER_GPS1/2/3_BAUD` 0 (auto), `SER_RC_BAUD` 0, `SER_URT6_BAUD` 57600,
  `SER_EXT2_BAUD` 57600, `SER_WIFI_BAUD` 1 (unset). **A**
- `GPS_1_CONFIG` GPS1 / `GPS_2_CONFIG` 0, `GPS_1_PROTOCOL` 1 (u-blox; 6 NMEA), `GPS_1_GNSS` 0 (receiver default constellations; bitmask), `GPS_UBX_DYNMODEL`
  7 → **6 for MC**, `GPS_SAT_INFO` 0. **A/B**
- `UXRCE_DDS_CFG` **0 (disabled)** on generic boards (SITL starts the client itself), `UXRCE_DDS_AG_IP`, `UXRCE_DDS_PRT` 8888, `UXRCE_DDS_DOM_ID` 0,
  `UXRCE_DDS_KEY` 1, `UXRCE_DDS_PTCFG` 0, `UXRCE_DDS_SYNCT` 1, `UXRCE_DDS_SYNCC` 0. **B**

### 3.12 `CA_*`, `PWM_*`, `DSHOT_*`, `UAVCAN_*` — see §6a/6c/6l. Uncovered A: per-output `PWM_MAIN_MINn/MAXn/DISn/FAILn` (module default
1000/2000/1000/−1; **assigning a Motor function sets MIN/MAX to 1100/1900**, assigning a Servo sets DIS to 1500 and an untouched 400 Hz timer to
50 Hz — `drivers/pwm_out/PWMOut.cpp`), `PWM_MAIN_REV`, `CA_SV_*` (all), `CA_R_REV`, `CA_ROTORn_CT` 6.5, `DSHOT_MIN` 0.055, `MOT_POLE_COUNT` 14,
`UAVCAN_SUB_*`, `UAVCAN_EC_FUNCn`/`UAVCAN_SV_FUNCn`, `UAVCAN_BITRATE` 1 Mbit/s.

### 3.13 `MNT_*`, `TRIG_*`, `CAM_*`, `OSD_*`, `SDLOG_*`, `CBRK_*`, `ASPD_*` — see §6. `SDLOG_MODE` 0 (armed→disarm) and `SDLOG_PROFILE` **1**
(bitmask: bit 0 default set, 1 estimator replay, 2 thermal, 3 sysid, 4 high rate, 5 debug, 6 sensor comparison, 7 vision, 8/9 raw FIFO gyro/accel,
10 MAVLink tunnel) are named; `SDLOG_MISSION` 0, `SDLOG_DIRS_MAX` 0, `SDLOG_UTC_OFFSET` 0, `SDLOG_BOOT_BAT` 0 and encryption `SDLOG_ALGORITHM` are not.
`CBRK_SUPPLY_CHK` 0, `CBRK_USB_CHK` 197848 (USB-connected arming check disabled by default; the param text recommends 0 for production), `CBRK_BUZZER` 0, `CBRK_FLIGHTTERM` 121212 (termination disabled) — only the
`CBRK_*` family is named. **B**

### 3.14 Most valuable uncovered parameters (top 25)
`RTL_RETURN_ALT`/`RTL_DESCEND_ALT` with the MC overrides, `RTL_TYPE`, `RTL_LAND_DELAY`; `NAV_ACC_RAD`; `MPC_XY_CRUISE`, `MPC_VEL_MANUAL`,
`MPC_LAND_SPEED`, `MPC_TKO_SPEED`; `MC_ACRO_*_MAX`; `NAV_DLL_ACT` (= 0); `COM_ARM_*` checks and `CBRK_IO_SAFETY`/`COM_PREARM_MODE`;
`COM_KILL_DISARM`, `MAN_ARM_GESTURE`; `GF_MAX_HOR_DIST`/`GF_MAX_VER_DIST`; `EKF2_GPS_POS_*`, `EKF2_REQ_*`, `EKF2_HGT_REF`;
`CAL_MAGn_ROT`; `SENS_EN_*` driver enables; `PWM_MAIN_MIN/MAX/DIS/FAILn`, `PWM_MAIN_REV`; `CA_SV_CS*`; `RC_MAP_AUXn`, `RC_MAP_PARAMn`;
`MAV_n_RATE` (B/s, not baud); `MC_AT_EN` on hardware; `BAT1_SOURCE`.

---

## 4. In-flight adjustment and tuning on a switch

### 4.1 What the course says now
Nothing about RC parameter tuning (`RC_MAP_PARAM*`, "Set RC to Param") — ✗. `px4-control` (practice step 3) says autotune can be
started "или тумблер на функцию autotune" — **wrong for multicopters** (§7.3). Mode slots are covered (`COM_FLTMODE1…6`).

### 4.2 How RC → parameter mapping works (1.15.4 source)
- **Three tuning channels.** `RC_MAP_PARAM1…3` (QGC Radio → "Param Tuning Channels") pick the RC channel for PARAM 1/2/3
  (`RcParameterMap.msg`: `RC_PARAM_MAP_NCHAN = 3`).
- **The binding is a MAVLink message, not a parameter.** QGC Parameters → select a parameter → Advanced Settings → **"Set RC to Param…"**
  sends `PARAM_MAP_RC` with the parameter id, PARAM channel index, `param_value0`, `scale`, `param_value_min`, `param_value_max`
  (`mavlink_parameters.cpp:239`). PX4 keeps it in the uORB topic `rc_parameter_map` (RAM). No parameter stores it, so **the
  binding is lost at reboot** (from the code; whether QGC re-sends it on reconnect is unverified). "Clear RC to Param" sends index −2.
- **Formula** (`rc_update.cpp`, `set_params_from_rc()`): `param = clamp(value0 + scale × rc, min, max)`, `rc` = the PARAM channel
  normalised to **[−1, 1]** (centre = `value0`, full deflection = `value0 ± scale`). Only float parameters are handled.
- **Rate.** Evaluated at most **once per second** (`_last_rc_to_param_map_time > 1_s`) and only when the channel value changed;
  armed or disarmed.
- **Persistence.** The result goes through `param_set()`, so **autosave stores the new value** (deferred until disarm on
  flash-backed boards — `autosave.cpp`). Opposite of Betaflight: here the tuned value survives a power cycle, the knob
  binding does not.
- No OSD feedback; the value is visible in QGC (Parameters, or the MAVLink Inspector) and in the ULog `parameter_update`.

### 4.3 Other in-flight mechanisms
- **Flight modes on a switch**: `RC_MAP_FLTMODE` + `COM_FLTMODE1…6` (✓), or one switch per mode / buttons `RC_MAP_FLTM_BTN` (✗).
  The dedicated mode switches `RC_MAP_POSCTL_SW` etc. are deprecated in 1.15 and removed in 1.16.
- **Autotune**: multicopter — only from QGC (PID Tuning → Autotune, `MAV_CMD_DO_AUTOTUNE_ENABLE`) after `MC_AT_EN = 1` + reboot; the only
  RC switch is **fixed-wing** `FW_AT_MAN_AUX` + `RC_MAP_AUXn` (`config/_autotune.md`: "only supported on fixed-wing vehicles").
- **RC AUX passthrough**: `RC_MAP_AUX1…6` → output function RC AUX 1–6 (407–412) — a knob drives a servo/relay directly (✗).
- **Payload/gimbal from RC**: `MNT_MAN_PITCH/ROLL/YAW` = AUXn, `MNT_RC_IN_MODE` 1 (rate) (✗).
- **Parameter change from the GCS in flight** (QGC, MAVSDK `param`, MAVLink `PARAM_SET`) — allowed; the guide warns against it
  except where stated (`advanced_config/parameters.md`).
- **External modes** (ROS 2 / MAVSDK mode registration, `COM_MODE0…7_HASH`, `COM_FLTMODEn` = 100…107 External Mode 1–8) — the PX4
  analogue of scripting on a switch; named nowhere. PX4 has **no Lua scripting**.

### 4.4 What a lesson needs
The two-step setup (Radio page + Parameters "Set RC to Param"), the formula with a worked example (`MC_ROLLRATE_K`, value0 1.0,
scale 0.3, min 0.6, max 1.3 → knob from 0.7 to 1.3), the 1 Hz update, autosave vs lost binding, "only floats", which parameters
are safe to touch in the air (rate `K`/`P`/`D`, `MPC_XY_VEL_P_ACC`; never `CA_*`, outputs, `SYS_*`), the multicopter-vs-fixed-wing
autotune switch difference, RC AUX passthrough. **Lab (SITL first):** `gz_x500` or SIH with a joystick axis as PARAM1 (QGC
virtual joystick has no knobs — use a pymavlink `RC_CHANNELS_OVERRIDE`/`MANUAL_CONTROL` sender with an aux axis, or a USB gamepad;
whether SITL's `COM_RC_IN_MODE 1` joystick path feeds `RC_MAP_PARAM*` is **unverified** — check first, else run the lab on the bench
with a real receiver), send `PARAM_MAP_RC` from pymavlink, sweep the knob, log `param show MC_ROLLRATE_K` once per second, reboot and
show that the value stayed and the binding did not. **Железо:** knob on `MC_ROLLRATE_K`, hover, step inputs at three knob positions,
Flight Review step response for each.

---

## 5. Popular questions (50)

Evidence: **O** = PX4 guide page/section, **Q** = QGC guide section, **S** = source behaviour/trap found here (see §1.2).

| # | Question | Evid. | Short correct answer (1.15) | Course now |
|---|---|---|---|---|
| 1 | Why won't it arm? | O Q | QGC shows "Preflight Fail: …"/arming check report; `commander check`; common: sensors not calibrated, `COM_ARM_IMU_ACC/GYR` inconsistency, `COM_ARM_MAG_ANG`/`_STR`, no RC (`COM_RC_IN_MODE`), battery low, safety switch, `COM_CPU_MAX`, SD missing (warning), mode needs position | ~ px4-intro (2 messages), px4-setup-scratch (`commander check`) — no table |
| 2 | I have to press the safety button / no safety button | O S | `CBRK_IO_SAFETY` 22027 (default in 1.15 source = not required) vs 0; `COM_PREARM_MODE` 0/1/2; docs claim other defaults (§1.3) | ✗ |
| 3 | How do I arm with a switch / disable stick arming? | O | `RC_MAP_ARM_SW`, `COM_ARM_SWISBTN`, `MAN_ARM_GESTURE` 1, `COM_RC_ARM_HYST` 1 s | ✓ px4-setup-scratch (switch); gesture ✗ |
| 4 | Kill switch vs disarm | O | `RC_MAP_KILL_SW` stops outputs immediately, disarms after `COM_KILL_DISARM` 5 s; `MAN_KILL_GEST_T` | ~ |
| 5 | ELRS/CRSF receiver: channels don't move | O | UART not RC IN (IO has no CRSF), `RC_PORT_CONFIG` or `RC_CRSF_PRT_CFG`, free the port, reboot | ✓ px4-setup-scratch |
| 6 | SBUS/PPM/DSM receiver | O | RC IN (IO) or `RC_PORT_CONFIG`; `RC_INPUT_PROTO` −1 auto | ~ |
| 7 | A stick or channel is reversed / channel order | O Q | Radio calibration writes `RC_MAP_*`, `RCn_REV`; fix on the transmitter or recalibrate | ~ px4-setup-scratch step 5 |
| 8 | Flight mode switch setup | O Q | `RC_MAP_FLTMODE` + `COM_FLTMODE1…6`, or buttons; 1.16 removed the per-mode switches | ✓ |
| 9 | Motor numbering differs from Betaflight; quad flips on take-off | O | PX4 quad X: 1 front-right CCW, 2 rear-left CCW, 3 front-left CW, 4 rear-right CW; Actuators test | ✓ |
| 10 | DShot on Pixhawk MAIN outputs doesn't work | O | MAIN outputs on IO boards are PWM-only; DShot on FMU (AUX) outputs; protocol per timer group | ✓ |
| 11 | Motor spins the wrong way (DShot) | O | Actuators "Set Spin Direction", or `dshot reverse -m n` + `dshot save -m n` | ✓ |
| 12 | ESC calibration | O Q | PWM/OneShot only; Power → Calibrate; 1000/2000 µs fixed range; DShot needs none | ✓ |
| 13 | Motor idles too fast / one motor starts late | O S | `PWM_MAIN_MINn` (1100 set when the Motor function is assigned) / `DSHOT_MIN` 0.055 | ~ (PWM yes, `DSHOT_MIN` ✗) |
| 14 | Bidirectional DShot / RPM notch filter | O S | **1.16+** `DSHOT_BIDIR_EN`; 1.15: serial telemetry `DSHOT_TEL_CFG`; then `IMU_GYRO_DNF_EN` bit 0, `MOT_POLE_COUNT` | ~ (version wrong, §7.3) |
| 15 | Battery voltage/current wrong | O Q | `BAT1_V_DIV`, `BAT1_A_PER_V` proportional calibration; Calculate buttons | ✓ |
| 16 | Battery % jumps under throttle | O | load compensation: `BAT1_R_INTERNAL` (1.16: online), `BAT1_V_LOAD_DROP` (≤ 1.15), `BAT1_CAPACITY` | ✓ (1.16 change ✗) |
| 17 | Low-battery failsafe | O | `COM_LOW_BAT_ACT` 0 warn / 2 land / 3 return+land, `BAT_*_THR`, `COM_FLTT_LOW_ACT` | ✓ (`COM_FLTT_LOW_ACT` ✗) |
| 18 | RC-loss failsafe and the 5 s Hold | O | `COM_RC_LOSS_T` 0.5 s, `COM_FAIL_ACT_T` 5 s, `NAV_RCL_ACT` 2, `COM_RCL_EXCEPT` | ✓ |
| 19 | GCS / telemetry loss failsafe | O | `NAV_DLL_ACT` **0 = off by default**, `COM_DL_LOSS_T` 10 s | ~ (named, default ✗) |
| 20 | Geofence | O | `GF_MAX_HOR_DIST`/`GF_MAX_VER_DIST` (0 = off), `GF_ACTION` 2 Hold, QGC Plan geofence | ~ |
| 21 | Return altitude and path; rally points | O | MC: `RTL_RETURN_ALT` **30**, `RTL_DESCEND_ALT` **10**, `RTL_CONE_ANG` 45, `RTL_TYPE`, `RTL_LAND_DELAY`, rally points in Plan | ~ (60 m stated — wrong for MC) |
| 22 | Mission doesn't start / "first waypoint too far" | O S | `MIS_DIST_1WP` 900 m (1.16: 10000), `MIS_TKO_LAND_REQ`, mission feasibility checks | ✗ |
| 23 | Waypoint acceptance / mission corners | O | `NAV_ACC_RAD` (MC 2 m), `MPC_XY_CRUISE`, `MPC_JERK_AUTO`, `MPC_ACC_HOR` | ✗ |
| 24 | Takeoff/landing speed | O | `MIS_TAKEOFF_ALT` 2.5, `MPC_TKO_SPEED` 1.5, `MPC_LAND_SPEED` 0.7, `MPC_LAND_ALT1/2` | ~ (takeoff alt only) |
| 25 | Compass errors / toilet-bowl | O | calibrate away from metal, `CAL_MAGn_ROT`, disable internal mag (`CAL_MAGn_PRIO` 0; 1.16 does it on calibration), power compensation `CAL_MAG_COMP_TYP`, `COM_ARM_MAG_*` | ~ (toilet bowl named) |
| 26 | "Accel/gyro inconsistent" | O | thermal drift, recalibrate, `COM_ARM_IMU_ACC/GYR`, `SENS_IMU_MODE` | ~ |
| 27 | Position mode not available / EKF rejects GPS | O | `ekf2 status`, `gps status`, `EKF2_REQ_NSATS/EPH/PDOP`, `EKF2_GPS_CHECK`, antenna offset `EKF2_GPS_POS_*` | ~ px4-intro |
| 28 | Altitude drifts / height source | O | `EKF2_HGT_REF` (1 = GPS default in 1.15), baro foam, `EKF2_GND_EFF_DZ`, rangefinder | ~ (nav-* only) |
| 29 | High vibration in Flight Review | O | accel PSD, mounting, `IMU_GYRO_CUTOFF`/notch; limits in the log-analysis guide | ✓ |
| 30 | How to tune / autotune button does nothing | O S | `MC_AT_EN 1` + reboot (default 0), Altitude/Position hover, `MC_AT_APPLY` | ~ (hardware step missing) |
| 31 | Rate gains and K form | O | `MC_*RATE_K/P/I/D/FF` | ✓ px4-control |
| 32 | Acro feels slow (FPV pilots) | O | `MC_ACRO_R/P/Y_MAX` 100 °/s, `MC_ACRO_EXPO`, `MC_ACRO_SUPEXPO` | ✗ |
| 33 | Position mode too slow / too twitchy | O | `MPC_VEL_MANUAL` 10, `MPC_ACC_HOR`, `MPC_JERK_MAX`, `MPC_XY_MAN_EXPO`, `MPC_POS_MODE` | ~ (`MPC_XY_VEL_MAX` only) |
| 34 | Hover throttle | O | `MPC_THR_HOVER` + HTE (`MPC_USE_HTE`) | ✓ |
| 35 | Back up / restore / compare parameters | O Q | QGC Save/Load `.params`; `param show-for-airframe`; airframe change resets | ✓ |
| 36 | Reset to defaults | O Q | QGC Tools → Reset; `param reset_all`; airframe re-apply | ~ |
| 37 | Parameter not in the list | O | module not in this board's build (`default.px4board`) or driver not enabled (`SENS_EN_*`) — reboot after enabling | ~ (crsf_rc only) |
| 38 | Logs: where, which profile, upload | O | `SDLOG_MODE`, `SDLOG_PROFILE` bitmask, QGC Log Download, review.px4.io | ✓ |
| 39 | Console access | O | QGC MAVLink Console; `mavlink_shell.py`; `pxh>` | ✓ |
| 40 | SiK telemetry radio | O | TELEM1, `MAV_0_CONFIG`, `SER_TEL1_BAUD` 57600, `MAV_0_RATE` 1200 B/s, `MAV_0_RADIO_CTL`, `MAV_SYS_ID` | ~ (link-telemetry-radios: `MAV_SYS_ID` only) |
| 41 | Companion: MAVLink vs uXRCE-DDS on TELEM2 | O | `MAV_1_CONFIG`/`MAV_1_MODE` Onboard or `UXRCE_DDS_CFG`, `SER_TEL2_BAUD` 921600, one per port | ✓ |
| 42 | Offboard drops out | O | stream > 2 Hz, `COM_OF_LOSS_T` 1 s, `COM_OBL_RC_ACT` | ✓ |
| 43 | DJI / Walksnail / HDZero OSD | S | `msp_osd` only in some builds (fmu-v5x, v6x, v6xrt, voxl2, SITL), `MSP_OSD_CONFIG`, `OSD_SYMBOLS`; 1.15 legacy DJI MSP, 1.16 DisplayPort | ~ |
| 44 | Gimbal | O | `MNT_MODE_IN` (−1 off), `MNT_MODE_OUT` 0 AUX/2 MAVLink v2, functions Gimbal Roll/Pitch/Yaw 420–422, `MNT_MAN_*`, `MAV_n_MODE` 10 | ~ payload-gimbal |
| 45 | Camera trigger / geotagging | O Q | `TRIG_MODE`, `TRIG_INTERFACE`, output function Camera Trigger, `CAM_CAP_FBACK`, QGC Camera page, survey in Plan | ✗ |
| 46 | Rangefinder | O | driver enable / port, `EKF2_RNG_*`, `SYS_HAS_NUM_DIST`, `MPC_ALT_MODE` | ~ nav-terrain |
| 47 | Optical flow indoor | O | sensor + rangefinder, `EKF2_OF_CTRL` (1.15 default 0), `SENS_FLOW_ROT`, offsets | ✓ nav-indoor |
| 48 | Airspeed sensor for planes | O Q | driver enable, `SYS_HAS_NUM_ASPD`, QGC Sensors → Airspeed calibration, `ASPD_*` checks | ✗ |
| 49 | Servo/control surfaces for plane/VTOL | O | Actuators: `CA_SV_CS_COUNT`, `CA_SV_CSn_TYPE`, trim, `PWM_*_REV`, 50 Hz timer | ✗ |
| 50 | RC knob to tune a parameter | O Q | §4 | ✗ |

**Totals: 50 questions — ✓ 18, ~ 23, ✗ 9** (✗: 2, 22, 23, 32, 45, 48, 49, 50, and 3's gesture sub-part counted ~). Several ✓ rows
still have a ✗ part (1.16 changes in 16, `COM_FLTT_LOW_ACT` in 17).

---

## 6. Hardware integration

Verdict scale: can a student connect and configure it from the course alone — **Yes / Partly / No**. Lab rule: SITL/QGC first, then
«Переход на реальное железо». PX4 1.15 SITL limits that matter: no UART (MAVLink and DDS over UDP), RC only from a joystick/MAVLink,
outputs go to `pwm_out_sim` (disarmed 900 µs, min 1000, max 2000 — `PWMSim.hpp`), `failure` exists only in SITL, the SITL build contains
`camera_trigger`, `camera_feedback`, `gimbal` and `msp_osd` (`boards/px4/sitl/default.px4board`).

### 6a. Servos (planes, VTOL, tilt, generic) — **No**
**Exists:** `ctl-allocation` (rotor effectiveness, `CA_METHOD`, failure mode), `px4-setup-scratch` (Motor functions 101…).
**Missing:** output functions **Servo 1–8 = 201–208** (`output_functions.yaml`); what happens when you assign one (`PWMOut.cpp`: disarmed
→ 1500 µs and the timer group → 50 Hz if it was 400 and no other function was set); per-output `PWM_MAIN_MINn`/`MAXn`/`DISn`/`FAILn`
(module defaults 1000/2000/1000/−1), `PWM_MAIN_REV` (bitmask, "only useful for servos"); the Actuators "Control Surfaces" block:
`CA_SV_CS_COUNT`, `CA_SV_CSn_TYPE` (1 left aileron, 2 right aileron, 3 elevator, 4 rudder, 5/6 elevons, 7/8 V-tail, 9/10 flaps,
11 airbrake …), `CA_SV_CSn_TRQ_R/P/Y` scaling, `CA_SV_CSn_TRIM`, `CA_SV_CSn_FLAP`/`_SPOIL`; tilt servos `CA_SV_TL_COUNT`, `CA_SV_TLn_MINA/MAXA`
(0/90°), `_TD`, `_CT`; the deflection convention (positive = trailing edge up/right — quote `config/actuators.md` "Control Surface
Deflection Convention"); servo test with `actuator_test set -s n -v x` / Actuators sliders; the same power/BEC rules as the Betaflight
audit §7a (separate BEC, common ground, never the FC 5 V rail). **Proposal:** module `px4-outputs-servos` (§7.1 #2). **Lab:** SITL
`sihsim_airplane` (10041) — read its `CA_SV_*` and `PWM_MAIN_FUNC*`, deflect each surface with `actuator_test -s`, `listener actuator_servos`
and `actuator_outputs`, then reverse one with `PWM_MAIN_REV` and show the sign change; **железо:** a servo on an FMU output, BEC, endpoints
set via MIN/MAX so the horn does not bind, trim via `CA_SV_CSn_TRIM` vs PWM centre.

### 6b. RGB LEDs and addressable strips — **No**
**Exists:** nothing.
**Facts:** PX4 drives the **status RGB LED** only: I²C drivers `rgbled` (TCA62724 on the GPS/mag module), `rgbled_ncp5623c`, `rgbled_lp5562`,
`rgbled_is31fl3195` (all probed in `rcS`), `rgbled_pwm` on some boards; brightness `SYS_RGB_MAXBRT` 1.0; test `led_control`; colour
meanings in `getting_started/led_meanings.md`. **Addressable strips (WS2812/NeoPixel) are not supported on a flight-controller output**:
the `neopixel` driver exists but is enabled only in `cuav/can-gps-v1` (1.15) and also `bluerobotics/navigator` (1.16/1.17), with the LED
count fixed by the board (`BOARD_HAS_N_S_RGB_LED`), no parameter. DroneCAN lights: `UAVCAN_LGT_ANTCL` 2, `_STROB` 1, `_NAV` 3, `_LAND` 0
(off / armed / prearmed / always). **Proposal:** one section in `px4-hardware-peripherals` (§7.1 #3) with the table of LED meanings and
"no strip support — use a DroneCAN light or an Arduino on an RC AUX passthrough". Lab: SITL has no LED; bench: `led_control test`,
`SYS_RGB_MAXBRT 0.2`, observe the arming/GPS colours.

### 6c. PWM / DShot outputs and timer groups — **Partly**
**Exists:** `px4-setup-scratch` theory ("Выход назначается функции", `PWM_MAIN_TIMx` −5…−2 DShot, −1 OneShot, 50…400 Hz), DShot only on FMU
outputs of IO boards, ESC calibration; `px4-control`.
**Missing:** the per-output MIN/MAX/DIS/FAIL and the automatic 1100/1900 on Motor assignment; `PWM_MAIN_TIMn` default **400** (PWM 400 Hz),
custom rates (any value > 0); that the timer→outputs grouping comes from the board's `timer_config.cpp` (QGC draws the groups); IO
`PWM_MAIN_*` (px4io: no DShot) vs FMU `PWM_AUX_*`, and on boards without IO the FMU outputs are `PWM_MAIN_*`; `DSHOT_MIN` 0.055, `DSHOT_3D_ENABLE`
0 + `DSHOT_3D_DEAD_H/L` 1000, `CA_R_REV`; `pwm_out status` / `dshot status`; Camera Trigger/Capture/PPS functions only on FMU pins
(`pwm_fmu` group, functions 2000/2032/2064); outputs for Landing gear 400, Parachute 401, RC passthrough 402–412, Gimbal 420–422, Gripper 430,
"Peripheral via Actuator Set 1–6" 301–306 (driven by `MAV_CMD_DO_SET_ACTUATOR`) — the PX4 equivalent of relays/PINIO. **Proposal:** in
`px4-outputs-servos`. **Lab:** SITL — assign functions to outputs 5–8, show `actuator_outputs` per function; hardware — map one timer
group to DShot600 and the other to 50 Hz servo, prove a servo on a DShot group cannot work.

### 6d. Digital video and OSD — **Partly → mostly No**
**Exists:** `px4-setup-scratch` hardware step 12: "`MSP_OSD_CONFIG` на свободный UART, если драйвер есть в сборке платы", CRSF telemetry
alternative; `link-digital-video` (Betaflight/ArduPilot side).
**Facts (source):** `msp_osd` is in the default builds of `px4/fmu-v5x`, `fmu-v6x`, `fmu-v6xrt`, `modalai/voxl2` and SITL only (1.15.4) —
**not** in `fmu-v6c`, `fmu-v5`, Kakute H7, Matek H743 → a custom build (`make <board> boardconfig` → drivers → OSD → msp_osd), as the PX4
guide's Reptile Dragon 2 page does. 1.15 driver: UART at fixed **115200**, legacy DJI MSP messages (DJI FPV goggles V1/V2 with Vista /
Air Unit "custom OSD" — that is the setup the PX4 guide documents); elements chosen by `OSD_SYMBOLS` (bitmask, default 16383 = bits 0–13:
craft name, disarmed, lat, lon, sats, speed, home dist/dir, voltage, current, mAh, RSSI, altitude, vario; 18 crosshairs, 19 avg cell, 21
power), `OSD_CH_HEIGHT`, `OSD_LOG_LEVEL` 3, `OSD_SCROLL_RATE` 125 ms, `OSD_DWELL_TIME` 500 ms. 1.16 driver switches to MSP DisplayPort and
adds VTX config and `OSD_RC_STICK`. Analogue: `atxxxx` (on-board AT7456 on some boards) with `OSD_ATXXXX_CFG` 0/1 NTSC/2 PAL. **HDZero,
Walksnail, DJI O3/O4: no PX4 documentation; compatibility unverified** — the course must say so rather than imply it works. RC through the
DJI goggles (SBUS) → RC IN with SBUS; link telemetry otherwise. **Proposal:** a section in `px4-hardware-peripherals` with a version table
(1.15 legacy vs 1.16 DisplayPort), build instructions, wiring (TX/RX crossed, GND, air-unit power from the battery per vendor spec),
and an honest compatibility note. **Lab:** SITL has `msp_osd` but no UART; feasible check: build `px4_fmu-v6c_default` with msp_osd via
`boardconfig` (build only), confirm `MSP_OSD_CONFIG` in the parameter metadata; hardware: DJI Vista/Air Unit or the student's system,
OSD elements toggled with `OSD_SYMBOLS`, screenshot per bit set.

### 6e. Camera gimbal — **Partly**
**Exists:** `payload-gimbal` ("PX4: `MNT_*`": `MNT_MODE_IN`, `MNT_MODE_OUT`, Actuators for servos, "details change between versions").
**Missing:** `MNT_MODE_IN` default **−1 (disabled; the `gimbal` module is not even started — `rcS`: `if param greater -s MNT_MODE_IN -1`)**,
values 0 auto (RC + MAVLink v2) / 1 RC / 4 MAVLink v2 (2/3 deprecated v1); `MNT_MODE_OUT` 0 AUX (PWM via functions Gimbal Roll/Pitch/Yaw
420–422) / 1 v1 / 2 v2; RC control `MNT_MAN_PITCH/ROLL/YAW` = AUX1…6 **plus** `RC_MAP_AUXn`, `MNT_RC_IN_MODE` 1 (rate) / 0 (angle),
`MNT_RATE_PITCH/YAW` 30 °/s, `MNT_RANGE_PITCH/ROLL` 90°, `_YAW` 360°, `MNT_OFF_*`, `MNT_DO_STAB` 0, `MNT_LND_P_MIN/MAX` ±90°; MAVLink gimbal:
`MAV_n_CONFIG` port, `MAV_n_MODE` **10 (Gimbal)**, `MAV_n_FORWARD`, `MNT_MAV_SYSID` 1 / `MNT_MAV_COMPID` 154; missions `MIS_MNT_YAW_CTL` 0 and
the ROI behaviour; test `gimbal test pitch -45`, `gimbal status`. **Lab:** SITL — `MNT_MODE_IN 0`, `MNT_MODE_OUT 0`, `PWM_MAIN_FUNC5…7 =
420…422`, reboot, `gimbal test pitch -45`, `listener actuator_outputs` (1.16+: `make px4_sitl gz_x500_gimbal` for a visual model —
`x500_gimbal` is new in 1.16); hardware: servo gimbal on AUX, then a MAVLink gimbal (e.g. SIYI/Gremsy) on TELEM2 with `MAV_1_MODE 10`.

### 6f. GPS and compass — **Partly**
**Exists:** `GPS_1_CONFIG`, `SER_GPS1_BAUD` 0, compass calibration, `SENS_MAG_AUTOROT`, `ekf2 status` (`px4-intro`, `px4-setup-scratch`);
dual-antenna heading in `nav-rtk`.
**Missing:** GPS2 (`GPS_2_CONFIG`, blending `SENS_GPS_MASK` 7 / `SENS_GPS_PRIME`), `GPS_1_PROTOCOL` 1, `GPS_1_GNSS` (constellations bitmask),
`GPS_UBX_DYNMODEL` (MC 6), `EKF2_GPS_POS_X/Y/Z`, `EKF2_REQ_*`, `gps status`, `gps reset`, `CAL_MAGn_ROT` / `_PRIO` (disable the internal
mag), `CAL_MAG_COMP_TYP` + the compass power-compensation procedure (`advanced_config/compass_power_compensation.md`), `COM_ARM_MAG_ANG`/
`_STR`, DroneCAN GPS/mag (`UAVCAN_SUB_GPS`/`_MAG` default 1). **Proposal:** section in `px4-hardware-peripherals`; lab: SITL `failure gps off`
→ Position-loss behaviour (`COM_POSCTL_NAVL`), hardware: time to 3D fix with `GPS_1_GNSS` variants, offset measurement.

### 6g. Rangefinder — **Partly**
**Exists:** `nav-terrain` (`MPC_ALT_MODE`, `MPC_HOLD_MAX_XY`), `nav-indoor` (flow needs a rangefinder).
**Missing:** how to enable one: I²C `SENS_EN_SF1XX`/`_LL40LS` (2 = I²C, 1 = PWM)/`_TRANGER`/`_VL53L1X`/`_TF02PRO`/`_MB12XX`/`_MPDT`,
serial `SENS_TFMINI_CFG`, `SENS_SF0X_CFG` + `SENS_EN_SF0X`, `SENS_ULAND_CFG`, `SENS_LEDDAR1_CFG`, `SENS_EN_SF45_CFG` (1.16: no longer auto-starts
on TELEM2); DroneCAN `UAVCAN_SUB_RNG` + `UAVCAN_RNG_MIN/MAX` (0.3/200 m; 1.16: 0/999); orientation from the driver (`-R` option, downward default —
check per driver); EKF use `EKF2_RNG_CTRL` 1 conditional / 2 always, `EKF2_RNG_A_HMAX` 5 m, `EKF2_RNG_A_VMAX` 1 m/s, `EKF2_MIN_RNG` 0.1 m,
`EKF2_RNG_POS_*`, `EKF2_HGT_REF` 2; `SYS_HAS_NUM_DIST`; verify `listener distance_sensor`, `i2cdetect`. **Lab:** SITL `gz_x500` 1.16+ has
`x500_lidar_down`; in 1.15 use SIH distance sensor if present (unverified) or `failure distance_sensor off` on gz; hardware: TFmini on
TELEM2, `listener distance_sensor` at three heights.

### 6h. Airspeed sensor — **No**
**Missing:** drivers `SENS_EN_MS4525DO`, `_MS5525DS`, `_SDP3X`, `_ETSASPD`, `_ASP5033`, `_MS4515` (I²C; reboot), DroneCAN `UAVCAN_SUB_ASPD`;
`SYS_HAS_NUM_ASPD` (0, planes 1 from `rc.fw_defaults`); QGC Sensors → Airspeed calibration (blow into the pitot when told);
`SENS_DPRES_OFF`, `CAL_AIR_CMODEL` 0 / `CAL_AIR_TUBELEN` 0.2 m / `CAL_AIR_TUBED_MM` 1.5 (SDP3x); validator `ASPD_PRIMARY` 1, `ASPD_DO_CHECKS` 7,
`ASPD_FS_INNOV` 5 m/s, `ASPD_FS_T_START/STOP`, `ASPD_SCALE_n`, `ASPD_SCALE_APPLY` 2, `ASPD_FALLBACK_GW` 0; `FW_USE_AIRSPD` 1;
pitot placement and tubing. **Lab:** SITL `sihsim_airplane` / gz plane `failure airspeed off` → airspeed-invalid handling; hardware: calibration
and a ground-run comparison with GPS speed in still air.

### 6i. Optical flow — **Yes (as estimation), Partly (as wiring)**
`nav-indoor` covers EKF2 flow fusion. Missing wiring/driver: `SENS_EN_PMW3901`/`_PAA3905`/`_PAW3902`/`_PX4FLOW`, MAVLink flow (`OPTICAL_FLOW_RAD`),
`SENS_TFLOW_CFG`, DroneCAN `UAVCAN_SUB_FLOW`, `SENS_FLOW_ROT`, `SENS_FLOW_MINHGT/MAXHGT`, `EKF2_OF_POS_*`, 1.16 `SENS_FLOW_SCALE` and
`EKF2_OF_CTRL` default 1. Add a short table to `nav-indoor`.

### 6j. Telemetry radios — **Partly**
`link-telemetry-radios` is firmware-neutral (SiK, `NETID`, `MAV_SYS_ID`). Missing PX4 specifics: TELEM1 = `MAV_0_CONFIG` by default,
`SER_TEL1_BAUD` 57600, `MAV_0_MODE` 0 Normal, **`MAV_n_RATE` is a byte-rate limit (B/s), not the baud** (1200 for instance 0; 0 = baud/20),
`MAV_0_RADIO_CTL` 1 (stream throttling from `RADIO_STATUS`), `MAV_0_FLOW_CTRL` 2, `MAV_PROTO_VER`, `mavlink status` and `mavlink stream`, High-latency
links (`MAV_n_MODE`, `COM_HLDL_*`), WiFi/Ethernet (`MAV_n_UDP_PRT`/`_REMOTE_PRT`/`_BROADCAST`). Add to `px4-hardware-peripherals`.

### 6k. ESC telemetry — **Partly (with a version error)**
**Exists:** `px4-control` mentions `DSHOT_TEL_CFG` and "bidirectional DShot".
**Facts:** 1.15: telemetry only over a **UART** from the ESC telemetry pads (`DSHOT_TEL_CFG` port; KISS-style serial telemetry, one wire from all
ESCs), `MOT_POLE_COUNT` 14, `dshot esc_info -m n`, topic `esc_status`. **Bidirectional DShot exists only from 1.16** (`DSHOT_BIDIR_EN`, ARK-sponsored, PR
#23863; board/timer support per the guide). Uses: dynamic notch `IMU_GYRO_DNF_EN` bit 0 + `IMU_GYRO_DNF_HMC` 3 / `_BW` 15 / `_MIN` 25 Hz, battery
from ESCs `BAT1_SOURCE` 2, arming check `COM_ARM_CHK_ESCS` 0, failure detector `FD_ESCS_EN` 1 and motor-failure detection `FD_ACT_EN` 1 /
`FD_ACT_MOT_THR` 0.2 / `FD_ACT_MOT_C2T` 2 A/% / `FD_ACT_MOT_TOUT` 100 ms (named in `ctl-allocation`), `COM_ACT_FAIL_ACT`. **Lab:** hardware only
(SITL has no ESC telemetry); `listener esc_status` with props off at three throttles, RPM vs `MOT_POLE_COUNT`, then the RPM notch on and the gyro
spectrum before/after in Flight Review.

### 6l. DroneCAN / UAVCAN — **Partly**
**Exists:** `el-dronecan` "Настройка PX4": `UAVCAN_ENABLE` 2/3, `UAVCAN_SUB_*`, CAN ESC mapping in Actuators.
**Missing:** `UAVCAN_ENABLE` default **0** and value 1 (manual sensor config), `UAVCAN_NODE_ID` 1, `UAVCAN_BITRATE` 1 000 000; which `UAVCAN_SUB_*` are on by
default (`_GPS`, `_GPS_R`, `_MAG` = 1; `_BARO`, `_BAT`, `_ASPD`, `_RNG`, `_FLOW`, `_IMU`, `_BTN`, `_DPRES`, `_HYGRO`, `_ICE` = 0); `UAVCAN_EC_FUNCn`
(ESC 1–8) with MIN 1 / MAX 8191, `UAVCAN_SV_FUNCn` (servos 1–8, 0…1000, disarmed 500); `UAVCAN_PUB_RTCM`/`_MBD` (RTK to CAN GPS),
`UAVCAN_PUB_ARM`, `UAVCAN_LGT_*`; node parameters via QGC (Power → "Show UAVCAN Settings"), firmware update of nodes from the SD card (guide
`dronecan/index.md` — procedure not re-verified here); `uavcan status`; Cyphal is a separate driver (`CYPHAL_ENABLE`), not to be mixed.
Add a PX4 practice block to `el-dronecan`.

### 6m. Relays, gripper, parachute, landing gear (the PX4 "PINIO") — **No**
No relay parameters as in ArduPilot. Outputs get functions: "Peripheral via Actuator Set 1–6" (301–306, set by `MAV_CMD_DO_SET_ACTUATOR` from a
mission or companion), RC AUX 1–6 (407–412, RC passthrough), Landing Gear 400 (+ `RC_MAP_GEAR_SW`), Parachute 401 (`COM_PARACHUTE`), Gripper 430
(1.15: `payload_deliverer` starts only with `PD_GRIPPER_EN 1`; 1.16 removes the parameter and starts the module unconditionally — `rcS`;
gripper type `PD_GRIPPER_TYPE`), Landing Gear Wheel 440. Payload power switch: `RC_MAP_PAY_SW`. Add a table to
`px4-outputs-servos`; lab: SITL, map output 8 to Peripheral 1, send `MAV_CMD_DO_SET_ACTUATOR` with pymavlink, read `actuator_outputs`.

### 6n. Buzzer and tunes — **No**
`tone_alarm` on the buzzer pin (usually in the GPS/safety-switch module); system tunes 1–19 (`lib/tunes/tune_definition.desc`: 1 STARTUP,
2 ERROR, 3/4/5 NOTIFY positive/neutral/negative, 6 ARMING_WARNING, 7/8 BATTERY_WARNING slow/fast, 9 GPS_WARNING, 10 ARMING_FAILURE,
11 PARACHUTE_RELEASE, 12 SINGLE_BEEP, 13 HOME_SET, 14 SD_INIT, 15 SD_ERROR, 16–18 PROG_PX4IO…, 19 POWER_OFF); meanings in
`getting_started/tunes.md`; `tune_control play -t n`; `CBRK_BUZZER` (782090 = silence); DShot ESC beeps `dshot beep1…5`; DroneCAN beep. A
"lost model" beeper on RC loss as in Betaflight was not found in the source — **unverified**, state it as "not provided" only after a check
of `tune_control` users. Section in `px4-hardware-peripherals` with the tune table (students ask "what does this beep mean").

### 6o. Camera trigger and capture — **No**
**Missing:** `TRIG_MODE` 0 (1 time on command, 2 time always, 3 distance always, 4 distance on command — QGC survey uses 4),
`TRIG_INTERFACE` 4 (1 GPIO, 2 Seagull MAP2 over PWM, 3 MAVLink, 4 generic PWM; SITL default 3), `TRIG_INTERVAL` 40 ms, `TRIG_DISTANCE`
25 m, `TRIG_ACT_TIME` 40 ms, `TRIG_POLARITY` 0, `TRIG_PWM_SHOOT` 1900 / `TRIG_PWM_NEUTRAL` 1500, `TRIG_MIN_INTERVA` 1 ms; output function
Camera Trigger (2000…, FMU pins only; note "needs TRIG_MODE ≠ 0"); hot-shoe feedback `CAM_CAP_FBACK` 1 + function Camera Capture (2032…),
`CAM_CAP_MODE`, `CAM_CAP_EDGE`; logging `SDLOG_MISSION` 2 (geotagging), topics `camera_trigger`/`camera_capture`; QGC Camera page; MAVLink
cameras (`camera_architecture.md`). `per-mapping` names only ArduPilot `CAM_*`. **Lab:** SITL — `TRIG_MODE 4`, survey in QGC Plan, run it,
count `camera_trigger` events in the ULog vs the planned images, geotag CSV with pyulog; hardware: PWM trigger on an FMU output to a camera
with an IR/servo trigger or a GoPro-style relay, hot-shoe feedback.

### 6p. Battery and power module — **Yes** (`px4-setup-scratch`, best-covered topic). Add `BAT1_SOURCE`, second battery, smart batteries
(`SENS_EN_BATT`, `BAT1_SMBUS_MODEL`), INA2xx digital power modules (`SENS_EN_INA226/228/238`), and the 1.16 changes.

### 6q. Summary
Yes: battery, optical flow (estimation side). Partly: PWM/DShot, GPS/compass, gimbal, rangefinder, telemetry radio, ESC telemetry, DroneCAN,
digital video/OSD. No: servos/control surfaces, LEDs, relays/gripper, buzzer, camera trigger, airspeed.

---

## 7. Proposed changes

### 7.1 New modules (ordered by value)

All follow `content/article-template.md` (summary, theory, practice ≥ 150 words with lab and acceptance line, diagnostics,
checklist, references ≥ 2, quiz bank 8, glossary term, diagram), are registered in `data/curriculum.json`, `data/content-manifest.json`,
`data/glossary.json`, and state the firmware line `PX4 1.15 (проверено на v1.15.4), отличия 1.16/1.17`.

| # | id | Title (ru) | Pri | Scope | Lab |
|---|---|---|---|---|---|
| 1 | `px4-safety-return` | «PX4: арм, failsafe, Return и геозона — полная матрица» | A | §2.3 Safety page in full; arming checks table (`COM_ARM_*`, `CBRK_*`, safety switch, `COM_PREARM_MODE`, `MAN_ARM_GESTURE`, kill); failsafe matrix (RC, data link `NAV_DLL_ACT` = 0, battery, flight time, position loss, offboard, geofence, wind, imbalanced prop, quad-chute), `COM_FAIL_ACT_T`, `COM_RCL_EXCEPT`; Return (`RTL_*` incl. MC overrides, `RTL_TYPE`, rally points, cone), Land (`MPC_LAND_*`), missions (`MIS_*`, `NAV_ACC_RAD`, feasibility); 1.16 changes | **SITL (SIH/gz):** script sets each failsafe, triggers it (`failure gps off`, stop `MANUAL_CONTROL`, kill GCS heartbeat, `failure battery off`, geofence by flying out), logs `failsafe_flags` and `nav_state` timeline; RTL with three `RTL_TYPE`s and a rally point; table of measured times vs parameters. **Железо:** bench arming-check table, field RC-loss and geofence tests |
| 2 | `px4-outputs-servos` | «Выходы PX4: функции, таймеры, сервы, поверхности, реле» | A | §6a, 6c, 6m: function list, timer groups, MIN/MAX/DIS/FAIL/REV, auto 1100/1900 and 1500/50 Hz, DShot vs PWM per group, IO vs FMU, `CA_SV_*` control surfaces and tilt servos, deflection convention, RC AUX/Peripheral/gripper/landing gear/parachute | **SITL:** `sihsim_airplane` and quad; assign functions, `actuator_test -s`, `listener actuator_servos`/`actuator_outputs`, reverse and trim; `MAV_CMD_DO_SET_ACTUATOR` to Peripheral 1. **Железо:** servo on FMU output with BEC, endpoints, one DShot group + one 50 Hz group |
| 3 | `px4-hardware-peripherals` | «Периферия PX4: GPS/компас, дальномер, airspeed, телеметрия, DroneCAN, OSD, LED и пищалка» | A | §6b, 6d, 6f–6l, 6n: the "port parameter or `SENS_EN_*` → reboot → `listener`/`status`" pattern, every driver family with its parameter, MAVLink instances (`MAV_n_*`, B/s rate), DroneCAN subscriptions and CAN ESC/servo outputs, msp_osd per version and build, LED meanings, tunes table, ESC telemetry and 1.16 bidir | **SITL:** sensors via `failure` (gps, mag, distance_sensor, airspeed) and `listener`; MAVLink instance 2 on UDP with `MAV_2_MODE` and `mavlink stream`. **Железо:** GPS2 blending, TFmini on TELEM2, airspeed calibration, SiK radio with `MAV_0_RATE` vs baud, msp_osd on a custom build |
| 4 | `px4-console-params` | «Консоль и параметры PX4: nsh/pxh, param, listener, status, бэкап» | B | §2.2 full command table, autosave and reboot rules, `param show-for-airframe` vs `.params` vs BSON, `param import`, board build (`default.px4board`, `boardconfig`), "parameter missing", `ver all`, `dmesg`, `mavlink status`, `logger on`, `perf`, `i2cdetect` | **SITL:** scripted session (pymavlink `SERIAL_CONTROL` or `mavlink_shell.py`) running 20 commands, outputs pasted; param round-trip (change → reboot → value kept; `param reset`); **Железо:** same on the FC, `dmesg` of a missing sensor |
| 5 | `px4-rc-tuning` | «PX4: подстройка в полёте — RC_MAP_PARAM, режимы на тумблерах, AUX» | B | §4 in full | §4.4 |
| 6 | `px4-camera-gimbal` | «PX4: подвес, триггер камеры и геотеги» | B | §6e and §6o (gimbal manager v2, AUX/MAVLink outputs, RC control, missions/ROI; `TRIG_*`, `CAM_CAP_*`, survey, geotagging) — or as additions to `payload-gimbal` and `per-mapping` | **SITL:** gimbal test + survey with trigger count from ULog. **Железо:** servo gimbal, then MAVLink gimbal; camera trigger with hot-shoe |
| 7 | `px4-setup-vtol` | «PX4 с нуля: самолёт и VTOL» (planned in COURSE-PLAN-STAGE6 §2.8) | B | `FW_*`/`VT_*` A-set (§3.3), airspeed (§6h), control surfaces (from #2), launch/landing, fixed-wing autotune with `FW_AT_MAN_AUX`, quad-chute | **SITL:** `sihsim_airplane`, `sihsim_xvert` (1.15) and SIH standard VTOL (1.16+); transitions logged. **Железо:** surface direction table, CG, first flight |

### 7.2 Additions to existing modules (ordered by value)

1. **`px4-setup-scratch`** — theory "Три вещи": fix the `MAV_0_RATE` sentence (§7.3 #1); add "parameters autosave; ports/outputs need a
   reboot"; add the MC airframe overrides (`rc.mc_defaults`). Hardware step 11: `RTL_RETURN_ALT` default 30 m for MC; add `NAV_DLL_ACT`
   (= 0 by default — decide), `GF_MAX_HOR_DIST`. Step 15: "`MC_AT_EN = 1`, reboot" before autotune. Step 6/7: per-output MIN/MAX/DIS,
   and that assigning Motor sets 1100/1900. Step 10: `BAT1_V_DIV`/`BAT1_A_PER_V` default −1 = board default; mark `BAT1_V_LOAD_DROP` removed in 1.16.
   Step 12: list which boards ship `msp_osd`, 1.15 vs 1.16 protocol. A "1.16 / 1.17" box: removed `RC_MAP_*_SW`, `COM_POS_FS_DELAY`,
   `BATn_V_LOAD_DROP`; bidir DShot; `EKF2_OF_CTRL` = 1; topic `_v1` suffixes.
2. **`px4-intro`** — fix the defaults (§7.3 #2, #3); "Safety" bullet: add `NAV_DLL_ACT` = 0, kill switch; the QGC screen list → full table of
   §2.3 (incl. Camera, Summary, Joystick, Parameters tools, Plan geofence/rally). Update `firmware: PX4 1.14+` and mention that 1.17 is
   current.
3. **`px4-control`** — fix the autotune-switch sentence (§7.3 #4) and the bidir-DShot version (§7.3 #5); add the all-axes default table
   (`MC_PITCHRATE_*`, `MC_YAWRATE_*`), `MC_ACRO_*` rates and expo for FPV pilots, `MPC_VEL_MANUAL`, `MPC_ACC_HOR`, `MPC_JERK_*`, the vertical
   loop gains; a paragraph on RC param tuning linking to #5 above.
4. **`px4-architecture`** — the console table (A rows), `ver all`, `dmesg`, `<module> status`; correct the 400 Hz sentence for MC (§7.3 #3).
5. **`payload-gimbal`** — PX4 block: `MNT_MODE_IN` −1 default and the module start condition, values, `MNT_MAN_*` + `RC_MAP_AUXn`, outputs
   420–422, `MAV_n_MODE` 10, `gimbal test`.
6. **`el-dronecan`** — PX4 practice: `UAVCAN_ENABLE` 0 default, value 1, subscription defaults, `UAVCAN_EC_FUNCn`/`UAVCAN_SV_FUNCn`,
   `UAVCAN_BITRATE`, `uavcan status`, RTCM publish.
7. **`link-telemetry-radios`** — PX4 row: TELEM1, `SER_TEL1_BAUD` 57600, `MAV_0_RATE` (B/s), `MAV_0_RADIO_CTL`.
8. **`nav-indoor`** — flow/rangefinder driver enables and `SENS_FLOW_*`; 1.16 `EKF2_OF_CTRL` default 1 and `SENS_FLOW_SCALE`.
9. **`per-mapping`** — PX4 camera trigger parameters (if #6 is not written).
10. **`pages/setup-cards.html`** (PX4 card) — `RTL_RETURN_ALT` 30 m for MC; `MC_AT_EN 1` in step 16; MSP OSD board list.

With 7.1 #1–#4 and 7.2 #1–#4 the A console commands and every A parameter group in §3 are explained, and 48/50 questions in §5 are
answered (45 and 48 need #6/#3).

### 7.3 Factual errors and outdated statements in existing modules

| # | Module, place | Quote | Problem | Source |
|---|---|---|---|---|
| 1 | `px4-setup-scratch` theory "Три вещи…" | "После выбора порта — перезагрузка, затем появляется скорость: `SER_GPS1_BAUD` (0 = Auto), для MAVLink — `MAV_0_RATE`." | `MAV_0_RATE` is the maximum MAVLink **data rate in bytes/s** (default 1200; 0 = baud/20), not the port speed. The baud of TELEM1 is `SER_TEL1_BAUD` (57600) | `src/modules/mavlink/module.yaml` (`MAV_${i}_RATE`, unit B/s); `Tools/serial/serial_params.c.jinja` |
| 2 | `px4-intro` theory "Числа для ориентира"; `px4-control` "Умолчания и что они значат" | "D-term `IMU_DGYRO_CUTOFF` = 20 Гц" (intro, firmware 1.14+); "`IMU_DGYRO_CUTOFF` = 20 Гц" (control) | 1.14–1.16: **30 Hz**; 20 Hz only from 1.17. `px4-control` itself says so later ("умолчание 20 с 1.17, до 1.16 — 30") — internal inconsistency | `imu_gyro_parameters.c` v1.15.4 / v1.16.2 (30.0), v1.17.0 (20.0) |
| 3 | `px4-intro` "Числа для ориентира"; `px4-architecture` step 1 of the data path | "Внутренний контур на `IMU_GYRO_RATEMAX` = 400 Гц"; "публикуется … на `IMU_GYRO_RATEMAX` (400 Гц)" | Parameter default 400, but every multicopter airframe gets **800** from `rc.mc_defaults` (`if param compare IMU_GYRO_RATEMAX 400 → 800`). `math-ode-dyn` already says 800 — inconsistent across modules. `px4-control` "400 → 800 Гц (H7)" suggests a manual change that the airframe already made | `ROMFS/px4fmu_common/init.d/rc.mc_defaults` (1.15.4–1.17.0) |
| 4 | `px4-control` practice step 3 | "QGC → PID Tuning → Autotune, или тумблер на функцию autotune." | Multicopter autotune has **no RC switch**; the switch (`FW_AT_MAN_AUX` + `RC_MAP_AUXn`) is fixed-wing only. Also on hardware `MC_AT_EN` is 0 → module not started until set to 1 and rebooted | `config/_autotune.md` (v1.16.2): "only supported on fixed-wing vehicles"; `rc.mc_apps` (`if param greater -s MC_AT_EN 0`); `mc_autotune_attitude_control_params.c` (`MC_AT_EN` 0) |
| 5 | `px4-control` worked example | "eRPM по DShot (bidirectional DShot или телеметрия ESC по UART — `DSHOT_TEL_CFG`)" (module firmware: 1.14+) | Bidirectional DShot does not exist in 1.14/1.15 (no bidir code in `drivers/dshot`, no parameter); added in **1.16** (`DSHOT_BIDIR_EN`) | `drivers/dshot/module.yaml` v1.15.4 vs v1.16.2; `docs/en/releases/1.16.md` |
| 6 | `px4-setup-scratch` hardware step 11; `pages/setup-cards.html` step 14 | "`RTL_RETURN_ALT` выше препятствий (умолчание 60 м)" | The parameter default is 60, but a multicopter airframe gets **30 m** (and `RTL_DESCEND_ALT` 10 m) from `rc.mc_defaults`; planes 100 m | `rc.mc_defaults`, `rc.fw_defaults`, `navigator/rtl_params.c` |
| 7 | `px4-setup-scratch` hardware step 15 (and setup card step 16) | autotune procedure "как в шаге 7 SITL" | SITL sets `MC_AT_EN 1` (`init.d-posix/rcS`), hardware default is 0 — the hardware step silently relies on a SITL-only default | `init.d-posix/rcS:170`, `mc_autotune_attitude_control_params.c` |
| 8 | `px4-setup-scratch` theory "Питание" and step 10; quiz/task banks `px4-setup-scratch` | `BAT1_V_LOAD_DROP` in the state-of-charge formula; module labelled 1.15 | Correct for 1.15, but **removed in 1.16** (with `BATn_R_INTERNAL` → −1, online estimate). Needs a version note since the course already quotes 1.16/1.17 elsewhere | `docs/en/releases/1.16.md`; param diff |
| 9 | `px4-setup-scratch` theory "Три вещи…" | "`MAV_1_CONFIG` (TELEM2)" next to "`MAV_0_CONFIG` (по умолчанию TELEM1)" | Reads as a default; `MAV_1_CONFIG` defaults to **0 (Disabled)** on generic boards (some airframes/boards set 102). Same for `UXRCE_DDS_CFG` (0) | `mavlink/module.yaml` default `[TEL1, "", ""]`; `generate_config.py` (`default_port = 0`) |
| 10 | `px4-intro` "Safety" bullet | "потере данных (`NAV_DLL_ACT`)" listed as a configured action | Not wrong, but the default is **0 = disabled**; a student reads it as active | `commander_params.c` (`NAV_DLL_ACT` 0) |
| 11 | `px4-intro` front matter and examples | "firmware: PX4 1.14+"; references to `docs.px4.io/main` | Content is a mix of 1.14–1.17 facts with no version marks (items 2, 3, 5). `main` docs links drift; pin to `/v1.15/` like `px4-setup-scratch` | — |
| 12 | `px4-architecture` "Исполнение: work queue" | "`top` … норма < 70–80% на FMUv5" | **Unverified**; the only source figure is the arming limit `COM_CPU_MAX` = 95 % | `commander_params.c` |
| 13 | Docs, not course: `advanced_config/prearm_arm_disarm.md` | "Default: COM_PREARM_MODE=Safety … CBRK_IO_SAFETY=0" | Source 1.15.4: `COM_PREARM_MODE` 0, `CBRK_IO_SAFETY` 22027 — do not copy the docs' default into the course | `commander_params.c:756`, `circuit_breaker_params.c` |

No errors found in: `px4-setup-scratch` geometry table (matches `airframes/4001_quad_x` and `10040_sihsim_quadx`), output-function numbers
101…, `PWM_MAIN_TIMx` values (−5…−2, −1, 50…400), DShot only on FMU outputs of IO boards (px4io `pwm_timer_param` has no DShot values), IO
RC decoder without CRSF (`px4iofirmware/controls.cpp`), `rc_input` in fmu-v6x but not fmu-v6c (v6c uses IO for RC), `crsf_rc` only in
ModalAI builds, analog battery formula, SITL default overrides, failsafe chain timings (`COM_RC_LOSS_T` 0.5, `COM_FAIL_ACT_T` 5, `NAV_RCL_ACT`
2, `COM_DISARM_LAND` 2, `COM_DISARM_PRFLT` 10), `COM_LOW_BAT_ACT` values, battery thresholds, `actuator_test` and `dshot` syntax, ESC
calibration range 1000/2000 µs (`mixer_module.cpp`), motor MIN/MAX 1100/1900 on assignment (`PWMOut.cpp`); `px4-control` gain defaults (rate
0.15/0.2/0.003/K 1, `MPC_XY_P` 0.95, `MPC_XY_VEL_*_ACC` 1.8/0.4/0.2, `MPC_Z_P` 1, `IMU_GYRO_CUTOFF` 40, `IMU_GYRO_DNF_EN` bits, `MC_AT_APPLY`
0/1/2, `MC_AT_SYSID_AMP` 0.7), `MC_ROLL_P` 6.5 → 4.0 from 1.17 (correct); `px4-ros2` (`COM_OF_LOSS_T` 1 s, `COM_OBL_RC_ACT`, `_v1` from 1.17 for
`vehicle_local_position`); `px4-companion-jetson` (`MAV_1_MODE` Onboard = 2, `SER_TEL2_BAUD` 921600 default); `nav-indoor`, `nav-terrain`,
`nav-rtk` PX4 values checked (`EKF2_EV_CTRL` 15, `EKF2_OF_CTRL` 0, `EKF2_OF_DELAY` 20, `EKF2_DELAY_MAX` 200, `MPC_ALT_MODE` 2,
`MPC_HOLD_MAX_XY` 0.8, `GPS_UBX_MODE` values, `GPS_DUMP_COMM` 2); `per-tracking` `MPC_Z_VEL_MAX_UP/DN` 3/1.5.

---

## Appendix — counts

- Console: 31 command rows (≈ 60 forms) — ✓ 12, ~ 4, ✗ 15; module/command names in 1.15.4: 224.
- QGC Vehicle Setup: 15 screens/tools — ✓ 8, ~ 3, ✗ 4.
- Parameters 1.15.4: **2237** (1979 defined + 258 generated for a 16+8-output board); named in the course 161, in the PX4 track 92.
  1.16.2: 2180 defined (−35 / +236 vs 1.15.4); 1.17.0: 2184 defined.
- In-flight tuning: RC → parameter mapping (3 channels) — 0 explained; one wrong statement (MC autotune switch).
- Popular questions: **50** — ✓ 18, ~ 23, ✗ 9.
- Hardware topics: 16 — Yes 2, Partly 8, No 6.
- Factual problems: 13 (11 course errors/inconsistencies or version issues, 1 unverified claim, 1 docs error).
