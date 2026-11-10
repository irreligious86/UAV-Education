---
id: f-safety
title: "Safety and the Pre-Flight Check"
level: L1
readingTime: 25 min
firmware: any firmware
status: published
added: 2026-11-07
tags:
  - safety
  - checklist
  - LiPo
  - arming
related:
  - bf-failsafe
  - f-power
  - f-regulations
  - ops-field
next:
  - f-regulations
source: content/foundation/f-safety.md
source_hash: c3dbe1ced49d
---

## summary
The tip of a 5-inch prop moves at about 300 km/h and carries enough energy to cut skin down to the bone; a shorted LiPo dumps hundreds of amps and burns with its own oxidizer: you can knock the flame down, but the burning restarts until the cells cool off. Most injuries in the hobby happen not in the air but on the bench: the drone armed with props on during setup. This module gives you the physics of the danger in numbers, the rules that are not up for discussion, the full list of Betaflight arming disable flags (from the source code, with explanations) and the ArduPilot equivalent, pre-flight and post-flight checklists, and what to do in a battery fire.

## theory
### Danger in numbers
- **Propeller.** Tip speed = π · D · n. For a 5" (D = 0.127 m) in hover at 14,000 rpm (233 rev/s): 0.40 m × 233 ≈ 93 m/s — about 335 km/h; unloaded, up to 30,000 rpm — 200 m/s. The kinetic energy of a spinning 5" prop (~4 g) is a few joules: enough for deep cuts; 7–10" — tens of joules, broken fingers; 15" on an X8 — injuries that end your hobby.
- **Motors on the bench.** A motor test in the configurator without removing the props is a classic injury. The firmware warns you but won't stop you.
- **LiPo.** Internal resistance is 1–3 mΩ per cell: a short circuit of a 6S pack means hundreds of amps, and the wire glows hot within a second. A cell punctured in a crash can catch fire minutes or hours after the impact. The burning is thermal runaway with oxygen released from the cathode: knock the flame down (ABC extinguisher, sand), then **cool with plenty of water**, or carry it outside in a non-flammable container and let it burn out. A class D extinguisher is designed for metallic lithium — LiPo and Li-Ion don't contain any. A puffed pack is retired: discharge it to 0 in salt water (several days) and dispose of it.
- **Link loss.** If failsafe hasn't been tested on this aircraft, it will do something nobody chose (module “Failsafe”).
- **The first flight after any change** — a swapped motor, prop direction, wrong mixer, untested filter: statistically the most dangerous flight.

### How the firmware protects against arming (Betaflight master; 2025.12 has no `AUTOPILOT_SW`, 4.5 has no `FLIP_SWITCH`/`ALT_HOLD_SW`/`POS_HOLD_SW`/`AUTOPILOT_SW`, and `ARM_SWITCH` is called `ARMSWITCH`)
Arming is impossible while at least one disable flag is active. The list lives in `src/main/fc/runtime_config.c`; the flags are shown by `status` in the CLI and in the OSD (the “Warnings” element):

