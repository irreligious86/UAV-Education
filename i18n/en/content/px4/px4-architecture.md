---
id: px4-architecture
title: "PX4 architecture: modules and uORB"
level: L3
readingTime: 25 min
firmware: PX4 1.18 (parameters, modules and uORB checked against v1.18.0)
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
source_hash: e0694315e2bb
---

## summary
PX4 is not one program but a set of independent modules that exchange messages over the uORB bus using publish/subscribe. That explains almost everything about PX4: why you can restart a module in flight, why ROS 2 sees the autopilot's internals directly, and how data travels from a sensor to a motor. This module covers the flight stack and the middleware, `.msg` definitions, update rates and the tools for looking inside a running system.

## theory
### Two layers
- **Middleware**: sensor drivers, communication with the outside world (MAVLink, uXRCE-DDS), the uORB bus and the simulation layer.
- **Flight stack**: the algorithms: state estimation (estimator), controllers, navigator, commander, control allocation.

### From sensor to motor
1. IMU drivers read the sensor FIFO (kilohertz rates, up to 8 kHz on modern IMUs); after filtering, the gyro data is published to `vehicle_angular_velocity` at `IMU_GYRO_RATEMAX` (800 Hz on a multicopter: the airframe raises the parameter default of 400 through `rc.mc_defaults`), and integrated data goes to `vehicle_imu` at `IMU_INTEG_RATE` (200 Hz).
2. **EKF2** fuses the IMU, GPS, barometer and magnetometer into an attitude, velocity and position estimate.
3. **Navigator** decides where to fly: mission, return, hold.
4. **Position controller** turns the desired position into a desired attitude and thrust.
5. **Attitude controller** → desired angular rates; **rate controller** → torques.
6. **Control allocation** turns torques and thrust into commands for specific motors and servos from the frame geometry (`CA_AIRFRAME`, `CA_ROTOR*`).
7. Output drivers: PWM/DShot.

**Commander** is the arbiter: arming and disarming, mode changes, readiness checks, failsafes.

### uORB
Each module publishes topics and subscribes to other modules' topics. A topic is defined by a `.msg` file (CamelCase file name → snake_case topic: `VehicleAttitude.msg` → `vehicle_attitude`), and the `uint64 timestamp` field is mandatory. One `.msg` can define several topics (`# TOPICS ...`). The bus is asynchronous: a subscriber wakes up when new data arrives, so the publisher sets the module's rate.

It is the same idea as ROS, which is why the uXRCE-DDS bridge feels so natural: it simply exposes part of the uORB topics to the outside.

### Execution
Modules are separate tasks (threads with priorities on NuttX; threads of one process on Linux/macOS in SITL). You start and stop them with `<module> start/stop`, check the load with `top` (on a flight controller; `listener cpuload` in SITL), topic rates with `uorb top`, and contents with `listener <topic>`.

### Why it matters
- When you debug odd behavior, you look for a **module and a topic**, not a "parameter": what was published, at what rate, and what the controller received.
- Your own code in PX4 is a new module that subscribes to topics, not an edit of someone else's.
- ULog logs are just recorded topics; when you analyze them you read the same messages.

### Modules by name (where to look in the code)
`src/modules/`: `sensors` (sensor aggregation, `sensor_combined`), `ekf2` (state estimation), `commander` (arming, modes, failsafes, preflight checks), `navigator` (missions, RTL, geofence, `position_setpoint_triplet`), `mc_pos_control` (position → attitude + thrust), `mc_att_control` (attitude → angular rate), `mc_rate_control` (rate → torques, `vehicle_torque_setpoint`/`vehicle_thrust_setpoint`), `control_allocator` (torques → `actuator_motors`/`actuator_servos`), `logger`, `mavlink`, `uxrce_dds_client`, `land_detector`, `battery_status`, `mc_autotune_attitude_control`. Drivers are in `src/drivers/` (imu, gps, barometer, dshot, pwm_out). The IMU → motor path: `sensors` → `ekf2` → `mc_pos_control` → `mc_att_control` → `mc_rate_control` → `control_allocator` → `dshot`/`pwm_out`.

### Execution: work queues and priorities
On NuttX most modules are not separate threads but items on a **work queue** with a priority (`wq:rate_ctrl` is higher; `wq:nav_and_controllers`, `wq:hp_default`, `wq:lp_default` are lower): fast tasks (rate control) wake up when gyro data arrives and run first; `work_queue status` lists them. Logger and mavlink are separate tasks; EKF2 also runs on a work queue (ScheduledWorkItem). `top` in the console shows CPU load per task; overload shows up as growing latency and warnings. The firmware has one hard limit: with the load above `COM_CPU_MAX` (95 %) for more than 2 s, arming is denied; the source defines no other load "norm", so judge the headroom for your build from `top` on the ground and from the log.

