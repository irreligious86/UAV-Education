---
id: inav-ipf
title: "INAV Programming Framework"
level: L3
readingTime: 25 min
firmware: INAV 9.1 (checked against 9.1.0)
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
source_hash: 02f9b70d2220
---

## summary
The INAV Programming Framework (IPF) is a way to add logic to the aircraft without Lua and without a companion computer: “if farther than 100 m — raise the VTX power”, “if the voltage is below a threshold — activate RTH”, “switch a channel on a condition”. Logic conditions are executed right in the firmware and work with telemetry, flight modes, mission waypoints and global variables. This module explains the model (a condition = an operation + two operands), the CLI syntax, GVARs and typical uses, including a comparison with Lua in ArduPilot.

## theory
### The model
- **Logic Condition** — one line of “code”: an operation on one or two operands, with a result that is true/false or a number.
- **Operand** — a number, an RC channel, a flight parameter (distance to home, voltage, altitude, speed), a flight mode, another condition, a GVAR, a mission waypoint.
- **Activator** — another condition that must be true for this one to be executed (−1 — always).
- **GVAR** — global variables, integers; by default the limits are −32768…32767, and the command `gvar <i> <default> <min> <max>` can widen them (they are stored as int32); they can be read, written, increased and used in the servo mixer.
- **Programming PID** — four configurable controllers whose output is available as an operand.

### CLI syntax
```
logic <rule> <enabled> <activatorId> <operation> <opA type> <opA value> <opB type> <opB value> <flags>
```

Operand types: 0 — Value, 1 — Get RC Channel, 2 — Flight, 3 — Flight Mode, 4 — Logic Condition, 5 — GVAR, 6 — Programming PID, 7 — Waypoints. Operations: comparisons (equal, greater than, lower than), logic (AND, OR, NOT), arithmetic, Set/Increase/Decrease GVAR, Override Throttle Scale, Override RC Channel, Set VTx Power Level and others. In 9.0 operations 55 (Set Gimbal Sensitivity) and 56 (Override Minimum Ground Speed) and flight operands 46–49 (minimum ground speed, wind speed and direction, relative wind offset) were appended to the lists; the old numbers did not shift. Configurator 9 also has the JavaScript Programming tab (marked as beta): JavaScript code is transpiled into the same logic conditions, so the limitations stay the same.

### The 9.1.0 numbers: how to build a `logic` line without the configurator
The numbers are taken from `programming/logic_condition.h` 9.1.0. They have not changed since 8.0.1: operations 0–54 and flight operands 0–45 are in the same places, and 9.x only appended new ones at the end. The workflow is this:
1. **Input** — a rule as a phrase: “if <quantity> <comparison> <threshold>, then <action>”.
2. **Decision** — for the quantity you choose the operand type (table 1) and the number within the type (tables 2–4). You convert the threshold into the units of the operand: 3.5 V per cell → 350, 30 m of altitude → 3000 cm. The comparison or the action is the operation number (table 5).
3. **Check** — you enter the line in the CLI, the `logic` command without arguments prints the rule back, and the Programming tab shows its live value. If the value does not look like the quantity (an altitude of 12 at 12 m of flight), the units or the operand type are mixed up.

Table 1 — operand types:

| Type | What the `value` field holds | Example |
|---|---|---|
| 0 | the number itself | `0 100` — the constant 100 |
| 1 | the RC channel number, **indexed from 1** | `1 6` — the raw value of AUX2 (channel 6), 1000–2000 µs |
| 2 | the number of a flight parameter (table 2) | `2 1` — the distance to home |
| 3 | the number of a flight mode (table 3), the value is 0/1 | `3 2` — RTH is active |
| 4 | the number of another logic condition, its value | `4 0` — the result of rule 0 |
| 5 | the GVAR number 0–7, its value | `5 1` — the contents of GVAR 1 |
| 6 | the Programming PID number 0–3, its output | `6 0` — the output of PID 0, −1000…1000 |
| 7 | the number of a waypoint parameter (table 4) | `7 6` — user action 1 is active on this leg |

