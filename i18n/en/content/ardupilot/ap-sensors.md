---
id: ap-sensors
title: "ArduPilot sensors on the bench: compass (MagFit, Large Vehicle), airspeed, multiple batteries"
level: L2
readingTime: 65 min
firmware: ArduCopter 4.7 (checked against 4.7.3)
status: published
added: 2026-11-22
tags:
  - ArduPilot
  - compass
  - MagFit
  - CompassMot
  - airspeed
  - BATT_MONITOR
  - current sensor
related:
  - ap-setup-scratch
  - ap-setup-plane
  - ap-ekf
  - ap-safety-fs
  - ap-osd-video
  - ap-outputs
  - ap-logs
  - ap-heavy
  - est-sensors
  - est-gnss
  - nav-resilience
  - el-emi
  - el-battery-packs
  - el-power-design
next:
  - ap-ekf
source: content/ardupilot/ap-sensors.md
source_hash: fd6b2485475e
---

## summary
This module covers three sensors that ArduPilot needs configured before the first flight and that most often get configured only halfway: the compass, the airspeed sensor and the battery monitors. Working from the 4.7.2 source, it goes through what the firmware does with the raw compass field (offsets, matrix, current compensation), the four calibration methods and the rule for choosing between them, the exact pre-arm failure strings, the bench side of the airspeed sensor and every `BATT_MONITOR` type from analog to "sum". After the module you choose the compass calibration method for a specific vehicle, check its result by the numbers, and lay out several batteries across monitors so that the failsafe and the OSD look at the right one. The lab is a calculation exercise with no hardware and no simulator: current interference compensation, "large vehicle" offsets, scale corrections for two monitors, a sum mask and three mistakes in a parameter file.

## theory
### How to read the module
The module covers the bench, not the flight: everything that has to be set and checked on the compass, the pitot tube and the battery sensors before takeoff. The order is: first the compass, with instances and priorities, the field correction formula, the four calibration methods, a selection table and the pre-arm failures; then a short bench part on airspeed; then the battery monitors, with types, thresholds, the "sum" and layouts for several batteries. The first calibration of a single analog monitor is in `ap-setup-scratch`, and the `ARSPD_*` parameters for flight are in `ap-setup-plane`; they are not repeated here. The behavior is described from reading the source at tag Copter-4.7.2; the firmware was not run in this pass.

### The compass: instances, priorities, external and internal
At boot the firmware finds all magnetometers, gives each one a device ID (bus type, bus number, address and chip type in one number) and sorts them into three priority slots. The parameters with the suffixes 2 and 3 refer to a **priority slot**, not to an "internal" or "external" compass.

| Parameter | Default | Values | Meaning |
|---|---|---|---|
| `COMPASS_ENABLE` | 1 | 0 / 1 | the drivers and the logging of `MAG`; needs a reboot |
| `COMPASS_USE`, `COMPASS_USE2`, `COMPASS_USE3` | 1 | 0 / 1 | whether the compass in slot 1, 2, 3 is used for yaw |
| `COMPASS_PRIO1_ID`…`PRIO3_ID` | 0 | device ID | which compass is in the slot; 0 means set automatically; needs a reboot |
| `COMPASS_DEV_ID`, `DEV_ID2`, `DEV_ID3` | 0 | read only | the device ID the calibration of the slot was saved with |
| `COMPASS_DEV_ID4`…`DEV_ID8` | 0 | read only | detected compasses beyond the three slots (up to five) |
| `COMPASS_EXTERNAL`, `EXTERN2`, `EXTERN3` | 0 | 0 Internal; 1 External; 2 ForcedExternal | with 0 and 1, auto-detection by bus connection can override the value; with 2 it cannot |
| `COMPASS_ORIENT`, `ORIENT2`, `ORIENT3` | 0 | 0 None; 2 Yaw90; 4 Yaw180; 6 Yaw270; 8 Roll180; 10 Yaw90Roll180; 12 Pitch180; 14 Yaw270Roll180 and others up to 43; 101, 102 are custom angles | the orientation of an **external** compass relative to the vehicle frame; an internal one follows `AHRS_ORIENTATION` |
| `COMPASS_AUTO_ROT` | 2 | 0 Disabled; 1 CheckOnly; 2 CheckAndFix; 3 the same with the same tolerance for 45° rotations | the orientation check at the end of a rotation calibration |
| `COMPASS_DISBLMSK` | 0 | a bitmask of driver types (bit 11 is DroneCAN, bit 7 is IST8310…) | do not look for chips of this type at startup |
| `COMPASS_OPTIONS` | 0 | bit 0 is CalRequireGPS; bit 1 allows a missing DroneCAN compass to be replaced automatically | bit 0 is worth setting, see the scale factor below |
| `COMPASS_AUTODEC`, `COMPASS_DEC` | 1; 0 rad | 0 / 1; −3.142…3.142 | the declination from the built-in field model by location, or set manually |

The selection rule. A compass on a mast with the GPS goes in slot 1. The internal compass of a board that sits 2–3 cm from the power wires is disabled: `COMPASS_USEn = 0` for its slot (usually 2 or 3; go by `COMPASS_PRIOn_ID`, not by the number). It adds no accuracy but does produce the `Compasses inconsistent` failure. Do not change `COMPASS_DEV_ID*` by hand: after a reboot the calibration would be tied to someone else's sensor.

### What the firmware does with the raw field
Every measurement goes through `correct_field` (`AP_Compass_Backend.cpp`) in a strictly defined order:

B = M · ((B_raw + OFS) · SCALE) + MOT · k

- OFS is `COMPASS_OFS_X/Y/Z`, in mG, and it is **added** (hard iron, `est-sensors`);
- SCALE is `COMPASS_SCALE`; it is applied only if it lies within 0.667–1.5, otherwise it is skipped (the value 0 means "not set");
- M is a symmetric matrix: the diagonal is `COMPASS_DIA_X/Y/Z` (1 by default), off the diagonal are `COMPASS_ODI_X` (xy), `ODI_Y` (xz), `ODI_Z` (yz) (soft iron);
- MOT is `COMPASS_MOT_X/Y/Z`; k depends on `COMPASS_MOTCT`.

| `COMPASS_MOTCT` | k | Unit of `COMPASS_MOT_*` |
|---|---|---|
| 0 | no compensation | — |
| 1 | throttle from 0 to 1 | mG at full throttle |
| 2 | the current of the **first** battery monitor, A | mG/A |

The compensation is added after the matrix. With `COMPASS_MOTCT = 2` the current is taken only from monitor 1 (`BATT_*`): if it has no current measurement, the correction is silently zero. For the second and third slot the parameters are the same with suffixes: `COMPASS_OFS2_*`, `DIA2`, `ODI2`, `SCALE2`, `MOT2`. There is also per-motor compensation, `COMPASS_PMOT_*`, for the first compass only; the module does not cover it.

In the log the result is in the `MAG` message (the `I` field is the instance): `MagX/Y/Z` is the already corrected field, `OfsX/Y/Z` are the current offsets, `MOX/MOY/MOZ` is the motor correction at that moment, and `Health`.

### Rotation calibration: what fitness is
Onboard calibration (a button in the ground station or the `RCx_OPTION = 171` switch, disarmed only) collects 300 samples while the vehicle is rotated with every side toward the ground and fits first a sphere and then an ellipsoid to them. **Fitness** is the root mean square of the residual: how many milligauss, on average, the points are away from the fitted surface. The lower, the better.

