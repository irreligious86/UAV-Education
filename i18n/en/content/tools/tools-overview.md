---
id: tools-overview
title: "Tools: Configurator, GCS, git"
level: L1
readingTime: 35 min
firmware: Betaflight 2025.12 · INAV 9.1 · ArduPilot 4.7 (checked against 4.7.3; lab recorded on SITL 4.7.2) · PX4 1.18
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
source_hash: bfa9e3324f4e
---

## summary
A UAV engineer needs not one tool but a set: a configurator for the firmware, a ground station, a log analyzer, a terminal and version control for configs. This module describes the minimal stack as of November 2026 with checked versions, how a tool's version relates to the firmware version and why a mismatch breaks things silently, a "task → tool" table with links to the modules where each tool is covered, and the one rule that saves the most grief: configs and logs live in dated folders and in git. The lab (run on ArduCopter 4.7.2 SITL): install the Python stack into a venv, save the parameters to a `.param` file, commit, change one parameter and get a `git diff` of exactly one line, and see that the firmware silently ignores a parameter written under its old name.

## theory
### Firmware configurators
- **Betaflight App**: Betaflight setup: ports, receiver, modes, PID, OSD, CLI, flashing. There are Windows/macOS/Linux versions and a web version.
- **INAV Configurator**: the same for INAV, with a mission planner.
- **Mission Planner** (Windows) and **QGroundControl** (cross-platform): ground stations for ArduPilot and PX4: parameters, calibrations, missions, telemetry, logs. For ArduPilot on Linux the console-based **MAVProxy** is handy too.

### Flashing and ESCs
- **Betaflight App → Firmware Flasher** with Cloud Build.
- **ESC Configurator** (web) or **Bluejay/AM32 Configurator** for flashing ESCs through passthrough.
- **ExpressLRS Configurator**: flashing ELRS receivers and modules.
- Sometimes you need **Zadig** (Windows) for the DFU driver when flashing.

### Logs
- **Blackbox Explorer** (Betaflight) and **PIDscope** (an open continuation of PIDtoolbox on GNU Octave; PIDtoolbox itself has been paid since 2024): Betaflight logs.
- **Mission Planner / MAVExplorer / UAV Log Viewer**: ArduPilot DataFlash.
- **Flight Review** (web) and **PlotJuggler**: PX4 `.ulg` logs; PlotJuggler opens `.ulg`, CSV and ROS 2 bags.
- **Python** with `orangebox` (Betaflight), `pymavlink.DFReader` (ArduPilot) and `pyulog` (PX4): when you need your own metrics.

### Terminal and Python
A Linux terminal, or WSL on Windows: `picocom`/`minicom` for UART, `pyserial` for scripts that talk to the CLI, `pymavlink` for MAVLink, `scipy`/`matplotlib` for spectra. One virtual environment per project (`python -m venv`), so library versions do not interfere with each other. Why this matters in practice: `pymavlink`, `MAVProxy` and `mavsdk` release several times a year, and a log-analysis script written against one version may break on another a year later. So a `requirements.txt` with exact versions sits next to the code: `pip freeze > requirements.txt` once everything works, and `pip install -r requirements.txt` in a new venv on another machine. The same principle as with the drone's config: a recorded state you can return to. The system Python on Ubuntu 23.04 and newer (that is, every LTS from 24.04 on) does not let you install packages with `pip` outside a venv at all (the "externally-managed-environment" error, PEP 668); that is not a breakage but a hint to create an environment.

Port and permissions. On Linux the flight controller shows up as `/dev/ttyACM0` (USB VCP) or `/dev/ttyUSB0` (through a USB-UART adapter), and only the `dialout` group has access to it: without `usermod -aG dialout` and logging in again, the configurator and `picocom` get "Permission denied." On Windows the port is `COMn`, and DFU mode needs the WinUSB driver (Zadig); without it Betaflight App sees the board in DFU but cannot flash it. One port, one owner: the configurator cannot open a port that is open in `picocom`, and vice versa; after the driver and the cable, this is the most common reason for "the configurator does not see the board."

How to read the versions on your own setup. Betaflight and INAV firmware: the `version` command in the CLI (the first line of `diff all` also contains the version and board); ArduPilot: the message on connecting in the GCS, or the version record in the log (`VER` in DataFlash); PX4: `ver all` in the console. The configurator shows its version in the window title, and Python packages via `pip list` or `importlib.metadata.version()` (as the lab script does). These four lines (firmware, configurator or GCS, Python stack, date) are the first thing written into the vehicle log before changing any settings.

