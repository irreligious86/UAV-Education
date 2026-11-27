---
id: ap-sitl
title: "SITL: a drone without a drone"
level: L2
readingTime: 35 min
firmware: ArduPilot 4.7 (checked against 4.7.3; the lab was captured on SITL 4.7.2)
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
source_hash: cbf268837ab4
---

## summary
SITL (Software In The Loop) is the real ArduPilot firmware running on a computer instead of a flight controller, with a physics simulator in place of the real world. Here you can crash a hundred octocopters for free: mix up parameters, turn off GPS in flight, lose a motor. This module shows how to bring up SITL, connect a ground station, control the drone from a Python script, and organize a project so that routes and scenarios live separately.

## theory
### How SITL works
The firmware is built for Linux and exchanges "sensor readings" and "motor commands" with a physics simulator. Everything else is real: the same parameters, modes, EKF, failsafes, and logs. So whatever you debug in SITL carries over to hardware almost unchanged. Almost, because the simulation has ideal vibration, an ideal link, and an honest GPS unless you degrade them yourself.

Technically SITL is a single process: the `build/sitl/bin/arducopter` binary (built with `./waf configure --board sitl && ./waf copter`) contains both the firmware and a built-in vehicle model selected with `--model`. The model and the firmware step on a shared clock (lockstep): the model computes physics at `SIM_RATE_HZ` (1200 Hz by default on SITL, `libraries/SITL/SITL.cpp:47`), and the firmware runs its main loop at `SCHED_LOOP_RATE` (400 Hz on Copter) on the same simulated clock: roughly three physics steps per firmware loop. The firmware reads the model's "sensors" and outputs PWM to the motors, and the model turns the PWM into thrust. Hence the key property: time in SITL is **simulated**. You can speed it up, and then a minute of flight passes in 6 seconds, but only if the computer can keep up.

### Starting it: sim_vehicle.py or the binary directly
`sim_vehicle.py` is a Python wrapper: it builds the firmware, picks the parameter files for the frame, and starts the binary and MAVProxy. For the `-f octa-quad` frame it passes `--defaults copter.parm,copter-octaquad.parm` to the binary (the frame table is `Tools/autotest/pysim/vehicleinfo.py`), for `-f hexa` it passes `copter.parm,copter-hexa.parm`, and for `+`/`quad` only `copter.parm`. The default start location is the CMAC airfield in Canberra: `SIM_OPOS_LAT/LNG/ALT` = −35.363261, 149.165230, 584 m, the same as the `CMAC` line in `Tools/autotest/locations.txt` (`-35.363261,149.165230,584,353`: latitude, longitude, altitude above mean sea level in meters, heading in degrees). For a different location use `-L <name>` from the same file, or `--home lat,lon,alt,hdg` with the binary.

For automated tests and CI it is more convenient to start the binary directly, without MAVProxy: fewer processes, full control over the flags, and your pymavlink script becomes the ground station. The command used in this module's practice:

```
build/sitl/bin/arducopter --model + --speedup 10 -w \
  --defaults Tools/autotest/default_params/copter.parm,lab.parm \
  --home -35.363261,149.165230,584,353
```

### Parameter layers: what overrides what
A parameter in SITL gets its value from four layers, and almost every "oddity" of the simulator is a forgotten layer.

1. The default value in the firmware code (`AP_GROUPINFO`).
2. The `--defaults` files from left to right: each one overrides the previous. `sim_vehicle.py --add-param-file my.parm` appends a file to the end of that list.
3. The saved values in `eeprom.bin` in the working folder: everything you changed with `param set` is stored there and **overrides** the defaults on the next start.
4. `param set` in the current session, which is written to layer 3 immediately.

The `-w` (`--wipe`) flag erases `eeprom.bin` at startup, and then only layers 1–2 apply. What follows from this order: if you edit `lab.parm` and the value does not change, `eeprom.bin` holds the old one, so start with `-w` or delete the file. And the other way around: to keep settings between runs (as in the Lua lab below), start without `-w` from the same folder.

{{diagram:sitl-param-layers|SITL parameter layers: the defaults file sets the default values, but eeprom.bin overrides them; -w erases eeprom.bin, otherwise an edit to the .parm file may have no effect.}}

