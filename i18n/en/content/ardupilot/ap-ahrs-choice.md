---
id: ap-ahrs-choice
title: "EKF3, EKF2 or DCM: how ArduPilot estimates attitude and position, and what to choose"
level: L3
readingTime: 55 min
firmware: ArduPilot 4.7 (checked against 4.7.3; the lab was captured on SITL 4.7.2)
status: published
added: 2026-11-23
tags:
  - AHRS
  - EKF3
  - DCM
  - EK3_SRC
  - GSF
  - lane switching
  - dead reckoning
related:
  - ap-ekf
  - est-kalman
  - nav-resilience
  - per-visual-nav
  - ap-sensors
  - nav-indoor
  - est-gnss
  - est-alt-sources
  - est-attitude
  - ap-safety-fs
  - ap-quadplane
  - ap-logs
next:
  - est-alt-sources
source: content/ardupilot/ap-ahrs-choice.md
source_hash: 6e0b036af001
---

## summary
In ArduPilot the question "where am I and which way am I pointing" is answered not by one filter but by the `AP_AHRS` front end with several backends: DCM, EKF3, EKF2, an external AHRS and the simulator. This module works out which of them actually flies the vehicle, when the firmware falls back to DCM by itself, whether EKF2 is still alive, how the EKF3 cores work, the source sets `EK3_SRC1..3_*`, yaw without a compass (GSF), airspeed and wind on a plane, the EKF failsafe, and the messages the pilot sees. The main result is a rule for choosing the estimator and the sources for seven typical vehicles, and a decision tree for when the EKF misbehaves. The lab: seven experiments in SITL ArduCopter and ArduPlane 4.7.2 with real output: GPS loss in Loiter, a switch to optical flow, an IMU failure, a copter with no compass, and a plane with no GPS in wind, with and without an airspeed sensor.

## theory
### AHRS in ArduPilot: one front end, several backends
The control loops do not ask EKF3 directly. They take attitude, velocity and position from the `AP_AHRS` object (`libraries/AP_AHRS`), which decides on every loop whose answer to return. That choice is called the active backend (`_active_EKF_type()`), and a change of it shows in the GCS as the message `AHRS: EKF3 active` or `AHRS: DCM active`.

| Backend | What it is | Where it exists in 4.7.2 | How to select it | Log |
|---|---|---|---|---|
| DCM | a complementary filter on a rotation matrix (`est-attitude`) plus position from GPS or dead reckoning | everywhere, always computed | `AHRS_EKF_TYPE = 0` (Plane and Rover only) or the automatic fallback | `AHR2`, when an EKF is active |
| EKF3 | an extended Kalman filter with 24 states (`est-kalman`) | everywhere | `AHRS_EKF_TYPE = 3` (the default) | `XKF1…XKF5`, `XKFS`, `XKQ`, `XKY0` |
| EKF2 | the previous generation of the filter | only SITL and custom build server builds with the EKF2 option | `AHRS_EKF_TYPE = 2`, `EK2_ENABLE = 1` | `NKF1…NKF5`, `NKQ` |
| External AHRS | a ready-made INS (VectorNav, MicroStrain, InertialLabs, SBG, Trimble, SensAItion, and since 4.7.3 Aeron PLX3 = 10; `EAHRS_TYPE`) | on boards with the driver | `AHRS_EKF_TYPE = 11` | the driver's messages |
| SIM | the ideal attitude from the simulator | SITL only | `AHRS_EKF_TYPE = 10` (new in 4.7) | — |

Three important consequences. First, DCM is updated on every loop whatever is selected (`AP_AHRS::update()` calls `update_DCM()` unconditionally), so it is always ready to take over. Second, the `AHR2` log message holds the "second" estimator: DCM when EKF3 is active, and EKF3 when the fallback to DCM has triggered with `AHRS_EKF_TYPE = 3` (with `AHRS_EKF_TYPE = 0` there are no `AHR2` lines); comparing `ATT` and `AHR2` is the first check of whether the primary one is lying. Third, EKF3 runs even when it is not active (with `EK3_ENABLE = 1`): a plane on DCM still logs the full `XKF*`.

### AHRS_EKF_TYPE: what is allowed on which vehicle
The parameter values in 4.7.3 (the same as in 4.7.2): 0 Disabled (which means DCM), 2 EKF2, 3 EKF3, 10 Sim, 11 ExternalAHRS. The value 1 (EKF1) was removed long ago: with it the board reports the config error `EKF1 not available`.

- **Copter, Heli, Sub.** The `AP_AHRS` constructor sets the flag `FLAG_ALWAYS_USE_EKF` for them: they cannot fly on DCM. The firmware silently turns `AHRS_EKF_TYPE = 0` into an EKF (EKF2 if it is compiled in, otherwise EKF3), but the pre-arm check compares the stored value with the actual one and refuses to arm: `PreArm: AHRS: not using configured AHRS type` (verified in SITL, step 2). On a copter DCM works only for the first seconds after boot, until EKF3 has started, and when EKF3 reports filter faults (`getFilterFaults` ≠ 0).
- **Plane and Rover.** `AHRS_EKF_TYPE = 0` is a legitimate configuration: the vehicle runs on DCM, and position-controlled modes take the position straight from GPS. That is how the compass-less HeeWing from `ap-ekf` flew. The price: no variances, no innovation gates, no dead reckoning on airspeed with a wind estimate, and lower accuracy during GPS glitches.
- **Boards with Remote ID.** The `defaults.parm` of the `*-ODID` builds has `AHRS_EKF_TYPE 3 @READONLY`: you cannot change the estimator on them.

### EKF2 in 4.7: an honest verdict
`AP_AHRS_config.h` has `HAL_NAVEKF2_AVAILABLE 0` by default, with the comment "compiled out by default in 4.5". The Copter 4.5.0-beta1 release notes say "EKF2 removed (can be re-enabled with Custom build server)". No board in `libraries/AP_HAL_ChibiOS/hwdef` of 4.7.2 enables it; only the SITL waf configuration does (`-DHAL_NAVEKF2_AVAILABLE=1`), plus the `EKF2` option in `build_options.py` for custom.ardupilot.org. If you set `AHRS_EKF_TYPE = 2` on standard firmware, `AP_AHRS::init()` quietly replaces it with 3 on the next boot (in memory, without writing the parameter); until the reboot the pre-arm check answers `not using configured AHRS type`. The `EK2_*` parameters are still visible in the documentation and in the pdef, which is no sign that the filter is on the board.

The verdict: on 4.7 EKF2 is not a choice but a museum piece. You need it only to read an old log (`NKF*`) or to compare filters in SITL. In SITL it does work: in our Plane run the log had `EKF2 IMU0 is using GPS` next to EKF3. Yaw without a compass, source sets, the copter's drag-based wind estimate, external navigation with `reset_counter`: all of that is developed in EKF3, and the source set switch (`set_posvelyaw_source_set`) in `AP_AHRS` calls EKF3 only.

### DCM: what it can do and when the firmware falls back to it
DCM is a complementary filter: the gyro is integrated into a rotation matrix, roll and pitch are pulled toward the accelerometer (`AHRS_RP_P` = 0.2), and yaw toward the compass or GPS (`AHRS_YAW_P` = 0.2). Centripetal acceleration in a turn is compensated from GPS velocity (`AHRS_GPS_GAIN` = 1.0, with at least `AHRS_GPS_MINSATS` = 6 satellites). Yaw for a vehicle that flies forward comes from the compass, but if the compass heading differs from the GPS heading by more than 45° for longer than 2 s at a speed of 3 m/s or more and a wind below 80 % of the ground speed, DCM switches to the GPS heading, a guard against taking off with a bad compass. DCM takes position from GPS (`AHRS_GPS_USE`: 0 Disabled, 1 position, 2 position and height), and with no GPS from dead reckoning on airspeed and the wind estimated in turns.

