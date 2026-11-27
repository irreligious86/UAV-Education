---
id: px4-console-params
title: "PX4 console and parameters: nsh/pxh, param, listener, status, backups"
level: L2
readingTime: 55 min
firmware: PX4 1.18 (checked against the v1.17.0 source; v1.18.0 differences in parameter loading, resets and logging noted)
status: published
added: 2026-11-22
tags:
  - PX4
  - console
  - parameters
  - nsh
  - backup
  - troubleshooting
related:
  - px4-intro
  - px4-setup-scratch
  - px4-architecture
  - px4-hardware-peripherals
  - px4-outputs-servos
  - px4-safety-return
  - px4-ros2
  - bf-cli
  - inav-cli-backup
  - eng-ci-configs
next:
  - px4-hardware-peripherals
source: content/px4/px4-console-params.md
source_hash: 8415e35e81da
---

## summary
The PX4 console and parameter system, from the 1.17.0 source: how to get into `nsh` on a flight controller and `pxh` in SITL and what each one lacks, every `param` subcommand with its exact semantics, which layers make up a parameter value and which of them reach storage, how the four kinds of reset and the three kinds of backup differ, why a parameter "disappears" from QGC, which commands to use to inspect sensors, modules, CPU load and the log, and in what order `rcS` applies `config.txt`, `extras.txt` and `rc.txt` from the SD card. After this module you can look at a `param show -c` listing and say what will survive a reset and a reboot, pick the command for a question, and name the output line that confirms the hypothesis. The lab needs no hardware and no simulator: analyzing a training parameter list, four troubleshooting situations, a pair of files for the SD card, and finding the dangerous steps in a procedure; the answers are checked against the reference on the page.

## theory
### What is in the module and how to read it
The module covers three topics, best read in this order. First the console: how to get into it and which commands exist on a flight controller and which only in the simulator. Then parameters: value layers, storage, the `param` command, resets, reboots and backups; this is where most of the non-obvious behavior lives. Last come the inspection commands, the startup scripts and the "which tool for which question" table. Port, output and failsafe assignment is not repeated here: that is in px4-hardware-peripherals, px4-outputs-servos and px4-safety-return.

### Getting into the console
A flight controller runs the NuttX shell, `nsh>`. SITL has no NuttX; it uses PX4's own shell, `pxh>`. The PX4 modules are the same in both; the system commands differ.

| Entry | How to open it | What you see | When to use it |
|---|---|---|---|
| QGC MAVLink Console | Analyze Tools → MAVLink Console, over USB or telemetry | only the output of the command you ran | by default: no soldering needed |
| `Tools/mavlink_shell.py` | `./Tools/mavlink_shell.py /dev/ttyACM0`, QGC closed | the same, in a terminal | scripts, recording a session to a file |
| System console (debug UART) | a 3.3 V USB–UART adapter on the debug port, terminal at 57600 8N1 | all boot output and the output of every module | the board does not boot, MAVLink did not come up |
| nsh over USB | `SYS_USB_AUTO` = 1, a terminal, press Enter three times | a regular nsh | no MAVLink client at hand |
| `pxh>` in SITL | the terminal running `make px4_sitl …` | all output of the process | the simulator |

Rule of thumb: start with the MAVLink Console; you need the debug UART only where MAVLink is not running yet, that is, for hangs during boot and errors in the startup scripts.

How it works. The MAVLink shell travels in `SERIAL_CONTROL` messages (id 126) with the device `SERIAL_CONTROL_DEV_SHELL` = 10, 70 bytes per message; it is not a `MAV_CMD`. One shell per MAVLink instance. `mavlink_shell.py` takes a port (`device[,baud]`, `IP:port` for UDP, `tcp:IP:port`; with no argument it looks for a serial port itself) and `--baudrate` / `-b`, 57600 by default; it needs `pymavlink` and `pyserial`.

`SYS_USB_AUTO`: 0 Disabled, 1 Auto-detect (three carriage returns in a row start `nshterm` on `/dev/ttyACM0`, the start of a u-blox packet gives GPS passthrough), 2 MAVLink only (the default). The parameter needs a reboot. The fmu-v6x system console is USART3 at 57600 baud (`nuttx-config/nsh/defconfig`).

Messages from other modules do not reach the MAVLink shell. Read them with `dmesg`, a 4 KB ring buffer of console output: old lines get pushed out, so look at the boot output right after boot. `dmesg -f &` keeps the output running in the background.

### nsh and pxh: what is there and what is not
The board build sets the command list, in `boards/<vendor>/<board>/default.px4board`. A command missing from the build answers `command not found`.

| Command | px4/fmu-v6x | SITL (px4/sitl) |
|---|---|---|
| `param`, `listener`, `uorb`, `work_queue`, `perf`, `ver` | yes | yes |
| `actuator_test`, `tune_control`, `led_control`, `bsondump` | yes | yes |
| `top`, `dmesg`, `reboot` | yes | no |
| `i2cdetect`, `nshterm`, `hardfault_log`, `mtd` | yes | no |
| `ls`, `cat`, `free`, `ps`, `df`, `cp`, `rm` (nsh built-ins) | yes | no |
| `sd_bench` | no (fmu-v6c has it) | yes |
| `failure` | no | yes |
| `shutdown`, `list_tasks`, `list_files` | no | yes |

This holds for all three releases 1.15–1.17 (and for the v1.18.0 board files). Consequences: `top` does not work in SITL, so check the load there with `listener cpuload` and `work_queue status`; the stock flight controller build has no `failure` (px4-safety-return); testing the card with `sd_bench` on a Pixhawk 6X needs a custom build.

### Where a parameter value comes from
A parameter has three layers (`src/lib/parameters/parameters.cpp`), and a module gets the value of the topmost non-empty one:

1. **Firmware default**: the number from `PARAM_DEFINE_*` or `module.yaml`, compiled in.
2. **Startup default**: what the board scripts (`rc.board_defaults`), the airframe and `config.txt` wrote with `param set-default`. It lives in RAM and is rebuilt on every boot.
3. **Saved value**: everything written with `param set`, from QGC, by a calibration or by a driver itself.

