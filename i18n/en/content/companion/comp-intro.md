---
id: comp-intro
title: "Companion: why and where the boundary is"
level: L2
readingTime: 15 min
firmware: MAVLink / Companion
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
source_hash: 1c07d96adcd3
---

## summary
The flight controller does one thing: it keeps the aircraft in the air and executes simple commands, thousands of times per second and with no right to hang. Everything heavier — computer vision, planning, network connectivity, your own mission logic — lives on the companion computer. This module draws the boundary between them, shows typical configurations from the ESP32 to the Jetson, and explains the main rule: the companion advises, the FC decides.

## theory
### Separation of responsibilities
- **Flight controller (FC):** stabilization, navigation, failsafe, mixer. Hard real time, minimal latency, proven code. It must keep flying even if the companion has hung, rebooted or burned out.
- **Companion:** everything else. Vision, neural networks, map processing, complex scenarios, the internet, logging to the cloud, the operator interface.

{{diagram:companion-system|Companion and flight controller: the FC keeps the aircraft in the air, the companion sees, plans and talks to the network.}}

The boundary follows the reliability requirement: whatever the aircraft would crash without goes on the FC; whatever it would just return home without goes on the companion.

### How they communicate
Via MAVLink over UART (the FC telemetry port) or over a network. The companion is a separate component in the same MAVLink system. It can:

- read telemetry and parameters;
- switch the aircraft to GUIDED and set position/velocity targets;
- upload and start missions;
- receive text messages and status.

What it doesn't do: it doesn't control the motors directly and doesn't replace stabilization. Even with offboard control, the FC itself watches the limits and the failsafe.

### The “advises, doesn't control” rule
The companion proposes “fly to point X at speed Y”. The FC checks the geofence, the battery, the EKF health and executes — or refuses. If the companion stops sending commands, the FC switches to a safe mode on a timeout. That is exactly why the GCS failsafe and GUIDED timeouts are part of the design, not a nuisance.

### Typical platforms
- **ESP32 / ESP32-S3** — a microcontroller with Wi-Fi and BLE. Telemetry to a phone, a MAVLink bridge over Wi-Fi, sensors, indication, small scenarios. No Linux, but instant boot and milliwatts.
- **Raspberry Pi** — Linux, Python, a camera. MAVLink routing, a video stream, mission scripts, logs. The standard first companion.
- **Jetson / Orange Pi with an NPU** — when you need real-time neural networks.

### Protocols and roles
ArduPilot expects MAVLink 2 on `SERIALx_PROTOCOL = 2`; PX4 on the companion port uses the same MAVLink or uXRCE-DDS for ROS 2. For Betaflight/INAV a companion in the classic sense is rare: they have MSP, and an onboard computer is usually needed only for video and telemetry.

### MAVLink routing
One FC port, several consumers (a GCS over 4G, a script on the companion, a logger): you need a router. `mavlink-router` (C++, a systemd service, a config with UART/UDP/TCP endpoints) or `mavproxy.py --master=/dev/ttyAMA0 --out=udp:gcs-ip:14550 --out=udp:127.0.0.1:14551` — each client gets a copy of the stream, and commands go back to the FC. The companion port UART speed: 921600 baud (`SERIALx_BAUD = 921`) — otherwise the port chokes with `SRx_*` streams at 10–50 Hz. The streams are configured from the companion (`REQUEST_DATA_STREAM`/`SET_MESSAGE_INTERVAL`), not by default.

{{diagram:mavlink-routing|A typical onboard MAVLink routing scheme with a companion.}}

### Latency and what you can delegate to the companion
The “companion → FC → response” command loop: UART 1–5 ms + FC processing + velocity loop dynamics of 0.3–1 s. That is fine for “fly to a point” and target tracking (the “Tracking” module), but not for stabilization. The companion must not: control the motors, replace the EKF (except supplying ExternalNav as a source), bypass the failsafe. The companion may: GUIDED/Offboard targets, missions, parameters, ExternalNav/optical flow as a source, the camera and video, logs to the cloud, the operator interface.

