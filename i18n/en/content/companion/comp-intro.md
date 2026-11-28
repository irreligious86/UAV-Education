---
id: comp-intro
title: "Companion computers: why, and where the boundary is"
level: L2
readingTime: 15 min
firmware: ArduPilot 4.7 (checked against 4.7.3) · MAVLink 2
status: published
added: 2026-11-07
tags:
  - companion
  - architecture
related:
  - comp-mavlink
  - ap-intro
next:
  - comp-mavlink
source: content/companion/comp-intro.md
source_hash: 39faf4080aaa
---

## summary
A flight controller does one job: it keeps the vehicle in the air and executes simple commands, thousands of times a second, and it is never allowed to hang. Anything heavier (computer vision, planning, network links, your own mission logic) lives on the companion computer. This module draws the line between the two, walks through typical setups from an ESP32 to a Jetson, and explains the core rule: the companion advises, the FC decides.

## theory
### Who is responsible for what
- **Flight controller (FC):** stabilization, navigation, failsafes, the mixer. Hard real time, minimal latency, proven code. It has to keep flying even if the companion hangs, reboots, or burns out.
- **Companion:** everything else. Vision, neural networks, map processing, complex behaviors, the internet, cloud logging, the operator interface.

{{diagram:companion-system|Companion computer and flight controller: the FC keeps the vehicle in the air; the companion sees, plans, and talks to the network.}}

The line is drawn by reliability: whatever the vehicle would crash without goes on the FC; whatever it would merely return home without goes on the companion.

### How they talk
Over MAVLink, on a UART (an FC telemetry port) or over a network. The companion is a separate component in the same MAVLink system. It can:

- read telemetry and parameters;
- switch the vehicle to GUIDED and send position or velocity targets;
- upload and start missions;
- receive status text messages and vehicle state.

What it does not do: drive the motors directly or replace stabilization. Even under offboard control the FC enforces its own limits and failsafes.

### The "advise, don't control" rule
The companion proposes "fly to point X at speed Y". The FC checks the geofence, the battery, and EKF health, then executes the request or rejects it. If the companion stops sending commands, the FC falls back to safe behavior on its own after a timeout: in Copter, velocity, acceleration, and angle targets last `GUID_TIMEOUT` (3 s), after which velocity targets are zeroed (the vehicle brakes and holds) and angle targets level out with zero climb rate (no position hold, so it drifts with the wind). That is why the GCS failsafe and the GUIDED timeouts are part of the design, not an obstacle.

### Typical platforms
- **ESP32 / ESP32-S3:** a microcontroller with Wi-Fi and BLE. Telemetry to a phone, a MAVLink bridge over Wi-Fi, sensors, status indication, small scripted behaviors. No Linux, but instant boot and well under a watt.
- **Raspberry Pi:** Linux, Python, a camera. MAVLink routing, video streaming, mission scripts, logs. The standard first companion.
- **Jetson / Orange Pi with an NPU:** when you need neural networks in real time.

### Protocols and roles
ArduPilot expects MAVLink 2 with `SERIALx_PROTOCOL = 2`; PX4 on its companion port speaks the same MAVLink or uXRCE-DDS for ROS 2. A companion in the classic sense is rare with Betaflight/INAV: they have MSP, and an onboard computer is usually there only for video and telemetry.

### MAVLink routing
One FC port, several consumers (a GCS over 4G, a script on the companion, a logger): you need a router. Use `mavlink-router` (C++, a systemd service, a config file with UART/UDP/TCP endpoints) or `mavproxy.py --master=/dev/ttyAMA0 --out=udp:gcs-ip:14550 --out=udp:127.0.0.1:14551`: every client gets a copy of the stream, and commands flow back to the FC. Run the companion UART at 921600 baud (`SERIALx_BAUD = 921`); otherwise `MAVn_*` streams (`SRn_*` before ArduPilot 4.7) at 10–50 Hz saturate the port. Streams are requested by the companion (`REQUEST_DATA_STREAM`/`MAV_CMD_SET_MESSAGE_INTERVAL`); they are not on by default.

