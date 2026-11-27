# Selection-rules audit — November 2026

Read-only audit, 2026-11-22. Scope: `content/foundation/*.md` (all 22), `content/electronics/*.md` (all 11), `content/link/*.md` (6), `content/estimation/est-sensors.md`, `est-gnss.md`, `content/design/*.md` (4), and `content/betaflight/` `bf-pid`, `bf-filters`, `bf-rpm-filter`, `bf-rates-rc`, `bf-failsafe`, `bf-ports`.

**What was looked for.** Every place where the reader must *choose* something — a component, value, protocol, setting, size, rate, threshold, connector, frequency, battery, prop, KV, antenna, channel or filter cutoff — and the module:

- **R:** gives no rule for choosing;
- **W:** gives a rule but not the reason for it;
- **C:** gives one value without saying which aircraft class it is for;
- **S:** gives a range or a list of options with no recommendation or starting point;
- **V:** gives no way to check the choice afterwards;
- **X:** contradicts another module.

**Reference quality.** The subsection «Частота ШИМ: как выбрать под аппарат» in `f-esc-firmware.md` (lines 49–130). It goes mechanism → table by aircraft class with a source or «оценка» label on each number → procedure → what to check afterwards. A finding is closed when the module reaches that pattern, or when it points to a module that does and gives a one-line summary.

**Severity.**
- **high:** the reader is likely to choose wrong or get stuck.
- **medium:** the reader has to look elsewhere.
- **low:** nice to have.

**«Elsewhere».** If another module already holds the rule, it is named, and the fix is a pointer plus a one-line summary. «None» means no module in the course has the rule. In that case the entry names the kind of source that would settle it. Numbers are **not** proposed from memory.

Second class (section T at the end): terms used without explanation at first use in L1 modules, and English calques where a Russian term should be used. The rule in `/tmp/claude-0/work/s6/SPEC.md` "Terminology" is applied to «петля», and the same logic is extended to other calques as candidates.

Line numbers are those of the files on 2026-11-22.

## Summary

**118 selection findings: 4 high, 34 medium, 80 low.** On top of these, 25 terminology rows: T1 has 16 terms (5 medium, 11 low); T2 has 9 calque rows (2 medium, 6 low, 1 checked with no violation).

**Counting rules.**
- A finding rated «low-medium» in the text is counted as low.
- A defect that repeats in several modules is counted once, at the module where the fix belongs; the other places are marked «merged» or «same defect».
- Verified no-finding notes are not counted.

**Stage** is the stage of the Betaflight path in `data/curriculum.json`: 1 Основа, 2 Первый полёт, 3 Настройка с нуля, 4 Электроника и радио, 5 Конструктор, 6 Настройка по данным. «—» means the module is only on other paths or tracks.

| Module | Level | Stage | High | Medium | Low |
|---|---|---|---|---|---|
| f-physics | L1 | 1 | 0 | 3 | 0 |
| f-mechanics | L1 | 1 | 0 | 1 | 1 |
| f-aero-props | L2 | 1 | **1** | 2 | 2 |
| f-electricity-101 | L1 | 1 | 0 | 1 | 2 |
| f-power | L1 | 1 | **1** | 1 | 4 |
| f-motors-esc | L1 | 1 | 0 | 2 | 4 |
| f-fc-sensors | L1 | 1 | 0 | 1 | 2 |
| f-frame-mech | L2 | 1 | 0 | 2 | 2 |
| f-safety | L1 | 1 | 0 | 0 | 2 |
| f-regulations | L1 | 1 | 0 | 0 | 0 |
| f-components-choice | L1 | 1 | 0 | 2 | 3 |
| f-starter-kit | L1 | 1 | 0 | 0 | 2 |
| f-micro-whoop | L2 | 1 | 0 | 4 | 3 |
| eng-method-101 | L1 | 1 | 0 | 1 | 1 |
| ops-pilot-training | L1 | 2 | 0 | 0 | 1 |
| bf-ports | L1 | 2 | 0 | 0 | 2 |
| link-protocols | L1 | 2 | 0 | 0 | 1 |
| bf-failsafe | L1 | 2 | **1** | 1 | 2 |
| link-edgetx | L2 | 2 | 0 | 1 | 1 |
| link-elrs | L2 | 2 | 0 | 0 | 4 |
| link-vtx | L2 | 2 | 0 | 1 | 3 |
| link-digital-video | L2 | 2 | 0 | 0 | 1 |
| ops-field | L2 | 2 | 0 | 0 | 2 |
| ops-case-studies | L1 | 2 | 0 | 1 | 0 |
| diag-troubleshooting | L1 | 2 | 0 | 0 | 0 (1 merged into PHY-1) |
| el-power-design | L2 | 4 | 0 | 3 | 2 |
| el-battery-packs | L2 | 4 | **1** | 1 | 2 |
| el-wiring | L1 | 4 | 0 | 2 | 1 |
| el-measure | L2 | 4 | 0 | 0 | 0 |
| el-emi | L2 | 4 | 0 | 1 | 1 |
| el-peripherals | L2 | 4 | 0 | 0 | 1 |
| rf-antennas | L2 | 4 | 0 | 0 | 2 |
| rf-link-budget | L2 | 4 | 0 | 0 | 2 |
| des-sizing | L3 | 5 | 0 | 0 | 1 |
| des-thrust-stand | L2 | 5 | 0 | 0 | 2 |
| bf-filters | L2 | 6 | 0 | 1 | 1 |
| bf-rpm-filter | L2 | 6 | 0 | 0 | 3 (1 merged into MOT-1) |
| bf-pid | L2 | 6 | 0 | 0 | 2 |
| bf-rates-rc | L2 | 6 | 0 | 1 | 2 |
| f-esc-firmware | L2 | — | 0 | 0 | 0 (reference quality; 2 merged into MOT-1/2) |
| ops-weather | L2 | — | 0 | 0 | 2 |
| ops-maintenance | L2 | — | 0 | 0 | 1 |
| f-remote-id-security | L3 | — | 0 | 0 | 1 |
| el-redundancy | L2 | — | 0 | 0 | 1 |
| el-dronecan | L3 | — | 0 | 0 | 0 |
| el-kicad | L3 | — | 0 | 0 | 0 |
| link-telemetry-radios | L2 | — | 0 | 0 | 2 |
| est-sensors | L2 | — | 0 | 0 | 1 |
| est-gnss | L2 | — | 0 | 1 | 2 |
| aero-stability | L3 | — | 0 | 0 | 1 |
| ctl-allocation | L3 | — | 0 | 0 | 2 |
| **Total** | | | **4** | **34** | **80** |

**Pattern.** The defects concentrate in stage 1, which is the first thing a beginner reads.
- The L1 foundation modules name a parameter and give a 5"-6S value or a qualitative rule. The class-aware rule, when it exists, lives in a later L2/L3 module: `des-sizing` for KV, `bf-rpm-filter` for low-rpm aircraft, `bf-filters` for DShot speed and loop rate, `bf-modes-osd` for battery warnings.
- Second recurring defect: the same threshold stated differently in 3–5 modules — hover throttle, T/W for freestyle, DShot error rate, cell imbalance, connector current, RSSI warning margin.
- Modules written recently are at or near target quality: `f-esc-firmware`, `f-starter-kit`, `ops-pilot-training`, `link-elrs`, `link-digital-video`, `bf-rpm-filter`, `bf-filters`, `des-sizing`.

## Status of the medium findings — 2026-11-27

The 4 high findings were fixed in commit 7f293211. This pass re-checked the 34 medium selection findings against the current text and fixed what was still open. Line numbers below are those of the files after this pass. Translations: where the changed line exists in `i18n/{en,uk,uk-galych}/content`, the same fact was changed there; new standalone paragraphs exist only in the Russian source (the translations were already stale before this pass, `check_i18n.py`: 0/176 current). The T-section medium rows (T1-1, T1-5, T1-7, T1-8, T1-9, T2-3, T2-4) are terminology, not selection findings, and were not part of this pass.

**Totals:** 25 fixed in this pass, 9 already fixed by earlier commits (no longer applies), 0 rejected.

