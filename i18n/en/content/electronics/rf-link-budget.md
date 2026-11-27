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
| 5 km | 105.6 | 114.0 | 121.7 |
| 10 km | 111.7 | 120.0 | 127.7 |
| 30 km | 121.2 | 129.6 | 137.3 |

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

{{diagram:chart-link-two-ray|The module's 2.4 GHz example: flying at 10 m, the ground reflection eats 10 dB at 5 km, and the −98 dBm warning comes at 3.9 km instead of 10 km; at 120 m the break point moves beyond 5.9 km and only short dips remain.}}

{{diagram:link-budget-chain|Worked budget example: ELRS 2.4 GHz, 250 mW, 10 km — received power of −98 dBm against a sensitivity of −108 dBm gives a 10 dB margin.}}

{{diagram:chart-link-margin|Received power from the free-space formula against ELRS sensitivity thresholds (the table from the link-elrs module). The margin is the distance from the curve to the threshold; a real flight needs 10–15 dB for fading, antenna rotation and the aircraft body.}}

{{widget:link-margin}}

## practice
### Step 1. RC budget table
For your link: power, mode and its sensitivity, antennas, cables. Calculate the margin at 1, 3, 5, 10 km. Find the range where the margin = 12 dB — that's your working limit.

### Step 2. Video budget table
The same for the video system, with the real sensitivity of the receiver/goggles. Compare the limits: what fails first.

### Step 2a. Budget script (code and output as in the source module)

```python
#!/usr/bin/env python3
"""Link budget lab for module rf-link-budget (stdlib only).

Inputs = the module's worked example: ExpressLRS 2.4 GHz, 250 Hz (sensitivity -108 dBm,
ELRS 4.1 src/src/common.cpp:100), 250 mW, dipole on the radio, 0 dBi effective on board,
1 dB cables, 3 dB polarisation loss. Run: python3 link_lab.py
"""
import math

C = 299_792_458.0
F_MHZ = 2440.0             # middle of the 2.4 GHz ISM band
LAM = C / (F_MHZ * 1e6)    # wavelength, m


def dbm(mw):               # mW -> dBm
    return 10 * math.log10(mw)


def fspl(d_km, f_mhz=F_MHZ):
    return 20 * math.log10(d_km) + 20 * math.log10(f_mhz) + 32.44


def two_ray_excess(d_m, ht, hr, gamma=-1.0):
    """Extra loss (dB) of direct + ground-reflected ray vs free space, flat ground, reflection gamma."""
    direct = math.hypot(d_m, hr - ht)
    refl = math.hypot(d_m, hr + ht)
    dphi = 2 * math.pi * (refl - direct) / LAM
    # field sum normalised to the direct ray (path-length amplitude difference included)
    re = 1 + gamma * (direct / refl) * math.cos(dphi)
    im = gamma * (direct / refl) * math.sin(-dphi)
    return -20 * math.log10(math.hypot(re, im))


def sens_from_noise(bw_hz, nf_db, snr_db):
    return -174 + 10 * math.log10(bw_hz) + nf_db + snr_db


P_TX = dbm(250)
G_TX, G_RX, L_CAB, L_POL = 2.0, 0.0, 1.0, 3.0
S = -108.0
EIRP = P_TX + G_TX - L_CAB

print(f"1) 250 mW = {P_TX:.1f} dBm; EIRP = {EIRP:.1f} dBm; 100 mW = {dbm(100):.1f} dBm; 1 W = {dbm(1000):.1f} dBm")
print("2) Budget vs distance (free space):")
print("   d_km  FSPL_dB  Prx_dBm  margin_dB")
for d in (1, 2, 5, 10, 15):
    prx = P_TX + G_TX + G_RX - L_CAB - L_POL - fspl(d)
    print(f"   {d:4}  {fspl(d):7.1f}  {prx:7.1f}  {prx - S:9.1f}")
for m in (12, 0):
    budget = P_TX + G_TX + G_RX - L_CAB - L_POL - S - m
    d = 10 ** ((budget - 20 * math.log10(F_MHZ) - 32.44) / 20)
    print(f"   distance with margin {m:2} dB: {d:5.1f} km")

print("3) Sensitivity from noise: S = -174 + 10lg(BW) + NF + SNR_min, NF = 6 dB")
# SX127x LoRa demodulator SNR per SF: datasheet Rev.7 Table 13; ELRS 900 MHz uses BW 500 kHz
for sf, snr, elrs, name in ((6, -5.0, -112, "200 Hz"), (7, -7.5, -117, "100 Hz"),
                            (8, -10.0, -120, "50 Hz"), (9, -12.5, -123, "25 Hz")):
    s = sens_from_noise(500e3, 6, snr)
    print(f"   SF{sf} BW500k: formula {s:6.1f} dBm, ELRS 4.1 table {elrs} dBm ({name}), diff {elrs - s:+.1f} dB")

print("4) First Fresnel zone radius at mid-path, 2.44 GHz:")
for d in (1, 5, 10):
    r = math.sqrt(LAM * d * 1000 / 4)
    print(f"   {d:3} km: r1 = {r:5.1f} m, 60 % clearance = {0.6 * r:5.1f} m")

print("5) Radio horizon d = sqrt(2*k*R*h), k = 4/3, R = 6371 km:")
for h1, h2 in ((2, 30), (2, 120), (10, 120)):
    k_r = 4 / 3 * 6371e3
    d = (math.sqrt(2 * k_r * h1) + math.sqrt(2 * k_r * h2)) / 1000
    print(f"   ground {h1:3} m, aircraft {h2:3} m: {d:5.1f} km")

print("6) Two-ray ground reflection, ground antenna 1.5 m, gamma = -1:")
for hr in (10, 30, 120):
    dc = 4 * 1.5 * hr / LAM
    row = "  ".join(f"{d}km {two_ray_excess(d * 1000, 1.5, hr):+5.1f}" for d in (1, 2, 5, 10))
    print(f"   aircraft {hr:3} m: breakpoint {dc / 1000:5.2f} km | extra loss vs FSPL: {row}")

print("7) ELRS 4.1 dynamic power (src/src/dynpower.cpp:166-252):")
S_FLRC = -104.0   # F1000/F500/D500/D250 have no SNR thresholds -> RSSI branch (common.cpp:94-97)
print(f"   FLRC/DVDA (S {S_FLRC:.0f}): RSSI branch, raise below {S_FLRC + 15:.0f} dBm, "
      f"lower above {S_FLRC + 21:.0f} dBm with LQ_avg >= 95")
print(f"   LoRa 250 Hz (S {S:.0f}): SNR branch, SNR raise gated by RSSI <= {S + 21:.0f} dBm or LQ_avg <= 95; "
      f"course warning S+10 = {S + 10:.0f} dBm")
```

```text
1) 250 mW = 24.0 dBm; EIRP = 25.0 dBm; 100 mW = 20.0 dBm; 1 W = 30.0 dBm
2) Budget vs distance (free space):
   d_km  FSPL_dB  Prx_dBm  margin_dB
      1    100.2    -78.2       29.8
      2    106.2    -84.2       23.8
      5    114.2    -92.2       15.8
     10    120.2    -98.2        9.8
     15    123.7   -101.7        6.3
   distance with margin 12 dB:   7.8 km
   distance with margin  0 dB:  30.9 km
3) Sensitivity from noise: S = -174 + 10lg(BW) + NF + SNR_min, NF = 6 dB
   SF6 BW500k: formula -116.0 dBm, ELRS 4.1 table -112 dBm (200 Hz), diff +4.0 dB
   SF7 BW500k: formula -118.5 dBm, ELRS 4.1 table -117 dBm (100 Hz), diff +1.5 dB
   SF8 BW500k: formula -121.0 dBm, ELRS 4.1 table -120 dBm (50 Hz), diff +1.0 dB
   SF9 BW500k: formula -123.5 dBm, ELRS 4.1 table -123 dBm (25 Hz), diff +0.5 dB
4) First Fresnel zone radius at mid-path, 2.44 GHz:
     1 km: r1 =   5.5 m, 60 % clearance =   3.3 m
     5 km: r1 =  12.4 m, 60 % clearance =   7.4 m
    10 km: r1 =  17.5 m, 60 % clearance =  10.5 m
5) Radio horizon d = sqrt(2*k*R*h), k = 4/3, R = 6371 km:
   ground   2 m, aircraft  30 m:  28.4 km
   ground   2 m, aircraft 120 m:  51.0 km
   ground  10 m, aircraft 120 m:  58.2 km
6) Two-ray ground reflection, ground antenna 1.5 m, gamma = -1:
   aircraft  10 m: breakpoint  0.49 km | extra loss vs FSPL: 1km  -2.8  2km  +2.5  5km +10.3  10km +16.3
   aircraft  30 m: breakpoint  1.47 km | extra loss vs FSPL: 1km  -3.5  2km  -5.2  5km  +1.0  10km  +6.8
   aircraft 120 m: breakpoint  5.86 km | extra loss vs FSPL: 1km  +5.0  2km  -6.0  5km  -5.7  10km  -4.0
7) ELRS 4.1 dynamic power (src/src/dynpower.cpp:166-252):
   FLRC/DVDA (S -104): RSSI branch, raise below -89 dBm, lower above -83 dBm with LQ_avg >= 95
   LoRa 250 Hz (S -108): SNR branch, SNR raise gated by RSSI <= -87 dBm or LQ_avg <= 95; course warning S+10 = -98 dBm
```

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
