---
id: ap-sitl
title: "SITL: a drone without a drone"
level: L2
readingTime: 25 min
firmware: ArduPilot 4.5+
status: published
added: 2026-11-07
tags:
  - SITL
  - pymavlink
  - simulation
related:
  - ap-intro
  - ap-lua
next:
  - ap-missions
source: content/ardupilot/ap-sitl.md
source_hash: 7ac85e12824f
---

## summary
SITL (Software In The Loop) is the real ArduPilot firmware running on a computer instead of a flight controller, with a physics simulator instead of the real world. Here you can crash a hundred octocopters for free: mix up parameters, kill GPS in flight, drop a motor. This module shows how to bring up SITL, connect a ground station, control the drone with a Python script, and organize the project so that routes and scenarios live separately.

## theory
### How SITL works
The firmware is built for Linux and exchanges “sensor readings” and “motor commands” with the physics simulator. Everything else is real: the same parameters, modes, EKF, failsafes, logs. So everything you debugged in SITL carries over to hardware almost unchanged. Almost — because in simulation the vibrations are perfect, the link is perfect and GPS is honest, unless you break them yourself.

### sim_vehicle.py and MAVProxy
The `sim_vehicle.py` script builds the firmware, starts it and starts the MAVProxy console ground station. Key flags:

- `-v ArduCopter` or `-v ArduPlane` — vehicle type;
- `-f octa-quad`, `-f quad`, `-f quadplane` — frame model in the simulator;
- `--console --map` — console and map windows;
- `-w` — wipe parameters to defaults (useful when experiments went sideways).

A ground station (QGroundControl, Mission Planner) connects to the MAVProxy output over UDP — usually it finds it on its own.

### Scenario vs. route
The main architectural decision in the course project: the route and the scenario live separately.

- **Route** — only a sequence of points in a single format. The first point is the start, the last one is the finish.
- **Scenario** — only commands: takeoff, “fly route X”, landing, motor failure at the third waypoint. There are no coordinates in a scenario.

That way one route runs under different scenarios, and one scenario runs over different routes. It's the same idea as separating data and logic in any decent code.

### What SITL can do besides “just fly”
- **Frame models** (`-f`): quad, hexa, octa, octa-quad (X8), y6, tri, heli, plane, quadplane, quadplane-tilttri/quadplane-tilt (tiltrotors), rover, boat, sub — each has its own physics in `libraries/SITL/SIM_*.cpp`; default parameters for a model are in `Tools/autotest/default_params/*.parm`.
- **Failures and environment** via `SIM_*`: wind (`SIM_WIND_SPD/DIR/TURB`), motor failure (`SIM_ENGINE_FAIL` + `SIM_ENGINE_MUL`), GPS (disable, noise, glitch, lag), compass (offset), baro (drift/glitch), vibration (`SIM_VIB_*`), RC loss (`SIM_RC_FAIL`), battery voltage (`SIM_BATT_VOLTAGE`), rangefinder and optical flow (`RNGFND1_TYPE = 100`, `FLOW_TYPE = 10`). This is the foundation of the “Fault tolerance” and “Navigation resilience” modules.
- **Time acceleration** `--speedup 10` for long missions; `--add-param-file` for your own parameters; `--out=udp:IP:14550` for an external GCS; `--no-mavproxy` for scripts.
- **External physics engines**: Gazebo (`-f gazebo-iris`), RealFlight, X-Plane, JSBSim (wing), Webots — when you need aerodynamics/visualization; for failsafe and mission logic the built-in physics is enough.
- **Lua and companion**: scripts (`SCR_ENABLE = 1`, a `scripts/` folder next to where you launch) and MAVLink clients (`tcp:127.0.0.1:5760`, the next ones — 5762/5763) work just like on hardware.

### SITL logs and reading them
Logs are written to `logs/` in the working folder (`.BIN`) and are read with the same tools as real ones (`mavexplorer.py`, Mission Planner, `pymavlink` — the “Python for data” module). That is the whole point of SITL: practicing the analysis **method** before real flights.

### Worked example: testing a mission with a failure
`sim_vehicle.py -v ArduCopter -f hexa --console --map --speedup 5`; load the mission (`wp load mission.txt`), `mode auto`, `arm throttle`; at the third waypoint `param set SIM_ENGINE_FAIL 4` (motor 3, bitmask), watch `RCOU`, altitude, yaw; set it back to `0`; then `param set SIM_RC_FAIL 1` in Loiter — check `FS_THR_ENABLE`. The result goes into the test log (the “Fault tolerance” module): scenario, expectation, actual result, log. The scenario can be written as a pymavlink script — a template is in `examples/sitl-pymavlink` in the course repo.

