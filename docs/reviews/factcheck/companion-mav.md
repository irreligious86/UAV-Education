# companion-mav
## comp-intro
verified: 14
- severity: imprecise
  file: content/companion/comp-intro.md
  quote: "`mavlink-router` (C, systemd-сервис"
  fix: "`mavlink-router` (C++, systemd-сервис"
  why: mavlink-router is written in C++ (sources are .cpp; README requires C and C++ std libs); mav-routing.md already says C++.
  source: https://github.com/mavlink-router/mavlink-router

## comp-mavlink
verified: 34
- severity: imprecise
  file: content/companion/comp-mavlink.md
  quote: "подпись — HMAC-SHA256 по секретному ключу + timestamp"
  fix: "подпись — первые 48 бит SHA-256 от (секретный ключ + заголовок + payload + CRC + link_id + timestamp), не HMAC"
  why: MAVLink 2 signature is sha256_48(secret_key + header + payload + CRC + link-ID + timestamp), not HMAC.
  source: https://mavlink.io/en/guide/message_signing.html
- severity: imprecise
  file: content/companion/comp-mavlink.md
  quote: "`MAV_SIGNING` в ArduPilot/QGC"
  fix: "ключ задаётся в Mission Planner/QGC и передаётся автопилоту сообщением `SETUP_SIGNING`"
  why: ArduPilot has no MAV_SIGNING parameter; the key is set via SETUP_SIGNING from the GCS (only MAVn_OPTIONS bit 0 in 4.7+ touches signing).
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/GCS_MAVLink/GCS_MAVLink_Parameters.cpp
- severity: imprecise
  file: content/companion/comp-mavlink.md
  quote: "целые упакованы «по байтам» (`MAV_PARAM_TYPE`)"
  fix: "целые ArduPilot передаёт приведением к float (C-cast), PX4 — побайтно; тип значения — в `param_type` (`MAV_PARAM_TYPE`)"
  why: ArduPilot uses C-cast encoding (advertises PARAM_FLOAT = PARAM_ENCODE_C_CAST), bytewise is PX4; mav-services.md says this correctly.
  source: https://mavlink.io/en/services/parameter.html

## mav-protocol
verified: 32
- severity: imprecise
  file: content/companion/mav-protocol.md
  quote: "В ArduPilot параметр `MAVn_OPTIONS` (в версиях до 4.7 — по-другому, см. описание параметров) управляет, принимать ли неподписанные пакеты на конкретном канале."
  fix: "В ArduPilot 4.7+ бит 0 параметра `MAVn_OPTIONS` («Accept unsigned MAVLink2 messages») разрешает неподписанные пакеты на конкретном канале; в 4.6 и раньше такой настройки нет — при включённой подписи неподписанные пакеты принимаются только на канале 0 (USB) и для `RADIO_STATUS`."
  why: 4.6 GCS_Signing has no per-channel option (accepts unsigned only on MAVLINK_COMM_0 plus RADIO_STATUS/RADIO); the option appears in master as MAVn_OPTIONS bit 0.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/GCS_MAVLink/GCS_Signing.cpp

## mav-services
verified: 38
- severity: imprecise
  file: content/companion/mav-services.md
  quote: "`COMMAND_INT` (75): то же, но параметры 5–6 — целые `x`, `y`"
  fix: "`COMMAND_INT` (75): та же адресация и param1–4, но без поля `confirmation` (вместо него `current`/`autocontinue`, не используются); параметры 5–6 — целые `x`, `y`"
  why: COMMAND_INT has no confirmation field, so the confirmation++ retry rule below applies to COMMAND_LONG only.
  source: https://mavlink.io/en/messages/common.html#COMMAND_INT
- severity: outdated
  file: content/companion/mav-services.md
  quote: "`MISSION_SET_CURRENT` или `MAV_CMD_DO_SET_MISSION_CURRENT` — перейти"
  fix: "`MAV_CMD_DO_SET_MISSION_CURRENT` (224) — перейти (сообщение `MISSION_SET_CURRENT` (41) устарело с 2022 г. и заменено этой командой)"
  why: MISSION_SET_CURRENT is marked superseded since 2022-08 by MAV_CMD_DO_SET_MISSION_CURRENT.
  source: https://mavlink.io/en/messages/common.html#MISSION_SET_CURRENT

## mav-routing
verified: 26, no findings

## mav-component
verified: 30
- severity: error
  file: content/companion/mav-component.md
  quote: "ArduPilot пишет полученные `NAMED_VALUE_FLOAT` в лог (`NVF`)"
  fix: "ArduPilot пишет полученные `NAMED_VALUE_FLOAT` в лог (`NVAL`)"
  why: GCS_MAVLINK::handle_named_value writes log message "NVAL" (TimeUS,TimeBootMS,Name,Value,SSys,SCom), both 4.6 and master.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/GCS_MAVLink/GCS_Common.cpp
