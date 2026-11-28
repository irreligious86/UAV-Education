---
id: f-frame-mech
title: "Frame, Mechanics and Vibration"
level: L2
readingTime: 25 min
firmware: any firmware
status: published
added: 2026-11-08
tags:
  - frame
  - vibration
  - balancing
related:
  - f-aero-props
  - bf-filters
next:
  - bf-pid-reg-in-bf
source: content/foundation/f-frame-mech.md
source_hash: 7d6028282ae8
---

## summary
Half of all “tuning problems” are mechanical: an unbalanced prop, a loose motor, a frame that rings at a frequency where the motor harmonics land. Filters and PID treat the symptoms; this module is about the causes. Where vibration comes from, what frame resonance is, how to balance props and motors, how to mount the flight controller and route the wires, and how to measure the result from the spectrum rather than by feel.

## theory
### Sources of vibration
- **Prop imbalance** — the blade masses are not equal: force ~ m·r·ω², i.e. it grows with the square of RPM. The main source at the rotation frequency (1st harmonic).
- **Motor imbalance** — the bell, the magnets; the same frequency.
- **Blade aerodynamics** — thrust pulsations at the “RPM × number of blades” frequency (2nd, 3rd harmonics).
- **Play and flex** — a bearing, an under-tightened motor, a flexible arm: they add broadband noise and can “ring” at their own frequency.
- **Prop wash and turbulence** — low-frequency shaking at 20–70 Hz, aerodynamics, not mechanics.

### Frame resonance
A frame has natural frequencies (arms, FC mount, standoffs). When a motor harmonic passes through a natural frequency, the amplitude grows several times. In the spectrum it is a peak that does not move with RPM. A resonance is not filtered by the RPM filter (that one tracks the motors); it is caught by the dynamic notch or removed by changing the design: a stiffer arm, a different mass, a damper.

### How vibration spoils flight
- The gyro sees vibration as angular rate → the PID “works off” movement that doesn't exist → hot motors, mushy response.
- The accelerometer clips (saturates) → the ArduPilot EKF loses its altitude and position estimate (`VIBE`, `Clip`).
- The barometer “breathes” from the airflow.

### Mounting the flight controller
The goal is to pass on the frame's movements but not high-frequency vibration. Standard practice: soft rubber grommets or standoffs with a damper, wires without tension (a taut harness is a rigid link that bypasses the dampers). A mount that is too soft has its own low-frequency resonances and gyro lag. For large aircraft — damping plates. On racing 5" you also see hard mounting with filter tuning: the motors there spin fast, and the grommets add their own 50–150 Hz resonance (section “Numbers”). The course rule for 5": start with the grommets that come with the stack — a 5" does have a soft-mount window (subsection “FC damping”); switch to hard mounting only if the spectrum shows a mount peak — a horizontal line below the motor harmonics that does not depend on throttle — and replacing the grommets with stiffer ones does not remove it.

### Numbers
The motor's 1st-harmonic frequency = RPM/60. In hover a 5" is ~200–260 Hz (12–16 thousand rpm; 14,000 rpm ≈ 233 Hz, as in the f-safety and f-physics calculations; a heavier build runs higher; on a punch-out up to 400–600 Hz), 7" ~110–200 (the 1.4 kg 7" LR from the `bf-rpm-filter` example — 110–130), 10" ~80–100, 15" ~50–70. Carbon arm resonances are usually 100–400 Hz, FC mount resonances — 50–150 Hz.

### Natural frequencies: a rough estimate
An arm as a cantilever beam: f₁ ≈ 0.56·√(E·I/(μ·L⁴)) (E — modulus of elasticity, I — second moment of area of the cross-section, μ — mass per meter, L — length); for an engineering estimate it is easier to measure: a tap on the arm with the accelerometer/gyro logging (`LOG_DISARMED`/`blackbox_mode = ALWAYS`) gives decaying oscillations — the frequency of the peak in the spectrum is the resonance. Typical values: a 5" carbon arm of 4–5 mm — 300–500 Hz (above the motor harmonics in hover, below them at full throttle); 7" 5 mm — 150–250 Hz (coincides with the 1st–2nd harmonics — the danger zone); 10"+ tubular arms of 16–25 mm — 60–150 Hz. Stiffen the arm (thicker, shorter, a tube instead of a plate) → the frequency rises as √(stiffness/mass); add mass at the tip (a heavier motor) → it falls.

