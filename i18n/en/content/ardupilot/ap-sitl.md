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

master.set_mode(master.mode_mapping()["GUIDED"])
master.arducopter_arm()
master.motors_armed_wait()

master.mav.command_long_send(
    master.target_system, master.target_component,
    mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
    0, 0, 0, 0, 0, 0, 0, 10,  # param7 = altitude, m
)

while True:
    msg = master.recv_match(type="GLOBAL_POSITION_INT", blocking=True)
    alt = msg.relative_alt / 1000
    print(f"alt {alt:.1f} m")
    if alt > 9.5:
        break
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
