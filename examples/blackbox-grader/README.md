# Betaflight Blackbox grader

Mirror of the ArduPilot grader (`examples/sitl-pymavlink/check_lab_log.py`) for the Betaflight labs:
decode the log with `blackbox_decode`, run one lab or all of them, get PASS/FAIL per check with the value,
the limit and what a failure means. Exit code 0 only when everything passes, so it works in CI too.

```bash
pip install numpy pytest
blackbox_decode LOG00001.BFL                                   # -> LOG00001.01.csv (blackbox-tools)
python check_bf_log.py LOG00001.01.csv --lab all --motor-range 48,2047 --json result.json
python make_bf_fixture.py practice.csv --kind noisy           # synthetic logs to practise on
python -m pytest -q tests                                      # 8 tests on synthetic logs
```

| Lab | Needs in the log | Checks | Course module |
|---|---|---|---|
| `filters` | `gyroUnfilt`, `gyroADC` | HF noise after filters, reduction in dB, dominant noise frequency | bf-filters, bf-rpm-filter |
| `tracking` | `setpoint`, `gyroADC` | relative tracking error on stick moves; residual rate with centred sticks (after a 300 ms settle) | bf-pid, bf-blackbox |
| `motors` | `motor`, `rcCommand[3]` | saturation share, per-motor imbalance in steady flight | bf-blackbox, f-motors-esc |
| `rpm` | `eRPM` (bidirectional DShot) | telemetry present and non-zero while motors spin | bf-rpm-filter |

Units follow Betaflight 4.x logs: gyro/setpoint in deg/s (`gyro_scale` = 1.0), `eRPM` column = eRPM/100,
time in µs. `--motor-range` comes from the log header line `motorOutput`. Thresholds are course defaults
for a 5" quad; override with `--set noise_max_dps=6` and write down why.
