# ROS 2 labs environment

Containers and a ROS 2 package for the elective "ROS 2 on board" (`ros2-basics`, `ros2-px4`,
`ros2-ardupilot`). Target: ROS 2 Jazzy on Ubuntu 24.04 (LTS to 2029, recommended by current PX4 docs),
PX4 SITL + Gazebo Harmonic, ArduPilot SITL built with `--enable-DDS`. The image is built and smoke-tested in CI for **Jazzy only** (`.github/workflows/ros2-image.yml`).
`ROS_DISTRO=humble` is accepted by the build argument but currently fails: the humble branch of
micro-ROS-Agent does not compile against the Fast-CDR 2.x it pulls in (`DDS_CDR` / `getSerializedDataLength`
errors in `graph_typesupport.cpp`). On Ubuntu 22.04 hosts use this image anyway (it is Ubuntu 24.04 inside), or
install ROS 2 Humble natively and build the agents by hand.

```bash
docker compose build ros                       # ROS 2 workspace (~10 min)
docker compose run --rm ros bash               # shell with px4_msgs, ardupilot_msgs, the course package
docker compose --profile px4 up --build        # + PX4 SITL gz_x500 + MicroXRCEAgent udp4 :8888 (heavy first build)
docker compose --profile ardupilot up --build  # + ArduPilot SITL (DDS) + micro_ros_agent udp4 :2019
```

Inside the `ros` shell:

```bash
ros2 topic list                                         # /fmu/... (PX4) or /ap/... (ArduPilot)
ros2 launch uav_ros2_labs px4_square.launch.py          # logger + offboard square
ros2 launch uav_ros2_labs ap_square.launch.py           # logger + GUIDED square over AP_DDS
ros2 bag record -o /bags/flight1 /fmu/out/vehicle_local_position_v1 /fmu/out/vehicle_status_v1
```

## What is verified where

| Part | Verified by |
|---|---|
| `uav_ros2_labs/frames.py`, `offboard_fsm.py` (all flight logic, no ROS imports) | `pytest ws/src/uav_ros2_labs/test` — runs in this repository's CI |
| Nodes (`telemetry_logger`, `px4_offboard_square`, `ap_dds_square`) | byte-compiled in CI; run them in the containers against SITL |
| Dockerfiles / compose | YAML validated in CI; image builds need Docker Hub and GitHub access and were not run in CI |

Versions are pinned via build args (`PX4_REF`, `PX4_MSGS_REF`, `AP_REF`). `px4_msgs` **must** match the
PX4 release: since v1.16 versioned messages publish on topics with a `_v<N>` suffix, and the nodes derive
the suffix from `MESSAGE_VERSION` so the same code works on both sides of that change.

Gazebo GUI: run PX4 with `HEADLESS=1` (default here) and connect QGroundControl from the host on UDP 14550,
or run the simulator natively and only the ROS 2 workspace in Docker (`network_mode: host`).
