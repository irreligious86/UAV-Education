---
id: el-emi
title: "Interference and electromagnetic compatibility"
level: L2
readingTime: 30 min
firmware: any firmware
status: published
added: 2026-11-08
tags:
  - interference
  - EMI
  - compass
  - GPS
related:
  - el-measure
  - f-fc-sensors
  - ap-ekf
next:
  - rf-antennas
source: content/electronics/el-emi.md
source_hash: 6a7836110ce1
---

## summary
The aircraft is a tightly packed box of interference sources (ESCs, power wires, buck converters, VTX, companion) and victims (compass, GPS, receiver, gyro). This module explains the mechanisms: the magnetic field of a current, radiation from switching edges, and conducted noise on the power and ground lines; it teaches three techniques (twist, shield, separate) and, most importantly, how to measure the effect from logs: the compass via `MAG`/`compassmot`, GPS via satellite count and HDOP, the receiver via LQ/RSSI.

## theory
### Three interference paths
1. **The magnetic field of a current** — around a wire carrying current I, at distance r, the field is B = μ₀·I/(2π·r). At 60 A and 5 cm that's 240 µT, 5 times the Earth's magnetic field (~50 µT). A compass 5 cm from a power wire is useless on throttle. The field falls off as 1/r: twice as far means half as strong; a twisted pair with opposing currents cancels the field almost completely.
2. **Radiation from switching edges** — ESCs and bucks switch current in tens of nanoseconds; sharp edges contain harmonics up to hundreds of MHz. The wires act as antennas. Victims: GPS (1.5 GHz, signal at −130 dBm — the weakest on board), the 900 MHz/2.4 GHz receiver, analog video.
3. **Conducted interference** — through shared power and ground wires. Buck ripple gets into the receiver's supply; ESC current through a shared ground creates a potential difference between the FC ground and the camera ground — lines in the video.

### Worked example: the compass and a power wire
Current 60 A, Earth's field ~50 µT. Single wire, B = 2·10⁻⁷·I/r:

