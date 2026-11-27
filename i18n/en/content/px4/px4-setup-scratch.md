---
id: px4-setup-scratch
source: content/px4/px4-setup-scratch.md
source_hash: 9ea550d96ca6
title: "PX4 from scratch: Vehicle Setup in QGroundControl"
level: L2
readingTime: 55 min
firmware: PX4 1.18 (checked against the v1.18.0 source; SITL output captured on v1.15.4, SIH)
status: published
tags:
  - PX4
  - QGroundControl
  - setup from scratch
  - failsafe
  - power calibration
related:
  - px4-intro
  - px4-architecture
  - px4-control
  - f-motors-esc
  - link-elrs
  - link-protocols
next:
  - px4-control
---

## summary
One multirotor, from a blank flight controller to a logged first hover on PX4 1.18 (the lab output was captured on v1.15.4), in the order of 17 setup steps. You go through half the steps in SITL (`make px4_sitl sihsim_quadx` or `gz_x500` + QGroundControl): airframe, motor geometry, motor test, modes, failsafe with failure injection, autotune, the log and a parameter export. The rest is on the bench without props and in the field: the `*_CONFIG` ports, a CRSF/ELRS receiver, radio calibration, DShot or PWM with ESC calibration, `BAT1_V_DIV` and `BAT1_A_PER_V` from a multimeter and the charger, a first hover in Position. The lab: exported parameters, a motor test against the geometry, RC loss and low battery in a ULog, and a Flight Review report of the first flight.

## theory
### What is new here and what is a reference
The px4-intro module gives the general order of the QGC screens, px4-architecture the modules and uORB, px4-control the cascade and tuning. Motor protocols are in f-motors-esc, the receiver and ELRS binding in link-elrs, the CRSF frame and UART wiring in link-protocols. Here is what the course did not yet have for PX4: ports, RC input, Actuators, power, failsafe with testing, the hover, the backup.

{{diagram:px4-setup-flow|Of the 17 steps, SITL covers airframe, motor test, modes, failsafe, RTL, autotune and the log; the receiver, ESCs, sensors and power are done only on hardware, and props go on at step 15.}}

### Three things PX4 does differently
- **A port is assigned to a function, not a function to a port.** Each service has its own `*_CONFIG` / `*_CFG` parameter: `MAV_0_CONFIG` (TELEM1 by default), `MAV_1_CONFIG` (usually for TELEM2, 0 = Disabled by default), `GPS_1_CONFIG` (GPS1), `RC_PORT_CONFIG`, `RC_CRSF_PRT_CFG`, `MSP_OSD_CONFIG`, `DSHOT_TEL_CFG`. After choosing the port, reboot, and then the port baud rate `SER_<port>_BAUD` appears: `SER_GPS1_BAUD` (0 = Auto), for MAVLink on TELEM1 `SER_TEL1_BAUD` (57600). `MAV_0_RATE` is not the port baud rate but the ceiling of the MAVLink stream in bytes/s (1200; 0 = baud/20). PX4 will neither forbid nor warn about two drivers on one port: you have to free the port by setting the other `*_CONFIG` to Disabled. The fmu-v6x port numbers, the parameters of all the peripherals (GPS, compass, rangefinders, airspeed sensor, DroneCAN, OSD) and how to find a port conflict by the `Conflicting config` line in `dmesg` are covered in `px4-hardware-peripherals`.
- **An output is assigned to a function.** In Actuators each output gets a function: `PWM_MAIN_FUNCn` / `PWM_AUX_FUNCn` = 101…112 for Motor 1…12. The protocol is chosen per timer group (`PWM_MAIN_TIMx` / `PWM_AUX_TIMx`: −5 / −4 / −3 = DShot150 / 300 / 600, since 1.18 −8 / −7 / −6 = the same with bidirectional DShot, −1 = OneShot, 50…400 = PWM, Hz; the value −2 = DShot1200 existed only in 1.15 and was removed in 1.16). The geometry is in `CA_*`: `CA_ROTOR_COUNT`, `CA_ROTORn_PX/PY` (m, FRD from the center of mass), `CA_ROTORn_KM` (> 0 CCW, < 0 CW).
- **Failsafe comes with a delay.** Most actions first give Hold for `COM_FAIL_ACT_T` = 5 s (the pilot can take over), then the action. SITL starts with different defaults than a flight controller: `COM_RC_IN_MODE` = 1 (MAVLink joystick only), `COM_LOW_BAT_ACT` = 3 (2 before 1.16), `SYS_FAILURE_EN` = 1, `MC_AT_EN` = 1, `SDLOG_MODE` = 1. Do not carry a `.params` file from SITL over to a vehicle.

