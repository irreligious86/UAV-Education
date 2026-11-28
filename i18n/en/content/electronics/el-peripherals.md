---
id: el-peripherals
title: "Connecting peripherals: UART, I2C, CAN in practice"
level: L2
readingTime: 45 min
firmware: Betaflight 2025.12.5 · ArduPilot 4.7 (checked against 4.7.3) · PX4 1.18 (parameters checked against v1.18.0); INAV — by analogy with Betaflight
status: published
added: 2026-11-08
tags:
  - UART
  - I2C
  - DroneCAN
  - peripherals
related:
  - el-measure
  - f-fc-sensors
  - bf-ports
  - el-emi
next:
  - rf-antennas
source: content/electronics/el-peripherals.md
source_hash: c3264704851e
---

## summary
Burning a flight controller port is easier than it looks: 5 V on a 3.3 V pin, swapped TX/RX with power from two sources, I2C without pull-ups, CAN without a terminator. This module is a practical procedure for connecting any device: identify the interface and levels → find the port and its power → check with a multimeter before power-up → configure the protocol in the firmware → confirm the data with an analyzer. The theory gives you the numbers to decide in advance: the I²C pull-up resistance window for the bus capacitance, address conflicts, UART load from a GPS stream, the resistance of a correctly terminated CAN bus, and a summary table of which parameter enables a device in Betaflight, ArduPilot and PX4. The lab starts with a bus calculation (a script), then GPS+compass, a rangefinder, ESC telemetry and a DroneCAN node on hardware.

## theory
### Three buses and their character
| Bus | Wires | Speed | Addressing | Typical devices | Main pitfalls |
|---|---|---|---|---|---|
| UART | TX, RX, GND (+power) | 9600 – 2 Mbaud; GPS 57600–230400 (depends on the firmware, see "How much fits on the line"), CRSF 420000, MSP 115200 | point to point | GPS, receiver, telemetry, VTX, rangefinder, companion | TX↔RX crossed; inversion (SBUS); one port, one device |
| I2C | SDA, SCL, GND | 100/400 kHz; Betaflight defaults to 800 kHz | 7-bit address, many devices on a bus | compass, barometer, OLED, airspeed sensor, some rangefinders | no pull-ups; duplicate addresses; long wires (> 30 cm causes problems, a course guideline) |
| SPI | CLK, MOSI, MISO, CS | up to tens of MHz | by CS | gyro, OSD, flash, sometimes baro, PMW3901 optical flow | on the board only; rarely brought out |
| CAN (DroneCAN) | CAN_H, CAN_L, GND (+power) | 1 Mbit/s | node ID 1–127 (126–127 for debugging tools, dynamic allocation up to 125) | GPS/compass, ESCs, current sensors, servos, rangefinders, airspeed | no 120 Ω terminators at the ends; twisted pair; duplicate node IDs |

