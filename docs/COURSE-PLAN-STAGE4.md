# Stage 4 plan: depth, missing topics, real charts

Audit of 2026-11-08 over all 103 modules (word counts per section, diagrams, widgets, references,
quizzes, tasks; topic map against a full UAV-engineer syllabus; every external URL).

## 1. Audit results

### Depth

Median module: 641 words of theory, 175 words of practice. That is a solid reference page, not a
lesson that takes a beginner to "I can do this". Thinnest modules (theory words / practice words):

| Module | Theory | Practice | Why it matters |
|---|---|---|---|
| px4-companion-jetson | 401 | 468 | still written for the EOL Jetson Nano, mixed with Orin Nano; legacy how-to style |
| est-kalman | 433 | 308 | the core estimation idea of the course, 3 references |
| el-wiring | 437 | 105 | failures in the field are mostly connections |
| el-emi | 443 | 126 | compass/GPS problems start here |
| rf-antennas | 448 | 145 | no radiation patterns, no placement practice |
| inav-intro / inav-missions / inav-ipf | 450–506 | 139–173 | INAV track is the thinnest track overall |
| ap-companion | 479 | 259 | first "code controls the vehicle" module |
| comp-raspberry | 480 | 190 | |
| px4-ros2 | 495 | 194 | L4 module with L2 depth |
| eng-systems / eng-ci-configs | 501–505 | 112–115 | practice is one paragraph |
| per-cv / per-camera / per-tracking | 511–545 | 103–162 | perception track depth is uneven (per-landing/per-mapping are 2× longer) |
| ctl-signals | 529 | 119 | spectra without a single plotted spectrum |
| ap-sitl | 546 | 203 | entry point to every lab |

Practice under 150 words in 30 modules: a student reads "do X, check Y" without a worked example.

### Missing topics (for a complete picture)

| # | Topic | Where it would sit | Why |
|---|---|---|---|
| 1 | DroneCAN / Cyphal: CAN GPS, ESC, power monitors, node setup | electronics + ArduPilot/PX4 | standard on every serious airframe; only mentioned today |
| 2 | Digital FPV video: DJI O3/O4, Walksnail, HDZero, OpenIPC; latency and range | link | link-vtx covers analog tables only |
| 3 | Gimbals and payload control: MAVLink Gimbal Protocol v2, MNT1_*, camera protocol | companion / ArduPilot | inspection and mapping projects depend on it |
| 4 | Simulation beyond SITL: Gazebo (gz) worlds, sensor plugins, HITL, scenario tests | tools | perception labs need cameras and obstacles |
| 5 | System identification: chirp/SYSID mode, model fitting, using the model for tuning | estimation / tools | turns tuning from folklore into engineering |
| 6 | Guidance and trajectories: L1/NPFG, S-curves, pure pursuit, minimum-snap | ArduPilot/PX4 / ros2 | "how the vehicle follows a path" is not taught |
| 7 | ArduPlane tuning: roll/pitch autotune, TECS tuning, NPFG/L1, landing | ArduPilot | aero-wing explains, nothing tunes a plane |
| 8 | ESC firmware and configuration: Bluejay, AM32, BLHeli_32 legacy, timing, PWM frequency | foundation | spread across 7 modules as one-liners |
| 9 | Hardware design: KiCad, a sensor or power board, layout for EMC, sensor placement | electronics | top-level engineers design boards |
| 10 | Remote ID and security: Remote ID broadcast, MAVLink signing in practice, link encryption, firmware integrity | foundation / companion | regulatory requirement plus a real attack surface |
| 11 | Long-range telemetry radios: SiK/RFD900, LoRa, Herelink, mesh; MAVLink over them | link | mav-routing touches transport, not the radios |
| 12 | Multi-vehicle operations: sysid plan, deconfliction, formation basics | companion | the fleet project has no theory module |
| 13 | Weather and flight planning: wind and gusts, density altitude, cold batteries, icing | foundation | ops-field assumes it |
| 14 | Maintenance and reliability: logbooks, battery lifecycle, inspection intervals, MTBF thinking | foundation | turns hobby practice into operations |

### Graphics

- 97 of 103 modules have exactly one diagram; 6 have two. Wave 2 diagrams are structural (boxes, trees,
  sequences) — good for "what talks to what", useless for "how much".
- **No quantitative charts at all.** Nothing plots a thrust curve, a discharge curve under load, a filter's
  frequency response, a gyro spectrum with motor harmonics, an antenna pattern, link margin vs distance,
  Kalman covariance converging, overshoot vs damping. The site has `assets/widgets/plot.js`, but it is
  used only inside 7 widgets.
- Interactive widgets live in 11 modules (wire-drop, elrs-calc, link-latency, attitude-3d, tw-calc,
  pid-sim, filter-response); est-kalman, rf-antennas, per-geometry/per-mapping, bf-rpm-filter and
  ctl-signals would benefit most from one.

