---
id: el-battery-packs
title: "Li-Ion and LiFePO4 packs: cells, welding, BMS"
level: L2
readingTime: 35 min
firmware: any firmware
status: published
added: 2026-11-08
tags:
  - Li-Ion
  - LiFePO4
  - BMS
  - spot welding
related:
  - f-power
  - el-power-design
  - el-measure
next:
  - el-measure
source: content/electronics/el-battery-packs.md
source_hash: 6a0ec0198fc3
---

## summary
LiPo is the norm for 5" and anything that needs 20C+, but long-range wings, 7–10" long range and heavy-lift X8s fly on Li-Ion 18650/21700, while ground stations and heavy platforms run on LiFePO4. This module compares the three chemistries in numbers, teaches you to work out the S/P configuration for current and capacity with internal resistance in mind, build a pack by spot welding nickel strip without overheating the cell, pick a BMS and balancer so they don't cut power to the aircraft in flight, and measure the real capacity and sag with a cycle under load.

## theory
### Three chemistries in numbers
| Parameter | LiPo (graphite/LCO-NMC) | Li-Ion 18650/21700 (NMC/NCA) | LiFePO4 |
|---|---|---|---|
| Cell nominal | 3.7 V (4.2 full, 3.3–3.5 land) | 3.6 V (4.2 full, 2.5–3.0 land) | 3.2 V (3.65 full, 2.5 land) |
| Specific energy | 150–200 Wh/kg | 220–270 Wh/kg (high-capacity 21700) | 90–140 Wh/kg |
| Continuous current | 20–100C (a 1300 mAh 75C pack ≈ 100 A) | 3–10C per cell (P42A: 45 A at 4.2 Ah; 40T: 35 A at 4 Ah; VTC6: 15 A per datasheet, 30 A with an 80 °C cutoff, at 3 Ah) | 1–3C, high-current ones up to 10C |
| Cycle life | 150–300 cycles to 80% | 300–500 | 2000–4000 |
| Internal resistance | 1–5 mΩ/cell | 15–40 mΩ/cell | 5–20 mΩ (26650) |
| Safety | catches fire easily, puffs | burns, but protected by the can; CID/PTC in “protected” versions | very tolerant of overcharge and temperature |
| Where it fits | racing, freestyle, anything with T/W > 3 | long range, wings, heavy-lift, companion power | ground equipment, heavy slow platforms, stationary |

Rule: Li-Ion wins when the average pack current is ≤ 1–2C and the flight is longer than 15 minutes. If hover needs > 3C, go LiPo.

### S/P configuration
- **S** sets the voltage: 6S Li-Ion = 21.6 V nominal, 25.2 full, 18 V to land (3.0 V/cell), 15 V is the absolute limit.
- **P** sets the current and capacity: 4P of P42A = 16.8 Ah, 4 × 45 = 180 A continuous per datasheet, but in practice limited by heating and sag.
- **Sag**: R of the pack = R of the cell × S / P. 6S4P P42A ≈ 25 mΩ × 6 / 4 ≈ 38 mΩ (plus strip and connections — +10–20 mΩ). At 60 A the sag is ≈ 2.3–3.5 V — almost 1 cell “lost” under load. That's why for the same job you size Li-Ion with margin on P, not “right at the datasheet current”.
- **Heat**: P = I²·R on the pack: 60 A × 60 A × 0.05 Ω = 180 W over the whole pack — noticeable heating in 10 minutes. Rule of thumb: average current ≤ 1.5C for 21700 without forced cooling.
- **Mass budget**: 6S4P 21700 ≈ 24 × 70 g = 1.7 kg + strip/case ≈ 1.85 kg for 363 Wh (≈ 195 Wh/kg including hardware).

### Spot welding
You must not solder to cells: overheating the terminal damages the separator and the protection. Weld with nickel strip:

- **Strip**: pure nickel (not nickel-plated steel — its resistance is several times higher and it rusts). A 0.15 × 8 mm cross-section carries roughly 7–10 A per path continuously; for high-current packs use 0.2 × 10 mm, “doubled” strip or a copper bus bar with a nickel layer, or parallel paths.
- **Welder**: a capacitor/supercapacitor or transformer welder; tune it on scraps: a weld should tear the strip leaving a crater, not peel off. Two electrodes on the same side, 2–4 welds per cell.
- **Order**: welding layout on paper → cells of equal capacity and voltage (spread ≤ 0.02 V) → insulator rings on the positive terminals → parallel groups → series links → balance wires from each group → heat shrink/case with air for cooling.
- **Safety**: shorting a 21700 through nickel strip means hundreds of amps and a burn; work one connection at a time, no metal tools over the assembled part, safety glasses, sand nearby, a non-combustible box and a bucket of water for cooling (class D is for metallic lithium, and Li-Ion has none).