### RC input: CRSF/ELRS
Two drivers. `crsf_rc` is a dedicated CRSF driver: port `RC_CRSF_PRT_CFG`, telemetry `RC_CRSF_TEL_EN`. `rc_input` is the generic one: it parses CRSF among others (`RC_INPUT_PROTO`: −1 auto, 6 CRSF) on the `RC_PORT_CONFIG` port. Which one your firmware has depends on the board and version, and you can see it by which parameter QGC shows. In 1.17 the fmu-v6x, fmu-v6xrt and fmu-v5x default builds include the `crsf_rc`, `sbus_rc`, `dsm_rc`, `ghst_rc` set and do not include `rc_input`: there ELRS is set up through `RC_CRSF_PRT_CFG`. fmu-v5 has both that set and `rc_input`; fmu-v6c has neither (checked against `default.px4board` v1.17.0). Before 1.17 it was different: the fmu-v6x default build had `rc_input` (`RC_PORT_CONFIG`), and `crsf_rc` required your own build via `make <board> boardconfig` with `rc_input` disabled; the CRSF Telemetry page of the 1.17 documentation still describes that procedure. The RC IN port through the Pixhawk IO processor understands SBUS/DSM/PPM/ST24/SUMD, but not CRSF: ELRS is connected to a UART (TELEM2, GPS2).

### Power: how PX4 computes voltage, current and remaining charge
From `analog_battery.cpp`: `V = V_adc · BAT1_V_DIV`, `I = (V_adc − BAT_V_OFFS_CURR) · BAT1_A_PER_V`. Both coefficients are in the numerator, so calibration is a proportion:

| What | Formula | What to measure with |
|---|---|---|
| Divider | `BAT1_V_DIV_new = BAT1_V_DIV_old × V_multimeter / V_QGC` | a multimeter on the balance lead or the XT60 |
| Current | `BAT1_A_PER_V_new = BAT1_A_PER_V_old × mAh_charger / mAh_log` | the charger after a flight; a clamp meter for a cross-check |

Remaining charge (`battery.cpp`): the cell voltage, corrected for the load (`+ R · I`, where R is `BAT1_R_INTERNAL` if it is ≥ 0, otherwise the resistance PX4 estimates in flight; default −1, initial estimate 0.005 Ω per cell; without a current sensor there is no correction), is interpolated linearly between `BAT1_V_EMPTY` (3.6 V) and `BAT1_V_CHARGED` (4.05 V). With `BAT1_CAPACITY` > 0 the current integral is added to this; the documentation recommends ≈ 90 % of the rated capacity. Thresholds: `BAT_LOW_THR` 0.15, `BAT_CRIT_THR` 0.07, `BAT_EMERGEN_THR` 0.05. Before 1.16 the formula was different: `BAT1_R_INTERNAL` defaulted to 0.005 Ω, and without a current sensor `throttle · BAT1_V_LOAD_DROP` was added (the parameter was removed in 1.16). The action is `COM_LOW_BAT_ACT`: 0 warning (the default on a flight controller), 2 Land, 3 Return at critical and Land at emergency.

### Hover throttle and thrust-to-weight
`MPC_THR_HOVER` (0.5) is the starting value. In flight the hover thrust estimator refines it (the `hover_thrust_estimate` topic; in 1.18 it is always on, and the `MPC_USE_HTE` switch was removed). With linear thrust the hover fraction = m·g / (n·T_max) = 1/(T/W). A real prop gives thrust closer to the square of the signal, which `THR_MDL_FAC` accounts for: `thrust = f·s² + (1 − f)·s`.

### What saves itself, what waits for a reboot, and what the airframe sets
The rule for every parameter you change: the input is the parameter name; the decision is from the table; the check is the value after a reboot in QGC → Parameters.

| What you change | When it takes effect | How to check |
|---|---|---|
| An ordinary parameter (gains, thresholds, failsafe) | at once; it is written to flash/SD by itself by autosave (`autosave.cpp`), no separate `param save` needed | the value is visible after a reboot |
| A `*_CONFIG` port, `BAT1_V_DIV` / `BAT1_A_PER_V`, `SENS_EN_*`, `MC_AT_EN` | only after a reboot: the first three are marked "reboot required" in their description, and `MC_AT_EN` is read by the `rc.mc_apps` startup script | the driver shows up in `<module> status`, the port in `dmesg` |
| `SYS_AUTOSTART` (airframe) | after Apply and Restart: `SYS_AUTOCONFIG` = 1 resets every parameter except the `CAL_*` calibrations (and also `TC_*`, `LND_FLIGHT*`, `COM_FLIGHT*`; before 1.18 `RC*` and `COM_FLTMODE*` were kept too, `rcS` v1.18.0), then the airframe script sets its own defaults again | `param show SYS_AUTOSTART` shows the new number; `param show-for-airframe` prints only the differences from the defaults: the calibrations remain (before 1.18, the modes too); in 1.18 you redo the radio calibration and the modes |