### Ports and multiple vehicles
The firmware's serial ports are TCP sockets in SITL (`libraries/AP_HAL_SITL/SITL_State.h:33`): SERIAL0 is `tcp:0:wait`, port 5760, and the firmware **waits** for a client on it before starting; SERIAL1 is 5762, SERIAL2 is 5763; SERIAL3 and SERIAL4 are taken by the simulated GPS1/GPS2; SERIAL5…SERIAL8 are 5765…5768. The `-I N` (`--instance`) flag shifts the base port by 10·N (`SITL_cmdline.cpp:438`): a second vehicle with `-I 1` listens on 5770, 5772, 5773. That is how you bring up a swarm of 2–3 vehicles on one machine (`sim_vehicle.py -n 3` does it for you). MAVProxy holds 5760 and forwards the stream over UDP (`--out=udp:IP:14550`); without MAVProxy your script connects to 5760.

### Time and speedup
`--speedup N` writes the `SIM_SPEEDUP` parameter (1 by default). In the practice run at `--speedup 10`, 101 s of simulated time passed in 10.1 s of real time, exactly 10×. The rule for scripts: measure every interval and timeout in firmware time (`time_boot_ms` in `SYSTEM_TIME` and `GLOBAL_POSITION_INT`), not in the computer's `time.time()`. A "wait 20 s" scenario written as `time.sleep(20)` waits 200 simulated seconds at a 10× speedup. If the computer cannot keep up, the real speedup is lower than the one requested, which is why it is worth measuring, as in step 5.

### sim_vehicle.py and MAVProxy
The `sim_vehicle.py` script builds the firmware and starts it together with MAVProxy, a console ground station. The key flags:

- `-v ArduCopter` or `-v ArduPlane`: the vehicle type;
- `-f octa-quad`, `-f quad`, `-f quadplane`: the frame model in the simulator (`-f quad`, and a start without `-f`, is a Quad Plus, `FRAME_TYPE = 0`; a Quad X is `-f X`);
- `--console --map`: the console and map windows;
- `-w`: reset the parameters to defaults (useful when experiments have gone astray).

You connect a ground station (QGroundControl, Mission Planner) to the MAVProxy output over UDP; it usually finds it by itself.

### Scenario versus route
The main architectural decision in a training project (a course guideline): the route and the scenario live separately.

- **A route** is only a sequence of points in one format. The first point is the start, the last is the finish.
- **A scenario** is only commands: take off, "fly route X", land, a motor failure at the third point. There are no coordinates in a scenario.

That way one route runs under different scenarios, and one scenario runs over different routes. It is the same idea as separating data from logic in any decent code.

### What SITL can do besides "fly around"
- **Frame models** (`-f`): quad, hexa, octa, octa-quad (X8), y6, tri, heli, plane, quadplane, quadplane-tilttri/quadplane-tilt (tiltrotors), rover, motorboat, sailboat (Rover), vectored (Sub); each has its own physics in `libraries/SITL/SIM_*.cpp`, and the default parameters for a model are in `Tools/autotest/default_params/*.parm`.
- **Failures and environment** through `SIM_*`: wind (`SIM_WIND_SPD/DIR/TURB`), motor failure (`SIM_ENGINE_FAIL` + `SIM_ENGINE_MUL`), GPS (disable, noise, glitch, lag), compass (offset), baro (drift, glitch), vibration (`SIM_VIB_*`), RC loss (`SIM_RC_FAIL`), battery voltage (`SIM_BATT_VOLTAGE`), a rangefinder and optical flow (`RNGFND1_TYPE = 100`, `FLOW_TYPE = 10`). This is the basis of the "Fault tolerance" and "Navigation resilience" modules.
- **Time speedup** with `--speedup 10` for long missions; `--add-param-file` for your own parameters; `--out=udp:IP:14550` for an external GCS; `--no-mavproxy` for scripts.
- **External physics engines**: Gazebo (`-f gazebo-iris`), RealFlight, X-Plane, JSBSim (fixed wing), Webots, for when you need aerodynamics or visualization; for failsafe logic and missions the built-in physics is enough.
- **Lua and companion computers**: scripts (`SCR_ENABLE = 1`, a `scripts/` folder next to where you start it) and MAVLink clients (`tcp:127.0.0.1:5760`, then 5762/5763) work as they do on hardware.

