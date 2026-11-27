---
id: ops-field
title: "Field Operations and Teamwork"
level: L2
readingTime: 25 min
firmware: any firmware
status: published
added: 2026-11-08
tags:
  - operations
  - team
  - protocol
related:
  - f-regulations
  - bf-failsafe
  - link-vtx
next:
  - bf-blackbox
source: content/foundation/ops-field.md
source_hash: 65453287f3a5
---

## summary
Most accidents happen not because of the firmware but because of organization: nobody checked the neighbors' frequencies, nobody agreed who watches the aircraft, there was no plan for loss of link. This module is about operations as a discipline: sortie planning, roles in the team, frequencies and communication, the pre-flight and post-flight protocol, actions in an incident and searching for a crashed aircraft. Based on the practice of several pilots working at one site.

## theory
### Sortie planning
Before leaving you know: the site and the zones (the module on regulations), the weather (wind by altitude, precipitation, temperature — cold cuts LiPo capacity), the goal of the sortie and the success criteria, who takes part and in what roles, which frequencies the neighbors occupy.

### Roles
Even with two people it is worth naming the roles explicitly:

- **Pilot** — flies, and does nothing else.
- **Observer (spotter)** — watches the aircraft by eye and the surroundings: people, birds, other aircraft; talks to the pilot without distracting them.
- **Technician / GCS** — telemetry, parameters, logs, battery swaps, the timer.
- **Lead** — decides “go / no-go”, keeps the logbook.

One person can combine roles, but a pilot in flight is only a pilot.

