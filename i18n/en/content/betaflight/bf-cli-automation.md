---
id: bf-cli-automation
title: "Automating the CLI over serial: the pitfalls"
level: L3
readingTime: 25 min
firmware: Betaflight 4.5+
status: published
added: 2026-11-07
tags:
  - CLI
  - automation
  - Python
related:
  - bf-cli
  - bf-rpm-filter
next: []
source: content/betaflight/bf-cli-automation.md
source_hash: 915000400e1d
---

## summary
Once you have more than one drone, configuring them by clicking around in Configurator is a road to mistakes. The Betaflight CLI is available over an ordinary serial port, which means you can script it. This module shows a working Python template (`pyserial`) and collects the pitfalls we actually stepped on while configuring several quadcopters in bulk: floating COM ports, “silent” parameter corrections, reboots and diff incompatibility between versions.

## theory
### How entering the CLI works
Over USB, a flight controller is a virtual COM port (USB CDC). The baud rate in the port settings doesn't matter for USB CDC; 115200 is the convention. The `#` character puts the controller into the CLI, `exit` leaves it with a reboot. While the FC is in the CLI, no signal goes to the motors — the ESCs may beep, that's normal.

### Pitfall 1: the COM port isn't fixed
If several identical boards are connected to the computer, they share one USB VID/PID, and the COM port number changes after every reboot. You can't bind to `COM8`. The reliable identifier is the `craft_name` inside the config: open each port, enter the CLI, run `get craft_name` and pick the right one. Hence the rule: every drone gets a distinct `craft_name` before you start working.

### Pitfall 2: exit noreboot reboots
In Betaflight 4.5.0–4.5.3 the `exit` command always reboots the controller (the `noreboot` argument appeared in 4.5.4 and 2025.12.x). So after any `exit` the script has to find the port again by `craft_name`. When you “just want to peek at a value”, don't leave the CLI with a command — just close the port.

### Pitfall 3: silent corrections
`set` + `save` doesn't guarantee that the value stayed the way you wrote it. On boot, Betaflight corrects incompatible combinations: the DShot protocol, bidirectional DShot, the timer layout on a specific board. In our practice, on an F405 board, after enabling bidir the DShot protocol turned out not to be what we had written. Rule: after every `save` and reboot, re-read every changed value with `get` and compare it with the expected one.

### Pitfall 4: a diff doesn't carry over between versions
Parameter names and meanings change between firmware versions: `debug_mode` values get renamed, the `serial` command syntax changes, the meaning of the D-term PID parameters changes. You can't paste a `diff all` from 2025.12 into 4.5 (or vice versa) line by line. Moving settings between versions only works deliberately, section by section, with re-reading.

### Why diff and not dump
`diff all` contains only the differences from defaults — you can read it by eye and keep it in git. `dump` is everything at once; when you update the firmware it drags the old defaults along as explicit values.

### Minimal script for exporting `diff all` (pyserial)
```python
import serial, time, sys, glob

def cli(port, cmds, timeout=3.0):
    """Open CLI, run commands, return full text. Do not send 'exit' (reboots on 4.5)."""
    with serial.Serial(port, 115200, timeout=0.2) as s:
        s.write(b"#\n"); time.sleep(0.5); s.read(s.in_waiting or 1)
        out = ""
        for c in cmds:
            s.write((c + "\n").encode()); t0 = time.time(); buf = ""
            while time.time() - t0 < timeout:
                chunk = s.read(4096).decode(errors="replace")
                if chunk: buf += chunk; t0 = time.time()
                if buf.rstrip().endswith("# "): break        # prompt returned
            out += buf
        return out

ports = glob.glob("/dev/ttyACM*")                              # Linux; Windows: COM*
for p in ports:
    name = cli(p, ["get craft_name"])
    if "viking7" in name:
        text = cli(p, ["version", "diff all"])
        open("viking7/betaflight/diff-all.txt", "w").write(text)
        break
else:
    sys.exit("craft not found")
```
Normalize before committing: strip the date/time lines from `version` and the `# ` echo, sort the blocks — otherwise `git diff` gets noisy (the “CI” module).

### What's worth automating and what isn't
Worth it: a `diff all` backup before every flying day; checking invariants (failsafe, poles, bidir) from the export; bulk changes of `craft_name`/VTX table across the fleet; downloading logs via `msc`. Not worth it: bulk “rolling out PIDs” to different vehicles (different mechanics), any change without re-reading with `get` after `save`.

{{diagram:bf-cli-session|A CLI session over serial: wait for the prompt, re-read values after set, find the port again after save.}}