{{lesson:ap-lua|Fault injection from a script: a motor failure on a timer or a switch through the same SIM_ENGINE_FAIL/SIM_ENGINE_MUL.}}

### Reference: startup flags and SIM_* parameters (ArduCopter 4.7.2)
The names and defaults are checked against the source of the Copter-4.7.2 tag: the flags in `libraries/AP_HAL_SITL/SITL_cmdline.cpp:327–386` and `Tools/autotest/sim_vehicle.py`, the parameters in `libraries/SITL/SITL.cpp` and `libraries/SITL/SIM_GPS.cpp`. In MAVProxy, `param show SIM_*` gives the full list for your build.

| Flag / parameter | Default | What it does | How to use it |
|---|---|---|---|
| `--model` (binary), `-f` (sim_vehicle) | — | the frame model: `+`, `X`, `hexa`, `octa-quad`, `quadplane`… | `-f` also picks the `--defaults` files |
| `--defaults a.parm,b.parm` | — | default values; the file on the right overrides the one on the left | your own `lab.parm` at the end of the list |
| `-w` / `--wipe` | off | erase `eeprom.bin` at startup | an edit to a `.parm` file had no effect: start with `-w` |
| `--speedup N` (binary: `-s N`; sim_vehicle.py: `-S N`) | 1 | writes `SIM_SPEEDUP` | 10 for long missions; measure the real value |
| `--home lat,lon,alt,hdg`, `-L name` | CMAC | the start location | your own site for missions |
| `-I N` / `--instance` | 0 | base port + 10·N | multiple vehicles |
| `SIM_WIND_SPD`, m/s | 0 | wind speed | 5–10 m/s to test position hold |
| `SIM_WIND_DIR`, ° | 180 | the direction the wind is coming from | 0 is from the north |
| `SIM_WIND_TURB`, m/s | 0 | turbulence | 2–3 m/s on top of the wind |
| `SIM_ENGINE_FAIL` | 0 | motor bitmask: bit 0 is motor 1 | 1 → motor 1, 4 → motor 3 |
| `SIM_ENGINE_MUL` | 0 | thrust multiplier for the motors in the mask, 0…1 | 0 is a complete failure, 0.5 is half thrust |
| `SIM_RC_FAIL` | 0 | 0 normal, 1 no RC pulses, 2 all channels neutral with throttle at 950 µs | testing `FS_THR_ENABLE` |
| `SIM_GPS1_ENABLE` | 1 (see below) | 0 makes GPS1 disappear | GPS loss in flight |
| `SIM_GPS1_NUMSATS` | 10 | number of satellites | 5 is below the arming threshold |
| `SIM_GPS1_GLTCH_X/Y/Z` | 0 | a GPS position jump | testing the EKF reaction to a glitch |
| `SIM_GPS1_LAG_MS`, ms | 100 | GPS lag | |
| `SIM_BATT_VOLTAGE`, V | 12.6 | voltage of the battery model | testing `BATT_FS_*` |
| `SIM_VIB_FREQ_X/Y/Z`, Hz | 0 | sinusoidal IMU vibration | testing filters on the shape, not on the numbers |
| `SIM_ESC_TELEM` | 1 | ESC telemetry in the model | for the Lua `esc_telem:*` bindings |
| `SIM_RATE_HZ`, Hz | 1200 | physics step rate | leave it alone without a reason |

Note: in the parameter table `SIM_GPS1_ENABLE` defaults to 0, but the GPS simulator itself sets 1 for the first receiver if the parameter is not configured explicitly (`libraries/SITL/SIM_GPS.cpp:177`); in the step 5 output it reads as 1.

### A trap that SITL reveals: the RTL cone
Copter does not always climb to `RTL_ALT_M` before returning. The code in `ArduCopter/mode_rtl.cpp:546–555` computes the return altitude like this (`RTL_CLIMB_MIN_M = 0`, the default):

h_ret = min( max(`RTL_ALT_M`, h), max(d · `RTL_CONE_SLOPE`, h) ),

where h is the current altitude, d is the horizontal distance to home, and `RTL_CONE_SLOPE` = 3 by default (below 0.5 the cone is disabled). Directly above home d = 0 and h_ret = h: a vehicle at 10 m does not climb to 20 m; it loiters above home for `RTL_LOIT_TIME` (5000 ms by default) and lands from its current altitude. At 40.7 m from home the cone gives 122 m, `RTL_ALT_M` = 20 limits it, and the vehicle climbs to 20 m. Both cases are run in step 5. Before Copter 4.7 the parameter was called `RTL_ALT` and was set in centimeters.

