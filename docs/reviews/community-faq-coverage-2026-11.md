# Community FAQ coverage audit: what the English-speaking drone community asks (Nov 2023 – Nov 2026) and how the course answers

Date: 2026-11-17. Scope: 140 modules in `content/` (Russian), tracks from `data/curriculum.json`. Nothing in `content/` was edited.
The four firmware audits (`docs/reviews/{betaflight,inav,ardupilot,px4}-coverage-audit.md`, about 217 firmware questions) are
not repeated here. Where a community question is a firmware question already in an audit, the row points to the audit row
("BF audit #n", "AP audit §n") and only adds what is new.

**Version targets (owner decision, 2026-11-17):** Betaflight **2025.12** line (latest patch 2025.12.5; renames mapped from
4.5.3), ArduCopter/Plane **4.7.2**, PX4 **v1.17.0**, INAV **9.1.0**, ExpressLRS **4.1.0**. "Outdated" in this report means
outdated against these. Betaflight 2026.6 is mentioned only where the community visibly asks about a difference from 2025.12.
Where only older-version information is reliable, it is used and marked with its version.

---

## 1. Method and sources

### 1.1 Method

1. Read `content/README.md`, the track list in `data/curriculum.json`, and the headings plus "popular questions" sections
   of the four firmware audits.
2. Collected recurring questions from forum listings, topic rankings, search-engine results that quote forum and Reddit
   threads, guide sites and release threads (sources in 1.2). A question went on the list only if it showed up in at least
   two independent places, or in one ranked listing with high views.
3. Grouped 119 distinct questions into 16 themes. For each one: frequency evidence (source key, views/replies/votes where
   visible, years), a short answer checked against official docs or release notes for anything technical, and course
   coverage.
4. **I checked coverage by grepping `content/` (`.md` only) for the key terms in Russian and English and reading the
   matching section.** I did not judge from titles. Grep hits that came only from quiz JSON were not counted.
   ✓ = answered fully (module + section), ~ = partly (what is missing), ✗ = no usable answer.
5. Version drift: checked module `firmware:` headers and grepped for parameter names that were renamed or removed in the
   target versions (section 6).

### 1.2 Sources and evidence keys

| Key | Source | What was usable |
|---|---|---|
| **IF** | IntoFPV forum index, fetched 2026-11-17 | Thread/post counts per section: Beginner Questions 6,448 / 60,941; Tiny Whoops & Micro 1,895 / 23,746; Radio TX/RX 1,824 / 14,237; Mini Quads 1,220 / 15,786; Analog FPV 1,125 / 8,693; Flight Controller 1,106 / 8,817; Motor & Prop 983 / 7,136; DJI FPV 602 / 4,919; Long Range 590 / 9,259; Betaflight 586 / 4,394; LiPo & Charger 496 / 3,597; 3D printing 242; Action Cameras 231 / 1,982; iNav 187 / 967; Walksnail 142 / 2,959; Wings & Planes 134 / 1,365; HDZero 112; FPV Simulators 109 / 719; Large multirotors 80 / 2,158; OpenIPC 18 |
| **IF-BQ** | IntoFPV Beginner Questions, page 1 | "Some common questions new pilots ask" 117,903 views (2016 post, still the top thread); "Quad motors make unusual sound on the bench" 35,629; "From CC2500 to ELRS module change on RM Pocket" 6,289; "Is Rotorxpress legit?" 1,441; "Video signal issues on Meteor 65 Pro" 1,091; "Analog video works, but OSD is completely missing" 571; "When to replace LiPos after crashing?" 424; "Seeking motor recommendations and flight time for a 7-inch" 425; "Would a modified Meteor75 Pro II make a good first drone?" 393; "Goggle recommendations" 391; "First FPV drone (1S 18650)" 397; "DJI O4 Air Unit range" 386; "TBS Nano RX and Tango 2 binding issues" 391; "Help me restore GPS in INAV, how to arm without GPS lock" 362; "No stick movement in Betaflight" 273 |
| **IF-T** | Individual IntoFPV threads found through search | Flipping on takeoff (tid 18944, 28261, 13584, "quad is flipping and I'm at my wits end"); smoked ESC ("smoked my first ESC", tid 18448, 19365, 24725); soldering (tid 20582, 3258, 16002); analog vs digital (tid 22025, 26905, 22860, 27706); Remote ID ("Remote ID — RDQ vs FAA", 18+ pages; tid 28152, 21257); simulators (tid 22826, 29970, 28657, 24542); whoops 1S/2S (tid 25690, 24724, 22629, "Meteor 75 Pro vs Mobula 7"); first wing (tid 26576, 27544, 28355, "FPV wing for beginners"); long range (tid 27093, 25312, "7-inch long-range quad recommendations"); finding crashed drone ("finding crashed drone with GPS coords", tid 28844) |
| **IF-REL** | IntoFPV release threads | ExpressLRS 4.0.0 RC1–RC4 (Dec 2025), 4.0.0 final (Jan 2026), 4.0.1, 4.1.0 RC1 and final (19 Jul 2026), "ExpressLRS 4.x SPI support now merged into Betaflight"; Betaflight 2025.12.0 RC4 (Dec 2025), 2025.12.1 final (26 Dec 2025), 2026.6.1 final |
| **AP-Y** | discuss.ardupilot.org `top.json?period=yearly` (fetched 2026-11-17) | ArduDeck GCS 13,315 views / 301 replies; "How to Assess PID Quality" 6,691 / 175; "Another attempt at an ArduConfigurator" 5,734; ADOS Mission Control 5,242; "ESP32 S3 can't connect to Mission Planner" 4,831 / 178; Copter-4.7.0 released 4,577; 4.7.0-beta1 4,353; 4.7.1 released 3,652; "15in quad unstable in wind" 2,568 / 80; "Crash during AutoTune, 4.7.0-beta3" 2,389; "48-inch propeller X11 Max" 2,379; "Good GPS units?" 2,346 / 95; "Pixhawk 2.4.8 F330 log/build review" 2,305 / 82; "IMU choice for drone" 2,013; "New beta fly away" 1,833; "Serious terrain data error" 1,803; "The drone suddenly crashed" 1,739; "Clarifying battery failsafe behavior" 1,573 / 49; "SpeedyBee F405 V4 not reading ELRS" 1,555 / 43; "List of automated ArduPilot log analysis software" 1,630; "4+1 QuadPlane uncommanded roll on transition start" 1,268; "Flying antenna tracker (relay copter)" 1,219; "450 mm ESP32 quadcopter success" 1,039; "AI-assisted log diagnosis engine" 825; "How do AltHold and Loiter feel in 4.7 vs 4.6?" 920; "Mid flight disarm" 553. Older: "Bad AHRS all the time", "PreArm: Gyros inconsistent 4.5.x", "Unhealthy AHRS every time", "PreArm compass inconsistent" (found through search) |
| **PX4-Y** | discuss.px4.io top, yearly | Hobbywing CAN ESCs 1,149; "EKF2 giving wildly wrong z" 687; "Camera trigger stops at exactly 255 photos" 610; "Pitch/roll issues on X500 with Pixhawk 6X (v1.17)" 487; "Quad drifts randomly in Position Hold" 495; "MAVLink heartbeat timeout" 499; "PiX 2.4.8 & QGC please help" 481; "Gazebo integrated with PX4" 463; "Compass inconsistent and magnetometer error" 435; "Cube Orange+ not detecting CAN devices" 421; "Hardware selection for autonomous vehicles" 417; "Newbie: Pixhawk 6C and Tekko F4" 358; "PID tuning large drone" 327; "No bidirectional DShot on PX4" 320; "Flight termination: attitude failure, disarmed mid-air" 317; "Motors cut out mid-flight" 310; "R-XSR to Pixhawk 6C mini doesn't work" 298; "Here4 GPS severe dropout" 288; "Large velocity divergences with optical flow" 251 |
| **PX4-A** | discuss.px4.io top, all time | "Detected 0 radio channels, you need at least 5" 23,280 + 16,594 (two threads); "4G telemetry for Pixhawk" 20,906; "PX4 cable connect FlySky FS-iA6" 20,577; "Create custom model for SITL" 19,995; "How to add a ROS camera to IRIS for Gazebo" 19,342; "Pixhawk 4 ESC wiring setup" 17,112; "Avionics power low" 15,852; "Motor test command denied" 15,124; "Offboard takeoff/landing" 15,322; "Receiving custom MAVLink message in QGC" 10,118; "Compass inconsistent" 9,285; "Swarm flight using 100 drones" 8,731; "Talking to a PX4 FMU with a RPi via serial" 7,165; "About learning PX4 source code" 6,683; "Obstacle avoidance in PX4" 5,875; "Tailsitter duorotor feedback" 24,717 |
| **GH-ELRS** | github.com/ExpressLRS/ExpressLRS/discussions sorted by top | "ELRS telemetry on smartphone via Bluetooth" 21 votes; "MAVLink stream via WiFi on ELRS backpack" 16 votes / 72 comments; "Battery telemetry for PWM receivers" 9 / 18; "PPM output support" 7 / 13; "Make binding phrase editable via Lua" 7 / 13 (done in 4.1); "CRSF and PWM on same RX" 6 / 16 |
| **OL** | Oscar Liang | Beginner guide (updated Apr 2025: total cost US$400–1,800, radio first, 5–10+ h simulator, ELRS 2.4 GHz, avoid gamepads, acro over angle); "Don't ask AI FPV questions" (names flipping on takeoff, ELRS not binding, black goggle screen as the common troubleshooting asks); ExpressLRS 4 article (11 Feb 2026); Betaflight 2025.12 (4.6) and 2026.6 articles; LiPo disposal; finding a lost quad; best tiny whoop; long-range guide; wing launch/landing guide; DJI FPV FAQ; radio transmitter guide; soldering guide |
| **RD** | Reddit, **only through search-engine result titles** (reddit.com blocked, see 1.3) | r/fpv "Read this before posting: FAQ and wiki" (Jun 2024); r/fpv "Crashed on first flight" (Mar 2024); "When I try to take off my drone flips over" (cross-posted to r/diydrones, r/Quadcopter, r/multicopterbuilds, 2025); r/fpv "Analog or DJI for long range" (2025); r/drones "Analog or digital" (Apr 2025); r/drones "Remote ID" (2024); r/TinyWhoop "Best beginner tinywhoop setup" (Jan 2025); r/FPVplanes "Familiar with quadcopters, wanting to build a wing" and "Wing setup" (Jul 2024); r/ardupilot "Which version should I use" (Apr 2025); r/UAVmapping "WebODM" (2025); r/fpv "Who is the Bardwell of learning to actually pilot?" (2025) |
| **POLL** | Painless360 FPV poll, Aug 2025 (secondary summary on dronetrest.com, 15 Sep 2025) | More than a third of pilots HD-only for the first time; Walksnail the most popular single system; DJI still dominant; HDZero kept by racers; OpenIPC/Ruby growing. No sample size published in the summary |
| **REG** | Regulators and secondary summaries | FPV UK "Class marks and Remote ID" (UK changes from 1 Jan 2026); UAV Coach "Part 108 stuck" (16 Sep 2026); Unmanned Tech blog, DroneXL, DroneDJ, TechRadar on the FCC Covered List action DA 25-1086 (22 Dec 2025); EASA open-category pages; Pilot Institute homebuilt Remote ID (2022, used only as background) |
| **CAR** | Career and business sources | The Drone U "Drone pilot jobs guide 2026"; RotatePilot "Drone pilot salary 2026" and "Is a drone career worth it" (Mar 2026); DroneXL "Get paid to fly drones: 25 jobs" (30 Sep 2025); "Your Drone Questions Answered" ep. 132 "Is a Part 107 certificate really enough to build a career?" (Jan 2026); commercialdronepilots.com "Best way to start a career in drones"; UGA Extension (May 2025) and Unmanned Aerial (Sep 2026) on Part 137 spray licensing |
| **REL** | Release notes | Betaflight 2026.6 release notes (betaflight.com); ArduCopter `ReleaseNotes.txt` (master): 4.7.0 on 21 Jul 2026, 4.7.1 on 31 Aug 2026, 4.7.2 on 11 Oct 2026; Copter-4.7.0 release thread; INAV 9.0.0 and 9.1.0 release notes; PX4 1.18 release notes page (beta) |
| **JB** | Joshua Bardwell | No view counts could be retrieved. The only usable signal: he keeps a standing "Ultimate FPV Shopping List" (fpvknowitall.com) and links it from his Q&A livestreams (e.g. 28 Dec 2025). That shows how often "what should I buy" comes up |

