# Fact-check: self-study references («Эталон для самопроверки») and rewritten «Самопроверка» criteria — 2026-11

Scope: every added/changed line of `git diff -- content/` (123 tracked files, 326 added lines; the four untracked new modules are excluded).
Method: each number / threshold / expected output / direction claim / «wrong result → cause» was either located in the same module outside the changed lines, or recomputed from the module's formula or code with the module's inputs (Python blocks run in a private scratchpad), or checked against firmware sources on disk (`/tmp/ardupilot-audit/copter472`, `/tmp/bf-migrate/{bf455,bf2025}`, `/tmp/px4-audit-v1.17.0`, `/tmp/inav-audit/inav9`). Nothing under `content/`, `data/`, `scripts/`, `assets/`, `i18n/` was edited.

Verdicts: **confirmed** (in module) · **recomputed OK** · **WRONG** · **not reproducible** (no source in module, cannot be derived) · **not self-checkable** (reader cannot verify alone / unstated number / judgement call) · **wording** (outside-audience wording left).
Rows with verdict confirmed/recomputed OK are grouped per line; every WRONG / not reproducible row carries an exact Russian replacement.

## content/ardupilot

| file:line | statement | verdict | evidence | replacement (RU) |
|---|---|---|---|---|
| aero-wing.md:84,86 | 0.4 м², 2 кг, C_Lmax 1.1 → ≈ 8.5 / 12 / 10.1 м/с; 45° → 1.19·V_s; `AIRSPEED_MIN` ≥ ~1.2·V_s; расхождение 10–20 %; «верь измерению» | recomputed OK | L76: √(2·2·9.81/(1.225·0.4·1.1)) = 8.53; ×1.4 = 11.9; ×1.189 = 10.15; L47, L81 | — |
| ap-companion.md:182,184 | `GUID_TIMEOUT` 3 с; 5–10 Гц; 20 м север / 10 м; z = −10; геозона 50 м | confirmed | L34, L108–110, L146–149, L177–180; `Parameters.cpp:875` default 3.0 | — |
| ap-companion.md:184 | «цель по скорости … идёт реже 2 Гц, сработал таймаут» | WRONG (internal contradiction, minor) | Timeout fires only when the gap between targets exceeds `GUID_TIMEOUT` = 3 с (L31, L178); 1 Гц does not trip it. «≥ 2 Гц» in L113 is a recommended margin, not the trip point | «…— цель по скорости ушла один раз или пауза между целями превысила `GUID_TIMEOUT` (3 с): сработал таймаут; держи частоту не ниже 2 Гц;» |
| ap-ekf.md:88,90 | `ERR` Subsys 11 / ECode 2 → 0; EKF-failsafe Subsys 17; `FS_EKF_ACTION` 1/2 только если режим требует позиции, 3 — из любого; GSF сходится только в движении | confirmed | L84–86, L45; `AP_Logger.h`: GPS = 11, FAILSAFE_EKFINAV = 17 | — |
| ap-heavy.md:93,95 | 8 × 3000 г, 9 кг → 24 кг / ≈ 20.4 кг, T/W ≈ 2.3; без поправки ≈ 2.7; VIBE < 30; газ висения < 0.5 | recomputed OK | L90–91: 24·0.85 = 20.4; 20.4/9 = 2.27; 24/9 = 2.67 | — |
| ap-intro.md:175,177 | `FRAME_CLASS = 1`, `FRAME_TYPE = 0` без `-f`; `FRAME_TYPE = 1` при `-f X`; что держит STABILIZE / ALT_HOLD / LOITER; LOITER до фикса GPS отклоняется | confirmed | L94, L109–115, L156, L170 | — |
| ap-logs.md:137,140,142 | пример разбора (×0.6, 14°, 1.2 с, 75 %, 4 м/с²) — иллюстрация; SITL: единицы м/с², клиппинг 0; `SIM_ENGINE_MUL` 0 → падение, брать 0.5–0.6 | confirmed | L131, L134 (пример помечен как пример, числа не выдаются за эталон) | — |
| ap-lua.md:134 | строки `Scripting2 -> …`, `switch_report: no channel with RCx_OPTION=301` раз в 5 с; `RC9_OPTION 301`; `MOT_STOP_BITMASK`; pytest | confirmed | code L91–108 (`return update, 5000`), L113, L118, L132 | — |
| ap-missions.md:111 | `mission upload: 0` = `MAV_MISSION_ACCEPTED`; три сценария с `ROUTE`; пункты автопроверки | confirmed | L76, L101, L104, L107, L109 | — |
| ap-plane-tuning.md:91,93 | 80 % `THR_MAX`, ~5°, ~10 м; `NAVL1_PERIOD` −5 / +1…2; `TECS_CLMB_MAX`, `TECS_TIME_CONST` +1 | confirmed | L55, L61, L86, L103–106 | — |
| ap-plane-tuning.md:91 | «факт угловой скорости после тюна идёт за запросом ближе, чем до него» | not self-checkable (judgement) | no metric given | «…а в `PIDR`/`PIDP` среднеквадратичная разница `Tar − Act` на одинаковых манёврах после тюна меньше, чем до него (оба числа записаны);» |
| ap-quadplane.md:105,107 | группы таймеров, MANUAL вперёд / QSTABILIZE вверх, `SERVOn_REVERSED` | confirmed | L43, L88, L99–101, L114–118 | — |
| ap-safety-fs.md:81,85 | `ERR` Subsys 5, реакция ≤ 5 с, PASS; `FS_THR_ENABLE = 0`; бит 0 `FS_OPTIONS`; просадка | confirmed | L83, L89, L94–99; `AP_Logger.h` FAILSAFE_RADIO = 5 | — |
| ap-safety-fs.md:81 | «для каждого с RPN выше порога записана мера» | not self-checkable (unstated number) | порог RPN нигде в модуле не задан (L52, L75); шкалы 1–5, максимум 125 | «…и для каждого отказа с RPN ≥ 27 (выбери и запиши свой порог; 27 = 3·3·3 по шкалам 1–5) записана мера» |
| ap-setup-scratch.md:222 | only wording changed («для проверки висения … отдельный чистый лог»); reason 3/4 = RADIO/BATTERY_FAILSAFE, Subsys 5/6 | confirmed | L217–219; `ModeReason.h` 3, 4; `AP_Logger.h` 5, 6 | — |
| ap-sitl.md:151,153 | `takeoff 10`; RTL climb 15 м; 9.5 м; `north_m,east_m,alt_m`; радиус 1 м; `SET_MESSAGE_INTERVAL`; 10–20 с | confirmed | L119, L135–137, L146, L164 | — |
| ap-tuning.md:82,84 | `AUTOTUNE_AGGR` 0.05 → D ниже; откат 20–30 %; перелёт ≤ 10–15 %; сохранение при дизарме с тумблером; резонанс рамы / `INS_HNTCH_HMNCS` | confirmed | L47, L77, L79–80, L88, L97 | — |

## content/betaflight

