---
id: f-components-choice
title: "Choosing Components for the Mission and Budget"
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
source_hash: e57d7f6d3be3
---

## summary
Eighty percent of real engineering work is not tuning but selection: what to buy so that the aircraft does the job, stays within budget and doesn't fall apart. The module gives you a method: the mission in numbers → aircraft class → frame and props → motors and ESC → battery → FC and peripherals → mass and T/W check → two alternatives. With a T/W and flight-time calculator and a walkthrough of two specifications: a long-range 7" and a cargo 10".

## theory
### Step 0: the mission in numbers
As long as the mission sounds like “I want to fly far”, there is nothing to choose. You need numbers:

| Parameter | Example: long-range 7" | Example: cargo 10" |
|---|---|---|
| Payload | camera 30 g | cargo 1000 g |
| Flight time | ≥ 15 min | ≥ 12 min with cargo |
| Range | 5 km | 1 km |
| Cruise speed | 15–20 m/s | 8 m/s |
| Conditions | wind up to 8 m/s | wind up to 6 m/s |
| Budget | €400 | €700 |
| Constraints | mass < 1 kg (category) | foldable |

Each number will become a requirement with an ID in the engineering folder (next module).

### Step 1: class and frame
The prop size determines everything else. Rule: the payload mass and time set the required efficiency (g/W), and the efficiency sets the prop diameter (the aerodynamics module): 5" — 4–6 g/W, 7" — 8–10, 10" — 12–15, 15" — 15–20 (for 10–15" this is the top of the range: a small fraction of maximum thrust; with cargo at working hover — 10–14, see f-aero-props). Long hover with cargo — large props; speed and maneuvering — small ones.

Frame: 4–5 mm carbon arms for a 5" (arm resonance 300–500 Hz — above the motor harmonics in hover), 5–6 mm or tubes for 10"+. On a 7" a 5 mm arm resonates at 150–250 Hz, within the band of the hover harmonics (`f-frame-mech`, “Natural frequencies”), and 6 mm instead of 5 raises the frequency by only ~20 %: thickness alone does not solve this problem. The rule for a 7": after assembly — a tap on the arm (method in `f-frame-mech`); if it coincides with the 1st or 2nd hover harmonic — a static notch or a different motor mounting point (worked example in `f-frame-mech`). Look at: weight, free space for the battery and payload, protection of the electronics, availability of spare parts (an arm must be purchasable separately), a 20×20 or 30.5×30.5 mm stack.

### Step 2: motors and props
From the manufacturer's thrust table for the chosen prop and voltage: the hover throttle must fall within the band for its class (`f-physics`, “Hover throttle”): freestyle and racing (T/W ≥ 6) — no higher than 30–41 %, long range and cinematic (T/W 3–4) — 41–58 %, cargo (T/W 2–2.5) — 56–71 %, and that is the limit; the current in hover — no higher than 40 % of the continuous rating. KV — by the rule from `f-aero-props` (“KV for the prop and cell count”): a prop is designed for certain RPM, RPM ≈ k × KV × U, so with fewer cells the KV is higher. Oscar Liang's guidelines for 6S: 5" — 1700–2100 KV (freestyle), 7" — 980–1300 (long range) or 1200–1400 (freestyle), 10" — about 900; 2806/2807 motors for a 7", 3110/3115 for a 10". A 15" on 6S — 4008–4114 at 320–400 KV (course estimate; example table — MN4006 380KV in `f-aero-props`). The motor mass goes into the mass budget.

{{diagram:component-choice-tree|Powertrain guidelines for typical aircraft classes.}}

### Step 3: ESC
ESC continuous current ≥ 1.3 × the maximum motor current from the table (course guideline: the thrust table is measured on a test stand with a fresh battery and a short run, while an ESC in the frame heats up and runs on a sagging battery; a smaller margin, like 45 A at a 38 A peak in the f-motors-esc example, only works because the peak lasts seconds, and counts as “cutting it close”); voltage with margin (6S → an ESC rated for 6S, not “up to 6S” at the limit). 4-in-1 — compact, but one crash = replacing everything; individual ESCs — repairable, but you need to route the power. What to take (course guideline): up to and including 7" — a 4-in-1 (AIO or stack, Step 5a); individual ESCs on the arms — on 10" and larger and on an X8, where the prop airflow cools them and replacing one channel is cheaper than a board. The firmware (BLHeli_32/AM32/BLHeli_S) determines telemetry and the RPM filter.

### Step 4: battery
Capacity from current: I_avg (from the table for cruise/hover × number of motors + electronics) × t / 0.8. Chemistry: LiPo — current, Li-Ion — energy per kilogram (but low current capability: the rated continuous current of a 21700 is 3–10C per cell, and for heat the average current is kept no higher than 1.5C, `el-battery-packs`). LiPo for current (the rule — `f-power`, “Capacity and C rating”): capacity — by the average current, as above; label C × Q ≥ peak current — only a filter; the cell resistance decides: R_cell ≤ 0.5 V / I_peak. Check: does the battery mass fit the mass budget? Otherwise — iterate: heavier battery → more current → even more battery. This loop does not always converge; if it doesn't — change the class.

### Step 5: FC, receiver, video, GPS
FC: an F4 is enough for Betaflight without extras. INAV 9.1.0 works in full on an F405 (1 MB of flash; it is the most common MCU among INAV targets — 117 build targets in 88 board directories); on boards with ≤ 512 KB of flash (F411, F722) some features are disabled at build time, including geozones, and on F411 also the second mixer profile (`target/common.h`). ArduPilot 4.7.3 — H7: for 65 of 82 flight controllers on F4 (AP_Periph boards not counted) the build is trimmed by `minimize_*.inc` files (no built-in FFT, some GPS and telemetry drivers missing), for H7 — 2 of 118 (`hwdef`). With GPS, compass and logs, the number of UARTs ≥ consumers + 1; a black box (flash/SD) for log-based tuning. Receiver: ELRS, the band — by the mission (`link-elrs`, “Choosing a mode for the mission”): freestyle, racing, line of sight — 2.4 GHz; wing, forest, long routes — 900 MHz (the longer wavelength diffracts around obstacles and penetrates foliage better; the price is a longer antenna and the regulatory domain for your country, `link-elrs`, “Regulatory domains”); long-range 7–10" — 2.4 GHz 150 Hz or 900 MHz 100 Hz. Video — by the mission (`link-digital-video`, “How to choose”): racing and flying in a crowd — analog or HDZero (constant low latency, many channels), freestyle and filming — DJI or Walksnail (image and recording), long range on autopilot — digital plus a separate RC link and OSD. GPS: with a compass on a mast for INAV/ArduPilot.

### Step 5a: AIO or an FC + ESC stack
An AIO is a flight controller and a 4-in-1 ESC on one board; a stack is two boards on shared standoffs. The decision is made on four inputs, in order; the first “no” sends you to a stack.

1. **Current.** ESC continuous current ≥ 1.3 × the maximum motor current from the table (Step 3). An example AIO for 3–6S: SpeedyBee F405 AIO — 40 A continuous, 25.5 × 25.5 mm mounting, 33 × 33 mm, 13.6 g (the board's README in the ArduPilot 4.7.2 tree). So a 40 A AIO is fine as long as the motor current is no more than 40 / 1.3 ≈ 31 A.
2. **Mounting.** The board's holes match the frame. The 25.5 mm pattern is on whoops and some 3″; for 20 × 20 and 30.5 × 30.5 frames a stack is more common (estimate based on the product range as of November 2026, not verified).
3. **MCU and ports.** The Step 5 rule does not change: F4 — Betaflight; INAV — F405, F745/F765 or H7 (not F411/F722 with 512 KB of flash); ArduPilot — H7; UARTs ≥ consumers + 1. H7 AIOs exist (`MicoAir743-AIO` — an H743 and a 35 A AM32 4-in-1, it is among the ArduPilot 4.7.2 boards), but on a typical F411 AIO one or two UARTs are free (`f-micro-whoop`).
4. **Cost of failure.** A burned MOSFET in one channel means replacing the whole board together with the flight controller; with a stack only the ESC is replaced. An aircraft that crashes often (training, freestyle), with current near the limit — a stack.

| Aircraft | Motor I_max | 1.3 × I_max | Conclusion |
|---|---|---|---|
| Whoop 65–75 mm, 1–2S | a few A (estimate) | — | AIO, there is almost no choice (`f-micro-whoop`) |
| 3–3.5″, I_max ≤ 31 A | ≤ 31 A | ≤ 40 A | AIO, if the mounting matches and there are enough UARTs |
| 5″ freestyle, 2207 1750KV, 5.1×3 (`f-motors-esc`) | 38 A | 49.4 A | stack: 40 A is too little, ESC ≥ 50 A |
| 7″ long range, 2806.5 1300KV (`f-motors-esc`) | 22 A | 28.6 A | an AIO passes on current; UARTs and an H7 for ArduPilot/INAV decide — usually a stack |

How to check the choice after the first flights: the channel's peak current from the log (ESC telemetry in Blackbox or `ESC` in the ArduPilot log) is no more than the ESC continuous current divided by 1.3; if it is more — the board is running “close to the edge”, like the 45 A ESC at a 38 A peak in `f-motors-esc`.

### Step 6: mass budget and check
A table: part, mass, price. Result: takeoff mass → T/W from the motor table → hover current → flight time → comparison with the requirements. Rule: if T/W < 2 at full load — redo it. A 15% margin in the budget for props, hardware, wires, repairs.

### Trade-offs
- **Price vs mass**: cheap components are heavier; mass is flight time and current.
- **Repairability**: an aircraft built from small, available parts lives longer than an exotic one.
- **Margin**: 20% on current and thrust pays for itself on the first windy day.
- **Availability**: a part that is out of stock six months later is a problem at the first repair.

The calculator below computes T/W, hover current and flight time from your numbers — use it in step 6.

### Place in the system

- **Receives:** g/W and the thrust table for the chosen prop (`f-aero-props`); thrust and current by mode (`f-mechanics`); battery chemistry properties (`f-power`); the board's number of UARTs and BEC current (`f-fc-sensors`).
- **Provides:** a specification with a mass budget, T/W and flight time — to the requirements with IDs (`eng-method-101`); currents per rail — to the power circuit (`el-power-design`); the same loop as a calculation from a statement of work — `des-sizing`.
- **If you get it wrong here:** T/W less than 2 at full load → hovering on most of the throttle range, no margin in wind (`f-physics`, `ops-weather`). Li-Ion chosen for an average current above 1.5C per cell → the sag “eats” a cell, the voltage warning triggers earlier than calculated (`el-battery-packs`). Fewer UARTs than consumers → nowhere to connect the GPS or VTX (`bf-ports`).

## practice
{{widget:tw-calc}}

### Step 1. Requirements
A mission-in-numbers table for your own aircraft idea (as in the theory), 8–12 rows.

### Step 2. Specification
A component table: model, mass, price, a link to the data source (thrust table, datasheet). Totals for mass and price.

### Step 3. Calculation
With the calculator: T/W, hover throttle, current, flight time. Compare with the requirements, write down which ones are met.

### Step 4. Alternatives
Two options (for example, 7" Li-Ion vs 7" LiPo; or a 10" quad vs a 7" with less cargo) in one table by criteria: time, price, mass, repairability, risk. Justify the choice.

### Worked calculation
The calculator's default values: mass 1400 g, 4 motors with 1200 g of maximum thrust each, 6.5 g/W in hover, 6S 4000 mAh, electronics 0.8 A.
- T/W = 4 · 1200 / 1400 = 3.43, hover throttle ≈ 1 / 3.43 ≈ 29 % — in the linear “thrust ∝ throttle” approximation; thrust grows faster than throttle (T ∝ n²), so the real hover throttle is higher: with the `MOT_THST_EXPO = 0.65` curve — about 45 %.
- Motor power in hover: 1400 g / 6.5 g/W ≈ 215 W; current 215 / (6 · 3.7) + 0.8 ≈ 10.5 A.
- Hover on 80 % of the capacity: 4 · 0.8 / 10.5 · 60 ≈ 18 minutes. In flight with maneuvers and wind — 20–40 % less.
- Added 400 g of cargo (1800 g): T/W 2.67, throttle ≈ 54 % on the same curve (38 % — in the linear approximation; the calculator shows exactly that, i.e. the fraction of thrust, not the throttle), current 13.3 A, hover ≈ 14.5 minutes. That is the price of every gram in minutes of flight; 54 % is already the cargo band, and there is little margin left to the 65–71 % limit (T/W 2).

### What to write down and how to check yourself
- **Requirements table:** every row has a number and a unit of measurement. “Flies a long time” is not a requirement, “≥ 15 minutes of hover with a 300 g cargo” is.
- **Specification:** every component has a source for its numbers: the manufacturer's thrust table, a datasheet, weighing. A mass without wires, connectors and hardware is underestimated by 5–10 %; add this as a separate row.
- **Calculation:** note which requirements are met and which are not, and by how much. If T/W is below 2, the aircraft has no margin for wind and maneuvering — the specification changes, not the requirement.
- **Alternatives:** a table of 4–6 criteria with weights and a total. The choice is justified by numbers, not by “I like it”.

### Lab
A specification with requirements, a calculation and a comparison of two alternatives — the first document of the engineering folder.

Self-check: the lab is done when your calculation on the default values reproduces the worked one (T/W 3.43, current ≈ 10.5 A, hover ≈ 18 minutes; with a 400 g cargo — 2.67, 13.3 A, ≈ 14.5 minutes), every requirement has a number and a unit, every component in the specification has a price, a mass and a data source, the mass of wires, connectors and hardware is added as a separate row (5–10 %), T/W and flight time are calculated with it included and T/W is not below 2, every requirement is marked “met” or “not met, by how much”, and the two alternatives are brought together in a table of 4–6 criteria with weights and a total, and the chosen option is the one with the higher total.

## diagnostics
- **Symptom:** the flight-time calculation doesn't converge: the battery grows, the time doesn't
  - Possible cause: the mass → current → mass loop diverges; the aircraft class is too small for the mission.
  - What to do: a bigger prop/frame or lower the requirements.
- **Symptom:** T/W is 3 on paper, but hover is above 60 % throttle (for T/W 3, 50–58 % is expected, `f-physics`)
  - Possible cause: a thrust table for a different voltage or prop; the real mass is higher.
  - What to do: reweigh, recalculate from your own table, check the voltage under load.
- **Symptom:** not enough UARTs for all the peripherals
  - Possible cause: the FC was chosen without counting the ports.
  - What to do: an FC with more UARTs or combining functions (for example, ESC telemetry on one port).
- **Symptom:** the budget is exceeded twofold
  - Possible cause: props, hardware, the charger, spare parts were not accounted for.
  - What to do: a 15–20% margin in the budget, postpone the optional (digital video) to the next iteration.

## references
- Choosing a MultiCopter Frame — ArduPilot Copter | https://ardupilot.org/copter/docs/choosing-a-frame.html | primary | A
- UIUC Propeller Database (efficiency data by diameter) | https://m-selig.ae.illinois.edu/props/propDB.html | primary | A
- ArduPilot Copter-4.7.2 hwdef SpeedyBeeF405AIO README (40 A continuous, 25.5 mm, 33 × 33 mm, 13.6 g) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_HAL_ChibiOS/hwdef/SpeedyBeeF405AIO/README.md | primary | A
- ArduPilot Copter-4.7.2 hwdef MicoAir743-AIO README (H743 + AM32 35A) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_HAL_ChibiOS/hwdef/MicoAir743-AIO/README.md | primary | A
- How to choose motors for FPV drones — Oscar Liang | https://oscarliang.com/quadcopter-motor-propeller/ | secondary | B

## checklist
- The mission is written down in numbers, not words
- The prop diameter is chosen from the required efficiency
- The motors are chosen from the thrust table: hover throttle within the band for the class (`f-physics`), KV for my cell count (`f-aero-props`)
- The battery is calculated from current and time, the mass converged
- AIO or stack chosen by current (1.3 × I_max), mounting, UARTs and cost of failure
- Two alternatives compared, the choice justified
