# i18n-translator-notes

Scope: 46 possible errors in the Russian source that the uk/en/uk-galych translators flagged (`source-issues.md`, 49 notes). Three notes had already been fixed and were skipped: bf-custom BUILD KEY, ap-intro ARMING_CHECK, aero-wing landing into the wind.

What a verdict means:
- **fixed**: the Russian source was corrected minimally, and the same correction went into the uk, en and uk-galych files. Translated `.md` files got a new `source_hash`.
- **not an error**: the source was checked and left as it is.
- **left: uncertain**: a real problem, but the right replacement value could not be established safely.

Quiz answers and option counts are identical in all four languages. `validate_content.py`, `check_i18n.py` and `publish.py` pass with 0 errors.

Basis:
- ArduPilot master/4.7:
  - AP_NavEKF3 `getVariances` and `LogStructure.h`.
  - `RC_Channels_VarInfo.h` (RC_OPTIONS).
  - `AP_Baro_Wind.cpp`.
  - `AP_AccelCal.cpp`.
  - AP_InertialSensor params.
  - AP_DDS_Client.cpp.
  - AP_Arming.
- PX4 main, v1.14–v1.17:
  - `commander_params.yaml` (COM_ACT_FAIL_ACT, COM_RC_IN_MODE, COM_OF_LOSS_T).
  - `failure_detector_params.c`.
  - `mc_att_control_params`.
  - `imu_gyro_parameters`.
  - `rc.mc_defaults`.
  - MulticopterRateControl.cpp.
  - docs motor_failure_detection / motor_failure_recovery.
- Betaflight master:
  - `cli/settings.c`.
  - `flight/pid.c`.
  - `io/serial.c`.
- INAV master and tags 7.0.0/7.1.0/8.0.0:
  - `docs/Settings.md`, `Serial.md`, `Navigation.md`, `GPS_fix_estimation.md`.
  - `settings.yaml`.
- INAV 2.2.0 release notes.
- Bluejay README.
- rosbag2 humble/jazzy/kilted/rolling `record.py`.
- PIDscope README.
- STSB report SUI-9903.
- AAIB Bulletin 1/2023 (Alta X).
- Ligpower/T-Motor MN4006 KV380 test table.

## electronics

- verdict: fixed
  file: content/electronics/el-power-design.md + content/quiz/el-power-design.json (q6)
  quote: "Недогруженный разъём греется…" / "Что происходит с недогруженным по току разъёмом?"
  fix: "Разъём, перегруженный по току (номинал ниже реального тока), греется…" / "…с разъёмом, перегруженным по току?"
  why: A connector carrying less current than its rating does not overheat. The heating, oxidation and more heating chain applies to an overloaded or under-rated connector. The answer index did not change.
  source: physics (I²R); text was internally inconsistent
- verdict: fixed
  file: content/tasks/el-power-design.json (lin-bec solution)
  quote: "от 6S на 5 В при 1 А — это 17 Вт тепла"
  fix: "от 6S (22.2 В номинал) на 5 В при 1 А — это ~17 Вт тепла (от заряженного, 25.2 В — ~20 Вт)"
  why: Recomputed: (22.2−5)·1 = 17.2 W and (25.2−5)·1 = 20.2 W. The text did not say which voltage it used.
  source: arithmetic
- verdict: fixed
  file: content/electronics/el-measure.md
  quote: "115200 для MSP/CRSF — 420000 для CRSF!"
  fix: "115200 для MSP, 420000 для CRSF!"
  why: The note gave two speeds for CRSF in one sentence. CRSF between the receiver and the FC runs at 420000, as the module's own practice step says.
  source: module practice step; https://www.expresslrs.org/
- verdict: fixed
  file: content/electronics/el-peripherals.md
  quote: "**Half-duplex**: ESC-телеметрия … VTX SmartAudio/Tramp — один провод на TX-пин."
  fix: "**Один провод**: ESC-телеметрия … — однонаправленная (ESC → FC) … запрос идёт по сигналу DShot; VTX SmartAudio/Tramp — настоящий half-duplex…"
  why: ESC telemetry is one-way and time-shared: the ESCs answer in turn on one RX pin, and the request goes over DShot. It is not half-duplex. SmartAudio and Tramp are true half-duplex.
  source: https://github.com/betaflight/betaflight (serial/esc_sensor); Betaflight Serial docs
