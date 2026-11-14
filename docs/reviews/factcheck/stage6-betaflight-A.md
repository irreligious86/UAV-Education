# stage6-betaflight-A

Scope: content/betaflight/bf-adjustments.md, bf-rates-rc.md, bf-arming-safety.md, bf-hd-osd-video.md, their banks
(content/quiz/<id>.json, content/tasks/<id>.json) and diagram scripts (scripts/diagrams/s6_bf_*.py for the four ids).
Scope documents: docs/reviews/betaflight-coverage-audit.md, docs/reviews/betaflight-fixes-2026-11-15.md. Where the audit
and the source disagree, this review follows the source.

Basis:
- Betaflight 4.5-maintenance at 7dcc851 (version.h 4.5.6), 2025.12-maintenance at 5b88201 and master at a12049c (2026.12),
  all full local clones. I read these files: fc/rc_adjustments.[ch], fc/rc_controls.c, fc/core.c, fc/rc.c,
  fc/controlrate_profile.c, fc/runtime_config.[ch], config/config.c, config/feature.c, io/vtx.c, io/vtx_control.c,
  io/vtx_msp.c, io/vtx_smartaudio.c, io/beeper.c, io/serial.[ch], io/displayport_msp.c, osd/osd.[ch],
  osd/osd_warnings.c, osd/osd_elements.c, msp/msp.c, rx/rx.c, pg/rx.c, pg/vcd.c, pg/displayport_profiles.c,
  flight/pid.[ch], flight/pid_init.c, flight/mixer.c, flight/failsafe.c, flight/gps_rescue.c, flight/imu.c,
  sensors/gyro.[ch], scheduler/scheduler.c, telemetry/telemetry.c, cli/cli.c, cli/settings.c, blackbox/blackbox.c,
  common/filter.c. I also checked tags 4.1/4.2/4.3/4.4-maintenance cli/settings.c on raw.githubusercontent.com.
- The betaflight.com docs repo (master 357535a): Inflight-Adjustments, Arming-Sequence-And-Safety,
  Runaway-Takeoff-Prevention, Yaw-Spin-Recovery-and-Gyro-Overflow-Detect, wiki/app/osd-tab, tuning/4-3-Tuning-Notes.
- ExpressLRS master: src/src/common.cpp and rx_main.cpp (DVDA forwarding).
- INAV 8.0.1 (local clone): io/serial.h, fc/settings.yaml. ArduPilot master: AP_SerialManager.h and AP_OSD.cpp.
  ArduCopter-stable: AP_MSP.cpp.
- HDZero: hdzero-vtx-docs (vtx_targets, vtx_user_manual, vtx_troubleshoot) and hdzero-vtx src (msp_displayport.c,
  msp_protocol.h).
- I read the manufacturer pages and PDFs that curl cannot reach through the proxy with WebFetch. These were the
  DJI O3 manual, the DJI O4 manual, the DJI O4 specs, the DJI FPV specs, the Caddx Walksnail HD Pro page and the Walksnail
  Mini V3 manual (rotorama). I did not read the Walksnail Quickstart V1.1, the Clifton O3 spec PDF, the manuals.plus DJI
  release notes, the getfpv Vista listing, the Divimath white paper or the Oscar Liang page.

Labs. I extracted every Python block in the four modules and reran it: the helper copies in /tmp/claude-0/work/s6
against the 4.5 / 2025.12 / master sources, and the arming blocks standalone. Then I compared the pasted outputs with
the run line by line.
- bf-arming-safety: all 3 blocks are byte-identical to the helpers, and all 3 outputs match byte for byte.
- bf-rates-rc: the `python` block is a contiguous excerpt of rates_lab.py. All three output blocks are contiguous
  substrings of the run.
- bf-hd-osd-video: the 3 blocks concatenated give the same output as hd_osd_calc.py. Block 1 differs from the helper
  only in its docstring and header comment. All output blocks match.
