---
id: fw-reading
title: "How to read firmware source code: Betaflight and ArduPilot"
level: L4
readingTime: 45 min
firmware: Betaflight · ArduPilot
status: published
added: 2026-11-08
tags:
  - source code
  - Betaflight
  - ArduPilot
  - SITL
  - patch
related:
  - bf-custom
  - emb-basics
  - ctl-theory
  - ap-sitl
next:
  - eng-ci-configs
source: content/companion/fw-reading.md
source_hash: 6ae3972e9635
---

## summary
Documentation describes what a parameter “does”; only the code shows what it **actually** does — with the order of operations, the limits and the side effects. This module teaches you to find your way around two large codebases without reading all of it: how to trace the path from the gyro to the motors, where the PID and filters live, how to check the implementation against theory (and find discrepancies), and how to make a minimal change, build it and test it in SITL — without touching a real aircraft. The lab: a patch with a report.

## theory
### Reading tools
`git clone` + `grep -rn`/`rg` + an editor with go-to-definition (VS Code with clangd, or just `rg "pidController\("`). For C/C++ firmware the main technique is to go from the **scheduler entry point** down the call chain, and from the **parameter** (its name in the code) to where it is used. `git blame`/`git log -S "name"` shows when and why a line was added — the PR comment often explains more than the wiki.

### Betaflight: the gyro → PID → mixer path
Repository `betaflight/betaflight`, code in `src/main/`:

1. **Scheduler**: `scheduler/scheduler.c` — picks tasks from the `fc/tasks.c` table. The `TASK_GYRO` task (`taskGyroSample`) and `TASK_FILTER`/`TASK_PID` (`taskMainPidLoop` in `fc/core.c`).
2. **Gyro**: `sensors/gyro.c` — `gyroUpdate()` reads the driver (`drivers/accgyro/accgyro_spi_icm426xx.c` and others, via DMA), `gyroFiltering()` applies the chain: RPM notch (`flight/rpm_filter.c`), dynamic notch (`flight/dyn_notch_filter.c`), LPF1/LPF2 (`common/filter.c`: PT1/PT2/PT3/biquad). The filter order is set right here, and it is not obvious from the configurator.
3. **PID**: `flight/pid.c` — `pidController()`: for each axis error = setpoint − gyro, P, I with anti-windup and iterm_relax, D on the filtered gyro (D-LPF, `d_min`/`d_max`), feedforward (`flight/pid_init.c`, `fc/rc.c` — FF is computed from the setpoint derivative with interpolation/smoothing), TPA, anti-gravity, `pidSum` in `pidData[axis].Sum`.
4. **Mixer**: `flight/mixer.c` — `mixTable()`: pidSum per axis × the mixer matrix (`mixer_init.c`/`mixer_tricopter.c`) + throttle → motors, `airmode`, limiting (`mixer_type`: LEGACY/LINEAR/DYNAMIC), idle (`dshot_idle_value`), `motorOutputLimit`.
5. **Output**: `drivers/dshot.c` (frame encoding), `drivers/pwm_output.c`; the platform part on current master — `src/platform/STM32/dshot_bitbang.c`, `src/platform/common/stm32/dshot_dpwm.c`, `pwm_output_dshot_shared.c` — generating DShot frames via timer+DMA; bidirectional DShot eRPM decoding — `drivers/dshot_bitbang_decode.c` (in 4.5 `dshot_dpwm.c` lived in `src/main/drivers/`).
6. **Blackbox**: `blackbox/blackbox.c` — what is logged and how (`blackbox_fields.c`).

Checking against theory: in `pid.c` find how D is computed — `-(gyroRateDterm[axis] - previousGyroRateDterm[axis]) * pidFrequency`, where `gyroRateDterm` is the gyro already passed through the D-notch and D-LPF1/LPF2 (the filters sit before the differentiation), then multiplied by `pidCoefficient[axis].Kd` and `dMinFactor` (in master — `dMaxMultiplier`): D is taken from the **gyro**, not from the error (no “derivative kick” when the stick moves), and the coefficient scaling is constants in `pid.h`, applied in `pid_init.c` (`PTERM_SCALE`, `ITERM_SCALE`, `DTERM_SCALE`: that is where the “dimensionless” values in the configurator come from).

### ArduPilot: the IMU → rate → motors path
Repository `ArduPilot/ardupilot`, the vehicle in `ArduCopter/`, libraries in `libraries/`:

