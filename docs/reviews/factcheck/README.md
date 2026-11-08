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
