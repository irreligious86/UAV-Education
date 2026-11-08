# ardupilot

Basis: ArduPilot source, master @2a54162 (2026-11-08) and branches ArduPilot-4.7 (current stable, Copter/Plane 4.7.2, 4.7.3-beta1), ArduPilot-4.6, Copter-4.5, Plane-4.2…4.5; pymavlink master; mavlink common.xml master; INAV settings.yaml (7.1 and master); ardupilot.org pages read through WebFetch.
Systemic note: Copter 4.7 (stable since July 2026) renamed many parameters that the course calls "4.5+": ARMING_CHECK→ARMING_SKIPCHK (with inverted meaning), WPNAV_*→WP_* (m, m/s), RTL_ALT→RTL_ALT_M, RTL_ALT_FINAL→RTL_ALT_FINAL_M, ATC_ACCEL_*_MAX→ATC_ACC_*_MAX (deg/s²), PSC_ACCZ_*→PSC_D_ACC_* (×0.1). Source: ArduCopter/ReleaseNotes.txt, 4.7.0-beta1, section "5) Parameter scaling and/or renaming". Each occurrence is listed below as "outdated".

## aero-wing
verified: 30
- severity: error
  file: content/ardupilot/aero-wing.md
  quote: "`nav_fw_min_throttle/max_throttle/cruise_throttle`"
  fix: "`nav_fw_min_thr/max_thr/cruise_thr`"
  why: INAV has no nav_fw_*_throttle settings; the real names are nav_fw_min_thr, nav_fw_max_thr, nav_fw_cruise_thr (7.1 and master).
  source: https://github.com/iNavFlight/inav/blob/master/src/main/fc/settings.yaml
- severity: imprecise
  file: content/ardupilot/aero-wing.md
  quote: "1 — баланс; у крыла близко к 2 — скорость важнее)"
  fix: "1 — баланс, по умолчанию; 2 — тангаж держит только скорость, газ — высоту, рекомендовано для планеров)"
  why: TECS_SPDWEIGHT defaults to 1.0. The param doc recommends 2 for gliders, not for powered wings in general.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_TECS/AP_TECS.cpp

## ap-companion
verified: 24
- severity: error
  file: content/ardupilot/ap-companion.md
  quote: "if hb and m.mode_mapping_bynumber(hb.custom_mode) != \"GUIDED\":"
  fix: "if hb and hb.type != mavutil.mavlink.MAV_TYPE_GCS and mavutil.mode_string_v10(hb) != \"GUIDED\":"
  why: the pymavlink connection object has no mode_mapping_bynumber() method (it is a module-level function that takes a mav_type), so this raises AttributeError. A GCS heartbeat would also be read as a mode change.
  source: https://github.com/ArduPilot/pymavlink/blob/master/mavutil.py
- severity: error
  file: content/ardupilot/ap-companion.md
  quote: "m = mavutil.mavlink_connection(\"udp:127.0.0.1:14551\"); m.wait_heartbeat()"
  fix: "m = mavutil.mavlink_connection(\"tcp:127.0.0.1:5762\"); m.wait_heartbeat()"
  why: since Copter-4.5, sim_vehicle.py tells MAVProxy to output only to 14550+10*i. Nothing sends to 14551, so wait_heartbeat() hangs.
  source: https://github.com/ArduPilot/ardupilot/blob/ArduPilot-4.7/Tools/autotest/sim_vehicle.py
- severity: outdated
  file: content/ardupilot/ap-companion.md
  quote: "(4) `WPNAV_SPEED`/`PSC_*` не ограничивают до нуля"
  fix: "(4) `WP_SPD` (до 4.7 — `WPNAV_SPEED`)/`PSC_*` не ограничивают до нуля"
  why: Copter 4.7 renamed the WPNAV_* params to WP_* and converted them to metres.
  source: https://github.com/ArduPilot/ardupilot/blob/ArduPilot-4.7/libraries/AC_WPNav/AC_WPNav.cpp