The calibration is accepted if all of the following hold:

| Condition | Threshold (`CompassCalibrator.cpp`) |
|---|---|
| fitness | ≤ `COMPASS_CAL_FIT` for an external compass in slot 1; ≤ 2 × `COMPASS_CAL_FIT` for all the others, including an internal one in slot 1 |
| sphere radius | from 150 to 950 mG |
| absolute value of each offset | < `COMPASS_OFFS_MAX` |
| diagonal | from 0.2 to 5.0 |
| off-diagonal | absolute value < 1.0 |
| scale factor (expected field / radius) | from 0.667 to 1.5, otherwise `Mag(n) bad radius` |

`COMPASS_CAL_FIT`: 4 Very Strict, 8 Strict, 16 Default, 32 Relaxed (range 4–32). `COMPASS_OFFS_MAX` is 1800 by default, range 500–3000. The wiki still has the old numbers 850 and "an offset above 600"; they are not in 4.7.2.

What is saved: `OFS`, `DIA`, `ODI`, `SCALE`, and for an external compass with `COMPASS_AUTO_ROT` ≥ 2 also `COMPASS_ORIENT`. The scale factor is calculated as the ratio of the field from the built-in Earth model to the fitted radius, so a location is needed: without a fix the firmware reports `MagCal: No location, fix_radius skipped` and leaves `COMPASS_SCALE = 0`. Hence the rule: calibrate outdoors with a 3D fix, and bit 0 of `COMPASS_OPTIONS` turns this rule into a hard requirement. After a success a reboot is needed; until then arming is blocked by `Compass calibrated requires reboot`. Starting a calibration resets `COMPASS_LEARN` to 0.

If the calibration fails again and again, raising `COMPASS_CAL_FIT` to 32 is the last step, not the first. First move away from metal, check the orientation and the distance to the power wires (`el-emi`).

### Large Vehicle MagCal: offsets from a known heading
You cannot spin a 25 kg vehicle around. The `MAV_CMD_FIXED_MAG_CAL_YAW` command (in Mission Planner, the Large Vehicle MagCal box; the interface was not checked against the source) calibrates in place. Inputs: param1 is the **true** heading of the nose in degrees, param2 is the compass mask (0 is all compasses in use), param3 and param4 are latitude and longitude (0 and 0 means take them from the AHRS or from a GPS with a 3D fix).

What `mag_cal_fixed_yaw` calculates:

1. From the location it takes the intensity F, declination D and inclination I out of the built-in world model tables. The field in "north, east, down" axes: N = F·cos I·cos D, E = F·cos I·sin D, Dn = F·sin I.
2. It rotates the field into the vehicle axes using the current roll and pitch from the AHRS and the given heading ψ. For a level vehicle: X = N·cos ψ + E·sin ψ, Y = −N·sin ψ + E·cos ψ, Z = Dn.
3. It takes the current measurement without the old offsets and matrix and saves **OFS = expected − measured**.
4. It sets `DIA` = 1, `ODI` = 0. It does not touch the scale factor or the orientation.

The consequences. The method corrects only hard iron and assumes the sensor already measures in milligauss and is in the right orientation: with a wrong `COMPASS_ORIENT` the command "successfully" saves garbage. The heading must be true: add the declination to a phone compass reading. A heading error of 8° gives an offset error of tens of milligauss (calculated in the practice section). The scale factor is not removed from the measurement: if `COMPASS_SCALE` is neither 0 nor 1 after an earlier rotation calibration, the saved offsets will be inaccurate. Set `COMPASS_SCALE = 0` (no scaling is done) before the command. There must be no metal and no running motors nearby: a single measurement is taken as is. The failures: `Mag: no position available`, `Mag: WMM table error`, `Mag[n]: unhealthy`.

### In-flight learning: `COMPASS_LEARN`
| Value | In 4.7.2 | What happens |
|---|---|---|
| 0 | the default | disabled |
| 1 | **removed** from the list of values (Internal-Learning in 4.6) | commented out in the 4.7.2 source |
| 2 | EKF-Learning | on disarm, Copter copies the offsets estimated by the EKF into `COMPASS_OFS*` |
| 3 | InFlight-Learning | after 3 s of flight it waits until the GSF yaw estimator (`ap-ekf`) converges to 5°, calls the same `mag_cal_fixed_yaw` with that heading, reports `CompassLearn: Finished` and sets the parameter back to 0 |

While `COMPASS_LEARN = 3`, the compass is **not used** for yaw (and the pre-arm compass checks are skipped); do not count on position control modes until the `Finished` message. Besides GSF convergence to 5°, the firmware waits for an absolute pitch of no more than 50° and no more than one IMU "clip". The `RCx_OPTION = 62` switch enables the same thing without saving the parameter. The wiki has called this learning "for advanced users and not recommended" ever since Large Vehicle MagCal appeared: the result is the same (offsets only), and the first flight is made without a compass.

### MagFit: calibration from a flight log
MagFit fits the compass parameters to an already recorded log. The tool is not part of the firmware tree: the web version is in the ArduPilot/WebTools repository (the `MAGFit` directory), and a second implementation is in MAVProxy (`modules/lib/magfit.py`, the Tools menu in MAVExplorer). Its screens and buttons cannot be checked against the firmware source.

The principle, from the source of the tools: for each `MAG` sample, the expected world model field in vehicle axes is calculated from the attitude in the log and the location, and then the parameters of the correction formula are fitted so that the corrected field is as close as possible to the expected one. You can fit offsets, the scale factor, `DIA`, `ODI` and the current-based `COMPASS_MOT_*`.

| What the log needs | Why |
|---|---|
| `MAG` of the chosen instance | the measured field and the offsets that were flown with |
| `ATT` (or the EKF quaternion / `AHR2`) | the vehicle attitude |
| `GPS`, `POS` or `ORGN` | the location for the field model |
| `BAT.Curr` | the current for fitting `COMPASS_MOT_*` |
| `PARM` | the old values, to remove them from the data |

The rules from the wiki and the tool README: a log of several minutes with several full turns; exclude the parts on the ground and in the hands; start with offsets alone and add `DIA`/`ODI` and current only if a noticeable residual remains; accept the result if the remaining heading deviation is under 10°; if the calculated heading after the fit moves away from the EKF heading by more than 20°, look for the error elsewhere (orientation, GPS) instead of saving the parameters. The first flight for the log is made with any rough calibration, in a mode without position hold.

### CompassMot: interference from the power wiring
The `compassmot` procedure exists only in Copter (except helicopters). **It spins the motors with the propellers on**: the flight controller arms itself, the stick throttle goes straight to the ESCs, and the throttle failsafe is disabled for the duration. Per the wiki, the propellers are flipped over and moved to the adjacent arms so that the thrust presses the vehicle to the ground, and the vehicle itself is secured.

What `compassmot.cpp` does:

- at zero throttle it stores the base field B₀;
- at throttle above zero it calculates the interference ΔB = B − B₀;
- if there is a current measurement and I ≥ 3 A, it accumulates **MOT = −ΔB / I** (a moving average), type 2; with no current sensor, MOT = −ΔB / throttle, type 1;
- it shows the interference percentage scaled to full throttle: |MOT| · (I_max / throttle_max) / 530 · 100, where throttle_max is the highest throttle seen during the procedure, from 0 to 1 (530 mG is the "expected" field assumed in the firmware); with throttle compensation it is |MOT| / 530 · 100. The procedure is run at 50–75 % throttle, so the percentage shown is higher than the interference at the throttle where you stopped: 40 A at 75 % throttle is counted as 53.3 A at full throttle;
- at the end it saves `COMPASS_MOTCT` and `COMPASS_MOT*` and reports `Calibration successful`.

