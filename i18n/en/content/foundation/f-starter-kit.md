---
id: f-starter-kit
title: "The first kit: radio, goggles, aircraft and budget"
level: L1
readingTime: 40 min
firmware: EdgeTX 2.12.5 · ExpressLRS 4.1.0 · Betaflight 2025.12 (prices and product lines — as of November 2026)
status: published
added: 2026-11-18
tags:
  - first kit
  - budget
  - radio
  - goggles
  - BNF
  - EdgeTX
related:
  - f-components-choice
  - f-power
  - f-electricity-101
  - f-regulations
  - link-digital-video
  - link-elrs
  - f-safety
next:
  - f-components-choice
source: content/foundation/f-starter-kit.md
source_hash: 2fa3a320c768
---

## summary
The first kit is five purchases that depend on each other: the radio, the video system with goggles, the aircraft, power and tools. A mistake in the order costs more than a mistake in the model: goggles of the wrong system make the next aircraft incompatible, and a receiver on the wrong ELRS version will not link with the radio. This module gives the order of decisions, class tables with price ranges as of November 2026, the DJI goggles compatibility matrix, a “do not buy first” list and a checklist for used gear. In the lab you put together a kit for a given budget and job, check compatibility against the table and calculate the total, the weight and the minutes in the air.

## theory
### The order of decisions: what outlives what
Buy from the long-lived to the consumable:

1. **The radio** — lasts the longest: it does not crash, and it fits any aircraft with the same radio protocol.
2. **The simulator** — the radio connects to a PC over USB as a joystick. Oscar Liang (guide updated in November 2026) advises at least 5–10 hours before the first real flight. Choosing a simulator and a training program with criteria are in `ops-pilot-training`.
3. **The video system and goggles** — choosing a system locks you into an ecosystem: the video transmitter of every later aircraft has to fit these goggles.
4. **The aircraft** — a consumable. You will crash the first one, and that is normal.
5. **Batteries, charger, tools** — chosen for the aircraft class (cell count, connector).

