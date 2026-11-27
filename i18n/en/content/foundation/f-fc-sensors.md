---
id: f-fc-sensors
title: "Flight Controller and Sensors"
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
source_hash: dfcd5736567b
---

## summary
The flight controller (FC) is a small computer that reads the sensors, runs the controller and commands the motors thousands of times a second. This module explains what sits on the board, what each sensor is responsible for, how to read a wiring diagram, and why the same wire behaves differently on different pads. After it, the board diagram stops being a puzzle.

## theory
### Processor
The heart of an FC is a microcontroller. The series determines the capabilities:

- **F4** — the most common and cheapest; limited in the number of UARTs and cannot invert UARTs in hardware (see the module on SBUS).
- **F7** — faster, more UARTs, software inversion.
- **H7** — the most powerful, the standard for ArduPilot and PX4 on complex platforms.

What matters is not “the best processor” but whether the firmware you need supports the board: each firmware has its own list of targets.

### Sensors
- **Gyroscope (gyro)** — angular rate on three axes. The main sensor: stabilization runs on it. It is read thousands of times a second and is sensitive to vibration.
- **Accelerometer (accel)** — acceleration; at rest it shows the direction of gravity. Needed for self-leveling modes (ANGLE) and navigation.
- **Barometer (baro)** — pressure, from which altitude. Sensitive to prop airflow and to light — it is covered with foam.
- **Magnetometer (mag, compass)** — heading. It is afraid of power wires: it is mounted on a mast together with the GPS, away from the current.
- **GPS** — position and velocity. Needed for position hold, return to home and missions.

Combining these sensors is the job of the state estimation filter: in ArduPilot it is the EKF (extended Kalman filter: it fuses the gyro, accelerometer, compass, GPS and baro into a single estimate of attitude, velocity and position, module `ap-ekf`), in Betaflight a simplified scheme without navigation.

### Buses
- **UART** — a serial port: receiver, GPS, VTX, telemetry, companion. The wires cross over (TX → RX).
- **I2C** — a bus for several sensors (compass, external baro, display) over two wires, SDA/SCL.
- **SPI** — a fast bus inside the board: gyro, OSD, flash for logs.

### Pads on the board
Typical labels: `VBAT` (battery voltage), `5V`/`9V`/`10V` (BEC outputs), `GND`, `TX1`/`RX1` (UART1), `SDA`/`SCL` (I2C), `CURR` (current sensor), `LED` (addressable LEDs), `BZ+`/`BZ-` (buzzer), `M1`–`M4` or `S1`–`S8` (outputs to ESCs/servos).

