---
id: ops-case-studies
title: "Analyzing Real Crashes"
level: L1
readingTime: 40 min
firmware: any firmware
status: published
added: 2026-11-08
tags:
  - crashes
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
source_hash: 7149d239f9be
---

## summary
Engineers learn from other people's crashes — if those crashes have been analyzed. This module takes three public investigations by government boards — the Matternet M2 in Zurich (2019, ArduCopter-based platform, failure due to vibration and EKF), the Alauda Airspeeder Mk II at Goodwood (2019, link loss and a kill switch that didn't work) and the Freefly Alta X in Henley (2022, battery depletion) — and breaks down each one using the same scheme: symptom → cause → what you see in the log → consequences → what to change in configuration and procedures. Each case ends with a line for your checklist.

## theory
### The analysis scheme
Board reports (AAIB in the UK, STSB/SUST in Switzerland, NTSB in the USA) are written with the same logic, and that logic is your tool too:

1. **Symptom** — what the operator saw.
2. **Sequence** — events in time order from logs and telemetry.
3. **Cause** — technical (what failed) and systemic (why it was possible).
4. **What you see in the data** — specific log messages, parameters, values.
5. **Consequences** — impact energy, who was nearby, what about the zone.
6. **Fix** — configuration, design, procedure.

Distinguish three types of causes: **hardware failure** (a part broke), **configuration error** (a parameter didn't fit the task), **operator error** (a procedure wasn't followed). In real crashes all three are almost always present.

### Case 1. Matternet M2, Zurich, May 9, 2019 (STSB, final report No. 2390, aircraft SUI-9903)
**Context.** A Swiss Post delivery quadcopter on a modified ArduCopter (based on 3.5.0-rc5), three IMUs, a flight termination system (FTS) with a parachute. Return flight without payload.

**Sequence.** Takeoff at 10:37:35. After ~50 s, vibration rose on all three IMUs (accelerations in places > 30 m/s²), and IMU3 produced sharp deviations while IMU1 and IMU2 showed consistent values; the aircraft started oscillating in pitch. At 10:38:46 the log shows `EKFCHECK_BAD_VARIANCE`; the error handler activated the FTS at ~185 m above the takeoff point (~100 m above ground): all four motors stopped, the parachute deployed. The parachute line snapped at its attachment on the aircraft; uncontrolled fall, destroyed at 10:38:48. The site: a forest, ~50 m from a group of children with their teachers, who didn't hear the warning signal.

**Causes.** Technical: increasing vibration of undetermined origin (probably a resonance from an external factor — prop damage or a bird strike) combined with insufficient robustness of the firmware against such an event. Systemic: the modified ArduCopter could run only two EKF lanes, `EK2_IMU_MASK = 5` (IMU1 and IMU3, without IMU2) — the faulty sensor couldn't be isolated; the FTS triggered an uncontrolled descent right away instead of attempting a controlled flight termination. The parachute line had been damaged by a sharp edge of the aluminum attachment even before deployment and didn't survive the jerk.

**What you see in the log.** `VIBE` rises on all IMUs, but the data of one IMU diverges sharply from the other two (a sign of a local source or sensor, not the frame as a whole); EKF innovations grow → `EKFCHECK_BAD_VARIANCE`; switch to the FTS.

**Consequences.** Impact energy ≈ 118 J without payload (above the 80 J accepted as the threshold for serious injury). The delivery program was suspended. Seven safety recommendations.

**Fixes (the real ones).** `EK2_IMU_MASK = 3` (two healthy IMUs + the ability to isolate), checking both EKF lanes at arming, a second safety line and a redesigned attachment, a 100 dB siren, a log analysis tool, parachute compliance with ASTM F3322, maximum speed reduced from 20 to 16 m/s. Board recommendation No. 591: pursue a redundant propulsion concept (the analysis noted that layouts with 6 or more motors have a significantly lower probability of failure).

**Line for your checklist:** “Per-IMU vibration in the log checked after every mechanical change; behavior on EKF failsafe known and tested in SITL”.

### Case 2. Alauda Airspeeder Mk II, Goodwood, July 4, 2019 (AAIB, report 03/2021)
**Context.** A 95 kg demonstration multirotor, an in-house flight controller with two IMUs, no GNSS and no RTH, controlled with a FrSky Taranis X9D radio + an R9M module on 915 MHz (10 mW, FCC mode — a band not permitted for airborne use in the UK). A separate kill switch on 433 MHz LoRa with its own battery, cutting the controller's power through a relay.

