---
id: est-alt-sources
title: "Altitude and position without GPS: baro, rangefinder, optical flow"
level: L3
readingTime: 35 min
firmware: ArduPilot · INAV
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
source_hash: 14fba06eba02
---

## summary
Indoors, under tree canopy and next to walls GPS is useless, and the baro “breathes.” This module breaks down barometer errors and how they're compensated, what a rangefinder (lidar/ultrasonic/radar) and optical flow give you, how they're connected in ArduPilot and INAV, and how to use `EK3_SRCn_*` to build a source set for the job: indoors, forest, precision landing. The lab is position hold without GPS in SITL (optical flow + rangefinder) and on the bench.

## theory
### Barometer: where the errors come from
Altitude from pressure via the standard atmosphere: Δh ≈ −8.4 m per 1 hPa near the ground. Errors:
- **Weather**: pressure changes by 1–3 hPa per hour when a front passes → 10–25 m of drift per hour; relative altitude over a 10-minute flight is ±1–3 m.
- Chip **temperature**: warm-up after power-on drifts by meters (`BARO_*` calibration, ArduPilot `TCAL_ENABLED`/`TCAL_BARO_EXP`, foam for thermal stability).
- **Prop wash and airspeed**: dynamic pressure ½ρv² — at 20 m/s that's 2.4 hPa ≈ 20 m! The baro must sit in a “quiet” spot, under foam; the error from the airflow is compensated by `BARO1_WCF_*` (wind pressure compensation; on copters only with EKF3 and tuned `EK3_DRAG_BCOEF_*`; `BARO_GND_TEMP` is only the ground temperature used for the altitude calculation), on copters also the prop-wash effect on takeoff/landing (−1…−3 m of false altitude near the ground).
- **Noise**: 0.2–0.5 m RMS unfiltered.

The EKF blends the baro with the accelerometer (see the Kalman module): fast changes come from the accel, the slow level from the baro; nothing compensates the weather drift relative to the takeoff point except GPS altitude (`EK3_SRC1_POSZ = 3`) or a rangefinder near the ground.

### Rangefinder
- **Lidar** (TFmini-S 12 m, TF02 40 m, Lightware SF20/LW20 100 m, Benewake TF03 180 m): narrow beam, works on any surface except black/mirror-like/water; error 1–3% or ±5 cm.
- **Ultrasonic** (MaxBotix): cheap, 5–7 m, noisy from props and wind, poor over grass.
- **Radar** (Ainstein, Nanoradar 60 GHz): 30–100 m, works over water and in dust, more expensive.
Connection: UART (`SERIALx_PROTOCOL = 9`, `RNGFND1_TYPE` per model), I2C (TFmini in I2C mode, `RNGFND1_TYPE = 25`), DroneCAN (`RNGFND1_TYPE = 24`). Parameters: `RNGFND1_MIN/MAX_CM`, `RNGFND1_ORIENT = 25` (down), `RNGFND1_GNDCLEAR` (sensor height above the ground when parked).

What it gives you: **height above terrain** (terrain following, `TERRAIN_*` and `WP_RFND_USE` (before 4.7 — `WPNAV_RFND_USE`)), precision landing (`LAND_ALT_LOW`), and an EKF altitude source near the ground (`EK3_SRC1_POSZ = 2`, `EK3_RNG_USE_HGT` — the percentage of max range up to which the EKF uses the rangefinder). Over tall grass/bushes the rangefinder gives you the “terrain,” not the ground — that's not a sensor error.

### Optical flow
A downward-facing camera (PX4Flow, Cheerson CX-OF, Matek 3901-L0X, HereFlow) measures the angular rate of image motion (rad/s). To get linear velocity you need: height above the surface (a rangefinder!) and the aircraft's angular rate (gyro) to subtract rotation. v = (flow − ω) × h. That's why flow without a rangefinder only gives rough stabilization.

