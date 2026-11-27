---
id: ops-pilot-training
title: "How to learn to fly: simulator, acro and the first hundred batteries"
level: L1
readingTime: 45 min
firmware: Betaflight 2025.12 (checked against 2025.12.5) · EdgeTX 2.12.5
status: published
added: 2026-11-18
tags:
  - piloting
  - simulator
  - acro
  - rates
  - training
related:
  - bf-rates-rc
  - bf-arming-safety
  - diag-troubleshooting
  - ops-field
  - f-safety
  - f-regulations
next:
  - bf-intro
source: content/foundation/ops-pilot-training.md
source_hash: f9f59576be99
---

## summary
A tuned aircraft is useless until your hands know how to control it, and learning on a real one means paying with propellers, motors and other people's safety. This module gives the order of training: a simulator with your own radio in USB joystick mode, Acro mode from the first hour, the same rates in the simulator and in Betaflight, a ladder of exercises with verifiable criteria, a whoop indoors, the first flights in a field with a spotter, and a training log up to the hundredth battery. After this module you can read rates from a configuration and calculate °/s from them, choose a simulator for your computer and draw up a personal plan with measurable gates between the rungs. The lab: a calculation with the real `applyActualRates` formula and a four-week training plan.

## theory
### Why the simulator comes first and how many hours
A simulator teaches one thing: the “eyes → fingers” link. It does not convey fear, wind, battery sag or video interference, but a crash in it costs a press of the reset button.

How many hours are needed before the first real flight — there is no single figure, and the sources disagree:

| Source | What it says | Date |
|---|---|---|
| Oscar Liang, beginner's guide | “at least 5 to 10 hours” in a simulator before the first flight | updated in November 2026 |
| Unmanned Tech, knowledge base | “Most pilots benefit from 10-20 hours”; also there: the quality of practice matters more than the quantity | March 2026 |
| RotorVillage, store blog | “10 to 15 hours”, the minimum — “at least three hours” | April 2026 |
| Simulator pages (Steam, velocidrone.com) | do not name a number of hours | verified 18.11.2026 |
| IntoFPV forum, the thread “starting out with no simulator” | opinions differ: some pilots hardly flew in a simulator, some consider it mandatory | May 2021 |

The course's conclusion: hours are a time estimate, not a criterion. The criterion is an exercise performed to its condition (the ladder below). The 5–20 hour range shows how long the first four rungs usually take.

### Your own radio instead of a gamepad
Simulators accept a gamepad and a keyboard, but learning on them is not worth it. Oscar Liang: “Avoid using Xbox controllers or keyboards for simulator training”. The reason is mechanical: on a gamepad both sticks are spring-loaded and the travel is short, while on a radio the throttle stick stays where it was left. You will have to buy a radio anyway, so muscle memory is built on it from the first hour.

An EdgeTX radio (the current stable version is 2.12.5) connects with a USB cable as an HID joystick; no receiver or aircraft is needed:
- **Radio Setup → USB Mode**: `Ask`, `Joystick`, `Storage`, `Serial` — what the radio does when the cable is connected. With `Ask` the radio asks for the mode every time; this is the default value (2.12.5 source, `hal/usb_driver.h`).
- **Model Setup → USB Joystick → Classic**: channels 1–8 go to the axes X, Y, Z, rotX, rotY, rotZ, Dial, Slider, channels 9–32 — to buttons 1–24. The simulator will see the arm switch on channel 5 as an axis.
- **Advanced**: `Interface mode` (`Joystick` / `Gamepad` / `MultiAxis`), `Circular cutout` and the mode of each channel (`None`, `Btn`, `Axis`, `Sim`). The manual advises starting with Classic. Windows may detect the radio only as a Joystick. After changing the settings the cable must be reconnected. Black-and-white radios with less than 1 MB of flash have no Advanced mode.

Create a separate model for the simulator with the RF module turned off, and in the simulator itself go through stick calibration and assign arm to the same switch that will be used on the aircraft. How to build a model and set up the radio itself is in `link-edgetx`.

### Simulators
Prices and requirements are taken from the store pages on 18.11.2026; the “what for” assessments are from Oscar Liang's review (August 2026).

