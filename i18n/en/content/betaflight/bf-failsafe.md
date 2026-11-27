---
id: bf-failsafe
title: "Failsafe: stages, procedures and the switch test"
level: L1
readingTime: 20 min
firmware: Betaflight 2025.12 (checked against 2025.12.5)
status: published
added: 2026-11-07
tags:
  - failsafe
  - safety
related:
  - bf-modes-osd
  - link-elrs
  - bf-led-buzzer
next:
  - bf-rpm-filter
source: content/betaflight/bf-failsafe.md
source_hash: 554332ef17f6
---

## summary
Failsafe is what the drone does when the link to the radio is lost. In Betaflight 4.3+ it is a two-stage process: a short “guard” Stage 1, then Stage 2 with the selected procedure (DROP, AUTO-LAND or GPS-RESCUE). This module explains how it works, how to choose a procedure for your drone and how to test failsafe safely with a switch, without turning the radio off in the air.

## theory
### How Betaflight decides the link is lost
After 150 ms without valid packets (100 ms in 4.5) the FC sets RXLOSS. The channels hold their last values for 300 ms from the last good packet (not from the detection of the loss), then get the `rxfail` values. That is Stage 1; Stage 2 is when there has been no signal for longer than `failsafe_delay` from the last good packet.

{{diagram:failsafe-stages|Failsafe timing diagram: loss detection, the short hold, Stage 1 and Stage 2.}}

{{lesson:link-elrs|Why an ELRS receiver simply goes silent on link loss, when it declares a disconnect itself, and what link margin each packet rate has.}}

### Stage 1 — the guard period
It lasts `failsafe_delay` (in tenths of a second: 15 = 1.5 s; 1.5 s by default (the same in 4.3–4.4; what changed between 4.4 and 4.5 is `failsafe_recovery_delay`: 1.0 → 0.5 s)). By default the sticks are centered, the throttle is at zero and the switch positions are held. The value for each channel is set in Betaflight App (Stage 1 - Channel Fallback Settings) or with the `rxfail` command. If the signal returns during Stage 1, control is restored instantly.

**How to choose `failsafe_delay`.** Stage 1 is a fall: after the 300 ms hold the throttle gets its `rxfail` value, and by default that is minimum (`RX_FAILSAFE_MODE_AUTO` in `rx/rx.c`); only airmode keeps stabilization going. A free fall over t seconds is h = ½·g·t²: with the default 1.5 s (1.2 s at minimum throttle) the aircraft loses up to 7 m, with 1.0 s (0.7 s) — up to 2.4 m (ignoring air resistance, hence “up to”). A shorter delay means less altitude lost before the Stage 2 procedure, but a dropout longer than the delay (antenna orientation, foliage, the edge of coverage) then triggers Stage 2: with DROP that is a disarm in the air, and with AUTO-LAND and GPS Rescue control comes back only after `failsafe_recovery_delay` (and for Rescue — also after the sticks are moved). The course rule (an estimate):
- **DROP, a 5" within visual range** — the default 15: the margin against a false disarm matters more than a few meters of fall;
- **AUTO-LAND and GPS Rescue at altitude** — 10 (1 s), as in “A worked example: 7" long range” below: at 250 Hz that is 250 lost packets in a row, at 50 Hz — only 50, so on the slow packet rates do not go below 10;
- **the check** — in the radio's telemetry (`RQly`, `link-edgetx`) find the longest LQ dropout to zero in ordinary flights: the delay should be at least twice as long (a course guideline); otherwise fix the link first (`link-elrs`, “Link margin”), not the delay.

### Stage 2 — the procedure
It is selected with the `failsafe_procedure` setting:

