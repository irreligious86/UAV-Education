---
id: f-regulations
title: "Regulations, Zones and Operator Responsibility"
level: L1
readingTime: 20 min
firmware: any firmware
status: published
added: 2026-11-08
tags:
  - regulations
  - safety
  - responsibility
related:
  - f-safety
  - ops-field
next:
  - tools-overview
source: content/foundation/f-regulations.md
source_hash: 1845c830098d
---

## summary
A UAV engineer is responsible not only for making the aircraft fly, but also for where and how it flies. Regulations differ by country and change every year, so this module does not retell them; it teaches you to find the current ones, to understand the common logic (risk categories, zones, altitudes, registration, insurance) and to keep the operator's documentation. This is not legal advice: the source of truth is your country's regulator.

## theory
### The common logic of regulation
Most countries build their rules around **risk**: the aircraft's mass, proximity to people and infrastructure, altitude, visibility. Typical elements:

- **Registration** of the operator and/or the aircraft above a certain mass.
- **Operation categories**: from “open” (small aircraft, within line of sight, away from people) to “specific” and “certified” (authorizations, risk assessment).
- **An altitude limit** above the ground (often around 120 m / 400 feet in the open category).
- **Zones**: aerodromes, cities, infrastructure sites, borders, military sites — prohibited or permitted.
- **Visual line of sight** (VLOS) as the basic requirement; flights beyond it (BVLOS) — separate authorizations.
- **Night flights, flights over people** — separate conditions.
- **Liability insurance** — mandatory or strongly recommended.

### What this means for an engineer
- Test flights are flights too: the same rules apply.
- Autonomous missions and BVLOS are almost always a separate category. Plan them legally or in a simulator.
- RC and video frequencies are regulated separately: VTX power and bands, the permitted ELRS/900 MHz channels depend on the country.
- Responsibility lies with the operator and the owner. The flight log is your protection in an incident.

### Operator documentation
The minimum that professionals keep:

- **Operator log**: date, location, aircraft, duration, purpose, incidents.
- **Aircraft log**: configurations, repairs, replacements, motor/battery hours.
- **Build spec sheet** (from the “Foundation” capstone): mass, powertrain, frequencies.
- **Site risk assessment**: people, obstacles, zones, weather, a plan for failure.

### How two “reference” systems work (so you understand your own)
- **EASA (EU)**: three categories — **Open** (up to 25 kg, VLOS, ≤ 120 m, subcategories A1/A2/A3 by proximity to people and by aircraft class C0–C4 (classes C5/C6 are for the STS standard scenarios in the Specific category); operator registration from 250 g or with a camera; an online A1/A3 exam, an additional one for A2), **Specific** (SORA risk assessment, an authorization from the national authority or the STS standard scenarios; this is where BVLOS, heavy aircraft and flights over assemblies of people fall — Open prohibits them, Regulation (EU) 2019/947, Art. 4), **Certified** (like crewed aviation). Home-built aircraft — Open only in A1 (< 250 g) or A3 (away from people), otherwise Specific.
- **FAA (USA)**: **Part 107** — for any flights not for recreation: commercial, government, volunteer (an exam, a Remote Pilot certificate, ≤ 400 feet, VLOS, registration of every aircraft regardless of mass, Remote ID); **Recreational** — an exception for flights purely for fun (the TRUST test, the rules of an FAA-recognized community-based organization (CBO), registration from 250 g, 400 feet in class G, Remote ID for registered aircraft); authorizations for flights in controlled airspace via LAANC or DroneZone; BVLOS — a waiver. Updates as of November 2026 — in the subsection below.
What both have in common: registration and identification (Remote ID / class C), a risk-based category, an altitude of ~120 m/400 feet, VLOS, zones, operator responsibility. Check your own country against the same structure: “what category, what registration threshold, what altitude, what identification, what about BVLOS”.

### What changed by November 2026: USA, United Kingdom, EU
Checked against the regulators' pages on 2026-11-17. Rules change: before flying, open the official page from the table at the end of this subsection, not this text. This is an overview for an engineer, not legal advice.

