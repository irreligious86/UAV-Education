# stage4-wave2

Basis: ArduPilot source master @2a54162 (2026-11-08) and release branches ArduPilot-4.7, Copter-4.5, ArduPilot-4.6, Plane-4.5 (ArduCopter/Parameters.cpp, mode_rtl.cpp, mode_systemid.cpp, Log.cpp; libraries/GCS_MAVLink GCS.cpp, GCS_Common.cpp handle_radio_status, GCS_MAVLink_Parameters.cpp; AC_WPNav, AC_AttitudeControl_Multi and _Logging, AP_Follow, AP_L1_Control, AP_InertialSensor, AP_BattMonitor INA2xx and Params, AC_Fence, AP_Avoidance; ArduPlane/Parameters.cpp; Tools/autotest/sim_vehicle.py; ArduCopter/ReleaseNotes.txt). ardupilot_wiki master sources (using-sitl-for-ardupilot-testing, follow-mode, SiK pages), ardupilot.org SiK advanced configuration and SystemID pages (WebFetch). SiK firmware master (packet.c, parameters.h, mavlink.c). MAVLink common.xml (RADIO_STATUS). ExpressLRS MAVLink page. PX4-Autopilot main @68c3a54 (mavlink_params.yaml, fw_mode_manager_params.yaml NPFG_*, init.d-posix airframes and px4-rc.simulator, docs/en sources for controller_diagrams, position_tuning_guide_fixedwing, multi_vehicle_simulation). Betaflight 2025.12.6 and 4.5 sources (chirp.c, msp_box.c, settings.c). ardupilot_gazebo README (main), ros_gz_bridge README (jazzy), gz-sim8 cmdsim.rb.in. TI INA226 datasheet formulas (CAL = 0.00512 / (Current_LSB · R_shunt), 2.5 µV shunt LSB, ±81.92 mV, 36 V bus). IPC-2221 external-layer formula recomputed. All Python blocks compiled locally, and the ops-weather, ctl-guidance and ctl-sysid scripts run with numpy. Their printed outputs match the comments in the modules. Worked numbers recomputed: wind power law, ISA/density altitude, 1/√ρ hover power, e^-λt and 5-of-6, L1 = ζTV/π, S-curve 7.0/7.5 s, IPC-2221 widths, INA226 shunt, LSB and CAL, METAR knots to m/s and feet to m.

## ops-weather
verified: 26

## ops-maintenance
verified: 21

## link-telemetry-radios
verified: 33
- severity: error
  file: content/link/link-telemetry-radios.md
  quote: "`txbuf` (заполнение буфера, %)"
  fix: "`txbuf` (свободное место в буфере передачи, %)"
  why: In both MAVLink common.xml and SiK, RADIO_STATUS.txbuf is the remaining free transmit buffer space. ArduPilot slows its streams when txbuf drops below 50 and 20, so the module states the meaning backwards.
  source: https://mavlink.io/en/messages/common.html#RADIO_STATUS
- severity: outdated
  file: content/link/link-telemetry-radios.md
  quote: "снизить частоты потоков (`SRn_*` в ArduPilot)"
  fix: "снизить частоты потоков (`MAVn_*` в ArduPilot 4.7, нумерация с 1: MAV1 — бывший SR0; до 4.7 — `SRn_*`)"
  why: ArduPilot 4.7 removed the SR0_…SR6_ groups ("SR0 through SR6 was here"). Stream rates now live under the MAV group, per channel, as MAV1_…, for example MAV1_RAW_SENS. The ExpressLRS page also names SRx_ or MAVx_.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/GCS_MAVLink/GCS.cpp
- severity: imprecise
  file: content/link/link-telemetry-radios.md
  quote: "к наземке телеметрия идёт через Backpack по Wi-Fi или USB"
  fix: "к наземке телеметрия идёт через TX Backpack по Wi-Fi (UDP 14550) или по USB самого передатчика (460800)"
  why: The ExpressLRS MAVLink page describes two paths. One goes through the TX Backpack over Wi-Fi on UDP 14550. The other is a direct USB connection to the TX module at 460800 baud, which does not go through the Backpack.
  source: https://www.expresslrs.org/software/mavlink/
- severity: imprecise
  file: content/quiz/link-telemetry-radios.json
  quote: "Режет полезную скорость вдвое и дальность"
  fix: "Режет полезную скорость вдвое, на части чипов не работает"
  why: The ArduPilot SiK page says ECC halves the supported data rate and that some newer radio chips cannot do ECC and fail with it enabled. It does not say that ECC reduces range.
  source: https://ardupilot.org/copter/docs/common-3dr-radio-advanced-configuration-and-technical-information.html
