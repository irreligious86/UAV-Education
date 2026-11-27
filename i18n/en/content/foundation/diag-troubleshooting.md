---
id: diag-troubleshooting
title: "Troubleshooting Tree: The Drone Won't Fly"
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
source_hash: 2ad6a45d8ff4
---

## summary
Troubleshooting is not trying guesses one after another but eliminating the branches of a tree, where each step is confirmed by a fact: a multimeter reading, a firmware message, a line in a log. The module gives you a tree for six typical situations — “won't arm”, “motors don't spin or spin wrong”, “goes crazy on throttle”, “an ESC/board burns when the battery is connected”, “loses link or video”, “shut off in the air or flew away” — and a rule for adding your own cases to it. Tools: a smoke stopper, a multimeter, CLI `status`/pre-arm messages, Blackbox/DataFlash.

## theory
### Troubleshooting rules
1. **Fact first, then hypothesis.** The firmware almost always *tells* you what is wrong: Betaflight — `status` in the CLI (the Arming disable flags line), INAV — the Status tab and `status` in the CLI, ArduPilot — PreArm messages in the GCS. Start with these, not with resoldering.
2. **One change — one check.** You changed two parameters and it started working — you don't know which one helped, and you don't know what you broke.
3. **From cheap to expensive.** Inspection and a multimeter come before an oscilloscope and replacing the board.
4. **Safety at every step.** Props off for everything to do with the motors. The first power-up after any soldering — through a smoke stopper.
5. **Record the path.** Steps with their results — in a note; the cause you found — into the tree and into the aircraft logbook.

### Tree 1. Won't arm
Read the reason: Betaflight CLI → `status` → `Arming disable flags: ...`. The CLI prints the short names from `runtime_config.c` (FAILSAFE, CALIB, NO_ACC_CAL, CMS, BOOTGRACE, MOTOR_PROTO, DSHOT_TELEM, ARM_SWITCH — before 2025.12 it was called ARMSWITCH); below, some of the flags are named as in the documentation. The most common:
- **RXLOSS / RX_FAILSAFE** — the receiver provides no channels. → The port and protocol (UART, CRSF/SBUS, inversion for SBUS on F4), the bind, receiver power (5 V with a multimeter), the Receiver tab — do the channels move.
- **THROTTLE** — throttle above minimum. → Stick calibration in the radio, `min_check`, channel reversal.
- **ANGLE** — the aircraft is tilted more than `small_angle`. → The surface, accelerometer calibration.
- **CALIBRATING / ACC_CALIBRATION / NOGYRO** — the gyro is not calibrated or not found. → Keep it still at power-up; NOGYRO — a hardware problem or the wrong firmware target.
- **ARM_SWITCH** — the arm switch was on when power was applied. → Switch it off, then on.
- **MSP / CLI / CMS_MENU** — the configurator is connected or the OSD menu is open. → Disconnect USB, exit the menu.
- **NOPREARM** — a prearm mode is configured but not activated.
- **DSHOT_TELEM** (before 4.5 — RPMFILTER) — the RPM filter is enabled, but there is no ESC telemetry (bidirectional DShot is not supported by the ESC firmware or not enabled).
- **BOOT_GRACE_TIME** — just wait a few seconds after power-up.
- **MOTOR_PROTOCOL** — no motor protocol selected.
INAV: the Status tab shows the reasons (Navigation is unsafe, Compass not calibrated, Hardware failure...). ArduPilot: `PreArm: ...` in the GCS — each line names the culprit (Compass not calibrated, Gyros inconsistent, RC not calibrated, Throttle below failsafe, GPS: No Fix, Battery failsafe, etc.); do not disable the checks in `ARMING_SKIPCHK` (before 4.7 — `ARMING_CHECK`) — fix the cause.

{{diagram:arming-tree|Tree 1 as a diagram: flag → cause → check.}}

