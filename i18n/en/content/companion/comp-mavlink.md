---
id: comp-mavlink
title: "MAVLink and MAVSDK"
level: L2
readingTime: 30 min
firmware: MAVLink 2
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
source_hash: e3e4078d2bf6
---

## summary
MAVLink is the language the flight controller uses to talk to the ground control station, the companion computer, telemetry and your scripts. Everything you did in SITL via pymavlink is MAVLink. This module takes the protocol apart at a level sufficient to write your own clients: the packet structure, system and component, heartbeat, commands with acknowledgment, parameters, telemetry streams. Two tools to choose from: pymavlink (low level, everything is visible) and MAVSDK (a high-level API).

## theory
### The packet
MAVLink 2 is a binary protocol over UART, UDP or TCP. The packet: the start byte `0xFD`, length, flags, sequence number, `system_id`, `component_id`, a three-byte message ID, the payload, CRC. The checksum includes a “salt” from the message definition, so both sides must use identical definitions (the dialect). Messages are described in XML: `common.xml` holds the common ones, `ardupilotmega.xml` the ArduPilot extensions. Libraries for C, Python and other languages are generated from the XML.

### System and component
`system_id` is the vehicle (1 by default), `component_id` is what's inside: the autopilot (1), a camera, a gimbal, the companion computer. The GCS is usually system 255. Commands are addressed to a system+component pair; the companion computer is a separate component of the same system.

### Heartbeat
`HEARTBEAT` (ID 0) once a second from every participant: vehicle type, autopilot, mode, arm state. No heartbeat, no link — that's why every client starts with `wait_heartbeat()`. No heartbeat from the GCS for longer than the timeout is a GCS failsafe.

### The main messages
- Telemetry from the vehicle: `SYS_STATUS` (1), `ATTITUDE` (30), `GLOBAL_POSITION_INT` (33), `RC_CHANNELS` (65), `BATTERY_STATUS` (147), `STATUSTEXT` (253 — text messages, including pre-arm ones).
- Commands: `COMMAND_LONG` (76) with a `MAV_CMD_*` code and seven parameters; the reply is `COMMAND_ACK` (77) with the result. Example codes: `MAV_CMD_COMPONENT_ARM_DISARM` (400), `MAV_CMD_NAV_TAKEOFF` (22), `MAV_CMD_DO_SET_MODE` (176).
- Stream rates: `MAV_CMD_SET_MESSAGE_INTERVAL` (511) — request a specific message at the interval you need; `MAV_CMD_REQUEST_MESSAGE` (512) — once.
- Parameters: `PARAM_REQUEST_READ` (20) → `PARAM_VALUE` (22); writing is `PARAM_SET` (23), confirmed by the same `PARAM_VALUE`.
- Control in GUIDED: `SET_POSITION_TARGET_LOCAL_NED` (84) and `SET_POSITION_TARGET_GLOBAL_INT` (86) — a position or velocity target; the basis of offboard control from a companion.
- Missions: `MISSION_COUNT` (44), `MISSION_ITEM_INT` (73), `MISSION_REQUEST_INT` (51), `MISSION_ACK` (47) — the dialog from the missions module.

### The acknowledgment rule
A command without a `COMMAND_ACK` check is hope, not control. The result `MAV_RESULT_ACCEPTED` (0) means “accepted”; the other codes are a refusal, and its reason usually arrives in `STATUSTEXT`.

### pymavlink vs MAVSDK
- **pymavlink** is a thin wrapper over the protocol: you see every message; it suits learning, diagnostics and non-standard things. The code is verbose.
- **MAVSDK** (C++, Python) offers high-level actions: `arm()`, `takeoff()`, `goto_location()`, telemetry subscriptions. Faster for writing applications, less visible from the inside. Historically closer to PX4, but works with ArduPilot.

### The MAVLink 2 frame byte by byte
`FD | len | incompat_flags | compat_flags | seq | sysid | compid | msgid(3) | payload(len) | crc(2) | [signature(13)]`. `incompat_flags` bit 0 means the packet is signed; the signature is the first 48 bits of SHA-256 over (secret key + header + payload + CRC + link_id + timestamp), not HMAC (protection against command spoofing over an open radio channel — the key is set in Mission Planner/QGC and sent to the autopilot with the `SETUP_SIGNING` message). CRC-16/MCRF4XX over the frame + the message's `CRC_EXTRA` byte (from the XML) — a dialect mismatch = “silence”. The payload is compressed by truncating trailing zero bytes (which is why `len` is smaller than the struct size). Parameters in `PARAM_VALUE` are always float (32-bit); ArduPilot sends integers cast to float (C cast), PX4 byte-wise; the value type is in `param_type` (`MAV_PARAM_TYPE`), which is easy to trip over in pymavlink.

{{diagram:mavlink2-frame|The MAVLink 2 frame: header, system and component IDs, payload, CRC with CRC_EXTRA, optional signature.}}

