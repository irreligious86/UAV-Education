# Course Plan — Stage 2: depth, software practice, infographics

Status: adopted 2026-11-08, implementation deferred (owner decision). Builds on `COURSE-PLAN.md` (v3,
phases 1–7 complete) and on the reviews in `docs/reviews/`. Owner's framing: an online course is
self-education, so hands-on flight practice is scarce — shift weight to theory and to practice that is
reproducible on a laptop (protocols, ROS 2, companion software, vision, data). Reviewer's framing:
do not add modules for volume; strengthen fundamentals, teaching method, engineering testing and
objective assessment.

## 0. Principles for this stage

| # | Principle | Consequence |
|---|---|---|
| P1 | Practice is software and reproducible | every lab runs on a laptop: SITL/Gazebo in Docker, Python, recorded data, open datasets |
| P2 | Assessment is objective | numeric-answer tasks, code autotests, log graders; quizzes test application, not recognition |
| P3 | Theory shows the mechanism and a picture | every new module ≥ 2 diagrams; every key existing module ≥ 1 |
| P4 | Depth, not breadth | new modules only where they close a gap in fundamentals, protocols or software; otherwise extend existing ones |
| P5 | One visual language | one diagram system, GC tokens, dark/light, works offline |

## 1. Infographics as a system

### 1.1 Infrastructure (first iteration)

| What | Where | How |
|---|---|---|
| Diagram files | `assets/diagrams/<id>.svg` | hand-written or generated SVG; colours via `currentColor` and GC CSS variables |
| Markdown tag | `{{diagram:<id>|caption}}` | new tag in `content_pipeline.py`; validator checks file and caption exist |
| Generated diagrams | `scripts/diagrams/*.py` → SVG | data-driven figures (mode tables, response curves, spectra) built from `data/` so they never drift from text |
| Flow diagrams | `scripts/diagrams/flow.py` | tiny "box → box" DSL, no external libraries |
| Style standard | `docs/DIAGRAMS.md` | diagram types, grid, labels, mandatory `<title>`, no raster images |
| CI check | `scripts/check_diagrams.py` | valid SVG, no external refs, < 60 KB, has `<title>` |

### 1.2 Diagram types and where they are mandatory

