# Perception labs (no drone required)

Small, tested building blocks for the perception track. numpy only; OpenCV is used in the module labs
but not needed for the tests.

```bash
pip install numpy pytest
python -m pytest -q tests                        # 14 tests
python latency_bench.py --size 320 --budget-ms 50
```

| File | What it gives you | Module |
|---|---|---|
| `camgeo.py` | intrinsics from FOV, radial distortion and its inverse, pixel → ray → ground point from attitude and altitude (and back), camera mount extrinsics, GSD/footprint/survey spacing, `LANDING_TARGET` angles | per-geometry, per-landing, per-mapping |
| `obstacles.py` | depth image → `OBSTACLE_DISTANCE` sectors (72 × 5°), nearest obstacle, stopping distance and the max safe speed for a sensor range | per-depth-avoid |
| `latency_bench.py` | warm-up, p50/p95/p99, budget verdict for any inference callable | per-edge-ml |
| `tests/` | synthetic round-trip checks (ground → pixel → ground with distortion and tilt), sign conventions, sector maps | — |

Frames: NED world, FRD body, OpenCV camera (x right, y down, z forward). Every function says which
frame its inputs and outputs are in — a wrong frame is the most common perception bug.
