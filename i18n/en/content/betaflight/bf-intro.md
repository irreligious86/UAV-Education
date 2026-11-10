---
id: bf-intro
title: "Introduction to Betaflight"
level: L1
readingTime: 25 min
firmware: Betaflight 4.5+
status: published
tags:
  - Betaflight
  - getting started
  - configurator
  - setup
references:
  - title: "Getting Started — Betaflight Documentation"
    url: "https://betaflight.com/docs/wiki/getting-started"
    tier: primary
    stack: betaflight
  - title: "Betaflight 4.5 Release Notes"
    url: "https://www.betaflight.com/docs/wiki/release/Betaflight-4-5-Release-Notes"
    tier: primary
    stack: betaflight
  - title: "Betaflight Configurator — Official Web App"
    url: "https://app.betaflight.com"
    tier: primary
    stack: betaflight
  - title: "Betaflight Advanced Guide — iFlight"
    url: "https://help.iflight-rc.eu/en-US/betaflight-advanced-guide-951396"
    tier: secondary
    stack: betaflight
  - title: "Betaflight FAQ — How to Start"
    url: "https://www.betaflight.com/docs/wiki/guides/current/FAQ"
    tier: primary
    stack: betaflight
  - title: "Betaflight Configurator — Releases"
    url: "https://github.com/betaflight/betaflight-configurator/releases"
    tier: primary
    stack: betaflight
related:
  - bf-ports
  - bf-modes-osd
  - bf-cli
next:
  - bf-ports
source: content/betaflight/bf-intro.md
source_hash: 18aabbcd6bb5
---

## summary

Betaflight is open-source firmware for multicopter flight controllers with a focus on **low control latency** and flexible setup. This article walks the chain from installing the configurator to a safe first flight.

**After reading, you will be able to:**

- flash the FC and make a configuration **backup** (`diff all`);
- set up **ports, receiver, modes** and sensor calibration;
- check **motors and failsafe** before flying.

## theory

### What Betaflight is

Betaflight is a fork of **Cleanflight** (the successor of Baseflight / the STM32 port of MultiWii). The stack's main emphasis is **performance**: minimal **latency** and a high gyro loop rate (up to **8 kHz**).

**Supported hardware:** flight controllers based on **STM32** (F4, F7, H7). **Firmware features:**

- multi-profile **PID**;
- gyro and **D-term** filtering;
- digital ESC protocols (**DShot**, ProShot);
- **Blackbox** for logs;
- **CLI** for fine-grained setup.

### Firmware architecture

The firmware is modular, and tasks run in real time. **Main tasks:**

- **Gyro task** — reads the gyro (up to 8 kHz), filters.
- **PID task** — motor output from the **setpoint** vs **gyro** error.
- **RX task** — the receiver (CRSF, SBUS, ELRS, etc.).
- **Scheduler** — splits time between tasks.

**PID loop:** the `pid_process_denom` parameter sets the PID loop rate. Example: gyro **8 kHz**, `pid_process_denom = 2` → PID **4 kHz** (a typical starting point for most builds).

### Firmware versions and compatibility

**Betaflight 4.5** is the previous stable branch (last release 4.5.5); the current ones are 2025.12.x and 2026.6.x. Key changes:

- GPS (including **M10** modules) and **GPS Rescue**;
- magnetometers;
- **Angle / Horizon** with the *Earth referencing* option;
- fonts for HD VTX (Walksnail);
- filtering aware of **RPM** harmonics.

**Important:** going from **4.4 → 4.5** requires a **Full Chip Erase** and setup from scratch. Old **CLI dumps** from 4.3 and earlier are often **incompatible** because of renamed parameters and changed ranges.

### The Betaflight ecosystem

Besides the firmware there is **Betaflight Configurator**. The web app was already available for 4.5 (Configurator 10.10), and since version **2025.12** the **web configurator** (`https://app.betaflight.com`) over **WebUSB / WebSerial** is the primary one. Native apps are still available for Android.

