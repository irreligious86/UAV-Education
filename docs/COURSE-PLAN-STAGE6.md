# Course plan — Stage 6: from "knows the stack" to "designs and ships an aircraft"

Status: **proposal, waiting for Alex's priorities** (2026-11-10). Nothing here is started.

## 1. Where the course is now

| Area | State |
|---|---|
| Modules | 117 published: 8 tracks (foundation 14, operator 14, electronics 11, integrator 11, estimation 7, autonomy 13, engineer 19, perception 9) and 4 electives (INAV 5, PX4 5, math 3, ROS 2 6) |
| Practice | every module has a lab with acceptance criteria and ≥ 150 words of practice prose; 117 quiz banks × 8 questions; 51 numeric task banks; 12 software projects; 8 track capstones |
| Visuals | 141 diagrams (generated, per language), 10+ interactive widgets |
| Reference | glossary 185 terms, failure log 572 cases, formulas and commands, checklists, firmware comparison |
| Languages | ru (source), uk, en, Galician dialect — all 117 modules, quizzes and tasks |
| Platform | static site + optional Supabase backend (accounts, roles, private exam banks, cohorts, account language) — built and tested, **not live** (waiting for go-live, MULTIUSER-PLAN §8) |
| Quality | fact-check reports for every stage, two security reviews, translation review; CI: content validation, links, rendering, JS, 111 database tests, 32 e2e steps, ROS 2 image |

What the course does well: FPV and ArduPilot/PX4 setup and tuning, logs and diagnostics, MAVLink and
companion computers, perception, the software side of UAS.

What a "top-level UAV engineer" still cannot learn here (topics with **zero** coverage found by a
full-text audit): designing an aircraft from requirements, measuring propulsion on a thrust stand,
fixed-wing stability and CG, helicopters and tailsitters, combustion/hybrid power, RTK base/NTRIP,
indoor positioning (UWB, motion capture), hardware debugging (SWD/JTAG/GDB), building and extending
firmware from source, HIL testing, control allocation in depth, LQR/MPC/INDI in practice, path planning
and behaviour trees, flight-test methodology, operational risk assessment (SORA), parachute systems,
cellular/satellite BVLOS links, video codecs and latency, application domains (agriculture, inspection,
LiDAR, delivery, SAR), training a detector on your own dataset.

## 2. Proposed new modules

Priority: **A** — core gap for an engineer, do first; **B** — strong addition; **C** — nice to have / backlog.
Every module follows the article template (summary, theory, practice with a lab and acceptance criteria,
diagnostics, checklist, references ≥ 2), gets a quiz bank (8), a task bank where there are formulas, a
diagram, glossary terms, and is translated into uk/en/gal and fact-checked before it is marked done.

### 2.1 Design and propulsion — new track "Конструктор" (between Electronics and Integrator)

| id | Module | Pri | Lab / outcome |
|---|---|---|---|
| des-sizing | Проектирование под задачу: ТЗ → масса, энергия, тяга, конфигурация | A | Python sizing script for a given mission (payload, endurance, wind); compare with a real build |
| des-thrust-stand | Тяговый стенд: тензодатчик + HX711, ток, обороты, КПД | A | build a stand (ESP32), measure one motor/prop at 5 throttle points, g/W curve vs datasheet |
| aero-stability | Самолёт: устойчивость, центровка, статический запас, поляра | A | compute CG/neutral point of a wing, check in XFLR5 or a script, balance a real airframe |
| des-structures | Конструкция и материалы: углепластик, печать PA-CF/PETG, крепёж, вибрация | B | load/stiffness estimate of an arm, print and test a mount, resonance measurement |
| des-cad | CAD для рамы и креплений (FreeCAD/Fusion), допуски под печать | B | parametric camera/gimbal mount, printed and fitted |
| des-thermal-ip | Тепло и влагозащита: ESC/компаньон, IP-рейтинг, покрытие | C | temperature log of ESC and companion under load, mitigation |
| des-manufacturing | От прототипа к серии: BOM, DFM, приёмочный стенд, документация (backlog topic) | B | BOM + acceptance test procedure for a small batch |