### 1.3 What was blocked or unusable

- **reddit.com** (wiki pages of r/fpv and r/Multicopter, top-of-year listings): `SITE_BLOCKED`. One Reddit mirror fetch was
  refused by the permission classifier, so **no Reddit page was read**. Reddit evidence (RD) is post titles and dates as they
  appear in search results only. Vote and comment counts were not visible.
- **IntoFPV view-sorted listings and `archive/index.php` pages:** `robots_disallowed`. The section index and page 1 of
  Beginner Questions (default sort) worked.
- **GitHub Discussions for Betaflight and INAV:** rate-limited twice. ExpressLRS worked.
- **discuss.ardupilot.org HTML "top" page:** rendered empty (JavaScript). `top.json` worked. Per-category rankings were not
  pulled.
- **YouTube** (Bardwell, Painless360 view counts): no source reachable without scraping.
- **RCGroups:** search gave no ranked listings, so it was not fetched. RCGroups is not represented.
- **raw.githubusercontent.com, ArduPilot `Copter-4.7` branch release notes:** client error. The `master` copy worked.
- Search-engine results only, never fetched: DroneDJ/DroneXL articles (used for dates and headlines), most career sites.

**Limitation:** the frequency ranking comes from forum structure, view counts and how many independent sources repeat a
question. It is not a vote count. Reddit, by far the largest English venue, is visible only through titles.

---

## 2. Theme summary

| # | Theme | Questions | ✓ | ~ | ✗ |
|---|---|---|---|---|---|
| A | Getting started and buying | 11 | 1 | 3 | 7 |
| B | Builds and soldering | 10 | 6 | 4 | 0 |
| C | Radio links | 9 | 3 | 3 | 3 |
| D | Video | 7 | 2 | 4 | 1 |
| E | Betaflight tuning | 6 | 4 | 2 | 0 |
| F | Arming, failsafe and in-flight troubleshooting | 7 | 4 | 3 | 0 |
| G | ArduPilot / INAV / PX4 setup | 13 | 9 | 2 | 2 |
| H | GPS and navigation | 5 | 4 | 1 | 0 |
| I | Batteries and power | 8 | 5 | 2 | 1 |
| J | Fixed wing and VTOL | 6 | 2 | 2 | 2 |
| K | Long range | 4 | 3 | 1 | 0 |
| L | Regulation and Remote ID | 9 | 2 | 5 | 2 |
| M | Careers and business | 6 | 0 | 2 | 4 |
| N | Software, companion computers, AI | 9 | 8 | 0 | 1 |
| O | Mapping and applications | 4 | 2 | 2 | 0 |
| P | Safety and crashes | 5 | 2 | 3 | 0 |
| | **Total** | **119** | **57 (48 %)** | **39 (33 %)** | **23 (19 %)** |

The pattern is clear. The course answers **engineering and firmware** questions well (themes B, E–H, N: 41 of 58 ✓).
It is weakest on **how a newcomer enters the hobby or the industry**: what to buy, how to learn to fly, small quads,
recording footage, current rules outside the EU/US basics, and careers (themes A, L, M: 3 of 26 ✓). Those are also the
highest-traffic questions in every English venue sampled (IntoFPV Beginner Questions alone is 6,448 threads, more than
the next three sections combined).

---

## 3. Full question list

Columns: **Evidence** (source keys from 1.2, years). **Answer** (short, checked against the source named). **Course**
(✓/~/✗ with module and section, or what is missing).

### A. Getting started and buying

| # | Question | Evidence | Short answer | Course |
|---|---|---|---|---|
| A1 | What should I buy first, and what does it cost in total? | IF Beginner Q (6,448 threads); IF-BQ "Goggle recommendations"; OL beginner guide 2025; JB shopping list; RD r/fpv FAQ 2024 | Order: radio, then simulator, then goggles and a cheap durable quad, then batteries and charger. OL (2025): radio + sim US$100–300, goggles 100–500, drone 100–500, batteries/charger 100–500; total about US$400–1,800. Spend on the radio and goggles, which outlive several quads | ✗. `f-components-choice` sizes a 7"/10" airframe from requirements (payload, endurance, budget in €). It has no starter path and no pilot kit |
| A2 | Which simulator, and how many hours before flying for real? | IF Simulators 109 threads; IF-T tid 22826, 29970, "advice on starting out with no simulator"; OL | Liftoff or Tryp (gaming PC), Velocidrone (low-spec PC, racing), Uncrashed (freestyle). Use the real radio as a USB joystick (EdgeTX "USB Joystick (HID)"). OL: 5–10 h minimum, 10+ preferred, in acro, before the first real flight | ✗. `Liftoff` appears once, in `ap-setup-scratch`. SITL and Gazebo (`ap-sitl`, `tools-gazebo`) are engineering simulators, not pilot training |
| A3 | Which radio should I get (EdgeTX, form factor, internal ELRS, gimbals)? | IF Radio section 1,824 threads; OL radio guide; IF-BQ "CC2500 to ELRS module on RM Pocket" 6,289 views | An EdgeTX radio with internal ELRS 2.4 GHz (e.g. RadioMaster Pocket/Boxer/TX16S class), hall gimbals, a JR/nano bay if a 900 MHz or Crossfire module may follow, and a USB-C joystick mode for sims. Pick the form factor (gamepad vs full size) by how you hold the sticks (thumbs vs pinch) | ✗. EdgeTX appears only in passing (`link-elrs`, `link-protocols` telemetry discovery, `tools-overview` table). RadioMaster appears only in `comp-esp32` |
| A4 | Build or buy (RTF/BNF/PNP) for the first quad? | IF-BQ top FAQ thread (117,903 views, Q2); OL "Build or buy" | First quad: BNF (bind-and-fly with your own radio) of a whoop or 5". You still need soldering for repairs. RTF kits save money only if their goggles and radio are good enough to keep. Build the second one | ✗. Not discussed. `BNF/PNP/RTF` hits are unrelated |
| A5 | Which size class: whoop, 3", 5", 7", cinewhoop? | IF Tiny Whoops 1,895 threads, Mini Quads 1,220; OL "Types of FPV drone"; IF-BQ "Meteor75 Pro II as first drone?" | Whoop (65–75 mm, 1S/2S): indoor and backyard, nearly harmless. 3–3.5" (<250 g): parks, light rules. 5": freestyle standard. 7" and up: long range. Cinewhoop: ducted, close-proximity filming. Weight decides the rule category in many countries (250 g, 100 g in the UK) | ~ `f-components-choice` «Шаг 1: класс и рама» covers 5/7/10/15" by efficiency. No whoop, toothpick, 3.5" or cinewhoop (0 hits) |
| A6 | Analog or digital (DJI O4, Walksnail, HDZero, OpenIPC)? | IF section counts (Analog 1,125, DJI 602, Walksnail 142, HDZero 112, OpenIPC 18 threads); POLL Aug 2025; RD r/drones Apr 2025; IF-T 22025, 26905 | Analog: cheapest, constant low latency, graceful fade. HDZero: low, fixed latency, racing. DJI and Walksnail: best image and onboard recording, latency varies with mode, closed ecosystem. OpenIPC: open, DIY, MAVLink in the video link. Mid-2025 more than a third of pilots were HD-only (POLL) | ✓ `link-digital-video` «Четыре семейства», «Как выбирать». Missing: price per system and the cost of switching goggles later |
| A7 | Which goggles, and will my goggles work with the O4? | IF-BQ "Goggle recommendations"; IF DJI section; heliguy O4 compatibility page | DJI O4/O4 Pro work with Goggles 3 and N3 (FPV Remote Controller 3) and with Goggles 2 and Integra (RC 2). No third-party goggles. Analog goggles: box vs slim, IPD/focus range, receiver module bay. HDZero and Walksnail goggles each tie you to their ecosystem | ~ `bf-hd-osd-video` table names goggles only in the latency column. No compatibility matrix, no goggle-choice criteria |
| A8 | Is a DJI Avata 2 (or similar ready-made) a good way into FPV? | OL kits list (Avata 2); IF DJI section; DroneXL | Easy start, good image, built-in stabilization and "turtle"; but expensive repairs, closed firmware, limited acro feel, and US availability now uncertain (L7). Good for cinematic flying, poor for learning to repair | ✗. Avata is named only as a DJI product in `link-digital-video`/`bf-hd-osd-video` |
| A9 | Can I learn with a gamepad or keyboard? | OL ("avoid Xbox controllers and keyboards") | Sims accept them, but stick throw and gimbal centering differ. You must buy a radio anyway, so train on it from day one | ✗. Gamepads appear only as GCS joysticks for PX4 |
| A10 | Angle or acro, and how do I actually learn to fly? | OL «Avoid auto-level mode»; RD r/fpv "Who is the Bardwell of learning to actually pilot?" (2025); IF-T "crashed on first flight" | Learn acro in the sim: hover, then orbits, figure eights, then tricks. Low rates first (Actual: center 150–200 °/s, max 500–670 °/s), then raise. First real flights over grass with a spotter. Angle is a crutch: useful for line-of-sight checks and camera drones, not for FPV progression | ✗. No flight-skill content anywhere. `bf-rates-rc` covers rates as math, not as a training progression |
| A11 | Which flight controller should I buy for ArduPilot/PX4? Is a Pixhawk 2.4.8 clone OK? | AP-Y "Pixhawk 2.4.8 F330 build review" 2,305; PX4-Y "PiX 2.4.8 & QGC please help" 481, "Hardware selection for autonomous vehicles" 417, "Newbie: Pixhawk 6C and Tekko F4" 358 | 2.4.8 clones: F427 with the 1 MB flash erratum on many chips, cheap IMUs, poor connectors; they work for learning but are not a recommendation. Prefer H7 boards (Holybro Pixhawk 6C/6X, CUAV, Matek H743, SpeedyBee F405 only for simple builds). Check the ArduPilot "autopilot hardware options" list | ~ `ap-intro` explains flash limits (1 MB F405 has no Lua, H7 for complex platforms). No board shortlist and no clone warning (0 hits for "2.4.8") |

### B. Builds and soldering