Rating the percentage per the wiki: under 30 is acceptable, 31–60 is a gray zone, above 60 means move the compass. Throttle compensation (type 1) is worse: the current at the same throttle depends on the battery voltage. The compensation holds only as long as the wires and the battery have not moved, so first separate the compass from the wiring (`el-emi`) and subtract only the remainder. MagFit from a log gives the same vector without spinning up on the bench.

### Which method for which vehicle
{{diagram:ap-sensors-compass-flow|The calibration method is chosen by two questions: can the vehicle be rotated by hand, and does the field depend on current. Rotation gives a full calibration, a known heading gives offsets only, and current interference is removed by moving the compass, with only the remainder left to CompassMot or MagFit.}}

| Vehicle | Method | Why | What to check afterwards |
|---|---|---|---|
| A 5″ quadcopter, compass in the GPS module 2–4 cm above the battery | rotation; then CompassMot or MagFit with current | it is easy to rotate, but the wires are close, so current interference is almost inevitable | interference percentage < 30; `MAG.MOX/Y/Z` change with throttle while the field length does not |
| A 7–10″ copter, compass on an 8–10 cm mast | rotation | the mast has already taken care of the current | the field length at full throttle changes by less than 5–10 % |
| A big multirotor that cannot be lifted | Large Vehicle MagCal; MagFit after the first flight | rotation is impossible; a known heading gives offsets only | `COMPASS_ORIENT` is set manually **before** the command; after MagFit the heading deviation is < 10° |
| A plane | rotation (a light one) or Large Vehicle | `EK3_MAG_CAL = 0` on Plane: in flight the EKF estimates the field itself; there is little current near a compass in the wing | the heading in the parking area matches the runway axis within 5–10° |
| A VTOL | as a big multirotor if it cannot be rotated; otherwise rotation | in hover the currents are multirotor currents, so MagFit on a hover segment is needed | `XKF3.IMX/IMY/IMZ` in hover and in forward flight are of the same order |

Common checks after any calibration:

- the length of the `COMPASS_OFS*` vector is well below `COMPASS_OFFS_MAX`; hundreds of milligauss are normal for a compass near metal, more than a thousand is a reason to look for a magnet or steel nearby;
- the length of `MAG.MagX/Y/Z` on the ground is close to the local field (450–550 mG at mid latitudes) and lies between 185 and 875 mG;
- in a hover log `XKF3.IMX/IMY/IMZ` (the magnetometer innovations) fluctuate around zero, and `XKF4.SM` is below 1 (`ap-logs`, `ap-ekf`);
- in Loiter there are no widening circles ("toilet bowling"): that is a sign of a heading error, not of the PIDs (`nav-resilience`). If toilet bowling starts, switch to a mode without GPS at once.

### Compass pre-arm failures
The strings arrive with the `PreArm:` prefix; the order of the checks is as in the table (`AP_Arming.cpp`, `compass_checks`).

| String | Condition | What to do |
|---|---|---|
| `Compass calibration running` | the calibration has not finished | wait or cancel |
| `Compass calibrated requires reboot` | after an onboard calibration | reboot |
| `Compass n not healthy` | no data for 0.5 s | wiring, bus, `COMPASS_DISBLMSK` |
| `Compass n not found` | the compass of a priority slot was not detected | bring the sensor back or remove it from `COMPASS_PRIOn_ID` |
| `Compass order change requires reboot` | the priorities were changed | reboot |
| `Compass not calibrated` | the offsets are zero or `DEV_ID` does not match the detected one | calibrate |
| `Compass offsets too high` | the **length** of the offset vector of the first compass > `COMPASS_OFFS_MAX` | remove the metal; do not raise the threshold blindly |
| `Check mag field: 912, max 875, min 185` | the field length is outside 185–875 mG | a magnet nearby, a wrong scale factor |
| `Compasses inconsistent` | for two compasses in use the angle between the vectors is > 90°, in the horizontal plane > 60°, or the horizontal components differ in length by > 200 mG | the orientation of the second compass; disable the internal one |
| `Check mag field (xy diff:142>100)` | a horizontal component differs from the field model by more than `ARMING_MAGTHRESH` | a calibration near metal, rebar under the vehicle |
| `Check mag field (z diff:260>200)` | the vertical one, by more than 2 × `ARMING_MAGTHRESH` | the same |

`ARMING_MAGTHRESH` is 100 mG by default, range 0–500; 0 **disables** the comparison with the field model. Note the difference: the calibrator checks each offset separately, while the pre-arm check uses the length of the vector. A calibration with three offsets of 1100 passes, but arming does not (the length is 1905).

### Compass and EKF
Calibration is an input to state estimation, and what the EKF does with it is set by three parameters (details in `ap-ekf`):

{{lesson:ap-ahrs-choice|Flying without a compass (GSF, `EK3_SRC1_YAW = 8`), in-flight yaw alignment from GPS, and when the EKF stops trusting the compass.}}

- `EK3_MAG_CAL`: 0 estimates the field on three axes when flying (the Plane default), 2 is heading only (Rover), 3 is three axes after the first climb (the Copter default), 4 is always. The offsets estimated by the EKF are visible in `XKF2.MX/MY/MZ`.
- `EK3_SRC1_YAW`: 1 Compass, 2 GPS (two antennas, `est-gnss`), 3 GPS with Compass Fallback, 6 ExternalNav, 8 GSF, which is yaw from motion with no compass.
- `COMPASS_USE = 0` for all slots plus `EK3_SRC1_YAW = 8` is a legitimate configuration for a plane with no compass; on a copter the heading is undefined until it starts moving (`nav-resilience`).

### The airspeed sensor on the bench
The setup for flight (`ARSPD_TYPE`, `ARSPD_USE`, `ARSPD_RATIO`, autocalibration) is in `ap-setup-plane`. Here is only what is checked on the bench.

| Parameter | Default | Meaning on the bench |
|---|---|---|
| `ARSPD_BUS` | 1 | the I²C bus number (0–3), which may not match the label on the board; needs a reboot |
| `ARSPD_PIN` | board dependent | the ADC input of an analog sensor (`ARSPD_TYPE = 2`) |
| `ARSPD_PSI_RANGE` | 1.0 | the sensor range in psi; change it only from the chip datasheet: the MS4525 converts pressure through this number |
| `ARSPD_OFFSET` | 0 | the sensor zero; written by the calibration at every power-up |
| `ARSPD_SKIP_CAL` | 0 | 0: calibrate the zero at startup; 1: use the saved one, no calibration required; 2: do not calibrate at startup, but require a manual one once per boot (the value 2 is new in 4.7) |
| `ARSPD_PRIMARY` | 0 | which sensor is primary: 0 the first, 1 the second |
| `ARSPD2_TYPE`, `ARSPD2_BUS`, `ARSPD2_USE`… | 0 | the second sensor; a standard build has two sensors |
| `ARSPD_WIND_MAX` | 0 m/s | the difference from GPS speed above which the sensor is marked unhealthy; 0 means no check against GPS speed (the EKF consistency check by `ARSPD_WIND_GATE` remains) |
| `ARSPD_WIND_WARN` | 0 m/s | the warning threshold; 0 means equal to `WIND_MAX` |
| `ARSPD_WIND_GATE` | 5.0 | the gate size of the EKF3 consistency check in standard deviations (0–10) |