### Links and documentation

Fixed in this pass (see commit "Replace stale documentation links"): archived Betaflight GitHub wiki,
Betaflight 4.0 CLI and 4.1 tuning notes, Naze32-era guides, a docs mirror, a YouTube search link, a
forum thread and a random repo, a personal GStreamer page, a French GitHub Docs link, an ESP32-C2 page
used for ESP32, ROS 2 concept pages pinned to Humble. The link checker now also reads front-matter
reference lists, and the validator rejects malformed reference sections (bf-blackbox rendered none).

Still to do:
- px4-companion-jetson: rewrite for Jetson Orin Nano / JetPack 6 (the Jetson Nano is end-of-life);
  verify UART device names against NVIDIA documentation.
- ✅ ROS 2: Jazzy first in ros2-basics, ros2-app-arch, px4-ros2; the course Docker image takes `ROS_DISTRO` (default jazzy, `ROS_DISTRO=humble` as fallback). Not test-built here (Docker Hub unreachable from the build environment) — first local build should confirm.
- ✅ Vendor support pages (SpeedyBee) in bf-intro and bf-ports → Betaflight Serial/Setup/GPS Rescue 4.5 docs and ExpressLRS FC configuration.
- ✅ Plasmatree PID-Analyzer marked legacy (unmaintained since 2019) in bf-pid.
- ✅ PIDtoolbox became a paid product in 2024; modules now point to PIDscope (GPL-3.0 GNU Octave continuation, maintained in 2026).
- NXP UM10204: `https://www.nxp.com/docs/en/user-guide/UM10204.pdf` is still the canonical location (search engines index it); the 404 is NXP refusing automated clients. Kept.
- ✅ QGroundControl docs now link `Stable_V5.0` instead of `master`.
- Every module has exactly 2–6 references, mostly 3; primary sources for the fact-checked claims
  (parameter reference pages, source files) should be added where the fact-check relied on them.

## 2. Iterations

| # | Iteration | Content | Done when |
|---|---|---|---|
| 1 ✅ | Chart toolkit | `scripts/diagrams/plot.py`: static SVG line/polar/log plots from computed data, same theme as diagrams; 12 charts: thrust & current vs throttle, LiPo/Li-Ion discharge under load, PT1/biquad/notch response, gyro spectrum with harmonics, dipole/patch patterns, link margin vs distance, Kalman gain/covariance, overshoot vs ζ, step responses, GSD vs altitude, glass-to-glass latency stack, aliasing | charts in the 12 modules they belong to, checked at phone width |
| 2 ✅ | Deepen the thinnest modules — done: est-kalman, el-wiring, el-emi, rf-antennas, ctl-signals, px4-companion-jetson (rewritten for Orin), inav-missions, inav-ipf, inav-intro, ap-companion, eng-ci-configs, eng-systems, per-cv, per-camera, px4-ros2; every added code sample was run or compiled. Left for later passes: comp-raspberry, per-tracking, ap-sitl (Alex runs SITL locally) | worked example, numbers, runnable code in each |
| 3 ✅ | New modules, wave 1 — done: el-dronecan, link-digital-video, payload-gimbal, f-esc-firmware, ap-plane-tuning, f-remote-id-security; fact-check `docs/reviews/factcheck/stage4-new-modules.md` (4 findings applied) | DroneCAN, digital FPV video, gimbals and payloads, ESC firmware, ArduPlane tuning, Remote ID and security | each with quiz, diagram, references, curriculum entry, fact-checked by an independent agent |
| 4 ✅ | New modules, wave 2 — done: ops-weather, ops-maintenance, link-telemetry-radios, mav-multi-vehicle, ctl-guidance, ctl-sysid, tools-gazebo, el-kicad; fact-check `stage4-wave2.md` (14 findings applied) | Gazebo simulation, system identification, guidance and trajectories, long-range telemetry radios, weather and planning, maintenance and reliability, multi-vehicle ops, hardware design (KiCad) | same bar as wave 1 |
| 5 ✅ | Widgets — done: kalman-1d (est-kalman), link-margin (rf-link-budget), gsd-calc (per-mapping), rpm-harmonics (bf-rpm-filter), antenna-pol (rf-antennas); checked in Chromium at 1200 and 390 px, no console errors | Kalman 1D, antenna polarization/pattern, GSD and overlap calculator, RPM harmonics vs filter, FSPL vs distance | each widget used in at least one module, works offline |
| 6 ✅ | ROS 2 Jazzy-first pass and remaining link items — done (see “Still to do” above) | | link check clean, Jazzy commands first everywhere |

SITL in CI stays postponed (Stage 3, iteration 3): Alex runs SITL locally.

Curriculum consistency (fixed): prerequisites placed later in their track (f-aero-props, emb-basics, mav-routing,
mav-component, fw-reading) — tracks reordered by dependency; validate_content.py now rejects this.