Table 2 — the key flight operands (type 2), units from `logic_condition.c`:

| No. | Quantity | Unit | No. | Quantity | Unit |
|---|---|---|---|---|---|
| 0 | time since arming | s | 14 | throttle position | % 0–100 |
| 1 | home distance | m | 15 / 16 / 40 | roll / pitch / yaw (heading) | deg |
| 2 | trip distance | m | 17 | is armed | 0/1 |
| 3 | RSSI | % 0–99 | 22 | is RTH | 0/1 |
| 4 | battery voltage | 0.01 V | 23 | is landing | 0/1 |
| 5 | average cell voltage | 0.01 V | 24 | is failsafe | 0/1 |
| 6 | current | 0.01 A | 28 | 3D home distance | m |
| 7 | current drawn | mAh | 29 / 44 | LQ uplink / downlink | % |
| 8 | GPS sats | pcs | 31 | GPS valid 3D fix | 0/1 |
| 9 | ground speed | cm/s | 33 / 42 | active control / battery profile | 1–3 |
| 11 | air speed (pitot) | cm/s | 38 | active mixer profile | number |
| 12 | altitude | cm | 45 | uplink RSSI | dBm |
| 13 | vertical speed | cm/s | 47 / 48 (9.x) | wind: speed / direction | cm/s / deg, −1 = no estimate |

Table 3 — flight modes (type 3), the value is 1 while the mode is active: 0 FAILSAFE, 1 MANUAL, 2 RTH, 3 POSHOLD (LOITER on a fixed wing), 4 CRUISE, 5 ALTHOLD, 6 ANGLE, 7 HORIZON, 8 AIRMODE, 9 USER1, 10 USER2, 11 COURSE HOLD, 12 USER3, 13 USER4, 14 ACRO, 15 WP mission, 16 ANGLE HOLD. These are the framework's own numbers, and they **do not match** the mode numbers in `aux` (RTH is 10 there).

Table 4 — waypoints (type 7): 0 a mission is in progress (0/1), 1 the current waypoint index (from 1), 2 / 3 the action of the current / next waypoint, 4 the distance to the next waypoint (m), 5 the distance from the previous waypoint (m), 6–9 user action 1–4 on this leg (0/1), 10–13 user action 1–4 on the next leg. How a user action turns into PINIO is in `inav-missions` and `inav-led-pinio-beeper`.

Table 5 — operations:

| No. | Operations | How to read A and B |
|---|---|---|
| 0–3 | TRUE, `=`, `>`, `<` | comparison of A with B |
| 4–6 | LOW, MID, HIGH | A is an RC channel: < 1333, 1333–1666, > 1666 µs |
| 7–12 | AND, OR, XOR, NAND, NOR, NOT | A, B — usually type 4 (other rules) |
| 13 | STICKY | A sets the latch, B resets it |
| 14–17, 40, 43, 44 | `+`, `−`, `×`, `÷`, modulo, MIN, MAX | the result is a number; division by 0 returns A |
| 18–20 | Set / Increase / Decrease GVAR | A — the GVAR **number** as a value (type 0), B — a number |
| 21 | Set IO Port | an I²C IO expander pin 0–7, value 0/1 |
| 22 | Override Arming Safety | bypasses **all** arming checks, including throttle |
| 23, 29 | Override Throttle Scale (%), Override Throttle (µs) | B is not needed |
| 24, 26–28 | Swap Roll & Yaw, Invert Roll/Pitch/Yaw | no operands, in effect while the rule is true |
| 25, 30, 31 | VTX: power (level), band 1–5, channel 1–8 | A — the number |
| 32 | Set OSD Layout | A = 0–3 (`inav-osd-hd`) |
| 33–37 | sin, cos, tan (A in degrees, × B, with B = 0 × 500), Map Input, Map Output | scaling 0…B ↔ 0…1000 |
| 38 | Override RC Channel | A — the channel number as a value, B — µs |
| 39, 41, 42 | Heading target (degrees, 0–359), Loiter radius (cm), Control profile 1–3 | A — the quantity |
| 45, 46 | Flight Axis Angle / Rate Override | A — the axis 0/1/2, B — deg or deg/s |
| 47–50 | EDGE, DELAY, TIMER, DELTA | time in ms, DELTA — the change within 100 ms |
| 51 | ≈ (B within 1 % of A) | |
| 52 | LED Pin PWM 0–100 % | `inav-led-pinio-beeper` |
| 53, 54 | disable the GPS sensor fix (a test), mag calibration | |
| 55, 56 (9.x) | gimbal sensitivity −16…15, minimum ground speed (m/s) | |

