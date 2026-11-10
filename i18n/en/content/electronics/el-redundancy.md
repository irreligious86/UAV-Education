---
id: el-redundancy
title: "On-Board Redundancy: X8, Hexa, Power and Signals"
level: L2
readingTime: 30 min
firmware: ArduPilot · PX4 · INAV
status: published
added: 2026-11-08
tags:
  - X8
  - hexacopter
  - redundancy
  - fault tolerance
related:
  - el-power-design
  - f-aero-props
  - ap-heavy
next:
  - rf-antennas
source: content/electronics/el-redundancy.md
source_hash: 99cc70366034
---

## summary
A quadcopter with a failed motor is a falling object; a hexa and an X8 can keep flying — if the power, signals and firmware are designed for it. This module covers which failures each layout survives and why (yaw moments), how to distribute power on a heavy aircraft (buses, fuses, dual BECs, a backup receiver), how to compute per-arm currents on an X8 and choose wire gauges and connectors, and how to test the behavior on a motor failure in SITL and on a test stand — before it happens in the air.

## theory
### What each layout survives
- **Quad**: a failure of any motor means loss of yaw and roll control; a controlled crash at best. Redundancy is geometrically impossible.
- **Hexa (6 arms)**: one motor fails — the remaining five can hold altitude and roll/pitch, but yaw holds poorly (the CW/CCW balance is broken): the aircraft slowly spins and lands. You need T/W ≥ 2 on the remaining motors. ArduPilot and PX4, without special settings, simply “give more throttle” to the others through the mixer — this works if there's thrust margin.
- **X8 (coaxial octo)**: one motor fails — its coaxial partner and the opposite pair compensate for both thrust and moment: the most survivable layout with 8 motors on 4 arms. The price is a 10–20% efficiency loss of the coaxial pair.
- **Flat octo**: like a hexa, but with a bigger margin; survives two failures in favorable positions.
- **VTOL**: a lift motor failure in vertical mode — like a quad; in forward flight the lift motors aren't needed — a different failure logic.

What else fails more often than a motor: the ESC (overheating, breakdown), the power connector, the flight controller's BEC, the receiver, the GPS, one of two IMUs. Redundancy starts with a failure table, not with extra motors.

### Powering a heavy aircraft
Example: an X8 on 6S, 8 × 4008 380KV, hover 7 A per motor, max 25 A: hover 56 A, peak 200 A.

