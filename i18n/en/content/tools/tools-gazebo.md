---
id: tools-gazebo
title: "Simulation in Gazebo: Worlds, Sensors, a Camera in ROS 2 and Scenario Tests"
level: L3
readingTime: 40 min
firmware: ArduPilot 4.5+ · PX4 1.15+ · Gazebo Harmonic · ROS 2 Jazzy
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
source_hash: 86f99ad4c74a
---

## summary
SITL without an external simulator computes physics with a simple built-in model and has no idea what a tree, a wall or a camera image is. For vision, obstacle avoidance, precision landing and gimbals you need a world: Gazebo provides physics, lighting, cameras, lidars and rangefinders, and the autopilot works with it as with a real vehicle. This module covers ArduPilot SITL and PX4 SITL paired with Gazebo (the new one, `gz`), how an SDF world is built, adding an obstacle and a camera, bridging images into ROS 2, headless scenario tests for CI, and what HITL is and how it differs from SITL.

## theory
### Which Gazebo
- **Gazebo (gz)** — the new line (formerly Ignition). For ROS 2 Jazzy the paired LTS version is **Gazebo Harmonic**; it is also the one the ArduPilot plugin recommends.
- **Gazebo Classic** (gazebo11) reached end of support in January 2025 — don't carry over old instructions with `gazebo --verbose` and Classic `.world` files.
- The “ROS 2 — Gazebo” pairing is fixed: mixing versions outside the recommended pairs is a source of hard-to-pin-down problems with building the bridges.

### How the autopilot talks to the world
- **ArduPilot**: the `ardupilot_gazebo` plugin (the `ArduPilotPlugin` system in the model). Gazebo computes physics and sensors, the plugin sends the state to SITL and receives motor/servo commands from it; the exchange is JSON over UDP, in lockstep mode (the simulation waits for the autopilot, time is synchronized). Launch: in one terminal `gz sim -v4 -r iris_runway.sdf`, in another `sim_vehicle.py -v ArduCopter -f gazebo-iris --model JSON --map --console`. The frame name must contain `gazebo-`, the model must be `JSON`.
- **PX4**: Gazebo is built into the SITL build: `make px4_sitl gz_x500`; there are model variants with sensors (e.g. `gz_x500_depth`, `gz_x500_mono_cam`) and planes/VTOL; the world is selected with the `PX4_GZ_WORLD` variable.
- Environment variables: `GZ_SIM_SYSTEM_PLUGIN_PATH` — where to look for plugins (the `ardupilot_gazebo` build), `GZ_SIM_RESOURCE_PATH` — models and worlds.

### An SDF world
A world is an SDF XML file: physics (the step, e.g. 1 ms), lighting, ground, models. A model is links (`link`) with collision geometry (`collision`) and visible geometry (`visual`), mass and inertia, joints (`joint`), sensors (`sensor`) and plugin systems. An obstacle is a static model:
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
A pole 10 m tall, 10 m east of the world origin (ENU: x — east, y — north, z — up).

### Sensors and the bridge to ROS 2
- Cameras, depth cameras, lidars (`gpu_lidar`), IMUs are `sensor` elements in the model; they publish to the Gazebo bus (gz-transport), list them with `gz topic -l`.
- **ros_gz_bridge** carries topics between Gazebo and ROS 2: `ros2 run ros_gz_bridge parameter_bridge /camera@sensor_msgs/msg/Image@gz.msgs.Image` — the topic name, the ROS 2 type, the Gazebo type; `@` means both directions, `[` from Gazebo to ROS, `]` from ROS to Gazebo.
- A separate plugin, `GstCameraPlugin` from `ardupilot_gazebo`, streams camera video over GStreamer (H.264, UDP 5600) — like a real camera on a companion; the stream is enabled by a message to the `.../enable_streaming` topic. An example world with a gimbal and camera is `gimbal.sdf`; the Iris gimbal in `iris_runway.sdf` (SITL with `gazebo-iris-gimbal.parm`) is controlled by channels RC6–RC8.
- Realism: a perfect camera with no noise or blur fools you — test vision algorithms with noise, lighting changes and motion blur (noise parameters go in the sensor description).

### Speed and resources
- **Real-time factor (RTF)** — the ratio of simulation speed to real time; with cameras and lidars on a weak machine it drops below 1. Lockstep keeps things correct, but the test takes longer.
- Rendering is needed only for image sensors; for logic tests without cameras use the headless server `gz sim -s -r world.sdf`, for cameras on a machine without a display use `--headless-rendering` mode.

### HITL and SITL
- **SITL** — the firmware is built for the computer, everything is virtual.
- **HITL** (hardware in the loop) — a real flight controller with its own firmware; the sensors are replaced with simulator data over USB/MAVLink, the motors don't spin. It tests the real hardware: timing, CPU load, drivers — what SITL hides. Support and the setup method differ between PX4 and ArduPilot and between versions — follow the documentation for your version.

### Scenario tests
A scenario is a reproducible flight with a check of the result: “take off to 10 m, fly around the pole, land; no closer than 2 m to the pole, altitude within tolerance.” It runs headless, is checked via MAVLink and the log, and the result is pass/fail for CI (the “Configurations in CI” module). One scenario per safety function (failsafe, geofence, RTL) catches regressions on firmware and parameter updates before the field does.