The details (storage, BSON, `param reset`) are in `px4-console-params`.

On top of the parameter defaults, the multirotor airframe runs `rc.mc_defaults` (v1.17.0; in v1.18.0 the `NAV_ACC_RAD` line was removed from it). That is why the value "from the parameter documentation" is not what you will see in QGC on a quadcopter:

| Parameter | Parameter default | `rc.mc_defaults` sets | Where it matters |
|---|---|---|---|
| `IMU_GYRO_RATEMAX` | 400 Hz | 800 Hz (only if it is 400) | the angular rate loop frequency, `px4-control` |
| `RTL_RETURN_ALT` | 60 m | 30 m | step 11 below; for a plane `rc.fw_defaults` sets 100 m |
| `RTL_DESCEND_ALT` | 30 m | 10 m | the altitude at which Return moves on to landing |
| `NAV_ACC_RAD` | 10 m | 2 m in 1.15–1.17; in 1.18 the line is gone, a multirotor has 10 m | the mission waypoint acceptance radius |
| `EKF2_RNG_FOG` | 3.0 m | 1.0 m (since 1.16) | rangefinder, `nav-indoor` |
| `GPS_UBX_DYNMODEL` | 7 | 6 in 1.15 and 1.16; in 1.17 the line is gone | `px4-hardware-peripherals` |

### What changed in 1.16 and 1.17 (for old instructions and `.params`)
The 1.17 → 1.18 migration (stick takeover, bidirectional DShot per group, `NAV_ACC_RAD`, `FD_ACT_EN`, `SENS_MAG_AUTOCAL`, converting `.params` with the `Tools/migrate_param_file.py` script) is a separate table in `px4-intro`; here are the earlier changes.

The input is an instruction or a `.params` file for 1.15; the decision is from the table row; the check is whether the parameter exists in QGC → Parameters on 1.17 firmware.

| Was in 1.15 | In 1.16 / 1.17 | What to do |
|---|---|---|
| `RC_MAP_ACRO_SW`, `RC_MAP_MAN_SW`, `RC_MAP_POSCTL_SW`, `RC_MAP_RATT_SW`, `RC_MAP_STAB_SW` | removed in 1.16 | modes only through `RC_MAP_FLTMODE` + `COM_FLTMODE1…6`; `RC_MAP_ARM_SW`, `RC_MAP_KILL_SW`, `RC_MAP_RETURN_SW`, `RC_MAP_LOITER_SW` remain, and 1.17 added `RC_MAP_TERM_SW` |
| `COM_POS_FS_DELAY` | removed in 1.16 | position loss is in `px4-safety-return` |
| `BAT1_V_LOAD_DROP`, `BAT1_R_INTERNAL` = 0.005 | `BAT1_V_LOAD_DROP` removed in 1.16, `BAT1_R_INTERNAL` = −1 (estimated in flight) | see "Power" above |
| eRPM only from ESC telemetry over UART (`DSHOT_TEL_CFG`) | since 1.16 bidirectional DShot: `DSHOT_BIDIR_EN`; in 1.18 the −6/−7/−8 values in the group's `PWM_AUX_TIMx` | `px4-outputs-servos`, `px4-control` |
| `EKF2_OF_CTRL` = 0 | the default is 1 since 1.16: optical flow is fused as soon as there is a sensor | `nav-indoor` |
| DShot1200 (`PWM_*_TIMx` = −2) | removed in 1.16 | DShot600 |
| Unversioned ROS 2 topics | versioned messages get a `_vN` suffix: in 1.16 `vehicle_status_v1`, in 1.17 also `vehicle_local_position_v1`, `battery_status_v1` and others | `px4-ros2` |

### Place in the system

- **Takes in:** the order of QGC screens and the defaults (`px4-intro`); the motor protocol (`f-motors-esc`); the ELRS receiver and the CRSF frame (`link-elrs`, `link-protocols`).
- **Gives out:** used and free ports to the peripherals layout (`px4-hardware-peripherals`); output functions and the `CA_*` geometry to control allocation (`px4-control`); `BAT1_V_DIV` and `BAT1_A_PER_V` to the remaining-charge estimate and `COM_LOW_BAT_ACT`; the free TELEM2 port to the companion (`px4-companion-jetson`); the first ULog to Flight Review.
- **If you get it wrong here:** two drivers on one port, and QGroundControl will not stop you; at boot only the first one starts and the second silently does not (a `Conflicting config` line in `dmesg`, absent on boards with a trimmed firmware, see `px4-hardware-peripherals`) → the receiver or the bridge to the companion goes silent (`px4-companion-jetson`). `BAT1_A_PER_V` not calibrated against the charger → the remaining charge is computed wrong → the low-battery failsafe fires at the wrong time; cross-check with the charger's mAh and the ULog (`px4-intro`).

