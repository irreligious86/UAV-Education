---
id: eng-systems
title: "Systems engineering: requirements, FMEA, documentation, tests"
level: L4
readingTime: 40 min
firmware: any firmware
status: published
added: 2026-11-08
tags:
  - systems engineering
  - requirements
  - FMEA
  - documentation
  - tests
related:
  - eng-method-101
  - ap-safety-fs
  - eng-ci-configs
  - el-redundancy
next:
  - eng-ci-configs
source: content/companion/eng-systems.md
source_hash: 69b1062cf401
---

## summary
“Engineering method 101” introduced the requirements → architecture → tests → documentation cycle on a single build. This module is the same cycle at full scale, for an aircraft or a system that someone else will carry on: how to write requirements you can verify (with an ID, a criterion and a method), how to trace them to tests, how to do a system-level FMEA with mitigations and their verification, how to build a verification plan (SITL → bench → field) and how to document so that a handover takes an hour, not a month. The lab is a full documentation package for your own project.

## theory
### Requirements
A good requirement is **unambiguous, verifiable, with a source**. Structure: `ID | statement | acceptance criterion | verification method (analysis/simulation/bench/flight) | source (task, rule, standard) | priority`.

- Bad: “The drone must fly for a long time.” Good: `R-PWR-03 | Hover time with a 500 g payload of at least 25 min at 20 °C | log: hover current, calculation from capacity ≥ 25 min; flight: ≥ 25 min to BATT_LOW | flight | customer task §2`.
- Classes: functional (what it does), performance (how much), constraints (mass, budget, law), safety (failsafe, zones), interfaces (MAVLink, payload power), operations (battery swap ≤ 2 min with no tools).
- Safety requirements are **derived from the FMEA and the rules**, not made up out of thin air.
- Every requirement has an owner and a status (draft/approved/verified/not met).

### Architecture and interfaces
System diagram: blocks (FC, companion, power, RC, video, payload), **the interfaces between them** with protocol, power, direction (the interface table is the main document during integration), budgets: mass (with a 10% margin), power (per branch, from the power module), link (link budget), compute (companion CPU). Decisions with alternatives and the reason for the choice (ADR — architecture decision record: context, options, decision, consequences) — so you do not argue it all over again a year later.

### System-level FMEA
The difference from the failsafe module: you consider not only in-flight failures but also integration ones (a firmware bug after an update, a wrong build, human error during preparation), and for each — a **mitigation** (elimination, redundancy, detection, procedure) and **how the mitigation was verified** (a link to a test). The RPN is recalculated after mitigations. The table is alive and is updated after every incident (review → a new row/an updated mitigation).

### Worked example: a three-row FMEA
Ratings on a 1–10 scale: S — severity of consequences, O — occurrence, D — how hard it is to detect before harm (10 — we will not detect it). RPN = S·O·D — the order in which to close the risks, not an absolute measure.

| Failure | Consequence | S | O | D | RPN | Mitigation | Requirement / test |
|---|---|---|---|---|---|---|---|
| RC loss at a distance | uncontrolled flight | 9 | 4 | 2 | 72 | `FS_THR_ENABLE` = RTL, RTL altitude above obstacles | R-SAF-01 / SITL `SIM_RC_FAIL` |
| Cold solder joint on a motor phase | crash (quad), yaw drift (X8) | 8 | 3 | 7 | 168 | load check and vibration test in the build checklist | R-MFG-04 / voltage drop test |
| New firmware renamed parameters | failsafe silently does not work | 9 | 3 | 8 | 216 | invariants in CI, parameter diff after the update | R-PRC-02 / `check_params.py` |

The surprise in this example is typical: the risk that feels “scariest” (link loss) is the best covered, while the highest RPNs belong to the build and the process, where detection is poor. That shift of attention is exactly what makes an FMEA valuable.

### ADR: a decision you can reread
An Architecture Decision Record is a short file for every irreversible decision. Template:
```
# ADR-003: Li-Ion 6S2P instead of LiPo for the survey airframe
Status: accepted (2026-11-08)
Context: requirement R-PWR-03 (25 min hover with 500 g); LiPo 6S 5000 gives 17 min by calculation.
Decision: 6S2P P42A, 8.4 Ah, cruise current 22 A.
Consequences: +180 g, sag under punch ~1.5 V, no aggressive manoeuvres; BATT_* thresholds for Li-Ion.
Alternatives: LiPo 6S 8000 (heavier, 21 min), hybrid (out of budget).
```
Six months later, the question “why Li-Ion here?” is answered by a file, not by memory.

### Verification and validation
- **Verification** — “did we build it right?”: every requirement → a test with a method; a staged test plan: analysis/calculation → SITL → bench (no props) → tethered/low flight → flight. The result of every test is a record with a date, a config (a tag!), a log, a verdict.
- **Validation** — “did we build the right thing?”: a run of the real task with the customer/user; it often uncovers requirements that did not exist.
- Traceability matrix: requirement ↔ test ↔ result. Empty cells are open requirements; tests without requirements are either unnecessary or a requirement was forgotten.
- Regression: after any change — a set of mandatory tests (the SITL autotest from the CI module + a short flight checklist).

