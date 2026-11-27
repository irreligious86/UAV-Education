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
  - f-esc-firmware
  - bf-motor-balance
next:
  - f-fc-sensors
source: content/foundation/f-motors-esc.md
source_hash: e81635eab54b
---

## summary
A brushless motor doesn't spin by itself: it is driven by an ESC (electronic speed controller), which receives commands from the flight controller. The module explains what numbers like “2207 1750KV” mean, what poles are, why everyone moved from analog PWM to digital DShot, and which ESC firmware is current in 2026 after BLHeli_32 was shut down.

## theory
### Motor designation
- **2207** — stator size: 22 mm diameter, 7 mm height. A bigger stator — more torque.
- **KV** — RPM per volt with no load. 1750KV on 6S (25.2 V) — roughly 44,000 rpm without a prop. Less under load.
- **12N14P** — 12 stator coils, 14 magnets. The number of magnets is `motor_poles` in the firmware; the RPM filter needs it.

Selection rule: a big prop needs a lot of torque and a low KV, a small prop — a high KV. A high-KV motor on a big prop overheats and pulls a huge current. How much exactly: RPM under the prop ≈ k × KV × U, so for a given prop KV × cell count is almost constant — the same 5" on 4S needs a higher KV than on 6S (2300–2700 versus 1700–2100); the table by class and the check after assembly — in `f-aero-props` (“KV for the prop and cell count”).

### What an ESC does
A brushless motor is three-phase. The ESC energizes the phases in turn, creating a rotating magnetic field. It determines the rotor position without sensors — from the EMF induced in the unpowered phase (sensorless). Hence desync: on a sharp throttle change the ESC can “lose” the rotor, and the motor will twitch or stop.

### Control protocols
- **PWM** — a 1000–2000 µs pulse at about 50 Hz. Analog, slow, requires range calibration. Still found on servos and heavy-lift ESCs.
- **OneShot, Multishot** — the same pulses, only shorter and more frequent. A historical stage.
- **DShot150/300/600** — a digital protocol: a 16-bit packet with a checksum, no calibration needed, noise does not shift the throttle. The number is the speed in kilobits.
- **Bidirectional DShot** — the ESC sends back the motor's eRPM. The RPM filter is built on this.

{{diagram:dshot-frame|A DShot frame: 11 throttle bits, a telemetry request bit and 4 CRC bits.}}

RPM is calculated from eRPM like this: RPM = eRPM / (number of magnets / 2).

### ESC firmware in 2026
- **BLHeli_S** — old 8-bit ESCs, open source. They are flashed with **Bluejay** — with bidirectional DShot and the RPM filter.
- **BLHeli_32** — 32-bit ESCs. The project was shut down in June 2024: the firmware server is offline, there will be no more updates. Existing ESCs keep working and can still be configured.
- **AM32** — open-source firmware for 32-bit ESCs, the de facto replacement for BLHeli_32. Switching from BLHeli_32 to AM32 is one-way.

{{lesson:f-esc-firmware|Bluejay and AM32 settings tables from the source code, choosing the PWM frequency for the aircraft, and a “symptom → setting” cheat sheet, including for desync.}}

### ESC current
ESCs are chosen by continuous current with a margin over the real peak current from the log; for a first build, when there is no log yet — by the motor's peak current from the thrust table: ESC continuous current ≥ 1.3 × that current (`f-components-choice`, Step 5a). A 4-in-1 is convenient and light, but overheating one channel often kills the whole board.

### Motor physics in two formulas
A brushless motor is two constants linked to each other: **KV** (rpm per volt) and **Kt** (torque per amp). Kt = 60/(2π·KV) N·m/A: a 1750KV motor gives 0.0055 N·m per amp, a 380KV motor — 0.025 N·m/A. So low KV = a lot of torque per amp = a big prop without overheating; high KV = RPM for a small prop. RPM under load: n = KV · (U − I·R_winding) — the drop from the winding resistance (tens of mΩ) and from the battery's internal resistance. Heat in the winding P = I²·R: at 30 A and 40 mΩ — 36 W per motor; the only heatsink is the bell itself and the prop airflow.

