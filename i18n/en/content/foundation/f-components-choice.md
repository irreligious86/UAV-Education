---
id: f-components-choice
title: "Choosing components for the mission and the budget"
level: L1
readingTime: 35 min
firmware: any firmware
status: published
added: 2026-11-08
tags:
  - components
  - specification
  - budget
  - selection
related:
  - f-aero-props
  - f-power
  - f-motors-esc
  - eng-method-101
next:
  - eng-method-101
source: content/foundation/f-components-choice.md
source_hash: bfc3c0c3c10c
---

## summary
Eighty percent of real engineering work isn't tuning, it's choosing: what to buy so the drone does the job, stays within budget and doesn't fall apart. This module gives you a method: the mission in numbers → aircraft class → frame and props → motors and ESC → battery → FC and peripherals → mass and T/W check → two alternatives. With a T/W and flight time calculator and a walkthrough of two specifications: a 7" long-range and a 10" heavy-lift.

## theory
### Step 0: the mission in numbers
As long as the mission sounds like “I want to fly far,” there's nothing to choose. You need numbers:

| Parameter | Example: 7" long-range | Example: 10" heavy-lift |
|---|---|---|
| Payload | 30 g camera | 1000 g load |
| Flight time | ≥ 15 min | ≥ 12 min with the load |
| Range | 5 km | 1 km |
| Cruise speed | 15–20 m/s | 8 m/s |
| Conditions | wind up to 8 m/s | wind up to 6 m/s |
| Budget | €400 | €700 |
| Constraints | mass < 1 kg (category) | foldable |

Each number becomes a requirement with an ID in the engineering folder (next module).

### Step 1: class and frame
Prop size determines everything else. The rule: payload mass and flight time set the required efficiency (g/W), and efficiency sets the prop diameter (see the aerodynamics module): 5" gives 4–6 g/W, 7" gives 8–10, 10" gives 12–15, 15" gives 15–20. Long hover with a load means big props; speed and maneuverability mean small ones.

Frame: 3–5 mm carbon arms for 5–7", 5–6 mm or tubes for 10"+. Look at: mass, free space for the battery and payload, protection of the electronics, availability of spare parts (you should be able to buy an arm separately), a 20×20 or 30.5×30.5 mm stack.

### Step 2: motors and props
From the manufacturer's thrust table for the chosen prop and voltage: hover thrust should fall at 30–45% throttle (headroom for wind and maneuvers) at a current no higher than 40% of the continuous rating. Motor size and KV: 7" uses 2806.5/2807 1300–1700 KV on 6S; 10" uses 3110/3115 600–900 KV on 6S; 15" uses 4008–4114 320–400 KV on 6S. Motor mass goes into the mass budget.

{{diagram:component-choice-tree|Power system guidelines for typical aircraft classes.}}

### Step 3: ESC
ESC continuous current ≥ 1.3 × the motor's maximum current from the table; voltage with margin (6S → an ESC rated for 6S, not one that's “up to 6S” at its limit). A 4-in-1 is compact, but one crash means replacing the whole thing; separate ESCs are repairable, but you have to route power to each. The firmware (BLHeli_32/AM32/BLHeli_S) determines telemetry and the RPM filter.

### Step 4: battery
Capacity from current: I_avg (from the table for cruise/hover × number of motors + electronics) × t / 0.8. Chemistry: LiPo for current, Li-Ion for energy per kilogram (but its discharge capability is low: typically 2–3C for high-capacity 21700 cells). Check: does the battery mass fit the mass budget? If not, iterate: heavier battery → more current → an even bigger battery. This loop doesn't always converge; if it doesn't, change the class.

### Step 5: FC, receiver, video, GPS
FC: an F4 is enough for Betaflight without extras, an F7/H7 for INAV/ArduPilot with GPS, compass and logs; number of UARTs ≥ number of peripherals + 1; a blackbox (flash/SD) for log-based tuning. Receiver: a band to match the range (900 MHz for 5+ km). Video: analog is cheap and tough, digital means quality and budget. GPS: with a compass on a mast for INAV/ArduPilot.

### Step 6: mass budget and check
A table: part, mass, price. The result: takeoff mass → T/W from the motor table → hover current → flight time → comparison with the requirements. The rule: if T/W < 2 at full load, redo it. Keep a 15% margin in the budget for props, hardware, wires and repairs.

