# betaflight

Sources: Betaflight source cloned at 4.5-maintenance (7dcc851, = 4.5.5+), 2025.12-maintenance, master (2026.12 dev); release tags 4.3.0/4.4.0/4.5.0–4.5.5/2025.12.1 fetched raw; betaflight.com docs repo (github.com/betaflight/betaflight.com); betaflight-configurator and blackbox-log-viewer master. Latest releases at check time: 4.5.5, 2025.12.5, 2026.6.2.

## bf-intro
verified: 30
- severity: outdated
  file: content/betaflight/bf-intro.md
  quote: "**Betaflight 4.5** — актуальная стабильная ветка."
  fix: "**Betaflight 4.5** — предыдущая стабильная ветка (последний выпуск 4.5.5); актуальные — 2025.12.x и 2026.6.x."
  why: Releases 2025.12.x and 2026.6.x are tagged; 4.5 is no longer the current stable line.
  source: https://github.com/betaflight/betaflight/tags
- severity: error
  file: content/betaflight/bf-intro.md
  quote: "С версии **2025.12** доступен **веб-конфигуратор**"
  fix: "Веб-приложение было доступно уже для 4.5 (Configurator 10.10), а с версии **2025.12** основным стал **веб-конфигуратор**"
  why: 4.5 release notes already point to the online app at app.betaflight.com; 2025.12 made the PWA the primary app.
  source: https://github.com/betaflight/betaflight.com/blob/master/docs/wiki/release/Betaflight-4-5-Release-Notes.md
- severity: error
  file: content/betaflight/bf-intro.md
  quote: "`version` в CLI показывает версию, target, `BUILD KEY` (ключ сборки для воспроизведения) и список включённых опций."
  fix: "`version` в CLI показывает версию, target, дату и git-ревизию сборки; `BUILD KEY` (ключ сборки для воспроизведения) печатает `status`, а список опций отдаёт build.betaflight.com по этому ключу."
  why: cliVersion() calls printVersion() only; "BUILD KEY:" is printed in cliStatus(); no options list is printed by either.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/cli.c
- severity: error
  file: content/betaflight/bf-intro.md
  quote: "(обычно передний правый для схемы «Motor 1»)"
  fix: "(в Betaflight Quad X: Motor 1 — задний правый, 2 — передний правый, 3 — задний левый, 4 — передний левый)"
  why: mixerQuadX order is REAR_R, FRONT_R, REAR_L, FRONT_L.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/flight/mixer_init.c
- severity: error
  file: content/betaflight/bf-intro.md
  quote: "(Motor 1 — передний правый и т.д.)"
  fix: "(Motor 1 — задний правый, Motor 2 — передний правый и т.д.)"
  why: Same mixer table; Motor 1 is rear-right in Quad X.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/flight/mixer_init.c
- severity: imprecise
  file: content/betaflight/bf-intro.md
  quote: "мигает ошибка (например, RX_FAILSAFE)"
  fix: "мигает ошибка (например, RXLOSS)"
  why: The arming-disable flag ARMING_DISABLED_RX_FAILSAFE is displayed as "RXLOSS"; no "RX_FAILSAFE" string exists.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/fc/runtime_config.c
- severity: outdated
  file: content/betaflight/bf-intro.md
  quote: "на вкладке Configuration увеличить значение Minimum Throttle (типичное значение 1050–1100)."
  fix: "с DShot `min_throttle` не используется: на вкладке Motors поднять Motor Idle (`dshot_idle_value` в 4.5, `motor_idle` в 2025.12; дефолт 5.5%)."
  why: With DShot idle is set by dshot_idle_value (Motors tab "Motor idle %"); min_throttle is removed in 2025.12.
  source: https://github.com/betaflight/betaflight/blob/2025.12-maintenance/src/main/cli/settings.c
- severity: imprecise
  file: content/betaflight/bf-intro.md
  quote: "**UART1** — часто связан с USB, **MSP ON**."
  fix: "**USB VCP** — отдельная строка в Ports (не UART1), MSP на ней обязателен; UART1 — обычный аппаратный порт."
  why: USB VCP is its own serial identifier (20) separate from UART1 (0), and a config without MSP on VCP is rejected.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/io/serial.c
- severity: outdated
  file: content/betaflight/bf-intro.md
  quote: "`motor_poles`, `dshot_idle_value` |"
  fix: "`motor_poles`, `dshot_idle_value` (2025.12: `motor_idle`) |"
  why: dshot_idle_value does not exist in 2025.12; replaced by motor_idle.
  source: https://github.com/betaflight/betaflight/blob/2025.12-maintenance/src/main/fc/parameter_names.h