## ap-ekf
verified: 30
- severity: error
  file: content/ardupilot/ap-ekf.md
  quote: "`EK3_GPS_DELAY`/`EK3_FLOW_DELAY` (задержка измерений, мс)"
  fix: "`GPS1_DELAY_MS`/`EK3_FLOW_DELAY`/`EK3_HGT_DELAY` (задержка измерений, мс)"
  why: EKF3 has no EK3_GPS_DELAY. GPS delay is set by the GPS driver param GPS1_DELAY_MS. EK3 only has FLOW_DELAY, HGT_DELAY and BCN_DELAY.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_NavEKF3/AP_NavEKF3.cpp
- severity: imprecise
  file: content/ardupilot/ap-ekf.md
  quote: "квадрат отношения инновации к допустимой"
  fix: "корень из test ratio, то есть отношение инновации к допустимой"
  why: getVariances() logs sqrtF(testRatio). The test ratio is already the squared normalised innovation, so the logged value is the plain ratio, not its square.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_NavEKF3/AP_NavEKF3_Outputs.cpp
- severity: imprecise
  file: content/ardupilot/ap-ekf.md
  quote: "`XKF2` — оценённые bias гироскопа/акселерометра и ветер; `XKF1` — состояние (скорости, позиция, углы)"
  fix: "`XKF2` — оценённый bias акселерометра, ветер и магнитное поле; `XKF1` — состояние (углы, скорости, позиция) и bias гироскопа (`GX/GY/GZ`)"
  why: per LogStructure, gyro bias (GX, GY, GZ) is in XKF1. XKF2 holds AX/AY/AZ, VWN/VWE and the mag field.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_NavEKF3/LogStructure.h

## ap-heavy
verified: 28
- severity: error
  file: content/ardupilot/ap-heavy.md
  quote: "sim_vehicle.py -v ArduCopter -f octaquad --console --map"
  fix: "sim_vehicle.py -v ArduCopter -f octa-quad --console --map"
  why: "octaquad" is not a frame name. Prefix matching resolves it to "octa", a flat octocopter with FRAME_CLASS=3 defaults, not the X8. The correct frame is "octa-quad".
  source: https://github.com/ArduPilot/ardupilot/blob/master/Tools/autotest/pysim/vehicleinfo.py
- severity: imprecise
  file: content/ardupilot/ap-heavy.md
  quote: "распределяет roll/pitch, затем throttle, затем yaw"
  fix: "распределяет roll/pitch, затем yaw (с минимальным запасом `MOT_YAW_HEADROOM`), а throttle — тем, что осталось"
  why: in output_armed_stabilizing() yaw is fitted before throttle, and throttle is reduced to make room. The code comments also recommend MOT_YAW_HEADROOM=300 for X8.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_Motors/AP_MotorsMatrix.cpp
- severity: outdated
  file: content/ardupilot/ap-heavy.md
  quote: "`ATC_ACCEL_R/P_MAX` 50 000 (медленнее, чем 5\")"
  fix: "`ATC_ACC_R/P_MAX` ≈ 500–700 °/с² (до 4.7 — `ATC_ACCEL_R/P_MAX` в cdeg/s², 50 000–70 000; медленнее, чем 5\")"
  why: 4.7 renamed and rescaled these to deg/s². The tuning guide gives 1100 for 10" and 500 for 20".
  source: https://ardupilot.org/copter/docs/setting-up-for-tuning.html
- severity: imprecise
  file: content/ardupilot/ap-heavy.md
  quote: "`INS_GYRO_FILTER` 20 Гц"
  fix: "`INS_GYRO_FILTER` ≈ 30 Гц (между 40 Гц для 10\" и 20 Гц для 20\")"
  why: the tuning guide gives 40 Hz for 10" and 20 Hz for 20"+. 20 Hz is the value for 20", not for 15".
  source: https://ardupilot.org/copter/docs/setting-up-for-tuning.html
- severity: outdated
  file: content/ardupilot/ap-heavy.md
  quote: "`PSC_ACCZ_P` ≈ 0.3× газа висения"
  fix: "`PSC_D_ACC_P` (до 4.7 — `PSC_ACCZ_P`; в 4.7 значение ×0.1) ≈ 0.3× газа висения"
  why: 4.7 renamed _ACCZ_ to _D_ACC_ and scaled P by 0.1 ("If upgrading from 4.6 this is _ACCZ_P * 0.1").
  source: https://github.com/ArduPilot/ardupilot/blob/ArduPilot-4.7/libraries/AC_AttitudeControl/AC_PosControl.cpp
