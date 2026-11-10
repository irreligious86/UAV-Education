---
id: f-motors-esc
title: "Motors, ESCs and DShot"
level: L1
readingTime: 20 min
firmware: any firmware
status: published
added: 2026-11-07
tags:
  - motors
  - ESC
  - DShot
related:
  - f-power
  - bf-rpm-filter
next:
  - f-fc-sensors
source: content/foundation/f-motors-esc.md
source_hash: 46a5be24d49c
---

## summary
A brushless motor doesn't spin by itself: it is driven by an ESC (electronic speed controller), which takes commands from the flight controller. This module explains what numbers like “2207 1750KV” mean, what poles are, why everyone moved from analog PWM to digital DShot, and which ESC firmware is current in 2026 after BLHeli_32 shut down.

## theory
### Motor designation
- **2207** — stator size: 22 mm diameter, 7 mm height. A bigger stator means more torque.
- **KV** — RPM per volt with no load. 1750KV on 6S (25.2 V) is roughly 44,000 rpm without a prop. Less under load.
- **12N14P** — 12 stator coils, 14 magnets. The number of magnets is `motor_poles` in the firmware; the RPM filter needs it.

Selection rule: a big prop needs a lot of torque and low KV, a small prop needs high KV. A high-KV motor on a big prop overheats and draws a huge current.

### What the ESC does
A brushless motor is three-phase. The ESC energizes the phases in turn, creating a rotating magnetic field. It determines the rotor position without sensors — from the back-EMF induced in the unpowered phase (sensorless). Hence desync: on a sharp throttle change the ESC can “lose” the rotor, and the motor stutters or stops.

### Control protocols
- **PWM** — a 1000–2000 µs pulse at about 50 Hz. Analog, slow, requires range calibration. Still found on servos and heavy-lift ESCs.
- **OneShot, Multishot** — the same pulses, just shorter and more frequent. A historical stage.
- **DShot150/300/600** — a digital protocol: a 16-bit packet with a checksum, no calibration needed, noise doesn't shift the throttle. The number is the speed in kilobits.
- **Bidirectional DShot** — the ESC replies with the motor's eRPM. The RPM filter is built on this.

{{diagram:dshot-frame|A DShot frame: 11 throttle bits, a telemetry request bit and 4 CRC bits.}}

RPM is calculated from eRPM like this: RPM = eRPM / (number of magnets / 2).

### ESC firmware in 2026
- **BLHeli_S** — old 8-bit ESCs, open source. People flash **Bluejay** onto them — with bidirectional DShot and the RPM filter.
- **BLHeli_32** — 32-bit ESCs. The project shut down in June 2024: the firmware server is offline, there will be no more updates. Existing ESCs keep working and can still be configured.
- **AM32** — open firmware for 32-bit ESCs, the de facto replacement for BLHeli_32. Moving from BLHeli_32 to AM32 is one-way.

### ESC current
Choose an ESC by its continuous current rating, with a margin over the real peak current from the log. A 4-in-1 is convenient and light, but overheating one channel often kills the whole board.

### Motor physics in two formulas
A brushless motor is two constants linked to each other: **KV** (rpm per volt) and **Kt** (torque per amp). Kt = 60/(2π·KV) N·m/A: a 1750KV motor gives 0.0055 N·m per amp, a 380KV motor 0.025 N·m/A. So low KV = high torque per amp = a big prop without overheating; high KV = RPM for a small prop. RPM under load: n = KV · (U − I·R_winding) — sag from the winding resistance (tens of mΩ) and from the battery's internal resistance. Heat in the winding P = I²·R: at 30 A and 40 mΩ — 36 W per motor; the only heatsink is the bell itself and the airflow from the prop.

Stator size sets the torque (volume of magnetic material): 2207 and 2306 have almost the same volume, and the difference is smaller than between manufacturers. The usual view is that a wider stator (2306) gives slightly more torque and a snappier response, while a taller one (2207) sheds heat better on long flights — compare using the thrust tables of specific motors, not the size numbers. The number of pole pairs (14 magnets = 7 pairs) sets the eRPM → RPM conversion and the commutation frequency: at 30,000 rpm, 7 pairs = 3500 electrical revolutions/s.

### What the ESC does every few microseconds
An ESC is a three-phase inverter on 6 MOSFETs. It commutates the phases according to the rotor position, which it estimates from the back-EMF in the unpowered phase (zero-crossing). The ESC firmware parameters that matter:
- **PWM frequency** (24/48/96 kHz) — the PWM frequency on the switches: higher is quieter and smoother at low throttle, but more switching losses and ESC heating; 48 kHz is the compromise for a 5".
- **Timing** (motor timing, 16–24°) — commutation advance: higher gives more RPM/power at high RPM, lower gives more reliable sync and runs cooler.
- **Demag compensation** — protection against desync on a sharp throttle chop (demagnetization current); “High” for heavy props.
- **Startup power / rampup** — a smooth start for big props.
- **Current limit / temperature protection** — the ESC reduces power when it overheats: in the log it looks like a “thrust drop”.
Desync means the ESC lost the rotor position: the motor stutters, screams, thrust drops; causes — long phase wires, high timing, a prop too big for the KV, old firmware.

### DShot: how a frame is built
16 bits: 11 bits of value (0 — stop, 1–47 — special commands, 48–2047 — throttle), 1 telemetry request bit, 4 CRC bits. A bit is encoded by pulse width: “1” ≈ 75% of the bit period, “0” ≈ 37%; DShot300 — a 3.33 µs bit, a 53 µs frame; DShot600 — 1.67 µs and 27 µs. A frame is sent every PID loop. **Bidirectional DShot**: after the frame the line is turned around, and the ESC replies with a frame carrying eRPM (the period of an electrical revolution), GCR-encoded; errors in this reply show up as `E%` on the Motors tab — normal is 0, and at > 1–2% the RPM filter places its notches in the wrong spot. Special DShot commands (1–47): beeper, spin direction reversal (`dshot_cmd` 7/8 — `motor direction`), 3D on/off, ESC info request — the configurator uses these on the Motors tab.

