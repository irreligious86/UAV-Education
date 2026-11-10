---
id: diag-troubleshooting
title: "Troubleshooting Tree: The Drone Won't Take Off"
level: L1
readingTime: 40 min
firmware: any firmware
status: published
added: 2026-11-08
tags:
  - troubleshooting
  - faults
  - decision tree
  - troubleshooting
related:
  - f-electricity-101
  - bf-failsafe
  - el-measure
  - ops-case-studies
next:
  - bf-blackbox
source: content/foundation/diag-troubleshooting.md
source_hash: c51c25408564
---

## summary
Troubleshooting is not a string of guesses but the elimination of branches of a tree, where every step is confirmed by a fact: a multimeter reading, a firmware message, a log line. This module gives you a tree for five typical situations — “won't arm,” “motors don't spin or spin wrong,” “goes crazy on throttle,” “ESC/board burns when you plug in the battery,” “loses link or video” — and a rule for adding your own cases to it. Tools: smoke stopper, multimeter, CLI `status`/pre-arm messages, Blackbox/DataFlash.

## theory
### Troubleshooting rules
1. **Fact first, hypothesis second.** The firmware almost always *tells you* what's wrong: Betaflight — `status` in the CLI (the Arming disable flags line), INAV — the Status tab and `status` in the CLI, ArduPilot — PreArm messages in the GCS. Start there, not with resoldering.
2. **One change — one test.** If you changed two parameters and it started working, you don't know which one helped, and you don't know what you broke.
3. **From cheap to expensive.** Visual inspection and the multimeter come before the oscilloscope and replacing the board.
4. **Safety at every step.** Props off for anything involving the motors. The first power-up after any soldering goes through a smoke stopper.
5. **Write down the path.** Steps with their results go into a note; the cause you found goes into the tree and into the vehicle's log.

### Tree 1. Won't arm
Read the reason: Betaflight CLI → `status` → `Arming disable flags: ...`. The CLI prints short names from `runtime_config.c` (FAILSAFE, CALIB, NO_ACC_CAL, CMS, BOOTGRACE, MOTOR_PROTO, DSHOT_TELEM, ARMSWITCH in 4.5 / ARM_SWITCH in 2025.12+); below, some flags are named as in the documentation. The most common ones:
- **RXLOSS / RX_FAILSAFE** — the receiver isn't delivering channels. → Port and protocol (UART, CRSF/SBUS, inversion for SBUS on F4), bind, receiver power (5 V with a multimeter), the Receiver tab — do the channels move?
- **THROTTLE** — throttle is above minimum. → Stick calibration in the radio, `min_check`, channel reversal.
- **ANGLE** — the vehicle is tilted more than `small_angle`. → The surface, accelerometer calibration.
- **CALIBRATING / ACC_CALIBRATION / NOGYRO** — the gyro isn't calibrated or isn't detected. → Keep it still at power-up; NOGYRO — a hardware problem or the wrong firmware target.
- **ARM_SWITCH** — the arm switch was on when power was applied. → Switch it off, then on.
- **MSP / CLI / CMS_MENU** — the configurator is connected or the OSD menu is open. → Unplug USB, exit the menu.
- **NOPREARM** — a prearm mode is configured but not activated.
- **DSHOT_TELEM** (before 4.5 — RPMFILTER) — the RPM filter is enabled but there's no ESC telemetry (bidirectional DShot isn't supported by the ESC firmware or isn't enabled).
- **BOOT_GRACE_TIME** — just wait a few seconds after power-up.
- **MOTOR_PROTOCOL** — no motor protocol selected.
INAV: the Status tab shows the reasons (Navigation is unsafe, Compass not calibrated, Hardware failure...). ArduPilot: `PreArm: ...` in the GCS — each line names the culprit (Compass not calibrated, Gyros inconsistent, RC not calibrated, Throttle below failsafe, GPS: No Fix, Battery failsafe, etc.); don't disable the checks in `ARMING_SKIPCHK` (before 4.7 — `ARMING_CHECK`) — fix the cause.

{{diagram:arming-tree|Tree 1 as a diagram: flag → cause → check.}}

