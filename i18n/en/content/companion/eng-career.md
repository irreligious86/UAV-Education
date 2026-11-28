---
id: eng-career
title: "A career in drones: roles, skills, certificates, portfolio"
level: L1
readingTime: 35 min
firmware: any firmware
status: published
added: 2026-11-22
tags:
  - career
  - portfolio
  - certificates
  - open source
related:
  - eng-method-101
  - eng-systems
  - f-regulations
  - fw-reading
  - ops-pilot-training
next:
  - eng-method-101
source: content/companion/eng-career.md
source_hash: 3dbcd7af9b01
---

## summary
The course teaches UAV engineering, but until now it left the question "what job do I do with this" to the reader. This module breaks the industry down into twelve roles: what each one does on an ordinary day, which course tracks and modules cover it, and what a candidate should be able to show at the door. Then: how to turn the capstone and the course projects into a portfolio that can be checked without the author; how to make a first contribution to ArduPilot, PX4, Betaflight or INAV; which pilot certificates you need in the EU (using Czechia as the example), the UK and the US, and what is known about Ukraine, from official sources only, as of November 2026; and what can and cannot be said about salaries. The practice needs no hardware and no simulator: you pick a role, compute in percent how much of its skill set your completed modules cover, draw up a plan of three portfolio pieces, and write down the steps to a certificate in your country.

## theory
### How to read the industry: a role is a set of verifiable skills
Job ads give the same work different names, so in this module a role is described not by its title but by what the person does and how they prove it. The twelve roles below cover almost everything you meet around small UAVs, from pilot to safety engineer. The further from flying, the less a pilot certificate matters and the more the artifacts do: code, logs, calculations, documents.

A pilot certificate (Part 107, A2 CofC, Flyer ID) is permission to fly, not a profession. When money is involved, the customer pays for a result in their niche: an inspection report with georeferenced findings, an orthomosaic with measured accuracy, a tuned vehicle with an analyzed log. So the answer to "should I become a pilot" is: yes, if the permission comes with data-processing skill in a specific niche (mapping, thermal inspection, agriculture, filming). On its own, the certificate is an entry ticket.