| file:line | statement | verdict | evidence | replacement (RU) |
|---|---|---|---|---|
| bf-adjustments.md:288–291,293 | `35 names`, `34 slots, 30 initialised`; `d_pitch=50 d_roll=44`; `31 \| LED_DIMMER`; слот 26 → enum 30 PITCH_F, расхождение с 25-го; 47 / 87 для 67 ± 20; 0/1/2 для 988/1500/2012; 1251 мкс → 58 (Python `//` → 57); `p_roll` 45 → 47 → 45; `vtx_power` 1 → 2 → 3 | confirmed | script output L161–172, L191–211, L221–226; L278–279; шаг 6 L247 | — |
| bf-arming-safety.md:400,403,406 | `0x02000020` → 6 RUNAWAY; `0x02100000` → 21 DSHOT_TELEM; `0x01002304` пять флагов, пищалка — RXLOSS (3); `BIT28?` / `THROTTLE FLIP_SWITCH` при чужой таблице; 217 → 292 мс; 1171 vs 1100 мс; гиро > 15 °/с; 670 → 870, 500…1950; газ ≥ 75 % → 250 мс | confirmed | L196–209, L312–316, L343–345, L353–361, L98–100; `FLIP_SWITCH` = индекс 25 в `F2512` (L169), т.е. маска 4.5 `0x02000080` по таблице 2025.12 читается как `THROTTLE FLIP_SWITCH` | — |
| bf-custom.md:101 | меньше размер / больше свободной flash; `get gps` пуст; BUILD KEY; `define AP_<FEATURE>_ENABLED 0` | confirmed | L33, L89, L95–97 | — |
| bf-failsafe.md:99,102 | `failsafe_delay` 1.5 с; Stage 1 → возврат сразу; Stage 2: ANGLE, `failsafe_throttle`, ~1 м/с, дизарм через `failsafe_landing_time`, ре-арм через тумблер; причины «набирает высоту» / «кувыркается» | confirmed | L29, L35, L50, L81–86, L95, L105–109 | — |
| bf-features-tour.md:532,535,539 | Angle 4.9° / 16.6° / 34.9°; Horizon 45° и стик 30 % → 0.300; turtle 60 %: 907 (expo 35) / 1138 (expo 0); предел 15 % / 5 % (4.5); debug[3] ≥ 450, сумма < 1500; 2025.12 — без кривой и −20 | recomputed OK | L295–297, L486–492, L397–402, L530, L87; Horizon: 0.75·(1 − 45/135)·(1 − 0.30/0.75) = 0.300 (формула L123; между 0.333 при стике 0.25 и 0.167 при 0.50) | — |
| bf-filters.md:142 | ≥ 20 дБ; 5–10 дБ над фоном; 100–300 Гц < 10 дБ; < 50–60 °C; bounce-back < 10–15 %; причины | confirmed | L91, L130–132, L158–160, L179–181 | — |
| bf-gps-setup.md:511–514 | DOP ≤ 0.03 (модуль: до 0.02); «GPS only» 10 / 1.57; «M10 default» 28 / 0.87; «VTX noise» trk 28, 9, 4.70; TTFF 25–29 с; 5–23 %; 38400 и выше < 50 %; PDOP ≤ 1.5, v95 ≤ 20 см/с, R95 ≤ 3 м; −2 спутника / −3 дБ; 10 минут | confirmed | L254, L376–382 (TTFF 25.4–28.6), L388–390, L396–398, L504–506 | — |
| bf-hd-osd-video.md:237,413–416 | `17 bits OK`; 131073 = MSP + VTX_MSP; (46, 1) → 3118; варианты B (131072), C, D; clamp 53×20 → 50×18 (напряжение на mAh в строке 17), 30×16 → столбец 29 | confirmed | L226, L60, L243–258, L357, L364–370, L383–385 | — |
| bf-led-buzzer.md:275–280 | `strip length = 10`, `total 380 mA`, `0x00020013`; «SE» → первый бит N,E,S,W; `0x00000000` обрезает ленту; 576 vs 572 мА; 600 / 1920 мА; 1.2 с / 2.2 с; 4.75 В | recomputed OK | L178–179, L196, L201–211 (1920·0.30 = 576; 1920·76/255 = 572), L224, L239–245, L270 | — |
| bf-pid.md:131 | bounce-back < 8 % / > 15 %; overshoot 3–10 % / > 20 %; 0.97 у WASH | confirmed | L77, L93–94 | — |
| bf-rates-rc.md:312,335,340–345 | RMS 2.5 / max 4; RMS 95.4 / max 151 @ 0.71; expo 89; срезы 18/56/93/187/375 = ⌊0.375·f⌋; FF ×1.00 / ×0.27; 158 vs 185 (27 °/с); 670 ± 1 % (± 7 °/с) | confirmed | L212–239, L250–256, L275–279, L337; 0.01·670 = 6.7 | — |
| bf-servos-pwm.md:278–279,283 | PSC 6 / ARR 19 vs PSC 83 / ARR 19999; S9 TIM12 после `resource CAMERA_CONTROL NONE`, M7 на TIM2 (B10 = TIM2 CH3); M5 → TIM8 пейсер; 11.11 мкс/° → `rate` 56, 1612 / 1724 мкс; rate 100 → 1900 мкс, 36° | confirmed | L51–52, L60, L179–196, L207, L230–235 | — |
| bf-setup-scratch.md:345–348 | `armed=1`, 0.07; газ 1300 → `['THROTTLE', 'ARMSWITCH']`; 1400 → 0.412; FAILSAFE через 0.1 с; 112 / 230 мА / 351 (точная 350, 0.3 %); 20–35 %; 12–60 % | confirmed | L161–167, L255–271, L89, L334 | — |

## content/companion (+ content/quiz/fw-reading.json)