- verdict: fixed
  file: content/electronics/el-redundancy.md
  quote: "ArduPilot: `RC_OPTIONS`, резервный вход … failover в PX4 (`RC_MAP`)" ; "действие (предупреждение/посадка/землю)"
  fix: "`RC_OPTIONS` бит 10 (несколько приёмников)…; PX4 — резерв RC ↔ MAVLink-управление (`COM_RC_IN_MODE`; `RC_MAP_*` — только назначение каналов)" ; "failsafe `COM_ACT_FAIL_ACT` (предупреждение/Hold/Land/Return/Terminate), а `CA_FAILURE_MODE = 1` убирает мотор из микшера"
  why: RC_OPTIONS bit 10 is "Enable multiple receiver support". PX4 RC_MAP_* only maps channels. PX4 falls back between RC and MAVLink manual control through COM_RC_IN_MODE. COM_ACT_FAIL_ACT has five values: 0 Warning, 1 Hold, 2 Land, 3 Return, 4 Terminate.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/RC_Channel/RC_Channels_VarInfo.h ; https://github.com/PX4/PX4-Autopilot/blob/main/src/modules/commander/commander_params.yaml ; https://docs.px4.io/main/en/config/motor_failure_detection
- verdict: fixed
  file: content/tasks/el-battery-packs.json (sag)
  quote: "Сборка **{s}S**…" ; "ΔU = I·S·R_ячейки"
  fix: "Сборка **{s}S1P**…" ; "(для 1P; при nP — делить на n)"
  why: The formula assumes one cell per series group. The answer formula did not change.
  source: arithmetic
- verdict: fixed
  file: content/electronics/el-wiring.md (references)
  quote: "NASA Workmanship Standards — Soldering (pictorial reference) | …/nasa-std-87394"
  fix: "NASA-STD-8739.4 — Crimping, Interconnecting Cables, Harnesses, and Wiring | …/nasa-std-87394"
  why: The URL points to NASA-STD-8739.4, the crimping and harness standard. The soldering standard is NASA-STD-8739.3, and it has since been cancelled. 8739.4 fits a wiring module, so I corrected the label and kept the link.
  source: https://sma.nasa.gov/news/articles/newsitem/2016/08/25/updates-to-crimping-interconnecting-cables-harnesses-and-wiring-standard-published
- verdict: fixed
  file: content/quiz/rf-link-budget.json (q4)
  quote: options "3 дБ — двукратный запас", "3 дБ"
  fix: option 0 → "0 дБ — приём ровно на пороге чувствительности"
  why: Two options were near-duplicates. The answer index did not change, and the correct option is not the longest one.
  source: —
- verdict: fixed
  file: content/tasks/rf-link-budget.json (margin solution)
  quote: "Рабочий запас — не меньше 15–20 дБ на замирания."
  fix: "Минимум — 10–15 дБ на замирания, комфортно — 20 дБ."
  why: The solution now matches the module's "Запас M" paragraph.
  source: module text

## estimation

- verdict: not an error
  file: content/ardupilot/ap-ekf.md, content/quiz/ap-ekf.json
  quote: "`SV`, `SP`, `SH`, `SM` — корень из test ratio"
  why: The code computes `getVariances()` as `velVar = sqrtF(velTestRatio)`, and the test ratio is innov²/maxInnov². So the logged value is innovation divided by the allowed innovation. The quiz's "Test ratio > 1" gives the same threshold. The log description says "square of …", but it contradicts the code; the code is the authority.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_NavEKF3/AP_NavEKF3_Outputs.cpp
- verdict: fixed
  file: content/quiz/est-kalman.json (q3 explain)
  quote: "SP — квадрат отношения инновации к допустимой"
  fix: "SP — отношение инновации к допустимой (корень из test ratio)"
  why: Same code path as the ap-ekf note above. The est-kalman module text was already correct.
  source: same as above
- verdict: fixed
  file: content/estimation/est-kalman.md (diagnostics)
  quote: "большой R не хватает"
  fix: "заданного R (`EK3_ALT_M_NSE`) не хватает, чтобы покрыть эту ошибку"
  why: The sentence was ungrammatical. The intended meaning is that the configured measurement noise is too small for prop-wash error.
  source: —
