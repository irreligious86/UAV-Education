---
id: px4-intro
title: "Introduction to PX4"
level: L2
readingTime: 20 min
firmware: PX4 1.18 (checked against v1.18.0)
status: published
added: 2026-11-08
tags:
  - PX4
  - QGroundControl
related:
  - ap-intro
  - px4-architecture
next:
  - px4-architecture
source: content/px4/px4-intro.md
source_hash: 14c1abf99254
---

## summary
PX4 is the other big open-source autopilot next to ArduPilot. It grew out of academia and leans toward research work: a modular architecture, strict interfaces and deep ROS 2 integration. This module shows how PX4 differs from ArduPilot in practice (ground station, flight modes, parameters, simulation, hardware requirements) and when to pick it.

## theory
### PX4 versus ArduPilot
Both are complete autopilots with navigation, missions and companion computer interfaces. They differ in character:

- **Ecosystem.** PX4 sits in the Dronecode Foundation next to the standards (Pixhawk, MAVLink, MAVSDK), with QGroundControl as its native GCS. ArduPilot is community-run, has Mission Planner and supports a huge range of hardware.
- **Architecture.** PX4 is a set of modules that talk over the uORB message bus; you can stop and restart any module at runtime. ArduPilot is more monolithic but runs Lua scripts on board.
- **ROS 2.** PX4 connects natively through uXRCE-DDS, so PX4 topics show up in ROS 2 directly. ArduPilot (4.5+) also has a native DDS client (AP_DDS), with a smaller set of topics.
- **Tuning.** PX4 has mature multicopter and fixed-wing autotuning, and its parameters are grouped by control loop (`MC_*RATE_*`, `MC_*_P`, `MPC_*`).

Rule of thumb: research, computer vision and ROS 2 point to PX4; exotic hardware, Lua on board and a large community of practitioners point to ArduPilot. Both fly.

### Ground control station
QGroundControl handles firmware, airframe selection, calibration, parameters, missions and log download (`.ulg`). It also works with ArduPilot, but for PX4 it is the main tool.

### Multicopter flight modes
- **Manual/Stabilized**: attitude is stabilized, throttle is manual.
- **Acro**: the sticks command angular rates.
- **Altitude**: holds altitude.
- **Position**: holds position using GNSS; the sticks command velocity.
- **Hold**, **Return**, **Land**, **Takeoff**, **Mission**, **Orbit**, **Follow Me**: autonomous modes.
- **Offboard**: setpoints come from a companion computer.

As everywhere, you pick a mode by which sensors you trust. Position will not engage without a reliable GNSS fix. In the source (`src/modules/commander/ModeUtil/mode_requirements.cpp`, v1.17.0 and v1.18.0) the requirements of the manual modes are nested: Acro needs angular rate, Stabilized adds attitude, Altitude adds altitude, Position adds local position, and all four need manual control input. If an estimate is lost in flight, PX4 drops one step down: from Position to Altitude, and without an altitude estimate to Stabilized (since 1.17 this is not configurable; see `COM_POSCTL_NAVL` in the upgrade table).

{{diagram:px4-mode-ladder|Each mode up the ladder needs one more estimate and holds one more quantity for the pilot; when an estimate is lost, PX4 drops one step down.}}

### Parameters and logs
Parameters are set in QGC or from the console with `param set/show`. ULog files (`.ulg`) contain every uORB topic enabled for logging; analyze them in Flight Review (web) or with `pyulog`.

### Hardware
The standard is a Pixhawk-compatible flight controller (FMUv5/v6, H7). PX4 needs more resources than Betaflight, and F4 boards running it are rare.

### Simulation
`make px4_sitl gz_x500` starts SITL with Gazebo and the x500 quadcopter model; QGC connects on its own. For ROS 2 this is the same setup as with the real vehicle.

### First setup in QGroundControl: the order that matters
1. **Firmware** (Firmware → PX4 stable) and **airframe** (Airframe → frame type; it sets `CA_AIRFRAME`, `CA_ROTOR_COUNT`, the geometry and the starting parameters). Changing the airframe resets parameters.
2. **Sensors**: compass (rotate through every axis), gyro (keep still), accelerometer (6 orientations), level horizon; board orientation in `SENS_BOARD_ROT`, external compass orientation is detected automatically.
3. **Radio**: stick calibration, `RC_MAP_*`; flight modes on switches (Flight Modes), and a kill switch, which is mandatory for tests.
4. **Motors**: Actuators, for output assignment and protocol (DShot/PWM is chosen per timer group in Actuators, `PWM_MAIN_TIMx`), testing each motor **with the props off**, and checking spin direction against the airframe diagram.
5. **Power**: `BAT1_N_CELLS`, voltage divider and current calibration against a multimeter or power meter, the `BAT_LOW_THR`/`BAT_CRIT_THR` thresholds.
6. **Safety**: actions on RC loss (`COM_RC_LOSS_T` = 0.5 s by default, `NAV_RCL_ACT`), on GCS data link loss (`NAV_DLL_ACT`, default 0, disabled, so you enable it yourself), on low battery (`COM_LOW_BAT_ACT`), the geofence (`GF_*`), the return altitude `RTL_RETURN_ALT`; kill switch `RC_MAP_KILL_SW` stops the motors immediately, in any mode and in the air (the full matrix is in `px4-safety-return`).
Preflight checks report to QGC as text ("Preflight Fail: …"); the `CBRK_*` circuit breakers disable them, and only belong on the bench.

### QGC pages: what is configured where
How to use it: start from what you need to configure, find the page in the table, and check the result in Parameters after a reboot, using the parameters in the "What it writes" column. Page names are from QGC Stable 5.0 (PX4). Newer QGC builds split the Safety and Power pages into separate ones (ports, battery, ESC, failsafe, Return and Land); names depend on the QGC version, the parameters stay the same.

