---
id: ops-maintenance
title: "Maintenance and Reliability: Logs, Battery Life, Schedule, MTBF"
level: L2
readingTime: 30 min
firmware: any
status: published
tags:
  - maintenance
  - reliability
  - logbook
  - MTBF
related:
  - ops-field
  - ops-case-studies
  - el-battery-packs
  - ap-logs
  - el-redundancy
next:
  - diag-troubleshooting
source: content/foundation/ops-maintenance.md
source_hash: 45c69b8629e5
---

## summary
A hobbyist repairs the aircraft after a crash; an operator doesn't let it get to a crash. The difference is the logbook and the schedule: every flight is recorded, every battery has a history of cell resistance, props are replaced by a rule rather than “when they crack”, and trends of vibration and motor balance from the logs warn about wear before it becomes a failure. The module gives you the aircraft and battery logbooks, battery retirement criteria, an inspection schedule by flight hours, log analysis as a maintenance tool, and the basics of reliability — failure rate, MTBF, series and redundant systems — with a calculation that shows why six motors instead of four.

## theory
### Logbooks
- **Aircraft logbook**: date, pilot, site, mission, flight time (min), battery, remarks, a link to the log; separately — repairs and replacements (what, why, serial numbers). The total flight time of the aircraft and its components (motors, ESCs, props) is the basis of the schedule.
- **Battery logbook**: battery number (a sticker), purchase date, cycles, voltage before/after the flight, the internal resistance of the cells by date, damage. A number on the battery is mandatory — otherwise the “bad battery” can never be pinned down.
- **Format**: a table or CSV in git next to the aircraft's parameters (the “Configs in CI” module) — history and search for free.

### Battery life
- **Internal resistance (IR)** of each cell is the main indicator. It is measured with a charger that has an IR function (compare with the same instrument at the same temperature). Growing IR — less output under load, more heating.
- **Retirement criteria** (guidelines, check with the manufacturer): a cell's IR has grown about 1.5–2 times from new; cell imbalance after charging and resting of more than 0.05 V (from 0.03 V — watch it; the script below flags from 0.04 V); swelling; capacity below ~80 % of the rating; mechanical damage after a crash. A swollen or damaged battery — do not fly it and do not charge it, dispose of it by the procedure from the “Power” module (discharge to ~0 V through a load outdoors, insulate the terminals, collection point).
- **Storage**: 3.80–3.90 V per cell (storage; Gens Ace datasheet, `f-power`), somewhere cool, in a fireproof bag or box; do not keep them fully charged for longer than a day (course guideline).
- **Operating regime**: do not discharge below the landing threshold (the “Power” module), do not charge them hot or cold, balance charging.

### Inspection schedule
| When | What | Criterion |
|---|---|---|
| Before every flight | props, prop and motor mounting, battery and connector, antennas, straps | cracks and chips, play, a hot connector |
| After every flight | motor and ESC temperature by touch, props, frame, logbook entry | one motor noticeably hotter than the others — investigate |
| After any impact | props (all of them, not just the broken one), frame, motors for play and binding, calibration check | a prop after a strike — replace it |
| Every ~10–20 h | motor bearings (spin by hand — rustling, play), frame screws, soldering and connectors, flight controller dampers | rustling and play — replace the bearings or the motor |
| Every ~50 h or per season | full teardown: wiring, insulation, power connectors, firmware update as planned | traces of heat, chafing |

The intervals are starting values; your own are determined from the logbook: if bearings die in 30 h, the schedule is 20.

{{diagram:maint-inspection-timeline|A schedule by flight hours: checks before and after every flight and after an impact always happen, the scheduled ones go by hours, and the bearing interval is adjusted from the logbook (they die in 30 h — inspection every 20 h).}}

### Post-crash checklist
The “after any impact” row of the schedule in expanded form. It is gone through in order, with an entry in the aircraft logbook; until the last row is done, the aircraft does not fly.

