---
id: px4-hardware-peripherals
source: content/px4/px4-hardware-peripherals.md
source_hash: 0bd75d8faa23
title: "PX4 peripherals: GPS/compass, rangefinder, airspeed, telemetry, DroneCAN, OSD, LED and buzzer"
level: L2
readingTime: 60 min
firmware: PX4 1.18 (checked against v1.18.0)
status: published
added: 2026-11-19
tags:
  - PX4
  - peripherals
  - MAVLink
  - DroneCAN
  - GPS
  - OSD
related:
  - px4-setup-scratch
  - px4-outputs-servos
  - px4-safety-return
  - px4-intro
  - px4-architecture
  - nav-rtk
  - nav-terrain
  - est-gnss
  - est-sensors
  - el-dronecan
  - link-telemetry-radios
  - comp-mavlink
  - ap-osd-video
  - inav-osd-hd
next:
  - px4-outputs-servos
---

## summary
Everything you connect to a PX4 flight controller apart from the motors and the receiver: GPS and compass, rangefinders, airspeed sensor, telemetry and MAVLink instances, DroneCAN, OSD, the status LED and the buzzer. They all follow one pattern: pick the port with a `*_CONFIG` / `*_CFG` parameter or enable the driver with a `SENS_EN_*` parameter, reboot, then check with `status` and `listener`. The module gives the PX4 1.18.0 parameter tables with defaults and the differences from 1.15–1.17, the fmu-v6x port numbers, the rule for computing a MAVLink stream in bytes per second, and what the LED colors and tunes mean. The lab needs no hardware and no simulator: assigning eight devices to Pixhawk 6X ports, a budget for a SiK link at 57600 baud, decoding the indications and finding errors in parameters; you check your answers against the reference on the page.

## theory
### The general pattern: parameter → reboot → check
In PX4 a peripheral driver does not run "by itself". A script starts it at boot, and only if a parameter allows it. There are three ways.

- **UART.** The driver has a port parameter: `GPS_1_CONFIG`, `MAV_1_CONFIG`, `SENS_TFMINI_CFG`, `MSP_OSD_CONFIG`. The value is a port number from the table below; 0 means the driver is off. The baud rate comes from `SER_<port>_BAUD`. From these definitions the build generates the `rc.serial` script: for each driver it reads the port parameter and runs a command such as `tfmini start -d /dev/ttyS1`.
- **I²C and SPI.** There is no port to pick; the driver is enabled with `SENS_EN_<sensor>`. The `rc.sensors` script checks the parameter and starts the driver on the external I²C bus (the `-X` flag).
- **DroneCAN.** The bus driver is enabled with `UAVCAN_ENABLE`, the data types it accepts with `UAVCAN_SUB_*`.

Almost all of these parameters are marked `reboot_required`: nothing changes until you reboot. The check always has two steps, in the QGC MAVLink Console:

1. The driver is running: `gps status`, `tfmini status`, `mavlink status`, `uavcan status`, `msp_osd status`, `airspeed_selector status`, `sensors status`.
2. Data is flowing: `listener <topic>`: `sensor_gps`, `sensor_mag`, `distance_sensor`, `differential_pressure`, `airspeed_validated`, `telemetry_status`. The second instance of a topic is the `-i 1` flag. What a uORB topic and `listener` are is covered in px4-architecture.

{{diagram:px4-periph-enable-flow|The parameter only allows the start: the driver is started by a script at boot, so the order is always the same: parameter, reboot, status, listener.}}

**One port, one driver.** If two parameters point at the same port, the script gives the port to the first one and prints `Conflicting config for /dev/ttyS…` for the second (visible in `dmesg`) and does not start it. Which one comes first depends on the order of drivers in the build, so do not rely on it.

**The driver may not be in the firmware.** The set of drivers is defined by the `boards/<vendor>/<board>/default.px4board` file. If the parameter is not in the QGC list, the driver is not built; you add it with your own build (`make px4_fmu-v6x_default boardconfig`). In the tables below the "v6x" column shows whether the driver is in the stock Pixhawk 6X firmware (px4/fmu-v6x) of version 1.18.0.

### fmu-v6x ports
Port numbers are the same on every board (`Tools/serial/generate_config.py`); only the set of ports differs.

| Value | Name in QGC | Pixhawk 6X connector | Device | `SER_*_BAUD`, default | Used by default |
|---|---|---|---|---|---|
| 0 | Disabled | — | — | — | — |
| 101 | TELEM 1 | TELEM1 | `/dev/ttyS6` | `SER_TEL1_BAUD` = 57600 | `MAV_0_CONFIG` |
| 102 | TELEM 2 | TELEM2 | `/dev/ttyS4` | `SER_TEL2_BAUD` = 921600 | — |
| 103 | TELEM 3 | TELEM3 | `/dev/ttyS1` | `SER_TEL3_BAUD` = 57600 | — |
| 201 | GPS 1 | GPS1 | `/dev/ttyS0` | `SER_GPS1_BAUD` = 0 (auto) | `GPS_1_CONFIG` |
| 202 | GPS 2 | GPS2 | `/dev/ttyS7` | `SER_GPS2_BAUD` = 0 (auto) | — |
| 300 | Radio Controller | PX4IO/RC line | `/dev/ttyS5` | `SER_RC_BAUD` = 0 | in the list since 1.17; on a board with an IO processor the line is taken by `px4io` |
| 401 | EXT2 | UART4 & I2C | `/dev/ttyS3` | `SER_EXT2_BAUD` = 57600 | — |
| 1000 | Ethernet | ETH | network, UDP | — | `MAV_2_CONFIG` |

The value 1000 is available only to drivers with network support: MAVLink and uXRCE-DDS. `SER_*_BAUD` takes a fixed list of rates from 50 to 3 000 000; 0 means "auto" and only suits drivers that find the rate themselves (GPS).

{{diagram:px4-periph-ports-v6x|fmu-v6x has six freely assignable UARTs: two GPS units, a companion, a telemetry radio, a rangefinder and an OSD take all of them, while airspeed and the ESCs go to I²C and CAN.}}

### GPS
| Parameter | Default | Values |
|---|---|---|
| `GPS_1_CONFIG` / `GPS_2_CONFIG` | 201 / 0 | port of the main and the second receiver |
| `SER_GPS1_BAUD` | 0 | auto: the driver tries the rates itself |
| `GPS_1_PROTOCOL` / `GPS_2_PROTOCOL` | 1 | 0 auto detect (slower start), 1 u-blox, 2 MTK, 3 Ashtech / Trimble, 4 Emlid Reach, 5 Femtomes, 6 NMEA |
| `GPS_1_GNSS` / `GPS_2_GNSS` | 0 | bitmask: bit 0 GPS (with QZSS), 1 SBAS, 2 Galileo, 3 BeiDou, 4 GLONASS, 5 NAVIC; 0 means as the receiver is configured. u-blox only |
| `GPS_UBX_DYNMODEL` | 7 | 2 stationary, 4 automotive, 6 airborne < 1 g, 7 airborne < 2 g, 8 airborne < 4 g |
| `GPS_SAT_INFO` | 0 | 1 publishes `satellite_info` |
| `GPS_CFG_WIPE` | 0 | 1 wipes the flash configuration of the u-blox module at boot (since 1.17) |
| `SENS_GPS_MASK` | 7 | blending of two receivers: bit 0 uses speed accuracy, 1 horizontal position accuracy, 2 vertical position accuracy; 0 means no blending |
| `SENS_GPS_PRIME` | 0 | primary instance without blending: 0, 1; −1 means equal priority |
| `SENS_GPS_TAU` | 10 s | 1…100 s: time constant for smoothing the offsets between receivers |

