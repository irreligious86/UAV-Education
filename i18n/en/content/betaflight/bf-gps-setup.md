---
id: bf-gps-setup
title: "GPS in Betaflight: M8/M10 modules, configuration, accuracy and the home point"
level: L2
readingTime: 50 min
firmware: Betaflight 2025.12 (checked against 2025.12.5); the auto-configuration walkthrough and the lab follow the 4.5.x source (branch 4.5-maintenance, 7dcc851; version.h 4.5.6, the latest release is 4.5.5) · u-blox M8 (SPG 3.01), M10 (SPG 5.00/5.10)
status: published
added: 2026-11-14
tags:
  - GPS
  - GNSS
  - u-blox
  - M10
  - home point
  - Betaflight
related:
  - bf-failsafe
  - bf-setup-scratch
  - bf-ports
  - bf-cli
  - bf-modes-osd
  - bf-arming-safety
  - est-gnss
  - inav-gps
  - el-peripherals
  - el-emi
  - link-vtx
next: []
source: content/betaflight/bf-gps-setup.md
source_hash: e924417871b3
---

## summary
On Betaflight, GPS is needed for GPS Rescue, the home arrow and the speed in the OSD. What matters is not “there are satellites” but “home is recorded correctly and the heading is known”. This module covers choosing and connecting a u-blox M8 or M10, what Betaflight writes to the receiver with `gps_auto_config = ON` (from the code of `io/gps.c`, which disagrees with the documentation in four places), the `gps_*` and `mag_*` variables, the GPS arming flag, recording home, heading without a compass, the OSD, `gpspassthrough` with u-center, cold, warm and hot start, DOP and CEP. A Python lab: a UBX parser following the 4.5 rules is checked on a real M8030 recording (DOP matched the receiver to within 0.02), then six synthetic logs show the effect of constellations and VTX noise, plus the UART load. On hardware — satellites with the VTX off and on, timing a cold start and checking home. GPS Rescue itself is in `bf-failsafe` and `bf-setup-scratch`.

## theory
### What GPS gives Betaflight 2025.12
Betaflight 2025.12 does not fly waypoints (that is INAV and ArduPilot, `inav-gps`). 2026.6 brought the AUTOPILOT (permanentId 56) and WP CAPTURE (57) modes and the `waypoint` CLI command, but all of it is under `ENABLE_FLIGHT_PLAN`, and in tag 2026.6.2 `USE_FLIGHT_PLAN` is defined only in the SITL target (`target/common_post.h`, `platform/SIMULATOR/target/SITL/target.h`): on flight controllers it is an experimental feature, not for flying. From 2025.12 it can hold position (the POS HOLD mode, id 11, the `pos_hold_*` and `ap_position_*` variables; a build option) and altitude (ALTHOLD); 4.5 does not have these modes. The coordinates go to GPS Rescue, to home, the distance and the OSD arrow, to the speed and coordinates in the OSD and telemetry, to the altitude (`flight/position.c` blends GPS with the baro with a weight of `gpsTrust = min(1/PDOP, 0.9)`) and to the lap timer `gps_lap_timer_*`. Without a compass GPS also provides the heading; POS HOLD without a compass is allowed by `pos_hold_without_mag` (OFF by default). In 2026.6 `pos_hold_without_mag` was removed: GPS-based POS HOLD and GPS Rescue require a trustworthy heading (POS HOLD on optical flow alone does not, `positionEstimatorIsHeadingRequired()` in `flight/pos_hold_multirotor.c`) — from the compass only if `trust_mag = ON` (OFF by default, `flight/imu.c`, `sensors/compass.c`), otherwise from GPS after gaining speed; the position source is selected by `poshold_position_source` (AUTO, GPS_ONLY, OPTICALFLOW_ONLY). The line `set pos_hold_without_mag` from an old `diff` gives `INVALID NAME` in 2026.6.

### The module: M8 or M10
| Parameter | u-blox M8 (NEO-M8N, FW 3.01) | u-blox M10 (MAX-M10S, ROM SPG 5.10) |
|---|---|---|
| Default constellations | GPS + GLONASS (+ SBAS, QZSS), Galileo disabled | GPS + Galileo + BeiDou B1I (+ QZSS, SBAS) |
| Cold start | 26 s (GPS+GLO), 29 s GPS only | 27 s by default, 23–28 s in other sets |
| Hot start | 1 s | 1 s |
| CEP accuracy (24 h, static) | 2.5 m (2.0 m with SBAS) | 1.5 m |
| Max navigation update rate | NEO-M8N: 5 Hz with two systems, 10 Hz with one | 3 Hz by default (GPS+GAL+BDS), 10 Hz for GPS+GAL, 6 Hz for GPS+GAL+GLO; 18 Hz with a single system |
| Supply of the module itself | 2.7–3.6 V | 1.76–3.6 V, 9.5 mA at 3 V (GPS+GAL+BDS) |
| Default UART | 9600 8N1, NMEA | 9600 8N1, NMEA |

The figures are from the u-blox datasheets. The M10 is more accurate, more economical and sees more satellites, but a factory MAX-M10S with GPS+GAL+BDS does not deliver the 10 Hz that Betaflight configures it for: the ceiling is 3 Hz. The M10 defaults depend on the firmware: for ROM 5.00 it is GPS+GAL, for the SAM-M10Q — GPS+GAL+GLO+BDS B1C. Look up the version and the constellation set in u-center (MON-VER, MON-GNSS).

An FPV module is a receiver, an LDO, a patch antenna, sometimes a capacitor or a battery on V_BCKP and a compass on I²C. “5 V” on the silkscreen is the LDO input; the chip itself runs on 3.3 or 1.8 V; without an LDO you need the 3.3 V pad — the board marking decides. Power on V_BCKP keeps the ephemeris and the clock — a restart takes seconds. The inrush current of the SAM-M10Q is up to 100 mA.

### Wiring and installation
- **UART crossed over:** module TX → flight controller RX, RX → TX, common GND. Both wires are needed: Betaflight sends configuration to the module. A hardware UART only: on SoftSerial the baud rate is capped at 19200 (`serial.c`), which is not enough (step 3). The compass (SDA/SCL) goes to the I²C pads.
- **The antenna** faces the sky, with nothing conductive above it. The SAM-M10Q gives its optimal pattern on a 50 × 50 mm ground plane; the board of an FPV module is 20–25 mm, so a large module on a mast is usually better than a small one inside the frame.
- **Interference:** L1 signals at the Earth's surface are about −130 dBm at 1561–1602 MHz (BeiDou B1I 1561.098, GPS and Galileo 1575.42, GLONASS ≈ 1602). Keep the module away from the VTX and its antenna, a digital air unit with its camera, the ESCs and the power wires; 1.2–1.3 GHz video is the closest of all to the L band. How much your VTX interferes is shown by the bench test in the practice.
- **Tilt:** the documentation advises tilting the aircraft 45° in all directions — the satellites must not be lost, since the aircraft flies home tilted.

### How Betaflight configures the module (from the code)
The sequence below was read from `io/gps.c` of 4.5.x (branch `4.5-maintenance`, commit `7dcc851`: `version.h` says 4.5.6, but there is no such release; the latest release is 4.5.5, and the `src/` code matches it except for the version number in `version.h`). In 2025.12 the file was reformatted; only what is named explicitly was checked against it: the auto-baud search rates (230400 was added), the VIRTUAL provider, the `pg/gps.c` defaults, the `GPS_MIN_SAT_COUNT` = 4 threshold, the model switch through `gps_ublox_acquire_model` / `gps_ublox_flight_model`, and the fact that `gps_auto_baud` is still read only in `status`.

