# theory-wave3 — independent fact-check

Scope: `content/ardupilot/ap-outputs.md`, `content/px4/px4-outputs-servos.md`, `content/ardupilot/ap-aux-tune.md`, `content/inav/inav-cli-backup.md`, their `content/quiz/<id>.json`, `content/tasks/<id>.json` and `scripts/diagrams/s6_<id>.py`.

Basis (all on disk; no firmware built or run): ArduPilot 4.7.2 (`/tmp/ardupilot-audit/copter472`, cited as `ap472/…`; `copter-4.7.2.pdef.json`, `copter-4.7.2-sitl-defaults.csv`; 4.6.3 tree `/tmp/ardupilot` = tag `Copter-4.6.3`, cited as `ap463/…`), PX4 1.17.0 (`/tmp/px4-audit-v1.17.0`, cited as `px4/…`; 1.16.2 and 1.15.4 trees for "changed in" claims), INAV 9.1.0 (`/tmp/inav-audit/inav9`, cited as `inav9/…`), INAV 8.0.1 (`/tmp/inavsrc/inav8`, `inav8/…`), INAV Configurator 9 (`/tmp/inav-audit/cfg9`, `cfg9/…`). Content files were not edited.

Two things were executed, both in a private scratchpad folder and neither is a firmware build: (a) ArduPilot's hwdef generator `chibios_hwdef.py` on `MatekH743/hwdef.dat` to read the generated `hwdef.h` (DMA assignment per timer); (b) the converter script printed in `inav-cli-backup.md`, on the module's own 91-line excerpt. All 22 task-bank formulas were evaluated over their full parameter grids against independent re-implementations of the firmware arithmetic.

Status: complete (2026-11-18).

Severity: **error** = contradicts the source / wrong number; **imprecise** = defensible but misleading or incomplete; **unverifiable** = could not be confirmed from a source on disk.

## Findings

### ap-outputs

| # | File:line | Statement | What the source says | Severity | Replacement (RU) |
|---|---|---|---|---|---|
| A1 | content/ardupilot/ap-outputs.md:169 (table row), :171 | «`BRD_SAFETY_MASK` \| 0 \| выходы, которые работают и при блокировке»; «Пока блокировка включена, PWM-выходы молчат» | The compiled default is 0 (ap472/libraries/AP_BoardConfig/AP_BoardConfig.cpp:244), but Copter replaces the default at start-up with "every output 1–14 that is not a motor": `safety_ignore_mask = (~motors->get_motor_mask()) & 0x3FFF; BoardConfig.set_default_safety_ignore_mask(...)` (ap472/ArduCopter/radio.cpp:82-87; AP_BoardConfig.cpp:486-490). The SITL default dump shows `BRD_SAFETY_MASK,16383`, not 0 (copter-4.7.2-sitl-defaults.csv). So on a Copter with a safety button all non-motor outputs (gimbal servos, gripper, parachute servo) are live while safety is on, unless the user writes 0 | error | Row: «\| `BRD_SAFETY_MASK` \| в Copter — все выходы 1–14, кроме моторных (у квадрокоптера с моторами на 1–4 это 16368); прошивка подставляет это умолчание при загрузке \| выходы, которые работают и при блокировке. По умолчанию это всё, что не мотор: сервы подвеса, захват, парашют двигаются и при включённой блокировке. Чтобы блокировка держала все выходы, запиши 0 явно \|». Line 171: «Пока блокировка включена, выходы, которых нет в `BRD_SAFETY_MASK`, молчат (в Copter по умолчанию это моторы): импульса PWM нет, кадры DShot не посылаются, арм запрещён сообщением `PreArm: Hardware safety switch`.» |
| A2 | content/ardupilot/ap-outputs.md:98 | «Исключения, для которых отказа нет: моторы, газ и скриптовые выходы» | `disabled_ok` = motors \|\| `should_e_stop()` (heli RSC 31/32, starter 69, throttle 70/73/74, boost 81, EngineRunEnable 30) \|\| NeoPixel 120–123 \|\| ProfiLED 129–132 \|\| Script 94–109 (ap472/libraries/AP_Arming/AP_Arming.cpp:1050-1057; SRV_Channel.cpp:326-352) | imprecise | «Исключения, для которых отказа нет: моторы, остальные функции, которые останавливает E-Stop (газ 70, 73, 74, 81, стартер 69, EngineRunEnable 30, роторы вертолёта 31 и 32), сами выходы лент (120–123, 129–132) и скриптовые выходы 94–109.» |
| A3 | content/ardupilot/ap-outputs.md:174, :148, :386 | digital servos tolerate 200–333 Hz; which ESC configurator versions work with passthrough; Mission Planner screen names; wiki pages | Author-marked as not from source; nothing on disk | unverifiable | — |

Confirmed against source (no change needed), priority items:

