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
source_hash: 21b5a09015db
---

## summary
Most crashes happen not because of the firmware but because of organization: nobody checked the neighbors' frequencies, nobody agreed on who watches the aircraft, there was no plan for link loss. This module is about operations as a discipline: sortie planning, team roles, frequencies and communication, pre-flight and post-flight protocol, actions during an incident and searching for a crashed aircraft. It's based on the practice of several pilots working at the same site.

## theory
### Sortie planning
Before you head out, you know: the site and zones (the rules module), the weather (wind at altitude, precipitation, temperature — cold cuts LiPo capacity), the goal of the sortie and success criteria, who takes part and in which roles, which frequencies the neighbors occupy.

### Roles
Even with two people it's worth naming the roles explicitly:

- **Pilot** — flies, and does nothing else.
- **Observer (spotter)** — watches the aircraft with their own eyes and the surroundings: people, birds, other aircraft; talks to the pilot without distracting them.
- **Technician / GCS** — telemetry, parameters, logs, battery swaps, timer.
- **Lead** — decides “go / no-go”, keeps the log.

One person can combine roles, but a pilot in flight is only a pilot.

### Frequencies and communication
- **Video**: a table of occupied channels at the site; spacing from neighbors (rule of thumb ≥ ~37 MHz for analog); channel changes follow the algorithm from the VTX module, on one aircraft first.
- **RC**: the binding phrase is unique; packet rate fits the task; with several ELRS radios — different phrases, otherwise the hopping patterns will coincide.
- **Voice**: short standard phrases: “arm”, “takeoff”, “link”, “low battery”, “landing”, “emergency”. The pilot confirms with one word.

### Protocols
**Pre-flight** (from the safety module, extended): frequencies coordinated, roles named, battery voltage recorded, failsafe tested on this aircraft, timer started on arming.

**Post-flight**: disarm, battery unplugged, motor temperature, inspection of props and frame, log entry (time, battery before/after, remarks), log file saved if it was a test sortie.

### Incidents
- **Link loss**: the pilot calls it out, everyone watches the aircraft, nobody runs. The aircraft does what failsafe is configured to do — that's exactly why failsafe is tested in advance.
- **Crash**: location from the last telemetry/video, the buzzer (BEEPER), GPS coordinates from the GCS log. Approaching a crashed aircraft — the battery may be damaged: don't touch it if hot/puffed, don't charge it.
- **Injury**: first aid, emergency services, then everything else.
- **Debrief**: what happened, from the log, without looking for someone to blame; the conclusion goes into the logbook and the checklist.

### Case
The working channel E5 (5885 MHz) turned out to be occupied by a crashed aircraft that kept transmitting until the end of the shift. Solution: F1 (5740 MHz) was chosen as the nearest free frequency, taking into account the channels of two neighbors; the switch was made first on two transmitters and a few drones as a test, then on all of them. The main lesson: the site's table of occupied frequencies must exist before the incident.

### Standard radio communication protocol (team of 2–4 people)
| Event | Phrase | Response |
|---|---|---|
| Ready to arm | “Aircraft 1, arm?” | “Clear to arm” / “Stop, <reason>” |
| Takeoff | “Taking off” | “Visual” (observer) |
| Mode change | “Loiter” / “Auto” | “Copy” |
| Problem | “Attention, <what>” | “Land” / “Continue” (lead) |
| Low battery | “Battery 3.5” | “Return” |
| Video/link loss | “No video” / “Failsafe” | “Everyone watch, don't move” |
| Landing | “Landing” | “Clear” (site is clear) |
| Disarm | “Disarmed” | “Copy, next” |
Short, always the same, no jargon; a newcomer learns the phrases before the first field trip.

### Briefing and debriefing (10 minutes each)
Briefing: goal of the sortie, roles, site and zones, frequencies, weather, emergency actions, who makes the “stop” call. Debriefing: what worked, what didn't, incidents and “almost-incidents” (near misses — the main source of improvements), changes to the protocol/checklist, tasks for the next field trip. It gets written into the site log, not kept in someone's head.

### Site checklist (one page)
Access and parking; takeoff point (level, no grass in the props); flight zone per the rules (module “Rules”); obstacles (power lines, towers, trees) with heights; people/animals/roads; wind (anemometer or forecast by altitude), precipitation, temperature (LiPo < 10 °C — warm it up); communication (phone, radios); first aid kit, extinguisher/sand, water; table of participants' frequencies; a “where it falls on DROP” diagram for every point of the route.