### Worked example: matching a motor and prop
A 5" freestyle on 6S, 700 g: you need T/W ≥ 5 → 3500 g total, 875 g max per motor. The table for a 2207 1750KV with a 5.1×3 prop: max ~1600 g at 38 A — there's margin; hover ~180 g per motor at ~4 A. A 45 A 4-in-1 ESC — 45 A continuous against a 38 A peak per channel: enough, but “cutting it close” in aggressive flying on a fresh battery; 55–60 A is more relaxed. A 7" long range on 6S at 1.4 kg: 2806.5 1300KV + 7×3.5: max ~1200 g at ~22 A → a 35–45 A ESC. The KV difference between 5" and 7" is precisely because of the torque on the prop (Kt).

## practice
### Checking motors and ESCs on the bench
1. Remove the props.
2. Connect the battery through a current limiter (smoke stopper) the first time you power up a new build.
3. On the Motors tab, spin each motor at low throttle: check direction and smoothness.
4. With bidirectional DShot, make sure each motor reports RPM and there are almost no telemetry errors.
5. Check by hand: the bell spins without play or grit, the magnets are intact, the screws don't touch the winding.

### Choosing a protocol
For Betaflight at a typical 4k–8k loop — DShot300 or DShot600 (see the RPM filter module). For ArduPilot — DShot where the ESC supports it, otherwise PWM with calibration.

### What to record: motor table
| Motor | Direction | Sound and smoothness | Play, grit | eRPM at 10 % throttle | DShot errors |
|---|---|---|---|---|---|
| 1 | ✓ / ✗ | smooth / growls | none / yes | … | … % |

- **Current limiter.** A bulb or smoke stopper flashes briefly when you connect (the capacitors charge) and goes out. If it stays brightly lit — there's a short somewhere: disconnect the battery and look for it.
- **Direction.** Check against the frame diagram on the Motors tab (Betaflight) or with the motor test in the GCS (ArduPilot: Optional Hardware → Motor Test, motors lettered A, B, C… starting from the front right, clockwise). A wrong direction is changed in the ESC firmware or with a DShot command — see the “ESC Firmware” module.
- **Sound and hands.** A motor that growls or stutters at low throttle is a candidate for desync or a damaged winding. Play in the bell — the bearing.
- **Telemetry.** With bidir DShot enabled, RPM is visible for every motor, and errors should be no more than 1 % with the battery connected. If there are more errors, check the soldering of the signal wires and ground, and try DShot300 instead of 600.
- **ESC firmware.** Record what's on the ESC (BLHeli_S, Bluejay, BLHeli_32, AM32) and whether it supports bidir DShot: that determines whether the RPM filter will work.

The lab counts as done when the first power-up was made without props through a current limiter, the table is filled in for every motor, the ESC firmware and bidir DShot support are identified, and DShot telemetry errors are no more than 1 % with the battery connected.

## diagnostics
- **Symptom:** one motor is hotter than the others
  - Possible cause: a bearing, rubbing, a damaged winding or prop.
  - What to do: compare how the bells spin by hand, swap the suspect motor to another position and see whether the problem “moved” with it.
- **Symptom:** a motor stutters or stops on sharp throttle
  - Possible cause: ESC desync.
  - What to do: check the timing/demag settings in the ESC firmware and the phase soldering.
- **Symptom:** when you plug in the battery the ESC is silent or doesn't play its tune
  - Possible cause: no power to the ESC, a burnt channel, no protocol selected.
  - What to do: check the power soldering, `MOTOR_PROTO` in the arming flags, the ESC firmware.
- **Symptom:** the RPM filter won't enable
  - Possible cause: ESC firmware without bidirectional DShot, or a wrong `motor_poles`.
  - What to do: Bluejay or AM32, count the magnets again.
- **Symptom:** a motor stutters/screams on sharp throttle
  - Possible cause: desync — timing, long wires, a prop too heavy for the KV.
  - What to do: lower timing, higher demag, check the phase wires, a smaller prop.
- **Symptom:** `E%` on the Motors tab is above zero
  - Possible cause: bidirectional DShot errors — ESC firmware, noise on the signal, DShot speed.
  - What to do: update the ESC (Bluejay/AM32), DShot300 instead of 600, shorter signal wires.
- **Symptom:** thrust “drops out” after a minute of flight
  - Possible cause: ESC or motor thermal protection.
  - What to do: ESC temperature from telemetry, cooling airflow, lower PWM frequency, current from the log.

## references
- DShot RPM Filtering — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/DSHOT-RPM-Filtering | primary | A
- BLHeli32, AM32 and BLHeli_S ESCs — ArduPilot | https://ardupilot.org/copter/docs/common-blheli32-passthru.html | primary | A
- AM32 — firmware source (GitHub) | https://github.com/am32-firmware/AM32 | primary | A
- Bluejay — firmware source (GitHub) | https://github.com/bird-sanctuary/bluejay | primary | A
- The end of BLHeli_32 — Oscar Liang | https://oscarliang.com/end-of-blheli_32 | secondary | B

## checklist
- I can decode 2207 1750KV 12N14P
- I know which firmware is on my ESCs and whether it supports bidirectional DShot
- I checked every motor without props: direction, smoothness, play
- I know the real peak current from the log and the ESC's current margin
