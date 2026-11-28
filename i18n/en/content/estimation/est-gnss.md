---
id: est-gnss
title: "GNSS: how GPS works, errors, RTK"
level: L2
readingTime: 50 min
firmware: ArduPilot 4.7 (checked against 4.7.3; the lab was captured on SITL 4.7.2) · PX4 1.18 (parameters checked against v1.18.0) · u-blox M8/M9/M10/F9
status: published
added: 2026-11-08
tags:
  - GNSS
  - GPS
  - HDOP
  - RTK
  - u-blox
related:
  - f-fc-sensors
  - el-emi
  - est-kalman
  - nav-resilience
next:
  - ap-ekf
source: content/estimation/est-gnss.md
source_hash: 750f5951a895
---

## summary
For an autopilot, GPS is not "a dot on the map" but a noisy measurement with a known (and changing) error. This module explains how the receiver obtains pseudoranges and solves for position by least squares, where the errors come from (ionosphere, multipath, satellite geometry, HDOP), what multiple constellations (GPS, GLONASS, Galileo, BeiDou) give you, how to choose a receiver and antenna, which u-blox settings matter for flight (rate, constellations, dynamic model, SBAS), which quality thresholds EKF3 and EKF2 check before arming, and what RTK/PPK are, when you need them and when you do not. The lab: a position and DOP solution on a sky model, pre-arm checks in ArduCopter 4.7.2 SITL, then GPS quality in different conditions from a log.

## theory
### The principle
Each satellite broadcasts time and its orbit; the receiver measures the signal delay → **pseudorange** (range + receiver clock error). Four unknowns (x, y, z, Δt) → at least 4 satellites; more is better (redundancy, quality estimation). At the input the signal is weaker than the noise and is extracted by correlation with a known code.

Numbers for L1 C/A per IS-GPS-200N: the minimum received power at the ground is −158.5 dBW, that is −128.5 dBm; the 1023-chip code runs at 1.023 Mchip/s and repeats every 1 ms. Thermal noise in a 2 MHz band is −174 + 10·lg(2·10⁶) ≈ −111 dBm, so the signal is 17.5 dB below the noise. Correlating with the code over 1 ms narrows the effective bandwidth from 2 MHz to the order of 1 kHz: a gain of 10·lg(2·10⁶ × 0.001) = 33 dB, and the post-correlation SNR is ≈ 15.5 dB. The same through C/N0, which does not depend on the input bandwidth: C/N0 = −128.5 + 174 = 45.5 dB-Hz, and with an integration time T = 1 ms, SNR = C/N0 + 10·lg T = 45.5 − 30 = 15.5 dB. Each doubling of the integration time adds 3 dB; that is how the receiver keeps tracking weak satellites. The tracking sensitivity of u-blox M9/M10 per the datasheets is −167 dBm. Hence the fragility: interference from a VTX or USB 3.0 ten-odd decibels above thermal noise eats this whole margin (`el-emi`).

### How the receiver solves for position
For satellite i at a known position sᵢ the measurement is ρᵢ = |sᵢ − x| + c·Δt + εᵢ. The receiver clock is a quartz crystal, and its error is huge: 1 ms is 300 km. So Δt is the fourth unknown, on a par with the coordinates. The equations are nonlinear. The receiver linearizes them around the current estimate and solves by least squares, repeating 2–4 times (Gauss–Newton). The row of the geometry matrix G for a satellite is [−eₓ, −e_y, −e_z, 1], where e is the unit vector toward the satellite.

**DOP.** If all pseudoranges have the same error σ (UERE, user equivalent range error), the covariance of the solution is σ²·(GᵀG)⁻¹. Let Q = (GᵀG)⁻¹. Then HDOP = √(Q₁₁ + Q₂₂), VDOP = √Q₃₃, PDOP = √(Q₁₁ + Q₂₂ + Q₃₃). The horizontal error is ≈ HDOP·σ. The lab checks the formula on 2000 solutions: 2.52 m against HDOP·σ = 2.47 m under open sky, 10.40 m against 10.45 m next to a wall. VDOP is almost always larger than HDOP: all satellites are above the horizon, none below. That is why GNSS altitude is 1.5–2 times worse than horizontal position.

### Errors and their size (single-frequency receiver, good conditions)
| Source | Error | How to reduce it |
|---|---|---|
| Ionosphere | 2–5 m | dual frequency (L1+L5/L2), SBAS corrections |
| Troposphere | 0.5–1 m | model |
| Satellite orbit/clock | 1–2 m | SBAS |
| Multipath (reflections from buildings, the ground, the frame) | 1–10+ m, in jumps | an antenna with a ground plane, higher above the frame, away from structures |
| Geometry (DOP) | multiplier ×1–×5 | many satellites across the whole sky |
| Receiver noise | 0.3–1 m | a good antenna, no interference |

