---
id: f-mechanics
title: "Flight Mechanics: Forces, Moments, Equations of Motion"
level: L1
readingTime: 30 min
firmware: any firmware
status: published
added: 2026-11-08
tags:
  - mechanics
  - forces
  - moments
  - dynamics
related:
  - f-physics
  - f-aero-props
  - bf-pid-reg-in-bf
next:
  - f-aero-props
source: content/foundation/f-mechanics.md
source_hash: 18bc29e1dc9d
---

## summary
“How a multirotor flies” explained the principle; this module turns it into equations you can calculate with. Hover, climb, bank and turn are four force balances that give you numbers: how much thrust and current each mode needs, how fast the aircraft accelerates at a 30° bank, why a heavy aircraft on long arms is “lazy” (moment of inertia and lever arm), and why you have to add throttle in a bank to hold altitude. Everything comes with a calculation for a 7" at 1.4 kg, which you then check against a log.

## theory
### Forces: Newton's second law for a drone
The forces on the aircraft: weight m·g downward, total thrust T along the aircraft's axis (perpendicular to the prop plane), air drag D opposite to the velocity. The equation of motion: **m·a = T + m·g + D** (as vectors). Four modes:

**1. Hover.** a = 0, thrust is vertical: **T = m·g**. For 1.4 kg: T = 1.4 × 9.81 = 13.7 N = 1400 gf. Per motor — 350 gf. This is exactly the “hover throttle” you see in the log.

