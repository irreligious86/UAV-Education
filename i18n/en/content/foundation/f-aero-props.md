---
id: f-aero-props
title: "Propeller Aerodynamics and Powertrain Selection"
level: L2
readingTime: 30 min
firmware: any firmware
status: published
added: 2026-11-08
tags:
  - propeller
  - thrust
  - powertrain
related:
  - f-physics
  - f-motors-esc
  - f-power
next:
  - f-frame-mech
source: content/foundation/f-aero-props.md
source_hash: 6bde7a3fd984
---

## summary
The propeller is the only part that turns electricity into flight, and the only one beginners choose “by the picture”. The module gives you the physics at a level sufficient for an informed choice: where thrust comes from, why a big slow prop is more efficient than a small fast one, what pitch and efficiency are, how to read a manufacturer's thrust tables and how to pick a motor-prop-battery combination for the required T/W and flight time. With calculations on the example of a 7" and an X8.

## theory
### The actuator disk: where thrust comes from
The simplest model: the prop is a disk of area A that accelerates the air from a speed V₀ (the incoming flow) to Vₑ (behind the disk). Thrust is the change in the air's momentum per second:

{{diagram:actuator-disk|The actuator disk: thrust is the change in the flow's momentum; power grows faster than thrust.}}

**F = ½ · ρ · A · (Vₑ² − V₀²)**, where ρ is the air density (≈1.225 kg/m³ at the ground).

In hover V₀ = 0, and thrust grows with the square of the speed of the air thrown back. Consequences:

- **A big disk is more economical.** For the same thrust a big prop throws a lot of air slowly, a small one — little air fast. Kinetic energy ~ V², momentum ~ V: at equal thrust the power on the small prop is higher. That is why long-range and cargo aircraft fly on big slow props.
- **Air density matters.** In the mountains and in heat ρ is lower — thrust drops at the same RPM; an aircraft that barely hovered on the plains will not take off in the mountains.
- The model is ideal: real losses (tip vortices, blade profile drag, flow swirl) reduce the efficiency.

### Pitch, diameter and designation
“5×4.3×3” = 5" diameter, 4.3" pitch, 3 blades. **Pitch** — how far the prop “screws” into the air per revolution without slip. More pitch — more flow speed and thrust per revolution, but more torque and current. More blades — more thrust from the same diameter at the cost of efficiency.

**How to choose the pitch and the number of blades.** There is no rule of the form “pitch X for class Y”: the combination is chosen by comparison, and the procedure is the same for any class. Start — the prop from the thrust table of the chosen motor (the manufacturer measures it on recommended props) or from the course's examples: 5" freestyle — a 5.1×3 tri-blade (`f-motors-esc`), 7" long range — 7×3.5 (practice), 15" cargo — 15×5 (MN4006 table). Then compare it with a neighboring option — a pitch one step higher or lower, 2 ↔ 3 blades — on two numbers from the table or the test stand: g/W at hover thrust (flight time) and the current at full throttle (no higher than the ESC and motor ratings). The direction depends on the mission (course estimate): freestyle and racing value thrust and response from a small diameter — more blades and pitch; long range and cargo value g/W — two blades and the pitch at which g/W in hover is highest. The lab assignment is the same comparison for your own build: two prop options, the choice by numbers (in step 2 of the practice 7×4 is the fallback option to 7×3.5). The check after choosing — hover current and motor temperature (subsection “KV for the prop”, step 4 of the “Procedure”).

### Dimensionless coefficients
Manufacturers and databases (UIUC) describe a prop by:

- **Cₜ = T / (ρ·n²·D⁴)** — the thrust coefficient (n — rev/s, D — diameter, m);
- **Cₚ = P / (ρ·n³·D⁵)** — the power coefficient;
- **J = V / (n·D)** — the advance ratio (flight speed relative to prop speed);
- **η = J·Cₜ/Cₚ** — the efficiency in flight (in hover J = 0, and one speaks of the static efficiency in g/W).

The practical conclusion from the formulas: thrust ~ n², power ~ n³. **To double the thrust you need 1.41 times the RPM and 2.8 times the power.** This is exactly why “adding throttle” is so expensive in current.

### Motor + prop: the operating point
The motor sets the RPM through KV and voltage, the prop sets the load. The operating point is where the motor's torque equals the prop's drag torque. Motor manufacturers publish tables: prop, voltage, throttle → thrust (g), current (A), power (W), g/W. This is the main document for selection.

The higher the KV with the same prop, the higher the RPM, thrust and current. Overdo it — overheating of the winding and the ESC. Rule: a big prop — low KV, a small one — high; how much exactly — in the next subsection.

### KV for the prop and cell count
**Mechanism.** KV is RPM per volt with no load; under the prop's load the motor spins slower: **RPM ≈ k × KV × U**, k ≈ 0.75–0.85 at full throttle (`des-sizing`: an MN4014 330KV at 22.2 V — 7326 rpm with no load and 6000 with a 15×5 prop, k = 0.82). A prop is designed for certain RPM: thrust (∝ n²), power (∝ n³) and the blade tip speed v = π × D × n / 60 depend on it. So what you choose is not the KV but the **RPM under the prop**, and the KV follows from it: KV ≈ RPM / (k × U). For a given prop **KV × cell count is almost constant**: the same prop on 4S needs a KV 6/4 = 1.5 times higher than on 6S. An error in this direction is a classic: a motor meant for 4S spins the prop 1.5 times faster on 6S, thrust grows 2.25 times, power and current — about 3.4 times (1.5³), and that means overheating and a burned ESC; the opposite error — a sluggish aircraft hovering near its limit.

**Guidelines by class.** KV — Oscar Liang's table “Motor & Prop Sizes, KV, Battery Cell Count” (updated in July 2025); the other columns are the course's calculation with k = 0.8, U = 3.7 V × S and the middle of the KV range, i.e. an estimate.

| Prop and class | Cells | KV (Oscar Liang) | KV × S | RPM under the prop | Blade tip, m/s |
|---|---|---|---|---|---|
| 31 mm, 65 mm whoop | 1S | 23,000–30,000 | 23,000–30,000 | ≈ 78,000 | ≈ 127 |
| 40 mm, 75 mm whoop | 1S | 20,000–23,000 | 20,000–23,000 | ≈ 64,000 | ≈ 133 |
| 40 mm, 75 mm whoop | 2S | 12,000–14,000 | 24,000–28,000 | ≈ 77,000 | ≈ 161 |
| 3", freestyle | 4S | 3000–4200 | 12,000–16,800 | ≈ 43,000 | ≈ 170 |
| 3", freestyle | 6S | 2700–3000 | 16,200–18,000 | ≈ 51,000 | ≈ 202 |
| 3.5", cinewhoop | 4S | 2500–3500 | 10,000–14,000 | ≈ 36,000 | ≈ 165 |
| 3.5", cinewhoop | 6S | 1800–2500 | 10,800–15,000 | ≈ 38,000 | ≈ 178 |
| 5", freestyle | 4S | 2300–2700 | 9200–10,800 | ≈ 30,000 | ≈ 197 |
| 5", freestyle | 6S | 1700–2100 | 10,200–12,600 | ≈ 34,000 | ≈ 224 |
| 5", racing | 6S | 1900–2300 | 11,400–13,800 | ≈ 37,000 | ≈ 248 |
| 7", long range | 4S | 1600–1900 | 6400–7600 | ≈ 21,000 | ≈ 193 |
| 7", long range | 6S | 980–1300 | 5880–7800 | ≈ 20,000 | ≈ 188 |
| 7", freestyle | 6S | 1200–1400 | 7200–8400 | ≈ 23,000 | ≈ 215 |
| 10", long range | 6S | 900 | 5400 | ≈ 16,000 | ≈ 213 |
| 10", long range | 12S | 450 | 5400 | ≈ 16,000 | ≈ 213 |
| 15", long range | 12S | 250 | 3000 | ≈ 8900 | ≈ 177 |
| 15–17", cargo, per the T-Motor table | 6S | 330 (MN4014), 380 (MN4006) | 1980–2280 | 6000 with 15×5 (table) | ≈ 120 |

What the table shows. For 7" and 10", KV × S at different voltages matches — the rule works. A 5" on 6S is given slightly more RPM than on 4S (KV × S 10,200–12,600 versus 9200–10,800), so a pure 6S → 4S conversion (1700–2100 × 6/4 = 2550–3150) gives 11–17 % more than the table's 2300–2700: the conversion is a first estimate, the table and the motor's thrust table are more precise. Cargo 15–17" spin the prop noticeably slower (blade tip about 120 m/s, `des-sizing`) — for g/W, not for response.

**Where to start within the range** (course estimate): from the middle. Closer to the upper bound — racing and a light aircraft (racing 5" have a higher KV in the table than freestyle), closer to the lower bound — long range, heavy, a high-pitch prop (more torque and current per revolution, subsection “Pitch, diameter and designation”).

**Procedure.**
1. Choose the prop for the mission (g/W, subsection “Hover efficiency”).
2. From the table above, take the KV for your cell count; for an intermediate cell count, recalculate KV × S.
3. Find the thrust table of a motor with this KV **at your voltage and with your prop**: thrust in hover, maximum thrust (T/W), current in hover and at full throttle.
4. After the first flights, check:
   - the hover throttle falls within the band for your class (`f-physics`, “Hover throttle”); above the band — the KV or the prop is too small, below 20 % — the KV is too high for this mass;
   - the hover current is no higher than ~40 % of the motor's continuous current (`des-sizing`, `f-components-choice`), the full-throttle current from the log — no higher than the ESC's continuous current with a 1.3 margin (`f-components-choice`);
   - after 5 minutes of flight the motor is warm, not hot: you can hold a finger on it for longer than 5 s (`bf-setup-scratch`). Hot at a normal hover current — the KV is too high for the prop, or the prop has too much pitch.

### Hover efficiency
The static efficiency in g/W is the key indicator for flight time. Typically (course estimate; the exact number is in your motor's table): a 5" racer ~4–6 g/W in hover, 7" ~8–10, 10–15" ~10–14 (up to 15–20 at a small fraction of maximum thrust; why a 10" sometimes gets 12–15 — `f-components-choice`). The higher the g/W, the longer the hover on the same battery.

### Coaxial pairs and wings
In an X8 the lower prop works in the swirled, accelerated flow of the upper one: the total thrust of the pair is lower than twice a single prop (a guideline for the losses is 10–20%). On a wing the prop works at J > 0, and it must be chosen for the cruise speed, not for hover: the static efficiency hardly matters there. Procedure (course estimate): calculate J = V/(n·D) at cruise (V — cruise speed, n — cruise RPM from the motor table); choose a prop whose maximum η per the UIUC data falls near this J; a quick check — the pitch speed n·P is noticeably higher than V, because at J around P/D the blade's angle of attack is close to zero and thrust disappears. The check after a flight — throttle and current at cruise from the log: the better prop is the one with the lower current at the same speed.

{{diagram:chart-thrust-current|Thrust grows as the square of RPM, current as the cube: at half throttle 375 g at 5 A (3.4 g/W), at full — 1500 g at 40 A (1.7 g/W). Model T ∝ n², I ∝ n³; for a real motor — the manufacturer's thrust table.}}

### Place in the system

- **Receives:** the motor's KV and the voltage under load — they set the RPM (`f-motors-esc`, `f-power`); the required thrust by mode (`f-mechanics`); the air density at the site (`ops-weather`).
- **Provides:** thrust, current and g/W at the operating point — to the selection and the iterative sizing of the aircraft (`f-components-choice`, `des-sizing`); the hover current — to the flight-time estimate (`f-power`).
- **If you get it wrong here:** a KV too high for the chosen prop → current and heating of the winding and ESC grow, the ESC reduces power — in the log this is a “thrust drop” (`f-motors-esc`). Thrust taken from the manufacturer's table without verification → the real combination differs, T/W and flight time don't match the calculation; verified on a test stand (`des-thrust-stand`).

## practice
{{widget:tw-calc}}

### Step 1. What you need for the calculation
1. Takeoff mass m (everything that flies).
2. Target T/W (2:1 cargo, 3–4:1 long range, 6+:1 freestyle).
3. The thrust table of the motor+prop candidates at your voltage.

### Step 2. Calculation on the example of a 1.4 kg 7"
- Required hover thrust: 1400 g / 4 motors = 350 g per motor.
- T/W 3:1 → a maximum of 1050 g per motor.
- From the table for a 2806.5 1300KV motor with a 7×3.5 prop on 6S: maximum ~1200 g at ~22 A → it fits. At 350 g — about 2.5–3 A and ~55–65 W per motor (≈6 g/W; the exact number only from your motor's table).
- Hover current: 4 × 3 + 1 A for the electronics = 13 A. A 6S 4000 mAh Li-Ion battery: 0.8 × 4 / 13 × 60 ≈ 15 min of pure hover; with maneuvers and wind — 20–40% less. If that's not enough — a 7×4 prop (higher g/W on this motor) or more capacity, recalculating the weight.

### Step 3. An X8 on 4008/4006-class 380KV motors (MN4006 table)
- Mass 6 kg, eight motors, but coaxial losses of ~15%: take the effective thrust of a pair as 1.7 of a single one.
- Needed in hover: 6000 g / (4 pairs × 1.7) ≈ 880 g per motor.
- From the T-Motor MN4006 380KV table with a 15×5 CF prop at 24 V: 805 g at 3.1 A (74 W), 959 g at 4.1 A (98 W), maximum 2228 g at 15 A (T/W ≈ 2228 × 1.7 × 4 / 6000 ≈ 2.5 — enough for cargo). Interpolating to 880 g: ~3.6 A, ~86 W, ≈10 g/W, ~52% of the test-stand throttle, ~3900 rpm.
- The table was measured at 24 V, while 6S Li-Ion is 22.2 V nominal: the power for the same thrust is almost the same, the current is higher by 24 / 22.2 ≈ 1.08 times → ~3.9 A per motor.
- Hover current ≈ 8 × 3.6–3.9 ≈ 29–31 A, take ~30 A with the electronics. Li-Ion 6S 20 Ah → 0.8 × 20 / 30 × 60 ≈ 32 min.
- Self-check by g/W: 880 g / 86 W ≈ 10 — the lower end for a 15". If you got 5–6 g/W on a 15" — there is an error in the current or in the table.
- Cross-check with the real log `CTUN.ThH` and `BAT.Curr` after the first hover: a discrepancy > 20% — an error in the weight or the table.

### Step 4. Overheating check
The motor's continuous current in hover must be noticeably below its continuous rating (guideline ≤ 40 %, as in `des-sizing` and `f-components-choice`; if the manufacturer does not give a continuous current — compare with the maximum from the table, which is stricter). The check after 5 minutes of hover: the motor is warm, not hot.

### Lab
Do steps 1–3 for your own build with two prop options, choose and justify the choice with numbers; after a flight, compare the calculated hover current with the log.

**Reference for self-check.** First run your table on the 7" example from step 2: 350 g per motor in hover, a maximum of 1050 g at T/W 3:1, a hover current of 13 A, about 15 minutes on 6S 4000 mAh. If it matches — calculate your own build. A correct result: the motor's maximum thrust with the chosen prop is no less than required by the T/W, the motor current in hover is no higher than ~40 % of the continuous rating (or of the maximum from the table, if the continuous one is not given), g/W is close to the typical value for the size (5" ~4–6, 7" ~8–10, 10–15" ~10–14) or the difference is explained by your motor's table, the calculated hover current differs from the log by no more than 20 %. Common wrong results: g/W half the typical value (5–6 on a 15") — an error in the current or the wrong row of the table was taken; a discrepancy with the log of more than 20 % — a wrong weight, or the table was measured at a different voltage and the current was not recalculated (in the example — by 24 / 22.2 ≈ 1.08 times); the prop choice is “justified” by maximum thrust alone — you have to compare g/W at hover thrust, flight time depends on it.

## diagnostics
- **Symptom:** hover at more than 60% throttle
  - Possible cause: T/W too low — the prop is too small, the KV is low, or the mass has grown.
  - What to do: recalculate from the table, a prop of larger diameter/pitch, reduce the mass.
- **Symptom:** the motors are hot after a short flight
  - Possible cause: the prop is too big or has too much pitch for the KV — the current is above the continuous rating.
  - What to do: less pitch or diameter, check the hover current in the log.
- **Symptom:** flight time is half of what was calculated
  - Possible cause: the calculation was for static hover, but the flight had maneuvers; or the battery capacity is below the rating.
  - What to do: the average current from the log, check the capacity with a cycle.
- **Symptom:** it won't take off in the mountains, though it flew on the plains
  - Possible cause: lower air density — less thrust at the same RPM.
  - What to do: a prop of larger diameter/pitch or reducing the mass.

## references
- Propeller Thrust — NASA Glenn Research Center | https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/propeller-thrust/ | primary | A
- UIUC Propeller Database | https://m-selig.ae.illinois.edu/props/propDB.html | primary | A
- Lookup Table: Motor & Prop Sizes, KV, Battery Cell Count, and Weight — Oscar Liang (KV by prop and cell count; updated in July 2025, accessed 2026-11-22) | https://oscarliang.com/table-prop-motor-lipo-weight | secondary | B
- Propulsion by Propellers — MH Aerotools | https://mh-aerotools.de/airfoils/propuls4.htm | secondary | B

## checklist
- I can explain why a big slow prop is more efficient
- I know that thrust ~ n², power ~ n³
- I can read a motor's thrust table and find the hover operating point
- I chose the KV for my prop and my cell count (KV × S) and checked it against hover throttle, current and motor temperature
- I calculated the hover current and flight time for my build
- I cross-checked the calculation with the log after a flight