- severity: outdated
  file: content/betaflight/bf-intro.md
  quote: "- **ESC/Motor** — **DSHOT300/600** при поддержке ESC; **Bidirectional DShot** для RPM-фильтра."
  fix: "- **ESC/Motor** — в текущем приложении протокол DShot, **Bidirectional DShot** и Motor idle настраиваются во вкладке **Motors**."
  why: Current app docs place Bidirectional DShot and Motor idle in the Motors tab.
  source: https://github.com/betaflight/betaflight.com/blob/master/docs/wiki/app/motors-tab.md
- severity: imprecise
  file: content/betaflight/bf-intro.md
  quote: "`OSD` (по `osd framerate_hz`)"
  fix: "`OSD` (по `osd_framerate_hz`)"
  why: Setting name is osd_framerate_hz.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/settings.c

## bf-cli
verified: 35
- severity: error
  file: content/betaflight/bf-cli.md
  quote: "D-term naming: в 4.5+ `d_roll` — base D, `d_max_roll` — peak."
  fix: "D-term naming: в 4.5 `d_roll` — пиковый D, `d_min_roll` — базовый; в 2025.12 наоборот: `d_roll` — базовый, `d_max_roll` — пиковый (`d_min_*` удалены)."
  why: 4.5 has d_roll (pid.D, max) + d_min_roll (base); d_max_roll only exists from 2025.12 where d_roll became the base value.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/settings.c
- severity: error
  file: content/betaflight/bf-cli.md
  quote: "| Узнать версию, target, BUILD KEY | `version` |"
  fix: "| Узнать версию, target / BUILD KEY | `version` / `status` |"
  why: BUILD KEY is printed by status, not by version.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/cli.c
- severity: error
  file: content/betaflight/bf-cli.md
  quote: "`dshotprog 1 21` (21 — reversed, 20 — normal; у части ESC 7/8 — direction 1/2), затем `dshotprog 1 12` (save settings); моторы без пропов, индекс с 1"
  fix: "`dshotprog 0 21` (21 — reversed, 20 — normal; у части ESC 7/8 — direction 1/2), затем `dshotprog 0 12` (save settings); моторы без пропов, индекс с 0 (255 — все моторы)"
  why: parseOutputIndex accepts 0..motorCount-1 (255 = all); "dshotprog 1" addresses the second motor.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/cli.c
- severity: error
  file: content/betaflight/bf-cli.md
  quote: "`profile 1`, `rateprofile 2`, `battery_profile`"
  fix: "`profile 1`, `rateprofile 2` (команды `battery_profile` в Betaflight нет)"
  why: CLI command table has no battery_profile command (that is INAV).
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/cli.c
- severity: error
  file: content/betaflight/bf-cli.md
  quote: "`sensor_hardware`, `gyroregisters`"
  fix: "`gyroregisters` (найденные датчики — в выводе `status`)"
  why: There is no sensor_hardware CLI command; detected sensors are listed in status.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/cli.c
- severity: error
  file: content/betaflight/bf-cli.md
  quote: "set gyro_lpf2_hz = 300"
  fix: "set gyro_lpf2_static_hz = 300"
  why: gyro_lpf2_hz does not exist in 4.5/2025.12; the setting is gyro_lpf2_static_hz.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/settings.c
- severity: error
  file: content/betaflight/bf-cli.md
  quote: "set dterm_lpf2_hz = 150"
  fix: "set dterm_lpf2_static_hz = 150"
  why: dterm_lpf2_hz does not exist; the setting is dterm_lpf2_static_hz.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/settings.c
- severity: error
  file: content/betaflight/bf-cli.md
  quote: "сверить `msp_baudrate` и скорость терминала"
  fix: "сверить скорость MSP на порту (`serial`/вкладка Ports) и скорость терминала (для USB VCP она не важна)"
  why: There is no msp_baudrate setting; MSP baud is a field of the serial command.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/settings.c
- severity: imprecise
  file: content/betaflight/bf-cli.md
  quote: "старая версия Betaflight (< 4.5)"
  fix: "старая версия Betaflight (< 4.4, до Cloud Build)"
  why: 4.4 status already prints "BUILD KEY:".
  source: https://github.com/betaflight/betaflight/blob/4.4-maintenance/src/main/cli/cli.c

## bf-filters
verified: 32
- severity: error
  file: content/betaflight/bf-filters.md
  quote: "(RPM-notch → динамический notch → LPF1 → LPF2 для гироскопа; LPF1 → notch → LPF2 для D-term)"
  fix: "(LPF2 при даунсэмплинге → RPM-notch → статические notch → LPF1 → динамический notch для гироскопа; notch → LPF1 → LPF2 для D-term)"
  why: In filterGyro() lowpass2 is applied in the sample/downsample stage, then RPM, notch1/2, lowpass1, dyn notch last; pid.c applies dtermNotch, then dtermLowpass, then dtermLowpass2.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/sensors/gyro_filter_impl.c
