# Course Plan v3 — "From zero to a top UAV engineer"

Status: adopted 2026-11-08. Supersedes the track list in ROADMAP.md.
Inputs: two external reviews (`docs/reviews/`), owner requirements
(independent parallel firmware paths, deeper grading, serious depth).

## 1. What the course is

A self-paced engineering program, not a collection of articles. A graduate can:

1. explain *why* an aircraft flies and *why* a tuning parameter exists — with
   formulas and with the place in the log or source code where it shows up;
2. design a power, radio and sensor system from requirements and verify it by
   measurement (multimeter, oscilloscope, logic analyzer, logs);
3. diagnose failures from logs and instruments using a decision tree, and
   learn from documented real incidents;
4. operate legally and safely in a team, with written procedures and records;
5. write, test and document code on the aircraft and on a companion computer;
6. hand the project to another engineer: requirements → architecture → tests
   → documentation is a thread through every track, not a final module.

## 2. Principles (every module is checked against these)

| # | Principle | How it is enforced |
|---|---|---|
| P1 | Mechanism before recipe | `theory` section explains the physics/maths; numbers have units and sources |
| P2 | Measure, don't guess | every `practice` ends in a lab that produces an artifact: log, spectrum, table, measurement |
| P3 | Sources or it didn't happen | ≥3 references, graded A/B; facts verified against firmware sources/docs |
| P4 | Engineering method is a thread | eng-method-101 in track 0; every capstone requires an engineering folder (requirements with IDs → tests → changelog) and is graded with a good/bad rubric |
| P5 | Independent firmware paths | Betaflight / INAV / ArduPilot / PX4 paths have their own order, progress and "Continue"; shared modules count once everywhere |
| P6 | Honest status | planned modules are visibly marked; a "ready only" filter hides them |
| P7 | Assessment with evidence | module = 40% best quiz (pass ≥80%) + 60% lab criteria; capstone = criteria + rubric; transcript exportable |
| P8 | Safety and law first | f-safety, f-regulations, ops-field, ops-case-studies early (L1) |

## 3. Program structure

Four stages, eight tracks. Levels: L1 operator → L2 technician/integrator →
L3 systems engineer → L4 developer. Hours are study estimates.

### Stage A — Entry (L1, ≈45 h)