The automatic fallback to DCM exists only on planes (VTOL included) and ground vehicles (`_active_EKF_type()`, the `FIXED_WING`/`GROUND` branch). First of all, before any options: if EKF3 is unhealthy (`EKF3.healthy()` = false: filter faults, all three test ratios of velocity, position and height above 1, or the first second after start), DCM is active. Then the conditions in the order they are tested:

1. EKF3 gives no attitude (a ground vehicle needs nothing more; a flying one also needs vertical velocity and height): DCM, no alternatives. The reverse case: if DCM has no yaw source (the compass is not used) and the vehicle is not flying forward, EKF3 stays.
2. The fallback is disabled by an `AHRS_OPTIONS` bit: bit 0 DisableDCMFallbackFW (fly-forward flight) or bit 1 DisableDCMFallbackVTOL (hover), so EKF3 stays. This does not apply to an unhealthy EKF3 or to item 1.
3. The vehicle is armed, the GPS has a 3D fix, EKF3 is configured to use GPS (and `AHRS_GPS_USE` ≠ 0), but it is not fusing GPS or has lost its absolute position: DCM (DCM runs on the raw GPS).
4. The vehicle is armed and EKF3 is in constant position mode (`const_pos_mode`): DCM.
5. EKF3 has no horizontal velocity or position: DCM; the exception: the compass is not used, the GPS has a 3D fix and is judged good, and the speed is below 2 m/s, which lets a compass-less plane arm before its yaw is aligned.

The default `AHRS_OPTIONS`: 0 on Plane, 3 on Rover (both fallbacks disabled), 16 on Sub. So on 4.7 Rover by default does not fall back to DCM on a loss of navigation (items 3–5), only on an unhealthy EKF3 and on item 1, while Plane falls back in every case. The pilot sees the fallback as the line `AHRS: DCM active` and the return as `AHRS: EKF3 active`; in SITL Plane with no airspeed sensor, after GPS was switched off this pair flashed by within one loop, 20 ms (step 7). There is no separate "DCM failsafe": position-controlled modes keep working on whatever DCM provides.

### EKF3 from the inside, for beginners
The filter math is in `est-kalman`; here is how it maps onto parameters. Every IMU step advances the prediction (24 states: quaternion, NED velocity and position, gyro and accelerometer bias, earth and body magnetic field, NE wind). Measurements arrive late and are fused "in the past", at the delayed time horizon. Before fusion each one goes through an innovation test:

test ratio = y² / ((G/100)² · S),

where y is the innovation (the difference between prediction and measurement; its sign does not matter for the test), S is its variance (prediction uncertainty plus measurement noise), and G is the gate parameter in percent of σ. For GPS position the numerator and S are sums over north and east (`AP_NavEKF3_PosVelFusion.cpp`). A ratio below 1 means the measurement is accepted, above 1 rejected. `XKF4` and `EKF_STATUS_REPORT` (the "variances" in the GCS) carry its square root: `SP` = |y| / ((G/100)·√S). With G = 500 a value of 1.0 means an innovation of 5σ.

| Measurement | Gate | Default | Measurement noise | Default Copter / Plane |
|---|---|---|---|---|
| GPS velocity | `EK3_VEL_I_GATE` | 500 | `EK3_VELNE_M_NSE` | 0.3 / 0.5 m/s |
| GPS position | `EK3_POS_I_GATE` | 500 | `EK3_POSNE_M_NSE` | 0.5 / 0.5 m |
| Height (baro, rangefinder as the height source) | `EK3_HGT_I_GATE` | 500 | `EK3_ALT_M_NSE` | 2.0 / 3.0 m |
| Compass (3 axes) | `EK3_MAG_I_GATE` | 300 | `EK3_MAG_M_NSE` | 0.05 / 0.05 G |
| Yaw (GPS yaw, external) | `EK3_YAW_I_GATE` | 300 | `EK3_YAW_M_NSE` | 0.5 rad |
| Airspeed | `EK3_EAS_I_GATE` | 400 | `EK3_EAS_M_NSE` | 1.4 m/s |
| Rangefinder | `EK3_RNG_I_GATE` | 500 | `EK3_RNG_M_NSE` | 0.5 m |
| Optical flow | `EK3_FLOW_I_GATE` | 300 / 500 | `EK3_FLOW_M_NSE` | 0.25 / 0.15 rad/s |
| Beacons | `EK3_BCN_I_GTE` | 500 | `EK3_BCN_M_NSE` | 1.0 m |

Two more mechanisms work behind the gates. `EK3_GLITCH_RAD` (25 m): while GPS is being rejected by the gate, the position uncertainty grows, and when its σ (the root of the sum of the north and east variances) exceeds this radius, the filter stops arguing and resets its position to GPS (the same happens on a timeout). And the timeouts: with no position measurements for 7 s (10 s if velocity is available) the position is declared lost, and with no source that constrains tilt for 15 s the filter enters constant position mode, with `EKF3 IMU0 stopped aiding` in the GCS. Why so fast: a tilt error δθ turns part of g into a false horizontal acceleration g · sin δθ, and uncorrected the position drifts by ½ · g · sin δθ · t²; at 0.5° that is 4.3 m in 10 s.

### Cores (lanes): EK3_IMU_MASK, EK3_PRIMARY and switching
EKF3 starts a separate core for each IMU selected in `EK3_IMU_MASK` (default 3, the first two; bits 0–5 for six IMUs). The mask is trimmed to the actual number of accelerometers; each core needs memory, and a shortage gives `EKF3 not enough memory`. `EK3_PRIMARY` (0–2, default 0) is an index in the mask, not an IMU number: while the vehicle is disarmed, the firmware forces the use of this core so that every flight starts the same way.

Switching in flight (`NavEKF3::UpdateFilter`) happens only on an armed vehicle and no sooner than 10 s into the health of the primary core. Each core has an error score: the maximum of ½·(velocity test ratio + position test ratio) and the height test ratio (plus airspeed and compass if the `EK3_AFFINITY` bits are set). A candidate core must be healthy and must not have been primary in the last 10 s. The switch happens if the primary has a score > 1, is unhealthy, has no aligned yaw while the candidate has one (this matters in compass-less flight), or the candidate is consistently better: at every filter step the difference between the candidate's and the primary's score is added to the candidate's relative error, but a gain counts only if it exceeds `EK3_ERR_THRESH` (0.2); the sum is limited to ±1, and at ≤ −0.5 the core changes. One more attempt comes from the autopilot itself: one iteration before the EKF failsafe it requests `check_lane_switch` (a candidate with a score < 0.9, no more often than once in 5 s). In the GCS: `EKF3 lane switch 1` and `EKF primary changed:1`; in the log, `ERR` subsystem 24 with the new core as the code, and `XKF4.PI`. `EK3_OPTIONS` bit 1 ManualLaneSwitching turns the automation off completely, and the parameter description says "DANGEROUS".