- `DROP` (the default) — an immediate disarm, the motors stop. Re-arming is possible after `failsafe_recovery_delay` of a stable signal (0.5 s by default in 4.5 and 2025.12) and with the ARM switch turned off.
- `AUTO-LAND` — the sticks are centered, the throttle is at `failsafe_throttle`, the Stage 1 modes are applied, and after `failsafe_landing_time` seconds (before 2025.12 — `failsafe_off_delay`, in tenths of a second, default 10 = 1 s) — a disarm. Re-arming — after `failsafe_recovery_delay` of a stable signal, as with DROP.
- `GPS-RESCUE` — needs GPS: the drone flies home and lands. To regain control you need a signal for `failsafe_recovery_delay` and a stick deflection greater than `failsafe_stick_threshold` (30% of stick travel).

A subtlety: if the throttle was at minimum for ≥10 s before Stage 2, a simple disarm happens (except for GPS Rescue). Stage 2 is not possible for the first 5 s after boot.

Video after a disarm: `vtx_low_power_disarm` (ON or UNTIL_FIRST_ARM) lowers the VTX power on the ground, but **not while failsafe is active** (`vtxGetSettings()` in `io/vtx.c` checks `!failsafeIsActive()`). After DROP the aircraft is disarmed, but failsafe stays active until the signal is recovered — the VTX keeps transmitting at flight power, and a crashed aircraft can be found by its picture (link-vtx).

`failsafe_landing_time` is in seconds, default 60, range 0–250 (in 4.5 its place is taken by `failsafe_off_delay`: tenths of a second, default 10, range 0–200). If the build has altitude hold and there is an altitude source (baro or GPS), AUTO-LAND descends through ALT_HOLD (`flight/alt_hold_multirotor.c`): faster when high, slower near the ground. A new PID profile setting, `landing_disarm_threshold` (0–250, default 0 = off), disarms on ground impact: after takeoff, with the sticks centered and zero throttle **or** in ALT_HOLD (and therefore in AUTO-LAND as well — but only when it runs through ALT_HOLD; with a fixed `failsafe_throttle` the throttle is not zero, and this disarm does not trigger), if the accelerometer jerk is greater than the threshold × 10 (`disarmOnImpact()` in `flight/pid.c`; the comment on the default in `pid.c:243` says “relatively safe values are around 100”, while the comment at the check itself, `pid.c:968`, says “eg around 10” — the source comments contradict each other, so the threshold is chosen from a log, as below). Without it AUTO-LAND disarms when `failsafe_landing_time` runs out (or earlier, if crash recovery triggered). 4.5 does not have this setting. How to check the threshold: `debug_mode = EZLANDING` logs jerk × 1000 in debug[7] (`flight/pid.c`); the disarm triggers when the jerk is greater than `landing_disarm_threshold` × 10, that is, in log units — when debug[7] is greater than the threshold × 10,000 (near the ground in ALT_HOLD the jerk is multiplied by 1.5, and the boundary in the log is the threshold × 10,000 / 1.5). In a log of several landings and sharp throttle chops in flight, debug[7] at touchdown must be above this boundary, and its maximum in the air — below it. A disarm in the air on a throttle chop — raise the threshold; the aircraft does not disarm after touchdown — lower it.

### What to choose
DROP is the honest choice for freestyle over a safe area: the drone falls nearby instead of flying away. AUTO-LAND with the throttle slightly below hover gives a controlled descent — sensible for heavy 7–10" builds and flights over people/equipment, but it requires choosing `failsafe_throttle` for the specific drone. In Stage 2 (AUTO-LAND and GPS Rescue) Betaflight enables ANGLE itself if there is an accelerometer; the fallback of the ANGLE channel affects only Stage 1. How many seconds to give AUTO-LAND and when GPS-RESCUE is needed instead — in the next subsection.