| Type | Example | Receiving modules |
|---|---|---|
| Data flow | gyro → filters → PID → mixer → ESC | f-fc-sensors, bf-filters, ctl-signals, fw-reading, px4-architecture, ap-ekf, comp-intro, per-* |
| Protocol frame (byte layout) | MAVLink v2, CRSF, DShot, I2C transaction, DroneCAN CAN-ID | comp-mavlink, link-protocols, f-motors-esc, emb-protocols, el-peripherals |
| Timing diagram | stick→motor latency chain, failsafe Stage 1/2, QuadPlane transition, offboard handshake | link-elrs, bf-failsafe, ap-quadplane, px4-ros2, per-tracking |
| System / wiring | power tree, on-board buses, companion ↔ FC ↔ GCS, MAVLink routing | el-power-design, el-peripherals, el-redundancy, comp-raspberry, comp-intro |
| Physics | forces/moments on a quad, actuator disk, wing (α, L, D, CG/NP), antenna patterns | f-physics, f-mechanics, f-aero-props, aero-wing, rf-antennas |
| Explanatory plot (generated) | PT1/PT2/notch response, FSPL vs range, V_s vs mass, discharge curve, spectrum with harmonics | bf-filters, rf-link-budget, aero-wing, f-power, ctl-signals |
| Decision tree | "won't arm", component choice, EKF source choice | diag-troubleshooting, f-components-choice, est-alt-sources, nav-resilience |
| Matrix / map | modes × sensors, failsafe × actions, firmware comparison | ap-intro, ap-safety-fs, inav-intro, px4-intro |
| Course map | stages → tracks → modules with firmware paths (interactive SVG) | index.html, path/* |

Target: ~120 diagrams (1–2 per existing module, 2–3 per new one).

## 2. Fundamentals: "Engineering mathematics for autopilots"

Placement: new elective **"Mathematical foundation" (L2–L3)** between stages B and C; prerequisite for
tracks 4–7; a "Mathematics" stage in the ArduPilot and PX4 paths before navigation.

| Module id | Content | Lab (Python, autotest) | Diagrams |
|---|---|---|---|
| `math-linalg-rot` | vectors/bases, dot/cross, rotation matrices and SO(3), quaternions (product, conjugate, rotating a vector), Euler angles and their degeneracy, small rotations and derivatives, FRD/NED ↔ ENU/FLU | `rot.py` (12 functions) tested against `scipy.spatial.transform`; numeric task "gravity vector in body axes for given angles" | 3D axes (widget exists), coordinate-system table, composition of rotations |
| `math-ode-dyn` | 1st/2nd-order ODEs, time constant, poles and stability, discretisation (Euler, Tustin), a quad axis as an ODE, transfer function | numpy axis simulation vs the PID widget; task "motor time constant from a logged step" | phase portrait, pole map ↔ response, discretisation |
| `math-prob-est` | random variables, variance, Gaussians, independence, fusing two measurements (= one Kalman step), covariance matrix and ellipse, sensor noise (ARW/VRW) | gyro bias/noise from a recording; numeric task "optimal fusion of two sensors" | Gaussian fusion, covariance ellipse, Allan deviation |

Plus `pages/prerequisites.html`: entry requirements for stage C, links to external courses (MIT OCW
18.06 / 2.003 / 6.041), a 10-task numeric entry test.

## 3. MAVLink mini-course (5 modules)

Placement: track 6 "Engineer"; existing `comp-mavlink` becomes the intro. Folder `content/companion/`,
starters in `examples/mavlink/`.

| Module | Theory | Lab | Autocheck | Diagrams |
|---|---|---|---|---|
| `mav-protocol` | v1/v2 frame byte by byte, seq and loss, CRC-16/MCRF4XX + CRC_EXTRA, signing, dialects/XML, `mavgen`, payload truncation, field types, extensions | decode frames by hand; generate a library from a custom XML with a new message | pytest: given frames decode, CRC matches | frame layout, dialect tree, signing |
| `mav-services` | heartbeat/state, parameters (read/write/timeouts/float packing), missions (COUNT/REQUEST/ITEM/ACK, partial updates, fence/rally types), commands and ACK incl. IN_PROGRESS, message intervals, MAVFTP, camera/gimbal, Remote ID | mission client from scratch with retries; upload/download/compare | pytest in SITL: mission matches | sequence diagram per microservice |
| `mav-routing` | sysid/compid routing, mavlink-router/mavproxy/mavp2p, serial/UDP/TCP, multiple GCS, SiK radios, 4G/LTE (NAT, VPN), Wi-Fi, loss/latency/jitter, encryption | router with 3 clients; latency and loss under `tc netem` | heartbeat RTT within threshold | topology, transport table, timing |
| `mav-component` | a component in the system, own parameter server, own messages, `NAMED_VALUE_*`, `DISTANCE_SENSOR`/`OBSTACLE_DISTANCE`, Python and C (ESP32) implementations, SITL test | virtual rangefinder in Python used by SITL EKF; then on ESP32 | pytest: ArduPilot sees RNGFND values | component in system, state machine |
| `mav-sdk` | MAVSDK (Python/C++) plugins, async, server side; pymavlink vs MAVSDK vs MAVROS vs DroneKit (deprecated) | same mission in MAVSDK; behaviour on disconnects | pytest | comparison table, API layers |

## 4. ROS 2 elective "Robotics on board" (6 modules)

Placement: elective next to INAV/PX4; mandatory stage in the PX4 path, recommended in ArduPilot.
Folder `content/ros2/`, manifest section "ROS 2". Environment `examples/ros2-docker/`
(Compose: ROS 2 Humble/Jazzy + Gazebo + PX4 SITL + ArduPilot SITL + MAVROS/AP_DDS) — `docker compose up`.

| Module | Theory | Lab | Diagrams |
|---|---|---|---|
| `ros2-basics` | node graph, topics/services/actions, QoS (why PX4 is best-effort), parameters, launch, `ros2 bag`, REP-103/105, `tf2`, sim time | telemetry node + logger node, bag record/replay | node graph, QoS matrix, tf tree |
| `ros2-px4` | uXRCE-DDS client/agent, `px4_msgs` versions, offboard node with a state machine (arm→offboard→mission→land), timesync, Gazebo gz_x500 | square flight with protections; test via bag | offboard state machine, uXRCE scheme |
| `ros2-ardupilot` | MAVROS (topics/services/plugins, frame conversion), AP_DDS (native DDS, `DDS_ENABLE`), comparison with the PX4 route | same square via MAVROS and AP_DDS | two routes, topic mapping |
| `ros2-app-arch` | node separation (perception / decision / protections / bridge), lifecycle nodes, watchdog node, parameters, containers, autostart, bag-based debugging, profiling | 4-node skeleton with watchdog; kill perception — protections hold | architecture, lifecycle |
| `ros2-nav` | occupancy map, global/local planners (Nav2 overview), obstacle avoidance with rangefinders/depth, plan → GUIDED/Offboard setpoints, 3D limits | avoid an obstacle in Gazebo with a lidar | Nav2 layers, example map |
| `ros2-from-ros1` | differences, reading ROS 1 projects (MAVROS 1, catkin), ros1_bridge, migration | port a small ROS 1 package | mapping table |

## 5. Perception track: 4 → 9 modules

Placement: track 7; move content to `content/perception/`. Lab data in `examples/perception-data/`
(open datasets + small recorded bags/videos).

| Module | Theory | Lab (no drone) | Diagrams |
|---|---|---|---|
| `per-geometry` | pinhole, intrinsics, distortion, checkerboard calibration, stereo and baseline, pixel → ray → ground point from height and attitude, PnP, camera–IMU extrinsics | calibration from video; ground coordinate of an object from frame + ATT + altitude; synthetic check | pinhole, stereo geometry, transform chain |
| `per-landing` | AprilTag/ArUco → pose → `LANDING_TARGET`, ArduPilot PLND_*, PX4 precision landing, filtering, target loss, switch altitudes | SITL + simulated camera (Gazebo) landing on a marker | landing loop, phase timing |
| `per-depth-avoid` | stereo/ToF/lidar/radar, depth maps, `OBSTACLE_DISTANCE`, BendyRuler/Dijkstra, PX4 collision prevention, sensor limits | avoidance in Gazebo with a depth camera | sector obstacle map, algorithms |
| `per-mapping` | survey planning (GSD, overlap), georeferencing (EXIF, log, timesync), OpenDroneMap/WebODM, orthophoto/DEM/point cloud, accuracy and GCPs | full pipeline on an open dataset | pipeline, overlap geometry |
| `per-edge-ml` | quantisation, profiling, thermal budget, held-out evaluation, model versioning/rollback, drift monitoring | profile a model on CPU/GPU, report | on-board MLOps loop |

Existing `per-camera`, `per-cv`, `per-visual-nav`, `per-tracking` gain labs on recorded data.

## 6. Project catalogue "Software for UAS"

Placement: `data/projects.json` → `projects/<id>.html` + `pages/projects.html`. Card: goal,
architecture diagram (mandatory), stack, starter in `examples/`, milestones, acceptance criteria,
autotests, deliverables. A project can replace the hardware capstone of its track (`capstoneFor`).

| # | Project | Replaces capstone of | Stack | Autocheck |
|---|---|---|---|---|
| 1 | Web GCS: telemetry, map, modes | 6 | Python (MAVLink → WebSocket), JS/Leaflet | e2e in SITL |
| 2 | Fleet telemetry to the cloud + dashboard | 6 | MQTT, InfluxDB/Timescale, Grafana, Docker | ingest test |
| 3 | Log analysis service | 3 | Python, pymavlink/blackbox_decode, HTML report | fixtures |
| 4 | Detector + tracker + following in Gazebo | 7 | ROS 2, OpenCV, YOLO-nano | SITL test |
| 5 | Precision landing on a marker in simulation | 7 | ROS 2/MAVLink, ArUco | SITL test |
| 6 | Route inspection with georeferenced findings | 5/7 | missions, camera, EXIF, report | fixtures |
| 7 ✅ | Perception +5 modules (per-geometry, per-landing, per-depth-avoid, per-mapping, per-edge-ml; 5 diagrams, 11 tasks; parameters and the LANDING_TARGET sign/timestamp handling verified against ArduPilot source, PLD_*/CP_* against PX4 docs), `examples/perception` (15 tests); starters for projects #4 `examples/follow-target`, #5 `examples/precision-landing`, #7 `examples/perception/checkpoints.py` (all in CI) | labs without a drone |
| 8 | MAVLink component on ESP32 + SITL twin | 6 | C/ESP-IDF, Python | pytest |
| 9 | 4G/Wi-Fi bridge with reconnect and encryption | 6 | Python/Go, VPN | loss test |
| 10 | Fleet CI/CD | 6 | GitHub Actions, SITL | exists |
| 11 | Lua protection package with tests | 5 | Lua, SITL | autotest |
| 12 | TX16S companion | 6 | ESP32, EdgeTX Lua | emulator |