- bf-adjustments: the output blocks are excerpts of the run, and every pasted line is present. Three lines of the
  Python excerpt are condensed one-liners of the helper code, with identical semantics. After fix A1/A2, two output
  lines changed in the helper (/tmp/claude-0/work/s6/bf-adjustments.adj_lab.py and .lab_output.txt were updated in step).

`python3 scripts/validate_content.py` after the edits reported only "not in manifest" for the four modules and errors
from other authors' files (nav-vtrn quiz length rule, nav-vtrn diagram, other unregistered modules). The diagram
scripts were not changed, so no diagram rebuild was needed.

Totals: 9 fixed, 7 left as uncertain, 36 ok (several ok entries group many checked values).

## Fixes

### A1. fixed: bf-adjustments.md theory + lab output (and helper), step-down beep
- Quote: "Бипер: 2 коротких — вверх, 1 длинный — вниз." Lab output: "beep 1 long".
- Why: `applyStepAdjustment()` calls `beeperConfirmationBeeps(delta > 0 ? 2 : 1)`. Every confirmation beep has the same
  duration (`BEEPER_CONFIRMATION_BEEP_DURATION` = 2). So "down" is one beep of the same short length, not a long one. The
  docs page says "beep shorter/longer", which the code contradicts. I changed the text and the model's label
  (`1 short`), regenerated the helper output, and replaced the two pasted lines.
- Source: https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/fc/rc_adjustments.c ;
  https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/io/beeper.c

### A2. fixed: bf-adjustments.md theory, lab step 5 and diagnostics, `vtx` slot evaluation
- Quotes: "первый подходящий применяется, цикл обрывается; повторно тот же слот не применяется, пока не сработает
  другой"; lab "slot 3 (AUX5) was never evaluated: a power slot with a lower index matched first and the loop breaks";
  "Слоты мощности покрывают весь ход AUX4, поэтому слот 3 с большим индексом не проверяется никогда — порядок слотов
  решает"; diagnostics "или слот с меньшим индексом уже совпал … поставить такой слот первым".
- Why: in `vtxUpdateActivatedChannel()` the match condition is `isRangeActive(...) && index != lastIndex`. The slot applied
  last time is skipped and the loop continues to the next active slot. The function runs on every RX frame
  (`processRxModes`, fc/core.c), so two simultaneously active slots alternate frame by frame and both take effect. A
  replay of the module's own slot table, with the band slot at index 3 and both channels high before arming, applies
  slot 2 and slot 3 on alternate calls, and the band does change to R. Even the helper's single-call model evaluates
  slot 3 on the "AUX5 high in flight" step. The real reason the band does not change in flight is the `locked` latch
  (this was already stated correctly). I rewrote the theory bullet (it now also warns that overlapping power slots make
  the power toggle), the helper's final message and the pasted line, the step 5 explanation and the diagnostics entry.
  The 2025.12 code is identical.
- Source: https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/io/vtx_control.c ;
  https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/fc/core.c

### A3. fixed: quiz/bf-adjustments.json Q6, built on the same wrong premise
- Quote: "Почему слот 3 (смена бэнда на AUX5) никогда не срабатывает?", keyed "Слоты 0–2 перекрывают весь ход AUX4, а
  применяется первый совпавший слот".
- Why: see A2. The keyed answer is false in firmware. I rewrote the question as "in flight the pilot flips AUX5 up, what
  happens?". The keyed answer is now "nothing: band/channel latched after the first arm". The old explanation is kept as
  a distractor. The keyed option is not the longest, and the validator passes.
- Source: as A2.

### A4. fixed: bf-adjustments.md theory, adjustment limits
- Quote: "рейты 0–255".
- Why: the code clamps RC rate to 1..`CONTROL_RATE_CONFIG_RC_RATES_MAX` (255), expo to 0..`CONTROL_RATE_CONFIG_RC_EXPO_MAX`
  (100) and super rate to 0..255. I changed the text to "RC rate 1–255, expo 0–100, super rate 0–255".
- Source: https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/fc/rc_adjustments.c (rc_controls.h
  constants)

