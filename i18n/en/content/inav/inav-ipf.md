---
id: inav-ipf
title: "INAV Programming Framework"
level: L3
readingTime: 25 min
firmware: INAV 7.0+
status: published
added: 2026-11-08
tags:
  - IPF
  - logic
  - GVAR
related:
  - inav-missions
  - ap-lua
next: []
source: content/inav/inav-ipf.md
source_hash: f5b5c1bb53ac
---

## summary
INAV Programming Framework (IPF) is a way to add logic to the aircraft without Lua and without a companion computer: “if farther than 100 m, raise the VTX power”, “if the voltage is below the threshold, engage RTH”, “switch a channel on a condition”. Logic conditions run right in the firmware and work with telemetry, modes, mission waypoints and global variables. This module explains the model (condition = operation + two operands), the CLI syntax, GVARs and typical uses, including a comparison with Lua in ArduPilot.

## theory
### The model
- **Logic Condition** — one line of “code”: an operation on one or two operands, with a true/false or numeric result.
- **Operand** — a number, an RC channel, a flight parameter (distance to home, voltage, altitude, speed), a mode, another condition, a GVAR, a mission waypoint.
- **Activator** — another condition that must be true for this one to run (−1 — always).
- **GVAR** — global variables, integers from −32768 to 32767; you can read, write and increment them and use them in the servo mixer.
- **Programming PID** — four configurable controllers whose output is available as an operand.

### CLI syntax
```
logic <rule> <enabled> <activatorId> <operation> <opA type> <opA value> <opB type> <opB value> <flags>
```

Operand types: 0 — value, 1 — RC channel, 2 — flight parameter, 3 — mode, 4 — logic condition, 5 — GVAR, 6 — Programming PID, 7 — mission waypoints. Operations: comparisons (equal, greater than, less than), logical (AND, OR, NOT), arithmetic, Set/Increase/Decrease GVAR, Override Throttle Scale, Override RC Channel, Set VTX power and others.

### An example from the documentation: VTX power by distance
Condition 0: “distance to home > 100 m”. Condition 1 (activator 0): “set VTX power = 3”. Two rules — and the transmitter raises its power by itself when the aircraft is far away.

### Where IPF makes sense
- onboard automation without a second computer: VTX, lights, PINIO, servos;
- conditional actions in a mission via user actions;
- protections: switching the mode based on voltage or distance;
- instrumentation tasks: GVARs as counters and states.

### Versus Lua in ArduPilot
Lua is a full-fledged language with access to the autopilot API, but it requires an F7/H7 and memory. IPF is a set of rules without loops or functions, but it runs on F4 and is configured from the configurator. Complex logic in IPF quickly becomes unreadable; the limit is ten to twenty rules.

### Worked example: a voltage and distance protection
The task: when the voltage is < 3.5 V/cell and the distance is > 300 m, engage RTH and raise the VTX power. The rules (`logic <rule> <enabled> <activator> <op> <A type> <A> <B type> <B> <flags>`):
- 0: `cell voltage < 350` (the flight operand “average cell voltage, hundredths of a volt” against the value 350) — result true/false;
- 1: `distance to home > 300` (meters);
- 2: AND with the operands “logic condition 0” and “logic condition 1” (operand type 4), no activator → true when both are;
- 3 (activator 2): Override RC channel → the RTH mode channel to the “on” position (RTH via channel override);
- 4 (activator 1): Set VTX power = 3.
Bench test with props off: simulate the voltage (a discharged battery/adjustable bench power supply) and the distance (a GVAR instead of the real operand during the test), and watch the rule status on the configurator's Programming tab. A protection rule lives in the firmware, so its logic must be documented in the aircraft's records: a month later, “RTH turned on by itself” will be a mystery.

### Time and state: EDGE, STICKY, DELAY, TIMER, DELTA
Rules without memory “chatter”: the voltage under load dips below the threshold for a second, and RTH engages from a single throttle punch. For this IPF has operations with time and memory:
- **DELAY** — true only if condition A holds continuously for N ms. A voltage protection always goes through DELAY (for example, 3000 ms), otherwise sag on a punch will trigger it.
- **STICKY** — a latch: it turns on from A and holds until B (reset) arrives. “Once it has triggered — RTH until the pilot resets it with a switch”.
- **EDGE** — true for N ms on the rising edge of A: a single event from holding a switch.
- **TIMER** — periodically true/false: blinking lights, a pulsing buzzer.
- **DELTA** — a change in value over a short interval greater than a threshold: “a sharp drop in altitude”.