### SITL logs and reading them
Logs are written to `logs/` in the working folder (`.BIN`) and are read with the same tools as real ones (`mavexplorer.py`, Mission Planner, `pymavlink`; see the "Python for data" module). That is the point of SITL: to practice the **method** of analysis before real flights.

### Worked example: testing a mission with a failure
`sim_vehicle.py -v ArduCopter -f hexa --console --map --speedup 5`; load the mission (`wp load mission.txt`), `mode auto`, `arm throttle`; at the third waypoint `param set SIM_ENGINE_FAIL 4` (motor 3, a bitmask) and watch `RCOU`, the altitude, and the yaw; set it back to `0`; then `param set SIM_RC_FAIL 1` in Loiter to test `FS_THR_ENABLE`. The result goes into the test log (see the "Fault tolerance" module): scenario, expectation, actual result, log. You can write the scenario as a pymavlink script; a starting point is in `examples/sitl-pymavlink` in the course repository.

### Where SITL lies
There is no vibration or motor noise until you enable it through `SIM_VIB_*`, and even then it is a sine wave at a set frequency, not the spectrum of your frame (you cannot tune filters in SITL); the mechanics are ideal, the ESCs have no delay, the GPS has the noise you specify, and the compass sees no interference except what is modeled. PID tuning parameters from SITL do **not carry over** to a real vehicle; logic, missions, scripts, failsafes, and analysis skills do.

{{diagram:sitl-arch|SITL: the same ArduCopter code gets its sensors from a physics model; MAVProxy forwards MAVLink to the GCS and to scripts, and logs are written as in flight.}}

### Place in the system

- **Receives:** the same firmware, parameters, and mission file (`ap-missions`); Lua scripts (`ap-lua`) and companion MAVLink clients (`ap-companion`); external physics and cameras when needed (`tools-gazebo`).
- **Provides:** tested failsafe logic and a test log (`ap-safety-fs`); `.BIN` logs for practicing the method of analysis (`ap-logs`, `data-python`); an automated test for CI (`eng-ci-configs`).
- **If you get it wrong here:** you carried PIDs and filters from SITL over to a real vehicle → the simulation has no vibration or motor noise, so the values do not fit; tuning is done from real logs (`ap-tuning`). You did not degrade the GPS and the link yourself → the failsafe "passed" on ideal sensors, while in the field degradation looks different (`nav-resilience`).

## practice
### Step 1. Installation (Ubuntu)
```
git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git
cd ardupilot
Tools/environment_install/install-prereqs-ubuntu.sh -y
. ~/.profile
```

A clone is on the `master` branch by default, which is development for the next release, and parameter names there may already differ from the course. To make the simulator match the modules, switch to the stable tag: `git checkout Copter-4.7.3`, then `git submodule update --init --recursive`. The outputs below were captured on `Copter-4.7.2`; nothing changes for these steps in 4.7.3 (the differences between releases are in `ap-intro`).

### Step 2. First start
```
sim_vehicle.py -v ArduCopter -f octa-quad --console --map -w
```

In the MAVProxy console:

```
mode guided
arm throttle
takeoff 10
```

The drone takes off to 10 m. `mode rtl` brings it home.

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

Output when run alongside MAVProxy on 5760 (SITL 4.7.2, `--speedup 10`):

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

### Step 5. Parameter layers, speedup, wind, and RC loss in one script
This step was run on ArduCopter 4.7.2 (the binary built from the `Copter-4.7.2` tag, pymavlink 2.4.50) without MAVProxy: the script starts SITL itself, connects to SERIAL0 (5760), and performs five checks. The `lab.parm` layer sets `RTL_ALT_M 20` on top of `copter.parm`; the speedup is measured from `time_boot_ms`; an 8 m/s wind from the north is switched on in flight; RTL is tested twice, directly above home and 40 m away from it, the second time through a simulated loss of the transmitter with `SIM_RC_FAIL = 1`. Run it with `mkdir run && cd run && python3 ../sitl_lab.py ~/ardupilot`; the run takes about 1.5 min of real time.

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

Output of the run (2026-11-26):

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

