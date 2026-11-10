---
id: bf-failsafe
title: "Failsafe: stages, procedures and the switch test"
level: L1
readingTime: 20 min
firmware: Betaflight 4.5+
status: published
added: 2026-11-07
tags:
  - failsafe
  - safety
related:
  - bf-modes-osd
  - link-elrs
next:
  - bf-rpm-filter
source: content/betaflight/bf-failsafe.md
source_hash: 2a1cc24bc80b
---

## summary
Failsafe is what the drone does when the link to the radio is lost. In Betaflight 4.3+ it's a two-stage process: a short “guard” Stage 1, then Stage 2 with the chosen procedure (DROP, AUTO-LAND or GPS_RESCUE). This module explains how it works, how to pick the procedure for your drone, and how to test failsafe safely with a switch, without turning off the radio in the air.

## theory
### How Betaflight decides the link is lost
If there are no valid packets for 100 ms, the signal is considered lost. The last values are held for another 300 ms, after which Stage 1 kicks in. The countdown to Stage 2 runs from the last good packet.

{{diagram:failsafe-stages|Failsafe timing diagram: loss detection, a short hold, Stage 1 and Stage 2.}}

### Stage 1 — the guard interval
It lasts `failsafe_delay` (in tenths of a second: 15 = 1.5 s; default 1.5 s (the same in 4.3–4.4; between 4.4 and 4.5 `failsafe_recovery_delay` changed: 1.0 → 0.5 s)). By default the sticks are centered, throttle is at zero, switch positions are held. Per-channel values are set in the Configurator (Channel fallback) or with the `rxfail` command. If the link returns during Stage 1, control comes back instantly.

### Stage 2 — the procedure
Chosen with the `failsafe_procedure` parameter:

- `DROP` (default) — instant disarm, motors stop. Re-arming is possible after `failsafe_recovery_delay` of stable link (0.5 s by default in 4.5) and with the ARM switch off.
- `AUTO-LAND` — sticks centered, throttle at `failsafe_throttle`, Stage 1 modes applied, disarm after `failsafe_off_delay`. Re-arming — after `failsafe_recovery_delay` of stable link, same as with DROP.
- `GPS_RESCUE` — needs GPS: the drone flies home and lands. To get control back you need the link for `failsafe_recovery_delay` and stick deflection greater than `failsafe_stick_threshold` (30% of stick travel).

A subtlety: if throttle was at minimum for ≥10 s before Stage 2, a plain disarm happens (except for GPS Rescue). Stage 2 is impossible for the first 5 s after boot.

### What to choose
DROP is the honest choice for freestyle over a safe area: the drone falls nearby instead of flying away. AUTO-LAND with throttle just below hover gives a controlled descent — sensible for heavy 7–10" quads and flights over people/vehicles, but it requires tuning `failsafe_throttle` for the specific drone. In Stage 2 (AUTO-LAND and GPS Rescue) Betaflight enables ANGLE by itself if an accelerometer is present; the ANGLE channel fallback only affects Stage 1.

### Switch test: failsafe_switch_mode
The FAILSAFE mode on an AUX channel lets you trigger failsafe without turning off the radio:

- `STAGE1` — straight into Stage 1, AUX channels stay active. Hold the switch longer than `failsafe_delay` — transition to Stage 2. Release it — control is back. This is the most honest test: it reproduces a real link loss.
- `STAGE2` — straight into the chosen Stage 2 procedure; releasing returns control.
- `KILL` — instant disarm. One channel glitch = a crash. Not for flying.

### All the parameters (CLI)
`failsafe_delay` (tenths of a second, Stage 1), `failsafe_off_delay` (tenths, AUTO-LAND time until disarm; in 2025.12 replaced by `failsafe_landing_time` in seconds, default 60), `failsafe_throttle` (AUTO-LAND throttle, 1000–2000), `failsafe_throttle_low_delay` (tenths: if throttle was below minimum longer than this — just disarm; default 100 = 10 s; 0 — disarm at any low throttle at the moment the link is lost), `failsafe_procedure` (DROP / AUTO-LAND / GPS-RESCUE), `failsafe_switch_mode` (STAGE1 / KILL / STAGE2), `failsafe_recovery_delay` (tenths, how long the link must be stable before control returns), `failsafe_stick_threshold` (%, stick deflection to exit GPS Rescue). Channel values for Stage 1 — `rxfail <channel> <mode> [value]`: `a` (auto: center/min throttle), `h` (hold — keep the last value), `s <value>` (set — a fixed value, e.g. 1700 on the ANGLE channel). Check: `rxfail` with no arguments prints the table.

### GPS Rescue: what it needs to work
A GPS fix with ≥ `gps_rescue_min_sats` (8 by default) **before arming** (home is recorded at arming), `gps_rescue_min_start_dist` (the minimum distance; closer than that — just landing/DROP logic), the return altitude `gps_rescue_alt_mode` (MAX_ALT / FIXED_ALT / CURRENT_ALT) and `gps_rescue_return_alt`, the speeds `gps_rescue_ground_speed`, `gps_rescue_ascend_rate/descend_rate`, descent and landing `gps_rescue_descent_dist` (the distance at which the descent starts), `gps_rescue_descend_rate`, `gps_rescue_disarm_threshold` (disarm on impact), `gps_rescue_initial_climb`; without a compass the heading comes from GPS while moving — that's why Rescue first climbs and flies, “feeling out” the heading; with a compass (`mag_hardware`) it's more reliable. Sanity checks (`gps_rescue_sanity_checks`) abort Rescue if the distance keeps growing or the aircraft is falling. Test only in an open area, with the GPS RESCUE switch at moderate altitude and distance, with your finger on the mode switch and an observer; leave `gps_rescue_allow_arming_without_fix` OFF — otherwise Rescue without a home point is useless.

