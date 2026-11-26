---
id: el-peripherals
title: "Connecting Peripherals: UART, I2C, CAN in Practice"
level: L2
readingTime: 35 min
firmware: Betaflight · INAV · ArduPilot
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
source_hash: a416702cb100
---

## summary
Frying a flight controller port is easier than it seems: 5 V on a 3.3 V pin, swapped TX/RX with power coming from two sources, I2C without pull-ups, CAN without a terminator. This module is a practical procedure for connecting any device: identify the interface and levels → find a port and its power → check with a multimeter before power-up → configure the protocol in the firmware → confirm the data with an analyzer. With examples: GPS+compass, rangefinder, ESC telemetry, digital video system, DroneCAN node.

## theory
### Three buses and their character
| Bus | Wires | Speed | Addressing | Typical devices | Main pitfalls |
|---|---|---|---|---|---|
| UART | TX, RX, GND (+power) | 9600 – 2 Mbaud; GPS 38400–115200, CRSF 420000, MSP 115200 | point-to-point | GPS, receiver, telemetry, VTX, rangefinder, companion | TX↔RX crossed; inversion (SBUS); one port — one device |
| I2C | SDA, SCL, GND | 100/400 kHz | 7-bit address, many devices on the bus | compass, barometer, OLED, some rangefinders | no pull-ups; identical addresses; long wires (> 30 cm — trouble) |
| SPI | CLK, MOSI, MISO, CS | up to tens of MHz | by CS | gyro, OSD, flash, sometimes baro | on-board only; almost never brought out |
| CAN (DroneCAN) | CAN_H, CAN_L, GND (+power) | 1 Mbit/s | node ID 1–125 | GPS/compass, ESC, current sensors, servos, rangefinders | no 120 Ω terminators at the ends; twisted pair; identical node IDs |

