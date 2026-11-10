---
id: bf-custom
title: "Custom firmware builds"
level: L4
readingTime: 25 min
firmware: Betaflight 4.5+ / ArduPilot 4.5+
status: published
added: 2026-11-07
tags:
  - cloud build
  - build
  - targets
related:
  - bf-cli
  - ap-quadplane
next: []
source: content/betaflight/bf-custom.md
source_hash: ae19af8cef46
---

## summary
A flight controller's flash memory isn't infinite: you can't enable everything at once, which means firmware for your aircraft is a choice. This module explains how to build Betaflight with your own feature set via Cloud Build and when you need custom defines, and how to build your own ArduPilot variant from source — for example, dropping GPS and unneeded drivers to fit what you need on an F405. With an example from the HeeWing project.

## theory
### Why build at all
- On an F411/F405 the standard firmware with every option doesn't fit, or fits without a feature you need.
- You need an option that isn't in the standard set (rangefinder, transponder, an exotic protocol).
- You need to remove what isn't and won't be on board (GPS, compass, OSD chip), freeing up flash and memory.

### Betaflight: Cloud Build
Since 4.4, a cloud server builds the firmware for your list of options. In Firmware Flasher you pick the receiver protocol, OSD type, telemetry, ESC protocol and so on; each option is a `USE_*` flag in the source, and you enter the name without the prefix. Your choice pulls in dependencies by itself: CRSF adds CRSF telemetry, `GPS` adds GPS Rescue and OSD elements. Drivers for the specific board (gyro, flash, OSD chip) are added automatically based on the target.

**Custom defines** is a field in expert mode for options outside the lists. They aren't tested on every board; if an option needs a pin, you assign it in the CLI with `resource`. If the firmware is too big, the build simply fails.

Checking on the board: the `version` command in the CLI shows the version and target, and `status` prints the `BUILD KEY` — the key Cloud Build uses to build exactly the same firmware again. `diff all` doesn't contain the key — save the `status` output separately.

### ArduPilot: building from source
ArduPilot is built with `waf`: `./waf configure --board <board>` and `./waf copter` (or `plane`). The target is described in `libraries/AP_HAL_ChibiOS/hwdef/<board>/hwdef.dat`: pins, buses, which drivers to include. That's also where `define` lines switch off what you don't need.

For boards with small flash there are trimmed configurations: many features in the code are wrapped in `#if AP_<FEATURE>_ENABLED` checks, and the hwdef can set `define AP_<FEATURE>_ENABLED 0`. The Custom Firmware Builder web tool (linked from the “Building the code” documentation) does the same through a UI: tick the boxes, get the firmware.

