---
id: px4-safety-return
source: content/px4/px4-safety-return.md
source_hash: 8b0e2ad643de
title: "PX4: arming, failsafe, Return and geofence, the full matrix"
level: L2
readingTime: 60 min
firmware: PX4 1.18 (checked against v1.18.0)
status: published
tags:
  - PX4
  - failsafe
  - arming
  - Return
  - geofence
  - safety
related:
  - px4-intro
  - px4-setup-scratch
  - nav-resilience
  - ap-safety-fs
  - px4-architecture
  - f-safety
next:
  - px4-control
---

## summary
The whole Safety page in QGroundControl and what stands behind it in the PX4 1.18.0 code: why the vehicle will not arm, how disarm differs from kill and from flight termination, how commander picks one action out of a dozen failure flags, how many seconds pass before it, and whether you can take over with the sticks. Separately, Return mode: where it flies, at what altitude (the cone formula from `rtl.cpp`), and how it lands. After the module, given a parameter list and a timeline of events, you can say what the vehicle will do at every second, and find configuration errors before the flight. The practice needs no simulator: working through a ready-made set of parameters and events with a reference, plus a bank of numeric problems.

## theory
### What is new here and what is a reference
px4-intro names the Safety page parameters and gives the 1.15 → 1.17 and 1.17 → 1.18 migration tables. px4-setup-scratch tests two chains in SITL, RC loss and low battery (step 6). What a position loss means from the estimator's point of view is in nav-resilience. Here are all the conditions at once, the logic of choosing between them, and Return in full. Values and ranges are checked against the v1.18.0 source (`commander_params.yaml`, `failsafe.cpp`, `rtl.cpp`); where a name or default differs in 1.15–1.17, that is stated. Parameters removed in 1.18 are named once, in parentheses, as "before 1.18".

QGC screen names depend on the version: in QGC 5.0 this is a single **Safety** page (low battery, RC loss, data link loss, geofence, Return, Land, kill); newer builds split it into Failsafes and Return & Land. The parameters are the same.

### Three ways to stop the motors
| Action | What happens to the outputs | Reversible | What triggers it |
|---|---|---|---|
| **Disarm** | disarmed values (`PWM_MAIN_DISn`) | yes, by arming again | the `RC_MAP_ARM_SW` switch, a stick gesture, auto-disarm after landing; in the air it is rejected ("Disarming denied: not landed"), except for a command from the transmitter in manual modes with direct throttle (Stabilized, Acro): always in 1.18 (before 1.18 with `COM_DISARM_MAN` = 1) |
| **Kill** | disarmed values at once, the vehicle stays armed | yes: flip the switch back within 5 s (hard-coded in `Commander.cpp` in 1.18; before 1.18 `COM_KILL_DISARM`, 0…30) and the motors run again; later, disarm and arm again | `RC_MAP_KILL_SW` (threshold `RC_KILLSWITCH_TH` 0.75); the `MAN_KILL_GEST_T` gesture (−1 disabled): both sticks down and outward |
| **Flight termination** | failsafe values (`PWM_MAIN_FAILn`), the `DO_PARACHUTE` command to the parachute | no, only a reboot | the Terminate action of any failsafe; the failure detector only with `CBRK_FLIGHTTERM` = 0 |

Kill in the air is a crash. It is for the ground and for the first seconds of takeoff. Termination is for vehicles with a parachute: the outputs go to their failsafe values to open the parachute and stop the motors (what each function outputs with `FAILn` = −1 is in `px4-outputs-servos`).

### Arming: the sequence
1. **Safety button.** `CBRK_IO_SAFETY` = 22027 by default (in 1.15 and 1.16 too): no button is required, even if there is one on the GPS module. Set 0 and arming is rejected with "Press safety button first" until you press it. `COM_FORCE_SAFETY` = 1 restores the lock on every disarm.
2. **Prearm.** `COM_PREARM_MODE`: 0 disabled (default), 1 after the safety button, 2 always, 5 s after boot. In prearm the servos and other "non-thrust" outputs work; the motors stay stopped (output states are in `px4-outputs-servos`).
3. **The arm command.** Gesture: left stick down-right (throttle < −0.8, yaw > 0.9), right stick centered, held for 1 s (hard-coded in `ManualControl.cpp` in 1.18; before 1.18 `COM_RC_ARM_HYST`, 100…1500 ms); `MAN_ARM_GESTURE` = 1. If `RC_MAP_ARM_SW` is assigned, the gesture is disabled. `COM_ARM_SWISBTN` = 1 turns the switch into a button with the same hold. The switch threshold is `RC_ARMSWITCH_TH` 0.75.
4. **No takeoff, disarm.** `COM_SPOOLUP_TIME` + `COM_DISARM_PRFLT` = 1 + 10 = 11 s after arming without liftoff. A plane has `COM_DISARM_PRFLT` = −1 (`rc.fw_defaults`) so as not to interfere with a hand or catapult launch.
5. **Arming is not allowed in Return, Land, Precision Land, Orbit, Follow**: change the mode first.

### Arming: the checks table ("why won't it arm")
QGC shows the reasons (`Preflight Fail: …` messages); `commander check` reruns the checks and prints the result of the previous evaluation, OK or FAILED, and the fresh reasons arrive a second later as messages in QGC and in `dmesg`. Below are the checks that have a parameter.

