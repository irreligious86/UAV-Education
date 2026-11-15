# ArduPilot coverage audit — parameters, GCS/console mechanisms, aux switches and TUNE, popular questions, hardware integration

Date: 2026-11-15. Scope: the ArduPilot track (`content/ardupilot/*.md`, 14 modules: ap-intro, ap-sitl, ap-setup-scratch,
ap-missions, ap-lua, ap-ekf, ap-logs, ap-tuning, ap-plane-tuning, ap-safety-fs, ap-heavy, ap-quadplane, ap-companion,
aero-wing) plus every other module that names ArduPilot parameters (estimation/*, companion/* incl. payload-gimbal,
per-*, mav-*, electronics/* incl. el-dronecan, link/*, foundation/f-esc-firmware, betaflight/bf-servos-pwm and
bf-hd-osd-video where they have ArduPilot rows). Goal set by the owner: close ArduPilot so that a student can do
everything common from the course alone. Method and structure follow `docs/reviews/betaflight-coverage-audit.md`.
No course content was edited.

Legend: **✓** explained (meaning and usage, module id) · **~** mentioned only · **✗** absent. Priority: **A** must-know
for anyone who sets up an ArduPilot copter or wing · **B** a good student should know it · **C** niche.
"Verified" below means read in the source of the stated version, or observed in SITL, in this audit. Anything not
verified that way is marked **(unverified)**.

---

## 1. Method and sources

### 1.1 Firmware sources

| Source | Version / commit | How used |
|---|---|---|
| `/tmp/ardupilot` full checkout | tag **Copter-4.6.3**, `92b0cd7` | reference for everything; `Tools/autotest/param_metadata/param_parse.py --vehicle ArduCopter --format json` → parameter list |
| same, built SITL `build/sitl/bin/arducopter` | Copter-4.6.3 | run as instance `-I9` (TCP 5850), `--defaults` = empty file, `-w`: firmware defaults dumped over MAVLink (1378 visible parameters); TUNE knob experiment (§4.2) |
| shallow clone `Plane-4.6.3` | `3fc7011`, 2025-11-04 | Plane metadata (`--vehicle ArduPlane`), `AP_Tuning`, `tiltrotor.cpp`, `AP_Airspeed.cpp` |
| shallow clone `Copter-4.7.2` | `fb77356`, 2026-10-13 | 4.7 metadata and the rename diff (§1.3); tag `Copter-4.7.0` = 2026-07-21 |
| shallow clone `master` | `abc2cd3`, 2026-11-15, `version.h` **4.8.0-dev** | what changes after 4.7 |
| `raw.githubusercontent.com` | Copter-4.5.7 / Plane-4.5.7 | two rename checks (GPS_TYPE → GPS1_TYPE in 4.6; AIRSPEED_MIN already in Plane 4.5) |

All clones are under `/tmp/ardupilot-audit/` (not built). Helper scripts written for the audit: `coverage.py`
(templates and course coverage), `p.py` (metadata + SITL default lookup), `names_check.py` (every backticked
parameter-like name in the course checked against 4.6.3/4.7.2/master Copter and Plane metadata), `tune_knob.py`.

Important caveat about defaults. SITL with an empty defaults file gives the **firmware** default, but many defaults
are set per board in `hwdef.dat` and differ on real hardware: `OSD_TYPE` (`HAL_OSD_TYPE_DEFAULT`, many FPV boards ship 1),
`BATT_MONITOR` and pins, `NTF_LED_TYPES` (`DEFAULT_NTF_LED_TYPES`; SITL shows 123079, which does **not** include the
NeoPixel bit), `BRD_SAFETY_DEFLT`, `RELAYn_PIN`, `SERIALn_PROTOCOL`, `ARSPD_TYPE`. Those are marked "board-dependent".
`sim_vehicle.py` additionally loads `Tools/autotest/default_params/copter.parm` (`RC1_MIN 1000`, `RC1_MAX 2000`,
`FRAME_TYPE 0`, `BATT_MONITOR 4`), which explains several values the course quotes from SITL (they are right for SITL,
not for a fresh board: the firmware default is `RC1_MIN` 1100 / `RC1_MAX` 1900, `FRAME_TYPE` 1, `BATT_MONITOR` 0).

### 1.2 Web sources

| Source | Status |
|---|---|
| ardupilot.org wiki | fetched with WebFetch: `common-blheli32-passthru`, `common-msp-osd-overview-4.2`, `common-displayport`, `common-serial-led-neopixel`, `common-magfit`, Mission Planner `mission-planner-initial-setup` |
| docs.qgroundcontrol.com (master) | `setup_view/setup_view.html` fetched (ArduPilot vs PX4 Vehicle Setup pages) |
| discuss.ardupilot.org | three web searches (PreArm/AHRS/compass; DJI/Walksnail OSD; BDShot); result lists cited in §5. Thread contents not read |
| github.com HTML | blocked by the proxy (not needed: sources cloned) |
| Mission Planner / QGC applications | not run; screen names come from their docs pages above |
| Reddit, RCGroups | not tried |

"How common" in §5 is an evidence class, not a count: **W** — the wiki has a dedicated page or section (**W†** = page
fetched in this audit); **D** — discuss.ardupilot.org threads appeared in this audit's search results; **S** — the
behaviour was checked in source or SITL here.

### 1.3 Versions: 4.6 vs 4.7 vs master

The course says "ArduPilot 4.5+" (ap-intro) but the SITL work is 4.6.3, and several modules already use 4.7 names.
Copter **4.7 is stable since 2026-07-21** (tag Copter-4.7.0), current **4.7.2**; `master` is **4.8.0-dev**. Parameter
templates (instance numbers collapsed, `SIM_*` and applet parameters excluded): **4.6.3 → 4.7.2: 101 removed, 232
added; 4.7.2 → master: 12 removed, 30 added.** The renames that matter for this course (4.6 name → 4.7 name):

- `ARMING_CHECK` (checks to perform, 1 = all) → `ARMING_SKIPCHK` (checks to **skip**, 0 = none skipped, −1 = skip all non-mandatory)
- `ANGLE_MAX` (cdeg, 3000) → `ATC_ANGLE_MAX` (deg); `ATC_ACCEL_R/P/Y_MAX` → `ATC_ACC_R/P/Y_MAX` (deg/s/s)
- `RTL_ALT`, `RTL_ALT_FINAL`, `RTL_CLIMB_MIN`, `RTL_SPEED` (cm, cm/s) → `RTL_ALT_M`, `RTL_ALT_FINAL_M`, `RTL_CLIMB_MIN_M`, `RTL_SPEED_MS`
- `WPNAV_*` → `WP_*` (`WP_SPD`, `WP_SPD_UP/DN`, `WP_ACC`, `WP_RADIUS_M`, `WP_RFND_USE`, `WP_TER_MARGIN`)
- `LOIT_SPEED`, `LOIT_ACC_MAX`, `LOIT_BRK_*` → `LOIT_SPEED_MS`, `LOIT_ACC_MAX_M`, `LOIT_BRK_ACC_M`, `LOIT_BRK_JRK_M`; `LAND_SPEED` → `LAND_SPD_MS`, `LAND_SPEED_HIGH` → `LAND_SPD_HIGH_MS`, `LAND_ALT_LOW` → `LAND_ALT_LOW_M`; `PILOT_SPEED_UP/DN`, `PILOT_ACCEL_Z`, `PILOT_TKOFF_ALT` → `PILOT_SPD_UP/DN`, `PILOT_ACC_Z`, `PILOT_TKO_ALT_M`; `CIRCLE_RADIUS` → `CIRCLE_RADIUS_M`
- `PSC_ACCZ_*` → `PSC_D_ACC_*`, `PSC_VELZ_*` → `PSC_D_VEL_*`, `PSC_POSZ_P` → `PSC_D_POS_P`, `PSC_VELXY_*` → `PSC_NE_VEL_*`, `PSC_POSXY_P` → `PSC_NE_POS_P`, `PSC_JERK_XY/Z` → `PSC_NE_JERK`/`PSC_D_JERK`
- `SRn_*` stream rates → `MAVn_*` with **index + 1** (`SR0_` → `MAV1_`; `GCS.cpp` `_chan[0]` = "1"); `SYSID_THISMAV` → `MAV_SYSID`, `SYSID_MYGCS` → `MAV_GCS_SYSID`, `TELEM_DELAY` → `MAV_TELEM_DELAY`
- `RNGFNDn_MIN_CM/MAX_CM/GNDCLEAR` → `RNGFNDn_MIN/MAX/GNDCLR` (m)
- `CAM_RC_*` (RunCam) → `CAMn_RC_*`; Copter 4.7 adds `TUNE2`, `TUNE2_MIN/MAX` (a second transmitter-tuning knob) and `TEMPn_*`, `FSTRATE_*`, `CCn_*` (custom controller)
- master (4.8-dev) after 4.7.2: `GND_EFFECT_COMP` → `GNDEFF_*`, `AHRS_CUSTOM_*`/`COMPASS_CUS_*` removed, adds `VTX_TYPES`, `FLIP_RATE`, `BATTn_CFG_UPDATE`, `MNTn_ATT_RATE`

Plane: `ARSPD_FBW_MIN/MAX` → `AIRSPEED_MIN/MAX` happened in **4.5** (Plane-4.5.7 `Parameters.cpp` already has `AIRSPEED_MIN`) —
the course statement is correct.

---

## 2. Settings interface: GCS screens, console, MAVLink mechanisms, scripting

ArduPilot has no CLI like Betaflight; the "commands" are the GCS screens, MAVProxy console commands and MAVLink
commands. Each row: what it does — course coverage — priority.

### 2.1 Parameters and files

| # | Mechanism | What it does | Course | Pri |
|---|---|---|---|---|
| 1 | Parameter store (AP_Param) | every change is written immediately; `@RebootRequired` params act after reboot; params of a disabled subsystem are hidden (`AP_PARAM_FLAG_ENABLE`: e.g. no `OSD_*` until `OSD_TYPE` ≠ 0, no `Q_TILT_*` until `Q_TILT_ENABLE = 1`) | ✓ ap-intro (immediate write, reboot); hidden-until-enabled rule ✗ | A |
| 2 | `.param` save / load / compare | MP Full Parameter List → Save/Load/Compare; QGC Parameters → Tools → Save/Load; MAVProxy `param save`/`param load`/`param diff` | ✓ ap-setup-scratch (save, compare), ap-intro; load and `param diff` ✗ | A |
| 3 | Defaults layers | firmware default → board `hwdef` defaults (`defaults.parm` in ROMFS) → user params; SITL adds `copter.parm` | ~ (hwdef named in ap-intro/ap-setup-scratch; layering ✗) | B |
| 4 | Firmware install | `*_with_bl.hex` over DFU first, then `.apj` (MP Install Firmware / QGC Firmware); `-bdshot` board variants (33 hwdef dirs in 4.6.3) | ✓ ap-setup-scratch; `-bdshot` variants ✗ | A |
| 5 | Custom firmware build server (custom.ardupilot.org) | builds with features removed from 1 MB F4 targets (e.g. OSD items, scripting is impossible <2 MB) | ✗ (only Betaflight Cloud Build in bf-custom) | B |
| 6 | MAVFTP and `@SYS/` | file access (logs, `APM/scripts`, `@PARAM/param.pck`); `@SYS/uarts.txt`, `@SYS/timers.txt` (output timer groups, mode and frequency per timer), `@SYS/dma.txt`, `@SYS/tasks.txt` (`AP_Filesystem_Sys.cpp`) | ~ mav-services (MAVFTP); `@SYS/timers.txt` ✗ | B |
| 7 | Applet parameters | applets add their own params (`param:add_table`), visible after reboot (e.g. `MOT_STOP_BITMASK`, `QUIK_*`) | ✓ ap-lua, ap-tuning | B |

### 2.2 Mission Planner screens (names from the MP docs, not re-checked in the app)

| # | Screen | Course | Pri |
|---|---|---|---|
| 8 | SETUP → Install Firmware | ✓ ap-setup-scratch | A |
| 9 | Mandatory Hardware → Frame Type | ✓ ap-intro (params) | A |
| 10 | → Accel Calibration (6 positions + level) | ✓ ap-setup-scratch | A |
| 11 | → Compass (onboard mag cal, fitness, **Large Vehicle MagCal** button) | ✓ onboard cal; Large Vehicle MagCal ✗ | A |
| 12 | → Radio Calibration | ✓ ap-setup-scratch | A |
| 13 | → **Servo Output** (function, min/trim/max, reverse per output; live bars) | ✗ (named nowhere) | A |
| 14 | → ESC Calibration | ✓ ap-setup-scratch | A |
| 15 | → Flight Modes | ✓ ap-setup-scratch | A |
| 16 | → Failsafe | ~ (params in ap-safety-fs, screen not named) | B |
| 17 | Optional Hardware → Battery Monitor (1 and 2) | ✓ BM1 ap-setup-scratch; BM2 ✗ | A |
| 18 | → Motor Test | ✓ ap-setup-scratch | A |
| 19 | → Compass/Motor Calib (CompassMot) | ✓ ap-setup-scratch, el-emi | B |
| 20 | → DroneCAN/UAVCAN (node list, node params, node firmware, SLCAN) | ✓ el-dronecan | B |
| 21 | → RTK/GPS Inject | ✓ nav-rtk | B |
| 22 | → SiK Radio | ~ link-telemetry-radios | B |
| 23 | → Range Finder, Airspeed, Optical Flow, Camera Gimbal, OSD, Parachute | ✗ (params partly elsewhere) | B |
| 24 | CONFIG → Full Parameter List / Tree | ✓ | A |
| 25 | CONFIG → Initial Parameter Setup ("Initial Tune Parameters") | ✓ ap-setup-scratch, ap-heavy | A |
| 26 | CONFIG → Basic / Extended Tuning, Standard/Advanced Params, User Params (aux switches CH7–CH12 option), Onboard OSD, MAVFtp | ~ (MAVFtp only); **Onboard OSD editor** and **User Params** ✗ | B |
| 27 | DATA → Actions, Messages, MAVLink Inspector, DataFlash logs, Scripts | ~ (Messages, Inspector, DataFlash logs) | B |

### 2.3 QGroundControl Vehicle Setup for ArduPilot (QGC master docs)

ArduPilot pages: Summary, Firmware, Frame, Sensors, Radio, Flight Modes, Power, Safety, Flight Safety, Motors, **Servo
Outputs**, **Gimbal**, **Scripting**, **Logging**, Tuning, ESC, Failsafes, Parameters, Joystick, Remote Support. Course:
Firmware ✓ and Parameters ✓ (ap-setup-scratch); Radio/Flight Modes/Power/Motors named once ("QGC → Radio") ~;
Servo Outputs, Gimbal, Scripting, Logging ✗. Priority B (MP is the course's main GCS; one QGC mapping table suffices).

### 2.4 MAVProxy console and MAVLink commands used for setup

| # | Command | What it does | Course | Pri |
|---|---|---|---|---|
| 28 | `param set/show/fetch/save/load/diff` | parameters | ✓ set/show/save (ap-lua, ap-ekf, ap-setup-scratch); load/diff ✗ | A |
| 29 | `mode`, `arm throttle`, `disarm`, `rc <ch> <pwm>`, `reboot` | flying SITL from the console | ✓ ap-sitl | A |
| 30 | `motortest`, `accelcal`, `magcal` | Motor Test, calibrations | ✓ ap-setup-scratch | A |
| 31 | `wp load/save/list`, `fence load`, `rally load/add` | mission, fence, rally upload | ✓ `wp load` ap-sitl; fence/rally ✗ | B |
| 32 | `module load` (map, console, graph, terrain, `output add`) | MAVProxy modules, extra outputs to a second GCS | ~ (module load in nav-terrain); `output add` ✗ | B |
| 33 | `MAV_CMD_DO_MOTOR_TEST`, `PREFLIGHT_CALIBRATION`, `PREFLIGHT_REBOOT_SHUTDOWN` | what the GCS buttons send | ✓ ap-setup-scratch | B |
| 34 | `MAV_CMD_DO_SET_SERVO`, `DO_SET_RELAY`, `DO_DIGICAM_CONTROL`, `DO_SET_CAM_TRIGG_DIST`, `DO_MOUNT_*`/gimbal manager | payload commands | ✓ ap-missions, payload-gimbal (commands only; hardware side ✗) | B |
| 35 | `MAV_CMD_FIXED_MAG_CAL_YAW` | compass cal from known yaw + WMM, no rotation (MP Large Vehicle MagCal; `GCS_Common.cpp`) | ✗ | B |

### 2.5 In-flight and on-aircraft mechanisms

| # | Mechanism | Course | Pri |
|---|---|---|---|
| 36 | `RCx_OPTION` aux functions (119 values in Copter 4.6.3, +29 Plane-only) | ~ (≈ 20 values named in 9 modules; no list, no thresholds) | A |
| 37 | `TUNE` / `TUNE_MIN` / `TUNE_MAX` + `RCx_OPTION = 219` (Copter); `TUNE_CHAN/PARAM/SELECTOR/RANGE/MODE_REVERT` (Plane `AP_Tuning`) | ✗ | A |
| 38 | Lua scripting (`SCR_*`, applets, `RCx_OPTION` 300–307) | ✓ ap-lua | A |
| 39 | OSD parameter screens (`OSD5_*`, `OSD6_*`: change params with sticks) | ✗ | C |
| 40 | `OSD_TYPE = 4` TXONLY (OSD parameter menus for CRSF TX without an OSD chip) | ✗ | C |
| 41 | AUTOTUNE (`RCx_OPTION = 17`, Plane 107), QuikTune applet | ✓ ap-tuning, ap-plane-tuning | A |
| 42 | Stick arming (`ARMING_RUDDER`), save trim (`RCx_OPTION = 5`), Simple/Super Simple | ~ (ARMING_RUDDER only) | B |
| 43 | Logs: DataFlash, MAVExplorer, `mavlogdump.py`, WebTools (filter review, MagFit) | ✓ ap-logs (WebTools ✗) | A |

**Totals (43 rows): ✓ 26, ~ 10, ✗ 7** (counting a row as ✓ only if its main mechanism is explained). The A rows that are not ✓:
Servo Output screen (13), `RCx_OPTION` list (36), TUNE (37), hidden-until-enabled params (1, partial).

---

## 3. Parameters by group (Copter 4.6.3)

Source: `param_parse.py` JSON for ArduCopter at Copter-4.6.3: **4775 names in 317 metadata groups**. Instance numbers
collapsed (`SERVO9_FUNCTION` → `SERVOn_FUNCTION`, `BATT2_*` → `BATT_*`, `OSD3_*` → `OSDn_*`) give **2356 templates**;
without `SIM_*` and Lua-applet parameters (`''` group, 241 names) **1762 templates**. A template counts as named if any
of its names, or the template spelling used by the course (`SERVOn_`, `RCx_`, `BATT_*`), appears as a token in a course
file. **Named in ArduPilot-track modules: 161; anywhere in the course: 348** (upper bound — e.g. `BATT2_MONITOR` is
counted through `BATT_MONITOR`, although no module mentions a second monitor).

| Group | Templates | Named in AP track | Named anywhere |
|---|---|---|---|
| Outputs: `SERVOn_*`, `SERVO_*` (DShot/BLHeli/rate/GPIO), `MOT_PWM_*`, `BRD_IO_*`, `BRD_SAFETY*`, `RC_SPEED` | 41 | 14 | 17 |
| Motors / mixer (`MOT_*`, `FRAME_*`) | 23 | 11 | 11 |
| RC input, aux switches, modes (`RCn_*`, `RC_*`, `RCMAP_*`, `FLTMODE*`, `RSSI_*`, `TUNE*`, `PILOT_*`, `ACRO_*`, `THR_DZ`, `ANGLE_MAX`) | 51 | 18 | 22 |
| Attitude/position control and modes (`ATC`, `PSC`, `WPNAV`, `LOIT`, `CIRCLE`, `LAND`, `RTL`, `PHLD`, `ZIGZ`, `THROW`, `FOLL`, `SURFTRAK`, `AUTOTUNE`, `SID`…) | 217 | 28 | 55 |
| Failsafe, arming, fence, rally, SmartRTL, avoidance, ADS-B, AFS, parachute | 141 | 19 | 36 |
| INS, filters, FFT, harmonic notches, temperature cal | 190 | 12 | 16 |
| EKF2/EKF3, AHRS, external AHRS, visual odometry, optical flow | 168 | 21 | 52 |
| Compass | 65 | 1 | 7 |
| GPS | 49 | 3 | 26 |
| Baro, airspeed, rangefinder, RPM, temperature sensors | 85 | 4 | 10 |
| Battery, generator, EFI | 48 | 14 | 16 |
| Logging | 14 | 3 | 3 |
| Serial, MAVLink streams, CAN/DroneCAN, network, DDS, MSP, FrSky | 162 | 2 | 24 |
| OSD (incl. 213 `OSDn_*` element/screen templates), VTX, notify (LED/buzzer), buttons | 270 | 3 | 3 |
| Mount, camera, relay, gripper, winch, sprayer, landing gear, precision landing | 96 | 0 | 33 |
| Scripting | 18 | 4 | 4 |
| Terrain | 6 | 1 | 6 |
| Traditional heli (`H_*`) | 72 | 0 | 0 |
| Other (AIS, `DID_*` Remote ID, `TMODE_*` Torqeedo, `MIS_*`, `INITIAL_MODE`…) | 46 | 3 | 7 |
| **Total** | **1762** | **161** | **348** |

Below: every uncovered **A/B** parameter with meaning and the 4.6.3 default (SITL firmware default unless marked
"source" or "board-dependent").

### 3.1 Outputs (41 / named 17)
Covered: `SERVOn_FUNCTION` (motors 33–36, mount 6–8, quadplane tilt), `SERVOn_MIN/MAX/TRIM/REVERSED` (bf-servos-pwm
comparison table, ap-plane-tuning), `MOT_PWM_TYPE` 0/1/2/4–7, `SERVO_DSHOT_ESC` 1/2, `SERVO_BLH_AUTO`, `SERVO_BLH_BDMASK`,
`SERVO_BLH_POLES` (14), `SERVO_BLH_RVMASK`, `BRD_IO_DSHOT`, `SERVO_RATE` 50 (named only in bf-servos-pwm). Uncovered:
- `SERVOn_FUNCTION` values beyond motors/mount: −1 GPIO, 1 RCPassThru, 51–66 RCIN1–16, 140–155 RCIN1Scaled–16Scaled,
  10 CameraTrigger, 28 Gripper, 29 LandingGear, 27 Parachute, 94–109 Script1–16, 120–123 NeoPixel1–4, 129–132 ProfiLED,
  138/139 Alarm, 134–136 SERVOn_MIN/TRIM/MAX (fixed value); Plane: 4 Aileron, 19 Elevator, 21 Rudder, 70 Throttle,
  77/78 Elevon, 79/80 V-tail, 2/3 Flap/FlapAuto, 24/25 Flaperon, 26 GroundSteering, 41/45 tilt groups. **A**
  (default 0 for outputs above the board's motor defaults)
- `SERVO_DSHOT_ESC` 3/4 (BLHeli32/AM32 or BLHeli_S/Bluejay **+ EDT**, extended DShot telemetry) — new values in 4.6. **B** (default 0)
- `SERVO_DSHOT_RATE` = 0 (1 kHz; 1–4 = 1–4× loop rate) — DShot frame rate. **B**
- `SERVO_BLH_MASK` = 0 — passthrough/BLHeli on non-motor outputs (Plane, Rover). **B**
- `SERVO_BLH_TRATE` = 10 Hz (source) — ESC serial-telemetry request rate; `SERVO_BLH_OTYPE`, `SERVO_BLH_3DMASK` (reversible), `SERVO_BLH_PORT`. **B**
- `SERVO_GPIO_MASK` = 0 — outputs used as GPIO even with a function; `SERVO_32_ENABLE` = 0. **B**/C
- `RC_SPEED` = 490 Hz — multicopter motor PWM frame rate for `MOT_PWM_TYPE = 0` (not for DShot). **A**
- `MOT_PWM_MIN/MAX` (named) = 1000/2000 in SITL; meaning of 0/0 on real boards (use RC3 range) **(unverified)**. **B**
- `BRD_SAFETY_DEFLT` (board-dependent; 0 in SITL), `BRD_SAFETY_MASK` = 16383, `BRD_SAFETYOPTION` = 3 — hardware safety
  switch; PreArm "Hardware safety switch" and passthrough need it off. **A**
- `BRD_PWM_COUNT` — **does not exist in 4.6.3** (removed earlier; outputs become GPIO with `SERVOn_FUNCTION = -1`). Version of removal **unverified**. Forum answers still quote it. **B** (as a "legacy" note)

### 3.2 Motors / mixer (23 / 11)
Well covered (ap-setup-scratch, ap-heavy, ap-tuning). Uncovered B: `MOT_SAFE_DISARM` = 0 (outputs off when disarmed),
`MOT_SAFE_TIME` = 1 s; `FRAME_TYPE` 12 BetaFlightX / 18 BetaFlightXReversed (12 named), 13 DJIX, 14 ClockwiseX;
`FRAME_CLASS` 5 Y6, 7 Tri (named), 12 DodecaHexa, 14 Deca, 15/17 Scripting Matrix. C: `MOT_BOOST_SCALE`, `MOT_SLEW_*`.

### 3.3 RC input, aux, modes (51 / 22)
Covered: `RC_PROTOCOLS`, `RC_OPTIONS` (bits 9, 13), `RSSI_TYPE`, `FLTMODE_CH`, `FLTMODEn`, `RCMAP_*`, `RC_FS_TIMEOUT`,
`RC_OVERRIDE_TIME`, `ARMING_RUDDER`, `ACRO_*`. Uncovered:
- `RCn_OPTION` value list and switch logic (§4) — **A**
- `TUNE` = 0, `TUNE_MIN` = 0, `TUNE_MAX` = 0 — §4. **A**
- `RCn_DZ` = 20 (`RC3_DZ` throttle), `RCn_REVERSED` = 0 (switch reversal only with `RC_OPTIONS` bit 7), `THR_DZ` = 100,
  `PILOT_THR_BHV` = 0 — "AltHold drifts with stick centred", reversed switches. **B**
- `RC_OPTIONS` bit 11 (use LQ as RSSI for CRSF), bit 1 (ignore MAVLink overrides), bit 10 (multiple receivers), bit 5/6
  arming checks. **B**
- `ANGLE_MAX` = 3000 cdeg (named only once, as rename) — max lean. **A**; `PILOT_SPEED_UP` = 250 cm/s, `PILOT_SPEED_DN`,
  `PILOT_ACCEL_Z`, `PILOT_Y_RATE`. **B**
- `DISARM_DELAY` = 10 s — auto-disarm after landing. **B**

### 3.4 Failsafe, arming, fence, rally (141 / 36)
Covered: the full Copter failsafe table (ap-safety-fs; values match the 4.6.3 metadata), `FENCE_ENABLE/TYPE/ACTION/
ALT_MAX/RADIUS/MARGIN`, `SRTL_POINTS`. Uncovered A/B:
- `ARMING_CHECK` bit list: 0 All, 1 Baro, 2 Compass, 3 GPS lock, 4 INS, 5 Parameters, 6 RC, 7 Board voltage, 8 Battery,
  9 Airspeed, 10 Logging, 11 Safety switch, 12 GPS config, 13 System, 14 Mission, 15 Rangefinder, 16 Camera, 17 AuxAuth,
  18 VisualOdometry, 19 FFT, 20 OSD (`AP_Arming.h`). **A**
- `ARMING_ACCTHRESH` = 0.75 m/s² ("Accels inconsistent"), `ARMING_MIS_ITEMS` = 0, `ARMING_NEED_LOC` = 0, `ARMING_OPTIONS` = 0. **B**
- `FENCE_ALT_MIN` = −10 m, `FENCE_AUTOENABLE` = 0 (1 on takeoff, 2 disable floor on landing, 3 only when armed),
  `FENCE_OPTIONS` = 0, `FENCE_TOTAL`; polygon/inclusion/exclusion via MP Plan → Fence (`FENCE_TYPE` bit 2). **B**
- `RALLY_TOTAL` = 0, `RALLY_LIMIT_KM` = 0.3, `RALLY_INCL_HOME` = 1 — RTL to the nearest rally point. **B**
- `SRTL_ACCURACY` = 2 m, `SRTL_OPTIONS` = 0. **B**
- `FS_OPTIONS` default is **16** (bit 4 set) — see §7.3 #5. **A**
- `FS_CRASH_CHECK` = 1, `FS_EKF_THRESH` = 0.8, `FS_DR_ENABLE` = 2 (RTL), `FS_DR_TIMEOUT` = 30 s (dead-reckoning
  failsafe; course names it without defaults). **B**
- Plane failsafes: `THR_FAILSAFE` (0/1/2), `FS_SHORT_ACTN`, `FS_SHORT_TIMEOUT`, `FS_LONG_ACTN` (0 Continue, 1 RTL, 2 Glide,
  3 Parachute, 4 Auto), `FS_LONG_TIMEOUT` — **named nowhere in the course**. **A** for wings

### 3.5 INS / filters (190 / 16)
Well covered for tuning (ap-tuning: `INS_GYRO_FILTER`, `INS_HNTCH_*`, `INS_LOG_BAT_MASK`). Uncovered B:
`INS_HNTC2_*` (second notch), `INS_ACCEL_FILTER` (named once), `INS_FAST_SAMPLE` = 1, `FFT_ENABLE` = 0 (in-flight FFT,
`INS_HNTCH_MODE = 4`), `INS_TCALn_*`/`TCAL_*` (temperature calibration — "Gyros inconsistent" on cold boards, §5 #3).

### 3.6 EKF / AHRS (168 / 52) — well covered (ap-ekf, nav-*). One wrong name: §7.3 #4.

### 3.7 Compass (65 / 7) — **largest relative gap among A topics**
Only `COMPASS_USE2/3`, `COMPASS_MOTCT`, `COMPASS_ORIENT` (once) are named. Uncovered:
- `COMPASS_CAL_FIT` = 16 (4 very strict, 8 strict, 32 relaxed) — "calibration never finishes". **A**
- `COMPASS_AUTO_ROT` = 2 (check and fix orientation during cal), `COMPASS_ORIENT` = 0 (external), `COMPASS_EXTERNAL` = 1. **A**
- `COMPASS_PRIOn_ID` (priority order since 4.0 — `COMPASS_USE2` refers to **priority 2**, not "the internal one"),
  `COMPASS_ENABLE` = 1, `COMPASS_DISBLMSK` = 0. **B**
- `COMPASS_LEARN` = 0 (3 = in-flight learning), `RCx_OPTION = 62` Compass Learn, `COMPASS_AUTODEC` = 1, `COMPASS_DEC` = 0. **B**
- `COMPASS_OFSn_*`, `DIAn`, `ODIn`, `SCALEn`, `MOTn` — what calibration and MagFit write. **B**
- `ARMING_MAGTHRESH` = 100 mGauss ("Check mag field"), `EK3_MAG_CAL` = 3. **B**

### 3.8 GPS (49 / 26) — covered by nav-rtk/est-gnss. B gaps for a first build: `GPS_AUTO_CONFIG` = 1, `GPS1_GNSS_MODE` = 0,
`GPS1_RATE_MS`, `GPS_AUTO_SWITCH`; `GPS1_TYPE` was `GPS_TYPE` in 4.5 (el-dronecan says so correctly).

### 3.9 Baro, airspeed, rangefinder (85 / 10)
Rangefinder covered in est-alt-sources (`RNGFND1_TYPE` 24/25/100, `ORIENT = 25`, `MIN/MAX_CM`, `GNDCLEAR`). Uncovered:
- `RNGFND1_MIN_CM` = 20, `RNGFND1_MAX_CM` = 700, `RNGFND1_GNDCLEAR` = 10 (source defaults), serial types 8 LightWare,
  20 Benewake serial, 10 MAVLink, 36 Lua; `RNGFND1_SCALING`/`PIN` for analog. **B**
- Airspeed (Plane): `ARSPD_TYPE` (Plane default 1 MS4525 on hardware, 2 Analog in SITL, 0 in Copter — `AP_Airspeed.cpp`),
  **`ARSPD_USE` = 0** (sensor read but not used by TECS until 1 — source default), `ARSPD_RATIO` = 2, `ARSPD_AUTOCAL` = 0,
  `ARSPD_PIN`, `ARSPD_BUS` = 1, `ARSPD_TUBE_ORDR` = 2, `ARSPD_OPTIONS` (wind-max disable/recover), `ARSPD_WIND_MAX`,
  `ARSPD2_*`, `RCx_OPTION 106` Disable Airspeed Use. **A** for wings
- `BARO1_GND_PRESS`, `BARO_ALT_OFFSET`, `BAROn_WCF_*` (wind compensation). C

### 3.10 Battery (48 / 16)
Covered in depth (ap-setup-scratch, el-battery-packs): analog monitor, calibration, failsafe thresholds. Uncovered B:
`BATT2_MONITOR` … `BATT9_`, `BATTA_`…`BATTG_` (16 monitors), `BATT_MONITOR` 10 (Sum of selected) + `BATT_SUM_MASK`,
8 DroneCAN, 9 ESC (+ `BATT_ESC_MASK`), 21 INA2xx, 7 SMBus; `BATT_FS_VOLTSRC` = 0 (1 = sag-compensated), `BATT_OPTIONS`,
`BATT_ARM_MAH`, `BATT_VOLT_PIN`/`BATT_CURR_PIN` (board-dependent), `BATT_SERIAL_NUM`.

### 3.11 Logging (14 / 3)
`LOG_BITMASK` named; default **180222** = bits 1–13, 15, 17 (Medium attitude, GPS, PM, CTUN, NTUN, RCIN, IMU, CMD,
Battery, RCOUT, OptFlow, **PID**, Compass, Camera, Motors) — `ArduCopter/config.h` `DEFAULT_LOG_BITMASK`. Uncovered B:
bit 0 Fast Attitude, 18 Fast IMU, 19 Raw IMU, 21 fast notch; `LOG_BACKEND_TYPE` = 1 (file), `LOG_MAX_FILES` = 500,
`LOG_FILE_MB_FREE` = 500, `LOG_FILE_BUFSIZE` = 200, `LOG_REPLAY` = 0, `LOG_DISARMED` values 2/3 (disabled on USB, discard if never armed).

### 3.12 Serial, MAVLink, CAN (162 / 24)
Covered: `SERIALn_PROTOCOL` 2, 5, 8, 9, 16, 23, 33, 42; `SRn_*`/`MAVn_*`; `CAN_P1_DRIVER`, `CAN_D1_PROTOCOL`,
`CAN_P1_BITRATE` = 1000000, `CAN_D1_UC_ESC_BM`. Uncovered B:
- `SERIALn_PROTOCOL` 10 FrSky passthrough, 32 MSP, 37 SmartAudio, 44 IRC Tramp, 29 Crossfire VTX, 26 RunCam, 34 airspeed,
  28 Scripting, 45 DDS; `SERIALn_BAUD` codes (57 = 57600, 115, 460, 921), `SERIALn_OPTIONS` bits (0/1 invert, 2 half-duplex,
  3 swap TX/RX, 8/9 no DMA — the F4 SBUS/FPort/SmartAudio answers), `BRD_SERn_RTSCTS`.
- `CAN_D1_UC_NODE`, `CAN_D1_UC_SRV_BM` (servos over CAN), `CAN_D1_UC_OPTION` (bit 0 clear DNA DB, bit 7 Hobbywing ESC),
  `CAN_D1_UC_ESC_OF`, `CAN_SLCAN_CPORT`/`SERNUM`/`TIMOUT`, `CAN_LOGLEVEL`; `CAN_D1_PROTOCOL` 11 Benewake etc.

### 3.13 OSD, VTX, notify (270 / 3) — **nothing usable**
Named: `OSD_TYPE` (1, 5; `3` in bf-hd-osd-video), `OSD_CHAN`, `OSDn_ENABLE`, `MSP_OPTIONS` (bit 2). Everything else is
✗; full list in §6d/§6b. Defaults (source `AP_OSD.cpp`, `AP_OSD_Screen.cpp`, `AP_MSP.cpp`, `AP_Notify.cpp`, `AP_VideoTX.cpp` via metadata):
`OSD_TYPE` 0 (board-dependent), `OSD_TYPE2` 0, `OSD_CHAN` 0, `OSD_SW_METHOD` 0 (toggle), `OSD_OPTIONS` 1 (decimal pack),
`OSD_UNITS` 0, `OSD_MSG_TIME` 10 s, `OSD_W_BATVOLT` 10.0, `OSD_W_AVGCELLV` 3.6, `OSD_W_LQ` 50, `OSD_W_NSAT` 9,
`OSD_CELL_COUNT` −1 (auto), `OSD_ARM_SCR`/`DSARM_SCR`/`FS_SCR` 0, `OSD_V_OFFSET` 16, `OSD_H_OFFSET` 32, `OSD1_ENABLE` 1
(screens 2–4: 0), `OSDn_CHAN_MIN/MAX` 900/2100, `OSDn_TXT_RES` 0 (30×16), `OSDn_FONT` 0, `MSP_OPTIONS` 0, `MSP_OSD_NCELLS` 0;
`NTF_LED_TYPES` board-dependent (NeoPixel = bit 8), `NTF_LED_LEN` 1 (1–32), `NTF_LED_BRIGHT` 3, `NTF_LED_OVERRIDE` 0,
`NTF_BUZZ_TYPES` 1 (5 = built-in + DroneCAN on CAN boards), `NTF_BUZZ_VOLUME` 100, `NTF_BUZZ_PIN` −1, `NTF_BUZZ_ON_LVL` 1,
`NTF_DISPLAY_TYPE` 0; `VTX_ENABLE` 0, `VTX_BAND/CHANNEL/FREQ/POWER/MAX_POWER`, `VTX_OPTIONS` (bit 0 pitmode, 1 pitmode until armed,
2 pitmode when disarmed, 3 unlocked). All **B** except `OSD_TYPE`/`OSDn_TXT_RES`/`MSP_OPTIONS` (**A** for anyone with an FPV link).

### 3.14 Mount, camera, relay (96 / 33 anywhere, **0 in the AP track**)
payload-gimbal explains `MNT1_TYPE`, `DEFLT_MODE`, limits, `RC_RATE`, `RCx_OPTION 212–214/163`, `SERVOn_FUNCTION 6–8`.
Uncovered: `MNT1_TYPE` value list (§6e), `MNT1_DEFLT_MODE` default **3 RC targeting** (source), `MNT1_PITCH_MIN/MAX`
−90/20, `MNT1_RC_RATE` 0, `MNT1_NEUTRAL_*`, `MNT1_RETRACT_*`, `MNT1_LEAD_*`, `MNT1_OPTIONS`, `MNT1_SYSID_DFLT`;
`CAM1_TYPE` (0 None, 1 Servo, 2 Relay, 3 Solo GoPro, 4 Mount, 5 MAVLink, 6 MAVLinkCamV2, 7 Scripting), `CAM1_DURATION`
0.1 s, `CAM1_SERVO_ON/OFF` 1300/1100, `CAM1_RELAY_ON` 1, `CAM1_TRIGG_DIST` 0, `CAM1_INTRVAL_MIN` 0, `CAM1_FEEDBAK_PIN` −1,
`CAM1_MNT_INST`, `CAM1_OPTIONS`, `CAM_AUTO_ONLY` 0, `CAM_MAX_ROLL` 0; `RELAYn_FUNCTION` (0 None, 1 Relay, 3 Parachute,
4 Camera; default NONE, SITL shows RELAY1 = 1), `RELAYn_PIN` −1 (board-dependent), `RELAYn_DEFAULT` 0, `RELAYn_INVERTED` 0;
`GRIP_*` (named in payload-gimbal), `LGR_*`, `WINCH_*`. **B** (camera/relay **A** for mapping projects).

### 3.15 Most valuable uncovered parameters (top 25)
`RCn_OPTION` list + thresholds; `TUNE`/`TUNE_MIN`/`TUNE_MAX`; Plane `TUNE_*`; `SERVOn_FUNCTION` non-motor values (−1, 1,
51–66, 10, 120–123); `RC_SPEED`; `SERVO_DSHOT_ESC` 3/4; `BRD_SAFETY_DEFLT`; `OSDn_TXT_RES`; `MSP_OPTIONS`;
`OSD_SW_METHOD`/`OSDn_CHAN_MIN/MAX`; `NTF_LED_TYPES` bit 8 + `NTF_LED_LEN`; `NTF_BUZZ_*`; `VTX_*` + `SERIALn_PROTOCOL 37/44`;
`COMPASS_CAL_FIT`; `COMPASS_AUTO_ROT`; `COMPASS_PRIOn_ID`; `ARSPD_USE`; `ARSPD_TYPE`; `BATT2_MONITOR` + `BATT_SUM_MASK`;
`ARMING_CHECK` bits; `FENCE_AUTOENABLE`; `RALLY_*`; Plane `THR_FAILSAFE`/`FS_SHORT_ACTN`/`FS_LONG_ACTN`; `CAM1_*`;
`RELAYn_PIN`; `LOG_BITMASK` bits.

---

## 4. In-flight adjustment: `RCx_OPTION`, TUNE, Plane AP_Tuning, scripting

### 4.1 What the course says now
- `RCx_OPTION` values named: 17 AutoTune, 31 Motor E-Stop, 153 ArmDisarm, 300–307 Scripting1–8 (ap-setup-scratch, ap-lua,
  ap-tuning), 212–214 Mount, 163 Mount Lock (payload-gimbal), 90 EKF source set (ap-ekf, nav-indoor), Plane 107 AutoTune,
  180 test gains (ap-plane-tuning). No list, no switch thresholds, no explanation of "acts on change", no reversal rule.
- TUNE: **nothing** in ArduPilot modules ("TUNE" appears only in INAV text). Plane `TUNE_*`: nothing.
- Scripting on a switch: ✓ ap-lua (`rc:find_channel_for_option`, `get_aux_switch_pos`), QuikTune switch ✓ ap-tuning.

### 4.2 How it works (4.6.3 source and SITL)

**Aux switches** (`libraries/RC_Channel/RC_Channel.cpp/.h`): position LOW below **1200 µs**, HIGH above **1800 µs**, MIDDLE
between (`AUX_SWITCH_PWM_TRIGGER_LOW/HIGH`); a new position must be stable **200 ms** (`SWITCH_DEBOUNCE_TIME_MS`); the
function runs **on change**, and a subset also runs at boot from the current position (`init_aux_function`, e.g. AirMode,
Simple, Transmitter Tuning in Copter). `RCn_REVERSED` reverses a switch only if `RC_OPTIONS` bit 7 "Allow Switch reverse"
is set. Any channel 1–16 can carry any option; the mode channel is `FLTMODE_CH` (positions 1230/1360/1490/1620/1749).
Copter 4.6.3 has 119 option values, Plane adds 29 (Plane-only: 51 MANUAL, 77 TAKEOFF, 82 QAssist 3pos, 87 Crow, 88 Soaring,
91 airspeed ratio cal, 106 disable airspeed, 107 FW autotune, 108 QRTL, 150 CRUISE, 155 set trim, 181 QuickTune, 208 Flap,
209 VTOL fwd throttle, 210 Airbrakes…). The common Copter set a lesson should table:

| Value | Function | Value | Function |
|---|---|---|---|
| 153 / 154 | ArmDisarm / ArmDisarm with AirMode | 31 / 165 | Motor Emergency Stop / Arm+E-Stop |
| 81 | Disarm | 32 | Motor Interlock (heli) |
| 4, 16, 18, 42, 55, 56, 68, 69, 70, 99 | RTL, AUTO, LAND, SmartRTL, GUIDED, LOITER, STABILIZE, POSHOLD, ALTHOLD, AUTO RTL | 33, 17 | BRAKE, AUTOTUNE |
| 3 / 13 / 152 | Simple / Super Simple / heading reset | 84 | AirMode |
| 9 / 166 / 167 | Camera trigger / record video / zoom | 212–217, 163, 27 | Mount1/2 roll/pitch/yaw, mount lock, retract |
| 28, 34–36, 66, 67 | Relay1–6 on/off | 19, 29, 21–23 | Gripper, landing gear, parachute |
| 30 | Lost Copter Sound (buzzer) | 94 | VTX Power |
| 11, 10, 40 | Fence, rangefinder, proximity avoidance enable | 90 | EKF source set (3-pos) |
| 62, 171 | Compass learn, calibrate compasses | 65, 105 | GPS disable, GPS disable yaw |
| 46 | RC override enable | 164 | Pause stream logging |
| 219 | Transmitter Tuning (TUNE knob) | 300–307 | Scripting1–8 |
| 78, 79 | RunCam control / OSD | 151 | TURTLE mode |

**Copter TUNE knob** (`ArduCopter/tuning.cpp`, `radio.cpp`, `Parameters.cpp`):
- The knob channel is the one with `RCx_OPTION = 219` (found at boot by `find_channel_for_option`; the parameter text still
  says "channel 6", but nothing forces channel 6). `TUNE` selects what is tuned; `TUNE_MIN`/`TUNE_MAX` are the values at
  the knob ends. Nothing happens if `TUNE ≤ 0` or both limits are 0, in radio failsafe, or with no RC.
- Value = linear interpolation `TUNE_MIN … TUNE_MAX` over the channel's calibrated range ignoring trim
  (`norm_input_ignore_trim`), called at ~3.3 Hz (comment), logged as **PTUN** (parameter, value, min, max).
- `TUNE` values (4.6.3): 1 Stab Roll/Pitch kP, 4/5/21 Rate Roll/Pitch kP/kI/kD, 46–48 Rate Pitch P/I/D, 49–51 Rate Roll
  P/I/D, 52–54 Rate Pitch/Roll/Yaw FF, 3 Stab Yaw kP, 6/26 Rate Yaw kP/kD, 56 Rate Yaw filter, 55 Motor yaw headroom,
  14 AltHold kP, 7 Throttle rate kP, 34/35/36 Throttle accel kP/kI/kD, 12 Loiter pos kP, 22/28 Velocity XY kP/kI,
  10 WP speed, 25 Acro RP rate, 40 Acro yaw rate, 45 RC feel, 38 Declination, 39 Circle rate, 13 Heli ext gyro,
  58 SysID magnitude, 59 PSC angle max.
- **Not saved.** The value is set in RAM (`set_kP`); a GCS reading shows it; to keep it, write the parameter from the GCS.
- **SITL check (this audit, Copter-4.6.3, `-I9`):** `RC6_OPTION = 219`, `TUNE = 4`, `TUNE_MIN = 0.05`, `TUNE_MAX = 0.25`, reboot;
  `ATC_RAT_RLL_P` = `ATC_RAT_PIT_P` = 0.135. RC6 override 2000 → **0.25**, 1000 → **0.05**, 1500 → **0.15**, 1750 →
  **0.2125** (both axes; 1750 = 0.625 of the 1100–1900 half-range, 0.15 + 0.625 × 0.1). Restart without writing: back to
  0.135. **Trap reproduced:** with no override, SITL's RC6 sits at 1000, and `ATC_RAT_RLL_P` read **0.05** a few seconds after
  boot — a knob left at the bottom drops the gain to `TUNE_MIN` the moment RC is valid, on the ground or in the air. Also:
  RC override is accepted only from `SYSID_MYGCS` (255): an override sent from another system id did nothing.
- 4.7 adds `TUNE2`, `TUNE2_MIN/MAX` and a second knob option `RCx_OPTION = 220` TRANSMITTER_TUNING2 (Copter-4.7.2 `RC_Channel.h`).

**Plane `AP_Tuning`** (`libraries/AP_Tuning/AP_Tuning.cpp`, Plane-4.6.3): `TUNE_CHAN` (knob channel, 0 off),
`TUNE_CHAN_MIN/MAX` 1000/2000, `TUNE_PARAM` (single parameter 1–… or a set 101–110, e.g. 101 Set_RateRollPitch; fixed-wing
50+), `TUNE_SELECTOR` (2-pos, preferably spring-loaded), `TUNE_RANGE` = 2, `TUNE_MODE_REVERT` = 1, `TUNE_ERR_THRESH` = 0.15.
Behaviour: the knob must first cross the **mid-point** ("Tuning: mid-point …"), then moves the value from centre/RANGE to
centre×RANGE (×0.5…×2 by default); selector tap 0.2–2 s → re-centre; hold 2–5 s → next parameter of the set; hold high
**> 5 s** → **save** ("Tuning: Saved"); a flight-mode change **reverts** unsaved values when `TUNE_MODE_REVERT = 1`. Logged.

**Scripting:** `RCx_OPTION 300–307` + `rc:get_aux_cached()`/`find_channel_for_option`; applets with switches: QuikTune
(mid = tune, high = save, low = revert current), `motor_failure_test.lua`, `leds_on_a_switch.lua`, `revert_param.lua`,
`Param_Controller.lua`/`Script_Controller.lua` (4.6.3 `applets/`).

### 4.3 What a lesson needs
Theory: switch thresholds/debounce/on-change, boot-time evaluation, reversal rule, the option table, the mode channel vs
aux channels; TUNE (formula, list, PTUN, no save, how to save), the Plane selector state machine; dangers (knob at end at
boot; combined roll+pitch functions; tuning in a mode that does not use the gain; RC failsafe stops tuning; overrides only from
`SYSID_MYGCS`). Typical uses: field P/D tuning without a laptop; AltHold kP; WP speed on a knob; payload/camera switches.
Lab: §7.1 module `ap-aux-tune`.

---

## 5. Popular questions (57)

Evidence: W/W†/D/S as defined in §1.2. Forum searches (result lists only): PreArm/AHRS/compass —
[Bad AHRS all the time](https://discuss.ardupilot.org/t/bad-ahrs-all-the-time/49890),
[Pre-arm Gyros Inconsistent](https://discuss.ardupilot.org/t/pre-arm-gyros-inconsistent/29910),
[PreArm compass inconsistent](https://discuss.ardupilot.org/t/prearm-compass-inconsistent/95574),
[AHRS errors preventing arming](https://discuss.ardupilot.org/t/ahrs-errors-preventing-arming/108920);
OSD — [DJI O3 and MSP DisplayPort OSD](https://discuss.ardupilot.org/t/dji-air-unit-o3-and-msp-displayport-osd/93549),
[Can't get OSD to work](https://discuss.ardupilot.org/t/cant-get-osd-to-work/129554),
[OSD on Walksnail Avatar Goggles X](https://discuss.ardupilot.org/t/how-to-display-osd-on-walksnail-avatar-goggles-x/145371),
[Kakute F7 OSD from Walksnail](https://discuss.ardupilot.org/t/customer-firmware-options-for-kakute-f7-to-get-osd-from-walksnail/96480);
DShot — [No parameter SERVO_BLH_BDMASK](https://discuss.ardupilot.org/t/no-parameter-servo-blh-bdmask/119677),
[Trouble getting bdshot to work](https://discuss.ardupilot.org/t/trouble-getting-bdshot-to-work/138466),
[BDShot on Matek H743 breaks BLHeli_32 telemetry](https://discuss.ardupilot.org/t/bidirectional-dshot-for-matek-h743-breaks-blheli-32-telemetry-and-buzzer/84042),
[Bi-directional DShot testers wanted](https://discuss.ardupilot.org/t/bi-directional-dshot-testers-wanted/64697).

| # | Question | How common | Short correct answer (4.6) | Course now |
|---|---|---|---|---|
| 1 | Why won't it arm? | W D S | read the `PreArm:` text; `ARMING_CHECK` bits (§3.4); never 0 on a flying aircraft | ~ ap-intro, ap-setup-scratch (no message table) |
| 2 | "Compass not calibrated / inconsistent" | W D | onboard cal outdoors, `COMPASS_CAL_FIT`, external compass priority 1 (`COMPASS_PRIO1_ID`), disable a noisy one (`COMPASS_USEn = 0`) | ✓ ap-intro, ap-setup-scratch |
| 3 | "Bad AHRS" / "Gyros/Accels inconsistent" / "EKF variance" | D | wait for warm-up/EKF, accel cal, `ARMING_ACCTHRESH` 0.75, temperature cal (`INS_TCALn_*`), vibration | ~ ap-ekf |
| 4 | "Throttle below failsafe" / RC not calibrated | W | radio cal; `FS_THR_VALUE` 975 at least 10 µs below RC3 min | ✓ ap-setup-scratch |
| 5 | PreArm "Hardware safety switch" | W† | press safety or `BRD_SAFETY_DEFLT = 0`; `BRD_SAFETY_MASK` | ✗ |
| 6 | Motors/servos dead after DShot; "Chan x to y, …" error | D S | outputs of one timer share protocol/rate; motors on DShot-capable outputs (not IOMCU MAIN without `BRD_IO_DSHOT`); read the boot message (`print_group_setup_error`) and `@SYS/timers.txt` | ~ ap-setup-scratch diag, ap-quadplane |
| 7 | No `SERVO_BLH_BDMASK` / BDShot not working | D S | param exists only on `HAL_WITH_BIDIR_DSHOT` builds — flash the board's `-bdshot` firmware (33 such hwdefs in 4.6.3); `SERVO_BLH_BDMASK`, `SERVO_BLH_POLES`, ESC with BDShot firmware | ✗ |
| 8 | Motor order / Motor Test letters | W | letters clockwise from front-right; Quad X 1 FR, 2 RL, 3 FL, 4 RR | ✓ ap-setup-scratch |
| 9 | Reverse a motor with DShot | W | `SERVO_BLH_RVMASK` or ESC tool | ✓ ap-setup-scratch |
| 10 | ESC calibration (PWM ESCs) | W | `ESC_CALIBRATION = 3` or all-at-once procedure; not for DShot | ✓ ap-setup-scratch |
| 11 | BLHeli passthrough won't connect | W† | DShot protocol set, `SERVO_BLH_AUTO = 1` (or `SERVO_BLH_MASK`), safety off, non-IOMCU outputs, USB; BLHeliSuite32/AM32 configurator; web ESC Configurator "variable" (wiki) | ~ (only `SERVO_BLH_AUTO`) |
| 12 | ESC telemetry (serial wire) | W | `SERIALn_PROTOCOL = 16`, `SERVO_BLH_TRATE` 10 Hz, `ESC` log, `BATT_MONITOR = 9` | ~ f-esc-firmware |
| 13 | Harmonic notch from ESC RPM | W | `INS_HNTCH_ENABLE = 1`, `INS_HNTCH_MODE = 3`, `REF`, `OPTS` | ✓ ap-tuning |
| 14 | ELRS / CRSF receiver | W | `SERIALn_PROTOCOL = 23`, `RC_PROTOCOLS = 512`, `RC_OPTIONS` bits 9/13 | ✓ ap-setup-scratch |
| 15 | RSSI/LQ on OSD | W | `RSSI_TYPE = 3`, `RC_OPTIONS` bit 11 (LQ as RSSI), OSD `LINK_Q`/`RSSI` items, `OSD_W_LQ` | ~ |
| 16 | Six modes on a 3-position switch | W | pair `FLTMODE1/2`, `3/4`, `5/6` | ✓ ap-setup-scratch |
| 17 | Arm on a switch / emergency stop | W | `RCx_OPTION` 153, 31, 165 | ✓ ap-setup-scratch |
| 18 | Which `RCx_OPTION` does X? | W | §4.2 table | ~ |
| 19 | Tune PIDs with a knob (no laptop) | W | `RCx_OPTION = 219` + `TUNE`/`TUNE_MIN/MAX`; not saved; Plane `TUNE_*` | ✗ |
| 20 | No OSD in DJI O3/O4 goggles | D | UART with TX+RX to the air unit, `SERIALn_PROTOCOL = 42`, `OSD_TYPE = 5`, 115200 (auto), `MSP_OPTIONS` bit 0 = 0, goggles' custom OSD on (O3/O4 specifics not on the wiki page — **unverified**) | ~ link-digital-video |
| 21 | Walksnail/HDZero OSD garbled or tiny | W† D | `OSDn_TXT_RES` 1 (50×18) or 2 (60×22); HDZero 0 or 1 only; fonts from the goggles (HDFonts folders) | ✗ |
| 22 | Wrong symbols on DJI | W† | `MSP_OPTIONS` bit 2 (Betaflight fonts) or bit 3 (INAV fonts), `OSD_OPTIONS` bit 5 TranslateArrows | ~ bf-hd-osd-video |
| 23 | Analog OSD: items, several screens | W | `OSD_TYPE = 1`, `OSDn_<ITEM>_EN/X/Y`, `OSD_CHAN` + `OSD_SW_METHOD` + `OSDn_CHAN_MIN/MAX`, MP Onboard OSD editor | ~ |
| 24 | VTX power/pit mode from ArduPilot | W | `VTX_ENABLE = 1`, `SERIALn_PROTOCOL = 37/44`, `VTX_*`, `VTX_OPTIONS`, `RCx_OPTION 94` | ✗ |
| 25 | LED strip (NeoPixel) | W† | `NTF_LED_TYPES` + 256 (bit 8), output `SERVOn_FUNCTION = 120`, `NTF_LED_LEN`, 3.3 V data → diode trick | ✗ |
| 26 | Buzzer silent / lost-model beep | W | board BUZZER pin or `NTF_BUZZ_PIN`, `NTF_BUZZ_TYPES` (bit 1 DShot beacon), `NTF_BUZZ_VOLUME`, `RCx_OPTION 30` | ✗ |
| 27 | Servo for a payload: endpoints, direction, rate | W | `SERVOn_FUNCTION`, `MIN/TRIM/MAX/REVERSED`, `SERVO_RATE` 50 for non-motor outputs | ~ payload-gimbal, bf-servos-pwm |
| 28 | Use a spare output as GPIO / relay | W | `SERVOn_FUNCTION = -1`, `RELAYn_FUNCTION = 1`, `RELAYn_PIN` = the output's GPIO number (board hwdef); `BRD_PWM_COUNT` is gone | ✗ |
| 29 | Camera trigger and survey by distance | W | `CAM1_TYPE` 1/2, `CAM1_SERVO_ON/OFF`, `CAM1_DURATION`, `CAM1_TRIGG_DIST`, `DO_SET_CAM_TRIGG_DIST`, `CAM1_FEEDBAK_PIN` | ~ ap-missions (commands only) |
| 30 | Siyi / Gremsy / Storm32 gimbal | W | `MNT1_TYPE` 8 + `SERIALn_PROTOCOL 8`, 6 + MAVLink2, 4/5/7; `MNT1_DEFLT_MODE` | ~ payload-gimbal (no wiring) |
| 31 | Rangefinder setup | W | `RNGFND1_TYPE`, `ORIENT 25`, `MIN/MAX_CM`, `GNDCLEAR` | ✓ est-alt-sources |
| 32 | Airspeed sensor not used / wrong | W | `ARSPD_TYPE`, **`ARSPD_USE = 1`**, `ARSPD_RATIO`, zero at boot with the pitot covered, `ARSPD_AUTOCAL` | ✗ |
| 33 | Compass calibration does not finish | W D | outdoors, all orientations, `COMPASS_CAL_FIT` | ✓ ap-setup-scratch |
| 34 | Calibrate the compass of a large vehicle | W S | MP Large Vehicle MagCal (`MAV_CMD_FIXED_MAG_CAL_YAW`: known heading + GPS + WMM) then MagFit | ✗ |
| 35 | MagFit from a flight log | W† | WebTools or MAVExplorer → MagFit; offsets first, deviation reduction < 10°; check ATT yaw change < 20° | ✗ |
| 36 | Motor interference on the compass | W | CompassMot, `COMPASS_MOTCT`, `COMPASS_MOTn_*` | ✓ ap-setup-scratch, el-emi |
| 37 | Battery voltage/current calibration | W | formulas, `BATT_VOLT_MULT`, `BATT_AMP_PERVLT`, `BATT_AMP_OFFSET` | ✓ ap-setup-scratch |
| 38 | Two batteries / second monitor | W | `BATT2_MONITOR`, pins, `BATT_MONITOR = 10` + `BATT_SUM_MASK` | ✗ |
| 39 | Battery failsafe thresholds | W | `BATT_LOW/CRT_VOLT`, `_MAH`, `_FS_*_ACT`, `BATT_FS_VOLTSRC` | ✓ ap-setup-scratch, ap-safety-fs |
| 40 | Test RC failsafe | W | TX off on the ground (disarm) and in the air (RTL/Land); `SIM_RC_FAIL` | ✓ |
| 41 | Telemetry lost — what happens? | W | `FS_GCS_ENABLE` 0 by default; with it on, `FS_OPTIONS` bit 4 (default) keeps manual modes | ✓ ap-safety-fs (one error, §7.3 #5) |
| 42 | Geofence setup, polygon, auto-enable | W | `FENCE_*`, MP Plan → Fence, `FENCE_AUTOENABLE` | ~ (circle/alt only) |
| 43 | Rally points | W | MP Plan → Rally, `RALLY_*` | ✗ |
| 44 | "SmartRTL unavailable" | W | buffer `SRTL_POINTS` 300, `SRTL_ACCURACY` 2 m, needs position at arming | ~ ap-safety-fs |
| 45 | Precision landing | W | `PLND_*`, IR-LOCK or `LANDING_TARGET` | ✓ per-landing |
| 46 | Terrain following | W | `TERRAIN_*`, rangefinder | ✓ nav-terrain |
| 47 | What to log for tuning | W S | default 180222 already has PID; add bit 0 Fast Attitude, batch sampler | ✓ ap-logs (with an error, §7.3 #1) |
| 48 | Vibration too high | W | `VIBE` < 30, clipping, mounting | ✓ ap-logs, ap-setup-scratch |
| 49 | Which firmware for my board / F405 limits | W | board name = hwdef; 1 MB boards lose features, custom build server | ~ (build server ✗) |
| 50 | Lua script does not start | W | `SCR_ENABLE`, reboot, `APM/scripts`, heap, flash > 1 MB | ✓ ap-lua |
| 51 | Companion MAVLink and stream rates | W | `SERIALn_PROTOCOL = 2`, `SRn_*` (4.7 `MAVn_*`) | ✓ comp-mavlink, ap-companion |
| 52 | DroneCAN GPS/compass not detected | W | `CAN_P1_DRIVER = 1`, `CAN_D1_PROTOCOL = 1`, `GPS1_TYPE = 9`, termination | ✓ el-dronecan |
| 53 | DroneCAN ESCs | W | `CAN_D1_UC_ESC_BM` | ✓ el-dronecan |
| 54 | Servo frame rate, digital servos | W | `SERVO_RATE` (25–400, default 50), `RC_SPEED` for copter motors, one rate per timer group | ~ |
| 55 | QuadPlane outputs mixed up | — | output map, timer groups | ✓ ap-quadplane |
| 56 | Plane: what happens on RC loss | W | `THR_FAILSAFE`, `FS_SHORT_ACTN/TIMEOUT`, `FS_LONG_ACTN/TIMEOUT` | ✗ |
| 57 | AutoTune result not saved | W | land and disarm with the switch still on | ✓ ap-tuning |

**Totals: 57 — ✓ 26, ~ 17, ✗ 14** (✗: 5, 7, 19, 21, 24, 25, 26, 28, 32, 34, 35, 38, 43, 56).

---

## 6. Hardware integration

Verdict: can a student **connect and configure** it from the course alone — **Yes / Partly / No**.

### 6a. Servos and PWM outputs, timer groups — **Partly**
**Exists:** ap-quadplane «Функции выходов» (Motor1–4 = 33–36, tilt 41/75/76, Elevator 19, Flaperons 24/25) and «Главная
ловушка: мотор на канале сервы» (one protocol and rate per timer; HeeWing incident); ap-setup-scratch step 6 («Выходы одной
таймерной группы должны быть одного типа») and diagnostics (IOMCU MAIN, `BRD_IO_DSHOT`); bf-servos-pwm «INAV и ArduPilot
для сравнения» (`SERVOn_MIN/MAX/TRIM/REVERSED`, `SERVO_RATE` 50); payload-gimbal (6/7/8).
**Missing:** the full `SERVOn_FUNCTION` list (§3.1) and the MP **Servo Output** screen; how to find a board's groups
(board wiki page / hwdef, `@SYS/timers.txt` via MAVFTP, boot error "Chan x to y, <mode>: …"); `RC_SPEED` 490 (copter
PWM motors) vs `SERVO_RATE` 50 (everything else) and that the group runs at the motor rate if they share; GPIO
(`SERVOn_FUNCTION = -1`, `SERVO_GPIO_MASK`; `BRD_PWM_COUNT` gone); RC passthrough (1, 51–66, 140–155); `SERVOn_TRIM`
vs `SERVO_AUTO_TRIM` (Plane); servo power (separate BEC, not the FC 5 V rail) — same gap as in the Betaflight audit §7a.
**Proposal:** new module `ap-outputs` (§7.1 #1). **SITL lab:** set `SERVO9_FUNCTION = 1` (RCPassThru), `SERVO10_FUNCTION = 56`
(RCIN6), `SERVO11_FUNCTION = 135` (fixed trim), `SERVO12_FUNCTION = 10` with `CAM1_TYPE = 1`; move RC6, read
`SERVO_OUTPUT_RAW` (servo9–12) with pymavlink, trigger the camera (`DO_DIGICAM_CONTROL`) and see 1300 µs for 0.1 s;
`SERVO9_REVERSED`, `MIN/MAX` effect. **Железо:** board output table from the board page, `@SYS/timers.txt` downloaded,
plan "4 DShot motors + 2 servos + NeoPixel" into groups, reproduce the boot error by putting a servo on a motor group, fix.

### 6b. RGB LEDs (NeoPixel / ProfiLED) — **No**
**Exists:** nothing for ArduPilot (bf-led-buzzer is Betaflight).
**Missing / exact:** `NTF_LED_TYPES` += 256 (bit 8 NeoPixel; bit 18 NeoPixelRGB if colours swap; bit 9 ProfiLED,
12 ProfiLED_SPI); output `SERVOn_FUNCTION = 120…123` (NeoPixel1–4) or 129–132 (ProfiLED1–3, ProfiLEDClock);
`NTF_LED_LEN` (1–32 per metadata; wiki: up to 44 per string known to work on H7 — **unverified in source**),
`NTF_LED_BRIGHT` 3, `NTF_LED_OVERRIDE` (1 = MAVLink/scripting colour); the whole **timer group switches to LED mode**
(`RCOutput::set_serial_led_num_LEDs` sets the group's `led_mode`), so other outputs of that group are lost; 3.3 V data vs
4.3 V input-high at 5 V → diode in the LED 5 V line (wiki); colour meanings (wiki "NTF LED meaning", not fetched);
scripting `serialLED` + applet `leds_on_a_switch.lua`; SITL `SIM_LED_LAYOUT` (exists in 4.6.3, use **unverified**).
**Proposal:** module `ap-notify` (§7.1 #5) shared with buzzer. **Lab:** SITL: `NTF_LED_TYPES`, `SERVO9_FUNCTION = 120`,
`NTF_LED_LEN = 8`, scripting colour on a switch (`leds_on_a_switch.lua`), verify by script prints / `SIM_LED_LAYOUT`
(mark if not visible); **Железо:** strip on a free group, current at full white measured, diode fix if flicker.

### 6c. Buzzer — **No**
Missing: board buzzer pin (hwdef) or `NTF_BUZZ_PIN`/`NTF_BUZZ_ON_LVL`, `NTF_BUZZ_TYPES` (bit 0 built-in, bit 1 DShot
beacon via ESCs, bit 2 DroneCAN), `NTF_BUZZ_VOLUME` 100, `RCx_OPTION 30` Lost Copter Sound, tune meanings (arming,
failsafe, EKF, battery — wiki "Sounds" page **unverified**), passive vs active buzzer, `notify:play_tune()` (named in ap-lua).
Proposal: in `ap-notify`.

### 6d. Digital video and OSD — **Partly** (two parameters; nothing else)
**Exists:** link-digital-video («ArduPilot: `SERIALn_PROTOCOL = 42`, `OSD_TYPE = 5`»); ap-setup-scratch step 13 (`OSD_TYPE`
1/5, `OSD_CHAN`, `OSDn_ENABLE`, SITL OSD needs SFML `--osd`); bf-hd-osd-video ArduPilot column (42/33, 5/3, `MSP_OPTIONS`
bit 2, 115200).
**Missing / exact (wiki† `common-displayport`, `common-msp-osd-overview-4.2`; source `AP_OSD*.cpp`, `AP_MSP.cpp`):**
- DisplayPort (DJI O3/O4 **(unverified on the wiki)**, Walksnail, HDZero, WTFOS): UART with **both TX and RX**, `SERIALn_PROTOCOL = 42`
  (baud switches to 115 automatically), `OSD_TYPE = 5`, `MSP_OPTIONS` bit 0 = 0 (no telemetry mode), bit 3 for INAV-font goggles;
  **`OSDn_TXT_RES`** 0 = 30×16, 1 = 50×18, 2 = 60×22 per screen (HDZero 0/1 only); fonts live in the goggles (HDFonts/WalkSnail,
  WTFOS msp-osd); UART with DMA on F4/F7 for crowded screens.
- Legacy DJI (Air Unit/Vista without WTFOS): `SERIALn_PROTOCOL = 33` (or 32 telemetry mode), `OSD_TYPE = 3`, `MSP_OPTIONS`
  bit 2 (BTFL fonts), `OSD_OPTIONS` bit 5 TranslateArrows, Custom OSD on in the goggles; panel set fixed by the goggles.
- Second OSD: `OSD_TYPE2` (e.g. analog + DisplayPort) — exists in 4.6.3, use not on the fetched pages.
- Screens and items: 4 screens `OSD1…4_*` with 65 items each (65 `OSD1_*_EN` in 4.6.3 metadata) (`OSDn_<ITEM>_EN/X/Y`, e.g. `OSD1_BAT_VOLT_EN/X/Y`, X 0–59,
  Y 0–21), switching `OSD_CHAN`, `OSD_SW_METHOD` (0 next on change, 1 by PWM ranges `OSDn_CHAN_MIN/MAX`, 2 low→high),
  `OSD_ARM_SCR`/`DSARM_SCR`/`FS_SCR`, warnings `OSD_W_*`, `OSD_UNITS`, `OSD_MSG_TIME`, `OSD_CELL_COUNT`; param screens 5/6;
  MP Config → Onboard OSD drag-and-drop editor.
- Analog: `OSD_TYPE = 1` (MAX7456, often the board default), `OSD_V_OFFSET`/`H_OFFSET` 16/32, `OSD_FONT`.
- Physical: power per air unit, SBUS from DJI goggles → `SERIALn_PROTOCOL = 23` (same as the Betaflight module, **unverified for AP**),
  heat on the bench — reuse bf-hd-osd-video's wiring table.
- VTX control for analog VTX: `VTX_ENABLE`, `SERIALn_PROTOCOL` 37 SmartAudio / 44 Tramp / 29 Crossfire VTX, `VTX_BAND/CHANNEL/
  POWER/MAX_POWER`, `VTX_OPTIONS`, `RCx_OPTION 94` VTX Power; 4.8-dev adds `VTX_TYPES`.
**Proposal:** module `ap-osd-video` (§7.1 #3). **Lab:** SITL first — MAVProxy SITL with `OSD_TYPE = 2` needs an SFML build
(`sim_vehicle.py --osd`; the course already says so) → if not built, a Python layout checker that reads the `.param` file
and draws the 4 screens on a 30×16/50×18/60×22 grid, flags overlaps and off-canvas items (the same idea as
`hd_osd_calc.py`); screen switching tested in SITL by reading `OSD_CHAN` behaviour is not observable without SFML (mark).
**Железо:** DJI/Walksnail/HDZero configs on one FC, `.param` diff, OSD visible, resolution change seen, screen switch on a
3-pos switch, `VTX_*` power change measured on analog.

### 6e. Camera gimbals — **Partly** (parameters yes, wiring no)
**Exists:** payload-gimbal (table `MNT1_*`, `RCx_OPTION 212–214/163`, `SERVOn_FUNCTION 6–8`, `SERIALn_PROTOCOL = 8`,
MAVLink Gimbal v2, SITL lab with servo gimbal). Correct against 4.6.3.
**Missing:** `MNT1_TYPE` values: 0 None, 1 Servo, 2 3DR Solo, 3 Alexmos serial, 4 SToRM32 MAVLink, 5 SToRM32 serial,
6 Gremsy/MAVLink, 7 BrushlessPWM, 8 Siyi, 9 Scripting, 10 Xacti, 11 Viewpro, 12 Topotek, 13 CADDX; 4.7 adds 14 XFRobot.
Defaults (source): `MNT1_DEFLT_MODE` **3** (RC targeting), `MNT1_PITCH_MIN/MAX` −90/20, `MNT1_YAW_MIN` −180, `MNT1_RC_RATE` 0.
Wiring per type (power straight from the pack for brushless gimbals per vendor; UART TX/RX crossed at 115200 for Siyi/Viewpro;
MAVLink2 port for Gremsy; PWM for type 7), the camera's video into the VTX, `CAM1_TYPE = 4` to trigger through the mount,
`MNT1_LEAD_*`, `MNT2_*`. **Proposal:** «Подключение подвеса к железу» block in payload-gimbal (+ `ap-payload` lab, §7.1 #6).

### 6f. Camera trigger — **Partly** (mission commands only)
ap-missions names `DO_DIGICAM_CONTROL`, `DO_SET_CAM_TRIGG_DIST`; per-mapping/per-camera use the commands. Missing: `CAM1_*`
(§3.14), servo vs relay vs MAVLink camera, hot-shoe feedback (`CAM1_FEEDBAK_PIN`, `CAM` vs `TRIG` log messages), `RCx_OPTION 9/166/167`.
**SITL lab:** `CAM1_TYPE = 1`, `SERVO10_FUNCTION = 10`, survey with `DO_SET_CAM_TRIGG_DIST 20`, count `CAM` messages vs flown
distance. Proposal: `ap-payload` (§7.1 #6).

### 6g. Relays — **No**
Missing: `RELAYn_FUNCTION` (0 None, 1 Relay, 3 Parachute, 4 Camera; Plane adds ICE functions **unverified**),
`RELAYn_PIN` (GPIO number of an output set to `SERVOn_FUNCTION = -1`, board-dependent numbering; DroneCAN hardpoints
1000+), `RELAYn_DEFAULT`, `RELAYn_INVERTED`; `RCx_OPTION` 28/34–36/66/67; `DO_SET_RELAY`, `DO_REPEAT_RELAY`; Lua `relay:on()`.
4.6 moved relays to per-instance `RELAYn_*` (old `RELAY_PIN` naming **unverified**). Proposal: in `ap-outputs` (GPIO section).

### 6h. Rangefinder — **Yes** (est-alt-sources, nav-terrain, per-landing). Add: defaults (§3.9), LightWare/Benewake serial
types, `RNGFND1_MAX_CM` must match the sensor, 4.7 metres rename.

### 6i. Airspeed — **No** (for setup)
aero-wing and ap-plane-tuning only say `ARSPD_*` "если есть трубка" and `ARSPD_AUTOCAL`. Missing: types and Plane default
(MS4525 I²C), **`ARSPD_USE = 1`** (default 0), `ARSPD_BUS`, `ARSPD_PIN` (analog), `ARSPD_TUBE_ORDR`, zero offset at boot
(cover the pitot), `ARSPD_RATIO` = 2, in-flight `ARSPD_AUTOCAL` / `RCx_OPTION 91`, preflight check, `ARSPD_OPTIONS`
wind-max failure detection, 2nd sensor. **Proposal:** section in new `ap-setup-plane` (§7.1 #4). **SITL:** Plane SITL default
analog airspeed — compare `ARSP.Airspeed` vs GPS ground speed in no wind, change `ARSPD_RATIO` 2 → 2.5 and see the TECS effect.

### 6j. GPS and compass, incl. large-vehicle MagFit — **Partly**
**Exists:** GPS: nav-rtk, est-gnss (deep). Compass: onboard cal, CompassMot, `COMPASS_USE2` (ap-setup-scratch, el-emi).
**Missing:** `COMPASS_CAL_FIT`, `COMPASS_AUTO_ROT`, priorities `COMPASS_PRIOn_ID`, `COMPASS_ORIENT` for a mast compass,
learning (`COMPASS_LEARN`, option 62), **Large Vehicle MagCal** (MP Compass → button; `MAV_CMD_FIXED_MAG_CAL_YAW`, source),
**MagFit** (WebTools or MAVExplorer; offsets first, then DIA/ODI/MOT; accept if heading deviation reduction leaves < 10°,
investigate if ATT yaw changes > 20° — wiki†). These matter for the course's X8 (ap-heavy) where rotating the aircraft
is impractical. **Proposal:** «Компас на большом аппарате» section in ap-heavy + compass section in `ap-sensors` (§7.1 #2).
**SITL lab:** set `SIM_MAG1_OFS_X = 300` (wrong offsets), fly a box, run MagFit on the `.BIN` in MAVExplorer, load the
result, fly again: heading error before/after; `MAV_CMD_FIXED_MAG_CAL_YAW` sent with pymavlink in SITL.

### 6k. Telemetry radios — **Yes** (link-telemetry-radios: `SERIALn_PROTOCOL = 2`, `SERIALn_BAUD`, `RSSI_TYPE = 5`, stream
rates incl. 4.7 `MAVn_*` index note). Add `BRD_SERn_RTSCTS` and the MP SiK Radio screen.

### 6l. ESC telemetry and BLHeli passthrough — **Partly**
**Exists:** f-esc-firmware (`SERVO_BLH_BDMASK`, `SERVO_BLH_POLES`, `ESC` log, `INS_HNTCH_MODE = 3`), ap-setup-scratch
(`SERVO_DSHOT_ESC`, `SERVO_BLH_AUTO`, `SERVO_BLH_RVMASK`, SITL has no BLHeli), ap-lua (`esc_telem:` example, `SIM_ESC_TELEM`).
**Missing:** serial ESC telemetry wire (`SERIALn_PROTOCOL = 16`, `SERVO_BLH_TRATE`), EDT (`SERVO_DSHOT_ESC` 3/4), `-bdshot`
firmware variants and why the param can be missing, BDShot vs IOMCU (`BRD_IO_DSHOT`, `HAL_WITH_IO_MCU_BIDIR_DSHOT`), ESC as
battery monitor (`BATT_MONITOR = 9`), `ESC_TLM_MAV_OFS`, passthrough prerequisites (§5 #11), BLHeliSuite32 10.0 bug warning (wiki).
**Proposal:** in `ap-outputs`. **SITL:** `SIM_ESC_TELEM = 1` → `ESC` messages and `esc_telem` rpm; real board for passthrough.

### 6m. DroneCAN peripherals — **Yes** (el-dronecan; correct). Add `CAN_D1_UC_SRV_BM`, `CAN_D1_UC_OPTION`, `CAN_D1_UC_NODE`,
SITL CAN (`SIM_CAN_TYPE1`, `sim_vehicle.py --can-peripherals` — option name **unverified**).

### 6n. Battery monitors (multiple) — **Partly** (one analog monitor in depth; nothing on BATT2…BATTG, sum, ESC, SMBus,
DroneCAN beyond one row). Add to ap-setup-scratch step 10 or `ap-sensors`; SITL lab: `BATT2_MONITOR = 4` on the SITL's
second analog pins **(pin numbers unverified)** or `BATT2_MONITOR = 9` with `SIM_ESC_TELEM`.

### 6o. Relays/PINIO-like switching, RunCam, landing gear, gripper, winch — covered only by the gripper row in payload-gimbal.
C except gripper (B). Fold into `ap-payload`.

### 6p. Summary
New modules proposed for hardware: `ap-outputs` (6a, 6g, 6l), `ap-notify` (6b, 6c), `ap-osd-video` (6d), `ap-sensors`
(6i compass part of 6j, 6n), `ap-payload` (6e, 6f, 6o), `ap-setup-plane` (6i Plane side, Plane failsafes).

---

## 7. Proposed changes

### 7.1 New modules (ordered by value)

All follow `content/article-template.md` (summary, theory, practice ≥ 150 words with lab and acceptance line, diagnostics,
checklist, references ≥ 2, quiz 8, glossary, diagram). SITL first (Copter-4.6.3 build, 4.7 names in brackets), then
«Переход на реальное железо». New ids go to `data/curriculum.json`, `data/content-manifest.json`, `data/glossary.json`.

| # | id | Title (ru) | Pri | Scope | Lab |
|---|---|---|---|---|---|
| 1 | `ap-outputs` | «Выходы ArduPilot: SERVOn_FUNCTION, таймерные группы, DShot/BDShot, BLHeli, сервы, GPIO и реле» | A | §3.1, §6a, §6g, §6l: function list, MP Servo Output / QGC Servo Outputs, groups and `@SYS/timers.txt`, `RC_SPEED` vs `SERVO_RATE`, DShot/EDT/BDShot and `-bdshot` firmware, IOMCU, passthrough, ESC telemetry, safety switch, GPIO/relays, `BRD_PWM_COUNT` legacy | **SITL:** RCPassThru / RCIN6 / fixed-trim / camera-trigger outputs read from `SERVO_OUTPUT_RAW`; relay on a GPIO output toggled by `RCx_OPTION 28` and `DO_SET_RELAY` (read state back over MAVLink — method to be confirmed); `SIM_ESC_TELEM` ESC log. **Железо:** group plan for 4 motors + 2 servos + LED, boot error reproduced and fixed, BDShot error rate in `ESC`, passthrough with BLHeliSuite32/AM32 |
| 2 | `ap-aux-tune` | «Тумблеры и крутилки: RCx_OPTION, TUNE и подстройка в полёте» | A | §4 complete: thresholds, debounce, boot evaluation, option table, Copter TUNE (list, formula, PTUN, no save), Plane `TUNE_*` selector logic, scripting switches, QuikTune switch, dangers | **SITL:** reproduce §4.2 exactly (`RC6_OPTION 219`, `TUNE 4`, 0.05/0.25 → 0.25/0.05/0.15/0.2125, restart → 0.135, knob-low trap), then `TUNE = 14` AltHold kP in flight with a log `PTUN`; aux thresholds by override 1190/1210/1790/1810. **Железо:** pot/slider on CH6–CH8, hover, tune `Rate Roll/Pitch kD` in a narrow range (±20 %), write from GCS, `.param` diff |
| 3 | `ap-osd-video` | «OSD и видео в ArduPilot: MAX7456, MSP DisplayPort (DJI, Walksnail, HDZero), экраны OSDn, VTX» | A | §6d | **SITL/desk:** SFML OSD if built; otherwise layout checker on `.param` for 4 screens and three resolutions; legacy DJI vs DisplayPort param sets compared. **Железо:** per system, screens on a switch, resolution, fonts, VTX power |
| 4 | `ap-setup-plane` | «ArduPlane с нуля: сервы, рули, airspeed, failsafe крыла» (already listed as optional in COURSE-PLAN-STAGE6 §2.8) | A | Plane outputs (4/19/21/70/77/78/79/80), direction checks in FBWA, `SERVO_AUTO_TRIM`, `ARSPD_*` incl. `ARSPD_USE`, `THR_FAILSAFE`/`FS_SHORT_*`/`FS_LONG_*`, Plane `ARMING_*`, takeoff mode basics, Plane TUNE | **SITL:** `sim_vehicle.py -v ArduPlane`; servo directions from `SERVO_OUTPUT_RAW` vs stick and vs attitude (FBWA), RC loss with `SIM_RC_FAIL` → short/long actions timeline, airspeed ratio change. **Железо:** surface direction table, CG check (aero-stability), hand launch |
| 5 | `ap-notify` | «Светодиоды и пищалка в ArduPilot: NTF_*, NeoPixel/ProfiLED, buzzer, DShot-маяк» | B | §6b, §6c, LED colour/tone meanings, scripting LEDs | **SITL:** LED via script + `SIM_LED_LAYOUT` (check), tunes via `notify:play_tune`. **Железо:** strip on a free group, current measured, diode fix, buzzer on a switch, DShot beacon |
| 6 | `ap-payload` | «Полезная нагрузка на железе: камера, реле, подвес, сброс — проводка и параметры» | B | §6e/6f/6g/6o: `CAM1_*`, `MNT1_TYPE` list and wiring, `RELAYn_*`, gripper/winch, feedback pin | **SITL:** survey with distance trigger and `CAM` count; servo gimbal (exists in payload-gimbal) + mount retract; gripper release. **Железо:** Siyi/Storm32 wiring, hot-shoe feedback |
| 7 | `ap-sensors` | «Датчики ArduPilot на столе: компас (MagFit, Large Vehicle), airspeed, несколько АКБ» | B | §3.7, §6j (compass), §6n | **SITL:** MagFit before/after with `SIM_MAG1_OFS_X = 300`; `MAV_CMD_FIXED_MAG_CAL_YAW`; second battery monitor. **Железо:** mast compass orientation via `COMPASS_AUTO_ROT`, large-vehicle cal on the X8 |

### 7.2 Additions to existing modules (ordered by value)

1. **ap-setup-scratch** — step 6: `SERVO_DSHOT_ESC` 3/4 (EDT), `-bdshot` firmware and the missing-`SERVO_BLH_BDMASK` case,
   `RC_SPEED`; step 7: MP **Servo Output** screen; step 9: `COMPASS_CAL_FIT`, `COMPASS_AUTO_ROT`; step 11: `ARMING_CHECK` bit
   table and the PreArm-message table (top 15 messages → cause → fix); step 13: `OSDn_TXT_RES`, `MSP_OPTIONS`; note that SITL
   values `RC1_MIN/MAX` 1000/2000 and `FRAME_TYPE 0` come from `copter.parm`, firmware defaults are 1100/1900 and 1.
2. **ap-safety-fs** — fix `FS_OPTIONS` (§7.3 #5); add rally points (`RALLY_*`, MP Plan → Rally), `FENCE_AUTOENABLE`,
   `FENCE_ALT_MIN`, polygon fences, `SRTL_ACCURACY`, dead-reckoning defaults; a Plane failsafe table (or link to
   `ap-setup-plane`).
3. **ap-logs** — fix the `PID` sentence (§7.3 #1), add a `LOG_BITMASK` bit table with the default 180222 decoded, bit 0
   for loop-rate `RATE`/`ATT`, `LOG_DISARMED` 2/3, WebTools.
4. **ap-quadplane** — add `Q_TILT_ENABLE = 1` as the first tilt step (§7.3 #3); remove `PTCH2SRV_*/RLL2SRV_*` (§7.3 #2).
5. **ap-heavy** — «Компас на большом аппарате»: Large Vehicle MagCal + MagFit, `COMPASS_PRIO*`, mast orientation.
6. **ap-intro** — fix version naming in practice (§7.3 #8), flash rule for scripting (§7.3 #6), add the hidden-until-enabled
   rule, a table "4.6 name → 4.7 name" from §1.3 (it is spread across modules now), custom firmware build server.
7. **ap-lua** — applet list fix (§7.3 #7), add `leds_on_a_switch.lua`, `revert_param.lua`, `Param_Controller.lua`.
8. **payload-gimbal** — `MNT1_TYPE` full list with the 4.7 addition, `MNT1_DEFLT_MODE` default 3, wiring per type, `CAM1_TYPE = 4`.
9. **bf-hd-osd-video** — ArduPilot column: grid row (§7.3 #9); **link-digital-video** — `OSDn_TXT_RES`, `MSP_OPTIONS` bits,
   legacy 33 vs 42, `VTX_*` for analog.
10. **el-dronecan** — `CAN_D1_UC_SRV_BM`, `CAN_D1_UC_OPTION`, `CAN_D1_UC_NODE`; **f-esc-firmware** — ArduPilot passthrough
    prerequisites and EDT.
11. **content/pages/setup-cards.html** (ArduPilot card) — add rows Servo Output, OSD resolution, LEDs, aux switches/TUNE,
    compass fit, airspeed use (not checked line by line in this audit).

With 7.1 and 7.2, all A/B mechanisms in §2, all A/B parameters in §3 and 57/57 questions in §5 would be answered.

### 7.3 Factual errors and outdated statements in existing modules

| # | Module, place | Quote | Problem | Source |
|---|---|---|---|---|
| 1 | ap-logs, theory «Что писать в LOG_BITMASK» | "для тюнинга добавить `PID` (сообщения `PIDR/PIDP/PIDY` …)" | `PID` (bit 12) is **already in the default** 180222 (bits 1–13, 15, 17). What tuning needs on top is bit 0 Fast Attitude (loop-rate `ATT`/`RATE`), plus Raw IMU / batch sampling | `ArduCopter/config.h` `DEFAULT_LOG_BITMASK`; SITL dump `LOG_BITMASK = 180222` |
| 2 | ap-quadplane, «Переходы…» VTOL-контур | "TECS и `PTCH2SRV_*`/`RLL2SRV_*` — для крыла" | These names do not exist in Plane 4.6.3; the fixed-wing rate loops are `PTCH_RATE_*`/`RLL_RATE_*` (+ `YAW_RATE_*`). Version of the rename **unverified** (4.0-era) | Plane-4.6.3 metadata (`PTCH2SRV_P` absent, `PTCH_RATE_P` present) |
| 3 | ap-quadplane, «Конфигурация QuadPlane-tiltrotor» | list starts with `Q_TILT_TYPE`, `Q_TILT_MASK`… | Omission: **`Q_TILT_ENABLE = 1`** is required; it is an enable-flag parameter (default 0), and the other `Q_TILT_*` are hidden/inactive without it. Defaults worth quoting: `Q_TILT_MAX` 45 (matches the module), `Q_TILT_RATE_UP` 40 °/s, `Q_TILT_RATE_DN` 0 (0 = use `Q_TILT_RATE_UP`, per its @Description) | Plane-4.6.3 `ArduPlane/tiltrotor.cpp` `AP_GROUPINFO_FLAGS("ENABLE", …, AP_PARAM_FLAG_ENABLE)` |
| 4 | nav-rtk, theory and practice (lines with "max(GPA.HAcc, EK3_GPS_P_NSE)²" and "упрётся в `EK3_GPS_P_NSE = 0.5`") | `EK3_GPS_P_NSE` | No such parameter in 4.6.3/4.7.2/master. The GPS horizontal position noise is **`EK3_POSNE_M_NSE`** (0.5 m); velocity `EK3_VELNE_M_NSE` 0.3, `EK3_VELD_M_NSE` 0.5. The value 0.5 is right, the name is wrong | 4.6.3 metadata (`EK3_*_NSE` list) |
| 5 | ap-safety-fs, practice step 1 (and diagnostics) | "`FS_OPTIONS` = 0 без разрешения BVLOS" | Default is **16** (bit 4 "continue in pilot-controlled modes on GCS failsafe"). Setting 0 removes that bit, so a telemetry dropout with `FS_GCS_ENABLE` on would RTL a manually flown copter. Advice should be: leave bits 0–2 off without authorisation, keep bit 4 | 4.6.3 metadata / SITL `FS_OPTIONS = 16` |
| 6 | ap-intro «Требования к железу», diagnostics; ap-lua theory | "Lua-скрипты требуют минимум 2 МБ флеша и не работают на F4" | Scripting is compiled when `BOARD_FLASH_SIZE > 1024` KB; 2 MB F427/F429 boards (fmuv3/Pixhawk1-class, CubeBlack) run Lua. The 1 MB **F405** boards cannot. Say "1 МБ флеша (почти все F405) — без Lua" | `libraries/AP_Scripting/AP_Scripting_config.h` |
| 7 | ap-lua, «Applets как учебник» | "`crsf-calibrate.lua`" | Not in 4.6.3 `applets/` (present in 4.7.2 and master) — mark as 4.7+ | `libraries/AP_Scripting/applets/` at the three trees |
| 8 | ap-intro, practice step 2 and «Порядок первой настройки»; ap-safety-fs | "найди `FRAME_CLASS`, `FRAME_TYPE`, `ARMING_SKIPCHK`…"; "`RTL_ALT_M`" | The course's SITL is 4.6.3, where these are `ARMING_CHECK` and `RTL_ALT` (cm); ap-setup-scratch uses the 4.6 names. A student following ap-intro in the course SITL will not find the parameter. Also «Разобранный пример»: "`ARMING_SKIPCHK` сообщает причину текстом" — the reason is in the `PreArm:` STATUSTEXT; the parameter only selects skipped checks | Copter-4.6.3 vs 4.7.2 metadata |
| 9 | bf-hd-osd-video, table «INAV и ArduPilot — коротко», row «Сетка» | ArduPilot: "от очков; `MSP_OPTIONS` бит 2 — шрифт Betaflight" | ArduPilot sets the DisplayPort grid itself per screen with `OSDn_TXT_RES` (0 30×16 default, 1 50×18, 2 60×22; HDZero 0/1 only). With the default 0 an HD system shows the SD grid. `MSP_OPTIONS` bit 2 is for the legacy DJI protocol 33; for DisplayPort the wiki recommends bit 0 = 0 and bit 3 only for INAV-font goggles | `AP_OSD_Screen.cpp` `TXT_RES` default 0; wiki† `common-displayport` |
| 10 | ap-setup-scratch, step 5 | "`RC1..8_MIN/MAX` = 1000/2000 в стандартных параметрах" | True for `sim_vehicle.py` (`copter.parm`), not for the firmware (default 1100/1900). Clarify "в параметрах SITL по умолчанию" | `default_params/copter.parm`; 4.6.3 SITL with empty defaults |
| 11 | ap-setup-scratch, step 6 | "`SERVO_BLH_AUTO = 1` (passthrough для BLHeliSuite/ESC Configurator …)" | Wiki: web ESC Configurator needs ≥ 4.5 and is "variable" over ArduPilot; the listed tools are BLHeliSuite32, AM32 Configurator, BLHeliSuite, JESC; passthrough needs DShot set, safety off, non-IOMCU outputs. Imprecise, not wrong | wiki† `common-blheli32-passthru` |
| 12 | ap-setup-scratch, step 7 / checklist | "`COMPASS_USE2 = 0` … если он [внутренний] мешает" (also ap-intro diagnostics) | Since compass priorities, index 2 is **priority 2**, which is not necessarily the internal compass; check `COMPASS_PRIOn_ID`/device list first. Clarification | 4.6.3 metadata `COMPASS_PRIO1_ID`, `COMPASS_USE2` |

No errors found in: ap-safety-fs failsafe action tables (all values of `FS_THR_ENABLE`, `FS_GCS_ENABLE`, `BATT_FS_*_ACT`,
`FS_EKF_ACTION`, `FENCE_ACTION`, `FS_OPTIONS` bit meanings match 4.6.3), ap-setup-scratch numbers checked here (`RC_OPTIONS`
8736, `RC_PROTOCOLS` 512, protocol numbers 2/5/16/23/42, `MOT_THST_HOVER` 0.125–0.6875 / 0.35, `MOT_SPIN_ARM/MIN` 0.10/0.15,
`MOT_THST_EXPO` 0.65, `MOT_HOVER_LEARN` 2, `ESC_CALIBRATION` 3, `SERVO_BLH_POLES` 14, `RC_OVERRIDE_TIME` 3, Quad X order),
ap-ekf (`EK3_SRC1_YAW` 1/2/3/8, `ERR Subsys 11 ECode 2` GPS glitch), el-dronecan (`GPS_TYPE` → `GPS1_TYPE` in 4.6 verified
against Copter-4.5.7), comp-mavlink/link-telemetry-radios (`SRn` → `MAVn+1` verified in 4.7.2 `GCS.cpp`), ap-intro 4.7 rename
list and date (4.7.0 tag 2026-07-21), payload-gimbal `MNT1_*` and option numbers, ap-lua `esc_telem:get_temperature`
(centi-degrees, `AP_ESC_Telem.h`), ap-plane-tuning (`AUTOTUNE_LEVEL` 6, options 107/180 exist in Plane 4.6.3).
`names_check.py` found no other non-existent ArduPilot parameter names in the course (MAVLink message/command names and
PX4 names excluded).

---

## Appendix — counts

- Copter 4.6.3 parameter metadata: **4775 names / 317 groups**; **2356 templates**, **1762** without `SIM_*` and applet params;
  named in the AP track **161**, anywhere **348** (upper bound). SITL firmware-default dump: 1378 visible parameters.
- 4.6.3 → 4.7.2: −101 / +232 templates; 4.7.2 → master (4.8.0-dev): −12 / +30.
- `RCx_OPTION`: 119 values in Copter 4.6.3 (+29 Plane-only) — ≈ 20 named in the course, 0 explained as a system.
  `SERVOn_FUNCTION`: 108 values in Copter (+24 Plane-only) — ≈ 15 named.
- Mechanisms (§2): 43 rows — ✓ 26, ~ 10, ✗ 7.
- Popular questions: **57** — ✓ 26, ~ 17, ✗ 14.
- Hardware topics (§6, 15 rows 6a–6o): Yes 3 (rangefinder, telemetry radios, DroneCAN), Partly 7 (servos/outputs,
  digital video/OSD, gimbals, camera trigger, GPS/compass, ESC telemetry, battery monitors), No 5 (RGB LEDs, buzzer,
  relays, airspeed, RunCam/landing gear/winch — only the gripper is mentioned).
- Factual problems flagged: 12 (9 errors or misleading omissions, #1–#9; 3 clarifications, #10–#12); SITL experiment: 1 (TUNE knob).
