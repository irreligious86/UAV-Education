---
id: f-physics
title: "How a Multirotor Flies"
level: L1
readingTime: 15 min
firmware: any firmware
status: published
added: 2026-11-07
tags:
  - physics
  - mixer
related:
  - f-motors-esc
  - bf-pid-reg-in-bf
next:
  - f-power
source: content/foundation/f-physics.md
source_hash: 769a92e070fb
---

## summary
A multirotor has no control surfaces: all control is a change in motor RPM. The module explains how four (six, eight) propellers produce throttle, roll, pitch and yaw, why the props spin in different directions, what a mixer is, and why the thrust-to-weight ratio defines the character of a drone. This is the foundation on which PID, filters and all of tuning stand.

## theory
### Thrust and weight
A propeller throws air downward and gets thrust upward. To hover, the total thrust of all the motors must equal the weight. Thrust grows roughly as the square of RPM: to double the thrust, RPM has to be raised about 1.4 times.

The thrust-to-weight ratio (T/W) is the maximum thrust of all the motors divided by the takeoff weight:

- about 2:1 — the minimum for controlled flight: heavy platforms, cargo octocopters;
- 3:1–4:1 — calm long-range 7–10";
- 6:1 and above — freestyle and racing.

Whoops, 3–3.5" and cinewhoops have no line of their own here; in the “Bands by class” table below they get estimated rows: whoops, toothpicks and 3–3.5" freestyle — like 5" freestyle, cinewhoop — like long range, 3–4. A wing does not hover, and T/W for it is a different quantity: in level flight it needs a thrust of about the weight divided by the lift-to-drag ratio, i.e. less than the weight; the criterion for a wing is thrust in a climb and at cruise speed (`aero-wing`). The threshold for any class is one and the same: this list; `f-motors-esc` and `f-aero-props` take their numbers from here.

At T/W 2:1 hover takes half the thrust — that is about 65–71 % throttle (subsection below), and there is almost no margin for maneuvering and wind gusts. This is the main argument for why a heavy drone cannot be tuned like a five-inch.

### Hover throttle: what it depends on and what is normal
**Mechanism.** In hover each motor delivers a fraction of its maximum thrust f = 1 / (T/W) — this follows exactly from the force balance. The throttle u is then greater than f, because thrust grows faster than throttle: RPM is roughly proportional to throttle (the ESC applies an average voltage u·U to the motor, `f-esc-firmware`), and thrust to the square of RPM. If thrust went strictly as u², the hover throttle would be u = √f. The real curve lies between the straight line and the square. ArduPilot describes it as T = (1 − e)·u + e·u², where e is `MOT_THST_EXPO` (0.65 for a 10", 0.55–0.6 for a 5", `ap-tuning`); hence u = (−(1 − e) + √((1 − e)² + 4·e·f)) / (2·e).

The arithmetic for T/W 2.5: f = 1 / 2.5 = 0.40; by the square law u = √0.40 = 0.63; by the 0.65 curve: u = (−0.35 + √(0.35² + 4 · 0.65 · 0.40)) / (2 · 0.65) = (−0.35 + √1.1625) / 1.3 = (−0.35 + 1.078) / 1.3 = 0.56. The hover throttle is 56–63 %, even though only 40 % of the thrust is needed.

**What number the firmware shows.** Betaflight and INAV show the throttle u (`rcCommand[3]`, the average `motor`). ArduPilot (`MOT_THST_HOVER`, `CTUN.ThO`) and PX4 (`MPC_THR_HOVER`) show the thrust fraction f before linearization, i.e. ≈ 1 / (T/W) (`ap-setup-scratch`, `px4-setup-scratch`). 0.40 in ArduPilot and 40 % in Betaflight are different quantities.

| T/W | Thrust fraction f (ArduPilot, PX4) | Throttle on the 0.65 curve | Throttle by the square law |
|---|---|---|---|
| 2 | 0.50 | 65 % | 71 % |
| 2.5 | 0.40 | 56 % | 63 % |
| 3 | 0.33 | 50 % | 58 % |
| 4 | 0.25 | 41 % | 50 % |
| 6 | 0.17 | 30 % | 41 % |
| 8 | 0.125 | 25 % | 35 % |
| 10 | 0.10 | 21 % | 32 % |

With e = 0.55 the throttle is 2–3 percentage points lower than on the 0.65 curve (T/W 4: 38 % instead of 41 %).

