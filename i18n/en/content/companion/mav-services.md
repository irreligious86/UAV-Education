---
id: mav-services
title: "MAVLink microservices: commands, parameters, missions, streams"
level: L3
readingTime: 50 min
firmware: ArduPilot · PX4
status: published
added: 2026-11-08
tags:
  - MAVLink
  - missions
  - parameters
  - COMMAND_ACK
  - MAVFTP
related:
  - mav-protocol
  - ap-missions
  - comp-mavlink
next:
  - mav-routing
source: content/companion/mav-services.md
source_hash: d570897fba1a
---

## summary
MAVLink is not a set of messages but a set of **dialogues** (microservices): who starts, who replies, what to do on a loss. Almost every companion integration bug is a violation of one of these dialogues: a command sent without waiting for an ACK, a parameter “written” without an echo, a mission uploaded halfway. This module goes through the main microservices: heartbeat and state, commands (`COMMAND_LONG`/`COMMAND_INT`, ACK, IN_PROGRESS, the confirmation counter), parameters (reading the list, writing with confirmation, type encoding), missions (upload, download, partial update, geofences and rally points as separate mission types), telemetry stream control, MAVFTP, camera/gimbal and Remote ID — at the level of “which dialogue, and where it breaks.” Lab: a mission client with retries that passes the tests at 25 % packet loss.

## theory
### Heartbeat and state
`HEARTBEAT` (0) once per second from every component: type (`MAV_TYPE`), autopilot, `base_mode` (the arm flag — `MAV_MODE_FLAG_SAFETY_ARMED`), `custom_mode` (the mode number, different for each firmware), `system_status`. The heartbeat is participant discovery, the source of the address for routing, and the basis of failsafe: an autopilot that stops hearing the GCS heartbeat triggers the GCS failsafe (if enabled); a companion that stops hearing the autopilot must stop issuing setpoints. Rule: start any addressed commands only after the first heartbeat from the addressee.

### Commands: COMMAND_LONG, COMMAND_INT and ACK
`COMMAND_LONG` (76): `target_system`, `target_component`, `command` (MAV_CMD), `confirmation`, seven float parameters. `COMMAND_INT` (75): the same addressing and param1–4, but without the `confirmation` field (instead there are `current`/`autocontinue`, unused); parameters 5–6 are integers `x`, `y` (latitude/longitude × 10⁷ without float precision loss) and there is a `frame` field; it's preferred for commands with coordinates. The reply is `COMMAND_ACK` (77) with `result`:

| result | Meaning | What the client should do |
|---|---|---|
| ACCEPTED (0) | executed/accepted | done |
| TEMPORARILY_REJECTED (1) | not possible right now | retry later |
| DENIED (2) | forbidden in this state | read STATUSTEXT, don't retry |
| UNSUPPORTED (3) | command not supported | don't retry |
| FAILED (4) | attempted and failed | investigate the cause |
| IN_PROGRESS (5) | long-running command, `progress` 0–100 | wait for the final ACK |

The protocol prescribes: if no ACK arrives within the timeout, resend the command, **incrementing `confirmation`**. The receiver can use it to tell a retry from a new command. Without waiting for an ACK, a command is a hope; without a retry limit, it's a hang.

{{diagram:mavlink-command-seq|Command with acknowledgment: a retry when the ACK is lost, an intermediate IN_PROGRESS, the final result.}}

### Parameters
- List: `PARAM_REQUEST_LIST` (21) → a stream of `PARAM_VALUE` (22) with `param_count` and `param_index`. Gaps are filled in by index via `PARAM_REQUEST_READ` (20) with `param_index`.
- Reading one: `PARAM_REQUEST_READ` by name (16 characters, with no terminating null when the length is 16!) or by index.
- Writing: `PARAM_SET` (23). **There is no separate ACK** — the confirmation is a `PARAM_VALUE` with the same name and the new value. If the echo comes back with the old value, the write was rejected (out of range, read-only).
- All values are sent in the `float param_value` field. ArduPilot sends integer types as a number cast to float (C-cast), PX4 — bytewise (the integer's bits in the float's bits). Which scheme the autopilot uses is reported by a flag in `AUTOPILOT_VERSION.capabilities` (`MAV_PROTOCOL_CAPABILITY_PARAM_ENCODE_C_CAST` or `..._BYTEWISE`). Getting the scheme wrong turns `SYSID_THISMAV = 1` into 1.4e-45.