### Tree 2. Motors don't spin / spin wrong
Props off.
- **No motor responds on the Motors tab.** → Do the protocol (DShot300/600) and `motor_pwm_protocol` match the ESC? → Are the ESCs getting power (voltage on the pads)? → Are the signal wires on the right pads (`resource MOTOR`)? → Do the ESCs beep when power is applied (the startup tune)? If not, the ESC is dead or has no power.
- **One motor doesn't spin, the others do.** → Swap the signal wires with a working one: if the problem moved with the wire — it's the signal/the FC pad; if it stayed — the ESC or the motor. → Is the resistance of the motor's three phases equal? → Phase soldering (a cold joint is typical).
- **A motor twitches and won't start.** → Lost contact on one phase (soldering, a chafed wire) or a damaged ESC. → Check the phases for continuity, wiggle them.
- **They spin the wrong way / in the wrong order.** → The Motors tab: check the number and direction one by one against the frame diagram; change the direction in the ESC firmware (BLHeli Suite/Configurator) or by swapping two phase wires. The “props in/out” direction — consistent on all four (which layout to choose — `f-physics`, “Props in or props out”).
- **The drone flips over on takeoff.** → This is tree 2: order/direction or a wrong mixer (`mixer` not for your frame).

### Tree 3. “Goes crazy” on throttle
Symptom: it hovers fine, above 60–70% throttle it shakes, the motors are hot, the drone behaves unpredictably.
- **Is there a Blackbox log?** If not — record one, otherwise it's guesswork. The gyro spectrum: a huge peak at the motor frequency → mechanics (imbalance, props, motor play); broadband noise growing with throttle → vibration + insufficient filtering; a peak that doesn't move with throttle → frame resonance.
- **Did gyro noise grow after a replacement/repair?** → Is there a capacitor on the power bus? The soldering of its leads, its capacitance. → The FC mounting (dampers, taut wires).
- **ESC desync** (a motor suddenly loses RPM, a jerk, then it recovers; in the log — an eRPM dip on one motor): → ESC settings (timing, demag), DShot too fast for long wires, a damaged motor; lower the protocol to DShot300, check the phases.
- **Voltage sag:** in the log VBAT drops below the threshold on throttle → the BEC reboots the FC (an instant loss of control) or the ESCs go into protection. → Connector, battery, soldering.
- **PID/filters**: too much D or P with insufficient filtering → oscillations at high throttle, where there is more noise. → Filters based on the spectrum, then lower D.
- **Interference to the receiver from a VTX at full power** (LQ drops with throttle — rare, but it happens with ripple on the VTX): → a VTX power filter, antenna separation.

### Tree 4. Something burns/smokes when the battery is connected
Disconnect immediately. From then on — only through a smoke stopper (a bulb/limiter inline in the positive lead).
- **The bulb glows brightly, the aircraft doesn't power up — a short circuit.** → Disconnect the loads one at a time (ESC, FC, VTX, camera), starting with the most recently soldered; where the bulb goes out — that's where the short is. → Continuity check of + and − for each device separately. → Typical places: a solder bridge on the pads, a screw in a motor winding (a long screw), a wire pinched by the frame, a connector with reversed polarity (2-pin JST-PH is wired with reversed polarity by different manufacturers — a classic), a capacitor installed backwards.
- **The bulb glows dimly, the aircraft works** — normal (the capacitor charging current and the BEC running).
- **A smell, but the bulb did not light up** — a component burned earlier; check the BEC voltages (5 V at the output?), the chip temperatures with a finger after a short power-up, visible damage under a magnifier.
- **The ESC burned on the first connection** → polarity, a voltage above the rating (6S on a 4S ESC), phases shorted to ground (a screw), a solder bridge between a phase and power.
- **It burned after reflashing the ESC** → wrong target/settings, a rare case; but 90% of “it burned after flashing” is a coincidence with new soldering.

