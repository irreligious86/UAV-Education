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
source_hash: 6b8284688b55
---

## summary
An aircraft is a tightly packed box of interference sources (ESCs, power wires, buck converters, VTX, companion computer) and victims (compass, GPS, receiver, gyro). This module explains the mechanisms: the magnetic field of a current, radiation from switching edges, conducted interference through power and ground. It teaches three techniques (twist, shield, separate) and, most importantly, how to measure their effect in the logs: the compass with `MAG`/`compassmot`, the GPS with satellite count and HDOP, the receiver with LQ/RSSI.

## theory
### Three interference paths
1. **The magnetic field of a current**: around a wire carrying current I, at distance r, the field is B = μ₀·I/(2π·r). At 60 A and 5 cm that is 240 µT, 5 times the Earth's magnetic field (~50 µT). A compass 5 cm from a power wire is useless under throttle. The field falls off as 1/r: twice as far means half as strong; a twisted pair with opposing currents cancels the field almost completely.
2. **Radiation from switching edges**: ESCs and bucks switch current within tens of nanoseconds; steep edges contain harmonics up to hundreds of MHz. Wires act as antennas. Victims: GPS (1.5 GHz, signal −130 dBm, the weakest on board), the 900 MHz/2.4 GHz receiver, analog video.
3. **Conducted interference**: through the shared power and ground wires. Buck ripple gets into the receiver supply; ESC current through a shared ground creates a potential difference between the FC ground and the camera ground, which shows up as lines in the video.

### Worked example: a compass and a power wire
Current 60 A, Earth's field ~50 µT. A single wire, B = 2·10⁻⁷·I/r:

| Distance to the compass | Single wire | Twisted pair (3 mm spacing) |
|---|---|---|
| 5 cm | 240 µT (×5 the Earth's field) | 14 µT |
| 10 cm | 120 µT | 3.6 µT |
| 20 cm | 60 µT | 0.9 µT |

The field of a pair with opposing currents is the difference of the two wires' fields: B ≈ 2·10⁻⁷·I·d/r², which falls off as 1/r², not 1/r. Hence two rules that do more than any shielding: power + and − always run together (twisted or laid tightly side by side), and the compass is at least 10 cm from the power bus, preferably on a mast. The magnetic field of a DC current is not shielded by foil, only by distance, geometry or mu-metal.

{{diagram:chart-emi-wire-field|At 60 A a single wire gives a field stronger than the Earth's even at 20 cm, while a twisted pair is already below 30 % of the Earth's field at 5 cm: its field falls off as 1/r², not 1/r.}}

### Compass current compensation
If you cannot separate them, ArduPilot can subtract the interference: `compassmot` (with props on, the aircraft firmly secured) measures the onboard field as a function of current and writes the coefficients to `COMPASS_MOT_X/Y/Z`; the mode is `COMPASS_MOTCT` (1 = Use Throttle, 2 = Use Current, which needs a current sensor). This compensates the linear part of the interference, not the nonlinear part (saturation, eddy currents). The ArduPilot wiki thresholds apply to the interference `compassmot` shows (the measured interference extrapolated to full throttle, before compensation): below 30 % of the Earth's field (≈ 15 µT at ~50 µT) it is acceptable; 31–60 % is the ArduPilot "gray zone" (it may or may not fly well); above 60 % compensating the linear part will not save you, and the compass has to be moved (`ap-sensors`). The course treats anything above 30 % as a reason to separate first.

### GPS: watch C/N0, not just the satellite count
Satellite count and HDOP drop late. The first thing to react to interference is the signal-to-noise ratio of each satellite (C/N0, dB-Hz): 35–45 dB-Hz for visible satellites under open sky. If switching on the VTX or companion lowers the C/N0 of all satellites by 5–10 dB at the same time, that is onboard interference, not the sky. To see it: u-center through flight controller passthrough (`SERIAL_PASS1`/`SERIAL_PASS2` and `SERIAL_PASSTIMO` in ArduPilot, the `serialpassthrough` command in Betaflight/INAV), the Satellite Level view.

### Victims and their symptoms
- **Compass**: heading changes with throttle; in ArduPilot `compassmot` shows the interference in %; in the log `MAG.MagX/Y/Z` correlate with `CTUN.ThO`. Above 30 % is the gray zone, above 60 % separation is mandatory.
- **GPS**: the satellite count drops when the VTX/companion is switched on and HDOP rises, `GPS.NSats`, `GPS.HDop`. Typical culprits: USB 3.0 (harmonics at 1.5 GHz), cameras, HDMI, a buck near the GPS antenna.
- **Receiver**: LQ drops while RSSI is normal: a broadband noise source near the antenna (VTX, companion). Sometimes RSSI "rises" from the interference: the receiver sees the noise as signal.
- **Gyro**: noise in the log at the buck switching frequency; rare, but it happens with poor layout.
- **Video**: lines under throttle are conducted ripple; "snow" is radiation.

### Techniques
- **Twist** power + and −: the opposing currents cancel the magnetic field; twisting signal wires with ground reduces pickup.
- **Separate**: compass and GPS on a mast pointing up (10–15 cm of distance gives ×3–5 on the field), receiver antennas away from the VTX and companion, preferably at the other end of the frame.
- **Shield**: copper foil or shielding fabric on the companion and camera, grounded at a single point; ferrite cores on USB/HDMI cables (turns through the core: more turns, stronger suppression). Choose the core material for the interference frequency found with an analyzer or SDR: for Fair-Rite, material 31 suppresses 1–300 MHz, 43 suppresses 25–300 MHz, 61 suppresses 200–1000 MHz; interference on GNSS at 1.2–1.6 GHz lies above all these ranges, so it is handled with shielding and separation, not with a ferrite on the cable (the course's conclusion from the ranges above). Verify with the same before/after measurement.
- **Filter**: an LC filter on the VTX/camera supply (how to choose L, C, ESR and the inductor saturation current is in `el-power-design`, "LC filter for video"; verify with a scope on the VTX input before and after the filter under throttle, `el-measure`), a capacitor on the power bus (see the power circuit design), an LDO for the receiver.
- **Single ground**: a star from the PDB, not a daisy chain; a cable shield grounded at one end (otherwise you get a ground loop).

### Measure, don't guess
One change at a time, with a before/after measurement:
- compass: `compassmot`, or the correlation of MAG with throttle in the log;
- GPS: NSats/HDOP at rest for 5 minutes with the loads switched on and off one by one;
- receiver: LQ at 50–100 m with the VTX off/on and the companion off/on;
- video: a scope on AC coupling on the camera supply.

{{diagram:emi-paths|The three interference paths and their typical victims: the magnetic field of a current hits the compass, edge radiation hits the GPS and receiver, conducted interference hits the video and the RX supply.}}

### Where it fits in the system

- **Takes in:** power bus currents and converter ripple (`el-power-design`); routing of power and signal wires (`el-wiring`); antenna placement (`rf-antennas`).
- **Puts out:** clean or corrupted compass and GPS measurements to state estimation (`est-sensors`, `est-gnss`); the effective receiver sensitivity to the link budget (`rf-link-budget`); the `compassmot` coefficients.
- **If you get this wrong:** a compass a few centimeters from a power wire → heading changes with throttle, "toilet bowling" in Loiter, the compass innovation grows (`nav-resilience`, `ap-ekf`). A companion with USB 3.0 next to the GPS antenna → the C/N0 of all satellites drops, then the satellite count and HDOP follow: a GPS glitch (`nav-resilience`). A buck next to the receiver → LQ drops with normal RSSI (tree 5 in `diag-troubleshooting`).

## practice
### Step 1. Map of sources and victims
On the aircraft diagram, mark the sources (ESCs, power wires, buck, VTX, companion, USB) and the victims (compass, GPS, RX antennas, camera) with distances.

### Step 2. Compass
The safe path is through the log: a 30 s hover with smooth throttle changes, a plot of `MAG.MagX/Y/Z` and the vector magnitude |B| against `BAT.Curr` (or `CTUN.ThO`). Correlation means interference; estimate its size as a percentage of |B| on the ground. Run `compassmot` only with the aircraft firmly secured, following the ArduPilot instructions, with props on and nobody in the plane of the props. INAV/Betaflight with a compass: compare the heading on the ground and in hover.

Calculate it in Python (log → CSV):
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
5 minutes on the ground: NSats and HDOP with everything off except FC+GPS → +VTX → +companion → +camera. Make a table. The culprit is the one at which NSats drops by ≥ 2 or HDOP rises noticeably. If you have u-center: the same steps, but record the average C/N0 over the visible satellites; the difference shows up already at 3–5 dB.

### Step 4. Fix and repeat
Apply one remedy (separation, shield, ferrite), repeat the measurement, record the difference. Self-check: the lab is done when the source has been found by measurement (compass: interference as a percentage of |B| on the ground; GPS: a drop in NSats of ≥ 2 or in average C/N0 of 3–5 dB when a specific load is switched on), and after the fix the same measurement under the same conditions gave a smaller number, with both numbers recorded side by side.

**Reference answer for self-check.** The step 2 script prints three numbers: |B| at rest, the slope in mGauss/A and the interference in percent at maximum current. A usable result is interference below 30 % of the field; 31–60 % is the gray zone, separate if you can; above 60 % the compass has to be moved, and compensation will not save it. Check the order of magnitude against the worked example: a single wire with 60 A at 10 cm gives 120 µT with the Earth's field at ~50 µT, a twisted pair at the same distance gives 3.6 µT, so twisting and separation should change the number several times over, not by a few percent. Common wrong results: |B| at rest came out as NaN, meaning the log has no segment with current below 2 A (you need a recording on the ground before takeoff); in step 3 a load was named the "culprit" although C/N0 dropped for only some of the satellites: onboard interference lowers the C/N0 of all satellites at once, and anything else is the sky.

## diagnostics
- **Symptom:** heading drifts under throttle, "toilet bowling" in Loiter
  - Possible cause: the magnetic field of the power wires at the compass.
  - What to do: compass on a mast, twist the wires, compassmot/external compass.
- **Symptom:** satellites drop out when the companion/camera is switched on
  - Possible cause: radiation from USB 3.0/HDMI/buck at 1.5 GHz.
  - What to do: shielding, ferrites, GPS on a mast, USB 2.0 cables where possible.
- **Symptom:** LQ drops near the VTX
  - Possible cause: broadband VTX noise at the RX antenna.
  - What to do: separate the antennas, lower VTX power on the ground, filter the VTX supply.
- **Symptom:** lines in the video under throttle
  - Possible cause: ripple and a ground loop.
  - What to do: LC filter, capacitor, single star ground.

## references
- Fair-Rite — Cable Snap-Its (suppression ranges by material: 31: 1–300 MHz, 43/44: 25–300 MHz, 61: 200–1000 MHz) | https://www.mouser.com/new/fair-rite/fair-rite-cable-snap-its | primary | B
- ArduPilot — Advanced Compass Setup (CompassMot section) | https://ardupilot.org/copter/docs/common-compass-setup-advanced.html | primary | A
- ArduPilot — GPS: How it works, mounting and interference | https://ardupilot.org/copter/docs/common-positioning-landing-page.html | primary | A
- ExpressLRS — Signal Health (LQ/RSSI meaning) | https://www.expresslrs.org/info/signal-health/ | primary | A
- ArduPilot — CompassMot and COMPASS_MOTCT (parameter reference) | https://ardupilot.org/copter/docs/parameters.html | primary | A

## checklist
- I know the three interference paths and their typical victims
- The map of sources and victims is drawn with distances
- I can calculate the field of a wire and of a pair and understand why twisting beats shielding
- Interference on the compass/GPS/RX was measured before any changes (compass by the slope of |B| against current, GPS by C/N0)
- One technique was applied and its effect confirmed by measurement
- Power wires are twisted, ground is a star