Total: 1.5–3 m (CEP) in the open, 5–20 m in a city. The u-blox datasheets give 1.5 m CEP for the M9N with SBAS and for the M10 in multi-constellation mode, and 2.5 m for the NEO-M8N on GPS + GLONASS without SBAS. **Velocity** from Doppler is much more accurate, 0.05–0.2 m/s (0.05 m/s in the M8N and M10 datasheets); the EKF relies on it more than on position.

### DOP: geometry
HDOP (horizontal) is the error multiplier from the satellite layout: all satellites on one side of the sky → bad. < 1 is excellent, 1–2 is good; above the threshold ArduPilot will not arm in GPS modes (`GPS_HDOP_GOOD`, stored as HDOP × 100; the default 140 = 1.4). The satellite count is a crude indicator: 6 is the minimum, 12+ is normal with several constellations.

The lab's sky model shows why the satellite count misleads: 10 satellites across the whole sky give HDOP 0.82. A wall blocks the southern half of the sky (a 180° sector): 6 satellites remain, and HDOP rises to 3.48, a factor of 4.2. Four satellites low in the north give HDOP 3.98. While the blocked sector is up to 90°, HDOP barely changes (0.82–0.95). Beyond that it grows faster than the satellite count falls.

{{diagram:chart-gnss-hdop-wall|A 180° wall removes 4 of 10 satellites, while HDOP rises from 0.82 to 3.48, above the ArduPilot 1.4 threshold and the EKF3 2.5 threshold; the satellite count falls slowly, the geometry sharply.}}

### Constellations
GPS (USA, L1 C/A), GLONASS (Russia), Galileo (EU, L1 + E5), BeiDou (China). A multi-constellation receiver (u-blox M8/M9/M10, F9P) sees 20–30 satellites instead of 8–10: better DOP, faster fix, more robust when part of the sky is blocked. The price is processing load and update rate, and it differs between generations (per the datasheets):

- **NEO-M8N:** up to 3 constellations concurrently; 5 Hz on GPS + GLONASS, 10 Hz on a single constellation.
- **NEO-M9N:** 4 constellations concurrently, and still up to 25 Hz.
- **MAX-M10S:** by default GPS + Galileo + BeiDou B1I at just 3 Hz; GPS + Galileo at 10 Hz; in high-performance mode (configuration required) 10–20 Hz depending on the set. BeiDou B1I cannot be enabled together with GLONASS. The M10 is power-efficient, but "25 Hz on four constellations" describes the M9, not the M10.
- **ZED-F9P:** dual frequency, RTK up to 20 Hz.

For an autopilot 5–10 Hz is enough, so an M10 at 5 Hz with two or three constellations is a sound choice.

**Which receiver to buy (no RTK).** The course rule, based on the datasheets above:
- **M10** is the default choice: 10 Hz on GPS + Galileo, 1.5 m CEP in multi-constellation mode, low power. The limitation is that the rate depends on the set and the mode: with three including BeiDou B1I the default is only 3 Hz, with four (GPS + Galileo + BeiDou B1C + GLONASS) 4 Hz, and 10 Hz on four only in high-performance mode, which you have to enable (Table 2 of the MAX-M10S datasheet; see diagnostics below).
- **M9N** if you need all four constellations at 10 Hz without a special mode or configuration: a partly blocked sky (city, forest, slopes), where extra satellites improve DOP. Its up to 25 Hz is of no use to an autopilot (the EKF gains nothing above 10 Hz, see "Rate" below); the M9N's advantage is that 4 constellations at 10 Hz work out of the box.
- **M8N** only if it is already installed: 5 Hz on two constellations, worse accuracy (2.5 m CEP without SBAS); it does not justify a new purchase.
- **F9P** only for RTK or dual-antenna heading (`nav-rtk`); without corrections its dual frequency gives less than it costs.

The antenna and its place on board are a separate rule (the "Antenna" subsection below). Checking the choice: after 5 minutes in the open, the satellite count, HDOP and `GPA.HAcc` in the log; the message rate from `GPS1_RATE_MS` and the actual intervals in the log.

### Antenna
A 25×25 mm ceramic patch on a ground plane is the standard; helical antennas have circular polarization, handle multipath better and need no ground plane. The rule: antenna on top, on a mast, nothing metallic nearby, a ground plane ≥ 40 mm for a patch. An active antenna (with an amplifier) is for a long cable.