| file:line | statement | verdict | evidence | replacement (RU) |
|---|---|---|---|---|
| comp-esp32.md:175 | эхо 200+ символов; S-строки 500 мс (± 50 мс — новый допуск); дизарм → GROUND через 3 с; кабель → FLIGHT через 2 с | confirmed | L53, L67, L80–81 (`LINE_TIMEOUT_MS = 2000`, `GROUND_AFTER_MS = 3000`), L169 | — |
| comp-intro.md:116,118 | компонент 191; порт 5762, потоки выключены; LOITER не замечает отказа, GUIDED — таймаут | confirmed | L42, L61, L73, L93–110 | — |
| comp-jetson-nano.md:417 | `WATCHDOG=1`, перезапуск через 10 с | confirmed | L286, L409 `WatchdogSec=10` | — |
| comp-mavlink.md:142 | 9.5–10.5 Гц; `COMMAND_ACK` 4 / 0; `PreArm:`; `assert` по `PARAM_VALUE` | confirmed | L42, L129–136 | — |
| comp-raspberry.md:175 | 14550 / 14551 / 5760; `Watchdog timeout` через 10 с; запас BEC ×1.5–2, ≥ ~4.9 В; `0x0` / `0x50000`; 10 отключений | recomputed OK | L50, L53 (биты 16 и 18 → 0x10000 + 0x40000 = 0x50000), L88–106, L167–173 | — |
| emb-basics.md:92 | `dt_us` ≈ 1000, std < 10 мкс, max < 50 мкс; приоритет 11 → джиттер / TWDT | confirmed | L89 | — |
| emb-protocols.md:100 | chip id 0x58 / 0x60; ≈ 0.21 мс; пять ошибок подряд; девять тактов SCL | recomputed OK | L61, L95–97; 85 · 2.5 мкс = 0.2125 мс | — |
| eng-ci-configs.md:122 | `all invariants hold`, код 0; `FS_THR_ENABLE = 0` → тест падает; «чек-лист self-review из теории» | confirmed (label mismatch) | L83, L90, L116; в теории L62 он назван «Чек-лист ревьюера … Для одного человека — self-review» | optional: «…прошёл по нему чек-лист из теории (причина, риск, проверка в SITL, откат)» |
| eng-systems.md:106,125,127 | `REQ-SAF-03` (1 с → RTL), `F-07`, `T-12` (1.5 с, 3 м); RPN 162 → 81 при D 6 → 3; FMEA ≥ 15 строк | recomputed OK | L103, L109–118; 9·3·6 = 162, 9·3·3 = 81 | — |
| fw-reading.md:99 | «порядок фильтров гироскопа в `gyroFiltering()` — RPM-notch, динамический notch, LPF1/LPF2» | **WRONG** (firmware fact) | `bf2025/src/main/sensors/gyro.c:435–437`: LPF2 применяется в `gyroUpdate()` до прореживания; `sensors/gyro_filter_impl.c:49–72`: RPM → `notchFilter1/2` → `lowpassFilter` (LPF1) → `dynNotchFilter` последним (то же в bf455: строки 53/62/76). Противоречит и `bf-filters.md:71` («LPF2 → RPM → статические notch → LPF1 → динамический notch»). Источник ошибки — теория самого модуля, L35 (вне diff) | «…а не от ошибки; порядок фильтров гироскопа: LPF2 — ещё на частоте гироскопа в `gyroUpdate()`, затем в `gyroFiltering()` (`sensors/gyro_filter_impl.c`) — RPM-notch, статические notch 1 и 2, LPF1 и последним динамический notch.» (и поправить L35 теории тем же порядком) |
| fw-reading.md:99 | BF: D от `gyroRateDterm` после D-notch/D-LPF; AP: `AC_PID::update_all()` — D от ошибки через `FLTD`, I ограничен `IMAX`, не копится при `limit`; `output_armed_stabilizing()` — roll/pitch → yaw → throttle; строка в консоли MAVProxy | confirmed | L41, L56, L89; `bf2025/flight/pid.c:1184–1196` | — |
| fw-reading.md:25,78–85,95,97,113,125; quiz/fw-reading.json:83 | wording only («страница разбора в своём репозитории», 6–10 строк карты, четыре ответа) | confirmed | L92–94 | — |
| mav-component.md:97 | `rangefinder1` ~10 м минус «рельеф», `RFND`; «несколько сотен миллисекунд»; `RF_OFFSET_CM`; синус | confirmed | L37 (0.5 с), L89–95 | — |
| mav-multi-vehicle.md:114,116 | 15 м / 5 м (`MIN_H`, `MIN_V`); 2 × 10 м/с, 0.5 + 0.5 + ~1.5 с → ~50 м, ~60 м; `--mcast`, `FOLL_SYSID`; потеря ведущего → стоит | recomputed OK | L41 (20 м/с · 2.5 с = 50 м), L51, L81, L100, L131–132 | — |
| mav-protocol.md:113 | CRC не сходится при порче payload и seq; `SYS_STATUS` — extension-поля; `PAYLOAD_STATUS`; 20 % | confirmed | L67, L102–111 | — |
| mav-routing.md:94,99 | 120 ± 40 мс и 5 %; 300 ± 150 мс и 15 %; TCP → «телеметрия из прошлого», секунды | confirmed | L61, L72, L88–91 | — |
| mav-sdk.md:112 | `COM_OF_LOSS_T` / `GUID_TIMEOUT`; обрыв 5 с | confirmed | L87, L107–110 | — |
| mav-services.md:111,113 | `loss=0.25`; C-cast (1 → 1.0) vs bytewise (1 → 1.4e-45); `AUTOPILOT_VERSION.capabilities` | recomputed OK | L50, L103–109; `struct.unpack('<f', struct.pack('<i', 1))` = 1.4e-45 | — |
| nav-vtrn.md:227 | 6 / 28 / 293 м; медиана ≤ 0.5 м; > 3σ; `GPS2_TYPE = 14`; ≤ 3 м; +60 м → `GPS Glitch`, `XKF4.SP` > 1 | confirmed | table L117–121 (5.9 / 27.9 / 292.7), L193, L205–211, L224–225 | — |
| payload-gimbal.md:105,107 | `MNT1_RC_RATE` 0 / 30; follow vs `YAW_LOCK`; `CAM` каждые 5 м; ~10 %; param5 | confirmed | L38, L46, L62, L80–100, L114 | — |
| per-camera.md:111 | 30–60 / 60–120 / 150–300 мс; 5–20 мс монитора; ~8 КБ на кадр; I-frame 0.5–1 с | recomputed OK | L54, L66, L103, L108; 2 Мбит/с / 30 / 8 = 8.3 КБ | — |
| per-cv.md:106 | 90 / (90 + 10) = 0.90; 90 / 100 = 0.90; 20 %; 5 порогов | confirmed | L97–102 | — |
| per-depth-avoid.md:93 | азимут 5–40°; сектор 180° = 65535; 6 м, запас 2 м, a = 3, L = 0.3 → ≈ 4.1 м/с; ~3 м (`AVOID_MARGIN = 3`) | recomputed OK | L55, L85, L91; v·0.3 + v²/6 = 4 → v = 4.08 | — |
| per-edge-ml.md:25,106 | p50/p95/p99/max; p99 вдвое хуже на 20-й минуте; FP16 почти бесплатен; INT8 0.5–2 пункта mAP; ≤ 80 мс | confirmed | L35, L47, L50, L58 | — |
| per-geometry.md:120 | RMS < 1 px; f_x = (W/2)/tan(HFOV/2); (25.0, −8.0); 1° → ~1 м на 60 м; +5 % → 5 %; 50 мс · 60°/с = 3° | recomputed OK | L37, L73–74, L109–115 (alt = 60): 60 · 0.01745 = 1.05 м | — |
| per-landing.md:110 | сторона < 20 px; `PL`: `TAcq = 1`, `pX/pY` → 0; `PLND_STRICT` 0 / 1 / 2 | confirmed (log fields only in firmware source) | L33, L54; `AC_PrecLand/LogStructure.h:46` `"PL" … "TimeUS,Heal,TAcq,pX,pY,…"` | — |
| per-landing.md:110 | «график дальности по маркеру, сверенный с рулеткой на трёх высотах» | not self-checkable (unstated tolerance) | допуск не задан ни здесь, ни в шаге 1 | «…сверенный с рулеткой на трёх высотах (расхождение в процентах записано для каждой высоты и не растёт с высотой быстрее, чем падает размер маркера в пикселях)» |
| per-mapping.md:98 | 100 м, 84° / 62° → 180 × 120 м; 24 м; 54 м; ~0.5 GSD; `TRIG` | recomputed OK | L42, L47–48, L93; 200·tan 42° = 180; 200·tan 31° = 120; 120·0.2 = 24; 180·0.3 = 54 | — |
| per-visual-nav.md:75 | < 0.5 px; 0.5–2 % пути (0.1–0.4 м на 20 м); `XKF4.SP/SV`, `VISP`; «замёрзшая» поза | recomputed OK | L32, L50, L54, L62, L66, L69 | — |

## content/design

| file:line | statement | verdict | evidence | replacement (RU) |
|---|---|---|---|---|
| aero-stability.md:205 | Skywalker 1830: NP 115 мм при V_h = 0.6; запас 11 % на 90 мм и 6.6 % на 100 мм; (L/D)max = 11.3 на 10.8 м/с; 5–15 %; ±3 мм | confirmed | script output L170–181, L187–193, L203 | — |
| ctl-allocation.md:296 | dead cat: передние +15.4 % = 0.15/0.13; `failure motor off -i 1`, `motor_stop_mask`, `handled_motor_failure_mask`; ±5 %; 90 % | recomputed OK | L151–170 (0.15/0.13 = 1.154), L258, L293–294 | — |
| des-sizing.md:248 | 3.0 → 3.73 → 4.29 кг за три итерации; 17″ — 28.8 мин, T/W 2.05; 10 %; ±15 % | confirmed | L193–202, L226, L246 | — |

## content/electronics

