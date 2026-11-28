---
id: est-alt-sources
title: "Altitude and position without GPS: baro, rangefinder, optical flow"
level: L3
readingTime: 35 min
firmware: ArduPilot 4.7 (checked against 4.7.3) · INAV 9.1.0 (checked against the source)
status: published
added: 2026-11-08
tags:
  - barometer
  - rangefinder
  - optical flow
  - EK3_SRC
related:
  - ap-ekf
  - est-kalman
  - est-gnss
  - el-peripherals
next:
  - nav-resilience
source: content/estimation/est-alt-sources.md
source_hash: eb202e1c618f
---

## summary
Indoors, under tree canopy and next to walls GPS is useless, and the baro drifts up and down. This module covers barometer errors and how they are compensated, what a rangefinder (lidar, ultrasonic, radar) and optical flow give you, how they connect in ArduPilot and INAV, and how to build a source set for the job with `EK3_SRCn_*`: indoors, forest, precision landing. The lab is position hold without GPS, in SITL (optical flow + rangefinder) and on the bench.

## theory
### Barometer: where the errors come from
Altitude comes from pressure through the standard atmosphere: Δh ≈ −8.4 m per 1 hPa near the ground. The errors:
- **Weather**: as a front passes, pressure changes by 1–3 hPa over a few hours (0.3–1 hPa/h, a drift of 3–8 m per hour; up to ~3 hPa/h in a squall, up to 25 m per hour); the height relative to takeoff over a 10-minute flight drifts by ±0.5–1.5 m, more in a squall.
- **Chip temperature**: warm-up after power-on shifts the reading by meters (`BARO_*` calibration, ArduPilot `TCAL_ENABLED`/`TCAL_BARO_EXP`, foam for thermal stability).
- **Prop wash and airspeed**: dynamic pressure ½ρv² at 20 m/s is 2.4 hPa, i.e. up to ≈ 20 m if the full dynamic pressure reaches the sensor! Put the baro somewhere "quiet" under foam; the airflow error is compensated by `BARO1_WCF_*` (barometer wind compensation; multirotors can use it only with EKF3 and tuned `EK3_DRAG_BCOEF_*`; `BARO_GND_TEMP` is only the ground temperature used in the altitude calculation). Copters also see the prop-wash effect on takeoff and landing (−1…−3 m of false altitude near the ground).
- **Noise**: 0.2–0.5 m RMS unfiltered in flight (with the airflow; the chip itself in a high-precision mode is about 0.1 m or less).

The EKF blends the baro with the accelerometer (see the Kalman filter module): fast changes come from the accel, the slow level from the baro. Nothing compensates the weather drift relative to the takeoff point except GPS altitude (`EK3_SRC1_POSZ = 3`) or a rangefinder near the ground.