| Page | What it writes (PX4 1.18) | Where in the course |
|---|---|---|
| Summary | nothing: red/green readiness tiles for the pages | — |
| Firmware | PX4 stable / beta / your own `.px4` firmware, bootloader | `px4-setup-scratch` |
| Airframe | `SYS_AUTOSTART` → airframe defaults (geometry `CA_*`, gains, `rc.mc_defaults`); Apply and Restart resets parameters except the `CAL_*` calibrations (and, before 1.18, `RC*` and `COM_FLTMODE*`; the v1.18.0 `rcS` no longer keeps them) | `px4-setup-scratch` |
| Sensors | compass, gyro, accelerometer, level horizon and airspeed calibration; orientations `SENS_BOARD_ROT`, `CAL_MAGn_ROT` | `px4-setup-scratch`, `px4-hardware-peripherals` |
| Radio | `RCn_MIN/TRIM/MAX/REV`, `RC_MAP_ROLL…THROTTLE`; Copy Trims; AUX channels `RC_MAP_AUX1…6`; tuning channels `RC_MAP_PARAM1…3` | `px4-setup-scratch`, `px4-rc-tuning` |
| Flight Modes | `RC_MAP_FLTMODE` + `COM_FLTMODE1…6`, `RC_MAP_ARM_SW`, `RC_MAP_KILL_SW`, `RC_MAP_RETURN_SW`, `RC_MAP_LOITER_SW`, `RC_MAP_OFFB_SW` | `px4-rc-tuning` |
| Power | `BAT1_N_CELLS`, `BAT1_V_CHARGED/EMPTY`, `BAT1_V_DIV`, `BAT1_A_PER_V` (Calculate buttons), ESC calibration, UAVCAN settings | `px4-setup-scratch` |
| Actuators | geometry `CA_*`, the function of each output `PWM_MAIN_FUNCn`, group protocol `PWM_MAIN_TIMn`, Disarmed/Min/Max/Failsafe per output, reversal `PWM_MAIN_REV`, test sliders, Set Spin Direction (DShot) | `px4-outputs-servos` |
| Safety | low battery, RC and data link loss, geofence, Return, Land, kill switch | `px4-safety-return` |
| PID Tuning | Start AutoTune button (needs `MC_AT_EN` = 1; the button sends `MAV_CMD_DO_AUTOTUNE_ENABLE`), rate / attitude / velocity / position sliders, response plots | `px4-control` |
| Camera | camera trigger `TRIG_*`, capture feedback `CAM_CAP_*` (the QGC user guide lists this page, but the Stable 5.0 source builds no PX4 camera page: set these in Parameters) | `px4-camera-gimbal` |
| Parameters | the full list, Save/Load `.params`, Reset all to firmware's defaults / Reset to vehicle's configuration defaults, Set RC to Param, Reboot Vehicle | `px4-console-params`, `px4-rc-tuning` |
| Joystick | a gamepad over MAVLink instead of a radio (`COM_RC_IN_MODE`) | `px4-setup-scratch` |
| Analyze Tools | MAVLink Console (`nsh>`), Log Download (ULog), MAVLink Inspector | `px4-console-params` |
| Plan → Fence, Rally | geofence polygons and circles, rally points for Return | `px4-safety-return` |

### Parameters: how they are organized
Names are grouped by module: `MC_*` (multicopter controllers), `MPC_*` (position control), `EKF2_*`, `IMU_*`, `COM_*` (commander/failsafe), `NAV_*`, `RTL_*`, `BAT*`, `CA_*` (control allocation), `SER_*`/`MAV_*`/`UXRCE_*` (ports). The full reference with ranges and defaults is the "Parameter Reference" in the documentation (generated from the source, as with ArduPilot). Export and import with QGC → Parameters → Tools (a `.params` file), and keep it under version control (the "CI" module).

### Reference numbers (defaults, multicopter)
Values are for PX4 1.18 (checked against v1.18.0; 1.17 has the same), older defaults in parentheses. The inner loop runs at `IMU_GYRO_RATEMAX` = 800 Hz: the parameter itself defaults to 400, but the multicopter airframe raises it to 800 (`rc.mc_defaults`); the maximum is 2000 Hz. Gyro filter `IMU_GYRO_CUTOFF` = 40 Hz, D-term `IMU_DGYRO_CUTOFF` = 20 Hz (30 before 1.17). That is well below Betaflight because PX4 targets larger, slower vehicles; on a 5" quad they are raised (gyro around 120, D-term 50–80, per the PX4 filter tuning guide) together with the ESC RPM notch (`IMU_GYRO_DNF_EN`, needs ESC RPM: bidirectional DShot is selected in 1.18 with values −6/−7/−8 in `PWM_AUX_TIMn` of the motor group, in 1.16–1.17 with `DSHOT_BIDIR_EN`; 1.15 only had ESC telemetry over UART, `DSHOT_TEL_CFG`). Maximum tilt `MPC_TILTMAX_AIR` = 45°, in manual modes `MPC_MAN_TILT_MAX` = 35°; maximum horizontal velocity `MPC_XY_VEL_MAX` = 12 m/s.

### ULog logs and Flight Review
Logging starts on arming (`SDLOG_MODE`) and records uORB topics at set rates (`SDLOG_PROFILE` is a bitmask of topic sets: Default set, High rate for fast maneuvers and tuning, and others). Since 1.18 rotation is on by default: a file is at most `SDLOG_MAX_SIZE` = 1024 MiB, and at log start the oldest logs are deleted until at least (100 − `SDLOG_ROTATE`) = 10 % of the card is free; your own `etc/logging/logger_topics.txt` on the SD card is added to the profile instead of replacing it. Flight Review (web) plots rate tracking (setpoint vs. actual), the vibration spectrum (acceleration power spectral density, which shows motor frequencies and resonances), estimator health ("Estimator Flags"; GPS accuracy in "GPS Uncertainty" and "GPS Noise & Jamming"), CPU and RAM load, RC inputs and the failsafe flags (an RC loss shows up there as `manual_control_signal_lost`). Innovation test ratios (the same "gates" as in the Kalman filter module) are not plotted: take them from `estimator_innovation_test_ratios` with `pyulog`. `pyulog` (`ulog2csv`) is for analysis in Python (the "Python for data" module).