- severity: imprecise
  file: content/companion/mav-component.md
  quote: "`signal_quality` (0 — неизвестно, 1 — плохо … 100 — отлично)"
  fix: "`signal_quality` (0 — неизвестно, 1 — сигнал недостоверен … 100 — отлично)"
  why: common.xml: 0 = unknown/unset, 1 = invalid signal, 100 = perfect signal.
  source: https://mavlink.io/en/messages/common.html#DISTANCE_SENSOR
- severity: imprecise
  file: content/companion/mav-component.md
  quote: "реже 5 Гц автопилот может посчитать датчик отвалившимся"
  fix: "таймаут MAVLink-дальномера в ArduPilot — 500 мс: если пакеты приходят реже ~2 Гц или с пропусками дольше 0.5 с, датчик считается отвалившимся"
  why: AP_RANGEFINDER_MAVLINK_TIMEOUT_MS = 500, so the threshold is 2 Hz, not 5 Hz.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_RangeFinder/AP_RangeFinder_MAVLink.h

## mav-sdk
verified: 16, no findings

## comp-esp32
verified: 18
- severity: error
  file: content/companion/comp-esp32.md
  quote: "`DISTANCE_SENSOR` (123)"
  fix: "`DISTANCE_SENSOR` (132)"
  why: DISTANCE_SENSOR message id is 132 (mav-component.md uses 132 correctly).
  source: https://mavlink.io/en/messages/common.html#DISTANCE_SENSOR
- severity: error
  file: content/companion/comp-esp32.md
  quote: "(видны в GCS и в логе `NVF`)"
  fix: "(видны в GCS и в логе `NVAL`)"
  why: ArduPilot logs received NAMED_VALUE_FLOAT as NVAL; there is no NVF message.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/GCS_MAVLink/GCS_Common.cpp
- severity: imprecise
  file: content/companion/comp-esp32.md
  quote: "component_id 25–100 по типу"
  fix: "свой component_id: `MAV_COMP_ID_PERIPHERAL` (158) или из диапазона USER1–USER75 (25–99)"
  why: MAV_COMP_ID_USER1..USER75 = 25..99; 100 is MAV_COMP_ID_CAMERA, and the range is not assigned "by type".
  source: https://mavlink.io/en/messages/minimal.html#MAV_COMPONENT

## comp-raspberry
verified: 24
- severity: error
  file: content/companion/comp-raspberry.md
  quote: "Address = 192.168.1.20      # laptop with QGC"
  fix: "Address = 192.168.1.20"
  why: mavlink-router config does not allow end-of-line comments, so the comment text becomes part of the value; comments must go on their own line.
  source: https://github.com/mavlink-router/mavlink-router/blob/master/examples/config.sample
- severity: error
  file: content/companion/comp-raspberry.md
  quote: "Port = 14551                # local scripts connect here (udpin)"
  fix: "Port = 14551"
  why: Same rule: no end-of-line comments in mavlink-router config. The hint is also wrong, because a Server endpoint needs udpout clients.
  source: https://github.com/mavlink-router/mavlink-router/blob/master/examples/config.sample
- severity: error
  file: content/companion/comp-raspberry.md
  quote: "скрипты — `mavutil.mavlink_connection(\"udpin:127.0.0.1:14551\")`"
  fix: "скрипты — `mavutil.mavlink_connection(\"udpout:127.0.0.1:14551\")` (endpoint в режиме Server слушает порт и отвечает тому, кто прислал первый пакет)"
  why: With Mode=Server the router binds 14551 and replies only after the first packet arrives, so the client must use udpout. udpin would try to bind the same port. (mav-component.md uses udpout correctly.)
  source: https://github.com/mavlink-router/mavlink-router#endpoints
- severity: error
  file: content/companion/comp-raspberry.md
  quote: "локальные скрипты подключаются к `udpin:127.0.0.1:14551`"
  fix: "локальные скрипты подключаются к `udpout:127.0.0.1:14551`"
  why: Same Server-mode semantics as above: the client must send first (udpout).
  source: https://github.com/mavlink-router/mavlink-router#endpoints

## emb-basics
verified: 26
- severity: error
  file: content/companion/emb-basics.md
  quote: "одинаковые — по времени (tick 1 кГц на ESP-IDF)"
  fix: "одинаковые — по времени (tick по умолчанию 100 Гц в ESP-IDF, `CONFIG_FREERTOS_HZ`; в Arduino-ESP32 — 1000 Гц)"
  why: ESP-IDF Kconfig FREERTOS_HZ defaults to 100 (range 1–1000).
  source: https://github.com/espressif/esp-idf/blob/master/components/freertos/Kconfig
