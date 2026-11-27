---
id: bf-custom
title: "Custom firmware builds"
level: L4
readingTime: 40 min
firmware: Betaflight 4.5 (checked against 4.5.3, Configurator 10.10) and 2025.12 (2025.12.5) / ArduPilot 4.5+
status: published
added: 2026-11-07
tags:
  - cloud build
  - build
  - targets
related:
  - bf-cli
  - ap-quadplane
  - bf-hd-osd-video
  - bf-led-buzzer
next: []
source: content/betaflight/bf-custom.md
source_hash: 48ca1cd5b0ba
---

## summary
A flight controller's flash memory is not elastic: you cannot enable everything at once, so firmware for your aircraft is a matter of choice. This module goes through Cloud Build in Betaflight using the 4.5.3 and Configurator 10.10 sources: what is sent to the build server, which option groups exist, what Core Only and Custom Defines do, where the build key can be seen on the board and how to check what is inside the firmware. Separately — why a missing option disappears silently and how to move a `diff all` into a build with a different set of options without losing half of the settings. For ArduPilot — building from source with subsystems disabled (the HeeWing F405 case). The lab without hardware is a Python port of the 4.5.3 CLI logic that predicts which `diff all` lines will not be accepted and whether the config will be saved.

## theory
### Why build at all
- On an F411/F405 the standard firmware with all options does not fit, or fits without the feature you need.
- You need an option that is not in the standard set (a rangefinder, a transponder, an exotic protocol).
- You need to remove what is not on board and never will be (GPS, compass, OSD chip), freeing up flash and memory.