- severity: error
  file: content/betaflight/bf-filters.md
  quote: "### Цепочка гироскопа в Betaflight 4.5 (порядок применения в `gyroFiltering()`)"
  fix: "### Цепочка гироскопа в Betaflight 4.5 (параметры; реальный порядок в `filterGyro()`: LPF2 → RPM → статические notch → LPF1 → динамический notch)"
  why: Function is filterGyro() (gyro_filter_impl.c) and the numbered list below does not match its order (dyn notch is last, LPF2 first).
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/sensors/gyro_filter_impl.c
- severity: outdated
  file: content/betaflight/bf-filters.md
  quote: "Blackbox на 2 кГц и выше, `debug_mode = GYRO_SCALED`."
  fix: "Blackbox на 2 кГц и выше, `debug_mode = GYRO_SCALED` (только 4.5; в 2025.12 режим удалён — нефильтрованный гироскоп пишется в поле `gyroUnfilt`)."
  why: GYRO_SCALED is absent from the 2025.12 debug mode table.
  source: https://github.com/betaflight/betaflight/blob/2025.12-maintenance/src/main/build/debug.c
- severity: imprecise
  file: content/betaflight/bf-filters.md
  quote: "без RPM-фильтра — `count = 3`, `q = 250–300` (шире)"
  fix: "без RPM-фильтра — `count = 4–5`, `q = 250–300` (шире)"
  why: Official PID tuning tab guidance: with RPM filter 1–2 notches, without RPM filter 4 or 5.
  source: https://github.com/betaflight/betaflight.com/blob/master/docs/wiki/app/pid-tuning-tab.mdx

## bf-rpm-filter
verified: 22
- severity: error
  file: content/betaflight/bf-rpm-filter.md
  quote: "В `status` должна быть DShot-телеметрия с нулевыми оборотами и почти нулевыми ошибками."
  fix: "Команда `dshot_telemetry_info` должна показать телеметрию по всем моторам с почти нулевыми ошибками (`status` её не выводит)."
  why: cliStatus() prints nothing about DShot telemetry; dshot_telemetry_info is the dedicated command.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/cli.c
- severity: error
  file: content/betaflight/bf-rpm-filter.md
  quote: "арм заблокирован, в OSD `RPMFILTER`"
  fix: "арм заблокирован, в OSD `DSHOT_TELEM`"
  why: No RPMFILTER arming flag exists; missing telemetry sets ARMING_DISABLED_DSHOT_TELEM shown as "DSHOT_TELEM".
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/fc/runtime_config.c
- severity: imprecise
  file: content/betaflight/bf-rpm-filter.md
  quote: "в OSD `DSHOT_TELEM`/RPMFILTER, арм невозможен"
  fix: "в OSD `DSHOT_TELEM`, арм невозможен"
  why: Only DSHOT_TELEM exists as an arming-disable reason.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/fc/core.c
- severity: imprecise
  file: content/betaflight/bf-rpm-filter.md
  quote: "Переведи eRPM в Гц: `Гц = eRPM / (motor_poles / 2) / 60`."
  fix: "Сырое поле `eRPM[n]` (blackbox_decode/orangebox) хранится в единицах по 100 eRPM: `Гц = eRPM × 100 / (motor_poles / 2) / 60`; Blackbox Explorer сам показывает rpm и Гц."
  why: Firmware uses ERPM_PER_LSB = 100; the log viewer converts with value*200/poles.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/drivers/dshot.c

## bf-blackbox
verified: 26
- severity: error
  file: content/betaflight/bf-blackbox.md
  quote: "`blackbox_uart`/`blackbox_baud` — внешний логгер."
  fix: "Внешний логгер — функция Blackbox на UART во вкладке Ports (`serial <id> 128 …` с blackbox baud); отдельных `blackbox_uart`/`blackbox_baud` в 4.5 и 2025.12 нет."
  why: These settings exist only on master (2026.12 dev), not in 4.5 or 2025.12 settings.c.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/settings.c
- severity: imprecise
  file: content/betaflight/bf-blackbox.md
  quote: "Заголовок лога содержит **весь `diff`** — по логу можно восстановить конфигурацию полёта."
  fix: "Заголовок лога содержит около 190 ключевых параметров (PID, рейты, фильтры, моторы), но не весь `diff`: нет `aux`, `serial`, OSD, failsafe — полный бэкап только через `diff all`."
  why: blackboxWriteSysinfo writes a fixed list of ~190 header lines; modes, ports, OSD, failsafe are not included.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/blackbox/blackbox.c
