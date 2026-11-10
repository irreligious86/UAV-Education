# stage6-iter1

Scope: content/design/{des-sizing, des-thrust-stand, aero-stability, ctl-allocation}.md and their quiz/task banks.

Basis: ArduPilot Copter-4.6.3 (Parameters.cpp, config.h, crash_check.cpp, Log.cpp, AP_Motors/AP_MotorsMulticopter.{h,cpp}, AP_MotorsMatrix.cpp, AP_Scripting/examples/MotorMatrix_fault_tolerant_hex.lua), ArduPilot master (AC_AttitudeControl.cpp, ArduPlane/Parameters.cpp, ArduPlane/Log.cpp, SRV_Channels.cpp, SITL/SIM_Plane.h), Plane-4.5.7 Parameters.cpp, ardupilot_wiki plane/source/docs/guide-center-of-gravity.rst. PX4 v1.15.0, v1.16.0, v1.17.0 and main: control_allocator/module.yaml, ActuatorEffectivenessRotors.cpp, ControlAllocationPseudoInverse.cpp, ControlAllocationSequentialDesaturation.{cpp,hpp}, ControlAllocator.cpp, failure_detector_params.c, FailureInjector.cpp, commander_params.c, mixer_module/params.c, FunctionMotors.hpp, airframes 10044_sihsim_hex and 4001_gz_x500, docs/en (actuators.md, failure_injection.md, sim_sih/index.md). Betaflight 4.5-maintenance: flight/mixer.c, flight/mixer_init.c, flight/pid.h, cli/settings.c; betaflight.com repo docs/wiki/guides/current/Mixer.md. INAV master and 7.0.0: fc/settings.yaml, fc/cli.c. Vendor pages through WebFetch: T-Motor MN4014 KV330 and MN4006 KV380 product pages, Molicel P45B datasheet v1.2, TAL220F datasheet, Skywalker 1830 manual (manuals.online), NASA GRC induced-drag page, MIT 16.333 lecture 2 PDF, Simões coaxial extended abstract.

Every Python block was rerun (Python 3, numpy 2.5.3, scipy 1.18.1). The pasted outputs match byte for byte: sizing.py, gen_stand_data.py plus `wc -l`, process_stand.py, the FM block, aero_stability.py, and alloc.py with demo.py, all four ctl-allocation outputs. The ESP32 host-test output (stubs) could not be rerun because the stubs are not in the module. I checked it for internal consistency instead: ramp 2 %/100 ms gives 10/18/26/34 % at 500/900/1300/1700 ms, the timeout is 500 ms, and the trip is at 16 A.

Counts: 6 fixed, 7 left: uncertain or note, 40 ok entries (several entries group related checks).

## des-sizing

- verdict: fixed
  file: content/design/des-sizing.md
  quote: "(в даташите 242 Вт·ч/кг — по типичной, а не максимальной массе)"
  why: Datasheet v1.2 lists only the maximum weight, 70 g, plus 242 Wh/kg. Its typical mass is not stated. 242 Wh/kg implies about 67 g, so the explanation is an inference. The text now says so.
  source: https://www.imrbatteries.com/content/molicel_p45b.pdf
- verdict: ok
  file: content/design/des-sizing.md
  quote: "MN4014 KV330 (22.2 В): проп 15×5, 75 % газа — 1430 г при 173.2 Вт" / script table MN4014 / "мотор 171 г с проводами" / "длительный 25 А (180 с)" / "6000 об/мин с 15×5 ... 5400 с 17×5.8"
  why: All five rows per prop, the weight with cables, the 25 A 180 s rating and the RPMs match the T-Motor page (report MN.00026). The script's `[:3]` takes the 50/65/75 % rows, which matches its comment.
  source: https://store.tmotor.com/product/mn4014-kv330-motor-navigator-type.html
- verdict: ok
  file: content/design/des-sizing.md
  quote: "4500 мА·ч, 3.6 В, 16.2 Вт·ч, масса 70 г (max) → 231 Вт·ч/кг"; "210 × 0.85 × 0.8 ≈ 143"
  why: Matches the datasheet, and the arithmetic is right: 231 → 210 → 142.8.
  source: https://www.imrbatteries.com/content/molicel_p45b.pdf
