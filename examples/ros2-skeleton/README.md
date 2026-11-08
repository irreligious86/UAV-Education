# ROS 2 companion skeleton

Package layout for a companion node that closes a loop "camera → error → velocity setpoint".
Two transports are supported by swapping one adapter:

- **PX4**: uXRCE-DDS bridge, topics `/fmu/in/trajectory_setpoint`, `/fmu/in/offboard_control_mode`,
  `/fmu/out/vehicle_local_position` (see PX4 docs "ROS 2 User Guide").
- **ArduPilot**: MAVROS, topic `/mavros/setpoint_velocity/cmd_vel_unstamped` in GUIDED.

```
uav_offboard/
  package.xml, setup.py
  uav_offboard/
    tracker_node.py        # subscribes to detections, publishes velocity setpoints with limits and a timeout
    adapters/px4.py        # TrajectorySetpoint/OffboardControlMode publisher + arming/offboard switch
    adapters/mavros.py     # TwistStamped publisher + GUIDED mode via /mavros/set_mode
  launch/sitl.launch.py    # starts the node with the chosen adapter
```

Run order (PX4): `make px4_sitl gz_x500` → `MicroXRCEAgent udp4 -p 8888` → `ros2 launch uav_offboard sitl.launch.py adapter:=px4`.
Run order (ArduPilot): `sim_vehicle.py -v ArduCopter` → `ros2 launch mavros apm.launch fcu_url:=udp://:14550@` → `ros2 launch uav_offboard sitl.launch.py adapter:=mavros`.

The node enforces: max speed, max acceleration, a 500 ms watchdog (no detection → zero velocity →
hover), and a 3 s target-loss timeout (→ hover, then hand control back). These are the protections
the per-tracking module requires; keep them even in simulation.
