---
id: px4-architecture
title: "PX4 architecture: modules and uORB"
level: L3
readingTime: 25 min
firmware: PX4 1.14+
status: published
added: 2026-11-08
tags:
  - uORB
  - architecture
related:
  - px4-intro
  - px4-ros2
next:
  - px4-control
source: content/px4/px4-architecture.md
source_hash: 5453ed2c4c43
---

## summary
PX4 is not one program but a set of independent modules that exchange messages over the uORB bus using publish/subscribe. This explains almost everything in PX4: why a module can be restarted in flight, why ROS 2 sees the autopilot's internals directly, how the path from sensor to motor is built. The module walks through the flight stack and middleware, `.msg` messages, update rates and the tools for peeking inside a running system.

## theory
### Two layers
- **Middleware** — sensor drivers, communication with the outside world (MAVLink, uXRCE-DDS), the uORB bus and the simulation layer.
- **Flight stack** — the algorithms: state estimation (estimator), controllers, navigator, commander, control allocation.

### The path from sensor to motor
1. IMU drivers read the sensor FIFO (kilohertz rates, up to 8 kHz on modern IMUs); the filtered gyro is published to `vehicle_angular_velocity` at `IMU_GYRO_RATEMAX` (400 Hz), the integrated data to `vehicle_imu` at `IMU_INTEG_RATE` (200 Hz).
2. **EKF2** combines IMU, GPS, baro and magnetometer into an estimate of attitude, velocity and position.
3. **Navigator** decides where to fly: mission, return, hold.
4. **Position controller** turns the desired position into a desired attitude and thrust.
5. **Attitude controller** → desired angular rates; **rate controller** → torques.
6. **Control allocation** turns torques and thrust into commands for specific motors/servos according to the frame geometry (`CA_AIRFRAME`, `CA_ROTOR*`).
7. Output drivers — PWM/DShot.

**Commander** is the “arbiter”: arm/disarm, mode switching, readiness checks, failsafe.

### uORB
Each module publishes topics and subscribes to others' topics. A topic is described by a `.msg` file (CamelCase name → snake_case topic: `VehicleAttitude.msg` → `vehicle_attitude`); the mandatory field is `uint64 timestamp`. One `.msg` can define several topics (`# TOPICS ...`). The bus is asynchronous: a subscriber wakes up when new data appears, so the module's rate is set by whoever publishes.

This is the same idea as ROS: that is exactly why the uXRCE-DDS bridge feels so natural — it simply exposes some of the uORB topics to the outside.

### Execution
Modules are separate tasks (on NuttX — threads with priorities; on Linux/macOS in SITL — threads of a process). You can start and stop them with `<module> start/stop`, check the load with `top`, topic rates with `uorb top`, the content with `listener <topic>`.

### Why you need to know this
- When debugging strange behavior you look not for “a parameter” but for **a module and a topic**: what was published, at what rate, what the controller received.
- Your own code in PX4 is a new module subscribing to topics, not an edit of someone else's.
- ULog logs are just a recording of topics; when you analyze them, you read the same messages.

### Modules by name (where to look in the code)
`src/modules/`: `sensors` (sensor collection, `sensor_combined`), `ekf2` (state estimation), `commander` (arming, modes, failsafe, pre-arm), `navigator` (missions, RTL, geofence, `position_setpoint_triplet`), `mc_pos_control` (position → attitude+thrust), `mc_att_control` (angle → angular rate), `mc_rate_control` (rate → torques, `vehicle_torque_setpoint`/`vehicle_thrust_setpoint`), `control_allocator` (torques → `actuator_motors`/`actuator_servos`), `logger`, `mavlink`, `uxrce_dds_client`, `land_detector`, `battery_status`, `mc_autotune_attitude_control`. Drivers are in `src/drivers/` (imu, gps, barometer, dshot, pwm_out). The IMU → motor path: `sensors` → `ekf2` → `mc_pos_control` → `mc_att_control` → `mc_rate_control` → `control_allocator` → `dshot`/`pwm_out`.

### Execution: work queues and priorities
On NuttX most modules are not separate threads but items in a **work queue** with priorities (`wq:rate_ctrl` higher, `wq:nav_and_controllers`, `wq:hp_default`, `wq:lp_default` lower): fast tasks (rate control) wake up when gyro data arrives and run first; `work_queue status` shows them. Separate tasks are logger and mavlink; EKF2 also runs in a work queue (ScheduledWorkItem). `top` in the console shows CPU load per task (normal is < 70–80% on FMUv5); overload shows up as growing latencies and warnings.

### Storage and configuration
Parameters live in flash/EEPROM (`param save`, `param reset_all`), missions and the geofence in `dataman` (SD or flash), logs on the SD card. Startup scripts are in `ROMFS/px4fmu_common/init.d/` (`rc.*`): which driver to start and with which parameters; the airframe files in `init.d/airframes/` are exactly the “airframe selection” in QGC. Your own module is added to `boards/<board>/default.px4board` and started from `rc.*` or by a parameter.

