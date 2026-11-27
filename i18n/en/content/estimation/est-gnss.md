---
id: est-gnss
title: "GNSS: how GPS works, errors, RTK"
level: L2
readingTime: 35 min
firmware: any firmware
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
source_hash: aaf21f538f56
---

## summary
For an autopilot, GPS isn't a “dot on the map” but a noisy measurement with a known (and changing) error. This module explains how a receiver gets pseudoranges and solves for position, where the errors come from (the ionosphere, multipath, satellite geometry — HDOP), what multiple constellations give you (GPS, GLONASS, Galileo, BeiDou), how to choose a receiver and an antenna, which u-blox settings matter for flight (rate, constellations, dynamic model, SBAS), and what RTK/PPK are, when you need them and when you don't. Lab: GPS quality under different conditions, from the log.

## theory
### The principle
Each satellite transmits time and its orbit; the receiver measures the signal delay → **pseudorange** (distance + receiver clock error). Four unknowns (x, y, z, Δt) → at least 4 satellites; more is better (redundancy, quality estimation). The signal at the input is ~−130 dBm — weaker than the noise; it's extracted by correlating with a known code.

### Errors and their magnitudes (single-frequency receiver, good conditions)
| Source | Error | How to reduce it |
|---|---|---|
| Ionosphere | 2–5 m | dual frequency (L1+L5/L2), SBAS correction |
| Troposphere | 0.5–1 m | model |
| Satellite orbit/clock | 1–2 m | SBAS |
| Multipath (reflections from buildings, the ground, the frame) | 1–10+ m, in jumps | antenna with a ground plane, higher above the frame, away from structures |
| Geometry (DOP) | multiplier ×1–×5 | many satellites across the whole sky |
| Receiver noise | 0.3–1 m | a good antenna, no interference |

Total: 1.5–3 m (CEP) in an open field, 5–20 m in a city. **Velocity** from Doppler is much more accurate — 0.05–0.2 m/s; the EKF relies on it more than on position.

### DOP: geometry
HDOP (horizontal) is an error multiplier from the satellite layout: all satellites on one side of the sky → bad. < 1 is excellent, 1–2 is good; above the threshold ArduPilot won't arm in GPS modes (`GPS_HDOP_GOOD`, stored as HDOP × 100; default 140 = 1.4). Satellite count is a rough indicator: 6 is the minimum, 12+ is normal with multiple constellations.

### Constellations
GPS (USA, L1 C/A), GLONASS (Russia), Galileo (EU, L1 + E5), BeiDou (China). A multi-constellation receiver (u-blox M8/M9/M10, F9P) sees 20–30 satellites instead of 8–10: better DOP, faster fix, more robust when part of the sky is blocked. The cost is computational load and update rate: M8 — 10 Hz with 2–3 constellations, M9/M10 — up to 25 Hz, F9P — 20 Hz RTK.

### Antenna
A 25×25 mm ceramic patch on a ground plane is the standard; helical antennas are circularly polarized, better against multipath, and don't need a ground plane. The rule: antenna on top, on a mast, nothing metal nearby, ground plane ≥ 40 mm for a patch. An active antenna (with an amplifier) is for a long cable.

