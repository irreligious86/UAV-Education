# Follow a target (project #4 starter)

The control part of "detector → tracker → follow": a pure function that turns the tracked bounding box
into a body-frame velocity and yaw-rate setpoint, with deadband, limits, an acceleration (slew) limit and
a target-lost watchdog (short gaps decay the command, long gaps hover). Pure means testable without a
camera, a simulator or a drone — the same function runs in your ROS 2 node or pymavlink loop.

```bash
pip install pytest
python -m pytest -q tests          # 7 tests
```

Wiring it up (milestones on the course page "Проекты → 4"):
1. Detector + tracker on a Gazebo camera (`examples/ros2-docker`) → `box` per frame.
2. Call `step(box, t, state)` at the camera rate; send `Setpoint` as GUIDED velocity
   (`SET_POSITION_TARGET_LOCAL_NED`, `MAV_FRAME_BODY_OFFSET_NED`, type mask for velocity + yaw rate)
   or as a PX4 `TrajectorySetpoint` in Offboard. Re-send at ≥ 10 Hz: both autopilots stop on timeout.
3. Measure latency camera → command, then tune `k_yaw`, `k_fwd` and `decay_tau` against it.
4. Replace the box-height distance cue with a range estimate (known size or depth) if available.

Sign conventions: `yaw_rate` > 0 turns right (clockwise from above, NED), `vx` forward, `vz` down.
