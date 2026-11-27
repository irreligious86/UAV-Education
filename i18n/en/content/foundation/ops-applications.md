---
id: ops-applications
title: "Application segments: agriculture, inspection, delivery, shows"
level: L2
readingTime: 45 min
firmware: ArduCopter 4.7 (AC_Sprayer, ZigZag; checked against 4.7.3) · Skybrush fork of ArduCopter · any firmware
status: published
added: 2026-11-22
tags:
  - agriculture
  - inspection
  - thermal camera
  - delivery
  - drone shows
  - requirements
related:
  - eng-career
  - f-regulations
  - ops-case-studies
  - payload-gimbal
  - ap-payload
  - per-mapping
next:
  - des-sizing
source: content/foundation/ops-applications.md
source_hash: def640eb401a
---

## summary
A customer does not come for a “drone” but for a job: treat 40 ha, find an overheated contact, carry 2 kg over 8 km, draw a picture of 231 points in the sky. This module goes through six application segments — spraying and spreading, mapping and multispectral, inspection (thermal camera, lidar), delivery, light shows, public safety — the same way: the job → the requirements (payload weight, time, position accuracy, wind, redundancy) → the aircraft class and the stack (firmware, course modules) → where to look in the rules of the EU, the United Kingdom and the USA → typical failures. The main tool is the selection rule: from the mission description to a requirements table and a class. The practice needs no hardware: four missions for which you calculate GSD, the thermal measurement distance, the number of show aircraft and the delivery radius, and choose the class; the answers are unambiguous and given in the reference.