- severity: imprecise
  file: content/quiz/link-telemetry-radios.json
  quote: "новые чипы его не поддерживают."
  fix: "часть новых радиочипов его не поддерживает и с ECC = 1 не работает."
  why: The SiK page limits this to "some newer radio chips". It is not true of all new chips.
  source: https://ardupilot.org/copter/docs/common-3dr-radio-advanced-configuration-and-technical-information.html

## mav-multi-vehicle
verified: 30
- severity: error
  file: content/companion/mav-multi-vehicle.md
  quote: "sim_vehicle.py -v Copter --count 3 --auto-sysid --location CMAC --auto-offset-line 90,10 --map --console` — три коптера в линию через 10 м, sysid 1…3."
  fix: "sim_vehicle.py -v Copter --count 3 --auto-sysid --location CMAC --auto-offset-line 90,10 --mcast --map --console` — три коптера в линию через 10 м, sysid 1…3; `--mcast` пускает MAVLink между аппаратами (без него ведомый в FOLLOW из шага 4 не услышит ведущего)."
  why: Without --mcast, sim_vehicle.py gives MAVProxy one separate TCP master per instance and nothing passes between vehicles. The wiki says to add --mcast "to send all mavlink data between the vehicles", and its example command includes it. Without it, the FOLLOW lab in step 4 never receives the leader's GLOBAL_POSITION_INT.
  source: https://ardupilot.org/dev/docs/using-sitl-for-ardupilot-testing.html

## ctl-guidance
verified: 27
- severity: imprecise
  file: content/tools/ctl-guidance.md
  quote: "L1 — тот же закон бокового ускорения, но дальность упреждения растёт со скоростью, чтобы динамика выхода на линию не зависела от скорости:"
  fix: "L1 — тот же закон бокового ускорения (в ArduPilot с коэффициентом 4ζ² вместо 2: a = 4ζ²·V²·sin η / L1, при ζ = 0.707 — ровно pure pursuit), но дальность упреждения растёт со скоростью, чтобы динамика выхода на линию не зависела от скорости:"
  why: AP_L1_Control computes latAccDem = K_L1·V²/L1·sin(Nu) with K_L1 = 4·NAVL1_DAMPING². At the default 0.75 the gain is 2.25, not the pure-pursuit 2. The L1 distance formula 0.3183·ζ·T·V and the 73 m example are correct.
  source: https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_L1_Control/AP_L1_Control.cpp
- severity: imprecise
  file: content/tools/ctl-guidance.md
  quote: "(`WPNAV_SPEED`, `WPNAV_ACCEL`, `WPNAV_JERK`; в Copter 4.7 — семейство `WP_*` в м/с)"
  fix: "(`WPNAV_SPEED`, см/с; `WPNAV_ACCEL`, см/с²; `WPNAV_JERK`, м/с³; в Copter 4.7 — `WP_SPD`, м/с; `WP_ACC`, м/с²; `WP_JERK`, м/с³)"
  why: In 4.7 the WPNAV_ group became WP_ with the names SPD, ACC, JERK and RADIUS_M. Only speed is in m/s; acceleration is m/s² and jerk is m/s³. Before 4.7, WPNAV_SPEED and WPNAV_ACCEL were in cm units. The WP_RADIUS_M rename in the same sentence is correct.
  source: https://github.com/ArduPilot/ardupilot/blob/ArduPilot-4.7/libraries/AC_WPNav/AC_WPNav.cpp
- severity: error
  file: content/tools/ctl-guidance.md
  quote: "- PX4 — Fixed-wing path following (NPFG) | https://docs.px4.io/main/en/flight_stack/controller_diagrams.html | primary | B"
  fix: "- PX4 — Fixed-wing position tuning (NPFG) | https://docs.px4.io/main/en/config_fw/position_tuning_guide_fixedwing.html | primary | B"
  why: The controller_diagrams page covers only TECS and the attitude controllers for fixed-wing, with no mention of NPFG. The fixed-wing position tuning guide states that PX4 uses NPFG for horizontal control and documents NPFG_PERIOD and NPFG_DAMPING.
  source: https://github.com/PX4/PX4-Autopilot/blob/main/docs/en/config_fw/position_tuning_guide_fixedwing.md

