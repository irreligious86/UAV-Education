---
id: rf-link-budget
title: "Radio link budget and range"
level: L2
readingTime: 30 min
firmware: any firmware
status: published
added: 2026-11-08
tags:
  - link budget
  - range
  - RSSI
  - dB
related:
  - rf-antennas
  - link-elrs
  - link-vtx
next:
  - el-wiring
source: content/electronics/rf-link-budget.md
source_hash: af1b0ba8b7a6
---

## summary
“Will it make 10 km?” is a question of arithmetic, not faith. A link budget is a sum in decibels: transmitter power + antenna gains − cable losses − free-space attenuation must be above the receiver sensitivity, with a margin for fading. This module teaches you to calculate it for RC and video, turn the margin into an expected range, set the RSSI warning threshold and compare the calculation with a field test — and shows why 900 MHz goes farther than 2.4 GHz at the same power, and why 5.8 GHz video is the weak link.

## theory
### Decibels in five minutes
dB is a logarithmic measure of a ratio: 3 dB ≈ ×2 in power, 10 dB = ×10, 20 dB = ×100. dBm is power relative to 1 mW: 0 dBm = 1 mW, 20 dBm = 100 mW, 27 dBm = 500 mW, 30 dBm = 1 W. **Doubling the transmitter power gives +3 dB — the same as a slightly better antenna.** Doubling the range costs 6 dB (see below).

### Free-space path loss (FSPL)
FSPL(dB) = 20·log₁₀(d, km) + 20·log₁₀(f, MHz) + 32.44.

| Range | 915 MHz | 2.4 GHz | 5.8 GHz |
|---|---|---|---|
| 1 km | 91.7 | 100.0 | 107.7 |
| 5 km | 105.7 | 114.0 | 121.7 |
| 10 km | 111.7 | 120.0 | 127.7 |
| 30 km | 121.2 | 129.6 | 137.2 |

Every doubling of range is +6 dB; going from 915 MHz → 2.4 GHz costs 8.4 dB at the same range, → 5.8 GHz another 7.7 dB. This is the physics of the receiving antenna's aperture, not “penetrating power.”

### The budget equation
**Prx = Ptx + Gtx + Grx − Lcable − FSPL − Lextra**, margin M = Prx − Ssens.

- Ptx — transmitter power in dBm.
- G — antenna gain in dBi (dipole 2, patch 8, Yagi 12).
- Lcable — pigtails/cables (0.5–2 dB).
- Lextra — polarization (3 dB linear↔circular), mismatch, obstacles, the Fresnel zone near the ground (flying low over the surface costs another 6–20 dB).
- S — receiver sensitivity in dBm for the given mode (for ELRS, from the mode table: 2.4 GHz 50 Hz −115, 150 Hz −112, 250 Hz −108, 500 Hz −105; 900 MHz 25 Hz −123, 50 Hz −120, 100 Hz −117, 200 Hz −112).

Margin M: 10–15 dB is the minimum for a reliable link with fading (multipath, aircraft maneuvering); 20 dB is comfortable; 0 is the edge, the link will keep dropping.

### RC example: ELRS 2.4 GHz, 250 Hz, 250 mW
Ptx = 24 dBm, Gtx = 2 (radio dipole), Grx = 2 (onboard dipole, but we count 0 because of orientation), Lcable = 1, polarization another −3 in banks.
Prx at 10 km = 24 + 2 + 0 − 1 − 120 − 3 = −98 dBm. S(250 Hz) = −108 → 10 dB margin. Switching to 50 Hz (−115) gives 17 dB — or the same reliability at ~22 km. Raising power to 1 W (+6 dB) is the same as doubling the range.

