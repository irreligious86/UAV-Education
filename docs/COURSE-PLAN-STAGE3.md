# Stage 3 plan: from "complete" to "verified"

Stage 2 is done: 103 modules, all published, every module with a quiz and a diagram, 71 numeric
tasks in 27 modules (plus the entry test), 12 project starters with unit tests in CI. What remains is not more content
but evidence that the content is right and that the labs actually work end to end.

## 0. Open items found by the audit (2026-11-08)

| Gap | Evidence | Iteration |
|---|---|---|
| Facts not re-verified against current firmware | only per-landing/perception were checked against source; the rest were written from documentation in one pass | 1 |
| External reference URLs never checked | `check_links.py` covers internal links only | 1 |
| Lab results are self-reported | graders emit `--json`, the progress page cannot read it; lab checks are manual ticks | 2 |
| Nothing runs in SITL in CI | `examples/sitl-pymavlink`, web-gcs e2e, Lua guard, precision landing are tested on mocks/fixtures only; `examples/ros2-docker` is never built | 3 |
| Numeric tasks in 27 of 103 modules | several calculation-heavy modules have none | 4 |
| Projects have acceptance criteria but no scoring rubric | `data/projects.json` has `acceptance`, no levels | 5 |
| Plan doc corruption | project row 7 in STAGE2 §6 overwritten by an iteration row (fixed in this commit) | — |

## 1. Fact-check pass (content correctness)

- Independent review by a separate agent that has not written the modules: per module, list every
  parameter name, default, unit, message id and CLI command; verify against the current
  ArduPilot 4.6 / PX4 1.15–1.16 / Betaflight 4.5 / INAV 8 documentation or source; record
  version-sensitive claims with "(since X.Y)".
- Output: `docs/reviews/factcheck-<date>.md` with a table claim → source → verdict; fixes land per
  track (one commit per track).
- External link check: a scheduled weekly workflow (non-blocking) that HEAD-requests every
  reference URL and opens an issue listing dead ones.

Done when: every module has been checked once, the report is in the repo, dead links are zero or
listed with replacements.

## 2. Lab results into progress

- One JSON schema for all graders: `{lab, module, version, passed, checks:[{id, ok, value}],
  inputHash}` (`docs/LAB-RESULTS.md`).
- `check_ap_lab.py`, `check_bf_log.py` and project checkpoint scripts write it with `--json`.
- Progress page: "Import lab result" accepts the file, marks the matching lab checks and stores
  the result; the transcript shows "verified by grader" versus "ticked by hand".
- Honest limit, stated on the page: this is self-study, the file can be forged; it proves the
  student ran the grader, not that a teacher saw it.

## 3. SITL in CI (nightly, not per push)

- Nightly workflow with the ArduPilot SITL container: `examples/sitl-pymavlink` labs, web-gcs
  bridge e2e (arm, takeoff, mode change visible over WebSocket), `guard.lua` in real SITL
  (vibration injected via `SIM_VIB_*`, polygon exit), precision landing with `lt_sender.py`.
- Weekly: build `examples/ros2-docker` images and run the PX4 offboard smoke test.
- Failures open an issue; per-push CI stays fast and unchanged.

## 4. More numeric tasks

Target: tasks in every module where a number decides something (~45 modules). Candidates:
f-frame-mech (natural frequency), per-camera (GSD, latency budget), inav-wing (stall speed, launch),
link-vtx (channel spacing), rf-antennas (polarization loss, Fresnel zone), est-gnss (DOP, RTK
baseline), ap-heavy (hover throttle, motor-out margin), f-mechanics, ctl-theory (phase margin),
bf-rpm-filter (harmonic frequencies from eRPM), per-cv (precision/recall from counts).

## 5. Project rubrics and reference checkpoints

- Add `rubric` to each project: 3–4 criteria × levels (meets / strong / exemplary) tied to the
  acceptance list.
- For each milestone, a checkpoint test the student can run (`checkpoints.py` pattern from #7).

## 6. Order and size

| # | Iteration | Size |
|---|---|---|
| 1 ✅ | fact-check pass + link checker: 2204 claims checked, 254 findings applied (125 errors), see `docs/reviews/factcheck/`; weekly `links.yml`, 18 dead links replaced | large (103 modules) |
| 2 ✅ | lab-result schema and import (`docs/LAB-RESULTS.md`), two graders, progress page import with ⚙ marks | medium |
| 3 | nightly SITL and Docker workflows | medium, needs CI minutes |
| 4 | ~11 modules of new tasks | medium |
| 5 | rubrics and checkpoints for 12 projects | medium |

Out of scope, unchanged from Stage 2: flight-simulator training, video content, country-specific law.
