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

{{diagram:config-change-flow|The “before/after” rule: the file before the change, a commit, one change — and git diff must show exactly one line; extra lines are sorted out before flying.}}

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

{{diagram:tools-firmware-tree|Firmware first, then the tool: every firmware has its own configurator and log format, and the configurator and firmware versions are checked for a match before connecting.}}

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

### SITL lab (done): the stack, `.param`, git

You do not need an aircraft: the same “save → commit → change one thing → compare” cycle runs on ArduCopter 4.7.2 SITL. Setup: `python3 -m venv ~/uav && . ~/uav/bin/activate && pip install pymavlink MAVProxy pyulog mavsdk pyserial numpy scipy matplotlib`, then `pip install orangebox` as a separate, last command. It ends with an ERROR about `bb2csv` and exit code 1, but the library gets installed (`from orangebox import Parser` works). In one command with the other packages this error aborts installing the rest, and the script fails on its very first line with the versions. Start SITL: `arducopter -S --model + -I 6 -w --defaults Tools/autotest/default_params/copter.parm --home -35.363261,149.165230,584,353`, then `python3 tools_lab.py tcp:127.0.0.1:5820 ~/lab-repo`. The script prints the stack versions, waits 60 s, saves all parameters to `drones/sitl-copter/configs/2026-11-26_sitl-copter_SITL.param`, commits, tries to write `RTL_ALT` (the pre-4.7 name) and `RTL_ALT_M` (the 4.7 name), saves again after 20 s and shows `git diff`.

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

Output of a run in the author's environment (ArduCopter 4.7.2 SITL, Python 3.13):

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

What this shows. Of the two writes only `RTL_ALT_M` is confirmed; `RTL_ALT` does not exist in 4.7.2, and the firmware simply stayed silent — a `.param` with the old names would load “successfully”, just without this parameter. The diff has exactly one line because the baseline file was taken after the boot calibrations had finished. In the author's first run the baseline was taken right after startup, and `git diff` showed 17 parameters that had changed by themselves: `BARO1_GND_PRESS` and `BARO2_GND_PRESS` (ground pressure), `INS_GYROFFS_*` and `INS_GYR2OFFS_*` (gyro offsets), `INS_GYR1_CALTEMP`, the sensor IDs `INS_*_ID`, `COMPASS_DEC`, `MIS_TOTAL`. Such parameters in a diff are not your edit but the aircraft's state; recognize them by name and do not mistake them for a settings change.

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
