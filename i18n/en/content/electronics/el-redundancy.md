---
id: el-redundancy
title: "Onboard redundancy: X8, hexa, power and signals"
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
source_hash: 0866b679a166
---

## summary
A quadcopter with a failed motor is a falling object; a hexa and an X8 can keep flying, if the power, signals and firmware are designed for it. This module looks at which failures each layout survives and why (yaw moments), how to distribute power on a heavy aircraft (buses, fuses, dual BECs, a backup receiver), how to calculate the currents per X8 arm and choose wire gauges and connectors, and how to test the behavior on a motor failure in SITL and on a test stand, before it happens in the air.

## theory
### What each layout survives
- **Quad**: the failure of any motor means loss of yaw and roll control; a controlled fall at best. Redundancy is geometrically impossible.
- **Hexa (6 arms)**: on a single motor failure the remaining five can hold altitude and roll/pitch, but yaw is held poorly (the CW/CCW balance is broken): the aircraft slowly rotates and lands. You need T/W ≥ 2 on the remaining motors. Without special settings, ArduPilot and PX4 simply "give more throttle" to the rest through the mixer; this works if there is thrust margin.
- **X8 (coaxial octo)**: on a single motor failure, the coaxial partner and the opposite pair compensate both thrust and torque: the most survivable layout with 8 motors on 4 arms. The price is a 10–20% efficiency loss of the coaxial pair.
- **Flat octo**: like a hexa, but with more margin; it survives two failures in lucky positions.
- **VTOL**: a lift motor failure in vertical mode is like a quad; in forward flight the lift motors are not needed, so a different failure logic applies.

What fails more often than a motor: an ESC (overheating, breakdown), the power connector, the flight controller's BEC, the receiver, the GPS, one of two IMUs. Redundancy starts with a failure table, not with extra motors.

### Powering a heavy aircraft
Example: an X8 on 6S with 8 motors of the 4008/4006 380KV class (the MN4006 table, 15×5): hover ~3.6–3.9 A per motor, maximum ~15–16 A: hover ~30 A, peak ~130 A.