### Role map
| Role | What it does on an ordinary day | Course modules | What to show at the door | Tools |
|---|---|---|---|---|
| FPV pilot / instructor | flights to a brief, preflight preparation, training, logbook | `ops-pilot-training`, `f-safety`, `f-regulations`, `ops-field`, `bf-setup-scratch`, `bf-failsafe` | your country's certificate, a flight-hours log, the `diff all` and failsafe check from `cap-first-quad`, video | simulator, EdgeTX, Betaflight App |
| UAS operator: inspection, mapping, agriculture, delivery | mission planning, flight, data processing, report to the customer | `ap-missions`, `ops-weather`, `ops-field`, `per-camera`, `per-mapping`, `est-gnss` | `proj-inspection` or `proj-photogrammetry` with RMSE on checkpoints, a certificate of the right category | Mission Planner, QGroundControl, OpenDroneMap, QGIS |
| Flight test engineer | test plan, flights to the program, log analysis, a verdict on each item | `eng-systems`, `ap-logs`, `bf-blackbox`, `ap-tuning`, `des-thrust-stand`, `diag-troubleshooting` | a test plan with expected numbers and a log analysis ending in "pass / fail" (`cap-heavy-or-vtol`) | MAVExplorer, PX4 Flight Review, Blackbox Explorer, Python |
| Controls / GNC engineer | models, controllers, state estimation, system identification from logs | `ctl-theory`, `ctl-sysid`, `ctl-guidance`, `ctl-allocation`, `est-kalman`, `ap-ekf`, `math-ode-dyn` | your own filter validated on real data (`cap-estimation`); a model identified from a log, with its error in numbers | Python (NumPy, SciPy), SITL |
| Embedded / firmware (PX4, ArduPilot, Betaflight) | drivers, firmware modules, loop time budget, tests, review | `emb-basics`, `emb-protocols`, `fw-reading`, `bf-custom`, `comp-esp32`, `mav-component`, `eng-ci-configs` | `proj-esp32-component`, your own PR or a bug reproduced in SITL | C/C++, PlatformIO / ESP-IDF, logic analyzer, git |
| Hardware / electronics | power and communication schematics, PCB layout, measurements, EMC | `el-power-design`, `el-measure`, `el-kicad`, `el-wiring`, `el-emi`, `el-battery-packs`, `el-redundancy` | a power schematic with calculations and measurements under load (`cap-electronics`), a KiCad project | KiCad, oscilloscope, multimeter, wattmeter |
| RF / radio link | link budget, antennas, choice of bands and power levels, field measurements | `rf-link-budget`, `rf-antennas`, `link-elrs`, `link-vtx`, `link-telemetry-radios`, `link-digital-video` | a link budget and a field RSSI / LQ measurement compared with the calculation | link budget calculator, ExpressLRS Configurator, spectrum analyzer or SDR |
| Perception / CV / ML | cameras and calibration, detectors, tracking, marker-based landing, deployment on board | `per-camera`, `per-geometry`, `per-cv`, `per-edge-ml`, `per-tracking`, `per-landing`, `per-vision-pipeline` | `proj-precision-landing` (landing error ≤ 15 cm in 9 of 10 runs) or `proj-detect-follow` (latency ≤ 150 ms) | OpenCV, ONNX, Jetson, Gazebo |
| ROS 2 robotics | nodes, launch files, the bridge to the autopilot, navigation, bag recordings | `ros2-basics`, `ros2-px4`, `ros2-ardupilot`, `ros2-app-arch`, `ros2-nav`, `tools-gazebo` | a ROS 2 package with a launch file and a test on a bag (`proj-detect-follow`) | ROS 2, colcon, rosbag, Gazebo |
| Systems / reliability / safety engineer | requirements, traceability, FMEA, operational risk assessment (SORA in the EU) | `eng-method-101`, `eng-systems`, `ap-safety-fs`, `el-redundancy`, `f-regulations`, `f-remote-id-security` | an FMEA of 15+ rows with recalculated RPN and the traceability matrix from `eng-systems` | requirements tables, FMEA, the SORA methodology |
| Technician / maintenance | assembly, repair, soldering, replacements by service hours, preflight checks | `ops-maintenance`, `f-frame-mech`, `f-motors-esc`, `el-wiring`, `el-measure`, `diag-troubleshooting` | a build record (`cap-foundation`), a vehicle logbook with service hours and replacements | soldering iron, multimeter, wattmeter, vehicle logbook |
| Product / field application engineer | choosing a configuration for a customer's task, demonstrations, failure analysis at the customer's site | `f-components-choice`, `des-sizing`, `comp-intro`, `ops-case-studies`, `diag-troubleshooting` | a vehicle sized to a specification (`cap-designer`) and one failure analyzed along the chain "cause → symptom → mitigation" | datasheets, SITL for demonstrations, documentation |

{{diagram:career-role-map|No role is covered by a single track: each needs from two (radio link) to five (flight testing, product), and almost every one involves a track that looks like "someone else's".}}

### Operator niches: what is behind them
- **Agriculture (spraying), US.** Per the FAA page (updated October 28, 2026): a Remote Pilot certificate and aircraft registration; a Part 137 agricultural aircraft operator certificate (Agricultural Aircraft Operator Certificate, form 8710-3, filed after you receive an exemption number); an exemption: for aircraft under 55 pounds, from § 107.36 and a number of Part 137 rules; for aircraft of 55 pounds and up, operation under Parts 91 and 137 with exemptions from Parts 61, 91 and 137; the petition is filed at least 120 days in advance. The FAA does not mention a state pesticide applicator license on that page; Pennsylvania, for example, requires one (category 25, Aerial Applicator, per Penn State Extension, a secondary source, June 2025).
- **Drone shows.** Skybrush, a platform for controlling shows and drone swarms, announced in 2022 that it had made most of its software open source. The engineering base here is many vehicles on one network and a reliable failsafe: `mav-multi-vehicle`, `ap-safety-fs`.
- **Delivery** rests on BVLOS: in the US, Part 108 has not been published as of November 2026, and operations run under waivers; in the EU, under the Specific category (`f-regulations`, `ops-case-studies`).
- **Inspection** requires thermal imaging and data processing. Personnel qualification in thermography is described by ISO 18436-7:2014 (three categories; the standard was confirmed in 2025).

A services business of your own follows the same logic: a niche, a certificate of the right category, insurance (in the UK it is mandatory for any paid work, `f-regulations`), data-processing skill, and a price per result (per report, per hectare, per orthomosaic), not per flight hour.