**`GPS_UBX_DYNMODEL` across versions.** In 1.15 and 1.16 the multicopter airframe defaults (`rc.mc_defaults`) set 6, "airborne < 1 g". In 1.17 that line is gone, and a multicopter gets the parameter default, 7. A plane gets 8 in all three versions. If you fly 1.16 or older, set 7 by hand: the model tells the receiver's filter what dynamics to expect, and a multicopter easily exceeds 1 g.

**Two receivers.** Each one publishes its own `sensor_gps` (instances 0 and 1), and the `sensors` module combines them into `vehicle_gps_position`, which EKF2 reads. With a nonzero `SENS_GPS_MASK` and two receivers that have at least a 2D fix, the solution is blended. For each enabled metric a receiver's weight is inversely proportional to the square of its reported error: for two receivers `w₁ = σ₂² / (σ₁² + σ₂²)`, where σ is `eph`, `epv` or the speed accuracy. The final weight is the mean of the weights over the enabled metrics. If the receivers do not report accuracy, or one has lost its fix, blending turns off and hard selection takes over: `SENS_GPS_PRIME` while it has a 3D fix, otherwise the receiver with the best fix type and the most satellites. `SENS_GPS_MASK` = 0 always means hard selection.

Choosing a module (an M10 with a compass, on a mast, away from the power wiring and the VTX) is in est-gnss. RTK, `GPS_UBX_MODE`, dual-antenna heading and `GPS_YAW_OFFSET` are in nav-rtk. The antenna offset from the center of mass is `SENS_GPS0_OFFX/Y/Z` (the second receiver has `SENS_GPS1_*`, the delay is `SENS_GPS0_DELAY`, the binding of a set to a receiver is `SENS_GPS0_ID`); before 1.18 these were the shared `EKF2_GPS_POS_X/Y/Z` and `EKF2_GPS_DELAY`, and on upgrade the offsets migrate to set 0 and the delay to both sets. GPS over CAN is on by default: `UAVCAN_SUB_GPS` = 1.

### Compass
| Parameter | Default | Meaning |
|---|---|---|
| `CAL_MAGn_ID` | 0 | ID of the sensor in slot n (0…3), written by calibration |
| `CAL_MAGn_PRIO` | −1 | −1 uninitialized, 0 disabled, 1 Min, 25 Low, 50 Medium, 75 High, 100 Max |
| `CAL_MAGn_ROT` | −1 | −1 internal, 0 no rotation, 1 Yaw 45° … 100 custom angles `CAL_MAGn_ROLL` / `_PITCH` / `_YAW` |
| `SENS_MAG_AUTOROT` | 1 | calibration sets the rotation of an external compass by itself |
| `SENS_MAG_MODE` | 1 | 1 publishes only the primary compass, 0 all of them |
| `SENS_MAG_SIDES` | 63 | calibration sides: 63 six, 38 three, 34 two |
| `SENS_MAG_AUTOCAL` | 0 (before 1.18: 1) | initializes the calibration of an uncalibrated compass from the bias estimate (hard iron only, not continuous in-flight learning); since 1.18 an uncalibrated compass no longer saves an initial calibration by itself by default, so calibrate in QGC |
| `CAL_MAG_COMP_TYP` | 0 | compensation of current interference: 1 throttle-based, 2 and 3 current-based from battery 0 and 1 |
| `COM_ARM_MAG_ANG` | 60° | allowed inconsistency between compasses before arming |
| `COM_ARM_MAG_STR` | 2 | strong magnetic interference: 0 disabled, 1 deny arming, 2 warning only |

**External versus internal.** When a compass appears for the first time, the firmware sets its priority by itself: 50 for an internal one, 75 for an external one (the barometer works the same way; external accelerometers and gyros, an IMU over DroneCAN for example, get 25 instead of 75 since 1.18, so that a new uncalibrated external IMU does not take over as primary; `sensor_calibration/*.hpp`, v1.18.0). That is why the compass in the GPS module becomes primary without you doing anything. To disable the internal one, set `CAL_MAGn_PRIO` = 0 in its slot (find the slot by `CAL_MAGn_ROT` = −1). There are no `SENS_EXT_MAG*` parameters in 1.15–1.17: everything goes through `CAL_MAGn_*`.

"Compass inconsistent" before arming means the compasses disagree by more than `COM_ARM_MAG_ANG`: a wrong rotation for the external one, power wiring nearby, or an old calibration. Calibration is QGC → Sensors → Compass. How the compass is used in estimation (`EKF2_MAG_TYPE`: 0 automatic, 1 heading only, 5 none, 6 initial heading only) is in est-sensors. Compass over CAN: `UAVCAN_SUB_MAG` = 1.

### Rangefinders
| Family | Parameter | Bus | v6x |
|---|---|---|---|
| Benewake TFmini, ISTRA24 | `SENS_TFMINI_CFG`; model `SENS_TFMINI_HW` 1…3 | UART, the driver sets 115200 itself | yes |
| Benewake TF02 Pro | `SENS_EN_TF02PRO` = 1 | I²C | yes |
| LightWare, serial | `SENS_SF0X_CFG`; model `SENS_EN_SF0X`: 1 SF02, 2…4 SF10/a/b/c, 5 SF11/c, 6…7 SF30/b/c, 8 LW20/c | UART: 9600 for models 1…4, 115200 for 5…8 | yes |
| LightWare, I²C | `SENS_EN_SF1XX`: 1…3 SF10/a/b/c, 4 SF11/c, 5…6 SF/LW20/b/c, 7 SF/LW30/d, 8 GRF250, 9 GRF500 | I²C | yes |
| LightWare SF45 | `SENS_EN_SF45_CFG` (this is the port), `SF45_ORIENT_CFG`, `SF45_YAW_CFG` | UART | no |
| Lidar-Lite | `SENS_EN_LL40LS`: 1 PWM, 2 I²C | PWM / I²C | yes (I²C) |
| ST VL53L0X, VL53L1X | `SENS_EN_VL53L0X`, `SENS_EN_VL53L1X` = 1 | I²C | yes |
| Aerotenna uLanding | `SENS_ULAND_CFG` | UART | yes |
| TeraRanger | `SENS_EN_TRANGER`: 1 autodetect, 2 One, 3 Evo 60 m, 4 Evo 600 Hz, 5 Evo 3 m | I²C | no |
| MaxBotix MB12xx | `SENS_EN_MB12XX` = 1, `SENS_MB12_n_ROT` | I²C | no |
| LeddarOne, Lanbao CM8JL65 | `SENS_LEDDAR1_CFG`, `SENS_CM8JL65_CFG` | UART | no |
| MappyDot, PGA460, HY-SRF05 | `SENS_EN_MPDT`, `SENS_EN_PGA460`, `SENS_EN_SR05` | I²C / UART / GPIO | no |
| DroneCAN | `UAVCAN_SUB_RNG` = 1; `UAVCAN_RNG_MIN` / `_MAX` = 0 / 999 m (in 1.15: 0.3 / 200) | CAN | yes |
| MAVLink | the `DISTANCE_SENSOR` message from a companion | any MAVLink instance | yes |

