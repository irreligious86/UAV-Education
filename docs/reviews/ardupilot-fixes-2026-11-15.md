# ArduPilot track fixes — 2026-11-15

Fixes for `docs/reviews/ardupilot-coverage-audit.md` §7.3 (9 errors #1–#9, 3 clarifications #10–#12), plus repeats of the
same errors that grep found elsewhere in the course. Primary source: `/tmp/ardupilot` at tag **Copter-4.6.3** (`92b0cd7`),
the version of the course SITL. Also used: `/tmp/ardupilot-audit/plane463` (Plane-4.6.3), `copter472` (Copter-4.7.2),
`master` (4.8.0-dev), the parameter metadata JSON there (`copter-4.6.3`, `copter-4.7.2`, `plane-4.6.3`), the SITL firmware
default dump `copter-sitl-defaults.csv`, and the wiki page `common-blheli32-passthru` (fetched, for #11 only). Every item
was checked against the source before editing. Nothing was committed and `publish.py` was not run. Built outputs
(`en/`, `cs/`, `uk/`, `api/`, root `quiz/` …) and `i18n/` translations still carry the old text until the next publish /
translation pass. `validate_content.py`: OK (140 articles, 140 quizzes).

## Changes

| # | §7.3 | File | Before → after (short) | Source |
|---|---|---|---|---|
| 1 | 1 | `content/ardupilot/ap-logs.md` theory «Что писать в LOG_BITMASK» | "для тюнинга добавить `PID`" → `PID` (bit 12) is already in the Copter default 180222 but logs at 10 Hz; for tuning add bit 0 Fast Attitude (`ANG`, `RATE`, `PIDx` at loop rate) plus `IMU_RAW`/batch sampling | `ArduCopter/config.h` `DEFAULT_LOG_BITMASK`; `defines.h` `MASK_LOG_*`; `Copter.cpp` `loop_rate_logging()` / `ten_hz_logging_loop()`; SITL `LOG_BITMASK` |
| 2 | 1 | `content/quiz/ap-logs.json` Q "Что включить в LOG_BITMASK для тюнинга PID?" | correct option "PID и батч-сэмплинг" → "Fast Attitude и батч-сэмплинг"; explain says PID is already default at 10 Hz. Answer index unchanged (1); correct option is not the longest | as above |
| 3 | 2 (partly) | `content/ardupilot/ap-quadplane.md` «Переходы…», VTOL-контур bullet | "TECS и `PTCH2SRV_*`/`RLL2SRV_*` — для крыла" → "TECS, `RLL_RATE_*`/`PTCH_RATE_*` (rate PID крыла) и `RLL2SRV_*`/`PTCH2SRV_*` (`TCONST`, `RMAX`) — для крыла" | Plane-4.6.3 metadata: `RLL_RATE_P…`, `PTCH_RATE_P…` present; `RLL2SRV_TCONST/RMAX`, `PTCH2SRV_TCONST/RMAX_UP/DN/RLL` present |
| 4 | 3 | `ap-quadplane.md` «Конфигурация QuadPlane-tiltrotor» | added bullet `Q_TILT_ENABLE = 1` (default 0; other `Q_TILT_*` hidden/inactive until set) | Plane-4.6.3 `ArduPlane/tiltrotor.cpp` `AP_GROUPINFO_FLAGS("ENABLE", 1, …, 0, AP_PARAM_FLAG_ENABLE)` |
| 5 | 3 | `ap-quadplane.md` same list, `Q_TILT_RATE_UP/DN` | added defaults 40 and 0 (`_DN = 0` → use `_UP`); the "≈15 °/s start" advice kept | `tiltrotor.cpp` `RATE_UP` 40, `RATE_DN` 0 + @Description |
| 6 | 4 | `content/estimation/nav-rtk.md` theory (RTK status paragraph) | `max(GPA.HAcc, EK3_GPS_P_NSE)²` and "`EK3_GPS_P_NSE` у Copter по умолчанию 0.5 м" → `EK3_POSNE_M_NSE` (value 0.5 m kept) | `AP_NavEKF3.cpp` `POSNE_M_NSE` (default `POSNE_M_NSE_DEFAULT 0.5f`); `AP_NavEKF3_PosVelFusion.cpp` L744 `R_OBS[3] = sq(constrain(gpsPosAccuracy, _gpsHorizPosNoise, 100))`; no `GPS_P_NSE` in 4.6.3/4.7.2/master |
| 7 | 4 | `nav-rtk.md` practice (`SIM_GPS2_ACC` line) | "упрётся в `EK3_GPS_P_NSE = 0.5`" → `EK3_POSNE_M_NSE = 0.5` | as above |
| 8 | 4 (grep) | `content/estimation/est-kalman.md` "Что трогать" line | `EK3_*_NOISE` (R по источникам) → `EK3_*_M_NSE` (no EKF3 parameter ends in `_NOISE`; measurement noises are `*_M_NSE`) | `AP_NavEKF3.cpp` var_info |
| 9 | 5 | `content/ardupilot/ap-safety-fs.md` practice Шаг 1 | "`FS_OPTIONS` = 0 без разрешения BVLOS" → bits 0–2 off without BVLOS authorisation, keep bit 4 from the default 16 (otherwise a telemetry dropout with `FS_GCS_ENABLE` RTLs a manually flown copter) | `ArduCopter/Parameters.cpp` L943 default `GCS_CONTINUE_IF_PILOT_CONTROL`; `Copter.h` L624 `(1<<4) // 16`; SITL `FS_OPTIONS,16` |
| 10 | 8 | `ap-safety-fs.md` practice Шаг 1 | "`RTL_ALT_M` выше препятствий" → "`RTL_ALT` (в SITL 4.6.3, см; в 4.7+ — `RTL_ALT_M`, м)". Theory already gave both names; diagnostics/checklist left as is | Copter-4.6.3 metadata `RTL_ALT` (cm), no `RTL_ALT_M`; 4.7.2 the reverse |
| 11 | 6 | `content/ardupilot/ap-intro.md` «Требования к железу» | "Lua-скрипты требуют минимум 2 МБ флеша и не работают на F4" → built only for boards with flash > 1 MB: none on F405/F411; F427/F429 with 2 MB (Pixhawk 1, Cube Black) run Lua | `libraries/AP_Scripting/AP_Scripting_config.h` `BOARD_FLASH_SIZE > 1024`; hwdef: `fmuv3` STM32F427 `FLASH_SIZE_KB 2048`, `MatekF405*` 1024 |
| 12 | 6 | `ap-intro.md` diagnostics "Lua-скрипты не запускаются" | cause "F4-плата" → board with ≤ 1 MB flash (F405, F411); action "нужен F7/H7" → "нужно 2 МБ (F427/F429, F7, H7)" | as above |
| 13 | 6 | `content/quiz/ap-intro.json` Q "Почему Lua-скрипты не работают на F4?" | → "…на F405-платах?"; explain: flash > 1 MB needed, F405 has 1 MB, F427 with 2 MB runs Lua. Options and answer index unchanged | as above |
| 14 | 6 | `content/ardupilot/ap-lua.md` theory bullet + checklist | "не работает на F4-контроллерах" → F405/F411 (1 MB) no, F427/F429 2 MB, F7, H7 yes; checklist "на F4" → "на F405 (1 МБ флеша)" | as above |
| 15 | 7 | `ap-lua.md` «Applets как учебник» | `crsf-calibrate.lua` → "(появился в 4.7, в 4.6.3 его нет)". Other listed applets checked: all present in 4.6.3 | `libraries/AP_Scripting/applets/` at Copter-4.6.3 (absent), 4.7.2 and master (present) |
| 16 | 8 | `ap-intro.md` practice step 2 | `ARMING_SKIPCHK` → `ARMING_CHECK` + "(SITL курса — 4.6.3; в 4.7+ вместо `ARMING_CHECK` будет `ARMING_SKIPCHK`)" | Copter-4.6.3 vs 4.7.2 metadata; SITL `ARMING_CHECK,1` |
| 17 | 8 | `ap-intro.md` practice «Что должно получиться» | "в Copter 4.7 задаёт `ARMING_SKIPCHK` (раньше `ARMING_CHECK`)" → "в SITL 4.6.3 — `ARMING_CHECK` (1 — все); в 4.7+ — `ARMING_SKIPCHK` с обратным смыслом" | as above |
| 18 | 8 | `ap-intro.md` «Порядок первой настройки» step 4 | `RTL_ALT_M` → "`RTL_ALT` (в 4.6, см; в 4.7+ — `RTL_ALT_M`, м)" | as above |
| 19 | 8 | `ap-intro.md` «Разобранный пример» | "`ARMING_SKIPCHK` сообщает причину текстом" → the `PreArm: …` message names the reason; `ARMING_CHECK` (4.7+ `ARMING_SKIPCHK`) only selects which checks run | `ARMING_CHECK` @Description (bitmask of checks); `AP_Arming` prearm STATUSTEXT |
| 20 | 9 | `content/betaflight/bf-hd-osd-video.md` table «INAV и ArduPilot — коротко», row «Сетка», ArduPilot cell | "от очков; `MSP_OPTIONS` бит 2 — шрифт Betaflight" → set by the FC per screen: `OSDn_TXT_RES` 0 30×16 (default — HD goggles show the SD grid), 1 50×18, 2 60×22; `MSP_OPTIONS` bit 2 — Betaflight symbols (kept, see rejections) | `AP_OSD_Screen.cpp` L1072–1077 `TXT_RES` default 0; `AP_OSD_MSP_DisplayPort.cpp` L68–70 sends it to the goggles (`MSP_DISPLAYPORT_SET_OPTIONS`); no canvas-from-goggles handling in `AP_MSP`/`AP_OSD` |
| 21 | 10 | `content/ardupilot/ap-setup-scratch.md` step 5 | "1000/2000 в стандартных параметрах" → "в параметрах SITL по умолчанию — `copter.parm`, который грузит `sim_vehicle.py`; у прошивки на чистой плате 1100/1900" | `Tools/autotest/default_params/copter.parm`; SITL with empty defaults `RC1_MIN 1100`, `RC1_MAX 1900` |
| 22 | 11 | `ap-setup-scratch.md` step 6 | "passthrough для BLHeliSuite/ESC Configurator на всех моторах" → BLHeliSuite32 or AM32 Configurator, BLHeliSuite/JESC for BLHeli_S; web ESC Configurator from 4.5, unreliable over ArduPilot; needs DShot, safety pressed/disabled, non-IOMCU outputs | `AP_BLHeli.cpp` `SERVO_BLH_AUTO` @Description; wiki `common-blheli32-passthru` (fetched) |
| 23 | 12 | `ap-setup-scratch.md` step 7 | "`COMPASS_USE2 = 0` (или `COMPASS_USE3`), если он мешает" → same, plus: the number is a priority, not "internal"; check `COMPASS_PRIO1_ID…3_ID` against the GCS compass list first | `AP_Compass.cpp` L343/L366: `USE2/USE3` = `_use_for_yaw._priv_instance[1/2]`, `RestrictIDTypeArray<…, Priority>` (`AP_Compass.h` L621) |
| 24 | 12 | `ap-intro.md` diagnostics "Compass not calibrated / inconsistent" | "отключить внутренний (`COMPASS_USE2 = 0`)" → `COMPASS_USEn = 0` for the priority it sits at; `USE2` = 2nd priority, not necessarily internal; check `COMPASS_PRIOn_ID` | as above |
| 25 | 12 | `content/pages/setup-cards.html` ArduPilot card, row 9 | "внутренний компас при мачтовом — `COMPASS_USE2 = 0`" → `COMPASS_USEn = 0` for its priority (check `COMPASS_PRIOn_ID`; `USE2` = 2nd priority) | as above |

## Audit items rejected or only partly accepted

- **#2 (partly rejected).** The audit says `PTCH2SRV_*`/`RLL2SRV_*` "do not exist in Plane 4.6.3". Wrong: the groups exist
  (`RLL2SRV_TCONST`, `RLL2SRV_RMAX`, `PTCH2SRV_TCONST`, `PTCH2SRV_RMAX_UP/DN`, `PTCH2SRV_RLL` in Plane-4.6.3 metadata; the
  course's ap-plane-tuning module and its quiz/task bank use them correctly). Only the old PID gains (`PTCH2SRV_P` etc.)
  are gone. The course wildcard was not wrong; it was incomplete next to `Q_A_RAT_*`, so the rate-PID groups
  `RLL_RATE_*`/`PTCH_RATE_*` were added (change #3) and the `*2SRV_*` names kept.
- **#9 (partly rejected).** The audit says `MSP_OPTIONS` bit 2 is "for the legacy DJI protocol 33". In 4.6.3 source the bit
  is `DISPLAYPORT_BTFL_SYMBOLS` (`AP_MSP.h` L63) and is read by the DisplayPort code (`AP_MSP_Telem_DisplayPort.cpp` L35:
  FC identifies as Betaflight; `AP_OSD_MSP_DisplayPort.cpp` L139/L158: Betaflight symbol table). So the course's "бит 2 —
  шрифт Betaflight" in the DisplayPort row is right and was kept (wording "символы Betaflight"). The grid part of #9
  (grid comes from `OSDn_TXT_RES`, not from the goggles) was correct and fixed. The audit's "HDZero 0/1 only" and wiki
  recommendations on bits 0/3 were not verified in source and were not added.
- **#12 note.** Accepted as a clarification; no course value was wrong in itself.

## Not changed (checked)

- `ap-safety-fs.md` diagnostics/checklist and `ap-tuning.md` still use `RTL_ALT_M` / "`LOG_BITMASK` с PID": the module
  theory names both RTL parameters, and PID is in the default mask, so these are not errors.
- `ap-safety-fs.md` theory bullet and diagnostics on `FS_OPTIONS` bit 0 (off without authorisation) are correct; quiz
  `ap-safety-fs.json` Q "Бит 0 FS_OPTIONS" is correct.
- `ap-quadplane.md` and `bf-custom.md` say "на F405 нет Lua" — correct.
- Other applets named in ap-lua (`motor_failure_test`, `VTOL-quicktune`, `rover-quicktune`, `copter-deadreckon-home`,
  `arming-checks`, `ahrs-source-extnav-optflow`, `BattEstimate`, `MissionSelector`, `net_webserver`, `SmartAudio`) all
  exist in 4.6.3.
