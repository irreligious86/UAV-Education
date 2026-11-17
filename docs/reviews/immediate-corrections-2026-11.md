# Immediate corrections (COURSE-PLAN-THEORY §4.0)

Date: 2026-11-17. Scope: six modules in `content/foundation/`. Source of the items: `docs/reviews/community-faq-coverage-2026-11.md`
(§3 rows I2, I4, L1–L7, D1, F6, F7, P1, P3; §4 ranks 5, 10, 11, 14, 19; §6.1 items 4, 8, 9).

Every source below was opened on 2026-11-17. Module structure is unchanged: the same `## ` sections, new `###` subsections
inside them, no new code fences or diagram directives. `scripts/validate_content.py` passes. No quiz or task file was
changed, because no fact that a question relies on changed (checked each question against the edits).

## 1. `f-power` — LiPo disposal, chargers, parallel charging

| Change | Where | Source |
|---|---|---|
| Removed "разряд в солёной воде" from the retirement sentence; it now points to the new procedure | theory «Заряд, хранение, утилизация» | — |
| New subsection «Утилизация LiPo: разряд до нуля через нагрузку»: outdoors on a non-flammable surface; charger discharge, then a resistive load to ~0 V; multimeter check; tape leads; hand in at a collection point | theory | MaxAmps (manufacturer): https://maxamps.com/blogs/news/a-proper-goodbye-disposing-of-your-lipo-battery · US EPA: https://www.epa.gov/recycle/used-lithium-ion-batteries |
| Discharge current C/10, 150 Ω 2 W resistor for 2S–3S, up to 24 h, sand bucket | same | Thunder Power instruction, **read only as a reprint**: https://diydrones.com/profiles/blogs/disposal-of-lipo-batteries (marked secondary) |
| Puffed or damaged pack: do not charge or use; observe outdoors at least 15 minutes; torn, hot or leaking pack gets no load and goes to hazardous waste | same | Team Associated: https://img2.associatedelectrics.com/pdf/cars_and_trucks/shared/LiPo-Safety-Instructions-and-Warnings.pdf · Gens Ace safety manual: https://www.freeflysystems.com/wp-content/uploads/2021/11/Gensace_safety_manual.pdf · EPA (as above) |
| Never puncture | same | Team Associated (as above) |
| Why not salt water: corrosion can stop the discharge; manufacturers that describe it disagree (2 hours vs 2 weeks) | same | Oscar Liang (secondary): https://oscarliang.com/dispose-lipo-battery-safely · Gens Ace manual (2 h, 1:20) · Thunder Power reprint (2 weeks) |
| New subsection «Зарядное устройство и параллельная зарядка»: balance charging, 4.22 V ceiling, up to 2C allowed and 0.5–1C recommended, charge at 10–45 °C, storage 3.80–3.90 V | theory | Gens Ace manual · Team Associated (2C ceiling, ~3.8 V storage) |
| Parallel charging: same cell count, within 0.1 V per cell, main lead before balance lead, charger set to the summed capacity, board current limits, fuses | same | CommonSense RC Paraboard: https://www.commonsenserc.com/product_instructions/PRBRD-JST_instructions.pdf · ProTek RC: https://images.amain.com/images/manuals/ProTekParallelChargeBoard.pdf · Lumenier ParaGuard product page: https://www.getfpv.com/lumenier-paraguard-safe-parallel-charging-board-xt-30-4-port.html |
| Practice item 3, two new diagnostics entries, two checklist lines, nine references | practice, diagnostics, references, checklist | as above |

Worked numbers in the text (resistor 180 Ω for a 6S pack, charger wattage 33 W and ~200 W) are arithmetic from the module's
own formulas, not quotations.

**Conflict to know about:** two manufacturer documents (Gens Ace manual; Thunder Power reprint) still prescribe salt water,
and Thunder Power says a swollen pack must not be discharged electrically at all. The course now recommends the resistive
method (MaxAmps) and states the disagreement openly instead of hiding it.

## 2. `f-regulations` — regulation overview to November 2026

