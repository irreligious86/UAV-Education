---
id: link-vtx
title: "VTX Tables and Changing the Video Channel"
level: L2
readingTime: 20 min
firmware: Betaflight 4.5+
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
source_hash: 42e8a5661265
---

## summary
The video transmitter (VTX) is controlled by the flight controller: Betaflight knows which frequencies and power levels the VTX has from the VTX table. This module explains how the table is built, how FACTORY and CUSTOM modes differ, and gives you a procedure for changing channels when yours is taken — for example, by a crashed drone that keeps broadcasting until the end of the shift.

## theory
### Why a table
VTX control protocols (SmartAudio, IRC Tramp, MSP) send either a band/channel number or a frequency. So that the OSD and the radio show the right values, Betaflight stores a table: a list of bands, 8 channels each, and a list of power levels.

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

Fields of a band line: number, name, letter, mode, eight frequencies. A frequency of `0` blocks the channel.

### FACTORY vs CUSTOM
- FACTORY: Betaflight sends the VTX a band and channel number, and the VTX uses its built-in table. The frequencies in the FC table are for display only — which is why they must match the VTX's real table.
- CUSTOM: Betaflight sends the frequency itself. You can set any frequencies within the VTX's capabilities. IRC Tramp and RTC6705 work only in CUSTOM.

### Two ways to write the same channel
A channel is written as letter+number (R1, F4, E5) or as a band-channel pair (5-1). They are the same thing if your table matches the table of whoever gave you that channel. On non-standard VTXs the band letters and numbers may not match the usual ones — compare by frequency in MHz, not by letter.

### Frequencies and the law
Tables from the internet often contain frequencies you aren't allowed to transmit on. The Betaflight documentation warns you outright: almost nobody can legally use a stock table without editing it. The allowed range and power are set by local regulations.

### Channel physics: frequencies, bandwidth, spacing
5.8 GHz analog video occupies ~20–27 MHz of bandwidth around the carrier (with audio subcarriers up to ±6.5 MHz); channels in the tables are spaced 17–37 MHz apart, so adjacent channels of the same band **overlap**. Practice at the field: 4–6 vehicles fly at once without interference with spacing ≥ 37–40 MHz (the classic set R1, R3, R5, R7 or R2, R4, R6, R8 on Raceband with 37 MHz steps); 8 vehicles only with planning across the whole grid and reduced power. Digital systems (DJI O3/O4, Walksnail, HDZero) occupy 20–40 MHz and have their own channel grid and limits on the number of simultaneous systems (usually 8 for Walksnail/HDZero, fewer for DJI on wide channels).

### Power: what actually changes
Doubling power = +3 dB = ×1.41 (√2) in free-space range (the “Link Budget” module); 25 → 800 mW = +15 dB ≈ ×5.6 in range — but an 800 mW+ VTX heats up (without airflow on the ground — thermal protection and picture degradation), jams your neighbors, and for video the range is usually limited by the **receiving** side (patch/helix on the ground, sensitivity). Pit mode (0.1–1 mW) for powering up at the field is mandatory when flying with a team; `vtx_low_power_disarm` in Betaflight lowers power on the ground automatically.

### Control protocols and their gotchas
- **SmartAudio** (TBS, versions 1/2/2.1): a single wire from an FC TX pin → VTX, 4800 baud, no inversion needed, but some VTXs need a pull-up (Betaflight always sends 2 stop bits); versions break compatibility — in the CLI `vtx_info` shows what the VTX replied.
- **IRC Tramp**: also a single wire, its own commands, always CUSTOM frequencies.
- **MSP** (digital systems over MSP DisplayPort): VTX settings go over the same UART as the OSD; the table is built from what the air unit reports.
Check: CLI `get vtx` → `vtx_band/channel/power/freq`; `vtx_info` → what the device reported; `vtxtable` → the table.

