# foundation-electronics

## el-battery-packs
verified: 14, no findings

## el-emi
verified: 8
- severity: error
  file: content/electronics/el-emi.md
  quote: "`GPS.NSats`, `GPA.HDop`"
  fix: "`GPS.NSats`, `GPS.HDop`"
  why: The ArduPilot GPA message has VDop/HAcc/VAcc/SAcc and no HDop field. HDop is in the GPS message.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_GPS/LogStructure.h

## el-measure
verified: 10, no findings

## el-peripherals
verified: 14
- severity: imprecise
  file: content/electronics/el-peripherals.md
  quote: "уникальные node ID (раздаёт автопилот при `CAN_D1_UC_NODE` и динамическом распределении)"
  fix: "уникальные node ID (автопилот раздаёт их как DNA-сервер при динамическом распределении; `CAN_D1_UC_NODE` — собственный node ID автопилота)"
  why: CAN_D1_UC_NODE is the autopilot's own node ID ("Own node ID"). It does not allocate IDs.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_DroneCAN/AP_DroneCAN.cpp

## el-power-design
verified: 12
- severity: error
  file: content/electronics/el-power-design.md
  quote: "Rвн АКБ 6S Li-Ion 4P ≈ 20–40 мОм на элемент → 150–250 мОм на пакет; при 60 А просадка 9–15 В."
  fix: "Rвн АКБ 6S Li-Ion 4P ≈ 20–40 мОм на элемент → 30–60 мОм на пакет (R × 6 / 4); при 60 А просадка 1.8–3.6 В."
  why: Pack resistance is R_cell×S/P, the same formula the battery-packs and electricity-101 modules use. 150–250 mΩ is wrong by about 5x.
  source: recomputed: 20e-3*6/4 = 0.030 Ω, 40e-3*6/4 = 0.060 Ω; 60*0.030 = 1.8 V, 60*0.060 = 3.6 V
- severity: imprecise
  file: content/electronics/el-power-design.md
  quote: "XT60 до ~60 А, XT90 выше"
  fix: "XT60 ~30 А длительно (кратковременно до ~60 А), XT90 ~45 А длительно"
  why: The continuous rating for XT60 is 30 A and for XT90 is 45 A. 60 A is a burst figure.
  source: https://docs.holybro.com/power-module-and-pdb/power-module/connector-and-wire-rating

## el-redundancy
verified: 12
- severity: error
  file: content/electronics/el-redundancy.md
  quote: "разъём луча XT60 (до ~60 А длительно) — впритык"
  fix: "разъём луча XT60 (~30 А длительно, ~60 А кратковременно) — для 50 А мал"
  why: The XT60 is rated 30 A continuous, so a 50 A arm current exceeds its continuous rating.
  source: https://docs.holybro.com/power-module-and-pdb/power-module/connector-and-wire-rating
- severity: imprecise
  file: content/electronics/el-redundancy.md
  quote: "Нет автоматического «режима отказа мотора» — живучесть зависит от запаса тяги и геометрии."
  fix: "Есть проверка потери тяги (сообщение «Potential Thrust Loss (n)»): миксер включает thrust boost и исключает потерянный мотор из управления рысканием; но живучесть всё равно определяется запасом тяги и геометрией."
  why: ArduCopter has thrust_loss_check(). It reports the lost motor and enables thrust boost handling in AP_MotorsMatrix.
  source: https://github.com/ArduPilot/ardupilot/blob/master/ArduCopter/crash_check.cpp

## el-wiring
verified: 4, no findings

## rf-antennas
verified: 9, no findings

## rf-link-budget
verified: 18, no findings

## est-alt-sources
verified: 22
- severity: error
  file: content/estimation/est-alt-sources.md
  quote: "(`BARO_GND_TEMP`, ARSPD)"
  fix: "(у коптеров — `BARO1_WCF_*`, ветровая компенсация давления; `BARO_GND_TEMP` — лишь температура у земли для расчёта высоты)"
  why: BARO_GND_TEMP is the ground temperature used in the altitude calculation, not airspeed or dynamic-pressure compensation. The wind compensation parameters are BARO1_WCF_*.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_Baro/AP_Baro.cpp