### u-blox settings that matter
- **Rate**: 5–10 Hz for a copter (ArduPilot `GPS1_RATE_MS = 200` → 5 Hz, allowed 50–200 ms; before 4.6, `GPS_RATE_MS`; the EKF does not need more than 10 Hz, and it overloads the UART/CPU). The UART baud rate for the chosen rate: the load calculation is in `el-peripherals`, "How much fits on the line" (ArduPilot 4.7.3 switches a u-blox to 230400 by itself).
- **Dynamic model**: Airborne < 1g/2g/4g tunes the receiver's internal filter to the dynamics; Pedestrian/Automotive are bad for a drone (they smooth and lag). ArduPilot sets `GPS_NAVFILTER` (default 8, Airborne4G); PX4 sets `GPS_UBX_DYNMODEL` (default 7, airborne with <2g acceleration).
- **Constellations** (`GPS1_GNSS_MODE`, before 4.6 `GPS_GNSS_MODE`; bitmask: 0 GPS, 1 SBAS, 2 Galileo, 3 BeiDou, 5 QZSS, 6 GLONASS; 0 leaves the receiver configuration alone): GPS + Galileo + GLONASS or GPS + Galileo + BeiDou, not all four at once on an M8 (the rate drops). Which third one (a course guideline): besides its medium-orbit satellites, BeiDou has geostationary and IGSO satellites over the Asia-Pacific region, so it wins there; GLONASS orbits are inclined at 64.8° against 55–56° for GPS and Galileo, so at high latitudes its satellites stand higher above the horizon. A test at your own site decides: the satellite count and HDOP from NAV-SAT or the log with each set, at the same rate.
- **SBAS** (`GPS_SBAS_MODE`, default 2, NoChange, leaves the receiver setting alone): WAAS/EGNOS corrections are slightly more accurate, but in some regions they get in the way; enable them where there is coverage.
- **Messages**: UBX (binary) instead of NMEA is more compact, more precise and carries quality status; ArduPilot configures a u-blox receiver by itself with `GPS_AUTO_CONFIG = 1`.

### RTK and PPK
**RTK** (Real-Time Kinematic): a base station at a known position sends carrier-phase corrections (RTCM) to the rover receiver over a radio or 4G link; accuracy is 1–3 cm with a fix (RTK Fixed status), 10–50 cm with a float. In practice it needs a dual-frequency receiver (F9P, UM982) at both ends (single-frequency L1 RTK, e.g. NEO-M8P, works only on short baselines and fixes slowly), your own base within ~10–20 km (an NTRIP network is usable up to 50–100 km at the cost of 1 ppm accuracy and slower convergence, see nav-rtk), and a continuous link. **PPK** is the same but post-processed from logs: it is for photogrammetry, not for flight control.

When you need RTK: precision landing, surveying, moving baseline for heading (two GPS units → yaw without a compass: ArduPilot "GPS for yaw", base `GPS_TYPE = 17`, rover `GPS_TYPE2 = 18`; in 4.6+ `GPS1_TYPE`/`GPS2_TYPE`). When you do not: ordinary waypoint flying (the EKF and a 2 m error are enough), FPV. RTK does not fix multipath or losing satellites under a roof.

{{diagram:gnss-rtk-choice-tree|You need RTK only when the task needs centimeters in flight; for waypoint flying the 1.5–3 m of ordinary GNSS is enough, and photogrammetry needs PPK.}}

### How GPS feeds the EKF
The EKF receives position, velocity, their accuracy estimates (`GPA.HAcc/VAcc/SAcc`) and the delay: the measurement is "old," and the EKF matches it against a past state. In ArduPilot 4.7.3 `GPS1_DELAY_MS` defaults to 0, which means "use the driver's delay": 120 ms for u-blox M8/M9/M10/F9, another +40 ms in moving-baseline mode, 220 ms for older and unidentified receivers (`AP_GPS_UBLOX.cpp:2236–2276`). A nonzero parameter value always overrides the driver. In PX4 1.18 the delay is set per receiver: `SENS_GPS0_DELAY` and `SENS_GPS1_DELAY` = 110 ms, with the receiver binding in `SENS_GPS0_ID` (before 1.18, a shared `EKF2_GPS_DELAY`, migrated on upgrade); with active PPS synchronization the PPS correction takes precedence over the parameter. Glitch protection is the innovation gate (see the Kalman filter module).

**Pre-arm checks happen at two levels.** The first is EKF3: until GPS passes them, the filter does not use GPS, home is not set, and arming in position modes is refused. `EK3_GPS_CHECK` defaults to 31, bits 0–4 (`AP_NavEKF3_VehicleStatus.cpp:24–187`):

- satellites ≥ 6;
- HDOP ≤ 2.5;
- receiver speed error ≤ 1.0 m/s;
- hAcc ≤ 5 m and vAcc ≤ 7.5 m;
- compass yaw consistency.