The stator size sets the torque (the volume of magnetic material): a 2207 and a 2306 have almost the same volume, and the difference is smaller than between manufacturers. It is usually believed that a wider stator (2306) gives slightly more torque and a sharper response, while a taller one (2207) sheds heat better on long flights — compare by the thrust tables of specific motors, not by the size numbers. The number of pole pairs (14 magnets = 7 pairs) sets the eRPM → RPM conversion and the commutation frequency: at 30,000 rpm, 7 pairs = 3500 electrical revolutions/s.

### What an ESC does every microsecond
An ESC is a three-phase inverter on 6 MOSFETs. It commutates the phases according to the rotor position, which it estimates from the back-EMF in the unpowered phase (zero-crossing). ESC firmware parameters that matter:
- **PWM frequency** (24/48/96 kHz) — the PWM frequency on the switches. Rule: the smaller the motor and the higher its RPM, the higher the frequency needed — whoop and 2–3.5" 48 kHz, 5" 48 (freestyle) or 24 (racing), 7" 24–48, 10" and larger, heavy aircraft and planes 24 kHz; higher — smoother current and quieter, but weaker braking and thrust at low throttle and a hotter ESC. Why, how to choose for any aircraft and what to check after a change — the subsection “PWM frequency: how to choose for the aircraft” in `f-esc-firmware`.
- **Timing** (motor timing; 0–30° in the firmware, default AM32 15°, Bluejay 22.5°) — commutation advance: higher — more RPM and current, more heating, but more margin against demagnetization; lower — cooler and more efficient, but heavy props and motors with high inductance desync more often on a sharp throttle input. Start — the firmware default; change it by the procedure in `f-esc-firmware`.
- **Demag compensation** — protection against desync on sharp throttle changes, especially accelerating from low RPM with a heavy prop (the demagnetization current grows with the motor current). The starting point for any class is the ESC firmware default (Bluejay — Low, AM32 — `demag_comp` from the table in `f-esc-firmware`); raise it by one step only when there is a sign of desync: in Blackbox, an eRPM dip of one motor on a sharp throttle input, by ear — “sneezing”. Large motors on heavy props — 7" and larger — need this more often (course estimate). The check after each step — three throttle punches from hover to 100 % on the same pack: no eRPM dips; the price — a short thrust dip on the transition (`f-esc-firmware`, “Symptom → setting”).
- **Startup power / rampup** — a smooth start for big props.
- **Current limit / temperature protection** — the ESC reduces power when overheating: in the log it looks like a “thrust drop”.
Desync — the ESC has lost the rotor position: the motor twitches, screeches, thrust drops; causes — long phase wires, weak demagnetization compensation or a low timing for a heavy prop, a prop too big for the KV, old firmware.

### DShot: how the frame is built
16 bits: 11 value bits (0 — stop, 1–47 — special commands, 48–2047 — throttle), 1 telemetry request bit, 4 CRC bits. A bit is encoded by pulse width: “1” ≈ 75% of the bit period, “0” ≈ 37%; DShot300 — a 3.33 µs bit, a 53 µs frame; DShot600 — 1.67 µs and 27 µs. A frame is sent every PID loop. **Bidirectional DShot**: after the frame the line turns around, and the ESC replies with a frame carrying the eRPM (the period of an electrical revolution), GCR-encoded; errors in this reply show up as `E%` on the Motors tab — normal is no higher than 1 % (course guideline, `bf-rpm-filter`; usually about 0), at a higher rate the RPM filter places its notches in the wrong place. A notch (band-stop filter) is a narrow “cut” in the gyro spectrum: it suppresses one frequency and barely touches the neighboring ones; the RPM filter places such cuts at the motors' rotation frequencies from eRPM, so a wrong eRPM or `motor_poles` moves the cut off the noise. DShot special commands (1–47): beeper, spin direction reversal (`dshot_cmd` 7/8 — `motor direction`), 3D on/off, ESC info request — the configurator uses these on the Motors tab.