| Simulator | Price | Platforms | Minimum per the page | What for | Caveats |
|---|---|---|---|---|---|
| Liftoff: FPV Drone Racing | $19.99, Steam | Windows, macOS, Linux | 8 GB RAM, RTX 2060 or RX Vega 56 (4 GB) | general start, freestyle, racing | does not launch without a radio or gamepad |
| VelociDrone | £16.99 base license, its own site | Windows, macOS, Linux | 1.7 GHz, Intel HD 530, 4 GB RAM | racing; a weak computer | aircraft packs £4–8 separately |
| Uncrashed | $14.99, Steam | Windows, macOS | Core i5 2.6 GHz, 4 GB RAM, GTX 770 (2 GB) | freestyle | per the review, in practice it needs a powerful gaming PC |
| DRL Simulator | $9.99, Steam | Windows, macOS | Core i5-4460, 8 GB RAM, GTX 650 (2 GB) | racing, built-in tutorial | review of 17.01.2026: the servers are shut down, buying is not advised; there is no note on the Steam page |
| TRYP FPV | $16.99, Steam, early access since 2022 | Windows, macOS | 4 cores at 2.4 GHz, 8 GB RAM, GTX 960 or RX 460 | large maps, cinematic flying | per the review, demanding on hardware |
| FPV SkyDive | free, Steam; DLC $5.99–10.99 | Windows, macOS, Linux | Core i5, 8 GB RAM, GTX 650 (2 GB) | a free way in | the paid add-ons are optional |
| WebFPV, FlowState | free | browser; Windows | not stated | checking that the radio is seen as a joystick | the physics is simpler than in the paid ones |
| Liftoff: Micro Drones | $5.99, Steam | Windows, macOS, Linux | not verified | a whoop before flying at home | a separate game |

How to choose: a weak laptop — VelociDrone or SkyDive; a gaming PC — Liftoff, Uncrashed or TRYP. More important than the brand are a stable frame rate and one simulator for the whole training period. The physics differs in all of them, so the transfer to a real aircraft gives the skill, not the exact feel.

### Rates: the same numbers in the simulator and in Betaflight
Rates translate stick deflection into a commanded angular rate. In Betaflight 2025.12 the default type is `ACTUAL`, and the formula in `applyActualRates` (`fc/rc.c`) is:

ω(x) = C·x + (M − C)·|x|·(x⁵·e + x·(1 − e)), where C = `rc_rate`·10, M = `srate`·10, e = `expo`/100, x is the stick deflection from 0 to 1.

C is the rate “at center” (Center Sensitivity), M is at full stick (Max Rate), and e changes only the shape of the curve. The default is 7/67/0: center 70 °/s, maximum 670 °/s. A full rotation at full stick takes 360/M seconds: 0.54 s at 670 °/s.

{{diagram:chart-pilot-training-rates|At half stick travel the three profiles give 185, 145 and 171 °/s: the 15/60/40 training profile is sharper than the default near center (up to a quarter of the travel) and calmer over the rest of the travel.}}

Reference values by style from Oscar Liang's article on rates (July 2026) — these are the author's recommendations, not a norm:

| Style | Center Sensitivity, °/s | Max Rate, °/s | Expo |
|---|---|---|---|
| Freestyle | 100–200 | 800–1000 | 0.5–0.7 |
| Racing | 150–250 | 600–800 | 0.4–0.6 |
| Cinematic | 50–150 | 600–800 | 0.6–0.8 |
| This module's training profile | 150 | 600 | 0.40 |

The same article says that there are no universal “best” rates and that a beginner should not rush to change them; the article on Acro says “default rates are usually fine”. The course has one rule: the simulator and the aircraft have the same type and numbers, and they do not change until the rung is passed. If the simulator has only the Betaflight type, Actual numbers must not be carried over to it: they are converted (module `bf-rates-rc`).

Settings the learner touches:

| Parameter | Where | Default | Range | Unit | Training value | Note |
|---|---|---|---|---|---|---|
| `rates_type` | Betaflight, rate profile | `ACTUAL` | BETAFLIGHT, RACEFLIGHT, KISS, ACTUAL, QUICK | — | `ACTUAL` | the numbers are not converted when the type is changed |
| `roll_rc_rate`, `pitch_rc_rate`, `yaw_rc_rate` | same | 7 | 1–255, for Actual up to 200 | ×10 °/s | 15 (yaw 12) | in the App — Center Sensitivity |
| `roll_srate`, `pitch_srate`, `yaw_srate` | same | 67 | 0–255, for Actual up to 200 | ×10 °/s | 60 (yaw 50) | in the App — Max Rate |
| `roll_expo`, `pitch_expo`, `yaw_expo` | same | 0 | 0–100 | hundredths | 40 (yaw 30) | in the App — Expo 0.40 |
| `throttle_limit_type` | same | `OFF` | OFF, SCALE, CLIP | — | `SCALE` on the first 5″ batteries | SCALE multiplies the throttle, CLIP cuts it off at the top |
| `throttle_limit_percent` | same | 100 | 25–100 | % | 70–80 (course reference) | return to 100 after rung 3 |
| `angle_limit` | Betaflight, PID profile | 60 | 10–80 (in 4.5: 10–85) | ° | do not change | the tilt limit in ANGLE |
| `acro_trainer_angle_limit` | same | 20 | 10–80 | ° | start at 20 (the default), by 5–10° up to 45 once flips to the limit stop being scary (course reference) | ACRO TRAINER mode, needs the accelerometer |
| `horizon_limit_degrees` | same | 135 | 10–250 | ° | do not use | HORIZON mode |
| `landing_disarm_threshold` | same | 0 (off) | 0–250 | — | 0 | appeared in 2025.12 |
| USB Mode | EdgeTX, Radio Setup | `Ask` (per the 2.12.5 source) | Ask, Joystick, Storage, Serial | — | `Ask` or `Joystick` | — |
| USB Joystick | EdgeTX, Model Setup | not stated in the manual | Classic, Advanced | — | Classic | Advanced — if the simulator mixes up the axes |

### Angle, Horizon, Acro
- **ANGLE** — the stick sets the tilt angle. Let go — the aircraft levels out. The tilt is limited by `angle_limit` (60°), and a flip is impossible.
- **HORIZON** — near stick center it behaves like ANGLE, and with growing deflection it transitions to angular rate. Oscar Liang: “Horizon mode can feel inconsistent” — the same finger movement gives a different result depending on how far the stick has gone.
- **Acro (Rate)** — the mode with neither ANGLE nor HORIZON selected, that is, Betaflight's default state. The stick sets the rotation rate; let go — the aircraft keeps the tilt it ended up in.
- **ACRO TRAINER** — Acro with an angle limit (`acro_trainer_angle_limit`, 20°): the motor skills of acro, but you cannot flip over.

The throttle is manual in all four modes. `ALTHOLD` and `POS HOLD` in 2025.12 are separate modes and have nothing to do with learning to pilot.

Why Acro is taught. In ANGLE, to fly forward you hold the stick deflected; in Acro you tilt the aircraft and return the stick. These are different skills, and the first gets in the way of the second. Besides, beyond the 60° limit ANGLE has no dives, no flips and no quick braking. The order that agrees with the sources: Acro in the simulator from the first hour; ANGLE is acceptable on the first real batteries and for checking a hover by line of sight; skip HORIZON. The forum also describes workable detours (ANGLE → ACRO TRAINER → Acro), so this is a recommendation, not a law.

### Sticks, grip and throttle
**Mode 2** is the layout of most FPV pilots: the left stick is throttle and yaw, the right one is pitch and roll. In Mode 1 throttle and pitch are swapped. The layout is chosen once: relearning is expensive.

**Grip.** Thumbs (thumbs on top) is easier to learn and comfortable on compact radios. Pinch (a pinch with the thumb and index finger) is more precise in small movements, but it requires a large radio and often a neck strap. Hybrid pinch — the thumb on top, the index finger at the side. The reviews agree that there is no “best” grip; what matters is not changing it in the middle of training.

