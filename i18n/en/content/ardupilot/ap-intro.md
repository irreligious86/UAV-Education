---
id: ap-intro
title: "Introduction to ArduPilot"
level: L2
readingTime: 20 min
firmware: ArduCopter / ArduPlane 4.7 (checked against 4.7.3)
status: published
added: 2026-11-07
tags:
  - ArduPilot
  - parameters
  - modes
related:
  - ap-sitl
  - bf-intro
next:
  - ap-sitl
source: content/ardupilot/ap-intro.md
source_hash: 0c7049106c92
---

## summary
ArduPilot is an autopilot, not just a stabilizer. Where Betaflight makes a quadcopter obedient under the sticks, ArduPilot knows where the vehicle is, where it is going, and what to do without a pilot. This module explains how thinking in ArduPilot differs from Betaflight: parameters instead of CLI diffs, flight modes as levels of autonomy, the ground station, pre-arm checks, and hardware requirements. After it the whole "Autonomy" track opens up.

## theory
### Versions and parameter names
The course is written for the stable ArduPilot 4.7 release (Copter and Plane 4.7.3 of November 14, 2026; 4.7.0 was released on July 21, 2026). Names, units, and defaults are checked against the source of the 4.7.2 tag and the SITL parameters of that build, and the 4.7.3 differences against the source of the 4.7.3 tag: no parameter names were removed or renamed, one default changed, and two parameters were added (the "Moving from 4.7.2 to 4.7.3" table below). Labs captured on SITL 4.7.2 are marked as such. The previous release is 4.6.3: where a parameter was renamed or changed its unit in 4.7, the modules give the new name and, once, the old one in parentheses, and all the replacements are collected in the table below. Lab outputs captured on 4.6.3 are left as they are and marked with the version. Earlier renames that still appear in old guides: in Plane from 4.5 `ARSPD_FBW_MIN/MAX` → `AIRSPEED_MIN/MAX`, and from 4.6 `GPS_TYPE` → `GPS1_TYPE`.

### Moving from 4.6 to 4.7: what was renamed and what changed
1. **Before flashing:** save the full parameter list to a file (`.param`) and download the logs from the flight controller. According to a developer post in the 4.7.0 release thread, on boards with logs in onboard flash (LittleFS) the update erases the logs; this has not been verified in the source.
2. **Flash over the top, without erasing parameters:** on its first boot 4.7 moves the old values to the new names by itself and converts the units (cm → m, centidegrees → degrees). A full erase is needed only if you want to start from factory values, and then you have to repeat the calibrations and the setup.
3. **What is not carried over:** the `SRn_*` stream rates (in `MAVn_*` they come up at defaults, so set them again); `.param` files, Lua scripts, pymavlink scripts, and CI rules with the old names: a parameter with that name no longer exists, and the write silently does nothing; `AVOID_ANGLE_MAX`: avoidance by leaning was removed from the standard builds (in a build with that option the value is moved to `AVOID_ANG_MAX`).
4. **A rollback to 4.6** is possible, but values already changed in 4.7 under the new names are not converted back: to roll back, load the saved 4.6 parameter file.
5. **Ground station:** update Mission Planner or QGroundControl; an old version shows errors on renamed parameters and does not know the new ones.
6. **After the update, compare** the new parameter list with the old file using the table below; be sure to check `ARMING_SKIPCHK` (it must be 0), `RTL_ALT_M`, `ATC_ANGLE_MAX`, `MAVn_*`, and the Loiter behavior.
7. **First-flight traps:** in 4.7.0–4.7.2 Loiter did coordinated turns by default (`LOIT_OPTIONS = 1`), and in 4.7.3 the default is 0 again, so Loiter behaves as in 4.6 (`LOITER_DEFAULT_OPTIONS` in `AC_Loiter.cpp`); you enable the turns by hand with `LOIT_OPTIONS = 1`; the `ATC_INPUT_TC` default became 0.10 instead of 0.15, so the sticks are sharper; old terrain tiles cause the pre-arm failure "terrain data expired, possible errors", so delete the `APM/TERRAIN` folder on the SD card; the Simple and Super Simple modes do not work in 4.7.0, which was fixed in 4.7.1.