### Worked example: choosing a pair
A 5" freestyle 6S, 700 g: you need T/W ≥ 6 (the freestyle band in `f-physics`) → 4200 g total, 1050 g per motor maximum. The table for a 2207 1750KV with a 5.1×3 prop: maximum ~1600 g at 38 A — there is margin, hover ~180 g per motor at ~4 A. A 45 A 4-in-1 ESC — 45 A continuous at a 38 A peak per channel (a 1.18× margin): enough as long as the peak lasts seconds, but “cutting it close” in aggressive flying on a fresh battery; by the ≥ 1.3× rule from f-components-choice you need ≥ 50 A, so 55–60 A is more comfortable. A 7" long range 6S 1.4 kg: 2806.5 1300KV + 7×3.5: maximum ~1200 g at ~22 A → by the rule 1.3 × 22 ≈ 29 A; an ESC of 35–45 A — with extra margin that costs only weight (current-wise a 30–35 A AIO would also do, `f-components-choice`, Step 5a). The KV difference between a 5" and a 7" is precisely because of the torque on the prop (Kt).

{{diagram:motor-esc-selection|The selection chain: the ESC current is calculated from the motor's peak current from the thrust table — 38 A × 1.3 = 49.4 A, so 45 A is cutting it close, while for a 7" with 22 A, 35–45 A is enough.}}

### Place in the system

- **Receives:** the throttle command over DShot every PID loop — from the mixer (`f-physics`, `f-fc-sensors`); the voltage under load, on which the RPM depends (`f-power`); the load from the propeller (`f-aero-props`).
- **Provides:** thrust and reaction torque — to the frame; eRPM over bidirectional DShot — to the RPM filter (`bf-rpm-filter`); the peak current — to the choice of ESC, battery and wires (`f-components-choice`, `el-power-design`).
- **If you get it wrong here:** `motor_poles` is not equal to the number of magnets → RPM from eRPM is converted wrongly, the RPM filter places the notch in the wrong place, motor noise goes into the PID (`bf-rpm-filter`). A prop too big for the KV or weak demag compensation → desync: in the log, an eRPM dip of one motor, the aircraft twitches or flips over (tree 3 in `diag-troubleshooting`, settings — `f-esc-firmware`).

## practice
### Checking motors and ESCs on the bench
1. Remove the props.
2. Connect the battery through a current limiter (smoke stopper) at the first power-up of a new build.
3. On the Motors tab, spin each motor at low throttle: check the direction and smoothness.
4. With bidirectional DShot, make sure each motor reports RPM and telemetry errors are no higher than 1 % (course guideline, `bf-rpm-filter`).
5. Check by hand: the bell spins without play or crunching, the magnets are intact, the screws do not touch the winding.

### Choosing the protocol
For Betaflight the DShot speed is chosen by the PID loop (the rule from `config/config.c` 2025.12.5): the frame together with the bidir DShot reply must fit into the loop, so DShot300 with bidir allows a PID loop of up to 4 kHz with an 8 kHz gyro (the firmware will raise `pid_process_denom` itself), DShot600 — up to 8 kHz. On F405, F411 and G47x (and APM32F405/F407) with `dshot_bidir = ON` the firmware itself rewrites DSHOT600 to DSHOT300 and the PID loop to 4 kHz, except for an F405 with `cpu_overclock` from 216 MHz (`bf-filters`, “What the firmware will change by itself”; `f-micro-whoop`). On F7, H7 and AT32F435 there is no such limitation: DSHOT600 at an 8 kHz PID loop, DSHOT300 — at a PID loop of 4 kHz and below, or if DShot errors exceed 1 % (course guideline: slower — more robust against interference). Check — `status` in the CLI (loop and CPU load) and DShot errors on the Motors tab. For ArduPilot — DShot where the ESC supports it, otherwise PWM with calibration.

### What to write down: the motor table
| Motor | Direction | Sound and smoothness | Play, crunch | eRPM at 10 % throttle | DShot errors |
|---|---|---|---|---|---|
| 1 | ✓ / ✗ | smooth / growls | none / present | … | … % |

- **Current limiter.** The bulb or smoke stopper flashes briefly on connection (the capacitors charge) and goes out. If it stays brightly lit — there is a short circuit somewhere: disconnect the battery and look for it.
- **Direction.** Check against the frame diagram on the Motors tab (Betaflight) or with the motor test in the GCS (ArduPilot: Optional Hardware → Motor Test, motors by letters A, B, C… starting from the front right, clockwise). A wrong direction is changed in the ESC firmware or with a DShot command — the “ESC firmware” module.
- **Sound and hands.** A motor that growls or twitches at low throttle is a candidate for desync or a damaged winding. Bell play — the bearing.
- **Telemetry.** With bidir DShot enabled, RPM is visible for each motor, and errors must be no higher than 1 % with the battery connected (course guideline, the same as in `bf-rpm-filter`). If there are more errors, check the soldering of the signal wires and the ground, and try DShot300 instead of 600.
- **ESC firmware.** Write down what is on the ESC (BLHeli_S, Bluejay, BLHeli_32, AM32) and whether it supports bidir DShot: whether the RPM filter will work depends on it.

{{lesson:bf-motor-balance|The bench only catches gross defects; a weak motor, a bent prop and a shifted center of gravity show up in the medians of `motor[0..3]` in a hover log.}}

Self-check: the lab is done when the first power-up was done without props through a current limiter (the bulb flashed briefly and went out), in the table for each motor the direction matched the frame diagram, there is no growling, play or crunching and the eRPM at 10 % throttle is written down, the ESC firmware and bidir DShot support are identified, and DShot telemetry errors are no higher than 1 % with the battery connected.

## diagnostics
- **Symptom:** one motor is hotter than the others
  - Possible cause: a bearing, rubbing, a damaged winding or prop.
  - What to do: compare the rotation of the bells by feel, swap the suspicious motor with another and see whether the problem “moved”.
- **Symptom:** a motor twitches or stops on a sharp throttle input
  - Possible cause: ESC desync.
  - What to do: check the timing/demag settings in the ESC firmware, the phase soldering.
- **Symptom:** when the battery is connected the ESC is silent or doesn't play its tune
  - Possible cause: no power to the ESC, a burned channel, no protocol selected.
  - What to do: check the power soldering, `MOTOR_PROTO` in the arming flags, the ESC firmware.
- **Symptom:** the RPM filter doesn't enable
  - Possible cause: ESC firmware without bidirectional DShot or a wrong `motor_poles`.
  - What to do: Bluejay or AM32, recount the magnets.
- **Symptom:** a motor twitches/screeches on a sharp throttle input
  - Possible cause: desync — demag/timing, long wires, a prop too heavy for the KV.
  - What to do: first raise demag, then timing by one step (watch the motor temperatures), check the phase wires; if that doesn't help — a smaller prop (in detail — `f-esc-firmware`).
- **Symptom:** `E%` on the Motors tab is above zero
  - Possible cause: bidirectional DShot errors — ESC firmware, noise on the signal, DShot speed.
  - What to do: update the ESC (Bluejay/AM32), DShot300 instead of 600, shorter signal wires.
- **Symptom:** thrust “drops off” after a minute of flight
  - Possible cause: ESC or motor thermal protection.
  - What to do: the ESC temperature from telemetry, cooling airflow, a lower PWM frequency, the current from the log.

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