What to read in the output. `RTL_ALT_M = 20` means the `lab.parm` layer overrode the 15 m default; `FS_THR_ENABLE = 1` and `RC_FS_TIMEOUT = 1` came from the code and `copter.parm`. The 10.0× speedup matched the requested one, so the machine keeps up. The 8 m/s wind tilted the vehicle by 6.5° on average against 0.3° in calm air: that is what holding position against wind looks like. Case A: an RTL directly above home climbed no higher than 10.0 m, which is the cone and not an error. Case B: 1.1 s after RC was lost (the `RC_FS_TIMEOUT` timeout = 1 s) RTL engaged, and the vehicle climbed to 20.0 m before returning.

### What you should get and what to record
- **Step 1.** Installation takes 10–30 minutes. After it, the `sim_vehicle.py` command must be found in a new terminal. If it is not, `~/.profile` has not been re-read.
- **Step 2.** The first build takes several minutes; later starts take seconds. In the console you can see the GPS get a fix and the EKF start using GPS, and after that arming succeeds. Arming before that moment is rejected with a `PreArm` message, which is normal. `takeoff 10` takes the vehicle up to 10 m. After `mode rtl` directly above the takeoff point it does **not** climb to `RTL_ALT_M` (before Copter 4.7, `RTL_ALT` in cm; 15 m by default) but lands from 10 m: with d = 0 the RTL cone keeps the current altitude (see the theory). To see the climb, first fly about 40 m away (in GUIDED with "Fly To Here" in the GCS or with the `SET_POSITION_TARGET_LOCAL_NED` message, as in step 5), then `mode rtl`: the vehicle climbs to 15 m and only then flies home. Record the time to climb 10 m and the altitude in both cases: this is how you check that the parameters work the way you think they do.
- **Step 3.** SITL ports: 5760 is SERIAL0, which MAVProxy holds; 5762 and 5763 are SERIAL1 and SERIAL2 for your own clients. The script reaches 9.5 m and prints the climb time on the firmware clock (6.6 s in the run), the first metric of a scenario. On Copter the streams on SERIAL1 are off by default (`MAV2_POSITION = 0`; before 4.7, `SR1_POSITION`), so the script first requests `GLOBAL_POSITION_INT` with `MAV_CMD_SET_MESSAGE_INTERVAL`; without that, `recv_match` waits forever. Arming is retried in a loop: until the EKF is using GPS, the pre-arm checks reject it, and `motors_armed_wait()` without a retry would hang forever.
- **Step 4.** The route is data, the scenario is code. An example route, `routes/square_20m.csv`, with `north_m,east_m,alt_m` lines relative to the takeoff point:

```text
20,0,10
20,20,10
0,20,10
0,0,10
```

The scenario reads the file, converts the offsets into GUIDED targets, and waits for arrival within a 1 m radius. A second route is the same format with different numbers.

### Lab
Write a "takeoff → circuit → landing" scenario so that the coordinates are in `routes/` and the scenario just refers to a route. Run it on two different routes without editing the scenario code.

Self-check: the lab is done when `run_sitl.sh` brings up SITL with the right frame and the ground station connects with no manual commands, in step 2 `takeoff 10` gave 10 m, `mode rtl` above home landed the vehicle from 10 m with no climb and 40 m from home it landed after a climb to `RTL_ALT_M` (15 m by default) with the times and altitudes recorded, your step 5 prints a speedup of 10× ± 1 (if it is lower, the machine cannot keep up, which is not a script error), an average tilt in the 8 m/s wind within 5–8° against less than 1° in calm air, case A no higher than 10.5 m, and case B 20 ± 0.5 m with RTL 1–1.5 s after `SIM_RC_FAIL = 1`, the step 3 script reaches 9.5 m by itself and prints a climb time of 5–9 s on the firmware clock (6.6 s in the run), the routes are in `routes/` in the `north_m,east_m,alt_m` format, and the "takeoff → circuit → landing" scenario flew two different routes without a single edit to the scenario code, arriving within a 1 m radius of every point, with the time for each recorded.

