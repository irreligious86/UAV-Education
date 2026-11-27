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
source_hash: 36fb26239dd9
---

## summary
“How a multirotor flies” explained the principle; this module turns it into equations you can calculate with. Hover, climb, bank and turn are four force balances that give you numbers: how much thrust and current each mode needs, with what acceleration the aircraft starts moving at a 30° bank, why a heavy aircraft on long arms is “lazy” (moment of inertia and lever arm), and why you have to add throttle in a bank to hold altitude. Everything is worked through for a 1.4 kg 7", which is then checked against the log.

## theory
### Forces: Newton's second law for a drone
The forces acting on the aircraft are: the weight m·g downward, the total thrust T along the aircraft's axis (perpendicular to the prop plane), and air drag D against the velocity. Equation of motion: **m·a = T + m·g + D** (as vectors). Four modes:

**1. Hover.** a = 0, thrust is vertical: **T = m·g**. For 1.4 kg: T = 1.4 × 9.81 = 13.7 N = 1400 gf. Per motor — 350 gf. This is the very “hover throttle” you see in the log.

**2. Climb.** To accelerate upward with acceleration a: T = m·(g + a) + D. Accelerating to 3 m/s in 1 s → a = 3 m/s² → T = 1.4 × 12.8 = 17.9 N (1830 gf, +30% over hover). A steady 3 m/s climb: a = 0, you only need to compensate drag — at that speed D is small (~20 gf with the same C_d = 1.1 and A = 0.03 m² for a 7"), T ≈ m·g + D ≈ 1410–1420 gf. Conclusion: what costs a lot is *acceleration*, not climb rate. But a propeller in an ascending flow works worse (V₀ in the thrust formula grows), and the real throttle in a climb is higher than this estimate gives.

**3. Bank (or pitch) while holding altitude.** The aircraft is tilted by an angle φ, and the thrust tilts with it. The vertical component must equal the weight: T·cos φ = m·g → **T = m·g / cos φ**. The horizontal component accelerates it: m·a = T·sin φ → **a = g·tan φ**.
- φ = 30°: T = 1.155·m·g (+15.5% throttle), a = 5.7 m/s².
- φ = 45°: T = 1.41·m·g, a = 9.8 m/s² (1 g).
- φ = 60°: T = 2·m·g — a T/W of 2:1 is no longer enough to hold altitude.
This is why in Angle mode with a 60° tilt limit a drone with T/W 2:1 sinks in sharp maneuvers, and why Betaflight/INAV/ArduPilot have throttle compensation by tilt angle (e.g. `thr_corr_value` (Betaflight), `throttle_tilt_comp_str` (INAV), `ATC_ANGLE_BOOST` (ArduPilot) in different forms).

**Tilt throttle compensation: whether to enable it and how much.** It only works in self-leveling modes; in Acro no firmware has it — the pilot adds throttle in a bank. How it works according to the source code:

| Firmware | Parameter, default | What it does | Starting point |
|---|---|---|---|
| Betaflight 2025.12.5 | `thr_corr_value` 0 (off), range 0–150; `thr_corr_angle` 800 (tenths of a degree, 1–900) | only in Angle and Horizon while armed: adds to the throttle command (scale 0–1000, 1 = 0.1 % of travel) `thr_corr_value` × the sine of the tilt relative to `thr_corr_angle` (`flight/imu.c`); the addition does not depend on throttle, and per the code at `thr_corr_angle` it is about 0.6 × `thr_corr_value` | the comment in `fc/core.c`: “40 for FPV” at an angle of 45.0° — clearly too little: at a hover throttle of 40 % a 30° bank needs about +4 % of travel, and 40 gives 1.6 %; closer — about 100 with `thr_corr_angle` 450 (course estimate: 100 × 0.41 ≈ 41 units = 4.1 %) |
| INAV 9.1.0 | `throttle_tilt_comp_str` 0 (off), 0–100 % | in Angle and Horizon the throttle above idle is multiplied by 1 + (1/cos φ − 1) × str/100, cos φ is limited to 0.6 (about 53°) (`fc/fc_core.c`); in navigation modes the firmware enables 100 % by itself | course estimate: 50 — str 100 multiplies throttle, not thrust, and because thrust is nonlinear it overcompensates: at a hover throttle of 40 % and a 30° bank you need about 44 % throttle (curve 0.65, `f-physics`), str 100 gives 46 %, str 50 — 43 % |
| ArduPilot 4.7 | `ATC_ANGLE_BOOST` 1 (on) | throttle × 1/cos of the **current** body tilt (`_thrust_angle_rad` from `thrust_vector_rotation_angles()`, `AC_AttitudeControl.cpp`), cos is limited from below to 0.1; above 60° the addition smoothly decreases to zero at 90° (`inverted_factor`); in Stabilize and in altitude-holding modes, not in Acro (`AC_AttitudeControl_Multi.cpp`) | leave the default |

Course rule: Acro 5" — don't touch it (it has no effect); Angle for a beginner, cinewhoop and filming in Angle — enable it from the starting value; ArduPilot — leave it at 1. Check: in Angle, a 30° bank with the throttle stick held still — the altitude in the log (baro or GPS) or against an object of known height holds; the aircraft sinks — raise the value (in Betaflight the addition is small: 40 at a 30° bank with `thr_corr_angle` 450 gives about 1.6 % of travel, at 45° and steeper — 2.4 %, while a 30° bank at a 40 % hover throttle needs about +4 %; hence the starting point of about 100), it climbs — lower it.

**4. Turn (coordinated turn).** The centripetal acceleration v²/r comes from the horizontal component of thrust: m·v²/r = m·g·tan φ → **r = v² / (g·tan φ)**. 15 m/s at a 30° bank: r = 225 / 5.66 = 40 m. To make a 20 m radius at the same speed you need a 49° bank and throttle ×1.52.

### Air drag
**D = ½·ρ·C_d·A·v²**, ρ = 1.225 kg/m³, A — frontal area, C_d ≈ 1.0–1.3 for a “box with arms”. A 7" with a frontal area of 0.03 m² at 20 m/s: D = 0.5 × 1.225 × 1.1 × 0.03 × 400 = 8 N — more than half its weight! That is why the maximum horizontal speed is limited: at a tilt φ the drag is balanced by T·sin φ, and there is no further acceleration. Falling: at D = m·g the aircraft reaches its **terminal velocity** v_t = √(2·m·g / (ρ·C_d·A)); for our example ≈ 26 m/s — the speed at which it will hit the ground if all motors fail at a great height.

### Moments: why an aircraft is “snappy” or “lazy”
Rotation about an axis is set by the **moment M = ΔT·L**: the thrust difference between opposite motors ΔT multiplied by the lever arm L (the distance from the motor to the axis). Angular acceleration **α = M / I**, where I is the **moment of inertia** I = Σ mᵢ·rᵢ² (the mass of each part times the square of its distance to the axis).

- Mass at the ends of the arms (motors, props) is expensive: r² grows fast. 4 motors of 35 g on 15 cm arms give I = 4 × 0.035 × 0.15² ≈ 0.0032 kg·m² — the same as a 300 g battery shifted 10 cm from the center.
- A large aircraft: the lever arm L grows linearly, I — quadratically. That is why a 15" X8 turns slower than a 5" at any reasonable thrust: with ΔT = 500 gf on a 0.4 m arm M = 2 N·m, I ≈ 0.3 kg·m² → α ≈ 6.7 rad/s² (380°/s²); a 5" with M = 0.5 N·m and I = 0.004 → α = 125 rad/s² (7000°/s²). A 20× difference — hence the different PIDs and rates.
- Yaw is controlled not by thrust but by the motors' **reaction torques** (the speed difference between the CW and CCW pairs). These torques are small, and I about the vertical axis is the largest (all the masses are far from the axis), so yaw is the “laziest” axis on every multirotor, and especially on large aircraft. This is the reason for reduced D and large I-term on yaw, and for tilted motors on some frames.

### Equations as a tool
Putting it all together: for any maneuver you can estimate the thrust needed (→ current from the motor table), the acceleration and the radius. Good practice is a mode table for your own aircraft: hover / climb / 30° bank / 45° bank / maximum speed — with thrust, current and the margin to T_max. A margin of < 20% in the heaviest mode means: in a gust or on a voltage drop the aircraft will sink. Why 20 % (course guideline): thrust grows as the square of RPM, and RPM is proportional to voltage, so a 10 % pack sag under load already takes away about 19 % of the maximum thrust (0.9² = 0.81). This is a different measure from T/W ≥ 2 in `f-components-choice`: T/W is relative to the weight in hover, while the margin is relative to the thrust of the heaviest mode in the table.

{{diagram:forces-moments|Translational motion is set by forces (thrust, weight, drag), rotational motion by moments and the inertia J.}}

{{diagram:chart-tilt-thrust|The thrust needed to hold altitude in a tilt grows as 1/cos φ: at 30° you need +15.5 %, at 60° twice the weight. An aircraft with T/W = 2 physically cannot hold altitude steeper than 60°.}}

### Place in the system

- **Receives:** the control principle and T/W (`f-physics`); the motor current at the required thrust — from the thrust table (`f-aero-props`); the masses of the parts and their distances to the axis — from the mass budget (`f-components-choice`).
- **Provides:** thrust and current by mode (hover, climb, bank) — to the sag and flight-time calculation (`f-electricity-101`, `f-power`); the angular acceleration α = M/I — the explanation of why the PIDs and rates of a 5" and an X8 differ (`bf-pid-reg-in-bf`).
- **If you get it wrong here:** the thrust margin in the heaviest mode is less than 20 % → in a gust or a voltage sag the aircraft loses altitude in a bank; at the field this shows up as a hover throttle in wind above 65–71 %, i.e. T/W below 2 (the “Hover throttle” table in `f-physics`, `ops-weather`). The current is calculated only for hover → the battery capacity and flight time are overestimated (`f-power`).

## practice
### Step 1. Data
Mass m with the battery (scales), lever arm L (center → motor axis), the masses of the large parts and their distances to the center, the motor's thrust table (thrust → current).

### Step 2. Mode table
For hover, a 3 m/s² upward acceleration, a 30° and a 45° bank: T = m·g·k (k = 1, 1.31, 1.155, 1.41), thrust per motor, current from the table, margin to maximum.

### Step 3. Moments of inertia
I in roll/pitch: motors+props at L, battery and FC near the center, the frame — roughly as a ring of mass m_frame at a radius of 0.6·L. Write down I_roll, I_pitch, I_yaw (for yaw all the masses are in the horizontal plane: motors at L, battery — at the center).

### Step 4. Cross-check with the log
From the hover log: hover throttle and current. Compare the current with the calculated one from step 2 (a discrepancy > 20% — an error in mass, the table, or strong wind). From a roll log: the maximum angular acceleration from the gyro (derivative of gyro) against the estimate α = ΔT_max·L / I — the order of magnitude should match.

### Lab
A table of modes and moments of inertia for your own build, cross-checked with the log on two numbers (hover current, angular acceleration). Keep it in the build's spec sheet.

**Reference for self-check.** First check the formulas on the 1.4 kg example from the theory: hover 1400 gf (350 gf per motor), 3 m/s² upward acceleration — 1830 gf, 30° bank — ×1.155, 45° bank — ×1.41; four motors of 35 g on 15 cm arms give I ≈ 0.0032 kg·m². For your own build: the margin to maximum thrust in the heaviest mode is at least 20 %, the calculated hover current differs from the log by no more than 20 %, the angular acceleration from the log and the estimate α = ΔT_max·L / I match in order of magnitude (reference values from the theory: 5" — about 125 rad/s², a large X8 — about 6.7). Common wrong results: I came out orders of magnitude larger than the reference values — the masses were plugged in as grams and the arms as centimeters instead of kg and m; I_yaw came out smaller than I_roll — that cannot happen: about the vertical axis all the masses are farther from the axis, and this moment of inertia is the largest.

## diagnostics
- **Symptom:** in Angle mode the drone loses altitude in a sharp bank
  - Possible cause: T = m·g/cos φ exceeds the available thrust; T/W is low or the tilt limit is large.
  - What to do: limit the angle, enable tilt throttle compensation (Angle/Horizon only; starting point and check — the table in the theory), increase T/W.
- **Symptom:** a large aircraft “doesn't complete” yaw, the I-term winds up
  - Possible cause: the reaction torques are small, I_yaw is large.
  - What to do: lower your expectations of yaw rates, revisit the yaw PID, tilted motors on large frames.
- **Symptom:** after moving the battery to the edge of the frame the response became sluggish and oscillations appeared
  - Possible cause: the moment of inertia grew and the center of mass shifted.
  - What to do: mass — toward the center, retune the PID.
- **Symptom:** the hover current in the log is much higher than calculated
  - Possible cause: wrong mass, a table for a different voltage, damaged props, wind.
  - What to do: reweigh, check against the table for your voltage, inspect the props.

## references
- Multicopter Dynamics (equations of motion) — PX4 Autopilot documentation | https://docs.px4.io/v1.17/en/flight_stack/controller_diagrams.html | primary | A
- Quadrotor dynamics — Beard, "Quadrotor Dynamics and Control", BYU (PDF) | https://scholarsarchive.byu.edu/facpub/1325/ | primary | A
- Newton's laws and drag — NASA Glenn Beginner's Guide to Aeronautics | https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/ | secondary | B
- Betaflight 2025.12.5: flight/imu.c, fc/core.c (`thr_corr_value`, `thr_corr_angle`) | https://github.com/betaflight/betaflight/blob/2025.12.5/src/main/flight/imu.c | primary | A
- INAV 9.1.0: fc/fc_core.c, fc/settings.yaml (`throttle_tilt_comp_str`) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/fc_core.c | primary | A
- ArduPilot: AC_AttitudeControl_Multi.cpp (`get_throttle_boosted`, `ATC_ANGLE_BOOST`) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.3/libraries/AC_AttitudeControl/AC_AttitudeControl_Multi.cpp | primary | A

## checklist
- I can write the force balance for hover, climb, bank and turn
- I know that a bank φ needs a thrust of m·g/cos φ, and gives an acceleration of g·tan φ
- I understand why yaw is the slowest axis and why large aircraft are “lazy”
- The mode table and moments of inertia are calculated for my build
- Two numbers are cross-checked with the log