For bulk parameter loading, so you don't run 1000 dialogues over the radio, there is MAVFTP: ArduPilot serves the whole `@PARAM/param.pck` file.

### Missions: a dialogue driven by the receiver
Upload (client → vehicle):
1. Client: `MISSION_COUNT` (44) with the number of items and `mission_type`.
2. The vehicle requests them one at a time: `MISSION_REQUEST_INT` (51) with `seq`.
3. The client replies with `MISSION_ITEM_INT` (73) with that `seq`.
4. After the last item the vehicle sends `MISSION_ACK` (47) with the result.

The key idea: **the receiving side holds the initiative**. It requests the items, and it also re-sends the request on a timeout. The sender replies to every request, including repeated ones, and doesn't send items “ahead.” Download (vehicle → client) is symmetrical: `MISSION_REQUEST_LIST` → `MISSION_COUNT` → the client requests `MISSION_REQUEST_INT` → `MISSION_ITEM_INT` → the client finishes with `MISSION_ACK`.

`mission_type`: 0 — route, 1 — geofence (fence), 2 — rally points (rally), 255 — all (for clearing with `MISSION_CLEAR_ALL`). Item 0 in ArduPilot is the home position; uploading from item 1 in Mission Planner is just the UI, and on the wire home is still seq 0. Avoid the deprecated `MISSION_ITEM` (39) and `MISSION_REQUEST` (40) with float coordinates: float precision at a latitude is ~ a meter.

In flight: `MISSION_CURRENT` (42) — the current item, `MISSION_ITEM_REACHED` (46) — reached, `MAV_CMD_DO_SET_MISSION_CURRENT` (224) — jump to (the `MISSION_SET_CURRENT` (41) message has been deprecated since 2022 and replaced by this command). Partial update: `MISSION_WRITE_PARTIAL_LIST` (38) with an index range — not supported everywhere; it's more reliable to re-upload the whole thing and verify by downloading.

{{diagram:mavlink-mission-seq|Mission upload: the vehicle requests items one at a time and re-sends the request itself on a loss; it finishes with MISSION_ACK.}}

### Telemetry streams
The vehicle sends telemetry either according to its own settings (ArduPilot — stream groups per port, `SRn_*` parameters in 4.6 and `MAVn_*` in 4.7+; PX4 — `MAV_n_MODE` profiles), or on the client's request:
- `MAV_CMD_SET_MESSAGE_INTERVAL` (511): param1 — msgid, param2 — interval in µs (−1 — off, 0 — default).
- `MAV_CMD_REQUEST_MESSAGE` (512): one message now (for example, `AUTOPILOT_VERSION`, `HOME_POSITION`).

Link budget: SiK at 57600 gives ~5 KB/s of payload; ATTITUDE (28 bytes payload + 12 overhead) at 10 Hz is 0.4 KB/s. A companion over UART at 921600 gets ~90 KB/s, and there you can ask for IMU at 100 Hz, but over the radio you can't. Request exactly what you use, and on the link where you use it.

### Time
`SYSTEM_TIME` (2) — boot time and UTC; `TIMESYNC` (111) — an estimate of the clock offset between the companion and the autopilot (a tc1/ts1 exchange, like NTP). Without time synchronization, fusing camera frames with telemetry won't be accurate: USB/UART and buffer latency easily reaches 10–50 ms.