- severity: outdated
  file: content/betaflight/bf-blackbox.md
  quote: "`GYRO_SCALED` — сырой гироскоп до фильтров"
  fix: "`GYRO_SCALED` — сырой гироскоп до фильтров (только 4.5; в 2025.12 удалён, используйте поле `gyroUnfilt`)"
  why: GYRO_SCALED is not in the 2025.12 debug mode list.
  source: https://github.com/betaflight/betaflight/blob/2025.12-maintenance/src/main/build/debug.c
- severity: outdated
  file: content/betaflight/bf-blackbox.md
  quote: "включить Gyro/D-term RPM filters"
  fix: "включить RPM-фильтр (в 4.5 он есть только на гироскопе; отдельного D-term RPM-фильтра нет)"
  why: 4.5 has only rpm_filter_* applied in the gyro chain; no dterm RPM settings exist.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/sensors/gyro_filter_impl.c

## bf-failsafe
verified: 34
- severity: error
  file: content/betaflight/bf-failsafe.md
  quote: "дефолт 1.5 с в 4.5, 1.0 с в 4.4"
  fix: "дефолт 1.5 с (так же в 4.3–4.4; между 4.4 и 4.5 изменился `failsafe_recovery_delay`: 1.0 → 0.5 с)"
  why: failsafe_delay = 15 at tags 4.3.0, 4.4.0 and 4.5.0; what changed is failsafe_recovery_delay (10 → 5). The official wiki line repeats the same mistake.
  source: https://github.com/betaflight/betaflight/blob/4.4.0/src/main/flight/failsafe.c
- severity: error
  file: content/betaflight/bf-failsafe.md
  quote: "Повторный арм возможен после ≥3 с стабильной связи и выключенного тумблера ARM."
  fix: "Повторный арм возможен после `failsafe_recovery_delay` стабильной связи (0.5 с по умолчанию в 4.5) и выключенного тумблера ARM."
  why: FAILSAFE_LANDED/RX_LOSS_MONITORING uses receivingRxDataPeriodPreset = rxDataRecoveryPeriod; no 3 s rule in code (stale wiki text).
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/flight/failsafe.c
- severity: error
  file: content/betaflight/bf-failsafe.md
  quote: "Повторный арм блокируется минимум на 30 с связи."
  fix: "Повторный арм — после `failsafe_recovery_delay` стабильной связи, как и в DROP."
  why: PERIOD_OF_30_SECONDS is defined but unused; landing path goes through the same recovery-delay logic.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/flight/failsafe.c
- severity: imprecise
  file: content/betaflight/bf-failsafe.md
  quote: "отклонение стиков больше 30°"
  fix: "отклонение стиков больше `failsafe_stick_threshold` (30% хода стика)"
  why: areSticksActive(stickPercentLimit) compares stick deflection in percent, not degrees.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/fc/core.c
- severity: error
  file: content/betaflight/bf-failsafe.md
  quote: "AUTO-LAND без самовыравнивания бессмыслен: в Stage 1 на fallback-каналах должен включаться ANGLE."
  fix: "В Stage 2 (AUTO-LAND и GPS Rescue) Betaflight сам включает ANGLE при наличии акселерометра; fallback канала ANGLE влияет только на Stage 1."
  why: updateFlightModes enables ANGLE_MODE when failsafeIsActive() and ACC is present.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/fc/core.c
- severity: error
  file: content/betaflight/bf-failsafe.md
  quote: "Иначе на AUTO-LAND дрон снижается без выравнивания."
  fix: "Это нужно только для Stage 1: в Stage 2 ANGLE включается автоматически (нужен откалиброванный акселерометр)."
  why: Same core.c logic; landing is always self-levelled when ACC is available.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/fc/core.c
- severity: error
  file: content/betaflight/bf-failsafe.md
  quote: "в Stage 1 не включается ANGLE (fallback канала режима не настроен)."
  fix: "акселерометр отключён или не откалиброван (ANGLE в Stage 2 включается автоматически только с ACC), либо `failsafe_throttle` не подобран."
  why: Stage 2 forces ANGLE regardless of fallback; tumbling points to missing ACC or wrong throttle.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/fc/core.c
- severity: outdated
  file: content/betaflight/bf-failsafe.md
  quote: "`failsafe_off_delay` (десятые, время AUTO-LAND до дизарма)"
  fix: "`failsafe_off_delay` (десятые, время AUTO-LAND до дизарма; в 2025.12 заменён на `failsafe_landing_time` в секундах, дефолт 60)"
  why: 2025.12 settings.c has failsafe_landing_time (0–250 s, default 60) and no failsafe_off_delay, so the module's `set failsafe_off_delay = 100` fails there.
  source: https://github.com/betaflight/betaflight/blob/2025.12-maintenance/src/main/flight/failsafe.c