{{diagram:px4-console-param-layers|The parameter value is the topmost non-empty of three layers; only what differs from the startup default goes to storage, so a value equal to the airframe default silently changes after a firmware update.}}

Example: the firmware default of `RTL_RETURN_ALT` is 60 m, `rc.mc_defaults` sets 30 m for a multicopter, and the operator can write their own.

The main storage rule: saving writes only third-layer values that are **not equal to the startup default** (`param_export_internal`). If you set `RTL_RETURN_ALT` = 30 on a quadcopter, the file does not contain it. Hence the px4-intro rule: after a firmware update everything that matched a default gets the new default.

### Storage and autosave
The storage format is BSON: a sequence of "type, name, value" records, integers as int32, floats as double. Where it goes depends on the board:

| Board | Main storage | Backup |
|---|---|---|
| fmu-v6x, fmu-v6c (FRAM) | `/fs/mtd_params` | `/fs/microsd/parameters_backup.bson` |
| boards with `CONFIG_BOARD_PARAM_FILE="/fs/microsd/params"` (for example Matek H743-Slim) | `/fs/microsd/params` | `/fs/microsd/parameters_backup.bson` |
| boards with `FLASH_BASED_PARAMS` (the Kakute H7 family, SP Racing H7 Extreme) | the MCU's internal flash | the same file, if there is an SD card |

In normal operation there is no "save" step: any change through `param_set()` schedules an autosave (`autosave.cpp`). The delay is 0.3 s, but no more than one save per 2 s: `delay = max(0.3, 2 − t)`, where t is the time since the last save. On boards with parameters in flash, writing is postponed while the vehicle is armed: erasing flash can stall the processor for hundreds of milliseconds. Every save is read back and verified, then the backup is written.

To save without the delay: `param save` with no arguments, or the MAVLink command `MAV_CMD_PREFLIGHT_STORAGE`. Do not cut power during the first two seconds after changing a parameter.

At boot `rcS` imports the main file; if it cannot be read, the error tune plays, the corrupt file is copied to `/fs/microsd/param_import_fail.bson` (if an SD card is present) and the parameters are taken from the backup. On boards with a `/fs/mtd_caldata` area, the factory calibration `CAL_ACC*`, `CAL_GYRO*`, `CAL_MAG*` is loaded from there first.

### The param command
All subcommands come from `src/systemcmds/param/param.cpp`; they are the same in 1.15–1.17.

| Command | What it does |
|---|---|
| `param show [filter]` | used parameters; a `*` in the filter only at the end, case-insensitive |
| `param show -a` | every parameter in the build, takes no filter |
| `param show -c [filter]` | everything in the third layer, including unused parameters |
| `param show -q <name>` | the value only, exact name, for scripts |
| `param show-for-airframe` | used third-layer parameters as `param set-default …` lines, with exceptions (below) |
| `param status` | counters, the storage and backup files, the time of the last autosave |
| `param set <name> <val> [fail]` | writes to the third layer; an unknown name prints an error but returns 0 unless `fail` is given |
| `param set-default [-s] <name> <val>` | changes the startup default; `-s` is silent about an unknown name |
| `param compare [-s] <name> <val…>` | returns 0 if the value equals one of those listed |
| `param greater [-s] <name> <val>` | returns 0 if the value is greater |
| `param touch <name…>` | marks the parameter as used |
| `param reset <name…>` | removes the third-layer entry of the listed parameters, `*` at the end allowed |
| `param reset_all [exclusions…]` | the same for all, except the exclusions |
| `param save [file]` | with no argument, to the main storage; with a file, a BSON export |
| `param load [file]` | clears the whole third layer, then imports |
| `param import [file]` | imports on top of what is there |
| `param select [file]`, `select-backup [file]` | change the main file or the backup file until reboot |
| `param find <name>` | the parameter index, or `Parameter … not found` |
| `param index <n>`, `index_used <n>` | the parameter by number among all or among the used ones |

A `param show` line looks like this: `x + MC_ROLLRATE_P [used_index,index] : 0.1800`. The first character `x` means the parameter is used. The second: `*` changed and not saved yet, `+` saved and different from the default, a space equal to the default. In 1.18.0 a third column follows: `l` marks a read-only parameter (`param.cpp`, v1.18.0). There is no `param dump` command: `bsondump <file>` prints a BSON file.

Three traps. `param set` does nothing if the value equals the current one. `param import` and `param load` mark the values as saved and do not trigger an autosave, so type `param save` after them, or the old storage comes back after a reboot. On a BSON import, old names are translated (`param_translation.cpp`: `SDLOG_MODE` = −1 → `SDLOG_BACKEND` = 0, `ASPD_FALLBACK_GW` → `ASPD_FALLBACK`) and unknown names are skipped with a warning; writes over MAVLink get no translation.

### Four resets
| Action | What remains | When to use it |
|---|---|---|
| `param reset <name>` | everything except the named one | return one parameter to the airframe default |
| console: `param reset_all` | nothing: `SYS_AUTOSTART`, calibrations and the radio go too | the board changes owner or vehicle type |
| QGC: Reset all to firmware's defaults | only `LND_FLIGHT_T_HI`, `LND_FLIGHT_T_LO`, `COM_FLIGHT_UUID` | the same, but keeping the flight time |
| QGC: Reset to vehicle's configuration defaults | `SYS_AUTOSTART`, `SYS_PARAM_VER`, `RC*`, `CAL_*`, `COM_FLTMODE*`, `LND_FLIGHT*`, `TC_*`, `COM_FLIGHT*` | a clean tune on the same vehicle without recalibrating |

The last option works through `SYS_AUTOCONFIG`: QGC writes a nonzero value to it, and at the next boot `rcS` runs `param reset_all` with this exclusion list; `SYS_AUTOCONFIG` itself is reset to 0 as well. A reboot is needed. The `RC*` exclusion covers every name starting with "RC", including `RC_MAP_*` and the receiver port. In 1.18.0 the list is shorter: `RC*` and `COM_FLTMODE*` are no longer excluded (`rcS`:259, v1.18.0), so the radio calibration and the flight mode slots are reset too.