The last field of a `logic` line is the flags: 0 — an ordinary rule, 1 — latch: a rule that has once become true is no longer re-evaluated and stays true until the next arm or disarm, when the firmware resets the state of all rules (`fc_core.c`). The exception is the activator: while it is false (and while the CLI is open), the value of the rule is 0, and re-evaluation does not resume until the reset, so put a latch on a rule without an activator (−1). A latch that has to be released with a switch in flight is the STICKY operation, not the flag.

{{diagram:inav-logic-line-fields|The nine fields of a logic line on the example of step 2: the activator of rule 1 is the number of rule 0, the threshold is written in the units of the operand (meters), and the action takes the power level as a value.}}

### Programming PID: the `pid` command
You need a controller when a rule has to hold a quantity rather than switch something on: for example, throttle by altitude for a tethered balloon or a servo angle by roll. The 9.1.0 format (`fc/cli.c`):

`pid <No. 0–3> <enabled> <setpoint type> <setpoint> <measurement type> <measurement> <P> <I> <D> <FF>`

The setpoint and the measurement are the same operands as in `logic` (table 1). The gains are integers 0–32767, and the firmware divides them by 1000: P = 500 means 0.5. The output is limited to −1000…1000 and is read by other rules as an operand of type 6. The procedure: first P (I = D = 0), watch the output on the Programming tab and check the sign — with the measurement below the setpoint the output must grow; then scale the output to the range you need with Map Output (operation 37); Map Output takes A only within 0…1000, and the negative half of the PID output is clipped to 0 — if you need it, first add 1000 and divide by 2 (operations 14 and 17), and feed it into Override RC Channel or Override Throttle. If the sign is wrong, swap the setpoint and the measurement: the command does not accept negative gains.

### Custom OSD elements and JavaScript
A GVAR value or the result of a rule is shown on the screen through `osd_custom_elements`: up to eight elements, each made of three parts (text, a value and others), visible always, by a GVAR or by a rule. The format and a worked example are in `inav-osd-hd` and are not repeated here. The same VTX example on the JavaScript Programming tab (Configurator 9.x) is written in one line: `if (inav.flight.homeDistance > 100) { inav.override.vtx.power = 3; }`. The transpiler turns it into the same two `logic` rules: after saving, compare them in the CLI with step 2 of the practice.

### The example from the documentation: VTX power by distance
Condition 0: “the distance to home > 100 m”. Condition 1 (activator 0): “set the VTX power = 3”. Two rules — and the transmitter raises its power by itself when the aircraft is far away.

### Where IPF fits
- onboard automation without a second computer: the VTX, the LED pin (operation 52), PINIO — not directly but through overriding the channel of a USER mode (operation 38, `inav-led-pinio-beeper`), servos;
- conditional actions in a mission through user actions;
- protections: switching the mode on voltage or distance;
- instrumentation tasks: GVARs as counters and states.

### Compared with Lua in ArduPilot
Lua is a full language with access to the autopilot API, but it requires an F7/H7 and memory. IPF is a set of rules without loops or functions, but it runs on an F4 and is set up from the configurator. Complex logic in IPF quickly becomes unreadable; the limit is ten to twenty rules.