### Git for configs
A drone's configuration is code. A Betaflight `diff all` and an ArduPilot `.param` are text files: you can keep them in git, compare them and roll them back. Structure:

```
drones/
  viking2/
    configs/   2026-11-03_viking2_F405_diff.txt
    logs/      2026-11-03_daylight_profiles/
    notes/     session_notes.md, SUMMARY_2026-11-03.md
  viking10/
```

The file name starts with a `YYYY-MM-DD` date, so sorting by name gives the chronology. Before any change, a "before" file; after it, an "after" file; `git diff` shows the difference.

{{diagram:config-change-flow|The "before/after" rule: a file before the change, a commit, one change, and git diff must show exactly one line; any extra lines are sorted out before flying.}}

### SITL
For ArduPilot, SITL; for PX4, Gazebo/jMAVSim. Every scenario, script and parameter goes on the simulator first.

### The engineer's workbench: a minimal set
| Task | Tool | Why this one |
|---|---|---|
| Betaflight/INAV setup | Betaflight App / INAV Configurator (desktop, not web, for flashing and DFU) | full CLI access, flashing, DFU |
| ArduPilot/PX4 | Mission Planner (Windows; the most complete for ArduPilot: Full Parameter List, MAVFtp, log review), QGroundControl (cross-platform; the main one for PX4) | parameters, calibrations, missions, logs |
| MAVLink console | MAVProxy (`pip install MAVProxy`), `mavproxy.py --master=/dev/ttyACM0 --console --map` | a scriptable GCS, `param`, `module load log` |
| Betaflight logs | Blackbox Explorer, PIDscope (GNU Octave), `blackbox_decode` → CSV → Python | spectra, step response, your own metrics |
| ArduPilot logs | Mission Planner Log Review, MAVExplorer (`mavexplorer.py log.bin`, plots of expressions like `ATT.Roll-ATT.DesRoll`), UAV Log Viewer (web), `pymavlink` | quick overview / your own metrics |
| ESC | ESC Configurator (web, Chrome), Bluejay/AM32 configurator; passthrough through the FC | flashing and setting up ESCs |
| Radio | ExpressLRS Configurator, EdgeTX Companion + Buddy | flashing modules, transmitter models |
| Hardware | multimeter, XT60 wattmeter, smoke stopper, ST-Link programmer (FC recovery), 24 MHz logic analyzer, oscilloscope (as you grow) | the "Measurements" modules |
| Terminal | Linux / WSL2: `picocom -b 115200 /dev/ttyACM0`, `pyserial`, `venv` | scripts for the CLI, MAVLink |
| Simulation | ArduPilot SITL (`sim_vehicle.py`), PX4 SITL (`make px4_sitl gz_x500`), Betaflight SITL (`make TARGET=SITL`) | every scenario goes here first |
| Versioning | git + GitHub; `.gitattributes` with LFS for `.bin/.BFL` | configs and scripts, the "CI" module |

### Versions as of November 2026
The versions were checked against the GitHub release tags on November 25–26, 2026 and against PyPI on November 25, 2026 (pyulog 1.4.0 on Nov 26 and MAVSDK-Python 4.3.0 on Nov 27 came out right after; the table keeps the versions of the snapshot). The course is built on ArduPilot 4.7.3 (Copter and Plane, tagged Nov 14, 2026; differences from 4.7.2 are in `ap-intro`), PX4 1.18.0 (tagged Nov 23, 2026; differences from 1.17.0 are in `px4-intro`), Betaflight 2025.12.5, INAV 9.1.0, ExpressLRS 4.1.0; the newer Betaflight 2026.6.2 (Sep 17, 2026) is already out, and the course covers its differences only where people trip over them (the "in 2026.6 …" notes in `bf-intro`).