After `param reset_all` the airframe defaults stay in RAM until the reboot. After it `SYS_AUTOSTART` = 0, no airframe is selected, `rcS` prints `No airframe file found` and plays the error tune. Check after any reset: `param show -c` and the `storage array` line in `param status`.

### Reboots and "missing" parameters
`reboot_required` is parameter metadata; the firmware does not check it. QGC shows it on the parameter card and reminds you to reboot; the console does not. A reboot is needed for parameters that a startup script or a module reads at start: ports (`*_CONFIG`, `SER_*_BAUD`), `SYS_AUTOSTART`, `SENS_EN_*`, `SENS_BOARD_ROT`, the output group protocol, `SDLOG_MODE`, `SDLOG_PROFILE`, `SYS_USB_AUTO`. Controller gains and failsafe thresholds take effect immediately.

QGC gets only the **used** parameters from the firmware, the ones some module or script has accessed at least once. That gives three reasons why a parameter is "missing":

| Reason | How to check | What to do |
|---|---|---|
| The module is not built for the board | `param find <name>` → `not found` | build the firmware: `make <target> boardconfig`, enable the driver |
| Another parameter gates it: the instance is not running | `param find` finds it, `param show <name>` prints nothing | enable the gating parameter (`MAV_1_CONFIG` ≠ 0) and reboot |
| The parameter belongs to another vehicle type | the same: `FW_*` on a multicopter | nothing; you can still see it with `param show -a` |

An example of the second case: `MAV_1_MODE` and `MAV_1_RATE` appear in QGC only after `MAV_1_CONFIG` ≠ 0 and a reboot, because the instance start command reads them. `param set` and `param touch` also mark a parameter as used.

### Three backups
| | QGC `.params` | `param save <file>` | `param show-for-airframe` |
|---|---|---|---|
| Format | text: system, component, name, value, type, tab-separated | BSON | `param set-default` lines |
| What is inside | every used parameter, including those equal to the default | the third layer, where not equal to the default | used third-layer parameters, minus exceptions |
| Calibrations `CAL_*`, radio `RC*` | yes | yes | no |
| `SYS_AUTOSTART` | yes | yes | no |
| Human-readable, `diff` in git | yes | no | yes |
| Restoring | QGC → Load from file for review... | `param import` or `param load`, then `param save` | lines in `config.txt` or in your own airframe |

`show-for-airframe` does not print `SYS_AUTOSTART`, `SYS_AUTOCONFIG`, `MAV_TYPE`, `SENS_DPRES_OFF`, anything starting with `RC`, `TC_`, `CAL_`, or counter (volatile) parameters; 1.17 and older also skip `SENS_BOARD_*`, while 1.18.0 prints them (`param.cpp`, v1.18.0), so delete the board rotation and level offsets from the output before moving it to another vehicle. The receiver port `RC_PORT_CONFIG` and `RC_CRSF_PRT_CFG` also start with "RC", so add them by hand.

Rule of thumb. For a change history in git (eng-ci-configs), use `.params`: it also shows the defaults that will change with the firmware. To roll back the same vehicle on the same firmware, use BSON. To move settings to another vehicle, use only `show-for-airframe`: it holds nothing tied to a particular board. In Betaflight and INAV, `diff all` and `dump` play the same role (bf-cli, inav-cli-backup).

When loading a `.params` file, QGC rejects a file with a different System Id, skips names that do not exist on the vehicle and shows a list of them. Values are written one at a time in file order, which is alphabetical.

### What must not be carried over
**Calibrations.** `CAL_ACCn_ID`, `CAL_GYROn_ID`, `CAL_MAGn_ID` are device IDs: bus type, bus number, address and chip type. There is no serial number in them. The arming check only requires the sensor's ID to be found in `CAL_*_ID`. So someone else's file on a board of the same model passes the check: the IDs match, while the offsets and scales come from another unit, giving a level and heading error without a single warning. On a board of another model the IDs do not match and the firmware asks for a calibration. Do not carry over `CAL_*`, `TC_*`, `RC*` or the level offsets `SENS_BOARD_X_OFF` / `SENS_BOARD_Y_OFF`.

**Output write order.** When an output's function changes from Disabled to Motor or Servo, the output driver itself writes the motor `MIN`/`MAX` and the servo `DIS` (px4-outputs-servos). When you load a file into fresh firmware, these writes compete with the values from the file; after loading, check `PWM_*_MINn`, `MAXn`, `DISn` against the file and reboot the board.

**A file from another version.** A `.params` file from 1.15 contains all the 1.15 defaults. Loaded in full into 1.17, it puts them back over the new ones (for example `MC_ROLL_P` 6.5 instead of 4.0) and makes them saved values. Removed parameters do not carry over. The migration procedure is in px4-intro: a clean start and copying values one by one.

**SITL → vehicle.** SITL has different startup defaults and no calibrations.

### Inspection commands
| Command | What it shows and where to look |
|---|---|
| `listener <topic> [-i inst] [-n count] [-r rate]` | a uORB message (px4-architecture). With no options, the latest message of each instance; `never published` means nobody has published the topic |
| `uorb top [-1] [-a] [filters]` | columns `INST #SUB RATE #Q SIZE`: publication rate and number of subscribers |
| `uorb status` | all topics: `INST #SUB #Q SIZE PATH` |
| `top`, `top once` | tasks: `CPU(ms) CPU(%) USED/STACK PRIO(BASE)`; at the bottom `CPU usage: … tasks, … sched, … idle` |
| `work_queue status` | the queues and their items, with rate in hertz and interval |
| `perf`, `perf reset`, `perf latency` | driver timing and event counters |
| `ver all` | board and firmware, fields below |
| `dmesg`, `dmesg -f &` | boot output and background module output |
| `free`, `ps`, `df` | memory, tasks, file systems (nsh) |
| `ls /fs/microsd`, `cat /etc/init.d/rc.serial` | the SD card and the startup scripts in ROMFS |
| `i2cdetect -b <bus>` | an address table: a hex address means a device answered, `--` means none |
| `logger status` | the log file, `Wrote … (avg … KiB/s)`, `dropouts`, `max used buffer` |
| `hardfault_log check` / `count` | whether there was a hard fault; `rcS` writes `fault_*.txt` to the SD card itself |
| `sd_bench` | the card's write speed and `max write time` |

