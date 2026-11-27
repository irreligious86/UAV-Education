---
id: bf-arming-safety
title: "Why it won't arm and how not to fly away: arming flags, runaway takeoff, yaw spin recovery"
level: L2
readingTime: 45 min
firmware: Betaflight 2025.12 (checked against 2025.12.5); the lab was captured on the 4.5.x sources (branch 4.5-maintenance, 7dcc851; version.h 4.5.6, the latest release is 4.5.5)
status: published
tags:
  - Betaflight
  - arming
  - safety
  - runaway takeoff
  - yaw spin
  - airmode
related:
  - bf-setup-scratch
  - f-safety
  - bf-modes-osd
  - bf-failsafe
  - bf-cli
  - bf-blackbox
  - bf-pid-reg-in-bf
  - f-motors-esc
  - diag-troubleshooting
  - bf-led-buzzer
next:
  - bf-filters
source: content/betaflight/bf-arming-safety.md
source_hash: 941c888a08b7
---

## summary
A reference module on the most frequent Betaflight question: “why won't it arm”. Here is the full table of the 29 arming disable flags of version 2025.12 (`armingDisableFlagNames[]` in `fc/runtime_config.c`; 4.5 has 26 flags): what sets each flag in the source and how to clear it. It covers where to read these flags: the Setup tab, `status` in the CLI, `MSP_STATUS_EX`, the OSD warning and the beeper code. Then — arming with a switch and with the sticks, PREARM, disarm, airmode. The protections that act after arming are covered separately: runaway takeoff prevention (the thresholds and the deactivation conditions are taken from `fc/core.c`), yaw spin recovery and crash recovery. One more section is about what swapped motors, a wrong rotation direction and the wrong prop look like on takeoff. A Python lab: a flag mask decoder on real masks, including the trap with bit numbers in the 4.5 → 2025.12 transition, and the runaway logic reproduced from the source on synthetic data. Then on hardware: clearing the flags one at a time without props, the motor order and direction test, the first arm without props and the first low hover with abort criteria.

## theory
### Where to read the flags
{{diagram:bf-arming-flag-groups|The arming disable flags (26 in 4.5, 29 in 2025.12) come down to five actions: move the switch or throttle, let the sensors settle, close the app/CLI/menu, fix the motor protocol or ESC, and after RUNAWAY, CRASH and PARALYZE — disarm or reboot.}}

The reasons for an arming block are stored in a single 32-bit mask (`armingDisableFlags_e`, `fc/runtime_config.h`). It is visible in four places:
- **Betaflight App → Setup → Arming Disable Flags.** The app gets the mask through `MSP_STATUS_EX`. The response has a byte with the number of flags (29 in 2025.12, 26 in 4.5) and the `uint32` of the mask itself (`msp/msp.c`).
- **CLI, the `status` command.** The line `Arming disable flags:` lists the names of all set flags from the lowest bit to the highest (`cliStatus()`). The documentation warns that on some stripped-down builds only hex is printed. Then decode the mask with the table for your version (step 1 of the practice).
- **OSD, the Warnings element.** The flags are shown **only while the ARM switch is on** and arming is blocked. The names alternate every 0.5 s. `ARM_SWITCH` (before 2025.12 — `ARMSWITCH`) is hidden if there are other reasons (`osd/osd_warnings.c`).
- **The beeper.** The code sounds on every failed arm attempt with a new reason: `tryArm()` → `beeperWarningBeeps(ffs(flags))`. First 4 fast beeps of 50 ms (in 4.5 — 5; `beeperWarningBeeps()` in `io/beeper.c`), then N/5 long ones (250 ms) and N%5 short ones (50 ms). N = bit number + 1. The beeper reports **only the lowest bit**, that is, the most critical reason: the flags are sorted by importance. Example: 1 long + 1 short = 6 = `RUNAWAY`.

{{lesson:bf-led-buzzer|The other beeper signals: the priorities of the conditions, the `beeper` mask, RX_LOST after a crash and the DShot beacon through the motors.}}

### All 29 flags of Betaflight 2025.12
The code is the number for the beeper (bit + 1). The source is the file where the flag is set. Codes 1–25 are the same in 4.5 and 2025.12; the conditions in rows 1–25 are checked against the 4.5.x source (branch `4.5-maintenance`, commit `7dcc851`: `version.h` says 4.5.6, but there is no such release; the latest release is 4.5.5, and the `src/` code matches it except for the version number in `version.h`), rows 26–29 — against 2025.12.5. 4.5 has 26 flags: there are no codes 26–28, and the last flag is called `ARMSWITCH` and has code 26.

