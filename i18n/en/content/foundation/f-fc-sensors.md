---
id: f-fc-sensors
title: "Flight controller and sensors"
level: L1
readingTime: 20 min
firmware: any firmware
status: published
added: 2026-11-07
tags:
  - FC
  - sensors
  - UART
related:
  - f-motors-esc
  - link-protocols
next:
  - bf-pid-reg-in-bf
source: content/foundation/f-fc-sensors.md
source_hash: adf44533658a
---

## summary
The flight controller (FC) is a small computer that reads the sensors, runs the controller math and commands the motors thousands of times a second. This module explains what sits on the board, what each sensor is responsible for, how to read a wiring diagram and why the same wire behaves differently on different pads. After it, the board diagram stops being a puzzle.

## theory
### Processor
The heart of the FC is a microcontroller. The series determines the capabilities:

- **F4**: the most common and cheapest; limited in the number of UARTs and can't invert UARTs in hardware (see the SBUS module).
- **F7**: faster, more UARTs, software inversion.
- **H7**: the most powerful, the standard for ArduPilot and PX4 on complex platforms.

What matters isn't “the best processor” but whether the firmware you need supports the board: each firmware has its own list of targets.

### Sensors
- **Gyroscope (gyro)**: angular rate on three axes. The main sensor: stabilization runs on it. It's read thousands of times a second and is sensitive to vibration.
- **Accelerometer (accel)**: acceleration; at rest it shows the direction of gravity. Needed for self-leveling modes (ANGLE) and navigation.
- **Barometer (baro)**: pressure, and from it altitude. Sensitive to prop wash and to light, so it gets covered with foam.
- **Magnetometer (mag, compass)**: heading. It's afraid of power wires: it goes on a mast together with the GPS, away from the current.
- **GPS**: position and velocity. Needed for position hold, return to home and missions.

Fusing these sensors is the job of the state estimation filter: in ArduPilot it's the EKF, in Betaflight a simplified scheme without navigation.

### Buses
- **UART**: a serial port: receiver, GPS, VTX, telemetry, companion. Wires are crossed (TX → RX).
- **I2C**: a bus for several sensors (compass, external baro, display) over two wires, SDA/SCL.
- **SPI**: a fast bus inside the board: gyro, OSD, flash for logs.

### Pads on the board
Typical labels: `VBAT` (battery voltage), `5V`/`9V`/`10V` (BEC outputs), `GND`, `TX1`/`RX1` (UART1), `SDA`/`SCL` (I2C), `CURR` (current sensor), `LED` (addressable LEDs), `BZ+`/`BZ-` (buzzer), `M1`–`M4` or `S1`–`S8` (outputs to ESCs/servos).

### Mounting
The mounting standards are 30.5×30.5 and 20×20 mm. The board sits on rubber dampers: the gyro should feel the frame's motion, not its vibrations. The arrow on the board points “forward”; if the board is rotated, the rotation is set in the firmware (board alignment / AHRS_ORIENTATION).

### A closer look at the gyro: chips and rates
The gyro is a MEMS chip on SPI. Common ones: MPU6000 (old, 8 kHz output, low noise, discontinued), ICM20602/20689 (noisier, more sensitive to power), ICM42688-P (the modern standard: up to 32 kHz, a configurable hardware anti-aliasing filter, low noise), BMI270 (an alternative, 6.4 kHz). The firmware reads the chip over SPI at 8–24 MHz with DMA (the “Embedded” module) and runs the PID loop in sync with the gyro output (always in 4.x; the PID loop divider is `pid_process_denom`): at 8 kHz that's every 125 µs. The chain: chip → hardware LPF (`gyro_hardware_lpf`) → software filters (the “Filters” module) → PID. Two gyros on a board (dual gyro) means averaging or selection; ArduPilot on H7 handles up to three IMUs with separate EKF cores.

{{diagram:fc-signal-path|The signal path inside the FC: gyro → filters → PID → mixer → ESC; the RC command sets the target, Blackbox and OSD take a copy.}}

