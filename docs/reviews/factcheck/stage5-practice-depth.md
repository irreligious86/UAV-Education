# stage5-practice-depth

Basis: ArduPilot source master @2a54162 (2026-11-08): ArduCopter Parameters.cpp, mode_rtl.cpp, mode_guided.cpp, events.cpp, ekf_check.cpp, Log.cpp, Attitude.cpp; ArduPlane/Log.cpp (CTUN); libraries AC_AutoTune_Multi.cpp, AP_Logger.h (LogErrorSubsystem/LogErrorCode), AP_Arming.cpp (ARMING_SKIPCHK, ARMING_RUDDER), AP_InertialSensor/BatchSampler.cpp, AP_NavEKF_Source.cpp (EK3_SRC1_YAW), RC_Channel.h (option 17), SITL/SITL.cpp (SIM_ENGINE_FAIL/MUL), AP_Motors, GCS_MAVLink GCS.cpp, GCS_Common.cpp (arm COMMAND_ACK), GCS_MAVLink_Parameters.cpp (default stream rates), Tools/autotest/default_params. AC_AutoTune_Multi.cpp on branches Copter-4.5, ArduPilot-4.6, ArduPilot-4.7 (raw.githubusercontent.com). Betaflight master @a12049c (2025.12 line): cli/settings.c, cli/cli.c, pg/rpm_filter.c, flight/pid.c, flight/mixer.c, platform/SIMULATOR. pymavlink (local install): heartbeat_send/param_set_send signatures, MAV_COMP_ID_ONBOARD_COMPUTER = 191, MAV_RESULT_FAILED = 4, DFReader. MAVLink common.xml MAV_RESULT. All four added Python blocks compiled locally; the data-python Welch block was run and prints "peak at 210 Hz". Worked numbers recomputed: stall speed 8.53 m/s, 1/√cos45°, coax T/W, T/W and hover-time chain (f-components-choice), T/W 4.14 and √(1/T/W), R_int, ζ from overshoot (0.591/0.404), ωₙ 167 rad/s, FSPL 100.19 dB and 12.6 km, DShot 1046 → 0x82C6 (CRC 6), CRSF length 0x18, I²C 85 clocks × 2.5 µs, Δp 0.118 hPa/m, RPN 162/81, precision/recall, gyro drift 30°/min.

## aero-wing
verified: 12

## ap-companion
verified: 9

## ap-ekf
verified: 8
- severity: imprecise
  file: content/ardupilot/ap-ekf.md
  quote: "В логе `ERR` с подсистемой GPS (код глитча — 11 по таблице модуля «Логи»)"
  fix: "В логе `ERR` с подсистемой GPS (`Subsys` 11, `ECode` 2 — `GPS_GLITCH`; после восстановления — `ECode` 0)"
  why: 11 is the GPS subsystem number. The glitch itself is ECode 2 (GPS_GLITCH), and ECode 0 (ERROR_RESOLVED) is logged when the glitch clears. Calling 11 the "glitch code" mixes up the Subsys and ECode fields.
  source: libraries/AP_Logger/AP_Logger.h and ArduCopter/events.cpp@2a54162
- severity: imprecise
  file: content/ardupilot/ap-ekf.md
  quote: "(1 — посадка, 2 — AltHold, 3 — посадка даже в STABILIZE)"
  fix: "(1 — посадка, 2 — AltHold, оба только если текущий режим требует позиции; 3 — посадка из любого режима, даже из STABILIZE)"
  why: The parameter description limits values 1 and 2 to the case where the current mode requires position. In STABILIZE or ALT_HOLD those values do not switch modes, and only value 3 lands from all modes.
  source: ArduCopter/Parameters.cpp@2a54162 (FS_EKF_ACTION @Values)

## ap-heavy
verified: 9

## ap-intro
verified: 9

## ap-logs
verified: 10

## ap-quadplane
verified: 7

## ap-sitl
verified: 9
- severity: error
  file: content/ardupilot/ap-sitl.md
  quote: "Скрипт печатает растущую высоту и выходит на 9.5 м."
  fix: "Скрипт печатает растущую высоту и выходит на 9.5 м — но только если `GLOBAL_POSITION_INT` вообще идёт на этот порт. У Copter потоки на SERIAL1 по умолчанию выключены (`SR1_POSITION = 0`, в 4.7 — `MAV2_POSITION`), поэтому перед циклом запроси сообщение через `MAV_CMD_SET_MESSAGE_INTERVAL`, иначе `recv_match` будет ждать вечно."
  why: Copter's default rate is 0 for every stream group, and the rates are set per MAVLink channel. MAVProxy requests streams only on its own SERIAL0 link, and the SITL default params set no SR1/MAV2 rates. A client on 5762 therefore gets heartbeats but no GLOBAL_POSITION_INT until it asks for it.
  source: libraries/GCS_MAVLink/GCS_MAVLink_Parameters.cpp@2a54162 (APM_BUILD_COPTER_OR_HELI defaults 0), Tools/autotest/default_params/copter.parm@2a54162