| Was (4.6.3) | Now (4.7.3) | What changed | Since |
|---|---|---|---|
| `ARMING_CHECK` | `ARMING_SKIPCHK` | the meaning is inverted: a mask of checks to **skip**; 0 means all enabled (it was 1), −1 skips all the optional ones (it was 0). Bits: 1 baro, 2 compass, 3 GPS, 4 INS, 5 parameters, 6 RC, 7 board voltage, 8 battery | 4.7.0 |
| `ANGLE_MAX` (centidegrees, 3000) | `ATC_ANGLE_MAX` (degrees, 30); on a QuadPlane `Q_ANGLE_MAX` → `Q_A_ANGLE_MAX` | name and unit | 4.7.0 |
| `ATC_ACCEL_R/P/Y_MAX` (centidegrees/s², 110000 / 110000 / 27000) | `ATC_ACC_R/P/Y_MAX` (deg/s², 1100 / 1100 / 270) | name and unit | 4.7.0 |
| `ATC_SLEW_YAW` (centidegrees/s, 6000) | `ATC_RATE_WPY_MAX` (deg/s, 60) | name and unit | 4.7.0 |
| `ATC_INPUT_TC` = 0.15 | `ATC_INPUT_TC` = 0.10 (on a QuadPlane `Q_A_INPUT_TC` 0.2 → 0.15) | only the default value | 4.7.0 |
| `RTL_ALT` (cm, 1500) | `RTL_ALT_M` (m, 15) | name and unit | 4.7.0 |
| `RTL_ALT_FINAL`, `RTL_CLIMB_MIN` (cm) | `RTL_ALT_FINAL_M`, `RTL_CLIMB_MIN_M` (m) | name and unit | 4.7.0 |
| `RTL_SPEED` (cm/s) | `RTL_SPEED_MS` (m/s; 0 means use `WP_SPD`) | name and unit | 4.7.0 |
| `WPNAV_SPEED` (cm/s, 1000) | `WP_SPD` (m/s, 10) | name and unit | 4.7.0 |
| `WPNAV_SPEED_UP` / `WPNAV_SPEED_DN` (cm/s, 250 / 150) | `WP_SPD_UP` / `WP_SPD_DN` (m/s, 2.5 / 1.5) | name and unit | 4.7.0 |
| `WPNAV_RADIUS` (cm, 200) | `WP_RADIUS_M` (m, 2) | name and unit | 4.7.0 |
| `WPNAV_ACCEL`, `WPNAV_ACCEL_Z`, `WPNAV_ACCEL_C` (cm/s², 250 / 100 / 0) | `WP_ACC`, `WP_ACC_Z`, `WP_ACC_CNR` (m/s², 2.5 / 1 / 0) | name and unit | 4.7.0 |
| `WPNAV_JERK`, `WPNAV_RFND_USE`, `WPNAV_TER_MARGIN` | `WP_JERK`, `WP_RFND_USE`, `WP_TER_MARGIN` | only the prefix (the units were already m/s³ and m) | 4.7.0 |
| `LAND_SPEED`, `LAND_SPEED_HIGH` (cm/s, 50 / 0) | `LAND_SPD_MS`, `LAND_SPD_HIGH_MS` (m/s, 0.5 / 0) | name and unit | 4.7.0 |
| `LAND_ALT_LOW` (cm, 1000) | `LAND_ALT_LOW_M` (m, 10) | name and unit | 4.7.0 |
| `PILOT_SPEED_UP` / `PILOT_SPEED_DN` (cm/s, 250 / 0) | `PILOT_SPD_UP` / `PILOT_SPD_DN` (m/s, 2.5 / 0) | name and unit | 4.7.0 |
| `PILOT_ACCEL_Z` (cm/s², 250) | `PILOT_ACC_Z` (m/s², 2.5) | name and unit | 4.7.0 |
| `PILOT_TKOFF_ALT` (cm) | `PILOT_TKO_ALT_M` (m) | name and unit | 4.7.0 |
| `LOIT_SPEED` (cm/s, 1250) | `LOIT_SPEED_MS` (m/s, 12.5) | name and unit | 4.7.0 |
| `LOIT_ACC_MAX`, `LOIT_BRK_ACCEL` (cm/s², 500 / 250), `LOIT_BRK_JERK` (cm/s³, 500) | `LOIT_ACC_MAX_M`, `LOIT_BRK_ACC_M` (m/s², 5 / 2.5), `LOIT_BRK_JRK_M` (m/s³, 5) | name and unit | 4.7.0 |
| — | `LOIT_OPTIONS` (bit 0 enables coordinated turns; default 0, it was 1 in 4.7.0–4.7.2) | a new parameter; 0 means Loiter as in 4.6 | 4.7.0; default 0 since 4.7.3 |
| — | `AUTOTUNE_GMBK` (0.25) | a new parameter: after AutoTune the tuned P and D gains are reduced by 25% | 4.7.0 |
| `PHLD_BRAKE_ANGLE` (centidegrees, 3000), `PHLD_BRAKE_RATE` | `PHLD_BRK_ANGLE` (degrees, 30), `PHLD_BRK_RATE` (deg/s, 8) | name; for the angle, also the unit; the threshold at which PosHold goes into braking after the stick is released was computed in degrees in 4.7.0–4.7.2 (2 × `PHLD_BRK_RATE`: 16° with the default of 8 on a multicopter, 8° on a helicopter with its default of 4), and in 4.7.3 it is 0.02 × `PHLD_BRK_RATE` again (0.16° / 0.08°), as in 4.6 | 4.7.0; threshold 4.7.3 |
| `CIRCLE_RADIUS` (cm, 1000) | `CIRCLE_RADIUS_M` (m, 10) | name and unit | 4.7.0 |
| `PSC_POSXY_P`, `PSC_VELXY_P/I/D` | `PSC_NE_POS_P`, `PSC_NE_VEL_P/I/D` | only the name (1 and 2 / 1 / 0.25) | 4.7.0 |
| `PSC_POSZ_P`, `PSC_VELZ_P/I/D` | `PSC_D_POS_P`, `PSC_D_VEL_P/I/D` | only the name (1 and 5 / 0 / 0) | 4.7.0 |
| `PSC_ACCZ_P/I/D` (0.5 / 1 / 0) | `PSC_D_ACC_P/I/D` (0.05 / 0.1 / 0) | name; values × 0.1 | 4.7.0 |
| `PSC_VELXY_IMAX`, `PSC_VELZ_IMAX` (1000) | `PSC_NE_VEL_IMAX`, `PSC_D_VEL_IMAX` (10) | name; values × 0.01 | 4.7.0 |
| `PSC_ACCZ_IMAX` (800) | `PSC_D_ACC_IMAX` (0.8) | name; value × 0.001 | 4.7.0 |
| `PSC_JERK_XY`, `PSC_JERK_Z` (m/s³, 5) | `PSC_NE_JERK`, `PSC_D_JERK` (in 4.7.0, `PSC_JERK_NE`, `PSC_JERK_D`) | only the name, twice | 4.7.0, 4.7.1 |
| `Q_P_POSXY/VELXY/POSZ/VELZ/ACCZ_*` (QuadPlane) | `Q_P_NE_POS/NE_VEL/D_POS/D_VEL/D_ACC_*` | the same rules and multipliers as for `PSC_*` | 4.7.0 |
| `Q_WP_SPEED*`, `Q_WP_RADIUS`, `Q_WP_ACCEL*`, `Q_LOIT_*` (cm) | `Q_WP_SPD*`, `Q_WP_RADIUS_M`, `Q_WP_ACC*`, `Q_LOIT_SPEED_MS`, `Q_LOIT_ACC_MAX_M`, `Q_LOIT_BRK_ACC_M`, `Q_LOIT_BRK_JRK_M` (m) | as for Copter | 4.7.0 |
| `SR0_*` … `SR6_*` (stream rates per channel, from zero) | `MAV1_*` … `MAV7_*` (from one: `SR0` → `MAV1`, `SR1` → `MAV2`; there are as many `MAVn_*` groups as the board has MAVLink channels) | name and numbering; the values are not carried over | 4.7.0 |
| `SERIALn_OPTIONS` bit 10 (do not forward MAVLink), bit 12 (ignore stream rate requests) | `MAVn_OPTIONS` bit 1, bit 2 | moved to the channel parameters; an old bit left in `SERIALn_OPTIONS` causes a pre-arm failure | 4.7.0 |
| `SYSID_THISMAV` | `MAV_SYSID` | only the name | 4.7.0 |
| `SYSID_MYGCS` | `MAV_GCS_SYSID` (+ the new `MAV_GCS_SYSID_HI`, a range of ground stations) | only the name | 4.7.0 |
| `SYSID_ENFORCE` | `MAV_OPTIONS` bit 0 | the parameter became a bit | 4.7.0 |
| `TELEM_DELAY` | `MAV_TELEM_DELAY` | only the name | 4.7.0 |
| `RNGFNDn_MIN_CM` / `RNGFNDn_MAX_CM` (cm) | `RNGFNDn_MIN` / `RNGFNDn_MAX` (m) | name and unit | 4.7.0 |
| `RNGFNDn_GNDCLEAR` (cm) | `RNGFNDn_GNDCLR` (m) | name and unit | 4.7.0 |
| `EK3_MAX_FLOW` | `EK3_FLOW_MAX` (rad/s, 2.5) | only the name | 4.7.0 |
| `EK3_SRC_OPTIONS` = 1 | `EK3_SRC_OPTIONS` = 0 | bit 0, FuseAllVelocities, is cleared by default; the new bit 3 gives every EKF core its own source set | 4.7.0 |
| `FS_EKF_ACTION` 1 / 2 / 3 | 0 added: report only | a new value; the default is still 1 | 4.7.0 |
| `AVOID_ANGLE_MAX` (centidegrees) | `AVOID_ANG_MAX` (degrees) | avoidance by leaning was removed from the standard builds, so the parameter exists only in firmware from the custom build server | 4.7.0 |
| `FS_SHORT_TIMEOUT` (Plane) | removed | the short failsafe was simplified; the long one is `FS_LONG_TIMEOUT` | 4.7.0 |
| the Plane short RC failsafe: on the `FS_SHORT_TIMEOUT` timer = 1.5 s | after `RC_FS_TIMEOUT` (1 s) + 0.2 s without frames; with throttle below `THR_FS_VALUE`, after 0.2 s | what now sets the delay of the short event; a step-by-step breakdown is in `ap-setup-plane` | 4.7.0 |
| `GLIDE_SLOPE_MIN`, `GLIDE_SLOPE_THR` (Plane) | `ALT_SLOPE_MIN`, `ALT_SLOPE_MAXHGT` | name | 4.7.0 |
| — (Plane) | the `AUTOLAND` mode (number 26), `AUTOLAND_*`, `RCx_OPTION = 183` | a new automatic landing mode without a mission | 4.7.0 |
| `FS_LONG_ACTN` 0…4, `BATT_FS_LOW_ACT` / `BATT_FS_CRT_ACT` up to 6, `FENCE_ACTION` 0, 1, 6, 7 (Plane) | + `FS_LONG_ACTN` = 5, `BATT_FS_*_ACT` = 7, `FENCE_ACTION` = 8 | the new "AUTOLAND, or RTL if that fails" values | 4.7.0 |
| — (Plane) | `TKOFF_THR_IDLE` = 0% | the throttle after arming and before the takeoff in TAKEOFF and AUTO | 4.7.0 |
| `FENCE_AUTOENABLE` = 1, 2 (Plane): they work, with a warning once a minute, "will be removed in 4.7, use 3" | the same: in 4.7.3 the values have not been removed and the warning is still there | the behavior did not change, but the values are declared deprecated, so move to 3 (enable when armed) | warning since 4.6.0 |
| `SERVOn_FUNCTION`: motors 33–40 and 82–85 (Motor1–12) | 160–179 added: Motor13…Motor32 | up to 32 motors | 4.7.0 |
| `BRD_SAFETY_MASK`: bits 0–13 in the description (outputs 1–14) | bits 0–31 (outputs 1–32) | the bit list was extended; the Copter default is unchanged, "all non-motor outputs of 1–14", not 0 (`ap-outputs`); the firmware reads only the low 16 bits of the mask | 4.7.0 |
| — | `MOT_IDLE_SEC` (0…5 s, default 0) | a delay at ground idle after arming, so the ESCs have time to start | 4.7.0 |
| one knob: `RCx_OPTION = 219`, `TUNE`, `TUNE_MIN` / `TUNE_MAX` | + a second one: `RCx_OPTION = 220`, `TUNE2`, `TUNE2_MIN` / `TUNE2_MAX` | 220 is not in the `RCx_OPTION` value list, so you enter it as a number (`ap-aux-tune`) | 4.7.0 |
| `TUNE` adjustment is off only if `TUNE_MIN` and `TUNE_MAX` are both 0 | it is off when `TUNE_MIN` = `TUNE_MAX` | the disable condition | 4.7.0 |
| `TUNE` up to 59 | + 60, Loiter Speed (m/s) | a new value; `TUNE = 10` (WP Speed) still sets the speed in **cm/s**, although `WP_SPD` is now in m/s | 4.7.0 |
| the `PTUN` log: `Param`, `TunVal`, `TunMin`, `TunMax` | + the `NIn` field | the normalized knob input (−1…1) | 4.7.0 |
| `RCx_OPTION` 300–307 (Scripting1–8) | 300–315 (Scripting1–16); 316 stops / restarts scripting | more scripting switches (`ap-lua`) | 4.7.0 |
| `RCx_OPTION = 163` Mount Lock | 163 Mount Yaw Lock; the new 185 Mount Roll/Pitch Lock and 186 Mount POI Lock | the name and two new functions | 4.7.0 |
| — | `RCx_OPTION = 182` AHRS AutoTrim | a new switch function | 4.7.0 |
| `CAM_RC_*` (RunCam) | `CAM1_RC_*`, camera type `CAM1_TYPE = 8` | RunCam became a camera type | 4.7.0 |
| `COMPASS_LEARN = 1` Internal-Learning | the value 1 is gone | what is left: 0, 2 EKF-Learning, 3 InFlight-Learning (`ap-sensors`) | 4.7.0 |
| `ARSPD_SKIP_CAL`: 0 / 1 | + 2 | 2 means do not calibrate the zero offset at boot, but require a manual calibration once per power-up | 4.7.0 |
| `ARSPD_TYPE` up to 16 | + 17–19 AUAV (10in, 5in, 30in) | new sensors | 4.7.0 |
| `BATT_MONITOR` up to 29 | + 30 INA3221, + 31 Analog Current Only (32, TI BQ76952, is AP_Periph only) | new monitors; type 31 always reports a voltage of 0 (`ap-sensors`) | 4.7.0 |
| `NTF_LED_TYPES` up to bit 18 | + bit 19 ProfiLED_IOMCU (524288) | an LED driven through the Cube's coprocessor (`ap-notify`) | 4.7.0 |
| `MNT1_TYPE` up to 13 | + 14 XFRobot | a new gimbal (only in builds for more than 1 MB of flash) | 4.7.0 |
| `RCx_OPTION = 19` Gripper: it was executed at boot, and without a receiver the position counted as LOW, so the gripper opened by itself | the same value; it is not executed at boot, and the gripper stays at `GRIP_NEUTRAL` | LOW is executed on the first receiver frame, so the gripper opens when you switch on the transmitter with the switch in LOW (`ap-payload`) | 4.7.0 |
| the winch, `WINCH_*`, in all builds | only with more than 2048 kB of flash | on boards with 2 MB of flash `WINCH_*` disappears after the update, and you need a custom build (`ap-payload`) | 4.7.0 |
| `SIM_GPS_DISABLE = 1`, `SIM_GPS2_DISABLE` (SITL) | `SIM_GPS1_ENABLE = 0`, `SIM_GPS2_ENABLE` | the meaning is inverted | 4.7.0 |
| `SIM_GPS_*` (the first receiver in SITL): `SIM_GPS_NOISE`, `SIM_GPS_GLITCH_X`, `SIM_GPS_ACC`, `SIM_GPS_HDG`, `SIM_GPS_POS_Y` | `SIM_GPS1_NOISE`, `SIM_GPS1_GLTCH_X`, `SIM_GPS1_ACC`, `SIM_GPS1_HDG`, `SIM_GPS1_POS_Y` | the receiver index in the name, and some names shortened | 4.7.0 |
| the Copter log fields `CTUN.CRt`, `CTUN.DCRt`: integer, cm/s | the same fields: floating point, m/s | recalculate in your own scripts that read the raw values | 4.7.0 |
| the `GEN` log (RichenPower generator) | `RICH` | the message name | 4.7.0 |