### 2.2 Navigation and precision

| id | Module | Pri | Lab / outcome |
|---|---|---|---|
| nav-rtk | RTK/PPK: база и ровер, NTRIP, moving baseline yaw, GPS_INJECT | A | base + rover (or NTRIP caster), fix type and accuracy log, GPS yaw on a bench |
| nav-indoor | Без GNSS: оптический поток, UWB, motion capture → EKF3 ExternalNav / VISION_POSITION | A | SITL with simulated external nav; optical-flow hover check; mocap pipeline described |
| nav-terrain | Следование рельефу: terrain data, дальномер, TERRAIN_*, безопасность | B | SITL mission over terrain with and without rangefinder, AGL plot |

### 2.3 Control and autonomy

| id | Module | Pri | Lab / outcome |
|---|---|---|---|
| ctl-allocation | Миксер и распределение управления: матрица, насыщение, PX4 Control Allocation, наклонные моторы | A | build a mixer matrix for a custom frame in Python, saturation demo, PX4 CA setup in SITL |
| aut-planning | Планирование пути: A*, RRT*, карты занятости; OA в ArduPilot (BendyRuler, Dijkstra) и Nav2 | A | planner in Python on a grid, then ArduPilot OA in SITL around a fence |
| aut-behavior | Логика миссии: конечные автоматы vs behaviour trees, обработка отказов | A | BehaviorTree.CPP (or py_trees) mission with failure branches against SITL |
| ctl-trajectory | Траектории: сплайны, minimum snap, ограничения динамики | B | generate and fly a min-snap path in SITL via offboard/guided |
| ctl-advanced | LQR, INDI, MPC: теория на пальцах и где они в реальных прошивках | B | LQR vs PID on the course's axis model; read the INDI/MPC code paths |
| aut-swarm | Рои и групповые полёты: формация, консенсус, эфир, шоу (Skybrush) (backlog topic) | B | 3–5 vehicles in SITL in formation through mavlink-router |

### 2.4 Firmware development — new elective "Разработка прошивок"

| id | Module | Pri | Lab / outcome |
|---|---|---|---|
| fw-build-ap | ArduPilot из исходников: waf, hwdef, свой параметр, свой Lua-биндинг | A | build for a real board and SITL, add a parameter, flash and verify |
| fw-debug | Отладка железа: SWD, ST-Link/J-Link, OpenOCD, GDB, HardFault, логический анализатор | A | breakpoint in the scheduler of a running FC, decode a HardFault, I²C capture |
| fw-driver | Свой драйвер датчика (I²C/SPI) в ArduPilot: AP_HAL, backend, тест на столе | B | driver for a cheap sensor, values in the log |
| fw-px4-module | Свой модуль PX4: uORB-топик, work queue, параметры | B | module publishing a topic, visible in ROS 2 via uXRCE-DDS |
| fw-hil-testing | Автотесты и HIL: autotest ArduPilot, SITL-сценарии в CI, HIL с реальным контроллером | B | one autotest scenario of your own, run in CI (connects to "SITL in CI") |
| fw-upstream | Контрибьют в open source: issue, PR, ревью, стиль, CI проекта | C | a real documentation or code PR to ArduPilot/PX4/Betaflight |

### 2.5 Power, airframes, links

