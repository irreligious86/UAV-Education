---
id: bf-cli-automation
title: "Automating the CLI over serial: the pitfalls"
level: L3
readingTime: 45 min
firmware: "Betaflight 4.5.3 and 2025.12.5 (sources and SITL of both versions); pyserial 3.5"
status: published
added: 2026-11-07
tags:
  - CLI
  - MSP
  - automation
  - Python
related:
  - bf-cli
  - bf-rpm-filter
  - eng-ci-configs
next: []
source: content/betaflight/bf-cli-automation.md
source_hash: 9c82534af3b3
---

## summary
Once you have more than one drone, configuring them by clicking through the Configurator is a recipe for mistakes. The Betaflight CLI is available over an ordinary serial port, so it can be scripted, and a board can be identified without the CLI at all — over the MSP protocol. This module shows how the firmware switches a port between MSP and the CLI, what format the CLI replies in and how to tell a reply from the prompt, and collects the pitfalls of bulk configuration: floating COM ports, `save` and `exit` that reboot (in 4.5.3 — even with `noreboot`), “silent” value fixes on save and at boot, the substring search in `get`, batch mode, and the incompatibility of `diff all` between 4.5 and 2025.12. The lab needs no hardware: on SITL builds of Betaflight 4.5.3 and 2025.12.5 made from source, a Python script does everything it would do with a board over USB and catches real value fixes made by the firmware.

## theory
### How entering the CLI works
A flight controller on USB is a virtual COM port (USB CDC). The baud rate in the port settings does not matter for USB CDC; 115200 is the convention. The `#` character puts the controller into the CLI, `exit` leaves it with a reboot.

The mechanism comes from the sources (`msp/msp_serial.c`, `cli/cli.c`, the same in 4.5.3 and 2025.12.5 unless stated otherwise). By default the port listens for MSP. Every byte that is not part of an MSP frame is treated by the firmware as “non-MSP data”: a `#` byte queues a request to enter the CLI, a `reboot_character` byte (`R` by default, code 82, range 48–126) queues a request to reboot into the bootloader. The request is executed only once the port has been silent for 100 ms, and the versions behave differently: in 4.5.3 any byte that arrives before those 100 ms have elapsed, on the next pass of the task, cancels the entry (`msp_serial.c:519–522`: “abort pending request”) — `#` followed immediately by a command gives “the CLI did not open”; in 2025.12 only `$` clears the request (`msp_serial.c:535–539`), but bytes that arrive before the entry are lost. The order for both: `#`, wait for the prompt, then the commands. While the aircraft is armed, non-MSP bytes are ignored (`fc/tasks.c`: `ARMING_FLAG(ARMED) ? MSP_SKIP_NON_MSP_DATA`): on an armed drone `#` does nothing, and that is a protection, not a bug. The same mechanism gives a pitfall: a script that sends arbitrary text to the port before entering the CLI may accidentally send `R` and drop the board into DFU.

After the entry the firmware prints `Entering CLI Mode, type 'exit' to return, or 'help'` (in 2025.12 — `... to reboot ...`), sets the `CLI` arming disable flag and prints the prompt — exactly the 4 bytes `\r\n# `. The CLI echoes every character it receives, so the reply to a command is the echo, a line break, the output and `\r\n# ` again. A line longer than 256 characters (`CLI_IN_BUFFER_SIZE`) is silently truncated, and everything after `#` in a line is treated as a comment (so if the board is already in the CLI from a previous session, a lone `#` starts a comment and swallows the next command: in testing the short script below, that is how the `version` command was lost; the safe entry is `#\n` sent in a single write to the port: then both bytes arrive in one pass, and it works in both states), and errors are printed in the format `###ERROR IN <command>: <text>###`. In the CLI all bytes of the port go to the CLI: MSP does not answer on this port (in 4.5.3 — on any port: `fc/tasks.c` returns before `mspSerialProcess`; in 2025.12 the CLI state is kept per port, and the other MSP ports work), Blackbox does not log (`fc/core.c`: `if (!cliMode && blackboxConfig()->device)`), and the telemetry task does not run (`fc/tasks.c`: `if (!cliMode && featureIsEnabled(FEATURE_TELEMETRY))`). The Configurator shows “no connection” during this time — that is normal.

### MSP: identify a board without entering the CLI
MSP v1 is the Configurator's binary protocol: a request is `$M<`, a size byte, a command byte, the payload and a checksum — the XOR of the size, the command and the payload; a reply starts with `$M>`, and an unsupported command gives `$M!`. Five commands are enough to find the right board, and none of them requires the CLI, reboots, or sets an arming block:

| Command (number) | Reply | 4.5.3 (SITL) | 2025.12.5 (SITL) |
|---|---|---|---|
| `MSP_API_VERSION` (1) | protocol, major, minor | 1.46 | 1.47 |
| `MSP_FC_VARIANT` (2) | 4 characters | `BTFL` | `BTFL` |
| `MSP_FC_VERSION` (3) | 3 version bytes (in 2025.12 — also a Pascal string) | 4.5.3 | 25.12.5 (year − 2000, month, patch) + `2025.12.5`, 13 bytes in total |
| `MSP_NAME` (10) | `craft_name` | string | string |
| `MSP_UID` (160) | 3 × uint32, the unique ID of the MCU | 12 bytes | 12 bytes |