### Worked example: an RTH test sortie
Briefing: goal — test RTH on a 7" at 100 m from home; pilot — A, observer — B, technician/GCS — C; a site with a no-fly direction toward the road; wind 4 m/s from the west — RTH is into the wind, the aircraft will return slower (battery margin); frequencies: R1 analog, ELRS 2.4 250 Hz. Execution: arm by the phrases, hover at 1 m → climb to 30 m → fly out 100 m downwind → “RTH” on the switch → the observer tracks it visually → return → hover over home → manual landing. Debriefing: RTH climbed to 60 m as configured, returned in 25 s, landed manually; near miss — the observer got distracted by their phone for 5 s → into the protocol: phones on “do not disturb” for everyone except the technician.

{{diagram:sortie-flow|A sortie as a process: plan, briefing, site checklist, flight with assigned roles, debriefing and a log entry.}}

## practice
### Step 1. Site map
A diagram: takeoff/landing point, flight zone, no-fly directions (people, road, wires), team position, landing approach. Neighbors' frequencies in a table.

### Step 2. A one-page protocol
Print it: roles, standard phrases, pre-flight and post-flight checklists, incident actions, phone numbers.

### Step 3. A run-through
One sortie strictly by the protocol, with a timer and the log. Afterwards — what was awkward, fix it in the protocol.

### Step 4. Incident analysis
Take a real or a training incident (link loss, crash) and analyze it from the log: cause, what worked, what didn't, what change goes into the protocol.

### Worked example: a one-page protocol
- **Site:** takeoff point — a level dirt road, no grass in the props; flight zone — a 120° sector to the north, up to 150 m; no-fly direction — the road to the east; power line 300 m to the west, 25 m high.
- **Frequencies:** participants table — pilot, video channel, RC link frequency. Whoever arrives later adds themselves before their first power-up.
- **Roles:** pilot (only the aircraft and the radio), observer (eyes on the aircraft and the sky, calls out people and birds by voice), technician or GCS (log, batteries, telemetry).
- **Standard phrases:** “Arming” → “Clear” from the observer; “Takeoff”; “Landing”; “Stop” — any participant, after which the aircraft lands or hovers immediately.
- **Sortie log:** arm and disarm time, battery number, voltage before and after, remarks. Example line: `14:05–14:12, battery #3, 25.1 → 22.3 V, RTH tested, vibration OK`.

### What to record after the run-through
How many minutes went into preparation and into the sortie itself; which checklist item was awkward or skipped; what the observer said and whether it was heard. The protocol is corrected right away, while it's fresh, and the next version gets a date.

### Incident analysis format
What happened (in time order, from the log) → immediate cause → why it became possible (several “whys” down to the process, not to the person) → what worked (failsafe, the “Stop” command) → what didn't work → one concrete change to the protocol or settings and who is responsible for it. No looking for someone to blame: the goal is that it doesn't happen again.

The lab counts as done when you have a site map with zones, obstacles and a frequency table, the roles and phrases are written down and run through on a real sortie with a log, and one incident (real or training) is analyzed using the format above with a concrete change to the protocol.

## diagnostics
- **Symptom:** video interference in the middle of a sortie
  - Possible cause: a neighbor powered up on an adjacent frequency.
  - What to do: frequency table, spacing, land and change the channel if needed.
- **Symptom:** two radios interfere with each other
  - Possible cause: the same binding phrase or an overloaded band.
  - What to do: unique phrases, lower the power when close together, separate them in time.
- **Symptom:** a crashed aircraft can't be found
  - Possible cause: no last coordinates, buzzer not configured.
  - What to do: BEEPER on a switch, GCS recording a tlog, the last point from the video.
- **Symptom:** the pilot got distracted by telemetry and lost sight of the aircraft
  - Possible cause: no division of roles.
  - What to do: the observer and the technician are separate people.

## references
- Safety — ArduPilot Copter | https://ardupilot.org/copter/docs/safety-multicopter.html | primary | A
- INAV Safety | https://github.com/iNavFlight/inav/blob/master/docs/Safety.md | primary | A
- Betaflight Arming Sequence & Safety | https://www.betaflight.com/docs/wiki/guides/current/Arming-Sequence-And-Safety | primary | A

## checklist
- A site map with zones and a frequency table exists
- Roles are named, the pilot in flight is only the pilot
- The one-page protocol is printed
- A run-through by the protocol is done, the log is filled in
- An incident analysis was carried out and produced a change to the protocol