| Code | Flag | When it is set | What to do |
|---|---|---|---|
| 1 | `NOGYRO` | the gyro was not found at startup (`fc/init.c`) | the wrong target or a dead gyro; the sensor line of `status` has no `GYRO=` |
| 2 | `FAILSAFE` | failsafe has disarmed the aircraft (`FAILSAFE_LANDED`, `flight/failsafe.c`); held until the link is back for `failsafe_recovery_delay` | restore the link; it clears after recovery |
| 3 | `RXLOSS` | no valid RC frames for 150 ms (100 ms in 4.5); after the link appears it is held for `failsafe_recovery_delay` = 5 (0.5 s) | RX wiring, bind, `serialrx_provider`, the Receiver tab |
| 4 | `NOT_DISARMED` | the link came back while the ARM switch is on | turn ARM off |
| 5 | `BOXFAILSAFE` | the FAILSAFE mode switch is on | turn it off |
| 6 | `RUNAWAY` | the runaway takeoff protection triggered | turn ARM off (or disarm with the sticks), look for the cause |
| 7 | `CRASH` | `crash_recovery = DISARM` saw a crash | turn ARM off, inspect the aircraft |
| 8 | `THROTTLE` | throttle ≥ `min_check` (1050) | throttle down; check the endpoints, the trim, `rxrange` |
| 9 | `ANGLE` | tilt > `small_angle` (25°) or level has not been estimated yet (`isUpright()`) | place it level, calibrate the accelerometer; with FLIP OVER AFTER CRASH enabled the flag is not set |
| 10 | `BOOTGRACE` | less than `pwr_on_arm_grace` (5 s) has passed since startup; with DShot — also until DShot commands are allowed | wait |
| 11 | `NOPREARM` | a PREARM range is set, and the mode is off or has not been toggled since the last arm | turn PREARM off and on |
| 12 | `LOAD` | over the last second more than `cpu_late_limit_permille` = 10 (1.0 %) of tasks ran late | reduce the load: the PID rate, unneeded features; look at `tasks` |
| 13 | `CALIB` | the gyro, accelerometer, baro or compass is calibrating; gyro calibration restarts if the standard deviation > `gyro_calib_noise_limit` (48) | do not touch the aircraft for ~1.25 s (`gyro_calib_duration` = 125 × 10 ms) |
| 14 | `CLI` | the CLI is open; the flag is held until reboot, `exit noreboot` (available from 4.5.4) does not clear it | `exit` or `save` |
| 15 | `CMS` | the OSD menu (CMS) is open | exit the menu |
| 16 | `BST` | Black Sheep Telemetry; the flag is not set anywhere in either 4.5 or 2025.12 | — |
| 17 | `MSP` | Betaflight App (Configurator) sent `MSP_ARMING_DISABLE` | the Disconnect button (per the documentation, pulling the USB cable does not clear the flag) |
| 18 | `PARALYZE` | PARALYZE mode was triggered; the mode is “sticky” | reboot only |
| 19 | `GPS` | GPS Rescue is configured, and there is no fix or fewer satellites than `gps_rescue_min_sats` (8); only before the first arm | wait for satellites or `gps_rescue_allow_arming_without_fix = ON` |
| 20 | `RESCUE_SW` | the GPS RESCUE switch is on | turn it off |
| 21 | `DSHOT_TELEM` | `dshot_bidir = ON`, but some ESC is not sending eRPM | ESC firmware with bidir (Bluejay, BLHeli_32, AM32) or `dshot_bidir = OFF` |
| 22 | `REBOOT_REQD` | a setting that requires a reboot was changed | reboot |
| 23 | `DSHOT_BBANG` | bit-bang DShot did not start: a timer or pin conflict | `dshot_bitbang`, `resource`, `timer` (bf-cli) |
| 24 | `NO_ACC_CAL` | the accelerometer is not calibrated, and it is used by ANGLE, HORIZON, GPS RESCUE, ACRO TRAINER, an OSD element or the GPS-RESCUE failsafe | Calibrate Accelerometer on a level table |
| 25 | `MOTOR_PROTO` | `motor_pwm_protocol = DISABLED` or the protocol did not start | select DSHOT300/600 |
| 26 | `FLIP_SWITCH` | during turtle (crashflip) the mode switch was moved back with `crashflip_auto_rearm = OFF` (`fc/core.c`) | turn ARM off: the flag is cleared by a manual disarm |
| 27 | `ALT_HOLD_SW` | the ALTHOLD switch is on | turn the mode off before arming |
| 28 | `POS_HOLD_SW` | the POS HOLD switch is on | turn the mode off before arming |
| 29 | `ARM_SWITCH` (in 4.5 — `ARMSWITCH`, code 26) | the ARM switch is on while any other flag is set; after a GPS Rescue disarm | turn ARM off, clear the other flags first |

Old names from the forums: `RPMFILTER` = `DSHOT_TELEM`, `BADRX` = `NOT_DISARMED`; `RESC` is the enum name for `RESCUE_SW`. There is no `LAUNCH` flag: launch control does not block arming.