Bits 5–7 are position drift on the ground ≤ 3 m and vertical and horizontal speed on the ground ≤ 0.3 m/s. `EK3_CHECK_SCALE`/100 (default 100%) multiplies only the accuracy and motion thresholds: hAcc, vAcc, speed error, drift and the on-ground speeds; the satellite count (6) and HDOP (2.5) are hard-coded and not scaled (`AP_NavEKF3_VehicleStatus.cpp:66–187`: HDOP at line 170, satellites at 182). Once the checks have passed, the scaler is further multiplied by 1.3 as hysteresis, so arming readiness does not flicker (`:26–34`). The second level is Copter: if the mode requires GPS, HDOP must not exceed `GPS_HDOP_GOOD` (1.4), otherwise "High GPS HDOP" (`AP_Arming_Copter.cpp:396`). The Copter threshold is stricter than the EKF3 one: at HDOP 2.0 the EKF accepts GPS, but arming in Loiter is still refused.

What this looks like in ArduCopter 4.7.2 SITL (practice step 2): with 5 satellites and with hAcc 6 m, arming is refused with "PreArm: AHRS: waiting for home". The message names the consequence (there is no home because EKF3 did not take GPS), not the cause. Find the cause by comparing `GPS_RAW_INT` with the thresholds above. With 6 satellites and hAcc 4.5 m the vehicle arms. With `GPS_HDOP_GOOD = 110` and HDOP 1.21 you get "Arm: High GPS HDOP".

**PX4 1.18.0** checks the same in EKF2: `EKF2_GPS_CHECK` defaults to 2047 (bits 0–10; bit 11, Jamming, is new in 1.18 and off by default), `EKF2_REQ_NSATS` 6, `EKF2_REQ_PDOP` 2.5 (PDOP, not HDOP; for fixed-wing since 1.18 it is 4.0 from `rc.fw_defaults`), `EKF2_REQ_EPH` 3 m, `EKF2_REQ_EPV` 5 m, `EKF2_REQ_SACC` 0.5 m/s, drift 0.1/0.2 m/s, `EKF2_REQ_FIX` 3; all of this must hold for `EKF2_REQ_GPS_H` = 10 s in a row.

| Parameter | Firmware | Default | Old name / note |
|---|---|---|---|
| `GPS1_TYPE` | ArduPilot 4.6+ | 1 AUTO (2 uBlox, 17/18 MB base/rover) | `GPS_TYPE` before 4.6 |
| `GPS1_RATE_MS` | ArduPilot 4.6+ | 200 ms (5 Hz), 50–200 | `GPS_RATE_MS` |
| `GPS1_GNSS_MODE` | ArduPilot 4.6+ | 0 (leave as configured) | `GPS_GNSS_MODE` |
| `GPS1_DELAY_MS` | ArduPilot 4.6+ | 0 → driver: 120 ms (M8–F9), 220 ms (older) | `GPS_DELAY_MS` |
| `GPS1_POS_X/Y/Z` | ArduPilot 4.6+ | 0 m | `GPS_POS1_X/Y/Z` |
| `GPS_NAVFILTER` | ArduPilot | 8 Airborne4G | 6/7 Airborne1G/2G, 3 Pedestrian, 4 Automotive |
| `GPS_AUTO_CONFIG` | ArduPilot | 1 (serial only) | 2 also DroneCAN |
| `GPS_SBAS_MODE` | ArduPilot | 2 (NoChange) | 0 Disabled, 1 Enabled |
| `GPS_HDOP_GOOD` | ArduPilot Copter | 140 (HDOP 1.4) | 100–900 |
| `EK3_GPS_CHECK` / `EK3_CHECK_SCALE` | ArduPilot | 31 / 100% | thresholds: 6 sats, HDOP 2.5, 5 m, 1 m/s |
| `GPS_1_CONFIG`, `GPS_1_GNSS` | PX4 1.18.0 | port / 0 (receiver default) | bits: GPS, SBAS, Galileo, BeiDou, GLONASS, NAVIC |
| `GPS_UBX_DYNMODEL` | PX4 | 7 (airborne <2g) | 6 is <1g, 8 is <4g |
| `SENS_GPS0_DELAY` (before 1.18, `EKF2_GPS_DELAY`) / `EKF2_GPS_CTRL` | PX4 | 110 ms / 7 | bit 3 is dual antenna heading |
| `EKF2_GPS_CHECK`, `EKF2_REQ_*` | PX4 | 2047; 6 sats, PDOP 2.5, EPH 3 m | `EKF2_REQ_GPS_H` 10 s |

{{lesson:ap-ahrs-choice|What EKF3 does when GPS drops out: how many seconds until failsafe, how a plane behaves with and without an airspeed sensor (11 m against 96 m in a minute).}}

{{diagram:rtk-chain|An ordinary GNSS solution gives meters; RTCM corrections from a base at a known point give an RTK fix with centimeter accuracy.}}