- severity: outdated
  file: content/ardupilot/ap-heavy.md
  quote: "проверка `PSC_ACCZ`"
  fix: "проверка `PSC_D_ACC_*` (до 4.7 — `PSC_ACCZ_*`)"
  why: same rename in 4.7.
  source: https://github.com/ArduPilot/ardupilot/blob/ArduPilot-4.7/libraries/AC_AttitudeControl/AC_PosControl.cpp

## ap-intro
verified: 32
- severity: outdated
  file: content/ardupilot/ap-intro.md
  quote: "а не отключать `ARMING_CHECK`"
  fix: "а не отключать проверки (`ARMING_SKIPCHK` в 4.7+, `ARMING_CHECK` в 4.6 и раньше)"
  why: 4.7 replaced ARMING_CHECK with ARMING_SKIPCHK, a bitmask of checks to skip where 0 means none skipped.
  source: https://github.com/ArduPilot/ardupilot/blob/ArduPilot-4.7/libraries/AP_Arming/AP_Arming.cpp
- severity: outdated
  file: content/ardupilot/ap-intro.md
  quote: "`ATC_INPUT_TC`, `PSC_ACCZ_*`"
  fix: "`ATC_INPUT_TC`, `PSC_D_ACC_*` (до 4.7 — `PSC_ACCZ_*`)"
  why: renamed in 4.7.
  source: https://github.com/ArduPilot/ardupilot/blob/ArduPilot-4.7/libraries/AC_AttitudeControl/AC_PosControl.cpp

## ap-logs
verified: 34, no findings

## ap-lua
verified: 38
- severity: imprecise
  file: content/ardupilot/ap-lua.md
  quote: "Если один скрипт исчерпал память или упал с ошибкой, останавливаются все скрипты до перезагрузки."
  fix: "Если один скрипт упал с ошибкой, останавливается только он. Если кончилась общая память скриптов (или паника), останавливаются все скрипты до перезагрузки."
  why: docs and lua_scripts.cpp agree: on an error only that script is removed. Only out-of-memory or a panic terminates all scripts.
  source: https://ardupilot.org/copter/docs/common-lua-scripts.html
- severity: error
  file: content/ardupilot/ap-lua.md
  quote: "`VTOL-quicktune.lua`/`copter-quicktune` (QuikTune)"
  fix: "`VTOL-quicktune.lua` (QuikTune для мультикоптеров и VTOL), `rover-quicktune.lua`"
  why: there is no copter-quicktune applet. VTOL-quicktune.lua covers multicopters too.
  source: https://github.com/ArduPilot/ardupilot/tree/master/libraries/AP_Scripting/applets
- severity: outdated
  file: content/ardupilot/ap-lua.md
  quote: "`rangefinder:distance_cm_orient()`"
  fix: "`rangefinder:distance_orient()` (в метрах; `distance_cm_orient` устарел)"
  why: docs.lua (4.7 and master) marks distance_cm_orient as @deprecated and points to distance_orient (metres). ahrs:get_yaw() is likewise deprecated in favour of get_yaw_rad().
  source: https://github.com/ArduPilot/ardupilot/blob/ArduPilot-4.7/libraries/AP_Scripting/docs/docs.lua
- severity: error
  file: content/ardupilot/ap-lua.md
  quote: "      t = t / 100"
  fix: "      t = t // 100"
  why: ArduPilot embeds Lua 5.3.6. Here "/" always returns a float, and string.format("%d", 80.5) raises "number has no integer representation", which kills the script exactly when the temperature is not a whole degree.
  source: https://www.lua.org/manual/5.3/manual.html#pdf-string.format