### A portfolio from the course: what counts as evidence
An employer, like you yourself six months from now, checks reproducible artifacts, not words. The course's standard for any portfolio piece:

1. **A repository with a README**: what it is, what the task was, how to run it with one command, and the results in numbers (not "it works" but "landing error 9 cm in 9 of 10 runs").
2. **Configuration**: `diff all` (Betaflight, INAV), `.param` (ArduPilot), a PX4 parameter file, with a comment on every changed value.
3. **Logs and plots**: the original log (`.bin`, `.ulg`, `.bbl`), the plot the conclusion is drawn from, and a "before / after" line.
4. **A short video** of 30–120 s: a hover, a mission in SITL, a failsafe triggering.
5. **A written FMEA**, or at least three failure rows with mitigations and their verification (`eng-systems`).

This is exactly what the "Systems thinking" criterion of the course's common project rubric requires: a system diagram with interfaces, the effect of each decision on neighboring subsystems with a number, and a failure analyzed along the chain "cause → symptom → system response".

| Course work | For which roles | What must be in the repository |
|---|---|---|
| `cap-first-quad` | pilot, technician | `diff all` in git, a failsafe test report, a 30 s hover video |
| `cap-tune-by-logs` | flight testing, GNC, embedded | profiles A/B/C/D, spectra before/after in dB, a table of metric medians |
| `cap-estimation` | GNC, perception | the filter code with tests, a comparison with ATT from a log |
| `cap-electronics` | hardware, RF | the power schematic, current calculations, measurements under load, a link budget |
| `cap-heavy-or-vtol` | flight testing, operator | `.param` with rationale, a mission in SITL, an analysis of VIBE, ERR, ATT, BAT |
| `proj-esp32-component` | embedded | the firmware and its twin, a shared test suite, a SITL log with RFND |
| `proj-log-service` | flight testing, embedded | the tool, three reports on your own logs and a comparison with a manual analysis |
| `proj-fleet-ci` | embedded, systems | CI with SITL tests, a red test blocks the merge, logs as artifacts |
| `proj-precision-landing` | perception | the autopilot parameters, a report on 10 landings |
| `proj-inspection`, `proj-photogrammetry` | operator | the mission, frame georeferencing, RMSE on checkpoints |

### Open source as a way into the profession
A contribution to ArduPilot, PX4, Betaflight or INAV is public proof that you can read someone else's code, follow someone else's rules and get through review. The rules below are taken from the projects' own files (the `master` / `main` branches as of 2026-11-22):

- **ArduPilot** (`.github/CONTRIBUTING.md`): you can start with testing, a good bug report (steps to reproduce, a `.bin` log, facts only), or reviewing other people's PRs. Tasks for newcomers carry the `good first issue` label; issues are not assigned to people: you do the work and open a PR, after first checking that there is no PR on the topic already. A patch: a separate branch, small commits, one library each, a title `Subsystem: description` under 72 characters, testing in SITL, and testing evidence in the PR description (log plots before and after). The documentation is a separate repository, `ardupilot_wiki`, and the PR says `Resolves #N`.
- **PX4** (`CONTRIBUTING.md`): GitHub flow, a branch from `main`, commit messages in the conventional commits format `type(scope): description` (`fix(mavlink): …`), with formatting checked by astyle and clang-tidy in CI. A bug fix comes with a regression test, or, where a test is not feasible, with a link to a log in Flight Review and the reproduction steps. Once review has begun, add new commits instead of rewriting history. The documentation lives in the same repository (`docs/en`), and simple edits are made with the "Edit on GitHub" button. AI assistants are allowed, but the commit must carry an `Assisted-by:` trailer.
- **Betaflight** (`CONTRIBUTING.md`, the PR template): the tracker is only for bugs with steps to reproduce; setup questions go to Discord. A PR is not opened from the `master` of your fork, it targets the project's `master`, it contains one change, preferably as one commit, with `Fixes #N`. Before submitting, run `make preview` (a quick subset of the CI builds; the PR template at tag 2025.12.5 still called it `make pre-push` and mentioned Azure Pipelines, although the Makefile at the same tag already has only the `preview` target, and CI is GitHub Actions); board configurations live in a separate repository, `betaflight/config`.
- **INAV** (`docs/development/Contributing.md`): the project especially needs testers for PRs labeled "Testing Required", documentation reviewers (the "Review needed" and "Documentation" labels), and issue triage: reproducing the problem and gathering the missing information.
- **GSoC.** ArduPilot takes part in Google Summer of Code every year; in 2026, Google gave the project three slots for 130 applications. Previous PRs are not required ("not a requirement"), but the application asks for links to contributions to ArduPilot or other open source projects, if you have any, and a work plan with a timeline.