The pitfall is in the third row: with the move to calendar versioning, `MSP_FC_VERSION` in 2025.12 returns `25, 12, 5` (`msp.c`: `FC_VERSION_YEAR - FC_CALVER_BASE_YEAR`). A script with the check “major ≥ 4 means new” will take 2025.12 for version 25, and a script with “major == 4” will take it for unknown firmware. Compare versions by `MSP_API_VERSION`, by the full string from `version`, or by the string that 2025.12 appends to the `MSP_FC_VERSION` reply after the three bytes (`sbufWritePString(FC_VERSION_STRING)`, `msp.c:646`). On a real board `MSP_UID` is the factory serial number of the microcontroller, and it does not change on reflashing or `defaults`; in SITL it is fixed (`000000000100000002000000` in both versions), so in the lab identification goes by name.

### Pitfall 1: the COM port is not permanent
If several identical boards are connected to the computer, they share one USB VID/PID, and the COM port number changes after every reboot. You cannot bind to `COM8`. The reliable identifier is `craft_name` inside the config, and it should be read over MSP (`MSP_NAME`), not by entering the CLI on every port: entering the CLI sets an arming block until reboot, and on 4.5.3 you cannot leave the CLI without a reboot. Hence the rule: all drones have different `craft_name` values before the work starts; for a fleet of identical boards, also store `MSP_UID` next to the name — it catches a cloned config where two aircraft got the same name.

### Pitfall 2: exit noreboot reboots on 4.5.3
By default the `exit` command reboots the controller and prints `leaving CLI mode, unsaved changes lost` — everything not saved with `save` is lost. 2025.12 (and 4.5.5, checked in the sources; per the change history — from 4.5.4) has `exit noreboot` and `save noreboot`; 4.5.0–4.5.3 has no such argument, and `exit` always reboots. Worse: in 4.5.3 `cliSave` and `cliExit` simply do not read the argument (`UNUSED(cmdline)`), so `save noreboot` sent to 4.5.3 saves and reboots the board with no error. A script that must work on any of these versions has to search for the port by `craft_name` again after every `exit` and `save`. To “just peek at a value”, do not leave the CLI with a command — just close the port. One more 2025.12 detail: after `exit noreboot` the `CLI` arming disable flag stays until reboot — in the sources it is only ever set (`setArmingDisabled(ARMING_DISABLED_CLI)` in `cliEnter`, with the comment “arming flag not released if exiting cli with no reboot for safety”).

### The non-interactive mode of 4.5.5 and 2025.12: STX … ETX
4.5.5 and 2025.12 have a mode for programs (4.5.3 does not; `msp_serial.c:547` in 4.5.5): a `0x02` (STX) byte instead of `#` enters the CLI with no echo, no prompt and no arming block; the firmware replies `0x02`, executes the lines it is sent and prints only their output (an unknown command gives `ERR_CMD_NA: <line>`), and a `0x03` (ETX) byte, or the first byte that arrives more than 2 s after the entry, ends the session — the firmware replies `0x03` and keeps running without a reboot (`cli.c`, `cliProcess`). The two-second limit is checked only when a byte arrives: if nothing is sent after the reply, the port simply stays in the CLI (MSP is silent on it, Blackbox and telemetry are stopped), so a session is always ended with a `0x03` byte. In the lab `\x02get failsafe_delay\n\x03` returned `\x02failsafe_delay = 10\r\nAllowed range: 1 - 200\r\nDefault value: 15\r\n\x03`. For reading values on 4.5.5 and 2025.12 this is the safest path; in 4.5.3 a `0x02` byte is just garbage to MSP.

### Pitfall 3: silent fixes
`set` + `save` does not guarantee that the value stayed the way you wrote it. Betaflight corrects incompatible combinations in the `validateAndFixConfig()` function (`config/config.c`) — and does so twice: inside `save` before writing to EEPROM and on every boot. The reply `x set to 20` only means “written to RAM”. Examples verified in the sources and in SITL:

- 2025.12: if `d_max_<axis>` is less than `d_<axis>`, `d_max` is zeroed (`config.c:268`); in 4.5.3 it is the mirror image — a `d_min` greater than `D` is zeroed (`config.c:281`).
- Both versions, a flight board with a GPS build: `failsafe_procedure = GPS-RESCUE` with `feature GPS` disabled (or 3D, or an airplane mixer) is reset to `DROP` (`config.c:370` in 4.5.3, `:357` in 2025.12; derived from the code, not verified in SITL).
- 4.5.5 and 2025.12: any `failsafe_procedure` value outside the list of procedures of this build is reset to `DROP` (`config.c:373` in 4.5.5, `:360–361` in 2025.12); 4.5.3 has no such check. This is exactly what triggered in the lab: GPS Rescue is not built into the SITL of either version (`target/common_pre.h:72`: GPS drivers only with `!defined(SITL)`), the string `GPS-RESCUE` is accepted by the value table, but the firmware has no such procedure. 2025.12.5 reset it to `DROP` on `save noreboot`, 4.5.3 left it as it was.
- Both versions: bidirectional DShot (`dshot_bidir`) is turned off if the motor protocol is not DShot, or if bitbang is off while burst DShot is on or a motor sits on an N-channel of a timer (`config.c:556` in 4.5.3, `:472` in 2025.12). An observation from practice with no saved log: on an F405 board, after enabling bidir, the “protocol + bidir” combination after a reboot was not what had been written.

