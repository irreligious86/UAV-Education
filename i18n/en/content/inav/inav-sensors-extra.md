---
id: inav-sensors-extra
title: "Additional INAV sensors: rangefinder and SURFACE, optical flow, pitot, temperature"
level: L2
readingTime: 65 min
firmware: INAV 9.1 (checked against 9.1.0)
status: published
added: 2026-11-20
tags:
  - INAV
  - rangefinder
  - SURFACE
  - optical flow
  - pitot
  - airspeed
  - temperature
  - barometer
related:
  - inav-gps
  - inav-setup-scratch
  - inav-setup-wing
  - inav-wing
  - inav-mc-tuning
  - inav-ipf
  - inav-osd-hd
  - est-alt-sources
  - nav-indoor
next:
  - inav-ipf
source: content/inav/inav-sensors-extra.md
source_hash: f3cd9787f2b2
---

## summary
GPS, the compass and the barometer from `inav-gps` cover outdoor flight. This module is about the other sensors of INAV 9.1.0: the rangefinder and the SURFACE mode, optical flow and position hold without GPS, the pitot tube and virtual airspeed, temperature sensors, and along the way the choice of the altitude source and flying without a barometer. From the source it works out which `*_hardware` values exist, by what formula a sensor number turns into an altitude or a speed, and under which conditions the firmware discards a measurement. The lab needs no hardware: decide from a table of readings which rangefinder altitudes are accepted, compute airspeed from pressure and from GPS with wind, repeat the arithmetic of the flow calibration and find three errors in the settings of three aircraft.

## theory
### Common rules for all four sensors
This module is about four optional INAV sensors — the rangefinder, optical flow, the pitot tube and temperature sensors — and about the choice of the altitude source. The reading order: first the common rules for enabling them (this section), then the rangefinder: the list of sensors, the path from a reading to the AGL altitude and the SURFACE mode; after it optical flow and position hold without GPS; then the pitot and where the firmware uses airspeed; at the end temperature and the barometer. The sections are self-contained: if the aircraft has only a pitot, go straight to it after the common rules. GPS, the compass and the main barometer are in `inav-gps`, the fixed-wing landing with a rangefinder flare is in `inav-geozones-landing`.

A sensor is enabled with a single `*_hardware` setting (the Configuration tab in Configurator 9, the lists Barometer, Pitot tube, Rangefinder, Optical flow) and takes effect after a reboot. They have no separate `feature` flags.

The rule that catches people most often (`sensors/diagnostics.c`): a sensor that is **selected but not found or silent** is treated as a hardware failure. `isHardwareHealthy()` returns false, and the arming-disabled flag `HWFAIL` appears in `status`. This applies to the barometer, the rangefinder, the pitot and optical flow alike. Hence: on a board without a barometer set `baro_hardware = NONE`, not `AUTO`; if you removed the rangefinder, set `rangefinder_hardware = NONE` back.

Serial sensors take a UART with a function from `io/serial.h`: `RANGEFINDER` — 65536 (Rangefinder in Ports), `OPTICAL_FLOW` — 16384 (Optic flow). MSP sensors have no function of their own: they need a port with the ordinary MSP function (1).

### Rangefinder: the values of `rangefinder_hardware`
| Value | Bus and protocol | Limit in the driver, cm | Cone, ° | Max tilt, ° | Period, ms |
|---|---|---|---|---|---|
| `NONE` | the default | — | — | — | — |
| `SRF10` | I²C, ultrasonic; not part of the common build (2 targets) | 600 | 50 | 25 | 70 |
| `VL53L0X` | I²C 0x29, laser ToF | 250 | 90 | 45 | 33 |
| `VL53L1X` | I²C, laser ToF | 300 | 27 | 13.5 | 40 |
| `US42` | I²C 0x70, ultrasonic | 400 | 25 (computed 30) | 15 | 100 |
| `TOF10120_I2C` | I²C 0x52, laser ToF | 200 | 30 (computed 45) | 22.5 | 100 |
| `TERARANGER_EVO` | I²C 0x31 | its own “out of range” code | 90 | 45 | 70 |
| `MSP` | a UART with the MSP function, the message `MSP2_SENSOR_RANGEFINDER` | none | 90 | 45 | 30 |
| `BENEWAKE` | UART `RANGEFINDER`, 115200, the TFmini protocol | none | 90 | 45 | 30 |
| `USD1_V0` | UART `RANGEFINDER`, 115200 (an NRA radar on the US-D1 protocol) | none | 90 | 45 | 30 |
| `NRA` | UART `RANGEFINDER`, 115200 (NanoRadar NRA15 / NRA24) | none | 90 | 45 | 30 |
| `FAKE` | simulator data (X-Plane, RealFlight, HITL) | 250 | 90 | 45 | 30 |

The values are taken from `drivers/rangefinder/*.c` and `rangefinder_virtual.h`. The I²C drivers return “out of range” above their limit by themselves. The serial drivers have no limit: the `maxRangeCm` field is filled with the number 250 but is not read anywhere, and a radar faithfully reports its tens of meters. How much of that goes into the estimator is decided by one setting — `inav_max_surface_altitude`.

The HC-SR04 and US-100 sensors are not supported (`docs/Rangefinder.md`).