- severity: error
  file: content/companion/emb-basics.md
  quote: "FreeRTOS (ESP32, также основа PX4 NuttX-подобных концепций)"
  fix: "FreeRTOS (ESP32; PX4 работает на NuttX — другой RTOS с теми же понятиями задач, приоритетов и очередей)"
  why: PX4 runs on NuttX (POSIX RTOS), not FreeRTOS.
  source: https://docs.px4.io/main/en/concept/architecture.html
- severity: error
  file: content/companion/emb-basics.md
  quote: "планировщик Betaflight и FreeRTOS в ESP32/PX4"
  fix: "планировщик Betaflight, FreeRTOS в ESP32 и NuttX в PX4"
  why: PX4 uses NuttX, not FreeRTOS.
  source: https://docs.px4.io/main/en/concept/architecture.html
- severity: imprecise
  file: content/companion/emb-basics.md
  quote: "// esp_timer periodic 1000 us -> on_timer"
  fix: "// esp_timer periodic 1000 us -> on_timer with dispatch_method = ESP_TIMER_ISR (needs CONFIG_ESP_TIMER_SUPPORTS_ISR_DISPATCH_METHOD); default ESP_TIMER_TASK runs the callback in the esp_timer task, not an ISR"
  why: esp_timer callbacks run from the esp_timer task by default, so on_timer (commented "ISR") is not an ISR unless ISR dispatch is enabled. The FromISR calls and portYIELD_FROM_ISR assume an ISR.
  source: https://github.com/espressif/esp-idf/blob/master/components/esp_timer/include/esp_timer.h
- severity: imprecise
  file: content/companion/emb-basics.md
  quote: "критические задачи (gyro/PID) вытесняют по времени, остальные ждут «дырки»"
  fix: "критические задачи (gyro/PID) ничего не вытесняют — планировщик просто не запускает задачу пониже, если её оценка времени выполнения (`anticipatedExecutionTime`) не помещается до следующего цикла гироскопа; остальные ждут «дырки»"
  why: The Betaflight scheduler is cooperative with no preemption. Gyro/PID timing is protected by skipping tasks whose estimated time does not fit (schedLoopRemainingCycles/taskRequiredTimeUs).
  source: https://github.com/betaflight/betaflight/blob/master/src/main/scheduler/scheduler.c

## emb-protocols
verified: 30
- severity: outdated
  file: content/companion/emb-protocols.md
  quote: "### Шаг 1. Драйвер I2C-датчика (ESP32, ESP-IDF)"
  fix: "### Шаг 1. Драйвер I2C-датчика (ESP32, ESP-IDF; пример на legacy-API `driver/i2c.h`, который объявлен end-of-life с ESP-IDF v6.0 — в новых проектах `driver/i2c_master.h`: `i2c_master_transmit_receive`/`i2c_master_transmit`)"
  why: i2c_master_write_read_device/i2c_master_write_to_device belong to the legacy driver, which now emits an EOL warning as of v6.0.
  source: https://github.com/espressif/esp-idf/blob/master/components/driver/i2c/include/driver/i2c.h

## eng-ci-configs
verified: 22
- severity: error
  file: content/companion/eng-ci-configs.md
  quote: "mavproxy.py --master=... --cmd=\"param download; param save params.param\""
  fix: "mavproxy.py --master=... --cmd=\"param fetch; param save params.param\""
  why: In MAVProxy `param download` downloads parameter metadata/docs (param_help_download); `param fetch` fetches the values.
  source: https://github.com/ArduPilot/MAVProxy/blob/master/MAVProxy/modules/mavproxy_param.py
- severity: imprecise
  file: content/companion/eng-ci-configs.md
  quote: "Betaflight: по USB через MSP — `diff all` с CLI командой"
  fix: "Betaflight: по USB в режиме CLI (не MSP: вход в CLI символом `#`) — `diff all`"
  why: diff all is a CLI command sent over the serial CLI, which is entered with '#'. It is not an MSP transaction.
  source: https://betaflight.com/docs/wiki/guides/current/Cli

## eng-systems
verified: 6, no findings

## fw-reading
verified: 34
- severity: error
  file: content/companion/fw-reading.md
  quote: "`(gyroRateDterm[axis] - previousGyroRateDterm[axis]) * pidFrequency` → затем D-LPF, умножение на `pidCoefficient[axis].Kd` и `dMinFactor`"
  fix: "`-(gyroRateDterm[axis] - previousGyroRateDterm[axis]) * pidFrequency`, где `gyroRateDterm` — гироскоп, уже пропущенный через D-notch и D-LPF1/LPF2 (фильтры стоят до дифференцирования), затем умножение на `pidCoefficient[axis].Kd` и `dMinFactor` (в master — `dMaxMultiplier`)"
  why: In pid.c the D-term notch/lowpass filters are applied to gyro before the delta is taken, not after. On master the factor is renamed dMaxMultiplier.
  source: https://github.com/betaflight/betaflight/blob/master/src/main/flight/pid.c