- **Buses**: a single power bus from the battery is a single point of failure. Option: two batteries in parallel through diode/ideal-diode ORing modules, or simply two parallel batteries with a fuse on each; one fails — you fly on the second.
- **Fuses**: on each battery (ANL/MIDI at 1.3 × the branch's maximum current), on the companion/payload branch, on the BEC. On the motors — no: the current is pulsed, so a fuse will either blow for nothing or fail to protect.
- **Dual BECs**: two 5 V BECs with diode ORing for the FC and receiver (a Pixhawk-class board accepts three sources: power module, USB, servo rail — with priority). One BEC fails — the aircraft lives on.
- **Receiver**: two receivers (primary CRSF + a backup on another band) or one with diversity; ArduPilot: `RC_OPTIONS` bit 10 (multiple receivers) — a backup input on another UART; PX4 — RC ↔ MAVLink control fallback (`COM_RC_IN_MODE`; `RC_MAP_*` only assigns channels), INAV — at the very least one receiver with diversity antennas.
- **GPS/compass**: two GPS units with blending (`GPS_AUTO_SWITCH`) on DroneCAN, two compasses with priority.
- **IMU**: H7 flight controllers have two or three IMUs — the EKF switches on its own (EK3 has several cores).

### Per-arm currents on an X8
Each arm has two motors: arm current = 2 × motor current. Hover 14 A, maximum 50 A per arm. Arm wire 12–14 AWG; an XT60 arm connector (~30 A continuous, ~60 A briefly) is too small for 50 A; an XT90 has margin. Central distribution board: 4 arms × 50 = 200 A peak — copper bus bars or a 200+ A PDB, XT90/AS150 from the battery, capacitors at the input of each ESC pair.

Drop across a 30 cm 12 AWG arm wire at 50 A: R = 0.0172 × 0.6 / 3.31 ≈ 3.1 mΩ → 0.16 V, 7.8 W of heat at peak — acceptable; with 14 AWG it's 0.25 V and 12 W, already hot over long sessions.

### Firmware behavior on a failure
- **ArduPilot**: the mixer normalizes the outputs; on saturation the priority is roll/pitch, then throttle, yaw last (`MOT_YAW_HEADROOM`). A motor failure shows up in `RCOU` (one channel at maximum, its neighbor at minimum) and in the `ESC` telemetry (RPM 0). There's a thrust loss check (the message “Potential Thrust Loss (n)”): the mixer enables thrust boost and excludes the lost motor from yaw control; but survivability is still determined by thrust margin and geometry.
- **PX4**: has motor failure detection from ESC telemetry (`FD_ACT_EN`, `FD_ACT_MOT_TOUT`) and an action: the `COM_ACT_FAIL_ACT` failsafe (warning/Hold/Land/Return/Terminate), while `CA_FAILURE_MODE = 1` removes the motor from the mixer.
- **INAV**: the mixer has no special logic; a hexa/X8 with thrust margin keeps flying, yaw degrades.

{{diagram:redundancy-schemes|What each layout survives when one motor fails.}}

## practice
### Step 1. Failure table
For your layout: failure of a motor (each position), ESC, battery/connector, BEC, receiver, GPS, compass, IMU → does it survive / what's noticeable / what to do. A “countermeasure” column: redundancy, detection, failsafe.

### Step 2. Power diagram
Draw the buses with fuses, dual BECs (ORing), separate branches for the companion/payload. Per-arm currents, wire gauges, connectors, capacitors. Check the drops by calculation (the widget in the “Electricity 101” module).

### Step 3. Motor failure in SITL
ArduPilot SITL: `SIM_ENGINE_FAIL` — a bitmask of motors (motor 1 → 1, motor 3 → 4, in the code `engine_fail & (1<<i)`), `SIM_ENGINE_MUL = 0` — a complete failure (0.5 — loss of half the thrust) in Loiter on a hexa/X8 (`-f hexa` / `-f octa-quad`), watch `RCOU`, altitude, yaw. Record: did it hold altitude, the yaw rotation rate, is a higher T/W needed. Repeat with `-f quad` — see the difference.

### Step 4. Test stand
Aircraft secured, no props: disconnect one ESC signal, make sure the firmware doesn't panic and the others respond. With props — only on a safe stand with a tether and an observer, if at all. Lab: failure table, power diagram, SITL failure described.

**Automatic log check (SITL):** `check_lab_log.py <log.bin> --lab motorfail` — the failure is visible (saturated output), altitude held (drop < 5 m), roll tracking p99 < 15°.

## diagnostics
- **Symptom:** a hexa spins and falls after a motor failure
  - Possible cause: T/W on the remaining motors < 2, no yaw margin.
  - What to do: more thrust/less mass, MOT_YAW_HEADROOM, an X8 instead of a hexa.
- **Symptom:** one X8 arm runs hotter
  - Possible cause: a wire/connector too thin for the double current.
  - What to do: 12 AWG, XT90, check the soldering.
- **Symptom:** the FC rebooted on a current peak
  - Possible cause: a single BEC on a sagging bus.
  - What to do: dual BECs with ORing, capacitors, power the FC from a power module with margin.
- **Symptom:** RC loss when the antenna turns
  - Possible cause: a single receiver without diversity.
  - What to do: diversity or a second receiver on another band.
- **Symptom:** one RCOU channel at maximum in the log
  - Possible cause: a motor/ESC failed or a prop broke.
  - What to do: land; check the ESC telemetry RPM for that motor.

## references
- ArduPilot — Motor Mixing and Yaw Headroom (MOT_YAW_HEADROOM) | https://ardupilot.org/copter/docs/parameters.html#mot-yaw-headroom | primary | A
- ArduPilot — SITL simulation parameters (SIM_* incl. engine failure) | https://ardupilot.org/dev/docs/SITL_simulation_parameters.html | primary | A
- PX4 — Motor Failure Detection | https://docs.px4.io/main/en/config/motor_failure_detection | primary | A

## checklist
- I know which failure breaks which layout and why
- The failure table for my aircraft is filled in
- Power is designed with fuses and dual BECs
- Per-arm currents are computed, wire gauges and connectors have margin
- A motor failure is simulated in SITL, the behavior is described