The rule: after every `save` and reboot — re-read every changed value with `get` and compare it with the expected one.

{{diagram:bf-cli-silent-fix|validateAndFixConfig runs twice — in save and at boot, so the “set to” confirmation guarantees nothing: the only check is reading with get after the reboot.}}

### Pitfall 4: get searches by substring
`get d_roll` prints every parameter whose name contains `d_roll` — in 4.5.3 that is `align_board_roll = 0` and only then `d_roll = 30` (real SITL output in the lab: `align_boar[d_roll]` matched). A check like `if "d_roll = " in out` will accidentally fire on the wrong line in such output, and naive parsing of “the first line with ` = `” will return 0 instead of 30 — that is how a false `FAIL` appeared in the first version of the lab script. Parse the reply with a regular expression anchored at the start of the line: `^d_roll = (.*)$` in multiline mode. `get` also prints the profile line (`profile 0`) and `Default value:` for changed values — those lines are not the value either.

### Pitfall 5: batch mode
`batch start` … `batch end` is a paste mode: commands are executed one at a time, but if at least one produced an error, `batch end` prints `###ERROR IN batch: ERRORS WERE DETECTED - PLEASE REVIEW BEFORE CONTINUING###`, and a `save` inside such a batch refuses: `###ERROR IN save: PLEASE FIX ERRORS THEN 'SAVE'###`. This protects against a half-applied config, but only once: both `batch end` and the refused `save` close the batch (`resetCommandBatch()`), so the next `save` will silently save everything that made it into RAM. A script must collect `###ERROR…###` errors after every command and, on any error, not send `save` but reboot the board without saving. A nuance: `defaults nosave` inside a batch clears the error flag but not the batch itself (`cli.c:4296` in 4.5.3, `:4374` in 2025.12). The output of `diff all` itself starts with `batch start` and `defaults nosave` — pasting a `diff all` first resets everything to defaults.

### Pitfall 6: a diff does not carry over between versions
Parameter names and meanings change between firmware versions: `debug_mode` values are renamed, the syntax of the `serial` command changes, the meaning of the D-term PID parameters changes. You cannot paste a `diff all` from 4.5 into 2025.12 (or the other way around) line by line: the table of differences is in the module “Introduction to Betaflight”, section “The 4.5.3 → 2025.12 transition”. Carry settings between versions only deliberately, section by section, re-reading the result.

What happens in practice — from the lab. The 4.5.3 `diff all` with `d_roll = 30` and `d_min_roll = 20`, pasted into 2025.12.5 as is, gave a single error, `INVALID NAME: d_min_roll = 20`, and the batch was not saved — that is the good outcome. The bad one is “fixing” it by renaming: with `d_roll = 30`, the firmware zeroed `d_max_roll = 20` on save, and `d_roll = 30`, accepted with no errors, means the base D in 2025.12, not the peak (defaults: 4.5.3 — D 40 and `d_min` 30; 2025.12 — D 30 and `d_max` 40; `flight/pid.h`). “No errors” does not mean “the same tune”.

{{lesson:bf-intro|The full table of parameter renames and changes of meaning for 4.5.3 → 2025.12 is there.}}

### Why a diff and not a dump
`diff all` contains only the differences from the defaults — it can be read by eye and kept in git. `dump` is everything, and on a firmware update it drags the old defaults along as explicit values.

The output format (`cli.c`, `printConfig`): a `# version` line and the version line with the build date, `batch start`, `defaults nosave`, `mcu_id`, `signature` (for `diff all`), `# name: …`, the `# feature` and `# master` blocks with `set …`, then `profile 0…3` and `rateprofile 0…3` with their own `set` lines, a return to the active profiles and `save` at the end. There is no `batch end` line after `save`: the firmware clears the batch flag since the save is already in the output (this is visible in the lab output). A trap for a script that reads the output: the comment lines `\r\n# version`, `\r\n# master` start exactly like the prompt. If a chunk of data happens to end on `\r\n# `, a naive “read until the prompt” will cut the backup off in the middle. A reliable end marker is the prompt at the end of the buffer followed by 0.3 s of silence (a course guideline; ample for USB and TCP).

| Command | 4.5.3 | 2025.12.5 | What it returns / does |
|---|---|---|---|
| `#` (byte) | enters the CLI | enters the CLI | after 100 ms of silence; not on an armed aircraft |
| `0x02` … `0x03` | no (4.5.5 has it) | one session with no echo and no reboot | command output, a 2 s window; end with `0x03` |
| `get <substring>` | yes | yes | all substring matches + range/default |
| `set <name> = <v>` | yes | yes | `<name> set to <v>` or `###ERROR IN set: INVALID NAME/VALUE###` |
| `batch start` / `batch end` | yes | yes | on an error in the batch, `save` refuses |
| `diff all` | yes | yes | `batch start`, `defaults nosave`, …, `save` |
| `save` | save + reboot | save + reboot | `# saving`; before the write — `validateAndFixConfig` |
| `save noreboot` | the argument is ignored: reboot | no reboot | 4.5.5 has it too |
| `exit` | reboot | reboot | `unsaved changes lost` |
| `exit noreboot` | the argument is ignored: reboot | no reboot | the `CLI` arming block stays until reboot |