### Upgrading 1.15 → 1.17: what was renamed and changed
Until November 27, 2026 the course was checked against PX4 v1.17.0; the table below covers the upgrade to it from 1.15 (v1.15.4) and 1.16 (v1.16.2), and the next step is "Upgrading 1.17 → 1.18" after it. The table comes from comparing the parameter definitions and airframe defaults of the three tags. Upgrade procedure:
- **Back up before flashing.** QGC → Parameters → Tools → Save to file (`.params`), the logs from the SD card, the version from `ver all`. Use this file as a reference, not as something to load back wholesale.
- **A QGC firmware update keeps parameters, but only values that differ from the default are stored.** Anything equal to the default, including a value you set by hand to the same number, silently takes the 1.17 default after flashing: `MC_ROLL_P`/`MC_PITCH_P` 4.0 instead of 6.5, `IMU_DGYRO_CUTOFF` 20 instead of 30. A vehicle that flew on defaults will fly differently, so check the tune again.
- **Removed parameters are not carried over.** Only a few names are translated automatically (in the 1.17 `param_translation.cpp`, the ones still relevant are `SDLOG_MODE` = −1 → `SDLOG_BACKEND` = 0 and `ASPD_FALLBACK_GW` → `ASPD_FALLBACK`). `MPC_HOLD_DZ` → `MAN_DEADZONE`, `BAT1_V_LOAD_DROP`, `COM_POSCTL_NAVL` and the other rows of the table are manual.
- **A clean start is more reliable.** Reset to defaults (QGC: Parameters → Tools → Reset all to firmware's defaults; in the console `param reset_all`, which also clears `SYS_AUTOSTART`, see `px4-console-params` for the difference), select the airframe again, redo the sensor and radio calibration, then copy your own values from the file one by one, checking each against the table.
- **Never carried over:** a `.params` file from SITL onto a real vehicle; a ROS 2 build with an old `px4_msgs` (the branch must match the firmware, and some topics got a `_v1` suffix); on fmu-v6x, receiver setup through `RC_PORT_CONFIG` (the 1.17 build has a different set of RC drivers).
- **After the upgrade:** motor test with the props off, failsafe test on the bench, a short hover with a log, as in the first setup (px4-setup-scratch).

{{diagram:px4-upgrade-param-tree|The right branch is the dangerous one: a parameter that matched the old default silently takes the new one after flashing, MC_ROLL_P 4.0 instead of 6.5.}}

| Before (1.15 / 1.16) | Now (1.17) | What changed | Since |
|---|---|---|---|
| `BAT1_V_LOAD_DROP` (and `BAT2_`, `BAT3_`) | removed | the "throttle × voltage drop" load compensation is gone; without a current sensor the cell voltage is not compensated | 1.16 |
| `BAT1_R_INTERNAL` = 0.005 Ω | `BAT1_R_INTERNAL` = −1 | −1 estimates the resistance in flight; a value ≥ 0 sets it manually | 1.16 |
| `BAT_N_CELLS`, `BAT_V_EMPTY`, `BAT_V_CHARGED`, `BAT_V_LOAD_DROP` | `BAT1_N_CELLS`, `BAT1_V_EMPTY`, `BAT1_V_CHARGED` | the old names without a battery number are removed | 1.16 |
| `COM_ARM_BAT_MIN` = 0 | `COM_ARM_BAT_MIN` = −1 | −1 uses `BAT_CRIT_THR` as the arming threshold | 1.16 |
| `COM_ARM_WO_GPS`: 0 requires GPS, 1 does not | 0 denies arming, 1 warns only, 2 disables the check | the default 1 is the same, the values mean something else: the reaction to a failed `EKF2_GPS_CHECK` | 1.16 |
| — | `COM_RAM_MAX` = 95 % | denies arming when memory usage is above the threshold; −1 disables the check (as in SITL) | 1.16 |
| ESC telemetry over UART only (`DSHOT_TEL_CFG`) | `DSHOT_BIDIR_EN` (removed in 1.18, see below) | bidirectional DShot (eRPM for the dynamic notch) arrived in 1.16; only on supported boards and FMU outputs | 1.16 |
| `DSHOT_MIN`, unit % | `DSHOT_MIN`, unit norm (0…1) | the default 0.055 is the same, only the unit label changed | 1.17 |
| `PWM_MAIN_TIMn` / `PWM_AUX_TIMn` = −2 is DShot1200 (1.15) | the value is gone: DShot is only −5 / −4 / −3 (150 / 300 / 600) | DShot1200 removed | 1.16 |
| — | `PWM_MAIN_CENTn`, `PWM_AUX_CENTn` (−1 or 800…2200 µs; on IO outputs since 1.18) | servo center in microseconds: two straight lines `MIN`–`CENT`–`MAX` (`px4-outputs-servos`) | 1.17 |
| `CA_SV_CSn_TRIM` for every servo | replaced by `CENTn` for PWM servos; with any `CENTn` ≠ −1 the firmware zeroes every nonzero `CA_SV_CSn_TRIM` | the neutral point moved from the mixer to the output | 1.17 |
| output functions up to 440 (1.15) | + 450–453 IC Engine Ignition / Throttle / Choke / Starter, + 2070 RPM Input | new functions | 1.16 |
| `PD_GRIPPER_EN` (0), `PD_GRIPPER_TO` = 3 s (1.15) | `PD_GRIPPER_EN` removed, `PD_GRIPPER_TO` = 1 s | no separate gripper enable any more: `PD_GRIPPER_TYPE` = 0 (Servo, the default) and an output with the Gripper function are enough | 1.16 |
| `msp_osd`: DJI legacy MSP elements | `msp_osd`: MSP DisplayPort, new `OSD_RC_STICK` | the driver was rewritten; PX4 does not document compatibility with specific goggles | 1.16 |
| `EKF2_EV_CTRL` = 15 | `EKF2_EV_CTRL` = 0 | external vision is off by default; you set the bits yourself | 1.16 |
| `EKF2_OF_CTRL` = 0 | `EKF2_OF_CTRL` = 1 | optical flow is on by default | 1.16 |
| `EKF2_AGP_CTRL` = 1 | `EKF2_AGP_CTRL` = 0; new `EKF2_AGP_MODE` (`EKF2_AGP0_*` in 1.18, see below) | the auxiliary global position input is off by default (1.16); reset mode added in 1.17 | 1.16 / 1.17 |
| `EKF2_GPS_CHECK` = 245 (max. 511) | `EKF2_GPS_CHECK` = 2047 | 1.16: 1023, bit 9 "Spoofing" added; 1.17: bit 10 is the fix type (`EKF2_REQ_FIX`, 3D by default) | 1.16 / 1.17 |
| `EKF2_TERR_MASK` | removed | — | 1.16 |
| `COM_ARM_EKF_HGT/POS/VEL/YAW`, `COM_POS_FS_DELAY` | removed | the EKF preflight thresholds and the position failsafe delay are no longer configurable | 1.16 |
| — | `COM_POS_LOW_ACT` (3 = Return) | action on low position accuracy in Mission/Hold; the `COM_POS_LOW_EPH` threshold existed before and defaults to −1 (disabled) | 1.16 |
| — | `COM_DLL_EXCEPT` | modes in which data link loss is ignored: bit 0 Mission, bit 1 Hold (all auto modes in 1.18), bit 2 Offboard | 1.16 |
| `COM_RCL_EXCEPT`: bits 0–2 (Mission, Hold, Offboard) | + bit 3 External Mode, bit 4 Altitude Cruise | new RC loss exceptions | 1.17 |
| `COM_POS_FS_EPH` = 50 m for planes and VTOL (`rc.fw_defaults`, `rc.vtol_defaults`) | 5 m (the parameter default) | the airframe no longer overrides the threshold: position is lost at eph > 2.5 × 5 = 12.5 m instead of 125 m | 1.17 |
| `COM_POSCTL_NAVL` (0 Altitude, 1 Land) | removed | on position loss in Position it is always Altitude, without an altitude estimate Stabilized | 1.17 |
| `COM_FLTT_LOW_ACT` = 3 (Return) | `COM_FLTT_LOW_ACT` = 0 (None) | return on remaining flight time is off by default (the parameter is removed in 1.18: time-based return is part of `COM_LOW_BAT_ACT` = 3 again) | 1.17 |
| `COM_RC_IN_MODE` 0…4 | `COM_RC_IN_MODE` 0…8 | priorities 5–8 added (RC and two MAVLink sources); "Joystick" in the labels replaced by "MAVLink"; the default 3 is the same | 1.17 |
| `COM_OBL_RC_ACT`: 2 = Manual | 2 = Stabilized | value label (1.16); in 1.17, if a switch to Position/Altitude/Stabilized is selected and there is no manual control, `NAV_RCL_ACT` is executed | 1.16 / 1.17 |
| `COM_FLTMODEn`: up to 13 | 16 Altitude Cruise added | new flight mode | 1.17 |
| `RC_MAP_ACRO_SW`, `RC_MAP_MAN_SW`, `RC_MAP_POSCTL_SW`, `RC_MAP_RATT_SW`, `RC_MAP_STAB_SW` | removed | modes only through `RC_MAP_FLTMODE` and `COM_FLTMODEn` | 1.16 |
| `MPC_HOLD_DZ` | `MAN_DEADZONE` (0.1) | stick deadzone shared by the modes | 1.17 |
| `MPC_XY_MAN_EXPO`, `MPC_Z_MAN_EXPO`, `MPC_YAW_EXPO` | removed | stick expo in Position is no longer configurable (the old default is used) | 1.17 |
| `RCn_DZ` (`RC1_DZ`…`RC18_DZ`) | removed | no per-channel deadzone any more; for the modes use `MAN_DEADZONE` | 1.17 |
| `MC_ROLL_P`, `MC_PITCH_P` = 6.5 | = 4.0 | softer attitude loop; check the response after upgrading | 1.17 |
| `IMU_DGYRO_CUTOFF` = 30 Hz | = 20 Hz | lower D-term filter | 1.17 |
| `MPC_YAWRAUTO_MAX` = 45 deg/s, `MPC_YAWRAUTO_ACC` = 60 deg/s² | 60 deg/s, 20 deg/s² | yaw in auto modes | 1.17 |
| `GPS_UBX_DYNMODEL` = 6 for multicopters (`rc.mc_defaults`) | 7 (the parameter default) | the airframe no longer overrides the u-blox dynamic model | 1.17 |
| `fw_pos_control` module | `fw_mode_manager` + `fw_lat_lon_control` | the fixed-wing position controller is split into two modules; parameter names are mostly the same (removed ones below), `top` and `work_queue status` show different names (`px4-setup-vtol`) | 1.17 |
| `FW_SPOILERS_DESC` | removed | — | 1.16 |
| — | `FW_T_F_ALT_ERR`, `FW_T_THR_LOW_HGT`, `LNDFW_ROT_MAX` | new TECS and fixed-wing landing parameters | 1.16 |
| `FW_AT_SYSID_AMP`, `RWTO_HDG`, `RWTO_NPFG_PERIOD`, `NPFG_EN_MIN_GSP`, `NPFG_GSP_MAX_TK`, `NPFG_TRACK_KEEP`, `NPFG_WIND_REG` | removed | skip these lines when moving a plane's `.params` | 1.17 |
| `FW_AT_SYSID_F1` = 20 Hz, `FW_AT_SYSID_TYPE` = 0 (Step) | 10 Hz, 1 (Linear sine sweep) | fixed-wing autotune excites the system differently by default | 1.17 |
| — | `FW_AIRSPD_FLP_SC` (1.0, 0.5…1) | minimum airspeed scale with flaps deployed | 1.17 |
| gimbal: a rate setpoint from MAVLink or RC holds until a new one arrives | reset to zero after 2 s without updates | the gimbal no longer spins forever when the link drops (`px4-camera-gimbal`) | 1.16 |
| `GIMBAL_MANAGER_INFORMATION`: fixed limits of ±90° pitch, ±180° yaw | from the device information (`MNT_MODE_OUT` = 2) or from `MNT_RANGE_*` (AUX; `MNT_MIN/MAX_PITCH` in 1.18) | the ground station sees the real gimbal limits | 1.16 |
| `MAV_PROTO_VER` = 0 | = 2 | MAVLink 2 from the first packet (value 0 is gone: 1 is version 1 with automatic switch to 2, 2 is version 2) | 1.17 |
| `MAV_n_MODE` up to 12 (1.15) | + 13 Low Bandwidth | new stream set for a narrow link | 1.16 |
| — | `GPS_CFG_WIPE` = 0 | 1 wipes the u-blox flash configuration on boot | 1.17 |
| `ASPD_PRIMARY` 0…3 | 0…4 | 4 is the thrust-based airspeed estimate; `ASPD_FALLBACK` = 2 uses it as a fallback | 1.17 |
| fmu-v6x: no `SENS_EN_AUAVX` in the build | present | the AUAV airspeed sensor driver was added to `default.px4board` | 1.17 |
| `UAVCAN_RNG_MIN` / `_MAX` = 0.3 / 200 (1.15) | 0 / 999 | defaults of the CAN rangefinder limits | 1.16 |
| — (1.15) | `UAVCAN_SUB_FUEL` = 0 | fuel level over CAN | 1.16 |
| — | `UAVCAN_ESC_IFACE` = 255 | CAN interface mask for ESC commands | 1.17 |
| fmu-v6x: port 300 not in the list | 300 "Radio Controller" = `/dev/ttyS5` | this is the PX4IO line; do not assign it on a board with an IO processor (`px4-hardware-peripherals`) | 1.17 |
| `MIS_PD_TO` | `MIS_COMMAND_TOUT` | renamed | 1.16 |
| `MIS_DIST_1WP` = 900 m | = 10000 m | allowed distance to the first mission waypoint | 1.16 |
| `RTL_TYPE` 0…3 | `RTL_TYPE` 0…4 | 4 picks the mission landing or home along the reversed mission, whichever is closer in waypoints; rally points are ignored | 1.16 |
| multicopter and hovering VTOL Return: always stops and descends to `RTL_DESCEND_ALT` | with `RTL_LAND_DELAY` = 0 the landing starts right from the return altitude | the stop at `RTL_DESCEND_ALT` with a wait happens only with a nonzero delay | 1.16 |
| `COM_OBS_AVOID`, `TRAJECTORY_REPRESENTATION_*` messages | removed | the external obstacle avoidance planner interface is gone; Collision Prevention (`CP_*`) remains | 1.16 |
| `rcS` picks the parameter file: `/fs/mtd_params` if present, otherwise the SD card | the board build sets the path (`CONFIG_BOARD_PARAM_FILE`, `/fs/mtd_params` by default) | some boards keep parameters on the SD card or in flash (`px4-console-params`) | 1.16 |
| — | `SYS_PARAM_VER` | a mismatch with the airframe's `PARAM_DEFAULTS_VER` at boot sets `SYS_AUTOCONFIG` = 1: parameters are reset to defaults (except `SYS_AUTOSTART`, calibrations, `RC*`) and the board reboots | 1.16 |
| `SDLOG_MODE` = −1 (disabled) | `SDLOG_BACKEND` = 0 | new parameter: bit 0 SD card, bit 1 MAVLink, 3 by default | 1.17 |
| `msg/VehicleCommand.msg` | `msg/versioned/VehicleCommand.msg` | versioned messages moved to `msg/versioned/` | 1.16 |
| `/fmu/out/vehicle_status` | `/fmu/out/vehicle_status_v1` | a `_vN` suffix on topics whose message version is > 0 | 1.16 |
| `/fmu/out/vehicle_local_position`, `battery_status`, `home_position`, `airspeed_validated`; `/fmu/in/vehicle_attitude_setpoint` | the same names with `_v1` | message version bumped | 1.17 |
| — | `UXRCE_DDS_RX_TO`, `UXRCE_DDS_TX_TO` (1.16), `UXRCE_DDS_NS_IDX` (1.17) | client timeouts and the namespace index; `UXRCE_DDS_CFG` unchanged | 1.16 / 1.17 |
| fmu-v6x, default build: `rc_input` (`RC_PORT_CONFIG`) | `crsf_rc`, `sbus_rc`, `dsm_rc`, `ghst_rc` (`RC_CRSF_PRT_CFG`, `RC_SBUS_PRT_CFG`, `RC_DSM_PRT_CFG`, `RC_GHST_PRT_CFG`) | CRSF/ELRS works without a custom build, `rc_input` is not in the build (same for fmu-v5x, fmu-v6xrt) | 1.17 |
| SITL: `COM_LOW_BAT_ACT` = 2 | SITL: `COM_LOW_BAT_ACT` = 3 | simulator default (`init.d-posix/rcS`); still 0 on a flight controller | 1.16 |
| SITL `gz_x500`: `NAV_DLL_ACT` = 0 | = 2 (Return) | only the simulator airframe 4001; 0 on a flight controller | 1.16 |

Unchanged and rechecked against v1.17.0: `IMU_GYRO_RATEMAX` 400 (800 for multicopters), `RTL_RETURN_ALT` 60 m (30 m for multicopters, `RTL_DESCEND_ALT` 10 m), `NAV_DLL_ACT` 0, `NAV_RCL_ACT` 2, `COM_RC_LOSS_T` 0.5 s, `COM_FAIL_ACT_T` 5 s, `COM_OF_LOSS_T` 1 s, `MC_AT_EN` 0 (1 in SITL), the `BAT_*_THR` thresholds, `MAV_1_CONFIG` = Disabled, the `make px4_sitl gz_x500` and `make px4_sitl sihsim_quadx` targets.

### Upgrading 1.17 → 1.18
PX4 v1.18.0 (tagged November 23, 2026, commit 935addf) is the course target since November 27, 2026. Comparing the parameter definitions of the v1.17.0 and v1.18.0 tags: 65 parameters removed, 237 added, 9 with a changed default (two of them for one vehicle type only). The tag carries the same lists in `Tools/migrate_param_file.py` (`CONVERSIONS`, `REMOVED`, `DEFAULT_CHANGES`). The values of the new parameters and the absence of the removed ones were checked with `param show` in SITL v1.18.0 (SIH, `sihsim_quadx`). Upgrade procedure:
1. **Back up before flashing**, as for 1.17: `.params`, logs, `ver all`.
2. **Flash over the old firmware.** On first boot 1.18 translates the values stored on board (`param_translation.cpp`): `EKF2_GPS_POS_X/Y/Z`, `EKF2_GPS_DELAY`, `MNT_RANGE_PITCH`, `MOT_POLE_COUNT`, `SENS_IMU_TEMP*`, `SENS_TEMP_ID`, `MPC_LAND_RC_HELP`, `EKF2_AGP_*`, `RCn_REV` (from float to integer) and only the "disabled" value of `COM_RC_OVERRIDE`. All other removed parameters are not carried over at all.
3. **A 1.17 `.params` file is not translated this way.** QGC sets parameters by name, so old names are silently skipped and the new ones stay at their defaults. Before loading, run the file through `Tools/migrate_param_file.py old.params new.params` from the v1.18.0 tag: it applies the same translations, writes `RCn_REV` as integers, drops the removed parameters and lists the values left at an old default. QGC may load a saved `-1.000000` into the integer `RCn_REV` as 0 (`migrate_param_file.py` warns about this; the tag does not name the QGC versions that fix it), so check the direction of every channel.
4. **Defaults.** A vehicle that was on a default gets the new one: `FD_ACT_EN` and `SENS_MAG_AUTOCAL` become 0, `NAV_ACC_RAD` on a multicopter is 10 m instead of 2.
5. **After the upgrade:** stick override in a hover (new threshold), failsafe on the bench (exception bits, `COM_LOW_BAT_ACT`), the gimbal on the bench (`px4-camera-gimbal`), ESC RPM in `esc_status` if you used bidirectional DShot.

| Before (1.17) | Now (1.18) | What to do | Where in the code (v1.18.0) |
|---|---|---|---|
| `COM_RC_OVERRIDE` (1: bit 0 auto modes, bit 1 Offboard), `COM_RC_STICK_OV` (30 → threshold 0.3 /s) | `MAN_OVERRIDE_SPD` = 1 /s (−1…10, negative disables): override by stick speed in every auto mode and in Offboard, multicopter and VTOL in hover | only "disabled" carries over (0 → −1); test the override with a sharp stick movement (`px4-safety-return`) | `manual_control_params.yaml:43`, `ManualControl.cpp:142`, `param_translation.cpp:247` |
| `COM_DISARM_MAN` = 1 | removed: disarming from the radio in the air in Stabilized and Acro is always allowed | if it was 0, arm on a latching switch (`px4-rc-tuning`) | `Commander.cpp:766` |
| `COM_KILL_DISARM` = 5 s, `COM_RC_ARM_HYST` = 1000 ms, `COM_LKDOWN_TKO` = 3 s, `COM_OBC_LOSS_T` = 5 s | removed, the old defaults are hard-coded | nothing; other times can no longer be set | `Commander.cpp:849`, `ManualControl.cpp:355`, `failsafe.cpp:681`, `Commander.cpp:3049` |
| `COM_ARM_SDCARD`, `COM_IMB_PROP_ACT`, `COM_MOT_TEST_EN`, `COM_TAKEOFF_ACT`, `COM_HLDL_REG_T`, `COM_FLT_PROFILE` | removed: SD card and prop imbalance always only warn, motor test is always allowed, Takeoff is always followed by Hold | to take off straight into a mission, arm in Mission | `migrate_param_file.py:134–142`, `failsafe.cpp:694`, `Commander.cpp:1786`, `Commander.cpp:2219` |
| `COM_FLTT_LOW_ACT` = 0 (return on remaining flight time off) | removed; return on remaining flight time is part of `COM_LOW_BAT_ACT` = 3, the new value 5 is the same without it | not carried over: with 3 and `BAT1_CAPACITY` set (or a smart battery) Return can start before critical; if you do not want that, use 5 | `commander_params.yaml:156`, `failsafe.cpp:666` |
| `COM_RCL_EXCEPT`, `COM_DLL_EXCEPT`: bit 1 is Hold (and Takeoff) | bit 1 is every auto mode (Hold, Takeoff, VTOL Takeoff, Land, Return, Descend, Follow Target, Precision Land, Orbit, fixed-wing Guided Course) | the stored value does not change: with bit 1 set, Return and Land now also ignore link loss | `commander_params.yaml:437`, `:454` |
| `COM_PARACHUTE` 0 / 1 (1 denies arming) | 0–4: 1 warns only, 2 denies arming, 3 Return, 4 Land | to deny arming, use 2 or higher | `commander_params.yaml:484` |
| `COM_ARM_ODID` 0–2 | 0–5: 3 Return, 4 Land, 5 Terminate on Remote ID loss in flight | — | `commander_params.yaml:569` |
| `NAV_RCL_ACT` 1, 2, 3, 5, 6 | + 7 Hold without failsafe | for external modes and Offboard without a radio | `commander_params.yaml:416` |
| `FD_ESCS_EN` = 1; `FD_ACT_EN` = 1 | `FD_ESCS_EN` removed, `FD_ACT_EN` = **0**; ESC offline and ESC faults with `COM_ARM_CHK_ESCS` = 1 | if you want the motor current check and the disarm on unarmed ESCs, set `FD_ACT_EN` = 1 | `esc_check_params.yaml:5`, `escCheck.cpp:84` |
| `FD_ACT_MOT_C2T` (2 A/%), `FD_ACT_MOT_THR`, `FD_ACT_MOT_TOUT` | `MOTFAIL_C2T` 35 A, `MOTFAIL_OFF` 10 A, `MOTFAIL_TIME` 1 s: both undercurrent and overcurrent trigger it | not carried over, set them again | `esc_check_params.yaml:15–40`, `escCheck.cpp:311` |
| `DSHOT_BIDIR_EN` (timer 0 only on STM32) | `PWM_MAIN/AUX_TIMn` = −6 / −7 / −8 is BDShot600/300/150 per group; `DSHOT_BIDIR_EDT` | not carried over: select BDShot for each motor group (`px4-outputs-servos`) | `pwm_out/module.yaml:24`, `dshot.c:303` |
| `MOT_POLE_COUNT` = 14 | `DSHOT_MOT_POL1…12` = 14 | carried over into all 12 | `dshot/module.yaml:77`, `param_translation.cpp:212` |
| `MNT_RANGE_PITCH` = 90, `MNT_OFF_ROLL/PITCH/YAW` | `MNT_MIN_PITCH` = −45, `MNT_MAX_PITCH` = 45 (can be asymmetric); no offsets, use the output trim; new parameter `MNT_TAU` (0.3 s), new values `MNT_DO_STAB` = 3 and `MNT_MODE_IN` = 5 (`MNT_FIXED_PITCH`; the parameter defaults are unchanged, 0 and −1) | the range carries over as ±range/2, the offsets do not; a knob in rate mode needs `MNT_TAU` = 0; with `MNT_DO_STAB` = 0 world-frame angle setpoints are not applied (SITL), see `px4-camera-gimbal` | `gimbal_params.yaml:101–171`, `output.cpp`, `param_translation.cpp:167` |
| `EKF2_GPS_POS_X/Y/Z`, `EKF2_GPS_DELAY` = 110 ms | `SENS_GPS0_OFFX/Y/Z`, `SENS_GPS0_DELAY` / `SENS_GPS1_DELAY` = 110, binding to the receiver via `SENS_GPS0_ID` / `SENS_GPS1_ID` | carried over; with two GNSS receivers check each one (`est-gnss`) | `vehicle_gps_position/module.yaml:58–110`, `param_translation.cpp:181, 202` |
| `EKF2_AGP_CTRL/MODE/DELAY/NOISE/GATE` (noise 0.9 m) | `EKF2_AGP0…3_*` + `EKF2_AGP0_ID`; noise 1.0 m; only bit 0 of `CTRL` enables it | carried over into set 0, with `CTRL` ≠ 0 `EKF2_AGP0_ID` = 1; for a source with another id, set it (`nav-vtrn`) | `params_aux_global_position.yaml:7–68`, `param_translation.cpp:318` |
| `SENS_IMU_TEMP*`, `SENS_TEMP_ID` | `HEATER1_TEMP*`, `HEATER1_SENS_ID` (0 is automatic selection; a stored 0 becomes −1, disabled) | carried over | `param_translation.cpp:273` |
| `MC_AT_START`, `FW_AT_START` | removed: autotune starts with the `MAV_CMD_DO_AUTOTUNE_ENABLE` command (QGC) | — | `mc_autotune_attitude_control.cpp:112` |
| `LNDMC_TRIG_TIME` = 1 s | removed: 1 s, 3 s with a rangefinder that has no data | — | `MulticopterLandDetector.cpp:127` |
| `GF_PREDICT`, `MPC_USE_HTE` = 1 | removed; the hover thrust estimator always runs | — | `migrate_param_file.py:155, 160` |
| `MPC_LAND_RC_HELP` | bit 1 of `MPC_AUTO_NUDGING`; bit 0 is stick yaw in every auto mode. Any bit, including nudging during landing, needs `MAN_OVERRIDE_SPD` = −1 (`multicopter_nudging_params.yaml:20`) | carried over, but `MAN_OVERRIDE_SPD` stays 1: a sharp nudge in Land becomes an override into Position, so set −1 | `multicopter_nudging_params.yaml:5`, `param_translation.cpp:302` |
| `NAV_ACC_RAD` on a multicopter 2 m (`rc.mc_defaults`) | 10 m (the parameter default; 2 for boats and airframes 4016, 4020, 24001) | on the old default the radius grows: waypoints are accepted earlier, the Return altitude near home is 2·d (`px4-safety-return`) | `navigator_params.yaml:20`, `rc.mc_defaults` |
| `SENS_MAG_AUTOCAL` = 1 | 0: an uncalibrated compass no longer saves an initial calibration on its own | calibrate the compass in QGC | `sensor_params_mag.yaml:77` |
| `VT_PITCH_MIN`, `VT_LND_PITCH_MIN` = −5° | 0° | — | `vtol_att_control_params.yaml:267, 280` |
| `EKF2_REQ_PDOP` on a plane 2.5 | 4.0 (`rc.fw_defaults`); 2.5 for the rest | — | `rc.fw_defaults:31` |
| `FW_T_HRATE_FF` 0.3; `MPC_LAND_RADIUS` 1000 | 0.5; −1 | — | `fw_lat_long_params.yaml:146`, `multicopter_nudging_params.yaml:26` |
| `RCn_REV` is a float | integer (−1 / 1) | when loading `.params` with an old QGC, check the reversal | `rc_update/params.yaml:32`, `param_translation.cpp:236` |
| Servo 1…8 functions (201…208) | Servo 1…15 (201…215) | — | `output_functions.yaml:14` |
| — | `COM_FLTMODE_BOOT` = 4 (Hold), the mode until the first command; `SYS_HAS_NUM_GNSS` + `COM_GNSSLOSS_ACT`; `FD_ALT_LOSS`; `ESC_TEMP_WARN_TH` 90 °C; `COM_CC_TEMP_WARN` 80 °C; `MC_REF_FF` 0; `MPC_Z_ERR_MAX` 1 m; `EKF2_POS_LOCK`; `EKF2_SENS_EN`; `RTL_TYPE` = 5 | new features; the default keeps the old behavior, except the temperature warnings and `MPC_Z_ERR_MAX` = 1 m: vertical trajectory stretching in auto modes is on (0 behaves as in 1.17; `multicopter_autonomous_params.yaml:134`, `FlightTaskAuto.cpp:782`) | `commander_params.yaml:132, 309, 612`, `system_params.yaml:139`, `failure_detector_params.yaml:94` |
| logs: no file size limit, old directories deleted only when less than 300 MiB was free (`logger/util.cpp:192`, v1.17.0); `logger_topics.txt` replaces the profile | `SDLOG_MAX_SIZE` = 1024 MiB, `SDLOG_ROTATE` = 90 % (at least 10 % of the card free); `logger_topics.txt` is added to the profile | keep only the extra topics in your `logger_topics.txt` | `logger/module.yaml:105, 120` |
| no MAVLink signing in 1.17.0 | standard MAVLink signing: key on the SD card, `SETUP_SIGNING` over any channel, but not while armed | — (`mav-protocol`) | `mavlink_sign_control.h:46`, `mavlink_main.cpp:1224` |
| `MAV_CMD_REQUEST_AUTOPILOT_CAPABILITIES`, `GET_HOME_POSITION` and others | removed, only `MAV_CMD_REQUEST_MESSAGE`; commands from the check table with a nonzero unused parameter (1–7) are rejected with `DENIED`, and a mission containing such an item is not uploaded (`MAV_MISSION_INVALID_PARAMn`, `mavlink_mission.cpp`) | companion scripts: send unused parameters as 0 or NaN | `mavlink_command_params.hpp`, `mavlink_receiver.cpp:685` |
| uXRCE-DDS topics `_v1` | `vehicle_status_v4`, `vehicle_command_ack_v1` and others | `px4_msgs` from the v1.18.0 branch (`px4-ros2`) | `msg/versioned/` |

Unchanged and rechecked against v1.18.0: the same defaults as in the 1.17 list above (`IMU_GYRO_RATEMAX`, gyro filters, `MC_ROLL_P` 4.0, `RTL_RETURN_ALT`/`RTL_DESCEND_ALT`, `NAV_DLL_ACT`, `NAV_RCL_ACT`, `COM_RC_LOSS_T`, `COM_FAIL_ACT_T`, `COM_OF_LOSS_T`, `MC_AT_EN`, `GPS_UBX_DYNMODEL`, `MIS_TAKEOFF_ALT` 2.5 m), the fmu-v6x timer groups (`timer_config.cpp`), the `rc_update` arithmetic, the `COM_FLTMODEn` slots, the selection of the most severe failsafe action (`framework.cpp`; refined: Warn no longer triggers a delayed Hold, disabled conditions are skipped, and a notification also arrives for a new condition absorbed by an action already in progress), the Return cone formula, the camera trigger and capture feedback drivers. Mode requirements (`mode_requirements.cpp`) are the same; only fixed-wing Guided Course was added.

{{diagram:px4-qgc-order|The order of the first PX4 setup in QGroundControl.}}

### Place in the system

- **Takes in:** a Pixhawk-compatible H7 flight controller (`f-fc-sensors`); sensor calibration results (`est-sensors`); ArduPilot habits for comparison (`ap-intro`).
- **Hands on:** the order of QGC pages to the step-by-step setup (`px4-setup-scratch`); the 1.15 → 1.17 and 1.17 → 1.18 upgrade tables to tuning, failsafes and the ROS 2 bridge (`px4-control`, `px4-safety-return`, `px4-ros2`); the ULog log to Flight Review and `data-python`.
- **If you get it wrong here:** you upgrade the firmware without checking the table → values that matched the old default silently take the new one → the vehicle flies differently and the tune must be checked again (`px4-control`). You keep an old `px4_msgs` → topics with the `_v1` suffix are not found → the offboard node cannot see the vehicle status (`ros2-px4`).

## practice
### Step 1. SITL and QGC
```
git clone https://github.com/PX4/PX4-Autopilot.git --recursive
cd PX4-Autopilot
bash ./Tools/setup/ubuntu.sh
make px4_sitl gz_x500
```

In the PX4 console (`pxh>`): `commander takeoff`, `commander land`. QGC connects over UDP on its own.

### Step 2. Modes
In QGC, switch the simulated vehicle through Position → Altitude → Stabilized and watch how the response to the sticks changes (QGC has a virtual joystick).

### Step 3. Parameters and the log
Run `param show MPC_THR_HOVER` in the console; after the flight download the `.ulg` from QGC (Analyze → Log Download) and open it in Flight Review.

### What you should get and what to write down
- **Step 1.** The first build and the first Gazebo start take a while: the build takes minutes and the world models download on the first start. After that a start takes seconds. `commander takeoff` lifts the x500 to the takeoff altitude `MIS_TAKEOFF_ALT` (2.5 m by default) and holds it there. QGC connects over UDP on its own. If there is no link, check that QGC runs on the same machine and that port 14550 is not taken by another client.
- **Step 2.** In Position, centered sticks hold the spot. In Altitude only the altitude is held and the vehicle drifts. In Stabilized the stick sets the angle and you hold the altitude. Write one line per mode: what the autopilot holds and what the pilot holds. That is the main takeaway of the module.
- **Step 3.** A mission in QGC (Plan): takeoff, three waypoints at 20 m, Return. In SITL the `.ulg` is in `build/px4_sitl_default/rootfs/log/<date>/`. In Flight Review find the roll and pitch angle plots (estimate vs. setpoint) and position vs. setpoint. In SITL a gap of more than a few degrees means something is wrong with the setup, not with the wind: SITL has no wind until you turn it on.

### Lab
Takeoff, a short mission from QGC and landing in SITL; the log uploaded to Flight Review, with the attitude and position setpoint plots found and compared with the actual values.

Self-check: the lab is done when SITL `gz_x500` is running and QGC connected on its own, `commander takeoff` lifted the vehicle to `MIS_TAKEOFF_ALT` (2.5 m by default), the three-waypoint mission ran through to landing, you wrote one line per mode on what the autopilot holds and what the pilot holds, and next to the `.ulg` your notes hold two Flight Review screenshots (attitude and position, setpoint vs. actual) with one sentence of conclusion each; the attitude error in SITL is no more than a few degrees.

**Reference answer for the self-check.** Position: with centered sticks the autopilot holds the spot. Altitude: only the altitude is held and the vehicle drifts. Stabilized: the stick sets the angle and you hold the altitude. Typical wrong results: (1) the attitude is off the setpoint by more than a few degrees: SITL has no wind until you turn it on, so the setup is at fault; (2) QGC did not connect: it runs on another machine, port 14550 is taken by another client, or an old PX4 instance is still running.

## diagnostics
- **Symptom:** QGC does not connect to SITL
  - Possible cause: another PX4 instance or a UDP port already in use.
  - What to do: kill the old processes and restart SITL.
- **Symptom:** Position will not engage
  - Possible cause: no GNSS fix (in SITL, wait for initialization).
  - What to do: wait for "Ready To Fly" in QGC.
- **Symptom:** the firmware will not install on an F4 board
  - Possible cause: PX4 does not support that hardware.
  - What to do: use a Pixhawk-compatible FMUv5/v6 board, or ArduPilot.
- **Symptom:** `make` fails on dependencies
  - Possible cause: `ubuntu.sh` was not run.
  - What to do: run the environment setup script and log in again.
- **Symptom:** "Preflight Fail: Compass Sensor 0 missing" / "Preflight Fail: Accel 0 inconsistent - check cal"
  - Possible cause: calibration not done or the sensor not detected (orientation, cable).
  - What to do: calibrate in order, check `SENS_BOARD_ROT`, run `dmesg` in the console.
- **Symptom:** Position mode will not engage
  - Possible cause: the EKF does not trust GNSS (`EKF2_GPS_CHECK`), no fix, or a bad compass.
  - What to do: QGC → MAVLink Console `ekf2 status`, the satellite count, a compass calibration in the field.
- **Symptom:** Flight Review shows high vibration
  - Possible cause: mechanics, a rigidly mounted FC.
  - What to do: the "Frame and vibration" module, dampers, balancing.

## references
- PX4 User Guide — Flight Modes (Multicopter) | https://docs.px4.io/v1.17/en/flight_modes_mc/index.html | primary | A
- PX4 User Guide — Simulation | https://docs.px4.io/v1.17/en/simulation/ | primary | A
- PX4-Autopilot — source code (GitHub) | https://github.com/PX4/PX4-Autopilot | primary | A
- PX4-Autopilot v1.18.0: docs/en/releases/1.18.md (release notes, Upgrade Guide) | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/docs/en/releases/1.18.md | primary | A
- PX4-Autopilot v1.18.0: Tools/migrate_param_file.py (translating .params 1.17 → 1.18) | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/Tools/migrate_param_file.py | primary | A
- PX4-Autopilot v1.18.0: src/lib/parameters/param_translation.cpp | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/lib/parameters/param_translation.cpp | primary | A
- QGroundControl — User Guide | https://docs.qgroundcontrol.com/Stable_V5.0/en/ | primary | A

## checklist
- I can explain when to choose PX4 and when ArduPilot
- SITL with Gazebo is running and QGC is connected
- I tried the Stabilized/Altitude/Position modes
- I opened a .ulg log in Flight Review