### The path of a reading: from the driver to the AGL altitude
1. The driver returns a distance in centimeters or a code: −1 “out of range”, −2 “failure”, −3 “no new data”. A reply of −1 counts as a live reply; health means “there was a reply within the last 500 ms”.
2. `rangefinder_median_filter = ON` enables a median over the last **five** readings (`quickMedianFilter5`), although the description of the setting speaks of three.
3. Tilt compensation (`rangefinderProcess()`): cos θ = cos(roll) × cos(pitch). If cos θ is less than the cosine of half the cone — the reading is replaced with −1. Otherwise altitude = distance × cos θ, with the fractional part dropped.
4. The estimator (`navigation_pos_estimator_agl.c`) accepts a reading if 0 ≤ altitude ≤ `inav_max_surface_altitude`. An accepted reading gives a “1”, any other — a “0”, and from these ones and zeros a first-order filter computes the **reliability**: r ← r × (1 − α) + reading × α, α = Δt / (Δt + 0.478 s). A gap longer than 400 ms resets r to zero.
5. The AGL quality: HIGH at r ≥ 0.75, MID at 0.33 ≤ r < 0.75, otherwise LOW. The only way out of LOW is straight to HIGH. In HIGH the estimate of the altitude above the surface is pulled toward the rangefinder with the weights `inav_w_z_surface_p` and `inav_w_z_surface_v`; in MID it is blended with the general altitude; in LOW it equals the general altitude minus a remembered offset.

All of item 5 is executed **only if the barometer is healthy**: the condition in the code is `EST_SURFACE_VALID` and `EST_BARO_VALID` at the same time. Without a barometer the AGL quality is always LOW, no matter how much the rangefinder measures.

The AGL altitude is a separate estimate. The rangefinder is not mixed into the Z altitude on which ALTHOLD, RTH and missions fly.

| Setting | Default | Range | Meaning |
|---|---|---|---|
| `rangefinder_hardware` | NONE | the table above | the sensor type |
| `rangefinder_median_filter` | OFF | OFF · ON | a median over 5 readings |
| `inav_max_surface_altitude` | 200 cm | 0–1000 | above it — the reading is not accepted |
| `inav_w_z_surface_p` | 3.5 | 0–100 | the weight of the rangefinder in the AGL altitude |
| `inav_w_z_surface_v` | 6.1 | 0–100 | the weight of the rangefinder in the AGL vertical velocity |
| `nav_max_terrain_follow_alt` | 100 cm | up to 1000 | the SURFACE altitude at full throttle |

{{diagram:inav-sensors-extra-flow|The rangefinder and optical flow do not enter the general altitude and position directly: the rangefinder feeds the separate AGL estimate and serves as the lever arm for the flow, and airspeed does not get into the position estimator at all.}}

### The SURFACE mode and the other consumers of AGL
The `SURFACE` mode (`BOXSURFACE`) appears in the mode list if the platform is a multirotor and **both a barometer and a rangefinder** are detected. An airplane does not have it: `navTerrainFollowingRequested()` contains an explicit prohibition.

SURFACE works on top of ALTHOLD or POSHOLD; RTH and missions reset it and fly on the general altitude. While it is on, the altitude controller takes the AGL altitude and velocity, and the throttle stick sets not the climb rate but the altitude itself: from idle to full throttle — from 0 to `nav_max_terrain_follow_alt`.

- AGL is trusted (quality MID or HIGH) and the target is above 10 cm — the set altitude above the surface is held, “(SURFACE)” in the OSD.
- Otherwise — a descent at 50 cm/s. If AGL is not trusted, the descent depends on the stick: 50 cm/s with the throttle at the middle or above, up to 200 cm/s at idle; “(!SURFACE UNRELIABLE!)” in the OSD.

**This is a mode that lowers the aircraft by itself.** Fly above `inav_max_surface_altitude`, tilt by more than half the cone, pass over water or glass — and half a second later a descent starts. Keep `nav_max_terrain_follow_alt` noticeably below `inav_max_surface_altitude`, and a finger on the switch that turns SURFACE off.

Where else AGL is used in 9.1.0:

- **The multirotor landing detector.** With a trusted AGL a landing is recognized only if the altitude is no more than the minimum of the flight plus 5 cm. Below 50 cm AGL the descent rate drops to `nav_land_minalt_vspd`.
- **The flare of fixed-wing autoland** (`inav-geozones-landing`). The entry condition is a rangefinder status of “healthy” and an altitude of no more than land alt + `nav_fw_land_flare_alt`. The altitude is taken straight from the rangefinder if its reading is in range, otherwise from AGL or the general altitude. “Healthy” means “it replies”, not “it sees the ground”.
- **The old fixed-wing landing** (`inav-wing`): with a trusted AGL below `nav_land_slowdown_minalt` the motor stops.
- **OSD and logic.** The Rangefinder distance element shows the raw distance without tilt compensation. The `inav-ipf` operands: 35 — AGL is trusted (HIGH only), 36 — AGL in cm, 37 — the raw distance.

### Optical flow
`opflow_hardware`: `NONE` (default), `CXOF` (a UART with the `OPTICAL_FLOW` function, the baud rate is taken from the sensors column of the port), `MSP` (the message `MSP2_SENSOR_OPTIC_FLOW`), `FAKE` (not part of ordinary builds). The firmware has no SPI driver for the PMW3901: such sensors are connected through an intermediate board over MSP.

The sensor sends a count of the image displacement on two axes over an interval Δt, and a quality. `sensors/opflow.c` turns this into an angular rate:

flow [°/s] = count × (10⁶ / Δt [µs]) / `opflow_scale`.

The body rotation from the gyro over the same interval is subtracted from the flow, and the remainder is multiplied by the altitude from the rangefinder (`navigation_pos_estimator_flow.c`):

V = (flow − gyro) [rad/s] × h [cm].