- severity: imprecise
  file: content/ardupilot/ap-lua.md
  quote: "«script took too long»"
  fix: "«<имя>.lua exceeded time limit»"
  why: the actual STATUSTEXT emitted on an instruction-count overrun is "%s exceeded time limit".
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_Scripting/lua_scripts.cpp
- severity: error
  file: content/ardupilot/ap-lua.md
  quote: "В SITL с рамой `octaquad`"
  fix: "В SITL с рамой `octa-quad`"
  why: "-f octaquad" resolves by prefix to a flat "octa" (FRAME_CLASS 3). The X8 frame is "octa-quad".
  source: https://github.com/ArduPilot/ardupilot/blob/master/Tools/autotest/pysim/vehicleinfo.py

## ap-missions
verified: 36
- severity: error
  file: content/ardupilot/ap-missions.md
  quote: "items = [item(0, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, alt=20)]"
  fix: "items = [item(0, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT), item(1, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, alt=20)]  # seq 0 = home"
  why: ArduPilot reserves mission item 0 for home (AP_MISSION_FIRST_REAL_COMMAND = 1). A TAKEOFF uploaded as seq 0 is treated as home and lost. The following seq values (i + 1, len(items)) then line up as written.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_Mission/AP_Mission.h
- severity: error
  file: content/ardupilot/ap-missions.md
  quote: "бит 1 — учитывать расстояние до посадки в failsafe АКБ; "
  fix: "бит 1 — учитывать расстояние до посадки в failsafe АКБ (только Plane); "
  why: MIS_OPTIONS @Bitmask{Copter} has only bits 0 (Clear on reboot) and 2 (ContinueAfterLand). Bit 1 is not available on Copter.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_Mission/AP_Mission.cpp
- severity: error
  file: content/ardupilot/ap-missions.md
  quote: "+ бит 1 `MIS_OPTIONS`"
  fix: "+ запас ёмкости на возврат"
  why: MIS_OPTIONS bit 1 does not exist for Copter, and this example is a Copter survey.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_Mission/AP_Mission.cpp
- severity: imprecise
  file: content/ardupilot/ap-missions.md
  quote: "Переход в AUTO на земле с заармленным аппаратом выполняет взлёт."
  fix: "Переход в AUTO на земле с заармленным аппаратом запускает взлёт после подъёма газа пилотом (или сразу, если в `AUTO_OPTIONS` включён бит 1 «Allow Takeoff Without Raising Throttle»); в SITL — `rc 3 1500`."
  why: Copter sets auto_armed only after the throttle is raised, unless the AUTO_OPTIONS AllowTakeOffWithoutRaisingThrottle bit is set. Practice step 1 ("Арм, режим AUTO, наблюдай") will otherwise just sit on the ground.
  source: https://github.com/ArduPilot/ardupilot/blob/master/ArduCopter/mode_auto.cpp
- severity: imprecise
  file: content/ardupilot/ap-missions.md
  quote: "Потеря радиосвязи во время AUTO ведёт себя по `FS_THR_ENABLE`: можно продолжать миссию, уйти в RTL или сесть."
  fix: "Потеря радиосвязи во время AUTO ведёт себя по `FS_THR_ENABLE` (RTL, Land, SmartRTL…), а продолжение миссии включается битом 0 `FS_OPTIONS`."
  why: the FS_THR_ENABLE value 2 "Continue with Mission" was removed in 4.0. Continuing the mission is now FS_OPTIONS bit 0.
  source: https://github.com/ArduPilot/ardupilot/blob/master/ArduCopter/Parameters.cpp
- severity: outdated
  file: content/ardupilot/ap-missions.md
  quote: "`WPNAV_SPEED` (см/с горизонталь), `WPNAV_SPEED_UP/DN`, `WPNAV_RADIUS` (радиус захвата), `WPNAV_ACCEL`"
  fix: "`WP_SPD` (м/с горизонталь), `WP_SPD_UP/DN`, `WP_RADIUS_M` (радиус захвата), `WP_ACC` (до 4.7 — `WPNAV_SPEED` в см/с, `WPNAV_SPEED_UP/DN`, `WPNAV_RADIUS`, `WPNAV_ACCEL`)"
  why: 4.7 renamed WPNAV_* to WP_* and converted them to m and m/s.
  source: https://github.com/ArduPilot/ardupilot/blob/ArduPilot-4.7/libraries/AC_WPNav/AC_WPNav.cpp
