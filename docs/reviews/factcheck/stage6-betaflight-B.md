# stage6-betaflight-B

Scope: content/betaflight/bf-led-buzzer.md, bf-servos-pwm.md, bf-gps-setup.md, bf-features-tour.md, their banks
(content/quiz/<id>.json, content/tasks/<id>.json) and diagram scripts (scripts/diagrams/s6_bf_led_buzzer.py,
s6_bf_servos_pwm.py, s6_bf_gps_setup.py, s6_bf_features_tour.py). Scope document: docs/reviews/betaflight-coverage-audit.md.
Where the audit, the betaflight.com docs and the source disagree, this review follows the source.

Basis:
- Betaflight 4.5-maintenance at 7dcc851 (version.h 4.5.6), 2025.12-maintenance at 5b88201, master at a12049c
  (2026.12), betaflight.com docs master 357535a, all local clones. 4.4-maintenance cli/settings.c, parameter_names.h
  and flight/pid.c were read on raw.githubusercontent.com. betaflight/config 4.5-config SPEEDYBEEF405V4/config.h was
  re-downloaded and is identical to the copy the lab used.
- Files read in the 4.5 tree, by module. LED/beeper: io/ledstrip.[ch], drivers/light_ws2811strip.[ch],
  drivers/stm32/light_ws2811strip_hal.c and _stdperiph.c, common/colorconversion.c, io/beeper.[ch], pg/beeper.c,
  drivers/sound_beeper.c, flight/failsafe.c, sensors/battery.c, drivers/stm32/dshot_bitbang.c, drivers/motor.c,
  drivers/timer_common.c, drivers/dshot_dpwm.h, drivers/stm32/pwm_output_dshot.c, fc/init.c, fc/tasks.c,
  config/config.c, fc/rc_adjustments.c, flight/mixer_init.c (areMotorsRunning), msp/msp_box.c, cli/cli.c (led, color,
  mode_color, beeper/beacon, aux, adjrange, timer, dma, resource), cli/settings.c. Servos: flight/servos.[ch],
  drivers/stm32/pwm_output.c, drivers/stm32/camera_control.c, target/common_pre.h, common_post.h,
  common_defaults_post.h, pg/motor.c, pg/rx_pwm.c, config/config.c (motor protocol fixes). GPS: io/gps.[ch],
  pg/gps.c, pg/gps_rescue.c, flight/gps_rescue.c, flight/imu.c, flight/position.c, fc/core.c, fc/rc_controls.c,
  io/serial.c, osd/osd_elements.c, telemetry/crsf.c, sensors/compass.c, msp/msp.c. Features: flight/pid.[ch],
  flight/pid_init.c, flight/mixer.c, flight/mixer_init.c, drivers/dshot.c, drivers/dshot_command.h, fc/core.c,
  fc/rc.c, fc/rc_modes.c, fc/rc_controls.c, osd/osd_warnings.c, io/rcdevice_cam.[ch], pg/rcdevice.c, pg/piniobox.c.
  In 2025.12 I read the same files where a difference is claimed (beeper, ledstrip, adjustments labels, gps, cli serial,
  mixer/mixer_init crashflip and dyn idle, pid.c launch default, msp_box, parameter_names.h). In master I read
  cli/settings.c (gps_uart, gps_baud, gps_ublox_enable_ana).
- Docs repo pages: LED-Strip-Functionality, Gps, GPS-Rescue, app/gps-tab, Mixer, Cloud-Build-API, Dynamic-Idle,
  3D-Setup, FPV-Camera-Control-Joystick-Emulation.
- Vendor data via WebFetch: Tower Pro MG996R datasheet (Cornell copy), u-blox MAX-M10S datasheet UBX-20035208, NEO-M8
  FW3 datasheet UBX-15031086, SAM-M10Q datasheet UBX-22013293, M10 ROM 5.00 release notes UBX-20050981, Adafruit
  NeoPixel Uberguide (power.md and best-practices.md). I did not read the M10 SPG 5.10 Interface Description or the
  MAX-M10S Integration manual (see U2).

Labs. I extracted every fenced block and reran it.
- bf-led-buzzer: the one `python` block is a contiguous excerpt of /tmp/claude-0/work/s6/bf-led-buzzer.led_lab.py.
  Rerun on the 4.5 + 2025.12 sources: output identical to bf-led-buzzer.lab_output.txt except the SVG path line.
  Every line of the 5 output blocks is present in the run (blocks are excerpts, block 6 is contiguous).
- bf-servos-pwm: the `python` block is a verbatim excerpt of the helper. Rerun on SPEEDYBEEF405V4/config.h +
  4.5 source: byte-identical to bf-servos-pwm.lab_output.txt. All output lines present (see B2 for one excerpt fix).
- bf-gps-setup: the 4 `python` blocks concatenated equal the helper gps_lab.py except for blank lines. Rerun with
  pygpsdata-MIXED.log (re-downloaded from pyubx2 master): byte-identical to bf-gps-setup.lab_output.txt; all lines of
  the 3 output blocks present (the real-capture block shows 5 of the 14 epochs, as the text says).