### A minimal `diff all` download script (pyserial)
```python
import serial, time, sys, glob, re

def cli(port, cmds, timeout=3.0):
    """Open CLI, run commands, return full text. Do not send 'exit' (reboots on 4.5.3)."""
    with serial.Serial(port, 115200, timeout=0.2) as s:
        s.write(b"#\n"); time.sleep(0.5); s.read(4096)   # "#\n": safe if the FC is already in CLI
        out = ""
        for c in cmds:
            s.write((c + "\n").encode()); t0 = time.time(); buf = ""
            while time.time() - t0 < timeout:
                chunk = s.read(4096).decode(errors="replace")
                if chunk: buf += chunk; t0 = time.time()
                elif buf.endswith("\r\n# "): break   # prompt AND a quiet read: end of output
            out += buf
        return out

ports = glob.glob("/dev/ttyACM*")                              # Linux; Windows: COM*
for p in ports:
    name = cli(p, ["get craft_name"])
    if re.search(r"^craft_name = viking7\r?$", name, re.M):   # anchored: not viking70
        text = cli(p, ["version", "diff all"])
        open("viking7/betaflight/diff-all.txt", "w").write(text)
        break
else:
    sys.exit("craft not found")
```
Normalization before a commit: remove the date/time lines from `version` and the `# ` echo, sort the blocks — otherwise `git diff` is noisy (the “CI” module). This short version enters the CLI on every port just for the name — tolerable for a one-off backup (the port is closed without `exit`, and the board stays in the CLI with the arming block until it is power-cycled); for a fleet, find the board by `MSP_NAME`, as in the practice.

### What is worth automating and what is not
Worth it: a `diff all` backup before every flying day; checking invariants (failsafe, poles, bidir) on the downloaded config; bulk changes of `craft_name`/the VTX table across a fleet; downloading logs through `msc`. Not worth it: bulk “PID rollout” onto different aircraft (different mechanics), any changes without re-reading with `get` after `save`.

{{diagram:bf-cli-session|A CLI session over serial: wait for the prompt, re-read values after set, find the port again after save.}}

### Place in the system

- **Receives:** the text CLI over USB and the commands `diff all`, `get`, `set`, `save` (`bf-cli`); MSP for identifying a board; the table of renames between 4.5 and 2025.12 (`bf-intro`); a unique `craft_name` for every aircraft.
- **Provides:** a `diff all` before the flying day — to git and to the invariant check in CI (`eng-ci-configs`); the actual values after a reboot for failsafe, the pole count and bidir (`bf-failsafe`, `bf-rpm-filter`).
- **If you get it wrong here:** you did not re-read with `get` after `save` → the firmware silently zeroed `d_max` or put failsafe back to `DROP` → the aircraft does not have what your records say; it surfaces in flight as a different tune (`bf-pid`) or as a drop instead of a return (`bf-failsafe`). You pasted a `diff all` from 4.5 into 2025.12 line by line and “fixed” the names → `d_roll` is accepted, but it now means the base D, not the peak → a different tune; the table is in `bf-intro`.

## practice
The main path needs no board: Betaflight 4.5.3 and 2025.12.5 build under Linux as SITL (a program that runs the real firmware code), and its UART1 is available as TCP port 5761. pyserial opens it with the same function as a USB port (`serial.serial_for_url("socket://127.0.0.1:5761")`), so the script differs from the “hardware” one by a single line. In SITL `save` calls `systemReset()`, which calls `exit(0)` (`target/SITL/sitl.c`): a reboot looks like the process exiting, and the script restarts it in the same folder, where `eeprom.bin` lives — exactly as a board boots from its flash.

### Step 1. Build SITL for the two versions
The sources are the tags `4.5.3` and `2025.12.5` of the betaflight/betaflight repository. The Makefile requires `arm-none-eabi-gcc` even for SITL (`mk/tools.mk:266`); the official way is `make arm_sdk_install`. For SITL the cross-compiler is not actually used, so it is enough to provide the system gcc under the expected names; 2025.12 also requires the `src/config` folder (`make configs` fills it with a clone of betaflight/config; for SITL an empty `src/config/configs` is enough — derived from `mk/config.mk`). The builds took 12 s and 8 s.

```bash
mkdir -p fakesdk/bin && for t in gcc g++ gdb objcopy objdump readelf size; do
  ln -sf /usr/bin/$t fakesdk/bin/arm-none-eabi-$t; done
(cd bf453 && make TARGET=SITL ARM_SDK_DIR=$PWD/../fakesdk -j8)      # -> obj/main/betaflight_SITL.elf
(cd bf2025 && mkdir -p src/config/configs && make SITL ARM_SDK_DIR=$PWD/../fakesdk -j8)
                                                                     # -> obj/betaflight_2025.12.5_SITL
```

### Step 2. The lab script
The script does six steps: (1) identification over MSP; (2) a batch of `set` and `save` on 4.5.3; (3) a search by `MSP_NAME` after the “reboot”, re-reading every key and downloading `diff all`; (4) pasting this `diff all` into 2025.12.5 as is; (5) a “port” by renaming `d_min_roll → d_max_roll`, `save noreboot`, a re-read, a non-interactive STX/ETX request; (6) a comparison of the two `diff all` outputs by key. To run it: `python3 -I bf_cli_lab.py <SITL 4.5.3> <SITL 2025.12.5> work`; port 5761 must be free — the script checks this itself, otherwise someone else's SITL would answer (that is what happened on the first run: a leftover 2025.12 process answered instead of the fresh 4.5.3).