**Reference for the self-check.** A correct result: to change the route, only the file name from `routes/` changes. Typical wrong results: (1) the step 3 script is silent and hangs on `recv_match`, because the `MAV_CMD_SET_MESSAGE_INTERVAL` request was dropped from the code and on Copter the `GLOBAL_POSITION_INT` stream on SERIAL1 is off by default; (2) arming is rejected with a `PreArm` message, because the EKF has not started using GPS yet: wait 10–20 s after startup; (3) you had to edit the scenario for the second route, because the coordinates stayed in the code and not in `routes/`. (4) In step 5 case B climbed to 15 m and not to 20 m, because an old `eeprom.bin` was left in the working folder without `-w`, or `lab.parm` is not last in `--defaults`. (5) Case A climbed to 20 m, because RTL was engaged away from home: first wait until the vehicle is back at the takeoff point.

## diagnostics
- **Symptom:** `sim_vehicle.py: command not found`
  - Possible cause: the profile was not re-read after installation.
  - What to do: `. ~/.profile` or a new terminal.
- **Symptom:** the script hangs on `wait_heartbeat`
  - Possible cause: a wrong address or port, or SITL is not running.
  - What to do: check that SITL is running and the port number.
- **Symptom:** `arm throttle` is refused with `PreArm`
  - Possible cause: the EKF has not converged yet after startup.
  - What to do: wait 10–20 s after startup, read the PreArm message.
- **Symptom:** the drone behaves strangely after experiments
  - Possible cause: changed parameters are still in effect.
  - What to do: restart with `-w` to reset.
- **Symptom:** sim_vehicle.py does not start, or "waf configure" errors
  - Possible cause: the dependencies are not installed.
  - What to do: `Tools/environment_install/install-prereqs-ubuntu.sh -y`, log in again, `git submodule update --init --recursive`.
- **Symptom:** you changed a value in a `.parm` file, but SITL still has the old one
  - Possible cause: the previous value is saved in `eeprom.bin` in the working folder, and it overrides `--defaults`.
  - What to do: start with `-w` or delete `eeprom.bin`; check that your file is last in `--defaults`.
- **Symptom:** the `arducopter` binary is running, but nothing happens and the log is empty
  - Possible cause: SERIAL0 is opened as `tcp:0:wait`, so the firmware is waiting for a client on 5760.
  - What to do: connect MAVProxy or your own script to `tcp:127.0.0.1:5760`.
- **Symptom:** a scenario with `--speedup 10` "waits" 10 times longer than it should, or timeouts fire early
  - Possible cause: the intervals are measured on the computer's clock, not on `time_boot_ms`.
  - What to do: do all waiting in firmware time, like `sim_t()` in step 5; measure the real speedup.
- **Symptom:** RTL does not climb to `RTL_ALT_M`; the vehicle lands from its current altitude
  - Possible cause: the vehicle is close to home, and the `RTL_CONE_SLOPE` = 3 cone limited the altitude to d · 3.
  - What to do: this is by design; to test the climb, fly farther than `RTL_ALT_M` / 3 or set `RTL_CONE_SLOPE = 0`.
- **Symptom:** the GCS does not connect to SITL
  - Possible cause: the ports are in use, or MAVProxy is not forwarding.
  - What to do: `--out=udp:127.0.0.1:14550` explicitly, check `ss -lunp`.

## references
- Setting up SITL on Linux — ArduPilot Dev | https://ardupilot.org/dev/docs/setting-up-sitl-on-linux.html | primary | A
- Setting Up SITL — ArduPilot Dev | https://ardupilot.org/dev/docs/SITL-setup-landingpage.html | primary | A
- pymavlink — source code (GitHub) | https://github.com/ArduPilot/pymavlink | primary | A
- SITL command line options — SITL_cmdline.cpp, Copter-4.7.2 | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_HAL_SITL/SITL_cmdline.cpp | primary | A
- SIM_* parameters — libraries/SITL/SITL.cpp, Copter-4.7.2 | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/SITL/SITL.cpp | primary | A
- sim_vehicle.py, Copter-4.7.2 | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/Tools/autotest/sim_vehicle.py | primary | A
- RTL return altitude — mode_rtl.cpp, Copter-4.7.2 | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/ArduCopter/mode_rtl.cpp | primary | A

## checklist
- SITL starts and the GCS is connected
- Takeoff and RTL have been done from the MAVProxy console
- A pymavlink script takes the drone up
- Routes and scenarios are in separate folders
- I know how to reset SITL parameters and which layer overrides which
- I do the waiting in scripts in firmware time and measure the speedup
