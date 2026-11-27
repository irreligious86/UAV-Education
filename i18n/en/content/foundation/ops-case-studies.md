---
id: ops-case-studies
title: "Analysis of Real Accidents"
level: L1
readingTime: 40 min
firmware: any firmware
status: published
added: 2026-11-08
tags:
  - accidents
  - investigation
  - failsafe
  - case studies
related:
  - ops-field
  - bf-failsafe
  - eng-method-101
  - f-frame-mech
next:
  - diag-troubleshooting
source: content/foundation/ops-case-studies.md
source_hash: 40ce13f89b55
---

## summary
Engineers learn from other people's crashes — if the crashes have been analyzed. This module takes three public investigations by government boards — the Matternet M2 in Zurich (2019, an ArduCopter-based platform, a failure caused by vibration and the EKF), the Alauda Airspeeder Mk II at Goodwood (2019, loss of link and a kill switch that did not work) and the Freefly Alta X at Henley (2022, battery depletion) — and analyzes each one with the same scheme: symptom → cause → what the log shows → consequences → what to change in the configuration and procedures. Each case ends with a line for your checklist.

## theory
### The analysis scheme
Board reports (AAIB in the UK, STSB/SUST in Switzerland, NTSB in the US) follow the same logic, and it is also your tool:

1. **Symptom** — what the operator saw.
2. **Sequence** — events in time order from the logs and telemetry.
3. **Cause** — technical (what failed) and systemic (why it was possible).
4. **What the data shows** — specific log messages, parameters, values.
5. **Consequences** — impact energy, who was nearby, what happened to the area.
6. **Fix** — configuration, design, procedure.

Distinguish three types of cause: **hardware failure** (a part broke), **configuration error** (a parameter did not match the mission), **operator error** (a procedure was not followed). In real accidents all three are almost always present.

### Case 1. Matternet M2, Zurich, 9 May 2019 (STSB, final report No. 2390, aircraft SUI-9903)
**Context.** A Swiss Post delivery quadcopter on a modified ArduCopter (based on 3.5.0-rc5), three IMUs, a flight termination system (FTS) with a parachute. A return flight without cargo.

**Sequence.** Takeoff at 10:37:35. After ~50 s, vibration grew on all three IMUs (accelerations in places > 30 m/s²), and IMU3 showed sharp deviations, while IMU1 and IMU2 showed consistent values; the aircraft began to oscillate in pitch. At 10:38:46 the log shows `EKFCHECK_BAD_VARIANCE`; the error handler activated the FTS at ~185 m above the takeoff point (~100 m above the ground): all four motors were stopped, the parachute was deployed. The parachute line broke at its attachment on the aircraft; an unbraked fall, destruction at 10:38:48. The location — a forest, ~50 m from a group of children with their teachers, who did not hear the warning signal.

**Causes.** Technical: growing vibration of unknown origin (probably a resonance from an external factor — prop damage or a bird strike) combined with insufficient robustness of the firmware to such an event. Systemic: the modified ArduCopter could run only two EKF lanes, `EK2_IMU_MASK = 5` (IMU1 and IMU3, without IMU2) — the faulty sensor could not be isolated; the FTS triggered an uncontrolled descent immediately instead of attempting a controlled flight termination. The parachute line had been damaged by the sharp edge of the aluminum attachment even before deployment and did not withstand the jerk.

**What the log shows.** `VIBE` grows on all IMUs, but the data of one IMU sharply diverges from the other two (a sign of a local source or sensor, not of the frame as a whole); the EKF innovations grow → `EKFCHECK_BAD_VARIANCE`; switch to the FTS.

**Consequences.** Impact energy ≈ 118 J without cargo (above the 80 J accepted as the threshold of serious injury). The delivery program was suspended. Seven safety recommendations.

**Fixes (actual).** `EK2_IMU_MASK = 3` (two healthy IMUs + the ability to isolate), a check of both EKF lanes at arming, a second safety line and a redesigned attachment, a 100 dB siren, a log analysis tool, a parachute compliant with ASTM F3322, maximum speed reduced from 20 to 16 m/s. Board recommendation No. 591: pursue a redundant propulsion concept (the analysis noted that configurations with 6 or more motors have a significantly lower probability of failure).

**Line for your checklist:** “Vibration on each IMU in the log is checked after every mechanical change; the behavior on an EKF failsafe is known and tested in SITL”.

### Case 2. Alauda Airspeeder Mk II, Goodwood, 4 July 2019 (AAIB, report 03/2021)
**Context.** A 95 kg demonstration multirotor, a custom flight controller with two IMUs, no GNSS and no RTH, controlled from a FrSky Taranis X9D radio + an R9M module on 915 MHz (10 mW, FCC mode — a band not permitted for airborne use in the UK). A separate kill switch on 433 MHz LoRa with its own battery, cutting power to the controller through a relay.