## practice
### Step 1. Firmware → SITL build (step 1 of 17)
Instead of flashing, a SITL build. I built v1.15.4 in a container (2 cores, 7 GB): `make px4_sitl_default` is 1024 targets. I installed the Python dependencies in a venv from `Tools/setup/requirements.txt`, not with the `ubuntu.sh` script. There is no Gazebo in the container, so the main path here is SIH: the physics is computed inside PX4 itself. With Gazebo the command is the same as in px4-intro: `make px4_sitl gz_x500`.

The output was captured on v1.15.4; in 1.17 and 1.18 the `sihsim_quadx` and `gz_x500` targets have the same names; for the target release clone `--branch v1.18.0` (SITL v1.18.0 with `sihsim_quadx` was built and run while preparing the move to 1.18; the output below was not recaptured; 1.18 prints the same 250 Hz line plus `Simulation with 1.0x speedup. Loop with (4000 us wall time interval)`).
```
git clone --branch v1.15.4 --recursive https://github.com/PX4/PX4-Autopilot.git
cd PX4-Autopilot && bash ./Tools/setup/ubuntu.sh --no-nuttx
HEADLESS=1 make px4_sitl sihsim_quadx
```
```
INFO  [init] found model autostart file as SYS_AUTOSTART=10040
INFO  [simulator_sih] Simulation loop with 250 Hz (4000 us sim time interval)
INFO  [logger] Opened full log file: ./log/2026-11-10/20_22_32.ulg
pxh> INFO  [commander] Ready for takeoff!
```
QGC connects by itself over UDP 14550. All the commands below are typed in `pxh>` or in QGC → Analyze Tools → MAVLink Console.

### Step 2. Airframe and geometry (2)
The airframe is set by `SYS_AUTOSTART`: 10040 is SIH Quad X, 4001 is gz_x500, and on hardware 4001 is Generic Quadcopter. Changing the airframe overwrites the parameters. Check the geometry:
```
pxh> param show CA_ROTOR0_KM
x   CA_ROTOR0_KM [132,252] : 0.0500
```
| Motor | `PX` | `PY` | `KM` | Where and which way |
|---|---|---|---|---|
| 1 | 1 | 1 | 0.05 | front right, CCW |
| 2 | −1 | −1 | 0.05 | rear left, CCW |
| 3 | 1 | −1 | −0.05 | front left, CW |
| 4 | −1 | 1 | −0.05 | rear right, CW |

This is PX4 numbering, not Betaflight: there motor 1 is rear right. `PWM_MAIN_FUNC1…4` = 101…104.

### Step 3. Ports, receiver, radio, protocol (3–6): what SITL cannot do
SITL has no UART: MAVLink goes over UDP, and the RC input is the QGC joystick (`COM_RC_IN_MODE` = 1). SITL does not cover steps 3–6, 8–10 and 13. They are below, in "Moving to real hardware".

### Step 4. Motor test (7)
```
pxh> actuator_test set -m 3 -v 0.15 -t 3
pxh> listener actuator_outputs -n 1
    output: [900.00000, 900.00000, 1150.00000, 900.00000, ...]
```
Only output 3 spins: 900 µs is disarmed, 1000 + 0.15 × 1000 = 1150 µs. In QGC this is Actuators → Enable sliders. Write down the table "slider → which motor → which way it spins". SITL checks only the number; the direction is checked on the bench.

### Step 5. Modes and arming (11; steps 8–10 are hardware only)
```
pxh> commander check
INFO  [commander] Preflight check: OK
```
In QGC → Flight Modes: the `RC_MAP_FLTMODE` channel, the `COM_FLTMODE1…6` slots (0 Manual, 1 Altitude, 2 Position, 4 Hold, 5 Return, 8 Stabilized; 1.17 added 16, Altitude Cruise). The arm switch is `RC_MAP_ARM_SW`, `COM_ARM_SWISBTN` = 0 (switch) or 1 (button). Kill is `RC_MAP_KILL_SW`. Without a takeoff PX4 disarms by itself after `COM_DISARM_PRFLT` = 10 s.

