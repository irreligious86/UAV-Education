---
id: rf-link-budget
title: "Radio link budget and range"
level: L2
readingTime: 30 min
firmware: any firmware · sensitivity tables and Dynamic Power — ExpressLRS 4.1.0
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
source_hash: c45d9d5ff944
---

## summary
"Will it make 10 km?" is a question of arithmetic, not faith. A link budget is a sum in decibels: transmitter power + antenna gains − cable losses − path loss must stay above the receiver sensitivity with a fade margin. This module teaches you to calculate it for RC and video, convert the margin into expected range, set the RSSI warning threshold and compare the calculation with a field test, and it shows why 900 MHz flies farther than 2.4 GHz at the same power, while 5.8 GHz video is the weak link.

## theory
### Decibels in five minutes
A dB is a logarithmic measure of a ratio: 3 dB ≈ ×2 in power, 10 dB = ×10, 20 dB = ×100. dBm is power relative to 1 mW: 0 dBm = 1 mW, 20 dBm = 100 mW, 27 dBm = 500 mW, 30 dBm = 1 W. **Doubling the transmitter power gives +3 dB, the same as a slightly better antenna.** Doubling the range costs 6 dB (see below).

### EIRP: what the receiver sees and what the law limits
EIRP (effective isotropic radiated power) = P_tx + G_tx − L_cable: the power you would have to feed into an isotropic antenna to get the same field in the main direction. This is what enters the budget, and regulatory limits are also written in EIRP. The module's example: 250 mW (24 dBm) + a 2 dBi dipole − 1 dB of cable = 25 dBm ≈ 316 mW EIRP. If your country allows 100 mW EIRP at 2.4 GHz (the general EU rules, see `f-regulations`), then with the same antenna you can feed the module no more than 20 − 2 + 1 = 19 dBm ≈ 80 mW. The budget loses 5 dB, and the range at the same margin drops by a factor of 10^(5/20) ≈ 1.8. A directional antenna on the transmitter raises the EIRP just as power does, so the limit applies to it too. The law does not limit receive gain: a patch on the ground video receiver is the cheapest legal decibel.

{{lesson:f-regulations|Which EIRP limits apply at 2.4 and 5.8 GHz and 868/915 MHz, and why 1 W is usually outside the general rules.}}

### Free-space path loss (FSPL)
FSPL(dB) = 20·log₁₀(d, km) + 20·log₁₀(f, MHz) + 32.44.

| Range | 915 MHz | 2.4 GHz | 5.8 GHz |
|---|---|---|---|
| 1 km | 91.7 | 100.0 | 107.7 |
| 5 km | 105.6 | 114.0 | 121.7 |
| 10 km | 111.7 | 120.0 | 127.7 |
| 30 km | 121.2 | 129.6 | 137.3 |

Each doubling of range adds 6 dB; going from 915 MHz to 2.4 GHz costs 8.4 dB at the same range, and on to 5.8 GHz another 7.7 dB. This is the physics of the receiving antenna's aperture, not "penetrating power".

### The budget equation
**P_rx = P_tx + G_tx + G_rx − L_cable − FSPL − L_extra**, margin M = P_rx − S_sens.

- P_tx is the transmitter power in dBm.
- G is the antenna gain in dBi (dipole 2, patch 8, Yagi 12).
- L_cable is the pigtails/cables (0.5–2 dB).
- L_extra is polarization (3 dB linear↔circular), mismatch, obstacles, the Fresnel zone near the ground (low flight close to the surface costs another 6–20 dB).
- S is the receiver sensitivity in dBm for the given mode (for ELRS, from the mode table: 2.4 GHz 50 Hz −115, 150 Hz −112, 250 Hz −108, 500 Hz −105; 900 MHz 25 Hz −123, 50 Hz −120, 100 Hz −117, 200 Hz −112).

Margin M: 10–15 dB is the minimum for a reliable link with fading (multipath, aircraft turns); 20 dB is comfortable; 0 is the limit, and the link will break up (a course guideline).

