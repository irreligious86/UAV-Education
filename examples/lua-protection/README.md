# Lua protection pack (project #11 starter)

An ArduPilot Copter script with two protections and a self-protection wrapper, plus a Python harness that
runs the **real Lua file** against a mock of the bindings it uses — fast unit tests before SITL.

```bash
pip install lupa pytest
python -m pytest -q tests      # 6 tests
```

| Protection | Trigger | Action |
|---|---|---|
| vibration | max(VIBE x,y,z) > `GRD_VIBE_MAX` for `GRD_VIBE_S` s | LAND |
| keep-in polygon | distance to the edge < `GRD_POLY_M` (or outside) | RTL |
| script health | 3 consecutive Lua errors while armed | RTL |

Each action fires once per flight and is announced with STATUSTEXT; disarming re-arms the guard. The script
logs `GRD` (Vib, Poly, Act) every cycle. Parameters live in table key 72 with prefix `GRD_`: pick a key no
other script on your vehicle uses.

On a vehicle: copy `scripts/guard.lua` to `APM/scripts/` on the SD card (or `scripts/` next to SITL),
`SCR_ENABLE 1`, reboot, then check `GRD loaded` in messages. The mock checks logic; the acceptance test is
SITL (course modules ap-lua, ap-sitl): a pymavlink test that injects vibration (`SIM_VIB_*`) or flies out
of the polygon and asserts the mode change. Keep `FENCE_*` and `FS_VIBE_ENABLE` configured — a script can
stop running, native failsafes cannot.