- bf-features-tour: the 3 `python` blocks concatenated differ from the helper lab.py only in comments; rerun output is
  byte-identical to bf-features-tour.lab_output.txt, and all three output blocks are contiguous substrings.
- Tasks: every formula re-derived from the code path and evaluated over the parameter grid. `max-leds` was checked
  against exact rational arithmetic over the whole grid (no floor() discrepancy).

`python3 scripts/validate_content.py` after the edits reports only "нет в манифесте" for the four modules (same as before
the edits). No diagram script was changed (all fixes are in Markdown/JSON captions and text), so no rebuild was needed.

Totals: 13 fixed, 8 left as uncertain, 47 ok (several ok entries group many checked values).

## Fixes

### B1. fixed: bf-servos-pwm.md, table "Три разных «ШИМ»", motor PWM row
- Quote: "`motor_pwm_rate` 480 Гц (200–32000), только при `use_unsynced_pwm`".
- Why: `motorPwmDevInit()` forces `useUnsyncedPwm = true` for PWM_TYPE_STANDARD (and BRUSHED), so motor_pwm_rate always
  applies to PWM; `validateAndFixConfig()` clamps it to 480 for PWM. The use_unsynced_pwm condition applies only to
  OneShot/Multishot. Changed to "для PWM всегда асинхронно и не выше 480 Гц, для OneShot/Multishot — только при
  `use_unsynced_pwm`".
- Source: https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/drivers/stm32/pwm_output.c ;
  https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/config/config.c

### B2. fixed: bf-servos-pwm.md, practice step 5 output excerpt
- Quote: "same servo, roll 2000 pitch 2000 -> servo3 1900 us (each rule clamped to +-400 = width/2, 800*60/100 = 480 …)".
- Why: the excerpt dropped the preceding run line that defines "same servo" (`servo 3 1100 1900 1480 60 -1`); without
  it the ±400, ×60 and 1480 numbers are unexplained (with the default servo they would be ±500, ×100, 1500). The maths
  is correct against `servoMixer()`/`servoTable()`. I inserted the missing line from the run (byte-identical).
- Source: module's lab run; https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/servos.c

### B3. fixed: bf-led-buzzer.md theory "Сборка, ресурс, таймер", driver file
- Quote: "Драйвер (`light_ws2811strip_hal.c`) забирает **таймер** пина и **поток DMA**…".
- Why: the HAL driver is built for F7/H7/G4; F4 (the most common FPV MCU) builds drivers/stm32/light_ws2811strip_stdperiph.c
  (mk/mcu/STM32F4.mk). Behaviour is the same (timerAllocate, dmaAllocate, prescaler/period for 800 kHz, silent false).
  Added "на F4 — `light_ws2811strip_stdperiph.c`".
- Source: https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/drivers/stm32/light_ws2811strip_stdperiph.c ;
  https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/mk/mcu/STM32F4.mk

### B4. fixed: bf-led-buzzer.md beeper table, BAT_LOW / BAT_CRIT_LOW
- Quote: "WARNING / CRITICAL по напряжению (`use_vbat_alerts`)".
- Why: `updateBatteryBeeperAlert()` uses `getBatteryState()`, which is `MAX(voltageState, consumptionState)`; with
  `use_consumption_alerts` and a capacity the mAh state also triggers it. `use_vbat_alerts` only gates the beeping
  (`batteryUpdateAlarms()`). Reworded accordingly.
- Source: https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/sensors/battery.c

### B5. fixed: bf-gps-setup.md, gps_ublox_mode removal
- Quote: "старый `diff` с ним даёт `Invalid name`".
- Why: removal confirmed (present in 4.4 settings.c line 1005, absent in 4.5). The CLI prints
  `###ERROR IN set: INVALID NAME: …###` (`ERROR_INVALID_NAME "INVALID NAME: %s"`). Changed the quoted text to `INVALID NAME`.
- Source: https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/cli/cli.c ;
  https://raw.githubusercontent.com/betaflight/betaflight/4.4-maintenance/src/main/cli/settings.c

### B6. fixed: bf-gps-setup.md, serial function mask (table, step 4 text, diagnostics)
- Quotes: "функция GPS (бит 2)", "`serial` с битом 2 на нужном UART".
- Why: `FUNCTION_GPS = (1 << 1)`, value 2, i.e. bit 1; "бит 2" would be value 4 (FRSKY telemetry). Changed to
  "значение 2 = бит 1" and "с функцией 2 (GPS)".
- Source: https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/io/serial.h

