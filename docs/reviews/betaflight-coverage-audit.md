# Betaflight coverage audit — CLI, `set` variables, Adjustments, popular questions, hardware integration

Date: 2026-11-14. Scope: the Betaflight track (`content/betaflight/*.md`, 13 modules) plus the Betaflight-relevant parts of
`content/link/*`, `content/foundation/f-motors-esc.md`, `f-esc-firmware.md`, `f-fc-sensors.md`, `content/electronics/*`,
`content/pages/*.html` (including `setup-cards.html`), and, for §7, `content/companion/payload-gimbal.md` and the INAV/ArduPilot
setup modules. Goal set by the owner: close the Betaflight topic completely — everything that can be set from the CLI, the
Adjustments tab, and the questions people actually ask. No course content was edited.

Legend used throughout: **✓** explained (meaning and usage given, module id) · **~** mentioned only (name appears, no usable
explanation) · **✗** absent. Priority for the course: **A** must-know for anyone who builds and flies a Betaflight quad ·
**B** useful, a good student should know it · **C** niche.

---

## 1. Method and sources

### 1.1 Firmware sources (read locally, no build)

| Source | Version | How |
|---|---|---|
| `betaflight/betaflight`, branch `4.5-maintenance`, commit `7dcc851` (2026-11-01) | `version.h`: **4.5.6** | shallow clone (1 commit) in the scratchpad; `src/main/cli/settings.c` and `cli/cli.c` also re-downloaded from `raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/...` — byte-identical |
| `betaflight/betaflight`, branch `2025.12-maintenance`, commit `5b88201` (2026-10-24) | `version.h`: **2025.12.6** | shallow clone |
| `betaflight/betaflight`, `master`, commit `a12049c` (2026-11-08) | `version.h`: 2026.12.0 (development) | shallow clone, used only to see what is coming after 2025.12 |
| `betaflight/betaflight.com` docs repo, commit `357535a` (2026-11-05) | "current" guides = 2025.12 | `docs/wiki/guides/current/*.md`, `docs/wiki/app/*.md` |
| ArduPilot (`AP_Mount_Params.cpp`, `AP_SerialManager.cpp`, `AP_OSD.cpp`, `SRV_Channel.h`) | master snapshot already in the scratchpad (date not recorded) | §7 only |
| INAV `settings.yaml` (master) and `y_8.0.0.yaml` | INAV 8.x / master | §7 only |

Files read in full or in the relevant parts: `cli/cli.c` (command table `cmdTable[]`, `cliStatus`, `printVersion`,
`cliAdjustmentRange`, `cliDshotProg`, `cliServo`, LED/colour formats), `cli/settings.c` (`valueTable[]`, lookup tables),
`fc/rc_adjustments.[ch]`, `fc/core.c`, `fc/rc_controls.c`, `fc/runtime_config.c`, `flight/failsafe.c`, `flight/pid.[ch]`,
`flight/imu.c`, `flight/servos.[ch]`, `flight/mixer.c`, `pg/motor.c`, `pg/rx.c`, `config/config.c`, `osd/osd.h`,
`msp/msp_box.c`, `io/serial.h`, `io/beeper.c`, `io/vtx_control.h`, `drivers/dshot_command.h`, `target/common_pre.h`,
`target/common_defaults_post.h`, `fc/controlrate_profile.c`, `blackbox/blackbox.c`, `rx/crsf_protocol.h`, 2025.12
`io/gimbal_control.c`.

Variable counts and defaults were extracted with a small parser (`valueTable[]` → name, PG, scope, range; defaults
from `PG_RESET_TEMPLATE`, `pgResetFn_*`, `resetPidProfile`, macros resolved). Every default quoted in this report for an
A/B variable was then checked by hand in the source file named. Two traps found by the hand check, both from `#ifdef
USE_RACE_PRO` blocks: the standard defaults are `small_angle = 25` (180 only in RACE_PRO builds) and
`failsafe_recovery_delay = 5` (1 only in RACE_PRO builds). Target-specific defaults (`motor_pwm_protocol`,
`serialrx_provider`, `vbat_scale`, `ibata_scale`, `pid_process_denom` after the F4 bidir check) can differ per board;
they are given as the generic source default and marked "target-dependent".

**Could not build or run.** Building the 4.5 SITL target (`make TARGET=SITL`) to dump `dump all` defaults was refused by the
session's permission policy, so no default here comes from a running firmware. The course's own SITL outputs
(`bf-setup-scratch`) were not re-run.

### 1.2 Web sources