`listener` details. Without `-n` it does not wait for new data, it prints the last published message, and the sensor may have died a minute ago. Check freshness: `listener <topic> -n 5` waits for new messages and after 2 s of silence prints `Waited for 2.0 seconds without a message. Giving up.` With `-r R` and no `-n` it prints `30 · R` messages. Exit with Ctrl+C, Esc or Q.

`ver all` belongs at the top of any bug report: `HW arch` (the build target), `HW type`, `HW version`, `HW revision` (board revision from resistors or EEPROM), `PX4 git-hash`, `PX4 version`, `OS version` (NuttX), `Build datetime`, `Build variant`, `Toolchain`, `PX4GUID` (a unique board ID from the MCU UID), `MCU`.

### Module status and dangerous commands
Every module has `<module> status`; one that is not running answers `not running`. What to look for:

| Command | Line |
|---|---|
| `commander status` | `Armed` / `Disarmed`, `navigation mode`, `in failsafe: yes/no` |
| `commander check` | `Preflight check: OK` / `FAILED`, the result of the previous evaluation; a second later the fresh reasons appear as `Preflight Fail: …` lines in `dmesg` and in the QGC Arming checks panel; if in doubt, run the command again |
| `sensors status` | `selected gyro`, `selected accel`, and for compasses `Ext ROT` or `Internal` |
| `ekf2 status` | `attitude`, `local position`, `global position`: 1 or 0 |
| `logger status` | mode, file, `dropouts` |
| `mavlink status [streams]` | covered in px4-hardware-peripherals |
| `gps status`, `px4io status`, `dshot status`, `uavcan status`, `navigator status` | the driver is alive, its port, error counters |

Commands that change the vehicle's state instead of reading it:

- **`commander arm -f`** arms bypassing every preflight check. The motors spin up to minimum immediately. Props off only; read the reason for the refusal with `commander check` first.
- **`commander disarm -f`** disarms in the air: the motors stop.
- **`commander takeoff`**, **`commander mode <mode>`** arm and take off; change the mode the same way a switch does. The 1.17 mode list: `manual`, `acro`, `offboard`, `stabilized`, `altctl`, `posctl`, `altitude_cruise`, `position:slow`, `auto:mission`, `auto:loiter`, `auto:rtl`, `auto:takeoff`, `auto:land`, `auto:precland`, `ext1` (1.18 adds `auto:course`).
- **`commander termination`** terminates the flight: outputs go to their failsafe values, the parachute fires.
- **`actuator_test`** spins a motor and moves a servo (px4-outputs-servos); **`failure`** disables a sensor (px4-safety-return).
- **`reboot`** does not check whether the vehicle is armed: in flight that is a crash. `reboot -b` reboots into the bootloader.
- **`rm`**, **`mtd erase`**, **`param reset_all`** erase without confirmation.

Safe ones: `tune_control play -t <1…21>` and `led_control test` check the buzzer and the LED; `logger on` starts a log right away without waiting for arming, `logger off` removes that override (the log still starts on arming).

### Boot: rcS and the files on the SD card
`ROMFS/px4fmu_common/init.d/rcS` runs on every boot. The order (line numbers from 1.17.0):

1. `ver all`, mounting the SD card, the `hardfault_log` check (48–118).
2. If `/fs/microsd/etc/rc.txt` exists, it runs and nothing else does (124–126).
3. Otherwise: `param import` of the main file (148–149), the reset by `SYS_AUTOCONFIG` (192–195), the board defaults (212–218), the airframe from `SYS_AUTOSTART` (233).
4. **`/fs/microsd/etc/config.txt`** (314–318).
5. Sensors, `ekf2`, `commander`, outputs, vehicle-type modules, `rc.serial` with the ports, `navigator` (322–583).
6. **`/fs/microsd/etc/extras.txt`** (599–603).
7. The logger (608–613), DroneCAN (634–640), `mavlink boot_complete` (680).

In 1.18.0 step 3 starts differently (`rcS`, lines 197–206): instead of `param import` there is a new subcommand, `param load-or-init <backup file>`. Empty storage (first boot, a firmware switch) is no longer an error: it is filled from the backup file or with defaults and saved right away, with no error tune; the firmware falls back to the backup through `param import` only when the storage is corrupt. At the end of `rcS` (line 728) there is now `param lock`: parameters the board build declared read-only then reject `param set` and `param reset` ("Parameter … is read-only."), and `param show -l` lists them. The default fmu-v6x builds have no such list (not tested on hardware).

| File | What it replaces | What it is for | Check |
|---|---|---|---|
| `config.txt` | nothing: it is added after the airframe, before the modules start | defaults and forced parameter values | `param show <name>` after boot |
| `extras.txt` | nothing: it is added after the modules start | starting your own applications, MAVLink stream rates | `<application> status`, `mavlink status streams` |
| `rc.txt` | the whole startup, including parameter loading and USB MAVLink | board debugging; not needed in operation | debug UART only |

The rule for `config.txt`: `param set-default` sets a default, so whatever the operator changes in QGC stays; `param set` writes the value on every boot and overrides anything written from QGC. Use UNIX line endings in these files. An error in them is visible only on the debug UART; with an empty `rc.txt` the board will not even bring up USB, and the fix is deleting the file from the card.