| # | Question | Evidence | Short answer | Course |
|---|---|---|---|---|
| B1 | How do I solder XT60 and motor wires and tiny FC pads? | IF-T tid 20582, 3258, 16002; OL soldering guide | 60–80 W iron, chisel tip for power pads, fine tip for signal; 330–370 °C leaded, 370–400 °C lead-free; tin both sides, use flux, ≤3 s on small pads; shiny concave joint | ✓ `el-wiring` «Физика пайки», «Шаг 2. Силовая пайка» |
| B2 | Smoke on first battery connect / how not to fry the ESC | IF-T "smoked my first ESC", 18448, 19365, 24725 | Continuity test + to − before power; smoke stopper or fuse on first power-up; check for solder bridges and stray strands; then USB-only tests before the battery | ✓ `diag-troubleshooting` «Дерево 4»; `el-power-design` (smoke stopper, fuse, reverse polarity) |
| B3 | Do I need the capacitor on the ESC? | IF-T threads; OL build guides | Yes: low-ESR 470–1000 µF, 35 V for 4S, 50 V for 6S, short leads, on the ESC battery pads. It absorbs voltage spikes that kill ESCs and add gyro/video noise | ✓ `el-power-design` «пульсации и шипы» (same values) |
| B4 | Stack or AIO? 20×20 or 30.5? Which FC/ESC? | IF Flight Controller 1,106 threads; AP-Y "SpeedyBee F405 V4 not reading ELRS" 1,555 | AIO (FC+ESC on one board): light, cheap, for whoops and 3", but one burnt FET replaces everything. Stack: repairable, higher current, 5" and up. Size by frame mounting. F4 is enough for Betaflight; F7/H7 for INAV/ArduPilot with GPS, compass and logs | ~ `f-components-choice` «Шаг 3: ESC», «Шаг 5: FC» (4-in-1 vs separate, F4/F7/H7, UART count). AIO not mentioned (0 hits) |
| B5 | Motors make strange sounds or twitch on the bench | IF-BQ 35,629 views (2nd most-viewed beginner thread); BF audit #51 | Props off. ESC beeps = no signal (normal in CLI). Twitching at idle with DShot is normal. Grinding = bearing or debris. Stutter on spin-up = one phase open (bad solder) or desync | ~ `diag-troubleshooting` «Дерево 2» (stutter = phase). The normal-vs-faulty sounds are not listed |
| B6 | Why are my motors hot after a flight? | BF audit #9; IF-BQ FAQ Q13 | D-term noise (RPM filter off or wrong `motor_poles`), too-long motor screws touching windings, bent bell, overpropping | ✓ `bf-filters`, `bf-rpm-filter` (see BF audit #9) |
| B7 | Which props for my quad? | IF Motor & Prop 983 threads | Diameter by frame; pitch and blade count trade grip for current. Check motor thrust tables for current at full throttle vs ESC rating. Freestyle 5" usually 51xx tri-blades | ~ `f-aero-props` (operating point, thrust tables, g/W) answers it as engineering; no freestyle prop-feel guidance |
| B8 | Antenna connectors and polarization (SMA/RP-SMA, U.FL ripped, RHCP vs LHCP) | IF-BQ top FAQ Q11; IF Long Range "U.fl ripped off" | Connector gender and polarization must match at both ends. A mismatch costs about 20+ dB and looks like "range is terrible". Secure U.FL with glue or a holder | ✓ `rf-antennas` (polarization, connectors) |
| B9 | I powered the VTX without an antenna. Is it dead? | IF Analog section; OL | Possibly. Power amplifier overheats without a load within seconds at high power. Test at 25 mW with an antenna; always fit the antenna before power | ✓ `f-safety` checklist and diagnostics |
| B10 | Build order and minimum toolset for a first build | OL beginner guide §12; IF Tools; Unmanned Tech "build order" | Tools: iron, flux, multimeter, smoke stopper, hex drivers, prop tool, heat shrink. Order: ESC and power lead, capacitor, FC, receiver, VTX/camera; test each step with USB and smoke stopper | ~ `el-wiring` + `el-measure` cover the skills. There is no FPV build walk-through with a tool list (`bf-setup-scratch` starts from an assembled board) |

### C. Radio links

| # | Question | Evidence | Short answer | Course |
|---|---|---|---|---|
| C1 | How do I bind ELRS? | OL "Don't ask AI" (ELRS not binding is a top troubleshooting ask); IF Radio; BF audit #5 | Same binding phrase and same **major** version on TX and RX. Methods: phrase flashed or set via WebUI/Lua (Lua bind phrase on TX and RX since 4.1), `bind_rx` in Betaflight CLI, or 3× power-cycle into bind mode. Receiver LED: slow blink = no link, solid = linked | ~ `link-elrs` «Binding phrase» explains what the phrase is. No step-by-step bind procedure, no WebUI/ExpressLRS Configurator update flow |
| C2 | ELRS 4.x: do I have to update? Why won't my 3.x receiver bind? | IF-REL (4.0 RC1–4, final, 4.0.1, 4.1.0); OL ExpressLRS 4 (Feb 2026); discuss.ardupilot "ELRS 4.0 impacts on ArduPilot" | 4.x does not link with 3.x: update TX and RX together. STM32 hardware (FrSky R9, ImmersionRC Ghost, Happymodel PP) is dropped. Save `hardware.json` before updating; replace `elrsV3.lua` with `elrs.lua`. **SPI receivers built into whoop AIOs run on FC firmware:** Betaflight 2025.12 keeps them on ELRS 3; V4 SPI arrives only in Betaflight 2026.6 (`ELRSV4` build option). 4.1 (Jul 2026) works with any 4.x | ✗. `link-elrs` is "ELRS 3.x" (header and mode table) |
| C3 | Gemini, dual-band (LR1121), 2.4 vs 900 vs dual-band? | OL Gemini guide; OL ELRS 4; IF Radio | Gemini = two RF paths transmitting the same packet on two frequencies for diversity. In 4.x the antenna mode is chosen automatically and Gemini nearly doubles telemetry bandwidth. LR1121 receivers can run 900 MHz and 2.4 GHz modes, and dual-band combinations | ✗. 0 hits for Gemini and LR1121 |
| C4 | Which packet rate and telemetry ratio? | IF Radio; OL | Freestyle near: 250–500 Hz or F500. Long range: 150 Hz (2.4) or 100 Hz Full / 50 Hz (900). Telemetry 1:32–1:64 for long range | ✓ `link-elrs` «Packet rate», table, «Выбор режима под задачу» (3.x numbers, see section 6) |
| C5 | Receiver not detected / no stick movement in the configurator | IF-BQ "No stick movement in Betaflight"; AP-Y "SpeedyBee F405 V4 not reading ELRS" 1,555; BF audit #4 | UART with Serial RX, provider CRSF, TX↔RX crossed, ELRS major versions match. ArduPilot: `SERIALn_PROTOCOL = 23`, `RSSI_TYPE = 3` | ✓ `bf-ports`, `link-protocols`; ArduPilot RC in `ap-setup-scratch` |
| C6 | Crossfire/Tracer vs ELRS; Tango 2 binding | IF-BQ "TBS Nano RX and Tango 2 binding issues" 391 | Both speak CRSF to the FC, so the FC side is identical. TBS binds through Agent/Lua, not a phrase. ELRS is now the default for new builds; Crossfire 900 is still common on older long-range rigs | ~ `link-protocols` covers CRSF wiring and telemetry. TBS-specific binding and its trade-offs are absent |
| C7 | How far will my link go? LQ or RSSI? | IF Long Range 590 threads | Range from link budget; LQ tells packets arrive, RSSI tells the margin. Warn at 5–10 dB above sensitivity | ✓ `link-elrs` «LQ и RSSI»; `rf-link-budget` |
| C8 | Internal vs external module, swapping CC2500 for ELRS, JR/nano bay | IF-BQ 6,289 views | EdgeTX: Model → Internal RF / External RF; external modules need the bay and CRSF baud rate set (400k or higher for 500 Hz+). Turn the internal module off when using an external one | ✗ |
| C9 | Telemetry on my phone / MAVLink over the ELRS backpack to a GCS | GH-ELRS top two discussions (21 votes; 72 comments) | ELRS TX backpack can bridge MAVLink to Wi-Fi (UDP) for QGC/Mission Planner. Shares the RC link bandwidth, so set telemetry ratio high and expect low rates | ~ `link-elrs` (MAVLink since 3.5 shares bandwidth), `link-telemetry-radios`. The backpack Wi-Fi/BT bridge setup is not shown |

### D. Video

| # | Question | Evidence | Short answer | Course |
|---|---|---|---|---|
| D1 | Black goggle screen / no video | OL "Don't ask AI" (black goggle screen); IF-BQ "Video signal issues on Meteor 65 Pro" 1,091 | Analog: band and channel match, pit mode, VTX power, camera powered, PAL/NTSC. Digital: link/bind the air unit to the goggles, firmware versions match, air unit not in overheat protection, antenna on | ~ `link-vtx` «Алгоритм смены канала»; `diag-troubleshooting` «Дерево 5»; `bf-hd-osd-video` heat. No single "black screen" flow that covers digital pairing |
| D2 | No OSD in the goggles (analog or HD) | IF-BQ "Analog video works, but OSD is completely missing" 571; BF audit #11, #12 | HD: MSP DisplayPort UART, `osd_displayport_device = MSP`, `vcd_video_system = HD`, custom OSD on in goggles. Analog: MAX7456 present, PAL/NTSC match | ~ HD ✓ in `bf-hd-osd-video`; analog OSD troubleshooting is still thin (BF audit #12) |
| D3 | O4/O4 Pro range, power supply, overheating | IF-BQ "DJI O4 Air Unit range" 386; OL DJI FAQ | O4: 3.7–13.2 V from a BEC ≥ 10 W. O4 Pro: 7.4–26.4 V. Both throttle down on the ground and shut off when hot: use a fan on the bench | ✓ `bf-hd-osd-video` table and heat paragraph |
| D4 | Jello in the footage | BF audit #7 | Mechanical: props/motors balance, soft-mount the camera/FC, bent shafts. Filters do not fix it | ~ `bf-filters` «Чего фильтры не лечат»; `f-frame-mech` balance. No camera-mount specifics |
| D5 | Action camera on a quad: GoPro or naked GoPro, ND filters, Gyroflow/ReelSteady | IF Action Cameras 231 threads / 1,982 posts; OL §18 "Use a separate HD action camera" | Goggle DVR is not HD; carry a GoPro/Insta360 or a "naked" camera to save weight. ND filter for a natural shutter angle (shutter ≈ 1/(2 × fps)). Stabilize in post with Gyroflow using the camera gyro log (or Betaflight blackbox). The extra mass changes the tune | ✗. 0 hits for GoPro, Gyroflow, ND |
| D6 | Is my VTX power legal? Pit mode, 25 mW vs 1 W | IF Analog; IF-REL ELRS VTX Admin | Licence-free limits vary (EU 25 mW EIRP at 5.8 GHz). Higher power needs an amateur licence in the US (Part 97) and is not legal for unlicensed use in most of Europe | ✓ `f-regulations` «Радиочастоты»; `link-vtx` power and pit mode |
| D7 | Recording quality / where to record (goggle DVR vs air unit) | IF DJI section | Digital air units record onboard without radio loss; goggle DVR records what you saw, including breakups. Analog DVR in goggles is low quality | ~ `link-digital-video` «Запись на борту». No settings or file handling |

### E. Betaflight tuning (community view; parameter detail is in the BF audit)

