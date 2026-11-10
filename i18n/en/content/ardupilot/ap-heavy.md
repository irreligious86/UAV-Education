---
id: ap-heavy
title: "Heavy Platforms: X8 and Octo"
level: L3
readingTime: 25 min
firmware: ArduPilot 4.5+
status: published
added: 2026-11-07
tags:
  - X8
  - OctaQuad
  - heavy lift
related:
  - ap-lua
  - f-physics
next:
  - ap-quadplane
source: content/ardupilot/ap-heavy.md
source_hash: ad02dbe04eab
---

## summary
An eight-motor vehicle with 15–17" props is a different beast from a five-inch quad: slow motors, huge inertia, a low thrust-to-weight ratio, and the price of a mistake is an expensive payload. This module covers the coaxial X8 layout using a build on two Tarot Ironman 650 frames as the example, thrust and vibration setup in ArduPilot, and fault-tolerance testing before the first flight with a payload.

## theory
### X8 (OctaQuad): pros and cons
An X8 has four arms with two coaxial motors on each: upper and lower, spinning in opposite directions.

- **Pros:** eight motors in a quadcopter footprint; a single motor failure does not bring the vehicle down; compact for transport.
- **Cons:** the lower prop works in the upper prop's wash, so a coaxial pair gives less thrust than two separate props. A rule-of-thumb loss is around 15% (it depends on the props and the spacing between them).

In ArduPilot this is `FRAME_CLASS = 4` (OctaQuad) and `FRAME_TYPE = 1` (X). Motor order and directions strictly follow the OctaQuad X diagram in the documentation.

### Example build
The course's training platform: two Tarot Ironman 650 frames, 8 Tarot 4008 380KV motors, 8 Flycolor 45A ESCs, 6S Li-Ion power. Low KV and big props are a bet on efficiency and flight time, not on agility. Li-Ion was chosen because of the moderate current in hover.

### Thrust and the throttle curve
- `MOT_THST_HOVER` — hover throttle; ArduPilot refines it by itself in flight. Altitude hold depends on it.
- `MOT_THST_EXPO` — thrust linearization. Big props usually need a higher value than five-inch ones.
- `MOT_SPIN_ARM` and `MOT_SPIN_MIN` — the spin when armed and the in-flight minimum: the motors should spin confidently but not lift the vehicle.
- The motor protocol `MOT_PWM_TYPE`: DShot if the ESCs support it, otherwise PWM with ESC calibration.

For starting values Mission Planner has the Initial Tune Parameters helper: it calculates the basic filters and limits from the prop size and voltage.

### Vibration
Big slow props produce low-frequency vibration that is harder to filter. With vibration the EKF starts to “drift”: in the logs you see it as rising `VIBE` and accelerometer clipping, in flight as altitude loss or IMU failure messages. The cure, in order of priority: balancing props and motors, frame stiffness, flight controller damping, and only then filters. The harmonic notch filter (`INS_HNTCH_*`) tracks the motor speed from throttle or from ESC telemetry — the counterpart of the Betaflight RPM filter.

### Fault tolerance
The main reason to go octo is to survive a motor failure. But you have to test that, not assume it: in SITL with the motor-failure applet (the Lua module), then on the real vehicle at altitude and without a payload.

### Numbers for the course platform (X8, 2×Tarot 650, 4008 380KV, 15×5.5, 6S Li-Ion, ~6 kg)
From the “Propeller Aerodynamics” module: hover ≈ 880 g of thrust per motor including coaxial losses, ~7 A per motor, 56 A for the pack; Li-Ion 6S 20 Ah → ~17 min of hover; `MOT_THST_HOVER` ≈ 0.3–0.35; `MOT_THST_EXPO` 0.65–0.7 (15"); `INS_GYRO_FILTER` ≈ 30 Hz (between 40 Hz for 10" and 20 Hz for 20"); `ATC_RAT_*_FLTD` 10; starting `ATC_RAT_RLL_P/I` 0.08, D 0.003, `ATC_ANG_RLL_P` 4.5; `ATC_ACC_R/P_MAX` ≈ 500–700 °/s² (before 4.7 — `ATC_ACCEL_R/P_MAX` in cdeg/s², 50 000–70 000; slower than a 5"); `PSC_D_ACC_P` (before 4.7 — `PSC_ACCZ_P`; in 4.7 the value is ×0.1) ≈ 0.3× the hover throttle. Arm wires 12 AWG, XT90 (the “Redundancy” module). The fundamental motor harmonic in hover is ~55–65 Hz (3400–3900 rpm) — `INS_HNTCH_*` from ESC telemetry, `INS_HNTCH_HMNCS = 7` (harmonics 1–3 up to 200 Hz), `INS_HNTCH_FREQ` at least 50.

### Motor failure: what the mixer does
`AP_MotorsMatrix::output_armed_stabilizing()` allocates roll/pitch, then yaw (with a minimum headroom of `MOT_YAW_HEADROOM`), and throttle gets what is left within `MOT_YAW_HEADROOM` (200 by default, in PWM units of yaw headroom). When one X8 motor fails, its coaxial partner and the opposite pair take the load; visually — a slight sag and a rise in `RCOU` of the neighboring channels. Test: the `motor_failure_test.lua` applet (`MOT_STOP_BITMASK`, the Scripting1 switch) first in SITL (`-f octa-quad`), then in the field at 20+ m altitude without a payload, with a spotter.

