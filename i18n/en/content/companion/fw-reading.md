---
id: fw-reading
title: "How to read firmware source code: Betaflight and ArduPilot"
level: L4
readingTime: 45 min
firmware: Betaflight 2025.12 (checked against 2025.12.5 and 2026.6.2) · ArduPilot 4.7 (checked against 4.7.3)
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
source_hash: 842556a2cf0f
---

## summary
Documentation describes what a parameter "does"; only the code shows what it **actually** does, including the order of operations, the limits and the side effects. This module teaches you to find your way around two large codebases without reading all of them: how to trace the path from the gyro to the motors, where the PID controller and the filters live, how to check the implementation against theory (and spot where they disagree), and how to make a minimal change, build it and test it in SITL without touching a real aircraft. The lab: a patch and a write-up page in your own repository.

## theory
### Tools for reading code
`git clone` + `grep -rn`/`rg` + an editor with go-to-definition (VS Code with clangd, or just `rg "pidController\("`). For C/C++ firmware the main technique is to start at the **scheduler entry point** and follow the calls down, and to go from a **parameter** (its name in the code) to the places where it is used. `git blame`/`git log -S "name"` shows when and why a line was added; the PR discussion often explains more than the wiki.

### Betaflight: the gyro → PID → mixer path
Repository `betaflight/betaflight`, code in `src/main/`:

1. **Scheduler**: `scheduler/scheduler.c` picks tasks from the table in `fc/tasks.c`. The task `TASK_GYRO` (`taskGyroSample`) and `TASK_FILTER`/`TASK_PID` (`taskMainPidLoop` in `fc/core.c`).
2. **Gyro**: `sensors/gyro.c`: `gyroUpdate()` reads the driver (`drivers/accgyro/accgyro_spi_icm426xx.c` and others, via DMA), and LPF2 (`common/filter.c`: PT1/PT2/PT3/biquad) is applied while still at the gyro sample rate; then `gyroFiltering()` (`sensors/gyro_filter_impl.c`) applies the chain: RPM notch (`flight/rpm_filter.c`), static notches 1 and 2, LPF1 and, last, the dynamic notch (`flight/dyn_notch_filter.c`). The filter order is defined right here, and you cannot tell it from the Configurator.
3. **PID**: `flight/pid.c`, `pidController()`: for each axis error = setpoint − gyro, P, I with anti-windup and iterm_relax, D on the filtered gyro (D-term LPF, D max: `d_max_*` in 2025.12, `d_min_*` in 4.5), feedforward (`flight/pid_init.c`, `fc/rc.c`: FF is computed from the setpoint derivative with interpolation/smoothing), TPA, anti-gravity, and `pidSum` in `pidData[axis].Sum`.
4. **Mixer**: `flight/mixer.c`, `mixTable()`: per-axis pidSum × the mixer matrix (`mixer_init.c`/`mixer_tricopter.c`) + throttle → motors, `airmode`, limiting (`mixer_type`: LEGACY/LINEAR/DYNAMIC/EZLANDING), idle (`motor_idle`; before 2025.12, `dshot_idle_value`), `motorOutputLimit`.
5. **Output**: `drivers/dshot.c` (frame encoding), `drivers/pwm_output.c`; the platform part on current master is `src/platform/STM32/dshot_bitbang.c`, `src/platform/common/stm32/dshot_dpwm.c` and `pwm_output_dshot_shared.c`, which generate DShot frames with a timer + DMA; bidirectional DShot eRPM decoding is in `drivers/dshot_bitbang_decode.c` (in 4.5, `dshot_dpwm.c` lived in `src/main/drivers/`).
6. **Blackbox**: `blackbox/blackbox.c`: what gets logged and how (the field table `blackboxMainFields[]` is in the same file).