### AUTO-LAND time: how to choose `failsafe_landing_time`
**What happens when the time is up.** The timer starts on entering Stage 2: `failsafe.c` records the end moment as “now + `failsafe_landing_time` × 1000 ms”. When it arrives, the `FAILSAFE_LANDED` phase disarms (`DISARM_REASON_FAILSAFE`) — whatever altitude the aircraft is at. AUTO-LAND ends ahead of time only if crash recovery triggered, the disarm on impact triggered (`landing_disarm_threshold`, only in ALT_HOLD) or the aircraft is already disarmed. **Too short a time is a DROP from altitude, only later:** the motors stop in the air, and the aircraft falls from whatever altitude it had descended to — possibly farther from you and over exactly what you did not want it to fall on. Example: 10 s at a descent of 1 m/s — from 50 m the aircraft disarms at about 40 m.

**What sets the descent rate.** It depends on whether the build has an altitude source (`fc/core.c`: ALT_HOLD in failsafe is enabled with an accelerometer, altitude from baro or GPS and the throttle already raised after arming):

| Build | What holds the throttle | Descent rate | What happens after touchdown |
|---|---|---|---|
| no baro and no GPS altitude | a fixed `failsafe_throttle`: `rx/rx.c` substitutes it for the throttle channel; the default is 1000, that is, throttle to zero | not regulated by anything: it depends on the weight, the battery charge and the wind — only measure it | the throttle is not zero, the disarm on impact does not work: the motors spin at `failsafe_throttle` until the timer ends |
| baro or GPS altitude and an accelerometer | the ALT_HOLD altitude controller from `ap_hover_throttle` (default 1275); `failsafe_throttle` is not involved | the target in `flight/alt_hold_multirotor.c`: `alt_hold_climb_rate` (default 50 = 5 m/s) × (0.9 + h / 20 m), but no less than 1×: 5 m/s near the ground, 9.5 m/s at 20 m; the comment at the same place in the source gives other numbers (about 1 m/s near the ground), so the rate must be measured from a log | `landing_disarm_threshold` disarms, if it is enabled; otherwise — the timer |

**The rule.** `failsafe_landing_time` ≥ (h_max / v_descent) × 1.5, where h_max is the greatest altitude at which you fly this aircraft (from the OSD or logs), and v_descent is the measured descent rate in Stage 2. The 1.5 margin is a course estimate: toward the end of the discharge and in wind the rate at a fixed throttle changes, and h_max is not known exactly. There is an upper bound on the time only for builds without an altitude source: every extra second after touchdown means motors spinning on the ground, so approach the aircraft only after the disarm. The limit of the setting is 250 s; if the rule gives more, AUTO-LAND is the wrong choice for this aircraft.