Without a rangefinder the flow is not used at all: the altitude is the lever arm that turns an angle into centimeters.

The conditions under which the flow takes part in the estimate:

- quality with hysteresis: the flow becomes valid at a quality ≥ 35 and invalid at ≤ 10 (percent; for MSP the byte 0–255 is converted to 0–100);
- the data is no older than 200 ms, the rangefinder replies, its reliability r ≥ 0.33, the Z estimate is valid;
- **horizontal GPS is not trusted.** The corrections are in a “GPS or flow” expression: while there is GPS, the flow is not called.

The flow gives a velocity correction with the weight `inav_w_xy_flow_v` (2.0). The flow-based position is integrated only if `inav_allow_dead_reckoning = ON`, with the weight `inav_w_xy_flow_p` (1.0). With `OFF` the position without GPS stays untrusted.

| Setting | Default | Range | Meaning |
|---|---|---|---|
| `opflow_hardware` | NONE | NONE · CXOF · MSP · FAKE | the sensor type |
| `opflow_scale` | 10.5 | 0–10000 | sensor counts per degree; at a value ≤ 0.01 the flow is zero |
| `align_opflow` | CW0FLIP | as for `align_mag` | the sensor alignment (the field `opflow_align` in the code) |
| `inav_w_xy_flow_p` · `inav_w_xy_flow_v` | 1.0 · 2.0 | 0–100 | the flow weights in position and velocity |
| `inav_allow_dead_reckoning` | OFF | OFF · ON | allow a position without GPS |

**Scale calibration** (the Calibration tab, the button “Calibrate Optic Flow sensor”, the command `MSP2_INAV_OPFLOW_CALIBRATION`, only while disarmed). For 30 seconds the aircraft is held by hand above a surface and rocked in roll and pitch **without moving it**. The code sums, over the valid samples, the magnitude of the body rate and the magnitude of the flow in sensor units:

`opflow_scale` = Σ(|count| × 10⁶ / Δt) / Σ|gyro, °/s|.

The result is saved by itself if Σ|gyro| is greater than 3600. With pure rotation in place the flow has to equal the rotation — hence the scale. The firmware has no “drag it over a known distance” calibration.

### Combined MSP sensors
A “flow + lidar” board sends two MSPv2 messages to one UART without a request and without a reply:

| Message | Code | Payload |
|---|---|---|
| `MSP2_SENSOR_RANGEFINDER` | 0x1F01 | quality (a byte, not used), distance int32 in **mm**; ≤ 0 — out of range |
| `MSP2_SENSOR_OPTIC_FLOW` | 0x1F02 | quality 0–255, motionX and motionY int32 |
| `MSP2_SENSOR_AIRSPEED` | 0x1F06 | differential pressure as a float in Pa, temperature |

The setup: the MSP function on the port (the baud rate — from the sensor documentation), `rangefinder_hardware = MSP`, `opflow_hardware = MSP`. The MSP drivers are always “detected”, so a silent sensor gives `HWFAIL` after 500 ms, not at boot. In the same code range 0x1F03–0x1F05 the GPS, the compass and the barometer are accepted over MSP.

### Position hold without GPS: what 9.1.0 allows
From `fc_msp_box.c` and `navigation.c`:

- NAV POSHOLD appears in the mode list without `feature GPS` if there is optical flow, an accelerometer, `inav_allow_dead_reckoning = ON` and an altitude source (a detected barometer).
- RTH, missions, CRUISE and COURSE HOLD require `feature GPS`. On the flow only ALTHOLD, POSHOLD and SURFACE are available.
- The heading without GPS is considered usable even without a compass — precisely with `inav_allow_dead_reckoning = ON`.
- Arming: if POSHOLD is assigned to a switch and the position estimate and home are not ready, the `NAV` flag is set. On the floor a flow sensor usually does not give the required quality, so in practice arming goes through `nav_extra_arming_safety = ALLOW_BYPASS` (default) with yaw held right (`inav-intro`). With the value `ON` there is no bypass.

The accuracy of such a hold depends on the texture and light under the aircraft; the general theory is in `nav-indoor` and `est-alt-sources`.

### Pitot: the values of `pitot_hardware` and the formula
| Value | What it is | Note |
|---|---|---|
| `NONE` | the default | |
| `AUTO` | tries MS4525, MS5525, then ADC (if a channel is assigned); in builds with `USE_PITOT_FAKE` (SITL) the chain ends at FAKE | does not detect DLVR, VIRTUAL or MSP; not found — `HWFAIL` |
| `MS4525` | I²C 0x28, ±1 psi (6895 Pa) | up to 106 m/s |
| `MS5525` | I²C 0x76 or 0x77 | new in 9.x |
| `DLVR-L10D` | I²C, ±10 inches of water (2488 Pa) | up to 64 m/s; explicit selection only |
| `ADC` | an analog MPXV7002DP, `airspeed_adc_channel` | expects a 1:1 divider and a zero at 2.5 V |
| `MSP` | `MSP2_SENSOR_AIRSPEED` | explicit selection only |
| `VIRTUAL` | computed from GPS and the wind estimate | needs `feature GPS`; without it the sensor is quietly disabled and `HWFAIL` does not appear — the only exception to the “selected but not found” rule |
| `FAKE` | simulator | only in the SITL build |

The formula from `sensors/pitotmeter.c`:

V [cm/s] = `pitot_scale` × √(2 × |P − P₀| / 1.225) × 100.