The key point for your choice: cores protect against the failure of **one IMU**. All cores see the same GPS, compass and baro, so they do not cure a common sensor failure. In SITL with GPS switched off the firmware still switched cores 0.1 s before the failsafe (step 3), to no effect, because the second core was in the same situation.

### The source sets EK3_SRC1..3 and how to switch them
A set is five parameters: `EK3_SRCn_POSXY`, `_VELXY`, `_POSZ`, `_VELZ`, `_YAW`. The values (`AP_NavEKF_Source.cpp`): POSXY is 0 None, 3 GPS, 4 Beacon, 6 ExternalNav; VELXY has the same plus 5 OpticalFlow and 7 WheelEncoder; POSZ is 0, 1 Baro, 2 RangeFinder, 3 GPS, 4 Beacon, 6 ExternalNav; VELZ is 0, 3, 4, 6; YAW is 0 None, 1 Compass, 2 GPS, 3 GPS with Compass Fallback, 6 ExternalNav, 8 GSF. Defaults: set 1 is 3/3/1/3/1, sets 2 and 3 are all 0 except POSZ = 1 (baro). Which sources to use for flow, beacons and mocap is tabulated in `nav-indoor`.

The active set is changed in three ways, all usable in flight:

- **A switch** with `RCx_OPTION = 90` (EKF Source Set): low position is set 1, middle is 2, high is 3. Only this path writes `Using EKF Source Set 2` to the GCS.
- **MAVLink** `MAV_CMD_SET_EKF_SOURCE_SET`, param1 = 1…3 (out of range gives `MAV_RESULT_DENIED`). This is how a companion computer with VIO switches.
- **Lua** `ahrs:set_posvelyaw_source_set(0…2)`. The ready-made script `applets/ahrs-source-extnav-optflow.lua` chooses between ExternalNav and optical flow from their innovations.

The current set is logged in `XKFS.SS` (0, 1, 2). `EK3_SRC_OPTIONS`: bit 0 FuseAllVelocities (fuse the velocities of all sets; cleared by default in 4.7), bit 1 AlignExtNavPosWhenUsingOptFlow, bit 3 UsePerCoreEKFSources (new in 4.7: different sets for different cores). A wrong combination is caught by the pre-arm line `AHRS: Check EK3_SRC1_POSXY` (likewise `_VELXY`, `_POSZ`, `_VELZ`, `_YAW`), and a sensor that is selected but not configured by the line `AHRS: EK3 sources require GPS` (OpticalFlow, RangeFinder, Compass and so on).

### Yaw: compass, GPS yaw and GSF
Yaw is the weakest point of the estimate (`est-attitude`): gravity does not see it, and in a hover it is not observable from GPS. The sources of `EK3_SRC1_YAW`:

- **1 Compass** is the default. How the EKF learns the field in flight is set by `EK3_MAG_CAL`: 0 When flying (the Plane default), 1 When manoeuvring, 2 Never (the Rover default), 3 After first climb yaw reset (the Copter default; in SITL this is the line `EKF3 IMU0 MAG0 in-flight yaw alignment complete` 5.6 s after arming), 4 Always. The old values 5 and 6 have been deprecated since 4.1 and give the pre-arm failure `EK3_MAG_CAL and EK3_SRC1_YAW inconsistent`.
- **2 GPS, 3 GPS with Compass Fallback**: yaw from two antennas (moving baseline, `nav-rtk`). With 3 the compass is aligned to the GPS yaw and takes over after 50 consistent samples in a row (10 s at 5 Hz).
- **6 ExternalNav**: yaw from VIO or mocap (`nav-indoor`, `per-visual-nav`).
- **8 GSF**: a yaw estimator based on motion: a bank of five small filters with different initial yaws (`XKY0.Y0…Y4` and weights `W0…W4`), which picks the right one from the agreement of IMU accelerations with GPS velocity. The result is `XKY0.YC`, and its σ is `XKY0.YCS`.

GSF also runs alongside a compass: `EK3_GSF_RUN_MASK` = 3 runs it on the first two cores, `EK3_GSF_USE_MASK` = 3 allows an emergency yaw reset from it, and `EK3_GSF_RST_MAX` = 2 means no more than two resets per flight. The autopilot requests the reset two iterations before the EKF failsafe (a copter only if the variances are above the threshold, not on a loss of position); the GCS then shows `EKF3 IMU0 emergency yaw reset`, and the compass is marked as failed. With `EK3_SRC1_YAW = 8` (or with no compass) the same operation is routine: `EKF3 IMU0 yaw aligned using GPS`. Planes with a bad compass yaw align to the GPS ground track by default (`EKF3 IMU0 yaw aligned to GPS velocity`) and use GSF for that only if 8 is selected; the emergency reset on the autopilot's request works for them too.

A compass-less copter (`COMPASS_USE = 0` for all, `EK3_SRC1_YAW = 8`) arms only in a mode that needs no position: in Loiter you get `PreArm: Need Position Estimate`. After takeoff in AltHold it needs straight flight: in SITL the GSF converged (σ 14.5° → 1.5°) within 1.5 s after accelerating above 1 m/s, and the yaw was accepted at about 3.2 m/s after roughly 4.5 m of straight flight (step 6).

### Plane and VTOL: airspeed, sideslip, wind and flight without GPS
For a vehicle that flies forward (`fly_forward`, not a ground vehicle) EKF3 assumes a small sideslip (`assume_zero_sideslip()`). That provides three things a copter does not have:

- **Wind states.** They are activated in flight once the ground speed exceeds 5 m/s; the initial wind is taken head-on to the heading, since the filter assumes the takeoff was into the wind. Their rate of change is `EK3_WIND_P_NSE` (0.1 m/s² on Plane, 0.2 on Copter), scaled with vertical speed by `EK3_WIND_PSCALE` (1.0). The estimate is in `XKF2.VWN/VWE`.
- **Airspeed fusion** (`ARSPD_USE = 1`, noise `EK3_EAS_M_NSE` 1.4 m/s, gate 400). While GPS is available, airspeed refines the wind; without GPS, airspeed plus wind gives the velocity over the ground, and that is how dead reckoning works.
- **Sideslip fusion** (`XKF2.IS`). With a working GPS it corrects only the wind by default; in dead reckoning (no position and velocity for longer than 1 s) it corrects all states. `EK3_BETA_MASK` bit 0 Always enables this at all times (a vehicle with no yaw sensor), bit 1 WhenNoYawSensor when there is no yaw source; the parameter description recommends it only for flights beyond visual range, where there are few turns.

Without an airspeed sensor, EKF3 in dead reckoning fuses the last estimated airspeed with a huge uncertainty (σ at least half of the airspeed itself), and the error grows much faster. SITL ArduPlane 4.7.2, LOITER at 50 m, wind 7.3 m/s, GPS off for 60 s: with an airspeed sensor the EKF3 position error against truth is 11.5 m, without one it is 96.3 m (step 7). That answers the question "does a plane need an airspeed sensor": for flight with GPS it is desirable, for any loss of GPS it is decisive.