Checking against theory: in `pid.c`, find how D is computed: `-(gyroRateDterm[axis] - previousGyroRateDterm[axis]) * pidFrequency`, where `gyroRateDterm` is the gyro already passed through the D-term notch and D-term LPF1/LPF2 (the filters come before the differentiation), then multiplied by `pidCoefficient[axis].Kd` and `dMinFactor` (in 4.5; `dMaxMultiplier` from 2025.12). D is taken from the **gyro**, not from the error (so there is no "derivative kick" when the stick moves), and the gain scaling is a set of constants in `pid.h` applied in `pid_init.c` (`PTERM_SCALE`, `ITERM_SCALE`, `DTERM_SCALE`: this is where the "dimensionless" values in the Configurator come from).

### ArduPilot: the IMU → rate → motors path
Repository `ArduPilot/ardupilot`, vehicle code in `ArduCopter/`, libraries in `libraries/`:

{{diagram:ardupilot-fast-loop|The ArduCopter fast loop: the tasks the scheduler calls on every tick, and the slower tasks with their own rates.}}

1. **Scheduler**: `ArduCopter/Copter.cpp`, the `scheduler_tasks[]` table: `FAST_TASK_CLASS(AP_InertialSensor, &copter.ins, update)` → `FAST_TASK(run_rate_controller_main)` → `FAST_TASK(motors_output_main)` → `FAST_TASK(read_AHRS)` → … → `FAST_TASK(update_flight_mode)`; slower tasks such as `SCHED_TASK(rc_loop, 250, 130, 3)` with a rate, a time budget (µs) and a priority. Newer versions can run a dedicated rate thread (`ArduCopter/rate_thread.cpp`, `FSTRATE_ENABLE`) at the gyro rate.
2. **IMU and filters**: `libraries/AP_InertialSensor/`: `AP_InertialSensor.cpp` (`update()`), the backend drivers (`AP_InertialSensor_Invensensev3.cpp`), the harmonic notch `libraries/Filter/HarmonicNotchFilter.cpp`, the LPF `Filter/LowPassFilter2p.cpp`.
3. **Rate loop**: `ArduCopter/Attitude.cpp`: `run_rate_controller_main()` → `attitude_control->rate_controller_run()` in `libraries/AC_AttitudeControl/AC_AttitudeControl_Multi.cpp`: for each axis `_motors.set_roll(get_rate_roll_pid().update_all(target, gyro, dt, _motors.limit.roll, …))` in `libraries/AC_PID/AC_PID.cpp` (P, I with limit, D with the `FLTD` filter, FF, the error through `FLTE`, the target through `FLTT`) → `_motors.set_roll(...)`.
4. **Angle loop**: `AC_AttitudeControl.cpp`: `input_euler_angle_roll_pitch_euler_rate_yaw_rad()` and others → quaternion attitude error → `rate_target_ang_vel` with `ATC_ANG_*_P` and the acceleration limits (`ATC_ACC_*_MAX`, before 4.7 `ATC_ACCEL_*_MAX`): this is the input shaping implementation.
5. **Motors**: `ArduCopter/motors.cpp` `motors_output_main()` → `libraries/AP_Motors/AP_MotorsMulticopter.cpp` `output()` (throttle filter, lift_max from battery voltage, spool logic) → `AP_MotorsMatrix.cpp` `output_armed_stabilizing()` (mixing roll/pitch/yaw/throttle through the matrix with priorities and `MOT_YAW_HEADROOM`) → `output_to_motors()` → `SRV_Channel`/`AP_HAL` RCOutput (DShot/PWM).
6. **EKF**: `libraries/AP_NavEKF3/`: `AP_NavEKF3_core.cpp` (`UpdateFilter`), one file per measurement type (`*_PosVelFusion.cpp`, `*_MagFusion.cpp`, `*_OptFlowFusion.cpp`), sources in `AP_NavEKF/AP_NavEKF_Source.cpp`.
7. **Parameters**: `ArduCopter/Parameters.cpp` and the `*_Params.cpp` files in the libraries: the `// @Param:` blocks with description, range and `@Values` are what the parameter wiki is generated from.