### Where SITL lies
No vibration or motor noise (you can't test filters), perfect mechanics, ESCs without latency, GPS with a configured noise level, no compass interference except what is modeled. PID tuning parameters from SITL **do not carry over** to a real vehicle; what carries over is logic, missions, scripts, failsafes and analysis skills.

{{diagram:sitl-param-layers|Слои параметров SITL: файл defaults задаёт значения по умолчанию, но eeprom.bin их перебивает; -w стирает eeprom.bin, иначе правка .parm может не подействовать.}}

{{diagram:sitl-arch|SITL: the same ArduCopter code gets sensor data from a physics model; MAVProxy distributes MAVLink to the GCS and scripts, logs are written just like in flight.}}

## practice
### Step 1. Installation (Ubuntu)
```
git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git
cd ardupilot
Tools/environment_install/install-prereqs-ubuntu.sh -y
. ~/.profile
```

### Step 2. First run
```
sim_vehicle.py -v ArduCopter -f octa-quad --console --map -w
```

In the MAVProxy console:

```
mode guided
arm throttle
takeoff 10
```

The drone will take off to 10 m. `mode rtl` brings it back home.

### Step 3. Control from a script (pymavlink)
SITL opens additional TCP ports for external clients. An example of a takeoff from a script:

```python
from pymavlink import mavutil

master = mavutil.mavlink_connection("tcp:127.0.0.1:5762")
master.wait_heartbeat()
print("connected to system", master.target_system)

# Copter streams on SERIAL1 are off by default (MAV2_* = 0): ask for GLOBAL_POSITION_INT at 5 Hz
master.mav.command_long_send(
    master.target_system, master.target_component,
    mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
    mavutil.mavlink.MAVLINK_MSG_ID_GLOBAL_POSITION_INT, 200000, 0, 0, 0, 0, 0)

master.set_mode(master.mode_mapping()["GUIDED"])
while not master.motors_armed():      # PreArm refuses until the EKF uses GPS: retry
    master.arducopter_arm()
    master.recv_match(type="HEARTBEAT", blocking=True)
    master.recv_match(type="HEARTBEAT", blocking=True)

master.mav.command_long_send(
    master.target_system, master.target_component,
    mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
    0, 0, 0, 0, 0, 0, 0, 10,  # param7 = altitude, m
)

t0 = None
while True:
    msg = master.recv_match(type="GLOBAL_POSITION_INT", blocking=True)
    t0 = t0 or msg.time_boot_ms
    alt = msg.relative_alt / 1000
    if alt > 9.5:
        print(f"alt {alt:.1f} m after {(msg.time_boot_ms - t0) / 1000:.1f} s (sim time)")
        break
```

```text
connected to system 1
alt 9.5 m after 6.6 s (sim time)
```

### Step 4. Project structure
```
ardupilot-lab/
  sitl/
    lib/          # shared code: connection, waiting for modes, helpers
    routes/       # data only: lists of waypoints, one format everywhere
    scenarios/    # commands only: takeoff, fly route X, inject failure, land
    run_sitl.sh   # start SITL + GCS with the right frame
```

### What you should get and what to record
- **Step 1.** Installation takes 10–30 minutes. After it, the `sim_vehicle.py` command should be found in a new terminal. If it isn't, `~/.profile` hasn't been re-read.
- **Step 2.** The first build takes a few minutes, later runs take seconds. In the console you can see GPS getting a fix and the EKF starting to use GPS; after that, arming goes through. Arming before that point is rejected with a `PreArm` message, and that's normal. `takeoff 10` lifts the vehicle to 10 m. After `mode rtl` it first climbs to the return altitude `RTL_ALT` (in Copter 4.7 — `RTL_ALT_M`; 15 m by default) if it is below it, and only then flies home. Record the time to climb to 10 m and the final altitude before the return: that's how you check that the parameters work the way you think they do.
- **Step 3.** SITL ports: 5760 is SERIAL0, taken by MAVProxy; 5762 and 5763 are SERIAL1 and SERIAL2 for your own clients. The script prints the rising altitude and exits at 9.5 m — but only if `GLOBAL_POSITION_INT` is actually being sent to that port. On Copter, streams on SERIAL1 are off by default (`SR1_POSITION = 0`, in 4.7 — `MAV2_POSITION`), so request the message with `MAV_CMD_SET_MESSAGE_INTERVAL` before the loop, otherwise `recv_match` will wait forever. Add output of the time from the command to the exit — that's the first metric of your scenario.
- **Step 4.** The route is data, the scenario is code. An example route `routes/square_20m.csv`, rows `north_m,east_m,alt_m` relative to the takeoff point:

```text
20,0,10
20,20,10
0,20,10
0,0,10
```

The scenario reads the file, converts the offsets into GUIDED targets and waits until the vehicle is within a 1 m radius. A second route is the same format with different numbers.

### Lab
Write a “takeoff → loop → landing” scenario so that the coordinates live in `routes/` and the scenario just references a route. Run it on two different routes without editing the scenario code.

The lab counts as done when SITL starts from the `run_sitl.sh` script with the right frame and the ground station is connected, the pymavlink scenario takes off, flies the route and lands, the routes live in `routes/` separately from the scenarios, and two routes have been run by the same code with the completion time recorded.

SITL run of this step (ArduCopter 4.7.2); walkthrough and expected output are in the Russian source.

```
build/sitl/bin/arducopter --model + --speedup 10 -w \
  --defaults Tools/autotest/default_params/copter.parm,lab.parm \
  --home -35.363261,149.165230,584,353
```

```python
"""SITL lab: layered defaults, speedup, wind and RC-loss injection (ArduCopter 4.7.2, no MAVProxy).
Usage: python3 sitl_lab.py ~/ardupilot   (run from an empty folder; logs/ and eeprom.bin appear here)"""
import math, subprocess, sys, time
from pymavlink import mavutil

AP = sys.argv[1]
open("lab.parm", "w").write("RTL_ALT_M 20\n")          # applied after copter.parm, so it wins
sitl = subprocess.Popen([AP + "/build/sitl/bin/arducopter", "--model", "+", "--speedup", "10", "-w",
                         "--defaults", AP + "/Tools/autotest/default_params/copter.parm,lab.parm",
                         "--home", "-35.363261,149.165230,584,353"], stdout=open("sitl.out", "w"), stderr=subprocess.STDOUT)
time.sleep(1)
m = mavutil.mavlink_connection("tcp:127.0.0.1:5760")   # SERIAL0 waits for this client
m.wait_heartbeat()
for name in ("GLOBAL_POSITION_INT", "ATTITUDE", "LOCAL_POSITION_NED"):   # 10 Hz each
    m.mav.command_long_send(1, 1, mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
                            getattr(mavutil.mavlink, "MAVLINK_MSG_ID_" + name), 100000, 0, 0, 0, 0, 0)


def param(name, value=None):
    if value is None:
        m.mav.param_request_read_send(1, 1, name.encode(), -1)
    else:
        m.param_set_send(name, value)
    while (r := m.recv_match(type="PARAM_VALUE", blocking=True)).param_id != name:
        pass
    return r.param_value


def sim_t():  # simulated seconds since boot, from a fresh message
    while m.recv_match(blocking=False):
        pass
    return m.recv_match(type="GLOBAL_POSITION_INT", blocking=True).time_boot_ms / 1000


def fly_until(test):  # read messages until test(msg) is true, return that message
    while not test(r := m.recv_match(blocking=True)):
        pass
    return r


def takeoff(alt):
    m.set_mode("GUIDED")
    while not m.motors_armed():      # PreArm refuses until the EKF uses GPS
        m.arducopter_arm()
        m.recv_match(type="HEARTBEAT", blocking=True); m.recv_match(type="HEARTBEAT", blocking=True)
    m.mav.command_long_send(1, 1, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, alt)
    fly_until(lambda r: r.get_type() == "GLOBAL_POSITION_INT" and r.relative_alt > (alt - 0.5) * 1000)


def mean_tilt(sec):
    t_end, tilt = sim_t() + sec, []
    while (r := m.recv_match(type=["ATTITUDE", "GLOBAL_POSITION_INT"], blocking=True)).time_boot_ms / 1000 < t_end:
        if r.get_type() == "ATTITUDE":
            tilt.append(math.degrees(math.hypot(r.roll, r.pitch)))
    return sum(tilt) / len(tilt)


def rtl_max_alt():  # watch RTL until disarm, return the highest altitude
    top = 0
    while (r := m.recv_match(type=["GLOBAL_POSITION_INT", "HEARTBEAT"], blocking=True)):
        if r.get_type() == "GLOBAL_POSITION_INT":
            top = max(top, r.relative_alt / 1000)
        elif r.get_srcSystem() == 1 and not r.base_mode & 128 and top > 1:
            return top


for n in ("FS_THR_ENABLE", "RC_FS_TIMEOUT", "RTL_ALT_M", "RTL_CONE_SLOPE", "SIM_WIND_DIR", "SIM_GPS1_ENABLE"):
    print(f"{n} = {param(n):g}")
t0, w0 = sim_t(), time.time(); time.sleep(10)
print(f"speedup: {(sim_t() - t0) / (time.time() - w0):.1f}x")
takeoff(10)
print(f"airborne at sim t = {sim_t():.0f} s; calm: mean tilt {mean_tilt(10):.1f} deg")
param("SIM_WIND_DIR", 0); param("SIM_WIND_SPD", 8)                  # 8 m/s FROM the north
mean_tilt(5)                                                         # let the controller settle
print(f"wind 8 m/s: mean tilt {mean_tilt(15):.1f} deg")
param("SIM_WIND_SPD", 0)
m.set_mode("RTL")
print(f"A: RTL straight above home -> max alt {rtl_max_alt():.1f} m")
takeoff(10)
m.mav.set_position_target_local_ned_send(0, 1, 1, mavutil.mavlink.MAV_FRAME_LOCAL_NED, 0b110111111000,
                                         40, 0, -10, 0, 0, 0, 0, 0, 0, 0, 0)
pos = fly_until(lambda r: r.get_type() == "LOCAL_POSITION_NED" and abs(r.x - 40) < 1 and abs(r.vx) < 0.3)
t_fail = sim_t(); param("SIM_RC_FAIL", 1)
fly_until(lambda r: r.get_type() == "HEARTBEAT" and r.get_srcSystem() == 1 and r.custom_mode == 6)
print(f"B: {pos.x:.1f} m north, SIM_RC_FAIL=1 -> RTL after {sim_t() - t_fail:.1f} s, max alt {rtl_max_alt():.1f} m")
sitl.terminate()
```

```text
FS_THR_ENABLE = 1
RC_FS_TIMEOUT = 1
RTL_ALT_M = 20
RTL_CONE_SLOPE = 3
SIM_WIND_DIR = 180
SIM_GPS1_ENABLE = 1
speedup: 10.0x
airborne at sim t = 112 s; calm: mean tilt 0.3 deg
wind 8 m/s: mean tilt 6.5 deg
A: RTL straight above home -> max alt 10.0 m
B: 40.7 m north, SIM_RC_FAIL=1 -> RTL after 1.1 s, max alt 20.0 m
```


## diagnostics
- **Symptom:** `sim_vehicle.py: command not found`
  - Possible cause: the profile wasn't re-read after installation.
  - What to do: `. ~/.profile` or open a new terminal.
- **Symptom:** the script hangs on `wait_heartbeat`
  - Possible cause: wrong address or port, SITL isn't running.
  - What to do: check that SITL is running, and check the port number.
- **Symptom:** `arm throttle` is refused with `PreArm`
  - Possible cause: the EKF hasn't converged yet after startup.
  - What to do: wait 10–20 s after launch, read the PreArm message.
- **Symptom:** after experiments the drone behaves strangely
  - Possible cause: changed parameters are still in place.
  - What to do: restart with `-w` to reset them.
- **Symptom:** sim_vehicle.py won't start / “waf configure” errors
  - Possible cause: dependencies aren't installed.
  - What to do: `Tools/environment_install/install-prereqs-ubuntu.sh -y`, log out and back in, `git submodule update --init --recursive`.
- **Symptom:** the GCS won't connect to SITL
  - Possible cause: ports are busy, MAVProxy isn't forwarding.
  - What to do: pass `--out=udp:127.0.0.1:14550` explicitly, check `ss -lunp`.

## references
- Setting up SITL on Linux — ArduPilot Dev | https://ardupilot.org/dev/docs/setting-up-sitl-on-linux.html | primary | A
- Setting Up SITL — ArduPilot Dev | https://ardupilot.org/dev/docs/SITL-setup-landingpage.html | primary | A
- pymavlink — source code (GitHub) | https://github.com/ArduPilot/pymavlink | primary | A

## checklist
- SITL starts, the GCS is connected
- Takeoff and RTL done from the MAVProxy console
- A pymavlink script lifts the drone
- Routes and scenarios are kept in separate folders
- I know how to reset SITL parameters