What other subsystems see. `AP_AHRS::airspeed_EAS()` returns the sensor, but if EKF3 is rejecting its airspeed (the `rejecting_airspeed` flag) in armed fly-forward flight outside dead reckoning, the sensor is replaced by the synthetic airspeed |v_ground − wind| from EKF3 (`AHRS_OPTIONS` bit 2 disables the replacement). Without EKF3, DCM computes the synthetic value. The synthetic airspeed is constrained to ground speed ± `AHRS_WIND_MAX` if that is not 0. TECS and the VTOL assistance threshold rest on this value; the details of the transitions are in the VTOL modules. On a copter EKF3 estimates wind from drag: `EK3_DRAG_BCOEF_X/Y` (mass/frontal area, kg/m²) and `EK3_DRAG_MCOEF` (rotor drag, 1/s), noise `EK3_DRAG_M_NSE` 0.5 m/s²; the SITL file `copter-wind-estimates.parm` has 9.5, 9.5 and 0.082.

The Plane EKF failsafe (`ArduPlane/ekf_check.cpp`) works only when armed and only in position-controlled VTOL modes: an automatic Q mode → QLAND, a pilot one → QHOVER. In fixed-wing flight it does not exist; the DCM fallback takes its place. The threshold is the same `FS_EKF_THRESH` (0.8; the Plane range is 0.6–1.0), and Plane has no `FS_EKF_ACTION`. Unlike the copter check, the Plane check looks only at the variances: it has no "no position" clause.

### The copter EKF failsafe and the messages to the pilot
`Copter::ekf_check()` is called 10 times a second. The check fails if (the position variance ≥ `FS_EKF_THRESH` and at least one of compass or velocity as well) or both compass and velocity are above the threshold (velocity above twice the threshold with no optical flow counts as both), **or if the EKF has no position at all**. The check starts only after the EKF has an origin and has passed at least once. Ten failed checks in a row (1 s) make a failsafe: `EKF variance`, then `EKF Failsafe: changed to Land Mode`; the log has `ERR` 16/2 and 17/1. At the 8th iteration the autopilot requests a GSF yaw reset (only if the variances are above the threshold), at the 9th a lane switch. It clears with `EKF Failsafe Cleared` once the counter returns to zero.

The position clause is a trap: the line says "EKF variance", yet the variances may be zero. In SITL after GPS was switched off all four variances stayed at 0.01, and the failsafe came when the horizontal position bits disappeared from the EKF flags (0x033f → 0x0025, step 3).

The threshold in sigmas is `FS_EKF_THRESH` · G/100: 0.8 with velocity and position gates of 500 is an innovation of 4σ, and with a compass gate of 300 it is 2.4σ.

`FS_EKF_ACTION`: 0 Report only (new in 4.7), 1 Land if the current mode requires position (the default), 2 AltHold if it does (with an RC failsafe already active, or if the change fails, Land), 3 Land from all modes. In a mode that needs no position, 1 and 2 give only `EKF Failsafe`. The Land used here is a landing without GPS. `FS_EKF_THRESH` = 0.8 (0 disables the check), `FS_EKF_FILT` = 5 Hz is the variance filter.

| Message | Where it comes from | What it means |
|---|---|---|
| `PreArm: AHRS: EKF3 not started` | `AP_AHRS::pre_arm_check` | EKF3 is not initialised yet (it starts no sooner than 1 s after boot) or is disabled with `EK3_ENABLE = 0` |
| `PreArm: AHRS: not using configured AHRS type` | the same | the `AHRS_EKF_TYPE` value is not allowed for the vehicle, or the wrong backend is active while the compass is in use |
| `PreArm: Need Position Estimate` | `AP_Arming_Copter` | the mode requires position and there is none: no GPS, no origin, or compass-less yaw not aligned yet |
| `PreArm: AHRS: EKF3 Yaw inconsistent 25 deg. Wait or reboot` | `attitudes_consistent` | the cores or DCM disagree on yaw (for roll and pitch, `Roll/Pitch`) |
| `PreArm: AHRS: GPS HDOP 3.1 (needs 2.5)` and the neighboring `GPS horiz error`, `GPS drift` | the `EK3_GPS_CHECK` checks | the GPS is not yet good enough for alignment; `EK3_CHECK_SCALE` scales the thresholds |
| `PreArm: AHRS: EKF3[1] vel error 2.4` | `NavEKF3_core::pre_arm_check` | on the ground the GPS velocity innovation is above 2 m/s |
| `PreArm: EKF attitude is bad` | `AP_Arming_Copter` | the EKF attitude does not converge, most often gyro bias after movement during boot |
| `EKF3 IMU0 stopped aiding` | an EKF3 core | 15 s with no source that constrains tilt: constant position mode |
| `AHRS: DCM active` | `AP_AHRS::update` | on Plane or Rover the fallback has triggered; on Copter, before EKF3 starts |

### Logs: what to open
- `XKF4` per core (`C`): `SV`, `SP`, `SH`, `SM`, `SVT` are square roots of test ratios; `SS` holds the solution status flags (bits as in `nav_filter_status`: 0 attitude, 1 horizontal velocity, 3 and 4 relative and absolute position, 7 constant position, 13 using GPS, 17 rejecting airspeed, 18 dead reckoning); `PI` is the primary core; `FS`, `TS` are faults and timeouts.
- `XKF3` has the innovations and `ErSc` (error score), `RErr` (the relative core error); `XKF2` has accelerometer bias, wind, field, drag and sideslip innovations; `XKF1` is the state; `XKF5` is flow and rangefinder; `XKFS` shows the selected compass, baro, GPS, airspeed and the source set `SS`; `XKQ` is the core quaternion; `XKY0/XKY1` are GSF.
- `AHR2` is the second estimator (see above), `ATT` is what the control loops saw. `NKF*` is the same for EKF2.
- `EK3_LOG_LEVEL`: 0 is everything (the default), 1 is `XKF4` only, 2 is `XKF4` and GSF, 3 is no streaming logs.
- `MSG` lines: `EKF3 IMU0 is using GPS` (the core has started fusing GPS; wait for it before arming in position-controlled modes), `EKF3 IMU0 fusing optical flow`, `EKF3 IMU0 is using external nav data`, `EKF3 IMU0 initialised`, `tilt alignment complete`, `origin set`.

### Selection rules
| Vehicle and condition | `AHRS_EKF_TYPE` | Set 1 (POSXY/VELXY/POSZ/VELZ/YAW) | Backup sets and switching | Key parameters | What not to do |
|---|---|---|---|---|---|
| Copter with GPS and compass | 3 | 3/3/1/3/1 (the defaults) | not needed | `EK3_IMU_MASK` for all healthy IMUs, `FS_EKF_ACTION` 1 | raising `FS_EKF_THRESH` just to be able to arm |
| Plane | 3 | 3/3/1/3/1, `ARSPD_USE = 1` | not needed | `EK3_MAG_CAL` 0, `AHRS_OPTIONS` 0 (the DCM fallback is allowed) | setting 0 "because it is simpler" for no reason, as in the HeeWing case |
| VTOL (QuadPlane) | 3 | as for a plane, with a compass for hovering | not needed | an airspeed sensor, the EKF failsafe of Q modes → QLAND or QHOVER | flying position-controlled Q modes without a verified compass |
| No GPS, indoors | 3 | flow 0/5/1/0/1, UWB 4/0/4/0/1, mocap 6/6/6/6/6 | GPS in set 1 outdoors, indoors in set 2, `RCx_OPTION = 90` | the origin through `SET_GPS_GLOBAL_ORIGIN`, `VISO_DELAY_MS`; in 4.7 beacons are compiled in only with more than 2 MB of flash (`AP_BEACON_ENABLED`), so on a typical H7 you need a custom build server build | Loiter on flow above the rangefinder range |
| Unreliable compass | 3 | 3/3/1/3/8, `COMPASS_USE = 0`; with two antennas 3/3/1/3/2 or 3 | not needed | arm in AltHold, fly straight until `yaw aligned using GPS` | arming in Loiter (`Need Position Estimate`) |
| VIO on a companion computer | 3 | GPS (3/3/1/3/1) | set 2: 6/6 (or VELXY 0)/1 or 6/6 or 0/6, switched by `MAV_CMD_SET_EKF_SOURCE_SET` or Lua | `VISO_TYPE = 1`, `reset_counter` | sending a "frozen" pose when tracking is lost (`per-visual-nav`) |
| 1 MB board (F405) | 3 | GPS (3/3/1/3/1), flow 0/5/1/0/1, compass or GSF (8) | the sets and the switch are available | ExternalNav, VisualOdom, the drag-based wind estimate and wheel odometry (on Copter and Plane) are compiled out: they need more than 1024 KB; `minimize_common.inc` also drops MAVLink GPS (`GPS_INPUT`) and dual-antenna yaw, so you cannot feed VIO to such a board on standard firmware | looking for EKF2 or DCM flight on a copter; planning VIO on an F405 |