Checking against theory: in `AC_PID::update_all()`, see that D is the derivative of the error (already smoothed by `FLTE`), passed through the `FLTD` filter, not the derivative of the raw gyro; that I is limited by `IMAX` and does not accumulate while `limit` is set (motor saturation): that is the anti-windup; in `AP_MotorsMatrix::output_armed_stabilizing()`, the order: roll/pitch first, then as much yaw as fits (`MOT_YAW_HEADROOM` is the guaranteed minimum), and only then the throttle that fits into the remaining range.

{{diagram:fw-gyro-motor-paths|The same gyro → motors path in the two codebases, with a file for each step; the PID is highlighted: D from the gyro in Betaflight and from the error through FLTD in ArduPilot.}}

### A minimal patch and SITL
Betaflight: `make SITL` builds the firmware for Linux (`obj/main/betaflight_SITL.elf`), which talks to a simulator (RealFlight/gazebo over UDP) or simply lets you connect the Configurator over TCP: changes to CLI/parameter logic can be checked without hardware; for PID logic there are unit tests in `src/test/unit/` (`make test`, gtest), for example `pid_unittest.cc`.
ArduPilot: `Tools/autotest/sim_vehicle.py -v ArduCopter --console --map` builds and starts SITL; patch → rebuild → SITL flight → log; autotests in `Tools/autotest/arducopter.py` (`./Tools/autotest/autotest.py build.Copter test.Copter.<Test>`).

A minimal change for the lab (safe and testable): add a GCS message or a log field (ArduPilot: `gcs().send_text(MAV_SEVERITY_INFO, ...)` on an event; Betaflight: a new `DEBUG_` mode with your own value), or change a parameter limit or default and see the effect in SITL.

### Where it fits

- **Takes in:** the model of the scheduler, interrupts and DMA (`emb-basics`); the theory you check the code against (`ctl-theory`); SITL to test the patch (`ap-sitl`).
- **Hands off:** the filter order and where the D term sits in the code, to tuning (`bf-filters`, `ap-tuning`); the mixer logic and axis priority, to control allocation (`ctl-allocation`); the groundwork for your own build (`bf-custom`).
- **If you get this wrong:** the conclusion "D is computed from the gyro" carried over from Betaflight to ArduPilot, where D comes from the error through `FLTD` → you misread what the filters do while tuning (`ap-tuning`). A patch checked only by building it, without a SITL flight → the regression shows up in the air; an autotest on every PR is covered in `eng-ci-configs`.

## practice
### Step 1. Call map
For one firmware: the list of files and functions on the path gyro → filters → PID → mixer → output, with references (path + line/function on current master). For the other: files only.

### Step 2. Checking against theory
Answer from the code, with quotes: where does D come from (the error or the gyro)? where is the anti-windup? in what order are the gyro filters applied? how is the mixer output limited at saturation?

### Step 3. Patch
Pick a minimal change; a branch; a SITL build; a check (a console message / a log field / the behavior); `git diff` goes onto the write-up page.

### Step 4. Write-up page
A page in your own repository, written for yourself six months from now: the map, the answers to the theory check, the diff, how you tested it, what did not work.

### How to search the code instead of scrolling through it
- `git grep -n "pidController\|mixTable" src/main/flight/` (Betaflight) or `git grep -n "rate_controller_run" ArduCopter libraries/AC_AttitudeControl` (ArduPilot) finds the entry points faster than any table of contents.
- The links on the write-up page point to a specific commit, not to `master`: `https://github.com/<org>/<repo>/blob/<sha>/<path>#L<n>`. In a month `master` will have moved on, but the commit link will still be right.
- Answer "where does D come from" with a quote from the code: is the error (setpoint minus gyro) differentiated, or only the gyro? That decides whether the aircraft jerks on a sharp stick movement.

