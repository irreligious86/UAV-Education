---
id: tools-gazebo
title: "Simulation in Gazebo: worlds, sensors, a camera in ROS 2, and scenario tests"
level: L3
readingTime: 40 min
firmware: ArduPilot 4.5+ (checked against 4.7.3) · PX4 1.15+ (checked against v1.18.0) · Gazebo Harmonic · ardupilot_gazebo (checked against f116b03, October 2026) · ROS 2 Jazzy
status: published
tags:
  - Gazebo
  - simulation
  - SITL
  - scenario tests
related:
  - ap-sitl
  - ros2-basics
  - per-camera
  - eng-ci-configs
next:
  - per-cv
source: content/tools/tools-gazebo.md
source_hash: 45ccdb13cd66
---

## summary
SITL without an external simulator computes physics with a simple built-in model and knows nothing about trees, walls or camera images. Vision, obstacle avoidance, precision landing and gimbals need a world: Gazebo provides physics, lighting, cameras, lidars and rangefinders, and the autopilot works with it as it would with a real vehicle. This module covers connecting ArduPilot SITL and PX4 SITL to Gazebo (the new one, `gz`), how a world is described in SDF, adding an obstacle and a camera, bridging images into ROS 2, headless scenario tests for CI, and what HITL is and how it differs from SITL.

## theory
### Which Gazebo
- **Gazebo (gz)** is the new line (formerly Ignition). The LTS release paired with ROS 2 Jazzy is **Gazebo Harmonic**; it is also the one the ArduPilot plugin recommends.
- **Gazebo Classic** (gazebo11) reached end of life in January 2025: do not carry over old instructions with `gazebo --verbose` and Classic `.world` files.
- The "ROS 2 – Gazebo" pairing is fixed: mixing versions outside the recommended pairs is a source of hard-to-track problems with building the bridges.

### How the autopilot talks to the world
- **ArduPilot**: the `ardupilot_gazebo` plugin (the `ArduPilotPlugin` system in the model). Gazebo computes the physics and sensors, the plugin sends the state to SITL and receives motor/servo commands from it; the exchange is JSON over UDP in lockstep mode (the simulation waits for the autopilot, and time stays consistent). Launch: in one terminal `gz sim -v4 -r iris_runway.sdf`, in another `sim_vehicle.py -v ArduCopter -f gazebo-iris --model JSON --map --console`. The link to Gazebo comes from the `JSON` model (`--model JSON`), while the `gazebo-iris` frame only loads the Iris parameters (`default_params/gazebo-iris.parm`).
- **PX4**: Gazebo is built into the SITL build: `make px4_sitl gz_x500`; there are model variants with sensors (for example `gz_x500_depth`, `gz_x500_mono_cam`) and planes/VTOL; the world is selected with the `PX4_GZ_WORLD` variable.
- Environment variables: `GZ_SIM_SYSTEM_PLUGIN_PATH` is where to look for plugins (the `ardupilot_gazebo` build), `GZ_SIM_RESOURCE_PATH` is for models and worlds.

### A world in SDF
A world is an SDF XML file: physics (the step, for example 1 ms), lighting, the ground, models. A model consists of links (`link`) with collision geometry (`collision`) and visual geometry (`visual`), mass and inertia, joints (`joint`), sensors (`sensor`) and system plugins. An obstacle is a static model:
```xml
<model name="pole">
  <static>true</static>
  <pose>10 0 5 0 0 0</pose>
  <link name="link">
    <collision name="collision">
      <geometry><cylinder><radius>0.3</radius><length>10</length></cylinder></geometry>
    </collision>
    <visual name="visual">
      <geometry><cylinder><radius>0.3</radius><length>10</length></cylinder></geometry>
    </visual>
  </link>
</model>
```
A pole 10 m tall, 10 m east of the world origin (ENU: x is east, y is north, z is up).

### Sensors and the bridge to ROS 2
- Cameras, depth cameras, lidars (`gpu_lidar`) and IMUs are `sensor` elements in a model; they publish on the Gazebo bus (gz-transport), and `gz topic -l` lists them.
- **ros_gz_bridge** carries topics between Gazebo and ROS 2: `ros2 run ros_gz_bridge parameter_bridge /camera@sensor_msgs/msg/Image@gz.msgs.Image` is the topic name, the ROS 2 type, the Gazebo type; `@` means both directions, `[` from Gazebo to ROS, `]` from ROS to Gazebo.
- A separate `GstCameraPlugin` from `ardupilot_gazebo` streams the camera video over GStreamer (H.264, UDP 5600), like a real camera on a companion; the stream is turned on with a message to the `.../enable_streaming` topic. An example world with a gimbal and camera is `gimbal.sdf`; the Iris gimbal in `iris_runway.sdf` (SITL with `gazebo-iris-gimbal.parm`) is controlled with channels RC6–RC8.
- Realism: an ideal camera with no noise or blur is misleading; check vision algorithms with noise, lighting changes and motion blur (the noise parameters go in the sensor description).