A first contribution is almost always small: a documentation fix, a bug reproduced in SITL with a log and steps, a test for an existing feature. That is normal: its value is that it was accepted under the project's rules.

{{diagram:career-first-contribution|A first contribution is not a new feature but a reproduced problem with a log and a small PR with proof of testing; a link to a merged PR in your portfolio weighs more than the line "I know C++".}}

### Pilot certificates by region (as of November 2026)
Checked against the official pages on 2026-11-22. This is an overview for planning, not legal advice: before you act, open the regulator's page from the references section.

| Region | Document | How to get it | What it allows | Validity, cost |
|---|---|---|---|---|
| EU (EASA), all countries | proof of completion of online training A1/A3 | an online course and an online exam with the national authority | the A1 and A3 Open subcategories | 5 years; recognized in all EASA countries; the price depends on the country |
| EU | A2 certificate of competency (A2 CofC) | A1/A3 + self-practical training under A3 conditions + a declaration of it + an additional exam with the authority (≥ 75 %) | the A2 subcategory | 5 years |
| EU | STS certificate | an online course and exam + an additional exam with the authority + accreditation of the practical training (a recognized entity or an operator with an STS declaration) | STS-01: VLOS over a controlled ground area, class C5; STS-02: BVLOS with observers in a sparsely populated area, visibility > 5 km, class C6 | 5 years; renewal by proof of recurrent competency or a refresher course |
| Czechia (ÚCL) | A1/A3, A2 | pilot registration at `dron.caa.gov.cz`; the A1/A3 test: 40 questions, 1 of 4 correct, ≥ 75 %, 60 min; A2: application and test booking through "Profil pilota" | as in the EU | minimum age 16; renewal no earlier than 180 days before expiry: training + test; once expired, start over; fees are not stated on the public pages |
| UK (CAA) | Flyer ID | a free online test | flying in Open (together with an Operator ID, where one is needed) | 5 years; under 13, with a parent |
| UK | Operator ID | operator registration | mandatory depending on mass and camera (`f-regulations`) | £12.34 per year, 18 and over |
| UK | A2 CofC | through an RAE(PC): theory, ≥ 30 questions, self-practical training; a Flyer ID is required | Open A2 (from 2026, Near People) | 5 years; the price is set by the organization |
| UK | GVC | through an RAE-PC | Specific, VLOS only, fixed-wing and multirotor | 5 years; issued until December 31, 2027, then RPC-L1/L2/L3 |
| US (FAA) | Remote Pilot Certificate, Part 107 | age 16 and over, English language; an FTN in IACRA → the UAG test at a testing center → form 8710-13 → TSA vetting → a temporary, then a permanent certificate | any flights not for recreation | the test is about $175 (per the FAA FAQ, charged by the center); a recurrent online course every 24 calendar months, free |
| Ukraine | — | an official procedure for a civil certificate could not be confirmed on the State Aviation Service website as of November 2026 | — | not verified |

**Ukraine: what is confirmed.** On January 14, 2025, the Ministry of Defence approved basic qualification levels for UAV operators (BKR I–IV) within an experimental project for certifying operator schools (Cabinet of Ministers Resolution No. 1129 of 01.10.2024); each level requires training with a practical demonstration. On July 17, 2025, the Ministry of Defence amended its orders on state aviation: for the duration of martial law and three months after it, some rules do not apply to single-use UAVs or to "micro" UAVs up to 2 kg and "mini" UAVs up to 15 kg; clearance to operate them is given by a commander's order. This is the domain of state aviation; check the civil rules, flight restrictions and pilot requirements on the State Aviation Service website (avia.gov.ua); a template for your notes is in `f-regulations`.

**Additional documents (FAQ M6).** A2 CofC and GVC are above; Part 137 is in the niches; thermography qualification is ISO 18436-7. For Specific in the EU, the rules contain no separate "SORA certificate": SORA is a risk assessment methodology under which the operator obtains an authorization; for example, ÚCL has accepted applications under SORA 2.5 since June 1, 2026, and has announced a full switch to it from January 1, 2027.

