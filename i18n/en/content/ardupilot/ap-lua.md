---
id: ap-lua
title: "Lua: scenarios and fault injection"
level: L3
readingTime: 35 min
firmware: ArduPilot 4.7 (checked against 4.7.3; the lab was captured on SITL 4.7.2)
status: published
added: 2026-11-07
tags:
  - Lua
  - fault injection
  - SITL
related:
  - ap-sitl
  - ap-heavy
next:
  - ap-heavy
source: content/ardupilot/ap-lua.md
source_hash: 510914301f73
---

## summary
ArduPilot can run Lua scripts right on the flight controller: add modes, read sensors, react to switches. In a training project the main use is fault injection: deliberately breaking a motor or a sensor in SITL and watching how the drone, and you, cope. This module explains how scripting works, how to bind a script to a transmitter switch, and how to build a set of "chaos scripts", each on its own switch.

## theory
### How scripting works
- It is enabled with `SCR_ENABLE = 1` and a reboot.
- Scripts (`.lua`) live in `APM/scripts` on the SD card; in SITL, in the `scripts` folder of the directory the simulator was started from.
- Every script runs in its own sandbox and at low priority: flight code matters more, and nobody promises a script an exact schedule.
- `SCR_HEAP_SIZE` sets the memory for scripts. If it is too small, the 4.7 firmware expands the heap by itself in 20 kB chunks and reports `Required SCR_HEAP_SIZE over N`; that message is stored as a scripting error and blocks arming (`Scripting: Required SCR_HEAP_SIZE over N`), so raise `SCR_HEAP_SIZE` to N plus a margin. If expansion is impossible or is disabled with bit 6 of `SCR_DEBUG_OPTS`, scripts fail with `out of memory`. If it is too large, the EKF may fail to initialize.
- If one script fails with an error (including running out of memory inside its own call), only that script is removed. All scripts stop only if the Lua engine itself has died (`Lua: Engine Error …`, then `Scripting: stopped`), until scripting is restarted.
- Scripting is built only for boards with more than 1 MB of flash (`AP_Scripting_config.h`): F405/F411 boards with 1 MB do not have it; F427/F429 boards with 2 MB (Pixhawk 1, Cube Black), F7, and H7 do.

### The update() pattern
A script is an `update()` function that does the work and returns itself and a delay in milliseconds until the next call. No infinite loops: the scheduler calls the function again.

How it works inside (`libraries/AP_Scripting/lua_scripts.cpp`, Copter-4.7.2). All scripts live in one thread and one Lua state with the shared `SCR_HEAP_SIZE` memory. The scheduler keeps a list of scripts ordered by next run time, takes the nearest one, and calls its function in protected mode. After it returns, the scheduler checks that exactly two values came back, a function and a number, and schedules the next run at `call start time + delay` (the `next_run_ms = start_time_ms + …` line). Three consequences follow:

- the delay is a **minimum**, not a period: in the practice run a script with `return update, 100` was called on average every ≈ 113 ms (112.8 ms in the step 6 output; SITL, 5× speedup). For "every 0.1 s" logic that is fine; for time-based measurements use `millis()`, not a call counter;
- one call is limited to `SCR_VM_I_COUNT` virtual machine instructions (10000 by default); exceed that and you get the message `<name>.lua exceeded time limit` and the script is removed. Split heavy work into portions across calls;
- if a call returns one value, more than two, or the wrong types, the script is also removed, with the message `did not return a delay` / `returned bad result count`, and that blocks arming; a `return` with no values is the normal end of a one-shot script: it is removed silently, with no message and without blocking arming.

### An error in a script: what exactly breaks
A runtime error (indexing `nil`, a wrong argument type) does **not** crash the firmware and does not stop other scripts, but it removes that script until a reboot. The consequences are visible in the step 6 run: the GCS receives `Lua: ./scripts/bad.lua:2: attempt to index a nil value (local 't')`, the first time with CRITICAL severity, then repeated every 10 s with DEBUG severity, no more than 10 times (the text itself is kept for the arming check). Arming is blocked right after the error; the GCS gets the `PreArm: Scripting: …` line every 30 s, which is the pre-arm reporting period, so in the run it arrived at 30.3 s. An arming attempt gets a `COMMAND_ACK` with result 4 (FAILED) and the text `Arm: Scripting: …`. This is deliberate: the failed script may have been a safeguard, and you must not fly without it. You can turn the check off with bit 4 of `SCR_DEBUG_OPTS`, but for a safeguard script that means flying without the safeguard and not knowing it.