### Step 6. Failsafe with failure injection (12, 14)
Injection works with `SYS_FAILURE_EN` = 1 (the default in SITL). `failure rc_signal off` is not implemented in SIH. The output of this step was captured on v1.15.4; in 1.17 there is no `rc_signal` handler either (the battery is handled by `battery_simulator`, the motors by `FailureInjector`), and in 1.18 the new `failure_injection_manager` rejects it explicitly (the console prints `ERROR [failure] Result: 3`, UNSUPPORTED; supported are the sensors, GPS, airspeed, motors, battery):
```
pxh> failure rc_signal off
ERROR [failure] Timeout waiting for ack
```
So I did the RC loss honestly: a pymavlink script (`udpin:0.0.0.0:14550`) sends `MANUAL_CONTROL` at 20 Hz like a joystick, takeoff, Position, and after 25 s the sending stops. The real log:
```
[  38.0 s] >>> joystick (manual control) stopped
[  39.4 s] mode=HOLD armed=True
[  44.5 s] mode=RTL armed=True
[  54.6 s] mode=POSCTL armed=False
WARN  [failsafe] Failsafe activated: entering Hold for 5 seconds
INFO  [navigator] RTL: start return at 35 m (3 m above destination)
INFO  [commander] Disarmed by landing
```
The chain: 0.5 s of `COM_RC_LOSS_T` (plus the detector delay) → Hold for `COM_FAIL_ACT_T` = 5 s → `NAV_RCL_ACT` = 2 (Return) → landing → disarm on landing (`COM_DISARM_LAND` = 2 s). The vehicle was 3 m from home, so RTL did not climb to `RTL_RETURN_ALT`. In 1.18 the multirotor `NAV_ACC_RAD` = 10 m (2 m in 1.15–1.17), and closer than 10 m to home the return altitude is computed as 2·d (`px4-safety-return`): the number in the `RTL: start return` line will be different.

Battery: `failure battery off` substitutes a voltage of 3.6 V/cell (14.4 V). With the 1.15 defaults (`BAT_CRIT_THR` 0.07), in a hover only LOW arrives: the `BAT1_V_LOAD_DROP` load compensation adds 0.49 × 0.1 = 0.049 V, and the remaining charge is (3.649 − 3.6)/0.45 = 0.109. 1.17 and 1.18 have no such parameter (the correction is `R · I` from the current), and SITL sets `COM_LOW_BAT_ACT` = 3 by itself, so the levels and times on 1.17 and 1.18 will differ; the log below was captured on v1.15.4. In 1.18 value 3 also enables the return on remaining flight time, but in SITL `BAT1_CAPACITY` = −1 (checked with `param show` on v1.18.0), there is no time estimate, and it does not trigger. For the test I set `COM_LOW_BAT_ACT 3`, `BAT_CRIT_THR 0.12`, `BAT_LOW_THR 0.20`:
```
[  38.0 s] failure cmd output: WARN  [failure] inject failure unit: battery (100), type: off (1), instance: 0
[  40.1 s] vehicle_status: nav_state=POSCTL armed; battery 14.40000 V warning=1
[  42.2 s] vehicle_status: nav_state=AUTO_LOITER(Hold) armed; battery 14.40000 V warning=2
[  47.2 s] vehicle_status: nav_state=AUTO_RTL armed; battery 14.40000 V warning=2
[  59.4 s] vehicle_status: nav_state=AUTO_RTL armed; battery 14.40000 V warning=3
[  60.0 s] vehicle_status: nav_state=AUTO_LAND armed; battery 14.40000 V warning=3
[  62.5 s] vehicle_status: nav_state=POSCTL disarmed; battery 14.40000 V warning=3
```
The conclusion: check the thresholds on the real voltage under load, not from a table.

### Step 7. Hover, autotune, log and backup (15–17)
The calculation for SIH: `SIH_MASS` 1 kg, `SIH_T_MAX` 5 N per motor → T/W = 20 / 9.81 = 2.04 → hover fraction 0.4905. The estimator in the log:

{{diagram:chart-px4-hte|HTE converges to 0.488–0.493 in ~25 s and matches the 1/(T/W) = 0.4905 calculation; MPC_THR_HOVER = 0.5 is only the starting point.}}

Autotune: Position at 2.5 m, `MAV_CMD_DO_AUTOTUNE_ENABLE` (in QGC, PID Tuning → Start AutoTune). According to `autotune_attitude_control_status` the identification took 26 s (35.4 → 61.2 s from arming), and the gains were applied after disarm (`MC_AT_APPLY` = 1). The table was captured on v1.15.4: the starting `MC_ROLL_P` there is 6.5, while the 1.17 default is 4.0:

| Parameter | Before | After |
|---|---|---|
| `MC_ROLLRATE_P` | 0.1500 | 0.1564 |
| `MC_ROLLRATE_D` | 0.0030 | 0.0001 |
| `MC_PITCHRATE_P` | 0.1500 | 0.1567 |
| `MC_ROLL_P` | 6.5000 | 6.1074 |

D near zero is a property of SIH: a model with no delays or noise. That does not happen on a real frame.