Types by bus: I²C has the MS4525 (1), MS5525 (3–5), SDP3X (6), DLVR (7, 9–12), ASP5033 (15), AUAV (17–19, new in 4.7); ADC has analog (2); DroneCAN (8); MSP (14). The selection rule: an analog sensor drifts with supply voltage and is worth choosing only on a ready-made board; on an I²C bus longer than 30–40 cm DroneCAN is more reliable.

The zero at startup: the firmware discards the first few samples (6; the source comment says 5), averages the rest over at least a second and writes `ARSPD_OFFSET` (`Airspeed 1 calibrated`). If wind is blowing into the tube at that moment, the zero is saved with a speed in it, and all readings come out low. That is why the tube is covered with a loose cap. A sensor with `ARSPD_OFFSET = 0` is considered unhealthy unless `ARSPD_SKIP_CAL = 1` is set.

A leak check of the tubing: put a piece of silicone tube on the total pressure port, squeeze it gently until the reading is 15–20 m/s and pinch it shut. The reading must hold for several seconds; if it drops, a joint is leaking. Do the same with the opposite sign on the static port.

In-flight monitoring (`AP_Airspeed_Health.cpp`): five times a second the health probability is multiplied by 0.9 on a mismatch and grows slowly on agreement; below 0.1 with bit 0 of `ARSPD_OPTIONS` the sensor is disabled (`Airspeed sensor 1 failure. Disabling`), and above 0.95 with bit 1 it is re-enabled. By default `ARSPD_OPTIONS` = 11 (bits 0, 1 and 3): the sensor is disabled and re-enabled automatically, and the mismatch is also evaluated against the EKF gate (`ARSPD_WIND_GATE` = 5), even with `ARSPD_WIND_MAX = 0`. The check is off entirely only when both `ARSPD_WIND_MAX` and `ARSPD_WIND_GATE` are 0. The rule for `ARSPD_WIND_MAX`: the maximum wind you fly in plus 5 m/s; with less, a gust disables the sensor.

### Battery monitors: the `BATT_MONITOR` types
A monitor is an instance with its own set of parameters: `BATT_*` is the first, `BATT2_*`…`BATT9_*` are the rest. A standard 4.7.2 build has **nine** of them (`AP_BATT_MONITOR_MAX_INSTANCES = 9`); the `BATTA_`…`BATTG_` prefixes and the "up to 16 monitors" from the wiki appear only in a build with an increased number of instances. A change of `BATTn_MONITOR` needs a reboot.

| Value | Type | What it measures and when to choose it |
|---|---|---|
| 0 | Disabled | — |
| 3 | Analog Voltage Only | a divider on an ADC input; an avionics battery, a sensor with no shunt. No current and no mAh |
| 4 | Analog Voltage and Current | an ordinary power module; the main option up to 6S and the sensor's current rating |
| 31 | Analog Current Only (new in 4.7) | a separate Hall sensor on an arm or on a second branch; the voltage is always 0 |
| 25 | Synthetic Current and Analog Voltage | the current is estimated from the plane's throttle output; for a wing with no current sensor |
| 7, 13, 14, 15, 16, 19 | SMBus: Generic, SUI3, SUI6, NeoDesign, Maxell, Rotoye | a "smart" battery on I²C: it reports its capacity, cells and serial number itself |
| 8 | DroneCAN-BatteryInfo | a sensor or battery on the CAN bus (`el-dronecan`); 12S and above, long wires |
| 9 | ESC | the average voltage and the **sum** of the currents from ESC telemetry (`ap-outputs`) |
| 10 | Sum Of Selected Monitors | a virtual monitor on top of the others |
| 21, 26, 30, 22, 28 | INA2XX on I²C, INA239 on SPI, INA3221 (new in 4.7), LTC2946, AD7091R5 | digital meters on the board or a module; more accurate than an analog input |
| 11, 12, 24 | FuelFlow (pulses), FuelLevelPWM and FuelLevelAnalog | combustion engines: the "capacity" is in milliliters |
| 17, 18, 27 | generator (electrical and fuel side), EFI | hybrid powertrains |
| 20, 23, 29 | MPPT, Torqeedo, Scripting | a solar controller, a boat motor, your own Lua driver |
| 5, 6, 32 | Solo, Bebop, TI BQ76952 (AP_Periph only) | specific products |

The parameters of an analog monitor: `BATT_VOLT_PIN` and `BATT_CURR_PIN` (ADC input numbers from the board `hwdef`; on the MatekH743 the first sensor is 10 and 11, the second 18 and 7), `BATT_VOLT_MULT`, `BATT_AMP_PERVLT`, `BATT_AMP_OFFSET`, `BATT_VLT_OFFSET`. The formulas from `AP_BattMonitor_Analog.cpp`:

- V = (V_in − `BATT_VLT_OFFSET`) × `BATT_VOLT_MULT`;
- I = (V_in − `BATT_AMP_OFFSET`) × `BATT_AMP_PERVLT`.

Both quantities are directly proportional to the multiplier, so the correction is always "new = old × reference / reading": for voltage the reference is a multimeter, for current it is the mAh put in by the charger against the mAh counted by the flight controller. The step-by-step procedure for the first monitor is in `ap-setup-scratch`; for the second it is the same with the `BATT2_` prefix. For the ESC monitor (type 9), the `BATT_ESC_MASK` mask selects which ESCs go into the sum (0 is all). Do not confuse it with `BATT_ESC_INDEX`: that one does the opposite, writing the monitor data into ESC telemetry under the given index.

### Thresholds, timer and resting voltage
| Parameter | Default | Meaning |
|---|---|---|
| `BATT_CAPACITY` | 3300 mAh | the capacity when full; the basis of the percentage and the mAh thresholds |
| `BATT_LOW_VOLT` / `BATT_CRT_VOLT` | 10.5 V (Copter), 0 (Plane) / 0 | the voltage thresholds; 0 disables them |
| `BATT_LOW_MAH` / `BATT_CRT_MAH` | 0 / 0 | thresholds on the **remaining** capacity: `CAPACITY` − consumed |
| `BATT_LOW_TIMER` | 10 s | how long the voltage must stay below the threshold; applies to both voltage thresholds |
| `BATT_FS_VOLTSRC` | 0 | 0 Raw Voltage, 1 Sag Compensated Voltage (resting voltage) |
| `BATT_FS_LOW_ACT` / `BATT_FS_CRT_ACT` | 0 / 0 | the action; 0 is Warn only (`ap-safety-fs`) |
| `BATT_ARM_VOLT` / `BATT_ARM_MAH` | 0 / 0 | the minimum voltage and remaining capacity required to arm |
| `BATT_SERIAL_NUM` | −1 | the SMBus serial number or the DroneCAN battery ID |
| `BATT_OPTIONS` | 0 | bit 6 sends the resistance compensated voltage to the GCS; bit 8 keeps the monitor from being reported to the ground station; bit 9 makes the "sum" take the minimum voltage instead of the average; bits 0, 7, 10 are DroneCAN; bits 1–5 are MPPT |

The logic of `update_failsafes` and `check_failsafes`:

- the mAh thresholds trigger **at once**, the voltage ones after `BATT_LOW_TIMER` seconds continuously below the threshold; the critical one is checked first;
- `BATT_LOW_TIMER = 0` **disables both voltage failsafes**;
- the check runs only when armed and **for each monitor separately**: each has its own thresholds and its own `BATTn_FS_*_ACT` action; the message is `Battery 2 is low 21.40V used 5200 mAh`;
- a monitor that is silent for 5 s gives only the message `Battery n is missing, last: …`, with no action;
- the mAh counter is reset on reboot (except for "smart" batteries): `BATT_ARM_MAH` does not protect against taking off on a half-empty battery after a restart, so `BATT_ARM_VOLT` is needed as well.

Resting voltage. The firmware continuously estimates the internal resistance R from the changes in current and voltage (the `BAT.Res` field in the log) and calculates V_rest = V + I × R (`BAT.VoltR`). With `BATT_FS_VOLTSRC = 1` the thresholds are compared with it. The selection rule: on a vehicle with large current surges and a "soft" battery (Li-Ion, `el-battery-packs`), source 1 removes false triggers in a climb; the thresholds are then set from the no-load voltage. The estimate needs a current sensor; until R has been learned, the correction is small.

Pre-arm failures: `Battery n unhealthy`, `below minimum arming voltage`, `below minimum arming capacity`, `low voltage failsafe`, `low capacity failsafe`, `critical voltage failsafe`, `critical capacity failsafe`, `capacity failsafe critical >= low`, `voltage failsafe critical >= low`, all with the `PreArm: Battery n` prefix.

### The "sum" monitor and layouts for several batteries
A type 10 monitor (`AP_BattMonitor_Sum.cpp`) adds up the current, mAh and Wh of the selected monitors and **averages** the voltage (or takes the minimum with bit 9 of `BATT_OPTIONS`). The selection is set by `BATTn_SUM_MASK`: bit 0 is monitor 1, bit 1 is monitor 2 and so on up to bit 8. It never includes itself. The value 0 means "all monitors **with a number higher than mine**". Unhealthy members are skipped silently: when one sensor fails, the sum shows half the current without a single failure message. The "sum" monitor is not built for every board with 1 MB of flash: if it is missing, arming is refused with `PreArm: Battery n feature BATTERY_SUM not available`.

{{diagram:ap-sensors-batt-sum|The sum is the first monitor and adds up only the power batteries 2 and 3 (mask 6): the ground station, the OSD and the compass compensation look at it. The failsafe is checked on each monitor separately, so the avionics battery has its own threshold and its own action.}}

| Task | Layout | Why |
|---|---|---|
| One battery, one sensor | `BATT_MONITOR = 4` | the basic case |
| Two batteries in parallel, each with its own sensor | `BATT_MONITOR = 10`, `BATT_SUM_MASK = 6`; `BATT2`, `BATT3` are the sensors | the total current and mAh are on the first monitor; the mAh thresholds go on the sum, from the total capacity |
| A power battery and an avionics battery | `BATT` is the power battery (type 4), `BATT2` is the avionics (type 3) | the avionics has no current; its own `BATT2_LOW_VOLT` and a "land" action |
| No common sensor, but telemetry from four ESCs | `BATT_MONITOR = 9`, `BATT_ESC_MASK = 15` | the current is the sum over the ESCs; loads that bypass the ESCs are not counted |
| A common voltage sensor and current sensors on two branches | `BATT` is the sum with mask 6; `BATT2`, `BATT3` are type 31; `BATT4` is type 3 with voltage thresholds | a type 31 monitor has a voltage of 0, so the sum's voltage is wrong (the zeros go into both the average and the minimum): keep only mAh thresholds on the sum |

The rule: put first the monitor that describes **the whole power circuit**, because that is the one three consumers take with no choice: the ground station `SYS_STATUS`, most OSD items and the compass current compensation.

### What the ground station and the OSD show
- `SYS_STATUS` (the voltage, current and percentage in the ground station header) is always monitor 1. `BATTERY_STATUS` is sent for every monitor except those marked with bit 8 of `BATT_OPTIONS`.
- OSD (`ap-osd-video`): `BAT_VOLT`, `CURRENT`, `BATUSED`, `RESTVOLT`, `AVGCELLV` are monitor 1; `BAT2_VLT`, `BAT2USED`, `CURRENT2` are monitor 2. There are no items for monitors 3–9.
- In the log the `BAT` message is written for every instance (the `Inst` field): `Volt`, `VoltR`, `Curr`, `CurrTot`, `EnrgTot`, `Res`, `RemPct`.

### Place in the system
- **Receives:** the compass location and the power wire routing from `el-emi` and `el-power-design`; the capacity, cell count and permissible sag from `el-battery-packs`; ESC telemetry from `ap-outputs`; the procedure for the first monitor calibration from `ap-setup-scratch`.
- **Provides:** the corrected field and heading to state estimation (`ap-ekf`, `est-sensors`); voltage, current and mAh to the failsafe thresholds (`ap-safety-fs`) and the display (`ap-osd-video`); the tube zero to the airspeed loop (`ap-setup-plane`).
- **If you get it wrong here:** a heading from wrong offsets gives toilet bowling in Loiter and an `EKF variance` failure (`nav-resilience`, `ap-ekf`); a sum missing one battery understates consumption, and the `BATT_LOW_MAH` threshold triggers late (`ap-safety-fs`); a tube zero taken in wind understates the airspeed all the way to a stall (`ap-setup-plane`).

## practice
The lab is a calculation exercise: you need neither a flight controller nor a simulator. All parameter excerpts and tables of readings are a training example assembled by hand; they are not exports from a vehicle. The answers are fully determined by the formulas of the theory.

### Step 1. Current interference and a calibration check
A 5″ quadcopter, the compass in the GPS module above the battery, external, in slot 1. After a rotation calibration:

```
# training example, assembled by hand
COMPASS_OFS_X,112
COMPASS_OFS_Y,-48
COMPASS_OFS_Z,205
COMPASS_DIA_X,1
COMPASS_DIA_Y,1
COMPASS_DIA_Z,1
COMPASS_SCALE,1.0
COMPASS_CAL_FIT,16
COMPASS_OFFS_MAX,1800
COMPASS_MOTCT,0
```

The calibration report: the fitness of the first compass is 14.2, of the second (internal) one 27.5. The vehicle is secured, and these are the `MAG` readings of the first compass at different currents:

| Current, A | MagX | MagY | MagZ |
|---|---|---|---|
| 0 | 210 | −35 | 420 |
| 10 | 228 | −41 | 451 |
| 20 | 246 | −47 | 482 |
| 30 | 264 | −53 | 513 |
| 40 | 282 | −59 | 544 |

Find: (a) whether the calibration of both compasses passed on fitness; (b) the `COMPASS_MOT_X/Y/Z` vector and the `COMPASS_MOTCT` value; (c) the corrected field at 30 A after they are saved; (d) the interference percentage if the 40 A were reached at full throttle, and the conclusion; (e) whether arming passes on the offset length and on the field length; (f) what happens with the offset vector (640, −1310, 1150).

