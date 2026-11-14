# Stage 6, iteration 2 — fact-check, part "vision"

Modules: `content/companion/nav-vtrn.md`, `content/companion/per-vision-pipeline.md`, `content/companion/comp-jetson-nano.md`
(+ their quiz/tasks JSON). Sources: ArduPilot `Copter-4.6.3` checkout at /tmp/ardupilot; PX4 `v1.15.4` via raw.githubusercontent.com;
MAVLink `common.xml` (master); NVIDIA docs via WebFetch; arXiv abstracts.

Reruns: `gen_video.py`, `pipeline.py` (frame / point / maxhits / att-offset 0, 50, 100), `score.py` — all P/R, FP/FN, geo error,
ID switches and interlock counts identical to the module and to `sample-output/`; timings within run-to-run noise.
`cc_health.py --parse` identical. Article code blocks of comp-jetson-nano equal the helper scripts line-for-line (blank lines aside).
SITL outputs of all three modules matched line-for-line against the saved runs (`sample-output/sitl_output.txt`,
`comp-jetson-nano.sitl_output.txt`, `nav-vtrn.sitl_output.txt`); nav-vtrn step-7 failure numbers found in `/tmp/vtrn/sitl_run4*.txt`,
`sitl_run6_lake*.txt`, `sitl_run7.txt` (scratch, not in the s6 helper copies). SITL was not re-run.
Lab code for per-vision-pipeline (`examples/vision-pipeline/`) is not yet in the repo — file names in the article match the staged copy.

## comp-jetson-nano

