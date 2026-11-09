# Fact-check, 2026-11-08

Independent review of all 103 modules by six agents that did not write them, against firmware
source and official documentation (ArduPilot master/4.7/4.6/4.5, PX4 main/1.14–1.17, Betaflight
4.5/2025.12/master, INAV 7.0–9.x, ExpressLRS, MAVLink common.xml, ROS 2 Humble/Jazzy) and by
recomputing worked examples. Every finding below was applied to the content (commits of 2026-11-08,
"Fact-check: …"), plus follow-up edits where the same fact appeared in other modules, quizzes and data.

| Report | Claims checked | error | outdated | imprecise |
|---|---|---|---|---|
| [ardupilot](ardupilot.md) | 394 | 17 | 19 | 12 |
| [betaflight](betaflight.md) | 315 | 50 | 15 | 17 |
| [companion-mav](companion-mav.md) | 350 | 13 | 4 | 13 |
| [foundation-electronics](foundation-electronics.md) | 489 | 21 | 2 | 19 |
| [inav-link-px4](inav-link-px4.md) | 329 | 20 | 4 | 15 |
| [perception-ros2](perception-ros2.md) | 327 | 4 | 2 | 7 |
| **total** | **2204** | **125** | **46** | **83** |

## Systemic causes

- **Firmware moved on.** Copter 4.7 renamed parameters into SI units (`ARMING_SKIPCHK`, `WP_*`, `RTL_ALT_M`,
  `ATC_ACC_*_MAX`, `PSC_D_ACC_*`); Betaflight 2025.12 renamed `motor_idle`, `failsafe_landing_time`, `iterm_windup`
  and the D-term pair; PX4 1.16/1.17 versioned uORB messages. Modules now give the new name with the old one
  in brackets, and ap-intro has a version note.
- **Stale official docs.** Several wrong claims match the vendor wiki word for word (Betaflight failsafe page,
  INAV Navigation.md); source code was taken as the authority.
- **Untested snippets.** Connection strings (`udpout` to a port nobody listens on), mission seq 0, Lua integer
  formatting, accelerometer sign in the Mahony lab — code in prose that never ran. Stage 3 iteration 3 (SITL in
  CI) is the structural fix.

## Still unverified

Each report ends with an "unverified" section: claims the reviewer could not confirm (blocked pages, vendor
figures without a primary source, rules of thumb). They stay in the text and are the starting list for the
next pass:

- ardupilot: 6 items
- betaflight: 8 items
- companion-mav: 8 items
- foundation-electronics: 10 items
- inav-link-px4: 9 items
- perception-ros2: 5 items

## Backlog resolved after the pass

- Raspberry Pi 5: `/dev/serial0` points to the debug UART `/dev/ttyAMA10`; GPIO 14/15 is `/dev/ttyAMA0`
  after `dtparam=uart0=on` (raspberrypi/documentation PR 3294) — comp-raspberry now says so.
- Lithium fire guidance unified across f-safety, el-battery-packs and f-electricity-101: knock the flame
  down, cool with plenty of water or isolate outdoors; class D is for metallic lithium.
- Sony VTC6 rating: 15 A continuous, 30 A with an 80 °C cutoff.
- f-motors-esc: the 2207-vs-2306 torque claim replaced with a neutral statement (compare thrust tables).
- tools-overview: Betaflight SITL is `make TARGET=SITL`.
- comp-esp32: the code now parses the documented `S,<mode>,<armed>,…` line; duplicate diagnostic removed.

## Stage 4 new modules (iteration 3)

`stage4-new-modules.md`: el-dronecan, link-digital-video, payload-gimbal, f-esc-firmware, ap-plane-tuning,
f-remote-id-security and their quizzes, checked by an independent agent against ArduPilot master/4.7,
PX4 main, pymavlink, MAVProxy, mavlink-devguide, Bluejay/AM32 sources. 4 findings (1 error, 1 outdated,
2 imprecise), all applied; quizzes clean. Not verified (fetch blocked): FAA Remote ID page, OpenIPC and
wfb-ng repository links — the weekly external link check covers them.

## Stage 4 wave 2 (iteration 4)

`stage4-wave2.md`: ops-weather, ops-maintenance, link-telemetry-radios, mav-multi-vehicle, ctl-guidance,
ctl-sysid, tools-gazebo, el-kicad and quizzes. 14 findings (4 errors, 2 outdated, 8 imprecise), all applied:
RADIO_STATUS.txbuf is free buffer space (also fixed in mav-routing), 4.7 stream rates `MAVn_*`, `--mcast`
for multi-vehicle SITL, L1 gain 4ζ², 4.7 `WP_SPD/WP_ACC/WP_JERK` units, SYSID input is `RATE.ROut` and the
entry conditions, Betaflight 2025.12 CHIRP mode, Gazebo camera streaming plugin. All code samples ran and
printed what the modules say. Several non-GitHub reference pages could not be fetched (weekly link check).

## Stage 5 practice depth

`stage5-practice-depth.md`: text added to 41 modules. 7 findings (3 errors, 1 outdated, 3 imprecise), all
applied: SITL ports 5762/5763 send no streams until asked (observer and takeoff scripts now request
messages; 4.7 rates are `MAVn_*`), `AUTOTUNE_AGGR` default 0.075 since 4.6, GPS glitch is ERR subsystem 11
code 2, `FS_EKF_ACTION` scope, rate measurement off-by-one. Also fixed from the reviewer's notes: comp-esp32
gap handling (re-checked on the host), ap-heavy hover throttle aligned with the module's own numbers.

## Stage 5 tasks, quizzes, glossary

`stage5-tasks-quizzes-glossary.md`: 31 numeric tasks, 66 new quiz questions, 69 glossary terms. 17 findings
(2 errors, 7 inaccuracies, 8 nits), all applied: INAV on GPS loss in RTH goes to Emergency Landing
(`failsafe_procedure` is the RC-loss reaction; the quiz and the nav-resilience module were wrong), AP_DDS is
an eProsima Micro XRCE-DDS client, `GPS1_RATE_MS` since 4.6, Bluejay targets BB21/BB51 (BB1 only to 0.18.1),
L2 tunnels carry MAVLink broadcast, two arguably-correct quiz distractors reworded, task wording and
tolerances (hover %, SiK units, hexa reliability, trapezoid ranges, T/W title).
