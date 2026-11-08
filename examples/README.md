# Starter repositories

Minimal, runnable starting points for the autonomy and companion modules.
Each folder is self-contained; copy it out of this repository to begin a project.

| Folder | What it gives you | Course modules |
|---|---|---|
| `sitl-pymavlink/` | ArduPilot SITL in Docker + a pymavlink script that arms, takes off, flies a square and lands; a failsafe test runnable in CI | comp-mavlink, ap-sitl, eng-ci-configs, per-tracking |
| `ros2-skeleton/` | ROS 2 package layout for a companion node talking to PX4 (uXRCE-DDS) or ArduPilot (MAVROS), with a velocity-setpoint publisher stub | px4-ros2, per-tracking |

Goal: a simulation on screen in 15 minutes, not an afternoon of dependencies.