{{diagram:ahrs-choice-tree|The decision takes two steps: the vehicle type determines whether DCM is allowed, and where position and yaw come from determines the EK3_SRC set; in every branch the estimator is EKF3.}}

### When the EKF misbehaves
1. **Read the whole line.** `PreArm: AHRS: …` is configuration or waiting for GPS; `EKF variance` means open `XKF4`; `EKF3 lane switch` means compare the cores; `AHRS: DCM active` on a plane means EKF3 has lost position or is unhealthy.
2. **Find the field above the threshold in `XKF4`.** `SM` is the compass: interference from current, calibration (`ap-sensors`), yaw source 3 or 8. `SV`/`SP` is GPS: satellites, `GPA.HAcc`, a glitch, the delay `GPS1_DELAY_MS` (`nav-resilience`). `SH` is baro or vibration.
3. **If everything is near zero**, look at `SS`: if bits 3 and 4 are gone, the position source has disappeared, and the problem is not the "variances" but the data (GPS dropped out, or a source set with no position).
4. **A lane switch with no external cause**: compare `XKF4` of cores `C=0` and `C=1`; if one core grows and the other does not, the culprit is the IMU, vibration or clipping (`ap-logs`).
5. **Leave the threshold and the gates alone** until you have found the cause: `FS_EKF_THRESH` 0.8 with gates of 500 is already 4σ.

{{diagram:ahrs-ekf-trouble-tree|The "everything is near zero" branch is the most deceptive: the message is called EKF variance, yet the cause is a position source that has disappeared, which shows in the SS flags and not in the variances.}}

### Place in the system

- **Receives:** IMU, GPS, compass, baro, airspeed, rangefinder and flow (`est-sensors`, `est-gnss`, `est-alt-sources`, `ap-sensors`); an external pose from a companion computer (`per-visual-nav`, `nav-indoor`).
- **Provides:** attitude, velocity, position and wind to the control loops and the position-controlled modes (`ap-missions`, `ap-quadplane`); variances and flags to the EKF failsafe and the pre-arm checks (`ap-safety-fs`); `XKF*`, `AHR2` to the log (`ap-logs`).
- **If you get it wrong here:** a compass-less copter is armed in Loiter → `Need Position Estimate`, and after a takeoff in AltHold the yaw does not converge without straight flight (`nav-resilience`). A plane with no airspeed sensor loses GPS → dead reckoning drifts 96 m in a minute, and RTL leads to the wrong place (`ap-safety-fs`).

## practice
The main path is SITL ArduCopter and ArduPlane 4.7.2 (built with `./waf configure --board sitl && ./waf copter plane`, as in `ap-sitl`). The time in the output is seconds since boot; with the same parameters, event times in SITL repeat to within 0.1–0.5 s, and the drift from `SIM` to within about a meter (SITL is not fully deterministic).

### Step 1. Who is active at boot
The script below (the experiments of steps 3–5; steps 2 and 6 were done with the same functions `pump`, `setp`, `mode` and the commands listed in the step) starts SITL, flies the vehicle and prints `STATUSTEXT`, mode changes and `EKF_STATUS_REPORT` (variances and flags). Put it in the root of the ArduPilot tree; the `flow` experiment needs `flow.parm` next to it (step 4). The last argument is the SITL instance number.

```python
"""EKF3 behaviour in ArduCopter 4.7.2 SITL: GPS loss, source set switch, IMU fault.
Run: python3 ahrs_lab.py gpsloss|flow|lane [instance]   (arducopter built with ./waf copter; flow.parm next to it for 'flow')."""
import subprocess, sys, time
from pymavlink import mavutil

BIN, DEF = 'build/sitl/bin/arducopter', 'Tools/autotest/default_params/copter.parm'
exp = sys.argv[1]
I = int(sys.argv[2]) if len(sys.argv) > 2 else 5        # SITL instance: ports 5760 + 10*I
defaults = DEF + (',flow.parm' if exp == 'flow' else '')
sitl = subprocess.Popen([BIN, '-S', '-w', '--model', '+', '--defaults', defaults, f'-I{I}',
                         '--home', '50.45,30.52,100,0'], stdout=subprocess.DEVNULL)
time.sleep(3)
m = mavutil.mavlink_connection(f'tcp:127.0.0.1:{5760 + 10 * I}', source_system=255)
m.wait_heartbeat()
m.mav.request_data_stream_send(m.target_system, 1, mavutil.mavlink.MAV_DATA_STREAM_ALL, 4, 1)
rc = [1500, 1500, 1000, 1500, 1800, 1000, 1000, 1000]   # RC override: throttle low, ch5 fixed
st = {'t': 0.0, 'mode': None, 'ekf': None}


def pump(sec, every=None, quiet=False):
    """Read MAVLink for sec seconds; print STATUSTEXT, mode changes and EKF_STATUS_REPORT."""
    t0 = last = time.time()
    while time.time() - t0 < sec:
        m.mav.rc_channels_override_send(m.target_system, 1, *rc)
        r = m.recv_match(blocking=True, timeout=0.1)
        if r is None:
            continue
        typ = r.get_type()
        if typ == 'SYSTEM_TIME':
            st['t'] = r.time_boot_ms / 1000
        elif typ == 'STATUSTEXT' and not quiet:
            print(f"{st['t']:7.1f} s  MSG  {r.text}")
        elif typ == 'HEARTBEAT' and r.get_srcComponent() == 1 and r.type != 6:
            md = mavutil.mode_string_v10(r)
            if md != st['mode'] and not quiet:
                print(f"{st['t']:7.1f} s  MODE {md}")
            st['mode'] = md
        elif typ == 'EKF_STATUS_REPORT':
            st['ekf'] = r
        if every and st['ekf'] and time.time() - last >= every:
            e, last = st['ekf'], time.time()
            print(f"{st['t']:7.1f} s  EKF  vel={e.velocity_variance:.2f} pos={e.pos_horiz_variance:.2f}"
                  f" hgt={e.pos_vert_variance:.2f} mag={e.compass_variance:.2f} flags=0x{e.flags:04x}")


def setp(name, value):
    m.mav.param_set_send(m.target_system, 1, name.encode(), value, mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
    print(f"{st['t']:7.1f} s  SET  {name} = {value:g}")


def mode(name):
    m.mav.set_mode_send(m.target_system, mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, m.mode_mapping()[name])
    pump(1)


pump(45, quiet=True)                                    # boot, EKF origin, "is using GPS"
mode('GUIDED')
m.mav.command_long_send(m.target_system, 1, mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 1, 0, 0, 0, 0, 0, 0)
pump(2)
alt = 10 if exp == 'flow' else 20
m.mav.command_long_send(m.target_system, 1, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, alt)
pump(15)
rc[2] = 1500                                            # throttle to mid before LOITER
mode('LOITER')
pump(5, every=5)
if exp == 'gpsloss':
    setp('SIM_GPS1_ENABLE', 0); pump(40, every=2)
elif exp == 'flow':
    rc[6] = 1500                                        # RC7_OPTION = 90: middle = source set 2
    pump(10, every=5)
    setp('SIM_GPS1_ENABLE', 0); pump(40, every=5)
elif exp == 'lane':
    pump(10)
    setp('SIM_ACC1_BIAS_Z', 3); pump(30, every=3)       # first IMU gets +3 m/s^2 on Z
sitl.terminate()
```