How much space there really is (4.5.3 linker scripts): the F411 and F722 have 512 KB of flash, the F405 has 1 MB, the H743 — 2 MB. After the config sector (16 KB) and the first 16 KB sector (the vector table, and on the F411 also the initialized data) the main code (`.text`) must fit into the `FLASH1` region (on the F722 it is called `AXIM_FLASH1`): 480 KB on the F411/F722 and 992 KB on the F405. The sum of the code regions is larger (496 and 1008 KB), but a build usually runs out of room in `FLASH1`; from here on the course counts by it. A “classic” build without the cloud (this is how the project's CI and a local `make` without options build) includes almost all features only on boards with 1024 KB of flash or more. On 512 KB boards that block of `common_pre.h` is skipped entirely: no GPS, LED strip, transponder, rangefinder or MAVLink telemetry. That is why GPS on an F411 is possible only through a custom build.

### Betaflight: Cloud Build
Starting with 4.4 the firmware is built by the server build.betaflight.com for your list of options. Betaflight firmware consists of two parts:

- **the target** — the processor family (`STM32F405`, `STM32F411`, `STM32H743`…), the common code;
- **the board config** (`config.h` from the betaflight/config repository): pins, gyro, flash, OSD chip. The drivers for a specific board come from it automatically; you do not select them.

What happens when the build button is pressed (per `firmware_flasher.js` of Configurator 10.10):

1. The Configurator sends a request with three fields to `/api/builds`: `target` (the board), `release` (the version) and `options` — a list of strings (in Expert Mode for Development also `commit`). The first string is `CLOUD_BUILD`, followed by the values of the selected items of all the lists, for example `USE_SERIALRX_CRSF`, `USE_DSHOT`, `USE_OSD_SD`, `USE_GPS`.
2. The server builds the firmware with these flags. In the sources `CLOUD_BUILD` turns off the classic set (`common_pre.h:52–272`): the firmware gets what came in the list and what those options pull in. In addition, the server explicitly adds base flags that are not in the Configurator list (for example, without `USE_SERIALRX` and `USE_TELEMETRY`, `common_post.h` would strip CRSF out entirely); which ones exactly is not visible in the open code — this is the course's inference from the fact that cloud builds with CRSF work. The exact set is shown by `/api/builds/<key>/json` and the build log. For example, `USE_GPS` adds GPS Rescue and the NMEA/UBLOX drivers, and `USE_OSD_SD` or `USE_OSD_HD` adds the OSD, CMS and the menus.
3. The build key `BUILD_KEY` is embedded in the firmware (`build/version.c:33–43`). It is 32 characters by which the server finds the request and the build log. An identical request is served from the cache: status `success (cached)`.
4. Flashing. If Expert Mode is off, the Configurator always erases the whole flash (Full chip erase, `firmware_flasher.js:581–585`): the config is gone, so `diff all` is needed before flashing, not after.

If a board is connected to the Firmware Flasher, the Configurator reads its key and fills the lists with the options of the current build (`loadOptionsByBuildKey`). This is the simplest way to “repeat it, but add one option”.

{{diagram:bf-cloud-build-pipeline|The Cloud Build path: an option that was not in the request is absent from the code — the setting, the CLI command and the tab disappear without a single error message.}}

The build types in the version list: `Release`, `Release And Release Candidate`, `Development`. For `Development` in Expert Mode you can select a specific commit.

### Option groups (Configurator 10.10 ↔ Betaflight 4.5)
The list comes from the server (`/api/options/<version>`). The 4.5 firmware keeps a copy of it in `msp/msp_build_info.h`: from it the board tells the Configurator what was built into it (MSP_BUILD_INFO, API 1.46).

| Group in the interface | 4.5 options (`USE_` + name) | Notes |
|---|---|---|
| Radio Protocol | SERIALRX_CRSF, SERIALRX_FPORT, SERIALRX_GHST, SERIALRX_IBUS, SERIALRX_JETIEXBUS, RX_PPM, SERIALRX_SBUS, SERIALRX_SPEKTRUM, SERIALRX_SRXL2, SERIALRX_SUMD, SERIALRX_SUMH, SERIALRX_XBUS | for CRSF, FPort and GHST the telemetry field is locked with the label `Automatically Included` |
| Telemetry Protocol | TELEMETRY_FRSKY_HUB, TELEMETRY_HOTT, TELEMETRY_IBUS_EXTENDED, TELEMETRY_LTM, TELEMETRY_MAVLINK, TELEMETRY_SMARTPORT, TELEMETRY_SRXL | ELRS/CRSF telemetry is not selected separately |
| Other Options | ACRO_TRAINER, AKK_SMARTAUDIO, BATTERY_CONTINUE, CAMERA_CONTROL, DASHBOARD, EMFAT_TOOLS, ESCSERIAL_SIMONK, FRSKYOSD, GPS, LED_STRIP, LED_STRIP_64, MAG, OSD_SD, OSD_HD, PINIO, RACE_PRO, SERVOS, VTX | the OSD is here too: `OSD_SD` — analog (MAX7456), `OSD_HD` — digital over MSP DisplayPort |
| Motor Protocol | BRUSHED, DSHOT, MULTISHOT, ONESHOT, PROSHOT, PWM_OUTPUT | with `CLOUD_BUILD` DShot is not enabled automatically (`common_pre.h:52–53`): without `DSHOT` in the list there is no DShot in the firmware |

*2025.12:* `SERIALRX_MAVLINK`, `ALTITUDE_HOLD`, `POSITION_HOLD`, `WING`, `CHIRP`, `SOFTSERIAL` were added to the list, MSP API 1.47. Configurator 10.10 works only with API up to 1.46, so 2025.12 firmware is built and flashed in Betaflight App (`bf-intro`).

Dependency traps from `common_pre.h` of 4.5.3:

- only `OSD_HD` without `OSD_SD` → the MAX7456 driver is stripped out (`#undef USE_MAX7456`, line 414), even if the chip is soldered on the board: the analog OSD will be gone;
- `LED_STRIP` gives 32 LEDs, `LED_STRIP_64` — 64 (`LED_STRIP_MAX_LENGTH`); on the F411 `LED_STRIP_64` is not supported: an `#error` in `target/STM32F411/target.h:87–88`, and the build will fail;
- `VTX` pulls in SmartAudio, Tramp, MSP VTX and the VTX tables;
- without `MAG` there is no compass, without `GPS` there is no GPS Rescue, and the GPS tab is hidden.

{{lesson:bf-hd-osd-video|Which defaults of `vcd_video_system` and `osd_displayport_device` the OSD (HD) option gives, the MSP + VTX_MSP port mask, and setting up DJI, Walksnail and HDZero.}}

### Core Only and Custom Defines
**Core Only** (the `coreBuildModeCheckbox` checkbox) sends the single string `CORE_BUILD` instead of the list. According to the description in the Configurator this is hardware drivers and a limited set of features: the build is for checking whether the board sees its gyro, flash and OSD chip, not for flying. In the 4.5.3 sources `CORE_BUILD` directly disables little (for example, Launch Control, `common_pre.h:380–389`); the full set of what the server adds to such a request is not visible in the open code.

**Custom Defines** is a field in Expert Mode. The names are entered separated by a space, **without** the `USE_` prefix; the server adds it itself (the hint `firmwareFlasherCustomDefinesDescription`). Each word goes into the same `options` list. Examples of flags that exist in the 4.5.3 sources but are not in the lists:

| Enter | Flag | What it gives |
|---|---|---|
| `RANGEFINDER RANGEFINDER_TF` | `USE_RANGEFINDER`, `USE_RANGEFINDER_TF` | the Benewake TFmini/TF02 lidars, `feature RANGEFINDER` |
| `GPS_LAP_TIMER` | `USE_GPS_LAP_TIMER` | a GPS lap timer and an OSD menu item (only together with `GPS`) |
| `TRANSPONDER` | `USE_TRANSPONDER` | an IR race timing transponder; in Configurator 10.10 the tab and the Features item will not appear (the option is not in the 4.5 MSP_BUILD_INFO), so it is configured only through the CLI |
| `ESC_SENSOR` | `USE_ESC_SENSOR` | wired ESC telemetry (in 4.5.3 it is enabled automatically together with DShot, `common_post.h:159–161`; without DShot it is absent) |

A typo in a name usually does not break the build: the compiler simply never notices an unknown `USE_…`, and the feature will not be there. `build request error (please check build configuration, e.g. custom defines)` means that the server rejected the `POST /api/builds` request itself; why — cannot be seen from the Configurator code. The names are split on a single space (`split(' ')`): a double space yields an empty list item. `failed (please check log)` — the request was accepted but did not build; the `Show Log.` link opens the compiler log. An option that needs a pin gets it assigned through `resource` in the CLI.

### How to find out what is inside the firmware
A reference of the commands and places where the build contents are visible (the format strings are from `cli.c` of 4.5.3):

| Where | What it shows about the build | What it looks like |
|---|---|---|
| `version` | the firmware name, target, board identifier, version, date, git revision, MSP API | `# Betaflight / STM32F405 (S405) 4.5.3 <date> / <time> (<git>) MSP API: 1.46`; below it `# config rev: …` (a build with a board config) and `# board: manufacturer_id: …, board_name: …` |
| `status` | the build key, only for a cloud build | `BUILD KEY: <32 characters> (<release name>)`; a local build has no such line |
| `get <part of a name>` | whether the subsystem's settings exist (a substring search) | none at all → `###ERROR IN get: INVALID NAME: gps_provider###` |
| `help <string>` | whether the command exists | no matches → `###ERROR IN help: NO MATCHES FOR 'smix'###` |
| `feature list` | **not** a check of the build: the table of names is the same for all builds | 4.5.3: `feature GPS` without GPS prints `unavailable`, `feature LED_STRIP` without the strip is enabled silently; *2025.12:* any missing item gives `Unavailable <NAME>`, and this does not count as a batch error |
| `diff all` | the version at the start, no key | `# version`, then the commented-out line `# Betaflight / … MSP API: 1.46` (without `# board:`) |
| Setup → Firmware info | the links `Config`, `Log`, `Options` to build.betaflight.com/api/builds/<key>/… | a local build: `Local Build - no Cloud information` |
| The Firmware Flasher and the Configurator log | the options of the current build are filled into the flasher's lists | on connecting, the log shows `Build Key: <key>` |

Configurator 10.10 also **hides tabs** based on the option list: GPS, LED Strip, OSD and Servos are shown only if the build has the corresponding option (`gui.js:57–63`, `serial_backend.js:611–620`; the substring `osd` is also provided by `USE_FRSKYOSD`). The Race Transponder tab is hidden in 4.5 on any build: there is no such option in MSP_BUILD_INFO. The board reports the option list itself (MSP_BUILD_INFO, API 1.46), so local builds behave the same way. In the Other Features list of the Configuration tab, items whose option is missing disappear likewise (`Features.js:44–51`), including TRANSPONDER and SONAR.

{{lesson:bf-cli|How to save `diff all`, read `dump` and automate CLI checks — covered there in detail.}}

### What is not in the build is not anywhere
The main risk of a custom build is that the errors are silent. A `USE_*` flag removes code entirely: settings, CLI commands, OSD elements, modes. The firmware still boots and flies; the feature is simply not there. The most insidious part is the value tables: the protocol names in `serialrx_provider` and `motor_pwm_protocol` are the same for all builds. So `set serialrx_provider = CRSF` and `set motor_pwm_protocol = DSHOT600` are accepted without an error even in a build without CRSF or DShot, while the receiver and the motors stay silent, and that looks like a wiring fault (`bf-ports`). What disappears completely is the subsystem's settings (`dshot_bidir`, `gps_*`) and commands (`servo`, `smix`, `led`, `gpspassthrough`). If the build does not fit, the GNU ld linker reports that the `FLASH1` region overflowed by N bytes; the usage of each region is printed by `-Wl,--print-memory-usage` (`Makefile:295`).

### Restoring the config after changing the build
`diff all` is structured like this (`cli.c:6197–6376`): the version line, `batch start`, `defaults nosave` (a reset to defaults), then `board_name`, `manufacturer_id`, `resource`, `feature`, `serial`, `set` lines by section, the profiles and `save` at the end. While a batch is running, **any** error marks the whole batch. A line with a nonexistent setting gives `INVALID NAME`, a missing command gives `###ERROR IN input: UNKNOWN COMMAND, TRY 'HELP'###`. Then the `save` at the end saves nothing and prints:

- `###ERROR IN save: ERRORS WERE DETECTED - PLEASE REVIEW BEFORE CONTINUING###`
- `###ERROR IN save: PLEASE FIX ERRORS THEN 'SAVE'###`

After that the batch is reset. The accepted lines have already been applied in memory, and a second `save`, typed by hand, will write them. The procedure:

1. Before flashing: `diff all`, `version`, `status` — to a file (the build key is only in the `status` output).
2. After flashing, paste the whole `diff all` and read **all** the `###ERROR` lines.
3. Explain every error: the option is not in the new build (that is fine if it was dropped deliberately) or the name was renamed between versions (then this is the wrong version, `bf-intro`).
4. `save` by hand, reboot, then `diff all` once more and a line-by-line comparison with the original file (`git diff`).

A `diff all` cannot be carried between **versions** (4.5 → 2025.12) this way: setting names and meanings changed, and some lines will be accepted with a different result and no error (`bf-intro`, the table of renames).

### ArduPilot: building from source
ArduPilot is built with `waf`: `./waf configure --board <board>` and `./waf copter` (or `plane`). The target is described in `libraries/AP_HAL_ChibiOS/hwdef/<board>/hwdef.dat`: pins, buses, which drivers to include. The same file is where unneeded things are disabled with `define` lines.

For boards with small flash there are reduced configurations: many features in the code are wrapped in `#if AP_<FEATURE>_ENABLED` checks, and the hwdef can set `define AP_<FEATURE>_ENABLED 0`. The Custom Firmware Builder web tool (linked from the “Building the code” documentation) does the same through an interface: tick the boxes, get the firmware.

### Case: a HeeWing F405 without GPS
The stock F405 in the HeeWing T1 project is a board with limited flash: no Lua scripting, and some capabilities are cut. The firmware variants planned for it: remove GPS support (on this build it is not used for arming or basic flight) and unneeded drivers, to free up room for what is needed. This is a sensible decision if you understand the consequences: without GPS in the firmware there will be neither RTL nor a position-based geofence — not just “for now”, but at all.

### Rules for custom builds
1. Keep the build configuration in git next to the parameters: the list of Betaflight options or the ArduPilot `hwdef` patch.
2. Name the build with the date and the commit hash; the `version` output and the BUILD KEY from `status` must match the record.
3. Before flashing — a full backup (`diff all` / a parameter file); after — re-read everything critical.
4. Do not mix: a custom build + a standard config from another version = unpredictability.
5. A course guideline: keep a margin of at least 5 % of the `FLASH1` region (on the F411 that is 24 KB). A patch release of the same branch may turn out fatter, and a build that “just fits” will stop building with the same options.

### A local Betaflight build (when Cloud Build does not suit)
```bash
git clone https://github.com/betaflight/betaflight && cd betaflight
make arm_sdk_install                      # toolchain
make configs                              # unified target configs
make STM32H743 EXTRA_FLAGS="-DUSE_GPS_LAP_TIMER"   # family target + extra define
# or with the config of a specific board:
make SPEEDYBEEF405V4 EXTRA_FLAGS="-DUSE_..."
```
`make configs` clones the betaflight/config repository into `src/config`. `make <BOARD_NAME>` is the same as `make CONFIG=<BOARD_NAME>`: the target is taken from `FC_TARGET_MCU` in the board's `config.h` (`mk/config.mk`), and `TARGET` and `CONFIG` cannot be given at the same time. The board name in the example is a placeholder; take yours from the list of configs. The result: `obj/betaflight_4.5.3_STM32F405_<BOARD>.hex` (`Makefile:309–324`). It is flashed with the “Load Firmware [Local]” button.

Two ways to pass flags:

- `OPTIONS="CLOUD_BUILD USE_SERIALRX USE_SERIALRX_CRSF USE_TELEMETRY USE_DSHOT USE_OSD_SD USE_GPS"` — `Makefile:252` prepends `-D` to every word. With `CLOUD_BUILD` the classic set is off, and only what is listed goes into the firmware. The Configurator list will not do verbatim: `USE_SERIALRX` and `USE_TELEMETRY` are defined only in the classic block (`common_pre.h:178`, `191`), and without them `common_post.h:198–223` strips out CRSF and its telemetry. The cloud adds such base flags itself (their set is visible in `/api/builds/<key>/json`) — check your list against it. This is how an F411 gets GPS, which is absent from the classic 512 KB build;
- `EXTRA_FLAGS="-DUSE_…"` — the flags are appended to the end of the compiler command line. This is a way to **add**, not to remove: `-U` on the command line will not undo a `#define` in `common_pre.h`, which takes effect later. A trap: a flag that `common_pre.h` already sets for this target without `#ifndef` (for example, `USE_RANGEFINDER` on an H743 with ≥ 1024 KB of flash) gives `error: "USE_RANGEFINDER" redefined` when passed through `EXTRA_FLAGS` — the build runs with `-Werror`. Options are removed only through the `CLOUD_BUILD` (or `CORE_BUILD`) gate with an explicit list — it does not matter whether through `OPTIONS` or `EXTRA_FLAGS="-DCLOUD_BUILD …"`.

A local build has no `BUILD_KEY`: there is no line in `status`, and Setup shows `Local Build - no Cloud information`. The Configurator hides tabs and Features items the same way as for a cloud build: the board reports the option list itself (MSP_BUILD_INFO). So record the `OPTIONS` list and the commit hash yourself. For checking without hardware there are `make SITL` and `make test` (gtest unit tests, the module “How to read the source”).

### What breaks after a custom build and how to check
1. By the BUILD KEY from `status` (`https://build.betaflight.com/api/builds/<key>/json`) — the expected options.
2. `status` — the gyro is detected.
3. Ports/Receiver — the receiver responds.
4. Motors — DShot and bidir work, without props.
5. The OSD is visible.
6. `diff all` matches the backup in meaning.

The checklist goes into the aircraft log together with the commit hash and the `EXTRA_FLAGS`/`OPTIONS`.

{{diagram:bf-custom-verify-flow|Six checks after a custom build: a silent receiver or a missing OSD is usually the build contents, not the wiring.}}

{{diagram:fw-build-paths|Which build path to choose: options — Cloud Build or custom.ardupilot.org, your own code — a local build.}}

### Place in the system

- **Receives:** the list of what is actually on board: the receiver protocol (`bf-ports`), the OSD type — analog or HD (`bf-hd-osd-video`), GPS (`bf-gps-setup`), servos (`bf-servos-pwm`); the constraint is the size of the flight controller's flash memory.
- **Provides:** firmware with the chosen set of options and a BUILD KEY in `status`, by which the build contents are checked and reproduced (`bf-cli`).
- **If you get it wrong here:** you did not select the receiver protocol → the receiver is “silent” however it is wired, and it looks like a wiring or port fault (`bf-ports`). You built without HD OSD → there is video in the goggles but no OSD with any port mask (`bf-hd-osd-video`). You built without SERVOS → the CLI has no `servo` and `smix` commands (`bf-servos-pwm`).

## practice
### Betaflight: a build for a specific aircraft
1. Firmware Flasher → the board target → the version. If the board is connected, the Configurator fills in the options of its current build — start from them.
2. Options: the receiver (CRSF), Motor Protocol (DShot — mandatory, a cloud build does not enable it automatically), OSD (`OSD_SD` for analog, `OSD_HD` for digital, both if you are not sure), telemetry, GPS only if you have one.
3. Expert Mode → Custom Defines, if you need something outside the lists: names without `USE_`, separated by a space.
4. Build → Flash. After flashing, in the CLI: `version` and `status` — save the output (the BUILD KEY is in `status`) to the drone's folder.
5. Restore the config from a `diff all` of the **same** version, read all the `###ERROR` lines, then `save` by hand if the errors are explained.

### ArduPilot: building from source
```
git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git
cd ardupilot
Tools/environment_install/install-prereqs-ubuntu.sh -y
./waf configure --board MatekF405-Wing   # example board name; use yours
./waf plane
ls build/MatekF405-Wing/bin/             # arduplane.apj / .bin / .hex
```

Disabling a feature: add a line of the form `define AP_<FEATURE>_ENABLED 0` to the board's `hwdef.dat` (or to a separate extra hwdef file), rebuild, and check the size in the build output. For a first attempt the Custom Firmware Builder on the website is easier.

### Step 1. An exercise without hardware: moving a `diff all` into another build
The situation. An F405 had a 4.5.3 cloud build with GPS, an LED strip, DShot and analog OSD. The GPS was removed, the strip and the servos too, and new firmware was built without `GPS`, `LED_STRIP` and `SERVOS`. The old `diff all` is pasted into the new build; among other things it has these lines: `feature GPS`, `feature LED_STRIP`, `led 0 0,0::C:0`, `set serialrx_provider = CRSF`, `set motor_pwm_protocol = DSHOT600`, `set dshot_bidir = ON`, `set gps_provider = UBLOX`, `set gps_rescue_min_sats = 7`, `set ledstrip_profile = STATUS`, `set osd_vbat_pos = 2401`, and `save` at the end.

Predict for every line: accepted, `unavailable`, `INVALID NAME` or `UNKNOWN COMMAND` — and whether the config will be saved. Then check against the lab: `bf-custom.lab.py` repeats the `cliGet`/`cliSet`/`cliFeature`/batch logic from `cli.c` of 4.5.3. The script output for the new build:

- `feature GPS` → `unavailable` (no error), `feature LED_STRIP` → `Enabled LED_STRIP` (silently, although there is no strip code);
- `led …` → `###ERROR IN input: UNKNOWN COMMAND, TRY 'HELP'###`;
- `gps_provider`, `gps_rescue_min_sats`, `ledstrip_profile` → `###ERROR IN set: INVALID NAME: …###`;
- `serialrx_provider`, `motor_pwm_protocol`, `dshot_bidir`, `osd_vbat_pos` → `… set to …`;
- the result: 6 errors (four in the lines and two in the `save` reply), saved: `False`; after a second manual `save` — `True`.

### Step 2. The flash budget
The same lab calculates the room for the main code (the `FLASH1` region): F411 — 480 KB, F405 — 992 KB. A 450 KB firmware on an F411 takes 93.8 % of `FLASH1` with 30 KB free: it passes the course guideline (a margin ≥ 5 %, 24 KB). 470 KB is 97.9 % with 10 KB free: it builds, but the guideline is not met. 490 KB does not fit: the linker will report a `FLASH1` overflow of 10 KB. Start removing with what is not on board: the second OSD type, extra receiver and telemetry protocols.

### Step 3. A lab on hardware
Build two ArduPlane firmwares for your board: the standard one and one without a single subsystem. Compare the size of the binaries, flash the second one onto a SITL-like bench setup (the board on the bench) and make sure the disabled subsystem really disappeared from the parameters. For Betaflight it is the same: two cloud builds that differ by one option (for example, `GPS`). Propellers are off in all steps — only the CLI and the tabs are checked.

### What you should get and what to record
- **Betaflight.** After flashing the reduced build, `version` and `status` are saved to a file next to the config (the BUILD KEY lets you rebuild exactly the same firmware). The config is restored from a `diff all` of the same version, all `###ERROR` lines are explained, and the key settings are re-read with `get`. The settings of the disabled options are absent from the CLI: after a build without GPS, `get gps_provider` answers `INVALID NAME`, `help gps` — `NO MATCHES FOR 'gps'`, and the Configurator has no GPS tab.
- **ArduPilot.** The build output shows the firmware size and the free flash. Record both numbers for the two builds: the difference is the price of the disabled subsystem in bytes. After flashing, the subsystem's parameters (its prefix) disappear from the full parameter list in the ground station — take a screenshot of a search by the prefix before and after.
- **Git.** The file with the build options (the `hwdef` with `define AP_<FEATURE>_ENABLED 0`, or the list of Cloud Build options / the `OPTIONS` of a local build) is in the repository next to the config. Six months later the question “why does this drone not have X” will be answered by a commit, not by memory.

Self-check: the lab is complete when (without hardware) for all ten lines of step 1 you predicted the same outcome as in the lab output, and the answer “saved: no, after a second `save` — yes” matched; in step 2 you calculated 93.8 % ± 0.1 % and 30 KB free for 450 KB on an F411 (97.9 % and 10 KB for 470 KB); (on hardware) the standard and the reduced firmware are built, the sizes are compared, the `version`/`status` output with the BUILD KEY is saved, the disappearance of the disabled subsystem is confirmed by CLI output (`INVALID NAME`) or a screenshot, and the build configuration is in git.

**Reference for self-check.** The correct result of step 1: `serialrx_provider`, `motor_pwm_protocol`, `dshot_bidir`, `osd_vbat_pos` and both `feature` lines are accepted (GPS — with the reply `unavailable`); `led` and the three `set` lines for GPS and the strip give errors; `save` refuses to save. Typical mistakes: “`feature LED_STRIP` will give an error” — no, `cliFeature` in 4.5.3 checks only GPS and RANGEFINDER and enables the rest silently (in 2025.12 it prints `Unavailable LED_STRIP`, but also without a batch error), which is why `feature list` says nothing about the build contents; “the accepted lines are lost” — no, they are applied in memory, and a second `save` will write them; “the config will be saved without the lines with errors” — no, a batch with an error blocks `save` entirely. On hardware: the sizes of the two builds are the same — the flag did not make it into the build (`define AP_<FEATURE>_ENABLED 0` is in the wrong `hwdef`, the option was not selected in Cloud Build): check `/api/builds/<key>/json` or the build output. The subsystem's parameters are still there — the board has the old build flashed: check `version` and the BUILD KEY against the record.

## diagnostics
- **Symptom:** Cloud Build fails with a size error
  - Possible cause: too many options for the board's flash (F411/F722 — 480 KB in `FLASH1`).
  - What to do: open `Show Log.`, find the message about the `FLASH1` overflow; remove what is unused (the second OSD, extra protocols, GPS without a GPS).
- **Symptom:** `build request error (please check build configuration, e.g. custom defines)`
  - Possible cause: the server rejected the request itself; most often Custom Defines are to blame.
  - What to do: one name per single space, without `USE_`, without commas; check the name against the sources of the required version. An unknown name usually does not break the build, it just does not give you the feature.
- **Symptom:** after a custom build a feature “is there” but does not work
  - Possible cause: the option needs a pin that was not assigned through `resource`; or the `feature` is enabled but the code is not in the build (LED_STRIP).
  - What to do: `get` by the name of the feature's settings and `help` by the command name; if `INVALID NAME` — rebuild with the option; otherwise `resource`, reboot, `status`.
- **Symptom:** after pasting `diff all` the settings were not saved, and the output has `ERRORS WERE DETECTED`
  - Possible cause: the batch has lines for options that are not in the new build; a batch with an error blocks `save`.
  - What to do: read all the `###ERROR` lines, make sure they are only the deliberately removed options, type `save` by hand.
- **Symptom:** the analog OSD disappeared after a rebuild
  - Possible cause: only `OSD_HD` was built — the MAX7456 driver is stripped out.
  - What to do: add `OSD_SD` (or both).
- **Symptom:** the motors do not respond to DShot, `get dshot_bidir` → `INVALID NAME`
  - Possible cause: a cloud build without `DSHOT` in Motor Protocol; `motor_pwm_protocol = DSHOT600` is accepted all the same, but there is no DShot code. The same with the receiver: `serialrx_provider = CRSF` is accepted even without `SERIALRX_CRSF` in the build.
  - What to do: rebuild with `DSHOT`; after flashing, `get dshot_bidir` must answer with a value.
- **Symptom:** the Configurator has no GPS / OSD / LED Strip / Servos tab
  - Possible cause: the option is not in the build — the Configurator hides the tab based on the option list.
  - What to do: Setup → Firmware info → `Options`; rebuild.
- **Symptom:** ArduPilot `waf configure` does not find the board
  - Possible cause: a typo in the name, missing submodules.
  - What to do: `./waf list_boards`, `git submodule update --init --recursive`.
- **Symptom:** after a custom build some parameters disappeared
  - Possible cause: that is exactly the effect of a disabled subsystem.
  - What to do: check against the build record; if the parameter is needed — bring the feature back.

## references
- Betaflight 4.5.3 — src/main/cli/cli.c (status, version, get, help, batch) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/cli/cli.c | primary | A
- Betaflight 4.5.3 — src/main/target/common_pre.h (CLOUD_BUILD, CORE_BUILD, option dependencies) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/target/common_pre.h | primary | A
- Betaflight 4.5.3 — src/main/msp/msp_build_info.h (the Cloud Build option list of 4.5) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/src/main/msp/msp_build_info.h | primary | A
- Betaflight 4.5.3 — Makefile and mk/config.mk (OPTIONS, EXTRA_FLAGS, CONFIG) | https://raw.githubusercontent.com/betaflight/betaflight/4.5.3/Makefile | primary | A
- Betaflight Configurator 10.10.0 — firmware_flasher.js (build request, Custom Defines, Core Only) | https://raw.githubusercontent.com/betaflight/betaflight-configurator/10.10.0/src/js/tabs/firmware_flasher.js | primary | A
- Build Options — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/Build-Options | primary | A
- Defines — Betaflight Development | https://betaflight.com/docs/development/Defines | primary | A
- Building the code — ArduPilot Dev | https://ardupilot.org/dev/docs/building-the-code.html | primary | A
- Setting up SITL / build environment — ArduPilot Dev | https://ardupilot.org/dev/docs/SITL-setup-landingpage.html | primary | A

## checklist
- I know which options my aircraft really needs, and that DShot has to be selected explicitly in a cloud build
- The build is described in git: options / `OPTIONS` / hwdef patch, date, hash
- The `version` and `status` (BUILD KEY) output is saved after flashing
- The config is restored from the same version; all `###ERROR` lines are read and explained
- I check the build contents with `get` and `help`, not with `feature list`
- I understand what I lose by disabling a subsystem