### Frequencies and communication
- **Video**: a table of the channels occupied at the site; separation from the neighbors (guideline ≥ ~37 MHz for analog: the signal occupies ~20–27 MHz around the carrier, so closer than that the bands overlap; with four or more aircraft there is also intermodulation, `link-vtx`); a channel change — by the algorithm from the VTX module, on one aircraft first.
- **RC**: the binding phrase is unique; packet rate for the mission (`link-elrs`, “Choosing a mode for the mission”: freestyle and racing within line of sight — 2.4 GHz 250–500 Hz or F500, long-range 7–10" — 2.4 GHz 150 Hz or 900 MHz 100 Hz, wing and forest — 900 MHz 50–100 Hz); with several ELRS radios — different phrases, otherwise the hopping patterns will coincide.
- **Voice**: short standard phrases: “arming”, “taking off”, “link”, “low battery”, “landing”, “emergency”. The pilot confirms with one word.

### Protocols
**Pre-flight** (from the safety module, extended): frequencies agreed, roles named, battery voltage written down, failsafe tested on this aircraft, timer started at arming.

**Post-flight**: disarm, battery disconnected, motor temperature, inspection of the props and frame, a logbook entry (time, battery before/after, remarks), the log saved if it was a test sortie.

### Incidents
- **Loss of link**: the pilot reports it, everyone watches the aircraft, nobody runs. The aircraft does what the failsafe is configured to do — that is why the failsafe is tested in advance.
- **Crash**: the location from the last telemetry/video, the buzzer (BEEPER), GPS coordinates from the GCS log. Approaching a crashed aircraft — the battery may be damaged: do not touch it if it is hot/swollen, do not charge it.
- **Injury**: first aid, emergency services, then everything else.
- **Debrief**: what happened, from the log, without looking for someone to blame; the conclusion goes into the logbook and the checklist.

### Searching for a crashed aircraft
The search starts before the sortie: without coordinates and a buzzer, an aircraft in the grass is searched for for hours.

**Prepare in advance.**
- **Coordinates to the radio and into the log.** GPS on board and CRSF telemetry: the GPS sensors appear in EdgeTX after Discover new sensors. Recording — the SD Logs special function: the radio writes a CSV with radio and telemetry values to the `LOGS` folder on the SD card at a set interval (at least 50 MB of free space needed). The last row with coordinates is the last known point.
- **Coordinates in the OSD and DVR recording in the goggles.** Latitude and longitude on screen (`osd_gps_lat_pos`, `osd_gps_lon_pos` in Betaflight) end up in the goggles' recording; the last frame gives the point, heading and altitude.
- **A GCS recording a tlog** for ArduPilot and PX4: the last position stays in the ground station's log even if the aircraft has lost power.
- **A buzzer on a switch** (BEEPER mode) and **a motor beacon over DShot**: `beacon RX_LOST` and `beacon RX_SET` — both off by default; the beacon works only with the DShot protocol and stopped motors, and `RX_LOST` in 4.5 — only if the craft was armed after power-up, in 2025.12 — if the flight controller does not see USB (in detail — the `bf-led-buzzer` module).
- **A standalone buzzer with its own battery** — the only thing that works when the battery has been thrown off.

**The first minute after a crash.**
1. Disarm. The pilot stays in place and says aloud the direction and a landmark where they last saw the aircraft; the observer points with their hand. Nobody runs.
2. Do not switch off the radio while there is telemetry: write down the coordinates and voltage, turn on BEEPER. If the link is already gone, the buzzer and the `RX_LOST` beacon work by themselves. If the link is there but there is no BEEPER switch, switching off the radio triggers them.
3. Stop the DVR recording and do not overwrite it; look at the last seconds: coordinates in the OSD, heading, altitude, what was under the aircraft.
4. The lead records the time of the crash and the remaining battery from the OSD — the time budget is counted from that.

**Where to get the last point (in decreasing order of accuracy).** Telemetry coordinates on the radio or in the CSV log → coordinates in the OSD on the last DVR frames → the last position in the ground station's tlog → without GPS: the direction of the last frame, the heading and the flight time from a known point. A correction for momentum: an aircraft that lost power at a height h at a speed v travels beyond the last point by about v × √(2h/g). At 20 m/s and 30 m that is about 50 m forward along the heading.

**Search pattern.**
1. Walk to the last point using a phone's navigator, start recording your own track — it will show what has already been covered.
2. Stop, 10–15 seconds of silence: listen for the buzzer. Repeat every 20–30 m.
3. First — a strip from the last point forward along the flight heading (the momentum correction), then an expanding spiral or parallel tracks. The spacing between passes — no more than the distance from which the aircraft is actually visible in this grass or audible: usually 5–10 m in tall grass, 20–30 m on a mown field.
4. Look not only down: tree crowns, wires, roofs. A second aircraft with a camera helps to inspect crowns and roofs — under the same flying rules.
5. The place where it is found — a point in the navigator and a photo before the aircraft is touched: this is material for the debrief.

**Time budget versus the battery.** The buzzer, beacon, GPS and video transmitter are powered by the flight battery and drain it. Estimate: t ≈ remaining capacity, Ah × voltage / consumption, W. Example: 6S 1300 mAh, 30 % remaining (0.39 Ah at ~22 V ≈ 8.6 Wh). With a digital video module (about 10 W) — less than an hour; only the flight controller, receiver, GPS and buzzer (about 3 W) — about three hours. This is an upper estimate: a deep discharge below 3.0 V per cell (the minimum per the Gens Ace instructions) damages a LiPo, and after the aircraft is found such a battery goes into quarantine and is checked against the criteria of the “Maintenance” module. Hence the order: the first 30–40 minutes — searching by sound and coordinates; if it is not found — the lead decides: continue in daylight with the remaining people, or come back in the morning without counting on the buzzer. Darkness, a thunderstorm and team fatigue are reasons to stop.

{{diagram:crash-search-flow|The search starts in the first minute on site: the last point from the most accurate source plus the momentum correction, then the search pattern and the lead's decision after 30–40 minutes, before the battery dies.}}

**Safety when recovering the aircraft.**
- **Approach.** The aircraft may be armed, and the motors may start. Approach from outside the prop plane (never level with the props), disconnect the battery first, and only then touch the props and frame.
- **Battery after an impact.** Treat it as damaged: not in a pocket and not inside the car, but in a fireproof bag; observe it outdoors for at least 15 minutes; a swollen, hot battery or one with a torn wrap — do not charge it (the “Power” module, disposal).
- **A tree.** Do not climb without a safety line and do not shake the trunk while standing under the aircraft. A pole, a rope with a weight, an arborist. An aircraft on wires or near a power line is not recovered at all: call the grid operator.
- **Water.** Do not wade into unfamiliar water, a current, or onto ice; one person always stays on the shore. An aircraft from the water is not powered on: disconnect the battery, and the battery goes into quarantine as damaged.
- **A roof and someone else's property.** Only with the owner's permission; do not go onto a roof without a railing and a safety line — the aircraft is cheaper.
- **Not found.** A logbook entry: coordinates, time, what is on board (battery, data storage); if the aircraft is registered and has Remote ID — act according to your country's rules.

### Case
The working channel E5 (5885 MHz) turned out to be occupied by a crashed aircraft that kept transmitting until the end of the session. Solution: F1 (5740 MHz) was chosen as the nearest free frequency taking into account the two neighbors' channels, the change was made first on two transmitters and a few drones as a test, then on all of them. The main lesson: a table of the occupied frequencies at the site must exist before an incident.

### Standard radio exchange protocol (a team of 2–4 people)
| Event | Phrase | Reply |
|---|---|---|
| Ready to arm | “Aircraft 1, arm?” | “Clear to arm” / “Stop, <reason>” |
| Takeoff | “Taking off” | “I see it” (observer) |
| Mode change | “Loiter” / “Auto” | “Copy” |
| Problem | “Attention, <what>” | “Land” / “Continue” (lead) |
| Low battery | “Battery 3.5” | “Return” |
| Loss of video/link | “No video” / “Failsafe” | “Everyone watch, don't move” |
| Landing | “Landing” | “Clear” (landing area free) |
| Disarm | “Disarmed” | “Copy, next” |
Short, always the same, no jargon; a beginner learns the phrases before the first trip to the field.

### Briefing and debriefing (10 minutes each)
Briefing: the goal of the sortie, roles, the site and zones, frequencies, weather, emergency actions, who makes the “stop” call. Debriefing: what worked, what didn't, incidents and “near misses” (the main source of improvements), changes to the protocol/checklist, tasks for the next trip. It is written in the site logbook, not kept in someone's head.

### Site checklist (one page)
Access and parking; takeoff point (level, no grass in the props); flight zone per the rules (the “Regulations” module); obstacles (power lines, towers, trees) with their heights; people/animals/roads; wind (anemometer or winds-aloft forecast), precipitation, temperature (LiPo < 10 °C — warm it up); communication (phone, radios); first aid kit, fire extinguisher/sand, water; the participants' frequency table; a “where it falls on DROP” diagram for each point of the route.

### Worked example: a sortie to test RTH
Briefing: the goal — test RTH on a 7" at 100 m from home; pilot — A, observer — B, technician/GCS — C; a site with a prohibited direction toward a road; wind 4 m/s from the west — RTH into the wind, the aircraft will return more slowly (battery margin); frequencies: R1 analog, ELRS 2.4 250 Hz. Execution: arming by the phrases, hover at 1 m → climb to 30 m → fly out 100 m downwind → “RTH” by switch → the observer tracks it by eye → return → hover above home → manual landing. Debriefing: RTH climbed to 60 m as configured, returned in 25 s, manual landing; near miss — the observer was distracted by their phone for 5 s → into the protocol: phones on “do not disturb” for everyone except the technician.

{{diagram:sortie-flow|A sortie as a process: plan, briefing, site checklist, flight with assigned roles, debriefing and a logbook entry.}}

### Place in the system

- **Receives:** the zones and flight category (`f-regulations`); the wind and temperature calculation (`ops-weather`); a tested failsafe (`bf-failsafe`); the VTX channels and power (`link-vtx`).
- **Provides:** logbook entries — flight time, battery voltage before and after, remarks — to maintenance (`ops-maintenance`); the saved log and near misses — to analysis (`diag-troubleshooting`, `ops-case-studies`).
- **If you get it wrong here:** two ELRS radios with the same binding phrase or a video channel without a frequency table → interference for a neighbor, loss of video or link in the air (`link-elrs`, `link-vtx`). Coordinates are not recorded, the beacon and buzzer are not configured → a crashed aircraft is searched for for hours while the flight battery goes into deep discharge (`bf-led-buzzer`, `ops-maintenance`).

## practice
### Step 1. Site map
A diagram: the takeoff/landing point, the flight zone, prohibited directions (people, a road, wires), the team's position, the landing approach. The neighbors' frequencies in a table.

### Step 2. A one-page protocol
Print out: roles, standard phrases, pre-flight and post-flight checklists, actions in an incident, phone numbers.

### Step 3. A run-through
One sortie strictly by the protocol, with a timer and the logbook. Afterwards — what was inconvenient, fix it in the protocol.

### Step 4. Incident analysis
Take a real or a training incident (loss of link, a crash), analyze it from the log: the cause, what worked, what didn't, what change to the protocol.

### Search readiness check (before the first sortie)
1. On the bench, props removed: the BEEPER switch — the buzzer is audible; switch off the radio — the buzzer (and the motor beacon, if `beacon RX_LOST` is enabled) triggers by itself; in 4.5 — only if the craft was armed before that, in 2025.12 — if the FC is not connected to USB. Write down from what distance it can be heard at the site.
2. Turn on SD Logs on the radio, do a short flight, open the CSV from the `LOGS` folder: are there GPS columns, and does the last row match the landing spot according to your phone? A discrepancy of more than 10–15 m — sort it out before long-range flights.
3. Check that the goggles' DVR records and the OSD coordinates are readable in the recording.
4. A training search: one participant hides the aircraft with a connected battery in grass 100–150 m away, the second searches using the last row of the log and by sound. Write down the search time and what got in the way. A solo variant: after the flight from item 2, leave the aircraft with a connected battery where it landed, 100–150 m from the start, go back to the takeoff point, enter the coordinates from the last row of the CSV into your phone's navigator and walk only by them, with track recording on. The result is checked with numbers: the point the navigator led you to is no farther than 10–15 m from the aircraft (the same tolerance as in item 2), the buzzer becomes audible from roughly the distance written down in item 1; write down both distances and the time from the start until your hand touches the aircraft. In addition — the momentum correction for a point you don't have: an aircraft lost power at a height of 40 m at a speed of 15 m/s — search v × √(2h/g) ≈ 43 m forward along the heading from the last point (for the 20 m/s and 30 m from the theory — about 50 m).

### Worked example: a one-page protocol
- **Site:** takeoff point — level dirt ground, no grass in the props; flight zone — a 120° sector to the north, up to 150 m; prohibited direction — the road to the east; a power line 300 m to the west, 25 m high.
- **Frequencies:** a participants' table — pilot, video channel, RC link frequency. Anyone arriving later adds themselves before their first power-up.
- **Roles:** pilot (only the aircraft and the radio), observer (eyes on the aircraft and the sky, reports people and birds by voice), technician or GCS (logbook, batteries, telemetry).
- **Standard phrases:** “Arming” → “Clear” from the observer; “Taking off”; “Landing”; “Stop” — any participant, after which the aircraft lands or hovers immediately.
- **Sortie log:** arm and disarm time, battery number, voltage before and after, remarks. An example row: `14:05–14:12, battery #3, 25.1 → 22.3 V, RTH tested, vibration normal`.

### What to write down after the run-through
How many minutes went into preparation and into the sortie itself; which checklist item was inconvenient or skipped; what the observer said and whether it was heard. The protocol is corrected right away, while it is fresh, and the next version gets a date.

### Incident analysis format
What happened (in time order, from the log) → the immediate cause → why it became possible (several “whys” down to the process, not to a person) → what worked (failsafe, the “Stop” command) → what didn't → one specific change to the protocol or settings and who is responsible for it. Without looking for someone to blame: the goal is that it doesn't happen again.

Self-check: the lab is done when the site map has all the elements of step 1 (takeoff and landing point, flight zone, prohibited directions, the team's position, the landing approach) with distances and obstacle heights, plus a frequency table; the roles and phrases are written down and run through on a real sortie, which left a logbook row in the format of the example (arm and disarm time, battery number, voltage before and after, remarks), the preparation and sortie time in minutes and at least one correction to the protocol with a new date; the search readiness check produced numbers — the distance from which the buzzer can be heard, and a discrepancy between the last row of the radio's log and the landing spot of no more than 10–15 m; and one incident (real or training) is analyzed in the format above: the chain of “whys” is taken down to the process, not to a person, and ends with one specific change to the protocol or settings.

## diagnostics
- **Symptom:** video interference in the middle of a sortie
  - Possible cause: a neighbor powered up on an adjacent frequency.
  - What to do: a frequency table, separation, landing and changing the channel if needed.
- **Symptom:** two radios interfere with each other
  - Possible cause: the same binding phrase or an overloaded band.
  - What to do: unique phrases, lower the power when close, separate the flights in time.
- **Symptom:** a crashed aircraft is not found
  - Possible cause: no last coordinates, the buzzer is not configured.
  - What to do: BEEPER on a switch, `beacon RX_LOST`, SD Logs recording on the radio and DVR in the goggles, a GCS recording a tlog; search from the last point forward along the heading, using the pattern from the section “Searching for a crashed aircraft”.
- **Symptom:** the pilot got distracted by telemetry and lost sight of the aircraft
  - Possible cause: no division of roles.
  - What to do: the observer and the technician are separate people.

## references
- Safety — ArduPilot Copter | https://ardupilot.org/copter/docs/safety-multicopter.html | primary | A
- INAV Safety | https://github.com/iNavFlight/inav/blob/master/docs/Safety.md | primary | A
- Betaflight Arming Sequence & Safety | https://www.betaflight.com/docs/wiki/guides/current/Arming-Sequence-And-Safety | primary | A
- EdgeTX User Manual — Special Functions, SD Logs (accessed 2026-11-17) | https://manual.edgetx.org/bw-radios/model-select/special-functions | primary | A
- EdgeTX User Manual — Storage, LOGS folder (accessed 2026-11-17) | https://manual.edgetx.org/color-radios/radio-settings/storage | primary | A
- Team Associated — LiPo Safety Instructions and Warnings (observing a battery after damage; accessed 2026-11-17) | https://img2.associatedelectrics.com/pdf/cars_and_trucks/shared/LiPo-Safety-Instructions-and-Warnings.pdf | primary | B
- Gens Ace — LiPo safety manual (minimum 3.0 V per cell; accessed 2026-11-17) | https://www.freeflysystems.com/wp-content/uploads/2021/11/Gensace_safety_manual.pdf | primary | B

## checklist
- There is a site map with zones and a frequency table
- Roles are named, the pilot in flight is only a pilot
- The one-page protocol is printed
- A run-through by the protocol is done, the logbook is filled in
- An incident analysis was done and led to a change in the protocol
- The buzzer, telemetry recording on the radio and DVR were checked before the sortie; a training search was done
