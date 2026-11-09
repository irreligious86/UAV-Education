# stage5-tasks-quizzes-glossary

Scope: numeric task banks from d46d205 (31 tasks in 16 `content/tasks/*.json`), quiz questions from c9e9d39 (66 new or changed questions in `content/quiz/*.json`; the commit message says 65), and glossary terms from 90743d1 (69 entries in `data/glossary.json`).

Basis:
- Task runtime: `scripts/build_site.py` `build_task_variants`, which evaluates `answer` with Python `eval` (globals limited to `math`, `min`, `max`, `abs` and `round`) and publishes 8 seeded variants per task. Acceptance in `assets/uav-tasks.js` is `|x − ans| ≤ max(|ans|·tol, abs)`.
- How I checked the tasks: I ran every bank through `build_task_variants` and inspected all published variants (parameters and answers). I recomputed the formulas independently and checked the parameter spaces for plausibility.
- ArduPilot sources:
  - AP_L1_Control (L1 = ζ·T·V/π, K_L1 = 4ζ²).
  - ArduPilot-4.6 `libraries/AP_GPS/AP_GPS.cpp` and `AP_GPS_Params.cpp`, which define the `GPS1_`/`GPS2_` subgroups with `RATE_MS` default 200.
  - ArduPilot-4.6 `AP_Camera_Params.cpp` (`CAM1_TRIGG_DIST`).
  - ArduPilot-4.7 `AC_WPNav.cpp` (`WP_JERK`, `WP_SPD`, `WP_ACC`, `WP_RADIUS_M`).
  - master `libraries/AP_DDS/README.md`.
  - The ardupilot.org param-rename page.
- Other primary sources:
  - ArduPilot wiki, SiK advanced configuration (RSSI/1.9 − 127; fade margin ≈ (rssi − noise)/2; +6 dB = 2× range).
  - INAV docs, GPS Failsafe and Glitch Protection.
  - Bluejay README (supported MCUs).
  - ros2_documentation jazzy, About-Quality-of-Service-Settings.rst.
  - rclcpp jazzy `subscription_base.cpp` (default incompatible-QoS callback).
  - Oscar Liang on Betaflight `status` / BUILD KEY.
- Recomputed by hand:
  - CAN frame 29-bit/8 B: 131 bits with IFS, about 160 bits worst-case stuffing.
  - INA226 CAL = 0.00512/(LSB·R) and 81.92 mV full scale.
  - DShot CRC.
  - P_hover ∝ 1/√ρ.
  - DA rule 36.6 m/°C.
  - Pure-pursuit a = 2V²sinα/L.
  - Trapezoid T = D/v + v/a.
  - Time-delay gain limit K = π/(2T_d).
  - 5-of-6 binomial.
  - UART 8N1 at 115200 = 86.8 µs.
  - ½ρv² at 20 m/s = 245 Pa.
  - `get_throttled` 0x50000 = bits 16 and 18.

## Numeric tasks (content/tasks/)
verified correct: 26 of 31 (formula, units, ranges, answer ↔ question, tolerance, solution text)

Checked without findings:
- ap-plane-tuning: tconst, bank
- comp-raspberry: drop
- ctl-guidance: l1, pp
- ctl-sysid: corner, phase
- el-dronecan: term, load
- el-kicad: shunt, cal, power
- el-measure: crc, ri
- est-attitude: drift
- f-components-choice: time
- f-esc-firmware: rpm, hz
- link-telemetry-radios: dbm, range
- mav-multi-vehicle: sep
- ops-maintenance: rel
- ops-weather: wind, da
- payload-gimbal: shots
- per-tracking: kp

- severity: inaccuracy
  file: content/tasks/ops-weather.json
  item: hover
  quote: "Плотность воздуха составляет **{r} %** от уровня моря. На сколько процентов от мощности на уровне моря нужно для висения той же массы?"
  fix: "Плотность воздуха составляет **{r} %** от уровня моря. Какая мощность нужна для висения той же массы — в процентах от мощности на уровне моря?"
  why: In Russian, «На сколько процентов…» asks for the increase, for example 6 %. The answer `100*math.sqrt(100/r)` is the total ratio, for example 106 %. A student who answers the question as written is marked wrong. The ×2 and ×1000 hints do not catch this.
  source: answer expression in the bank; content/foundation/ops-weather.md ("мощность висения растёт на ~16 %" = 116 %)