### B7. fixed: bf-gps-setup.md "Курс без компаса", diagnostics, quiz/bf-gps-setup.json Q8 explanation
- Quote: "Вес: 0 при 0 м/с, ∝ v² до 1 м/с, линейно до ×10 при 10 м/с; крен больше 12° и стик рыскания его гасят."
- Why: verified (GPS_COG_MIN_GROUNDSPEED 100 cm/s, numSat > GPS_MIN_SAT_COUNT, first >1 m/s re-initialises the
  quaternion from course, speed gain sq()/linear capped at 10, roll 12°, yaw-stick suppression). But
  `imuCalcGroundspeedGain()` also multiplies by `pitchSuppression = pitch/45`, zero when level or pitched back. This
  matters for students (no correction in a level hover or drift). Added the pitch factor to the theory, "нос наклонён
  вперёд" to the diagnostics, and to the quiz explanation (keyed answer unchanged and still correct).
- Source: https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/imu.c

### B8. fixed: bf-gps-setup.md, home point also set by the stick gyro calibration (bullet, table row, diagram caption)
- Quotes: "Дом `GPS_reset_home_position()` пишет на арме…"; caption "Дом записывается только при арме…".
- Why: `GPS_reset_home_position()` is also called from `processRcStickPositions()` on THR_LO+YAW_LO+PIT_LO+ROL_CE
  (gyro calibration, feature GPS on). With `gps_set_home_point_once = ON` this sets a home before arming that the
  first arm then keeps; with OFF the disarmed loop clears GPS_FIX_HOME again. It also turns NAV-SAT off. Added this
  to the bullet, the `gps_set_home_point_once` row and the caption.
- Source: https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/fc/rc_controls.c ;
  https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/io/gps.c

### B9. fixed: bf-gps-setup.md "Переход на реальное железо", props statement
- Quote: "Пропеллеры сняты на всех шагах."
- Why: step 6 is a flight; the blanket statement contradicts it. Changed to "на шагах 1–5". Step 5 (arm for home)
  stays props-off.
- Source: module text.

### B10. fixed: bf-gps-setup.md step 1 analysis, clock-per-system DOP increase
- Quote: "«часы на каждую систему» при 13–14 спутниках даёт на 5–20 % больше".
- Why: the pasted run shows up to 1.29 vs 1.05 (+23 %) HDOP at epoch 473621. Changed to "5–23 %".
- Source: module's lab run (rerun, identical).

### B11. fixed: bf-features-tour.md, Angle bullets, level_race_mode
- Quote: "`level_race_mode` (ON) — Angle только по крену…".
- Why: in the neighbouring bullets "(100)", "(50)" are defaults; the default of level_race_mode is false (pid.c), as the
  module's own table says. Changed to "`level_race_mode = ON` (по умолчанию OFF)". Behaviour (LEVEL_MODE_R, not in
  GPS Rescue) verified.
- Source: https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/pid.c

### B12. fixed: bf-features-tour.md step 2 analysis, where P alone reaches the 15 % cap
- Quote: "предел 15 % (`dyn_idle_max_increase`) — при недоборе 2000 об/мин."
- Why: P = err_rps · 50 · 0.00015 = 0.0075/rps, so 15 % needs 20 rps = 1200 rpm of deficit (motor at 1800 rpm); the
  module's own table shows 12.5 % at a 1000 rpm deficit and the cap already at 1500. Changed to "при недоборе 1200 об/мин
  (мотор на 1800)".
- Source: https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/mixer_init.c ; lab output.

### B13. fixed: bf-features-tour.md hardware step 5, DYN_IDLE debug channels
- Quote: "debug[0] (прибавка ×10000) меньше 1500".
- Why: in `calculateThrottleAndCurrentMotorEndpoints()` DEBUG_DYN_IDLE[0] is the P term only (clamped at −1000),
  [1] is I and [2] is D (each ×10000), [3] is min rps ×10. The total increase is not logged. Changed the criterion to
  "сумма debug[0] + debug[1] + debug[2] … меньше 1500". debug[3] ≥ 450 is correct (50 rps ×10 = 500).
- Source: https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/mixer.c

## Left: uncertain

### U1. left: uncertain, bf-features-tour.md front matter
- The other three modules have `added: 2026-11-14`; bf-features-tour has no `added:` line. Metadata only, not a factual
  error, and the publish step may fill it; I did not add it.

### U2. left: uncertain, bf-gps-setup.md, M10 interface claims
- Quote: "Описание интерфейса M10 из CFG-сообщений знает только CFG-CFG, CFG-RST и VALSET/VALGET/VALDEL".
- Why: I did not fetch the M10 SPG 5.10 Interface Description, so this is unverified. The module itself says in notes
  that it did not check whether M10 answers the CFG-GNSS poll or whether CFG-PM-OPERATEMODE = FULL equals CFG-PMS full
  power on ROM 5.00. The code path (Betaflight sends the CFG-GNSS poll to M10 too; it sends PM via VALSET to M9+) is
  verified.