### An example of a minimal patch
The safest patch is a message at startup or a new log field. It changes nothing in the control path, but it proves that the build you are running really is yours. ArduPilot: the line `gcs().send_text(MAV_SEVERITY_INFO, "my build: hello");` in the Copter initialization, build with `./waf configure --board sitl && ./waf copter`, start SITL. The message shows up in the MAVProxy console. Betaflight: build with `make TARGET=SITL`, your own line in the startup output.

### What you should end up with and what to record
- The call map: 6–10 lines of "file → function → what it does", in the order the data flows from the gyro to the output.
- Answers to the four theory-check questions, each with a code quote (2–5 lines) and a commit link.
- The patch's `git diff` (usually 1–10 lines), the build command, and proof that it works: a console line or a log field.
- What did not work: an honest item on the write-up page, not a failure.

Self-check: the lab is done when the gyro → PID → mixer path has been found in the code with links to files and a commit, the minimal patch has been built and tested in SITL with proof from the console or the log, and the write-up page in your repository contains a 6–10 line map, the four theory-check answers with code quotes, and the diff.

**Reference answer for self-check.** Compare your theory-check answers with the walkthrough in the theory section. Betaflight: D is computed from the gyro that has already gone through the D-term notch and D-term LPF (`gyroRateDterm` in `pid.c`), not from the error; the gyro filter order: LPF2 still at the gyro rate in `gyroUpdate()`, then in `gyroFiltering()` (`sensors/gyro_filter_impl.c`): RPM notch, static notches 1 and 2, LPF1 and, last, the dynamic notch. ArduPilot: in `AC_PID::update_all()` D comes from the error through `FLTD`, I is limited by `IMAX` and does not accumulate while `limit` is set: that is the anti-windup; in `AP_MotorsMatrix::output_armed_stabilizing()` at saturation roll/pitch come first, then as much yaw as fits, and only then throttle. Common mistake #1: the conclusion "D from the gyro" carried over from Betaflight to ArduPilot. Common mistake #2: an answer without a code quote and a commit link; that is a retelling of the wiki with nothing to check it against. The patch is verified if your line shows up in the MAVProxy console when SITL starts; if it does not, you are running the wrong build.

## diagnostics
- **Symptom:** I cannot find where a parameter is used
  - Possible cause: the name in the code differs from the name in the GUI (Betaflight: `pidProfile()->pid[PID_ROLL].D`; ArduPilot: `_pid_rate_roll` from `ATC_RAT_RLL_*`).
  - What to do: search for `@Param`/`PG_REGISTER`/`parameter_names.h`, then for the struct field.
- **Symptom:** the SITL build fails
  - Possible cause: wrong dependencies/toolchain.
  - What to do: `Tools/environment_install/install-prereqs-ubuntu.sh` (ArduPilot), `make arm_sdk_install`/`make SITL` per the Betaflight README.
- **Symptom:** the patch has no effect on behavior in SITL
  - Possible cause: you changed the wrong path (another controller/mode), or a parameter overrides the value.
  - What to do: a `printf`/send_text at the point of the change, to confirm the code actually runs.
- **Symptom:** "the theory does not match" the code
  - Possible cause: that is normal: scaling, filters, order of operations; occasionally a bug.
  - What to do: record the discrepancy on the write-up page with a quote; if you suspect a bug, open an issue with a SITL reproduction.

## references
- Betaflight — source tree (src/main) | https://github.com/betaflight/betaflight/tree/master/src/main | primary | A
- ArduPilot — ArduCopter scheduler and attitude control sources | https://github.com/ArduPilot/ardupilot/tree/master/ArduCopter | primary | A
- ArduPilot — Developer docs: SITL setup and autotest | https://ardupilot.org/dev/docs/sitl-simulator-software-in-the-loop.html | primary | A

## checklist
- I found the gyro → PID → mixer path in Betaflight and ArduPilot, with files
- I checked the D-term and anti-windup implementation against theory in the code
- I know the gyro filter order from the code, not from the wiki
- I built SITL and tested a minimal patch
- The write-up page with the diff and links is in my repository
