# stage6-iter1b

Scope: content/betaflight/bf-setup-scratch.md, content/inav/inav-setup-scratch.md, content/inav/inav-setup-wing.md, content/ardupilot/ap-setup-scratch.md, content/px4/px4-setup-scratch.md, their quiz and task banks, plus the SITL default-frame statements in content/ardupilot/ap-intro.md and ap-sitl.md.

Basis (all fetched from raw.githubusercontent.com unless noted):
- Betaflight 4.5-maintenance: sensors/voltage.c, sensors/current.c, flight/mixer_init.c, pg/gps_rescue.c, pg/motor.c, pg/rx.c, cli/settings.c, cli/cli.c, rx/crsf.c, drivers/dshot_command.{c,h}, fc/runtime_config.c, flight/failsafe.c, msp/msp.c, target/SITL/{target.h,sitl.c}; master platform/STM32/dshot_bitbang.c for how `motorOutputReordering` is used; betaflight.com GPS Rescue 4.5 page (WebFetch).
- INAV 8.0.1 and 7.1.2: fc/settings.yaml (defaults extracted with a YAML script), sensors/battery.c, fc/config.c, fc/fc_msp_box.c, fc/runtime_config.c, fc/cli.c, io/serial.h, flight/servos.c, flight/pid_autotune.c, drivers/serial_tcp.c, docs/{Settings,Battery,Failsafe}.md, docs/SITL/{SITL,X-Plane}.md; inav-configurator 8.0.1 js/model.js; INAV-X-Plane-HITL doc/setup.md.
- ArduPilot Copter-4.6.3: AP_BattMonitor_Analog.cpp, AP_MotorsMulticopter.{h,cpp}, AP_MotorsMatrix.cpp, RC_Channels_VarInfo.h, AC_PosControl.cpp, ArduCopter/Parameters.cpp, Tools/autotest/pysim/vehicleinfo.py, default_params/{copter,copter-X,copter-octaquad}.parm, libraries/SITL/SIM_Frame.cpp; master AC_PosControl.cpp, AP_BattMonitor_Analog.cpp, vehicleinfo.json, copter.parm; ardupilot_wiki copter initial-tuning-flight.rst and setting-up-for-tuning.rst; MissionPlanner master ConfigInitialParams.cs.
- PX4 v1.15.4: battery_status/analog_battery.cpp and analog_battery_params_common.c, lib/battery/{battery.cpp,module.yaml,battery_params_common.c}, commander/commander_params.c, drivers/pwm_out/module.yaml, drivers/rc_input/module.yaml, drivers/rc/crsf_rc/module.yaml, boards/px4/fmu-v6x and fmu-v6c default.px4board, ROMFS init.d-posix/rcS and airframes/10040_sihsim_quadx, simulator_sih/sih_params.c; docs.px4.io v1.15 ESC calibration page (WebFetch).

I re-ran every calibration number in the modules, banks and diagram captions by hand or in Python. The firmware SITL builds were not re-run, as instructed. I checked the pasted SITL outputs against the source for internal consistency.

Totals (report entries): 8 fixed (7 distinct errors; F8 is the task-bank half of F1), 3 left as uncertain, 25 ok. Each ok entry groups several checked values.

## Fixes

### F1. fixed: ap-setup-scratch.md and tasks/ap-setup-scratch.json, wrong parameter name `BATT_VOLT_OFFSET`
- Quote: "V = (V_pin − `BATT_VOLT_OFFSET`) × `BATT_VOLT_MULT`" (module theory). The `volt-mult` task solution used the same name.
- Why: the parameter is `BATT_VLT_OFFSET` (`AP_GROUPINFO("VLT_OFFSET", 6, ...)`), both in 4.6.3 and in master. Changed it in both places.
- Source: https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.6.3/libraries/AP_BattMonitor/AP_BattMonitor_Analog.cpp

### F2. fixed: ap-setup-scratch.md, props-off boundary on the hardware path
- Quote: "Пропы сняты до пункта 9."
- Why: the props go on in item 11 ("Пропы на место"). Item 9 is the bench failsafe test, which the module itself says to run "без пропов". With "до пункта 9", props would be on during the arming failsafe test. Changed to "до пункта 11".
- Source: internal consistency (items 9 and 11 of the same section).