- severity: imprecise
  file: content/ardupilot/ap-missions.md
  quote: "TERRAIN_ENABLE`, `TERRAIN_FOLLOW`"
  fix: "TERRAIN_ENABLE`, frame «Terrain» у точек и `WP_RFND_USE`/`RTL_ALT_TYPE`"
  why: TERRAIN_FOLLOW is a Plane-only parameter. Copter has no such param and follows terrain per waypoint frame, with WP_RFND_USE and RTL_ALT_TYPE.
  source: https://github.com/ArduPilot/ardupilot/blob/master/ArduPlane/Parameters.cpp

## ap-quadplane
verified: 34
- severity: outdated
  file: content/ardupilot/ap-quadplane.md
  quote: "пока airspeed не достигнет `ARSPD_FBW_MIN` (минимальная скорость крыла)"
  fix: "пока airspeed не достигнет `AIRSPEED_MIN` (минимальная скорость крыла; до 4.5 — `ARSPD_FBW_MIN`)"
  why: Plane 4.5 renamed ARSPD_FBW_MIN to AIRSPEED_MIN, and the module targets "ArduPlane 4.5+". aero-wing already uses AIRSPEED_MIN.
  source: https://github.com/ArduPilot/ardupilot/blob/Plane-4.5/ArduPlane/Parameters.cpp
- severity: outdated
  file: content/ardupilot/ap-quadplane.md
  quote: "Слишком маленький `ARSPD_FBW_MIN` относительно V_s"
  fix: "Слишком маленький `AIRSPEED_MIN` относительно V_s"
  why: same rename in Plane 4.5.
  source: https://github.com/ArduPilot/ardupilot/blob/Plane-4.5/ArduPlane/Parameters.cpp
- severity: outdated
  file: content/ardupilot/ap-quadplane.md
  quote: "пока не набрана ARSPD_FBW_MIN"
  fix: "пока не набрана AIRSPEED_MIN"
  why: same rename in Plane 4.5.
  source: https://github.com/ArduPilot/ardupilot/blob/Plane-4.5/ArduPlane/Parameters.cpp
- severity: outdated
  file: content/ardupilot/ap-quadplane.md
  quote: "в FBWA с `ARSPD_FBW_MIN` = 1.3 V_s"
  fix: "в FBWA с `AIRSPEED_MIN` = 1.3 V_s"
  why: same rename in Plane 4.5.
  source: https://github.com/ArduPilot/ardupilot/blob/Plane-4.5/ArduPlane/Parameters.cpp
- severity: outdated
  file: content/ardupilot/ap-quadplane.md
  quote: "`ARSPD_FBW_MIN` ниже реальной V_s"
  fix: "`AIRSPEED_MIN` ниже реальной V_s"
  why: same rename in Plane 4.5.
  source: https://github.com/ArduPilot/ardupilot/blob/Plane-4.5/ArduPlane/Parameters.cpp
- severity: outdated
  file: content/ardupilot/ap-quadplane.md
  quote: "`Q_LAND_SPEED`, `Q_LAND_FINAL_ALT`"
  fix: "`Q_LAND_FINAL_SPD` (м/с), `Q_LAND_FINAL_ALT`"
  why: Q_LAND_SPEED (cm/s) existed up to Plane 4.3. Plane 4.5, 4.6 and 4.7 have Q_LAND_FINAL_SPD (m/s) instead.
  source: https://github.com/ArduPilot/ardupilot/blob/ArduPilot-4.7/ArduPlane/quadplane.cpp

## ap-safety-fs
verified: 40
- severity: error
  file: content/ardupilot/ap-safety-fs.md
  quote: "0 выкл, 1 RTL, 3 SmartRTL/RTL, 4 SmartRTL/Land, 5 Land, 6 DO_LAND_START или RTL, 7 Brake/Land"
  fix: "0 выкл, 1 RTL, 3 Land, 4 SmartRTL/RTL, 5 SmartRTL/Land, 6 DO_LAND_START или RTL, 7 Brake/Land"
  why: FS_THR_ENABLE values are 3 = always Land, 4 = SmartRTL or RTL, 5 = SmartRTL or Land. The module shifts 3–5.
  source: https://github.com/ArduPilot/ardupilot/blob/master/ArduCopter/Parameters.cpp
