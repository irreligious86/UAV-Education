# Theory completion plan (approved 2026-11-17)

**Status: approved by Alex on 2026-11-17 ("at your discretion") — phases, wave order and scope as written; the C-priority backlog stays out. Progress is tracked in §9.**

Goal (Alex, 2026-11-17): no holes in the theory first; practice is raised to the same level afterwards.
Language: Russian only until the content is complete (decision 4 in `COURSE-PLAN-STAGE6.md`). Firmware
versions: today's stable releases, old-version fallback marked, renames shown for one or two previous
releases (decision 5 there).

## 1. Where the course is (140 modules)

| Source of evidence | Result |
|---|---|
| Theory depth by word count | no module under 300 words of theory; 29 at 300–600, 97 at 600–1200, 14 above |
| English community FAQ, Nov 2023 – Nov 2026 (`docs/reviews/community-faq-coverage-2026-11.md`) | 119 questions: 57 answered, 39 partly, 23 not. Strong: builds, tuning, failsafe, firmware setup, GPS, companion (41 of 58 answered). Weak: getting started, regulation, careers (3 of 26) |
| Firmware audits (`docs/reviews/{betaflight,inav,ardupilot,px4}-coverage-audit.md`) | Betaflight closed. INAV / ArduPilot / PX4: errors fixed (70 changes); 23 proposed modules and ~33 additions not written |
| Stage 6 plan (`COURSE-PLAN-STAGE6.md` §4) | iterations 1, 1b, 2 done; iterations 3–7 (27 modules) not started |
| Firmware versions | every firmware track is one release behind (ArduPilot 4.6.3 → 4.7.2, PX4 1.15 → 1.17.0, INAV 8.0.1 → 9.1.0, Betaflight 4.5 → 2025.12, ELRS 3.x → 4.1.0) |

Caveat on the community study: reddit.com, view-sorted forum listings and YouTube view counts were not
reachable, so frequency is ranked from search results, forum section sizes and official FAQ coverage, not
from vote counts.

## 2. What "theory complete" means for a module in this plan

Phase 1 modules are written theory-first:
- full theory with a reference table for the topic (every relevant parameter / command, default, range, unit,
  old name where renamed), diagnostics, checklist, references, quiz, numeric tasks where formulas exist;
- **practice is a short check without a simulator run**: a worked calculation, reading a real config / log
  excerpt, or a decision exercise — enough for the validator and for the student to test understanding;
- every fact verified against the source of the target release (or marked with the older release it was
  verified on); an independent fact-check per wave, as before.

SITL labs with real output, «Переход на реальное железо» with acceptance criteria and re-runs on the new
firmware releases are Phase 2.

## 3. Phase 0 — move the course to the current stable releases

Each step: (1) a migration table for the track (old → new name, unit, default, release where it changed, for
the previous one or two releases) as a section of the track's intro module; (2) a sweep of every module, quiz,
task bank and the setup cards for names, defaults and procedures; (3) front matter `firmware:` updated;
(4) pasted lab output that was produced on the old release stays, labelled with that release, until Phase 2
re-runs it.

| Step | Track | From → to | Known size |
|---|---|---|---|
| M1 | ArduPilot | 4.6.3 → 4.7.2 (stable since 2026-07-21) | 101 names removed, 232 added; old names in about 20 files; units moved into names (`RTL_ALT_M`, `WP_SPD`, `ARMING_SKIPCHK`, `PSC_D_*`/`PSC_NE_*`, `SRn` → `MAVn`) |
| M2 | Betaflight | 4.5.3 → 2025.12 (latest patch 2025.12.5) | settings table 683 → 760, arming-flag bits shifted, renames already noted across about 20 modules — collected into one checklist in `bf-intro` |
| M3 | PX4 | 1.15 → 1.17.0 | 35 parameters removed and 236 added in 1.16; further default changes in 1.17 (e.g. `IMU_DGYRO_CUTOFF`); 35 files link to `docs.px4.io/main` |
| M4 | INAV | 8.0.1 → 9.1.0 | 665 → 677 settings; changed GPS defaults; new JavaScript Programming tab; logic-condition numbers unchanged |
| M5 | ExpressLRS | 3.x → 4.1.0 | `link-elrs` rewritten: 3.x → 4.x incompatibility, Gemini, LR1121, binding; known conflict to state: boards with an SPI ELRS receiver run ELRS 3 under Betaflight 2025.12 (ELRS 4 for them arrives in 2026.6) |