### BMS, balancer and the drone
A BMS protects against overcharge, overdischarge, overcurrent and temperature. For **flight** a classic BMS is dangerous: a discharge cutoff on current/temperature in the air = a crash. Options:

1. **No BMS on board** — balancing through the balance connector at charging (like LiPo), voltage monitoring by the flight controller (voltage failsafe). The standard for flying packs.
2. **Charge-only BMS**: balancer and protection while charging, discharge goes direct. Good for stationary and ground use.
3. **Smart BMS with configurable thresholds** (JK/Jikong and similar, with a 1–2 A active balancer and Bluetooth): for ground stations and heavy slow platforms; for flight — only with discharge protection disabled and with an understanding of the consequences.

An active balancer (moves energy between groups) is needed for large capacity and infrequent full charges; a passive one (burns the excess on resistors) is enough for 4–6S flying packs balanced regularly.

### Internal resistance and health
The charger shows IR per cell: a new 21700 ≈ 15–25 mΩ; a rise to 50+ is end of life for high-current work. A difference between groups > 30% means a weak group — check the welds/cells. LiPo: 1–3 mΩ new, 10+ — time to move it to ground duty.

{{diagram:chemistry-choice|Choosing a chemistry: LiPo when you need current, Li-Ion when you need energy, LiFePO4 when you need cycle life and safety.}}

## practice
### Step 1. Pick the chemistry for the job
For your aircraft: average hover/cruise current from the log, the desired flight time, the mass. Work out the C-rate for the LiPo and Li-Ion candidates. If the average current is ≤ 1.5C on Li-Ion, go on with Li-Ion.

### Step 2. S/P calculation
Pick a cell (datasheet: capacity, continuous current, IR). P ≥ maximum current / (0.6 × cell current) — a 40% margin for heating and sag. Work out the pack R, the sag at maximum and in hover, the heat, the mass and Wh/kg. Compare with LiPo.

### Step 3. Welding design
Layout: cell arrangement, strip direction, path cross-section for the group current, balance wire points, connector (XT60/XT90 depending on current), an output fuse. The lab accepts “designed” without building it.

### Step 4. Pack test
1. Full charge with balancing, record the group voltages.
2. Discharge under constant load (a discharger, a resistor, or a flight with a current log) down to 3.0 V/cell: the integral of I·dt = the real capacity. Compare with datasheet × P: ≥ 90% is normal.
3. Sag: the voltage without load and under 1C after 10 s — pack R = ΔU/I. Compare with the calculation.
4. Pack temperature after discharge ≤ 45 °C.

## diagnostics
- **Symptom:** one group is always lower after a flight
  - Possible cause: a weak cell or a bad weld in the group (high R).
  - What to do: IR per group, re-measure the cells, re-weld.
- **Symptom:** heavy sag with normal capacity
  - Possible cause: too few P for the current, thin strip, nickel-plated steel.
  - What to do: recalculate P, use thicker pure nickel strip/parallel paths.
- **Symptom:** the pack cut out in flight
  - Possible cause: the BMS tripped on current/temperature.
  - What to do: take the BMS off the discharge path, voltage failsafe in the firmware.
- **Symptom:** 70% of the rated capacity in the test
  - Possible cause: counterfeit cells, old cells, discharge in the cold.
  - What to do: test individual cells, buy from trusted suppliers, warm the pack to 20 °C.
- **Symptom:** the strip comes off the cell with a finger
  - Possible cause: a weak weld.
  - What to do: tune the energy on scraps, 4 welds, check the electrodes.

## references
- ArduPilot — Battery Monitors (voltage/current, failsafe context) | https://ardupilot.org/copter/docs/common-powermodule-landingpage.html | primary | A
- Battery University — Types of Lithium-ion | https://batteryuniversity.com/article/lithium-ion | secondary | B
- Battery University — BU-302: Series and Parallel Battery Configurations | https://batteryuniversity.com/article/serial-and-parallel-battery-configurations | secondary | B

## checklist
- I know when Li-Ion beats LiPo and when it doesn't
- I worked out S/P, pack R, sag and heat for my use case
- The welding layout with strip cross-section and balance leads is ready
- I understand why a BMS with discharge cutoff is dangerous in flight
- The real capacity and sag are measured with a cycle