### A worked example: protection by voltage and distance
The task: at a voltage < 3.5 V/cell and a distance > 300 m activate RTH and raise the VTX power. The rules (`logic <rule> <enabled> <activator> <op> <A type> <A> <B type> <B> <flags>`):
- 0: `cell voltage < 350` (the flight operand “average cell voltage, hundredths of a volt” against the value 350) — the result is true/false;
- 1: `distance to home > 300` (meters);
- 2: AND with the operands “logic condition 0” and “logic condition 1” (operand type 4), no activator → true when both are;
- 3 (activator 2): Override RC channel → the channel of the RTH mode to the “on” position (RTH through a channel override);
- 4 (activator 1): Set VTX power = 3.
The bench check without props: simulate the voltage (a discharged battery or an adjustable power supply) and the distance (a GVAR instead of the real operand at the test stage), and watch the rule status on the Programming tab of the configurator. A protection rule lives in the firmware, so its logic must be documented in the aircraft's records: a month later “RTH turned on by itself” will be a mystery.

### Time and state: EDGE, STICKY, DELAY, TIMER, DELTA
Rules without memory “bounce”: under load the voltage drops below the threshold for a second — and RTH is activated by a single throttle punch. For this IPF has operations with time and memory:
- **DELAY** — true only if condition A has held continuously for N ms. A voltage protection always goes through DELAY (for example, 3000 ms), otherwise it trips on the sag during a punch.
- **STICKY** — a latch: it turns on with A and holds until B (the reset) arrives. “Triggered once — RTH until the pilot resets it with a switch”.
- **EDGE** — true for N ms on the rising edge of A: a single event from a held switch.
- **TIMER** — periodically true/false: a blinking light, a pulsing buzzer.
- **DELTA** — a change of the value within a short interval greater than the threshold: “a sudden loss of altitude”.

The rewritten protection: rule 0 → DELAY(3000) on top of “voltage < 350”, then STICKY set by AND(0, 1) and reset by a switch — and only its result activates the channel override.

### Debugging
- The Programming tab shows the state and the value of every rule live — it is the main debugger.
- GVARs can be shown in the OSD (the GVAR 0–3 elements): you see the state of the state machine in flight and on the video recording.
- `logic` and `gvar` in the CLI print the current rules — their dump is part of `diff all`, that is, of the backup and of git (the module “CI and versioning of configs”).

### Limitations people trip over
The rules are executed in a fixed order at ~10 Hz; there are no loops, functions or strings; GVARs are integers; a channel override (Override RC) conflicts with the real stick — for modes a separate “virtual” channel is better. The number of rules is fixed by the firmware: 64 logic conditions, 8 GVARs, 4 Programming PIDs — the same on an F4 and an H7. If the logic needs “states” and history, that is a job for a companion computer.

{{diagram:inav-ipf-model|The IPF model: operands → logic conditions with activators → global variables and programming PIDs → actions.}}

### Place in the system

- **Receives:** operands from the firmware: cell voltage, distance to home, altitude, flight modes, RC channels, mission waypoints (`inav-gps`, `inav-missions`); a calibrated battery voltage (`inav-setup-scratch`).
- **Provides:** actions: an RC channel override (for example, activating RTH), VTX power (`link-vtx`), GVARs in the OSD and in the servo mixer; the `logic` and `gvar` rules — in `diff all` and git (`eng-ci-configs`).
- **If you get it wrong here:** a voltage protection without DELAY → the sag on a throttle punch drops the voltage below the threshold for a second, and RTH activates by itself in the middle of the flight; the cause is then looked for in failsafe (`inav-setup-scratch`), not in the rules. Override RC on a channel the pilot controls → the rule conflicts with the real stick; modes need a separate “virtual” channel.

## practice
### Step 1. The first pair of rules in the configurator
The Programming tab: rule 0 — `Flight` > `Home distance [m]` greater than `100`; rule 1 — activator 0, the operation `Set VTx Power Level`, value 3. Save and check the tab: the state of the conditions is shown live.