- verdict: fixed
  file: content/estimation/est-alt-sources.md
  quote: "у крыльев — компенсация по airspeed (у коптеров — `BARO1_WCF_*` …), у коптеров — эффект пропвоша"
  fix: "ошибку от обдува компенсирует `BARO1_WCF_*` (…; у коптеров — только с EKF3 и настроенными `EK3_DRAG_BCOEF_*`; …), у коптеров ещё и эффект пропвоша"
  why: The sentence was awkward and said "у коптеров" twice. BARO_WCF is generic. Its parameter description says multirotors can use it only with EKF3 and tuned EK3_DRAG_BCOEF_X/Y.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_Baro/AP_Baro_Wind.cpp
- verdict: fixed
  file: content/estimation/est-attitude.md (Mahony step 3)
  quote: "e = a × v"
  fix: "e = (−a/|a|) × v"
  why: Step 2 defines the measured down vector as −a/|a|, and the code uses `np.cross(a_u, v)` with `a_u = -a/an`. Step 3 used the raw `a`.
  source: module code
- verdict: fixed
  file: content/estimation/est-sensors.md
  quote: "(ArduPilot — ещё и неортогональность при `INS_ACC*_ID`-калибровке через Mission Planner)"
  fix: "(так и в ArduPilot: `INS_ACCOFFS` + `INS_ACCSCAL`, эллипсоид без перекрёстных членов — неортогональность не калибруется; `INS_ACC*_ID` — лишь идентификатор датчика)"
  why: AP_AccelCal starts `ACCEL_CAL_AXIS_ALIGNED_ELLIPSOID` with 6 parameters, which has no off-diagonal terms. `INS_ACC_ID` is a read-only sensor ID.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_AccelCal/AP_AccelCal.cpp
- verdict: fixed
  file: content/estimation/est-sensors.md (diagnostics)
  quote: "EKF-варианты растут"
  fix: "EKF-вариации (дисперсии) растут"
  why: typo
  source: —
- verdict: fixed
  file: content/estimation/nav-resilience.md
  quote: "Над водой: продолжать по инерциалке к берегу — не рассчитывать, не хватит."
  fix: "Над водой: на инерциалку до берега не рассчитывать — не хватит; AltHold и ручной возврат к берегу визуально или по видео."
  why: The sentence contradicted itself: it said to do something and then not to count on it. Now it gives one clear action.
  source: —

## foundation

- verdict: fixed
  file: content/foundation/diag-troubleshooting.md
  quote: "(XT30 на 2-пиновом JST — классика)"
  fix: "(2-пиновый JST-PH у разных производителей распаян с обратной полярностью — классика)"
  why: XT30 is keyed and does not mate with JST. The real classic is a JST-PH lead with reversed polarity from different vendors. The `ARMING_SKIPCHK` (before 4.7: `ARMING_CHECK`) statement is correct, because the 4.7 source has `SKIPCHK` replacing `CHECK`. Not changed.
  source: https://github.com/ArduPilot/ardupilot/blob/ArduPilot-4.7/libraries/AP_Arming/AP_Arming.cpp
- verdict: fixed
  file: content/foundation/f-aero-props.md
  quote: "(10\": 300–500 KV на 6S)"
  fix: "(10\": 600–900 KV на 6S)"
  why: 300–500 KV on 6S is the 13–15" class; the same module's X8 uses 4008 380KV with 15" props. f-components-choice gives 10" 3110/3115 at 600–900 KV on 6S.
  source: f-components-choice; manufacturer 10" motor ranges
- verdict: left: uncertain
  file: content/foundation/f-aero-props.md (Step 3, X8) and the derived numbers in ap-heavy.md, el-redundancy.md, f-power.md, tasks/ap-heavy.json
  quote: "~880 г при ~7 А. Ток висения ≈ 56 А … ≈ 17 мин"
  why: The translator is right that 880 g / (7 A · 22.2 V) = 5.7 g/W contradicts the module's 12–20 g/W. A comparable motor's table, MN4006 KV380 with a 15×5 prop at 24 V, gives 805 g at 3.1 A and 959 g at 4.1 A. So ~880 g needs ~3.6 A, which is ~10 g/W, ~29 A per pack and ~33 min. The figures 7 A, 56 A and 17 min feed four modules and a task bank, and ap-heavy also uses them for MOT_THST_HOVER 0.3–0.35. I did not have a real 4008 380KV/15×5.5 table, so I left the chain alone. Recommendation: rebuild the X8 example from one real 4008 table and update all four modules and the task bank together.
  source: https://www.ligpower.com/product/mn4006-kv380-motor-antigravity-type.html