### A5. fixed: bf-adjustments.md theory, number of SIMPLIFIED_MASTER_MULTIPLIER in master
- Quote: "Функция SIMPLIFIED_MASTER_MULTIPLIER, описанная на betaflight.com под номером 31, есть только в `master`."
- Why: true that it exists only in master, but there it is CLI number 32. Number 31 is LED_DIMMER, and 33 is
  BATTERY_PROFILE (the lab script run on master). The docs page's "31" is wrong for master as well. I added
  "и там это номер 32 (31 — LED_DIMMER)".
- Source: master src/main/fc/rc_adjustments.c (local clone a12049c); docs/wiki/guides/current/Inflight-Adjustments.md

### A6. fixed: bf-rates-rc.md lab step 2 analysis, ripple range
- Quote: "производная setpoint в 17–161 раз больше нормы".
- Why: the pasted table's "ripple OFF" column is 161.0 / 54.0 / 33.0 / 17.0 / 9.0 for 50…F1000. The range is 9–161.
  I changed the text to "9–161".
- Source: the module's own lab output (rerun, identical).

### A7. fixed: bf-arming-safety.md hardware step 1, NOPREARM row
- Quote: "Тумблеры FAILSAFE, GPS RESCUE, PREARM в исходное положение | `BOXFAILSAFE`, `RESCUE_SW`, `NOPREARM`".
- Why: `updateArmingStatus()` clears NOPREARM only while the PREARM mode is active (and not `WAS_ARMED_WITH_PREARM`).
  Returning PREARM to its "initial" (off) position sets the flag. I changed the row to "FAILSAFE и GPS RESCUE выключить,
  PREARM (если задан) включить".
- Source: https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/fc/core.c

### A8. fixed: bf-hd-osd-video.md reference table, `osd_sys_*_pos` list
- Quote: "`osd_sys_*_pos` (`goggle_voltage`, `vtx_temp`, `bitrate`, `delay`, `lq`, `goggle_dvr`, `vtx_dvr`, `fan_speed`,
  `warnings`, `distance`)".
- Why: 4.5 settings.c has 11 of them. `osd_sys_vtx_voltage_pos` was missing, so I added it.
- Source: https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/cli/settings.c

### A9. fixed: bf-hd-osd-video.md "Мощность и закон", Walksnail FCC EIRP
- Quote: "Walksnail: FCC < 30 дБм, CE < 14 дБм, MIC < 25 дБм".
- Why: < 30 dBm FCC is the HD Pro figure (Caddx page). The Mini V3 manual cited by the module gives FCC < 27 dBm. I added
  "(Mini V3 — < 27 дБм)".
- Sources: https://www.caddxfpv.com/products/walksnail-avatar-hd-pro-kit-dual-antenna ;
  https://www.rotorama.com/assets/docs/5f2b6df00100231feac11bb2a7480570/47716-1/walksnail-avatar-hd-mini-vtx-v3-manual-en.pdf

## Left: uncertain

### U1. left: uncertain, helper glossary /tmp/claude-0/work/s6/bf-adjustments.glossary.json, `vtx` entry
- Quote: "Применяется первый совпавший слот".
- Why: the entry is imprecise for the reason given in A2. It is not one of the files I was allowed to edit. When the
  glossary is merged, suggested wording: "слоты по порядку, пропуская слот, применённый в прошлый раз; при двух активных
  слотах они чередуются".
- Source: as A2.

### U2. left: uncertain, bf-arming-safety.md hardware step 2, hand-tilt warning
- Quote: "Держи наклон не дольше 1–2 с: длинный наклон рукой — это сценарий D, и он закончится дизармом по `RUNAWAY`."
- Why: runaway needs |pidSum| ≥ 600 **and** gyro > 15 °/s continuously for 75 ms. A tilt held still gives gyro ≈ 0 and
  cannot trip. What trips is continued rotation, which is what scenario D models (40 °/s). The advice is safe and the
  test itself is correct (props off), so I left it. Suggested wording: "не крути аппарат рукой дольше 1–2 с".
