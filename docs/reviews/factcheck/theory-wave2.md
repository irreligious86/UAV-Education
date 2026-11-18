# theory-wave2 — independent fact-check

Scope: `content/px4/px4-safety-return.md`, `content/inav/inav-osd-hd.md`, `content/ardupilot/ap-osd-video.md`, `content/inav/inav-mixer-vtol.md`, their `content/quiz/<id>.json`, `content/tasks/<id>.json` and `scripts/diagrams/s6_<id>.py`.

Basis (all on disk, nothing built or run): PX4 v1.17.0 (`/tmp/px4-audit-v1.17.0`, cited as `px4/…`; 1.16.2 and 1.15.4 for "changed in" claims), INAV 9.1.0 (`/tmp/inav-audit/inav9`, cited as `inav9/…`; Configurator `cfg9/…`), ArduPilot 4.7.2 (`/tmp/ardupilot-audit/copter472`, cited as `ap472/…`, plus `copter-4.7.2.pdef.json`, `plane-4.7.2.pdef.json`), Betaflight 2025.12.5 (`/tmp/bf-migrate/bf2025`). Content files were not edited.

Status: complete (2026-11-18). Web fetch was unavailable for the whole run, so every claim that rests only on release notes, wiki pages or forum threads is marked unverifiable.

Severity: **error** = contradicts the source / wrong number; **imprecise** = defensible but misleading or incomplete; **unverifiable** = could not be confirmed from a source on disk.

## Findings

### px4-safety-return

| # | File:line | Statement | What the source says | Severity | Replacement (RU) |
|---|---|---|---|---|---|
| P1 | content/tasks/px4-safety-return.json, task `time-to-action` (`answer`, `solution`) | Answer `L + min(T, x/4)`: x is counted from the end of the previous delay to the **last RC frame** | The Hold budget `_current_start_delay` keeps refilling at dt/4 on every update in which no delayed action is pending (px4/src/modules/commander/failsafe/framework.cpp:124-145) — that includes the `COM_RC_LOSS_T` seconds between the last frame and the flag. The budget is latched into `_current_delay` only when the new action is added (framework.cpp:346-349), i.e. at x + L. Real time = L + min(T, (x + L)/4). Example L = 2, T = 3, x = 2: bank says 2.5 s, code gives 3.0 s (20 % off, tol is 2 %); L = 0.5, T = 5, x = 2: 1.0 vs 1.125 s. Wrong whenever (x + L)/4 < T | error | `"answer": "L + min(T, (x + L)/4)"`. Solution: «Запас задержки восстанавливается вчетверо медленнее, чем тратится, и продолжает восстанавливаться, пока флаг потери не поднят — то есть ещё `COM_RC_LOSS_T` после последнего кадра. К моменту флага доступно min(`COM_FAIL_ACT_T`, (x + `COM_RC_LOSS_T`)/4). Время от последнего кадра = `COM_RC_LOSS_T` + min(`COM_FAIL_ACT_T`, (x + `COM_RC_LOSS_T`)/4).» |
| P2 | content/px4/px4-safety-return.md:249, :266, :298 | «270 — по логу аппарат в 35 м от дома на высоте 40 м»; «Land сразу, в 35 м от дома» | Not a source contradiction, but it contradicts the module's own inputs (step 1: 5 m/s cruise, 3 m/s climb). Return starts at 205.5 s from 305 m / 25 m: climb 15 m = 5 s → 210.5 s; 59.5 s × 5 m/s = 297.5 m → **7.5 m** from home at t = 270, not 35 m. A reader recomputing "every moment" gets 7.5 m | imprecise | L249: «270 — по расчёту аппарат в 7.5 м от дома на высоте 40 м (205.5 с + 5 с набора; 59.5 с × 5 м/с = 297.5 м)». L266: «Land сразу, в 7.5 м от дома». L298 (эталон, п. 2): «…аппарат сядет не дома: на 270-й секунде до точки ещё 7.5 м, а при потере пульта на 30 с позже — уже полтораста метров». Alternative: keep 35 m and change the event at t = 200 to «аппарат в 332.5 м от дома» (then also 205.5 → d = 332.5 m in the table; all other numbers stay). |
| P3 | content/px4/px4-safety-return.md:170, :178, :180 | Cone «только мультиротор»; «Самолёт и VTOL всегда снижаются по кругу до `RTL_DESCEND_ALT`» | Both branches test `vehicle_type == VEHICLE_TYPE_ROTARY_WING` (px4/src/modules/navigator/rtl.cpp:472-473; rtl_direct.cpp:167,177). A VTOL in hover has that vehicle type, so it gets the cone and, with `RTL_LAND_DELAY` = 0 (the VTOL default), also skips the `RTL_DESCEND_ALT` stop | imprecise | L170: «…только мультиротор и VTOL в режиме висения, и только при `RTL_CONE_ANG` > 0». L180: «Самолёт и VTOL в самолётном режиме всегда снижаются по кругу до `RTL_DESCEND_ALT`; VTOL в висении ведёт себя как мультиротор.» |
| P4 | content/px4/px4-safety-return.md:33 | QGC 5.0 has one **Safety** page; newer builds split it into Failsafes and Return & Land | QGroundControl sources are not on disk | unverifiable | — |

Confirmed against source (no change needed), priority items:

- **Hold delay.** `COM_FAIL_ACT_T` 5 s, 0…25 (commander_params.c); delayed for every action except None/Hold/Disarm/Terminate (framework.cpp:488-499); during the delay takeover is `AlwaysModeSwitchOnly` (framework.cpp:497); delay is zeroed when `_selected_action > Hold`, Hold cannot run, or takeover is active (framework.cpp:655-670); threshold for "no stick takeover at all" is `COM_FAIL_ACT_T` ≤ 0.1 s (framework.cpp:345-355).
- **Quarter-rate refill.** framework.cpp:124-145 — minus dt while a delayed action is pending, plus dt/4 otherwise, capped at `COM_FAIL_ACT_T`.
- **Action order** None < Warn < Position < Altitude < Stabilized < Hold < RTL < Land < Descend < Disarm < Terminate — framework.h:52-70; worst wins — framework.cpp:463-481; fallback chain Hold → RTL → Land → Descend → Terminate — framework.cpp:545-618.
- **Takeover.** Sticks: multicopter only and gated by `COM_RC_OVERRIDE` bits 0/1 (Commander.cpp:2939-2968); geofence Hold and high-wind Hold are `AlwaysModeSwitchOnly` (failsafe.cpp:100, 322); Terminate/Disarm `Never`.
- **Clear conditions.** RC loss / GCS loss / geofence: `OnModeChangeOrDisarm`; Terminate: `Never` (failsafe.cpp:44-128).
- **Cone formula** re-derived from rtl.cpp:518-553: d ≤ `NAV_ACC_RAD` → 2·d; else if d ≤ `RTL_MIN_DIST` → min(d / tan(angle clamped 1…89°), `RTL_RETURN_ALT`); then max(…, 2·`NAV_ACC_RAD`); finally constrained to [current altitude, destination + `RTL_RETURN_ALT`]. The cone is applied **only** inside `RTL_MIN_DIST` — the module is right and the parameter text (rtl_params.c:92-104) agrees. `scripts/diagrams/s6_px4_safety_return.py:rtl_alt()` reproduces the function.
- **`RTL_LAND_DELAY` = 0 on a multicopter** → `MOVE_TO_LOITER` goes straight to `LAND` (rtl_direct.cpp:166-181, same in 1.16.2 rtl_direct.cpp:166-178); 1.15.4 always went through `LOITER_DOWN` (px4-audit/src/modules/navigator/rtl_direct.cpp:194).
- **Wind.** `wind_limit_exceeded` is raised only when `COM_WIND_MAX_ACT` > 1 (HealthAndArmingChecks/checks/windCheck.cpp:54-57).
- **Defaults per vehicle type**: every cell of the two matrices matches `PARAM_DEFINE_*` plus `ROMFS/px4fmu_common/init.d/rc.mc_defaults:18-21`, `rc.fw_defaults:16-45`, `rc.vtol_defaults:13-40`, `init.d-posix/rcS:166-190`, `airframes/4001_gz_x500:51`.
- **Version notes** (1.15.4 / 1.16.2 / 1.17.0 trees): `COM_ARM_BAT_MIN` 0 → −1 (1.16), `COM_RAM_MAX` new in 1.16, `COM_ARM_EKF_*` and `COM_POS_FS_DELAY` gone in 1.16, `COM_POS_LOW_ACT` / `COM_DLL_EXCEPT` / `RTL_TYPE` 4 new in 1.16, `COM_POSCTL_NAVL` gone in 1.17, `COM_FLTT_LOW_ACT` 3 → 0 in 1.17, `MIS_DIST_1WP` 900 → 10000 (1.16), `COM_OBL_RC_ACT` 2 "Manual" → "Stabilized" (1.16), `COM_RCL_EXCEPT` bits 3-4 new in 1.17 — all confirmed.
- **Exercise timeline** recomputed: 90 / 234 / 270 s thresholds; 60 s Hold immediately (geofence action is not delayable and not stick-overridable); 200.5 s delayed Hold (geofence Hold is `_selected_action == Hold`, not `> Hold`, so the delay is not cleared); 205.5 s RTL; ≈207.2 s ceiling crossed, geofence Hold < RTL; 234 s critical → RTL already selected; 270 s emergency → new caller id, delay cleared because `_selected_action` = RTL → Land at once. Six cone heights 3.0 / 5.0 / 25.0 / 40 / 40 / 32 and 11.7 m at 65° all reproduce.
- **Task bank**: `rtl-cone-alt`, `bat-time-to-critical`, `bat-return-radius` recomputed for 3+ variants each — formulas agree with the code/arithmetic; only `time-to-action` is wrong (P1).
- **Quiz**: 10/10 answers have exactly one defensible option and a true `explain`.


### inav-osd-hd