### Where it fits

- **Receives:** a radio environment free of on-board interference around the antenna (`el-emi`); an antenna position on top with a ground plane (`rf-antennas`); a UART port or a CAN node (`el-peripherals`); RTCM corrections for centimeter accuracy (`nav-rtk`).
- **Provides:** position, Doppler velocity, accuracy estimates and the delay to the EKF (`est-kalman`, `ap-ekf`); course over ground while moving to the attitude filter (`est-attitude`); the satellite count and HDOP to the pre-arm checks.
- **If you get this wrong:** an antenna under carbon or next to the VTX → HDOP above the threshold, ArduPilot will not arm in GPS modes, and in flight you get a GPS glitch (`nav-resilience`). A Pedestrian or Automotive dynamic model in the receiver → the solution is smoothed and lags, and the EKF innovations grow during maneuvers (`ap-ekf`).

## practice
### Step 1. Solving for position and DOP by hand
The script builds a sky model of 10 satellites (azimuth and elevation), places them at a slant range of 22 000 km in a local ENU frame, adds a 1 ms clock error (300 km) and σ = 3 m noise to the pseudoranges, and solves for position by Gauss–Newton from a start 141 km from the truth. It then repeats for a "wall" (azimuths 90…270° blocked) and for four low satellites in the north, and checks HDOP·σ on 2000 solutions. Requires NumPy.

```python
"""est-gnss lab: pseudorange least squares, DOP from geometry, open sky vs a wall.
Local ENU frame, satellites at 22 000 km slant range; UERE sigma 3 m; receiver clock bias 1 ms."""
import math
import numpy as np

C = 299_792_458.0
SKY = [(0, 75), (40, 30), (85, 50), (130, 20), (175, 60), (220, 35), (260, 15), (300, 45), (335, 25), (20, 10)]
#        azimuth, elevation in degrees: 10 satellites spread over the whole sky


def unit(az, el):
    a, e = math.radians(az), math.radians(el)
    return np.array([math.cos(e) * math.sin(a), math.cos(e) * math.cos(a), math.sin(e)])   # E, N, U


def dop(sats):
    G = np.array([np.append(-unit(az, el), 1.0) for az, el in sats])
    Q = np.linalg.inv(G.T @ G)
    return math.sqrt(Q[0, 0] + Q[1, 1]), math.sqrt(Q[2, 2]), math.sqrt(np.trace(Q[:3, :3])), math.sqrt(np.trace(Q))


def solve(sats, rng, sigma=3.0, bias_s=1e-3, iters=6):
    truth = np.zeros(3)
    pos = np.array([unit(az, el) * 22_000e3 for az, el in sats])
    rho = np.linalg.norm(pos - truth, axis=1) + C * bias_s + rng.normal(0, sigma, len(sats))
    x = np.array([100e3, -100e3, 0.0, 0.0])            # E, N, U, c*dt; start 141 km off, zero clock
    for k in range(iters):
        r = np.linalg.norm(pos - x[:3], axis=1)
        H = np.hstack([-(pos - x[:3]) / r[:, None], np.ones((len(sats), 1))])
        dx = np.linalg.lstsq(H, rho - (r + x[3]), rcond=None)[0]
        x += dx
        if np.linalg.norm(dx) < 1e-3:
            break
    return x, k + 1


rng = np.random.default_rng(42)
for name, sats in (("open sky, 10 sats", SKY),
                   ("wall to the south (az 90..270 blocked)", [s for s in SKY if not 90 <= s[0] <= 270]),
                   ("4 sats, all low in the north", [(300, 15), (335, 25), (20, 10), (40, 30)])):
    h, v, p, g = dop(sats)
    x, n = solve(sats, rng)
    print(f"{name}: {len(sats)} sats, HDOP {h:.2f} VDOP {v:.2f} PDOP {p:.2f}")
    print(f"   one fix: E {x[0]:+6.2f} N {x[1]:+6.2f} U {x[2]:+6.2f} m, clock {x[3] / C * 1e3:.6f} ms, {n} iterations")
    errs = np.array([solve(sats, rng)[0][:3] for _ in range(2000)])
    sh = math.sqrt(np.mean(errs[:, 0] ** 2 + errs[:, 1] ** 2))
    print(f"   2000 fixes: horizontal RMS {sh:.2f} m  vs  HDOP*UERE = {h * 3.0:.2f} m")
```

Output (Python 3.13, NumPy 2.5.3):