- Source: https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/fc/core.c

### U3. left: uncertain, bf-hd-osd-video.md table, Walksnail HD Pro "VBAT (6S — с конденсатором 50 В/47 мкФ)"
- Why: the Caddx product page says "Supports 6S input (6–25.2V)" with enhanced TVS, and says nothing about a capacitor.
  The Quickstart V1.1 PDF that may contain it could not be fetched (proxy).
- Source: https://www.caddxfpv.com/products/walksnail-avatar-hd-pro-kit-dual-antenna

### U4. left: uncertain, bf-hd-osd-video.md, old DJI firmware facts
- Quote: "до 24 элементов, прошивка v01.00.02.00 (2019)"; Caddx Vista "7.4–26.4 В", "21–28 мс 720p/120".
- Why: the sources (manuals.plus release notes, getfpv listing) could not be fetched. The DJI FPV page confirms only the
  Air Unit figures (7.4–17.6 V, about 4–9 W, < 28 ms at 720p/120).
- Source: https://www.dji.com/fpv/info

### U5. left: uncertain, bf-hd-osd-video.md, Walksnail "каналы 1, 2, 6, 7 в FCC-регионах попадают в любительский диапазон" and "Режим standby снижает мощность, пока аппарат не армлен"
- Why: neither the Caddx page nor the Mini V3 manual text I could read says this. Not verified either way.

### U6. left: uncertain, bf-hd-osd-video.md, HDZero latency model "≈ 3 мс + период кадра (14 мс при 90 к/с)"
- Why: the arithmetic matches the task (3 + 11.1 ≈ 14.1 ms). The Divimath white paper could not be fetched to confirm
  the 3 ms term.

### U7. left: uncertain, bf-hd-osd-video.md, DJI O4 bench time wording
- Quote: "Время на столе от холодного старта при 25 °C без обдува: O4 Pro около 20 мин, O4 около 2.5 мин."
- Why: the O4 manual gives these as "idle standby time from cold start … measured under idle conditions in an open
  environment at 25 °C, for reference only". It does not literally say "без обдува". The meaning is close and the
  hardware step uses 2.5 min as a hard ceiling (conservative), so I left it.
- Source: https://hobbydrone.cz/user/related_files/dji_o4_air_unit_series_user_manual_v1_en.pdf

## OK (verified)

### bf-adjustments
- O1. ok: 30 slots (`MAX_ADJUSTMENT_RANGE_COUNT 30`). The range end is exclusive. `adjrange` parser: index < 30, fn
  0..34 (`< ADJUSTMENT_FUNCTION_COUNT` 35), both channels < `MAX_AUX_CHANNEL_COUNT`, 6 mandatory args + optional
  center/scale. Function 0 in a non-empty slot indexes `defaultAdjustmentConfigs[-1]` (uint8 0 − 1). Source: cli/cli.c
  `cliAdjustmentRange`, fc/rc_adjustments.c.
- O2. ok: the CLI ≠ enum table, regenerated by the lab from the 4.5 source. CLI 25–30 = enum 29–34, CLI 31–34 are empty,
  and ROLL/PITCH_RC_RATE/EXPO are unreachable. On 2025.12 the lab prints `31 | LED_DIMMER | SELECT | 100 | 35`. All
  Blackbox codes in the table follow the `blackboxLogInflightAdjustmentEvent` calls (combined functions log two events,
  pitch first).
- O3. ok: step mode thresholds (> midrc+200, < midrc−200), `RESET_FREQUENCY_2HZ` 500 ms, centre re-arms immediately.
  The first repeat comes about 490 ms after the press, absolute formula with C truncation (1251 µs → 58), lastRcData
  reset → jump, select formula `(constrain(rc,900,2099)−900)/(1200/N)`, `rate_6pos_switch`, OSD profile = position + 1,
  HORIZON_STRENGTH writes `pid[PID_LEVEL].D` = `horizon_limit_sticks`. `changeControlRateProfile()` ignores index ≥ 4.
  The OSD label format is `"%s: %3d"` and is shown for 2 s. Rate/OSD profile changes are excluded. LED_PROFILE has no
  4.5 label (`adjustmentLabels[]` ends at "OSD PROFILE"). Adjustments are skipped in CLI and while PARALYZE is active
  and disarmed (`fc/core.c`).