| Check | Parameter | Default | Range / values | Note |
|---|---|---|---|---|
| Arming allowed at all | `COM_ARMABLE` | 1 | 0 / 1 | 0 locks it during maintenance |
| Accelerometer inconsistency | `COM_ARM_IMU_ACC` | 0.7 m/s² | 0.1…1.0 | recalibrate on a warmed-up board |
| Gyro inconsistency | `COM_ARM_IMU_GYR` | 0.25 rad/s | 0.02…0.3 | the same |
| Compass inconsistency | `COM_ARM_MAG_ANG` | 60° | 3…180, −1 off | external compass orientation |
| Strong magnetic interference | `COM_ARM_MAG_STR` | 2 | 0 off, 1 deny, 2 warning | |
| GPS checks (`EKF2_GPS_CHECK`) | `COM_ARM_WO_GPS` | 1 | 0 deny, 1 warning, 2 off | in 1.15: 0 GPS required, 1 not required |
| Battery charge | `COM_ARM_BAT_MIN` | −1 | −1…0.9 | −1 means `BAT_CRIT_THR` is the threshold; in 1.15 the default is 0 |
| 5 V power, module count | `COM_POWER_COUNT`, `CBRK_SUPPLY_CHK` | 1; 0 | 0…4; key 894281 | the key disables all power checks |
| USB connected | `CBRK_USB_CHK` | 197848 | 0 denies arming with USB | the check is off by default |
| CPU / RAM load | `COM_CPU_MAX`, `COM_RAM_MAX` | 95 % | −1…100 | in SITL `COM_CPU_MAX` = −1; `COM_RAM_MAX` appeared in 1.16 |
| SD card | none (before 1.18 `COM_ARM_SDCARD`) | — | — | in 1.18 always a warning only; on boards without SD the check is removed at build time |
| Hardfault files on the card | `COM_ARM_HFLT_CHK` | 1 | 0 / 1 | |
| ESC telemetry | `COM_ARM_CHK_ESCS` | 0 | 0 / 1 | only for ESCs with telemetry; since 1.18 with 1, an ESC going offline or an ESC fault (including overheating and overspeed) in flight counts as a motor failure → `COM_ACT_FAIL_ACT` |
| Valid mission | `COM_ARM_MIS_REQ` | 0 | 0 / 1 | |
| Remote ID | `COM_ARM_ODID` | 0 | 0 off, 1 warning, 2 deny arming, 3 Return, 4 Land, 5 Terminate | 3–5 (since 1.18) also deny arming and trigger the action on Remote ID loss in flight |
| MAVLink parachute | `COM_PARACHUTE` | 0 | 0 off, 1 warning, 2 deny arming, 3 Return, 4 Land | in 1.17 it was 0 / 1, and 1 denied arming; since 1.18, 2 and above deny it, and 1 only warns (the value is not changed on upgrade) |
| External arming authorization | `COM_ARM_AUTH_REQ` | 0 | 0 / 1 | |
| VTOL in plane mode | `CBRK_VTOLARMING` | 0 | key 159753 | |

Without a parameter: no manual control in a mode that needs it (with `COM_RC_IN_MODE` ≠ 4), no GCS link with `NAV_DLL_ACT` > 0, the mode needs a position or home that is not there, the geofence is already violated, `GF_ACTION` = 3 without home. Removed in 1.16: `COM_ARM_EKF_HGT/POS/VEL/YAW`.

`CBRK_*` are circuit breakers: a check is disabled only by writing the exact key number. Two of them are on from the factory: `CBRK_IO_SAFETY` (no button needed) and `CBRK_FLIGHTTERM` (termination by the failure detector is forbidden).

### How PX4 chooses the action
Each check sets a bit in the `failsafe_flags` topic. Then `failsafe/framework.cpp` takes over:

{{diagram:px4-failsafe-flow|Of all active conditions the most severe action wins; RTL and Land first give Hold for COM_FAIL_ACT_T, while Hold, Disarm and Terminate run at once.}}

1. **Each condition has its own action** (an `*_ACT` parameter). The severity order is hard-coded: None < Warn < Position < Altitude < Stabilized < Hold < RTL < Land < Descend < Disarm < Terminate.
2. **The most severe wins.** A geofence with a Hold action will not stop a Return triggered by RC loss: Hold is lighter than RTL. The emergency battery level (Land) overrides Return.
3. **The `COM_FAIL_ACT_T` delay** = 5 s (0…25). Before RTL, Land and Descend the vehicle hovers in Hold so the pilot can react. During the delay you take over only by changing the mode; the sticks have no effect. Hold, Disarm and Terminate run without delay. If the vehicle is already in a failsafe more severe than Hold, the next action also runs at once: during a Return from RC loss, the move to Land on battery is instant.
4. **The delay budget gets used up.** While an action is deferred, the budget is spent second by second; the rest of the time it recovers four times more slowly, including the `COM_RC_LOSS_T` seconds between the last RC frame and the loss flag. The budget is fixed at the moment the flag goes up: if x seconds passed from the end of a fully used delay to the new flag, min(`COM_FAIL_ACT_T`, x/4) is available. That way a flickering condition does not defer the action forever. Any parameter change resets the budget to the full `COM_FAIL_ACT_T`.
5. **If the action's mode is unavailable**, PX4 goes down the chain: Hold → RTL → Land → Descend → Terminate. Descend is a descent without position hold; it needs only angular rates and attitude.
6. **User takeover.** A mode change or a **fast stick movement** switches to Position: the smoothed stick speed on any axis (throttle included) exceeds `MAN_OVERRIDE_SPD` = 1 unit of the −1…+1 scale per second (range −1…10; at 1, half the full travel per second), and the stick moves the same way for three frames in a row (`ManualControl.cpp`, v1.18.0). A slow deflection by any amount does not take over: if you move the stick smoothly during a failsafe, the vehicle continues Return or Land, and the stick only shifts the setpoint once control comes back. To take control, move the stick sharply or switch the mode with a switch; the latter is more reliable. Sticks work only on a multirotor (and a VTOL in hover mode), in all automatic modes and in Offboard; a negative `MAN_OVERRIDE_SPD` disables stick takeover. Before 1.18 the same was set by `COM_RC_OVERRIDE` (bit 0 automatic modes, bit 1 Offboard, off by default) and `COM_RC_STICK_OV` (a threshold of 0.01·30 = 0.3 /s): on upgrade only "disabled" migrates (`COM_RC_OVERRIDE` = 0 → −1), and the rest has to be set again. With `COM_FAIL_ACT_T` = 0 stick takeover in a failsafe does not work at all, leaving only a mode change. Terminate and Disarm have no takeover.
7. **Clearing.** The RC loss, data link and geofence actions stay active until the condition is gone **and** the pilot changes the mode (or disarms). The link came back, but Return continues until you switch the mode. Terminate is not cleared until a reboot.

### The failsafe matrix
Defaults are the parameter's; the "MC / FW / VTOL" column shows what the airframe changes (`rc.mc_defaults`, `rc.fw_defaults`, `rc.vtol_defaults`).