- **Buses**: a single power bus from the battery is a single point of failure. An option: two batteries in parallel through diode/ideal-diode ORing modules, or simply two parallel batteries with a fuse on each; if one fails, you fly on the other.
- **Fuses**: on each battery (ANL/MIDI rated ≥ 1.33 × the branch's maximum continuous current, rounded up to the next standard value), on the companion/payload branch, on the BEC. Why 1.33: a fuse's rating at 25 °C is derated by 25 % to avoid nuisance blowing (Littelfuse, "The Twelve Cardinal Rules of Fuseology", rule 1), so the operating current is ≤ 0.75 × the rating, and 1 / 0.75 ≈ 1.33. Type: time-delay (as ANL and MIDI are): the inrush current when the battery is plugged in and when the motors start is compared against the fuse's time-current curve and I²t (same source, rule 6). Also check the DC voltage rating against the full-charge pack voltage (rule 2: common ANL/MIDI fuses are typically 32 V DC, enough for 6S but not for 8S at 33.6 V) and the interrupting rating against the pack's short-circuit current (rule 5); in a hot frame derate further (rule 3). Not on the motors: the current is pulsed, so the fuse will either blow for nothing or fail to protect.
- **Dual BECs**: two 5 V BECs with diode ORing to the FC and receiver (a Pixhawk-class board accepts three sources: power module, USB, servo rail, with priority). If one BEC fails, the aircraft lives.
- **Receiver**: two receivers (the main CRSF plus a backup on another band) or one with diversity; ArduPilot: `RC_OPTIONS` bit 10 (multiple receiver support), a backup input on another UART; PX4: a backup between RC and MAVLink control (`COM_RC_IN_MODE`; `RC_MAP_*` only assigns channels); INAV: at least one receiver with diversity antennas.
- **GPS/compass**: two GPS units with blending (`GPS_AUTO_SWITCH`) on DroneCAN, two compasses with priority.
- **IMU**: H7 flight controllers have two or three IMUs, and the EKF switches by itself (EK3 runs several cores).

### Currents per X8 arm
Each arm carries two motors: arm current = 2 × motor current. Hover ~7.5 A, maximum ~32 A per arm. Arm wire 12–14 AWG; an XT60 arm connector (30 A continuous, 60 A instantaneous per the Amass datasheet) is at its limit at full throttle; an XT90 (45 A on 12 AWG) has margin. The central distribution board: 4 arms × 32 ≈ 130 A peak, so copper busbars or a 150+ A PDB, an AS150 on each battery: with two batteries in parallel, ~65 A flows through each connector at the peak and ~15 A in hover, within the 75 A of the Amass catalog; on a single battery 130 A exceeds both the AS150 and the XT90 (60 A for one minute); capacitors at the input of each ESC pair.

The drop across a 30 cm 12 AWG arm wire at 32 A: R = 0.0172 × 0.6 / 3.31 ≈ 3.1 mΩ → 0.10 V, 3.2 W of heat at the peak, acceptable; with 14 AWG (≈ 5.0 mΩ) 0.16 V and 5 W, tolerable, but with less margin for long sessions.

{{diagram:x8-power-redundancy|The module's X8 power layout: the aircraft survives the failure of one battery or one BEC, there are no fuses on the motors, and for an arm at ~32 A an XT60 is at its limit while an XT90 has margin.}}

### Firmware behavior on a failure
- **ArduPilot**: the mixer normalizes the outputs; on saturation roll/pitch come first, then yaw, as much as fits (`MOT_YAW_HEADROOM` is the guaranteed minimum), and throttle goes into the remaining range. A motor failure shows in `RCOU` (one channel at maximum, its neighbor at minimum) and in the `ESC` telemetry (RPM 0). There is a thrust loss check (the message "Potential Thrust Loss (n)"): the mixer enables thrust boost and removes the lost motor from yaw control; but survivability is still determined by thrust margin and geometry.
- **PX4**: motor failure detection from ESC telemetry (`FD_ACT_EN`, default 0 in 1.18, so enable it explicitly; thresholds `MOTFAIL_C2T`, `MOTFAIL_OFF`, `MOTFAIL_TIME`, before 1.18 `FD_ACT_MOT_*`) and an action: the failsafe `COM_ACT_FAIL_ACT` (Warning only/Hold/Land/Return/Terminate), and `CA_FAILURE_MODE = 1` removes the motor from the mixer.
- **INAV**: the mixer has no special logic; a hexa/X8 with thrust margin keeps flying, with degraded yaw.

{{diagram:redundancy-schemes|What each layout survives when a single motor fails.}}

### Where it fits in the system

- **Takes in:** T/W and the frame layout, which determine what is left after a motor failure (`f-physics`, `ctl-allocation`); the motor currents from the thrust table (`f-aero-props`); component failure rates (`ops-maintenance`).
- **Puts out:** a power layout with two batteries, fuses and dual BECs (`el-power-design`); the failure table to the failsafe setup (`ap-safety-fs`); motor failure scenarios to testing in the simulator (`ap-sitl`, `ap-lua`).
- **If you get this wrong:** a hexa without T/W ≥ 2 margin on five motors → on a motor failure the mixer saturates, yaw is lost, the aircraft descends; in the log one `RCOU` channel sits at maximum (`ap-logs`). One power bus and one BEC → a connector failure cuts the log off without a disarm event (tree 6 in `diag-troubleshooting`).

## practice
### Step 1. Failure table
For your layout: failure of a motor (in each position), ESC, battery/connector, BEC, receiver, GPS, compass, IMU → survives or not / what is noticeable / what to do. A "remedy" column: redundancy, detection, failsafe.

### Step 2. Power layout
Draw the buses with fuses, dual BECs (ORing), separate branches for the companion/payload. The currents per arm, wire gauges, connectors, capacitors. Check the drops by calculation (the widget in the "Electricity 101" module).

### Step 3. A motor failure in SITL
ArduPilot SITL: `SIM_ENGINE_FAIL` is a bitmask of motors (motor 1 → 1, motor 3 → 4; in the code `engine_fail & (1<<i)`), `SIM_ENGINE_MUL = 0` is a complete failure (0.5 is a loss of half the thrust), in Loiter on a hexa/X8 (`-f hexa` / `-f octa-quad`); watch `RCOU`, altitude, yaw. Record: whether it held altitude, the yaw rotation rate, whether a higher T/W is needed. Repeat with `-f quad` to see the difference.

### Step 4. Test stand
The aircraft tied down, no props: disconnect one ESC signal and make sure the firmware does not panic and the others respond. With props, only on a safe tethered stand with an observer, if at all. Self-check: the lab is done when every row of the failure table has the "remedy" column filled in, the drops in the power layout are calculated, and the SITL motor failure is recorded in numbers (altitude loss, yaw rotation rate, the `RCOU` outputs) for a hexa or X8 and for a quad.

**Reference answer for self-check.** The table: a quad does not survive the failure of any motor (redundancy is geometrically impossible); a hexa holds altitude and roll/pitch but slowly rotates in yaw, and needs T/W ≥ 2 on the remaining motors; an X8 compensates both thrust and torque with the coaxial partner and the opposite pair. The layout: check the drop calculation against the X8 arm example: 30 cm of 12 AWG at 32 A ≈ 3.1 mΩ, 0.10 V and 3.2 W; a fuse on each battery rated ≥ 1.33 × the branch's maximum continuous current (rounded up to the next standard rating), no fuses on the motors. SITL: in `RCOU` one channel at maximum, its neighbor at minimum; on a hexa and an X8 the altitude is held (a loss of < 5 m, the same threshold as in the automatic check below), and with `-f quad` the aircraft falls. Common wrong results: the failure "does not show", because `SIM_ENGINE_FAIL` was given the motor number instead of the mask (motor 3 is 4); the hexa loses altitude, which means not enough thrust margin, a conclusion about T/W, not a setup error.

**Automatic log check (SITL):** `check_lab_log.py <log.bin> --lab motorfail`: the failure is visible (a saturated output), altitude is held (a loss of < 5 m), roll tracking p99 < 15°.

## diagnostics
- **Symptom:** a hexa rotates and falls after a motor failure
  - Possible cause: T/W on the remaining motors < 2, no yaw margin.
  - What to do: more thrust/less mass, MOT_YAW_HEADROOM, an X8 instead of a hexa.
- **Symptom:** one X8 arm runs hotter
  - Possible cause: a thin wire/connector for double the current.
  - What to do: 12 AWG, XT90, check the soldering.
- **Symptom:** the FC rebooted at a current peak
  - Possible cause: a single BEC on a sagging bus.
  - What to do: dual BECs with ORing, capacitors, power the FC from a power module with margin.
- **Symptom:** RC loss when the antenna turns
  - Possible cause: a single receiver without diversity.
  - What to do: diversity or a second receiver on another band.
- **Symptom:** one RCOU channel at maximum in the log
  - Possible cause: a motor/ESC failed or a prop broke.
  - What to do: land; check the ESC telemetry RPM of that motor.

## references
- ArduPilot — Motor Mixing and Yaw Headroom (MOT_YAW_HEADROOM) | https://ardupilot.org/copter/docs/parameters.html#mot-yaw-headroom | primary | A
- ArduPilot — SITL simulation parameters (SIM_* incl. engine failure) | https://ardupilot.org/dev/docs/SITL_simulation_parameters.html | primary | A
- PX4 — Motor Failure Detection | https://docs.px4.io/main/en/config/motor_failure_detection | primary | A
- Amass — XT90H-M datasheet (UL1977 30 A; 60 A for 1 min; recommended current 45/50/55 A on 12/10/8 AWG at a 60 K rise) | https://atta.szlcsc.com/upload/public/pdf/source/20220706/D6369ADC773D7B5378E901BEE0D5B60C.pdf | primary | A
- Amass — XT60H-M datasheet V1.2 (30 A continuous, 60 A instantaneous, 12 AWG) | https://cdn.eicom.ru/media/PDF/XT60H-M.pdf | primary | A
- Amass — XT30UPB datasheet (UL1977 15 A; 30 A for 1 min; 15 A on 18 AWG, 20 A on 16 AWG at a 60 K rise) | https://atta.szlcsc.com/upload/public/pdf/source/20230412/7B5DFEF57C9EA5273853390C734B3AC5.pdf | primary | A
- Amass — product catalog (AS150: 75 A MAX, 8 AWG, rise < 85 K) | https://www.rcscomponents.kiev.ua/datasheets/Amas-cat1.pdf | primary | B
- Holybro — Connector & Wire Rating (XT60 12 AWG: 30 A for 4 h and 60 A for 1 min at a rise < 60 K) | https://docs.holybro.com/power-module-and-pdb/power-module/connector-and-wire-rating | secondary | B
- Littelfuse (B. Shenoy) — The Twelve Cardinal Rules of Fuseology (rule 1: derate the rating by 25 % at 25 °C; rule 6: inrush currents call for a time-delay fuse, checked against I²t) | https://www.allaboutcircuits.com/industry-articles/the-twelve-cardinal-rules-of-fuseology/ | primary | B

## checklist
- I know which failure breaks which layout and why
- The failure table for my aircraft is filled in
- The power is designed with fuses and dual BECs
- The currents per arm are calculated, wire gauges and connectors have margin
- A motor failure was simulated in SITL and the behavior described