- severity: imprecise
  file: content/betaflight/bf-failsafe.md
  quote: "просто дизарм; 0 = выкл)"
  fix: "просто дизарм; дефолт 100 = 10 с; 0 — дизарм при любом низком газе в момент потери связи)"
  why: With 0 the throttleLowPeriod is always already expired when throttle is low, so it never disables the check.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/flight/failsafe.c
- severity: error
  file: content/betaflight/bf-failsafe.md
  quote: "на земле без пропов — выключить пульт, в OSD «FAILSAFE», через 1 с «RESCUE» (без арма — только индикация)"
  fix: "на земле без пропов — выключить пульт: без арма failsafe не запускается, в OSD будет только `RXLOSS`; стадии проверять тумблером FAILSAFE в арме без пропов"
  why: In FAILSAFE_IDLE when disarmed the state machine does not advance; the "FAIL SAFE" warning needs failsafeIsActive().
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/osd/osd_warnings.c

## bf-modes-osd
verified: 26
- severity: error
  file: content/betaflight/bf-modes-osd.md
  quote: "это спасение при потере ориентации и обязательное условие для AUTO-LAND в failsafe."
  fix: "это спасение при потере ориентации (в Stage 2 failsafe ANGLE включается автоматически, тумблер для этого не нужен)."
  why: failsafeIsActive() forces ANGLE_MODE when ACC is present.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/fc/core.c
- severity: error
  file: content/betaflight/bf-modes-osd.md
  quote: "sag-компенсация `vbat_sag_compensation` показывает «отдохнувшее» напряжение."
  fix: "`vbat_sag_compensation` — не индикация: она поднимает выход моторов при просадке напряжения, чтобы отклик не «плыл» по ходу разряда."
  why: vbat_sag_compensation is a PID-profile value used in the mixer (motor output scaling), not an OSD voltage display.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/flight/mixer.c
- severity: error
  file: content/betaflight/bf-modes-osd.md
  quote: "`osd_timer` по арму"
  fix: "`osd_tim1`/`osd_tim2` (источник, точность, порог) — по арму"
  why: There is no osd_timer setting; timers are osd_tim1/osd_tim2, positions osd_tim_1_pos/osd_tim_2_pos.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/settings.c
- severity: imprecise
  file: content/betaflight/bf-modes-osd.md
  quote: "id режима (`BOXARM` = 0, `BOXANGLE` = 1, … — см. `fc/rc_modes.h`)"
  fix: "id режима — `permanentId` из `msp/msp_box.c` (ARM = 0, ANGLE = 1, HORIZON = 2, FAILSAFE = 27, PREARM = 36), а не номер из enum в `fc/rc_modes.h`"
  why: cliAux parses the mode via findBoxByPermanentId(); permanent IDs differ from the boxId enum for most modes.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/msp/msp_box.c
- severity: outdated
  file: content/betaflight/bf-modes-osd.md
  quote: "в OSD `ARMSWITCH` или `NOPREARM`"
  fix: "в OSD `ARMSWITCH` (в 2025.12 — `ARM_SWITCH`) или `NOPREARM`"
  why: Flag name renamed in the 2025.12 armingDisableFlagNames table.
  source: https://github.com/betaflight/betaflight/blob/2025.12-maintenance/src/main/fc/runtime_config.c

## bf-ports
verified: 28
- severity: error
  file: content/betaflight/bf-ports.md
  quote: "- **Serial Rx** + выбор протокола во вкладке **Configuration**;"
  fix: "- **Serial Rx** во вкладке **Ports** + выбор протокола во вкладке **Receiver**;"
  why: Receiver Mode and Serial Receiver Provider live in the Receiver tab in the current app.
  source: https://github.com/betaflight/betaflight.com/blob/master/docs/wiki/getting-started/setup-guide.md
- severity: error
  file: content/betaflight/bf-ports.md
  quote: "1. После перезагрузки — **Configuration** → раздел **Receiver**."
  fix: "1. После перезагрузки — вкладка **Receiver**."
  why: Same; the heading "Шаг 4. Протокол приёмника (Configuration)" should also say Receiver.
  source: https://github.com/betaflight/betaflight.com/blob/master/docs/wiki/app/receiver-tab.md