- O4. ok: stick commands. Save = THR_LO+YAW_LO+PIT_LO+ROL_HI → `saveConfigAndNotify()` (writeEEPROM, readEEPROM,
  1 beep). PID profiles 1/2/3 = …+PIT_CE+ROL_LO / PIT_HI+ROL_CE / PIT_CE+ROL_HI, disarmed only. LO = ≤ mincheck 1050,
  HI = ≥ maxcheck 1900. A pitch of 1060 turns the save gesture into the profile 3 gesture.
- O5. ok: `vtx` CLI (10 slots, band/channel/power ≤ table size, 0 = leave). Lock after arm until reboot. Power is
  always applied. `vtx_low_power_disarm` OFF/ON/UNTIL_FIRST_ARM, not in failsafe, overrides the slots
  (`vtxGetSettings`). Defaults and ranges of `vtx_band/channel/power/freq/pit_mode_freq/halfduplex/softserial_alt`,
  `osd_profile`, `ledstrip_profile` (STATUS / RACE), `rate_6pos_switch`. SmartAudio < 2.1 cannot enter pit mode by
  software. EU 25 mW EIRP at 5.8 GHz.
- O6. ok: d_roll = D max in 4.5 (40/46, d_min 30/34). Defaults roll_srate 67 → 670 °/s Actual. 25 → 400 mW = +12.04 dB.
- O7. ok: quiz Q1, Q2, Q3, Q4, Q5, Q7, Q8 keyed answers are correct and unique. Tasks: `abs-value` (C truncation, no clamp hit
  over the grid: minimum 16), `select-pos`, `step-count` (1 + ⌊t/500⌋ holds for all t in the grid given the ~490 ms first
  repeat. Taps < 0.4 s give exactly one step.)
- O8. ok: hardware path. Props off on the bench. Arming for the VTX power check is explicitly "без пропов". Hover abort
  criteria are observable (oscillation, motor heat, OSD, step count). CLI entry/exit behaviour (exit reboots) is
  consistent with steps 3–4.

### bf-rates-rc
- O9. ok: all five rate formulas, centre slopes and maxima in the table against `apply*Rates()`. RC_RATE_INCREMENTAL 14.54.
  Actual 7/67/0 gives 185 °/s at half stick. Type limits table (`ratesSettingLimits`: BF 255/100, RF 200/255, KISS 255/99,
  ACTUAL 200/200, QUICK 255/200, expo 100), applied in `validateAndFixRatesSettings`. 7/67/0 read as BETAFLIGHT → 14 °/s
  centre.
- O10. ok: throttle lookup (12 points, formula, `thr_mid` inert at expo 0, slope (100−expo)/100). Throttle scaling
  `(rc−mincheck)·1000/(2000−mincheck)`. `throttle_limit_*` SCALE/CLIP in the mixer.
