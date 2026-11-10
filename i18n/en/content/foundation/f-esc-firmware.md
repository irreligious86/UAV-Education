---
id: f-esc-firmware
title: "ESC firmware: Bluejay, AM32, BLHeli_32 and ESC setup"
level: L2
readingTime: 30 min
firmware: Betaflight 4.4+ · ArduPilot 4.5+ · Bluejay 0.21+ · AM32 2.x
status: published
tags:
  - ESC
  - Bluejay
  - AM32
  - DShot
related:
  - f-motors-esc
  - bf-rpm-filter
  - bf-filters
  - bf-blackbox
next:
  - bf-rpm-filter
source: content/foundation/f-esc-firmware.md
source_hash: e6c1fde3e719
---

## summary
An ESC is a separate computer with its own firmware, and that firmware decides the RPM filter, how the motors sound, how hot they run and even whether a motor will start after a crash. The “Motors and ESC” module explained what an ESC does; here you'll learn which firmware goes on which hardware, what bidirectional DShot and EDT are, which ESC settings actually change how it flies (PWM frequency, timing, demagnetization, startup power), how to flash through the flight controller in Betaflight and ArduPilot, and how not to turn a 4-in-1 into a brick.

## theory
### Who's who
| Firmware | Hardware | Status | What matters |
|---|---|---|---|
| BLHeli_S | 8-bit EFM8 (BB1/BB2/BB21) | factory firmware on cheap ESCs, no longer developed | no bidirectional DShot in its original form |
| Bluejay | 8-bit EFM8 BB21 and BB51 (BB1/BB10 only up to version 0.18.1) | open source, actively developed | bidirectional DShot, EDT, PWM frequency 24/48/96 kHz, startup melodies |
| BLHeli_32 | 32-bit ARM | closed source; development and support ended in 2024 | it works, but there will be no updates or new configurator |
| AM32 | 32-bit ARM (STM32F051, G071, AT32F421, GD32, etc.) | open source, actively developed | a replacement for BLHeli_32 where a target exists for the board |

The firmware name on the box tells you about the ESC's microcontroller: “BLHeli_S” means 8-bit, “BLHeli_32” or “AM32” means ARM.

### Bidirectional DShot and EDT
- **DShot** is a digital command protocol from the flight controller to the ESC: DShot300/600 is the speed in kbit/s; no throttle range calibration, with a checksum.
- **Bidirectional DShot (bidir)**: over the same wire, the ESC replies with electrical RPM (eRPM). This is the input for the Betaflight RPM filter and the harmonic notch in ArduPilot. Mechanical RPM = eRPM / (number of poles / 2), so the motor's pole count (usually 14 for 22xx–28xx) must be set in the flight controller.
- **EDT (Extended DShot Telemetry)** adds the ESC's temperature, voltage, current and status to the same replies, with no separate telemetry wire. Supported by Bluejay and AM32; you enable it in the flight controller.

### Settings that change how it flies
- **PWM frequency.** Higher (48–96 kHz) is quieter and smoother at low throttle, with better response; lower (24 kHz) means less switching loss and heat, and more “thrust per amp” on heavy aircraft. For 5" freestyle 48 kHz is typical, for big props 24.
- **Timing (advance).** The commutation advance angle. Higher means more RPM and current, and heat; lower is more efficient, but risks losing sync on sharp throttle changes. Auto/medium is a sensible start.
- **Demagnetization (demag compensation).** Protection against losing sync on sharp throttle changes with big motors. Desyncs (the motor twitches or stops in flight) are treated first by raising the compensation.
- **Startup power (startup/rampup power).** Too high and the windings burn when the motor is jammed; too low and a heavy motor won't start.
- **Rotation direction.** Changed in the ESC firmware or with a DShot command from the flight controller; no need to resolder wires.
- **Melodies and beacon.** The “lost drone” sound after a crash is a useful feature, not a toy.

### How to flash
- **Through the flight controller (passthrough).** The flight controller routes the ESC signal wire through to the computer. Betaflight: connect USB, close the Configurator (the port is busy), open ESC Configurator (esc-configurator.com) in Chrome for BLHeli_S/Bluejay and AM32; for BLHeli_32 use BLHeliSuite32 (the archived version). ArduPilot: `SERVO_BLH_AUTO = 1` for the motors (on planes, `SERVO_BLH_MASK`), DShot protocol, disconnect the GCS, keep USB, and in the configurator choose the “BLHeli32/AM32 Bootloader (Betaflight/Cleanflight)” interface. IOMCU outputs (MAIN) don't support passthrough; you need the FMU/AUX outputs.
- **The target rule.** The firmware is chosen for the specific ESC board (layout/target). A wrong target ranges from misbehavior to burned MOSFETs. The configurator usually shows the current layout; flash only a matching one.
- **Before flashing**: remove the props, save the current settings (a screenshot or a file), flash one ESC at a time if in doubt, use a protected battery (smoke stopper).

