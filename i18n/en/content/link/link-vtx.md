---
id: link-vtx
title: "VTX tables and changing the video channel"
level: L2
readingTime: 20 min
firmware: Betaflight 2025.12 (checked against 2025.12.5)
status: published
added: 2026-11-07
tags:
  - VTX
  - vtxtable
related:
  - link-elrs
  - bf-modes-osd
next: []
source: content/link/link-vtx.md
source_hash: e4ec3a594414
---

## summary
The flight controller controls the video transmitter (VTX): Betaflight learns which frequencies and power levels the VTX has from the VTX table. This module explains how the table is built, how FACTORY and CUSTOM modes differ, and gives a procedure for changing channel when yours is taken, for example by a crashed aircraft that keeps transmitting until the end of the session.

## theory
### Why a table
VTX control protocols (SmartAudio, IRC Tramp, MSP) send either a band/channel number or a frequency. So that the OSD and the radio show the right values, Betaflight keeps a table: a list of bands, 8 channels in each, and a list of power levels.

### Syntax
```
vtxtable bands 5
vtxtable channels 8
vtxtable band 1 BOSCAM_A A FACTORY 5865 5845 5825 5805 5785 5765 5745 5725
vtxtable band 5 RACEBAND R FACTORY 5658 5695 5732 5769 5806 5843 5880 5917
vtxtable powerlevels 3
vtxtable powervalues 14 20 26
vtxtable powerlabels 25 100 400
```

Fields of a band line: number, name, letter, mode, eight frequencies. A frequency of `0` blocks that channel.

### FACTORY versus CUSTOM
- FACTORY: Betaflight sends the VTX the band and channel number, and the VTX uses its built-in table. The frequencies in the FC table are for display only, which is why they must match the VTX's real table.
- CUSTOM: Betaflight sends the frequency itself. You can set any frequencies within the VTX's capabilities. IRC Tramp and RTC6705 work only in CUSTOM.
- What to choose: the table from your VTX's manufacturer, in the mode it comes in; if there is no table, CUSTOM, because then the frequency in the OSD always equals the real one (FACTORY with someone else's table shows one channel and transmits on another; see the error below). Check with a frequency counter or the goggles' scanner on the ground.

### Two ways to write one channel
A channel is written as letter + number (R1, F4, E5) or as a band-channel pair (5-1). They mean the same thing if your table matches the table of whoever named the channel. On non-standard VTXs the band letters and numbers may differ from the usual ones: compare by frequency in MHz, not by letter.

### Frequencies and the law
Tables from the internet often contain frequencies you may not transmit on. The Betaflight documentation warns plainly that almost no one can legally use the typical table without editing it. The permitted band and power are set by local rules.

### Channel physics: frequencies, bandwidth, spacing
Analog 5.8 GHz video occupies a bandwidth of ~20–27 MHz around the carrier (with audio subcarriers up to ±6.5 MHz); channels in the tables are spaced 19–37 MHz apart, so neighboring channels of one band **overlap**. Field practice: 4–6 aircraft work at once without interference with a spacing of ≥ 37–40 MHz (the classic set R1, R3, R5, R7 or R2, R4, R6, R8 on Raceband with its 37 MHz step); with 8 aircraft, only with planning across the whole grid and reduced power. Digital systems (DJI O3/O4, Walksnail, HDZero) occupy 10–60 MHz (DJI O4 up to 60 MHz with Goggles 3/N3) and have their own channel grid and limits on the number of simultaneous systems (usually 8 for Walksnail/HDZero, fewer for DJI on wide channels). Spacing alone is not enough: two transmitters on f₁ and f₂ produce third-order intermodulation products at 2f₁ − f₂ and 2f₂ − f₁. They sit one pair-spacing away from the pair, and on an evenly spaced grid they land exactly on the next channel of that grid: a third pilot can get interference even though all three channels are spaced far enough apart.