```text
open sky, 10 sats: 10 sats, HDOP 0.82 VDOP 1.29 PDOP 1.53
   one fix: E  -0.93 N  +0.10 U  +1.29 m, clock 0.999999 ms, 4 iterations
   2000 fixes: horizontal RMS 2.52 m  vs  HDOP*UERE = 2.47 m
wall to the south (az 90..270 blocked): 6 sats, HDOP 3.48 VDOP 4.07 PDOP 5.36
   one fix: E  +7.62 N +11.36 U +11.70 m, clock 1.000050 ms, 4 iterations
   2000 fixes: horizontal RMS 10.40 m  vs  HDOP*UERE = 10.45 m
4 sats, all low in the north: 4 sats, HDOP 3.98 VDOP 4.30 PDOP 5.86
   one fix: E  -4.13 N +22.34 U +10.57 m, clock 1.000067 ms, 4 iterations
   2000 fixes: horizontal RMS 12.03 m  vs  HDOP*UERE = 11.94 m
```

What to read from it: the clock is recovered with an error of 1–67 ns (0.999999–1.000067 ms), so the 300 km of clock error went into the fourth unknown, not into the coordinates. Four iterations from a start 141 km away: the nonlinearity is weak. HDOP·σ matched the spread of 2000 solutions within 2%. The wall turned the same 3 m range error into 10 m horizontally, and four low satellites into 12 m. Look at the single solutions: next to the wall the error is 11 m north, along the north–south axis that the geometry barely constrains: all the remaining satellites are on one (northern) side, and a shift along this axis changes the ranges to all of them almost equally.

### Step 2. Pre-arm checks in SITL
ArduCopter 4.7.2 SITL with the standard `copter.parm`; the script `examples/sitl-nav-labs/gnss_prearm.py` (29 lines, pymavlink; run it with `./run_lab.sh g_sats5 - "SIM_GPS1_NUMSATS 5" gnss_prearm.py`, the other runs the same way, README in the folder) waits 40 s, then tries to arm in Loiter every 3 s and prints the messages and the `GPS_RAW_INT` fields. A baseline run and five runs, each changing one simulator or firmware parameter:

| Run | What changed | Result | Message |
|---|---|---|---|
| baseline | — | ARMED in LOITER | "EKF3 IMU0 is using GPS", "Arming motors" |
| 5 satellites | `SIM_GPS1_NUMSATS 5` | NOT armed | "PreArm: AHRS: waiting for home" |
| 6 satellites | `SIM_GPS1_NUMSATS 6` | ARMED in LOITER | "Arming motors" |
| hAcc 6 m | `SIM_GPS1_ACC 6` | NOT armed | "PreArm: AHRS: waiting for home" |
| hAcc 4.5 m | `SIM_GPS1_ACC 4.5` | ARMED in LOITER | "Arming motors" |
| HDOP threshold 1.1 | `GPS_HDOP_GOOD 110` | NOT armed | "Arm: High GPS HDOP" |

The end of the output of the "5 satellites" run:

```text
[ 40.0s] Arm: AHRS: waiting for home
[ 40.4s] PreArm: AHRS: waiting for home
GPS_RAW_INT: fix 6, sats 5, HDOP 1.21, h_acc 0.30 m
NOT armed after 60 s
```

The SITL u-blox simulator always reports HDOP 1.21 and the "carrier solution fixed" flag in NAV-PVT (`SIM_GPS_UBLOX.cpp:249, 264`), so `fix 6` (RTK fixed) is a SITL quirk; a real receiver without corrections will show 3. For the same reason the EKF3 HDOP threshold (2.5) cannot be tested in SITL, but the Copter threshold can, by lowering `GPS_HDOP_GOOD` below 1.21.

### Step 3. Do you need RTK?
For your task: do you need RTK? Justify it from the accuracy requirements (engineering folder): compare the required accuracy with the spread you will measure in the section below and with the decision tree in the theory.

### Moving to real hardware
Vehicle on the ground, props off, `LOG_DISARMED = 1`, 5 minutes at each of three spots: an open field; next to a house wall; under trees. From `GPS`: `NSats`, `HDop`, `Status`; from `GPA`: `HAcc`, `SAcc`. Make a table: the mean and the worst for each condition. In the second condition, plot the position (`GPS.Lat/Lng` → meters) over 5 minutes in place: the spread and the jumps. Compare with the field. Match the jumps against `XKF4.SP` in the log (the normalized position innovation, √test ratio) if the EKF was running. Check `GPS1_RATE_MS`, `GPS1_GNSS_MODE`, `GPS_NAVFILTER` (or their INAV/Betaflight counterparts: `gps_ublox_use_galileo` (on by default in INAV 9.1, off before 9.1), the dynamic model), `GPS_AUTO_CONFIG`. Record them in the build passport.