Unchanged names that people ask about most often: `FRAME_CLASS`, `FRAME_TYPE`, `FLTMODE1..6`, `FS_THR_ENABLE`, `FS_GCS_ENABLE`, `BATT_*`, `FENCE_*`, `EK3_SRCn_*`, `MOT_*`, `ATC_RAT_*`, `ATC_ANG_*`, `INS_*`, `SERIALn_PROTOCOL`, `RCx_OPTION`, `RTL_ALT_TYPE`, `RTL_LOIT_TIME` (ms), `RTL_CONE_SLOPE`, `PSC_ANGLE_MAX`, `WP_YAW_BEHAVIOR`, `WP_NAVALT_MIN`; the Copter mode numbers did not change.

### Moving from 4.7.2 to 4.7.3
A patch release: flash over the top; there is nothing to migrate in the parameters. From the source of the 4.7.3 tag (`ArduCopter/ReleaseNotes.txt`; Plane has the same library changes and none of its own):

| What | 4.7.2 | 4.7.3 | Where in the code |
|---|---|---|---|
| `LOIT_OPTIONS` (and `Q_LOIT_OPTIONS` on a QuadPlane, the same `AC_Loiter` class) | 1, coordinated turns | **0**, Loiter as in 4.6 | `LOITER_DEFAULT_OPTIONS`, `AC_Loiter.cpp` |
| PosHold going into braking after the stick is released | pilot lean < 2 × `PHLD_BRK_RATE` **degrees** (16° with the default of 8 on a multicopter; a helicopter's default is 4, so 8°) | < 0.02 × `PHLD_BRK_RATE` (0.16° / 0.08°), as in 4.6 | `mode_poshold.cpp`, `config.h` (`POSHOLD_BRAKE_RATE_DEFAULT`) |
| `CAMx_ZOM_RAT_MAX`, `CAMx_FOC_RAT_MAX` | absent | new, 5 %/s (0–100): the speed of the zoom and focus servo for `CAMx_TYPE = 1` (`ap-payload`) | `AP_Camera_Params.cpp` |
| `EAHRS_TYPE` | 0, 1, 2, 5–8, 11 | + 10, Aeron PLX3 (`ap-ahrs-choice`) | `AP_ExternalAHRS.cpp` |
| Throttle during vibration compensation (`ERR` subsystem 29) | acceleration feedforward without dividing by g | `throttle_hover / GRAVITY_MSS` | `AC_PosControl.cpp` |
| The post-filter `GYR` log (`INS_RAW_LOG_OPT`, `ap-logs`) with the fast rate thread enabled (`FSTRATE_ENABLE` > 0), which decimates the gyro | the log got the last value of the loop, not every filtered sample | every filtered sample | `AP_InertialSensor_Backend.cpp` |
| `CONDITION_YAW` with an absolute angle and `WP_YAW_BEHAVIOR = 0` (`ap-missions`) | in the HOLD yaw mode the heading was taken from navigation (`pos_control`), and the commanded angle was not held | HOLD holds the current target heading and remembers it on entry | `autoyaw.cpp` (`set_mode`, `yaw_rad`) |
| BLHeli passthrough (`ap-outputs`) | the flight controller could hang and data could be corrupted by an interrupt storm | fixed | `RCOutput.cpp`, `stm32_util.c` (ChibiOS) |

How a default value reaches the vehicle: a value equal to the default is not written to EEPROM as long as the parameter has never been saved (`AP_Param::save_sync`); if an entry already exists, it is overwritten with any value, and a `PARAM_SET` from the ground station that changes the value saves it even if it equals the default (`force_save`, `GCS_Param.cpp`). So: if you never touched `LOIT_OPTIONS` on 4.7.0–4.7.2, it becomes 0 after 4.7.3; if you changed it even once (even back to 1), the entry exists and it stays 1. Check `LOIT_OPTIONS` and Loiter on the first hover.

### One codebase, many vehicles
ArduPilot is a shared codebase with separate firmware per vehicle type: Copter (multirotors and helicopters), Plane (planes, wings, and QuadPlane VTOL), Rover, Sub. The frame type within a firmware is set with parameters: for Copter these are `FRAME_CLASS` (1 Quad, 2 Hexa, 3 Octa, 4 OctaQuad, 7 Tri…) and `FRAME_TYPE` (0 Plus, 1 X, 2 V, 3 H…).

{{diagram:ardupilot-fast-loop|How the ArduCopter loop works: sensors → EKF → mode controllers → rate controller → motors.}}

### Parameters
The whole configuration is parameters (there are more than a thousand). The key difference from Betaflight: a parameter change is written immediately, and there is no `save` command. Some parameters require a reboot (frame type, protocols, enabling subsystems). The workflow:

1. Save the full parameter list to a file (`.param`) before making changes.
2. Change one logical block at a time.
3. Compare the parameter files before and after, like `diff all` in Betaflight.

**Hidden until enabled.** Many subsystems have an enable parameter, and while it is 0, none of the parameters of that group are shown in the list (the `AP_PARAM_FLAG_ENABLE` flag in `AP_Param.h`: "enable variable allows a whole subtree of variables to be made invisible"). Examples in Copter 4.7.2: `INS_HNTCH_ENABLE` → `INS_HNTCH_*`, `FFT_ENABLE` → `FFT_*`, `BATT2_MONITOR` → `BATT2_*`, `RNGFND1_TYPE` → `RNGFND1_*`, `MNT1_TYPE` → `MNT1_*`, `CAM1_TYPE` → `CAM1_*`, `GRIP_ENABLE` → `GRIP_*`, `VTX_ENABLE` → `VTX_*`; in Plane, `Q_TILT_ENABLE` → `Q_TILT_*`. The procedure: (1) set the enable parameter to 1 (or to the type you need); (2) refresh the parameter list in the GCS: Mission Planner → Full Parameter List → Refresh Params, or in QGC Parameters → Tools → Refresh; (3) if the enable parameter is marked "Reboot Required", reboot, otherwise the driver does not start and the values do not reach the log. The check: after step 2 the group's parameters have appeared in the list. If the enable parameter itself is not in the list, the feature is not in the build (see "Which board to choose"), and no `.param` file will enable it.

### Flight modes
Modes are levels of autonomy. For Copter:

- **STABILIZE**: self-leveling, manual throttle. The basic mode; it works without GPS.
- **ALT_HOLD**: adds altitude hold from the barometer.
- **LOITER**: adds position hold; needs GPS.
- **AUTO**: flies a mission.
- **GUIDED**: commands from a ground station or a script (the basis of companion computers).
- **RTL** and **LAND**: return to launch and landing.

The rule: you choose a mode by which sensors you trust. No GPS means no LOITER, RTL, or AUTO.

### Ground station and MAVLink
You configure ArduPilot through a ground control station (GCS): Mission Planner, QGroundControl, or the console-based MAVProxy. All of them talk to the flight controller over MAVLink, the same protocol your companion computer will use later.

### Pre-arm checks
ArduPilot does not arm while something is wrong: an uncalibrated accelerometer or compass, no link, a bad EKF, wrong parameters. A `PreArm: ...` message in the GCS is a hint, not an obstacle. Disabling checks so that "it just flies" is the classic road to a crash.

### Hardware requirements
ArduPilot is noticeably heavier than Betaflight. On F4 flight controllers some features are unavailable: for example, Lua scripting is built only for boards with more than 1 MB of flash, so F405/F411 boards (1 MB or less) do not have it; F427/F429 boards with 2 MB (Pixhawk 1, Cube Black) do run Lua. For complex platforms people use an H7.

### Which board to choose
You choose a board by features, not by price. There is one threshold in the source, `HAL_PROGRAM_SIZE_LIMIT_KB` (`FLASH_SIZE_KB` from the hwdef plus external flash if the hwdef sets `EXT_FLASH_SIZE_MB`; `AP_HAL/board/chibios.h`), and each feature is included in a build only above its own threshold (ArduPilot 4.7.2, the `*_config.h` files):

| Feature you need | Flash threshold | What it is |
|---|---|---|
| Lua scripts (`SCR_*`) | > 1 MB | `ap-lua` |
| In-flight gyro FFT analysis (`FFT_*`) | > 1 MB | a notch driven by the spectrum, `ap-tuning` |
| ADS-B, proximity sensors, visual odometry | > 1 MB | `nav-indoor`, `per-depth-avoid` |
| MAVLink gimbals, ViewPro, Xacti, XFRobot | > 1 MB | `payload-gimbal` |
| RTCM decoding, EFI (combustion engines), deepstall landing | > 1 MB | `nav-rtk` |
| external AHRS (VectorNav and others), beacons, generator, winch, Volz servos | > 2 MB (on 2 MB, that is, on F765 and H743, **not** in the standard build) | — |

**Step 1. Flash.** You need a feature with a > 1 MB threshold → 2 MB: an STM32F7 (F765/F767) or an H7 (H743). Features with a > 2 MB threshold are not in the standard build on such boards: the threshold is strict, and an H743 has exactly 2048 kB. They exist only on boards with external flash (`EXT_FLASH_SIZE_MB` in the hwdef, for example H750 boards and CubeRedPrimary) or in your own build from custom.ardupilot.org. Chips per the ST datasheets: F405 has 1 MB, 168 MHz, 192 kB of RAM; F765 has 2 MB, 216 MHz, 512 kB; H743 has 2 MB, 480 MHz, 1 MB of RAM. In 4.7.2 there are more H743 boards than boards on any other chip. An F405 makes sense only for a simple plane or copter without scripts; some of these boards are cut down further (`minimize_features.inc`: no OSD, CRSF telemetry, or MSP). The exact contents of a build are in `features.txt` in the board's folder on firmware.ardupilot.org. What is missing on 1 MB can be built on custom.ardupilot.org, but only at the cost of other features. The procedure for your own build (the "Custom Firmware Build Server" wiki page): Add a build → vehicle, version (Stable is a release, for example 4.7.2; Beta and Latest are for testing), board → tick the features (the board's defaults are already ticked; enabling a feature adds its dependencies, and removing a feature removes everything that depends on it) → Generate → download the archive and flash the `.apj` (Mission Planner → Install Firmware → Load custom firmware). If it does not fit in flash, the build fails with an error; the fix is to remove other features (Lua alone takes about 180 kB). The check: after flashing, the enable parameter you need (`SCR_ENABLE`, `FFT_ENABLE`, `WINCH_TYPE`) is in the parameter list.