| id | Module | Pri | Lab / outcome |
|---|---|---|---|
| link-cellular | BVLOS-каналы: LTE-модемы, VPN/WireGuard, задержка, резервирование; спутник (Iridium SBD, Starlink) | A | MAVLink over LTE with WireGuard, latency/jitter log, failover to RC link |
| link-video-codec | Видео: H.264/H.265, GOP, битрейт, бюджет задержки glass-to-glass | B | measure glass-to-glass latency with a stopwatch method, tune encoder |
| pwr-ice-hybrid | ДВС и гибриды: двигатели, зажигание, EFI в ArduPilot, генератор, топливо (backlog topic) | B | EFI telemetry in SITL, endurance math battery vs hybrid |
| safety-parachute | Парашют и терминация: CHUTE_*, скорость снижения, ASTM F3322 | B | descent-rate calculation, CHUTE trigger test in SITL |
| heli-trad | Классический вертолёт в ArduPilot: автомат перекоса, коллективный шаг, H_*, RSC | B | heli SITL setup and tune basics |
| vtol-tailsitter | Тейлситтеры и тилтроторы: переходы, Q_TAILSIT_*, Q_TILT_*, отказы перехода | B | tailsitter SITL transitions, log of a failed transition |
| pwr-tether | Привязные системы: питание по кабелю, ВВ-передача, лебёдка | C | power budget of a tethered hover |
| link-mesh-lora | Mesh и LoRa (Meshtastic): медленная телеметрия, ограничения | C | position over Meshtastic to a GCS |

### 2.6 Operations, safety, regulations

| id | Module | Pri | Lab / outcome |
|---|---|---|---|
| ops-flight-test | Лётные испытания: план, тест-карты, расширение диапазона, критерии остановки, отчёт | A | test plan + test cards + report for a new build (envelope expansion) |
| ops-risk-sora | Оценка риска: SORA, safety case, требования к BVLOS | A | SORA ground/air risk for a sample mission |
| ops-human-factors | Человеческий фактор: CRM, чек-листы, усталость, нагрузка | B | crew briefing and checklist redesign from an incident |
| sec-threats | Безопасность БАС: модель угроз, подписанная прошивка, шифрование линков, детекция spoofing/jamming | B | threat model of the student's own system, secure bootloader on a board |
| ops-airworthiness | Лётная годность и сертификация: ASTM F38, EASA SC-Light UAS, документация (backlog topic) | C | document set outline for a certification basis |

### 2.7 Applications — new track "Применения" (after Perception)

| id | Module | Pri | Lab / outcome |
|---|---|---|---|
| ml-dataset | Свой датасет и обучение детектора: сбор, разметка (CVAT), аугментация, YOLO, метрики, экспорт | A | train on 300–500 own images, mAP report, deploy to the companion from per-edge-ml |
| app-agri | Агро: опрыскивание (насос, SPRAY_*), расход и снос, мультиспектр и NDVI | B | spray-rate calculation, NDVI from an open multispectral set |
| app-inspection | Инспекция: радиометрические тепловизоры, ЛЭП и солнечные станции, отчёт | B | thermal anomaly report from an open dataset |
| app-lidar | Лидарная съёмка: принцип, синхронизация с IMU, PPK, облака точек | B | point-cloud processing in CloudCompare/Open3D on an open set |
| app-delivery | Доставка и сброс: механизмы, лебёдка, безопасность зоны | C | release mechanism on a servo with GRIPPER_* in SITL |
| app-sar | Поиск и спасание: паттерны поиска, тепловизор, ретрансляция | C | search-pattern mission and coverage calculation |
| sim-photoreal | Фотореалистичная симуляция: AirSim/Isaac Sim, синтетические данные, sim2real | C | synthetic dataset for ml-dataset |
| ml-rl-control | RL для управления: что работает, sim2real, безопасность | C | — (reading + small gym experiment) |
| career | Портфолио и карьера: проекты, GitHub, даташиты, техписьмо, собеседование | C | portfolio page from the student's own capstones |

Totals: A 18, B 20, C 11 (49 modules), plus 5 setup-from-scratch modules (§2.8, priority A). Stage 6 proper = A + most of B (~40); C stays in the backlog.

### 2.8 Setup from scratch — one hands-on lesson per firmware (audit 2026-11-10)

**Question (Alex):** can a student take each of the four firmwares and set up their own drone from zero
using only the course? **Answer today: Betaflight almost; ArduPilot partly; INAV and PX4 no.**
The knowledge is spread across modules, but no module walks the whole chain end to end on one
aircraft, and several steps are not covered anywhere.

Coverage of the 17 setup steps by the current modules (✓ covered with a procedure, ~ mentioned or theory
only, ✗ missing; "n/a" = not applicable to that firmware):