| Condition | Detector | Action | Default | MC / FW / VTOL | Action values |
|---|---|---|---|---|---|
| Manual control loss | `COM_RC_LOSS_T` 0.5 s (0…35) | `NAV_RCL_ACT` | 2 Return | the same | 1 Hold, 2 Return, 3 Land, 5 Terminate, 6 Disarm, 7 Hold without failsafe (since 1.18) |
| GCS link loss | `COM_DL_LOSS_T` 10 s (5…300) | `NAV_DLL_ACT` | **0, disabled** | the same; SITL `gz_x500`: 2 | 0, 1 Hold, 2 Return, 3 Land, 5 Terminate, 6 Disarm |
| Battery low | `BAT_LOW_THR` 0.15 (0.12…0.5) | — | warning | the same | — |
| Battery critical | `BAT_CRIT_THR` 0.07 (0.05…0.5) | `COM_LOW_BAT_ACT` | 0 Warning | SITL: 3 | 0 Warning, 2 Land, 3 and 5 Return |
| Battery emergency | `BAT_EMERGEN_THR` 0.05 (0.03…0.5) | `COM_LOW_BAT_ACT` | 0 Warning | SITL: 3 | Land with 2, 3 and 5 |
| Remaining time < Return time (distance-aware return) | estimate with `RTL_TIME_FACTOR` 1.1, `RTL_TIME_MARGIN` 100 s; needs `BAT1_CAPACITY` (−1 by default, no estimate) or a "smart" battery | `COM_LOW_BAT_ACT` (since 1.18; in 1.17 `COM_FLTT_LOW_ACT`) | 0, warning only | SITL: 3 | 3 Return; 0, 2, 5 warning only |
| Flight time limit | `COM_FLT_TIME_MAX` −1 s (off) | — | always Return | the same | warning from 90 % of the limit |
| Wind | `COM_WIND_MAX` −1 m/s; `COM_WIND_WARN` −1 | `COM_WIND_MAX_ACT` | 0 None | the same | 0 None, 1 Warning, 2 Hold, 3 Return, 4 Terminate, 5 Land |
| Low position accuracy (Mission, Hold) | `COM_POS_LOW_EPH` −1 m | `COM_POS_LOW_ACT` (since 1.16) | 3 Return | threshold: MC −1 / FW 50 / VTOL 50 | 0 None, 1 Warning, 2 Hold, 3 Return, 4 Terminate, 5 Land |
| Position loss | `COM_POS_FS_EPH` 5 m, `COM_VEL_FS_EVH` 1 m/s | no parameter | the mode chain | `COM_VEL_FS_EVH`: FW 3 | see below |
| Offboard loss | `COM_OF_LOSS_T` 1 s (0…60) | `COM_OBL_RC_ACT` | 0 Position | the same | 0 Position, 1 Altitude, 2 Stabilized, 3 Return, 4 Land, 5 Hold, 6 Terminate, 7 Disarm |
| Geofence | `GF_MAX_HOR_DIST`, `GF_MAX_VER_DIST`, polygons | `GF_ACTION` | 2 Hold | the same | 0 None, 1 Warning, 2 Hold, 3 Return, 4 Terminate, 5 Land |
| Mission failure | navigator check | — | always Return | the same | — |
| Traffic (ADS-B) | `NAV_TRAFF_A_HOR` 500 m, `NAV_TRAFF_A_VER` 500 m, `NAV_TRAFF_COLL_T` 60 s | `NAV_TRAFF_AVOID` | 1 Warn | the same | 0 off, 1 Warn, 2 Return, 3 Land, 4 Hold |
| Roll/pitch beyond limit | `FD_FAIL_R`, `FD_FAIL_P` 60° | `CBRK_FLIGHTTERM` | 121212, warning only | the same | 0 Terminate |
| Motor failure | `FD_ACT_EN` **0** (before 1.18, 1); since 1.18 also `COM_ARM_CHK_ESCS` = 1 | `COM_ACT_FAIL_ACT` | 0 Warning | the same | 1 Hold, 2 Land, 3 Return, 4 Terminate |
| Propeller imbalance | `FD_IMB_PROP_THR` 30 (0 off) | none | always Warning | the same | since 1.18 warning only (before 1.18 `COM_IMB_PROP_ACT`: −1 off, 0 Warning, 1 Return, 2 Land) |
| GNSS receiver loss (since 1.18) | fewer receivers with a 3D fix than `SYS_HAS_NUM_GNSS` (0 means no check); with 2, also a disagreement between the two positions | `COM_GNSSLOSS_ACT` | 0 Warning | the same | 0 Warning, 1 Return, 2 Land, 3 Terminate; above 0 also denies arming |
| Remote ID loss in flight (since 1.18) | no Open Drone ID heartbeat for 3 s | `COM_ARM_ODID` | 0 off | the same | 3 Return, 4 Land, 5 Terminate; 0–2 do nothing in flight |
| Parachute not OK (since 1.18) | no parachute heartbeat for 3 s, or it reports an error | `COM_PARACHUTE` | 0 off | the same | 1 and 2 warning (2 also denies arming), 3 Return, 4 Land |
| Altitude loss (since 1.18) | below the setpoint by more than `FD_ALT_LOSS` (0 off) for longer than `FD_ALT_LOSS_T` 1 s, in altitude-holding modes | `CBRK_FLIGHTTERM` | 121212, warning only | multirotor and VTOL in hover only | 0 Terminate (and the parachute) |
| Quad-chute (VTOL) | the VTOL controller | `COM_QC_ACT` | 0 Return | VTOL only and only in Mission, Hold, Takeoff, VTOL Takeoff; in manual modes the vehicle simply stays a multirotor | −1 Warning, 0 Return, 1 Land, 2 Hold |