**Step 2. Number of IMUs.** By default EKF3 starts a core on each of the first two IMUs (`EK3_IMU_MASK = 3`) and switches to the other when one fails. With one IMU there is nothing to switch to. For a vehicle that costs more than a whoop or flies beyond visual line of sight, choose a board with ≥ 2 IMUs; for heavy vehicles and BVLOS, three IMUs and a damped IMU block (an **estimate**; details are in `el-redundancy`).

**Step 3. The board is in the release.** Find it in `libraries/AP_HAL_ChibiOS/hwdef` of your version or in the firmware list; the recommended list is the "Choosing an Autopilot" page.

**Step 4. A check after flashing.** Are `SCR_ENABLE` and `FFT_ENABLE` in the parameter list? If not, the build does not have those features. Pixhawk 2.4.8 clones use an F427, and on some of these chips the firmware can use only 1 MB (how common this is among clones is **not verified**): a 2 MB firmware on such a board reports `ERROR: 1M flash use Pixhawk1-1M` (the `Pixhawk1` build) or `ERROR: 1M flash use fmuv2` (the `fmuv3` build) by itself, so install the one the message names. A board like that is fine for learning, but not for a vehicle with Lua and FFT.

### What changes for a Betaflight pilot
- Parameter files instead of diffs.
- Calibrations (accelerometer, compass, radio, ESCs) and pre-arm checks instead of "flash and fly".
- DataFlash logs (`.bin`) are written almost always and contain everything, from vibration to EKF decisions.
- Tuning more often starts with AUTOTUNE than with manual PID.

