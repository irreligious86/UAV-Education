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
source_hash: dda28b6087e0
---

## summary
"Engineering method 101" introduced the requirements → architecture → tests → documentation cycle on a single build. This module is the same cycle at full scale, for a vehicle or system that someone else will carry on: how to write requirements that can be verified (with an ID, a criterion and a method), how to trace them to tests, how to run a system-level FMEA with mitigations and their verification, how to build a verification plan (SITL → bench → field), and how to document so that a handover takes an hour instead of a month. The lab: a complete documentation package for your own project.

## theory
### Requirements
A good requirement is **unambiguous, verifiable and has a source**. Structure: `ID | statement | acceptance criterion | verification method (analysis/simulation/bench/flight) | source (task, rule, standard) | priority`.

- Bad: "The drone shall fly for a long time." Good: `R-PWR-03 | Hover endurance with a 500 g payload of at least 25 min at 20 °C | log: hover current, capacity calculation ≥ 25 min; flight: ≥ 25 min until BATT_LOW | flight | customer task §2`.
- Classes: functional (what it does), performance (how much), constraints (mass, budget, law), safety (failsafe, zones), interfaces (MAVLink, payload power), operational (battery swap ≤ 2 min without tools).
- Safety requirements are **derived from the FMEA and the rules**, not made up out of thin air.
- Every requirement has an owner and a status (draft/approved/verified/not met).

