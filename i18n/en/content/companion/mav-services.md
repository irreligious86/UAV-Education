---
id: mav-services
title: "MAVLink microservices: commands, parameters, missions, streams"
level: L3
readingTime: 50 min
firmware: ArduPilot 4.7 (checked against 4.7.3) · PX4 1.18 (checked against v1.18.0) · MAVLink 2 (mavlink/mavlink master, November 2026)
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
source_hash: c0f420982c8f
---

## summary
MAVLink is not a set of messages but a set of **exchanges** (microservices): who starts, who answers, what to do on loss. Almost every companion integration bug is a violation of one of these exchanges: a command sent without waiting for the ACK, a parameter "written" without an echo, a mission uploaded halfway. The module walks through the main microservices: heartbeat and state, commands (`COMMAND_LONG`/`COMMAND_INT`, ACK, IN_PROGRESS, the confirmation counter), parameters (reading the list, writing with confirmation, type encoding), missions (upload, download, partial update, geofences and rally points as separate mission types), telemetry stream control, MAVFTP, camera/gimbal, and Remote ID, at the level of "which exchange it is and where it breaks". Lab: a mission client with retries that passes its tests at 25 % packet loss.

## theory
### Heartbeat and state
`HEARTBEAT` (0) goes out once a second from every component: the type (`MAV_TYPE`), the autopilot, `base_mode` (the arming flag is `MAV_MODE_FLAG_SAFETY_ARMED`), `custom_mode` (the mode number, specific to each firmware), `system_status`. The heartbeat is participant discovery, the source of addresses for routing, and the basis of failsafes: an autopilot that stops hearing the GCS heartbeat triggers the GCS failsafe (if enabled); a companion that stops hearing the autopilot must stop sending setpoints. The rule: send addressed commands only after the first heartbeat from the target.

### Commands: COMMAND_LONG, COMMAND_INT, and the ACK
`COMMAND_LONG` (76): `target_system`, `target_component`, `command` (MAV_CMD), `confirmation`, seven float parameters. `COMMAND_INT` (75): the same addressing and param1–4, but no `confirmation` field (instead there are `current`/`autocontinue`, both unused); parameters 5–6 are the integers `x`, `y` (latitude/longitude × 10⁷ without float precision loss), and there is a `frame` field; prefer it for commands with coordinates. The reply is `COMMAND_ACK` (77) with a `result`:

| result | Meaning | What the client does |
|---|---|---|
| ACCEPTED (0) | executed/accepted | done |
| TEMPORARILY_REJECTED (1) | not possible right now | retry later |
| DENIED (2) | not allowed in this state | read STATUSTEXT, do not retry |
| UNSUPPORTED (3) | command not supported | do not retry |
| FAILED (4) | attempted, and failed | analyze the cause |
| IN_PROGRESS (5) | long-running command, `progress` 0–100 | wait for the final ACK |

The protocol prescribes: if no ACK arrives within the timeout, resend the command **with `confirmation` incremented**. That lets the receiver tell a retry from a new command. Without waiting for the ACK a command is hope; without a retry limit it is a hang.

{{diagram:mavlink-command-seq|An acknowledged command: a retry when the ACK is lost, an intermediate IN_PROGRESS, the final result.}}

### Parameters
- The list: `PARAM_REQUEST_LIST` (21) → a stream of `PARAM_VALUE` (22) with `param_count` and `param_index`. Gaps are filled by index with `PARAM_REQUEST_READ` (20) and `param_index`.
- Reading one: `PARAM_REQUEST_READ` by name (16 characters, with no terminating null when the name is 16 long!) or by index.
- Writing: `PARAM_SET` (23). **There is no separate ACK**: the confirmation is a `PARAM_VALUE` with the same name and the new value. If the echo carries the old value, the write was rejected (a read-only parameter, for example); on an error (no such name, read-only, a NaN value) ArduPilot 4.7 and PX4 1.18 send `PARAM_ERROR` (345); for an unknown name or a NaN value ArduPilot sends only `PARAM_ERROR` and no echo at all, so a client waiting only for `PARAM_VALUE` times out.
- Every value travels in the `float param_value` field. ArduPilot sends integer types as a number converted to float (C cast), PX4 byte-wise (the integer's bits in the float's bits). A flag in `AUTOPILOT_VERSION.capabilities` tells which scheme the autopilot uses (`MAV_PROTOCOL_CAPABILITY_PARAM_ENCODE_C_CAST` or `..._BYTEWISE`); ArduPilot 4.7 does not set `..._C_CAST` and reports the deprecated `MAV_PROTOCOL_CAPABILITY_PARAM_FLOAT` instead, so the sign to look for is the absence of `..._BYTEWISE`. Getting the scheme wrong turns `MAV_SYSID = 1` (`SYSID_THISMAV` before ArduPilot 4.7) into 1.4e-45.

