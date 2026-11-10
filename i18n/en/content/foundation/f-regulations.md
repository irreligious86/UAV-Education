---
id: f-regulations
title: "Rules, Zones and Operator Responsibility"
level: L1
readingTime: 20 min
firmware: any firmware
status: published
added: 2026-11-08
tags:
  - rules
  - safety
  - responsibility
related:
  - f-safety
  - ops-field
next:
  - tools-overview
source: content/foundation/f-regulations.md
source_hash: 88b3f9de7c73
---

## summary
A UAV engineer is responsible not only for making the aircraft fly, but also for where and how it flies. Rules differ from country to country and change every year, so this module doesn't retell them. Instead it teaches you to find the current ones, understand the common logic (risk categories, zones, altitudes, registration, insurance) and keep operator documentation. This is not legal advice: the source of truth is your country's regulator.

## theory
### The common logic of regulation
Most countries build their rules around **risk**: aircraft mass, proximity to people and infrastructure, altitude, visibility. Typical elements:

- **Registration** of the operator and/or the aircraft above a certain mass.
- **Operation categories**: from “open” (small aircraft, in visual line of sight, away from people) to “specific” and “certified” (authorizations, risk assessment).
- **Altitude limit** above ground (often around 120 m / 400 ft in the open category).
- **Zones**: airports, cities, infrastructure sites, borders, military sites — prohibited or requiring authorization.
- **Visual line of sight** (VLOS) as the baseline requirement; flights beyond it (BVLOS) need separate authorizations.
- **Night flights, flights over people** — separate conditions.
- **Liability insurance** — mandatory or strongly recommended.

### What this means for an engineer
- Test flights are flights too: same rules.
- Autonomous missions and BVLOS are almost always a separate category. Plan them legally or in a simulator.
- RC and video frequencies are regulated separately: VTX power and bands, and the allowed ELRS/900 MHz channels, depend on the country.
- Responsibility lies with the operator and the owner. The flight log is your protection in case of an incident.

### Operator documentation
The minimum professionals keep:

- **Operator log**: date, location, aircraft, duration, purpose, incidents.
- **Aircraft log**: configurations, repairs, replacements, motor/battery hours.
- **Build sheet** (from the “Foundation” capstone): mass, power system, frequencies.
- **Site risk assessment**: people, obstacles, zones, weather, failure plan.

### How two “reference” systems work (so you understand your own)
- **EASA (EU)**: three categories — **Open** (up to 25 kg, VLOS, ≤ 120 m, subcategories A1/A2/A3 by proximity to people and aircraft class C0–C4 (classes C5/C6 are for the STS standard scenarios in the Specific category); operator registration from 250 g or if there is a camera; online exam A1/A3, an additional one for A2), **Specific** (SORA risk assessment, authorization from the national authority or STS standard scenarios; this is where BVLOS, heavy aircraft and flights over people end up), **Certified** (like manned aviation). Homebuilt aircraft are Open only in A1 (< 250 g) or A3 (away from people), otherwise Specific.
- **FAA (USA)**: **Part 107** for commercial flying (exam, certificate, ≤ 400 ft, VLOS, Remote ID), **Recreational** (TRUST test, registration from 250 g, 400 ft, Remote ID), authorization for flights in controlled airspace via LAANC; BVLOS — waiver.
What both have in common: registration and identification (Remote ID / C class), risk-based category, altitude ~120 m/400 ft, VLOS, zones, operator responsibility. Check your own country against the same structure: “which category, what registration threshold, what altitude, what identification, what about BVLOS”.