### Where sensitivity comes from
A receiver decodes a packet as long as the signal is above the noise by the amount the demodulator needs. The thermal noise at the input is kTB: −174 dBm per 1 Hz of bandwidth at 290 K. Hence **S = −174 + 10·lg(B, Hz) + NF + SNR_min**, where NF is the receiver's noise figure and SNR_min is the signal-to-noise ratio at which the demodulator still receives packets. For LoRa SNR_min is negative: the signal is received below the noise, because each symbol is spread over 2^SF chips. Per the SX1276 datasheet (Rev. 7, Table 13) SNR_min = −5 dB at SF6 and drops by 2.5 dB with each SF step, down to −20 dB at SF12.

ELRS 900 MHz modes on the SX127x use a 500 kHz bandwidth and SF6…SF9. With NF = 6 dB (a course guideline for a typical low-noise amplifier), the formula gives −116, −118.5, −121 and −123.5 dBm. The ELRS 4.1 table (`src/src/common.cpp:17–23`) for 200, 100, 50 and 25 Hz gives −112, −117, −120 and −123 dBm. The firmware builds in 0.5–4 dB of margin over theory (inferred from the comparison; the calculation is in practice step 3). Two practical rules follow from the formula:
- **A lower packet rate means a longer link.** A slower mode uses a higher SF: one SF step gives ≈ 2.5–3 dB of sensitivity, that is ≈ ×1.4 in range. You pay with airtime and latency (`link-elrs`).
- **Onboard noise adds to the NF.** If interference from ESCs, the VTX or a DC-DC converter raises the receiver's noise floor by 6 dB, the 250 Hz mode behaves as if its sensitivity were −102 dBm instead of −108. The budget loses 6 dB, the range loses half. RSSI meanwhile looks normal, while LQ drops earlier than calculated (`el-emi`).

### RC example: ELRS 2.4 GHz, 250 Hz, 250 mW
P_tx = 24 dBm, G_tx = 2 (transmitter dipole), G_rx = 2 (onboard dipole, but count it as 0 because of orientation), L_cable = 1, polarization another −3 in banks.
P_rx at 10 km = 24 + 2 + 0 − 1 − 120 − 3 = −98 dBm. S(250 Hz) = −108 → a 10 dB margin. Switching to 50 Hz (−115) gives 17 dB, or the same reliability at ~22 km. Raising the power to 1 W (+6 dB) is the same as doubling the range.

### Video example: analog 5.8 GHz 800 mW
P_tx = 29 dBm, onboard cloverleaf 2, ground patch 8, cables −1.5, S of a typical analog receiver ≈ −90 dBm (the video starts getting noisy long before it is lost). At 5 km: 29 + 2 + 8 − 1.5 − 121.7 = −84 dBm → a 6 dB margin, and the picture will have interference. Digital systems work down to −100…−105 dBm, but break up abruptly at the threshold. Video almost always limits range before RC; hence 900 MHz/1.2–1.3 GHz video for long-range flights and directional antennas on the ground.

### Turning the budget into an RSSI threshold
Per the ELRS documentation, the RSSI warning is set 5–10 dB above the mode's sensitivity (`link-elrs`); the critical failsafe threshold is at the sensitivity. The course guideline is a single number, S + 10 dB (table below, `link-elrs`, `link-edgetx`). For 2.4 GHz 250 Hz: the warning at −98 dBm, turn back no lower than −103 dBm (S + 5, the low end of the documented range), as in `link-elrs`. In EdgeTX, a voice warning on RSSI dBm and on LQ (<70% is a reason to worry, 50 % is critical, `link-edgetx`; the threshold is the same for any packet rate, because LQ is the share of packets that arrived, not their number; the margin is read from RSSI: LQ falls "off a cliff", `link-elrs`).