```python
"""Betaflight CLI + MSP automation lab on SITL (4.5.3 and 2025.12.5).

The same functions work on a real FC over USB: replace open_port() with
serial.Serial("/dev/ttyACM0", 115200, timeout=0.2) (Windows: "COM8").
Usage: python3 bf_cli_lab.py <sitl-4.5.3> <sitl-2025.12.5> <workdir>
"""
import os, re, socket, subprocess, sys, time
import serial  # pyserial 3.5

PROMPT = b"\r\n# "
ERR = re.compile(r"###ERROR IN (\w+): (.*?)###")


def open_port(url="socket://127.0.0.1:5761", tries=50):
    for _ in range(tries):               # SITL needs ~0.5 s to bind its TCP "UART1"
        try:
            return serial.serial_for_url(url, timeout=0.2)
        except (serial.SerialException, OSError):
            time.sleep(0.1)
    raise RuntimeError("port did not open")


def msp(port, cmd, payload=b""):
    """MSP v1: '$M<' size cmd payload xor; reply '$M>' (or '$M!' = unsupported)."""
    body = bytes([len(payload), cmd]) + payload
    ck = 0
    for b in body:
        ck ^= b
    port.reset_input_buffer()
    port.write(b"$M<" + body + bytes([ck]))
    buf, t_end = b"", time.time() + 1.0
    while time.time() < t_end:
        buf += port.read(256)
        i = buf.find(b"$M")
        if i >= 0 and len(buf) >= i + 6 and len(buf) >= i + 6 + buf[i + 3]:
            n = buf[i + 3]
            if buf[i + 2:i + 3] != b">":
                raise IOError(f"MSP {cmd}: error reply")
            ck = 0
            for b in buf[i + 3:i + 5 + n]:
                ck ^= b
            if ck != buf[i + 5 + n]:
                raise IOError(f"MSP {cmd}: bad checksum")
            return buf[i + 5:i + 5 + n]
    raise TimeoutError(f"MSP {cmd}: no reply")


def identify(port):
    api = msp(port, 1)            # MSP_API_VERSION: protocol, major, minor
    variant = msp(port, 2)        # MSP_FC_VARIANT: 'BTFL'
    ver = msp(port, 3)            # MSP_FC_VERSION: 4.5.3 or 25.12.5 (calver: year-2000)
    name = msp(port, 10)          # MSP_NAME: craft_name
    uid = msp(port, 160)          # MSP_UID: 3 x uint32 MCU unique id
    return {"api": f"{api[1]}.{api[2]}", "variant": variant.decode(),
            "version": ".".join(str(x) for x in ver[:3]),
            "name": name.decode(errors="replace"), "uid": uid.hex()}


def read_prompt(port, timeout=8.0, quiet=0.3):
    """Read until the CLI prompt AND then `quiet` s of silence: comment lines of
    `diff` ('\\r\\n# version') look exactly like the prompt at a chunk boundary."""
    buf, t_end = b"", time.time() + timeout
    while time.time() < t_end:
        chunk = port.read(4096)
        buf += chunk
        if buf.endswith(PROMPT) and not chunk:
            t_quiet = time.time() + quiet
            while time.time() < t_quiet and not (chunk := port.read(4096)):
                pass
            if not chunk:
                return buf.decode(errors="replace")
            buf += chunk
    raise TimeoutError(f"no prompt after {len(buf)} bytes")


def cli_enter(port):
    port.write(b"#")              # non-MSP '#', handled after 100 ms idle; ignored while ARMED
    return read_prompt(port)


def cli(port, cmd, timeout=8.0):
    port.write(cmd.encode() + b"\n")
    out = read_prompt(port, timeout)
    lines = out.replace("\r", "").split("\n")[1:-1]  # drop echo and prompt
    return "\n".join(lines).strip("\n"), ERR.findall(out)


def get(port, key):
    """`get` is a substring search: `get d_roll` also prints align_board_roll."""
    out, _ = cli(port, f"get {key}")
    return re.search(rf"^{re.escape(key)} = (.*)$", out, re.M)[1].strip()


def start_sitl(binary, workdir):
    with socket.socket() as s:            # a leftover SITL would answer instead of ours
        if s.connect_ex(("127.0.0.1", 5761)) == 0:
            sys.exit("port 5761 busy: another SITL is running")
    os.makedirs(workdir, exist_ok=True)
    PROCS.append(subprocess.Popen([binary], cwd=workdir, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL))
    return PROCS[-1]


def wait_reboot(port, proc):
    """On SITL `save` = systemReset() = exit(0); on a real FC the USB device re-enumerates."""
    try:
        while port.read(4096):
            pass
    except (serial.SerialException, OSError):
        pass
    port.close()
    return proc.wait(timeout=5)


def parse_diff(text):
    """`diff all` -> {(context, key): value}; context = master / profile N / rateprofile N."""
    ctx, out = "master", {}
    for line in text.replace("\r", "").split("\n"):
        line = line.strip()
        if m := re.match(r"(profile|rateprofile) (\d)$", line):
            ctx = f"{m[1]} {m[2]}"
        elif m := re.match(r"set (\S+) = (.*)$", line):
            out[(ctx, m[1])] = m[2]
        elif line and not line.startswith("#") and line.split()[0] in (
                "feature", "serial", "aux", "resource", "beacon", "map", "led", "vtxtable"):
            out[(ctx, line)] = "line"
    return out


CHANGES = {"craft_name": "viking2", "failsafe_delay": "10",
           "failsafe_procedure": "GPS-RESCUE", "d_roll": "30", "d_min_roll": "20"}

PROCS = []


def run(bin453, bin2025, work):
    w453 = os.path.join(work, "fc453")
    print("== 1. MSP identify (no CLI, no reboot)")
    proc = start_sitl(bin453, w453)
    p = open_port()
    print("  ", identify(p))

    print("== 2. CLI: batch of set, then save")
    cli_enter(p)
    print("  ", cli(p, "batch start")[0])
    for k, v in CHANGES.items():
        print("  ", cli(p, f"set {k} = {v}")[0].splitlines()[0])
    print("  ", cli(p, "batch end")[0])
    p.write(b"save\n")
    print("   save -> FC reboots, SITL exit code", wait_reboot(p, proc))

    print("== 3. after reboot: find by MSP_NAME, re-read every key with get")
    proc = start_sitl(bin453, w453)
    p = open_port()
    print("   MSP_NAME =", identify(p)["name"])
    cli_enter(p)
    print("   raw `get d_roll`:", cli(p, "get d_roll")[0].replace("\n", " | "))
    for k, v in CHANGES.items():
        got = get(p, k)
        print(f"   {'OK  ' if got == v else 'FAIL'} {k:20s} wrote {v:10s} read {got}")
    diff453, _ = cli(p, "diff all", timeout=15)
    open(os.path.join(work, "viking2_4.5.3_diff.txt"), "w").write(diff453 + "\n")
    print(f"   diff all: {len(diff453.splitlines())} lines saved")
    p.close(); proc.terminate(); proc.wait()

    print("== 4. paste the 4.5.3 diff into 2025.12.5 as is")
    proc = start_sitl(bin2025, os.path.join(work, "fc2025"))
    p = open_port()
    print("  ", identify(p))
    cli_enter(p)
    errors = []
    for line in diff453.splitlines():
        if line.strip() and not line.startswith("#") and line.strip() != "save":
            errors += cli(p, line)[1]
    for e in errors:
        print("   ERROR", e)
    print("  ", cli(p, "save noreboot")[0].replace("\n", " | "))

    print("== 5. 'port' by renaming d_min_roll -> d_max_roll, save noreboot")
    cli(p, "defaults nosave")
    ported = {("d_max_roll" if k == "d_min_roll" else k): v for k, v in CHANGES.items()}
    for k, v in ported.items():
        cli(p, f"set {k} = {v}")
    print("  ", cli(p, "save noreboot")[0])
    for k, v in ported.items():
        got = get(p, k)
        print(f"   {'OK  ' if got == v else 'FAIL'} {k:20s} wrote {v:10s} read {got}")
    diff2025, _ = cli(p, "diff all", timeout=15)
    open(os.path.join(work, "viking2_2025.12.5_diff.txt"), "w").write(diff2025 + "\n")
    p.write(b"exit noreboot\n"); time.sleep(1.0)
    print("  ", p.read(4096).decode().strip().replace("\r\n", " | "),
          "| SITL alive:", proc.poll() is None, "| MSP_NAME:", identify(p)["name"])
    p.write(b"\x02get failsafe_delay\n\x03"); time.sleep(0.5)  # 2025.12: one-shot CLI, STX..ETX
    print("   STX/ETX:", p.read(4096))
    p.close(); proc.terminate(); proc.wait()

    print("== 6. semantic diff 4.5.3 -> 2025.12.5 (by key, not by text line)")
    a, b = parse_diff(diff453), parse_diff(diff2025)
    for key in sorted(set(a) | set(b)):
        if a.get(key) != b.get(key):
            print(f"   {key[0]:10s} {key[1]:20s} {a.get(key, '-'):>10s} -> {b.get(key, '-')}")


if __name__ == "__main__":
    try:
        run(*sys.argv[1:4])
    finally:
        for pr in PROCS:
            if pr.poll() is None:
                pr.terminate()
```

