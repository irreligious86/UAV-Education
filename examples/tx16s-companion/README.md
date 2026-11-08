# TX16S companion: CRSF telemetry (project #12 starter)

The radio-side half of an ESP32 companion for a RadioMaster TX16S: parse CRSF telemetry coming from the
receiver (battery, link statistics, attitude, GPS) so it can be shown on the module's own screen or sent
to a phone over BLE/Wi-Fi.

```bash
python -m pytest -q tests        # compiles firmware/ with -Wall -Werror and compares it to crsf.py
```

| File | Role |
|---|---|
| `firmware/crsf_telemetry.[ch]` | portable C99 byte-at-a-time parser: sync search, length check (2–62), CRC8 (0xD5), big-endian decoders |
| `firmware/test_main.c` | host driver: hex on stdin → one JSON line per frame (used by the tests) |
| `crsf.py` | Python reference decoder and an encoder to build fixtures |
| `tests/` | the same noisy stream (garbage, invalid lengths, corrupted frames, unknown types) through both |

Into the ESP32 project (PlatformIO/ESP-IDF): copy `firmware/crsf_telemetry.*`, feed every UART byte to
`crsf_feed()`, render from `crsf_telemetry_t`. Milestones on the course page "Проекты → 12": UART wiring in
the module bay (check voltage levels first), EdgeTX Lua side in the simulator, BLE to a phone, power
measurement, and the rule that the radio keeps flying if the companion hangs.