**Track 0 · Фундамент** — physics, electricity and method.
f-physics · **f-mechanics** (NEW: forces, moments, equations of motion, hover/climb/turn) · f-aero-props · **f-electricity-101** (NEW bridge: Ohm's law, power, thrust–current–voltage chain, multimeter, LiPo safety) · f-power · f-motors-esc · f-fc-sensors · f-frame-mech · f-safety · f-regulations · **f-components-choice** (NEW: choosing motor/ESC/frame/battery for a task and budget) · **eng-method-101** (NEW: requirements → architecture → tests → documentation on the first build) · tools-overview.
Capstone: Паспорт сборки — now requires measured hover current vs calculation (wattmeter, current sensor or thrust stand) and an engineering folder.

**Track 1 · Оператор** — runs in parallel with Track 0.
bf-intro · bf-ports · link-protocols · bf-modes-osd · bf-failsafe · link-elrs · link-vtx · ops-field · **ops-case-studies** (NEW: real incidents from public logs/reports, each as symptom → cause → evidence → consequence → fix) · **diag-troubleshooting** (NEW: decision tree "doesn't arm / doesn't take off / goes crazy above 70% throttle / ESC burns on plug-in").
Capstone: Первый квадрокоптер.

### Stage B — Technician → Integrator (L2, ≈70 h)

**Track 2 · Электроника и радио**
el-wiring · el-power-design · **el-battery-packs** (NEW: Li-Ion/LiFePO4 packs, spot welding, BMS, real discharge capability) · el-measure · el-emi · **el-peripherals** (NEW: connecting devices over UART/I2C/CAN, levels, port power, "how not to burn the FC") · rf-antennas · rf-link-budget · **el-redundancy** (NEW: X8/hexa/octo power and signal redundancy, current distribution).
Capstone: Электроника борта.

**Track 3 · Интегратор: настройка по данным**
data-python (with flight-quality metrics as formulas: overshoot, settling, jitter) · ctl-signals · bf-blackbox · bf-filters · bf-rpm-filter · bf-pid-reg-in-bf · bf-pid · ctl-theory · INAV elective.
Capstone: Тюнинг по логам.

### Stage C — Systems engineer (L3, ≈80 h)

**Track 4 · Навигация и оценка состояния** (the bottleneck named by both reviews — highest writing priority)
est-sensors · est-attitude · est-kalman · est-gnss · ap-ekf · est-alt-sources · **nav-resilience** (NEW: recognising degraded GNSS/compass in logs, EKF source fallbacks, behaviour on GPS loss, frequency planning; civilian scope).
Capstone: Оценка состояния.

**Track 5 · Автономия и платформы**
ap-intro · ap-sitl · ap-missions · ap-logs · ap-tuning · ap-lua · ap-safety-fs · aero-wing · ap-heavy · ap-quadplane · PX4 elective.
Capstone: Тяжёлая платформа или VTOL.

### Stage D — Developer (L4, ≈90 h)

**Track 6 · Инженер: код на борту**
comp-intro · comp-mavlink · comp-raspberry · comp-esp32 · ap-companion · emb-basics · emb-protocols · bf-cli · bf-cli-automation · bf-custom · fw-reading · **eng-ci-configs** (NEW: configs in git, `diff all` reviews, SITL tests in CI, code review) · eng-systems.
Capstone: Своя логика на борту. Starter repositories in `examples/` (SITL + pymavlink/MAVSDK, ROS 2 skeleton) so a simulation runs in 15 minutes.

**Track 7 · Восприятие (специализация)** — optional specialisation, labelled as such.
per-camera · per-cv · per-visual-nav · per-tracking. Capstone: Восприятие.

### Cross-cutting sections

- Справочник: per-firmware reference + **formulas & CLI reference page** (NEW).
- Глоссарий (exists), Поиск (exists).
- Фейлы: restructured as symptom → cause → log/oscillogram evidence → consequence → config fix.
- Interactive widgets: pid-sim, filter-response, elrs-calc (exist) + **tw-calc** (thrust/weight & flight time), **wire-drop** (voltage drop by gauge/length), **link-latency** (packet rate → latency/telemetry) (NEW).
- Progress: localStorage + export/import now; server API later (ARCHITECTURE.md). Transcript per path and per track.
- Feedback: GitHub issue template "Log review" (NEW).

## 4. Module contract (unchanged, enforced by validator)

Sections: summary · theory · practice (ends with "Лабораторная") · diagnostics (symptom → cause → action) · references (≥3, graded) · checklist. Quiz ≥5 questions, pass 80%. Curriculum entry: objectives, prerequisites, hours, lab criteria.

## 5. Implementation phases

| Phase | Scope | Exit criterion |
|---|---|---|
| 1 Structure | curriculum v3 (tracks reordered, 11 new planned modules, rubrics, engineering-folder deliverables), "ready only" filter, rubric rendering, fails restructure, formulas page, issue template | site rebuilt, CI green |
| 2 Stage A | f-mechanics, f-electricity-101, f-components-choice, eng-method-101, ops-case-studies, diag-troubleshooting; widgets tw-calc, wire-drop | Track 0 and 1 100% written |
| 3 Stage B | el-battery-packs, el-peripherals, el-redundancy, data-python, ctl-signals, ctl-theory; widget link-latency | Tracks 2, 3 100% written |
| 4 Stage C | est-sensors, est-attitude, est-kalman, est-gnss, est-alt-sources, nav-resilience, aero-wing, ap-tuning, ap-safety-fs | Tracks 4, 5 100% written |
| 5 Stage D | emb-basics, emb-protocols, fw-reading, eng-ci-configs, eng-systems, `examples/` starters | Track 6 100% written |
| 6 Specialisation | per-camera, per-cv, per-visual-nav, per-tracking | Track 7 written |
| 7 Depth pass | every pre-v3 module deepened: mechanisms, worked numbers, extended diagnostics, source re-verification | owner review |

Later (unchanged from ROADMAP): PWA/offline, progress server, SITL labs with automatic log checks.
