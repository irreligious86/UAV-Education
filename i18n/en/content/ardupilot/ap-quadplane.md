---
id: ap-quadplane
title: "QuadPlane and tilt-rotor VTOL"
level: L3
readingTime: 30 min
firmware: ArduPlane 4.7 (checked against 4.7.3)
status: published
added: 2026-11-07
tags:
  - QuadPlane
  - VTOL
  - tiltrotor
related:
  - ap-heavy
  - ap-intro
  - ap-vtol-anatomy
  - ap-vtol-modes
next:
  - ap-vtol-modes
source: content/ardupilot/ap-quadplane.md
source_hash: 85e82cf5f5b4
---

## summary
A tilt-rotor VTOL takes off like a multirotor and flies like a plane, tilting its motors on the way. It is one of the most complex ArduPilot platforms: a copter mixer, a plane mixer, and a tilt mechanism all live in one aircraft. This module is written at the level of an experienced pilot and walks through a real bring-up from scratch of a HeeWing T1 Ranger tricopter wing: output assignment, an incident with a motor that spun up by itself, the limits of an F405, and a transition check on the ground. Which half of a QuadPlane is plane and which is copter, and which side to tune a symptom from, is in `ap-vtol-anatomy`; all modes, transitions, Q-assist, and the VTOL failsafes from the source and SITL are in `ap-vtol-modes`.

## theory
### QuadPlane tiltrotor configuration
- `Q_ENABLE = 1` enables the VTOL side in ArduPlane. Reboot after changing `Q_ENABLE`, `Q_FRAME_CLASS`, or `Q_FRAME_TYPE`.
- `Q_FRAME_CLASS = 7` is Tri.
- `Q_TILT_ENABLE = 1` enables tiltrotor functionality (the default is 0); while it is 0, the other `Q_TILT_*` parameters are hidden and have no effect.
- `Q_TILT_TYPE`: 0 Continuous (ordinary tilt servos), 1 Binary (only "up" or "forward"), 2 VectoredYaw (the left and right motors tilt independently and provide yaw in hover), 3 Bicopter.
- `Q_TILT_MASK` selects the motors that tilt (bit 0 is motor 1). A tricopter with two tilting front motors uses 3.
- `Q_TILT_MAX` is the tilt angle held while waiting for transition airspeed (the default of 45° suits most aircraft).
- `Q_TILT_RATE_UP` / `Q_TILT_RATE_DN` are the tilt rates in deg/s (defaults 40 and 0; `Q_TILT_RATE_DN = 0` means use `Q_TILT_RATE_UP`); a sensible start is about 15 deg/s.
- `Q_TILT_YAW_ANGLE` is for vectored yaw: how far the motors can tilt back past 90°.

### Output functions
Every output gets a role through `SERVOn_FUNCTION`:

- tricopter motors: Motor1 (33), Motor2 (34), Motor4 (36);
- tilt servos for vectored yaw: TiltMotorFrontLeft (75), TiltMotorFrontRight (76); for an ordinary tilt, TiltMotorsFront (41);
- surfaces: Elevator (19), FlaperonLeft (24), FlaperonRight (25).

Check the function numbers against the documentation for your version: the table grows, but old numbers do not change.

### The main trap: a motor on a servo channel
The outputs of a flight controller are grouped by timer. Within a group all outputs share one protocol and rate: you cannot have DShot for a motor and 50 Hz for a servo on the same timer. If the physical wiring does not match the assigned functions, one of two things happens: a servo receives "throttle" and drives against its stop, or an ESC receives a servo signal and the motor spins up with no command.

### Case: HeeWing T1 Ranger
Configuration: the stock HeeWing F405, a tilt tricopter with two tilting front motors and a fixed rear one. Project requirements: arming only from a transmitter switch, and GPS not required for arming or basic flight.

**The incident.** During a channel check one motor unexpectedly spun up to maximum. The cause was a category mismatch: motor functions had been assigned to outputs physically wired to servos, and the other way around. The project was stopped until everything had been rechecked.

