---
id: f-electricity-101
title: "Electricity and measurements 101"
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
source_hash: ad65d5a7349e
---

## summary
The bridge between “how it flies” and “power circuit design.” Without it, people copy other people's solutions: they add a capacitor because “that's how it's done” and don't understand why the BEC is hot. This module gives you the minimum you need to calculate: Ohm's law, power, series and parallel connections, the thrust → power → current → voltage sag chain in formulas, safe multimeter use and the rules for handling LiPo: charging, storage, damage, fire.

## theory
### Three quantities and two formulas
- **Voltage U** (volts) is the “pressure” in the circuit. A 4S battery is 14.8 V nominal, 16.8 V full.
- **Current I** (amps) is the “flow.” A 5" motor at full throttle draws 30–40 A.
- **Resistance R** (ohms) is what impedes the flow. A motor winding is a fraction of an ohm, a wire is milliohms.

**Ohm's law: U = I·R.** If 60 A flows through a resistance of 10 mΩ (wire + connector), 0.6 V drops across it. **Power P = U·I = I²·R = U²/R** (watts). The same 60 A through 10 mΩ is 36 W of heat in the wire and connector. That's why current is the main enemy: losses grow with the square of the current.

### Series and parallel
- **Series (S)**: voltages add up, the current is shared. 6 cells of 3.7 V = 22.2 V (6S). Resistances add up too.
- **Parallel (P)**: the current splits, the voltage is shared, capacities add up. 4 cells of 3 Ah = 12 Ah (4P); the internal resistance is divided by 4.
18650 cells of 3 Ah and 30 mΩ in a 6S4P pack: 22.2 V, 12 Ah, R_int = 30 × 6 / 4 = 45 mΩ.

### The chain from thrust to sag
1. You need thrust T (from mechanics: m·g in hover).
2. From the motor table: thrust → power P_mech and current I_motor at voltage U.
3. Battery current ≈ ΣI_motors + loads (ESCs pass current through, they don't multiply it; but at partial throttle the battery current is lower than the motor phase current, because the ESC works as a step-down converter).
4. Sag ΔU = I·(R_int_battery + R_wires + R_connectors). Under load U_onboard = U_open-circuit − ΔU.
5. Power delivered by the battery: P = U_onboard·I; losses P_loss = I²·R_total heat the battery and the wires.

Example: a 10" heavy-lift, 4 × 5 A = 20 A in hover, R_int of a 6S Li-Ion 4P battery 45 mΩ, wires and XT60 15 mΩ → ΔU = 20 × 0.06 = 1.2 V, losses 24 W. At full throttle 100 A → ΔU = 6 V (!) and 600 W of losses: Li-Ion isn't for racing.

### Energy and capacity
Capacity in Ah (or mAh) is how much current for how many hours. Energy in Wh = Ah × U_nom. 6S 4 Ah = 88.8 Wh. At an average power of 300 W that's 0.3 h = 18 min in theory, ~14 if you use 80%. **C rating** is the maximum current as a multiple of capacity: 4 Ah × 25C = 100 A. Real values are often lower than the label; look at the sag under load.

### Multimeter: what and how
- **Voltage (V⎓)**: probes in parallel with what you measure; black in COM, red in V. Safe almost always. Battery check: the whole pack and each cell through the balance connector (a difference > 0.05 V means imbalance).
- **Continuity (•)))**: only on a de-energized circuit. A beep between + and − of the power bus = short circuit. On a circuit with a capacitor the beep may be short and then the resistance rises; that's normal.
- **Resistance (Ω)**: de-energized. Motor windings give three identical values (0.05–0.3 Ω; a cheap multimeter will show noise, what matters is that they match). A difference means a short between turns.
- **Current (A)**: probes *in series*, red in the 10 A jack; above 10 A is off-limits (you'll blow the fuse or the meter). The classic beginner mistake: leaving the probe in the A jack and measuring voltage, which is a short circuit through the meter. Onboard current is measured with the FC's current sensor (calibrated) or with an inline wattmeter.
- **Diode test**: checks diodes and junctions; it'll come in handy later.

### LiPo: rules that aren't up for discussion
- Per-cell voltages: full 4.20 V (HV: 4.35), nominal 3.7, storage 3.80–3.85, minimum under load ~3.3–3.5, below 3.0 means damage.
- **Charging**: only with a balance charger, current ≤ 1C (4 Ah → 4 A) unless the manufacturer allows more; in a LiPo bag or on a non-flammable surface; never unattended; don't charge it cold (< 5 °C) or hot.
- **Storage**: at storage voltage, somewhere cool; don't leave it full for more than a day, or it loses capacity and puffs up.
- **Damage**: puffing, a puncture, a smell: the battery doesn't fly anymore. Discharge it to 0 (salt water or a discharger) and dispose of it properly. After a drone crash, put the battery in an open, non-flammable spot for 30 minutes.
- **Fire**: a LiPo sustains its own fire and is hard to put out. Plan ahead: a bucket of sand, a place to throw it, don't breathe the smoke. Lots of water cools it and is acceptable for LiPo (there's no metallic lithium in it), but the best tool is prevention: correct charging, inspection, a bag.
- **Short circuit**: short-circuit current is hundreds of amps; a connector welds itself in a fraction of a second. Solder the power connector one contact at a time, insulate your tools, don't put an XT60 down on metal.