Boot (the first 45 s, printed without `quiet` in my run):

```
    0.0 s  MSG  AHRS: DCM active
    4.3 s  MSG  EKF3 IMU0 initialised
    4.3 s  MSG  EKF3 IMU1 initialised
    4.3 s  MSG  AHRS: EKF3 active
    5.8 s  MSG  EKF3 IMU0 tilt alignment complete
    5.8 s  MSG  EKF3 IMU0 MAG0 initial yaw alignment complete
   19.8 s  MSG  EKF3 IMU0 origin set
   41.5 s  MSG  EKF3 IMU0 is using GPS
   41.5 s  MSG  EKF3 IMU1 is using GPS
```

There are two cores because SITL has two IMUs and `EK3_IMU_MASK = 3`. For the first 4.3 s DCM is active, which is its only normal role on Copter: you cannot arm during this time, since EKF3 has not started yet.

### Step 2. AHRS_EKF_TYPE = 0 on a copter
On the ground, after `is using GPS`: `AHRS_EKF_TYPE = 0`, then an arming attempt in STABILIZE.

```
   46.0 s  SET  AHRS_EKF_TYPE = 0
   46.0 s  MSG  AHRS: DCM active
   47.0 s  MSG  EKF variance
   47.0 s  MSG  Arm: EKF attitude is bad
   47.0 s  MSG  Arm: AHRS: not using configured AHRS type
   52.3 s  SET  AHRS_EKF_TYPE = 3
   52.3 s  MSG  AHRS: EKF3 active
```

The copter does not arm even in STABILIZE. A SITL peculiarity: EKF2 is compiled in there, so 0 became "EKF2", which is disabled (`EK2_ENABLE = 0`), and DCM became active. On a board without EKF2, EKF3 stays active, but the line `not using configured AHRS type` is the same: the pre-arm check compares the stored value with the actual one.

### Step 3. GPS loss in Loiter
`python3 ahrs_lab.py gpsloss`: a takeoff in GUIDED to 20 m, LOITER, then `SIM_GPS1_ENABLE = 0` (before 4.7, `SIM_GPS_DISABLE = 1`).

```
   69.8 s  SET  SIM_GPS1_ENABLE = 0
   76.1 s  EKF  vel=0.01 pos=0.01 hgt=0.00 mag=0.01 flags=0x033f
   77.8 s  MSG  EKF3 lane switch 1
   77.8 s  MSG  EKF primary changed:1
   78.1 s  MODE LAND
   78.1 s  MSG  EKF variance
   78.1 s  MSG  EKF Failsafe: changed to Land Mode
   78.1 s  EKF  vel=0.01 pos=0.01 hgt=0.00 mag=0.01 flags=0x0025
   85.1 s  MSG  EKF3 IMU1 stopped aiding
   85.1 s  MSG  EKF3 IMU0 stopped aiding
   86.6 s  EKF  vel=0.00 pos=0.00 hgt=0.00 mag=0.01 flags=0x00a7
   92.1 s  MSG  SmartRTL deactivated: bad position
```

Decoding the flags (`EKF_STATUS_FLAGS`): 0x033f is attitude, both velocities, relative and absolute position, height, predicted position; 0x0025 leaves only 1 + 4 + 32: attitude, vertical velocity, height; 0x00a7 adds bit 128, constant position mode. The variances never rose above 0.01, and the failsafe triggered on the "no position" clause: 8.3 s later in the script output, and more precisely from the log, `PARM SIM_GPS1_ENABLE` at 70.06 s and `ERR` 17/1 at 78.14 s, that is 8.1 s (the printed time lags by 0.2–0.3 s, because `SYSTEM_TIME` arrives a few times a second). The lane switch at 78.04 s, 0.1 s before the failsafe, is that `check_lane_switch` attempt, useless in a common failure. `stopped aiding` came at 85.21 s, 15.2 s later: the 15 s timeout with no tilt-constraining source. Per `SIM` in the log the vehicle had drifted 1.2 m from its point by the time of the failsafe and 4.3 m by the 16th second (no wind): Land without GPS does not hold position.

### Step 4. Source set 2: optical flow
`flow.parm` (SITL flow and a rangefinder, as in `Tools/autotest/default_params/copter-optflow.parm`, but with flow in set 2):

```
FLOW_TYPE 10
SIM_FLOW_ENABLE 1
RNGFND1_TYPE 1
RNGFND1_MIN 0
RNGFND1_MAX 40.00
RNGFND1_PIN 0
RNGFND1_SCALING 12.12
EK3_SRC2_POSXY 0
EK3_SRC2_VELXY 5
EK3_SRC2_POSZ 1
EK3_SRC2_VELZ 0
EK3_SRC2_YAW 1
RC7_OPTION 90
```

`python3 ahrs_lab.py flow`: Loiter at 10 m on GPS, the RC7 switch to the middle, then GPS off.

```
   69.8 s  EKF  vel=0.01 pos=0.01 hgt=0.00 mag=0.02 flags=0x037f
   70.3 s  MSG  Using EKF Source Set 2
   70.3 s  MSG  EKF3 IMU1 fusing optical flow
   70.3 s  MSG  EKF3 IMU0 fusing optical flow
   79.8 s  SET  SIM_GPS1_ENABLE = 0
   84.8 s  EKF  vel=0.01 pos=0.01 hgt=0.00 mag=0.01 flags=0x016f
  115.1 s  EKF  vel=0.01 pos=0.01 hgt=0.00 mag=0.01 flags=0x016f
```

0x016f = 1 + 2 + 4 + 8 + 32 + 64 + 256: absolute position is gone (flags 16 and 512 are cleared), relative position remains, the mode is LOITER, and there is no failsafe for 35 s. The true drift from the point per `SIM` is about 1 m (no wind; across three runs the maximum was 0.8–1.4 m in 36–40 s). Compare with step 3: the same GPS failure, but a backup source set turned a landing into a continued flight.

### Step 5. Failure of one IMU, and the cores
`python3 ahrs_lab.py lane`: in Loiter at 20 m the first IMU gets `SIM_ACC1_BIAS_Z = 3` m/s².

```
   79.8 s  SET  SIM_ACC1_BIAS_Z = 3
   80.8 s  MSG  EKF3 lane switch 1
   80.8 s  MSG  EKF primary changed:1
   82.8 s  EKF  vel=0.01 pos=0.01 hgt=0.00 mag=0.02 flags=0x033f
```