### Operating a big vehicle
The pre-arm ritual gets longer: 8 props (tightness, cracks), 8 ESCs (heat after the previous flight), the Li-Ion balancer by group, a GPS fix up to 14+ satellites, the geofence, a 30 m radius area with no people, a buzzer and a sling for carrying. Any change in mass (payload, battery) → recompute `MOT_THST_HOVER` (it will learn) and check `PSC_D_ACC_*` (before 4.7 — `PSC_ACCZ_*`). Logs — every flight; `VIBE` < 15 on big props is normal, > 30 — go looking.

{{diagram:x8-layout|X8: four arms with coaxial pairs; on a motor failure the coaxial partner and the opposite pair take the load, and the throttle headroom in hover is your margin for a failure.}}

## practice
### Step 1. SITL first
```
sim_vehicle.py -v ArduCopter -f octa-quad --console --map
```

Practice takeoff, LOITER, RTL and a motor failure before you touch the hardware.

### Step 2. Configuring the real frame
1. `FRAME_CLASS = 4`, `FRAME_TYPE = 1`, reboot.
2. With props off — Motor Test on each motor: order and direction per the OctaQuad X diagram.
3. ESC calibration (for PWM) or choosing DShot.
4. Initial Tune Parameters for the prop size and cell count.
5. Check: all props are the same model, correct direction and tightness.

### Step 3. First flights
1. A low hover in STABILIZE, then ALT_HOLD, with logging.
2. Log analysis: `VIBE` (vibration and clipping), the real hover throttle, current and battery sag.
3. Only then AUTOTUNE — one axis at a time, in calm weather.
4. The motor failure test — at altitude, without a payload, ready to take over control.

### What you should end up with and what to record
- **SITL.** The `octa-quad` frame in SITL is the same OctaQuad: eight motors, four coaxial pairs. A single motor failure (`SIM_ENGINE_FAIL` — the motor mask, `SIM_ENGINE_MUL = 0`) is survivable on an octo: the vehicle rolls, the remaining motors make up the thrust, the position holds. Record the maximum roll and the `RCOU` motor outputs before and after the failure.
- **Motor Test.** Motors go by letters A, B, C… clockwise starting from the front right. Each letter is its own motor per the OctaQuad X diagram, direction as on the diagram. The table “letter → motor → direction → ok” goes into the vehicle's logbook.
- **T/W with the coaxial correction.** The thrust of a pair is not twice the thrust of one motor: the rule-of-thumb loss is about 15 %. Example: 8 motors with 3000 g of max thrust each give 24 kg on paper and ≈ 20.4 kg with the correction; at a takeoff mass of 9 kg T/W ≈ 2.3. Without the correction you will overestimate your margin.
- **First log.** Vibration (median below 30 m/s², clipping 0), hover throttle (the learned `MOT_THST_HOVER` for this build is ≈ 0.3–0.35 by calculation; above 0.5 the thrust margin is small), battery sag at hover throttle. Compare the hover current with the calculation from the theory (~7 A per motor for the module's example).

The lab counts as done when a motor failure is practiced in SITL with the response recorded, the props-off Motor Test matches the OctaQuad X diagram, T/W is calculated with the coaxial correction, and the first log is checked for VIBE, hover throttle and battery sag.

## diagnostics
- **Symptom:** the vehicle loses altitude in ALT_HOLD for no reason
  - Possible cause: vibration, the EKF stops trusting the accelerometer.
  - What to do: look at `VIBE` and clipping in the log, balance the props and motors.
- **Symptom:** a constant yaw rotation in hover
  - Possible cause: a tilted motor or different props in the coaxial pairs.
  - What to do: check motor alignment, props of the same model and pitch.
- **Symptom:** hover throttle above 60%
  - Possible cause: overloaded once coaxial losses are taken into account.
  - What to do: recalculate T/W with the coaxial correction, lighten the vehicle.
- **Symptom:** after a motor failure the vehicle spins and loses control
  - Possible cause: insufficient thrust margin or a wrong motor order.
  - What to do: repeat the test in SITL, check Motor Test and the thrust margin.

## references
- Connect ESCs and Motors — ArduPilot Copter | https://ardupilot.org/copter/docs/connect-escs-and-motors.html | primary | A
- Frame Class and Type Configuration — ArduPilot Copter | https://ardupilot.org/copter/docs/frame-type-configuration.html | primary | A
- Motor failure test applet — ArduPilot (GitHub) | https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_Scripting/applets/motor_failure_test.md | primary | A

## checklist
- `FRAME_CLASS`/`FRAME_TYPE` match the frame, Motor Test passed with props off
- T/W calculated with the coaxial correction
- Initial Tune Parameters applied
- The first log checked for vibration and hover throttle
- Motor failure tested in SITL before the real test