| file:line | statement | verdict | evidence | replacement (RU) |
|---|---|---|---|---|
| el-battery-packs.md:90 | 25 мОм × 6 / 4 ≈ 38 мОм (+10–20); 60 А → 2.3–3.5 В; 180 Вт при 0.05 Ом; ≈ 1.85 кг, ≈ 195 Вт·ч/кг; ≤ 45 °C; без деления на P — 150 мОм; коэффициент 0.6; 30 % | recomputed OK | L42–44, L64, L79, L84–88; 25·6 = 150; 60·(0.038…0.058) = 2.3…3.5; 363/1.85 = 196 | — |
| el-battery-packs.md:90 | «ёмкость ≥ 90 % паспорта × P» | confirmed | шаг 4, L86: «Сравнить с паспортом × P: норма ≥ 90%» | — |
| el-dronecan.md:94,96 | 55–65 Ом; ~60 / 120 / 40 Ом / ∞; node ID 10, ≤ 125; «Duplicate Node»; ESC 400 Гц ~15–20 %, шина < ~50 %; перезагрузка после `CAN_*` | recomputed OK | L36, L42, L59, L65, L76, L80; 120/2 = 60, 120/3 = 40 | — |
| el-emi.md:99,101 | 30 % поля; 60 А в 10 см → 120 мкТл, пара — 3.6 мкТл; NaN при отсутствии участка < 2 А; NSats ≥ 2; C/N0 3–5 дБ; помеха опускает C/N0 всех спутников | confirmed | L32–37, L43, L46, L90–92 (`b[cur < 2].mean()`), L96 | — |
| el-kicad.md:85,87 | 100 А · 0.5 мОм → 50 мВ, 5 Вт, шаг 5 мА, CAL = 2048; 81.92 мВ; 0.8 / 2.8 / 7.2 мм; мОм вместо Ом → CAL в 1000 раз; `PWR_FLAG`; Kelvin | recomputed OK | L41–49; 0.00512/(0.005·0.0005) = 2048; с 0.5 вместо 0.0005 → 2.048 | — |
| el-measure.md:77,89 | DShot 1046 → CRC 6, кадр 0x82C6; CRSF `0xC8`, `0x18`, `0x16`; десятки / сотни мВ p-p | recomputed OK | L81, L85–86; v = 1046·2 = 0x82C; (0x82C ^ 0x82 ^ 0x8) & 0xF = 6 | — |
| el-peripherals.md:91 | NSats ≥ 6; `B5 62`; нет КЗ 5 В / 3.3 В на GND | confirmed | L61, L74, L83, L89 | — |
| el-power-design.md:90 | BEC 1 А / 3–5 А; ≥ 1.5 × суммы; 470–1000 мкФ 35 В / 1000 мкФ 50 В; 1.8–3.6 В при 60 А; ~0.2 В на 20 см 14 AWG; > 300 Гц; 10–15 мм; 100 мВ p-p | recomputed OK | L42, L50, L55, L79, L82, L88; 60·(0.03…0.06) = 1.8…3.6; 0.4 м · 8.3 мОм · 60 А = 0.2 В | — |
| el-redundancy.md:74,76 | квад / гекса (T/W ≥ 2) / X8; 30 см 12 AWG, 32 А → 3.1 мОм, 0.10 В, 3.2 Вт; 1.3 × тока ветки; просадка < 5 м; мотор 3 → маска 4 | recomputed OK | L27–29, L39, L48, L71, L78; 0.0031·32 = 0.10 В; 0.0031·32² = 3.2 Вт | — |
| el-wiring.md:101,103 | 1.2 мВ / 5 А → 0.24 мОм; 8 мВ → 1.6 мОм; 1–5 мОм; 14 AWG: 2.5 мОм, 0.15 В, 9 Вт; 18 AWG: 0.38 В, 23 Вт; 3–5 см | recomputed OK | L50, L55, L64, L87, L98 | — |
| el-wiring.md:101 | «газ на минуту без пропов — соединение не нагрелось» | not self-checkable (judgement) | критерий «не нагрелось» без числа; без пропов ток мал, нагрев плохого контакта не проявится | «…проверена измерением падения напряжения под током (R = U/I — доли миллиома, как в эталоне ниже)» — проверку «газ на минуту» оставить только как дополнительную |
| rf-antennas.md:96,98 | +6 дБ = ×2 дальности → ~6 дБ на удвоение; 90° линейной — 10–20 дБ; RHCP/LHCP 15–20 дБ; КСВ ≤ 1.5; минимум на 5.4 при 5.8; SMA/RP-SMA | confirmed | L47, L50, L65, L77, L91 | — |
| rf-link-budget.md:96 | 1 км: FSPL ≈ 100.2 дБ, ≈ −78 дБм, запас ≈ 34 дБ; 12 дБ на ≈ 12–13 км; поправка 5–10 дБ; чувствительность + 10 дБ | recomputed OK | L88–94; 20·log10(2440) + 32.44 = 100.19; 24 + 2 − 4 − 100.2 = −78.2; (33.8 − 12)/20 → ×12.3 | — |

## content/estimation