Scripts are read only at startup. A new or fixed file is picked up after a reboot, on the `MAV_CMD_SCRIPTING` command (42701) with `param1 = 3` (`SCRIPTING_CMD_STOP_AND_RESTART`), with an `RCx_OPTION = 316` switch (Stop-Restart Scripting), or by toggling `SCR_ENABLE` 0 → 1; that restarts the whole Lua engine without rebooting the flight controller. The firmware does not check whether the vehicle is armed, so the course rule is to restart scripts only on the ground: during the restart all scripted safeguards are off (a course guideline).

{{diagram:lua-script-lifecycle|A script is rescheduled as long as update() returns a function and a delay; any error removes it until a reboot and blocks arming through PreArm: Scripting.}}

### Your own parameters and log messages
A script can create its own parameters, which are visible in the GCS and saved like ordinary ones: `param:add_table(key, "FLT_", 2)` reserves a table with a prefix (the key is your own table number, different for every script), and `param:add_param(key, 1, "DELAY", 5)` creates `FLT_DELAY` with a default of 5. A value changed with `param set FLT_DELAY 7` is saved to storage and survives a restart, provided the script creates the table with the same key and prefix; the step 6 run does not test this (the `FLT_*` values were not changed there), so test it yourself: change it, restart SITL without `-w`, and read it back (a conclusion from the documentation and the code). Choose a unique prefix: two scripts with the same prefix cannot coexist. `logger:write("FLT", "Alt,Mask", "fi", "m-", "0-", alt, mask)` writes your own `FLT` message to the `.BIN` (a name of up to 4 characters, with the format as in `AP_Logger`: `f` is float, `i` is int32), and you can then see it next to `RCOU` and `CTUN` in a log analyzer.

### Reference: SCR_* parameters (ArduPilot 4.7.2)
The source is `libraries/AP_Scripting/AP_Scripting.cpp:65–200`, tag Copter-4.7.2.

| Parameter | Default | What it does | When to touch it |
|---|---|---|---|
| `SCR_ENABLE` | 0 | 1 is Lua Scripts; needs a reboot | always first |
| `SCR_HEAP_SIZE`, bytes | 204800 on SITL/Linux and on boards in the ≥ 1000 kB memory class (H7); 102400 at ≥ 500 kB; 44032 otherwise | memory for all scripts | on `Required SCR_HEAP_SIZE over N`, set N plus a margin of 20–50 kB (a course guideline) |
| `SCR_VM_I_COUNT` | 10000 | the instruction limit for one call | on `exceeded time limit`, split the work first, then raise it |
| `SCR_DEBUG_OPTS` | 0 | bits: 0 reports "No scripts to run" when all scripts have stopped, 1 runtime messages for memory usage and execution time, 2 suppresses logging of the scripts, 3 logs memory usage and execution time, 4 disables the pre-arm check, 5 saves the CRC of the scripts to `SCR_LD_CHECKSUM`/`SCR_RUN_CHECKSUM`, 6 disables heap expansion on allocation failure | debugging; bit 4 only deliberately |
| `SCR_DIR_DISABLE` | 0 | bits: 0 do not load from ROMFS, 1 do not load from `APM/scripts` | scripts built into the firmware, with no SD card |
| `SCR_USER1…6` | 0 | general-purpose numbers for scripts | quick settings without your own table |
| `SCR_LD_CHECKSUM`, `SCR_RUN_CHECKSUM` | −1 (disabled) | the required CRC of the loaded / running scripts, otherwise a pre-arm failure | a vehicle in service: nobody has slipped in a foreign script |
| `SCR_THD_PRIORITY` | 0 (Normal) | the priority of the scripting thread | scripts acting as drivers (UART, CAN) |
| `RCx_OPTION` | 300…315, 316 | Scripting1…Scripting16 (in 4.6, 300…307); 316 is Stop-Restart Scripting | a switch for a script; an emergency scripting restart |

### Binding to a switch
The `RCx_OPTION` parameter assigns a function to a transmitter channel. Values 300–315 are Scripting1…Scripting16 (in 4.6, only 300–307) and are reserved for scripts. A script finds its channel with `rc:find_channel_for_option(300)` and reads the switch position with `get_aux_switch_pos()` (0 low, 1 middle, 2 high).

### Applets and examples
The ArduPilot repository has ready-made scripts: `libraries/AP_Scripting/applets` (ready to use, each with an `.md` description) and `libraries/AP_Scripting/examples` (teaching examples). A good one to start with is the `motor_failure_test.lua` applet: it stops the motors given by the `MOT_STOP_BITMASK` bitmask when the Scripting1 switch is high. An octocopter should keep flying with one failed motor.

