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
source_hash: c96f8d3b120a
---

## summary
A multirotor has no control surfaces: all control is changing motor RPM. This module explains how four (six, eight) propellers produce throttle, roll, pitch and yaw, why the props spin in opposite directions, what the mixer is, and why the thrust-to-weight ratio defines a drone's character. This is the foundation that PIDs, filters and all of tuning stand on.

## theory
### Thrust and weight
A propeller throws air down and gets thrust up. To hover, the total thrust of all motors must equal the weight. Thrust grows roughly as the square of RPM: to double the thrust you need to raise RPM by about 1.4×.

The thrust-to-weight ratio (T/W) is the maximum thrust of all motors divided by the takeoff weight:

- around 2:1 — the minimum for controllable flight: heavy platforms, cargo octocopters;
- 3:1–4:1 — calm long-range 7–10" builds;
- 6:1 and above — freestyle and racing.

At a 2:1 T/W, hover is at about half throttle, and there is almost no margin for maneuvering or a gust of wind. That's the main argument for why you can't tune a heavy drone like a five-inch.

### Reaction torque and spin directions
A motor spinning up a prop simultaneously tries to turn the frame the opposite way — that's reaction torque. If all props spun the same way, the frame would rotate about the vertical axis. So a quadcopter has two pairs: diagonal props spin one way, neighboring props the opposite way. The torques cancel out as long as the RPMs are equal.

{{diagram:quad-forces|Quadcopter roll and yaw: a thrust difference gives a moment about an axis, a difference in the reaction torques of the CCW/CW pairs gives yaw.}}

### The four control axes
- **Throttle:** all motors faster or slower at the same time.
- **Roll:** the motors on one side faster, on the other side slower. Roll right — the left motors speed up.
- **Pitch:** front against rear. Nose down (flying forward) — the rear motors speed up.
- **Yaw:** the diagonal pairs. A motor spinning counterclockwise pushes the frame clockwise. To turn clockwise (viewed from above), the counterclockwise-spinning motors are sped up and the other pair slowed down. Total thrust barely changes.

Yaw is the “weakest” axis: the torque from an RPM difference is small compared with the moments from a thrust difference. So in yaw the drone responds more slowly and hits the motor limits more easily.

### The mixer
The flight controller computes the desired throttle, roll, pitch and yaw, and the mixer turns them into a command for each motor. For each motor it is a sum: throttle plus the roll, pitch and yaw contributions, with a sign that depends on the motor's position and spin direction. The mixer is set by the frame type (Quad X, Hex, Octo X8, etc.), and the firmware knows the signs for each type.

Hence the main rule: the motor order and spin directions in the firmware must match the real build. A swapped motor means a drone that flips over instantly on takeoff.

### Motor saturation
If some motor is already at 100% or 0%, the mixer can't fully execute the command. Firmwares handle this differently (Betaflight — air mode and mixer scaling, ArduPilot — roll/pitch priority over yaw), but you can't cheat physics: no thrust margin, no control.

### The mixer in numbers (Quad X, Betaflight convention)
Motor command = throttle + k_r·roll + k_p·pitch + k_y·yaw, where each k is ±1 depending on position and spin direction. For Quad X (Betaflight numbering: 1 — rear right, 2 — front right, 3 — rear left, 4 — front left; “props in”/“props out” flips the yaw signs):

| Motor | roll | pitch | yaw |
|---|---|---|---|
| 1 rear right (CW) | −1 | +1 | −1 |
| 2 front right (CCW) | −1 | −1 | +1 |
| 3 rear left (CCW) | +1 | +1 | +1 |
| 4 front left (CW) | +1 | −1 | −1 |