**How it was sorted out.** With the props off, by hand, one output at a time, an "output → device" map was built and checked against the list of 8 devices:

1. elevator;
2. left flaperon;
3. right flaperon;
4. left nacelle tilt servo;
5. right nacelle tilt servo;
6. left tilting motor;
7. right tilting motor;
8. fixed rear motor.

After that the functions were reassigned on all 8 channels, and the motors and servos were placed in timer groups with compatible protocols.

**Hardware limits.** An F405 has no Lua scripting, and some features are cut. This build has no compass at all, and the GPS was unstable at the time of setup. So EKF3 is disabled and the DCM attitude estimate is used: the aircraft arms and flies without GPS or a compass, but with no altitude or position hold. The mode set for that decision: MANUAL, FBWA, ACRO, QSTABILIZE for takeoff, QLAND for landing. It is a deliberate trade-off for specific hardware, not a default recommendation.

{{lesson:ap-ahrs-choice|What a QuadPlane loses on DCM without GPS or a compass: there is no synthetic airspeed, so a transition in a fixed-wing mode without an airspeed sensor never completes.}}

### Transitions: the parameters that decide safety
- **Forward** (VTOL → fixed wing): in the fixed-wing modes with `Q_ENABLE` the aircraft is held by the VTOL motors until the airspeed (from the sensor or, without one, the AHRS synthetic estimate of "ground speed minus wind", which needs GPS; without GPS there is no estimate) exceeds the larger of `AIRSPEED_MIN` (the minimum fixed-wing airspeed; before 4.5 it was `ARSPD_FBW_MIN`) and `Q_ASSIST_SPEED`; after that the VTOL motor throttle ramps to zero over `Q_TRANSITION_MS` (5000 ms), which is the time after the threshold and not a timeout; the timeout is `Q_TRANS_FAIL` (`ap-vtol-modes`). The tilt motors rotate forward at `Q_TILT_RATE_DN` (0 means `Q_TILT_RATE_UP` is used, 40 deg/s). An `AIRSPEED_MIN` that is too low relative to V_s (see the "Wing aerodynamics" module) means a stall right after the transition.
- **Back** (fixed wing → VTOL): on a switch to the Q modes the VTOL motors start immediately; `Q_TRANS_DECEL` (m/s²) sets the deceleration; `Q_ASSIST_SPEED` (m/s) is the speed below which the VTOL motors assist automatically in fixed-wing modes, as protection against a stall; `Q_ASSIST_ANGLE` and `Q_ASSIST_ALT` give assistance at a large attitude error or at low altitude.
- **VTOL controllers**: `Q_A_RAT_*` (VTOL rate PIDs), `Q_A_ANG_*`, `Q_P_*` (position; in 4.7 these are `Q_P_NE_*` and `Q_P_D_*` instead of the 4.6 `Q_P_POSXY/VELXY/POSZ/VELZ/ACCZ_*`), `Q_M_THST_HOVER`, `Q_M_SPIN_MIN/ARM`, `Q_WVANE_*` (weathervaning into the wind). QAUTOTUNE is for the VTOL side; TECS, `RLL_RATE_*`/`PTCH_RATE_*` (the fixed-wing rate PIDs), and `RLL2SRV_*`/`PTCH2SRV_*` (`TCONST`, `RMAX`) are for the wing.
- **Landing**: `Q_LAND_FINAL_SPD` (m/s), `Q_LAND_FINAL_ALT`; with `Q_RTL_MODE` 1–3 an RTL changes to QRTL near home and lands vertically, or `RTL_AUTOLAND` takes it into the mission's landing sequence; you cannot have both at once (arming fails with "unset one of RTL_AUTOLAND or Q_RTL_MODE").

{{diagram:quadplane-transition|VTOL → fixed-wing transition: the VTOL motors hold the aircraft until the airspeed exceeds max(AIRSPEED_MIN, Q_ASSIST_SPEED); only then does their throttle ramp to zero over Q_TRANSITION_MS. The times are from SITL 4.7.2 (4.2 s + 5.0 s).}}