### Power, heat, failure
Raspberry Pi 4/5 — 1–3 A at 5 V with peaks up to 5 A: a separate 5 V/5 A BEC, not an FC pad (the “Connecting peripherals” module); Jetson Orin Nano — 7–15 W, 19 V or 5 V/4 A depending on the module; a heatsink and airflow are mandatory — with thermal throttling, latency grows unpredictably. A companion failure (hang, reboot, broken UART) — the FC must survive it: GUIDED timeouts, a GCS failsafe with a deliberate action, a pilot with a no-companion mode on a switch. This is tested by pulling the UART in SITL/on the bench.

### Three typical architectures
1. **Telemetry and bridge**: an ESP32 with bridge firmware (MAVLink over Wi-Fi/BLE to a phone, DroneBridge-class) — decides nothing, only relays.
2. **Pi + camera + scripts**: Raspberry Pi 4/5, mavlink-router, Python mission scripts, a video stream to the GCS, optical flow/rangefinder over MAVLink. The standard for learning and prototypes.
3. **Jetson + ROS 2**: detection/VIO on the GPU, PX4 via uXRCE-DDS or ArduPilot via MAVROS/AP_DDS, nodes with safeguards (the “Tracking” module). For serious autonomy.
Starter repositories for 2 and 3 are in `examples/` in the course repository.

## practice
### Choosing a platform for the task
1. Telemetry on a screen, indication, setup from a phone — ESP32.
2. Video, MAVLink routing, Python scenarios — Raspberry Pi.
3. Object recognition, tracking — Jetson.

### Architecture checklist before a project
1. What does the aircraft do if the companion shuts down in flight? The answer must be “switches to mode X on a timeout”.
2. Which port and at what speed does MAVLink run on? Is there enough bandwidth for telemetry and commands?
3. How is the companion powered? Not from the FC telemetry port.
4. Who logs: the FC to the SD card, the companion its own logs. Do the timestamps match?
5. How do you update the companion software in the field?

### The observer code and what you should get
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
- On port 5762 (SERIAL1), Copter has streams off by default (`SR1_POSITION = 0`, in 4.7 — `MAV2_POSITION`), so without a request the file stays empty. First request a `GLOBAL_POSITION_INT` interval of 1,000,000 µs (`MAV_CMD_SET_MESSAGE_INTERVAL`) — then the file gets one line per second.
- **Failure.** Stop the process (Ctrl+C or `kill`) in flight in LOITER. The aircraft keeps doing what it was doing, because it wasn't expecting anything from the companion. Record this as a fact. If the companion were in control (GUIDED), stopping it would lead to a setpoint timeout — that's the next module.

### Lab
In SITL, bring up a “companion” as a separate pymavlink process (with its own `component_id`) that reads `GLOBAL_POSITION_INT` once a second and writes it to a file. Stop the process in flight and make sure the aircraft didn't notice anything.

The lab counts as done when the process with its own `component_id` is visible in the GCS and writes the position to a file, stopping it in flight didn't change the aircraft's behavior, and the report records what would happen on a failure of a companion controlling in GUIDED.

## diagnostics
- **Symptom:** the aircraft “freezes” or crashes when the companion hangs
  - Possible cause: the companion does what the FC should do (stabilization, direct motor commands).
  - What to do: move the critical parts to the FC, leave the companion only advice via GUIDED.
- **Symptom:** the FC doesn't see the companion
  - Possible cause: wrong port, protocol or baud rate; TX/RX swapped.
  - What to do: `SERIALx_PROTOCOL`, `SERIALx_BAUD`, check the heartbeat via MAVProxy.
- **Symptom:** the companion reboots under throttle
  - Possible cause: power from a weak BEC or a voltage sag.
  - What to do: a separate BEC/regulator with current headroom.

## references
- Companion Computers — ArduPilot Dev | https://ardupilot.org/dev/docs/companion-computers.html | primary | A
- Communicating with Raspberry Pi via MAVLink — ArduPilot Dev | https://ardupilot.org/dev/docs/raspberry-pi-via-mavlink.html | primary | A
- Companion Computers — PX4 User Guide | https://docs.px4.io/main/en/companion_computer/ | primary | A

## checklist
- I can explain what stays on the FC and why
- I know what the aircraft does when the companion fails
- I chose the platform for the task, not the other way around
- The companion is not powered from the telemetry port
- The companion acts as a separate MAVLink component