- severity: error
  file: content/estimation/est-alt-sources.md
  quote: "ArduPilot `BARO_FLTR`"
  fix: "ArduPilot `TCAL_ENABLED`/`TCAL_BARO_EXP`"
  why: There is no BARO_FLTR parameter. The only similar one is BARO_FLTR_RNG (outlier rejection). Baro temperature calibration uses the TCAL_* group.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_TempCalibration/AP_TempCalibration.cpp
- severity: imprecise
  file: content/estimation/est-alt-sources.md
  quote: "(preflight check «EKF needs position»)"
  fix: "(preflight check «PreArm: Need Position Estimate»)"
  why: The actual Copter pre-arm text is "Need Position Estimate".
  source: https://github.com/ArduPilot/ardupilot/blob/master/ArduCopter/AP_Arming_Copter.cpp

## est-attitude
verified: 12
- severity: error
  file: content/estimation/est-attitude.md
  quote: "2. Измеренный «вниз» — нормированный акселерометр a/|a|."
  fix: "2. Измеренный «вниз» — нормированный акселерометр со знаком минус: −a/|a| (акселерометр меряет удельную силу; в покое в FRD он показывает (0, 0, −g))."
  why: An accelerometer at rest measures the upward reaction (the module's own est-sensors says "+1 g вверх"), so a/|a| points up, not down. ArduPilot IMU.AccZ ≈ −9.81 when level.
  source: recomputed: R_nbᵀ·(0,0,−9.81) for a level FRD body = (0,0,−9.81)
- severity: error
  file: content/estimation/est-attitude.md
  quote: "a_u = a / an; v = down_body(q)"
  fix: "a_u = -a / an; v = down_body(q)   # accel measures specific force (-g at rest, FRD)"
  why: With ArduPilot/FRD accelerometer data, the published code locks onto the inverted attitude.
  source: recomputed: simulated the module's mahony() with a static 10° roll; as written it converges to roll −172.9°, with -a it converges to 10.2°

## est-gnss
verified: 18
- severity: error
  file: content/estimation/est-gnss.md
  quote: "`EK3_GPS_DELAY` ~ 100–200 мс"
  fix: "`GPS_DELAY_MS` (в 4.6+ `GPS1_DELAY_MS`) ~ 100–200 мс"
  why: EKF3 has no EK3_GPS_DELAY parameter. GPS lag is set per receiver in the AP_GPS DELAY_MS parameter.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_NavEKF3/AP_NavEKF3.cpp ; https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_GPS/AP_GPS_Params.cpp
- severity: outdated
  file: content/estimation/est-gnss.md
  quote: "(ArduPilot `GPS_RATE_MS = 200` → 5 Гц;"
  fix: "(ArduPilot `GPS_RATE_MS = 200`, в 4.6+ `GPS1_RATE_MS` → 5 Гц;"
  why: In 4.6 the per-receiver GPS parameters moved to GPS1_* (GPS_RATE_MS → GPS1_RATE_MS). The same applies to GPS_GNSS_MODE → GPS1_GNSS_MODE. The module already notes the GPS1_TYPE rename.
  source: https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/AP_GPS/AP_GPS.cpp
- severity: imprecise
  file: content/estimation/est-gnss.md
  quote: "`XKF4.SP` в логе (инновации позиции)"
  fix: "`XKF4.SP` в логе (нормированная инновация позиции, √test ratio)"
  why: XKF4.SP is the square root of the position innovation test ratio, not the raw innovation.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_NavEKF3/LogStructure.h

## est-kalman
verified: 14
- severity: imprecise
  file: content/estimation/est-kalman.md
  quote: "это квадрат отношения «инновация / максимально допустимая инновация»"
  fix: "это корень из test ratio, то есть само отношение «инновация / максимально допустимая инновация»"
  why: getVariances() logs sqrtF(velTestRatio/posTestRatio/hgtTestRatio). The log docs say "Square root of the ... variance". The <1 threshold still holds.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_NavEKF3/AP_NavEKF3_Outputs.cpp

## est-sensors
verified: 14
- severity: error
  file: content/estimation/est-sensors.md
  quote: "ArduPilot — при каждом арме"
  fix: "ArduPilot — при включении (`INS_GYR_CAL = 1`, Start-up only)"
  why: INS_GYR_CAL accepts only 0 (Never) or 1 (Start-up only). ArduPilot does not recalibrate gyros on every arm.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_InertialSensor/AP_InertialSensor.cpp
- severity: error
  file: content/estimation/est-sensors.md
  quote: "(состояния EKF `XKF2`: `GX/GY/GZ` — gyro bias, `AX/AY/AZ` — accel bias)"
  fix: "(состояния EKF: `XKF1.GX/GY/GZ` — gyro bias, `XKF2.AX/AY/AZ` — accel bias)"
  why: The gyro bias fields GX/GY/GZ are in XKF1. XKF2 carries the AX/AY/AZ accel bias.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_NavEKF3/LogStructure.h

## nav-resilience
verified: 20
- severity: error
  file: content/estimation/nav-resilience.md
  quote: "| Что происходит | GPS.NSats | GPA.HDop / HAcc |"
  fix: "| Что происходит | GPS.NSats | GPS.HDop / GPA.HAcc |"
  why: GPA has no HDop field. HDop is in GPS and HAcc is in GPA.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_GPS/LogStructure.h
- severity: imprecise
  file: content/estimation/nav-resilience.md
  quote: "по inerциалке"
  fix: "по инерциалке"
  why: The word mixes Latin letters ("iner") into Cyrillic, which breaks search and spell-check.
  source: recomputed: visual/codepoint check of the string

## diag-troubleshooting
verified: 12
- severity: imprecise
  file: content/foundation/diag-troubleshooting.md
  quote: "Прочитай причину: Betaflight CLI → `status` → `Arming disable flags: ...`. Самые частые:"
  fix: "Прочитай причину: Betaflight CLI → `status` → `Arming disable flags: ...`. CLI печатает короткие имена из `runtime_config.c` (FAILSAFE, CALIB, NO_ACC_CAL, CMS, BOOTGRACE, MOTOR_PROTO, DSHOT_TELEM, ARMSWITCH в 4.5 / ARM_SWITCH в 2025.12+); ниже часть флагов названа по документации. Самые частые:"
  why: The list uses enum-style names (RX_FAILSAFE, CALIBRATING, ACC_CALIBRATION, CMS_MENU, BOOT_GRACE_TIME, MOTOR_PROTOCOL) that never appear in `status` output.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/fc/runtime_config.c
- severity: outdated
  file: content/foundation/diag-troubleshooting.md
  quote: "**RPMFILTER**"
  fix: "**DSHOT_TELEM** (до 4.5 — RPMFILTER)"
  why: The flag was renamed RPMFILTER → DSHOT_TELEM between 4.4 and 4.5.
  source: https://github.com/betaflight/betaflight/blob/4.4-maintenance/src/main/fc/runtime_config.c ; https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/fc/runtime_config.c

## eng-method-101
verified: 2, no findings

## f-aero-props
verified: 12, no findings

## f-components-choice
verified: 4, no findings

## f-electricity-101
verified: 10, no findings

## f-fc-sensors
verified: 12
- severity: imprecise
  file: content/foundation/f-fc-sensors.md
  quote: "синхронно с выдачей гироскопа (`gyro_sync`)"
  fix: "синхронно с выдачей гироскопа (в 4.x всегда; делитель PID-петли — `pid_process_denom`)"
  why: Betaflight 4.5 has no `gyro_sync` setting. The PID rate divider is pid_process_denom.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/fc/parameter_names.h

## f-frame-mech
verified: 6, no findings

## f-mechanics
verified: 16
- severity: imprecise
  file: content/foundation/f-mechanics.md
  quote: "D мал (единицы граммов"
  fix: "D мал (~20 гс при тех же C_d = 1.1 и A = 0.03 м²"
  why: The module's own drag formula at 3 m/s gives about 18.5 gf, i.e. tens of grams. That matches its own "1410–1420 гс", not "units of grams".
  source: recomputed: 0.5*1.225*1.1*0.03*3^2 = 0.182 N = 18.5 gf
- severity: imprecise
  file: content/foundation/f-mechanics.md
  quote: "`thr_corr_value`/`throttle_boost`"
  fix: "`thr_corr_value` (Betaflight), `throttle_tilt_comp_str` (INAV), `ATC_ANGLE_BOOST` (ArduPilot)"
  why: Betaflight's throttle_boost boosts throttle on fast stick movement and is not tilt compensation. The INAV and ArduPilot equivalents are the parameters named in the fix.
  source: https://github.com/iNavFlight/inav/blob/master/src/main/fc/settings.yaml ; https://github.com/ArduPilot/ardupilot/blob/master/libraries/AC_AttitudeControl/AC_AttitudeControl.cpp

## f-motors-esc
verified: 12, no findings

## f-physics
verified: 12
- severity: error
  file: content/foundation/f-physics.md
  quote: "| 2 передний правый (CW) |"
  fix: "| 2 передний правый (CCW) |"
  why: As written, adjacent motors 1/2 both spin CW and diagonal motors 1/4 spin opposite ways. That contradicts the module's own text (diagonals share a direction) and its yaw column (1&4 = −1, 2&3 = +1). Betaflight default is M1 RR CW, M2 FR CCW, M3 RL CCW, M4 FL CW.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/flight/mixer_init.c (mixerQuadX yaw signs)
- severity: error
  file: content/foundation/f-physics.md
  quote: "| 4 передний левый (CCW) |"
  fix: "| 4 передний левый (CW) |"
  why: Same direction error as motor 2: motor 4 is diagonal to motor 1 (CW) and has the same yaw sign (−1), so it must be CW.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/flight/mixer_init.c

## f-power
verified: 12, no findings

## f-regulations
verified: 12
- severity: error
  file: content/foundation/f-regulations.md
  quote: "по близости к людям и классу аппарата C0–C6"
  fix: "по близости к людям и классу аппарата C0–C4 (классы C5/C6 — для стандартных сценариев STS в категории Specific)"
  why: Open-category subcategories use classes C0–C4. C5 and C6 (added by Reg. 2020/1058) are for STS-01/02 in the Specific category.
  source: https://skybrary.aero/articles/uas-rules-and-guidance-eu

## f-safety
verified: 34
- severity: error
  file: content/foundation/f-safety.md
  quote: "### Как прошивка защищает от арма (Betaflight 4.5)"
  fix: "### Как прошивка защищает от арма (Betaflight master; в 2025.12 нет `AUTOPILOT_SW`, в 4.5 нет `FLIP_SWITCH`/`ALT_HOLD_SW`/`POS_HOLD_SW`/`AUTOPILOT_SW`, а `ARM_SWITCH` называется `ARMSWITCH`)"
  why: The table matches master's armingDisableFlagNames. The 4.5 list ends with MOTOR_PROTO and ARMSWITCH, has no mode-switch flags, and AUTOPILOT_SW exists only in master.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/fc/runtime_config.c ; https://github.com/betaflight/betaflight/blob/2025.12-maintenance/src/main/fc/runtime_config.c

## ops-case-studies
verified: 42
- severity: imprecise
  file: content/foundation/ops-case-studies.md
  quote: "(STSB, отчёт SUI-9903)"
  fix: "(STSB, итоговый отчёт № 2390, аппарат SUI-9903)"
  why: SUI-9903 is the aircraft registration. The STSB document is Final Report No. 2390, approved 6 June 2023.
  source: https://www.sust.admin.ch/inhalte/AV-berichte/SUI-9903_SB_e.pdf
- severity: imprecise
  file: content/foundation/ops-case-studies.md
  quote: "вибрации на IMU3 резко выросли (ускорения местами > 30 м/с²), IMU1 и IMU2 — в норме"
  fix: "вибрации выросли на всех трёх IMU (ускорения местами > 30 м/с²), а IMU3 дал резкие отклонения, тогда как IMU1 и IMU2 показывали согласованные значения"
  why: The report says all three IMUs recorded rising vibrations "well over 30 m/s2". Only IMU3 showed the abrupt deviations.
  source: https://www.sust.admin.ch/inhalte/AV-berichte/SUI-9903_SB_e.pdf
- severity: imprecise
  file: content/foundation/ops-case-studies.md
  quote: "`VIBE` на одном IMU растёт, на других — нет"
  fix: "`VIBE` растёт на всех IMU, но данные одного IMU резко расходятся с двумя другими"
  why: All IMUs saw increasing vibration. The signature was one IMU diverging from the other two.
  source: https://www.sust.admin.ch/inhalte/AV-berichte/SUI-9903_SB_e.pdf
- severity: imprecise
  file: content/foundation/ops-case-studies.md
  quote: "Рекомендация комиссии: шестимоторные схемы для полётов над людьми (отказ одного мотора на квадрокоптере почти всегда означает падение или FTS)."
  fix: "Рекомендация комиссии № 591: добиваться резервированной концепции силовой установки (в анализе отмечено, что схемы с 6 и более моторами имеют значительно меньшую вероятность отказа)."
  why: STSB did not formally recommend hexacopters. SR 591 asks for a "redundant propulsion concept", and "6 or more propulsion units" appears only in the analysis.
  source: https://www.sust.admin.ch/inhalte/AV-berichte/SUI-9903_SB_e.pdf

## ops-field
verified: 4
- severity: error
  file: content/foundation/ops-field.md
  quote: "E5 (6510 МГц)"
  fix: "E5 (5885 МГц)"
  why: Boscam E band channel 5 is 5885 MHz. 6510 MHz is not a 5.8 GHz band channel.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/io/vtx_string.c
- severity: error
  file: content/foundation/ops-field.md
  quote: "F1 (6590 МГц)"
  fix: "F1 (5740 МГц)"
  why: FatShark F1 is 5740 MHz.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/io/vtx_string.c

## math-linalg-rot
verified: 16
- severity: error
  file: content/math/math-linalg-rot.md
  quote: "Ответ проверьте через `R_nbᵀ · (0, 0, 9.81)`."
  fix: "Ответ проверьте через `R_nbᵀ · (0, 0, −9.81)`: акселерометр меряет удельную силу (−g), поэтому в горизонте в FRD он показывает (0, 0, −9.81)."
  why: The step asks what the accelerometer reads. That is specific force (−g), not the gravity vector (est-sensors: "+1 g вверх"; ArduPilot IMU.AccZ ≈ −9.81 level).
  source: recomputed: f_body = R_nbᵀ·(g_ned − a) with a = 0 → R_nbᵀ·(0,0,−9.81)

## math-ode-dyn
verified: 14
- severity: error
  file: content/math/math-ode-dyn.md
  quote: "(Эйлер вперёд, Эйлер назад, точная формула k = T_s/(τ + T_s))"
  fix: "(Эйлер вперёд k = T_s/τ, Эйлер назад k = T_s/(τ + T_s), точная формула k = 1 − e^(−T_s/τ))"
  why: k = T_s/(τ+T_s) is the backward-Euler gain, as the module's own theory section says. The exact (impulse-invariant) PT1 gain is 1 − e^(−T_s/τ).
  source: recomputed: backward Euler y_k = y_{k-1} + (T_s/τ)(x_k − y_k) ⇒ k = T_s/(τ+T_s)
- severity: error
  file: content/math/math-ode-dyn.md
  quote: "Эйлер вперёд даёт неустойчивость при f_c > f_s/(2π)"
  fix: "Эйлер вперёд даёт неустойчивость при f_c > f_s/π (полюс 1 − 2π·f_c·T_s уходит за −1; при f_c > f_s/(2π) он уже отрицателен — знакопеременный «звон»)"
  why: The forward-Euler PT1 pole is 1 − T_s/τ, which is unstable when T_s/τ > 2, i.e. f_c > f_s/π. The f_s/(2π) threshold only marks where the pole becomes negative.
  source: recomputed: fs=100: f_c=16 → pole −0.005 (stable), f_c=30 → −0.885 (stable), f_c=32 → −1.011 (unstable); f_s/π = 31.8 Hz

## math-prob-est
verified: 14
- severity: error
  file: content/math/math-prob-est.md
  quote: "«EKF variance» в failsafe — это диагональные элементы P, превысившие порог"
  fix: "«EKF variance» в failsafe ArduPilot — это нормированные инновации (√test ratio скорости, позиции, компаса — те же числа, что в `XKF4`), превысившие `FS_EKF_THRESH`"
  why: ekf_check uses get_variances(), which returns sqrt of the innovation test ratios, not covariance diagonals.
  source: https://github.com/ArduPilot/ardupilot/blob/master/ArduCopter/ekf_check.cpp ; https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_NavEKF3/AP_NavEKF3_Outputs.cpp
- severity: imprecise
  file: content/math/math-prob-est.md
  quote: "`EK3_GYRO_P_NSE` ≈ ARW в рад/с/√Гц"
  fix: "`EK3_GYRO_P_NSE` задаётся в рад/с (по умолчанию 0.015 — с большим запасом над паспортной плотностью шума, потому что он покрывает вибрации и ошибки модели)"
  why: The parameter's units are rad/s (default 1.5E-02), not a noise density. A datasheet ARW of about 5e-5 rad/s/√Hz is orders of magnitude lower.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_NavEKF3/AP_NavEKF3.cpp
- severity: imprecise
  file: content/math/math-prob-est.md
  quote: "P по позиции растёт как t^1.5"
  fix: "σ позиции растёт как t^1.5 (дисперсия P — как t³)"
  why: Under VRW the position standard deviation grows as t^1.5, so the variance (P) grows as t³. The module's own theory says position error grows as t^1.5.
  source: recomputed: σ_p ∝ t^1.5 ⇒ P = σ_p² ∝ t³

## ctl-signals
verified: 12, no findings

## ctl-theory
verified: 10
- severity: imprecise
  file: content/tools/ctl-theory.md
  quote: "В Betaflight angle mode: `angle_p` поверх rate PID."
  fix: "В Betaflight angle mode: `angle_p_gain` (4.5) поверх rate PID."
  why: The Betaflight 4.5 parameter is angle_p_gain. There is no `angle_p`.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/fc/parameter_names.h

## data-python
verified: 12
- severity: imprecise
  file: content/tools/data-python.md
  quote: "до — `gyroUnfilt` в новых версиях при `debug_mode = GYRO_SCALED`"
  fix: "до — `gyroUnfilt` (отдельное поле blackbox в 4.5, включается выбором полей; `debug_mode = GYRO_SCALED` пишет нефильтрованный гироскоп в `debug[]`)"
  why: In 4.5, gyroUnfilt is a regular blackbox field gated by FIELD_SELECT(GYROUNFILT), not by debug_mode.
  source: https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/blackbox/blackbox.c

## tools-overview
verified: 8, no findings

## unverified
- el-battery-packs: Sony VTC6 "30 А" continuous. The Sony datasheet rates 15 A (30 A only with an 80 °C cutoff, by memory). Not confirmed against a primary datasheet.
- Lithium fire suppression: f-safety ("водой её не потушить", class D/ABC) and el-battery-packs (class D) contradict f-electricity-101 ("Много воды ... допустима"). Class D is for metallic lithium. Not confirmed because the Battery University BU-304a fetch was blocked: https://batteryuniversity.com/article/bu-304a-safety-concerns-with-li-ion
- f-regulations: the EASA open-category page fetch was blocked (https://www.easa.europa.eu/en/domains/civil-drones/drones-regulatory-framework-background/open-category-civil-drones). The C0–C4 finding relies on SKYbrary plus the regulation text.
- f-motors-esc: "2207 даёт больше момента на низких оборотах, 2306 — выше КПД на высоких". Oscar Liang's motor guide does not address it, and common FPV wisdom says the opposite (wider stator gives more low-RPM torque).
- est-alt-sources: lidar ranges (TF02 40 m, TF03 180 m). The ArduPilot TF02 page lists TF02 10 m, TF02-Pro 13.5 m and TF03 50 m, while Benewake marketing gives 22/40/180 m. These depend on reflectivity and could not be reconciled.
- est-gnss: u-blox M10 "до 25 Гц" and M8 "4 созвездия сразу (частота падает)" (M8 supports at most 3 concurrent GNSS) were not checked against u-blox product summaries.
- nav-resilience: "GSF ... автоматически при `COMPASS_USE = 0`" was not confirmed.
- f-fc-sensors: Softserial "до 115200 бод" and MPU6000 "снят с производства" were not confirmed.
- tools-overview: Betaflight SITL `make SITL` (it may be `make TARGET=SITL`) was not confirmed.
- f-aero-props: "4008 380KV 15×5.5 6S: ~880 г при ~7 А" has no manufacturer table at hand.