**2. Climb.** To accelerate upward at a: T = m·(g + a) + D. Accelerating to 3 m/s in 1 s → a = 3 m/s² → T = 1.4 × 12.8 = 17.9 N (1830 gf, +30% over hover). A steady 3 m/s climb: a = 0, you only need to overcome drag — at that speed D is small (~20 gf with the same C_d = 1.1 and A = 0.03 m² for a 7"), T ≈ m·g + D ≈ 1410–1420 gf. Takeaway: it's the *acceleration* that's expensive, not the climb rate. But a propeller in an upward flow works worse (V₀ in the thrust formula grows), and the real throttle in a climb is higher than this estimate gives.

**3. Bank (or pitch) while holding altitude.** The aircraft is tilted by an angle φ, and the thrust tilts with it. The vertical component must equal the weight: T·cos φ = m·g → **T = m·g / cos φ**. The horizontal component accelerates you: m·a = T·sin φ → **a = g·tan φ**.
- φ = 30°: T = 1.155·m·g (+15.5% throttle), a = 5.7 m/s².
- φ = 45°: T = 1.41·m·g, a = 9.8 m/s² (1 g).
- φ = 60°: T = 2·m·g — a 2:1 T/W is no longer enough to hold altitude.
This is why in Angle mode with a 60° tilt limit a drone with a 2:1 T/W sinks in hard maneuvers, and why Betaflight/INAV/ArduPilot have tilt-based throttle compensation (e.g. `thr_corr_value` (Betaflight), `throttle_tilt_comp_str` (INAV), `ATC_ANGLE_BOOST` (ArduPilot) in various forms).

**4. Turn (coordinated turn).** The centripetal acceleration v²/r comes from the horizontal component of thrust: m·v²/r = m·g·tan φ → **r = v² / (g·tan φ)**. 15 m/s at a 30° bank: r = 225 / 5.66 = 40 m. To make a 20 m radius at the same speed you need a 49° bank and throttle ×1.52.

### Air drag
**D = ½·ρ·C_d·A·v²**, ρ = 1.225 kg/m³, A — frontal area, C_d ≈ 1.0–1.3 for a “box with arms”. A 7" with a frontal area of 0.03 m² at 20 m/s: D = 0.5 × 1.225 × 1.1 × 0.03 × 400 = 8 N — more than half its weight! That's why maximum horizontal speed is limited: at tilt φ the drag is balanced by T·sin φ, and there is no further acceleration. Falling: when D = m·g the aircraft reaches **terminal velocity** v_t = √(2·m·g / (ρ·C_d·A)); for our example ≈ 26 m/s — the speed at which it hits the ground if all motors fail at a high altitude.

### Moments: why an aircraft is “snappy” or “lazy”
Rotation about an axis is driven by the **moment M = ΔT·L**: the thrust difference ΔT between opposite motors times the lever arm L (distance from the motor to the axis). The angular acceleration is **α = M / I**, where I is the **moment of inertia** I = Σ mᵢ·rᵢ² (each part's mass times the square of its distance to the axis).

- Mass at the arm tips (motors, props) is expensive: r² grows fast. 4 motors of 35 g on 15 cm arms give I = 4 × 0.035 × 0.15² ≈ 0.0032 kg·m² — the same as a 300 g battery shifted 10 cm from the center.
- A big aircraft: the lever arm L grows linearly, I grows quadratically. That's why a 15" X8 with any reasonable thrust rotates slower than a 5": with ΔT = 500 gf on a 0.4 m arm M = 2 N·m, I ≈ 0.3 kg·m² → α ≈ 6.7 rad/s² (380°/s²); a 5" with M = 0.5 N·m and I = 0.004 → α = 125 rad/s² (7000°/s²). A 20× difference — hence the different PIDs and rates.
- Yaw is controlled not by thrust but by the motors' **reaction torques** (the speed difference between the CW and CCW pairs). These torques are small, and I about the vertical axis is the largest (all masses are far from the axis), so yaw is the “laziest” axis on every multirotor, especially on big aircraft. This is the reason for the reduced D and large I-term on yaw, and for tilted motors on some frames.

### Equations as a tool
Putting it all together: for any maneuver you can estimate the required thrust (→ current from the motor's table), the acceleration and the radius. Good practice is a mode table for your own aircraft: hover / climb / 30° bank / 45° bank / max speed — with thrust, current and margin to T_max. A margin below 20% in the heaviest mode means: in a gust or with voltage sag the aircraft will sink.

{{diagram:forces-moments|Translational motion is set by forces (thrust, weight, drag), rotational motion by moments and the inertia J.}}

{{diagram:chart-tilt-thrust|The thrust needed to hold altitude in a tilt grows as 1/cos φ: at 30° you need +15.5 %, at 60° twice the weight. An aircraft with T/W = 2 physically cannot hold altitude steeper than 60°.}}

## practice
### Step 1. Data
Mass m with battery (scales), lever arm L (center → motor axis), the masses of the large parts and their distances to the center, the motor's thrust table (thrust → current).

### Step 2. Mode table
For hover, a 3 m/s² upward acceleration, a 30° bank and a 45° bank: T = m·g·k (k = 1, 1.31, 1.155, 1.41), thrust per motor, current from the table, margin to maximum.

### Step 3. Moments of inertia
I for roll/pitch: motors+props at L, battery and FC near the center, the frame roughly as a ring of mass m_frame at a radius of 0.6·L. Record I_roll, I_pitch, I_yaw (for yaw all masses are in the horizontal plane: motors at L, battery at the center).

### Step 4. Check against the log
From a hover log: hover throttle and current. Compare the current with the value calculated in step 2 (a discrepancy > 20% means a wrong mass, a wrong table, or strong wind). From a roll log: the maximum angular acceleration from the gyro (the derivative of gyro) against the estimate α = ΔT_max·L / I — the order of magnitude should match.

### Lab
A mode table and moments of inertia for your own build, checked against a log on two numbers (hover current, angular acceleration). Keep it in the build sheet.

## diagnostics
- **Symptom:** in Angle mode the drone loses altitude in a hard bank
  - Possible cause: T = m·g/cos φ exceeds the available thrust; T/W is low or the tilt limit is high.
  - What to do: limit the angle, enable tilt throttle compensation, increase T/W.
- **Symptom:** a big aircraft “doesn't complete” yaw, I-term winds up
  - Possible cause: reaction torques are small, I_yaw is large.
  - What to do: lower your expectations for yaw rates, revisit the yaw PID, tilt the motors on big frames.
- **Symptom:** after moving the battery to the edge of the frame the response became sluggish and oscillations appeared
  - Possible cause: the moment of inertia grew and the center of mass shifted.
  - What to do: move the mass toward the center, retune.
- **Symptom:** hover current in the log is much higher than calculated
  - Possible cause: wrong mass, a table for a different voltage, damaged props, wind.
  - What to do: reweigh, check the table for your voltage, inspect the props.

## references
- Multicopter Dynamics (equations of motion) — PX4 Autopilot documentation | https://docs.px4.io/main/en/flight_stack/controller_diagrams.html | primary | A
- Quadrotor dynamics — Beard, "Quadrotor Dynamics and Control", BYU (PDF) | https://scholarsarchive.byu.edu/facpub/1325/ | primary | A
- Newton's laws and drag — NASA Glenn Beginner's Guide to Aeronautics | https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/ | secondary | B

## checklist
- I can write the force balance for hover, climb, bank and turn
- I know that a bank of φ needs thrust m·g/cos φ and gives acceleration g·tan φ
- I understand why yaw is the slowest axis and why big aircraft are “lazy”
- The mode table and moments of inertia are calculated for my build
- Two numbers checked against a log