## practice
### Step 1. A minimal CLI client in Python
```python
import time
import serial
from serial.tools import list_ports


def cli_cmd(port: serial.Serial, cmd: str, wait: float = 0.6) -> str:
    port.write((cmd + "\n").encode())
    time.sleep(wait)
    return port.read_all().decode(errors="replace")


def enter_cli(port: serial.Serial) -> None:
    port.write(b"\n")
    time.sleep(0.3)
    port.read_all()
    port.write(b"#")
    time.sleep(1.2)
    port.read_all()


def find_craft(craft_name: str) -> str:
    """Return the COM port of the FC whose craft_name matches. Never trust COM numbers."""
    for info in list_ports.comports():
        try:
            with serial.Serial(info.device, 115200, timeout=1) as p:
                enter_cli(p)
                out = cli_cmd(p, "get craft_name")
                # do NOT send exit here: on 4.5.x it reboots the FC
                if f"craft_name = {craft_name}" in out:
                    return info.device
        except serial.SerialException:
            continue
    raise RuntimeError(f"FC '{craft_name}' not found")
```

### Step 2. Applying changes with verification
```python
CHANGES = {"rpm_filter_min_hz": "50", "failsafe_delay": "15"}

port_name = find_craft("viking2")
with serial.Serial(port_name, 115200, timeout=1) as p:
    enter_cli(p)
    backup = cli_cmd(p, "diff all", wait=3.0)
    open("viking2_before_diff.txt", "w", encoding="utf-8").write(backup)
    for key, val in CHANGES.items():
        cli_cmd(p, f"set {key} = {val}")
    cli_cmd(p, "save", wait=1.0)  # FC reboots, COM port may change

time.sleep(6)
port_name = find_craft("viking2")  # find it again after reboot
with serial.Serial(port_name, 115200, timeout=1) as p:
    enter_cli(p)
    for key, val in CHANGES.items():
        out = cli_cmd(p, f"get {key}")
        ok = f"{key} = {val}" in out
        print(("OK  " if ok else "FAIL"), key, "expected", val)
```

### Step 3. Keep configs as code
1. A folder per drone, with `configs/` and `logs/` inside.
2. File name: `<drone>_<board>_<YYYY-MM-DD>_diff.txt` — sorting by name = sorting by date.
3. Before changes — a backup, after — a new diff; compare them with a plain `git diff`.

### Step 4. A second drone and comparison
Run the same script for the second drone, changing only the `craft_name` in the arguments — not the code. Compare the before and after backups with `git diff --no-index viking2_before_diff.txt viking2_after_diff.txt`: the difference should be exactly the lines from `CHANGES` and nothing more. An extra line means someone changed settings by hand between backups, and that's a reason to sort it out before you fly.

### What you should get and typical failures
- `find_craft` prints the list of polled ports and finds the right one by `craft_name`. If the drone isn't found, check that `craft_name` is set (`get craft_name`) and that Configurator is closed: it holds the port and floods it with MSP traffic.
- `diff all` on an F7/H7 with a large config doesn't finish within 3 s, and the backup gets cut off in the middle. It's more reliable to read until the CLI prompt `# ` at the end of the output than to wait a fixed time.
- After `save` the board reboots, and on Windows the COM port may change — that's why `find_craft` is called again. 6 s of waiting is enough for most boards. If it isn't, search for the port in a loop with a timeout.
- The verification result is an `OK` line for each key. Any `FAIL` means the value wasn't saved or the key has a different name in this version (Betaflight 2025.12 renamed some settings — the “CLI” module).

The lab counts as done when the script finds the drone by `craft_name`, saves a dated `diff all` before the changes, finds the port again after `save` and re-reads the values with all `OK`, and a run on two drones passes without editing the code.

## diagnostics
- **Symptom:** the script “lost” the drone after save
  - Possible cause: after the reboot the COM port got a different number.
  - What to do: find the port again by `craft_name`, not by number.
- **Symptom:** the written value is different after a reboot
  - Possible cause: Betaflight corrected an incompatible combination.
  - What to do: re-read the related parameters, check against the board and firmware documentation.
- **Symptom:** after pasting a diff, some lines gave `Invalid name` errors
  - Possible cause: the diff is from a different firmware version.
  - What to do: move settings section by section, checking parameter names in `help` of the current version.
- **Symptom:** two drones respond to the same `craft_name`
  - Possible cause: identical names (a cloned config).
  - What to do: rename right away, `set craft_name = ...` + `save`.

## references
- Betaflight CLI — Documentation | https://betaflight.com/docs/wiki/guides/current/Cli | primary | A
- pySerial — Documentation | https://pyserial.readthedocs.io/en/latest/ | primary | A
- Betaflight — source code (GitHub) | https://github.com/betaflight/betaflight | primary | A

## checklist
- Every drone has a unique `craft_name`
- The script finds the port by `craft_name`, not by COM number
- A `diff all` with the date in the file name is saved before any change
- After `save` the script finds the port again and re-reads the values
- A diff from a different firmware version is never pasted line by line