{{diagram:thrust-sag-chain|The chain from thrust to sag: more thrust means more current, a bigger drop across the internal resistance and a lower voltage under load.}}

## practice
{{widget:wire-drop}}

### Step 1. Electrical passport
A table: the battery's open-circuit voltage, the voltage of each cell, the 5 V and 9 V BEC outputs (with no load and with the electronics connected), the resistance of the three phases of each motor.

### Step 2. Calculating hover current
From the motor table: thrust per motor in hover → current → ×4 + 1 A for the electronics. Write it down. Battery R_int: from the datasheet or measured: U_open-circuit − U under a known load current, divided by that current.

### Step 3. Cross-check
After a hover, get the average current from the log (the current sensor must be calibrated against a wattmeter). The discrepancy and its cause go into the passport.

### Step 4. LiPo checklist
Your own one-page checklist: charging, storage, inspection, what to do after a crash, where the sand is. Pin it up at your charging spot.

### Reference values and a worked example
- **LiPo cells:** 4.20 V is fully charged, 3.80–3.85 V is storage. After balancing, the difference between cells is hundredths of a volt; more than 0.05 V is a reason to check the battery (the “Maintenance” module).
- **BEC:** 5 V should be within roughly ±5% (4.75–5.25 V) with the electronics connected. If the voltage sags noticeably under load, the BEC's current rating is too small.
- **Pack internal resistance:** 25.2 V with no load, 24.4 V at 20 A → R = (25.2 − 24.4) / 20 = 0.04 Ω for a 6S pack, ≈ 6.7 mΩ per cell. At hover current the sag will be proportionally smaller.
- **Motor windings:** phase resistance is tenths and hundredths of an ohm, and an ordinary multimeter measures it poorly: the probes and the contact add a comparable error. Compare the three phases of one motor with each other: they should match. A bad solder joint on a lead raises the two pairs that include that lead; one pair that stands out from the other two means a damaged winding (an inter-turn short); an “open” means a broken winding or lead. For more accuracy, pass a known current from a bench power supply (for example, 1 A) and measure the voltage drop.

### What the cross-check should show
A 10–20% difference between the calculated hover current and the average current from the log is normal: the motor table was measured with a different prop, at a different temperature and voltage. More than 30% means you should check the current sensor calibration against a wattmeter and the drone's mass.

### Lab
The onboard electrical passport (step 1), the hover current calculation with a cross-check (steps 2–3), the LiPo checklist (step 4).

The lab counts as done when the voltages of each cell and of the BEC outputs are measured and written down, the hover current is calculated and checked against the log with the discrepancy explained, the three phases of each motor match, and the LiPo storage and charging checklist is hanging at the charging spot.

## diagnostics
- **Symptom:** the multimeter died / the fuse blew during a measurement
  - Possible cause: the probe was in the A jack while measuring voltage.
  - What to do: replace the fuse; the rule: after measuring current, move the probe back to V right away.
- **Symptom:** one battery cell is 0.1 V or more below the others
  - Possible cause: cell degradation, imbalance.
  - What to do: a balance charge; if it happens again, the battery goes to storage/disposal, not into the air.
- **Symptom:** the XT60 is hot after a flight
  - Possible cause: contact resistance: I²·R.
  - What to do: replace the connector, check the soldering.
- **Symptom:** flight time is half of what the capacity calculation says
  - Possible cause: the calculation used the rated capacity, the real capacity is lower (age, cold), the current is higher.
  - What to do: measure the delivered capacity with the charger, get the average current from the log.
- **Symptom:** motor phase resistances differ
  - Possible cause: a short between turns or a damaged wire.
  - What to do: replace the motor; check whether it runs hotter than the others.

## references
- Battery Safety — INAV documentation | https://github.com/iNavFlight/inav/blob/master/docs/Battery.md | primary | A
- LiPo Battery Basics: Safe Use — Academy of Model Aeronautics (Model Aviation) | https://www.modelaviation.com/lipo1 | secondary | B
- Battery Monitor configuration and calibration — ArduPilot | https://ardupilot.org/copter/docs/common-power-module-configuration-in-mission-planner.html | primary | A

## checklist
- I can apply U = I·R and P = U·I to onboard circuits
- I understand why losses grow with the square of the current
- I measure voltage and resistance and check continuity safely
- I know the LiPo voltages: full, storage, minimum
- The LiPo checklist is written and sits at the charging spot