- verdict: ok
  file: content/design/des-sizing.md
  quote: theory numbers (A = 0.1140 м², P_ideal 99.4 Вт, FM 0.574; ranges 0.55–0.59 / 0.53–0.60; DL 92/72 Н/м², 9.3/10.7 г/Вт, 13 %, 3.7 мин; 0.82/0.74 KV ratio; 122 м/с, M 0.36; 4.8 А hover per motor; (20.4/22.2)² = 0.84; (1/1.28)^(2/3) = 0.85; t ∝ f/√m)
  why: Every value was recomputed independently and agrees.
  source: recomputation
- verdict: ok
  file: content/design/des-sizing.md
  quote: "κ_int ≈ 1.28 при равных тягах (нижний проп в дальнем следе верхнего)"
  why: The paper states κ_int = 1.281 for the far-wake, equal-thrust case.
  source: https://fenix.tecnico.ulisboa.pt/downloadFile/566729524644716/CedricSimoes_ExtendedAbstract.pdf
- verdict: ok
  file: content/design/des-sizing.md
  quote: "`ANGLE_MAX` в Copter 4.6 (сантиградусы, по умолчанию 3000), в ветке master — `ATC_ANGLE_MAX` в градусах (30)"
  why: In Copter-4.6.3 the units are cdeg and DEFAULT_ANGLE_MAX is 3000. In master, Copter no longer has ANGLE_MAX. AC_AttitudeControl has ANGLE_MAX (deg) with AC_ATTITUDE_CONTROL_ANGLE_MAX_DEFAULT 30.0, so the full name is ATC_ANGLE_MAX. Resolves the authors' open point.
  source: https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.6.3/ArduCopter/Parameters.cpp ; https://raw.githubusercontent.com/ArduPilot/ardupilot/master/libraries/AC_AttitudeControl/AC_AttitudeControl.cpp
- verdict: ok
  file: content/design/des-sizing.md
  quote: "`MOT_HOVER_LEARN` = 2 по умолчанию ... «тяга висения от 0 до 1»"; `CTUN.ThO`
  why: The default is HOVER_LEARN_AND_SAVE (2), and the THST_HOVER description is "Motor thrust needed to hover expressed as a number from 0 to 1". CTUN has ThO and ThH.
  source: https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.6.3/libraries/AP_Motors/AP_MotorsMulticopter.cpp ; .../ArduCopter/Log.cpp
- verdict: ok
  file: content/design/des-sizing.md
  quote: «Переход на реальное железо» steps 1–5 and the acceptance criteria
  why: Weighing and current calibration are done with props off. Props go on only for the hover, outdoors, with people 30 m away and failsafe checked. All criteria are numeric: ±10 % mass, ±15 % power, MOT_THST_HOVER ≤ 0.5.
  source: module text
- verdict: ok
  file: content/quiz/des-sizing.json, content/tasks/des-sizing.json
  quote: all 8 questions; 4 tasks
  why: Each keyed answer is correct and the only defensible option (Q4: 464 → 403 W = −13 %). The task formulas match the module. Over the parameter extremes all answers are finite and positive: P 48–1973 W, t 12–71 min, m 1.7–8 kg, tilt 0.5–21°. At the edge (8 kg on 4 × 10″) the disc loading is about 390 N/m², which is unrealistic. That is plausibility only, and I left it.
  source: recomputation

## des-thrust-stand

- verdict: fixed
  file: content/tasks/des-thrust-stand.json
  quote: stand-fm params `"t": 900–1100 step 50, "p": 80–100`
  why: The independent random parameters gave FM 0.47–0.85, against the task's own solution text "Хорошие пропы для коптеров дают 0.6–0.75". FM 0.85 is not plausible for a 15–16″ prop. The new ranges, t 950–1050 step 25 and p 85–100, give 0.51–0.74 with 40 combinations, which is more than the 8 variants needed.
  source: recomputation; MN4006 table (shaft power about 93 W at 1093 g)
- verdict: ok
  file: content/design/des-thrust-stand.md
  quote: TABLE / DS (MN4006 KV380, 15×5 CF, 24 V), torques 0.15/0.29/0.40 Н·м, "У MN4006 24 полюса, значит делитель 12", "паспортный пик — 16 А на 180 с"
  why: All seven rows match the T-Motor page (current, power, RPM, torque, thrust). The configuration is 18N24P, so there are 24 poles and the eRPM divider is 12. Peak current is 16 A for 180 s. Quiz Q7 (74 000/12 ≈ 6167) is therefore correct.
  source: https://store.tmotor.com/product/mn4006-kv380-motor-antigravity-type.html
