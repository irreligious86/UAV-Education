---
id: inav-setup-scratch
title: "INAV from scratch: a GPS quadcopter"
level: L2
readingTime: 50 min
firmware: INAV 9.1 (checked against 9.1.0)
status: published
added: 2026-11-10
tags:
  - INAV
  - setup
  - SITL
  - failsafe
  - calibration
related:
  - inav-intro
  - inav-gps
  - inav-missions
  - link-elrs
  - f-motors-esc
  - bf-modes-osd
next:
  - inav-missions
source: content/inav/inav-setup-scratch.md
source_hash: 5ba46e457bdc
---

## summary
One GPS quadcopter goes all the way from a blank board to a logged hover, POSHOLD and RTH — in an order of 17 setup steps. The other INAV modules explain individual parts: what RTH is, how the estimator works, how to write missions. Here the whole chain is assembled, including the steps the course did not have before: bind and the channel map, the motor protocol, motor order and direction, ESC calibration, voltage and current calibration (`vbat_scale`, `current_meter_scale`, `current_meter_offset`), failsafe with the RTH procedure, ground checks of navigation and the first flight with abort criteria. The main path is INAV SITL: everything that concerns the configuration you do without hardware. The steps that require real hardware are laid out separately for the bench and for the field. The lab: a `diff all` from SITL and from the real aircraft, the battery calibration calculation, a hover log and a recorded failsafe → RTH.

## theory
### The step map: what, where and with what
{{diagram:inav-setup-flow|The 17 steps go strictly in order: everything that concerns the configuration is checked in SITL; bind, motors, ESCs and the battery — only on the bench without props; the props go on at step 15, not earlier.}}

| # | Step | Where | INAV: tab / CLI | In detail |
|---|---|---|---|---|
| 1 | Firmware, backup of the old config | SITL, bench | Firmware Flasher, `diff all` | inav-intro |
| 2 | Platform, mixer | SITL | Mixer, `platform_type`, `mmix` | inav-intro |
| 3 | UART ports | SITL | Ports, `serial` | here |
| 4 | Receiver, bind | bench | Receiver, `receiver_type`, `serialrx_provider` | link-elrs |
| 5 | Channel map, endpoints, centers | SITL + bench | `map`, `rxrange`, `min_check`/`max_check` | here |
| 6 | Motor protocol | bench | Outputs, `motor_pwm_protocol` | f-motors-esc |
| 7 | Motor order and direction | bench, no props | Outputs (motor test), Motor Mixer Wizard | here |
| 8 | ESC calibration (PWM only) | bench, no props | Outputs, the Master slider | here |
| 9 | Accelerometer, compass | bench, field | Status / Calibration, `align_mag` | inav-gps |
| 10 | Voltage and current | bench + flight | `vbat_scale`, `current_meter_scale`, `current_meter_offset` | here |
| 11 | Modes, arming, arming blocks | SITL | Modes, `aux`, `status` | inav-intro |
| 12 | Failsafe: set up and test | SITL + bench + field | `failsafe_procedure = RTH` | here, bf-failsafe |
| 13 | OSD and video | bench | OSD, `osd_video_system` | bf-modes-osd, link-vtx |
| 14 | GPS, home, RTH | SITL + field | `nav_rth_*` | inav-gps |
| 15 | Preflight check, first hover | field | — | here |
| 16 | First tuning | field | `nav_mc_hover_thr`, filters, EZ Tune | here, `inav-mc-tuning`, bf-filters |
| 17 | Log, `diff all`, restore | SITL + field | Blackbox, CLI | here |

### What INAV SITL can and cannot do
SITL is the same INAV firmware compiled with an ordinary gcc for a PC (`cmake -DSITL=ON`). You can run the build by hand or from the SITL tab in the Configurator. The sensors (gyro, accelerometer, baro, compass, GPS) work in FAKE mode: the simulator supplies their data. The UARTs are replaced with TCP ports: UART1 = 5760, UART2 = 5761 and so on. The Configurator connects by selecting “SITL” or over TCP to `localhost:5760`.

