# Precision landing (project #5 starter)

Precision landing in ArduPilot SITL **without Gazebo**: a synthetic downward camera computes where the
marker would appear in the frame from the vehicle's real SITL state, applies detection limits, noise,
dropouts and camera latency, and sends `LANDING_TARGET` with the exposure timestamp.

```bash
pip install pymavlink numpy pytest
python -m pytest -q tests                       # 7 tests

# SITL (second MAVLink output to 14551): PLND_ENABLED=1 PLND_TYPE=1 PLND_EST_TYPE=1 RNGFND1_TYPE=100
python lt_sender.py --url udpin:0.0.0.0:14551 --marker 3.0 -2.0 --dropout 0.1
# take off to 10 m, switch to LAND; log message PL shows the target being tracked
python landing_stats.py touchdowns.csv --marker 3.0 -2.0      # exit 0 when ≥ 9/10 within 15 cm
```

| File | Role |
|---|---|
| `target_sim.py` | synthetic camera + detector over `examples/perception/camgeo.py` (range, frame limits, noise, dropouts) |
| `lt_sender.py` | SITL bridge: state in, delayed detections out as `LANDING_TARGET` on the vehicle's clock |
| `landing_stats.py` | touchdown error statistics and the project's acceptance verdict |

Milestones (course page "Проекты → 5"): replace the synthetic camera with ArUco on a Gazebo camera, nested
markers, `PLND_STRICT` experiments, wind (`SIM_WIND_SPD`), PX4 precision land.