### Worked example: troubleshooting “the vehicle wobbles in roll”
1. `listener vehicle_angular_velocity` — is the rate ~400 Hz? If lower — overload (`top`).
2. `listener vehicle_rates_setpoint` versus `vehicle_angular_velocity` in the log: oscillation only in the actual rate → rate P/D; in the setpoint as well → attitude P/position.
3. `uorb top -1` — who publishes unusually rarely/often (a sensor with dropouts → EKF2 innovations).
4. Flight Review → spectrum: a motor peak in the passband? → `IMU_GYRO_CUTOFF`/notch (`IMU_GYRO_NF0_FRQ`/`BW`, `IMU_GYRO_DNF_EN`).
This is how the architecture turns into a method: topic → module → parameter, instead of “bump P a bit”.

{{diagram:px4-uorb-path|The data path in PX4 from sensors to motors: modules exchange uORB topics, and every step can be inspected with the listener command.}}

## practice
### Step 1. Look inside SITL
```
make px4_sitl gz_x500
pxh> top
pxh> uorb top
pxh> listener vehicle_attitude
pxh> listener sensor_combined -n 1
```

### Step 2. Trace the chain
In `uorb top`, find the rates of `sensor_combined`, `vehicle_attitude`, `vehicle_local_position`, `actuator_motors`. Match them against the chain above: which is faster, which is slower, and why.

### Step 3. Stop and start a module
`mc_rate_control stop` while hovering in SITL — the vehicle loses control; `mc_rate_control start` — brings it back. Do this only in the simulator: it is a demonstration of modularity, not a technique.

### Step 4. Read a `.msg`
Open `msg/VehicleCommand.msg` (since PX4 1.16 — `msg/versioned/VehicleCommand.msg`) and `msg/OffboardControlMode.msg` in the source tree: you will need these two messages for ROS 2.

### What you should get and what to write down
- **Step 1.** `top` shows the modules and their CPU load: in SITL this is `px4` as a process, with the stack's modules inside. `uorb top` is a table of topics with publication rate and number of subscribers. `listener sensor_combined -n 1` prints one message with accelerations and angular rates, and from it you can see the fields you will need later in ROS 2.
- **Step 2.** Write down the actual rates of the four topics from `uorb top`. The expected picture: sensors and attitude — hundreds of hertz, local position — tens, motor outputs — at the rate of the angular-rate loop. Rates in SITL depend on the simulator model and may differ from hardware — compare them with each other, not with someone else's numbers. Explain why position is slower than attitude: it relies on GNSS and the barometer, which are slow themselves.
- **Step 3.** After `mc_rate_control stop` the vehicle in SITL flips or crashes within a fraction of a second: without the angular-rate loop nothing holds the attitude. After `start` the module is subscribed to its topics again, but the crashed vehicle has to be restarted. This clearly shows that modules are separate processes connected only by topics.
- **Step 4.** Write out the fields of `VehicleCommand` (the command, seven parameters, the targets) and `OffboardControlMode` (which type of setpoint is allowed) — this is direct preparation for the PX4 + ROS 2 module.

### Lab
A one-page report: the chain from IMU to motors with module and topic names and their rates measured in SITL.

The lab counts as done when the rates of the four topics have been measured with `uorb top` and written down, `listener` has been run on at least two topics with a breakdown of the fields, and the report describes the chain “sensors → estimation → angular-rate loop → motors” with module and topic names.

## diagnostics
- **Symptom:** the controller doesn't respond to a setpoint
  - Possible cause: the topic isn't published or is published at zero rate.
  - What to do: `uorb top`, `listener <topic>` — is there any data.
- **Symptom:** a module won't start
  - Possible cause: it isn't built for this board or depends on a missing driver.
  - What to do: check the board config and the startup output.
- **Symptom:** the topic you need isn't in the log
  - Possible cause: it isn't included in the logging profile (`SDLOG_PROFILE`).
  - What to do: enable the profile, repeat the flight.

## references
- PX4 Architectural Overview | https://docs.px4.io/main/en/concept/architecture.html | primary | A
- PX4 uORB Messaging | https://docs.px4.io/main/en/middleware/uorb.html | primary | A
- PX4 Control Allocation | https://docs.px4.io/main/en/concept/control_allocation.html | primary | A
- PX4-Autopilot msg definitions (GitHub) | https://github.com/PX4/PX4-Autopilot/tree/main/msg | primary | A

## checklist
- I can name the chain of modules from IMU to motors
- I understand publish/subscribe and the role of timestamp
- I have used `top`, `uorb top`, `listener` in SITL
- I know where the `.msg` files live and how a file name becomes a topic
