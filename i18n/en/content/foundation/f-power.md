---
id: f-power
title: "Power: LiPo, Li-Ion, BEC"
level: L1
readingTime: 20 min
firmware: any firmware
status: published
added: 2026-11-07
tags:
  - LiPo
  - Li-Ion
  - power
related:
  - f-physics
  - f-motors-esc
next:
  - f-motors-esc
source: content/foundation/f-power.md
source_hash: d3f0cc66d732
---

## summary
The battery is the heaviest and the most dangerous part of a drone. This module explains how LiPo differs from Li-Ion, what “S”, “mAh” and “C” really mean, why voltage sags under load, how to estimate flight time, and how to burn down neither the battery nor the workshop. At the end — a real log from a heavy 10", where the voltage sag told more than any spec sheet.

## theory
### Designations
- **S** — the number of cells in series. 6S = 6 cells, the voltages add up.
- **mAh** — capacity. 1300 mAh = 1.3 Ah.
- **C** — discharge current as a multiple of capacity. 1300 mAh × 100C = 130 A according to the label. Marketing C ratings are almost always inflated; go by internal resistance and real tests. How to choose capacity and C for your current — see the subsection “Capacity and C rating: how to choose” below.
- **P** — parallel cells in packs built from cylindrical cells (6S2P = 12 cells).

### LiPo vs Li-Ion
- **LiPo:** nominal 3.7 V/cell, full charge 4.2 V (LiHV — 4.35 V). Delivers huge currents, but less energy per gram. For freestyle, racing, anything with high currents and short flights.
- **Li-Ion (18650, 21700):** nominal about 3.6 V, full 4.2 V, deeper discharge — down to 2.8–3.0 V. Noticeably more energy per gram, more modest currents. For long-range 7–10", wings, long hovering at moderate throttle.

Selection rule (numbers — `el-battery-packs`): Li-Ion gives more minutes if (1) the average current per cell is no higher than 1.5C — a course guideline for a 21700 without airflow cooling, the cell datasheet has no such number (for a 4.2 Ah P42A that is 6.3 A per cell, 25 A for a 4P pack) and (2) the peak current per cell is no higher than 0.6 × the rated continuous current (P42A: 0.6 × 45 = 27 A, 108 A for a 4P pack). If even one check fails — more P (the weight grows, recalculate the time) or LiPo; if you need peaks of tens of amps per kilogram of pack — LiPo. Take the average current from a log or from the hover calculation (`f-components-choice`); the check after the flight — average current from the log / P, and a warm, not hot, pack.

### Voltage sag
Every cell has an internal resistance R. At current I the voltage drops by I × R. On a sharp throttle input the sag is instantaneous, and the flight controller sees not “how much is left” but “how much is left minus the sag”. Hence false low-voltage warnings on punch-outs and real ESC shutdowns on a depleted battery.

### Flight time
Estimate: time, min ≈ usable capacity, Ah / average current, A × 60. Usable capacity is about 80% of the rating: never run the battery down to zero. Take the average current from the log, not from your head.

### BEC and on-board voltages
The flight controller, receiver, camera and VTX run on 5, 9 or 12 V, not on 6S. These voltages come from BECs — regulators on the flight controller or the ESC. Before connecting peripherals, check: which pad powers it, whether the BEC has enough current (a VTX at high power can draw more than an amp), and that the VTX is not on 5 V if it needs 9–12 V.

### Case: voltage sag on a 10"
Log of a heavy 10" on 6S (battery at 23.8 V at the start of the flight): median current 14–16 A, but p95 on the aggressive profile is 124 A, peak 147 A. On those peaks the voltage dropped to 16.2 V, i.e. 2.7 V per cell. Conclusion: at such currents the battery is working at its limit, and the ESC must be checked for a continuous current of about 125 A. No label would have told you this — the log did.

### Calculating flight time honestly
t ≈ (capacity × usable fraction) / average current. Fraction: 0.8 for LiPo (landing at 3.5 V/cell), 0.85 for Li-Ion (down to 3.0 V/cell). Average current — from the log (`BAT.Curr`/`amperageLatest`), not from hover: 5" freestyle — 25–40 A average with 60–100 A peaks; 7" long range cruise — 8–12 A; X8 15" hover ~30 A. Example: 6S 4000 mAh Li-Ion on a 7" at 10 A: 0.85 × 4 / 10 × 60 ≈ 20 min. Check after the flight: the mAh put back by the charger must match `CurrTot`/mAh drawn in the log within ±10% — otherwise the current sensor is calibrated wrong (`BATT_AMP_PERVLT`, `ibata_scale`).