### Education and money
- **The path into a role.** The US Bureau of Labor Statistics (BLS) gives a bachelor's degree in aerospace engineering or a related field as the typical entry for aerospace engineers, and for technicians (aerospace engineering and operations technologists and technicians) an associate degree (two years), sometimes a high school diploma with a certificate. Self-study and bootcamps are not covered by official statistics; their result can be verified only through a portfolio. A degree gets you past the formal screening, a portfolio through the technical interview; one does not replace the other.
- **Salaries only from published statistics.** BLS, US, May 2025 data: the median for aerospace engineers is $134,960 per year, for aerospace engineering and operations technologists and technicians $82,890 per year; both pages mention drones as a factor in demand. There is no separate "drone pilot" occupation in this classification, so pilot figures from blogs and school surveys are not included in the module. For the EU, the UK and Ukraine we found no official figures for drone roles specifically, so we give no numbers.

### The technical interview: question types and where they are in the course
Below are the types of problems that test engineering skills in this field; specific companies' questions are not given.

| Problem type | What it tests | Modules | What to bring |
|---|---|---|---|
| Tuning a control loop | stability margin, the effect of P/I/D and filters, loop rate | `ctl-theory`, `bf-pid`, `ap-tuning`, `px4-control` | spectra and step response before/after |
| State estimation | complementary filter vs EKF, innovations, altitude and heading sources | `est-attitude`, `est-kalman`, `ap-ekf` | your own filter and a comparison with ATT |
| Failsafe design | order of reactions, timeouts, what if the protection itself fails | `bf-failsafe`, `ap-safety-fs`, `px4-safety-return` | a failsafe matrix: expected and observed |
| Timing in embedded software | main loop budget, interrupts, DMA, jitter | `emb-basics`, `fw-reading` | a loop time measurement, your own patch in SITL |
| Radio link budget | FSPL, margin, antennas, power and legality | `rf-link-budget`, `rf-antennas` | a calculation and a field measurement |
| Log analysis | vibration, voltage sag, EKF, cause and mitigation | `ap-logs`, `bf-blackbox`, `diag-troubleshooting` | a `proj-log-service` report |
| Systems thinking | requirements, FMEA, traceability | `eng-systems` | an FMEA and a traceability matrix |

How to prepare: for each type, one piece of your own work that you can explain at a whiteboard in 5 minutes, with a number from your own log.

### Where it fits

- **Takes in:** the labs and capstones of all tracks as artifacts (`cap-first-quad`, `cap-tune-by-logs`, `eng-systems`); your country's rules and the template for summarizing them (`f-regulations`); the ability to read source code and build SITL (`fw-reading`).
- **Hands off:** the chosen role and its list of gaps, to the order in which you take the tracks; the requirements for how work is presented (README, config, log, FMEA), to every lab starting with `eng-method-101`.
- **If you get this wrong:** a role chosen without a skill map → you go through the modules in order, and the gap in `emb-protocols` or `ap-safety-fs` surfaces at the interview; a portfolio piece without a config and a log → it cannot be reproduced, and `cap-tune-by-logs` turns into screenshots; a certificate of the wrong category → legal work in the niche is impossible (`f-regulations`).

## practice
### Step 1. Choose a role and list its skills
Take one target role from the role map and write down 8–12 skills, each with the course modules that cover it (from the "Course modules" column and adjacent tracks). Phrase a skill as an action with a check, not as a topic: "find the cause of vibration from a log and confirm it with a fix", not "logs".

### Step 2. Compute the coverage
The rule for rating a skill: 1 means all its modules are mastered (quiz ≥ 80 %, problems solved, all lab criteria met, which is how progress is counted on the site); 0.5 means some of its modules are mastered; 0 means none. Two metrics:

- strict coverage = (number of skills rated 1) / N × 100 %;
- weighted coverage = (number rated 1 + 0.5 × number rated 0.5) / N × 100 %.

Modules not on the role's skill list do not count toward coverage, even if completed. The gaps are the uncompleted modules on the list; the sum of their hours from the course program divided by your hours per week (rounded up) is the number of weeks to close the gaps. The prerequisites of the gap modules are not included; add their hours separately.