What is on the card (`/fs/microsd`): `log/` (logs: `sess001/log001.ulg` or `2026-11-22/10_15_30.ulg`), `mission_log/`, `etc/`, `parameters_backup.bson`, `dataman` (missions and the geofence), `fault_*.txt`, and `params` if the board keeps its parameters on the card. At start the logger deletes the oldest log directory while less than 300 MiB is free (or 10 % of the card, if that is less); with less than 50 MiB free the log does not start. In 1.18.0 the rule is different: the oldest directories are deleted until at least (100 − `SDLOG_ROTATE`) % of the card plus `SDLOG_MAX_SIZE` is free, and logging is refused below 1 MiB (`logger/util.cpp`, v1.18.0).

### Which tool for which question
{{diagram:px4-console-tool-choice|Each typical question has one main command and one output line that answers it; commands that change state are not in this table.}}

| Question | Commands in order | What confirms it |
|---|---|---|
| Is the sensor visible? | `listener <topic>` → `<driver> status` → `dmesg` → `i2cdetect -b <bus>` | the number of instances rather than `never published`; the address in the table |
| Is the data fresh? | `listener <topic> -n 5`, `uorb top <topic>` | no `Giving up`; `RATE` close to the expected one |
| Why won't it arm? | `commander check` → `dmesg` → `commander check` again | `FAILED` and `Preflight Fail: …` lines; the second call shows the result of the fresh evaluation |
| Is the driver running? | `<module> status`, `work_queue status` | not `not running`; a line with a rate |
| What was changed in the parameters? | `param show -c`, `param show-for-airframe`, `param status` | lines with `+` and `*`; `storage array` |
| A parameter missing from QGC? | `param find`, `param show <name>`, `param show -a` | `not found` means not in the build; found but not shown means not used |
| Is the CPU overloaded? | `top once`, `listener cpuload`, `work_queue status` | `idle` in the `CPU usage` line; `load` against `COM_CPU_MAX` = 95 % |
| A log with gaps? | `logger status`, `sd_bench` | `dropouts` not 0, `max used buffer` near the limit |
| Which board and firmware? | `ver all` | `HW arch`, `PX4 version`, `PX4 git-hash` |

CPU load: `cpuload.load` = 1 − the idle fraction, from 0 to 1. The arming check trips if the load stays above `COM_CPU_MAX` (95 %) for more than 2 s; `COM_RAM_MAX` does the same for memory.

### Differences in 1.15 and 1.16
| What | 1.15 | 1.16 | 1.17 |
|---|---|---|---|
| The `param`, `listener`, `top`, `dmesg` commands | the same subcommands and options | the same | — |
| Parameter file path | chosen by `rcS`: FRAM if present, otherwise SD | the board's `CONFIG_BOARD_PARAM_FILE` | as in 1.16 |
| `SYS_PARAM_VER` and the reset on airframe version | no | yes | yes |
| Exclusions of the `SYS_AUTOCONFIG` reset | without `SYS_PARAM_VER` | with it | with it |
| Disabling the log | `SDLOG_MODE` = −1 | `SDLOG_MODE` = −1 | `SDLOG_BACKEND` = 0; `SDLOG_MODE` = −1 removed |
| Translation on BSON import | `FW_ARSP_MODE`, `CBRK_AIRSPD_CHK`, `SYS_MC_EST_GROUP` | the same | plus `ASPD_FALLBACK_GW`, `SDLOG_MODE` |
| `commander mode altitude_cruise` | no | no | yes |
| Extra board script `rc.additional_init` | no | no | yes |

`SYS_PARAM_VER`: an airframe can declare `set PARAM_DEFAULTS_VER 2`; if that number does not match the saved `SYS_PARAM_VER`, `rcS` sets `SYS_AUTOCONFIG` = 1, saves and reboots, and the settings are reset to the airframe defaults without your involvement. In the stock 1.17.0 airframes the version is 1 everywhere.

### Place in the system

- **Takes in:** the first setup order and the `param set`, `actuator_test`, `commander check` commands (`px4-setup-scratch`); the uORB topics that `listener` prints (`px4-architecture`); the rename table and the "only what differs from the default is stored" rule (`px4-intro`).
- **Hands on:** the "parameter → reboot → `status` → `listener`" check for ports and sensors (`px4-hardware-peripherals`); a text parameter file to keep in git (`eng-ci-configs`); inspection commands for debugging the uXRCE-DDS bridge (`px4-ros2`).
- **If you get it wrong here:** someone else's `CAL_*` from a neighboring vehicle's file means a skewed horizon and heading with no warnings (`px4-hardware-peripherals`); an output file loaded without checking `MIN`/`MAX`/`DIS` means servos hard against their stops or motors without minimum throttle (`px4-outputs-servos`); `commander arm -f` instead of reading the reason means a takeoff with a failed check (`px4-safety-return`).

## practice
An exercise with no hardware and no simulator. You need paper or an editor. Every answer follows from the module's theory and is checked against the reference at the end.

### Step 1. What is stored and what comes back
A quadcopter on a Pixhawk 6X, PX4 1.17.0, airframe 4001. History: the airframe was selected, the accelerometer and radio were calibrated; `MC_ROLLRATE_P` was raised to 0.18; `COM_LOW_BAT_ACT` = 3; `RTL_RETURN_ALT` was set to 45 and back to 30; `NAV_RCL_ACT` was set to 3 and back to 2; `MAV_1_CONFIG` = 102; the last line typed was `param set SDLOG_PROFILE 3; param show -c`. There was no reboot after `MAV_1_CONFIG`.

A training example, put together by hand (the columns are the characters and fields of a `param show -c` line; indices omitted; the number in `CAL_ACC0_ID` is made up):