| Component | What to check | “Do not fly” criterion |
|---|---|---|
| Battery — first | disconnect it; dents, cuts in the wrap, swelling, heat, smell; cell voltages immediately and after 30 min of rest | any damage to the wrap, swelling, heat; cell spread of more than 0.05 V; a cell below 3.0 V |
| Battery — quarantine | apart from the others, on a non-flammable surface, outdoors or in a fireproof box; watch it for at least 15 minutes, charge it only after inspection and under supervision; an entry in the battery logbook marked “impact” | IR growth relative to the logbook, imbalance after the first charge, swelling during charging — retire it |
| Frame | plates and standoffs for cracks and carbon delamination (against the light and by bending), all frame screws for tightness | a crack, delamination, a stripped thread |
| Arms | each arm for bending and twisting by hand, the fit in the plates; compare the motor-to-motor diagonals with a tape measure | arm play, a crack at the base, diagonals differ by millimeters |
| Motors | spin by hand: rustling and sticking — bearings; bell play up-down and sideways; the bell for dents and runout; the shaft; the shaft circlip or screw; magnets for chips; mounting screws — do they reach the winding | rustling, sticking, bell runout, a visible gap at the magnets, shaft play |
| Props | replace all of them, not just the broken one; check the nuts and the fit | a prop after a strike does not go back into the air |
| Wiring | phase wires at the base of the arm (chafing against the carbon), power wires, insulation, the capacitor on the power bus and its leads | a bare conductor, a break at the solder joint, a torn-off capacitor lead |
| Connectors | XT60/XT30: cracks in the housing, recessed or blackened contacts; the U.FL of the receiver and video antennas; the camera ribbon cable; stack and GPS connectors | the connector heats up, wobbles, a contact is recessed; the U.FL comes off without effort |
| Flight controller and gyro | stack mounting: the dampers are intact and identical, the board does not touch the frame or wires, the screws are not overtightened; nothing presses on the board | a torn damper, the board touches the frame, a taut harness |
| Antennas and GPS | antennas intact, the GPS module and compass mounting, their orientation unchanged | a broken antenna element, a shifted compass |

**Recheck — props removed.** The first power-up after a repair — through a smoke stopper (the “Troubleshooting tree” module). Then step by step:
1. Configurator or GCS: on a level table the horizon reads zero, the model on the screen repeats the tilts; if it is off — accelerometer calibration, and the compass — if the module or the wiring near it was touched.
2. Receiver: the channels move, the failsafe triggers when the radio is switched off.
3. The motors one at a time on the Motors tab (or the motor test in the GCS): the sound is smooth, the same for all four, without crunching; DShot errors and eRPM, if there is telemetry, without dropouts.
4. All motors at low throttle for 20–30 seconds: gyro noise no higher than in the logs before the crash; the motors and ESCs are equally warm.
5. Only after that — new props and a test hover of 30–60 seconds at 1–2 m near you, with log recording: compare vibration and motor balance with the trend before the crash.

The aircraft logbook entry: what happened, what was replaced (serial numbers), the result of the test hover, the number of the battery sent to quarantine.

{{diagram:post-crash-recheck-flow|After a crash the order matters: the battery first and into quarantine, then mechanics and wiring, then the check without props — and only then new props and a test hover.}}

### Logs as a maintenance tool
A log is not only “why it crashed” but also “what is wearing out”:
- **Vibration** (`VIBE` in ArduPilot, the gyro in Betaflight Blackbox): growth from flight to flight with the same props — bearings, a prop, loosened mounting.
- **Motor balance** (`RCOU` / `motor[n]`): one motor consistently higher than the others in hover — it is weaker (wear, prop) or the aircraft is unbalanced.
- **Compass** (`MAG`): growth of current-induced interference after a wiring repair.
- **Battery** (`BAT`): the voltage sag at the same current grows — the battery's resistance is growing.

The trend matters more than a single value: one point is noise, five points are wear.

