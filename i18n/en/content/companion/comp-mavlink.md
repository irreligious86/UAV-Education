---
id: comp-mavlink
title: "MAVLink and MAVSDK"
level: L2
readingTime: 30 min
firmware: MAVLink 2 · ArduPilot 4.7 (checked against 4.7.3)
status: published
added: 2026-11-07
tags:
  - MAVLink
  - pymavlink
  - MAVSDK
related:
  - ap-sitl
  - comp-esp32
next:
  - comp-esp32
source: content/companion/comp-mavlink.md
source_hash: 9b5ca1e47bc0
---

## summary
MAVLink is the language the flight controller speaks with the ground control station, the companion computer, telemetry radios, and your scripts. Everything you did in SITL through pymavlink was MAVLink. This module takes the protocol apart far enough for you to write your own clients: the packet structure, system and component, the heartbeat, acknowledged commands, parameters, telemetry streams. Two tools to choose from: pymavlink (low level, everything visible) and MAVSDK (a high-level API).

## theory
### The packet
MAVLink 2 is a binary protocol over UART, UDP, or TCP. A packet holds the start marker `0xFD`, the length, flags, a sequence number, `system_id`, `component_id`, a three-byte message ID, the payload, and a CRC. The checksum includes a "seed" derived from the message definition, so both sides must use the same definitions (dialect). Messages are defined in XML: `common.xml` holds the common set, `ardupilotmega.xml` the ArduPilot extensions. Libraries for C, Python, and other languages are generated from the XML.

### System and component
`system_id` is the vehicle (1 by default); `component_id` is what is inside it: the autopilot (1), a camera, a gimbal, an onboard computer. A GCS is usually system 255. Commands are addressed to a system + component pair; an onboard computer is a separate component of the same system.

### Heartbeat
`HEARTBEAT` (ID 0) is sent once a second by every participant: vehicle type, autopilot, mode, arming state. No heartbeat means no connection, which is why every client starts with `wait_heartbeat()`. A missing GCS heartbeat for longer than the timeout is the GCS failsafe.

### Core messages
- Telemetry from the vehicle: `SYS_STATUS` (1), `ATTITUDE` (30), `GLOBAL_POSITION_INT` (33), `RC_CHANNELS` (65), `BATTERY_STATUS` (147), `STATUSTEXT` (253, text messages, pre-arm ones included).
- Commands: `COMMAND_LONG` (76) with a `MAV_CMD_*` code and seven parameters; the reply is `COMMAND_ACK` (77) with the result. Example codes: `MAV_CMD_COMPONENT_ARM_DISARM` (400), `MAV_CMD_NAV_TAKEOFF` (22), `MAV_CMD_DO_SET_MODE` (176).
- Stream rates: `MAV_CMD_SET_MESSAGE_INTERVAL` (511) requests a specific message at a given interval; `MAV_CMD_REQUEST_MESSAGE` (512) requests it once.
- Parameters: `PARAM_REQUEST_READ` (20) → `PARAM_VALUE` (22); writing is `PARAM_SET` (23), confirmed by the same `PARAM_VALUE`.
- GUIDED control: `SET_POSITION_TARGET_LOCAL_NED` (84) and `SET_POSITION_TARGET_GLOBAL_INT` (86) set a position or velocity target; the basis of offboard control from a companion.
- Missions: `MISSION_COUNT` (44), `MISSION_ITEM_INT` (73), `MISSION_REQUEST_INT` (51; when receiving a mission, ArduPilot 4.7 sends `MISSION_REQUEST` (40) and accepts `MISSION_ITEM_INT` in reply), `MISSION_ACK` (47): the exchange from the missions module.

### The acknowledgment rule
A command without a `COMMAND_ACK` check is hope, not control. `MAV_RESULT_ACCEPTED` (0) means "accepted"; any other code is a rejection, and the reason usually arrives in a `STATUSTEXT`.

### pymavlink vs MAVSDK
- **pymavlink** is a thin wrapper over the protocol: you see every message, which suits learning, troubleshooting, and anything non-standard. The code is verbose.
- **MAVSDK** (C++, Python) offers high-level actions: `arm()`, `takeoff()`, `goto_location()`, telemetry subscriptions. Faster for writing applications, less visibility into what happens inside. Historically closer to PX4, but it works with ArduPilot.

### A MAVLink 2 frame byte by byte
`FD | len | incompat_flags | compat_flags | seq | sysid | compid | msgid(3) | payload(len) | crc(2) | [signature(13)]`. Bit 0 of `incompat_flags` means the packet is signed; the signature is the first 48 bits of a SHA-256 hash of (secret key + header + payload + CRC + link_id + timestamp), not an HMAC (it protects against spoofed commands over an open radio link; you set the key in Mission Planner/QGC, and it reaches the autopilot in a `SETUP_SIGNING` message). The checksum is CRC-16/MCRF4XX over the frame plus the message's `CRC_EXTRA` byte (from the XML): mismatched dialects mean "silence". The payload is shortened by truncating trailing zero bytes (which is why `len` is smaller than the struct size). Parameters in `PARAM_VALUE` are always a float (32 bit): ArduPilot converts integers to float with a C cast, PX4 encodes them byte-wise; the value type is in `param_type` (`MAV_PARAM_TYPE`), an easy thing to trip over in pymavlink.