- **`SERVOn_FUNCTION` numbers.** Every number in the table matches `enum Function` (ap472/libraries/SRV_Channel/SRV_Channel.h:46-215): −1, 0, 1, 2/3, 4, 6–9, 10, 12–15, 19, 21, 24/25, 27, 28, 29, 33–40, 41, 45–47, 51–66, 70, 75/76, 77/78, 79/80, 82–85, 88, 94–109, 120–123, 129–132, 134–136, 138/139, 140–155, 160–179. Motor13–32 are absent from ap463 (`SRV_Channel.h` has no `k_motor13`). Reboot required: `@RebootRequired: True` (SRV_Channel.cpp:175).
- **Scaling formula.** `pwm_from_angle` / `pwm_from_range` (SRV_Channel.cpp:193-219): reverse first, constrain, float product, `uint16_t()` cast = truncation. Type table: angle 4500 for control surfaces, Script1–16 and RCINnScaled; range 100 for flap and fixed-wing throttle (SRV_Channel_aux.cpp:136-215). Exercise recomputed in float32: 1646, 1347, 1347, 1900, 1380, 1669 — all exact. Arming check `SERVOn_MIN is greater than SERVOn_TRIM` (AP_Arming.cpp:1036-1043). DShot outputs forced to 1000/2000 and trim 1000/1500 (SRV_Channel_aux.cpp:326-336).
- **Timer-group rules.** `get_disabled_channels` (ap472/libraries/AP_HAL_ChibiOS/RCOutput.cpp:632-657) + NeoPixel/ProfiLED added to the digital mask (SRV_Channel_aux.cpp:300-320) + pre-arm string `SERVO%u_FUNCTION=%u on disabled channel` (AP_Arming.cpp:1060). GPIO channel removed from its group at init, alarm takes the whole timer (RCOutput.cpp:117-134). Error strings `Chan %i to %i, %s: %s` with `failed to match clock speed` / `failed to allocate DMA` / `failed, no DMA` (RCOutput.cpp:933-957, 974, 1034, 1217). PWM group forced to motor rate, capped at 400 Hz, `set_default_rate` skips fast groups (RCOutput.cpp:444-518). Banner strings `PWM/OneS/OS125/Brush/DS150…DS1200/NeoP/ProfiLED` (ap472/libraries/AP_HAL/RCOutput.cpp:10-58). `@SYS/timers.txt` fields `CLK/MODE/FREQ/TGT` (RCOutput.cpp:2845-2870).
- **MatekH743 quote and plan.** `hwdef.dat` lines 145-157 match the quote character for character. Groups re-derived independently: TIM8 {1,2}, TIM5 {3,4,5,6}, TIM4 {7,8,9,10}, TIM15 {11,12}, TIM1 {13}. "All five timers have a DMA channel": confirmed from the generated `hwdef.h` (`STM32_TIM_TIM8/5/4/15/1_UP_DMA_STREAM` all defined). The three conflicts and the three strings are right: output 5 disabled by DShot on TIM5; NeoPixel on 8 disables 7 (and 9, 10 — output 9 has function 0 and is skipped by the check); `RELAY1_PIN=58, set SERVO9_FUNCTION=-1` (ap472/libraries/AP_Relay/AP_Relay.cpp:462-470). `MatekH743-bdshot` regrouping (1–2 TIM3, 3–4 TIM2, 5–6 TIM5, 7–10 TIM4; RC input moved to USART6) matches its `hwdef.dat`. Counts: 35 `*-bdshot` directories; 133 non-bdshot `hwdef.dat` files with a pin line carrying `BIDIR` — both exact by my count.
- **`SERVO_BLH_*`, DShot.** All defaults/ranges/values match `copter-4.7.2.pdef.json` and AP_BLHeli.cpp (POLES 14, TRATE 10, TMOUT 0; BDMASK only under `HAL_WITH_BIDIR_DSHOT`/IOMCU bidir, line 143). `SERVO_DSHOT_RATE`: 800 Hz floor loop (RCOutput.cpp:524-570). Reverse/3D commands only for ESC types 1–4, only disarmed, at 1 Hz (RCOutput_serial.cpp:155-186; SRV_Channel_aux.cpp:283). Passthrough handler installed only with AUTO or MASK, ignored when armed (AP_BLHeli.cpp:1290, 1411). No `SERVO_BLH_*` in the SITL default dump. Bitmask exercise: 15, 207, 768, 4288, {2,4}, {5,6,9}, 1–14 — all exact.
- **eRPM → RPM.** `… * 200 / motor_poles` in integers (AP_BLHeli.cpp:1544, 1568, 1594). 1470 → 21000 (350 Hz); with 12 poles 24500 (408.3 Hz), difference 58 Hz.
- **IOMCU.** Groups `{0x03, 0x0C, 0xF0}` (AP_IOMCU.h:190); DShot150–600 only (RCOutput.cpp:1232-1240); other MAIN outputs disabled under DShot (AP_IOMCU.cpp:1023-1030); `BRD_IO_DSHOT` only with `HAL_WITH_IO_MCU_DSHOT` (AP_BoardConfig.cpp:421-428); DShot on IOMCU in 4.5.0 (ReleaseNotes.txt:2169-2171); GPIO 101–108 (iofirmware.cpp:1341).
- **`BRD_SAFETY_DEFLT` / `BRD_SAFETYOPTION`.** 1 with `HAL_GPIO_PIN_SAFETY_IN` or IOMCU, else 0; option default 3; bits 0–3 as described (AP_BoardConfig.cpp:47-69, 282-287; pdef). `BRD_SAFETY_MASK` bitmask 14 outputs in ap463, 32 in 4.7.2.
- **Relay.** Six relays (AP_Relay.h:20), `FUNCTION` 0/1/3/4 (+2, 9 in Plane), `PIN` −1…1015, `DEFAULT` 0/1/2, `INVERTED`; aux options 28, 34, 35, 36, 66, 67, on only in HIGH (RC_Channel.h:179-228; RC_Channel.cpp:1518-1535); `DO_SET_RELAY` 0-based, 1 on / 0 off / else toggle (AP_ServoRelayEvents.cpp:70-92); manual set only with function 1 (AP_Relay.cpp:420-431); `DO_SET_SERVO` allowed functions and the `ServoRelayEvent: Channel %d is already in use` string (AP_ServoRelayEvents.cpp:40-56). `BRD_PWM_COUNT` removed in 4.2.0, `RELAYx_FUNCTION` in 4.5.0 (ReleaseNotes.txt:3341, 2196).
- **Quiz** 10/10: one defensible option each, `explain` true. **Tasks** 7/7: every variant matches an independent model (3508 variants in total, float32 arithmetic for the two servo tasks).

### px4-outputs-servos

