# ArduPilot SITL (Copter) built with DDS support.
FROM ubuntu:22.04
ARG DEBIAN_FRONTEND=noninteractive
ARG AP_REF=master
RUN apt-get update && apt-get install -y --no-install-recommends git sudo ca-certificates lsb-release tzdata python3-pip \
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m ap && echo "ap ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/ap
USER ap
WORKDIR /home/ap
RUN git clone --recursive --depth 1 -b ${AP_REF} https://github.com/ArduPilot/ardupilot.git
WORKDIR /home/ap/ardupilot
RUN USER=ap Tools/environment_install/install-prereqs-ubuntu.sh -y
RUN ./waf configure --board sitl --enable-DDS && ./waf copter
ENV PATH=/home/ap/ardupilot/Tools/autotest:$PATH
# DDS over UDP to the agent container (DDS_IP0..3 / DDS_UDP_PORT parameters), MAVLink on 14550 for QGC
CMD ["bash", "-lc", "sim_vehicle.py -v ArduCopter --enable-DDS --no-mavproxy -w -A '--defaults Tools/autotest/default_params/copter.parm'"]