### F3. fixed: ap-setup-scratch.md, 6S battery failsafe example thresholds (authors' open point)
- Quote: "`BATT_LOW_VOLT = 21.0` (3.5 В/банка под нагрузкой), `BATT_CRT_VOLT = 19.8`, … `BATT_ARM_VOLT = 23.0`"
- Why: item 11 runs Mission Planner Initial Parameter Setup. That tool always writes `BATT_ARM_VOLT = (n−1)·0.1 + (Vmin+0.3)·n`, `BATT_LOW_VOLT = (Vmin+0.3)·n` and `BATT_CRT_VOLT = (Vmin+0.2)·n`. For 6S with Vmin 3.3 that gives 22.1, 21.6 and 21.0 V, so it would silently overwrite the item 9 values. There was a second problem: `BATT_CRT_VOLT = 19.8` equals `MOT_BAT_VOLT_MIN` (3.3 V/cell), which leaves no margin before Land. Changed to 21.6 / 21.0 / 22.1 and noted that item 11 writes the same values. `MOT_BAT_VOLT_MAX/MIN` = 25.2 / 19.8 match the wiki (4.2·n, 3.3·n) and are unchanged.
- Sources: https://raw.githubusercontent.com/ArduPilot/MissionPlanner/master/GCSViews/ConfigurationView/ConfigInitialParams.cs ; https://raw.githubusercontent.com/ArduPilot/ardupilot_wiki/master/copter/source/docs/setting-up-for-tuning.rst

### F4. fixed: ap-intro.md, SITL default FRAME_TYPE
- Quote: "`FRAME_CLASS = 1` (Quad), `FRAME_TYPE = 1` (X) — так называется рама в SITL по умолчанию."
- Why: in `vehicleinfo.py`, ArduCopter has `default_frame: "quad"`, and the "quad" frame is `model "+"` with `default_params/copter.parm`, whose first line is `FRAME_TYPE 0`. Only `-f X` adds `copter-X.parm` (`FRAME_TYPE 1`). master `vehicleinfo.json` and `copter.parm` are the same. Rewritten: the SITL default is Quad Plus (`FRAME_TYPE = 0`, with no `-f` or with `-f quad`), and Quad X needs `-f X`.
- Sources: https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.6.3/Tools/autotest/pysim/vehicleinfo.py ; https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.6.3/Tools/autotest/default_params/copter.parm ; https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.6.3/Tools/autotest/default_params/copter-X.parm

### F5. fixed: ap-sitl.md, frame flag list (clarification)
- Quote: "`-f octa-quad`, `-f quad`, `-f quadplane` — модель рамы в симуляторе;"
- Why: the module never says which `FRAME_TYPE` `-f quad` gives, and readers who come to it from ap-intro expect X. Added in parentheses: `-f quad` and no `-f` give Quad Plus (`FRAME_TYPE = 0`), Quad X is `-f X`. Same sources as F4.

### F6. fixed: inav-setup-scratch.md, `throttle_idle` default across INAV 7/8 (authors' open point)
- Quote: "`throttle_idle` = 8 % (по умолчанию; для 5" обычно хватает 5–8 %)"
- Why: the module covers "INAV 7/8". settings.yaml has `throttle_idle` default 15 in 7.1.2 and 8 in 8.0.1. `motorstop_on_low` also changed, OFF in 7.1.2 and ON in 8.0.1, but the scratch module does not mention it. The wing module already states both correctly. Changed to "по умолчанию в 8.x, в 7.1 — 15 %".
- Sources: https://raw.githubusercontent.com/iNavFlight/inav/8.0.1/src/main/fc/settings.yaml ; https://raw.githubusercontent.com/iNavFlight/inav/7.1.2/src/main/fc/settings.yaml

### F7. fixed: inav-setup-wing.md, where the servo autotrim 1300–1700 µs limit applies
- Quote: "Servo autotrim двигает именно `mid`, в пределах 1300–1700 мкс (`servos.c`)."
- Why: `SERVO_AUTOTRIM_CENTER_MIN/MAX` (1300/1700) are applied only in `processContinuousServoAutotrim` (feature FW_AUTOTRIM). `processServoAutotrimMode`, the SERVO AUTOTRIM mode that the module teaches in П3, writes the 2-second average into `middle` with no constrain. Rewritten to say this.
- Source: https://raw.githubusercontent.com/iNavFlight/inav/8.0.1/src/main/flight/servos.c