### Copter modes by number (`FLTMODE1..6`, values from `Parameters.cpp`)
0 Stabilize, 1 Acro, 2 AltHold, 3 Auto, 4 Guided, 5 Loiter, 6 RTL, 7 Circle, 9 Land, 11 Drift, 13 Sport, 14 Flip, 15 AutoTune, 16 PosHold, 17 Brake, 18 Throw, 19 Avoid_ADSB, 20 Guided_NoGPS, 21 Smart_RTL, 22 FlowHold, 23 Follow, 24 ZigZag, 25 SystemID, 26 Heli_Autorotate, 27 Auto RTL, 28 Turtle. Six positions of the `FLTMODE_CH` channel (PWM boundaries at 1230/1360/1490/1620/1749) plus any modes on `RCx_OPTION`. Groups by sensor requirements: without position, Stabilize, Acro, AltHold (baro), Land (partly), FlowHold (optical flow); with position, Loiter, PosHold, Auto, Guided, RTL, Smart_RTL, Circle, Follow, ZigZag, Brake. The first flight of any build is Stabilize → AltHold → Loiter, in that order.

### Order of first setup (Mission Planner / QGC)
1. Firmware for the board type (`hwdef`), then the frame class and type (`FRAME_CLASS`, `FRAME_TYPE`).
2. Calibrations: accelerometer (6 positions), level, compass (outdoors), radio (`RC1..4_MIN/MAX/TRIM`), ESCs (with a DShot `MOT_PWM_TYPE` no calibration is needed), the voltage and current sensor (`BATT_MONITOR`, `BATT_VOLT_MULT`, `BATT_AMP_PERVLT` against a wattmeter).
3. Modes on switches, `RCx_OPTION` (ARM/DISARM, Motor E-Stop, EKF source set…).
4. Failsafes (see the "Fault tolerance" module), the geofence, `RTL_ALT_M` (meters; before 4.7, `RTL_ALT` in centimeters).
5. Starting tuning parameters for the prop size (see the "Tuning ArduPilot" module): `INS_GYRO_FILTER`, `ATC_RAT_*_FLT*`, `MOT_THST_EXPO`, `ATC_INPUT_TC`, `PSC_D_ACC_*`.
6. Logs (`LOG_BITMASK`), `LOG_DISARMED` for ground measurements.
7. A motor test (Mission Planner → Optional Hardware → Motor Test) with the props off: order and direction per the frame type diagram.