**Sequence.** ~65 s after takeoff — a sudden uncommanded transition to level attitude, then link loss. On link loss the controller **froze the last throttle commands and held level** — the aircraft kept climbing at ~2000 ft/min while rotating at ~40°/s for 4 min 12 s up to ~7900 ft, and entered the controlled airspace of a Gatwick holding area. On the “kill” command the observer activated the switch — with no effect. After the battery was depleted, the aircraft flipped over and fell at ~4500 ft/min into a field 40 m from houses, 700 m outside the authorized area. Impact energy ≈ 24,800 J. No injuries.

**Causes.** The exact cause of the link loss was not determined: **there was no onboard recording**, the boards were destroyed. Systemic causes found by the board: the link-loss failsafe was designed as “hold throttle” rather than “descend/land”; the kill switch had no feedback (loss of its channel wasn't detected), with a relay in the normally closed state (a switch failure goes unnoticed until the moment you need it), on a breadboard with jumper wires, activated by a voice command instead of automatically; in the wreckage the relay and the power wire were disconnected from the board. The aircraft was not designed or tested to any standard: mounting with Velcro and zip ties, Ethernet cables as ESC signal lines, soldering with jumpers, a 42–58 V battery with no protection at all; no vibration tests, no RF tests. Speed in flight up to 25 m/s against a declared limit of 11 m/s.

**What you see in the data.** Nothing — and that's the main lesson: without a log an investigation ends with the words “not determined”.

**Fixes.** 15 recommendations to the regulator and the operator. For you: failsafe must put the aircraft into a safe state (descend/land/RTH), not “hold”; the emergency circuit needs feedback and self-diagnostics; single points of failure — counted; onboard recording — always.

**Line for your checklist:** “Failsafe tested by switching off the radio on the ground without props before the first flight of every new configuration; blackbox enabled”.

### Case 3. Freefly Alta X, Henley-on-Thames, June 29, 2022 (AAIB, bulletin 01/2023)
**Context.** Commercial filming of a regatta, a 28 kg multirotor (MTOW 34.9) on two 12S LiPos, 50.4 V when fully charged. The 21st flight of the day, the 6th on this battery set, while the intention was to swap them every three flights.

**Sequence.** At ~50 m the low-voltage warning went off. During the return the voltage kept dropping and controlled flight was lost; the aircraft, almost in free fall (≈ 30 m/s), hit a boat on the river. No injuries; impact energy ≈ 13,700 J — the board noted that hitting a person would have been fatal. **No logs** — the aircraft wasn't recovered.

**Causes.** Configuration error: the pilot had lowered the warning threshold from 44 V (the manufacturer's default, “land as soon as possible”) to 42 V — the margin to critical voltage was cut by 2 V. Operator error: the voltage before takeoff was most likely not checked (the manufacturer requires > 48 V, the pilot “took off below 48 too”); the batteries weren't swapped as planned. No hardware failure was found.

**What you would have seen in the log.** Voltage under load below the threshold long before the warning; the warning triggering at a voltage that left seconds, not minutes.

**Fixes.** Thresholds no lower than the manufacturer's recommendations, and for your own batteries — based on the measured discharge curve; the pre-flight voltage check is a checklist item that can't be skipped; tracking the number of flights on each battery set.

**Line for your checklist:** “Battery voltage recorded before every takeoff; warning and failsafe thresholds justified by the discharge curve, not lowered for an extra minute”.

### Common patterns across the three cases
- In all three, the problem isn't a “bad part” but the **design of the behavior on failure**: what the aircraft does when something goes wrong.
- In two of the three **there was no data**; the investigation hit a wall of “not determined”. A log isn't for tuning, it's for answering the question “why”.
- In none of the cases was anyone injured — **and that's luck**, not a result: 50 m from children, 40 m from houses, a boat instead of a person.
- Impact energies of 118 J, 13,700 J, 24,800 J versus the ~80 J serious-injury threshold: even a light aircraft is dangerous, a heavy one is lethal.

{{diagram:incident-analysis|Crash analysis scheme following the logic of board reports — and the last step: what to change in your own process.}}

## practice
### Step 1. Read the primary source
Open one of the three reports (links below) and read the section with the sequence of events and the conclusions. Compare with the analysis above: what's in the report that isn't here.

### Step 2. Analyze two more incidents
Take two public cases (the AAIB publishes dozens of UAS reports; the “record-only” bulletins are short) and fill in the table using the six-item scheme, with links.

### Step 3. Your own incident
Your own crash or link loss (or a training one: a log from a forum) — the same scheme, from the log. If there's no log, that's your first conclusion.

### Step 4. Changes
For each of the five analyzed cases — one line in your pre-flight checklist or one parameter in your configuration, with a justification. Record it in the CHANGELOG of your engineering folder.

### Lab
A table analyzing three public incidents with links to the reports; for each — a change in your checklist or configuration; an analysis of one of your own incidents from the log.

### Analysis scheme and an example line
Six items for each case: what happened → sequence of events in time → immediate cause → root cause (the process, not the person) → what worked and what didn't → the change on your side. Example result line: “Report X (link): GNSS loss near a metal structure → root: position-based flight without checking navigation quality → on my side: checklist item "HDOP and satellite count at the site", in the config — a GNSS quality warning”.

### What you should end up with
- A table of three public cases: each with a link to the primary report, not to a retelling.
- Every conclusion turned into a concrete action — a checklist line, a parameter or a site rule, not “be more careful”.
- Your own incident analyzed from the log with the same scheme. If there's no log, the first measure is to enable logging. This isn't a joke, it's the most common real-world conclusion.
- Entries in the CHANGELOG of your engineering folder: date, change, link to the case that led to it.

The lab counts as done when three public incidents are analyzed using the scheme with links to sources, each has a concrete change in your checklist or config, and one of your own (or a training) incident is analyzed from the log.

## diagnostics
- **Symptom:** the analysis of your crash ends with “I don't know why”
  - Possible cause: there was no onboard recording or telemetry.
  - In the log/on the instrument: nothing to look at.
  - Consequences: the cause will repeat.
  - What to do: enable Blackbox/DataFlash on all flights, record a tlog on the GCS.
- **Symptom:** failsafe is “configured” but has never been tested
  - Possible cause: no ground test in the procedure.
  - In the log/on the instrument: no failsafe event in the log over the aircraft's entire history.
  - Consequences: like the Airspeeder — the aircraft doesn't do what you think it does.
  - What to do: a test without props for every new configuration, the result goes in the test table.
- **Symptom:** battery thresholds lowered “to fly longer”
  - Possible cause: margin sacrificed for flight time.
  - In the log/on the instrument: voltage under load near the critical level before the warning triggers.
  - Consequences: like the Alta X — a fall in free fall.
  - What to do: thresholds based on your batteries' discharge curve, no lower than the manufacturer's recommendations.
- **Symptom:** vibration rose on only one IMU
  - Possible cause: a local source (mounting, sensor) or damage.
  - In the log/on the instrument: per-IMU `VIBE` diverges, EKF innovations grow.
  - Consequences: EKF failsafe; for Matternet — the FTS.
  - What to do: land, inspect the props and the mounting; an IMU mask that lets you isolate a faulty sensor.

## references
- STSB (SUST) — Final report SUI-9903, Matternet M2 V9, Zürich, 9 May 2019 (PDF) | https://www.sust.admin.ch/inhalte/AV-berichte/SUI-9903_SB_e.pdf | primary | A
- AAIB — Investigation to Alauda Airspeeder Mk II (UAS), Goodwood, 4 July 2019 | https://www.gov.uk/aaib-reports/aaib-investigation-to-alauda-airspeeder-mk-ii-uas-registration-n-slash-a-040719 | primary | A
- AAIB — Investigation to Freefly Systems Inc. Alta X (UAS), Henley-on-Thames, 29 June 2022 | https://www.gov.uk/aaib-reports/aaib-investigation-to-freefly-systems-inc-alta-x-uas-registration-n-slash-a | primary | A
- AAIB — all UAS reports (search) | https://www.gov.uk/aaib-reports?keywords=UAS | primary | A

## checklist
- I know the six-item analysis scheme and the three types of causes
- I've read at least one primary source in full
- Three public incidents analyzed with links
- My own incident analyzed from the log (or the conclusion drawn that there wasn't one)
- Five changes made to the checklist/configuration and recorded in the CHANGELOG
