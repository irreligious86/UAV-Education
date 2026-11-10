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

Totals: A 18, B 20, C 11 (49 modules). Stage 6 proper = A + most of B (~35); C stays in the backlog.

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
| 2 | Precision navigation | nav-rtk, nav-indoor, nav-terrain |
| 3 | Firmware development elective | fw-build-ap, fw-debug, fw-driver, fw-px4-module, fw-hil-testing |
| 4 | Autonomy | aut-planning, aut-behavior, ctl-trajectory, ctl-advanced, aut-swarm |
| 5 | Operations and safety | ops-flight-test, ops-risk-sora, ops-human-factors, safety-parachute, sec-threats |
| 6 | Links, power, airframes | link-cellular, link-video-codec, pwr-ice-hybrid, heli-trad, vtol-tailsitter |
| 7 | Applications track | ml-dataset, app-agri, app-inspection, app-lidar; des-structures, des-cad, des-manufacturing |
| 8 | Beyond modules | browser lab checker, widgets, bench kit, flashcards, exam-bank workflow |
| 9 | Verification | security review of new platform features, full fact-check sample, translation review, report |

Rough size: an iteration of 4–5 modules ≈ 25–30k words of Russian source plus ~3× that in translations.

## 5. Decisions for Alex

1. **Order**: the iterations above follow "engineering depth first". Alternatives: applications first
   (faster visible value) or firmware development first (closest to Alex's ESP32/C++ work).
2. **Exam banks**: private repository, local files uploaded through the admin page, or postpone until go-live.
3. **Hardware**: which bench hardware is available (thrust stand parts, ST-Link/J-Link, RTK modules,
   UWB kit) — labs can be written for SITL-only with an optional hardware path.
4. **New modules in all four languages from day one**, or Russian first and translations in a batch.