- severity: error
  file: content/ardupilot/ap-safety-fs.md
  quote: "| те же действия; актуален для Guided/телеметрии |"
  fix: "| 0 выкл, 1 RTL, 3 SmartRTL/RTL, 4 SmartRTL/Land, 5 Land, 6 DO_LAND_START или RTL, 7 Brake/Land (нумерация отличается от `FS_THR_ENABLE`); актуален для Guided/телеметрии |"
  why: FS_GCS_ENABLE numbering differs from FS_THR_ENABLE (3 = SmartRTL/RTL, 5 = Land), so "the same actions" leads to wrong values.
  source: https://github.com/ArduPilot/ardupilot/blob/master/ArduCopter/Parameters.cpp
- severity: outdated
  file: content/ardupilot/ap-safety-fs.md
  quote: "RTL сначала набирает `RTL_ALT` (минимальная высота над домом для возврата, по умолчанию 15 м;"
  fix: "RTL сначала набирает `RTL_ALT_M` (в 4.6 и раньше — `RTL_ALT` в см; минимальная высота над домом для возврата, по умолчанию 15 м;"
  why: 4.7 moved RTL_ALT to RTL_ALT_M, and RTL_ALT_FINAL to RTL_ALT_FINAL_M (metres).
  source: https://github.com/ArduPilot/ardupilot/blob/ArduPilot-4.7/ArduCopter/mode_rtl.cpp
- severity: outdated
  file: content/ardupilot/ap-safety-fs.md
  quote: "Плюс **пред-армовые проверки** (`ARMING_CHECK`)"
  fix: "Плюс **пред-армовые проверки** (`ARMING_SKIPCHK` в 4.7+, `ARMING_CHECK` раньше)"
  why: 4.7 replaced ARMING_CHECK with the skip-bitmask ARMING_SKIPCHK.
  source: https://github.com/ArduPilot/ardupilot/blob/ArduPilot-4.7/libraries/AP_Arming/AP_Arming.cpp

## ap-sitl
verified: 30
- severity: error
  file: content/ardupilot/ap-sitl.md
  quote: "`-f octaquad`, `-f quad`, `-f quadplane`"
  fix: "`-f octa-quad`, `-f quad`, `-f quadplane`"
  why: "octaquad" is not a frame. It prefix-matches "octa", a flat octocopter with FRAME_CLASS 3 defaults.
  source: https://github.com/ArduPilot/ardupilot/blob/master/Tools/autotest/pysim/vehicleinfo.py
- severity: error
  file: content/ardupilot/ap-sitl.md
  quote: "sim_vehicle.py -v ArduCopter -f octaquad --console --map -w"
  fix: "sim_vehicle.py -v ArduCopter -f octa-quad --console --map -w"
  why: same frame-name issue as above.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/SITL/SIM_Frame.cpp
- severity: imprecise
  file: content/ardupilot/ap-sitl.md
  quote: "plane, quadplane, tiltrotor, rover"
  fix: "plane, quadplane, quadplane-tilttri/quadplane-tilt (тилтроторы), rover"
  why: no "tiltrotor" frame exists. The tilt-rotor SITL frames are quadplane-tilt, quadplane-tilttri, quadplane-tilttrivec and quadplane-tilthvec.
  source: https://github.com/ArduPilot/ardupilot/blob/master/Tools/autotest/pysim/vehicleinfo.json

## ap-tuning
verified: 38
- severity: error
  file: content/ardupilot/ap-tuning.md
  quote: "INS_GYRO_FILTER` (20 Гц для 10\"+, 40 для 7\", 80 для 5\")"
  fix: "INS_GYRO_FILTER` (80 Гц для 5\", 40 для 10\", 20 для 20\" и больше)"
  why: the official guide gives 80 Hz for 5", 40 Hz for 10" and 20 Hz for 20"+. The module puts 10" at 20 Hz.
  source: https://ardupilot.org/copter/docs/setting-up-for-tuning.html