Without a simulator SITL runs in “Configurator only” mode: the mixer, ports, modes, failsafe and `diff all` are configured as on a real board, but the aircraft does not fly. Flight comes only from an external simulator: RealFlight 9.5S / Evolution or X-Plane. For a quadcopter only RealFlight really works (paid, Windows): the INAV-X-Plane-HITL plugin supports only the Airplane platform (checked on 8.0.1; the 9.1 documentation also names the INAV-X-Plane-XITL plugin — its multirotor support has not been checked). What SITL cannot do in principle:
- **DShot.** SITL has no `USE_DSHOT`, and `config.c` silently changes DSHOT300 to MULTISHOT at load — this is verified below, in step 6.
- **Bind, motor direction, ESCs, the voltage divider, the current shunt, the compass on the real airframe.** All of this is the physics of a particular aircraft, and SITL does not have it.
- **Analog OSD.** There is only MSP DisplayPort through INAV-Sim-OSD.

### Battery calibration: the formulas from the source
`src/main/sensors/battery.c` (INAV 9.1.0; the formulas are the same in 8.0.1) computes:
- voltage: `V = ADC · vbat_scale · 3300 / (4095 · 1000)`, that is, the reading is **directly proportional** to `vbat_scale`. Hence **new = old × V_multimeter / V_INAV**;
- current: `I = (U_sensor − offset) / scale`. `current_meter_scale` is set in 0.1 mV/A (400 = 40 mV/A). The reading is **inversely proportional** to scale, so **new = old × mAh_INAV / mAh_charger** — this is the formula from docs/Battery.md;
- offset: in the code `offset × 100` µV is subtracted from the sensor voltage, so the actual unit of `current_meter_offset` is 0.1 mV, although Settings.md says “millivolts”. In practice it is easier to think in current: the offset removes `offset / scale` amps from the reading. The correction: **new_offset = old_offset + (I_INAV − I_ammeter) × scale**.

The order: first scale from mAh (a flight that uses more than 50 % of the capacity), then offset from the idle current, and a check flight. The current in flight is 20–40 times the idle current, so an offset error hardly affects the scale calculation.

