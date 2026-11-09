# ROS 2 workspace: px4_msgs, ardupilot_msgs, Micro XRCE-DDS Agent (PX4), micro-ROS agent (ArduPilot AP_DDS),
# and the course package uav_ros2_labs.
# ROS_DISTRO: jazzy (default, LTS to 2029, Ubuntu 24.04) or humble (fallback, Ubuntu 22.04).
ARG ROS_DISTRO=jazzy
FROM ros:${ROS_DISTRO}-ros-base
ARG ROS_DISTRO

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      git python3-pip python3-colcon-common-extensions ros-${ROS_DISTRO}-geographic-msgs ros-${ROS_DISTRO}-launch-ros \
      ros-${ROS_DISTRO}-rmw-cyclonedds-cpp ros-${ROS_DISTRO}-rosbag2 \
    && rm -rf /var/lib/apt/lists/*

# Micro XRCE-DDS Agent for PX4's uXRCE-DDS client (pinned release)
WORKDIR /opt
# Installed into its own prefix: its bundled Fast-CDR must not shadow the one ROS ships (Humble uses Fast-CDR 1.x,
# and micro_ros_agent below fails to compile against 2.x headers in /usr/local).
RUN git clone --depth 1 -b v2.4.3 https://github.com/eProsima/Micro-XRCE-DDS-Agent.git \
 && cmake -S Micro-XRCE-DDS-Agent -B Micro-XRCE-DDS-Agent/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/xrce \
 && cmake --build Micro-XRCE-DDS-Agent/build -j"$(nproc)" && cmake --install Micro-XRCE-DDS-Agent/build \
 && echo /opt/xrce/lib > /etc/ld.so.conf.d/xrce.conf && ldconfig
ENV PATH=/opt/xrce/bin:$PATH

WORKDIR /ws
# px4_msgs must match the PX4 release you fly (message versioning since v1.16)
ARG PX4_MSGS_REF=release/1.16
RUN mkdir -p src && git clone --depth 1 -b ${PX4_MSGS_REF} https://github.com/PX4/px4_msgs.git src/px4_msgs
# ardupilot_msgs lives in the ArduPilot repository under Tools/ros2
RUN git clone --depth 1 --filter=blob:none --sparse https://github.com/ArduPilot/ardupilot.git /tmp/ap \
 && git -C /tmp/ap sparse-checkout set Tools/ros2/ardupilot_msgs \
 && cp -r /tmp/ap/Tools/ros2/ardupilot_msgs src/ && rm -rf /tmp/ap
# micro-ROS agent (used by ArduPilot AP_DDS)
RUN git clone --depth 1 -b ${ROS_DISTRO} https://github.com/micro-ROS/micro_ros_setup.git src/micro_ros_setup

COPY ws/src/uav_ros2_labs src/uav_ros2_labs
RUN . /opt/ros/${ROS_DISTRO}/setup.sh && apt-get update && rosdep update \
 && rosdep install --from-paths src --ignore-src -y --skip-keys "px4_msgs ardupilot_msgs" \
 && rm -rf /var/lib/apt/lists/*
RUN . /opt/ros/${ROS_DISTRO}/setup.sh && colcon build --packages-select micro_ros_setup \
 && . install/setup.sh && ros2 run micro_ros_setup create_agent_ws.sh && ros2 run micro_ros_setup build_agent.sh
RUN . /opt/ros/${ROS_DISTRO}/setup.sh && . install/setup.sh \
 && colcon build --packages-select px4_msgs ardupilot_msgs uav_ros2_labs

ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
RUN echo "source /opt/ros/${ROS_DISTRO}/setup.bash && source /ws/install/setup.bash" >> /root/.bashrc
CMD ["bash"]