{{diagram:mavlink-routing|A typical onboard MAVLink routing layout with a companion computer.}}

### Latency, and what to hand to the companion
The "companion → FC → response" loop: 1–5 ms on the UART, plus FC processing, plus the velocity loop dynamics of 0.3–1 s. That is fine for "fly to a point" and for target following (the "Target tracking and target-based control" module), but not for stabilization. The companion must not: drive the motors, replace the EKF (other than feeding ExternalNav as a source), or bypass failsafes. The companion may: send GUIDED/Offboard targets, run missions, set parameters, provide ExternalNav or optical flow as a source, handle the camera and video, push logs to the cloud, run the operator interface.

### Power, heat, failure
A Raspberry Pi 4/5 draws 0.6–3 A at 5 V depending on load and USB peripherals, so size the BEC for 5 A (the Pi 5 PSU spec): give it a dedicated 5 V/5 A BEC, not an FC pad (the "Connecting Peripherals" module). A Jetson Orin Nano draws 7–15 W (up to 25 W in the Super configuration) and its devkit barrel jack takes 9–20 V (it ships with a 19 V supply); 5 V/4 A is the old 2019 Jetson Nano (figures from the `comp-jetson-nano` module). A heatsink and airflow are mandatory: once it throttles on temperature, latency grows unpredictably. A companion failure (a hang, a reboot, a broken UART link) is something the FC must survive: GUIDED timeouts, a GCS failsafe with a deliberately chosen action, and a pilot with a companion-free mode on a switch. Test it by pulling the UART in SITL or on the bench.

### Three typical architectures
1. **Telemetry and bridge:** an ESP32 running bridge firmware (MAVLink over Wi-Fi/BLE to a phone, DroneBridge-style). It decides nothing; it only relays.
2. **Pi + camera + scripts:** a Raspberry Pi 4/5, mavlink-router, Python mission scripts, a video stream to the GCS, optical flow/rangefinder over MAVLink. The standard for learning and prototypes.
3. **Jetson + ROS 2:** detection/VIO on the GPU, PX4 over uXRCE-DDS or ArduPilot over MAVROS/AP_DDS, nodes with safeguards (the "Target tracking and target-based control" module). For serious autonomy.
Starter code for 2 and 3 is in `examples/` in the course repository.

### Where it fits in the system

- **Takes in:** telemetry and parameters from the flight controller over a UART in MAVLink (`comp-mavlink`); 5 V power from a dedicated BEC, not from an FC pad (`el-peripherals`).
- **Puts out:** GUIDED position and velocity targets, missions (`ap-companion`); rangefinder data and ExternalNav as an EKF source (`mav-component`); copies of the stream for the GCS and the logger through a router (`mav-routing`).
- **If you get this wrong:** a companion on a weak BEC reboots under throttle → the GUIDED targets stop coming, and after the timeout the autopilot stops the vehicle (`GUID_TIMEOUT`); in the log this looks like a link failure, analyzed in `ap-safety-fs`. A port at a low baud rate with 10–50 Hz streams saturates → telemetry drops for every consumer; the bandwidth math is in `comp-mavlink`.

## practice
### Picking a platform for the job
1. Telemetry on a screen, status indication, settings from a phone: ESP32.
2. Video, MAVLink routing, Python scripts: Raspberry Pi.
3. Object detection, target following: Jetson.

### Architecture checklist before a project
1. What does the vehicle do if the companion shuts down in flight? The answer must be "it switches to mode X after a timeout".
2. Which port and what baud rate carry MAVLink? Is there enough bandwidth for telemetry and commands?
3. How is the companion powered? Not from the FC telemetry port.
4. Who logs what: the FC to its SD card, the companion its own logs. Do the timestamps line up?
5. How do you update the companion software in the field?

