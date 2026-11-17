# Migration report — ExpressLRS 3.x → 4.1.0 (2026-11-17)

Scope: step M5 of `COURSE-PLAN-THEORY.md` §3. Previous release 3.x (3.6.4 used as the baseline), target
4.1.0. No builds were run; nothing was committed; `scripts/publish.py` was not run.

## 1. Sources

| Source | How it was used |
|---|---|
| `ExpressLRS/ExpressLRS` tag `4.1.0` and tag `3.6.4`, shallow clones in `/tmp/elrs-migrate/elrs41`, `/tmp/elrs-migrate/elrs36` | `src/src/common.cpp`, `src/include/common.h`, `src/include/targets.h`, `src/lib/OTA/OTA.cpp`, `src/lib/tx-crsf/*`, `src/lib/LUA/tx_devLUA.cpp` (3.6), `src/src/dynpower.cpp`, `src/src/rx_main.cpp`, `src/src/rx-serial/*`, `src/targets/*.ini`, `src/lua/` diffed or read |
| `ExpressLRS/Docs` (HEAD of 2026-11-09), `/tmp/elrs-migrate/docs` | binding, lua-howto, switch-config, gemini, signal-health, telem-bandwidth, dynamic-transmit-power, model-config-match, mavlink, ardupilot-setup, webui, wifi-updating, backpack pages, spi-receivers, led-status, tx-prep, blog post of 2026-11-08 on the new Lua package |
| GitHub release pages 4.0.0 and 4.1.0 (WebFetch, summarised by the fetch tool, not verbatim) | breaking changes, dropped hardware, LittleFS, Lua, arming, telemetry changes, 4.1 additions |
| Betaflight `2025.12.5` (`/tmp/bf-migrate/bf2025`) and `2026.6.2` (raw.githubusercontent, `src/main/rx/expresslrs*.{c,h}`) | SPI receiver OTA version |
| ArduPilot Copter 4.7.2 parameter definitions (`/tmp/ardupilot-audit/copter-4.7.2.pdef.json`) | `SERIALn_PROTOCOL`, `SERIALn_BAUD`, `RSSI_TYPE`, `RC_OPTIONS`, `RC_PROTOCOLS`, `MAVn_*` |

## 2. Diff-derived migration table (full)

Rows marked **C** are in the course table in `link-elrs` («Переход 3.x → 4.x: что переименовано и
изменилось», 20 rows).