| Change | Where | Source |
|---|---|---|
| FAA bullet rewritten: Part 107 covers every non-recreational flight; recreational flying is an exception with TRUST, CBO guidelines, 400 ft in Class G, LAANC or DroneZone | theory «Как устроены две эталонные системы» | FAA Recreational Flyers (updated 2026-10-29): https://www.faa.gov/uas/recreational_flyers · FAA Getting Started: https://www.faa.gov/uas/getting_started |
| New subsection «Что изменилось к ноябрю 2026: США, Великобритания, ЕС» | theory | below |
| US: no registration for an aircraft of 0.55 lb or less flown exclusively under 49 U.S.C. 44809; Part 107 aircraft register at any weight | same | eCFR 14 CFR 48.15 (current as of 2026-10-22): https://www.ecfr.gov/current/title-14/chapter-I/subchapter-C/part-48 |
| US: purpose, not payment, decides; goodwill and nonprofit flights fall under Part 107 | same | FAA Safety Briefing: https://medium.com/faa/flying-for-fun-but-are-you-sure-54710c5448e6 |
| US: FPV needs a visual observer (recreational: co-located and in direct communication; Part 107: §107.31, §107.33) | same | FAA Recreational Flyers · 14 CFR Part 107: https://www.govinfo.gov/content/pkg/CFR-2025-title14-vol2/pdf/CFR-2025-title14-vol2-part107.pdf |
| US: Remote ID applies to aircraft that need registration, or fly in a FRIA | same | FAA Recreational Flyers |
| US: Part 108 not in force. NPRM 2025-08-07 (90 FR 38212), comments closed 2025-10-06, comment period reopened January 2026 (91 FR 3695), Unified Agenda shows Final Rule stage with target 07/2026; BVLOS remains a Part 107 waiver (§107.205) | same | OIRA Unified Agenda RIN 2120-AL82: https://www.reginfo.gov/public/do/eAgendaViewRule?pubId=202510&RIN=2120-AL82&operation=OPERATION_PRINT_RULE · govinfo listing for 91 FR 3695: https://www.govinfo.gov/app/details/FR-2026-01-28/2026-01644 · 14 CFR Part 107 |
| UK from 2026-01-01: Flyer ID from 100 g; Operator ID from 250 g or from 100 g with a camera (table) | same | CAA registration page: https://www.caa.co.uk/drones/open-category/getting-started-with-drones-and-model-aircraft/registering-to-fly-drones-and-model-aircraft/ · The Drone Code, March 2026: https://www.caa.co.uk/media/ejjbzm40/the-drone-code-march-2026.pdf |
| UK class marks UK0–UK6, legacy aircraft by weight, EU C-marks accepted until 2027-12-31 | same | CAA class marks: https://www.caa.co.uk/drones/open-category/getting-started-with-drones-and-model-aircraft/class-marks/ |
| UK Remote ID: UK1, UK2, UK3, UK5, UK6 from 2026-01-01; UK0 ≥ 100 g with camera, UK4, privately built and legacy ≥ 100 g with camera from 2028-01-01 | same | CAA Remote ID: https://www.caa.co.uk/drones/drone-regulations/policy-programmes/remote-id-rid/ |
| UK: FPV observer, green flashing light at night, insurance from 20 kg and for paid work, overseas registrations not recognised | same | The Drone Code, March 2026 · CAA registration page |
| EU: transition ended 2024-01-01; aircraft without a class label fly in A1 below 250 g or A3 below 25 kg; FPV with a UA observer; FPV races with spectators are Specific | same | EASA Open category FAQ: https://www.easa.europa.eu/en/the-agency/faqs/open-category · EASA FAQ 116508: https://www.easa.europa.eu/faq/116508 |
| Table of official pages to check | same | — |
| New subsection «Рынок и оборудование: FCC Covered List (США)»: 2025-12-22 addition of foreign-produced UAS and UAS critical components; no new equipment authorizations | theory | FCC DA 25-1086: https://docs.fcc.gov/public/attachments/DA-25-1086A1.txt |
| Already-purchased aircraft stay usable; earlier-approved models may still be sold; restriction applies to new models | same | FCC fact sheet: https://docs.fcc.gov/public/attachments/DOC-416839A1.txt |
| Exemptions (Blue UAS Cleared List, Buy American domestic end products) until 2027-01-01; firmware-update waiver until 2027-01-01; toy drones removed 2026-06-15; July 2026 proposals on continued import and marketing | same | DA 26-22: https://docs.fcc.gov/public/attachments/DA-26-22A1.pdf · DA 26-69: https://docs.fcc.gov/public/attachments/DA-26-69A1.txt · DA 26-758: https://docs.fcc.gov/public/attachments/DA-26-758A1.pdf · DA 26-742: https://docs.fcc.gov/public/attachments/DA-26-742A1.pdf |
| Worked 7" example extended (US observer for FPV, UK line); two diagnostics entries; one checklist line; 17 references | theory, diagnostics, checklist, references | as above |