**Sequence.** ~65 s after takeoff — a sudden uncommanded transition to level attitude, then loss of link. On loss of link the controller **froze the last throttle commands and held level attitude** — the aircraft continued climbing at ~2000 ft/min, rotating at ~40°/s, for 4 min 12 s up to ~7900 feet, and entered the controlled airspace of a Gatwick holding area. On the “kill” command the observer activated the switch — with no effect. After the battery was depleted the aircraft flipped over and fell at ~4500 ft/min into a field 40 m from houses, 700 m outside the permitted area. Impact energy ≈ 24,800 J. No one was hurt.

**Causes.** The exact cause of the loss of link was not established: **there was no on-board recording**, the boards were destroyed. Systemic causes established by the board: the loss-of-link failsafe was designed as “hold throttle” rather than “descend/land”; the kill switch had no feedback (loss of its channel went undetected), with the relay in a normally closed state (a switch failure goes unnoticed until the moment it is needed), on a prototyping board with jumper wires, activated by a voice command instead of automatically; in the wreckage the relay and the power wire were detached from the board. The aircraft was not designed or tested to any standard: mounting with Velcro and zip ties, Ethernet cables as ESC signal lines, soldering with jumper wires, a 42–58 V battery with no protection whatsoever; no vibration tests, no RF tests. Speed in flight up to 25 m/s against a declared limit of 11 m/s.

**What the data shows.** Nothing — and that is the main lesson: without a log, an investigation ends with the words “not established”.

**Fixes.** 15 recommendations to the regulator and the operator. For you: the failsafe must put the aircraft into a safe state (descend/land/RTH), not “hold”; the emergency circuit — with feedback and self-diagnostics; single points of failure — counted; on-board recording — always.

**Line for your checklist:** “The failsafe is tested by switching off the radio on the ground without props before the first flight of every new configuration; the black box is enabled”.

### Case 3. Freefly Alta X, Henley-on-Thames, 29 June 2022 (AAIB, bulletin 01/2023)
**Context.** Commercial video filming of a regatta, a 28 kg multirotor (MTOW 34.9) on two 12S LiPos, full charge 50.4 V. The 21st flight of the day, the 6th on this battery set, while the intention was to change them every three flights.

**Sequence.** At ~50 m the low-voltage warning triggered. During the return the voltage kept falling, controlled flight was lost; the aircraft, almost in free fall (≈ 30 m/s), hit a boat on the river. No one was hurt; impact energy ≈ 13,700 J (AAIB estimate; ½·28·30² ≈ 12,600 J, 13,700 J corresponds to ~31 m/s — a free fall from 50 m) — the board noted that an impact on a person would have been fatal. **No logs** — the aircraft was not recovered.