- verdict: fixed
  file: content/foundation/f-components-choice.md (worked example)
  quote: "газ висения ≈ 1 / 3.43 ≈ 29 %."
  fix: added: "— в линейном приближении «тяга ∝ газ»; тяга растёт быстрее газа (T ∝ n²), поэтому реальный газ висения выше: при кривой `MOT_THST_EXPO = 0.65` — около 45 %."
  why: The linear rule contradicts T ∝ n² in f-aero-props. Recomputed: 0.35u + 0.65u² = 1/3.43 gives u = 0.45. The rule in the widget and in `data/formulas.json` was kept as the first-order estimate and is now labelled as such in the module.
  source: arithmetic; ArduPilot MOT_THST_EXPO
- verdict: fixed
  file: content/foundation/f-fc-sensors.md + content/quiz/f-fc-sensors.json (softserial explain)
  quote: "Softserial … до 115200 бод"
  fix: "до 19200 бод"
  why: The INAV Serial docs say "Softserial is limited to 19200 baud". The course's own bf-ports module says "до 19200 (прошивка ограничивает), MSP и Serial RX на нём запрещены", which matches `serialPortFunctionsConflict` in Betaflight.
  source: https://github.com/iNavFlight/inav/blob/master/docs/Serial.md ; https://github.com/betaflight/betaflight/blob/master/src/main/io/serial.c
- verdict: fixed
  file: content/foundation/f-esc-firmware.md
  quote: "### Шаг 4. Частота ШИМ на столе"
  fix: "### Шаг 4. Частота ШИМ: сравнение в полёте"
  why: The step's text says not to measure on the bench but in flight or tethered.
  source: —
- verdict: not an error
  file: content/foundation/f-esc-firmware.md (table)
  quote: "Bluejay … (BB1/BB10 — только до версии 0.18.1)"
  why: The Bluejay README says the EFM8 BB10 is deprecated and "The last official release is 0.18.1". BB1 is the same chip family name.
  source: https://github.com/bird-sanctuary/bluejay
- verdict: fixed
  file: content/foundation/f-frame-mech.md + content/tasks/f-frame-mech.json (mount-f0)
  quote: "7\" ~150–200" (vs example 125 Hz) ; task: "f₀ должна быть в 2–3 раза ниже … иначе он её усиливает"
  fix: "7\" ~120–200" ; task: "в 3–5 раз ниже … (как в модуле); при отношении частот меньше √2 подвес её усиливает"
  why: The range now covers the module's own 125 Hz example. The task now matches the module's 3–5× rule. The physics also needed correcting: amplification happens below a ratio of √2, not below 2–3.
  source: vibration isolation transmissibility
- verdict: fixed
  file: content/quiz/f-mechanics.json (q5 explain)
  quote: "сопротивление при 3 м/с для 7\" — единицы граммов"
  fix: "— ~20 гс против ~420 гс на разгон 3 м/с²"
  why: Recomputed: ½·1.225·3²·1.1·0.03 = 0.18 N ≈ 19 gf, the same as the module's "~20 гс". Also 1.4 kg · 3 m/s² = 4.2 N ≈ 428 gf. `thr_corr_value` still exists in Betaflight master and 4.5.
  source: arithmetic; https://github.com/betaflight/betaflight/blob/master/src/main/cli/settings.c
- verdict: fixed
  file: content/quiz/ops-case-studies.json (q1 explain), content/foundation/ops-case-studies.md (Alta X)
  quote: "Вибрации на IMU3 → …" ; "энергия удара ≈ 13 700 Дж"
  fix: "Вибрации выросли на всех трёх IMU, данные IMU3 резко разошлись с двумя другими → …" ; added "(оценка AAIB; ½·28·30² ≈ 12 600 Дж, 13 700 Дж соответствует ~31 м/с — свободному падению с 50 м)"
  why: The STSB report says "all three IMUs recorded clearly increasing vibrations" and that the deviations were in IMU3. The AAIB figures are 28 kg, about 30 m/s and about 13,700 J. ½mv² gives 12.6 kJ; 13.7 kJ matches free fall from 50 m (31.3 m/s). The AAIB figure is kept, with the arithmetic shown.
  source: https://www.sust.admin.ch/inhalte/AV-berichte/SUI-9903_SB_e.pdf ; https://assets.publishing.service.gov.uk/media/63bd39a28fa8f55e38046bcc/Freefly__Systems_Inc_Alta_X_01-23.pdf