### Levels and power
- FC logic is **3.3 V**. Most inputs tolerate 5 V (“5V tolerant”), but not all: read the MCU datasheet (STM32F4/F7/H7 — most GPIOs are 5V-tolerant, except pins with analog functions). Rule: if in doubt — a 1k/2k divider at the FC input or a level shifter.
- **Port power**: the 5 V and 9 V pads on the FC come from on-board BECs with a limit (typically 5 V/2–3 A, 9 V/2–3 A total for all loads). Powering a Raspberry Pi or a digital air unit “from the pad” overloads the BEC; power it from a separate BEC.
- **Common ground** — always. A device with its own power and no common ground with the FC means garbage on the UART or a fried port.
- **Two power points** (a device powered from the FC and from the companion's USB at the same time) — reverse current through the BEC. A diode or a single power source.

### UART: details
- FC TX → device RX, FC RX ← device TX.
- **Inversion**: SBUS and some protocols are inverted; on an F4 without a hardware inverter you need an external one or a port with an inverter; F7/H7 — software inversion (Betaflight `serialrx_inverted`). CRSF is not inverted, one line in each direction.
- **Single wire**: ESC telemetry (KISS/BLHeli_32 protocol) is one-way (ESC → FC): it arrives on one RX pin from all ESCs in turn over a common wire, the request goes over the DShot signal; VTX SmartAudio/Tramp is true half-duplex: one wire to the TX pin, data both ways.
- One device per UART (except half-duplex protocols designed specifically for that).

### I2C: details
- Pull-ups of 2.2–4.7 kΩ on SDA and SCL to 3.3 V — usually already on the FC; a second device with its own pull-ups lowers the combined resistance — fine down to ~1 kΩ equivalent.
- Addresses: compass HMC5883 0x1E, QMC5883 0x0D, IST8310 0x0C/0x0E, baro BMP280 0x76/0x77, MS5611 0x76/0x77. Two devices with the same address — a conflict.
- Length: short wires, twisted with ground; on a GPS mast 15–20 cm is fine, 50 cm is already risky (drop to 100 kHz).

{{diagram:i2c-transaction|An I2C transaction bit by bit — exactly what the logic analyzer sees when “the sensor can't be found.”}}

{{diagram:chart-i2c-pullup-window|Подтяжка должна лежать между красной линией (0.97 кОм) и кривой режима: при 100 пФ одиночные 4.7 кОм для 400 кГц слишком слабы, а две параллельные (2.35 кОм) — в окне.}}

### DroneCAN: when and how
When: the aircraft is large (long wires → UART/I2C pick up noise), there are many devices, you need ESC and sensor telemetry on one bus, redundancy. In ArduPilot: `CAN_P1_DRIVER = 1` (enable port 1), `CAN_D1_PROTOCOL = 1` (DroneCAN), reboot; GPS `GPS_TYPE = 9` (`GPS1_TYPE` in 4.6+) — DroneCAN, the compass is detected automatically. The bus: twisted pair, 120 Ω terminators at both ends (many devices have a terminator jumper), node power per the spec (usually 5 V), unique node IDs (the autopilot hands them out as a DNA server with dynamic allocation; `CAN_D1_UC_NODE` is the autopilot's own node ID).

### Connection procedure (always the same)
1. Device datasheet: interface, levels, power (V, mA), protocol and speed.
2. FC map: a free port, its inverter/power, the BEC limit.
3. Wires labeled; TX/RX crossed; common ground.
4. **Before power-up**: multimeter — no short from 5 V/3.3 V to GND, the device's power will come from the right pad.
5. Power up through a smoke stopper. The voltage at the device is normal.
6. Firmware: port → function → protocol/speed. Check the data (GPS: satellites; compass: heading changes when you rotate; ESC telemetry: RPM on the motors tab).
7. If there's no data — analyzer on the line: are there bytes, what speed, inversion.

{{diagram:periph-connect-flow|Мультиметр и smoke stopper — до прошивки; если данных нет, следующий шаг — анализатор на линии: есть ли байты, какая скорость, нет ли инверсии.}}

## practice
### Step 0. Bus calculation before soldering
Checks four decisions from the theory: the I2C pull-up window versus bus capacitance, sensor address overlaps, the UART load of UBX-NAV-PVT and the CAN bus resistance. Runs on any computer with Python 3; save as `periph_lab.py`:
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

# Address conflicts (7-bit) from ArduPilot 4.7.2 drivers
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

### Step 1. GPS with compass (UART + I2C)
Connect the GPS to UARTx (TX↔RX), the compass to SDA/SCL, 5 V power. Betaflight: Ports → GPS on UARTx, Configuration → GPS UBLOX, 57600/115200; enable the magnetometer. ArduPilot: `SERIALx_PROTOCOL = 5`, `GPS_TYPE = 2` (`GPS1_TYPE` in 4.6+, u-blox), compass — autodetect. Check: NSats ≥ 6 outdoors, the heading rotates.

### Step 2. ESC telemetry
The common telemetry wire from all ESCs → RX of a free UART. Betaflight: Ports → ESC on UARTx, `feature ESC_SENSOR` (Configuration → ESC Sensor) enabled; check — RPM/temperature on the Motors tab without props. ArduPilot: `SERIALx_PROTOCOL = 16`.

### Step 3. A rangefinder or another UART/I2C device
Follow the procedure from the theory; check in the firmware (ArduPilot `RNGFND1_TYPE`, Betaflight/INAV — the sensors tab).

### Step 4. Analyzer
Capture one frame: UBX from the GPS (header `B5 62`), an ESC telemetry byte, or a compass I2C transaction with the address and ACK.

### What you should get and what to record
- **Before power-up:** with the multimeter — 5 V at the device connector, common ground, TX and RX not swapped (the TX of one goes to the RX of the other). 3.3 V and 5 V levels not mixed: a 5 V TX into a 3.3 V RX without level shifting is a path to a fried port.
- **GPS:** in the firmware the satellite count grows and a fix appears. The I²C compass is detected automatically. If not, a bus scanner will show the address: for example, 0x0D (QMC5883L), 0x0E (IST8310), 0x1E (HMC5883L).
- **ESC telemetry:** in the Motors tab (Betaflight), without props, you see the RPM and temperature of each ESC. If one is missing — the telemetry wire from that ESC isn't making it.
- **Analyzer frame:** UBX starts with `B5 62`, then class, ID and length. An I²C transaction — the address, the read or write bit and the ACK from the device. Label the bytes on the analyzer screenshot and put it in the build record.

The lab is passed when a UART device, an I²C device and ESC telemetry are connected and visible in the firmware, levels and power are checked with a multimeter before power-up with the values recorded, and one protocol frame is captured with the analyzer and labeled byte by byte.

## diagnostics
- **Symptom:** the device doesn't respond, the port is configured
  - Possible cause: TX/RX not crossed, speed, inversion, no common ground.
  - What to do: analyzer on the device's line: are there bytes; swap TX/RX; check GND.
- **Symptom:** an I2C device is “sometimes there, sometimes not”
  - Possible cause: long wires, no pull-ups, noise from the power wiring.
  - What to do: shorter, twisted, 100 kHz, 2.2–4.7 kΩ pull-ups.
- **Symptom:** after connecting a companion the FC reboots
  - Possible cause: the flight controller's 5 V BEC is overloaded.
  - What to do: a separate 5 V/3–5 A BEC for the companion, common ground.
- **Symptom:** a DroneCAN node isn't visible
  - Possible cause: no terminators, CAN_H/CAN_L swapped, driver not enabled.
  - What to do: 120 Ω at the ends, check `CAN_P1_DRIVER`/`CAN_D1_PROTOCOL`, reboot.
- **Symptom:** a port burned out after connecting a 5 V sensor
  - Possible cause: the pin isn't 5V-tolerant, or power got onto the signal line.
  - What to do: a divider/level shifter; another port; check the MCU datasheet.

## references
- ArduPilot — CAN Bus Setup (DroneCAN) | https://ardupilot.org/copter/docs/common-canbus-setup-advanced.html | primary | A
- Betaflight — Serial (development docs: ports, inversion, half-duplex) | https://betaflight.com/docs/wiki/guides/current/Serial | primary | A
- ArduPilot — Serial Port Options and Protocols | https://ardupilot.org/copter/docs/common-serial-options.html | primary | A

## checklist
- I know the levels, power and pitfalls of each bus
- I always follow the connection procedure in the same order, with the multimeter before power-up
- GPS, compass and ESC telemetry are connected and visible in the firmware
- I captured a protocol frame with the analyzer
- I understand when DroneCAN is needed and how to enable it