### Case: HeeWing F405 without GPS
The stock F405 in the HeeWing T1 project is a board with limited flash: no Lua scripting, some features trimmed. The firmware variants planned for it: remove GPS support (on this build it isn't used for arming or basic flight) and unneeded drivers to free up room for what's needed. That's a sensible decision if you understand the consequences: without GPS in the firmware there is neither RTL nor a coordinate-based geofence — not just “for now”, but at all.

### Rules for custom builds
1. Keep the build configuration in git next to the parameters: the Betaflight option list or the ArduPilot `hwdef` patch.
2. Name the build with the date and commit hash; the `version` output and the BUILD KEY from `status` must match the record.
3. Before flashing — a full backup (`diff all` / parameter file); after — re-read everything critical.
4. Don't mix: a custom build + a stock config from another version = unpredictability.

### Building Betaflight locally (when Cloud Build doesn't fit)
```bash
git clone https://github.com/betaflight/betaflight && cd betaflight
make arm_sdk_install                      # toolchain
make configs                              # unified target configs
make STM32H743 EXTRA_FLAGS="-DUSE_RANGEFINDER -DUSE_GPS_LAP_TIMER"   # family target + extra defines
# or with a specific board's config:
make SPEEDYBEEF405V4 EXTRA_FLAGS="-DUSE_..."
```
The result is `obj/betaflight_<ver>_<target>.hex`, flashed with the configurator's “Load Firmware [Local]”. To test without hardware — `make SITL` and `make test` (gtest unit tests, the “How to read the source” module). The firmware size is printed at the end of the build; an F411 (512 KB flash) requires disabling `-DUSE_*` options via `EXTRA_FLAGS` with a minus, or trimmed target configs.

### What breaks after a custom build and how to check
1. via the BUILD KEY from `status` (`https://build.betaflight.com/api/builds/<key>/json`) — the expected options; 2. `status` — the gyro is detected; 3. Ports/Receiver — the receiver responds; 4. Motors — DShot and bidir work without props; 5. the OSD is visible; 6. `diff all` matches the backup in meaning. Put the checklist in the aircraft's log together with the commit hash and `EXTRA_FLAGS`.

{{diagram:fw-build-paths|Which build path to choose: options — Cloud Build or custom.ardupilot.org, your own code — a local build.}}

## practice
### Betaflight: a build for a specific aircraft
1. Firmware Flasher → board target → version.
2. Options: receiver (CRSF), OSD (analog or digital), telemetry, ESC protocol (DShot), GPS only if you have one.
3. Expert mode → Custom Defines, if you need something outside the lists.
4. Build → Flash. After flashing, in the CLI: `version` and `status` — save the output (the BUILD KEY is in `status`) into the drone's folder.
5. Restore the config from a `diff all` of **the same** major version, re-read the key parameters.

### ArduPilot: building from source
```
git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git
cd ardupilot
Tools/environment_install/install-prereqs-ubuntu.sh -y
./waf configure --board MatekF405-Wing   # example board name; use yours
./waf plane
ls build/MatekF405-Wing/bin/             # arduplane.apj / .bin / .hex
```

Disabling a feature: add a line like `define AP_<FEATURE>_ENABLED 0` to the board's `hwdef.dat` (or to a separate extra hwdef file), rebuild, check the size in the build output. For a first attempt, the Custom Firmware Builder on the website is simpler.

### Lab
Build two ArduPlane firmwares for your board: a standard one and one without a single subsystem. Compare the binary sizes, flash the second onto a SITL-like bench (the board on the desk) and make sure the disabled subsystem really disappeared from the parameters.

### What you should end up with and what to record
- **Betaflight.** After flashing the trimmed build, `version` and `status` are saved to a file next to the config (the BUILD KEY lets you rebuild exactly the same firmware). The config is restored from a `diff all` of the same major version, and the key parameters are re-read with `get`. Settings for disabled options are absent from the CLI — check, for example, that after a build without GPS the `get gps` command finds nothing.
- **ArduPilot.** The build output shows the firmware size and the free flash. Record both numbers for the two builds: the difference is the price of the disabled subsystem in bytes. After flashing, the subsystem's parameters (its prefix) disappear from the full parameter list in the GCS — take a screenshot of a search by the prefix before and after.
- **Git.** The file with the build options (`hwdef` with `define AP_<FEATURE>_ENABLED 0` or the Custom Firmware Build option list) sits in the repo next to the config. Six months from now, the question “why doesn't this drone have X” is answered by a commit, not by memory.

The lab counts as done when the standard and trimmed firmwares are built, the sizes are compared and the `version`/BUILD KEY output is saved, the disappearance of the disabled subsystem from the parameters is confirmed by a screenshot or CLI output, and the build configuration is in git.

## diagnostics
- **Symptom:** Cloud Build fails with a size error
  - Possible cause: too many options for the board's flash.
  - What to do: remove what you don't use (a second OSD, extra protocols, GPS without a GPS).
- **Symptom:** after a custom build the feature is “there” but doesn't work
  - Possible cause: the option needs a pin that wasn't assigned with `resource`.
  - What to do: `resource` in the CLI, reboot, check `status`.
- **Symptom:** ArduPilot `waf configure` can't find the board
  - Possible cause: a typo in the name, missing submodules.
  - What to do: `./waf list_boards`, `git submodule update --init --recursive`.
- **Symptom:** after a custom build some parameters disappeared
  - Possible cause: that's exactly the effect of the disabled subsystem.
  - What to do: compare with the build record; if you need the parameter, bring the feature back.

## references
- Build Options — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/Build-Options | primary | A
- Defines — Betaflight Development | https://betaflight.com/docs/development/Defines | primary | A
- Building the code — ArduPilot Dev | https://ardupilot.org/dev/docs/building-the-code.html | primary | A
- Setting up SITL / build environment — ArduPilot Dev | https://ardupilot.org/dev/docs/SITL-setup-landingpage.html | primary | A

## checklist
- I know which options my aircraft actually needs
- The build is described in git: options / hwdef patch, date, hash
- The `version` and `status` (BUILD KEY) output is saved after flashing
- The config is restored from the same major version
- I understand what I lose by disabling a subsystem