### Worked example: moving a pilot over from Betaflight
"Why won't it arm?" The `PreArm: …` message in the GCS names the cause in text (compass, GPS, INS, parameters, RC not calibrated), and `ARMING_SKIPCHK` (before 4.7, `ARMING_CHECK` with the inverted meaning) only selects which checks to skip. "Why doesn't it hold altitude in Stabilize?" Because Stabilize = Betaflight Angle, and AltHold is what holds altitude. "Where are the rates?" `ACRO_RP_RATE`/`ACRO_Y_RATE`, `ACRO_RP_EXPO`. "Where is the PID?" `ATC_RAT_RLL_P/I/D/FF/FLTD/FLTE/FLTT` (rate) and `ATC_ANG_RLL_P` (angle). "Where are the filters?" `INS_GYRO_FILTER`, `INS_HNTCH_*`. "Where is Blackbox?" DataFlash on the SD card, Review a Log. "Where is diff all?" Full Parameter List → Save to file / Compare Params, or `param save` in MAVProxy.

### Place in the system

- **Receives:** the EKF estimate, which decides which modes are available (`ap-ekf`); accelerometer and compass calibrations for the pre-arm checks (`est-sensors`); board resources: an F4 has fewer UARTs and no hardware inversion (`f-fc-sensors`), and with 1 MB of flash there is no Lua (`ap-lua`).
- **Provides:** the 4.7 parameter names and the rename table to every module of the track; the choice of a board by flash size to `ap-lua`; the order of first setup to `ap-setup-scratch`; the GUIDED mode to `ap-companion`.
- **If you get it wrong here:** after an update you loaded an old `.param` file or a script with 4.6 names → the write silently does nothing → failsafe and RTL run on defaults, not on your values (`ap-safety-fs`). `ARMING_SKIPCHK` is not 0 → some pre-arm checks are skipped → a bad compass or GPS surfaces in flight as "EKF variance" (`ap-ekf`).