| Used | Mark | Name | Value | Firmware default | Startup default |
|---|---|---|---|---|---|
| x | + | `CAL_ACC0_ID` | 2490378 | 0 | 0 |
| x | + | `CAL_ACC0_XOFF` | 0.0120 | 0 | 0 |
| x | + | `COM_LOW_BAT_ACT` | 3 | 0 | 0 |
| x | + | `LND_FLIGHT_T_LO` | 1260000000 | 0 | 0 |
| x | + | `MAV_1_CONFIG` | 102 | 0 | 0 |
| x | + | `MC_ROLLRATE_P` | 0.1800 | 0.15 | 0.15 |
| x | (space) | `NAV_RCL_ACT` | 2 | 2 | 2 |
| x | + | `RC1_MAX` | 2012.0000 | 2000 | 2000 |
| x | (space) | `RTL_RETURN_ALT` | 30.0000 | 60 | 30 |
| x | * | `SDLOG_PROFILE` | 3 | 1 | 1 |
| x | + | `SYS_AUTOSTART` | 4001 | 0 | 0 |

Answer:

1. How many records will the BSON hold after the autosave, and what is its size in bytes? Size: 4 bytes of length + one record per parameter (1 type byte, the name, 1 zero byte, 4 bytes for an int32 or 8 for a double) + 1 terminating byte.
2. Which lines remain in `param show -c` after a reboot?
3. Which of the changes need a reboot?
4. What remains after each of the three resets: the console `param reset_all`, QGC "Reset all to firmware's defaults", QGC "Reset to vehicle's configuration defaults" (after a reboot)? What will `RTL_RETURN_ALT` be after the console reset, before and after the reboot?
5. What will `param show-for-airframe` print?
6. The board was replaced with a new one of the same model, firmware 1.17.0. What does each of the three backups taken at the time of the listing restore, and what does it not?

### Step 2. Four situations
For each one, choose the commands in order and name the output line or field that confirms the hypothesis. You do not need to invent the output.

1. A GPS module with a compass is connected over I²C. QGC shows one compass.
2. The vehicle will not arm. The only link is the MAVLink Console over telemetry; the QGC checks panel is not at hand.
3. QGC does not list `MAV_1_MODE`, although the documentation has it.
4. The Flight Review logs have gaps, and the pilot complains about "stutters". The board is a Pixhawk 6X.

### Step 3. config.txt and extras.txt
On a Pixhawk 6X the companion is connected to TELEM2 (`/dev/ttyS4`). A card with these files must give every vehicle in the fleet:

- (a) MAVLink in Onboard mode on TELEM2 by default, but if the operator disabled the port in QGC, that must stick;
- (b) `SDLOG_PROFILE` = 1 always, whatever is written from QGC;
- (c) a `HIGHRES_IMU` stream on TELEM2 at 100 Hz.

Write both files. Then put these in execution order: `extras.txt`, starting `commander`, `param import`, `rc.serial`, the airframe, `config.txt`, starting the logger. Explain why (a) takes effect on the same boot.

### Step 4. Three dangerous steps in a procedure
A training example, put together by hand. Find the three dangerous or broken steps; the rest are correct.

1. Before upgrading from 1.15, save `fleet.params` from QGC and download the logs.
2. Flash 1.17.0.
3. Load all of `fleet.params` through Load from file for review....
4. Load the same file onto a second vehicle of the same model to skip the sensor calibration.
5. Change `MAV_1_CONFIG`, type `reboot` on the bench, disarmed.
6. Check the motors after the upgrade: leave the propellers on, `commander arm -f` in the console.
7. Take `param show-for-airframe` and put it in the vehicle's repository.
8. Take `param save /fs/microsd/backup_1117.bson` before tuning the controllers.

### Moving to real hardware
Propellers off for every item; `commander arm`, `actuator_test` and `reboot` are never typed in flight.

1. QGC → Analyze Tools → MAVLink Console: `ver all`, write down `HW arch`, `PX4 version`, `PX4 git-hash`.
2. `param status`: the storage and backup files, `storage array`; `param show -c`, save the output.
3. `param show-for-airframe` into the repository; `.params` from QGC; `param save /fs/microsd/backup.bson`.
4. `param set COM_DISARM_PRFLT 12` (default 10 s), after 3 s `param show COM_DISARM_PRFLT` shows the `+` mark. `reboot`, the value is still there. `param reset COM_DISARM_PRFLT`: the line disappears from `param show -c`.
5. `listener sensor_mag`, `sensors status`, `commander check`, then `dmesg`.
6. `top once` and `listener cpuload`: `load` plus the `idle` fraction is close to 1.
7. `logger status` before and after a minute of `logger on` / `logger off`.

Hardware criteria: the value from item 4 survived the reboot and disappeared after `param reset`; the three backups hold different numbers of parameters, explained by the "Three backups" table; `idle` and `load` agree to within 0.05.

Self-check: the lab is done when
- step 1: the record count and the BSON size matched the reference exactly; the lists for questions 2–6 matched the reference name by name;
- step 2: in each situation you named the same first command and the same confirming line as the reference;
- step 3: `config.txt` uses `set-default` for (a) and `set` for (b); the order of the seven events matched the reference;
- step 4: you named exactly steps 3, 4 and 6, and none of the correct steps went into the errors.

The hardware criteria in the previous paragraph are not part of this self-check; they are for the bench.

**Reference answer for the self-check.**

