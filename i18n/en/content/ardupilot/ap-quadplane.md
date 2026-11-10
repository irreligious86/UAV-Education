---
id: ap-quadplane
title: "QuadPlane and Tilt-Rotor VTOL"
level: L3
readingTime: 30 min
firmware: ArduPlane 4.5+
status: published
added: 2026-11-07
tags:
  - QuadPlane
  - VTOL
  - tiltrotor
related:
  - ap-heavy
  - ap-intro
next: []
source: content/ardupilot/ap-quadplane.md
source_hash: a9a5fbc28f71
---

## summary
A tilt-rotor VTOL takes off like a multirotor and flies like a plane, tilting its motors on the fly. It's one of the most complex ArduPilot platforms: a copter mixer, a plane mixer and the tilt mechanics all live in one aircraft. This module is written at an experienced-pilot level and walks through a real from-scratch bring-up of the HeeWing T1 Ranger tricopter wing: output assignment, an incident with a motor that spun up on its own, the limitations of the F405, and checking the transition on the ground.

## theory
### QuadPlane tiltrotor configuration
- `Q_ENABLE = 1` — enables the VTOL part in ArduPlane. After changing `Q_ENABLE`, `Q_FRAME_CLASS`, `Q_FRAME_TYPE` — reboot.
- `Q_FRAME_CLASS = 7` — tricopter.
- `Q_TILT_TYPE`: 0 — continuous (regular tilt servos), 1 — binary (only “up/forward”), 2 — vectored yaw (the left and right motors tilt independently and provide yaw in hover), 3 — bicopter.
- `Q_TILT_MASK` — which motors tilt (bit 0 — motor 1). A tricopter with two tilting front motors — 3.
- `Q_TILT_MAX` — the tilt angle while waiting for transition airspeed (the default 45° suits most).
- `Q_TILT_RATE_UP` / `Q_TILT_RATE_DN` — the tilt rate, °/s; a reasonable start is about 15°/s.
- `Q_TILT_YAW_ANGLE` — for vectored yaw: how far the motors can go beyond 90°.

### Output functions
Each output `SERVOn_FUNCTION` is assigned a role:

- tricopter motors: Motor1 (33), Motor2 (34), Motor4 (36);
- tilt servos for vectored yaw: TiltMotorFrontLeft (75), TiltMotorFrontRight (76); for regular tilt — TiltMotorsFront (41);
- surfaces: Elevator (19), FlaperonLeft (24), FlaperonRight (25).

Check the function numbers against the documentation for your version: the table grows, but old numbers don't change.

### The main trap: a motor on a servo channel
The flight controller's outputs are grouped by timers. Within a group all outputs share one protocol and rate: you can't have DShot for a motor and 50 Hz for a servo on the same timer. If the physical wiring doesn't match the assigned functions, you get one of two things: a servo receives “throttle” and slams into its stop, or an ESC receives a servo signal — and the motor spins up without a command.

### Case study: HeeWing T1 Ranger
Configuration: the stock HeeWing F405, a tilt tricopter — the two front motors tilt, the rear one is fixed. Project requirements: arm only from a radio switch, GPS not required for arming and basic flight.

**The incident.** While checking channels, one motor unexpectedly spun up to full. Cause: a category mismatch — motor functions were assigned to outputs physically connected to servos, and vice versa. The project was halted until a full recheck.

**How it was sorted out.** With props off, by hand, one output at a time, an “output → device” map was built and checked against the list of 8 devices:

1. elevator;
2. left flaperon;
3. right flaperon;
4. left nacelle tilt servo;
5. right nacelle tilt servo;
6. left tilting motor;
7. right tilting motor;
8. rear fixed motor.

After that the functions were reassigned on all 8 channels, and the motors and servos were split into timer groups with compatible protocols.

**Hardware limitations.** The F405 has no Lua scripting, and some features are cut down. This build has no compass at all, and the GPS was unstable at the time of setup. So EKF3 was disabled and DCM attitude estimation was chosen: the aircraft arms and flies without GPS and a compass, but without altitude and position hold. The set of modes for this decision: MANUAL, FBWA, ACRO, QSTABILIZE for takeoff, QLAND for landing. This is a deliberate compromise for specific hardware, not a default recommendation.

### Transitions: the parameters that determine safety
- **Forward** (VTOL → wing): in wing modes with `Q_ENABLE` the aircraft is held up by the VTOL motors until airspeed reaches `AIRSPEED_MIN` (the minimum wing airspeed; before 4.5 — `ARSPD_FBW_MIN`) or `Q_TRANSITION_MS` elapses (ms; without an airspeed sensor — by time); the tilt motors tilt at `Q_TILT_RATE_UP`. An `AIRSPEED_MIN` too small relative to V_s (the “Wing Aerodynamics” module) = a stall right after the transition.
- **Back** (wing → VTOL): when switching to Q modes the VTOL motors turn on immediately; `Q_TRANS_DECEL` (m/s²) sets the deceleration; `Q_ASSIST_SPEED` (m/s) — below this airspeed in plane modes the VTOL motors help automatically (assist) — stall protection; `Q_ASSIST_ANGLE`, `Q_ASSIST_ALT` — assist at a large bank angle / at low altitude.
- **VTOL loop**: `Q_A_RAT_*` (VTOL rate PID), `Q_A_ANG_*`, `Q_P_*` (position), `Q_M_THST_HOVER`, `Q_M_SPIN_MIN/ARM`, `Q_WVANE_*` (weathervaning into the wind). QAUTOTUNE — for the VTOL part; TECS and `PTCH2SRV_*`/`RLL2SRV_*` — for the wing.
- **Landing**: `Q_LAND_FINAL_SPD` (m/s), `Q_LAND_FINAL_ALT`; RTL as VTOL (`Q_RTL_MODE`) or plane-style with a transition to QLAND near home.