### Flight controller: what to enable
- Betaflight: `set motor_pwm_protocol = DSHOT600` (or 300), `set dshot_bidir = ON`, `set motor_poles = 14`; to check, the Motors tab shows RPM, DShot errors ≈ 0%.
- ArduPilot: `MOT_PWM_TYPE` set to DShot300/600, `SERVO_BLH_BDMASK` is the mask of outputs with bidirectional DShot, `SERVO_BLH_POLES` is the pole count; ESC telemetry shows up in the log (`ESC`) and is used by the harmonic notch (`INS_HNTCH_MODE = 3`, driven by ESC telemetry).

{{diagram:esc-firmware-choice|Choosing ESC firmware: an 8-bit ESC on BB21/BB51 gets Bluejay instead of BLHeli_S, a 32-bit one gets AM32 if a target exists, a working BLHeli_32 can stay, and without a target don't flash.}}

## practice
### Step 1. Inventory
Read each ESC through passthrough: firmware and version, layout/target, PWM frequency, timing, direction. Write the table into the aircraft's passport.

### Step 2. Bidir DShot and RPM
If the firmware supports it, enable bidirectional DShot and the pole count in the flight controller. Betaflight: the Motors tab, with the motors spinning (no props), shows RPM and the error percentage. Write down eRPM and mechanical RPM at 10% throttle and check the conversion formula with your pole count.

### Step 3. Flashing (if there's a benefit)
Only if you need bidir DShot or EDT that you don't have: BLHeli_S → Bluejay (only on BB21/BB51 MCUs) or BLHeli_32 → AM32 if a target exists. Save the settings first; take the target from the layout you read. After flashing, restore the direction and check the motor order and direction.

### Step 4. PWM frequency: comparison in flight
Don't measure without props: you need a real operating mode. With props, tethered or in flight: two flights with the same pack at 24 and 48 kHz (Bluejay/AM32). Compare in Blackbox or the log: hover current, ESC temperature (EDT), gyro noise. Write down the conclusion for your aircraft.

The lab counts as done when the ESC table is filled in, the ESC RPM is visible in the flight controller with errors around 0%, and the PWM frequency choice is backed by a current or temperature comparison.

## diagnostics
- **Symptom:** the RPM filter won't enable, the Motors tab shows no RPM
  - Possible cause: ESC firmware without bidir DShot (original BLHeli_S), `dshot_bidir` is off, wrong protocol.
  - What to do: check the ESC firmware, enable bidir, switch to Bluejay/AM32 if needed.
- **Symptom:** a high percentage of DShot errors
  - Possible cause: noise on the signal wires, a DShot speed too high for the wire length, a poor ground.
  - What to do: DShot300 instead of 600, short wires, a common ground, ferrites if needed.
- **Symptom:** the motor twitches or stops on sharp throttle
  - Possible cause: loss of sync (desync).
  - What to do: raise demag compensation, lower the timing or the throttle sharpness, check the bearings and windings.
- **Symptom:** passthrough doesn't find the ESC
  - Possible cause: the Configurator/GCS is open, the ESC isn't powered from the battery, IOMCU outputs in ArduPilot, the protocol isn't DShot.
  - What to do: close other programs, plug in the battery, move to the FMU/AUX outputs, enable DShot.
- **Symptom:** after flashing, the motor doesn't spin or gets hot at rest
  - Possible cause: wrong target/layout.
  - What to do: reflash with the correct target through the bootloader; if the bootloader is damaged, only a programmer will help.

## references
- Bluejay — open-source firmware for BLHeli_S ESCs | https://github.com/bird-sanctuary/bluejay | primary | A
- AM32 — open-source firmware for ARM ESCs | https://github.com/am32-firmware/AM32 | primary | A
- ESC Configurator (web) | https://esc-configurator.com | primary | B
- ArduPilot — BLHeli32, AM32 and BLHeli_S ESCs (passthrough) | https://ardupilot.org/copter/docs/common-blheli32-passthru.html | primary | A
- Betaflight — DShot RPM filtering | https://betaflight.com/docs/wiki/guides/current/DSHOT-RPM-Filtering | primary | A

## checklist
- I can identify the ESC type (8-bit / ARM) and the right firmware for it
- I can explain bidir DShot, eRPM and EDT, and convert eRPM to RPM
- I know what PWM frequency, timing and demagnetization change
- I flash ESCs through the flight controller and check the target
- I enable ESC RPM in Betaflight and ArduPilot