Existing regional content (ICAO/EASA/FAA structure, radio limits, worked example, practice template) is kept.

## 3. `f-remote-id-security` — who must broadcast and since when

| Change | Where | Source |
|---|---|---|
| «Кому и когда обязательно» rewritten as a table for the US, EU and UK with dates, plus what it means for a home-built FPV aircraft | theory | FAA Recreational Flyers · eCFR 14 CFR 48.15 · CAA Remote ID · EASA Open category FAQ (URLs in section 2) |
| Four references added | references | as above |

## 4. `diag-troubleshooting` — tree 6 and the digital "black screen" branch

| Change | Where | Source |
|---|---|---|
| Summary now names six trees | summary | — |
| New subsection «Дерево 5, ветка цифровой системы: чёрный экран в очках»: link procedure and indicator colours, firmware on all devices before linking, activation limits, low-power mode and overheat shutdown, antenna placement, supply ranges | theory | DJI O4 Air Unit Series User Manual v1.0 (copy hosted by a retailer): https://hobbydrone.cz/user/related_files/dji_o4_air_unit_series_user_manual_v1_en.pdf · supply ranges also in the course (`bf-hd-osd-video`) |
| New subsection «Дерево 6. Отключение в воздухе и улёт»: per-firmware table of where the disarm reason is logged | theory | Betaflight 2025.12.1 `fc/core.h`: https://raw.githubusercontent.com/betaflight/betaflight/2025.12.1/src/main/fc/core.h · ArduPilot Copter-4.7.2 `AP_Logger.h`, `AP_Arming.h`, `LogStructure.h`: https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_Logger/AP_Logger.h , https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/libraries/AP_Arming/AP_Arming.h · INAV 9.1.0 `fc/fc_core.h`, `io/osd.c`, `blackbox/blackbox.c`: https://raw.githubusercontent.com/iNavFlight/inav/9.1.0/src/main/fc/fc_core.h · PX4 v1.17.0 `VehicleStatus.msg`: https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.17.0/msg/versioned/VehicleStatus.msg |
| Cause branches: failsafe, switch, runaway takeoff and crash detection, desync, EKF failsafe, GPS glitch, auto-disarm, brownout | same | Betaflight 2025.12.1 `fc/core.c`, `flight/pid.c`, `flight/gps_rescue_multirotor.c`, `cli/settings.c` · ArduPilot Copter-4.7.2 `ArduCopter/crash_check.cpp`, `ArduCopter/Parameters.cpp`: https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.2/ArduCopter/crash_check.cpp · PX4 v1.17.0 `failure_detector_params.c`, `commander_params.c`: https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.17.0/src/modules/commander/failure_detector/failure_detector_params.c · course modules `bf-arming-safety`, `bf-blackbox`, `ap-logs`, `ap-ekf`, `nav-resilience`, `px4-setup-scratch` |
| Recovery reflex: one switch to a mode without GPS, manual throttle, gain margin, when to disarm | theory | course modules (`ap-setup-scratch` step 12, `px4-setup-scratch` mode list); operating guidance, no external numbers |
| New practice subsection «Отрепетировать рефлекс восстановления» (bench, SITL, field) | practice | — |
| Three diagnostics entries, two checklist lines, eight references | diagnostics, checklist, references | as above |

Parameter names are written in their current form and were checked in the tagged sources: `FS_CRASH_CHECK`, `FS_EKF_ACTION`,
`FS_EKF_THRESH`, `DISARM_DELAY` (Copter-4.7.2); `crash_recovery`, `failsafe_procedure`, `auto_disarm_delay`,
`landing_disarm_threshold` (Betaflight 2025.12.1); `FD_FAIL_R`, `FD_FAIL_P`, `FD_FAIL_R_TTRI`, `FD_FAIL_P_TTRI`,
`COM_LKDOWN_TKO`, `COM_KILL_DISARM`, `COM_DISARM_LAND`, `COM_DISARM_PRFLT`, `NAV_RCL_ACT`, `CBRK_FLIGHTTERM` (PX4 v1.17.0).