| file:line | statement | verdict | evidence | replacement (RU) |
|---|---|---|---|---|
| est-alt-sources.md:85,87 | `RNGFND1_GNDCLR`; метры от прогрева; пропвош −1…−3 м; шум 0.2–0.5 м RMS; POSXY 0, VELXY 5, POSZ 2, YAW 1 / 0; «PreArm: Need Position Estimate»; v = (flow − ω) × h; трава | confirmed | L30–32, L45, L59, L63, L72, L79, L82 | — |
| est-attitude.md:109,117,119 | 0.5 °/с → 30° за минуту; ~3°/мин → 30° за 10 минут; источники курса; FRD, в покое −g; `trust = 0`; `Ki = 0` → bias; kp ×10 / ÷10 | confirmed | L38, L43, L45, L51, L57, L86–90, L112–115 | — |
| est-gnss.md:114 | HDOP около 1 и ниже; разброс метр–два; p95 и max кратно у стены; RTK не лечит многолучёвость | confirmed | L108–110 | — |
| est-gnss.md:114 | «спутников 12 и больше» (подано как часть «эталона выше») | confirmed (minor mismatch) | теория L44: «6 — минимум, 12+ — норма с несколькими созвездиями»; но блок «эталон выше» (L109) называет «20 и больше» — два разных числа под словом «эталон» | optional: «…спутников не меньше 12 (с несколькими созвездиями обычно 20 и больше)…» |
| est-kalman.md:125,127 | базовый прогон: bias ≈ 0.2, RMS ≪ 0.3 м, NIS ≈ 1 | recomputed OK | код модуля: `bias: 0.202 RMS h error: 0.044 NIS mean: 1.0` | — |
| est-kalman.md:127 | «`q_acc` ×10 — … RMS ошибки h растёт» | recomputed OK | скрипт: RMS 0.044 → 0.068 (NIS 0.99). Для ×0.1 скрипт даёт RMS 0.039 — НИЖЕ базового; эталон про ×0.1 молчит и обратного не утверждает. Теория (L31, L50) говорит только «Q — насколько модель может ошибиться» и «NIS 5 — Q или R малы»; на этом сигнале NIS от `q_acc` почти не меняется (0.99 / 1.00 / 1.01) — читатель, ждущий по L50 роста NIS при ×0.1, его не увидит | optional addition: «`q_acc` ×0.1 на этом сигнале даёт RMS чуть ниже базового (≈ 0.039 против 0.044 м) и NIS по-прежнему около 1: модель здесь точная, и меньшее Q — не ошибка. Задержка оценки v от `q_acc` почти не зависит (≈ 0.2 с), а при `r_baro` ×10 растёт до ≈ 0.9 с.» |
| est-kalman.md:127 | «`r_baro` ×10 — среднее NIS падает намного ниже 1» | recomputed OK | скрипт: NIS 0.10, RMS 0.045, задержка v ≥ 1.8 м/с 900 мс (база 210 мс) | — |
| est-kalman.md:127 | скачок +5 м на 1 с с воротами — отброшен, оценка не прыгает; на 10 с — уходит к +5 м | recomputed OK | скрипт: 1 с — max |ν| 18, ошибка ≤ 0.14 м (без ворот 5.6 м); 10 с — первое принятое измерение через 7.6 с, к концу скачка ошибка 5.1 м | — |
| est-kalman.md:127 | NIS далеко от 1 при R = 0.3 вместо 0.3²; bias не сходится при неверном знаке; `XKF4.SH` < 0.5 / > 1 | recomputed OK | скрипт: R = 0.3 → NIS 0.30; знак «+» → bias −0.202; L62 | — |
| est-sensors.md:78,80 | \|bias\| < 0.1 °/с, std 0.05–0.3 °/с; 0.2 °/с; ≤ 0.5°, 90 ± 1°; ±5 %; 0.01–0.05 °/с на °C, 20 °C; 1–3°; soft iron | confirmed | L31–33, L40, L49, L69–75 | — |
| nav-indoor.md:229 | `AHRS: waiting for home`; p95 ≤ 0.05 м, `SP < 0.2`; 250/250 ≈ 50/50; Δτ 200 мс → p95 ≈ 0.5 м; `SP > 1` только на 550 мс; ворота 5σ ≈ 1.5 м; 1.7 с; 3 ± 0.3 м; 0.5 м | confirmed | L71, L113–121, table L145–151 (p95 0.029 / 0.053 / 0.514), L155, L181, L220–226 | — |
| nav-resilience.md:86,88–97 | таблица-эталон: NSats → 0, SP/SV растут, EKF failsafe; шум 5 м; скачок ~50 м, `EK3_GLITCH_RAD` 25 м; `XKF4.SM` > 1, «Compass variance», yaw reset; «десятки секунд, не минуты»; `SIM_GPS_DISABLE` до 4.7; `FS_EKF_ACTION = 0`; AltHold / Land по месту | confirmed | L32–36, L41, L48, L73–76 | — |
| nav-terrain.md:136 | ~24 м (база) / ~20 м (дальномер); 35 % · 10 м/с = 3.5 м/с против `WP_SPD_UP` 2.5; «waiting for terrain data», `pending = 0`; `ERR Subsys 23`, `MODE Rsn 11`; ≤ 3 % | confirmed | L44, L52, L84–91, L107, L114, L133; `AP_Logger.h` FAILSAFE_TERRAIN = 23; `ModeReason.h` TERRAIN_FAILSAFE = 11 | — |

## content/foundation