| Tool | Version (tag date) | Used for | Compatibility, what was checked |
|---|---|---|---|
| Betaflight App (formerly Configurator) | 2026.6.2 (Sep 17, 2026) | Betaflight: setup, CLI, flashing, Blackbox | accepts firmware with MSP API ≥ 1.44 (`API_VERSION_ACCEPTED` in `data_storage.js`); 4.5 reports 1.46, 2025.12 reports 1.47 (`msp_protocol.h`); with older firmware it opens only the CLI |
| Blackbox Explorer | 2025.12.1 (Feb 14, 2026) | Betaflight `.BFL` logs | reads 4.x and 2025.12 logs |
| INAV Configurator | 9.1.1 (Jul 12, 2026) | INAV: setup, missions | accepts firmware from 9.0.0 up to < 10.0.0 (`data_storage.js`): the major version must match |
| Mission Planner | 1.3.83 (tagged Sep 10, 2025; master on Nov 25, 2026 is still 1.3.83) | ArduPilot, Windows | updates parameter descriptions from the network; a parameter under its old name simply will not be found in 4.7 |
| QGroundControl | 5.1.5 (Sep 30, 2026) | PX4 and ArduPilot, Windows/macOS/Linux/Android | the main GCS for PX4 |
| MAVProxy / pymavlink | 1.8.75 / 2.4.50 (PyPI, Sep 24, 2026) | console GCS, MAVLink from Python, MAVExplorer | `pip install` into a venv |
| pyulog | 1.3.0 (PyPI, Oct 20, 2026) | PX4 logs from Python | — |
| MAVSDK-Python | 4.2.1 (PyPI, Nov 17, 2026) | controlling the vehicle from Python | covered in `mav-sdk` |
| orangebox | 0.5.0 (PyPI, May 16, 2026) | Betaflight logs from Python | install it as a separate, last command: `pip install orangebox` prints an ERROR about the `bb2csv` entry point and exits with code 1, but the library does get installed and `from orangebox import Parser` works; in one command with other packages this error aborts the installation of the rest (checked) |
| PlotJuggler | 4.2.0 (Nov 25, 2026) | plots of `.ulg`, CSV, ROS 2 bags | — |
| ExpressLRS Configurator | 1.8.5 (Nov 14, 2026) | building and flashing ELRS | both ends of the link on the same ELRS major version (`link-elrs`) |
| EdgeTX / Companion | 2.12.5 (Oct 17, 2026) | transmitter firmware, models | Companion of the same version as the transmitter |
| ArduPilot SITL | Copter 4.7.3 (course; the lab below was recorded on 4.7.2) | ArduPilot simulation | `sim_vehicle.py` or the `arducopter` binary |
| PX4 SITL | 1.18.0 (course; the `px4_sitl_default` build and a `sihsim_quadx` run were checked on v1.18.0), Gazebo Harmonic | PX4 simulation | `Tools/setup/ubuntu.sh` installs `gz-harmonic` on Ubuntu 22.04 and 24.04 |

The dates are the dates of the commit under the tag; each project has its own idea of "stable": Mission Planner updates within 1.3.83, while Betaflight App and Betaflight firmware version numbers match the year and month of release.

### Why the tool version is not a detail
A tool and the firmware talk over a protocol, and each protocol has its own way of breaking when versions do not match. Knowing the mechanism is more useful than remembering versions: it tells you what to check first.

- **MSP (Betaflight, INAV).** The configurator asks the flight controller for its API version and decides what it can show. Betaflight App has a lower bound: it will not configure firmware older than MSP API 1.44 and instead offers an update and lets you into the CLI only (from the `serial_backend.js` code in 2026.6.2). INAV is stricter, with a window on the firmware major version: Configurator 9.1.1 works with 9.x, and with 8.x or 10.x it says the version is not supported and opens only the CLI (`serial_backend.js`). Hence the rule: first update the configurator to match the firmware, then connect.
- **MAVLink (ArduPilot, PX4).** The protocol is backward compatible: a GCS of any version sees the heartbeat and the parameters. What breaks is not the messages but the parameter names. In ArduPilot 4.7 some parameters were renamed in the move to meters (`RTL_ALT` in centimeters became `RTL_ALT_M` in meters; `ARMING_CHECK`, a mask of enabled checks, was replaced by `ARMING_SKIPCHK`, a mask of skipped ones: the value is not carried over but recalculated). Writing the old name produces no error: the firmware simply does not reply, and a `.param` file with old names "loads" only partly. You can see this in the lab: `RTL_ALT` gets "no answer," `RTL_ALT_M` is acknowledged.
- **Firmware builders (ExpressLRS Configurator, Betaflight Cloud Build).** The tool builds whatever version you chose; a mismatch shows up only in operation: a 3.x receiver will not bind to a 4.x transmitter (`link-elrs`).
- **Transmitter model files.** EdgeTX stores models in YAML; Companion must be the same version as the transmitter firmware, otherwise a model saved by a newer version is not read completely by an older one (course guideline: keep Companion and the transmitter on the same version).