Result. (a) The first is external in slot 1, threshold 16: 14.2 ≤ 16, accepted. The second has a threshold of 2 × 16 = 32: 27.5 ≤ 32, accepted. (b) ΔB at 40 A = (72, −24, 124); MOT = −ΔB / I = (**−1.8, 0.6, −3.1**) mG/A; `COMPASS_MOTCT = 2`. The 10, 20 and 30 A rows give the same vector. (c) (264, −53, 513) + (−1.8, 0.6, −3.1) × 30 = (**210, −35, 420**), the base field. (d) |MOT| = √(1.8² + 0.6² + 3.1²) = 3.635; 3.635 × 40 = 145.4 mG; 145.4 / 530 = **27.4 %** (the 40 A are at full throttle; if the same 40 A were reached at 75 % throttle, the procedure shows 27.4 / 0.75 = 36.6 %), which is under 30 and acceptable but close to the limit; at 36.6 % it is already the gray zone. (e) |OFS| = √(112² + 48² + 205²) = **238.5** < 1800; |B₀| = √(210² + 35² + 420²) = **470.9** mG, inside 185–875. (f) Each offset is below 1800, so the calibrator accepts it; the vector length is **1856.9** > 1800, so `PreArm: Compass offsets too high`.

### Step 2. Large Vehicle MagCal by hand
A heavy octocopter sits level, nose on a landmark with a true heading of ψ = 60°. The field model data for this point (given as inputs): F = 500 mG, declination D = +8°, inclination I = 66°. The compass is in the right orientation, the old offsets are zero, `DIA` = 1, `ODI` = 0; the measurement is (310, −95, 250). Find the offsets the command will save. Then repeat the calculation for an operator error: the magnetic heading of 52° was entered.

Result. N = 500 · cos 66° · cos 8° = 201.39; E = 500 · cos 66° · sin 8° = 28.30; Dn = 500 · sin 66° = 456.77. In vehicle axes: X = 201.39 · 0.5 + 28.30 · 0.8660 = 125.21; Y = −201.39 · 0.8660 + 28.30 · 0.5 = −160.26; Z = 456.77. OFS = expected − measured = (**−184.8, −65.3, 206.8**). With ψ = 52° the expected field is (146.29, −141.27, 456.77) and the offsets are (−163.7, −46.3, 206.8): an error of 21 and 19 mG on the horizontal axes, and the heading after such a "calibration" is off by those same 8°. The command reports success in both cases.

### Step 3. Two sensors, a sum and the failsafe
The same octocopter: two 6S batteries of 10 000 mAh in parallel, each with its own analog sensor; the avionics runs from a separate 3S. The layout: `BATT` is the sum, `BATT2` and `BATT3` are the sensors, `BATT4` is the avionics (type 3).

(a) Both power batteries are connected on the bench, and the multimeter reads 24.36 V. The ground station shows 23.90 V for monitor 2 and 24.60 V for monitor 3; both have `VOLT_MULT = 11.0`. Find the new multipliers. (b) After a flight the flight controller counted 4150 mAh on monitor 2 and 4620 mAh on monitor 3; the charger put in 4480 and 4390 mAh; both have `AMP_PERVLT = 40`. Find the new values. (c) Which `BATT_SUM_MASK`, and what happens with a mask of 0? (d) The thresholds of the sum: `BATT_CAPACITY = 20000`, `BATT_LOW_MAH = 5000`, `BATT_CRT_MAH = 3000`, `BATT_LOW_VOLT = 21.6`, `BATT_CRT_VOLT = 21.0`, `BATT_LOW_TIMER = 10`, `BATT_FS_LOW_ACT = 2`, `BATT_FS_CRT_ACT = 1`, `BATT_FS_VOLTSRC = 0`. Decide four cases: 1) 21.9 V, 15 200 mAh consumed; 2) 21.4 V for 6 s, then 22.0 V; 3) 20.8 V for 12 s, 12 000 mAh consumed; 4) with `BATT_FS_VOLTSRC = 1`: 21.4 V, a current of 60 A, R = 0.012 Ω, held for 15 s. (e) 6000 mAh are consumed and the hover current is 54 A: in how many minutes does `BATT_LOW_MAH` trigger?

Result. (a) 11.0 × 24.36 / 23.90 = **11.21**; 11.0 × 24.36 / 24.60 = **10.89**. (b) 40 × 4480 / 4150 = **43.18**; 40 × 4390 / 4620 = **38.01**. (c) Monitors 2 and 3 are bits 1 and 2: 2 + 4 = **6**. With a mask of 0 the sum takes monitors 2, 3 and 4: the current does not change (the avionics has no current), but the voltage becomes the average of three: (24.36 + 24.36 + 11.9) / 3 = 20.2 V with 11.9 V on the avionics, which is below `BATT_LOW_VOLT` and `BATT_CRT_VOLT`: arming fails with `PreArm: Battery 1 low voltage failsafe` (before arming the thresholds are checked without the timer, and the low one is checked before the critical one). If you disable that check, a false critical failsafe follows 10 s after arming. (d) 1) the remaining 4800 < 5000, so low at once, RTL. 2) nothing: 6 s < 10 s, and the timer is reset. 3) below 21.0 for longer than 10 s, so critical, Land; the remaining 8000 does not reach the thresholds. 4) V_rest = 21.4 + 60 × 0.012 = 22.12 V > 21.6, so nothing. (e) To the threshold: (20000 − 5000) − 6000 = 9000 mAh; 9000 / 54 000 h = 0.1667 h = **10.0 min**.

### Step 4. Choosing a method and three mistakes
(a) Name the compass calibration method and the monitor layout for three vehicles: A is a 5″ quadcopter, the compass in the GPS module 3 cm above the battery, one battery, a current sensor on the board; B is a 25 kg octocopter, the compass on a 15 cm mast, two batteries with sensors and an avionics battery; C is a VTOL wing that takes two people to lift, the compass in a wingtip, a 6S power battery and a 3S avionics battery, an MS4525 tube.

(b) Find the mistakes in the excerpt for vehicle B:

```
# training example, assembled by hand
COMPASS_USE,1
COMPASS_USE2,0
COMPASS_EXTERNAL,1
COMPASS_AUTO_ROT,2
COMPASS_LEARN,0
COMPASS_MOTCT,2
COMPASS_MOT_X,-0.4
COMPASS_MOT_Y,0.1
COMPASS_MOT_Z,-0.7
BATT_MONITOR,3
BATT_LOW_VOLT,10.8
BATT_FS_LOW_ACT,1
BATT2_MONITOR,4
BATT2_LOW_VOLT,21.6
BATT2_CRT_VOLT,22.2
BATT2_LOW_TIMER,10
BATT3_MONITOR,4
BATT4_MONITOR,10
BATT4_SUM_MASK,0
BATT4_CAPACITY,20000
BATT4_LOW_MAH,5000
```

Result. (a) A: rotation, then CompassMot or MagFit with current; `BATT_MONITOR = 4`. B: Large Vehicle MagCal with a manually set `COMPASS_ORIENT`, MagFit after the first flight; `BATT` is the sum with mask 6, `BATT2`, `BATT3` are the sensors, `BATT4` is the avionics, type 3. C: Large Vehicle MagCal (or rotation by two people), MagFit on a hover segment; `BATT` is the power battery, type 4, `BATT2` is the avionics, type 3; the tube zero under a cap, a leak check.