### Sag and internal resistance in numbers
U under load = E − I·R. A “fresh” LiPo 6S 1300 mAh 100C: R ≈ 2 mΩ/cell → 12 mΩ/pack; at 80 A the sag is 1 V (4.0 → 3.84 V/cell). The same pack after 150 cycles — 6 mΩ/cell → 36 mΩ → 2.9 V of sag: this is why “old” packs trigger the OSD warning on the very first punch. Li-Ion 6S4P P42A ≈ 40–50 mΩ/pack: at 60 A — 2.4–3 V, one cell's worth is “lost”; that is why warning thresholds are set by voltage **under load** or by mAh (the rule and numbers — next subsection). Heat: 60 A × 60 A × 0.045 Ω = 160 W in the pack — Li-Ion heats up noticeably; LiPo 100C — 80 × 80 × 0.012 = 77 W. In detail (chemistries, packs, BMS) — the “Li-Ion packs” module.

### Voltage thresholds: warning and landing
**Two different voltages.** The rest voltage E is what a cell shows with no current, 1–2 minutes after landing (estimate): it tells you the state of charge. The voltage under load U = E − I·R is what the flight controller sees in flight, and alarms trigger on it. The difference is the sag: at the same state of charge it is larger the higher the current and the older the pack (above: 2 → 6 mΩ/cell over 150 cycles). Hence two rules:
1. The threshold in the firmware is set **under load** — so that at a typical cruise current it corresponds to the desired remaining charge. Short punches are filtered out by a delay, not by lowering the threshold.
2. The threshold is verified **after landing** — by the rest voltage and by how many mAh the charger put back into the battery.

**Chemistry limits — from the datasheet.**
- **LiPo.** Tattu (Grepow): “never discharge below 3V per cell under load”, full charge 4.2 V/cell; for its UAV batteries Tattu recommends a cutoff of 3.5 V/cell. Gens Ace: automatic cutoff at 3.0 V/cell.
- **LiHV.** Charge to 4.35 V/cell, only for packs where this is allowed; lower thresholds — as for LiPo (Oscar Liang). In Betaflight for LiHV `vbat_max_cell_voltage = 440`, otherwise a fresh pack is not detected (`f-micro-whoop`).
- **Li-Ion.** The rated cell cutoff for the Molicel P42A is 2.5 V (INR21700-P42A datasheet); for your cell — from its datasheet. This is the cell's limit at the test current, not a landing point: the course lands Li-Ion at 3.0 V/cell (capacity fraction 0.85, subsection “Calculating flight time honestly”).

**Per-cell thresholds, under load.**

| Chemistry and class | Warning | Critical (land now) | Lower limit under load | Why | Where the numbers come from |
|---|---|---|---|---|---|
| LiPo / LiHV, 4–6S: 5", 3–3.5", cinewhoop | 3.5 V | 3.3 V | 3.0 V | after 3.5 V under working current little energy remains; below 3.0 V — damage | 3.5 and 3.3 — Betaflight defaults (`sensors/battery.c`); 3.5 — Tattu's recommendation for UAVs and Oscar Liang (“think about landing around 3.5–3.6 V” in flight); 3.0 — Tattu, Gens Ace |
| LiPo, 7–10" and heavy craft, return longer than a minute | 3.6 V or by mAh | 3.5 V | 3.0 V | after the warning you still have to fly back: the threshold is higher by the return time | 3.6 / 3.5 — the 6S values in `ap-setup-scratch` (ArduPilot Initial Parameter Setup gives the same); for your own route — by the procedure below |
| LiPo / LiHV 1S, whoop | 3.3–3.4 V | 3.1–3.2 V | 3.0 V | on 1S the same 0.3 V of cell and connector sag is 8 % of the voltage (`f-micro-whoop`): with a 3.5 V threshold the alarm comes on a punch with a half-empty cell, and landing indoors takes seconds | estimate (`f-micro-whoop`); 3.0 — Tattu |
| Li-Ion 18650/21700: 7" LR, wing, cargo | 3.3 V or by mAh | 3.0 V | cell datasheet (P42A — 2.5 V) | the sag is large (6S4P at 60 A — 0.4–0.5 V per cell), so the main signal is mAh | 3.3 / 3.0 — course values (`bf-modes-osd`, `inav-setup-wing`), estimate; 2.5 — P42A datasheet |