- verdict: left: uncertain (note)
  file: content/design/des-thrust-stand.md
  quote: "У типовой дешёвой балки (серия TAL220) S = 1.0 ± 0.15 мВ/В, нелинейность и гистерезис ±0.05 % FS, ползучесть ±0.1 % FS за 30 мин, температурный уход нуля ±0.2 % FS на 10 °C. Для балки на 5 кг ..."
  why: The values match the cited TAL220F datasheet: 1.0 ± 0.15 mV/V for 1–3 kg, NL and hysteresis ±0.05 % FS, creep ±0.1 % FS over 30 min, zero TC ±0.20 % FS per 10 °C. But TAL220F only goes up to 3 kg, so the 5 kg beam in the module is not a TAL220F (it would be TAL220/TAL220B, whose datasheet I did not open). The %FS scaling to ±2.5/±5/±10 g is arithmetically right. Consider citing the 5 kg variant's datasheet.
  source: https://cdn.shopify.com/s/files/1/0761/6561/1847/files/TAL220F.pdf
- verdict: ok
  file: content/design/des-thrust-stand.md
  quote: "FM = C_T^1.5 / (√(π/2)·C_P) ... C_T^1.5 / (√2·C_P) ... на 11 % ниже правды"
  why: Derived from scratch. P_id = T^1.5/√(2ρA) with A = πD²/4, T = C_T ρ n² D⁴ and P = C_P ρ n³ D⁵ gives FM = C_T^1.5/(√(π/2)·C_P). The helicopter form (Ω·R normalisation) is C_T^1.5/(√2·C_P), and with propeller coefficients the ratio is √π/2 = 0.886, i.e. 11 % low. Resolves the authors' open point.
  source: derivation; Brandt & Selig coefficient definitions
- verdict: ok
  file: content/design/des-thrust-stand.md
  quote: HX711 "±0.5·AVDD/128 (±20 мВ при 5 В)", "10 или 80 отсчётов/с", "800000h / 7FFFFFh", "2 147 484 отсчёта", "≈ 430 отсчётов/г", "25-й выбирает канал A×128", "дольше 60 мкс ... power-down"
  why: These match the HX711 datasheet values, and the count arithmetic is verified. The sparkfun URL could not be opened through the proxy; values were checked from the known datasheet.
  source: https://cdn.sparkfun.com/datasheets/Sensors/ForceFlex/hx711_english.pdf
- verdict: ok
  file: content/design/des-thrust-stand.md
  quote: INA226 "±81.92 мВ, LSB 2.5 мкВ", "36 В, LSB 1.25 мВ", "CAL = 0.00512 / (Current_LSB·R_шунт)", "CAL = 2048 и полная шкала 40.96 А", "0x4527" = AVG 16, 1.1 ms/1.1 ms, continuous
  why: These match the TI INA226 datasheet (register 00h bit fields decoded). The ti.com URL could not be opened through the proxy.
  source: https://www.ti.com/lit/ds/symlink/ina226.pdf
- verdict: ok
  file: content/design/des-thrust-stand.md
  quote: ρ = 1.204 at 20 °C and 101.325 kPa; −5 % at 35 °C; C_T 0.0798/0.0813 from the datasheet; application 3.6 A, 86 W, 10.2 → 9.4 g/W, −8 %; 123 m/s tip speed; "80 → 16"; "×6–7 неопределённости"
  why: All recomputed and correct.
  source: recomputation
- verdict: ok
  file: content/design/des-thrust-stand.md
  quote: ESP32 code (LEDC 2.x/3.x API, critical-section HX711 read, sign extension, 100 ms safety tick, arm only at thrOut == 0)
  why: `ledcAttach(pin,freq,res)` and `ledcWrite(pin,duty)` are the 3.x API. `ledcSetup` and `ledcAttachPin` are the 2.x API. The duty count is right for 50 Hz at 16 bit. The safety logic does not depend on HX711 readiness.
  source: https://docs.espressif.com/projects/arduino-esp32/en/latest/api/ledc.html (not reachable from sandbox; API names from the arduino-esp32 3.x migration)
