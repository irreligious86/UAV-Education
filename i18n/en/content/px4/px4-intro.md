---
id: px4-intro
title: "Introduction to PX4"
level: L2
readingTime: 20 min
firmware: PX4 1.14+
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
source_hash: 0121c386b29e
---

## summary
PX4 is the second big open-source autopilot next to ArduPilot. It grew out of academia and is closer to research tasks: a modular architecture, strict interfaces, deep integration with ROS 2. This module explains how PX4 differs from ArduPilot in practice — the ground control station, flight modes, parameters, simulation, hardware requirements — and when to choose it.

## theory
### PX4 versus ArduPilot
Both firmwares are full-fledged autopilots with navigation, missions and companion interfaces. The differences are in character:

- **Ecosystem.** PX4 — the Dronecode Foundation, standards (Pixhawk, MAVLink, MAVSDK), QGroundControl as the “native” GCS. ArduPilot — the community, Mission Planner, a huge base of supported hardware.
- **Architecture.** PX4 — modules talking over the uORB bus; each module can be stopped and restarted on the fly. ArduPilot — more monolithic, but with Lua scripts inside.
- **ROS 2.** In PX4 — native via uXRCE-DDS: PX4 topics are visible in ROS 2 directly. ArduPilot (4.5+) also has a native DDS client (AP_DDS), but with a smaller set of topics.
- **Tuning.** PX4 has a well-developed autotune for multirotors and planes; the parameters are structured by loop (`MC_*RATE_*`, `MC_*_P`, `MPC_*`).

The rule of thumb: research, computer vision and ROS 2 — PX4; support for exotic hardware, Lua on board, a large community of practitioners — ArduPilot. Both fly.

### Ground control station
QGroundControl: firmware, airframe selection, calibrations, parameters, missions, log analysis (`.ulg`). It works with ArduPilot too, but for PX4 it is the main tool.

### Multirotor flight modes
- **Manual/Stabilized** — angle stabilization, manual throttle.
- **Acro** — angular rates.
- **Altitude** — altitude hold.
- **Position** — position hold by GPS; the stick sets velocity.
- **Hold**, **Return**, **Land**, **Takeoff**, **Mission**, **Orbit**, **Follow Me** — autonomous.
- **Offboard** — control from a companion computer.

As everywhere: you pick a mode by which sensors you trust. Position won't engage without a reliable GPS.

### Parameters and logs
Parameters — via QGC or the console `param set/show`. ULog logs (`.ulg`) contain all the uORB topics enabled for logging; analysis — Flight Review (web) or `pyulog`.

### Hardware
The standard is Pixhawk-compatible flight controllers (FMUv5/v6, H7). PX4 is more resource-hungry than Betaflight, and F4 boards for it are a rarity.

### Simulation
`make px4_sitl gz_x500` brings up SITL with Gazebo and the x500 quadcopter model; QGC connects by itself. For ROS 2 this is the same setup as for the real vehicle.

### First setup in QGroundControl: an order you must not break
1. **Firmware** (Firmware → PX4 stable) and **airframe** (Airframe → frame type: sets `CA_AIRFRAME`, `CA_ROTOR_COUNT`, the geometry and the starting parameters). Changing the airframe resets the parameters.
2. **Sensors**: compass (rotation about all axes), gyro (stationary), accelerometer (6 positions), level horizon; board orientation `SENS_BOARD_ROT`, the external compass — autodetected.
3. **Radio**: stick calibration, `RC_MAP_*`; modes on switches (Flight Modes), a kill switch — mandatory for tests.
4. **Motors**: Actuators — output assignment, protocol (DShot/PWM — by timer groups in Actuators, `PWM_MAIN_TIMx`), test each one **with props off**, direction according to the airframe diagram.
5. **Power**: `BAT1_N_CELLS`, calibration of the voltage divider and current against a multimeter/wattmeter, thresholds `BAT_LOW_THR`/`BAT_CRIT_THR`.
6. **Safety**: actions on RC loss (`COM_RC_LOSS_T` = 0.5 s by default, `NAV_RCL_ACT`), data link loss (`NAV_DLL_ACT`), low battery (`COM_LOW_BAT_ACT`), geofence (`GF_*`), return altitude `RTL_RETURN_ALT`.
Pre-arm checks are reported in QGC as text (“Preflight Fail: …”); the `CBRK_*` circuit breakers disable them, and only on the bench.

### Parameters: how they are organized
Names are grouped by module: `MC_*` (multirotor controllers), `MPC_*` (position), `EKF2_*`, `IMU_*`, `COM_*` (commander/failsafe), `NAV_*`, `RTL_*`, `BAT*`, `CA_*` (control allocation), `SER_*`/`MAV_*`/`UXRCE_*` (ports). The full reference with ranges and defaults is the “Parameter Reference” in the documentation (generated from the source, as with ArduPilot). Export/import — QGC → Parameters → Tools (a `.params` file), kept under version control (module “CI”).

### Numbers for orientation (defaults, multirotor)
The inner loop runs at `IMU_GYRO_RATEMAX` = 400 Hz (up to 1 kHz on fast boards); the gyro filter `IMU_GYRO_CUTOFF` = 40 Hz, D-term `IMU_DGYRO_CUTOFF` = 20 Hz — noticeably lower than Betaflight: PX4 is designed for larger and slower vehicles; for a 5" they are raised (80–120 / 40–60) together with a notch by ESC (`IMU_GYRO_DNF_EN`, needs DShot telemetry). Maximum tilt `MPC_TILTMAX_AIR` = 45°, in manual modes `MPC_MAN_TILT_MAX` = 35°; maximum speed `MPC_XY_VEL_MAX` = 12 m/s.