### Worked example: the first transition
The order: (1) a QSTABILIZE/QHOVER hover and QLOITER (GPS), so the VTOL side is tuned; (2) FBWA/MANUAL checked separately with a hand launch, if the design allows; (3) a transition at ≥ 60 m in FBWA with `AIRSPEED_MIN` = 1.3 V_s, `Q_ASSIST_SPEED` 3 m/s below `AIRSPEED_MIN` (5 m/s below without a sensor, per the parameter description) but not below V_s, `Q_TRANSITION_MS` 5000, and `Q_TRANS_FAIL` set (`ap-vtol-modes`); watch the airspeed (`ARSP`), the tilt angle (`RCOU`), and the altitude; (4) the back transition into QHOVER; then the log → `QTUN` (VTOL), `TECS`, `ATT`. Without an airspeed sensor the transition completes on the synthetic airspeed from GPS, so fly it only with a working GPS, with `Q_TRANS_FAIL` set, over an open area, and with altitude to spare; with neither GPS nor a sensor the transition never completes at all.

### Which VTOL to choose: 4+1, tilt-rotor, tailsitter
All three layouts run the same ArduPlane 4.7.2 firmware; the difference is in the parameters: a 4+1 has separate lift motors (`Q_ENABLE = 1`, `Q_TILT_ENABLE = 0`); a tilt-rotor has `Q_TILT_ENABLE = 1`; a tailsitter has `Q_TAILSIT_ENABLE = 1` (2 is for a vehicle with no control surfaces, stabilized by the motors only). On a 4+1 and a tilt-rotor the transition completes on airspeed: max(`AIRSPEED_MIN`, `Q_ASSIST_SPEED`), then another `Q_TRANSITION_MS` to ramp down the VTOL motor throttle (on a tilt-rotor, also until the tilt is complete); on a tailsitter it completes on pitch angle: `Q_TAILSIT_ANGLE`, 45° by default.

**Inputs** to write down before you buy a frame: (1) the share of hover in the flight; (2) the surface wind at takeoff and landing (`ops-weather`); (3) your experience with QuadPlane and your readiness for tilt mechanics; (4) what must happen on a failure: fly on the wing after a lift motor failure, or land vertically after a cruise motor failure.

The ArduPilot documentation does not compare the layouts, so the table below is an **estimate** based on how they are built:

| Layout | What you pay | What you get | Choose it if |
|---|---|---|---|
| 4+1 | the mass of the lift motors, ESCs, and booms, plus their drag for the whole cruise | two independent propulsion systems; the wing and the VTOL side are tuned separately; in the transition the cruise motor accelerates and the lift motors fade out | it is your first VTOL, the site is windy, you need to be able to land "on whatever is left" |
| tilt-rotor | tilt servos and hinges; a tilt servo failure breaks control both in hover and on the wing; the timer map is more complex (see the case above) | the same motors in hover and in cruise, so less dead mass | long cruise, mass is critical, you have already mastered a 4+1 |
| tailsitter | in hover the wing stands vertical and catches the wind with its whole area; landing in wind is the hardest phase | the fewest parts: no separate lift motors and no tilt | a small aircraft, light wind, short hover, plenty of time for tuning |

**How to check the choice with a number.** Calculate the dead mass of a 4+1 in cruise: Δm is the lift motors, ESCs, and booms. The power a plane requires is P = D·V; at constant C_L the drag is D = W/(L/D) and the speed is V ∝ √W (the L and D formulas are in `aero-wing`), so P ∝ W^1.5, and the time on the wing with the same battery changes as ((m − Δm)/m)^1.5. Example: m = 6 kg, Δm = 0.8 kg (13%) → (5.2/6)^1.5 = 0.81, that is, about −19% of cruise time. The drag of the booms is not included, so the real loss is larger. If the calculated share (81% in the example, and less once boom drag is counted) of the time of a wing without the lift group is enough for the mission, choose a 4+1: it is simpler and more reliable. If it is not enough, choose a tilt-rotor, but only after the tilt mechanics have been checked on the ground with the bring-up protocol. A tailsitter makes sense when there is little hover and the landing wind is light.