For bulk parameter download, so you do not run 1000 exchanges over the radio, there is MAVFTP: ArduPilot serves the whole `@PARAM/param.pck` file.

### Missions: an exchange driven by the receiver
Upload (client → vehicle):
1. Client: `MISSION_COUNT` (44) with the number of items and the `mission_type`.
2. The vehicle requests items one by one: `MISSION_REQUEST_INT` (51) with a `seq` (ArduPilot 4.7 sends the old `MISSION_REQUEST` (40); answer it with `MISSION_ITEM_INT` as well).
3. The client replies with `MISSION_ITEM_INT` (73) carrying that `seq`.
4. After the last item the vehicle sends `MISSION_ACK` (47) with the result.

The key idea: **the receiving side holds the initiative**. It requests the items, and it repeats a request on a timeout. The sender answers every request, repeated ones included, and never sends items "ahead". Download (vehicle → client) is symmetric: `MISSION_REQUEST_LIST` → `MISSION_COUNT` → the client requests with `MISSION_REQUEST_INT` → `MISSION_ITEM_INT` → the client finishes with `MISSION_ACK`.

`mission_type`: 0 is the mission, 1 the geofence (fence), 2 rally points, 255 all of them (for clearing with `MISSION_CLEAR_ALL`). Item 0 in ArduPilot is the home position; uploading from item 1 in Mission Planner is just the interface, and on the wire home is still seq 0. Avoid the deprecated `MISSION_ITEM` (39) with float coordinates (float precision at a given latitude is about a meter); never send the deprecated `MISSION_REQUEST` (40) yourself, but accept it (ArduPilot sends it during upload).

In flight: `MISSION_CURRENT` (42) is the current item, `MISSION_ITEM_REACHED` (46) means an item was reached, `MAV_CMD_DO_SET_MISSION_CURRENT` (224) jumps to an item (the `MISSION_SET_CURRENT` (41) message was superseded by this command in 2022). Partial update: `MISSION_WRITE_PARTIAL_LIST` (38) with an index range; not supported everywhere, so it is safer to re-upload the whole mission and verify it by downloading.

{{diagram:mavlink-mission-seq|Mission upload: the vehicle requests items one by one and repeats a request itself on loss; it finishes with MISSION_ACK.}}

### Telemetry streams
The vehicle sends telemetry either according to its own settings (ArduPilot: stream groups per port, the `MAVn_*` parameters, numbered from 1; before 4.7 they were `SRn_*` numbered from zero, so `SR0_*` became `MAV1_*`; PX4: `MAV_n_MODE` profiles) or at the client's request:
- `MAV_CMD_SET_MESSAGE_INTERVAL` (511): param1 is the msgid, param2 the interval in µs (−1 disables, 0 restores the default).
- `MAV_CMD_REQUEST_MESSAGE` (512): one message right now (for example `AUTOPILOT_VERSION`, `HOME_POSITION`).

The link budget: a SiK radio at 57600 gives ~5 KB/s of payload; ATTITUDE (28 bytes of payload + 12 of overhead) at 10 Hz is 0.4 KB/s. A companion on a 921600 UART gets ~90 KB/s, and there you can request the IMU at 100 Hz; over the radio you cannot. Request exactly what you use, on the link where you use it.

### Time
`SYSTEM_TIME` (2) carries the time since boot and UTC; `TIMESYNC` (111) estimates the clock offset between the companion and the autopilot (a tc1/ts1 exchange, like NTP). Without time synchronization, fusing camera frames with telemetry will not be accurate: USB/UART and buffer latency easily reaches 10–50 ms.

### MAVFTP, camera, gimbal, Remote ID
- **MAVFTP**, `FILE_TRANSFER_PROTOCOL` (110): a file system over MAVLink (read/write/list, retries by session sequence number). ArduPilot: logs, Lua scripts, `@PARAM/param.pck`, `@SYS/` with diagnostics.
- **Camera** (Camera Protocol v2): `MAV_CMD_IMAGE_START_CAPTURE` (2000), `CAMERA_INFORMATION`, `CAMERA_IMAGE_CAPTURED` with the coordinates and time of the frame. A camera is a separate component (compid 100–105).
- **Gimbal** (Gimbal Protocol v2): a gimbal manager on the autopilot and a gimbal device; `MAV_CMD_DO_GIMBAL_MANAGER_PITCHYAW` (1000), `GIMBAL_MANAGER_SET_ATTITUDE` (282), and `GIMBAL_DEVICE_ATTITUDE_STATUS` for status.
- **Remote ID**: the `OPEN_DRONE_ID_*` group (12900+): the autopilot or a module broadcasts the identifier, the location, and the operator data; what you are required to broadcast is a regulatory question (see f-regulations).

### Where it fits in the system