**USA (FAA).**
- **Under 250 g and only for recreation — no registration.** Under 14 CFR 48.15, registration is not required for an aircraft that flies exclusively under the recreational rules (49 U.S.C. 44809) and weighs no more than 0.55 lb (250 g) at takeoff together with everything attached to it. No registration — no Remote ID requirement either. TRUST, 400 feet and the other rules still apply.
- **TRUST** — a free online test, mandatory for any recreational flight; you must carry proof of completion.
- **Part 107 — everything that isn't recreation.** The FAA's criterion is the purpose of the flight, not payment: according to the FAA Safety Briefing article, free services, volunteering and nonprofit organizations fall under Part 107 (“goodwill and nonprofit operations fall under part 107”). An aircraft for Part 107 is registered regardless of mass, even under 250 g. On the FAA pages we checked there is no separate line about monetized video; by the purpose criterion, filming for channel income is not a flight “purely for fun” — in that case you fly under Part 107, and if in doubt you ask the FAA.
- **FPV in goggles — only with an observer.** For recreation: the aircraft within the visual line of sight of the pilot or of an observer who stands next to the pilot and is in direct communication with them. Part 107: either the pilot or a visual observer must see the aircraft without instruments (§ 107.31, § 107.33). A pilot in goggles does not see the aircraft, so an observer is mandatory.
- **Remote ID is in force:** a registered aircraft broadcasts Remote ID or flies only within a FRIA (details — the `f-remote-id-security` module).
- **Part 108 (routine BVLOS operations) is not yet in force.** The proposed rule (NPRM) was published on 7 August 2025 (90 FR 38212), the comment period closed on 6 October 2025 and was reopened in January 2026 (91 FR 3695). In the regulatory agenda the rule is at the Final Rule stage with a target date of “July 2026”, but as of 2026-11-17 we did not find a published final rule. Until it is published, BVLOS in the US is a waiver under Part 107 (§ 107.31 is on the list of provisions that can be waived). To check: docket FAA-2025-1908.

**United Kingdom (CAA), rules from 1 January 2026.**
| Aircraft | Flyer ID (pilot test) | Operator ID (operator registration) |
|---|---|---|
| under 100 g | not required, test recommended | optional |
| 100–250 g without a camera | required | optional |
| 100–250 g with a camera | required | required |
| from 250 g to 25 kg | required | required |

- **Classes UK0–UK6.** New models placed on the market from 1 January 2026 carry a UK class mark: UK0 (< 250 g) and UK1 (< 900 g) — subcategory A1; UK2 (< 4 kg) — A2 with an A2 CofC, or A3; UK3 and UK4 (< 25 kg) — A3; UK5 and UK6 — only with an Operational Authorisation. European C classes are accepted as the corresponding UK classes until 31 December 2027, after which they become “legacy”.
- **An aircraft without a class mark (legacy, home-built)** flies by mass: < 250 g — A1, < 2 kg — A2 with an A2 CofC (no closer than 50 m to uninvolved people), < 25 kg — A3 (no closer than 50 m to people and 150 m to residential, recreational, commercial and industrial areas). Altitude — up to 120 m.
- **Remote ID:** from 1 January 2026 mandatory for UK1, UK2, UK3, UK5, UK6; from 1 January 2028 — for UK0 from 100 g with a camera, UK4, and home-built and legacy aircraft from 100 g with a camera.
- **FPV:** an observer is mandatory, standing next to the pilot, and one of the two always sees the aircraft. **At night** — a flashing green light. Liability **insurance**: mandatory from 20 kg and for any paid work.
- The CAA does not recognize other countries' registrations and certificates.

**EU (EASA): the transition period has ended.** Since 1 January 2024, an aircraft without a class mark (bought before that date or home-built) can fly in Open only like this: A1 — if the takeoff mass is under 250 g (for a home-built one, also a speed under 19 m/s), A3 — if under 25 kg. The transitional options “up to 500 g in A1” and “up to 2 kg in A2” no longer apply. FPV is allowed when an observer (UA observer) stands next to the pilot and keeps the aircraft in sight at all times; races with spectators already fall into the Specific category.

{{diagram:easa-open-category-tree|A home-built aircraft without a class mark gets into A1 only with a mass < 250 g and a speed < 19 m/s, otherwise into A3 up to 25 kg; BVLOS, flights over assemblies of people and aircraft from 25 kg — Specific.}}