| file:line | statement | verdict | evidence | replacement (RU) |
|---|---|---|---|---|
| diag-troubleshooting.md:167 | `RXLOSS` при выключенном приёмнике; флаг `THROTTLE` при неверном `min_check`; пять переключений, ±2 м | confirmed | L36–37, L131–134, L159–160 | — |
| eng-method-101.md:74 | «В рубриках итоговых проектов курса это отдельная строка» | wording (outside audience) | «рубрики» — шкала оценивания внешним проверяющим; предложение осталось после замены «сдать» → «считать законченным» | delete sentence (или: «В итоговых проектах курса эта нить — отдельный пункт самопроверки.») |
| eng-method-101.md:119 | 8 и больше требований; REQ-01…REQ-07; три абзаца README; «дата — что сделано — числа» | confirmed | L89, L92, L106–110 | — |
| f-aero-props.md:99 | 7": 350 г на мотор, 1050 г при T/W 3:1, 13 А, ≈ 15 мин на 6S 4000 мА·ч; ≤ ~40 %; 5" 4–6, 7" 8–10, 10–15" 10–14 г/Вт; 5–6 на 15" — ошибка; 24 / 22.2 ≈ 1.08; 20 % | recomputed OK | L57, L79–82, L88–94; 0.8·4/13·60 = 14.8 мин | — |
| f-components-choice.md:109 | T/W 3.43, ≈ 10.5 А, ≈ 18 мин; +400 г: 2.67, 13.3 А, ≈ 14.5 мин; 5–10 %; T/W ≥ 2; 4–6 критериев | recomputed OK | L62, L95–104; 4800/1400 = 3.43; 215/22.2 + 0.8 = 10.5; 3.2/10.5·60 = 18.3; 4800/1800 = 2.67; 3.2/13.3·60 = 14.4 | — |
| f-electricity-101.md:100 | ≤ 0.05 В; 4.75–5.25 В; (25.2 − 24.4) / 20 = 0.04 Ом; 10–20 % / > 30 % | confirmed | L51, L89–95 | — |
| f-esc-firmware.md:79,81 | eRPM / (полюса / 2), для 14 — eRPM / 7; 24 кГц — меньше потерь и нагрева, 48 кГц — тише и плавнее; 5" — 48, большие винты — 24 | confirmed | L38, L42, L77 | — |
| f-fc-sensors.md:111 | модель повторяет наклоны; барометр ≈ 1 м на метр; курс меняется | confirmed (qualitative) | L35–37 | — |
| f-frame-mech.md:83 | RPM/60; 5" ~250–350, 7" ~120–200, 10" ~80–100 Гц; резонанс не движется с газом; щелчок по лучу; мягкое крепление → низкочастотный резонанс | confirmed | L32, L40, L43, L46, L96 | — |
| f-frame-mech.md:83 | «низкочастотный пик 20–40 Гц — слишком мягкое крепление» | not reproducible (число) | в модуле для мягких демпферов названы f₀ 15–20 Гц (X8) и 60–80 Гц (5") (L49), диапазона 20–40 Гц нет | «…в спектре вырос низкочастотный пик (десятки герц, ниже частоты моторов) — это слишком мягкое крепление полётника, а не пропы.» |
| f-mechanics.md:80 | 1400 гс / 350 гс; 3 м/с² → 1830 гс; ×1.155; ×1.41; I ≈ 0.0032 кг·м²; запас 20 %; α ≈ 125 и ≈ 6.7 рад/с²; I_yaw наибольший | recomputed OK | L29–35, L47–49, L62; 4·0.035·0.15² = 0.00315; 1.4·12.81/9.81 = 1.83 кгс | — |
| f-motors-esc.md:100 | лампа вспыхнула и погасла; eRPM на 10 % газа; ошибки ≤ 1 % | confirmed | L90–97 | — |
| f-physics.md:103 | газ висения между 1/(T/W) и √(1/(T/W)); в примере 24–49 % | confirmed | L95 (√0.24 = 0.49) | — |
| f-power.md:111 | t ≈ 0.8 × А·ч / ток × 60 (Li-Ion 0.85); 6S 1300: 80 А → ~1 В (4.0 → 3.84 В/эл.), через 150 циклов — 2.9 В; ~2.7 В/эл. в кейсе 10" | recomputed OK | L46, L49, L52, L107; 0.012·80 = 0.96 В; 0.036·80 = 2.9 В; 16.2/6 = 2.7 | — |
| f-regulations.md:148 | восемь строк конспекта; шесть пунктов шага 4 | confirmed | шаблон L132–139 (8 строк), L127 (6 пунктов) | — |
| f-remote-id-security.md:118 | `tcp:127.0.0.1:5763`; без ключа — нет, с ключом — да, телеметрия читается; ловушка MAVProxy / канал 0; `ss -tulpn`; OpenDroneID | confirmed | L90, L104, L113, L116 | — |
| ops-case-studies.md:119 | три инцидента, шесть пунктов, процесс, а не человек; CHANGELOG | confirmed | L24, L105–117 | — |
| ops-field.md:154 | элементы шага 1; строка журнала; расстояние слышимости пищалки; расхождение ≤ 10–15 м | confirmed | L136–137, L152 | — |
| ops-maintenance.md:127 | `OK` / `ПРОВЕРИТЬ: …`; IR ×1.5–2; 0.03–0.05 В; 5+ логов; λ = 1/1000 ч, 100 ч: квадро 0.67, гекса ≈ 0.90; 1/3000 выше | recomputed OK | L34, L81, L88, L118, L122–125; e^(−0.4) = 0.670; p = e^(−0.1): p⁶ + 6p⁵(1 − p) = 0.895 | — |
| ops-weather.md:108 | 7 м/с на 10 м → ≈ 9.7 м/с на 100 м (α = 1/7); ×1.3–1.5; 50–60 %; `DA 3025 м, ρ/ρ0 0.74, тяга 74%, мощность висения 116%` | recomputed OK | L27–28, L33, L99; 7·10^(1/7) = 9.73 | — |

## content/inav

| file:line | statement | verdict | evidence | replacement (RU) |
|---|---|---|---|---|
| inav-ipf.md:114,116 | DELAY(3000) поверх «напряжение < порога», AND, STICKY со сбросом тумблером, `Override RC Channel`; пять строк таблицы истинности; порог 50 м вместо 300 м; причины «без DELAY» / «без STICKY» | confirmed | L50, L60–61, L66, L82, table L103–108 (5 строк; пятая — «RTH держится до сброса») | — |
| inav-missions.md:110 | контроль генератора: `wp 0 1 504500000 305200000 3000 0 0 0 0`; `wp 3 4 0 0 0 1 0 0 165`; lat/lon местами → ошибка в 1–2-м знаке | recomputed OK | код шага 2б запущен с его же координатами: вывод `wp reset`, `wp 0 1 504500000 305200000 3000 0 0 0 0`, …, `wp 3 4 0 0 0 1 0 0 165`. Мелочь: это первая строка `wp` (перед ней печатается `wp reset`), и она отличается от ручного примера шага 2 (`505000000 304000000`) | optional: «первая строка с точкой — `wp 0 1 504500000 …`» |
| inav-setup-scratch.md:252–255 | 4 строки `mmix`; `MSP_RC` при `map AETR` — газ (4-е значение) 1000; `map TAER` → газ 1500, тангаж 1000; `RX` через 0.5 с; 1132 / 435 / 104; scale < 400 — перевёрнута дробь; DSHOT300 → MULTISHOT; `FAKE`, `receiver_type = MSP` | recomputed OK | L57, L104, L121, L130–138, L144, L158–167; 400·1120/1030 = 435 (перевёрнутая дробь даёт 368) | — |
| inav-setup-wing.md:237–240 | ЦТ 126–138 мм (15–20 % MAC), MAC LE = 92 мм; 8.4 / 12.5 / 15.5 мм; таблица серв (вправо — левый вверх, правый вниз; нос вниз — оба вверх); `failsafe_throttle_low_delay = 0`; `nav_rth_allow_landing = NEVER`; 60 м; 0.5 с, газ 1700 | confirmed | L120–125, L130–132, L143–149, L173–179, L188–200, L256–257 | — |

## content/link

| file:line | statement | verdict | evidence | replacement (RU) |
|---|---|---|---|---|
| link-digital-video.md:79,81 | 10 замеров, медиана и максимум; режим с меньшей частотой кадров / битрейтом → больше задержка; порядок «битрейт → задержка → блоки → фриз» | confirmed | L28–29, L64, L74 (конкретных мс модуль не задаёт — эталон это прямо оговаривает) | — |
| link-protocols.md:114,116 | `serialrx_provider = CRSF`, `serialrx_inverted = OFF`, `serialrx_halfduplex = OFF`; 988–2012, центр 1500; `RXLOSS`; F4 + SBUS без инвертора; LQ есть, напряжения нет | confirmed | L39, L61, L93–95, L109–111, L132 | — |
| link-telemetry-radios.md:111,113 | дБм ≈ RSSI / 1.9 − 127 → RSSI 190 = −27 дБм; (RSSI − noise) / 2; 18 дБ ≈ ×8; 64 → 32: +3 дБ; ~8 КБ/с на 64 кбит/с; `txbuf`; > ~190 на 1 м; `RT&W`, `RTZ` | recomputed OK | L27–28, L33, L53–56, L85–91; 190/1.9 − 127 = −27.0 | — |

## content/math

| file:line | statement | verdict | evidence | replacement (RU) |
|---|---|---|---|---|
| math-linalg-rot.md:126 | шаг 2: акселерометр ≈ (−1.70, −3.30, −9.08) м/с², модуль 9.81; yaw не влияет | recomputed OK | R_nb = Rz(135°)·Ry(−10°)·Rx(20°) (L52); R_nbᵀ·(0, 0, −9.81) = (−1.7035, −3.3042, −9.0783) | — |
| math-linalg-rot.md:126 | шаг 3: Rx(90°)·Ry(90°)·(1,0,0) = (0, 1, 0); Ry(90°)·Rx(90°)·(1,0,0) = (0, 0, −1); для 1° разница ≈ 3·10⁻⁴ | recomputed OK | матрицы L44–46; разница для 1° = (0, 3.046·10⁻⁴, 2.7·10⁻⁶), норма 3.046·10⁻⁴ = (π/180)² | — |
| math-linalg-rot.md:126 | шаг 4: при 1 мс q → (−1, 0, 0, 0); при 50 мс ошибка в z; без нормировки \|q\| ≈ 1.04 | recomputed OK | q ← q ⊗ (1, ω·Δt/2) (L73): 1 мс → (−1, 0, 0, 1·10⁻⁴); 50 мс → z = +0.017 (125 шагов) или −0.008 (126); без нормировки \|q\| = 1.0398 / 1.0401 (и 1.0008 при 1 мс) | — |
| math-linalg-rot.md:126 | ошибки: R_nb вместо R_nbᵀ → зависит от yaw; порядок (w,x,y,z) / (x,y,z,w) | confirmed | R_nb·(0,0,−g) = −g·(третий столбец), зависит от ψ; L70 | — |
| math-ode-dyn.md:108 | шаг 1: kp/(kp + b) ≈ 0.83 при kp = 1 и ≈ 0.94 при kp = 3; за T = 1 с не доходит; с ki = 5 → 1 | recomputed OK | код модуля (b = 0.2): T = 1 с → 0.582 и 0.904; T = 10 с → 0.8333 и 0.9375; (3, 5, 0.05) → 1.000 | — |
| math-ode-dyn.md:108 | kp = 50: ζ ≈ 0.5, перелёт ≈ 16 % | recomputed OK | s² + (1/τ + b/J)·s + (b + kp)/(τJ) = s² + 50.2·s + 2510: ω₀ = 50.1, ζ = 0.501; код: пик 1.155 при установившемся 0.996 → 16.0 % | — |
| math-ode-dyn.md:108 | «колебания ≈ 44 рад/с — столько же даёт мнимая часть полюсов» | **WRONG** (minor, число) | полюса −25.1 ± 43.36j; по коду модуля период между пиками 0.1440–0.1445 с → 43.5–43.6 рад/с. Ни расчёт, ни симуляция не дают 44 | «…ζ ≈ 0.5, перелёт ≈ 16 % и колебания ≈ 43 рад/с (период ≈ 0.145 с) — столько же даёт мнимая часть полюсов −25.1 ± 43.4j.» |
| math-ode-dyn.md:108 | шаг 3: \|G\| ≈ 0.894, φ ≈ −26.6°; «при T_s = 1/8000 все три способа дают эти числа» | not reproducible as stated (нужен допуск) | аналитика 0.8944 / −26.57° верна. Численно при 1/8000 (y[k] = y[k−1] + k·(x[k] − y[k−1])): Эйлер вперёд 0.902 / −24.5°, назад 0.888 / −26.3°, точная 0.894 / −25.5° — до 1 % по амплитуде и до 2° по фазе | «…при T_s = 1/8000 все три способа совпадают с этими числами в пределах 1 % по амплитуде и 1–2° по фазе (у Эйлера вперёд ≈ 0.90 и −24.5°);» |
| math-ode-dyn.md:108 | «при T_s = 1/100 у Эйлера вперёд k ≈ 6.28, полюс 1 − k ≈ −5.28 — выход растёт без ограничений» | not self-checkable (число верно, постановка шага не даёт его проверить) | k = 2π·100/100 = 6.283 ✓. Но шаг 3 велит подать синус 50 Гц: при f_s = 100 Гц это частота Найквиста, отсчёты sin(π·k) равны нулю (≈ 10⁻¹⁴). Выход Эйлера вперёд растёт только из шума округления (до 10⁵⁵), два других способа дают нули — сравнить амплитуду и фазу при 1/100 читателю нечем | add: «При T_s = 1/100 синус 50 Гц попадает точно на частоту Найквиста — его отсчёты нулевые; для этой проверки подайте скачок или синус 10 Гц: выход Эйлера вперёд меняет знак и растёт в 5.28 раза за шаг.» |
| math-ode-dyn.md:98 (шаг 1) vs :108 | «Найдите kp, при котором начинаются незатухающие колебания» — эталон числа не даёт | not self-checkable | в этой модели с одним P незатухающих колебаний нет: ζ = 50.2/(2·√(50·(kp + 0.2))) > 0 при любом kp; код модуля до kp = 6000 даёт затухающий отклик (пик ≤ 1.87). Граница есть только у дискретной схемы при kp порядка 10⁵ | add to эталон: «Незатухающих колебаний с одним P эта модель не даёт: ζ = 50.2 / (2·√(50·(kp + 0.2))) убывает, но остаётся больше нуля (kp = 500 → ζ ≈ 0.16, kp = 5000 → ζ ≈ 0.05). Правильный результат шага — таблица kp → ζ → частота, а не одно граничное kp.» |
| math-ode-dyn.md:101,104,106 | τ_m 15–30 мс (5"), 80–150 мс (15"); f_c > f_s/π; T_s ≤ τ/10 | confirmed | L31, L63 | — |
| math-prob-est.md:95,100,102 | ≈ 100.24 м, σ ≈ 0.098 м; инновация 6.3 м, S ≈ 0.51 м, «больше 12·S», ворота 3·S ≈ 1.5 м | recomputed OK | (4·101.3 + 100·100.2)/104 = 100.242; 1/√104 = 0.0981; 101.3 − 95 = 6.3; √0.26 = 0.510; 6.3/0.51 = 12.4; 3·0.51 = 1.53 | — |
| math-prob-est.md:102 | R·P·Rᵀ = [[0.725, 0.875], [0.875, 5.525]] для 45°; «несколько процентов» для 2000 точек | recomputed OK | P = [[4, 2.4], [2.4, 2.25]], R = Rz(+45°): [[0.725, 0.875], [0.875, 5.525]]. (При повороте на −45° получится [[5.525, −0.875], [−0.875, 0.725]] — возможная причина «несовпадения» у читателя.) Ошибка выборочной дисперсии ≈ √(2/2000) = 3 % | optional addition: «Если получилось [[5.525, −0.875], [−0.875, 0.725]] — облако повёрнуто на −45° (применена Rᵀ).» |
| math-prob-est.md:100,102 | ±3σ — 0.3 %; ARW при τ = 1 с, bias instability — минимум; причины | confirmed | theory | — |

## content/px4

| file:line | statement | verdict | evidence | replacement (RU) |
|---|---|---|---|---|
| px4-architecture.md:101,103,105 | сотни герц / десятки / частота контура угловых скоростей; `uorb top`, `listener`; `VehicleCommand`, `OffboardControlMode` | confirmed | L28, L44, L61–63, L92–98 | — |
| px4-companion-jetson.md:135,137 | пины 8/10 — OK на одном порту; «Permission denied» — dialout / консоль; `MAV_1_CONFIG` не Disabled, скорость, `px4_msgs`; 2–3 с; задержка ×2 при троттлинге | confirmed | L41, L87, L105, L130–133, L140–147 | — |
| px4-control.md:91,93 | `MC_ROLLRATE_K` — общий множитель P, I, D; ×2 → быстрее, перелёт больше, затухание дольше, частота выше | confirmed | L31, L87–89 | — |
| px4-intro.md:160,162 | `MIS_TAKEOFF_ALT` 2.5 м; порт 14550; Position / Altitude / Stabilized; «ветра в SITL нет» | confirmed | L37–40, L153–155 | — |
| px4-ros2.md:162,164 | 3 м = z = −3; 10 с, радиус 5 м; 2–4 с, перелёт ≤ 0.5 м; `COM_OF_LOSS_T` 1 с; < 2 Гц; агент 8888, `px4_msgs` | confirmed | L27, L32, L42, L82, L102, L111, L145, L159, L172–180 | — |
| px4-setup-scratch.md:189 | HTE = 1/(T/W) ± 0.01; в SIH `MC_ROLLRATE_D` после тюна около нуля | confirmed | L53, L145 (0.488–0.493 против 0.4905), L152 (0.0030 → 0.0001) | — |

## content/ros2

| file:line | statement | verdict | evidence | replacement (RU) |
|---|---|---|---|---|
| ros2-app-arch.md:91,93,95 | `recover_s` (например, 1 с) > 0.5 с → ещё DEGRADED; DEGRADED / FAILSAFE; `After=`, `BindsTo=`; четыре узла | confirmed | L50–53, L60, L82–88, L103–106 | — |
| ros2-ardupilot.md:102,104 | `GUID_TIMEOUT` 3 с; ENU/NED, `frame_id`; takeoff в GUIDED; 20+ уставок | confirmed | L44–51, L87, L98–100 | — |
| ros2-basics.md:89,91 | x = 0.1, z = −0.05, pitch 0.5; FLU: +pitch вокруг y наклоняет x к −z → «камера смотрит вниз»; RELIABLE на BEST_EFFORT; `_v1`; `--clock`, `use_sim_time` | recomputed OK | L87 (команда), L43, L48, L53, L95–102; Ry(θ)·(1,0,0) = (cos θ, 0, −sin θ) — при θ = +0.5 ось x получает −z, в FLU это вниз | — |
| ros2-from-ros1.md:90,93,95 | `call_async`; `declare_parameter`; `while` + `rate.sleep()` → таймер | confirmed | L61–67, L100–105 | — |
| ros2-nav.md:79,81,83 | v·0.3 + v²/(2·3) = 8 − 2 → v ≈ 5.2 м/с; 6.0 м/с без задержки (d = 6 м); ≈ 6.9 м/с без запаса | recomputed OK | входные L73 (3 м/с², 8 м, 2 м, 0.3 с): v² + 1.8·v − 36 = 0 → v = 5.17; √(2·3·6) = 6.00; √(2·3·8) = 6.93. Согласуется с `per-depth-avoid` (6 м → 4.1 м/с). Замечание: теория самого модуля (L54) даёт только v ≤ √(2·a·d) — формула с задержкой реакции в ros2-nav появляется лишь в эталоне | optional: добавить в L54 теории «…с задержкой реакции t: v·t + v²/(2·a) ≤ d» |
| ros2-px4.md:93,95 | (а) Hold → DONE; (б) Ctrl+C → `COM_OF_LOSS_T`, `COM_OBL_RC_ACT`; (в) статус > 1 с → ABORT; квадрат 10 × 10 м на 5 м; z = −высота | confirmed | L44, L53–54, L78, L85–88 | — |

## content/tools

| file:line | statement | verdict | evidence | replacement (RU) |
|---|---|---|---|---|
| ctl-guidance.md:114,116 | перелёт 3.0 / 1.0 / 0.9 м, коридор с 35 / 35 / 91 м; L1 ≈ 73 м (18 м/с, 17 с, 0.75); трапеция 7.0 с, S-кривая 7.5 с, рывок ≤ 10 м/с³ | recomputed OK | код шага 1 запущен: три строки совпали; 0.318·0.75·17·18 = 73.0; трапеция 2 + 3 + 2 = 7.0 с; S-кривая 2.5 + 2.5 + 2.5 = 7.5 с | — |
| ctl-signals.md:94,96 | `peaks (Hz): [179, 218, 500]`; f₁ = eRPM/(poles/2)/60; наклонные — моторы, горизонтальные — рама | recomputed OK | код шага 0 запущен: `peaks (Hz): [179, 218, 500]`; L37, L82, L88 | — |
| ctl-sysid.md:129 | `K = 1.00, T = 20 мс, τ = 9.0 мс`; фильтр 80 Гц ≈ 14°, 40 Гц ≈ 27° на 20 Гц | recomputed OK | код шага 1 запущен: вывод совпал; arctan(20/80) = 14.04°, arctan(20/40) = 26.57° (формула L62) | — |
| ctl-sysid.md:129 | «после снижения `INS_GYRO_FILTER` вдвое фаза на 20 Гц ушла вниз на величину, близкую к расчёту шага 2» | not self-checkable (unstated number) | шаг 2 считает 80 → 40 Гц (разница ≈ 12.5°), а в Copter `INS_GYRO_FILTER` по умолчанию 20 Гц (`AP_InertialSensor.cpp:64`): 20 → 10 Гц даёт arctan(1) − arctan(2) = 45° → 63.4°, то есть ≈ 18°. С каким числом сравнивать, не сказано | «…а после снижения `INS_GYRO_FILTER` вдвое фаза на 20 Гц ушла вниз на arctan(20/f_новый) − arctan(20/f_старый): для умолчания Copter 20 → 10 Гц это ≈ 18° (45° → 63°).» |
| ctl-sysid.md:131 | Kp ↑ → срез выше, запас меньше; `SIDD.Targ` vs `RATE.ROut`; чирп 1–30 Гц; `SID_AXIS = 0`, вход из STABILIZE | confirmed | L40, L124, L147 | — |
| ctl-theory.md:102,104 | ζ ≈ 0.59 при 10 %; ωₙ ≈ 167 рад/с при 40 мс и ζ = 0.6; при 5 мс P_max и частота ниже; `ATC_ANG_RLL_P = 15`; ζ < 0.4 звенит | recomputed OK | L81, L93–95, L100; −ln 0.1/√(π² + ln² 0.1) = 0.591; 4/(0.6·0.04) = 166.7 | — |
| data-python.md:170,172 | 8 кГц / 4 = 2 кГц; пик 210 Гц; overshoot 5–15 %, bounce-back < 10 % / > 25 %; медиана по 10–20 шагам | confirmed | L151–167 | — |
| tools-gazebo.md:117,119 | взлёт 10 м, RTF; 3 м / 2 м от столба; геозона 50 м; `GZ_SIM_SYSTEM_PLUGIN_PATH`, `gazebo-`, `JSON`; `gz topic -l` | confirmed | L34, L61, L69, L81–87, L115, L123, L133 | — |
| tools-overview.md:126,128,130 | одна изменённая строка; «rpm_filter_min_hz 100→50: моторы 10" ниже 100 Гц на висении»; `dump` вместо `diff all` | confirmed | L111–123 | — |


## Counts per directory

| directory | rows | confirmed | recomputed OK | WRONG | not reproducible | not self-checkable | wording |
|---|---|---|---|---|---|---|---|
| ardupilot | 17 | 12 | 2 | 1 | 0 | 2 | 0 |
| betaflight | 13 | 11 | 2 | 0 | 0 | 0 | 0 |
| companion (+ quiz) | 29 | 17 | 10 | 1 | 0 | 1 | 0 |
| design | 3 | 2 | 1 | 0 | 0 | 0 | 0 |
| electronics | 13 | 4 | 8 | 0 | 0 | 1 | 0 |
| estimation | 13 | 8 | 5 | 0 | 0 | 0 | 0 |
| foundation | 20 | 12 | 6 | 0 | 1 | 0 | 1 |
| inav | 4 | 2 | 2 | 0 | 0 | 0 | 0 |
| link | 3 | 2 | 1 | 0 | 0 | 0 | 0 |
| math | 14 | 3 | 7 | 1 | 1 | 2 | 0 |
| px4 | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| ros2 | 6 | 4 | 2 | 0 | 0 | 0 | 0 |
| tools | 9 | 4 | 4 | 0 | 0 | 1 | 0 |
| **total** | **150** | **87** | **50** | **3** | **2** | **7** | **1** |

Rows group several statements of one changed line; 123 files / 326 added lines are covered.

## Summary of items that need an edit

WRONG (3):
1. `companion/fw-reading.md:99` — порядок фильтров гироскопа Betaflight (динамический notch стоит последним, LPF2 — первым; источник — теория L35).
2. `math/math-ode-dyn.md:108` — «≈ 44 рад/с» → 43 (полюса −25.1 ± 43.4j).
3. `ardupilot/ap-companion.md:184` — «реже 2 Гц → таймаут»: таймаут срабатывает при паузе > `GUID_TIMEOUT` (3 с).

Not reproducible (2): `math/math-ode-dyn.md:108` («все три способа дают эти числа» — нужен допуск 1 % / 1–2°); `foundation/f-frame-mech.md:83` (пик «20–40 Гц»).

Not self-checkable (7): `ardupilot/ap-plane-tuning.md:91` (ближе, чем до него); `ardupilot/ap-safety-fs.md:81` (порог RPN не задан); `companion/per-landing.md:110` (сверка с рулеткой без допуска); `electronics/el-wiring.md:101` («не нагрелось»); `math/math-ode-dyn.md:108` (синус 50 Гц при f_s = 100 Гц — нулевые отсчёты); `math/math-ode-dyn.md:98/108` (kp незатухающих колебаний в модели не существует); `tools/ctl-sysid.md:129` (20 → 10 Гц даёт ≈ 18°, а не числа шага 2).

Outside-audience wording (1): `foundation/eng-method-101.md:74` («В рубриках итоговых проектов курса…»). Other hits of «наблюдатель», «помощник», «отчёт ODM», «первичный отчёт» are safety observers or document names, not graders.

Out of scope but found on the way: `companion/fw-reading.md:35` (theory, same wrong filter order); `est-kalman` lab gives LOWER RMS for `q_acc` ×0.1 (0.039 vs 0.044 м) — the эталон does not claim otherwise; `ros2-nav.md:54` theory has no reaction-delay term; `ops-field.md:138` (step 4 of the search drill needs a second person; unchanged line).
