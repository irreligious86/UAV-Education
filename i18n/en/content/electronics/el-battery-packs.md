---
id: el-battery-packs
title: "Li-Ion and LiFePO4 packs: cells, spot welding, BMS"
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
source_hash: 1f5cf0350208
---

## summary
LiPo is the norm for 5" quads and anything that needs 20C or more, but long-range wings, 7–10" long-range quads and X8 heavy lifters fly on 18650/21700 Li-Ion, while ground stations and heavy platforms run on LiFePO4. This module compares the three chemistries with numbers and teaches you to size an S/P configuration for current and capacity with internal resistance taken into account, to build a pack by spot welding nickel strip without overheating the cell, to choose a BMS and balancer that will not cut power to the aircraft in flight, and to measure real capacity and voltage sag with a discharge cycle under load.

## theory
### The three chemistries in numbers
| Parameter | LiPo (graphite/LCO-NMC) | Li-Ion 18650/21700 (NMC/NCA) | LiFePO4 |
|---|---|---|---|
| Nominal cell voltage | 3.7 V (4.2 full; under load: warning 3.5, critical 3.3, never below 3.0; `f-power`) | 3.6 V (4.2 full; under load: warning 3.3, land at 3.0; 2.5 is the P42A datasheet discharge cut-off, `f-power`) | 3.2 V (3.65 full; land at 2.8–3.0 under load; 2.5 is the cut-off) |
| Specific energy | 150–200 Wh/kg | 220–270 Wh/kg (high-capacity 21700) | 90–140 Wh/kg |
| Continuous current | 20–100C on the label (a 1300 mAh 75C pack ≈ 100 A); labels are inflated, so choose by IR: R_cell ≤ 0.5 V / I_peak (`f-power`) | 3–10C per cell (P42A: 45 A at 4.2 Ah; 40T: 35 A at 4 Ah; VTC6: 15 A per the datasheet, 30 A only with an 80 °C temperature cut, at 3 Ah) | 1–3C, high-drain cells up to 10C |
| Cycle life | 150–300 cycles to 80% | 300–500 | 2000–4000 |
| Internal resistance | 1–5 mΩ per cell | 15–40 mΩ per cell | 5–20 mΩ (26650) |
| Safety | catches fire easily, puffs | the steel can resists puncture but does not stop thermal runaway: the cell vents violently and burns; CID/PTC in "protected" versions | the most thermally stable (thermal runaway ≈270 °C vs ≈150–210 °C for NCA/NMC); tolerates only mild overcharge: still charge CC/CV to 3.65 V per cell with balancing/BMS |
| Where it fits | racing, freestyle, anything with T/W > 3 | long range, wings, heavy lifters, companion power | ground equipment, heavy slow platforms, stationary use |

Rule: Li-Ion wins when the average current per cell is ≤ 1.5C (the thermal limit, see "Heat" below), the peak stays within the 0.6 rule (practice step 2), and the flight is longer than 15 minutes. Between 1.5C and 3C, add more P if the mass still passes the flight-time calculation (`des-sizing`); otherwise use LiPo. If hover needs > 3C, use LiPo.

**Sizing LiPo for current is covered by the rule in `f-power` ("Capacity and C rating: how to choose").** Capacity follows the average current: Q ≥ I_avg × t / (60 × 0.8). C rating and resistance follow the peak: label C × Q ≥ I_peak is only a filter; the deciding check is that the cell sag at the peak, I_peak × R_cell, stays within 0.5 V on a fresh pack. The example from there: a 5" 6S 1300 mAh pack with a 100 A peak needs C ≥ 77 on the label and R_cell ≤ 5 mΩ; a fresh pack at 2 mΩ per cell sags 0.2 V per cell. For Li-Ion the same problem is solved by the S/P rule with the 0.6 factor (practice step 2).