- severity: nit
  file: content/tasks/link-telemetry-radios.json
  item: fade
  quote: "`RADIO_STATUS`: rssi = **{r}**, noise = **{n}** (единицы SiK). Найдите запас по замиранию (дБ)."
  fix: "`RADIO_STATUS`: rssi = **{r}**, noise = **{n}** (единицы SiK, одна единица ≈ 0.5 дБ). Найдите запас по замиранию (дБ)."
  why: The previous task in the same bank teaches that 1 unit = 1/1.9 dB. A student who computes (r − n)/1.9 gets a result about 5 % high, for example 60.5 instead of 57.5, and tol 0.01 rejects it. The ÷2 rule is the official one, so state it in the statement. The alternative is to raise `tol` to 0.06.
  source: https://ardupilot.org/copter/docs/common-3dr-radio-advanced-configuration-and-technical-information.html

- severity: nit
  file: content/tasks/ops-maintenance.json
  item: hexa
  quote: "\"tol\": 0.002"
  fix: "\"tol\": 0.0002"
  why: The tolerance is relative to an answer close to 100 %, which gives ±0.2 percentage points. For r = 0.99 (99.854 %) and r = 0.995 (99.963 %), simply typing "100" is accepted. With 0.0002 the window is ±0.02 pp, which still accepts answers rounded to two decimals.
  source: assets/uav-tasks.js check(); published variants

- severity: nit
  file: content/tasks/ctl-guidance.json
  item: trap
  quote: "\"D\": {\"min\": 60, ...}" with v up to 12 and a down to 2
  fix: "\"D\": {\"min\": 80, \"max\": 200, \"step\": 10}"
  why: The statement promises that the distance is enough to reach the speed limit (D ≥ v²/a), but the parameter space allows D = 60–70 with v²/a = 72 (v 12, a 2), or 60.5 (v 11, a 2). In that case D/v + v/a is wrong. The 8 currently published variants happen to satisfy the condition, but any change to the seed or the variant count could publish a broken one.
  source: scripts/build_site.py build_task_variants; formula derivation in the task solution

- severity: nit
  file: content/tasks/f-components-choice.json
  item: tw
  quote: "\"title\": \"T/W и газ висения\""
  fix: "\"title\": \"Тяговооружённость T/W\"; also narrow \"m\" to {\"min\": 800, \"max\": 2000, \"step\": 100} (or tm max 1500)"
  why: The task asks only for T/W, not hover throttle. The parameter space also allows unrealistic builds, such as 4 × 2500 g motors on a 500 g craft (T/W 20). The published variants are 3.2–6.7, which is plausible.
  source: bank params

## Quizzes (content/quiz/)
verified correct: 61 of 66

Checked without findings:
- aero-wing #7, ap-heavy #7, ap-sitl #7, ap-tuning #7
- bf-cli-automation #5–7, bf-cli #7, bf-custom #6–7, bf-intro #7
- comp-intro #7, comp-raspberry #7
- ctl-signals #7, ctl-theory #7
- data-python #6–7, diag-troubleshooting #7
- el-battery-packs #7, el-emi #6–7, el-measure #7, el-peripherals #7, el-wiring #6–7
- emb-basics #7, emb-protocols #7
- eng-ci-configs #6–7, eng-method-101 #6–7, eng-systems #7
- est-alt-sources #6, est-attitude #6–7, est-gnss #7, est-kalman #6–7, est-sensors #7
- f-aero-props #7, f-components-choice #6–7, f-electricity-101 #7, f-frame-mech #7, f-mechanics #7, f-regulations #7
- fw-reading #7
- inav-intro #7, inav-ipf #7, inav-missions #7
- link-vtx #7, ops-case-studies #7, ops-field #7
- per-camera #7, per-cv #7, per-tracking #7, per-visual-nav #7
- px4-architecture #7, rf-antennas #7, rf-link-budget #7, tools-overview #7

