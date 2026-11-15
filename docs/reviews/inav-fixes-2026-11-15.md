# INAV track fixes — 2026-11-15

Fixes for `docs/reviews/inav-coverage-audit.md` §7.3 (E1–E15), with the HD OSD item (E4) carried to every place in the
course that names `osd_video_system`. Primary source: INAV 8.0.1 at `/tmp/inavsrc/inav8` (the course's stated version),
cross-checked against INAV 9.1.0 (`/tmp/inav-audit/inav9`) and Configurator 8.0.1 / 9.1.0 (`tabs/osd.js`). Web sources:
INAV 8.0.0 / 8.0.1 / 2.2.0 release notes. Nothing was committed and `publish.py` was not run. `validate_content.py`: OK
before and after.

Built outputs (`en/`, `cs/` HTML, `search.json`) still carry the old text until the next publish and translation pass.

## HD OSD: what each system needs (verified)

`osd_video_system` table (8.0.1 = 9.1.0): AUTO, PAL, NTSC, HDZERO, DJIWTF, AVATAR, BF43COMPAT, BFHDCOMPAT, DJI_NATIVE.
`io/displayport_msp_osd.c` `mspOsdDisplayPortInit()`: HDZERO → 50×18; DJIWTF → 60×22; AVATAR, BFHDCOMPAT (`VIDEO_SYSTEM_DJICOMPAT_HD`),
DJI_NATIVE → 53×20; BF43COMPAT (`VIDEO_SYSTEM_DJICOMPAT`), AUTO, PAL → 30×16. Only BF43COMPAT/BFHDCOMPAT remap glyphs to the
DJI/Betaflight font (`displayport_msp_dji_compat.h` `isDJICompatibleVideoSystem`). Same switch in 9.1 (only the HDZero 30×16
sub-mode was removed). Configurator 8.0.1 and 9.1.0 offer PAL, HDZERO, DJIWTF, AVATAR, BF43COMPAT, BFHDCOMPAT, DJI_NATIVE for MSP OSD.

| System | Value | Evidence |
|---|---|---|
| HDZero | HDZERO (50×18) | source; `OSD.md` |
| Walksnail Avatar | AVATAR (53×20) | source; `OSD.md` |
| DJI O4; Goggles 2/3/N3/Integra on the 2025 firmware with INAV font | DJI_NATIVE (53×20), goggles OSD type "INAV" | 8.0.1 release notes ("select DJI_NATIVE … select INAV as the OSD type in your updated goggles"); 9.1 `OSD.md` "DJI Goggles 2 and newer — YES (no custom fonts)" |
| DJI O3, stock firmware | BFHDCOMPAT (53×20, Betaflight font, `?` for missing glyphs, HD canvas in goggles) | 8.0.1 `OSD.md` "DJI O3 53×20 (HD), BF characters only"; `DJI compatible OSD.md` |
| Air Unit / Vista + V1/V2 goggles under WTFOS | DJIWTF (60×22) | source; `OSD.md` |
| Legacy DJI without WTFOS | BF43COMPAT (30×16) | source; `DJI compatible OSD.md` |
| O4 on old firmware (no arm detection) | update goggles or `enable_broken_o4_workaround = ON` (still present in 9.1 despite the 8.0.1 note) | `settings.yaml` 8.0.1 and 9.1.0 |

Not verified: whether DJI_NATIVE works with an O3 air unit on updated goggles (DJI and the press name only O4), so the course
recommends BFHDCOMPAT for O3. `DJI compatible OSD.md` still uses the old names DJI43COMPAT/DJIHDCOMPAT; the CLI names are
BF43COMPAT/BFHDCOMPAT.

## Changes

| # | Item | File | Before → after (short) | Source |
|---|---|---|---|---|
| 1 | E4 | `content/inav/inav-setup-scratch.md` practice step 8 | "MSP_OSD … `DJIWTF`, AVATAR или HDZERO" → per-system map (HDZERO 50×18, AVATAR 53×20, DJI_NATIVE for O4 / updated goggles + OSD type INAV, BFHDCOMPAT for stock O3, DJIWTF for WTFOS), 115200, O4 arm workaround, "в 9.1 то же" | see table above |
| 2 | E4 | `inav-setup-scratch.md` references | +3 sources: `OSD.md` 8.0.1, `displayport_msp_osd.c` 8.0.1, 8.0.1 release notes | — |
| 3 | E4 | `content/pages/setup-cards.html` INAV card 13 | same map, short form | as above |
| 4 | E4 | `content/betaflight/bf-hd-osd-video.md` "INAV и ArduPilot — коротко" | value list only → added one paragraph after the table: system → value → grid (incl. BF43COMPAT for legacy DJI) | as above |
| 5 | E4 | `content/link/link-digital-video.md` theory INAV bullet | "тип OSD — по документации своей системы" → MSP_OSD + value per system, link to `bf-hd-osd-video` | as above |
| 6 | E4 | `link-digital-video.md` practice step 2 | added the INAV line (MSP_OSD + `osd_video_system` for the system) | as above |
| 7 | E1 | `content/inav/inav-missions.md` "Структура точки" `p1`/`p2` | "50 < p1 < `nav_auto_speed`" → 50 ≤ p1 ≤ `nav_max_auto_speed` (1000), larger clamped, < 50 → `nav_auto_speed`; also for LAND; POSHOLD_TIME speed in `p2` with the same rules | `navigation.c` `getActiveSpeed()` L4212–4236; only caller `navigation_multicopter.c` L725 |
| 8 | E2 | `content/inav/inav-gps.md` "Три датчика" | stick "сброс курса" → GPS ground course is used with 3D fix, ≥ 6 sats, ground speed ≥ 3 m/s; no heading before first run; no stick command for heading | `io/gps.c` `isGPSHeadingValid()`; `flight/imu.c` L746–760; `fc/rc_controls.c` stick list |
| 9 | E8 | `inav-gps.md` barometer bullet | "обязателен для ALTHOLD/RTH" → strongly recommended; without it altitude comes from GPS (`inav_default_alt_sensor`) and is much worse | `navigation.c` `canActivateAltHoldMode()` L4378; `navigation_pos_estimator.c` L563–577 |
| 10 | E8 | `content/inav/inav-intro.md` "Что под капотом" | "компас и баро обязательны для мультиротора" → "практически обязательны" with what replaces each (GPS altitude; GPS course while moving) | as above + `imu.c` `isImuHeadingValid()` L881 |
| 11 | E11 | `inav-intro.md` "Что иначе", home/safehomes | safehome "replaces home on RTH" → selected at arming, replaces home when RTH starts; home = arm point per `inav_reset_home` (FIRST_ARM default, EACH_ARM, NEVER) | `navigation.c` L3384–3388 (`findNearestSafeHome()` on home set at arm); `docs/Safehomes.md`; `settings.yaml` |
| 12 | E12 | `inav-intro.md` "Арм только тумблером" | kept "удалён в INAV 2.2" (verified); added `fixed_wing_auto_arm` (OFF): with motorstop, arms on throttle above `min_check`, disarm only by power-off | 2.2.0 release notes ("Remove Sticks Arming"); `rc_controls.c` L215–220; `settings.yaml` |
| 13 | E3 | `content/estimation/nav-resilience.md` INAV bullet | "~2 с … снижение на `failsafe_throttle`, моторы через `failsafe_off_delay`" → `nav_position_timeout` 5 s (0 = off); descent at `nav_emerg_landing_speed` (5 m/s) while altitude valid, until landing detection (`nav_disarm_on_landing`); `failsafe_throttle` only without altitude | `settings.yaml`; `navigation.c` `checkForPositionSensorTimeout()` L2777, L2211–2228, L3558; `navigation_multicopter.c` L938–957; `navigation_fixedwing.c` L789–801 |
| 14 | E15 | `nav-resilience.md` INAV bullet | "по airspeed+компасу" → wing only: heading from compass (drifts without it), altitude from baro, speed from pitot or `fw_reference_airspeed`, wind from before the loss; fix and home needed before takeoff | `docs/GPS_fix_estimation.md` 8.0.1 |
| 15 | E9 | `inav-missions.md` "Защита от чужой миссии" | "`ALLOW_BYPASS` плюс yaw" → yaw right at arming bypasses the first-WP block regardless of `nav_extra_arming_safety`; 0 in `nav_wp_max_safe_distance` (100 m) disables it; ALLOW_BYPASS (8.0.1 default) is for the no-fix block | `navigation.c` `navigationIsBlockingArming()` L4701–4721; `settings.yaml` |
| 16 | E10 | `content/inav/inav-wing.md` diagnostics loiter | `max_angle` → `nav_fw_bank_angle` (35°) | `settings.yaml` L2883 |
| 17 | E5 | `content/inav/inav-setup-wing.md` step 2 | "MOTORS или SERVOS" → "AUTO, MOTORS, SERVOS или LED (выход под LED-ленту)" | `fc/cli.c` `outputModeNames[]`; `drivers/pwm_mapping.c` `timerHardwareOverride()` |
| 18 | E5 | `content/betaflight/bf-servos-pwm.md` INAV column | `AUTO\|MOTORS\|SERVOS` → `AUTO\|MOTORS\|SERVOS\|LED` | as above |
| 19 | E6 | `content/inav/inav-ipf.md` practice step 2 | placeholders `<home_distance_operand_id>`, `<set_vtx_power_op_id>` → `logic 0 1 -1 2 2 1 0 100 0`, `logic 1 1 0 25 0 3 0 0 0`; "номера меняются между релизами" → CLI format, op 2 = GREATER_THAN, 25 = SET_VTX_POWER_LEVEL, flight operand 1 = home distance; same in 9.1 (append-only), still check the docs | `programming/logic_condition.h` 8.0.1 vs 9.1.0 (ops 0–54, flight operands 0–45 identical); `cli.c` `logic` help |
| 20 | E7 | `inav-ipf.md` theory "Модель" | "целые от −32768 до 32767" → default bounds −32768…32767, `gvar <i> <default> <min> <max>` widens them (int32) | `global_variables.c` L44–45, L60; `global_variables.h` `int32_t min/max`; `cli.c` `cliGvar` |
| 21 | E7 | `content/quiz/inav-ipf.json` Q "Диапазон GVAR?" | question → "…по умолчанию (без команды gvar)?"; explain "Целые 16-битные" → default bounds + `gvar` changes them (int32). Answer index 1 unchanged | as above |
| 22 | E14 | frontmatter `inav-intro`, `inav-gps`, `inav-missions`, `inav-wing`, `inav-ipf` | "INAV 7.0+" → "INAV 7.0+ (сверено с 8.0.1)" | factcheck reports cite 8.0.x |
| 23 | E13 | frontmatter `inav-setup-scratch` | added: in 9.1 some defaults differ (Galileo/BeiDou ON, `gps_ublox_nav_hz` 8, `inav_w_z_*`) | audit §1.3 (9.1.0 `settings.yaml` diff) |

## Rejected or narrowed audit points

- **E14, suggested wording "INAV 8 (7.x отличия отмечены)"**: not used. The modules do not mark 7.x differences, and none of
  the five modules uses an 8-only feature (no geozones or serial gimbal there). The audit's example "FW autoland approach is
  8-only" is wrong: the 8.0.0 notes list "FW Nav Auto Landing fixes" and "MW XML schema for 7.1 Autoland", so `inav-wing`'s
  "INAV 7.1+ умеет … посадочные паттерны" stays. Only "(сверено с 8.0.1)" was added.
- **E12, "2.2 unverified"**: verified correct (2.2.0 release notes: "Arming with sticks is being removed", "Remove Sticks
  Arming"). Only the `fixed_wing_auto_arm` gap was fixed. Note: `settings.yaml` says auto-arm "requires … no arm switch
  configured", but `rc_controls.c` does not check that, so the course states only motorstop.
- **E4, "newer DJI firmware/O4 uses DJI_NATIVE"**: accepted for O4 and updated goggles. Not extended to O3, because no source
  confirms DJI_NATIVE with an O3 air unit (see above).
- **E8 flight behaviour without baro**: code permits ALTHOLD/RTH on GPS altitude; flight quality not tested here, so the course
  says "strongly recommended", not "not needed". `inav-setup-scratch` theory "RTH требует GPS, компас и баро" was left as is:
  it follows `Failsafe.md` (docs), which is the documented requirement for MC RTH.
- `inav-gps` "Потеря GPS в полёте" ("после короткого таймаута") was left: no wrong number there.