**A check before hardware.** SITL has all three layouts: `sim_vehicle.py -v ArduPlane -f quadplane`, `-f quadplane-tilttri`, `-f plane-tailsitter`. Fly a "takeoff, transition, circuit, back transition, landing" mission on each and compare the transition duration and the attitude hold in wind (`SIM_WIND_SPD`) from `QTUN` and `ATT`.

### Place in the system

- **Receives:** the boundary between the halves (`ap-vtol-anatomy`); the mission profile and the surface wind (`ops-weather`), which decide the VTOL layout; V_s for `AIRSPEED_MIN` and `Q_ASSIST_SPEED` (`aero-wing`); the attitude estimate, EKF3 or the DCM backup (`ap-ekf`); the fixed-wing tune, TECS and `RLL_RATE_*`/`PTCH_RATE_*` (`ap-plane-tuning`).
- **Provides:** the `SERVOn_FUNCTION` output roles and the "output → device" map to the copter and plane mixers; the "DCM without position" decision to the set of available modes; the `QTUN`, `TECS`, and `ATT` of the first transition to log analysis (`ap-logs`, `ap-vtol-modes`).
- **If you get it wrong here:** a motor function is assigned to an output that is physically wired to a servo, and the other way around → the ESC receives a servo signal → the motor spins up with no command: that is an injury on the bench, so check with the props off only (`f-safety`). `AIRSPEED_MIN` too low relative to V_s → a stall right after the transition (`aero-wing`).

## practice
### Bring-up protocol (props off!)
1. Save the parameters to a file.
2. Build the "output → physical device" map by hand, one output at a time.
3. Assign `SERVOn_FUNCTION` from the map. Place the motors and servos in timer groups with compatible protocols.
4. Set `Q_ENABLE`, `Q_FRAME_CLASS`, `Q_TILT_*`, then reboot.
5. Check the servo directions (`SERVOn_REVERSED`): in MANUAL the motors point forward, in QSTABILIZE they point up.
6. On the ground switch MANUAL ↔ QSTABILIZE and check that the tilt is smooth and the servos are trimmed.
7. Check the response of the surfaces and the tilt to roll, pitch, and yaw in both modes.
8. Arming only from the switch; check the failsafe.

### First flight
1. QSTABILIZE: a short, low hover; assess the yaw from vectored yaw.
2. QLAND from a low altitude.
3. Transition to a fixed-wing mode only after a confident hover, at high altitude, and with a plan ready for going back to a Q mode.

### What you should get and what to record
- **The output map** is a table made before you assign functions: "output → what is connected → expected function → protocol (PWM/DShot) → timer group". You fill it in by driving one output at a time (Motor Test, a servo tester, or `SERVOn_*` by hand), not from memory.
- **Cross-check.** Every `SERVOn_FUNCTION` matches the map. Motors on DShot and servos on PWM do not share a timer group; otherwise the protocols conflict. No output in the table may be left with a function that is not in the map.
- **Tilt on the ground.** In MANUAL the motors point forward, in QSTABILIZE they point up. The change is smooth, with no jerks and no servo driving against the mechanism; a stalled servo hums and gets hot. Record the end positions (`SERVOn_MIN/MAX/TRIM`) after setup.
- **Stick response** in both modes: in QSTABILIZE the motors answer a roll input, in MANUAL the ailerons do. Draw a "stick → what responds → which way" table for both modes.
- **Arming and failsafe.** Arming only with the switch (`ARMING_RUDDER = 0`, or per the documentation for your version); with the transmitter off the failsafe triggers, tested on the ground with the props off.