### S/P configuration
- **S** sets the voltage: 6S Li-Ion = 21.6 V nominal, 25.2 full, 18 V to land (3.0 V per cell), 15 V is the absolute limit.
- **P** sets the current and capacity: 4P of P42A = 16.8 Ah and 4 × 45 = 180 A continuous per the datasheet, but in practice it is limited by heat and sag.
- **Sag**: pack R = cell R × S / P. 6S4P P42A ≈ 25 mΩ × 6 / 4 ≈ 38 mΩ (25 mΩ is the course's design value with margin for spread and aging; the datasheet DC resistance of a new P42A is 16 mΩ at 10 A/1 s; add 10–20 mΩ for strip and joints). At 60 A the sag is ≈ 2.3–3.5 V: almost 1 cell is "lost" under load. That is why Li-Ion for the same job is built with extra P, not "just enough for the datasheet current".
- **Heat**: P = I²·R across the pack: 60 A × 60 A × 0.05 Ω = 180 W over the whole pack, noticeable heating within 10 minutes. Guideline: average current ≤ 1.5C for 21700 cells without forced cooling.
- **Mass budget**: 6S4P 21700 ≈ 24 × 70 g = 1.7 kg, plus strip and enclosure ≈ 1.85 kg for 363 Wh (≈ 195 Wh/kg including the hardware).

The P rule from practice step 2 for the P42A: 0.6 × 45 A = 27 A per cell, so 2P handles up to 54 A, 3P up to 81 A, 4P up to 108 A. For 60 A the rule requires P ≥ 60 / 27 ≈ 2.2, that is 3P (50 mΩ, 3.0 V of sag); the 4P from the example has current margin (up to 108 A) and less sag: 2.3 V from the cells alone versus 3.0 V for 3P.

{{diagram:chart-pack-sag-sp|Sag grows linearly with current and inversely with P; each curve ends at the 0.6-rule limit, and the example 4P at 60 A loses 2.3–3.5 V, almost a whole cell.}}

### Spot welding
Never solder to the cells: overheating the terminal damages the separator and the protection devices. Weld nickel strip instead:

- **Strip**: pure nickel (not nickel-plated steel, which has several times the resistance and rusts). A 0.15 × 8 mm strip carries roughly 5 A per run comfortably and up to ~8 A continuously (a course guideline; check the strip's temperature); for high-current packs use 0.2 × 10 mm, a double layer of strip, a copper busbar with a nickel layer, or parallel runs.
- **Welder**: a capacitor/supercapacitor or transformer spot welder; tune it on offcuts: a good weld tears the strip and leaves a crater instead of peeling off. Both electrodes on the same side, 2–4 welds per cell.
- **Order**: welding plan on paper → cells matched in capacity and voltage (spread ≤ 0.02 V) → insulator rings on the positive terminals → parallel groups → series links → a balance lead from each group → heat-shrink or an enclosure with air for cooling.
- **Safety**: shorting a 21700 through nickel strip means hundreds of amps and burns; make one connection at a time, no metal tools over the assembled part, wear safety glasses, keep sand, a non-flammable box and a bucket of water for cooling nearby (Class D is for lithium metal, and Li-Ion cells contain none).

### BMS, balancer and the drone
A BMS protects against overcharge, overdischarge, overcurrent and overtemperature. For **flight** a classic BMS is dangerous: a discharge cutoff on current or temperature in the air means a crash. The options:

1. **No BMS on board**: balance through the balance connector while charging (as with LiPo), and let the flight controller monitor voltage (battery voltage failsafe). This is the standard for flight packs.
2. **Charge-only BMS**: balancing and protection while charging, discharge goes straight out. Good for stationary and ground equipment.
3. **Smart BMS with configurable thresholds** (JK/Jikong and similar, with a 1–2 A active balancer and Bluetooth): for ground stations and heavy slow platforms; in flight only with the discharge protection disabled and with a clear understanding of the consequences.

An active balancer (moves energy between groups) is needed for large capacities and infrequent full charges; a passive one (burns off the excess in resistors) is enough for 4–6S flight packs that are balanced regularly.

### Internal resistance and health
The charger shows IR per cell: a new 21700 is ≈ 15–25 mΩ; a rise to 50+ is the end of its life for high-current work. A difference between groups of > 30% means a weak group: check the welds and the cells. LiPo: 1–3 mΩ new, 10+ means it is time for ground duty. The deciding criterion is the ratio to the same pack's value when new: a rise of 1.5–2 times (`ops-maintenance`, a course guideline); the absolute 50+ and 10+ mΩ are the fallback when the initial IR was not recorded (for 21700 that is ×2–3 the typical new value).

{{diagram:chemistry-choice|Choosing the chemistry: LiPo when you need current, Li-Ion when you need energy, LiFePO4 when you need cycle life and safety.}}

### Where it fits in the system

- **Takes in:** the aircraft's average and peak current (`f-mechanics`, `f-power`); the required capacity and allowed pack mass (`f-components-choice`, `des-sizing`).
- **Puts out:** voltage under load and pack resistance to the power bus (`el-power-design`); the per-cell landing voltage to the battery failsafe thresholds (`ap-safety-fs`); per-group IR to the battery log (`ops-maintenance`).
- **If you get this wrong:** a BMS with discharge protection left on a flight pack → a cutoff in the air; the log ends without a disarm event (tree 6 in `diag-troubleshooting`). P chosen "just enough" for the datasheet current → under load the sag "loses" almost a cell, and the low-voltage warning arrives earlier than the calculated time (`f-power`).

## practice
### Step 1. Choose the chemistry for the job
For your aircraft: average hover/cruise current from the log, the desired flight time, the mass. Calculate the C rate for the LiPo and Li-Ion candidates (for LiPo: capacity from the average current and R_cell ≤ 0.5 / I_peak, `f-power`). If the average current is ≤ 1.5C on Li-Ion, go on with Li-Ion.

### Step 2. Calculate S/P
Choose a cell (datasheet: capacity, continuous current, IR). P ≥ maximum current / (0.6 × cell current), a 40% margin for heat and sag. Calculate the pack R, the sag at maximum current and in hover, the heat, the mass and Wh/kg. Compare with LiPo.

### Step 3. Welding design
Drawing: cell layout, strip direction, run cross-section for the group current, balance lead points, connector (XT60/XT90 for the current), a fuse on the output. For the lab, "designed" without building it is acceptable.

### Step 4. Test the pack
1. Full balance charge, record the group voltages.
2. Discharge at a constant load (a discharger, a resistor, or a flight with a current log) to 3.0 V per cell: the integral of I·dt is the real capacity. Compare with datasheet × P: ≥ 90% is normal.
3. Sag: voltage at no load and under 1C after 10 s; pack R = ΔU/I. Compare with the calculation.
4. Pack temperature after the discharge ≤ 45 °C.

**Reference answer for self-check.** First check the step 2 formulas on the worked 6S4P P42A example: pack R ≈ 25 mΩ × 6 / 4 ≈ 38 mΩ (10–20 mΩ more with strip and joints), sag at 60 A ≈ 2.3–3.5 V, heat at 0.05 Ω is 180 W, mass ≈ 1.85 kg and ≈ 195 Wh/kg. If these match, plug in your own cell. The step 4 test passes when the capacity is ≥ 90 % of datasheet × P, the temperature is ≤ 45 °C, and the measured R = ΔU/I is no higher than the calculated value including the strip. Two common calculation errors: R calculated without dividing by P (150 mΩ instead of 38), and P chosen "just enough" for the datasheet current without the 0.6 factor, so that under load you "lose" almost a cell. If the measured R is noticeably above the calculation, or the group IRs differ by more than 30 %, check the welds and the cells of the weak group.

## diagnostics
- **Symptom:** one group is always lower after a flight
  - Possible cause: a weak cell or a bad weld in the group (high R).
  - What to do: IR per group, re-measure the cells, re-weld.
- **Symptom:** heavy sag with normal capacity
  - Possible cause: too few P for the current, thin strip, nickel-plated steel.
  - What to do: recalculate P; use thicker pure nickel strip or parallel runs.
- **Symptom:** the pack shut off in flight
  - Possible cause: the BMS tripped on current or temperature.
  - What to do: take the BMS off the discharge path, use the battery voltage failsafe in the firmware.
- **Symptom:** the test shows 70% of the datasheet capacity
  - Possible cause: counterfeit cells, old cells, discharge in the cold.
  - What to do: test individual cells, buy from trusted suppliers, warm the pack to 20 °C.
- **Symptom:** the strip comes off the cell with a finger
  - Possible cause: a weak weld.
  - What to do: tune the energy on offcuts, 4 welds, check the electrodes.

## references
- ArduPilot — Battery Monitors (voltage/current, failsafe context) | https://ardupilot.org/copter/docs/common-powermodule-landingpage.html | primary | A
- Battery University — Types of Lithium-ion | https://batteryuniversity.com/article/types-of-lithium-ion | secondary | B
- Battery University — BU-302: Series and Parallel Battery Configurations | https://batteryuniversity.com/article/serial-and-parallel-battery-configurations | secondary | B

## checklist
- I know when Li-Ion beats LiPo and when it does not
- I have calculated S/P, pack R, sag and heat for my task
- The welding plan with strip cross-section and balance leads is ready
- I understand why a BMS with a discharge cutoff is dangerous in flight
- Real capacity and sag have been measured with a discharge cycle
