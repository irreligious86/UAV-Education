# inav-link-px4
## inav-gps
verified: 32
- severity: outdated
  file: content/inav/inav-gps.md
  quote: "шесть режимов высоты возврата"
  fix: "пять режимов высоты возврата"
  why: AT_LEAST_LINEAR_DESCENT was removed in INAV 6; 7.0+/8.0 nav_rth_alt_mode table is CURRENT, EXTRA, FIXED, MAX, AT_LEAST (Navigation.md still says 6, but that is stale)
  source: https://github.com/iNavFlight/inav/blob/8.0.0/src/main/fc/settings.yaml
- severity: error
  file: content/inav/inav-gps.md
  quote: "(может быть смещена `nav_rth_home_offset_*` или заменена safehome)"
  fix: "(может быть заменена safehome)"
  why: nav_rth_home_offset_distance/direction exist only in docs/Navigation.md text; no such setting in settings.yaml of 5.0–9.x, CLI will reject it
  source: https://github.com/iNavFlight/inav/blob/master/src/main/fc/settings.yaml
- severity: error
  file: content/inav/inav-gps.md
  quote: "плавно снижается по пути так, чтобы прийти домой на `nav_rth_altitude`"
  fix: "плавно снижается по пути так, чтобы прийти домой на `nav_rth_home_altitude` (начало снижения — `nav_rth_linear_descent_start_distance`)"
  why: Settings.md: linear descent descends to nav_rth_home_altitude, start distance set by nav_rth_linear_descent_start_distance
  source: https://github.com/iNavFlight/inav/blob/master/docs/Settings.md#nav_rth_use_linear_descent
- severity: error
  file: content/inav/inav-gps.md
  quote: "`nav_rth_allow_landing` (OFF / ALWAYS / FS_ONLY)"
  fix: "`nav_rth_allow_landing` (NEVER / ALWAYS / FS_ONLY)"
  why: enum values are NEVER, ALWAYS, FS_ONLY; OFF is not a valid value
  source: https://github.com/iNavFlight/inav/blob/8.0.0/src/main/fc/settings.yaml
- severity: error
  file: content/inav/inav-gps.md
  quote: "обычно `FS_ONLY` или OFF с кружением"
  fix: "обычно `FS_ONLY` или NEVER с кружением"
  why: same enum — OFF does not exist for nav_rth_allow_landing
  source: https://github.com/iNavFlight/inav/blob/8.0.0/src/main/fc/settings.yaml
- severity: imprecise
  file: content/inav/inav-gps.md
  quote: "Для крыла есть оценка позиции без GPS по компасу и барометру (`inav_allow_gps_fix_estimation`)"
  fix: "Для крыла (INAV 8.0+) есть оценка позиции без GPS по компасу и барометру (`inav_allow_gps_fix_estimation`)"
  why: setting absent in 7.0.0 and 7.1.0 settings.yaml, first appears in 8.0.0; module targets 7.0+
  source: https://github.com/iNavFlight/inav/blob/8.0.0/src/main/fc/settings.yaml

## inav-intro
verified: 18
- severity: imprecise
  file: content/inav/inav-intro.md
  quote: "MULTIROTOR, AIRPLANE, TRICOPTER, ROVER, BOAT"
  fix: "MULTIROTOR, AIRPLANE, TRICOPTER (значения HELICOPTER, ROVER, BOAT есть в списке, но реализованы не полностью)"
  why: Settings.md: allowed values include HELICOPTER; "Currently only MULTIROTOR, AIRPLANE and TRICOPTER types are implemented"
  source: https://github.com/iNavFlight/inav/blob/master/docs/Settings.md#platform_type

## inav-ipf
verified: 20
- severity: imprecise
  file: content/inav/inav-ipf.md
  quote: "Типы операндов: 0 — значение, 1 — RC-канал, 2 — параметр полёта, 3 — режим, 4 — логическое условие, 5 — GVAR."
  fix: "Типы операндов: 0 — значение, 1 — RC-канал, 2 — параметр полёта, 3 — режим, 4 — логическое условие, 5 — GVAR, 6 — Programming PID, 7 — точки миссии."
  why: logic_condition.h enum: ..., GVAR=5, PID=6, WAYPOINTS=7 (the module itself relies on PID and waypoint operands)
  source: https://github.com/iNavFlight/inav/blob/8.0.0/src/main/programming/logic_condition.h
