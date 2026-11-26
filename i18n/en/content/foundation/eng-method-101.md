---
id: eng-method-101
title: "Engineering Method 101: Requirements, Architecture, Tests, Documentation"
level: L1
readingTime: 30 min
firmware: any firmware
status: published
added: 2026-11-08
tags:
  - engineering method
  - requirements
  - tests
  - documentation
related:
  - f-components-choice
  - tools-overview
  - f-safety
next:
  - tools-overview
source: content/foundation/eng-method-101.md
source_hash: ae91b13ffb1e
---

## summary
The difference between a builder and an engineer isn't the soldering iron but the method: an engineer knows *what* the vehicle must do (requirements), *how* it's put together (architecture), *what* proves that it does it (tests), and leaves a trail that lets another person continue the work (documentation). This module introduces the method at the very start of the course — using your first build as the example — and sets the format of the “engineering folder,” which from now on is mandatory in every capstone project.

## theory
### Why a beginner needs this
Without requirements, any tuning “worked” or “didn't work” based on gut feeling. Without architecture, troubleshooting is trial and error. Without tests, you don't know what you broke with yesterday's change. Without documentation, a month from now you're a stranger to yourself. The method costs an hour up front and saves days later; in big projects (see the accident case studies) its absence costs vehicles and reputations.

### 1. Requirements
A requirement is a statement about what the vehicle must do that can be **verified**. Format: ID, text, criterion, verification method.

| ID | Requirement | Criterion | Verification |
|---|---|---|---|
| R-01 | Hovers with a 30 g payload for at least 15 min | ≥ 15:00 down to 3.5 V/cell | Timed flight, voltage log |
| R-02 | T/W at takeoff weight ≥ 2.5 | calculation and hover throttle ≤ 40% | Thrust table + log |
| R-03 | On link loss, lands in place after 1.5 s | DROP after 1.5 s | Ground test without props + log |
| R-04 | Video and RC are not lost out to 1 km at 50 m altitude | LQ > 70%, video without dropouts | Field test with recording |
| R-05 | Takeoff weight ≤ 900 g | scale | Weighing |

Rules: measurable (“fast” is not a requirement, “accelerates to 15 m/s in 3 s” is); one requirement — one verification; safety and legal requirements form a separate group (S-xx); the source of every number is stated.

### 2. Architecture
A diagram of blocks and connections: what connects to what, over which interface, where the power comes from. For a drone — three layers on one sheet:
- **Power**: battery → ESC; battery → 5 V BEC → FC, RX, GPS; 9 V BEC → VTX. Currents on the arrows.
- **Data**: RX —CRSF→ FC (UART1); GPS —UBX→ FC (UART2); FC —DShot→ ESC; FC —MSP/OSD→ VTX (UART3); FC —Blackbox→ flash.
- **Mechanics**: where everything sits, masses, center of gravity.
The architecture answers “why exactly this way” with one sentence per decision: “GPS on a mast — keeps the compass away from the power wiring (see interference).”

{{diagram:eng-architecture-layers|Архитектура примера на одном листе: питание и данные — разными линиями, у каждой стрелки данных подписаны интерфейс и порт; токи на стрелках питания подписываешь своими числами.}}

### 3. Tests
Every requirement → a test with an expected result, an actual result and a date. Tests can be:
- **Ground** (no props): ports, motor direction, failsafe, the firmware's preflight checks.
- **Simulation** (SITL for INAV/ArduPilot/PX4): missions, failsafe, geofence.
- **Bench**: thrust, current, vibration spectrum.
- **Flight**: hover, range, endurance.
Regression rule: after any configuration change you run the ground tests and the flight test the change affects. The test table is a living document.

### 4. Documentation and the changelog
A minimal engineering folder (a git repository):

```
my-drone/
  README.md          — what it is, what it's for, current state, how to run it
  requirements.md    — requirements table
  architecture.md    — power/data/mechanics diagrams (images + text)
  tests.md           — test table with results
  config/            — diff all / parameters with date and firmware version
  logs/              — key logs with a note on what's in them
  CHANGELOG.md       — date, what changed, why, how it was verified
```

The changelog is one line per change: `2026-11-08 — D-term 25→30 on roll; goal: remove bounce-back; verification: log 0042, overshoot 12%→6%`. This is what “data-driven tuning” means.

### Traceability
The thread requirement → architectural decision → test → result. If it's missing, the project can't be submitted: it's unclear what has been proven. In the course's capstone project rubrics this is a separate line item.

### What this looks like in professional practice
Accident investigation reports (the “Real Accident Case Studies” module) name the same causes again and again: there were no failure requirements, there were no failsafe tests, the configuration was changed without a record, the documentation didn't match the vehicle. The method isn't bureaucracy — it's what separates an engineered vehicle from a pile of parts.

{{diagram:traceability|Traceability: every requirement has a test, every test has a requirement; a change shows which tests to run again.}}