```text
== 1. MSP identify (no CLI, no reboot)
   {'api': '1.46', 'variant': 'BTFL', 'version': '4.5.3', 'name': '', 'uid': '000000000100000002000000'}
== 2. CLI: batch of set, then save
   Command batch started
   craft_name set to viking2
   failsafe_delay set to 10
   failsafe_procedure set to GPS-RESCUE
   d_roll set to 30
   d_min_roll set to 20
   Command batch ended
   save -> FC reboots, SITL exit code 0
== 3. after reboot: find by MSP_NAME, re-read every key with get
   MSP_NAME = viking2
   raw `get d_roll`: align_board_roll = 0 | Allowed range: -180 - 360 |  | d_roll = 30 | profile 0 | Allowed range: 0 - 250 | Default value: 40
   OK   craft_name           wrote viking2    read viking2
   OK   failsafe_delay       wrote 10         read 10
   OK   failsafe_procedure   wrote GPS-RESCUE read GPS-RESCUE
   OK   d_roll               wrote 30         read 30
   OK   d_min_roll           wrote 20         read 20
   diff all: 51 lines saved
== 4. paste the 4.5.3 diff into 2025.12.5 as is
   {'api': '1.47', 'variant': 'BTFL', 'version': '25.12.5', 'name': '', 'uid': '000000000100000002000000'}
   ERROR ('set', 'INVALID NAME: d_min_roll = 20')
   ###ERROR IN save: ERRORS WERE DETECTED - PLEASE REVIEW BEFORE CONTINUING### | ###ERROR IN save: PLEASE FIX ERRORS THEN 'SAVE'###
== 5. 'port' by renaming d_min_roll -> d_max_roll, save noreboot
   # saving
   OK   craft_name           wrote viking2    read viking2
   OK   failsafe_delay       wrote 10         read 10
   FAIL failsafe_procedure   wrote GPS-RESCUE read DROP
   OK   d_roll               wrote 30         read 30
   FAIL d_max_roll           wrote 20         read 0
   exit noreboot |  | # leaving CLI mode, no reboot | SITL alive: True | MSP_NAME: viking2
   STX/ETX: b'\x02failsafe_delay = 10\r\nAllowed range: 1 - 200\r\nDefault value: 15\r\n\x03'
== 6. semantic diff 4.5.3 -> 2025.12.5 (by key, not by text line)
   master     failsafe_procedure   GPS-RESCUE -> -
   profile 0  d_max_roll                    - -> 0
   profile 0  d_min_roll                   20 -> -
   profile 0  d_roll                       30 -> -
```

