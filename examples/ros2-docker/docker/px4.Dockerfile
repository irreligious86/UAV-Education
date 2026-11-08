# PX4 SITL with Gazebo Harmonic (gz_x500). Heavy: ~20 GB build context and 30+ minutes on first build.
FROM ubuntu:22.04
ARG DEBIAN_FRONTEND=noninteractive
ARG PX4_REF=v1.16.0
RUN apt-get update && apt-get install -y --no-install-recommends git sudo ca-certificates lsb-release tzdata \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt
RUN git clone --recursive --depth 1 -b ${PX4_REF} https://github.com/PX4/PX4-Autopilot.git
RUN bash PX4-Autopilot/Tools/setup/ubuntu.sh --no-nuttx
WORKDIR /opt/PX4-Autopilot
RUN make px4_sitl
# headless by default; the uXRCE-DDS client connects to the agent at $PX4_UXRCE_DDS_AG_IP (see compose)
ENV HEADLESS=1
CMD ["make", "px4_sitl", "gz_x500"]