The rewritten protection: rule 0 → DELAY(3000) on top of “voltage < 350”, then STICKY, set by AND(0, 1) and reset by a switch — and only its result activates the channel override.

### Debugging
- The Programming tab shows the state and value of every rule live — it is the main debugger.
- GVARs can be shown in the OSD (GVAR 0–3 elements): you can see the state machine's state in flight and in the video recording.
- `logic` and `gvar` in the CLI print the current rules — their dump is part of `diff all`, i.e. of the backup and of git (module “CI and config versioning”).

### Limitations people trip over
Rules run in a fixed order at ~10 Hz; there are no loops, functions or strings; GVARs are integers; channel override (Override RC) conflicts with the real stick — for modes it is better to use a separate “virtual” channel. The number of rules is fixed by the firmware: 64 logic conditions, 8 GVARs, 4 Programming PIDs — the same on F4 and H7. If the logic needs “states” and history, that is a job for a companion computer.

{{diagram:inav-ipf-model|The IPF model: operands → logic conditions with activators → global variables and programming PIDs → actions.}}

## practice
### Step 1. The first pair of rules in the configurator
Programming tab: rule 0 — `Flight > Home distance (m)` greater than `100`; rule 1 — activator 0, operation `Set VTX Power`, value 3. Save, check the tab: the state of the conditions is shown live.

### Step 2. The same in the CLI
```
logic 0 1 -1 2 2 <home_distance_operand_id> 0 100 0
logic 1 1 0  <set_vtx_power_op_id> 0 3 0 0 0
save
```

Take the operation and operand numbers from the tables in the Programming Framework documentation for your version: they change between releases, so they are not hard-coded in this module.

### Step 3. GVAR as state
A rule: when a switch is flipped, increment GVAR 1 by 1; another rule — if GVAR 1 is even, turn the light on, otherwise off. That's a state machine in two lines.

### Step 4. Truth table before flight
For the protection from the worked example, write out all combinations of inputs and the expected output, then test each row on the bench (props off), substituting the real operands with GVARs that are changed by a switch:

| Voltage < 3.5 V for ≥ 3 s | Home > 300 m | Latch before this | Expected |
|---|---|---|---|
| no | no | no | nothing |
| yes | no | no | nothing (close — the pilot handles it) |
| no | yes | no | nothing |
| yes | yes | no | RTH + VTX power 3, latch is set |
| no | no | yes | RTH holds until reset by the switch |

A row that behaves differently is a bug in the rules, found on the bench rather than in the field.

### Lab
Build a protection: if the voltage is below the threshold for longer than 3 s (DELAY) **and** the distance is greater than 50 m — latch it (STICKY) and override the mode channel to the RTH position (`Override RC Channel`). Go through the truth table on the bench, test in INAV SITL, then in the field at a short distance. Submit: the `logic`/`gvar` dump, the filled-in table, an OSD video showing the GVAR state.

## diagnostics
- **Symptom:** a rule doesn't trigger
  - Possible cause: the activator is false, wrong operand type (GVAR “value 1” versus “GVAR 1”).
  - What to do: watch the live state on the Programming tab, check the types.
- **Symptom:** Set GVAR writes to the wrong variable
  - Possible cause: operand A is set to “Global Variable 1” instead of “Value 1”.
  - What to do: the GVAR index is specified as a Value.
- **Symptom:** rules broke after an INAV update
  - Possible cause: operation/operand numbers changed.
  - What to do: check against the tables for your version, rebuild the rules.
- **Symptom:** the logic has become unreadable
  - Possible cause: too many rules for IPF.
  - What to do: simplify, or move to Lua/ArduPilot.

## references
- INAV Programming Framework | https://github.com/iNavFlight/inav/blob/master/docs/Programming%20Framework.md | primary | A
- INAV Navigation — waypoint user actions | https://github.com/iNavFlight/inav/blob/master/docs/Navigation.md | primary | A

## checklist
- I understand: condition = operation + operands + activator
- The first rule works and is visible live
- GVAR is used as state
- The voltage/distance protection is built and tested
- The rules are documented along with the INAV version number