### F8. fixed: tasks/ap-setup-scratch.json, same name error as F1 (the task half of F1)
- Listed separately because it is a different file. Fixed together with F1.

## Authors' open points

### O1. ok: BF GPS Rescue minimum start distance
- Quote: "`gps_rescue_min_start_dist` = 15 м" plus the note on docs 30 m vs source 15 m.
- Verdict: `pg/gps_rescue.c` (4.5-maintenance) sets `.minStartDistM = 15`, and the CLI range is 10–30. The betaflight.com 4.5 page says "The default minimum initiation distance of 30m". The module's note (trust your firmware, `get gps_rescue_min_start_dist`) is right. The other GPS Rescue defaults quoted all match pg/gps_rescue.c and the lookup tables: min_sats 8, MAX_ALT, initial climb 10, return alt 30, 750 cm/s, hover 1275, RESCUE_SANITY_FS_ONLY, arming without fix OFF. "Документация советует 10" matches "10 is preferable".
- Sources: https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/pg/gps_rescue.c ; https://betaflight.com/docs/wiki/guides/current/GPS-Rescue-v4-5

### O2. ok: INAV `current_meter_offset` unit
- Verdict: battery.c 8.0.1 computes `microvolts = ADC·3300·100/0xFFF·10 − offset·100`, then `microvolts / scale` in 0.01 A. So offset is in 0.1 mV and scale in 0.1 mV/A. Settings.md says "millivolts" for offset, which is wrong, and "0.1 mV/A" for scale, which is right. The correction new = old + (I_INAV − I_meter)·scale follows directly: Δoffset·100 µV / scale = Δoffset/scale A. Worked example: (0.69 − 0.45)·435 = 104.4, so 104.
- Source: https://raw.githubusercontent.com/iNavFlight/inav/8.0.1/src/main/sensors/battery.c

### O3. ok: INAV fixed-wing autotune scope
- Verdict: `autotuneUpdateGains()` in pid_autotune.c 8.0.1 writes only `pid[axis].FF` and `stabilized.rates[axis]`. The wing module text and quiz Q6 are correct. Saving manually after disarm (stick save) fits the code: autotune only updates RAM values every 5 s.
- Source: https://raw.githubusercontent.com/iNavFlight/inav/8.0.1/src/main/flight/pid_autotune.c

### O4. ok (wing) / fixed (scratch, F6): INAV defaults changed 7.1→8.0
- Verdict: `motorstop_on_low` False→True and `throttle_idle` 15→8, confirmed in settings.yaml. The wing module's "у 7.1.2 по умолчанию OFF и 15 %, у 8.0.1 — ON и 8 %" is correct.

### O5. ok: PX4 CRSF input
- Verdict: in rc_input/module.yaml (v1.15.4), `RC_INPUT_PROTO` has −1 Auto … 6 CRSF, 7 GHST, default −1, and the port parameter is `RC_PORT_CONFIG`. crsf_rc/module.yaml has port parameter `RC_CRSF_PRT_CFG` and `RC_CRSF_TEL_EN`. fmu-v6x default.px4board has `CONFIG_DRIVERS_RC_INPUT=y` (and MSP_OSD); fmu-v6c default.px4board has no RC_INPUT line. The module text is consistent with this.
- Sources: https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.15.4/src/drivers/rc_input/module.yaml ; https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.15.4/src/drivers/rc/crsf_rc/module.yaml ; https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.15.4/boards/px4/fmu-v6x/default.px4board

### O6. ok: PX4 SITL defaults differ from hardware
- Verdict: init.d-posix/rcS sets `COM_RC_IN_MODE 1`, `MC_AT_EN 1`, `SDLOG_MODE 1`, `SYS_FAILURE_EN 1` and `COM_LOW_BAT_ACT 2`. commander_params.c defaults are `COM_LOW_BAT_ACT 0` and `COM_RC_IN_MODE 3`. COM_LOW_BAT_ACT values 0/2/3 match the module.
- Source: https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.15.4/ROMFS/px4fmu_common/init.d-posix/rcS