```python
import math, sys
from pymavlink import DFReader

log = DFReader.DFReader_binary(sys.argv[1])
pts, worst_hdop, min_sats = [], 0.0, 99
while (m := log.recv_match(type="GPS")) is not None:
    if m.Status < 3:                      # no 3D fix yet
        continue
    pts.append((m.Lat, m.Lng))
    worst_hdop, min_sats = max(worst_hdop, m.HDop), min(min_sats, m.NSats)
lat0, lon0 = pts[0]
xy = [((la - lat0) * 111_320, (lo - lon0) * 111_320 * math.cos(math.radians(lat0))) for la, lo in pts]
cx, cy = sum(p[0] for p in xy) / len(xy), sum(p[1] for p in xy) / len(xy)
r = sorted(math.hypot(x - cx, y - cy) for x, y in xy)
print(f"{len(r)} fixes, median {r[len(r) // 2]:.2f} m, p95 {r[int(len(r) * 0.95)]:.2f} m, max {r[-1]:.2f} m, "
      f"worst HDOP {worst_hdop:.2f}, min sats {min_sats}")
```

What you should get and what to record:

- **Open field:** many satellites (the normal threshold is 12 or more; a multi-constellation receiver in an open field usually sees 20–30), HDOP around 1 or lower, a spread in place of a meter or two. This is the reference the other conditions are compared with.
- **Next to a wall:** fewer satellites and a higher HDOP, but above all position jumps of meters from the reflected signal (multipath). The p95 and max spread grow several times over, even though the satellite count may stay decent. That is exactly why "lots of satellites" is no guarantee.
- **Under trees:** the signal is attenuated, the fix is lost more often (`Status` drops), and `HAcc` in `GPA` grows.
- **Settings:** record the actual values of the GNSS parameters for your ArduPilot version (in 4.6+ some receiver parameters have the `GPS1_` prefix, for example `GPS1_TYPE`; check against the table in the theory).

Abort conditions and safety: everything on the ground without props; if the vehicle must fly for the comparison, the first flight is in AltHold, and switch to Loiter only when HDOP ≤ 1.4 and there is no "GPS glitch".

Self-check: the lab is done when (calculation and SITL) the step 1 script gave HDOP 0.82 / 3.48 / 3.98 for the three skies and the spread of 2000 solutions matched HDOP·σ within 5%; in step 2 all six rows of the table were reproduced: 5 satellites and hAcc 6 m do not arm, with "waiting for home", 6 satellites and hAcc 4.5 m arm, and `GPS_HDOP_GOOD 110` gives "High GPS HDOP"; (hardware) HDOP, the satellite count and the position spread (median, p95 and max from the script) are recorded for three conditions, and in the open field they fall within the reference above: HDOP around 1 or lower, at least 12 satellites (20–30 is typical for a multi-constellation receiver, but the self-check threshold is 12), a spread in place of a meter or two; multipath is shown as a number: next to the wall p95 and max grew several times over relative to the field; the receiver settings are recorded in the passport; and the RTK decision follows from comparing the required accuracy with the measured spread: if ~2 m is enough for the task (waypoint flying, FPV), you do not need RTK; if you need centimeters (precision landing, surveying, dual-GPS heading), you do, and you have noted that it does not fix multipath or satellite loss.

**Reference for the self-check.**

| Check | Correct | Typical mistake and its cause |
|---|---|---|
| Open-sky HDOP | 0.82 | 1.53: you computed PDOP (added Q₃₃); 0.80: a 3 × 3 matrix without the clock column; estimating the clock also "uses up" redundancy, and without it HDOP comes out too low |
| Spread next to the wall | 10.4 m ≈ 3.48 × 3 m | 3 m: the noise was not multiplied by the geometry; "6 satellites by the wall, so twice as bad": satellite count instead of HDOP |
| Arming with 5 satellites | refused, "AHRS: waiting for home" | you expected "GPS numsats": that EKF3 text does not reach the arming message, which names the consequence |
| `GPS_HDOP_GOOD 110` | "Arm: High GPS HDOP" at HDOP 1.21 | confused with the EKF3 threshold 2.5: the EKF accepted GPS, the refusal comes from Copter |

## diagnostics
- **Symptom:** a long satellite search after power-on
  - Possible cause: cold start, antenna under carbon, interference from USB or the camera.
  - What to do: a mast, a ground plane, the EMI module; give it 1–2 minutes.
- **Symptom:** HDOP > 2 with 15 satellites
  - Possible cause: satellites on one side (a wall, a roof).
  - What to do: open sky; do not arm in GPS modes.
- **Symptom:** the position jumps by 10–30 m in a city
  - Possible cause: multipath.
  - What to do: higher above the frame, a helical antenna, do not trust Loiter near buildings.
- **Symptom:** "GPS glitch" in the ArduPilot messages
  - Possible cause: a position or velocity jump beyond the EKF gate.
  - What to do: the `GPS`/`XKF4` log, the interference source; if it repeats, the failsafe settings.