| # | Step | Betaflight | INAV | ArduPilot (Copter) | PX4 (multirotor) |
|---|---|---|---|---|---|
| 1 | Flash the right target / board, back up the old config | ✓ bf-intro | ~ inav-intro | ~ ap-intro | ~ px4-intro |
| 2 | Board orientation, frame type, mixer | ✓ | ✓ inav-intro | ✓ ap-intro | ~ px4-intro |
| 3 | UART / port map (RX, GPS, VTX, telemetry) | ✓ bf-ports | ~ | ~ `SERIALn_PROTOCOL` | ✗ |
| 4 | Receiver: protocol, bind, link check | ✓ link-elrs | ✗ | ✗ `RC_PROTOCOLS`, `SERIALn_PROTOCOL 23` absent | ✗ |
| 5 | Channel map, endpoints, stick calibration | ~ | ✗ | ~ | ✗ |
| 6 | Motor protocol (DShot/PWM/OneShot) | ✓ f-motors-esc | ✗ | ~ `MOT_PWM_TYPE` | ✗ |
| 7 | Motor order and direction test, props off | ~ | ✗ | ~ | ✗ |
| 8 | ESC calibration (PWM ESCs only) | n/a for DShot, ✗ for PWM | ✗ | ~ | ✗ |
| 9 | Accelerometer / compass calibration | ✓ accel | ~ | ~ | ~ |
| 10 | Battery voltage / current calibration | ✗ `vbat_scale`, `ibata_scale` | ✗ | ~ `BATT_VOLT_MULT`, `BATT_AMP_PERVLT` | ✗ `BAT1_V_DIV`, `BAT1_A_PER_V` |
| 11 | Modes, arming switch, pre-arm checks | ✓ bf-modes-osd | ✓ inav-intro | ✓ ap-intro | ~ px4-intro |
| 12 | Failsafe configured **and tested** | ✓ bf-failsafe | ~ | ✓ ap-safety-fs | ~ |
| 13 | OSD and video (analog / MSP DisplayPort) | ✓ bf-modes-osd, link-vtx | ~ | ✗ `OSD_TYPE` | ✗ |
| 14 | GPS, home, RTH / RTL / GPS Rescue | ✓ GPS Rescue | ✓ inav-gps | ~ | ~ |
| 15 | Pre-flight check and maiden hover procedure | ✗ | ~ inav-intro step 4 | ✗ | ✗ |
| 16 | First tune (filters, PIDs, autotune) | ✓ bf-filters, bf-pid | ~ | ✓ ap-tuning | ~ px4-control |
| 17 | Logging on, config backup (diff / .param), restore | ✓ bf-cli | ~ | ~ | ✗ |

Other gaps found:
- The **INAV path** has no setup stage and no capstone; it also lacks f-motors-esc and link-vtx.
- The **PX4 path** has no capstone and no f-power, f-motors-esc, link-protocols, link-elrs, f-regulations:
  a student on that path never learns how the aircraft is powered or controlled by radio.
- ArduPilot covers the most, but in pieces across 9 modules; ArduPlane setup exists only as tuning (ap-plane-tuning).

**New modules (L2, ~6–8 h each incl. lab).** Each one is a single aircraft taken from an empty board to a
logged maiden hover, in the order of the 17 steps above. The theory section is short and links to the
modules that already explain each step; the module adds what is missing (bold in the table above).
SITL is the main path (decision 3) wherever the firmware has one; steps that cannot exist in a simulator
(bind, motor direction, ESC calibration, battery calibration, maiden hover) are done on the bench in
«Переход на реальное железо» — **props off** until step 15.