**Orientation.** The drivers that the boot script starts are started without the `-R` flag and assume the sensor faces down (code 25). Only some families have their own orientation parameter: `SENS_CM8JL65_R_0`, `SF45_ORIENT_CFG`, `SENS_MB12_n_ROT`, `SENS_MPDTn_ROT`. Codes for `SENS_CM8JL65_R_0` (`SF45_ORIENT_CFG` takes only 24 and 25): 25 down, 24 up, 0 forward, 4 backward, 6 left, 2 right; `SENS_MB12_n_ROT` and `SENS_MPDTn_ROT` take a yaw rotation 0…7 instead.

`SYS_HAS_NUM_DIST` (default 0) is how many rangefinders with healthy data the preflight check requires. How rangefinder height enters the estimate (`EKF2_RNG_CTRL`, `EKF2_RNG_POS_*`) and terrain following are in nav-terrain.

### Airspeed sensor
| Sensor | Parameter | v6x |
|---|---|---|
| TE MS4525DO | `SENS_EN_MS4525DO` = 1 | yes |
| TE MS5525DSO | `SENS_EN_MS5525DS` = 1 | yes |
| Sensirion SDP3x | `SENS_EN_SDP3X` = 1 | yes |
| Amphenol AUAV | `SENS_EN_AUAVX`: 1 L05D, 2 L10D, 3 L30D, since 1.18 also L60D | yes in 1.17; the v1.18.0 default build drops the driver again (your own build) |
| TE MS4515, Eagle Tree, ASP5033 | `SENS_EN_MS4515`, `SENS_EN_ETSASPD`, `SENS_EN_ASP5033` | no |
| DroneCAN | `UAVCAN_SUB_ASPD` = 1 (airspeed), `UAVCAN_SUB_DPRES` = 1 (differential pressure) | yes |

All of these sensors are on I²C. The data path: driver → `differential_pressure` → the `sensors` module computes indicated airspeed (`airspeed`) → `airspeed_selector` checks it and publishes `airspeed_validated`, which the controllers use.

| Parameter | Default | Meaning |
|---|---|---|
| `SYS_HAS_NUM_ASPD` | 0; plane and VTOL: 1 | how many sensors the preflight check requires |
| `CAL_AIR_CMODEL` | 0 | tube model: 0 with Pitot, 1 without Pitot (1.5 mm tubes), 2 tube pressure drop |
| `CAL_AIR_TUBELEN` / `CAL_AIR_TUBED_MM` | 0.2 m / 1.5 mm | tube length and diameter for models 1 and 2 |
| `SENS_DPRES_OFF` | 0 | zero offset, written by calibration |
| `ASPD_PRIMARY` | 1 | 0 groundspeed minus windspeed, 1…3 a sensor, 4 thrust-based airspeed (since 1.17) |
| `ASPD_DO_CHECKS` | 7 | bit 0 data missing for 1 s, 1 data stuck for 2 s, 2 innovation, 3 load factor, 4 first principle (airspeed change against throttle and pitch) |
| `ASPD_FALLBACK` | 0 | on failure: 0 other airspeed sensors only, 1 groundspeed minus windspeed, 2 thrust-based estimate |
| `ASPD_FS_INNOV` / `ASPD_FS_INTEG` | 5 m/s / 10 m | innovation threshold and innovation integral threshold for failure |
| `ASPD_FS_T_STOP` / `ASPD_FS_T_START` | 1 s / −1 s | delay before switching off and back; −1 means no re-enabling in flight |
| `ASPD_SCALE_1…3` | 1.0 | 0.5…2.0: scale of indicated airspeed, estimated in flight |
| `ASPD_SCALE_APPLY` | 2 | 0 do not apply, 1 after disarm, 2 in air |
| `FW_USE_AIRSPD` | 1 | use airspeed in the fixed-wing controllers |

Renames: before 1.17 there was a boolean `ASPD_FALLBACK_GW` instead of `ASPD_FALLBACK` (the firmware converts it); before 1.15 `FW_USE_AIRSPD` was called `FW_ARSP_MODE`, with the opposite meaning (1 = do not use).

**Do you need the sensor.** A plane or a VTOL does: airspeed drives control surface scaling, speed hold and the VTOL transition, and the airframe requires one sensor by default. You can fly without it: `SYS_HAS_NUM_ASPD` = 0 and either `FW_USE_AIRSPD` = 0 (the controllers do not use airspeed) or `ASPD_PRIMARY` = 0 (airspeed is estimated as groundspeed minus wind), and then nothing measures your stall margin. A multicopter does not need the sensor. Calibration is QGC → Sensors → Airspeed: first shield the tube from the wind (the zero is taken), then blow into it from the front.

### Telemetry and MAVLink instances
PX4 runs up to three MAVLink instances, each with its own port, message set and rate limit.

| Parameter | Instances 0 / 1 / 2 | Meaning |
|---|---|---|
| `MAV_n_CONFIG` | 101 / 0 / 0 (fmu-v6x: `MAV_2_CONFIG` = 1000) | port |
| `MAV_n_MODE` | 0 / 2 / 0 | message set and rates |
| `MAV_n_RATE` | 1200 / 0 / 0 (fmu-v6x: `MAV_2_RATE` = 100000) | rate limit, **bytes/s**; 0 means half the UART bandwidth (`baud / 20`); on USB 100 000 B/s |
| `MAV_n_FORWARD` | 1 / 0 / 0 | forward other systems' messages to the other instances |
| `MAV_n_RADIO_CTL` | 1 / 1 / 1 (fmu-v6x: `MAV_2_RADIO_CTL` = 0) | throttle the stream by `RADIO_STATUS` from the radio |
| `MAV_n_FLOW_CTRL` | 2 | RTS/CTS: 0 force off, 1 force on, 2 auto-detected |
| `MAV_n_UDP_PRT` / `_REMOTE_PRT` / `_BROADCAST` | 14556 / 14550 / 1 on instance 0 | network; fmu-v6x for instance 2: 14550 / 14550 / 1 |

`MAV_n_MODE` values: 0 Normal (ground station), 1 Custom (sends nothing, streams are set by command), 2 Onboard (companion: high rates), 3 OSD, 4 Magic, 5 Config (USB), 7 Minimal, 8 External Vision, 10 Gimbal, 11 Onboard Low Bandwidth, 12 uAvionix, 13 Low Bandwidth (since 1.16).

**Baud and bytes.** On an 8N1 port a byte takes 10 bits: start, eight data bits, stop. The port limit is `baud / 10` bytes/s: 57600 baud gives 5760 B/s, 921600 gives 92160 B/s. `MAV_n_RATE` = 0 gives `baud / 20`: 2880 and 46080 B/s. Instance 0 defaults not to 0 but to 1200 B/s, about a fifth of what a 57600 port carries.

**What happens when you exceed it.** Messages are either constant-rate (`HEARTBEAT` at 1 Hz and a few service messages) or scalable. The firmware computes the requested stream as the sum of "size × rate" and a multiplier:

`mult = (MAV_n_RATE − constant-rate streams) / scalable streams`, constrained to 0.05…1.

The rate of every scalable message is multiplied by `mult`. There is no error: telemetry simply arrives less often than you expected, `ATTITUDE` at 15 Hz becomes 7.5. The firmware takes the full message size: the payload length from the MAVLink definition plus 12 bytes of MAVLink 2 header and checksum. `mavlink status` shows the current values (the `tx rate max` and `tx rate mult` lines), `mavlink status streams` lists the streams, and `mavlink stream -d /dev/ttyS6 -s ATTITUDE -r 5` changes the rate of one stream.

**SiK radio.** The radio sends `RADIO_STATUS` with the fill level of its `txbuf` buffer. With `MAV_n_RADIO_CTL` = 1 the firmware throttles the stream further: `txbuf` below 25 % multiplies by 0.8, below 35 % by 0.975, above 50 % by 1.025. If no `RADIO_STATUS` arrives for `MAV_RADIO_TOUT` = 5 s, the throttling resets. `MAV_SIK_RADIO_ID` sets the radio's NETID from the vehicle. Setting up the radios themselves, range and 4G links are in link-telemetry-radios.

**Companion.** A Raspberry Pi or a Jetson on TELEM2: `MAV_1_CONFIG` = 102, `MAV_1_MODE` = 2, `SER_TEL2_BAUD` = 921600, wires TX↔RX plus ground, the companion powered from its own BEC. If you need ROS 2 instead of MAVLink, put `UXRCE_DDS_CFG` on the same port and set `MAV_1_CONFIG` back to 0 (px4-ros2). The onboard protocol is in comp-mavlink.

Versions: `MAV_PROTO_VER` defaults to 2 in 1.17 (0 in 1.15–1.16). The Pixhawk 6X Ethernet defaults are the same in all three versions (in 1.16 the Skynode base boards got uXRCE-DDS on Ethernet instead of MAVLink).

### DroneCAN
| Parameter | Default | Meaning |
|---|---|---|
| `UAVCAN_ENABLE` | 0 | 0 disabled; 1 sensors, node IDs set by hand; 2 sensors, the flight controller allocates node IDs and updates node firmware; 3 the same plus outputs to ESCs and servos |
| `UAVCAN_NODE_ID` | 1 | 1…125: the flight controller's own node ID |
| `UAVCAN_BITRATE` | 1 000 000 | 20 000…1 000 000 bit/s |
| `UAVCAN_SUB_GPS`, `_GPS_R`, `_MAG` | 1 | subscribe to GPS, GPS relative position, compass |
| `UAVCAN_SUB_ASPD`, `_BARO`, `_DPRES`, `_FLOW`, `_HYGRO`, `_ICE`, `_IMU`, `_RNG`, `_BTN`, `_FUEL` | 0 | the other types are enabled by hand; `_FUEL` since 1.16 |
| `UAVCAN_SUB_BAT` | 0 | 1 raw battery data, 2 filtered |
| `UAVCAN_PUB_RTCM`, `_MBD`, `_ARM` | 0 | publish RTK corrections, moving baseline corrections, arming status to the bus |
| `UAVCAN_LGT_MODE` (since 1.18) | 1 | CAN lights, when to turn on the navigation functions: 0 always off, 1 when armed, 2 when prearmed, 3 always on; since 1.18 together with `UAVCAN_LGT_NUM` (1), `UAVCAN_LGT_IDn` and `UAVCAN_LGT_FNn`, the ID and function of each light (before 1.18 there was no common mode, but a separate mode per light type: `UAVCAN_LGT_ANTCL` / `_STROB` / `_NAV` / `_LAND`, removed without migration) |
| `UAVCAN_ESC_IFACE` | 255 | which CAN interfaces get ESC commands (since 1.17) |

With `UAVCAN_ENABLE` = 3 the Actuators screen shows the `UAVCAN_EC_FUNCn` outputs (ESC 1…12, values 1…8191) and `UAVCAN_SV_FUNCn` (servos 1…15, 0…1000, disarmed 500); in 1.17 there were 8 of each. Functions are assigned the same way as for PWM outputs (`px4-outputs-servos`); do not assign one motor to CAN and PWM at the same time. Check with `uavcan status`; a node's parameters are `uavcan param list <node ID>`.

If a node does not show up: `UAVCAN_ENABLE` is still 0; the node's bitrate differs from `UAVCAN_BITRATE`; there are no terminators at the ends of the bus; with value 1 two nodes have the same ID, or an ID matches `UAVCAN_NODE_ID`; the node is visible but there is no data: its `UAVCAN_SUB_*` is off. Bus physics, terminators and node IDs are in el-dronecan. The `CANNODE_*` parameters belong not to the flight controller but to PX4 firmware running on the CAN node itself. Cyphal is a separate driver (`CYPHAL_ENABLE`); do not mix it with DroneCAN.

### OSD
The `msp_osd` driver sends telemetry to the video transmitter over MSP.

| Parameter | Default | Meaning |
|---|---|---|
| `MSP_OSD_CONFIG` | 0 | port; the driver sets the rate itself, 115200, and `SER_*_BAUD` has no effect |
| `OSD_SYMBOLS` | 16383 | element mask: bits 0…13 are craft name, DISARMED, latitude, longitude, satellites, speed, home distance and home direction, voltage, current, mAh, RSSI, altitude, vario; 18 crosshairs, 19 average cell voltage, 21 power; 14…17 and 20 are unused |
| `OSD_CH_HEIGHT` | 0 | −8…8: vertical position of the crosshairs |
| `OSD_LOG_LEVEL` | 3 | minimum severity of messages shown: 0 Emergency … 3 Error … 7 Debug |
| `OSD_SCROLL_RATE` / `OSD_DWELL_TIME` | 125 / 500 ms | scrolling of long messages |
| `OSD_RC_STICK` | 1 | forward stick input to the VTX menu when disarmed (since 1.16) |

`msp_osd` has no warning thresholds for voltage or altitude like Betaflight and INAV: the screen shows PX4 text messages at `OSD_LOG_LEVEL` severity or higher.

- **Versions.** In 1.15 the driver sent DJI legacy MSP elements. Since 1.16 it has been rewritten for MSP DisplayPort and can read the VTX settings. PX4 does not document which goggles this works with (DJI O3/O4, Walksnail, HDZero), so test it on your own setup.
- **Build.** The stock fmu-v6x firmware has `msp_osd` in all three versions (the `CONFIG_DRIVERS_OSD_MSP_OSD=y` line), as does fmu-v5x. fmu-v6c, Kakute H7 and Matek H743 do not have it; there you need your own build.
- **Analog OSD.** The `atxxxx` driver (AT7456 chip): `OSD_ATXXXX_CFG` 0 disabled, 1 NTSC, 2 PAL. In 1.17.0 it is built for Kakute F7, Kakute H7 Wing, Kakute H7 Dual IMU, fmu-v5, RadioLink PIX6, X-MAV AP-H743v2 and a few more boards; the stock Matek H743 and Kakute H7 / H7 v2 / H7 mini firmware does not have it, even though the chip is on the board, so you need your own build. fmu-v6x has no such chip.
- **MAVLink OSD.** An external OSD that reads MAVLink gets an instance with `MAV_n_MODE` = 3.