### Speed and resources
- **Real-time factor (RTF)** is the ratio of simulation speed to real time; with cameras and lidars on a weak machine it drops below 1. Lockstep keeps the results correct, but the test takes longer.
- Rendering is needed for sensors computed through the graphics engine: cameras (including depth and segmentation) and `gpu_lidar`; for logic tests without such sensors use the server without a GUI, `gz sim -s -r world.sdf`, and for cameras on a machine without a display, the `--headless-rendering` mode.

### HITL and SITL
- **SITL**: the firmware is built for the computer, and everything is virtual.
- **HITL** (hardware in the loop): a real flight controller with its own firmware, the sensors are replaced with simulator data over USB/MAVLink, and the motors do not spin. It tests the real hardware: timing, CPU load, drivers, the things SITL hides. Support and the setup procedure differ between PX4 and ArduPilot and between versions; follow the documentation for your version.

{{diagram:sim-stand-choice-tree|Choose the setup by what you are testing: logic without a world needs only SITL, a world without cameras and CI needs headless Gazebo, vision needs Gazebo with a camera, and flight controller timing and drivers need HITL.}}

### Scenario tests
A scenario is a repeatable flight with a check of the result: "take off to 10 m, fly around the pole, land; no closer than 2 m to the pole, altitude within tolerance." It runs headless, is checked through MAVLink and the log, and the result is pass/fail for CI (the "Configs in CI" module). One scenario per safety feature (failsafe, geofence, RTL) catches regressions from firmware and parameter updates before the field does.

{{diagram:gazebo-sitl|Gazebo computes the physics and sensors, the plugin exchanges JSON with SITL in lockstep; images go to ROS 2 through ros_gz_bridge, and the ground station and tests connect to SITL over MAVLink.}}

### Where it fits

- **Takes in:** motor and servo commands from SITL (`ap-sitl`, `px4-intro`); SDF models and worlds; ROS 2 Jazzy from the course image (`ros2-basics`).
- **Hands off:** physics and sensor readings to the autopilot; images and lidar to ROS 2 through `ros_gz_bridge` (`ros2-nav`, `per-cv`); GStreamer video, as from a real camera (`per-camera`); scenario tests to CI (`eng-ci-configs`).
- **If you get this wrong:** you left an ideal camera with no noise or blur → the detector "works" in simulation and fails in the field on glare, shadows and motion blur, the failure classes from `per-cv`. You mixed ROS 2 and Gazebo versions outside the recommended pair (Jazzy + Harmonic) → problems building the bridges, and no camera topics in ROS 2; the course's ROS 2 version is in `ros2-basics`.

## practice
### Step 1. Iris in Gazebo
Install Gazebo Harmonic and build `ardupilot_gazebo` following the README (dependencies, `cmake`, `make`), set `GZ_SIM_SYSTEM_PLUGIN_PATH` and `GZ_SIM_RESOURCE_PATH`. Launch `iris_runway.sdf` and SITL with `-f gazebo-iris --model JSON`. Take off in GUIDED to 10 m from MAVProxy. Record the RTF in hover.

### Step 2. Your own world with a pole
Copy `iris_runway.sdf` into your own world and add the pole from the theory. Mission: takeoff, a waypoint 20 m east at 5 m altitude, return. What happens to the vehicle without obstacle avoidance? Move the waypoint so the route passes 3 m from the pole.

### Step 3. A camera in ROS 2
Launch a world with a camera (`gimbal.sdf` or a model with a camera), find the image topic (`gz topic -l`), bring up the bridge to ROS 2 and check `ros2 topic hz` and `rqt_image_view` (or `ros2 run image_tools showimage`). Record the frame rate and resolution.

