---
id: ops-maintenance
title: "Maintenance and reliability: logs, battery service life, inspection schedule, MTBF"
level: L2
readingTime: 30 min
firmware: any
status: published
tags:
  - maintenance
  - reliability
  - log
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
source_hash: cf0f12f6dca4
---

## summary
A hobbyist fixes the aircraft after a crash; an operator never lets it get to a crash. The difference is the logbook and the inspection schedule: every flight is recorded, every battery has a history of its cell resistance, props are replaced by a rule rather than “when they crack”, and trends in vibration and motor balance from the logs warn you about wear before it turns into a failure. This module covers aircraft and battery logbooks, battery retirement criteria, an inspection schedule based on flight hours, log analysis as a maintenance tool, and reliability basics — failure rate, MTBF, series and redundant systems — with a calculation that shows why six motors instead of four.

## theory
### Logbooks
- **Aircraft logbook**: date, pilot, site, task, flight time (min), battery, remarks, link to the log; separately, repairs and replacements (what, why, serial numbers). The total flight time of the aircraft and its components (motors, ESCs, props) is the basis of the inspection schedule.
- **Battery logbook**: battery number (sticker), purchase date, cycles, voltage before/after the flight, internal resistance of the cells by date, damage. A number on the battery is mandatory — otherwise the “bad battery” is impossible to pin down.
- **Format**: a spreadsheet or CSV in git next to the aircraft parameters (module “Configs in CI”) — you get history and search for free.

### Battery service life
- **Internal resistance (IR)** of each cell is the main indicator. Measure it with a charger that has an IR function (compare using the same device at the same temperature). Rising IR means less output under load and more heating.
- **Retirement criteria** (guidelines, check with the manufacturer): cell IR has grown to roughly 1.5–2 times the new value; cell imbalance after charging and resting is more than ~0.03–0.05 V; puffing; capacity below ~80 % of rated; mechanical damage after a crash. A puffed or damaged battery: discharge it and dispose of it properly, do not fly it.
- **Storage**: 3.80–3.85 V per cell (storage), cool, in a fireproof bag or box; do not keep them fully charged for more than a few days.
- **Operating practice**: do not discharge below the landing threshold (module “Power”), do not charge them hot or cold, use balance charging.

### Inspection schedule
| When | What | Criterion |
|---|---|---|
| Before every flight | props, prop and motor mounting, battery and connector, antennas, straps | cracks and chips, play, connector heating |
| After every flight | motor and ESC temperature by touch, props, frame, logbook entry | one motor noticeably hotter than the others — take it apart |
| After any impact | props (all of them, not only the broken one), frame, motors for play and binding, check calibrations | a prop that touched something — replace it |
| Every ~10–20 h | motor bearings (spin by hand — grinding, play), frame screws, soldering and connectors, flight controller dampers | grinding and play — replace the bearings or the motor |
| Every ~50 h or per season | full teardown: wiring, insulation, power connectors, planned firmware update | signs of heating, chafing |

The intervals are starting values; your own come from the logbook: if bearings die within 30 h, the schedule is 20.

### Logs as a maintenance tool
A log is not only “why it crashed” but also “what is wearing out”:
- **Vibration** (`VIBE` in ArduPilot, gyro in Betaflight Blackbox): growth from flight to flight with the same props — bearings, a prop, a loose mount.
- **Motor balance** (`RCOU` / `motor[n]`): one motor consistently higher than the others in hover — it is weaker (wear, prop) or the aircraft is out of balance.
- **Compass** (`MAG`): increased current-induced interference after wiring repairs.
- **Battery** (`BAT`): voltage sag at the same current grows — the battery resistance is growing.

A trend matters more than a single value: one point is noise, five points are wear.