## ap-tuning
verified: 9
- severity: outdated
  file: content/ardupilot/ap-tuning.md
  quote: "(0.05–0.10, по умолчанию 0.1)"
  fix: "(0.05–0.10, по умолчанию 0.075; в 4.5 и раньше — 0.1)"
  why: The AGGR default is 0.1 in Copter-4.5 and 0.075 on the ArduPilot-4.6, ArduPilot-4.7 and master branches. The range is unchanged.
  source: libraries/AC_AutoTune/AC_AutoTune_Multi.cpp@2a54162; https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.5/libraries/AC_AutoTune/AC_AutoTune_Multi.cpp

## bf-cli-automation
verified: 6

## bf-custom
verified: 6

## comp-esp32
verified: 12

## comp-intro
verified: 7
- severity: error
  file: content/companion/comp-intro.md
  quote: "В файле одна строка на каждое сообщение позиции. Чтобы было ровно раз в секунду, либо запроси интервал `GLOBAL_POSITION_INT` 1 000 000 мкс, либо прореживай запись в коде."
  fix: "На порту 5762 (SERIAL1) у Copter потоки по умолчанию выключены (`SR1_POSITION = 0`, в 4.7 — `MAV2_POSITION`), поэтому без запроса файл останется пустым. Сначала запроси интервал `GLOBAL_POSITION_INT` 1 000 000 мкс (`MAV_CMD_SET_MESSAGE_INTERVAL`) — тогда в файле будет одна строка в секунду."
  why: The observer script never requests a stream. Copter's default stream rates are 0 on every channel, and MAVProxy's stream request only affects SERIAL0. On tcp:5762 the script would therefore receive heartbeats but no GLOBAL_POSITION_INT, and it would write nothing.
  source: libraries/GCS_MAVLink/GCS_MAVLink_Parameters.cpp@2a54162; libraries/GCS_MAVLink/GCS.cpp@2a54162 (MAV1..MAVn per-channel groups)

## comp-mavlink
verified: 11
- severity: error
  file: content/companion/comp-mavlink.md
  quote: "Если выходит ~4 Гц, команда интервала не дошла, и работает частота по умолчанию из `SRx_EXTRA1`."
  fix: "Если `ATTITUDE` не приходит вовсе, команда интервала не дошла: на порту 5762 у Copter частота по умолчанию (`SR1_EXTRA1`, в 4.7 — `MAV2_EXTRA1`) равна 0. Около 4 Гц — это частота, которую MAVProxy сам запрашивает на своём порту 5760."
  why: Copter's default EXTRA1 rate is 0, so a lost interval command on 5762 produces no ATTITUDE at all rather than about 4 Hz. The 4 Hz figure is MAVProxy's default stream request on SERIAL0. ArduPilot 4.7 also replaced SRn_* with the per-channel MAVn_* groups, where MAV1 is the former SR0.
  source: libraries/GCS_MAVLink/GCS_MAVLink_Parameters.cpp@2a54162; libraries/GCS_MAVLink/GCS.cpp@2a54162
- severity: imprecise
  file: content/companion/comp-mavlink.md
  quote: "раздели их число на разницу `time_boot_ms` первого и последнего"
  fix: "раздели число интервалов (49) на разницу `time_boot_ms` первого и последнего (в секундах)"
  why: 50 timestamps span 49 intervals. Dividing 50 by the span overstates a true 10 Hz as about 10.2 Hz, a systematic 2 % error in a step meant to measure the rate.
  source: arithmetic

## emb-protocols
verified: 8

## eng-systems
verified: 4

## fw-reading
verified: 7

## per-cv
verified: 4

## el-measure
verified: 8

## el-peripherals
verified: 6

## rf-link-budget
verified: 9

## est-attitude
verified: 5

## est-gnss
verified: 8

## diag-troubleshooting
verified: 5

## eng-method-101
verified: 2

## f-components-choice
verified: 10

## f-electricity-101
verified: 6

## f-fc-sensors
verified: 4

## f-motors-esc
verified: 4

## f-physics
verified: 6

## f-regulations
verified: 0

## ops-case-studies
verified: 0

## ops-field
verified: 0

## link-protocols
verified: 7

## px4-architecture
verified: 5

## px4-control
verified: 5

## px4-intro
verified: 4

## ros2-ardupilot
verified: 3

## ctl-theory
verified: 6

## data-python
verified: 6

## tools-overview
verified: 3