### Reliability: numbers instead of feelings
- **Failure rate** λ — failures per hour (roughly constant during normal operation). **MTBF** = 1/λ — mean time between failures. An MTBF of 1000 h does not mean “1000 h without failures”: the probability of running t hours without failure is R(t) = e^(−λt), which for 1000 h is only 37 %.
- **The “bathtub” curve**: at first — early failures (defects, cold solder joints) → normal operation → wear-out. Hence acceptance of new aircraft (a ground test, the first flights low and close) and replacement by service life before the wear-out zone.
- **A series system** — a failure of any component = a failure of the system: R = R₁·R₂·…·Rₙ. For its motors, a quadcopter is a series system of four: R = r⁴.
- **Redundancy** — the system works as long as at least one of the duplicates is alive: R = 1 − (1 − r)². A hexacopter able to fly home on five motors is “5 out of 6 needed”: R = r⁶ + 6·r⁵·(1 − r). But the ability to survive a motor failure depends on the frame, the thrust-to-weight ratio and the firmware — it is tested, not assumed (the “Redundancy” module).
- **Example**: motor λ = 1/1000 h (illustrative). Over 100 h of flight time without replacement: quad R = e^(−0.4) ≈ 0.67, a hexa that survives one failure ≈ 0.90. The same calculation shows why replacing motors by service life raises reliability more than it seems.

{{diagram:chart-reliability|The probability of avoiding a loss due to a motor failure versus flight time: a quad (all four needed) versus a hexa that survives one failure.}}

### A one-page FMEA
For each component: how it can fail → what the pilot will see → what the aircraft will do → how to detect it in advance → what we do. Five rows for the motor, ESC, battery, receiver and GNSS give you a plan of the inspections and checks that really matter.

### Place in the system

- **Receives:** the sortie log: flight time, battery number, voltages (`ops-field`); trends of vibration, motor balance and sag from the logs (`ap-logs`, `bf-blackbox`); battery charging and disposal rules (`f-power`).
- **Provides:** clearance of the aircraft for flight after an inspection or a crash; the decision to retire a battery and to replace bearings and props; the failure rate — to the redundancy calculation (`el-redundancy`); FMEA rows (`eng-systems`).
- **If you get it wrong here:** a prop was left in service after a strike → imbalance, gyro vibration grows from flight to flight (`f-frame-mech`). After an impact the compass position was not checked → interference and a wrong heading, “toilet bowling” in Loiter (`el-emi`, `nav-resilience`). The battery did not go through quarantine after an impact → a fire during charging (`f-power`).

## practice
### Step 1. Logbooks
Start an aircraft logbook and a battery logbook (CSV or a table): the fields from the theory. Number the batteries with stickers. Enter the recent flights that can be reconstructed from the logs.

### Step 2. Batteries
For each battery — the IR of each cell (a charger with an IR function, at room temperature), the cell voltages after charging and 30 min of rest. Mark the batteries on the verge of retirement by the criteria. A script for the logbook:
```python
import csv
LIMIT_IR_RATIO, LIMIT_DV = 1.5, 0.04
for row in csv.DictReader(open("batteries.csv")):
    ir = [float(x) for x in row["ir_mohm"].split("/")]          # "3.1/3.0/3.4/3.2"
    ir_new = [float(x) for x in row["ir_new_mohm"].split("/")]
    v = [float(x) for x in row["v_rest"].split("/")]
    worst = max(a / b for a, b in zip(ir, ir_new))
    flags = []
    if worst >= LIMIT_IR_RATIO: flags.append(f"IR x{worst:.1f}")
    if max(v) - min(v) > LIMIT_DV: flags.append(f"imbalance {max(v) - min(v):.2f} V")
    print(row["id"], "OK" if not flags else "CHECK: " + ", ".join(flags))
```

### Step 3. A trend from the logs
Take 5+ logs of one aircraft over a period (ArduPilot `.bin` or Blackbox). For each: the mean vibration in hover and the mean output of each motor in hover. Plot the trend (pandas/matplotlib, the “Data and Python” module). Is there a motor that is consistently higher? Is vibration growing?

### Step 4. Schedule and FMEA
An inspection table for your aircraft with intervals by flight hours and an FMEA for 5 components. Calculate R for your frame over a season's flight time with a motor λ of 1/1000 and 1/3000 h.