## 5. `ops-field` — finding a downed aircraft

| Change | Where | Source |
|---|---|---|
| New subsection «Поиск упавшего аппарата»: preparation, first minute, sources of the last position, search pattern, time budget against battery state, recovery safety | theory | EdgeTX manual, SD Logs: https://manual.edgetx.org/bw-radios/model-select/special-functions · EdgeTX manual, LOGS folder: https://manual.edgetx.org/color-radios/radio-settings/storage · course modules `bf-led-buzzer` (beeper, DShot beacon), `bf-gps-setup` (OSD coordinates, CRSF GPS telemetry), `f-power` (BEC budget) · Team Associated and Gens Ace manuals (URLs in section 1) |
| New practice subsection «Проверка готовности к поиску» | practice | — |
| Diagnostics entry "упавший аппарат не найден" extended; one checklist line; four references | diagnostics, checklist, references | as above |

The drift estimate v·√(2h/g) and the time-budget example (8.6 Wh, ~10 W and ~3 W loads) are arithmetic. Search spacing
figures (5–10 m, 20–30 m) are working guidance without an external source.

## 6. `ops-maintenance` — post-crash checklist

| Change | Where | Source |
|---|---|---|
| Battery-retirement sentence now points to the `f-power` disposal procedure | theory «Ресурс батарей» | section 1 |
| New subsection «Чек-лист после аварии»: battery first and quarantine, frame, arms, motors (bearings, bell, shaft, magnets, screws), props, wiring, connectors, FC and gyro mount, antennas and GPS; re-test with props off | theory | battery rows: Team Associated (15-minute observation), Gens Ace manual (no use of damaged or swollen cells, 3.0 V minimum), module's own retirement criteria; mechanical rows: workshop practice consistent with `f-frame-mech` and the module's inspection schedule, no external numbers |
| One diagnostics entry, one checklist line, two references | diagnostics, checklist, references | as above |

## 7. Not verified from a primary source

| Item | Status in the course |
|---|---|
| FAA Remote ID page (`faa.gov/uas/getting_started/remote_id`) and FAA Part 107 page (`faa.gov/uas/commercial_operators`) could not be opened in this session | The existing sentence "обязательно для большинства полётов с марта 2024" and the Standard RID / broadcast module wording were kept as they were and **not re-verified**. The registration → Remote ID link and FRIA come from the FAA Recreational Flyers page |
| "Monetised content needs Part 107" | No FAA page opened says this in those words. The module states the FAA purpose test and says so explicitly |
| Part 108: date the final rule went to OIRA (reported as 2026-07-10) and the statutory deadline (reported as 2026-12-07) | Secondary sources only; **left out**. The module says no published final rule was found on 2026-11-17; the Federal Register API could not be queried, so this rests on the Unified Agenda entry and on web searches |
| FCC Covered List web page (`fcc.gov/supplychain/coveredlist`) and DA 26-761 could not be opened | The module uses the public notices and the fact sheet. Whether the July 2026 proposals (DA 26-742, DA 26-758) were adopted is **not stated**; the module tells the reader to check |
| EASA Open category web page (`.../open-category-low-risk-civil-drones`) could not be opened | EASA FAQ pages used instead |
| Thunder Power disposal instruction | Read only as a reprint; marked secondary in the module |
| Lumenier ParaGuard | Read on the GetFPV product page, not in a separate manual |
| DJI O4 manual | Read as a copy on a retailer's site, not on dji.com |
| Walksnail, HDZero, OpenIPC bind procedures; goggles ↔ air unit compatibility table | **Left out**; the module refers to the manufacturer's instructions |
| UK: insurance and age rules beyond what the Drone Code states; UK1–UK6 technical requirements | Left out |
| EdgeTX: whether the telemetry screen keeps the last GPS value after link loss | Left out; the module relies on the last row of the SD log. That the CSV contains GPS columns follows from "radio and telemetry values" in the manual and is checked in the new practice step |
| Betaflight Blackbox Explorer: how the disarm reason is displayed | Not checked; the module says only that the disarm event carries the reason code (firmware source) |