The course's practical rule: the firmware, configurator and GCS versions are written into the vehicle log next to every `diff all` or `.param`, and only diffs of the same firmware version are compared.

### Task → tool
| Task | Betaflight | INAV | ArduPilot | PX4 |
|---|---|---|---|---|
| Set up from scratch | Betaflight App (`bf-setup-scratch`) | INAV Configurator (`inav-setup-scratch`) | Mission Planner or QGC (`ap-setup-scratch`) | QGroundControl (`px4-setup-scratch`) |
| Save the config as text | `diff all` in the CLI (`bf-cli`) | `diff all` in the CLI | `.param` from the GCS or MAVProxy `param save` | `.params` from QGC, `param save` in the console |
| Analyze a log | Blackbox Explorer, PIDscope (`bf-blackbox`) | Blackbox Explorer (INAV fork) | Mission Planner, MAVExplorer, UAV Log Viewer, WebTools (`ap-logs`) | Flight Review, PlotJuggler |
| Your own log metrics | `orangebox` | `orangebox` | `pymavlink.DFReader` (`data-python`) | `pyulog` (`data-python`) |
| Simulation | Betaflight SITL | INAV SITL | ArduPilot SITL (`ap-sitl`) | PX4 SITL + Gazebo (`tools-gazebo`) |
| Control from a program | MSP over `pyserial` (`bf-cli-automation`) | MSP | `pymavlink`, MAVSDK, MAVProxy | MAVSDK, uXRCE-DDS (ROS 2) |
| Flash an ESC | ESC Configurator, Bluejay/AM32 (`f-esc-firmware`) | the same | the same, or DShot/BLHeli passthrough | the same |

How to choose when there are several tools. First, the one maintained by the firmware project (Betaflight App, INAV Configurator, QGC for PX4): it is the first to support new parameters. Mission Planner for ArduPilot has more complete setup screens than QGC (Full Parameter List, MAVFtp, log analysis), but runs only on Windows; on Linux its functions are covered by QGC plus MAVProxy. New open GCSs for ArduPilot (for example ArduDeck and ADOS Mission Control, discussed on the ArduPilot forum discuss.ardupilot.org) are still in development as of November 2026, so the course does not build its setup on them. Web versions (Betaflight App in the browser, ESC Configurator) are handy for a quick look, but the desktop version is more reliable for flashing in DFU.

{{diagram:tools-firmware-tree|Firmware first, then the tool: each firmware has its own configurator and log format, and the configurator/firmware version match is checked before connecting.}}

{{lesson:ap-sitl|ArduPilot SITL from scratch: launching, MAVProxy, injecting failures: an environment for any check before the real vehicle.}}

{{lesson:data-python|Analyzing DataFlash and ULog logs in Python: metrics, spectra and step responses with your own scripts.}}

### Installation order (Linux / WSL2)
```bash
sudo apt install git python3-venv picocom build-essential
python3 -m venv ~/uav && . ~/uav/bin/activate
pip install pymavlink MAVProxy pandas numpy scipy matplotlib pyserial
sudo usermod -aG dialout $USER     # access to /dev/ttyACM*/ttyUSB*; re-login
git clone --depth 1 https://github.com/ArduPilot/ardupilot && cd ardupilot && Tools/environment_install/install-prereqs-ubuntu.sh -y
```
Check: with `sim_vehicle.py -v ArduCopter` running, a second `mavproxy.py --master=udp:127.0.0.1:14550` receives its UDP output (SITL's tcp:5760 is already taken by sim_vehicle.py's own MAVProxy and accepts one client; to connect to it yourself, start `sim_vehicle.py -v ArduCopter --no-mavproxy` and use `--master=tcp:127.0.0.1:5760`). In WSL2, USB devices are passed through with `usbipd` (Windows 11); or use Windows applications for USB and Linux for scripts and logs.

### Where things are logged (so you can find them later)
Betaflight: flash on the FC → download through the configurator (Blackbox tab) as `.BFL`; ArduPilot: SD card `/APM/LOGS/*.BIN` or MAVFtp from Mission Planner; GCS telemetry logs (`.tlog`) are separate and contain everything that went over MAVLink; PX4: `.ulg` on the SD card, viewed with Flight Review (web) or `pyulog`. Naming: `YYYY-MM-DD_vehicle_purpose.ext` in the vehicle's folder.