### Reliability: numbers instead of feelings
- **Failure rate** λ — failures per hour (roughly constant during normal operation). **MTBF** = 1/λ — mean time between failures. An MTBF of 1000 h does not mean “1000 h without failures”: the probability of running t hours without a failure is R(t) = e^(−λt), and for 1000 h that is only 37 %.
- **Bathtub curve**: at the start, early failures (defects, cold solder joints) → normal operation → wear-out. Hence acceptance testing of new aircraft (ground test, first flights low and close) and replacement by service life before the wear-out zone.
- **Series system** — failure of any component = failure of the system: R = R₁·R₂·…·Rₙ. For motors, a quadcopter is a series system of four: R = r⁴.
- **Redundancy** — the system works as long as at least one of the duplicates is alive: R = 1 − (1 − r)². A hexacopter that can make it home on five motors is “5 out of 6 needed”: R = r⁶ + 6·r⁵·(1 − r). But the ability to survive a motor failure depends on the frame, thrust-to-weight ratio and firmware — you test it, you don't assume it (module “Redundancy”).
- **Example**: motor λ = 1/1000 h (illustrative). Over 100 h of flight time without replacement: quad R = e^(−0.4) ≈ 0.67, a hexa that survives one failure ≈ 0.90. The same calculation shows why replacing motors by service life raises reliability more than it seems.

{{diagram:chart-reliability|Probability of avoiding a loss due to motor failure versus flight time: a quad (needs all four) versus a hexa that survives one failure.}}

### One-page FMEA
For each component: how it can fail → what the pilot will see → what the aircraft will do → how to detect it in advance → what we do. Five rows for the motor, ESC, battery, receiver and GNSS give you a plan of the inspections and checks that actually matter.

## practice
### Step 1. Logbooks
Set up an aircraft logbook and a battery logbook (CSV or spreadsheet) with the fields from the theory. Number the batteries with stickers. Enter the recent flights you can reconstruct from the logs.

### Step 2. Batteries
For each battery: the IR of each cell (a charger with an IR function, at room temperature), and the cell voltages after charging and 30 min of rest. Mark the batteries that are close to retirement by the criteria. A script for the logbook:
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

### Step 3. Trend from logs
Take 5+ logs of one aircraft over a period (ArduPilot `.bin` or Blackbox). For each: the average vibration in hover and the average output of each motor in hover. Plot the trend (pandas/matplotlib, module “Data and Python”). Is there a motor that is consistently higher? Is vibration growing?

### Step 4. Schedule and FMEA
An inspection table for your aircraft with intervals by flight time, and an FMEA for 5 components. Calculate R for your frame over a season's flight time with motor λ of 1/1000 and 1/3000 h.

The lab counts as done when the logbooks are set up and filled in, battery IR and imbalance are measured with a decision for each battery, the vibration and motor balance trend is plotted from 5+ logs, the schedule and FMEA are written, and the reliability calculation for your frame is done.

## diagnostics
- **Symptom:** one battery “dies” faster than the others
  - Possible cause: growing IR of one cell, imbalance.
  - What to do: per-cell IR, logbook; if the criteria are exceeded, retire it.
- **Symptom:** vibration grows from flight to flight
  - Possible cause: worn bearings, a damaged prop, a loosened mount.
  - What to do: spin the motors by hand, replace the props, check the mounts, compare with the replacement log.
- **Symptom:** one motor is hotter than the others after a flight
  - Possible cause: motor wear, a heavy/damaged prop, the aircraft is out of balance.
  - What to do: motor outputs in the log, replace the prop, check the CG, then the motor.
- **Symptom:** a “sudden” failure without warning
  - Possible cause: no logbook and no trends — there were warnings, but nobody recorded them.
  - What to do: logbook, trends from logs, replacement by service life.
- **Symptom:** strange compass behavior after a repair
  - Possible cause: power wires routed differently, current-induced interference.
  - What to do: compare `MAG` against current before and after, recalibrate, restore the wire routing.

## references
- ArduPilot — Measuring vibration | https://ardupilot.org/copter/docs/common-measuring-vibration.html | primary | A
- ArduPilot — Battery monitor and failsafe | https://ardupilot.org/copter/docs/common-powermodule-landingpage.html | primary | A
- NIST/SEMATECH e-Handbook — Reliability (exponential model, MTBF) | https://www.itl.nist.gov/div898/handbook/apr/section1/apr1.htm | primary | A
- Battery University — How to prolong lithium-based batteries | https://batteryuniversity.com/article/bu-808-how-to-prolong-lithium-based-batteries | secondary | B

## checklist
- I keep an aircraft logbook and a battery logbook with numbered batteries
- I measure cell IR and retire batteries by the criteria
- I inspect the aircraft on schedule and replace props after any contact
- I track vibration and motor balance trends from the logs
- I calculate the reliability of series and redundant systems
- I write an FMEA for the main components