### Worked example: 7" long range
`failsafe_procedure = GPS-RESCUE`, `failsafe_delay = 10` (1 s: at 250 Hz that's 250 lost packets — a clear loss), `gps_rescue_min_sats = 8`, `gps_rescue_alt_mode = MAX_ALT` (return at the maximum flight altitude + a margin), `gps_rescue_return_alt = 50`, `gps_rescue_ground_speed = 1000` (10 m/s), `gps_rescue_descend_rate = 150`, `rxfail 5 s 1700` (the ANGLE channel), ELRS: failsafe “no pulses” in the receiver (otherwise Stage 1 won't start), an LQ warning in the OSD. Check: on the ground without props — turn off the radio: without arming, failsafe doesn't start, the OSD will only show `RXLOSS`; check the stages with the FAILSAFE switch while armed without props; in the field — with the switch at 30 m altitude and 60 m from home, an observer, ready to take over.

## practice
### Step 1. Look at the current values
Don't memorize the defaults — read them from your specific controller:

```
get failsafe
rxfail
```

### Step 2. Set up AUTO-LAND with a switch test
A real-world example (7", failsafe switch on AUX6):

```
set failsafe_procedure = AUTO-LAND
set failsafe_switch_mode = STAGE1
set failsafe_delay = 15
set failsafe_throttle = 1250
set failsafe_off_delay = 100
save
```

Then on the Modes tab put FAILSAFE on a switch, and in Channel fallback for the ANGLE channel set a value that enables ANGLE. This is only needed for Stage 1: in Stage 2 ANGLE is enabled automatically (a calibrated accelerometer is required).

### Step 3. Pick the failsafe throttle from the log
1. Fly a hover with a Blackbox log.
2. Find the median hover throttle (the `rcCommand[3]` field or motor average).
3. Set `failsafe_throttle` slightly below hover — aim for about 1 m/s descent. On a heavy 10" that might be 1350, on a light 7" — 1250: the value is individual.

### Step 4. Test
1. Without props: arm, flip the failsafe switch, make sure the OSD shows `FAILSAFE`, the motors behave as expected, and control returns after you release it.
2. With props, at 5–10 m over a soft surface: in ANGLE flip the switch for 2–3 s, release. Repeat holding it longer than `failsafe_delay`.
3. Record the test date and parameters in the drone's log.

## diagnostics
- **Symptom:** after failsafe the drone won't arm, the OSD shows `NOT_DISARMED`
  - Possible cause: the ARM switch was left on.
  - What to do: turn ARM off and on again after `failsafe_recovery_delay`.
- **Symptom:** in AUTO-LAND the drone tumbles or drifts sideways
  - Possible cause: the accelerometer is disabled or not calibrated (ANGLE in Stage 2 is enabled automatically only with ACC), or `failsafe_throttle` isn't tuned.
  - What to do: set Channel fallback / `rxfail` for the ANGLE channel.
- **Symptom:** in AUTO-LAND the drone climbs
  - Possible cause: `failsafe_throttle` is above hover throttle (e.g. after changing the battery or props).
  - What to do: recalculate hover throttle from a fresh log.
- **Symptom:** RXLOSS / failsafe in normal flight
  - Possible cause: a weak link (receiver antenna, packet rate, TX power).
  - What to do: look at RSSI/LQ in the log, see the ExpressLRS module.
- **Symptom:** when you turn off the radio, the aircraft keeps flying on the last stick values
  - Possible cause: the receiver isn't in “no pulses”/cut mode — Stage 1 doesn't start.
  - What to do: set up the receiver's failsafe (ELRS: “no pulses” by default; FrSky — select it), check without props.
- **Symptom:** GPS Rescue doesn't fly home / “goes crazy”
  - Possible cause: home recorded with a poor fix, no compass and too little speed for a GPS heading, magnetic interference.
  - What to do: arm after a fix with 8+ satellites, put the compass on a mast, check `gps_rescue_sanity_checks`.
- **Symptom:** after the link returns, control doesn't come back
  - Possible cause: `failsafe_recovery_delay` + the requirement to deflect the sticks (`failsafe_stick_threshold`).
  - What to do: deflect a stick past the threshold; lower recovery_delay moderately.

## references
- Failsafe — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/Failsafe | primary | A
- Failsafe tab — Betaflight App | https://betaflight.com/docs/wiki/app/failsafe-tab | primary | A
- Betaflight — Failsafe tab | https://betaflight.com/docs/wiki/app/failsafe-tab | secondary | B

## checklist
- A Stage 2 procedure is chosen and it's clear why that one
- FAILSAFE is assigned to a switch with `failsafe_switch_mode = STAGE1`
- For AUTO-LAND: the fallback enables ANGLE, throttle is picked from the log
- The test without props is passed
- The in-air test at a safe altitude is passed
- The failsafe parameters are recorded in the drone's log