{{diagram:chart-failsafe-landing-time|AUTO-LAND time by the rule h_max / v × 1.5: at 1 m/s from 30 m you need 45 s, and from 150 m — 225 s, almost the 250 s limit of the setting, which is why a 7" long range flies with GPS-RESCUE; the slower the descent, the sooner you hit the limit.}}

**What the aircraft class changes.** The altitudes in the table are a course estimate; take your own h_max from your flights.

| Class | Working altitude | Stage 2 | `failsafe_landing_time` |
|---|---|---|---|
| A whoop indoors | 1–3 m | DROP: a fall of a light whoop from 2 m is safer than a minute of motors running on the floor; without a baro AUTO-LAND is not controllable in a room | not used |
| 5" freestyle over a safe area | any | DROP (subsection “What to choose”) | not used |
| 5–7" within line of sight, no GPS, over something you care about | up to 30 m | AUTO-LAND | 30 / 1 × 1.5 = 45 s at a measured 1 m/s |
| 7" long range beyond line of sight | 50–150 m | GPS-RESCUE | AUTO-LAND is no good here: 150 / 1 × 1.5 = 225 s — almost the 250 s limit, and all that time the aircraft, with no position hold, drifts with the wind and lands where the link was lost — far from you |
| Heavy 7–10" over people and equipment | per the job | AUTO-LAND within line of sight, GPS-RESCUE — beyond | by the rule; with a baro — measure the ALT_HOLD descent |

**When Stage 2 is GPS-RESCUE and not AUTO-LAND.** When the place where the link is lost is far away or out of sight: the aircraft has to be brought back, not landed wherever it happens to be. The conditions are from the subsection “GPS Rescue: what it needs”: a fix before arming, home recorded, preferably with a compass. Without them Rescue is useless, and what remains is AUTO-LAND by the rule above or DROP.

**The procedure.**
1. Write down h_max for the aircraft.
2. Measure v_descent at your `failsafe_throttle` (step 4 of the practice): at 10 m hold the FAILSAFE switch for 5 s longer than `failsafe_delay`, release it, take over. From the log: the `baroAlt` field (with a baro) or `GPS_altitude` — v = Δh / Δt over the Stage 2 section; in the goggles — the `NUMERICAL_VARIO` OSD element or the altitude before and after. Without a baro or GPS — with a stopwatch against an object of known height; such an estimate is rough, so take a margin of 2 instead of 1.5 (an estimate).
3. Calculate the time by the rule, round up, and write it in the drone's log together with h_max and v.
4. The check: on any change of battery, props or weight, step 3 of the practice (hover throttle) and this measurement are repeated — afterwards the hover throttle and the descent rate are different.

### The switch test: failsafe_switch_mode
The FAILSAFE mode on an AUX channel lets you trigger failsafe without turning the radio off:

- `STAGE1` — Stage 1 at once, the AUX channels stay active. Hold the switch longer than `failsafe_delay` — the transition to Stage 2. Release it — control is back. This is the most honest test: it reproduces a real link loss.
- `STAGE2` — the selected Stage 2 procedure immediately; releasing the switch returns control.
- `KILL` — an immediate disarm. One channel glitch = a crash. Not for flying.

### The full set of settings (CLI)
`failsafe_delay` (tenths of a second, Stage 1), `failsafe_landing_time` (seconds, the AUTO-LAND time before the disarm, default 60), `failsafe_throttle` (the AUTO-LAND throttle, 750–2250, default 1000), `failsafe_throttle_low_delay` (tenths: if the throttle was below minimum for longer than this — just disarm; default 100 = 10 s; 0 — a disarm at any low throttle at the moment of link loss), `failsafe_procedure` (DROP / AUTO-LAND / GPS-RESCUE), `failsafe_switch_mode` (STAGE1 / KILL / STAGE2), `failsafe_recovery_delay` (tenths, how long the signal must be stable before control is returned), `failsafe_stick_threshold` (%, the stick deflection for exiting GPS Rescue). The channel values in Stage 1 — `rxfail <channel> <mode> [value]`: `a` (auto: center/minimum throttle), `h` (hold — keep the last value), `s <value>` (set — a fixed value, for example 1700 on the ANGLE channel). The check: `rxfail` without arguments prints the table.

### Failsafe and the beeper
- **RX_LOST** (0.5 s of sound, 0.5 s of pause) starts together with Stage 2 — when there has been no signal for longer than `failsafe_delay`, not at the moment of RXLOSS — and repeats until the signal returns and holds for `failsafe_recovery_delay`. In 2025.12 it sounds on any link loss if the FC does not see USB (a VCP connection or the detect pin), including while disarmed. In 4.5 — only while armed or if there has been an arm since power-up: the `WAS_EVER_ARMED` flag is set on disarm and cleared by an FC reboot.
- In AUTO-LAND and GPS Rescue, while the aircraft is armed, SOS (`RX_LOST_LANDING`) sounds instead of RX_LOST; after the disarm — RX_LOST again. With DROP it is RX_LOST at once.
- `rxfail` acts on AUX channels even without an active failsafe. `rxfail <3 + n> s 2000` on the channel of the BEEPER switch (AUXn) turns the beeper on 0.3 s after link loss — even while disarmed and after an FC reboot.
- On link loss the motors (DShot beacon) beep with `beacon RX_LOST` (off by default; needs DShot, no sooner than 1.2 s after the disarm, and in 2025.12 — the FC does not see USB). `beacon RX_SET` does not work on link loss in 2025.12; in 4.5 it works too — with `rxfail` on the BEEPER channel.

{{lesson:bf-led-buzzer|The exact RX_LOST code, the priorities of the beeper conditions, rxfail for the BEEPER switch and the procedure for finding a crashed aircraft.}}

### GPS Rescue: what it needs to work
A GPS with a fix of ≥ `gps_rescue_min_sats` (8 by default) **before arming** (home is recorded on arming), `gps_rescue_min_start_dist` (the minimum distance; closer than that — simply the landing/DROP logic), the return altitude `gps_rescue_alt_mode` (MAX_ALT / FIXED_ALT / CURRENT_ALT) and `gps_rescue_return_alt`, the speeds `gps_rescue_ground_speed`, `gps_rescue_ascend_rate/descend_rate`, the descent and landing `gps_rescue_descent_dist` (the distance from which the descent begins), `gps_rescue_descend_rate`, `gps_rescue_disarm_threshold` (disarm on impact), `gps_rescue_initial_climb`; without a compass the heading is taken from GPS while moving — that is why Rescue first climbs and flies, “feeling out” the heading; with a compass (`mag_hardware`) it is more reliable. The sanity checks (`gps_rescue_sanity_checks`) abort Rescue if the distance is growing or the aircraft is falling. Test only in an open area, with the GPS RESCUE switch at a moderate altitude and distance, with a finger on the mode switch and a spotter; leave `gps_rescue_allow_arming_without_fix` OFF — otherwise Rescue without a home is useless.

**Where to start.** The Betaflight 2025.12.5 defaults (`pg/gps_rescue_multirotor.c`): `gps_rescue_min_start_dist` 15 m, `gps_rescue_alt_mode` MAX_ALT, `gps_rescue_initial_climb` 10 m, `gps_rescue_return_alt` 30 m, `gps_rescue_ground_speed` 750 (7.5 m/s), `gps_rescue_ascend_rate` 750 (7.5 m/s), `gps_rescue_descent_dist` 20 m, `gps_rescue_descend_rate` 150 (1.5 m/s), `gps_rescue_disarm_threshold` 30, `gps_rescue_min_sats` 8. Change them for the site (a course guideline): the return altitude — above the tallest obstacle on the route with a margin, the return speed — below what the aircraft can hold against the wind (`ops-weather`); leave the rest until a switch test shows a reason. An example of the changes for a 7" is the next subsection.

### A worked example: 7" long range
`failsafe_procedure = GPS-RESCUE`, `failsafe_delay = 10` (1 s: at 250 Hz that is 250 lost packets — an unmistakable loss), `gps_rescue_min_sats = 8`, `gps_rescue_alt_mode = MAX_ALT` (return at the maximum altitude of the flight + a margin), `gps_rescue_return_alt = 50`, `gps_rescue_ground_speed = 1000` (10 m/s), `gps_rescue_descend_rate = 150`, `rxfail 5 s 1700` (the ANGLE channel), ELRS: over CRSF the receiver itself stops sending channels on link loss; on an SBUS output both modes are suitable — `No Pulses` (no frames) and `Last Position` (frames keep coming with the failsafe flag, and Betaflight reads it in `rx/sbus_channels.c`); “No Pulses” is mandatory only where there is no flag (PWM/PPM outputs), otherwise Stage 1 will not start, the LQ warning in the OSD. The check: on the ground without props — turn the radio off: without arming failsafe does not start, and the OSD will show only `RXLOSS`; test the stages with the FAILSAFE switch while armed without props; in the field — with the switch at 30 m of altitude and 60 m from home, with a spotter, ready to take over.

### Place in the system

- **Receives:** the absence of valid RC packets — over CRSF the receiver stops sending frames on link loss (`link-elrs`); the FAILSAFE mode switch (`bf-modes-osd`); home and the satellite count for GPS Rescue (`bf-gps-setup`); the hover throttle as a reference for `failsafe_throttle` (`bf-setup-scratch`).
- **Provides:** a disarm, a descent or a return home; the `FAILSAFE` and `RXLOSS` flags — to the arming block (`bf-arming-safety`); the “failsafe is active” condition under which the VTX does not lower its power (`link-vtx`); the link state from which the beeper gives RX_LOST (`bf-led-buzzer`). The AUX values on link loss are substituted by `rxfail` (`rx/rx.c`) — even without failsafe.
- **If you get it wrong here:** you chose GPS-RESCUE but home is not recorded (an arm without a fix) → on link loss Rescue is useless; the cause is looked for in `bf-gps-setup` and `bf-arming-safety`. You left the FAILSAFE switch in KILL mode → one glitch of the AUX channel gives an immediate disarm in the air; in the log it is the disarm event and `failsafePhase` (`bf-blackbox`).

## practice
### Step 1. Look at the current values
Do not memorize the defaults — read them from the specific controller:

```
get failsafe
rxfail
```

### Step 2. Set up AUTO-LAND with a switch test
An example from practice (a 7", the failsafe switch on AUX6):

```
set failsafe_procedure = AUTO-LAND
set failsafe_switch_mode = STAGE1
set failsafe_delay = 15
set failsafe_throttle = 1250
set failsafe_landing_time = 45
save
```

45 s follows from the rule in the theory for this aircraft: a working altitude of up to 30 m, the target of step 3 — about 1 m/s, 30 / 1 × 1.5 = 45. This is a starting value: after the measurement in step 4, recalculate it from your own descent rate and your own h_max. A value of 10 at 1 m/s gives a disarm after 10 m of descent — from 30 m that is a fall from 20 m.

Then, in the Modes tab, put FAILSAFE on a switch, and in Stage 1 - Channel Fallback Settings set the ANGLE channel to a value that enables ANGLE. This is needed only for Stage 1: in Stage 2 ANGLE is enabled automatically (a calibrated accelerometer is required).

### Step 3. Choose the failsafe throttle from a log
1. Fly a flight with a hover and a Blackbox log.
2. Find the median hover throttle (the `rcCommand[3]` field or the motor average).
3. Set `failsafe_throttle` slightly below hover — the target is a descent of about 1 m/s. For a heavy 10" that may be 1350, for a light 7" — 1250: the value is individual.

### Step 4. The test
1. Without props: arm, flip the failsafe switch, make sure the OSD shows `RXLOSS` and, once `failsafe_delay` has passed, `!FS!` in the flight-mode element (read from the source, not bench-verified), the motors behave as expected, and control returns after the switch is released.
2. With props, at an altitude of 5–10 m over a soft surface: in ANGLE turn the switch on for about 1 s (shorter than `failsafe_delay`), release. Repeat, holding it longer than `failsafe_delay`.
3. The descent rate: at 10 m hold the switch for 5 s longer than `failsafe_delay`, release, take over control. From the log (`baroAlt` or `GPS_altitude`) or from the OSD calculate v = Δh / Δt and recalculate `failsafe_landing_time` = h_max / v × 1.5 (subsection “AUTO-LAND time”). If you let the aircraft land in Stage 2, release the switch after touchdown and disarm: without a baro the motors spin at `failsafe_throttle` until the time runs out.
4. Write the test date, the settings, h_max and the measured v in the drone's log.

**Reference for self-check.** With the config from step 2 the correct result is this: while the switch is on for less than `failsafe_delay` (1.5 s), only Stage 1 runs — the OSD Warnings element shows `RXLOSS`, and control returns immediately after release. Hold it longer than 1.5 s — Stage 2: the flight-mode element shows `!FS!`, and after the failsafe disarm the warnings add `FAILSAFE` (the OSD texts are read from `osd/osd_warnings.c` and `flight/failsafe.c`, not bench-verified); sticks centered, ANGLE, throttle at `failsafe_throttle`, a descent of about 1 m/s (over the 5 s of holding in item 3 of step 4 — about 5 m), a disarm after `failsafe_landing_time` = 45 s; after it, arming is possible only by turning ARM off and on again. The time is consistent if the value written in the log is no less than h_max / v × 1.5 by your measurements: at v = 1 m/s and h_max = 30 m — 45 s; at v = 1.5 m/s 30 s is enough; at v = 0.7 m/s you need 65 s. A wrong result is a time shorter than h_max / v: at the working altitude the aircraft disarms in the air. The drone climbs or hovers — `failsafe_throttle` is not below hover throttle, go back to step 3. The drone tumbles or drifts off to the side — the accelerometer is disabled or not calibrated.

## diagnostics
- **Symptom:** after a failsafe the drone does not arm, the OSD shows `NOT_DISARMED`
  - Possible cause: the ARM switch was left on.
  - What to do: turn ARM off and on again after `failsafe_recovery_delay`.
- **Symptom:** in AUTO-LAND the drone tumbles or drifts off to the side
  - Possible cause: the accelerometer is disabled or not calibrated (ANGLE in Stage 2 is enabled automatically only with an ACC), or `failsafe_throttle` is not tuned.
  - What to do: set up Channel Fallback Settings / `rxfail` for the ANGLE channel.
- **Symptom:** in AUTO-LAND the drone climbs
  - Possible cause: `failsafe_throttle` is above hover throttle (for example, after a change of battery or props).
  - What to do: recalculate the hover throttle from a fresh log.
- **Symptom:** RXLOSS / failsafe in ordinary flight
  - Possible cause: a weak link (the receiver antenna, the packet rate, TX power).
  - What to do: look at RSSI/LQ in the log, see the module on ExpressLRS.
- **Symptom:** when the radio is turned off the aircraft keeps flying on the last stick positions
  - Possible cause: on link loss the receiver holds the last values and does not report the loss (neither “no pulses” nor a failsafe flag in the SBUS frame) — Stage 1 does not start.
  - What to do: configure the receiver's failsafe (ELRS over CRSF always goes silent; for an SBUS output `No Pulses` and `Last Position` are both suitable — in the second case the frame carries the failsafe flag, which Betaflight reads; PWM/PPM — only “no pulses”; FrSky — select it), and test without props.
- **Symptom:** GPS Rescue does not fly home / “goes crazy”
  - Possible cause: home was recorded with a poor fix, there is no compass and too little speed for a GPS heading, magnetic interference.
  - What to do: arm after a fix with 8+ satellites, the compass on a mast, check `gps_rescue_sanity_checks`.
- **Symptom:** after the signal returns, control does not come back
  - Possible cause: `failsafe_recovery_delay` + the requirement to move the sticks (`failsafe_stick_threshold`).
  - What to do: deflect a stick > the threshold; reduce recovery_delay moderately.

## references
- Failsafe — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/Failsafe | primary | A
- Failsafe tab — Betaflight App | https://betaflight.com/docs/wiki/app/failsafe-tab | primary | A
- Betaflight — Failsafe tab | https://betaflight.com/docs/wiki/app/failsafe-tab | secondary | B
- Betaflight 2025.12.5 — source: `flight/failsafe.c` (the AUTO-LAND timer and disarm), `rx/rx.c` (substitution of `failsafe_throttle`), `flight/alt_hold_multirotor.c` (the descent in failsafe), `flight/pid.c` (`disarmOnImpact`) | https://github.com/betaflight/betaflight | primary | A

## checklist
- A Stage 2 procedure is chosen, and it is clear why that one
- FAILSAFE is assigned to a switch with `failsafe_switch_mode = STAGE1`
- For AUTO-LAND: the fallback enables ANGLE, the throttle is chosen from a log
- For AUTO-LAND: the descent rate is measured, `failsafe_landing_time` ≥ h_max / v × 1.5
- The test without props is passed
- The test in the air at a safe altitude is passed
- The failsafe settings are written in the drone's log