Self-check: the lab is done when the "output → device" map was built with the props off by driving one output at a time, every `SERVOn_FUNCTION` matches the map and the table has no outputs with a function outside the map, motors on DShot and servos on PWM do not share a timer group, in MANUAL the motors point forward and in QSTABILIZE up, with no jerks, binding, or servo hum, the "stick → what responds → which way" table is filled in for both modes (in QSTABILIZE the motors answer a roll input, in MANUAL the ailerons do), arming works only from the switch, and switching off the transmitter on the ground with the props off triggers the failsafe.

**Reference for the self-check.** A correct result: you can find any output in the map and explain its function, protocol, and timer group. Typical wrong results: (1) a motor spins up with no command or a servo drives against the mechanism, because a servo signal is going to an ESC (or the other way around): the function is assigned to the wrong output, so check against the map; (2) the motors tilt the wrong way, because the tilt servo reversal is not set (`SERVOn_REVERSED`).

## diagnostics
- **Symptom:** a motor spins up with no command during a check
  - Possible cause: the motor function is assigned to the wrong output, or a servo signal is going to an ESC.
  - What to do: cut the power immediately, rebuild the output map with the props off.
- **Symptom:** a servo hums and drives against its stop at power-up
  - Possible cause: the output is running a motor protocol (DShot or a high PWM rate).
  - What to do: check the timer groups and the output rates.
- **Symptom:** on switching to MANUAL the motors tilt back instead of forward
  - Possible cause: the tilt servo reversal is not set.
  - What to do: `SERVOn_REVERSED`, then check in both modes.
- **Symptom:** the aircraft holds yaw poorly in hover
  - Possible cause: `Q_TILT_YAW_ANGLE` is too small, or the left and right tilt servos are swapped.
  - What to do: check functions 75/76 and the direction of deflection on a yaw command.
- **Symptom:** a sag and a nose drop after the forward transition
  - Possible cause: `AIRSPEED_MIN` is below the real V_s, `Q_TRANSITION_MS` is too short.
  - What to do: `AIRSPEED_MIN` ≥ 1.2–1.3 V_s from the calculation, `Q_ASSIST_SPEED` not above `AIRSPEED_MIN`, transition higher.
- **Symptom:** the VTOL motors kick in during level flight
  - Possible cause: `Q_ASSIST_SPEED` is above the airspeed the mode holds (FBWB/CRUISE at low throttle hold `AIRSPEED_MIN`), or the airspeed reading is wrong.
  - What to do: calibrate the airspeed sensor; set `Q_ASSIST_SPEED` 3 m/s below `AIRSPEED_MIN` (5 m/s below without a sensor), as the parameter description advises, but not below V_s (`ap-vtol-modes`).

## references
- Tilt Rotor Planes — ArduPilot Plane | https://ardupilot.org/plane/docs/guide-tilt-rotor.html | primary | A
- Pre-Arm Safety Checks — ArduPilot | https://ardupilot.org/plane/docs/common-prearm-safety-checks.html | primary | A
- Lua Scripts (F4 limitation) — ArduPilot | https://ardupilot.org/copter/docs/common-lua-scripts.html | primary | A
- Tailsitter Planes — ArduPilot Plane (Q_TAILSIT_*; accessed 2026-11-22) | https://ardupilot.org/plane/docs/guide-tailsitter.html | primary | A
- ArduPilot Plane-4.7.2 — tailsitter.cpp, tiltrotor.cpp (Q_TAILSIT_ENABLE, Q_TAILSIT_ANGLE = 45) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/ArduPlane/tailsitter.cpp | primary | A
- ArduPilot — SITL vehicleinfo.py (the quadplane, quadplane-tilttri, and plane-tailsitter frames) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/Tools/autotest/pysim/vehicleinfo.py | primary | A

## checklist
- The "output → device" map is built by hand with the props off
- `SERVOn_FUNCTION` matches the map on every channel
- Motors and servos are in timer groups with compatible protocols
- The tilt is checked on the ground in MANUAL and QSTABILIZE
- Arming only from the switch, failsafe tested
- The hardware limits (F405, no compass) are reflected in the choice of modes