{{diagram:bf-gps-boot-flow|After power-up Betaflight finds the module's baud rate by itself, switches it to the rate from `serial`, writes the settings to RAM and switches the dynamic model on the first 3D fix. Home is recorded on arming (and on a stick gyro calibration) and only with at least `gps_rescue_min_sats` satellites.}}

With `gps_provider = UBLOX` the `gpsConfigureUblox()` state machine does the following.
1. **Baud rate search.** Three MON-VER requests 330 ms apart. No answer — the next rate: from the rate in `serial` upward to 115200, then from 9600 upward in a loop. The answer (hwVersion `00080000` = M8, `000A0000` = M10) selects the branch: CFG-VALSET for M9 and newer, the old CFG messages for M8 and older.
2. **Baud rate change.** The module is sent `$PUBX,41,…` with the GPS baud rate from the `serial` command, then a 990 ms pause.
3. **Configuration** (only with `gps_auto_config = ON`): a 1 s pause, then 16 (M10) or 22 (M8) steps no more often than once per 110 ms: a 1 Hz rate, NMEA disabled, the `gps_ublox_acquire_model` model, SBAS, FULL power, NAV-PVT every cycle, NAV-SAT every 5th, `gps_update_rate_hz`, CFG-GNSS (Galileo). All of it goes to the module's RAM (`UBX_VAL_LAYER_RAM`). An estimate from the constants: a factory module at 9600 with `serial … 57600` is ready in 2 + 0.3 + 1 + 1 + 1.8 ≈ 6 s.
4. **Receiving.** On the first 3D fix (not on arming!) the module gets `gps_ublox_flight_model`. If there is no NAV data for 2.5 s, the state machine goes back to the baud rate search.

Where the documentation disagrees with the code (verified on 4.5-maintenance):
- The GPS page says: Stationary before arming, Airborne <4g after. In the code the switch happens on the first 3D fix (`gpsUpdate()`); arming has nothing to do with it.
- The same page says that `gps_sbas_mode` defaults to AUTO. In `pg/gps.c` (4.5 and 2025.12) it is `SBAS_NONE`.
- According to the documentation GPS Rescue is aborted when there are fewer satellites than half of `gps_rescue_min_sats`. In the code the threshold is fixed: `GPS_MIN_SAT_COUNT` = 4. That is 10 s in flight (`RESCUE_LOWSATS`), while for “Rescue available” 2 s below 4 is enough. With min_sats 8 the result is the same, with 12 it no longer is.
- `gps_auto_baud` (in both 4.5 and 2025.12) affects nothing except the `status` text (“set to AUTO”): for UBLOX the baud rate search always runs, for NMEA it never does.

More consequences of the code. Galileo is switched only with the old UBX-CFG-GNSS (poll → modify → write), and the step is skipped with SBAS enabled and Galileo disabled: `gps_ublox_use_galileo = OFF` with `gps_sbas_mode = AUTO` leaves Galileo as it is in the module (enabled on an M10). Of the CFG messages, the M10 interface description knows only CFG-CFG, CFG-RST and VALSET/VALGET/VALDEL, so check the result by the list of E satellites on the GPS tab. `gps_ublox_mode` from 4.4 was removed: an old `diff` with it gives `INVALID NAME`.

### Reference: variables and commands (2025.12)
| Variable / command | Default | Range | Meaning |
|---|---|---|---|
| `feature GPS` | off | — | without it the GPS task does not start, `status` → `NOT ENABLED` |
| `serial <id> 2 … <gps_baud> …` | 57600 | 9600–115200 (SoftSerial ≤ 19200) | the GPS function (value 2 = bit 1) and the baud rate; in 2025.12 the port is written by name (`serial UART2 2 …`), and the auto-baud search knows 230400 (in 4.5 — up to 115200, the port by number) |
| `gps_provider` | UBLOX | NMEA, UBLOX, MSP, VIRTUAL | NMEA — no configuration and no baud rate search; VIRTUAL — GPS in SITL (from 2025.12, 4.5 does not have it) |
| `gps_auto_config` | ON | OFF, ON | the CONFIGURE steps; OFF — the module must be configured in u-center |
| `gps_auto_baud` | OFF | OFF, ON | only the text in `status` |
| `gps_update_rate_hz` | 10 | 1–20 | the navigation update rate; no higher than the module's ceiling |
| `gps_ublox_use_galileo` | OFF | OFF, ON | Galileo through CFG-GNSS (see above) |
| `gps_sbas_mode` | NONE | AUTO, EGNOS, WAAS, MSAS, GAGAN, NONE | SBAS and the PRN mask (EGNOS: 123, 126, 136) |
| `gps_sbas_integrity` | OFF | OFF, ON | use the SBAS integrity flags |
| `gps_ublox_acquire_model` | STATIONARY | PORTABLE, STATIONARY, PEDESTRIAN, AUTOMOTIVE, AT_SEA, AIRBORNE_1G/2G/4G | the model before the first 3D fix |
| `gps_ublox_flight_model` | AIRBORNE_4G | the same | the model after the first 3D fix |
| `gps_ublox_utc_standard` | AUTO | AUTO, USNO, EU, SU, NTSC | the UTC source |
| `gps_set_home_point_once` | OFF | OFF, ON | ON: home is written on the first arm (or earlier — by a stick gyro calibration) and kept until reboot |
| `gps_use_3d_speed` | OFF | OFF, ON | the OSD speed and the distance traveled include the vertical component |
| `gps_nmea_custom_commands` | empty | string | commands to the module with `gps_provider = NMEA` |
| `gps_rescue_min_sats` | 8 | 5–50 | satellites for clearing the GPS flag and for recording home |
| `gps_rescue_allow_arming_without_fix` | OFF | OFF, ON | arming without a fix, and then without home: Rescue is unavailable |
| `mag_hardware` | AUTO | AUTO, NONE, HMC5883, AK8975, AK8963, QMC5883, LIS2MDL, LIS3MDL, MPU925X_AK8963, IST8310 | only in a build with the magnetometer |
| `align_mag`, `mag_align_roll/pitch/yaw` | DEFAULT, 0 | −3600…3600 (0.1°) | the compass orientation |
| `mag_declination` | 0 | −300…300 (0.1°) | magnetic declination, west is negative (in 4.5 the range is 0–3599) |
| `gps_rescue_use_mag` | ON | OFF, ON | use the compass in Rescue (if there is one); removed in 2026.6 — the compass for heading is enabled by the common `trust_mag` (OFF) |
| `osd_gps_sats_show_pdop` | OFF | OFF, ON | PDOP next to the satellite count |
| `gpspassthrough` | — | — | a USB ↔ GPS UART bridge until reboot |
| `status` | — | — | the line `GPS: connected, UART2 57600 (set to 57600), configured, version =  M10` |
| `debug_mode = GPS_CONNECTION` / `GPS_DOP` | — | — | the NAV interval, the configuration step; satellites and DOP in Blackbox |

### Satellites, the arming flag and the home point
- **3D fix** = NAV-PVT `fixType == 3` and the `gnssFixOK` bit; the satellites are `numSV` from the same message.
- **The GPS arming flag** exists only if Rescue is configured (`failsafe_procedure = GPS-RESCUE` or the GPS RESCUE mode). It is cleared with a 3D fix and `numSat ≥ gps_rescue_min_sats`, after the first arm, or with `gps_rescue_allow_arming_without_fix = ON`. Rescue is configured but `feature GPS` is off — the flag stays forever.
- **Signals:** when the condition is met before arming — a single READY_BEEP. On arming — “short-long” twice with a fix and `numSat ≥ gps_rescue_min_sats`, otherwise three long beeps of 300 ms.
- **Home** is written by `GPS_reset_home_position()` on arming (and on a stick gyro calibration: throttle down + yaw left + pitch down), only with a fix and `numSat ≥ gps_rescue_min_sats`. With `gps_set_home_point_once = OFF` home is erased on every disarm: a disarm in the field moves home. With ON home is kept until reboot — make the first arm where you want to return to, and do not calibrate the gyro with the sticks anywhere else.
- **In flight** the Rescue threshold is 4 satellites, on arming — 8.
- On arming NAV-SAT is turned off until reboot: the satellite list on the GPS tab “freezes”, and that is normal.

### Heading without a compass, and the compass itself
Without a magnetometer yaw is integrated by the gyro from power-up. `imu.c` corrects it from the GPS course over ground with a fix, more than 4 satellites and after the speed has first exceeded 1 m/s. The weight: 0 at 0 m/s, ∝ v² up to 1 m/s, linear up to ×10 at 10 m/s; it is multiplied by the forward pitch tilt (0 when level or tilted back, ×1 at 45°); a roll of more than 12° and the yaw stick suppress it. The home arrow is drawn as `direction to home − yaw`, so until the first straight pass it lies. The documentation: 30–50 m straight at more than 1–2 m/s, then trust the arrow.

The compass is a build option (selected separately in Cloud Build; so in both 4.5 and 2025.12). On a 5″ it is usually not fitted: the field from tens of amps in the power wires and ESCs gets in the way more than the compass helps; the documentation advises against enabling it without a log of a “square” with clean 90° turns. If there is one: `align_mag`, calibration from Betaflight App (15 s to start rotating, then 30 s in all axes), `mag_declination` in 0.1°, a comparison with a phone (true north) within 10°. A healthy compass turns off the GPS course correction; Rescue itself turns the compass off if it does not get closer to home for 30 s.

### OSD elements
| Element | Variable | What it shows (verified on 4.5-maintenance) |
|---|---|---|
| GPS sats | `osd_gps_sats_pos` | `NC` until GPS is receiving data; “critical” severity without a fix or with < 4, “caution” with < `gps_rescue_min_sats` and Rescue configured |
| GPS speed | `osd_gps_speed_pos` | only with a fix; `gps_use_3d_speed` adds the vertical component |
| Home direction | `osd_home_dir_pos` | `-` until there is a fix and home; the “over home” symbol at a distance of 0 |
| Home distance | `osd_home_dist_pos` | meters from the recorded home |
| GPS latitude / longitude | `osd_gps_lat_pos`, `osd_gps_lon_pos` | latitude and longitude for a search after a crash |
| Altitude | `osd_altitude_pos` | a blend of baro and GPS (`position.c`) |
| Warnings | `osd_warnings_pos` | `RESCUE N/A` (Rescue is configured but unavailable), `RESCUE OFF` |

The minimum: satellites, the home arrow and distance, coordinates, warnings. The coordinates from the last frame of the goggles recording are the best way to find a crashed aircraft.

CRSF/ELRS telemetry (question No. 47): the GPS frame is sent with `feature GPS` unless all four of `telemetry_disabled_lat_long`, `_ground_speed`, `_heading`, `_altitude` are ON; the sensors in EdgeTX come through “Discover new”. The mode on the radio is `WAIT` while the aircraft is not armed and there is no fix or home. There is no home before the first arm, and with `gps_set_home_point_once = OFF` it is erased on every disarm, so `WAIT` on the ground is normal.

### Accuracy and start time
**Cold start** (no almanac, ephemeris or time): 26–29 s per the datasheets under an open sky. **Warm** — the time and almanac are there but the ephemeris is stale (u-blox: valid for up to 4 h); it has to be downloaded anyway (GPS sends it in subframes 1–3, 6 s each), so a warm start is closer to a cold one, and the datasheets give no figures. **Hot** — fresh ephemeris in BBR with V_BCKP alive: 1 s; the Betaflight auto-configuration takes longer (about 6 s).

DOP is the geometry multiplier: position error ≈ DOP × range error (`est-gnss`). Betaflight works with **PDOP** (verified on 4.5-maintenance): NAV-DOP is disabled on M7+, the `hdop` field is not updated, and the app and MSP receive PDOP. A PDOP of about 1.0 and lower is good (the Rescue documentation), above 2.5 — weak geometry. A good module at rest: 1–2 m CEP, speed no more than 10–20 cm/s; consistently above 25 cm/s — the module or the site is unsuitable (the Rescue documentation).

### `gpspassthrough` and u-center
`gpspassthrough` bridges the CLI's USB port to the GPS UART at the current port rate (after auto-configuration — 57600) in an endless loop: the only way out is a reboot. `feature GPS` and a port with the GPS function are required; if the board does not power the GPS pad from USB (the documentation names the SPRacingF3), connect a battery, without propellers. The procedure: `gpspassthrough` → close Betaflight App → u-center on the same COM port. What to look at: MON-VER (ROM SPG 5.00 or 5.10), MON-GNSS, C/N0 in NAV-SAT; record a `.ubx` for the lab. Configure what Betaflight does not touch: the M10 constellations through CFG-SIGNAL (GPS+GAL for the sake of 10 Hz), the power mode on ROM 5.00. Save to BBR/flash; the MAX-M10S has no flash, and BBR lives as long as V_BCKP is present. Betaflight will rewrite its own items (baud rate, model, SBAS, rate, messages) to RAM on every boot.

### How 4.5 differs and what comes next
The `gps_*` variables are the same in 4.5 and 2025.12 (by `cli/settings.c` only the range of `mag_declination` differs). In 4.5 the baud rate search does not know 230400, there is no VIRTUAL provider (the 4.5 SITL has no GPS at all), and the landing altitude and throttle of GPS Rescue are set by `gps_rescue_landing_alt` and `gps_rescue_throttle_*` — in 2025.12 they were replaced by the common `ap_landing_altitude_m`, `ap_hover_throttle`, `ap_throttle_min/max`, `ap_altitude_*`. The default of `gps_rescue_disarm_threshold` in 2025.12 is 30 (in 4.5 — 20). In 2026.6 GPS Rescue was rewritten on top of the common position estimator: `gps_rescue_velocity_p/i/d`, `gps_rescue_max_angle`, `gps_rescue_roll_mix`, `gps_rescue_pitch_cutoff`, `gps_rescue_imu_yaw_gain`, `gps_rescue_use_mag` and `gps_rescue_disarm_threshold` were removed, `gps_rescue_yaw_p` stayed; `trust_mag` (OFF) was added; `gps_rescue_min_start_dist` and `gps_rescue_descent_dist` have a minimum of 5 m instead of 10; `ap_altitude_p/i/d/f` default to 30 (15 in 2025.12), `ap_throttle_max` — to 1900 (was 1700) (per `cli/settings.c` and `pg/` of tag 2026.6.2; not part of the course's target version). `master` (2026.12): `gps_uart`, `gps_baud`, `gps_ublox_enable_ana` (AssistNow Autonomous, commented out in 4.5).

### Place in the system

- **Receives:** a hardware UART with the GPS function and the baud rate from `serial` (`bf-ports`); the GPS and magnetometer options in the build (`bf-custom`); interference from the VTX and the power wires, which lowers the satellite count (`el-emi`); the satellite geometry — DOP (`est-gnss`).
- **Provides:** home, distance and heading — to GPS Rescue (`bf-failsafe`); the `GPS` arming flag (`bf-arming-safety`); satellites, the home arrow and coordinates — to the OSD (`bf-modes-osd`) and to CRSF telemetry (`link-elrs`).
- **If you get it wrong here:** a disarm and re-arm in the field with `gps_set_home_point_once = OFF` → home has moved, and Rescue will bring the aircraft back to somewhere other than where it took off (`bf-failsafe`). GPS is put on SoftSerial → the baud rate is limited to 19200, which is not enough; it looks like a bad module, while the cause is in the port allocation (`bf-ports`).

## practice
### Step 1. A UBX parser following the 4.5 rules and a check on a real recording
The script and the output of the whole lab were captured from `io/gps.c` of 4.5-maintenance; the frame parsing in 2025.12 was not re-checked line by line (phase 2 will rerun the lab). The Betaflight 4.5 SITL has no GPS (2025.12 has a virtual one), so the lab is Python that reads UBX the same way as `UBLOX_parse_gps()`. The file `gps_lab.py` is the four blocks of this module one after another. Block 1: frames with the checksum, the NAV-PVT and NAV-SAT fields, DOP from the geometry.

```python
"""bf-gps-setup lab: read a u-blox UBX capture the way Betaflight 4.5 reads it.

Block 1 - UBX framing and the fields io/gps.c (4.5) takes from NAV-PVT / NAV-SAT, DOP from geometry.
Block 2 - SYNTHETIC capture generator (no real log in the course repo): fixed sky, 10 Hz NAV-PVT +
          NAV-SAT every 5th epoch, exactly the message set Betaflight 4.5 auto-config enables.
          Every number of the sky / signal / error model is an assumption and is printed in the header.
Block 3 - analysis: TTFF, time to "8 sats + 3D fix" (arming flag GPS clears), sats, PDOP, HDOP,
          position scatter (CEP50 / R95), still-speed, UART load, for six scenarios; check_real() runs
          the same parser on a real capture and compares our DOP with the receiver's NAV-DOP.
Run:  python3 gps_lab.py [outdir] [real_capture.ubx]
"""
import math
import random
import struct
import sys
from pathlib import Path

import numpy as np

# ---------------- Block 1: UBX as Betaflight 4.5 parses it ----------------
GNSS = {0: "G", 1: "S", 2: "E", 3: "C", 5: "J", 6: "R"}   # u-blox gnssId: GPS, SBAS, GAL, BDS, QZSS, GLO


def ubx(cls, mid, payload):
    body = bytes([cls, mid]) + struct.pack("<H", len(payload)) + payload
    a = b = 0
    for x in body:                                # 8-bit Fletcher over class..payload
        a = (a + x) & 0xFF
        b = (b + a) & 0xFF
    return b"\xb5\x62" + body + bytes([a, b])


def frames(data, stats):
    i = 0
    while True:
        i = data.find(b"\xb5\x62", i)
        if i < 0 or i + 8 > len(data):
            return
        n = struct.unpack_from("<H", data, i + 4)[0]
        end = i + 8 + n
        if end > len(data):
            return
        a = b = 0
        for x in data[i + 2:i + 6 + n]:
            a = (a + x) & 0xFF
            b = (b + a) & 0xFF
        if data[end - 2] == a and data[end - 1] == b:
            yield data[i + 2], data[i + 3], data[i + 6:i + 6 + n]
            i = end
        else:
            stats["bad"] += 1
            i += 2


def nav_pvt(p):
    """UBLOX_parse_gps(), case NAV-PVT: fix = gnssFixOK && fixType == 3D; numSV; pDOP; gSpeed/10."""
    fix_type, flags, num_sv = p[20], p[21], p[23]
    lon, lat, _h, hmsl, hacc = struct.unpack_from("<iiiiI", p, 24)
    gspeed = struct.unpack_from("<i", p, 60)[0]
    return dict(t=struct.unpack_from("<I", p, 0)[0] / 1000, fix=bool(flags & 1) and fix_type == 3,
                sats=num_sv, lat=lat * 1e-7, lon=lon * 1e-7, alt_cm=int(hmsl / 10),
                hacc=hacc / 1000, speed_cms=int(gspeed / 10), pdop=struct.unpack_from("<H", p, 76)[0] / 100)


def nav_sat(p):
    t, _ver, n = struct.unpack_from("<IBB", p, 0)
    svs = [struct.unpack_from("<BBBbhhI", p, 8 + 12 * k) for k in range(n)]
    return t / 1000, [(GNSS[g], sv, cno, el, az, bool(fl & 8)) for g, sv, cno, el, az, _pr, fl in svs]


def dop(used, clock_per_system=False):
    """used: [(system, el_deg, az_deg)]. Unknowns E, N, U + receiver clock(s). One common clock reproduces
    the receiver's NAV-DOP (checked on the real capture); a clock per system is the stricter LS model."""
    systems = sorted({s for s, _, _ in used}) if clock_per_system else ["*"]
    H = []
    for s, el, az in used:
        e, a = math.radians(el), math.radians(az)
        H.append([-math.cos(e) * math.sin(a), -math.cos(e) * math.cos(a), -math.sin(e)]
                 + [1.0 if k in (s, "*") else 0.0 for k in systems])
    H = np.array(H)
    Q = np.linalg.inv(H.T @ H)
    return math.sqrt(Q[0, 0] + Q[1, 1]), math.sqrt(Q[0, 0] + Q[1, 1] + Q[2, 2]), H, Q
```

A check on a real receiver — an open u-blox M8030 recording from the pyubx2 tests: `curl -O https://raw.githubusercontent.com/semuconsulting/pyubx2/master/tests/pygpsdata-MIXED.log`. `check_real()` (block 4) prints what Betaflight would see and compares the DOP from the NAV-SAT angles with the receiver's NAV-DOP:

```text
real capture pygpsdata-MIXED.log: HW UBX-M8030 00080000, NAV-PVT 39, NAV-SAT 28, NAV-DOP 17, bad checksums 0
  Betaflight view: 3D fix 39/39, numSV 13-15, pDOP 1.35-1.75, hAcc 6.3-7.0 m, scatter over 38 s: max 0.88 m
  epoch     used (sys)          HDOP rx / 1 clk / clk per sys   PDOP rx / 1 clk / clk per sys
     473615  15 {'G': 8, 'R': 7}    0.78 /  0.78 /  0.78              1.35 /  1.35 /  1.36
     473621  13 {'G': 7, 'R': 6}    1.07 /  1.05 /  1.29              1.75 /  1.75 /  1.92
     473627  14 {'G': 7, 'R': 7}    0.94 /  0.94 /  1.00              1.66 /  1.67 /  1.74
     473645  13 {'G': 6, 'R': 7}    0.96 /  0.97 /  1.02              1.68 /  1.68 /  1.74
     473648  14 {'G': 7, 'R': 7}    0.94 /  0.94 /  1.00              1.66 /  1.66 /  1.73
```

5 of the 14 epochs are shown; the rest are the same. The “single clock” model reproduces the receiver's DOP to within 0.02; “a clock per system” with 13–14 satellites gives 5–23 % more — so the reported DOP of the M8 in this recording is computed with a single clock. The receiver estimates hAcc at 6–7 m, while over 38 s the position moved by 0.88 m: a short recording does not measure accuracy, the error changes over minutes. That is why on hardware we record 10 minutes.

### Step 2. Synthetic logs: constellations, VTX noise, start
Block 2 writes **synthetic** `.ubx` files with the same message set as after the 4.5 auto-configuration (NAV-PVT at 10 Hz, NAV-SAT every 5th cycle). The sky, C/N0 and the errors are assumptions, and they are printed in the header of the output; the ephemeris decoding (18–30 s after acquisition) is fitted to the 26–29 s cold start from the datasheets. The position error is a real least-squares solution from the geometry with a correlated range error for every satellite. A fix: 3 + the number of satellite systems, and PDOP ≤ 25 (the mask that Betaflight writes to the M8).

```python
# ---------------- Block 2: SYNTHETIC capture (assumptions, not measurements) ----------------
VISIBLE = {"G": 10, "E": 8, "C": 10, "R": 7}     # sats above 5 deg, mid-latitude open sky (assumed)
CNO_TRACK, CNO_DECODE = 20, 30                   # dB-Hz: keep tracking / decode ephemeris from cold (assumed)
SIGMA_SLOW, TAU_S, SIGMA_WHITE = 1.5, 60.0, 0.3  # m per sat: multipath+atmosphere (Gauss-Markov) + noise
LAT0, LON0, ALT0 = 50.45, 30.52, 180.0           # arbitrary bench location


def sky(seed=7):
    rnd = random.Random(seed)
    out = []
    for s, n in VISIBLE.items():
        for k in range(n):
            el = math.degrees(math.asin(rnd.uniform(math.sin(math.radians(5)), 1.0)))
            out.append(dict(sys=s, sv=k + 1, el=el, az=rnd.uniform(0, 360),
                            cno0=28 + 18 * math.sin(math.radians(el)) + rnd.gauss(0, 1.5)))
    return out


def make_capture(path, systems, start="cold", noise_db=0.0, seed=1, duration=600, rate=10):
    rnd = random.Random(seed)
    sats = [dict(s) for s in sky() if s["sys"] in systems]
    for s in sats:
        s["cno"] = max(0.0, s["cno0"] - noise_db)
        acq = rnd.uniform(2, 10) if start == "cold" else rnd.uniform(0.3, 1.0)
        s["t_acq"] = acq if s["cno"] >= CNO_TRACK else math.inf
        if start == "hot":
            s["t_eph"] = s["t_acq"]                      # ephemeris kept in BBR (V_BCKP), < 4 h old
        else:
            s["t_eph"] = acq + rnd.uniform(18, 30) if s["cno"] >= CNO_DECODE else math.inf
        s["err"] = rnd.gauss(0, SIGMA_SLOW)
    phi = math.exp(-1 / (rate * TAU_S))
    m_per_deg = 111_320.0
    out = bytearray()
    for k in range(1, duration * rate + 1):
        t = k / rate
        for s in sats:
            s["err"] = phi * s["err"] + math.sqrt(1 - phi * phi) * rnd.gauss(0, SIGMA_SLOW)
        used = [s for s in sats if t >= s["t_eph"] and s["cno"] >= CNO_TRACK]
        fix, pdop_v, hdop_v, dE = False, 99.99, 99.99, np.zeros(3)
        if len(used) >= 3 + len({s["sys"] for s in used}):
            geo = [(s["sys"], s["el"], s["az"]) for s in used]
            hdop_v, pdop_v, _, _ = dop(geo)              # what the receiver reports
            _, _, H, Q = dop(geo, clock_per_system=True)  # solution with an inter-system clock bias
            eps = np.array([s["err"] + rnd.gauss(0, SIGMA_WHITE) for s in used])
            dE = (Q @ H.T @ eps)[:3]                     # least-squares position error, metres E/N/U
            fix = pdop_v <= 25.0                          # pDOP mask Betaflight writes to M8 (NAV5 pDOP = 250)
        lat = LAT0 + dE[1] / m_per_deg
        lon = LON0 + dE[0] / (m_per_deg * math.cos(math.radians(LAT0)))
        vel = [rnd.gauss(0, 0.05 * hdop_v) if fix else 0.0 for _ in range(2)]   # 0.05 m/s per axis x HDOP
        pvt = bytearray(92)
        struct.pack_into("<I", pvt, 0, int(t * 1000))
        pvt[20], pvt[21], pvt[23] = (3 if fix else 0), (1 if fix else 0), (len(used) if fix else 0)
        struct.pack_into("<iiiiII", pvt, 24, round(lon * 1e7), round(lat * 1e7), round((ALT0 + dE[2]) * 1000),
                         round((ALT0 + dE[2]) * 1000), round(hdop_v * SIGMA_SLOW * 1000), 9999)
        struct.pack_into("<i", pvt, 60, round(math.hypot(*vel) * 1000))
        struct.pack_into("<H", pvt, 76, min(9999, round(pdop_v * 100)))
        out += ubx(0x01, 0x07, bytes(pvt))
        if k % 5 == 0:                                   # setSatInfoMessageRate(5): NAV-SAT every 5th epoch
            inv = {v: g for g, v in GNSS.items()}
            body = struct.pack("<IBBH", int(t * 1000), 1, len(sats), 0)
            for s in sats:
                cno = round(s["cno"]) if t >= s["t_acq"] else 0
                flags = 4 | (8 if s in used and fix else 0)
                body += struct.pack("<BBBbhhI", inv[s["sys"]], s["sv"], cno, round(s["el"]), round(s["az"]), 0, flags)
            out += ubx(0x01, 0x35, body)
    Path(path).write_bytes(bytes(out))
    return len(sats)
```

Block 3 is the analysis: TTFF (the first 3D fix), “8sat” (the GPS arming flag would be cleared with `gps_rescue_min_sats = 8`), the medians of satellites and DOP, CEP50/R95 and v95 after the first minute of the fix, the UART load.

```python
# ---------------- Block 3: analysis ----------------
def analyze(path, min_sats=8):
    stats = {"bad": 0}
    pvts, sat_epochs = [], []
    for cls, mid, p in frames(Path(path).read_bytes(), stats):
        if (cls, mid) == (0x01, 0x07):
            pvts.append(nav_pvt(p))
        elif (cls, mid) == (0x01, 0x35):
            sat_epochs.append(nav_sat(p))
    t_fix = next((e["t"] for e in pvts if e["fix"]), None)
    t_arm = next((e["t"] for e in pvts if e["fix"] and e["sats"] >= min_sats), None)
    if t_fix is None:
        return dict(n=len(pvts), bad=stats["bad"], ttff=None, t_arm=None)
    late = [e for e in pvts if e["fix"] and e["t"] >= t_fix + 60]     # skip the first minute after fix
    lat0 = np.mean([e["lat"] for e in late])
    lon0 = np.mean([e["lon"] for e in late])
    east = np.array([(e["lon"] - lon0) * 111_320 * math.cos(math.radians(lat0)) for e in late])
    north = np.array([(e["lat"] - lat0) * 111_320 for e in late])
    r = np.hypot(east, north)
    hd = [dop([(s, el, az) for s, _sv, _c, el, az, u in svs if u])[0]
          for t, svs in sat_epochs if t >= t_fix + 60]
    last = sat_epochs[-1][1]
    return dict(n=len(pvts), bad=stats["bad"], ttff=t_fix, t_arm=t_arm,
                sats=float(np.median([e["sats"] for e in late])), pdop=float(np.median([e["pdop"] for e in late])),
                hdop=float(np.median(hd)), cep50=float(np.percentile(r, 50)), r95=float(np.percentile(r, 95)),
                rmax=float(r.max()), v95=float(np.percentile([e["speed_cms"] for e in late], 95)),
                trk=sum(1 for sv in last if sv[2] > 0), used=sum(1 for sv in last if sv[5]))


def uart_load(n_svs, rate=10, sat_div=5):
    pvt = 8 + 92                                        # header 6 + checksum 2 + payload
    sat = 8 + 8 + 12 * n_svs
    bps = 10 * (rate * pvt + rate / sat_div * sat)      # 8N1 = 10 bits per byte
    return bps, {b: 100 * bps / b for b in (9600, 19200, 38400, 57600, 115200)}
```

The output of `python3 gps_lab.py out pygpsdata-MIXED.log`, the synthetic part:

```text
SYNTHETIC capture - model assumptions:
  visible sats {'G': 10, 'E': 8, 'C': 10, 'R': 7}, track >= 20 dB-Hz, cold decode >= 30 dB-Hz,
  pseudorange error 1.5 m (tau 60 s) + 0.3 m white, 10 Hz NAV-PVT, NAV-SAT 1:5, 600 s

scenario                             file kB TTFF s 8sat s trk sats  PDOP  HDOP CEP50   R95  v95 bad
GPS only                                 745   26.7   32.8  10   10  1.57  0.79  1.13  2.61    9   0
M8 default: GPS+GLO (galileo OFF)        844   25.8   27.1  17   16  1.38  0.60  0.70  1.30    7   0
M8 + gps_ublox_use_galileo=ON            956   28.6   29.3  25   24  1.06  0.50  0.44  0.90    6   0
M10 default: GPS+GAL+BDS                 998   25.4   26.5  28   28  0.87  0.46  0.55  1.23    5   0
M10 default, VTX noise +10 dB            998   27.8   29.2  28    9  4.70  1.31  1.91  3.33   15   0
M10 default, hot start                   998    0.5    0.6  28   28  0.87  0.46  0.59  1.09    5   0
  (TTFF and 8sat: s from power-on; trk = sats with C/N0 > 0 in the last NAV-SAT; sats/DOP/scatter: medians after the first 60 s of fix; CEP50/R95 m; v95 = 95th pct still speed, cm/s; bad = frames with a wrong checksum)
```

{{diagram:chart-bf-gps-cold-sats|A cold start from the synthetic logs: GPS+GLONASS and the M10 pass the 8-satellite threshold 1–2 s after the fix, GPS only — after 6 s. VTX noise of +10 dB leaves 9 satellites in the solution out of 28 visible.}}

What the table shows (the numbers are properties of the model, the causes are physical):
1. **Constellations.** GPS only: 10 satellites, PDOP 1.57, R95 2.6 m; with GLONASS — 16 and 1.38; with Galileo — 24 and 1.06, R95 0.9 m versus 1.3 m. An M10 out of the box has better geometry than an M8 out of the box. TTFF is 25–29 s for all of them: it is set by the ephemeris decoding, not by the number of satellites.
2. **The GPS flag.** “GPS only” reaches 8 satellites 6 s after the fix (32.8 versus 26.7 s), with two systems — after 1 s.
3. **VTX noise** of +10 dB lowers the C/N0 of all satellites by 10 dB. All 28 are tracked (`trk`), but from a cold start the ephemeris was downloaded only for the 9 strong ones: PDOP 4.70, R95 3.3 m, a speed at rest of 15 cm/s. The mechanism is in the datasheet: cold-start sensitivity is −148 dBm, tracking sensitivity is −167 dBm. That is why the bench test compares both the satellites after the fix and a cold start with the VTX on.
4. **Hot start:** a fix in 0.5 s; the wait for the Betaflight auto-configuration is longer (about 6 s).

### Step 3. The UART baud rate
```text
UART load, 10 Hz NAV-PVT + NAV-SAT 1:5 (disarmed):
  10 SVs in NAV-SAT:  12720 bit/s -> 9600: 132.5%  19200:  66.2%  38400:  33.1%  57600:  22.1%  115200:  11.0%
  28 SVs in NAV-SAT:  17040 bit/s -> 9600: 177.5%  19200:  88.8%  38400:  44.4%  57600:  29.6%  115200:  14.8%
  32 SVs in NAV-SAT:  18000 bit/s -> 9600: 187.5%  19200:  93.8%  38400:  46.9%  57600:  31.2%  115200:  15.6%
```

At 9600 with 10 Hz even NAV-PVT does not fit. At 19200 (the SoftSerial limit) the load is 89–94 % before arming — frames will be lost. 57600 (the default) is 30 %; at 115200 the documentation notes packet loss and advises 57600.

The fourth block is the check of the real recording and the run. Put your own recording in as the second argument: `python3 gps_lab.py out my_m10.ubx`.

```python
def check_real(path):
    """A real capture: what Betaflight would read, and our DOP from NAV-SAT vs the receiver's NAV-DOP."""
    data = Path(path).read_bytes()
    hw = [ln.split(",")[-1].split("*")[0] for ln in data.decode("ascii", "replace").splitlines()
          if ln.startswith("$GNTXT") and "HW" in ln]
    stats, pvt, sat, rx = {"bad": 0}, {}, {}, {}
    for cls, mid, p in frames(data, stats):
        if (cls, mid) == (0x01, 0x07):
            e = nav_pvt(p)
            pvt[e["t"]] = e
        elif (cls, mid) == (0x01, 0x35):
            t, svs = nav_sat(p)
            sat[t] = svs
        elif (cls, mid) == (0x01, 0x04):                 # NAV-DOP: gDOP pDOP tDOP vDOP hDOP (x0.01)
            t = struct.unpack_from("<I", p, 0)[0] / 1000
            rx[t] = [v / 100 for v in struct.unpack_from("<5H", p, 4)]
    print(f"real capture {Path(path).name}: {hw[0] if hw else '?'}, NAV-PVT {len(pvt)}, NAV-SAT {len(sat)},"
          f" NAV-DOP {len(rx)}, bad checksums {stats['bad']}")
    e = list(pvt.values())
    lat0, lon0 = np.mean([x["lat"] for x in e]), np.mean([x["lon"] for x in e])
    r = [math.hypot((x["lon"] - lon0) * 111_320 * math.cos(math.radians(lat0)), (x["lat"] - lat0) * 111_320) for x in e]
    print(f"  Betaflight view: 3D fix {sum(x['fix'] for x in e)}/{len(e)}, numSV {min(x['sats'] for x in e)}-"
          f"{max(x['sats'] for x in e)}, pDOP {min(x['pdop'] for x in e):.2f}-{max(x['pdop'] for x in e):.2f},"
          f" hAcc {min(x['hacc'] for x in e):.1f}-{max(x['hacc'] for x in e):.1f} m,"
          f" scatter over {e[-1]['t'] - e[0]['t']:.0f} s: max {max(r):.2f} m")
    print("  epoch     used (sys)          HDOP rx / 1 clk / clk per sys   PDOP rx / 1 clk / clk per sys")
    for t in sorted(set(sat) & set(rx)):
        used = [(s, el, az) for s, _sv, _c, el, az, u in sat[t] if u]
        h1, p1, _, _ = dop(used)
        h2, p2, _, _ = dop(used, clock_per_system=True)
        by = {k: sum(1 for u in used if u[0] == k) for k in sorted({u[0] for u in used})}
        print(f"  {t:9.0f}  {len(used):2d} {str(by):16s}   {rx[t][4]:5.2f} / {h1:5.2f} / {h2:5.2f}"
              f"             {rx[t][1]:5.2f} / {p1:5.2f} / {p2:5.2f}")


SCENARIOS = [  # name, constellations, start, VTX noise rise dB
    ("GPS only", "G", "cold", 0),
    ("M8 default: GPS+GLO (galileo OFF)", "GR", "cold", 0),
    ("M8 + gps_ublox_use_galileo=ON", "GRE", "cold", 0),
    ("M10 default: GPS+GAL+BDS", "GEC", "cold", 0),
    ("M10 default, VTX noise +10 dB", "GEC", "cold", 10),
    ("M10 default, hot start", "GEC", "hot", 0),
]

if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) > 2:
        check_real(sys.argv[2])
        print()
    print("SYNTHETIC capture - model assumptions:")
    print(f"  visible sats {VISIBLE}, track >= {CNO_TRACK} dB-Hz, cold decode >= {CNO_DECODE} dB-Hz,")
    print(f"  pseudorange error {SIGMA_SLOW} m (tau {TAU_S:.0f} s) + {SIGMA_WHITE} m white, 10 Hz NAV-PVT, NAV-SAT 1:5, 600 s")
    print()
    print(f"{'scenario':36s} {'file kB':>7s} {'TTFF s':>6s} {'8sat s':>6s} {'trk':>3s} {'sats':>4s} {'PDOP':>5s} {'HDOP':>5s}"
          f" {'CEP50':>5s} {'R95':>5s} {'v95':>4s} {'bad':>3s}")
    for i, (name, systems, start, noise) in enumerate(SCENARIOS):
        f = out / f"synthetic_{i}_{systems}_{start}_{noise}dB.ubx"
        make_capture(f, systems, start, noise, seed=100 + i)
        a = analyze(f)
        kb = f.stat().st_size / 1024
        if a["ttff"] is None:
            print(f"{name:36s} {kb:7.0f}  no 3D fix in 600 s")
            continue
        arm = f"{a['t_arm']:6.1f}" if a["t_arm"] is not None else "  never"
        print(f"{name:36s} {kb:7.0f} {a['ttff']:6.1f} {arm} {a['trk']:3d} {a['sats']:4.0f} {a['pdop']:5.2f} {a['hdop']:5.2f}"
              f" {a['cep50']:5.2f} {a['r95']:5.2f} {a['v95']:4.0f} {a['bad']:3d}")
    print("  (TTFF and 8sat: s from power-on; trk = sats with C/N0 > 0 in the last NAV-SAT; sats/DOP/scatter: medians after the first 60 s of fix;"
          " CEP50/R95 m; v95 = 95th pct still speed, cm/s; bad = frames with a wrong checksum)")
    print()
    print("UART load, 10 Hz NAV-PVT + NAV-SAT 1:5 (disarmed):")
    for n in (10, 28, 32):
        bps, util = uart_load(n)
        print(f"  {n:2d} SVs in NAV-SAT: {bps:6.0f} bit/s -> " + "  ".join(f"{b}: {u:5.1f}%" for b, u in util.items()))
```

### Step 4. Configuration (a procedure from the source and the documentation)
Betaflight App: Ports → UART2 → Sensor Input “GPS”, 57600 → Save and Reboot. Configuration → enable GPS, Protocol UBLOX, Auto Config. The same in the CLI:

```text
feature GPS
serial UART2 2 115200 57600 0 115200
set gps_provider = UBLOX
set gps_auto_config = ON
set gps_ublox_use_galileo = ON
set gps_sbas_mode = AUTO
set gps_update_rate_hz = 10
set gps_set_home_point_once = OFF
set gps_rescue_min_sats = 8
set osd_gps_sats_show_pdop = ON
save
```

`serial UART2 2 …` (in 4.5 — `serial 1 2 …`): UART2, the GPS function (value 2 = bit 1), and the fourth number is the GPS baud rate. For a MAX-M10S with the factory GPS+GAL+BDS set (a 3 Hz ceiling) there are two ways. The first is `set gps_update_rate_hz = 3`. The second is u-center through `gpspassthrough`: CFG-SIGNAL GPS+GAL, save to BBR, and then 10 Hz. After a reboot `status` should show `GPS: connected, UART2 57600 (set to 57600), configured, version =  M10` (two spaces after `=` — that is how it is in `cli.c`).

### Moving to real hardware
Propellers are off for steps 1–5. GPS Rescue is enabled only after this procedure, per `bf-failsafe`.
1. **Wiring.** Check continuity of TX→RX and RX→TX, and GND. The voltage on the GPS power pad without the module — per the marking on the module board (5 V to the LDO input or 3.3 V). `status` → `connected … configured, version = M8|M10`. If `NOT CONNECTED`, see the troubleshooting section.
2. **Cold start, open sky.** The aircraft on a table in a field or on a roof, the VTX unpowered or in pit mode. The module unpowered for more than 4 h, or a reset through u-center (CFG-RST cold). Time from connecting the battery to a 3D fix and to 8 satellites (the GPS tab or the OSD). Record 10 minutes of `.ubx` through `gpspassthrough` and u-center and run it through `gps_lab.py`. The criterion: a fix within 60 s, no fewer than 12 satellites after 2 minutes (the documentation: “about 20”), PDOP ≤ 1.5, speed at rest p95 ≤ 20 cm/s, R95 ≤ 3 m.
3. **VTX off/on.** After a stable fix, the VTX at minimum power, then at the working power levels (25 / 200 / 400 mW or the modes of the digital air unit), 2 minutes per level: satellites, PDOP, the average C/N0 from NAV-SAT (u-center). Then a cold start with the VTX on. The criterion: at working power no more than 2 satellites fewer, C/N0 no more than 3 dB lower, a cold start no longer than 90 s. Otherwise move the module and repeat.
4. **Tilt.** Tilt the aircraft 45° forward, back and sideways. The number of satellites in the fix does not drop by more than 2.
5. **Home.** Arm without propellers (`bf-arming-safety`): “short-long” twice, the arrow and 0 m in the OSD. Disarm, carry it 20 m: with `gps_set_home_point_once = OFF` the arrow shows `-`, and after a new arm home is at the new point. The coordinates are visible in the OSD.
6. **The first flight with GPS** (Rescue off): takeoff, a straight 50 m pass at more than 2 m/s. The arrow points home within the sector of the symbol (the documentation: within 5–10 s or 50–80 m), and on the way back the distance decreases. Abort the flight if the arrow has not settled after 80 m, there are fewer than 8 satellites, `RESCUE N/A` appeared, or the speed in a hover in calm air is more than 1 m/s.

Self-check: the lab is complete when:
- **Calculation (without hardware):** `gps_lab.py` has been run. The real M8030 recording gave a DOP match with NAV-DOP no worse than 0.03 (the “single clock” model). The table of the six synthetic scenarios is reproduced, and for each one you wrote down how it differs from the default M10 and checked your note against the analysis below the table. A UART baud rate with a load below 50 % is chosen (by the output of step 3 that is 38400 and above).
- **Hardware:** `status` with the module version is written down. The cold start is timed (the time to the fix and to 8 satellites) and fits within 60 s. A 10-minute `.ubx` recording of your own module has been run through `gps_lab.py`, and the numbers pass the criterion of item 2: PDOP ≤ 1.5, v95 ≤ 20 cm/s, R95 ≤ 3 m. The “VTX off/by power level” table is filled in and passes the criterion of item 3 (no more than 2 satellites fewer, C/N0 no more than 3 dB lower), and the 45° tilt and home on arming are checked. The `diff all` after setup is saved next to the `.ubx` recording.

**Reference for self-check.** The calculation is correct if the rows of the scenario table match the module: “GPS only” — 10 satellites and PDOP 1.57, “M10 default” — 28 and 0.87, “VTX noise +10 dB” — `trk` 28, but 9 in the solution and PDOP 4.70. The correct explanation of the differences is in the analysis below the table: the number of constellations changes the geometry and R95 but not TTFF (25–29 s is set by the ephemeris decoding); VTX noise leaves tracking intact but prevents the ephemeris of the weak satellites from being downloaded. The model's DOP differs from NAV-DOP by 5–23 % — “a clock per system” was computed instead of a single clock. On hardware R95 from a short recording looks better than 1 m — that is not accuracy: less than 10 minutes was recorded, and the error changes over minutes.

## diagnostics
- **Symptom:** `status` → `GPS: NOT CONNECTED` or `NOT ENABLED`
  - Possible cause: `feature GPS` is off; TX/RX are not crossed over; the module has no power (on USB some boards do not power the GPS pad); the GPS function is on the wrong UART; SoftSerial.
  - What to do: `feature GPS`, `serial` with function 2 (GPS) on the right UART, a continuity check, power from a battery without propellers.
- **Symptom:** it does not arm, the `GPS` flag in `status`
  - Possible cause: Rescue is configured (the procedure or the mode), and there is no fix or fewer satellites than `gps_rescue_min_sats`; or Rescue is configured with `feature GPS` off — then the flag stays forever.
  - What to do: wait under an open sky, watch the OSD and the GPS tab; do not lower `gps_rescue_min_sats` below 8 and do not enable `gps_rescue_allow_arming_without_fix` just to be able to arm.
  - Consequences: an arm without home gives `RESCUE N/A` — on failsafe the aircraft will not fly home.
- **Symptom:** few satellites or a slow fix, while with the VTX off everything is fine (question No. 17)
  - Possible cause: interference from the VTX or the digital air unit raises the noise floor; a cold start is especially sensitive (ephemeris decoding).
  - What to do: the “VTX off/on” bench test, the module farther from the VTX antenna and higher, the antenna facing the sky, turn the VTX on after the fix, a battery or capacitor on V_BCKP for a hot start.
- **Symptom:** the M10 does not deliver 10 Hz, the NAV interval in `debug_mode = GPS_CONNECTION` is more than 100 ms
  - Possible cause: the factory GPS+GAL+BDS set of the MAX-M10S is limited to 3 Hz (datasheet).
  - What to do: `gps_update_rate_hz = 3`, or through u-center the GPS+GAL set (10 Hz) saved to BBR.
- **Symptom:** an M10 on Betaflight 4.4 and earlier works poorly or erratically
  - Possible cause: 4.4 does not know the M10 and sends only the old CFG messages; the GPS tab documentation requires 4.5 for the M10.
  - What to do: update to 2025.12 (or at least to 4.5, if the board is not supported by anything newer).
- **Symptom:** an M10 with ROM SPG 5.00 firmware (MON-VER) loses accuracy with a strong signal
  - Possible cause: known limitation 14 from the 5.00 release notes — the “balanced” power mode. Betaflight (verified on 4.5-maintenance) sends M9+ only CFG-PM-OPERATEMODE = FULL, and CFG-PMS only to M8 modules.
  - What to do: u-center → CFG-PMS full power saved to BBR, or a module with SPG 5.10.
- **Symptom:** the home arrow points the wrong way right after takeoff
  - Possible cause: there is no compass, and the GPS heading has not been learned yet (it needs a speed above 1 m/s, the nose tilted forward, a roll below 12°, the yaw stick centered).
  - What to do: a straight pass of 30–50 m at more than 2 m/s, then check the arrow; if it has not settled — land and reboot.
- **Symptom:** home turned out to be at the landing point, not the takeoff point
  - Possible cause: `gps_set_home_point_once = OFF` and a disarm in the field — the new arm overwrote home.
  - What to do: `gps_set_home_point_once = ON` for flights with intermediate landings, the first arm at the launch site.
- **Symptom:** `gps_ublox_use_galileo = ON`, but there are no Galileo (E) satellites on the GPS tab — or they are there with OFF
  - Possible cause: Galileo is changed only through CFG-GNSS; the step is skipped with SBAS ≠ NONE and Galileo OFF; the M10 documents only VALSET.
  - What to do: check the satellite list on the GPS tab; if necessary set CFG-SIGNAL in u-center and save to BBR.
- **Symptom:** GPS loss in flight, `status` shows a rate of 115200, the NAV intervals jump around in the logs
  - Possible cause: frame loss at 115200 (documentation).
  - What to do: `serial … 57600 …` for GPS, check the load per step 3.

## checklist
- The module is an M8 or M10, and the firmware version and constellation set are known (MON-VER, MON-GNSS)
- Power per the marking on the module board, UART crossed over, a hardware UART, `feature GPS`
- The antenna faces the sky, the module is on a mast or on top, away from the VTX and the power wires; the “VTX off/on” test is passed
- `status` → `connected, configured`, 57600 baud, the rate no higher than the module's ceiling
- I know the discrepancies between the documentation and the code (verified on 4.5-maintenance): the model on the first fix, SBAS NONE, low satellites — a threshold of 4, `gps_auto_baud` affects nothing
- `gps_rescue_min_sats` ≥ 8, `gps_rescue_allow_arming_without_fix = OFF`, home is recorded on arming (“short-long” twice)
- In the OSD: satellites with PDOP, the home arrow and distance, coordinates, warnings
- Without a compass: a straight pass of 30–50 m before trusting the arrow
- GPS Rescue is configured and tested per `bf-failsafe`

## references
- Betaflight io/gps.c — the u-blox configuration state machine, NAV-PVT, home, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/io/gps.c | primary | A
- Betaflight pg/gps.c — the gpsConfig defaults, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/pg/gps.c | primary | A
- Betaflight cli/settings.c — the gps_*, mag_*, osd_gps_* variables, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/cli/settings.c | primary | A
- Betaflight cli/cli.c — status (the GPS line), gpspassthrough, serial, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/cli/cli.c | primary | A
- Betaflight fc/core.c — the GPS arming flag, the arming signals, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/fc/core.c | primary | A
- Betaflight flight/gps_rescue.c — the GPS_MIN_SAT_COUNT threshold, LOWSATS, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/gps_rescue.c | primary | A
- Betaflight flight/imu.c — GPS heading without a compass, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/imu.c | primary | A
- Betaflight flight/position.c — GPS trust from PDOP, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/position.c | primary | A
- Betaflight osd/osd_elements.c — the satellite, speed and home elements, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/osd/osd_elements.c | primary | A
- Betaflight sensors/compass.c — mag_hardware, calibration, 4.5-maintenance | https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/sensors/compass.c | primary | A
- Betaflight io/gps.c, tag 2025.12.5 (230400, GPS_VIRTUAL) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/io/gps.c | primary | A
- Betaflight cli/settings.c, tag 2025.12.5 (gps_*, mag_declination, ap_*, pos_hold_*) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/cli/settings.c | primary | A
- Betaflight cli/settings.c, 4.4-maintenance (gps_ublox_mode) | https://raw.githubusercontent.com/betaflight/betaflight/4.4-maintenance/src/main/cli/settings.c | primary | A
- Betaflight docs — GPS guide (u-center, models, SBAS) | https://betaflight.com/docs/wiki/guides/current/Gps | primary | B
- Betaflight docs — GPS Rescue (checking the module, heading without a compass, the compass) | https://betaflight.com/docs/wiki/guides/current/GPS-Rescue | primary | B
- Betaflight App — GPS tab (the M10 requires 4.5, PDOP) | https://betaflight.com/docs/wiki/app/gps-tab | primary | B
- u-blox MAX-M10S Data sheet UBX-20035208 (constellations, TTFF, rate, power) | https://content.u-blox.com/sites/default/files/MAX-M10S_DataSheet_UBX-20035208.pdf | primary | A
- u-blox M10 SPG 5.10 Interface Description UBX-21035062 (CFG-SIGNAL, DYNMODEL, PM) | https://cdn.sparkfun.com/assets/f/1/2/9/e/u-blox-M10-SPG-5.10_InterfaceDescription_UBX-21035062.pdf | primary | A
- u-blox MAX-M10S Integration manual UBX-20053088 (ephemeris 4 h, V_BCKP, the RAM/BBR layers) | https://cdn.sparkfun.com/assets/5/c/a/0/b/MAX-M10S_IntegrationManual_UBX-20053088.pdf | primary | A
- u-blox M10 ROM 5.00 Release notes UBX-20050981 (known limitations) | https://cdn.sparkfun.com/assets/2/0/d/7/4/u-blox_M10_ROM_5.00_ReleaseNotes_UBX-20050981.pdf | primary | A
- u-blox NEO-M8 FW3 Data sheet UBX-15031086 | https://www.mouser.lt/datasheet/3/3699/1/NEO_M8_FW3_DataSheet_UBX_15031086.pdf | primary | A
- u-blox SAM-M10Q Data sheet UBX-22013293 (50 × 50 mm ground plane, inrush current) | https://cdn.sparkfun.com/assets/1/1/d/f/4/SAM-M10Q_DataSheet_UBX-22013293.pdf | primary | A
- pyubx2 test data — a real u-blox M8030 recording (pygpsdata-MIXED.log) | https://raw.githubusercontent.com/semuconsulting/pyubx2/master/tests/pygpsdata-MIXED.log | secondary | B

## notes
The names, defaults and ranges are checked against the settings table and the defaults of 2025.12.5; the behavior of the auto-configuration and the parser is taken from the 4.5-maintenance source (code = 4.5.5) and verified by following the code, not by names. The module figures are from the u-blox datasheets. The synthetic logs are a model with the assumptions from the output header: their numbers show the direction of an effect, not the properties of a specific module. The real check is a single third-party M8030 recording 38 s long. Not verified: whether the M10 answers a UBX-CFG-GNSS poll, that is, whether `gps_ublox_use_galileo` works on an M10; what the MAX-M10S does if 10 Hz is requested above the 3 Hz ceiling; whether CFG-PM-OPERATEMODE = FULL is the same as the “full power” of CFG-PMS on ROM 5.00. The auto-configuration time of about 6 s is an estimate from the `gps.c` constants, with no measurement. The acceptance thresholds on the bench (C/N0 −3 dB, ±2 satellites) are a course rule, not a manufacturer's specification.