### O7. ok: ArduPilot PSC_ACCZ_P/I vs MOT_THST_HOVER
- Verdict: the wiki initial-tuning-flight says `PSC_D_ACC_P` = 0.1×HOVER and `PSC_D_ACC_I` = 0.2×HOVER, with a note that in 4.6 and earlier they were `PSC_ACCZ_*`, scaled 10x larger (P = HOVER, I = 2×HOVER). master AC_PosControl.cpp: "If upgrading from 4.6 this is _ACCZ_P * 0.1". The module's "PSC_ACCZ_P = MOT_THST_HOVER, PSC_ACCZ_I = 2 × MOT_THST_HOVER (масштаб 4.6)" and "(PSC_D_ACC_P/I, значения ×0.1)" are correct.
- Sources: https://raw.githubusercontent.com/ArduPilot/ardupilot_wiki/master/copter/source/docs/initial-tuning-flight.rst ; https://raw.githubusercontent.com/ArduPilot/ardupilot/master/libraries/AC_AttitudeControl/AC_PosControl.cpp

### O8. fixed (F3): ArduPilot 6S battery failsafe example thresholds

## Calibration formula direction (all ok)

- **BF voltage, ok:** voltage.c `((ADC·vbatscale·Vref/10 + 0xFFF·5)/(0xFFF·vbatresdivval))/vbatresdivmultiplier`, defaults 110/10/1. V ∝ scale, so new = old × V_meter / V_FC. Example 110·24.42/24.04 = 111.7, rounded to 112. Error 10 mV/cell, one step 0.89 % ≈ 36 mV/cell. All correct.
- **BF current, ok:** current.c `centiAmps = (mV·10000/scale + offset)/10`, scale in mV/10 A (default 400), offset in mA, CLI range −16000…16000. I ∝ 1/scale, so new = old × mAh_FC / mAh_charger: 400·905/1032 = 350.8, rounded to 351. Offset 0 + 0.23·1000 = 230. `updateCurrentmAhDrawnState` runs whenever the meter updates, not only when armed. The ACS758 comment matches.
- **INAV voltage/current, ok:** see O2. Examples check out: 1100·16.42/15.95 = 1132.4; 400·1120/1030 = 434.95; wing 1100·16.42/16.08 = 1123.3 and 250·2860/3180 = 224.8. The Battery.md formula and its 1260/1158·400 = 435 example agree.
- **ArduPilot, ok (name fixed in F1):** `voltage = (pin − _volt_offset)·_volt_multiplier`, `current = (pin − _curr_amp_offset)·_curr_amp_per_volt`, so new mult = old·V_meter/V_GCS and new PERVLT = old·mAh_charger/mAh_FC. Offset = old + I0/PERVLT. The chart caption numbers (0.50 A, 9.59 A, 9.09 A, 44) and the SITL numbers (11·12.6/10.1 = 13.723) check out.
- **PX4, ok:** analog_battery.cpp `voltage_v = raw·v_div`, `current_a = (raw − v_offs_cur)·a_per_v`, offset param `BAT_V_OFFS_CURR` (single, not per battery). Examples: 18·16.71/16.42 = 18.318; 36·2465/2310 = 38.416. SoC in battery.cpp: `+ r_internal·I` when current > 0, otherwise `+ throttle·v_load_drop`, then interpolate between V_EMPTY 3.6 and V_CHARGED 4.05 (module.yaml defaults). V_LOAD_DROP 0.1, R_INTERNAL 0.005. Thresholds 0.15 / 0.07 / 0.05 come from battery_params_common.c. The 0.109 example is correct.

## Motor order, numbering and direction procedures (all ok)