### Tree 2. Motors don't spin / spin wrong
Props off.
- **No motor responds in the Motors tab.** → Does the protocol (DShot300/600) and `motor_pwm_protocol` match the ESC? → Are the ESCs getting power (voltage at the pads)? → Are the signal wires on the right pads (`resource MOTOR`)? → Do the ESCs beep when power is applied (startup tune)? If not, the ESC is dead or has no power.
- **One motor doesn't spin, the others do.** → Swap its signal wire with a working one: if the problem moved with the wire — it's the signal/FC pad; if it stayed — it's the ESC or the motor. → Is the resistance of all three motor phases the same? → Phase solder joints (a cold joint is typical).
- **The motor twitches but won't start.** → Lost contact on one phase (solder joint, chafed wire) or a damaged ESC. → Continuity-test the phases, wiggle them.
- **Spinning the wrong way / wrong order.** → Motors tab: check the number and direction of each one against the frame diagram; change the direction in the ESC firmware (BLHeli Suite/Configurator) or by swapping two phases. The “props in/out” direction must be consistent across all four.
- **The drone flips over on takeoff.** → This is Tree 2: order/direction or the wrong mixer (`mixer` isn't for your frame).

### Tree 3. “Goes crazy” on throttle
Symptom: it hovers fine, shakes above 60–70% throttle, motors are hot, the drone behaves unpredictably.
- **Do you have a Blackbox log?** If not, record one; otherwise you're guessing. Gyro spectrum: a huge peak at the motor frequency → mechanics (imbalance, props, motor bearing play); wideband noise that grows with throttle → vibration + insufficient filtering; a peak that doesn't move with throttle → frame resonance.
- **Gyro noise grew after a replacement/repair?** → Is there a capacitor on the power bus? Its lead solder joints, its capacitance. → FC mounting (dampers, taut wires).
- **ESC desync** (a motor suddenly loses RPM, a jerk, then it recovers; in the log — an eRPM dip on one motor): → ESC settings (timing, demag), DShot too fast for long wires, a damaged motor; drop the protocol to DShot300, check the phases.
- **Voltage sag:** in the log VBAT drops below the threshold under throttle → the BEC reboots the FC (instant loss of control) or the ESCs go into protection. → Connector, battery, solder joints.
- **PID/filters**: too much D or P with insufficient filtering → oscillations at high throttle, where there's more noise. → Filters based on the spectrum, then reduce D.
- **Interference on the receiver from the VTX at full power** (LQ drops with throttle — rare, but it happens with ripple on the VTX supply): → a VTX power filter, spacing the antennas apart.

### Tree 4. Something burns/smokes when you plug in the battery
Disconnect immediately. From here on — only through a smoke stopper (a bulb/limiter in series with the positive lead).
- **The bulb glows brightly, the vehicle doesn't power up — a short circuit.** → Disconnect the loads one at a time (ESC, FC, VTX, camera), starting with the last one soldered; where the bulb goes out — that's the short. → Continuity-test + and − on each device separately. → Typical spots: a solder bridge on the pads, a screw in a motor winding (screw too long), a wire pinched by the frame, reversed connector polarity (XT30 on a 2-pin JST is a classic), a capacitor installed backwards.
- **The bulb glows dimly, the vehicle works** — normal (capacitor charging current and the BEC running).
- **A smell, but the bulb didn't light up** — a component burned out earlier; check the BEC voltages (5 V at the output?), feel the chip temperatures with your finger after a brief power-up, look for visible damage under a magnifier.
- **ESC burned on the first connection** → polarity, voltage above the rating (6S on a 4S ESC), phases shorted to ground (a screw), a solder bridge between a phase and power.
- **Burned after reflashing the ESC** → wrong target/settings, a rare case; but 90% of “burned after flashing” is a coincidence with new soldering.

### Tree 5. Loses link or video
- **Failsafe at short range** → LQ and RSSI in the OSD: low RSSI — the antenna (soldering, U.FL connector, under carbon), TX power, bind phrase; low LQ with normal RSSI — interference near the receiver (VTX, buck converter, companion computer). → A range test on the ground (see antennas).
- **Video gets noisy on throttle** → power ripple (capacitor, LC filter), ground, VTX antenna.
- **Video drops out at a distance, RC holds** → the video link budget is used up — expected; antennas, power, whether the power is legal.
- **The link drops when the vehicle turns** → polarization/a null in the radiation pattern: a second antenna at 90°.
- **GPS won't get a fix** → under carbon, near interference sources, no power (the module's LED), wrong UART protocol/baud rate.

### How to extend the tree
Every case of your own: symptom → steps (with facts) → cause → which branch to add it to. In a year this will be your main reference. Some of the course's branches are already collected automatically: the “Failures” page is all the “Troubleshooting” sections of all the modules.