### U3. left: uncertain, bf-gps-setup.md theory and task `gps-alt-trust`, gpsTrust simplification
- Quote: "смешивает GPS с баро с весом `gpsTrust = min(1/PDOP, 0.9)`".
- Why: correct as far as it goes (`100/pdop`, MIN 0.9, 0.3 without PDOP, 0 without 3D fix), but `calculateEstimatedAltitude()`
  then divides gpsTrust by the baro/GPS mismatch (in m × altitude_prefer_baro/100) when it exceeds 1. The task asks only
  for the variable after MIN and is correct. Suggested addition: "и уменьшает его при расхождении с баро больше 1 м".
- Source: https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/position.c

### U4. left: uncertain, bf-led-buzzer.md DShot beacon default
- Quote: "по умолчанию оба выключены (`DEFAULT_DSHOT_BEACON_OFF_FLAGS = DSHOT_BEACON_ALLOWED_MODES`)".
- Why: true for standard builds. With the RACE_PRO build option (`USE_RACE_PRO`) the default is only RX_LOST off, so
  RX_SET beacons by default. Suggested note "(в сборке RACE_PRO выключен только RX_LOST)".
- Source: https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/io/beeper.h

### U5. left: uncertain, bf-features-tour.md reference table, `pinio_box` default
- Quote: "`pinio_box` | 255,255,255,255".
- Why: the pg reset uses PINIOn_BOX from the board config, falling back to PERMANENT_ID_NONE (255). Some boards
  predefine PINIO1_BOX (e.g. 40 for VTX power), so "по умолчанию" is board-dependent. Suggested "255… (или из конфига платы)".
- Source: https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/pg/piniobox.c

### U6. left: uncertain, bf-gps-setup.md diagnostics wording
- Quote: "M10 на Betaflight 4.4 и старше работает плохо".
- Why: in Russian "старше" for versions can be read either way; the intent ("4.4 and earlier") is right (4.4 has no
  M10 branch; docs: auto config needs 4.5 for M10). Suggested "4.4 и более ранних".

### U7. left: uncertain, helper /tmp/claude-0/work/s6/bf-led-buzzer.led_lab.py argument parsing
- Why: `SRC2` is taken from `args[1]` before the `--svg` value is removed, so `led_lab.py <4.5> --svg x.svg` (without
  a 2025.12 tree) treats x.svg as the second source. The documented invocation (two trees + --svg) works and the
  outputs are unaffected. Not changed.

### U8. left: uncertain, bf-servos-pwm.md "2025.12: Добавлены `SERVO5_PIN`…`SERVO8_PIN` в конфигах плат"
- Why: what 2025.12 adds is support for these defines in `pgResetFn_servoConfig()` (servos.c); whether any board
  config uses them was not checked. Wording is close enough; suggested "поддержка `SERVO5_PIN`…`SERVO8_PIN`".
- Source: https://raw.githubusercontent.com/betaflight/betaflight/2025.12-maintenance/src/main/flight/servos.c

## OK (verified)

### bf-led-buzzer
- O1. ok: `parseLedStripConfig()`: `atoi` + 4-bit mask via CALCULATE_LED_XY (17 → 1), direction letters N E S W U D,
  base letters C F A L S G R (last one wins: "FCW" → C+W), overlays T Y O B V I W, chunk buffer 11 (≤ 10 chars, 11th
  char → parse error), colour ≥ 16 → 0, packing offsets 0/8/12/22/26. `generateLedConfig()` prints directions in
  NESWUD order, base function first. Lab lines 0x0C0401E1, 0x180401EE, 0x24040011 etc. recomputed.
- O2. ok: `updateLedCount()` stops at the first all-zero config (strip end); `ws2811UpdateStrip()` refreshes the tail
  black on a full refresh, so LEDs past the terminator go dark (quiz Q2).
- O3. ok: `getDirectionalModeColor()` returns the colour of the first set direction bit (i = 0…5 = N,E,S,W,U,D): "SE" →
  E = DARK_VIOLET; default ORIENTATION colours; flight-mode priority HEADFREE, MAG, HORIZON, ANGLE, else ORIENTATION;
  BARO unused; `mode_color 6` special colours (array 11, first 8 used), `mode_color 7 0 <ch>` (default THROTTLE = 3).
- O4. ok: `hsvToRgb24()` `sat = 255 − s`; default palette (WHITE 0,255,255, RED 0,0,255 …); `parseColor()` limits
  359/255/255 and zeroes the colour on error; hue 270 → rgb (127,0,255).
- O5. ok: STATUS layers: L/S hue `MAX(scaleRange(pct,0,100,−30,120),0)` (red ≤ 20 %, 0 % red not DEEP_PINK); battery %
  from mAh when capacity > 0, else from voltage between vbat min/max (no current sensor needed); A green/blue; W
  1.6 s cycle of 0.4 s windows, fixed colours, low-battery only with a voltage meter, NOT_PRESENT ≠ OK; B pattern
  0x8005 at 10 Hz = two 100 ms flashes per 1.5 s; R rate 5…50 Hz with throttle.