### Step 2. The same in the CLI
```
logic 0 1 -1 2 2 1 0 100 0
logic 1 1 0 25 0 3 0 0 0
save
```

The format: `logic <rule> <enabled> <activator> <operation> <A type> <A value> <B type> <B value> <flags>`. Here operation 2 is GREATER_THAN, 25 is SET_VTX_POWER_LEVEL, flight operand 1 is the home distance (m). The numbers are checked against `programming/logic_condition.h` 9.1.0; in 8.0.1 they are the same (in 9.0 new operations and operands were only appended at the end). On another version, check the Programming Framework documentation of that version before pasting.

### Step 3. A GVAR as state
A rule: on a switch event increase GVAR 1 by 1; another rule — if GVAR 1 is even, turn the light on, otherwise off. That is a state machine in two lines.

### Step 4. A truth table before the flight
For the protection from the worked example write out all the input combinations and the expected output, then check every row on the bench (without props), replacing the real operands with GVARs that are changed with a switch:

| Voltage < 3.5 V for ≥ 3 s | Home > 300 m | Latch set before | Expected |
|---|---|---|---|
| no | no | no | nothing |
| yes | no | no | nothing (close — the pilot handles it) |
| no | yes | no | nothing |
| yes | yes | no | RTH + VTX power 3, the latch is set |
| no | no | yes | RTH holds until reset with the switch |

A row that behaves differently is an error in the rules found on the bench, not in the field.

### Lab
Build the protection: if the voltage is below the threshold for longer than 3 s (DELAY) **and** the distance is greater than 50 m — latch (STICKY) and override the mode channel to the RTH position (`Override RC Channel`). Go through the truth table on the bench, test in INAV SITL, then in the field at a short distance. Save in your repository: the `logic`/`gvar` dump, the filled-in table, an OSD video with the GVAR state. The work is done when all five rows of the truth table gave the expected output on the bench (with a 50 m threshold instead of 300 m), and the Programming tab shows the same rule states as written in the table.

**Reference for the self-check.** The correct build: DELAY(3000) on top of “voltage < threshold”, AND with the distance, STICKY set by the AND and reset by a switch — and only the latch result activates `Override RC Channel`. RTH is activated by a short sag on a throttle punch — the protection was built without DELAY. RTH turns off by itself as soon as the voltage recovers (the fifth row of the table fails) — there is no STICKY, the override hangs directly on the AND. The rule does not trigger at all — the activator is false or the operand type is mixed up (value 1 instead of GVAR 1): look at the live state on the Programming tab.

## diagnostics
- **Symptom:** a rule does not trigger
  - Possible cause: the activator is false, the wrong operand type (GVAR “value 1” versus “GVAR 1”).
  - What to do: watch the live state on the Programming tab, check the types.
- **Symptom:** Set GVAR writes to the wrong variable
  - Possible cause: operand A is “Global Variable 1” instead of “Value 1”.
  - What to do: the GVAR index is given as a Value.
- **Symptom:** after an INAV upgrade the rules broke
  - Possible cause: the operation/operand numbers changed (between 8.0.1 and 9.1.0 they did not: the new ones were appended at the end).
  - What to do: check against the tables of the version, rebuild the rules.
- **Symptom:** the logic has become unreadable
  - Possible cause: too many rules for IPF.
  - What to do: simplify or move to Lua/ArduPilot.

## references
- INAV Programming Framework | https://github.com/iNavFlight/inav/blob/master/docs/Programming%20Framework.md | primary | A
- INAV Navigation — waypoint user actions | https://github.com/iNavFlight/inav/blob/master/docs/Navigation.md | primary | A

## checklist
- I understand: a condition = an operation + operands + an activator
- The first rule works and is visible live
- A GVAR is used as state
- The voltage/distance protection is built and tested
- The rules are documented together with the INAV version number