### Step 3. What each line of the output proves
- Step 1 of the output: identification went over MSP, and the board did not enter the CLI. Version 4.5.3 came back as `4.5.3`, 2025.12.5 — as `25.12.5`: a version check on the first byte would have broken.
- Steps 2–3: all five values on 4.5.3 survived `save` and the boot — `OK`. The `raw get d_roll` line shows why the reply has to be parsed with an anchor: `align_board_roll = 0` came first.
- Step 4: the only error is `d_min_roll`, and because of it the batch was not saved at all; this is the correct behavior, not a failure.
- Step 5: after the “port” by renaming there are two `FAIL` lines: `failsafe_procedure` became `DROP` (SITL has no GPS Rescue, the value is outside the list — the 2025.12 check), and `d_max_roll` became 0 (less than `d_roll`). Not a single command printed an error — these are the silent fixes. `exit noreboot` left SITL alive, and MSP answers again.
- Step 6: a line-by-line `git diff` of the two files would also show the change of the version line with the build date; the comparison by key shows the four real changes of meaning, including the disappearance of `d_roll = 30` from the 2025.12 diff — 30 is already the default there.

{{diagram:bf-cli-apply-verify|The edit script: a backup, set and save, finding the port again after the reboot, get for every key and a second backup — git diff must show exactly the CHANGES lines.}}

### Step 4. Keep configs as code
1. A folder per drone, with `configs/` and `logs/` inside.
2. The file name: `<drone>_<board>_<YYYY-MM-DD>_diff.txt` — sorting by name = sorting by date.
3. Before changes — a backup, after them — a new `diff all` (`viking2_after_diff.txt`, with the same command as the backup); compare them with an ordinary `git diff`. Use `diff all`, not plain `diff`: a plain `diff` saves only the current PID and rate profile, and the other three pairs of profiles will not make it into the backup.
4. Keep the `# Betaflight / … <build date>` line before committing, but compare the files by key (`parse_diff` from the script): the build date changes on every reflash and looks like a config change in a line-by-line diff.

### Moving to real hardware
Propellers are off for the whole time; a battery is not needed — USB powers the FC, and ESCs without main power do not spin the motors. Connect two boards over USB and close the Configurator (it holds the port and floods it with MSP traffic). On a real machine the ports are `/dev/ttyACM*` or `COM*`; the search by `MSP_NAME` is the same `identify()` from the lab script, only over the port list from `list_ports.comports()`. Verified on SITL with one dead and one live port:

```python
"""Find an FC by craft_name over MSP: no CLI, no reboot, no arming lock. Usage: find_craft.py NAME [port ...]"""
import sys
import serial
from serial.tools import list_ports
from bf_cli_lab import identify   # msp() + MSP_API_VERSION/FC_VARIANT/FC_VERSION/NAME/UID from the lab


def find_craft(name, ports=None):
    ports = ports or [p.device for p in list_ports.comports()]   # /dev/ttyACM*, COM*
    for dev in ports:
        try:
            with serial.serial_for_url(dev, baudrate=115200, timeout=0.2) as p:
                info = identify(p)
        except (serial.SerialException, OSError, TimeoutError) as e:
            print(f"  {dev}: no MSP ({type(e).__name__})")
            continue
        print(f"  {dev}: {info['variant']} {info['version']} name={info['name']!r} uid={info['uid']}")
        if info["name"] == name:
            return dev, info
    raise RuntimeError(f"FC {name!r} not found")


if __name__ == "__main__":
    print(find_craft(sys.argv[1], sys.argv[2:] or None))
# python3 find_craft.py viking2 socket://127.0.0.1:5768 socket://127.0.0.1:5761   (SITL 2025.12.5 running)
#   socket://127.0.0.1:5768: no MSP (SerialException)
#   socket://127.0.0.1:5761: BTFL 25.12.5 name='viking2' uid=000000000100000002000000
# ('socket://127.0.0.1:5761', {'api': '1.47', 'variant': 'BTFL', 'version': '25.12.5', 'name': 'viking2', 'uid': '000000000100000002000000'})
```