| Id | Title (ru) | SITL / main path | «Переход на реальное железо» | Lab accepted when |
|---|---|---|---|---|
| bf-setup-scratch | Betaflight с нуля: от пустой платы до первого висения | BF `SITL` target + Configurator over TCP for steps 1–3, 9, 11, 16–17; the rest on a USB-powered FC (no battery, no props) | full 17 steps on a 5″ quad: bind ELRS, DShot order/direction (`resource`, `motor` CLI / Motors tab), `vbat_scale` and `ibata_scale` against a multimeter and a charger's mAh, failsafe test with the TX off, maiden hover | `diff all` committed; voltage error < 0.05 V/cell, mAh within 5 % of the charger; failsafe stage 2 recorded; blackbox of a 60 s hover |
| inav-setup-scratch | INAV с нуля: GPS-квадрокоптер | INAV SITL (built in since INAV 7, Configurator «SITL» tab) for mixer, modes, failsafe, RTH, missions | GPS quad: bind, motor order/direction, battery calibration, compass, `nav_*` checks on the ground (estimator test from inav-intro), maiden hover, PosHold, RTH from 100 m | `diff all`; RTH lands within 3 m of home in SITL and within 5 m in flight; failsafe → RTH recorded |
| inav-setup-wing | INAV с нуля: крыло | INAV SITL with a fixed-wing model | flying wing / plane: servo direction and endpoints, surface throws and centring, CG check, motor/ESC, launch mode, `nav_fw_*` basics, first hand-launch | servo test table filled; CG within the design range; launch log; RTH loiter recorded |
| ap-setup-scratch | ArduPilot с нуля: Copter через Mission Planner / QGC | `sim_vehicle.py -v ArduCopter` + MP/QGC: frame, `SERIALn_PROTOCOL`, `RC_PROTOCOLS`, `MOT_PWM_TYPE`, motor test, `BATT_*`, modes, FS (`SIM_RC_FAIL`), `OSD_TYPE`, param backup | real copter: flash with the bootloader, bind, RC calibration, ESC calibration (PWM) or DShot, compass and accel calibration, `BATT_VOLT_MULT` / `BATT_AMP_PERVLT`, motor order with `MOT_SPIN_ARM`/`MOT_SPIN_MIN`, maiden hover in Stabilize → AltHold → Loiter, QuickTune / AutoTune | `.param` file committed; hover throttle `MOT_THST_HOVER` 0.2–0.5; vibration < 30 m/s²; RC and battery failsafe recorded in the log |
| px4-setup-scratch | PX4 с нуля: Vehicle Setup в QGroundControl | `make px4_sitl gz_x500` (or SIH) + QGC: airframe, sensors, radio, flight modes, power, Actuators tab (motor order and direction test), safety; failure injection (`failure` command) | real multirotor: flash, airframe, `SER_*` / RC input, radio calibration, actuator geometry and motor test, ESC calibration (PWM), `BAT1_V_DIV`, `BAT1_A_PER_V`, failsafes, maiden hover in Position mode | params exported; motor test matches the geometry; RC loss and low battery failsafes in the ULog; Flight Review report of the maiden flight |

Later, optional: `ap-setup-plane` (ArduPlane from scratch: servo functions, `TRIM_*`, `TECS_*` basics,
takeoff mode) and `px4-setup-vtol`.

**Capstones** (fill the empty capstone slots):
- `cap-inav-gps` — "INAV-аппарат с нуля": choose quad or wing, set up from an empty board, fly a
  5-waypoint mission with failsafe-RTH tested; deliverable: `diff all`, logs, a one-page setup card.
- `cap-px4-scratch` — "PX4 с нуля до миссии": SITL rehearsal, then the real vehicle (or SIH/Gazebo if no
  hardware yet, with the hardware part graded later): setup, failsafe matrix, mission, ULog analysis report.

**Path changes** (curriculum.json): a stage «Настройка с нуля» in every firmware path, right after the
introduction module — Betaflight: after bf-intro/bf-ports; INAV: after inav-intro; ArduPilot: after
ap-sitl; PX4: after px4-intro. PX4 path also gets f-power, f-motors-esc, link-protocols, link-elrs,
f-regulations in «Основа»; INAV path gets f-motors-esc and link-vtx.

**Beyond modules:** a printable one-page "setup card" per firmware (the 17 steps with the exact
Configurator tab / CLI command / parameter for that firmware) — linked from each setup module.

## 3. Material beyond modules