{{diagram:starter-kit-order|You first buy what lives longer: the radio and the goggles stay for years, the aircraft and the batteries change. Goggles are chosen before the aircraft because the video transmitter has to match the goggles' system.}}

A reference total (Oscar Liang's estimate, November 2026): aircraft $100–500, radio $50–300, goggles $50–900, batteries $20–100, charger $30–200 — about $250–2000 in all.

**A gamepad or keyboard instead of a radio?** The simulator will accept them, but the stick travel and centering are different, and you will have to buy a radio anyway. Learn on it from the start.

### The radio: classes and what to look at
Minimum requirements: **EdgeTX** firmware, a built-in **ExpressLRS 2.4 GHz** module, Hall-sensor gimbals, USB-C with joystick mode. The current stable EdgeTX is **2.12.5** (October 17, 2026). Radios on STM32F2 have stayed on the 2.11 branch (2.11.8, fixes only) — this matters for used gear.

Prices — the RadioMaster site and Oscar Liang's articles, November 2026, estimates without shipping and taxes.

| Class | Example | Price, $ | Built-in RF | Module bay | For whom |
|---|---|---|---|---|---|
| Mini gamepad | RadioMaster Pocket (288 g, Hall gimbals, 2×18650 — not included) | 60–72 | ELRS 2.4, up to 250 mW (FCC) or 100 mW (EU LBT) | nano | thumb grip, whoop and park, budget |
| Ultra-budget | RadioMaster T8L | 35–40 | ELRS 2.4 | check the product page | simulator and whoop; few switches |
| Compact full-size | RadioMaster Boxer, Jumper T20S | 110–160 | ELRS 2.4, up to 1 W on the Boxer | JR (Boxer) | full-size gimbals, pinch grip, long-range flights |
| Full-size with a color screen | RadioMaster TX15, TX16S MK3 | 154–200; MAX versions 220–270 | ELRS 2.4 | check the product page | planes, many models, ArduPilot with telemetry |
| Dual-band | RadioMaster GX12 (Gemini-X) | 170 | ELRS 2.4 + 900 MHz | check the product page | long range, noisy RF environment |
| DJI ecosystem radio | DJI FPV Remote Controller 3 | not verified | DJI O4 only | none | flying O4 without a separate receiver |

- **The form factor** is chosen by grip. Thumbs on the sticks — a gamepad is more comfortable; a pinch grip — a full-size case and long sticks. There is no correct grip.
- **Gimbals.** A potentiometer has a wiper rubbing on a track, and it wears. A Hall sensor is contactless: more durable, less signal jitter. A metal (CNC) gimbal housing feels stiffer; it does not change the accuracy of the electronics.
- **The external module bay** (JR — large, nano/Lite — small, not compatible with each other without an adapter) is needed if you later want 900 MHz, Crossfire or more power. Which one to get (course reference): ELRS and Crossfire modules are made in both formats, so what you already own decides: if you have a JR module — a radio with a JR bay; if not — either of the two, but the choice cannot be changed later without an adapter.
- **“Multiprotocol” (4-in-1, MPM)** — a module with four radio chips (CC2500, NRF24L01, A7105, CYRF6936) running the MULTI-Module firmware: FrSky D8/D16, FlySky AFHDS 2A, Spektrum DSM and dozens of toy protocols. **It cannot do ELRS.** The “CC2500” version is one chip of the four (the Pocket CC2500 is 100 mW). A beginner in 2026 needs the ELRS variant; a 4-in-1 is bought for a fleet of old receivers.
- **Power.** Many radios are sold without 18650 cells — budget $10–15.

Setting up models, mixes and modules is a separate module on EdgeTX (`link-edgetx`).

### The video system and goggles: the ecosystem lock
How the systems differ in principle is in `link-digital-video` (“Four families”, “How to choose”). Here — money and compatibility (Oscar Liang's estimates, October 2026).

| System | Camera + VTX per aircraft, $ | Goggles, $ | What it locks |
|---|---|---|---|
| Analog 5.8 GHz | 30–80 | 55–130 box without diversity; 100–220 box with diversity; 360–670 binocular | nothing: any VTX with any goggles |
| HDZero | 125–170 | 300–350 (BoxPro), 650 (Goggle 2) | HDZero VTX only; the goggles also receive analog |
| Walksnail Avatar | 79–184 | 200 (Goggles L), 459 (Goggles X) | Walksnail VTX only; Goggles X show analog and HDZero through the AV/HDMI inputs with an external receiver, Goggles L do not |
| DJI O4 / O4 Pro | 130–160 / 229 | 229 (Goggles N3), 499 (Goggles 3) | DJI goggles work only with DJI; they do not show analog |

The price of changing systems = new goggles + a new VTX for **every** aircraft. Three aircraft on analog → DJI: $229–499 for the goggles and 3 × $130–229 for the air units.

The DJI matrix (the O4 specification on dji.com, opened 2026-11-18):

| Goggles | O4 Air Unit (8.2 g with the camera, 3.7–13.2 V) | O4 Air Unit Pro (32 g, 7.4–26.4 V) | O3 Air Unit | DJI radio |
|---|---|---|---|---|
| Goggles 3 | yes, latency from 20 ms | yes, from 15 ms | yes — according to reviews, check against dji.com | FPV RC 3 |
| Goggles N3 | yes, from 24 ms | yes, from 19 ms | **no** (Oscar Liang) | FPV RC 3 |
| Goggles 2 / Integra | yes, up to 35 ms | yes, up to 30 ms | yes | FPV RC 2 |
| Goggles V2 | not on DJI's list | not on DJI's list | yes | discontinued in 2024 |
| Goggles from other brands | no | no | no | — |

Traps:

- **The DJI radio is tied to the goggles generation** (RC 3 ↔ Goggles 3/N3, RC 2 ↔ Goggles 2/Integra) and requires the S.Bus protocol on the flight controller. With an EdgeTX radio you need a separate ELRS receiver — that is what almost everyone does.
- **The O4 (small)** is powered only from a 5 V BEC ≥ 10 W; it does not run directly from 4S–6S. Power and heat — `bf-hd-osd-video`.
- **The N3 has no IPD or diopter adjustment**, but prescription glasses fit under them. The Goggles 3 have an IPD of 56–72 mm and from −6 to +2 D. Try them on before buying.
- **Analog goggles:** a “box” is one screen, cheap, usable with prescription glasses; binoculars are two screens, and IPD and focus matter. Diversity (two receivers) noticeably improves the picture.
- **USA.** Since December 22, 2025, new foreign models of drones and components do not receive FCC authorization; previously approved ones are sold, what has been bought remains legal, and exemptions are in effect until January 1, 2027. Details and links — `f-regulations`, section “FCC Covered List”. Before buying in the USA, check whether the model is on sale and whether spare parts are available for it.

### The aircraft: class and way of buying
| Class | Weight with battery | Power | Where to fly | BNF, $ |
|---|---|---|---|---|
| Tiny whoop 65–75 mm, ducted props | 25–45 g | 1S | apartment, yard | ≈ 100 (analog) |
| 3–3.5" | ≈ 230–330 g; “sub-250” — only with a light battery | 4S | park, field | ≈ 245 (analog), ≈ 480 (O4 Pro) — prices of a 3-inch |
| 5" freestyle | ≈ 600–750 g | 6S | a field away from people | ≈ 240 (analog), ≈ 440 (O4 Pro) |
| Cinewhoop 2.5–3.5", ducted props | ≈ 250–500 g | 4S–6S: the same S as the main aircraft (shared packs and charger), motor KV to match it (`f-aero-props`, “KV for the prop”) | filming close to objects | not verified |
| 7" and larger | from 1 kg | 6S | long-range flights | later: `f-components-choice` |

The weights are typical for the class, not datasheet values. The first aircraft is a whoop or a 3.5": Oscar Liang directly advises against starting with a 5" — the impact energy of 700 g at 100 km/h is something else (`f-safety`). Whoops have a module of their own (`f-micro-whoop`).

| Way | What is in the box | Pros | Cons |
|---|---|---|---|
| **BNF** (bind-and-fly) | an aircraft with a receiver, set up | flies on the day of purchase; the radio and goggles are your own | repairs are still up to you |
| **PNP** | an aircraft without a receiver | you fit your own receiver | soldering and port setup are needed |
| **RTF kit** | aircraft, radio, goggles, battery, charger | one purchase (a whoop kit ≈ $215) | the kit's radio and goggles are usually not worth keeping — you pay twice |
| **Self-build** | loose parts | you know the whole aircraft and repair it yourself | a 5" on no-name parts ≈ $170, on decent ones ≈ $255 — no cheaper than a BNF (≈ $237), plus tools and mistakes |
| **Ready-made DJI** (Avata 2) | drone, goggles, radio, stabilization | the best way in “for the picture”, flies out of the box | closed firmware, expensive repairs, acro is limited, does not teach repair; kits ≈ $800–1400 (not checked against the DJI store) |

The conclusion: the first aircraft is a BNF, the second is a self-build. Do not touch the factory setup of a working BNF until you have learned to fly: first `diff all` to a file.

### Batteries, charger, parallel board: the minimum
- **Number of batteries.** One flight is 3–5 minutes (`f-power`, “Flight time”). Four batteries give 12–20 minutes per session; with fewer than three there is more travel than flying. Reference points: 5 pcs of 1S 320 mAh ≈ $22; 4S 850 mAh ≈ $20 each; 6S 1200 mAh ≈ $35 each.
- **The charger — balance only** (`f-power`, “The charger and parallel charging”). For 1S — a six-port board ($30–36), with BT2.0, A30 or PH2.0 connectors to suit your whoop. For 4S–6S — a single-channel 200 W (≈ $60; the iSDT 608AC, for example, gives only 60 W on its built-in supply), a dual-channel (≈ $120) or a four-channel (≈ $200).
- **Calculate the power in advance:** P = U × I (`f-electricity-101`). Four 4S 850 mAh in parallel at 1C: 16.8 V × 3.4 A ≈ 57 W — fits within 60 W. Four 6S 1200 mAh: 25.2 V × 4.8 A ≈ 121 W — you need a more powerful charger or twice the time.
- **A parallel board** — only with fuses, batteries with the same cell count and a difference of no more than 0.1 V per cell. Price ≈ $10–25 (not verified).
- **Connectors.** A 3.5" usually uses XT30, chargers and boards use XT60: an adapter is needed.
- **Storage:** a non-flammable container, Storage mode at 3.8 V per cell.

### Tools and consumables
| What | Parameters | When |
|---|---|---|
| Hex drivers | 1.5, 2.0, 2.5 mm (3.0 — optional) | right away |
| Prop wrench | 8 mm (M5 nut) for 3.5–5"; for a whoop — a prop puller | right away |
| Nut drivers | 4.0 mm (M2), 5.5 mm (M3) | right away |
| Cell tester (LiPo checker) | 1S–6S | right away, mandatory for parallel charging |
| Spare props | 2–4 sets | right away |
| Battery straps, 2 and 3 mm zip ties, electrical tape | — | right away |
| Soldering iron | 60–80 W, powered from USB-C PD or 12–25 V; 63/37 rosin-core solder, flux | before the first repair (`el-wiring`) |
| Multimeter | continuity, voltage | before the first repair (`el-measure`) |
| Smoke stopper | for XT30/XT60 | before the first soldering of the power section |
| Heat shrink, threadlocker, isopropyl alcohol ≥ 91 % | — | with the soldering iron |

The “right away” set is ≈ $30–50, with a soldering iron and a multimeter — ≈ $80–150 (estimate, not checked against stores).

### Three budgets
Classes and ranges, not a shopping list. Prices as of November 2026, estimates in US dollars without shipping, duties and VAT (in the EU add 20–25 %).

| Item | 1. Whoop, analog | 2. Park 3.5", analog | 3. DJI digital, 3.5–5" |
|---|---|---|---|
| Radio | 35–72 | 60–160 | 110–270 |
| Simulator | 15–20 | 15–20 | 15–20 |
| Goggles | 55–130 | 100–220 | 229–499 |
| BNF aircraft | ≈ 100 | ≈ 245 | 440–480 |
| Batteries | 22 (5 × 1S) | 80 (4 × 4S) | 80–140 (4 pcs) |
| Charger | 30–36 | ≈ 60 | 60–200 |
| Tools, consumables | 20–40 | 40–150 | 80–150 |
| **Total** | **≈ 280–420** | **≈ 600–935** | **≈ 1015–1760** |

Oscar Liang's ready-made bundles (October 2026) give the same orders of magnitude: a whoop ≈ $262, a 3" analog — up to $600, the entry into digital — up to $900, the “maximum” — up to $1500.

### What not to buy first
- **A 5" as the first aircraft.** Expensive crashes, dangerous, nowhere to fly.
- **An RTF kit “to add to later”.** The kit's radio and goggles are rarely any good for the next aircraft. The exception is a deliberate choice of the Avata 2.
- **Goggles before the decision on the system.** And expensive analog binoculars if you are going to move to digital in six months.
- **A radio without ELRS** (CC2500/4-in-1) for modern BNFs — the receiver will have to be replaced.
- **A single battery** and a charger “just barely enough” without balancing.
- **A parallel board without fuses.**
- **A 900 MHz module, GPS, a 7" “to grow into”** — until you fly confidently on 2.4 GHz within line of sight.
- **Spare parts “just in case”.** Except props: you will buy whatever breaks.

### Used gear: a checklist
- **Radio:** the gimbals return to center, the values on the calibration screen do not jitter; all the switches; which built-in module (ELRS or CC2500); the MCU (STM32F2 — EdgeTX 2.11 only); USB is detected by the PC as a joystick; the battery bay contacts.
- **Goggles:** dead pixels, lens scratches, the fan, the antenna connectors, the power cable. DJI — power them on and link them with your own or the seller's air unit when buying; check the generation against the matrix above.
- **Aircraft:** cracks in the arms, play and grinding in the bearings, a burnt smell at the ESC, the flight controller is detected over USB and returns `diff all`, the receiver type and version, the video transmitter warms up and gives a picture.
- **Do not buy used batteries.** If you get them as part of a kit: no puffing, cell spread at rest within 0.03–0.05 V, and charge them one at a time under watch right away.
- **Charger:** compare the cell voltage readings with a multimeter.

### 250 g and the rules
The takeoff weight determines the category (`f-regulations`): in the EU an unmarked aircraft lighter than 250 g flies in A1 (a self-built one — only if its maximum speed is also less than 19 m/s, otherwise A3), and operator registration is required if there is a camera; in the United Kingdom a Flyer ID is needed from 100 g already; in the USA, lighter than 250 g for recreation only — without registration and Remote ID. An FPV aircraft always has a camera. Weigh it **with the battery and everything attached**: a 3.5" with an 850 mAh battery easily goes over 250 g, with a 650 mAh — it passes. The VTX power and the ELRS region (EU LBT — 100 mW on 2.4 GHz) are also set by the country's rules.

### The ELRS version trap
The radio and the receiver link only on the same **major** version of ExpressLRS: 3.x and 4.x are incompatible (`link-elrs`, “The 3.x → 4.x transition”). The current one is 4.1.0, and warehouses hold a bit of everything.

| What you bought | Which version is inside | What to do |
|---|---|---|
| A radio with built-in ELRS | whatever was flashed at the factory | look in ELRS Lua; update to 4.1.0 once all the receivers are updated |
| A BNF with a separate (UART) ELRS receiver | 3.x or 4.x | update the receiver over Wi-Fi to the radio's version; the binding phrase is the same |
| A whoop with an **SPI receiver** on the flight controller board | determined by Betaflight: in 2025.12 — ELRS 3 only | ELRS Configurator does not flash such a receiver. Either the radio stays on 3.x, or flight controller firmware with ELRS 4 support (the conditions are in `link-elrs`), or a whoop with a UART receiver |
| Old ELRS hardware on STM32 (FrSky R9, Ghost) | 3.x forever | do not buy |

Before buying a whoop, ask the seller: is the receiver SPI or UART? How an SPI receiver works and what ways out of the trap it has are in `f-micro-whoop`.

### Place in the system
- **Receives:** the weight and energy budget and the selection logic — from `f-components-choice`; flight time and the charging and storage rules — from `f-power` and `f-electricity-101`; the 250 g thresholds, the radio region and the status of the US market — from `f-regulations`; the principle of the video systems — from `link-digital-video`; version compatibility — from `link-elrs`.
- **Provides:** a ready, compatible kit — to the setup modules (`bf-setup-scratch`, `bf-hd-osd-video`); the cell count and connector — to charging (`f-power`); the receiver type — to port setup (`bf-ports`).
- **If you get it wrong here:** a radio on ELRS 4.x and an SPI whoop on ELRS 3 → `RXLOSS`, arming blocked (`bf-arming-safety`); goggles of the wrong generation → a black screen with a working air unit (`link-digital-video`); a battery heavier than calculated → the aircraft went over 250 g and landed in another category (`f-regulations`).

## practice
A lab without hardware: a decision from given input data, with the answer checked by arithmetic. Prices are from the theory tables (November 2026, estimates); the weights and the average current are **notional input data of the assignment** — for your own aircraft substitute numbers from the scales and from the OSD.

**Assignment.** A budget of $700. The job: freestyle in a park, EU, and you want to stay under 250 g. There is a PC for the simulator, there are no tools. The goal is at least 15 minutes in the air per session.

### Step 1. The order and the choice of classes
Follow the order from the theory and write down each decision with its reason:

1. Radio — a mini gamepad with ELRS 2.4 ($65) and two 18650 cells ($12). Reason: budget, ELRS, joystick mode.
2. Simulator — $20.
3. Video — analog: with $700 digital does not fit (goggles $229 + aircraft $480 = $709 without anything else). Goggles — a box with diversity, $160.
4. Aircraft — a BNF 3–3.5", analog, ELRS receiver, $244 (the price of a 3-inch from the bundle).
5. Power — 4 4S batteries at $20 each, a 200 W charger with a 60 W supply ($60), a parallel board with fuses and an XT30–XT60 adapter ($15).
6. “Right away” tools: hex drivers, an 8 mm wrench, a cell tester, two sets of props, straps — $40.

### Step 2. The compatibility table
Fill in the table for your own set; the sample shows the expected answers.

| Pair | What to check | Result in the sample |
|---|---|---|
| Radio ↔ receiver | ELRS 2.4 protocol; major version; receiver type (UART or SPI) | UART: update the receiver and the radio to 4.1.0, one binding phrase |
| Radio ↔ region | ELRS firmware for the EU (LBT), 100 mW | select the EU region when flashing |
| Goggles ↔ VTX | system (analog 5.8 GHz), band and channel, power per the country's rules | matches; VTX power — per `f-regulations` |
| Battery ↔ aircraft | cell count 4S, XT30 connector | matches |
| Battery ↔ charger | cell count, connector, power | an XT30–XT60 adapter is needed; power — step 4 |
| Aircraft ↔ rules | weight with battery < 250 g, there is a camera | step 3 |
| Radio ↔ simulator | USB joystick | yes |

### Step 3. Weight and category
Input data: aircraft dry weight 158 g, a 4S 850 mAh battery — 98 g, a 4S 650 mAh — 76 g.

- With 850 mAh: 158 + 98 = **256 g** — more than 250 g, and in the EU that is no longer A1 but A3.
- With 650 mAh: 158 + 76 = **234 g** — a margin of 16 g.

The conclusion: for the “under 250 g” job we take 650 mAh. There is a camera, so operator registration in the EU is required at any weight. For a self-built aircraft the weight alone is not enough: A1 also requires a maximum speed below 19 m/s (`f-regulations`).

### Step 4. Minutes in the air and charging
Input data: average current 10 A, we use 80 % of the capacity. The formula from `f-power`: t = 0.8 × Q / I.

- 650 mAh: 0.8 × 0.65 / 10 × 60 = **3.1 min** per battery; four batteries — **12.5 min**. The 15-minute goal is not met: you need ⌈15 / 3.12⌉ = **5 batteries** (15.6 min).
- 850 mAh: 4.1 min per battery, four — 16.3 min, but the weight is 256 g.

{{diagram:chart-starter-kit-session|At an average current of 10 A four 4S 850 mAh batteries give 16.3 minutes per session, and four 650 mAh — only 12.5: to stay under 250 g and fly 15 minutes you need a fifth battery.}}

Charging five 4S 650 mAh batteries in parallel at 1C: current 5 × 0.65 = 3.25 A, power 16.8 × 3.25 = **54.6 W** — less than 60 W, so the charger will manage in about an hour.

### Step 5. The total and the budget decision
| Item | $ |
|---|---|
| Radio + 2×18650 | 77 |
| Simulator | 20 |
| Goggles | 160 |
| BNF aircraft | 244 |
| Batteries 5 × 20 | 100 |
| Charger | 60 |
| Board and adapter | 15 |
| “Right away” tools | 40 |
| **Total** | **716** |

An overrun of $16. Acceptable solutions — each with its price: (a) goggles without diversity for $75 → $631, the remaining $69 goes toward a soldering iron; a worse picture; (b) four batteries → $696, but 12.5 minutes instead of 15; (c) a $35 radio → $686, fewer switches. Unacceptable ones: giving up the cell tester, a parallel board without fuses, a charger without balancing.

Now repeat steps 1–5 for your own job and budget. Take prices from two stores as of today's date and write the date down.

Self-check: the lab is complete when: (1) for the sample assignment your numbers matched steps 3–5: 256 g and 234 g, 3.1 min per battery, 5 batteries for the 15-minute goal, 54.6 W, a total of $716 — with a discrepancy of no more than 2 %; (2) your own kit is laid out in the order “radio → video → aircraft → power → tools”, and the reason for each choice is a row from the theory tables (class, compatibility or price); (3) your own compatibility table has seven rows, as in step 2, the ELRS version and the receiver type (SPI or UART) are stated explicitly, and no row is left with “don't know”; (4) for your own kit you have calculated the weight with the battery, the time per battery (t = 0.8 × Q / I), the number of batteries for the goal rounded up, and the charger power (P = U × I) — a repeat calculation with the same formulas agrees to within 2 %; (5) the total does not exceed the budget, or it is written down what was cut and why, and every price has a date and a store next to it.

**Reference for self-check.** The correct solution of the assignment: analog, a 650 mAh battery (234 g), five batteries (15.6 min), a charger with a 60 W supply (54.6 W needed), a total of $716 and one of the acceptable cuts (a)–(c) with its price. Two common mistakes: the 850 mAh battery is taken because four of them give 16.3 min — but 256 g violates the condition of the job; the 0.8 factor is forgotten — then it comes out at 3.9 min per battery and it seems that four are enough (15.6 min), though in reality that is 12.5 min. A third one is fitting into $700 by removing the cell tester, the fuses or balancing: the budget adds up, but the kit is unacceptable.

## diagnostics
- **Symptom:** a new whoop does not link with the radio although the binding phrase is the same
  - Possible cause: an SPI receiver under Betaflight 2025.12 is ELRS 3, while the radio is already on 4.x.
  - What to do: check the version in ELRS Lua and the receiver type; the options are in the table “The ELRS version trap” and in `link-elrs`.
- **Symptom:** a black screen in the DJI goggles, the air unit is working
  - Possible cause: an incompatible generation (Goggles N3 and O3; Goggles V2 and O4) or the air unit is not bound to the goggles.
  - What to do: check the pair against the matrix, bind again, update the firmware on both sides.
- **Symptom:** the kit is bought, but you get to fly 4 minutes per session
  - Possible cause: a single battery.
  - What to do: calculate the number of batteries for the goal (step 4) and the charger power for them.
- **Symptom:** the charger charges four batteries in two hours instead of one
  - Possible cause: the built-in power supply is weaker than the power needed, and the charger reduced the current by itself.
  - What to do: P = U × I for the whole bundle; an external power supply or fewer batteries at a time.
- **Symptom:** the battery does not connect to the charger or to the aircraft
  - Possible cause: different connectors (XT30 and XT60; BT2.0, A30 and PH2.0 on 1S).
  - What to do: an adapter for charging; on the aircraft change the connector by soldering, not with a chain of adapters.
- **Symptom:** the RTF kit is mastered, and a new BNF does not bind to the kit's radio
  - Possible cause: the kit's radio works on its own protocol or has no ELRS.
  - What to do: an EdgeTX radio with ELRS; keep the kit's radio for the simulator.
- **Symptom:** a “sub-250” aircraft showed 262 g on the scales
  - Possible cause: the battery is heavier than calculated, or a camera or mounts were added.
  - What to do: weigh it with the battery, take a battery of smaller capacity or fly by the rules of your category (`f-regulations`).
- **Symptom:** a used radio does not update to EdgeTX 2.12
  - Possible cause: the MCU is an STM32F2 — supported only in the 2.11 branch.
  - What to do: install 2.11.8; for `Arm using = Switch` in ELRS 4, EdgeTX 2.11.0+ is enough.

## checklist
- Radio: EdgeTX, built-in ELRS 2.4 GHz, Hall gimbals, USB joystick; the cells are bought
- 5–10 hours of simulator on your own radio before the first flight
- The video system is chosen before the aircraft; the “goggles ↔ VTX” pair is checked against the matrix
- The first aircraft is a BNF whoop or 3.5", not a 5"
- The radio and the receiver are on the same ELRS version; the receiver type (SPI or UART) is known
- At least 3–4 batteries; a balance charger, with the power calculated
- A parallel board with fuses, a cell tester, a non-flammable container
- The weight with the battery is measured, the category under the country's rules is determined
- Prices are written down with the date and the store

## references
- EdgeTX — Releases (v2.12.5 “Queen Anne's Revenge” marked Latest; 2.11.8 for STM32F2; accessed 2026-11-18) | https://www.github.com/EdgeTX/edgetx/releases | primary | A
- DJI — O4 Air Unit Series, Specs (compatible goggles and radios, weight, power, latency; accessed 2026-11-18) | https://www.dji.com/o4-air-unit/specs | primary | A
- ExpressLRS Docs — SPI Receivers (the version is determined by the flight controller firmware, Configurator does not flash them) | https://www.expresslrs.org/hardware/spi-receivers/ | primary | A
- RadioMaster — Radio Controller, catalog with prices (accessed 2026-11-18) | https://radiomasterrc.com/collections/radio-controller | primary | B
- RaceDayQuads — RadioMaster Pocket, specifications and price (accessed 2026-11-18) | https://www.racedayquads.com/products/radiomaster-pocket-edgetx-rc-transmitter-choose-version?aff=2 | secondary | B
- heliguy — Which goggles and remote controllers are supported by the DJI O4 Air Unit series | https://www.heliguy.com/blogs/knowledge-base/which-goggles-and-remote-controllers-are-supported-by-the-dji-o4-air-unit-series | secondary | B
- Oscar Liang — How To Get Started With FPV Drone (updated in November 2026: order, cost, what to avoid) | https://oscarliang.com/fpv-drone-guide | secondary | B
- Oscar Liang — Beginner FPV Drone Bundles (October 2026: bundles with prices) | https://oscarliang.com/beginner-fpv-drone-bundles/ | secondary | B
- Oscar Liang — FPV Systems compared (October 2026: the price of the VTX and goggles by system) | https://oscarliang.com/fpv-system/ | secondary | B
- Oscar Liang — FPV Goggles (prices, IPD, focus, N3 and O3 compatibility) | https://oscarliang.com/fpv-goggles/ | secondary | B
- Oscar Liang — Radio Transmitter guide (gimbals, grip, module bays) | https://oscarliang.com/radio-transmitter/ | secondary | B
- Oscar Liang — The Cheapest 5" FPV Drone Build in 2026 (self-build versus BNF) | https://oscarliang.com/cheapest-fpv-drone-build/ | secondary | B
- Oscar Liang — FPV Tools (wrench sizes, consumables) | https://oscarliang.com/fpv-tools/ | secondary | B
- Oscar Liang — How to choose LiPo charger and power supply (charger classes, power on AC and DC) | https://oscarliang.com/choose-lipo-battery-charger-power-supply/ | secondary | B

## notes
The prices are estimates as of November 2026 in US dollars: the RadioMaster catalog and the RaceDayQuads product page were opened on 2026-11-18, the rest is from Oscar Liang's articles with edits of October–November 2026. The GetFPV, BetaFPV (aircraft catalog), HDZero and DJI store pages could not be opened, so the prices of whoops, HDZero/Walksnail goggles and DJI air units are taken from a single source. Not verified: the price of parallel boards and tools, of Avata 2 kits, of the DJI FPV RC 3 radio, of cinewhoops; the module bays of the TX15, TX16S MK3, GX12 and T8L; O3 support in the Goggles 3; the chip set of the 4-in-1 (from memory of the MULTI-Module documentation). The class weights and the 10 A average current in the lab are typical and notional values, not measurements.