- severity: error
  file: content/betaflight/bf-ports.md
  quote: "| SoftSerial | любые 2 ноги | — | до 115200, нагружает CPU, не для приёмника |"
  fix: "| SoftSerial | любые 2 ноги | — | до 19200 (прошивка ограничивает), MSP и Serial RX на нём запрещены |"
  why: isSerialConfigValid() clamps softserial baud indices to BAUD_19200 and strips MSP/RX_SERIAL functions.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/io/serial.c
- severity: imprecise
  file: content/betaflight/bf-ports.md
  quote: "четвёртый может привести к сбросу настроек MSP после перезагрузки."
  fix: "с четвёртым конфигурация портов считается невалидной и при загрузке **вся** сбрасывается к умолчаниям."
  why: Invalid serial config (MAX_MSP_PORT_COUNT = 3 exceeded, or VCP without MSP) triggers pgResetFn_serialConfig() for all ports.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/config/config.c
- severity: outdated
  file: content/betaflight/bf-ports.md
  quote: "идентификатор порта (0 = UART1, 1 = UART2, … 20 = VCP/USB, 30+ = SoftSerial)"
  fix: "идентификатор порта (в 4.5: 0 = UART1, 1 = UART2, … 20 = VCP/USB, 30+ = SoftSerial; в 2025.12 `diff` пишет имена, например `serial UART3 64 …`)"
  why: 2025.12 prints "serial %s ..." with port names and renumbered UARTs (UART1 = 51 internally); numeric legacy ids are still accepted.
  source: https://github.com/betaflight/betaflight/blob/2025.12-maintenance/src/main/io/serial.h
- severity: imprecise
  file: content/betaflight/bf-ports.md
  quote: "**USB** часто «сидит» на **UART1** или отдельном USB-мосте"
  fix: "**USB** на STM32-платах — отдельный виртуальный порт (строка USB VCP в Ports), а не UART1; исключение — редкие платы с внешним USB-UART мостом"
  why: SERIAL_PORT_USB_VCP is a separate identifier from UART1.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/io/serial.h
- severity: imprecise
  file: content/betaflight/bf-ports.md
  quote: "`esc_sensor` в CLI (или"
  fix: "`feature ESC_SENSOR` в CLI (или"
  why: ESC telemetry is the feature ESC_SENSOR; there is no esc_sensor setting (same applies to "не включён `esc_sensor`" a line above).
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/settings.c
- severity: imprecise
  file: content/betaflight/bf-ports.md
  quote: "По умолчанию часто включены **SBUS**, **CRSF**, **GHST**."
  fix: "По умолчанию в Firmware Flasher отмечен только **CRSF**; **SBUS** и **GHST** тоже нужно выбрать вручную."
  why: Build Options doc lists only SERIALRX_CRSF with Default = Yes among receiver protocols.
  source: https://github.com/betaflight/betaflight.com/blob/master/docs/wiki/guides/current/Build-Options.md

## bf-pid
verified: 14
- severity: outdated
  file: content/betaflight/bf-pid.md
  quote: "`simplified_feedforward_gain`, `simplified_d_max_gain`"
  fix: "`simplified_feedforward_gain`, `simplified_dmax_gain` (в 2025.12 — `simplified_d_max_gain`)"
  why: In 4.5 the slider setting is simplified_dmax_gain; simplified_d_max_gain exists only from 2025.12.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/fc/parameter_names.h

## bf-pid-reg-in-bf
verified: 38
- severity: error
  file: content/betaflight/bf-pid-reg-in-bf.md
  quote: "Параметр `i_limit` ограничивает максимальное значение I-term."
  fix: "Параметр `iterm_limit` (в 2025.12 — `iterm_windup`) ограничивает максимальное значение I-term."
  why: i_limit does not exist; 4.5 uses iterm_limit (default 400), 2025.12 replaced it with iterm_windup.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/settings.c
- severity: error
  file: content/betaflight/bf-pid-reg-in-bf.md
  quote: "Проверить параметр `i_limit` (100–150 достаточно)."
  fix: "Проверить `iterm_limit` (дефолт 400; в 2025.12 — `iterm_windup`)."
  why: Wrong name; default iterm_limit is 400.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/flight/pid.c
- severity: error
  file: content/betaflight/bf-pid-reg-in-bf.md
  quote: "`iterm_relax_type = GYRO`"
  fix: "`iterm_relax_type = SETPOINT`"
  why: resetPidProfile sets iterm_relax_type = ITERM_RELAX_SETPOINT in 4.5 and 2025.12.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/flight/pid.c
