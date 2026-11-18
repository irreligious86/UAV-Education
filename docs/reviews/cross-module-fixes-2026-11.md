# Cross-module consistency fixes, 2026-11

Input: `INCONSISTENCIES.md` from the «Место в системе» linking pass (28 contradictions + weak links).
Rule applied: decide by primary source, not by majority; where both statements hold under different conditions, each place now states its condition.

Verdicts: **fixed** (one side was wrong by source), **reconciled** (both true, condition added), **open** (source could not settle it, text left as is).

Source roots: BF = `/tmp/bf-migrate/bf2025/src/main`, AP = `/tmp/ardupilot-audit/copter472`, INAV = `/tmp/inav-audit/inav9/src/main`, ELRS = `/tmp/elrs-migrate/elrs41/src`.

## Items

| # | Item | Verdict | Source | Files changed |
|---|------|---------|--------|---------------|
| 1 | SBUS failsafe: is "No Pulses" required? | **fixed** — the SBUS failsafe flag is honoured by both firmwares, so `Last Pos` (frames with the flag) works too; "No Pulses" is mandatory only for outputs with no flag (PWM/PPM). link-protocols / link-elrs were right. | BF `rx/sbus_channels.c:76-79`, `rx/rx.c:550`; INAV `rx/sbus_channels.c:74-77`, `rx/rx.c:416-420`; ELRS `src/rx-serial/SerialSBUS.cpp:27,89` | `betaflight/bf-failsafe.md`, `inav/inav-setup-scratch.md`, `link/link-protocols.md` (diagnostics) |
| 2 | `serialrx_inverted` for SBUS | **fixed** — for SBUS, ON = non-inverted signal; F7/H7/G4 need no change. link-protocols:76 was wrong, bf-ports:103 right. | BF `rx/sbus.c:192-194`, `rx/crsf.c:650`, `rx/fport.c:406` | `link/link-protocols.md`, `electronics/el-peripherals.md` (same wrong hint) |
| 3 | `dshotprog` motor reverse | **fixed** — 7/8 (`SPIN_DIRECTION_1/2`) + 12 set the stored direction; 20/21 are the temporary reversal the firmware sends for crashflip. bf-cli was wrong. | BF `drivers/dshot_command.h:42-51`, `fc/core.c:592`, `drivers/dshot_command.c:196-204`; Bluejay `src/Modules/DShot.asm` (https://raw.githubusercontent.com/bird-sanctuary/bluejay/main/src/Modules/DShot.asm) | `betaflight/bf-cli.md`, `quiz/bf-cli.json` |
| 4 | Beeper condition count | **fixed** — 2025.12 has 23 conditions + `ALL` (4.5 had 24). bf-intro was right. | BF `io/beeper.c:210-233`, `io/beeper.h:38-61`; bf453 `io/beeper.h` | `betaflight/bf-led-buzzer.md` |
| 5 | Digital video systems per site | **fixed (partly)** — the blanket "fewer than analog" is wrong for HDZero (up to 8 pilots). link-digital-video now states it depends on system and channel width. The Walksnail "8" and DJI "fewer" figures in link-vtx were not verified. | https://docs.hd-zero.com/ ("up to 8 simultaneous pilots") | `link/link-digital-video.md` |
| 6 | Two AUX layouts in bf-modes-osd | **fixed** — second layout rewritten to match the first (ARM AUX1, mode AUX3, FAILSAFE AUX6, BEEPER AUX7, PREARM AUX8); extras moved to free AUX2/AUX4. Quiz has no layout question; no tasks file for this module. | internal consistency (no firmware constraint on the choice) | `betaflight/bf-modes-osd.md` |
| 7 | `GPS_RESCUE` vs `GPS-RESCUE` | **fixed** — the `failsafe_procedure` value is `GPS-RESCUE`; "GPS RESCUE" (mode name) left. | BF `cli/settings.c:383` | `betaflight/bf-failsafe.md` |
| 8 | Fence stop margin in GUIDED | **fixed** — `FENCE_MARGIN` (or `FENCE_MARGIN_XY` if non-zero); `AVOID_MARGIN` applies to proximity/beacon obstacles. per-tracking was right. | AP `libraries/AC_Avoidance/AC_Avoid.cpp:816,878,916,964` vs `:1265`; `libraries/AC_Fence/AC_Fence.cpp:100,166` | `companion/per-vision-pipeline.md` (text + reference label) |
| 9 | Target-loss timeout exit | **fixed** — LOITER takes climb rate from the pilot's throttle; without a pilot the exit is BRAKE or zero velocity in GUIDED. per-vision-pipeline:92 was right; its :88 and per-tracking now state the condition. | AP `ArduCopter/mode_loiter.cpp:96`, `ArduCopter/mode_brake.cpp:61` | `companion/per-vision-pipeline.md`, `companion/per-tracking.md` |
| 10 | Jetson Orin Nano power | **open** — see below. | — | — |
| 11 | INT8 quantization cost | **reconciled** — ×2…×4 is vs FP32 on integer accelerators; vs FP16 on Jetson GPUs the gain is 17–39 % (Orin Nano Super) or none (old Nano). | module's own cited benchmarks (Ultralytics Jetson guide, Q-engineering) — not re-fetched | `companion/per-cv.md`, `companion/per-edge-ml.md` |
| 12 | Orin Nano YOLO-nano inference time | **reconciled** — per-cv figure marked as an order-of-magnitude estimate; 4.57 ms tied to YOLO26n on Orin Nano Super. | as in 11 — not re-fetched | `companion/per-cv.md` |
| 13 | comp-raspberry duplicated sections | **fixed** — short «Сервис вместо…» and first «Время и логи» merged into the fuller later sections (`journalctl`, "no exact time after boot", `TimeUS`-like counter kept). | — | `companion/comp-raspberry.md` |
| 14 | 0.72 m vs 0.71 m | **fixed** — 15·tan(2.7°) = 0.707 m. | arithmetic | `companion/per-vision-pipeline.md` |
| 15 | X8 D-term filter | **fixed** — FLTD = `INS_GYRO_FILTER`/2 → 15 Hz for 30 Hz. ap-tuning was right. | AP `libraries/AP_Quicktune/AP_Quicktune.cpp:16,363`, `libraries/AP_Scripting/applets/VTOL-quicktune.md:159`; ardupilot_wiki `copter/source/docs/setting-up-for-tuning.rst` | `ardupilot/ap-heavy.md` |
| 16 | EKF noise parameter names | **fixed** — `EK3_*_M_NSE` / `EK3_*_P_NSE`. | `/tmp/ardupilot-audit/copter-4.7.2.pdef.json` (`EK3_POSNE_M_NSE`, `EK3_GYRO_P_NSE`) | `math/math-prob-est.md` |
| 17 | VIBE thresholds | **reconciled** — 30/60 are the general documentation thresholds; 15 is the working target for large props. | ardupilot_wiki `common/source/docs/common-measuring-vibration.rst` ("below 30m/s/s … above 60m/s/s") | `ardupilot/ap-logs.md`, `ardupilot/ap-heavy.md`, `ardupilot/ap-tuning.md` |
| 18 | 5" motor time constant | **open** — see below. | — | — |
| 19 | Jetson UART device name | **fixed** — name depends on board/JetPack; px4-ros2 and the practice of px4-companion-jetson now point to the loopback check. | internal (px4-companion-jetson theory + quiz); not checked against NVIDIA docs | `px4/px4-ros2.md`, `px4/px4-companion-jetson.md` |
| 20 | ap-lua "F4 не хватает" | **fixed** — scripting is built for flash > 1 MB, so F427/F429 run Lua with a small default heap. Diagram caption untouched as instructed. | AP `libraries/AP_Scripting/AP_Scripting_config.h:8`, `libraries/AP_Scripting/AP_Scripting.cpp:42-49` | `ardupilot/ap-lua.md` |
| 21 | LiPo salt water | already fixed at integration | — | — |
| 22 | DroneCAN node id range | **fixed** — valid 1–127; 126/127 reserved for maintenance tools, so dynamic allocation gives ≤ 125. | https://dronecan.github.io/Specification/4.1_CAN_bus_transport_layer/ , https://dronecan.github.io/Specification/6._Application_level_functions/ | `electronics/el-peripherals.md`, `electronics/el-dronecan.md` |
| 23 | 5" hover rpm | **reconciled** — 14 000 rpm is the light-build case, 15–21k the heavier one. | no primary source; conditions only | `foundation/f-frame-mech.md`, `foundation/f-safety.md` |
| 24 | Hover efficiency | **reconciled** — the higher 10–15" figures are for a small fraction of max thrust. | f-aero-props own wording; no primary source | `foundation/f-components-choice.md` |
| 25 | RTK base distance | **reconciled** — 10–20 km for an own base, 50–100 km for an NTRIP network at 1 ppm cost. | ZED-F9P data sheet figure already cited in nav-rtk (not re-fetched) | `estimation/est-gnss.md`, `estimation/nav-rtk.md` |
| 26 | ESC margin | **reconciled** — the 45 A / 38 A example is 1.18×, below the 1.3× rule, and is now labelled as such. | arithmetic | `foundation/f-components-choice.md`, `foundation/f-motors-esc.md` |
| 27 | LiPo cold-charge threshold | **reconciled** — 10–45 °C is the Gens Ace figure; other places now say the threshold is per manufacturer. | Gens Ace safety manual (https://www.freeflysystems.com/wp-content/uploads/2021/11/Gensace_safety_manual.pdf): "keep the tempreture between 10 ℃ and 45℃" | `foundation/f-electricity-101.md`, `foundation/f-power.md`, `foundation/ops-weather.md` |
| 28 | LiPo storage voltage | **reconciled** — about 3.8 V; 3.80–3.90 V per Gens Ace. | same manual: "Storage Single Cell Voltage : 3.80V~3.90V" | `foundation/f-electricity-101.md`, `foundation/f-power.md` |

Quiz change to report: `quiz/bf-cli.json`, question «Как сохранить реверс направления мотора через DShot-команды?» — the keyed option (index 0) said `dshotprog 1 21`, which became wrong. The option text is now `dshotprog 1 8, затем dshotprog 1 12` and the explanation is rewritten; answer index and option count unchanged.

## Weak links in «Место в системе» blocks

| Module | Result |
|--------|--------|
| math-prob-est | Reworded. The inference is correct, not inverse: the gate test divides by P + R (AP `libraries/AP_NavEKF3/AP_NavEKF3_PosVelFusion.cpp:808-817,891`), so a too-low `*_M_NSE` raises the test ratio. The bullet now says that explicitly. |
| math-ode-dyn | Reworded: per-tracking supports "delay cuts the allowed gain", not "period comparable to τ". |
| ap-intro | Reworded: f-fc-sensors supports only "fewer UARTs, no hardware inversion"; the flash limit is now cited to ap-lua. |
| px4-companion-jetson | Reworded: el-power-design supports a separate BEC with current margin, not "common ground". |
| tools-gazebo | Reworded: per-cv lists real-world failure classes (glare, shadows, motion blur), not sim-to-real; ros2-basics only states the course ROS 2 version. |
| inav-intro | Citation to inav-missions dropped (it does not cover the throttle oscillation). |
| f-safety | Airspeeder bullet made specific to what ops-case-studies says (last throttle held, kill switch failed). |
| el-dronecan | Reworded: the pre-arm "Duplicate Node" message is real (AP `libraries/AP_DroneCAN/AP_DroneCAN_DNA_Server.cpp:481-491`) but ap-safety-fs only covers the pre-arm mechanism. |
| nav-rtk | Reworded: comp-mavlink does not mention RTCM; it is now cited only for the MAVLink channel itself. No module other than est-gnss / nav-rtk covers `GPS_RTCM_DATA`. |
| comp-esp32, mav-multi-vehicle, ctl-allocation, payload-gimbal, inav-ipf, bf-features-tour, est-sensors | Checked, left unchanged: the cited modules support the claims (`RCOU` in ap-logs:124,136,149; GCS heartbeat failsafe in ap-safety-fs:32; LQ/RSSI in link-elrs:91; dynamic idle zeroed without DShot telemetry in BF `flight/mixer_init.c:346-350`). |

All blocks remain the last `###` of theory, 60–120 words, three bold labels.

## Open items

- **10. Jetson Orin Nano power.** comp-intro says "19 В или 5 В/4 А в зависимости от модуля"; comp-jetson-nano says the devkit jack takes 9–20 V. The NVIDIA pages reachable (`docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/hardware_layout.html`, `…/howto.html`) do not state the voltage range; the carrier board specification copy (uelectronics.com PDF) and developer.nvidia.com were blocked. Text left. Likely fix once the spec is readable: comp-intro should say 9–20 V for the Orin Nano devkit and keep 5 V/4 A for the old Jetson Nano only.
- **18. 5" motor time constant** (ctl-theory 10–30 ms vs math-ode-dyn 15–30 ms). No primary source on disk or found; the ranges overlap. Text left.
- **5 (remainder).** link-vtx figures "8 for Walksnail, fewer for DJI on wide channels" not verified against vendor documentation.
- **19 (remainder).** `/dev/ttyTHS0` vs `/dev/ttyTHS1` per board/JetPack not verified against NVIDIA documentation; only made consistent with px4-companion-jetson.

## Validation

`python3 scripts/validate_content.py` reports four errors, none from this pass: quizzes `f-micro-whoop`, `f-starter-kit`, `link-edgetx`, `ops-pilot-training` have no manifest entry. Those modules (md + quiz + tasks) appeared in `content/` during this pass from another job; `data/` is out of scope here. Before they appeared the validator returned OK (140 articles). Code-fence counts per module and quiz question counts are unchanged.