HD system grids and setup in other firmware are in ap-osd-video and inav-osd-hd.

### Status LED
PX4 drives one RGB status LED, usually located in the GPS module (the `rgbled`, `rgbled_ncp5623c`, `rgbled_lp5562` and `rgbled_is31fl3195` drivers are probed at boot). Brightness is `SYS_RGB_MAXBRT` (0…1, default 1; 0 turns it off). Test with `led_control test`.

| What you see | State |
|---|---|
| Red, fast blink (5 Hz) | disarmed, preflight checks failed |
| Blue, breathing (1.6 s cycle) | disarmed, checks passed, no global position or home position |
| Green, breathing | disarmed, checks passed, position and home available |
| Blue or green, solid | armed; the color means the same for position |
| Amber, solid or breathing | battery below the Low threshold |
| Red, solid or breathing | battery at the Critical level, and only there. At the Emergency level the code sets no battery color: the LED goes back to blue or green (to purple if `COM_LOW_BAT_ACT` started a failsafe) |
| Purple, solid | armed, failsafe active |
| Purple, continuous fast blink | overload: CPU above `COM_CPU_MAX` (95 %) or RAM above 99 % |
| Yellow, fast blink | ready to throw (throw launch) |
| Three fast flashes in 0.7 s | event: green for success, home set, mission accepted; white for neutral; yellow for a mission with a warning; red for failure |

Priority in the code, top down: overload, ready to throw, armed, failed checks, ready. The failsafe color beats the battery color, and the battery color beats the position color.

**Emergency does not look like an emergency.** The red color and tune 8 are tied to the Critical level exactly. When the battery drains further, to Emergency (`BAT_EMERGEN_THR`), with `COM_LOW_BAT_ACT` = 0 (the default, warning only) the LED turns from red back to green or blue and the battery tune stops: the vehicle looks healthy exactly when you must land immediately. With `COM_LOW_BAT_ACT` = 2, 3 or 5 (5 since 1.18) a failsafe triggers: the LED is purple and the buzzer beeps rapidly. The rule: a red LED that "went away by itself" is not a battery recovery; read the level in QGC or on the OSD, not from the LED (`px4-safety-return`).

PX4 does not support WS2812 addressable strips on the flight controller outputs (the `neopixel` driver is built only for a few boards); for external lights use DroneCAN and `UAVCAN_LGT_*`.

### Buzzer and tunes
The `tone_alarm` driver plays tunes from `tune_definition.desc`. To listen to any of them: `tune_control play -t <number>`.

| No. | Name | When it plays |
|---|---|---|
| 1 | STARTUP | normal boot |
| 2 | ERROR_TUNE | at boot: parameters failed to import, a hardfault dump was found, IO did not start; after a crash with `EV_TSK_RC_LOSS` = 1 |
| 3 | NOTIFY_POSITIVE | success: calibration, mission accepted, safety released, takeover with the sticks |
| 4 | NOTIFY_NEUTRAL | a calibration step; safety engaged; after disarm: "safe to approach" |
| 5 | NOTIFY_NEGATIVE | failure: arming or mode change rejected, calibration or mission not accepted |
| 6 | ARMING_WARNING | once on arming (a long tone, 3 s); ready to throw |
| 7 | BATTERY_WARNING_SLOW | battery Low, repeating |
| 8 | BATTERY_WARNING_FAST | battery Critical (the Emergency level has no tune of its own); the same sound is a failsafe while armed |
| 11 | PARACHUTE_RELEASE | parachute release command on flight termination |
| 12 | SINGLE_BEEP | compass calibration: start rotating the vehicle |
| 13 | HOME_SET | home position set |
| 14 / 15 | SD_INIT / SD_ERROR | card formatted at boot / formatting failed |
| 16 / 17 / 18 | PROG_PX4IO / _OK / _ERR | IO processor flashing: in progress / success / error |
| 19 | POWER_OFF | power-off button pressed |

Tunes 9 (GPS_WARNING) and 10 (ARMING_FAILURE) are defined, but nothing calls them in 1.17.0 and 1.18.0. `CBRK_BUZZER` = 782097 disables the buzzer entirely, 782090 only the startup tune (the boot error tune still plays). `EV_TSK_RC_LOSS` (default 0) is a "find me" alarm: if the vehicle was armed, had an RC signal and lost it, tune 2 plays continuously after disarm.

