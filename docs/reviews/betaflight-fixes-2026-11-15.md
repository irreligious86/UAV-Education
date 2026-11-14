# Betaflight track fixes — 2026-11-15

Fixes for `docs/reviews/betaflight-coverage-audit.md` §6.3, plus the in-flight PID-profile sweep and the `diff` / `diff all` sweep.
Primary source: `betaflight/betaflight` branch `4.5-maintenance`, commit `7dcc851` (version.h 4.5.6), local shallow clone. Release tags
(4.3.0 … 4.5.5, 2025.12.1) were read from `raw.githubusercontent.com`. Nothing was committed and `publish.py` was not run.
`validate_content.py` reports the same 8 errors as before the edits. All of them are in other authors' files: modules missing from
the manifest, the nav-vtrn quiz length rule, and a missing nav-vtrn diagram.

## Changes

| # | §6.3 | File | Before → after (short) | Source |
|---|---|---|---|---|
| 1 | 3 | `content/betaflight/bf-pid.md` summary | "четыре профиля в одном полёте" → "четыре коротких полёта подряд по одной программе" | `fc/rc_adjustments.h` (no PID-profile adjustment), `fc/rc_controls.c` |
| 2 | 3 | `bf-pid.md` theory "Слайдеры" | "переключаются тумблером или `profile N`" → the rate profile can be switched in flight (`RATE PROFILE`); the PID profile only on the ground when disarmed: sticks / OSD menu / Configurator / `profile N` (0–3) | `fc/rc_adjustments.c`, `fc/rc_controls.c` L270–283, `cli/cli.c` `cliProfile` |
| 3 | 3 | `bf-pid.md` case intro + results line | added "каждый профиль — свой короткий полёт, четыре полёта подряд"; "медианы" → "четыре полёта, медианы". Numbers unchanged | as above |
| 4 | 3 | `bf-pid.md` case, bullet "два одинаковых дрона" | "сравнивать только внутри одного полёта" → "внутри одной серии полётов (один пилот, одна программа, одно окно заряда)" | as above |
| 5 | 3 | `bf-pid.md` protocol step 4 | "переключение тумблером" → chosen on the ground; the PID profile cannot be switched in flight in 4.5 | as above |
| 6 | 3 | `bf-pid.md` practice Шаг 2 | "тумблером (режим или adjustment), чтобы менять в воздухе" → the method that works: stick commands (Mode 2, thr low + yaw left + roll left / pitch up / roll right → profiles 1/2/3; no stick command for 4; confirmation beeps); OSD menu (thr mid + yaw left + pitch up → PROFILE → PID PROF, covers profile 4); CLI `profile 0..3`. A stick or menu choice made without SAVE is lost on re-plug. Honest in-flight alternative: rate profiles via adjustment function 12, but PID/sliders/D-max/FF cannot be carried in a rate profile | `fc/rc_controls.c` L230, L270–283; `cms/cms.c` L1498; `cms/cms_menu_main.c` "PROFILE"; `cms/cms_menu_imu.c` "PID PROF"; `config/config.c` `changePidProfile` (no save); `cli/settings.c` rate-profile table |
| 7 | 3 | `bf-pid.md` practice Шаг 3 | "Профили по очереди в одном вылете" → four short consecutive flights, profile switched and checked on the ground, same battery window (fresh pack per flight from one batch, same landing voltage per cell), order rotated between series | method |
| 8 | 3 | `bf-pid.md` practice Шаг 5 | "Назад — одним движением тумблера" → "одной стик-командой на земле" | `fc/rc_controls.c` |
| 9 | 3 | `bf-pid.md` diagnostics | "внутри одного полёта" → "внутри одной серии полётов с одной программой и одним окном заряда" | method |
| 10 | 3 | `content/quiz/bf-pid.json` Q "Два «одинаковых» дрона…" | option "Сравнивать в одном полёте" → "Сравнивать в одной серии полётов"; explain updated the same way (correct answer is still not the longest option) | method |
| 11 | 3 | `content/betaflight/bf-intro.md` "Карта настройки" | "переключаемые тумблером/adjustments" → only the rate profile can be switched in flight; PID profile on the ground (sticks, OSD, `profile N`) | `fc/rc_adjustments.c` |
| 12 | 1 | `bf-intro.md` diagnostics (Cloud Build) | "`version` → список опций" → "`status` → BUILD KEY → option list on build.betaflight.com; `version` prints only version/target/date/git" | `cli/cli.c` `printVersion()`, `cliStatus()` |
| 13 | 2 | `bf-intro.md` "Архитектура прошивки" | "`pid_process_denom = 2` … типичная отправная точка" → default is 1 (PID = gyro rate); F4/G4 with bidir DShot and gyro > 4 kHz forces ≥ 2 and DSHOT600 → 300 | `flight/pid.c` `DEFAULT_PID_PROCESS_DENOM 1`; `config/config.c` `USE_PID_DENOM_CHECK` (defined in STM32F405/F411/G47X targets) |
| 14 | 12 | `bf-intro.md` versions | "(последний выпуск 4.5.5)" kept, with one addition: the `4.5-maintenance` branch already carries 4.5.6, and the SITL in «Betaflight с нуля» is built from that branch. Checked: tag `4.5.5` exists, tag `4.5.6` does not (404), so 4.5.5 is still the latest release | `build/version.h` at branch head and at tag 4.5.5 |
| 15 | 13 | `bf-intro.md` "Поддержка" | "STM32 (F4, F7, H7)" → "STM32 (F4, F7, H7, G4) и AT32F435; в 2025.12 добавлены APM32 и RP2350" | `src/main/target/` (4.5: AT32F435G/M, STM32G47X); `src/platform/{APM32,PICO}` (2025.12, PICO/target/RP2350A/B) |
| 16 | 4 | `content/betaflight/bf-pid-reg-in-bf.md` theory I-term | "`iterm_limit` (в 2025.12 — `iterm_windup`)" → two separate variables in 4.5: `iterm_windup` 85 (attenuates I accumulation as the motor mix nears saturation) and `iterm_limit` 400 (absolute cap). 2025.12 removed `iterm_limit`; there `iterm_windup` (default 80) sets the I cap as % of `pidsum_limit`. Not a rename | 4.5 `flight/pid.c` L136/L154, `pid_init.c` L300–314, `pid.c` L860; 2025.12 `pid.c` L144, `pid_init.c` L445 |
| 17 | 4 | `bf-pid-reg-in-bf.md` formula bullet | "с ограничением `iterm_limit` (анти-windup)" → "Ki weakened by `iterm_windup` on saturation, cap `iterm_limit`" | as above |
| 18 | 4 | `bf-pid-reg-in-bf.md` diagnostics "медленные колебания" | "`iterm_limit` (дефолт 400; в 2025.12 — `iterm_windup`)" → check both (85 / 400); in 2025.12 there is no `iterm_limit` | as above |
| 19 | 5 | `bf-pid-reg-in-bf.md` practice step 6 | "снизьте `tpa_breakpoint` до 1400" → "снизьте ниже дефолтных 1350 (например, до 1250), чтобы TPA начинался раньше" | `flight/pid.c` `.tpa_breakpoint = 1350` |
| 20 | 6 | `bf-pid-reg-in-bf.md` practice step 1 | invalid `\n` / comma `set` lines with sub-default values → fenced `text` block, one `set` per line, 4.5 defaults (roll 45/80/40, d_min 30; pitch 47/84/46, d_min 34; yaw 45/80/0); the 2025.12 naming note moved to prose | `cli/cli.c` `cliSet`; `flight/pid.h` `PID_*_DEFAULT`, `D_MIN_DEFAULT` |
| 21 | 6 | `bf-pid-reg-in-bf.md` practice "Подготовка" step 3 | unfenced filter lines + stray `text` → fenced `text` block (values unchanged) | formatting |
| 22 | 7 | `bf-pid-reg-in-bf.md` practice "Подготовка" step 2 | "включите логирование gyro_scaled, pid, setpoint, motor" → fields are logged by default (check `blackbox_disable_*` = OFF); `GYRO_SCALED` is a `debug_mode`, not a field group | `blackbox/blackbox.c` `.fields_disabled_mask = 0`; `cli/settings.c` `blackbox_disable_*`; `build/debug.c` |
| 23 | 8 | `bf-pid-reg-in-bf.md` practice step 2 | "bounce-back — P низкий, увеличьте" → bounce-back is not "low P": check D/Damping, I-term relax, D-filter delay (as in the worked example); raising P alone usually makes it worse | course-internal (`bf-pid` symptoms, this module's worked example) |
| 24 | 8 | `bf-pid-reg-in-bf.md` diagnostics "Bounce-back" | cause "низкий P, высокий D", action "увеличить P" → cause under-damping / I-relax off / D-filter delay; action Damping +0.1–0.15, `iterm_relax = RP`, D filters | as above |
| 25 | 10 | `content/betaflight/bf-modes-osd.md` OSD HD | "канва 50×18/60×22" → default 53×20 (`OSD_HD_COLS/ROWS`); the HD system reports its own canvas over MSP (`MSP_SET_OSD_CANVAS`) and the firmware adapts `osd_canvas_width/height`; sizes are vendor-specific | `osd/osd.h` L89–90, `osd/osd.c` L418, L537–541, `msp/msp.c` L4327 |
| 26 | 11 | `bf-modes-osd.md` `aux` paragraph | "`adjrange` … (PID, рейты, профили)" → profiles = rate/OSD/LED only; no PID-profile adjustment in 4.5 | `fc/rc_adjustments.h` enum |
| 27 | diff sweep | `content/betaflight/bf-cli-automation.md` lab Шаг 3 | "после — новый diff" → "новый `diff all` (`viking2_after_diff.txt`)" + one sentence: plain `diff` saves only the current PID and rate profile | `cli/cli.c` `printConfig`: profile loop only under `DUMP_ALL` (L6201, L6335) |

Structure: headings and `{{…}}` directives are unchanged in every file. Code fences are unchanged except in `bf-pid-reg-in-bf.md`
(0 → 4 fence lines, i.e. 0 → 2 blocks). This was deliberate (#20, #21): the old blocks had lost their fences, which left the
stray `text` lines.

## §6.3 items verified and left unchanged

| §6.3 | Finding |
|---|---|
| 9 (`bf-failsafe`, "дефолт 1.5 с (так же в 4.3–4.4…)") | **The course is right; the audit's point is wrong.** `failsafe_delay = 15` (1.5 s) in `flight/failsafe.c` at tags 4.3.0, 4.3.2, 4.4.0 and 4.4.3. The official `Failsafe.md` ("1.0s in 4.4") is wrong. `failsafe_recovery_delay` 10 → 5 between 4.4 and 4.5 matches the course |
| 12 (4.5.5 vs 4.5.6) | Only a clarification was added (#14). "Latest release 4.5.5" is correct, because the 4.5.6 tag does not exist |
| 14 (betaflight.com In-flight Adjustments page) | Docs-side issue. The course never copies "12 ranges" or SLIDER_MASTER_MULTIPLIER (grep) |
| 15 (`bf-cli-automation`, "`noreboot` появился в 4.5.4") | **Verified correct.** `noreboot` is absent from `cli/cli.c` at tags 4.5.0–4.5.3, present at 4.5.4, 4.5.5 and 2025.12.1 |
| 16 (`bf-cli` / `bf-custom`, `…/api/builds/<BUILD_KEY>/json`) | **Verified from client code.** `betaflight-configurator` master `src/js/BuildApi.ts` calls `https://build.betaflight.com/api/builds/${key}/json` (`requestBuildOptions`). The live endpoint itself could not be called (proxy 403) |

## Sweeps

- In-flight PID-profile switching: after the edits, no instance is left in `content/betaflight/`, `content/quiz/bf-*.json`,
  `content/tasks/bf-*.json` or `content/pages/setup-cards.html`. The ones fixed were `bf-pid` (#1–#9), the `bf-pid` quiz (#10),
  `bf-intro` (#11) and `bf-modes-osd` (#26). `bf-cli.md` "`profile 1`, `rateprofile 2`" is a valid CLI example and was left as is.
- `diff` vs `diff all`: `bf-cli-automation` lab step 3 (#27) was the only backup instruction that used plain `diff`. All other
  backup instructions already say `diff all`. The plain `diff` in `bf-cli.md` L53 is only a list of viewing commands.

## Observations outside §6.3 (not changed)

- `bf-pid-reg-in-bf` filter block: `gyro_lpf2_static_hz = 300`, `dyn_notch_q = 250`, `*_lpf2_type = PT2`. The 4.5 defaults are
  500 / 300 / PT1 (`sensors/gyro.h`, `pg/dyn_notch.c`, `sensors/gyro.c`), and the module gives no reason for these values.
  This should be reviewed together with the `bf-filters` author.
- Built translations `en/quiz/bf-pid.json` and `uk/quiz/bf-pid.json` still have the old wording until the i18n/publish pipeline
  runs again.