{{diagram:chart-hover-throttle|The hover throttle lies between the thrust fraction f and the square law: at T/W 4.1 that is 24–49 %, on the 0.65 curve — 40 %; 60 % throttle is already T/W 2.25–2.8, which for a 5–7" is a stop.}}

**Bands by class.** The T/W of the classes are course guidelines from the list above (an estimate, without a source); the throttle is calculated from the table.

| Class | T/W | Hover throttle | Thrust fraction |
|---|---|---|---|
| Freestyle and racing 5" | 6 and above (racers usually higher — estimate) | no higher than 30–41 %; at T/W 8–10 — 21–35 % | no higher than 0.17 |
| Whoops 65–75 mm, toothpicks, 3–3.5" freestyle | 6 and above (estimate: the class is not in the list above, taken as for 5" freestyle) | no higher than 30–41 % | no higher than 0.17 |
| Cinematic: cinewhoop, 5" with an action camera | 3–4 (estimate: the class is not in the list above, taken as for long range) | 41–58 % | 0.25–0.33 |
| Long-range 7–10" | 3–4 | 41–58 % | 0.25–0.33 |
| Cargo, heavy, X8 | 2–2.5 | 56–71 % | 0.40–0.50 |

**Limits for any class.**
- **The limit is T/W 2** (`f-components-choice`: below it — redo the design): thrust fraction 0.5, throttle 65–71 %. Above that throttle there is no margin.
- **60 % is the course's stop criterion for the first hover of a 5–7"** (`bf-setup-scratch`, `inav-setup-scratch`): that is T/W 2.25–2.8, which for such aircraft means an error in the mass or the table. For the cargo class this is what normal looks like; its limit is 65–71 %.
- **Below 20 %** — T/W 10–25: the aircraft is very twitchy, low throttle is hard to modulate. Below 12 % (a stop in `bf-setup-scratch`) — T/W 19–69, more than any class in the table: more likely a throttle reading error.
- **Toward the end of the discharge the throttle grows.** Thrust ∝ U² (`des-sizing`): at 20.4 V instead of 22.2 V the maximum thrust is 0.84 times as much, the thrust fraction in hover is 1 / 0.84 = 1.19 times larger. The band is compared on a full battery; T/W 2.5 turns into 2.5 × 0.84 = 2.1 toward the end of the discharge.

**Check.** The median hover throttle from the log must lie within the band for its T/W, between the thrust fraction f = 1/(T/W) and √f (for T/W 4.1 from the worked example below — 24–49 %; the 0.65 curve gives a point inside the band, 40 %, not its lower bound). Above the band — the mass is larger than weighed, or the thrust table was measured at a different voltage.

### Reaction torque and rotation directions
A motor spinning up a prop simultaneously tries to turn the frame in the opposite direction — this is the reaction torque. If all the props spun the same way, the frame would rotate around the vertical axis. That is why a quadcopter has two pairs: diagonally opposite props spin the same way, neighboring ones in opposite directions. The torques cancel each other as long as the RPM is equal.

**Props in or props out: what to choose.** Both layouts cancel the reaction torque equally; the difference is where the props' leading edges throw air and debris. Betaflight defaults to props in: `yaw_motors_reversed = OFF` (`flight/mixer_init.c`, 2025.12.5); `ON` only tells the mixer that the motors are reversed: it inverts the sign of the yaw PID (and the direction in crashflip, `flight/mixer.c`), the motor numbers stay the same. The flight controller firmware does not change the actual spin direction — that is changed in the ESC (the Bluejay/AM32/BLHeli configurator or a DShot command), see `bf-motor-balance`. The trade-off according to Oscar Liang's review (updated 2024-01): props in is the familiar layout, but debris from the ground more often flies into the camera lens, and there is more prop wash; props out — debris less often gets into the camera but more often into the FC/ESC stack, branches and gate frames bounce off on contact, and whoops and micros handle better in tight turns; in turtle mode the props spin in reverse and throw dirt into the lens. The course rule: 5" and larger — the props in default (Oscar Liang: on a 5" the difference in flight is barely noticeable); whoops and micros — props out (same source: “recommended”); a ready-made BNF — as from the factory, don't change the layout. The check after choosing — the direction of each motor without props (practice) and props fitted for that layout.

{{diagram:quad-forces|Quadcopter roll and yaw: the thrust difference produces a moment about an axis, the difference in reaction torques of the CCW/CW pair produces yaw.}}

### Four control axes
- **Throttle:** all motors faster or slower at the same time.
- **Roll:** the motors on one side faster, on the other slower. Roll right — the left motors are faster.
- **Pitch:** front versus rear. Nose down (forward flight) — the rear motors are faster.
- **Yaw:** diagonal pairs. A motor spinning counterclockwise pushes the frame clockwise. To turn clockwise (viewed from above), the counterclockwise-spinning motors are sped up and the other pair slowed down. The total thrust barely changes.

