---
id: eng-method-101
title: "Engineering Method 101: Requirements, Architecture, Tests, Documentation"
level: L1
readingTime: 50 min
firmware: any firmware
status: published
added: 2026-11-08
tags:
  - engineering method
  - requirements
  - tests
  - documentation
  - uncertainty
related:
  - f-components-choice
  - tools-overview
  - f-safety
  - bf-tuning-method
  - bf-motor-balance
  - des-thrust-stand
next:
  - tools-overview
source: content/foundation/eng-method-101.md
source_hash: 04169a629f66
---

## summary
The difference between an assembler and an engineer is not the soldering iron but the method: an engineer knows *what* the aircraft must do (requirements), *how* it is built (architecture), *what* proves that it does it (tests), and leaves a trail that someone else can pick up the work from (documentation). This module introduces the method at the very start of the course — using your first build as the example — and sets the format of the “engineering folder”, which from now on is mandatory in every capstone project. The second half covers the “requirement → hypothesis → experiment → log → decision” loop, an error budget per the GUM with a guard-band decision rule, change management and reproducibility; in the lab a Python script checks the T/W ≥ 2.5 requirement with uncertainty and shows which experiment to do next.

## theory
### Why a beginner needs this
Without requirements, any tuning “worked” or “didn't work” by feel. Without an architecture, troubleshooting is trial and error. Without tests, you don't know what yesterday's change broke. Without documentation, in a month you are a stranger to yourself. The method costs an hour at the start and saves days later; in large projects (see the accident analyses) its absence costs aircraft and reputations.

### 1. Requirements
A requirement is a statement of what the aircraft must do that can be **verified**. Format: ID, text, criterion, verification method.

| ID | Requirement | Criterion | Verification |
|---|---|---|---|
| R-01 | Hovers with a 30 g payload for at least 15 min | ≥ 15:00 down to 3.5 V/cell | A flight on a timer, a voltage log |
| R-02 | T/W at takeoff mass ≥ 2.5 | calculated T/W ≥ 2.5; hover throttle in the log ≤ 63 % (in ArduPilot — `MOT_THST_HOVER` ≤ 0.40) | Thrust table + log |
| R-03 | On loss of link it terminates the flight in place after 1.5 s | DROP after 1.5 s (a 5" over a safe area: it falls nearby rather than flying away; for 7–10" and flights over people — AUTO-LAND or GPS Rescue, `bf-failsafe`, “What to choose”) | A ground test without props + log |
| R-04 | Video and RC are not lost up to 1 km at an altitude of 50 m | LQ > 70%, video without dropouts | A field test with recording |
| R-05 | Takeoff mass ≤ 900 g | scales | Weighing |

Why R-02 has this criterion: at T/W 2.5 the thrust fraction in hover is 1 / 2.5 = 0.40, while the throttle, because thrust is nonlinear, is 56–63 % (the 0.65 curve and the square law, the “Hover throttle” table in `f-physics`). A “throttle ≤ 40 %” criterion would require T/W 4.1–6.25 and would fail even when the requirement is met; 63 % = √(1 / 2.5) is the upper bound for T/W 2.5.

Rules: measurable (“fast” is not a requirement, “accelerates to 15 m/s in 3 s” is); one requirement — one verification; safety and legal requirements — in a separate group (S-xx); the source of every number is stated.

### 2. Architecture
A diagram of blocks and links: what is connected to what, over which interface, where the power comes from. For a drone — three layers on one sheet:
- **Power**: battery → ESC; battery → 5 V BEC → FC, RX, GPS; 9 V BEC → VTX. Currents on the arrows.
- **Data**: RX —CRSF→ FC (UART1); GPS —UBX→ FC (UART2); FC —DShot→ ESC; FC —MSP/OSD→ VTX (UART3); FC —Blackbox→ flash.
- **Mechanics**: where everything sits, masses, center of mass.
The architecture answers the question “why exactly this way” with one sentence per decision: “GPS on a mast — the compass away from the power wires (see interference)”.