| # | Item | 3.6.4 | 4.1.0 | Evidence | In course |
|---|---|---|---|---|---|
| 1 | `OTA_VERSION_ID` | 3 (`include/common.h`) | 4 (`include/targets.h`); XORed into the CRC initialiser (now shifted to the high byte) and into the FHSS seed (`UID[5]^OTA_VERSION_ID`) | source diff | C |
| 2 | Platforms | ESP8285, ESP32, STM32 (23 files with `PLATFORM_STM32`) | ESP8285, ESP32, ESP32-C3, ESP32-S3 only (0 files) | grep, `src/targets/` | C |
| 3 | Target files | `unified.ini` + `frsky.ini`, `imrc.ini`, `siyi.ini`, `happymodel_*.ini`, `namimnorc_*.ini`, `diy_*.ini` | `esp32-*.ini`, `esp32c3-*.ini`, `esp32s3-*.ini`, `esp8285-*.ini`, all `Unified_*` | `ls src/targets` | C |
| 4 | Removed STM32 targets | `Frsky_TX_R9M*`, `Frsky_RX_R9MM_R9MINI`, `R9MX`, `R9SLIM*`, `GHOST_2400_TX*`, `GHOST_ATTO_2400_RX`, `HappyModel_PP_2400_RX`, `HappyModel_*_ES915*`, `FM30_*`, `NamimnoRC_FLASH_2400_*`, `NamimnoRC_VOYAGER_900_*`, `Jumper_RX_R900MINI`, `DIY_*_STM32*`, `DIY_900_RX_BluePill` | none | target ini files | C (as device list) |
| 5 | Device filesystem | SPIFFS | LittleFS, no in-place upgrade; custom `hardware.json` / `options.json` erased; PWM mapping and serial protocol kept | release notes 4.0.0 | C |
| 6 | Lua script | `elrsV3.lua` (+ `ELRS.lua`) | `elrs.lua` (r18), works with 2.0+ | `src/lua/`, README | C |
| 7 | Arming | CH5 only (`CRSFHandset::IsArmed` = AUX1) | status byte in the CRSF channels frame: `Arm using CH5` or `Switch`; EdgeTX 2.11.0+ | `TXModuleEndpoint.cpp`, release notes | C |
| 8 | Full Res 8ch | CH1–4, CH6–9, CH5 1-bit arm | CH1–8, CH5 proportional, arm flag copied to CH14 | `OTA.cpp`, switch-config doc | C |
| 9 | Full Res 12ch Mixed | CH1–4 full rate, CH6–13 half | CH1–4 full, CH5–12 half; CH13 not generated | switch-config doc, release notes | C |
| 10 | Wide switch mode | 128 positions (64 when telemetry is 1:2 / 1:4) | always 64 (`CRSF_to_N(ch, 64)`) | `OTA.cpp` both tags | C |
| 11 | Antenna mode / Gemini | manual on TX and RX (`Rx Mode`) | negotiated; steps down to Switch for single-chip RX; `Rx Mode` removed | release notes, lua-howto | C |
| 12 | Band selection on LR1121 | band suffix in the rate list (`"50 2.4G;…"`, `"… Low Band"`) | `RF Band` item (`2.4GHz` / `900MHz` / `X-Band`) | parameter string diff | C |
| 13 | LR1121 rate table | `RATE_MAX 16` | `RATE_MAX 20`: + `FSK_2G4_1000HZ` (K1000), `FSK_2G4_250HZ_DVDA` (DK250), `LORA_900_25HZ`, `LORA_900_50HZ_DVDA` | `common.cpp` diff | C |
| 14 | Rate enum / RFMD numbering | 1–19 | 0–11 (900), 20–36 (2.4), 100–101 (X-Band) | `common.h`, signal-health doc | C |
| 15 | Telemetry bandwidth | baseline | about +30 % in non-full-res modes; doubled in Gemini | release notes | C |
| 16 | `TQly` window | 25 | 100 | release notes | C |
| 17 | MAVLink RX protocol | manual `Protocol = MAVLINK` | automatic with `Link Mode = MAVLink`; Yaapu supported | mavlink doc, release notes (#3077) | C |
| 18 | Dynamic power | table SNR thresholds | statistical thresholds (mean, SD), table as fallback; 4.1: lower-power threshold +0.5 SD (was +1.5 SD) | `dynpower.cpp`, release notes 4.1.0 (#3577) | C |
| 19 | Web UI | tabs, hardware page hidden | page menu, Hardware page visible | webui doc, `html/src/pages` | C |
| 20 | Receiver outputs | CRSF, SBUS, SUMD, DJI RS2 Pro, HoTT, MAVLink | + `PROTOCOL_MSP_DISPLAYPORT`, `PROTOCOL_GPS`, `somDShot3D` | `common.h` diff | C |
| 21 | Bind phrase from the radio | none | Bind Phrase Manager (4.1, #3554) | release notes 4.1.0, Lua blog post | C |
| 22 | "Telemetry Lost" | immediate | scaled grace period (4.1, #3550) | release notes 4.1.0 | C |
| 23 | Rate enum names | `RATE_LORA_250HZ`, `RATE_DVDA_500HZ`, `RADIO_TYPE_*` | `RATE_LORA_2G4_250HZ`, `RATE_FLRC_2G4_500HZ_DVDA`, `RadioBandMod::Combined::*` | `common.h` | no (internal) |
| 24 | Config versions | TX 7, RX 9 | TX 8, RX 11 | `config.h` | no |
| 25 | Sync-boost telemetry | bumps to 1:8 in Wide to keep 7-bit switches | always 1:2 | `tx_main.cpp` | no |
| 26 | Linkstats to handset when disconnected | no | yes | release notes | mentioned in text |
| 27 | Servo stretch 500–2500 µs, PWM failsafe range 476–2523, headtracking channels, HoTT VSpeak, counter sync lock | — | added | release notes | no |
| 28 | 4.1: mV voltage telemetry, GPS time sync, VBAT calibration in Web UI, LR2021 refactoring | — | added | release notes 4.1.0 | no |

Unchanged and stated as such in the module: sensitivity, interval and `Std` telemetry ratio of every mode that
existed in 3.6.4 (the per-mode rows of `ExpressLRS_AirRateConfig` / `ExpressLRS_AirRateRFperf` are identical);
bind-phrase hashing (MD5 of `-DMY_BINDING_PHRASE="…"`, first 6 bytes); CRSF output to the flight controller;
3× power-cycle bind, button bind, `Bind Storage` options; `AUTO_WIFI_ON_INTERVAL=60`.

SPI receiver conflict, verified: Betaflight 2025.12.5 `src/main/rx/expresslrs_common.h:36`
`#define ELRS_OTA_VERSION_ID 3` (no alternative). Betaflight 2026.6.2: `#ifndef USE_ELRSV4 … 3 … #else … 4`;
`USE_ELRSV4` is not defined in the fetched headers, so it is a build-time option.

## 3. Files changed

| File | Change | Edits |
|---|---|---|
| `content/link/link-elrs.md` | theory rewritten for 4.1.0 (8 → 16 `###` subsections; mode table 9 → 18 rows from source; new: binding methods, Model Match, arming, Gemini/GemX/LR1121, MAVLink mode, Backpack, receiver failsafe, flashing/`hardware.json`/Web UI, «Переход 3.x → 4.x» with 7-step order and 20-row table, SPI conflict); practice: 2 steps given version notes; diagnostics 6 → 10; references 4 → 12; checklist 5 → 7; front matter `firmware`, `readingTime`. Sections, 3 directives and code-fence count (0) unchanged | 1 rewrite |
| `content/quiz/link-elrs.json` | 2 `explain` texts updated, 3 questions added (9 → 12); existing answer indexes untouched | 5 |
| `content/tasks/link-elrs.json` | no change needed (formulas valid for 4.x) | 0 |
| `content/betaflight/bf-setup-scratch.md` | bind sentence: "версии 3.x" → same major version + SPI note | 1 |
| `content/pages/setup-cards.html` | Betaflight card step 4, same wording as above (consistent with `bf-intro` item 8) | 1 |
| `content/betaflight/bf-ports.md` | one sentence in the CRSF bullet: serial receiver unaffected, SPI receiver stays ELRS 3 on 2025.12 | 1 |
| `content/betaflight/bf-failsafe.md` | two ELRS phrases: CRSF output simply stops; "No Pulses" is an SBUS/PWM output setting | 2 |
| `content/betaflight/bf-rates-rc.md` | packet-interval sentence labelled "ELRS 4.1.0, same in 3.x" (values re-verified) | 1 |
| `content/link/link-telemetry-radios.md` | ELRS MAVLink bullet: 4.x automatic RX protocol, Gemini bandwidth, same major version | 2 |

Totals: 9 files, 14 edits plus the module rewrite. `scripts/validate_content.py`: OK (140 modules, 140 quizzes).

Checked and left unchanged (already correct for 4.1): `rf-link-budget.md` sensitivity list, `ap-setup-scratch.md`
(`SERIALn_PROTOCOL = 23`, `RC_PROTOCOLS = 512`, `RC_OPTIONS = 8736`, `RSSI_TYPE = 3` match the 4.7.2
definitions), `px4-setup-scratch.md`, `inav-setup-scratch.md`, `inav-setup-wing.md`, `link-protocols.md`,
`bf-intro.md` (SPI note written by the Betaflight editor, consistent), `bf-modes-osd.md`, `ops-field.md`,
other quiz banks.

## 4. Items left on the old release or marked

- Practice text «Анализ линка по логу Blackbox» (field example with RSSI in %) is unchanged; it does not depend
  on the ELRS version.
- `link-telemetry-radios.md` keeps "ELRS 3.5.0+" as the minimum version for MAVLink mode (still true).

## 5. Not verified / open questions

1. Release notes were read through a summarising fetch, not verbatim. Items taken only from them: +30 %
   telemetry bandwidth, `TQly` 25 → 100, the list "R9M, PP, Ghost", EdgeTX 2.11.0 for `Arm using`, the 4.1
   year (the page shows "17 Jul"; 2026 is from the task and the FAQ report).
2. The exact EdgeTX menu wording for `Arm using` was not checked in EdgeTX source.
3. Betaflight 2026.6: the cloud-build option name `ELRSV4` comes from the FAQ report; source confirms only the
   define `USE_ELRSV4`.
4. PX4 parameters for MAVLink mode (`SER_TELn_BAUD`, `MAV_0_CONFIG`, `MAV_0_RATE`) and the INAV / Betaflight
   MAVLink steps are quoted from the ELRS MAVLink page, not checked against PX4 1.17 / INAV 9.1 source; the
   module says so ("по странице MAVLink документации ELRS").
5. Hybrid switch layout (6 × 6-position + 16-position) and button-bind hold time (1.5 s) are from the docs,
   not traced in source.
6. The Docs repository is newer than 4.1.0. The multi-file Lua package (ExpressLRS/Lua, EdgeTX 2.12.1+,
   announced 2026-11-08) is described as an alternative to the single `elrs.lua` shipped in the 4.1.0 tree.
7. Outside `content/`, not edited: `assets/widgets/elrs-calc.js` values match 4.1.0, but its comments say
   "ELRS 3.x" and the `kind` label of D250 reads "DVDA (пакет ×2)" (D250 sends each packet 4 times).
8. `content/quiz/ap-setup-scratch.json` question 1 still says "ArduCopter 4.6" (ArduPilot track, not touched).
9. `f-micro-whoop` (planned module) should repeat the SPI-receiver conflict when it is written.