### Telemetry streams: who sets the rate
ArduPilot sends streams according to the port's `SRx_*` parameters (`SR2_EXTRA1` — ATTITUDE, `SR2_POSITION` — GLOBAL_POSITION_INT, `SR2_RAW_SENS` — RAW_IMU…) in Hz; the modern way is `MAV_CMD_SET_MESSAGE_INTERVAL` (511) from the client: the interval in µs (−1 — off, 0 — default). PX4 uses `MAV_x_MODE` profiles (Normal/Onboard/OSD…). A 921600 baud port carries ~90 KB/s: ATTITUDE at 50 Hz + position at 10 Hz + RAW_IMU at 50 Hz is about 10 KB/s, so there is headroom; at 57600 (a radio modem) anything above 5–10 Hz chokes.

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
`STATUSTEXT` explains the refusal in parallel (“PreArm: …”). MAVSDK does the same under the hood — but you need to understand what's inside to read a tlog during an analysis.

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

### Step 2. A command with acknowledgment
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
Run `mavproxy.py --master=tcp:127.0.0.1:5762` and the `watch ATTITUDE` command: you see the live message stream. It's the best way to understand what exactly is flying over the line before you write code.

### What you should get and what to record
- **Step 1.** In SITL the first heartbeat comes from system 1, component 1 (the autopilot). Don't take the rate on faith — measure it: collect 50 `ATTITUDE` messages and divide the number of intervals (49) by the difference in `time_boot_ms` between the first and the last (in seconds). Expect 9.5–10.5 Hz with an interval of 100,000 µs. If `ATTITUDE` doesn't arrive at all, the interval command didn't get through: on port 5762, Copter's default rate (`SR1_EXTRA1`, in 4.7 — `MAV2_EXTRA1`) is 0. Around 4 Hz is the rate MAVProxy itself requests on its port 5760.
- **Step 2.** Repeat the arm right after SITL starts, before the EKF has converged. A `COMMAND_ACK` with result 4 (`MAV_RESULT_FAILED`) arrives, and the reason is in a `STATUSTEXT` with the `PreArm:` prefix. Record both lines: this is what a refusal that your code must handle looks like. Result codes: 0 — accepted, 1 — temporarily rejected, 2 — denied, 3 — unsupported, 4 — failed, 5 — in progress.
- **Step 3.** Writing a parameter is a `PARAM_SET` and a reply `PARAM_VALUE` with the new value. Until the reply arrives, the parameter isn't written:

```python
m.mav.param_set_send(m.target_system, m.target_component, b"FS_THR_ENABLE", 1,
                     mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=3)
assert p and p.param_id == "FS_THR_ENABLE" and p.param_value == 1, p
```

- **Step 4.** `watch ATTITUDE` shows the rate and the live angles. Compare it with the rate measured in step 1. In the flight from the “SITL” module the angles change on every maneuver — that's how you check that the stream is alive and not frozen.

The lab counts as done when the `ATTITUDE` rate is measured (not just set) and close to 10 Hz, a failed arm and a successful arm are analyzed via `COMMAND_ACK` and `STATUSTEXT`, a parameter is written with the `PARAM_VALUE` reply checked, and the link has been inspected in MAVProxy.

## diagnostics
- **Symptom:** `wait_heartbeat()` doesn't return
  - Possible cause: wrong address/port, the wrong dialect, UART baud rate.
  - What to do: check the port, the baud (57600 or 115200 on telemetry), that SITL is running.
- **Symptom:** the command “succeeded”, but the vehicle did nothing
  - Possible cause: `COMMAND_ACK` wasn't checked, the command was rejected.
  - What to do: read the ACK and `STATUSTEXT`.
- **Symptom:** telemetry arrives rarely
  - Possible cause: default stream intervals.
  - What to do: `MAV_CMD_SET_MESSAGE_INTERVAL` for the messages you need.
- **Symptom:** CRC errors, “unknown” messages
  - Possible cause: different versions of the definitions on the two sides.
  - What to do: update pymavlink/MAVSDK, use the same dialect (ardupilotmega).

## references
- MAVLink Developer Guide | https://mavlink.io/en/ | primary | A
- MAVLink common message set | https://mavlink.io/en/messages/common.html | primary | A
- pymavlink — source code (GitHub) | https://github.com/ArduPilot/pymavlink | primary | A
- MAVSDK — Documentation | https://mavsdk.mavlink.io/main/en/ | primary | A
- MAVLink Interface — ArduPilot Dev | https://ardupilot.org/dev/docs/mavlink-basics.html | primary | A

## checklist
- I understand system_id / component_id and heartbeat
- Every command is checked via `COMMAND_ACK`
- I can request telemetry at the rate I need
- I read and write parameters from code
- I know when to use pymavlink and when MAVSDK
