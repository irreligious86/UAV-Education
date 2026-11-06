# UAV Student — Roadmap

Living plan. Updated as phases land. Detailed rules live in `PROJECT-DIRECTIVES.md`;
this file only says **what is next and why**.

## Principles

1. **Content over infrastructure.** Ten honest articles beat thirty pretty stubs.
2. **Write from real cases.** Every article is grounded in something we actually configured,
   broke or measured (logs, diffs, numbers), plus primary docs. No retelling of docs.
3. **Honest status.** `published` = real content; `planned` = visible "coming soon" slot;
   `draft` = hidden. The validator and CI enforce it.
4. **Verify, don't assume.** After every change: re-read values, rebuild, check links.

## Status (2026-11-07)

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
- [ ] `ap-intro` + new `ap-sitl` — ArduPilot via SITL, from the ardupilot-lab project
- [ ] `ap-lua` — Lua fault-injection applets used in SITL (sensor/motor chaos, gated by RC switches)
- [ ] New `ap-quadplane-tilt` — tilt-rotor QuadPlane bring-up: channel mapping, DCM-only, the "motor on a servo channel" incident (expert level)
- [ ] `bf-pid` — practical tuning workflow with A/B profiles (CRISP/COOL/SHARP/FLOAT) and stick-response metrics
- [ ] `bf-modes-osd`
- [ ] `comp-esp32` — ESP32 companion: EdgeTX Lua ↔ ESP32 serial (TX16S companion project)
- [ ] `tools-overview`

## Phase 2 — Architecture (needs owner decision)

Problem: one 185 KB `index.html` that every article rewrites.

Options under discussion (see chat): modular static site vs. adding backend services.
Tentative direction until decided:
- [ ] One generated page per article + shared layout (still zero-framework, still GitHub Pages)
- [ ] Apply the Ground Control design system tokens
- [ ] Offline PWA (service worker), reusing the Report UAV approach
- [ ] Client-side search over a generated JSON index

## Phase 3 — Interactivity

- [ ] Quiz mode: JSON question bank per article ("question → answer → explanation")
- [ ] Widgets as standalone Web Components: PID step-response simulator, filter frequency response, ELRS packet rate ↔ latency calculator
- [ ] 3D attitude demo (three.js)

## Phase 4 — Lab track

- [ ] SITL exercises with checkable outcomes: load `.param`, fly a mission, compare the log to a reference

## Backlog / ideas

- Optional backend for progress and quiz results (only if Phase 2 decision calls for it)
- English version of the site