| Source | Status |
|---|---|
| GitHub API (`gh api`, `api.github.com`) for releases, issue/discussion reaction counts | **blocked** (403, "GitHub access to this repository is not enabled for this session"). Release list therefore not verified; versions above come from `version.h` on the maintenance branches |
| `raw.githubusercontent.com` | works (used for the cross-check above) |
| Reddit r/fpv (`reddit.com/.../search.json`) | **blocked** ("SITE_BLOCKED") |
| oscarliang.com | one page fetched: [Why your Betaflight drone won't arm](https://oscarliang.com/quad-arming-issue-fix); the troubleshooting index failed (client error) |
| IntoFPV, RotorBuilds | not fetched directly; topic frequency estimated from web-search hit lists (links in §5) |
| betaflight.com FAQ / Failsafe / In-flight Adjustments / LED Strip / Servos | read from the docs repo |

Because reaction counts could not be read, the "how common" column in §5 uses an evidence class instead of a number:
**O** — the official docs have a dedicated FAQ/troubleshooting entry or page; **L** — Oscar Liang has a dedicated guide;
**F** — several forum threads (IntoFPV) on the first page of a web search; **G** — a GitHub issue/discussion found by search.
More letters = more common. This is an ordering, not a measurement.

### 1.3 Version note — 4.5 is no longer the newest line

The brief calls 4.5 "current stable". Per the source tree, **2025.12 is the newer maintained line** (branch
`2025.12-maintenance`, at 2025.12.6) and `master` is already 2026.12 development. The course already says this in
`bf-intro` ("4.5 — предыдущая стабильная ветка"). This audit keeps 4.5 as the reference (the course's SITL work is 4.5.6) and
lists 2025.12 differences wherever a name changes. Summary of 2025.12 vs 4.5 relevant to this audit:

- CLI commands: **identical set of 59** (only `flash_read` argument order changed: 4.5 `<length> <address>`, 2025.12
  `<address> <length>`).
- `set` variables: 683 → 760 raw table entries (+114 / −37). Removed or renamed: `d_min_*` → `d_max_*` with inverted meaning
  of `d_*`, `simplified_dmax_gain` → `simplified_d_max_gain`, `dshot_idle_value` → `motor_idle`, `failsafe_off_delay` →
  `failsafe_landing_time` (seconds), `iterm_limit` removed, `crashflip_expo` → `crashflip_rate` (+`crashflip_auto_rearm`),
  `gps_rescue_throttle_*`/`gps_rescue_landing_alt` replaced by the shared autopilot `ap_*` set, `min_throttle` removed,
  `rc_smoothing_feedforward_cutoff` removed, `expresslrs_rate_index`/`expresslrs_switch_mode` removed, per-gyro
  `gyro_1_*`/`gyro_2_*` → `gyro_N_enabled`/`gyro_enabled_bitmask`. Added: altitude hold and position hold (`alt_hold_*`,
  `pos_hold_*`, `ap_*`), new TPA curve and "speed TPA" for wings (`tpa_curve_*`, `tpa_speed_*`), servo/wing
  `s_roll/s_pitch/s_yaw`, `spa_*` (setpoint PID attenuation), chirp excitation (`chirp_*`), MAVLink telemetry rates
  (`mavlink_*_rate`), optical flow (`opticalflow_*`), serial camera gimbal (`gimbal_*`), `yaw_type`, `thr_hover`,
  `landing_disarm_threshold`, `prearm_allow_rearm`, `osd_arming_logo`.
- Arming flags: 4.5 has 26 (last `ARMSWITCH`); 2025.12 adds `FLIP_SWITCH`, `ALT_HOLD_SW`, `POS_HOLD_SW` and renames
  `ARMSWITCH` → `ARM_SWITCH`.
- Adjustments: 2025.12 adds function 31 `LED_DIMMER`; `master` adds `SIMPLIFIED_MASTER_MULTIPLIER` (the current
  betaflight.com page already documents it as 31 — it is **not** in 2025.12, the docs are ahead of the release).
- MCUs: 4.5 targets are STM32 F405/F411/F446/F7x2/F745/G47x/H723/H725/H730/H743/H750 and **AT32F435**; 2025.12 adds
  APM32 and PICO (RP2350) platforms.

---

## 2. CLI commands (4.5): all 59

Source: `cmdTable[]` in `src/main/cli/cli.c` (4.5-maintenance). Some commands exist only when the build has the feature
(`#ifdef` in brackets). Coverage was measured by grepping every module for the command used as a command (in backticks or
at line start), then checking each hit by hand.

| # | Command | What it does (one line) | Course | Pri |
|---|---|---|---|---|
| 1 | `adjrange` | in-flight adjustment ranges: `<index> <unused> <range ch> <start> <end> <function> <adj ch> [<center> <scale>]` | ~ bf-modes-osd (one sentence) | A |
| 2 | `aux` | mode ranges: `<index> <mode permanentId> <aux> <start> <end> <logic>` | ✓ bf-modes-osd, bf-setup-scratch | A |
| 3 | `batch` | `batch start` / `batch end` — apply a pasted block, single reboot | ✓ bf-cli | A |
| 4 | `beacon` | which conditions fire the DShot beacon (motor beeps): `list`, `[-]name` [USE_DSHOT] | ✗ | B |
| 5 | `beeper` | which conditions sound the buzzer: `list`, `[-]name` | ~ bf-cli (named in a table) | B |
| 6 | `bind_rx` | put an SPI RX, SRXL2 or **CRSF/ELRS** receiver into bind mode from the FC [USE_RX_BIND] | ✗ | B |
| 7 | `bl` | reboot to bootloader (`bl`, `bl rom`; `flash` on external-flash targets) | ~ bf-cli | A |
| 8 | `board_name` | read/set board model name (unified target identity) | ~ bf-cli, bf-intro | C |
| 9 | `color` | LED strip colour palette: `color <i> <h>,<s>,<v>` [LED_STRIP_STATUS_MODE] | ✗ | B |
| 10 | `defaults` | reset to defaults and reboot; `defaults nosave` | ✓ bf-cli | A |
| 11 | `diff` | changes from default; `[master\|profile\|rates\|hardware\|all] {defaults\|bare}` | ✓ bf-cli (`diff all` only; the scopes/flags are not explained) | A |
| 12 | `dma` | show/set DMA streams: `dma show`, `dma <dev> <idx> [opt\|none]`, `dma <dev> <idx> list` | ✓ bf-cli (worked example) | B |
| 13 | `dshot_telemetry_info` | per-motor eRPM and DShot telemetry error stats [USE_DSHOT_TELEMETRY] | ~ bf-rpm-filter, bf-cli | A |
| 14 | `dshotprog` | send raw DShot commands (0–47) to ESC(s): `<index\|255> <cmd>+` | ✓ bf-setup-scratch | B |
| 15 | `dump` | full config incl. defaults, same scopes as `diff` | ✓ bf-cli | B |
| 16 | `escprog` | ESC serial passthrough `<sk\|bl\|ki\|cc> <index>` [USE_ESCSERIAL] | ~ bf-cli | C |
| 17 | `exit` | leave CLI and reboot; `exit noreboot` | ✓ bf-cli-automation | A |
| 18 | `feature` | list/enable/disable features (`feature -GPS`, `feature LED_STRIP`) | ~ (used in examples, the feature list is never shown) | A |
| 19 | `flash_erase` | erase onboard log flash [USE_FLASHFS] | ✗ | B |
| 20 | `flash_info` | flash chip size/usage | ~ bf-cli | B |
| 21 | `flash_read` | raw read `<length> <address>` [USE_FLASH_TOOLS] | ✗ | C |
| 22 | `flash_scan` | scan flash for errors [USE_FLASH_TOOLS] | ✗ | C |
| 23 | `flash_write` | raw write `<address> <message>` [USE_FLASH_TOOLS] | ✗ | C |
| 24 | `get` | read variables (substring match: `get gps_rescue`) | ✓ bf-cli | A |
| 25 | `gpspassthrough` | bridge USB to the GPS UART (u-center) [USE_GPS] | ✗ | B |
| 26 | `gyroregisters` | dump gyro config registers | ~ bf-cli | C |
| 27 | `help` | list commands, `help <search>` | ~ bf-cli-automation | A |
| 28 | `led` | LED strip layout: `led <i> <x>,<y>:<dirs>:<functions>:<colour>` | ✗ | B |
| 29 | `manufacturer_id` | read/set manufacturer id | ~ bf-cli | C |
| 30 | `map` | RC channel order (`map AETR1234`) | ~ bf-intro, bf-setup-scratch | A |
| 31 | `mcu_id` | unique MCU id | ~ bf-cli | C |
| 32 | `mixer` | frame type (`mixer list`, `mixer QUADX`) [!QUAD_MIXER_ONLY] | ~ bf-setup-scratch | A |
| 33 | `mmix` | custom motor mix rows `mmix <i> <thr> <roll> <pitch> <yaw>`, `mmix reset`, `mmix load <mixer>` | ✗ for Betaflight (only INAV and `ctl-allocation`) | B |
| 34 | `mode_color` | LED colour per mode/special function: `mode_color <mode> <fn> <colour>` | ✗ | C |
| 35 | `motor` | get/set one motor output from CLI (`motor 0 1100`) | ✗ | B |
| 36 | `msc` | reboot as USB mass storage (download logs) | ~ bf-cli, bf-cli-automation | B |
| 37 | `play_sound` | play beeper sequence by index | ~ bf-cli | C |
| 38 | `profile` | select PID profile 0–3 | ~ bf-cli, bf-pid | A |
| 39 | `rateprofile` | select rate profile 0–3 | ~ bf-cli | A |
| 40 | `rc_smoothing_info` | live RC smoothing: detected RX rate, active setpoint/FF/throttle cutoffs | ✗ | B |
| 41 | `resource` | pin ↔ function map: `resource`, `resource show all`, `resource MOTOR 1 B00`, `none` | ✓ bf-cli | A |
| 42 | `rxfail` | Stage-1 fallback per channel `rxfail <ch> a\|h\|s <value>` | ✓ bf-failsafe | A |
| 43 | `rxrange` | per-channel input scaling `rxrange <ch> <min> <max>` | ~ bf-ports | B |
| 44 | `save` | save and reboot; `save noreboot` | ✓ bf-cli | A |
| 45 | `sd_info` | SD card state [USE_SDCARD] | ✗ | B |
| 46 | `serial` | port functions and bauds `serial <id> <mask> <msp> <gps> <tlm> <bbox>` | ✓ bf-ports | A |
| 47 | `serialpassthrough` | bridge USB ↔ any UART (flash ELRS RX, configure a VTX/GPS); optional DTR/PINIO reset | ~ bf-cli, el-emi | B |
| 48 | `servo` | servo endpoints `servo <i> <min> <max> <mid> <rate> <forward ch>` [USE_SERVOS] | ✗ | B |
| 49 | `set` | change a variable | ✓ bf-cli | A |
| 50 | `signature` | board signature | ~ bf-cli | C |
| 51 | `simplified_tuning` | `apply` / `disable` — recompute PIDs/filters from sliders | ~ bf-pid | B |
| 52 | `smix` | servo mixer rules `smix <rule> <servo> <src> <rate> <speed> <min> <max> <box>`, `reset`, `load`, `reverse` [USE_SERVOS] | ✗ for Betaflight (INAV only) | C |
| 53 | `status` | MCU, sensors, CPU load, gyro rate, arming disable flags, OSD device, BUILD KEY | ✓ bf-intro, bf-cli | A |
| 54 | `tasks` | per-task rate, load, max time | ✓ bf-intro | B |
| 55 | `timer` | timer/alternate-function per pin: `timer show`, `timer <pin> list`, `timer <pin> AF<n>` | ✓ bf-cli (example) | B |
| 56 | `version` | firmware, target, date, git rev, MSP API, board | ✓ bf-cli | A |
| 57 | `vtx` | **VTX band/channel/power on a switch**: `vtx <i> <aux> <band> <ch> <power> <start> <end>` (10 slots) | ✗ | B |
| 58 | `vtx_info` | what the VTX reports (power levels, capabilities) [USE_VTX_TABLE] | ~ link-vtx | B |
| 59 | `vtxtable` | VTX table `bands/channels/band/powerlevels/powervalues/powerlabels` | ✓ link-vtx | A |

**Totals: 59 commands; ✓ 19, ~ 23, ✗ 17.** By priority: **A 23** (✓ 14; ~ 9: `adjrange`, `bl`, `dshot_telemetry_info`,
`feature`, `help`, `map`, `mixer`, `profile`, `rateprofile` — `profile`/`rateprofile` are named, but how they interact with
`diff`/`dump` is not), **B 24** (✓ 5, ~ 7, ✗ 12), **C 12**.

Not explained anywhere, and worth one table in `bf-cli`: the `diff`/`dump` scopes (`master` = everything except the
profiles, `profile` = **only the current PID profile**, `rates` = only the current rate profile, `hardware` =
`resource`/`timer`/`dma`, `all` = everything including all profiles) and flags (`defaults` prints the default as a comment
next to each changed line, `bare` omits the `batch`/`defaults nosave`/`save` wrapper). A student who backs up with `diff`
instead of `diff all` loses profiles 1–3 — this is a common trap.

---

## 3. `set` variables (4.5): 683 entries

Source: `valueTable[]` in `src/main/cli/settings.c`. 683 is the number of distinct names in the table; a given board
shows fewer because about a third sit behind `#ifdef USE_*` (SPI receivers, extra gyros, I2C/MCO hardware, etc.).
Coverage was measured automatically: a name counts as covered if it appears as a whole token in a course file.

**Totals: 683 variables; 140 named in Betaflight-track modules; 168 named anywhere in the course.** "Named" is the upper
bound on "explained". In the Betaflight track a name nearly always comes with a meaning; elsewhere it is often only listed.
The number with a meaning **and** a default was not measured automatically.

Grouping follows the PGs in `settings.c`, merged into the Configurator's tab logic.

| Group | Vars | Named in BF track | Named anywhere |
|---|---|---|---|
| 1 Gyro, filters, sensors, alignment | 88 | 33 | 40 |
| 2 PID & profile | 51 | 32 | 34 |
| 3 Rates | 19 | 2 | 2 |
| 4 RC input, smoothing, feedforward | 23 | 7 | 11 |
| 5 Motors, mixer, DShot, 3D, servos | 54 | 12 | 14 |
| 6 Battery & power | 31 | 10 | 11 |
| 7 Failsafe | 8 | 8 | 8 |
| 8 GPS, GPS Rescue, position | 49 | 15 | 16 |
| 9 OSD (incl. element positions, stats, displayport) | 144 | 13 | 16 |
| 10 VTX | 9 | 0 | 3 |
| 11 Blackbox, storage, debug | 27 | 6 | 6 |
| 12 LED strip | 13 | 0 | 0 |
| 13 Beeper | 4 | 0 | 0 |
| 14 Serial, RX, telemetry | 78 | 2 | 4 |
| 15 Arming, modes and flight-mode tuning (angle/horizon/acro trainer/launch/crash/yaw spin/runaway) | 49 | 0 | 2 |
| 16 Misc / hardware (camera control, RunCam, PINIO, I2C, scheduler, CPU) | 36 | 0 | 1 |

Below, for each group, every **uncovered A/B** variable appears with its meaning and its 4.5 default (source file in
brackets). Trivial or hardware-only variables (`gyro_1_spibus`, `mco_*`, `sdio_*`, `frsky_spi_*`, `telemetry_disabled_*` one by one,
each `osd_*_pos`) are summarised, not listed.

### 3.1 Gyro, filters, sensors (88 / named 40)
Well covered: the full filter chain, RPM filter, dyn notch, simplified filter sliders (`bf-filters`, `bf-rpm-filter`).
Uncovered A/B:
- `align_board_roll`/`align_board_pitch` (0/0, −180…360) — board tilt. Only `align_board_yaw` is taught; tilted FC stacks and
  camera-angle-mounted FCs need roll/pitch. **B** [`sensors/boardalignment.c`]
- `gyro_calib_duration` = 125 (×10 ms = 1.25 s) and `gyro_calib_noise_limit` = 48 — why the quad "won't arm until still"
  (`CALIB` flag), boats/wind. **B** [`sensors/gyro.c` reset fn]
- `acc_trim_roll`/`acc_trim_pitch` = 0 — angle-mode trim (also via stick trims). **B**
- `acc_lpf_hz` = 25. **C**
- `gyro_overflow_detect` = `ALL_AXES` and the related `yaw_spin_recovery` = `AUTO` / `yaw_spin_threshold` = 1950 (listed in group 15).
- `mag_declination` = 0, `align_mag` = `DEFAULT`, `mag_align_*` — needed with GPS Rescue + compass (`gps_rescue_use_mag`). **B**
- `imu_dcm_kp` = 2500 (named nowhere), `small_angle` = **25°** (max tilt allowed to arm; `ANGLE` arming flag). **A** for
  `small_angle` [`flight/imu.c`; 180 only with USE_RACE_PRO]
- `dterm_lpf1_dyn_expo` = 5, `gyro_lpf1_dyn_expo` = 5 (named only once), `yaw_lowpass_hz` = 100. **C**
- `gyro_hardware_lpf` = `NORMAL` (named, OK).

### 3.2 PID & profile (51 / named 34)
Well covered: P/I/D/FF, D-min/D-max, I-relax, anti-gravity, TPA, thrust linearisation, `simplified_*`.
Uncovered A/B:
- `f_roll`/`f_pitch`/`f_yaw` = 120/125/120 — the FF gains themselves are never named (FF is explained only through
  `feedforward_*`). **A**
- `p_* / i_* / d_*` defaults are not given: roll 45/80/40, pitch 47/84/46, yaw 45/80/0, `d_min` 30/34/0
  [`flight/pid.h` `PID_*_DEFAULT`, `D_MIN_DEFAULT`]. **A**
- `tpa_low_rate` = 20, `tpa_low_breakpoint` = 1050, `tpa_low_always` = OFF — new in 4.5, low-throttle TPA. **B**
- `auto_profile_cell_count` = 0 (stay) — auto-select PID profile by cell count. **B**
- `pid_at_min_throttle` = ON, `profile_name`. **C**
- `use_integrated_yaw`, `integrated_yaw_relax`, `acc_limit*`, `simplified_pids_mode` = `RPY`, `simplified_pitch_*`. **C**
- `pidsum_limit` = 500, `pidsum_limit_yaw` = 400 — named once, not explained. **B**

### 3.3 Rates (19 / named 2) — **largest relative gap among A-topics**
Only `rates_type` and `roll_rc_rate` appear, in a table in `bf-intro`. Nothing explains the rate curve.
- `rates_type` = `ACTUAL` (BETAFLIGHT, RACEFLIGHT, KISS, ACTUAL, QUICK). **A**
- `roll_rc_rate`/`pitch_rc_rate`/`yaw_rc_rate` = 7 (Actual: centre sensitivity 70 °/s), `roll_srate`/`pitch_srate`/`yaw_srate` = 67
  (Actual: max rate 670 °/s), `roll_expo`/`pitch_expo`/`yaw_expo` = 0 [`fc/controlrate_profile.c`]. **A**
- `thr_mid` = 50, `thr_expo` = 0 — throttle curve. **B**
- `throttle_limit_type` = OFF (SCALE/CLIP), `throttle_limit_percent` = 100 — learning and indoor flying. **B**
- `roll_rate_limit`… = 1998 °/s, `quickrates_rc_expo`, `rateprofile_name`. **C**

### 3.4 RC input, smoothing, feedforward (23 / named 11)
- `rc_smoothing` = ON, `rc_smoothing_auto_factor` = 30 (named), `rc_smoothing_auto_factor_throttle` = 30,
  `rc_smoothing_setpoint_cutoff` / `_throttle_cutoff` / `_feedforward_cutoff` = 0 (auto). Plus the CLI `rc_smoothing_info`.
  Nothing explains why ELRS 500 Hz vs 50 Hz changes feel. **A**
- `deadband` = 0, `yaw_deadband` = 0 — jittery gimbals and TX centring. **B**
- `airmode_start_throttle_percent` = 25 — air mode activates only after this throttle. **B**
- `feedforward_transition` = 0. **C**; `fpv_mix_degrees` = 0 (camera-angle yaw/roll mix). **C**
- `mid_rc` = 1500, `min_check` = 1050, `max_check` = 1900, `rx_min_usec` = 885, `rx_max_usec` = 2115 — named, but the
  difference between `min_check` (arming/stick commands), `rx_min_usec` (signal-valid window) and `min_command`/`min_throttle`
  (outputs) is never stated. The official FAQ's first technical question is exactly this. **A**

### 3.5 Motors, mixer, DShot, 3D, servos (54 / named 14)
- `dshot_idle_value` = 550 (5.5 %) — named. `motor_poles` = 14, `dshot_bidir` = OFF — named.
- `motor_pwm_protocol` = DSHOT600 generic default [`pg/motor.c`], **target-dependent**; and on F4/G4 with bidir DShot the
  firmware rewrites DSHOT600 → **DSHOT300** and forces `pid_process_denom ≥ 2` when gyro > 4 kHz [`config/config.c`,
  USE_PID_DENOM_CHECK] — the reason behind the "silent corrections" in `bf-cli-automation`, which the course observed but
  never explained. **A**
- `dyn_idle_min_rpm` = 0 (off; ×100 rpm), `dyn_idle_p_gain`/`i`/`d` = 50, `dyn_idle_max_increase` = 150,
  `dyn_idle_start_increase` = 50 — dynamic idle, standard in presets. **A**
- `crashflip_motor_percent` = 0, `crashflip_expo` = 35 — turtle mode tuning (2025.12: `crashflip_rate`). **B**
- `dshot_bitbang` = AUTO (named), `dshot_burst` = OFF — DMA conflicts. **B**
- `motor_output_limit` = 100 — run 6S motors on a 4S-tuned quad / limit power. **B**
- `throttle_boost` = 5, `throttle_boost_cutoff` = 15 — named in prose only. **B**
- `3d_deadband_low` = 1406, `3d_deadband_high` = 1514, `3d_neutral` = 1460, `3d_deadband_throttle` = 50,
  `3d_switched_mode` = OFF + `feature 3D`. **C**
- `servo_center_pulse` = 1500, `servo_pwm_rate` = **50 Hz** (50–498), `servo_lowpass_hz` = 0, `channel_forwarding_start` = AUX1,
  `tri_unarmed_servo` = ON, `gimbal_mode` = NORMAL — see §7. **B**
- `motor_kv` = 1960, `rpm_limit*` (OFF, 18000 rpm) — motor RPM limiter for spec classes. **C**
- `thr_corr_value` = 0 / `thr_corr_angle` = 800 — tilt throttle correction. **C**

### 3.6 Battery & power (31 / named 11)
Covered in depth: `vbat_scale` = 110, `ibata_scale` = 400, `ibata_offset` = 0, `vbat_divider`, `vbat_multiplier`,
`bat_capacity`, `vbat_min/warning_cell_voltage` 330/350, `vbat_max_cell_voltage` 430 (`bf-setup-scratch`, `bf-modes-osd`).
Uncovered B:
- `force_battery_cell_count` = 0 — needed for HV/Li-Ion packs where auto-detect guesses the wrong S. **B**
- `vbat_detect_cell_voltage` = 300, `vbat_full_cell_voltage` = 410 — basis of cell-count detection and "battery not full"
  warning. **B**
- `use_cbat_alerts` = OFF, `cbat_alert_percent` = 10 — capacity-based warning (Li-Ion). **B**
- `vbat_cutoff_percent` = 100 — limits throttle when the battery is critical. **B**
- `vbat_duration_for_warning` / `_for_critical` = 0, `vbat_hysteresis` = 1, `*_lpf_period`. **C**
- `ibatv_scale`/`ibatv_offset` (virtual current meter — no sensor). **C**

### 3.7 Failsafe (8 / 8 named)
Complete. Only fix: see the 4.4 default error in §6.3.

### 3.8 GPS, GPS Rescue, position (49 / named 16)
Covered: the key Rescue variables (`gps_rescue_min_sats` = 8, `min_start_dist` = 15, `alt_mode` = MAX_ALT,
`initial_climb` = 10, `return_alt` = 30, `ground_speed` = 750, `throttle_hover` = 1275, `sanity_checks` = FS_ONLY,
`descend_rate` = 150, `descent_dist` = 20, `disarm_threshold` = 20, `allow_arming_without_fix` = OFF).
Uncovered A/B:
- `gps_ublox_use_galileo` = OFF, `gps_sbas_mode` = NONE, `gps_update_rate_hz` = 10, `gps_auto_config` = ON (named),
  `gps_auto_baud` = OFF, `gps_ublox_flight_model` = AIRBORNE_4G, `gps_set_home_point_once` = OFF — "GPS takes forever to fix",
  M10 setup. **B**
- `gps_rescue_max_angle` = 45, `gps_rescue_landing_alt` = 4, `gps_rescue_throttle_min` / `_max` = 1100/1700,
  `gps_rescue_use_mag` = ON (when USE_MAG), `gps_rescue_velocity_*`, `gps_rescue_throttle_p/i/d` — needed to tune a Rescue
  that undershoots. **B**
- `altitude_source` = DEFAULT, `altitude_prefer_baro` = 100 — baro vs GPS altitude for Rescue. **B**
- `gps_lap_timer_*` (4.5 new). **C**

### 3.9 OSD (144 / named 16)
Covered: `osd_displayport_device`, `vcd_video_system`, `osd_canvas_width`, `osd_warn_bitmask`, `osd_profile`, alarms
`osd_cap_alarm`, `osd_alt_alarm`, `osd_rssi_alarm`, `osd_link_quality_alarm`, `osd_tim1/2`, `osd_avg_cell_voltage_pos`,
`osd_framerate_hz`, `craft_name`.
Uncovered A/B:
- `osd_stat_bitmask` (post-flight stats page; the CLI only shows a bitmask — the OSD tab sets it), `stats_min_armed_time_s` = −1,
  `stats_total_flights`/`_time_s`/`_dist_m`/`_mah_used` (lifetime counters, flight log). **B**
- `osd_rssi_dbm_alarm` = −60, `osd_rsnr_alarm` = 4, `osd_core_temp_alarm` = 70, `osd_esc_temp_alarm` = 0,
  `osd_distance_alarm` = 0. **B**
- `displayport_msp_fonts`, `displayport_msp_col_adjust`/`row_adjust`, `osd_canvas_height`, `vcd_h_offset`/`vcd_v_offset` — HD
  font sets and analogue centring (§7d). **B**
- `osd_units` = METRIC, `osd_ah_max_pit`/`_rol` 20/40, `osd_logo_on_arming` = OFF, `osd_craftname_msgs` = OFF, `pilot_name`. **C**
- 80 `osd_*_pos` element variables — taught as one rule: position encoding `pos = x | (y << 5) | flags` (the OSD tab writes
  them), and only a few named elements matter (`osd_warnings_pos`, `osd_link_quality_pos`, `osd_mah_drawn_pos`,
  `osd_home_dir_pos`, `osd_home_dist_pos`, `osd_gps_sats_pos`, `osd_flymode_pos`). The encoding was not re-verified here (marked
  unverified).

### 3.10 VTX (9 / named 3)
`vtx_band`, `vtx_channel` are used in `link-vtx`; uncovered:
- `vtx_power` = 0 (index into the VTX table), `vtx_freq` = 0, `vtx_pit_mode_freq`. **A** (`vtx_power` is how power is set)
- `vtx_low_power_disarm` = OFF (OFF/ON/UNTIL_FIRST_ARM) — low power on the bench, standard at races. **B**
- `vtx_halfduplex` = ON, `vtx_softserial_alt` = OFF — SmartAudio on softserial/odd VTX. **C**

### 3.11 Blackbox, storage, debug (27 / named 6)
Covered: `blackbox_device`, `blackbox_sample_rate` (= 1/4, so 2 kHz at 8 kHz PID), `blackbox_mode`,
`blackbox_high_resolution`, `debug_mode`, `blackbox_disable_*` as a family. Missing: a list of the 13 `blackbox_disable_*`
fields with what each costs in bandwidth (B), `sdcard_mode` (C).

### 3.12 LED strip (13 / 0) — nothing
`ledstrip_profile` = STATUS (RACE/BEACON/STATUS), `ledstrip_race_color` = ORANGE, `ledstrip_beacon_color` = WHITE,
`ledstrip_beacon_period_ms` = 500, `ledstrip_beacon_percent` = 50, `ledstrip_beacon_armed_only` = OFF,
`ledstrip_brightness` = 100, `ledstrip_visual_beeper` = OFF, `ledstrip_grb_rgb`, `ledstrip_rainbow_*`. All **B**, see §7b.

### 3.13 Beeper (4 / 0)
`beeper_dshot_beacon_tone` = 1 (1–5) **B**, `beeper_inversion` = ON, `beeper_od` = OFF, `beeper_frequency` = 0 (passive
buzzers) **C**. With the commands `beeper`/`beacon` (✗) the whole buzzer topic is missing.

### 3.14 Serial, RX, telemetry (78 / named 4)
Covered: `serialrx_provider`. Uncovered A/B:
- `serialrx_inverted` = OFF, `serialrx_halfduplex` = OFF — F4 SBUS / FPort wiring. **A**
- `crsf_use_negotiated_baud` = OFF (CRSF baud negotiation; CRSF default 420000 bd [`rx/crsf_protocol.h`]). **B**
- `rssi_channel` = 0 (named), `rssi_src_frame_errors` = OFF, `rssi_scale`/`rssi_offset`/`rssi_invert`, `rssi_smoothing` — RSSI from
  SBUS/AUX. **B**
- `msp_override_channels_mask`, `msp_override_failsafe` + mode MSP OVERRIDE — companion control (4.5). **C**
- `tlm_inverted`, `tlm_halfduplex` = ON (SmartPort), `report_cell_voltage` = OFF, `telemetry_disabled_*` (bitfield per sensor,
  one line suffices). **B**
- `expresslrs_*`, `frsky_spi_*`, `spektrum_spi_*`, `flysky_spi_*` — SPI-receiver boards (the ELRS SPI ones are **B** for AIO
  whoops: `expresslrs_uid` = binding phrase hash, `expresslrs_domain`).
- `serial_update_rate_hz` = 100, `reboot_character` = 'R'. **C**

### 3.15 Arming, modes and flight-mode tuning (49 / named 2) — **second-largest gap**
- `small_angle` = 25 (in 3.1), `auto_disarm_delay` = 5 s (with MOTOR_STOP), `pwr_on_arm_grace` = 5 s (`BOOTGRACE`),
  `enable_stick_arming` = OFF, `gyro_cal_on_first_arm` = OFF. **A**
- `runaway_takeoff_prevention` = ON (named in a quiz only), `runaway_takeoff_deactivate_delay` = 500 ms,
  `runaway_takeoff_deactivate_throttle_percent` = 20 — the `RUNAWAY` flag and "quad disarms on takeoff". **A**
- `angle_limit` = 60°, `angle_p_gain` (= `p_level`, 50), `angle_feedforward`, `angle_earth_ref` = 100 (4.5 Earth-referenced
  angle — named in `bf-intro` as a feature, not the parameter), `horizon_level_strength`, `horizon_limit_degrees` = 135,
  `horizon_limit_sticks` = 30, `horizon_delay_ms` = 500. **A** for `angle_limit`, B for the rest
- `yaw_spin_recovery` = AUTO, `yaw_spin_threshold` = 1950 (in the gyro PG). **B**
- `crash_recovery` = OFF and `crash_*` (thresholds 50/400/350, time 500 ms, angle 10°, rate 100). **C**
- `acro_trainer_angle_limit` = 20, `acro_trainer_lookahead_ms` = 50, `acro_trainer_gain` = 75. **B**
- `launch_control_mode` = NORMAL, `launch_trigger_throttle_percent` = 20, `launch_angle_limit` = 0, `launch_control_gain` = 40,
  `launch_trigger_allow_reset` = ON. **C** (racing)
- `level_race_mode` = OFF (4.5 "NFE race mode"), `ez_landing_threshold` = 25 / `_limit` = 15 / `_speed` = 50. **C**
- `abs_control_*` (off), `box_user_1..4_name` (USER1–4 mode labels for PINIO). **C**

### 3.16 Misc / hardware (36 / named 1)
- `camera_control_mode` = HARDWARE_PWM, `camera_control_ref_voltage` = 330, `_key_delay` = 180,
  `_internal_resistance` = 470 — RunCam joystick emulation via a resistor. **C**
- `rcdevice_*` (RunCam Device Protocol on a UART, function bit 16384). **C**
- `pinio_config`, `pinio_box` — switch a VTX/camera power rail or a Bluetooth module from an AUX mode (USER1–4). **B**
- `cpu_overclock` = 1, `task_statistics` = ON, `rate_6pos_switch` = OFF (Adjustments), `timezone_offset_minutes` = 0. **C**

### 3.17 Most valuable uncovered variables (top 25)
`roll/pitch/yaw_rc_rate`, `*_srate`, `*_expo`, `rates_type` math; `f_roll/f_pitch/f_yaw`; PID defaults; `small_angle`;
`runaway_takeoff_*`; `angle_limit`, `angle_earth_ref`; `dyn_idle_min_rpm` and gains; `rc_smoothing_*` + `rc_smoothing_info`;
`min_check` vs `rx_min_usec` vs `min_command`/`min_throttle`; `serialrx_inverted`/`serialrx_halfduplex`; `vtx_power`,
`vtx_low_power_disarm`; `force_battery_cell_count`; `crashflip_motor_percent`; `motor_output_limit`; `throttle_limit_*`;
`ledstrip_profile` family; `beeper_dshot_beacon_tone`; `osd_stat_bitmask` + stats; `gps_ublox_use_galileo`/`gps_sbas_mode`;
`gps_rescue_max_angle`/`_landing_alt`; `align_board_roll/pitch`; `pinio_box`.

---

## 4. Adjustments tab (in-flight adjustments)

### 4.1 What the course says now
Three sentences in three modules, and two of them are wrong (§6.3):
- `bf-modes-osd` (theory, "Команда `aux`"): "`adjrange` — то же для «подстроек в полёте» (PID, рейты, профили) тумблером или крутилкой."
- `bf-intro` (theory, "Карта настройки"): PID and rate profiles "переключаемые тумблером/adjustments".
- `bf-pid` (practice, Шаг 2): "Переключение — тумблером (режим или `adjustment`)" for PID profiles 1–4.

There is no syntax, no function list, no lab. The betaflight.com Adjustments **tab** page is itself empty ("Sorry; this Wiki
page has not yet been written"), so the course would be one of the few complete sources.

### 4.2 How it works (4.5 source, `fc/rc_adjustments.c`)
- **Up to 30 ranges** (`MAX_ADJUSTMENT_RANGE_COUNT 30`). The current guide says "12 adjustment ranges can be defined" in one
  place and "Index 0–29" in the table: 30 is correct for 4.5 and 2025.12.
- Each range has two channels. The **range channel** (`auxChannelIndex`, AUX1 = 0) enables the slot when it is inside
  `start..end` (900–2100, step 25, same as `aux`). The **adjustment channel** (`auxSwitchChannelIndex`, AUX1 = 0) carries the
  value. They may be the same channel.
- **Step mode** (`center = 0`, function not a "select" function): adjustment channel above `mid_rc + 200` (1700) → +step,
  below `mid_rc − 200` (1300) → −step. `step = 1` for every function. While held, it repeats **every 500 ms**
  (`RESET_FREQUENCY_2HZ`); back to centre resets it, so tapping is faster than holding. Beeps: 2 short = up, 1 long = down
  (`beeperConfirmationBeeps(delta > 0 ? 2 : 1)`).
- **Absolute mode** (`center ≠ 0`, step-type function): value = `center + (rc − 1500) × scale / 500`, applied whenever the
  channel moves. Stick at 1000 gives `center − scale`, at 2000 `center + scale`. Values are clamped (P/I/D 0–200 here, rates per
  `CONTROL_RATE_CONFIG_*_MAX`).
- **Select mode** (functions RATE_PROFILE, HORIZON_STRENGTH, PID_AUDIO, OSD_PROFILE, LED_PROFILE): the 900–2100 span is split into
  N equal positions (rate profile 3, or **6** with `rate_6pos_switch = ON`; OSD profile 3; LED profile 3; PID audio 7; horizon
  strength 255) and the position selects the value. Rate-profile change beeps position+1 times.
- Adjustments are processed only outside the CLI and not while PARALYZE is active and disarmed (`fc/core.c`). They run armed
  **and** disarmed.
- **Nothing is saved automatically.** The change marks the config dirty. To keep it: disarm, then stick command
  **throttle low + yaw left + pitch low + roll right** (`rc_controls.c` → `saveConfigAndNotify()`), or save from the
  Configurator/CMS. Power-off without saving discards it (`Inflight-Adjustments.md`: "Settings are not saved automatically").
- Every change is written to Blackbox as an `INFLIGHT_ADJUSTMENT` event (function + new value), and the OSD element
  `osd_adjustment_range_pos` shows "NAME value" for 2 s (`VALUE_DISPLAY_LATENCY_MS`). Without that element the pilot is blind.

### 4.3 Function list (the CLI number is the slot in `defaultAdjustmentConfigs[]`, not the enum value)
In 4.5 the enum `adjustmentFunction_e` has ROLL/PITCH RC RATE/EXPO at 25–28, but those four are **not** in
`defaultAdjustmentConfigs[]`, and the CLI number indexes that table (`adjustmentConfig − 1`). So the numbers a user types are:

| # | Function | Mode | # | Function | Mode |
|---|---|---|---|---|---|
| 0 | none | — | 16 | PITCH_I | step/abs |
| 1 | RC_RATE (roll+pitch) | step/abs | 17 | PITCH_D | step/abs |
| 2 | RC_EXPO (roll+pitch) | step/abs | 18 | ROLL_P | step/abs |
| 3 | THROTTLE_EXPO | step/abs | 19 | ROLL_I | step/abs |
| 4 | PITCH_ROLL_RATE (super rate) | step/abs | 20 | ROLL_D | step/abs |
| 5 | YAW_RATE | step/abs | 21 | RC_RATE_YAW | step/abs |
| 6 | PITCH_ROLL_P | step/abs | 22 | PITCH_ROLL_F | step/abs |
| 7 | PITCH_ROLL_I | step/abs | 23 | FEEDFORWARD_TRANSITION | step/abs |
| 8 | PITCH_ROLL_D | step/abs | 24 | HORIZON_STRENGTH | select |
| 9 | YAW_P | step/abs | 25 | PID_AUDIO | select |
| 10 | YAW_I | step/abs | 26 | PITCH_F | step/abs |
| 11 | YAW_D | step/abs | 27 | ROLL_F | step/abs |
| 12 | RATE_PROFILE | select (3/6) | 28 | YAW_F | step/abs |
| 13 | PITCH_RATE | step/abs | 29 | OSD_PROFILE | select (3) |
| 14 | ROLL_RATE | step/abs | 30 | LED_PROFILE | select (3: RACE/BEACON/STATUS) |
| 15 | PITCH_P | step/abs | 31 | LED_DIMMER — **2025.12 only** | |

`master` adds `SIMPLIFIED_MASTER_MULTIPLIER` (documented online as 31 — not in 2025.12). Numbers 31–34 are accepted by the
4.5 CLI (`val < ADJUSTMENT_FUNCTION_COUNT`) but do nothing — a silent trap.

**What Adjustments cannot do in 4.5:** switch PID profiles, change D-min/D-max, filters, `simplified_*` sliders or
anti-gravity, or set VTX band/channel/power. VTX on a switch is the separate CLI command **`vtx`** (Configurator: Video
Transmitter tab); PID profile is switched by stick command (throttle low + yaw left + roll left / pitch up / roll right →
profiles 1/2/3), OSD/CMS, CLI `profile`, or `auto_profile_cell_count`.

### 4.4 `adjrange` syntax and worked examples
`adjrange <index> <unused=0> <range channel> <start> <end> <function> <adjustment channel> [<center> <scale>]`

**Example A — field PID tuning on one momentary 3-position switch, selected by a 6-position switch.** AUX2 (=1) is a 6-pos
selector, AUX4 (=3) a self-centring switch:
```
adjrange 0 0 1  900 1150  6 3 0 0   # pos 1: pitch+roll P
adjrange 1 0 1 1150 1300  8 3 0 0   # pos 2: pitch+roll D
adjrange 2 0 1 1300 1500 22 3 0 0   # pos 3: pitch+roll F
adjrange 3 0 1 1500 1700  4 3 0 0   # pos 4: roll+pitch rate
adjrange 4 0 1 1700 2100  0 3 0 0   # pos 5-6: nothing (safe position)
set osd_adjustment_range_pos = <from OSD tab>
save
```
Fly in pos 5–6. To raise D: selector to pos 2, tap AUX4 up twice → OSD "PITCH/ROLL D 42" then "43", two short beeps each.
Land, disarm, stick-save. `diff all` shows the new `d_roll`/`d_pitch`. Danger: the change is live immediately and applies to
**both** axes for combined functions.

**Example B — absolute pot for roll rate.** Pot on AUX5 (=4), enabled only while AUX3 (=2) is high:
```
adjrange 5 0 2 1700 2100 14 4 67 20
```
Pot centre → `roll_srate` 67, ends → 47…87. If the pot is not centred when AUX3 goes high, the value **jumps** — centre first.

**Example C — profiles on switches (no tuning risk).**
```
adjrange 6 0 5 900 2100 12 5 0 0    # AUX6 3-pos: rate profile 1/2/3
adjrange 7 0 6 900 2100 29 6 0 0    # AUX7 3-pos: OSD profile 1/2/3
adjrange 8 0 7 900 2100 30 7 0 0    # AUX8 3-pos: LED RACE/BEACON/STATUS
vtx 0 3 1 1 1 900 1300              # AUX4 low: band A ch1 power index 1 (25 mW)
vtx 1 3 1 1 3 1700 2100             # AUX4 high: band A ch1 power index 3
```
(`vtx` arguments: `<index> <aux> <band> <channel> <power index> <start> <end>`; 0 for band/channel/power = "don't change";
10 slots, `MAX_CHANNEL_ACTIVATION_CONDITION_COUNT`.)

### 4.5 What a full lesson needs
Theory: the three modes, the two-channel model, timing (500 ms repeat, ±200 µs thresholds from `mid_rc`), clamping, no auto-save
plus the save stick command, OSD element and Blackbox event, the function table with the "CLI number ≠ enum" note, what it
cannot do, `vtx` on a switch, `rate_6pos_switch`. Dangers: live changes in the air; combined functions change two axes;
absolute pot jumps; switch not centred at power-up keeps stepping; CMS stick commands and adjustments on the same sticks; the
Configurator Adjustments tab shows the same 30 slots (no extra features). Typical uses: field tuning of P/D/FF when there is no
laptop; rate profiles for different pilots; OSD profile race/LR/clean; LED race colour; VTX power low on the bench, high in
the air. Lab: §6.1, module `bf-adjustments`.

---

## 5. Popular questions (52)

Evidence: O = official FAQ/guide entry, L = Oscar Liang guide, F = several IntoFPV threads in search results,
G = GitHub issue/discussion found. Sources: [Oscar Liang — won't arm](https://oscarliang.com/quad-arming-issue-fix),
[Oscar Liang — jello, vibrations, hot motors](https://oscarliang.com/mini-quad-motors-overheat), IntoFPV threads
([arming without flags](https://intofpv.com/t-quad-not-armed-with-no-arming-status-flag?page=1),
[CLI/MSP arming flag](https://intofpv.com/t-quad-won-t-arm-and-only-arming-error-i-get-is-cli-msp),
[propwash help](https://intofpv.com/t-help-a-newbie-with-propwash-oscillations?pid=25766),
[blackbox oscillations](https://intofpv.com/t-blackbox-analysis-for-oscillations),
[no OSD in goggles](https://intofpv.com/t-need-help-no-osd-in-goggles),
[DJI air unit no OSD](https://intofpv.com/t-dji-goggles-and-air-unit-01-no-osd),
[SmartAudio not working](https://intofpv.com/t-mamba-f405-mk2-eachine-tx805s-smartaudio-not-working),
[VTX in OSD not working](https://intofpv.com/t-vtx-in-osd-not-working)),
[GitHub discussion #12167: 4.4 displayport and DJI O3 OSD](https://www.github.com/betaflight/betaflight/discussions/12167),
the betaflight.com FAQ (local copy). Reddit and GitHub reaction counts: not reachable.

| # | Question | How common | Short correct answer (4.5) | Course now |
|---|---|---|---|---|
| 1 | Why won't it arm? | O L F F | Read the flags: `status` → "Arming disable flags", OSD warnings, or the buzzer code. 26 flags in 4.5 (`fc/runtime_config.c`). The commonest: `RXLOSS`, `THROTTLE` (throttle above `min_check` 1050), `ANGLE` (tilt > `small_angle` 25°), `CALIB` (gyro calibrating, `gyro_calib_noise_limit`), `CLI`/`MSP` (Configurator connected), `ARMSWITCH` (arm switch high at boot or after failsafe), `NOPREARM`, `LOAD`, `BOOTGRACE` (`pwr_on_arm_grace` 5 s), `MOTOR_PROTO`, `DSHOT_TELEM`, `RPMFILTER`, `REBOOT_REQD` | ✓ bf-setup-scratch (SITL), ~ bf-intro, bf-modes-osd — no table of all 26 with fixes |
| 2 | Arms on the bench but not with the goggles/after unplugging USB | L F | `MSP`/`CLI` flag while the Configurator is open; `ANGLE` on uneven ground; `LOAD` with a laptop in CLI | ~ |
| 3 | Motors spin in the wrong order / wrong direction, quad flips on take-off | O F | Motor 1 rear-right, 2 front-right, 3 rear-left, 4 front-left (QUADX). Order: Motors tab Reorder → `motor_output_reordering`; direction: Motor direction dialog / `dshotprog <i> 7\|8 12`; props-out → `yaw_motors_reversed = ON` | ✓ bf-setup-scratch, bf-intro |
| 4 | Receiver not detected / sliders don't move | O F | UART with Serial RX, right `serialrx_provider`, protocol included in the Cloud Build, TX↔RX crossed for CRSF, SBUS on F4 needs an inverted pad or `serialrx_inverted` | ✓ bf-ports |
| 5 | How do I bind ELRS? | F | Same binding phrase and major version on TX and RX; or `bind_rx` from the CLI (CRSF), or 3× power-cycle; check with the receiver LED; LQ in Receiver tab | ✓ link-elrs; `bind_rx` ✗ |
| 6 | Failsafe: what happens and how do I test it? | O F | Stage 1 (`failsafe_delay` 1.5 s, `rxfail` values), Stage 2 (`failsafe_procedure` DROP/AUTO-LAND/GPS-RESCUE), switch test `failsafe_switch_mode` STAGE1 | ✓ bf-failsafe |
| 7 | Jello in the video | L F | Mechanical: prop/motor balance, FC/camera soft-mount, bent shaft; filters do not fix jello (it's < 100 Hz wobble on the camera) | ~ bf-filters ("Чего фильтры не лечат") |
| 8 | Propwash oscillation on descents | L F F | D (D-max), `simplified_d_gain`/`dmax`, `iterm_relax`, better props, higher idle (`dyn_idle_min_rpm`), not only filters | ✓ bf-pid, bf-pid-reg-in-bf, bf-filters |
| 9 | Hot motors | L F | D noise: RPM filter working (bidir DShot, `motor_poles`), D lower, D-LPF; check mechanics | ✓ bf-filters, bf-rpm-filter |
| 10 | High-throttle or mid-throttle oscillation | O F | Frame resonance (dyn notch, static notch), too much P/D at high throttle → TPA (`tpa_rate` 65, `tpa_breakpoint` 1350, `tpa_mode` D) | ✓ bf-filters, bf-pid-reg-in-bf |
| 11 | No OSD in DJI/Walksnail/HDZero goggles | F F G | UART: MSP + VTX (MSP+DisplayPort) [`serial` mask 1+131072], `osd_displayport_device = MSP`, `vcd_video_system = HD`, OSD feature on, custom OSD enabled in the goggles, MSP baud 115200 | ~ link-digital-video, bf-modes-osd (no wiring, no goggle settings) |
| 12 | No analogue OSD / OSD jitter | F | `osd_displayport_device = MAX7456` or AUTO, `vcd_video_system` PAL/NTSC matching the camera, `vcd_h_offset`/`v_offset` | ~ |
| 13 | SmartAudio/Tramp doesn't change channel | F F | TX pad, Peripherals = VTX (SmartAudio/IRC Tramp), VTX table loaded, `vtx_info` shows the device; some VTX need a pull-up or `vtx_softserial_alt`/halfduplex; VTX not locked | ✓ link-vtx |
| 14 | How do VTX tables work, which one to load? | O F | `vtxtable` bands/channels/powerlevels; FACTORY vs CUSTOM; use the manufacturer's table; legal channels | ✓ link-vtx |
| 15 | How do I change VTX power with a switch / pit mode? | F | `vtx` command or Video Transmitter tab "VTX channel on switch"; mode VTX PIT MODE; `vtx_low_power_disarm` | ✗ |
| 16 | How do I set up GPS Rescue? | O L F | GPS UART + `gps_provider`, ≥ `gps_rescue_min_sats`, home fix before arming, return altitude/speed, hover throttle from log, test with the switch | ✓ bf-failsafe, bf-setup-scratch |
| 17 | GPS takes long to fix / M10 setup | F | `gps_auto_config = ON`, `gps_ublox_use_galileo = ON`, `gps_sbas_mode` AUTO, 10 Hz, clear sky, distance from the VTX | ✗ |
| 18 | Turtle mode doesn't work | L F | DShot required, mode FLIP OVER AFTER CRASH, flip switch then arm, `crashflip_motor_percent`, `crashflip_expo`; 2025.12: `crashflip_rate`, `FLIP_SWITCH` flag | ~ bf-modes-osd (mode named) |
| 19 | Buzzer / lost-model beeper / DShot beacon | O F | Mode BEEPER; `beeper` list (`RX_LOST`, `RX_SET`, `BAT_LOW`…), `beacon RX_LOST`, `beeper_dshot_beacon_tone`; standalone buzzer for a cut battery | ~ bf-modes-osd (mode only) |
| 20 | How do I set up an LED strip? | O F | `resource LED_STRIP 1 <pin>`, `feature LED_STRIP`, LED tab or `led`, `ledstrip_profile`, 5 V supply | ✗ |
| 21 | Battery voltage wrong / calibrate current sensor | O F | `vbat_scale` new = old × V_meter / V_fc; `ibata_scale` new = old × mAh_fc / mAh_charger, `ibata_offset` | ✓ bf-setup-scratch |
| 22 | Wrong cell count detected (HV/Li-Ion, storage battery) | F | `force_battery_cell_count`, `vbat_detect_cell_voltage`, `vbat_max_cell_voltage` | ✗ |
| 23 | Rates: Actual vs Betaflight vs Quick — what do the numbers mean? | O F | Actual: centre sensitivity (`rc_rate`×10 °/s), max rate (`srate`×10 °/s), expo; Betaflight: RC rate, super rate, expo; Rate Calculator page | ✗ |
| 24 | Should I use presets? Which? | O | Presets tab = CLI snippets (community repo), apply on top of defaults, check the "options", `diff all` before/after | ✗ (named on `compare.html`) |
| 25 | What Blackbox logging rate? Flash fills too quickly | O F | 2 kHz for filters (default 1/4 of 8 kHz), 1 kHz for PIDs; `blackbox_disable_*` fields; erase flash (`flash_erase`/button); SD for long logs | ✓ bf-blackbox; `flash_erase` ✗ |
| 26 | Bidirectional DShot: how to enable, error % | O L | ESC Bluejay/BLHeli_32/AM32, `dshot_bidir = ON`, `motor_poles`, errors < 1 % on the Motors tab, `dshot_telemetry_info`; F4 auto-switches to DSHOT300 | ✓ bf-rpm-filter; F4 rewrite ✗ |
| 27 | Gyro / PID loop rate: 8k or 4k? CPU load | O F | gyro rate is fixed by chip (8 kHz most; BMI270 3.2 kHz); `pid_process_denom` 1 default (8 kHz) — 2 on F411/F4 with bidir; keep CPU load < 75 % (Oscar Liang, 4.5) | ~ bf-intro (says denom 2 is the typical start — §6.3) |
| 28 | Which ESC protocol? DShot300 vs 600 | O | DShot600 needs ≥ 8 kHz updates; DShot300 on F4 bidir or 4 kHz; PWM/OneShot only for old ESCs (calibration) | ✓ f-motors-esc, bf-setup-scratch |
| 29 | Can't flash / DFU not detected / driver | O F | Boot button or `bl`, ImpulseRC Driver Fixer / Zadig on Windows, data cable, Full chip erase | ✓ bf-intro, bf-cli |
| 30 | Unified target / which target to pick, Cloud Build options | O | Pick the board name; options decide what's compiled; `status` BUILD KEY | ✓ bf-intro, bf-custom |
| 31 | How do I move my config to a new version? | O F | Not by pasting old `diff all`: renamed variables (D-min/D-max, `motor_idle`, `failsafe_landing_time`); re-enter by section; `diff all` with `defaults` flag to compare | ✓ bf-cli, bf-cli-automation |
| 32 | How do I back up / restore with CLI diff? | O | `diff all` (not `diff`!), paste after `defaults`, `batch` wrapper, `save` | ✓ bf-cli (`diff` vs `diff all` trap ✗) |
| 33 | What is Air mode? Quad bounces on landing | O F | PID authority at zero throttle (`feature AIRMODE`/mode), `airmode_start_throttle_percent` 25, disarm on landing | ~ bf-pid-reg-in-bf, bf-modes-osd |
| 34 | Anti-gravity: what does it do? | O | Raises I (and P) on fast throttle changes: `anti_gravity_gain` 80, `anti_gravity_cutoff_hz` 5, `anti_gravity_p_gain` 100 | ✓ bf-pid-reg-in-bf |
| 35 | I-term relax / bounce-back after flips | O F | `iterm_relax = RP`, `SETPOINT`, cutoff 15 | ✓ bf-pid-reg-in-bf |
| 36 | Feedforward settings for ELRS/crossfire (jitter, smoothing) | O F | `feedforward_jitter_factor` 7, `_smooth_factor` 25, `_averaging`, `_boost` 15, `_max_rate_limit` 90, plus RC smoothing auto-factor | ~ bf-pid-reg-in-bf (names only) |
| 37 | RC smoothing — what values? | O | Auto by RX rate: `rc_smoothing_auto_factor` 30; check `rc_smoothing_info` | ✗ |
| 38 | TPA — should I change it? | O | 4.5: `tpa_mode` D, `tpa_rate` 65, `tpa_breakpoint` 1350, new `tpa_low_*` | ✓ bf-pid-reg-in-bf (one wrong number, §6.3) |
| 39 | Dynamic idle — what RPM? | O L | `dyn_idle_min_rpm` (×100 rpm), e.g. 30–40 for 5", needs bidir DShot; lowers `dshot_idle_value` need | ✗ |
| 40 | Quad disarms at take-off (runaway takeoff) | O F | `RUNAWAY` flag: wrong motor order/direction or prop on the wrong motor; `runaway_takeoff_prevention`, deactivates after 500 ms at > 20 % throttle | ✗ (only in a quiz) |
| 41 | Crash recovery / yaw spin to the moon | O | `yaw_spin_recovery = AUTO`, `yaw_spin_threshold`; `crash_recovery` (off) | ✗ |
| 42 | Launch control | O | Mode LAUNCH CONTROL, `launch_control_mode`, `launch_trigger_throttle_percent` 20, `launch_angle_limit` | ✗ |
| 43 | 3D mode (reversible) | O | ESC in 3D mode, `feature 3D`, `3d_deadband_*`, mode "3D DISABLE / SWITCH" | ✗ |
| 44 | Camera control / RunCam (change camera settings from the radio) | O | RunCam Device Protocol (UART function RCDEVICE) or `camera_control_*` PWM; modes CAMERA CONTROL 1–3; CMS camera menu | ~ bf-ports (one mention) |
| 45 | RSSI vs LQ in OSD; RSSI shows 0 | O F | CRSF provides LQ and dBm automatically: don't set `rssi_channel`; use `osd_link_quality_pos`, `osd_rssi_dbm_pos`; SBUS RSSI via AUX channel `rssi_channel` | ✓ link-protocols, bf-modes-osd |
| 46 | OSD post-flight stats | O | OSD tab Statistics (`osd_stat_bitmask`), `stats_min_armed_time_s`, lifetime `stats_total_*` | ✗ |
| 47 | CRSF/ELRS telemetry on the radio: which sensors, missing GPS | O F | same UART, `feature TELEMETRY`, discover sensors in EdgeTX; `telemetry_disabled_*`; ELRS telemetry ratio | ✓ bf-ports, link-protocols |
| 48 | Configure from the phone: Bluetooth / ESP32 / SpeedyBee app | F | MSP over a UART with a Bluetooth/ESP32 bridge (115200), or vendor app via built-in BLE; app.betaflight.com on Android Chrome with USB OTG | ✗ |
| 49 | In-flight adjustments: tune PIDs without a laptop | O | §4 | ✗ (two wrong hints) |
| 50 | min_check / min_command / min_throttle — what's the difference? | O (first FAQ item) | `min_check` input threshold for arming/sticks; `min_command` output when disarmed (PWM); `min_throttle` idle for PWM ESCs; DShot uses `dshot_idle_value` | ~ bf-setup-scratch (pieces) |
| 51 | Motors twitch/beep while connected / ESCs beep in CLI | O | No signal to ESCs while in CLI/Motors tab; beeps = ESC waiting for signal | ~ bf-cli-automation |
| 52 | Remap a motor or free a pad (LED/servo) — timer and DMA conflicts | O F | `resource`, `timer <pin> list`, `dma`, `dshot_bitbang` | ✓ bf-cli |

**Totals: 52 questions — ✓ answered 25, ~ partly 12, ✗ not answered 15** (✗: 15, 17, 20, 22, 23, 24, 37, 39, 40, 41, 42,
43, 46, 48, 49). Several ✓ rows still have a ✗ sub-part (for example `bind_rx` in 5, `flash_erase` in 25, the F4 rewrite in 26,
the `diff` vs `diff all` trap in 32).

---

## 6. Proposed changes

### 6.1 New modules (ordered by value)

Every module follows `content/article-template.md`: summary, theory, practice ≥ 150 words with a lab and an acceptance line,
diagnostics, checklist, references ≥ 2, quiz bank (8), glossary terms, diagram. SITL-first wherever Betaflight 4.5 SITL can
show it; then «Переход на реальное железо». Important SITL limits (from `bf-setup-scratch`): no DShot, serial RX, OSD, VTX,
GPS, Blackbox or `resource` in the SITL build, so OSD/VTX/LED labs are Configurator-and-bench labs.

| # | id | Title (ru) | Pri | Scope | Lab |
|---|---|---|---|---|---|
| 1 | `bf-adjustments` | «Подстройки в полёте: Adjustments, `adjrange` и VTX на тумблере» | A | everything in §4: modes, function table, CLI numbering trap, timing, clamping, save stick command, OSD element, Blackbox event, `vtx` command, `rate_6pos_switch`, dangers | **SITL:** three `adjrange` slots (step D, absolute rate, select rate profile); a Python RC sender (reuse the `bf-setup-scratch` script) moves AUX channels; read `get d_roll`/`get roll_srate`/`rateprofile` over MSP or CLI after each step and show the 500 ms repeat and the ±200 µs thresholds; confirm nothing is saved after a SITL restart without save. **Железо:** OSD element on, 6-pos selector + momentary switch, raise D by 2 in a hover, stick-save, `diff all` before/after, Blackbox event visible in Explorer; VTX power on a switch measured with a power meter or the goggles' RSSI |
| 2 | `bf-rates-rc` | «Рейты, RC smoothing и feedforward: от стика до setpoint» | A | rate types and formulas (Actual, Betaflight, Quick), `*_rc_rate`/`*_srate`/`*_expo`, `thr_mid`/`thr_expo`, `throttle_limit_*`, rate profiles, `rc_smoothing_*` and `rc_smoothing_info`, link rate vs smoothing, `feedforward_*` with ELRS rates, `deadband` | **SITL:** feed RC steps at 50/150/250/500 Hz into SITL, read `rc_smoothing_info` and setpoint from MSP (`MSP_RC`/debug); Python plot of the rate curve for three `rates_type`. **Железо:** Blackbox of stick snaps at two ELRS rates, setpoint vs rcCommand, feedforward spikes with jitter factor 7 vs 0 |
| 3 | `bf-arming-safety` | «Почему не армится: 26 флагов, runaway takeoff, yaw spin и безопасный старт» | A | full flag table (4.5 + 2025.12 changes) with cause→parameter→fix; `small_angle`, `pwr_on_arm_grace`, `gyro_calib_*`, `auto_disarm_delay`, `enable_stick_arming`, `runaway_takeoff_*`, `yaw_spin_recovery`, `crash_recovery`, PREARM logic, beeper codes | **SITL:** script provokes ≥ 10 flags (THROTTLE, ANGLE via FDM tilt > 25°, CLI, MSP, ARMSWITCH, BOOTGRACE, CALIB with noisy FDM, NOPREARM, BOXFAILSAFE, MOTOR_PROTO) and prints `MSP_STATUS_EX` before/after each fix. **Железо:** flag table filled on the real quad, runaway test with props off (wrong order simulated by `motor_output_reordering`) — observe `RUNAWAY` |
| 4 | `bf-led-buzzer` | «Светодиоды, пищалка и маячки: LED_STRIP, `led`/`color`/`mode_color`, beeper, DShot beacon» | B | §7b plus beeper/beacon: WS2812 wiring and power, `resource LED_STRIP`, timer/DMA, LED tab, function letters, profiles RACE/BEACON/STATUS, visual beeper, `beeper` conditions, `beacon`, `beeper_dshot_beacon_tone`, standalone lost-model buzzer | **Configurator/bench-first** (no LED/beeper in SITL): build an 8-LED layout in the LED tab, export `led`/`color`/`mode_color` lines, explain each field; on the bench measure strip current at brightness 100 vs 30; switch LED profile with `adjrange` 30. **Железо:** race colour on a switch, beacon on RX_LOST verified by switching off the TX |
| 5 | `bf-hd-osd-video` | «Цифровое видео в Betaflight: DJI, Walksnail, HDZero — проводка, DisplayPort, OSD» | A | §7d | **Configurator-first:** Ports + OSD for each system, `diff` of the three configs compared; **Железо:** wiring table filled, OSD in goggles, power-on order, heat test, DVR, latency measurement (reuse `link-digital-video` method) |
| 6 | `bf-servos-pwm` | «Сервы, PWM и таймеры в Betaflight: `resource SERVO`, `servo`, `smix`, SERVO_TILT, channel forwarding» | B | §7a + §7c + servo gimbal from §7e | **SITL:** SITL has USE_SERVOS (non-cloud build): configure `mixer` with a servo (e.g. a gimbal via SERVO_TILT), read servo outputs from the SITL PWM UDP stream; **Железо:** one servo on a freed pad: `resource SERVO 1 <pin>`, `timer` check, BEC power, endpoints `servo 0 1100 1900 1500 100 -1`, channel forwarding to AUX |
| 7 | `bf-gps-setup` | «GPS в Betaflight: модули M8/M10, конфигурация, точность, домашняя точка» | B | `gps_*` (auto config, Galileo, SBAS, rate, models), `gpspassthrough` + u-center, `gps_set_home_point_once`, mag declination/alignment, OSD GPS elements, then Rescue tuning variables not covered (max angle, landing alt, throttle min/max, velocity PID) | **SITL:** Betaflight SITL has no GPS (per `bf-setup-scratch`) → replay a u-blox log through `gpspassthrough`-like Python NMEA/UBX parser to compute HDOP/sat count; **Железо:** time-to-fix with Galileo OFF/ON, cold vs warm, distance from VTX |
| 8 | `bf-features-tour` | «Остальные режимы Betaflight: turtle, launch control, 3D, acro trainer, Horizon/Angle 4.5, camera control» | B | turtle (`crashflip_*`), launch control, 3D, acro trainer, angle/horizon parameters (`angle_limit`, `angle_earth_ref`, `horizon_*`), `level_race_mode`, `ez_landing_*`, camera control/RunCam, PINIO/USER modes | **SITL:** Angle/Horizon/acro trainer/launch control behaviour from setpoint and motor outputs with FDM tilt; `crashflip` logic visible in motor outputs with PWM protocol (check — DShot absent, mark if turtle cannot be shown); **Железо:** turtle and launch control on the field |

New ids must also go into `data/curriculum.json`, `data/content-manifest.json`, `data/glossary.json` and quizzes per
`content/README.md`.

### 6.2 Additions to existing modules (ordered by value)

1. **`bf-cli` — theory, after "Diff vs Dump":** table of `diff`/`dump` scopes and `defaults`/`bare` flags, and the
   `diff` vs `diff all` profile trap. **New subsection "Все команды CLI"** with the §2 table (one line each, A/B only).
   Add `feature list` output for 4.5 (RX_PPM, INFLIGHT_ACC_CAL, RX_SERIAL, MOTOR_STOP, SERVO_TILT, SOFTSERIAL, GPS,
   RANGEFINDER, TELEMETRY, 3D, RX_PARALLEL_PWM, RX_MSP, RSSI_ADC, LED_STRIP, DISPLAY, OSD, CHANNEL_FORWARDING, TRANSPONDER,
   AIRMODE, RX_SPI, ESC_SENSOR, ANTI_GRAVITY — `cli.c featureNames[]`). Add `motor`, `bind_rx`, `gpspassthrough`,
   `serialpassthrough` (ELRS RX flashing), `flash_erase`, `sd_info`, `rc_smoothing_info` to the recipes table.
2. **`bf-intro` — "Карта настройки":** add rows Adjustments (`adjrange`), Video Transmitter (`vtx`, `vtxtable`), LED Strip
   (`led`), Presets, Rates (`rates_type`, `roll_srate`…). Fix the three errors in §6.3.
3. **`bf-pid-reg-in-bf` — practice:** rewrite the broken code block (§6.3), add a "Значения по умолчанию 4.5" table (PID,
   D-min, FF from `pid.h`), add `f_*`, `tpa_low_*`, `pidsum_limit`, dynamic idle.
4. **`bf-modes-osd` — theory:** full `permanentId` table for `aux` (from `msp_box.c`: 0 ARM, 1 ANGLE, 2 HORIZON, 8 CAMSTAB,
   13 BEEPER, 15 LEDLOW, 19 OSD DISABLE, 20 TELEMETRY, 26 BLACKBOX, 27 FAILSAFE, 28 AIR MODE, 29 3D, 32–34 CAMERA CONTROL 1–3,
   35 FLIP OVER AFTER CRASH, 36 PREARM, 39 VTX PIT MODE, 40–43 USER1–4, 45 PARALYZE, 46 GPS RESCUE, 47 ACRO TRAINER,
   48 VTX CONTROL DISABLE, 49 LAUNCH CONTROL, 50 MSP OVERRIDE, 51 STICK COMMANDS DISABLE, 52 BEEPER MUTE, 53 READY), OSD
   stats (`osd_stat_bitmask`, `stats_*`), more alarms (`osd_rssi_dbm_alarm`, `osd_core_temp_alarm`), stick commands table
   (save, profile change, acc calibration, trims) — they are how a user saves adjustments.
5. **`bf-setup-scratch` — step 10 and 12:** `force_battery_cell_count`, `use_cbat_alerts`, `vbat_cutoff_percent`; step 12 GPS:
   `gps_ublox_use_galileo`, `gps_sbas_mode`. Add `small_angle` to the "ANGLE" flag explanation.
6. **`bf-failsafe` — theory:** fix the 4.4 default sentence; add `vtx_low_power_disarm` cross-reference; add the 2025.12
   `landing_disarm_threshold`.
7. **`bf-ports` — functions table:** add the bit values of `serialPortFunction_e` (MSP 1, GPS 2, SmartPort 32, Serial RX 64,
   Blackbox 128, MAVLink 512, ESC sensor 1024, SmartAudio 2048, IBUS tlm 4096, Tramp 8192, RunCam device 16384, TF lidar 32768,
   FrSky OSD 65536, VTX (MSP+DisplayPort) 131072 — `io/serial.h`), `serialrx_inverted`, `serialrx_halfduplex`,
   `crsf_use_negotiated_baud`; "configure from a phone" (Bluetooth/ESP32 MSP bridge).
8. **`bf-filters`** — one paragraph on the F4 bidir rewrite (DSHOT600 → 300, `pid_process_denom ≥ 2`, `config/config.c`), and
   CPU-load target (< 75 % per Oscar Liang for 4.5).
9. **`bf-blackbox`** — a table of the 13 `blackbox_disable_*` fields; `flash_erase`, `msc`, `sd_info`; Adjustments events.
10. **`link-vtx`** — `vtx_power` (table index), `vtx_low_power_disarm`, VTX PIT MODE, `vtx` on a switch (link to
    `bf-adjustments`).

With 6.1 and 6.2 done, the projected coverage is: CLI A+B commands all ✓ (47/47), C commands at least ~; all A/B `set`
variables in §3 named with meaning and default; 52/52 popular questions answered.

### 6.3 Factual errors and outdated statements in existing modules

| # | Module, place | Quote | Problem | Source |
|---|---|---|---|---|
| 1 | `bf-intro`, diagnostics ("после прошивки приёмник/GPS не работают") | "`version` → список опций" | `version` prints firmware/target/date/git/MSP API/board only. The BUILD KEY is printed by `status`; the option list comes from build.betaflight.com by key (the module says this correctly in theory) | `cli/cli.c` `printVersion()`, `cliStatus()` ("BUILD KEY: %s") |
| 2 | `bf-intro`, theory "Архитектура прошивки" | "`pid_process_denom = 2` → PID 4 кГц (типичная отправная точка для большинства сборок)" | 4.5 default is **1** (PID = gyro rate). The firmware itself forces ≥ 2 only on F4/G4 with bidir DShot and gyro > 4 kHz, and switches DSHOT600 → 300 there | `flight/pid.c` `DEFAULT_PID_PROCESS_DENOM 1`; `config/config.c` (USE_PID_DENOM_CHECK block) |
| 3 | `bf-intro`, "Карта настройки"; `bf-pid` theory "Слайдеры" ("Профилей PID четыре… переключаются тумблером"), practice Шаг 2 ("тумблером (режим или `adjustment`)"), protocol step 4 | PID profiles switched by a switch/adjustment | 4.5 has **no** PID-profile adjustment function and no PID-profile mode. Only the **rate** profile is selectable via `adjrange` function 12. PID profile: stick command (thr low + yaw left + roll left / pitch up / roll right → 1/2/3), OSD/CMS, CLI `profile`, `auto_profile_cell_count`. The 4-profile one-flight comparison in `bf-pid` must use a different method (or rate profiles only) | `fc/rc_adjustments.h` (enum), `fc/rc_controls.c` lines 270–283 |
| 4 | `bf-pid-reg-in-bf`, theory I-term and diagnostics | "`iterm_limit` (в 2025.12 — `iterm_windup`) ограничивает максимальное значение I-term"; "`iterm_limit` (дефолт 400; в 2025.12 — `iterm_windup`)" | Two different variables, both in 4.5: `iterm_windup` = 85 (% of `pidsum_limit` at which I stops accumulating) and `iterm_limit` = 400 (absolute I cap). 2025.12 removed `iterm_limit`; `iterm_windup` existed before and still exists. Not a rename | `cli/settings.c` (4.5 and 2025.12 tables), `flight/pid.c` `.itermWindupPointPercent = 85` |
| 5 | `bf-pid-reg-in-bf`, practice step 6 | "увеличьте `tpa_rate` … до 70–80, снизьте `tpa_breakpoint` до 1400" | Default `tpa_breakpoint` is **1350**, so 1400 is a raise (TPA starts later) | `flight/pid.c` `.tpa_breakpoint = 1350` |
| 6 | `bf-pid-reg-in-bf`, practice code blocks | `set p_pitch = 45\nset i_pitch = 50…`, `set p_roll = 42, i_roll = 45, d_roll = 23`, stray `text` lines | Not valid CLI: one `set` per line; literal `\n` is pasted as text; the comma form fails. Also "starting values" below 4.5 defaults with no justification | `cli/cli.c` `cliSet` (single `name = value`) |
| 7 | `bf-pid-reg-in-bf`, practice "Подготовка" step 2 | "включите логирование gyro_scaled, pid, setpoint, motor" | `GYRO_SCALED` is a `debug_mode`, not a log field group; fields are switched off with `blackbox_disable_*`, everything is on by default | `cli/settings.c` `blackbox_disable_*`, `build/debug.c` |
| 8 | `bf-pid-reg-in-bf`, practice step 2 and diagnostics "Bounce-back" | "Если gyro пересекает setpoint в обратную сторону (bounce-back) — P низкий, увеличьте"; "Bounce-back… низкий P-term, высокий D-term" | Contradicts the course's own `bf-pid` ("D мал — bounce-back") and this module's worked example (Damping up fixes bounce-back). Bounce-back is under-damping/I-relax/latency; raising P alone usually makes it worse | course-internal; betaflight.com PID-Tuning-Guide (secondary check recommended) |
| 9 | `bf-failsafe`, theory Stage 1 | "дефолт 1.5 с (так же в 4.3–4.4…)" | Official doc: 1.5 s in 4.5, **1.0 s in 4.4** | `Failsafe.md` lines 46 and 85 |
| 10 | `bf-modes-osd`, OSD | "канва 50×18/60×22" | 4.5 default HD canvas is **53×20** (`OSD_HD_COLS`/`ROWS`); the goggles report their own canvas over MSP (HDZero 50×18, etc. — per vendor, unverified) | `osd/osd.h` |
| 11 | `bf-modes-osd`, `aux` paragraph | "`adjrange` — то же для «подстроек в полёте» (PID, рейты, профили)" | Profiles = rate/OSD/LED only (see #3) | `fc/rc_adjustments.c` |
| 12 | `bf-intro`, versions | "4.5 — … (последний выпуск 4.5.5)" | The 4.5-maintenance branch is at **4.5.6**, and `bf-setup-scratch` is built from 4.5.6 — internal inconsistency. Release tag not verifiable here (API blocked) | `build/version.h` |
| 13 | `bf-intro`, theory | "Поддержка: полётные контроллеры на STM32 (F4, F7, H7)" | 4.5 also targets STM32G47x and **AT32F435**; 2025.12 adds APM32 and RP2350 (PICO) | `src/main/target/` (4.5), `src/platform/` (2025.12) |
| 14 | Docs, not course: betaflight.com In-flight Adjustments | "12 adjustment ranges can be defined" / function 31 SLIDER_MASTER_MULTIPLIER | 30 ranges; function 31 in 2025.12 is LED_DIMMER, slider multiplier only in `master`. Course should not copy the page verbatim | `fc/rc_adjustments.h` in all three branches |
| 15 | `bf-cli-automation`, Грабли 2 | "`noreboot` появился в 4.5.4" | Plausible but **unverified** (shallow clone, no tags) | — |
| 16 | `bf-cli`, BUILD KEY URL | `https://build.betaflight.com/api/builds/<BUILD_KEY>/json` | Endpoint **unverified** here | — |

No errors found in: `bf-filters` (all quoted defaults match the 4.5 source), `bf-rpm-filter` (defaults match),
`bf-setup-scratch` (QUADX order, `dshot_idle_value` 550, `min_throttle` 1070, `min_check` 1050, `max_check` 1900, GPS Rescue
defaults, DShot commands 7/8/12 — all match), `bf-failsafe` other values (`failsafe_throttle_low_delay` 100,
`failsafe_recovery_delay` 5, `failsafe_stick_threshold` 30, Stage 2 blocked for 5 s after boot, switch STAGE1 leaves AUX
channels — match source/docs), `bf-modes-osd` mode ids (match `msp_box.c`), `link-protocols` CRSF 420000 bd (matches).

---

## 7. Hardware integration topics

Question for each topic: can a student **connect and configure** it from the course alone? Verdict scale: **Yes / Partly / No**.

### 7a. Servos — verdict for Betaflight: **No**; INAV: **Partly**; ArduPilot: **Partly**

**What is covered**
- `foundation/f-motors-esc` (theory, ESC protocols): "PWM — импульс 1000–2000 мкс с частотой около 50 Гц" — written about ESCs.
- `inav/inav-setup-wing` ("Сервы в INAV: смикс → servo → выход"): `smix <n> <servo> <input> <weight> <speed> <lc>`, reversal
  in `smix`/`servo`, not on the radio, servo autotrim. Good for a wing.
- `ardupilot/ap-quadplane` ("Главная ловушка: мотор на канале сервы"): timer groups share one protocol/rate, no DShot motor and
  50 Hz servo on one timer; the HeeWing incident. `ap-plane-tuning`: `SERVOn_REVERSED`.
- `companion/payload-gimbal`: `SERVOn_FUNCTION` 6/7/8 = Mount1 yaw/pitch/roll.

**Missing to actually do it**
- Power: servo current (a 9–25 kg·cm servo draws amps on stall), a separate BEC (5–6 V or HV 7.4–8.4 V for HV servos),
  **never from the FC 5 V rail for anything bigger than a micro servo**, common ground, a capacitor on the servo rail.
  Nothing in the course.
- Signal: 50 Hz analogue vs 200–333 Hz digital servos (frame period vs pulse width), 1000–2000 µs pulse, 1500 centre, how to
  check with a servo tester/oscilloscope (`el-measure` could host it).
- Betaflight servo support at all: `USE_SERVOS` and `USE_LED_STRIP` are in the `#if !defined(CLOUD_BUILD)` default block of
  `target/common_pre.h` — **a Cloud Build has servos only if the SERVOS option is ticked** (verify the option name in the
  Configurator, unverified here). Up to 8 servos (`MAX_SUPPORTED_SERVOS`, 1 with QUAD_MIXER_ONLY).
- Betaflight commands: `resource SERVO <n> <pin>` (**1-based**, unlike the Servos tab, per `Servos-And-SERVO_TILT-for-3-1.md`),
  `servo <index> <min> <max> <mid> <rate> <forward channel>` (defaults 1000/2000/1500, `cli.c` format `servo %u %d %d %d %d %d`,
  `flight/servos.h`), `smix` (`<rule> <servo> <source> <rate> <speed> <min> <max> <box>`, `smix reverse <servo> <source> r|n`),
  `set servo_pwm_rate = 50…498` (default 50), `servo_center_pulse` 1500, `servo_lowpass_hz`, `feature SERVO_TILT` (two
  channels, tilt/roll gimbal with CAMSTAB mode id 8, `gimbal_mode` NORMAL/MIXTILT), `feature CHANNEL_FORWARDING` +
  `channel_forwarding_start` (AUX → servo pass-through), modes SERVO1–3 (ids 23–25), `tri_unarmed_servo` for tricopters, the
  Servos tab.
- INAV: `servo_pwm_rate` default 50 (`settings.yaml`), `servo_lpf_hz`, Outputs tab / `timer_output_mode` for timer groups
  (unverified in this audit), endpoints and trim via `servo` (min/max/middle/rate).
- ArduPilot: `SERVOn_FUNCTION`, `SERVOn_MIN/MAX/TRIM/REVERSED`, `SERVO_RATE` (default 50 Hz, `SRV_Channels.cpp` `_RATE`), the
  same timer-group rule as `ap-quadplane`, `SERVO_BLH_MASK`/`SERVO_DSHOT_ESC` for motor vs servo groups.

**Proposal:** module `bf-servos-pwm` (§6.1 #6), plus a short shared section in `electronics/el-wiring` or a new
`el-servos-power`: «Сервы: питание, BEC, сигнал 50/333 Гц, проверка тестером». Lab: bench servo on a separate BEC, current
measured at stall with a multimeter, pulse measured with the course's logic-analyser workflow (`el-peripherals` step 4),
then Betaflight `resource SERVO 1 <freed pad>`, endpoints, channel forwarding; INAV/ArduPilot: same servo via `SERVOn_*`
in SITL (ArduPilot SITL shows `SERVOn` outputs; the course already reads them in `ap-setup-scratch`).

### 7b. RGB LED strips — verdict: **No** (all three firmwares)

**Covered:** only `bf-cli` uses `LED_STRIP 1 A08` as a pad to steal for a motor.

**Missing**
- Wiring/power: WS2812/WS2811, one data line + 5 V + GND; current at full white ≈ tens of mA per LED (verify per strip); power
  from a separate BEC if long; common ground; data-level problem: DIN needs ≥ 0.7 × VIN, so a 3.3 V MCU pin may need VIN
  ≤ 4.7 V (inline diode) — `LED-Strip-Functionality.md` line 102. Max **32 LEDs** (64 with USE_LED_STRIP_64,
  `common_pre.h`).
- Betaflight: Cloud Build option LED_STRIP; `resource LED_STRIP 1 <pin>` (the pad must have a timer with DMA: `timer <pin>
  list`, `dma`); `feature LED_STRIP`; WS2812 needs an 800 kHz signal on a **dedicated hardware timer** (doc line 42), which is why it
  conflicts with motors on the same timer/DMA; the LED tab; CLI `led <i> <x>,<y>:<directions>:<functions>:<colour>` (e.g.
  `led 0 0,15:SD:AWI:0`, `led 4 7,7::C:1`), `color <i> <h>,<s>,<v>`, `mode_color <mode> <function> <colour>`;
  `ledstrip_profile` RACE/BEACON/STATUS, `ledstrip_race_color`, `ledstrip_beacon_*`, `ledstrip_brightness`,
  `ledstrip_visual_beeper`, `ledstrip_grb_rgb`; mode LEDLOW (id 15); Adjustments function 30 (LED profile), 2025.12 31
  (LED dimmer).
- INAV: LED strip similar (`led`, `color`, `mode_color`) plus `led_pin_pwm_mode` (settings.yaml) — not verified in detail.
- ArduPilot: `NTF_LED_TYPES` (NeoPixel bit), `SERVOn_FUNCTION = 120` (NeoPixel1), `NTF_LED_LEN` — **unverified here** (from the
  ArduPilot wiki; not checked in source).

**Proposal:** `bf-led-buzzer` (§6.1 #4). Lab as in §6.1; the INAV/ArduPilot parts go into `inav-setup-scratch` and
`ap-setup-scratch` as a two-line "Подключение светодиодов" subsection.

### 7c. PWM in general — verdict: **Partly**

**Covered:** `f-motors-esc` (PWM/OneShot/Multishot/DShot, calibration), `bf-setup-scratch` (PWM ESC calibration),
`bf-cli` (`resource`, `timer`, `dma`, bitbang DShot), `ap-quadplane` (timer groups).

**Missing:** one page that puts the three side by side: **motor PWM** (`motor_pwm_rate` default 16000 Hz for
OneShot/brushed with `use_unsynced_pwm`; standard PWM 50–490 Hz), **servo PWM** (50 Hz analogue, up to 333 Hz digital), and
**ESC digital protocols** (DShot: no rate, frame per PID loop). Why outputs on one timer share frequency and protocol; why
DShot needs DMA (or bitbang on a GPIO port); how to read a board's timer map (`timer show`, `resource show all`); PWM inputs
(`feature RX_PARALLEL_PWM`, PPM `feature RX_PPM`, `input_filtering_mode`, `rssi_channel` from PWM) — legacy but still asked.
`motor_pwm_rate`, `motor_pwm_inversion`, `use_unsynced_pwm` are named nowhere.

**Proposal:** fold into `bf-servos-pwm` (theory "Три вида ШИМ на одной плате"), with a diagram: timer → channels → pads,
protocol per timer. Lab: on a board, `timer show` + `resource show all` → table of pads with timer number and DMA; propose a
legal assignment for 4 motors + 1 servo + LED.

### 7d. Digital video — verdict: **Partly** (protocol settings yes, physical integration no)

**Covered:** `link-digital-video` ("Четыре семейства", "HD OSD: MSP DisplayPort"): `osd_displayport_device = MSP`,
`vcd_video_system = HD`, UART MSP for the air unit; ArduPilot `SERIALn_PROTOCOL = 42`, `OSD_TYPE = 5`; latency method;
behaviour at range. `bf-modes-osd`: `osd_canvas_*`, HD positions. `ap-setup-scratch` step 13: `OSD_TYPE` 1/5.

**Missing to actually connect one**
- Wiring per system: power input range (DJI O3/O4 air units take 2S–6S directly — **unverified here**, check the DJI spec
  page; Walksnail and HDZero vary by model — check the manual), UART TX↔RX crossed, ground; for DJI the **SBUS output from the
  goggles' controller** (DJI FPV Remote/Goggles linkage) → FC RX pad with `serialrx_provider = SBUS`; for Walksnail the same
  idea (its own RC via the goggles is model-dependent — unverified); HDZero: no RC passthrough (MSP only).
- Betaflight specifics: serial function **VTX (MSP + DisplayPort)** = mask **131072**, usually combined with MSP (1) →
  `serial <id> 131073 115200 …` (`io/serial.h`); `osd_displayport_device = MSP`; `vcd_video_system = HD`; canvas
  `osd_canvas_width`/`height` (default 53×20, `osd/osd.h`); `displayport_msp_fonts`, `displayport_msp_col_adjust`/`row_adjust`,
  `displayport_msp_use_device_blink` (all named nowhere); OSD feature enabled; the 4.4 parameter `displayport_msp_serial`
  that many forum answers still quote **does not exist in 4.5** (absent from the 4.5 table) — GitHub discussion #12167 is about
  that 4.4 setting.
- Goggle side: DJI "Custom OSD"/canvas mode setting, WTFOS + msp-osd for the legacy DJI FPV/Vista/Air Unit (community firmware,
  unverified), Walksnail OSD on, HDZero OSD on — none are mentioned.
- Operations: power-on order (goggles and air unit bind/link), **heat** (DJI and Walksnail air units overheat on the bench
  without airflow; low-power-on-disarm options exist in their firmware — unverified), recording (DVR on air unit vs goggles),
  channel/bandwidth/power settings in the goggles (not via VTX tables), `vtx_low_power_disarm` does not apply to them,
  latency vs bitrate modes.
- INAV: `osd_video_system` = AUTO/PAL/NTSC/**HDZERO/DJIWTF/AVATAR/BF43COMPAT/BFHDCOMPAT/DJI_NATIVE** (`settings.yaml`) and the
  serial function MSP DisplayPort — the course says only "тип OSD — по документации своей системы".
- ArduPilot: `OSD_TYPE = 5` (`AP_OSD.cpp` values 0 None, 1 MAX7456, 2 SITL, 3 MSP, 4 TXONLY, 5 MSP_DISPLAYPORT),
  `SERIALn_PROTOCOL = 42` (DisplayPort, `AP_SerialManager.cpp`; 33 = "DJI FPV" legacy MSP), `MSP_OPTIONS`, `OSD_TYPE2` for a second
  OSD (names from source; `MSP_OPTIONS` bit meanings unverified).

**Proposal:** module `bf-hd-osd-video` (§6.1 #5), or extend `link-digital-video` to ≥ 1100 words with a wiring table per
system. Lab: Configurator-first (no OSD in SITL): set up the three configs (DJI O3, Walksnail, HDZero) on one FC on the bench,
`diff all` each, compare; on the real quad: wiring photo, OSD visible, heat test (temperature of the air unit after 5 min
disarmed at full power vs low power), DVR file, latency with the existing method. INAV/ArduPilot: add the `osd_video_system`
and `OSD_TYPE`/`SERIALn_PROTOCOL` rows to `inav-setup-scratch` and `ap-setup-scratch`; ArduPilot SITL has `OSD_TYPE = 2`
(SITL OSD) for a software preview of the layout.

### 7e. Camera gimbals — verdict: Betaflight **No**; ArduPilot **Yes for parameters, No for wiring**; INAV **No**

**Covered:** `payload-gimbal` — Gimbal Protocol v2, ArduPilot `MNT1_*` table, `RCx_OPTION` 212–214/163, `SERVOn_FUNCTION`
6/7/8, `SERIALn_PROTOCOL = 8`, PX4 `MNT_MODE_IN/OUT`. MAVLink-centric and correct.

**Missing**
- Betaflight servo gimbal: `feature SERVO_TILT` + mode CAMSTAB (id 8) + `gimbal_mode` (NORMAL/MIXTILT), or `feature
  CHANNEL_FORWARDING` + `channel_forwarding_start` to drive a tilt servo straight from an AUX pot; servo power (§7a).
- Betaflight 2025.12 serial gimbal: new `gimbal_*` variables (`gimbal_stabilisation` 0 none / 1 pitch / 2 roll+pitch,
  `gimbal_*_rc_gain`, `_gain`, `_offset`, `_limit`, `gimbal_sensitivity`; defaults in `io/gimbal_control.c` header table) and
  serial function GIMBAL (`1 << 18`). The device family it targets is **unverified here** — read the 2025.12 release notes before
  teaching it.
- ArduPilot: the full `MNT1_TYPE` list from source: 0 None, 1 Servo, 2 3DR Solo, 3 Alexmos Serial, 4 SToRM32 MAVLink,
  5 SToRM32 Serial, 6 MAVLink (Gremsy/AVT), 7 BrushlessPWM, 8 Siyi, 9 Scripting, 10 Xacti, 11 Viewpro, 12 Topotek, 13 CADDX,
  14 XFRobot (`AP_Mount_Params.cpp`, master; numbering stable, newer entries version-dependent). Wiring: brushless gimbal
  power (often 3S–6S direct — per vendor), UART TX/RX to a `SERIALn` with protocol 8 (Siyi/ViewPro, etc.) or MAVLink 2
  (Gremsy), PWM to a Storm32 for `MNT1_TYPE = 7`; video out of the gimbal camera into the VTX/air unit.
- INAV: servo gimbal via `smix` sources (gimbal pitch/roll inputs) and INAV 7+ serial gimbal/headtracker
  (`headtracker_dev_type` exists in `settings.yaml`) — unverified details.
- Control from the radio: Betaflight AUX → channel forwarding; ArduPilot `RCx_OPTION` 212–214 (covered), `MNT1_RC_RATE`
  (covered).

**Proposal:** add a «Сервоподвес в Betaflight и INAV» section to `bf-servos-pwm`, and a «Подключение подвеса к железу»
practice block to `payload-gimbal` (power, UART/PWM wiring per `MNT1_TYPE`, test with `MNT1_DEFLT_MODE = 3` RC targeting).
Lab: ArduPilot SITL `MNT1_TYPE = 1` with `SERVO9_FUNCTION = 7`, move RC pitch, read SERVO9 (SITL already used in the course);
Betaflight: tilt servo through channel forwarding on the bench.

### 7f. Summary for §6

Added to the module list in §6.1: `bf-servos-pwm` (#6, covers 7a, 7c and the servo gimbal part of 7e), `bf-led-buzzer`
(#4, 7b), `bf-hd-osd-video` (#5, 7d). Optional shared electronics module `el-servos-power` («Сервы и нагрузки на BEC: питание,
сигнал, проверка»), priority B, and additions to `payload-gimbal`, `inav-setup-scratch`, `ap-setup-scratch` and
`link-digital-video` as described above.

---

## Appendix — counts

- CLI commands in 4.5: **59** (same 59 in 2025.12) — ✓ 19, ~ 23, ✗ 17.
- `set` variables in 4.5: **683** table entries (2025.12: 760) — named in Betaflight modules 140, anywhere in the course 168.
  Explained with meaning and default: not measured automatically; the 140 is the upper bound.
- Popular questions: **52** — ✓ 25, ~ 12, ✗ 15.
- Adjustments: 30 functions in 4.5 (31 in 2025.12) — 0 explained.
- Factual problems flagged: 16 (13 course errors or inconsistencies, 1 docs error, 2 unverified claims).