### Video example: analog 5.8 GHz 800 mW
Ptx = 29 dBm, onboard cloverleaf 2, ground patch 8, cables −1.5, S of a typical analog receiver ≈ −90 dBm (video starts getting noisy long before it's lost). At 5 km: 29 + 2 + 8 − 1.5 − 121.7 = −84 dBm → 6 dB margin, the picture will have interference. Digital systems work down to −100…−105 dBm, but cut out abruptly at the threshold. Video almost always limits range before RC does — hence 900 MHz/1.2–1.3 GHz video for long-range flights and directional antennas on the ground.

### How to turn the budget into an RSSI threshold
The ELRS rule: warning when RSSI is ~8–10 dB above the mode's sensitivity; the critical failsafe threshold is at the sensitivity. For 2.4 GHz 250 Hz: warning at −98…−100 dBm, at −105 — turn back. In EdgeTX — a voice warning on RSSI dBm and on LQ (<70% at 250 Hz is a reason to worry).

### Why the calculation doesn't match the field
Multipath (ground reflections add up out of phase), obstacles in the Fresnel zone (the first-zone radius at 2.4 GHz over 5 km is ~12 m: flying low over the ground costs 6–20 dB), onboard interference (it reduces effective sensitivity), the real antenna orientation. That's why a range test is mandatory and a 10–15 dB margin is the minimum.

{{diagram:link-budget-chain|Worked budget example: ELRS 2.4 GHz, 250 mW, 10 km — received power of −98 dBm against a sensitivity of −108 dBm gives a 10 dB margin.}}

{{diagram:chart-link-margin|Received power from the free-space formula against ELRS sensitivity thresholds (the table from the link-elrs module). The margin is the distance from the curve to the threshold; a real flight needs 10–15 dB for fading, antenna rotation and the aircraft body.}}

{{widget:link-margin}}

## practice
### Step 1. RC budget table
For your link: power, mode and its sensitivity, antennas, cables. Calculate the margin at 1, 3, 5, 10 km. Find the range where the margin = 12 dB — that's your working limit.

### Step 2. Video budget table
The same for the video system, with the real sensitivity of the receiver/goggles. Compare the limits: what fails first.

### Step 3. Thresholds
Set an RSSI dBm warning = S + 10 and an LQ warning on the radio; record them in the aircraft's logbook. Failsafe in the firmware is tested.

### Step 4. Field test
A straight-line flight logging RSSI/LQ in the radio or FC log at 500 m, 1, 2 km (within permitted limits and area). Compare the measured RSSI with the calculated Prx for the same distances: the difference is your “reality correction,” usually 5–10 dB.

### Worked example and what to record
The module's example: ELRS 2.4 GHz, 250 mW (24 dBm), antennas 2 and 0 dBi, 4 dB of losses (cables and polarization), 150 Hz mode sensitivity −112 dBm. Free-space loss at 1 km at 2440 MHz: 20·log10(1) + 20·log10(2440) + 32.44 ≈ 100.2 dB. Received power 24 + 2 + 0 − 4 − 100.2 ≈ −78 dBm, margin ≈ 34 dB. Every doubling of distance takes away 6 dB: a 12 dB margin remains out to ≈ 12–13 km — that's the theoretical limit in free space. The same calculation is in the link budget widget above.
- **RC and video table:** distance, FSPL, received power, margin. Mark the distance where the margin drops to 12 dB. Usually video gives out first, not RC — check whether that's true for you.
- **Thresholds on the radio.** Warning on RSSI = sensitivity + 10 dB (here −102 dBm) and on LQ. Record the values in the aircraft's logbook.
- **Field test.** The measured RSSI at 500 m, 1 and 2 km is usually 5–10 dB worse than calculated: ground, the Fresnel zone, the airframe, antenna orientation. That difference is your correction — subtract it from the calculated range for this aircraft.

The lab counts as done when the budget is calculated for RC and video with the 12 dB margin distance, the field test produced a “calculated vs measured” table with the correction, and the RSSI warning threshold is set on the radio and recorded in the logbook.

## diagnostics
- **Symptom:** RSSI drops faster than calculated right from the start
  - Possible cause: losses in a cable/connector, polarization, an antenna under carbon.
  - What to do: check SWR, pigtails, orientation.
- **Symptom:** the link drops at the same range every time even with good RSSI
  - Possible cause: onboard interference reduces effective sensitivity; LQ drops earlier.
  - What to do: watch LQ, see the module on interference.
- **Symptom:** in the field the margin is 10 dB worse than calculated
  - Possible cause: flying low — obstacles in the Fresnel zone, multipath.
  - What to do: more altitude, a higher ground antenna, a directional antenna.
- **Symptom:** video is gone, RC still holds
  - Possible cause: the video budget ran out first (expected on 5.8 GHz).
  - What to do: a patch on the ground, more power, another band; RTH on video loss.

## references
- ExpressLRS — Signal Health (sensitivity per mode, RSSI/LQ) | https://www.expresslrs.org/info/signal-health/ | primary | A
- ExpressLRS — Long Range Competition / range considerations | https://www.expresslrs.org/info/long-range/ | primary | A
- Free-space path loss — Wikipedia (formula and derivation) | https://en.wikipedia.org/wiki/Free-space_path_loss | secondary | B

## checklist
- I can convert mW to dBm and calculate FSPL
- RC and video budgets are calculated, with a range margin
- The RSSI warning threshold is set from the mode's sensitivity
- The field test is compared with the calculation, the correction is recorded
- I know that video usually limits range before RC does