**Throttle.** A beginner's mistakes are almost always in the left stick. Thrust is directed along the aircraft's axis, so at a tilt angle φ only the cos φ share remains vertical. To keep from losing altitude, thrust has to be raised by a factor of n = 1/cos φ: at 30° that is 1.15, at 45° — 1.41, at 60° — 2.0. For a level turn at a speed v the radius is r = v²/(g·tan φ), and the turn rate is ω = g·tan φ/v. At 10 m/s and a 45° roll you get r = 10.2 m and ω = 56 °/s. Hence three conclusions for training: in a turn, throttle is added before the altitude has dropped; yaw and pitch in a turn are in the tens of °/s (ω·cos φ and ω·sin φ), which is less than a quarter of the stick travel; a sharp upward throttle movement in fright carries the aircraft tens of meters away in a second.

### The ladder of exercises
The criteria are the course's training gates, not a community standard. An exercise counts as done when its condition has been met in two training sessions in a row — according to the entries in your log.

| No. | Exercise | What it trains | Completion criterion |
|---|---|---|---|
| 1 | Hover | throttle, fine corrections | 60 s over a landmark at a height of 1–3 m without touching the ground, 3 times in a row |
| 2 | Takeoff, circuit, landing | the full flight cycle | 10 landings in a row inside a 2 m circle without flipping over |
| 3 | Figure eight around two objects | turns in both directions, altitude in the turn | 5 laps in a row without a reset, altitude no higher than the objects |
| 4 | Orbit with the nose toward an object | roll, yaw and throttle at the same time | 3 laps in each direction, the object does not leave the frame |
| 5 | Split-S | a flip, losing altitude under control | 5 out of 5, exit no lower than half the entry height |
| 6 | Power loop over an object | throttle at the top | 5 out of 5, exit on the entry line |
| 7 | Gaps | trajectory accuracy | 9 out of 10 through a 2×2 m gate, then 1×1 m |
| 8 | Proximity | flying near a surface | 3 passes of 100 m within 1 m of the ground without touching |
| 9 | Disarm on command (in the simulator; on a real aircraft — only on the ground or in a hover no higher than 0.5 m over grass, with no people nearby) | the emergency reflex | 10 out of 10: the switch within 1 s after an unexpected signal (a timer with a random interval or the spotter's command) |

The gate from the simulator to the whoop: exercise 3 (figure eight, 5 laps without a reset) has been done to the criterion in two training sessions in a row; keep practicing exercises 4–6 in the simulator in parallel with the whoop.

{{diagram:pilot-training-ladder|Under each rung is the condition for leaving it: you move to the next one on a met condition, not on a number of hours.}}

### Onto a real aircraft
**A whoop indoors.** The 65–75 mm class on 1S with prop guards is almost harmless and survives hitting walls (construction and setup — `f-micro-whoop`). The job is to get used to real video, latency and battery sag. The gate: three batteries in a row without touching the walls on exercises 1–3.

**Flying by line of sight (LOS).** You need to be able to hover without goggles: if the video fails, the aircraft is landed by eye. You start tail-in, at a height of 1–2 m, and ANGLE is acceptable. When the aircraft is turned nose toward the pilot, roll and yaw are mirrored for the observer — this is the main cause of losing orientation in line-of-sight flying.

**The first flights in a field.** An open place without people, animals or roads, grass instead of asphalt, rules and zones per the module `f-regulations`, the flight session protocol per `ops-field`. The spotter watches the aircraft and the surroundings and speaks to the pilot briefly. The first batteries: takeoff, a circuit in front of you, landing. The altitude and distance are such that the spotter can see the aircraft.

**Milestones by batteries** (course reference values; at 4 minutes per battery a hundred of them is 6.7 hours of flight time):

| Batteries | What you do | What is not there yet |
|---|---|---|
| 1–10 | exercises 1–2, `throttle_limit_percent` 70–80 on a 5″ | tricks, flying behind your back |
| 11–30 | exercises 3–4 at a height of 3–10 m | gaps |
| 31–60 | exercises 5–6 with an altitude margin | proximity |
| 61–100 | exercises 7–8, your own style | — |

### Typical mistakes
| Mistake | Why it happens | Correction |
|---|---|---|
| Throttle to the floor or to the ceiling in fright | the hand reacts before the head | exercise 9; `throttle_limit_percent` on the first batteries; the reflex “throttle to hover, sticks to center” |
| Losing altitude in a turn | vertical thrust falls as cos φ | add throttle together with roll: at 45° — 1.4 times in thrust |
| Losing orientation | no horizon in the frame, too high or too far | stop the rotation, find the horizon, then throttle; in the field — large landmarks |
| Flying behind your back and overhead | the spotter and the pilot lose sight of the aircraft, the body and head block the antennas | the working zone is only in front of you; antennas and patterns — modules `rf-antennas`, `link-vtx` |
| A reset instead of a landing in the simulator | the habit of the button | end every attempt with a landing |

### The disarm reflex
For a light aircraft over an empty field the rule is simple: you lost control near the ground or an impact is inevitable — disarm before touching down. Motors that keep spinning in grass or in branches burn the windings and the ESCs and cut fingers. Oscar Liang puts it the same way: “stay close to the ground, disarm quickly if you are losing control to minimize damage”.

This is part of the recovery reflex from `diag-troubleshooting`, not a replacement for it: there, disarming in the air is the last resort, acceptable in four cases. The fourth one is described here: a light aircraft (a whoop, 3–5″) right at the ground over an empty area, when an impact is already inevitable. At altitude a disarm turns the aircraft into a falling object, so with an altitude margin, over people and with a heavy aircraft it is throttle and steering away first. How Betaflight processes the switch (more than three frames in a row with ARM off), what airmode does after landing and why the aircraft does not arm again — in `bf-arming-safety`. The arm switch is put on a two-position switch that the finger can reach without letting go of the stick.

### Motion sickness in goggles
In goggles the eyes see motion while the vestibular system does not feel it. The sensory conflict theory is the most widespread one, but not the only one. No direct studies for FPV goggles could be found; the closest data are for VR. In the work of Adhanom and co-authors (2022; 19 participants, five days in a row, no control group) the nausea score on the SSQ questionnaire went down from 40.7 to 12.1 — adaptation works, but the size of the effect is unreliable. Pilots' practice: the first sessions seated and one battery at a time, stopping at the first signs rather than “toughing it out”, a break until the symptoms are completely gone. A simulator on a monitor causes sickness less often and will do until the goggles are mastered.

### The training log
One line per session: the date; simulator or aircraft; minutes or number of batteries; the exercise; the result in the units of the criterion (figure eight: 3 laps out of 5); the rate profile; incidents and breakages. The log answers two questions: whether the rung is passed and what breaks most often. The aircraft log from `ops-maintenance` is kept separately.

### Place in the system
- **Receives:** safety rules and zones (`f-safety`, `f-regulations`); rates and the throttle curve as numbers (`bf-rates-rc`); the behavior of arm, disarm and airmode (`bf-arming-safety`); the flight session protocol and roles (`ops-field`).
- **Provides:** a pilot who can perform the first hover and the test flights during setup (`bf-intro`, `bf-setup-scratch`); a log with flight time and incidents — to maintenance (`ops-maintenance`) and analysis (`diag-troubleshooting`).
- **If you get it wrong here:** different rates in the simulator and on the aircraft look like “bad PIDs” and lead to needless retuning; the ANGLE habit and abrupt throttle give crashes that are searched for in failsafe and the link (`bf-failsafe`), although the cause is in the hands.

## practice
The practice is a calculation: no simulator or aircraft is needed, only a calculator. The configuration fragment below was composed for the exercise — it is not a dump from a specific aircraft.

### Step 1. Read the rates from the configuration
```
set rates_type = ACTUAL
set roll_rc_rate = 15
set pitch_rc_rate = 15
set yaw_rc_rate = 12
set roll_expo = 40
set pitch_expo = 40
set yaw_expo = 30
set roll_srate = 60
set pitch_srate = 60
set yaw_srate = 50
```
Convert them to the numbers that Betaflight App shows. Roll and pitch: Center Sensitivity 15·10 = 150 °/s, Max Rate 60·10 = 600 °/s, Expo 0.40. Yaw: 120 °/s, 500 °/s, 0.30. Write the six numbers in the log — this is your profile for the whole training period.

### Step 2. Calculate °/s at half and at full stick
The `applyActualRates` formula: ω = C·x + (M − C)·|x|·(x⁵·e + x·(1 − e)).

Roll, x = 0.5: 150·0.5 + (600 − 150)·0.5·(0.5⁵·0.4 + 0.5·0.6) = 75 + 225·(0.0125 + 0.3) = 75 + 70.3 = **145.3 °/s**.
Roll, x = 1: 150 + 450·1·(0.4 + 0.6) = **600 °/s**. A full rotation: 360/600 = **0.60 s**.

For comparison, the default 7/67/0 profile: at half travel 70·0.5 + 600·0.5·0.5 = 185 °/s, at full — 670 °/s, a rotation in 0.54 s. The training profile is 40 °/s slower at half stick, although at center it is twice as sharp. Calculate yaw at x = 0.5 yourself; it should come out at 128.3 °/s.

### Step 3. Find the matching simulator profile
Three profiles are saved in the simulator. Which one corresponds to the configuration from step 1?

| Profile | Type | Numbers |
|---|---|---|
| A | Actual | Center 150, Max 600, Expo 0.40 |
| B | Betaflight | RC Rate 1.50, Super Rate 0.60, Expo 0.40 |
| C | Actual | Center 70, Max 670, Expo 0.00 |

Checking B with the Betaflight-type formulas: center 200·1.5·(1 − 0.4) = 180 °/s, maximum 200·1.5/(1 − 0.6) = 750 °/s. The digits in the fields are the same as in the configuration, but the aircraft is 150 °/s faster at full stick. C is the default profile. The answer: **A**.

### Step 4. An orbit in numbers
Speed 10 m/s, roll 45°. The radius r = v²/(g·tan φ) = 100/9.81 = 10.2 m. The angular rate ω = g·tan φ/v = 0.98 rad/s = 56 °/s, a lap in 6.4 s. Thrust has to grow by a factor of 1/cos 45° = 1.41. In the aircraft's axes this is a yaw of ω·cos 45° ≈ 40 °/s and a pitch of ω·sin 45° ≈ 40 °/s. By the formula from step 2, a 12/50/30 yaw at x = 0.25 gives 46.7 °/s, so the turn requires less than a quarter of the yaw stick travel. Repeat the calculation for 5 m/s and a 30° roll; the expected answer: r = 4.4 m, ω = 65 °/s, n = 1.15.

### Step 5. A personal training plan
Fill in the table for four weeks. An example for 5 training sessions a week of 30 minutes each — that is 10 hours, the lower half of the range from the theory:

| Week | Exercises | Exit criterion | Where |
|---|---|---|---|
| 1 | 1, 2, 9 | 10 landings in a row inside a 2 m circle; disarm 10 out of 10 | simulator |
| 2 | 3, 4 | 5 figure-eight laps without a reset; orbit, 3 laps in both directions | simulator |
| 3 | 5, 6; whoop: 1–3 | split-S 5 out of 5; 3 batteries without touching the walls | simulator, indoors |
| 4 | field: 1–2 | 10 batteries of “takeoff — circuit — landing” with a spotter | field |

In your own plan state: the hours per week, the simulator, the rate profile from step 1, the criterion for every week in numbers, and what you do if the criterion is not met (there is one answer: the week is repeated, the next rung does not open).

### Moving to real hardware
1. Radio: a model for the simulator, USB Mode `Ask`, a cable with data lines. In the simulator after calibration all four axes reach their endpoints, and arm is assigned to the same switch as on the aircraft.
2. Aircraft, **propellers off**: the Rateprofile Settings sub-tab of the PID Tuning tab in Betaflight App (Rate Profile Settings in App builds after 2025.12) shows the same six numbers as in the simulator; the arm switch is checked in the Modes tab.
3. Whoop: the first battery — only hovering and landings, disarm right after touchdown.
4. Field: the propellers are fitted at the site, the spotter is named, exercise 9 has been done once on the ground before the first takeoff.

The criterion for hardware: a log line with the date, the number of batteries, the exercise and the result in the units of the criterion.

Self-check: the lab is complete when: (1) the six profile numbers from step 1 matched 150 / 600 / 0.40 for roll and pitch and 120 / 500 / 0.30 for yaw; (2) you obtained 145.3 °/s and 600 °/s for roll and 128.3 °/s for yaw with a discrepancy of no more than 1 °/s; (3) profile A is chosen, and two numbers are written against B — 180 and 750 °/s instead of 150 and 600; (4) the orbit calculation for 5 m/s and 30° gave r = 4.4 m, ω = 65 °/s, n = 1.15 with a discrepancy of no more than 2 %; (5) in the four-week plan every week has a criterion in the units of the exercise ladder (laps, landings, batteries, “N out of N”) and the rule of repeating a week is written down. Items 1–5 are done without hardware; for the hardware path a line in your log for the first session is added.

**Reference for self-check.** The correct answer to step 3 is a comparison by the formulas of the type, not by the digits in the fields: B has a center of 180 °/s and a maximum of 750 °/s, and at full stick it is 150 °/s faster than the configuration. Two common mistakes: B is chosen because the digits 1.50 / 0.60 / 0.40 look the same (the rate type is not taken into account), and C is chosen because the profile from step 1 is confused with the default 7/67/0. In step 2 a result of 70.3 °/s instead of 145.3 means that the term C·x = 75 was lost, and 300 °/s — that the maximum was simply multiplied by x. A correct plan in step 5 is one where every week is closed by a log line of the form “10 landings out of 10” or “3 laps out of 5”; “I fly more confidently” and “I logged 5 hours” are not criteria.

## diagnostics
- **Symptom:** in the simulator the aircraft obeys, while the real one feels “twitchy” or “mushy”.
  Possible cause: different rates or rate type; a different camera angle.
  What to do: compare the six numbers and `rates_type` with the simulator profile; set the same camera angle in the simulator.
- **Symptom:** the simulator does not see the radio or the axes are mixed up.
  Possible cause: Storage mode is selected; a cable without data lines; Advanced mode with an unsuitable `Interface mode`.
  What to do: USB Mode `Joystick`, go back to Classic, reconnect the cable, go through calibration in the simulator again.
- **Symptom:** the aircraft “jumps” upward at every fright.
  Possible cause: reflexive throttle.
  What to do: `throttle_limit_type = SCALE`, `throttle_limit_percent` 70–80; exercises 1 and 9 until they are automatic.
- **Symptom:** in turns the aircraft sinks and clips the ground.
  Possible cause: throttle is not added with roll.
  What to do: a figure eight at a height of 5 m with the task of holding altitude; recall n = 1/cos φ.
- **Symptom:** after a crash the motors keep spinning in the grass.
  Possible cause: the disarm has not become a reflex or the switch is awkward.
  What to do: move arm to a two-position switch under the finger; exercise 9; arm behavior — `bf-arming-safety`.
  Consequences: burned windings and ESC, cuts when trying to pick up the aircraft.
- **Symptom:** nausea after a few minutes in goggles.
  Possible cause: sensory conflict, a first session that is too long.
  What to do: fly seated, one battery at a time, stop at the first signs; the simulator — on a monitor.
- **Symptom:** progress has stalled, the same crashes over and over.
  Possible cause: training without a criterion, changing rates and simulators.
  What to do: go back to the last rung passed, lock the profile, record the result in the units of the criterion.

## checklist
- I learn on my own radio in USB Joystick mode, not on a gamepad
- The simulator and the aircraft have one rate type and the same numbers
- I fly in Acro; I use ANGLE only for a line-of-sight check
- I move to the next rung on a met criterion, not on hours
- I perform a disarm on command within a second
- In the field I fly in front of myself, with a spotter, over grass
- I keep a log: date, time or batteries, exercise, result

## references
- Betaflight `fc/rc.c`, tag 2025.12.5 (`applyActualRates`, `applyBetaflightRates`) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/fc/rc.c | primary | A
- Betaflight `fc/controlrate_profile.c`, tag 2025.12.5 (defaults 7/67/0, limits by type) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/fc/controlrate_profile.c | primary | A
- Betaflight `cli/settings.c`, tag 2025.12.5 (ranges of `throttle_limit_*`, `angle_limit`, `acro_trainer_*`) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/cli/settings.c | primary | A
- Betaflight — Modes (ANGLE, HORIZON, ACRO TRAINER, AIR MODE) | https://betaflight.com/docs/wiki/guides/current/Modes | primary | A
- EdgeTX User Manual v2.12 — USB Joystick | https://manual.edgetx.org/color-radios/model-settings/model-setup/usb-joystick | primary | A
- EdgeTX User Manual v2.12 — Radio Setup (USB Mode) | https://manual.edgetx.org/color-radios/radio-settings/radio-setup | primary | A
- EdgeTX — Configure advanced joystick | https://manual.edgetx.org/edgetx-how-to/configure-advanced-joystick-with-edgetx | primary | A
- EdgeTX — project site (current release 2.12.5) | https://edgetx.org/ | primary | A
- EdgeTX, source code, tag v2.12.5 — radio/src/hal/usb_driver.h (USB Mode `Ask` by default) | https://github.com/EdgeTX/edgetx/blob/v2.12.5/radio/src/hal/usb_driver.h | primary | A
- Liftoff: FPV Drone Racing — Steam page (price, requirements) | https://store.steampowered.com/app/410340/Liftoff | primary | B
- VelociDrone — shop (license price, minimum requirements) | https://velocidrone.com/shop | primary | B
- Uncrashed: FPV Drone Simulator — Steam page | https://store.steampowered.com/app/1682970/ | primary | B
- TRYP FPV: Drone Racer Simulator — Steam page | https://store.steampowered.com/app/1881200 | primary | B
- The Drone Racing League Simulator — Steam page | https://store.steampowered.com/app/641780 | primary | B
- FPV SkyDive — Steam page | https://store.steampowered.com/app/1278060 | primary | B
- Adhanom I., Halow S., Folmer E., MacNeilage P. VR Sickness Adaptation With Ramped Optic Flow Transfers From Abstract To Realistic Environments. Frontiers in Virtual Reality, 2022 | https://frontiersin.org/journals/virtual-reality/articles/10.3389/frvir.2022.848001/full | primary | B
- Oscar Liang — FPV Drone Guide for Beginners (simulator hours, gamepad, Mode 2, first flights) | https://oscarliang.com/fpv-drone-guide/ | secondary | B
- Oscar Liang — FPV Simulators (comparison, prices, the DRL warning) | https://oscarliang.com/fpv-simulator/ | secondary | B
- Oscar Liang — Why You Should Fly Acro Mode and NOT Angle or Horizon Mode | https://oscarliang.com/acro-angle-horizon-modes/ | secondary | B
- Oscar Liang — FPV Drone Rates and Expo Explained (Actual ranges by style) | https://oscarliang.com/rates/ | secondary | B
- Oscar Liang — Thumb, Pinch, or Hybrid-Pinch? | https://oscarliang.com/pinch-thumb-stick | secondary | B
- GetFPV Learn — Control Methods: Thumbs vs. Pinch | https://www.getfpv.com/learn/fpv-flight-academy/control-methods-thumbs-vs-pinch/ | secondary | B
- Unmanned Tech — FPV Simulator Guide: Practice Before You Fly (10–20 hours) | https://www.unmannedtechshop.co.uk/blogs/knowledge-base/fpv-simulator-guide-practice-before-you-fly | secondary | C
- RotorVillage — Why Every FPV Beginner Should Start with a Simulator (10–15 hours) | https://rotorvillage.ca/blog/why-every-fpv-beginner-should-start-with-a-simulator-and-a-real-radio/ | secondary | C
- IntoFPV — Advice on starting out in FPV with no simulator (pilots' opinions, 2021) | https://intofpv.com/printthread.php?tid=16984 | secondary | C

## notes
What could not be verified against primary sources: the USB Joystick default in EdgeTX (not stated in the manual); support for the Actual type in each of the simulators (Oscar Liang writes “most popular FPV simulators”); the current status of the DRL Simulator servers (the review's warning and the Steam page disagree); the minimum requirements of Liftoff: Micro Drones. Prices are as of November 18, 2026, without regional markups and sales. The criteria of the exercise ladder, the milestones by batteries and the `throttle_limit_percent` values of 70–80 are the course's training reference values, not community data.