### How ELRS spends the margin itself: Dynamic Power and LQ
Dynamic Power in ELRS 4.1 (`src/src/dynpower.cpp`) works through two branches, and the mode table decides which one applies. The FLRC and DVDA modes (F1000, F500, D500, D250, S = −104) have no SNR thresholds and use the RSSI branch (`dynpower.cpp:166–189`): the power goes up one step when the average of five RSSI samples is below S + 15 dB, and down when it is above S + 21 dB with an average LQ ≥ 95 %; for these modes that is −89 and −83 dBm. All LoRa modes, both 2.4 GHz (including the 250 Hz of the example) and 900 MHz, use the SNR branch (`:190–249`): the power goes down when the SNR is above the threshold from the statistics and the average LQ is ≥ 95 %, and goes up on an SNR deficit, but only while RSSI ≤ S + 21 or the average LQ ≤ 95 % (`:239`). For 250 Hz that is the only RSSI threshold: −87 dBm. Besides these branches, four more paths raise the power: an instantaneous LQ ≤ 85 % when the branches changed nothing, plus one step (`:20`, `:252`); LQ 20 points below its moving average over 8 packets, or LQ ≤ 50 %, straight to the maximum configured power (`:17–19`, `:154–157`); missed telemetry while armed, plus one step for each missed statistics packet (`:121–136`); a link loss while armed or the Boost switch, maximum (`:106–113`). Steps are added one per evaluation, so the code does not guarantee that the power is already at maximum by the time of the S + 10 = −98 dBm warning. For the budget, assume there is no power headroom left in the transmitter at that point: the budget is calculated at the maximum configured power, not the average.

**LQ or RSSI?** RSSI is the early indicator: it shows the margin in dB while LQ is still 100 %. LQ is the share of packets that arrived: it stays near 100 % almost until the threshold and then falls sharply, and it also falls from interference with a good RSSI. An RSSI alarm warns about range, an LQ alarm that the link is already breaking up, for whatever reason. You need both. On the transmitter these are the sensors `1RSS`/`2RSS` (dBm for the two antennas), `RQly` and `RSNR` (`tx-lua-widgets`). If the receiver outputs RSSI on a channel (CRSF output not in 16-channel mode: LQ on CH15, RSSI on CH16; in the code these are the fields `ch14` and `ch15`, counting from zero), the 0…100 % scale runs from the mode's sensitivity to −50 dBm (`src/src/rx-serial/SerialCRSF.cpp:63`). So 0 % on that channel means "signal at the threshold", not "no signal".

{{lesson:link-elrs|The mode table, telemetry ratio, LBT and Dynamic Power in full, in the place where the mode for the job is chosen.}}

### The ground: two rays, the Fresnel zone and the radio horizon
The FSPL formula assumes empty space. Near the ground, a reflected ray adds to the direct one; at grazing angles the reflection is almost total, with a phase reversal (coefficient ≈ −1). While the path difference between the rays is small compared with the wavelength, they cancel each other. The two-ray ground reflection model gives a breakpoint at **d_c = 4·h₁·h₂/λ**. Before it, the received power oscillates around free space: nulls and gains of up to +6 dB. After it, the power falls at 40 dB per decade instead of 20, that is 12 dB per doubling of range instead of 6. At 2.44 GHz (λ = 0.123 m) with the transmitter antenna at a height of 1.5 m, the practice script gives:

| Aircraft height | Breakpoint d_c | Extra loss at 5 km | at 10 km |
|---|---|---|---|
| 10 m | 0.49 km | +10.3 dB | +16.3 dB |
| 30 m | 1.47 km | +1.0 dB | +6.8 dB |
| 120 m | 5.86 km | −5.7 dB | −4.0 dB |

For the module's example this changes everything. In free space the margin at 10 km is 9.8 dB. At a height of 10 m the −98 dBm warning comes already at ≈ 3.9 km and the −108 sensitivity at ≈ 6.9 km; at 120 m, at ≈ 12.9 and ≈ 23.6 km. Before the breakpoint at 120 m there are narrow interference nulls (around 1, 1.5 and 2.9 km); in the ideal model each of them goes below the −108 dBm sensitivity, and closer than 1 km such nulls come even more often (0.73, 0.57 km and so on). The aircraft passes through them in seconds, and they cause short LQ dips at medium range. Real ground (grass, unevenness) reflects less than the ideal one, so the nulls are shallower, but the breakpoint and the 40 dB per decade slope remain (inferred from the model). Hence the rule: fly the aircraft higher and put the ground antenna higher. A transmitter antenna on a 3 m mast instead of 1.5 m moves the breakpoint out by a factor of two.