### Failsafe in INAV
Failsafe triggers if frames are lost on any of the roll, pitch, throttle or yaw channels, if a channel goes outside `rx_min_usec`…`rx_max_usec` (885…2115) or if the FAILSAFE mode is activated. It triggers 200 ms + `failsafe_delay` × 100 ms after valid frames stop: 0.7 s at the default `failsafe_delay` = 5 (plus the receiver's own signal timeout: 100 ms for serial receivers, 200 ms for the MSP receiver), and then the procedure `failsafe_procedure` is executed: LAND (default), DROP, RTH or NONE. For a GPS quadcopter choose RTH. Four things are important to know:
- **RTH requires GPS, a compass and a baro** (that is what docs/Failsafe.md 9.1 says; for heading without a compass see inav-intro). If one of the sensors is missing at the moment failsafe triggers, an emergency landing at `nav_emerg_landing_speed` (500 cm/s) starts immediately.
- **`failsafe_throttle_low_delay`** (0 = off): if the throttle has been low for a long time, the aircraft is considered to be on the ground and is simply disarmed.
- **`failsafe_min_distance`** with `failsafe_min_distance_procedure` (DROP by default): close to home a different procedure applies. Leave it at 0 until you understand what it is for.
- **Leaving failsafe.** With `failsafe_stick_threshold` = 50 RTH is not interrupted until you move a stick by more than 50 µs. That way a link at the edge of coverage does not jerk the aircraft back and forth.

On link loss the receiver must tell the flight controller about it: stop sending channels or set the failsafe flag. ELRS over CRSF stops sending channels. On SBUS INAV reads the failsafe flag in the frame (`rx/sbus_channels.c`), so both “no pulses” and holding the last values with the flag will do. A PWM/PPM receiver is set to “no pulses”, and you check that it does not silently hold the last values (in detail — the modules link-elrs and bf-failsafe).

### Place in the system

- **Receives:** ready decisions: the platform and the arming blocks (`inav-intro`), the receiver and bind (`link-elrs`), the motor protocol (`f-motors-esc`), the RTH settings (`inav-gps`); the multimeter readings and the charger's mAh.
- **Provides:** an assembled aircraft and the first hover log — to PID, filter and navigation tuning (`inav-mc-tuning`); calibrated voltage and current — to the OSD and the IPF rules (`inav-ipf`); `nav_mc_hover_thr` — to the altitude controller (`inav-gps`); a tested failsafe with RTH — to missions (`inav-missions`); a `diff all` for restoring.
- **If you get it wrong here:** on link loss the receiver silently holds the last values (PWM/PPM without “no pulses”, SBUS without the failsafe flag) → failsafe does not trigger and RTH will not start (`link-elrs`, `bf-failsafe`). At the moment of failsafe there is no GPS, compass or baro → instead of RTH an emergency landing starts immediately wherever the aircraft is; the sensors are checked per `inav-gps`.

## practice
### Step 1. Build and run SITL, save the initial config
The fastest way is the SITL tab in Configurator 9.1: Start, then Connect through “SITL”. To see what happens inside, build SITL yourself: with gcc 13.3 the 8.0.1 build took 19 seconds.

The commands and the output below were captured on 8.0.1; in 9.1.0 only the tag and the file name change (`-b 9.1.0`, `./inav_9.1.0_SITL`), and the first line of the output is `INAV 9.1.0 SITL`. The 9.1 documentation recommends gcc 13 or newer.

```bash
git clone --depth 1 -b 8.0.1 https://github.com/iNavFlight/inav.git && cd inav
mkdir build_SITL && cd build_SITL && cmake -GNinja -DSITL=ON .. && ninja
./inav_8.0.1_SITL          # in a separate folder: eeprom.bin will appear there
```

```text
INAV 8.0.1 SITL (ae47bcba)
[SIM] No interface specified. Configurator only.
[EEPROM] Unable to load eeprom.bin
[SOCKET] Bind TCP 0.0.0.0:5760 to UART1
[SOCKET] Unable to bind socket
```

The second bind line is UART2 (port 5761): another process had taken it, in my case Betaflight SITL. UART1 is enough for the Configurator. Before any changes save a `diff all` — on a real board that is the backup of the old config before flashing. `status` on a clean SITL shows `GYRO=FAKE, ACC=FAKE, MAG=FAKE, BARO=FAKE` and the line `Arming disabled flags: CAL ACC RX CLI`.

### Step 2–3. Mixer and ports
The Quad X preset on the Mixer tab is four `mmix` lines. The Configurator takes them from `js/model.js`, and the CLI prints exactly this:

```text
mmix 0  1.000 -1.000  1.000 -1.000      # 1: rear right, CW
mmix 1  1.000 -1.000 -1.000  1.000      # 2: front right, CCW
mmix 2  1.000  1.000  1.000  1.000      # 3: rear left, CCW
mmix 3  1.000  1.000 -1.000 -1.000      # 4: front left, CW
```

The columns: throttle, roll, pitch, yaw. The sign of yaw shows the direction of rotation: on a “yaw clockwise” command motor 1 has to slow down (−1), so it spins clockwise (CW). This is the “props in” layout; for “props out” set `motor_direction_inverted = ON`.

The ports are set with the command `serial <n> <functions> <msp> <gps> <telem> <periph>`, and the functions are a bitmask: MSP = 1, GPS = 2, RX_SERIAL = 64, BLACKBOX = 128, MSP_OSD (DisplayPort) = 33554432. In SITL I enabled MSP on UART3 (`serial 2 1 115200 115200 0 115200`), and after a reboot the port `Bind TCP 0.0.0.0:5762 to UART3` appeared. On a real board it is usually this: `serial 1 64 …` — the receiver on UART2, `serial 2 2 …` — GPS on UART3. The other bits, the rules for combining two functions on one UART and the ports for telemetry and a ground station are in `inav-telemetry-gcs`.

### Step 4–5. Receiver and channel map — a check in SITL
In SITL the receiver is connected through `receiver_type = MSP`. A Python script sends `MSP_SET_RAW_RC` (code 200) to port 5762 50 times a second in AETR order: roll 1500, pitch 1500, throttle 1000, yaw 1500, AUX1 1000. It reads back `MSP_RC` (105) — the channels already after `map`, in INAV's internal order: roll, pitch, yaw, throttle.

The output of both blocks of this step was captured on 8.0.1; in 9.1.0 the MSP codes 200 and 105 and the flag names (`CAL`, `NAV`, `ACC`, `RX`, `CLI`, `THR`) are the same.

```text
### 1. no RC source
Arming disabled flags: CAL NAV ACC RX CLI
### 2. MSP RC at 50 Hz
Arming disabled flags: CAL NAV ACC CLI
MSP_RC ch1-8: (1500, 1500, 1500, 1000, 1000, 1000, 1500, 1500)
### 3. RC stopped 2 s ago
Arming disabled flags: CAL NAV ACC RX CLI
```

The `RX` flag disappears while frames are arriving and comes back about 0.9 s after they stop (MSP receiver: 200 ms signal timeout + 200 ms + `failsafe_delay` × 100 ms) — this is the same logic by which failsafe triggers. With `map AETR` the throttle (the fourth value) is 1000, as intended. If you make a mistake and set `map TAER`, you get:

```text
MSP_RC ch1-8: (1500, 1000, 1500, 1500, 1000, 1000, 1500, 1500)
```

The throttle is now 1500 and the pitch is 1000. Such an aircraft will not arm (the `THR` flag), and if you bypass the block, it will shoot off. For ELRS/CRSF the right map is AETR, which is the default.

### Step 6. Motor protocol: what SITL cannot do
After `set motor_pwm_protocol = DSHOT300` and `save` SITL answers like this (the output was captured on 8.0.1; in 9.1.0 the condition in `fc/config.c` is the same):

```text
motor_pwm_protocol = MULTISHOT
```

That is `#if !defined(USE_DSHOT)` in `fc/config.c`. The conclusion: the protocol, the motor order and direction and the ESC calibration are checked only on the bench (the hardware section below).

### Step 10. Battery calibration — the calculation
This is an example from a real 4S 1500 mAh pack (the numbers are repeated in the hardware section). A multimeter on the balance lead shows 16.42 V, `status` in INAV — 15.95 V with `vbat_scale` = 1100. After the flight INAV counted 1120 mAh, and the charger put back 1030 mAh. The idle current (FC, receiver, VTX) on the ammeter of a bench power supply is 0.45 A, and INAV shows 0.69 A.

```python
old_vs, v_meter, v_inav = 1100, 16.42, 15.95
new_vs = round(old_vs * v_meter / v_inav)                  # V ∝ scale
old_cs, mah_inav, mah_charger = 400, 1120, 1030
new_cs = round(old_cs * mah_inav / mah_charger)            # I ∝ 1/scale
old_off, i_inav, i_meter = 0, 0.69, 0.45
new_off = round(old_off + (i_inav - i_meter) * new_cs)     # offset/scale = amps
```

```text
vbat_scale 1100 -> 1132; after: 16.414 V, error 1.5 mV/cell
current_meter_scale 400 -> 435 (mAh error before +8.7 %)
current_meter_offset 0 -> 104 (removes 0.24 A)
```

{{diagram:chart-inav-vbat-cal|With vbat_scale 1100 the voltage reads 90–120 mV per cell low: the OSD will show “time to land” later than it really is. After 1132 the error is 1.5 mV per cell over the whole 4S range, because the divider error is proportional to the voltage and is corrected with a single coefficient.}}

### Step 11–12, 14. Modes, failsafe, RTH — the config and a check in SITL
```text
aux 0 0 0 1700 2100        # ARM: AUX1 high
aux 1 1 1 900 2100         # ANGLE: always on, on AUX2
aux 2 11 1 1300 1700       # NAV POSHOLD: AUX2 in the middle
aux 3 10 1 1700 2100       # NAV RTH: AUX2 high
set failsafe_procedure = RTH
set nav_rth_altitude = 3000            # 30 m; AT_LEAST, climb_first ON, landing ALWAYS are already the defaults
set bat_cells = 4
set battery_capacity = 1500
set battery_capacity_warning = 450
set battery_capacity_critical = 300
set vbat_scale = 1132
set current_meter_scale = 435
set current_meter_offset = 104
set nav_mc_hover_thr = 1380
```

The second number in `aux` is the permanent id of the mode, not its ordinal number: ARM = 0, ANGLE = 1, NAV ALTHOLD = 3, NAV RTH = 10, NAV POSHOLD = 11, FAILSAFE = 27 (the table in `fc_msp_box.c`). Without a simulator SITL does not arm: the flags `CAL NAV ACC` stay in `status`, that is, the sensors are calibrating, there is no GPS fix, the accelerometer is not calibrated. So the full test “radio off → RTH → landing” passes in SITL only with RealFlight. In that case fly 100 m away before RTH, stop the RC transmission and measure the distance of the landing point from home on the Configurator map. Without RealFlight you check the chain in SITL up to the trigger: losing RC gives the `RX` flag (step 4–5), and the RTH procedure is in the config.

### Step 17. diff all and a restore check
`diff all` after the setup (a fragment; the output was captured on 8.0.1, and in 9.1.0 these names and values are the same):

```text
# master
set acc_hardware = FAKE
set mag_hardware = FAKE
set baro_hardware = FAKE
set receiver_type = MSP
set motor_pwm_protocol = MULTISHOT
set failsafe_procedure = RTH
set vbat_scale = 1132
set current_meter_scale = 435
set current_meter_offset = 104
set gps_provider = FAKE
set nav_rth_altitude = 3000
```

The backup check: I deleted `eeprom.bin`, pasted all 56 command lines of the diff into the CLI (from `batch start` to `save`) and took a `diff all` again. All the `set`, `aux`, `mmix` and `serial` lines matched. A backup that has never been restored is not a backup yet. Important: **do not move a SITL diff to a real board as a whole**. The lines `*_hardware = FAKE`, `receiver_type = MSP`, `gps_provider = FAKE` and the `serial` lines for TCP are needed only in SITL. A real aircraft gets its own diff.

### Moving to real hardware
Safety: the props stay off until the “First hover” step. Apply power for the first time through a smoke stopper or a bench supply limited to 1–2 A. The aircraft lies on the bench, and nobody is in front of it.

**1. Firmware.** Save the `diff all` of the old firmware to a file. In Firmware Flasher select the target of your board and do a Full chip erase. The Configurator must match the firmware by major version (for 9.1 — Configurator 9.x). If the board ran INAV 8.x, the migration procedure and the rename table are in inav-intro (“Moving from 8.0 to 9.1”). After flashing — the Quad X mixer (Load and apply) and `align_board_*` if the board is rotated.

**2. Receiver and channels.** ELRS bind: a binding phrase or bind mode, as in link-elrs. Then `receiver_type = SERIAL`, `serialrx_provider = CRSF`, and the RX_SERIAL function (64) on the receiver's UART. On the Receiver tab each stick moves its own bar. The norms:
| Position | Norm | If not |
|---|---|---|
| Throttle low | < `min_check` (1100); on ELRS usually about 988 | the endpoints (limits) on the radio |
| Throttle high | > `max_check` (1900) | the endpoints on the radio |
| Roll, pitch, yaw center | 1500 ± 5 | subtrim on the radio, trims at 0 |
| AUX1 (ARM) | two positions: < 1300 and > 1700 | the radio mixer |

**3. Protocol and motors.** For BLHeli_S, BLHeli_32 and AM32: `motor_pwm_protocol = DSHOT300`, `throttle_idle` = 8 % (the 9.1 default, unchanged since 8.0; 15 % in 7.1; for a 5" 5–8 % is usually enough). PWM ESCs: STANDARD or ONESHOT125 plus calibration (item 4). The test: connect the battery, Outputs → enable the motor test, raise each motor in turn to ~1100. The motor that responds must be in the place with the same number on the Quad X diagram: 1 — rear right CW, 2 — front right CCW, 3 — rear left CCW, 4 — front left CW. Watch the rotation with a strip of tape on the bell. A wrong order is fixed by the Motor Mixer Wizard on the Mixer tab: you click the position of each motor that responds. A wrong direction — reverse it in the ESC configurator or swap two phase wires.

**4. ESC calibration (PWM/OneShot only).** Props off, battery disconnected. Outputs → enable the test, the Master slider to maximum (2000). Connect the battery, wait for the maximum tone, then the Master slider to minimum (1000), wait for the confirmation tone, disconnect the battery. After that all the motors must start moving at the same time, and the spread at ~1050 is no more than one or two ticks. DShot ESCs need no calibration: the command is digital.

**5. Sensors.** Accelerometer — 6 positions on a level table. Compass: outdoors, away from a car and rebar, the Calibrate Compass button, `mag_calibration_time` = 30 s. Rotate the aircraft around all axes. The declination is taken from GPS (`inav_auto_mag_decl = ON`). GPS: in 9.1 Galileo and BeiDou are enabled by default (`gps_ublox_use_galileo`, `gps_ublox_use_beidou` = ON; OFF before 9.1), the rate `gps_ublox_nav_hz` = 8 Hz (10 before 9.1); on the GPS tab of Configurator 9.1 select the preset for your module (M8, M9, M10) or Auto-detect GPS Type. Then the ground check of heading, home and altitude from inav-intro (step 3b): the heading within ±10° at the four cardinal points, the distance to home within ±2 m over 20 m.

**6. Battery.** A voltmeter on the balance lead → `vbat_scale` by the formula, tolerance 50 mV per cell. The idle current on the ammeter of a bench supply → `current_meter_offset`. A flight that uses more than 50 % of the capacity → charge → `current_meter_scale`. A check flight: the difference between INAV's mAh and the charger's is less than 5 %. Then `bat_cells`, `battery_capacity`, warning and critical — 30 % and 20 % of the capacity.

**7. Failsafe on the bench.** Props off, battery connected, radio on. Turn the radio off: on the Receiver tab the channels freeze, the `RX` flag appears in `status`, and the OSD shows a failsafe warning. Turn the radio on — the flag clears. There is no need to arm on the bench for this test; the RTH procedure is tested in the field.

**8. OSD and video.** Analog: `osd_video_system = AUTO` or PAL. HD: the MSP_OSD function (DisplayPort, 115200) on the UART of the air unit, and `osd_video_system` by system: HDZero — `HDZERO` (a 50×18 grid); Walksnail Avatar — `AVATAR` (53×20); DJI O4 and Goggles 2/3/N3/Integra on firmware with the INAV font — `DJI_NATIVE` (53×20), with the OSD type “INAV” in the goggles menu; DJI O3 on stock firmware — `BFHDCOMPAT` (53×20, the Betaflight font: some symbols will be “?”, enable the HD canvas in the goggles); old Air Unit/Vista with V1/V2 goggles on WTFOS — `DJIWTF` (60×22). A value for another system gives a shifted or empty OSD. If an O4 on old firmware does not see the arm state — update the goggles or `set enable_broken_o4_workaround = ON`. The values and grids are the same in 9.1.0 and 8.0.1; 9.1 only removed the automatic HDZero 30×16 sub-mode. The minimum set of elements: voltage, mAh, satellites, the distance and arrow to home, the flight mode, LQ/RSSI. In detail — bf-modes-osd and link-vtx.

**9. Preflight check and first hover (the props go on here).** Check the props for direction of rotation. At the field: a 3D fix, at least 10 satellites (`gps_min_sats` = 6 is the minimum for a fix, not for navigation), HDOP ≤ 2, home recorded. Blackbox on. Arm in ANGLE, hover at 1–2 m for 60 s. Abort and land if:
- the aircraft shakes or oscillates in the hover;
- with the sticks released it drifts faster than 1 m/s in calm air (trim the accelerometer);
- the hover throttle is above 60 %;
- after 60 s any motor is hot.

Take the hover throttle from the OSD or the log and put it into `nav_mc_hover_thr` (1380 in the example). Otherwise ALTHOLD sags when it is enabled.

**10. POSHOLD and RTH.** At 5–10 m switch to POSHOLD: in calm air the aircraft holds the point within ±1–2 m. “Toilet bowling” is a sign of a compass problem: go back to ANGLE and land. RTH first from the switch at 30–50 m, then from 100 m at an altitude of 20 m: the aircraft climbs to `nav_rth_altitude` (30 m), flies home and lands. Measure the distance of the landing point from home with a tape measure or from the last point of the log. Then the failsafe test: at 50–100 m turn the radio off. RTH must start after about 0.7–0.8 s. Turn the radio on and move a stick — control comes back.

**11. First tuning.** For the first flights the INAV 9.1 defaults are enough (the same as in 8.x): `gyro_main_lpf_hz` = 60, the dynamic notch (`dynamic_gyro_notch_enabled = ON`). Enable the RPM filter (`rpm_gyro_filter_enabled`) only with working ESC RPM telemetry. INAV has no bidirectional DShot: DSHOT300 does not return RPM; it comes over a separate ESC telemetry wire to the RX of a free UART with function 262144 (ESC telemetry), and `motor_poles` (14) must match the motor. The check before enabling the filter: `status` in the CLI prints the line `ESC Temperature(s)` and the temperature of every ESC (the line appears as soon as the ESC sensor is enabled; telemetry is arriving if the temperatures are non-zero and rise after the motors have run), and the OSD element “Motor RPM from ESC telemetry” changes together with the throttle. `feature RPM_FILTERS` is in the `feature` list, but in 9.1.0 the code does not read this bit — enabling it is pointless. The starting PIDs of 9.1.0, which you will see in `diff all` as missing lines (they are the defaults): `mc_p/i/d/cd_roll` and `_pitch` = 40/30/23/60, yaw 85/45/0/60, level `mc_p/i/d_level` = 20/15/75, `max_angle_inclination_rll/_pit` = 450 (45°). The rates are in tens of °/s: `roll_rate = 20` is 200 °/s, not 20; `rc_expo` = 70. The quick way to tune is EZ Tune (`ez_enabled = ON`), but enabling it already changes the tune: with untouched sliders the rate becomes 600 °/s instead of 200, roll I — 75 instead of 30, the gyro cutoff — 110 Hz instead of 60, and the Smith predictor is enabled. Before enabling it set `ez_filter_hz` for your size (7 inches — 90, 10 — 75; never more than 255) and `ez_rate` (at 0 the rate is 300 °/s — EZ Tune does not go lower); the formulas of each slider are in `inav-mc-tuning`. Touch the PIDs after analyzing Blackbox: the numbers and the INAV tuning order are there as well, the theory of filters and PIDs is in bf-filters and bf-pid.

**12. Backup.** CLI → `diff all` → save to a file with the date and the version. Save the Blackbox log of the first hover next to it.

Self-check: the lab is done when:
- **SITL**: SITL 9.1 is built or started (the output in the module was captured on 8.0.1). `diff all` contains Quad X (4 `mmix` lines), `aux` for ARM, ANGLE, POSHOLD and RTH, `failsafe_procedure = RTH` and the calculated `vbat_scale`, `current_meter_scale`, `current_meter_offset`. The `RX` flag appears when RC stops: your CLI log is saved and repeats blocks 1–3 of step 4–5. Restoring the diff from a file is verified: the `set`, `aux`, `mmix` and `serial` lines of the second `diff all` matched the original ones. If you have RealFlight — RTH from 100 m lands no farther than 3 m from home.
- **Hardware**: the channel table is filled in, the motor order and direction match Quad X. The voltage error is less than 50 mV per cell, INAV's mAh is within 5 % of the charger's. A Blackbox log of a 60-second hover is recorded, and `nav_mc_hover_thr` is taken from it. RTH from 100 m lands no farther than 5 m from home. Failsafe → RTH is recorded in the log or on OSD video. The `diff all` from the real aircraft is saved next to the log.

**Reference for the self-check.** The SITL part is right if `MSP_RC` with `map AETR` shows a throttle (the fourth value) of 1000, the `RX` flag disappears while frames are arriving and comes back about 0.9 s after they stop (MSP receiver: 200 ms signal timeout + 200 ms + `failsafe_delay` × 100 ms), and the battery calculation on the example data gives 1132, 435 and 104. Throttle 1500 and pitch 1000 in `MSP_RC` — `map TAER` is set. `current_meter_scale` came out below 400 although INAV counted more than the charger — the fraction is inverted: the current is inversely proportional to scale. `motor_pwm_protocol = MULTISHOT` after setting DSHOT300 in SITL is not an error in your config: SITL has no DShot. If a `diff all` taken for a real board still has `*_hardware = FAKE` or `receiver_type = MSP` — that is a SITL diff, and it is not moved to a board.

## diagnostics
- **Symptom:** SITL prints `[SOCKET] Unable to bind socket`
  - Possible cause: port 5760/5761 is taken by another SITL (INAV or Betaflight) or by an old process.
  - What to do: close the process; the Configurator connects to UART1, so an error on UART2 does not matter.
- **Symptom:** after `save` MULTISHOT is set instead of DSHOT
  - Possible cause: this is SITL or a target without `USE_DSHOT`; `config.c` replaces the protocol.
  - What to do: in SITL this is normal; on a real board check the target and the motor output.
- **Symptom:** it does not arm, `status` has the `RX` flag
  - Possible cause: no receiver frames — the wrong UART, `serialrx_provider`, no bind.
  - What to do: the Receiver tab, Ports, repeat the bind.
  - In the log: the flag clears as soon as frames arrive (step 4–5).
- **Symptom:** in Receiver the throttle moves a different channel, the aircraft does not arm with the `THR` flag
  - Possible cause: the wrong `map` (TAER instead of AETR).
  - What to do: `map AETR` for CRSF, check against the Receiver bars.
- **Symptom:** on the first arm the aircraft flips over or spins in place
  - Possible cause: the motors are in the wrong order or spin the wrong way for Quad X.
  - What to do: remove the props, motor test, Motor Mixer Wizard, reverse in the ESC.
  - Consequences: broken props and frames; this is caught on the bench in 5 minutes.
- **Symptom:** the OSD shows “battery empty” much earlier or later than it really is
  - Possible cause: `vbat_scale` or `current_meter_scale` is not calibrated; scale was corrected the wrong way.
  - What to do: voltage — old × V_multimeter / V_INAV; current — old × mAh_INAV / mAh_charger.
- **Symptom:** the idle current in the OSD is 0.3–1 A with the motors off instead of the real value
  - Possible cause: `current_meter_offset` is not set.
  - What to do: new = old + (I_INAV − I_ammeter) × scale, recheck after changing scale.
- **Symptom:** when the radio is turned off the aircraft lands on the spot instead of RTH
  - Possible cause: `failsafe_procedure` = LAND (default), no GPS fix or compass, `failsafe_min_distance` applied, or the aircraft is closer than `nav_min_rth_distance` (5 m).
  - What to do: check the procedure and the sensors, repeat the test farther than 50 m.
- **Symptom:** when ALTHOLD or POSHOLD is enabled the aircraft sags or jumps
  - Possible cause: `nav_mc_hover_thr` (1300 by default) is far from the real hover throttle.
  - What to do: take the hover throttle from the Blackbox log of the first hover.

## checklist
- SITL is running, the Configurator is connected, the initial `diff all` is saved
- Quad X, ports, receiver, `map AETR` are checked (the `RX` flag behaves as expected)
- The protocol, the motor order and direction are checked on the bench without props; PWM ESCs are calibrated
- `vbat_scale`, `current_meter_scale`, `current_meter_offset` are calculated with the formulas from the source and verified
- `failsafe_procedure = RTH`, failsafe is tested on the bench and in the field
- The compass is calibrated; heading, home and altitude are checked on the ground
- A 60 s hover with Blackbox, `nav_mc_hover_thr` from the log, POSHOLD and RTH tested
- The `diff all` from the real aircraft and the log are saved, the restore is verified

## references
- INAV SITL | https://github.com/iNavFlight/inav/blob/master/docs/SITL/SITL.md | primary | A
- INAV Building SITL | https://github.com/iNavFlight/inav/blob/master/docs/development/Building%20SITL.md | primary | A
- INAV Settings reference | https://github.com/iNavFlight/inav/blob/master/docs/Settings.md | primary | A
- INAV Battery (vbat_scale, current meter) | https://github.com/iNavFlight/inav/blob/master/docs/Battery.md | primary | A
- INAV battery.c (voltage and current formulas) | https://github.com/iNavFlight/inav/blob/master/src/main/sensors/battery.c | primary | A
- INAV Failsafe | https://github.com/iNavFlight/inav/blob/master/docs/Failsafe.md | primary | A
- INAV Mixer | https://github.com/iNavFlight/inav/blob/master/docs/Mixer.md | primary | A
- INAV Controls (sticks, throttle_idle, min_check) | https://github.com/iNavFlight/inav/blob/master/docs/Controls.md | primary | A
- INAV Configurator (the SITL tab, Motor Mixer Wizard) | https://github.com/iNavFlight/inav-configurator | primary | A
- INAV-X-Plane-HITL setup (Airplane only) | https://github.com/RomanLut/INAV-X-Plane-HITL/blob/main/doc/setup.md | secondary | B
- INAV OSD (the table of HD systems and grids) | https://github.com/iNavFlight/inav/blob/9.1.0/docs/OSD.md | primary | A
- INAV displayport_msp_osd.c (osd_video_system → grid) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/io/displayport_msp_osd.c | primary | A
- INAV 8.0.1 release notes (DJI O4, DJI_NATIVE) | https://github.com/iNavFlight/inav/releases/tag/8.0.1 | primary | A
- INAV 9.1.0 Release Notes (GNSS: constellations and update rate, the upgrade procedure) | https://github.com/iNavFlight/inav/wiki/9.1.0-Release-Notes | primary | A