## 7. Objective assessment

| Mechanism | Where | Implementation |
|---|---|---|
| Numeric-answer tasks | calculation modules (aero, power, link budget, wires, V_s, FSPL, Kalman, mathematics) | `content/tasks/<id>.json` (parametrised statement, tolerance), `<uav-task>` widget, score in progress |
| Code lab autotests | all new modules + existing companion ones | `examples/*/tests/`, "how to run" page, JSON result importable into progress |
| Application quizzes | every module, 2–3 questions | "given a log fragment / frame / config — find the fault" |
| Blackbox grader | Betaflight modules | `check_bf_log.py`, mirror of the ArduPilot grader |
| Grading model | `grading.js` | module = quiz 30 % + tasks 30 % + lab 40 %; track adds project/capstone |

## 8. Where it lands in the course structure

```
Stage A   unchanged
Stage B   Track 2, Track 3  + elective "Mathematical foundation" (3)
Stage C   Track 4, Track 5  (prereq: mathematics)
Stage D   Track 6 "Engineer" (+5 MAVLink) · elective "ROS 2" (6) · Track 7 "Perception" (4 → 9)
Cross     Projects (12) · numeric tasks · infographics · Docker environments
Paths     ArduPilot: + "Mathematics", "MAVLink", "ROS 2 (recommended)", "Project"
          PX4:       + "Mathematics", "MAVLink", "ROS 2 (mandatory)", "Project"
          Betaflight/INAV: + "Mathematics (optional)", projects #3 / #10
```