{{diagram:eng-method-loop|Цикл метода замкнут: решение «не доказано» возвращает к новому эксперименту, а не к ощущениям; каждый шаг оставляет файл в инженерной папке.}}

{{diagram:eng-error-budget|Бюджет ошибок R-02: весы и калибровка стенда почти ничего не весят, больше половины дисперсии — разброс экземпляров (измерен один мотор из четырёх); нижнюю границу T/W выше 2.5 поднимает только обмер всех четырёх моторов вместе с замером при 14.0 В.}}

## practice
### Step 1. Repository
Create a `my-drone` repository with files following the template above. In the README — three paragraphs: what the vehicle is, what it's for, its current state.

### Step 2. Requirements
A table of ≥ 8 requirements for your first build: 4–5 functional (endurance, T/W, range, weight), 3 safety (failsafe, zones, preflight checklist), 1–2 operational (repairability, budget). Each with a criterion and a verification method.

### Step 3. Architecture
One power and data diagram (hand-drawn, a photo is fine) with the interfaces and currents labeled.

### Step 4. Tests
A test table covering every requirement. Run the ones you already can (weighing, T/W calculation, ground checks); mark the rest as “planned.”

### Step 5. First commit and changelog entry
A commit with a message saying what was done; the first line of CHANGELOG.

### Examples of verifiable requirements
| ID | Requirement | Method | Test |
|---|---|---|---|
| REQ-01 | Hover for at least 12 minutes on a 6S 4000 mAh battery | test | T-01: hover down to 3.5 V per cell, timer |
| REQ-02 | T/W of at least 3 with all flight equipment | calculation + weighing | T-02 |
| REQ-03 | Takeoff weight no more than 900 g | weighing | T-03 |
| REQ-06 | On RC loss longer than 1 s — failsafe landing or RTH | test | T-06: switching off the radio on the bench without props, then in the field |
| REQ-07 | Flights only outside restricted zones | map check | T-07: site map in the folder |

“The vehicle must be reliable” is not a requirement: it can't be verified. “Not a single failure in 20 consecutive flights” — now that can.

### What you should end up with
- The repository contains `README.md`, `requirements.md`, `architecture.jpg` (a photo of the diagram is fine), `tests.md`, `CHANGELOG.md`.
- Every row of the test table references a requirement, and every requirement has at least one test. Completed tests have a date and result, planned ones are marked as such.
- The first line of CHANGELOG: `2026-11-09 — engineering folder created, T/W calculated (3.4), weight 860 g`. The numbers are yours.

The lab counts as completed when git contains requirements with IDs (8 or more, each measurable), an architecture diagram with labeled interfaces and currents, a “requirement → test → result” table, and an initial README and changelog.

```python
"""eng-method-101: error budget for requirement R-02 (T/W >= 2.5) with GUM-style propagation + Monte Carlo.

Measured: one of the four installed motor+prop units on the stand at 16.0 V (4.0 V/cell under load), 20 C: T1 = 750 g.
Its own deviation from the batch mean enters all four motors at once: u = 3% * sqrt(12)/4 = 2.60%.
Requirement condition (rewritten R-02): end of flight 3.5 V/cell = 14.0 V, air 35 C, take-off mass.
Model: TW = 4 * T1 * (V/V0)^a * (T0/T) / m
"""
import math
import numpy as np

T1, V0, V, a, t0, t, m = 750.0, 16.0, 14.0, 1.8, 20.0, 35.0, 860.0
rho_ratio = (273.15 + t0) / (273.15 + t)           # same pressure: rho ~ 1/T_abs
volt = (V / V0) ** a
TW = 4 * T1 * volt * rho_ratio / m
print(f"corrections: voltage (14/16)^1.8 = {volt:.4f}, air density 293.15/308.15 = {rho_ratio:.4f}")
print(f"T/W at requirement conditions = 4*{T1:.0f}*{volt:.4f}*{rho_ratio:.4f}/{m:.0f} = {TW:.3f}")

# relative standard uncertainties (k=1) of each input, and sensitivity of ln(TW)
rows = [
    ("stand calibration (des-thrust-stand U=0.61% k=2)", 0.0061 / 2, "B, normal"),
    ("motor/prop spread 3%/unit; one measured unit stands for 4", 0.03 * math.sqrt(12) / 4, "B, normal"),
    ("exponent a in [1.6, 2.0], uniform: |ln(14/16)|*0.2/sqrt3", abs(math.log(V / V0)) * 0.2 / math.sqrt(3), "B, rect"),
    ("pack voltage under load +-0.2 V, uniform: a*0.2/sqrt3/14", a * 0.2 / math.sqrt(3) / V, "B, rect"),
    ("scale +-2 g, uniform", 2 / math.sqrt(3) / m, "B, rect"),
]
tot = math.sqrt(sum(u * u for _, u, _ in rows))
print("\n contribution                                              u_rel     share of variance")
for name, u, kind in sorted(rows, key=lambda r: -r[1]):
    print(f" {name:<58s} {u*100:5.2f} %   {u*u/tot/tot*100:5.1f} %")
U = 2 * tot * TW
print(f"\ncombined u_rel = {tot*100:.2f} %, u = {tot*TW:.3f}; expanded U (k=2) = {U:.3f}")
print(f"interval: {TW-U:.2f} ... {TW+U:.2f}")
print("decision with guard band (accept if TW - U >= 2.5):", "PASS" if TW - U >= 2.5 else "NOT PROVEN")

# Monte Carlo check of the linear propagation
rng = np.random.default_rng(42)
N = 200_000
Tst = T1 * (1 + rng.normal(0, 0.0061 / 2, N))                          # one calibration for all 4 (correlated)
e = rng.normal(0, 0.03, (N, 4))                                        # e[:,0] - the measured motor (installed)
units = (4 + e.sum(1)) / (1 + e[:, 0])                                 # true sum of 4 / measured one
aa = rng.uniform(1.6, 2.0, N)
VV = V + rng.uniform(-0.2, 0.2, N)
mm = m + rng.uniform(-2, 2, N)
tw = Tst * units * (VV / V0) ** aa * rho_ratio / mm
lo, hi = np.percentile(tw, [2.5, 97.5])
print(f"\nMonte Carlo {N}: mean {tw.mean():.3f}, sd {tw.std():.3f}, 95% interval {lo:.2f} ... {hi:.2f}, P(TW<2.5) = {(tw<2.5).mean()*100:.1f} %")

# what each next experiment buys
def comb(skip):
    return math.sqrt(sum(u * u for n_, u, _ in rows if not n_.startswith(skip)))
for label, skip in [("measure all four motors on the stand", "motor/prop"), ("measure at 14.0 V directly", "exponent"),
                    ("buy a 0.1 g scale", "scale"), ("all four motors AND at 14.0 V", ("motor/prop", "exponent"))]:
    c = comb(skip)
    print(f"next experiment: {label:<38s} -> U(k=2) = {2*c*TW:.3f}, lower bound {TW-2*c*TW:.3f}")
```