The difference from **4.5**: it has no `FLIP_SWITCH` (bit 25), `ALT_HOLD_SW` (26) or `POS_HOLD_SW` (27), and the last flag is called `ARMSWITCH` and sits on bit 25, not 28. In 2026.6 (2026.6.2 was released on 17.09.2026, outside the course's base version) bit 28 was taken by `AUTOPILOT_SW` (code 29: the AUTOPILOT mode switch is on; `fc/core.c` sets it only under `#if ENABLE_FLIGHT_PLAN && !defined(USE_WING)`, and in tag 2026.6.2 `USE_FLIGHT_PLAN` is defined only in the SITL target), `ARM_SWITCH` moved to bit 29 (code 30), and there are now 30 flags (`fc/runtime_config.h` and `runtime_config.c` of tag 2026.6.2). In the decoder below this is the `F2606` table under key 30. The bit numbers and beeper codes after the 24th depend on the version, so the decoder picks the table by the number of flags from `MSP_STATUS_EX`.

### Arming with a switch and with the sticks, PREARM, disarm
`fc/rc_controls.c`: stick arming is enabled only if there is **no** ARM range on the Modes tab **and** `enable_stick_arming = ON` (OFF by default). The arm gesture is throttle down + yaw right, the disarm gesture is throttle down + yaw left, both held for 500 ms (`ARM_DELAY_MS`). The arm gesture is ignored if the STICK COMMANDS DISABLE mode is on.

Arming with a switch: on every RC cycle while ARM is on, `tryArm()` is called. If any flag is set at that moment, `ARM_SWITCH` is set. It will not let the aircraft arm by itself when the cause disappears — the switch has to be lowered and raised again. To disarm with the switch, more than three RC frames in a row with ARM off are needed: an accidental single frame will not cause a disarm. During a real link loss a switch disarm will not work until valid data come back (`failsafeIsReceivingRxData()`).

**PREARM**: if a range is set for it, arming is possible only with PREARM on. After every arm it has to be turned off and on again (the `WAS_ARMED_WITH_PREARM` flag). For aircraft of 7″ and larger this is a second key. `prearm_allow_rearm` (from 2025.12, OFF by default) allows a re-arm without toggling PREARM; 4.5 has no such variable.

`auto_disarm_delay` = 5 s works only in one combination: `MOTOR_STOP` is enabled, airmode is off, arming is with the sticks. Then after 5 s of throttle at the bottom the aircraft disarms by itself. With switch arming in the same situation the FC only beeps (`BEEPER_ARMED`). `gyro_cal_on_first_arm = ON` moves the gyro calibration to the moment of the first arm. The beeper reports arming (`ARMING`; with GPS — `ARMING_GPS_FIX` or `ARMING_GPS_NO_FIX` depending on the number of satellites) and disarming (`DISARMING`). After RUNAWAY and CRASH the flag code sounds instead of the disarm signal. Individual events are turned off with the command `beeper -ARMING` and the like.

### Airmode: what the PID does right after arming
`feature AIRMODE` is enabled by default (`config/feature.c`), `pid_at_min_throttle = ON` (in both 4.5 and 2025.12). After arming at idle, P and D already work, while I is zeroed as long as the throttle is below `min_check` and airmode has not “latched”. Airmode latches when the throttle has exceeded `airmode_start_throttle_percent` = 25 % at least once. From that moment the PID has full authority even at zero throttle — right up to disarm (`processRx()`). Two consequences:
- A swapped motor shows up already at idle: the aircraft twitches, and on liftoff it flips at once.
- After a landing with airmode latched the aircraft bounces and may flip over: the PID tries to hold level by pushing the props into the ground. The fix is disarming right after touchdown, not tuning; `landing_disarm_threshold` does this automatically (from 2025.12; 0 = off, 4.5 does not have it).

### Runaway takeoff prevention
“Taz”, runaway — after arming or on liftoff the aircraft goes into a wild spin. The protection in `fc/core.c` works like this.

**Triggering** (`subTaskPidController`, every PID cycle): |pidSum| on any axis ≥ 600 **and** the gyro on roll or pitch > 15 °/s or on yaw > 50 °/s. The condition must hold without interruption for 75 ms. After that, `setArmingDisabled(RUNAWAY)` and a disarm. The scale: pidSum 1000 = 100 % of the motor range, and the mixer clips it to `pidsum_limit` = 500 (yaw 400). The pidSum itself is not clipped, so 600 means that the controller has hit the limit and is still losing. The gyro thresholds are needed for the bench: without props pidSum grows from the sticks alone while the aircraft stands still — no disarm. The check does not run on planes, during crash flip, in GPS Rescue, or while a connected app (Betaflight App) has temporarily disabled it (`runawayTakeoffTemporaryDisable`). With `MOTOR_STOP` without airmode it does not run at throttle below `min_check` either.

**Deactivation** (`processRx`): “normal flight” time is accumulated. These are the moments when throttle ≥ `runaway_takeoff_deactivate_throttle_percent` (20 %) and some roll, pitch or yaw stick is deflected ≥ 15 %, or throttle ≥ 40 % (2 × 20, but no more than 75). In addition, |pidSum| on all axes must be < 100. When `runaway_takeoff_deactivate_delay` = 500 ms has accumulated (250 ms at throttle ≥ 75 %), the protection is deactivated until reboot. The exception is arming in crash flip mode: it turns it on again. The throttle percentage is calculated as (rc − `min_check`) × 100 / (2000 − `min_check`), so 20 % is roughly 1240 µs. This means that in a hover without stick movement at 26 % throttle the protection will never be deactivated.

**Clearing the `RUNAWAY` flag**: lower ARM or make the stick disarm gesture. Then look for the cause: false triggers are rare, and if the protection triggered on liftoff, the motors, props or board orientation are almost always wrong. The documentation explicitly advises against disabling it (`runaway_takeoff_prevention = OFF`).

{{diagram:chart-bf-runaway-trip|With inverted roll feedback, pidSum passes 600 at 217 ms after liftoff, with the roll at only about 12°; after 75 ms of confirmation, the disarm comes at 292 ms with a 45° roll — before the flip.}}

### What motor errors look like on takeoff
| Error | What the aircraft does | RUNAWAY? | Check (bf-setup-scratch) |
|---|---|---|---|
| The left and right motors are swapped (M1↔M3, M2↔M4) or the board is rotated 180° without `align_board_yaw` | an instant flip over the side on liftoff | yes, ~0.3 s | the Motors tab, one motor at a time; Setup — the model follows the tilt |
| Two motors on one side are swapped (M1↔M2) | loses pitch and yaw control, tumbles forward or backward | yes | the same |
| One motor spins the wrong way or carries a prop of the other direction | that corner hardly pulls: a flip onto it plus yaw | usually yes | a strip of tape on the bell, `dshotprog <i> 7\|8 12` |
| `yaw_motors_reversed` does not match the props (props out/in) | a yaw pirouette on liftoff | yes (yaw > 50 °/s) | yaw with the stick at idle without props: which motors speed up |
| The accelerometer is not calibrated (ANGLE) | drift to the side, no flip | no | Calibrate Accelerometer |

In QUADX motor 1 is rear right (CW with props in), 2 is front right (CCW), 3 is rear left (CCW), 4 is front left (CW). The order is fixed by `motor_output_reordering` (the Reorder motors dialog), the direction — by DShot commands 7/8 + 12. Details are in bf-setup-scratch.

### Yaw spin recovery and crash recovery
**Yaw spin recovery** (`sensors/gyro.c`). If |gyro Z| > the threshold, recovery mode turns on. In it the yaw setpoint = 0, I on all axes is zeroed, P, D and FF on roll and pitch are zeroed, and the yaw pidSum limit is raised to 1000. Without airmode the throttle is set to 0.5 (`flight/mixer.c`). All the thrust goes into stopping the rotation. The mode turns off when the yaw rate has stayed below the threshold − 100 °/s for longer than 20 ms. The threshold depends on `yaw_spin_recovery`: `ON` — exactly `yaw_spin_threshold` (1950, range 500–1950); `AUTO` (the default) — max_yaw + max(max_yaw/4, 200), limited to 500…1950, where max_yaw is the maximum yaw rate of the current rate profile. For the default rates (Actual, `yaw_srate` = 67 → 670 °/s; the same in 4.5 and 2025.12) the threshold is 870 °/s. `OFF` — the feature is off.

**Crash recovery** (`flight/pid.c`) is `OFF` by default. A crash is detected when, simultaneously: the mixer is saturated, |ΔD| > `crash_dthreshold` (50 °/s²), |error| > `crash_gthreshold` (400 °/s), |setpoint| < `crash_setpoint_threshold` (350 °/s). The reaction depends on the mode. `ON` — the FC levels the aircraft and zeroes I. The exit is when roll and pitch are less than `crash_recovery_angle` (10°) and, in addition, either `crash_time` (500 ms) has passed, or the mixer has left saturation and the rates on all axes are less than `crash_recovery_rate` (100 °/s). `BEEP` — per the source (4.5 and 2025.12) the same leveling plus the beeper (see notes). `DISARM` — a disarm and the `CRASH` flag. In GPS Rescue the detector always runs. For freestyle and racing the feature is usually not enabled: it would take a hit on a gate for a crash.

### Parameter reference (2025.12; the values and ranges are the same as in 4.5 except where noted)
| Parameter | Default | Range | Meaning |
|---|---|---|---|
| `small_angle` | 25 | 0–180° | the maximum tilt for arming (180 only in RACE_PRO builds) |
| `pwr_on_arm_grace` | 5 | 0–30 s | arming block after power-up (`BOOTGRACE`) |
| `enable_stick_arming` | OFF | OFF/ON | stick arming, if there is no ARM range |
| `auto_disarm_delay` | 5 | 0–60 s | auto-disarm with the throttle down (MOTOR_STOP, no airmode, sticks) |
| `gyro_cal_on_first_arm` | OFF | OFF/ON | calibrate the gyro on the first arm |
| `gyro_calib_duration` | 125 | 50–3000 (×10 ms) | the duration of gyro calibration |
| `gyro_calib_noise_limit` | 48 | 0–200 | the standard deviation at which calibration restarts |
| `min_check` | 1050 | 750–2250 µs | the “throttle down” threshold for arming and stick commands |
| `airmode_start_throttle_percent` | 25 | 0–100 % | the throttle after which airmode latches |
| `pid_at_min_throttle` | ON | OFF/ON | P/D work at idle |
| `cpu_late_limit_permille` | 10 | 0–100 ‰ | the share of late tasks for `LOAD` |
| `runaway_takeoff_prevention` | ON | OFF/ON | runaway protection |
| `runaway_takeoff_deactivate_delay` | 500 | 100–1000 ms | how much “normal flight” to accumulate before deactivation |
| `runaway_takeoff_deactivate_throttle_percent` | 20 | 0–100 % | the minimum throttle for accumulation |
| `yaw_spin_recovery` | AUTO | OFF/ON/AUTO | recovery from a yaw spin |
| `yaw_spin_threshold` | 1950 | 500–1950 °/s | the threshold for ON mode |
| `crash_recovery` | OFF | OFF/ON/BEEP/DISARM | the reaction to a crash (PID profile) |
| `crash_dthreshold` / `crash_gthreshold` / `crash_setpoint_threshold` | 50 / 400 / 350 | 10–2000 / 100–2000 / 50–2000 | the crash detector thresholds |
| `crash_time` / `crash_delay` | 500 / 0 | 100–5000 / 0–500 ms | the duration and delay of leveling |
| `crash_recovery_angle` / `crash_recovery_rate` / `crash_limit_yaw` | 10 / 100 / 200 | 5–30° / 50–255 °/s / 0–1000 °/s | the exit criteria; the limit on the yaw error |
| `gps_rescue_allow_arming_without_fix` | OFF | OFF/ON | arming without a fix with GPS Rescue configured |
| `prearm_allow_rearm` | OFF | OFF/ON | re-arm without toggling PREARM (from 2025.12) |
| `landing_disarm_threshold` | 0 | 0–250 | disarm on impact at landing, 0 = off (from 2025.12, PID profile) |
| `crashflip_auto_rearm` | OFF | OFF/ON | arm after turtle without a manual disarm; with OFF, `FLIP_SWITCH` is set (from 2025.12) |
| `yaw_motors_reversed` | OFF | OFF/ON | props out |
| `motor_output_reordering` | 0,1,2,…,7 | array | the remapping of motor outputs |
| `dshot_bidir` | OFF | OFF/ON | bidir DShot; with ON, eRPM from every ESC is required |

### Place in the system

- **Receives:** valid RC frames and the position of the ARM and PREARM switches (`bf-modes-osd`); the failsafe state (`bf-failsafe`); eRPM from every ESC with `dshot_bidir = ON` (`bf-rpm-filter`); the fix and the number of satellites, if GPS Rescue is configured (`bf-gps-setup`).
- **Provides:** permission to arm — to the mixer and motors; the flag name — to the OSD and to `status` (`bf-cli`), the reason code — to the beeper (`bf-led-buzzer`); a RUNAWAY disarm — to the first takeoff (`bf-setup-scratch`).
- **If you get it wrong here:** you allowed arming without a fix (`gps_rescue_allow_arming_without_fix = ON`) → home is not recorded → on link loss GPS Rescue is unavailable; this is covered in `bf-failsafe` and `bf-gps-setup`. You did not disarm right after touchdown with airmode latched → the PID pushes the props into the ground, the aircraft bounces and flips over; the fix is a disarm, not PID tuning (`bf-pid`).

## practice
### Step 1. The flag mask decoder
You will see the mask as hex (a stripped-down `status`, a raw `MSP_STATUS_EX`, the log of your own script) or as a list of names. The script converts the mask into names using the table of the right version, computes the beeper code (from the lowest bit) and shows what the OSD will write. Five masks are taken from practice: the SITL config from bf-setup-scratch, the bench with the app connected, power-up with the throttle raised and ARM on, a disarm after runaway, an ESC without bidir. The sixth mask is the same “throttle + switch” situation in 2025.12, decoded first with the 4.5 table and then by the number of flags from the MSP response. The first five masks and the “5 fast” string in the output were captured for 4.5-maintenance; in 2025.12 the same situations give `ARM_SWITCH` on bit 28 (masks `0x10000080`, `0x10000020`, `0x10100000`) and 4 fast beeps in the beeper preamble.

```python
# Betaflight arming-disable flags: decode a mask from `status` / MSP_STATUS_EX (fc/runtime_config.c, msp/msp.c)
import struct
F45 = ("NOGYRO FAILSAFE RXLOSS NOT_DISARMED BOXFAILSAFE RUNAWAY CRASH THROTTLE ANGLE BOOTGRACE NOPREARM LOAD "
       "CALIB CLI CMS BST MSP PARALYZE GPS RESCUE_SW DSHOT_TELEM REBOOT_REQD DSHOT_BBANG NO_ACC_CAL "
       "MOTOR_PROTO ARMSWITCH").split()                                          # 4.5: 26 flags
F2512 = F45[:25] + ["FLIP_SWITCH", "ALT_HOLD_SW", "POS_HOLD_SW", "ARM_SWITCH"]  # 2025.12: 29 flags
F2606 = F2512[:28] + ["AUTOPILOT_SW", "ARM_SWITCH"]                     # 2026.6: 30 flags
TABLE = {26: F45, 29: F2512, 30: F2606}

def decode(mask, count=26):
    names = TABLE[count]
    nm = lambda b: names[b] if b < len(names) else f"BIT{b}?"
    bits = [b for b in range(32) if mask >> b & 1]
    code = bits[0] + 1                       # tryArm(): beeperWarningBeeps(ffs(flags)) -> lowest bit only
    osd = [nm(b) for b in bits if b != count - 1] or [nm(count - 1)]   # osd_warnings.c hides ARMSWITCH
    print(f"0x{mask:08X} [{count}] {' '.join(nm(b) for b in bits)}")
    print(f"   beeper: 5 fast + {code // 5} long + {code % 5} short = {code} ({nm(bits[0])}); OSD: {' '.join(osd)}")

def mask_of(words, names=F45):
    return sum(1 << names.index(w) for w in words.split())

for words in ("RXLOSS ANGLE BOOTGRACE CLI MOTOR_PROTO", "ANGLE MSP", "THROTTLE ARMSWITCH",
              "RUNAWAY ARMSWITCH", "DSHOT_TELEM ARMSWITCH"):
    decode(mask_of(words))

m = mask_of("THROTTLE ARM_SWITCH", F2512)        # the same situation on 2025.12
decode(m, 26)                                     # wrong table: bit 28 unknown
payload = struct.pack("<HHHIBHBBB", 125, 0, 0b100001, 0, 0, 120, 4, 0, 0) + struct.pack("<BIB", 29, m, 0)
nb = payload[15]; count, flags = struct.unpack_from("<BI", payload, 16 + nb)   # MSP_STATUS_EX layout
decode(flags, count)                              # flag count from the FC picks the right table
```

```text
0x01002304 [26] RXLOSS ANGLE BOOTGRACE CLI MOTOR_PROTO
   beeper: 5 fast + 0 long + 3 short = 3 (RXLOSS); OSD: RXLOSS ANGLE BOOTGRACE CLI MOTOR_PROTO
0x00010100 [26] ANGLE MSP
   beeper: 5 fast + 1 long + 4 short = 9 (ANGLE); OSD: ANGLE MSP
0x02000080 [26] THROTTLE ARMSWITCH
   beeper: 5 fast + 1 long + 3 short = 8 (THROTTLE); OSD: THROTTLE
0x02000020 [26] RUNAWAY ARMSWITCH
   beeper: 5 fast + 1 long + 1 short = 6 (RUNAWAY); OSD: RUNAWAY
0x02100000 [26] DSHOT_TELEM ARMSWITCH
   beeper: 5 fast + 4 long + 1 short = 21 (DSHOT_TELEM); OSD: DSHOT_TELEM
0x10000080 [26] THROTTLE BIT28?
   beeper: 5 fast + 1 long + 3 short = 8 (THROTTLE); OSD: THROTTLE BIT28?
0x10000080 [29] THROTTLE ARM_SWITCH
   beeper: 5 fast + 1 long + 3 short = 8 (THROTTLE); OSD: THROTTLE
```

What you see in the output:
- Of the five SITL flags the beeper will report only `RXLOSS` (code 3). Fix it, try to arm and listen for the next code.
- Codes 6 (`RUNAWAY`) and 21 (`DSHOT_TELEM`) match the documentation table for 4.2+. This is a check that the decoder and the firmware count the same way.
- The 2025.12 mask `0x10000080` gives an unknown bit 28 with the 4.5 table, and the 4.5 mask `0x02000080` reads as `THROTTLE FLIP_SWITCH` with the 2025.12 table — plausible and wrong. Hex cannot be decoded without the firmware version: the version number is taken from `version` or from the number of flags in `MSP_STATUS_EX`.

### Step 2. The runaway takeoff logic on synthetic data
The `Runaway` class is a line-by-line port of two pieces of `fc/core.c` with the same constants: the accumulation of “normal flight” in `processRx()` and the trigger check in `subTaskPidController()`. The aircraft model is deliberately simple: a single roll axis, P = 45 and I = 80 from the defaults (the same in 4.5 and 2025.12; D and FF are dropped), 12 °/s² of angular acceleration per unit of pidSum, a 20 ms motor lag, the limits `pidsum_limit` 500 and an I ceiling of 400. The script is written for 4.5-maintenance, where the ceiling is `iterm_limit` = 400; in 2025.12 there is no `iterm_limit` variable, but the ceiling is the same: `iterm_windup` 80 % × `pidsum_limit` 500 = 400. The runaway logic in `fc/core.c` has not changed in 2025.12 (only `flipOverAfterCrashActive` → `crashFlipModeActive` and `airmodeIsEnabled()` → `isAirmodeEnabled()` were renamed), so the output is valid for both versions. The scenarios: A — a normal takeoff, B — inverted feedback (the left and right motors are swapped), C and D — the bench without props, E — a hover without stick movement.

```python
# Betaflight 4.5 runaway takeoff prevention, reproduced from fc/core.c (processRx + subTaskPidController)
# and run on synthetic data. Constants are the firmware's #defines; settings are 4.5 defaults (flight/pid.c).
PIDSUM_TRIP, ACTIVATE_US = 600, 75_000          # RUNAWAY_TAKEOFF_PIDSUM_THRESHOLD, _ACTIVATE_DELAY
GYRO_RP, GYRO_YAW = 15, 50                      # RUNAWAY_TAKEOFF_GYRO_LIMIT_RP/_YAW, deg/s
STICK_PCT, PIDSUM_OK, HIGH_THR = 15, 100, 75    # _DEACTIVATE_STICK_PERCENT, _DEACTIVATE_PIDSUM_LIMIT, _HIGH_THROTTLE_PERCENT
DEACT_THR, DEACT_DELAY_MS = 20, 500             # runaway_takeoff_deactivate_throttle_percent, _deactivate_delay
MIN_CHECK = 1050

class Runaway:
    def __init__(s): s.trig = 0; s.deact = 0; s.acc = 0; s.off = False; s.off_at = None; s.disarmed_at = None
    def rx(s, t, thr_us, stick, pidsum):        # processRx(): learn "stable flight", then switch off
        if s.off: return
        pct = max(0, min(100, (thr_us - MIN_CHECK) * 100 // (2000 - MIN_CHECK)))
        mid = min(DEACT_THR * 2, HIGH_THR)       # constrain(low*2, low*2, 75)
        ok = ((pct >= DEACT_THR and stick >= STICK_PCT) or pct >= mid) and max(map(abs, pidsum)) < PIDSUM_OK
        if ok:
            if s.deact == 0: s.deact = t
            delay = DEACT_DELAY_MS // 2 if pct >= HIGH_THR else DEACT_DELAY_MS
            if t - s.deact + s.acc > delay * 1000: s.off = True; s.off_at = t
        else:
            if s.deact: s.acc += t - s.deact
            s.deact = 0
    def pid(s, t, pidsum, gyro):                 # subTaskPidController(): trip -> setArmingDisabled(RUNAWAY), disarm
        if s.off or s.disarmed_at is not None: return
        if max(map(abs, pidsum)) >= PIDSUM_TRIP and (abs(gyro[0]) > GYRO_RP or abs(gyro[1]) > GYRO_RP or abs(gyro[2]) > GYRO_YAW):
            if s.trig == 0: s.trig = t + ACTIVATE_US
            elif t > s.trig: s.disarmed_at = t
        else:
            s.trig = 0

# Roll axis of a 5" quad: P = 45, I = 80 (PTERM_SCALE 0.032029, ITERM_SCALE 0.244381, flight/pid.h), D/FF omitted.
# Plant: roll acceleration 12 deg/s^2 per pidSum unit (12 000 deg/s^2 at full authority), motor lag tau = 20 ms,
# I is clamped to iterm_limit = 400; mixer clamps the roll command to pidsum_limit = 500 (flight/mixer.c); pidSum itself is not clamped.
KP, KI = 0.032029 * 45, 0.244381 * 80
def fly(sign, thr_profile, stick_profile, setpoint_profile, props=True, hand=None, T=2.0, dt=125e-6):
    r = Runaway(); w = ang = cmd = I = 0.0; w = 5.0 if props else 0.0   # 5 deg/s disturbance at lift-off
    trace = []; t_us = 0; k = 0
    while t_us < T * 1e6:
        t = t_us / 1e6
        sp = setpoint_profile(t)
        err = sp - w
        I = max(-400, min(400, I + KI * err * dt))      # iterm_limit = 400 (flight/pid.c)
        P = KP * err; pidsum = P + I
        if r.disarmed_at is None and props:
            cmd += (max(-500, min(500, pidsum)) - cmd) * dt / 0.020
            w += sign * 12.0 * cmd * dt                 # sign = -1: left/right swapped -> positive feedback
            ang += w * dt
        elif not props:
            w = hand(t) if hand else 0.3                # props off: gyro sees noise or the hand
        if k % 8 == 0:                                  # PID loop 8 kHz, RX checks at ~1 kHz are enough here
            r.rx(t_us, thr_profile(t), stick_profile(t), (pidsum, 0, 0))
        r.pid(t_us, (pidsum, 0, 0), (w, 0, 0))
        if k % 80 == 0: trace.append((round(t, 3), round(pidsum), round(w), round(ang)))
        if r.disarmed_at is not None and t_us > r.disarmed_at + 50_000: break
        t_us += 125; k += 1
    return r, trace

ramp = lambda t: 1000 + min(t / 0.4, 1) * 330          # throttle 1000 -> 1330 us (29 %) in 0.4 s
roll_stick = lambda t: 25 if 0.6 < t < 1.6 else 0       # pilot moves roll 25 % between 0.6 and 1.6 s
sp_stick = lambda t: 100 if 0.6 < t < 1.6 else 0        # setpoint 100 deg/s while the stick is out

def report(name, r, tr, every=None):
    print(f"--- {name}")
    if r.disarmed_at is not None:
        row = min(tr, key=lambda x: abs(x[0] - r.disarmed_at / 1e6))
        print(f"  RUNAWAY: disarm at t = {r.disarmed_at/1e3:.0f} ms, pidSum {row[1]}, gyro {row[2]} deg/s, roll {row[3]} deg")
        trip_start = (r.trig - ACTIVATE_US) / 1e3
        print(f"  pidSum first >= 600 with gyro > 15 deg/s at {trip_start:.0f} ms, +75 ms confirmation")
    when = f" at t = {r.off_at/1e3:.0f} ms" if r.off else ""
    print(f"  prevention switched off for this battery: {r.off}{when}")
    print(f"  max |pidSum| {max(abs(x[1]) for x in tr)}, max |gyro| {max(abs(x[2]) for x in tr)} deg/s")
    if every:
        for row in tr[::every]: print("   t={:5.2f}s pidSum={:5d} gyro={:5d} roll={:4d}".format(*row))

r, tr = fly(+1, ramp, roll_stick, sp_stick)
report("A. correct motor order, normal take-off, roll stick 25 % from 0.6 s", r, tr)
r, tr = fly(-1, ramp, lambda t: 0, lambda t: 0, T=1.0)
report("B. roll feedback inverted (left/right motors swapped M1<->M3, M2<->M4)", r, tr, every=4)
r, tr = fly(+1, lambda t: 1300, lambda t: 60, lambda t: 300, props=False, T=2.0)
report("C. bench, props OFF, roll stick held 60 % (setpoint 300 deg/s), quad on the table", r, tr)
r, tr = fly(+1, lambda t: 1300, lambda t: 60, lambda t: 300, props=False, hand=lambda t: 40 if t > 1.0 else 0.3, T=2.0)
report("D. as C, but from 1.0 s the quad is tilted by hand at 40 deg/s", r, tr)
for lim in (20, 10):
    DEACT_THR = lim
    r, tr = fly(+1, lambda t: 1000 + min(t / 0.4, 1) * 300, lambda t: 0, lambda t: 0, T=3.0)
    print(f"--- E. hover at throttle 1300 us (26 %), sticks centred, deactivate_throttle_percent = {lim}")
    print(f"  prevention switched off: {r.off}")
```

```text
--- A. correct motor order, normal take-off, roll stick 25 % from 0.6 s
  prevention switched off for this battery: True at t = 1171 ms
  max |pidSum| 162, max |gyro| 147 deg/s
--- B. roll feedback inverted (left/right motors swapped M1<->M3, M2<->M4)
  RUNAWAY: disarm at t = 292 ms, pidSum -1361, gyro 667 deg/s, roll 45 deg
  pidSum first >= 600 with gyro > 15 deg/s at 217 ms, +75 ms confirmation
  prevention switched off for this battery: False
  max |pidSum| 1380, max |gyro| 680 deg/s
   t= 0.00s pidSum=   -7 gyro=    5 roll=   0
   t= 0.04s pidSum=  -16 gyro=    8 roll=   0
   t= 0.08s pidSum=  -36 gyro=   16 roll=   1
   t= 0.12s pidSum=  -82 gyro=   35 roll=   2
   t= 0.16s pidSum= -187 gyro=   79 roll=   4
   t= 0.20s pidSum= -425 gyro=  178 roll=   9
   t= 0.24s pidSum= -917 gyro=  374 roll=  19
   t= 0.28s pidSum=-1275 gyro=  608 roll=  39
   t= 0.32s pidSum=-1380 gyro=  680 roll=  47
--- C. bench, props OFF, roll stick held 60 % (setpoint 300 deg/s), quad on the table
  prevention switched off for this battery: False
  max |pidSum| 832, max |gyro| 0 deg/s
--- D. as C, but from 1.0 s the quad is tilted by hand at 40 deg/s
  RUNAWAY: disarm at t = 1075 ms, pidSum 775, gyro 40 deg/s, roll 0 deg
  pidSum first >= 600 with gyro > 15 deg/s at 1000 ms, +75 ms confirmation
  prevention switched off for this battery: False
  max |pidSum| 832, max |gyro| 40 deg/s
--- E. hover at throttle 1300 us (26 %), sticks centred, deactivate_throttle_percent = 20
  prevention switched off: False
--- E. hover at throttle 1300 us (26 %), sticks centred, deactivate_throttle_percent = 10
  prevention switched off: True
```

Analysis:
- **A.** Until 0.6 s the throttle is 29 % (less than 40 %) and the sticks are centered — no time accumulates. From 0.6 s the roll stick is at 25 %, but for the first ~70 ms |pidSum| reaches 162 (> 100) while the aircraft accelerates to the setpoint. That is why the protection is deactivated at 1171 ms, not at 1100.
- **B.** This is the “flip on takeoff”. An error of 5 °/s grows exponentially, doubling about every 35 ms. The 600 threshold is passed at 217 ms with a roll of about 12°, the disarm is at 292 ms with a 45° roll. The motors go out before the aircraft lands on its back and heads toward the pilot. This is the chart in the theory above. The I term shows saturation at 400: the kink in the curve at about 245 ms.
- **C and D.** Without props pidSum reaches 832, but the gyro is near zero, so the bench with stick wiggling is safe. Tilt the aircraft by hand at 40 °/s — and 75 ms later comes the disarm. This matches “Known issues” in the documentation.
- **E.** A steady hover at 26 % throttle without stick movement does not deactivate the protection. With `runaway_takeoff_deactivate_throttle_percent = 10` the “no sticks” threshold drops to 20 %, and the protection is deactivated. Do not lower this parameter for the sake of a light aircraft without need: the protection will be deactivated before you are sure that the aircraft flies correctly.

### Step 3. The yaw spin recovery threshold in AUTO mode
```python
# yaw_spin_recovery = AUTO threshold (sensors/gyro.c initYawSpinRecovery) from the max yaw rate
# of the rate profile (fc/rc.c: maxRcRate = applyRates(axis, 1.0, 1.0)); Actual rates: max = rates * 10 deg/s.
def auto_threshold(max_yaw):
    return max(500, min(1950, max_yaw + max(max_yaw // 4, 200)))   # YAW_SPIN_RECOVERY_THRESHOLD_MIN/MAX
for name, srate in (("4.5 default (yaw_srate 67)", 67), ("cinematic (40)", 40), ("freestyle (100)", 100), ("max (200)", 200)):
    m = srate * 10
    th = auto_threshold(m)
    print(f"{name:28s} max yaw {m:4d} deg/s -> trip {th:4d} deg/s, release below {th - 100} deg/s for 20 ms")
```

```text
4.5 default (yaw_srate 67)   max yaw  670 deg/s -> trip  870 deg/s, release below 770 deg/s for 20 ms
cinematic (40)               max yaw  400 deg/s -> trip  600 deg/s, release below 500 deg/s for 20 ms
freestyle (100)              max yaw 1000 deg/s -> trip 1250 deg/s, release below 1150 deg/s for 20 ms
max (200)                    max yaw 2000 deg/s -> trip 1950 deg/s, release below 1850 deg/s for 20 ms
```

AUTO keeps the threshold 25 %, but no less than 200 °/s, above your maximum yaw rate. With the default rates that is 870 °/s — close to the value of 850 that the documentation advised setting by hand with `ON`. The last line is a trap: yaw rates of 2000 °/s are above the 1950 ceiling. A long stick pirouette will trigger the recovery, and the aircraft will start to “stutter” in yaw — this is exactly how the documentation describes a threshold that is too low.

### Moving to real hardware
Props are off until item 4. The battery is connected through a smoke stopper or with a current limit on the first power-up after soldering.

**1. Clear the flags one at a time (bench, props off).** Power up the aircraft, connect Betaflight App and write the flags from the Setup tab into a table. Then perform the actions in order and look at `status` again after each one:

| Action | The flag should disappear |
|---|---|
| Wait 5 s without touching the aircraft | `BOOTGRACE`, `CALIB` |
| Turn on the radio, wait for the link | `RXLOSS` (after 0.5 s) |
| Throttle to zero; check on Receiver that it is < 1050 | `THROTTLE` |
| Place it on a level table; accelerometer calibration | `ANGLE`, `NO_ACC_CAL` |
| Select DShot, save, reboot | `MOTOR_PROTO`, `REBOOT_REQD` |
| Exit the CLI (`exit`) | `CLI` |
| Disconnect in Betaflight App | `MSP` |
| Turn the FAILSAFE and GPS RESCUE switches off, turn PREARM (if set) on | `BOXFAILSAFE`, `RESCUE_SW`, `NOPREARM` |

Take the last `status` through an MSP bridge without the app or look at the OSD: the app itself sets `MSP`. Then deliberately cause three flags and check the beeper. ARM is on with the throttle raised → `THROTTLE` (1 long + 3 short). The aircraft is tilted 40° → `ANGLE` (1 + 4). The ARM switch is on before the link appears → first `RXLOSS` (3 short), and 0.5 s later `NOT_DISARMED` (4 short): the beeper repeats the code when the main reason changes.

**2. Motor order and direction.** The Motors tab, “I understand the risks”. Raise each slider in turn to ~1100. Motor 1 should spin — rear right CW, 2 — front right CCW, 3 — rear left CCW, 4 — front left CW (props in). The direction is visible from the strip of tape on the bell. The fix is Reorder motors and Motor direction (bf-setup-scratch, step 7). Then a check without the app, with the aircraft armed on the bench. Tilt it by hand 10–15° to the right: the right motors should speed up and the left ones slow down. If it is the other way around — this is the “flip on takeoff”, do not go any further. Tilt it forward: the front ones should speed up. Yaw with the stick to the right: the motors that rotate counterclockwise should speed up (2 and 3 with props in). Hold the tilt for no longer than 1–2 s: a long tilt by hand is scenario D, and it will end with a `RUNAWAY` disarm.

**3. The first arm without props.** Betaflight App is disconnected (otherwise `MSP`), ARM is on a switch. Expected: the `ARMING` signal, the motors idling evenly. Check the switch disarm, then a repeat arm. If GPS Rescue is configured — check that `GPS` stays set without satellites. If PREARM is set — check that a repeat arm without toggling PREARM is blocked (`NOPREARM`).

**4. The first low hover — the props go on here.** Check the props against the props in diagram and their tightness. The site is grass, people no closer than 10 m, you 5 m behind the aircraft. Arm in ANGLE, smoothly throttle up to liftoff. A hover at 0.3–0.5 m, 10–20 s, landing, disarm. For a large or heavy aircraft (7″+), a tether instead of a free hover: 1.5–2 m of cord from the center of the frame underneath to a weight of no less than 3 times the aircraft's weight. The cord must not reach the props. **Immediate disarm** on any of these signs:
- on liftoff the aircraft rolls more than 20° or spins in yaw;
- the beeper gives RUNAWAY (1 long + 1 short);
- the liftoff throttle is above 60 % or below 12 %;
- oscillations can be heard;
- the aircraft “walks” on the ground before liftoff.

After the hover, land and disarm right after touchdown (airmode is already latched, see the theory). Write down the liftoff throttle and the flags after landing.

**Self-check of the hardware part:** the table from item 1 is filled in, every flag was cleared by its own action, three beeper codes are written down and match the decoder. The order, direction and reaction to a tilt by hand correspond to QUADX. Arming and disarming with the switch are checked without props. The first hover of 10–20 s went by without the abort criteria being met, and the liftoff throttle is written down.

Self-check: the lab is complete when:
- **The calculation path (Python)**: the decoder from step 1 has been run on the five masks and on the 2025.12 mask with the table chosen by the number of flags. For your own mask from `status` (a real one or from the bf-setup-scratch SITL) the flags, the beeper code and the OSD line are written out. The script of step 2 has been run, and you got the disarm in scenario B (217 → 292 ms) and the deactivation of the protection in scenario A (at 1171 ms). Your own scenario is added — for example, throttle ≥ 75 % (a 250 ms delay); you have explained its result to yourself from the trigger conditions in the theory, the same way as in the analysis of scenarios A–E. The AUTO yaw spin threshold is calculated for your rate profile and lies within 500…1950 °/s; the formula check — 670 °/s gives 870.
- **Hardware**: the self-check of the hardware part above is done.

**Reference for self-check.** The decoder is correct if the five masks of step 1 give the same lines as in the module: `0x02000020` — code 6 (`RUNAWAY`), `0x02100000` — code 21 (`DSHOT_TELEM`), and of the five flags of `0x01002304` the beeper reports only `RXLOSS` (code 3). `BIT28?` or a plausible `THROTTLE FLIP_SWITCH` appeared in the decoding — the mask was read with the table of the wrong version: pick the table by the number of flags (26 or 29). In scenario A the protection was deactivated at 1100 ms instead of 1171 — the model accumulates time even when |pidSum| > 100; in scenario C you got a disarm — the gyro condition (> 15 °/s) was left out.

## diagnostics
- **Symptom:** the aircraft does not arm, the `MSP` flag in Betaflight App
  - Possible cause: the app itself blocks arming while it is connected.
  - What to do: Disconnect; per the documentation, pulling the USB cable does not clear the flag. Check arming without the app.
- **Symptom:** it arms on the bench but not in the field (or the other way around)
  - Possible cause: `ANGLE` on uneven ground (> 25°), `MSP`/`CLI` on the bench, `GPS` without satellites in the field.
  - What to do: read the flag in the OSD with ARM on; do not raise `small_angle` instead of finding a level spot.
- **Symptom:** there are no flags in `status`, but the switch does not arm
  - Possible cause: `status` was taken with ARM off; the ARM range on the Modes tab does not match the real channel value; ARM is on and `ARM_SWITCH` (in 4.5 — `ARMSWITCH`) is still set after an earlier reason.
  - What to do: turn ARM on and look at Setup/OSD; check on Receiver that the channel value is no closer than 50 µs to the range boundary; lower the switch and raise it again.
- **Symptom:** when the throttle is raised the aircraft flips instantly and disarms, beeping 1 long + 1 short
  - Possible cause: `RUNAWAY` — the motors, the rotation direction, the props or the board orientation are mixed up.
  - What to do: take the props off, item 2 of the practice, the Setup tab (does the model follow the tilt?); do not turn `runaway_takeoff_prevention` off.
  - Consequences: without the protection — a flip within 0.3 s, broken props, a risk to the pilot.
- **Symptom:** a RUNAWAY disarm on the bench without props
  - Possible cause: the aircraft was moved by hand with the motors armed, or a long yaw with the stick (the 50 °/s threshold).
  - What to do: do not hold an armed aircraft in your hands; for long bench tests — the Motors tab.
  - What you see in the log: `debug_mode = RUNAWAY_TAKEOFF`, debug[1] = 1 for 75 ms before the disarm.
- **Symptom:** `CALIB` does not go away
  - Possible cause: the aircraft is rocking or vibrating (a fan, the table), the gyro standard deviation > `gyro_calib_noise_limit`.
  - What to do: place it motionless; do not raise the limit until you are sure the gyro is healthy.
- **Symptom:** `DSHOT_TELEM` after enabling `dshot_bidir`
  - Possible cause: an ESC without bidir firmware (BLHeli_S without Bluejay) or one ESC is not responding.
  - What to do: `dshot_telemetry_info`, flash Bluejay/AM32 or `dshot_bidir = OFF` (bf-rpm-filter).
- **Symptom:** after clipping a gate the aircraft spins in yaw and climbs
  - Possible cause: a yaw spin; with `yaw_spin_recovery = OFF` or a threshold of 1950 the recovery kicks in late.
  - What to do: `AUTO` or `ON` with a threshold 100–200 °/s above max yaw; throttle to zero, sticks to center, and with a prolonged spin of more than 0.5 s — disarm.
- **Symptom:** the aircraft bounces or flips over after touchdown on landing
  - Possible cause: airmode is latched, and the PID holds level with the props in the ground.
  - What to do: disarm right after touchdown; `landing_disarm_threshold` (from 2025.12) does this on impact.

## checklist
- I know the four places to read the flags, and that the OSD shows them only with ARM on
- From a beeper code (long × 5 + short) I can find the flag in the table for my version
- The mask decoder has been run; I remember that `ARM_SWITCH` is bit 28 (in 4.5 `ARMSWITCH` is bit 25)
- `small_angle`, `pwr_on_arm_grace`, `min_check` — the default values are known and have not been changed without a reason
- The motor order and direction and the reaction to a tilt by hand are checked without props
- `runaway_takeoff_prevention = ON`, `yaw_spin_recovery = AUTO` (or ON with a threshold above max yaw)
- The first hover is low or on a tether, with criteria for an immediate disarm
- Disarm right after touchdown with airmode

## references
- Betaflight runtime_config.c / runtime_config.h (flag names and bits), 4.5-maintenance | https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/fc/runtime_config.c | primary | A
- Betaflight core.c (updateArmingStatus, tryArm, runaway takeoff, auto-disarm), 4.5-maintenance | https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/fc/core.c | primary | A
- Betaflight rc_controls.c (stick and switch arming, disarm) | https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/fc/rc_controls.c | primary | A
- Betaflight gyro.c (yaw spin recovery, gyro calibration) | https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/sensors/gyro.c | primary | A
- Betaflight pid.c (crash recovery, the runaway and crash_* defaults) | https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/flight/pid.c | primary | A
- Betaflight beeper.c (warning codes, arming signals) | https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/io/beeper.c | primary | A
- Betaflight runtime_config.h, tag 2025.12.5 (29 flags, ARM_SWITCH = bit 28) | https://github.com/betaflight/betaflight/blob/2025.12.5/src/main/fc/runtime_config.h | primary | A
- Betaflight core.c, tag 2025.12.5 (FLIP_SWITCH, ALT_HOLD_SW, POS_HOLD_SW) | https://github.com/betaflight/betaflight/blob/2025.12.5/src/main/fc/core.c | primary | A
- Betaflight docs: Arming Sequence & Safety | https://betaflight.com/docs/wiki/guides/current/Arming-Sequence-And-Safety | primary | A
- Betaflight docs: Runaway Takeoff Prevention | https://betaflight.com/docs/wiki/guides/current/Runaway-Takeoff-Prevention | primary | A
- Betaflight docs: Yaw Spin Recovery and Gyro Overflow Detect | https://betaflight.com/docs/wiki/guides/current/Yaw-Spin-Recovery-and-Gyro-Overflow-Detect | primary | A
- Oscar Liang: Why your Betaflight drone won't arm | https://oscarliang.com/quad-arming-issue-fix | secondary | B

## notes
Where the documentation disagrees with the source (4.5 and 2025.12), the module follows the source:
- The Crash Recovery page says that `crash_limit_yaw` “cancels” the recovery when the yaw rate is exceeded. In `pid.c` it only limits the yaw error during the recovery.
- The same page calls `BEEP` a “beeper only” mode. In `handleCrashRecovery()` (4.5 and 2025.12) the leveling is performed with `BEEP` too.
- The Yaw Spin Recovery page describes the ON/OFF modes and the 1950 threshold as the default. The default is `AUTO` (in both 4.5 and 2025.12), and the threshold is calculated from the rates.
- The Runaway Takeoff Prevention page says that a connected configurator temporarily disables the protection. In the firmware this is the second byte of the `MSP_ARMING_DISABLE` command, when the app allows arming. Which actions in the interface make it send it has not been verified here.

The aircraft model in step 2 is for teaching: the times on a real aircraft will be different, while the threshold logic is line by line from the firmware.