- verdict: not an error
  file: content/foundation/ops-case-studies.md (Matternet)
  quote: "Энергия удара ≈ 118 Дж без груза"
  why: STSB 2.2.2: "around 118 J" for the drone without payload.
  source: https://www.sust.admin.ch/inhalte/AV-berichte/SUI-9903_SB_e.pdf
  note (outside the list, not changed): the same module says `EK2_IMU_MASK = 3` (две исправные IMU) is the real fix. STSB 1.2.4 says the manufacturer recommended 7 from 2 May 2019, so that all three IMUs feed the EKF. Worth checking in the next pass.
- verdict: fixed
  file: content/foundation/f-electricity-101.md + content/quiz/f-electricity-101.json (q7 explain)
  quote: "Одна заметно выше — плохая пайка; «обрыв» — повреждённая обмотка."
  fix: "Плохая пайка вывода поднимает две пары с этим выводом; одна пара, выпадающая из двух других, — повреждённая обмотка (межвитковое замыкание); «обрыв» — оборванная обмотка или вывод." Quiz explain: added "В звезде R_AB = R_A + R_B: 0.08/0.08/0.15 значит, что обмотка B почти закорочена."
  why: In a star winding, a bad joint on one lead raises both pairs that include it. Solving 0.08/0.08/0.15 gives R_A = R_C = 0.075 Ω and R_B ≈ 0.005 Ω, which is a shorted winding. So the quiz answer (inter-turn short) was right and the module was wrong. The answer index did not change.
  source: arithmetic

## inav

- verdict: fixed
  file: content/quiz/inav-gps.json (q6)
  quote: "nav_user_control_mode = GPS_CRUISE" ; "В GPS_ATTI стик задаёт наклон."
  fix: "= CRUISE" ; "В CRUISE стик задаёт скорость; в ATTI — наклон."
  why: The setting's values are ATTI and CRUISE.
  source: https://github.com/iNavFlight/inav/blob/master/docs/Settings.md#nav_user_control_mode
- verdict: not an error
  file: content/inav/inav-gps.md
  quote: "Для крыла (INAV 8.0+) … `inav_allow_gps_fix_estimation`"
  why: The setting is absent from `settings.yaml` at tags 7.0.0 and 7.1.0 and present at 8.0.0.
  source: https://github.com/iNavFlight/inav/blob/8.0.0/src/main/fc/settings.yaml
- verdict: not an error
  file: content/inav/inav-intro.md, content/quiz/inav-intro.json
  quote: "Арм стиками удалён ещё в INAV 2.2."
  why: The 2.2.0 release notes say "Arming with sticks is being removed since it is not safe to use."
  source: https://newreleases.io/project/github/iNavFlight/inav/release/2.2.0
- verdict: fixed
  file: content/inav/inav-ipf.md (Russian only; the translations were already correct)
  quote: "иначе просадка на панче её сработает"
  fix: "иначе защита сработает от просадки на панче"
  why: The sentence was ungrammatical.
  source: —
- verdict: fixed
  file: content/quiz/inav-missions.json (q4 explain)
  quote: "Для WAYPOINT p1 — скорость в см/с."
  fix: "Для RTH p1 > 0 разрешает посадку дома; скорость в см/с p1 задаёт у обычной WAYPOINT."
  why: The question is about RTH, but the explanation described WAYPOINT. The answer index did not change.
  source: https://github.com/iNavFlight/inav/blob/master/docs/Navigation.md

## companion, link, mavlink, ros2

- verdict: fixed
  file: content/companion/per-mapping.md (practice step 2)
  quote: "имитация продольного перекрытия ниже на ~половину от исходного"
  fix: "имитация вдвое большего шага съёмки: продольное перекрытие o → 2o − 1, например 80 % → 60 %"
  why: Spacing = F·(1−o), so doubling it gives 1−o' = 2(1−o).
  source: arithmetic