### Mounting
Mounting standards are 30.5×30.5 and 20×20 mm (whoops and some 3" use 25.5×25.5). The frame sets the size: you fit the one the frame is drilled for; an AIO or a stack is chosen by ESC current, mounting and number of UARTs (`f-components-choice`, Step 5a). The board sits on rubber dampers: the gyro should hear the frame's movement, not its vibration. The arrow on the board shows “forward”; if the board is rotated, the rotation is set in the firmware (board alignment / AHRS_ORIENTATION).

### A closer look at the gyro: chips and rates
The gyro is a MEMS chip on SPI. Common ones: MPU6000 (old, 8 kHz output, low noise, discontinued), ICM20602/20689 (noisier, more sensitive to power), ICM42688-P (the modern standard: up to 32 kHz, a configurable hardware anti-aliasing filter — it suppresses frequencies above half the output rate before digitization, otherwise they “fold” into false low frequencies, — low noise), BMI270 (an alternative; up to 6.4 kHz per the datasheet, but Betaflight reads it at 3.2 kHz by default, and the PID loop on it is no faster than 3.2 kHz; with `gyro_hardware_lpf = EXPERIMENTAL` — 6.4 kHz, but without the hardware LPF — the low-pass filter inside the chip; `drivers/accgyro/gyro_sync.c`). The firmware reads the chip over SPI at 8–24 MHz with DMA (direct memory access: data goes into memory without the processor's involvement; the “Embedded” module) and runs the PID loop synchronously with the gyro output (always in 4.x; the PID loop divider is `pid_process_denom`): at 8 kHz — every 125 µs. The chain: chip → hardware LPF (`gyro_hardware_lpf`) → software filters (the “Filters” module) → PID.

**What PID loop rate to set and what it means when buying** (Betaflight 2025.12.5, `config/config.c`). PID loop = gyro rate / `pid_process_denom`. With the RPM filter (it needs bidirectional DShot) the rule is: on F405, F411 and G47x the firmware itself sets DSHOT300 and a 4 kHz PID loop with an 8 kHz gyro (an F405 with `cpu_overclock` from 216 MHz is the exception); on F7, H7 and AT32F435, DSHOT600 and an 8 kHz PID loop are available; with a BMI270 — 3.2 kHz on any MCU (by default). 4 kHz with the RPM filter is a normal setup for 5" and larger, not a “cut-down” one (`bf-filters`, “What the firmware will change by itself”; MCU table — `f-micro-whoop`). To check — `status` in the CLI: `cycle time` (µs) and `GYRO rate` — this is the gyro loop, the PID loop = `GYRO rate` / `get pid_process_denom`; the `CPU` load is there too; the `LOAD` arming flag is a sign that the loop is too fast for the board. What to choose in DShot for this loop — `f-motors-esc`.

Two gyros on a board (dual gyro) — averaging or selection; ArduPilot on H7 — up to three IMUs with separate EKF cores.

{{diagram:fc-signal-path|The signal path inside the FC: gyro → filters → PID → mixer → ESC; the RC command sets the target, Blackbox and OSD take a copy.}}

### What else sits on the board
- **OSD chip** (MAX7456 for analog) or digital OSD over MSP DisplayPort (DJI/Walksnail/HDZero; the protocol the FC uses to send OSD characters to a digital VTX) — draws telemetry into the video.
- **Flash/SD** for Blackbox: 16–32 MB of flash is enough for minutes at 2 kHz (16 MB — 2.7–4.6 min); SD — hours. Log rate: 1 kHz — for PID analysis, 2 kHz (1.6 kHz with BMI270) — for noise and filters (`bf-blackbox`). Written over SPI/SDIO, on F4 it sometimes has DMA conflicts with other functions.
- **BEC**: 5 V (typically 2–3 A total for all consumers) and 9–12 V (for VTX/digital, 2–3 A). Limits — in the board's description; a Raspberry Pi is not powered from an FC pad (the “Connecting peripherals” module).
- **Current sensor** on the PDB (power distribution board)/ESC → the `CURR` pad, the scale `ibata_scale` (Betaflight) / `BATT_AMP_PERVLT` (ArduPilot) is calibrated against a wattmeter.
- **UART inverters** on F4 are only on some ports (for SBUS they are labeled “SBUS”/“RX” with a hardware inverter); F7/H7 invert any port in software.
- **Softserial** — a UART emulated on GPIO: up to 19200 baud, loads the processor; for SmartAudio (VTX control over a single wire, `link-vtx`)/telemetry, not for the receiver.

### What limits the choice of board
The number of UARTs (receiver + GPS + VTX + companion = 4 minimum), a baro and compass (mandatory for INAV/ArduPilot), BEC current for the load, support of the target by the firmware you need **and its version** (ArduPilot — `hwdef`, the board description file in the source tree; Betaflight — unified target: one firmware per MCU type plus a configuration file for the specific board), size and weight, 30.5/20 mm mounting, CAN (DroneCAN — a peripheral protocol on the CAN bus: GPS, compass, ESCs; on large craft, `el-dronecan`), the number of motor/servo outputs (VTOL — 8+).

{{diagram:fc-board-choice-tree|Board selection starts from the firmware: navigation needs a baro, a compass and at least 4 UARTs, while VTOL and large aircraft need an H7 with CAN and 8+ outputs.}}

### Worked example: reading a pinout
A typical H743 board (30.5 mm): `UART1` — RX with an inverter (labeled SBUS), `UART2` — GPS (with `SDA/SCL` next to it for the compass), `UART4` — VTX/DisplayPort (with a `9V` pad next to it), `UART6`/`UART7` — companion/telemetry, `M1–M8` — DShot, `CURR` — current sensor from the ESC, `LED` — addressable strip, `BZ-` — buzzer, `VBAT` — voltage measurement, `5V` — receiver/GPS, `4V5` — powered from USB (for setup without a battery). Reading rule: first power (what comes from where, what current), then the UARTs by function, then I2C, then the “special” pads. Put the “pad → function → device → current” table into the build's spec sheet.

### Place in the system

- **Receives:** 5 V and 9–12 V power from the BEC (`el-power-design`); receiver channels over UART (`link-protocols`); the frame's movement together with its vibration — through the mount (`f-frame-mech`).
- **Provides:** the gyro after the hardware LPF — to the software filters and PID (`bf-filters`); DShot — to the ESCs (`f-motors-esc`); the accelerometer, baro, compass and GPS — to the state estimation filter (`est-sensors`, `ap-ekf`).
- **If you get it wrong here:** the board was rotated but board alignment was not set → stabilization responds on the wrong axis, an uncontrolled takeoff (tree 6 in `diag-troubleshooting`). The compass was left next to the power wires → the heading drifts with throttle, “toilet bowling” in Loiter (`el-emi`). SBUS on an F4 port without an inverter → no channels, the RXLOSS flag (`link-protocols`).

## practice
### Lab: read your board's diagram
1. Find the wiring diagram of your FC from the manufacturer.
2. Write down which UART is free for the receiver, which for the GPS, which for the VTX.
3. Find which pad powers the VTX and camera and what current that BEC provides.
4. Note whether there is a pad with an inverter (for SBUS on F4) and where to solder the LED and buzzer.
5. Save the result in the build log next to a photo of the board.

### Checking the sensors after assembly
1. Connect the FC to the configurator (Betaflight App, Mission Planner or QGroundControl).
2. Tilt the drone: the model on the screen should repeat the movements on all three axes without delay.
3. Calibrate the accelerometer on a level surface.
4. Check that the barometer shows a change in altitude when you lift the drone by hand, and that the compass shows the heading.

### What to write down: the board map
| Resource | Purpose | Note |
|---|---|---|
| UART1 | receiver (CRSF) | RX1/TX1 pads next to 5 V |
| UART2 | GPS | 5 V from a separate pad |
| UART3 | VTX (MSP/SmartAudio) | |
| UART4 | free | |
| 9 V BEC | VTX and camera | current per the board datasheet, e.g. 2 A |
| 5 V BEC | receiver, GPS, LED | |
| SBUS pad | with an inverter (F4) or not needed (F7/H7) | |

The values in the table are an example of the format: fill it in from your board's diagram, noting the source (diagram page, labeled photo).

### What the check should give
- **Gyro and accelerometer.** The model on the Setup tab repeats the tilts immediately and in the right direction on all axes. If an axis is inverted or the model “looks” the wrong way — wrong board orientation (`align_board_*` in Betaflight; in 2025.12 the separate `gyro_1_sensor_align`/`gyro_1_align_*` from 4.5 were removed, so after an update the model on the Setup tab is checked again; `AHRS_ORIENTATION` in ArduPilot), and this is fixed before the first flight.
- **Accelerometer calibration** on a level surface; after it the horizon is level.
- **Barometer.** When you raise your hand by a meter, the altitude grows by about a meter. A barometer in direct airflow or in light is noisy — it is covered with a piece of foam.
- **Compass** (if present) shows a heading that changes when you turn the aircraft. Next to power wires it lies — the “Interference” module.

Self-check: the lab is done when all the UARTs are assigned a purpose, the power pads and BEC current are written down with their source, the pad with the inverter is found or it is noted that it is not needed, and all the sensors were checked in the configurator after assembly and gave the expected result: the model repeats the tilts immediately and in the right direction on three axes, after calibration the horizon is level, the barometer shows about a meter when raised by a meter, the compass heading changes when turning — the result of each check is written down.

## diagnostics
- **Symptom:** the model in the configurator rotates the wrong way
  - Possible cause: the board is mounted rotated, and the rotation is not set in the firmware.
  - What to do: set board alignment / AHRS_ORIENTATION.
- **Symptom:** `NOGYRO` in the arming flags
  - Possible cause: the gyro is not detected — the wrong firmware (target) or a damaged board.
  - What to do: reflash with the correct target, check the board for damage.
- **Symptom:** the compass heading “drifts” with throttle
  - Possible cause: magnetic interference from the power wires.
  - What to do: move the compass with the GPS onto a mast, twist the power wires.
- **Symptom:** the baro altitude jumps in hover
  - Possible cause: airflow from the props hitting the sensor.
  - What to do: cover the barometer with foam.
- **Symptom:** the receiver on a UART does not work on F4
  - Possible cause: SBUS on a port without an inverter.
  - What to do: a port with an inverter (labeled) or a protocol without inversion (CRSF).
- **Symptom:** Blackbox cuts off/has gaps
  - Possible cause: a DMA conflict or slow flash.
  - What to do: lower the logging rate, disable the conflicting function (LED), SD instead of flash.
- **Symptom:** the FC reboots when GPS+VTX+camera are connected
  - Possible cause: the 5 V/9 V BEC current is exceeded.
  - What to do: add up the currents, move a consumer to a separate BEC.

## references
- Arming Sequence & Safety — Betaflight Documentation | https://www.betaflight.com/docs/wiki/guides/current/Arming-Sequence-And-Safety | primary | A
- Flight Controller Hardware — ArduPilot | https://ardupilot.org/copter/docs/common-autopilots.html | primary | A
- Compass Setup — ArduPilot | https://ardupilot.org/copter/docs/common-compass-setup-advanced.html | primary | A

## checklist
- I know my FC's processor series and that the firmware supports it
- I assigned my board's UARTs to the receiver, GPS, VTX
- I know which power pad is for which peripheral
- The board is on dampers, the orientation is set in the firmware
- The sensors were checked in the configurator after assembly