(b) There are exactly three mistakes. (1) `COMPASS_MOTCT = 2` with `BATT_MONITOR = 3`: the first monitor has no current, so the compensation is zero. (2) `BATT4_SUM_MASK = 0` on monitor 4: "all with a number higher than mine" means none, the sum is unhealthy, `PreArm: Battery 4 unhealthy`; make the sum the first monitor with mask 6 (or here, mask 6 on monitor 4, but then mistake 1 remains). (3) `BATT2_CRT_VOLT = 22.2` is above `BATT2_LOW_VOLT = 21.6`: `PreArm: Battery 2 voltage failsafe critical >= low`. The rest is correct: `COMPASS_USE2 = 0` disables the internal compass, `COMPASS_LEARN = 0`, the timer is 10 s.

### Moving to real hardware
The propellers are off in every step except CompassMot. **CompassMot spins the motors up to 50–75 % throttle** (the firmware scales the interference percentage to full throttle by dividing by the highest throttle of the procedure): the propellers are flipped and moved, the vehicle is tied down, and people stand behind the operator; on a vehicle heavier than 5 kg use MagFit from a log instead.

1. Save the parameters to a file. Write down `COMPASS_PRIOn_ID` and `COMPASS_DEV_ID*`, work out which slot holds the external compass; disable `COMPASS_USEn` of the internal one.
2. Calibrate per the selection table, outdoors, with a 3D fix, 10 m away from cars and rebar. For Large Vehicle, first `COMPASS_ORIENT`, then the true heading from a landmark on the map.
3. Reboot. Messages has no compass `PreArm` lines; turn the vehicle by 90° using landmarks, and the heading in the ground station changes by 90 ± 10°.
4. The tube: the cap, power-up, `Airspeed 1 calibrated`; the leak test; the reading rises when you breathe out into the tube.
5. Each monitor: the voltage against a multimeter, the current zero, and after the first flight the correction from the charger mAh. Disconnect one sensor of the sum and make sure you see it in the ground station (half the current), because there will be no other signal.
6. The failsafe of each monitor on the ground with the propellers off: raise `BATTn_LOW_VOLT` above the present voltage, arm, wait for `Battery n is low`; restore the threshold.

On hardware the work is done when the length of `COMPASS_OFS*` is below `COMPASS_OFFS_MAX`, the field length on the ground is within 185–875 mG, `XKF4.SM` in a hover log is below 1, the readings of each monitor differ from the multimeter by no more than 0.1 V, and the `Battery n is low` message has been received from every monitor that has a threshold.

Self-check: the lab is done when:
- step 1: MOT = (−1.8, 0.6, −3.1) mG/A exactly, `COMPASS_MOTCT = 2`; the corrected field is (210, −35, 420); the interference is 27.4 ± 0.2 % at full throttle and 36.6 ± 0.2 % for 40 A at 75 % throttle; the lengths are 238.5 and 470.9 (± 0.5); for the second vector the length is 1857 ± 1 and the string is `Compass offsets too high`;
- step 2: the offsets are (−184.8, −65.3, 206.8) with a tolerance of ± 0.3; for a heading of 52°, (−163.7, −46.3, 206.8);
- step 3: the multipliers are 11.21 and 10.89 (± 0.01), 43.18 and 38.01 (± 0.02); the mask is 6; with a mask of 0, arming is refused with `PreArm: Battery 1 low voltage failsafe`; the cases are decided as "RTL at once", "nothing", "Land", "nothing"; 10.0 min;
- step 4: the methods match the selection table; exactly three mistakes are found (the current for the compensation, the sum mask, the inverted thresholds) and two `PreArm` strings are named.

**Reference for the self-check.** The correct result is the numbers of the four items above. Typical mistakes: (1) MOT = (+1.8, −0.6, +3.1): the minus was forgotten; the compensation is added to the field and must cancel the interference, and with this sign it doubles it. (2) In step 2 the offsets are (184.8, 65.3, −206.8): "measured − expected" was subtracted, while the firmware adds the offset to the measurement. (3) In step 3 the multipliers are 10.79 and 37.05: the fraction is upside down; the reading is below the reference, so the multiplier has to grow. (4) A mask of 3 instead of 6: the bits were counted from one, while bit 0 is monitor 1, that is, the sum itself, which never includes itself; only monitor 2 would be left in the sum. (5) In case 3 the answer "RTL on low": the critical threshold is checked first. (6) An interference of 27.4 % for 40 A at 75 % throttle: the division by the highest throttle was forgotten; the firmware scales the current to full throttle and shows 36.6 %. (7) In (c) with a mask of 0, the answer "a false failsafe 10 s after arming": it never gets to arming, because the pre-arm check compares the voltage with the thresholds without the timer.

## diagnostics
- **Symptom:** the rotation calibration does not finish or keeps starting over.
  Possible cause: the fitness is above the threshold: metal nearby, the compass next to the power wires, a wrong `AHRS_ORIENTATION` for an internal compass; an internal compass already has a doubled threshold.
  What to do: move to an open area, take off your phone and keys, rotate more slowly; only then `COMPASS_CAL_FIT = 32`. A compass that will not calibrate while the others are fine should be disabled with `COMPASS_USEn`.
- **Symptom:** `Mag(1) bad orientation: 4/0 1.6` or `Mag(1) internal bad orientation`.
  Possible cause: the actual rotation of the sensor does not match `COMPASS_ORIENT`, and the confidence was not high enough for an automatic fix; for an internal compass `AHRS_ORIENTATION` is wrong.
  What to do: look at the arrow on the module, set the orientation manually and repeat.
- **Symptom:** `PreArm: Compasses inconsistent`.
  Possible cause: an internal compass near the wiring differs from the external one by more than 60° in the horizontal plane or by 200 mG.
  What to do: find the slot of the internal compass from `COMPASS_PRIOn_ID` and set its `COMPASS_USEn = 0`; if two external ones disagree, check the orientation of each.
- **Symptom:** `PreArm: Check mag field (xy diff:…>100)` at one site only.
  Possible cause: rebar, a manhole cover, a car under the vehicle or next to it.
  What to do: move the vehicle 5–10 m. If the failure is everywhere, recalibrate. `ARMING_MAGTHRESH = 0` disables the check and leaves you without it in flight.
- **Symptom:** in Loiter the vehicle flies widening circles, and the heading in the ground station drifts with throttle.
  Possible cause: current interference or wrong offsets.
  What to do: switch at once to a mode without GPS (AltHold, Stabilize) and land; then the log.
  What you see in the log: `MAG.MagX/Y/Z` change together with `BAT.Curr`, `XKF4.SM` rises above 1, `XKF3.IYAW` moves away from zero.
  Consequences: a flyaway along an arc, `EKF variance`, an EKF lane switch.
- **Symptom:** `COMPASS_MOTCT = 2`, but `MAG.MOX/MOY/MOZ` in the log are zero.
  Possible cause: the first battery monitor has no current (type 3, a sum with no members, disabled).
  What to do: make the first monitor one with the current of the power circuit.
- **Symptom:** after Large Vehicle MagCal the heading in the ground station is off from the real one by 5–15°.
  Possible cause: the magnetic heading was entered instead of the true one; metal nearby; a wrong `COMPASS_ORIENT`.
  What to do: add the declination and repeat at another spot; MagFit after the first flight.
- **Symptom:** `COMPASS_LEARN = 3`, and in Loiter and Auto the heading is unsteady or the mode cannot be entered.
  Possible cause: learning has not finished: while it runs, the compass is not used for yaw (whether the mode is refused depends on the EKF yaw source; not traced in the source).
  What to do: fly straight for several seconds until `CompassLearn: Finished`, or set it back to 0 and calibrate on the ground.