### Power: what really changes
Doubling the power = +3 dB = ×1.41 (√2) in free-space range (the "Radio link budget and range" module); 25 → 800 mW = +15 dB ≈ ×5.6 in range. But an 800 mW+ VTX runs hot (without airflow on the ground: thermal protection and a degraded picture), jams neighbors, and video range is usually limited by the **receiving** side (patch/helix on the ground, sensitivity; antenna types on the aircraft and the goggles by task are in `rf-antennas`, "Polarization"). How to find the "minimum sufficient" power: the upper limit is your country's permitted EIRP (`f-regulations`; EIRP = power + antenna gain, `rf-link-budget`); within it, a link budget for your range with margin (`rf-link-budget`), then a field test: at the farthest and most obstructed point of the route the picture has no dropouts, and one step lower it does. A starting point indoors is 25 mW (`f-micro-whoop`). Pit mode (0.1–1 mW) for powering up at the field is mandatory in team work; `vtx_low_power_disarm` in Betaflight lowers the power on the ground automatically.

### Power, pit mode and VTX on a switch in Betaflight 2025.12
The `vtx_*` variables, the `vtx` command and the `io/vtx.c` logic in 2025.12 are the same as in 4.5.

- **`vtx_power`** is not milliwatts but the **level number** in `vtxtable powerlevels`, starting at 1: in the table above 1 = 25 mW, 2 = 100, 3 = 400 (`powerlabels` are only OSD labels). 0 means "not set". The CLI range is 0–7; the firmware will not send a level higher than the table's level count (`vtxCommonSetPowerByIndex()`, `drivers/vtx_common.c`). So `set vtx_power = 3` on another VTX with another table is a different power.
- **`vtx_low_power_disarm`**: OFF (the default); ON sends level 1 while disarmed; UNTIL_FIRST_ARM sends level 1 only until the first arm after power-up, and after landing the power stays at flight level. While failsafe is active the power is not lowered (`vtxGetSettings()`, `io/vtx.c`): an aircraft that came down after a DROP keeps transmitting and can be found by its picture (bf-failsafe). **What to choose** (a course rule). UNTIL_FIRST_ARM is the course's recommendation for flying at the field (the firmware default is OFF): on the bench after power-up the VTX does not overheat or jam neighbors, and after the first arm the power stays at flight level even on a disarm without failsafe (a switch disarm after a crash, crash recovery, a landing in grass), so the aircraft can be found by its picture (`ops-field`). ON when not bothering others matters more than finding the aircraft: group flying, an aircraft often sitting disarmed with the VTX on; the price is that after a crash with a disarm without failsafe the VTX drops to level 1 (25 mW in the table above), and the picture from the field is harder to catch. OFF only if you lower the ground power yourself (pit mode on a switch). Check: after arming and disarming with props off, `get vtx` and the goggles' RSSI show the expected level.
- **The VTX PIT MODE mode** (id 39, Modes tab): the switch turns the VTX's pit mode on and off, but the change is processed **only while disarmed**; in flight the switch does nothing (`vtxProcessPitMode()`). For protocols that take a direct frequency you can set `vtx_pit_mode_freq`: then instead of pit mode the VTX moves to that frequency at power level 1. SmartAudio before 2.1 cannot enter pit mode by software.
- **The firmware sends band and channel to the VTX only while disarmed** (`vtxProcessBandAndChannel()`). After the first arm, `vtx` slots and the band/channel stick commands are blocked until a reboot (`locked` in `io/vtx_control.c`); slots can still change the power in flight. The VTX CONTROL DISABLE mode (id 48) stops the FC from controlling the VTX over SmartAudio and Tramp (`io/vtx_smartaudio.c`, `io/vtx_tramp.c`).
- **VTX on a switch**: the `vtx` command (Video Transmitter tab): `vtx <index> <aux_channel> <vtx_band> <vtx_channel> <vtx_power> <start_range> <end_range>`, 10 slots, 0 = "do not change". A typical use is 25 mW with the switch down and flight power with it up. The slot evaluation order and the traps (overlapping ranges, band locking) are in bf-adjustments.
- With the sticks while disarmed: throttle up + yaw left + roll right/left is band +/−, throttle up + yaw right + roll right/left is channel +/− (bf-modes-osd).