- severity: error
  file: content/betaflight/bf-pid-reg-in-bf.md
  quote: "во вкладке Configuration включите *RPM Filter*, установите `rpm_notch_q = 500` (CLI)."
  fix: "во вкладке Motors включите **Bidirectional DShot** и задайте Motor poles (RPM-фильтр включится сам); `rpm_filter_q = 500` — значение по умолчанию (CLI)."
  why: rpm_notch_q does not exist (setting is rpm_filter_q); RPM filtering is activated by bidirectional DShot in the Motors tab.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/pg/rpm_filter.c
- severity: error
  file: content/betaflight/bf-pid-reg-in-bf.md
  quote: "set gyro_lowpass2_hz = 300"
  fix: "set gyro_lpf2_static_hz = 300"
  why: gyro_lowpass2_hz is a pre-4.0 name; not in 4.5/2025.12.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/settings.c
- severity: error
  file: content/betaflight/bf-pid-reg-in-bf.md
  quote: "set gyro_lowpass2_type = PT2"
  fix: "set gyro_lpf2_type = PT2"
  why: Setting name is gyro_lpf2_type.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/settings.c
- severity: error
  file: content/betaflight/bf-pid-reg-in-bf.md
  quote: "set dterm_lowpass2_hz = 150"
  fix: "set dterm_lpf2_static_hz = 150"
  why: Setting name is dterm_lpf2_static_hz.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/settings.c
- severity: error
  file: content/betaflight/bf-pid-reg-in-bf.md
  quote: "set dterm_lowpass2_type = PT2"
  fix: "set dterm_lpf2_type = PT2"
  why: Setting name is dterm_lpf2_type.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/settings.c
- severity: error
  file: content/betaflight/bf-pid-reg-in-bf.md
  quote: "set dynamic_notch_range = MEDIUM"
  fix: "set dyn_notch_max_hz = 600"
  why: No dynamic_notch_range/dyn_notch_range in 4.5; range is set by dyn_notch_min_hz/dyn_notch_max_hz.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/pg/dyn_notch.c
- severity: error
  file: content/betaflight/bf-pid-reg-in-bf.md
  quote: "set dynamic_notch_q = 250"
  fix: "set dyn_notch_q = 250"
  why: Setting name is dyn_notch_q.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/settings.c
- severity: error
  file: content/betaflight/bf-pid-reg-in-bf.md
  quote: "set p_pitch = 45, i_pitch = 50, d_pitch = 25"
  fix: "set p_pitch = 45\nset i_pitch = 50\nset d_pitch = 25"
  why: CLI set takes one name = value per command; comma lists are parsed as an invalid value (same applies to the roll, yaw and d_min lines).
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/cli.c
- severity: outdated
  file: content/betaflight/bf-pid-reg-in-bf.md
  quote: "set d_min_roll = 20, d_min_pitch = 22"
  fix: "set d_min_roll = 20\nset d_min_pitch = 22\n# 2025.12: d_roll/d_pitch — базовый D, d_max_roll/d_max_pitch — пиковый"
  why: One setting per line; d_min_* removed in 2025.12 (renamed scheme d/d_max).
  source: https://github.com/betaflight/betaflight/blob/2025.12-maintenance/src/main/cli/settings.c
- severity: error
  file: content/betaflight/bf-pid-reg-in-bf.md
  quote: "увеличьте `tpa_rate` до 1.5"
  fix: "увеличьте `tpa_rate` (проценты, 0–100; дефолт 65) до 70–80"
  why: tpa_rate is uint8 0..TPA_MAX (100), percent.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/flight/pid.h
- severity: error
  file: content/betaflight/bf-pid-reg-in-bf.md
  quote: "Увеличить `dterm_lowpass2` до 100–120 Гц."
  fix: "Снизить `dterm_lpf2_static_hz` до 100–120 Гц."
  why: Wrong name, and the default is 150 Hz, so 100–120 is a reduction.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/flight/pid.h
- severity: error
  file: content/betaflight/bf-pid-reg-in-bf.md
  quote: "Включить `gyro_lowpass2` 250–300 Гц."
  fix: "Опустить `gyro_lpf2_static_hz` до 250–300 Гц."
  why: Setting name is gyro_lpf2_static_hz (on by default at 500 Hz).
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/sensors/gyro.h
- severity: imprecise
  file: content/betaflight/bf-pid-reg-in-bf.md
  quote: "(`airmode`)"
  fix: "(`feature AIRMODE` или режим AIR MODE)"
  why: There is no airmode setting; it is a feature/mode.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/settings.c
- severity: outdated
  file: content/betaflight/bf-pid-reg-in-bf.md
  quote: "с минимальным idle (`dshot_idle_value`)"
  fix: "с минимальным idle (`dshot_idle_value`; в 2025.12 — `motor_idle`)"
  why: dshot_idle_value removed in 2025.12.
  source: https://github.com/betaflight/betaflight/blob/2025.12-maintenance/src/main/fc/parameter_names.h