| # | File:line | Statement | What the source says | Severity | Replacement (RU) |
|---|---|---|---|---|---|
| I1 | content/inav/inav-osd-hd.md:176 | «До 9.0 настройка называлась `osd_pan_servo_pwm2centideg` и имела другой масштаб — старое число не переносится» | Configurator 9 migrates it as a pure rename with no value change: `"settingRenames": {"osd_pan_servo_pwm2centideg": "osd_pan_servo_range_decadegrees"}`, `"valueReplacements": {}` (cfg9/js/migration/8_to_9.json:10-15; inav9/docs/development/Backup Restore Architecture.md:153-154). The module also contradicts `content/inav/inav-intro.md:72` («имя; число то же (серва на 180° — 18, диапазон −36…36)»). 9.1.0 range −36…36, «180° → 18» (inav9/src/main/fc/settings.yaml:3790-3794) | error | «До 9.0 настройка называлась `osd_pan_servo_pwm2centideg`; при переносе меняется только имя, число остаётся тем же (серва на 180° — 18). В 9.1 поправка делится на фактический ход сервы `max − min`, поэтому при ходе не 1000 мкс проверь стрелку заново.» |
| I2 | content/tasks/inav-osd-hd.json, task `pan-servo` | Answer `(p - 1500) * r * 1000 / (hi - lo) / 100` as a float, question «на сколько градусов **прошивка считает** камеру повёрнутой» | `osdGetPanServoOffset()` returns `(int16_t)CENTIDEGREES_TO_DEGREES(...)` — the float is truncated toward zero to whole degrees (inav9/src/main/io/osd.c:1338-1352; common/maths.h:39). 393 of the 675 parameter combinations give a non-integer bank answer (e.g. r = 9, 1000–2000, p = 1575: bank 6.75, firmware 6), far outside tol 0.01 | error | Statement: «…На сколько целых градусов прошивка считает камеру повёрнутой (по модулю; прошивка отбрасывает дробную часть)?» `"answer": "int((p - 1500) * r * 1000 / (hi - lo) / 100)"`, `"tol": 0.001`. Solution: add «Результат приводится к целому отбрасыванием дробной части: 6.75 → 6°.» |
| I3 | content/inav/inav-osd-hd.md:251 (эталон, п. 2) | «Слова вышли 8226 и 8780 … — применена пятибитная формула `x \| (y << 5)`» | With the formula as written (no mask) `44 18 V` gives 44 + 18·32 + 8192 = **8812**; 8780 appears only if x is also masked to 5 bits as in `OSD_POS_SD` (`(x & 0x1F) \| ((y & 0x1F) << 5)`, inav9/src/main/io/osd.h:45): 12 + 576 + 8192. A reader who made the described mistake sees 8812 and does not recognise it | imprecise | «(2) Слова вышли 8226 и 8812 (или 8780, если столбец ещё и обрезан до 5 бит) либо расшифровка 0x2118 дала (24, 8) — применена пятибитная формула…» |
| I4 | content/inav/inav-osd-hd.md:57, :59 | `DJI_NATIVE` appeared in 8.0.1; wording of the 8.0.1 release notes (O4 + Goggles 2/3/N3/Integra firmware, «AVATAR gives the same»); 8.0.x notes promised to remove `enable_broken_o4_workaround` in INAV 9 | INAV 8.x firmware and the GitHub release pages are not on disk (web fetch unavailable). From 9.1.0 source only: the setting exists, default OFF (settings.yaml:3848-3853); `DJI_NATIVE` shares `HD_5320` with `AVATAR` and differs only in the direction-icon index (displayport_msp_osd.c:470-476; osd.c:1548; osd_hud.c:191) — that part is confirmed | unverifiable | — |
| I5 | content/inav/inav-osd-hd.md:58, :61 | DJI O3/O4 goggles firmware versions carrying the «INAV» OSD type; font file names/folders for HDZero, Walksnail, WTFOS | Author-marked as unverified; nothing on disk covers goggles firmware. Only inav9/docs/OSD.md:27 («DJI Goggles 2 and newer — 53 x 20 (HD) — YES (no custom fonts)») | unverifiable | — |
| I6 | content/inav/inav-osd-hd.md:119, :140, :156 | `osd_snr_alarm` max 99 in 8.0.1; three custom elements in 7.x; type numbers 4–7 shifted in 8.0 | No 7.x/8.x firmware on disk. 9.1.0: max 30 (settings.yaml:3447-3452), `MAX_CUSTOM_ELEMENTS 8` (io/osd/custom_elements.h:24). Consistent with `inav-intro.md:81` | unverifiable | — |

Settled from source (author-marked "unverified"): **Walksnail / WTFOS text resolution** — `AVATAR` 53×20, `DJIWTF` 60×22 (inav9/src/main/io/displayport_msp_osd.c:82-96, 448-476; docs/OSD.md:23-25). Note docs/OSD.md:26 lists «DJI O3 Goggles V2 + WTFOS» as 53×20, i.e. `DJIWTF` 60×22 is for the original Air Unit/Vista only — the module's table already says so.

Confirmed against source, priority items:

- **`osd_video_system`**: nine values in the order `AUTO, PAL, NTSC, HDZERO, DJIWTF, AVATAR, BF43COMPAT, BFHDCOMPAT, DJI_NATIVE` (settings.yaml:69-71), default `AUTO`; grids over MSP: AUTO/PAL/BF43COMPAT 30×16, NTSC 30×13, HDZERO 50×18, DJIWTF 60×22, AVATAR/BFHDCOMPAT/DJI_NATIVE 53×20 (displayport_msp_osd.c:448-476).
- **Serial function bits**: `FUNCTION_MSP_OSD` 1<<25 = 33554432, `FUNCTION_VTX_MSP` alias, `FUNCTION_DJI_HD_OSD` 1<<21, `FUNCTION_FRSKY_OSD` 1<<20 (io/serial.h:54-64); Ports labels «MSP DisplayPort» / «DJI FPV VTX» (cfg9/locale/en/messages.json:1488-1492); baud from `peripheral_baudrateIndex` (displayport_msp_osd.c:424-426), default 115200 (io/serial.c:120).
- **Init order** FrSky OSD → MSP DisplayPort → MAX7456 under `feature OSD` (fc/fc_init.c:559-582). **Link behaviour**: `vtxActive` set only on a received MSP command, 1 s timeout, nothing sent in CLI (displayport_msp_osd.c:73, 116-137, 503-511); full-frame interval default 10 ds, −1…600 (settings.yaml:3325-3331; displayport_msp_osd.c:257-270).
- **`osd_layout` CLI**: `<layout 0-3> <item 0-168> <col 0-63> <row 0-63> [V|H]`, visibility kept when omitted (fc/cli.c:3060-3146); packing `x | y<<6 | 0x2000` (io/osd.h:35-47); `OSD_ITEM_COUNT` = 169; custom elements are items 147-149 and 154-158 (io/osd.h enum).
- **Layout priority**: override (CMS / MSP 10 s) → failsafe layout 0 → ALT3 → ALT2 → ALT1 → logic operation 32 → 0 (io/osd.c:6027-6058; fc/fc_msp.c:3474; programming/logic_condition.h:64).
- **Alarms**: all 16 defaults, ranges and units match settings.yaml:3355-3501 and the comparisons in io/osd.c (711-712, 1892, 1925-1926, 2148-2149, 2445-2448, 2707, 2747, 2776-2790, 3462-3463, 3708, 3750, 3972).
- **Custom elements**: 8 elements × 3 parts, text buffer 16 (15 chars), upper-cased at draw time, CLI values 0-255, visibility 0-2, type numbers 0-28, widths = digits + 1 (io/osd/custom_elements.h:22-62; custom_elements.c:70-221; fc/cli.c:2770-2833).
- **`osd_row_shiftdown` is dead**: only the struct member and its default reference it (io/osd.h:454; io/osd.c:4338) — confirmed.
- **Exercise**: six elements outside 30×16, three outside 50×18, element 147 width 10; words 8258 / 9388 / 194 and decodes (24, 4, V), (21, 15, H); alarm values 121 / 2414 / 18 / 800 / 1112 / 3055 / 45 / 25 — all reproduce.
- **Task bank**: `pos-encode`, `pos-decode-row`, `canvas-fit`, `alt-alarm-m`, `airspeed-alarm` recomputed for 3+ variants each — correct; `pan-servo` wrong (I2). **Quiz**: 10/10 correct with one defensible option (Q7 «121 vs 122» relies on the module's round-down rule).
- **Cross-module**: grids and the system → value mapping agree with `bf-hd-osd-video.md:116-119`; the only conflict is I1 vs `inav-intro.md:72`.


### ap-osd-video

| # | File:line | Statement | What the source says | Severity | Replacement (RU) |
|---|---|---|---|---|---|
| A1 | content/ardupilot/ap-osd-video.md:58, :158, :339 | Tramp: «один провод на TX, 9600 бод» with no port option; half-duplex offered only as «попробуй» in diagnostics (author-marked unverified) | Settled from source. SmartAudio forces half-duplex itself: `set_options(... \| OPTION_HDPLEX \| OPTION_PULLDOWN_TX \| OPTION_PULLDOWN_RX)` (ap472/libraries/AP_VideoTX/AP_SmartAudio.cpp:55-58). The Tramp driver only clears RX inversion, sets 1 stop bit and opens 9600 baud — **no** `OPTION_HDPLEX` (AP_VideoTX/AP_Tramp.cpp:528-537). On one wire the FC therefore never hears the VTX reply unless the user sets `SERIALn_OPTIONS` bit 2 «HalfDuplex» = 4 (AP_SerialManager/AP_SerialManager.cpp:278) | imprecise | L58: «44 IRC Tramp — управление аналоговым VTX — один провод на TX и `SERIALn_OPTIONS = 4` (полудуплекс)». L158: «…44 (Tramp: один провод на TX, 9600 бод; полудуплекс прошивка сама не включает — задай `SERIALn_OPTIONS = 4`)…». L339: «для Tramp проверь `SERIALn_OPTIONS = 4`: без полудуплекса полётник не слышит ответ VTX». |
| A2 | content/ardupilot/ap-osd-video.md:91 | `OSD_FONT` «меняется на лету» | Code agrees: MAX7456 and SITL reload when `last_font != get_font_num()` (AP_OSD/AP_OSD_MAX7456.cpp:360-361; AP_OSD_SITL.cpp:172-173). But the parameter metadata says `@RebootRequired: True` (AP_OSD/AP_OSD.cpp:92-97), so a GCS will ask for a reboot | imprecise | «…меняется на лету (наземная станция при этом попросит перезагрузку — так помечен параметр, но MAX7456 перечитывает шрифт сразу).» |
| A3 | content/ardupilot/ap-osd-video.md:78-84, :250, :272 (п. 2), :316-318 | Per-system recipes: HDZero `OSDn_TXT_RES` 0/1 and «мусор» at 2; Walksnail 1; WTFOS 2; DJI O3/O4 `MSP_OPTIONS` 4 (8 for INAV font) and `OSDn_TXT_RES` 1; «Custom OSD» in DJI goggles; Mission Planner «HD Layout» | Author-marked. The 4.7.2 tree has no per-system table; the wiki and forum threads are not on disk. Source confirms only the mechanism: values 0/1/2 = 30×16 / 50×18 / 60×22 sent every cycle together with the font index (AP_OSD/AP_OSD_Screen.cpp:1071-1084; AP_OSD_MSP_DisplayPort.cpp:62-70), bits 2/3 select the BF / INAV symbol path (below), `fonts/HDFonts/{WalkSnail,WTFOS-DJI}` exist | unverifiable | — |

Settled from source (author-marked "unverified"):

- **`AUTO_SWITCH` timing** (`OSD_SW_METHOD` = 2). The thread ticks every 100 ms (AP_OSD.cpp:397-404); the debouncer makes the high-channel branch run on every second tick, and a step needs `now - last_switch_ms > 1000` with `last_switch_ms` reset to 0 while the channel is low (AP_OSD.cpp:586-601). Result: first step 0.1-0.2 s after the channel goes above `RCn_TRIM` (strictly greater), then one step every 1.2 s. In 3.0 s: three steps, 1 → 2 → 3 → 1. The module's numbers are right.
- **Extended link stats only in custom builds**: `AP_OSD_LINK_STATS_EXTENSIONS_ENABLED 0 // Disabled by default to save flash, enable via custom build server` (AP_OSD/AP_OSD_config.h:27; AP_OSD.h:55-62; Tools/scripts/build_options.py:143). Confirmed; `OSD_W_RSSI` default switches to −100 in such a build.
- **Tramp half-duplex** — see A1.

Confirmed against source, priority items:

- **`OSD_TYPE`** 0-5 names, default 0, reboot, enable flag (AP_OSD.cpp:46-52); hwdef overrides: 102 files set `HAL_OSD_TYPE_DEFAULT 1`, 14 set 5; 100 ms loop; `OSD_TYPE2` compatibility matrix (AP_OSD_MAX7456.h:44-56, AP_OSD_MSP.h:22-34, AP_OSD_MSP_DisplayPort.h:39-51, AP_OSD_SITL.h:46-58) and both pre-arm texts (AP_OSD.cpp:621-639).
- **Serial protocols** 29 / 32 / 33 / 37 / 42 / 44 (AP_SerialManager.h:68-83); baud default 115 for 32/33/42 via `set_default` (AP_SerialManager.cpp:557-561); SmartAudio 4800, Tramp 9600.
- **`MSP_OPTIONS`**: bit 0 read only by the DJI backend (`AP_MSP_Telem_DJI::is_scheduler_enabled`, AP_MSP/AP_MSP_Telem_DJI.cpp:42-46; DisplayPort and generic MSP return false — AP_MSP_Telem_DisplayPort.h:27, AP_MSP_Telem_Generic.h:27); bit 1 declared but never read (AP_MSP.h:62); bit 2 → BF symbol table at backend init, `BTFL` variant, decimal packing off (AP_OSD_MSP_DisplayPort.cpp:139, 155-163; AP_MSP_Telem_DisplayPort.cpp:28-41); bit 3 → INAV transcoding in `write()` and overrides bit 2 for table and variant (AP_OSD_MSP_DisplayPort.cpp:85-92). `MSP_OSD_NCELLS` auto = floor(V / 4.35 + 1) (AP_MSP_Telem_Backend.h:32; .cpp:163-166).
- **Screen switching**: method 0 — `abs(delta) > 200` from the stored value, next enabled screen over all six; method 1 — `min <= pwm && max > pwm`, highest matching index wins (re-simulated tick by tick, including the `break` on `previous_pwm_screen`), no match → no change; arm / disarm / failsafe screens 1-4 only if enabled, previous screen restored after failsafe (AP_OSD.cpp:520-617). Whole step-1 exercise reproduces: 1, 1, 2, 3, 3; 2100 stays on 2; screen 4 wins when enabled; 1 → 2 → 3 → 1 → 2; 1150 no / 1250 yes; arm 2, disarm 3 and held.
- **Elements**: 65 per screen, five behind the extended-link-stats flag (AP_OSD_Screen.cpp, 65 `AP_SUBGROUPINFO`); X 0-59, Y 0-21; `TXT_RES`, `FONT` 0-21; `MESSAGE` width 26, upper-cased, `OSD_MSG_TIME` 1-20 / 10 (AP_OSD.h:163; AP_OSD_Screen.cpp:1622-1672); `STATS` six rows (AP_OSD_Screen.cpp:2296-2307); 26 legacy-MSP item mappings (AP_MSP/AP_MSP.cpp).
- **Warnings**: all defaults and ranges (AP_OSD.cpp:115-230); blink is `value < threshold` (AP_OSD_Screen.cpp:1494-1497, 1536, 1595, 2526).
- **Cell count**: `(uint8_t)(max_battery_voltage * 0.2381 + 1)`, −1 → dashes (AP_OSD_Screen.cpp:1481-1489). 12.6 V → 4, 16.8 V → 5, 25.2 V → 7: the "N+1 at exactly 4.20 V per cell" claim is correct.
- **VTX**: parameter ranges, band list, `VTX_MAX_POWER` 800 (AP_VideoTX.cpp:31-76); power table 0 / 25 / 100 / 200 / 400 / 500 / 600 / 800 / 1000 and round-down at init (AP_VideoTX.cpp:110-121, 148-159); pit logic — bit 2 alone already toggles pit on disarm / off on arm, bits 0+1 leave power on after disarm (AP_VideoTX.cpp:346-355); 6-position boundaries 1231 / 1361 / 1491 / 1621 / 1750 (RC_Channel.cpp:604-616); option 94; pit not entered while armed (AP_VideoTX.cpp:540-544); message format (AP_VideoTX.cpp:497-502).
- **4.6 → 4.7**: 1029 `OSD*` / `MSP_*` / `VTX_*` parameters in both `copter-4.6.3.pdef.json` and `copter-4.7.2.pdef.json`, identical names, values, ranges, bitmasks.
- **Exercise steps 2-5** recomputed: 3 anchors + 1 `STATS` row outside 50×18; 5 anchors + 2 `MESSAGE` cells outside 30×16; masks 33 → bits 0, 5 and 49; three config errors (the HDZero one rests on A3); 300 → 200 mW, 23.0 dBm, 6.0 dB, `VTX_OPTIONS` 7.
- **Task bank**: all 8 tasks recomputed for 3+ variants each — correct. **Quiz**: 10/10 correct, one defensible option each.
- **Cross-module**: agrees with `bf-hd-osd-video.md:112-117`, `link-digital-video.md:46`, `ap-setup-scratch.md:194`; mW ↔ dBm agrees with `link-vtx.md:110-119`.


### inav-mixer-vtol

| # | File:line | Statement | What the source says | Severity | Replacement (RU) |
|---|---|---|---|---|---|
| M1 | content/inav/inav-mixer-vtol.md:244 (task), :333 (эталон), :314 | Step 1: throttle 1500, roll +100, pitch −60, **yaw 0** → «Моторы: 1359, 1462, 1538, 1641, 1440, 1560» | With the module's own formula and the Hex X rows (which do match cfg9/js/model.js:185-190) yaw 0 gives **1399, 1501, 1499, 1601, 1400, 1600** (`rpyMix` is `int16_t`, truncation toward zero — inav9/src/main/flight/mixer.c:531-541, 631). The printed numbers are exactly what the code gives for `axisPID[YAW]` = **+40** (term `−yaw·Y`): every motor is off by ∓40. A reader following the task as written cannot reach the reference | error | Keep the task, fix the reference (L333): «Моторы: 1399, 1501, 1499, 1601, 1400, 1600.» Alternative (keeps the numbers and exercises the yaw column): L244 «…`axisPID` крен +100, тангаж −60, рыскание +40: `motor = 1500 + trunc(pitch·P + roll·R − yaw·Y)`». |
| M2 | content/inav/inav-mixer-vtol.md:131 | «Настройки `output_mode` в 9.1.0 нет: в `settings.yaml` осталось только перечисление значений для `timer_output_mode`» | First half true. Second half false: `settings.yaml` contains no table with `AUTO/MOTORS/SERVOS/LED` at all (no match for `output_mode`, `outputMode`, `MOTORS`, `SERVOS` outside descriptions). The values are the C enum `OUTPUT_MODE_AUTO…OUTPUT_MODE_LED` (flight/mixer.h:47-52) parsed by string compare in `cliTimerOutputMode` (fc/cli.c:3168-3225) and stored in `timerOverrides` (flight/mixer.c:100-105) | error | «Настройки `output_mode` в 9.1.0 нет — ни самой настройки, ни таблицы значений в `settings.yaml`: режимы `AUTO`, `MOTORS`, `SERVOS`, `LED` заданы перечислением в `flight/mixer.h` и меняются только командой `timer_output_mode`.» |
| M3 | content/inav/inav-mixer-vtol.md:126 | Timer index = TIM number − 1 «на STM32F4»; other MCUs left open (author-marked) | Settled. F4, F7 and AT32F43x: index = N − 1 for timers 1…14 (drivers/timer_stm32f4xx.c:36-96, timer_stm32f7xx.c:35-48, timer_at32f43x.c:37-93; AT32 adds TMR20 at index 14). **H7 differs** above TIM8: TIM12 → 8, TIM13 → 9, TIM14 → 10, TIM15 → 11, TIM16 → 12, TIM17 → 13 (timer_stm32h7xx.c:35-48). Configurator label «Timer N» = index + 1 on every MCU (cfg9/tabs/mixer.js:94-98, 137) | imprecise | «Номер — индекс в таблице таймеров. На F4, F7 и AT32 это номер TIM минус 1; на H7 так только до TIM8, дальше TIM12 → 8, TIM13 → 9, TIM14 → 10, TIM15 → 11, TIM16 → 12, TIM17 → 13 (`timer_stm32h7xx.c`). Надёжнее смотреть вкладку Mixer: «Timer N» = индекс + 1.» |
| M4 | content/inav/inav-mixer-vtol.md:104, :151, :216 | `MIXER_SWITCH_HELPER` «появился в 9.x»; serial gimbal «с INAV 8»; `transition_pid_mmix_multiplier_*` «новые в 9.x» | No 8.x firmware tree on disk. All three exist in 9.1.0 (flight/servos.h:87; io/serial.h:60; settings.yaml:1282-1299). The last one agrees with `inav-intro.md:86` | unverifiable | — |

Settled from source (author-marked "unverified"):

- **DShot on MATEKF405TE S9 / S10.** `DEF_TIM_DMA__BTCH_TIM12_CH1 NONE`, `…TIM13_CH1 NONE` (drivers/timer_def_stm32f4xx.h:71-74); the target builds with `USE_DSHOT_DMAR` (target/MATEKF405TE/target.h:175-176) and `motorConfigDshot()` returns NULL when the burst-DMA setup fails (drivers/pwm_output.c:341-363) → `PWM_INIT_ERROR_TIMER_INIT_FAILED`, arming flag `PWMOUT`. The module's statement is correct.
- **Timer index ↔ TIM beyond F4** — see M3.

Confirmed against source, priority items:

- **`mmix`**: `rpyMix = (pitch·P + roll·R − motorYawMultiplier·yaw·Y)·mixerScale`, `motor = rpyMix + constrain(thr·throttle, …)` (flight/mixer.c:531-541, 631); yaw stick sign `cachedCmd[YAW] = −getAxisRcCommand(…)` (fc/fc_core.c:402); `motor_direction_inverted` flips `motorYawMultiplier` (mixer.c:232-236); sign conventions per docs/Mixer.md:32-34; 12 motors (flight/mixer.h:27); print stops at throttle 0 (fc/cli.c:1150-1152).
- **Throttle −1 / −2**: `throttle <= 0` → `motorZeroCommand`; in transition mixing and `−2.0 ≤ throttle ≤ −1.05`, not with `REVERSIBLE_MOTORS` → `−throttle·1000` constrained to the throttle range (mixer.c:641-648). Motor count over both profiles (mixer.c:117-137). The docs' «−2.0 < throttle < −1.0» (docs/VTOL.md:250; docs/MixerProfile.md:41-42) and the stale `mixer_pid_profile_linking` lines (docs/VTOL.md:73-145) are as the module's note says.
- **61 `smix` sources**: ids 0…60 and every name match `inputSource_e` (flight/servos.h:26-89); value semantics (flight/servos.c:302-420): stabilized inputs = sticks in MANUAL, throttle −500 when disarmed, CAMSTAB gating and ±900 / ±1800 scaling, flaperon offset, `INPUT_MAX` 500, GVAR ±1000, transition 500, head tracker zero in GIMBAL CENTER, CH19-34 behind `USE_34CHANNELS` (target/common.h:207-212), helper = 0. CLI limits: 36 rules, 18 servos, weight ±1000, speed 0-255, condition −1…63 (fc/cli.c:2382-2387; servos.h:23, 139-140).
- **Servo maths**: `servo += (int32)input·weight/100`; `·rate/100`; `(int16)(servo · (max−mid)/500.0f)` or `(mid−min)/500.0f`; `+ mid`; `constrain` (servos.c:443-497); `servo` limits 500…2500, rate ±125 (cli.c:2289-2293). Step 2 re-run with float32 arithmetic: A 1748 / 1308, B 1369 / 1792, C 1900 / 1500, D 1535 / 2000, E 1976 → 1900 / 1442; one clip; 1.0 s — all ten values match, as do the three "typical wrong" numbers (1820, 1667, +500 = `max`).
- **Timer allocation**: re-implemented `pwmEnsureEnoughtMotors()` + `pwmBuildTimerOutputList()` (drivers/pwm_mapping.c:273-369) in a separate script against the `target.c` table (target/MATEKF405TE/target.c:28-42). Results: 1-2 motors → 9 servo outputs, 3-4 → 7 (S5-S11), 5-8 → 3 (S9-S11); 5 motors + `timer_output_mode 1 SERVOS` → motors S1-S4, S9; + `timer_output_mode 3 MOTORS` → motors S1-S4, S11 and servos S5-S10. Identical to the module, the quiz and the `timer-servo-count` task. `LED` accepted by the parser though the help text omits it (cli.c:3194, 4986); error strings (pwm_mapping.c:67-68; cli.c:4327).
- **Profiles / transition** (flight/mixer_profile.c): two profiles, one on ≤ 512 KB non-F7 (target/common.h:207-222); hot switch refused in CLI, during sensor calibration and unless `navState` is IDLE or MIXERAT (lines 196-256); transition mixing only in IDLE / ALTHOLD / automated transition (line 207); switches ignored in failsafe (line 200); linking read from the profile being switched **to** (lines 93-106); timer × 100 ms from the current profile (lines 108-112); automated switch needs the `MIXER PROFILE 2` mode to exist (lines 123-146); RTH threshold `3 × nav_fw_loiter_radius` (navigation/navigation.c:1677), landing (navigation.c:1827). Mode ids 8 / 34 / 62 / 63 / 65-68 (fc/fc_msp_box.c:60-111).
- **Settings that do not exist**: no `mixer_vtol_*`, no `output_mode`, no `mixer_pid_profile_linking` in 9.1.0 `settings.yaml` — confirmed. Every row of the reference table matches settings.yaml:849, 1120, 1234-1299, 1327-1357.
- **Presets**: Quad X, Hex X, Flying Wing, Airplane, Airplane V-tail rows match cfg9/js/model.js:83-95, 178-192, 352-372, 401-426, 460-487.
- **Step 4 state table and the three errors** (−1.000 placeholder, timer 4 = 0.4 s, linking OFF in the target profile) follow from the code above.
- **Task bank**: `mmix-roll-weight`, `mmix-pitch-weight`, `servo-pulse` (all 272 combinations checked against float32 firmware arithmetic: worst deviation 1 µs, inside tol), `timer-servo-count`, `transition-timer`, `transition-tilt-time` — correct. **Quiz**: 10/10 correct, one defensible option each.
- **Cross-module**: agrees with `inav-setup-wing.md:51, 99-102`, `inav-setup-scratch.md:225`, `inav-intro.md:71, 86`, `bf-servos-pwm.md:41-52`.

## Checks 5 and 6 (all four modules)

- **Safety.** No advice found that, followed literally, causes a fly-away, an unexpected motor start or loss of failsafe. Hardware sections keep props off for bench steps; `px4-safety-return` flags `GF_PREDICT`, `CBRK_FLIGHTTERM` = 0, `GF_ACTION` = 4 and `SYS_FAILURE_EN` as dangerous; `inav-mixer-vtol` warns about profile switch without airspeed. The one field test (PX4, transmitter off at 10 m in Position) is the standard RC-loss test and is preceded by the bench version.
- **Self-study wording.** No «сдать / отчёт / покажи / проверяющий / преподаватель» in the four modules or their quiz / task files. Every self-check criterion is a number or a named item the reader can compare alone. The only criteria a reader cannot reach are the ones broken by P1, P2, I2 and M1.

## Counts

| Module | Statements checked | Confirmed | Error | Imprecise | Unverifiable |
|---|---|---|---|---|---|
| px4-safety-return (+ 10 quiz, 4 tasks) | 212 | 208 | 1 | 2 | 1 |
| inav-osd-hd (+ 10 quiz, 6 tasks) | 148 | 142 | 2 | 1 | 3 |
| ap-osd-video (+ 10 quiz, 8 tasks) | 171 | 168 | 0 | 2 | 1 |
| inav-mixer-vtol (+ 10 quiz, 6 tasks) | 186 | 182 | 2 | 1 | 1 |
| **Total** | **717** | **700** | **5** | **6** | **6** |

Counts are per finding row (a row may cover several lines of the module); "statements checked" counts parameter cells, enum values, formulas, worked numbers, quiz items and task variants individually and is approximate to ±5 %.

## Rows the migration tables should gain

`content/px4/px4-intro.md` (1.15 → 1.17 table) — facts used by `px4-safety-return` that the table does not carry yet (all verified in the three trees):

| Было | Стало | Что изменилось | С какого релиза |
|---|---|---|---|
| `COM_ARM_WO_GPS`: 0 — нужен GPS, 1 — не нужен | 0 — запрет арма, 1 — предупреждение, 2 — проверка выключена | умолчание 1 сохранилось, смысл значений другой | 1.16 |
| — | `COM_RAM_MAX` = 95 % | запрет арма по занятой памяти (SITL: −1) | 1.16 |
| `RTL_TYPE` 0…3 | 0…4 | 4 — посадка миссии или дом по миссии назад, что ближе по числу точек | 1.16 |
| Return мультиротора: всегда остановка и снижение до `RTL_DESCEND_ALT` | при `RTL_LAND_DELAY` = 0 посадка начинается с высоты возврата | остановка на `RTL_DESCEND_ALT` только при ненулевой задержке | 1.16 |
| `COM_RCL_EXCEPT` биты 0–2 | + бит 3 External Mode, бит 4 Altitude Cruise | новые исключения потери RC | 1.17 |
| `COM_DLL_EXCEPT` — | биты 0 Mission, 1 Hold, 2 Offboard | (строка в таблице есть — проверь, что перечислены биты) | 1.16 |

`content/inav/inav-intro.md` (8.0 → 9.1 table):

| Было (8.0.1) | Стало (9.1.0) | Что изменилось | С какого релиза |
|---|---|---|---|
| `osd_pan_servo_pwm2centideg` | `osd_pan_servo_range_decadegrees` | (строка есть и верна — число то же; привести `inav-osd-hd`:176 в соответствие, см. I1) | 9.0 |
| `timer_output_mode <n> AUTO\|MOTORS\|SERVOS` | + `LED` | значение принимает парсер 9.1.0, в подсказке CLI его нет — **проверить по дереву 8.0.1 перед добавлением** | ? |
| входы `smix` 0…59 | 0…60 | 60 — служебный `MIXER_SWITCH_HELPER` — **проверить по дереву 8.0.1** | 9.x ? |
| документация VTOL: `set mixer_pid_profile_linking = ON` | `mixer_control_profile_linking` | `docs/VTOL.md` и `docs/MixerProfile.md` тега 9.1.0 всё ещё содержат старое имя; строку из документации прошивка отвергнет | 9.0 |
| `osd_row_shiftdown` | есть, но не читается | в 9.1.0 настройка ни на что не влияет — **с какой версии, проверить по 8.0.1** | ? |

The three rows marked «проверить» need the 8.0.1 firmware tree, which was not on disk for this review.