- verdict: not an error (already handled in translations)
  file: content/tasks/mav-protocol.json (frame-len)
  why: The Russian string values of `s` are parameters by design (DOCS I18N.md, step 4). All three translations already carry `labels` that map them to their own language.
  source: docs/I18N.md
- verdict: fixed
  file: content/link/link-vtx.md (references)
  quote: "VTX Tables — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/VTX"
  fix: "…/docs/wiki/guides/current/VTX-Tables"
  why: The VTX Tables reference used the same URL as the VTX guide.
  source: https://betaflight.com/docs/wiki/guides/current/VTX-Tables
- verdict: fixed
  file: content/quiz/ros2-ardupilot.json (q2, q6)
  quote: q2 option "ENU, map" ; q6 options "В px4_msgs", "В пакете px4_msgs"
  fix: q2: "ENU относительно home", explain: "…; в header.frame_id прошивка пишет base_link." ; q6 option 2 → "В mavros_msgs"
  why: AP_DDS writes `BASE_LINK_FRAME_ID` into the PoseStamped header, as the module table says, so "map" was misleading. q6 had duplicate options. The answer indices did not change.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_DDS/AP_DDS_Client.cpp
- verdict: not an error
  file: content/ros2/ros2-app-arch.md
  quote: "автоудаление старых файлов `--max-bag-files` есть только в новых версиях rosbag2, в Humble/Jazzy … чистить самому"
  why: `--max-bag-files` is in rosbag2 rolling `record.py` and absent in humble, jazzy and kilted.
  source: https://github.com/ros2/rosbag2/blob/rolling/ros2bag/ros2bag/verb/record.py

## px4

- verdict: fixed
  file: content/px4/px4-architecture.md (practice step 3 result)
  quote: "модули — отдельные процессы, связанные только топиками"
  fix: "модули — независимые задачи (потоки или элементы work queue — `mc_rate_control` работает в очереди `rate_ctrl`, а не отдельным процессом), связанные только топиками"
  why: This contradicted the module's own theory section, which describes threads, and the code: mc_rate_control is `WorkItem(MODULE_NAME, wq_configurations::rate_ctrl)`.
  source: https://github.com/PX4/PX4-Autopilot/blob/main/src/modules/mc_rate_control/MulticopterRateControl.cpp
- verdict: fixed
  file: content/px4/px4-control.md
  quote: "`MC_ROLL_P` = 4.0" ; "`IMU_DGYRO_CUTOFF` 20 → 40"
  fix: added "(умолчание с PX4 1.17, до 1.16 — 6.5)" and "(умолчание 20 с 1.17, до 1.16 — 30)"
  why: Both translators' values are right for different versions. MC_ROLL_P is 6.5 in v1.14 and v1.16 and 4.0 in v1.17 and main. IMU_DGYRO_CUTOFF is 30 in v1.14–v1.16 and 20 in v1.17 and main. The module claims PX4 1.14+, so both versions are now given.
  source: https://github.com/PX4/PX4-Autopilot/blob/v1.16.0/src/modules/mc_att_control/mc_att_control_params.c ; https://github.com/PX4/PX4-Autopilot/blob/v1.17.0/src/modules/sensors/vehicle_angular_velocity/imu_gyro_parameters.c
- verdict: fixed
  file: content/px4/px4-ros2.md (practice)
  quote: "остановил узел — через ~2 с PX4 выходит из Offboard"
  fix: "через ~1 с (`COM_OF_LOSS_T`, 1 с по умолчанию)"
  why: The module itself states COM_OF_LOSS_T = 1 s, which is the default.
  source: https://github.com/PX4/PX4-Autopilot/blob/main/src/modules/commander/commander_params.yaml

## math, tools

- verdict: fixed
  file: content/math/math-linalg-rot.md
  quote: "12 функций" ; "ψ ∈ [0°, 360°)" ; "десятки тысяч раз в секунду"
  fix: "14 функций" (twice) ; "ψ ∈ (−180°, 180°] (на OSD курс обычно показывают как 0–360°)" ; "сотни–тысячи раз в секунду (по частоте цикла)"
  why: The list names 14 functions. The `atan2` extraction and the test, which compares against `uniform(−π, π)`, both use (−π, π]. AHRS update rates are 400 Hz to a few kHz.
  source: module text; ArduPilot 400 Hz, PX4 IMU_GYRO_RATEMAX, Betaflight