### Control protocols and their pitfalls
- **SmartAudio** (TBS, versions 1/2/2.1): one wire from an FC TX pin → VTX, 4800 baud, no inversion needed, but some VTXs need a pull-up (Betaflight always sends 2 stop bits); the versions break compatibility, and in the CLI `vtx_info` lists the power levels the device reported.
- **IRC Tramp**: also one wire, its own commands, always CUSTOM frequencies.
- **MSP** (digital systems over MSP DisplayPort): VTX settings travel over the same UART as the OSD; the table is built from what the air unit reports.
Check: CLI `get vtx` → `vtx_band/channel/power/freq`; `vtx_info` → what the device reported; `vtxtable` → the table.

### VTX in INAV 9.1: what differs from the above
Everything said about `vtxtable` does not apply to INAV: there is no such command, and the bands (1 A, 2 B, 3 E, 4 F, 5 Race) and channels 1–8 are built into the firmware (`settings.yaml`, `drivers/vtx_common.h` 9.1.0). The rule for turning "I want N mW" into a setting:
1. The VTX is connected to a UART with the SmartAudio (2048) or Tramp (4096) function, or over MSP together with the OSD (`inav-osd-hd`); `vtx_halfduplex` = ON means one TX wire.
2. `vtx_power` (default 1, 0–8) is a **level number**; the milliwatts depend on the transmitter: on a 600 mW Tramp VTX levels 1–5 = 25, 100, 200, 400, 600 mW (`io/vtx_tramp.c`); on SmartAudio, whatever the VTX reported about itself. If the VTX reports its maximum wrongly, use `vtx_max_power_override` (mW, 0 = trust the VTX).
3. `vtx_low_power_disarm`: OFF (the default), ON = level 1 while disarmed, UNTIL_FIRST_ARM = level 1 only until the first arm; during failsafe the power is not lowered, just as in Betaflight (`io/vtx.c`).
4. `vtx_frequency_group` = FREQUENCYGROUP_5G8 (also 2G4, 1G3) selects which frequency tables to use.
5. In flight: `adjrange` function 53 steps through the levels (`inav-adjustments`); logic conditions use operations 25 (power level), 30 (band), 31 (channel); a "power by distance" example is in `inav-ipf`. INAV has no VTX PIT MODE mode and no `vtx` command with slots like Betaflight: the `vtx_pit_mode_chan` setting is in the list, but turning pit mode on is disabled in the code of `io/vtx.c` 9.1.0.

Check: `get vtx_power` and the power label in the OSD or the VTX menu match your transmitter's table; on the bench with ON the power is 25 mW (level 1), after arming it is the selected one.

{{diagram:vtx-power-index-map|The same line set vtx_power = 3 gives 400, 500 or 200 mW depending on the transmitter's table, and the module's table has no level 4 at all.}}

### Worked example: four aircraft at the field
Analog, Raceband (37 MHz step: R1 5658 … R8 5917), 200 mW. Four aircraft on R1, R3, R5, R7: at least 74 MHz between any two, the bands do not overlap, so spacing causes no interference. Intermodulation remains: the grid is even, and the product of R1 and R3 (2·5732 − 5658 = 5806) lands exactly on R5; in total four products land on occupied channels (lab, item 3). So "different channels with wide spacing" is not yet a guarantee of a clean picture for the third pilot; hence 200 mW, not the maximum, and pilots spread out across the field. A fifth pilot asks for the "free" F2 (5760): it sits between R3 (5732) and R5 (5806) with spacings of 28 and 46 MHz, so R3 will get interference. The right options: put the fifth on a digital system (a different modulation, but it still occupies bandwidth, so its channel goes into the table too), or switch to a 6-channel grid with a 37 MHz step at ≤ 100 mW with the pilots spread across the field: tight, but it works. The wrong option is "I'll switch to whatever is not taken in the OSD": the field's table of occupied frequencies (the "Field operations" module) is kept before anyone powers up.

{{diagram:vtx-four-pilots|Worked example: four analog aircraft on R1/R3/R5/R7 spaced 74 MHz apart; the "free" F2 interferes with R3.}}

### Where it fits in the system