Self-check: the lab is done when the aircraft and battery logbooks are started with the fields from the theory and the batteries are numbered; for each battery the step 2 script printed `OK` or `CHECK: …`, and for each flagged one a decision by the retirement criteria is written down (a cell's IR has grown 1.5–2 times from new, imbalance after charging and resting of more than ~0.03–0.05 V, swelling); the trend of vibration and the mean output of each motor is plotted from 5+ logs, and a conclusion is written under the plot — whether there is a motor consistently higher than the others and whether vibration is growing (one point is noise, five are wear); the schedule is drawn up, and in the FMEA for 5 components every row has all five columns filled in; before calculating your own frame, the reliability formula was checked on the example from the theory — λ = 1/1000 h, 100 h of flight time: quad R = e^(−0.4) ≈ 0.67, a hexa that survives one failure ≈ 0.90 — and for λ = 1/3000 h the result came out higher than for 1/1000.

## diagnostics
- **Symptom:** after a crash the aircraft “seems intact”, but vibration has grown
  - Possible cause: a bent motor shaft or bell, a cracked arm, a damaged flight controller damper, a prop with a microcrack.
  - In the log/on the instrument: gyro noise and `VIBE` are higher than in the logs before the crash; one motor is louder in the test without props.
  - What to do: go through the whole post-crash checklist, replace all the props, spin each motor by hand and in the test without props.
- **Symptom:** one battery “dies” faster than the others
  - Possible cause: IR growth in one cell, imbalance.
  - What to do: per-cell IR, the logbook; if it exceeds the criteria — retire it.
- **Symptom:** vibration grows from flight to flight
  - Possible cause: bearing wear, a damaged prop, loosened mounting.
  - What to do: spin the motors by hand, replace the props, check the mounting, compare with the replacement log.
- **Symptom:** one motor is hotter than the others after a flight
  - Possible cause: motor wear, a heavy/damaged prop, an unbalanced aircraft.
  - What to do: the motor outputs in the log, replace the prop, check the CG, then the motor.
- **Symptom:** a “sudden” failure without warnings
  - Possible cause: no logbook and no trends — there were warnings, but nobody recorded them.
  - What to do: a logbook, trends from the logs, replacement by service life.
- **Symptom:** strange compass behavior after a repair
  - Possible cause: the power wires are routed differently, current-induced interference.
  - What to do: compare `MAG` against current before and after, recalibrate, restore the wire routing.

## references
- ArduPilot — Measuring vibration | https://ardupilot.org/copter/docs/common-measuring-vibration.html | primary | A
- ArduPilot — Battery monitor and failsafe | https://ardupilot.org/copter/docs/common-powermodule-landingpage.html | primary | A
- NIST/SEMATECH e-Handbook — Reliability (exponential model, MTBF) | https://www.itl.nist.gov/div898/handbook/apr/section1/apr1.htm | primary | A
- Battery University — How to prolong lithium-based batteries | https://batteryuniversity.com/article/bu-808-how-to-prolong-lithium-based-batteries | secondary | B
- Team Associated — LiPo Safety Instructions and Warnings (damaged battery: observe for at least 15 minutes; accessed 2026-11-17) | https://img2.associatedelectrics.com/pdf/cars_and_trucks/shared/LiPo-Safety-Instructions-and-Warnings.pdf | primary | B
- Gens Ace — LiPo safety manual (do not use damaged and swollen cells, minimum 3.0 V; accessed 2026-11-17) | https://www.freeflysystems.com/wp-content/uploads/2021/11/Gensace_safety_manual.pdf | primary | B

## checklist
- I keep an aircraft logbook and a battery logbook with numbers
- I measure cell IR and retire batteries by the criteria
- I inspect the aircraft per the schedule and replace props after a strike
- After a crash I go through the whole checklist: battery into quarantine, motors and frame inspected, check without props
- I watch the trends of vibration and motor balance in the logs
- I calculate the reliability of a series and a redundant system
- I draw up an FMEA for the main components