## practice
### A first look with no risk
1. Go through the SITL module: everything below can be done in the simulator.
2. Open the full parameter list in the GCS and find `FRAME_CLASS`, `FRAME_TYPE`, `ARMING_SKIPCHK`, and `FS_THR_ENABLE` (in SITL 4.6.3 you will see `ARMING_CHECK` instead of `ARMING_SKIPCHK`).
3. Save the parameters to a file with the date in its name.
4. Switch the modes STABILIZE → ALT_HOLD → LOITER in SITL and see which ones require GPS.

### Check before the first real flight
1. The frame type and the motor order are verified with the props off (Motor Test).
2. The calibrations are done: accelerometer, compass (if there is one), radio, ESCs.
3. The radio and battery failsafes are configured.
4. There are no `PreArm` messages.
5. The first flight is low in STABILIZE, then ALT_HOLD.

**Automatic check of the first hover:** `examples/sitl-pymavlink/check_lab_log.py <log.bin> --lab hover` checks vibration p95 < 30, no clipping, `CTUN.ThO` in hover of 0.2–0.6 (this is a fraction of maximum thrust before the `MOT_THST_EXPO` curve, not a stick position: ThO ≈ 1/(T/W), that is, T/W from ~1.7 to 5), attitude tracking p99 < 10°, and battery sag < 15%.