- **Takes in:** a UART and a control protocol, SmartAudio, Tramp or MSP (`bf-ports`); the arm and failsafe state for choosing the power (`bf-failsafe`); `vtx` slots from a switch (`bf-adjustments`); the field's table of occupied channels (`ops-field`).
- **Puts out:** the channel and power into the air, and their values to the OSD (`bf-modes-osd`); the power level, to the video range (`rf-link-budget`); radiation that the GPS module is mounted away from (`bf-gps-setup`).
- **If you get this wrong:** the FACTORY table frequencies do not match the VTX's own table → the OSD shows one channel, the transmitter works on another and interferes with a neighbor; sorted out by comparing in MHz and with the field's table (`ops-field`). You carried `set vtx_power = 3` over to a VTX with a different table → that is a different power: overheating on the ground or not enough range (`rf-link-budget`).

## practice
### Procedure for changing channel when yours is taken
1. Find out which frequencies are taken: your neighbors, other pilots at the field, a crashed aircraft still "transmitting".
2. Convert every taken channel to MHz using the table of its VTX, not by letter.
3. Pick a free frequency with the largest possible spacing from the neighbors. A guideline for analog: no less than ~37 MHz, as between neighboring Raceband channels; closer channels interfere noticeably.
4. Find that frequency in your table and write down the band and channel.
5. Change it on one or two transmitters/drones first, check the picture and interference to neighbors.
6. Only after a successful test, on all the other aircraft.

### Changing it in the CLI
```
get vtx
set vtx_band = 4
set vtx_channel = 1
set vtx_power = 1
set vtx_low_power_disarm = ON
save
```

`ON` in the example is for group flying; alone at the field, `UNTIL_FIRST_ARM` (the rule is in the theory). Switch the video receiver (goggles, ground station) to the same frequency. For digital systems (Walksnail, DJI, HDZero) the channel is changed in their menu; the selection logic is the same.

### Check
1. The OSD or the goggles show the new frequency.
2. The neighbors confirm there is no interference.
3. Write the new frequency in the drone's log and in the shared channel allocation table.

### Exercise without hardware: power and a frequency plan
No transmitter needed, only the tables from the theory.

**1. Power.** In the `vtxtable` from the "Syntax" section, the line `powervalues 14 20 26` sets the levels in dBm and `powerlabels 25 100 400` the labels in mW. Check the labels by converting: mW = 10 to the power (dBm / 10); the rule from the "Radio link budget and range" module is 0 dBm = 1 mW, 20 dBm = 100 mW. Then answer: what power does `set vtx_power = 2` set; what happens with `set vtx_power = 4` and this table; what the power becomes with `set vtx_power = 3` if the config is moved to another VTX with the table `powervalues 14 23 27 29` and `powerlabels 25 200 500 800` (a teaching example, assembled by hand); by how many dB and by what factor in range 25 and 100 mW differ, and 25 and 400 mW.

**2. The fifth pilot.** R1, R3, R5 and R7 are taken at the field (the worked example). The fifth pilot is offered R2, R8, A2, A6 and F2 (5760 MHz). For each candidate, find its frequency from the tables and the spacing to the two nearest taken channels; pick a channel by the rule "no less than 37 MHz to every neighbor, and the fewer such neighbors, the better".

**3. Intermodulation.** For the taken R1, R3, R5, R7, compute all the 2f₁ − f₂ products over ordered pairs (there are 12) and list the ones that land on a taken channel. Then check the channel chosen in item 2: does anyone's product land on it, and do its products with the nearest neighbor land on a taken channel?

**4. The crashed aircraft.** The aircraft on R5 crashed and its failsafe triggered; the config has `vtx_low_power_disarm = ON`. At what power does it transmit, and can you put it into pit mode remotely with the VTX PIT MODE switch while it is armed?

Self-check: the lab is done when:
- item 1: 14 dBm = 25.1 mW, 20 dBm = 100 mW, 26 dBm = 398 mW; `vtx_power = 2` is 100 mW; with three levels the firmware will not send level 4; on the other VTX level 3 is 27 dBm = 501 mW instead of 400; 25 → 100 mW is +6 dB and ×2 in range, 25 → 400 mW is +12 dB and ×4;
- item 2: R2 is 5695 MHz, spacing 37 and 37; R8 is 5917, spacing 37 and 111; A2 is 5845, 35 and 39; A6 is 5765, 33 and 41; F2 is 5760, 28 and 46; R8 is chosen;
- item 3: of the 12 products, four land on taken channels: 5806 (R5), 5658 (R1), 5880 (R7) and 5732 (R3); none lands on 5917; the products of the R7–R8 pair are 5843 (R6, free) and 5954 (outside the table);
- item 4: at flight power; with the switch while armed, you cannot;
- on hardware (if you have it): the OSD or the goggles show the frequency from your plan, and `get vtx` shows the same band, channel and power level as written in the log.

