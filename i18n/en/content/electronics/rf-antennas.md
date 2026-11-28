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
source_hash: f8f086e9bf22
---

## summary
The antenna is half of the radio link, and the most underrated half. This module explains dipole, patch, cloverleaf and "T" antennas, the difference between linear and circular polarization, what gain in dBi is and why it always comes at the cost of beamwidth, how to read a radiation pattern and orient antennas on the aircraft and on the ground, what SWR measures, and when an antenna is "the wrong one". It ends with a ground range test.

## theory
### How an antenna radiates
A half-wave dipole is two conductors of a quarter wavelength each. λ = c/f: 2.4 GHz → 12.5 cm (a quarter is 3.1 cm), 915 MHz → 32.8 cm (a quarter is 8.2 cm), 5.8 GHz → 5.2 cm (a quarter is 1.3 cm). An antenna is "tuned" when its size matches the frequency: then the energy goes out into the air instead of reflecting back.

### Radiation pattern and gain
An isotropic radiator (an imaginary one) radiates equally in all directions: 0 dBi. A real antenna redistributes the energy: a dipole gives 2.15 dBi in the plane perpendicular to its axis and nothing along the axis (the "donut"). **Gain always comes from narrowing the beam.** An 8–9 dBi patch covers a sector of ~60–70°, a 12–14 dBi directional Yagi ~30°. On the aircraft you need an omnidirectional antenna (the aircraft's attitude changes); on the ground, a directional one if someone can point it.

The main consequence for the aircraft: a dipole/"T" antenna mounted vertically does not radiate up and down. If the aircraft is directly overhead, there is a null. That is why the receiver's two antennas (diversity) are mounted at 90° to each other.

### Worked example: where a dipole has its null
A vertical dipole on the transmitter, the aircraft at a height of 100 m. The elevation angle is θ = atan(h/d), the angle from the dipole axis is 90° − θ, and the relative gain ≈ sin²(angle from the axis):

| Aircraft distance | Elevation angle | Pattern loss |
|---|---|---|
| 1 km | 5.7° | 0 dB |
| 300 m | 18° | −0.5 dB |
| 100 m | 45° | −3 dB |
| 30 m (almost overhead) | 73° | −10.8 dB |

The conclusion: at range the dipole works perfectly, and the null happens close in and overhead, where there is plenty of power margin. That is why the transmitter antenna is held **side-on** to the aircraft (not pointing its tip at it), and on the aircraft a second antenna at 90° covers the null of the first.

### What dBi give you in range
+6 dB of gain = ×2 range in free space. An 8 dBi patch on the ground instead of a 2 dBi dipole gives +6 dB, a doubling, but **only within the beam's sector**: once the aircraft leaves the sector, you lose more than you gained. A directional antenna without pointing (a tracker, or a pilot turning the transmitter) is a trap for flights "in a circle".

### Polarization
- **Linear** (dipole, "T", monopole): the field oscillates in one plane. The receiving antenna must be in the same plane: a 90° rotation in theory gives unlimited loss (cos² 90° = 0); real antennas give 20–30 dB, and in flight reflections reduce it to 10–20 dB. When the aircraft banks, the polarizations become misaligned.
- **Circular** (cloverleaf, helical, circularly polarized patch): the field rotates, right-hand (RHCP) or left-hand (LHCP). Antenna orientation hardly matters; reflections reverse the direction of rotation and are attenuated (less multipath, cleaner video). You pay ~3 dB when a linear antenna receives circular polarization and vice versa. RHCP↔LHCP costs 15–20 dB: do not mix them.
- For 5.8 GHz video, circular at both ends; for 900 MHz/2.4 GHz RC, linear dipoles mounted orthogonally.
- The video antenna type for the job (a course guideline): on the aircraft, an omnidirectional circular one (cloverleaf, pagoda, lollipop): the aircraft spins around, and a narrow beam would keep losing the receiver; a stubby (shortened) one on whoops and wherever the antenna gets hit often, at the cost of gain. On the goggles, an omni plus a directional patch if the flight stays in one sector (beamwidth: see "Ground antennas and trackers" below). Check by flying a circle at the working distance: there should be no picture dropouts in any one direction.

### SWR and matching
SWR shows what share of the power reflects from the antenna back into the transmitter. 1.0 is ideal; 1.5 is 4% reflected (−0.18 dB), 2.0 is 11% (−0.5 dB), 3.0 is 25% (−1.25 dB). A high SWR heats the VTX and can kill it; it affects range less than you might think as long as it is ≤ 2. It is measured with an antenna analyzer (a NanoVNA is affordable). An antenna is "the wrong one" when the SWR minimum is not at your frequency (cut for or designed for another band), the connector is damaged, or the coax ground is broken.

### Placement on the aircraft
- Antennas go outside the carbon: carbon is a conductor, it shields and detunes the antenna.
- Receiver: two antennas at 90°, away from the VTX and power wires; tail-mounted "whiskers" down and back at 45°.
- Video: the antenna on top or underneath so that no frame or battery is between it and the ground/pilot; when flying far and low, underneath.
- GPS: on top, the ceramic patch horizontal, with a ground plane underneath.
- Keep the pigtail cable as short as possible: thin RG178 coax loses ~1 dB per 30 cm at 5.8 GHz.

### Connectors: the quiet cause of a "bad antenna"
SMA and RP-SMA look the same, but one has the pin in the plug and the other in the jack: "it screwed on" does not mean "it connected", and the center contact may not touch. U.FL/IPEX is rated for tens of mating cycles and comes off from vibration unless secured: a drop of glue or heat-shrink on the cable. MMCX holds better, but also needs cable strain relief.

{{diagram:polarization-loss|Polarization mismatch losses: matched is 0 dB, linear with circular is 3 dB, crossed or opposite hands is 20 dB or more.}}

{{diagram:chart-antenna-patterns|Radiation patterns: a vertical dipole has a null along its axis (above and below the aircraft), a patch radiates a forward sector and hardly sees backward. Models: dipole sin²θ, patch cos⁴θ with a −20 dB back lobe.}}

{{widget:antenna-pol}}

### Ground antennas and trackers
The input is a map of the flight from the pilot's position: the azimuth spread Δφ over the far part of the route, the elevation angle θ = atan(h/d) where the aircraft is low and close, and the distance at which the link budget runs out of margin (`rf-link-budget`).

**Gain and beamwidth.** Directivity D ≈ 41253 / (θE · θH), with the half-power angles in degrees (Kraus's approximation, Balanis). A 65° × 65° beam → 9.9 dBi, 30° × 30° → 16.6 dBi; losses to efficiency and side lobes give the datasheet 8–9 dBi of a patch and 12–14 dBi of a Yagi from the subsection above. With the cos⁴θ patch model (the chart above), an 8 dBi patch has a half-power beamwidth of 65.5° and beats a 2.15 dBi dipole only within ±44° of its axis; at 45° it equals the dipole (2 dBi), at 60° it loses 6 dB.

**The rule.**
1. Δφ in the far zone is smaller than the beamwidth → a fixed patch pointed along the route. Worked example: a corridor ±500 m wide and 5 km long. The whole corridor fits within ±32.8° starting from d = 500 / tan 32.8° ≈ 776 m; closer in, the edge of the corridor leaves the beam: at d = 500 m it is at 45°, where the patch equals the dipole, and closer still it is worse than the dipole, but there the path loss is also 20·lg(5000 / 776) = 16.2 dB lower than at 5 km. No tracker is needed.
2. Flying around yourself (Δφ ≈ 360°) or an antenna narrower than 30° → a tracker or an omnidirectional antenna.
3. Check the elevation angle: at a height of 120 m and a distance of 200 m, θ = 31°, the edge of the beam of a patch pointed at the horizon; at 1 km it is 6.8°.
4. A tracker needs an angular rate of ω = v / d: 20 m/s at 50 m is 23 °/s, at 1 km 1.1 °/s. The near zone sets the requirements, but there a dipole is enough anyway.

**Tracker types, by where the aircraft's position comes from.**

| Source | Example | What to configure and check |
|---|---|---|
| MAVLink | ArduPilot AntennaTracker 4.7.3 firmware on a separate flight controller with servos | `SYSID_TARGET` (0 = auto detect); its own position from a GPS or `START_LATITUDE`/`START_LONGITUDE`; `SERVO_YAW_TYPE`/`SERVO_PITCH_TYPE`: 0 Position, 1 OnOff, 2 ContinuousRotation; `YAW_RANGE` 360, `PITCH_MIN`/`PITCH_MAX` −90/90; targets closer than `DISTANCE_MIN` = 5 m are not tracked |
| CRSF through the ELRS Backpack | a tracker with a Backpack receiver (example: Sentinel) | `Backpack → Telemetry = ESPNOW` (ELRS 3.4+); the aircraft's GPS arrives in the transmitter's telemetry; the tracker within 10 m of the module, preferably 5 m; Telem Ratio from 1:2 to 1:16 |
| INAV analog video | Sentinel reading an OSD line | `osd_telemetry = ON` (default `OFF`) |

How to check: carry the aircraft in a circle at 50–100 m and the tracker keeps it in the beam; at the far point compare the RSSI with the patch and with the omnidirectional antenna: for 8 and 2 dBi expect about +6 dB. A relay is needed only when the aircraft is beyond the pilot's radio line of sight, and that is almost always beyond visual line of sight too, i.e. BVLOS with a separate authorization (`f-regulations`).

### Where it fits in the system

- **Takes in:** the RC and video operating frequency and power (`link-elrs`, `link-vtx`); the aircraft coordinates from telemetry for the ground antenna tracker (`link-telemetry-radios`); a place on the frame outside the carbon and away from interference sources (`el-emi`).
- **Puts out:** the gain in dBi, the pattern null and the polarization losses as terms of the link budget (`rf-link-budget`); the actual LQ and RSSI that trigger the failsafe (`bf-failsafe`).
- **If you get this wrong:** RHCP on the aircraft and LHCP on the ground → 15–20 dB of loss, and the video drops out much earlier than the calculated range (`rf-link-budget`). Both receiver antennas in one plane or under carbon → the link drops when the aircraft turns, a failsafe at short range (tree 5 in `diag-troubleshooting`). A high SWR from a damaged connector → the VTX heats up and can fail.

## practice
### Step 1. Inventory
For each antenna on the aircraft and on the ground: band, type, polarization (and the hand of circular), gain, connector (SMA/RP-SMA, U.FL/MMCX). Check that the polarizations match in each link.

### Step 2. Orientation
Draw the patterns (the dipole donut, the patch sector) projected onto the aircraft in typical attitudes: hover, a 45° bank, 1 km out at a height of 100 m (elevation angle ~6°). Make sure that in every attitude both ends "see" each other outside a null.

### Step 3. SWR
NanoVNA (if you have one):
1. Sweep range: 5.6–6.0 GHz for video (or 2.3–2.6 GHz, 850–950 MHz for RC).
2. SOL (Short–Open–Load) calibration **at the end of the cable** the antenna will connect to; otherwise you are measuring the cable.
3. Connect the antenna, display the SWR plot: record the SWR minimum and the frequency of the minimum, and the SWR on your channel.
4. Normal: the minimum inside the operating band, SWR ≤ 1.5 on the channel (a course guideline). This is stricter than range requires (1.5 is −0.18 dB, 2.0 is −0.5 dB, see the theory above): it leaves margin for the SWR rising on the aircraft, with carbon nearby or the antenna bent or hit; a new antenna at 1.5 leaves room up to 2, beyond which the VTX heats up noticeably. A minimum at 5.4 GHz when operating at 5.8 means the antenna is "the wrong one" (or for another band).

Without an instrument, indirectly: RSSI at a fixed distance with two antennas in turn.

### Step 4. Ground range test
The aircraft on a 1.5 m stand, the operator walks away to 50, 100, 200 m (line of sight). Record RSSI/LQ and the video quality; turn the aircraft by 90° and 180° and record the dips. Self-check: the lab is done when the distance × orientation × RSSI table is filled in for 50, 100 and 200 m and three orientations (0°, 90°, 180°), the polarizations match in every link, and, if you have a NanoVNA, the SWR minimum lies inside the operating band and the SWR on your channel is ≤ 1.5.

**Reference answer for self-check.** In line of sight the RSSI falls smoothly with distance: +6 dB is ×2 range, so from 50 to 100 m and from 100 to 200 m you lose roughly 6 dB each. Turning the aircraft gives a dip where the antenna points its axis at the operator (the dipole null) or where the frame and battery end up between the antennas; with linear antennas a 90° polarization mismatch is 10–20 dB in practice. Common wrong results: 15–20 dB of loss in the video at any orientation means RHCP and LHCP are mixed; the SWR minimum outside the operating band (5.4 GHz when operating at 5.8) means an antenna for another band; a high SWR at all frequencies means the calibration was not done at the end of the cable, or there is no contact in the connector (SMA versus RP-SMA "screwed on" but did not connect).

## diagnostics
- **Symptom:** the link drops when the aircraft is directly overhead
  - Possible cause: the dipole pattern null along its axis.
  - What to do: a second antenna at 90°, tilt the transmitter antenna.
- **Symptom:** the video is noisy in banks
  - Possible cause: linear antennas, polarization mismatch.
  - What to do: circular polarization at both ends, the same RHCP/LHCP.
- **Symptom:** the VTX gets very hot, the range is short
  - Possible cause: a high SWR: an antenna for another band, or a damaged one.
  - What to do: check the SWR/replace the antenna; never power a VTX without an antenna.
- **Symptom:** RSSI is good, LQ is bad
  - Possible cause: noise next to the RX antenna, not the antenna.
  - What to do: see the interference module; move it away from the VTX.
- **Symptom:** the GPS takes a long time to acquire satellites
  - Possible cause: the patch is under carbon, no ground plane, interference nearby.
  - What to do: a mast, a metal plate under the patch.

## references
- ExpressLRS — Hardware Selection (antennas RX/TX) | https://www.expresslrs.org/hardware/hardware-selection/ | primary | A
- Balanis C. A. — Antenna Theory: Analysis and Design, 4th ed., Wiley 2016 (chapter 2, directivity; Kraus's approximation D ≈ 41253 / (Θ1·Θ2)) | https://au.mathworks.com/academia/books/antenna-theory-balanis.html | primary | A
- ArduPilot Copter-4.7.3 AntennaTracker/Parameters.cpp and config.h (tracker parameters and defaults) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.3/AntennaTracker/Parameters.cpp | primary | A
- ExpressLRS — Backpack Telemetry (ESP-NOW, tracker; accessed 2026-11-22) | https://www.expresslrs.org/software/backpack-telemetry/ | primary | A
- INAV wiki — AAT Automatic Antenna Tracker (telemetry in analog video) | https://github.com/inavFlight/inav/wiki/AAT-Automatic-Antenna-Tracker | primary | B
- Oscar Liang — FPV Antenna guide (polarization, types) | https://oscarliang.com/fpv-antenna/ | secondary | B
- ARRL — Antenna fundamentals (SWR, gain, polarization) | https://www.arrl.org/antennas | secondary | B

## checklist
- I know the antenna types, their patterns and gain
- I calculate the pattern loss from the elevation angle and hold the transmitter antenna side-on to the aircraft
- I check the connectors (SMA/RP-SMA, securing U.FL)
- The polarizations match in every link (RHCP/LHCP not mixed)
- The RC antennas are orthogonal, outside the carbon, away from the VTX
- The SWR has been measured or estimated indirectly
- I choose a directional ground antenna by the azimuth spread and elevation angle, and a tracker when the flight leaves the beam
- The ground range test is done and the table recorded