Backup. `param save <file>` writes binary BSON. QGC → Parameters → Tools → Save to file saves a text `.params`. The changes relative to the airframe, in the console:
```
pxh> param show-for-airframe
param set-default BAT_CRIT_THR 0.1200
param set-default COM_LOW_BAT_ACT 3
param set-default MC_ROLLRATE_P 0.1564
# Make sure to add all params from the current airframe (ID=10040) as well
```
The SITL log is in `build/px4_sitl_default/rootfs/log/<date>/`; from hardware, QGC → Analyze Tools → Log Download, then upload it to review.px4.io.

### Moving to real hardware
Example: a 450–500 mm frame, a Pixhawk FMUv6, 4S 5000 mAh, a 1.6 kg takeoff weight, ESCs with PWM or DShot. **Props stay off until item 13.**

1. **Firmware.** QGC → Vehicle Setup → Firmware; plug in USB after the screen is open, PX4 Pro, stable release. If firmware was already installed, first Parameters → Save to file (the old configuration).
2. **Airframe** (Generic Quadcopter, 4001) → Apply and Restart. Board orientation `SENS_BOARD_ROT`; the GPS compass is detected by itself (`SENS_MAG_AUTOROT` = 1).
3. **Ports.** GPS on GPS1 (`GPS_1_CONFIG`), telemetry on TELEM1 (`MAV_0_CONFIG`). For ELRS on TELEM2: check that `MAV_1_CONFIG` = Disabled (that is the default; if TELEM2 was given to a companion, turn it off), then `RC_CRSF_PRT_CFG` = TELEM 2 (`crsf_rc`; the fmu-v6x default build in 1.17) or `RC_PORT_CONFIG` = TELEM 2 (`rc_input`; fmu-v6x before 1.17, fmu-v5), reboot. The controller's TX goes to the receiver's RX, RX to TX.
4. **Receiver.** Binding and packet rate per link-elrs. Check: in Radio all the sliders move, ≥ 8 channels.
5. **Radio calibration.** QGC → Radio → Calibrate: it writes `RC1_MIN/TRIM/MAX`…, `RC_MAP_*`. Normal is about 1000/1500/2000 µs. Then the modes and arm/kill from SITL step 5.
6. **Protocol.** Actuators: motors on FMU outputs. On a Pixhawk with IO, DShot works only on AUX; MAIN goes through IO. Timer group → DShot600 (if the ESC supports it) or PWM 400 Hz.
7. **Order and direction.** The sliders one at a time at 10–15 %. The motor number per the step 2 table, the direction per the arrows in the diagram. Wrong direction with DShot: `dshot reverse -m 2`, then `dshot save -m 2`; with PWM, swap two phase wires. Disarmed, the motor is stopped; at minimum it barely spins.
8. **ESC calibration (PWM/OneShot only).** FC on USB, battery disconnected, QGC → Power → Calibrate, connect the battery when prompted. Calibration runs at 1000/2000 µs. After the Motor function is assigned in Actuators, the driver itself writes min/max = 1100/1900 µs (the parameter defaults are 1000/2000); disarmed stays 1000 µs. DShot needs no calibration. The limits are set per output: `PWM_MAIN_MINn` / `PWM_MAIN_MAXn` / `PWM_MAIN_DISn` / `PWM_MAIN_FAILn` (on AUX, `PWM_AUX_*`); the rule "raise the minimum until the motor barely spins, the same on all motors" and the details for servos are in `px4-outputs-servos`.
9. **Sensors.** Accelerometer (6 positions), Gyroscope (still), Compass (rotation, away from metal), Level Horizon (on a level surface).
10. **Power.** QGC → Power: `BAT1_N_CELLS` 4, `BAT1_V_EMPTY` 3.6, `BAT1_V_CHARGED` 4.05. Voltage: QGC shows 16.42 V, the multimeter 16.71 V, `BAT1_V_DIV` 18.000 → 18.000 × 16.71 / 16.42 = 18.318 (the error was 0.072 V/cell). The Calculate button in QGC computes the same proportion. The default of `BAT1_V_DIV` and `BAT1_A_PER_V` in the parameter itself is −1 ("board value"): the number is set by the board's `rc.board_defaults` script (fmu-v6c: 18.1 and 36.37), and the `analog_battery.cpp` code does no substitution. If you see −1 in QGC, the board did not set an analog divider: enter the coefficient from the power module's datasheet, then calibrate by proportion; both parameters require a reboot. Current is checked after the first flight: the log shows 2310 mAh, the charger put in 2465 → `BAT1_A_PER_V` 36.0 × 2465 / 2310 = 38.416. `BAT1_CAPACITY` = 4500.
11. **Failsafe.** `COM_LOW_BAT_ACT` = 3 (in 1.18, with `BAT1_CAPACITY` set at step 10, this also means a return on remaining flight time: Return may start before the critical level; if you do not want that, 5), `NAV_RCL_ACT` = 2, `RTL_RETURN_ALT` above obstacles (the multirotor airframe sets 30 m, `RTL_DESCEND_ALT` 10 m; 60 m is the default of the parameter itself), `GF_ACTION` for the task (default 2 = Hold). The radius geofence is off while `GF_MAX_HOR_DIST` = 0 (and `GF_MAX_VER_DIST` = 0): for the first flight set a radius and height with margin over the flying area, for example 150 m and 60 m. QGC link loss `NAV_DLL_ACT` = 0 is off. The decision: if you fly with a transmitter and telemetry is only for monitoring, leave 0 (otherwise a SiK radio dropout at the edge of the area triggers Return while the transmitter is fine); if you fly a mission without a transmitter and QGC is the only link, set 2 (Return) after `COM_DL_LOSS_T` = 10 s. The whole matrix is in `px4-safety-return`. On the bench, without props and disarmed: switch the transmitter off → QGC shows a manual control loss message, and in the console `listener failsafe_flags` → `manual_control_signal_lost: True`.
12. **OSD and telemetry.** MSP OSD: `MSP_OSD_CONFIG` on a free UART, if the driver is in the board's build. In the v1.17.0 default builds `msp_osd` is in px4 fmu-v5x, fmu-v6x, fmu-v6xrt, ark fpv, cuav 7-nano, cuav fmu-v6x, cuav x25-evo, micoair h743 / h743-aio / h743-v2, radiolink PIX6, hkust nxt-dual, zeroone x6, accton-godwit ga1, nxp tropic-community and mr-tropic, modalai voxl2 (and SITL); v1.18.0 added the new boards aedrox aedroxh7, corvon 743v2, cuav x25-mega and x25-super, gearup airbrainh743, svehicle e2; in 1.15.4 only fmu-v5x, fmu-v6x, fmu-v6xrt and voxl2 (and SITL). fmu-v6c and fmu-v5 do not have it: no `MSP_OSD_CONFIG` parameter → you need your own build (`px4-console-params`); since 1.16 the driver sends MSP DisplayPort (before 1.16, DJI legacy MSP elements), and PX4 does not document compatibility with particular goggles. Otherwise, telemetry on the transmitter over CRSF (`RC_CRSF_TEL_EN`).
13. **Preflight check and hover.** Props per the CW/CCW diagram. GPS ≥ 10 satellites, "Ready To Fly", the kill switch under your finger, 10 m from people. Take off in Position, 2–3 m, 60 s of hover, 2 m to each side, land. Abort (kill or Land) if: oscillation above ±5°, drift over 1 m with the sticks released, "toilet bowling" (circling, the compass), hover throttle above 0.7.
14. **In-air failsafe test.** Position at 10 m, transmitter off → Hold 5 s → Return. Switch the transmitter on and take over with a mode change.
15. **Autotune.** First `MC_AT_EN` = 1 and a reboot: on a flight controller the default is 0 and the module is not running, while SITL sets 1 by itself. Altitude, 4–20 m, calm air. The order is as in SITL step 7, but with the filters and vibration checked beforehand per px4-control.
16. **Log and backup.** The ULog to Flight Review: vibration, hover throttle, RC and battery. The `.params` from QGC goes into the vehicle's repository.