- O6. ok: profiles: BEACON 500 ms / 50 % → 2 flashes/s (docs say once per second); `BEACON_FAILSAFE_PERIOD_US = 250`
  used in `millis() %` → 250 ms, 4 flashes/s; trigger `BOXBEEPERON || failsafeIsActive()` (stage 2, set only when armed,
  held through FAILSAFE_LANDED → RX_LOSS_MONITORING until recovery); visual beeper option only in applySimpleProfile,
  while STATUS W LEDs follow `isBeeperOn()` when there are no warnings regardless of the option.
- O7. ok: brightness `v·b/100` integer in the driver; GRBW white = min(R,G,B); LEDLOW id 15 disables the strip;
  LED_PROFILE adjrange (CLI 30), 3 positions 900–1299/1300–1699/1700+, no beep, config not saved, `adjustmentLabels[]`
  ends at "OSD PROFILE" so index 34 reads past the array; 2025.12 has "LED PROFILE"/"LED DIMMER".
- O8. ok: timer conflict chain: `timerAllocate()` checks only the pin/channel owner; ledStripInit (init.c 774) after
  motorDevInit (545); DShot600 12 MHz × 20 ticks, DShot rewrites ARR every frame; bitbang AUTO rule (`isDshotBitbangActive`);
  `bbFindPacerTimer()` runs in bbPostInit (motorPostInit, init.c 992, after the LED), skips timers with foreign owners;
  F411 pacers TIM1 only; failure → `motorWriteNull`.
- O9. ok: beeper: `systemBeep()` `inverted ? on : !on`; BEEPER_INVERTED → inversion ON / od OFF, else OFF/ON; prefix,
  case-insensitive, first-match name lookup (`beeper -RX` → RX_LOST, `-ARM` → ARMING); off-flag silences the pin and the
  visual beeper but not the DShot beacon; ON_USB rule; BEEPER MUTE silences via `beeper()`; table rows (sequences
  50/50 for RX_LOST, SOS, arming GPS fix/no-fix patterns, ≥ gps_rescue_min_sats, GPS_STATUS fix and > 4, READY_BEEP
  once, ARMED with MOTOR_STOP without airmode, RC_SMOOTHING_INIT_FAIL armed); 24 conditions + ALL; masks
  0x00020013, 0x200, 0x00800000 recomputed.
- O10. ok: RX_LOST only with `!receivingRxData && (armed || WAS_EVER_ARMED)` (failsafe.c). DShot beacon: modes RX_LOST/RX_SET
  only, `!areMotorsRunning()` (armed or motor test), > 1.2 s after disarm, not while trying to arm, > 450/950 ms, checked
  only at beeper toggle times (hence ~0.52 s / ~1.0 s in the lab timeline); beacon tone 1–5. 2025.12: single 450 ms
  interval, RX_LOST beacon off with USB, RX_SET only with `failsafeIsReceivingRxData()`; CRASHFLIP rename,
  RC_SMOOTHING_INIT_FAIL removed (ARMING_GPS_NO_FIX bit 23 → 22); 2025.12 adds P/E/U base functions.
- O11. ok: settings table (all names, defaults, ranges in settings.c / pgResetFn_ledStripConfig), `feature LED_STRIP`
  forced off without USE_LED_STRIP and on for an unconfigured board, task rate 60 Hz, LED_STRIP_64 error on F411,
  box ids 13/15/37/52, `aux` uses permanentId, `adjrange` 6 mandatory args.
- O12. ok: vendor/docs: Adafruit 60 mA white / 20 mA rule, 300–500 Ω at the pixel end, 500–1000 µF ≥ 6.3 V, ground first
  and data last, 0.7·VDD, 74AHCT125/74HCT245 (best-practices page); BF docs Jewel 7 ~350 mA, separate BEC with common
  ground, diode to < 4.7 V.
- O13. ok: quiz Q1–Q8 keyed answers correct and unique; tasks `strip-current`, `max-leds` (exact over the grid),
  `led-packed`. Diagram data (380 mA layout sum, 572 mA at 30 %) matches the lab.
- O14. ok: hardware path: props off, current-limited battery, continuity before power, ammeter, arm without props for the
  RX_LOST test, abort criteria observable (smell, hot BEC, FC reset, 5 V < 4.75 V, motor twitch, hot motors).

### bf-servos-pwm
- O15. ok: `timerAllocate()` refuses only the same pin/channel; motorDevInit (545) before servoDevInit (717), so a servo on a
  motor timer rewrites PSC; F405 APB1 84 MHz → DShot600 PSC 6/ARR 19, servo PSC 83/ARR 19999 via
  `pwmOutConfig(…, PWM_TIMER_1MHZ, 1 MHz/servo_pwm_rate, servoCenterPulse)`.
- O16. ok: `servoDevInit()` breaks at the first empty ioTag (and at a failed timer allocation); `servo_center_pulse` is
  only the initial CCR, and `pwmOutConfig()` sets `*ccr = 0` right after.