### Target, unified target and Cloud Build
The firmware is built for a **target** — a board description: the processor, which pins are wired to what (`resource`), which gyro sits on which SPI. Since 4.3 nearly all boards are **unified targets**: one binary per processor family (e.g. `STM32F405`) plus a text board config (`board_name`, `manufacturer_id`, a set of `resource`/`set` lines) that the configurator loads when flashing. Cloud Build (4.4+) builds the binary on the server with the feature set you pick: receiver protocol, OSD, GPS, telemetry, LED — whatever you didn't tick isn't in the firmware (a typical cause of “the receiver is silent”). `version` in the CLI shows the version, target, date and git revision of the build; `BUILD KEY` (the build key for reproducing it) is printed by `status`, and build.betaflight.com returns the option list for that key.

### What the scheduler does every 125 µs
`fc/tasks.c` describes tasks with a period and a priority; `scheduler/scheduler.c` picks among them. The critical ones are `GYRO` (reading, filters) and `PID` (`taskMainPidLoop`: RC command → PID → mixer → DShot) — at the gyro rate / `pid_process_denom`. The rest run on whatever time is left: `RX` (receiving and processing frames, event-driven), `SERIAL`, `BATTERY_*`, `GPS`, `OSD` (per `osd_framerate_hz`), `BLACKBOX`, `TELEMETRY`, `LED_STRIP`. The CLI command `tasks` shows the actual period, average and maximum time of each task, plus CPU load; `status` shows the gyro rate, load and arming flags. Overload (> 85–90% on an F4 at 8 kHz) means skipped tasks, jitter and the `LOAD` flag: fix it with `pid_process_denom = 2` or by turning features off.

### Setup map: where things live
| What | Where in the configurator | Key CLI parameters |
|---|---|---|
| Ports and devices | Ports | `serial`, `resource`, `serialrx_provider` |
| Receiver, channels, rates | Receiver | `map`, `rates_type`, `roll_rc_rate`… |
| Modes on switches | Modes | `aux` |
| Motors, ESC, protocol | Motors | `motor_pwm_protocol`, `dshot_bidir`, `motor_poles`, `dshot_idle_value` (2025.12: `motor_idle`) |
| PID, filters, FF | PID Tuning | `set p_roll`… `simplified_*`, `gyro_lpf*`, `rpm_filter_*` |
| OSD | OSD | `osd_*_pos`, `osd_warn_bitmask` |
| Blackbox | Blackbox | `blackbox_device`, `blackbox_sample_rate`, `debug_mode` |
| Failsafe | Failsafe | `failsafe_procedure`, `failsafe_delay`, `rxfail` |
| Firmware | Firmware Flasher | — |
Profiles: up to 4 PID profiles (`profile`) and 4 rate profiles (`rateprofile`), switchable with a switch/adjustments — one “calm”, one “race”.

### Worked example: first-setup order
Firmware (Cloud Build: CRSF, OSD HD, GPS if you have one) → default `resource`/target → Ports (receiver UART) → Receiver (CRSF, check the channels and `map` AETR) → Motors (DShot600, `motor_poles`, `dshot_bidir`, direction without props) → Modes (ARM, ANGLE, BEEPER, FAILSAFE) → Failsafe (DROP for the first flight) → OSD (voltage, LQ, timer, warnings) → Blackbox (2 kHz) → `diff all` into the repo (the “CI” module). Fly the first flight on default PIDs: Betaflight 4.5 “out of the box” flies a 5" better than most beginners' hand tunes; tune after you have logs.

{{diagram:bf-setup-map|First-setup order: backup → Ports → Receiver → Modes → Motors (without propellers) → OSD → PID and filters from the log.}}

## practice

### Installing Betaflight Configurator

**Option A — web (recommended on a PC):**

1. A **Chromium**-based browser (Chrome, Edge, Opera).
2. Open `https://app.betaflight.com`.
3. On the first FC connection, allow **USB** access.

