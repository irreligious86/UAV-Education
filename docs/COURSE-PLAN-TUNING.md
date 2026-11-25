# Tuning, chip-tuning and personalization — course plan

**Status: approved by Alex on 2026-11-24 ("план внедрения всех этих тем в курс"). The brochure (textbook) is postponed.
Videos are published outside the repo and are not embedded; renderer sources live in `tools/shorts/`.**

Goal: every topic of the short-video series gets an engineering-depth home in the course. Existing modules are
deepened wherever a topic already has a home; new modules are created only where there is none.

## Rules for every wave

- Facts are checked against source code of the pinned versions: Betaflight 4.5.3 (Viking drones; 2025.12.5 noted where it differs),
  Bluejay, AM32 2.22, ExpressLRS 4.1.0, EdgeTX 2.12.5.
- Rules of thumb (motor imbalance thresholds, LQ colour bands, …) are labelled as course guidelines, never as firmware values.
- Viking's drones are referenced as cases only; no paths to the owner's PC.
- Two writer agents per wave, then an independent fact-check agent that does not write content, then register, publish, one commit per wave.

## Waves

| Wave | Module | Kind | Content |
|---|---|---|---|
| 0 | `tools/shorts/`, this file | infra | renderer sources and plan |
| 1 | `bf-motor-balance` | new | Quad X numbering vs `motor[0..3]`, medians on steady segments, CG / weak motor / prop-vs-motor swap / yaw diagonal imbalance; Python lab over blackbox CSV; viking10 case |
| 1 | `bf-rates-rc` | deepen | Actual rates formula with plot; feedforward pipeline from `rc.c` (smoothing, jitter reduction, boost, max rate limit, transition); RC smoothing auto factor and its link to ELRS packet rate; `debug_mode = FEEDFORWARD` lab |
| 2 | `bf-pid-reg-in-bf`, `bf-rpm-filter` | deepen | dynamic idle as an RPM loop (DShot telemetry, overrides `dshot_idle_value`), `thrust_linear`, `vbat_sag_compensation` (Li-Ion), TPA mode D / breakpoint / `tpa_low`, anti-gravity, throttle boost; worked problems |
| 2 | `bf-tuning-method` | new | A/B method: one variable, control flight, repeatable flight program, comparing two logs (gyro noise, tracking error, motor temperature), minimal statistics; lab script; viking / viking2 case |
| 3 | `f-esc-firmware` | deepen | Bluejay and AM32 settings tables from source, symptom → setting cheat sheet, ESC beacon vs DShot beacon |
| 3 | `bf-custom`, `link-elrs` | deepen | Cloud Build option groups, Core Only, Custom Defines, verifying a build via `status`; ELRS UID derivation, model match, regulatory domains and LBT, packet-rate sensitivity → link margin (`rf-link-budget`), telemetry ratio |
| 4 | `bf-led-buzzer`, `bf-failsafe` | deepen | `rxfail` + BEEPER mode, RX_LOST / RX_LOST_LANDED / WAS_EVER_ARMED, finding a downed quad, LED profiles and strip current |
| 4 | `bf-modes-osd`, `bf-adjustments`, `bf-hd-osd-video` | deepen | `osd_*_pos` bit layout, OSD profiles on a switch (`adjrange` function 33), warning / stats masks, boot logo 288×72, HD OSD fonts and logos per system |
| 5 | `tx-lua-widgets`, `link-edgetx` | new + links | script types, widget lifecycle, LVGL API (2.12), CRSF sensors, simulator debugging; project: LinkBox widget |
| 6 | cross-links, curriculum, glossary | finish | `{{lesson:…}}` cards, curriculum tracks, ~25 glossary terms, i18n mirrors, full fact-check pass |

## Progress

| Wave | Status | Commit |
|---|---|---|
| 0 | done | 680c34e5 |
| 1 | done: bf-motor-balance (new), bf-rates-rc (deepened); both fact-checked | 13cf75e9 + this |