- severity: imprecise
  file: content/companion/fw-reading.md
  quote: "масштаб коэффициента — в `pid_init.c`"
  fix: "масштаб коэффициента — константы в `pid.h`, применяются в `pid_init.c`"
  why: PTERM_SCALE/ITERM_SCALE/DTERM_SCALE are #defined in flight/pid.h and used in pid_init.c.
  source: https://github.com/betaflight/betaflight/blob/master/src/main/flight/pid.h
- severity: outdated
  file: content/companion/fw-reading.md
  quote: "для каждой оси `rate_target_to_motor_roll(gyro, target)` → `_pid_rate_roll.update_all(target, gyro, dt, limit)`"
  fix: "для каждой оси `_motors.set_roll(get_rate_roll_pid().update_all(target, gyro, dt, _motors.limit.roll, …))`"
  why: The current rate_controller_run() calls get_rate_*_pid().update_all() directly inside _motors.set_*(). rate_target_to_motor_* no longer exists.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AC_AttitudeControl/AC_AttitudeControl_Multi.cpp
- severity: error
  file: content/companion/fw-reading.md
  quote: "порядок: сначала roll/pitch, потом throttle, потом yaw в пределах headroom"
  fix: "порядок: сначала roll/pitch, затем yaw — сколько помещается (`MOT_YAW_HEADROOM` — гарантированный минимум), и только потом подбирается throttle, который влезает в оставшийся диапазон"
  why: output_armed_stabilizing computes roll/pitch, then yaw_allowed with yaw headroom, adds yaw, and fits throttle last.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_Motors/AP_MotorsMatrix.cpp
- severity: outdated
  file: content/companion/fw-reading.md
  quote: "**Вывод**: `drivers/dshot.c`, `drivers/pwm_output*.c`, `drivers/dshot_bitbang.c` — формирование кадров DShot через таймер+DMA, bidirectional DShot для eRPM (`drivers/dshot_dpwm.c`)."
  fix: "**Вывод**: `drivers/dshot.c` (кодирование кадра), `drivers/pwm_output.c`; платформенная часть на текущем master — `src/platform/STM32/dshot_bitbang.c`, `src/platform/common/stm32/dshot_dpwm.c`, `pwm_output_dshot_shared.c` — формирование кадров DShot через таймер+DMA; декодирование eRPM bidirectional DShot — `drivers/dshot_bitbang_decode.c` (в 4.5 `dshot_dpwm.c` лежал в `src/main/drivers/`)."
  why: On master dshot_bitbang.c and dshot_dpwm.c are no longer in src/main/drivers (404) but in src/platform/. dshot_dpwm is DMA-PWM output, not specifically bidirectional.
  source: https://github.com/betaflight/betaflight/tree/master/src/platform

## unverified
- comp-raspberry: Pi 5 "`/dev/ttyAMA0` на GPIO 14/15 после `dtparam=uart0=on`" and whether `/dev/serial0` on Pi 5 points to the debug UART (ttyAMA10) rather than GPIO14/15. The raspberrypi.com configuration page was blocked (permission prompt unanswered), so this was not checked. It matters because the config uses /dev/serial0 throughout.
- comp-intro: Jetson Orin Nano "7–15 Вт, 19 В или 5 В/4 А" (newer JetPack "Super" mode reaches 25 W). Not checked against NVIDIA docs.
- comp-esp32: mavlink C headers for common.xml "100 КБ flash". This depends on how many messages get linked in, so there is no fixed figure.
- comp-esp32: EdgeTX widget background() semantics. serialRead/setSerialBaudrate were confirmed in api_general.cpp, but luadoc.edgetx.org was blocked.
- mav-routing: "Аппараты: 1…250". MAVLink defines 1–255 with no reserved vehicle range. This looks like convention, not spec.
- eng-ci-configs: "`ver` в ArduPilot" as a way to get the firmware version (MAVProxy has `version`; no ArduPilot CLI `ver` found).
- fw-reading: AC_PID description "D считается от ошибки, пропущенной через FLTD". FLTE filters the error and FLTD filters the derivative. AC_PID.cpp was not re-read, so this is not filed.
- Internal consistency (not a factual source check): comp-esp32 describes the line protocol as `S,<mode>,<armed>,...`, but the code uses `STATE armed`. The "ESP32 перезагружается при включении Wi-Fi" diagnostic appears twice. Both are worth cleaning up.