{{diagram:chart-link-two-ray|The module's example at 2.4 GHz: flying at 10 m, the ground reflection eats 10 dB at 5 km, and the −98 dBm warning comes at 3.9 km instead of 10 km; at 120 m the breakpoint moves beyond 5.9 km, and only short nulls remain.}}

**The Fresnel zone.** The radius of the first zone is r₁ = √(λ·d₁·d₂/d); at mid-path r₁ = 17.32·√(d/(4f)) m, with d in km and f in GHz (17.32 = √300). At 2.44 GHz that is 5.5 m at 1 km, 12.4 m at 5 km, 17.5 m at 10 km. The rule: keep at least 60 % of the first zone clear, preferably 80 %. On a 5 km path nothing at mid-path should rise above the line of sight minus 7.4 m. Example: the transmitter antenna at 2 m, the aircraft at 20 m: the line of sight at mid-path is at a height of ≈ 11 m. A 15 m forest there blocks not the Fresnel zone but the line of sight itself; for 60 % of the zone to be clear, the treetops must be below ≈ 11 − 7.4 ≈ 3.6 m.

**The radio horizon.** d = √(2kRh₁) + √(2kRh₂), where R = 6371 km and k = 4/3 is the standard refraction; in convenient units d ≈ 4.12·(√h₁ + √h₂) km with h in meters. A transmitter at 2 m and an aircraft at 30 m see each other out to 28.4 km, at 120 m out to 51 km. If the aircraft has gone beyond the horizon or behind a hill, the link drops abruptly while FSPL still shows margin.

### Why the calculation does not match the field
Multipath (ground reflections adding out of phase), obstacles in the Fresnel zone (the first-zone radius at 2.4 GHz at 5 km is ~12 m: flying low near the ground costs 6–20 dB), onboard interference (lowers the effective sensitivity), the real orientation of the antennas. That is why a range test is mandatory and a 10–15 dB margin is the minimum.

### Reference: formulas, constants, thresholds

| Quantity | Formula or value | Module example | Source |
|---|---|---|---|
| Power in dBm | 10·lg(P, mW) | 250 mW = 24.0 dBm | definition |
| EIRP | P_tx + G_tx − L_cable | 25 dBm ≈ 316 mW | definition |
| FSPL | 20·lg d(km) + 20·lg f(MHz) + 32.44 | 10 km, 2440 MHz: 120.2 dB | Friis formula |
| Range at margin M | d = 10^((EIRP + G_rx − L_extra − S − M − 20·lg f − 32.44)/20) | M = 12 dB: 7.8 km | from FSPL |
| Sensitivity | −174 + 10·lg B + NF + SNR_min | SF8, 500 kHz, NF 6: −121 dBm | kTB; SX1276 Rev. 7, Table 13 |
| ELRS 2.4 GHz (SX1280) | 50 Hz −115, 100 Full and 150 Hz −112, 250 Hz −108, 333 Full and 500 Hz −105, F1000/F500/D500/D250 −104 dBm | 250 Hz: −108 | ELRS 4.1.0 `common.cpp:94–103` |
| ELRS 900 MHz (SX127x) | 25 Hz −123, 50 Hz −120, 100 Hz −117, 100 Full and 200 Hz −112, D50 −112 dBm | — | ELRS 4.1.0 `common.cpp:17–23` |
| Fresnel zone (mid-path) | 17.32·√(d/(4f)) m | 5 km: 12.4 m, ≥ 60 % clear | geometry |
| Two-ray breakpoint | 4·h₁·h₂/λ | 1.5 and 10 m: 0.49 km | two-ray model |
| Radio horizon | 4.12·(√h₁ + √h₂) km | 2 and 120 m: 51 km | k = 4/3 |
| Dynamic Power, RSSI branch (FLRC/DVDA) | + one step at RSSI < S + 15, − at RSSI > S + 21 and LQ ≥ 95 % | S −104: −89 / −83 dBm | ELRS 4.1.0 `dynpower.cpp:166–189` |
| Dynamic Power, SNR branch (all LoRa) | raise on SNR deficit only at RSSI ≤ S + 21 or LQ ≤ 95 %; always: LQ ≤ 85 % → + one step, LQ ≤ 50 % or −20 vs the average → maximum | 250 Hz: −87 dBm | ELRS 4.1.0 `dynpower.cpp:17–28, 154–157, 239, 252` |
| Fade margin | 10–15 dB minimum, 20 dB comfortable | — | course guideline |
| Warning threshold | S + 10 dB on RSSI and LQ < 70 % | 250 Hz: −98 dBm | course guideline |

{{diagram:link-budget-chain|The worked budget example: ELRS 2.4 GHz, 250 mW, 10 km: a received power of −98 dBm against a sensitivity of −108 dBm gives a 10 dB margin.}}

{{diagram:chart-link-margin|Received power from the free-space formula against the ELRS sensitivity thresholds (the table in the link-elrs module). The margin is the distance from the curve to the threshold; a real flight needs 10–15 dB for fading, antenna turns and the aircraft body.}}

{{widget:link-margin}}

### Where it fits in the system

- **Takes in:** antenna gains, polarization and cable losses (`rf-antennas`); the receiver sensitivity per mode (`link-elrs`); the permitted power (`f-regulations`); onboard interference that lowers the sensitivity (`el-emi`).
- **Puts out:** the margin in dB and the expected range to the range requirement (`eng-method-101`); the RSSI and LQ warning thresholds on the transmitter; the choice of packet rate and power (`link-elrs`).
- **If you get this wrong:** a budget calculated without polarization, the Fresnel zone and antenna orientation → a margin around zero, the link breaks up and the failsafe triggers far from home (`bf-failsafe`, `ap-safety-fs`). Only RC calculated → the 5.8 GHz video runs out first, and the pilot is left without a picture while control is still alive (tree 5 in `diag-troubleshooting`, `link-digital-video`).

## practice
### Step 1. RC budget table
For your link: power, mode and its sensitivity, antennas, cables. Calculate the margin at 1, 3, 5, 10 km. Find the range at which the margin = 12 dB: that is your working limit (a course guideline: 12 lies inside the 10–15 dB minimum range, closer to its lower end, because it is the boundary up to which you fly, not a target for the whole flight; the same 12 as in `link-elrs`).

### Step 2. Video budget table
The same for the video system with the real sensitivity of the receiver/goggles. Compare the limits: which fails first.

### Step 3. Budget script: free space, ground, horizon
It is easier to calculate the table from steps 1–2 with a script than by hand: then a change of mode or antenna is recalculated in a second. The script below takes the example from the theory (ELRS 2.4 GHz, 250 Hz, S = −108 dBm, 250 mW, 2 and 0 dBi antennas, 1 dB of cable, 3 dB of polarization) and calculates: EIRP, the margin by distance, the range at a margin of 12 and 0 dB, the sensitivity from noise against the ELRS table, the Fresnel zone, the radio horizon, the ground reflection loss and the Dynamic Power thresholds for the RSSI branch (FLRC) and the SNR branch (LoRa). It needs only Python 3, no packages. Save it as `link_lab.py` and run `python3 link_lab.py`.

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

Script output (Python 3, run while preparing the module):

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

How to read the output. Item 2 is free space: the 12 dB margin runs out at 7.8 km, zero at 30.9 km. Item 6 says that at a height of 10 m, 10.3 dB of loss is added by 5 km: the 15.8 dB margin turns into 5.5 dB, below the 10–15 minimum. Item 3 shows that the ELRS table is not "marketing": it is 0.5–4 dB more cautious than the physics. Block 7 reminds you that the 250 Hz (LoRa) mode has no RSSI-based power-raise threshold: the SNR branch works with a −87 dBm gate, and the pair of RSSI thresholds belongs to the FLRC/DVDA modes. Now change the inputs to your own (`P_TX`, the antennas, the `S` of your mode, `F_MHZ`: 915 for 900 MHz, 5800 for video) and save the output next to the aircraft's logbook. For the 150 Hz mode (S = −112) all margins grow by 4 dB: that is the worked example below.

### Step 4. Thresholds
Set the RSSI dBm warning = S + 10 and the LQ warning on the transmitter; record them in the aircraft's logbook. The failsafe in the firmware has been tested.

### Step 5. Field test
A straight-line flight recording RSSI/LQ in the transmitter or FC log at 500 m, 1, 2 km (within the permitted limits and area). Compare the measured RSSI with the calculated P_rx for the same distances: the difference is your "reality correction", usually 5–10 dB.

Procedure and abort. Before the flight: the failsafe has been tested on the ground (transmitter off → return or land mode in the log), the S + 10 and LQ < 70 % warnings sound on the transmitter, the power is at the maximum configured, the flight altitude is constant and recorded (item 6 of the script depends on it). Abort: at the first RSSI or LQ voice warning, turn back, with no "just a little more". If the RSSI at 500 m is already 15 dB or more worse than calculated, land and find the cause (antenna, connector, polarization), instead of flying the next leg.

### Worked example and what to record
The module's example: ELRS 2.4 GHz, 250 mW (24 dBm), 2 and 0 dBi antennas, 4 dB of losses (cables and polarization), the 150 Hz mode sensitivity of −112 dBm. Free-space loss at 1 km and 2440 MHz: 20·log10(1) + 20·log10(2440) + 32.44 ≈ 100.2 dB. Received power 24 + 2 + 0 − 4 − 100.2 ≈ −78 dBm, a margin of ≈ 34 dB. Each doubling of distance takes 6 dB off: a 12 dB margin remains at ≈ 12–13 km, which is the theoretical limit in free space. The same calculation is in the link budget widget above.
- **RC and video table:** distance, FSPL, received power, margin. Mark the distance where the margin drops to 12 dB. Usually the video gives out first, not the RC; check whether that holds for you.
- **Thresholds on the transmitter.** RSSI warning = sensitivity + 10 dB (here −102 dBm), and LQ. Record the values in the aircraft's logbook.
- **Field test.** The measured RSSI at 500 m, 1 and 2 km is usually 5–10 dB worse than calculated: the ground, the Fresnel zone, the airframe, antenna orientation. That difference is your correction; subtract it from the calculated range for this aircraft.

Self-check: the lab is done when your table with the inputs of the worked example gives its numbers (1 km: FSPL ≈ 100.2 dB, received power ≈ −78 dBm, margin ≈ 34 dB, a 12 dB margin at ≈ 12–13 km), the budget is calculated for RC and video with the 12 dB margin distance, the field test produced a "calculation versus measurement" table with a correction (usually 5–10 dB; if more, look for the cause in onboard interference, antenna orientation or low flight in the Fresnel zone), and the RSSI warning threshold = sensitivity + 10 dB is set on the transmitter and recorded in the logbook. For the step 3 script (the path without hardware): with the example inputs your output matches the reference to 0.1 dB: a 29.8 dB margin at 1 km and 9.8 dB at 10 km, a 12 dB margin at 7.8 km, a 0.49 km breakpoint and +10.3 dB at 5 km for a height of 10 m, a 51.0 km radio horizon for 2 and 120 m, and in block 7 the −89 / −83 dBm thresholds for FLRC (S −104) and the single −87 dBm threshold for LoRa 250 Hz.

**Reference answer for self-check.** The correct result is the numbers of the step 3 output and of the worked example. Typical mistakes: (1) the margin at 10 km came out as ≈ 13 dB instead of 9.8, meaning the 3 dB of polarization was forgotten (if the 1 dB of cable is forgotten too, ≈ 14 dB); (2) FSPL at 1 km ≈ 40 dB, meaning the frequency was entered in GHz instead of MHz (the formula with 32.44 requires MHz and km); (3) the range at a 12 dB margin ≈ 60 km instead of 7.8, meaning the 17.8 dB margin difference was divided by 10 instead of 20 (range grows as 10^(ΔM/20)). If the field RSSI at a height of 10 m is 10 dB worse than the free-space calculation by 5 km, that is not a defect but item 6 of the script: compare the field with the two-ray model for your altitude.

## diagnostics
- **Symptom:** RSSI falls faster than calculated from the very start
  - Possible cause: cable/connector losses, polarization, an antenna under carbon.
  - What to do: check the SWR, the pigtails, the orientation.
- **Symptom:** the link breaks up at the same range despite a good RSSI
  - Possible cause: onboard interference lowers the effective sensitivity; LQ drops earlier.
  - What to do: watch LQ, see the interference module.
- **Symptom:** in the field the margin is 10 dB worse than calculated
  - Possible cause: low flight: obstacles in the Fresnel zone, multipath.
  - What to do: higher altitude, a higher ground antenna, a directional antenna.
- **Symptom:** the video is lost, the RC holds
  - Possible cause: the video budget ran out first (expected at 5.8 GHz).
  - What to do: a patch on the ground, more power, another band; RTH on video loss.
- **Symptom:** LQ dips at the same medium range (1–3 km) and then recovers
  - Possible cause: an interference null between the direct and the ground-reflected ray (the two-ray model), a low transmitter antenna.
  - What the log shows: a 10–20 dB dip in `RQly` and `1RSS` over a short stretch, at the same range on every flight at the same altitude.
  - What to do: raise the ground antenna (a 3 m mast moves the breakpoint out by a factor of two), change the flight altitude; enable antenna diversity if the receiver has two antennas.
- **Symptom:** the link dropped instantly, although a second earlier RSSI was 10 dB above the threshold
  - Possible cause: the aircraft went beyond the radio horizon, behind a hill or a forest: there is no line of sight, and FSPL no longer applies.
  - What to do: check the horizon 4.12·(√h₁ + √h₂) km and the terrain profile along the path; plan the far leg at a higher altitude.
- **Symptom:** a CE build has noticeably less range than calculated
  - Possible cause: the budget was calculated for 250 mW or more, while the build limits 2.4 GHz to 100 mW at the module output (with a 2 dBi antenna that is already ≈ 125 mW EIRP, which is why the module is set to ≈ 80 mW for a 100 mW EIRP limit, see the EIRP section).
  - What to do: recalculate the budget for the actual power; −4 dB (from 250 to 100 mW) means range ×0.63.
  - Consequence: the failsafe comes earlier than the calculation suggests.

## references
- ExpressLRS 4.1.0 — source: `src/src/common.cpp` (RXsensitivity per mode), `src/src/dynpower.cpp` (Dynamic Power thresholds), `src/src/rx-serial/SerialCRSF.cpp` | https://github.com/ExpressLRS/ExpressLRS/tree/4.1.0/src/src | primary | A
- Semtech SX1276/77/78/79 datasheet Rev. 7 (Table 13: LoRa demodulator SNR per SF) | https://cdn.sparkfun.com/assets/7/7/3/2/2/SX1276_Datasheet.pdf | primary | A
- ExpressLRS — Signal Health (sensitivity per mode, RSSI/LQ) | https://www.expresslrs.org/info/signal-health/ | primary | A
- ExpressLRS — Long Range Competition / range considerations | https://www.expresslrs.org/info/long-range/ | primary | A
- Free-space path loss — Wikipedia (formula and derivation) | https://en.wikipedia.org/wiki/Free-space_path_loss | secondary | B
- Two-ray ground-reflection model — Wikipedia (critical distance, d⁻⁴ far field) | https://en.wikipedia.org/wiki/Two-ray_ground-reflection_model | secondary | B
- Fresnel zone — Wikipedia (radius, 60 / 80 % clearance rule) | https://en.wikipedia.org/wiki/Fresnel_zone | secondary | B
- Radio horizon with 4/3 effective Earth radius — continuousWave | https://www.continuouswave.com/radio/radioHorizon.html | secondary | B

## checklist
- I can convert mW to dBm and calculate FSPL
- The RC and video budgets are calculated with range margin
- The RSSI warning threshold is set from the mode's sensitivity
- The field test has been compared with the calculation and the correction recorded
- I know that video usually limits range before RC
- I take the flight altitude into account (the two-ray breakpoint, the Fresnel zone) and the radio horizon, and calculate the budget at the maximum Dynamic Power and within the EIRP limit