Worked example (a script in the module's scratchpad, output below). Role: embedded / firmware, entry level. Mastered: `tools-overview`, `eng-method-101`, `bf-failsafe`, `bf-pid`, `bf-blackbox`, `bf-filters`, `ctl-signals`, `data-python`, `emb-basics`, `comp-esp32`, `el-peripherals`, `comp-mavlink`.

```
C/C++ on MCUs: interrupts, timers, DMA   emb-basics                   1/1 -> 1
UART/I2C/SPI/CAN buses, peripherals      emb-protocols,el-peripherals 1/2 -> 0.5
Reading source code, building SITL       fw-reading,ap-sitl           0/2 -> 0
MAVLink: protocol and own component      mav-protocol,mav-component   0/2 -> 0
ESP32 as an onboard module               comp-esp32                   1/1 -> 1
Control loop and PID                     ctl-theory,bf-pid            1/2 -> 0.5
Signals and filters                      ctl-signals,bf-filters       2/2 -> 1
Failsafe and safe failure                ap-safety-fs,bf-failsafe     1/2 -> 0.5
Log analysis in Python                   data-python,ap-logs          1/2 -> 0.5
Config tests and CI                      eng-ci-configs               0/1 -> 0
N=10 full=3 partial=4 zero=3
binary coverage = 30 %
weighted coverage = 50 %
gaps: emb-protocols(3 h), fw-reading(4 h), ap-sitl(3 h), mav-protocol(4 h), mav-component(5 h), ctl-theory(4 h), ap-safety-fs(3 h), ap-logs(3 h), eng-ci-configs(3 h) total 32 h
weeks at 6 h/week = ceil(32/6) = 6
```

The example's result: strict coverage 30 %, weighted 50 %, gaps of 32 h by the program, which at 6 h per week is 6 weeks (without prerequisites: for `ap-safety-fs`, for example, those are `ap-lua` and `ap-missions`).

### Step 3. A portfolio plan of three pieces
For your role, choose three pieces from the "Course work → roles" table and for each one write down the five items of evidence from the portfolio standard (README with numbers, config, log with a plot, video, FMEA): which specific file each will be. For the embedded role example: `proj-esp32-component` (the firmware and its twin, a shared test suite, a SITL log with RFND, FMEA rows "UART loss → watchdog"), `proj-log-service` (three reports on your own logs, the discrepancies with a manual analysis), `proj-fleet-ci` (CI with a SITL failsafe test, the reference `.param`, the log as an artifact). On a separate line: a first open source contribution, following the steps from the theory section.

### Step 4. A certificate in your country
From the certificate table, write down the document you need for the work you want to do and the exact steps, with a link to the regulator's page and the date you checked it. If your country is not in the table, fill in the same template from `f-regulations`. An example for Czechia and work in A2: pilot registration at `dron.caa.gov.cz` → the A1/A3 test (40 questions, ≥ 75 %, 60 min) → self-practical training under A3 conditions and the declaration → the application and the A2 test through "Profil pilota" → valid for 5 years, renewal no earlier than 180 days before expiry.

Self-check: the lab is done when (1) the role has 8–12 skills, each tied to existing modules, and both percentages can be recomputed from the table by hand; for the worked example you get exactly 30 % and 50 %, gaps of 32 h and 6 weeks at 6 h per week; (2) the portfolio plan has three pieces, and for each all five kinds of evidence are named as specific files: config, log, README with the result in numbers, video, FMEA rows; (3) for your country, the document, the steps in order with a link to the official page, and the date of the check are written down; whatever is not on the official page (for example, a fee) is marked "not stated" rather than taken from a blog.

**Reference answer for self-check.** The correct calculation for the example: 3 skills rated 1, 4 rated 0.5, 3 rated 0 → 3/10 = 30 % and (3 + 2)/10 = 50 %. Common mistake #1: counting by modules instead of skills: 8 of 17 modules = 47 %; that makes the role look half covered, although only three skills are fully covered. Common mistake #2: counting a partial skill as whole: that gives 70 %, and the gaps in `ap-safety-fs`, `ctl-theory` and `ap-logs` disappear from the plan. Common mistake #3: including completed modules that are not on the role's list (`tools-overview`, `comp-mavlink`): coverage grows without any new skills. In the portfolio plan, the mistake is a piece without a log or a config: it cannot be reproduced, and the "Systems thinking" criterion is not met.

## diagnostics
- **Symptom:** I have a pilot certificate but no work
  - Possible cause: permission without a niche and without data-processing skill.
  - What to do: choose a niche (inspection, mapping, agriculture) and do one piece of work with measured accuracy: `proj-photogrammetry` (RMSE), `proj-inspection`.
- **Symptom:** the portfolio is screenshots and videos without files
  - Possible cause: there is no reproducible artifact.
  - What to do: give every piece a config, the original log and a README with the result in numbers; someone else must be able to reproduce the conclusion without you.
- **Symptom:** the issue was closed as "support", the PR hangs without a reply
  - Possible cause: a setup question in the bug tracker; a PR without reproduction steps and testing evidence; several changes in one PR.
  - What to do: questions go to Discord or the project forum; a bug report with steps and a log; one PR, one change, with a before/after plot from SITL.
- **Symptom:** role coverage is 80 %, yet the interview failed
  - Possible cause: the modules are completed, but there is no work of your own that you can explain with numbers.
  - What to do: following the question-type table, one piece of your own work for each type, with a number from your own log.
- **Symptom:** the certificate is "suddenly" invalid
  - Possible cause: it expired (5 years in the EU and the UK), or the FAA recurrent course was missed (24 calendar months).
  - What to do: put the expiry date in the operator's logbook; in Czechia renewal opens 180 days before expiry.
- **Symptom:** salary figures from different sources differ several times over
  - Possible cause: school and blog surveys, different roles under the same title.
  - What to do: use only official statistics with a year and a country (BLS, May 2025); if there are none, do not rely on the number.

## references
- EASA — FAQ: Training requirements in the 'open' category (validity 5 years, recognition in EASA countries, age; accessed 2026-11-22) | https://www.easa.europa.eu/en/the-agency/faqs/training-requirements-open-category | primary | A
- EASA — Easy Access Rules for UAS: UAS.OPEN.020/030/040 (online exam, A2, ≥ 75 %; accessed 2026-11-22) | https://www.easa.europa.eu/en/document-library/easy-access-rules/online-publications/easy-access-rules-unmanned-aircraft-systems?page=5 | primary | A
- EASA — Easy Access Rules for UAS: UAS.STS-01.020, STS-01/STS-02 (accessed 2026-11-22) | https://www.easa.europa.eu/en/document-library/easy-access-rules/online-publications/easy-access-rules-unmanned-aircraft-systems?page=8 | primary | A
- EASA — FAQ: training of remote pilots in the 'specific' category (STS, validity, renewal; accessed 2026-11-22) | https://www.easa.europa.eu/en/node/119286 | primary | A
- ÚCL — Registrace pilota bezpilotního systému (40 questions, 75 %, 60 min, age 16; published 2026-01-09) | https://www.caa.gov.cz/provoz/bezpilotni-letadla/pilot-bezpilotniho-systemu/registrace-pilota-bezpilotniho-systemu/ | primary | A
- ÚCL — Prodloužení platnosti kvalifikace A1/A3 a A2 (180 days; published 2026-01-09) | https://www.caa.gov.cz/provoz/bezpilotni-letadla/pilot-bezpilotniho-systemu/prodlouzeni-platnosti-kvalifikace-dalkove-ridiciho-pilota-a1-3-a-a2/ | primary | A
- ÚCL — Způsobilost pilotů pro provoz v podkategorii A2 (application through Profil pilota; published 2025-12-03) | https://www.caa.gov.cz/provoz/bezpilotni-letadla/otevrena-kategorie-open/zpusobilost-pilotu-pro-provoz-v-podkategorii-provozu-a2/ | primary | A
- ÚCL — Bezpilotní letadla (SORA 2.5 from 2026-06-01; accessed 2026-11-22) | https://www.caa.gov.cz/provoz/bezpilotni-letadla/ | primary | A
- UK CAA — Flyer IDs and operator IDs (free test, 5 years, £12.34 per year, 18+; accessed 2026-11-22) | https://www.caa.co.uk/drones/getting-started-with-drones-and-model-aircraft/flyer-ids-and-operator-ids/ | primary | A
- UK CAA — A2 Certificate of Competence (RAE(PC), ≥ 30 questions, 5 years; accessed 2026-11-22) | https://www.caa.co.uk/drones/remote-pilot-qualifications/a2-certificate-of-competence-a2-cofc/ | primary | A
- UK CAA — Remote pilot certificates and GVC (GVC until 31.12.2027; accessed 2026-11-22) | https://www.caa.co.uk/drones/remote-pilot-qualifications/level-1-2-3-and-4-remote-pilot-certificates-and-gvc/ | primary | A
- FAA — Become a Certificated Remote Pilot (updated 2026-06-09) | https://www.faa.gov/uas/commercial_operators/become_a_drone_pilot/ | primary | A
- FAA — FAQ: How much does it cost to get a remote pilot certificate (about $175) | https://faa.gov/faq/how-much-does-it-cost-get-remote-pilot-certificate | primary | A
- FAA — Dispensing Chemicals and Agricultural Products (Part 137) with UAS (updated 2026-10-28) | https://www.faa.gov/uas/advanced_operations/dispensing_chemicals | primary | A
- Penn State Extension — How to become an aerial drone pesticide applicator (state license; updated 2025-06-03) | https://extension.psu.edu/how-to-become-an-aerial-drone-pesticide-applicator | secondary | B
- Ministry of Defence of Ukraine — Basic qualification levels for UAV operators approved (2025-01-14) | https://mod.gov.ua/news/zatverdzheno-bazovi-kvalifikaczijni-rivni-operatoriv-bezpilotnih-litalnih-aparativ | primary | A
- Ministry of Defence of Ukraine — The Ministry of Defence has simplified the rules for using UAVs (2025-07-17) | https://mod.gov.ua/news/ministerstvo-oboroni-sprostilo-pravila-vikoristannya-bp-la | primary | A
- U.S. BLS — Occupational Outlook Handbook: Aerospace Engineers (median for May 2025) | https://www.bls.gov/ooh/architecture-and-engineering/aerospace-engineers.htm | primary | A
- U.S. BLS — Occupational Outlook Handbook: Aerospace Engineering and Operations Technologists and Technicians (May 2025) | https://www.bls.gov/ooh/architecture-and-engineering/aerospace-engineering-and-operations-technicians.htm | primary | A
- ISO 18436-7:2014 — Condition monitoring: qualification of personnel, Thermography (confirmed in 2025) | https://www.iso.org/standard/61417.html | primary | A
- ArduPilot — CONTRIBUTING.md (good first issue, bug reports) | https://raw.githubusercontent.com/ArduPilot/ardupilot/master/.github/CONTRIBUTING.md | primary | A
- ArduPilot — Submitting Patches Back to Master (dev docs source) | https://raw.githubusercontent.com/ArduPilot/ardupilot_wiki/master/dev/source/docs/submitting-patches-back-to-master.rst | primary | A
- ArduPilot — Wiki README (documentation edits, Resolves #N) | https://raw.githubusercontent.com/ArduPilot/ardupilot_wiki/master/README.md | primary | A
- ArduPilot — GSoC | https://ardupilot.org/dev/docs/gsoc.html | primary | A
- ArduPilot Discourse — Note on GSoC 2026 Results (130 applications, 3 slots; 2026-04-30) | https://discuss.ardupilot.org/t/note-on-gsoc-2026-results/143602 | primary | B
- PX4 — CONTRIBUTING.md (conventional commits, tests, AI policy) | https://raw.githubusercontent.com/PX4/PX4-Autopilot/main/CONTRIBUTING.md | primary | A
- PX4 — Contributing to Documentation | https://raw.githubusercontent.com/PX4/PX4-Autopilot/main/docs/en/contribute/docs.md | primary | A
- Betaflight — CONTRIBUTING.md | https://raw.githubusercontent.com/betaflight/betaflight/master/CONTRIBUTING.md | primary | A
- Betaflight — pull request template (make preview, betaflight/config) | https://raw.githubusercontent.com/betaflight/betaflight/master/.github/pull_request_template.md | primary | A
- INAV — Contributing (Testing Required, Review needed) | https://raw.githubusercontent.com/iNavFlight/inav/master/docs/development/Contributing.md | primary | A
- Skybrush — Skybrush is open source (2022-04-01) | https://skybrush.io/blog/2022-04-01-skybrush-is-open-source/ | secondary | B

## checklist
- The target role is chosen from the role map, with 8–12 skills tied to modules
- Strict and weighted coverage computed, the gaps and the weeks to close them written down
- Three portfolio pieces, each with a config, a log, a README with a number, a video, FMEA rows
- A certificate for your country: the document, the steps, a link to the regulator, the date of the check, the expiry date in the logbook
- A project for the first contribution is chosen, and its CONTRIBUTING has been read
