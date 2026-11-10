---
id: rf-antennas
title: "Antennas, polarization and radiation patterns"
level: L2
readingTime: 30 min
firmware: any firmware
status: published
added: 2026-11-08
tags:
  - antennas
  - polarization
  - SWR
  - radio link
related:
  - link-protocols
  - link-vtx
  - rf-link-budget
next:
  - rf-link-budget
source: content/electronics/rf-antennas.md
source_hash: 078d000655bc
---

## summary
The antenna is half of the radio link, and the most underrated half. This module explains dipole, patch, cloverleaf and “T” antennas, the difference between linear and circular polarization, what gain in dBi is and why it always comes at the cost of beamwidth, how to read a radiation pattern and orient antennas on the aircraft and on the ground, what SWR measures and when an antenna is “the wrong one.” It ends with a ground range test.

## theory
### How an antenna radiates
A half-wave dipole is two conductors, each a quarter wave long. λ = c/f: 2.4 GHz → 12.5 cm (quarter 3.1 cm), 915 MHz → 32.8 cm (quarter 8.2 cm), 5.8 GHz → 5.2 cm (quarter 1.3 cm). An antenna is “tuned” when its size matches the frequency — then the energy goes out into the air instead of reflecting back.

### Radiation pattern and gain
An isotropic radiator (an imaginary one) radiates equally in all directions — 0 dBi. A real antenna redistributes energy: a dipole gives 2.15 dBi in the plane perpendicular to its axis and nothing along the axis (the “donut”). **Gain always comes from narrowing the beam.** An 8–9 dBi patch covers a sector of ~60–70°, a 12–14 dBi directional Yagi about ~30°. On the aircraft you need an omnidirectional antenna (its attitude keeps changing); on the ground, a directional one, if there's someone to aim it.

The main consequence for the aircraft: a dipole/“T” antenna mounted vertically does not radiate up or down. If the aircraft is directly overhead, you get a null. That's why the two receiver antennas (diversity) are mounted at 90° to each other.

### Worked example: where the dipole's null is
A vertical dipole on the radio, the aircraft at 100 m altitude. Elevation angle θ = atan(h/d), angle from the dipole axis is 90° − θ, relative gain ≈ sin²(angle from the axis):

| Aircraft distance | Elevation angle | Pattern loss |
|---|---|---|
| 1 km | 5.7° | 0 dB |
| 300 m | 18° | −0.5 dB |
| 100 m | 45° | −3 dB |
| 30 m (almost overhead) | 73° | −10.8 dB |