### Trade-offs
- **Price vs mass**: cheap components are heavier; mass means flight time and current.
- **Repairability**: a drone built from small, available parts lives longer than an exotic one.
- **Margin**: 20% of headroom in current and thrust pays for itself on the first windy day.
- **Availability**: a part that's out of stock six months from now is a problem at the first repair.

The calculator below computes T/W, hover current and flight time from your numbers; use it in step 6.

## practice
{{widget:tw-calc}}

### Step 1. Requirements
A table of the mission in numbers for your own drone idea (as in the theory), 8–12 rows.

### Step 2. Specification
A component table: model, mass, price, a link to the data source (thrust table, datasheet). Totals for mass and price.

### Step 3. Calculation
With the calculator: T/W, hover throttle, current, flight time. Compare with the requirements and write down which ones are met.

### Step 4. Alternatives
Two options (for example, 7" Li-Ion vs 7" LiPo; or a 10" quad vs a 7" with a smaller load) in one table by criteria: time, price, mass, repairability, risk. Justify the choice.

### Worked calculation
The calculator's default values: mass 1400 g, 4 motors with 1200 g maximum thrust each, 6.5 g/W in hover, 6S 4000 mAh, electronics 0.8 A.
- T/W = 4 · 1200 / 1400 = 3.43, hover throttle ≈ 1 / 3.43 ≈ 29% — in the linear "thrust ∝ throttle" approximation; thrust grows faster than throttle (T ∝ n²), so the real hover throttle is higher: with a `MOT_THST_EXPO = 0.65` curve, about 45%.
- Motor power in hover: 1400 g / 6.5 g/W ≈ 215 W; current 215 / (6 · 3.7) + 0.8 ≈ 10.5 A.
- Hover on 80% of capacity: 4 · 0.8 / 10.5 · 60 ≈ 18 minutes. In flight with maneuvers and wind, 20–40% less.
- Add 400 g of load (1800 g): T/W 2.67, throttle 38%, current 13.3 A, hover ≈ 14.5 minutes. That's the price of every gram in minutes of flight.

### What to write down and how to check yourself
- **Requirements table:** every row has a number and a unit. “Flies for a long time” isn't a requirement; “≥ 15 minutes of hover with a 300 g load” is.
- **Specification:** every component has a source for its numbers: the manufacturer's thrust table, a datasheet, weighing. A mass without wires, connectors and hardware is 5–10% too low; add that as a separate row.
- **Calculation:** mark which requirements are met, which aren't, and by how much. If T/W is below 2, the drone has no headroom for wind and maneuvers: you change the specification, not the requirement.
- **Alternatives:** a table of 4–6 weighted criteria with a total. The choice is justified with numbers, not “I like it.”

### Lab
A specification with requirements, a calculation and a comparison of two alternatives: the first document in your engineering folder.

The lab counts as done when the requirements are written as numbers, the specification has prices, masses and data sources, T/W and flight time are calculated with wires and hardware included, and the two alternatives are compared by criteria with a justified choice.

## diagnostics
- **Symptom:** the flight time calculation doesn't converge: the battery grows, the time doesn't
  - Possible cause: the mass → current → mass loop diverges; the aircraft class is too small for the mission.
  - What to do: a bigger prop/frame, or lower the requirements.
- **Symptom:** T/W is 3 on paper, but it hovers at 60% throttle
  - Possible cause: the thrust table is for a different voltage or prop; the real mass is higher.
  - What to do: reweigh, recalculate from your own table, check the voltage under load.
- **Symptom:** not enough UARTs for all the peripherals
  - Possible cause: the FC was chosen without counting ports.
  - What to do: an FC with more UARTs, or combine functions (for example, ESC telemetry over a single port).
- **Symptom:** the budget is exceeded twofold
  - Possible cause: props, hardware, the charger and spare parts weren't accounted for.
  - What to do: a 15–20% margin in the budget; postpone the non-essentials (digital video) to the next iteration.

## references
- Choosing a MultiCopter Frame — ArduPilot Copter | https://ardupilot.org/copter/docs/choosing-a-frame.html | primary | A
- UIUC Propeller Database (efficiency data by diameter) | https://m-selig.ae.illinois.edu/props/propDB.html | primary | A
- How to choose motors for FPV drones — Oscar Liang | https://oscarliang.com/quadcopter-motor-propeller/ | secondary | B

## checklist
- The mission is written in numbers, not words
- The prop diameter is chosen from the required efficiency
- The motors are chosen from the thrust table: hover at 30–45% throttle
- The battery is calculated from current and time, and the mass works out
- Two alternatives are compared and the choice is justified