Input for the migration: 27 community questions caused by these releases (FAQ report §6.3).

## 4. Phase 1 — close the theory gaps

### 4.0 Immediate corrections (small, safety or legality)

| Item | Where |
|---|---|
| LiPo disposal: salt-water advice replaced by resistor discharge to ~0 V; chargers and parallel charging | `f-power` |
| Regulation update: UK rules from 2026-01-01, FAA (sub-250 g recreational, visual observer for FPV, Part 108 status), FCC Covered List | `f-regulations`, `f-remote-id-security` |
| In-flight disarm / fly-away tree and the recovery reflex; digital "black screen" branch | `diag-troubleshooting` |
| Finding a lost aircraft; post-crash checklist | `ops-field`, `ops-maintenance` |

### 4.0b Systems thinking (added 2026-11-18, requested by Alex)

Assessment side is done: criterion «Системность» in the project rubric and in every track capstone.
Learning side: every module gets a block «Место в системе» — what the module's subject receives from
neighbouring subsystems, what it hands on, and what breaks elsewhere when it is set wrong (with module ids).
The validator requires the block; new modules are written with it from wave 1 on. Existing 140 modules:
one pass after wave 0, track by track.

### 4.1 New modules — newcomer and industry block (community study)

| Id | Title (ru) | Track |
|---|---|---|
| ops-pilot-training | Как научиться летать: симулятор, акро и первые сто батарей | Оператор, before `bf-intro` |
| f-starter-kit | Первый комплект: пульт, очки, аппарат и бюджет | Фундамент |
| f-micro-whoop | Вупы и микро: 1S/2S, AIO, SPI-приёмники и разъёмы | Фундамент |
| link-edgetx | Пульт на EdgeTX: модели, миксы, телеметрия и модули | Оператор |
| per-fpv-footage | Съёмка с FPV: экшн-камера, ND-фильтры, Gyroflow и DVR | Оператор |
| eng-career | Профессия в беспилотниках: роли, навыки, сертификаты, портфолио | Инженер |
| ops-applications | Прикладные сегменты: агро, инспекция, доставка, шоу | Инженер |

### 4.2 New modules — firmware closure (audits)

| Firmware | Priority A | Priority B |
|---|---|---|
| INAV | inav-mixer-vtol, inav-cli-backup, inav-osd-hd, inav-mc-tuning | inav-adjustments, inav-geozones-landing, inav-sensors-extra, inav-telemetry-gcs, inav-led-pinio-beeper |
| ArduPilot | ap-outputs, ap-aux-tune, ap-osd-video, ap-setup-plane | ap-notify, ap-payload, ap-sensors |
| PX4 | px4-safety-return, px4-outputs-servos, px4-hardware-peripherals | px4-console-params, px4-rc-tuning, px4-camera-gimbal, px4-setup-vtol |

23 modules (11 A, 12 B). Titles and scope: §7.1 of each audit.

### 4.3 Additions to existing modules

- Firmware audits: 11 additions for INAV, 11 for ArduPilot, the PX4 list in its §7.2.
- Community study (FAQ report §4, ranks 15–25): VTOL type choice and airspeed sensor (`ap-quadplane`,
  `ap-plane-tuning`); ESP32 as a flight controller (`comp-esp32`); goggles compatibility
  (`link-digital-video`); board choice (`ap-intro`); AI log analysers (`ap-logs`); AIO vs stack and a 5″ build
  order (`f-components-choice`, `el-wiring`); TBS Crossfire and ELRS Backpack (`link-protocols`,
  `link-telemetry-radios`); ground antennas and trackers (`rf-antennas`); compass calibration incl. MagFit
  (`est-sensors`).
- The 29 modules with 300–600 words of theory are reviewed in the same pass as their track; thinnest first:
  `px4-ros2`, `data-python`, `bf-cli-automation`, `eng-ci-configs`.