Limitations: texture (a plain floor, water, snow — doesn't work), lighting (night without illumination), height (0.3–10 m typical), speed (motion blur). Calibrate `FLOW_FXSCALER/FYSCALER` in flight: the test is rocking over a textured surface and comparing `OF.flowX` with `OF.bodyX` (ArduPilot log `OF`).

Connection: `FLOW_TYPE` (1 PX4Flow I2C, 5 MAVLink, 6 DroneCAN, 7 MSP), orientation `FLOW_ORIENT_YAW`, offset relative to the IMU `FLOW_POS_*`. EKF source: `EK3_SRC1_VELXY = 5`.

### Building a source set
EKF3 has three source sets (`EK3_SRC1_*`, `SRC2`, `SRC3`), switched with a switch (`RCx_OPTION = 90`) or a Lua script. Each one has: `POSXY`, `VELXY`, `POSZ`, `VELZ`, `YAW`.

{{diagram:ekf-source-tree|Choosing EKF3 sources for the scenario: with GPS, with flow and a rangefinder, with external navigation.}}

| Scenario | POSXY | VELXY | POSZ | YAW | Comment |
|---|---|---|---|---|---|
| Open field, GPS | 3 GPS | 3 GPS | 1 Baro | 1 Compass | standard |
| Indoors, textured floor | 0 None | 5 OptFlow | 2 RangeFinder | 1 Compass / 0 | no GPS; the compass often lies indoors — then yaw 0 and heading is held by the gyro only (drift) |
| Forest, GPS present but jumping | 3 GPS | 5 OptFlow | 2 RangeFinder (low) / 1 Baro | 1 Compass | flow smooths out GPS jumps |
| Precision landing | 3 GPS | 3 GPS | 2 RangeFinder | 1 | rangefinder near the ground |

`EK3_SRC_OPTIONS = 1` — fuse all velocities (use velocities from all configured sources at once). Flying without GPS and without flow is Stabilize/AltHold only; Loiter/Auto are unavailable (preflight check “PreArm: Need Position Estimate”).

### INAV
Optical flow (`opflow_hardware`, scale `opflow_scale`) and the rangefinder (`rangefinder_hardware`) feed into the INAV position estimator via the weights `inav_w_xy_flow_p` / `inav_w_xy_flow_v` (the flow weight in position and velocity); for indoor flights on flow the documentation recommends `inav_allow_dead_reckoning = ON` (“may be useful for indoor navigation with OPFLOW”). Position hold without GPS is POSHOLD mode with flow and a rangefinder set up, over a textured surface.

## practice
### Step 1. Baro
A 10-minute log on the ground after power-on: `BARO.Alt` — the drift from warm-up. Then a hover at 2 m over a flat pad: `BARO.Alt` against `RFND.Dist` — see the prop-wash effect on takeoff.

### Step 2. Rangefinder
Connect it, set up `RNGFND1_*`, check in the GCS that the value when parked = `GNDCLEAR`. Flight: is `RFND.Dist` smooth, with no spikes over grass? Record it.

### Step 3. SITL without GPS
ArduPilot SITL `--add-param-file` with: `SIM_GPS1_ENABLE = 0` (in older versions `SIM_GPS_DISABLE = 1`), `FLOW_TYPE = 10` (SITL), `RNGFND1_TYPE = 100` (SITL), `EK3_SRC1_POSXY = 0`, `EK3_SRC1_VELXY = 5`, `EK3_SRC1_POSZ = 2`, `EK3_SRC1_YAW = 1`. Take off in Loiter, hold position for 60 s, then move with the sticks: record the position drift (`XKF1.PN/PE`). Repeat with `SRC1_POSZ = 1` — see the difference in altitude.

### Step 4. Bench/flight
With real flow and a rangefinder: hold in Loiter without GPS over a textured floor at 1–1.5 m, with an observer and a net/tether. Lab: the source is connected, hold without GPS is demonstrated, the EK3_SRC choices are justified.

## diagnostics
- **Symptom:** altitude “sags” on takeoff and jumps on landing
  - Possible cause: prop wash on the baro.
  - What to do: foam, relocate the baro, a rangefinder as POSZ near the ground.
- **Symptom:** Loiter without GPS drifts on flow
  - Possible cause: poor texture/lighting, the flow scale isn't calibrated, no rangefinder.
  - What to do: calibrate FXSCALER, add lighting, texture; a rangefinder is mandatory.
- **Symptom:** the rangefinder shows max over a field
  - Possible cause: the surface doesn't reflect (water, black asphalt), range exceeded, angle.
  - What to do: a different type (radar over water), a realistic `RNGFND1_MAX_CM`.
- **Symptom:** “EKF needs position” and Loiter won't engage
  - Possible cause: no POSXY/VELXY source (GPS disabled, flow not set up).
  - What to do: check `EK3_SRC1_VELXY`, the flow status in `OF`.
- **Symptom:** altitude drifts by 10 m over half an hour while parked
  - Possible cause: weather/temperature drift of the baro.
  - What to do: that's normal; the relative takeoff altitude is reset at arming.

## references
- ArduPilot — EKF Source Selection and Switching (EK3_SRC) | https://ardupilot.org/copter/docs/common-ekf-sources.html | primary | A
- ArduPilot — Optical Flow Sensors (setup and calibration) | https://ardupilot.org/copter/docs/common-optical-flow-sensor-setup.html | primary | A
- ArduPilot — Rangefinders (landing page) | https://ardupilot.org/copter/docs/common-rangefinder-landingpage.html | primary | A

## checklist
- I know the three main barometer errors and what they look like in the log
- I connected and checked the rangefinder
- I understand the formula v = (flow − ω)·h and why flow needs a rangefinder
- I built an EK3_SRC set for my scenario and justified it
- Hold without GPS is demonstrated in SITL
