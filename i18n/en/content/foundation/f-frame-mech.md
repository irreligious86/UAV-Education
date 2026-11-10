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
source_hash: eed2fd86907e
---

## summary
Half of all “tuning problems” are mechanical: an unbalanced prop, a loose motor, a frame that rings at a frequency where the motor harmonics land. Filters and PIDs treat the symptoms; this module is about the causes. Where vibration comes from, what frame resonance is, how to balance props and motors, how to mount the flight controller and route the wires, and how to measure the result with a spectrum instead of by feel.

## theory
### Sources of vibration
- **Prop imbalance** — the blades don't have equal mass: the force is ~ m·r·ω², so it grows with the square of RPM. The main source at the rotation frequency (1st harmonic).
- **Motor imbalance** — the bell, the magnets; same frequency.
- **Blade aerodynamics** — thrust pulsations at “RPM × number of blades” (2nd, 3rd harmonics).
- **Play and flex** — a bearing, an under-tightened motor, a flexible arm: they add broadband noise and can “ring” at their own frequency.
- **Prop wash and turbulence** — low-frequency shaking at 20–70 Hz; that's aerodynamics, not mechanics.

### Frame resonance
A frame has natural frequencies (the arms, the FC mount, the standoffs). When a motor harmonic passes through a natural frequency, the amplitude grows several times over. In the spectrum this is a peak that does not move with RPM. Resonance is not removed by the RPM filter (it tracks the motors); it is caught by the dynamic notch or eliminated by changing the structure: a stiffer arm, different mass, a damper.

### How vibration ruins a flight
- The gyro sees vibration as angular rate → the PID “corrects” motion that doesn't exist → hot motors, mushy response.
- The accelerometer clips (saturates) → the ArduPilot EKF loses its altitude and position estimate (`VIBE`, `Clip`).
- The barometer “breathes” from the airflow.

### Mounting the flight controller
The goal is to pass the frame's motion through but not the high-frequency vibration. The standard: soft rubber grommets or standoffs with dampers, wires without tension (a tight harness is a rigid link that bypasses the dampers). A mount that is too soft has its own low-frequency resonances and adds gyro lag. Big aircraft use damping plates; 5" racers often use a hard mount and a clean filter tune.

### Numbers
Motor 1st-harmonic frequency = RPM/60. At hover: 5" ~250–350 Hz, 7" ~150–200, 10" ~80–100, 15" ~50–70. Carbon arm resonances are usually 100–400 Hz, FC mounts 50–150 Hz.

### Natural frequencies: a rough estimate
An arm as a cantilever beam: f₁ ≈ 0.56·√(E·I/(μ·L⁴)) (E — Young's modulus, I — second moment of area of the cross-section, μ — mass per meter, L — length). For an engineering estimate it's easier to measure: tapping the arm with the accelerometer/gyro being logged (`LOG_DISARMED`/`blackbox_mode = ALWAYS`) gives a decaying oscillation — the frequency of the peak in the spectrum is the resonance. Typical values: 5" carbon arm 4–5 mm — 300–500 Hz (above the motor harmonics at hover, below them at full throttle); 7" 5 mm — 150–250 Hz (matches the 1st–2nd harmonics — the danger zone); 10"+ tube arms 16–25 mm — 60–150 Hz. Stiffen the arm (thicker, shorter, a tube instead of a plate) → the frequency rises as √(stiffness/mass); add mass at the tip (a heavier motor) → it drops.

### FC damping: how to choose
A rubber grommet is a spring with a damper: the natural frequency of the “board on grommets” system is f₀ = (1/2π)·√(k/m). You want f₀ 3–5 times below the lowest motor harmonic but above the control bandwidth (≥ 50–80 Hz): for a 5" (motors at 250+ Hz) — f₀ ≈ 60–80 Hz; for an X8 (motors at 55 Hz), dampers with f₀ of 15–20 Hz are already “soft” and add lag — there you work through balancing and notches, not softness. Sign of a mount that is too soft: a low-frequency peak at 20–40 Hz in the spectrum and a “mushy” feel. Wires and ribbon cables bypass the dampers if they are tight.

### Worked example: a 7" with a 180 Hz peak
Spectrogram: a horizontal line at 180 Hz regardless of throttle, 25 dB above the noise floor; the motor harmonic at hover is 125 Hz, the 2nd is 250 Hz (when throttling up it passes through 180 Hz — the resonance “rings”). Tap test on the arm — 182 Hz: it's the arm. Options: a 6 mm arm instead of 5 (f ↑ ~20% → 215 Hz, moves away from the 1st harmonic, but the 2nd still passes through) — not a solution; a dynamic notch at 180 (helps, but adds delay) — a stopgap; the real fix — move the motor mounting point/shorten the arm (f ↑ by 1.3–1.5×), or accept it and set a static notch `gyro_notch1_hz = 180`, `cutoff = 150`. Write it into the build sheet: “arm resonance 180 Hz, notch”. Without a spectrum all of this would have looked like “you need to lower D”.

{{diagram:vibration-path|The vibration path from motors and propellers through the frame and mount to the gyro and the control loop — and where to break it.}}

## practice
### Step 1. Inspection
1. Props: cracks, chips, the same model and pitch on all motors.
2. Motors: up-and-down play in the bell, bearing grit when you spin it by hand, screw tightness (no longer than needed — a screw in the winding = a short circuit).
3. Frame: cracks around the holes, standoffs tight, no wires touching the props.

### Step 2. Balancing
1. Props — on a balancer: the heavy blade drops; sand material off the back side near the tip, or add a drop of lacquer/a piece of tape to the light one.
2. Motors — run them without props at low throttle and touch the standoff: you can feel the vibrating motor. More precisely — a log spectrum without props.

### Step 3. Measure, don't feel
1. A hover log before any changes, the gyro spectrum (Blackbox Explorer / PID Toolbox / your own Python).
2. Find the peaks: they follow throttle → motors; they stay put → resonance.
3. After balancing/a damper — the same flight, the same spectrum, the difference in dB in the peak's band.

### Step 4. Wires
Harnesses not tight, not touching rotating parts, power wires twisted (against noise) and secured to the frame, not to the FC.

### Lab
A spectrum before/after balancing the props on your own aircraft; record the frequency of the main peak and the change in amplitude in dB.

## diagnostics
- **Symptom:** a peak in the spectrum does not move when throttle changes
  - Possible cause: resonance of the frame or the FC mount.
  - What to do: arm/standoff stiffness, a damper, a dynamic notch at that frequency.
- **Symptom:** the peak at the motor frequency is huge
  - Possible cause: prop or motor imbalance.
  - What to do: balance, replace the prop, check the bell.
- **Symptom:** `VIBE` and `Clip` are rising in ArduPilot
  - Possible cause: a hard FC mount, imbalance of large props.
  - What to do: FC damping, balancing, wires without tension.
- **Symptom:** after adding dampers the flight feels “mushy”
  - Possible cause: a mount that is too soft, a low-frequency resonance.
  - What to do: stiffer grommets, less mass on the damper.

## references
- Vibration Damping — ArduPilot Copter | https://ardupilot.org/copter/docs/common-vibration-damping.html | primary | A
- Measuring Vibration — ArduPilot Copter | https://ardupilot.org/copter/docs/common-measuring-vibration.html | primary | A
- Blackbox Explorer — Betaflight (GitHub) | https://github.com/betaflight/blackbox-log-viewer | primary | A

## checklist
- Props and motors checked by inspection and balancing
- I understand the difference between a motor peak and a resonance in the spectrum
- FC on dampers, wires without tension
- Before/after spectrum taken, result in dB recorded