{{diagram:quadplane-transition|VTOL → wing transition: the VTOL motors hold the aircraft until AIRSPEED_MIN is reached or Q_TRANSITION_MS expires.}}

### Worked example: the first transition
Order: (1) QSTABILIZE/QHOVER hover and QLOITER (GPS) — the VTOL part is tuned; (2) FBWA/MANUAL checked separately with a toss or hand launch, if the design allows; (3) a transition at an altitude of ≥ 60 m in FBWA with `AIRSPEED_MIN` = 1.3 V_s, `Q_ASSIST_SPEED` = 1.2 V_s, `Q_TRANSITION_MS` 5000; watch airspeed (`ARSP`), tilt (`RCOU`), altitude; (4) a back transition to QHOVER; log → `QTUN` (VTOL), `TECS`, `ATT`. Without an airspeed sensor, a time-based transition is only for flying over an open field with an altitude margin.

## practice
### Bring-up protocol (props off!)
1. Save the parameters to a file.
2. Build the “output → physical device” map by hand, one output at a time.
3. Assign `SERVOn_FUNCTION` per the map. Split the motors and servos into timer groups with compatible protocols.
4. `Q_ENABLE`, `Q_FRAME_CLASS`, `Q_TILT_*` — reboot.
5. Check servo directions (`SERVOn_REVERSED`): in MANUAL the motors point forward, in QSTABILIZE — up.
6. On the ground, switch MANUAL ↔ QSTABILIZE and check that the tilt is smooth and the servos are trimmed.
7. Check the response of the surfaces and the tilt to roll, pitch and yaw in both modes.
8. Arm only from the switch, check the failsafe.

### First flight
1. QSTABILIZE: a short low hover, assess yaw from vectored yaw.
2. QLAND from a low altitude.
3. Transition to a plane mode — only after a confident hover, at a high altitude, and with a ready plan for returning to a Q mode.

### What you should get and what to write down
- **Output map** — a table made before assigning functions: “output → what's connected → expected function → protocol (PWM/DShot) → timer group.” You fill it in by sending a signal to one output at a time (Motor Test, a servo tester or `SERVOn_*` by hand), not from memory.
- **Cross-check.** Every `SERVOn_FUNCTION` matches the map. DShot motors and PWM servos don't share a timer group — otherwise the protocols conflict. The table must have no outputs left with a function that isn't on the map.
- **Tilt on the ground.** In MANUAL the motors point forward, in QSTABILIZE — up. The transition is smooth, with no jerks and no servo hitting the mechanical stop; a servo against its stop hums and heats up. Write down the end positions (`SERVOn_MIN/MAX/TRIM`) after setup.
- **Stick response** in both modes: in QSTABILIZE roll is handled by the motors, in MANUAL — by the ailerons. Draw a “stick → what responds → which direction” table for both modes.
- **Arming and failsafe.** Arming only by switch (`ARMING_RUDDER = 0` or per the documentation for your version); with the radio turned off the failsafe triggers — verified on the ground with props off.

The lab counts as done when the “output → device” map is built by hand with props off, every `SERVOn_FUNCTION` matches the map, the tilt is checked on the ground in MANUAL and QSTABILIZE, and arming works only from the switch with the failsafe verified.

## diagnostics
- **Symptom:** a motor spins up without a command during a check
  - Possible cause: the motor function is assigned to the wrong output, or a servo signal is going to an ESC.
  - What to do: cut power immediately, rebuild the output map from scratch, props off.
- **Symptom:** a servo hums and slams into its stop on power-up
  - Possible cause: the output carries a motor protocol (DShot or a high PWM rate).
  - What to do: check the timer groups and output rates.
- **Symptom:** when switching to MANUAL the motors tilt backward instead of forward
  - Possible cause: the tilt servo reversal isn't set.
  - What to do: `SERVOn_REVERSED`, check in both modes.
- **Symptom:** in hover the aircraft holds yaw poorly
  - Possible cause: `Q_TILT_YAW_ANGLE` is too small, or the left and right tilt servos are swapped.
  - What to do: check functions 75/76 and the deflection direction on a yaw command.
- **Symptom:** after the forward transition, a sink and a nose drop
  - Possible cause: `AIRSPEED_MIN` is below the real V_s, `Q_TRANSITION_MS` is too small.
  - What to do: airspeeds per the V_s calculation, a higher assist speed, transition higher.
- **Symptom:** the VTOL motors “kick in” during level flight
  - Possible cause: `Q_ASSIST_SPEED` is above cruise, or the airspeed reading is wrong.
  - What to do: calibrate the airspeed sensor, set assist 15–20% below cruise.

## references
- Tilt Rotor Planes — ArduPilot Plane | https://ardupilot.org/plane/docs/guide-tilt-rotor.html | primary | A
- Pre-Arm Safety Checks — ArduPilot | https://ardupilot.org/plane/docs/common-prearm-safety-checks.html | primary | A
- Lua Scripts (F4 limitation) — ArduPilot | https://ardupilot.org/copter/docs/common-lua-scripts.html | primary | A

## checklist
- The “output → device” map is built by hand with props off
- `SERVOn_FUNCTION` matches the map on all channels
- Motors and servos are in timer groups with compatible protocols
- The tilt is checked on the ground in MANUAL and QSTABILIZE
- Arming only from the switch, the failsafe is verified
- Hardware limitations (F405, no compass) are accounted for in the choice of modes