- verdict: left: uncertain (note)
  file: content/design/des-thrust-stand.md
  quote: "4. Аварийные пути, пропа нет. Выдерни USB — газ должен уйти в 0 за 0.5 с."
  why: The test is safe because props are off. But if the ESP32 is powered from that same USB cable, pulling it tests the ESC's signal-loss behaviour, not the firmware CMD_TIMEOUT. A cleaner test of the timeout is to stop the PC script, or to power the ESP32 separately. I did not edit this because it is not a factual error.
  source: module code
- verdict: ok
  file: content/design/des-thrust-stand.md
  quote: «Переход на реальное железо» steps 1–6, criteria
  why: Steps 1–4 are explicitly done with no prop, and the prop is fitted only at step 5, with ring or guard, glasses, kill switch and a 10 s top step. All criteria are numeric.
  source: module text
- verdict: ok
  file: content/quiz/des-thrust-stand.json
  quote: all 8 questions
  why: Each keyed answer is correct and unique. Q4: (421 646 − 84 254)/432 = 781 g; the 976 g distractor is the result without subtracting zero. Q6: ≈ 430 counts/g.
  source: recomputation
- verdict: left: uncertain (note)
  file: content/tasks/des-thrust-stand.json
  quote: stand-ct "Для 15×5 T-Motor получается около 0.08"
  why: The independent t and rpm ranges give C_T 0.059–0.087. The sentence is still true on average, but the variants do not all represent a real prop. Optional: narrow the rpm range. Left.
  source: recomputation

## aero-stability

- verdict: fixed
  file: content/design/aero-stability.md
  quote: diagram caption chart-stability-polar "12 м/с стоят всего на 3 % больше энергии на километр"
  why: (L/D)max 11.32 against L/D(12 m/s) 11.07 gives +2.3 % energy per km. Changed to 2.3 %.
  source: recomputation with the module's polar
- verdict: fixed
  file: content/design/aero-stability.md
  quote: "`AIRSPEED_CRUISE` — 12–13 м/с: качество там 11.1, энергия на километр всего на 3 % выше оптимума."
  why: L/D is 11.1 only at 12 m/s (+2.3 %). At 13 m/s it is 10.6, which costs 7 % more energy. The sentence now gives both ends.
  source: recomputation
- verdict: fixed
  file: content/design/aero-stability.md
  quote: diagram caption chart-stability-margin "диапазон из инструкции (90–100 мм) даёт 5–15 % только при V_h 0.5–0.7"
  why: At V_h 0.5 the rear CG gives 2.2 %, and at 0.7 the front CG gives 15.4 %. The whole 90–100 mm range stays within 5–15 % only for V_h ≈ 0.56–0.69.
  source: recomputation with np_with_tail()
- verdict: ok
  file: content/design/aero-stability.md
  quote: Skywalker 1830 "размах 1830 мм, площадь крыла 41.06 дм², полётная масса 2500–3000 г, ЦТ в 90–100 мм за передней кромкой"; "Размеры ГО производитель не даёт"
  why: Matches the cited manual, including the absence of tail dimensions. Note that the same manual's Features section says 1820 mm. This source is secondary (manuals.online), as the authors flagged.
  source: https://manuals.online/fpv/toy/2015-new-skywalker-1830/user-manual/26dqz
