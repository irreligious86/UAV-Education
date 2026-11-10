---
id: f-aero-props
title: "Propeller aerodynamics and choosing a power system"
level: L2
readingTime: 30 min
firmware: any firmware
status: published
added: 2026-11-08
tags:
  - propeller
  - thrust
  - power system
related:
  - f-physics
  - f-motors-esc
  - f-power
next:
  - f-frame-mech
source: content/foundation/f-aero-props.md
source_hash: 4d7f6bbd1213
---

## summary
The propeller is the only part that turns electricity into flight, and the only one beginners pick “by the picture.” This module gives you enough physics to choose deliberately: where thrust comes from, why a big slow prop is more efficient than a small fast one, what pitch and efficiency are, how to read a manufacturer's thrust tables and how to match a motor-prop-battery combo to the T/W and flight time you need. With worked calculations for a 7" and an X8.

## theory
### Actuator disk: where thrust comes from
The simplest model: the prop is a disk of area A that accelerates air from velocity V₀ (the incoming flow) to Vₑ (behind the disk). Thrust is the change in the air's momentum per second:

{{diagram:actuator-disk|Actuator disk: thrust is the change in the flow's momentum; power grows faster than thrust.}}

**F = ½ · ρ · A · (Vₑ² − V₀²)**, where ρ is air density (≈1.225 kg/m³ at sea level).

In hover V₀ = 0, and thrust grows with the square of the velocity of the air thrown back. Consequences:

- **A big disk pays off.** For the same thrust a big prop throws a lot of air slowly, a small one throws a little air fast. Kinetic energy ~ V², momentum ~ V: at equal thrust the small prop needs more power. That's why long-range and heavy-lift aircraft fly on big slow props.
- **Air density matters.** In the mountains and in the heat ρ is lower, so thrust drops at the same RPM; a drone that barely hovered on the plain won't take off in the mountains.
- The model is ideal: real losses (tip vortices, blade profile drag, flow swirl) reduce efficiency.

### Pitch, diameter and designation
“5×4.3×3” = 5" diameter, 4.3" pitch, 3 blades. **Pitch** is how far the prop “screws” into the air per revolution with no slip. More pitch means more flow velocity and thrust per revolution, but more torque and current. More blades means more thrust from the same diameter at the cost of efficiency.

### Dimensionless coefficients
Manufacturers and databases (UIUC) describe a prop with:

- **Cₜ = T / (ρ·n²·D⁴)**: thrust coefficient (n in rev/s, D is diameter in m);
- **Cₚ = P / (ρ·n³·D⁵)**: power coefficient;
- **J = V / (n·D)**: advance ratio (flight speed relative to prop speed);
- **η = J·Cₜ/Cₚ**: efficiency in flight (in hover J = 0, and people talk about static efficiency in g/W).

The practical takeaway from the formulas: thrust ~ n², power ~ n³. **To double thrust you need 1.41 times the RPM and 2.8 times the power.** That's exactly why “giving it more throttle” costs so much current.

### Motor + prop: the operating point
The motor sets the RPM through KV and voltage, the prop sets the load. The operating point is where motor torque equals the prop's drag torque. Motor manufacturers publish tables: prop, voltage, throttle → thrust (g), current (A), power (W), g/W. That's the main document when choosing.

The higher the KV with the same prop, the higher the RPM, thrust and current. Overdo it and you overheat the winding and the ESC. Rule of thumb: big prop, low KV (10": 300–500 KV on 6S); small prop, high KV (5": 1700–2300 KV on 6S).

### Hover efficiency
Static efficiency in g/W is the key figure for flight time. Typical values: a 5" racer ~4–6 g/W in hover, a 7" ~8–10, 10–15" ~12–20. The higher the g/W, the longer the hover on the same battery.

### Coaxial pairs and wings
In an X8 the lower prop works in the swirled, accelerated flow of the upper one: the total thrust of the pair is less than twice a single prop's (losses of 10–20% as a ballpark). On a wing the prop works at J > 0, and you have to choose it for cruise speed, not for hover: static efficiency hardly matters there.

{{diagram:chart-thrust-current|Thrust grows as the square of RPM, current as the cube: at half throttle 375 g at 5 A (3.4 g/W), at full throttle 1500 g at 40 A (1.7 g/W). Model T ∝ n², I ∝ n³; for a real motor use the manufacturer's thrust table.}}

## practice
{{widget:tw-calc}}

### Step 1. What you need for the calculation
1. Takeoff mass m (everything that flies).
2. Target T/W (2:1 heavy-lift, 3–4:1 long-range, 6+:1 freestyle).
3. The thrust table of the candidate motor+prop combos at your voltage.

### Step 2. Worked example: a 7" at 1.4 kg
- Hover thrust needed: 1400 g / 4 motors = 350 g per motor.
- T/W 3:1 → 1050 g per motor at maximum.
- From the table for a 2806.5 1300KV motor with a 7×3.5 prop on 6S: maximum ~1200 g at ~22 A → it fits. At 350 g it's about 2.5–3 A and ~55–65 W per motor (≈6 g/W; the exact number only comes from your own motor's table).
- Hover current: 4 × 3 + 1 A for the electronics = 13 A. A 6S 4000 mAh Li-Ion battery: 0.8 × 4 / 13 × 60 ≈ 15 min of pure hover; with maneuvers and wind, 20–40% less. If that's not enough, go with a 7×4 prop (higher g/W on this motor) or more capacity, recalculating the weight.

### Step 3. An X8 on 4008 380KV
- Mass 6 kg, eight motors, but coaxial losses ~15%: count the effective thrust of a pair as 1.7 times a single prop.
- Needed in hover: 6000 g / (4 pairs × 1.7) ≈ 880 g per motor.
- From the table for a 4008 380KV with a 15×5.5 prop on 6S: ~880 g at ~7 A. Hover current ≈ 56 A. Li-Ion 6S 20 Ah → 0.8 × 20 / 56 × 60 ≈ 17 min.
- Check against the real `CTUN.ThH` and `BAT.Curr` log after the first hover: a discrepancy > 20% means an error in the weight or the table.

### Step 4. Overheating check
The continuous motor current in hover should be well below the maximum in the table (aim for ≤ 40%). Check after 5 minutes of hover: the motor is warm, not hot.

### Lab
Do steps 1–3 for your own build with two prop options, pick one and justify it with numbers; after the flight, compare the calculated hover current with the log.

## diagnostics
- **Symptom:** hover throttle above 60%
  - Possible cause: T/W too low: the prop is too small, the KV too low, or the mass has grown.
  - What to do: recalculate from the table, use a prop with a larger diameter/pitch, cut the mass.
- **Symptom:** motors are hot after a short flight
  - Possible cause: the prop is too big or has too much pitch for the KV, so the current is above the continuous rating.
  - What to do: less pitch or diameter, check the hover current in the log.
- **Symptom:** flight time is half the calculated value
  - Possible cause: the calculation was for static hover, but the flight had maneuvers; or the battery capacity is below its rating.
  - What to do: take the average current from the log, check the capacity with a cycle.
- **Symptom:** won't take off in the mountains, flew fine on the plain
  - Possible cause: lower air density means less thrust at the same RPM.
  - What to do: a prop with a larger diameter/pitch or a lower mass.

## references
- Propeller Thrust — NASA Glenn Research Center | https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/propeller-thrust/ | primary | A
- UIUC Propeller Database | https://m-selig.ae.illinois.edu/props/propDB.html | primary | A
- Propulsion by Propellers — MH Aerotools | https://mh-aerotools.de/airfoils/propuls4.htm | secondary | B

## checklist
- I can explain why a big slow prop is more efficient
- I know that thrust ~ n², power ~ n³
- I can read a motor thrust table and find the hover operating point
- I calculated the hover current and flight time for my build
- I checked the calculation against the log after a flight