**Where it is set.**
- **Betaflight.** `vbat_warning_cell_voltage` (default 350 = 3.50 V) and `vbat_min_cell_voltage` (330 = 3.30 V) — in hundredths of a volt per cell (`sensors/battery.c`). The smoothed voltage is compared: filter `vbat_display_lpf_period`, default 30 — cutoff 1 / (30 / 10) = 0.33 Hz (`sensors/battery.h`). Delay — `vbat_duration_for_warning` and `vbat_duration_for_critical`: in tenths of a second, 0–150, default 0; the voltage must stay below the threshold for that long. Starting point — 20 (2 s), like the delay of the `L02` alarm in `link-edgetx` (estimate).
- **ArduPilot.** `BATT_LOW_VOLT` and `BATT_CRT_VOLT` — the voltage of the **whole pack**: number of cells × the value from the table, different for each pack. The `BATT_LOW_VOLT` default of 10.5 V is 3S × 3.5 V; for 6S it is meaningless. Delay — `BATT_LOW_TIMER` (per the ArduPilot documentation, it triggers after 10 s below the threshold); `BATT_FS_VOLTSRC = 1` compares against the voltage corrected to rest using the pack resistance (`ap-sensors`). Actions — `BATT_FS_LOW_ACT = 2` (RTL, recommended by the documentation) and `BATT_FS_CRT_ACT = 1` (Land), in detail — `ap-safety-fs`.
- **INAV.** `vbat_warning_cell_voltage`, `vbat_min_cell_voltage` and the capacity thresholds `battery_capacity_warning` / `battery_capacity_critical` — an example for Li-Ion 4S2P in `inav-setup-wing`, the rest — the INAV documentation.

**The mAh alternative.** The mAh counter does not depend on sag, so for Li-Ion, long-range flights and old packs it is more reliable than voltage. Landing — at the same capacity fraction as in the flight-time calculation: 0.8 for LiPo, 0.85 for Li-Ion. The “time to go home” warning — earlier by the return consumption: 0.8 × capacity − cruise current × return time. This needs a calibrated current sensor (±10 % against the charger, subsection “Calculating flight time honestly”).
- Betaflight: `bat_capacity` — pack capacity, `use_cbat_alerts = ON`, `cbat_alert_percent` — the remaining percentage at which the warning comes (default 10; for landing at 0.8 of capacity — 20). Betaflight treats only 0 % remaining as critical by mAh (`batteryUpdateConsumptionState()` in `battery.c`), so “land now” stays with the voltage.
- ArduPilot: `BATT_LOW_MAH` and `BATT_CRT_MAH` — remaining mAh; the documentation advises `BATT_LOW_MAH` at about 20 % of capacity (1000 for 5000 mAh).
- EdgeTX: a logical switch on `Capa` at 0.8 of capacity (`link-edgetx`).