### MAVFTP, camera, gimbal, Remote ID
- **MAVFTP** — `FILE_TRANSFER_PROTOCOL` (110): a file system over MAVLink (read/write/list, retries by session sequence). ArduPilot: logs, Lua scripts, `@PARAM/param.pck`, `@SYS/` with diagnostics.
- **Camera** (Camera Protocol v2): `MAV_CMD_IMAGE_START_CAPTURE` (2000), `CAMERA_INFORMATION`, `CAMERA_IMAGE_CAPTURED` with the frame's coordinates and time. The camera is a separate component (compid 100–105).
- **Gimbal** (Gimbal Protocol v2): a gimbal manager on the autopilot and a gimbal device; `MAV_CMD_DO_GIMBAL_MANAGER_PITCHYAW` (1000), `GIMBAL_MANAGER_SET_ATTITUDE` (282), status `GIMBAL_DEVICE_ATTITUDE_STATUS`.
- **Remote ID**: the `OPEN_DRONE_ID_*` group (12900+) — the autopilot or a module broadcasts the ID, location and operator data; the requirements for broadcasting them are a regulatory matter (see f-regulations).

## practice
### Step 1. Tests without SITL
`examples/mavlink/mav_client.py` is the reference implementation, `fake_vehicle.py` is a vehicle that can lose packets.

```bash
cd examples/mavlink
python -m pytest -q tests/test_services.py
```

Read `mission_upload`: the client replies to any `MISSION_REQUEST_INT`, including retries, and restarts the transaction with `MISSION_COUNT` if the vehicle goes silent.

### Step 2. Your own mission client
Write **your own** implementation of `mission_upload/mission_download` (without copying), plug it into the test instead of `mav_client` and get it to pass at `loss=0.25`. Then add a test: the vehicle replies with a `MISSION_ACK` with an error — the client must raise an exception, not report a “silent success.”

### Step 3. In SITL
With the same client, upload a 10-waypoint mission to ArduPilot SITL, download it and compare item by item; then do the same for a geofence (`mission_type = 1`, `MAV_CMD_NAV_FENCE_POLYGON_VERTEX_INCLUSION` commands). Make sure Mission Planner sees both.

### Step 4. Parameters with encoding
Read `SYSID_THISMAV` (or `MAV_SYSID` on 4.7+) in ArduPilot SITL and `MAV_SYS_ID` in PX4 SITL via `PARAM_REQUEST_READ`; look at the raw `param_value` and `param_type`. Explain the difference between the C-cast and bytewise schemes using these two values.

The lab is passed when your own mission client passes the tests under loss, the mission and geofence match after downloading in SITL, and the parameter encoding is explained.

## diagnostics
- **Symptom:** the mission is “uploaded,” but the vehicle has one or two fewer items
  - Possible cause: the client sent items back to back without waiting for requests; some were lost, the ACK wasn't checked.
  - What to do: reply only to MISSION_REQUEST_INT; require MISSION_ACK ACCEPTED; download and compare.
- **Symptom:** PARAM_SET “went through,” but the value didn't change
  - Possible cause: the PARAM_VALUE echo wasn't checked; the value is out of range or the type encoding is wrong.
  - What to do: compare the echo with the value; account for C-cast vs bytewise.
- **Symptom:** a command is sometimes executed twice
  - Possible cause: a retry without incrementing confirmation on a non-idempotent command.
  - What to do: confirmation++ on retry; check the state before retrying.
- **Symptom:** telemetry over the radio “stutters” after the script connects
  - Possible cause: the script requested high rates via SET_MESSAGE_INTERVAL on the radio link.
  - What to do: request streams only on your own link; calculate the budget.

## references
- MAVLink — Mission protocol | https://mavlink.io/en/services/mission.html | primary | A
- MAVLink — Command protocol | https://mavlink.io/en/services/command.html | primary | A
- MAVLink — Parameter protocol (encoding) | https://mavlink.io/en/services/parameter.html | primary | A
- MAVLink — FTP protocol | https://mavlink.io/en/services/ftp.html | primary | A
- MAVLink — Camera and Gimbal protocols v2 | https://mavlink.io/en/services/camera.html | primary | A
- ArduPilot — MissionItemProtocol (source) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/GCS_MAVLink | primary | A

## checklist
- I know the COMMAND_ACK codes and what to do for each
- I retry commands with confirmation++ and a limit
- I confirm PARAM_SET with the PARAM_VALUE echo and understand type encoding
- I describe the mission upload/download dialogue and who re-sends requests in it
- I tell the mission types apart (route, geofence, rally)
- I control stream rates and calculate the link budget