### ESC telemetry and RPM
RPM and current from the ESCs arrive three ways: over UART (`DSHOT_TEL_CFG`, another port parameter from the same table), over the signal wire (bidirectional DShot: since 1.16; in 1.18 the −6/−7/−8 values in the group's `PWM_AUX_TIMn`, in 1.16–1.17 `DSHOT_BIDIR_EN`; since 1.18, with `DSHOT_BIDIR_EDT` = 1, also temperature, voltage and current) and over DroneCAN. All of it lands in the `esc_status` topic. A separate RPM sensor: `SENS_EN_PCF8583` (I²C) or a timer input with the RPM Input function and `RPM_CAP_ENABLE` = 1; the stock fmu-v6x firmware of 1.17.0 and 1.18.0 has neither driver, so you need your own build. Details are in `px4-outputs-servos`.

### Place in the system

- **Takes in:** the first-setup order and the receiver port (`px4-setup-scratch`); the uORB topic layout and `listener` (`px4-architecture`); CAN bus physics (`el-dronecan`); radio setup (`link-telemetry-radios`); choosing a GPS module (`est-gnss`).
- **Gives out:** `vehicle_gps_position`, `sensor_mag`, `distance_sensor`, `airspeed_validated` to state estimation (`est-sensors`, `nav-terrain`, `nav-rtk`); the MAVLink link to the ground station and the companion (`comp-mavlink`); DroneCAN outputs to the motors (`px4-outputs-servos`); LED and buzzer indication to the pilot.
- **If you get it wrong here:** two drivers on one port mean no GPS or telemetry and arming denied; a `MAV_n_RATE` that does not fit the link means sparse telemetry and a false data link loss (`px4-safety-return`); a wrong compass rotation means "toilet bowling" in Position (`est-sensors`); a rangefinder not facing down means height jumps (`nav-terrain`).

## practice
An exercise without hardware or a simulator. You need an editor or paper and a calculator. All answers follow from the theory tables, and you check them against the reference at the end.

### Step 1. Port assignment on fmu-v6x
The vehicle: a VTOL plane on a Pixhawk 6X, PX4 1.18. You need to connect:

- two u-blox GPS receivers (UART);
- a TFmini rangefinder (UART);
- an MS4525DO airspeed sensor (I²C);
- a SiK radio at 57600 baud;
- a companion with MAVLink at 921600 baud;
- four ESCs over DroneCAN;
- a video transmitter with MSP DisplayPort.

Task A. Make a table: device, port or bus, parameter and its value, baud rate. Do not use port 300: on the Pixhawk 6X it is the IO processor line.

Task B. Find three errors in this fragment (a teaching example, put together by hand):
```
GPS_1_CONFIG      201
GPS_2_CONFIG      102
MAV_0_CONFIG      101
MAV_0_RATE        57600
SER_TEL1_BAUD     57600
MAV_1_CONFIG      102
MAV_1_MODE        2
SER_TEL2_BAUD     921600
SENS_TFMINI_CFG   103
SER_TEL3_BAUD     57600
MSP_OSD_CONFIG    103
```

### Step 2. MAVLink budget on a SiK link
The radio is on TELEM1: `SER_TEL1_BAUD` = 57600, `MAV_0_MODE` = 0, `MAV_0_RATE` = 1200. Take eleven Normal-mode streams (the heaviest of about fifty; on a real vehicle the total is larger) with rates from `mavlink_main.cpp` and sizes "payload + 12 bytes":

| Message | Rate, Hz | Payload, bytes | On the wire, bytes |
|---|---|---|---|
| `ATTITUDE` | 15 | 28 | 40 |
| `ATTITUDE_QUATERNION` | 10 | 48 | 60 |
| `GLOBAL_POSITION_INT` | 5 | 28 | 40 |
| `GPS_RAW_INT` | 5 | 52 | 64 |
| `RC_CHANNELS` | 5 | 42 | 54 |
| `VFR_HUD` | 4 | 20 | 32 |
| `SYS_STATUS` | 1 | 43 | 55 |
| `ALTITUDE` | 1 | 32 | 44 |
| `GPS2_RAW` | 1 | 57 | 69 |
| `BATTERY_STATUS` | 0.5 | 54 | 66 |
| `DISTANCE_SENSOR` | 0.5 | 39 | 51 |

The constant-rate stream is `HEARTBEAT`: 1 Hz, 9 + 12 = 21 bytes.

A worked example, the first row: `ATTITUDE` gives 15 × 40 = 600 B/s. Compute:

1. The port limit in bytes per second, and what fraction of it `MAV_0_RATE` = 1200 is.
2. The sum of the scalable streams, B/s.
3. The multiplier `mult` at `MAV_0_RATE` = 1200, and the actual rates of `ATTITUDE` and `GLOBAL_POSITION_INT`.
4. The same with `MAV_0_RATE` = 0. Does the set fit without throttling?
5. By mistake someone set `MAV_0_MODE` = 2 (Onboard) on the same radio. Eight of its streams: `TIMESYNC` 10 Hz × 30, `HIGHRES_IMU` 50 × 75, `LOCAL_POSITION_NED` 30 × 40, `ATTITUDE` 100 × 40, `ODOMETRY` 30 × 245, `ATTITUDE_QUATERNION` 50 × 60, `GLOBAL_POSITION_INT` 50 × 40, `RC_CHANNELS` 20 × 54. Find the sum, `mult` at 1200 B/s and the rate of `ATTITUDE`.
6. The same Onboard set on TELEM2: 921600 baud, `MAV_1_RATE` = 0. The limit and `mult`.

### Step 3. Indications: state and action
For each observation write down the vehicle state and what to do.

1. After power-on the LED blinks red fast, the boot tune is normal.
2. The LED is breathing blue.
3. At power-on, instead of the startup tune: three identical tones, a pause, three more (tune 2).
4. In flight the LED is solid amber, the buzzer repeats a single tone slowly.
5. In flight the LED turned solid purple, the buzzer beeps rapidly.
6. On the ground, disarmed, the LED blinks purple fast and continuously.
7. Right after arming: a long low tone of about three seconds.
8. After landing and disarming: two short tones and three white flashes.
9. The vehicle crashed, the transmitter was switched off, the buzzer plays tune 2 continuously.

### Step 4. Masks and three errors
First, two masks:

- `GPS_1_GNSS` = 21: which systems are enabled? Which number enables GPS, Galileo and BeiDou?
- Which `OSD_SYMBOLS` value leaves only DISARMED, satellites, voltage, current, mAh and altitude on screen?

Then a parameter fragment of the same vehicle, but with the airspeed sensor on the DroneCAN bus and one TFmini rangefinder (a teaching example, put together by hand). Find three errors and name the rule from the theory for each.
```
SYS_HAS_NUM_ASPD    1
SENS_EN_MS4525DO    0
ASPD_PRIMARY        1
UAVCAN_ENABLE       2
UAVCAN_NODE_ID      1
UAVCAN_BITRATE      1000000
UAVCAN_SUB_GPS      1
UAVCAN_SUB_ASPD     0
UAVCAN_EC_FUNC1     101
UAVCAN_EC_FUNC2     102
SENS_GPS_MASK       7
GPS_2_CONFIG        0
GPS_1_GNSS          0
SENS_TFMINI_CFG     103
SER_TEL3_BAUD       57600
SYS_HAS_NUM_DIST    2
CAL_MAG0_PRIO       75
CAL_MAG0_ROT        0
CAL_MAG1_PRIO       50
CAL_MAG1_ROT        -1
```

### Moving to real hardware
Only after all four steps check out. The propellers stay off until the end of the procedure.

1. Connect one device at a time: parameter, reboot, `<driver> status`, `listener <topic>`. Two devices at once and you will not know which one failed to start.
2. GPS: `gps status` shows the protocol and the port baud rate; `listener sensor_gps` and `listener sensor_gps -i 1` show both receivers, `listener vehicle_gps_position` the combined solution.
3. Compass: calibrate in QGC away from metal; afterwards the external compass has `CAL_MAGn_PRIO` = 75 and `CAL_MAGn_ROT` ≥ 0.
4. TFmini: `listener distance_sensor` at three heights above the floor; check the readings with a tape measure.
5. Telemetry: `mavlink status`; write down `tx rate max` (this is `MAV_0_RATE`, or `baud / 20` at 0) and `tx rate mult`. The multiplier will not match the number from step 2, and it should not: step 2 counted eleven streams, while Normal mode configures about fifty, and a stream whose topic nobody publishes yet counts as zero. What you check is something else: that the multiplier follows from the real list. `mavlink status streams` prints, for each stream, the configured rate, the current rate in parentheses, and the message size; only active streams have a size. Add up "configured rate × size" over the rows that have a size, except `HEARTBEAT` and `PING` (they are constant-rate: 21 and 2.6 B/s), skip the "unlimited" rows, and compute (`tx rate max` − 23.6) / sum. The result should match `tx rate mult` within 10 %, and the current `ATTITUDE` rate in parentheses should equal 15 × mult. If `tx rate mult` is clearly below your figure, what throttles the stream is no longer the budget but the link: look at the radio's `txbuf` and the `txerr` line. You cannot predict the multiplier in advance without this list: the set of active streams depends on which sensors and modules run on your vehicle, and it also dips briefly whenever a text message goes out. A ballpark for `MAV_0_RATE` = 1200 on a vehicle with one GPS, no gimbal and no ESC telemetry is 0.3–0.45 (an estimate from the source code, not a measurement).
6. DroneCAN: `uavcan status` lists the ESC nodes; test the motors with the sliders as in `px4-outputs-servos`.

Hardware criteria: every driver answers `status`; every topic updates; `dmesg` has no `Conflicting config`; the LED breathes green outdoors with a 3D fix.

Self-check: the lab is done when
- step 1: in the table each of the six UART devices has its own port, no port repeats, airspeed and the ESCs do not take a UART; exactly three errors are named in the fragment;
- step 2: all numbers match the reference: sums exactly, multipliers ±0.01, rates ±0.1 Hz;
- step 3: the state in each of the nine items matches the reference;
- step 4: both masks match exactly, exactly three errors are found, and no "trap" is written down as an error.

The hardware criteria from the previous paragraph are not part of this self-check; they are for the bench.

**Reference for the self-check.**

| Step | Correct result | Typical mistake and its cause |
|---|---|---|
| 1A | GPS 1: `GPS_1_CONFIG` = 201; GPS 2: `GPS_2_CONFIG` = 202; both `SER_GPS*_BAUD` = 0. SiK: `MAV_0_CONFIG` = 101, `SER_TEL1_BAUD` = 57600. Companion: `MAV_1_CONFIG` = 102, `MAV_1_MODE` = 2, `SER_TEL2_BAUD` = 921600. TFmini: `SENS_TFMINI_CFG` = 103. OSD: `MSP_OSD_CONFIG` = 401. Airspeed: `SENS_EN_MS4525DO` = 1, no port needed. ESCs: `UAVCAN_ENABLE` = 3, `UAVCAN_EC_FUNC1…4` = 101…104. TFmini and OSD can swap places | Airspeed or the ESCs put on a UART: I²C and CAN have no port parameter. OSD on 1000: Ethernet is available only to MAVLink and uXRCE-DDS |
| 1B | (1) `GPS_2_CONFIG` and `MAV_1_CONFIG` are both 102; (2) `SENS_TFMINI_CFG` and `MSP_OSD_CONFIG` are both 103; (3) `MAV_0_RATE` = 57600 is bytes per second, while a 57600 baud port carries 5760 | `SER_TEL3_BAUD` = 57600 with the TFmini written down as an error: the driver sets 115200 itself |
| 2.1 | 57600 / 10 = 5760 B/s; 1200 / 5760 = 20.8 % | 57600 B/s: baud taken for bytes |
| 2.2 | 600 + 600 + 200 + 320 + 270 + 128 + 55 + 44 + 69 + 33 + 25.5 = 2344.5 B/s | 1768.5: the 12 bytes per message forgotten |
| 2.3 | (1200 − 21) / 2344.5 = 0.50; `ATTITUDE` 7.5 Hz, `GLOBAL_POSITION_INT` 2.5 Hz | 0.51: `HEARTBEAT` not subtracted; constant-rate streams are not scaled |
| 2.4 | Limit 57600 / 20 = 2880; (2880 − 21) / 2344.5 = 1.22 → capped at 1.0; it fits, the rates are nominal for these eleven streams; the full Normal set on a vehicle needs about 3000 B/s or more, so even at 2880 B/s the multiplier can end up below 1 | `mult` = 1.22 and "the rates will go up": the multiplier never goes above 1 |
| 2.5 | 300 + 3750 + 1200 + 4000 + 7350 + 3000 + 2000 + 1080 = 22680 B/s; (1200 − 21) / 22680 = 0.052; `ATTITUDE` 5.2 Hz instead of 100 | 0.05 "at the lower bound": here 0.052 is just above it; the bound would kick in at a limit below 1155 B/s |
| 2.6 | 921600 / 20 = 46080 B/s; (46080 − 21) / 22680 = 2.03 → 1.0 | 92160: that is the port limit, not half of it |
| 3 | (1) checks failed: the reasons are in the `Preflight Fail: …` messages in QGC and in `dmesg`; `commander check` reruns the checks, read the result with a second call; (2) ready, but no position or home: wait for a fix, arming is possible only in manual modes; (3) boot error: look at `dmesg`: parameters, hardfault, IO; (4) battery Low: head back; (5) failsafe: find the cause in QGC, be ready to take over; (6) CPU or RAM overload: do not fly, `top`; (7) normal: the arming warning; (8) normal: "safe to approach"; (9) `EV_TSK_RC_LOSS` = 1, the find-me alarm: follow the sound | (2) taken for arming denied: denied is red. (5) and (6) mixed up: failsafe is solid, overload blinks |
| 4, masks | 21 = 16 + 4 + 1 → GLONASS, Galileo, GPS. GPS + Galileo + BeiDou = 1 + 4 + 8 = 13. OSD: 2 + 16 + 256 + 512 + 1024 + 4096 = 5906 | 21 → "GPS, SBAS, BeiDou": bits are numbered from zero, bit 4 is GLONASS |
| 4, errors | (1) `UAVCAN_ENABLE` = 2 with `UAVCAN_EC_FUNC` assigned: the ESC outputs work only with 3; (2) `UAVCAN_SUB_ASPD` = 0 with the airspeed sensor on CAN: the subscription is off by default, and `SYS_HAS_NUM_ASPD` = 1 will not let you arm; (3) `SYS_HAS_NUM_DIST` = 2 with one rangefinder: the preflight check will fail | Traps that are not errors: `SENS_EN_MS4525DO` = 0 (the sensor is on CAN), `SENS_GPS_MASK` = 7 with one GPS (blending simply does not engage), `SER_TEL3_BAUD` = 57600, `GPS_1_GNSS` = 0, compass priorities 75 and 50 |

## diagnostics
- **Symptom:** the device is connected, but its driver's parameter is not in the QGC list.
  - Possible cause: the driver is not built for this board (`default.px4board`).
  - What to do: check the "v6x" column in the tables or the board file; build firmware with the driver via `boardconfig`.
- **Symptom:** the port parameter is set, but the driver answers "not running" to `status`.
  - Possible cause: no reboot; the port is already taken by another driver.
  - What you see in the log: `dmesg` has a `Conflicting config for /dev/ttyS…` line.
  - What to do: find the second parameter with the same port number (most often `MAV_1_CONFIG` or `UXRCE_DDS_CFG` on TELEM2), separate them, reboot.
- **Symptom:** the GPS is not detected, `gps status` shows it cycling through baud rates.
  - Possible cause: TX and RX swapped; the receiver is not a u-blox with `GPS_1_PROTOCOL` = 1.
  - What to do: check the wiring; `GPS_1_PROTOCOL` = 0 (auto) or 6 for NMEA.
- **Symptom:** on 1.16 or older a multicopter's GPS "lags" in sharp maneuvers.
  - Possible cause: the airframe set `GPS_UBX_DYNMODEL` = 6 (airborne < 1 g).
  - What to do: `GPS_UBX_DYNMODEL` = 7, reboot; in 1.17 this is the default.
- **Symptom:** "Compass inconsistent", the vehicle circles in Position.
  - Possible cause: a wrong `CAL_MAGn_ROT` for the external compass; the internal compass is next to the power wiring.
  - What to do: recalibrate with `SENS_MAG_AUTOROT` = 1; set `CAL_MAGn_PRIO` = 0 for the internal one; for current interference, `CAL_MAG_COMP_TYP`.
- **Symptom:** the rangefinder shows up in `listener distance_sensor`, but height above ground is not used.
  - Possible cause: the sensor does not face down, while the driver assumes it does; rangefinder height estimation is not enabled.
  - What to do: check the `orientation` field in the topic; `EKF2_RNG_CTRL` as in the nav-terrain module.
- **Symptom:** the plane will not arm: "Preflight Fail: Airspeed invalid".
  - Possible cause: `SYS_HAS_NUM_ASPD` = 1, but the sensor driver is not enabled (`SENS_EN_*`) or `UAVCAN_SUB_ASPD` is off; the sensor is not calibrated.
  - What to do: enable the driver and reboot; if there is no sensor, `SYS_HAS_NUM_ASPD` = 0 and `FW_USE_AIRSPD` = 0.
- **Symptom:** telemetry in QGC updates in jerks, `ATTITUDE` at 5–7 Hz.
  - Possible cause: the stream set is larger than `MAV_0_RATE`; the radio reports a low `txbuf`.
  - What you see in the log: `mavlink status` shows `tx rate mult` clearly below 1.
  - What to do: raise `MAV_0_RATE` to `baud / 20` (value 0) or lower the rates with `mavlink stream`; raise the radio's air rate.
- **Symptom:** QGC reports a lost link with the vehicle, although the radio is connected.
  - Possible cause: a high-rate mode on the radio link (`MAV_n_MODE` = 2) or a `MAV_n_RATE` higher than the radio carries: its buffer overflows and packets are lost.
  - What you see in the log: `mavlink status` shows a low `txbuf` and `tx rate mult` near the lower bound.
  - What to do: mode 0 or 13 (Low Bandwidth) for a radio, Onboard only for a wired companion; `MAV_n_RATE` no higher than `baud / 20`.
- **Symptom:** in flight the LED was red, then turned green or blue again, and the battery tune went quiet.
  - Possible cause: the battery went past the Critical level to Emergency; with `COM_LOW_BAT_ACT` = 0 this level has neither a color nor a tune.
  - What you see in the log: `battery_status.warning` = 3; QGC shows a dangerously low battery message.
  - What to do: land immediately; on the ground set `COM_LOW_BAT_ACT` = 2, 3 or 5 so that the Emergency level triggers a landing.
  - Consequences: the ESCs cut out on low voltage and the vehicle falls.
- **Symptom:** a DroneCAN node does not appear in `uavcan status`.
  - Possible cause: `UAVCAN_ENABLE` = 0; a bitrate mismatch; no terminator; an ID conflict with value 1.
  - What to do: `UAVCAN_ENABLE` = 2, `UAVCAN_BITRATE` matching the node, 120 Ω terminators at the ends; for ESCs value 3.
- **Symptom:** the OSD is empty.
  - Possible cause: TX and RX swapped; `msp_osd` is not in the board's build; the video system expects something other than DisplayPort (1.15 firmware).
  - What to do: `msp_osd status`; check the PX4 version and the build; the VTX port runs at 115200.
- **Symptom:** the buzzer is silent at boot and on arming.
  - Possible cause: `CBRK_BUZZER` = 782097; the buzzer sits in the GPS module, and the module is not connected.
  - What to do: `CBRK_BUZZER` = 0, reboot; `tune_control play -t 1`.

## checklist
- Every UART device has its port and port number written down; no number repeats across the `*_CONFIG` / `*_CFG` parameters.
- After every change to a port parameter or `SENS_EN_*`: reboot, then `status` and `listener`.
- `dmesg` has no `Conflicting config`.
- `GPS_UBX_DYNMODEL` = 7 on a multicopter on any version; the second GPS shows up as `sensor_gps -i 1`.
- The external compass has a higher `CAL_MAGn_PRIO` than the internal one, and its rotation was set by calibration.
- The rangefinder faces where the driver thinks it does; `SYS_HAS_NUM_DIST` and `SYS_HAS_NUM_ASPD` equal the number of sensors you cannot fly without.
- `MAV_n_RATE` is computed in bytes per second and is no more than `baud / 10`; on the radio link `tx rate mult` agrees with the figure from `mavlink status streams`, and the `ATTITUDE` rate equals 15 × mult.
- The radio link runs Normal or Low Bandwidth; Onboard only on a wire.
- `UAVCAN_ENABLE` = 3 for CAN ESCs; each motor is assigned either to CAN or to PWM.
- You know the LED colors and tunes 2, 5, 7, 8 before the first flight.

## references
- PX4-Autopilot v1.17.0: Tools/serial/generate_config.py (port numbers, default baud rates) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/Tools/serial/generate_config.py | primary | A
- PX4-Autopilot v1.17.0: boards/px4/fmu-v6x/default.px4board (ports and drivers in the build) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/boards/px4/fmu-v6x/default.px4board | primary | A
- PX4-Autopilot v1.17.0: src/modules/mavlink/module.yaml (MAV_n_*) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/mavlink/module.yaml | primary | A
- PX4-Autopilot v1.17.0: src/modules/mavlink/mavlink_main.cpp (rate limit, multiplier, mode stream sets) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/mavlink/mavlink_main.cpp | primary | A
- PX4-Autopilot v1.17.0: src/drivers/gps/params.c | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/drivers/gps/params.c | primary | A
- PX4-Autopilot v1.17.0: src/modules/sensors/vehicle_gps_position/gps_blending.cpp | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/sensors/vehicle_gps_position/gps_blending.cpp | primary | A
- PX4-Autopilot v1.17.0: ROMFS/px4fmu_common/init.d/rc.sensors (SENS_EN_*) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/ROMFS/px4fmu_common/init.d/rc.sensors | primary | A
- PX4-Autopilot v1.17.0: src/modules/airspeed_selector/airspeed_selector_params.c | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/airspeed_selector/airspeed_selector_params.c | primary | A
- PX4-Autopilot v1.17.0: src/drivers/uavcan/uavcan_params.c | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/drivers/uavcan/uavcan_params.c | primary | A
- PX4-Autopilot v1.17.0: src/drivers/osd/msp_osd/module.yaml | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/drivers/osd/msp_osd/module.yaml | primary | A
- PX4-Autopilot v1.17.0: src/modules/commander/Commander.cpp (control_status_leds, updateTunes) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/commander/Commander.cpp | primary | A
- PX4-Autopilot v1.17.0: src/lib/tunes/tune_definition.desc | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/lib/tunes/tune_definition.desc | primary | A
- MAVLink: message_definitions/v1.0/common.xml (message lengths) | https://github.com/mavlink/mavlink/blob/master/message_definitions/v1.0/common.xml | primary | A
- PX4 Guide v1.17: Serial Port Configuration | https://docs.px4.io/v1.17/en/peripherals/serial_configuration | primary | A
- PX4 Guide v1.17: MAVLink Peripherals (GCS/OSD/Companion) | https://docs.px4.io/v1.17/en/peripherals/mavlink_peripherals | primary | A
- PX4 Guide v1.17: LED Meanings | https://docs.px4.io/v1.17/en/getting_started/led_meanings | primary | A
- PX4 Guide v1.17: Holybro Pixhawk 6X (UART table) | https://docs.px4.io/v1.17/en/flight_controller/pixhawk6x | primary | A

## notes
MAVLink message lengths are taken from `common.xml`, `standard.xml` and `minimal.xml` in the mavlink/mavlink repository; in the PX4 tree it is the `src/modules/mavlink/mavlink` submodule. The lengths were checked against mavlink/mavlink master as of November 2026; check them against the submodule of your PX4 version if you compute for another one. An actual MAVLink 2 frame can be shorter: trailing zero bytes of the payload are dropped, but the firmware uses the full length when computing the multiplier. The LED color table and the list of tune calls were taken from the 1.17.0 code, not from the guide pages; where they disagree, the tagged source wins.
