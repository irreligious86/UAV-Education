---
id: f-electricity-101
title: "Electricity and Measurements 101"
level: L1
readingTime: 30 min
firmware: any firmware
status: published
added: 2026-11-08
tags:
  - electricity
  - Ohm's law
  - multimeter
  - LiPo
related:
  - f-power
  - el-power-design
  - el-measure
next:
  - f-power
source: content/foundation/f-electricity-101.md
source_hash: 34fe88759b61
---

## summary
The bridge between “how it flies” and “power circuit design”. Without it, people repeat other people's decisions: they fit a capacitor because “that's how it's done” and don't understand why the BEC is hot. The module gives you the minimum you need to calculate: Ohm's law, power, series and parallel connection, the thrust → power → current → sag chain worked through with formulas, safe multimeter use, and the LiPo handling rules — charging, storage, damage, fire.

## theory
### Three quantities and two formulas
- **Voltage U** (volts) — the “pressure” in the circuit. A 4S battery — 14.8 V nominal, 16.8 V full.
- **Current I** (amps) — the “flow”. A 5" motor at full throttle — 30–40 A.
- **Resistance R** (ohms) — what impedes the flow. A motor winding — fractions of an ohm, a wire — milliohms.

**Ohm's law: U = I·R.** If 60 A flows through a resistance of 10 mΩ (wire + connector), 0.6 V drops across it. **Power P = U·I = I²·R = U²/R** (watts). The same 60 A through 10 mΩ — 36 W of heat in the wire and connector. That is why current is the main enemy: losses grow with the square of the current.

### Series and parallel
- **Series (S)**: voltages add up, the same current flows through all cells. 6 cells of 3.7 V = 22.2 V (6S). Resistances add up too.
- **Parallel (P)**: the current splits, the voltage is the same, capacities add up. 4 cells of 3 Ah = 12 Ah (4P); the internal resistance is divided by 4.
18650 cells of 3 Ah and 30 mΩ in a 6S4P pack: 22.2 V, 12 Ah, R_int = 30 × 6 / 4 = 45 mΩ.

### The chain from thrust to sag
1. The thrust you need is T (from mechanics: m·g in hover).
2. From the motor's table: thrust → power P_mech and current I_motor at voltage U.
3. Battery current ≈ ΣI_motors + loads (ESCs pass current through, they don't multiply it; but at partial throttle the battery current is lower than the motor phase current — the ESC works as a step-down converter).
4. Sag ΔU = I·(R_int_batt + R_wires + R_connectors). Under load U_onboard = U_open − ΔU.
5. The power the battery delivers: P = U_onboard·I; the losses P_loss = I²·R_total — heat up the battery and wires.

Example: a 10" cargo craft, 4 × 5 A = 20 A in hover, R_int of a 6S Li-Ion 4P battery 45 mΩ, wires and XT60 15 mΩ → ΔU = 20 × 0.06 = 1.2 V, losses 24 W. At full throttle 100 A → ΔU = 6 V (!) and 600 W of losses — Li-Ion is not for racing.

### Energy and capacity
Capacity in Ah (or mAh) — how much current for how many hours. Energy Wh = Ah × U_nom. 6S 4 Ah = 88.8 Wh. At an average power of 300 W — 0.3 h = 18 min in theory, ~14 taking into account the usable 80%. **C rating** — the maximum current as a multiple of capacity: 4 Ah × 25C = 100 A. Real values are often lower than the marking; look at the sag under load. How to choose a pack (the rule — in `f-power`, “Capacity and C rating”): capacity — by the average current, Q ≥ I_avg × t / (60 × 0.8); label C × Q ≥ I_peak — only a filter; the cell resistance decides: the sag I_peak × R_cell on a fresh pack is no more than 0.5 V, i.e. R_cell ≤ 0.5 / I_peak.

### Multimeter: what and how
- **Voltage (V⎓)**: probes in parallel with what you measure; black in COM, red in V. Almost always safe. Checking a battery: the total and each cell through the balance connector (spread thresholds — one line in `f-power`, “Charging, storage, disposal”: after charging ≤ 0.02 V, after a flight ≤ 0.05 V, after charging and resting more than 0.05 V — retire it).
- **Continuity (•)))**: only on a de-energized circuit. A beep between + and − of the power bus = a short circuit. On a circuit with a capacitor the beep may be short, then the resistance rises — that is normal.
- **Resistance (Ω)**: de-energized. Motor windings — three identical values (0.05–0.3 Ω; a cheap multimeter will show noise — what matters is that they are the same). A difference — an inter-turn short.
- **Current (A)**: probes *in series*, red in the 10 A jack; above 10 A — not allowed (the fuse or the meter will burn). The main beginner mistake: leaving the probe in the A jack and measuring voltage — that is a short circuit through the meter. On-board current is measured with the FC's current sensor (calibrated) or with an inline wattmeter.
- **Diode test**: checks diodes and junctions — will be useful later.

