---
id: ap-lua
title: "Lua: Scripts and Fault Injection"
level: L3
readingTime: 25 min
firmware: ArduPilot 4.5+
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
source_hash: 2f6f17b88f3d
---

## summary
ArduPilot can run Lua scripts right on the flight controller: add modes, read sensors, react to switches. In a training project the main use is fault injection: deliberately breaking a motor or sensor in SITL and watching how the drone and you cope. This module explains how scripting works, how to bind a script to a radio switch, and how to build a set of “chaos scripts,” each on its own switch.

## theory
### How scripting works
- Enabled with the `SCR_ENABLE = 1` parameter and a reboot.
- Scripts (`.lua`) live in `APM/scripts` on the SD card; in SITL — in the `scripts` folder in the directory the simulator was launched from.
- Each script runs in its own “sandbox” at low priority: flight code comes first, and nobody promises the script an exact schedule.
- Script memory is set by `SCR_HEAP_SIZE`. Too little — scripts crash and a pre-arm error about insufficient memory appears. Too much — the EKF may fail to initialize.
- If one script crashes with an error, only that script stops. If the shared script memory runs out (or there's a panic), all scripts stop until a reboot.
- Scripting requires at least 2 MB of flash and doesn't work on F4 controllers.

### The update() pattern
A script is an `update()` function that does its work and returns itself and a delay in milliseconds until the next call. No infinite loops: the scheduler calls the function again on its own.

### Binding to a switch
The `RCx_OPTION` parameter assigns a function to a radio channel. Values 300–307 are Scripting1…Scripting8: reserved for scripts. A script finds its channel via `rc:find_channel_for_option(300)` and reads the switch position via `get_aux_switch_pos()` (0 — low, 1 — middle, 2 — high).

### Applets and examples
The ArduPilot repository has ready-made scripts: `libraries/AP_Scripting/applets` (ready to use, each with an `.md` description) and `libraries/AP_Scripting/examples` (learning examples). Start with the `motor_failure_test.lua` applet: it stops the motors set by the `MOT_STOP_BITMASK` bitmask when the Scripting1 switch is high. An octocopter should keep flying with one failed motor.

### What the API can do (per `docs/docs.lua` in AP_Scripting)
Reading state: `ahrs:get_position()`, `ahrs:get_velocity_NED()`, `ahrs:get_yaw()`, `gps:num_sats()`, `battery:voltage()`, `rangefinder:distance_orient()` (in meters; `distance_cm_orient` is deprecated), `esc_telem:get_rpm()`, `vehicle:get_mode()`, `arming:is_armed()`; actions: `vehicle:set_mode()`, `vehicle:set_target_velocity_NED()`, `vehicle:set_target_location()`, `mission:set_current_cmd()`, `SRV_Channels:set_output_pwm()`, `relay:on()`, `param:set()`/`param:add_param()` (your own parameters with a prefix), `gcs:send_text()`, `logger:write()` (your own log messages!), `notify:play_tune()`, `rc:get_aux_cached()` (switch `RCx_OPTION = 300..307` Scripting1..8), `serial:find_serial()` (your own protocol on a UART), `CAN:get_device()` (DroneCAN), `periph` on AP_Periph. Timers — return `update, 100` (ms until the next call). Scripting parameters: `SCR_ENABLE`, `SCR_HEAP_SIZE` (memory; F4 doesn't have enough → only H7/F7 with headroom), `SCR_VM_I_COUNT` (instruction limit per call — protection against hangs), `SCR_DEBUG_OPTS`.

### Applets as a textbook
`libraries/AP_Scripting/applets/` — ready-made, with an `.md` description: `motor_failure_test.lua` (stops motors per the `MOT_STOP_BITMASK` bitmask with the Scripting1 switch — a motor-failure test on a hexa/X8 in SITL and in the field), `VTOL-quicktune.lua` (QuikTune for multicopters and VTOL), `rover-quicktune.lua`, `copter-deadreckon-home.lua` (dead-reckoning return on GPS loss), `arming-checks.lua` (your own pre-arm checks), `ahrs-source-extnav-optflow.lua` (switching EKF sources by quality), `BattEstimate.lua`, `MissionSelector.lua`, `net_webserver.lua`, `crsf-calibrate.lua`, `SmartAudio.lua`. Reading them is the best way to learn the API and the style (defensive checks, `pcall`-like wrappers, parameters via `param:add_table`).

### Worked example: ESC temperature guard
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
Testing in SITL: `SIM_ESC_TELEM = 1`, temporarily set the threshold to 30 °C, make sure it triggers; then — on the test bench. Record it in the FMEA as a mitigation with a reference to the test (the “Fault Tolerance” module).

{{diagram:lua-script-lifecycle|Скрипт перепланируется, пока update() возвращает функцию и задержку; любая ошибка снимает его до перезагрузки и блокирует арм через PreArm: Scripting.}}

{{diagram:lua-runtime|How a script runs: a file from APM/scripts/ goes into the Lua VM, update() returns itself and the period, pcall catches errors, actions go through API bindings.}}

## practice
### Step 1. Enable scripting in SITL
```
param set SCR_ENABLE 1
reboot
```

### Step 2. An indicator script on a switch
A minimal script: reports Scripting2 switch position changes and the arming state to the GCS.

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

Put the file in `scripts/`, assign a switch (`param set RC9_OPTION 301`), restart SITL, and flip the switch a few times.

### Step 3. Motor failure on a switch
1. Copy the `motor_failure_test.lua` applet into `scripts/`.
2. Assign a switch to Scripting1: `RCx_OPTION = 300`.
3. After a reboot, `MOT_STOP_BITMASK` appears. Set it to 1 — motor 1 will be cut.
4. In SITL with the `octa-quad` frame: takeoff, LOITER, switch high. Watch how the drone compensates for the failure.

### Step 4. A set of chaos scripts
The idea of the training set: each “failure” is a separate script on its own switch, so you can enable them independently:

- an arming indicator (LED or message);
- a manual motor failure (the applet);
- random sensor failures via the `SIM_*` simulator parameters;
- a random failure of 1–3 motors.

`SIM_*` parameter names change between versions — check the current ones in your build with `param show SIM_GPS*` in MAVProxy. Such scripts are SITL-only: a real aircraft has no `SIM_*` parameters.

### Step 5. A guard with tests before SITL
The project #11 starter `examples/lua-protection`: `guard.lua` — a vibration guard (LAND), keeping inside a polygon with a margin (RTL), and a `pcall` wrapper that sends the aircraft to RTL after three consecutive errors in the air. The tests run **the same** Lua file via `lupa` against a stub of the bindings (`millis`, `ahrs`, `vehicle`, `param`, `gcs`, `logger`) — logic errors are caught in a fraction of a second, and SITL remains the acceptance test. Run `python -m pytest -q examples/lua-protection/tests`, then add a third guard (for example, voltage sag under load) together with a test.

SITL run of this step (ArduCopter 4.7.2); walkthrough and expected output are in the Russian source.

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


## diagnostics
- **Symptom:** the script doesn't start, silence in the GCS
  - Possible cause: `SCR_ENABLE` isn't enabled or there was no reboot, the file is in the wrong folder.
  - What to do: check the parameter and the `scripts/` path relative to the SITL launch folder.
- **Symptom:** a pre-arm error about script memory
  - Possible cause: `SCR_HEAP_SIZE` is too small for the loaded scripts.
  - What to do: raise `SCR_HEAP_SIZE` or remove unneeded scripts.
- **Symptom:** all scripts stopped working mid-flight
  - Possible cause: one script crashed with an error or exhausted the memory.
  - What to do: read the messages in the GCS, fix the script, reboot.
- **Symptom:** `find_channel_for_option` returns nil
  - Possible cause: no channel is assigned the required `RCx_OPTION`.
  - What to do: assign the option to a channel with a switch.
- **Symptom:** the script doesn't start, “Lua: … out of memory”
  - Possible cause: `SCR_HEAP_SIZE` is small, the board has no RAM headroom.
  - What to do: increase the heap (H7 — 200–300 KB), simplify the script.
- **Symptom:** “<name>.lua exceeded time limit”
  - Possible cause: a heavy loop in a single update call.
  - What to do: split the work across calls, raise `SCR_VM_I_COUNT` carefully.

## references
- Lua Scripts — ArduPilot | https://ardupilot.org/copter/docs/common-lua-scripts.html | primary | A
- Script Setup and Use Examples — ArduPilot | https://ardupilot.org/copter/docs/common-scripting-step-by-step.html | primary | A
- AP_Scripting applets (GitHub) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/AP_Scripting/applets | primary | A

## checklist
- Scripting is enabled in SITL, the test script responds to a switch
- The motor-failure applet is set up and tested on an octa-quad
- Each chaos script is on its own switch
- I understand why F4 has no scripting
- Scripts using `SIM_*` never end up on a real aircraft