### What you should get and what to record
- **Parameters.** `FRAME_CLASS = 1` (Quad), `FRAME_TYPE = 0` (Plus) is the default SITL frame (`sim_vehicle.py -v ArduCopter` without `-f` or with `-f quad`); a Quad X (`FRAME_TYPE = 1`) is started with `-f X`. `FS_THR_ENABLE` is the action on loss of the transmitter signal (the default is 1, RTL). The checks before arming are set by `ARMING_SKIPCHK` (0 means none is skipped); in SITL 4.6.3 it is `ARMING_CHECK` with the inverted meaning (1 means all enabled). For each parameter record the value and one sentence about what it does.
- **Parameter file:** `2026-11-09_sitl-quad.param`. Save before any change: it is your rollback point.
- **Modes.** STABILIZE works right away: the stick sets the angle, and the throttle is yours. ALT_HOLD holds altitude from the barometer, and horizontally the vehicle drifts. LOITER holds a point and requires a position estimate (GPS and a converged EKF). If you switch to LOITER before the GPS has a fix, the mode does not engage, and the ground station shows a refusal. Record which message you got: it checks that you understand how modes depend on sensors.
- **Automatic hover check.** The script prints the items that passed and failed. Run it on a SITL log (everything should pass) and save the output next to the log.

Self-check: the lab is done when the parameters are saved to a file with the date in its name before any change, in SITL without `-f` you found `FRAME_CLASS = 1` and `FRAME_TYPE = 0` and wrote one sentence about what each of the four parameters does, you did the STABILIZE → ALT_HOLD → LOITER sequence and your note on "what each mode holds" matches the reference below, and `check_lab_log.py --lab hover` passes every item on the SITL log, with its output saved next to the log.

**Reference for the self-check.** STABILIZE: the autopilot holds the angle, and throttle and altitude are yours. ALT_HOLD: it holds altitude from the barometer, and horizontally the vehicle drifts. LOITER: it holds a point and therefore requires a position estimate, that is, GPS and a converged EKF. Typical wrong results: (1) LOITER "does not engage" because you switched before the GPS had a fix and the ground station shows a refusal: that is expected behavior, not a fault; (2) `FRAME_TYPE = 1` instead of 0, because SITL was started with `-f X` and not with the default frame.

## diagnostics
- **Symptom:** `PreArm: ...` and the drone does not arm
  - Possible cause: an unfinished calibration or a wrong parameter; the message text names the subsystem.
  - What to do: read the whole message and remove the cause; do not disable the checks (`ARMING_SKIPCHK`).
- **Symptom:** nothing changed after you changed a parameter
  - Possible cause: the parameter requires a reboot.
  - What to do: reboot the flight controller and read the value back.
- **Symptom:** LOITER/RTL are unavailable
  - Possible cause: no GPS fix, or the EKF is not ready.
  - What to do: wait for a 3D fix, check the EKF status in the GCS.
- **Symptom:** Lua scripts do not run on the flight controller
  - Possible cause: a board with 1 MB of flash or less (F405, F411), so the firmware has no scripting; or not enough memory.
  - What to do: check the board's flash size; scripts need more than 1 MB, that is, 2 MB (F427/F429, F7, H7).
- **Symptom:** "PreArm: Compass not calibrated / inconsistent"
  - Possible cause: the calibration was not done, or the internal and external compasses disagree (interference).
  - What to do: calibrate outdoors, and disable the internal compass when you have an external one on a mast: `COMPASS_USEn = 0` for the priority slot it is in (`COMPASS_USE2` is the second by priority, not necessarily the internal one; check `COMPASS_PRIOn_ID` against the compass list in the GCS).
- **Symptom:** "PreArm: Check fence" / "Need 3D Fix"
  - Possible cause: the geofence is enabled and the GPS has no fix.
  - What to do: wait for a fix (`GPS_HDOP_GOOD`), or temporarily fly without the geofence, in modes that need no position only.

## references
- Frame Class and Type Configuration — ArduPilot Copter | https://ardupilot.org/copter/docs/frame-type-configuration.html | primary | A
- Pre-Arm Safety Checks — ArduPilot Copter | https://ardupilot.org/copter/docs/common-prearm-safety-checks.html | primary | A
- Choosing an Autopilot — ArduPilot Copter | https://ardupilot.org/copter/docs/common-autopilots.html | primary | A
- Lua Scripts — ArduPilot | https://ardupilot.org/copter/docs/common-lua-scripts.html | primary | A
- Firmware Limitations on AutoPilot Hardware — ArduPilot (features.txt, custom.ardupilot.org; accessed 2026-11-22) | https://ardupilot.org/copter/docs/common-limited-firmware.html | primary | A
- ArduPilot Copter-4.7.3 — ReleaseNotes.txt (changes from 4.7.2) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.3/ArduCopter/ReleaseNotes.txt | primary | A
- ArduPilot Copter-4.7.2 — AP_HAL/board/chibios.h (HAL_PROGRAM_SIZE_LIMIT_KB) and *_config.h (feature thresholds) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_HAL/board/chibios.h | primary | A
- ArduPilot Copter-4.7.2 — hwdef Pixhawk1-1M and fmuv3 (the 1 MB flash message) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_HAL_ChibiOS/hwdef/Pixhawk1/hwdef.dat | primary | A

## checklist
- I understand the difference between Copter and Plane and what `FRAME_CLASS` and `FRAME_TYPE` set
- I save the parameters to a file before making changes
- I know which modes require GPS
- I do not disable pre-arm checks just to take off
- I know the processor series of my FC and the limits of an F4