- **Takes in:** frames and field types (`mav-protocol`); the target's heartbeat, before which no addressed commands go out; the link budget for streams (`link-telemetry-radios`).
- **Puts out:** acknowledged commands and parameters to the autopilot; missions (`ap-missions`); telemetry stream intervals; the `TIMESYNC` clock offset for fusing camera frames with telemetry (`per-geometry`).
- **If you get this wrong:** `PARAM_SET` without an echo check → the parameter is "written", but the old value stays on board; for a failsafe threshold this surfaces only in a crash (`ap-safety-fs`). A mission upload cut off before `MISSION_ACK` → the mission on board is not the one in the planner, and in AUTO you find out in the air (`ap-missions`); verify by downloading.

## practice
### Step 1. Tests without SITL
`examples/mavlink/mav_client.py` is the reference implementation; `fake_vehicle.py` is a vehicle that can drop packets.

```bash
cd examples/mavlink
python -m pytest -q tests/test_services.py
```

Read `mission_upload`: the client answers every `MISSION_REQUEST_INT` (and `MISSION_REQUEST`), repeats included, and restarts the `MISSION_COUNT` transaction if the vehicle goes silent.

### Step 2. Your own mission client
Write **your own** implementation of `mission_upload/mission_download` (do not copy), plug it into the test in place of `mav_client`, and make it pass at `loss=0.25`. Then add a test: the vehicle answers with a `MISSION_ACK` carrying an error, and the client must raise an exception rather than report a "silent success".

### Step 3. In SITL
With the same client, upload a 10-waypoint mission to ArduPilot SITL, download it, and compare item by item; then do the same for a geofence (`mission_type = 1`, `MAV_CMD_NAV_FENCE_POLYGON_VERTEX_INCLUSION` commands). Make sure Mission Planner sees both.

### Step 4. Parameters and encoding
Read `MAV_SYSID` (`SYSID_THISMAV` on 4.6 and earlier) in ArduPilot SITL and `MAV_SYS_ID` in PX4 SITL with `PARAM_REQUEST_READ`; look at the raw `param_value` and `param_type`. Explain the difference between the C-cast and bytewise schemes using these two values.

Self-check: the lab is done when your own mission client passes the tests at `loss=0.25` and raises an exception on a `MISSION_ACK` with an error, the 10-waypoint mission and the geofence downloaded from SITL match the uploaded ones item by item and show in Mission Planner, and the parameter encoding is explained.

**Reference answer for self-check.** A correct explanation: every value travels in the `float param_value` field. ArduPilot converts the integer to float (C cast), so sysid 1 reads as 1.0. PX4 puts the integer's bits into the float's bits (bytewise), and the same value, read as an ordinary float, looks like 1.4e-45. A flag in `AUTOPILOT_VERSION.capabilities` tells which scheme applies. Common mistake #1: the PX4 value read as a float, giving 1.4e-45 instead of 1. Common mistake #2: the explanation leaves out `param_type` and the `capabilities` flag, so the scheme was guessed, not read.

## diagnostics
- **Symptom:** the mission is "uploaded", but the vehicle has one or two items fewer
  - Possible cause: the client sent items back to back without waiting for requests; some were lost, and the ACK was not checked.
  - What to do: answer only MISSION_REQUEST_INT/MISSION_REQUEST; require MISSION_ACK ACCEPTED; download and compare.
- **Symptom:** PARAM_SET "went through", but the value did not change
  - Possible cause: the PARAM_VALUE echo was not checked; the value is out of range or the type encoding is wrong.
  - What to do: compare the echo with the value; account for C-cast vs bytewise.
- **Symptom:** a command sometimes executes twice
  - Possible cause: a retry without incrementing confirmation on a non-idempotent command.
  - What to do: confirmation++ on retry; check the state before retrying.
- **Symptom:** radio telemetry "stutters" after a script connects
  - Possible cause: the script requested high rates with SET_MESSAGE_INTERVAL on the radio link.
  - What to do: request streams only on your own link; do the budget math.

## references
- MAVLink — Mission protocol | https://mavlink.io/en/services/mission.html | primary | A
- MAVLink — Command protocol | https://mavlink.io/en/services/command.html | primary | A
- MAVLink — Parameter protocol (encoding) | https://mavlink.io/en/services/parameter.html | primary | A
- MAVLink — FTP protocol | https://mavlink.io/en/services/ftp.html | primary | A
- MAVLink — Camera and Gimbal protocols v2 | https://mavlink.io/en/services/camera.html | primary | A
- ArduPilot — MissionItemProtocol (source) | https://github.com/ArduPilot/ardupilot/tree/master/libraries/GCS_MAVLink | primary | A

## checklist
- I know the COMMAND_ACK codes and what to do on each
- I retry commands with confirmation++ and a limit
- I confirm PARAM_SET with the PARAM_VALUE echo and understand type encoding
- I can describe the mission upload/download exchange and who repeats requests in it
- I can tell the mission types apart (mission, geofence, rally)
- I control stream rates and do the link budget math