| # | Question | Evidence | Short answer | Course |
|---|---|---|---|---|
| E1 | Presets or sliders? How do I start tuning without blackbox? | BF audit #24; OL "How to tune"; IF Betaflight 586 threads | Start from defaults or a preset that matches the frame; adjust master/PD-balance sliders by feel; `diff all` before and after; Blackbox only when the feel stops improving | ~ `bf-intro` table names Presets; `bf-pid` sliders. No "tune by feel" sequence for people without logs |
| E2 | Propwash on dives | BF audit #8 | D/D-max, I-term relax, dynamic idle, props, not only filters | ✓ `bf-pid`, `bf-pid-reg-in-bf` |
| E3 | What rates should I run? | BF audit #23 | Actual rates: center 150–250 °/s, max 600–850 °/s for freestyle, lower for cinematic | ✓ `bf-rates-rc` (formulas, types). A table of typical pilot rates by style would help |
| E4 | How do I read a blackbox log? | IF Betaflight; OL | Blackbox Explorer or PIDtoolbox: step response, noise spectrum, motor saturation | ✓ `bf-blackbox`, `bf-pid` |
| E5 | Oscillation on heavy 7–10" builds | IF Long Range; BF audit #10 | RPM filter with bidir DShot, lower D, TPA, frame resonance notch | ✓ `bf-rpm-filter` (10" case) |
| E6 | Should I upgrade from 4.5 to 2025.12, and what changes? | IF-REL 2025.12.0 RC4 and 2025.12.1 final (Dec 2025); OL 2025.12 article | Calendar versioning; Configurator becomes the web/PWA "Betaflight App" with matching version; OSD protocol (analog/HD) and magnetometer are explicit build options; full chip erase recommended; altitude hold, position hold, chirp generator added. Re-enter settings by section; don't paste a 4.5 diff blindly | ~ 2025.12 differences are marked in about 20 Betaflight modules (`bf-intro`, `bf-ports`, `bf-setup-scratch`, …), but there is no single 4.5.3 → 2025.12 migration checklist |

### F. Arming, failsafe and in-flight troubleshooting

| # | Question | Evidence | Short answer | Course |
|---|---|---|---|---|
| F1 | Why won't it arm (Betaflight)? | BF audit #1; OL arming guide | Read arming-disable flags (`status`, OSD, beeper) and fix the cause | ✓ `bf-arming-safety` |
| F2 | Flips on takeoff | OL "Don't ask AI"; RD cross-posted "drone flips over" (2025); IF-T 18944, 28261, 13584 | Motor order, motor direction, props on the wrong motors, wrong board orientation (`align_board_*`), wrong mixer | ✓ `diag-troubleshooting` «Дерево 2»; `bf-setup-scratch` |
| F3 | What happens on signal loss, and how do I test failsafe? | BF audit #6; IF Radio | Betaflight stages 1/2 and switch test; ArduPilot `FS_THR_ENABLE`; INAV RTH | ✓ `bf-failsafe`; `ap-safety-fs`; `inav-gps` |
| F4 | ArduPilot PreArm: "Bad AHRS", "Gyros inconsistent", "Compass not calibrated", "EKF variance" | AP threads ("Bad AHRS all the time", "Gyros inconsistent 4.5.x", "Unhealthy AHRS every time", "Compass inconsistent"); PX4 "Preflight fail and aircraft not ready" | Read the exact message. Wait for EKF to converge (3D fix, no movement); recalibrate accelerometers with the board at operating temperature; compass calibration away from metal, correct orientation; inconsistent IMUs = temperature or vibration or a faulty clone IMU | ~ `ap-setup-scratch` abort criteria name PreArm and EKF variance as "don't fly". No message-by-message table (see AP audit §5) |
| F5 | PX4 "Detected 0 radio channels" / ELRS or FlySky won't work on Pixhawk | PX4-A 23,280 + 16,594 + 20,577 views; PX4-Y "R-XSR to Pixhawk 6C mini" 298 | The RC IN port (IO processor) takes SBUS/DSM/PPM but not CRSF: wire ELRS to a UART (TELEM2/GPS2) and set `RC_PORT_CONFIG`. FS-iA6 needs PPM/iBus, not PWM | ✓ `px4-setup-scratch` (RC IN does not understand CRSF; UART; `RC_INPUT_PROTO`) |
| F6 | Motors cut out / disarmed in mid-air | PX4-Y "Motors cut out mid-flight" 310, "Flight termination due to attitude failure" 317; AP-Y "Mid flight disarm" 553, "The drone suddenly crashed" 1,739 | Pull the log first. Common causes: RC failsafe set to disarm/terminate, crash/attitude-failure detector (PX4 `FD_FAIL_P/R`, ArduPilot crash check), arm switch bumped, brownout (FC reboot), ESC desync | ~ `ap-safety-fs` failsafe table; `ap-logs` `ERR` codes. No "sudden disarm" decision tree across firmwares |
| F7 | Fly-away / toilet bowl in Loiter/Position | AP-Y "New beta fly away" 1,833; PX4-Y "Quad drifts randomly in Position Hold" 495; IF-T INAV "erratic behaviour in GPS modes" | Toilet bowl = compass error (interference, wrong orientation). Fly-away = GPS glitch or EKF lane switch. Recovery: switch to a non-GPS mode (Stabilize/AltHold/Angle) immediately; that switch must be on a known position | ~ `ap-setup-scratch` step 12 (toilet bowl → AltHold, compass); `est-sensors`; `inav-gps`. The recovery reflex is not trained or tested anywhere |

### G. ArduPilot / INAV / PX4 setup