1.225 kg/m³ is the air density at sea level (`SSL_AIR_DENSITY`). There is no correction for altitude or temperature: INAV computes indicated airspeed (IAS), and that is deliberate — a stall happens at the same indicated airspeed. Three consequences of the formula:

- `pitot_scale` (default 1.0, range 0–100) multiplies the **speed**, not the pressure. The correction is linear: new scale = old × V reference / V indicated.
- There is an absolute value under the root. Swapped total and static pressure tubes give the same number; the sign will not reveal the mistake.
- P₀ is the zero, which is taken at every power-up over 4 seconds (`pitotStartCalibration()` in `fc_init.c`). Until it is taken, arming is disabled (the `CAL` flag). Wind into the tube at power-up goes into the zero. Cover the pitot probe when applying power.

`pitot_lpf_milli_hz` is the cutoff frequency of the pressure filter in millihertz: the default is **3000** (3 Hz), the range 0–50000, and 0 turns it off. In 8.0.1 it was 350 with a limit of 10000 (this matches the table in `inav-intro`).

{{diagram:chart-inav-airspeed-dp|The speed grows as the square root of the pressure: 10 m/s is only 61 Pa, so a zero error of a few pascals is noticeable precisely at low speed, and a scale of 1.08 raises the whole curve by 8 %.}}

**Virtual pitot** (`pitotmeter_virtual.c`). The wind estimator keeps the velocity vector of the air relative to the ground; its direction is where the wind is blowing to. The calculation:

- the tailwind component W∥ = W × cos(wind direction − nose heading);
- the horizontal airspeed A = ground speed − W∥;
- V = √(A² + (vertical speed + vertical wind)²).

No wind estimate — the full GPS speed is taken; no fix — `fw_reference_airspeed`. The wind estimator works only on an airplane. The result goes through the same formula and the same filter, so `pitot_scale` acts on it too.

**Checking a real pitot against GPS** (new in 9.x). While armed the reading is compared with the virtual estimate when the latter is above 7 m/s. A counter goes up on every sample outside the 30–200 % corridor and down on every plausible one; when it reaches ten, the pitot is declared failed (at the fastest — after ten samples in a row). `getAirspeedEstimate()` starts returning the virtual airspeed. The warning “PITOT FAIL” is shown only by the Multi Function Status OSD element — without it in the layout the substitution happens silently. The system message “PITOT METER FAILURE” is different: it means a failure of the pitot hardware (the same case as `HWFAIL`). Recovery — after 100 plausible samples in a row.

### Where airspeed is used in 9.1.0
| Consumer | What it does |
|---|---|
| `apa_pow` (control profile, 0–200, default 0) | on an airplane, instead of throttle-based TPA: the P, D and FF factor = (`fw_reference_airspeed` / V)^(`apa_pow` / 100), within 0.3…2.0; for I with `apa_pow` > 100 — an exponent one less, limits 0.3…1.5 |
| coordinated turn (TURN ASSIST) | the yaw rate is computed from V; without a pitot — from `fw_reference_airspeed` (1500 cm/s, 300–6000) |
| attitude (`imu.c`) | the centrifugal correction of the accelerometer on an airplane |
| GPS fix estimation on a fixed wing (`inav_allow_gps_fix_estimation`) | the dead-reckoning speed — from the pitot, otherwise `fw_reference_airspeed` |
| OSD, telemetry, logic | the Air Speed element, the thresholds `osd_airspeed_alarm_min` and `_max` in **cm/s** (0 — off), `osd_speed_source = AIR`; operand 11 in `inav-ipf` |

What 9.1.0 does not have: fixed-wing navigation still holds the throttle by pitch (`nav_fw_pitch2thr`, `inav-wing`) and does not control airspeed; there is no built-in stall warning either — its role is played by the blinking from `osd_airspeed_alarm_min`. Hence the answer to the question “do I need a pitot”: INAV flies without one, and a pitot gives PID gains tied to speed rather than to throttle (gliding with the motor off, diving) and the speed on the screen. Enable `apa_pow` (the description recommends 120) only with a verified pitot: with `apa_pow` = 120 **an airspeed that reads twice too high reduces the gains to 0.44 of the tuned ones**, and one that reads half the real value raises them to the 2.0 limit.

### Temperature
In addition to the built-in gyro and barometer temperatures there can be up to 8 external sensors: LM75 on I²C (addresses 0x48–0x4F, numbers 0–7 in INAV) and DS18B20 through the DS2482 I²C-to-1-Wire bridge. Sensors found at power-up get into free slots by themselves.

`temp_sensor <slot 0–7> <type> <address> <alarm_min> <alarm_max> <OSD symbol> <label>`

- type: 0 — empty, 1 — LM75, 2 — DS18B20;
- address: 0–7 for an LM75 or the 16 hexadecimal digits of the ROM for a DS18B20;
- the thresholds are in **tenths of a degree Celsius**, from −550 to 1250; for automatically detected sensors −200 and 600, that is, −20 and +60 °C;
- the symbol 0–6 (0 — show the label) and a label of up to 4 characters are optional: four arguments after the slot are enough for the parser, without them the symbol is 0 and the label is empty; the label is converted to upper case.

`temp_sensor` without arguments prints the slots, `temp_sensor reset` erases them all. The OSD elements — one per slot, plus the IMU, barometer and ESC temperatures with the thresholds `osd_imu_temp_alarm_*`, `osd_baro_temp_alarm_*` (−200 and 600) and `osd_esc_temp_alarm_*` (−200 and 900) in the same units. Going beyond a threshold only makes the element blink: the firmware takes no protective action.