{{diagram:ardupilot-fast-loop|The ArduCopter fast loop: tasks the scheduler calls every tick, and slow tasks with their own rate.}}

1. **Scheduler**: `ArduCopter/Copter.cpp` — the `scheduler_tasks[]` table: `FAST_TASK_CLASS(AP_InertialSensor, &copter.ins, update)` → `FAST_TASK(run_rate_controller_main)` → `FAST_TASK(motors_output_main)` → `FAST_TASK(read_AHRS)` → … → `FAST_TASK(update_flight_mode)`; slow tasks `SCHED_TASK(rc_loop, 250, 130, 3)` with a rate, a budget (µs) and a priority. Newer versions support a dedicated rate thread (`ArduCopter/rate_thread.cpp`, `FSTRATE_ENABLE`) at the gyro rate.
2. **IMU and filters**: `libraries/AP_InertialSensor/` — `AP_InertialSensor.cpp` (`update()`), backend drivers (`AP_InertialSensor_Invensensev3.cpp`), harmonic notch `libraries/Filter/HarmonicNotchFilter.cpp`, LPF `Filter/LowPassFilter2p.cpp`.
3. **Rate loop**: `ArduCopter/Attitude.cpp` — `run_rate_controller_main()` → `attitude_control->rate_controller_run()` in `libraries/AC_AttitudeControl/AC_AttitudeControl_Multi.cpp`: for each axis `_motors.set_roll(get_rate_roll_pid().update_all(target, gyro, dt, _motors.limit.roll, …))` in `libraries/AC_PID/AC_PID.cpp` (P, I with a limit, D with the `FLTD` filter, FF, the error through `FLTE`, the target through `FLTT`) → `_motors.set_roll(...)`.
4. **Angle loop**: `AC_AttitudeControl.cpp` — `input_euler_angle_roll_pitch_euler_rate_yaw()` and others → quaternion error → `rate_target_ang_vel` with `ATC_ANG_*_P` and acceleration limits (`ATC_ACCEL_*_MAX`) — the input shaping implementation.
5. **Motors**: `ArduCopter/motors.cpp` `motors_output_main()` → `libraries/AP_Motors/AP_MotorsMulticopter.cpp` `output()` (throttle filter, lift_max from battery voltage, spool logic) → `AP_MotorsMatrix.cpp` `output_armed_stabilizing()` (distributing roll/pitch/yaw/throttle over the matrix with priority and `MOT_YAW_HEADROOM`) → `output_to_motors()` → `SRV_Channel`/`AP_HAL` RCOutput (DShot/PWM).
6. **EKF**: `libraries/AP_NavEKF3/` — `AP_NavEKF3_core.cpp` (`UpdateFilter`), one file per measurement type (`*_PosVelFusion.cpp`, `*_MagFusion.cpp`, `*_OptFlowFusion.cpp`), sources in `AP_NavEKF/AP_NavEKF_Source.cpp`.
7. **Parameters**: `ArduCopter/Parameters.cpp` and `*_Params.cpp` in the libraries — `// @Param:` blocks with a description, range and `@Values` — this is the source of the parameter wiki.

Checking against theory: in `AC_PID::update_all()` see that D is computed from the error passed through `FLTD`, not from the raw gyro; that I is limited by `IMAX` and does not accumulate under `limit` (motor saturation) — that is the anti-windup; `AP_MotorsMatrix::output_armed_stabilizing()` — the order: roll/pitch first, then yaw — as much as fits (`MOT_YAW_HEADROOM` is the guaranteed minimum), and only then the throttle that fits into the remaining range is chosen.

### Minimal patch and SITL
Betaflight: `make SITL` builds the firmware for Linux (`obj/main/betaflight_SITL.elf`), connects to a simulator (RealFlight/gazebo over UDP) or simply lets you connect the configurator over TCP: changes to CLI/parameter logic are tested without hardware; for PID logic — unit tests in `src/test/unit/` (`make test` — gtest), for example `pid_unittest.cc`.
ArduPilot: `Tools/autotest/sim_vehicle.py -v ArduCopter --console --map` builds and runs SITL; patch → rebuild → flight in SITL → log; autotests `Tools/autotest/arducopter.py` (`./Tools/autotest/autotest.py build.Copter test.Copter.<Test>`).