## ctl-sysid
verified: 27
- severity: error
  file: content/tools/ctl-sysid.md
  quote: "Взлёт, висение, режим SYSID, запись до конца, выход. Из лога (`SIDD`) взять вход и угловую скорость по крену (имена полей — по описанию сообщения в документации логов своей версии), прогнать через код шага 1."
  fix: "Взлёт, висение в STABILIZE (из GUIDED или ALT_HOLD вход для осей 1–13 запрещён), режим SYSID, запись до конца, выход. Из лога взять вход объекта — `RATE.ROut` (выход регулятора вместе с подмешанным чирпом; `SIDD.Targ` — только сам чирп, с ним получится оценка «задание → выход») — и угловую скорость по крену (`SIDD.Gx` или `RATE.R`), привести к общей частоте и прогнать через код шага 1."
  why: SIDD logs only TimeUS, Time, Targ (the injected waveform), F, Gx/Gy/Gz and Ax/Ay/Az, so it holds no plant input. The chirp is added to the PID output (set_roll(pid + _actuator_sysid)), and RATE.ROut logs that sum. Using SIDD as the input gives exactly the closed-loop error the module warns against. ModeSystemId::init also refuses entry for axes 1–13 unless the previous mode has manual throttle, which rules out GUIDED and ALT_HOLD.
  source: https://github.com/ArduPilot/ardupilot/blob/master/ArduCopter/mode_systemid.cpp
- severity: imprecise
  file: content/tools/ctl-sysid.md
  quote: "Пока `SID_AXIS = 0`, войти в режим нельзя."
  fix: "Пока `SID_AXIS = 0`, войти в режим нельзя; кроме того, аппарат должен быть в воздухе, а переключаться в SYSID для осей 1–13 можно только из режима с ручным газом (STABILIZE, ACRO), для осей 14–19 — только из LOITER."
  why: ModeSystemId::init() rejects entry with "Aircraft must be flying", with "Axis requires manual throttle" for axes 1–13 and with "Axis requires switch from Loiter" for axes 14–19. These are entry conditions besides SID_AXIS.
  source: https://github.com/ArduPilot/ardupilot/blob/master/ArduCopter/mode_systemid.cpp
- severity: imprecise
  file: content/tools/ctl-sysid.md
  quote: "Возможная причина: `SID_AXIS = 0`, параметры не обновлены."
  fix: "Возможная причина: `SID_AXIS = 0`, параметры не обновлены, аппарат на земле или переключение не из режима с ручным газом (для осей 14–19 — не из LOITER)."
  why: The same init() checks apply here. Switching from GUIDED or ALT_HOLD is the usual reason SITL users cannot enter SYSID.
  source: https://github.com/ArduPilot/ardupilot/blob/master/ArduCopter/mode_systemid.cpp
- severity: outdated
  file: content/tools/ctl-sysid.md
  quote: "штатного режима чирпа в Betaflight нет (анализ — по Blackbox при ручных возмущениях)"
  fix: "в Betaflight с 2025.12 есть режим `CHIRP` (опция сборки `USE_CHIRP`, параметры `chirp_*`, настройки пишутся в заголовок Blackbox); в 4.5 штатного чирпа нет (анализ — по Blackbox при ручных возмущениях)"
  why: Betaflight 2025.12 adds src/main/common/chirp.c, the CHIRP mode box (permanentId 55), CLI settings chirp_amplitude_*, chirp_frequency_*_deci_hz and chirp_time_seconds, and Blackbox header fields, all under USE_CHIRP. 4.5 has none of this.
  source: https://github.com/betaflight/betaflight/blob/2025.12-maintenance/src/main/common/chirp.c

## tools-gazebo
verified: 31
- severity: imprecise
  file: content/tools/tools-gazebo.md
  quote: "Плагин ArduPilot умеет отдавать видео с камеры по GStreamer (UDP 5600) — как настоящая камера на companion; пример мира с подвесом — `gimbal.sdf`, подвес управляется каналами RC6–RC8."
  fix: "Отдельный плагин `GstCameraPlugin` из `ardupilot_gazebo` отдаёт видео с камеры по GStreamer (H.264, UDP 5600) — как настоящая камера на companion; поток включается сообщением в топик `.../enable_streaming`. Пример мира с подвесом и камерой — `gimbal.sdf`; подвес Iris в `iris_runway.sdf` (SITL с `gazebo-iris-gimbal.parm`) управляется каналами RC6–RC8."
  why: The ardupilot_gazebo README streams video through the separate GstCameraPlugin sensor plugin, not ArduPilotPlugin, and streaming starts only after a message to the enable_streaming topic. RC6–RC8 control is documented for the Iris model's 3D gimbal in iris_runway.sdf with gazebo-iris-gimbal.parm, not for the gimbal.sdf world.
  source: https://github.com/ArduPilot/ardupilot_gazebo/blob/main/README.md

## el-kicad
verified: 29