### Observer code and what you should see
```python
import time
from pymavlink import mavutil

# own identity: system 1 (this vehicle), component 191 = onboard computer
m = mavutil.mavlink_connection("tcp:127.0.0.1:5762", source_system=1,
                               source_component=mavutil.mavlink.MAV_COMP_ID_ONBOARD_COMPUTER)
m.wait_heartbeat()
with open("companion_track.csv", "a") as f:
    last_hb = 0.0
    while True:
        if time.time() - last_hb > 1.0:          # say "I am here" once a second, like a real companion
            m.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER,
                                 mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
            last_hb = time.time()
        p = m.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=1)
        if p:
            f.write(f"{time.monotonic():.3f},{p.lat / 1e7:.7f},{p.lon / 1e7:.7f},{p.relative_alt / 1000:.1f}\n")
            f.flush()
```
- In the GCS (MAVLink Inspector) a second participant appears: component 191 of the same system. That is how a companion looks to the rest of the network.
- On port 5762 (SERIAL1) Copter's streams are off by default (`MAV2_POSITION = 0`; `SR1_POSITION` before 4.7), so without a request the file stays empty. First request a `GLOBAL_POSITION_INT` interval of 1 000 000 µs (`MAV_CMD_SET_MESSAGE_INTERVAL`); then the file gets one line per second.
- **Failure.** Stop the process (Ctrl+C or `kill`) while flying in LOITER. The vehicle keeps doing what it was doing, because it was not waiting for anything from the companion. Write that down as a fact. If the companion had been in control (GUIDED), stopping it would have made the targets time out; that is the next module.

### Lab
In SITL, start a "companion" as a separate pymavlink process (its own `component_id`) that reads `GLOBAL_POSITION_INT` once a second and writes it to a file. Stop the process in flight and confirm the vehicle did not notice.

Self-check: the lab is done when the process with its own `component_id` shows in the GCS as component 191 of the same system, `companion_track.csv` gains one line per second after the interval request, stopping it in flight did not change the vehicle's behavior, and your notes say what would have happened if a companion controlling the vehicle in GUIDED had failed.

**Reference answer for self-check.** A correct note: the observer is stopped, and the vehicle in LOITER keeps doing what it was doing, because it was not waiting for anything from the companion; had the companion been controlling it in GUIDED, the targets would have stopped, and after the timeout the autopilot would have stopped the vehicle; in the log this looks like a link failure. Common mistake #1: the file is empty because the `GLOBAL_POSITION_INT` interval was never requested, and streams on port 5762 are off by default. Common mistake #2: notes saying "without the companion the vehicle crashes" or "nothing changes in any mode": that mixes up who is responsible for what. The companion does not control the motors or stabilization, and the autopilot has to handle the missing targets by itself, on a timeout.

## diagnostics
- **Symptom:** the vehicle "freezes" or crashes when the companion hangs
  - Possible cause: the companion is doing the FC's job (stabilization, direct motor commands).
  - What to do: move the critical parts to the FC and leave the companion only advice through GUIDED.
- **Symptom:** the FC does not see the companion
  - Possible cause: wrong port, protocol, or baud rate; TX/RX swapped.
  - What to do: check `SERIALx_PROTOCOL` and `SERIALx_BAUD`, and look for the heartbeat in MAVProxy.
- **Symptom:** the companion reboots under throttle
  - Possible cause: power from a weak BEC, or voltage sag.
  - What to do: a dedicated BEC/regulator with current headroom.

## references
- Companion Computers — ArduPilot Dev | https://ardupilot.org/dev/docs/companion-computers.html | primary | A
- Communicating with Raspberry Pi via MAVLink — ArduPilot Dev | https://ardupilot.org/dev/docs/raspberry-pi-via-mavlink.html | primary | A
- Companion Computers — PX4 User Guide | https://docs.px4.io/v1.17/en/companion_computer/index.html | primary | A

## checklist
- I can explain what stays on the FC and why
- I know what the vehicle does when the companion fails
- I picked the platform for the job, not the other way around
- The companion is not powered from the telemetry port
- The companion appears as a separate MAVLink component