| ID | Status | Edit (file:line) | Source |
|---|---|---|---|
| PHY-1 | fixed | `f-physics.md:77` rule props in / props out by class + 2 references; `yaw_motors_reversed = ON` only flips the yaw-PID sign, direction is changed in the ESC (aligned with `bf-motor-balance.md:122`; FC-sel E1); pointer in `diag-troubleshooting.md:55` | Betaflight 2025.12.5 `flight/mixer_init.c` (`YAW_MOTORS_REVERSED 0`), `flight/mixer.c`; Oscar Liang «Props In vs Props Out» (updated 2024-01-06) |
| PHY-2 | fixed | `f-physics.md:32` and a new row «Вупы, тупики, 3–3.5" фристайл» in the class table (оценка, as 5" freestyle; FC-sel I1) (cinewhoop → class table; wing: thrust ≈ weight / L/D, criterion in `aero-wing`; one canonical list); `f-motors-esc.md:74` T/W ≥ 5 → ≥ 6, arithmetic redone (4200 g, 1050 g per motor); `assets/widgets/tw-calc.js:53` T/W tag now critical < 2, caution < 2.5 (was 1.6 / 2.2) | course bands in `f-physics`; limit T/W 2 in `f-components-choice` |
| PHY-3 | no longer applies | fixed in 7f293211: `f-physics.md:34–70` hover throttle from T/W on the course curve, class bands; `f-mechanics`, `ops-weather`, `eng-method-101` aligned | — |
| MEC-1 | fixed | `f-mechanics.md:39` table: parameter, default, mechanism, start, check (BF start ~100, the source comment's 40 is knowingly low; AP boost uses the **current** lean, cos ≥ 0.1, fades above 60° — FC-sel I3 and nit); diagnostics `:95` | Betaflight 2025.12.5 `cli/settings.c:984–985`, `flight/imu.c:727–764`, `fc/core.c:178–179`; INAV 9.1.0 `fc/settings.yaml`, `fc/fc_core.c:864–884`; ArduPilot `AC_AttitudeControl.cpp:55–60, 1062–1070` (`thrust_angle_rad` = current lean), `AC_AttitudeControl_Multi.cpp:373–390`, `mode_stabilize.cpp:60`, `mode_acro.cpp:67` |
| AER-2 | fixed | `f-aero-props.md:41` procedure (start prop from the motor table or course examples, compare a neighbour by g/W at hover thrust and full-throttle current, direction by task); lab reference reworded (step 2 has 7×4 only as a fallback) | course examples (`f-motors-esc` 5.1×3, `f-aero-props` 7×3.5, MN4006 15×5); direction labelled «оценка курса» |
| AER-3 | no longer applies | fixed in 7f293211: `f-aero-props.md:133` and `:91` compare with the **continuous** rating (maximum only if continuous is not given), same as `des-sizing` and `f-components-choice` | — |
| ELE-1 | no longer applies | fixed in 7f293211: `f-electricity-101.md:48` points to the `f-power` rule (capacity from average current, label C as a filter, R_cell ≤ 0.5 / I_peak) | — |
| POW-1 | fixed | `f-power.md:34` numbers: average ≤ 1.5C per cell, peak ≤ 0.6 × datasheet continuous per cell, worked for P42A, check; 1.5C labelled «ориентир курса» (not a datasheet figure, FC-sel I9); `el-battery-packs.md:37` aligned (was «≤ 1–2C»); `f-components-choice.md:93`; quiz `el-battery-packs.json` explain | Molicel P42A datasheet values already cited in `el-battery-packs`; 1.5C and 0.6 are the course rules of `el-battery-packs` |
| MOT-1 | fixed (with RPM-3) | `f-motors-esc.md:93` rule DShot speed ↔ PID loop ↔ MCU, wrong pointer removed; `f-esc-firmware.md:232` pointer | Betaflight 2025.12.5 `config/config.c:585–646` (`USE_PID_DENOM_CHECK`, `motorUpdateRestriction` 100 µs DShot300, ×2 with bidir), `target.h` of STM32F405/F411/G47X, APM32F405/F407 (`USE_PID_DENOM_OVERCLOCK_LEVEL 2`) |
| MOT-2 | fixed (with ESC-1) | `f-motors-esc.md:65` start = firmware default for every class, raise one step only on evidence (eRPM dip), check = 3 punch-outs; pointer to the `f-esc-firmware` tables, which already hold the Bluejay / AM32 values from source | `f-esc-firmware` tables (Bluejay, AM32 source); «7" and up» labelled «оценка курса» |
| FCS-1 | fixed | `f-fc-sensors.md:54` BMI270 runs at 3.2 kHz in Betaflight by default, 6.4 kHz without hardware LPF with `gyro_hardware_lpf = EXPERIMENTAL` (was «6.4 кГц»; FC-sel I7); `:56` loop-rate rule by MCU and gyro, buyer consequence, check via `status` | Betaflight 2025.12.5 `drivers/accgyro/gyro_sync.c:60–72` (3200 Hz default, 6400 with `GYRO_HARDWARE_LPF_EXPERIMENTAL`), `config/config.c`, `cli/cli.c:4896` (`status` line) |
| FRM-1 | fixed | `f-frame-mech.md:40` contradiction removed: start with grommets on 5", hard mount only on evidence; `:49` f₀ measured by tap test, target 50–83 Hz for 5" (the earlier «60–80» in the same paragraph unified to 50–83) | the module's own window diagram (`chart-fc-damper-window`) and tap-test method; measurement labelled «метод курса» |
| FRM-2 | fixed | `f-components-choice.md:45` 5" 4–5 mm; 7" 5 mm is in the danger zone, thickness alone does not fix it, rule = tap test → notch or mounting point | `f-frame-mech` numbers and worked example. Frame geometry (X / stretched X / H / deadcat) still has no rule — no primary source in hand; left open as a low item |
| CMP-1 | no longer applies | fixed in 7f293211: `f-components-choice.md:48` class bands from `f-physics`; KV part fixed with AER-1 | — |
| CMP-5 | fixed | `f-components-choice.md:59` band and video by task with pointers to `link-elrs` and `link-digital-video`; «900 МГц для 5+ км» removed | `link-elrs` «Выбор режима под задачу», «Регуляторные домены»; `link-digital-video` «Как выбирать» |
| WHP-1 | fixed | `f-micro-whoop.md:153` start procedure (static idle → slowest-motor rpm at zero throttle → `dyn_idle_min_rpm`), check by `debug_mode = DYN_IDLE` (debug[3] = min rps × 10, `mixer.c:234`); table cell `:135` | mechanism and check from `bf-features-tour` (Betaflight 2025.12 `mixer.c`, `mixer_init.c`); doc value 30–40 for 5"; the whoop procedure is labelled «оценка курса» |
| WHP-3 | fixed (with RPM-1) | `f-micro-whoop.md:154` rule rewritten after FC-sel I4: `rpm_filter_harmonics` drops only from the top, so a single harmonic is switched off by `rpm_filter_weights` = 0; blade-pass = harmonic number = blade count (2/3 blades inside the filter, 4 blades = 4th, outside it — dynamic notch); notches = motors × N per axis (X8 ×2); check by spectrogram; table cell; `bf-rpm-filter.md:106` same rule, «ослабить до 50–80» limited to non-blade-pass harmonics | Betaflight 2025.12.5 `flight/rpm_filter.c:97–101` (`notch[axis][motor][harmonic]`, harmonics 0…N−1); blade-pass mechanism labelled «оценка курса» |
| WHP-4 | no longer applies | fixed in 7f293211: `f-micro-whoop.md:160` reason (8 % sag on 1S), check (rest 3.6–3.7 V, recharge ≤ 0.8), «опускать в последнюю очередь» explained; `f-power` canonical table row for 1S | — |
| WHP-5 | fixed | `f-micro-whoop.md:48` where to start in the KV range (middle; up for light/race, down for heavy), pointer to `f-aero-props` table (fixed in 7f293211) | Oscar Liang KV table already cited in `f-aero-props` |
| ENG-1 | no longer applies | fixed in 7f293211: `eng-method-101.md:39` R-02 criterion «газ ≤ 63 %», reason at `:44` | — |
| CAS-1 | fixed | procedure was added to `f-power.md:98` (step 6) in 7f293211; this pass added the pointer in `ops-case-studies.md:76` | — |
| PWR-1 | fixed | `el-power-design.md:66` manufacturer minimums (Holybro 35 V noted as the manufacturer's minimum, not a margin), class table, when to add a second capacitor, check | FETtec «How to use caps and FETtec Spike Absorber» (6S: ≥ 470 µF 50 V); Holybro Tekko32 F4 4in1 50A spec (1000 µF 35 V included, «highly recommended for 6s»); whoop row labelled «оценка» |
| PWR-2 | no longer applies | fixed in 7ca39a09: `el-power-design.md:96–105` continuous current from the Amass datasheet for the wire gauge, short-term ≤ 1-minute figure, heat table | Amass XT30/XT60/XT90 datasheets (already cited) |
| PWR-3 | fixed | `el-power-design.md:110` gauge line is **continuous** current; peak checked by ≤ 1 % drop; 14 AWG on 5" reconciled (0.2 m loop, 100 A → 0.17 V) | copper resistance per AWG already in the module (ρ = 1.724·10⁻⁸ Ω·m); 1 % is the module's existing course criterion |
| BAT-3 | no longer applies | fixed in 7f293211: `el-battery-packs.md:29` thresholds from the `f-power` table | — |
| WIR-1 | fixed | `el-wiring.md:50` pass/fail criterion (≤ 1 % at peak; continuous ≤ gauge rule), worked example scored; `assets/widgets/wire-drop.js:42` tag thresholds 1 % / 5 % (was 2.5 % / 5 %) and hint text, catalogs in `i18n/*/ui.json` re-keyed | same as PWR-3 |
| WIR-2 | no longer applies | fixed in 7ca39a09: `el-wiring.md:55` Amass datasheet values, rule in `el-power-design` | — |
| EMI-1 | fixed | selection was added to `el-power-design.md:77` («LC-фильтр для видео»: f₀, Q vs ESR, I_sat ≥ 1.5 × peak) in 1161e41e; this pass added the pointer and the oscilloscope check in `el-emi.md:61` | `el-power-design` calculation and lab; `el-measure` for the measurement |
| VTX-1 | fixed | `link-vtx.md:58` which mode and why (UNTIL_FIRST_ARM default on the field, ON in a group, OFF only with manual pit mode), check; `:112` note on the CLI example | Betaflight 2025.12.5 `io/vtx.c:131–135` (`!ARMED && !failsafeIsActive()`, `WAS_EVER_ARMED`) |
| ETX-1 | fixed | `link-edgetx.md:195` table split into «recommended» and «firmware hard limit» columns; the 400k row no longer contradicts the text | ExpressLRS 4.1.0 `src/lib/Handset/CRSFHandset.cpp:413–425` (115k → 250 Hz, 200 Hz half-duplex; 400k → 500 Hz). The ELRS «Radio Preparation» page could not be fetched in this pass; the «recommended» column keeps the attribution the module already had |
| GNS-1 | fixed | `est-gnss.md:67` receiver choice without RTK (M10 default; 4 constellations on M10: 4 Hz by default, 10 Hz only in high-performance mode; M9N when 4 constellations at 10 Hz are wanted without that mode — «и выше» removed, EKF needs ≤ 10 Hz; M8N only if fitted; F9P only for RTK / dual antenna — unsourced «UM982» removed here; FC-sel I6), check | u-blox MAX-M10S, NEO-M9N, NEO-M8, ZED-F9P documents already cited in the module |
| BFS-2 | fixed | `bf-failsafe.md:34` rule: Stage 1 = fall at minimum throttle (h = ½gt²), trade-off vs false Stage 2, values by procedure and packet rate, check from LQ telemetry | Betaflight 2025.12.5 `rx/rx.c:131, 158–161, 625–636` (300 ms hold, `RX_FAILSAFE_MODE_AUTO` → `rx_min_usec` for throttle), `flight/failsafe.c:75`, `cli/settings.c:988`; values labelled «оценка курса» |
| FIL-1 | fixed | `bf-filters.md:59` class paragraph (harmonics by class; 7" given as 110–200 Hz so both cited sources agree — FC-sel I5; `rpm_filter_min_hz` first, `dyn_notch_min_hz` range); `:137` «ниже 100 Гц» limited to 5" | Betaflight 2025.12.5 `cli/settings.c:805` (`dyn_notch_min_hz` 20–250), `pg/dyn_notch.c:33`; class values from `bf-rpm-filter` and `f-frame-mech` |
| RAT-1 | fixed | `bf-rates-rc.md:92` new subsection: M ≤ α × 0.25–0.5 s, worked for 5" (one α: 75 rad/s² conservative, 125 as the upper end; «в 10–20 раз» — FC-sel I2) and X8, Actual settings for a heavy aircraft, saturation check by log | α from `f-mechanics` and `f-physics`; Actual formula (`fc/rc.c`) already in the module; 0.25–0.5 s labelled «оценка курса» |

**Fact-check (FC-sel, `/tmp/claude-0/work/s6/FC-sel.md`), all items applied:**
- E1 → PHY-1.
- I1 → PHY-2.
- I2 → RAT-1.
- I3 → MEC-1.
- I4 → WHP-3 / RPM-1.
- I5 → FIL-1.
- I6 → GNS-1.
- I7 → FCS-1.
- I8: the old wrong facts are also fixed in the `cs` and `ru-odessa` copies, in the lines that exist there. `ru-odessa` received the Russian source sentences. The files touched:
  - f-motors-esc: T/W, DShot, demag
  - f-fc-sensors: BMI270
  - f-components-choice: band and video, frame, Li-Ion C
  - f-frame-mech: hard mount, f₀
  - f-esc-firmware; `cs` stops here
  - ru-odessa only: f-power, f-mechanics diagnostics, diag-troubleshooting, ops-case-studies, bf-filters, bf-rpm-filter

  Their new standalone paragraphs exist only in the Russian source, as for the other languages.
- I9 → POW-1.

Nits fixed:
- f₀ range in `f-frame-mech`;
- the tilt-comp start value;
- the DYN_IDLE units;
- `tw-calc.js` header comment (hover throttle from the 0.65 curve, not 1/(T/W));
- the unsourced «UM982» in the GNSS choice;
- the Holybro capacitor note;
- the `f-aero-props` lab wording;
- «больше пропвоша» added to the props-in cons.

Accepted as is, per FC-sel: wire-drop rates only the percentage drop (the hint says to check the continuous current separately); «DShot600 — до 8 кГц» is the practical number (the code limit is 16 kHz).

Checks after this pass: `validate_content.py` OK, `check_i18n.py` 0 errors, `check_diagrams.py` 0 errors, `check_js.py` 0 errors.

---

## 1. Foundation

### f-physics.md (L1)

- **PHY-1** · `f-physics.md:56` · «"props in"/"props out" меняет знаки yaw». Same in `diag-troubleshooting.md:55` («Направление "props in/out" — согласованно во всех четырёх») and `bf-setup-scratch.md:83` (`yaw_motors_reversed`).
  - *Decision:* which rotation scheme to set up a quad with.
  - *Missing:* R+W. No rule and no reason for preferring either scheme. The factors usually cited — debris, yaw behaviour, firmware default — are listed for the author to verify, not as facts.
  - *Severity:* medium.
  - *Elsewhere:* none — every module only defines the two schemes.
  - *Settle with:* the Betaflight docs (default and the reason for the option) plus a manufacturer or community guide for the trade-off.
- **PHY-2** · `f-physics.md:28–30` · «6:1 и выше — фристайл и гонки».
  - *Decision:* target T/W for the build.
  - *Missing:* X+C.
    - Conflicts with `f-motors-esc.md:70` («5" фристайл … нужен T/W ≥ 5»).
    - `f-aero-props.md:75` repeats 6+.
    - The classes the course recommends as first aircraft (whoop, 3.5", cinewhoop) have no T/W row, and neither does a wing.
    - No source on any band.
  - *Severity:* medium.
  - *Elsewhere:* partial — the same bands are in `f-aero-props:75` and `f-components-choice:62` (T/W < 2 → rework).
- **PHY-3** · `f-physics.md:100` · «газ висения выше 60 % … запаса … почти нет; ниже 20 % — аппарат очень резкий».
  - *Decision:* whether hover throttle is acceptable.
  - *Missing:* X — the threshold differs between modules:
    - `f-mechanics:62` «выше ~70 %»;
    - `f-physics:113` «60–70 %»;
    - `ops-weather:33` «~70 %»;
    - `f-components-choice:48` «висение на 30–45 % газа»;
    - `eng-method-101:35` «газ висения ≤ 40 %» at T/W 2.5.
  - The last value cannot be reached under the course's own estimate: at T/W 2.5 hover lies between 1/(T/W) = 40 % and √(1/(T/W)) = 63 % (`f-physics:95`).
  - *Severity:* medium.
  - *Elsewhere:* none consistent; one canonical statement is needed, with class dependence (freestyle 5" hovers lower than a cargo X8).

### f-mechanics.md (L1)

- **MEC-1** · `f-mechanics.md:37`, `:85` · «`thr_corr_value` (Betaflight), `throttle_tilt_comp_str` (INAV), `ATC_ANGLE_BOOST`»; diagnostics: «включить компенсацию газа по наклону».
  - *Decision:* whether to enable tilt compensation, and to what value.
  - *Missing:* R+S+V. No value, no starting point, no way to check it; Betaflight `thr_corr_value` / `thr_corr_angle` appear nowhere else in the course.
  - *Severity:* medium.
  - *Elsewhere:* none.
  - *Settle with:* Betaflight `cli/settings.c` (defaults and ranges) and the INAV / ArduPilot parameter docs.
- **MEC-2** · `f-mechanics.md:52`, `:62`, `:80` · «Запас в самом тяжёлом режиме < 20 %».
  - *Decision:* thrust margin for the heaviest mode.
  - *Missing:* W — no source and no reason for 20 %, and it is not labelled «оценка». `f-components-choice:67` says «Запас: 20 %», and `:62` says T/W ≥ 2, which is a different measure.
  - *Severity:* low.
  - *Elsewhere:* none.

### f-aero-props.md (L2)

- **AER-1** · `f-aero-props.md:54` · «большой проп — низкий KV (10": 600–900 KV на 6S), маленький — высокий (5": 1700–2300 KV на 6S)».
  - *Decision:* KV for the build.
  - *Missing:* C+S+R.
    - Only two classes, and both on 6S.
    - No rule for another cell count: the same prop on 4S needs a different KV, because rpm ≈ KV·U.
    - No where-to-start within the range, and no check after.
  - Other modules add classes but not the rule:
    - `f-components-choice:48` gives 7" 1300–1700, 10" and 15";
    - `f-micro-whoop:41–45` gives micro classes «оценка»;
    - `f-motors-esc:29` gives only a qualitative rule.
  - A reader building a 4S 5" or a 3" has nothing to apply.
  - *Severity:* **high** — choosing KV for the wrong cell count is the classic overcurrent or underpower mistake.
  - *Elsewhere:* partial. `des-sizing.md:68–72` (L3, much later in the path) gives the mechanism («обороты под нагрузкой ≈ 0.75–0.85 × KV × U») and the hover-current check, but only for 15–17" heavy lift.
  - *Fix pattern:* pull that mechanism forward into `f-aero-props` (target rpm or tip speed for the prop → KV = rpm / U_load), then a class × S table with a source per row, then a check («ток висения ≤ … по таблице», motor temperature).
  - *Settle with:* manufacturer thrust tables for several classes and cell counts.
- **AER-2** · `f-aero-props.md:39` · «Больше шаг — больше скорость потока и тяга на оборот, но больше момент и ток. Больше лопастей — больше тяги … ценой КПД».
  - *Decision:* pitch and blade count.
  - *Missing:* S+C — the trade-off is given but nothing to start from per class (freestyle 5" vs LR 7" vs cinewhoop vs X8).
  - *Severity:* medium.
  - *Elsewhere:* partial — the procedure exists in this module's lab (`:97`, `:99`: compare two props by g/W at hover thrust). A one-line pointer to that rule in the theory, plus class starting points, closes it.
- **AER-3** · `f-aero-props.md:94` · «Длительный ток мотора на висении … ориентир ≤ 40 %» of the table **maximum**.
  - *Missing:* X+W. `f-components-choice:48` says «при токе не выше 40 % **длительного**» — maximum and continuous are different references. No reason is given for 40 %.
  - *Severity:* medium.
  - *Elsewhere:* `des-sizing.md:71` agrees with `f-components-choice` («~40 % длительного тока мотора»), so `f-aero-props` is the outlier.
- **AER-4** · `f-aero-props.md:60` · «У крыла проп … нужно подбирать на крейсерскую скорость».
  - *Decision:* prop for a wing.
  - *Missing:* R+V — no procedure (pitch speed vs cruise, J at cruise).
  - *Severity:* low here; the course is multirotor-first.
  - *Elsewhere:* not in scope modules — check `des-sizing` (DS-findings below).
- **AER-5** · `f-aero-props.md:57` · g/W by class «5" ~4–6 … 10–15" ~10–14».
  - *Missing:* the numbers have no source or «оценка» label. Low.
  - *Elsewhere:* `f-components-choice:43` gives a different 10" figure (12–15) and explains why.

### f-electricity-101.md (L1)

- **ELE-1** · `f-electricity-101.md:48` · «C-рейтинг — максимальный ток в долях ёмкости … Реальные значения часто ниже маркировки».
  - *Decision:* which C rating and capacity to buy.
  - *Missing:* R. No sizing rule from peak current, and no margin.
  - *Severity:* medium.
  - *Elsewhere:* partial — `f-components-choice:56` sizes capacity from current, and `f-power:27` says to judge by IR. Neither gives «C required = I_peak / Q with margin», and `el-battery-packs` has it only for Li-Ion (BAT-1).
- **ELE-2** · `f-electricity-101.md:58` · «минимум под нагрузкой ~3.3–3.5».
  - *Decision:* landing voltage.
  - *Missing:* S. Nothing says where in the range to land or why; it depends on chemistry, load and class.
  - *Severity:* low here (warning thresholds are set elsewhere).
  - *Elsewhere:* `bf-modes-osd:104` (3.5 V LiPo 5", 3.3 V Li-Ion) — pointer.
- **ELE-3** · `f-electricity-101.md:51`, `:89`, `:106` · cell imbalance «> 0.05 В — разбаланс» and symptom «на 0.1 В и больше».
  - *Missing:* X — `f-power:55` says ≤ 0.02 V after charge and ≤ 0.05 V after flight; `ops-maintenance:34` says 0.03–0.05 V after charge and rest.
  - *Severity:* low.
  - *Elsewhere:* the fix is one canonical line («после заряда и отдыха …, после полёта …»), referenced from all three.

### f-power.md (L1)

- **POW-1** · `f-power.md:34` · «если средний ток на банку небольшой … Li-Ion даёт больше минут. Если нужны пики в десятки ампер — LiPo».
  - *Decision:* battery chemistry.
  - *Missing:* R — «небольшой» has no number (A per cell or C) and no check.
  - *Severity:* medium.
  - *Elsewhere:* `f-components-choice:56` («типично 2–3C для 21700 с высокой ёмкостью»), `:76`. A pointer and the number close it; cell datasheets (continuous rating) settle it.
- **POW-2** · `f-power.md:52`, `:114` · «пороги предупреждения ставят по напряжению под нагрузкой или по mAh»; «настрой предупреждения в OSD так, чтобы садиться с запасом».
  - *Decision:* warning and critical voltage per cell.
  - *Missing:* R+C+V. No number, no class or chemistry split, no pointer.
  - *Severity:* **high** — the reader is told to set a threshold and given nothing. `ops-case-studies:76` shows how wrong thresholds cause crashes.
  - *Elsewhere:*
    - `bf-modes-osd:104` (warning 3.5 V LiPo 5", 3.3 V Li-Ion);
    - `f-micro-whoop:146–147`, `:155` (whoop 1S values, «оценка»);
    - `ops-case-studies:76` («по измеренной кривой разряда»), which has no procedure.
  - *Fix:* pointer, a one-line rule by chemistry and class, and «проверка: напряжение покоя после посадки».
- **POW-3** · `f-power.md:43`, `:85` · BEC «впритык при нагреве; отдельный BEC 3 А спокойнее».
  - *Decision:* BEC current rating.
  - *Missing:* W — no margin rule (what fraction of the rating is safe and why, i.e. thermal derating).
  - *Severity:* low.
  - *Elsewhere:* `el-power-design.md:42`, `:79` («номинал ≥ 1.5 × сумма») — pointer. Note the inconsistency in PWR-4.
- **POW-4** · `f-power.md:55` · «Баланс-заряд 1C (LiPo) / 0.5–1C (Li-Ion), до 4.2 В/эл. (4.1 — дольше ресурс)».
  - *Missing:* S — no recommendation on when 4.1 V is worth it, or where to start in 0.5–1C.
  - *Severity:* low.
- **POW-5** · `f-power.md:55` vs `ops-weather.md:49` · warm-up temperature «20–30 °C» vs «20–25 °C».
  - *Missing:* X. Low.
- **POW-6** · `f-power.md:113–114` · «проверь масштаб датчика напряжения и тока … по мультиметру».
  - *Missing:* V+R — no procedure here.
  - *Severity:* low.
  - *Elsewhere:* `bf-setup-scratch` (the `ibata_scale` chart) and `f-power:49` (±10 % mAh check) — pointer.

### f-motors-esc.md (L1)

- **MOT-1** · `f-motors-esc.md:87` · «Для Betaflight на типовом 4k–8k цикле — DShot300 или DShot600»; same at `f-esc-firmware.md:138` («DSHOT600 (или 300)»).
  - *Decision:* DShot speed.
  - *Missing:* R+W. No rule linking DShot speed to PID loop rate, bidir and MCU.
  - The pointer «см. модуль про RPM-фильтр» is wrong: `bf-rpm-filter` holds no DShot-speed rule (RPM-3).
  - `bf-filters.md:110` and `f-micro-whoop:129` hold a hard rule that belongs here: with `dshot_bidir = ON`, F405/F411/G47x (and APM32F405/F407) are rewritten to DSHOT300 with PID ≤ 4 kHz, except F405 at `cpu_overclock` ≥ 216 MHz.
  - *Severity:* medium.
  - *Elsewhere:* `bf-filters:110`, `f-micro-whoop:88–92` — fix the pointer and add the one-line summary.
- **MOT-2** · `f-motors-esc.md:61` · «Demag compensation … "High" для тяжёлых пропов»; `f-esc-firmware.md:44` «первым делом лечатся повышением компенсации».
  - *Decision:* demag level.
  - *Missing:* C+S — «тяжёлые» is undefined, no starting value per class, no check (eRPM dips in Blackbox).
  - *Severity:* medium.
  - *Elsewhere:* none.
  - *Settle with:* the Bluejay wiki and AM32 / BLHeli_32 manuals.
- **MOT-3** · `f-motors-esc.md:60` · «Timing (motor timing, 16–24°)».
  - *Missing:* S — no starting point here.
  - *Severity:* low.
  - *Elsewhere:* `f-esc-firmware:43` («Автоматический/средний — разумный старт») — pointer.
- **MOT-4** · `f-motors-esc.md:67`, `:97`, `:100`; `f-esc-firmware.md:110`, `:138` · DShot error threshold: «норма 0, при > 1–2 %» vs «не выше 1 %» vs «≈ 0 %».
  - *Missing:* X. Low-medium; one canonical number with its source is needed.
- **MOT-5** · `f-motors-esc.md:70` · T/W ≥ 5 for freestyle.
  - *Missing:* X with `f-physics` (see PHY-2). Also «7" … ESC 35–45 А» at a 22 A peak is a 1.6–2× margin, unexplained against the 1.3× rule. Low.
- **MOT-6** · `f-motors-esc.md:50` · «ESC выбирают по длительному току с запасом относительно реального пикового тока из лога».
  - *Missing:* R for the first build, which has no log yet. «Из таблицы мотора» is said only in `f-components-choice:53`. Low — pointer.

### f-esc-firmware.md (L2) — reference module

- **ESC-1** · `:44`, `:45` · demag compensation and startup power: no starting value per class (see MOT-2). The PWM subsection gives a procedure for startup power (`:106`), and it is good.
  - *Severity:* medium, merged with MOT-2.
- **ESC-2** · `:138` · «`set motor_pwm_protocol = DSHOT600` (или 300)» — see MOT-1.

### f-fc-sensors.md (L1)

- **FCS-1** · `f-fc-sensors.md:54` · «делитель цикла PID — `pid_process_denom`»; and the gyro chip list (MPU6000 / ICM20602 / ICM42688-P / BMI270).
  - *Decision:* PID loop rate. For a buyer, also which gyro and MCU to accept.
  - *Missing:* R+W.
    - Nothing says which loop rate to run on which MCU / gyro / DShot / RPM-filter combination.
    - The chip list has no consequence for the buyer: BMI270 caps PID at 3.2 kHz, as stated only in `f-micro-whoop:100`, `:152`.
  - *Severity:* medium.
  - *Elsewhere:* `bf-filters.md:110` (F4 / G4 with bidir: PID ≤ 4 kHz; `LOAD` flag criterion) and `f-micro-whoop:88–92`, `:131`, `:152`. Nothing covers F7 / H7 — a pointer plus a one-line rule covers the common case.
- **FCS-2** · `f-fc-sensors.md:51` · «Стандарты крепления — 30.5×30.5 и 20×20 мм»; `f-components-choice:45`.
  - *Decision:* stack size.
  - *Missing:* R — no rule by class and current (the usual split is by ESC current and frame size).
  - *Severity:* low.
  - *Elsewhere:* `f-micro-whoop:86` (AIO up to 3", stack from 5"), only for micro.
- **FCS-3** · `f-fc-sensors.md:60` · «16–32 МБ flash хватает на минуты на 2 кГц; SD — часы».
  - *Decision:* Blackbox rate and flash vs SD.
  - *Missing:* S — no rate recommendation.
  - *Severity:* low.
  - *Elsewhere:* `bf-blackbox` (outside scope) — pointer.

### f-frame-mech.md (L2)

- **FRM-1** · `f-frame-mech.md:40` vs `:49` · «для гоночных 5" часто жёсткое крепление и чистый тюн фильтров» vs «для 5" (моторы 250+ Гц) — f₀ ≈ 60–80 Гц» (soft mount).
  - *Decision:* soft or hard FC mount on a 5".
  - *Missing:* X inside the module, and R: f₀ needs k, which the reader does not know (grommet hardness or Shore value, part spec).
  - The «признак слишком мягкого» check is good.
  - *Severity:* medium.
  - *Elsewhere:* none.
  - *Settle with:* damper manufacturer specs, or measure by tap test (the procedure exists at `:46` for arms).
- **FRM-2** · `f-frame-mech.md:46`; `f-components-choice.md:45` · arm thickness «карбон 3–5 мм на лучах для 5–7"» and «7" 5 мм — 150–250 Гц (… опасная зона)».
  - *Decision:* frame / arm choice for 7".
  - *Missing:* R+X. `f-components-choice` recommends a thickness that `f-frame-mech` calls a danger zone for 7", with no rule for which to pick and no frame geometry (X / stretched X / H / deadcat).
  - *Severity:* medium.
  - *Elsewhere:* none.
- **FRM-3** · `f-frame-mech.md:52` · «статический notch `gyro_notch1_hz = 180`, `cutoff = 150`».
  - *Decision:* notch width.
  - *Missing:* W+X — no rule for picking the cutoff here. `bf-filters.md:131` gives «`cutoff` = частота × 0.7», while this example uses 150 / 180 = 0.83 without saying why.
  - *Severity:* low.
  - *Elsewhere:* `bf-filters:131` — pointer; align the example or explain the difference.
- **FRM-4** · `f-frame-mech.md:43` vs `f-esc-firmware.md:88` · 7" hover first harmonic «~120–200» vs «110–130 Гц (`bf-rpm-filter`)».
  - *Missing:* X. Low.

### f-components-choice.md (L1)

- **CMP-1** · `f-components-choice.md:48` · «тяга на висении должна приходиться на 30–45 % газа … Размер мотора и KV: 7" … 10" … 15"».
  - *Missing:* C+X.
    - One hover-throttle band is used for every class (see PHY-3).
    - The KV ranges have no starting point and no voltage rule (see AER-1).
    - 5" is missing, although `f-aero-props:54` has it.
  - *Severity:* medium for the hover band. The KV part is the same defect as AER-1 and is counted there (high); fix both together.
- **CMP-2** · `f-components-choice.md:53` · «Длительный ток ESC ≥ 1.3 × максимальный ток мотора из таблицы».
  - *Missing:* W — no reason or source for 1.3. Low.
- **CMP-3** · `f-components-choice.md:53` · «4-в-1 — компактно … отдельные ESC — ремонтопригодно».
  - *Decision:* 4-in-1 or individual ESCs.
  - *Missing:* S — no recommendation by class.
  - *Severity:* low.
  - *Elsewhere:* `f-micro-whoop:86` for micro only.
- **CMP-4** · `f-components-choice.md:56` · battery from current.
  - The capacity rule is present; the C rating for LiPo is absent.
  - Same defect as ELE-1 / BAT-1 — counted under BAT-1, fixed together.
- **CMP-5** · `f-components-choice.md:59` · «Приёмник: диапазон под дальность (900 МГц для 5+ км). Видео: аналог дёшев и живуч, цифра — качество и бюджет».
  - *Decision:* RC band; video system.
  - *Missing:* R+W.
    - One threshold with no reason: antenna size, regulation, noise floor.
    - Video has no decision rule and no pointer.
  - *Severity:* medium; low once the pointers are in.
  - *Elsewhere:* `link-digital-video.md:52–56` («Как выбирать») for video, `link-elrs.md:239–242` for the band — both hold the rule. Pointers plus one-line summaries close it.
- **CMP-6** · `f-components-choice.md:59` · «FC: F4 хватает для Betaflight без лишнего, F7/H7 для INAV/ArduPilot».
  - *Missing:* W — the reason (UART count, flash size, loop rate with bidir) is not linked; `f-micro-whoop:88–92` holds it for micro. Low.

### f-safety.md (L1)

- **SAF-1** · `f-safety.md:75` · «Радиус безопасной зоны … не меньше 10–15 м для 5", 30 м для тяжёлых».
  - *Missing:* C+W — «тяжёлых» is undefined, there is no source, and it is not labelled «оценка». Low.
- **SAF-2** · `f-safety.md:68` · «PREARM … обязателен на аппаратах с пропами 7"+».
  - *Missing:* W — the reason (prop energy, `:28`) is not linked. Low.

### f-regulations.md (L1)

No selection findings: the module points to the regulator for every value, which is correct for law. Terms are covered in section T.

### f-starter-kit.md (L1)

Mostly at target quality: purchase order with reason, compatibility tables, worked budget.

- **KIT-1** · `f-starter-kit.md:105` · «Cinewhoop 2.5–3.5" … 4S–6S».
  - *Missing:* S — no rule for 4S vs 6S. Low.
- **KIT-2** · `f-starter-kit.md:63` · «Отсек внешнего модуля (JR — большой, nano/Lite — малый …)».
  - *Missing:* S — no recommendation for which bay to prefer when buying. Low.
- **KIT-3** · `f-starter-kit.md:70` · the video-system choice is deferred to `link-digital-video` «Как выбирать».
  - Verified: `link-digital-video:52–56` holds the rule. No finding.

### f-micro-whoop.md (L2)

- **WHP-1** · `f-micro-whoop.md:134` · «`dyn_idle_min_rpm` … подбирается, у вупов выше, чем у 5" (оценка)».
  - *Decision:* dynamic idle rpm.
  - *Missing:* R+S+V — no starting value, no procedure, no check.
  - *Severity:* medium.
  - *Elsewhere:* none in the audited modules. `bf-rpm-filter:77` only points to `bf-features-tour` (outside scope) — check there first. `f-esc-firmware:107` covers static `motor_idle` only.
- **WHP-2** · `f-micro-whoop.md:133`, `:151`, `:270` · «`motor_idle` 600–1000 (оценка)»; «поднять шагами по 50–100».
  - *Missing:* S — no starting point in a wide range, though the step procedure exists. Low-medium.
  - *Elsewhere:* `f-esc-firmware:107` gives the procedure (find the minimum stable idle in Motors, set slightly above it). Pointer.
- **WHP-3** · `f-micro-whoop.md:136` · «`rpm_filter_harmonics` … 1–3».
  - *Missing:* S — no rule (two-blade vs three-blade, noise in log). Medium.
  - *Elsewhere:* none — `bf-rpm-filter` keeps the default 3 without a rule (RPM-1).
- **WHP-4** · `f-micro-whoop.md:146–147` vs `:155` vs `:210` · thresholds:
  - warning 330–340 and critical 310–320 «оценка»;
  - «садиться … до 3.3 В, и не доводить … ниже 3.1–3.2 В»;
  - Betaflight defaults 3.5 / 3.3.
  - *Missing:* W+V — no reason for lowering thresholds on 1S (sag share per `:56`); no check (rest voltage after landing).
  - `:264` says «Пороги опускать в последнюю очередь», which reads against the table recommending lower values.
  - *Severity:* medium.
- **WHP-5** · `f-micro-whoop.md:41–45` · KV ranges per micro class «оценка».
  - *Missing:* S — no where-to-start. With AER-1, medium.
- **WHP-6** · `f-micro-whoop.md:44–45` · toothpick «1S–3S», 3.5" «3S–4S».
  - *Missing:* S — no rule for cell count. Low.
- **WHP-7** · `f-micro-whoop.md:138` · «`vbat_sag_compensation` … 100 (оценка)».
  - *Missing:* W+V. Low.

### eng-method-101.md (L1)

- **ENG-1** · `eng-method-101.md:35` · «T/W при взлётной массе ≥ 2.5 | расчёт и газ висения ≤ 40 %».
  - *Missing:* X — the two criteria in one row are not compatible under `f-physics:95`; a reader copying this requirement fails it by construction.
  - *Severity:* medium, because this table is the model requirements table.
- **ENG-2** · `eng-method-101.md:36` · «DROP через 1.5 с».
  - *Missing:* W — no reason for choosing DROP. Low.
  - *Elsewhere:* `bf-failsafe` — pointer.

### ops-pilot-training.md (L1)

At target quality: source table, labelled course guidelines, rule plus check.

- **PLT-1** · `ops-pilot-training.md:102` · «`acro_trainer_angle_limit` … 20–45».
  - *Missing:* S — no starting point (the default 20 is implied). Low.

### ops-field.md (L2)

- **FLD-1** · `ops-field.md:39` · «разнос с соседями (ориентир ≥ ~37 МГц для аналога)».
  - *Decision:* VTX channel spacing.
  - *Missing:* W — no source or reason (filter bandwidth, IMD).
  - *Severity:* low after the pointer.
  - *Elsewhere:* `link-vtx.md:49` (bandwidth 20–27 MHz, Raceband 37 MHz, IMD) — pointer and one-line reason.
- **FLD-2** · `ops-field.md:40` · «packet rate под задачу».
  - *Missing:* R. Low after the pointer.
  - *Elsewhere:* `link-elrs.md:239–242` («Выбор режима под задачу») — pointer.

### ops-weather.md (L2)

- **WTH-1** · `ops-weather.md:33` · «порывы не больше ~50–60 % максимальной горизонтальной скорости».
  - *Missing:* W — no source and not labelled «оценка». Low-medium.
- **WTH-2** · `ops-weather.md:71` · go / no-go «минимальный запас по разнице температуры и точки росы».
  - *Missing:* S — the reader must fill a number, and the module gives only «0–2 °C … вероятны» (`:56`) and «3 °C — влажно» (`:65`). No recommended threshold. Low.

### ops-maintenance.md, ops-case-studies.md, diag-troubleshooting.md, f-remote-id-security.md

- **MNT-1** · `ops-maintenance.md:34` · «IR … в 1.5–2 раза», «0.03–0.05 В».
  - The script picks 1.5 and 0.04. Fine; only the cross-module imbalance numbers conflict (ELE-3). Low.
- **CAS-1** · `ops-case-studies.md:76`, `:136` · «Пороги … для своих АКБ — по измеренной кривой разряда».
  - *Missing:* R — no procedure for deriving a threshold from a discharge curve, anywhere in the course.
  - *Severity:* medium. Merge into the POW-2 fix.
- **DIA-1** · `diag-troubleshooting.md:55` · props in/out (see PHY-1).
- **RID-1** · `f-remote-id-security.md` · «модуль по MAVLink/DroneCAN» vs «отдельный маячок».
  - *Missing:* S — no recommendation. Low (L3; the country rule is given).

---

## 2. Electronics

### el-power-design.md (L2)

- **PWR-1** · `el-power-design.md:55` · «470–1000 мкФ на 35 В для 4S, 1000 мкФ на 50 В для 6S (запас ≥ 30 % по напряжению)».
  - *Decision:* bulk capacitor value and type.
  - *Missing:* C+R.
    - Only 4S and 6S, with one value range for every class (whoop AIO vs 10" with 100+ A peaks).
    - No rule for capacitance or ripple-current rating vs ESC current.
    - No rule for when to add a second capacitor.
  - The check after is good (`:82`: gyro noise above 300 Hz must drop).
  - *Severity:* medium.
  - *Elsewhere:* none.
  - *Settle with:* capacitor datasheets (ripple current, ESR) and ESC manufacturer recommendations.
- **PWR-2** · `el-power-design.md:61` · «XT30 до ~15–30 А длительно, XT60 ~30 А длительно (кратковременно до ~60 А), XT90 ~45 А длительно».
  - *Decision:* battery connector.
  - *Missing:* R+X.
    - Nothing says which current to compare the rating with (average flight current, p95, peak).
    - `el-wiring.md:55` says «для 40–60 А длительно — XT90 или AS150».
    - `f-power.md:49` gives 5" freestyle an average of 25–40 A with 60–100 A peaks.
    - Taken literally, a 5" on XT60 is at the limit or over it, yet the whole course (`f-starter-kit:125`, `f-micro-whoop`) uses XT60/XT30 as standard.
    - The «XT90 ~45 А» continuous figure looks low next to «XT60 ~30 А» and is unsourced.
  - *Severity:* medium.
  - *Elsewhere:* `f-micro-whoop:64–71` does it correctly for micro connectors (datasheet current and contact resistance) — the pattern to copy. Settle with Amass datasheets.
- **PWR-3** · `el-power-design.md:66` · «12 AWG до ~60–80 А, 14 AWG до ~40–50 А, 16 AWG до ~25 А …».
  - *Missing:* X+W.
    - Peak or continuous is not said.
    - `el-wiring.md:45` puts 14 AWG on «АКБ 5"» (60–100 A peaks per `f-power:49`).
    - `el-wiring.md:50` says to choose by peak current with a drop and heat calculation, but no acceptable drop or heat target is given in either module.
  - *Severity:* medium.
  - *Elsewhere:* `el-wiring:50` (method). Missing in both: the pass/fail criterion.
- **PWR-4** · `el-power-design.md:42`, `:79` · «Сложи с запасом 50 %», «номинал ≥ 1.5 × сумма».
  - *Missing:* W+X.
    - No reason given (thermal derating, startup surge).
    - `f-power:85` calls a 9 V 2 A BEC for a 0.8–1.2 A air unit «впритык при нагреве». That is a 1.7–2.5× margin, i.e. more than the 1.5× rule here.
  - *Severity:* low-medium.
- **PWR-5** · `el-power-design.md:59` · «Предохранитель — на больших аппаратах на силовой шине».
  - *Decision:* fuse rating.
  - *Missing:* R here.
  - *Severity:* low.
  - *Elsewhere:* `el-redundancy.md:41` («ANL/MIDI на 1.3 × максимальный ток ветки») — pointer. The 1.3 has no reason there either.

### el-battery-packs.md (L2)

- **BAT-1** · `el-battery-packs.md:31`, `:35` · LiPo «20–100C».
  - *Decision:* LiPo C rating and capacity for a given peak current.
  - *Missing:* R+V.
    - The S/P rule with a 0.6 derating exists for Li-Ion (`:79`), but there is no analogue for LiPo: C rating from peak current, with a label-vs-real margin.
    - With ELE-1 and CMP-4, no module tells a 5" builder how to pick capacity × C.
  - *Severity:* **high** — the first LiPo purchase is made on the label C, which `f-power:27` itself calls unreliable.
  - *Elsewhere:* none.
  - *Fix pattern:* reuse the Li-Ion procedure (`:79`) with IR (`f-power:52`) as the honest measure, plus «проверка: просадка на панче по логу».
  - *Settle with:* manufacturer IR data or independent discharge tests.
- **BAT-2** · `el-battery-packs.md:37`, `:43`, `:76` · «Li-Ion выигрывает, когда средний ток пакета ≤ 1–2C … Если висение требует > 3C — LiPo»; «≤ 1.5C».
  - *Missing:* S — the 2–3C band is undefined.
  - Also X: `f-components-choice:56` says high-capacity 21700 deliver «типично 2–3C», while this table says «3–10C на элемент».
  - *Severity:* low-medium.
- **BAT-3** · `el-battery-packs.md:29` · landing voltage «3.3–3.5» LiPo, «2.5–3.0» Li-Ion, «2.5» LiFePO4.
  - *Missing:* S+X.
    - No where-in-range rule.
    - `f-power:49` uses 3.0 V for Li-Ion; `bf-modes-osd:104` uses a 3.3 V warning for Li-Ion.
  - Merge into the POW-2 fix. Medium.
- **BAT-4** · `el-battery-packs.md:64` vs `ops-maintenance.md:34` · end of life «рост до 50+ мОм» (absolute) and «LiPo 10+» vs «в 1.5–2 раза от нового» (ratio).
  - *Missing:* X — two criteria, and no statement of which one decides. Low.

### el-wiring.md (L1)

- **WIR-1** · `el-wiring.md:41–50`, `:101` · gauge table «где на борту» and «калибр силовых проводов обоснован расчётом падения и нагрева на пиковом токе».
  - *Decision:* wire gauge.
  - *Missing:* V — no acceptable drop or heat number, so «обоснован» cannot be checked. The worked example says 18 AWG is bad and 14 AWG fine, but not why the line falls between them.
  - Also X with `el-power-design:66` (see PWR-3).
  - *Severity:* medium.
- **WIR-2** · `el-wiring.md:55` · «XT60 рассчитан примерно на 30 А длительно … для 40–60 А длительно — XT90 или AS150». See PWR-2. Medium.
- **WIR-3** · `el-wiring.md:27` · iron temperature «330–370 °C» / «370–400 °C».
  - *Missing:* S — no starting point (by pad size). Low.

### el-measure.md (L2)

No selection findings. Instrument choice is given with reasons (2 channels and 50–100 MHz; analyzer ≥ 4–5 samples per bit, 12–24 MHz).

### el-emi.md (L2)

- **EMI-1** · `el-emi.md:59`; `el-power-design.md:98`; `diag-troubleshooting.md:77` · «LC-фильтр на питание VTX/камеры».
  - *Decision:* L and C values, and current rating, of the filter.
  - *Missing:* R+V — it is recommended in three modules, and no module says how to choose it (cutoff vs noise frequency, inductor saturation current vs VTX current) or how to check it (ripple before and after with the oscilloscope from `el-measure`).
  - *Severity:* medium.
  - *Elsewhere:* none.
- **EMI-2** · `el-emi.md:58` · «ферритовые кольца на кабелях USB/HDMI».
  - *Missing:* R — no rule for material or frequency range. Low.

### el-peripherals.md (L2)

- **PER-1** · `el-peripherals.md:30` vs `:74` · GPS baud «38400–115200» vs «57600/115200».
  - *Missing:* S — no rule; it depends on the fix rate and the messages.
  - *Severity:* low.
  - *Elsewhere:* check `est-gnss` (GNS-findings).

### el-redundancy.md, el-dronecan.md, el-kicad.md (L2–L3)

At target quality: shunt sizing in `el-kicad:46–48` goes requirement → calculation → margin; DroneCAN «когда» is stated.

- **RED-1** · `el-redundancy.md:41` · «ANL/MIDI на 1.3 × максимальный ток ветки».
  - *Missing:* W — no reason; no fast-blow vs slow-blow choice for the battery inrush. Low.

### rf-antennas.md (L2)

At target quality for most choices (RC linear and orthogonal; video circular and matched; directional only when someone aims it).

- **ANT-1** · `rf-antennas.md:55` vs `:91` · SWR «на потери дальности влияет меньше … пока он ≤ 2» vs lab norm «КСВ ≤ 1.5 на канале».
  - *Missing:* X/W — two thresholds; the reason for 1.5 (VTX heating vs range) is not stated. Low.
- **ANT-2** · VTX antenna type (stubby / pagoda / lollipop / patch on goggles) by use is not covered; only polarization matching is.
  - *Severity:* low.
  - *Elsewhere:* check `link-vtx`.

### rf-link-budget.md (L2)

- **LB-1** · `rf-link-budget.md:60`; `bf-modes-osd:104` · «LQ (<70 % на 250 Гц — повод тревожиться)».
  - *Decision:* LQ warning threshold.
  - *Missing:* C — given for 250 Hz only, though the module tabulates seven packet rates. Whether the threshold depends on rate is not said.
  - *Severity:* low, revised after reading link modules.
  - *Elsewhere:* `link-edgetx.md:151` gives «70–80, критично 50», labelled as community practice. ELRS documentation (`link-elrs:96`: «LQ падает с обрыва») makes RSSI the primary margin. A pointer and one sentence close it.
- **LB-2** · `rf-link-budget.md:50` vs `:79` · margin «10–15 дБ — минимум … 20 дБ — комфортно» vs working limit «запас = 12 дБ».
  - *Missing:* W — the choice of 12 is not explained (e.g. «середина минимального диапазона»). Low.

---

## 3. Link

### link-protocols.md (L1)

At target quality: «новые сборки — CRSF; SBUS — только для старого железа», with the reason (inversion on F4, CRC, duplex).

- **PRO-1** · `link-protocols.md:44`, `:58`; `bf-ports.md:105` · «может договариваться выше для меньшей задержки» and `crsf_use_negotiated_baud` (default OFF).
  - *Missing:* S — no recommendation on when to turn negotiation on. Low.

### link-vtx.md (L2)

Channel spacing has its mechanism (`:49`: bandwidth 20–27 MHz, IMD), so FLD-1 in `ops-field` is closed by a pointer here.

- **VTX-1** · `link-vtx.md:58`, `:96` · `vtx_low_power_disarm`: OFF / ON / UNTIL_FIRST_ARM; the CLI example sets ON.
  - *Decision:* which mode.
  - *Missing:* R+W — no recommendation and no trade-off:
    - ON lowers power after every disarm;
    - UNTIL_FIRST_ARM keeps flight power after a landing, which matters for finding a disarmed crash by video;
    - failsafe keeps power in either case.
  - *Severity:* medium.
  - *Elsewhere:* `ops-field:61` (search readiness) does not mention it.
- **VTX-2** · `link-vtx.md:52` · VTX power: «мощность минимально достаточная».
  - *Decision:* flight power level.
  - *Missing:* R+C — no procedure to find «minimally sufficient»: link budget → legal cap → field test. Indoor 25 mW is given only in `f-micro-whoop:173`.
  - *Severity:* low-medium.
  - *Elsewhere:* `rf-link-budget` (the method) and `f-regulations:100` (the cap) — pointers.
- **VTX-3** · `link-vtx.md:38–40` · FACTORY vs CUSTOM.
  - *Missing:* S — no recommendation beyond «Tramp/RTC6705 only CUSTOM». Low.
- **VTX-4** · VTX antenna type and mounting by use: not in this module (see ANT-2).
  - *Severity:* low.
  - *Elsewhere:* `rf-antennas:60` covers placement only.

### link-elrs.md (L2)

At target quality: the mode table has a «Когда» column, there is a «Выбор режима под задачу» list (`:239–242`), a telemetry-ratio rule (`:129`) and a worked 7" LR example (`:218`).

- **ELR-1** · `link-elrs.md:96` vs `rf-link-budget.md:60`, `:85`; `link-edgetx.md:151` · RSSI warning «на 5–10 дБ выше порога» vs «~8–10 дБ», «S + 10».
  - *Missing:* X — small, but the reader gets three numbers. Low.
- **ELR-2** · `link-elrs.md:101–105` · Switch mode Hybrid / Wide.
  - *Missing:* S — the only reason given for Wide is «показ мощности в OSD»; no default recommendation for a quad vs a wing. Low.
- **ELR-3** · `link-elrs.md:111–117` · `Arm using: CH5` vs `Switch`.
  - *Missing:* S — no recommendation (when Switch is worth it: freeing CH5, three-position arm switches). Low.
- **ELR-4** · `link-elrs.md:120`, `:245` · `Max Power`.
  - *Missing:* R — the ceiling is not tied to the legal cap and link budget explicitly; only «не ставить максимум» for close flying.
  - *Severity:* low.
  - *Elsewhere:* `f-regulations:100`, `rf-link-budget` — pointer.

### link-edgetx.md (L2)

- **ETX-1** · `link-edgetx.md:188–196` · CRSF baud table «400k | до 250 Гц» vs text «на 400k — до 500 Гц».
  - *Decision:* module baud for the chosen packet rate.
  - *Missing:* X inside the module — the table and the sentence below it disagree on the 400k limit.
  - *Severity:* medium (the reader picks the baud from this table).
  - *Settle with:* `CRSFHandset.cpp` 4.1.0, already cited.
- **ETX-2** · `link-edgetx.md:155` · `RxBt` alarm «3.5 В × число банок; критично 3.3 В × банки».
  - *Missing:* C — LiPo only; no Li-Ion or 1S figure. Same cluster as POW-2. Low here.
- **ETX-3** · `link-edgetx.md:151` · `RQly` «предупреждение 70–80, критично 50».
  - Labelled practice — good. The difference from `rf-link-budget:60` («<70 % на 250 Гц») is small; LB-1 downgraded to low.

### link-digital-video.md (L2)

At target quality: «Как выбирать» by task (`:52–56`), with the reason (latency vs picture vs openness). CMP-5 and KIT-3 are closed by a pointer here.

- **DIG-1** · `link-digital-video.md:77` · «какой запас по качеству линка нужен в полёте, чтобы не дойти до фриза».
  - The reader derives it by test — good. No starting threshold is given for the OSD warning (`:88`: «разворачиваться по порогу»). Low.

### link-telemetry-radios.md (L2)

At target quality: «Как выбрать» table (`:82–88`).

- **TEL-1** · `link-telemetry-radios.md` practice step 3 · «Оценить дальность с запасом 6–10 дБ» vs `rf-link-budget.md:50` «10–15 дБ — минимум».
  - *Missing:* X/W — different margins for two radio links, with no statement of why the telemetry link may run thinner (it is not the control link). Low-medium.
- **TEL-2** · `link-telemetry-radios.md:42`, `:44` · `NUM_CHANNELS`, `MAX_WINDOW`.
  - *Missing:* S — no starting values beyond the default. Low.

---

## 4. Estimation

### est-sensors.md (L2)

No selection findings. The calibration choices come with a rule and a check:
- 6-position calibration vs level only (`:43`: «для Acro это неважно»);
- temperature calibration when drift exceeds 0.2 °/s (`:72`).

- **SEN-1** · `est-sensors.md:33` · `BRD_HEAT_TARG` (IMU heater target).
  - *Missing:* R — no value or rule. Low (ArduPilot H7 / Cube only).

### est-gnss.md (L2)

- **GNS-1** · `est-gnss.md:25` (summary promises «как выбрать приёмник и антенну») vs `:47`.
  - *Decision:* which GNSS receiver to buy (M8 / M9 / M10 / F9P).
  - *Missing:* R — the theory lists capabilities (rates, constellations, RTK) but gives no decision rule for the non-RTK case. The antenna rule is present (`:50`).
  - *Severity:* medium, because the summary promises the rule.
- **GNS-2** · `est-gnss.md:53` · «Частота: 5–10 Гц для коптера … выше не нужно EKF».
  - Rule and reason given — good.
  - The UART baud a given rate needs is not stated, which leaves PER-1 open. Low.
- **GNS-3** · `est-gnss.md:55` · «GPS + Galileo + GLONASS или GPS + Galileo + BeiDou».
  - *Missing:* S — no rule for which pair (region, receiver generation). Low.

---

## 5. Design

All four modules are L2–L3 and mostly at target quality. Each choice is derived from a requirement, and examples carry sources: MN4014 tables, the P45B datasheet, Etkin, PX4 / ArduPilot source.

### des-sizing.md (L3)

- **SIZ-1** · `des-sizing.md:68–72` holds the KV mechanism that `f-aero-props` lacks: «обороты под нагрузкой ≈ 0.75–0.85 × KV × U», and «Ток висения — не выше ~40 % длительного тока мотора».
  - This is the pointer target for AER-1 and AER-3, because it agrees with `f-components-choice:48` («длительного»), not with `f-aero-props:94` («максимального»).
  - No finding against this module itself.
- **SIZ-2** · `des-sizing.md:74–76` · «Тяга в установившемся полёте … не больше 80 % максимума»; «1.5 × ветер».
  - *Missing:* W — no source or «оценка» label on 80 % and 1.5×.
  - Also X with `ops-weather:33` (gusts ≤ 50–60 % of maximum speed), which uses a different criterion for the same decision. Low-medium.
- **SIZ-3** · `des-sizing.md:42` · «f_frame … 15–20 %».
  - Labelled «ориентир», refined by weighing — fine.

### des-thrust-stand.md (L2)

- **STD-1** · `des-thrust-stand.md:402` · «балка 5 кг (запас 2.2× к 2228 г)».
  - *Decision:* load cell capacity.
  - *Missing:* R+W — no rule for picking capacity against resolution (HX711 full scale) and overload. Low.
- **STD-2** · `des-thrust-stand.md:36`, `:82` · HX711 10 vs 80 SPS; the script uses 10.
  - *Missing:* W — the reason (noise vs settling at a 10 s step) is not stated near the choice. Low.

### aero-stability.md (L3)

- **AST-1** · `aero-stability.md:47` · «V_h … 0.4–0.7».
  - *Missing:* S — no where-to-start for a FPV plane.
  - The static-margin choice is well reasoned (`:39`, `:49`: aim 5–10 %, not the 5 % edge). Low.

### ctl-allocation.md (L3)

- **ALC-1** · `ctl-allocation.md:63–70` · motor tilt angle «наклон 10° даёт ×1.84 по рысканию ценой 1.5 % тяги».
  - *Missing:* R — the trade-off is given but no rule for choosing the angle. Low.
- **ALC-2** · `ctl-allocation.md:53` · Betaflight `mixer_type` (LEGACY default).
  - *Missing:* S — the other options (LINEAR, DYNAMIC, EZLANDING) are not listed with a recommendation. Low.
  - *Elsewhere:* check `bf-features-tour` (outside scope).

---

## 6. Betaflight (selected modules)

### bf-ports.md (L1)

At target quality for UART allocation: «сначала полнодуплексные, потом однопроводные, потом softserial» (`:126`), with a worked F405 example.

- **BFP-1** · `bf-ports.md:71` · «F4 и SBUS … используйте выделенный пин SBUS … или другой протокол (FPort и т.д.)».
  - *Missing:* X with `link-protocols:73` («новые сборки — CRSF»). The L1 reader is pointed to FPort, the one-wire protocol with board-dependent inversion (`:67`), rather than to CRSF. Low-medium.
- **BFP-2** · `bf-ports.md:115` · GPS «57600/115200». See PER-1. Low.

### bf-failsafe.md (L1)

The procedure choice has a rule with a reason («Что выбрать», `:44–45`), and `failsafe_throttle` has a procedure with a target (`:93–95`: «около 1 м/с снижения»).

- **BFS-1** · `bf-failsafe.md:86`, `:35`, `:42` · lab config `set failsafe_landing_time = 10` (default 60); «через `failsafe_landing_time` секунд … дизарм».
  - *Decision:* AUTO-LAND duration.
  - *Missing:* R+V.
    - No rule connects it to altitude and descent rate.
    - With the module's own `failsafe_throttle` target of ~1 m/s, 10 s ends the descent about 10 m below the point of link loss. A 7" lost at 50 m disarms around 40 m up. The lab example is the configuration the reader is told to copy.
    - The module mentions `landing_disarm_threshold` and ALT_HOLD descent, but no pass/fail check of «время ≥ рабочая высота / скорость снижения».
  - *Severity:* **high** — the copied value turns a controlled landing into a drop from height.
  - *Elsewhere:* none.
  - *Fix pattern:* the rule in one line (landing_time ≥ h_max / v_descent with margin), plus a check in the field test (`:99`: hold the switch at known height, read the descent rate from the log).
- **BFS-2** · `bf-failsafe.md:29`, `:61`, `:84`; `eng-method-101:36` · `failsafe_delay`: default 15, LR example 10 («на 250 Гц это 250 потерянных пакетов»), AUTO-LAND example 15, requirement «1.5 с».
  - *Missing:* W+C — the only reason is given for one example. No rule by class or packet rate, i.e. the trade-off between false triggers on short dropouts and distance travelled before Stage 2.
  - *Severity:* medium.
- **BFS-3** · `bf-failsafe.md:58` · GPS Rescue parameters listed with no starting values except the 7" example.
  - *Severity:* low-medium.
  - *Elsewhere:* `bf-gps-setup` (outside scope) — check, then pointer.
- **BFS-4** · `bf-failsafe.md:42` · `landing_disarm_threshold` «около 100» from a source comment.
  - *Missing:* V — no check (false disarm on a hard touch-and-go vs missed impact). Low.

### bf-filters.md (L2)

At target quality for a 5": defaults table, decision table (`:129–134`), acceptance criteria (`:91`), the F4 DSHOT300 / `pid_process_denom` rule (`:110`), notch cutoff = 0.7 × frequency (`:131`).

- **FIL-1** · `bf-filters.md:50–56`, `:87`, `:95`, `:134` · all frequencies and slider ranges are for «5" 6S» and «Для чистого 5"»; «Ничего не помогает ниже 100 Гц → это не фильтры».
  - *Decision:* filter settings on 7", 10", X8 or whoop.
  - *Missing:* C+X.
    - No class adaptation.
    - The «below 100 Hz is not filters» rule is wrong for large props: `f-frame-mech:43` puts the 10" hover harmonic at 80–100 Hz and 15" at 50–70 Hz, and `bf-rpm-filter:28`, `:57` lowers `rpm_filter_min_hz` to 50 for exactly that reason.
    - `dyn_notch_min_hz = 100` gets no class note.
  - *Severity:* medium — the rule exists in the next module, but a 10" reader following step 3 here is told the wrong thing.
  - *Elsewhere:* `bf-rpm-filter:57`, `:66`, `:114` — pointer, plus a class line («для 7–10" сначала `bf-rpm-filter`, шаг 2–3; граница 100 Гц сдвигается»).
- **FIL-2** · `bf-filters.md:74` · «С RPM-фильтром достаточно `count = 1–2` и `q = 300–500`; без RPM-фильтра — `count = 4–5`, `q = 250–300`».
  - *Missing:* W+S — rule without a reason, and no start inside the range (step 1 uses count 2, q 300 — fine; one sentence on why would close it). Low.
- **FIL-3** · `bf-filters.md:91` · temperature «< 50–60 °C».
  - Consistent with `bf-pid:48`. No finding; noted as the canonical value for MOT and WHP cross-references.

### bf-rpm-filter.md (L2)

At target quality for `rpm_filter_min_hz` by class (5" default, 7" 70, 10" 50; `:57`, `:66`, `:114`), with a measure-then-set procedure (`:100–112`).

- **RPM-1** · `bf-rpm-filter.md:54` · `rpm_filter_harmonics` 3 (default).
  - *Decision:* number of harmonics.
  - *Missing:* R — no rule for 1–3 (blade count, where the 2nd and 3rd lines are on the spectrogram) or for the CPU cost on F411 / F405. `f-micro-whoop:136` says «1–3» for whoops.
  - *Severity:* low-medium.
- **RPM-2** · `bf-rpm-filter.md:55` · «2-ю и 3-ю часто можно ослабить до 50–80 на чистых аппаратах».
  - *Missing:* W+V — «чистых» is undefined; the check (attenuation in dB per harmonic, `:60`) is not linked. Low.
- **RPM-3** · `f-motors-esc.md:87` points «см. модуль про RPM-фильтр» for the DShot300 / 600 choice, but `bf-rpm-filter` holds no such rule. It is in `bf-filters:110` and `f-micro-whoop:129`.
  - *Missing:* X (wrong pointer). Medium, merged into MOT-1.
- **RPM-4** · `bf-rpm-filter.md:35` · «Ошибки телеметрии … не выше 1 %» — part of the MOT-4 cluster. Low.

### bf-pid.md (L2)

At target quality: one slider ±0.1 per flight, acceptance criterion, metric table.

- **PID-1** · `bf-pid.md:90–99` · «Ориентиры метрик для 5" 6S»; «Для 7–10" все времена ×1.5–2, overshoot ниже».
  - *Missing:* C+W — the 7–10" scaling has no source and no «оценка» label; whoops and X8 are not covered. Low-medium.
- **PID-2** · TPA (`tpa_rate`, `tpa_breakpoint`, `tpa_mode`, `tpa_low_*`) is not discussed. `f-micro-whoop:140–144` lists defaults «для вупа» equal to the defaults, with no reason.
  - *Decision:* whether to change TPA on a heavy or high-throttle-hover aircraft.
  - *Missing:* R.
  - *Severity:* low-medium.
  - *Elsewhere:* check `bf-pid-reg-in-bf` and `bf-features-tour` (outside scope).

### bf-rates-rc.md (L2)

A mechanism reference at high quality: feedforward settings by packet rate with a source (`:118`), and the throttle curve point «туда, где аппарат реально висит» (`:66`).

- **RAT-1** · rates by aircraft class.
  - *Decision:* max rate for a 7–10" or X8.
  - *Missing:* C+R. Starting rates exist only by style (`ops-pilot-training:82–87`: freestyle / race / cinematic), all implicitly 5".
    - `f-mechanics:48` and `f-physics:71` show a 15" X8 has an order of magnitude less angular acceleration, «отсюда разные PID и rates», but no module gives a rule or starting value for heavy aircraft.
    - Nothing says to check that the max rate is reachable without motor saturation (log: setpoint vs gyro at full stick).
  - *Severity:* medium.
  - *Elsewhere:* none.
- **RAT-2** · `bf-rates-rc.md:64–66`; `:368` · `thr_expo`: no starting value in theory; «на 4.5 задать `thr_expo` 20–50» appears only in diagnostics. Low.
- **RAT-3** · `bf-rates-rc.md:46–62` · five rate types: no recommendation in this module.
  - *Severity:* low.
  - *Elsewhere:* `ops-pilot-training:89`, `:95` (Actual, the same type in sim and on the aircraft) — pointer.

---

## T. Terms at first use (L1 modules) and English calques

**How this was checked.** Each term's first occurrence along the Betaflight path (`data/curriculum.json` → `paths[betaflight]`) was located, and the line was checked for an inline explanation. The glossary (`data/glossary.json`, 336 terms) is a separate page; `scripts/build_site.py:1029` renders it, and terms are not auto-linked in module text. So a glossary entry alone does not explain a term at first use. The glossary status is given for each term because it shows where a definition already exists to copy.

### T1. Terms used without explanation at first use

| # | First use | Term | Inline explanation | In glossary | Severity |
|---|---|---|---|---|---|
| T1-1 | `f-physics.md:53` | «air mode и mixer scaling» | none | no («Air mode» absent) | medium — in the first module of the course; the sentence is the explanation of saturation |
| T1-2 | `f-physics.md:20`, `f-mechanics.md:48–49` | PID, «D», «I-term», «rates» | no (PID is explained in `bf-pid-reg-in-bf`, much later) | PID, D-term yes; I-term no | low — add «(регулятор, модуль …)» once |
| T1-3 | `f-electricity-101.md:23` | BEC | defined only in the next module (`f-power:43`) | yes | low |
| T1-4 | `f-power.md:46`, `:52`, `:55` | «p95», «BMS», «IR» | no | no / no / no | low |
| T1-5 | `f-motors-esc.md:67`, `:76` | notch («RPM-фильтр ставит notch'и мимо») | no | generic «notch» absent (only Dynamic / Harmonic notch) | medium — the notch is the reason `motor_poles` matters, which is this module's main check |
| T1-6 | `f-motors-esc.md:87` | «на типовом 4k–8k цикле» (PID loop rate) | no | «Цикл PID (PID loop, looptime)» yes | low |
| T1-7 | `f-fc-sensors.md:40`, `:54`, `:59`, `:62`, `:64`, `:67` | EKF, DMA, LPF, «антиалиасинговый», MSP DisplayPort, PDB, SmartAudio, Softserial (partly explained), hwdef, unified target, DroneCAN | mostly no; the «Гироскоп ближе» subsection is L2 density inside an L1 module | EKF, DMA, MSP DisplayPort yes; LPF, PDB, SmartAudio no | medium (by density) — split the subsection off as «для любопытных» or add one-line glosses |
| T1-8 | `f-safety.md:89` | «LQ/RSSI» in the preflight checklist | no; explained in `link-protocols:52` and `link-elrs:92`, later in the path | LQ yes, RSSI no | medium — a checklist item the reader cannot evaluate |
| T1-9 | `f-regulations.md:100` | EIRP («100 мВт EIRP», «25 мВт EIRP») | no | no | medium — the reader cannot compare a VTX's «мВт» with the legal «EIRP» without antenna gain (link to `rf-link-budget`) |
| T1-10 | `f-regulations.md:127` | DROP, RTH | no | not checked | low |
| T1-11 | `f-starter-kit.md:54`, `:118`, `:185` | LBT, «`diff all` в файл», «ELRS Lua» | no | diff all yes | low |
| T1-12 | `eng-method-101.md:37`, `:45`, `:71` | LQ, UBX, MSP, D-term, bounce-back, overshoot | no | partly | low (example rows; one line «пример, термины — в модулях …») |
| T1-13 | `el-wiring.md:43` (L1), also `f-fc-sensors:62` | PDB | no | no | low |
| T1-14 | `bf-ports.md:51`, `:79` | MSP, VCP | partly (`:78` «MSP нужен конфигуратору») | MSP RX / DisplayPort only | low |
| T1-15 | `bf-failsafe.md:29`, `:44` | «Channel fallback», «crash recovery» | partly | not checked | low |
| T1-16 | `diag-troubleshooting.md:65`, `:76`, `:77` (L1) | buck, U.FL, LC-фильтр, HDOP | no | HDOP yes | low |

### T2. English calques where a Russian term exists

Only «петля» is in SPEC "Terminology". The others are listed as candidates for the same rule (Russian term, English once in brackets), for the owner to decide.

| # | Calque | Where (in scope) | Russian term the course already uses elsewhere | Severity |
|---|---|---|---|---|
| T2-1 | «петля» | `el-kicad.md:55`, `:101`, `:118` («петли тока»); `el-wiring.md:50` («0.3 м петли») | physical current or wire loops — **allowed** by SPEC; no violation | — |
| T2-2 | «без петель» (routing loop) | `link-protocols.md:54` («звезда без петель») | not covered by SPEC: neither control «контур» nor periodic «цикл»; a network routing loop. «без циклов маршрутизации» or keep with a note | low (owner's call) |
| T2-3 | «дефолт», «дефолтный», «к дефолту» | `bf-failsafe.md` (6 lines incl. `:29`, `:34`, `:35`, `:42`, `:55`), `bf-rates-rc.md` (15 lines incl. `:58`, `:77`), `bf-ports.md:103–105`, `bf-rpm-filter.md:45` (+1), `ops-pilot-training.md:78` | «по умолчанию», «умолчание» — tables in the same modules already say «По умолчанию» | medium (frequency; `bf-failsafe` is L1) |
| T2-4 | «тюнинг», «тюнить», «тюн», «перетюнить» | `bf-pid.md:3` (title), `:11` (tag), `:29`, `:82`, `:102`; `bf-filters.md:67`, `:102`; `f-frame-mech.md:40`; `f-mechanics.md:91` (L1); `design/ctl-allocation.md:308` and others | «настройка» («настройка по данным» is the course's own phrase in `eng-method-101:71`, `curriculum.json` stage «Настройка по данным») | medium (module title) |
| T2-5 | «панч», «на панчах» | `f-power.md:37`, `:52`, `:95` (L1) | «резкий набор газа (punch-out)» | low |
| T2-6 | «клиппится», «клиппят», «клиппинг» | `f-frame-mech.md:36` (glossed «(насыщение)»), `:60` (unglossed); `est-sensors.md:40` (glossed), `:63`; `diag-troubleshooting.md:110` (L1, unglossed) | «насыщение (clipping)» | low |
| T2-7 | «глитч» | `bf-failsafe.md:52`, `:67` (L1); `diag-troubleshooting.md:185` («GPS-глитч») | «кратковременный сбой (glitch)» | low |
| T2-8 | «D-term», «I-term» inside Russian sentences | `f-mechanics.md:49` (L1), `eng-method-101.md:71` (L1), `bf-filters.md:40`, `:58`, `:83`, `:103` | «D-составляющая», «I-составляющая» — the glossary definition and `aero-stability:69` («I-составляющая») already use these | low |
| T2-9 | «desync» in Latin script | `diag-troubleshooting.md:62` («ESC desync») | «срыв синхронизации (десинк)», as in `f-esc-firmware:44` | low |

---

## Proposed order of fixing

Ranked by severity × how early in the Betaflight path the module sits, i.e. how many readers hit it before the rule appears anywhere. Where a defect repeats, fix it once at the canonical place and add pointers elsewhere.

### Wave 1 — high, stages 1–2

1. **Battery warning and landing thresholds** — POW-2, plus CAS-1, BAT-3, ETX-2, WHP-4, ELE-2. Canonical place: `f-power` (stage 1, L1).
   - Mechanism: sag under load vs rest voltage.
   - Table by chemistry × class (LiPo 5", Li-Ion LR, 1S LiHV whoop), each cell with a source or «оценка».
   - Procedure: from a log or discharge curve (closes CAS-1), then the check «напряжение покоя после посадки».
   - Then point `bf-modes-osd`, `link-edgetx`, `el-battery-packs`, `f-micro-whoop` to it.
2. **KV for prop × cell count** — AER-1 (with CMP-1, WHP-5). Canonical place: `f-aero-props` (stage 1).
   - Move the `des-sizing:68–72` mechanism forward (rpm under load ≈ 0.75–0.85·KV·U).
   - Add a class × S table from manufacturer thrust tables.
   - Check: hover current and motor temperature.
3. **LiPo C rating and capacity from peak current** — BAT-1 (with ELE-1, CMP-4).
   - Canonical rule in `f-power` or `f-components-choice` (stage 1); `el-battery-packs` reuses the Li-Ion derating pattern.
   - Check: sag on punch in the log against the IR estimate.
4. **AUTO-LAND duration** — BFS-1 (`bf-failsafe`, stage 2, L1).
   - Rule `failsafe_landing_time ≥ h_max / v_descent + запас`.
   - Correct or annotate the lab value 10.
   - Add the descent-rate check to the field test.

### Wave 2 — medium, stage 1: one canonical number per threshold

5. **One «canonical numbers» pass** over stage 1, each with source and class:
   - T/W by class (PHY-2, MOT-5);
   - hover throttle band (PHY-3, ENG-1, CMP-1);
   - hover current as a share of the *continuous* rating (AER-3);
   - DShot error ceiling (MOT-4, RPM-4);
   - cell imbalance after charge and after flight (ELE-3, BAT-4, MNT-1).

   This is cheap and removes most X-type findings.
6. **DShot speed and PID loop rate** — MOT-1, RPM-3, FCS-1. Fix the wrong pointer in `f-motors-esc:87` and add a one-line rule with pointers to `bf-filters:110` and `f-micro-whoop:88–92`.
7. **Props in / props out** — PHY-1, DIA-1. Needs a source; the rule goes in `f-physics`.
8. **Demag compensation and startup by class** — MOT-2, ESC-1. Add rows to the `f-esc-firmware` table in the PWM subsection's format.
9. **Tilt compensation** — MEC-1. Value, start and check, or an explicit «не трогать на Acro-5"».
10. **L1 terms and calques in stage 1–2:**
    - T1-1 (air mode), T1-5 (notch), T1-7 (density in `f-fc-sensors`), T1-8 (LQ/RSSI in the checklist), T1-9 (EIRP).
    - T2-3 «дефолт» and T2-4 «тюнинг» (including the `bf-pid` title).
    - Extend SPEC "Terminology" first, so later edits follow it.
11. **Mechanics choices** — FRM-1 (soft vs hard mount on 5"), FRM-2 (arm thickness vs the 7" danger zone), AER-2 (pitch and blades: pointer to the lab procedure plus class starts).
12. **Micro and link medium items** — WHP-1 (dynamic idle), WHP-3 (harmonics), ETX-1 (CRSF baud table vs text), VTX-1 (`vtx_low_power_disarm`), BFS-2 (`failsafe_delay`), CMP-5 (pointers to `link-digital-video` and `link-elrs`).

### Wave 3 — medium, stage 4 (electronics)

13. **Connector and wire criteria** — PWR-2, WIR-2, PWR-3, WIR-1. Which current to compare (average, p95, peak); acceptable drop and heat as pass/fail; reconcile the XT60 / XT90 numbers with datasheets.
14. **Bulk capacitor by class** — PWR-1.
15. **LC filter selection and check** — EMI-1.

### Wave 4 — medium, stage 6 and off-path

16. **Filter class adaptation** — FIL-1: fix «ниже 100 Гц — не фильтры» for 7–15" and point to `bf-rpm-filter`.
17. **Rates for heavy aircraft** — RAT-1.
18. **GNSS receiver choice** — GNS-1 (the summary promises it).

### Wave 5 — low

19. A sweep module by module in path order. Most lows are one-line pointers («правило — в `<module>`») or an «оценка» label on an unsourced number. Batch them per module when the module is next edited for another reason.

**Sources that would settle the open items**, none proposed from memory here:
- manufacturer thrust tables across classes and cell counts (AER-1);
- LiPo IR or independent discharge tests (BAT-1);
- Betaflight `cli/settings.c` and the docs for `thr_corr_*`, `yaw_motors_reversed`, `rpm_filter_harmonics`, `dyn_idle_*`, `mixer_type` (MEC-1, PHY-1, RPM-1, WHP-1, ALC-2);
- Bluejay wiki and AM32 / BLHeli_32 manuals for demag and startup (MOT-2);
- Amass connector datasheets (PWR-2);
- capacitor datasheets (PWR-1);
- `CRSFHandset.cpp` 4.1.0 for ETX-1.