### Documentation you can hand over
Minimum package:
1. `README` — what it is, what it is for, its state, how to get it running in 15 minutes.
2. Requirements (a table) and ADRs.
3. Architecture: diagram, interface table, budgets.
4. Build: BOM with versions, wiring diagram, photos, tightening torques where they matter.
5. Configuration: a config repository with tags (the CI module).
6. FMEA and failsafe settings with their rationale.
7. Test plan and test log, traceability matrix.
8. Operations: checklists (preflight/postflight), flight log, procedures (battery swap, calibrations, firmware update with rollback).
9. Changelog and known issues.
Quality criterion: another engineer restores the aircraft from the package and performs a flight without asking the author anything. The test for this — ask someone to try.

### Change process
Request → impact assessment on requirements/FMEA → change in a branch → tests (regression) → review → tagged release → documentation update in the same PR. Documentation updated “later” is never updated.

{{diagram:v-model|The V-model: each level of requirements and design has its own level of verification — from unit tests to validation in the field.}}

## practice
### Step 1. Requirements
20–40 requirements for your aircraft using the structure; ≥ 5 safety requirements from the FMEA; each with a verification method.

### Step 2. Architecture
Block diagram, interface table, mass/power/link budgets, 3 ADRs using the template above (for example: Li-Ion vs LiPo; ELRS 900 vs 2.4; companion Pi vs Jetson).

### Step 3. FMEA and test plan
A system FMEA (≥ 15 rows) in the format of the worked example: S/O/D/RPN, mitigation, a link to the requirement and the test; close the three risks with the highest RPN first and show how their O or D changed. A staged test plan; a traceability matrix.

### Step 4. Package and handover
Assemble the package (items 1–9), have another person read it (or yourself a week later) with the task “prepare it for flight from the documentation” — the list of questions that came up → fixes.

### Worked example: requirement, test, traceability
- **Requirement:** `REQ-SAF-03` — on loss of the radio signal for longer than 1 s the aircraft performs RTL; verification — test. Source: FMEA row `F-07` “RC link loss”.
- **Test:** `T-12` — SITL: RC input switched off in LOITER 50 m from home; expected: RTL mode no later than 1.5 s, landing within 3 m of home. Stage 2 — a field test at 20 m altitude with an observer.
- **Traceability** (a fragment of the matrix):

| Requirement | Source | Test | Result |
|---|---|---|---|
| REQ-SAF-03 | FMEA F-07 | T-12 (SITL), T-31 (field) | pass 2026-11-09 |
| REQ-PWR-01 | power budget | T-05 (bench, hover current) | pass |

- **FMEA:** RPN = S × O × D (each 1–10). The row “5 V BEC failure: S 9, O 3, D 6 → RPN 162; mitigation — backup power for the receiver, voltage check in the preflight checklist → D 3, RPN 81”.

### What you should get
- Every requirement has an ID, a statement with a number, a verification method and at least one test. A requirement without a test and a test without a requirement are two kinds of the same hole.
- The top three FMEA risks are closed with mitigations, and you can see how their RPN dropped.
- The README answers the question “how do I prepare the aircraft for flight” without the author nearby. The CHANGELOG is by date: what changed and why, with a link to a requirement or a test.

The lab counts as done when the requirements have IDs and are traced to tests in the matrix, a 15+ row FMEA with mitigations for the top three risks is ready, and the README and the changelog have passed a read-through check with a list of fixed questions.

## diagnostics
- **Symptom:** there are requirements, but the tests are “by feel”
  - Possible cause: the acceptance criteria are not numeric.
  - What to do: rewrite them with numbers and a method; a requirement without a method is not a requirement.
- **Symptom:** after a firmware update everything broke
  - Possible cause: no regression and no rollback.
  - What to do: a tag before the update, a regression suite, a rollback procedure in the documentation.
- **Symptom:** the project handover took weeks
  - Possible cause: the knowledge is in someone's head, not in the package.
  - What to do: a handover test, ADRs, an interface table.
- **Symptom:** the FMEA was written once and went stale
  - Possible cause: no process for updating it after incidents.
  - What to do: an incident review ends with a row in the FMEA and a change to a mitigation.

## references
- INCOSE — Technical publications (Systems Engineering Handbook) | https://www.incose.org/publications/products/technical-publications | secondary | B
- NASA — Systems Engineering Handbook, NASA/SP-2016-6105 Rev2 (NTRS) | https://ntrs.nasa.gov/citations/20170001761 | primary | A
- ArduPilot — Developer: testing and autotest as an example of verification practice | https://ardupilot.org/dev/docs/the-ardupilot-autotest-framework.html | primary | A

## checklist
- Requirements with an ID, a criterion and a verification method
- Architecture with an interface table, budgets and ADRs
- A system FMEA with mitigations and links to tests
- A traceability matrix with no empty cells
- The documentation package passed the handover test