{{diagram:mavlink2-frame|A MAVLink 2 frame: header, system and component IDs, payload, CRC with CRC_EXTRA, optional signature.}}

### Telemetry streams: who sets the rate
ArduPilot sends streams according to the `MAVn_*` parameters of each MAVLink channel (`MAV3_EXTRA1` for ATTITUDE, `MAV3_POSITION` for GLOBAL_POSITION_INT, `MAV3_RAW_SENS` for RAW_IMU…), in Hz; before 4.7 these were `SRn_*`, numbered from zero (`SR2_EXTRA1` is today's `MAV3_EXTRA1`), and `SRn_*` values are not carried over on upgrade. The modern way is `MAV_CMD_SET_MESSAGE_INTERVAL` (511) from the client: an interval in µs (−1 disables, 0 restores the default). PX4 uses `MAV_x_MODE` profiles (Normal/Onboard/OSD…). A 921600-baud port carries ~90 KB/s: ATTITUDE at 50 Hz + position (GLOBAL_POSITION_INT) at 10 Hz + RAW_IMU at 50 Hz, in MAVLink 2 frames of 40, 40, and 41 bytes (payloads of 28, 28, and 29 bytes + 12 bytes of header and CRC, unsigned), comes to ~4.5 KB/s, with room to spare; at 57600 (~5.8 KB/s at 10 bits per byte) the same set would take ~77 % of the port, and a telemetry radio's air link is also shared half-duplex and cut down by ECC, which is why anything above 5–10 Hz saturates it.

### Worked example: a reliable command
```python
def cmd(m, command, *params, retries=3, timeout=1.0):
    """Send COMMAND_LONG and wait for a matching ACK; retry on timeout; raise on rejection."""
    p = list(params) + [0] * (7 - len(params))
    for _ in range(retries):
        m.mav.command_long_send(m.target_system, m.target_component, command, 0, *p)
        t0 = time.time()
        while time.time() - t0 < timeout:
            ack = m.recv_match(type="COMMAND_ACK", blocking=True, timeout=timeout)
            if ack and ack.command == command:
                if ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED: return True
                if ack.result == mavutil.mavlink.MAV_RESULT_IN_PROGRESS: continue
                raise RuntimeError(f"cmd {command} rejected: result {ack.result}")
    raise TimeoutError(f"cmd {command}: no ACK")
```
A `STATUSTEXT` explains the rejection alongside it ("PreArm: …"). MAVSDK does the same under the hood, but you need to understand what is inside to read a tlog during analysis.

{{diagram:mav-cmd-ack-flow|The worked command as a diagram: wait for the ACK of this specific command, IN_PROGRESS means keep waiting, a rejection raises an exception with the reason in STATUSTEXT, silence means retry, and after three tries a TimeoutError.}}

### Where it fits in the system

- **Takes in:** bytes from a transport: UART, UDP, a telemetry radio (`mav-routing`, `link-telemetry-radios`); message definitions from an XML dialect, the same on both sides (`mav-protocol`).
- **Puts out:** telemetry (`ATTITUDE`, `GLOBAL_POSITION_INT`, `STATUSTEXT`) to scripts and the GCS; commands, parameters, and GUIDED targets to the autopilot (`ap-companion`); the mission upload exchange (`ap-missions`).
- **If you get this wrong:** a command without a `COMMAND_ACK` check → the script assumes arming or takeoff went through, while the autopilot rejected it on a pre-arm check; the reason is in a `STATUSTEXT`, and the exchange is taken apart in `mav-services`. Streams above 5–10 Hz at 57600 → the telemetry radio saturates and the GCS loses packets (`link-telemetry-radios`).

## practice
### Step 1. Listen to telemetry
```python
from pymavlink import mavutil

m = mavutil.mavlink_connection("tcp:127.0.0.1:5762")
m.wait_heartbeat()
print(f"system {m.target_system} component {m.target_component}")

# ask for ATTITUDE at 10 Hz (interval in microseconds)
m.mav.command_long_send(
    m.target_system, m.target_component,
    mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
    mavutil.mavlink.MAVLINK_MSG_ID_ATTITUDE, 100_000, 0, 0, 0, 0, 0)

for _ in range(20):
    msg = m.recv_match(type=["ATTITUDE", "STATUSTEXT"], blocking=True)
    if msg.get_type() == "ATTITUDE":
        print(f"roll {msg.roll:+.2f} pitch {msg.pitch:+.2f} yaw {msg.yaw:+.2f} rad")
    else:
        print("FC says:", msg.text)
```

### Step 2. An acknowledged command
```python
def command(m, cmd, *params):
    m.mav.command_long_send(m.target_system, m.target_component, cmd, 0, *params)
    ack = m.recv_match(type="COMMAND_ACK", blocking=True, timeout=3)
    if ack is None or ack.command != cmd:
        raise RuntimeError(f"no ACK for {cmd}")
    if ack.result != mavutil.mavlink.MAV_RESULT_ACCEPTED:
        raise RuntimeError(f"command {cmd} rejected: result {ack.result}")

m.set_mode(m.mode_mapping()["GUIDED"])
command(m, mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 1, 0, 0, 0, 0, 0, 0)
command(m, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 15)
```

### Step 3. Parameters
```python
m.mav.param_request_read_send(m.target_system, m.target_component, b"FS_THR_ENABLE", -1)
p = m.recv_match(type="PARAM_VALUE", blocking=True)
print(p.param_id, p.param_value)
```

### Step 4. Listen to the link
Run `mavproxy.py --master=tcp:127.0.0.1:5762` and the `watch ATTITUDE` command: you see the live message stream. That is the best way to understand what actually travels over the link before you write code.

### What you should see and what to write down
- **Step 1.** In SITL the first heartbeat comes from system 1, component 1 (the autopilot). Do not take the rate on faith; measure it: collect 50 `ATTITUDE` messages and divide the number of intervals (49) by the difference between the first and last `time_boot_ms` (in seconds). Expect 9.5–10.5 Hz for a 100 000 µs interval. If `ATTITUDE` never arrives, the interval command did not get through: on port 5762 Copter's default rate (`MAV2_EXTRA1`; `SR1_EXTRA1` before 4.7) is 0. Around 4 Hz is the rate MAVProxy itself requests on its port, 5760.
- **Step 2.** Repeat the arm right after SITL starts, before the EKF has converged. You get a `COMMAND_ACK` with result 4 (`MAV_RESULT_FAILED`), and the reason in a `STATUSTEXT` with the `PreArm:` prefix. Write down both lines: this is what a rejection your code must handle looks like. Result codes: 0 accepted, 1 temporarily rejected, 2 denied, 3 unsupported, 4 failed, 5 in progress.
- **Step 3.** Writing a parameter is a `PARAM_SET` and a `PARAM_VALUE` reply with the new value. Until the reply arrives, the parameter is not written:

```python
m.mav.param_set_send(m.target_system, m.target_component, b"FS_THR_ENABLE", 1,
                     mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=3)
assert p and p.param_id == "FS_THR_ENABLE" and p.param_value == 1, p
```

- **Step 4.** `watch ATTITUDE` shows the rate and the live angles. Compare the rate with the one you measured in step 1. In the flight from the "SITL" module the angles change with every maneuver: that is how you confirm the stream is live, not frozen.

Self-check: the lab is done when the `ATTITUDE` rate is measured (not assumed) and falls within 9.5–10.5 Hz, the rejected arm gave a `COMMAND_ACK` with result 4 and a `STATUSTEXT` with the `PreArm:` prefix while the successful arm gave result 0, the parameter was written with the `PARAM_VALUE` reply checked (the `assert` from step 3 passed), and the rate in MAVProxy's `watch ATTITUDE` matches the one measured in step 1.

## diagnostics
- **Symptom:** `wait_heartbeat()` never returns
  - Possible cause: wrong address/port, wrong dialect, UART baud rate.
  - What to do: check the port, the baud rate (57600 or 115200 on telemetry), and that SITL is running.
- **Symptom:** the command "went through", but the vehicle did nothing
  - Possible cause: `COMMAND_ACK` was not checked; the command was rejected.
  - What to do: read the ACK and the `STATUSTEXT`.
- **Symptom:** telemetry arrives rarely
  - Possible cause: default stream intervals.
  - What to do: `MAV_CMD_SET_MESSAGE_INTERVAL` for the messages you need.
- **Symptom:** CRC errors, "unknown" messages
  - Possible cause: different definition versions on the two sides.
  - What to do: update pymavlink/MAVSDK and use the same dialect (ardupilotmega).

## references
- MAVLink Developer Guide | https://mavlink.io/en/ | primary | A
- MAVLink common message set | https://mavlink.io/en/messages/common.html | primary | A
- pymavlink — source code (GitHub) | https://github.com/ArduPilot/pymavlink | primary | A
- MAVSDK — Documentation | https://mavsdk.mavlink.io/main/en/ | primary | A
- MAVLink Interface — ArduPilot Dev | https://ardupilot.org/dev/docs/mavlink-basics.html | primary | A

## checklist
- I understand system_id / component_id and the heartbeat
- Every command is checked against `COMMAND_ACK`
- I can request telemetry at the rate I need
- I read and write parameters from code
- I know when to use pymavlink and when MAVSDK