**Reference answer for self-check.** The hits in item 3: 2·5732 − 5658 = 5806; 2·5732 − 5806 = 5658; 2·5806 − 5732 = 5880; 2·5806 − 5880 = 5732. An even grid with a 74 MHz step puts the product of each neighboring pair onto the next taken channel. This is the same picture as in the worked example: by spacing (74 MHz, the bands do not overlap) the R1/R3/R5/R7 set is clean, but by intermodulation it is not, and that is exactly why even with it the power is kept at the minimum sufficient level and the pilots are spread across the field. If you got "no hits", you computed products only for pairs one channel apart (R1–R5, R3–R7) or mixed up the R-channel frequencies. In item 2, R2 passes the 37 MHz threshold but is squeezed from both sides; R8 has one neighbor at 37 MHz and the next at 111. In item 4: while failsafe is active the power is not lowered, and the pit mode switch is processed only while disarmed, so channel R5 stays occupied at full power until the aircraft is found or the battery dies. Common wrong answers: "F2 is free, it is not in the taken list": it is only 28 MHz from R3, the error from the worked example; `vtx_power = 3` taken as "400 mW on any VTX": it is a level number in the table, not milliwatts; 26 dBm converted as 260 or 2600 mW: every +10 dBm gives ×10, not +10; in item 3 only 6 pairs counted: each pair gives two products, 2f₁ − f₂ and 2f₂ − f₁.

## diagnostics
- **Symptom:** the OSD shows one frequency, the goggles get the picture on another
  - Possible cause: FACTORY mode, and the FC table does not match the VTX's built-in table.
  - What to do: load the table made for your VTX model and your region.
- **Symptom:** the VTX does not respond to a channel change from Betaflight
  - Possible cause: the UART is not set up for SmartAudio/Tramp, or there is no table.
  - What to do: check Ports (VTX on the right UART) and that a `vtxtable` exists.
- **Symptom:** after a channel change a neighbor gets interference
  - Possible cause: too little frequency spacing, or harmonics at high power.
  - What to do: increase the spacing, lower the power on the ground (pit mode).
- **Symptom:** channel "E5" is a different frequency for you and for your neighbor
  - Possible cause: the VTXs have different band tables.
  - What to do: agree on frequencies in MHz.
- **Symptom:** the VTX does not change channel from the OSD
  - Possible cause: the protocol does not answer (SmartAudio version/wiring), the VTX is locked (pit/lock).
  - What to do: CLI `vtx_info` to see whether the device answers; wiring to a TX pin; unlock per the VTX's instructions.
- **Symptom:** one pilot's picture gets "snowy" when a second one takes off
  - Possible cause: neighboring channels with overlapping bandwidth, or too much power.
  - What to do: spacing ≥ 37 MHz, the minimum sufficient power, the field's table.

## references
- VTX — Betaflight Development Docs | https://betaflight.com/docs/wiki/guides/current/VTX | primary | A
- VTX Tables — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/VTX-Tables | primary | A
- How to Setup VTX Table in Betaflight — Oscar Liang | https://oscarliang.com/smartaudio-tramp-vtx-control-vtxtables/ | secondary | B
- 5.8GHz FPV Channels & Frequency Chart (IMD: 2 × f1 − f2, example F2/F4/F6) — Oscar Liang | https://oscarliang.com/fpv-channels/ | secondary | B

## checklist
- The table is loaded for your own VTX model and region
- Taken channels are converted to MHz
- Spacing to neighbors is no less than ~37 MHz (the Raceband guideline)
- The new channel is checked on 1–2 aircraft before changing them all
- The frequency is written in the log and in the shared channel table