**Option B — offline or an older environment:**

- the installer from GitHub Releases: `https://github.com/betaflight/betaflight-configurator/releases` (Windows / macOS / Linux).

### Connecting the flight controller

1. A USB cable **with data lines** (not “charge only”).
2. In the configurator: port (**COM*** / `/dev/ttyACM*`) → **Connect**.
3. If no port shows up — drivers (**ImpulseRC Driver Fixer** or manually on Windows).

**Check:** on the **Setup** tab the 3D model follows your tilts. No reaction — the accelerometer or the connection.

### Backup (CLI)

Before any changes: **CLI** tab → enter the command below → **Save to File**.

```text
diff all
```

`diff all` saves only the **differences from defaults** — handy for restoring. `dump all` is for deep troubleshooting; it is not recommended for moving a config **between major versions**.

### Updating the firmware (Firmware Flasher)

1. **Firmware Flasher** — the target controller (often detected over USB).
2. Version — the latest stable **4.5.x**.
3. Enable **Full chip erase** when changing the major branch.
4. **Load Firmware [Online]** → **Flash Firmware**; don't unplug USB until it finishes.
5. After the reboot — restore the config from the backup (**CLI**) or set it up again.

### Configuration tab

- **Mixer** — frame type (**Quad X** for a typical FPV quad).
- **Board and Sensor Alignment** — **Yaw degrees**, if the FC is rotated on the frame.
- **Battery Voltage** — **VBAT** to display voltage.
- **ESC/Motor** — in the current app the DShot protocol, **Bidirectional DShot** and Motor idle are set on the **Motors** tab.
- **Motor Stop** — if the motors must not spin at zero throttle after arming.

### Ports tab

- **USB VCP** — a separate row in Ports (not UART1), MSP on it is mandatory; UART1 is a regular hardware port.
- **UART2/3/4** — **Serial RX** on the port the receiver is soldered to.
- **UART5** (example) — **GPS**, baud **57600** or **115200**.

### Receiver tab

- **Serial-based receiver** for CRSF / SBUS / FPORT.
- **Provider:** **CRSF** (ELRS, TBS), **SBUS** (FrSky, DJI, etc.).
- Sticks on the radio → the sliders in the configurator must move.
- Range **1000–2000** (center **1500**); otherwise **rxrange** in the CLI or endpoints on the radio.
- **Channel Map** (e.g. **AETR**, **TAER**) if channels are mixed up.

### Modes tab

Assign **AUX** channels to modes. A short rundown:

- **ARM** — enables the motors (a 2-position switch is best).
- **ANGLE** — self-leveling, for learning.
- **HORIZON** — a hybrid of stabilization and acro.
- **ACRO** — the default; it has no row of its own in the list.
- **BEEPER** — for finding the drone.
- **GPS RESCUE** — if GPS is set up.

For each mode: **Add Range** → pick the channel and the switch-position range.

### Sensor calibration

- **Accelerometer:** **Setup**, a level surface → **Calibrate Accelerometer**.
- **Magnetometer:** **Calibrate Magnetometer**, ~30 s of rotating around the axes; check that it agrees with the real heading.

### ESCs and motors (without propellers!)

**Danger:** always **remove the propellers** before testing motors.

1. **Motors** — enable **I understand the risks**.
2. **Motor 1** — check that it matches the physical motor (in Betaflight Quad X: Motor 1 — rear right, 2 — front right, 3 — rear left, 4 — front left).
3. Spin direction — per the frame diagram; fix it by swapping wires or in **BLHeli / Bluejay**.
4. Wrong order/direction is a typical cause of flipping on takeoff.

### Preflight check

- **ARM without props** — the motors spin at low RPM.
- **Tilt forward** — the front motors briefly add throttle (the stabilization reacts).
- **Failsafe** — switch off the radio; the expected behavior (landing / **GPS Rescue**).
- **OSD** — voltage, timer, mode (if you use a video link).