- severity: outdated
  file: content/ardupilot/ap-tuning.md
  quote: "`PSC_ACCZ_P/I` под газ висения"
  fix: "`PSC_D_ACC_P/I` (до 4.7 — `PSC_ACCZ_P/I`, в 4.7 значения ×0.1) под газ висения"
  why: renamed and rescaled in 4.7.
  source: https://github.com/ArduPilot/ardupilot/blob/ArduPilot-4.7/libraries/AC_AttitudeControl/AC_PosControl.cpp
- severity: outdated
  file: content/ardupilot/ap-tuning.md
  quote: "`ATC_ACCEL_R/P/Y_MAX`"
  fix: "`ATC_ACC_R/P/Y_MAX` (°/с²; до 4.7 — `ATC_ACCEL_R/P/Y_MAX` в cdeg/s²)"
  why: 4.7 renamed these to ATC_ACC_*_MAX in deg/s².
  source: https://github.com/ArduPilot/ardupilot/blob/ArduPilot-4.7/libraries/AC_AttitudeControl/AC_AttitudeControl.cpp
- severity: outdated
  file: content/ardupilot/ap-tuning.md
  quote: "начинать с 0.10 по умолчанию"
  fix: "по умолчанию 0.075 с 4.6 (0.1 в 4.5 и раньше)"
  why: the AUTOTUNE_AGGR code default changed from 0.1 (Copter-4.5) to 0.075 (4.6 and 4.7). The docs page still says 0.1. 4.7 also adds AUTOTUNE_GMBK (0.25 gain backoff).
  source: https://github.com/ArduPilot/ardupilot/blob/ArduPilot-4.7/libraries/AC_AutoTune/AC_AutoTune_Multi.cpp
- severity: error
  file: content/ardupilot/ap-tuning.md
  quote: "QuikTune (Lua-скрипт `quicktune.lua`, тумблер `QUIK_ENABLE`)"
  fix: "QuikTune (Lua-applet `VTOL-quicktune.lua`, включается параметром `QUIK_ENABLE`, тумблер — `RCx_OPTION = 300` или `QUIK_RC_FUNC`)"
  why: the applet file is VTOL-quicktune.lua (there is no quicktune.lua). QUIK_ENABLE is an enable parameter, not a switch. The switch is aux function 300 or QUIK_RC_FUNC.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_Scripting/applets/VTOL-quicktune.md
- severity: imprecise
  file: content/ardupilot/ap-tuning.md
  quote: "биты 0/1/4 не совмещать"
  fix: "биты 0 и 4 (double/triple) не совмещать — при обоих работает только double"
  why: the OPTS doc says "If both double and triple notches are specified only double notches will take effect". Multi-Source (bit 1) is combinable.
  source: https://github.com/ArduPilot/ardupilot/blob/ArduPilot-4.7/libraries/Filter/HarmonicNotchFilter.cpp

## unverified
- ap-intro: "«PreArm: Check fence» / «Need 3D Fix»": I did not find the exact message strings. AC_Fence emits "Fence requires position".
- ap-heavy: the hover numbers (880 g per motor, 7 A, 17 min, 55–65 Hz) and ATC_RAT P/I 0.08, D 0.003 start values are design estimates, not checkable against a reference.
- ap-tuning: "INS_LOG_BAT_OPT … 4 — до и после на 1 кГц": value 4 is "pre- and post-filter". I could not confirm the "1 kHz" qualifier.
- ap-logs: the GPS thresholds (HDOP < 1.5 good, < 12 sats bad) are not in the parameter or log reference. They are plausible, but I did not confirm them against the docs page.
- ap-heavy and ap-intro: "Initial Tune Parameters" helper in Mission Planner. The MP UI was not checked.
- ap-companion: the GUID_OPTIONS bits, GUID_TIMEOUT (3 s, 0.1–5), MAVLink ids 84/86/82 and the type_mask values were all verified correct (no finding).