- **Symptom:** the airspeed in the parking area is 5–8 m/s, or it reads low in flight.
  Possible cause: the zero was saved in wind; a leak in the tubing.
  What to do: the cap and a repeated zero calibration; the leak test.
- **Symptom:** `Airspeed sensor 1 failure. Disabling` on a windy day.
  Possible cause: `ARSPD_WIND_MAX` is below the actual wind with gusts.
  What to do: the threshold is the maximum operating wind plus 5 m/s.
- **Symptom:** `PreArm: Battery 3 unhealthy`.
  Possible cause: the monitor type was changed without a reboot; the sum has no healthy members (a mask of 0 on the last monitor); `BATTn_VOLT_PIN` is the wrong one.
  What to do: reboot, break the mask down into bits, check the input numbers against the board `hwdef`.
- **Symptom:** the current in the ground station is half of what is expected, with no failures.
  Possible cause: one sensor of the sum is unhealthy and skipped.
  What to do: look at `BATTERY_STATUS` or `BAT` for each instance.
  Consequences: the mAh are understated, and `BATT_LOW_MAH` triggers late.
- **Symptom:** the voltage of the first monitor is 15–20 % below the real one; with charged batteries, `PreArm: Battery 1 low voltage failsafe`.
  Possible cause: the avionics battery or a "current only" monitor got into the sum (a mask of 0 takes all monitors with a higher number).
  What to do: set the mask explicitly.
- **Symptom:** `PreArm: Battery n feature BATTERY_SUM not available`.
  Possible cause: the build for a board with 1 MB of flash has no "sum" monitor.
  What to do: manage without a sum (thresholds on each monitor) or take a board with more flash.
- **Symptom:** the voltage failsafe does not trigger although the threshold has been crossed.
  Possible cause: `BATT_LOW_TIMER = 0`; `BATT_FS_VOLTSRC = 1` and the resting voltage is above the threshold; the vehicle is not armed; the action is 0.
  What to do: check the four parameters of that monitor.
- **Symptom:** after a reboot in the field the battery percentage is 100 again.
  Possible cause: the mAh counter lives until a reboot.
  What to do: `BATT_ARM_VOLT` from the no-load voltage; do not reboot with a partly used battery.

## checklist
- The external compass is in slot 1, and an internal one next to the power wiring is disabled with `COMPASS_USEn` of its slot
- The calibration was done outdoors with a 3D fix; `COMPASS_SCALE` is not 0
- For Large Vehicle MagCal: `COMPASS_ORIENT` is set in advance, the heading is true
- The length of `COMPASS_OFS*` is below `COMPASS_OFFS_MAX`, and the threshold was not raised blindly
- `COMPASS_LEARN = 0` before a flight with position hold
- `ARMING_MAGTHRESH` is not 0
- CompassMot: the propellers are flipped, the vehicle is tied down, people are behind the operator, because the motors spin up
- `COMPASS_MOTCT = 2` only if monitor 1 has current; the CompassMot percentage is read as the interference at full throttle
- `COMPASS_SCALE = 0` before Large Vehicle MagCal
- The tube zero was saved under a cap, and there is no leak
- The first monitor describes the whole power circuit; the sum mask is set explicitly
- Every monitor with a threshold has a nonzero `BATTn_FS_*_ACT` and a `BATTn_LOW_TIMER` above 0, otherwise the failsafe for that battery is disabled
- `BATT_CRT_*` are below `BATT_LOW_*`; `BATT_ARM_VOLT` is set

## references
- ArduPilot Copter-4.7.2 AP_Compass.cpp (the COMPASS_* parameters) | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_Compass/AP_Compass.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_Compass_Backend.cpp (correct_field: the order of the field correction) | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_Compass/AP_Compass_Backend.cpp | primary | A
- ArduPilot Copter-4.7.2 CompassCalibrator.cpp (fitness, thresholds, orientation, scale factor) | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_Compass/CompassCalibrator.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_Compass_Calibration.cpp (the 2 × CAL_FIT threshold, mag_cal_fixed_yaw) | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_Compass/AP_Compass_Calibration.cpp | primary | A
- ArduPilot Copter-4.7.2 Compass_learn.cpp (COMPASS_LEARN = 3) | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_Compass/Compass_learn.cpp | primary | A
- ArduPilot Copter-4.7.2 ArduCopter compassmot.cpp | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/ArduCopter/compassmot.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_Arming.cpp (compass_checks, ARMING_MAGTHRESH) | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_Arming/AP_Arming.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_Airspeed.cpp and AP_Airspeed_Health.cpp (the zero, ARSPD_WIND_*) | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_Airspeed/AP_Airspeed_Health.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_BattMonitor_Params.cpp (BATT_MONITOR, thresholds, BATT_OPTIONS) | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_BattMonitor/AP_BattMonitor_Params.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_BattMonitor_Backend.cpp (failsafe, resting voltage, pre-arm checks) | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_BattMonitor/AP_BattMonitor_Backend.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_BattMonitor_Sum.cpp (BATT_SUM_MASK) | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_BattMonitor/AP_BattMonitor_Sum.cpp | primary | A
- ArduPilot Copter-4.7.2 AP_BattMonitor_Analog.cpp (the voltage and current formulas) | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_BattMonitor/AP_BattMonitor_Analog.cpp | primary | A
- ArduPilot wiki (page source): Compass Calibration, Large Vehicle MagCal | https://raw.githubusercontent.com/ArduPilot/ardupilot_wiki/master/common/source/docs/common-compass-calibration-in-mission-planner.rst | primary | A
- ArduPilot wiki (page source): Advanced Compass Setup, CompassMot, COMPASS_LEARN | https://raw.githubusercontent.com/ArduPilot/ardupilot_wiki/master/common/source/docs/common-compass-setup-advanced.rst | primary | A
- ArduPilot wiki (page source): Refining Calibration Parameters using a Flight Log (MagFit) | https://raw.githubusercontent.com/ArduPilot/ardupilot_wiki/master/common/source/docs/common-magfit.rst | primary | A
- ArduPilot WebTools MAGFit Readme | https://raw.githubusercontent.com/ArduPilot/WebTools/main/MAGFit/Readme.md | primary | B
- MAVProxy magfit.py (MagFit in MAVExplorer) | https://raw.githubusercontent.com/ArduPilot/MAVProxy/master/MAVProxy/modules/lib/magfit.py | primary | B

## notes
The parameters, values, message strings and formulas were checked by reading the tree at tag Copter-4.7.2 and the 4.7.2 metadata; the comparison with 4.6 is based on the 4.6.3 tree. The firmware was not built or run in this pass: the behavior is described from the source. Not checked and taken from the wiki and the source of the tools: the Mission Planner screens (Large Vehicle MagCal, Compass/Motor Calib), the interface of WebTools MAGFit and MAVExplorer, the "30 / 60 %" thresholds for CompassMot, and the "10° and 20°" for MagFit. The 450–550 mG range for mid latitudes, the tube leak test and the "wind plus 5 m/s" rule are engineering practice, not the source. Differences from the wiki on the date of the check: the wiki gives `COMPASS_OFFS_MAX` as 850 and an offset threshold of 600 (in 4.7.2 it is 1800 and a check of the vector length) and "up to 16 monitors" (a standard 4.7.2 build has 9). The ardupilot.org site was not reachable from the environment where the module was prepared, so the wiki pages are given as links to their source files in the ardupilot_wiki repository.