- verdict: left: uncertain (note)
  file: content/design/aero-stability.md
  quote: "h_n = h_ac + η·V_h·(a_t/a_w)·(1 − dε/dα)" (Etkin, MIT 16.333)
  why: This is the standard textbook approximation (Nelson's form uses C_Lα,w). MIT 16.333 lecture 2 uses the fuller form h_NP = (a_w·h_ac + η(S_t/S)a_t(1−ε_α)h_t)/(a_w + η(S_t/S)a_t(1−ε_α)) with V_H measured from the CG. For the Skywalker example at V_h 0.6 (S_t/S ≈ 0.17), the fuller form puts NP about 7 % less far aft: ≈ 111 mm instead of 115 mm. The module already calls the formula optimistic and tells the reader to start at the front CG. I checked the other formulas line by line and they are correct: Helmbold slope, downwash 2a/(πAR), trapezoid MAC, y_MAC, x_LE, the dCm/dCL = −SM link, the polar optima and V_mp = V_md/3^¼. The citation "Etkin" could arguably be "Nelson".
  source: https://ocw.mit.edu/courses/16-333-aircraft-stability-and-control-fall-2004/99dac83da0ad7eb8906ebac40e9e6ae1_lecture_2.pdf
- verdict: ok
  file: content/design/aero-stability.md
  quote: "прямоугольное крыло — около 0.7 по NASA"
  why: The NASA page says "For a rectangular wing, the efficiency factor is equal to .7."
  source: https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/induced-drag-coefficient/
- verdict: ok
  file: content/design/aero-stability.md
  quote: worked numbers (AR 8.16, MAC 224 mm, 40–45 % MAC, NP 51 %, 0.45 %/mm; wing MAC 245/229/107, NP 168, CG 149 = 17 % MAC = 50 % root, 74 mm, 38 %; V_s 9.4, V_md 10.8 = 1.15 V_s, 86 W at 15 m/s vs 50 W, battery shift 50 mm, C_D0 0.044)
  why: All recomputed and correct.
  source: recomputation
- verdict: ok
  file: content/design/aero-stability.md
  quote: "`PIDP.I` ... Стабильно больше нуля — ... руля вверх (тяжёлый нос или неверный триммер руля высоты)"
  why: The wiki says the same, nearly verbatim. Quiz Q7 follows it.
  source: https://raw.githubusercontent.com/ArduPilot/ardupilot_wiki/master/plane/source/docs/guide-center-of-gravity.rst (ardupilot.org itself blocked by proxy)
- verdict: ok
  file: content/design/aero-stability.md
  quote: "`SERVO_AUTO_TRIM = 1` ... не более чем на 20 % от центра", "`PTCH_TRIM_DEG`", "`STAB_PITCH_DOWN` (по умолчанию 2°)" below TRIM_THROTTLE in FBWA; CTUN.Pitch/NavPitch/As
  why: SRV_Channels says "won't go more than 20% away from a centered trim". PTCH_TRIM_DEG is present in Plane-4.5.7 and master. STAB_PITCH_DOWN defaults to 2.0 deg and applies in FBWA and AUTOTUNE below TRIM_THROTTLE. Plane CTUN fields include NavPitch, Pitch and As.
  source: https://raw.githubusercontent.com/ArduPilot/ardupilot/master/libraries/SRV_Channel/SRV_Channels.cpp ; .../ArduPlane/Parameters.cpp ; .../ArduPlane/Log.cpp
- verdict: ok
  file: content/design/aero-stability.md
  quote: INAV `fw_level_pitch_trim` (degrees), `feature FW_AUTOTRIM`
  why: Both are present in INAV 7.0.0 and master. The description is "Pitch trim for self-leveling flight modes. In degrees".
  source: https://raw.githubusercontent.com/iNavFlight/inav/master/src/main/fc/settings.yaml ; .../fc/cli.c
- verdict: ok
  file: content/design/aero-stability.md
  quote: notes "SIM_Plane.h ... Cmα = −0.7 при C_Lα = 6.9 ... «честное» смещение ЦТ делало модель хвостотяжёлой"
  why: Source: c_lift_a 6.9, c_m_a −0.7, and the comment "the X CoG offset should be -0.02, but that makes the plane too tail heavy ... Adjusted to -0.15".
  source: https://raw.githubusercontent.com/ArduPilot/ardupilot/master/libraries/SITL/SIM_Plane.h
- verdict: ok
  file: content/design/aero-stability.md
  quote: «Переход на реальное железо»
  why: The propeller stays off for balancing and the control-surface check, and is fitted only at the field. The criteria are numeric (±3 mm, ±25 % L/D).
  source: module text
- verdict: ok
  file: content/quiz/aero-stability.json, content/tasks/aero-stability.json
  quote: 8 questions; 4 tasks
  why: Every answer is correct and unique. The task formulas match the module. Over the extremes: MAC 134–360 mm, wing CG 60–287 mm, battery shift 6–103 mm, C_D0 0.017–0.075 (always positive).
  source: recomputation

## ctl-allocation

- verdict: fixed
  file: content/design/ctl-allocation.md
  quote: "Геометрия и нумерация взяты из `10044_sihsim_hex` (плечо 1, CT = 1)."
  why: The airframe sets positions at radius 1 m, angles 30/90/150/−150/−90/−30, and KM −0.05 on rotors 1, 3 and 5, which is the PNPNPN pattern used. It does not set CT, so CT stays at the default 6.5. CT = 1 is the script's normalisation, and the text now says so.
  source: https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.17.0/ROMFS/px4fmu_common/init.d-posix/airframes/10044_sihsim_hex
- verdict: ok
  file: content/design/ctl-allocation.md
  quote: "Fᵢ = CT·aᵢ", "Mᵢ = CT·(pᵢ × aᵢ) − CT·KM·aᵢ ... (одинаково в 1.15, 1.16 и 1.17)", "`CT` = 6.5, `KM` = 0.05", "положительное у CCW"
  why: The line `moment = ct * position.cross(axis) - ct * km * axis` is identical in v1.15.0, v1.16.0 and v1.17.0 (the file moved path between versions). module.yaml gives defaults 6.5 and 0.05 and says "Use a positive value for a rotor with CCW rotation".
  source: https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.17.0/src/modules/control_allocator/VehicleActuatorEffectiveness/ActuatorEffectivenessRotors.cpp ; .../module.yaml
- verdict: ok
  file: content/design/ctl-allocation.md
  quote: alloc.py port of normalisation and sequential desaturation; "CA_METHOD = 1 или 2 = Auto", MC_AIRMODE 0/1/2 behaviour, `MINIMUM_YAW_MARGIN` 15 %
  why: The port matches updateControlAllocationMatrixScale (1e-3 count, max(roll, pitch), yaw max, thrust mean with fallback to z), normalizeControlAllocationMatrix (zero below 1e-3), and desaturateActuators/computeDesaturationGain (0.2 threshold, second half-step). The mixAirmodeDisabled/RP/RPY and mixYaw order also matches. CA_METHOD values are 0 clipping, 1 sequential desaturation, 2 automatic (default).
  source: https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.17.0/src/lib/control_allocation/control_allocation/ControlAllocationSequentialDesaturation.cpp ; .../ControlAllocationPseudoInverse.cpp
- verdict: left: uncertain (note)
  file: content/design/ctl-allocation.md
  quote: "(`MINIMUM_YAW_MARGIN`)" with firmware range "PX4 1.15–1.17"
  why: The named constant exists in v1.16.0 and v1.17.0. In v1.15.0 the same 0.15 is a literal in mixYaw(). The behaviour is identical across the three versions; only the name is missing in 1.15. Left as is.
  source: https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.15.0/src/modules/control_allocator/ControlAllocation/ControlAllocationSequentialDesaturation.cpp
- verdict: ok
  file: content/design/ctl-allocation.md, content/quiz/ctl-allocation.json
  quote: "описание параметра просит выключать airmode на время тюнинга"; "airmode по рысканию требует тумблер арма"
  why: The MC_AIRMODE description says "This function should be disabled during tuning ..." and "Enabling air-mode for yaw requires the use of an arming switch."
  source: https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.15.0/src/lib/mixer_module/params.c
- verdict: ok
  file: content/design/ctl-allocation.md
  quote: "`CA_FAILURE_MODE` = 1 ... (в 1.15–1.17 это единственный режим, кроме 0 = Ignore)"; "`FD_ACT_EN`, `FD_ACT_MOT_THR` = 0.2, `FD_ACT_MOT_C2T` = 2.0 А/%, `FD_ACT_MOT_TOUT` = 100 мс"; `COM_ACT_FAIL_ACT`; "В ветке main ... 1 и 2 вдобавок останавливают или реверсируют противоположный мотор гексы"
  why: v1.15.0, v1.16.0 and v1.17.0 module.yaml all have only 0 Ignore and 1 "Remove first failed motor from effectiveness". main has 1 "Remove failed motor and stop its opposite" and 2 "... reverse its opposite". failure_detector_params.c is identical in 1.15 to 1.17: FD_ACT_EN 1, FD_ACT_MOT_THR 0.2 norm, FD_ACT_MOT_C2T 2.0 A/%, FD_ACT_MOT_TOUT 100 ms. COM_ACT_FAIL_ACT has values 0 to 4. Resolves the authors' open point.
  source: https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.17.0/src/modules/control_allocator/module.yaml ; .../main/src/modules/control_allocator/module.yaml ; .../v1.17.0/src/modules/commander/failure_detector/failure_detector_params.c
- verdict: ok
  file: content/design/ctl-allocation.md
  quote: "инъекция только останавливает мотор (`motor_stop_mask`, в консоли «Stopping motors»). Из матрицы его убирает детектор ... «Removing motor from allocation»"; `make px4_sitl sihsim_hex`; `failure motor off -i 1`
  why: The v1.17.0 FailureInjector sets _motor_stop_mask on "off". ControlAllocator.cpp has PX4_WARN "Stopping motors (%d)" and "Removing motor from allocation (0x%x)". The v1.17.0 SIH docs give `make px4_sitl sihsim_hex`; main renamed the target to `px4_sitl_sih sihsim_hex`.
  source: https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.17.0/src/modules/commander/failure_detector/FailureInjector.cpp ; .../src/modules/control_allocator/ControlAllocator.cpp ; .../docs/en/sim_sih/index.md
- verdict: ok
  file: content/design/ctl-allocation.md
  quote: PX4 docs quotes «The X, Y, Z positions are in FRD coordinate frame, relative to the centre of gravity», «Remove the propellers from motors before assigning outputs or any testing»
  why: Both quotes are present in docs/en/config/actuators.md; the first has link markup in the source.
  source: https://raw.githubusercontent.com/PX4/PX4-Autopilot/main/docs/en/config/actuators.md
- verdict: ok
  file: content/design/ctl-allocation.md
  quote: PPNNPN = [-1,-1,1,-1,1,1] at angles [30,90,150,-150,-90,-30] ("пример `MotorMatrix_fault_tolerant_hex.lua`")
  why: Mapping the Lua example motor by motor (90 CW, −90 CCW, −30 CCW, 150 CCW, 30 CW, −150 CW, with ArduPilot angles in the same sense as PX4 FRD) gives exactly the module's sign vector. The margins table reproduces. Resolves the authors' open point.
  source: https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.6.3/libraries/AP_Scripting/examples/MotorMatrix_fault_tolerant_hex.lua
- verdict: ok
  file: content/design/ctl-allocation.md
  quote: Betaflight table row "положительный (`mixerQuadX`)", "−1 (документация: 1 = CCW)"; mmix block; "порядок моторов как у QUADX: 0 — RR, 1 — FR, 2 — RL, 3 — FL"
  why: In mixerQuadX, REAR_R is {1, −1, +1, −1}, so pitch is +1 for the rear motor, while PX4 and ArduPilot use a negative factor for the rear. BF docs say "YAW: 1.0 = CCW, -1.0 = CW". The mmix rows match the PX4 matrix with pitch negated and roll/pitch scaled to ±1, and their signs reproduce the built-in QuadX pattern (front pitch −, right roll −, CCW yaw +). Resolves the authors' open point at the level of coefficient signs; the BF internal axis convention (yaw PID negated in mixer.c unless yaw_motors_reversed) is consistent with this.
  source: https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/mixer_init.c ; https://raw.githubusercontent.com/betaflight/betaflight.com/master/docs/wiki/guides/current/Mixer.md
- verdict: ok
  file: content/design/ctl-allocation.md, content/tasks/ctl-allocation.json
  quote: Betaflight "mixer_type = LEGACY по умолчанию", "делятся на размах", "Без airmode при газе ниже 50 % размах дополнительно ужимается до 0.5…1", "`pidsum_limit` = 500 против `pidsum_limit_yaw` = 400"; task bf-legacy-scale
  why: mixer_init.c sets mixer_type = MIXER_LEGACY. applyMixerAdjustment scales by airmodeTransitionPercent/motorMixRange, where the transition runs 0.5 → 1 over throttle 0 to 0.5 without airmode. PIDSUM_LIMIT is 500 and PIDSUM_LIMIT_YAW is 400. The task formula with airmode, 100·min(1, 1/range), matches.
  source: https://raw.githubusercontent.com/betaflight/betaflight/4.5-maintenance/src/main/flight/mixer.c ; .../flight/pid.h
- verdict: ok
  file: content/design/ctl-allocation.md
  quote: ArduPilot "`MOT_YAW_HEADROOM`/1000 (умолчание 200 → 0.2)", rpy scaling and `limit.*`, "`normalise_rpy_factors` ±0.5", "`ACRO_OPTIONS` бит 0 или RC-опцию 84", thrust_loss_check (1 s, ≥ 90 % or throttle_upper, < 15°, "Potential Thrust Loss (N)"), highest filtered output = lost motor, "≥ 6 моторах"; "`set_throttle_factor` работает только до `init()` и только в классе 15"
  why: Every item matches Copter-4.6.3: AP_MOTORS_YAW_HEADROOM_DEFAULT is 200 and yaw_allowed_min = _yaw_headroom·0.001; crash_check.cpp has the constants 1/1500/0.9; check_for_failed_motor applies "number_motors >= 6"; set_throttle_factor returns false unless the frame class is MOTOR_FRAME_SCRIPTING_MATRIX and the matrix is not yet initialised (quiz Q8 is correct). Note: normalise_rpy_factors also rescales throttle factors to a maximum of 1 (1.071/0.929 → 1.0/0.867). The ratio, and so the module's claim, is preserved.
  source: https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.6.3/libraries/AP_Motors/AP_MotorsMatrix.cpp ; .../ArduCopter/crash_check.cpp ; .../ArduCopter/Parameters.cpp
- verdict: ok
  file: content/design/ctl-allocation.md
  quote: Lua `add_motor_raw` values and testing orders 1/3/4/2
  why: These match ArduPilot add_motor() conventions (roll = cos(angle+90), pitch = cos(angle), CCW = +1) and the Quad-X testing order.
  source: AP_MotorsMatrix.cpp (Copter-4.6.3); MotorMatrix_fault_tolerant_hex.lua
- verdict: ok
  file: content/design/ctl-allocation.md
  quote: "в `actuator_motors` PX4 это тяга (1.15, `THR_MDL_FAC` применяется позже, в драйвере выхода)"
  why: The thrust model is applied in mixer_module FunctionMotors::updateValues(thrust_factor).
  source: https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.17.0/src/lib/mixer_module/functions/FunctionMotors.hpp
- verdict: left: uncertain (note)
  file: content/quiz/ctl-allocation.json
  quote: "Моторы x500 (r = 0.246 м, KM = 0.05)"
  why: In PX4 4001_gz_x500 the front rotors sit at (0.13, ±0.22), so r = 0.256, and the rear at (−0.13, ∓0.20), so r = 0.239. The physical frame's 500 mm wheelbase gives 0.25. 0.246 is an approximation (the module's symmetric 0.174/0.174 frame). The answer does not change because r is given in the question. Optionally drop "x500".
  source: https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.17.0/ROMFS/px4fmu_common/init.d-posix/airframes/4001_gz_x500