| Item | Why | Notes |
|---|---|---|
| Exam banks per track | the exam engine exists, but there are no banks yet | banks must **not** live in the public repository: author them in a private repo or upload straight through the admin page (decision for Alex) |
| Lab checker in the browser | today labs are self-checked | parse a DataFlash/ULog file in the browser (JS), verify lab criteria (e.g. "hover throttle 0.3–0.5", "vibration < 30 m/s²"), record the result in progress |
| New widgets | interactive beats static for control topics | mixer matrix, step response with delay, A* planner, CG/static margin, link budget over LTE, flight-envelope chart |
| Bench kit | many labs need hardware | recommended kit in three tiers (sim only / bench / flying), BOM with prices and alternatives |
| Thrust-table reference data | fixes the open X8 example in f-aero-props (translator notes) | measured on the des-thrust-stand rig; numbers reused by f-aero-props, f-power, ap-heavy, el-redundancy |
| Flashcards with spaced repetition | retention of glossary and quiz facts | from the glossary and quiz banks, per-browser schedule (or account when live) |
| Video | the planned "Betaflight изнутри" series | embed short videos in their modules when published |
| Case-study library | learning from real accidents | 10 more investigated incidents (AAIB, NTSB, BFU, STSB reports) in ops-case-studies style |
| SITL in CI | postponed by Alex | becomes natural with fw-hil-testing |

## 4. Iterations

Each iteration ends with: modules published, quizzes and tasks, diagrams, glossary terms, translations
(uk, en, gal), an independent fact-check applied, CI green.

| # | Iteration | Content |
|---|---|---|
| 1 | Design core | des-sizing, des-thrust-stand, aero-stability, ctl-allocation; new track "Конструктор" |
| 1b | Setup from scratch (§2.8) | bf-setup-scratch, inav-setup-scratch, inav-setup-wing, ap-setup-scratch, px4-setup-scratch; capstones cap-inav-gps, cap-px4-scratch; path changes; setup cards |
| 2 | Precision navigation | nav-rtk, nav-indoor, nav-terrain |
| 3 | Firmware development elective | fw-build-ap, fw-debug, fw-driver, fw-px4-module, fw-hil-testing |
| 4 | Autonomy | aut-planning, aut-behavior, ctl-trajectory, ctl-advanced, aut-swarm |
| 5 | Operations and safety | ops-flight-test, ops-risk-sora, ops-human-factors, safety-parachute, sec-threats |
| 6 | Links, power, airframes | link-cellular, link-video-codec, pwr-ice-hybrid, heli-trad, vtol-tailsitter |
| 7 | Applications track | ml-dataset, app-agri, app-inspection, app-lidar; des-structures, des-cad, des-manufacturing |
| 8 | Beyond modules | browser lab checker, widgets, bench kit, flashcards, exam-bank workflow |
| 9 | Verification | security review of new platform features, full fact-check sample, translation review, report |

Rough size: an iteration of 4–5 modules ≈ 25–30k words of Russian source plus ~3× that in translations.

## 5. Decisions (Alex, 2026-11-10)

1. Order: engineering depth first — iterations as listed in §4.
2. Exam banks: in the public repository while the course is in development; revisit when moving to a server.
3. Hardware: SITL / calculation is the main path of every lab; each module has a separate
   «Переход на реальное железо» part (procedure and acceptance criteria) so students move to real hardware later.
4. Languages: new modules are written in Russian only (the source). Localisation of everything new or stale into
   uk/en/gal runs later as one batch when Alex asks for it; until then those pages show the Russian text with the
   "not translated" notice.

## 5a. Original questions

1. **Order**: the iterations above follow "engineering depth first". Alternatives: applications first
   (faster visible value) or firmware development first (closest to Alex's ESP32/C++ work).
2. **Exam banks**: private repository, local files uploaded through the admin page, or postpone until go-live.
3. **Hardware**: which bench hardware is available (thrust stand parts, ST-Link/J-Link, RTK modules,
   UWB kit) — labs can be written for SITL-only with an optional hardware path.
4. **New modules in all four languages from day one**, or Russian first and translations in a batch.