- severity: imprecise
  file: content/inav/inav-ipf.md
  quote: "Число правил ограничено прошивкой и памятью F4 (на F4 часть функций вырезана)."
  fix: "Число правил фиксировано прошивкой: 64 логических условия, 8 GVAR, 4 Programming PID — одинаково на F4 и H7."
  why: MAX_LOGIC_CONDITIONS 64, MAX_GLOBAL_VARIABLES 8, MAX_PROGRAMMING_PID_COUNT 4 are compile-time constants, not per-MCU
  source: https://github.com/iNavFlight/inav/blob/8.0.0/src/main/programming/logic_condition.h

## inav-missions
verified: 22
- severity: error
  file: content/inav/inav-missions.md
  quote: "нет MAVLink-диалога загрузки — точки пишутся в EEPROM напрямую"
  fix: "загрузка через MSP/CLI, MAVLink-протокол миссий (MISSION_COUNT/MISSION_ITEM) поддерживается упрощённо"
  why: INAV telemetry/mavlink.c implements MISSION_COUNT, MISSION_ITEM, MISSION_REQUEST_LIST, MISSION_CLEAR_ALL handlers
  source: https://github.com/iNavFlight/inav/blob/8.0.0/src/main/telemetry/mavlink.c
- severity: imprecise
  file: content/inav/inav-missions.md
  quote: "`p1`: для WAYPOINT — скорость к точке (см/с)"
  fix: "`p1`: для WAYPOINT — скорость к точке (см/с; только мультиротор и только если 50 < p1 < `nav_auto_speed`)"
  why: Navigation.md: WP speed "is taken into account only for multicopters and when > 50 and < nav_auto_speed"
  source: https://github.com/iNavFlight/inav/blob/master/docs/Navigation.md
- severity: imprecise
  file: content/inav/inav-missions.md
  quote: "WAYPOINT ×8 с `p1` = 500 (5 м/с)"
  fix: "WAYPOINT ×8 с `p1` = 0 (скорость `nav_auto_speed` = 5 м/с)"
  why: p1=500 equals default nav_auto_speed=500, so it is ignored (must be < nav_auto_speed)
  source: https://github.com/iNavFlight/inav/blob/master/docs/Navigation.md

## inav-wing
verified: 34
- severity: error
  file: content/inav/inav-wing.md
  quote: "Результат сохраняется при дизарме."
  fix: "Результат не сохраняется автоматически: после посадки дизарм и стик-команда сохранения (или `save` в CLI)."
  why: Autotune doc: "AUTOTUNE mode doesn't automatically save parameters to EEPROM. You need to disarm and issue a stick command"; no autosave in fc_core.c/pid_autotune.c
  source: https://github.com/iNavFlight/inav/blob/master/docs/Autotune%20-%20fixedwing.md
- severity: error
  file: content/inav/inav-wing.md
  quote: "сохранение дизармом"
  fix: "сохранение стик-командой после дизарма"
  why: same — disarm alone does not save autotune results
  source: https://github.com/iNavFlight/inav/blob/master/docs/Autotune%20-%20fixedwing.md
- severity: error
  file: content/inav/inav-wing.md
  quote: "Дизарм на земле — сохранение."
  fix: "Дизарм на земле, затем стик-команда сохранения."
  why: same
  source: https://github.com/iNavFlight/inav/blob/master/docs/Autotune%20-%20fixedwing.md
- severity: imprecise
  file: content/inav/inav-wing.md
  quote: "по скорости `nav_fw_launch_velocity` (300 см/с — для резинки/катапульты)"
  fix: "по скорости `nav_fw_launch_velocity` (300 см/с — для запуска «махом»/swing и по GPS-скорости; резинка/бросок детектируются по ускорению)"
  why: navigation_fw_launch.c: accel threshold → isBungeeLaunched; launch_velocity_thresh → isSwingLaunched / isForwardLaunched (GPS); Settings.md: "swing-launch detection"
  source: https://github.com/iNavFlight/inav/blob/8.0.0/src/main/navigation/navigation_fw_launch.c
- severity: imprecise
  file: content/inav/inav-wing.md
  quote: "INAV 7+ умеет оценку ветра и посадочные паттерны"
  fix: "INAV 7.1+ умеет оценку ветра и посадочные паттерны"
  why: docs/Fixed Wing Landing.md and nav_fw_land_approach settings absent in 7.0.0, present from 7.1.0
  source: https://github.com/iNavFlight/inav/blob/7.1.0/docs/Fixed%20Wing%20Landing.md