### What else is on the board
- **OSD chip** (MAX7456 for analog) or digital OSD via MSP DisplayPort (DJI/Walksnail/HDZero): draws telemetry onto the video.
- **Flash/SD** for Blackbox: 16–32 MB of flash is enough for minutes at 2 kHz; SD for hours. It's written over SPI/SDIO and sometimes conflicts over DMA with other functions on F4.
- **BEC**: 5 V (typically 2–3 A total for all loads) and 9–12 V (for the VTX/digital system, 2–3 A). The limits are in the board's description; don't power a Raspberry Pi from an FC pad (the “Connecting peripherals” module).
- **Current sensor** on the PDB/ESC → the `CURR` pad; the scale `ibata_scale` (Betaflight) / `BATT_AMP_PERVLT` (ArduPilot) is calibrated against a wattmeter.
- **UART inverters** on F4 exist only on some ports (for SBUS they're labeled “SBUS”/“RX” and have a hardware inverter); F7/H7 invert any port in software.
- **Softserial**: a UART emulated on GPIO: up to 115200 baud, loads the processor; for SmartAudio/telemetry, not for the receiver.

### What limits your choice of board
The number of UARTs (receiver + GPS + VTX + companion = 4 minimum), whether it has a baro and compass (mandatory for INAV/ArduPilot), BEC current for the load, support for the target by the firmware you need **and its version** (ArduPilot: `hwdef`, Betaflight: unified target), size and mass, 30.5/20 mm mounting, whether it has CAN (DroneCAN on big aircraft), the number of motor/servo outputs (VTOL needs 8+).

### Worked example: reading a pinout
A typical H743 board (30.5 mm): `UART1` is RX with an inverter (labeled SBUS), `UART2` is GPS (with `SDA/SCL` next to it for the compass), `UART4` is VTX/DisplayPort (the `9V` pad is next to it), `UART6`/`UART7` are companion/telemetry, `M1–M8` are DShot, `CURR` is the current sensor from the ESC, `LED` is the addressable strip, `BZ-` is the buzzer, `VBAT` is voltage measurement, `5V` is for the receiver/GPS, `4V5` is powered from USB (for setup without a battery). The reading rule: power first (what comes from where, how much current), then the UARTs by function, then I2C, then the “special” pads. Put the “pad → function → device → current” table into the build passport.

## practice
### Lab: read your board's diagram
1. Find the wiring diagram of your FC from the manufacturer.
2. Write down which UART is free for the receiver, which for the GPS, which for the VTX.
3. Find which pad powers the VTX and camera and how much current that BEC supplies.
4. Note whether there's a pad with an inverter (for SBUS on F4) and where to solder the LED and buzzer.
5. Save the result in the build log next to a photo of the board.

### Checking the sensors after the build
1. Connect the FC to the configurator (Betaflight App, Mission Planner or QGroundControl).
2. Tilt the drone: the model on screen should follow the motion on all three axes without lag.
3. Calibrate the accelerometer on a level surface.
4. Check that the barometer shows a change in altitude when you lift the drone by hand, and that the compass shows the heading.

### What to write down: the board map
| Resource | Purpose | Note |
|---|---|---|
| UART1 | receiver (CRSF) | RX1/TX1 pads next to 5 V |
| UART2 | GPS | 5 V from a separate pad |
| UART3 | VTX (MSP/SmartAudio) | |
| UART4 | free | |
| 9 V BEC | VTX and camera | current from the board datasheet, for example 2 A |
| 5 V BEC | receiver, GPS, LED | |
| SBUS pad | with an inverter (F4) or not needed (F7/H7) | |

The values in the table are an example of the format: fill it in from your own board's diagram, noting the source (diagram page, labeled photo).

### What the check should show
- **Gyro and accelerometer.** The model on the Setup tab follows tilts immediately and in the right direction on all axes. If an axis is inverted or the model “faces” the wrong way, the board orientation is wrong (`align_board_*` in Betaflight, `AHRS_ORIENTATION` in ArduPilot); fix it before the first flight.
- **Accelerometer calibration** on a level surface; after it the horizon is level.
- **Barometer.** When you raise your hand by a meter, the altitude grows by about a meter. A barometer in direct airflow or in the light is noisy; cover it with a piece of foam.
- **Compass** (if present) shows a heading that changes when you turn the aircraft. Next to power wires it lies (the “Interference” module).

The lab counts as done when every UART is assigned a purpose, the power pads and BEC current are written down with a source, the inverter pad is found or noted as not needed, and all sensors are checked in the configurator after the build with the result recorded.

## diagnostics
- **Symptom:** the model in the configurator rotates the wrong way
  - Possible cause: the board is mounted rotated, but the rotation isn't set in the firmware.
  - What to do: set board alignment / AHRS_ORIENTATION.
- **Symptom:** `NOGYRO` in the arming flags
  - Possible cause: the gyro isn't detected: the wrong firmware (target) or a damaged board.
  - What to do: reflash with the correct target, check the board for damage.
- **Symptom:** the compass heading “drifts” with throttle
  - Possible cause: magnetic interference from the power wires.
  - What to do: move the compass with the GPS onto a mast, twist the power wires.
- **Symptom:** baro altitude jumps in hover
  - Possible cause: prop wash hitting the sensor.
  - What to do: cover the barometer with foam.
- **Symptom:** the receiver on a UART doesn't work on F4
  - Possible cause: SBUS on a port without an inverter.
  - What to do: a port with an inverter (labeled) or a protocol without inversion (CRSF).
- **Symptom:** Blackbox cuts off / has gaps
  - Possible cause: a DMA conflict or slow flash.
  - What to do: lower the logging rate, disable the conflicting function (LED), use SD instead of flash.
- **Symptom:** the FC reboots when GPS+VTX+camera are connected
  - Possible cause: the 5 V/9 V BEC current is exceeded.
  - What to do: add up the currents, move a load to a separate BEC.

## references
- Arming Sequence & Safety — Betaflight Documentation | https://www.betaflight.com/docs/wiki/guides/current/Arming-Sequence-And-Safety | primary | A
- Flight Controller Hardware — ArduPilot | https://ardupilot.org/copter/docs/common-autopilots.html | primary | A
- Compass Setup — ArduPilot | https://ardupilot.org/copter/docs/common-compass-setup-advanced.html | primary | A

## checklist
- I know my FC's processor series and that the firmware supports it
- I assigned my board's UARTs to the receiver, GPS, VTX
- I know which power pad is for which peripheral
- The board is on dampers, the orientation is set in the firmware
- The sensors were checked in the configurator after the build
