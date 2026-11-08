# Web GCS (project #1 starter)

A browser ground station: `bridge.py` reads MAVLink and serves JSON over WebSocket; `web/index.html`
shows the vehicle on a Leaflet map with mode, battery, attitude and STATUSTEXT, and sends arm/disarm
and mode changes that are confirmed by COMMAND_ACK before the UI reports success.

```bash
pip install pymavlink websockets pytest
python -m pytest -q tests                         # 6 tests against examples/mavlink/fake_vehicle.py

# with ArduPilot SITL (it sends to udp 14550 by default)
python bridge.py --mavlink udpin:0.0.0.0:14550
# open web/index.html in a browser (or serve the folder: python -m http.server -d web 8000)
```

| File | Role |
|---|---|
| `bridge.py` | MAVLink link thread, `telemetry_json()` translation, command execution with ACK, WebSocket server |
| `web/index.html` | the UI: one handler per frame type, reconnects on its own |
| `docs/protocol.md` | the WebSocket protocol (version 1) |
| `tests/` | translation, commands, link-loss detection |

Milestones (course page "Проекты → 1"): measure end-to-end latency, record and replay tlog,
PX4 mode encoding, missions on the map. Reuses `examples/mavlink/mav_client.py` for reliable commands.