```text
corrections: voltage (14/16)^1.8 = 0.7863, air density 293.15/308.15 = 0.9513
T/W at requirement conditions = 4*750*0.7863*0.9513/860 = 2.610

 contribution                                              u_rel     share of variance
 motor/prop spread 3%/unit; one measured unit stands for 4   2.60 %    59.0 %
 exponent a in [1.6, 2.0], uniform: |ln(14/16)|*0.2/sqrt3    1.54 %    20.8 %
 pack voltage under load +-0.2 V, uniform: a*0.2/sqrt3/14    1.48 %    19.3 %
 stand calibration (des-thrust-stand U=0.61% k=2)            0.30 %     0.8 %
 scale +-2 g, uniform                                        0.13 %     0.2 %

combined u_rel = 3.38 %, u = 0.088; expanded U (k=2) = 0.177
interval: 2.43 ... 2.79
decision with guard band (accept if TW - U >= 2.5): NOT PROVEN

Monte Carlo 200000: mean 2.612, sd 0.089, 95% interval 2.44 ... 2.79, P(TW<2.5) = 10.3 %
next experiment: measure all four motors on the stand   -> U(k=2) = 0.113, lower bound 2.496
next experiment: measure at 14.0 V directly             -> U(k=2) = 0.157, lower bound 2.452
next experiment: buy a 0.1 g scale                      -> U(k=2) = 0.176, lower bound 2.433
next experiment: all four motors AND at 14.0 V          -> U(k=2) = 0.079, lower bound 2.530
```

## diagnostics
- **Symptom:** the requirements sound like wishes (“reliable,” “fast”)
  - Possible cause: there's no criterion and no verification method.
  - What to do: rewrite them with a number and a test; if there's no number, it's not a requirement but a goal.
- **Symptom:** after tuning, it's unclear whether things got better or worse
  - Possible cause: there's no metric and no “before” log.
  - What to do: before a change — a log and a metric; a changelog entry with the result.
- **Symptom:** a month later it's unclear why a parameter has the value it does
  - Possible cause: a change without a record.
  - What to do: the rule “no line in CHANGELOG — no change.”
- **Symptom:** another person can't reproduce the build
  - Possible cause: the README describes a dream, not the vehicle.
  - What to do: the README states the current state, firmware versions, config in the repository.

## references
- Systems Engineering Handbook — NASA (free PDF) | https://www.nasa.gov/reference/systems-engineering-handbook/ | primary | A
- Requirements engineering (overview, further reading) — Wikipedia | https://en.wikipedia.org/wiki/Requirements_engineering | secondary | B
- Log Analysis and Tuning Workflow — ArduPilot (example of evidence-based tuning) | https://ardupilot.org/copter/docs/common-diagnosing-problems-using-logs.html | primary | A

## checklist
- The engineering folder repository is created
- ≥ 8 requirements with a criterion and a verification method
- A power and data diagram with interfaces
- The test table is linked to the requirements
- The changelog is kept from the very first change