**Worked example: why a delay and not a lower threshold.** 6S 1300 mAh LiPo: R = 2 mΩ/cell for a fresh pack and 6 mΩ/cell after 150 cycles (subsection above), cruise 30 A (the middle of 25–40 A for a 5"), punch 80 A. Threshold 3.5 V.

| Pack | Sag at 30 A | Cruise alarm at rest voltage | Sag at 80 A | Punch alarm at rest voltage |
|---|---|---|---|---|
| fresh | 30 × 0.002 = 0.06 V/cell | 3.5 + 0.06 = 3.56 V | 80 × 0.002 = 0.16 V/cell | 3.66 V |
| 150 cycles | 30 × 0.006 = 0.18 V/cell | 3.68 V | 80 × 0.006 = 0.48 V/cell | 3.98 V |

At cruise, a fresh pack warns at a rest voltage of 3.56 V — as intended, but on a punch it already warns at 3.66 V, and the old one at 3.98 V, almost at the start of the flight. A 2 s delay filters out the punch: it is shorter, while a real discharge keeps the voltage below the threshold the whole time. Lowering the threshold cures the false alarm at the cost of the real one: an old pack with a 3.3 V threshold will warn at cruise at a rest voltage of 3.48 V. A pack on which the alarm comes early even with a delay should be retired from high-current craft (`el-battery-packs`: LiPo with IR of 10+ mΩ — for ground tasks).

**Setup order and verification.**
1. Thresholds — from the table by chemistry and class; for ArduPilot multiply by the number of cells.
2. Delay: Betaflight `vbat_duration_for_warning = 20`, ArduPilot `BATT_LOW_TIMER` (10 s per the documentation).
3. If the current sensor is calibrated — add an mAh threshold.
4. Fly until the warning and land immediately. Check: (a) the charger put back no more than 0.8 of capacity for LiPo (≤ 1040 mAh into a 1300 mAh pack) or 0.85 for Li-Ion; (b) the LiPo rest voltage is not below 3.5–3.6 V/cell (Oscar Liang: after landing the voltage should recover above 3.5–3.6 V).
5. The charger put back more — the threshold is late: raise the warning by 0.1 V or switch to mAh. It put back noticeably less, and the alarm came on a punch — increase the delay or replace the pack, but do not lower the threshold.
6. For long-range and heavy craft — the discharge curve of your own pack (`ops-case-studies`): from the log, plot the voltage under load at cruise current against the mAh consumed; the warning threshold is the voltage at the point “0.8 × capacity − return consumption”. Recalculate when you change the pack and when its IR has grown.

### Capacity and C rating: how to choose
**Two different currents.** Capacity is sized by the **average** current — how much energy the flight needs. The C rating and resistance are sized by the **peak** current — whether the pack will sag on a punch. For Li-Ion the S/P rule with the 0.6 factor does the same (`el-battery-packs`); here — LiPo.

1. **Capacity.** Q ≥ I_avg × t / (60 × fraction), Ah (t in minutes; fraction 0.8 for LiPo, 0.85 for Li-Ion). A heavier pack means more current: iterate in `f-components-choice`.
2. **The label C is a filter, not proof:** C_label × Q ≥ I_peak. Manufacturers do not publish how much lower the real C is than the label, and there is no sourced factor (Oscar Liang: C ratings are “often exaggerated”, take the numbers “with a grain of salt”). So the label only rules out obviously weak packs.
3. **Internal resistance decides.** The cell sag at peak ΔU = I_peak × R_cell. Course guideline — no more than 0.5 V/cell on a fresh pack: then a punch at the end of the flight, at a rest voltage of about 3.6 V (the landing point from the check above), leaves 3.6 − 0.5 = 3.1 V under load — above the rated limit of 3.0 V (Tattu). Hence **R_cell ≤ 0.5 / I_peak**. The 0.5 figure is the course's calculation from these two thresholds, not a datasheet value. Take IR from the charger (per cell) or from independent tests; after a hundred and fifty cycles it is several times higher.
4. **Heat at average current:** P = I_avg² × R_pack.

**Worked example: 5" 6S.** Average current 25 A, peak 100 A (the lower and upper ends of the ranges from the subsection “Calculating flight time honestly”), a 1300 mAh pack labeled 100C.

| Step | Calculation | Result |
|---|---|---|
| Time on 1300 mAh | 1.3 × 0.8 / 25 × 60 | 2.5 min |
| Capacity for 3 min | 25 × 3 / (60 × 0.8) | 1.56 Ah — the pack is heavier, the current will grow: recalculate per `f-components-choice` |
| Label for 1300 mAh | 100 / 1.3 | need C ≥ 77: “100C” (130 A) passes the filter |
| IR limit | 0.5 / 100 | R_cell ≤ 5 mΩ |
| Fresh pack, 2 mΩ/cell | 100 × 0.002 = 0.2 V/cell | at the end of the flight 3.6 − 0.2 = 3.4 V — fit for use |
| After 150 cycles, 6 mΩ/cell | 100 × 0.006 = 0.6 V/cell | 3.6 − 0.6 = 3.0 V — at the limit: the pack is for calm flights |
| Heat at 25 A, fresh | 25² × 0.012 | 7.5 W per pack |

**Check after the flight.** Find a punch in the log: the voltage before it U₁ at current I₁ and at the peak U₂ at I₂; R_pack = (U₁ − U₂) / (I₂ − I₁), per cell — divide by S. Compare with the charger's IR × S: noticeably higher — look for wire and connector resistance (`f-electricity-101`) or a cold pack. The per-cell minimum on peaks — not below 3.0 V; in the 10" case above it was 2.7 V — the pack is too small for those currents.

### Charging, storage, disposal
Balance charge at 1C (LiPo) / Li-Ion — at the standard current from the cell datasheet (Molicel P42A: 4.2 A = 1C, CC-CV to 4.2 V, charging at 0–45 °C), where there is no datasheet — 0.5C; to 4.2 V/cell (4.1 — longer service life: charge this way when you don't need the full capacity — practice near home, pack charged in advance; for a flight to the limit — 4.2, course guideline); storage at about 3.8 V/cell (LiPo; manufacturers' ranges — below) / 3.6–3.7 (Li-Ion), no longer than a day at full charge (course guideline); cell spread after charging ≤ 0.02 V, after a flight ≤ 0.05 — more = a weak cell; after charging and resting, from 0.03 V — watch it, more than 0.05 V — retire it (course guideline, as in `ops-maintenance`); per-cell IR in the charger as a “health certificate”; swelling/puncture — retire and dispose of it by the procedure in the next subsection (not salt water). In winter: LiPo below 10 °C loses up to 30–50% of its output — warm it to 20–25 °C before the flight (course guideline, as in `ops-weather`).

### LiPo disposal: discharge to zero through a load
A retired battery is dangerous as long as there is energy in it. The goal is to bring it to ~0 V and only then hand it in. Procedure:

1. **Location.** Outdoors, on a non-flammable surface (concrete, tiles, a bucket of sand), away from anything flammable, under supervision. The manufacturer MaxAmps puts it this way: “fire-safe, outdoor location”; in the Thunder Power instructions the battery is placed in a non-flammable container or a bucket of sand.
2. **Discharge with the charger as far as it allows.** Discharge mode usually stops at about 3.0 V/cell — that is not zero yet. Some chargers have a full-discharge mode (MaxAmps calls it Destroy).
3. **Resistive load down to ~0 V.** A resistor or a halogen bulb on the power connector. An LED bulb will not do: it goes out before the battery is empty. Current — about C/10 (Thunder Power guideline; for 2S–3S the same source gives a 150 Ω 2 W resistor, time — up to a day). Size your own resistor yourself: R = U / I, P = U × I. Example: 6S 1300 mAh at 22.8 V and C/10 = 0.13 A → R ≈ 175 Ω, P ≈ 3 W → take 180 Ω with margin, 5–10 W. The resistor gets hot: it also sits on a non-flammable surface.
4. **Check with a multimeter:** about 0 V on the power connector, and the voltage does not “grow back” after an hour without a load.
5. **Insulation and drop-off.** Tape over exposed terminals, put the battery in its own bag and take it to a battery or hazardous-waste collection point. The US EPA states directly: lithium batteries do not go in household trash or recycling bins; tape the terminals and/or put each battery in a separate bag. Collection rules in your country — on the website of your local waste service.

**Swollen or damaged battery.** Do not charge or use it (Gens Ace instructions: swollen, damaged and leaking cells are not to be used). Take it outdoors and watch it for at least 15 minutes: according to the Team Associated instructions, a damaged battery can catch fire even after 10 minutes. A swollen battery with an intact wrap is discharged the same way, at low current and from a distance. If the wrap is torn, or the battery is heating up, smoking or leaking — do not connect a load: isolate it outdoors in sand and hand it in as hazardous waste. Here the manufacturers' instructions differ (Thunder Power does not discharge such a battery at all), and the EPA advises contacting the manufacturer about damaged batteries.

**Never puncture, cut, disassemble or hit it.** Puncturing a charged cell is a short circuit inside it and a fire with toxic smoke.

**Why not salt water.** It is not a discharge but a slow current leak through the brine. The terminals corrode, and the current may stop while the battery is still charged — and you cannot see this from outside (Oscar Liang's review: “slow and ineffective”). The manufacturers who describe this method differ by two orders of magnitude: the Gens Ace instructions say 2 hours in a 1:20 solution, the Thunder Power instructions — at least 2 weeks. The conclusion is the same: whatever way the battery was discharged, the criterion is about 0 V on a multimeter, and only a load reliably gets you there.

### Charger and parallel charging
**Charger.** You need a balance charger: it sees every cell and does not let any of them go above 4.2 V (Gens Ace's limit is 4.22 V). Current: manufacturers allow up to 2C, but recommend 0.5–1C for service life (Gens Ace); that is why the course uses 1C everywhere. Charge at 10–45 °C (Gens Ace datasheet; another manufacturer's limit — in your pack's datasheet). Storage — 3.80–3.90 V/cell (Gens Ace), about 3.8 V/cell (Team Associated): the Storage mode on the charger. Work out the charger power in advance: P = U × I. One 6S 1300 mAh at 1C — 25.2 V × 1.3 A ≈ 33 W; six of them in parallel — 7.8 A and almost 200 W. If the charger is weaker, it will simply lower the current, and the charge will take more than an hour.

**Parallel charging** — several batteries on one board, and the charger sees them as one big battery. The power leads and the corresponding cells are connected directly, so at the moment of connection the batteries equalize with each other at a current limited only by their internal resistance: a 0.5 V difference per cell on 6S is 3 V across tens of milliohms, i.e. tens to hundreds of amps. Hence the rules:

- **The same number of cells** and the same chemistry. 4S and 6S on one board is a short circuit through the balance leads.
- **Voltages close: no more than ~0.1 V per cell** (CommonSense RC Paraboard instructions: “within 0.1V per cell”; Lumenier ParaGuard: difference within 0.1 V). Before connecting, check each battery with a cell checker; do not parallel-charge a battery with an “outlier” cell.
- **Connection order:** power connector first, then the balance connector (CommonSense RC, ProTek). The reverse order sends the equalizing current through the thin balance leads.
- **Charger settings:** cell count — as for one battery, capacity and current — by the sum of capacities (ProTek: two 3S 2200 mAh are one 3S 4400 mAh). Do not exceed the board's current: on simple boards it is a few amps (Paraboard — 5 A), ParaGuard — 40 A at the input.
- **A board with protection:** a fuse on every power port and resettable fuses on the balance pins (ParaGuard — a 10 A automotive fuse per port). A board without fuses does not forgive mistakes.
- **What parallel charging cannot do:** the charger sees the average of the corresponding cells, so it will not show a weak cell in one battery or its internal resistance. Old, crashed and “suspicious” batteries are charged one at a time. And, like any charging, — on a non-flammable surface and under supervision.

### BEC rails: the budget
5 V total: FC 0.2 + RX 0.2 + GPS 0.1 + LED 0.5 ≈ 1 A → the board's 5 V/2–3 A BEC is enough; add a Raspberry Pi (2–3 A) — not enough, a separate BEC. 9–12 V: a digital air unit 0.8–1.2 A → a 9 V/2 A BEC on the FC — 2 / 1.2 ≈ 1.7 × peak: the rule “rating ≥ 1.5 × the rail's peak” (`el-power-design`, course guideline) is met, but the margin is small if a camera is on the same rail or the FC board is heated by the ESC; then a separate 3 A BEC. All the numbers go into the build's spec sheet (the “Power circuit design” module).

{{diagram:flight-time-chain|An honest flight-time calculation: the usable fraction of capacity, the average current over the whole profile, corrections for conditions.}}

{{diagram:chart-discharge|Discharge curves: under load the cell sags by I·R, so LiPo at 40C hits 3.5 V sooner, and Li-Ion at 3C loses a noticeable part of its capacity before the cutoff. The curve shapes are typical, the resistances are from the module's examples.}}

### Place in the system

- **Receives:** average and peak current by mode (`f-mechanics`, `f-aero-props`); sag formulas and LiPo handling rules (`f-electricity-101`); consumer currents on the BEC rails (`el-power-design`).
- **Provides:** voltage under load — to the motors, ESC and BEC; flight time — to the requirements (`eng-method-101`); warning and landing thresholds — to the OSD and the battery failsafe (`bf-modes-osd`, `ap-safety-fs`).
- **If you get it wrong here:** the threshold is set by the no-load voltage or lowered “for an extra minute” → the warning comes when only seconds are left, as in the Alta X case (`ops-case-studies`). An old pack with grown resistance → on a punch the voltage drops below the BEC threshold, and the log cuts off without a disarm event (tree 6 in `diag-troubleshooting`).

## practice
### Safe LiPo handling
1. Charge at 1C, on a non-flammable surface, under supervision, with balancing.
2. Storage — about 3.8 V/cell (the Storage mode on the charger). A full battery left on a shelf for weeks degrades and swells.
3. A swollen, punctured battery or one with a damaged wrap is taken out of service and disposed of: discharge to ~0 V through a load outdoors, insulate the terminals, collection point (procedure — in the theory). Not salt water and not the trash can.
4. Transport — in a fireproof bag or box.
5. After a hard crash, set the battery aside and watch it before charging.

### Lab: calculate the flight time and compare with the log
1. Take the battery capacity and the average current from a Blackbox or DataFlash log.
2. Calculate the estimate: 0.8 × capacity, Ah / current × 60.
3. Compare with the real flight time until the voltage warning.
4. Find the minimum voltage under load in the log and convert it to per-cell.

**Reference for self-check.** Estimate: t ≈ 0.8 × capacity, Ah / average current × 60 (for Li-Ion the fraction is 0.85). A correct result: the formula uses the average current of the whole flight from the log, not the hover current; the minimum voltage is divided by the number of cells and explained by the I·R sag — for comparison, a fresh 6S 1300 mAh at 80 A loses about 1 V (4.0 → 3.84 V/cell), the same pack after 150 cycles — 2.9 V. Common wrong results: the real time until the warning is noticeably shorter than the estimate at the same average current — the pack has aged, and the warning triggers on sag rather than on capacity; a per-cell minimum of about 2.7 V on peaks, as in the 10" case, — the battery is working at its limit, and the cure is a different pack or flight profile, not a lower warning threshold.

### Setting up voltage monitoring
In Betaflight, check the voltage and current sensor scale (Power & Battery) against a multimeter (the `vbat_scale` and `ibata_scale` formulas — `el-measure`): voltage — against a multimeter at the battery connector, current — against the mAh the charger put back (±10 %, subsection “Calculating flight time honestly”). Thresholds — from the “Per-cell thresholds” table for your chemistry and class, with a delay: for LiPo 4–6S `set vbat_warning_cell_voltage = 350`, `set vbat_min_cell_voltage = 330`, `set vbat_duration_for_warning = 20`. Verification — step 4 of the setup order: after landing on the warning, the charger put back no more than 0.8 of capacity, and the rest voltage is not below 3.5–3.6 V/cell.

## diagnostics
- **Symptom:** a low-voltage warning on every punch
  - Possible cause: sag under current, an old battery with high internal resistance.
  - What to do: look at the rest voltage after the flight, measure the internal resistance with the charger.
- **Symptom:** flight time much shorter than calculated
  - Possible cause: the average current is higher than it seemed, or the battery has lost capacity.
  - What to do: take the average current from the log, check the capacity with a charge cycle.
- **Symptom:** the VTX or camera reboots on throttle
  - Possible cause: sag on the BEC rail or power from the wrong pad.
  - What to do: check the power pad, add a capacitor on the power bus, check the BEC current.
- **Symptom:** the battery is warm and swollen after the flight
  - Possible cause: current overload.
  - What to do: take the battery out of service, reconsider capacity/C for the real current.
- **Symptom:** a spark and hot wires when connecting a battery to a parallel board
  - Possible cause: different voltages or a different number of cells among the batteries on the board.
  - In the log/on the instrument: the cell checker shows a difference of more than 0.1 V per cell.
  - What to do: disconnect, check each battery with a cell checker, equalize them one at a time in Storage mode, replace the board's blown fuses.
- **Symptom:** a retired battery shows voltage again after “discharging”
  - Possible cause: the discharge was stopped too early (charger to 3.0 V/cell, an LED bulb, salt water).
  - What to do: a resistive load down to ~0 V, check with a multimeter after an hour without a load.

## references
- Betaflight App — tabs reference (Power & Battery) | https://betaflight.com/docs/wiki/app | primary | A
- Battery Monitors — ArduPilot Copter | https://ardupilot.org/copter/docs/common-powermodule-landingpage.html | primary | A
- LiPo Battery Guide — Oscar Liang (landing at about 3.5–3.6 V/cell in flight, recovery after landing, C ratings inflated; accessed 2026-11-22) | https://oscarliang.com/lipo-battery-guide/ | secondary | B
- LiHV Battery — Oscar Liang (charge to 4.35 V/cell, lower thresholds as for LiPo; accessed 2026-11-22) | https://oscarliang.com/lihv-battery | secondary | B
- Tattu (Grepow) — Important safety instructions (not below 3.0 V/cell under load, 3.5 V/cell cutoff for UAVs, 4.2 V/cell maximum; accessed 2026-11-22) | https://www.genstattu.com/content/Ordinary.pdf | primary | B
- Gens Ace — LiPo Battery Charging/Discharging & Safety Information (automatic cutoff 3.0 V/cell; accessed 2026-11-22) | https://gensace.de/news/lipo-battery-charging-discharging-safety-info | primary | B
- Molicel INR21700-P42A datasheet V4 (cutoff 2.5 V, 45 A continuous; standard charge 4.2 A CC-CV to 4.2 V, charging at 0–45 °C; accessed 2026-11-27) | https://www.rcscomponents.kiev.ua/datasheets/INR21700P42A-V4-80092.pdf | primary | A
- Battery Failsafe — ArduPilot Copter (`BATT_LOW_VOLT` 10.5 V by default, `BATT_LOW_MAH` about 20 % of capacity, RTL recommended) | https://ardupilot.org/copter/docs/failsafe-battery.html | primary | A
- Betaflight 2025.12.5 — source `sensors/battery.c`, `sensors/battery.h` (threshold defaults, delays, mAh alarm) | https://github.com/betaflight/betaflight | primary | A
- MaxAmps — A Proper Goodbye: Disposing of your LiPo Battery (discharge to 0 V, insulation, drop-off; accessed 2026-11-17) | https://maxamps.com/blogs/news/a-proper-goodbye-disposing-of-your-lipo-battery | primary | B
- US EPA — Used Lithium-Ion Batteries (not in household trash, insulate the terminals; accessed 2026-11-17) | https://www.epa.gov/recycle/used-lithium-ion-batteries | primary | A
- Gens Ace — LiPo safety manual (charge current, 4.22 V, storage 3.80–3.90 V; accessed 2026-11-17) | https://www.freeflysystems.com/wp-content/uploads/2021/11/Gensace_safety_manual.pdf | primary | B
- Team Associated — LiPo Safety Instructions and Warnings (2C maximum, observe for 15 minutes, do not puncture; accessed 2026-11-17) | https://img2.associatedelectrics.com/pdf/cars_and_trucks/shared/LiPo-Safety-Instructions-and-Warnings.pdf | primary | B
- CommonSense RC — Paraboard instructions (parallel charging: 0.1 V per cell, connection order; accessed 2026-11-17) | https://www.commonsenserc.com/product_instructions/PRBRD-JST_instructions.pdf | primary | B
- ProTek RC — Parallel Charge Board manual (same cell count, total capacity; accessed 2026-11-17) | https://images.amain.com/images/manuals/ProTekParallelChargeBoard.pdf | primary | B
- Lumenier ParaGuard — description of the fused board (accessed 2026-11-17) | https://www.getfpv.com/lumenier-paraguard-safe-parallel-charging-board-xt-30-4-port.html | primary | B
- Thunder Power — Disposal of old/damaged LiPo batteries, reprinted on DIY Drones (C/10, 150 Ω 2 W resistor; accessed 2026-11-17) | https://diydrones.com/profiles/blogs/disposal-of-lipo-batteries | secondary | B
- How to Safely Dispose LiPo Batteries — Oscar Liang (why not salt water; accessed 2026-11-17) | https://oscarliang.com/dispose-lipo-battery-safely | secondary | B

## checklist
- I understand the difference between S, P, mAh and C
- I know when to choose Li-Ion and when LiPo
- I calculated the flight time and compared it with the log
- I checked the voltage sensor scale with a multimeter
- The warning and landing thresholds are taken from the table by chemistry and class, with a delay; after landing the charger put back no more than 0.8 of capacity
- The pack is chosen by the average current (capacity) and by the peak (R_cell ≤ 0.5 / I_peak), not by the label C
- Batteries are stored at storage voltage and in a fireproof container
- Before parallel charging I check the cell counts and voltages (no more than 0.1 V per cell)
- I know how to dispose of a retired battery: load down to ~0 V, insulation, collection point