Self-check: the lab is done when:
- **SITL:** the motor table (number, position, KM) matches `CA_ROTOR*`; the log has the chain RC loss → Hold → Return → disarm and battery → Hold → Return → Land with times; HTE matched the 1/(T/W) calculation within 0.01; the autotune before/after table is filled in (in SIH `MC_ROLLRATE_D` after tuning is near zero, a model with no delays or noise) and the `param show-for-airframe` output is saved.
- **Hardware:** an exported `.params`; the motor test table matches the airframe geometry; the voltage error < 0.05 V/cell; log mAh within 5 % of the charger after correcting `BAT1_A_PER_V`; RC loss and low battery are visible in the ULog (`failsafe_flags`, a `nav_state` change); a Flight Review report of the first 60-second hover in Position.

## diagnostics
- **Symptom:** the ELRS receiver shows "link up", but the channels in QGC Radio do not move
  - Possible cause: the receiver is connected to RC IN through IO (CRSF is not parsed there), the port is taken by MAVLink (`MAV_1_CONFIG`), or TX/RX are swapped.
  - What to do: UART + `RC_PORT_CONFIG` or `RC_CRSF_PRT_CFG`, free the port, reboot; in the MAVLink Console, `rc_input status` or `crsf_rc status`.
- **Symptom:** `RC_CRSF_PRT_CFG` is not in the parameter list
  - Possible cause: the `crsf_rc` driver is not built for this board (common before 1.17; in 1.17 and 1.18 fmu-v6x has it, and it is `RC_PORT_CONFIG` that is missing).
  - What to do: `rc_input` on a UART, or your own build via `boardconfig`.