### Step 4. A scenario test
A pytest scenario against SITL (headless Gazebo: `gz sim -s -r world.sdf`):
```python
import time
from pymavlink import mavutil

def test_takeoff_hold_land():
    m = mavutil.mavlink_connection("udpin:0.0.0.0:14550")
    m.wait_heartbeat(timeout=30)
    m.set_mode("GUIDED")
    deadline = time.time() + 60
    while not m.motors_armed():                    # pre-arm checks pass once EKF and GPS are ready
        assert time.time() < deadline, "not armed within 60 s"
        m.arducopter_arm()
        m.recv_match(type="HEARTBEAT", blocking=True, timeout=2)
    m.mav.command_long_send(m.target_system, m.target_component,
                            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, 10)
    alts, t0 = [], time.time()
    while time.time() - t0 < 30:
        p = m.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=2)
        if p:
            alts.append(p.relative_alt / 1000)
    assert max(alts) > 9.0, f"did not climb: {max(alts):.1f} m"
    assert abs(alts[-1] - 10) < 1.0, f"not holding altitude: {alts[-1]:.1f} m"
    m.set_mode("LAND")
```
Add a second test: a geofence (`FENCE_ENABLE = 1`, 50 m radius) and a flight to a point outside it; the vehicle must take the fence action. Record how long each test takes to run.

Self-check: the lab is done when Iris takes off in Gazebo to 10 m from MAVProxy and the RTF in hover is recorded, your world with the pole loads and the waypoint is moved so the route passes 3 m from the pole, the camera image is visible in ROS 2 and the frame rate from `ros2 topic hz` and the resolution are recorded, both scenario tests pass under pytest headless (takeoff–hold–land: climbs above 9 m and holds 10 ± 1 m; 50 m geofence: the vehicle takes the fence action) and the run time of each is recorded.

**Reference answer for self-check.** Correct result: the test answers pass/fail by itself, without anyone looking at a screen. Typical wrong results: (1) the vehicle "hangs" on the ground and SITL does not see Gazebo: `GZ_SIM_SYSTEM_PLUGIN_PATH` is not set, or SITL was not started with the `JSON` model; (2) the RTF is well below 1: cameras and lidars on a weak machine, or rendering in a window; run the server without a GUI; (3) the bridge is running but there is no image topic in ROS 2: wrong name or type; check against `gz topic -l`.

## diagnostics
- **Symptom:** SITL does not see Gazebo, the vehicle "hangs" on the ground
  - Possible cause: `GZ_SIM_SYSTEM_PLUGIN_PATH` is not set, the plugin is not built, or SITL was not started with the `JSON` model.
  - What to do: check the variables, the plugin build, the `sim_vehicle.py` arguments.
- **Symptom:** the world cannot find the models
  - Possible cause: `GZ_SIM_RESOURCE_PATH` is not set.
  - What to do: add the `models` and `worlds` paths.
- **Symptom:** the simulation runs slower than real time
  - Possible cause: cameras and lidars on a weak machine, a small physics step, rendering in a window.
  - What to do: the server without a GUI, fewer sensors and lower resolution, `--headless-rendering` for cameras.
- **Symptom:** ros_gz_bridge is running, but the topic is missing in ROS 2
  - Possible cause: wrong topic name or type, mismatched ROS 2 and Gazebo versions.
  - What to do: `gz topic -l` and `gz topic -i`, the exact name and type, the recommended version pair.
- **Symptom:** a vision algorithm works perfectly in simulation and poorly in the field
  - Possible cause: an ideal image with no noise, blur or lighting changes.
  - What to do: sensor noise in the SDF, different lighting and textures, testing on recorded real data.

## references
- ArduPilot — ardupilot_gazebo plugin (README) | https://github.com/ArduPilot/ardupilot_gazebo | primary | A
- ArduPilot — Using SITL with Gazebo | https://ardupilot.org/dev/docs/sitl-with-gazebo.html | primary | A
- PX4 — Gazebo simulation | https://docs.px4.io/v1.17/en/sim_gazebo_gz/ | primary | A
- Gazebo — documentation (Harmonic) | https://gazebosim.org/docs/harmonic/getstarted/ | primary | A
- ros_gz — ROS 2 ↔ Gazebo bridge | https://github.com/gazebosim/ros_gz | primary | A

## checklist
- I choose the Gazebo version paired with ROS 2 and do not confuse it with Gazebo Classic
- I can launch ArduPilot and PX4 SITL with Gazebo
- I can describe a world and models in SDF and add obstacles
- I can bring a camera image into ROS 2 through ros_gz_bridge
- I write scenario tests that run headless in CI
- I can explain the difference between SITL and HITL