A minimal change for the lab (safe, verifiable): add a GCS message/log field (ArduPilot `gcs().send_text(MAV_SEVERITY_INFO, ...)` on an event; Betaflight — a new `DEBUG_` mode with its own value) or change a parameter's limit/default value and see the effect in SITL.

## practice
### Step 1. Call map
For one firmware — a list of files and functions along the gyro → filters → PID → mixer → output path with links (path + line/function on current master). For the other — files only.

### Step 2. Checking against theory
Answer from the code, with quotes: where does D come from (the error or the gyro)? Where is the anti-windup? In what order are the gyro filters applied? How is the mixer output limited under saturation?

### Step 3. Patch
Pick a minimal change; a branch; a SITL build; verification (a message in the console / a field in the log / behavior); `git diff` into the report.

### Step 4. Report
One page: the map, the answers to the theory check, the diff, how it was tested, what did not work.

### How to search the code instead of scrolling
- `git grep -n "pidController\|mixTable" src/main/flight/` (Betaflight) or `git grep -n "rate_controller_run" ArduCopter libraries/AC_AttitudeControl` (ArduPilot) finds the entry points faster than any table of contents.
- Links in the report point to a specific commit, not to `master`: `https://github.com/<org>/<repo>/blob/<sha>/<path>#L<n>`. In a month `master` will have moved on, but the commit link stays correct.
- Answer the question “where does D come from” with a quote from the code: is it the error (setpoint minus gyro) that gets differentiated, or only the gyro. That determines whether the aircraft jerks on a sharp stick movement.

### Example of a minimal patch
The safest patch is a startup message or a new log field. It changes nothing in control, but it proves that your build really is the one running. ArduPilot: the line `gcs().send_text(MAV_SEVERITY_INFO, "my build: hello");` in the Copter initialization, build with `./waf configure --board sitl && ./waf copter`, run SITL. The message shows up in the MAVProxy console. Betaflight: build with `make TARGET=SITL`, your own line in the startup output.

### What you should get and what to record
- Call map: 6–10 lines of “file → function → what it does”, in the order the data flows from the gyro to the output.
- Answers to the four theory-check questions, each with a code quote (2–5 lines) and a link to the commit.
- The patch's `git diff` (usually 1–10 lines), the build command, proof that it works: a line from the console or a field from the log.
- What did not work is an honest item in the report, not a failure.

The lab counts as done when the gyro → PID → mixer path is found in the code with links to files and a commit, the minimal patch is built and tested in SITL with proof from the console or the log, and the report contains the map, the answers to the theory check and the diff.

## diagnostics
- **Symptom:** I can't find where a parameter is used
  - Possible cause: the name in the code differs from the name in the GUI (Betaflight: `pidProfile()->pid[PID_ROLL].D`; ArduPilot: `_pid_rate_roll` from `ATC_RAT_RLL_*`).
  - What to do: search by `@Param`/`PG_REGISTER`/`parameter_names.h`, then by the struct field.
- **Symptom:** the SITL build fails
  - Possible cause: wrong dependencies/toolchain.
  - What to do: `Tools/environment_install/install-prereqs-ubuntu.sh` (ArduPilot), `make arm_sdk_install`/`make SITL` per the Betaflight README.
- **Symptom:** the patch does not affect behavior in SITL
  - Possible cause: you changed the wrong path (a different controller/mode), or the value is overridden by a parameter.
  - What to do: `printf`/send_text at the point of change, check that the code actually executes.
- **Symptom:** “the theory doesn't match” the code
  - Possible cause: that is normal — scaling, filters, order of operations; sometimes it is a bug.
  - What to do: record the discrepancy in the report with a quote; if you suspect a bug — an issue with a reproduction in SITL.

## references
- Betaflight — source tree (src/main) | https://github.com/betaflight/betaflight/tree/master/src/main | primary | A
- ArduPilot — ArduCopter scheduler and attitude control sources | https://github.com/ArduPilot/ardupilot/tree/master/ArduCopter | primary | A
- ArduPilot — Developer docs: SITL setup and autotest | https://ardupilot.org/dev/docs/sitl-simulator-software-in-the-loop.html | primary | A

## checklist
- I found the gyro → PID → mixer path in Betaflight and ArduPilot, with files
- I checked the D-term and anti-windup implementation against theory in the code
- I know the gyro filter order from the code, not from the wiki
- I built SITL and tested a minimal patch
- The report with the diff and links is ready