- **BF, ok:** mixerQuadX order is REAR_R, FRONT_R, REAR_L, FRONT_L, and props-in directions are 1 CW, 2 CCW, 3 CCW, 4 CW. `motor_output_reordering` default is identity (pg/motor.c), and the driver uses `ioTags[motorOutputReordering[i]]`, so the "1,0,2,3,…" example and quiz Q5 are right. DShot commands are 7/8/12, sent 10 times. `dshotprog` index: `parseOutputIndex(..., allowAll)` takes 255 for all motors. CRSF 172→988 and 1811→2012 match crsf.c.
- **INAV, ok:** the mmix Quad X rows match configurator model.js and the BF matrix. Serial function bits match io/serial.h (MSP 1, GPS 2, RX_SERIAL 64, BLACKBOX 128, MSP_OSD 1<<25). Mode permanent IDs (0, 1, 3, 10, 11, 27, plus NAV LAUNCH 36, SERVO AUTOTRIM 37) match fc_msp_box.c. SERVO AUTOTRIM is hidden when FW_AUTOTRIM is set, as stated. The wing preset smix rules (servo 1: +50 roll, +50 pitch; servo 2: −50 roll, +50 pitch) and the Airplane preset match model.js. The servo test table directions are correct.
- **ArduPilot, ok:** Quad X 1 FR CCW, 2 BL CCW, 3 FL CW, 4 BR CW. Motor Test letters A, B, C, D map to outputs 1, 4, 2, 3. Motor test percent maps to `pwm_min + (max−min)·%`, giving 1100. Spin-arm idle is 1000 + 0.10·1000. Defaults: SPIN_ARM 0.10, SPIN_MIN 0.15, SPIN_MAX 0.95, THST_HOVER 0.35 with range 0.125–0.6875, THST_EXPO 0.65. The hover check (r = 0.523, PWM ≈ 1569) and the task's example (1547) recompute correctly.
- **PX4, ok:** the 10040_sihsim_quadx CA_ROTOR PX/PY/KM values and `PWM_MAIN_FUNC1–4 = 101–104` match the table. The PWM_MAIN_TIM enum −5…−1 and 50…400 matches pwm_out/module.yaml. The hardware motor defaults 1100/1900/1000 match docs.px4.io v1.15 ESC calibration. The SITL disarmed value of 900 comes from the simulator output, not the pwm_out defaults (1000/1000/2000). `dshot reverse/save -m N` is correct.

## Other parameters, defaults and CLI (ok unless noted)

- **BF, ok:** min_check 1050, max_check 1900 (pg/rx.c); min_throttle 1070, max_throttle 2000, min_command 1000, dshot_idle_value 550 (pg/motor.c); failsafe_delay 15, switch mode STAGE1 by default, procedure DROP (failsafe.c); lookup names AUTO-LAND/DROP/GPS-RESCUE and STAGE1/KILL/STAGE2; SITL ports 9001/9002/9003/9004 and `rxRCFrameStatus` always returning RX_FRAME_COMPLETE (sitl.c); SITL disables ADC, OSD, serial RX, VTX and resource management (target.h); arming flag names (runtime_config.c).
- **BF SITL output, ok:** 0.07 = (1070 − 1000)/1000, and 0.412 = 0.07 + 0.93·(1400 − 1050)/950. Both reproduce exactly.
- **INAV defaults, ok (8.0.1 = 7.1.2 except O4):** failsafe_delay 5, rx_min/max_usec 885/2115, failsafe_procedure LAND, throttle_low_delay 0, min_distance_procedure DROP, stick_threshold 50, nav_emerg_landing_speed 500, min/max_check 1100/1900, gps_min_sats 6, mag_calibration_time 30, gyro_main_lpf_hz 60, dynamic notch ON, nav_mc_hover_thr 1300, nav_min_rth_distance 500 cm, nav_rth_altitude 1000, AT_LEAST/ON/ALWAYS, motor_pwm_protocol ONESHOT125, nav_fw_loiter_radius 7500, fw_loiter_direction RIGHT, nav_fw_bank_angle 35, failsafe_fw_roll/pitch/yaw −200/100/−45 (decidegrees; negative roll = left, positive pitch = dive per Settings.md), nav_fw_launch_* defaults 1700/500/18/5000/0/45, `nav_fw_launch_max_altitude` in cm, servo rate −125…125 and smix weight −1000…1000 (cli.c), fw_level_pitch_trim in degrees with + = nose up.
- **INAV SITL output, ok:** "[SOCKET] Bind TCP %s to UART%d" and "Unable to bind socket" strings exist in serial_tcp.c 8.0.1. `config.c` swaps DSHOT for MULTISHOT under `#if !defined(USE_DSHOT)`. INAV arming flag short names (CAL, NAV, ACC, RX, CLI, THR) exist in runtime_config.c. The MSP_RC TAER example is consistent.
- **INAV, ok:** "RTH requires GPS, compass, baro; else emergency landing" is supported by Failsafe.md (lines on RTH requirements and "if any required sensor is reported as unavailable").
- **INAV wing geometry, ok:** MAC 229.5 mm at y = 275.6 mm, MAC LE 92 mm, CG 126/133/138 mm. Elevon h = c·sin δ gives 8.4/12.5/15.5 mm. Bank angles 17.0°/37.4°/20.9° are right.
- **ArduPilot, ok:** RC_OPTIONS default 32 and bits 9/13 (8736), RC_PROTOCOLS bit 9 = CRSF (512), RC_FS_TIMEOUT 1.0 s, RC_OVERRIDE_TIME 3 s (RC_Channels_VarInfo.h). FLTMODE PWM bounds, RCx_OPTION 153/31/17/300, OSD_TYPE 1/5, SERIAL protocols 2/5/16/23/42, FRAME_TYPE 12 BetaFlightX (Parameters.cpp values). SITL `MOT_BAT_VOLT_MAX 12.8`, `BATT_MONITOR 4` (copter.parm). ERR subsystems 5/6 (FAILSAFE_RADIO/BATT) and mode reasons 3/4 are correct.
- **PX4, ok:** COM_RC_LOSS_T 0.5, COM_FAIL_ACT_T 5, COM_DISARM_LAND 2, COM_DISARM_PRFLT 10, COM_ARM_SWISBTN 0 (commander_params.c). SIH_MASS 1.0 and SIH_T_MAX 5.0 give 20/9.81 → 0.4905.