Details that change the behavior:
- **RC.** `COM_RCL_EXCEPT` (0…31) is the modes where RC loss is ignored: bit 0 Mission, 1 all automatic modes (Hold, Takeoff, VTOL Takeoff, Land, Return, Descend, Follow Target, Precision Land, Orbit, the plane's Guided Course; `failsafe.cpp:508–518`; in 1.17 bit 1 meant only Hold and Takeoff), 2 Offboard, 3 External (1.17), 4 Altitude Cruise (1.17). On upgrading to 1.18 the saved value does not change: if bit 1 was set, RC loss is now ignored in Return and Land too. If the RC was already lost at the moment of arming, the condition stays silent until the link appears. With `COM_RC_IN_MODE` = 4 the check is off.
- **GCS.** `COM_DLL_EXCEPT` (since 1.16; 0…31 in 1.18): bit 0 Mission, 1 all automatic modes (in 1.17, Hold), 2 Offboard, 3 External, 4 Altitude Cruise. In Land and Precision Land a link loss is always ignored. A safeguard in the code: if RC loss is excepted in Mission, `NAV_DLL_ACT` = 0, the GCS link is lost and the mission has finished, the result is Return.
- **Battery.** In flight the level only grows in severity: a voltage sag under load down to critical will not go back. If you armed already at the low level (allowed through `COM_ARM_BAT_MIN`), the failsafe triggers only at the next level. `COM_LOW_BAT_ACT` = 1 (Return without Land) remains in the code as deprecated and is not in the value list. Since 1.18, value 3 also enables the return on remaining flight time (distance-aware return, the matrix row above), and 5 is the same as 3 but without it; `COM_FLTT_LOW_ACT` was removed and does not migrate: if you do not want the time-based return, set 5. With two batteries in 1.18 a battery that disconnects in flight no longer masks the other battery's emergency level with critical: with 3 the vehicle lands at emergency instead of continuing Return. Critical level: Hold 5 s → Return; emergency while Return is already running: Land at once. How the battery levels look on the LED and the buzzer, and why at the emergency level with `COM_LOW_BAT_ACT` = 0 there is no longer a red color, is in `px4-hardware-peripherals`.
- **Offboard.** There is no `COM_FAIL_ACT_T` delay: the switch is immediate. Since 1.17, if Position, Altitude or Stabilized is selected and there is no manual control, `NAV_RCL_ACT` is carried out; in 1.18 with `NAV_RCL_ACT` = 7 (which has no action of its own) Hold is used instead of the manual mode (`manualControlLossFallbackAction`, `failsafe.h`). Value 2 was called Manual before 1.16.
- **`NAV_RCL_ACT` = 7** (since 1.18): on RC loss in a manual mode the vehicle switches to Hold with an ordinary mode change, without a failsafe state, so an external mode or Offboard can keep controlling it; if Hold is impossible (no position), the normal failsafe triggers (`Commander.cpp`, `manualControlLossModeSwitch`).
- **Wind.** `COM_WIND_MAX` alone is not enough: with `COM_WIND_MAX_ACT` = 0 the flag is not raised.

### Position loss: what replaced COM_POSCTL_NAVL
`COM_POSCTL_NAVL` (0 Altitude, 1 Land) was removed in 1.17, `COM_POS_FS_DELAY` in 1.16. Now only the chain of mode requirements applies:
- the position **becomes valid** at eph < `COM_POS_FS_EPH` (5 m, −1 means do not check) and **is lost** at eph > 2.5 × the threshold = 12.5 m, or when the data is older than 1 s; it comes back after 1 s of good data;
- **Position** requires a "relaxed" position (no accuracy threshold). Without it, Altitude; without altitude, Stabilized;
- **Mission, Hold, Return** on a multirotor require a position with the threshold. Lost, the chain is Hold → RTL → Land → Descend: Land requires a relaxed local position, Descend requires nothing;
- on a plane, Mission, Hold and Return require only a relaxed position.

`COM_POS_LOW_EPH` is an early threshold: the position is still valid but less accurate than set; in Mission and Hold `COM_POS_LOW_ACT` is carried out, in other modes a warning.

### Geofence
- **A cylinder around home:** `GF_MAX_HOR_DIST` and `GF_MAX_VER_DIST`, 0…10000 m, 0 disabled. Needs a valid home.
- **Polygons and circles** are drawn in QGC → Plan → Fence: inclusion (stay inside) and exclusion (do not enter). They are stored in dataman. When the fence is loaded, each polygon or circle that does not contain home (an exclusion one: that contains home), or, with `GF_ACTION` ≠ 0 in flight, the current position, is discarded with "Geofence invalid, doesn't contain Home position" / "… current vehicle position"; the other areas stay active, so read the message after every upload.
- **`GF_SOURCE`**: 0 the position estimate (GPOS), 1 raw GPS, independent of EKF.
- There is no triggering "in advance from the braking distance" in 1.18: the experimental `GF_PREDICT` (0 by default in 1.17, with a flyaway risk warning) was removed. Since 1.18 a geofence that did not upload completely is cleared and reported to the operator (`GF_STATUS_FAILED`) instead of staying partially loaded.
- **`GF_ACTION`** = 0 also turns off the check itself. A geofence Hold runs at once; you can leave it only by changing the mode, the sticks do not take over. A violated geofence denies arming. `GF_ACTION` = 4 kills the vehicle at the very first crossing, and `CBRK_FLIGHTTERM` has no effect on it.
- The Return altitude must be below `GF_MAX_VER_DIST`, otherwise the vehicle breaks the ceiling on its very first return.

### Failure detector and flight termination
- **Attitude.** Roll above `FD_FAIL_R` or pitch above `FD_FAIL_P` (60°, 0…180, 0 off) for longer than `FD_FAIL_R_TTRI` / `FD_FAIL_P_TTRI` (0.3 s, 0.02…5). Checked only in modes with attitude stabilization (not in Acro).
- **What follows.** In the first `COM_SPOOLUP_TIME` + 3 = 1 + 3 = 4 s after arming, a **disarm** (it flipped on takeoff); the 3 s are hard-coded in 1.18 (`failsafe.cpp`; before 1.18 `COM_LKDOWN_TKO`). Later: with `CBRK_FLIGHTTERM` = 121212 (default) only a warning; with 0, **Terminate**, and the motors stop in the air. Zero is set only on a vehicle with a parachute.
- **ESC.** With `FD_ACT_EN` = 1: if ESCs with telemetry did not confirm arming within 0.4 s, during `COM_SPOOLUP_TIME`, a disarm (`escCheck.cpp`). In 1.17 this was done by `FD_ESCS_EN` (default 1, a 0.3 s threshold); it was removed, and `FD_ACT_EN` defaults to **0** in 1.18: the check is off until you turn it on.
- **Motors.** `FD_ACT_EN` = 1: the expected current = `MOTFAIL_C2T` (35 A at full thrust; the parameter description labels the unit "A/%", which is misleading) × normalized thrust; if the actual current differs from it by more than `MOTFAIL_OFF` (10 A) in either direction for longer than `MOTFAIL_TIME` (1 s) → `COM_ACT_FAIL_ACT`. Needs current telemetry from the ESC. Before 1.18 only undercurrent: `FD_ACT_MOT_C2T` (2 A/%), `FD_ACT_MOT_THR` (0.2), `FD_ACT_MOT_TOUT` (100 ms); these names were removed and do not migrate.
- **Altitude.** `FD_ALT_LOSS` (since 1.18, 0 by default, off): a multirotor below the setpoint by more than the threshold for longer than `FD_ALT_LOSS_T` → the same as a flip: a disarm in the first 4 s, later Terminate only with `CBRK_FLIGHTTERM` = 0.
- **External trigger.** `FD_EXT_ATS_EN` = 0, threshold `FD_EXT_ATS_TRIG` 1900 µs: an input from an external flight termination system.

### Return: where to fly
| `RTL_TYPE` | Where and how |
|---|---|
| 0 (MC default) | the closest of: home, a rally point; direct path |
| 1 (FW and VTOL default) | the closest of: the start of the mission landing pattern, a rally point; if there are none, home. A VTOL in hover mode takes the closest point of all |
| 2 | along the mission route to its landing; no landing, back along the mission to home. Rally points are not considered |
| 3 | the closest of: home, the start of the landing pattern, a rally point; direct path |
| 4 (since 1.16) | the mission landing or home back along the mission, whichever is closer by number of waypoints. Rally points are not considered |
| 5 (since 1.18) | a rally point only, direct path; the mission landing and home are not considered. Without uploaded rally points arming is allowed since 1.18 (with the warning "No rally point configured"): then Return lands at the current position instead of flying home (`rtl.cpp`, `findRtlDestination`) |

Rally points (safe points) are drawn in QGC → Plan → Rally. An alternative displaces home only if it is at least 2 m closer. `RTL_APPR_FORCE` = 1 leaves a VTOL only the points with a defined approach.

### Return: altitude and the cone
| Parameter | Default | MC / FW / VTOL | Range | Meaning |
|---|---|---|---|---|
| `RTL_RETURN_ALT` | 60 m | 30 / 100 / 60 | ≥ 0 | return altitude above the destination |
| `RTL_DESCEND_ALT` | 30 m | 10 / 100 / 30 | ≥ 0 | loiter altitude above the point |
| `RTL_LAND_DELAY` | 0 s | 0 / −1 / 0 | ≥ −1 | wait before landing; −1 means circle and do not land |
| `RTL_MIN_DIST` | 10 m | the same | ≥ 0.5 | the cone applies closer than this distance |
| `RTL_CONE_ANG` | 45° | the same | 0…90 (0, 25, 45, 65, 80, 90) | cone half-angle; 0 means no cone |
| `RTL_LOITER_RAD` | 80 m | the same | ≥ 25 | radius of the descent circle (FW, VTOL) |
| `RTL_PLD_MD` | 0 | the same | 0 none, 1 opportunistic, 2 required | precision landing at the end of Return |
| `NAV_ACC_RAD` | 10 m | 10 / 10 / 10 (before 1.18 the MC had 2: `rc.mc_defaults` no longer sets it) | 0.05…200 | waypoint acceptance radius |

The return altitude h above the destination at distance d (the `computeReturnAltitude` function in `rtl.cpp`, only for a multirotor and a VTOL in hover mode, and only with `RTL_CONE_ANG` > 0):
- d ≤ `NAV_ACC_RAD`: h = 2·d;
- `NAV_ACC_RAD` < d ≤ `RTL_MIN_DIST`: h = min(d / tan(`RTL_CONE_ANG`), `RTL_RETURN_ALT`), but not below 2·`NAV_ACC_RAD`;
- d > `RTL_MIN_DIST`: h = `RTL_RETURN_ALT`;
- the result is not below the current altitude: in Return the vehicle does not descend en route.

{{diagram:chart-px4-rtl-cone|With the 1.18 defaults (NAV_ACC_RAD = RTL_MIN_DIST = 10 m) there is no cone branch at all: closer than 10 m h = 2·d; to keep the vehicle from climbing to full altitude nearby, raise RTL_MIN_DIST rather than changing the angle.}}

So the cone ends at `RTL_MIN_DIST`. With the 1.18 multirotor defaults (`NAV_ACC_RAD` 10 m, `RTL_MIN_DIST` 10 m, 45°) the cone branch is empty: 8 m from home the return altitude is 2·8 = 16 m, and at 11 m already the full 30 m. In 1.17 the multirotor `NAV_ACC_RAD` was 2 m, and at 8 m the cone gave 8 m: after the upgrade, a vehicle nobody configured climbs twice as high near home. The documentation describes `RTL_MIN_DIST` differently ("closer than this, return at the current altitude"); here it follows the code (`RTL::computeReturnAltitude`, `rtl.cpp`, v1.18.0; in 1.17 the same arithmetic was called `calculate_return_alt_from_cone_half_angle`). A plane and a VTOL in plane mode have no cone: max(current, `RTL_RETURN_ALT`).

The phases of a direct multirotor Return: climb to h in place → fly to the point → land. Since 1.16, with `RTL_LAND_DELAY` = 0, a multirotor starts landing straight from the return altitude; the stop at `RTL_DESCEND_ALT` with a wait happens only with a nonzero delay (in 1.15, always). A plane and a VTOL in plane mode always descend in a circle to `RTL_DESCEND_ALT`; a VTOL in hover behaves like a multirotor. A landed vehicle does not execute Return.

Landing: below `MPC_LAND_ALT1` = 10 m the speed decreases toward `MPC_LAND_SPEED` = 0.7 m/s, below `MPC_LAND_ALT2` = 5 m it holds exactly that; with a rangefinder, below `MPC_LAND_ALT3` = 1 m, `MPC_LAND_CRWL` = 0.3 m/s. `RTL_PLD_MD` has no effect on landings defined in a mission.

The mission next to Return: `MIS_TKO_LAND_REQ` (0; FW and VTOL 2, a landing is required), `MIS_DIST_1WP` = 10000 m (900 m in 1.15; in 1.17 only a warning), `NAV_ACC_RAD`, which also enters the cone formula.

### Disarm after landing
| Parameter | Default | Range | Meaning |
|---|---|---|---|
| `COM_DISARM_LAND` | 2 s | ≤ 0 off | disarm this long after the landed flag |
| detector time (no parameter since 1.18; before 1.18 `LNDMC_TRIG_TIME`, 0.1…10) | 1 s; 3 s if there is a rangefinder but it currently gives no distance | — | three stages: ground contact → maybe landed → landed, each a third of the time (`MulticopterLandDetector.cpp`) |
| `LNDMC_Z_VEL_MAX` | 0.25 m/s | ≥ 0 | must be below `MPC_LAND_SPEED` and `MPC_LAND_CRWL` |
| `LNDMC_XY_VEL_MAX` | 1.5 m/s | — | horizontal speed "on the ground" |
| `LNDMC_ROT_MAX` | 20 °/s | — | angular rate "on the ground" |
| `LNDFW_TRIG_TIME` | 2 s | ≥ 0.1 | plane; `LNDFW_AIRSPD_MAX` 6 m/s, `LNDFW_VEL_XY_MAX` 5 m/s, `LNDFW_VEL_Z_MAX` 1 m/s |

From touchdown to the motors stopping is about 1 + `COM_DISARM_LAND` = 1 + 2 = 3 s. Auto-disarm works only after a takeoff and does not work while an unfinished mission is running (intermediate landings).

### Failure injection in SITL
`SYS_FAILURE_EN` = 0 on a flight controller, 1 in SITL (`init.d-posix/rcS`). The console command is `failure <unit> <type> [-i instance]`. Units: `gyro`, `accel`, `mag`, `baro`, `gps`, `optical_flow`, `vio`, `distance_sensor`, `airspeed`, `battery`, `motor`, `servo`, `avoidance`, `rc_signal`, `mavlink_signal`. Types: `ok` (clear), `off`, `stuck`, `garbage`, `wrong`, `slow`, `delayed`, `intermittent`. Not every unit–type pair is implemented; ready-made chains with output are in px4-setup-scratch, step 6. Never enable the parameter on a real vehicle.

### PX4 and ArduPilot: matching concepts
ArduPilot names are Copter 4.7.3; details are in ap-safety-fs.

| Concept | PX4 1.18 | ArduCopter 4.7 |
|---|---|---|
| RC loss | `NAV_RCL_ACT` | `FS_THR_ENABLE` |
| GCS loss | `NAV_DLL_ACT` | `FS_GCS_ENABLE` |
| Battery | `COM_LOW_BAT_ACT` + `BAT_*_THR` | `BATT_FS_LOW_ACT`, `BATT_FS_CRT_ACT` |
| Geofence | `GF_ACTION` | `FENCE_ACTION` |
| Return altitude | `RTL_RETURN_ALT` | `RTL_ALT_M` |
| Cone | `RTL_CONE_ANG` (angle) | `RTL_CONE_SLOPE` (slope) |
| Wait before landing | `RTL_LAND_DELAY`, `RTL_DESCEND_ALT` | `RTL_LOIT_TIME`, `RTL_ALT_FINAL_M` |
| Pre-arm checks | `COM_ARM_*`, `CBRK_*` | `ARMING_SKIPCHK` |
| Auto-disarm | `COM_DISARM_LAND` | `DISARM_DELAY` |
| Estimator failure | the mode chain | `FS_EKF_ACTION` |
| Flip | `FD_FAIL_R/P` | `FS_CRASH_CHECK` |

The main difference: PX4 has a shared Hold delay and a single "most severe action wins" rule; in ArduPilot the priorities and exceptions are set per failsafe (`FS_OPTIONS`).

### Place in the system

- **Takes in:** manual control frames and switch positions from the receiver (`px4-setup-scratch`); eph and position validity flags from EKF2 (`nav-resilience`); the remaining charge from a calibrated `BAT1_*` (`px4-setup-scratch`); the ground station heartbeat (`px4-intro`) over the MAVLink link whose budget is computed in `px4-hardware-peripherals`.
- **Gives out:** the mode and the armed, kill, termination flags to the controllers and outputs (`px4-architecture`, `px4-control`); the parameters that ArduPilot is compared with (`ap-safety-fs`).
- **If you get it wrong here:** a `RTL_RETURN_ALT` below obstacles or above the geofence ceiling shows up on the very first Return; an uncalibrated remaining charge shifts the battery thresholds, covered in `px4-setup-scratch`; `CBRK_FLIGHTTERM` = 0 without a parachute turns a sharp maneuver into the motors stopping in the air.

## practice
An exercise on paper: no simulator or hardware needed, all answers follow from the theory above. The numbers are computed with the same formulas as in the module.

### Step 1. The inputs
A multirotor, a 10000 mAh battery, an average current of 20 A (we treat the remaining charge as linear in amp-hours used), Return speed `MPC_XY_CRUISE` = 5 m/s, climb `MPC_Z_V_AUTO_UP` = 3 m/s. The parameter set; the rest are 1.18 multirotor defaults (including `BAT1_CAPACITY` = −1: there is no remaining flight time estimate, so the remaining-time return that is part of `COM_LOW_BAT_ACT` = 3 will not trigger here; with the capacity set, Return would start earlier):

```
COM_RC_LOSS_T    0.5      COM_FAIL_ACT_T   5        MAN_OVERRIDE_SPD 1
NAV_RCL_ACT      2        COM_RCL_EXCEPT   1        NAV_DLL_ACT      0
COM_LOW_BAT_ACT  3        BAT_LOW_THR      0.15     BAT_CRIT_THR     0.07
BAT_EMERGEN_THR  0.05     GF_ACTION        2        GF_MAX_HOR_DIST  300
GF_MAX_VER_DIST  30       RTL_TYPE         0        RTL_RETURN_ALT   40
RTL_MIN_DIST     60       RTL_CONE_ANG     45       NAV_ACC_RAD      2
RTL_LAND_DELAY   0        CBRK_FLIGHTTERM  121212   COM_DISARM_LAND  2
```

The timeline (t is seconds from the start of the log). Position mode, 25 m above home, remaining charge at t = 0 is 0.20.

| t, s | Event |
|---|---|
| 60 | the vehicle crossed 300 m from home and keeps getting a "forward" stick |
| 150 | the ground station heartbeat disappeared |
| 200 | the last valid RC frame; the vehicle is 305 m from home |
| 270 | by calculation the vehicle is 7.5 m from home at 40 m (205.5 s + 5 s of climb; 59.5 s × 5 m/s = 297.5 m) |

### Step 2. Battery thresholds
The time a threshold is crossed: t = (0.20 − threshold) · 10 Ah / 20 A; for seconds, multiply by 3600. Low: 0.05 · 0.5 h = 90 s. Critical: 0.13 · 0.5 h = 234 s. Emergency: 0.15 · 0.5 h = 270 s. Between critical and emergency: 36 s.

### Step 3. What PX4 does at each moment
Fill in the table yourself, then compare.

| t, s | PX4 action | Why |
|---|---|---|
| 60 | Hold at once, no 5 s | `GF_ACTION` = 2; Hold is not deferred. The sticks do not take over; you exit by changing the mode |
| 90 | warning | the low level has no action |
| 150–160 | nothing | the GCS loss flag goes up at second 160, but `NAV_DLL_ACT` = 0 |
| 200.5 | Hold with a deferred Return | `COM_RC_LOSS_T` 0.5 s; the mode is Position, and the `COM_RCL_EXCEPT` = 1 exception covers only Mission |
| 205.5 | Return, climb to 40 m | 200 + 0.5 + 5; d = 305 m > `RTL_MIN_DIST`, h = `RTL_RETURN_ALT` |
| ≈ 207 | Return continues | a 5 m climb at 3 m/s; at 30 m the geofence ceiling is broken, but Hold is lighter than RTL, so only a message |
| 234 | Return continues | critical with `COM_LOW_BAT_ACT` = 3 gives RTL, and it is already running |
| 270 | Land at once, 7.5 m from home | emergency → Land is more severe than RTL; the vehicle is already in a failsafe, no delay |
| touchdown + 3 s | disarm | the 1 s land detector (hard-coded in 1.18) + `COM_DISARM_LAND` 2 s |

### Step 4. Return altitude from the cone
The same set (40 m, `RTL_MIN_DIST` 60 m, 45°, `NAV_ACC_RAD` 2 m). Compute h for each row:

| d, m | current altitude, m | h, m | Formula branch |
|---|---|---|---|
| 1.5 | 1 | 3.0 | d ≤ `NAV_ACC_RAD`: 2·d |
| 5 | 2 | 5.0 | cone 5 / tan 45° = 5, not below 4 |
| 25 | 10 | 25.0 | cone |
| 50 | 10 | 40 | the cone would give 50, capped by `RTL_RETURN_ALT` |
| 61 | 10 | 40 | beyond `RTL_MIN_DIST` |
| 25 | 32 | 32 | the current altitude is above the computed one |

A comprehension check: with `RTL_CONE_ANG` = 65° at d = 25 m you get 25 / tan 65° = 11.7 m; with the default `RTL_MIN_DIST` = 10 m at the same 25 m, the full 40 m.

### Step 5. Three configuration errors
Find them in the step 1 set before reading the reference. A hint: one is about altitudes, one about battery and range, one about the link in a mission.

### Moving to real hardware
Propellers off, the vehicle on the bench, powered from the battery.
1. `commander check` in the QGC console prints `Preflight check: OK`, and a second call is OK too; there are no `Preflight Fail` messages in QGC and in `dmesg`, or each one is explained by the checks table.
2. Disarmed, switch the transmitter off: after 0.5 s QGC shows a manual control loss message, and `listener failsafe_flags` shows `manual_control_signal_lost: True`; switch the transmitter on and the flag clears.
3. Arm without props, kill switch: the motors stop at once; flip it back within 5 s and they spin again; hold it longer and it disarms. You have 11 s for all of this before the no-takeoff auto-disarm.
4. In the field, with props, at 10 m in Position: switch the transmitter off → Hold 5 s → Return; switch the transmitter on, change the mode, and control is yours. Criterion: the times match the step 3 calculation within 1 s.

Self-check: the lab is done when:
- **Calculation:** the three battery threshold times match step 2 (90, 234 and 270 s, tolerance 1 s); the step 3 table was filled in without the hint, and all its actions and two times, 200.5 and 205.5 s, match (tolerance 0.2 s); the six step 4 altitudes match within 0.1 m.
- **Configuration errors:** all three from the reference below are named, each with the parameter and the new value.
- **Hardware (if available):** bench items 1–3 passed without props; the RC loss flag went up after 0.5 s, the kill disarm after 5 s (tolerance 1 s).

**Reference for the self-check.** The three errors: (1) `RTL_RETURN_ALT` 40 m is above `GF_MAX_VER_DIST` 30 m, so every Return breaks the ceiling; with `GF_ACTION` = 4 that would stop the motors. The fix: a ceiling above the return altitude with a margin, for example 60 m. (2) Between critical and emergency there are 36 s, while returning from 305 m at 5 m/s takes 5 s of Hold, 5 s of climb and 61 s of flight, 71 s in total: the vehicle will not land at home. In the timeline at second 270 there are still 7.5 m to go, and only because Return started earlier, on RC loss; had it started at the critical level at second 234, 175 m would remain to home (36 − 5 − 5 = 26 s of flight, 130 m of 305). The fix: raise `BAT_CRIT_THR` so the gap covers a return from the working range, or reduce the range. (3) `COM_RCL_EXCEPT` = 1 with `NAV_DLL_ACT` = 0: in a mission the loss of both the transmitter and the ground station triggers nothing until the end of the mission. The fix: `NAV_DLL_ACT` = 2, or remove the exception. Typical wrong answers: "at second 60, Hold after 5 s": the delay applies only to RTL, Land and Descend; "at second 270, first Hold for 5 s": the vehicle is already in a failsafe, so the delay is skipped; "at 25 m the altitude is 40 m": the cone was forgotten, or the default `RTL_MIN_DIST` was used.

## diagnostics
- **Symptom:** the vehicle will not arm, QGC shows "Preflight Fail" or a red readiness indicator.
  - Possible cause: one of the checks in the arming table; most often calibration, IMU or compass inconsistency, no manual control, charge below `BAT_CRIT_THR`, Return or Land mode.
  - What to do: read the `Preflight Fail: …` messages in QGC (or `commander check`, then `dmesg`), find the row in the checks table; do not disable a check until you understand the cause.
- **Symptom:** it asks you to press a safety button you do not have, or the other way round: the button is there but locks nothing.
  - Possible cause: `CBRK_IO_SAFETY` = 0 without a button; the default 22027 means the button is not used.
  - What to do: 22027 without a button, 0 with a button; `COM_PREARM_MODE` = 1 if you need the servos before arming.
- **Symptom:** the motors stopped in the air, and the log shows termination or "Kill engaged".
  - Possible cause: the kill switch was bumped; `CBRK_FLIGHTTERM` = 0 and roll above `FD_FAIL_R`; a Terminate action on the geofence or link loss; not a failsafe at all, but a power sag and a flight controller reboot.
  - What you see in the log: `failsafe_flags.fd_critical_failure`, `actuator_armed.kill` or `.termination`; on a reboot the log ends without a disarm.
  - What to do: put kill on a switch protected against accidental presses; set `CBRK_FLIGHTTERM` back to 121212 if there is no parachute; do not set Terminate in `GF_ACTION` and `NAV_*_ACT` without a parachute.
- **Symptom:** a disarm in the first seconds after arming when trying to take off.
  - Possible cause: roll or pitch above 60° in the first 4 s (wrong motor order or spin direction); the ESCs did not confirm arming (with `FD_ACT_EN` = 1; before 1.18 `FD_ESCS_EN`); no liftoff for 11 s (`COM_DISARM_PRFLT`).
  - What to do: a motor test without props as in px4-setup-scratch; check the ESC telemetry.
- **Symptom:** on RC loss the vehicle hovers for 5 s and only then returns.
  - Possible cause: that is `COM_FAIL_ACT_T`, normal behavior.
  - What to do: change it only deliberately; at 0, stick takeover in a failsafe stops working.
- **Symptom:** the link came back, but the vehicle keeps doing Return and ignores the sticks.
  - Possible cause: the action clears only on a mode change; the sticks do not take over with `MAN_OVERRIDE_SPD` < 0, on a plane, during the Hold delay, and with a slow stick movement, since stick speed is compared, not deflection.
  - What to do: switch the mode with a switch; check `MAN_OVERRIDE_SPD` (after an upgrade from 1.17, −1 means `COM_RC_OVERRIDE` was 0).
- **Symptom:** a Return near home climbs to full altitude.
  - Possible cause: d is greater than `RTL_MIN_DIST` (10 m by default), so the cone no longer applies.
  - What to do: raise `RTL_MIN_DIST` to the radius you need, and leave the angle.
- **Symptom:** nothing happens when the telemetry with the ground station is lost.
  - Possible cause: `NAV_DLL_ACT` = 0 by default.
  - What to do: for missions without a transmitter, `NAV_DLL_ACT` = 2 and `COM_DL_LOSS_T` to suit the link quality.
- **Symptom:** after landing the motors do not stop.
  - Possible cause: the land detector does not see the landing (`LNDMC_Z_VEL_MAX` above the landing speed, vibration); an unfinished mission is running; `COM_DISARM_LAND` ≤ 0.
  - What to do: disarm with the switch; check `vehicle_land_detected` in the log.

## checklist
- `commander check` gives `OK` twice in a row, with no `Preflight Fail` messages; `CBRK_*` only the two factory ones.
- Taking over in a failsafe is practiced: the mode with a switch (the stick takes over only with a sharp movement).
- `NAV_RCL_ACT`, `COM_LOW_BAT_ACT` (not 0), `NAV_DLL_ACT` are chosen for the task.
- The `BAT_CRIT_THR` − `BAT_EMERGEN_THR` gap covers a return from the working range.
- `RTL_RETURN_ALT` is above obstacles and below `GF_MAX_VER_DIST`.
- `GF_ACTION` is not 4 without a parachute; `CBRK_FLIGHTTERM` = 121212 without a parachute.
- The kill switch is assigned and tested without props.
- RC loss is tested on the bench and in the air at 10 m.

## references
- PX4 v1.18.0 source, commander/failsafe/failsafe.cpp (conditions and actions) | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/modules/commander/failsafe/failsafe.cpp | primary | A
- PX4 v1.18.0 source, navigator/rtl.cpp (return point, cone) | https://github.com/PX4/PX4-Autopilot/blob/v1.18.0/src/modules/navigator/rtl.cpp | primary | A
- PX4 User Guide v1.17 — Safety (Failsafe) Configuration | https://docs.px4.io/v1.17/en/config/safety.html | primary | A
- PX4 User Guide v1.17 — Return Mode | https://docs.px4.io/v1.17/en/flight_modes/return.html | primary | A
- PX4 User Guide v1.17 — Geofence | https://docs.px4.io/v1.17/en/flying/geofence.html | primary | A
- PX4 User Guide v1.17 — System Failure Injection | https://docs.px4.io/v1.17/en/debug/failure_injection.html | primary | A

## notes
The cone formula and the multirotor behavior with `RTL_LAND_DELAY` = 0 were taken from the 1.17.0 source, rechecked against 1.18.0 (the function was renamed to `computeReturnAltitude`, the arithmetic is the same; the multirotor `NAV_ACC_RAD` default changed), and they disagree with the text of the Return Mode page; when you update the firmware, check `rtl.cpp` again. The exercise is a paper calculation and was not run in a simulator; the values of the parameters new in and removed in 1.18 (`MAN_OVERRIDE_SPD` = 1, `NAV_ACC_RAD` = 10, `FD_ACT_EN` = 0, `MOTFAIL_*`, the absence of `COM_KILL_DISARM`, `COM_RC_OVERRIDE`, `LNDMC_TRIG_TIME` and others) were checked with `param show` in SITL v1.18.0 (SIH, `sihsim_quadx`).