| # | Question | Evidence | Short answer | Course |
|---|---|---|---|---|
| G1 | Betaflight, INAV, ArduPilot or PX4? | IF-T "ArduCopter to INAV, seeking a beginner-friendly setup"; RD r/ardupilot "Which version should I use" (Apr 2025) | Betaflight: freestyle/racing. INAV: GPS quads and wings on FPV hardware. ArduPilot: full autonomy, every vehicle type. PX4: research/ROS 2 and industry on Pixhawk | ✓ `ap-intro`, `inav-intro`, `px4-intro`, `content/pages/compare.html` |
| G2 | ArduPilot 4.7: should I upgrade, and what broke? | AP-Y Copter-4.7.0 released 4,577, 4.7.0-beta1 4,353, 4.7.1 released 3,652, "AltHold and Loiter in 4.7 vs 4.6" 920, "Crash during AutoTune 4.7.0-beta3" 2,389 | 4.7 renamed and rescaled many parameters to metres and degrees (`ANGLE_MAX` → `ATC_ANGLE_MAX`, `WPNAV_*` → `WP_*`, `CIRCLE_RADIUS` → `CIRCLE_RADIUS_M`, Land/PosHold/RTL/PILOT params to metres, `ARMING_CHECK` → `ARMING_SKIPCHK`, `SERIALn_OPTIONS` bits → `MAVn_OPTIONS`); auto-converted on upgrade; update QGC; download flash logs first (LittleFS boards erase them). 4.7.2 (11 Oct 2026) is current | ✗. Base is 4.6.3; only `ap-safety-fs` notes `RTL_ALT_M`. See section 6 |
| G3 | Mission Planner or QGroundControl? (and the new GCSs) | AP-Y ArduDeck 13,315, ArduConfigurator 5,734, ADOS 5,242; PX4-A "Most wanted QGC features" | Mission Planner: Windows, most ArduPilot setup screens. QGC: cross-platform, required for PX4. New open-source GCSs (ArduDeck, ADOS) are still maturing | ✓ `ap-intro`, `tools-overview`, `ap-setup-scratch`. New GCSs not mentioned (minor) |
| G4 | ArduPilot on an FPV F405 board (SpeedyBee etc.) | AP-Y SpeedyBee threads; discuss "SpeedyBee F405 Mini ESC passthrough troubles" | Works for basic copter/plane; 1 MB flash = no Lua scripting, limited features; ESC passthrough limitations; H7 for anything complex | ✓ `ap-intro` (flash/Lua), `ap-quadplane` (F405 limits) |
| G5 | Can I use an ESP32 as a flight controller? | AP-Y "ESP32 S3 can't connect to Mission Planner" 4,831 / 178, "450 mm ESP32 quadcopter success" 1,039; REL Betaflight 2026.6 (ESP32 target experimental) | ArduPilot has an ESP32 HAL port that people fly, but it is experimental and not a supported production target. Betaflight added ESP32 only in 2026.6, marked experimental. For learning, fine; for anything you care about, use an STM32 board | ✗. `comp-esp32` treats ESP32 only as a companion/peripheral |
| G6 | How do I judge whether my PID tune is good? AutoTune/QuikTune | AP-Y "How to Assess PID Quality" 6,691 / 175; PX4-Y "PID tuning large drone" 327 | Log `RATE` desired vs actual and step response; notch first, then AutoTune/QuikTune; check `MOT_THST_HOVER`, `ATC_ANG_*` | ✓ `ap-tuning`, `ap-setup-scratch` step 13 |
| G7 | Large (15"+, 12S–18S) multirotor unstable in wind, vibration | AP-Y 15" 2,568, 48" props 2,379, 2330 mm X13 1,056; PX4-Y "Large quad oscillates on takeoff" | Lower starting gains (Initial Parameters helper), `MOT_THST_EXPO` for the prop size, harmonic notch on ESC RPM, stiff arms, check `VIBE` and clipping | ✓ `ap-heavy`, `ap-tuning` |
| G8 | What exactly does ArduPilot's battery failsafe do? | AP-Y "Clarifying battery failsafe behavior" 1,573 / 49 | `BATT_LOW_VOLT`/`_MAH` → `BATT_FS_LOW_ACT`, critical → `BATT_FS_CRT_ACT`; voltage uses `BATT_LOW_TIMER` and is sag-compensated if `BATT_FS_VOLTSRC = 1` | ✓ `ap-safety-fs` failsafe table |
| G9 | INAV: how do I arm without a GPS lock? | IF-BQ 362 views | Navigation modes block arming without fix; `nav_extra_arming_safety` can allow it, with known risk | ✓ `inav-intro` |
| G10 | CAN ESCs / DroneCAN device not detected | PX4-Y Hobbywing CAN ESCs 1,149, "Cube Orange+ not detecting CAN" 421 | Enable the CAN driver and protocol (`CAN_P1_DRIVER`, `CAN_D1_PROTOCOL`; PX4 `UAVCAN_ENABLE`), termination, node IDs, bitrate | ✓ `el-dronecan` |
| G11 | Which log-analysis tools should I use? | AP-Y "List of automated log analysis software" 1,630; PX4-Y web .ulg analyzer 332 | ArduPilot: UAV Log Viewer, MAVExplorer, Mission Planner; PX4: Flight Review, PlotJuggler; Python (pymavlink, pyulog) | ✓ `ap-logs`, `data-python`, `tools-overview` |
| G12 | INAV 8 → 9.x: what do I need to redo? | REL INAV 9.0.0 and 9.1.0 notes; forum.wearefpv.fr INAV 9.0.1 thread | Full chip erase required; load the old `diff all`, fix settings flagged red; 9.1 renames profile commands to `control_profile`, removes `servo_autotrim_iterm_rate_limit`, tunes GNSS rate per M8/M9/M10, adds magless heading set to north before takeoff | ~ `inav-setup-scratch` header lists 9.1 default differences (Galileo/BeiDou on, `gps_ublox_nav_hz` 8, `inav_w_z_*`). The other INAV modules are "verified with 8.0.1"; no migration procedure |
| G13 | PX4 1.15 → 1.16/1.17: what changed? | PX4-Y "Pitch/roll issues on X500 with Pixhawk 6X (v1.17)" 487; "On v1.16 or older your u-blox likely runs dynamic model 6" 166 | 1.16 removed `COM_OBS_AVOID`, per-mode `RC_MAP_*_SW`, legacy `BAT_V_*`; added `DSHOT_BIDIR_EN`. 1.17 changed `MC_ROLL_P`/`MC_PITCH_P` 6.5 → 4.0, `IMU_DGYRO_CUTOFF` 30 → 20, `RCn_DZ` → `MAN_DEADZONE`; ROS 2 topics gain `_vN` suffixes (from PX4 audit §1.4) | ~ PX4 modules say 1.14+/1.15; the PX4 audit lists the deltas but the modules do not |

### H. GPS and navigation

| # | Question | Evidence | Short answer | Course |
|---|---|---|---|---|
| H1 | Which GPS module (M10 or M8, with or without compass)? | AP-Y "Good GPS units?" 2,346 / 95; PX4-Y "Here4 GPS severe dropout" 288 | M10 for new builds (four constellations, lower power); with a compass for INAV/ArduPilot/PX4, on a mast away from VTX and power wires | ✓ `bf-gps-setup` «Модуль: M8 или M10»; `est-gnss` |
| H2 | GPS takes ages to get a fix / few satellites | BF audit #17 | `gps_auto_config`, Galileo on, SBAS, clear sky, distance from VTX/camera noise | ✓ `bf-gps-setup` (VTX on/off test, cold start) |
| H3 | Compass calibration and interference ("compass inconsistent") | PX4-A "Compass inconsistent" 9,285; PX4-Y 435; AP threads | Mount away from current-carrying wires; calibrate outdoors; check orientation; `COMPASS_MOT` / compassmot for current interference; large vehicles: MagFit from a flight log | ~ `est-sensors` (orientation, metal), `el-emi`. MagFit 0 hits; compassmot only named (see AP audit §3.7) |
| H4 | Does GPS Rescue/position hold work without a compass? | BF audit #16; OL 2025.12 and 2026.6 articles | Betaflight 2025.12: GPS Rescue and position hold work without a magnetometer (heading from GPS course after forward flight). 2026.6 adds `trust_mag` (default OFF) | ✓ `bf-failsafe`, `bf-gps-setup` (4.5 with 2025.12 marks) |
| H5 | Position hold indoors with optical flow | PX4-Y "Large velocity divergences with optical flow" 251 | Flow + rangefinder; tune flow scale; requires texture and light; EKF settings per firmware | ✓ `est-alt-sources`, `nav-indoor` |

### I. Batteries and power

| # | Question | Evidence | Short answer | Course |
|---|---|---|---|---|
| I1 | Storage voltage; when to retire a pack after a crash | IF-BQ "When to replace LiPos after crashing?" 424; IF LiPo 496 threads | Storage 3.8 V/cell; retire if puffed, dented, cell drift > 0.05 V after rest, IR rising; after a hard crash, isolate and watch for an hour before charging | ✓ `f-power` «Безопасная работа с LiPo»; `ops-maintenance` |
| I2 | How do I dispose of a dead LiPo? Salt water? | OL "Dispose LiPo safely" | Discharge to ~0 V with a resistor/bulb discharger, verify with a multimeter, cut and isolate leads, take to battery recycling. OL calls salt water "slow and ineffective" (corrodes terminals, stops discharging) | ~ **Outdated:** `f-power` «Заряд, хранение, утилизация» says "разряд в солёной воде" |
| I3 | Li-Ion or LiPo for long range? | IF-BQ "First FPV drone (1S 18650)"; IF Long Range | Li-Ion for low steady current (cruise), LiPo for high current. Li-Ion sags under freestyle loads | ✓ `f-power` «LiPo против Li-Ion» |
| I4 | Which charger? Is parallel charging safe? | IF LiPo section | AC/DC balance charger with enough watts; parallel board only for packs of the same cell count and similar voltage (±0.1 V/cell), fuse-protected board | ~ `f-power` charging current only; parallel charging mentioned once in `f-electricity-101` |
| I5 | How long will it fly? (7" motors, flight time) | IF-BQ 425 views | From average current and usable capacity (80 %); calculator | ✓ `f-components-choice` calculator, `f-power` «Время полёта» |
| I6 | Battery voltage wrong / wrong cell count | BF audit #21, #22 | `vbat_scale`, `ibata_scale`; `force_battery_cell_count` | ✓ `bf-setup-scratch` |
| I7 | Whoop batteries: 1S or 2S, BT2.0 vs PH2.0, HV | IF Tiny Whoops 1,895 threads; IF-T "Meteor 75 Pro vs Mobula 7", "Mobula 7 ELRS 1S batteries"; RD r/TinyWhoop Jan 2025; OL best tiny whoop | 1S 65–75 mm for indoor; 2S for outdoor punch. BT2.0 connectors carry more current than PH2.0 (less sag). LiHV 4.35 V packs; replace often, they are consumables | ✗. 0 hits for whoop |
| I8 | LiPo fire; flying in cold weather | IF LiPo; OL | Charge on a non-flammable surface, LiPo bag/ammo box, sand; let it burn out outdoors. Warm packs to 20–30 °C in cold | ✓ `f-safety` «При пожаре АКБ»; `f-power` (cold); `ops-weather` |

### J. Fixed wing and VTOL

| # | Question | Evidence | Short answer | Course |
|---|---|---|---|---|
| J1 | Which first FPV wing, INAV or ArduPilot? | IF Wings 134; IF-T 26576, 28355, "FPV wing for beginners"; RD r/FPVplanes (Jul 2024); Unmanned Tech wing guide | A foam flying wing (e.g. 900–1,100 mm EPP/EPO) or a high-wing pusher trainer; INAV for simplicity on FPV hardware, ArduPlane for missions and logging | ~ `inav-setup-wing`, `aero-wing` cover setup. Airframe choice and build are not covered |
| J2 | How do I launch and land a wing? | OL "How to launch and land an FPV wing" | Hand launch at full throttle, slight nose up, firm throw; or auto-launch (INAV `nav_fw_launch_*`, ArduPlane TKOFF). Land into wind, long shallow glide, cut throttle in the flare | ~ `inav-setup-wing` (auto-launch), `ap-plane-tuning` (landing). No hand-throw technique for first-timers |
| J3 | Where should the CG be? | IF Wings; OL | 15–25 % MAC for most wings (check the maker). Nose-heavy flies, tail-heavy crashes | ✓ `aero-stability`; `inav-setup-wing` (15–20 % MAC) |
| J4 | QuadPlane transition problems | AP-Y "4+1 QuadPlane uncommanded roll on transition start" 1,268 | Check `Q_TRANSITION_MS`, airspeed, tilt servo directions, `Q_ASSIST_SPEED` | ✓ `ap-quadplane` |
| J5 | Tailsitter vs tilt-rotor vs 4+1: which VTOL type? | PX4-A "Tailsitter duorotor feedback" 24,717, "VTOL tailsitter pointers" 4,211 | 4+1: simplest and most forgiving, drag penalty. Tilt-rotor: efficient, mechanically complex. Tailsitter: lightest, hardest to tune and land in wind | ✗. 0 hits for tailsitter. `ap-quadplane` covers 4+1 and tilt-rotor only |
| J6 | Do I need an airspeed sensor? | AP/INAV/PX4 audits (airspeed setup: No in all three) | Strongly recommended for VTOL transitions and TECS on planes; synthetic airspeed is possible. Pitot placement, calibration `ARSPD_*` | ✗. Setup absent (see AP audit §6i, INAV §6.8, PX4 §6h) |

### K. Long range

| # | Question | Evidence | Short answer | Course |
|---|---|---|---|---|
| K1 | How do I set up my first long-range 7"? | IF Long Range 590 threads / 9,259 posts; IF-T "7-inch long-range quad recommendations", 27093; OL long-range guide; Unmanned Tech LR guide (2026) | Efficient 7" frame and motors, Li-Ion or large LiPo, GPS with tested GPS Rescue, ELRS at a long-range packet rate with RSSI warnings, return before half battery | ✓ `link-elrs` «Разобранный пример: настройка для 7" long range»; `bf-gps-setup`; `bf-failsafe`; `f-components-choice` (7" example) |
| K2 | Analog or DJI for long range? | RD r/fpv "Analog or DJI for long range" (2025) | DJI/Walksnail have longer range and record clean video but freeze at the edge; analog degrades gracefully | ✓ `link-digital-video` «Деградация», «Как выбирать» |
| K3 | Ground antennas, patch vs omni, antenna trackers, relays | AP-Y "Flying antenna tracker (relay copter)" 1,219 | Directional patch/helical on the ground for range; tracker when beyond the beamwidth; relays are BVLOS by definition (rules) | ~ `rf-antennas` covers patterns and gain. Trackers and relays not covered |
| K4 | How do I plan battery for the return, with wind? | IF Long Range; OL | Turn back at 50 % or earlier, more with headwind on return; check wind aloft | ✓ `ops-weather`; `f-power` |

### L. Regulation and Remote ID

| # | Question | Evidence | Short answer (check your regulator; not legal advice) | Course |
|---|---|---|---|---|
| L1 | Does my FPV quad need Remote ID in the US? | RD r/drones "Remote ID" (2024); IF-T "Remote ID — RDQ vs FAA" (18+ pages), tid 28152; REG | Part 89: Standard RID aircraft, or a broadcast module, or fly only at a FRIA. Recreational aircraft under 250 g are not registered and do not need RID; Part 107 aircraft need RID at any weight. Enforcement from 16 Mar 2024 | ~ `f-remote-id-security` «Кому и когда обязательно» has Part 89, module, FRIA in one sentence. Missing: the sub-250 g recreational exemption, the "registered aircraft = RID" logic, standalone modules for FPV builds |
| L2 | Do I need Part 107 to post videos on YouTube? TRUST? | CAR (YDQA ep. 132, Jan 2026); REG | Recreational = TRUST + registration from 250 g + community-based safety guidelines. Flying for compensation or in furtherance of a business (including monetized content) = Part 107 | ~ `f-regulations` FAA paragraph (Part 107, TRUST, LAANC). The monetized-content line and the CBO guideline requirement are missing |
| L3 | Can I legally fly with goggles on alone? | IF; OL safety rules | US: VLOS must be kept by the pilot or a co-located visual observer, so FPV needs a VO. EU open category: FPV is allowed with a UA observer next to the pilot. UK: similar observer requirement. Check national rules | ~ `f-regulations` template row "VLOS, нужен ли наблюдатель"; `ops-field` defines the observer role. The legal rule for FPV is not stated |
| L4 | What changed in the UK in 2026? | REG FPV UK; CAA news; DroneXL "UK registration 100 grams" (Oct 2025) | From 1 Jan 2026: Flyer ID required above 100 g; UK class marks UK0–UK6 on new products (A1 now up to 900 g with UK0/UK1); Remote ID mandatory for UK1–UK3, UK5, UK6 from 2026, and for UK0, UK4, legacy and privately built aircraft of 100 g+ with a camera from 1 Jan 2028; C-marks accepted until 31 Dec 2027 | ✗ |
| L5 | EU: can I fly a homebuilt FPV quad in the open category? | REG EASA open category | Yes: privately built aircraft below 250 g in A1, otherwise A3 (far from people) up to 25 kg; operator registration from 250 g or with a camera; A1/A3 online test, A2 CofC for A2 | ✓ `f-regulations` «Как устроены две эталонные системы» (EASA paragraph and the 7" worked example) |
| L6 | How do I get BVLOS approval? What is Part 108? | REG UAV Coach (16 Sep 2026); DLA Piper (Oct 2025) | US: Part 107 waivers today. Part 108 NPRM published 7 Aug 2025; the final rule has been under OIRA review since 10 Jul 2026, no publication date yet. EU: specific category with SORA or a standard scenario/PDRA | ~ `f-regulations` (BVLOS = waiver/SORA). Part 108 absent |
| L7 | Can I still buy DJI and Chinese FPV parts in the US? (FCC Covered List) | REG DroneXL, DroneDJ (22 Dec 2025), Unmanned Tech blog, DroneLife (27 Dec 2025), iClarified (12 Feb 2026) | FCC action DA 25-1086 (22 Dec 2025) added foreign-made UAS and critical components (flight controllers, radios, cameras, motors, batteries) to the Covered List: no new FCC authorizations. Devices already authorized and owned stay legal to fly. Supply of new products is shrinking | ✗ |
| L8 | VTX power and ham licence for 5.8 GHz | IF Analog; IF-REL | See D6 | ✓ `f-regulations` «Радиочастоты» |
| L9 | Do I need insurance? (AMA, FPV UK, BMFA) | OL safety rules; REG FPV UK | Mandatory for some operations in the EU/UK, recommended everywhere; club membership (AMA, FPV UK, BMFA) often includes liability cover | ~ `f-regulations` mentions insurance generically; clubs not named |

### M. Careers and business

| # | Question | Evidence | Short answer | Course |
|---|---|---|---|---|
| M1 | Is a drone pilot career worth it? What does it pay? | CAR (RotatePilot salary 2026 and "worth it" Mar 2026; The Drone U 2026; DroneXL 25 jobs Sep 2025; YDQA ep. 132) | Part 107 alone rarely makes a career: pay depends on a niche (inspection, survey, film, agriculture, public safety) and on industry skills (GIS, thermography, data processing). Many roles are part-time or project-based | ✗ |
| M2 | How do I become a drone engineer or developer? | CAR (commercialdronepilots "best way to start a career"); PX4-A "About learning PX4 source code" 6,683; AP GSoC posts | Embedded C/C++, control and estimation, Python, ROS 2; contribute to ArduPilot/PX4 (issues, docs, GSoC); show a portfolio of real builds with logs | ~ The course itself is this path (`fw-reading`, `eng-*`, capstone). No explicit career mapping: roles, which modules prove which skill, how to present a portfolio |
| M3 | How do I start a drone services business? | CAR | Pick a niche, insurance, Part 107 / national licence, data-processing skill, pricing per deliverable, not per flight hour | ✗ |
| M4 | Agricultural spraying: what licences? | CAR (UGA Extension May 2025; Unmanned Aerial Sep 2026; beancount Oct 2026) | US: Part 107 + Part 137 agricultural aircraft operator certificate + exemption for aircraft over 55 lb + state pesticide applicator licence | ✗. 0 hits for spraying/agriculture |
| M5 | Other niches: delivery, light shows, inspection | CAR (DroneXL 25 jobs) | Light shows (Skybrush is open source, ArduPilot-based); delivery is BVLOS-dependent (L6); inspection needs thermal/LiDAR skills | ✗. Delivery only in case studies (`ops-case-studies`) |
| M6 | Which certificates beyond the basic licence? | CAR; REG | A2 CofC / UK GVC, thermography (Level 1), Part 137, SORA operator training | ~ `f-regulations` (A2 exam only) |

### N. Software, companion computers, AI

| # | Question | Evidence | Short answer | Course |
|---|---|---|---|---|
| N1 | Raspberry Pi or Jetson? How do I connect it to the FC? | PX4-A "Talking to a PX4 FMU with a RPi via serial" 7,165; PX4-Y "Hardware selection for autonomous vehicles" 417; AP companion threads | Pi for MAVLink routing and light vision; Jetson for neural networks. UART to TELEM with matching `SERIALn_PROTOCOL`/`MAV_n_CONFIG`, common ground, separate BEC | ✓ `comp-raspberry`, `comp-jetson-nano`, `ap-companion` |
| N2 | Object detection / follow-me with YOLO | AP GSoC24 "Visual follow-me using AI"; PX4 "Drone computer vision project (need help)" | Detect on companion, track, convert to velocity/position setpoints in GUIDED/Offboard, geofence | ✓ `per-cv`, `per-tracking`, `per-vision-pipeline` |
| N3 | ROS 2 with PX4/ArduPilot | PX4-Y "PX4 + uXRCE + zenoh_bridge_ros2dds" 576 | PX4: uXRCE-DDS agent; ArduPilot: native DDS; versioned topics in PX4 1.16+ | ✓ `ros2-px4`, `ros2-ardupilot` (check topic names against 1.17, see G13) |
| N4 | Gazebo / custom model in SITL / camera in Gazebo | PX4-A 19,995 and 19,342; PX4-Y 463 | Gazebo (gz) worlds and models; camera sensor bridged to ROS 2 | ✓ `tools-gazebo`, `ap-sitl` |
| N5 | Obstacle avoidance | PX4-A 5,875 | PX4 1.16 removed the old obstacle-avoidance interface (`COM_OBS_AVOID`); ArduPilot 4.7 removed lean-angle ("ping-pong") avoidance from standard builds (custom build server); proximity-based avoidance (BendyRuler, simple avoidance) remains | ✓ `per-depth-avoid` (check against these removals, section 6) |
| N6 | 4G/LTE telemetry | PX4-A 20,906 | Companion or LTE modem with MAVLink router / VPN; latency and failsafe on link loss | ✓ `link-telemetry-radios`, `mav-routing` |
| N7 | Multi-vehicle / swarms | PX4-A 8,731, 9,981 | Unique `SYSID`, routing, supervisor | ✓ `mav-multi-vehicle` |
| N8 | Custom MAVLink message in QGC | PX4-A 10,118 | Dialect XML, regenerate, both ends | ✓ `mav-component`, `mav-protocol` |
| N9 | Can I use ChatGPT/AI to tune or read logs? | OL "Don't ask AI FPV questions"; AP-Y "AI-assisted log diagnosis engine" 825, "A tool that tells you which PID to change, and my AI agent reads it" 743; "List of issues with the Chris Rosser guides" | Useful for starting checklists; unreliable on version-specific parameters (mixes versions) and on blackbox interpretation; never paste AI parameter lists without checking names against your firmware version | ✗ |

### O. Mapping and applications

| # | Question | Evidence | Short answer | Course |
|---|---|---|---|---|
| O1 | WebODM, Pix4D or DroneDeploy? GSD and overlap settings | RD r/UAVmapping "WebODM" (2025); mavicpilots "Consensus on mapping software"; DroneDeploy forum "Software for starters" | WebODM/ODM: free, local, good enough; Pix4D/Metashape: accuracy and support; DroneDeploy: cloud, easy. 75–80 % front, 65–70 % side overlap | ✓ `per-mapping` (GSD formula, overlap, ODM, GCP). Commercial tools are not compared (minor) |
| O2 | Camera trigger / geotagging (PX4 "stops at 255 photos") | PX4-Y 610 views | ArduPilot `CAM1_*`, `DO_SET_CAM_TRIGG_DIST`, geotag from `CAM`/`TRIG` log; PX4 `TRIG_*`, camera capture feedback | ~ `per-mapping` (ArduPilot). PX4 trigger absent (PX4 audit §6o) |
| O3 | Do I need RTK/PPK or ground control points? | IF; mapping forums | GCPs or PPK for absolute accuracy at cm level; RTK for real-time positioning | ✓ `nav-rtk`, `per-mapping` |
| O4 | Thermal / inspection payloads | CAR | Radiometric thermal camera, gimbal control, thermography training | ~ `payload-gimbal` covers gimbals; thermal sensing absent |

### P. Safety and crashes

| # | Question | Evidence | Short answer | Course |
|---|---|---|---|---|
| P1 | How do I find a crashed or lost drone? | OL "Find downed and lost FPV drone"; IF-T "Finding crashed drone with GPS coords", tid 28844; Unmanned Tech buzzer guide | Standalone self-powered buzzer, DShot beacon on RX loss, GPS coordinates in the radio telemetry (EdgeTX logs last position) and OSD, DVR review, search in the direction of the last frame | ~ `bf-led-buzzer` (beeper, DShot beacon), `bf-gps-setup` (telemetry). No consolidated "lost model" procedure (last coordinates from EdgeTX telemetry log, search pattern) |
| P2 | Turtle mode after a crash | BF audit #18 | DShot, FLIP OVER AFTER CRASH mode, flip switch then arm | ✓ `bf-features-tour` |
| P3 | What to check after a crash | IF Mini Quads; OL | Bent motor shafts/bells (spin by hand), cracked arms, props, antenna and U.FL connectors, XT60 lead, battery puffing, FC soft mounts | ~ `ops-maintenance` (logbooks, regulations); `f-frame-mech` inspection. No post-crash checklist (0 hits for bent shaft) |
| P4 | Bench safety (props off, accidental arm) | OL; BF audit #40 | Props off for any configuration, arm on a switch, prearm, beeper on arm | ✓ `f-safety` «Правила на столе»; `bf-arming-safety` |
| P5 | Where am I allowed to fly? Which app? | OL safety rules; REG | US: B4UFLY-approved apps (e.g. Aloft), LAANC; UK: Drone Assist/Altitude Angel maps; EU: national geo-zone portals | ~ `f-regulations` «Шаг 2. Карта зон» (generic, no named services) |

---

## 4. Top 25 gaps, ranked by frequency × importance

Score: frequency (F, 1–5, from section 1 evidence) × importance (I, 1–5: safety, money, legality, or blocks progress).
Proposals give a new module id with a Russian title, or an existing module and section. New modules also need
`data/curriculum.json`, `data/content-manifest.json`, `data/glossary.json` and a quiz (per `content/README.md`).

| Rank | Gap (questions) | F × I | Proposal |
|---|---|---|---|
| 1 | Learning to fly: simulator, acro progression, first real flights (A2, A9, A10) | 5 × 5 | **New `ops-pilot-training` «Как научиться летать: симулятор, акро и первые сто батарей»** (track Оператор, before `bf-intro`): sim choice, radio as USB joystick, rate presets for training, skill ladder with measurable targets (hover box, orbits, figure eight, line-of-sight), first-field-day protocol with spotter, logbook of hours |
| 2 | ExpressLRS 4.x migration, Gemini, LR1121 (C2, C3, C1) | 5 × 5 | **Rewrite `link-elrs` to 4.1**: header, mode table re-checked against 4.x docs; new section «Переход 3.x → 4.x» (incompatibility, dropped STM32 hardware, `hardware.json` backup, `elrs.lua`, arm-channel option, EdgeTX ≥ 2.11); new section «Gemini и двухдиапазонные приёмники»; new practice step «Привязка: фраза, Lua, `bind_rx`, режим привязки». **Flag the SPI-receiver conflict** (Betaflight 2025.12 SPI = ELRS 3) |
| 3 | First kit, budget, radio choice, BNF vs build (A1, A3, A4, A8) | 5 × 4 | **New `f-starter-kit` «Первый комплект: пульт, очки, аппарат и бюджет»** (Фундамент, L1): decision table by goal and budget, what outlives what, BNF vs build, ready-made DJI vs open hardware, compatibility traps (ELRS versions, goggles ↔ air unit) |
| 4 | ArduPilot 4.7 parameter renames (G2) | 4 × 5 | **`ap-intro` new section «ArduPilot 4.7: переименованные параметры и единицы»** + update every file listed in section 6.2; `ap-setup-scratch` re-verified on Copter-4.7.2 SITL |
| 5 | Regulation update: UK 2026, FCC Covered List, FPV observer rule, US sub-250 g, Part 108 (L1–L4, L6, L7) | 4 × 5 | **`f-regulations`: new subsection «Великобритания с 2026 года»**, FAA paragraph extended (sub-250 g recreational, monetized content = Part 107, VO for FPV, Part 108 status with a check-by date), **new «Рынок и оборудование: FCC Covered List (США, 2025)»**; `f-remote-id-security` «Кому и когда обязательно» rewritten as a three-jurisdiction table (US/EU/UK) with dates |
| 6 | Whoops and micro classes (A5, I7, B4) | 5 × 3 | **New `f-micro-whoop` «Вупы и микро: 1S/2S, AIO, SPI-приёмники и разъёмы»**: class table (65/75 mm, toothpick, 3.5" sub-250), AIO boards, BT2.0/PH2.0 and HV packs, SPI receivers and the ELRS-version trap, indoor safety |
| 7 | Recording footage: action camera, ND, Gyroflow, DVR (D5, D7) | 4 × 3 | **New `per-fpv-footage` «Съёмка с FPV: экшн-камера, ND-фильтры, Gyroflow и DVR»** (Восприятие or Оператор): mass/tune impact, shutter rule, gyro-log stabilization (camera gyro or Betaflight Blackbox), DVR settings |
| 8 | Careers and industry roles (M1–M3, M6) | 4 × 4 | **New `eng-career` «Профессия в беспилотниках: роли, навыки, сертификаты, портфолио»** (Инженер, L1): role map (pilot, technician, integrator, firmware, perception, ops), which course modules evidence which skill, certificates by country, how to build a portfolio from course labs, open-source contribution (ArduPilot/PX4/GSoC) |
| 9 | Radio setup on EdgeTX: models, mixes, telemetry, voice alerts, modules (C8, A3, C1) | 4 × 3 | **New `link-edgetx` «Пульт на EdgeTX: модели, миксы, телеметрия и модули»** (Оператор, after `link-protocols`): model setup, internal/external module, CRSF baud, logical switches for arm, telemetry discover and logging (feeds P1), USB joystick mode for sims |
| 10 | Sudden disarm / fly-away / recovery reflex (F6, F7) | 4 × 5 | **`diag-troubleshooting`: new «Дерево 6. Отключение в воздухе и улёт»** (log-first, per firmware) + practice item: a rehearsed manual-mode recovery switch tested in SITL and on the field |
| 11 | Finding a lost drone and post-crash inspection (P1, P3) | 4 × 3 | **`ops-field`: new section «Поиск упавшего аппарата»** (last coordinates from EdgeTX telemetry log/OSD/DVR, beeper, search pattern); **`ops-maintenance`: new «Чек-лист после аварии»** |
| 12 | INAV 9.1 and PX4 1.17 migration (G12, G13) | 3 × 4 | `inav-intro` new section «Обновление 8 → 9.1» (full chip erase, red settings, `control_profile`); `px4-intro` new section «Что изменилось в 1.16–1.17» (from PX4 audit §1.4); update headers |
| 13 | Betaflight 4.5.3 → 2025.12 consolidated migration (E6) | 3 × 4 | `bf-intro` new section «Переход 4.5.3 → 2025.12: чек-лист» collecting the per-module notes (App/Configurator, build options for OSD/mag, full chip erase, renamed variables) |
| 14 | No video / black goggle screen (D1) | 4 × 3 | `diag-troubleshooting` «Дерево 5» extended with a digital pairing branch (bind, firmware match, overheat, power) |
| 15 | VTOL type choice and airspeed sensors (J5, J6) | 3 × 4 | `ap-quadplane` new section «Какой VTOL выбрать: 4+1, tilt-rotor, tailsitter»; `ap-plane-tuning` new section «Датчик воздушной скорости: установка и калибровка» (`ARSPD_*`) |
| 16 | ESP32 as a flight controller (G5) | 4 × 2 | `comp-esp32` new section «ESP32 как полётный контроллер: что есть в ArduPilot и Betaflight и чего ждать» (experimental status, limits) |
| 17 | Goggles compatibility and choice (A7) | 4 × 3 | `link-digital-video` new section «Очки: совместимость и выбор» (O4 ↔ Goggles 2/Integra/3/N3, ecosystem lock-in, analog goggle criteria) |
| 18 | Application segments: agriculture, delivery, shows, inspection (M4, M5, O4) | 3 × 3 | **New `ops-applications` «Прикладные сегменты: агро, инспекция, доставка, шоу»** (requirements, payloads, licensing pointers, e.g. Part 137) |
| 19 | LiPo disposal fix, chargers and parallel charging (I2, I4) | 3 × 4 | `f-power` «Заряд, хранение, утилизация»: replace salt water with resistor discharge to 0 V; new subsection «Зарядное устройство и параллельная зарядка» |
| 20 | Board choice for ArduPilot/PX4, clones (A11) | 3 × 3 | `ap-intro` new section «Какую плату брать» (H7 vs F4, clone risks, official hardware list) |
| 21 | AI assistants for tuning and logs (N9) | 3 × 3 | `ap-logs` or `data-python` new section «ИИ-анализаторы логов: где помогают и где ошибаются» (version mixing, verification against the param list) |
| 22 | AIO vs stack and an FPV build walk-through (B4, B10) | 3 × 3 | `f-components-choice` «Шаг 5» extended with AIO; `el-wiring` new practice «Сборка 5": порядок и инструмент» |
| 23 | TBS Crossfire/Tracer and the ELRS backpack (C6, C9) | 3 × 2 | `link-protocols` short TBS subsection; `link-telemetry-radios` new section «MAVLink через ELRS Backpack по Wi-Fi» |
| 24 | Ground antennas, trackers, relays (K3) | 3 × 2 | `rf-antennas` new section «Наземные антенны и трекеры» (with the BVLOS note for relays) |
| 25 | Compass calibration incl. MagFit and compassmot (H3) | 4 × 3 | `est-sensors` new subsection; detailed parameters per AP audit §3.7 |

---

## 5. Where the course is stronger than typical community resources

- **Numbers and verification instead of folklore.** Community threads answer "how far" or "is it enough" by anecdote.
  The course gives link budgets with sensitivity per packet rate (`link-elrs`, `rf-link-budget`), GSD and overlap formulas
  with worked numbers (`per-mapping`), flight-time chains with honest usable-capacity factors (`f-power`,
  `f-components-choice`), and capacitor and wire sizing by calculation (`el-power-design`, `el-wiring`).
- **Version-precise parameter names.** The Oscar Liang "Don't ask AI" complaint (advice mixing versions) is exactly what
  the course avoids: modules state the firmware version in the header and mark 2025.12/9.1/4.7 differences inline
  (`bf-*`, `inav-setup-scratch`, `ap-safety-fs`).
- **Failsafe as an engineering table.** `ap-safety-fs` lists every trigger, parameter and action code with reasons. The
  most-read ArduPilot threads ("Clarifying battery failsafe behavior") are still trying to piece this together.
- **Log-first diagnostics.** `diag-troubleshooting`, `ap-logs`, `bf-blackbox` and `data-python` teach a fact-per-step
  method and Python plotting. Forums mostly answer "post your log" and wait for an expert.
- **SITL-first labs with acceptance criteria.** `bf-setup-scratch`, `inav-setup-scratch`, `ap-setup-scratch`,
  `px4-setup-scratch` let a student configure and verify before risking hardware. No popular English resource does this
  for all four firmwares.
- **Real accident investigations.** `ops-case-studies` works from STSB/AAIB reports (Matternet, Alauda, Freefly Alta X).
  Community crash threads rarely reach root cause.
- **Full autonomy stack.** MAVLink internals, routing, signing, companion, ROS 2, perception pipelines, precision landing,
  multi-vehicle (`mav-*`, `per-*`, `ros2-*`). On the forums these are the questions that get the fewest good answers
  (PX4-A: "Create custom model for SITL", 19,995 views, 38 replies).
- **Digital-video wiring detail.** `bf-hd-osd-video` has power, pinout and heat data per air unit (O3, O4, O4 Pro,
  Walksnail, HDZero). That table answers a large share of IntoFPV DJI/Walksnail threads in one place.

---

## 6. Outdated or wrong items, and version-migration questions

### 6.1 Outdated or wrong statements (against the targets in the header)

| # | Where | What the course says | Current state | Fix |
|---|---|---|---|---|
| 1 | `link/link-elrs.md` header and «Режимы 2.4 ГГц в ELRS 3.x», table «ELRS 3.x, из документации Signal Health» | ELRS 3.x throughout | Target ELRS 4.1.0. 4.x does not link with 3.x; STM32 RX dropped; automatic antenna mode (Gemini); selectable arm channel; Lua bind phrase on TX and RX (4.1); `elrs.lua` replaces `elrsV3.lua` | Rewrite (gap 2). Re-verify each packet-rate and sensitivity row against the 4.x docs; I did not verify the 4.x mode list |
| 2 | `link/link-elrs.md` diagnostics «не биндится после обновления» | "обновить обе стороны до одной версии" | Correct, but it should name the 3.x/4.x boundary and the SPI-receiver case | Add both |
| 3 | Course-wide combination of **Betaflight 2025.12 + ELRS 4.1** | Not discussed | SPI ELRS receivers built into AIO boards run receiver code inside Betaflight. In 2025.12 that code is ELRS 3; V4 SPI support arrives only in Betaflight 2026.6 (`ELRSV4` build option; REL; OL ELRS 4; IF-REL "4.x SPI support now merged"). A student on the course targets with a whoop AIO cannot use an ELRS 4.1 radio module without a separate serial receiver | State it in `link-elrs`, `f-micro-whoop` (new) and `bf-ports` |
| 4 | `foundation/f-power.md` «Заряд, хранение, утилизация» | "вздутие/пробой — списание (разряд в солёной воде, утилизация)" | OL: salt water is "slow and ineffective"; recommended: resistor/bulb discharge to ~0 V, verify, isolate leads, recycle | Replace |
| 5 | ArduPilot modules, header "ArduPilot 4.5+" (`ap-intro`, `ap-ekf`, `ap-heavy`, `ap-logs`, `ap-lua`, `ap-missions`, `ap-sitl`, `ap-companion`, `ap-quadplane`, `ap-plane-tuning`); `ap-setup-scratch` "ArduCopter 4.6 (Copter-4.6.3)" | 4.6 parameter names and centimetre units | Target 4.7.2; renames in 6.2 | Update headers and names; re-run `ap-setup-scratch` SITL on 4.7.2 |
| 6 | INAV modules, header "INAV 7.0+ (сверено с 8.0.1)" (`inav-intro`, `inav-gps`, `inav-ipf`, `inav-missions`, `inav-wing`, `inav-setup-wing`) | 8.0.1 | Target 9.1.0: full chip erase when upgrading from 8; `control_profile` rename; `servo_autotrim_iterm_rate_limit` removed (affects `inav-setup-wing` autotrim if it names it); GNSS rate tuned per receiver; Galileo/BeiDou on by default | Update; `inav-setup-scratch` already lists the 9.1 default changes |
| 7 | PX4 modules, header "PX4 1.14+" / "1.15" | 1.15.4 defaults | Target 1.17.0: see G13 and PX4 audit §1.4 (`MC_ROLL_P`/`MC_PITCH_P` 4.0, `IMU_DGYRO_CUTOFF` 20, `RCn_DZ` → `MAN_DEADZONE`, removed `COM_OBS_AVOID` and per-mode `RC_MAP_*_SW`, `_vN` ROS 2 topic names) | Update per PX4 audit |
| 8 | `foundation/f-regulations.md`, FAA paragraph | Part 107 / recreational / LAANC / BVLOS waiver | Missing: sub-250 g recreational exemption from registration and RID; visual observer for FPV; Part 108 (NPRM Aug 2025, final rule at OIRA since Jul 2026); FCC Covered List (Dec 2025) | Gap 5 |
| 9 | `foundation/f-remote-id-security.md` «Кому и когда обязательно» | US and EU only | UK RID dates (2026 for UK1–UK3/UK5/UK6; 2028 for UK0/UK4/legacy/privately built ≥ 100 g with camera); Flyer ID from 100 g | Add UK |
| 10 | `foundation/f-components-choice.md` «Шаг 1» | Classes start at 5" | Whoops and sub-250 g 3–3.5" are the most common first aircraft (IF: 1,895 whoop threads) | Gap 6 |
| 11 | `companion/per-depth-avoid.md` (not re-read line by line) | — | PX4 1.16 removed the old avoidance interface; ArduPilot 4.7 moved lean-angle avoidance out of standard builds | Check the module against both removals |

### 6.2 ArduPilot 4.6 → 4.7 names still used in the course

Confirmed renames from `ArduCopter/ReleaseNotes.txt` (master) and the Copter-4.7.0 release thread. The release notes do
not list every renamed name in the Land/PosHold/RTL/PILOT/WPNAV groups. **Check each new name against the 4.7.2
parameter list before editing.**

| Old (4.6) | New (4.7) | Files in `content/` that use the old name |
|---|---|---|
| `ANGLE_MAX` (centidegrees) | `ATC_ANGLE_MAX` (degrees); `Q_A_ANGLE_MAX` on QuadPlane | `des-sizing`, `per-tracking` |
| `WPNAV_*` | `WP_*`, in metres/degrees (e.g. `WP_SPD` per the release thread, unverified) | `ctl-guidance`, `est-alt-sources`, `nav-terrain`, `ap-missions`, `ap-intro`, `ap-companion`, `per-vision-pipeline`, `per-tracking` |
| `RTL_ALT` (cm) | RTL parameters renamed to metres (`RTL_ALT_M` per the release thread; `ap-safety-fs` already notes it) | `nav-terrain`, `ap-safety-fs`, `ap-intro`, `ap-setup-scratch`, `ap-sitl`, `eng-ci-configs`, `mav-multi-vehicle` |
| `ARMING_CHECK` | `ARMING_SKIPCHK` (now a mask of checks to skip; confirm semantics) | `nav-indoor`, `diag-troubleshooting`, `f-safety`, `ap-safety-fs`, `ap-intro`, `ap-setup-scratch`, `eng-ci-configs` |
| `PSC_*` (cm units); `PSC_JERK_NE/D` | Position controller converted to metres; `PSC_NE/D_JERK` (4.7.1); `PSC_VELXY_IMAX`/`PSC_VELZ_IMAX` 100× smaller, `PSC_ACCZ_IMAX` 1000× smaller | `ctl-theory`, `ap-intro`, `ap-setup-scratch` (the `PSC_ACCZ_P = MOT_THST_HOVER` rule says "масштаб 4.6"), `ap-tuning`, `ap-heavy`, `ap-companion`, `per-tracking` |
| `LAND_SPEED`, `PILOT_SPEED_UP` and similar | Land and PILOT parameters renamed to metres | `est-alt-sources` |
| `SERIALn_OPTIONS` MAVLink bits | moved to `MAVn_OPTIONS` | `mav-routing` |
| `CIRCLE_RADIUS` | `CIRCLE_RADIUS_M` | none |
| `ATC_INPUT_TC` default | reduced in 4.7 (×≈0.66 to keep the 4.6 feel) | check `ap-tuning`, `ap-setup-scratch` |

### 6.3 Community questions that exist because of the target versions (input for the migration plan)

| # | Firmware | Question people ask | Evidence | Answer to teach |
|---|---|---|---|---|
| V1 | ELRS 4.x | "My receiver stopped binding after I updated the radio" | IF-REL 4.0 RC/final threads (Dec 2025–Jan 2026); OL ELRS 4 | 3.x and 4.x do not interoperate; update both |
| V2 | ELRS 4.x | "Can my R9 / Ghost / PP receiver run 4.0?" | OL ELRS 4 | No: STM32 hardware is dropped; stay on 3.x or replace |
| V3 | ELRS 4.x + Betaflight 2025.12 | "My whoop's built-in receiver won't connect to my 4.0 radio" | OL ELRS 4 (advises not to update SPI receivers); IF-REL "4.x SPI support now merged into Betaflight"; REL Betaflight 2026.6 (`ELRSV4`) | SPI ELRS lives in FC firmware; 2025.12 stays on V3. Options: keep the TX on 3.x for that model, add a serial ELRS receiver, or move that board to 2026.6 |
| V4 | ELRS 4.x | "WebUI settings gone after update", "old Lua script doesn't work" | OL ELRS 4 | Back up `hardware.json`; delete `elrsV3.lua`/`.luac`, install `elrs.lua` |
| V5 | ELRS 4.1 | "Telemetry lost announcements are annoying" | IF-REL 4.1.0 final thread (Jul 2026) | Longer grace period in 4.1; the alert can be disabled in the model's Telemetry page |
| V6 | ELRS 4.x | "Where did the Gemini/antenna mode setting go?" | OL ELRS 4 | Antenna mode is automatic in 4.x |
| V7 | Betaflight 4.5.3 → 2025.12 | "Should I paste my 4.5 diff?", "Configurator vs Betaflight App?" | IF-REL 2025.12.1 (Dec 2025); OL 2025.12 | Fresh setup by section; full chip erase; the App version matches firmware; OSD protocol and magnetometer are build options |
| V8 | Betaflight 2025.12 | "No OSD after flashing 2025.12" | OL 2025.12 (OSD protocol is an explicit build option); OL 2026.6 comments (Walksnail OSD on a pre-release) | Rebuild with the right OSD option (analog/HD) |
| V9 | Betaflight 2025.12 vs 2026.6 (asked visibly) | "What is `trust_mag`? Why does position hold need a heading?" | OL 2026.6; REL 2026.6 | 2026.6-only: compass is opt-in (`trust_mag` OFF by default), heading needed before GPS position hold; not applicable to 2025.12 |
| V10 | Betaflight 2025.12 vs 2026.6 (asked visibly) | "My board with the IIM-42652 gyro flies differently after the update" | REL 2026.6; OL 2026.6 | 2026.6-only: gyro range corrected ±4000 → ±2000 dps, effectively doubling PID gains; reset and retune |
| V11 | Betaflight 2025.12 vs 2026.6 (asked visibly) | "GPS Rescue settings disappeared" | REL 2026.6 | 2026.6-only: `gps_rescue_velocity_p/i/d`, `gps_rescue_max_angle`, `gps_rescue_roll_mix`, `gps_rescue_use_mag` etc. removed. The course (2025.12 target) is unaffected but should say so where it names them (`gps_rescue_use_mag` appears once) |
| V12 | Betaflight (board support) | "My board isn't in the 2025.12/2026 target list, throttle only reaches 30 %" | OL 2026.6 comments (SpeedyBee F7 V3 stayed on 4.5.5) | Check board support before upgrading; stay on 4.5.x if unsupported |
| V13 | ArduPilot 4.7 | "My parameters have different names/units", "QGC shows errors for renamed parameters" | REL Copter-4.7.0 release thread; AP-Y 4.7 threads | Auto-conversion on upgrade; update QGC; table 6.2 |
| V14 | ArduPilot 4.7 | "Flash logs vanished after upgrading" | REL release thread (LittleFS boards erase logs) | Download logs before flashing |
| V15 | ArduPilot 4.7 | "Loiter turns instead of strafing", "Loiter feels different" | REL (coordinated turns default, `LOIT_OPTIONS`); AP-Y "AltHold and Loiter in 4.7 vs 4.6" 920 | `LOIT_OPTIONS = 0` restores the old behaviour; reduced `ATC_INPUT_TC` default |
| V16 | ArduPilot 4.7 | "Simple/Super Simple mode does nothing" | REL (broken in 4.7.0, fixed from 4.7.1) | Use 4.7.1 or later (target 4.7.2) |
| V17 | ArduPilot 4.7 | "Object avoidance stopped working" | REL (lean-angle avoidance removed from standard builds) | Custom build server, or proximity-based avoidance |
| V18 | ArduPilot 4.7 | "Terrain data expired, possible errors" | REL release thread; AP-Y "Serious terrain data error" 1,803 | Delete terrain data on the SD card so it re-downloads |
| V19 | ArduPilot 4.7 / ELRS 4 | "Does ELRS 4 change anything for ArduPilot?" | discuss.ardupilot "ELRS 4.0 — curious about impacts on ArduPilot" | CRSF on the FC side is unchanged; the arm-channel option and telemetry rates matter |
| V20 | INAV 9.x | "Do I need a full chip erase? Why are settings red when I paste my diff?" | REL INAV 9.0.0/9.1.0 | Yes, from 8.x; remove red settings, `defaults`, reload the edited diff; diff update tool |
| V21 | INAV 9.1 | "`profile` command not found" | REL 9.1.0 | Renamed to `control_profile` |
| V22 | INAV 9.1 | "Can I hold position without a compass?" | REL 9.1.0 | Multicopter magless heading: set heading to north before takeoff |
| V23 | PX4 1.17 | "Pitch/roll issues on X500 after 1.17" | PX4-Y 487 | Default `MC_ROLL_P`/`MC_PITCH_P` changed to 4.0; review the tune |
| V24 | PX4 1.16+ | "Bidirectional DShot doesn't work on PX4" | PX4-Y 320 | `DSHOT_BIDIR_EN` exists only from 1.16 |
| V25 | PX4 1.16 | "u-blox dynamic model 6 adds GPS lag on 1.16 or older" | PX4-Y 166 | Relevant to 1.15/1.16 users; check the 1.17 GPS driver setting |
| V26 | PX4 1.16+ | "My ROS 2 topic `vehicle_status` disappeared" | PX4 audit §1.4 | Topics with message version > 0 get `_vN` (e.g. `/fmu/out/vehicle_status_v1`) |
| V27 | PX4 1.18 (beta, watch) | "`MAV_SIGN_CFG` / `COM_RC_OVERRIDE` missing" | PX4 1.18 release notes (beta) | Not a target yet; when 1.18 is stable, signing activates from a key on the SD card and override uses `MAN_OVERRIDE_SPD`. Affects `f-remote-id-security` (MAVLink signing) later |

---

## Appendix: counts

- Questions: 119 (A 11, B 10, C 9, D 7, E 6, F 7, G 13, H 5, I 8, J 6, K 4, L 9, M 6, N 9, O 4, P 5).
- Coverage: ✓ 57 (48 %), ~ 39 (33 %), ✗ 23 (19 %).
- Questions overlapping the four firmware audits (pointer only): B5, B6, D2, D4, E1–E5, F1, F3, F4, H2, H3, H4, I6, J6, O2, P2, P4 (20).
- Version-migration questions: 27 (V1–V27), of which 3 are Betaflight 2026.6-only items people ask about (V9–V11) and 1 is a PX4 1.18 watch item (V27).
