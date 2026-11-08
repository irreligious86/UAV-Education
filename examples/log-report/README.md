# Flight log report (project #3 starter)

ArduPilot DataFlash `.bin` → findings (JSON) + a self-contained HTML report with charts.

```bash
pip install pymavlink pytest
python log_report.py flight.bin --html report.html --json findings.json   # exit code 1 on any FAIL
python -m pytest -q tests                                                 # synthetic logs with known defects
```

Checks: vibration and clipping, battery internal resistance from load sag, ERR events, GPS satellites/HDOP,
roll/pitch tracking error; mode timeline and messages. Each finding has severity, value, threshold and meaning.

Project milestones (see the course page "Проекты"): add Blackbox (Betaflight) input via `blackbox_decode`,
EKF innovation checks (`XKF4`), a web upload form, and regression tests on real logs you collect.