### What the API can do (per `docs/docs.lua` in AP_Scripting)
Reading state: `ahrs:get_position()`, `ahrs:get_velocity_NED()`, `ahrs:get_yaw()`, `gps:num_sats()`, `battery:voltage()`, `rangefinder:distance_orient()` (in meters; `distance_cm_orient` is deprecated), `esc_telem:get_rpm()`, `vehicle:get_mode()`, `arming:is_armed()`; acting: `vehicle:set_mode()`, `vehicle:set_target_velocity_NED()`, `vehicle:set_target_location()`, `mission:set_current_cmd()`, `SRV_Channels:set_output_pwm()`, `relay:on()`, `param:set()`/`param:add_param()` (your own parameters with a prefix), `gcs:send_text()`, `logger:write()` (your own log messages!), `notify:play_tune()`, `rc:get_aux_cached()` (a switch with `RCx_OPTION = 300..315`, Scripting1..16; in 4.6, 300..307), `serial:find_serial()` (your own protocol on a UART), `CAN:get_device()` (DroneCAN), `periph` on AP_Periph. Timers are the `update, 100` return (ms until the next call). Scripting parameters: `SCR_ENABLE`, `SCR_HEAP_SIZE` (memory; the default depends on the board's memory class: 43, 100, or 200 kB; on F427/F429 scripts run but the heap is small, and F7/H7 have room to spare), `SCR_VM_I_COUNT` (the per-call instruction limit, a guard against hangs), `SCR_DEBUG_OPTS`.

### Applets as a textbook
`libraries/AP_Scripting/applets/` holds ready-made scripts with `.md` descriptions: `motor_failure_test.lua` (stops motors by the `MOT_STOP_BITMASK` bitmask with the Scripting1 switch: a motor failure test on a hexa or an X8 in SITL and in the field), `VTOL-quicktune.lua` (QuikTune for multicopters and VTOL), `rover-quicktune.lua`, `copter-deadreckon-home.lua` (a dead-reckoning return when GPS is lost), `arming-checks.lua` (your own pre-arm checks), `ahrs-source-extnav-optflow.lua` (switching EKF sources by quality), `BattEstimate.lua`, `MissionSelector.lua`, `net_webserver.lua`, `crsf-calibrate.lua` (added in 4.7; 4.6.3 does not have it), `SmartAudio.lua`. Three applets for the field, all on a switch and all present in both 4.6.3 and 4.7.2:

| Applet | Switch | What it does | When to use it |
|---|---|---|---|
| `leds_on_a_switch.lua` | `RCx_OPTION = 300` (Scripting1) | writes `NTF_LED_BRIGHT`: low is 0 (off), middle is 1, high is 3 (maximum) | at night or on a shoot, when the LEDs must go dark in flight (`ap-notify`) |
| `revert_param.lua` | `PREV_RC_FUNC` (300 by default), enabled with `PREV_ENABLE = 1` | the switch high restores the values that were present at boot for `ATC_RAT_*`, `ATC_ANG_*_P`, `ATC_RATE_*_MAX`, `INS_HNTCH_*`, `INS_GYRO_FILTER` (on a QuadPlane, `Q_A_*`; on a fixed wing, `RLL_RATE_*`, `PTCH_RATE_*`, `*2SRV_TCONST`, TECS); at startup it reports `Stored N parameters`, on a revert `Reverted N parameters`. `revert_param.md` also promises `PSC_D_*`/`PSC_NE_*`, but the 4.7.2 code looks for the old names (`PSC_ACCZ_*`, `PSC_VELXY_*`), which do not exist in 4.7, so the position controller is not reverted; check the number in `Stored N` | manual in-flight tuning with the `TUNE` knob or from the GCS: the switch reverts it if an oscillation starts (`ap-aux-tune`) |
| `Param_Controller.lua` | `RCx_OPTION = 302` (Scripting3) | loads the `params.param` file from `scripts/1`, `scripts/2`, or `scripts/3` by switch position (low, middle, high); the changes are not kept after a reboot | several parameter sets (with and without a payload) on one vehicle |

Rule: two applets on the same `RCx_OPTION` function (both default to 300) share a switch, so reassign the function for one of them (`PREV_RC_FUNC = 301` and `RCx_OPTION = 301` on another channel). The check after installation: reboot, refresh the parameter list (the `PREV_*` parameters have appeared), and a flick of the switch produces a message or a parameter change. Reading them is the best way to learn the API and the style (defensive checks, `pcall`-style wrappers, parameters through `param:add_table`).

### Worked example: an ESC temperature guard
```lua
-- esc_temp_guard.lua: warn at 80 C, switch to LAND at 100 C (any ESC), check every 500 ms
local WARN, CRIT = 80, 100
local MODE_LAND = 9
local warned = false
function update()
  for i = 0, 7 do
    local t = esc_telem:get_temperature(i)          -- nil if no telemetry; value in centi-degrees
    if t then
      t = t // 100
      if t >= CRIT and arming:is_armed() and vehicle:get_mode() ~= MODE_LAND then
        gcs:send_text(2, string.format("ESC %d %dC: LAND", i + 1, t))
        vehicle:set_mode(MODE_LAND)
      elseif t >= WARN and not warned then
        gcs:send_text(4, string.format("ESC %d temp %dC", i + 1, t)); warned = true
      end
    end
  end
  return update, 500
end
return update()
```
Test in SITL: `SIM_ESC_TELEM = 1`, replace the threshold with 30 °C, and confirm that it triggers; then test on the bench. Enter it in the FMEA as a mitigation with a reference to the test (see the "Fault tolerance" module).

### When to use a script and when not to
Selection rule (a course guideline). Lua suits logic that can live with a reaction time of hundreds of milliseconds: guards on temperature, voltage, or geometry, switching parameter sets, your own log messages, fault injection in SITL. It does not suit anything that must run in every control loop: the call period is not guaranteed (≈ 113 ms instead of 100 in the run), and a failed script is removed entirely. If a guard is entered in the FMEA as a mitigation, it must have a test outside flight (step 5) and a check that it is actually running after boot: a startup message and the arming check. If the logic needs a camera, a map, or heavy computation, that is a job for a companion computer over MAVLink (`ap-companion`), not for a script.

{{diagram:lua-runtime|How a script is executed: a file from APM/scripts/ goes into the Lua VM, update() returns itself and a period; the call is protected (pcall), so an error does not crash the firmware, but the script itself is removed; actions go through the API bindings.}}

### Place in the system

- **Receives:** the switch position through `RCx_OPTION = 300…315`; the vehicle state through the API: `ahrs`, `battery`, `esc_telem` (ESC telemetry is covered in `f-motors-esc`); board resources: more than 1 MB of flash and the `SCR_HEAP_SIZE` memory (`ap-intro`).
- **Provides:** fault injection, that is, stopping motors to test an X8 (`ap-heavy`) and scenarios in `ap-sitl`; your own guards, such as ESC temperature, as a mitigation in the FMEA (`ap-safety-fs`); QuikTune to step 5 of tuning (`ap-tuning`).
- **If you get it wrong here:** `SCR_HEAP_SIZE` too high → the EKF may fail to initialize → the vehicle does not arm, and people look for the cause in navigation (`ap-ekf`). Too low → the script fails, and the guard entered in the FMEA as a mitigation is not running at the moment of the failure (`ap-safety-fs`).

## practice
### Step 1. Enable scripting in SITL
```
param set SCR_ENABLE 1
reboot
```

### Step 2. An indicator script on a switch
A minimal script: it reports changes of the Scripting2 switch position and the arming state to the GCS.

```lua
-- switch_report.lua: report Scripting2 switch position and arming state to the GCS
local SWITCH_OPTION = 301  -- RCx_OPTION = 301 (Scripting2)
local switch = rc:find_channel_for_option(SWITCH_OPTION)
local last_pos = -1

function update()
  if not switch then
    gcs:send_text(4, "switch_report: no channel with RCx_OPTION=301")
    return update, 5000
  end
  local pos = switch:get_aux_switch_pos()
  if pos ~= last_pos then
    local armed = arming:is_armed() and "ARMED" or "disarmed"
    gcs:send_text(6, string.format("Scripting2 -> %d (%s)", pos, armed))
    last_pos = pos
  end
  return update, 200
end

return update, 1000
```

Put the file in `scripts/`, assign the switch (`param set RC9_OPTION 301`), restart SITL, and flick the switch.

### Step 3. A motor failure on a switch
1. Copy the `motor_failure_test.lua` applet into `scripts/`.
2. Assign a switch to Scripting1: `RCx_OPTION = 300`.
3. After a reboot `MOT_STOP_BITMASK` appears. Set it to 1 and motor 1 will be stopped.
4. In SITL with the `octa-quad` frame: take off, LOITER, switch high. Watch the drone compensate for the failure.

### Step 4. A set of chaos scripts
The idea of the training set: every "failure" is a separate script on its own switch, so you can enable them independently:

- an arming indicator (an LED or a message);
- a manual motor failure (the applet);
- random sensor failures through the simulator's `SIM_*` parameters;
- a random failure of 1–3 motors.

The `SIM_*` parameter names change between versions, so look up the current ones in your build with `param show SIM_GPS*` in MAVProxy. Scripts like these are for SITL only: a real vehicle has no `SIM_*` parameters.

### Step 5. A guard with tests before SITL
The starter for project 11, `examples/lua-protection`: `guard.lua` has a vibration guard (LAND), a keep-inside-a-polygon guard with a margin (RTL), and a `pcall` wrapper that sends the vehicle into RTL after three errors in a row in the air. The tests run **this very** Lua file through `lupa` against a stub of the bindings (`millis`, `ahrs`, `vehicle`, `param`, `gcs`, `logger`), so logic errors are caught in a fraction of a second and SITL remains the acceptance test. Run `python -m pytest -q examples/lua-protection/tests`, then add a third guard (for example, voltage sag under load) together with a test.

### Step 6. Fault injection on a timer: a SITL run
This step was run on ArduCopter 4.7.2 SITL (the `hexa` frame, `--speedup 5`, pymavlink 2.4.50) without MAVProxy. The `fault_inject.lua` script creates its own parameters `FLT_DELAY` (s) and `FLT_MASK` (a motor bitmask), reports the average call period every 50 calls, and `FLT_DELAY` seconds after climbing above 8 m writes `SIM_ENGINE_MUL = 0` and `SIM_ENGINE_FAIL = FLT_MASK`, so the motors in the mask stop producing thrust, and it writes its own `FLT` message to the log. The script is for SITL only: a real vehicle has no `SIM_*` parameters, and `param:set` returns false.

```lua
-- fault_inject.lua (SITL only): N s after climbing above 8 m, cut thrust of the motors in FLT_MASK
local PARAM_KEY = 72
assert(param:add_table(PARAM_KEY, "FLT_", 2), "add_table failed")
assert(param:add_param(PARAM_KEY, 1, "DELAY", 5), "add DELAY failed")   -- s after passing 8 m
assert(param:add_param(PARAM_KEY, 2, "MASK", 1), "add MASK failed")     -- bitmask, 1 = motor 1
local t_above, fired = nil, false
local calls, t_last, dt_sum = 0, millis(), 0

function update()
  local now = millis()
  calls = calls + 1
  dt_sum = dt_sum + (now - t_last):tofloat()
  t_last = now
  if calls % 50 == 0 then
    gcs:send_text(6, string.format("FLT: 50 calls, mean period %.1f ms", dt_sum / 50))
    dt_sum = 0
  end
  local d = ahrs:get_relative_position_D_home()       -- metres, positive down
  if not fired and d and arming:is_armed() and -d > 8 then
    t_above = t_above or now
    if (now - t_above):tofloat() > param:get("FLT_DELAY") * 1000 then
      local mask = math.floor(param:get("FLT_MASK"))
      param:set("SIM_ENGINE_MUL", 0)
      param:set("SIM_ENGINE_FAIL", mask)
      gcs:send_text(2, string.format("FLT: motors mask %d cut at %.1f m", mask, -d))
      logger:write("FLT", "Alt,Mask", "fi", "m-", "0-", -d, mask)
      fired = true
    end
  end
  return update, 100
end

gcs:send_text(6, "FLT: loaded")
return update, 100
```

The Python harness does two runs. The first has an extra `scripts/bad.lua` that indexes `nil` on its third call, to show what one script's error does to arming. The second runs without it and without `-w`, as after an ordinary reboot of the vehicle (`SCR_ENABLE` comes from `lua.parm` in both runs); a takeoff to 15 m, a wait for the failure, 25 s of observation. Run it with `mkdir -p run/scripts && cp fault_inject.lua run/scripts/ && cd run && python3 ../lua_lab.py ~/ardupilot`.

```python
"""Lua lab: fault_inject.lua on a SITL hexa; run 1 adds a broken script to see what it does to arming.
Usage: python3 lua_lab.py ~/ardupilot   (run from a folder that holds scripts/fault_inject.lua)"""
import os, subprocess, sys, time
from pymavlink import mavutil

AP, DP = sys.argv[1], sys.argv[1] + "/Tools/autotest/default_params/"
open("lua.parm", "w").write("SCR_ENABLE 1\n")
open("scripts/bad.lua", "w").write(          # runtime error on the 3rd call
    "local n = 0\nfunction update() n = n + 1; if n == 3 then local t = nil; return t.x end\n"
    "  return update, 1000 end\nreturn update, 1000\n")


def start(wipe):
    sitl = subprocess.Popen([AP + "/build/sitl/bin/arducopter", "--model", "hexa", "--speedup", "5", *wipe,
                             "--defaults", DP + "copter.parm," + DP + "copter-hexa.parm,lua.parm",
                             "--home", "-35.363261,149.165230,584,353"],
                            stdout=open("sitl.out", "a"), stderr=subprocess.STDOUT)
    time.sleep(1)
    m = mavutil.mavlink_connection("tcp:127.0.0.1:5760"); m.wait_heartbeat()
    for msg_id in (33, 36):  # GLOBAL_POSITION_INT, SERVO_OUTPUT_RAW at 5 Hz
        m.mav.command_long_send(1, 1, mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0, msg_id, 200000, 0, 0, 0, 0, 0)
    return sitl, m


def wait(m, sec, until=None):  # print STATUSTEXT for sec simulated seconds or until a text appears
    t_end = None
    while True:
        r = m.recv_match(type=["STATUSTEXT", "GLOBAL_POSITION_INT", "SERVO_OUTPUT_RAW"], blocking=True)
        if r.get_type() == "GLOBAL_POSITION_INT":
            wait.t, wait.alt = r.time_boot_ms / 1000, r.relative_alt / 1000
            t_end = t_end or wait.t + sec
            if wait.t > t_end:
                return
        elif r.get_type() == "SERVO_OUTPUT_RAW":
            wait.pwm = [getattr(r, f"servo{i}_raw") for i in range(1, 7)]
        elif "50 calls" not in r.text or "50 calls" not in wait.seen:
            print(f"[{wait.t:6.1f} s] {r.text}")
            wait.seen += r.text
            if until and until in r.text:
                return


wait.t, wait.seen = 0, ""
print("--- run 1: fault_inject.lua + bad.lua")
sitl, m = start(["-w"])
wait(m, 45)
m.set_mode("GUIDED"); m.arducopter_arm()
ack = m.recv_match(type="COMMAND_ACK", condition="COMMAND_ACK.command==400", blocking=True)
print(f"arm: COMMAND_ACK result {ack.result} (0 = accepted, 4 = failed)")
wait(m, 2); sitl.terminate(); sitl.wait()
os.remove("scripts/bad.lua")
print("--- run 2: bad.lua removed, same eeprom.bin (no -w)")
sitl, m = start([])
wait(m, 45)
m.set_mode("GUIDED")
while not m.motors_armed():
    m.arducopter_arm(); m.recv_match(type="HEARTBEAT", blocking=True); m.recv_match(type="HEARTBEAT", blocking=True)
m.mav.command_long_send(1, 1, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, 15)
wait(m, 300, until="cut at")
print(f"PWM at the cut: {wait.pwm}")
t_cut, low = wait.t, 99
while wait.t < t_cut + 25:
    wait(m, 0.2); low = min(low, wait.alt)
print(f"25 s after the cut: lowest alt {low:.1f} m, PWM {wait.pwm}")
sitl.terminate()
```

Output of the run (2026-11-26; the time in square brackets is on the firmware clock, and after the restart the count starts over, so the first lines of the second run still carry the time of the first):

```text
--- run 1: fault_inject.lua + bad.lua
[   0.0 s] Barometer 1 calibration complete
[   0.0 s] Barometer 2 calibration complete
[   0.0 s] ArduPilot Ready
[   0.0 s] AHRS: DCM active
[   0.0 s] FLT: loaded
[   2.5 s] RC7: SaveWaypoint LOW
[   4.3 s] EKF3 IMU0 initialised
[   4.3 s] EKF3 IMU1 initialised
[   4.3 s] AHRS: EKF3 active
[   5.3 s] Lua: ./scripts/bad.lua:2: attempt to index a nil v
[   5.3 s] alue (local 't')
[   5.7 s] EKF3 IMU0 tilt alignment complete
[   5.7 s] EKF3 IMU1 tilt alignment complete
[   5.7 s] EKF3 IMU0 MAG0 initial yaw alignment complete
[   5.7 s] EKF3 IMU1 MAG0 initial yaw alignment complete
[   7.9 s] FLT: 50 calls, mean period 112.8 ms
[   9.7 s] GPS 1: probing for u-blox at 230400 baud
[   9.7 s] GPS 1: detected u-blox
[  15.5 s] Lua: ./scripts/bad.lua:2: attempt to index a nil v
[  15.5 s] alue (local 't')
[  19.9 s] EKF3 IMU0 origin set
[  19.9 s] Field Elevation Set: 584m
[  20.1 s] EKF3 IMU1 origin set
[  25.5 s] Lua: ./scripts/bad.lua:2: attempt to index a nil v
[  25.5 s] alue (local 't')
[  30.3 s] PreArm: Scripting: ./scripts/bad.lua:2: attempt to
[  30.3 s]  index a
[  35.5 s] Lua: ./scripts/bad.lua:2: attempt to index a nil v
[  35.5 s] alue (local 't')
[  41.5 s] EKF3 IMU0 is using GPS
[  41.5 s] EKF3 IMU1 is using GPS
[  45.5 s] Lua: ./scripts/bad.lua:2: attempt to index a nil v
[  45.5 s] alue (local 't')
arm: COMMAND_ACK result 4 (0 = accepted, 4 = failed)
[  47.7 s] Arm: Scripting: ./scripts/bad.lua:2: attempt to in
[  47.7 s] dex a
--- run 2: bad.lua removed, same eeprom.bin (no -w)
[  50.1 s] Barometer 1 calibration complete
[  50.1 s] Barometer 2 calibration complete
[  50.1 s] ArduPilot Ready
[  50.1 s] AHRS: DCM active
[  50.1 s] FLT: loaded
[   2.6 s] RC7: SaveWaypoint LOW
[   4.2 s] EKF3 IMU0 initialised
[   4.2 s] EKF3 IMU1 initialised
[   4.2 s] AHRS: EKF3 active
[   5.6 s] EKF3 IMU1 tilt alignment complete
[   5.6 s] EKF3 IMU0 tilt alignment complete
[   5.8 s] EKF3 IMU1 MAG0 initial yaw alignment complete
[   5.8 s] EKF3 IMU0 MAG0 initial yaw alignment complete
[   9.6 s] GPS 1: probing for u-blox at 230400 baud
[   9.6 s] GPS 1: detected u-blox
[  19.8 s] EKF3 IMU1 origin set
[  19.8 s] Field Elevation Set: 584m
[  20.0 s] EKF3 IMU0 origin set
[  41.4 s] EKF3 IMU0 is using GPS
[  41.4 s] EKF3 IMU1 is using GPS
[  53.2 s] EKF3 IMU0 MAG0 in-flight yaw alignment complete
[  53.2 s] EKF3 IMU1 MAG0 in-flight yaw alignment complete
[  60.4 s] FLT: motors mask 1 cut at 14.9 m
PWM at the cut: [1594, 1594, 1594, 1594, 1594, 1595]
[  63.6 s] Potential Thrust Loss (1)
[  84.6 s] SIM Hit ground at 1.578218 m/s
25 s after the cut: lowest alt -0.0 m, PWM [1950, 1207, 1862, 1915, 1913, 1864]
```

What to read in the output. First run: `fault_inject.lua` loaded (`FLT: loaded`) and is running, `bad.lua` failed on its third call (5.3 s), the error repeats every 10 s, arming is blocked (the `PreArm: Scripting` line arrived with the next report at 30.3 s), and the arming attempt was rejected with result 4. Second run: no errors, arming succeeded; at 14.9 m the script cut motor 1, and the PWM of all six motors at that moment was 1594–1595 µs. After 3 s the firmware reported `Potential Thrust Loss (1)`. In the PWM snapshot motor 1 is pinned at 1950 µs (commanded, but producing no thrust), the other four are at 1862–1915 µs, and motor 2, opposite to it (a Hexa Plus frame: `copter-hexa.parm` sets only `FRAME_CLASS 2`, and `FRAME_TYPE` 0 comes from `copter.parm`; motor 1 is the nose, 2 is the tail), is at 1207 µs: the controller is cancelling pitch and yaw. The snapshot was taken 25 s after the failure, already after touchdown; to see the picture in flight, capture the PWM 2–5 s after the failure. This hexa model did not hold altitude and touched the ground 24 s after the failure at 1.6 m/s: a soft landing, not a crash. The conclusion for a project: in this model a six-motor vehicle survives a motor failure as a controlled descent, not as a hover; to "fly on with a failure" you need thrust margin or eight motors (`ap-heavy`).

Self-check: the lab is done when in step 2 every flick of the switch gives exactly one `Scripting2 -> …` line; in step 3 `MOT_STOP_BITMASK` has appeared; step 5 passes `pytest` before and after your change; in step 6 the first run rejects arming with result 4 and the text `Scripting: ./scripts/bad.lua:2`, the second arms, reports `FLT: motors mask 1 cut at` at an altitude of 13–16 m (a takeoff to 15 m; 5 s after passing 8 m the vehicle is already at 15 m), the average call period is within 100–120 ms, and in the PWM snapshot after the failure motor 1 is at 1950 µs, at least one of the healthy motors is above 1850 µs, and motor 2 is below 1400 µs.

**Reference for the self-check.** Step 2: on every flick of the switch a `Scripting2 -> <position> (ARMED or disarmed)` line appears in the GCS messages; if you get `switch_report: no channel with RCx_OPTION=301` every 5 s instead, the switch is not assigned (`RC9_OPTION 301`) or SITL was not restarted. Step 3: after a reboot the `MOT_STOP_BITMASK` parameter has appeared; if it has not, the applet is not in `scripts/` or `SCR_ENABLE` is not 1. Step 5: `python -m pytest -q examples/lua-protection/tests` passes before and after your changes, and the third guard has its own test that fails if you remove its logic. Step 6, typical wrong results: (1) `FLT_DELAY` did not appear: the file is not in `scripts/`, or `SCR_ENABLE` was not 1 at startup (the parameter would take effect only after a restart); (2) the failure never happens: the vehicle did not climb above 8 m or is not armed, and the script waits for both conditions; (3) in the second run arming is rejected again: `bad.lua` is still in `scripts/`; (4) `FLT_DELAY` went back to 5 after your change: the second run was started with `-w`, which erased `eeprom.bin`.

## diagnostics
- **Symptom:** a script does not start and the GCS is silent
  - Possible cause: `SCR_ENABLE` is not set or there was no reboot, or the file is in the wrong folder.
  - What to do: check the parameter and the `scripts/` path relative to the folder SITL was started from.
- **Symptom:** a pre-arm error about script memory
  - Possible cause: `SCR_HEAP_SIZE` is too small for the loaded scripts.
  - What to do: raise `SCR_HEAP_SIZE` or remove scripts you do not need.
- **Symptom:** all scripts stopped working in the middle of a flight
  - Possible cause: the Lua engine died (`Lua: Engine Error …`, then `Scripting: stopped`) or scripting was restarted; an error in one script removes only that script.
  - What to do: read the GCS messages, fix the script, restart scripting (a reboot, `MAV_CMD_SCRIPTING`, `RCx_OPTION = 316`, `SCR_ENABLE` 0 → 1).
- **Symptom:** `find_channel_for_option` returns nil
  - Possible cause: no channel has the required `RCx_OPTION` assigned.
  - What to do: assign the option to a channel with a switch.
- **Symptom:** arming is rejected with `PreArm: Scripting: ./scripts/<name>.lua:<line>: …`
  - Possible cause: a script failed with a runtime error and was removed; the firmware will not let you fly without it.
  - What to do: fix the line from the message, then reboot or send `MAV_CMD_SCRIPTING` with `param1 = 3`; leave bit 4 of `SCR_DEBUG_OPTS` alone if the script is a safeguard.
  - In the log: the `Lua: …` message repeats in the GCS every 10 s (DEBUG severity, up to 10 times).
- **Symptom:** `add_table failed` when a script starts
  - Possible cause: the table key or the prefix is already taken by another script, or the prefix is longer than allowed.
  - What to do: give the script its own `param:add_table` key and a unique prefix; check `param show <prefix>*`.
- **Symptom:** a script is "slow": `return update, 100`, but it reacts noticeably less often
  - Possible cause: the delay is a minimum, not a period; many scripts or a heavy call stretch the queue.
  - What to do: measure the real period with `millis()` (≈ 113 ms for 100 ms in the run); do not do time-critical work in Lua.
- **Symptom:** a script does not start, "Lua: … out of memory"
  - Possible cause: `SCR_HEAP_SIZE` is too small, or the board has no spare RAM.
  - What to do: increase the heap (200–300 kB on an H7, a course guideline), check whether expansion is disabled with bit 6 of `SCR_DEBUG_OPTS`, simplify the script.
- **Symptom:** "<name>.lua exceeded time limit"
  - Possible cause: a heavy loop in a single update call.
  - What to do: split the work across calls; raise `SCR_VM_I_COUNT` with care.

## references
- Lua Scripts — ArduPilot | https://ardupilot.org/copter/docs/common-lua-scripts.html | primary | A
- Script Setup and Use Examples — ArduPilot | https://ardupilot.org/copter/docs/common-scripting-step-by-step.html | primary | A
- AP_Scripting applets (GitHub) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/AP_Scripting/applets | primary | A
- Lua bindings reference — docs/docs.lua, Copter-4.7.2 | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_Scripting/docs/docs.lua | primary | A
- SCR_* parameters — AP_Scripting.cpp, Copter-4.7.2 | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_Scripting/AP_Scripting.cpp | primary | A
- Script scheduler and error handling — lua_scripts.cpp, Copter-4.7.2 | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_Scripting/lua_scripts.cpp | primary | A

## checklist
- Scripting is enabled in SITL and a test script responds to a switch
- The motor failure applet is set up and tested on octa-quad
- Every chaos script is on its own switch
- I understand why an F405 (1 MB of flash) has no scripting
- Scripts that use `SIM_*` never go onto a real vehicle
- I know why a failed script blocks arming and how to restart it
- My script's own parameters are created through `param:add_table` with a unique prefix