### Console: commands by architecture layer
The console is `nsh>` on a flight controller (QGC → Analyze Tools → MAVLink Console) and `pxh>` in SITL. How to use it: start from the question "where in the chain sensor → module → topic → output did it get lost", run the layer's command from the table, and check the output against the last column. The full list, options and the nsh/pxh differences are in `px4-console-params`.

| Layer | Question | Command | What counts as normal |
|---|---|---|---|
| Firmware | which board and build? | `ver all` | `HW arch`, `PX4 version`, `PX4 git-hash`; write them down before any change |
| Boot | which drivers started? | `dmesg` (flight controller only) | the driver start line; `Conflicting config` means two drivers on one port |
| Module | is the module alive? | `<module> status`: `sensors`, `ekf2`, `commander`, `mavlink`, `logger`, `gps`, `dshot`, `pwm_out`, `uavcan`, `navigator` | not `not running`; for `ekf2 status`, the estimate flags are 1 |
| Topic | is data flowing, and at what rate? | `listener <topic> -n 5`, `uorb top` | new messages, not `Giving up`; the rate matches the publishing module |
| Execution | is there enough CPU? | `top` (flight controller), `work_queue status`; `listener cpuload` in SITL | load comfortably below `COM_CPU_MAX` = 95 % |
| Module | restart after a parameter change | `<module> stop` / `start` | on the ground only, disarmed |
| Commander | why won't it arm? | `commander check`, then `dmesg` | `Preflight Fail: …` lines |
| Parameters | what value is actually set? | `param show <name>` | `x`: the parameter is used; `+`: the value differs from the default; `*`: changed and not saved yet |

### Storage and configuration
Parameters live in the file the board defines (`CONFIG_BOARD_PARAM_FILE`): by default the FRAM/EEPROM partition `/fs/mtd_params`, on some boards `/fs/microsd/params` on the SD card, on boards without FRAM a flash sector (`px4-console-params`) (`param save`, `param reset_all`); missions and the geofence are in `dataman` (SD card or flash), logs on the SD card. The startup scripts are in `ROMFS/px4fmu_common/init.d/` (`rc.*`): which drivers start and with which parameters, plus the airframe files in `init.d/airframes/`, which is what "selecting an airframe" in QGC means. You add your own module to `boards/<board>/default.px4board` and start it from `rc.*` or by a parameter.

### Worked example: "the vehicle oscillates in roll"
1. `uorb top vehicle_angular_velocity`: is the rate close to `IMU_GYRO_RATEMAX` (800 Hz on a multicopter, the parameter default of 400 for everything else; in SITL the simulated gyro rate caps it too)? If it is clearly lower, the CPU is overloaded (`top` on a flight controller, `listener cpuload` in SITL).
2. `listener vehicle_rates_setpoint` vs. `vehicle_angular_velocity` in the log: oscillation only in the actual rate → the cause is in the rate loop or the filters (step 4); in the setpoint too → the cause is further up the chain (step 3).
3. Oscillation in the setpoint as well: `uorb top -1` shows who publishes unusually rarely or often; a sensor with dropouts → the EKF2 innovations for that sensor; sensors fine → attitude P / the position loop.
4. Oscillation only in the actual rate: Flight Review → spectrum: is there a motor peak in the band? → `IMU_GYRO_CUTOFF`/notch (`IMU_GYRO_NF0_FRQ`/`BW`, `IMU_GYRO_DNF_EN`); no peak → rate P/D.
That is how the architecture becomes a method: topic → module → parameter, instead of "turn up P".

{{diagram:px4-roll-osc-tree|Every question goes to a topic, not a parameter: first the gyro rate, then whether the setpoint oscillates too; only then do you know which module to tune.}}

{{diagram:px4-uorb-path|The PX4 data path from sensors to motors: modules exchange uORB topics, and you can inspect every step with listener.}}

### Place in the system

- **Takes in:** IMU, GPS, barometer and magnetometer data from the drivers (sensor errors: `est-sensors`); the frame geometry `CA_*` from the airframe (`px4-setup-scratch`); the loop parameters (`px4-control`).
- **Hands on:** uORB topics to the ULog log for Flight Review (`px4-intro`) and out to ROS 2 through uXRCE-DDS (`px4-ros2`); the "topic → module → parameter" debugging method to tuning (`px4-control`).
- **If you get it wrong here:** your own module or driver overloads the CPU → `vehicle_angular_velocity` arrives slower than `IMU_GYRO_RATEMAX` → the vehicle oscillates and the cause gets hunted in the PIDs (`px4-control`). Firmware and `px4_msgs` of different versions → the message definitions do not match → ROS 2 nodes cannot read the topics (`ros2-px4`).

## practice
### Step 1. Look inside SITL
```
make px4_sitl gz_x500
pxh> work_queue status
pxh> uorb top
pxh> listener vehicle_attitude
pxh> listener sensor_combined -n 1
```