- severity: imprecise
  file: content/inav/inav-wing.md
  quote: "(при DROP/LAND без датчиков высоты)"
  fix: "(при LAND без датчиков высоты; DROP просто выключает мотор)"
  why: Failsafe.md: failsafe_throttle used by LAND/SET-THR when altitude sensors unavailable; DROP does not use it
  source: https://github.com/iNavFlight/inav/blob/master/docs/Failsafe.md

## link-elrs
verified: 28
- severity: error
  file: content/link/link-elrs.md
  quote: "D250, D500 — каждый пакет отправляется дважды"
  fix: "D250, D500 — FLRC 1000 Гц с повтором: в D500 каждый пакет отправляется дважды, в D250 — четыре раза"
  why: ELRS common.cpp air-rate table: RATE_FLRC_2G4_500HZ_DVDA numOfSends=2, RATE_FLRC_2G4_250HZ_DVDA numOfSends=4
  source: https://github.com/ExpressLRS/ExpressLRS/blob/master/src/src/common.cpp
- severity: error
  file: content/link/link-elrs.md
  quote: "Wide даёт 8 каналов по 64/128 позиций + 4 полных"
  fix: "Wide даёт 4 полных канала, 1-битный ARM (AUX1) и 7 каналов AUX2–AUX8 по 64/128 позиций"
  why: ELRS switch-config: Wide = ch1-4 10-bit, AUX1 1-bit, AUX2-AUX8 (7 channels) 6/7-bit round-robin
  source: https://www.expresslrs.org/software/switch-config/
- severity: imprecise
  file: content/link/link-elrs.md
  quote: "все каналы в 10 бит для серв крыла/гимбала"
  fix: "8, 12 или 16 каналов в 10 бит (8ch, 12ch Mixed, 16ch Rate/2) для серв крыла/гимбала"
  why: only 16ch Rate/2 has all channels 10-bit (at half rate); 8ch/12ch keep ch5 as 1-bit arm
  source: https://www.expresslrs.org/software/switch-config/
- severity: error
  file: content/link/link-elrs.md
  quote: "airport/MAVLink-режим в 3.4+"
  fix: "airport/MAVLink-режим, MAVLink — с 3.5.0"
  why: Lua how-to: MAVLink link mode and MAVLink receiver protocol "Introduced in 3.5.0"
  source: https://www.expresslrs.org/quick-start/transmitters/lua-howto/
- severity: error
  file: content/link/link-elrs.md
  quote: "(для long range — 1:16…1:32 или `Std`/`Race` пресеты 3.x)"
  fix: "(для long range — 1:16…1:32 или `Std`; `Race` отключает телеметрию в арме и для long range не подходит)"
  why: Lua how-to: "Race is the same as Std, but will disable telemetry and sync while Armed"
  source: https://www.expresslrs.org/quick-start/transmitters/lua-howto/

## link-protocols
verified: 27
- severity: error
  file: content/link/link-protocols.md
  quote: "(`sbus_inversion`, Betaflight обрабатывает автоматически)"
  fix: "(Betaflight читает флаг автоматически)"
  why: no setting sbus_inversion exists in Betaflight (inversion is serialrx_inverted, unrelated to the failsafe flag)
  source: https://github.com/betaflight/betaflight/blob/master/src/main/cli/settings.c

## link-vtx
verified: 20
- severity: error
  file: content/link/link-vtx.md
  quote: "Удвоение мощности = +3 дБ = ×1.19 по дальности"
  fix: "Удвоение мощности = +3 дБ = ×1.41 (√2) по дальности"
  why: free-space range scales as 10^(dB/20); +3 dB → ×1.41 (module itself uses 15 dB → ×5.6, consistent only with 20·log)
  source: https://en.wikipedia.org/wiki/Free-space_path_loss
- severity: error
  file: content/link/link-vtx.md
  quote: "но у части VTX нужен `vtx_smartaudio_stopbits`/подтяжка; версии ломают совместимость — в CLI `vtx` показывает, что VTX ответил."
  fix: "но у части VTX нужна подтяжка (Betaflight всегда шлёт 2 стоп-бита); версии ломают совместимость — в CLI `vtx_info` показывает, что VTX ответил."
  why: no vtx_smartaudio_stopbits setting (driver hardcodes SERIAL_STOPBITS_2); CLI `vtx` is "vtx channels on switch", device info is `vtx_info`
  source: https://github.com/betaflight/betaflight/blob/master/src/main/cli/cli.c