{{diagram:arming-tree|“Won't arm” troubleshooting tree: read the flag first, then check the specific cause.}}

| Flag | What it means | What to do |
|---|---|---|
| `NOGYRO` | gyro not detected | check the board/target, don't fly |
| `FAILSAFE` / `BOXFAILSAFE` | failsafe active (no RC) / failsafe switch on | restore the link, turn the switch off |
| `RXLOSS` | no receiver signal | bind, RX power, port protocol |
| `NOT_DISARMED` | not disarmed after… | disarm with the switch |
| `RUNAWAY` | runaway takeoff protection triggered | disarm; check motor/prop direction |
| `CRASH` | crash detector | disarm/reboot |
| `THROTTLE` | throttle not at minimum | throttle stick down, check `min_check` |
| `ANGLE` | tilt greater than `small_angle` | level it, or `small_angle = 180` for Acro |
| `BOOTGRACE` | not enough time since power-on | wait |
| `NOPREARM` | PREARM not enabled | enable PREARM |
| `LOAD` | CPU overload | lower the loop rate/disable features |
| `CALIB` | calibration in progress | wait |
| `CLI`, `CMS`, `MSP`, `BST` | CLI / OSD menu open / configurator connected | close it — and that's how it should be |
| `PARALYZE` | PARALYZE mode activated | reboot |
| `GPS` | GPS Rescue requires a fix, there isn't one | wait for a fix or disable the requirement |
| `RESCUE_SW` | GPS Rescue switch on at arming | turn it off |
| `DSHOT_TELEM` | RPM filter enabled, but no eRPM from the ESC | `dshot_bidir`, ESC firmware, wires |
| `REBOOT_REQD` | reboot required after setup | reboot |
| `DSHOT_BBANG` | bitbang DShot error | check resources/timers |
| `NO_ACC_CAL` | accelerometer not calibrated | calibrate |
| `MOTOR_PROTO` | motor protocol not configured | select DShot |
| `FLIP_SWITCH`, `ALT_HOLD_SW`, `POS_HOLD_SW`, `AUTOPILOT_SW` | mode switch on at arming | turn it off |
| `ARM_SWITCH` | ARM switch was on when connected | turn it off and on again |

These flags are a safety net, not a nuisance. The rule: fix the cause, don't disable the check. **ArduPilot**: `ARMING_SKIPCHK` (4.7+, a bitmask of **skipped** checks; before 4.7 — `ARMING_CHECK`, a bitmask of enabled ones: baro, compass, GPS, INS, parameters, RC, voltage, geofence…), and “PreArm: …” messages in the GCS follow the same logic; skipping checks is acceptable only on a test stand.

### Modes and devices for protection
- **PREARM** — a second switch without which arming is impossible; mandatory on aircraft with 7"+ props.
- **Failsafe** — what to do on link loss; tested on the ground without props before the first flight of every new build.
- **Beeper** and **GPS in the OSD** — to find a crashed aircraft.
- **Runaway takeoff prevention** (Betaflight `runaway_takeoff_prevention = ON`) — disarms if, after arming, the gyro shows growing rotation that doesn't respond to control inputs (swapped motors/props).
- **Low-battery buzzer, timer** — so you don't keep flying on a depleted battery.

### Site and people
The safe zone radius around takeoff is at least 10–15 m for a 5", 30 m for heavy aircraft; nobody stands in the plane of the props during arming; take off away from yourself. Rules and zones — module “Rules”, team organization — “Field Operations”.

## practice
### Pre-flight checklist (print it)
1. Props: intact, tightened, direction matches the motor diagram, no foreign objects in the prop plane.
2. Battery: no puffing or damage, per-cell voltage normal (4.1–4.2 V/cell when full), secured with a strap, XT connector not melted.
3. RC and VTX antennas: in place, intact, not in the prop plane; VTX with antenna attached (without one it will burn out).
4. Radio: correct model, charged, ARM/PREARM switches off, failsafe test done on this aircraft.
5. Video/OSD: voltage, LQ/RSSI, warnings — no flags.
6. Zone: people and animals outside the radius, takeoff away from yourself, obstacles accounted for, site rules.
7. After arming: 2–3 s of hover at 0.5–1 m — response, sound, no shaking; at the slightest oddity — land.

### Bench rules
1. Props off before you plug in the battery. Always. Including “just for a second”.
2. The first power-up of a new/resoldered build goes through a smoke stopper, with a multimeter check beforehand (module “Electricity 101”).
3. Motor test — only without props, with limited throttle, with your hand at the battery connector.
4. Configurator connected → `MSP` flag → arming impossible. Don't bypass it.
5. Charge LiPos in a fireproof bag/box, under supervision, in balance mode, not on a flammable surface; store at 3.8 V/cell.

### In a battery fire
1. Don't touch it with your hands, don't blow on it. Step back, get people to step back (the smoke is toxic).
2. Sand/earth on top, or drag it with a metal object onto a non-flammable surface.
3. Extinguisher — knock the flame down, then cool (the burning can restart).
4. Afterwards — don't leave it unattended for an hour; put the remains in a metal container.

### After the flight
1. Disarm, turn the radio off last (not first!), unplug the battery.
2. Feel the motor and ESC temperature by hand; inspect the props and frame.
3. Entry in the aircraft log: what you changed, how it flew, what you noticed; the log file — if it was a test flight.

## diagnostics
- **Symptom:** the drone won't arm
  - Possible cause: an arming disable flag is active.
  - What to do: `status` in the CLI or OSD Warnings; the table above; fix the cause.
- **Symptom:** the drone armed right after the battery was plugged in
  - Possible cause: the ARM switch was on and the `ARM_SWITCH` protection was disabled/didn't trigger, or arming is assigned to the wrong channel.
  - What to do: check Modes, the ARM channel range, add PREARM.
- **Symptom:** after arming the aircraft lurched sideways and disarmed
  - Possible cause: runaway takeoff — swapped motors/prop direction.
  - What to do: motor test without props, direction diagram, `resource`/`motor` remap.
- **Symptom:** after a crash the battery heats up with no load
  - Possible cause: an internal short.
  - What to do: isolate it on a non-flammable surface outdoors, watch it, don't charge it, dispose of it.
- **Symptom:** the VTX is hot, no video
  - Possible cause: it was powered without an antenna.
  - What to do: always attach the antenna before power; the VTX may already be damaged.

## references
- Arming Sequence & Safety — Betaflight Documentation | https://www.betaflight.com/docs/wiki/guides/current/Arming-Sequence-And-Safety | primary | A
- Betaflight source — fc/runtime_config.c (armingDisableFlagNames) | https://github.com/betaflight/betaflight/blob/master/src/main/fc/runtime_config.c | primary | A
- Pre-Arm Safety Checks — ArduPilot Copter | https://ardupilot.org/copter/docs/common-prearm-safety-checks.html | primary | A
- Safety — ArduPilot Copter (multicopter safety practices) | https://ardupilot.org/copter/docs/safety-multicopter.html | primary | A

## checklist
- No props on the bench — no exceptions
- I know all the arming disable flags and what to do with each
- The pre-flight checklist is printed and in use
- Failsafe tested on this drone without props
- I know what to do in a LiPo fire and where the sand is
- After every flight I make an entry in the aircraft log