### Rangefinder
- **Lidar** (TFmini-S 12 m, TF02-Pro 40 m, Lightware SF20/LW20 100 m, Benewake TF03 180 m): narrow beam, works on any surface except black, mirror-like or water; error about ±6 cm up to 6 m and ~1% beyond (TFmini-S, TF02-Pro; TF03 ±10 cm).
- **Ultrasonic** (MaxBotix): cheap, 5–7 m, picks up noise from props and wind, poor over grass.
- **Radar** (Ainstein US-D1, Nanoradar NRA24, both 24 GHz): 50–200 m, works over water and in dust, more expensive.
Connection: UART (`SERIALx_PROTOCOL = 9`, `RNGFND1_TYPE` per model), I2C (TFmini in I2C mode, `RNGFND1_TYPE = 25`), DroneCAN (`RNGFND1_TYPE = 24`). Parameters: `RNGFND1_MIN/MAX` (meters; before ArduPilot 4.7, `RNGFND1_MIN_CM/MAX_CM` in centimeters), `RNGFND1_ORIENT = 25` (down), `RNGFND1_GNDCLR` (the sensor's height above the ground when the vehicle is landed, m; before 4.7, `RNGFND1_GNDCLEAR` in cm).

What it gives you: **height above terrain** (terrain following, `TERRAIN_*` and `WP_RFND_USE` (before 4.7, `WPNAV_RFND_USE`)), precise landing (`LAND_ALT_LOW_M`, before 4.7 `LAND_ALT_LOW` in cm), and an EKF height source near the ground (`EK3_SRC1_POSZ = 2`; `EK3_RNG_USE_HGT` is the percentage of the maximum range below which the EKF uses the rangefinder). Over tall grass or bushes the rangefinder reports the "terrain" of the vegetation, not the ground; that is not a sensor fault.

### Optical flow
A downward camera (PX4Flow, Cheerson CX-OF, Matek 3901-L0X, HereFlow) measures the angular rate at which the image moves (rad/s). To turn that into linear velocity you need the height above the surface (a rangefinder!) and the vehicle's angular rate (gyro) to subtract rotation: v = (flow − ω) × h. That is why flow without a rangefinder gives only crude stabilization.

Limitations: texture (a plain floor, water or snow do not work), lighting (night without illumination), height (typically 0.3–10 m), speed (motion blur). Calibrate `FLOW_FXSCALER/FYSCALER` in flight: rock the vehicle over a textured surface and compare `OF.flowX` with `OF.bodyX` (ArduPilot log message `OF`).

Connection: `FLOW_TYPE` (1 PX4Flow I2C, 5 MAVLink, 6 DroneCAN, 7 MSP), orientation `FLOW_ORIENT_YAW`, offset from the IMU `FLOW_POS_*`. EKF source: `EK3_SRC1_VELXY = 5`.

### Building a source set
EKF3 has three source sets (`EK3_SRC1_*`, `SRC2`, `SRC3`), switched by an RC switch (`RCx_OPTION = 90`) or a Lua script. Each one has `POSXY`, `VELXY`, `POSZ`, `VELZ`, `YAW`.

{{diagram:ekf-source-tree|Choosing EKF3 sources for the scenario: with GPS, with optical flow and a rangefinder, with external navigation.}}

| Scenario | POSXY | VELXY | POSZ | YAW | Comment |
|---|---|---|---|---|---|
| Open field, GPS | 3 GPS | 3 GPS | 1 Baro | 1 Compass | standard |
| Indoors, textured floor | 0 None | 5 OptFlow | 2 RangeFinder | 1 Compass / 0 | no GPS; the compass is often wrong indoors, then yaw 0 and the heading is held by the gyro alone (drifts) |
| Forest, GPS present but jumping | 3 GPS | 5 OptFlow | 2 RangeFinder (low) / 1 Baro | 1 Compass | flow smooths the GPS jumps |
| Precision landing | 3 GPS | 3 GPS | 2 RangeFinder | 1 | rangefinder near the ground |

`EK3_SRC_OPTIONS = 1` is FuseAllVelocities (fuse the velocities from all configured sources at once; the default is 0 in 4.7, it was 1 in 4.6). Without GPS and without flow you only have Stabilize/AltHold; Loiter and Auto are unavailable (the pre-arm check "PreArm: Need Position Estimate").

### INAV
Optical flow (`opflow_hardware`, scale `opflow_scale`) and the rangefinder (`rangefinder_hardware`) feed the INAV position estimator through the weights `inav_w_xy_flow_p` / `inav_w_xy_flow_v` (the weight of flow in position and in velocity); for indoor flow-based flying the setting description recommends `inav_allow_dead_reckoning = ON` ("May also be useful for indoors OPFLOW navigation"). Position hold without GPS is the POSHOLD mode with flow and a rangefinder set up, over a textured surface.

Height above the surface in INAV 9.1.0 is the **SURFACE** mode (id 33), not a source choice like `EK3_SRC1_POSZ`. The enabling rule: the mode appears on the Modes tab only if the platform is a multirotor and **both a barometer and a rangefinder** are detected (`fc_msp_box.c`); it runs on top of ALTHOLD or POSHOLD, and the throttle stick sets the height above the ground. Two limits define where it is reliable:
- `inav_max_surface_altitude` = 200 cm (0–1000): above this the estimator stops accepting the rangefinder reading, AGL becomes untrusted, and SURFACE starts descending;
- `nav_max_terrain_follow_alt` = 100 cm (up to 1000): the height that full throttle gives in SURFACE; throttle from idle to full maps linearly to 0…`nav_max_terrain_follow_alt` (`navigation_multicopter.c`). Keep it well below the first limit: 100 with 200 is normal; with 250 against 200, the top 20% of the throttle travel ((250 − 200)/250) takes the vehicle where the rangefinder is no longer used.

{{diagram:inav-surface-limits|Full throttle in SURFACE must give a height below inav_max_surface_altitude: with 250 above the 200 limit, the top 20% of the throttle travel takes the vehicle where the rangefinder is no longer used.}}

A "flow + lidar" board over MSP: one UART with the MSP function, `rangefinder_hardware = MSP` and `opflow_hardware = MSP`, then calibrate `opflow_scale` on the Calibration tab. Checking it, the OSD warnings "(SURFACE)" / "(!SURFACE UNRELIABLE!)" and the message format are covered in `inav-sensors-extra`.

### Where it fits

- **Receives:** pressure from the on-board barometer, shielded from airflow (`f-fc-sensors`, `est-sensors`); the gyro's angular rate, to subtract rotation from flow; the rangefinder over UART, I²C or DroneCAN (`el-peripherals`, `el-dronecan`).
- **Provides:** altitude and horizontal velocity to the `EK3_SRCn_*` sets (`est-kalman`, `ap-ekf`); height above the surface to terrain following (`nav-terrain`); the flow + rangefinder pair to flying without GNSS (`nav-indoor`).
- **If you get this wrong:** optical flow enabled without a rangefinder, or over a plain floor, gives no velocity: "PreArm: Need Position Estimate" or a drifting hold point (`nav-indoor`). A rangefinder as the height source over grass or bushes raises the "ground" to the height of the vegetation, and the vehicle flies higher or lower than expected (`nav-terrain`).

## practice
### Step 1. Baro
Log 10 minutes on the ground after power-on: `BARO.Alt` shows the warm-up drift. Then hover at 2 m over a flat pad: `BARO.Alt` against `RFND.Dist`, to see the prop-wash effect on takeoff.

### Step 2. Rangefinder
Connect it, set `RNGFND1_*`, and check that the GCS shows `RNGFND1_GNDCLR` while landed. Fly: is `RFND.Dist` smooth, without spikes over grass? Write it down.

### Step 3. SITL without GPS
ArduPilot SITL `--add-param-file` with: `SIM_GPS1_ENABLE = 0` (before 4.7, `SIM_GPS_DISABLE = 1`), `FLOW_TYPE = 10` (SITL), `RNGFND1_TYPE = 100` (SITL), `EK3_SRC1_POSXY = 0`, `EK3_SRC1_VELXY = 5`, `EK3_SRC1_POSZ = 2`, `EK3_SRC1_YAW = 1`. Take off in Loiter, hold position for 60 s, then move with the sticks: record the position drift (`XKF1.PN/PE`). Repeat with `SRC1_POSZ = 1` to see the altitude difference.

### Step 4. Bench/flight
With a real flow sensor and rangefinder: hold in Loiter without GPS over a textured floor at 1–1.5 m, with a spotter and a net or tether. Self-check: the lab is done when the rangefinder shows a value equal to `RNGFND1_GNDCLR` in the GCS while landed, the hold without GPS is recorded as a number (the `XKF1.PN/PE` drift over 60 s in Loiter with `SRC1_POSZ = 2` and with `SRC1_POSZ = 1`), and every `EK3_SRC1_*` you set matches the row of the scenario table for your case.

**Reference for the self-check.** Baro: over 10 minutes on the ground `BARO.Alt` drifts by meters from warm-up; on takeoff near the ground you see prop wash, a false −1…−3 m that is absent from `RFND.Dist`; unfiltered baro noise in flight is 0.2–0.5 m RMS. The no-GPS set for indoors over a textured floor: POSXY 0, VELXY 5, POSZ 2, YAW 1 (or 0 if the compass is wrong indoors). Common wrong results: Loiter will not engage and you get "PreArm: Need Position Estimate", which means the EKF has neither GPS nor flow (check `FLOW_TYPE` and `EK3_SRC1_VELXY = 5`); flow works but the position wanders off, which means there is no height from the rangefinder (v = (flow − ω) × h) or the surface has no texture; `RFND.Dist` jumps over grass, which is the rangefinder honestly seeing "terrain", not a sensor fault.

## diagnostics
- **Symptom:** the altitude "sags" on takeoff and jumps on landing
  - Possible cause: prop wash on the baro.
  - What to do: foam, move the baro, rangefinder as POSZ near the ground.
- **Symptom:** Loiter without GPS drifts on flow
  - Possible cause: poor texture or lighting, flow scale not calibrated, no rangefinder.
  - What to do: calibrate FXSCALER, add lighting and texture; the rangefinder is mandatory.
- **Symptom:** the rangefinder shows max over a field
  - Possible cause: the surface does not reflect (water, black asphalt), range exceeded, angle.
  - What to do: a different type (radar over water), a realistic `RNGFND1_MAX`.
- **Symptom:** Loiter will not engage: "Mode change to Loiter failed: requires position"
  - Possible cause: no POSXY/VELXY source (GPS disabled, flow not set up).
  - What to do: check `EK3_SRC1_VELXY` and the flow status in `OF`.
- **Symptom:** the altitude drifts by 1–3 m over half an hour while landed
  - Possible cause: weather or baro temperature drift.
  - What to do: that is normal; the takeoff-relative altitude is reset at arming.

## references
- ArduPilot — EKF Source Selection and Switching (EK3_SRC) | https://ardupilot.org/copter/docs/common-ekf-sources.html | primary | A
- ArduPilot — Optical Flow Sensors (setup and calibration) | https://ardupilot.org/copter/docs/common-optical-flow-sensor-setup.html | primary | A
- ArduPilot — Rangefinders (landing page) | https://ardupilot.org/copter/docs/common-rangefinder-landingpage.html | primary | A

## checklist
- I know the three main barometer errors and what they look like in the log
- I connected and checked a rangefinder
- I understand the formula v = (flow − ω)·h and why flow needs a rangefinder
- I built an EK3_SRC set for my scenario and can justify it
- I showed position hold without GPS in SITL