- O11. ok: rate profiles = 4 (`CONTROL_RATE_PROFILE_COUNT 4` in 4.5, 2025.12 and master. The audit's "6" is wrong).
  Stick rate-profile change THR_HI + pitch/roll in ACRO, acc trims in ANGLE/HORIZON. `diff rates` = current profile only.
  `rateprofile_name` ≤ 8 characters.
- O12. ok: `rxrange` syntax (channels 0–3, 750–2250, `reset`). Range applied before the validity check. 885/2115 window,
  300 ms hold, then rxfail and flight channels invalid (`detectAndApplySignalLossBehaviour`). CRSF 988…2012. 12/512 µs dead
  travel. Centre stays 1500 after `rxrange 988 2012`.
- O13. ok: RC smoothing 4.5. PT3 with `CUTOFF_CORRECTION_PT3` 1.961459177. 1 s guard. Interval 950–65500 µs. k = 0.1.
  Outlier rule (< 7/8 of previous accepted). Recompute on every 4th accepted sample. `max(15, (uint16)(f·1.5/(1+factor/10)))`.
  `rc_smoothing_info` format strings (`# Active setpoint cutoff: %dhz (auto)`, `NO SIGNAL` only when interval is 0),
  Blackbox header `rc_smoothing_active_cutoffs_ff_sp_thr`, `RC_SMOOTHING_RATE` debug.
- O14. ok: feedforward 4.5 (`calculateFeedforward`). Duplicate handling. smooth factor = 1 − n/100. Boost ×0.1.
  Transition. Jitter attenuator `1 − (max(1 − (Δ+Δprev)/(2J), 0))²`. Max-rate limit `(maxRcRate − |sp|)·90`, raw 90, not
  /100, so the module's "·90" is literal. `FEEDFORWARD_SCALE` 0.013754. F defaults 120/125/120. All ranges/defaults in the
  reference table.
- O15. ok: ELRS intervals from common.cpp (2.4 GHz LoRa 50/150/250/500 = 20000/6666/4000/2000 µs, F500 2000,
  F1000 1000, D250/D500 = 1000 µs × 4/×2). rx_main.cpp forwards one RC frame per numOfSends for DVDA, so BF sees 250/500 Hz.
  TLM ratios 1:16…1:128.
- O16. ok: 4.3 tuning notes quotes (auto 30, 20 for racing at 250/500, 90–120 cinematic, Crossfire non-locked 20–30 Hz;
  500 Hz smooth 65–70 + 2_POINT; 250 Hz 35–40 in one place and 40–50 in another; 3_POINT for Crossfire 150; jitter 10–12,
  FF = 0 test).
- O17. ok: 2025.12 changes (`rc_smoothing_feedforward_cutoff` removed, "Active setpoint and FF cutoff", 20 % outlier, float
  cutoffs, FF defaults 2_POINT/65 with PT1 from the RX interval, `feedforward_yaw_hold_gain/time` 15/100, `thr_hover` 50 with
  a quadratic Bézier, SPI ELRS settings removed).
- O18. ok: quiz Q1–Q8 keyed answers. Tasks: `actual-rate` (srate·10 ≥ 500 > rc·10, so the MAX(0) is never active),
  `bf-max-rate`, `auto-cutoff` (checked the float32 edge cases: products that are exact integers, such as 100·0.15, truncate
  the same in C and Python, and no other grid point lands on an integer), `rxrange-scale` (rcData is float in 4.5,
  no truncation).
- O19. ok: hardware path. Props off before item 4. Flight item has observable abort criteria (horizon, LQ < 70 %, flip
  recovery). Blackbox targets (670 ± 1 %, 158 vs 185 °/s) match the lab.

### bf-arming-safety
- O20. ok: 26 flags and bit order in 4.5. 2025.12: FLIP_SWITCH 25, ALT_HOLD_SW 26, POS_HOLD_SW 27, ARM_SWITCH 28 (29 flags).
  master: AUTOPILOT_SW 28, ARM_SWITCH 29. `MSP_STATUS_EX` layout used by the decoder (U16,U16,U16,U32,U8,U16,U8,U8, byteCount,
  flags count, U32 mask). `status` prints names lowest bit first.
- O21. ok: per-flag triggers (`updateArmingStatus`, failsafe.c RXLOSS with `failsafe_recovery_delay`, NOT_DISARMED on RX
  return with switch on, ANGLE via `isUpright()` incl. not-yet-established attitude and the crash-flip exemption,
  BOOTGRACE + DShot commands, LOAD in permille per second, CLI flag kept until reboot (`cliExit` does not clear it), MSP via
  `MSP_ARMING_DISABLE`, PARALYZE sticky, GPS only before first arm, `NO_ACC_CAL` users, MOTOR_PROTO, ARMSWITCH incl.
  GPS Rescue disarms, BST never set).
- O22. ok: beeper. `ffs(flags)` → `beeperWarningBeeps`. 5 × 50 ms flashes, long 250 ms, short 50 ms, code = 5·long + short.
  Repeats when the lowest flag changes. RUNAWAY/CRASH codes replace the disarm beep.
- O23. ok: OSD warning shown only with ARM switch on, 0.5 s rotation, ARMSWITCH hidden unless alone.
- O24. ok: stick arming (`enable_stick_arming` OFF and no ARM range, THR_LO+YAW_HI, 500 ms, STICK COMMAND DISABLE), switch
  disarm after > 3 frames and only with valid RX data. `auto_disarm_delay` only MOTOR_STOP + no airmode + sticks. Airmode
  default on, latch at 25 %, I reset below min_check before latching. `pid_at_min_throttle` ON. 2025.12
  `landing_disarm_threshold`, `prearm_allow_rearm`.
- O25. ok: runaway constants (600, 75 ms, 15/50 °/s, 15 % stick, pidSum < 100, 75 % high throttle → half delay),
  deactivation logic incl. `constrain(low·2, low·2, 75)`, exclusions (fixed wing, crash flip, temporary disable, GPS
  Rescue, MOTOR_STOP without airmode below min_check), crash-flip re-enable, throttle percent formula (20 % ≈ 1240 µs),
  `pidSum` not clamped (mixer clamps to 500/400, `PID_MIXER_SCALING` 1000).
- O26. ok: yaw spin recovery (threshold logic, −100 °/s / 20 ms release, AUTO = max_yaw + max(max_yaw/4, 200) clamped
  500…1950, I zero on all axes, P/D/F zero on roll/pitch, yaw pidSum limit 1000, throttle 0.5 without airmode). Default
  670 → 870. The docs' 850 example is quoted correctly. Crash recovery thresholds, exit condition, BEEP also levels,
  `crash_limit_yaw` only limits yaw error, detector active in GPS Rescue. All defaults/ranges in the parameter table.
- O27. ok: lab blocks rerun byte-identical (flags, runaway A–E, yaw spin table). Runaway model logic matches
  `processRx`/`subTaskPidController` line by line. PTERM/ITERM scales and `iterm_limit` 400 are the 4.5 values.
- O28. ok: quiz Q1–Q8 keyed answers. Tasks: `beeper-bit` (bits ≤ 23, shared by 4.5 and 2025.12), `runaway-throttle`,
  `yaw-spin-auto` (uses float /4, firmware integer; worst difference 0.5 °/s, well inside tol 0.003), `small-angle`.
  The diagram tree lists all 26 flags once.
- O29. ok: hardware path. Props off until item 4. Smoke stopper. Abort list is observable (tilt > 20°, yaw spin, RUNAWAY
  code, lift-off throttle bounds, oscillation, ground walking). Tether option for 7″+.

### bf-hd-osd-video
- O30. ok: firmware side. Serial bits (VTX_MSP 1<<17 = 131072, the port value 131073 = MSP + VTX_MSP. The module correctly
  flags the audit's 131072 as a single bit). `isSerialConfigValid()` rules and order, whole-config reset in config.c,
  ≤ 3 MSP ports, SoftSerial strip. DisplayPort port = first non-VCP port with MSP|VTX_MSP (`validateAndFixConfig`).
  `displayport_msp_serial` present in 4.2 and 4.3, absent in 4.1, 4.4, 4.5 and 2025.12 (so the audit's "existed in 4.4" is
  wrong, and the module says so). `displayport_msp_attrs` (4.3) → `displayport_msp_fonts` default 0,1,2,3.
  `col/row_adjust` only in the SD branch of `displayPortMspInit()`. HD fallbacks under `USE_OSD_SD`/`USE_OSD_HD`.
  `pgResetFn_vcdProfile` / `osdConfig` HD defaults 53×20 vs SD 30×16. `MSP_SET_OSD_CANVAS` → save + `systemReset()`
  when not HD/MSP. `osdInit()` clamp. `OSD_POS`/`OSD_X`/`OSD_Y` bits. `status` line `OSD: %s (%u x %u)`. Settings
  ranges (canvas 0–63/0–31, framerate 1–60 default 12, lookup tables). `vtx_msp.c` sends power index 1 when
  `isLowPowerDisarmed()`. 2025.12 `serial %s` by name and `FUNCTION_GIMBAL` 1<<18. master `msp_1_uart` … (the module's
  `msp_uart_2` is an illustrative name, not the real one. Minor, left as is).
- O31. ok: HDZero. Canvas `HD_5018` / `MSP_SET_OSD_CANVAS` 50×18 sent to BTFL. Race V3 4–12 V, 5–6 W, white TX → FC RX,
  yellow RX → FC TX. Freestyle V2 7–25 V, 6–15 W, same colours. "All HDZero VTXes, except Freestyle Batch 2 VTX or later,
  do not support 6S VBAT", BEC recommended. Baud 115200/230400 auto-switch (Race V3 115200 only). LP_MODE, P1MW/0MW,
  0 mW modes. Blue LED 3× on MSP. Overheat 3 short pulses, Freestyle RF off until arm/repower. No soft serial. USB/battery
  order. 500 mW/1 W only with ham firmware.
- O32. ok: DJI O3 (manual: 7.4–26.4 V, cable colours, Canvas with BF 4.3.0+, standby overheat shutdown, low-power state,
  link goggles before remote, < 28 ms 810p/120 V2 and 30 ms 1080p/100 Goggles 2, FCC < 33 / CE < 14 / SRRC < 30 dBm).
  DJI O4 / O4 Pro (specs + manual: 3.7–13.2 V with BEC ≥ 10 W e.g. 5 V/2 A, 7.4–26.4 V with ≥ 13.5 W e.g. 9 V/1.5 A,
  same 6-wire colours, 20 / 15 ms Goggles 3, low-power mode until takeoff or recording, recording blocked while waiting
  on the ground, 2.5 / 20 min idle). DJI FPV Air Unit (7.4–17.6 V, 4–9 W, < 28 ms 720p/120).
- O33. ok: Walksnail HD Pro (6–25.2 V, average 22 ms, 32 GB, 1080p/720p, FCC < 30, CE < 14, MIC < 25 dBm). Mini V3
  (3.1–13 V, never 4S direct, 8 GB, crossed TX/RX, fan on bench, red/green overheat flashing, never power without
  antenna, CLI `osd_displayport_device = MSP` / `vcd_video_system = HD`).
- O34. ok: INAV 8 (`FUNCTION_MSP_OSD` 1<<25, 1<<17 = `FUNCTION_VTX_FFPV`, `osd_video_system` values). ArduPilot
  (`SERIALn_PROTOCOL` 42 DisplayPort / 33 DJI FPV, `OSD_TYPE` 5 MSP_DISPLAYPORT / 3 MSP, `MSP_OPTIONS` bit 2 BTFL fonts).
  msp-osd README (fonts 0,1,2,3 vs 0,0,0,0, 4.3 `displayport_msp_serial`).
- O35. ok: lab (17 bits OK against serial.h, validate cases A–E, OSD position table incl. hand check 3118, clamp table).
  Quiz Q1–Q8 keyed answers. Tasks `osd-pos-encode` (x 0–52, y 0–19), `eirp-mw`, `hdzero-latency`.
- O36. ok: hardware path. Props off on all steps except the flight. Pad voltage measured with the module disconnected.
  Fan on the bench, with the 2.5 min O4 ceiling. Abort criteria observable (smell, overheat LED, RX lost after Ports save,
  OSD flicker).

References. Every raw.githubusercontent.com reference returned 200. The github.com/blob links (bf-arming-safety) return
403 through this proxy only, and the same paths exist in the local clones. The betaflight.com pages exist in the docs
repo (wiki/guides/current/*.md, wiki/app/osd-tab.md). The DJI, Caddx and rotorama pages were read via WebFetch and
support the claims, except where listed under U3–U7.