Yaw is the “weakest” axis: the torque from an RPM difference is small compared with the moments from a thrust difference. That is why the drone responds more slowly in yaw and hits the motor limits more easily.

### Mixer
The flight controller computes the desired throttle, roll, pitch and yaw, and the mixer turns them into a command for each motor. For each motor this is a sum: throttle plus the roll, pitch and yaw contributions, with a sign depending on the motor's position and spin direction. The mixer is defined by the frame type (Quad X, Hex, Octo X8 etc.), and the firmware knows the signs for each type.

Hence the main rule: the motor order and spin directions in the firmware must match the real build. A swapped motor means a drone that flips over instantly on takeoff.

### Motor saturation
If some motor is already at 100% or at 0%, the mixer cannot fully execute the command. Firmware handles this differently (Betaflight — air mode and mixer scaling: air mode allows the mixer to raise throttle for the sake of control even at zero stick throttle, and when the range runs out mixer scaling shrinks the roll, pitch and yaw commands equally and shifts the throttle so that all motors stay within 0–100 % — in detail `ctl-allocation`; ArduPilot — roll/pitch priority over yaw), but you cannot cheat physics: without thrust margin there is no control.

### The mixer in numbers (Quad X, Betaflight convention)
Motor command = throttle + k_r·roll + k_p·pitch + k_y·yaw, where k is ±1 by position and spin direction. For Quad X (Betaflight numbering: 1 — rear right, 2 — front right, 3 — rear left, 4 — front left; “props in”/“props out” changes the yaw signs):

| Motor | roll | pitch | yaw |
|---|---|---|---|
| 1 rear right (CW) | −1 | +1 | −1 |
| 2 front right (CCW) | −1 | −1 | +1 |
| 3 rear left (CCW) | +1 | +1 | +1 |
| 4 front left (CW) | +1 | −1 | −1 |