- severity: error
  file: content/link/link-vtx.md
  quote: "Проверка: CLI `vtx` → строки `vtx_band/channel/power/freq` и статус устройства; `vtxtable` → таблица."
  fix: "Проверка: CLI `get vtx` → `vtx_band/channel/power/freq`; `vtx_info` → что сообщило устройство; `vtxtable` → таблица."
  why: `vtx` CLI command configures band/channel per AUX switch range; settings via `get vtx`, device report via `vtx_info`
  source: https://github.com/betaflight/betaflight/blob/master/src/main/cli/cli.c
- severity: error
  file: content/link/link-vtx.md
  quote: "CLI `vtx` — есть ли ответ устройства"
  fix: "CLI `vtx_info` — есть ли ответ устройства"
  why: same
  source: https://github.com/betaflight/betaflight/blob/master/src/main/cli/cli.c
- severity: imprecise
  file: content/link/link-vtx.md
  quote: "разнос 74 МГц между любыми двумя"
  fix: "разнос не меньше 74 МГц между любыми двумя"
  why: R1/R3/R5/R7 = 5658/5732/5806/5880; only adjacent pairs are 74 MHz apart (R1–R7 is 222)
  source: https://github.com/betaflight/betaflight/blob/master/src/main/cli/cli.c

## px4-architecture
verified: 24
- severity: imprecise
  file: content/px4/px4-architecture.md
  quote: "Драйверы IMU опрашивают датчик (~1 кГц), интегрируют и публикуют (~250 Гц)."
  fix: "Драйверы IMU читают FIFO датчика (килогерцы, у современных IMU до 8 кГц); гироскоп после фильтров публикуется в `vehicle_angular_velocity` на `IMU_GYRO_RATEMAX` (400 Гц), интегрированные данные — в `vehicle_imu` на `IMU_INTEG_RATE` (200 Гц)."
  why: IMU_INTEG_RATE default 200 Hz, IMU_GYRO_RATEMAX default 400 Hz in PX4 sensors params
  source: https://docs.px4.io/main/en/advanced_config/parameter_reference.html
- severity: error
  file: content/px4/px4-architecture.md
  quote: "Тяжёлые — EKF2, logger, mavlink — отдельные задачи."
  fix: "Отдельные задачи — logger, mavlink; EKF2 тоже работает в work queue (ScheduledWorkItem)."
  why: class EKF2 final : public ModuleParams, public px4::ScheduledWorkItem — EKF2 is a work-queue item, not a task
  source: https://github.com/PX4/PX4-Autopilot/blob/main/src/modules/ekf2/EKF2.hpp
- severity: outdated
  file: content/px4/px4-architecture.md
  quote: "Открой `msg/VehicleCommand.msg`"
  fix: "Открой `msg/VehicleCommand.msg` (с PX4 1.16 — `msg/versioned/VehicleCommand.msg`)"
  why: since v1.16 versioned messages live in msg/versioned/ (msg/VehicleCommand.msg 404 at v1.16.0)
  source: https://github.com/PX4/PX4-Autopilot/tree/main/msg/versioned

## px4-companion-jetson
verified: 16
- severity: error
  file: content/px4/px4-companion-jetson.md
  quote: "Для MAVLink на TELEM2 (так настроено по умолчанию)"
  fix: "Для MAVLink на TELEM2 (по умолчанию MAVLink на TELEM2 выключен — включить вручную)"
  why: mavlink/module.yaml: MAV_1_CONFIG default "" with comment "Telem2 Port (Companion Link). Disabled by default"
  source: https://github.com/PX4/PX4-Autopilot/blob/main/src/modules/mavlink/module.yaml
- severity: imprecise
  file: content/px4/px4-companion-jetson.md
  quote: "прямое подключение по USB дает полный поток данных MAVLink без потери пакетов"
  fix: "USB удобен на стенде, но в полёте ненадёжен (см. раздел «Физическое подключение»)"
  why: contradicts the module's own theory section; PX4 companion docs recommend TELEM2/Ethernet for flight links
  source: https://docs.px4.io/main/en/companion_computer/pixhawk_companion.html