### Radio frequencies: what is usually restricted
The ISM bands (2.4 GHz, 5.8 GHz, 868/915 MHz) are open for license-free use with a power limit (in the EU 2.4 GHz — 100 mW EIRP, 5.8 GHz video — 25 mW EIRP under the general rules; 868 MHz — 25 mW with a duty cycle limit; in the USA it's different, 900 MHz is wider) — a 1 W VTX or ELRS is formally outside the general rules in most countries and requires an amateur radio license or a separate authorization. The course modules on link budget compute the physics; whether the power is legal is a separate question you settle before the flight.

### Worked example: test flights of a homebuilt 7"
A 1.4 kg aircraft, homebuilt (no C class), with a camera. EU: Open A3 — ≥ 150 m from residential/industrial/recreational areas, away from people, ≤ 120 m, operator registration, A1/A3 exam, insurance as your country requires; any BVLOS test or autonomous mission test beyond VLOS is Specific. USA: recreational (TRUST, registration, Remote ID module) or Part 107, 400 ft, LAANC if needed. The takeaway for your engineering folder: site, category, documents, what is not allowed — written down before the first flight; autonomous tests go to SITL and a tethered test stand until you have an authorization.

{{diagram:airspace-check|Pre-flight check logic: zone status on the official map, category rules and allowed radio frequencies (specific values follow your country's legislation).}}

## practice
### Step 1. Find your country's rules
1. Your country's civil aviation regulator — the official website, the section on drones.
2. Write down with links: registration (from what mass), categories, altitude, zones, VLOS/BVLOS, insurance.
3. Separately — the radio frequency rules (VTX power, bands).
4. The date you checked goes in the note: check again in a year.

### Step 2. Zone map around your site
Find the official zone map (many regulators have a service or an app). Mark the nearest airports and restricted zones, figure out where you can fly without an authorization.

### Step 3. Start the logs
Two files in your drone repository: `operator-log.md` and `<drone>/log.md`. The first entry is today.

### Step 4. Site risk assessment
A one-page checklist: people and animals, obstacles and wires, zone and altitude, weather (wind, precipitation, battery temperature), plan for link loss (where it falls on DROP, where it flies on RTH), emergency services contact.

### Rules summary template
| Item | What the rule says | Link (document, clause) | Date checked |
|---|---|---|---|
| Registration | from what mass, how and where | … | … |
| Category and subcategory | for your aircraft and task | … | … |
| Altitude | maximum above ground | … | … |
| Zones | where it's prohibited or needs authorization | … | … |
| Visibility | VLOS, whether an observer is needed | … | … |
| Insurance, certificate | whether required | … | … |
| Radio | VTX and RC power and bands | … | … |
| Remote ID | whether required and in what form | … | … |

The summary links to the regulator's official documents, not to retellings in chats: rules change, and retellings lag behind.

### What to record
- **Operator log,** first entry: `2026-11-09 — rules checked (links in regs.md), site “field by the river”: outside zones, nearest airport 18 km, altitude up to 120 m`. The specific numbers follow your country's rules and map.
- **Drone log:** every flight — date, site, duration, battery, remarks.
- **Site risk assessment** — one sheet tied to a specific location. New site — new sheet.

The lab counts as done when your country's current rules are summarized using the template with links to official sources and the date checked, the zones around your site are checked on the official map, and the operator log and drone log are started with their first entries.

## diagnostics
- **Symptom:** unclear whether registration is required
  - Possible cause: the threshold mass differs between countries and changes.
  - What to do: look only at the official source, write down the date checked.
- **Symptom:** the site “seems clear”, but there's an airport nearby
  - Possible cause: airport zones often extend for kilometers.
  - What to do: the official zone map; when in doubt, don't fly.
- **Symptom:** incident involving third parties
  - Possible cause: anything.
  - What to do: help the injured, document everything, notify as your country's rules require, log it.

## references
- ICAO — Unmanned Aircraft Systems (UAS) | https://www.icao.int/UA | primary | A
- EASA — Civil drones (example of a rule structure: open/specific/certified categories) | https://www.easa.europa.eu/en/domains/civil-drones | primary | A
- FAA — Unmanned Aircraft Systems (example: Part 107, Recreational Flyers) | https://www.faa.gov/uas | primary | A

## checklist
- Your country's rules found on the official website and summarized with a date
- Zones around the site checked on the official map
- Operator and aircraft logs started
- Site risk assessment written
- I know the frequency and VTX/RC power limits in my country
