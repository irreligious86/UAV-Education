---
id: bf-modes-osd
title: "Modes and OSD"
level: L1
readingTime: 20 min
firmware: Betaflight 4.5+
status: published
added: 2026-11-07
tags:
  - modes
  - OSD
  - AUX
related:
  - link-protocols
  - bf-failsafe
next:
  - bf-failsafe
source: content/betaflight/bf-modes-osd.md
source_hash: 824a1129635a
---

## summary
Modes are what you put on switches: arm, self-leveling, beeper, failsafe test, flip over after crash. The OSD is what you see in your goggles: voltage, timer, link, warnings. This module explains how AUX channel ranges work, which modes are mandatory, which are dangerous, and how to build an OSD that warns you in advance instead of stating the obvious after the fact. Plus a working layout from several 7–10" drones, designed so your hands remember it.

## theory
### How the Modes tab works
Each mode is bound to an AUX channel and a range of values (1000–2000 µs). Switch in that range — the mode is active. Several modes can share one channel in different ranges (a three-position switch). The check is at the bottom of the tab: flip the switch and watch which mode lights up.

### Mandatory
- **ARM** — always a separate two-position switch, with no neighbors on the channel. On the bench — props off.
- **ANGLE** — self-leveling. Even if you fly ACRO, keep it on a switch: it saves you when you lose orientation (in Stage 2 failsafe ANGLE turns on automatically, you don't need the switch for that).
- **BEEPER** — to find the drone in the grass.
- **FAILSAFE** — failsafe test from a switch (see the failsafe module), STAGE1 mode.

### Useful
- **AIR MODE** — PID works at zero throttle; for ACRO it is almost always on permanently (no switch).
- **PREARM** — a second switch without which arming is impossible. A must for heavy drones.
- **FLIP OVER AFTER CRASH** — flip back over from the ground after a crash. Only when the drone is lying still and the props don't touch anything.
- **HORIZON** — self-leveling that still lets you flip; **ACRO TRAINER** — angle limit in ACRO for training.
- **GPS RESCUE** — return home by GPS (a separate switch and separate setup).
- **BLACKBOX** — record the log only on a switch, if the flash chip is small.
- **OSD DISABLE**, **VTX PIT MODE**, **PARALYZE** — situational.

### Example layout
A layout from several drones of one team, identical on all of them so you don't have to think in the air: ARM on AUX1, ANGLE on AUX3, FAILSAFE (STAGE1) on AUX6, BEEPER on AUX7, PREARM on AUX8. The rule: the same switches on every drone you fly.

### OSD
Elements are selected in the OSD tab; positions are stored in the `osd_*_pos` parameters. The minimum set for safety: voltage (average per cell — `osd_avg_cell_voltage_pos`), timer, link quality / RSSI, flight mode, warnings, `craft_name`. For long range — mAh consumed, GPS satellites, direction and distance to home.

Warnings (`osd_warn_bitmask`): low voltage, failsafe, RXLOSS, arming flags. Set the voltage thresholds so the warning comes with enough margin to fly back, not at the last few percent.

Analog OSD (MAX7456 chip) and digital (MSP DisplayPort for Walksnail/HDZero/DJI) are configured in the same tab, but the set of elements and the resolution differ.

### The `aux` command and mode logic
`aux <index> <mode id> <aux channel> <start> <end> <logic>`: rule index, mode id — the `permanentId` from `msp/msp_box.c` (ARM = 0, ANGLE = 1, HORIZON = 2, FAILSAFE = 27, PREARM = 36), not the enum number from `fc/rc_modes.h`, AUX channel (0 = AUX1), range 900–2100 in steps of 25, logic 0 = OR, 1 = AND (the mode is active only if **both** this rule **and** the previous rule of the same mode are satisfied — this is how you make “ARM only if PREARM on the same channel” or two-switch combinations). Ranges for a three-position switch: 900–1300, 1300–1700, 1700–2100 — with a gap, so jitter doesn't toggle modes at the boundary. `adjrange` does the same for “in-flight adjustments” (PID, rates, profiles) from a switch or a knob.

### OSD: set it up for meaning, not looks
- **OSD profiles** (`osd_profile`, up to 3) — on a switch: “minimal” for racing, “full” for long range, “empty” for recording.
- **Warnings** (`osd_warn_bitmask`): ARMING_DISABLE, BATTERY_WARNING/CRITICAL, FAIL_SAFE, LINK_QUALITY, RSSI, CORE_TEMP, GPS_RESCUE_*, OVER_CAP — enable all except the noisy ones; `osd_cap_alarm`, `osd_alt_alarm`, `osd_rssi_alarm`, `osd_link_quality_alarm` are the thresholds.
- **Voltage**: show the average per cell (`osd_avg_cell_voltage_pos`) and set `vbat_warning_cell_voltage` based on sag under load (3.5 V for 5" LiPo, 3.3 for Li-Ion), `vbat_min_cell_voltage` is the critical one; `vbat_sag_compensation` is not an indicator: it raises motor output when the voltage sags so the response doesn't “drift” as the battery discharges.
- **Link**: LQ and RSSI dBm from CRSF (not `rssi_channel`), warning at LQ < 70% on 250 Hz ELRS (the “Link budget” module).
- **Timer**: `osd_tim1`/`osd_tim2` (source, precision, threshold) — on arm; for Li-Ion, mAh drawn matters more.
- HD (MSP DisplayPort): `osd_displayport_device`, canvas 50×18/60×22 — elements outside the analog canvas are not displayed; `osd_canvas_width/height`.

### Worked example: a team layout
AUX1 ARM (1700–2100), AUX2 mode: ACRO (900–1300, nothing active) / ANGLE (1300–1700) / HORIZON (1700–2100); AUX3 PREARM (1700–2100, logic AND with ARM on the 7"+ drones); AUX4 BEEPER (1700–2100); AUX5 FAILSAFE STAGE1 (1700–2100) — for testing on the ground and in the first flights; AUX6 BLACKBOX (1700–2100) if the flash is small; AUX7 OSD profile 1/2/3. Written into the aircraft's logbook and into the radio model; identical on every aircraft.

{{diagram:bf-modes-layout|Example mode layout across AUX channels.}}

## practice
### Step 1. Switch layout
1. On the radio: assign switches to channels AUX1…AUX8 (CH5…CH12).
2. In Modes: ARM — AUX1, range only on the top position.
3. ANGLE — a separate switch; FAILSAFE — STAGE1 on a three-position switch; BEEPER; PREARM if needed.
4. At the bottom of the tab — check that each switch turns on only its own mode.
5. `diff all` — save it. Write the layout into the drone's log and repeat it on the others.

### Step 2. OSD
1. Pick the elements: voltage per cell, timer, LQ/RSSI, mode, warnings, name.
2. Arrange them so the center of the screen stays clear.
3. Voltage warning thresholds — for your battery and flying style (a reference point: a warning at about 3.5 V per cell under load, landing — based on your own experience).
4. Check in the goggles on the bench without props: all elements are visible and don't overlap.

### Step 3. Ground test
Without props: arm/disarm, ANGLE (the model in the configurator levels out), beeper, failsafe switch (`FAILSAFE` in the OSD). Only after that — out to the field.

## diagnostics
- **Symptom:** won't arm, OSD shows `ARMSWITCH` (in 2025.12 — `ARM_SWITCH`) or `NOPREARM`
  - Possible cause: the ARM switch was on when power was applied, or PREARM is not on.
  - What to do: switch ARM off and on again, check PREARM.
- **Symptom:** a mode turns on from the wrong switch
  - Possible cause: wrong channel or range.
  - What to do: check at the bottom of Modes, and in the Receiver tab see which channel moves.
- **Symptom:** no OSD in the goggles
  - Possible cause: OSD not enabled in Configuration, wrong type (analog/digital), UART not configured for DisplayPort.
  - What to do: check the OSD type and Ports.
- **Symptom:** the voltage warning comes too late
  - Possible cause: the threshold is based on resting voltage.
  - What to do: raise the threshold to account for sag under load.
- **Symptom:** a mode “flickers” at the switch boundary
  - Possible cause: a range with no gap, channel jitter.
  - What to do: ranges with a 100 µs gap, check in the Receiver tab.
- **Symptom:** OSD elements “moved” after switching to HD
  - Possible cause: positions were set for the analog canvas.
  - What to do: rearrange them in the HD profile, `osd_canvas_*`.

## references
- Auxiliary (Modes) tab — Betaflight App | https://betaflight.com/docs/wiki/app/auxiliary-tab | primary | A
- OSD tab — Betaflight App | https://betaflight.com/docs/wiki/app/osd-tab | primary | A
- Mode box names (msp_box.c, GitHub) | https://github.com/betaflight/betaflight/blob/master/src/main/msp/msp_box.c | primary | A
- Arming Sequence & Safety — Betaflight Documentation | https://www.betaflight.com/docs/wiki/guides/current/Arming-Sequence-And-Safety | primary | A

## checklist
- ARM on a separate switch, with no neighbors on the channel
- ANGLE, BEEPER, FAILSAFE assigned
- The layout is the same on all my drones and written down
- In the OSD: voltage per cell, timer, LQ, mode, warnings
- Voltage thresholds account for sag
- Ground test without props passed