### Step 2. Trace the chain
In `uorb top`, find the rates of `sensor_combined`, `vehicle_attitude`, `vehicle_local_position`, `actuator_motors`. Map them onto the chain above: which is faster, which is slower, and why.

### Step 3. Stop and start a module
`mc_rate_control stop` while hovering in SITL: the vehicle loses control; `mc_rate_control start` brings it back. Do this only in the simulator: it demonstrates modularity, it is not a technique.

### Step 4. Read a `.msg`
Open `msg/versioned/VehicleCommand.msg` (`msg/VehicleCommand.msg` before 1.16) and `msg/OffboardControlMode.msg` in the source: you will need these two messages for ROS 2.

### What you should get and what to write down
- **Step 1.** The SITL build has no `top` command (a flight controller has it: `top once`). In SITL, `work_queue status` shows the queues and the modules on them (`mc_rate_control` is on `wq:rate_ctrl`), `listener cpuload` gives the CPU load, and `uorb top` is a table of topics with their publication rate and number of subscribers. `listener sensor_combined -n 1` prints one message with accelerations and angular rates, which shows you the fields you will need later in ROS 2.
- **Step 2.** Write down the actual rates of the four topics from `uorb top`. The expected picture: sensors and attitude in the hundreds of hertz, local position in the tens, motor outputs at the rate loop frequency. Rates in SITL depend on the simulator model and can differ from real hardware, so compare them with each other, not with someone else's numbers. Explain why position is slower than attitude: EKF2 publishes position once per filter step (`EKF2_PREDICT_US` = 10 ms, ~83 Hz in SITL, ~100 Hz on a flight controller), attitude on every IMU sample (250 Hz in SITL); GNSS and the barometer are slower still, but they are fused inside the filter and do not set its output rate.
- **Step 3.** After `mc_rate_control stop` the vehicle in SITL flips or falls within a fraction of a second: without the rate loop nothing holds the attitude. After `start` the module subscribes to its topics again, but a crashed vehicle has to be restarted. This shows clearly that modules are independent tasks (threads or work queue items: `mc_rate_control` runs on the `rate_ctrl` queue, not as a separate process) connected only by topics.
- **Step 4.** List the fields of `VehicleCommand` (the command, seven parameters, the targets) and of `OffboardControlMode` (which setpoint types are allowed); this is direct preparation for the PX4 + ROS 2 module.

### Lab
A one-page diagram in your notes: the chain from the IMU to the motors with module names, topic names and the rates you measured in SITL.

Self-check: the lab is done when you measured and wrote down the rates of the four topics with `uorb top`, their ratios match the expected picture (sensors and attitude in the hundreds of hertz, local position in the tens, motor outputs at the rate loop frequency), you ran `listener` on at least two topics and went through their fields, you listed the fields of `VehicleCommand` and `OffboardControlMode`, and the one-page diagram shows the chain "sensors → estimation → rate loop → motors" with the same module and topic names as in the theory and with your rates.

**Reference answer for the self-check.** A correct result: every link of the diagram has a module name, a topic and a rate from your `uorb top`, and position is slower than attitude because EKF2 publishes it once per filter step (`EKF2_PREDICT_US` = 10 ms, ~83 Hz in SITL, ~100 Hz on a flight controller) and attitude on every IMU sample (250 Hz in SITL); GNSS and the barometer are slower still, but they are fused inside the filter and do not set its output rate. Typical wrong results: (1) a topic is missing from `uorb top` or its rate is zero: it is not being published, check with `listener <topic>`; (2) the rates were compared with someone else's numbers and "don't match": in SITL they depend on the simulator model, so compare the topics with each other.

## diagnostics
- **Symptom:** the controller does not react to a setpoint
  - Possible cause: the topic is not published, or is published at zero rate.
  - What to do: `uorb top`, `listener <topic>`: is there any data?
- **Symptom:** a module will not start
  - Possible cause: it was not built for this board, or it depends on a missing driver.
  - What to do: check the board config and the startup output.
- **Symptom:** the topic you need is missing from the log
  - Possible cause: it is not in the logging profile (`SDLOG_PROFILE`).
  - What to do: enable the profile and fly again.

## references
- PX4 Architectural Overview | https://docs.px4.io/v1.17/en/concept/architecture.html | primary | A
- PX4 uORB Messaging | https://docs.px4.io/v1.17/en/middleware/uorb.html | primary | A
- PX4 Control Allocation | https://docs.px4.io/v1.17/en/concept/control_allocation.html | primary | A
- PX4-Autopilot msg definitions (GitHub) | https://github.com/PX4/PX4-Autopilot/tree/v1.17.0/msg | primary | A

## checklist
- I can name the chain of modules from the IMU to the motors
- I understand publish/subscribe and the role of the timestamp
- I used `work_queue status`, `uorb top`, `listener` in SITL
- I know where the `.msg` files live and how a file name becomes a topic