| Step | Correct result | Typical mistake and its cause |
|---|---|---|
| 1.1 | 9 records: all except `NAV_RCL_ACT` and `RTL_RETURN_ALT`. Size 4 + (17 + 23 + 21 + 21 + 18 + 23 + 17 + 19 + 19) + 1 = 183 bytes: six int32 and three double | 11 records: forgot that a value equal to the startup default is not written; 171 bytes: a double counted as 4 bytes |
| 1.2 | The same 9 lines, `SDLOG_PROFILE` marked `+`. `NAV_RCL_ACT` and `RTL_RETURN_ALT` disappear: they are not in the file | All 11 lines: the list before the reboot shows the RAM layer, not the file |
| 1.3 | `SYS_AUTOSTART`, `MAV_1_CONFIG`, `SDLOG_PROFILE`. The controller, failsafe, calibrations and `RC1_MAX` do not | `MC_ROLLRATE_P` put in the list: gains take effect immediately |
| 1.4 | Console: nothing; `RTL_RETURN_ALT` is 30 before the reboot (the airframe default is still in RAM) and 60 after it, because `SYS_AUTOSTART` = 0 and no airframe is loaded. Firmware's defaults: only `LND_FLIGHT_T_LO`. Vehicle configuration: `SYS_AUTOSTART`, `CAL_ACC0_ID`, `CAL_ACC0_XOFF`, `RC1_MAX`, `LND_FLIGHT_T_LO`; reset: `COM_LOW_BAT_ACT`, `MAV_1_CONFIG`, `MC_ROLLRATE_P`, `SDLOG_PROFILE` | "After `reset_all` the return altitude is 30": forgot that `SYS_AUTOSTART` is reset |
| 1.5 | Six `param set-default` lines: `COM_LOW_BAT_ACT 3`, `MAV_1_CONFIG 102`, `MC_ROLLRATE_P 0.1800`, `NAV_RCL_ACT 2`, `RTL_RETURN_ALT 30.0000`, `SDLOG_PROFILE 3`, and a comment about airframe 4001 | Four lines: the command prints every used third-layer parameter, including those equal to the default |
| 1.6 | `.params` restores everything, including the foreign `CAL_ACC0_*` and `RC1_MAX`, which must not be loaded: redo the calibrations. BSON (`param import` + `param save`) restores 9 records with the same foreign calibrations; it has no return altitude, that comes from the airframe. `show-for-airframe` restores six settings without calibrations, radio, `SYS_AUTOSTART` and flight time, so you select the airframe by hand | "BSON is safer, it is binary": it holds the same `CAL_*` |
| 2.1 | `listener sensor_mag`: `2 instances` or a single block; `sensors status`: is there a compass line with `Ext ROT`; `dmesg`: the driver start lines; `i2cdetect -b <bus>`: an address instead of `--` | Starting with a recalibration: there is nothing to calibrate while the topic is missing |
| 2.2 | `commander check` → `Preflight check: FAILED` (the result of the previous evaluation; the command also starts a new one); then `dmesg`: the `Preflight Fail: …` lines (`commander` messages do not go to the MAVLink shell); `commander check` again: the result of the fresh evaluation; `commander status`: `in failsafe` | `commander arm -f` "to see what happens": that bypasses the checks instead of reading them |
| 2.3 | `param find MAV_1_MODE`: found, so it is in the build; `param show MAV_1_MODE` prints nothing, so it is not used; `param show MAV_1_CONFIG` = 0. Set `MAV_1_CONFIG`, reboot | Rebuilding the firmware: there was no `not found` |
| 2.4 | `top once`: `idle` in the `CPU usage` line; `listener cpuload`: `load`; `logger status`: `dropouts` and `max used buffer`; `work_queue status`: rates. The px4/fmu-v6x build has no `sd_bench` | Prescribing `sd_bench` on a Pixhawk 6X: the answer will be `command not found` |
| 3 | `config.txt`: `param set-default MAV_1_CONFIG 102`, `param set-default MAV_1_MODE 2`, `param set SDLOG_PROFILE 1`. `extras.txt`: `mavlink stream -d /dev/ttyS4 -s HIGHRES_IMU -r 100`. Order: `param import` → airframe → `config.txt` → `commander` → `rc.serial` → `extras.txt` → logger. (a) works at once because `rc.serial` reads `MAV_1_CONFIG` after `config.txt`. No need to touch `SER_TEL2_BAUD`: the default is already 921600 | `param set MAV_1_CONFIG 102`: the port can no longer be disabled from QGC; `mavlink stream` in `config.txt`: the instance is not running yet |
| 4 | Step 3: the whole 1.15 file puts the 1.15 defaults back over 1.17 and makes them saved values, and removed names are lost. Step 4: foreign `CAL_*` pass the ID check and give wrong offsets. Step 6: arming bypassing the checks with the propellers on | Step 5 marked as an error: `reboot` on the bench while disarmed is a normal action; step 8: BSON is fine for a rollback on the same vehicle |