The log (`XKF4` of the two cores, the same run):

```
 80.06 PARM SIM_ACC1_BIAS_Z 3.0
 80.64 XKF4 C=0 SV=0.44 SP=0.00 SH=0.01 PI=0
 80.64 XKF4 C=1 SV=0.02 SP=0.00 SH=0.00 PI=0
 80.81 MSG EKF3 lane switch 1
 80.81 ERR Subsys=24 ECode=1
 81.84 XKF4 C=0 SV=1.32 SP=0.00 SH=0.24 PI=1
 81.84 XKF4 C=1 SV=0.02 SP=0.00 SH=0.00 PI=1
```

Core 0 was switched out 0.75 s after the parameter was applied (80.06 → 80.81 s). The last record before the switch has `SV` = 0.44; by the moment of the switch the error score of core 0 (`XKF3.ErSc`) had reached 0.21, which is ½·SV² at SV ≈ 0.65. The difference from the healthy core exceeded `EK3_ERR_THRESH` = 0.2, and the relative error of core 1 hit −1 within a fraction of a second (`XKF3.RErr`): the "candidate is consistently better" rule fired, not score > 1. A second later `SV` of the corrupted core reached 1.32: its velocity measurements would already have been rejected. Work out by hand what 0.44 means: with `EK3_VEL_I_GATE = 500` the velocity innovation is 0.44 · 5 = 2.2σ. The vehicle did not change mode: on the healthy IMU the EKF is healthy.

### Step 6. A copter with no compass
The same SITL with `COMPASS_USE`, `COMPASS_USE2`, `COMPASS_USE3` = 0 and `EK3_SRC1_YAW = 8`. Arming in LOITER, then in ALT_HOLD, a 6 s climb, pitch at 1300 µs (forward flight).

```
   47.0 s  MSG  Arm: Need Position Estimate
   51.0 s  MODE ALT_HOLD
   52.0 s  MSG  Arming motors
   60.0 s  EKF  vel=0.00 pos=0.00 hgt=0.00 mag=0.00 flags=0x00a7
   62.8 s  MSG  EKF3 IMU1 yaw aligned using GPS
   62.8 s  MSG  EKF3 IMU0 yaw aligned using GPS
   62.8 s  MSG  EKF3 IMU0 is using GPS
   63.0 s  EKF  vel=0.00 pos=0.00 hgt=0.00 mag=0.00 flags=0x033f
```

From the `XKY0` log (true yaw 0°): at 60.5 s `YC` = 273.6°, `YCS` = 14.4°; at 61.0 s, at 1.0 m/s, 356.3° and 5.1°; at 61.5 s, 357.3° and 2.6°; at 62.5 s, 357.8° and 1.5°. The yaw was accepted at 62.8 s at about 3.2 m/s, about 4.5 m from the start of the acceleration (per `GPS`: 2.4 m/s and 2.2 m by 62.0 s, 3.4 m/s and 5.1 m by 63.0 s). After that LOITER engaged without a refusal.

### Step 7. A plane with no GPS in wind
ArduPlane SITL (`--model plane`, `Tools/autotest/models/plane.parm`), `SIM_WIND_SPD 8`, `SIM_WIND_DIR 270`. Wind in SITL grows with altitude as a square root up to `SIM_WIND_T_ALT` = 60 m, so at 50 m it is 8 · √(50/60) = 7.30 m/s. A takeoff in TAKEOFF to 50 m, LOITER, `SIM_GPS1_ENABLE = 0` for 60 s. Two runs: `ARSPD_USE = 1` and `ARSPD_USE = 0`. A script computes the EKF3 position error against truth:

```python
"""EKF position error against SITL truth: python3 poserr.py <run dir> <t0 s> <t1 s> <step s>.
POS = AHRS position (EKF3 when active), SIM = simulator truth, XKF2.VWE = EKF wind estimate (moving-to-East)."""
import glob, math, sys
from pymavlink import mavutil

run, ta, tb, step = sys.argv[1], *map(float, sys.argv[2:5])
log = mavutil.mavlink_connection(sorted(glob.glob(run + '/logs/0*.BIN'))[-1])
sim = wind = xkf4 = None
last = -99
while (r := log.recv_match(type=['SIM', 'POS', 'XKF2', 'XKF4', 'MSG'])) is not None:
    t, typ = r.TimeUS / 1e6, r.get_type()
    if typ == 'SIM':
        sim = r
    elif typ == 'XKF2' and r.C == 0:
        wind = (r.VWN, r.VWE)
    elif typ == 'XKF4' and r.C == 0:
        xkf4 = r
    elif typ == 'MSG' and ta <= t <= tb:
        print(f'{t:7.1f} MSG {r.Message}')
    elif typ == 'POS' and sim and wind and xkf4 and ta <= t <= tb and t - last >= step:
        last = t
        dn = (r.Lat - sim.Lat) * 111320                                   # degrees -> metres
        de = (r.Lng - sim.Lng) * 111320 * math.cos(math.radians(sim.Lat))
        print(f'{t:7.1f} POS err vs truth {math.hypot(dn, de):.1f} m wind_est N={wind[0]:.1f} E={wind[1]:.1f}'
              f' SS=0x{xkf4.SS:x}')
```

The output (GPS off at 110.0 s, on at 170.0 s) is a selection from the two runs side by side, with some lines and the fields `N=` and `SS` omitted:

```
ARSPD_USE = 1                                         ARSPD_USE = 0
  110.0 POS err vs truth 1.0 m wind_est E=7.1           110.0 POS err vs truth 1.0 m wind_est E=6.0
  125.1 POS err vs truth 2.2 m SS=0x5812f               117.3 MSG AHRS: DCM active
  140.1 POS err vs truth 6.9 m                          117.3 MSG AHRS: EKF3 active
  155.2 POS err vs truth 7.8 m                          125.1 POS err vs truth 17.7 m SS=0x5812f
  165.3 POS err vs truth 11.8 m                         140.1 POS err vs truth 39.7 m
  170.3 POS err vs truth 11.5 m                         155.2 POS err vs truth 75.0 m
                                                        170.3 POS err vs truth 96.3 m
```

`SS = 0x5812f` is bits 0–3, 5, 8, 15, 16 and 18: the position is relative, the dead reckoning flag (bit 18) is set, and there is no absolute position. With the sensor the wind is estimated at 7.1 m/s against a true 7.3; the error estimate Δw · t = 0.2 · 60 = 12 m agrees with the measured 11.5–11.8 m. Without the sensor the wind is 6.4 m/s and the error is 96.3 m, noticeably more than the wind alone would explain (0.9 · 60 = 54 m): the airspeed itself is unknown too.

{{diagram:chart-ahrs-deadreckon|With an airspeed sensor the dead reckoning error over a minute without GPS fits the estimate Δw·t ≈ 12 m; without a sensor it is eight times larger, and that decides whether you need the sensor.}}