Then on each board: a `diff all` backup, the batch of `set` commands from `CHANGES`, `save`, finding the port again (on Windows the COM number may change; wait up to 10 s in a loop — a course guideline), re-reading every key. Abort: the board was not found within 10 s after `save` — do not repeat the write, reconnect USB and start from the backup; any `###ERROR` line in the batch — do not send `save`. Criteria on hardware: both boards are found by name without entering the CLI; after `save` every key from `CHANGES` is re-read with status `OK` or an explained `FAIL` (a firmware fix that you can name from the table above); `diff all` before and after differ in exactly the lines from `CHANGES` and nothing else; the run on the second board goes without editing the code — only `craft_name` in the arguments changes.

Self-check: the lab is complete when (SITL) both versions are built and answer over MSP: 4.5.3 — API 1.46 and version `4.5.3`, 2025.12.5 — API 1.47 and version `25.12.5`; after `save` on 4.5.3 the process exits with code 0, and after the restart all five keys are `OK`; pasting the 4.5.3 `diff all` into 2025.12.5 gives exactly one error, `INVALID NAME: d_min_roll = 20`, and a refused `save`; after the rename there are exactly two `FAIL` lines — `failsafe_procedure → DROP` and `d_max_roll → 0`; the STX/ETX request returns `failsafe_delay = 10` framed by the bytes `\x02` and `\x03`; the comparison by key prints 4 lines. On hardware — the criteria from the section “Moving to real hardware”.

**Reference for self-check.** A correct output matches the one above except for the build date in the version line and the commit hash. Typical wrong ones: (1) in step 3 `FAIL d_roll … read 0` — the `get` reply was parsed without an anchor, and the `align_board_roll` line matched; (2) step 1 immediately shows `25.12.5` and `name: viking2` — a 2025.12 SITL left over from the previous run answered on port 5761, and your own could not bind the port; (3) the script hangs after `exit noreboot` — there is no prompt after leaving the CLI, so you have to read with a timeout, not until `# `; (4) there is not a single `FAIL` on 4.5.3, and you expected the failsafe fix — 4.5.3 has no “value outside the list → DROP” check, and the “GPS-RESCUE without feature GPS” rule is not built into SITL (SITL has no GPS); on a flight board with a GPS build it will trigger.

## diagnostics
- **Symptom:** the script “lost” the drone after save
  - Possible cause: after the reboot the COM port got a different number.
  - What to do: find the port again by `craft_name` through `MSP_NAME`, not by number.
- **Symptom:** a written value is different after the reboot
  - Possible cause: Betaflight corrected an incompatible combination in `validateAndFixConfig` (`d_max` < D, GPS-RESCUE without GPS, bidir without DShot).
  - What to do: re-read the related parameters, check them against the table of fixes above and against the board and firmware documentation.
- **Symptom:** after pasting a diff some lines gave `INVALID NAME` errors
  - Possible cause: the diff is from another firmware version.
  - What to do: carry settings over section by section, checking the parameter names in the `help` of the current version.
  - Consequences: if a batch was opened with `batch start`, the first `save` will refuse and nothing will be saved (the changes stay in RAM until reboot; a repeated `save` will save them); without a batch everything is applied except the failing lines.
- **Symptom:** two drones respond to the same `craft_name`
  - Possible cause: identical names (a cloned config).
  - What to do: rename right away, `set craft_name = ...` + `save`; keep `MSP_UID` next to the name.
- **Symptom:** `save noreboot` rebooted the board
  - Possible cause: firmware 4.5.3 or older: the argument is not read.
  - What to do: determine the version over MSP before writing, and on 4.5.3 always wait for a reboot.
- **Symptom:** after `exit noreboot` the aircraft does not arm
  - Possible cause: 2025.12 keeps the `CLI` arming disable flag until reboot.
  - What you see in the log: `status` → `Arming disable flags: CLI`.
  - What to do: reboot the board before flying; use MSP or STX/ETX for reading values.
- **Symptom:** a `diff all` backup is cut off in the middle
  - Possible cause: reading “until `# `” fired on the comment line `# master` at a chunk boundary; or a fixed timeout is shorter than the output time on a large F7/H7 config.
  - What to do: the end of the output is the prompt plus 0.3 s of silence; check that the file ends with the `save` line.

## references
- Betaflight — source code: src/main/cli/cli.c, msp/msp_serial.c, msp/msp.c, config/config.c (tags 4.5.3, 2025.12.5) | https://github.com/betaflight/betaflight | primary | A
- Betaflight CLI — Documentation | https://betaflight.com/docs/wiki/guides/current/Cli | primary | A
- pySerial — Documentation (serial_for_url, socket://) | https://pyserial.readthedocs.io/en/latest/ | primary | A

## checklist
- Every drone has a unique `craft_name`, with `MSP_UID` recorded next to it
- The script finds the port by `MSP_NAME`, not by COM number and not by entering the CLI
- A `diff all` with the date in the file name is saved before changes
- After `save` the script finds the port again and re-reads the values with `get` using the anchor `^name = `
- `save noreboot` on 4.5.3 is treated as a reboot
- `###ERROR` errors in a batch stop `save`
- A diff between different firmware versions is not pasted line by line
