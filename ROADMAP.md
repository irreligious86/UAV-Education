# UAV Student — Roadmap

Living plan. Updated as phases land. Detailed rules live in `PROJECT-DIRECTIVES.md`;
this file only says **what is next and why**.

> **2026-11-08 — Course Plan v3 adopted.** The program structure, principles and
> implementation phases now live in [`docs/COURSE-PLAN.md`](docs/COURSE-PLAN.md),
> built from two external reviews in `docs/reviews/`. Sections below that
> describe tracks are superseded by it.

## Principles

1. **Content over infrastructure.** Ten honest articles beat thirty pretty stubs.
2. **Write from real cases.** Every article is grounded in something we actually configured,
   broke or measured (logs, diffs, numbers), plus primary docs. No retelling of docs.
3. **Honest status.** `published` = real content; `planned` = visible "coming soon" slot;
   `draft` = hidden. The validator and CI enforce it.
4. **Verify, don't assume.** After every change: re-read values, rebuild, check links.

## Status (2026-11-07, see the course map on the site for live numbers)

| Section | Published | Planned |
|---|---|---|
| Betaflight | 9 | 3 |
| INAV | 1 | 4 |
| ArduPilot | 0 | 5 |
| PX4 | 2 | 3 |
| Companion | 0 | 4 |
| Радиолинк (new) | 3 | 0 |
| Инструменты | 0 | 1 |

## Phase 0 — Hygiene ✅ done

- [x] Stub articles moved from fake `published` to `planned`; honest progress bars
- [x] Strict validator: no placeholders (`example.com`, stub text), minimum length, front matter ↔ manifest status
- [x] Reference parser fixed (quoted YAML urls, pipe refs without `- `)
- [x] Legacy and duplicate scripts removed; single `publish.bat` / `publish.sh`
- [x] GitHub Actions CI: validate, `index.html` freshness, broken local links

## Phase 1 — Content from real experience 🟡 in progress

Done:
- [x] Радиолинк: `link-protocols`, `link-elrs`, `link-vtx`
- [x] Betaflight: `bf-failsafe`, `bf-rpm-filter` (10" whistle case), `bf-cli-automation`

Next (priority order):
- [x] Foundation track: `f-physics`, `f-power`, `f-motors-esc`, `f-fc-sensors`, `f-safety`
- [x] `ap-intro` + `ap-sitl` — ArduPilot via SITL, from the ardupilot-lab project
- [x] `ap-lua` — Lua fault-injection applets used in SITL (sensor/motor chaos, gated by RC switches)
- [x] `ap-heavy` — X8 / OctaQuad: coaxial losses, thrust curve, vibrations, motor-failure testing
- [x] `ap-quadplane` — tilt-rotor QuadPlane bring-up: channel mapping, DCM-only, the "motor on a servo channel" incident (expert level)
- [x] `bf-pid` — A/B profiles (CRISP/COOL/SHARP/FLOAT) and stick-response metrics
- [x] `bf-modes-osd`
- [x] `ap-missions`, `ap-ekf`, `ap-logs` — Autonomy track complete
- [x] `comp-mavlink`
- [x] Engineer track complete: `comp-intro`, `comp-esp32` (TX16S companion), `comp-raspberry`, `ap-companion` (GUIDED offboard), `bf-custom`
- [x] `tools-overview` — **core curriculum complete (34/34)**
- [x] `related` modules shown on module pages

## Phase 2 — Course structure and architecture ✅ done (except PWA)

Decision (2026-11-07): **modular monolith on static hosting** now, ready to move data to our own server later.
Priority: a well-structured learning program.

- [x] Course map `data/curriculum.json`: 5 core tracks (Foundation → Operator → Integrator → Autonomy → Engineer),
      electives (INAV, PX4), prerequisites, objectives, hours, capstones on real hardware — approved
- [x] One page per module (`m/<id>.html`), reference by stack (`ref/`), hand-written pages (`pages/`);
      old `index.html#<id>` links redirect to module pages
- [x] Home = course map with per-track progress
- [x] Progress behind an async `ProgressStore` interface (localStorage now, server later)
- [x] Ground Control UI as a pinned git submodule (`lib/ground-control-ui`, v0.2.2);
      gaps found here are fixed upstream (v0.2.0: namespace + content primitives, v0.2.1: `[hidden]` fix, v0.2.2: card colour)
- [x] Static API: `api/v1/curriculum.json` — the contract a future server will serve
- [x] Quizzes: `<uav-quiz>` + JSON banks for all 34 core modules (5–7 questions each, shuffled, explained, result in ProgressStore)
- [x] Labs with acceptance criteria on every core module (checklist, state in ProgressStore); capstone pages `cap/<id>.html` with deliverables and criteria
- [x] Fails journal generated from every module's diagnostics (120+ cases); glossary from `data/glossary.json` (68 terms, each linked to its module)
- [x] Client-side search (`pages/search.html`) over `api/v1/search.json`: modules, terms, capstones; identifiers like `rpm_filter_min_hz` searchable
- [x] `ARCHITECTURE.md`: layers, data contracts, migration path to own server
- [x] Offline PWA: generated `sw.js` precaches the whole site (versioned by content hash), `manifest.webmanifest`, status line in the footer (2026-11-08)

## Phase 2b — Structure and grading (2026-11-08) ✅

- [x] Learning paths per firmware: `path/betaflight|inav|ardupilot|px4.html` with stages; chooser on home; step position on module pages
- [x] Grading model: module score (quiz 40 / lab 60), earned vs self-marked status, group scores, capstone status
- [x] `pages/progress.html`: transcript with per-module quiz/lab/score/status, export/import/reset

## Content status (2026-11-08, evening)

**Course Plan v3 phases 1–7 complete: all 84 modules written** (8 tracks in 4 stages + INAV/PX4 electives), 84 quizzes, labs with criteria on every module, 8 capstones with good/bad rubrics and an engineering-folder deliverable, 116 glossary terms, 47 formulas, 6 interactive widgets, starter repositories in `examples/`. Every pre-v3 module went through a depth pass (mechanisms, numbers, worked examples, extended diagnostics, source-verified parameter names).
Remaining content work: owner review and first-student feedback (Phase C).

## Phase 3 — Interactivity

- [x] Widgets as standalone Web Components: `uav-pid-sim` (PID modules), `uav-filter-response` (filters), `uav-elrs-calc` (ELRS); `{{widget:name}}` in Markdown; JS syntax check in CI
- [ ] 3D attitude demo (three.js)

## Phase 4 — Lab track

- [ ] SITL exercises with checkable outcomes: load `.param`, fly a mission, compare the log to a reference

## Backlog / ideas

- Optional backend for progress and quiz results (only if Phase 2 decision calls for it)
- English version of the site