### The barometer, `inav_default_alt_sensor` and flying without a barometer
`baro_hardware`: `NONE`, `AUTO` (default), `BMP085`, `MS5611`, `BMP280`, `MS5607`, `LPS25H`, `SPL06`, `BMP388`, `DPS310`, `B2SMPB`, `MSP`, `FAKE`.

`inav_default_alt_sensor` (default `GPS`) decides how the trust is split between the GPS altitude and the barometer (`estimationCalculateCorrection_Z()`):

| Value | Behavior in 9.1.0 |
|---|---|
| `GPS` | both sensors; as their difference grows from `inav_max_eph_epv` to twice that (10 → 20 m at the default 1000), the barometer weight falls linearly from 1 to 0 |
| `BARO` | both sensors; the GPS weight falls from 1 to 0 as the difference goes from 2 × `inav_baro_epv` to 4 × `inav_baro_epv` (2 → 4 m at the default 100) |
| `GPS_ONLY` | GPS only; the barometer is brought in if the GPS altitude is lost |
| `BARO_ONLY` | the barometer only; GPS is brought in if the barometer is lost |

At the end the corrections are multiplied by 2 / (GPS weight + baro weight): with one sensor of the two in the `*_ONLY` modes and at full separation they are doubled.

Without a barometer (`baro_hardware = NONE`): the altitude comes from GPS only with any value of the setting, and ALTHOLD stays available with `feature GPS` enabled; the SURFACE mode, the AGL estimate and the AUTO LEVEL TRIM mode of a fixed wing disappear. There is no `inav_use_gps_no_baro` setting in 9.1.0: it was removed in the move from 7.x to 8.0, and the Configurator drops a line with it from an old backup.

The compass and its alignment (`align_mag`) are covered in `inav-gps` and `inav-setup-scratch`.

### What changed between 8.0 and 9.1
The lists `rangefinder_hardware`, `opflow_hardware`, `baro_hardware`, the values of `inav_default_alt_sensor`, the weights and limits of the rangefinder and the flow, the `temp_sensor` command — unchanged. In 9.x (present in 9.1.0): `MS5525` in `pitot_hardware`; `pitot_lpf_milli_hz` 350 → 3000; the GPS check of the pitot with substitution of the virtual airspeed; `apa_pow`; the flow now corrects the estimate at its own interval between packets rather than at the estimator loop period.

### Place in the system
- **Receives:** the roll and pitch angles and the gyro rate from the attitude estimate; the Z altitude and the healthy-barometer flag, the GPS speed and the wind estimate from navigation (`inav-gps`, `inav-wing`); the UARTs and port functions from `inav-setup-scratch`.
- **Provides:** the AGL altitude — to the SURFACE mode, the landing detector and the autoland flare (`inav-geozones-landing`); the flow-based velocity and position — to POSHOLD without GPS; airspeed — to the `apa_pow` PID factor (`inav-mc-tuning`, `inav-setup-wing`), the OSD (`inav-osd-hd`) and logic (`inav-ipf`).
- **If you get it wrong here:** a sensor that is selected but not connected gives `HWFAIL` and an arming block (`inav-intro`); SURFACE with the rangefinder beyond its range lowers the aircraft by itself; an airspeed that reads high with `apa_pow` > 0 weakens the fixed-wing PIDs, and the error looks like a bad tune from `inav-setup-wing`.

## practice
The lab needs no hardware and no simulator: all the answers are derived from the formulas and rules of the theory. The sets of settings and the tables of readings are a **teaching example assembled by hand** from the 9.1.0 names and constants. You need a calculator with cosine and square root.

### Step 1. Rangefinder: is the reading accepted or not
A multirotor, the barometer is healthy. `rangefinder_hardware = VL53L1X`, `rangefinder_median_filter = OFF`, `inav_max_surface_altitude = 200`. Readings arrive every 40 ms, the reliability before the first row is r = 0.95, the AGL quality is HIGH.

| No. | Driver reply, cm | Roll, ° | Pitch, ° |
|---|---|---|---|
| 1 | 120 | 0 | 0 |
| 2 | 150 | 8 | 6 |
| 3 | 150 | 10 | 10 |
| 4 | 206 | 12 | 0 |
| 5 | 204 | 12 | 0 |
| 6 | −1 | 2 | 1 |
| 7 | 95 | −5 | 12 |
| 8 | −2 | 0 | 0 |

1. Find the cos θ threshold for this sensor.
2. For each row calculate cos θ and the altitude the way the code does, and decide: is the reading accepted or discarded, and at which step.
3. Calculate α and the reliability after each row. What is the AGL quality after the eighth?
4. How many discarded readings in a row (from r = 1) take the quality to LOW, and how many seconds is that? How many accepted readings in a row are needed from r = 0 (after a gap longer than 400 ms) to get HIGH?

### Step 2. Airspeed
1. MS4525, `pitot_scale = 1.0`, P − P₀ = 245 Pa. What speed does INAV show? What — at 61.25 Pa and at −245 Pa?
2. In calm air a wing flew a straight leg there and back, the average ground speed was 21.6 m/s, and the pitot showed 20.0 m/s all the time. What `pitot_scale` do you set?
3. `pitot_hardware = VIRTUAL`. Ground speed 18 m/s, nose heading 90°, level flight. Calculate the airspeed for three states of the wind estimator: (a) wind 5 m/s, vector direction 270°; (b) wind 6 m/s, direction 30°, the wing climbing at 2 m/s; (c) wind 6 m/s, direction 180°.
4. `fw_reference_airspeed = 1500`, `apa_pow = 120`. Find the P, D, FF factor and the I factor at an airspeed of 20 m/s and 10 m/s. What happens to the P factor at 6 m/s?