## diagnostics
- **Symptom:** the parameter is in the documentation but not in the QGC list.
  - Possible cause: the module is not built for the board; the parameter is not used (the gating parameter is off, or it belongs to another vehicle type's module).
  - What to do: `param find <name>`; `not found` means building the firmware via `boardconfig`; if found, enable the gating parameter and reboot, or `param touch <name>` and refresh the list in QGC.
- **Symptom:** after `param import` everything is set, after a reboot the old values are back.
  - Possible cause: an import does not trigger an autosave.
  - What to do: after `param import` or `param load` type `param save`, check `last auto save` and `storage array` in `param status`.
- **Symptom:** after a firmware update the vehicle flies differently, though "nobody touched" the parameters.
  - Possible cause: values equal to the old default were not stored and got the new defaults.
  - What to do: compare `.params` before and after; the change table is in px4-intro.
- **Symptom:** `top`, `dmesg` or `reboot` answer `command not found`.
  - Possible cause: this is SITL, and the `px4/sitl` build does not have these commands.
  - What to do: `listener cpuload`, `work_queue status`; module output shows up directly in the `pxh>` terminal.
- **Symptom:** `listener` prints sensor data, but QGC reports the sensor lost.
  - Possible cause: without `-n` it prints the last message, however old.
  - What to do: `listener <topic> -n 5`; on `Giving up`, `<driver> status` and `dmesg`.
- **Symptom:** after editing files on the SD card the board no longer connects over USB or telemetry.
  - Possible cause: `etc/rc.txt` left on the card, or an error in `config.txt` / `extras.txt`; Windows line endings.
  - What to do: take the card out and remove the files; to investigate, the debug UART at 57600 baud.
- **Symptom:** an error tune at power-on, and a `param import failed` line in `dmesg`.
  - Possible cause: the main parameter file is corrupt; the parameters came from the backup.
  - What to do: `param status`, compare `param show -c` with the latest backup; keep the `param_import_fail.bson` file for analysis.
  - Consequences: without a backup the vehicle is on defaults, with no calibrations and no failsafes.
- **Symptom:** on a board with parameters in flash, changes made in flight are lost after landing and a power-off.
  - Possible cause: writing to flash is postponed until disarm.
  - What to do: after disarming wait 2 s, or type `param save`.
- **Symptom:** after loading someone else's `.params` the horizon is tilted, the heading drifts, and the checks are silent.
  - Possible cause: foreign `CAL_*` on a board of the same model.
  - What to do: QGC → redo the calibrations; from now on carry over only `show-for-airframe`.

## checklist
- The version is written down from `ver all` before any change.
- The vehicle's repository holds `.params` and the `param show-for-airframe` output; BSON is only for a rollback on the same vehicle.
- `param save` typed after `param import` / `param load`.
- After changing a port, `SYS_AUTOSTART`, `SENS_EN_*`, `SDLOG_*`: a reboot, then `status` and `listener`.
- `CAL_*`, `TC_*`, `RC*` not carried over to another vehicle; after loading a file, `PWM_*_MINn`, `MAXn`, `DISn` checked.
- `commander arm -f`, `actuator_test`, `commander takeoff` only with the props off or in SITL; `reboot` and `commander disarm -f` never in flight.
- No `etc/rc.txt` on the SD card; `config.txt` uses `param set-default` for defaults and `param set` only where the value must override QGC.
- Power was not cut during the first 2 s after a parameter change.
- After a reset, `SYS_AUTOSTART`, the calibrations and the failsafes are checked (px4-safety-return).

## references
- PX4-Autopilot v1.17.0: src/systemcmds/param/param.cpp (param subcommands) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/systemcmds/param/param.cpp | primary | A
- PX4-Autopilot v1.17.0: src/lib/parameters/parameters.cpp (layers, export, import, reset) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/lib/parameters/parameters.cpp | primary | A
- PX4-Autopilot v1.17.0: src/lib/parameters/autosave.cpp (autosave delay) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/lib/parameters/autosave.cpp | primary | A
- PX4-Autopilot v1.17.0: src/lib/parameters/param_translation.cpp | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/lib/parameters/param_translation.cpp | primary | A
- PX4-Autopilot v1.17.0: ROMFS/px4fmu_common/init.d/rcS (boot order, config.txt, extras.txt, rc.txt) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/ROMFS/px4fmu_common/init.d/rcS | primary | A
- PX4-Autopilot v1.17.0: boards/px4/fmu-v6x/default.px4board and boards/px4/sitl/default.px4board (command set) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/boards/px4/fmu-v6x/default.px4board | primary | A
- PX4-Autopilot v1.17.0: src/systemcmds/topic_listener/listener_main.cpp | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/systemcmds/topic_listener/listener_main.cpp | primary | A
- PX4-Autopilot v1.17.0: src/modules/commander/Commander.cpp (commander subcommands, status) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/commander/Commander.cpp | primary | A
- PX4-Autopilot v1.17.0: src/modules/commander/worker_thread.cpp (resets via MAV_CMD_PREFLIGHT_STORAGE) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/commander/worker_thread.cpp | primary | A
- PX4-Autopilot v1.17.0: platforms/nuttx/src/px4/common/print_load.cpp (top output) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/platforms/nuttx/src/px4/common/print_load.cpp | primary | A
- PX4-Autopilot v1.17.0: src/modules/logger/util.cpp (free space on the card) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/logger/util.cpp | primary | A
- PX4-Autopilot v1.17.0: src/drivers/cdcacm_autostart/cdcacm_autostart.cpp (SYS_USB_AUTO) | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/drivers/cdcacm_autostart/cdcacm_autostart.cpp | primary | A
- PX4-Autopilot v1.17.0: Tools/mavlink_shell.py | https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/Tools/mavlink_shell.py | primary | A
- QGroundControl Stable_V5.0: src/FactSystem/ParameterManager.cc (.params format, resets) | https://github.com/mavlink/qgroundcontrol/blob/Stable_V5.0/src/FactSystem/ParameterManager.cc | primary | A
- PX4 Guide v1.17: PX4 Consoles/Shells | https://docs.px4.io/v1.17/en/debug/consoles | primary | A
- PX4 Guide v1.17: MAVLink Shell | https://docs.px4.io/v1.17/en/debug/mavlink_shell | primary | A
- PX4 Guide v1.17: System Startup (config.txt, extras.txt) | https://docs.px4.io/v1.17/en/concept/system_startup | primary | A
- PX4 Guide v1.17: PX4 SD Card Layout | https://docs.px4.io/v1.17/en/concept/sd_card_layout | primary | A
- PX4 Guide v1.17: Finding/Updating Parameters | https://docs.px4.io/v1.17/en/advanced_config/parameters | primary | A

## notes
The firmware was not built or run in this pass: command behavior and output strings come from reading the source of the v1.17.0, v1.16.2 and v1.15.4 tags, and QGC behavior from `ParameterManager.cc` on the Stable_V5.0 branch (rechecked against that source for the English edition, commit b21fa4f: "Reset all to firmware's defaults" sends `MAV_CMD_PREFLIGHT_STORAGE` with param1 = 2, "Reset to vehicle's configuration defaults" writes `SYS_AUTOCONFIG` = 2; the System Id rule was not rechecked; the firmware side, `MAV_CMD_PREFLIGHT_STORAGE` and `SYS_AUTOCONFIG` in `rcS`, was checked). The docs.px4.io pages were read from the `docs/en` directory of the v1.17.0 tag. Not verified by running: the wording of the QGC reboot reminder; that the `Preflight Fail: …` lines reach `dmesg` on a given board (the buffer is enabled on fmu-v6x and fmu-v6c by the `BOARD_ENABLE_CONSOLE_BUFFER` macro). Per the `param_value_is_default()` code, a float parameter written below its default is printed with a space instead of `+`, although the value is saved; the training list in step 1 has no such lines. The `rcS` line numbers and build contents refer to 1.17.0 and the px4/fmu-v6x and px4/sitl boards; for your own board, look at its `default.px4board`.