### How to check the wording: INCOSE and EARS
The INCOSE Guide to Writing Requirements (v4, 2023) defines nine characteristics of an individual requirement: necessary, appropriate (for its level), unambiguous, complete, singular (one thought), feasible, verifiable, correct, and conforming (to the project's patterns) (C1–C9). A set of requirements has its own characteristics: complete, consistent, feasible, comprehensible, able to be validated, and correct (C10–C15). Of the guide's 42 rules, five catch almost every beginner mistake:
- **R7, vague terms:** "fast", "reliable", "user-friendly", "enough", "long": replace with a number.
- **R8, escape clauses:** "where possible", "if necessary", "as a rule": a requirement you are allowed not to meet is not a requirement.
- **R18, single thought:** "shall hold altitude and return on link loss" is two requirements and two tests.
- **R26, absolutes:** "always", "never", "100 %" cannot be verified; give a probability, a condition or a time.
- **R33–R34, range of values and measurable performance:** "±2 m in winds up to 8 m/s", not "holds altitude accurately".

To keep the condition from getting lost, the EARS syntax (Easy Approach to Requirements Syntax; Mavin et al., Rolls-Royce, RE'09 conference, 2009) is handy. Five patterns, with an example on a vehicle:

| Pattern | Keyword | Example |
|---|---|---|
| Ubiquitous | — | The vehicle shall record a flight log on board. |
| State-driven | WHILE | While the vehicle is in AUTO mode, it shall hold altitude within ±2 m in winds up to 8 m/s. |
| Event-driven | WHEN | When the RC signal has been absent for more than 1 s, the vehicle shall switch to RTL. |
| Unwanted behavior | IF … THEN | If the voltage stays below 3.5 V per cell for more than 10 s, then the vehicle shall switch to RTL. |
| Optional feature | WHERE | Where an airspeed sensor is fitted, the autopilot shall use it in TECS. |

The unwanted-behavior pattern is a direct bridge from the FMEA: every FMEA row with a "detection + response" mitigation becomes an IF … THEN requirement with a number in both the condition and the response. Combining WHILE + WHEN gives the complex pattern: "While the vehicle is airborne, when the geofence is breached, …".

### Architecture and interfaces
The system diagram: blocks (FC, companion, power, RC, video, payload), **the interfaces between them** with protocol, power and direction (the interface table is the main document during integration), and budgets: mass (with a 10% margin), power (per branch, from the power module), link (the link budget), compute (companion CPU). Decisions with their alternatives and the reason for the choice (ADR, architecture decision record: context, options, decision, consequences), so that a year from now you do not argue it all over again.

### System-level FMEA
The difference from the failsafe module: it covers not only in-flight failures but also integration failures (a firmware bug after an update, an incorrect build, human error during preparation), and for each one a **mitigation** (elimination, redundancy, detection, procedure) and **how the mitigation was verified** (a link to the test). The RPN is recalculated after the mitigations. The table is a living document, updated after every incident (review → a new row or an updated mitigation).

### Worked example: a three-row FMEA
Ratings on a 1–10 scale: S is the severity of the effect, O the likelihood of occurrence, D how hard it is to detect before harm is done (10 means we will not detect it). RPN = S·O·D gives the order in which to close risks; it is not an absolute measure.

| Failure | Effect | S | O | D | RPN | Mitigation | Requirement / test |
|---|---|---|---|---|---|---|---|
| RC loss at a distance | uncontrolled flight | 9 | 4 | 2 | 72 | `FS_THR_ENABLE` = RTL, RTL altitude above obstacles | R-SAF-01 / SITL `SIM_RC_FAIL` |
| Cold solder joint on a motor phase | crash (quad), yaw departure (X8) | 8 | 3 | 7 | 168 | load check and vibration test in the build checklist | R-MFG-04 / voltage-drop test |
| A new firmware renamed parameters | failsafe silently stops working | 9 | 3 | 8 | 216 | invariants in CI, parameter diff after an update | R-PRC-02 / `check_params.py` |

The surprise in this example is typical: the risk that feels "scariest" (link loss) is the best covered, and the highest RPNs belong to the build and the process, where detection is poor. That shift of attention is exactly what makes an FMEA valuable.

{{diagram:eng-trace-chain|The FMEA row with RPN 216 goes through the chain mitigation → requirement R-PRC-02 → test check_params.py → record → matrix; the test result comes back to the FMEA as a recalculated RPN.}}

### The S, O, D scales and the weak spots of the RPN
Ratings mean nothing until the scale has anchors. The course scale (a course guideline; write it at the top of your own FMEA so that a year from now you rate the same way):

| Score | S: effect | O: likelihood | D: detection before harm |
|---|---|---|---|
| 9–10 | uncontrolled flight or a crash outside the field, a risk to people | almost every flight; a known widespread problem | not detected by anything before the flight |
| 7–8 | a crash on the field, loss of the vehicle | once in tens of flights | only in flight, from the log afterwards |
| 4–6 | an aborted mission, an emergency landing | once in hundreds of flights | by a manual check, if someone remembers it |
| 1–3 | an inconvenience, an extra flight | not observed, prevented by design | automatically: pre-arm, CI, a test |

RPN = S·O·D has three known defects. First, the product of three numbers from 1–10 takes only 120 distinct values out of 1000 possible. Second, a single value hides different risks: RPN 72 comes from 24 different triples, from "S 9, O 4, D 2" to "S 2, O 4, D 9" (both counts are computed by the practice script). Third, high severity drowns when detection is good: a battery strap failure with S 10, O 2, D 3 gives RPN 60 and ends up at the bottom of the list. Hence the course rule: rows with S ≥ 9 are reviewed and closed with a mitigation regardless of RPN, and RPN sorts the rest. Industry took the next step: the AIAG & VDA FMEA Handbook (2019) replaced RPN with Action Priority tables (AP: high, medium, low) and introduced a seven-step approach. For a solo developer the S ≥ 9 rule plus recalculating RPN after the mitigations is enough.

### ADR: a decision you can reread
An Architecture Decision Record is a short file for each irreversible decision. Template:
```
# ADR-003: Li-Ion 6S2P instead of LiPo for the survey airframe
Status: accepted (2026-11-08)
Context: requirement R-PWR-03 (25 min hover with 500 g); hover current 16 A (R-PWR-01); LiPo 6S 5000 gives 15 min at 80 % DoD.
Decision: 6S2P P42A, 8.4 Ah: 6.7 Ah usable at 80 % DoD / 16 A = 25 min.
Consequences: +180 g, sag under punch ~1.5 V, no aggressive manoeuvres; BATT_* thresholds for Li-Ion.
Alternatives: LiPo 6S 8000 (heavier, hover ~18 A, 21 min at 80 % DoD), hybrid (out of budget).
```
Six months later, the question "why Li-Ion here?" is answered by a file, not by memory. The format was proposed by Michael Nygard (2011): title, context, decision, status, consequences. Statuses: proposed, accepted, deprecated, or superseded with a link to the new ADR. An old ADR is not rewritten or deleted but marked as superseded: the history of the decisions is the value. The files live in the project repository, one per decision, numbered (`doc/arch/adr-003.md` in Nygard's layout).

### Verification and validation
- **Verification** asks "did we build it right?": every requirement → a test with a method; the test plan goes in stages: analysis/calculation → SITL → bench (no props) → tethered/low flight → flight. The result of every test is a record with the date, the config (a tag!), the log and the verdict.
- **Four methods** (NASA Systems Engineering Handbook, §5.3): **inspection** (I), the visual examination of a realized end product; **analysis** (A), a mathematical model or calculation predicts the suitability of the design; **demonstration** (D), showing that the product meets the requirement, without detailed data gathering; **test** (T), operating the product to obtain detailed data. SITL is analysis, not test: it verifies a model running the firmware, not your vehicle (this follows from the definitions). So a safety requirement closed only by SITL is not closed yet: it needs a stage on hardware. The method is a column in the requirements table, with the letters I/A/D/T.
- **Validation** asks "did we build the right thing?": running the real task with the customer/user; it often reveals requirements nobody had written down.
- The traceability matrix: requirement ↔ test ↔ result. Empty cells are open requirements; tests without requirements are either unnecessary or a requirement has been forgotten.
- Regression: after any change, a set of mandatory tests (the SITL autotest from the CI module + a short flight checklist).

{{diagram:eng-verify-method-tree|The verification method is chosen by three questions: is the property visible without operating the product, can it be run safely, and is a number with a tolerance needed; SITL falls under analysis, so it cannot close a safety requirement on its own.}}

Part of the analysis is already written for you. ArduPilot 4.7.3 has a set of SITL autotests (`Tools/autotest/`), and for a requirement like `R-SAF-01` there is a ready-made test, `ThrottleFailsafe` (`Tools/autotest/arducopter.py:897`). Among other things, it sets `SIM_RC_FAIL` = 1 and checks how the firmware reacts. You run a single test like this: `./Tools/autotest/autotest.py build.Copter test.Copter.ThrottleFailsafe` (the name is parsed at `autotest.py:534–545`). Citing such a test in the matrix is legitimate if the firmware tag and your parameter file are recorded. The upstream test checks the logic with its own test values of `FS_*` (it cycles through several `FS_THR_ENABLE` values itself in subtests) and on the stock SITL model, not with your parameter file. So you add your own SITL run with your own parameters, as in `eng-ci-configs`.

### Baseline, reviews and interfaces
A **baseline** is a frozen set: the requirements, the tagged config, the BOM and the FMEA as of a date. After it, every change goes only through the change process below; otherwise the traceability matrix lies, because a "pass" refers to a different version. In practice a baseline is a git tag under which all the artifacts of the package live, not just the firmware.

**Review gates.** In large programs, moving between phases goes through reviews: requirements, preliminary design, critical design, test readiness. A solo developer needs two gates, each with its questions on paper. Before the build: every requirement has a method and a test, and the top FMEA risks have mitigations. Before the first flight: all tests of the "analysis" and "bench" stages have passed, the failsafe has been checked, and the baseline is tagged.

The **interface table** is a lightweight ICD (interface control document). A row of the table: from → to, physical layer (connector, wire, 3.3/5 V level), protocol and speed (CRSF at 420 000 baud, MAVLink 2 at 921 600), power (who supplies it, current), owner, test. Most integration failures are an interface without a row or a row without a test.

### Reference: the package artifacts and how to check them

| Artifact | What is inside | Format | How to check it yourself |
|---|---|---|---|
| Requirements | ID, EARS wording, I/A/D/T method, source, test | CSV/table in the repo | the practice script: no R7 words, a number present, a test present |
| ADR | context, decision, status, consequences | `doc/arch/adr-NNN.md` | every irreversible decision has a file; superseded ones are marked |
| Interface table (ICD) | from → to, physical layer, protocol, power, test | table | every cable on the diagram has a row |
| Budgets | mass +10 %, power per branch, link, CPU | table + calculation | the total agrees with the scales/log within ±10 % |
| FMEA | failure, S/O/D, RPN before/after, mitigation, requirement, test | CSV | rows with S ≥ 9 are closed with a mitigation; RPN recalculated |
| Test plan and test log | stage, date, tag, log, verdict | CSV + logs | every "pass" has a tag and a log |
| Traceability matrix | requirement ↔ test ↔ result | generated by a script | 0 holes |
| Config and baseline | parameters, firmware, tag | git | the `git tag` points at all the artifacts |
| CHANGELOG | date, what, why, link to a requirement/test | Markdown | every entry has a link |

{{lesson:eng-ci-configs|How to run these checks (parameter invariants, the SITL failsafe test, the trace script) automatically on every commit.}}

### Documentation you can hand over
The minimal package:
1. `README`: what it is, what it is for, its status, how to get it running in 15 minutes.
2. Requirements (the table) and ADRs.
3. Architecture: the diagram, the interface table, the budgets.
4. Build: a BOM with versions, a wiring diagram, photos, torque values where they matter.
5. Configuration: a tagged config repository (the CI module).
6. The FMEA and the failsafe settings with their rationale.
7. The test plan and test log, the traceability matrix.
8. Operations: checklists (preflight/postflight), the flight log, procedures (battery swap, calibrations, firmware update with rollback).
9. The changelog and known issues.
Quality criterion: another engineer can rebuild the vehicle from the package and fly it without asking the author anything. The test for this is to ask someone to try.

### Change process
Request → impact assessment on the requirements/FMEA → change in a branch → tests (regression) → review → tagged release → documentation updated in the same PR. Documentation updated "later" never gets updated.

{{diagram:v-model|The V-model: each level of requirements and design has its own level of verification, from unit tests to validation in the field.}}

### Where it fits

- **Takes in:** the "requirements → architecture → tests → documentation" cycle (`eng-method-101`); the list of failsafes as FMEA rows (`ap-safety-fs`); the power and link budgets (`el-power-design`, `rf-link-budget`).
- **Hands off:** requirements with a number and a criterion, to vehicle sizing (`des-sizing`); FMEA mitigations, to invariants and regression in CI (`eng-ci-configs`); redundancy decisions (`el-redundancy`).
- **If you get this wrong:** a requirement without a number ("it flew a long time") → the battery and motors are picked at random, and the short endurance shows up in the field; recalculation is in `des-sizing`. An interface without a row in the table (payload power, levels, protocol) → during integration a BEC gets overloaded or a port burns out (`el-peripherals`).

## practice
### Step 1. Requirements
20–40 requirements for your own vehicle in this structure; ≥ 5 safety requirements from the FMEA (the EARS "IF … THEN" pattern); each with a verification method (the letter I/A/D/T) and without the words from rule R7.

### Step 2. Architecture
The block diagram, the interface table, the mass/power/link budgets, 3 ADRs using the template above (for example: Li-Ion vs LiPo; ELRS 900 vs 2.4; a Pi vs a Jetson companion).

### Step 3. FMEA and test plan
A system FMEA (≥ 15 rows) in the format of the worked example: S/O/D/RPN, mitigation, a link to the requirement and the test; close the three risks with the highest RPN first and show how their O or D changed. The test plan by stages; the traceability matrix.

### Step 4. A script: requirements linter, matrix and FMEA ranking
Checking the matrix by eye across 30 requirements is tedious and unreliable. The script below does it in a second and exits with code 1 if there is a hole, which means you can put it in CI. The data inside are the rows of the module's worked example (R-SAF-01, R-PWR-01, an FMEA with RPN 216/168/162/72) plus three deliberate mistakes: a vague requirement, a requirement without a test, and a test without a requirement. You only need Python 3. Save it as `trace_lab.py`, run `python3 trace_lab.py; echo $?`, then replace the three CSV blocks with your own tables (or read them from files in the repo).

```python
#!/usr/bin/env python3
"""Traceability and FMEA checker for module eng-systems (stdlib only).

Keep requirements, tests, results and FMEA as CSV files in the project repo; this script is the
self-check: it lints requirement wording, finds holes in the trace matrix and ranks FMEA rows.
Exit code 1 when a hole is found, so the same script can run in CI (module eng-ci-configs).
Run: python3 trace_lab.py
"""
import csv
import io
import re
import sys

REQS = """id,text,method,source,test
R-SAF-01,When the RC signal is lost for more than 1 s the vehicle shall switch to RTL,T,FMEA F-07,T-12;T-31
R-PWR-01,Hover current with 500 g payload shall not exceed 16 A,T,power budget,T-05
R-PWR-03,Hover endurance with 500 g payload shall be at least 25 min at 20 C,A;T,customer 2,
R-OPS-02,Battery swap shall be fast and easy,D,operator,T-40
R-LNK-01,RC link margin at 3 km shall be at least 12 dB,A,mission 3 km,T-20
"""
TESTS = """id,stage,result,date
T-12,SITL,pass,2026-11-09
T-31,field,pass,2026-11-09
T-05,bench,pass,2026-11-10
T-20,analysis,pass,2026-11-10
T-40,bench,,
T-77,SITL,pass,2026-11-11
"""
FMEA = """id,failure,S,O,D,S_after,O_after,D_after
F-07,RC link lost far away,9,4,2,9,4,2
F-11,cold solder joint on motor phase,8,3,7,8,3,3
F-12,firmware update renamed failsafe parameters,9,3,8,9,3,2
F-14,BEC 5 V fails,9,3,6,9,3,3
F-15,battery strap fails in flight,10,2,3,10,2,3
"""

VAGUE = r"\b(fast|easy|quick|reliable|enough|good|user-friendly|as soon as possible|long)\b"
NUMBER = r"\d"


def rows(text):
    return list(csv.DictReader(io.StringIO(text)))


reqs, tests, fmea = rows(REQS), rows(TESTS), rows(FMEA)
test_ids = {t["id"]: t for t in tests}
holes = 0

print("1) Requirement lint (INCOSE R7 vague terms, R34 measurable, method in I/A/D/T):")
for r in reqs:
    issues = []
    if re.search(VAGUE, r["text"], re.I):
        issues.append("vague term")
    if not re.search(NUMBER, r["text"]):
        issues.append("no number")
    if not set(r["method"].split(";")) <= set("IADT"):
        issues.append("bad method")
    if not r["source"]:
        issues.append("no source")
    print(f"   {r['id']:<10} {'OK' if not issues else ', '.join(issues)}")
    holes += bool(issues)

print("2) Trace matrix:")
linked = set()
for r in reqs:
    ids = [x for x in r["test"].split(";") if x]
    linked.update(ids)
    if not ids:
        print(f"   {r['id']:<10} -> NO TEST")
        holes += 1
        continue
    res = [f"{i}:{test_ids[i]['result'] or 'not run'}" if i in test_ids else f"{i}:MISSING" for i in ids]
    print(f"   {r['id']:<10} -> {', '.join(res)}")
    holes += sum(1 for i in ids if i not in test_ids or test_ids[i]["result"] != "pass")
for t in tests:
    if t["id"] not in linked:
        print(f"   {t['id']:<10} -> test without requirement")
        holes += 1

print("3) FMEA ranking, RPN = S*O*D before -> after the measure:")
for f in sorted(fmea, key=lambda f: -int(f["S"]) * int(f["O"]) * int(f["D"])):
    before = int(f["S"]) * int(f["O"]) * int(f["D"])
    after = int(f["S_after"]) * int(f["O_after"]) * int(f["D_after"])
    flag = "  <- S>=9: review regardless of RPN" if int(f["S"]) >= 9 and before < 100 else ""
    print(f"   {f['id']} RPN {before:3} -> {after:3}  S={f['S']}{flag}")

distinct = {s * o * d for s in range(1, 11) for o in range(1, 11) for d in range(1, 11)}
print(f"4) RPN takes {len(distinct)} distinct values out of 1..1000; RPN 72 arises from "
      f"{sum(1 for s in range(1, 11) for o in range(1, 11) for d in range(1, 11) if s * o * d == 72)} (S,O,D) triples")

print(f"holes: {holes}")
sys.exit(1 if holes else 0)
```

The script output (Python 3, run while preparing the module; exit code 1):

```text
1) Requirement lint (INCOSE R7 vague terms, R34 measurable, method in I/A/D/T):
   R-SAF-01   OK
   R-PWR-01   OK
   R-PWR-03   OK
   R-OPS-02   vague term, no number
   R-LNK-01   OK
2) Trace matrix:
   R-SAF-01   -> T-12:pass, T-31:pass
   R-PWR-01   -> T-05:pass
   R-PWR-03   -> NO TEST
   R-OPS-02   -> T-40:not run
   R-LNK-01   -> T-20:pass
   T-77       -> test without requirement
3) FMEA ranking, RPN = S*O*D before -> after the measure:
   F-12 RPN 216 ->  54  S=9
   F-11 RPN 168 ->  72  S=8
   F-14 RPN 162 ->  81  S=9
   F-07 RPN  72 ->  72  S=9  <- S>=9: review regardless of RPN
   F-15 RPN  60 ->  60  S=10  <- S>=9: review regardless of RPN
4) RPN takes 120 distinct values out of 1..1000; RPN 72 arises from 24 (S,O,D) triples
holes: 4
```

How to read it. Block 1 catches `R-OPS-02` "fast and easy": that is a violation of R7 from the theory section; rewrite it along the lines of "battery swap ≤ 2 min without tools". Block 2 finds three holes: a requirement without a test (`R-PWR-03`), a test that has not been run (`T-40`) and a test without a requirement (`T-77`). Block 3 sorts the FMEA by RPN and flags the rows with S ≥ 9 and RPN below 100 that the sorting would otherwise bury: the battery strap failure (`F-15`, S = 10) comes last but is reviewed regardless. Block 4 is the proof of the RPN weakness from the theory section. The goal for your own project is `holes: 0` and exit code 0.

### Step 5. Package and handover
Assemble the package (items 1–9), put it aside for a week, then go through it yourself with the task "prepare the vehicle for flight from the documentation", looking at nothing but the package: the list of questions that came up → fixes.

### Worked example: requirement, test, traceability
- **Requirement:** `R-SAF-01`: when the RC signal is lost for more than 1 s, the vehicle performs RTL; verification by test. Source: FMEA row `F-07` "RC link loss".
- **Test:** `T-12`: SITL: the RC input switched off in LOITER 50 m from home; expected: RTL mode within 1.5 s, landing within 3 m of home. Stage 2 is a field test at 20 m altitude with an observer.
- **Traceability** (a fragment of the matrix):

| Requirement | Source | Test | Result |
|---|---|---|---|
| R-SAF-01 | FMEA F-07 | T-12 (SITL), T-31 (field) | pass 2026-11-09 |
| R-PWR-01 | power budget | T-05 (bench, hover current) | pass |

- **FMEA:** RPN = S × O × D (each 1–10). The row "5 V BEC failure: S 9, O 3, D 6 → RPN 162; mitigation: backup power for the receiver, a voltage check in the preflight checklist → D 3, RPN 81".

### What you should end up with
- Every requirement has an ID, a statement with a number, a verification method and at least one test. A requirement without a test and a test without a requirement are two kinds of the same hole.
- The top three FMEA risks are closed with mitigations, and you can see how far their RPN dropped.
- The README answers "how do I prepare the vehicle for flight" without the author around. The CHANGELOG is by date: what changed and why, with a link to a requirement or a test.

Self-check: the lab is done when the requirements have IDs and are traced to tests in the matrix, the FMEA with 15+ rows and mitigations for the top three risks is ready, and the README and the changelog have survived your own rereading a week later: every question that came up is recorded and closed with an edit to the document. For the step 4 script (the hardware-free path): on the built-in data the output matches the reference: `R-OPS-02` is flagged "vague term, no number", the matrix has exactly three holes (`R-PWR-03` without a test, `T-40` not run, `T-77` without a requirement), the FMEA is sorted 216 → 168 → 162 → 72 → 60 with flags on `F-07` and `F-15`, block 4 prints 120 values and 24 triples, `holes: 4`, exit code 1. On your own tables: `holes: 0` and exit code 0.

**Reference answer for self-check.** Compare your rows with the worked example. A correct requirement looks like `R-SAF-01`: a number in the statement (signal lost for more than 1 s → RTL), a verification method, a source (FMEA row `F-07`) and a test with a numeric expectation (`T-12`: RTL within 1.5 s, landing within 3 m). A correct FMEA row: RPN = S × O × D recalculated after the mitigation and lowered through O or D, as in 162 → 81 with D 6 → 3. Common mistake #1: a requirement without a number, so its test ends up being "by feel"; rewrite it with a number and a method. Common mistake #2: the matrix still has a requirement without a test or a test without a requirement; that is a hole, not a formatting nit. Common mistake #3: the script printed `holes: 3` on the built-in data: test `T-40` with an empty result was counted as passed; "not run" is a hole too. Common mistake #4: a safety requirement closed only by a SITL test; by the NASA methods that is analysis, and it still needs a test on hardware.

## diagnostics
- **Symptom:** there are requirements, but the tests are "by feel"
  - Possible cause: the acceptance criteria are not numeric.
  - What to do: rewrite them with numbers and a method; a requirement without a method is not a requirement.
- **Symptom:** everything broke after a firmware update
  - Possible cause: no regression tests and no rollback.
  - What to do: a tag before the update, a regression set, a rollback procedure in the documentation.
- **Symptom:** handing the project over took weeks
  - Possible cause: the knowledge is in someone's head, not in the package.
  - What to do: the handover test, ADRs, the interface table.
- **Symptom:** a serious failure "got lost" at the bottom of the FMEA
  - Possible cause: sorting by RPN only; a row with S = 10 and good detection gives a small product.
  - What to do: the S ≥ 9 rule: review regardless of RPN; the practice script flags such rows.
- **Symptom:** everything "passes" in SITL, but on the vehicle the failsafe behaved differently
  - Possible cause: SITL checked a model with default parameters (analysis), not your vehicle with your `FS_*` (test).
  - What to do: give safety requirements two tests in the matrix: SITL with your own parameters and a stage on hardware; the firmware tag and the parameter file go into the test record.
- **Symptom:** a test "passed", but after a config edit nobody knows whether it applies to the current version
  - Possible cause: there is no baseline; the test result was recorded without a tag.
  - What to do: every test record carries a git tag; after a change, the mandatory regression set.
- **Symptom:** the FMEA was written once and went stale
  - Possible cause: there is no process for updating it after incidents.
  - What to do: an incident review ends with a row in the FMEA and a change to a mitigation.

## references
- INCOSE — Technical publications (Systems Engineering Handbook) | https://www.incose.org/publications/products/technical-publications | secondary | B
- NASA — Systems Engineering Handbook, NASA/SP-2016-6105 Rev2 (NTRS) | https://ntrs.nasa.gov/citations/20170001761 | primary | A
- ArduPilot — Developer: testing and autotest as an example of verification practice | https://ardupilot.org/dev/docs/the-ardupilot-autotest-framework.html | primary | A
- NASA Systems Engineering Handbook, §5.3 Product Verification (methods: inspection, analysis, demonstration, test) | https://www.nasa.gov/seh/5-3-product-verification | primary | A
- INCOSE Guide to Writing Requirements v4 (2023) — summary sheet: characteristics C1–C15, rules R1–R42 | https://www.incose.org/docs/default-source/working-groups/requirements-wg/guidetowritingrequirements/incose_rwg_gtwr_v4_summary_sheet.pdf | primary | A
- Easy Approach to Requirements Syntax (EARS) — patterns and origin | https://en.wikipedia.org/wiki/Easy_Approach_to_Requirements_Syntax | secondary | B
- AIAG — FMEA: AIAG & VDA FMEA Handbook (7-step approach, Action Priority instead of RPN) | https://aiag.org/FMEA | primary | B
- Michael Nygard — Documenting Architecture Decisions (2011) | https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions | primary | A
- ArduPilot source, tag Copter-4.7.3: Tools/autotest/arducopter.py (ThrottleFailsafe) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.3/Tools/autotest/arducopter.py | primary | A

## checklist
- Requirements with an ID, a criterion and a verification method
- Architecture with an interface table, budgets and ADRs
- A system FMEA with mitigations and links to tests
- A traceability matrix with no empty cells
- The requirements pass INCOSE rules R7/R8/R18 and follow the EARS patterns, each with a method letter I/A/D/T
- The trace script gives `holes: 0`; FMEA rows with S ≥ 9 are closed with a mitigation regardless of RPN
- The documentation package passed the handover test