## theory
### How to read a segment: job → requirements → class
The professions and the way into the industry are in `eng-career` (“Niches for an operator”); here — what the aircraft must be able to do. The typical mistake is starting from the aircraft (“I have a 7", what can I do with it?”). The order is the reverse.

**The selection rule (course, 5 steps).**

1. **Describe the job in one sentence with numbers:** what, where, how much, how accurately, over whom. “Spray 40 ha of wheat at a rate of 15 L/ha, with a road nearby” will do; “agricultural survey” will not.
2. **Derive six requirements:** the payload weight m_pl (including consumables: liquid, cargo); the working time t_work from the segment's productivity formula; the position accuracy σ; the design wind at the working height (v(h) = v₁₀·(h/10)^α, `ops-weather`); the consequences of a failure (over people, BVLOS, expensive cargo, takeoff weight > 25 kg); whether hovering over a point is needed.
3. **The class by the layouts from `des-sizing`:** t_work ≤ 40 min → a multirotor (20–40 min). t_work > 40 min and hovering is not needed or is needed for minutes → a VTOL (no runway) or a plane (1–3 h); hovering is the main work → several multirotor flights. Serious consequences of a failure → a hexa or an octo, which survive a motor failure (`el-redundancy`). In terms of energy a wing is also better on short missions without hovering (`des-sizing`); a quad is taken there for the simplicity of launch.
4. **Positioning:** ordinary GNSS gives 2–3 m, RTK — 1–10 cm (Skybrush FAQ). The course rule (estimate): the tolerance σ the job needs is at least three times the navigation error; otherwise — RTK (`nav-rtk`), and for absolute map accuracy — ground control points as well (`per-mapping`).
5. **The regulatory corridor:** takeoff weight up to 25 kg (in the USA — less than 55 pounds), VLOS, not over people, nothing is dropped or sprayed → Open (EU, United Kingdom) or Part 107; commercial VLOS work in the United Kingdom often goes under PDRA01 — that is already a simplified Specific. Any “no” → Specific, a waiver, an exemption or an operator certificate. The specifics are in the rules table below and in `f-regulations`.

{{diagram:apps-selection-tree|The class is chosen by the job, not by the aircraft at hand: the working time and the share of hovering set the type, the consequences of a failure set the number of motors, and a weight > 25 kg and BVLOS take you straight out of the “open” rules.}}

### Summary table of requirements by segment
The ranges are the course's engineering estimate; products are named only as an example of the class (manufacturer specifications as of November 2026), not as a recommendation.

| Segment | Payload | Time / productivity | Position accuracy | Wind | Redundancy | Class and stack | Course modules |
|---|---|---|---|---|---|---|---|
| Spraying | 10–50 kg of liquid | 10–20 min per flight; ha/h = B·v·0.36 | RTK; track error ≤ 10 % of the swath (estimate) | T50: up to 6 m/s; drift — per the product label | MTOW > 25 kg → hexa/octo | heavy multirotor; `AC_Sprayer`, ZigZag | `ap-heavy`, `ap-payload`, `nav-rtk`, `nav-terrain` |
| Spreading | T50: 50 kg, 75 L hopper, MTOW 103 kg | as for spraying, the weight drops in jerks | RTK | as above | as above | a spreader on a servo output | `ap-heavy`, `ap-outputs` |
| Mapping, multispectral | camera 0.2–1 kg (Mavic 3M — MTOW 1050 g) | ha/h = line spacing · v · 0.36 | RTK for georeferencing, GCPs for absolute accuracy | Mavic 3M: 12 m/s (takeoff, landing) | usually not needed | a quad up to 40 min, a VTOL/plane beyond | `per-mapping`, `ap-payload`, `ap-quadplane` |
| Thermal camera | 0.3–1 kg (Matrice 4T — 1219 g, MTOW 1420 g) | hovering at the object; distance by the 3 × 3 px rule | GNSS degrades near structures | M4T: 12 m/s (takeoff, landing) | over people and near power lines — yes | a quad with a gimbal | `payload-gimbal`, `per-depth-avoid`, `nav-resilience` |
| Lidar | about 1 kg | ρ = PRR/(v·W) | RTK FIX for the datasheet accuracy | as for the carrier | expensive cargo → hexa/octo | medium multirotor | `nav-rtk`, `ap-heavy` |
| Delivery | 1–3 kg (estimate) | radius from the flight time with a reserve | landing or drop at the point (`per-landing`) | along the route | BVLOS over people → high | a multirotor with a winch or a VTOL | `ap-payload`, `ap-quadplane`, `ap-safety-fs`, `el-redundancy` |
| Light show | a light quad with an RGBW light | 10–20 min (estimate) | RTK 1–10 cm | stronger at 120 m than near the ground | geofence and failsafe on each one | Skybrush fork of ArduCopter | `mav-multi-vehicle`, `nav-rtk`, `ap-notify` |
| Search and rescue | thermal camera | area coverage | ordinary GNSS | any | by the job | a quad or a VTOL | `ops-field`, `ops-weather` |

### Agriculture: spraying and spreading
**The job.** Apply a product at a rate q (L/ha) evenly, without gaps or overlaps, and keep the droplets from drifting beyond the edge of the field.

**Requirements from the formulas.** The swath width B (m) and the speed v (m/s) give the productivity P = B·v·3600/10,000 ha/h; the tank V (L) — the area per flight S = V/q; the pump flow Q = q·B·v·60/10,000 L/min. Example (the tank and the swath are within the T50 specification: 40 L, 4–11 m): B = 7 m, v = 6 m/s, q = 15 L/ha → P = 15.12 ha/h, with a utilization factor of 0.7 (turns, refilling; estimate) — 10.58 ha/h; S = 2.667 ha, for 40 ha — 15 flights; Q = 3.78 L/min against the T50 maximum of 16 L/min on two sprinklers; spraying per flight — 10.6 min. A track error of 10 % of the swath (0.7 m) already gives stripes, and ordinary GNSS is off by 2–3 m — RTK is needed (the T50 datasheet says ±10 cm). The height above the crop is held by a rangefinder or radar, not by the barometer (`est-alt-sources`, `nav-terrain`).

**Class and stack.** 40 kg of liquid means a takeoff weight of 92 kg: a heavy-class hexa or octo (`ap-heavy`). Production agricultural drones fly on manufacturers' firmware; the open stack is ArduCopter 4.7.2 with `AC_Sprayer` (`ap-payload`). How it meters (`libraries/AC_Sprayer/AC_Sprayer.cpp`): the pump gets `speed (m/s) × SPRAY_PUMP_RATE` percent of duty (10 % per 1 m/s by default), but no less than `SPRAY_PUMP_MIN` and no more than 100 %; spraying turns on when the speed has been no lower than `SPRAY_SPEED_MIN` (100 cm/s) for longer than 0.1 s, and turns off 1 s after it drops below. The flow grows with speed, and the rate per hectare is constant — until the pump hits 100 %. By default that is 10 m/s, and at 6 m/s the pump is already at 60 %: with a linear 16 L/min pump that is 9.6 L/min and 38.1 L/ha instead of 15. The example needs `SPRAY_PUMP_RATE` = 23.6 % / 6 m/s = 3.94; saturation is then at 25.4 m/s. The passes are convenient to fly in ZigZag mode: the spacing is `ZIGZ_SIDE_DIST` (4 m by default), and `ZIGZ_SPRAYER = 1` turns on spraying on the leg to point A or B.

{{diagram:chart-apps-spray-rate|With the default `SPRAY_PUMP_RATE` the rate in the example is 38.1 L/ha instead of 15 and drops above 10 m/s; the recalculated value of 3.94 holds 15 L/ha at any working pass speed.}}

**Rules.**
- **USA.** Part 137 on top of Part 107 (form 8710-3, a petition 120 days ahead — in `eng-career`). An exemption from § 107.36 is needed because a small UAV is prohibited from carrying hazardous material in the sense of 49 CFR 171.8. From 55 pounds (a T50 at 92 kg) — Parts 91 and 137 with exemptions from Parts 61, 91, 137 and an N-number through CARES instead of an FA number in DroneZone (FAA page, updated 28.10.2026).
- **EU.** Directive 2009/128/EC, Art. 9(1): aerial spraying is prohibited; Art. 9(2) allows exceptions when all the conditions are met at once, among them: there is no viable alternative or aerial application has clear advantages for health and the environment, the product is approved specifically for aerial application, the operator and the service are certified, the area is not close to housing. In aviation terms it is Specific; EASA names “agricultural works” among the typical applications of PDRA-S01, PDRA-S02 and PDRA-G03. On 16.12.2025 the Commission proposed allowing member states to take certain types of UAS out of the ban (2025/0409(COD), “Omnibus X”); as of 2026-11-22 it is a draft — check the stage.
- **United Kingdom.** HSE (updated 01.07.2026): spraying from a drone is aerial spraying, and every application needs an Aerial Spraying Permit; there are no commercial permits for drones, only an Extrapolated Trials Permit (3 years, £3,349); PA1 and PA6 certificates and a CAA authorization.

**Typical failures:** pump saturation; loss of RTK — stripes and gaps; slosh in a half-empty tank rocks the aircraft; the rangefinder “sees” the top of the crop differently at the edge; exceeding MTOW in the heat (`ops-weather`); chemicals in the connectors (`ops-maintenance`).

### Mapping, surveying and multispectral
**The job:** an orthophoto or an index map (NDVI) with a given GSD and accuracy. The formulas for GSD, overlaps, blur and RMSE are in `per-mapping`; here — how they set the class. An example camera (DJI Mavic 3M): a 1/2.8" sensor, 2592×1944 px, field of view 61.2° × 48.1°, bands 560 ± 16, 650 ± 16, 730 ± 16 (red edge) and 860 ± 26 nm. At 100 m the frame is 118.3 × 89.3 m, GSD = 4.56 cm/px; with a side overlap of 70 % the line spacing is 35.5 m, with a forward overlap of 80 % — a frame every 17.9 m. At 10 m/s — 127.7 ha/h on the lines alone: 120 ha is 56 min, more than the 40 min multirotor ceiling. So it is a VTOL or a plane (`ap-quadplane`), or two quad flights.

**Typical failures:** blur at a long exposure; too little overlap over terrain; no GCPs — the map is shifted by meters; multispectral data are compared between days without radiometric calibration — the difference in the “index” turns out to be a difference in lighting (what to calibrate — per the specification of your camera; not verified for specific models).

### Inspection: thermal camera and lidar
**The job:** find a defect (an overheated contact, a hot panel cell, a heat leak) and, if needed, measure the temperature.

- **Radiometric or not.** Teledyne FLIR divides thermography into qualitative (a picture for a human decision; for finding people “identifying specific temperatures isn't necessary”) and quantitative — the temperature of every pixel. Only a radiometric camera records it; a non-radiometric one gives a relative picture. A report saying “the contact is at 82 °C with neighbors at 41 °C” requires a radiometric one.
- **Error.** An example of the class — the Matrice 4T thermal camera: 640 × 512, 12 µm pixel, sensitivity ≤ 50 mK, accuracy in high gain ±2 °C or ±2 % (whichever is greater) in the −20…150 °C range, in low gain ±5 °C or ±3 % in 0…550 °C. According to FLIR, wrong emissivity and reflection shift the result by 2 °C and more — by the whole datasheet error.
- **Distance: the 3 × 3 rule.** FLIR: the target needs at least 3 × 3 pixels on it, otherwise a mix of target and background is measured. A pixel at a distance D covers s = D·p/f, hence D_max = L·f/(3p). Example (input data; the M4T specification does not state the focal length, and the 45° DFOV works out to about 12 mm): p = 12 µm, f = 13 mm, a 10 cm target → D_max = 36.1 m; at 20 m a pixel is 1.85 cm and the minimum target is 5.5 cm. That is why “from far away” with a big aircraft does not replace flying up close with a gimbal quad (`payload-gimbal`), and near metal GNSS and the compass degrade (`nav-resilience`, `per-depth-avoid`).
- **Qualification.** A thermographer — ISO 18436-7:2014 (three categories, confirmed in 2025). It is a standard for the person: a pilot certificate does not replace it.
- **Lidar — an overview.** Zenmuse L2: 905 g, up to 240,000 points/s with a single return, up to 5 returns; the datasheet 5 cm horizontally and 4 cm vertically — at 150 m, 15 m/s, with RTK FIX and processing in the manufacturer's software. The density per pass is ρ = PRR/(v·W), W = 2H·tan(FOV/2): at 240,000 points/s, 10 m/s, 100 m and a 70° field (input data of the example) — 171 points/m².

**Typical failures:** a non-radiometric camera in a report with degrees; a target smaller than 3 × 3 px; emissivity not set or a sun reflection in the frame; the aircraft loses heading near a metal structure.

### Delivery
**The job:** deliver cargo to a point at a distance d and return, having placed it with a winch, by a drop or with a landing. The mechanisms — `GRIP_*`, `WINCH_*` (Copter only; from 4.7 — in builds with more than 2 MB of flash), `NAV_PAYLOAD_PLACE` — are in `ap-payload`.

**Requirements.** t = 2d/v + t_winch + t_hover, the required flight time is t/(1 − reserve). Example: 8 km one way, 15 m/s, a 30 m line down and up at 1 m/s (`WINCH_RATE_MAX` by default), a 60 s hover → 1187 s = 19.8 min; with a 30 % reserve — 28.3 min. That is inside the 20–40 min of a multirotor, but at the edge: with 30 min the radius is 8.55 km, and beyond that — a VTOL. Almost all delivery is BVLOS over people, so redundancy (`el-redundancy`), a proven failsafe (`ap-safety-fs`) and the analysis of the Matternet M2 accident (`ops-case-studies`) are part of the requirements specification, not an option.

**Rules.**
- **USA.** Other people's cargo is carried for compensation only by a Part 135 certificate holder with an airspace authorization and a BVLOS exemption or waiver (FAA, updated 03.09.2026; holders include Wing, Zipline, Amazon Prime Air). § 107.205: a waiver of § 107.25 and § 107.31 is not issued for carrying another person's property for compensation. Part 108: the final rule has been under OIRA review since 10.07.2026 (RIN 2120-AL82, “Pending Review” as of 2026-11-22) and is not published in the Federal Register. The deadline under 49 U.S.C. 44811 (16 months after the proposed rule) is about December 7, 2026, according to a secondary source.
- **EU.** Specific. STS-02 — BVLOS over a controlled ground area in a sparsely populated environment, class C6, visibility greater than 5 km, no farther than 2 km from the pilot with observers and 1 km without them: not enough for 8 km. Beyond that — PDRA-G01 (“long range cargo”) or SORA; ÚCL has been accepting applications under SORA 2.5 since 01.06.2026 (`eng-career`).
- **United Kingdom.** BVLOS and dropping articles — only UK SORA (it replaced the OSC from 23.04.2025).

**Typical failures:** the load swinging on the line; the gripper opened on failsafe over people; loss of the BVLOS link; GNSS multipath near buildings at the drop point.

### Light shows
**The job:** hundreds of aircraft fly along computed trajectories with a set spacing and color; the failure of one does not bring down the others.

- **The stack.** Skybrush open-sourced most of its software in 2022; the server, the Live ground control station and the Studio add-on for Blender (checking spacing, speeds, altitude) are on GitHub under GPL-3.0. The onboard firmware is a modified ArduCopter: Skybrush asks you to flash exactly that (ready-made builds exist for common boards, for the rest you build it yourself); a flight controller with ArduPilot support and a microSD, 2 MB of flash recommended. The link is Wi-Fi (usually the Skybrush fork of `mavesp8266`), the emergency one-way channel is a SiK radio, plus an RC receiver; the light is RGBW (`ap-notify`, `mav-multi-vehicle`).
- **Accuracy.** Skybrush calls RTK “highly recommended”: the 2–3 m of ordinary GNSS → 1–10 cm. A 3 m spacing with a 2.5 m error is a ratio of 1.2, less than the “three times” rule: without RTK the picture is impossible; with RTK at 0.1 m the ratio is 30.
- **The number of aircraft.** A flat W × H picture with a spacing d holds (⌊W/d⌋ + 1)·(⌊H/d⌋ + 1) points: 60 × 30 m with a 3 m spacing — 21 × 11 = 231 aircraft. The wind at 120 m with 6 m/s at the weather station is 8.56 m/s (α = 1/7, `ops-weather`).

**Rules.** USA: a waiver of § 107.35 (several aircraft per pilot) and usually of § 107.29(a)(2) and (b) (anti-collision lighting at night and in twilight). An example is waiver 107W-2026-02200 (03.11.2026–30.11.2030): up to 3000 aircraft with redundant control and link, one observer per 250, FSDO notification 72 h ahead, only the declared model and show software. EU: Specific; PDRA-08 (VLOS with airspace observers, the typical application being swarming) is still under review at EASA. United Kingdom: a swarm — UK SORA. **Typical failures:** Wi-Fi overload with hundreds of aircraft; loss of RTK corrections in the middle of the show; a failed aircraft falls toward the spectators if the geofence and failsafe have not been tested (`ap-safety-fs`).

### Public safety and search (briefly)
Searching for people is qualitative thermography: contrast matters, not degrees, and radiometry is not required. USA: an agency flies under Part 107 (up to 55 pounds, ≤ 400 feet, VLOS) or as a public aircraft under a COA, certifying its aircraft and pilots itself; for emergencies the FAA issues expedited approvals. EU: under Art. 2(3)(a) of Regulation 2018/1139 it does not apply to police, search and rescue, firefighting, border control and similar flights under the responsibility of a state — national rules apply. The United Kingdom has not been verified for this niche.

### Rules by segment: where to look
An overview as of 2026-11-22 for planning, not legal advice: before the job, open the page from the references.

| Segment | USA (FAA) | EU (EASA) | United Kingdom (CAA and others) |
|---|---|---|---|
| Spraying | Part 107 + Part 137 (AAOC) + exemption; ≥ 55 pounds — Parts 91/137 | Art. 9 of Directive 2009/128/EC (a ban with exceptions) + Specific; proposal 2025/0409(COD) | HSE: Aerial Spraying Permit, trials only; CAA authorization |
| Surveying, VLOS inspection | Part 107 | Open A1–A3 or Specific | Open or PDRA01 (CAA: for example, roof inspection) |
| Long linear BVLOS inspection | waiver of § 107.31 | PDRA-G03 (“linear inspections”), SORA | UK SORA |
| Delivery | Part 135 + BVLOS exemption/waiver; Part 108 not published | STS-02, PDRA-G01, SORA | UK SORA (BVLOS, dropping) |
| Shows | waiver of § 107.35, § 107.29 | Specific; PDRA-08 under review | UK SORA (swarm) |
| Government services, search | Part 107 or public aircraft COA | outside 2018/1139, Art. 2(3)(a) | not verified |

A weight from 25 kg takes you out of Open in the EU and the United Kingdom; in the USA the threshold is 55 pounds (24.95 kg).

### Place in the system

- **Receives:** the flight time and the layout class from the weight (`des-sizing`); the rules of your country and the template for summarizing them (`f-regulations`); the GSD and overlap formulas (`per-mapping`); the drop, winch and sprayer mechanisms (`ap-payload`).
- **Provides:** the requirements table — to the aircraft requirements specification (`des-sizing`, `ap-heavy`); the RTK requirement — to `nav-rtk`; the payload class and the gimbal — to `payload-gimbal`; the chosen niche — to the career plan (`eng-career`).
- **If you get it wrong here:** you did not calculate pump saturation → under-application at speed, visible only as stripes on the field and not in the log (`ap-payload`); you took a quad for a 56 min mission → a landing on reserve in the middle of the field (`ops-weather`); a show without RTK → aircraft close in by the GNSS error, analysis — `mav-multi-vehicle`.

## practice
### Step 1. Mapping: from GSD to class
The mission: an NDVI map of a 120 ha field with a GSD no worse than 5 cm; the camera as in the walkthrough (field of view 61.2° × 48.1°, 2592 px across), overlaps of 80 % forward and 70 % side, speed 10 m/s, a multirotor ceiling of 40 min. Calculate: the maximum height for 5 cm (H = 5/GSD₁₀₀·100), the GSD at 100 m, the line spacing, the frame interval, the productivity and the time on the lines alone. Compare the time with 40 min and choose the class by step 3 of the rule.

### Step 2. Thermal camera: distance and camera type
The mission: find overheated 10 cm contacts at a substation and record their temperature in a report for yourself; the camera: 12 µm pixel, 13 mm lens. Calculate D_max by the 3 × 3 rule and the pixel size at 20 m. Decide: radiometric or not; what the error of an M4T-class camera is at 80 °C in high gain mode (the greater of 2 °C and 2 %).

### Step 3. Show: the number of aircraft and RTK
The mission: a flat 60 × 30 m picture, 3 m spacing, altitude 120 m, wind at the weather station 6 m/s. Calculate the number of aircraft, the number of observers per the waiver example (1 per 250, rounded up), the ratio of the spacing to the position error for 2.5 m and 0.1 m, and the wind at 120 m.

### Step 4. Delivery: is a multirotor enough
The mission: 2 kg over 8 km, cruise 15 m/s, a 30 m line at 1 m/s, a 60 s hover, a 30 % reserve. Calculate the required flight time and the radius with 30 min; choose the class and the regulatory corridor for your country from the table.

The output of the module's script (`calc.py` in the module's scratchpad, the same calculation):

```
footprint 118.3 x 89.3 m; GSD = 4.56 cm/px
line spacing 35.5 m; shot interval 17.9 m
coverage at 10.0 m/s = 127.7 ha/h; 120.0 ha -> 56 min (lines only)
altitude for GSD 5 cm = 109.6 m
pixel footprint at 20.0 m = 1.85 cm; min target 3x3 = 5.5 cm
Dmax for 10 cm target = 36.1 m
grid 21 x 11 = 231 drones; VOs at 1/250 = 1
  pos error 2.5 m -> spacing/error = 1.2
  pos error 0.1 m -> spacing/error = 30.0
wind at 120.0 m from v10=6.0: 8.56 m/s
cruise 1067 s, winch 60 s, hover 60 s, total 1187 s = 19.8 min
required endurance with 30% reserve = 28.3 min
radius with 30.0 min endurance = 8.55 km
```

### Moving to real hardware
If you have an ArduCopter with a sprayer, check the metering with water before the first flight with a product. Propellers are off for the whole duration of the check. `SPRAY_ENABLE = 1`, the pump and spinner outputs are functions 22 and 23, the switch is `RCx_OPTION = 15`. While disarmed, the switch at HIGH turns on a test: the pump runs as if the aircraft were flying at 1 m/s, that is at `SPRAY_PUMP_RATE` percent of duty, but no lower than `SPRAY_PUMP_MIN` (`RC_Channel.cpp`, `do_aux_function_sprayer`; `AC_Sprayer::update`). Collect the water for 60 s in a measuring container. The required flow at 1 m/s: Q₁ = q·B·60/10,000; for the example (15 L/ha, 7 m) — 0.63 L/min. If you measured more, reduce `SPRAY_PUMP_RATE` proportionally and repeat. If the pump does not spin at 4 % duty or is nonlinear (estimate: typical of cheap pumps), set `SPRAY_PUMP_RATE` = 3.94 × 6 = 23.6 for the duration of the test — the test will show the flow at the working speed, 3.78 L/min; then put 3.94 back. Criteria: the test flow is within ±5 % of Q₁ (the tolerance is a course estimate); at full pass speed `speed × SPRAY_PUMP_RATE` is less than 100 %; after arming the test is off (`AP_Arming_Copter.cpp` calls `test_pump(false)`).

Self-check: the lab is complete when (1) step 1: H for 5 cm = 109.6 m (±1 m), GSD at 100 m = 4.56 cm/px (±0.05), line spacing 35.5 m, interval 17.9 m, 127.7 ha/h and 56 min (±1 min), the class — a VTOL/plane or two quad flights; (2) step 2: D_max = 36.1 m (±0.5 m), the pixel at 20 m is 1.85 cm, the camera is radiometric, the error is ±2 °C; (3) step 3: 231 aircraft, 1 observer, ratios of 1.2 and 30, the conclusion “RTK is needed”, wind 8.56 m/s (±0.1); (4) step 4: 28.3 min (±0.3) and 8.55 km (±0.1), the class — a multirotor with a winch at the limit, the corridor — BVLOS (Part 135 + exemption in the USA, Specific in the EU, UK SORA). All four items belong to the calculation path; the pump check criteria are for hardware only.

**Reference for self-check.**

| Step | Correct result | Common mistake and its cause |
|---|---|---|
| 1 | 4.56 cm/px, 56 min → not one quad flight | 4.56 mm: the units are mixed up; 17 min: the line spacing is taken equal to the frame width of 118.3 m, the side overlap is forgotten, and the job falsely fits into one flight |
| 2 | 36.1 m, radiometric | 108 m: the factor of 3 is forgotten (one point per target); “any will do” — the report needs degrees, not a picture |
| 3 | 231, RTK is mandatory | 200 = 20 × 10: the edge rows are lost (the +1 in the formula); “GNSS is enough” — the ratio of 1.2 is less than 3 |
| 4 | 28.3 min, 8.55 km | 19.8 min: the reserve is not included; 17.1 km: the radius is not divided by 2 (there and back) |

## diagnostics
- **Symptom:** stripes of under-application on the field, while in the log spraying is “on” the whole time
  - Possible cause: the pump is saturated: `speed × SPRAY_PUMP_RATE` ≥ 100 %; by default that is 10 m/s.
  - What to do: recalculate `SPRAY_PUMP_RATE` for the rate and the pump flow, reduce the pass speed, check with water by the procedure from the practice.
- **Symptom:** stripes of double rate and gaps spaced one pass apart
  - Possible cause: the track error is comparable to the swath width — flying without RTK FIX, or the `ZIGZ_SIDE_DIST` spacing does not equal the real swath.
  - What you see in the log: `GPS.Status` less than 6 (6 — RTK Fixed, 5 — RTK Float), `GPA.HAcc` on the order of meters.
  - What to do: RTK (`nav-rtk`), the pass spacing — from the swath measured at your height.
- **Symptom:** the NDVI of one field “changes” from flight to flight
  - Possible cause: different lighting without radiometric calibration.
  - What to do: calibration by the camera manufacturer's procedure, surveying at the same time of day.
- **Symptom:** the temperature of an overheated contact in the report is lower than that of the neighboring one
  - Possible cause: the target is smaller than 3 × 3 px or the emissivity is wrong; according to FLIR that is a shift of 2 °C and more.
  - What to do: fly closer than D_max = L·f/(3p), set the emissivity of the material, eliminate reflections.
- **Symptom:** the delivery aircraft lands on reserve before returning
  - Possible cause: the radius was calculated without the hover and winch or without the reserve; a headwind on the way back.
  - What to do: t/(1 − reserve) with the wind per `ops-weather`; with t at the limit of 20–40 min — a VTOL.
- **Symptom:** at the show rehearsal two aircraft come closer than the spacing
  - Possible cause: no RTK corrections on some of the aircraft, an error of 2–3 m against a 3 m spacing.
  - What to do: check the RTK fix of each one before takeoff, increase the spacing or do not take off; the check of spacing and speeds is Safety Check in Skybrush Studio.

## references
- FAA — Dispensing Chemicals and Agricultural Products (Part 137) with UAS (updated 2026-10-28; verified 2026-11-22) | https://www.faa.gov/uas/advanced_operations/dispensing_chemicals | primary | A
- eCFR / LII — 14 CFR § 107.36 Carriage of hazardous material | https://www.law.cornell.edu/cfr/text/14/107.36 | primary | A
- eCFR / LII — 14 CFR § 107.205 List of regulations subject to waiver | https://www.law.cornell.edu/cfr/text/14/107.205 | primary | A
- eCFR / LII — 14 CFR § 107.23 Hazardous operation (dropping objects) | https://www.law.cornell.edu/cfr/text/14/107.23 | primary | A
- FAA — Package Delivery by Drone (Part 135) (updated 2026-09-03) | https://www.faa.gov/uas/advanced_operations/package_delivery_drone | primary | A
- reginfo.gov — RIN 2120-AL82, Normalizing UAS BVLOS Operations: Final Rule, Pending Review since 2026-07-10 (verified 2026-11-22) | https://www.reginfo.gov/public/do/eo/neweomeeting?rin=2120-AL82 | primary | A
- Federal Register (govinfo) — Normalizing Unmanned Aircraft Systems Beyond Visual Line of Sight Operations, NPRM, 90 FR 38212, docket FAA-2025-1908 (2025-08-07) | https://www.govinfo.gov/content/pkg/FR-2025-08-07/html/2025-14992.htm | primary | A
- FAA — Certificate of Waiver 107W-2026-02200 (drone light show, § 107.35, § 107.29; up to 3000 aircraft) | https://www.faa.gov/sites/faa.gov/files/107W-2026-02200-Jamison-Russell-CoW.pdf | primary | A
- FAA — Operate a Drone, Start a Drone Program (public safety: Part 107 or COA) | https://www.faa.gov/uas/public_safety_gov/drone_program | primary | A
- EASA — Predefined Risk Assessment (PDRA): S01, S02, G01, G02, G03, PDRA-05…08 under review (verified 2026-11-22) | https://www.easa.europa.eu/en/domains/drones-air-mobility/operating-drone/specific-category-civil-drones/predefined-risk-assessment-pdra | primary | A
- EASA — Easy Access Rules for UAS: STS-01/STS-02 | https://www.easa.europa.eu/en/document-library/easy-access-rules/online-publications/easy-access-rules-unmanned-aircraft-systems?page=8 | primary | A
- EASA — FAQ 19236: exclusions under Article 2(3) of Regulation 2018/1139 | https://www.easa.europa.eu/en/faq/19236 | primary | A
- Directive 2009/128/EC, Article 9 Aerial spraying (text as adopted) | https://legislation.gov.uk/eudr/2009/128/article/9/adopted | primary | A
- European Parliament Legislative Observatory — 2025/0409(COD), summary of the Commission proposal (2025-12-16) | https://oeil.europarl.europa.eu/oeil/en/document-summary?id=1880196 | primary | A
- HSE — Aerial spraying permit arrangements (updated 2026-07-01) | https://www.hse.gov.uk/pesticides/using-pesticides/general/aerial-spraying.htm | primary | A
- UK CAA — Specific Category overview (PDRA01, UK SORA from 2025-04-23) | https://www.caa.co.uk/drones/specific-category/specific-category-overview/ | primary | A
- ArduPilot 4.7.2 — libraries/AC_Sprayer/AC_Sprayer.cpp (SPRAY_*, pump duty calculation) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AC_Sprayer/AC_Sprayer.cpp | primary | A
- ArduPilot 4.7.2 — ArduCopter/mode_zigzag.cpp (ZIGZ_SPRAYER, ZIGZ_SIDE_DIST) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/ArduCopter/mode_zigzag.cpp | primary | A
- ISO 18436-7:2014 — Qualification and assessment of personnel: Thermography (confirmed in 2025) | https://www.iso.org/standard/61417.html | primary | A
- Teledyne FLIR — Qualitative vs. Quantitative Thermography | https://www.flir.com/discover/professional-tools/qualitative-vs.-quantitative-thermography-understanding-what-is-required-and-when | primary | B
- Teledyne FLIR — How Far Can You Measure with a Thermal Camera? (3 × 3 pixels) | https://www.flir.com/discover/professional-tools/how-far-can-you-measure-with-a-thermal-camera/ | primary | B
- Skybrush — Building custom drones (ArduCopter fork, RTK 2–3 m → 1–10 cm, Wi-Fi, 2 MB flash) | https://docs.skybrush.io/public/faq/latest/building-custom-drones.html | primary | A
- Skybrush — Firmware documentation (fork of ArduPilot) | https://docs.skybrush.io/public/skybrush-firmware-doc/latest/index.html | primary | A
- Skybrush — GitHub organisation (server, live, studio-blender under GPL-3.0) | https://github.com/skybrush-io | primary | A
- DJI — AGRAS T50 specs (class example: 40 L tank, 4–11 m swath, 16 L/min, MTOW 92/103 kg, RTK ±10 cm, wind 6 m/s) | https://ag.dji.com/t50/specs | primary | B
- DJI — Mavic 3 Multispectral specs (class example: 2592×1944, 61.2° × 48.1°, bands 560/650/730/860 nm) | https://enterprise.dji.com/mavic-3-m/specs | primary | B
- DJI — Matrice 4 Series specs (class example: 640×512, 12 µm, ±2 °C or ±2 %) | https://enterprise.dji.com/matrice-4-series/specs | primary | B
- DJI — Zenmuse L2 specs (class example: 905 g, 5/4 cm at 150 m with RTK FIX) | https://enterprise.dji.com/zenmuse-l2/specs | primary | B
- UAShield — Is Part 108 Final? (the deadline under 49 U.S.C. 44811 is about 2026-12-07; status as of 2026-11-13) | https://uashield.com/guides/part-108-bvlos-status | secondary | B
- Euronews — Regulatory roadblocks for commercial use of drones in Europe (2026-03-31) | https://www.euronews.com/2026/03/31/regulatory-roadblocks-for-commercial-use-of-drones-in-europe | secondary | C

## checklist
- The mission is described in one sentence with numbers: what, where, how much, how accurately, over whom
- Six requirements are written out: payload, working time, accuracy, wind at the working height, consequences of a failure, hovering
- The class is chosen by the tree, not by the aircraft at hand; a weight > 25 kg and BVLOS are marked as leaving Open
- For a sprayer, `SPRAY_PUMP_RATE` is recalculated for the rate, and pump saturation is above the pass speed
- For a thermal camera, the 3 × 3 rule is checked and the radiometric type is chosen if the report needs degrees
- The regulatory corridor of your country is written out with a link to the regulator's page and the date of the check
