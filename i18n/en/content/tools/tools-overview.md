---
id: tools-overview
title: "Tools: Configurator, GCS, git"
level: L1
readingTime: 15 min
firmware: any firmware
status: published
added: 2026-11-07
tags:
  - tools
  - git
  - GCS
related:
  - f-safety
  - bf-cli-automation
next:
  - bf-intro
source: content/tools/tools-overview.md
source_hash: 7528e2cae361
---

## summary
A UAV engineer needs not one tool but a set: a configurator for the firmware, a ground control station, a log analyzer, a terminal and a version control system for configs. This module describes the minimal stack as of 2026, what to use for what, and the one rule that saves the most nerves: configs and logs live in dated folders and in git.

## theory
### Firmware configurators
- **Betaflight App** — Betaflight setup: ports, receiver, modes, PID, OSD, CLI, flashing. There are versions for Windows/macOS/Linux and a web version.
- **INAV Configurator** — the same for INAV, with a mission planner.
- **Mission Planner** (Windows) and **QGroundControl** (cross-platform) — ground control stations for ArduPilot and PX4: parameters, calibrations, missions, telemetry, logs. For ArduPilot on Linux the console-based **MAVProxy** is handy too.

### Flashing and ESCs
- **Betaflight App → Firmware Flasher** with Cloud Build.
- **ESC Configurator** (web) or **Bluejay/AM32 Configurator** to flash ESCs via passthrough.
- **ExpressLRS Configurator** — flashing ELRS receivers and modules.
- Sometimes you need **Zadig** (Windows) for the DFU driver when flashing.

### Logs
- **Blackbox Explorer** (Betaflight) and **PIDscope** (an open continuation of PIDtoolbox on GNU Octave; PIDtoolbox itself has been paid since 2024) — Betaflight logs.
- **Mission Planner / MAVExplorer / UAV Log Viewer** — ArduPilot DataFlash.
- **Python** with `orangebox` (Betaflight) and `pymavlink.DFReader` (ArduPilot) — when you need your own metrics.

### Terminal and Python
A Linux terminal or WSL on Windows: `picocom`/`minicom` for UART, `pyserial` for CLI scripts, `pymavlink` for MAVLink, `scipy`/`matplotlib` for spectra. One virtual environment per project (`python -m venv`) so library versions don't get in each other's way.

### Git for configs
A drone's configuration is code. A Betaflight `diff all` and an ArduPilot `.param` are text files; you can keep them in git, compare them and roll them back. Structure:

```
drones/
  viking2/
    configs/   2026-11-03_viking2_F405_diff.txt
    logs/      2026-11-03_daylight_profiles/
    notes/     session_notes.md, SUMMARY_2026-11-03.md
  viking10/
```

The file name starts with the date `YYYY-MM-DD` — sorting by name gives you the chronology. Before any change — a “before” file, after it — an “after” file, and `git diff` shows the difference.

### SITL
For ArduPilot — SITL, for PX4 — Gazebo/jMAVSim. Every scenario, script and parameter goes to the simulator first.

### The engineer's workbench: the minimal set
| Task | Tool | Why this one |
|---|---|---|
| Betaflight/INAV setup | Betaflight App / INAV Configurator (desktop, not web — for flashing and DFU) | full CLI access, flashing, DFU |
| ArduPilot/PX4 | Mission Planner (Windows; the most complete for ArduPilot: Full Parameter List, MAVFtp, log review), QGroundControl (cross-platform; the main one for PX4) | parameters, calibrations, missions, logs |
| MAVLink console | MAVProxy (`pip install MAVProxy`), `mavproxy.py --master=/dev/ttyACM0 --console --map` | scriptable GCS, `param`, `module load log` |
| Betaflight logs | Blackbox Explorer, PIDscope (GNU Octave), `blackbox_decode` → CSV → Python | spectra, step response, your own metrics |
| ArduPilot logs | Mission Planner Log Review, MAVExplorer (`mavexplorer.py log.bin`, plots from expressions like `ATT.Roll-ATT.DesRoll`), UAV Log Viewer (web), `pymavlink` | quick overview / your own metrics |
| ESC | ESC Configurator (web, Chrome), Bluejay/AM32 configurator; passthrough via the FC | ESC flashing and settings |
| Radio | ExpressLRS Configurator, EdgeTX Companion + Buddy | flashing modules, radio models |
| Hardware | multimeter, XT60 wattmeter, smoke stopper, ST-Link programmer (FC recovery), 24 MHz logic analyzer, oscilloscope (as you grow) | the “Measurements” modules |
| Terminal | Linux / WSL2: `picocom -b 115200 /dev/ttyACM0`, `pyserial`, `venv` | CLI scripts, MAVLink |
| Simulation | ArduPilot SITL (`sim_vehicle.py`), PX4 SITL (`make px4_sitl gz_x500`), Betaflight SITL (`make TARGET=SITL`) | every scenario — here first |
| Version control | git + GitHub; `.gitattributes` with LFS for `.bin/.BFL` | configs and scripts, the “CI” module |

