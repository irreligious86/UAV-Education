# Starter repositories

Minimal, runnable starting points for the autonomy and companion modules.
Each folder is self-contained; copy it out of this repository to begin a project.

| Folder | What it gives you | Course modules |
|---|---|---|
| `sitl-pymavlink/` | ArduPilot SITL in Docker + a pymavlink script that arms, takes off, flies a square and lands; a failsafe test runnable in CI | comp-mavlink, ap-sitl, eng-ci-configs, per-tracking |
| `mavlink/` | MAVLink from the wire up: frame decoder and CRC, reliable command/param/mission client, a virtual rangefinder component, a lossy fake vehicle; 12 pytest tests without SITL | mav-protocol, mav-services, mav-routing, mav-component, mav-sdk |
| `ros2-docker/` | Docker Compose environment (ROS 2 Humble, PX4 SITL + Gazebo, ArduPilot SITL with DDS) and the `uav_ros2_labs` package: telemetry logger, PX4 offboard square, ArduPilot AP_DDS square; flight logic as a tested state machine | ros2-basics, ros2-px4, ros2-ardupilot |
| `ros2-skeleton/` | ROS 2 package layout for a companion node talking to PX4 (uXRCE-DDS) or ArduPilot (MAVROS), with a velocity-setpoint publisher stub | px4-ros2, per-tracking |
| `web-gcs/` | Project #1 starter: MAVLink → WebSocket bridge with ACK-confirmed commands and link-loss detection, a Leaflet UI, protocol doc, 6 tests | mav-services, mav-routing, projects/proj-web-gcs |
| `perception/` | Camera geometry (pixel → ground, distortion, mount extrinsics, GSD/survey spacing, LANDING_TARGET angles), depth → OBSTACLE_DISTANCE sectors, stopping-distance budget, inference latency bench; 14 tests | per-geometry, per-landing, per-depth-avoid, per-mapping, per-edge-ml |
| `precision-landing/` | Project #5 starter: synthetic downward camera over SITL state, delayed LANDING_TARGET sender (sign convention checked against ArduPilot), touchdown statistics; 7 tests | per-landing, projects/proj-precision-landing |
| `follow-target/` | Project #4 starter: follow controller as a pure function (bbox → body velocity + yaw rate, limits, slew, target-lost watchdog); 7 tests | per-tracking, projects/proj-detect-follow |
| `blackbox-grader/` | Betaflight Blackbox grader (filters, tracking, motors, RPM telemetry) on blackbox_decode CSV, synthetic fixtures with known defects; 8 tests | bf-blackbox, bf-filters, bf-rpm-filter, bf-pid |

Goal: a simulation on screen in 15 minutes, not an afternoon of dependencies.