- verdict: ok
  file: content/design/ctl-allocation.md
  quote: worked numbers (1.154 = 0.15/0.13, tilt ×1.84 and −1.5 %, 1.30 → 2.39, PNPNPN 0.75 = W/4, "минимум два нуля", PPNNPN survives M0/M1/M4/M5)
  why: All recomputed, and they match the rerun output.
  source: recomputation
- verdict: ok
  file: content/design/ctl-allocation.md
  quote: «Переход на реальное железо» steps 1–5 and criteria
  why: Props stay off for the motor test and the hand-tilt sign check, which is the step with motors spinning and the frame in hand. Props are fitted only at step 4, with 10 m distance and abort criteria. All criteria are measurable (±5 %, no motor above 90 %).
  source: module text
- verdict: ok
  file: content/quiz/ctl-allocation.json, content/tasks/ctl-allocation.json
  quote: 8 questions; 4 tasks
  why: Every answer is correct and unique. Over the extremes the tasks give: front motor 86–1071 g, yaw gain ×1.09–6.1, hexa motor load 17–78 % (never above 100 %), and BF scale 50–100 %.
  source: recomputation

## not opened (proxy)

- verdict: left: uncertain (note)
  file: references in all four modules
  quote: Leishman (openlibrary), NASA propeller-thrust and lift-to-drag pages, Brandt & Selig PDF, XFLR5, HX711/INA226/Espressif/PX4/Betaflight docs pages
  why: The sandbox proxy blocks curl to these hosts, and they were not opened with WebFetch. Their claims were checked through source files or derivation (see above), but I did not confirm that these exact URLs resolve.
  source: n/a
