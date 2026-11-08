# Bridge ↔ browser protocol (WebSocket, JSON text frames)

Version 1. One JSON object per frame. Unknown fields must be ignored by both sides.

## Bridge → browser

| type | fields | source MAVLink message |
|---|---|---|
| `link` | `ok` (bool) — false when no autopilot HEARTBEAT for 3 s | — |
| `heartbeat` | `armed`, `mode` (ArduCopter name or number), `sysid` | HEARTBEAT (autopilot only) |
| `position` | `lat`, `lon` (deg), `alt_rel` (m), `hdg` (deg or null), `vel` (m/s, ground) | GLOBAL_POSITION_INT |
| `attitude` | `roll`, `pitch`, `yaw` (deg) | ATTITUDE |
| `battery` | `voltage` (V), `current` (A or null), `remaining` (% or null) | SYS_STATUS |
| `text` | `severity` (0–7, MAV_SEVERITY), `text` | STATUSTEXT |
| `ack` | `id`, `ok`, `detail` — answer to a command | COMMAND_ACK (or timeout) |

## Browser → bridge

`{"id": <int>, "op": "arm" | "disarm" | "mode", "mode": "<name>"}`

Every request gets exactly one `ack` with the same `id`. `ok: false` carries the reason
(`MAV_RESULT_*` name, timeout, unknown mode). The UI shows a command as done only after `ok: true`.

## Modes

The starter maps ArduCopter custom modes (`COPTER_MODES` in `bridge.py`). PX4 encodes
main/sub mode in `custom_mode` bytes — a project milestone is to support both by `HEARTBEAT.autopilot`.