### 4.4 New modules — Stage 6 remainder (already planned)

| Iteration | Modules |
|---|---|
| 3 Firmware development | fw-build-ap, fw-debug, fw-driver, fw-px4-module, fw-hil-testing |
| 4 Autonomy | aut-planning, aut-behavior, ctl-trajectory, ctl-advanced, aut-swarm |
| 5 Operations and safety | ops-flight-test, ops-risk-sora, ops-human-factors, safety-parachute, sec-threats |
| 6 Links, power, airframes | link-cellular, link-video-codec, pwr-ice-hybrid, heli-trad, vtol-tailsitter |
| 7 Applications and design | ml-dataset, app-agri, app-inspection, app-lidar, des-structures, des-cad, des-manufacturing |

27 modules. The C-priority backlog (des-thermal-ip, fw-upstream, pwr-tether, link-mesh-lora,
ops-airworthiness, app-delivery, app-sar, sim-photoreal, ml-rl-control) stays out of this plan; `career`
from that backlog is replaced by `eng-career`.

### 4.5 Order of waves (3–4 modules in parallel, each wave fact-checked)

| Wave | Content |
|---|---|
| 0 | Phase 0 migration M1–M5, and the immediate corrections of §4.0 |
| 1 | ops-pilot-training, f-starter-kit, f-micro-whoop, link-edgetx |
| 2 | inav-osd-hd, ap-osd-video, px4-safety-return, inav-mixer-vtol |
| 3 | ap-outputs, ap-aux-tune, px4-outputs-servos, inav-cli-backup |
| 4 | ap-setup-plane, inav-mc-tuning, px4-hardware-peripherals |
| 5 | INAV priority B (5 modules) |
| 6 | ArduPilot priority B (3) and PX4 priority B (4) |
| 7 | per-fpv-footage, eng-career, ops-applications, and the additions of §4.3 |
| 8–12 | Stage 6 iterations 3–7 |

Totals: 57 new modules (7 + 23 + 27), about 45 additions, one migration pass over four firmware tracks and
the radio-link module. The course would grow from 140 to 197 modules.

## 5. Phase 2 — practice to the same level (scoped after Phase 1)

Re-run every SITL lab on the target releases (ArduCopter 4.7.2, PX4 1.17, INAV 9.1), replace the short checks
of Phase 1 modules with labs, add «Переход на реальное железо» with acceptance criteria, update lab
checkers. Betaflight SITL could not be built in the authoring environment; its labs stay Python models of the
firmware's maths unless that changes.

## 6. Phase 3 — languages

Ukrainian and English in one pass after the content is complete; the dialect versions and Czech are decided
after that (decision 4).

## 7. Cost estimate (rough)

From the work so far: a theory-first module with its share of an independent fact-check costs about
0.3 million subagent tokens; one 5-hour window gave about 3–3.5 million.

| Part | Estimate |
|---|---|
| Phase 0 migration | about 3 million — one window |
| 57 modules, theory-first | about 17 million — five to six windows |
| about 45 additions | about 3 million — one window |
| **Phase 0 + Phase 1** | **about 23 million — seven to eight windows** |

Phase 2 is not estimated yet; SITL labs cost roughly as much again per module.

## 8. Decisions needed

1. Approve the phases and the wave order, or change the order.
2. Scope: is anything in §4.1–§4.4 unwanted (e.g. careers, footage, application segments, regulation outside
   the course's home region)?
3. The C-priority backlog stays out — confirm.
4. Phase 0 first (recommended, so that new modules are written once, for the target releases) — confirm.

## 9. Progress

| Wave | State |
|---|---|
| 0 — migration M1–M5, immediate corrections | corrections published; M1 ArduPilot, M2 Betaflight, M3 PX4, M5 ELRS published 2026-11-18 (reports `docs/reviews/migration-*-2026-11.md`); M4 INAV in progress; independent fact-check of the migrations pending |
| «Системность» criterion in rubrics | done 2026-11-18 (`411ae49`) |
| «Место в системе» block in 140 modules | approved 2026-11-18, starts after wave 0 |