- **Symptom:** one motor does not spin in the Actuators test, the others do
  - Possible cause: the output is not assigned Motor N, or DShot is set on MAIN through IO.
  - What to do: `PWM_AUX_FUNCn` = 10x, the protocol on the AUX group.
- **Symptom:** on arming one motor does not start, or starts later
  - Possible cause: a PWM ESC without calibration, a min of 1100 µs below its start point.
  - What to do: ESC calibration in Power (USB, no props), or raise the minimum until the motor barely spins.
- **Symptom:** the vehicle flips over right at takeoff
  - Possible cause: the motor order or direction does not match `CA_ROTOR*`, the props are swapped.
  - What to do: redo the motor test against the table, check CW/CCW.
  - Consequences: broken props, a risk to people nearby.
- **Symptom:** "Low battery" in flight although the battery is full; or the opposite, it lands at 3.3 V/cell without a warning
  - Possible cause: `BAT1_V_DIV` is not calibrated, `BAT1_N_CELLS` is not set, `COM_LOW_BAT_ACT` = 0.
  - What to do: calibrate with a multimeter, the thresholds, action 3.
  - What you see in the log: `battery_status.voltage_v` differs from the multimeter by a constant percentage.
- **Symptom:** the log mAh is 7–10 % less than what the charger put in
  - Possible cause: a `BAT1_A_PER_V` from a different power module.
  - What to do: multiply by mAh_charger / mAh_log, verify with one more flight.
- **Symptom:** after RC loss the vehicle hovers for 5 s and only then heads home
  - Possible cause: this is normal: Hold for `COM_FAIL_ACT_T`.
  - What to do: account for it when planning distance; reduce the delay only deliberately.
- **Symptom:** `failure rc_signal off` in SITL answers "Timeout waiting for ack" (1.15–1.17) or "Result: 3" (1.18)
  - Possible cause: this injection is not handled in the simulators (the response was captured on 1.15.4; the 1.17 sources have no handler either, and in 1.18 `failure_injection_manager` reports it as unsupported).
  - What to do: simulate the loss by stopping `MANUAL_CONTROL` (the QGC joystick or a script).

## references
- PX4 User Guide v1.17 — Actuator Configuration and Testing | https://docs.px4.io/v1.17/en/config/actuators.html | primary | A
- PX4 User Guide v1.17 — ESC Calibration | https://docs.px4.io/v1.17/en/advanced_config/esc_calibration.html | primary | A
- PX4 User Guide v1.17 — Battery Estimation Tuning | https://docs.px4.io/v1.17/en/config/battery.html | primary | A
- PX4 User Guide v1.17 — Serial Port Configuration | https://docs.px4.io/v1.17/en/peripherals/serial_configuration.html | primary | A
- PX4 User Guide v1.17 — CRSF Telemetry (TBS Crossfire / ExpressLRS) | https://docs.px4.io/v1.17/en/telemetry/crsf_telemetry.html | primary | A
- PX4 User Guide v1.17 — DShot ESCs | https://docs.px4.io/v1.17/en/peripherals/dshot.html | primary | A
- PX4 User Guide v1.15 — Safety Configuration (Failsafes) | https://docs.px4.io/v1.15/en/config/safety.html | primary | A
- PX4 User Guide v1.17 — System Failure Injection | https://docs.px4.io/v1.17/en/debug/failure_injection.html | primary | A
- PX4 User Guide v1.17 — Multicopter Auto-Tuning | https://docs.px4.io/v1.17/en/config/autotune_mc.html | primary | A
- PX4 User Guide v1.17 — Simulation-In-Hardware (SIH) | https://docs.px4.io/v1.17/en/sim_sih/ | primary | A
- PX4-Autopilot v1.17.0 — analog_battery.cpp (V_DIV, A_PER_V) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/battery_status/analog_battery.cpp | primary | A
- PX4-Autopilot v1.17.0 — battery.cpp (state of charge) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/lib/battery/battery.cpp | primary | A
- QGroundControl User Guide — Power Setup | https://docs.qgroundcontrol.com/Stable_V4.3/en/qgc-user-guide/setup_view/power.html | primary | A
- PX4 User Guide v1.17 — Radio Control Systems | https://docs.px4.io/v1.17/en/getting_started/rc_transmitter_receiver.html | primary | B

## checklist
- The SITL build works, QGC is connected
- The `CA_ROTOR*` geometry and the motor test match the frame
- Ports are freed and assigned through `*_CONFIG`, the reboot is done
- ELRS on a UART, the channels move in Radio, the radio calibration is done
- DShot on FMU outputs, or the PWM ESCs are calibrated
- `BAT1_V_DIV` and `BAT1_A_PER_V` are calibrated against the multimeter and the charger
- RC loss and low battery are tested in SITL and on the bench
- The first hover in Position is logged, the log is in Flight Review, the `.params` is saved