{{diagram:eng-architecture-layers|The example's architecture on one sheet: power and data as different lines, each data arrow labeled with the interface and port; you label the currents on the power arrows with your own numbers.}}

### 3. Tests
Each requirement → a test with the expected result, the actual result and a date. Tests can be:
- **Ground** (without props): ports, motor direction, failsafe, the firmware's pre-flight checks.
- **Simulation** (SITL for INAV/ArduPilot/PX4): missions, failsafe, geofence.
- **Bench**: thrust, current, vibration spectrum.
- **Flight**: hover, range, time.
The regression rule: after any configuration change, the ground tests are run, plus the flight test that the change affects. The test table is a living document.

### 4. Documentation and the change log
The minimal engineering folder (a git repository):

```
my-drone/
  README.md          — what it is, what it's for, current state, how to run it
  requirements.md    — the requirements table
  architecture.md    — power/data/mechanics diagrams (images + text)
  tests.md           — the test table with results
  config/            — diff all / parameters with date and firmware version
  logs/              — key logs with a note on what is in them
  CHANGELOG.md       — date, what changed, why, how it was verified
```

The change log is one line per change: `2026-11-08 — D-term 25→30 on roll; goal: remove bounce-back; verification: log 0042, overshoot 12%→6%`. This is what “data-driven tuning” means.

### Traceability
The thread requirement → architectural decision → test → result. If it is missing, the project cannot be considered finished: it is unclear what has been proven. In the self-assessment rubric of the capstone projects this is a separate row — “Systems thinking”.

### What it looks like in professional practice
Accident investigation reports (the “Analysis of real accidents” module) name the same causes time after time: there were no requirements for failures, no failsafe tests, the configuration was changed without a record, the documentation did not match the aircraft. The method is not bureaucracy; it is what separates an engineered aircraft from a pile of parts.

{{diagram:traceability|Traceability: every requirement has a test, every test has a requirement; a change shows which tests to run again.}}

### 5. The method loop: requirement → hypothesis → experiment → log → decision
Requirements say *what* must be. The method loop answers *how* to find out whether it is met, and what to do if it isn't. There are five steps, and each leaves a record in the folder.

1. **A requirement** with a criterion and **conditions**. “T/W ≥ 2.5” without conditions cannot be verified: motor thrust depends on voltage and air density, and on a full battery at +10 °C the requirement will be met, while at the end of a flight at +35 °C it won't. The working wording of R-02: “T/W ≥ 2.5 at takeoff mass, 3.5 V per cell under load, air up to +35 °C”.
2. **A hypothesis** is a statement about a cause or an effect. It predicts a number and can turn out to be false. Example: “the hover throttle is 48 % instead of the calculated 42 % because of 5×4.3 props instead of 5×4.8; with 5×4.8 props the throttle will return to 42 ± 2 %”. “I'll try other props” does not count as a hypothesis: it predicts nothing, and there is nothing to refute it with.
3. **An experiment** is a plan written down *before* it is run. It contains: what changes (exactly one thing), what is held constant (battery, mass, firmware, weather window), a metric with a precise definition, the number of repetitions and a stop condition (for example, “land at 3.5 V/cell or vibration above the threshold”).
4. **The log** — raw data is never edited. A flight or bench log gets a number, and a note on the conditions sits next to it. The processing is done by a script from the repository, not by editing cells in a spreadsheet.
5. **The decision** is one of three: accept, reject, or “not proven, experiment X is needed”. The decision with a number and an uncertainty is written to the CHANGELOG, and the next loop starts from it.

{{diagram:eng-method-loop|The method loop is closed: a “not proven” decision leads back to a new experiment, not to feelings; each step leaves a file in the engineering folder.}}

This loop already works in the course's modules, just under other names. In `bf-tuning-method` the hypothesis “`d_roll`/`d_pitch` 40/46 → 46/52 reduces prop wash by at least 10 %” is tested with flights in ABBA order, and the decision is made by the ratio of the effect to the standard error: a single pair of flights decides nothing there. In `bf-motor-balance` one motor imbalance is explained by three hypotheses (center of gravity, motor, prop), and a swap test distinguishes them: if the imbalance moved together with the motor, the motor is to blame. In `des-thrust-stand` the rated thrust is a hypothesis, and the stand tests it with an uncertainty budget of 0.61 % (k = 2).

{{lesson:bf-tuning-method|A full walkthrough of an A/B experiment: ABBA order, log metrics and a permutation test on synthetic data with a known effect.}}

{{lesson:des-thrust-stand|Where the 0.61 % thrust uncertainty comes from: calibration, drift, creep and a budget by contribution.}}

### 6. Uncertainty and the error budget
A number without an uncertainty cannot be honestly compared with a requirement. The language for this is set by the GUM (JCGM 100:2008):
- **Standard uncertainty u** — uncertainty expressed as one standard deviation.
- **Type A** — from repeated measurements: u = s/√n, where s is the spread and n the number of measurements.
- **Type B** — from other information. For a “±a” tolerance with no information about the shape of the distribution, a uniform one is assumed, and then u = a/√3; kitchen scales with ±2 g give u = 1.15 g. If a calibration certificate states U at k = 2, then u = U/2.
- **Combination.** For independent inputs u_c² = Σ(c_i·u_i)², where c_i = ∂f/∂x_i is the sensitivity coefficient. For products, quotients and powers it is more convenient to use relative quantities: if y = x₁·x₂ᵃ/x₃, then (u_y/y)² = (u₁/x₁)² + (a·u₂/x₂)² + (u₃/x₃)². If the exponent a itself has an uncertainty, its sensitivity is ∂ln y/∂a = ln x₂.
- **Correlation.** Errors with a common source add linearly, not in quadrature. If all four motors were measured on the same stand, its calibration error shifts all four thrusts equally, and the sum keeps the same 0.30 %, not 0.30/√4. The unit-to-unit spread depends on what was measured. If the thrust of each of the four motors is known only as the batch mean, their independent deviations of 3 % each give 3/√4 = 1.5 % on the sum. If, however, one motor was measured on the stand and its number multiplied by four, that motor's deviation from the batch mean enters all four equally — it is the same common source. For a motor that is one of the four installed, the sum differs from 4·T₁ by e₂ + e₃ + e₄ − 3e₁, and u = 3 %·√12/4 = 2.6 %; for a spare motor not mounted on the frame — 3 %·√20/4 = 3.35 %.
- **Expanded uncertainty** U = k·u_c. At k = 2 this is about 95 % for a normal distribution.

**An error budget** is a table of contributions sorted by their share of the variance u_i²/u_c². The main point of a budget is choosing the next experiment: it makes sense to refine a large contribution. A contribution with a 1 % share can be reduced all the way to zero, and the total will barely change. In the lab for R-02 the scales give 0.2 % of the variance, while the main contribution — 59 % — is the unit-to-unit spread: one motor out of four was measured. Next come the thrust's voltage exponent (21 %) and the voltage under load (19 %). Buying 0.1 g scales gives nothing. Measuring all four motors removes the top row and raises the lower bound almost to the limit, and together with a bench measurement right at 14.0 V it moves R-02 from “not proven” to “met”.

{{diagram:eng-error-budget|The R-02 error budget: the scales and the stand calibration weigh almost nothing, more than half of the variance is the unit-to-unit spread (one motor out of four measured); only measuring all four motors together with a measurement at 14.0 V raises the lower bound of T/W above 2.5.}}

**The decision rule** with a guard band w = U. JCGM 106:2012 describes binary rules: guarded acceptance shifts the acceptance limit inside the tolerance by w. The third outcome, “not proven”, is a non-binary rule in the spirit of ISO 14253-1 and ILAC-G8. Measured y ± U, requirement limit L (a requirement of the form y ≥ L):
- y − U ≥ L — **met**;
- y + U < L — **not met**;
- otherwise — **not proven**: an experiment that reduces U, or margin in the design, is needed.

In the lab T/W = 2.61 ± 0.18 (k = 2), interval 2.43…2.79. The mean is 4 % above the limit, but the conclusion is “not proven”: the Monte Carlo method gives a 10 % probability that T/W is actually below 2.5. Without a budget, the log would have said “T/W 2.61, requirement met”.

### 7. Change management
**A baseline** is the state of the aircraft that has passed the test table: hardware, firmware version, config. In git it gets a tag, for example `v1.0`. Any deviation from the baseline is filed as a change with five fields: *what* was changed, *why* (the hypothesis), *how it was verified* (test ID, log number), *the result* (the number before and after), *how to roll it back*. The CHANGELOG line from section 4 is a compressed record of exactly these fields. Rules:
- **One change per experiment.** When you changed the D-term and the props on the same field trip, the improvement cannot be attributed to either.
- **A freeze before the field trip.** The config in the field is exactly the one in the repository. A quick edit “on your knee” in the field is a change too: a line in the log the same day, otherwise the next log has nothing to be compared with.
- **The scope of regression by change class.** A parameter inside one function (D-term, rates) — the ground tests plus the test of that function. A new firmware version, replacing the powertrain or a mass increase of more than 5 % — the whole test table again (course guideline). For firmware this is also mandatory because parameters get renamed between versions.

The automation of this control — config invariants and a CI that turns red on a broken failsafe — is provided by `eng-ci-configs`.

### 8. Reproducibility
**Computational reproducibility** means that someone else (or you in a month) gets exactly the same number from the repository. Do not confuse it with the reproducibility of measurements per VIM 2.25 — the spread of results when conditions and operators change. For computational reproducibility you pin down:
- **raw data** — logs without edits, with a checksum (`sha256sum logs/0042.bbl` → a line in `logs/README.md`);
- **processing** — the script in the repository, its commit and the input file names; for random methods — the generator seed (in the lab `seed 42`: the same input gives the same numbers on every run);
- **firmware and config** — the version and build hash (in Betaflight — the version line in the header of `diff all`, in ArduPilot — the message with the version and git hash at the start of the log), the config file itself;
- **conditions** — temperature, wind, the battery's ID and cycle count, the mass on the day of the test.

Do not confuse two concepts. **Repeatability**: a new flight gives a different number, but within the uncertainty — that is normal, and that is what the budget is calculated for. **Reproducibility of processing** — rerunning the script on the same logs must give exactly the same number. If it doesn't, the error is in the process, not in the aircraft.

### Reference table: uncertainty and decision

| What | Formula / action | Example from the module |
|---|---|---|
| Type A (repetitions) | u = s/√n | 5 flights, s = 0.4 % → u = 0.18 % |
| Type B, tolerance ±a | u = a/√3 (uniform) | scales ±2 g → 1.15 g |
| Certificate U (k = 2) | u = U/2 | stand 0.61 % → 0.30 % |
| Product/quotient | (u_y/y)² = Σ(a_i·u_i/x_i)² | T/W = 4·T·(V/V₀)ᵃ·(ρ/ρ₀)/m |
| Uncertainty of the exponent a | u_rel = ln(x₀/x)·u_a for x < x₀ | ln(16/14)·0.2/√3 = 1.54 % |
| Common source (correlation) | add linearly | stand calibration on 4 motors: 0.30 % |
| Units: batch mean known | σ/√N for the sum | 3 % per motor → 1.5 % for four |
| Units: one measured × 4 | σ·√12/4 (a motor from the frame), σ·√20/4 (a spare) | 3 % → 2.6 % / 3.35 % |
| Expanded | U = 2·u_c (≈ 95 %) | 2 × 0.088 = 0.177 |
| Decision rule | y − U ≥ L — met; y + U < L — not met; otherwise “not proven” | 2.61 − 0.18 = 2.43 < 2.5 → not proven |
| Checking the linear model | Monte Carlo, 2·10⁵ samples, fixed seed | 95 %: 2.44…2.79, P(T/W < 2.5) = 10.3 % |
| Lab tools | Python 3.13, NumPy 2.5 | `tw_budget.py`, step 6 |

### Place in the system

- **Receives:** the mission in numbers — payload, time, range, mass (`f-components-choice`); the rules from which the S-xx group of requirements is built (`f-safety`, `f-regulations`).
- **Provides:** requirements with IDs, the three-layer diagram and the test table — every capstone project inherits them; the full version of the loop — `eng-systems`, the `config/` folder under version control — `eng-ci-configs`.
- **If you get it wrong here:** there is no loss-of-link requirement and no test for it → the failsafe triggers for the first time in the air and does something nobody chose (`bf-failsafe`). The configuration was changed without a line in the log → after an accident it is impossible to reconstruct which change caused it: the analysis ends with the words “not established” (`ops-case-studies`).

## practice
### Step 1. Repository
Create a `my-drone` repository with files following the template above. In the README — three paragraphs: what the aircraft is, what it is for, its current state.

### Step 2. Requirements
A table of ≥ 8 requirements for your first build: 4–5 functional (time, T/W, range, mass), 3 safety (failsafe, zones, pre-flight checklist), 1–2 operational (repairability, budget). Each one — with a criterion and a verification method.

### Step 3. Architecture
One power and data diagram (hand-drawn, a photo is fine) with the interfaces and currents labeled.

### Step 4. Tests
A test table for every requirement. Do the ones that can already be done (weighing, the T/W calculation, ground checks); the rest — marked “planned”.

### Step 5. The first commit and a log entry
A commit with a message saying what was done; the first line of the CHANGELOG.

### Examples of requirements that can be verified
| ID | Requirement | Method | Test |
|---|---|---|---|
| REQ-01 | Hover for no less than 12 minutes on a 6S 4000 mAh battery | test | T-01: hover down to 3.5 V per cell, a timer |
| REQ-02 | T/W of no less than 3 with all flight equipment | calculation + weighing | T-02 |
| REQ-03 | Takeoff mass no more than 900 g | weighing | T-03 |
| REQ-06 | On RC loss longer than 1 s — a failsafe landing or RTH | test | T-06: switching off the radio on the bench without props, then in the field |
| REQ-07 | Flights only outside restricted zones | map check | T-07: the site map in the folder |

“The aircraft must be reliable” is not a requirement: it cannot be verified. “Not a single failure over 20 flights in a row” already can be.

### Step 6. The error budget for R-02
Requirement R-02 is rewritten with conditions (section 5 of the theory): T/W ≥ 2.5 at 3.5 V/cell under load (4S → 14.0 V) and air up to +35 °C. The input data of the worked example: one motor with a prop was measured on the stand at 16.0 V (4.0 V/cell under load) and +20 °C, thrust T₁ = 750 g; takeoff mass 860 g on scales with ±2 g. Converting to the requirement's conditions takes two corrections. Air density at the same pressure is inversely proportional to the absolute temperature: 293.15/308.15 = 0.951. The correction is conservative: in thinner air the prop unloads, RPM rises, and thrust drops less than the density; pressure (site elevation) and humidity are not taken into account here. Thrust at full throttle grows with voltage roughly as Vᵃ: ideally a = 2 (RPM ∝ V, thrust ∝ n²), less under load; we take a = 1.8 within 1.6–2.0 (course guideline — refined with a stand at two voltages). The unit-to-unit spread of motor + prop is 3 % per unit relative to the batch mean (course guideline). One of the four installed motors was measured, so its deviation enters all four: u = 3 %·√12/4 = 2.60 % (theory, section 6). The voltage under load at the end of the flight is known to within ±0.2 V (uniform distribution; course guideline — the accuracy of the FC's voltmeter and the spread of the sag): u = a·0.2/√3/14 = 1.48 %. The stand's uncertainty is 0.61 % at k = 2 from `des-thrust-stand`.

The script calculates the corrections, the budget by contribution, the expanded uncertainty, the decision by the guard-band rule, checks the linear model with the Monte Carlo method and shows what each next experiment would give. Run it: `python3 tw_budget.py` (Python 3.13, NumPy 2.5).

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

Output (run as is, unedited):

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

How to read this. The mean of 2.610 is 4 % above the limit, while the lower bound of 2.43 is below it: the decision is “not proven”. Monte Carlo matched the linear model to the hundredth (95 %: 2.44…2.79 versus 2.43…2.79), so linear combination is sufficient here. More than half of the variance comes from the unit-to-unit spread. Measuring all four motors removes it and raises the lower bound to 2.496 — almost, but not quite to the limit. A measurement at 14.0 V on its own gives 2.452, precise scales — 2.433. The first two experiments together give 2.530, and that is already “met”. If T₁ had been the batch mean over many measurements, the spread would contribute only 1.5 % (σ/√4) — check it by changing the line in `rows`.

### Step 7. Decision and a log entry
Write down the decision in the format of section 7: “2026-11-26 — R-02: T/W = 2.61 ± 0.18 (k = 2) at 14.0 V and +35 °C → not proven; hypothesis: after measuring the four motors and a stand run at 14.0 V the lower bound is ≥ 2.5; verification: stand, logs 0051–0055; no rollback needed (config not changed)”. Then plug in your own data: the thrust from a stand or from the manufacturer's table, your mass, the end-of-flight voltage. If the thrust is taken from the datasheet rather than from a stand, replace the “stand calibration” row with the discrepancy between the datasheet and your combination. According to `des-thrust-stand`, a combination is usually 5–15 % weaker than the datasheet. Such a one-sided discrepancy is a known systematic effect: apply a −10 % correction to the thrust and an uncertainty of ±5 % (u = 5/√3 ≈ 2.9 %). If the sign of the discrepancy is unknown, take a half-width of 15 % (u = 15/√3 ≈ 8.7 %; course guideline). See how the decision changed.

### What you should end up with
- The repository contains `README.md`, `requirements.md`, `architecture.jpg` (a photo of the diagram will do), `tests.md`, `CHANGELOG.md`.
- Every row of the test table refers to a requirement, every requirement has at least one test. Completed tests — with a date and result, planned ones — marked as such.
- The first line of the CHANGELOG: `2026-11-09 — engineering folder created, T/W calculated (3.4), mass 860 g`. The numbers are yours.
- In `tests.md`, R-02 has T/W ± U (k = 2), the conditions and a decision in one of three words: “met”, “not met”, “not proven”.

Self-check: the lab is done when git holds requirements with IDs (8 or more), and each passes the “number, unit, verification method” check — like REQ-01…REQ-07 in the examples above; a line like “must be reliable” does not pass it and is rewritten; on the architecture diagram every arrow is labeled with its interface, and the power arrows with their current; the “requirement → test → result” table has no requirement without a test and no test without a requirement, completed tests have a date and a result, the rest are marked “planned”; a three-paragraph README and a change log with a first line in the format “date — what was done — numbers” are in place; the step 6 script on the example data outputs T/W = 2.610, u_c = 3.38 %, U = 0.177, interval 2.43…2.79, “NOT PROVEN” and P(T/W < 2.5) = 10.3 % (seed 42, a match to the last digit is the reproducibility check); your own R-02 has its conditions stated (voltage, temperature), a budget of three or more contributions sorted by share of variance, and a decision by the guard-band rule.

**Reference for self-check.** On the example data the correct result is 2.61 ± 0.18 and “not proven”; the budget is topped by the unit-to-unit spread (59 %), followed by the exponent (21 %) and the voltage (19 %), the scales give 0.2 %. Typical errors: (1) T/W = 3.49 and “met” — the voltage and temperature corrections were forgotten, i.e. the thrust at 16 V and +20 °C is compared with a requirement for 14 V and +35 °C; (2) U ≈ 0.09 instead of 0.18 — the k = 2 factor was forgotten; U ≈ 0.14 — the unit-to-unit spread was divided by √4, as if the thrust of each motor were known independently, although only one motor was measured; U ≈ 0.02 — only the stand calibration was left in the budget; (3) “met, because 2.61 > 2.5” — the mean is compared without a guard band. If the numbers differ on a rerun — the script or the seed was changed, and the result is not reproducible.

## diagnostics
- **Symptom:** the requirements sound like wishes (“reliable”, “fast”)
  - Possible cause: no criterion and no verification method.
  - What to do: rewrite with a number and a test; if there is no number — it is a goal, not a requirement.
- **Symptom:** after tuning it is unclear whether things got better or worse
  - Possible cause: no metric and no “before” log.
  - What to do: before a change — a log and a metric; an entry in the change log with the result.
- **Symptom:** a month later it is unclear why a parameter has this value
  - Possible cause: a change without a record.
  - What to do: the rule “no line in the CHANGELOG — no change”.
- **Symptom:** someone else cannot reproduce the build
  - Possible cause: the README describes a dream, not the aircraft.
  - What to do: the README — the current state, firmware versions, the config in the repository.
- **Symptom:** the requirement is met on the stand but not in the field (T/W, flight time)
  - Possible cause: the requirement has no conditions; the stand measured on a full battery and in cool air.
  - What to do: add the voltage and temperature to the requirement, recalculate with the corrections (step 6) and compare by the guard-band rule.
- **Symptom:** reprocessing the same log gives a different number
  - Possible cause: processing by hand in a spreadsheet, a modified script, or a random method without a seed.
  - What to do: the script in the repository, its commit in the record, a fixed seed, `sha256sum` of the logs; manual cell edits are forbidden.
- **Symptom:** after a field trip “it got better”, but it is unclear why
  - Possible cause: several things were changed during one trip.
  - What to do: one change per experiment; roll back to the baseline (a git tag) and introduce the changes one at a time.
- **Symptom:** the most expensive instrument was upgraded, but the total uncertainty did not change
  - Possible cause: a small contribution of the budget was improved.
  - What to do: sort the budget by share of variance and reduce the top row (in the example the scales are 0.2 %).

## references
- Systems Engineering Handbook — NASA (free PDF) | https://www.nasa.gov/reference/systems-engineering-handbook/ | primary | A
- Requirements engineering (overview, further reading) — Wikipedia | https://en.wikipedia.org/wiki/Requirements_engineering | secondary | B
- JCGM 100:2008 — Evaluation of measurement data: Guide to the expression of uncertainty in measurement (GUM) | https://www.bipm.org/documents/20126/2071204/JCGM_100_2008_E.pdf | primary | A
- JCGM 106:2012 — The role of measurement uncertainty in conformity assessment (guard bands) | https://www.bipm.org/documents/20126/2071204/JCGM_106_2012_E.pdf | primary | A
- NIST Technical Note 1297 — Guidelines for evaluating and expressing the uncertainty of NIST measurement results | https://www.nist.gov/pml/nist-technical-note-1297 | primary | A
- Log Analysis and Tuning Workflow — ArduPilot (example of evidence-based tuning) | https://ardupilot.org/copter/docs/common-diagnosing-problems-using-logs.html | primary | A

## checklist
- The engineering folder repository is created
- ≥ 8 requirements with a criterion and a verification method
- A power and data diagram with interfaces
- The test table is linked to the requirements
- The change log is kept from the first change
- Requirements have their conditions written down, results have U (k = 2) and a decision by the guard-band rule
- The error budget is sorted by share of variance, the next experiment is chosen by the top row
- Processing is reproducible: the script and seed are in the repository, logs have checksums