- severity: outdated
  file: content/betaflight/bf-pid-reg-in-bf.md
  quote: "(`d_min_*`, `d_max_gain`, `d_max_advance`)"
  fix: "(4.5: `d_min_*` — база, `d_*` — пик; 2025.12: `d_*` — база, `d_max_*` — пик; плюс `d_max_gain`, `d_max_advance`)"
  why: d_min_* exists only up to 4.5; 2025.12 uses d_max_*.
  source: https://github.com/betaflight/betaflight/blob/2025.12-maintenance/src/main/cli/settings.c
- severity: imprecise
  file: content/betaflight/bf-pid-reg-in-bf.md
  quote: "В BF 4.5+ работает в режиме `D` (снижает только D-term)."
  fix: "В BF 4.5+ по умолчанию `tpa_mode = D` (снижает только D-term); доступен и `PD`."
  why: lookupTableTpaMode = {PD, D}; D is only the default.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/settings.c

## bf-custom
verified: 18
- severity: error
  file: content/betaflight/bf-custom.md
  quote: "команда `version` в CLI показывает версию, таргет и `BUILD KEY`"
  fix: "команда `version` в CLI показывает версию и таргет, а `BUILD KEY` выводит `status`"
  why: BUILD KEY is printed only in cliStatus().
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/cli.c
- severity: error
  file: content/betaflight/bf-custom.md
  quote: "В `diff all` ключ тоже записывается."
  fix: "В `diff all` ключа нет — вывод `status` сохраняйте отдельно."
  why: buildKey is referenced only in the status printer; diff prints version header without it.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/cli.c
- severity: error
  file: content/betaflight/bf-custom.md
  quote: "вывод `version` (с BUILD KEY) должен совпадать с записью."
  fix: "вывод `version` и BUILD KEY из `status` должны совпадать с записью."
  why: Same; version has no BUILD KEY.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/cli.c
- severity: error
  file: content/betaflight/bf-custom.md
  quote: "`version` — сохранить вывод (там BUILD KEY)"
  fix: "`version` и `status` — сохранить вывод (BUILD KEY — в `status`)"
  why: Same.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/cli.c
- severity: error
  file: content/betaflight/bf-custom.md
  quote: "1. `version` показывает ожидаемые опции;"
  fix: "1. по BUILD KEY из `status` (`https://build.betaflight.com/api/builds/<key>/json`) — ожидаемые опции;"
  why: version does not list build options; the build API JSON does.
  source: https://github.com/betaflight/betaflight-configurator/blob/master/src/js/BuildApi.ts
- severity: error
  file: content/betaflight/bf-custom.md
  quote: "Вывод `version` с BUILD KEY сохранён после прошивки"
  fix: "Вывод `version` и `status` (BUILD KEY) сохранён после прошивки"
  why: Same.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/cli/cli.c

## bf-cli-automation
verified: 12
- severity: outdated
  file: content/betaflight/bf-cli-automation.md
  quote: "В Betaflight 4.5.x команда `exit noreboot` всё равно перезагружает контроллер (флаг `noreboot` заработал только в более новых версиях)."
  fix: "В Betaflight 4.5.0–4.5.3 команда `exit` всегда перезагружает контроллер (аргумент `noreboot` появился в 4.5.4 и 2025.12.x)."
  why: Tags 4.5.0–4.5.3 register exit with no args; 4.5.4/4.5.5 and 2025.12.1 have cliExitCmd with [noreboot].
  source: https://github.com/betaflight/betaflight/blob/4.5.4/src/main/cli/cli.c

## unverified
- bf-intro: "Для Android по-прежнему есть нативные приложения" — no source found for a current native Android app.
- bf-intro: "С 4.3 почти все платы — unified targets" — not traced to a primary source (unified targets started in 4.1).
- bf-blackbox: throughput "60–100 КБ/с → 16 МБ хватает на 3–4 минуты" — depends on field set; not measured.
- bf-modes-osd: HD canvas sizes "50×18/60×22" — not traced to a source.
- bf-cli: sample "Options" JSON contents — endpoint verified in configurator BuildApi.ts, payload contents not.
- bf-custom: ArduPilot build/hwdef claims — out of the Betaflight scope of this check.
- bf-rpm-filter / bf-pid: case-study numbers (viking10, 7" profiles) — user data, not verifiable.
- Note: the betaflight.com failsafe page could not be web-fetched (permission timeout); the same content was read from the docs repo clone. That page still contains the stale "3 seconds / 30 seconds" and "1.0s in 4.4" lines that the source code contradicts.