**Where to check.**
| Country | What to look at | Official page |
|---|---|---|
| USA | recreational rules, TRUST, Remote ID | faa.gov/uas/recreational_flyers |
| USA | Part 107, waiver | faa.gov/uas/commercial_operators |
| USA | Part 108 status | regulations.gov, docket FAA-2025-1908 |
| United Kingdom | Drone Code, registration, classes, Remote ID | caa.co.uk/drones |
| EU | Open category, classes, questions and answers | easa.europa.eu → Drones → Open category; then the national authority's website |

### Market and equipment: the FCC Covered List (USA)
This is not an aviation rule but a radio-frequency one, and it affects what can be bought in the US.

- **What happened.** On 22 December 2025 the FCC (Public Notice DA 25-1086) added to the Covered List unmanned aircraft systems and their “critical components” produced outside the US. The definition of components includes flight controllers, ground stations and radios, communication and data transmission systems, navigation, sensors and cameras, batteries with a BMS, and motors. The entry is based on the place of production, without naming companies.
- **What it means.** Equipment on the Covered List cannot receive a new FCC equipment authorization, i.e. a new model with a radio part cannot legally enter the US market. According to the FCC's official fact sheet, the restriction applies to new models: aircraft already bought can be used, and previously authorized models can continue to be sold and imported.
- **The exemptions are temporary.** On 7 January 2026 (DA 26-22), products on the Blue UAS Cleared List and “domestic end products” under the Buy American standard were removed from the list — until 1 January 2027. Until the same date, firmware updates for previously authorized devices are permitted (DA 26-69). On 15 June 2026, toy drones were removed.
- **What is still under discussion.** In July 2026 the FCC put up for comment a ban on further import and sale of part of the already authorized equipment (DA 26-742 — by a list of specific manufacturers, DA 26-758 — “military-grade”: from 55 lb, with a thermal camera or lidar, swarm-capable). These are proposals; by their text they do not affect the use of equipment already bought. Whether they have been adopted — check on the FCC page.
- **The takeaway for an engineer in the US.** Existing equipment remains legal. New models of foreign flight controllers, receivers, video transmitters, motors and batteries may not reach the market, so the build spec sheet records a replacement for each key part, and a stock of consumables is kept. The exemptions expire on 1 January 2027 — check the current Covered List before buying. For other countries this decision changes nothing directly, but it affects the product range and prices.

### Radio frequencies: what is usually restricted
The ISM bands (2.4 GHz, 5.8 GHz, 868/915 MHz) are open for license-exempt use with a power limit (EIRP — equivalent isotropically radiated power: the transmitter power plus the antenna gain in dB, minus cable losses; a 25 mW VTX with a 3 dBi antenna gives about 50 mW EIRP — the calculation in `rf-link-budget`; in the EU 2.4 GHz — 100 mW EIRP, 5.8 GHz video — 25 mW EIRP under the general rules; 868 MHz — 25 mW with a duty-cycle limit; in the US it is different, 900 MHz is wider) — a 1 W VTX or ELRS in most countries is formally outside the general rules and requires an amateur radio license or a separate authorization. The course's link budget modules calculate the physics; whether the power is legal is a separate question, settled before the flight.

### Worked example: test flights of a home-built 7"
An aircraft of 1.4 kg, home-built (no C class), with a camera. EU: Open A3 — ≥ 150 m from residential/industrial/recreational areas, away from people, ≤ 120 m, operator registration, the A1/A3 exam, insurance as the country requires; any BVLOS test/an autonomous mission beyond VLOS — Specific. USA: recreational (TRUST, registration — the aircraft is heavier than 250 g, a Remote ID module, for FPV — an observer next to the pilot) or Part 107, 400 feet, LAANC if needed. United Kingdom: no class mark and heavier than 250 g — A3, Flyer ID and Operator ID, an observer for FPV. The conclusion for the engineering folder: the site, the category, the documents, what is not allowed — written down before the first flight; autonomous tests — SITL and a tethered test stand until there is an authorization.