### Step 3. Flow calibration
An MSP sensor, packets every 100 ms (Δt = 100000 µs). A fragment of the 30-second calibration; before the first row the flow is valid.

| No. | Count X | Count Y | Gyro X, °/s | Gyro Y, °/s | Quality, % |
|---|---|---|---|---|---|
| 1 | 38 | 0 | 40 | 0 | 80 |
| 2 | −45 | 12 | −48 | 10 | 75 |
| 3 | 0 | 57 | 0 | 60 | 70 |
| 4 | 20 | −21 | 22 | −20 | 66 |
| 5 | 60 | 5 | 62 | 4 | 8 |
| 6 | −30 | −40 | −31 | −42 | 30 |
| 7 | 33 | 44 | 35 | 46 | 60 |

1. Which rows go into the sums? Calculate both sums and `opflow_scale` from these seven rows.
2. In 30 seconds 300 packets arrive. What must the average rocking rate be for the result to be saved if all packets are valid? If 60 % are valid?
3. The scale from item 1 is written. In flight: count X = 30 per 100 ms, the gyro on X shows 5 °/s, the rangefinder — 80 cm. What velocity does the estimator get on this axis?
4. A reverse check: the aircraft moves at 50 cm/s without rotation at an altitude of 80 cm. What count per 100 ms should arrive with `opflow_scale = 10.5`?

### Step 4. Three aircraft and three errors
For each aircraft check the proposed settings and find one error.

| Setting | A: an indoor micro, a “flow + lidar” MSP board, has a barometer, no GPS | B: a fixed wing, MS4525, barometer and GPS | C: a quadcopter with GPS, no barometer on the board |
|---|---|---|---|
| `baro_hardware` | AUTO | AUTO | AUTO |
| `rangefinder_hardware` | MSP | NONE | NONE |
| `opflow_hardware` | MSP | NONE | NONE |
| `pitot_hardware` | NONE | MS4525 | NONE |
| `inav_allow_dead_reckoning` | OFF | OFF | OFF |
| `inav_default_alt_sensor` | GPS | GPS | GPS |
| other | `inav_max_surface_altitude = 200`, `nav_max_terrain_follow_alt = 100` | `osd_airspeed_alarm_min = 12` (they want blinking below 12 m/s), `apa_pow = 0` | the ALTHOLD, POSHOLD, RTH modes on switches |

1. Name the error in each column and its consequence.
2. For aircraft B: what are the GPS and barometer weights and the overall correction factor if the altitudes differ by 14 m? And if you set `BARO` with the same difference? And with `BARO` and a difference of 3 m?
3. For aircraft C: what changes in the altitude estimate if, after fixing the error, you set `GPS_ONLY` instead of `GPS`?
4. Aircraft A after the fix: which navigation modes are available, and why can `inav_default_alt_sensor` be left alone?

### Moving to real hardware
The order, if you have the sensors. The propellers stay off until item 5.

1. Rangefinder: no `HWFAIL` in `status`; raise the aircraft above the floor against a tape measure to 50 and 100 cm — the Rangefinder distance OSD element shows the distance with an error of no more than 5 cm. Tilt the aircraft in place: at an angle greater than half the cone of the sensor logic operand 36 stops following the tape measure.
2. Flow: the calibration button, 30 seconds of rocking above a contrasting floor; `opflow_scale` changed and on a repeat differs by no more than 10 %.
3. Pitot: power up with the probe covered, wait for the zero to be taken — Air Speed shows 0–2 m/s. Blow into the tube: the speed rises. Swapped tubes cannot be found this way (there is an absolute value in the formula) — check the hoses by eye.
4. Temperature: `temp_sensor` shows the detected sensors; warm one with your fingers — its OSD element rises.
5. The first flight in SURFACE: above a level matte floor, ALTHOLD, throttle in the middle, `nav_max_terrain_follow_alt` no more than half of `inav_max_surface_altitude`. Keep a finger on the SURFACE switch: a loss of AGL means a descent.
6. Pitot in the air: in calm air fly a straight leg there and back, compare the average ground speed with the indicated airspeed, correct `pitot_scale`. Only after that enable `apa_pow`.

The criteria on hardware: the distance in the OSD matched the tape measure within 5 cm; two flow calibration results agreed within 10 %; after correcting `pitot_scale` the airspeed in calm air differs from the average ground speed by no more than 1 m/s.

Self-check: the lab is done when:
- step 1: the threshold is cos 13.5° = 0.9724; rows 1, 2, 5 and 7 are accepted with altitudes 120, 147, 199 and 92 cm; α = 0.0772; the reliability after the eighth row is 0.723 (±0.005), the quality is MID; to LOW — 14 readings (0.56 s), from zero to HIGH — 18 readings (0.72 s);
- step 2: 20.0 m/s, 10.0 m/s and again 20.0 m/s; `pitot_scale` = 1.08; the virtual airspeed is 23.0, 15.13 and 18.0 m/s (±0.05); the factors are 0.708 and 0.944 at 20 m/s, 1.627 and 1.084 at 10 m/s (±0.005); at 6 m/s — the 2.0 limit;
- step 3: rows 1–4 and 7 are in the sums; Σ flow 2255.7, Σ gyro 236.56, `opflow_scale` = 9.535 (±0.01); the average rate is above 12 °/s and above 20 °/s; the velocity on the axis is 36.9 cm/s (±0.3); the count is 37.6 (±0.2);
- step 4: the three errors from the reference are named; the weights are 1 and 0.6 with a factor of 1.25; with `BARO` and 14 m — a GPS weight of 0, a factor of 2; with `BARO` and 3 m — a GPS weight of 0.5, a factor of 1.33.