- **Symptom:** RTK never reaches Fixed
  - Possible cause: too far from the base, a poor RTCM link, a single-frequency receiver.
  - What to do: check the RTCM stream, the distance, the antennas at both ends.
- **Symptom:** "PreArm: AHRS: waiting for home" even though there is a 3D fix
  - What the log shows: `GPS.NSats` < 6, or `GPA.HAcc` > 5 m, or HDOP > 2.5, or `GPA.SAcc` > 1 m/s.
  - Possible cause: EKF3 did not accept GPS by its own thresholds (`EK3_GPS_CHECK`), so home is not set.
  - What to do: open sky and patience. `EK3_CHECK_SCALE` helps only with a failure on hAcc, vAcc, speed error or drift; it does not touch the satellite count or HDOP, which only clearing bits 0 and 1 in `EK3_GPS_CHECK` removes, and then the EKF starts trusting poor geometry. Do neither "just to take off."
- **Symptom:** "Arm: High GPS HDOP" at HDOP 1.5–2
  - Possible cause: the Copter threshold `GPS_HDOP_GOOD` = 140 is stricter than the EKF3 one.
  - What to do: wait for the geometry to improve; arm in AltHold if you do not need position; do not raise the threshold "just to take off."
- **Symptom:** after updating to 4.6+ the GPS settings "disappeared"
  - Possible cause: the parameters were renamed (`GPS_TYPE` → `GPS1_TYPE`, `GPS_RATE_MS` → `GPS1_RATE_MS`, `GPS_POS1_X` → `GPS1_POS_X`); an old parameter file with the former names loads only partly.
  - What to do: update the firmware over the live parameters (they are converted), and fix saved files using the table in the theory.
- **Symptom:** an M10 outputs 3 Hz with `GPS1_RATE_MS = 100`
  - Possible cause: the default constellation set (GPS + Galileo + BeiDou B1I) is limited to 3 Hz in normal mode.
  - What to do: set `GPS1_GNSS_MODE` to GPS + Galileo (10 Hz), or use 5 Hz as the copter standard.

## references
- IS-GPS-200N — Navstar GPS Space Segment / Navigation User Interfaces (L1 C/A power, C/A code) | https://www.gps.gov/technical/icwg/IS-GPS-200N.pdf | primary | A
- ArduPilot — GPS/Compass (landing page) | https://ardupilot.org/copter/docs/common-positioning-landing-page.html | primary | A
- ArduPilot 4.7.3 — AP_GPS (AP_GPS.cpp, AP_GPS_Params.cpp, AP_GPS_UBLOX.cpp) | https://github.com/ArduPilot/ardupilot/tree/Copter-4.7.3/libraries/AP_GPS | primary | A
- ArduPilot 4.7.3 — AP_NavEKF3_VehicleStatus.cpp (GPS thresholds before use) | https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.3/libraries/AP_NavEKF3/AP_NavEKF3_VehicleStatus.cpp | primary | A
- ArduPilot — GPS for Yaw (moving baseline) | https://ardupilot.org/copter/docs/common-gps-for-yaw.html | primary | A
- PX4 v1.18.0 — params_gnss.yaml (EKF2_GPS_*, EKF2_REQ_*) | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/modules/ekf2/params_gnss.yaml | primary | A
- u-blox — MAX-M10S Data Sheet UBX-20035208 (rate per constellation set, CEP, velocity) | https://content.u-blox.com/sites/default/files/MAX-M10S_DataSheet_UBX-20035208.pdf | primary | A
- u-blox — NEO-M9N Product Summary UBX-19027207 | https://content.u-blox.com/sites/default/files/NEO-M9N_ProductSummary_UBX-19027207.pdf | primary | A
- u-blox — NEO-M8 FW3 Data Sheet UBX-15031086 | https://www.mouser.lt/datasheet/3/3699/1/NEO_M8_FW3_DataSheet_UBX_15031086.pdf | primary | A
- u-blox — ZED-F9P Product Summary (RTK, update rates) | https://incremental-content.u-blox.com/sites/default/files/ZED-F9P_ProductSummary_UBX-17005151.pdf | primary | A

## checklist
- I understand pseudorange, the fourth unknown (the clock), HDOP and why velocity is more accurate than position
- I can compute DOP from the geometry and know that the horizontal error ≈ HDOP × UERE
- I know the main error sources and their size
- Antenna on a mast with a ground plane, away from interference
- Rate, constellation and model settings checked; I know how many Hz my receiver gives on my constellation set
- I know the EKF3 thresholds (6 sats, HDOP 2.5, hAcc 5 m) and the Copter one (`GPS_HDOP_GOOD` 1.4) and what they look like at arming
- I measured GPS quality in three conditions and saw multipath in the log