### u-blox settings that matter
- **Rate**: 5–10 Hz for a copter (ArduPilot `GPS_RATE_MS = 200`, in 4.6+ `GPS1_RATE_MS` → 5 Hz; the EKF doesn't need more, and it overloads the UART/CPU).
- **Dynamic model**: Airborne < 1g/2g/4g — the filter inside the receiver tuned for the dynamics; Pedestrian/Automotive are bad for a drone (they smooth and lag). ArduPilot sets `GPS_NAVFILTER`.
- **Constellations** (`GPS_GNSS_MODE`): GPS + Galileo + GLONASS or GPS + Galileo + BeiDou — not all four at once on an M8 (the rate drops).
- **SBAS** (`GPS_SBAS_MODE`): WAAS/EGNOS corrections — slightly more accurate, but in some regions it gets in the way; enable it where there is coverage.
- **Messages**: UBX (binary) instead of NMEA — more compact, more precise, with quality status; ArduPilot configures a u-blox receiver itself with `GPS_AUTO_CONFIG = 1`.

### RTK and PPK
**RTK** (Real-Time Kinematic): a base station at a known position sends carrier-phase corrections (RTCM) to the rover receiver over radio/4G; accuracy is 1–3 cm with a fix (RTK Fixed status), 10–50 cm with float. You need a dual-frequency receiver (F9P, UM982) on both ends, the base within ~10–20 km, and a continuous link. **PPK** is the same but post-processed from logs: it's for photogrammetry, not for flight control.

When you need RTK: precision landing, surveying, moving baseline for heading (two GPS units → yaw without a compass: ArduPilot “GPS for yaw,” base `GPS_TYPE = 17`, rover `GPS_TYPE2 = 18`; in 4.6+ — `GPS1_TYPE`/`GPS2_TYPE`). When you don't: regular waypoint flying (the EKF and a 2 m error are enough), FPV. RTK doesn't cure multipath or satellite loss under a roof.

{{diagram:chart-gnss-hdop-wall|Стена в 180° убирает 4 спутника из 10, а HDOP растёт с 0.82 до 3.48 — выше порога ArduPilot 1.4 и порога EKF3 2.5; число спутников падает медленно, геометрия — резко.}}

{{diagram:gnss-rtk-choice-tree|RTK нужен, только когда задаче нужны сантиметры в полёте; для полёта по точкам хватает 1.5–3 м обычного GNSS, для фотограмметрии — PPK.}}

### How GPS enters the EKF
The EKF receives position, velocity, their accuracy estimates (`GPA.HAcc/VAcc/SAcc`) and the delay (`GPS1_DELAY_MS` ~ 100–200 ms — the measurement is “old,” the EKF accounts for that). Quality is checked (`EK3_GPS_CHECK`: HDOP, satellite count, velocity drift on the ground) before arming is allowed in GPS modes. Glitch protection is the innovation gate (see the Kalman module).

{{diagram:rtk-chain|A standard GNSS solution gives meters; RTCM corrections from a base at a known point give an RTK fix with centimeter accuracy.}}

## practice
### Step 1. Three conditions
Ground logs, 5 minutes each (`LOG_DISARMED = 1`): an open field; next to a house wall; under trees. From `GPS`: `NSats`, `HDop`, `Status`; from `GPA`: `HAcc`, `SAcc`. Table: the average and the worst for each condition.

### Step 2. Multipath
For the second condition, plot the position (`GPS.Lat/Lng` → meters) over 5 minutes in place: the scatter and the jumps. Compare with the field. Match the jumps with `XKF4.SP` in the log (normalized position innovation, √test ratio), if the EKF was running.

### Step 3. Settings
Check `GPS_RATE_MS`, `GPS_GNSS_MODE`, `GPS_NAVFILTER` (or the equivalents in INAV/Betaflight: `gps_ublox_use_galileo`, dynamic model), `GPS_AUTO_CONFIG`. Record them in the build logbook.

### Step 4. Assessing the need for RTK
For your task — do you need RTK? Justify it from the accuracy requirements (engineering folder).

### Script: position scatter in place
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

### What you should get and what to record
- **Open field:** lots of satellites (20 or more with multiple constellations), HDOP around 1 and below, scatter in place of a meter or two. This is the reference the other conditions are compared against.
- **Next to a wall:** fewer satellites, higher HDOP, and above all — position jumps of meters caused by the reflected signal (multipath). The p95 and max scatter will grow several times over, even though the satellite count may stay decent. That's exactly why “lots of satellites” is no guarantee.
- **Under trees:** the signal is attenuated, the fix is lost more often (`Status` drops), `HAcc` in `GPA` grows.
- **Settings:** record the actual GNSS parameter values for your ArduPilot version (in 4.6+ some receiver parameters have the `GPS1_` prefix, e.g. `GPS1_TYPE`; check against the parameter list).

The lab counts as done when HDOP, satellite count and position scatter are recorded for the three conditions, multipath is shown as position jumps in the log next to the wall, the receiver settings are checked and recorded in the logbook, and the RTK decision is justified by the accuracy requirements.

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

```text
[ 40.0s] Arm: AHRS: waiting for home
[ 40.4s] PreArm: AHRS: waiting for home
GPS_RAW_INT: fix 6, sats 5, HDOP 1.21, h_acc 0.30 m
NOT armed after 60 s
```

## diagnostics
- **Symptom:** a long satellite search after power-on
  - Possible cause: cold start, the antenna under carbon, interference from USB/the camera.
  - What to do: a mast, a ground plane, see the EMI module; give it 1–2 minutes.
- **Symptom:** HDOP > 2 with 15 satellites
  - Possible cause: satellites on one side (a wall, a roof).
  - What to do: open sky; don't arm in GPS modes.
- **Symptom:** position jumps by 10–30 m in a city
  - Possible cause: multipath.
  - What to do: higher above the frame, a helical antenna, don't trust Loiter near buildings.
- **Symptom:** “GPS glitch” in ArduPilot messages
  - Possible cause: a position/velocity jump beyond the EKF gate.
  - What to do: the `GPS`/`XKF4` log, the interference source; if it repeats — the failsafe settings.
- **Symptom:** RTK doesn't reach Fixed
  - Possible cause: too far from the base, a poor RTCM link, a single-frequency receiver.
  - What to do: check the RTCM stream, the distance, the antennas on both ends.

## references
- ArduPilot — GPS/Compass (landing page) | https://ardupilot.org/copter/docs/common-positioning-landing-page.html | primary | A
- ArduPilot — GPS for Yaw (moving baseline) | https://ardupilot.org/copter/docs/common-gps-for-yaw.html | primary | A
- u-blox — ZED-F9P Product Summary (RTK, update rates) | https://incremental-content.u-blox.com/sites/default/files/ZED-F9P_ProductSummary_UBX-17005151.pdf | primary | A

## checklist
- I understand pseudorange, HDOP and why velocity is more accurate than position
- I know the main error sources and their magnitudes
- The antenna is on a mast with a ground plane, away from interference
- Rate/constellation/model settings are checked
- I measured GPS quality in three conditions and saw multipath in the log
