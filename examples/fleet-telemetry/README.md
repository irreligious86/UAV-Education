# Fleet telemetry (project #2 starter)

The parts of a fleet telemetry pipeline that decide whether data survives: the message schema, a
store-and-forward publisher on the companion, and an ingest core that validates, de-duplicates and alerts.
No broker or database is needed for the tests; the transport and the sink are plain interfaces.

```bash
python -m pytest -q tests      # 6 tests: 3 vehicles × 10 min, 60 s outage, overflow, schema, alerts, traffic
```

| File | Role |
|---|---|
| `schema.py` | v1 message: required/optional fields with types and ranges; unknown fields ignored, a breaking change bumps `v`; `validate()` never raises |
| `publisher.py` | `tick(sample)` at 1–5 Hz; bounded buffer during outages, backlog sent oldest-first and rate-limited, thinning instead of losing the latest minutes |
| `ingest.py` | topic ↔ id check, de-duplication by `(id, seq)` (QoS 1 is at-least-once), last state per vehicle, alerts: battery, no data > 10 s, EKF |

Traffic: about 1 MB per vehicle-hour at 2 Hz compact JSON, before MQTT and TLS overhead — measure your own
and put the number in the report. Milestones (course page "Проекты → 2"): paho-mqtt transport with last will
for online/offline, a pymavlink source for `sample()`, InfluxDB/TimescaleDB sink, Grafana dashboard JSON,
everything in one `docker compose up`.