**Reference for the self-check.**

| No. | cos θ | Tilt, ° | Altitude per the code | Result | r after the row |
|---|---|---|---|---|---|
| 1 | 1.0000 | 0 | 120 | accepted | 0.954 |
| 2 | 0.9848 | 10.0 | 147 (147.7 with the fractional part dropped) | accepted | 0.957 |
| 3 | 0.9699 | 14.1 | −1 | discarded: the tilt is greater than 13.5° | 0.884 |
| 4 | 0.9781 | 12.0 | 201 | discarded by the estimator: greater than 200 | 0.815 |
| 5 | 0.9781 | 12.0 | 199 | accepted | 0.830 |
| 6 | 0.9992 | 2.2 | −1 | discarded: the driver is out of range | 0.766 |
| 7 | 0.9744 | 13.0 | 92 | accepted | 0.784 |
| 8 | 1.0000 | 0 | −1 | discarded: a driver failure, after 500 ms without replies — `HWFAIL` | 0.723 |

Step 3: row 5 makes the flow invalid (quality ≤ 10), row 6 does not bring it back (≥ 35 is needed), row 7 does. The velocity in item 3: 30 × 10 / 9.535 = 31.46 °/s, minus 5 — 26.46 °/s = 0.4618 rad/s, multiplied by 80 cm. Item 4: 50 / 80 = 0.625 rad/s = 35.81 °/s; 35.81 × 10.5 × 0.1 s.

Step 4. A: `inav_allow_dead_reckoning = OFF` — POSHOLD will not appear in the mode list, and the flow corrects only the velocity; `ON` is needed. B: `osd_airspeed_alarm_min = 12` — that is 0.12 m/s, the threshold is in cm/s, 1200 is needed. C: `baro_hardware = AUTO` on a board without a barometer — the `HWFAIL` flag, arming disabled; `NONE` is needed. Aircraft C with `GPS_ONLY`: the source is the same, but the barometer weight in the formula becomes 0 and the correction factor is 2 instead of 1, that is, GPS pulls the altitude twice as hard. Aircraft A: ALTHOLD, POSHOLD and SURFACE are available; the GPS altitude is never valid, so with any value of the setting the barometer is what works.

Typical wrong answers and their cause. Row 3 “accepted, both angles are less than 13.5°” — the total tilt has to be compared, cos θ = cos roll × cos pitch. Rows 4 and 5 judged the same — the limit is compared with the altitude after compensation, not with the driver reply. An altitude of 148 in row 2 — the code drops the fractional part, it does not round. In step 2 a scale of 1.166 — it was squared: `pitot_scale` multiplies the speed. A virtual airspeed of 13 m/s in item (a) — the direction of the wind vector was taken as “where it blows from”; the vector points to 270°, the nose to 90°, the wind is a headwind, and the speeds add up. 19.0 m/s in item (c) — the formula takes into account only the component along the nose, it does not see a crosswind. In step 3 a scale of 9.82 — rows 5 and 6 got into the sums; a scale of 0.95 — the factor 10⁶ / Δt was forgotten. A velocity of 43.9 cm/s — the body rotation was not subtracted.

## diagnostics
- **Symptom:** after selecting a sensor `status` has the `HWFAIL` flag, arming is disabled
  - Possible cause: the sensor is selected but not found or has not replied for longer than 500 ms; `baro_hardware = AUTO` or `pitot_hardware = AUTO` on a board without the sensor; the port function is not assigned for a serial rangefinder.
  - What to do: the value `NONE` for a missing sensor; the Rangefinder or Optic flow function on the right UART; for MSP — check that packets are arriving.
- **Symptom:** the SURFACE mode is not in the list
  - Possible cause: the platform is an airplane; the barometer or the rangefinder is not detected.
  - What to do: SURFACE exists only on a multirotor with both sensors.
- **Symptom:** in SURFACE the aircraft descends by itself, “(!SURFACE UNRELIABLE!)” in the OSD
  - Possible cause: the altitude is greater than `inav_max_surface_altitude`; the tilt is greater than half the cone (only 13.5° for the VL53L1X); the surface does not reflect; the target from the throttle stick is below 10 cm.
  - What to do: turn SURFACE off with the switch, lower `nav_max_terrain_follow_alt`, fly more smoothly or use a sensor with a wide cone.
  - Consequences: a descent of up to 2 m/s with the throttle at idle.
- **Symptom:** the rangefinder shows the distance in the OSD, but AGL does not use it
  - Possible cause: no healthy barometer; the reading after tilt compensation is greater than `inav_max_surface_altitude`; the reliability has not yet reached 0.75.
  - What to do: check logic operands 35 and 36; raise `inav_max_surface_altitude` to the real range of the sensor.
- **Symptom:** POSHOLD on the flow drifts or cannot be enabled
  - Possible cause: `inav_allow_dead_reckoning = OFF`; no rangefinder, or its reliability is below 0.33; the flow quality is below the threshold (a smooth floor, darkness); a wrong `align_opflow` or `opflow_scale`.
  - What to do: calibrate the scale by rocking; check the sign of the displacement in the `FLOW_RAW` debug mode from `docs/Blackbox.md`.