Totals: +19 modules, 12 projects, ~120 diagrams, 4 Docker environments, a task system.

## 9. Iterations (each one lands on the site with CI green)

| Iteration | Scope | Exit criterion |
|---|---|---|
| 1 ✅ | diagram infrastructure (`{{diagram}}`, standard, CI check) + 25 diagrams on key existing modules | diagrams on all pillar modules of tracks 0–3 |
| 2 ✅ | numeric task system + 31 tasks in 14 calculation modules; grading 30/30/40 (`docs/TASKS.md`) | tasks count in progress |
| 3 ✅ | mathematics elective (3 modules, 9 tasks, 3 diagrams) + `pages/prerequisites.html` with a 10-task entry test; stage "Математика" in the ArduPilot and PX4 paths | prerequisites wired in curriculum |
| 4 ✅ | MAVLink mini-course (5 modules, 3 sequence/topology diagrams) + `examples/mavlink/` with 12 pytest tests against a lossy fake vehicle (CI; SITL steps are in the labs) | labs autotested in CI |
| 5 ✅ | `examples/ros2-docker/` (Compose: ROS 2 Humble, PX4 SITL + Gazebo, ArduPilot SITL + DDS) and `uav_ros2_labs` (logger, PX4 offboard square, AP_DDS square; flight logic as a pure state machine with 11 CI tests) + modules ros2-basics, ros2-px4, ros2-ardupilot. Image builds not exercised in CI (registry access) | flight logic tested in CI; flights in Gazebo are the student lab |
| 6 ✅ | ROS 2 modules 4–6 (ros2-app-arch with a tested watchdog, ros2-nav with a tested A* planner, ros2-from-ros1); project catalogue `data/projects.json` → `projects/` (12 cards, each with an architecture diagram, milestones, acceptance criteria tracked like capstones, validated in CI); starters for #1 web GCS (`examples/web-gcs`, 6 tests), #3 log service (`examples/log-report`), #8 (`examples/mavlink`), #10 (`examples/sitl-pymavlink`) | projects with autotests |
| 7 | Perception +5 modules, lab data, projects #4, #5, #7 | labs without a drone |
| 8 | remaining projects (#2, 6, 8, 9, 11, 12), Blackbox grader, application quizzes | catalogue of 12 |
| 9 | second infographics wave (to ~120), consistency review of all modules | every module ≥ 1 diagram |

Effort: iterations 1–3 are fast (structure + text); 4–8 are the heavy ones (code and simulation);
9 is review.

## 10. Out of scope for this stage

Flight-simulator training (Liftoff/Velocidrone): a short "how to train your hands" note in the
Operator track at most — the course is an engineering program, not a flight school. Video content:
separate decision. Country-specific law: stays as structure + pointers, not as retold regulations.