(the yaw signs depend on the firmware's convention; ArduPilot uses its own numbering around the circle — always check against the frame type diagram). Example: throttle 0.5, roll command +0.1, everything else 0 → motors 1,2 = 0.4, motors 3,4 = 0.6: more thrust on the left — roll right. Yaw command +0.05 → 1 = 0.45, 2 = 0.55, 3 = 0.55, 4 = 0.45: the total thrust is the same, the reaction torques no longer cancel → the frame turns.

### Why yaw is weak — an estimate
Roll/pitch moment = Δthrust × lever arm (0.1–0.3 m): with Δ = 200 g (2 N) and a 0.15 m arm — 0.3 N·m. Yaw moment = the difference in the motors' reaction torques: a motor's reaction torque ≈ power/angular velocity = 150 W / (14,000 rpm ≈ 1470 rad/s) ≈ 0.1 N·m; a 30% change on a pair — ~0.06 N·m. 5 times less — hence the slow yaw and the quick hit into saturation. With “props out” and tilted motors part of the thrust works on yaw — faster, but with losses.

### Dynamics: from command to angle
Angular acceleration = moment / moment of inertia J (for a 5", J in roll ≈ 0.003–0.005 kg·m²; for a 15" X8 — 50–100 times more): 0.3 N·m / 0.004 = 75 rad/s² ≈ 4300 °/s² — that's why a 5" reaches 1000 °/s in a quarter of a second, while an X8 with the same relative thrust margin is an order of magnitude slower, and its PID gains and acceleration limits (`ATC_ACCEL_*_MAX`) are different. In detail — the “Flight Mechanics” module.

## practice
### Lab: calculate the T/W of your build
1. Find the thrust table for your prop and voltage in the motor's datasheet: the maximum thrust of one motor, g.
2. Multiply by the number of motors — that's the maximum thrust.
3. Weigh the drone with the battery, camera and everything it carries in flight.
4. T/W = maximum thrust / takeoff weight. Write it into the drone's log.
5. Check against a flight log: average hover throttle should be roughly `1 / (T/W)` (corrected for nonlinearity — thrust grows faster than throttle).

### Checking directions without props
1. Remove the props.
2. On the Motors tab (Betaflight) or in Motor Test (ArduPilot), spin each motor in turn at low throttle.
3. Check the number and spin direction against your firmware's frame diagram.

### Worked example and what to expect in the log
According to the manufacturer's table the motor gives 1500 g on the chosen prop and 6S, there are four motors, takeoff mass with battery is 1450 g: T/W = 4 · 1500 / 1450 ≈ 4.1.

The “1 / (T/W)” estimate of hover throttle would give ~24 %. But thrust grows faster than throttle (roughly as the square of RPM), so the real hover throttle is higher. If thrust followed strictly the square of throttle, it would be √(1 / 4.1) ≈ 49 %. In practice hover throttle lies between these two estimates — for this example 24–49 %. In Betaflight you see it in Blackbox (the average `motor` at hover), in ArduPilot — `CTUN.ThO` and the learned `MOT_THST_HOVER`.

### What to record
- The source of the maximum thrust: motor model, prop, voltage, the row in the table. Thrust on 4S and on 6S differs by a large factor, so the table must be for your voltage.
- The mass — on scales, with everything that flies: battery, camera, antennas, strap.
- T/W and hover throttle from the log. If hover throttle is above 60 %, there's almost no margin for maneuvering and wind; below 20 % — the aircraft is very twitchy, and tuning at low throttle will be harder.
- A motor table: number, expected direction from the frame diagram, actual direction, an “ok” mark.

The lab counts as done when the mass with battery and the maximum thrust with its source are recorded, T/W is calculated and entered into the drone's log, the hover throttle from the flight log is compared with the range between 1/(T/W) and √(1/(T/W)), and the order and direction of all motors are checked without props.

## diagnostics
- **Symptom:** the drone flips over right on takeoff
  - Possible cause: motor order or spin direction swapped, props mounted the wrong way round.
  - What to do: without props, check each motor against the frame diagram; check the props.
- **Symptom:** the drone slowly rotates in yaw while hovering
  - Possible cause: a tilted motor, mismatched props, motors of different strength.
  - What to do: check motor alignment, fit identical new props.
- **Symptom:** hover at more than 60–70% throttle
  - Possible cause: overloaded, T/W around 1.5–2.
  - What to do: lighten it, fit different props/motors, don't fly in wind.

## references
- Frame Class and Type Configuration — ArduPilot Copter | https://ardupilot.org/copter/docs/frame-type-configuration.html | primary | A
- Connect ESCs and Motors — ArduPilot Copter | https://ardupilot.org/copter/docs/connect-escs-and-motors.html | primary | A
- Copter Motors Library — ArduPilot Dev | https://ardupilot.org/dev/docs/code-overview-copter-motors-library.html | primary | A

## checklist
- I can explain how a drone rolls, pitches and yaws without control surfaces
- I know why neighboring props spin in opposite directions
- I calculated the T/W of my build and recorded it
- I checked motor order and direction without props