(the yaw signs depend on the firmware's convention; ArduPilot uses its own numbering around the circle — always check against the frame type diagram). Example: throttle 0.5, roll command +0.1, the rest 0 → motors 1,2 = 0.4, motors 3,4 = 0.6: more thrust on the left — roll to the right. A yaw command of +0.05 → 1 = 0.45, 2 = 0.55, 3 = 0.55, 4 = 0.45: the total thrust is the same, the reaction torques are not balanced → the frame turns.

### Why yaw is weak — an estimate
The roll/pitch moment = Δthrust × lever arm (0.1–0.3 m): with Δ = 200 g (2 N) and a 0.15 m arm — 0.3 N·m. The yaw moment = the difference in the motors' reaction torques: a motor's reaction torque ≈ power/angular velocity = 150 W / (14,000 rpm ≈ 1470 rad/s) ≈ 0.1 N·m; a 30% change on a pair — ~0.06 N·m. Five times less — hence the slow yaw and the quick hit into saturation. With “props out” and tilted motors, part of the thrust works for yaw — faster, but with losses.

### Dynamics: from command to angle
Angular acceleration = moment / moment of inertia J (for a 5" J in roll ≈ 0.003–0.005 kg·m²; for a 15" X8 — 50–100 times more): 0.3 N·m / 0.004 = 75 rad/s² ≈ 4300 °/s² — that is why a 5" reaches 1000 °/s in a quarter of a second, while an X8 with the same relative thrust margin is an order of magnitude slower, and its PID gains and acceleration limits (`ATC_ACC_*_MAX`, °/s²; before ArduPilot 4.7 — `ATC_ACCEL_*_MAX`, centidegrees/s²) are different. In detail — the “Flight mechanics” module.

### Place in the system

- **Receives:** the desired throttle, roll, pitch and yaw from the controller (the signal path — `f-fc-sensors`); the maximum thrust of the motor–prop combination, from which T/W follows (`f-aero-props`).
- **Provides:** a command to each motor — the ESC executes it (`f-motors-esc`); T/W and hover throttle — to component selection (`f-components-choice`); the mixer signs — to the control allocation calculation (`ctl-allocation`).
- **If you get it wrong here:** the motor order or direction in the firmware does not match the build → a flip on takeoff, Betaflight disarms with the reason RUNAWAY (`bf-arming-safety`, tree 2 in `diag-troubleshooting`). T/W around 2:1 → in a gust a motor hits 100 %, the mixer cannot execute the command, and yaw is lost first (`ctl-allocation`).

## practice
### Lab: calculate the T/W of your build
1. Find the thrust table for your prop and voltage in the motor's datasheet: the maximum thrust of one motor, g.
2. Multiply by the number of motors — that is the maximum thrust.
3. Weigh the drone with the battery, camera and everything it carries in flight.
4. T/W = maximum thrust / takeoff weight. Write it in the drone's logbook.
5. Check against the log: the average hover throttle lies between `1 / (T/W)` and `√(1 / (T/W))` — thrust grows faster than throttle; more precisely — by the “Hover throttle” table in the theory.

### Checking directions without props
1. Remove the props.
2. On the Motors tab (Betaflight) or Motor Test (ArduPilot), spin each motor in turn at low throttle.
3. Check the number and spin direction against your firmware's frame diagram.

### Worked example and what to expect in the log
According to the manufacturer's table, a motor gives 1500 g on the chosen prop and 6S, there are four motors, the takeoff mass with the battery is 1450 g: T/W = 4 · 1500 / 1450 ≈ 4.1.

The “1 / (T/W)” estimate of the hover throttle would give ~24 %. But thrust grows faster than throttle (roughly as the square of RPM), so the real hover throttle is higher. If thrust went strictly as the square of throttle, it would be √(1 / 4.1) ≈ 49 %. In practice the hover throttle lies between these two estimates — for this example 24–49 %. On the 0.65 curve from the theory — 40 %. In Betaflight the throttle is visible in Blackbox (the average `motor` in hover); in ArduPilot `CTUN.ThO` and the learned `MOT_THST_HOVER` are the thrust fraction, for this example about 1 / 4.1 = 0.24.

### What to write down
- The source of the maximum thrust: motor model, prop, voltage, the table row. Thrust on 4S and on 6S differs severalfold, so the table must be for your voltage.
- The mass — on scales, with everything that flies: battery, camera, antennas, strap.
- T/W and the hover throttle from the log, compared with the band for your class (the “Bands by class” table). Above 65–71 % (T/W below 2) there is no margin for any class; for a 5–7" even 60 % is a reason to reweigh the aircraft and check the thrust table; below 20 % — the aircraft is very twitchy, and tuning at low throttle will be harder.
- The motor table: number, the expected direction per the frame diagram, the actual direction, an “ok” mark.

Self-check: the lab is done when the mass with the battery and the maximum thrust with its source are written down, T/W is calculated and entered in the drone's logbook, the hover throttle from the log has been compared with the range between 1/(T/W) and √(1/(T/W)) and fell within it (in the worked example — 24–49 %; if it didn't — check that the thrust table was measured for your voltage and that the mass was weighed with everything that flies), and the order and direction of all motors were checked without props and every motor has “ok” in the motor table.

## diagnostics
- **Symptom:** the drone flips over immediately on takeoff
  - Possible cause: the motor order or spin direction is wrong, the props are mounted the wrong way round.
  - What to do: without props, check each motor against the frame diagram, check the props.
- **Symptom:** the drone slowly rotates in yaw while hovering
  - Possible cause: a tilted motor, mismatched props, motors of different strength.
  - What to do: check the motor alignment, fit identical new props.
- **Symptom:** hover at more than 60–70% throttle
  - Possible cause: overload: 60 % throttle means T/W 2.25–2.8, 70 % — 1.8–2.0 (the “Hover throttle” table).
  - What to do: make it lighter, fit different props/motors, don't fly in wind.

## references
- Frame Class and Type Configuration — ArduPilot Copter | https://ardupilot.org/copter/docs/frame-type-configuration.html | primary | A
- Connect ESCs and Motors — ArduPilot Copter | https://ardupilot.org/copter/docs/connect-escs-and-motors.html | primary | A
- Copter Motors Library — ArduPilot Dev | https://ardupilot.org/dev/docs/code-overview-copter-motors-library.html | primary | A
- Betaflight 2025.12.5: flight/mixer_init.c, flight/mixer.c (`yaw_motors_reversed`, default OFF = props in) | https://github.com/betaflight/betaflight/blob/2025.12.5/src/main/flight/mixer_init.c | primary | A
- Props In vs. Props Out — Oscar Liang (updated 2024-01-06; debris and the camera, whoops — props out, 5" — the default) | https://oscarliang.com/reversed-motor-prop-rotation-quadcopter/ | secondary | B

## checklist
- I can explain how a drone rolls, pitches and yaws without control surfaces
- I know why neighboring props spin in opposite directions
- I calculated the T/W of my build and wrote it down
- I checked the motor order and direction without props