## diagnostics
- **Symptom:** The configurator doesn't see the controller, the port doesn't appear
  - Possible cause: drivers not installed (Windows), a poor USB cable, a port conflict.
  - What to do: replace the cable with one that carries data. On Windows, install drivers with ImpulseRC Driver Fixer. Reboot the computer. Try another USB port.

- **Symptom:** The controller connects, but the 3D model doesn't respond to movement
  - Possible cause: the accelerometer isn't calibrated, the sensor is damaged.
  - What to do: calibrate the accelerometer on a level surface. If that doesn't help, check status in the CLI and make sure ACCEL is detected. Check the wires and soldering.

- **Symptom:** The drone won't arm, an error blinks in the top right corner (e.g. RXLOSS)
  - Possible cause: the receiver gets no signal, the port isn't set up, wrong protocol.
  - What to do: check that the right UART is selected for Serial RX and the right protocol (CRSF/SBUS) is chosen. Make sure the radio is on and the receiver is bound (the LED on the receiver is solid). On the Receiver tab check that the sliders move.

- **Symptom:** The motors spin, but the drone doesn't take off or flips over when you try
  - Possible cause: wrong motor spin direction, wrong connection order, wrong FC orientation.
  - What to do: on the Motors tab check the motor order (Motor 1 — rear right, Motor 2 — front right, and so on). Check the spin direction (using the markings on the propellers). Make sure the FC rotation angle (Yaw degrees) is set correctly.

- **Symptom:** The sticks move in the configurator, but the values don't reach 1000–2000
  - Possible cause: the endpoints on the radio are set wrong.
  - What to do: in the radio settings adjust Travel/Endpoints to 1000–2000 µs. Alternatively, use the CLI command rxrange to correct it.

- **Symptom:** The drone arms, but the motors don't spin (with MOTOR_STOP off)
  - Possible cause: minimum throttle (min_throttle) is too low to start the motors.
  - What to do: with DShot, `min_throttle` isn't used: on the Motors tab raise Motor Idle (`dshot_idle_value` in 4.5, `motor_idle` in 2025.12; default 5.5%).
- **Symptom:** after flashing, the receiver/GPS doesn't work even though the wiring is correct
  - Possible cause: the feature wasn't included in Cloud Build.
  - What to do: `version` → the option list; reflash with the ones you need.
- **Symptom:** `LOAD` in the arming flags or CPU > 90%
  - Possible cause: an F4 at 8 kHz with every feature on.
  - What to do: `pid_process_denom = 2`, disable LED/extra telemetry, use `tasks` to find the heavy ones.

## references
- Getting Started — Betaflight Documentation | https://betaflight.com/docs/wiki/getting-started | primary | A
- Betaflight 4.5 Release Notes | https://www.betaflight.com/docs/wiki/release/Betaflight-4-5-Release-Notes | primary | A
- Betaflight Configurator — Official Web App | https://app.betaflight.com | primary | A
- Betaflight CLI Documentation — Command Reference | https://betaflight.com/docs/wiki/guides/current/Cli | primary | A
- Betaflight Configurator — GitHub Releases | https://github.com/betaflight/betaflight-configurator/releases | primary | A
- Betaflight FAQ — How to Start | https://www.betaflight.com/docs/wiki/guides/current/FAQ | primary | A
- Betaflight Advanced Guide — iFlight | https://help.iflight-rc.eu/en-US/betaflight-advanced-guide-951396 | secondary | B
- GPS Rescue 4.5 — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/GPS-Rescue-v4-5 | primary | A
- Betaflight — Arming sequence and safety (arming flags) | https://www.betaflight.com/docs/wiki/guides/current/Arming-Sequence-And-Safety | secondary | B
- Joshua Bardwell — Betaflight Setup Tutorial | https://www.youtube.com/watch?v=xSzO6HP6yzs | secondary | B