### Levels and power
- FC logic is **3.3 V**. Most inputs tolerate 5 V ("5V tolerant"), but not all: read the MCU datasheet (STM32F4/F7/H7: most GPIOs are 5V-tolerant, except pins with analog functions, and only while the FC is powered). Rule: if in doubt, a 1k/2k divider on the FC input or a level shifter.
- **Port power**: the 5 V and 9 V pads on the FC come from onboard BECs with a limit (typically 5 V/2–3 A and 9 V/2–3 A in total for all loads). Connecting a Raspberry Pi or a digital air unit "to a pad" overloads the BEC; power it from a separate BEC.
- **Common ground**: always. A device with its own power and no common ground with the FC means garbage on the UART or a burned port.
- **Two power points** (a device powered from the FC and from the companion's USB at the same time) means reverse current through the BEC. Use a diode or a single supply.

### UART: details
- FC TX → device RX, FC RX ← device TX.
- **Inversion**: SBUS and some other protocols are inverted; on an F4 without a hardware inverter you need an external one or a port with an inverter; F7/H7 invert the signal in the UART itself, so no parameter needs changing (Betaflight `serialrx_inverted` sets a deviation from the protocol's standard: for SBUS, ON = non-inverted signal). CRSF is not inverted, one line in each direction.
- **Single wire**: ESC telemetry (the KISS/BLHeli_32 protocol) is one-way (ESC → FC): it arrives on one RX pin from all ESCs in turn over a shared wire, and the request goes out over the DShot signal; VTX SmartAudio/Tramp is true half-duplex: one wire to the TX pin, data in both directions.
- One device per UART (except half-duplex protocols designed for it).

**How much fits on the line.** An 8N1 byte is a start bit, 8 data bits and a stop bit, 10 bits on the line. Load = bytes per frame × frames per second × 10 / baud. Example: the main u-blox message, UBX-NAV-PVT, carries 92 bytes of payload (the `ubx_nav_pvt` struct in `AP_GPS_UBLOX.h`); the frame with the `B5 62` sync bytes, class, ID, length and checksum is 100 bytes. At 9600 baud and 10 Hz that is 104 % of the line, so not even this one message fits; at 5 Hz it is 52 %; at 115200 baud and 10 Hz it is 8.7 %. Hence the rule: 9600 for a GPS is only for first contact; the working baud rate is the one the firmware sets, and the firmware can set it itself (Betaflight: `gps_auto_config` is on by default, `gps_auto_baud` has to be enabled; ArduPilot and PX4 configure u-blox automatically by default). Betaflight 2025.12.5 uses 57600: NAV-PVT at 10 Hz plus NAV-SAT at 2 Hz (1:5, and only while the configurator is connected, `io/gps.c`) take about 30 % of the line, and at 115200 the documentation notes lost frames (`bf-gps-setup`); ArduPilot 4.7.3 switches u-blox to 230400 by itself (`AP_GPS.cpp`; 115200 with the `GPS_DRV_OPTIONS` option, bit 2). If you configure the module by hand in u-center and have disabled auto-configuration in the firmware, keep the load below ~50 % (a course guideline): besides NAV-PVT, the module often sends other messages too.

### I2C: details
- Pull-ups of 2.2–4.7 kΩ on SDA and SCL to 3.3 V are usually already on the FC and on the GPS board; several boards with pull-ups end up in parallel, and the total resistance drops. The MCU's internal pull-ups (Betaflight `i2cN_pullup`, off by default unless the target defines `USE_I2C_PULLUP`) are weak and only suitable for short on-board buses.
- Addresses (7-bit, from the ArduPilot 4.7.3 drivers): compass HMC5883 0x1E, QMC5883L 0x0D, IST8310 one of 0x0C, 0x0D, 0x0E, 0x0F (set by pins), baro BMP280 0x76/0x77, MS5611 0x77/0x76, airspeed sensor MS4525DO 0x28 (variants 0x36, 0x46), PX4Flow 0x42 (+ `FLOW_ADDR`, up to 0x49). Two devices with the same address on one bus are a conflict.
- Length: short wires, twisted with ground; 15–20 cm up a GPS mast is normal, 50 cm is already risky (lower the clock; a course guideline).

{{diagram:i2c-transaction|An I2C transaction bit by bit: exactly what the logic analyzer shows when "the sensor is not found".}}

**Why exactly 2.2–4.7 kΩ.** I²C lines are open-drain: a device only pulls the line to ground, and a resistor pulls it up, charging the bus capacitance Cb (the wires plus the inputs of all devices). That gives two limits (TI SLVA689, based on the I²C specification). The lower one: an open-drain output must pull the line below 0.4 V while sinking 3 mA, so Rp ≥ (3.3 − 0.4) / 3 mA = 967 Ω. The upper one: the edge from 30 to 70 % of the voltage takes t = 0.8473·Rp·Cb and must not exceed 1000 ns in 100 kHz mode and 300 ns in 400 kHz mode, so Rp ≤ t_r / (0.8473·Cb). At 100 pF the window for 400 kHz is 0.97–3.54 kΩ: a single 4.7 kΩ pull-up is already too weak (a 398 ns edge), while 4.7 kΩ on the FC in parallel with 4.7 kΩ on the GPS gives 2.35 kΩ and a 199 ns edge, which fits. At 200 pF the window narrows to 0.97–1.77 kΩ, and at 400 pF there is no solution for 400 kHz at all, only 100 kHz. A third board with a 2.2 kΩ pull-up brings the total down to 1.14 kΩ, still above the limit; a fourth one goes below 967 Ω, and a logic zero stops being a zero.

{{diagram:chart-i2c-pullup-window|The pull-up must lie between the red line (0.97 kΩ) and the curve for the mode: at 100 pF a single 4.7 kΩ is too weak for 400 kHz, while two in parallel (2.35 kΩ) are inside the window.}}

Betaflight sets `i2cN_clockspeed_khz` = 800 by default (range 100–1300, `common_defaults_post.h`). That is above Fast-mode at 400 kHz, and for that frequency the specification requires an edge no longer than 120 ns (Fast-mode Plus). On the board it works, but on an external bus to a GPS with a compass the 199 ns edge from the example above no longer fits. The conclusion from the calculation: for an external compass set `i2cN_clockspeed_khz = 400`, and 100 with a long or unreliable cable. ArduPilot and PX4 set the external bus clocks in the board definition, and there is no parameter; the remedies there are a shorter wire, stronger pull-ups, or moving to DroneCAN.

**Address conflicts.** The IST8310 can be set to 0x0D, the same address as the QMC5883L; the MS5611 and BMP280 share 0x76/0x77. On one bus such pairs produce garbage or a "floating" sensor. The cure is selecting the address with a pin (if it is brought out), splitting them across different I²C buses, or moving one of the sensors to CAN.

### SPI: details
SPI is four wires and a separate CS for each device, with no addresses and no pull-ups, at clocks from a few to tens of MHz. That is why it is rarely brought out: at 10–20 MHz a 10 cm wire is already a transmission line with ringing and pickup. On a flight controller, SPI carries the gyro, the OSD chip, the blackbox flash, sometimes the barometer; outside, at most a PMW3901 or PAA3905 optical flow module right next to the board (PX4 `SENS_EN_PMW3901`, `SENS_EN_PAA3905`, if the board brings out the bus). An SPI fault on the board is a reason to replace the board, not to tweak parameters.

### DroneCAN: when and how
When: a large aircraft (long wires → UART/I2C pick up interference), many devices, ESC and sensor telemetry on one bus, redundancy. In ArduPilot: `CAN_P1_DRIVER = 1` (enable port 1; the default depends on the board), `CAN_D1_PROTOCOL = 1` (DroneCAN, this is the default), `CAN_P1_BITRATE` = 1000000 by default, reboot; GPS `GPS1_TYPE = 9` (before 4.6: `GPS_TYPE`) for DroneCAN, and the compass is found automatically. In PX4: `UAVCAN_ENABLE`: 0 off, 1 sensors with manual config, 2 sensors with automatic config, 3 sensors and ESCs; `UAVCAN_NODE_ID` = 1 (its own, 1–125), `UAVCAN_BITRATE` = 1000000, subscriptions by type: `UAVCAN_SUB_GPS` and `UAVCAN_SUB_MAG` are on by default, `UAVCAN_SUB_RNG`, `UAVCAN_SUB_FLOW`, `UAVCAN_SUB_ASPD` are off. Betaflight does not support CAN. The bus: twisted pair, 120 Ω terminators at both ends (many devices have a terminator jumper), node power per the specification (usually 5 V), unique node IDs (the autopilot hands them out as the DNA server in dynamic allocation; `CAN_D1_UC_NODE` is ArduPilot's own node ID, 10 by default).

Checking the termination with a multimeter on an unpowered bus between CAN_H and CAN_L: 60 Ω means two terminators, correct; 120 Ω means one, with the other end "open"; 40 Ω means three, with an extra one in the middle of the bus. This is the fastest check before touching any parameters.

{{lesson:el-dronecan|The DroneCAN bus at the system level: arbitration, DNA, redundancy, length and topology, node firmware.}}

### Reference: where a device is enabled in the firmware
| Device | Betaflight 2025.12.5 | ArduPilot 4.7.3 | PX4 1.18.0 |
|---|---|---|---|
| GPS (UART) | `serial <n> 2 …` (GPS function = 2), `gps_provider = UBLOX`, `gps_auto_config` (on), `gps_auto_baud` (off by default) | `SERIALn_PROTOCOL = 5`, `GPS1_TYPE = 1` (auto) or 2 (u-blox); before 4.6: `GPS_TYPE` | `GPS_1_CONFIG` (default GPS1), `GPS_1_PROTOCOL = 1` (u-blox), `SER_GPS1_BAUD = 0` (auto) |
| Compass (I²C) | `mag_hardware` (AUTO, QMC5883, IST8310…), `mag_bustype`, `mag_i2c_device`, `mag_i2c_address`, `mag_align_*` | auto-probe; `COMPASS_EXTERNAL`, `COMPASS_ORIENT`, `COMPASS_DISBLMSK` | auto-probe with `SENS_EXT_I2C_PRB = 1` (default), rotation `CAL_MAGn_ROT` |
| Barometer | `baro_hardware`, `baro_bustype`, `baro_i2c_device`, `baro_i2c_address` | auto-probe | auto-probe |
| Rangefinder | `rangefinder_hardware` (TFMINI, TF02 on a port with function 32768; MTF01/MTF02 over MSP) | `RNGFND1_TYPE` (20 TFmini serial, 25 TFmini I²C, 24 DroneCAN), `SERIALn_PROTOCOL = 9`, `RNGFND1_ADDR` | `SENS_TFMINI_CFG` (port), `SENS_EN_LL40LS`, `UAVCAN_SUB_RNG` |
| Optical flow | `opticalflow_hardware = MT` (over MSP) | `FLOW_TYPE` (1 PX4Flow, 5 MAVLink, 6 DroneCAN, 7 MSP) | `SENS_EN_PMW3901`, `SENS_EN_PAA3905`, `UAVCAN_SUB_FLOW`, `SENS_FLOW_ROT` |
| Airspeed | none | `ARSPD_TYPE` (1 MS4525, 8 DroneCAN), `ARSPD_BUS` (default 1) | `SENS_EN_MS4525DO`, `SENS_EN_SDP3X`, `SENS_EN_MS5525DS`, `UAVCAN_SUB_ASPD` |
| ESC telemetry | `serial <n> 1024` (ESC_SENSOR function), `feature ESC_SENSOR` | `SERIALn_PROTOCOL = 16` | `DSHOT_TEL_CFG` (DShot telemetry port) or DroneCAN ESCs (`UAVCAN_ENABLE = 3`) |
| I²C bus | `i2cN_clockspeed_khz` (800, 100–1300), `i2cN_pullup` | in the board definition | in the board definition |
| CAN bus | none | `CAN_P1_DRIVER`, `CAN_P1_BITRATE` (1000000), `CAN_D1_PROTOCOL` (1), `CAN_D1_UC_NODE` (10) | `UAVCAN_ENABLE` (0), `UAVCAN_NODE_ID` (1), `UAVCAN_BITRATE` (1000000) |

{{lesson:px4-hardware-peripherals|The Pixhawk 6X port map on PX4 and the "one port, one driver" rule, with a reboot and a driver check in the console.}}

### The connection procedure (always the same)
1. The device datasheet: interface, levels, power (V, mA), protocol and baud rate.
2. The FC map: a free port, its inverter/power, the BEC limit.
3. Wires labeled; TX/RX crossed; common ground.
4. **Before power-up**: multimeter: no short from 5 V/3.3 V to GND, the device will get power from the right pad; on CAN, 60 Ω between H and L.
5. Power up through a smoke stopper. The voltage at the device is normal.
6. Firmware: port → function → protocol/baud rate. Check the data (GPS: satellites; compass: heading changes when you turn it; ESC telemetry: RPM on the motors tab).
7. If there is no data, put the analyzer on the line: are there bytes, what baud rate, inversion.

{{diagram:periph-connect-flow|The multimeter and the smoke stopper come before the firmware; if there is no data, the next step is the analyzer on the line: are there bytes, what baud rate, is it inverted.}}

### Where it fits in the system

- **Takes in:** the BEC current limit and the 5 and 9 V pads (`el-power-design`, `f-fc-sensors`); free UARTs and their inverters (`bf-ports`); the device's protocol and baud rate (`link-protocols`).
- **Puts out:** GPS and compass data to state estimation (`est-gnss`); the rangefinder to the altitude sources (`est-alt-sources`); CAN nodes to the bus system level (`el-dronecan`); unclear cases to the analyzer (`el-measure`).
- **If you get this wrong:** a Raspberry Pi or air unit powered from a flight controller pad → the BEC is overloaded and the flight controller reboots in flight (tree 6 in `diag-troubleshooting`). A compass on I²C over a 50 cm wire next to the power bus → bus errors, the compass data drops out; the cure is interference protection or moving to CAN (`el-emi`, `el-dronecan`). An external compass at the Betaflight default of 800 kHz → by the calculation the edges do not fit in 120 ns, the compass can drop out, and the navigation modes fail (`est-gnss`).

## practice
### Step 0. Bus calculation before soldering
The script checks four decisions from the theory: the I²C pull-up window for the bus capacitance, overlapping sensor addresses, UART load from a UBX-NAV-PVT stream, and the CAN bus resistance. It runs on any computer with Python 3; save it as `periph_lab.py`:
```python
"""Peripheral bus checks: I2C pull-up window, address conflicts, UART load of a GPS, CAN termination."""
import itertools

# I2C: TI SLVA689 (from the I2C-bus spec): Rp_min = (Vcc - VOL) / IOL, Rp_max = tr / (0.8473 * Cb)
VCC, VOL, IOL = 3.3, 0.4, 3e-3
TR = {"100 kHz": 1000e-9, "400 kHz": 300e-9, "1 MHz (Fm+)": 120e-9}
rp_min = (VCC - VOL) / IOL
print(f"1) I2C pull-up window at {VCC} V: Rp_min = {rp_min:.0f} Ohm")
for cb_pf in (50, 100, 200, 400):
    cells = []
    for mode, tr in TR.items():
        rmax = tr / (0.8473 * cb_pf * 1e-12)
        bad = "Fm+" not in mode and rmax < rp_min          # Fm+: the I2C spec (UM10204) allows 20 mA sink, so Rp_min is lower; not checked here
        cells.append(f"{mode} {rmax / 1000:5.2f} k" + (" (impossible)" if bad else ""))
    print(f"   Cb {cb_pf:3d} pF: Rp_max " + " | ".join(cells))


def par(*r):
    return 1 / sum(1 / x for x in r)


print(f"   pull-ups in parallel: FC 4.7k || GPS 4.7k = {par(4700, 4700):.0f} Ohm, "
      f"+ third 2.2k = {par(4700, 4700, 2200):.0f} Ohm (min {rp_min:.0f})")
for r in (4700, 2350, 1000):
    tr = 0.8473 * r * 100e-12
    print(f"   rise time with {r} Ohm and 100 pF: {tr * 1e9:.0f} ns")

# Address conflicts (7-bit) from ArduPilot 4.7.3 drivers
DEV = {"QMC5883L": [0x0D], "IST8310": [0x0C, 0x0D, 0x0E, 0x0F], "HMC5883": [0x1E],
       "MS5611": [0x76, 0x77], "BMP280": [0x76, 0x77], "MS4525DO": [0x28, 0x36, 0x46], "PX4Flow": [0x42]}
print("\n2) I2C address overlaps (possible addresses per driver):")
for a, b in itertools.combinations(DEV, 2):
    common = sorted(set(DEV[a]) & set(DEV[b]))
    if common:
        print(f"   {a} / {b}: " + ", ".join(f"0x{x:02X}" for x in common))

# UART load: UBX-NAV-PVT payload is the ubx_nav_pvt struct in AP_GPS_UBLOX.h
pvt = 4 + 2 + 5 * 1 + 1 + 4 + 4 + 4 * 1 + 2 * 4 + 2 * 4 + 2 * 4 + 4 * 4 + 4 + 4 + 4 + 2 + 1 + 5 + 4 + 2 + 2
frame = pvt + 8                                   # sync 2 + class 1 + id 1 + length 2 + checksum 2
print(f"\n3) UBX-NAV-PVT: payload {pvt} B, frame {frame} B")
for baud in (9600, 38400, 115200, 230400):
    for hz in (5, 10):
        load = frame * hz * 10 / baud
        print(f"   {baud:>6} baud, {hz:>2} Hz: {100 * load:5.1f} % of the line")

print("\n4) CAN: resistance CAN_H-CAN_L, power off")
for n in (1, 2, 3):
    print(f"   {n} x 120 Ohm -> {120 / n:.0f} Ohm" + ("  <- correct" if n == 2 else ""))
for rate in (1_000_000, 500_000):
    print(f"   {rate // 1000} kbit/s: bit time {1e9 / rate:.0f} ns")
```
Output of `python3 periph_lab.py` (2026-11-26):
```
1) I2C pull-up window at 3.3 V: Rp_min = 967 Ohm
   Cb  50 pF: Rp_max 100 kHz 23.60 k | 400 kHz  7.08 k | 1 MHz (Fm+)  2.83 k
   Cb 100 pF: Rp_max 100 kHz 11.80 k | 400 kHz  3.54 k | 1 MHz (Fm+)  1.42 k
   Cb 200 pF: Rp_max 100 kHz  5.90 k | 400 kHz  1.77 k | 1 MHz (Fm+)  0.71 k
   Cb 400 pF: Rp_max 100 kHz  2.95 k | 400 kHz  0.89 k (impossible) | 1 MHz (Fm+)  0.35 k
   pull-ups in parallel: FC 4.7k || GPS 4.7k = 2350 Ohm, + third 2.2k = 1136 Ohm (min 967)
   rise time with 4700 Ohm and 100 pF: 398 ns
   rise time with 2350 Ohm and 100 pF: 199 ns
   rise time with 1000 Ohm and 100 pF: 85 ns

2) I2C address overlaps (possible addresses per driver):
   QMC5883L / IST8310: 0x0D
   MS5611 / BMP280: 0x76, 0x77

3) UBX-NAV-PVT: payload 92 B, frame 100 B
     9600 baud,  5 Hz:  52.1 % of the line
     9600 baud, 10 Hz: 104.2 % of the line
    38400 baud,  5 Hz:  13.0 % of the line
    38400 baud, 10 Hz:  26.0 % of the line
   115200 baud,  5 Hz:   4.3 % of the line
   115200 baud, 10 Hz:   8.7 % of the line
   230400 baud,  5 Hz:   2.2 % of the line
   230400 baud, 10 Hz:   4.3 % of the line

4) CAN: resistance CAN_H-CAN_L, power off
   1 x 120 Ohm -> 120 Ohm
   2 x 120 Ohm -> 60 Ohm  <- correct
   3 x 120 Ohm -> 40 Ohm
   1000 kbit/s: bit time 1000 ns
   500 kbit/s: bit time 2000 ns
```
Decisions that follow from the output. For your build, write down in your notes: which pull-ups are on the FC and on the GPS board (measure with a multimeter between SDA and 3.3 V on an unpowered board: you will see the parallel total), whether the total falls inside the window for your clock, whether your sensor set has a pair from item 2 on the same bus, what the GPS baud rate and line load are, and how many ohms there are between CAN_H and CAN_L. The "Fm+" line is there to evaluate Betaflight's 800 kHz: even at 50 pF the ceiling is 2.83 kΩ, and the 199 ns edge at 100 pF is longer than the allowed 120 ns.

### Step 1. GPS with compass (UART + I2C)
Connect the GPS to UARTx (TX↔RX), the compass to SDA/SCL, 5 V power. Betaflight: Ports → GPS on UARTx, Configuration → GPS UBLOX, `gps_auto_config` on (the default), enable `gps_auto_baud`; enable the magnetometer, and for an external compass set `i2cN_clockspeed_khz = 400`. ArduPilot: `SERIALx_PROTOCOL = 5`, `GPS1_TYPE = 2` (u-blox; before 4.6: `GPS_TYPE`), compass auto-detected. PX4: `GPS_1_CONFIG` set to the GPS 1 port (the default), compass auto-probed on the external bus. Check: NSats ≥ 6 outdoors, the heading turns.

### Step 2. ESC telemetry
The shared telemetry wire from all ESCs → RX of a free UART. Betaflight: Ports → ESC on UARTx, `feature ESC_SENSOR` (Configuration → ESC Sensor) on; check RPM/temperature on the Motors tab without props. ArduPilot: `SERIALx_PROTOCOL = 16`.

### Step 3. A rangefinder or another UART/I2C device
Following the protocol from the theory and the row of the reference table; check in the firmware (ArduPilot `RNGFND1_TYPE`, PX4 `SENS_TFMINI_CFG` and `listener distance_sensor`, Betaflight/INAV the sensors tab).

### Step 4. Analyzer
Capture one frame: UBX from the GPS (header `B5 62`), a byte of ESC telemetry, or a compass I2C transaction with the address and ACK. If you have a scope, also look at the SCL edge on I²C: from 30 to 70 % of the voltage (as in the step 0 calculation) it must fit within 300 ns for 400 kHz. Measure it with a scope or an analog analyzer channel sampling at 100 MHz or more; a digital channel will not show the edge.

### Step 5. A DroneCAN node (if you have one)
With the bus unpowered: 60 Ω between CAN_H and CAN_L. ArduPilot: `CAN_P1_DRIVER = 1`, `CAN_D1_PROTOCOL = 1`, reboot, `GPS1_TYPE = 9` for a GPS on CAN. PX4: `UAVCAN_ENABLE = 2`, reboot. Check: in ArduPilot the node is visible in the Mission Planner DroneCAN inspector, in PX4 with `uavcan status` in the console.

### Moving to real hardware: safety, abort, acceptance
All connections are made without propellers and through a smoke stopper. Abort (cut power immediately): power-up current more than 2 times what the device datasheet suggests (a course guideline), voltage at the device more than 10 % off nominal (a course guideline), a hot connector or regulator, anything other than 60 Ω between CAN_H and CAN_L. Acceptance: the device is visible in the firmware with plausible data for 10 minutes in a row (a course guideline) without dropouts (compass: no heading jumps with the aircraft stationary; GPS: no loss of fix under open sky).

### What you should get and what to record
- **Before power-up:** with the multimeter: 5 V at the device connector, a common ground, TX and RX not swapped (the TX of one goes to the RX of the other). 3.3 V and 5 V levels not mixed: a 5 V TX into a 3.3 V RX without level shifting is the road to a burned port.
- **GPS:** the satellite count rises in the firmware and a fix appears. A compass on I²C is found automatically. If not, a bus scanner shows the address: for example, 0x0D (a QMC5883L or an IST8310 at that address), 0x0E (IST8310), 0x1E (HMC5883L).
- **ESC telemetry:** on the Motors tab (Betaflight), without props, you see the RPM and temperature of each ESC. If one is missing, the telemetry wire from that ESC did not make it.
- **A frame on the analyzer:** UBX starts with `B5 62`, then class, ID and length. An I²C transaction is the address, the read or write bit, and the ACK from the device. Label the bytes on the analyzer screenshot and put it in the build logbook.

Self-check: the lab is done when (calculation) your run of step 0 gave Rp_min = 967 Ω, a 400 kHz window at 100 pF up to 3.54 kΩ, 2350 Ω for two 4.7 kΩ in parallel, the 0x0D and 0x76/0x77 overlaps, 104.2 % for 9600 baud at 10 Hz and 60 Ω for two terminators, and your notes record the pull-ups, the I²C clock, the GPS baud rate and the CAN resistance of your build with the verdict "inside / outside the window"; (hardware) a UART device, an I²C device and ESC telemetry are connected and visible in the firmware (GPS: NSats ≥ 6 outdoors; the compass heading changes when you turn it; the Motors tab shows the RPM and temperature of each ESC without props), the levels and power were checked with a multimeter before power-up and the values recorded (5 V at the device connector, no short from 5 V or 3.3 V to GND), and one protocol frame was captured with the analyzer and labeled byte by byte so that the expected start is recognizable: `B5 62` for UBX, or a compass address from the list above with an ACK for I²C.

**Reference answer for self-check.** The correct calculation result: a 0.97–3.54 kΩ window at 100 pF and 400 kHz, the 2.35 kΩ total inside it, a single 4.7 kΩ outside it. Typical wrong results: (1) Rp_max came out a thousand times too large: the capacitance was entered in nanofarads instead of picofarads; (2) the UART load came out as 83 % instead of 104 % at 9600 baud: 8 bits per byte were counted instead of 10; (3) a "window" appeared with 0.5 kΩ pull-ups: the lower limit of 967 Ω for 3 mA was forgotten; (4) 120 Ω was measured on CAN and taken as normal: one terminator is missing.

## diagnostics
- **Symptom:** the device does not respond, the port is configured
  - Possible cause: TX/RX not crossed, baud rate, inversion, no common ground.
  - What to do: analyzer on the device line: are there bytes; swap TX/RX; check GND.
- **Symptom:** an I2C device "comes and goes"
  - Possible cause: long wires, pull-ups outside the window for the bus capacitance, interference from power wires, Betaflight driving the external bus at 800 kHz.
  - What to do: shorter, twisted wires; Betaflight `i2cN_clockspeed_khz = 400` or 100; pull-ups per the step 0 calculation (2.2–4.7 kΩ, with the total no lower than 967 Ω).
  - What the log shows: the SCL edge (30→70 %) on a scope is longer than 300 ns at 400 kHz.
- **Symptom:** the compass is found, but the heading jumps or it reports a different sensor
  - Possible cause: an address conflict: an IST8310 at 0x0D next to a QMC5883L, two barometers at 0x76/0x77.
  - What to do: a bus scanner; change the address with a pin, split them across different I²C buses, or move a sensor to CAN.
- **Symptom:** a GPS at 9600 baud loses updates or the fix "jitters"
  - Possible cause: the line is overloaded: NAV-PVT at 10 Hz is 104 % of 9600 baud.
  - What to do: 115200/230400 and auto-configuration in the firmware (Betaflight: `gps_auto_config` by default, enable `gps_auto_baud`; ArduPilot/PX4 by default).
- **Symptom:** the FC reboots after the companion is connected
  - Possible cause: the flight controller's 5 V BEC is overloaded.
  - What to do: a separate 5 V/3–5 A BEC for the companion, common ground.
- **Symptom:** a DroneCAN node is not visible
  - Possible cause: no terminators (the multimeter shows 120 Ω or open circuit), CAN_H/CAN_L swapped, the driver not enabled.
  - What to do: 120 Ω at the ends (60 Ω between H and L), ArduPilot `CAN_P1_DRIVER`/`CAN_D1_PROTOCOL`, PX4 `UAVCAN_ENABLE` ≥ 1, reboot.
- **Symptom:** a rangefinder on PX4 is connected to TELEM3, but there is no data
  - Possible cause: the port is not assigned to the driver (`SENS_TFMINI_CFG`), or another driver is still on it.
  - What to do: one port, one driver; assign the port, reboot, `tfmini status`.
- **Symptom:** a port burned out after connecting a 5 V sensor
  - Possible cause: the pin is not 5V-tolerant, or power got onto a signal line.
  - What to do: a divider/level shifter; another port; check the MCU datasheet.

## references
- ArduPilot — CAN Bus Setup (DroneCAN) | https://ardupilot.org/copter/docs/common-canbus-setup-advanced.html | primary | A
- Betaflight — Serial (development docs: ports, inversion, half-duplex) | https://betaflight.com/docs/wiki/guides/current/Serial | primary | A
- ArduPilot — Serial Port Options and Protocols | https://ardupilot.org/copter/docs/common-serial-options.html | primary | A
- Texas Instruments SLVA689 — I2C Bus Pullup Resistor Calculation | https://ti.com/lit/SLVA689 | primary | A
- Betaflight 2025.12 source — cli/settings.c (i2cN_clockspeed_khz, mag_*, rangefinder_hardware) | https://github.com/betaflight/betaflight/blob/2025.12.5/src/main/cli/settings.c | primary | A
- ArduPilot 4.7.3 source — AP_GPS_UBLOX.h (ubx_nav_pvt), AP_Compass.cpp (IST8310 addresses) | https://github.com/ArduPilot/ardupilot/tree/Copter-4.7.3/libraries | primary | A
- PX4-Autopilot v1.18.0 — uavcan_params.yaml (UAVCAN_ENABLE, UAVCAN_SUB_*) | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/drivers/uavcan/uavcan_params.yaml | primary | A

## checklist
- I know the levels, power and pitfalls of each bus
- I calculate the I²C pull-up window for the bus capacitance and check the total of parallel pull-ups
- I check the sensor set for address conflicts before building
- I calculate the UART load from a device's stream
- I always follow the connection procedure in the same order, with a multimeter before power-up; 60 Ω on CAN
- GPS, compass and ESC telemetry are connected and visible in the firmware
- I captured a protocol frame with the analyzer
- I understand when DroneCAN is needed and how to enable it in ArduPilot and PX4