### FC damping: how to choose
A rubber grommet is a spring with a damper: the natural frequency of the “board on grommets” system is f₀ = (1/2π)·√(k/m). You want f₀ 3–5 times below the lowest motor harmonic, but above the control bandwidth (≥ 50–80 Hz): for a 5" (motors 250+ Hz) — f₀ ≈ 50–83 Hz (250 / 5 … 250 / 3); for an X8 (motors 55 Hz) dampers with an f₀ of 15–20 Hz are already “soft” and add lag — there you rely on balancing and notches, not on softness. Manufacturers usually do not publish the grommet stiffness k, so f₀ is not calculated but measured with the same tap as the arm: `blackbox_mode = ALWAYS`, a tap on the frame next to the stack, and the peak of the decaying oscillations in the gyro spectrum is the f₀ of the mount (course method). The target for a 5" is 50–83 Hz (the window in the diagram below); higher — the grommets are too stiff for this stack, lower — too soft. The sign of a mount that is too soft: a low-frequency peak in the spectrum (tens of hertz, below the motor frequency) and a “mushy” feel. Wires and ribbon cables bypass the dampers if they are taut.

{{diagram:chart-fc-damper-window|A soft-mount window (f₀ 3–5 times below the motor harmonic, but not below 50–80 Hz) exists only for harmonics from 150–240 Hz: for a 5" (250 Hz) it is 50–83 Hz; the 7" from the example (125 Hz), the 10" and the X8 have no window — there it is balancing and notches.}}

### Worked example: a 7" with a 180 Hz peak
Spectrogram: a horizontal line at 180 Hz regardless of throttle, 25 dB above the noise floor; the motor harmonic in hover is 125 Hz, the 2nd is 250 Hz (when throttling up it passes through 180 Hz — the resonance “rings”). Tap test on the arm — 182 Hz: it's the arm. Options: a 6 mm arm instead of 5 (f ↑ ~20% → 215 Hz, moves away from the 1st harmonic, but the 2nd still passes through) — not a solution; a dynamic notch at 180 (helps, but adds delay) — a temporary fix; the real fix — change the motor mounting point / shorten the arm (f ↑ by 1.3–1.5 times) or accept it and set a static notch `gyro_notch1_hz = 180`, `cutoff = 150`. Why not the `bf-filters` rule “`cutoff` = frequency × 0.7”: `cutoff` is the lower edge of the notch, Q = f·f_c / (f² − f_c²) (`filterGetNotchQ` in Betaflight 2025.12.5). 0.7 × 180 = 126 Hz gives Q ≈ 1.4, and the edge of the notch would land on the 125 Hz 1st hover harmonic — extra delay where the RPM filter is already working. 150 / 180 = 0.83 gives Q ≈ 2.7 — the notch is narrower, but it still covers the narrow resonance line. Rule: 0.7 — when there is no motor line next to the resonance, closer to 1 — when there is. Write it in the build's spec sheet: “arm resonance 180 Hz, notch”. Without a spectrum all of this would have looked like “need to lower D”.

{{diagram:vibration-path|The vibration path from the motors and propellers through the frame and the mount to the gyro and the control loop — and where to break it.}}

### Place in the system

- **Receives:** motor RPM and the number of blades — the source of the harmonics (`f-motors-esc`, `f-aero-props`); the way the board is mounted and the harnesses are routed (`f-fc-sensors`, `el-wiring`).
- **Provides:** the vibration spectrum that the gyro and accelerometer will see — the input for the filters and the RPM filter (`bf-filters`, `bf-rpm-filter`) and for the sensor error model (`est-sensors`); a resonance you found — into the build's spec sheet.
- **If you get it wrong here:** an arm resonance coincides with a motor harmonic → the PID works off movement that doesn't exist, the motors are hot; without a spectrum this looks like “need to lower D” (`bf-blackbox`, `bf-filters`). Vibration clips the accelerometer → the ArduPilot EKF loses its altitude and position estimate, `VIBE` and `Clip` grow in the log (`ap-logs`, `ap-ekf`).

## practice
### Step 1. Inspection
1. Props: cracks, chips, the same model and pitch on all motors.
2. Motors: up-and-down play of the bell, bearing crunch when spinning by hand, screw tightness (no longer than needed — a screw in the winding = a short circuit).
3. Frame: cracks around holes, standoff tightness, no contact between wires and props.

### Step 2. Balancing
1. Props — on a balancer: the heavy blade drops; remove material with sandpaper on the back side near the tip, or add a drop of lacquer/tape to the light one.
2. Motors — run them without props at low throttle and touch the standoff: a vibrating motor can be felt. More precisely — the spectrum of a log without props.

### Step 3. Measure, don't feel
1. A hover log before any changes, the gyro spectrum (Blackbox Explorer / PID Toolbox / your own Python).
2. Find the peaks: they follow throttle → motors; they stay put → resonance.
3. After balancing/the damper — the same flight, the same spectrum, the difference in dB in the peak's band.

### Step 4. Wires
Harnesses are not taut and do not touch rotating parts, power wires are twisted (against noise) and secured to the frame, not to the FC.

### Lab
The spectrum before/after balancing the props on your own aircraft; write down the frequency of the main peak and the change in amplitude in dB.

**Reference for self-check.** A correct result is two spectra of the same mode (hover) in which the peak and its nature are named: the motor peak follows throttle and sits at the RPM/60 frequency (in hover a 5" is ~200–260 Hz, 7" ~110–200, 10" ~80–100), a resonance stays put at any throttle. Prop balancing lowers specifically the peak of the motors' first harmonic; the difference is written down in dB in that peak's band. Common wrong results: the peak did not change — it does not move with throttle, it's a frame resonance, and balancing does not cure it (check with a tap on the arm); “before” and “after” were recorded at different throttle — the motor peak simply moved in frequency, there is nothing to compare; a low-frequency 20–40 Hz peak grew in the spectrum — that is a flight-controller mount that is too soft, not the props.

## diagnostics
- **Symptom:** a peak in the spectrum does not move when throttle changes
  - Possible cause: a resonance of the frame or the FC mount.
  - What to do: arm/standoff stiffness, a damper, a dynamic notch at that frequency.
- **Symptom:** the peak at the motor frequency is huge
  - Possible cause: prop or motor imbalance.
  - What to do: balance, replace the prop, check the bell.
- **Symptom:** `VIBE` and `Clip` grow in ArduPilot
  - Possible cause: a hard FC mount, imbalance of large props.
  - What to do: FC damping, balancing, wires without tension.
- **Symptom:** after fitting dampers the flight became “mushy”
  - Possible cause: a mount that is too soft, a low-frequency resonance.
  - What to do: stiffer grommets, less mass on the damper.

## references
- Vibration Damping — ArduPilot Copter | https://ardupilot.org/copter/docs/common-vibration-damping.html | primary | A
- Measuring Vibration — ArduPilot Copter | https://ardupilot.org/copter/docs/common-measuring-vibration.html | primary | A
- Blackbox Explorer — Betaflight (GitHub) | https://github.com/betaflight/blackbox-log-viewer | primary | A

## checklist
- Props and motors checked by inspection and balancing
- I understand the difference between a motor peak and a resonance in the spectrum
- The FC is on dampers, wires without tension
- The before/after spectrum is recorded, the result in dB is written down
