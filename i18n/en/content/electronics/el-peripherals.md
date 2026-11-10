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
source_hash: 640f4adb2205
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
- **Half-duplex**: ESC telemetry (KISS/BLHeli_32 protocol) arrives on one RX pin from all ESCs over a common wire; VTX SmartAudio/Tramp — one wire to the TX pin.
- One device per UART (except half-duplex protocols designed specifically for that).

### I2C: details
- Pull-ups of 2.2–4.7 kΩ on SDA and SCL to 3.3 V — usually already on the FC; a second device with its own pull-ups lowers the combined resistance — fine down to ~1 kΩ equivalent.
- Addresses: compass HMC5883 0x1E, QMC5883 0x0D, IST8310 0x0C/0x0E, baro BMP280 0x76/0x77, MS5611 0x76/0x77. Two devices with the same address — a conflict.
- Length: short wires, twisted with ground; on a GPS mast 15–20 cm is fine, 50 cm is already risky (drop to 100 kHz).

{{diagram:i2c-transaction|An I2C transaction bit by bit — exactly what the logic analyzer sees when “the sensor can't be found.”}}

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

## practice
### Step 1. GPS with compass (UART + I2C)
Connect the GPS to UARTx (TX↔RX), the compass to SDA/SCL, 5 V power. Betaflight: Ports → GPS on UARTx, Configuration → GPS UBLOX, 57600/115200; enable the magnetometer. ArduPilot: `SERIALx_PROTOCOL = 5`, `GPS_TYPE = 2` (`GPS1_TYPE` in 4.6+, u-blox), compass — autodetect. Check: NSats ≥ 6 outdoors, the heading rotates.

### Step 2. ESC telemetry
The common telemetry wire from all ESCs → RX of a free UART. Betaflight: Ports → ESC on UARTx, `esc_sensor` enabled; check — RPM/temperature on the Motors tab without props. ArduPilot: `SERIALx_PROTOCOL = 16`.

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