(# = 0-based index in `questions`.)

- severity: error
  file: content/quiz/nav-resilience.json
  item: #7 "Что делает INAV при потере GPS в RTH?"
  quote: "failsafe_procedure: Land или Drop — RTH без GPS невозможен" / explain "…INAV выполняет процедуру failsafe."
  fix: |
    q: "Что делает INAV на мультикоптере, если GPS пропал во время RTH?"
    option 0: "Аварийная посадка (Emergency Landing): позиция потеряна — RTH невозможен"
    explain: "Если позиции нет дольше ~2 с, INAV в RTH/WP переходит в Emergency Landing: коптер в ANGLE снижается на failsafe_throttle и выключает моторы через failsafe_off_delay (при нулевых значениях — фактически DROP). failsafe_procedure — реакция на потерю RC, а не GPS; крыло с inav_allow_gps_fix_estimation может продолжить возврат по оценке."
  why: The INAV docs say that losing position in RTH or WP, including failsafe RTH, triggers the Emergency Landing state once the failure persists for more than 2 s. `failsafe_procedure` selects the reaction to RC loss. Distractor 1 ("Продолжает RTH по последнему курсу") is close to true for a fixed wing with GPS fix estimation, so the question has to be scoped to multicopters. The same wording is in content/inav/nav-resilience.md line 43 ("при потере GPS — `failsafe_procedure` (… → Land/Drop)"), and the module should be fixed the same way.
  source: https://inavflight.github.io/docs/features/GPS-Failsafe-and-Glitch-Protection

- severity: inaccuracy
  file: content/quiz/est-gnss.json
  item: #6 "Какая частота GPS разумна для коптера в ArduPilot?"
  quote: "5 Гц (GPS_RATE_MS = 200)"
  fix: "5 Гц (GPS1_RATE_MS = 200; до 4.6 — GPS_RATE_MS)"
  why: Since ArduPilot 4.6 the per-receiver GPS parameters are in the `GPS1_`/`GPS2_` subgroups, so `GPS_RATE_MS` is now `GPS1_RATE_MS`. The module already gives both names, but the quiz shows only the old one.
  source: https://raw.githubusercontent.com/ArduPilot/ardupilot/ArduPilot-4.6/libraries/AP_GPS/AP_GPS.cpp (AP_SUBGROUPINFO params[0] "1_"), AP_GPS_Params.cpp (RATE_MS default 200)

- severity: inaccuracy
  file: content/quiz/est-alt-sources.json
  item: #7 "Какой дальномер работает над водой и в пыли?"
  quote: "Какой дальномер работает над водой и в пыли?" / explain "…ультразвук и оптика — боятся."
  fix: |
    q: "Какой дальномер надёжно работает над водой, в пыли и тумане на высотах в десятки метров?"
    explain: "Радар не боится воды, пыли, тумана и освещения и берёт десятки метров; лидар над водой и в пыли теряет отражение, ультразвук ограничен 5–7 м и шумит от пропов и ветра."
  why: Water reflects ultrasound well, and dust barely affects it; MaxBotix sells sensors for water-level measurement. That makes distractor 0 arguably correct as the question is worded. The real limits of ultrasound, as the module states them, are its 5–7 m range and noise from props and wind.
  source: content/estimation/est-alt-sources.md line 38 (the module's own limits for ultrasound); MaxBotix markets its ultrasonic sensors for water-level measurement (manufacturer site, maxbotix.com)

- severity: inaccuracy
  file: content/quiz/el-redundancy.json
  item: #7 "Плоская окто по сравнению с гексой:"
  quote: option 1 "Требует меньше тяги на мотор при отказе"
  fix: option 1 → "Требует меньше общей тяги для висения той же массы"
  why: This distractor is arguably true. After one failure the remaining motors share the weight: 7 motors at about 8/7 of normal load, against 5 motors at 6/5 on a hexa. Each remaining octo motor therefore needs a smaller increase in thrust. The replacement is unambiguously false, because hover thrust equals weight on any frame.
  source: momentum/thrust balance; content/electronics/el-redundancy.md line 30

- severity: nit
  file: content/quiz/per-camera.json
  item: #6 "Чем YUV420 удобен для алгоритмов?"
  quote: "Сырой формат, не нужно декодировать"
  fix: "Несжатый формат: кадр не нужно декодировать"
  why: In camera work, "сырой" (raw) usually means Bayer RAW before demosaicing, and YUV420 is already processed by the ISP. "Несжатый" (uncompressed) is the accurate property.
  source: content/companion/per-camera.md line 32 (context)

## Glossary (data/glossary.json)
verified correct and consistent with linked module: 62 of 69

Every linked module exists and covers its term. No other entries contradict their modules. Spot checks on the remaining entries:
- MAV_COMP_ID_CAMERA = 100 and GIMBAL = 154
- OBSTACLE_DISTANCE has 72 sectors
- DroneCAN node ID is 1–127
- `MAV_SYSID` (4.7)
- `WP_JERK` (4.7)
- GSD formula
- overlap 70–80/60–70 %
- L1/NAVL1_PERIOD
- coherence
- uORB/uXRCE-DDS
- lifecycle states

- severity: error
  term: AP_DDS (module ros2-ardupilot)
  quote: "Встроенный в ArduPilot клиент DDS (micro-ROS): публикует состояние в ROS 2 и принимает команды без MAVLink, через micro-ROS agent."
  fix: "Встроенный в ArduPilot клиент eProsima Micro XRCE-DDS: публикует состояние в ROS 2 и принимает команды без MAVLink; на стороне ROS 2 его обслуживает агент (`micro_ros_agent` или Micro XRCE-DDS Agent)."
  why: The firmware does not run micro-ROS (rclc). AP_DDS is built on the eProsima Micro XRCE-DDS Client. Only the agent comes from the micro-ROS packaging (`micro_ros_agent`), as the module says ("клиент DDS … снаружи — агент micro-ROS").
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_DDS/README.md ("EProsima Micro XRCE DDS Client", "ros2 run micro_ros_agent micro_ros_agent udp4 -p 2019")

- severity: inaccuracy
  term: Bluejay (module f-esc-firmware)
  quote: "Открытая прошивка для ESC на MCU BB1/BB2/BB51 (наследник BLHeli_S) …"
  fix: "Открытая прошивка для ESC на 8-битных EFM8 BB21 и BB51 (BB1 — только до версии 0.18.1), наследник BLHeli_S, с bidirectional DShot для RPM-фильтра."
  why: BB10 (BB1, "L" layout) support was dropped after 0.18.1, and current Bluejay supports BB21 and BB51 only. The linked module's table already says this, so the glossary contradicts it.
  source: https://github.com/bird-sanctuary/bluejay/blob/main/README.md ("Supported Platforms"); content/foundation/f-esc-firmware.md line 30

- severity: inaccuracy
  term: Отказоустойчивость (module el-redundancy)
  quote: "Квадрокоптер её по мотору не имеет, X8 и гекса — имеют."
  fix: "Квадрокоптер её по мотору не имеет; гекса и X8 могут иметь — при запасе тяги, продуманном питании и проверенной (в SITL/на стенде) реакции прошивки."
  why: The module makes this conditional: «гекса и X8 могут продолжить полёт — если питание, сигналы и прошивка спроектированы под это». It also says a hexa holds yaw poorly. ops-maintenance adds that the ability "проверяют, а не предполагают". The glossary states it unconditionally.
  source: content/electronics/el-redundancy.md lines 23, 28; content/foundation/ops-maintenance.md line 62

- severity: inaccuracy
  term: UDP broadcast / unicast (module mav-routing)
  quote: "Через 4G и VPN работает только unicast."
  fix: "Через 4G/NAT и L3-VPN (WireGuard, Tailscale, OpenVPN tun) работает только unicast; broadcast проходит лишь через L2-туннели (ZeroTier, OpenVPN tap)."
  why: ZeroTier, which the linked module lists as a VPN option, emulates an Ethernet L2 network and carries broadcast when it is enabled. Only L3 tunnels drop broadcast.
  source: https://docs.zerotier.com/ (network setting "Enable Broadcast"); content/companion/mav-routing.md line 61

- severity: nit
  term: QoS (module ros2-basics)
  quote: "Несовместимые QoS у издателя и подписчика молча не соединяются."
  fix: "Несовместимые QoS у издателя и подписчика не соединяются, и ошибки нет — подписчик просто ничего не получает (в логе только предупреждение «incompatible QoS»)."
  why: It is not entirely silent. rclcpp installs a default incompatible-QoS event callback that logs a warning, and the module itself mentions that warning (line 39).
  source: https://github.com/ros2/rclcpp/blob/jazzy/rclcpp/src/rclcpp/subscription_base.cpp (default_incompatible_qos_callback); https://github.com/ros2/ros2_documentation/blob/jazzy/source/Concepts/Intermediate/About-Quality-of-Service-Settings.rst

- severity: nit
  term: SiK (module link-telemetry-radios)
  quote: "Открытая прошивка телеметрийных модемов 433/915 МГц …"
  fix: "Открытая прошивка телеметрийных модемов 433/868/915 МГц …"
  why: The linked module lists 433, 868 and 915 MHz.
  source: content/link/link-telemetry-radios.md lines 23, 30

- severity: nit
  term: Jetson Orin (module px4-companion-jetson)
  quote: "Семейство модулей NVIDIA с GPU и NPU для бортового инференса."
  fix: "Семейство модулей NVIDIA с GPU Ampere (у Orin NX/AGX — ещё ускорители DLA) для бортового инференса."
  why: NVIDIA calls its accelerator a DLA, not an NPU, and the Orin Nano has no DLA.
  source: https://developer.nvidia.com/embedded/jetson-modules (Orin series specs)