| # | Verdict | Quote | Finding | Source |
|---|---|---|---|---|
| J1 | fixed | «нет NVENC: 1080p30 на 1–2 ядрах CPU» (table, diag, quiz) | NVIDIA: x264enc ultrafast on a 30 fps camera stream = 38 % per core on all six cores ≈ 2.3 cores; resolution not stated. Changed to «≈ 2 ядра CPU» / «около двух ядер» | https://docs.nvidia.com/jetson/archives/r36.5.2/DeveloperGuide/SD/Multimedia/SoftwareEncodeInOrinNano.html |
| J2 | fixed | «На Orin после `jetson_clocks` смена режима требует перезагрузки» | Not in the r36.4.3 power doc; it says a reboot is needed when the new mode changes the GPU TPC power-gating mask. Rewritten accordingly | r36.4.3 PlatformPowerAndPerformance (Orin) |
| J3 | fixed | «плата 77 г, модуль 15 г, модуль с радиатором 61 г … (цифры из ответов на форуме NVIDIA)» | 15 g / 61 g are from NVIDIA staff (dusty_nv); 77 g is a user's subtraction (138 − 61) citing elinux. Attribution corrected | https://forums.developer.nvidia.com/t/weight-of-boards/175292 |
| J4 | fixed | «Orin Nano devkit — 100 × 79 × 21 мм … официальной массы нет» | Carrier Board Spec: carrier 100 × 79 mm; devkit 103 × 90.5 × 34.8 mm, 0.175 kg. Replaced | https://uelectronics.com/wp-content/uploads/2023/05/Jetson-Orin-Nano-DevKit-Carrier-Board-Specification.pdf |
| J5 | fixed | «Под TensorRT 8.2 ONNX экспортируют с `opset=12`» | No source found; Q-engineering's TensorRT-8 branch exports with `opset=11`. Replaced with the sourced statement | https://github.com/Qengineering/YoloV8-TensorRT-Jetson_Nano |
| J6 | fixed | Benchmark caveat paragraph, header «Модель, 640 px» | Ultralytics rows: inference only, 640 px, Orin Nano Super on JetPack 6.1 (guide's test note). Q-engineering rows: FPS of their C++ demo, scope and input size not stated, FP16. Power mode stated by neither. Caveats made explicit; "640 px" removed from header; quiz stem/explain adjusted. All numbers (299.09/67.03/172.88, 15.60/4.57/3.80/7.17, 19/9.25, INT8 −17…−39 %, mAP 0.480→0.449) confirmed | https://github.com/ultralytics/ultralytics/blob/main/docs/en/guides/nvidia-jetson.md , …/raspberry-pi.md, Q-engineering README |
| J7 | fixed | «загрузка с USB-накопителя, по JetsonHacks, появилась в JetPack 4.5 — у нас не проверено» | Confirmed by JetPack 4.5 release notes («loading kernel, DT and initrd from rootfs on USB drive or NVMe» for Nano; inserted microSD has priority). Text and reference added | https://docs.nvidia.com/jetson/archives/jetpack-archived/jetpack-45/release-notes/index.html |
| J8 | ok | «слота под NVMe нет (M.2 только Key E)» | User guide: «M.2 Key E connector can be used for wireless networking cards». Added «под Wi-Fi» | Nano DevKit User Guide (PDF) |
| J9 | fixed (wording) | `nvarguscamerasrc sensor-id=0` | Property is not in the Accelerated GStreamer guide; used as `sensor-id`/`sensor_id` in JetsonHacks CSI-Camera (GStreamer accepts both). Source named in text, reference added | https://github.com/JetsonHacksNano/CSI-Camera |
| J10 | fixed (wording) | «Orin Nano в простое — около 4 Вт (ответ модератора форума)» | Confirmed: NVIDIA staff, "around 4W idle", mode unstated; OP measured 6.1 W in default 25 W mode. Attribution + context added | https://forums.developer.nvidia.com/t/jetson-orin-nano-8gb-lowest-theoretical-operating-power-consumption/348662 |
| J11 | ok | Ubuntu 22.04 for JetPack 6.2; Python 3.6 on 18.04 | Standard (JP 6.x = Ubuntu 22.04; 18.04 ships python3 3.6.9) | JetPack 6.2 release notes |
| J12 | ok | nvpmodel table (Nano 0/1; Orin Super 0/1/2 with 1497.6/612, 1344/918 default, 1728/1020; non-Super 15/7 W) | Confirmed | r36.4.3 power doc; L4T 32.7.6 power_management_nano |
| J13 | ok | Thermal thresholds Nano 97/100.5/102/102.5 (CPU), 97.5/101/102.5/103 (GPU); Orin 99/103/104.5/105; fan 51 °C; jetson_clocks no fan since 32.4 | Confirmed | same |
| J14 | ok | 4.75–5.25 V, micro-USB 2 A, jack 4 A + J48, J41 5 V pins 2.5 A each, carrier 0.5–1.25 W, budgets = CPU+GPU only | Confirmed (datasheet Table 27; user guide) | DS-09366-001; Nano DevKit User Guide |
| J15 | ok | Orin devkit 9–20 V, 19 V supply; two M.2 Key M; 22-pin CSI | Confirmed | Carrier Board Spec; Orin devkit hardware layout |
| J16 | ok | Lifecycle: Nano module Jan 2027, Orin Nano Jan 2032 | Confirmed | https://www.developer.nvidia.com/embedded/lifecycle |
| J17 | ok | tegrastats lines 1–2, 2.9 W / 7.7 W peak / 4.5 W avg | Verbatim from the forum post | https://forums.developer.nvidia.com/t/power-consumption-monitoring/73608 |
| J18 | ok | Wire-drop and hover-time arithmetic (4.19 V, 0.48 A, 4.77/4.55/4.85 V, 11.84/11.46/9.97 min) | Recomputed | — |
| J19 | ok | NVAL logging, MAV_COMP_ID_ONBOARD_COMPUTER = 191, NAMED_VALUE_FLOAT name char[10], REBOOT_SHUTDOWN param2 = 2 (SHUTDOWN), PX4 debug_key_value + SDLOG_PROFILE bit 5 | Confirmed in GCS_Common.cpp, common.xml, PX4 logged_topics.h | — |
| J20 | ok (no trim) | Length | ~3550 words by `wc`; no theory block found that duplicates comp-raspberry/px4-companion-jetson beyond one-line cross-references, so nothing trimmed | — |

## per-vision-pipeline

| # | Verdict | Quote | Finding | Source |
|---|---|---|---|---|
| V1 | fixed | «метка буфера V4L2 идёт по CLOCK_MONOTONIC и ставится драйвером при приёме кадра (в начале или в конце)» | Kernel doc: MONOTONIC is a flag (`V4L2_BUF_FLAG_TIMESTAMP_MONOTONIC`), default source EOF (last pixel received), some drivers SOE = start of exposure (not "start of reception"). Rewritten; reference added | https://docs.kernel.org/userspace-api/media/v4l/buffer.html |
| V2 | fixed | «YOLO-n 25–150 мс на CPU» (2 places) | Lab: 25 ms (x86, 320 px); Ultralytics Pi 5 YOLO26n 640 px: NCNN 67 ms, PyTorch 299 ms. Range widened to 25–300 ms with its endpoints named | Ultralytics Raspberry Pi guide |
| V3 | left: estimate | Sensor 10–30 ms, link 3–20 ms; diagram uses 25 ms + 8 ms | Typical values, labelled in the text as "типичные до стендового замера"; no single source. Kept | — |
| V4 | fixed | «команда 6 м/с исполняется как 6.2 м/с» | Saved SITL run shows 6.1 m/s (also quoted as 6.1 in step 6) | sample-output/sitl_output.txt |
| V5 | ok | GUIDED velocity not capped by WPNAV_SPEED | `ModeGuided::velaccel_control_run` → `AC_PosControl::input_vel_accel_xy` → `shape_vel_accel_xy` uses only accel/jerk limits, not `_vel_max_xy_cms`; only AC_Avoid adjusts the target | ArduCopter/mode_guided.cpp, AC_PosControl.cpp @ Copter-4.6.3 |
| V6 | ok | GUID_TIMEOUT 3 s (range 0.1–5) → velocity zeroed, stays GUIDED; AP_FOLLOW_TIMEOUT_MS 3000; FOLL_POS_P 0.1; FOLL_DIST_MAX 100; AVOID_ENABLE 3, AVOID_MARGIN 2 m; PLND_LAG 0.02–0.25 s; LANDING_TARGET BODY_FRD + distance > 0; correct_offboard_timestamp_usec_to_ms | Confirmed in 4.6.3 source; FOLL_TIMEOUT exists only on master (quiz explain OK) | — |
| V7 | ok | PX4 COM_OF_LOSS_T (1.0 s, 0–60), COM_OBL_RC_ACT, GF_ACTION, GF_MAX_HOR_DIST, FLW_TGT_HT/DST (8 m), PLD_BTOUT, PLD_SRCH_ALT | All exist in v1.15.4 | commander_params.c, geofence_params.c, AutoFollowTarget/follow_target_params.c, precland_params.c |
| V8 | ok | MPC_XY_VEL_MAX as offboard cap | `MulticopterPositionControl` passes MPC_XY_VEL_MAX to `setVelocityLimits`; `PositionControl::_positionControl` constrains `_vel_sp.xy()` (incl. feed-forward offboard velocity) to it | MulticopterPositionControl.cpp, PositionControl.cpp @ v1.15.4 |
| V9 | fixed | PX4 LANDING_TARGET «только MAV_FRAME_LOCAL_NED и x, y, z» | v1.15.4: with position_valid = 1 only LOCAL_NED; with position_valid = 0 angle_x/angle_y are published as `irlock_report`. Cell corrected | mavlink_receiver.cpp handle_message_landing_target |
| V10 | fixed (wording) | «R = 0.4 м (21 px)» | 21 px is the diameter (2·0.4·400/15 = 21.3). Now «Ø 21 px» | — |
| V11 | ok | TIMESYNC request/response semantics, offset formula | Matches common.xml #111 | common.xml |
| V12 | ok | Pipeline constants (gate 0.8–1.3, fill ≥ 0.6, Kp 0.8, 2 m/s, 3-frame confirm, max_age 15, gate 30 px, reacq 100 px, watchdog 0.5 s / 3 s), dataset 240 = 192/48 | Match pipeline.py / make_dataset.py | — |
| V13 | ok | Rock area 201 px² vs gate 229 px²; δ = 0.72 m; diagram 36 / 65 ms; ×4.5 | Recomputed | — |
| V14 | left: not re-verified | «проходит ворота в 564 кадрах из 1200 (без remap — в 119)», «в 93 px от последней позиции» | Needs instrumenting pipeline.py; FP 77 / FN 79 that follow from it do reproduce | — |
| V15 | left: uncertain | quiz Q8 explain «детекция через кадр … режет среднюю задержку команды почти вдвое» | Halving the detector rate cuts compute load, not the age of a detection; the claim is loose. Not changed (author's call) | — |

## nav-vtrn

| # | Verdict | Quote | Finding | Source |
|---|---|---|---|---|
| N1 | ok | «здоров при среднем интервале < 215 мс: слать нужно ≥ 5 Гц» | `AP_GPS::is_healthy`: `delay_avg_max = 215` (333 for RTK rover), `delayed_count < 2` with a frame "delayed" above 245 ms (`gps_max_delta_ms`); comment "average frame rate close to 5Hz" | libraries/AP_GPS/AP_GPS.cpp @ Copter-4.6.3 |
| N2 | ok | horiz_accuracy → R constrained [EK3_POSNE_M_NSE 0.5, 100]; EK3_GPS_CHECK HDOP 2.5 / 6 sats / hAcc 5 / sAcc 1; sAcc fail 1.5 / recover 1.0; arming 3D fix + < 50 m; GLITCH_RAD 25; UseBest semantics | Confirmed (PosVelFusion.cpp:744, VehicleStatus.cpp, AP_Arming.cpp:681–705, AP_GPS.cpp:1495) | — |
| N3 | ok | PX4 1.15 has no GPS_INPUT handler; EKF2_AGP_CTRL bit 0 (bit 1 = vertical), EKF2_AGP_NOISE 0.9, EKF2_AGP_GATE 3; /fmu/in/aux_global_position (VehicleGlobalPosition); EKF2_EV_CTRL bits 0–3, EKF2_EVP_GATE 5, EKF2_EV_NOISE_MD | Confirmed: no `MAVLINK_MSG_ID_GPS_INPUT` case in mavlink_receiver.cpp; params in ekf2/module.yaml; topic in uxrce_dds_client/dds_topics.yaml (all v1.15.4) | — |
| N4 | fixed | rectify code snippet (`M = getRotationMatrix2D(...)`, `warpAffine(frame, M, (Wr, Hr))`) | Snippet omitted `Wr, Hr` and the translation that centres the frame on the larger canvas, so `perspectiveTransform([[Wr/2, Hr/2]])` would map the wrong point. Two lines added from vtrn_lab.py `map_fix` | /tmp/claude-0/work/s6/nav-vtrn.vtrn_lab.py:236–241 |
| N5 | fixed (wording) | RANSAC N for w = 0.5 / 0.2: 72 / 2900 | Correct only for p = 0.99, which was not stated. Added | — |
| N6 | fixed | «SuperPoint и LightGlue держат смену сезона и освещения, где ORB сдаётся» | Abstracts: SuperPoint — self-supervised detector+descriptor, SOTA homography on HPatches vs LIFT/SIFT/ORB; LightGlue — efficient learned matcher. Season robustness is not claimed. Rewritten to what the papers say | arXiv 1712.07629, 2306.13643 |
| N7 | ok | NetVLAD — trainable VLAD layer for place recognition; AnyLoc — universal VPR from off-the-shelf self-supervised features (DINOv2 in the paper body) + unsupervised aggregation | Consistent with abstracts | arXiv 1511.07247, 2308.00688 |
| N8 | ok | All lab and SITL output blocks, RANSAC/footprint/overlap/sin 1° arithmetic, route 1.3 km / 900 m | Matched saved outputs; recomputed | nav-vtrn.lab_output.txt, nav-vtrn.sitl_output.txt |

## Quiz / tasks

- All keyed answers checked; unique and correct. Fixed: comp-jetson-nano Q4 option/explain (≈ 2 cores, J1); benchmark question stem/explain (J6).
- Tasks: formulas match the theory; grids sensible (hover-loss up to 720 W, wire drop can go negative-margin by design). nav-vtrn `ransac-iters`, `vo-min-fps`, per-vision `timesync-error`, `glass-to-command`, Jetson `u-board`, `pipeline-fps` worked examples recomputed — ok. (`pipeline-fps` uses 52.6 / 108.1 ms = 1000/19 and 1000/9.25 from Q-engineering, whose FPS may already include pre/post — minor.)

## Safety of «Переход на реальное железо»

- comp-jetson-nano: props off until step 6, tethered/netted hover, measurable criteria — ok.
- per-vision-pipeline: bench with props off, then tether/low hover with listed abort criteria — ok.
- nav-vtrn: props off on bench, shadow mode before live, GNSS kept as reference, abort criteria — ok.