- O17. ok: `servoConfigureOutput()` loads custom smix rules only for CUSTOM_AIRPLANE/CUSTOM_TRI; `servoTable()` calls
  `servoMixer()` only for plane-type mixers and GIMBAL, not QUADX; rule with rate 0 ends the table; min/max per rule
  as % of the target servo width minus width/2; servo rate and middle applied after the sum; reverse applied after
  the rule clamp; speed per call; BOXSERVO1–3 only with CUSTOMAIRPLANE.
- O18. ok: SERVO_TILT: `rate · attitude_decideg / 50` = rate/5 µs per degree; MIXTILT formula; no CAMSTAB → middle or
  forward channel; forward maps 1000…2000 to min…max; final constrain. 56 for a 90°/1000 µs servo, 1.8× overcompensation,
  saturation at ±25° with rate 100 (lab table recomputed). Quiz Q4 1620 µs.
- O19. ok: `writeServos()` output order (mixer servos, two gimbal servos, unwritten forwarded servos, then AUX via
  `forwardAuxChannelsToServos()` unconstrained); servos written every PID loop without an arm check (except tricopter
  tail with tri_unarmed_servo OFF).
- O20. ok: SpeedyBee F405 V4 4.5-config: pins and TIMER_PIN_MAP occurrences, `DEFAULT_DSHOT_BITBANG OFF`, SERVO1_PIN PB15
  (S9), CAMERA_CONTROL_PIN PB14 on TIM12 CH1. `USE_CAMERA_CONTROL` auto-defined with CAMERA_CONTROL_PIN and USE_VTX;
  `cameraControlInit()` (init.c 669) allocates TIM12 in HARDWARE_PWM (84 MHz/128), servoDevInit later rewrites the time
  base, so the camera loses its PWM; SOFTWARE_PWM available on F405, not on F411/F7/H7/G4.
- O21. ok: CLI: `servo` index + 5 numbers, 500 ≤ min ≤ middle ≤ max ≤ 2500, rate −100…100, forward < 18; `smix` limits
  (rule < 16, servo < 8, source < 14, rate ±100, speed ≤ 255, 0 ≤ min < max ≤ 100, box ≤ 3), `smix reset` clears
  reversals; `resource` NOTE text and that a different resource type is not cleared; `timer show` format, `timer list`
  "NOT IMPLEMENTED YET", `resource show all` includes timer/dma show.
- O22. ok: settings: servo_pwm_rate 50 (50–498), servo_center_pulse 1500 (750–2250), servo_lowpass_hz 0 (0–400),
  channel_forwarding_start 4 (4–18), tri_unarmed_servo ON, gimbal_mode NORMAL/MIXTILT, camera_control_mode, motor
  protocol table, dshot_bitbang(_timer) AUTO, input_filtering_mode OFF, MAX_SUPPORTED_SERVOS 8 / 1.
- O23. ok: USE_SERVOS and USE_RX_PPM/USE_RX_PWM inside `#if !defined(CLOUD_BUILD) && !defined(SITL)` in common_pre.h; Cloud
  Build API lists SERVOS and WING (WING = ADVANCED_TPA + SERVOS, USE_WING only in 2025.12); docs Mixer page uses the
  old `servo … angleMin angleMax …` syntax, `servo_lowpass_freq/_enable`, the old servo numbering, "1 ms per loop" and
  per-profile reversal; 4.5 `servoIndex_e` 2 FLAPS … 7 THROTTLE.
- O24. ok: DShot600 bit/frame times; bidir F4/G4 DShot600 → DShot300 in config.c (below the overclock level); INAV
  servo_pwm_rate 50–498 and its "330 Hz" description; ArduPilot SERVOn_FUNCTION 7/8, MNT1_TYPE 1, SERVO_RATE 25–400.
- O25. ok: MG996R datasheet: running 500–900 mA (6 V), stall 2.5 A (6 V).
- O26. ok: quiz Q1–Q8 keyed answers correct and unique; tasks `tilt-rate`, `tilt-pulse` (C truncation), `elevon`
  (no ±500 clamp over the grid), `smix-speed` (ceil(d/s) loops).
- O27. ok: hardware path: props off, smoke stopper, separate BEC with common ground, measured stall current, pulse checked
  with a tester/scope, motors checked after `resource`, abort criteria observable, optional flight with abort criteria.

### bf-gps-setup
- O28. ok: `gpsConfigureUblox()`: 3 MON-VER per baud at 330 ms; baud order from the user index towards 115200, then 9600
  upwards; hwVersion 00080000/000A0000; PUBX,41 then 3 × 330 = 990 ms; CONFIGURE 1 s then steps ≥ 110 ms; 22 positions
  for M8, 16 for M9+; acquire model, SBAS, PM (VALSET for M9+, CFG-PMS for M8), NAV-PVT 1, NAV-SAT 5, NAV-DOP off for M7+,
  user rate, CFG-GNSS step only if SBAS NONE or Galileo ON; VALSET in UBX_VAL_LAYER_RAM; M8 NAV5 pDOP 250.
