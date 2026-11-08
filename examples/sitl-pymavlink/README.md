# ArduPilot SITL + pymavlink starter

## 1. Run SITL (Docker, no toolchain on the host)

```bash
docker run --rm -it -p 5760:5760 -p 14550:14550/udp \
  ardupilot/ardupilot-dev-base:latest bash -c \
  "git clone --depth 1 https://github.com/ArduPilot/ardupilot.git && cd ardupilot && \
   git submodule update --init --recursive --depth 1 && \
   Tools/autotest/sim_vehicle.py -v ArduCopter -f quad --no-mavproxy --out=udp:host.docker.internal:14550 -w"
```

Alternative without Docker: follow https://ardupilot.org/dev/docs/setting-up-sitl-on-linux.html
and run `sim_vehicle.py -v ArduCopter --console --map`.

SITL listens on TCP 5760 (first MAVLink client) and forwards to UDP 14550 (GCS such as QGroundControl / Mission Planner).

## 2. Fly a square

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install pymavlink
python3 fly_square.py --connect tcp:127.0.0.1:5760
```

## 3. Failsafe test (what CI runs)

```bash
python3 test_failsafe.py --connect tcp:127.0.0.1:5760   # exit code 0 = pass
```

The test arms in GUIDED, climbs to 10 m, simulates RC loss (`SIM_RC_FAIL = 1`) and asserts
that the mode changes to RTL or LAND within 5 s. Break it on purpose (`FS_THR_ENABLE = 0`)
to see it fail — a test that cannot fail proves nothing.

## 4. Grade a lab log automatically

```bash
python3 check_lab_log.py logs/00000012.BIN --lab failsafe    # also: mission | hover | motorfail
```

Prints PASS/FAIL per criterion (RC failsafe triggered, mode changed within 5 s, …) and exits 0/1.
SITL logs are in `logs/` next to where `sim_vehicle.py` ran; real logs come from the SD card.
The checks are deliberately simple and readable — extend them for your own labs.

## Files

- `fly_square.py` — connect, wait for EKF, arm, takeoff, 4 waypoints in GUIDED, land.
- `test_failsafe.py` — RC-failsafe assertion, usable in GitHub Actions.
- `ci.yml` — example workflow (copy to `.github/workflows/`).
- `check_lab_log.py` — lab grader for DataFlash logs (failsafe, mission, hover, motor failure).
- `make_fixture_log.py`, `test_check_lab_log.py` — synthetic DataFlash fixtures and the grader's self-test (CI).
