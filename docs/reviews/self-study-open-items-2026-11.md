# Modules where the reader cannot self-check the result (no reference in the module) — Phase 2 input
## companion / design
- mav-sdk: no reference message sequence (step 1); no expected connection_state / autopilot behaviour (step 4)
- payload-gimbal: no expected GIMBAL_DEVICE_ATTITUDE_STATUS rate; no criterion for angle-vs-rate choice
- mav-multi-vehicle: no expected follower lag; step 3 text says lower sysid goes LOITER, code holds the higher one (inconsistency)
- mav-routing: netem delay one-way or both? expected median RTT ambiguous
- comp-raspberry: step 4 no expected temperature / time-to-throttle
- per-mapping: step 2 no expected numbers for the ODM dataset
- per-cv, per-edge-ml: no reference dataset/result
- per-visual-nav: no SITL output or tolerance for XKF1 vs truth; step 4 (frozen pose rejected by gates) contradicts theory (EKF believes it)
Headings left with old wording (byte-identical rule): fw-reading «### Шаг 4. Отчёт», eng-systems «### Шаг 4. Пакет и передача».
## betaflight / inav / link
- link-digital-video: no latency numbers (worked table median/max for two modes; link quality at bitrate drop / blocks / freeze)
- bf-features-tour step 2: minimum dyn_idle_min_rpm where the increase saturates at 15 % — script answer missing; Horizon strength 0.300 at 45°/30 % derived by the editor, verify
- bf-arming-safety own scenario (throttle ≥ 75 %, 250 ms): no reference output
- bf-rates-rc: solo blind-shuffle script referenced but not listed in the module — add listing (verify the editor's procedural addition)
- No self-check paragraph / lab task at all: bf-blackbox, bf-cli (candidate: motor-remap example), bf-intro, bf-ports, bf-pid-reg-in-bf, bf-modes-osd, link-elrs, link-vtx, inav-gps, inav-wing
- bf-failsafe step 4.2: "2–3 с" already exceeds failsafe_delay 1.5 s → should read "~1 с" (fix at integration)
## foundation / electronics / estimation
- est-kalman step 1б: no numbers for perturbed runs. Editor ran the module script (seed 0): base RMS h 0.044 m, NIS 1.00, bias 0.202; q_acc×10 → 0.068 / 0.99; q_acc×0.1 → 0.039 / 1.01; r_baro×10 → 0.045 / 0.10; 1 s glitch with gate max err 0.41 m; 10 s glitch ends ~5.1 m off. CONTENT PROBLEMS: "задержка до 1.8 м/с" metric is 210 ms for all q_acc (useless); theory "Q слишком мал → запаздывание, большие инновации" not reproduced by the lab (q_acc×0.1 gives lower RMS). Re-run, then put numbers in and fix the theory/lab mismatch.
- f-remote-id-security step 2: no pasted output for unsigned vs signed attempt
- f-esc-firmware step 4: no expected size of 24 vs 48 kHz difference
- el-emi step 2: no reference for a clean airframe (only 30 % bad threshold)
- ops-maintenance step 4: no number for λ = 1/3000 h
- f-regulations, ops-case-studies, eng-method-101, ops-field: reader-specific; need a filled sample
- ops-field «Учебный поиск»: needs a second person; no solo variant
- f-safety: no lab, no completion criterion
Heading changed by editor: el-measure «### Шаг 5. Отчёт» → «### Шаг 5. Таблица измерений» (accepted).
## ardupilot / px4 / ros2 / tools / math
- math-ode-dyn step 1: "find kp where undamped oscillations begin" has NO answer — P-only model stays stable to kp=1e5 (needs delay in model or rewording); step 2: no reference kd for ringing
- ap-plane-tuning step 5: no target sink rate / rollout
- px4-companion-jetson steps 3,4,6: no expected rates / throttling temperature
- ap-tuning: no expected ATC_RAT_RLL_* from SITL AUTOTUNE, no target notch attenuation
- ctl-sysid steps 3–4: no expected K, T, τ
- ctl-guidance: no reference L for 20 m/s; no numbers for the two jerk settings
- tools-gazebo: no expected RTF / camera fps; step 2 question unanswered
- ap-lua step 4: no completion criterion
- math-prob-est steps 1–2: no worked ARW / bias-instability example
- px4-architecture, ros2-from-ros1: reader-specific
## from the reference verification (docs/reviews/factcheck/self-study-references-2026-11.md)
- math-ode-dyn step 3: 50 Hz sine at T_s = 1/100 is exactly Nyquist — all samples zero; step 1 has no answer (see above)
- ctl-sysid:129 "близкую к расчёту шага 2" — step 2 uses 80→40 Hz but Copter default INS_GYRO_FILTER is 20 Hz
- ap-safety-fs:81 RPN threshold not stated; ap-plane-tuning:91 no metric; per-landing:110 no tolerance; el-wiring:101 judgement call
- est-gnss:114 "12 и больше" vs block "20 и больше"; eng-ci-configs:122 checklist name; ros2-nav:54 reaction-delay formula only in Эталон; inav-missions:110 "первая строка" = first wp line

## Status 2026-11-18 (later)
- DONE: math-ode-dyn steps 1–3 and est-kalman step 1b repaired (commit d6a7325b).
- DONE: the eleven modules without any self-check now have a no-hardware exercise, criteria and a reference block; 18 task-bank items added (7 new banks).
- Still open: everything else above; bf-pid-reg-in-bf in-flight tuning steps 2–6 have no numeric pass criteria; est-kalman steps 2–3 qualitative only.
- DONE (stage 3): five judgement-call criteria given numbers (ctl-sysid, ap-safety-fs, ap-plane-tuning, per-landing, el-wiring); contradictions fixed (est-gnss, eng-ci-configs, ros2-nav, inav-missions, per-visual-nav, mav-multi-vehicle, mav-routing, link-vtx IMD, comp-intro); solo variants (bf-rates-rc, ops-field); diagrams ap-setup-flow and bf-arming-flag-groups brought to 4.7 / 2025.12. Course conventions introduced and labelled as such: RPN ≥ 27 or S = 5 (ap-safety-fs), 10 % no-change band (ap-plane-tuning), 1 px corner error (per-landing), netem tolerances (mav-routing). Calculated, not measured — to confirm in Phase 2: ctl-sysid 20→10 Hz phase numbers, mav-routing RTT, bf-rates-rc inline snippets.