## practice
### Step 1. Work through three faults
Three faults — your own, training ones (create them: disconnect a motor signal wire, turn off the receiver, set `min_check` wrong) or from a forum with a log. Follow the tree strictly, writing down every step and fact.

### Step 2. A fact at every step
Each step's record includes what was measured/read: “status: RXLOSS,” “5 V at RX: 4.98 V,” “phase A–B 0.08 Ω, B–C 0.08, A–C open.” Redo any step without a fact.

### Step 3. Extend the tree
At least one case of your own that isn't in the tree — add it to your copy of the tree (the `troubleshooting.md` file in your engineering folder).

### Worked record of one case
Fault: motor 3 doesn't spin when armed, the others do.

| Tree step | Check | Fact | Conclusion |
|---|---|---|---|
| Does the command reach the ESC? | Motors tab, motor 3 slider | the ESC beeps when power is applied, doesn't respond to the slider | the ESC is alive, there's no signal or it's the wrong one |
| Signal at the FC output | `resource` in the CLI, an oscilloscope or moving the signal wire to a neighboring output | on the neighboring output motor 3 spins | the ESC and motor are fine |
| FC output | the M3 pad solder joint under a magnifier, continuity test | a cold solder joint on the signal wire | cause found |
| Check after the repair | Motors, all four motors, DShot errors | all spin, errors 0 % | closed |

Every row is a fact that can be reproduced. A row saying “probably the ESC” without a check isn't a step, it's a guess.

### What to record for the three faults
- **For each one** — a table of steps like the one above, and the time spent finding it. In a month, compare how much it has shrunk.
- **Create training faults** so they don't do any damage: a disconnected signal wire (with power off!), a receiver switched off (Betaflight will show the `RXLOSS` flag in `status`), a wrong `min_check` (throttle stick at the bottom isn't recognized as “throttle low,” arming fails because of the `THROTTLE` flag).
- **Your own case in the tree:** a branch with a question, a check and a sign. For example: “motors twitch when the video transmitter is switched on → interference on the signal wires → move the VTX, ferrites, DShot300.”

### Lab
Three faults found using the tree with the steps recorded; each step confirmed by a measurement or a firmware message; the tree extended with your own case.

The lab counts as completed when each of the three faults has a table of steps with facts and a conclusion, no conclusion was made without a measurement or a firmware message, and your own tree branch has been added to `troubleshooting.md`.

## diagnostics
- **Symptom:** “nothing helped, I reflashed it, and it started working”
  - Possible cause: the cause wasn't found, it's a coincidence (more often — reseating the contacts).
  - What to do: treat it as unresolved; record it as an open case and keep an eye on it.
- **Symptom:** an intermittent problem that shows up once every few flights
  - Possible cause: a contact/solder joint, vibration, temperature.
  - In the log/on the instrument: an event in the log (an eRPM dip, a VBAT jump, RXLOSS) at the moment of the symptom.
  - What to do: log every flight; wiggle the harnesses with the vehicle powered; spot-heat with a heat gun.
- **Symptom:** the symptom remained after replacing a part
  - Possible cause: the part wasn't to blame — a branch was eliminated incorrectly.
  - What to do: go back to the last confirmed fact.
- **Symptom:** the drone flips over right on takeoff
  - Possible cause: motor order or rotation direction mixed up, wrong mixer.
  - What to do: with props off, check each motor against the frame diagram in the Motors tab.

## references
- Betaflight — Arming Sequence & Safety (arming disable flags) | https://www.betaflight.com/docs/wiki/guides/current/Arming-Sequence-And-Safety | primary | A
- ArduPilot — Pre-Arm Safety Checks (messages and causes) | https://ardupilot.org/copter/docs/common-prearm-safety-checks.html | primary | A
- ArduPilot — Diagnosing problems using logs | https://ardupilot.org/copter/docs/common-diagnosing-problems-using-logs.html | primary | A
- INAV — Troubleshooting / Status reasons (wiki) | https://github.com/iNavFlight/inav/wiki | secondary | B

## checklist
- I start with the firmware message (`status` / PreArm), not with the soldering iron
- One change — one test, every step backed by a fact
- The first power-up after soldering goes through a smoke stopper
- Three faults found using the tree and recorded
- My own troubleshooting tree is set up in my engineering folder