{{diagram:toolbox-map|The engineer's minimal toolset, by task.}}

### Where it fits

- **Takes in:** from the vehicle, configs (`diff all` from `bf-cli`, `.param`) and logs (`.BFL`, `.BIN`, `.ulg`); from the task, what exactly needs to be done: set up, flash, analyze a log, simulate.
- **Hands off:** the right tool for the task to every track: the Python stack to `data-python`, the simulator to `ap-sitl`, the folder structure and git for configs to `eng-ci-configs`.
- **If you get this wrong:** you did not save a "before" file → after a failed edit there is nothing to compare against and nothing to roll back to → the cause is hunted down through the troubleshooting tree blindly (`diag-troubleshooting`). You tested a script or parameter straight on the vehicle, skipping the simulator → the error shows up only in the field (`ap-sitl`).

## practice
### Minimal installation
1. Betaflight App, Mission Planner or QGroundControl.
2. Python 3 + `pip install pyserial pymavlink scipy matplotlib` in a venv, then `pip install orangebox` separately (it will exit with an ERROR about `bb2csv`, but the library gets installed).
3. Git; a `drones/` repository with the structure above.
4. A serial terminal.
5. For ArduPilot, SITL following the "SITL: a drone without a drone" module.

### First commit
1. Connect the drone, `diff all` in the CLI (or save a `.param`).
2. Save it to `drones/<name>/configs/<date>_<name>_<board>_diff.txt`.
3. `git add`, `git commit -m "<name>: baseline <date>"`.
4. After any change, a new file and a commit describing what and why.

### SITL lab (done): stack, `.param`, git
No vehicle needed: the same "save → commit → change one thing → compare" cycle runs on ArduCopter 4.7.2 SITL. Preparation: `python3 -m venv ~/uav && . ~/uav/bin/activate && pip install pymavlink MAVProxy pyulog mavsdk pyserial numpy scipy matplotlib`, then, as a separate last command, `pip install orangebox`. It will finish with an ERROR about `bb2csv` and exit code 1, but the library gets installed (`from orangebox import Parser` works). In one command with other packages this error aborts the installation of the rest, and the script then fails on the very first line, the one with the versions. Start SITL: `arducopter -S --model + -I 6 -w --defaults Tools/autotest/default_params/copter.parm --home -35.363261,149.165230,584,353`, then `python3 tools_lab.py tcp:127.0.0.1:5820 ~/lab-repo`. The script prints the stack versions, waits 60 s, saves all parameters to `drones/sitl-copter/configs/2026-11-26_sitl-copter_SITL.param`, commits, tries to write `RTL_ALT` (the pre-4.7 name) and `RTL_ALT_M` (the 4.7 name), saves again after 20 s and shows the `git diff`.

```python
"""tools-overview lab: versions of the Python stack, then config-as-code with ArduCopter SITL:
save .param (Mission Planner format NAME,VALUE) -> git commit -> change one parameter -> save -> git diff."""
import subprocess, sys, time
from importlib.metadata import version
from pathlib import Path
from pymavlink import mavutil
for p in ("pymavlink", "MAVProxy", "pyulog", "mavsdk", "orangebox", "pyserial", "numpy", "scipy", "matplotlib"):
    print(f"{p:11s} {version(p)}")
repo = Path(sys.argv[2]); cfg = repo / "drones/sitl-copter/configs"; cfg.mkdir(parents=True, exist_ok=True)
def git(*a): return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True).stdout.strip()
m = mavutil.mavlink_connection(sys.argv[1]); m.wait_heartbeat()
def fetch():
    m.param_fetch_all(); got = {}; total = None
    while total is None or len(got) < total:
        p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=10)
        if p is None: break
        got[p.param_id] = p.param_value; total = p.param_count
    return got
def save(name, params):
    (cfg / name).write_text("".join(f"{k},{v:g}\n" for k, v in sorted(params.items())))
    return len(params)
time.sleep(60)     # baseline only after boot calibrations (gyro offsets, baro ground pressure) are done
def setp(name, val):
    m.mav.param_set_send(m.target_system, m.target_component, name.encode(), val, mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
    ack = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=3,
                       condition=f"PARAM_VALUE.param_id=='{name}'")
    print(f"set {name}={val}: " + (f"ack {ack.param_value:g}" if ack else "no answer - no such parameter"))
git("init", "-q"); git("config", "user.email", "me@example.invalid"); git("config", "user.name", "me")
n = save("2026-11-26_sitl-copter_SITL.param", fetch()); print(f"saved {n} params")
git("add", "-A"); git("commit", "-q", "-m", "sitl-copter: baseline 2026-11-26 (ArduCopter 4.7.2 SITL)")
setp("RTL_ALT", 3000)     # the 4.6 name, centimetres
setp("RTL_ALT_M", 30)     # the 4.7 name, metres
time.sleep(20)            # let the vehicle run a while, like a real bench session
save("2026-11-26_sitl-copter_SITL.param", fetch())
git("commit", "-q", "-am", "sitl-copter: RTL_ALT_M 15->30: return above 25 m trees")
print(git("log", "--oneline"))
print(git("diff", "-U0", "HEAD~1", "--", "drones"))
```

Output of the run in the author's environment (ArduCopter 4.7.2 SITL, Python 3.13):

```text
pymavlink   2.4.50
MAVProxy    1.8.75
pyulog      1.3.0
mavsdk      4.2.1
orangebox   0.5.0
pyserial    3.5
numpy       2.5.5
scipy       1.18.1
matplotlib  3.11.2
saved 1370 params
set RTL_ALT=3000: no answer - no such parameter
set RTL_ALT_M=30: ack 30
89ad5f7 sitl-copter: RTL_ALT_M 15->30: return above 25 m trees
7487194 sitl-copter: baseline 2026-11-26 (ArduCopter 4.7.2 SITL)
diff --git a/drones/sitl-copter/configs/2026-11-26_sitl-copter_SITL.param b/drones/sitl-copter/configs/2026-11-26_sitl-copter_SITL.param
index 4a5d4f5..2c809a9 100644
--- a/drones/sitl-copter/configs/2026-11-26_sitl-copter_SITL.param
+++ b/drones/sitl-copter/configs/2026-11-26_sitl-copter_SITL.param
@@ -824 +824 @@ RTL_ALT_FINAL_M,0
-RTL_ALT_M,15
+RTL_ALT_M,30
```

What this shows. Of the two writes, only `RTL_ALT_M` was acknowledged; `RTL_ALT` does not exist in 4.7.2, and the firmware simply stayed silent: a `.param` with old names would have loaded "successfully," but without this parameter. The diff has exactly one line because the baseline file was taken after the boot calibrations finished. In the author's first run the baseline was taken right after startup, and `git diff` showed 17 parameters that had changed on their own: `BARO1_GND_PRESS` and `BARO2_GND_PRESS` (ground pressure), `INS_GYROFFS_*` and `INS_GYR2OFFS_*` (gyro offsets), `INS_GYR1_CALTEMP`, the sensor IDs `INS_*_ID`, `COMPASS_DEC`, `MIS_TOTAL`. Such parameters in a diff are not your edit but the vehicle's state; recognize them by name and do not mistake them for a settings change.

### What you should get
After two commits, `git log --oneline drones/<name>/configs/` shows two lines with clear descriptions, and `git diff` between the files shows exactly one changed line:

```text
-set rpm_filter_min_hz = 100
+set rpm_filter_min_hz = 50
```

If the difference has more lines than you changed, unexpected changes got into the diff: a different firmware version (new or renamed settings), someone else's edits, a reset to defaults. That is a reason to sort it out before flying, not after. Compare diffs of the same firmware version. After a firmware update, make a separate baseline commit, "baseline after update."

### Typical mistakes
- A file name without the date or the board: a month later you cannot tell what it is or where it came from.
- Saving a `dump` instead of `diff all`: a dump has hundreds of lines of default values, and the useful change gets lost in it.
- A commit with no "why." Six months later "changed filter" tells you nothing, while "rpm_filter_min_hz 100→50: 10" motors below 100 Hz in hover" does.

### Lab
Make two diffs that differ in one parameter and look at the `git diff` between them. This is the first "code review" of your own drone.

Self-check: the lab is done when **(SITL)** the script printed the stack versions (pymavlink 2.4.x, MAVProxy 1.8.x, or newer, in which case record yours), 1370 ± 50 ArduCopter 4.7.x parameters are saved, `RTL_ALT` gave "no answer," `RTL_ALT_M` gave "ack 30," and `git diff` shows exactly two lines, `-RTL_ALT_M,15` / `+RTL_ALT_M,30`; **(your vehicle)** the `drones/` repository is created with the structure, the config is saved with the date and board in its name and committed with a description, `git log --oneline drones/<name>/configs/` shows two lines with clear descriptions, and `git diff` of the two configs shows exactly one changed line, the one you changed, with the "why" in the commit message.

**Reference answer for self-check.** Correct result: one changed line and a message like "rpm_filter_min_hz 100→50: 10" motors below 100 Hz in hover." Typical wrong results: (1) the difference has more lines than you changed: a different firmware version or a reset to defaults got into the diff; sort it out before flying; (2) the difference has hundreds of lines: a `dump` was saved instead of `diff all`; (3) the SITL diff has `INS_GYROFFS_*`, `BARO*_GND_PRESS`, `INS_*_ID` lines: the baseline was taken before the boot calibrations finished; wait 60 s and take it again; (4) the diff has no RTL line: `RTL_ALT` was written instead of `RTL_ALT_M`, the name from before 4.7.

## diagnostics
- **Symptom:** the configurator does not see the board
  - Possible cause: the driver (Windows), a charge-only cable, the board in DFU.
  - What to do: Zadig for DFU, a different cable, check the COM port.
- **Symptom:** I don't remember what I changed before it broke
  - Possible cause: no "before/after" diffs.
  - What to do: the "a file before any change, always" rule, git.
- **Symptom:** I loaded a `.param` into ArduPilot 4.7, there were no errors, but some settings did not apply
  - Possible cause: the file has pre-4.7 parameter names (`RTL_ALT`, `ARMING_CHECK`); the firmware silently ignores writes to unknown names.
  - What to do: compare the file with the full parameter list after loading (`git diff`), rename following the release notes (`ap-setup-scratch`); `ARMING_CHECK` is not renamed but recalculated into `ARMING_SKIPCHK` (a mask of skipped checks, the opposite meaning).
- **Symptom:** INAV Configurator says the firmware version is not supported and opens only the CLI tab
  - Possible cause: the major versions do not match (Configurator 9.x accepts only 9.x firmware).
  - What to do: install a Configurator with the same major version as the firmware, or update the firmware.
- **Symptom:** `pip install` into the system Python answers "externally-managed-environment"
  - Possible cause: Ubuntu 23.04+ (every LTS from 24.04 on) forbids installing packages into the system Python (PEP 668).
  - What to do: `python3 -m venv` per project; a `requirements.txt` with exact versions.
- **Symptom:** Python libraries conflict between projects
  - Possible cause: everything is installed into the system Python.
  - What to do: a venv per project.

## references
- Betaflight App — Documentation | https://betaflight.com/docs/wiki/app | primary | A
- Mission Planner — Documentation | https://ardupilot.org/planner/ | primary | A
- QGroundControl — User Guide | https://docs.qgroundcontrol.com/Stable_V5.0/en/ | primary | A
- MAVProxy — Documentation | https://ardupilot.org/mavproxy/ | primary | A
- Pro Git — book | https://git-scm.com/book/en/v2 | primary | A
- Betaflight App 2026.6.2 source — src/js/data_storage.js (API_VERSION_ACCEPTED 1.44, MAX_SUPPORTED 1.48), src/js/serial_backend.js | https://github.com/betaflight/betaflight-configurator/blob/2026.6.2/src/js/data_storage.js | primary | A
- INAV Configurator 9.1.1 source — js/data_storage.js (minfirmwareVersionAccepted 9.0.0, maxFirmwareVersionAccepted 10.0.0) | https://github.com/iNavFlight/inav-configurator/blob/9.1.1/js/data_storage.js | primary | A
- PX4 1.18.0 — Tools/setup/ubuntu.sh (Gazebo Harmonic on Ubuntu 22.04+) | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/Tools/setup/ubuntu.sh | primary | A
- PyPI — pymavlink, MAVProxy, pyulog, mavsdk, orangebox (versions and dates as of 2026-11-25) | https://pypi.org/project/pymavlink/ | primary | A

## checklist
- A configurator and a ground station for my firmware are installed
- Python in a venv with pyserial/pymavlink, a `requirements.txt` with versions
- The firmware, configurator/GCS and Python stack versions are written in the vehicle log
- The configurator has the same major version as the firmware (INAV) or is within the MSP API window (Betaflight)
- A `drones/` repository with a folder per drone
- Every config is a file with a date in its name, in git
- Before any change there is always a "before" file