| Distance to the compass | Single wire | Twisted pair (3 mm spacing) |
|---|---|---|
| 5 cm | 240 µT (×5 the Earth's field) | 14 µT |
| 10 cm | 120 µT | 3.6 µT |
| 20 cm | 60 µT | 0.9 µT |

The field of a pair with opposing currents is the difference between the fields of the two wires: B ≈ 2·10⁻⁷·I·d/r², falling off as 1/r², not 1/r. Hence two rules that do more than any shielding: power + and − always run together (twisted or tightly bundled), and the compass sits at least 10 cm from the power bus, preferably on a mast. The magnetic field of a DC current is not shielded by foil — only by distance, geometry or mu-metal.

### Current-based compass compensation
If you can't separate them, ArduPilot can subtract the interference: `compassmot` (with props on, the vehicle rigidly secured) measures the field on board as a function of current and writes coefficients to `COMPASS_MOT_X/Y/Z`; the mode is `COMPASS_MOTCT` (1 — by throttle, 2 — by current, needs a current sensor). This compensates the linear part of the interference; the nonlinear part (saturation, eddy currents) it does not. If the interference is above ~30 % of the Earth's field after compensation, the compass still has to be moved.

### GPS: look at C/N0, not just the satellites
Satellite count and HDOP drop late. The first thing to react to interference is the signal-to-noise ratio of each satellite (C/N0, dB·Hz): under open sky, 35–45 dB·Hz for visible satellites. If turning on the VTX or companion lowers the C/N0 of all satellites by 5–10 dB at once, that's interference on board, not the sky. To look: u-center through the flight controller passthrough (`SERIAL_PASS1`/`SERIAL_PASS2` and `SERIAL_PASSTIMO` in ArduPilot, the `serialpassthrough` command in Betaflight/INAV), the Satellite Level view.

### Victims and their symptoms
- **Compass**: heading changes with throttle; in ArduPilot `compassmot` shows the % of interference; in the log `MAG.MagX/Y/Z` correlate with `CTUN.ThO`. Above 30% is bad, you need to separate.
- **GPS**: satellite count drops when the VTX/companion is turned on, HDOP rises, `GPS.NSats`, `GPS.HDop`. Typical culprits: USB 3.0 (harmonics at 1.5 GHz), cameras, HDMI, a buck next to the GPS antenna.
- **Receiver**: LQ drops while RSSI is normal — a wideband noise source near the antenna (VTX, companion). Sometimes RSSI “rises” from interference: the receiver sees the noise as signal.
- **Gyro**: noise in the log at the buck switching frequency — rare, but it happens with poor layout.
- **Video**: lines on throttle — conducted ripple; “snow” — radiation.

### Techniques
- **Twist** the power + and −: opposing currents cancel the magnetic field; twisting signal wires with ground reduces pickup.
- **Separate**: compass and GPS on a mast pointing up (10–15 cm of distance gives ×3–5 on the field), receiver antennas away from the VTX and companion, preferably at the other end of the frame.
- **Shield**: copper foil/shielding fabric on the companion and camera, grounded at a single point; ferrite rings on USB/HDMI cables (turns through the ring — more turns, stronger suppression).
- **Filter**: an LC filter on the VTX/camera supply, a capacitor on the power bus (see power circuit design), an LDO for the receiver.
- **Single ground**: a star from the PDB, not a daisy chain; a cable shield grounded at one end (otherwise — a ground loop).

### Measure, don't guess
One change at a time, with a before/after measurement:
- compass: `compassmot` or the correlation of MAG with throttle in the log;
- GPS: NSats/HDOP at rest for 5 minutes with the loads turned on and off one by one;
- receiver: LQ at 50–100 m with the VTX off/on, companion off/on;
- video: an oscilloscope in AC mode on the camera supply.

{{diagram:emi-paths|Three interference paths and their typical victims: the magnetic field of a current — compass, radiation from switching edges — GPS and receiver, conducted — video and RX power.}}

## practice
### Step 1. A map of sources and victims
On the aircraft wiring diagram, mark the sources (ESCs, power wires, buck, VTX, companion, USB) and the victims (compass, GPS, RX antennas, camera) with distances.

### Step 2. Compass
The safe way is from the log: a 30 s hover with smooth throttle changes, a plot of `MAG.MagX/Y/Z` and the vector magnitude |B| against `BAT.Curr` (or `CTUN.ThO`). Correlation = interference; estimate its size as a percentage of |B| on the ground. `compassmot` only with the vehicle rigidly secured, following the ArduPilot instructions, with props on and nobody in the plane of rotation. INAV/Betaflight with a compass: compare the heading on the ground and in hover.

Compute it in Python (log → CSV):
```python
import numpy as np, pandas as pd
mag = pd.read_csv("MAG.csv"); bat = pd.read_csv("BAT.csv")
b = np.sqrt(mag.MagX**2 + mag.MagY**2 + mag.MagZ**2)
cur = np.interp(mag.TimeUS, bat.TimeUS, bat.Curr)
k = np.polyfit(cur, b, 1)[0]                       # mGauss per amp
print(f"|B| at rest {b[cur < 2].mean():.0f} mGauss, slope {k:.2f} mGauss/A, "
      f"interference at max current {100 * k * cur.max() / b[cur < 2].mean():.0f} %")
```

### Step 3. GPS
5 minutes on the ground: NSats and HDOP with: everything off except FC+GPS → +VTX → +companion → +camera. A table. The culprit is whichever drops NSats by ≥ 2 or noticeably raises HDOP. If you have u-center: the same steps, but record the average C/N0 over the visible satellites — the difference shows up already at 3–5 dB.

### Step 4. Fix and repeat
Apply one remedy (separation, shield, ferrite), repeat the measurement, record the difference. Lab: the source found by measurement, the fix confirmed in the log.

## diagnostics
- **Symptom:** heading drifts on throttle, “toilet bowling” in Loiter
  - Possible cause: the magnetic field of the power wires at the compass.
  - What to do: compass on a mast, twist the wires, compassmot/external compass.
- **Symptom:** satellites drop out when the companion/camera is turned on
  - Possible cause: radiation from USB 3.0/HDMI/buck at 1.5 GHz.
  - What to do: shielding, ferrites, GPS on a mast, USB 2.0 cables where possible.
- **Symptom:** LQ drops near the VTX
  - Possible cause: wideband VTX noise at the RX antenna.
  - What to do: separate the antennas, lower VTX power on the ground, a filter on the VTX supply.
- **Symptom:** lines in the video on throttle
  - Possible cause: ripple and a ground loop.
  - What to do: LC filter, capacitor, single star ground.

## references
- ArduPilot — Advanced Compass Setup (CompassMot section) | https://ardupilot.org/copter/docs/common-compass-setup-advanced.html | primary | A
- ArduPilot — GPS: How it works, mounting and interference | https://ardupilot.org/copter/docs/common-positioning-landing-page.html | primary | A
- ExpressLRS — Signal Health (LQ/RSSI meaning) | https://www.expresslrs.org/info/signal-health/ | primary | A
- ArduPilot — CompassMot and COMPASS_MOTCT (parameter reference) | https://ardupilot.org/copter/docs/parameters.html | primary | A

## checklist
- I know the three interference paths and their typical victims
- The source/victim map is drawn with distances
- I can calculate the field of a wire and of a pair, and I understand why twisting beats shielding
- Interference on the compass/GPS/RX measured before changes (compass — by the slope of |B| vs. current, GPS — by C/N0)
- One technique applied, the effect confirmed by measurement
- Power wires twisted, star ground