## px4-control
verified: 36
- severity: imprecise
  file: content/px4/px4-control.md
  quote: "eRPM по DShot (`DSHOT_TEL_CFG`)"
  fix: "eRPM по DShot (bidirectional DShot или телеметрия ESC по UART — `DSHOT_TEL_CFG`)"
  why: DSHOT_TEL_CFG is the serial port for ESC telemetry wire, not a bidirectional-DShot switch
  source: https://github.com/PX4/PX4-Autopilot/blob/main/src/drivers/dshot/module.yaml
- severity: imprecise
  file: content/px4/px4-control.md
  quote: "(битмаска; требует eRPM от ESC по DShot-телеметрии)"
  fix: "(битмаска: бит 0 — по ESC RPM, бит 1 — по бортовому FFT `IMU_GYRO_FFT_EN`)"
  why: IMU_GYRO_DNF_EN bit0 ESC RPM, bit1 FFT — eRPM not mandatory
  source: https://github.com/PX4/PX4-Autopilot/blob/main/src/modules/sensors/vehicle_angular_velocity/imu_gyro_parameters.yaml

## px4-intro
verified: 30
- severity: error
  file: content/px4/px4-intro.md
  quote: "протокол (DShot `DSHOT_CONFIG`/PWM)"
  fix: "протокол (DShot/PWM — по группам таймеров в Actuators, `PWM_MAIN_TIMx`)"
  why: DSHOT_CONFIG was removed with dynamic control allocation; absent in v1.14.0 dshot module.yaml and in main
  source: https://github.com/PX4/PX4-Autopilot/blob/v1.14.0/src/drivers/dshot/module.yaml
- severity: outdated
  file: content/px4/px4-intro.md
  quote: "В ArduPilot — через MAVLink/DDS-мост."
  fix: "В ArduPilot (4.5+) — тоже нативный DDS-клиент (AP_DDS), но с меньшим набором топиков."
  why: ArduPilot ships native micro-XRCE-DDS (AP_DDS) for ROS 2
  source: https://ardupilot.org/dev/docs/ros2.html

## px4-ros2
verified: 22
- severity: outdated
  file: content/px4/px4-ros2.md
  quote: "`ros2 topic echo /fmu/out/vehicle_local_position`"
  fix: "`ros2 topic echo /fmu/out/vehicle_local_position` (с PX4 1.17 — `/fmu/out/vehicle_local_position_v1`)"
  why: VehicleLocalPosition MESSAGE_VERSION=1 in v1.17.0; uxrce_dds_client appends "_v%u" to topic names when version != 0
  source: https://github.com/PX4/PX4-Autopilot/blob/main/src/modules/uxrce_dds_client/utilities.hpp

## unverified
- inav-intro: list of arming-blocker names (`NAV`, `ROLL/PITCH`, `WP MISSION`, ...) — they match neither INAV OSD strings ("NAVIGATION SAFETY"/"AIRCRAFT IS NOT LEVEL"...) nor clearly the CLI `status` flag names; not resolved.
- inav-gps / inav-intro: "barometer mandatory for multirotor" — INAV 7.0 had inav_use_gps_no_baro, removed in 8.0; current baro-less behaviour not confirmed.
- link-elrs: "Dynamic Power ... требует телеметрии (ratio ≥ 1:64)" — telemetry needed is plausible, the ≥1:64 threshold not found in ELRS docs.
- link-elrs: "RQly — из последних 100 пакетов"; "F1000 недоступен на SPI-приёмнике" — not confirmed in docs.
- link-vtx: Betaflight docs legal-warning wording and "Tramp/RTC6705 only CUSTOM" — betaflight.com fetch blocked (permission timeout: https://betaflight.com/docs/wiki/guides/current/VTX-Tables); source shows Tramp sends frequency, consistent but not confirmed in docs.
- link-vtx: digital-system simultaneous-channel limits (Walksnail/HDZero 8, DJI fewer).
- px4-companion-jetson: `/dev/ttyTHS1` on pins 8/10 of Orin Nano and `nvgetty` on JetPack 5/6 (on Orin the 40-pin UART is often reported as ttyTHS0, console on ttyTCU0) — no NVIDIA primary source checked.
- px4-ros2: in PX4 main (post-1.17) VehicleCommand MESSAGE_VERSION=1, so `/fmu/in/vehicle_command` becomes `/fmu/in/vehicle_command_v1`; not yet in a release (v1.17.0 is v0) — heads-up only.
- px4-intro: `EKF2_GPS_CHECK` is renamed to `GNSS_CHECK` in PX4 main (param_translation.cpp, 2026-09-29); still valid in released 1.17 — heads-up only.
