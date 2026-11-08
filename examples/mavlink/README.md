# MAVLink labs

Starter code and autotests for the MAVLink mini-course (`mav-protocol`, `mav-services`,
`mav-routing`, `mav-component`, `mav-sdk`). Everything here runs **without SITL**: a small
`fake_vehicle.py` speaks heartbeat, parameters, missions and commands, and can drop a fraction
of its packets to prove that your retries work. The same clients work unchanged against
ArduPilot SITL (listen with `udpin:0.0.0.0:14551` on an extra MAVProxy output `--out=udp:127.0.0.1:14551`, or connect `tcp:127.0.0.1:5762`) or a real vehicle.

```bash
pip install pymavlink pytest
python -m pytest -q tests          # 12 tests, ~12 s
```

| File | What it is | Module |
|---|---|---|
| `mavlink_crc.py` | CRC-16/MCRF4XX and CRC_EXTRA from scratch | mav-protocol |
| `decode_frame.py` | decode a raw MAVLink 2 frame byte by byte, verify CRC, unpack payload (incl. trailing-zero truncation) | mav-protocol |
| `mav_client.py` | commands with ACK/retries/confirmation counter, PARAM_SET/GET with echo check, mission upload/download | mav-services |
| `fake_vehicle.py` | minimal vehicle for tests, configurable packet loss | all |
| `virtual_rangefinder.py` | a MAVLink component (own compid and heartbeat) publishing DISTANCE_SENSOR; ArduPilot: `RNGFND1_TYPE=10`, `RNGFND1_ORIENT=25` | mav-component |
| `tests/` | pytest: protocol, services under 25–30 % loss, component | — |

Lab rule: your own implementation (a mission client, a decoder, a component) passes the same
tests when you point them at it. Extend the tests, do not loosen them.