### Installation order (Linux / WSL2)
```bash
sudo apt install git python3-venv picocom build-essential
python3 -m venv ~/uav && . ~/uav/bin/activate
pip install pymavlink MAVProxy pandas numpy scipy matplotlib pyserial
sudo usermod -aG dialout $USER     # access to /dev/ttyACM*/ttyUSB*; re-login
git clone --depth 1 https://github.com/ArduPilot/ardupilot && cd ardupilot && Tools/environment_install/install-prereqs-ubuntu.sh -y
```
Check: `mavproxy.py --master=tcp:127.0.0.1:5760` connects to `sim_vehicle.py -v ArduCopter`. In WSL2, USB devices are passed through with `usbipd` (Windows 11) — or use Windows apps for USB and Linux for scripts and logs.

### Where things get logged (so you can find them later)
Betaflight: flash on the FC → download through the configurator (Blackbox tab) into a `.BFL`; ArduPilot: SD card `/APM/LOGS/*.BIN` or MAVFtp from Mission Planner; GCS telemetry logs (`.tlog`) are separate and contain everything that went over MAVLink; PX4: `.ulg` on the SD card, viewed in Flight Review (web) or with `pyulog`. Naming: `YYYY-MM-DD_vehicle_purpose.ext` in the vehicle's folder.

{{diagram:toolbox-map|The engineer's minimal toolset by task.}}

## practice
### Minimal installation
1. Betaflight App, Mission Planner or QGroundControl.
2. Python 3 + `pip install pyserial pymavlink orangebox scipy matplotlib` in a venv.
3. Git; a `drones/` repository with the structure above.
4. A serial port terminal.
5. For ArduPilot — SITL per the “SITL: a drone without a drone” module.

### First commit
1. Connect the drone, run `diff all` in the CLI (or save a `.param`).
2. Save it to `drones/<name>/configs/<date>_<name>_<board>_diff.txt`.
3. `git add`, `git commit -m "<name>: baseline <date>"`.
4. After any change — a new file and a commit describing what and why.

### What you should get
After two commits, `git log --oneline drones/<name>/configs/` shows two lines with clear descriptions, and `git diff` between the files shows exactly one changed line:

```text
-set rpm_filter_min_hz = 100
+set rpm_filter_min_hz = 50
```

If the diff has more lines than you changed, unexpected changes got into it: a different firmware version (new or renamed settings), someone else's edits, a reset to defaults. That's a reason to sort it out before the flight, not after. Compare diffs from the same firmware version. After a firmware update, make a separate baseline commit, “baseline after update.”

### Common mistakes
- A file name without the date or the board — in a month you won't know what it is or where it came from.
- Saving a `dump` instead of `diff all`: a dump has hundreds of lines of default values, and the useful change gets lost in it.
- A commit without a “why.” Six months later “changed filter” tells you nothing, but “rpm_filter_min_hz 100→50: 10" motors below 100 Hz in hover” does.

### Lab
Make two diffs that differ by one parameter and show the `git diff` between them. This is your first “code review” of your own drone.

The lab counts as done when the `drones/` repository is created with the structure, a config is saved with the date and board in its name and committed with a description, and `git diff` of two configs shows exactly one change with an explanation in the commit message.

## diagnostics
- **Symptom:** the configurator doesn't see the board
  - Possible cause: the driver (Windows), a charge-only cable, the board is in DFU.
  - What to do: Zadig for DFU, a different cable, check the COM port.
- **Symptom:** I don't remember what I changed before it broke
  - Possible cause: no “before/after” diffs.
  - What to do: the rule “always a file before changes,” git.
- **Symptom:** Python libraries conflict between projects
  - Possible cause: everything is installed into the system Python.
  - What to do: one venv per project.

## references
- Betaflight App — Documentation | https://betaflight.com/docs/wiki/app | primary | A
- Mission Planner — Documentation | https://ardupilot.org/planner/ | primary | A
- QGroundControl — User Guide | https://docs.qgroundcontrol.com/Stable_V5.0/en/ | primary | A
- MAVProxy — Documentation | https://ardupilot.org/mavproxy/ | primary | A
- Pro Git — book | https://git-scm.com/book/en/v2 | primary | A

## checklist
- A configurator and a ground control station for my firmware are installed
- Python in a venv with pyserial/pymavlink
- A `drones/` repository with a folder for each drone
- Every config is a file with the date in its name, in git
- Before changes there is always a “before” file