- O29. ok: flight model sent at the first STATE(GPS_FIX) in RECEIVING_DATA (not at arming); 2.5 s NAV timeout →
  LOST_COMMUNICATION → DETECT_BAUD; `gps_sbas_mode` default SBAS_NONE (docs: AUTO); `gps_auto_baud` read only by cli.c
  status and MSP; NMEA skips detection; gps_ublox_mode in 4.4 only.
- O30. ok: Rescue low sats uses `GPS_MIN_SAT_COUNT` 4 (10 s cumulative in flight, 2 s for availability; docs: half of
  min_sats); arming flag GPS when Rescue is configured (procedure or mode), cleared by fix + minSats, WAS_EVER_ARMED,
  allow_arming_without_fix or crash-flip mode; home only with fix and numSat ≥ minSats, GPS_FIX_HOME cleared while
  disarmed when set_home_point_once OFF; NAV-SAT rate 0 on arming; arming beeps.
- O31. ok: settings table names/defaults/ranges (gps_* in pg/gps.c and settings.c, gps_rescue_min_sats 8 5–50,
  allow_arming_without_fix OFF, use_mag ON, mag_hardware list, mag_align ±3600, mag_declination 0–3599 in 4.5,
  osd_gps_sats_show_pdop), `serial` GPS baud 9600–115200 (2025.12 230400), SoftSerial clamp to 19200, `status` line format
  with two spaces after `=`; 2025.12 VIRTUAL provider and ap_* replacing gps_rescue_landing_alt/throttle_*; master
  gps_uart/gps_baud/gps_ublox_enable_ana; pos_hold only in 2025.12.
- O32. ok: PDOP: NAV-PVT pDOP stored, hdop not updated with NAV-DOP off; MSP sends pdop ("hdop in 4.4 and earlier");
  OSD sats element NC/critical (< 4 or no fix)/warning (< minSats with Rescue); speed only with fix; home arrow `-`
  without fix/home, over-home symbol at 0; CRSF GPS frame and WAIT flight mode conditions; compass calibration
  15 s + 30 s; Rescue drops the mag after 30 s of not closing on home.
- O33. ok: vendor data: MAX-M10S (GPS+GAL+BDS B1I default, cold 27 s, 23–28 s other sets, hot 1 s, CEP 1.5 m, 3/10/6/18 Hz,
  1.76–3.6 V, 9.5 mA, −148/−167 dBm, ROM SPG 5.10, 9600 NMEA); NEO-M8N (GPS+GLO default, Galileo off, cold 26/29 s, CEP 2.5/2.0 m,
  5 Hz concurrent / 10 Hz single, 2.7–3.6 V, FW SPG 3.01); SAM-M10Q (GPS+GAL+GLO+BDS B1C, 50 × 50 mm ground plane, up to
  100 mA, SPG 5.10); ROM 5.00 notes (default without BDS/GLO, limitation 14 "balanced" power mode → CFG-PMS full power).
- O34. ok: docs quotes (Stationary before arming / Airborne after, SBAS default AUTO, 115200 packet loss, SPRacingF3 USB
  power, 45° tilt, ~20 sats, 10–20 / > 25 cm/s, PDOP ≈ 1.0, 30–50 m straight flight, compass ±10°, M10 needs 4.5).
  UART load arithmetic; quiz Q1–Q8 keyed answers correct and unique; tasks `gps-uart-load`, `gps-home-distance`
  (`GPS_distance_cm_bearing()` with 1.113195 cm per 1e-7°), `gps-alt-trust`. Hardware path props-off steps, abort
  criteria for the first flight (Rescue off).

### bf-features-tour
- O35. ok: `aux` format, permanentIds and visibility conditions in `initActiveBoxIds()` for every row (ANTI GRAVITY only with
  feature off and a non-zero gain, AIR MODE only with feature off, FLIP OVER AFTER CRASH only with a DShot protocol,
  USER1–4 only via pinio_box, MSP OVERRIDE with the mask, ACRO TRAINER with acc and USE_ACRO_TRAINER, etc.); feature
  defaults ANTI_GRAVITY + AIRMODE; 2025.12 ids 3 ALTHOLD, 11 POS HOLD, 29 "3D DISABLE", 55 CHIRP; box_user_N_name ≤ 16.
- O36. ok: PARALYZE sticky (armed only after the switch was off at > 5 s from boot), blocks arming, disables stick
  commands/adjustments/CMS while disarmed, never disarms.
- O37. ok: turtle: DShot commands 21/20 on arm/disarm (not with feature 3D), only when the mode has a range; state cleared
  only by disarm; ANGLE/GPS arming flags exempt; OSD texts; runaway check re-enabled on a turtle arm;
  `applyFlipOverAfterCrashModeToMotors()` maths (signs, yaw dominance, 30° diagonal, 0.15 dead zone in expo space,
  CRASH_FLIP_DEADBAND 20 → stop, motorRangeMax = motorOutputHigh) reproduced by the lab and task `crashflip-dshot`;
  crashflip settings MASTER_VALUE; 2025.12 crashflip_rate 0–250 (0 default, 30 with RACE_PRO), crashflip_auto_rearm,
  FLIP_SWITCH flag, crashflip_expo removed.