### Worked example: four vehicles at the field
Analog, Raceband (37 MHz step: R1 5658 … R8 5917), 200 mW power. Four vehicles — R1, R3, R5, R7: at least 74 MHz between any two, no interference. A fifth one asks for the “free” F2 (5760): it sits between R3 (5732) and R5 (5806) with 28 and 46 MHz of spacing — R3 will get interference. The right options: put the fifth on a digital system (different modulation, but it still occupies bandwidth — its channel goes into the table too), or switch to a 6-channel grid with 37 MHz steps at ≤ 100 mW and spread the pilots across the field — tight, but it works. The wrong option is “I'll switch to whatever isn't taken in the OSD”: the field's table of occupied frequencies (the “Field Operations” module) is kept before anyone powers up.

{{diagram:vtx-four-pilots|Worked example: four analog vehicles on R1/R3/R5/R7 with 74 MHz spacing; the “free” F2 interferes with R3.}}

## practice
### Procedure for changing channels when yours is taken
1. Find out which frequencies are taken: your neighbors, other pilots at the field, a “broadcasting” crashed drone.
2. Convert all taken channels to MHz using their VTX's table — not by letter.
3. Pick a free frequency with the largest possible spacing from your neighbors. A guideline for analog is at least ~37 MHz, like between adjacent Raceband channels: closer channels noticeably interfere with each other.
4. Find that frequency in your table and write down the band and channel.
5. Change it on one or two transmitters/drones first, check the picture and interference with neighbors.
6. Only after a successful test — on all the other drones.

### Changing it via the CLI
```
get vtx
set vtx_band = 4
set vtx_channel = 1
save
```

Switch the video receiver (goggles, ground station) to the same frequency. For digital systems (Walksnail, DJI, HDZero) the channel is changed in their menu; the selection logic is the same.

### Verification
1. The new frequency is visible in the OSD or in the goggles.
2. Neighbors confirm there is no interference.
3. Record the new frequency in the drone's log and in the shared channel allocation table.

## diagnostics
- **Symptom:** the OSD shows one frequency, but the goggles get the picture on another
  - Possible cause: FACTORY mode, and the FC table doesn't match the VTX's built-in table.
  - What to do: load the table made specifically for your VTX model and your region.
- **Symptom:** the VTX doesn't respond to channel changes from Betaflight
  - Possible cause: the UART isn't configured for SmartAudio/Tramp, or there is no table.
  - What to do: check Ports (VTX on the right UART) and that a `vtxtable` exists.
- **Symptom:** a neighbor gets interference after the channel change
  - Possible cause: frequency spacing too small, or harmonics at high power.
  - What to do: increase the spacing, lower power on the ground (pit mode).
- **Symptom:** channel “E5” is a different frequency for you and your neighbor
  - Possible cause: the VTXs have different band tables.
  - What to do: agree on frequencies in MHz.
- **Symptom:** the VTX won't change channels from the OSD
  - Possible cause: the protocol isn't responding (SmartAudio version/wiring), the VTX is locked (pit/lock).
  - What to do: CLI `vtx_info` — is there a response from the device; wiring to the TX pin; unlock it following the VTX's instructions.
- **Symptom:** one pilot's picture gets “snowy” when a second one takes off
  - Possible cause: adjacent channels with overlapping bandwidth, or too much power.
  - What to do: spacing ≥ 37 MHz, the minimum sufficient power, a field frequency table.

## references
- VTX — Betaflight Development Docs | https://betaflight.com/docs/wiki/guides/current/VTX | primary | A
- VTX Tables — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/VTX-Tables | primary | A
- How to Setup VTX Table in Betaflight — Oscar Liang | https://oscarliang.com/smartaudio-tramp-vtx-control-vtxtables/ | secondary | B

## checklist
- The table is loaded specifically for my VTX model and region
- Taken channels are converted to MHz
- Spacing from neighbors is at least ~37 MHz (Raceband guideline)
- The new channel is tested on 1–2 drones before changing all of them
- The frequency is recorded in the log and the shared channel table