{{diagram:airspace-check|The logic of the pre-flight check: the zone status on the official map, the category rules and the permitted radio frequencies (the specific values — per your country's legislation).}}

### Place in the system

- **Receives:** the takeoff mass and whether there is a camera — they determine the category and registration (`f-components-choice`); the power and band of RC and video (`rf-link-budget`, `link-vtx`); the type of operation — within line of sight or an autonomous mission (`ap-missions`).
- **Provides:** the permitted zone, altitude and category — to sortie planning and the site risk assessment (`ops-field`); the identification requirement — `f-remote-id-security`; constraints — to the S-xx requirements (`eng-method-101`).
- **If you get it wrong here:** the link budget was calculated for 1 W where the general rules allow 25 mW EIRP → either the flight is outside the rules, or the range is shorter than calculated and the failsafe comes earlier (`rf-link-budget`). A home-built aircraft became heavier than 250 g after modifications → a different subcategory, registration and Remote ID (`f-remote-id-security`).

## practice
### Step 1. Find your country's rules
1. Your country's civil aviation regulator — the official website, the section on drones.
2. Write down, with links: registration (from what mass), categories, altitude, zones, VLOS/BVLOS, insurance.
3. Separately — the radio frequency rules (VTX power, bands).
4. The date of the check — in the note: check again in a year.

### Step 2. A map of the zones around your site
Find the official zone map (many regulators have a service or an app). Mark the nearest aerodromes and restricted zones, determine where you can fly without an authorization.

### Step 3. Start the logs
Two files in your drone repository: `operator-log.md` and `<drone>/log.md`. The first entry — today.

### Step 4. Site risk assessment
A one-page checklist: people and animals, obstacles and wires, zone and altitude, weather (wind, precipitation, battery temperature), the plan on loss of link (where it falls on DROP, where it flies on RTH), emergency services contacts.

### Template for a summary of the rules
| Item | What the rule says | Link (document, clause) | Date checked |
|---|---|---|---|
| Registration | from what mass, how and where | … | … |
| Category and subcategory | for your aircraft and mission | … | … |
| Altitude | maximum above the ground | … | … |
| Zones | where it is prohibited or an authorization is needed | … | … |
| Visibility | VLOS, whether an observer is needed | … | … |
| Insurance, certificate | whether it is needed | … | … |
| Radio | VTX and RC power and bands | … | … |
| Remote ID | whether it is needed and in what form | … | … |

The summary links to the regulator's official documents, not to retellings in chats: rules change, and retellings lag behind.

### What to write down
- **Operator log,** the first entry: `2026-11-09 — rules checked (links in regs.md), site "field by the river": outside zones, nearest aerodrome 18 km, altitude up to 120 m`. The specific numbers — per your country's rules and map.
- **Drone log:** every sortie — date, site, duration, battery, remarks.
- **Site risk assessment** — one sheet tied to a specific place. A new site — a new sheet.

Self-check: the lab is done when all eight rows of the summary template are filled in and each has what the rule says, a link to the regulator's document with the clause (not a retelling in a chat) and the date checked; the zones around your site are checked against the official map, and the result is written down in numbers — the distance to the nearest aerodrome, the permitted altitude, the conclusion “outside zones” or “authorization needed”; the operator log and the drone log are started, the first entry is in the format of the example above (date, what was checked, site, numbers); the site risk assessment sheet answers all six items of step 4, including “where it falls on DROP and where it flies on RTH”.

## diagnostics
- **Symptom:** it is not clear whether registration is needed
  - Possible cause: the threshold mass differs by country and changes.
  - What to do: look only at the official source, write down the date of the check.
- **Symptom:** the aircraft is under 250 g — “so the rules don't apply”
  - Possible cause: the 250 g threshold applies only to some of the requirements, and not in every country.
  - What to do: USA — no registration only for recreational flights, under Part 107 registration regardless of mass; United Kingdom — a Flyer ID already from 100 g; EU — operator registration if there is a camera. Check against the official page.
- **Symptom:** I fly in goggles alone
  - Possible cause: only an observer next to the pilot satisfies the visual line of sight requirement.
  - What to do: an observer for every FPV sortie (USA, United Kingdom, EU); the role is described in the `ops-field` module.
- **Symptom:** the site “seems clear”, but there is an aerodrome nearby
  - Possible cause: aerodrome zones often extend for kilometers.
  - What to do: the official zone map; if in doubt — don't fly.
- **Symptom:** an incident involving third parties
  - Possible cause: any.
  - What to do: help the injured, record what happened, notify according to the country's rules, the log.

## references
- ICAO — Unmanned Aircraft Systems (UAS) | https://www.icao.int/UA | primary | A
- EASA — Civil drones (an example of the rule structure: open/specific/certified categories) | https://www.easa.europa.eu/en/domains/civil-drones | primary | A
- FAA — Unmanned Aircraft Systems (example: Part 107, Recreational Flyers) | https://www.faa.gov/uas | primary | A
- FAA — Recreational Flyers (TRUST, CBO, observer, Remote ID; updated 2026-10-29, accessed 2026-11-17) | https://www.faa.gov/uas/recreational_flyers | primary | A
- eCFR — 14 CFR Part 48, § 48.15 (registration exception: 0.55 lb and 44809 only; accessed 2026-11-17) | https://www.ecfr.gov/current/title-14/chapter-I/subchapter-C/part-48 | primary | A
- 14 CFR Part 107 — § 107.31, § 107.33, § 107.205 (visual line of sight, observer, waiver; accessed 2026-11-17) | https://www.govinfo.gov/content/pkg/CFR-2025-title14-vol2/pdf/CFR-2025-title14-vol2-part107.pdf | primary | A
- FAA Safety Briefing — Flying for Fun; But Are You Sure? (the purpose of the flight, not payment; accessed 2026-11-17) | https://medium.com/faa/flying-for-fun-but-are-you-sure-54710c5448e6 | primary | B
- OIRA Unified Agenda — RIN 2120-AL82, Part 108 BVLOS (stage and dates; accessed 2026-11-17) | https://www.reginfo.gov/public/do/eAgendaViewRule?pubId=202510&RIN=2120-AL82&operation=OPERATION_PRINT_RULE | primary | A
- UK CAA — Registering to fly drones and model aircraft (Flyer ID, Operator ID; accessed 2026-11-17) | https://www.caa.co.uk/drones/open-category/getting-started-with-drones-and-model-aircraft/registering-to-fly-drones-and-model-aircraft/ | primary | A
- UK CAA — Class marks (UK0–UK6, legacy, C classes until 2027-12-31; accessed 2026-11-17) | https://www.caa.co.uk/drones/open-category/getting-started-with-drones-and-model-aircraft/class-marks/ | primary | A
- UK CAA — The Drone Code, March 2026 (subcategories, FPV, night, insurance; accessed 2026-11-17) | https://www.caa.co.uk/media/ejjbzm40/the-drone-code-march-2026.pdf | primary | A
- UK CAA — Remote ID (the 2026 and 2028 dates; accessed 2026-11-17) | https://www.caa.co.uk/drones/drone-regulations/policy-programmes/remote-id-rid/ | primary | A
- EASA — FAQ: Open category (the table from 1 January 2024, FPV and the observer; accessed 2026-11-17) | https://www.easa.europa.eu/en/the-agency/faqs/open-category | primary | A
- FCC — Public Notice DA 25-1086 (UAS and components on the Covered List, 2025-12-22; accessed 2026-11-17) | https://docs.fcc.gov/public/attachments/DA-25-1086A1.txt | primary | A
- FCC — Fact Sheet for the decision of 2025-12-22 (already purchased and previously authorized equipment; accessed 2026-11-17) | https://docs.fcc.gov/public/attachments/DOC-416839A1.txt | primary | A
- FCC — Public Notice DA 26-22 (exemptions until 2027-01-01; accessed 2026-11-17) | https://docs.fcc.gov/public/attachments/DA-26-22A1.pdf | primary | A
- FCC — Public Notice DA 26-69 (firmware updates until 2027-01-01; accessed 2026-11-17) | https://docs.fcc.gov/public/attachments/DA-26-69A1.txt | primary | A
- FCC — Public Notice DA 26-758 (the “military-grade” proposal, history of changes to the list; accessed 2026-11-17) | https://docs.fcc.gov/public/attachments/DA-26-758A1.pdf | primary | A
- FCC — Public Notice DA 26-742 (the proposal based on a list of manufacturers; accessed 2026-11-17) | https://docs.fcc.gov/public/attachments/DA-26-742A1.pdf | primary | A

## checklist
- My country's rules are found on the official website and summarized with a date
- The zones around the site are checked against the official map
- The operator and aircraft logs are started
- The site risk assessment is written
- I know the restrictions on VTX/RC frequencies and power in my country
- I know whether my country requires an observer for FPV and from what mass registration and a test are required