| # | File:line | Statement | What the source says | Severity | Replacement (RU) |
|---|---|---|---|---|---|
| P1 | content/px4/px4-outputs-servos.md:93 | «…драйвер (`PWMOut::update_params`, то же в `px4io`) в момент, когда выходу впервые назначена функция» | The automatic values are written only when a function goes from unset to set **while the driver is running**: the block is guarded by `if (!_first_update_cycle)` (px4/src/drivers/pwm_out/PWMOut.cpp:221-273; px4io.cpp:699-745). Functions already present at boot (airframe file, saved parameters) get nothing. Conversely, a parameter file loaded into a clean firmware triggers it, and the driver then overwrites motor `MIN`/`MAX` and servo `DIS` that the file has just set | imprecise | «Не QGC, а драйвер (`PWMOut::update_params`, то же в `px4io`) — в тот момент, когда функция выхода при работающей прошивке меняется с Disabled на Motor или Servo. Первый проход после загрузки пропускается: функции, которые уже записаны airframe-файлом или сохранены до перезагрузки, автоматика не трогает. Обратная сторона: после загрузки файла параметров в чистую прошивку драйвер перезапишет `MIN`/`MAX` моторов и `DIS` серв своими числами — сверь их с файлом.» |
| P2 | content/px4/px4-outputs-servos.md:75, :114 | Pixhawk 6C Mini on fmu-v6c keeps `PWM_AUX_*`; case labels «FMU PWM OUT» / «I/O PWM OUT»; "documentation advises AUX for lower latency" | Hardware labelling and the board/doc pages were not traced; no contradiction found in `boards/px4/fmu-v6c` | unverifiable | — |
| P3 | content/px4/px4-outputs-servos.md:412 | Docs v1.17 Actuators page says the function list is «correct for v1.15» and lists 12 of 18 surface types | Not checked line by line against `docs/en/config/actuators.md` | unverifiable | — |

Confirmed against source, priority items:

- **Function ids.** `output_functions.yaml` (px4/src/lib/mixer_module/output_functions.yaml): 0, 1, 2, 101–112, 201–208, 301–306, 400, 401, 402–406, 407–412, 420–422, 430, 440, 450–453, 2000, 2032, 2064, 2070. IC Engine 450–453 and RPM Input 2070 exist in 1.16.2 and not in 1.15.4.
- **µs mapping.** `output_limit_calc_single` (mixer_module.cpp:535-576): NaN → DIS, REV flips sign, `interpolate` −1…1 → MIN…MAX, `lroundf`; the new bi-linear path for Servo 201–208, Landing Gear Wheel 440 and Gimbal 420–422 when `CENT` is 800…2200. `a = 425, b = 1475` in the worked example is exactly `math::interpolate` (px4/src/lib/mathlib/math/Functions.hpp:152-166). `CENTn`: default −1, absent in 1.16.2 and in `px4io/module.yaml` (no `center` key). MIN > MAX swapped silently (mixer_module.cpp:186-190).
- **`CA_SV_CSn_TRIM` reset.** Any `PWM_MAIN_CENT1…8` or `PWM_AUX_CENT1…8` ≠ −1 zeroes every non-zero trim and sends `CA_SV_CS{1}_TRIM ({2}) is reset to 0 as PWM CENTER is used` (px4/src/modules/control_allocator/VehicleActuatorEffectiveness/ActuatorEffectivenessControlSurfaces.cpp:79-135). Migration formula as in docs/en/config/actuators.md:674.
- **Automatic values.** Motor → MIN 1100 / MAX 1900; Servo → DIS 1500 and TIM 400 → 50 only if no channel of the group had a function (PWMOut.cpp:229-269).
- **`_TIMn` values per release.** 1.17.0 and 1.16.2: −5, −4, −3, −1, 50, 100, 200, 400. 1.15.4: the same plus **−2 = DShot1200** (px4-audit/src/drivers/pwm_out/module.yaml). IO: −1, 50, 100, 200, 400 only.
- **Bidirectional DShot on STM32.** `_bidi_timer_index = 0`; every other timer is skipped in `init_timer_config` and `init_timers_dma_up`; log line «Bidirectional DShot enabled, only one timer will be used» (px4/platforms/nuttx/src/px4/stm/stm32_common/dshot/dshot.c:126, 166, 201, 284-289); same in 1.16.2; no `DSHOT_BIDIR_EN` in 1.15.4. On fmu-v6x timer index 0 is Timer5 = AUX1–4, so AUX5–6 (Timer4) lose DShot. fmu-v6c: index 0 = Timer1 = first four outputs. Doc wording (STM32H7 first four FMU outputs on one timer; i.MXRT eight; KakuteH7 unsupported; eRPM only) — docs/en/peripherals/dshot.md:152-182.
- **`PWM_*_FAILn`.** Used only under `_armed.termination`; −1 → per-function default: Constant Min −1, Constant Max and Parachute +1, Servo 0, everything else NaN → DIS (mixer_module.cpp:497-501, 691-710; functions/*.hpp). Kill/lockdown → DIS for all outputs (mixer_module.cpp:491-495). Not an RC-loss reaction.
- **fmu-v6x quote and plan.** `timer_config.cpp` lines 59-77 match the quote. Groups re-derived: Timer5 AUX1–4 (`TIM0`, DMA), Timer4 AUX5–6 (`TIM1`, DMA), Timer12 AUX7–8 (`TIM2`, no DMA), Timer1 CAP1 (`TIM3`). IO: 2 + 2 + 4 (boards/px4/io-v2/src/timer_config.cpp:37-50). A camera-trigger channel allocates its whole timer in `IOTimerChanMode_Trigger`; another mode gets `-EBUSY` (io_timer.c:293-306). A group set to DShot on a timer without DMA is taken by neither driver (PWMOut.cpp:75-83; dshot.c:160-163).
- **Sign convention and airframes.** docs/en/config/actuators.md:216-240; the three airframe quotes match line for line (`3000_generic_wing` 17-23, `2100_standard_plane` 16-24, `13100_generic_vtol_tiltrotor` 36-41). Elevon inverse checked: [[−0.5, 0.5], [0.5, 0.5]]⁻¹ = [[−1, 1], [1, 1]].
- **States.** Prearm passes only functions with `allowPrearmControl()` (motors return false) (mixer_module.cpp:460; FunctionMotors.hpp:74); `COM_PREARM_MODE` 0 default, 2 = after 5 s (Commander.cpp:2053-2081); 0.5 s ramp on pwm_out and px4io, none on dshot (mixer_module.cpp:582; DShot.h:142).
- **`actuator_test`.** `set -m/-s/-f -v -t`, `iterate-motors` 0.15 for 400 ms, `iterate-servos` 0.3 (px4/src/systemcmds/actuator_test/actuator_test.cpp:29-40, 120-131); MAVLink path DENIED when armed / safety present and on / `COM_MOT_TEST_EN` ≠ 1, timeout capped at 3 s (Commander.cpp:1596-1647).
- **Exercise numbers** recomputed: 1679; 1509 / 1084 / 1900; 1441 / 1271; 1500 / 1509; 1475 / 1500; CENT 1509, 1665; masks 48 → 5, 6 and 22. DShot minimum 0.055 × 1999 → 109 (`static_cast<int>`, DShot.cpp:626).
- **Quiz** 10/10, **tasks** 5/5 (1914 variants).

### ap-aux-tune

| # | File:line | Statement | What the source says | Severity | Replacement (RU) |
|---|---|---|---|---|---|
| T1 | content/ardupilot/ap-aux-tune.md:102 | «`65`, `100`–`110` \| Отключают GPS и IMU «для проверки»» | Only 65 (GPS_DISABLE), 105 (GPS_DISABLE_YAW), 100, 101, 110 (KILL_IMU1/2/3) do that. The range also covers 102 Camera Mode Toggle, 103 EKF lane switch, 104 EKF yaw reset, 106 Disable Airspeed Use, **107 FW AutoTune** (which the module itself lists as the wing autotune switch), **108 QRTL**, 109 custom controller (ap472/libraries/RC_Channel/RC_Channel.h, `enum class AUX_FUNC`) | error | «\| `65`, `105`; `100`, `101`, `110` \| 65 отключает GPS, 105 — курс от GPS; 100, 101 и 110 «убивают» IMU 1, 2 и 3 — всё для проверки отказов \| Только для стенда и SITL \|» |
| T2 | content/ardupilot/ap-aux-tune.md:39, :376 | EdgeTX gives 988 / 1500 / 2012 µs | Taken from `link-edgetx`, author-marked as not rechecked; no EdgeTX source on disk | unverifiable | — |

Confirmed against source, priority items:

- **Aux option numbers.** Every number in the function table and in the danger table (except T1) matches `enum class AUX_FUNC` in 4.7.2. New since 4.6.3 (absent from ap463 `RC_Channel.h`, where `AUX_FUNCTION_MAX = 308`): 182, 183, 185, 186, 220, 308–315, 316; 163 renamed `MOUNT_LOCK` → `MOUNT_YAW_LOCK`. 41 → 154 conversion at boot (ap472/ArduCopter/system.cpp:67). Plane switch cases confirmed in ArduPlane/RC_Channel_Plane.cpp.
- **Thresholds, debounce.** 800 / 2200, 1200 / 1800 (RC_Channel.h:465-477), strict `<` / `>` and switch reverse only with `RC_OPTIONS` bit 7 (RC_Channel.cpp:2031-2049), 200 ms (RC_Channel.cpp:64, 634-656), six-position limits 1231/1361/1491/1621/1750 (RC_Channel.cpp:604-612). Scheduler lines `Copter.cpp:151`, `:161`, `Plane.cpp:72`, `:134` are exact. No aux reads in Copter radio failsafe (ArduCopter/RC_Channel_Copter.cpp:45-54; RC_Channels.cpp:173-178).
- **First-frame behaviour — traced.** `switch_state.current_position` and `debounce_position` start at −1 (RC_Channel.h:556-557; reset at RC_Channel.cpp:590-591). `init_aux()` (RC_Channel.cpp:2020-2028) only calls `init_aux_function`; it never writes `switch_state`. On the first successful `read_aux()` the state is pre-loaded only when `init_position_on_first_radio_read()` is true — `ARMDISARM` 153, `ARMDISARM_AIRMODE` 154, `ARM_EMERGENCY_STOP` 165, `PARACHUTE_RELEASE` 22 (RC_Channel.cpp:999-1005, 1030-1047). For every other function `debounce_completed()` sees position ≠ −1, stamps the edge, and fires on the first later call with ≥ 200 ms elapsed — including LOW. The claim is correct. The INIT/no-INIT lists agree with RC_Channel.cpp:663-833 and RC_Channel_Copter.cpp `init_aux_function`.
- **Exercise timeline** recomputed tick by tick: 200 (31 LOW), 200 (4 HIGH), 200 (28 MIDDLE), 1300 (153 LOW), 2300 (153 HIGH), 3300 (28 HIGH), 5300 (28 MIDDLE), 6300 (4 MIDDLE), 7300 (31 HIGH); the 4010–4190 pulse is dropped because at tick 4200 the position equals `current_position`; 153 and 22 do nothing on the first frame. Nine calls.
- **`TUNE`.** Formula: `norm_input_ignore_trim` (RC_Channel.cpp:458-466, reversal without `RC_OPTIONS`) + `linear_interpolate(min, max, n, −1, 1)` (ap472/ArduCopter/tuning.cpp:27-55). Every row of the `TUNE` table matches `defines.h` `enum tuning_func` and the `switch` in tuning.cpp, including `TUNE = 10` → `set_speed_NE_cms` (cm/s) while `WP_SPD` is m/s (pdef), 59 → `set_lean_angle_max_deg`, 60 → `set_speed_max_NE_ms`. Knob series recomputed: 0.25 / 0.05 / 0.15 / 0.2125 / 0.10, reversed 1750 → 0.0875, 0.135 at 1440 µs, step 3: 1316 µs and 0.5 / 0.135 = 3.7.
- **4.6.3 → 4.7.2.** Second knob (`rc_tuning2`, option 220, `TUNE2*`) absent in ap463; 220 is missing from the 4.7.2 `RCx_OPTION` value list (pdef); off condition `is_equal(min, max)` (tuning.cpp:41) vs `is_zero(min) && is_zero(max)` (ap463/ArduCopter/tuning.cpp:18); `PTUN` gained `NIn` (Log.cpp:438 vs ap463 Log.cpp:405); `TUNE = 10` is cm/s in both trees (ap463 `set_speed_xy`); Scripting 300–307 → 300–315; C++ `AP_Quicktune` only under `AP_QUICKTUNE_ENABLED = HAL_QUADPLANE_ENABLED` in ArduPlane/mode.h:16-17, no reference in ArduCopter; `error_threshold` is declared and has a parameter (AP_Tuning.h:51, AP_Tuning.cpp:61) and is read nowhere.
- **Danger claims.** E-stop: `SRV_Channels::set_emergency_stop(true)` on HIGH, nothing on MIDDLE, cleared on LOW (RC_Channel.cpp:1664-1676); auto-disarm delay halved (ArduCopter/motors.cpp:30-36); `Motors Emergency Stopped` and `Disarm Switch on` (AP_Arming.cpp:1671, 2083). Disarm by switch has no in-flight check — only GCS and rudder are guarded (AP_Arming_Copter.cpp:790-808, lines exact). 165: HIGH clear + arm, MIDDLE clear, LOW stop (RC_Channel.cpp:1905-1921). Parachute: enabled, not landed, above `CHUTE_ALT_MIN` when non-zero, strings `Parachute: Landed` / `Parachute: Too low` (ArduCopter/crash_check.cpp:348-374); `PARACHUTE_3POS` has no first-frame guard (comment at RC_Channel_Copter.cpp:127).
- **Plane `AP_Tuning`.** Parameters, defaults, 0.2 / 2 / 5 s selector timing, mid-point wait with a 0.02 dead zone, `range < 1.1` clamp, messages (ap472/libraries/AP_Tuning/AP_Tuning.cpp:18-61, 90-144, 164-225); sets 101–110 in metadata, 111–113 only in code (ArduPlane/tuning.h:87-99).
- VTX power formula `round(N·(pos+1)/6 − 1)` (AP_VideoTX.cpp:519) — the 1–2 / 3–4 / 5–6 split for three levels follows from `roundf` rounding half away from zero.
- **Quiz** 10/10, **tasks** 5/5 (3988 variants).

### inav-cli-backup

| # | File:line | Statement | What the source says | Severity | Replacement (RU) |
|---|---|---|---|---|---|
| N1 | content/inav/inav-cli-backup.md:167 | «Файл начинается с шапки `# INAV Backup`, `# Version: 8.0.1`, …» (in the list about the pre-flash auto-backup) | The pre-flash auto-backup starts with `# INAV Auto-Backup (pre-flash)` (cfg9/js/backup_restore.js:502); `# INAV Backup` is the header of the manual Backup Config button (backup_restore.js:203, 256). Both carry `# Version:` | imprecise | «Файл начинается с шапки: у авто-бэкапа перед прошивкой — `# INAV Auto-Backup (pre-flash)`, у бэкапа кнопкой Backup Config — `# INAV Backup`; дальше одинаково: `# Version: 8.0.1`, `# Board:`, `# Date:`, `# Craft:`.» |
| N2 | content/inav/inav-cli-backup.md:32 | «Пока CLI открыт … логические условия (`inav-ipf`) не выполняются» | Not traced in `programming/logic_condition.c`; the MSP-OSD part was confirmed in wave 2 | unverifiable | — |
| N3 | content/inav/inav-cli-backup.md:37, :75 | `bind_msp_rx` «с 9.1» | Only 8.0.1 and 9.1.0 trees are on disk: absent in 8.0.1, present in 9.1.0. `inav-intro.md:94` states 9.1 from a three-tag comparison that included 9.0.0 | unverifiable (9.0 vs 9.1) | — |
| N4 | content/inav/inav-cli-backup.md:126, :192 | Release notes 9.0 advise pasting in two parts; mrd-rc.com converter | Release pages not on disk | unverifiable | — |

**Central claim — decided: the module is right, the earlier course audit is wrong.** `printConfig()` starts with `dumpMask = DUMP_MASTER`. The enum values are separate bits: `DUMP_MASTER = 1<<0`, `DUMP_CONTROL_PROFILE = 1<<1`, `DUMP_BATTERY_PROFILE = 1<<2`, `DUMP_MIXER_PROFILE = 1<<3`, `DUMP_ALL = 1<<4` (inav9/src/main/fc/cli.c:338-345; inav8/src/main/fc/cli.c:330-337). Inside `if ((dumpMask & DUMP_MASTER) || (dumpMask & DUMP_ALL))`, after `dumpAllValues(MASTER_VALUE, …)`, the code branches on `if (dumpMask & DUMP_ALL)`; with plain `diff` that is false and the `else` branch runs — «dump just the current profiles»: `cliDumpControlProfile(getConfigProfile(), …)`, `cliDumpMixerProfile(getConfigMixerProfile(), …)`, `cliDumpBatteryProfile(getConfigBatteryProfile(), …)` (inav9 cli.c:4593-4624; inav8 cli.c:4547-4578). Identical in both releases. Plain `diff` = master **plus** the active control, mixer and battery profile; `diff all` adds `defaults noreboot` (only when `DUMP_ALL | DO_DIFF`, cli.c:4485-4491), all 3 + 2 + 3 profiles, three restore-selection lines, and suppresses `batch end` (`batchModeEnabled = false`, cli.c:4617).

Other confirmed items:

- **Command count.** `cmdTable[]`: 62 `CLI_COMMAND_DEF` in 9.1.0, 61 in 8.0.1; the only difference is `bind_msp_rx`. The module's table lists exactly those 62 names.
- **Scopes.** `master | control_profile | mixer_profile | battery_profile | all`, `showdefaults`; `rates` appears only in the help string (cli.c:4887-4890). `showdefaults` for `set` lines prints `#set name = <current value>` — `printValuePointer(value, valuePointer, 0)` is called with the current-value pointer in both places (cli.c:545-562).
- **Profile counts.** `MAX_PROFILE_COUNT 3` (fc/config.h:28), `MAX_MIXER_PROFILE_COUNT 2` or 1 (target/common.h:213, 221), battery 3.
- **677 settings.** Parsed `settings.yaml` 9.1.0: master 511, `PROFILE_VALUE` 91, `CONTROL_VALUE` 25, `EZ_TUNE_VALUE` 10 (= 126), mixer 12, battery 28; total 677. 8.0.1: 665 (505 / 90 / 23 / 10 / 9 / 28). Removed 8 → 9: exactly four names; added: sixteen.
- **Batch / save.** `cliSave` with an active batch and errors prints `N ERRORS WERE DETECTED - Please review and fix before continuing!` and `PLEASE FIX ERRORS THEN 'SAVE'`, resets the batch, returns without writing (cli.c:3838-3855, 3879-3897); `defaults` writes EEPROM itself and reboots unless `noreboot` (cli.c:3899-3915); `exit` reboots and clears motor-test outputs (cli.c:3643-3660).
- **Profile-select commands write EEPROM** when the index changes: `set…ProfileAndWriteEEPROM` → `writeEEPROM(); readEEPROM();` (inav9/src/main/fc/config.c:453-463, 484-494, 514-524). `control_profile 0` is ignored (`i >= 0`, cli.c:3756-3757).
- **Arming flags.** Bits 6–30 without 17, 24 flags; the enum is identical in 8.0.1 and 9.1.0 (fc/runtime_config.h); names are printed in bit order, hex only with `CLI_MINIMAL_VERBOSITY` (cli.c:4217-4259); `small_angle` default 25. Step 4 mask: 2^8 + 2^11 + 2^12 + 2^13 + 2^18 + 2^20 = 1325312 = 0x143900.
- **Calibration values in diff.** `acczero_*`, `accgain_*`, `magzero_*`, `maggain_*`, `gyro_zero_*`, `vbat_scale`, `current_meter_scale`, `current_meter_offset`, `stats_total_*` are all `MASTER_VALUE` settings.
- **Configurator.** `8_to_9.json`: `commandRenames` controlrate_profile → use_control_profile, `settingRenames` for the two others, `removed: []`, two warnings; `ahrs_acc_ignore_rate` default is 15 in both settings.yaml files, so the second warning is indeed unfounded. Version comes only from `/^#\s*Version:\s*(\S+)/m` (cfg9/js/migration/migration_handler.js:31). Folder `path.join(app.getPath('userData'), 'inav-backups')` (cfg9/js/main/main.js:429) vs `…/backups/` in inav9/docs/Backup and Restore.md:57-59. File name `UPDATE_inav_backup_…`, 10 kept (backup_restore.js:499, 510-532). Restore is offered only with a known target version, no major downgrade, and Full chip erase without the skipped-warning path (cfg9/tabs/firmware_flasher.js:592-605; firmware_flasher_restore.js:53-67). Restore skips comments, `save`, `exit`; error markers `### ERROR:`, `Invalid`, `Unknown command` (backup_restore.js:298-327). 7 → 8 column agrees with `7_to_8.json`.
- **Exercise.** The excerpt has 91 lines: 22 comments, 69 command lines (counted). All 28 `set` names exist in 8.0.1 `settings.yaml` in the sections where the excerpt puts them (`controlrate_profile` is a battery-profile setting). I ran the module's converter on the excerpt: stderr is byte-identical to the pasted output (lines 18, 19, 20, 42, 59, 82; «command lines out: 68, renamed: 4, dropped: 1, review: 1»); every `set` name of the output exists in 9.1.0. Classification 63 / 4 / 1 / 1 holds. Step 2: 8 + 6 + (5 + 5 + 3) + (15 + 14) + (3 + 5 + 1) + 3 + 1 = 69; plain `diff` 7 + 6 + 5 + 15 + 3 + 1 + `batch end` = 38; lost 32 = 23 + 5 + 3 + 1. `tasks` load: (120 × 2000 + 5000) / 1000 = 245 → 24.5 % (cli.c:4344-4352).
- **Quiz** 10/10, **tasks** 5/5 (90027 variants; the `arming-top-bit` values use only valid flag bits).

## Counts per module

Exact tallies (counted): findings by severity, quiz questions, task items, task variants. "Statements confirmed" is an **estimate** of distinct factual claims I compared with a source line; it is not a count of sentences.

| Module | error | imprecise | unverifiable | Quiz checked / defective | Task items checked / defective | Task variants evaluated | Statements confirmed (estimate) |
|---|---|---|---|---|---|---|---|
| ap-outputs | 1 | 1 | 1 | 10 / 0 | 7 / 0 | 3508 | ≈ 150 |
| px4-outputs-servos | 0 | 1 | 2 | 10 / 0 | 5 / 0 | 1914 | ≈ 130 |
| ap-aux-tune | 1 | 0 | 1 | 10 / 0 | 5 / 0 | 3988 | ≈ 170 |
| inav-cli-backup | 0 | 1 | 3 | 10 / 0 | 5 / 0 | 90027 | ≈ 160 |
| **Total** | **2** | **3** | **7** | **40 / 0** | **22 / 0** | **99437** | ≈ 610 |

«Эталон для самопроверки» blocks: every stated correct answer and every "typical wrong result → cause" was recomputed (ap-outputs: 1647, 1381, 1670, 1536, 10500; px4: 1475, 1934, 1509, 1679, "48 → 4 and 5"; ap-aux-tune: 1230 / 2250 / 3220, 0.20, 0.135; inav: 14, 31, 37). None is wrong.

## Rows the migration tables should gain

Each row was verified in the old and the new tree.

**`ap-intro` (4.6.3 → 4.7.2)**

| Было (4.6) | Стало (4.7) | Что изменилось | С какого релиза | Evidence |
|---|---|---|---|---|
| `SERVOn_FUNCTION` до 155 (моторы 33–40, 82–85) | добавлены 160–179 — Motor13…Motor32 | до 32 моторов | 4.7.0 | ap463 SRV_Channel.h has no `k_motor13`; ap472 SRV_Channel.h; ReleaseNotes.txt:704 |
| `BRD_SAFETY_MASK`: биты 0–13 (выходы 1–14) | биты 0–31 (выходы 1–32) | маска расширена; умолчание Copter по-прежнему «все немоторные из 1–14» | 4.7.0 | ap463 AP_BoardConfig.cpp:209 vs ap472 pdef; radio.cpp:86 |
| — | `MOT_IDLE_SEC` (0…5 с) | задержка после выхода на холостой ход для запуска ESC | 4.7.0 | absent in ap463 AP_Motors; ReleaseNotes.txt:694 |
| одна крутилка: `RCx_OPTION = 219`, `TUNE`, `TUNE_MIN/MAX` | + вторая: `RCx_OPTION = 220`, `TUNE2`, `TUNE2_MIN/MAX` | 220 нет в списке значений `RCx_OPTION` — вводится числом | 4.7.0 | ap463 tuning.cpp / RC_Channel.h vs ap472 |
| подстройка `TUNE` выключена, только если `TUNE_MIN` и `TUNE_MAX` оба равны 0 | выключена, когда `TUNE_MIN` = `TUNE_MAX` | условие | 4.7.0 | ap463 tuning.cpp:18 vs ap472 tuning.cpp:41 |
| `TUNE` до 59 | + 60 — `LOIT_SPEED_MS` (м/с); `TUNE = 10` по-прежнему задаёт скорость в **см/с**, хотя `WP_SPD` стал в м/с | новое значение; единица 10 не менялась | 4.7.0 | defines.h in both trees; tuning.cpp |
| лог `PTUN`: `Param, TunVal, TunMin, TunMax` | + поле `NIn` | нормированный вход крутилки | 4.7.0 | Log.cpp:405 vs :438 |
| `RCx_OPTION` 300–307 (Scripting1–8) | 300–315 (Scripting1–16), 316 — остановить / перезапустить скрипты | больше скриптовых тумблеров | 4.7.0 | `AUX_FUNCTION_MAX` 308 → 317 |
| `RCx_OPTION = 163` Mount Lock | 163 Mount Yaw Lock; новые 185 Roll/Pitch Lock, 186 POI Lock | имя и две новые функции | 4.7.0 | RC_Channel.h both trees |
| — | `RCx_OPTION = 182` AHRS AutoTrim (Copter) | новая функция | 4.7.0 | RC_Channel.h both trees |

(`RCx_OPTION = 183` AUTOLAND is already in the table.)

**`px4-intro` (1.15 / 1.16 → 1.17)**

| Было (1.15 / 1.16) | Стало (1.17) | Что изменилось | С версии | Evidence |
|---|---|---|---|---|
| `PWM_*_TIMn` = −2 — DShot1200 (1.15) | значения нет: DShot только −5 / −4 / −3 (150 / 300 / 600) | DShot1200 убран | 1.16 | pwm_out/module.yaml in the three trees |
| — | `PWM_MAIN_CENTn`, `PWM_AUX_CENTn` (−1 или 800…2200 мкс; на выходах IO нет) | центр сервы в микросекундах, две прямые MIN–CENT–MAX | 1.17 | pwm_out/module.yaml 1.16.2 vs 1.17.0; mixer_module.cpp:548-566 |
| `CA_SV_CSn_TRIM` для любых серв | для PWM-серв заменён на `CENTn`; при любом `CENTn` ≠ −1 прошивка обнуляет все ненулевые `CA_SV_CSn_TRIM` | нейтраль переехала | 1.17 | ActuatorEffectivenessControlSurfaces.cpp:79-135; absent in 1.16.2 |
| функции выходов до 440 (1.15) | + 450–453 IC Engine Ignition / Throttle / Choke / Starter, + 2070 RPM Input | новые функции | 1.16 | output_functions.yaml in the three trees |
| `PD_GRIPPER_EN`, `PD_GRIPPER_TO` = 3 с (1.15) | `PD_GRIPPER_EN` удалён, `PD_GRIPPER_TO` = 1 с | захват включается назначением функции Gripper | 1.16 | payload_deliverer/module.yaml in the three trees |

**`inav-intro` (8.0.1 → 9.1.0)**

No new row is required: the three renames, the removal of `reboot_character`, the changed defaults, the `osd_snr_alarm` limit and `bind_msp_rx` are already there, and the `diff` scopes, the arming flags and the profile counts did not change between 8.0.1 and 9.1.0. Two optional notes, both verified in both trees: (1) `ahrs_acc_ignore_rate` is 15 in 8.0.1 and in 9.1.0 — the "20 → 15" warning shown by Configurator's `8_to_9.json` does not correspond to a firmware change; (2) the section sizes: master 505 → 511, control profile 123 → 126, mixer profile 9 → 12, battery profile 28 → 28.

## Contradictions in already-published modules

`grep` over all of `content/` (and `i18n/`, `data/` where relevant).

| # | File:line | Published statement | Source | Severity | Replacement (RU) |
|---|---|---|---|---|---|
| C1 | content/px4/px4-setup-scratch.md:36 | «`PWM_MAIN_TIMx` / `PWM_AUX_TIMx`: −5…−2 = DShot150…1200» | 1.17.0 and 1.16.2 offer only −5 DShot150, −4 DShot300, −3 DShot600; −2 = DShot1200 exists only in 1.15.4 (pwm_out/module.yaml) | error | «(`PWM_MAIN_TIMx` / `PWM_AUX_TIMx`: −5 / −4 / −3 = DShot150 / 300 / 600, −1 = OneShot, 50…400 = PWM, Гц; значение −2 = DShot1200 было только в 1.15 и убрано в 1.16)» |
| C2 | content/pages/setup-cards.html:121 | «−5…−2 DShot150…1200, −1 OneShot, 50…400 PWM (Гц)» | same | error | «−5 / −4 / −3 — DShot150 / 300 / 600, −1 OneShot, 50…400 PWM (Гц); DShot1200 (−2) был только в 1.15» |
| C3 | content/quiz/px4-setup-scratch.json:79 | distractor «Выходы MAIN через IO понимают только DShot1200» | The answer key is right (option 1); the distractor names a protocol that 1.17 does not have | imprecise | «Выходы MAIN через IO понимают только DShot150» |
| C4 | content/ardupilot/ap-lua.md:36, :76; content/quiz/ap-lua.json:47 (and the three `i18n/*/content/ardupilot/ap-lua.md`, `i18n/*/content/quiz/ap-lua.json` copies) | «Значения 300–307 — Scripting1…Scripting8»; «`RCx_OPTION = 300…307`»; «300–307 — Scripting1…8» | The module is marked 4.7.2; in 4.7.2 the range is 300–315, Scripting1…16 (ap472 RC_Channel.h); 300–307 is 4.6.3 | error | :36 «Значения 300–315 — Scripting1…Scripting16 (в 4.6 — только 300–307): зарезервированы для скриптов.» :76 «положение тумблера через `RCx_OPTION = 300…315`». Quiz explain: «300–315 — Scripting1…16 (в 4.6 — 300–307), зарезервированы для скриптов.» |
| C5 | content/px4/px4-setup-scratch.md:178; content/pages/setup-cards.html:123 | «Умолчания выходов мотора — min/max/disarmed = 1100/1900/1000 мкс» | Parameter defaults are 1000 / 2000 / 1000 (pwm_out/module.yaml); 1100 / 1900 are written by the driver when a Motor function is assigned at run time (PWMOut.cpp:261-268) | imprecise | «После назначения функции Motor драйвер сам записывает min/max = 1100/1900 мкс (умолчание параметров — 1000/2000); disarmed остаётся 1000 мкс.» |
| C6 | docs/reviews/inav-coverage-audit.md:133, :188, :694 (not under `content/`) | «plain `diff` = master only, without any profile» | Wrong for 8.0.1 and 9.1.0, see the central claim above | error (in a review document) | Annotate: «Superseded by theory-wave3: plain `diff` prints master plus the active control, mixer and battery profile (cli.c `printConfig`, `else` branch of `if (dumpMask & DUMP_ALL)`).» |

Searched and found consistent (no change needed):

- **INAV `diff` = master only / no profiles** — no occurrence anywhere in `content/`. `inav-setup-scratch`, `inav-setup-wing`, `inav-mixer-vtol`, `inav-intro` and `setup-cards.html` only say "save `diff all`". `inav-mixer-vtol` (the `mmix` listing stops at the first zero-throttle row, use −1.000 placeholders) agrees with the new module's excerpt. The matching Betaflight statement in `bf-cli.md:74-82` is about Betaflight and is not affected.
- **`PWM_*_FAILn` as an RC-loss reaction** — no occurrence; `px4-safety-return.md:40` ties `PWM_MAIN_FAILn` to flight termination.
- **`BRD_SAFETY_MASK` / `BRD_SAFETY_DEFLT`** — mentioned only in the new module (see A1).
- **`TUNE` units, knob tuning, `RCx_OPTION = 219`** — only in the new module.
- **DShot1200 in ArduPilot** (`MOT_PWM_TYPE = 7`, `ap-setup-scratch.md:126`, `setup-cards.html:95`) — correct for ArduPilot.
- `ap-intro.md:133` and `ap-setup-scratch.md:174` give the mode-switch limits as 1230 / 1360 / 1490 / 1620 / 1749; the new module gives 1231 / 1361 / 1491 / 1621 / 1750. Both describe the same code (`< 1231 … < 1750`): one lists the last value of a position, the other the first value of the next.
- `px4-intro.md:90-91` (`DSHOT_BIDIR_EN` from 1.16; `DSHOT_MIN` unit % → norm in 1.17), `px4-safety-return.md:46` (`COM_PREARM_MODE`), `ap-intro.md:63-65` (`PSC_*` renames used in the `TUNE` table), `inav-intro.md:62-94` (665 → 677 settings, renames, defaults), `inav-osd-hd.md:119` (`osd_snr_alarm`), `bf-cli.md:102, :116` (`noreboot` since 4.5.4), `ap-tuning.md:44, :77`, `ap-plane-tuning.md:38, :42` (options 107, 180, 17, QuikTune on 300) — all agree with the new modules.

## Safety review

- **A1 is the one safety-relevant error.** A reader who trusts «`BRD_SAFETY_MASK` = 0» believes nothing moves while the safety switch is on; by default in Copter every non-motor output on 1–14 does — including a parachute or gripper servo. Motors stay blocked, so this is not a prop-start hazard.
- No instruction in the four modules, followed literally, starts a motor with propellers on: every bench procedure states props off (`ap-outputs` «Пропеллеры сняты на всё время проверки», `px4-outputs-servos` «Пропеллеры сняты до конца процедуры», `ap-aux-tune` «Пропеллеры сняты до пункта 4», `inav-cli-backup` «Пропы сняты на всё время»), and the two commands that bypass arming checks are flagged (`actuator_test` from the console; INAV `motor`).
- `ap-aux-tune`: the E-stop "returns to LOW → motors restart", disarm-switch-in-flight and first-frame relay/RTL statements are all correct and are stated as warnings. T1 could send a reader to assign 107 or 108 thinking the whole 100–110 block is bench-only, or — worse — to treat 107/108 as "kills GPS/IMU"; the fix removes that.
- `px4-outputs-servos`: P1 matters on a parameter-file restore — a servo `DIS` or a motor `MIN` can silently differ from the file afterwards; the replacement says to compare.
- `inav-cli-backup`: no path to a lost failsafe was found; the module's own rule (never `save` over red lines, re-run `diff all` and compare) is what protects `failsafe_procedure`.

## Self-study wording

No collective or instructor-dependent wording was found in the four modules. Criteria a reader cannot check alone:

- `px4-outputs-servos.md:333` — «в крайних положениях серва не упирается (ток покоя не растёт)» needs an ammeter in the servo supply; it is placed under hardware criteria and explicitly excluded from the lab self-check, so it is acceptable as written.
- `inav-cli-backup.md:202, :350` — «все имена настроек проверены скриптом по дереву 8.0.1 / 9.1.0»: the checking script is not included, so the reader cannot repeat it (I repeated it; the claim holds). Not a pass criterion.
- `ap-aux-tune.md:150, :257` — the SITL numbers are attributed to a course audit on 4.6.3; the reader's criterion is the calculation, which is self-contained.

## What could not be checked

- Anything resting on release pages, wikis, forums or third-party tools (INAV 8.0/9.0 release notes, mrd-rc.com converter, ArduPilot wiki pages, EdgeTX output values, ESC configurator compatibility, QGC and Mission Planner screen names, Pixhawk case labels).
- Whether `bind_msp_rx` appeared in INAV 9.0 or 9.1 (no 9.0.0 tree).
- INAV: logic conditions being suspended while the CLI is open.
- PX4: the Pixhawk 6C Mini parameter-prefix exception; the two "docs lag behind code" remarks in the module's notes.
- Real CLI / SITL output: nothing was run on firmware; the SITL knob series of `ap-aux-tune` (measured by the course audit on 4.6.3) was reproduced only by calculation from the 4.7.2 code.