- O38. ok: launch control: `canUseLaunchControl()` conditions; airmode forced in the mixer while active; 100 °/s·2·x with
  ±0.5 clamp; angle window 10° → 5 °/s; Ki from launch_control_gain; D and FF off; yaw I limit 0/50 (NORMAL/FULL);
  PITCHONLY roll/yaw P and I zero, pitch I ≥ 0, front motors' pitch and throttle zeroed in launchControlMixer; trigger
  above throttle percent with I reset; allow_reset; OSD LAUNCH n blink 10 % before; 2025.12 default PITCHONLY.
- O39. ok: 3D: DShot split 48–1047/1048–2047 in `dshotInitEndpoints()`, idle offset in both halves; 3d_deadband_low/high,
  3d_neutral, 3d_limit_* read only in `analogInitEndpoints()` (and neutral as PWM idle pulse in init.c);
  3d_deadband_throttle window 1451–1549 for arming, direction hold in the deadband, I reset 250 ms, switch disarm in
  processRx; mode 29 semantics in rc.c; disabled functions (dyn idle branch, MOTOR_STOP, launch control, Rescue box,
  turtle commands); defaults 1406/1514/1460/50/1000/2000; dshotprog 10 + 12.
- O40. ok: acro trainer (`applyAcroTrainer()`: limit, gain/10, ±1000, I reset, lookahead window ∝ gyro up to 500 °/s, stick
  reversal releases, not in ANGLE/HORIZON/Rescue/crash recovery/launch).
- O41. ok: Angle/Horizon 4.5 (`pidLevel()`: target = limit·setpoint/maxRate, gain P/10, FF from F/100 with PT3 at
  1000/(2π·80 ms) ≈ 2 Hz, attitude PT3 50 Hz, earth-ref cross-feed; `calcHorizonLevelStrength()` with I/100 strength,
  D/100 stick limit (default 75), 135°, ignore_sticks, PT1 delay with MIN → slow rise, instant fall; PID_LEVEL defaults
  {50,75,75,50}); 4.4 → 4.5 renames and 4.4 values (level_limit 55, 10–90; angle_level_strength, horizon_transition,
  horizon_tilt_effect/expert_mode, roll/pitch_level_expo); 2025.12 angle_pitch_offset; EZ landing defaults and ranges.
- O42. ok: dynamic idle (`calculateThrottleAndCurrentMotorEndpoints()` and `mixerInitProfile()`: target n·100/60 rps,
  P 0.00015, I 0.01·dT with −0.1 floor, D 3·10⁻⁷·f_PID on the ~20 ms delayed rps, caps max/start increase ×0.001 chosen
  by `isAirmodeActivated()`, motorOutputLow = DSHOT_MIN_THROTTLE when active, throttle ≥ 0.01, target zeroed without
  DShot telemetry, not in 3D, profile values); dshot_idle_value 550; docs' "fixed 4 %" vs code 5 %; 2025.12 removal of
  dyn_idle_start_increase in favour of motor_idle ×0.0001. MOTOR_STOP conditions in `mixTable()`.
- O43. ok: anti-gravity / I-term relax defaults and ranges; I-term relax skipped in launch control and crash recovery.
- O44. ok: RunCam device: FUNCTION_RCDEVICE 16384, 6 attempts × 1000 ms, camera buttons 1/3 only disarmed, 2 any time,
  stick menu thresholds 1080/1350/1650/1920 and gestures, CMS gesture. Joystick emulation: settings defaults/ranges,
  47 kΩ, 150–600 Ω resistor (docs), stick gestures incl. THR_LO + PIT_HI → Up for 2000 ms.
- O45. ok: reference table names/defaults/ranges (settings.c, pid.c resetPidProfile, mixer_init.c, rc_controls.c,
  camera_control.c, pg/rcdevice.c); PID_PROFILE_COUNT 4 ("остальные три профиля").
- O46. ok: lab and banks: three blocks rerun identical; quiz Q1–Q8 keyed answers correct and unique; tasks `angle-target`
  (max(0) inactive over the grid), `horizon-strength` (no clamp active), `dyn-idle-p` (positive error over the grid),
  `crashflip-dshot` (always above the dead band). Diagram scripts reproduce the lab loops and the Horizon formula.
- O47. ok: hardware path: props off for the bench and the 3D check (3D props only after the four-point check), turtle on
  grass with props and people > 10 m, short pushes, explicit abort criteria; launch control and dynamic idle as
  flights with observable criteria.

References. Every raw.githubusercontent.com link in the four modules returned 200. The betaflight.com pages exist in
the docs repo. The Adafruit reference points to power.md; the resistor and connection-order claims are on the
best-practices page of the same guide (both support the text).