### LiPo: rules that are not up for discussion
- Per-cell voltages: full 4.20 V (HV — 4.35), nominal 3.7, storage about 3.8 (3.80–3.90 per the manufacturer's datasheet, f-power), under load warning at 3.5 and critical threshold at 3.3 (Betaflight defaults for 4–6S; for 1S and Li-Ion the thresholds differ — table in `f-power`), below 3.0 — damage.
- **Charging**: only with a balance charger, current ≤ 1C (4 Ah → 4 A) unless the manufacturer allows more; in a LiPo bag or on a non-flammable surface; never leave it unattended; do not charge it cold or hot: the limit is per the pack's datasheet (Gens Ace allows charging at 10–45 °C, f-power).
- **Storage**: at storage voltage, somewhere cool, not full for longer than a day — it loses capacity and swells.
- **Damage**: swelling, a puncture, a smell — the battery never flies again. Discharge it to 0 through a load (a discharger or a resistor; not salt water — procedure in `f-power`) and dispose of it properly. A crashed drone → the battery goes to an open, non-flammable spot for 30 minutes.
- **Fire**: LiPo burns on its own and is hard to extinguish. Plan ahead: a bucket of sand, a place to throw it, don't breathe the smoke. A lot of water cools it and is acceptable for LiPo (there is no metallic lithium in it), but the best tool is prevention: correct charging, inspection, a LiPo bag.
- **Short circuit**: the short-circuit current is hundreds of amps, a connector welds in a fraction of a second. Solder the power connector one pin at a time, insulate your tools, don't put an XT60 on metal.

{{diagram:thrust-sag-chain|The chain from thrust to sag: more thrust — more current, a bigger drop across the internal resistance, lower voltage under load.}}

### Place in the system

- **Receives:** thrust in hover and in maneuvers (`f-mechanics`); the motor current at that thrust — from the thrust table (`f-aero-props`).
- **Provides:** battery current, sag ΔU and I²·R losses — to the choice of chemistry and the flight-time calculation (`f-power`), to wire gauges, connectors and BECs (`el-power-design`); multimeter techniques — to measurements and troubleshooting (`el-measure`, `diag-troubleshooting`).
- **If you get it wrong here:** the milliohms of the wires and connector are left out of the calculation → the real sag is larger, and on a sharp throttle input the BEC reboots the flight controller or the ESCs go into protection (tree 3 in `diag-troubleshooting`). A cell imbalance of more than 0.05 V missed during the check → the weak cell sags first, and the battery gets retired (`ops-maintenance`).

## practice
{{widget:wire-drop}}

### Step 1. Electrical spec sheet
A table: battery open-circuit voltage, the voltage of each cell, the 5 V and 9 V BEC outputs (with no load and with the on-board equipment connected), the resistance of the three phases of each motor.

### Step 2. Calculating the hover current
From the motor's table: thrust per motor in hover → current → ×4 + 1 A for the on-board equipment. Write it down. Battery R_int: from the datasheet or measure it: U_open − U under a known current load, divided by the current.

### Step 3. Cross-check
After hovering — the average current from the log (the current sensor must be calibrated against a wattmeter). The discrepancy and its cause go into the spec sheet.

### Step 4. LiPo checklist
Your own one-page checklist: charging, storage, inspection, what to do after a crash, where the sand is. Pin it at the charging spot.

### Reference values and a worked example
- **LiPo cells:** 4.20 V — full charge, 3.80–3.85 V — storage. After balancing the difference between cells is ≤ 0.02 V; after charging and resting, from 0.03 V — watch it, more than 0.05 V — retire it (course guideline, `f-power` and the “Maintenance” module).
- **BEC:** 5 V should be within about ±5 % (4.75–5.25 V) with the on-board equipment connected. If the voltage sags noticeably under load, the BEC is too small for the current.
- **Pack internal resistance:** 25.2 V with no load, 24.4 V under a 20 A current → R = (25.2 − 24.4) / 20 = 0.04 Ω for a 6S pack, ≈ 6.7 mΩ per cell. At hover current the sag will be proportionally smaller.
- **Motor windings:** phase resistance is tenths and hundredths of an ohm, and an ordinary multimeter measures it poorly: the probes and the contact give a comparable error. Compare the three phases of one motor with each other: they must match. A bad solder joint on a lead raises the two pairs that include that lead; one pair that stands out from the other two — a damaged winding (inter-turn short); “open” — a broken winding or lead. More precisely — pass a known current from a bench supply (for example, 1 A) and measure the voltage drop.

### What the cross-check should give
The calculated hover current and the average current from the log differ by 10–20 % — that is normal: the motor table was measured with a different prop, at a different temperature and voltage. More than 30 % — check the current sensor calibration against a wattmeter and the weight of the aircraft.

### Lab
The craft's electrical spec sheet (step 1), the hover current calculation with a cross-check (steps 2–3), the LiPo checklist (step 4).

Self-check: the lab is done when the voltages of each cell and of the BEC outputs are measured, written down and fall within the reference values (difference between cells after balancing no more than 0.02 V, `f-power`; 5 V with the on-board equipment connected — 4.75–5.25 V), the pack's R_int is calculated the same way as in the worked example ((25.2 − 24.4) / 20 = 0.04 Ω), the hover current is calculated and cross-checked with the log (a 10–20 % discrepancy is normal; more than 30 % — the cause is found and written down: current sensor calibration or weight), the three phases of each motor match each other, and the LiPo storage and charging checklist hangs at the charging spot.

## diagnostics
- **Symptom:** the multimeter burned out / the fuse blew during a measurement
  - Possible cause: the probe in the A jack while measuring voltage.
  - What to do: replace the fuse; rule: after measuring current, move the probe back to V immediately.
- **Symptom:** one battery cell is 0.1 V or more below the others
  - Possible cause: cell degradation, imbalance.
  - What to do: balance charge; if it happens again — the battery goes to storage/disposal, not into the air.
- **Symptom:** the XT60 is hot after a flight
  - Possible cause: contact resistance: I²·R.
  - What to do: replace the connector, check the soldering.
- **Symptom:** flight time is half of what the capacity calculation gives
  - Possible cause: calculated from the rating, the real capacity is lower (age, cold), the current is higher.
  - What to do: measure the delivered capacity with the charger, take the average current from the log.
- **Symptom:** motor phase resistances differ
  - Possible cause: an inter-turn short or a damaged wire.
  - What to do: replace the motor; check whether it heats up more than the others.

## references
- Battery Safety — INAV documentation | https://github.com/iNavFlight/inav/blob/master/docs/Battery.md | primary | A
- LiPo Battery Basics: Safe Use — Academy of Model Aeronautics (Model Aviation) | https://www.modelaviation.com/lipo1 | secondary | B
- Battery Monitor configuration and calibration — ArduPilot | https://ardupilot.org/copter/docs/common-power-module-configuration-in-mission-planner.html | primary | A

## checklist
- I can apply U = I·R and P = U·I to the craft's circuits
- I understand why losses grow with the square of the current
- I measure voltage and resistance and check continuity safely
- I know the LiPo voltages: full, storage, minimum
- The LiPo checklist is written and kept at the charging spot