- verdict: fixed
  file: content/math/math-ode-dyn.md + content/quiz/math-ode-dyn.json (q6)
  quote: "с P-регулятором угла … − K_d·θ̇" ; "PX4 rate loop — до 1 кГц" ; options "0.5" and "0.5 — половина шага"
  fix: "с PD-регулятором угла" ; "PX4 rate loop — 800 Гц по умолчанию, до 2 кГц через `IMU_GYRO_RATEMAX`" ; option 3 → "0.0125"
  why: The law has a K_d term, so it is PD. In `rc.mc_defaults` the default rises from 400 to 800, and boards set up to 2000. The quiz had duplicate options. The answer index did not change: k = 0.125/(1.59+0.125) ≈ 0.073, recomputed.
  source: https://github.com/PX4/PX4-Autopilot/blob/main/ROMFS/px4fmu_common/init.d/rc.mc_defaults
- verdict: fixed
  file: content/math/math-prob-est.md (table)
  quote: "σ шума гироскопа (R-часть предсказания)"
  fix: "σ шума гироскопа (входит в Q — шум процесса при предсказании)"
  why: In EKF3 the gyro is the control input to the prediction, so its noise enters the process noise Q.
  source: ArduPilot EKF3 (EK3_GYRO_P_NSE "Rate gyro noise", used in covariance prediction)
  note (outside the list, not changed): practice step says EK3_GYRO_P_NSE is in rad/s/√Hz. The parameter is documented in rad/s.
- verdict: not an error
  file: content/tools/data-python.md
  quote: "`IMU` (обычно 1 кГц при `LOG_BITMASK` с RAW IMU)"
  why: Without the Raw IMU bit (LOG_BITMASK bit 19), IMU is logged at the loop rate of 400 Hz. With it, IMU is logged at the backend sample rate, which is typically 1 kHz.
  source: https://github.com/ArduPilot/ardupilot/blob/master/ArduCopter/Parameters.cpp (LOG_BITMASK)
- verdict: not an error
  file: content/tools/tools-overview.md
  quote: "сам PIDtoolbox с 2024 года платный"
  why: The PIDscope README says that in May 2024 releases moved behind a Patreon paywall.
  source: https://github.com/dzikus/PIDscope
- verdict: fixed
  file: content/tools/ctl-signals.md (practice)
  quote: "nperseg=512 для 8 кГц (Δf 15 Гц, Δt 32 мс)"
  fix: "(Δf ≈ 15.6 Гц, окно 64 мс, шаг по времени 32 мс при noverlap=256)"
  why: The window is 512/8000 = 64 ms, as stated in the theory section. The 32 ms is the column step with data-python's `noverlap=256`. Both are now named.
  source: arithmetic; content/tools/data-python.md
- verdict: fixed
  file: content/tools/ctl-theory.md
  quote: "`angle_p_gain` (4.5)"
  fix: "`angle_p_gain` (по умолчанию 50)"
  why: The default is `[PID_LEVEL] = { 50, … }`, and angle_p_gain maps to `pid[PID_LEVEL].P`.
  source: https://github.com/betaflight/betaflight/blob/master/src/main/flight/pid.c

## Summary

- fixed: 36 notes.
  - Russian source in 29 modules, 11 quiz banks and 4 task banks.
  - Every change mirrored in uk, en and uk-galych.
  - 87 translated modules rehashed.
- not an error: 9 notes (ap-ekf, mav-protocol, inav fix estimation, inav stick arming, Bluejay BB10, Matternet 118 J, data-python IMU rate, PIDtoolbox, rosbag2 max-bag-files).
- left: uncertain: 1 note (X8 7 A / 56 A / 17 min chain).
- Outside the list, noticed and not changed: ops-case-studies `EK2_IMU_MASK = 3` versus the STSB "7"; math-prob-est EK3_GYRO_P_NSE units.
- Blocked: the docs.px4.io and ardupilot.org parameter pages could not be fetched (WebFetch permission). GitHub sources were used instead.