### Moving to real hardware
1. **Props off, on the bench.** Connect the GCS and wait for `EKF3 IMU0 is using GPS` (outdoors). Check `AHRS_EKF_TYPE = 3`, `EK3_IMU_MASK` against the number of IMUs (`INS_*` in the sensor list), and set 1. Compare `ATT.Yaw` and `AHR2.Yaw` in a short log taken with `LOG_DISARMED = 1`: a difference of more than 20° points to the compass or its orientation. Turn the vehicle through a full circle: `XKF4.SM` must stay < 0.3.
2. **The source set switch.** If you have flow or VIO: `RCx_OPTION = 90`, and on the ground flip it to the middle position: `Using EKF Source Set 2`, then `fusing optical flow` or `is using external nav data`. Without that line do not go airborne on set 2.
3. **First flight with props.** Altitude 5–10 m, AltHold on a switch. Switch to set 2 only over a level, textured surface within rangefinder range; keep a finger on AltHold. A compass-less copter: take off in AltHold, fly straight for 5–10 s at 3–5 m/s until `yaw aligned using GPS`, and only then use Loiter.
4. **Plane.** Before flying without GPS check `ARSPD_USE = 1` and that `XKF4.SS` bit 17 (rejecting airspeed) does not come up in straight flight; the wind estimate `XKF2.VWN/VWE` over the first 2–3 turns should agree in direction with the weather forecast. Do not switch GPS off in the air on a real vehicle; use the log of a real loss if you have had one.

Hardware acceptance criteria: `EKF3 IMU0 is using GPS` before every arming in position-controlled modes; `XKF4.SV/SP/SM` < 0.5 in a calm hover; not a single `lane switch` in 10 flights; on a compass-less copter the yaw aligns in less than 10 s of straight flight; on a plane the `XKF2` wind differs from the forecast by no more than 3 m/s.

Self-check: the lab is done when, for the SITL path: (1) in step 2 you got the line `AHRS: not using configured AHRS type` and arming failed; (2) in step 3 the change to LAND with `EKF Failsafe: changed to Land Mode` came 8.1 ± 0.5 s by the log (`PARM` → `ERR` 17/1; 8.3 s by the script output) after `SIM_GPS1_ENABLE = 0`, with variances no higher than 0.02 and flags 0x033f → 0x0025; (3) in step 4, after `Using EKF Source Set 2` and GPS off, the vehicle stays in LOITER for 35 s with flags 0x016f; (4) in step 5 the lane switch came 0.75 ± 0.3 s after `PARM SIM_ACC1_BIAS_Z` in the log, and 0.44 is converted to 2.2σ; (5) in step 6 `yaw aligned using GPS` came after 4–6 s of straight flight; (6) in step 7 the error after 60 s is 11.5 ± 2 m with the sensor and 96 ± 10 m without it, and the estimate Δw · t = 12 m agrees with the first number to within 3 m. For hardware, use the acceptance criteria above.

**Reference for the self-check.**

| Result | Correct | Typical mistake and its cause |
|---|---|---|
| Step 3, time to LAND | 8.1 s by the log, variances 0.01 | "the failsafe never came": `FS_EKF_ACTION = 0` is set, or the mode does not require position; "it came within 1 s": the EKF (`EK3_ENABLE`) was switched off instead of GPS |
| Step 4, flags | 0x016f, LOITER | 0x0025 and LAND: the switch is not in the middle position, or `RC7_OPTION 90` is missing from `flow.parm`; no `fusing optical flow`: `SIM_FLOW_ENABLE` is not set |
| Step 5, sigmas | 0.44 · 500/100 = 2.2σ | 0.44σ: the normalization by the gate is forgotten; 0.44²: the root of the test ratio is confused with the ratio itself |
| Step 7, error at 60 s | 11.5 and 96.3 m | the same numbers in both runs: `ARSPD_USE` was changed without a restart; an error near zero: `SIM_WIND_SPD` is not set |

## diagnostics
- **Symptom:** `PreArm: AHRS: not using configured AHRS type` on a copter
  - Possible cause: `AHRS_EKF_TYPE = 0` or 2 on a build without EKF2; on a plane, EKF3 is unhealthy and DCM is active while the compass is in use.
  - What to do: `AHRS_EKF_TYPE = 3`, `EK3_ENABLE = 1`, reboot; on a plane, find out why EKF3 is unhealthy (`XKF4`).
- **Symptom:** `EKF variance` and Land although all the variance bars in the GCS are green
  - Possible cause: the EKF has no horizontal position: GPS dropped out, or the active source set has no position.
  - In the log: `XKF4.SS` without bits 3 and 4, `GPS.Status` dropped, variances near 0.
  - What to do: find out why the source disappeared (GPS power, connector, the `EK3_SRCn` set) and leave the threshold alone; add a backup set with flow or VIO (step 4).
- **Symptom:** `EKF3 lane switch` in flight with no visible cause
  - Possible cause: one IMU is noisier: vibration, clipping, heating.
  - In the log: `XKF4.SV/SH` of one core grow and those of the other do not; `VIBE.Clip` on that IMU.
  - What to do: mechanics and damping (`ap-logs`); occasional switches are normal, frequent ones are not.
- **Symptom:** `AHRS: DCM active` in the GCS on a plane
  - Possible cause: EKF3 is not fusing GPS or has lost position with a working 3D fix, or it has entered constant position mode.
  - Consequences: position-controlled modes run on raw GPS, with no gates against glitches.
  - What to do: `XKF4.SP`, `GPA.HAcc`, glitches; disable the fallback (`AHRS_OPTIONS` bit 0) only deliberately.
- **Symptom:** a compass-less copter does not arm in Loiter, and after a takeoff in AltHold it yaws around and will not enter Loiter
  - Possible cause: the GSF yaw is not aligned: the vehicle is hovering or flying slower than 1–2 m/s.
  - What to do: straight flight for 5–10 s at 3–5 m/s until `EKF3 IMU0 yaw aligned using GPS`; watch for `XKY0.YCS` < 5°.
- **Symptom:** `EKF3 IMU0 emergency yaw reset` in flight
  - Possible cause: the compass yaw went wrong (interference from current), GSF rescued the yaw and marked the compass as failed.
  - What to do: `ap-sensors` (CompassMot, moving the compass away); remember that there are no more than `EK3_GSF_RST_MAX` = 2 resets per flight.
- **Symptom:** a plane with no GPS returns to the "wrong place", tens of meters off
  - Possible cause: there is no airspeed sensor, or the EKF is rejecting it (bit 17 in `XKF4.SS`).
  - What to do: fit and calibrate a sensor (`ap-sensors`); dead reckoning with it drifts about 12 m a minute in a 7 m/s wind against 96 m without it.

## references
- ArduPilot source 4.7.2 — AP_AHRS (front end, fallback, pre-arm) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_AHRS/AP_AHRS.cpp | primary | A
- ArduPilot source 4.7.2 — AP_NavEKF3 (parameters, lanes, GSF, air data) | https://github.com/ArduPilot/ardupilot/tree/Copter-4.7.2/libraries/AP_NavEKF3 | primary | A
- ArduPilot source 4.7.2 — EKF source sets (AP_NavEKF_Source.cpp) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_NavEKF/AP_NavEKF_Source.cpp | primary | A
- ArduPilot source 4.7.2 — Copter EKF failsafe (ekf_check.cpp) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/ArduCopter/ekf_check.cpp | primary | A
- ArduPilot docs — Extended Kalman Filter navigation overview | https://ardupilot.org/copter/docs/common-apm-navigation-extended-kalman-filter-overview.html | primary | A
- ArduPilot docs — EKF Source Selection and Switching | https://ardupilot.org/copter/docs/common-ekf-sources.html | primary | A
- ArduPilot docs — Compass-less Operation (EK3_SRC1_YAW = 8, GSF) | https://ardupilot.org/copter/docs/common-compassless.html | primary | A