### ULog logs and Flight Review
Logging starts on arming (`SDLOG_MODE`) and contains uORB topics at a set rate (`SDLOG_PROFILE` — profiles: default, high rate for tuning, ...). Flight Review (web) plots: the rate response (setpoint vs actual), the vibration spectrum (acceleration power spectral density — it shows the motors and resonances), the GPS/EKF estimate (innovation test ratios — the same “gates” as in the Kalman module), CPU and RAM load, RC losses. `pyulog` (`ulog2csv`) — for analysis in Python (module “Python for data”).

{{diagram:px4-qgc-order|The order of the first PX4 setup in QGroundControl.}}

## practice
### Step 1. SITL and QGC
```
git clone https://github.com/PX4/PX4-Autopilot.git --recursive
cd PX4-Autopilot
bash ./Tools/setup/ubuntu.sh
make px4_sitl gz_x500
```

In the PX4 console (`pxh>`): `commander takeoff`, `commander land`. QGC will connect over UDP by itself.

### Step 2. Modes
In QGC switch Position → Altitude → Stabilized on the simulator and watch how the response to the stick changes (QGC has a virtual joystick).

### Step 3. Parameters and the log
`param show MPC_THR_HOVER` in the console; after the flight download the `.ulg` from QGC (Analyze → Log Download) and open it in Flight Review.

### What you should get and what to write down
- **Step 1.** The first build and the first Gazebo launch take a long time: the build takes minutes, and the world models are downloaded on the first start. After that, startup takes seconds. `commander takeoff` lifts the x500 to the takeoff altitude `MIS_TAKEOFF_ALT` (2.5 m by default) and holds it. QGC connects by itself over UDP. If there is no link, check that QGC is running on the same machine and that port 14550 isn't taken by another client.
- **Step 2.** In Position released sticks hold the spot. In Altitude only the altitude is held, and the vehicle drifts. In Stabilized the stick sets the angle, and you hold the altitude. Write one line per mode: what the autopilot holds and what the pilot does — this is the main takeaway of the module.
- **Step 3.** A mission in QGC (Plan): takeoff, three waypoints at 20 m, Return. In SITL the `.ulg` is in `build/px4_sitl_default/rootfs/log/<date>/`. In Flight Review find the roll and pitch angle plots (estimate versus setpoint) and position versus setpoint. A discrepancy of more than a few degrees in SITL means something is wrong with the setup, not the wind: there is no wind in SITL until you turn it on.

### Lab
Takeoff, a short mission from QGC and landing in SITL; the log uploaded to Flight Review, with the attitude and position setpoint plots versus actual found.

The lab counts as done when SITL `gz_x500` is running and QGC is connected, the mission has been flown through to landing, the log is open in Flight Review, and the report has two screenshots (angle and position: setpoint versus actual) with a one-sentence conclusion for each.

## diagnostics
- **Symptom:** QGC doesn't connect to SITL
  - Possible cause: another PX4 instance or a UDP port already in use.
  - What to do: close the old processes, restart SITL.
- **Symptom:** Position won't engage
  - Possible cause: no GPS fix (in SITL — wait for initialization).
  - What to do: wait for “ready for takeoff” in QGC.
- **Symptom:** the firmware won't install on an F4 board
  - Possible cause: PX4 doesn't support this hardware.
  - What to do: a Pixhawk-compatible FMUv5/v6, or ArduPilot.
- **Symptom:** `make` fails on dependencies
  - Possible cause: `ubuntu.sh` hasn't been run.
  - What to do: run the environment setup script, log in again.
- **Symptom:** “Preflight Fail: Compass sensor 0 missing” / “Accel inconsistent”
  - Possible cause: calibration not done or the sensor isn't detected (orientation, ribbon cable).
  - What to do: calibrate in order, check `SENS_BOARD_ROT`, the `dmesg` log in the console.
- **Symptom:** Position mode won't engage
  - Possible cause: the EKF doesn't trust the GPS (`EKF2_GPS_CHECK`), no fix, the compass is lying.
  - What to do: QGC → MAVLink Console `ekf2 status`, the number of satellites, compass calibration in the field.
- **Symptom:** a high vibration level in Flight Review
  - Possible cause: the mechanics, a rigid FC mount.
  - What to do: module “Frame and vibration”, dampers, balancing.

## references
- PX4 User Guide — Flight Modes (Multicopter) | https://docs.px4.io/main/en/flight_modes_mc/ | primary | A
- PX4 User Guide — Simulation | https://docs.px4.io/main/en/simulation/ | primary | A
- PX4-Autopilot — source code (GitHub) | https://github.com/PX4/PX4-Autopilot | primary | A
- QGroundControl — User Guide | https://docs.qgroundcontrol.com/Stable_V5.0/en/ | primary | A

## checklist
- I can explain when to use PX4 and when ArduPilot
- SITL with Gazebo is running, QGC is connected
- I have tried the Stabilized/Altitude/Position modes
- A .ulg log has been opened in Flight Review