### Tree 5. Loses link or video
- **Failsafe at short range** → LQ and RSSI in the OSD: low RSSI — the antenna (soldering, the U.FL connector, under carbon), TX power, the binding phrase; low LQ with normal RSSI — interference near the receiver (VTX, buck converter, companion). → A range test on the ground (see antennas).
- **Video is noisy on throttle** → power ripple (capacitor, LC filter), ground, the VTX antenna.
- **Video drops out far away, RC holds** → the video budget is exhausted — expected; antennas, power, whether the power is legal.
- **The link drops when the aircraft turns** → polarization/a null in the pattern: a second antenna at 90°.
- **GPS doesn't get a fix** → under carbon, near interference sources, no power (the module's LED), wrong UART protocol/baud rate.
- **A digital system, a black screen in the goggles** → a separate branch below.

### Tree 5, the digital system branch: a black screen in the goggles
Analog gets noisy on a weak signal, digital without a link is silent — so we go branch by branch, not “by eye”. The example is the DJI O4 (per the manufacturer's manual); Walksnail, HDZero and OpenIPC have their own buttons and indicators, the order of the branches is the same.
- **Binding (bind/link).** The air unit's indicator is red — no pairing; green — there is a link. Binding: the link button on the module (the indicator blinks red) → the link button on the goggles (the goggles beep) → the module's indicator turns green. After replacing the module or the goggles, binding is repeated. The module and the goggles must be from compatible generations — per the manufacturer's compatibility table.
- **Firmware versions.** DJI requires updating all devices to the latest versions before binding and rebooting each one after the update. A new module with old goggles (or vice versa) is a typical cause of “they don't see each other”. A non-activated device works in a limited way: the module — at reduced power, the goggles — only on the public channel.
- **Power.** With a multimeter on the module's pad under load: O4 — 3.7–13.2 V, O4 Pro — 7.4–26.4 V (other modules — the `bf-hd-osd-video` module). The module reboots on throttle — BEC sag: the power branch from tree 3 and the BEC budget from the “Power” module.
- **Overheating.** On the ground the module first runs in a reduced-power mode (lower image quality — normal until takeoff or the start of recording), and when overheating while idle it shuts down; the goggles warn about overheating. The screen went black on the bench after a few minutes — cool it down, add airflow, don't keep it on without airflow.
- **Antenna.** The antenna connector on the module is clicked in, the cable is not cut, the antenna is routed outside the frame and not covered by carbon; on the goggles the antennas are screwed on.
- **There is a picture, but no OSD** — this is no longer the link but the MSP DisplayPort setup: the `bf-hd-osd-video` module.

### Tree 6. Shutdown in the air and flyaway
The aircraft disarmed, switched off or flew the wrong way. In the air the recovery reflex applies (below); on the ground — rule 1: first the log, then a hypothesis. Do not power on or reflash the aircraft until the log has been copied.

**Step 1. What to read in the log.**
| Firmware | Where the reason is recorded | What else to look at |
|---|---|---|
| Betaflight 2025.12 | Blackbox: the disarm event carries a reason code (`flightLogDisarmReason_e` in `fc/core.h`): 0 ARMING_DISABLED, 1 FAILSAFE, 2 THROTTLE_TIMEOUT, 3 STICKS, 4 SWITCH, 5 CRASH_PROTECTION, 6 RUNAWAY_TAKEOFF, 7 GPS_RESCUE, 8 SERIAL_COMMAND, 9 LANDING, 10 CRASHFLIP | `failsafePhase`, `rssi`, `vbatLatest`, `eRPM[n]`, `motor[n]` in the last seconds |
| ArduPilot 4.7 | DataFlash: `ARM` with `ArmState` = 0 and the `Method` field (2 switch, 7 battery failsafe, 12 crash check, 13 landing, 16 radio failsafe, 17 the `DISARM_DELAY` delay, 24 EKF failsafe); `ERR` with `Subsys`/`ECode` | `MODE.Rsn` (who changed the mode), `EV`, `MSG`, `POWR.VCC`, `BAT`, `XKF4`, `VIBE` |
| INAV 9.1 | the OSD statistics screen after disarming: the `DISARMED BY` line (TIMEOUT, STICKS, SWITCH, FAILSAFE, NAV SYS, LANDING); the Blackbox ends with the line `End of log (disarm reason:N)` — 1 TIMEOUT, 2 STICKS, 4 SWITCH, 6 FAILSAFE, 7 NAVIGATION, 8 LANDING | voltage, RSSI, navigation state before the end of the log |
| PX4 1.17 | ULog, the `vehicle_status` topic: `latest_disarming_reason` (1 sticks, 2 switch, 7 auto-disarm after landing, 8 auto-disarm before takeoff, 9 kill switch, 10 lockdown, 11 failure detector), the `failsafe` flag, `failure_detector_status` | Flight Review: power, vibration, position estimate |

**Step 2. The log cuts off in the air without a disarm event** → the firmware did not disarm; power was lost or the flight controller rebooted (brownout). → The battery connector and its soldering, a sag in `vbatLatest`/`BAT.Volt` before the cutoff, `POWR.VCC` (ArduPilot), the BEC and the capacitor — the power branch from tree 3. A battery that came off gives the same picture: check the strap and the battery pad.

**Step 3. The reason is recorded — branches by reason.**
- **Failsafe** (Betaflight 1 FAILSAFE; ArduPilot `ERR` Subsys 5 and `Method` 16; INAV FAILSAFE). → The aircraft did what it was configured to do: `failsafe_procedure = DROP` in Betaflight means a fall; in PX4 `NAV_RCL_ACT` = 6 — disarm, 5 — flight termination (default 2, return). Why the link was lost — tree 5; what should happen on loss — the failsafe modules for your firmware.
- **Switch or sticks** (Betaflight 4 SWITCH / 3 STICKS; ArduPilot `Method` 2; INAV SWITCH; PX4 2 or 9). → The arm or kill switch was bumped. In PX4, after the kill switch is engaged, disarm follows after 5 s (hard-coded in 1.18; before 1.18 — `COM_KILL_DISARM`). → Move the arm switch to a two-position switch with a lock, check in `RCIN`/`rcCommand` whether the channel “chatters”.
- **Runaway takeoff protection and the crash detector.** Betaflight 6 RUNAWAY_TAKEOFF — in the first seconds after liftoff: motor order and direction, props, board orientation (tree 2, the `bf-arming-safety` module); 5 CRASH_PROTECTION — `crash_recovery = DISARM` triggered, or the impact detector during GPS Rescue. ArduPilot `ERR` Subsys 12 (`ECode` 1 — crash, 2 — loss of control) and `Method` 12: crash check disarms when the angle error stays above 30° for about 2 s (enabled by `FS_CRASH_CHECK`); Subsys 25 — the thrust loss check. PX4 11 FAILURE_DETECTOR / 10 LOCKDOWN: roll or pitch greater than `FD_FAIL_R`/`FD_FAIL_P` (60°) for longer than `FD_FAIL_R_TTRI`/`FD_FAIL_P_TTRI` (0.3 s); in the first 3 s after takeoff (hard-coded in 1.18; before 1.18 — `COM_LKDOWN_TKO`) this is a disarm (in Acro this check is not performed), after that — flight termination if `CBRK_FLIGHTTERM` = 0. → The detector is a consequence. The cause is earlier in the log: a motor or ESC failure, desync, a thrown prop, motor saturation.
- **Desync or motor failure** → an `eRPM` dip on one motor, that motor's output going to maximum, a flip. The desync branch from tree 3.
- **EKF failsafe (ArduPilot)** → `ERR` Subsys 16 with `ECode` 2 (bad variance), then Subsys 17. The action is set by `FS_EKF_ACTION` (1 — Land if the mode requires position; 2 — AltHold; 3 — Land from any mode), the threshold — `FS_EKF_THRESH` (0.8 by default). → `XKF4`: which variance grew — compass (`SM`), position/velocity (`SP`, `SV`) or height (`SH`); `VIBE` and clipping.
- **GPS glitch and flyaway** → ArduPilot `ERR` Subsys 11 with `ECode` 2; “toilet bowling” in Loiter/PosHold — the compass: interference from power wires or a wrong orientation. Betaflight 7 GPS_RESCUE — Rescue disarmed by itself on hitting the ground. INAV NAV SYS — a disarm from navigation. → The satellite count and HDOP before the event, the position of the GPS module and compass, the module's power.
- **Auto-disarm** (Betaflight 2 THROTTLE_TIMEOUT — `MOTOR_STOP` with `auto_disarm_delay`, 9 LANDING — a disarm on the jolt of touchdown, threshold `landing_disarm_threshold`; ArduPilot `Method` 17 or 13; PX4 7 or 8 — `COM_DISARM_LAND` 2 s, `COM_DISARM_PRFLT` 10 s). → The firmware decided the aircraft was on the ground: zero throttle during a descent, a hard touchdown, a long pause after arming.

{{diagram:inair-disarm-tree|Tree 6 as a diagram: first — is there a disarm event in the log; if not — look at power, if yes — follow the branch for the reason, and treat a triggered crash detector as a consequence.}}

**The recovery reflex (in the air).** There is no time for troubleshooting in flight, so there is one action, learned in advance.
1. **One switch to a mode without GPS and compass.** ArduPilot — Stabilize (AltHold if altitude hold is reliable); INAV — ANGLE without navigation modes; PX4 — Stabilized; Betaflight — turn off GPS Rescue and go back to your main mode. The switch is always in the same place on all your models on the radio.
2. **Throttle — by hand and immediately.** In manual-throttle modes the throttle stick directly sets the thrust: center stick after Loiter is not necessarily hover. Before switching, put the stick at roughly the hover throttle; after switching, hold the altitude. Do not cut the throttle to zero in the air: the aircraft will fall or lose controllability.
3. **Gain margin and move away from people.** Altitude and distance give you seconds; land at the nearest clear spot, not “home at any cost”.
4. **Disarming is the last resort.** Disarming in the air turns the aircraft into a falling object, so it is used in four cases: the aircraft is already on the ground or in an obstacle, and the motors are spinning; a runaway takeoff right after liftoff; the aircraft is heading uncontrollably toward people, and a fall here is safer than continued flight; a light aircraft (whoop, 3–5″) right above the ground over an empty area, when the impact is already unavoidable (`ops-pilot-training`). In all other cases — items 1–3.

### How to extend the tree
Each case of your own: symptom → steps (with facts) → cause → which branch to add it to. In a year this will be your main reference. Some of the course's branches are already collected automatically: the “Failures” page is all the “Troubleshooting” sections of all modules.

### Place in the system

- **Receives:** the arming disable flags (`bf-arming-safety`); the disarm reason and the last seconds of flight from the log (`bf-blackbox`, `ap-logs`); voltages and continuity checks with a multimeter (`el-measure`).
- **Provides:** a cause localized to its subsystem: power (`el-power-design`), soldering and connectors (`el-wiring`), link and antennas (`rf-antennas`); the case found — into the aircraft logbook (`ops-maintenance`).
- **If you get it wrong here:** the aircraft was powered on or reflashed before the log was copied → the disarm reason is lost, the analysis ends with “not established” (`ops-case-studies`). A triggered crash detector was taken for the cause → the real failure (desync, a thrown prop) remains and will repeat on the next flight (`f-esc-firmware`). Two parameters changed at once → it is unclear what helped and what broke (`eng-method-101`).

## practice
### Step 1. Analyze three faults
Three faults — your own, training ones (create them: disconnect a motor signal wire, switch off the receiver, set `min_check` wrong) or from a forum with a log. Follow the tree strictly, writing down every step and fact.

### Step 2. A fact at every step
The record of each step contains what was measured/read: “status: RXLOSS”, “5 V on RX: 4.98 V”, “phase A–B 0.08 Ω, B–C 0.08, A–C open”. Redo any step without a fact.

### Step 3. Extend the tree
At least one case of your own that is not in the tree — add it to your copy of the tree (the `troubleshooting.md` file in the engineering folder).

### A worked record of one case
Fault: motor 3 does not spin when armed, the others do.

| Tree step | Check | Fact | Conclusion |
|---|---|---|---|
| Does the command reach the ESC? | the Motors tab, the motor 3 slider | the ESC beeps when power is applied, does not respond to the slider | the ESC is alive, there is no signal or it is wrong |
| Signal at the FC output | `resource` in the CLI, an oscilloscope, or moving the signal wire to a neighboring output | on the neighboring output motor 3 spins | the ESC and the motor are fine |
| The FC output | the soldering of pad M3 under a magnifier, a continuity check | a cold solder joint on the signal wire | cause found |
| Check after the repair | Motors, all four motors, DShot errors | all spin, errors ≤ 1 % (`bf-rpm-filter`) | closed |

Each row is a fact that can be repeated. A row “probably the ESC” without a check is not a step but a guess.

### What to write down for the three faults
- **For each one** — a table of steps, as above, and the time spent searching. In a month, compare how much it has shrunk.
- **Create training faults** in a way that does no harm: a disconnected signal wire (with no power!), a switched-off receiver (Betaflight will show the `RXLOSS` flag in `status`), a wrong `min_check` (the throttle stick at the bottom is not recognized as “throttle low”, arming fails because of the `THROTTLE` flag).
- **Your own case in the tree:** a branch with a question, a check and a sign. For example: “motors twitch when the video transmitter is switched on → interference on the signal wires → move the VTX, ferrites, DShot300”.

### Rehearse the recovery reflex
The reflex from tree 6 works only if your hand has made this movement before. Three stages:
1. **Bench, props off.** Flip the “manual” mode switch and confirm in the OSD or GCS that the mode really changed (Stabilize, ANGLE, Stabilized). Write the channel number, switch position and mode into the aircraft's spec sheet. Check that it is the same switch on all your models on the radio.
2. **SITL** (ArduPilot, INAV or PX4 — the “from scratch” modules for your firmware). Hover in a position-holding mode at 10 m → switch to manual → hold altitude within a ±2 m corridor for 30 s → back again. Five repetitions in a row without losing altitude. Write down where the throttle stick was at the moment of switching.
3. **Field.** Hover at 3–5 m over a soft area, an observer next to you, no people around. The same five switches. Then the same on an unexpected “mode!” call from the observer — the time from the call to the click must be within 2 seconds.

After each stage — a line in the logbook: date, aircraft, how many repetitions, maximum altitude loss. Repeat after every change of radio, model or switch layout.

### Lab
Three faults found using the tree with the steps recorded; each step confirmed by a measurement or a firmware message; the tree extended with a case of your own.

Self-check: the lab is done when each of the three faults has a table of steps, as in the worked record: the “Fact” column of every row contains a measured number or a verbatim firmware message (not “probably”), and the last row is the check after the repair; for the training faults, the cause found via the tree matched the one you created yourself, and its sign showed up along the way (`RXLOSS` in `status` with the receiver switched off, the `THROTTLE` flag with a wrong `min_check`); a branch of your own with a question, a check and a sign is added to `troubleshooting.md`; and the rehearsal of the reflex is recorded in numbers — five switches in a row within the ±2 m corridor and the maximum altitude loss.

## diagnostics
- **Symptom:** “nothing helped, I reflashed it, it works”
  - Possible cause: the cause was not found, a coincidence (more often — reseating contacts).
  - What to do: treat it as unresolved; record it as an open case, keep watching.
- **Symptom:** an intermittent problem, appears once every few flights
  - Possible cause: a contact/solder joint, vibration, temperature.
  - In the log/on the instrument: an event in the log (an eRPM dip, a VBAT jump, RXLOSS) at the moment of the symptom.
  - What to do: a log on every flight; wiggle the harnesses with the aircraft powered; spot heating with a hot-air gun.
- **Symptom:** after replacing a part the symptom remained
  - Possible cause: the part was not at fault — a branch was eliminated incorrectly.
  - What to do: go back to the last confirmed fact.
- **Symptom:** the aircraft disarmed or shut off in the air
  - Possible cause: a failsafe with a “disarm” action, a bumped switch, the crash detector, a power sag with a flight controller reboot.
  - In the log/on the instrument: the disarm reason code (tree 6, step 1); a log cut off without a disarm event — power.
  - What to do: copy the log before any power-up; follow the branch for your reason; do not fly until it is resolved.
- **Symptom:** in a position-holding mode the aircraft drifts sideways or circles
  - Possible cause: compass interference, a GPS glitch, a position estimate failure.
  - In the log/on the instrument: ArduPilot — `ERR` Subsys 11, 16, 17; the `XKF4` variances.
  - What to do: in the air — switch to a mode without GPS and manual throttle; on the ground — the EKF and GPS branches of tree 6.
- **Symptom:** a black screen in digital goggles
  - Possible cause: no binding, different firmware versions on the module and goggles, overheating or a power sag on the module, the antenna.
  - What to do: tree 5, the digital system branch — in order: binding, versions, power, overheating, antenna.
- **Symptom:** the drone flips over immediately on takeoff
  - Possible cause: the motor order or spin direction is wrong, a wrong mixer.
  - What to do: without props, check each motor against the frame diagram on the Motors tab.

## references
- Betaflight — Arming Sequence & Safety (arming disable flags) | https://www.betaflight.com/docs/wiki/guides/current/Arming-Sequence-And-Safety | primary | A
- ArduPilot — Pre-Arm Safety Checks (messages and causes) | https://ardupilot.org/copter/docs/common-prearm-safety-checks.html | primary | A
- ArduPilot — Diagnosing problems using logs | https://ardupilot.org/copter/docs/common-diagnosing-problems-using-logs.html | primary | A
- INAV — Troubleshooting / Status reasons (wiki) | https://github.com/iNavFlight/inav/wiki | secondary | B
- Betaflight 2025.12.1 — fc/core.h, disarm reasons flightLogDisarmReason_e (accessed 2026-11-17) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.1/src/main/fc/core.h | primary | A
- ArduPilot Copter-4.7.2 — AP_Logger.h, ERR subsystems and codes (accessed 2026-11-17) | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_Logger/AP_Logger.h | primary | A
- ArduPilot Copter-4.7.2 — AP_Arming.h, the Method field of the ARM message (accessed 2026-11-17) | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_Arming/AP_Arming.h | primary | A
- ArduPilot Copter-4.7.2 — crash_check.cpp, crash check conditions (accessed 2026-11-17) | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/ArduCopter/crash_check.cpp | primary | A
- INAV 9.1.0 — fc/fc_core.h, disarmReason_t (accessed 2026-11-17) | https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/fc/fc_core.h | primary | A
- PX4 v1.17.0 — VehicleStatus.msg, disarm reasons (accessed 2026-11-17) | https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.17.0/msg/versioned/VehicleStatus.msg | primary | A
- PX4 v1.17.0 — Failure Detector parameters (accessed 2026-11-17) | https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.17.0/src/modules/commander/failure_detector/failure_detector_params.c | primary | A
- DJI O4 Air Unit Series — User Manual v1.0 (binding, firmware, overheating, power; accessed 2026-11-17) | https://hobbydrone.cz/user/related_files/dji_o4_air_unit_series_user_manual_v1_en.pdf | primary | B

## checklist
- I start with the firmware's message (`status` / PreArm), not with the soldering iron
- One change — one check, every step with a fact
- The first power-up after soldering — through a smoke stopper
- Three faults found using the tree and recorded
- My own troubleshooting tree is set up in the engineering folder
- After a shutdown in the air I first copy the log and read the disarm reason code
- The “manual” mode switch is rehearsed on the bench, in SITL and in the field