**Causes.** Configuration error: the warning threshold had been lowered by the pilot from 44 V (the manufacturer's default, “land as soon as possible”) to 42 V — the margin to the critical voltage was reduced by 2 V. Operator error: the voltage before takeoff was most likely not checked (the manufacturer requires > 48 V, the pilot “took off below 48 too”); the batteries were not replaced as planned. No hardware failure was established.

**What the log would have shown.** The voltage under load below the threshold long before the warning; a warning that triggered at a voltage leaving seconds, not minutes.

**Fixes.** Thresholds — not lower than the manufacturer's recommendations, and for your own batteries — from a measured discharge curve (the procedure and the threshold table by chemistry and class — `f-power`, “Setup order and verification”, step 6); the pre-flight voltage check is a checklist item that cannot be skipped; tracking the flights on each battery set.

**Line for your checklist:** “The battery voltage is written down before every takeoff; the warning and failsafe thresholds are justified by the discharge curve and not lowered for an extra minute”.

### Common patterns across the three cases
- In all three, the problem is not a “bad part” but the **design of failure behavior**: what the aircraft does when something goes wrong.
- In two of the three **there was no data**; the investigation hit “not established”. The log is not for tuning, it is for answering the question “why”.
- In no case was anyone hurt — **and that is luck**, not a result: 50 m from children, 40 m from houses, a boat instead of a person.
- Impact energies of 118 J, 13,700 J, 24,800 J versus a ~80 J threshold of serious injury: even a light aircraft is dangerous, a heavy one is lethal.

{{diagram:chart-impact-energy|The impact energy of even the light Matternet is 1.5 times above the serious-injury threshold; for the heavy aircraft it is 171 and 310 times (logarithmic scale).}}

{{diagram:incident-analysis|The accident analysis scheme following the logic of board reports — and the last step: what to change in your own process.}}

### Place in the system

- **Receives:** log messages and plots — `VIBE`, EKF innovations, voltage (`ap-logs`, `ap-ekf`); the configured failure behavior (`ap-safety-fs`); battery thresholds (`f-power`).
- **Provides:** lines for the checklists (`f-safety`, `ops-field`); requirements for failure behavior (`eng-systems`); an argument for motor and power redundancy (`el-redundancy`).
- **If you get it wrong here:** the analysis is done without a log → the cause is “not established”, the fix is chosen at random; so log recording is a requirement, not an option (`bf-blackbox`, `ap-logs`). The accident is blamed on a “part failure” and the configuration and procedure are not checked → the battery threshold or failsafe stay the same, and the scenario repeats (`ap-safety-fs`, `ops-maintenance`).

## practice
### Step 1. Read the primary source
Open one of the three reports (links below) and read the section with the sequence of events and the conclusions. Compare with the analysis above: what the report has that is not here.

### Step 2. Analyze two more incidents
Take two public cases (the AAIB publishes dozens of UAS reports; “record-only” bulletins are short) and fill in a table using the six-point scheme, with links.

### Step 3. Your own incident
Your own crash or loss of link (or a training one: a log from a forum) — the same scheme, from the log. If there is no log — that is the first conclusion.

### Step 4. Changes
For each of the five analyzed cases — one line in your pre-flight checklist or one parameter in the configuration, with a justification. Record it in the CHANGELOG of the engineering folder.

### Lab
A table analyzing three public incidents with links to the reports; for each — a change in your checklist or configuration; an analysis of one of your own incidents from the log.

### The analysis scheme and an example line
Six points per case: what happened → the sequence of events in time → the immediate cause → the root cause (a process, not a person) → what worked and what didn't → the change on your side. An example result line: “Report X (link): GNSS loss near a metal structure → root: position flight without checking navigation quality → on my side: a checklist item ‘HDOP and satellite count at the site’, in the config — a warning on GNSS quality”.

### What you should end up with
- A table of three public cases: each with a link to the primary report, not to a retelling.
- Each conclusion turned into a specific action — a checklist line, a parameter or a site rule, not “be more careful”.
- Your own incident analyzed from the log with the same scheme. If there is no log, the first measure is to enable log recording. This is not a joke but the most common real conclusion.
- Entries in the CHANGELOG of the engineering folder: date, change, a link to the case that led to it.

Self-check: the lab is done when three public incidents are analyzed with the scheme and every row has all six points filled in and a link to the primary report; the root cause in every row is named as a process, not as a person (“the pilot made a mistake” is the immediate cause, dig further); for each there is a change you can find by eye in your checklist or config — a line, a parameter or a site rule, not “be more careful” — and an entry about it in the CHANGELOG with a link to the case; one incident of your own (or a training one) is analyzed from the log with the same scheme. The benchmark for depth is the case analyses in the theory: check against them whether your “event → immediate cause → root” chain is shorter.

## diagnostics
- **Symptom:** the analysis of your own crash ends with “I don't know why”
  - Possible cause: there was no on-board recording or telemetry.
  - In the log/on the instrument: nothing to look at.
  - Consequences: the cause will repeat.
  - What to do: enable Blackbox/DataFlash on all flights, record a tlog on the GCS.
- **Symptom:** the failsafe is “configured” but has never been tested
  - Possible cause: no ground test in the procedure.
  - In the log/on the instrument: no failsafe event in the log over the whole history of the aircraft.
  - Consequences: as with the Airspeeder — the aircraft does something other than what you think.
  - What to do: a test without props for every new configuration, the result goes into the test table.
- **Symptom:** battery thresholds lowered “to fly longer”
  - Possible cause: the margin was sacrificed for flight time.
  - In the log/on the instrument: the voltage under load near the critical level before the warning triggers.
  - Consequences: as with the Alta X — a fall in free fall.
  - What to do: thresholds from the discharge curve of your batteries, not lower than the manufacturer's recommendations.
- **Symptom:** vibration grew on only one IMU
  - Possible cause: a local source (mount, sensor) or damage.
  - In the log/on the instrument: `VIBE` diverges between the IMUs, the EKF innovations grow.
  - Consequences: an EKF failsafe, for the Matternet — the FTS.
  - What to do: land, inspect the props and the mount; an IMU mask that allows a faulty sensor to be isolated.

## references
- STSB (SUST) — Final report SUI-9903, Matternet M2 V9, Zürich, 9 May 2019 (PDF) | https://www.sust.admin.ch/inhalte/AV-berichte/SUI-9903_SB_e.pdf | primary | A
- AAIB — Investigation to Alauda Airspeeder Mk II (UAS), Goodwood, 4 July 2019 | https://www.gov.uk/aaib-reports/aaib-investigation-to-alauda-airspeeder-mk-ii-uas-registration-n-slash-a-040719 | primary | A
- AAIB — Investigation to Freefly Systems Inc. Alta X (UAS), Henley-on-Thames, 29 June 2022 | https://www.gov.uk/aaib-reports/aaib-investigation-to-freefly-systems-inc-alta-x-uas-registration-n-slash-a | primary | A
- AAIB — all UAS reports (search) | https://www.gov.uk/aaib-reports?keywords=UAS | primary | A

## checklist
- I know the six-point analysis scheme and the three types of cause
- I have read at least one primary source in full
- Three public incidents are analyzed, with links
- My own incident is analyzed from the log (or the conclusion about its absence is drawn)
- Five changes are made to the checklist/configuration and recorded in the CHANGELOG