Takeaway: at long range the dipole works perfectly, and the null happens close in and overhead — where you have plenty of power margin. That's why you hold the radio's antenna **side-on** to the aircraft (don't point its tip at it), and on the aircraft a second antenna at 90° covers the first one's null.

### What dBi buys you in range
+6 dB of gain = ×2 range in free space. An 8 dBi patch on the ground instead of a 2 dBi dipole gives +6 dB — double the range, but **only inside the beam sector**: once the aircraft leaves the sector, you lose more than you gained. A directional antenna without aiming (a tracker or a pilot turning the radio) is a trap for flights that go “around in a circle.”

### Polarization
- **Linear** (dipole, “T”, monopole): the field oscillates in one plane. The receiving antenna must be in the same plane: a 90° rotation gives up to 20–30 dB of loss in theory, 10–20 in practice because of reflections. When the aircraft banks, the polarization gets misaligned.
- **Circular** (cloverleaf, helical, circularly polarized patch): the field rotates — right-hand (RHCP) or left-hand (LHCP). Antenna orientation barely matters; reflections reverse the direction of rotation and get attenuated (less multipath — cleaner video). You pay ~3 dB when receiving circular with a linear antenna and vice versa. RHCP↔LHCP costs 15–20 dB: don't mix them.
- For 5.8 GHz video — circular on both ends; for 900 MHz/2.4 GHz RC — linear dipoles mounted orthogonally.

### SWR and matching
SWR shows how much of the power is reflected from the antenna back into the transmitter. 1.0 is ideal; 1.5 — 4% reflected (−0.18 dB), 2.0 — 11% (−0.5 dB), 3.0 — 25% (−1.25 dB). High SWR heats the VTX and can kill it; it affects range less than you'd think as long as it's ≤ 2. It's measured with an antenna analyzer (NanoVNA — affordable). An antenna is “the wrong one” when the SWR minimum is not at your frequency (trimmed for / designed for another band), the connector is damaged, or the coax ground is torn off.

### Placement on the aircraft
- Antennas go outside the carbon: carbon is a conductor, it shields and detunes the antenna.
- Receiver: two antennas at 90°, away from the VTX and power wiring; tail “whiskers” pointing down and back at 45°.
- Video: antenna on top or on the bottom so that there is no frame or battery between it and the ground/pilot; for flying far and low — on the bottom.
- GPS: on top, ceramic patch horizontal, with a ground plane under it.
- Keep the pigtail cable as short as possible: thin RG178 coax loses ~1 dB per 30 cm at 5.8 GHz.

### Connectors: the quiet cause of a “bad antenna”
SMA and RP-SMA look the same, but one has the pin in the plug and the other in the jack: “it screwed on” doesn't mean “it connected” — the center contact may not touch. U.FL/IPEX is rated for a few dozen mating cycles and pops off from vibration if not secured — a drop of glue or heat shrink on the cable. MMCX holds better but also needs cable strain relief.

{{diagram:polarization-loss|Polarization mismatch loss: matched — 0 dB, linear to circular — 3 dB, crossed or opposite hand — 20 dB and more.}}

{{diagram:chart-antenna-patterns|Radiation patterns: a vertical dipole has a null along its axis (above and below the aircraft), a patch radiates forward in a sector and barely sees backward. Models: dipole sin²θ, patch cos⁴θ with a −20 dB back lobe.}}

{{widget:antenna-pol}}

## practice
### Step 1. Inventory
For every antenna on the aircraft and on the ground: band, type, polarization (and the hand of circular), gain, connector (SMA/RP-SMA, U.FL/MMCX). Check that polarizations match in every link.

### Step 2. Orientation
Sketch the patterns (the dipole donut, the patch sector) projected onto the aircraft in typical attitudes: hover, 45° bank, flying out to 1 km at 100 m altitude (elevation ~6°). Make sure that in every attitude both ends “see” each other outside a null.

### Step 3. SWR
NanoVNA (if you have one):
1. Sweep range: 5.6–6.0 GHz for video (or 2.3–2.6 GHz, 850–950 MHz for RC).
2. SOL calibration (Short–Open–Load) **at the end of the very cable** the antenna will be connected to, otherwise you're measuring the cable.
3. Connect the antenna, display the SWR plot: record the minimum SWR and the frequency of the minimum, and the SWR on your channel.
4. Normal: the minimum inside the operating band, SWR ≤ 1.5 on the channel. A minimum at 5.4 GHz while operating at 5.8 — the antenna is “the wrong one” (or for another band).

Without an instrument — indirectly: RSSI at a fixed distance with two antennas, one after the other.

### Step 4. Ground range test
Aircraft on a 1.5 m stand, the operator walks out to 50, 100, 200 m (line of sight). Record RSSI/LQ and video quality; rotate the aircraft by 90° and 180° — record the dropouts. Lab: a table of distance × orientation × RSSI.

## diagnostics
- **Symptom:** the link drops when the aircraft is directly overhead
  - Possible cause: the dipole pattern null along its axis.
  - What to do: a second antenna at 90°, tilt the radio's antenna.
- **Symptom:** video gets noisy when banking
  - Possible cause: linear antennas, polarization mismatch.
  - What to do: circular polarization on both ends, the same RHCP/LHCP.
- **Symptom:** the VTX gets very hot, range is short
  - Possible cause: high SWR — an antenna for a different band, or a damaged one.
  - What to do: check the SWR/replace the antenna; never power the VTX without an antenna.
- **Symptom:** RSSI is good, LQ is bad
  - Possible cause: noise near the RX antenna, not the antenna itself.
  - What to do: see the module on interference; move it away from the VTX.
- **Symptom:** GPS takes a long time to acquire satellites
  - Possible cause: the patch is under carbon, no ground plane, interference nearby.
  - What to do: a mast, a metal plate under the patch.

## references
- ExpressLRS — Hardware Selection (antennas RX/TX) | https://www.expresslrs.org/hardware/hardware-selection/ | primary | A
- Oscar Liang — FPV Antenna guide (polarization, types) | https://oscarliang.com/fpv-antenna/ | secondary | B
- ARRL — Antenna fundamentals (SWR, gain, polarization) | https://www.arrl.org/antennas | secondary | B

## checklist
- I know the antenna types, their patterns and gain
- I calculate the pattern null from the elevation angle and hold the radio's antenna side-on to the aircraft
- I check the connectors (SMA/RP-SMA, U.FL retention)
- Polarizations match in every link (RHCP/LHCP not mixed)
- RC antennas are orthogonal, outside the carbon, away from the VTX
- SWR is measured or estimated indirectly
- Ground range test done, table recorded