## Quizzes and task banks (all ok)

All 32 quiz answers were checked against the module and the source, and each has exactly one defensible correct option. Task formulas match the modules, and the parameter ranges give sensible answers: BF vbat scale stays within 0.93–1.09 of the old value; INAV and PX4 offsets may come out negative, which the solutions explain; the hover tasks stay in τ 0.125–0.75; the AP hover PWM example recomputes to 1547; the PX4 soc task is clamped to 0…1. Apart from F8, I found no errors in the banks.

## Left: uncertain / outside scope

### U1. left: uncertain, ap-heavy.md / ap-lua.md, octa-quad SITL frame type
- Quote: ap-heavy "В ArduPilot это `FRAME_CLASS = 4` (OctaQuad) и `FRAME_TYPE = 1` (X)", and "Рама `octa-quad` в SITL — та же OctaQuad".
- Why: `-f octa-quad` loads copter.parm (`FRAME_TYPE 0`) plus copter-octaquad.parm (`FRAME_CLASS 4` only). So SITL runs the OctaQuad **Plus** mixer (motors at 0/−90/180/90 in AP_MotorsMatrix), while SIM_Frame `octa_quad_motors` places the motors at ±45/±135 (X). Not in the requested scope and not verified in flight, so left as is. Suggestion: tell students to set `FRAME_TYPE = 1` after the first `-w` run, or check what `param show FRAME_TYPE` returns.
- Sources: https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.6.3/Tools/autotest/default_params/copter-octaquad.parm ; https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.6.3/libraries/SITL/SIM_Frame.cpp ; https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.6.3/libraries/AP_Motors/AP_MotorsMatrix.cpp

### U2. left: uncertain, ap-tuning.md uses `sim_vehicle.py -v ArduCopter -f quad`
- Why: this is a Plus frame (see F4). AUTOTUNE works on Plus, so the exercise is still valid, but it does not match the course's Quad X examples. Left unchanged and reported.

### U3. left: uncertain, inav-setup-scratch.md, X-Plane for multirotors
- Quote: "Для квадрокоптера реально подходит только RealFlight …: плагин INAV-X-Plane-HITL поддерживает только платформу Airplane."
- Why: the plugin statement is correct ("Platforms other than "Airplane" are not supported"). SITL's native X-Plane interface (`--sim=xp`) is separate from the plugin, and the INAV docs do not say outright that multirotors are unsupported there. The conclusion is practically right, but the reasoning mixes the two paths. Left unchanged.
- Source: https://raw.githubusercontent.com/RomanLut/INAV-X-Plane-HITL/main/doc/setup.md

## Validation

`python3 scripts/validate_content.py`: OK (126 articles, 126 quizzes). `python3 scripts/diagrams/build_diagrams.py`: 159 diagrams per locale, no errors. No diagram data depended on the edited values. The s6_ap_setup_scratch "props off before step 15" note stays correct, because hardware item 11 corresponds to course step 15.