{{diagram:gazebo-sitl|Gazebo computes physics and sensors, the plugin exchanges JSON with SITL in lockstep; images go to ROS 2 via ros_gz_bridge, the GCS and tests connect to SITL over MAVLink.}}

## practice
### Step 1. Iris in Gazebo
Install Gazebo Harmonic and build `ardupilot_gazebo` following the README (dependencies, `cmake`, `make`), set `GZ_SIM_SYSTEM_PLUGIN_PATH` and `GZ_SIM_RESOURCE_PATH`. Launch `iris_runway.sdf` and SITL with `-f gazebo-iris --model JSON`. Take off in GUIDED to 10 m from MAVProxy. Record the RTF in hover.

### Step 2. Your own world with a pole
Copy `iris_runway.sdf` into your own world and add the pole from the theory. Mission: takeoff, a waypoint 20 m east at 5 m altitude, return. What happens to the vehicle without obstacle avoidance? Move the waypoint so the route passes 3 m from the pole.

### Step 3. A camera in ROS 2
Launch a world with a camera (`gimbal.sdf` or a model with a camera), find the image topic (`gz topic -l`), bring up the bridge to ROS 2 and check with `ros2 topic hz` and `rqt_image_view` (or `ros2 run image_tools showimage`). Record the frame rate and resolution.

### Step 4. A scenario test
A pytest scenario against SITL (Gazebo headless: `gz sim -s -r world.sdf`):
```python
import time
from pymavlink import mavutil

def test_takeoff_hold_land():
    m = mavutil.mavlink_connection("udpin:0.0.0.0:14550")
    m.wait_heartbeat(timeout=30)
    m.set_mode("GUIDED")
    deadline = time.time() + 60
    while not m.motors_armed():                    # pre-arm checks pass once EKF and GPS are ready
        assert time.time() < deadline, "won't arm within 60 s"
        m.arducopter_arm()
        m.recv_match(type="HEARTBEAT", blocking=True, timeout=2)
    m.mav.command_long_send(m.target_system, m.target_component,
                            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, 10)
    alts, t0 = [], time.time()
    while time.time() - t0 < 30:
        p = m.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=2)
        if p:
            alts.append(p.relative_alt / 1000)
    assert max(alts) > 9.0, f"didn't climb: {max(alts):.1f} m"
    assert abs(alts[-1] - 10) < 1.0, f"doesn't hold altitude: {alts[-1]:.1f} m"
    m.set_mode("LAND")
```
Add a second test: a geofence (`FENCE_ENABLE = 1`, radius 50 m) and a flight to a point beyond it — the vehicle must switch to the geofence action. Record how long each test takes to run.

The lab counts as done when Iris flies in Gazebo with a measured RTF, your own world with the pole loads, the camera image is visible in ROS 2 with a measured frame rate, and two scenario tests pass headless.

## diagnostics
- **Symptom:** SITL doesn't see Gazebo, the vehicle “hangs” on the ground
  - Possible cause: `GZ_SIM_SYSTEM_PLUGIN_PATH` not set, the plugin isn't built, the frame lacks `gazebo-`, or the model isn't `JSON`.
  - What to do: check the variables, the plugin build, the `sim_vehicle.py` arguments.
- **Symptom:** the world can't find models
  - Possible cause: `GZ_SIM_RESOURCE_PATH` not set.
  - What to do: add the `models` and `worlds` paths.
- **Symptom:** the simulation runs slower than real time
  - Possible cause: cameras and lidars on a weak machine, a small physics step, rendering in a window.
  - What to do: a headless server, fewer sensors and lower resolution, `--headless-rendering` for cameras.
- **Symptom:** ros_gz_bridge is running, but the topic isn't in ROS 2
  - Possible cause: wrong topic name or type, mismatched ROS 2 and Gazebo versions.
  - What to do: `gz topic -l` and `gz topic -i`, the exact name and type, the recommended version pair.
- **Symptom:** a vision algorithm works great in simulation and poorly in the field
  - Possible cause: a perfect image with no noise, blur or lighting changes.
  - What to do: sensor noise in the SDF, varied lighting and textures, testing on recorded real data.

## references
- ArduPilot — ardupilot_gazebo plugin (README) | https://github.com/ArduPilot/ardupilot_gazebo | primary | A
- ArduPilot — Using SITL with Gazebo | https://ardupilot.org/dev/docs/sitl-with-gazebo.html | primary | A
- PX4 — Gazebo simulation | https://docs.px4.io/main/en/sim_gazebo_gz/ | primary | A
- Gazebo — documentation (Harmonic) | https://gazebosim.org/docs/harmonic/getstarted/ | primary | A
- ros_gz — ROS 2 ↔ Gazebo bridge | https://github.com/gazebosim/ros_gz | primary | A

## checklist
- I pick the Gazebo version paired with ROS 2 and don't confuse it with Gazebo Classic
- I launch ArduPilot and PX4 SITL with Gazebo
- I describe worlds and models in SDF and add obstacles
- I pass the camera image to ROS 2 via ros_gz_bridge
- I write scenario tests that run headless in CI
- I can explain the difference between SITL and HITL