- **Symptom:** the flow calibration ran, but `opflow_scale` did not change
  - Possible cause: the sum of the body rates did not exceed 3600 — too little rocking, or the quality was below the threshold.
  - What to do: rock more vigorously, 20–40 °/s, above a contrasting surface.
- **Symptom:** arming is disabled after power-up, the `CAL` flag in `status` does not clear
  - Possible cause: the pitot zero is being taken; in wind the pressure spread is above the threshold, and the calibration restarts.
  - What to do: cover the pitot probe at power-up.
- **Symptom:** the airspeed on the ground is not zero, or in flight it disagrees with the ground speed
  - Possible cause: the zero was taken in wind; a wrong `pitot_scale`; a leaking hose.
  - What to do: reboot with the probe covered; a there-and-back pass in calm air and a scale correction.
  - Consequences: with `apa_pow` > 0 a speed error directly changes the PID gains.
- **Symptom:** the Multi Function Status OSD element shows the warning “PITOT FAIL” (without this element in the layout there is no indication: the speed on the screen simply becomes the computed one)
  - Possible cause: the reading went outside 30–200 % of the virtual airspeed — a blocked tube, a hose that came off; or the wind estimate is far from the truth.
  - What to do: land; INAV is already computing the speed from GPS and wind.
- **Symptom:** a temperature element blinks at a normal temperature
  - Possible cause: the threshold was written in degrees, not in tenths: `60` is 6.0 °C.
  - What to do: `temp_sensor` with the thresholds ×10.
- **Symptom:** without a barometer the altitude in ALTHOLD wanders by meters
  - Possible cause: that is the accuracy of the GPS altitude, and there is no other source.
  - What to do: install a barometer; changing `inav_default_alt_sensor` will not add a source.

## checklist
- Every missing sensor is set to `NONE`, there is no `HWFAIL` flag in `status`
- Serial sensors have a port function assigned, MSP sensors — the MSP function
- `inav_max_surface_altitude` is no greater than the real range of the rangefinder
- `nav_max_terrain_follow_alt` is noticeably smaller than `inav_max_surface_altitude`
- The barometer is healthy if you need SURFACE, AGL or the flow
- `opflow_scale` was obtained by calibration, `align_opflow` is checked
- For POSHOLD without GPS `inav_allow_dead_reckoning` is enabled
- The pitot zero was taken with the probe covered, `pitot_scale` is checked with a pass in calm air
- The OSD layout has the Multi Function Status element — otherwise a pitot failure (“PITOT FAIL”) and the substitution of the computed speed will go unnoticed
- `apa_pow` is enabled only after the pitot check, `fw_reference_airspeed` equals the cruise speed
- The temperature thresholds are written in tenths of a degree, the airspeed thresholds — in cm/s
- The switch that turns SURFACE off is tested on the ground

## references
- INAV 9.1.0 — sensors/rangefinder.c | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/sensors/rangefinder.c | primary | A
- INAV 9.1.0 — navigation_pos_estimator_agl.c | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/navigation/navigation_pos_estimator_agl.c | primary | A
- INAV 9.1.0 — navigation_pos_estimator_flow.c | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/navigation/navigation_pos_estimator_flow.c | primary | A
- INAV 9.1.0 — navigation_pos_estimator.c | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/navigation/navigation_pos_estimator.c | primary | A
- INAV 9.1.0 — sensors/opflow.c | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/sensors/opflow.c | primary | A
- INAV 9.1.0 — sensors/pitotmeter.c | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/sensors/pitotmeter.c | primary | A
- INAV 9.1.0 — sensors/temperature.c | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/sensors/temperature.c | primary | A
- INAV 9.1.0 — settings.yaml | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/settings.yaml | primary | A
- INAV 9.1.0 — fc_msp_box.c (mode availability) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/fc_msp_box.c | primary | A
- INAV docs — Rangefinder | https://github.com/iNavFlight/inav/blob/9.1.0/docs/Rangefinder.md | primary | A
- INAV docs — Temperature sensors | https://github.com/iNavFlight/inav/blob/9.1.0/docs/Temperature%20sensors.md | primary | A
- INAV Configurator 9 — tabs/calibration.js | https://github.com/iNavFlight/inav-configurator/blob/master/tabs/calibration.js | primary | B

## notes
The firmware was not built or run: all the behavior was derived by reading the INAV 9.1.0 source and comparing it with 8.0.1; the numbers of the practice were computed with a script using the formulas of the code. Not verified in flight: the accuracy of a flow-based hold, the behavior of SURFACE over real terrain, arming without GPS with the flow (the conclusion is drawn from the conditions of `navigationIsBlockingArming()` and `updateHomePosition()`), the quality threshold of particular sensors. The port baud rate and the format of the count units of “flow + lidar” boards come from the board documentation; they are not in the firmware. Discrepancies between the documentation and the 9.1.0 code: the description of `rangefinder_median_filter` speaks of three points (five in the code); `docs/Rangefinder.md` gives ranges of 75 cm for the VL53L0X, 400 cm for the VL53L1X and 645 cm for the US42 (250, 300 and 400 in the drivers) and calls CRUISE compatible with SURFACE (in the code the SURFACE request is handled on entering ALTHOLD and POSHOLD); the description of `apa_pow` gives a gain range of 30–150 % (0.3…2.0 for P, D, FF and 0.3…1.5 for I in the code); the descriptions of the `inav_w_z_surface_*` weights say “when the Surface mode is enabled” (the AGL estimate is always computed). In the CLI the alignment of the flow sensor is set with the setting `align_opflow`; `opflow_align` is the name of the field in the source.
