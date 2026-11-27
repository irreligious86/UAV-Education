---
id: f-esc-firmware
title: "ESC Firmware: Bluejay, AM32, BLHeli_32 and ESC Setup"
level: L2
readingTime: 40 min
firmware: Betaflight 2025.12 (checked against 2025.12.5; beacon — per 4.5.3) · ArduPilot 4.5+ · Bluejay 0.21 · AM32 2.22
status: published
tags:
  - ESC
  - Bluejay
  - AM32
  - DShot
related:
  - f-motors-esc
  - bf-rpm-filter
  - bf-filters
  - bf-blackbox
  - bf-led-buzzer
next:
  - bf-rpm-filter
source: content/foundation/f-esc-firmware.md
source_hash: ec36721b9533
---

## summary
An electronic speed controller is a separate computer with its own firmware, and the RPM filter, the sound of the motors, heating and even whether a motor will start after a crash all depend on it. The “Motors and ESCs” module explained what an ESC does; here — which firmware to put on which hardware, what bidirectional DShot and EDT are, which ESC settings really change the flight (PWM frequency, timing, demagnetization, startup power), how to flash through the flight controller in Betaflight and ArduPilot, and how not to turn a 4-in-1 into a brick.

## theory
### Who is who
| Firmware | Hardware | Status | What matters |
|---|---|---|---|
| BLHeli_S | 8-bit EFM8 (BB1/BB2/BB21) | factory firmware on cheap ESCs, not developed | no bidirectional DShot in its original form |
| Bluejay | 8-bit EFM8 BB21 and BB51 (BB1/BB10 — only up to version 0.18.1) | open source, developed | bidirectional DShot, EDT, PWM frequency 24/48/96 kHz, startup tunes |
| BLHeli_32 | 32-bit ARM | closed; development and support ended in 2024 | works, but there will be no updates and no new configurator |
| AM32 | 32-bit ARM (STM32F051, G071, AT32F421, GD32 and others) | open source, developed | the replacement for BLHeli_32 where there is a target for the board |

The firmware name on the box tells you about the ESC's microcontroller: “BLHeli_S” — 8 bit, “BLHeli_32” or “AM32” — ARM.

### Bidirectional DShot and EDT
- **DShot** — a digital command protocol from the flight controller → ESC: DShot300/600 — the speed in kbit/s; no throttle range calibration, with a checksum.
- **Bidirectional DShot (bidir)** — over the same wire the ESC replies with the electrical RPM (eRPM). This is the input of the Betaflight RPM filter and the ArduPilot harmonic notch. Mechanical RPM = eRPM / (number of poles / 2), so the motor's number of poles (usually 14 for 22xx–28xx) must be set in the flight controller.
- **EDT (Extended DShot Telemetry)** — the same replies additionally carry the ESC's temperature, voltage, current and status — without a separate telemetry wire. Supported by Bluejay and AM32; enabled in the flight controller.

{{lesson:bf-rpm-filter|What Betaflight does with eRPM: notches on the harmonics, the lower limit `rpm_filter_min_hz` for large props, and diagnosing telemetry errors.}}

### Settings that change the flight
- **PWM frequency.** Lower (24 kHz) — more thrust and braking at low throttle, cooler ESC switches; higher (48–96 kHz) — smoother current in a low-inductance motor, a softer sound and less vibration. The smaller the motor and the higher its RPM, the higher the frequency needed. The selection rule, a table by class and the calculation — in the subsection “PWM frequency: how to choose for the aircraft” below.
- **Timing (advance).** The commutation advance angle. Higher — more RPM and current, heating; lower — more efficient, but a risk of losing sync on a sharp throttle input. Auto/medium is a sensible start.
- **Demagnetization (demag compensation).** Protection against losing sync on sharp throttle changes with large motors. Sync losses (“desyncs”) — a motor twitches or stops in flight — are treated first of all by raising the compensation.
- **Startup power (startup/rampup power).** Too high — the windings burn if the motor is jammed; too low — a heavy motor won't start.
- **Spin direction.** Changed in the ESC firmware or with a DShot command from the flight controller — no need to resolder wires.
- **Tunes and beacon.** The “lost aircraft” sound after a crash is a useful feature, not a toy.

### PWM frequency: how to choose for the aircraft
An ESC does not change the voltage on the winding smoothly but with switches: in a period T = 1/f the phase is connected to the battery for a fraction D of the period (the duty cycle), and for the rest of the time it is connected to ground. The average voltage on the motor is D·U. The frequency f of these switchings is the PWM frequency. It does not affect throttle; it determines how smooth the current will be and how much the ESC pays for it.

**The rule.** The PWM frequency must be high enough for the current in the winding to be smooth at hover RPM, and no higher than that. A small motor with a high KV (few turns — low inductance, high RPM) needs a high frequency. A large low-KV motor is smooth already at a low frequency, and its ESC, with a high current and voltage, pays more than anyone for every switching. Hence the direction: the smaller the aircraft, the higher the frequency; the bigger and heavier, the lower.

The four mechanisms this follows from:

| Mechanism | Formula | What follows from it |
|---|---|---|
| Current ripple in the winding (the winding is an R–L load) | peak-to-peak ΔI ≈ U·D·(1 − D)/(L·f); the addition to copper losses ≈ ΔI²/(12·I²) of I²·R | torque is produced by the average current I, but heating by the RMS current; the lower L, the more “extra” motor heating at a low frequency; doubling f reduces the addition fourfold |
| Switching losses in the switches | P ≈ ½·U·I·t_sw·f per switch (t_sw — the MOSFET transition time) | grow in proportion to f and to the product U·I: at 1S and 2 A it is milliwatts, at 6S and 40 A — watts |
| Dead time (the pause between the half-bridge switches) | fraction of the period = t_d·f | by this fraction the actual voltage is lower than commanded when driving and higher when braking: both thrust and braking at low throttle weaken as f grows |
| The number of PWM periods per commutation step | N = 10·f/eRPM (f in Hz) | at N around 1–2 the duty cycle “doesn't have time” to take effect within a step: jerky torque, beating, a rough sound |

The ripple formula is the triangular approximation; it holds when T is much less than L/R. For the smallest motors this condition is violated at 24 kHz, and the formula gives an upper estimate. L and R here are between two phase wires.

Throttle resolution also depends on the frequency. In Bluejay the PWM counter has 1024 steps at 24 kHz, 512 at 48 kHz and 256 at 96 kHz (in builds with dead time greater than 0, i.e. with center-aligned PWM; with dead time 0 — twice as many), and the dead time is subtracted from them. In AM32 the PWM timer counts at the processor frequency (on a 48 MHz MCU — 2000 counts at 24 kHz, 500 at 96 kHz), and this effect is weaker.

**What changes in each direction.** The word “response” in descriptions of the PWM frequency means two different things, which is why the advice “higher — better response” and “higher — sluggish response” both circulate at the same time. Precisely:

| Property | Lower frequency (24 kHz) | Higher frequency (48–96 kHz) | Source |
|---|---|---|---|
| Thrust and controllability at low throttle | more: the dead time eats less, more throttle steps | less: a “sluggish bottom end”, the motors find it harder to start | Bluejay wiki (FAQ, Concepts) |
| Motor braking (active braking, damped light) | stronger — a sharper stop after a flip, better in prop wash | weaker | BLHeli_32 manual; Oscar Liang |
| Acceleration | does not depend on the frequency | does not depend | Oscar Liang |
| Current smoothness, sound, vibration | rougher; growling on small motors | smoother and quieter, less noise in the gyro | BLHeli_32 manual; Oscar Liang |
| Heating of a small motor | higher (ripple) | lower | the ripple formula |
| ESC heating | lower | higher | the switching loss formula |
| Flight time | on large motors — no worse | on small motors it grows at 24 → 48 kHz; 48 → 96 kHz — the gain is “minuscule” | Bluejay wiki (FAQ, Migrating) |

The bottom line: a high frequency improves smoothness, a low one — the sharpness of braking and the thrust at low throttle. “Response” in the sense of “the motor brakes quickly and holds the bottom of the throttle” is better at a low frequency.

**The starting value by aircraft class.** The recommendations in the “Start” column are community practice, not physics: the sources disagree, and the final word belongs to a check on your own aircraft.

| Class | Start | Why | Status of the number | What to check after a change |
|---|---|---|---|---|
| Whoop 65–75 mm, 1S, 0603–0802 motors | 48 kHz; 96 kHz — only with a dead time in the layout below 30 | low L and the highest RPM of all: at 24 kHz the current is jerky; at 96 kHz 256 steps minus the dead time remain | Bluejay FAQ: 48 kHz — the longest flight time, the gain from 96 is “minuscule”; Oscar Liang advises 96 in one article and 48 in another | all motors start on every arming; min/max startup power and `motor_idle`; flight time |
| 2–3.5" (toothpick, cinewhoop), 2–4S | 48 kHz | intermediate L and RPM | Oscar Liang: 48 kHz for intermediate sizes | motor and ESC temperature, jitter at low throttle |
| 5" freestyle / racing, 4–6S | freestyle 48 kHz, racing 24 kHz; AM32 — 24 kHz with variable frequency | freestyle values smoothness and a clean gyro, racing — braking and the bottom of the throttle | Oscar Liang (articles on BLHeli_32 and Bluejay) | prop wash, oscillations at low throttle, motor temperature |
| 7" long range, 6S | 24 kHz or variable 24–48 kHz; 48 kHz is acceptable on Bluejay | hover at 110–130 Hz (the 7" LR from the `bf-rpm-filter` example; the whole 7" class — 110–200 Hz, `f-frame-mech`) is about 50,000 eRPM: at 24 kHz N ≈ 4.8, there is already margin | Oscar Liang: Bluejay — 48, BLHeli_32 — low 24 and “By RPM”; the N number — a calculation | hover current, ESC temperature, interference in the video |
| 10" and larger, heavy lift, X8, low-KV motors | 24 kHz, fixed | high L, high U·I: the ripple is small, while the switching losses are the highest | an estimate: there is no source with a number for this class; Oscar Liang does not recommend AM32 below 16 kHz — the current grows | ESC temperature under full load, desync on a sharp throttle input, N in hover |
| Plane (one or two motors) | 24 kHz | throttle changes slowly, motor braking is not needed, the ESC works at a high current for a long time | an estimate | ESC temperature in a climb, a confident motor start |
| A constraint for any class: a DJI O3/O4 on board, footage stabilized in Gyroflow | 48 kHz and higher, even if the class gives 24 | per the Gyroflow documentation, the default 24 kHz PWM interferes with the module's IMU sampling rate, and the gyro data in the file gets corrupted; 48 kHz and higher avoid this | Gyroflow docs, DJI (O3/O4 Air Unit); the same source — a soft camera mount or Optical correction | after Gyroflow there is no “jello” or shaking from the module's gyro; then — as per the class: ESC temperature, the bottom of the throttle (`per-fpv-footage`) |

{{diagram:esc-pwm-class-map|The smaller the aircraft, the higher the starting frequency; a DJI O3/O4 with Gyroflow moves all classes that start at 24 kHz to 48, and the final value is checked by N = 10·f/eRPM in hover.}}

**The selection procedure for any aircraft.**
1. Take the starting value for the class.
2. Read the eRPM in hover (the Motors tab, the OSD or the log) and calculate N = 10·f/eRPM. Guideline: N around 3–5 and above (an estimate; AM32's automatic mode keeps about 4.6 periods per step, and the BLHeli_32 manual calls 48 kHz sufficient up to about 100,000 eRPM — that is 4.8). N below 3 — an argument for raising the frequency one step. N above 10 with a hot ESC — an argument for lowering it.
3. Fly and watch the symptoms:

| Symptom | Which way to move | Why |
|---|---|---|
| Growling, a rough sound, oscillations at mid throttle, motor noise in the gyro | up | too few periods per step, large ripple |
| Small motors hot with a cold ESC | up | additional copper losses from the ripple |
| Motors start only every other time, stutter, desync, even though startup power is already at maximum | down | the dead time has eaten the low throttle (Bluejay FAQ: with a dead time of 30 and above — lower the frequency) |
| A sluggish bottom end, worse prop wash, the aircraft “sinks” after chopping throttle | down | weaker braking and thrust at low throttle |
| The ESC is hot, the thermal protection triggers | down | switching losses |

4. Adjust the related settings:
- **Startup power (Bluejay: min/max startup power; BLHeli_32: rampup power).** After raising the frequency, 1–2S motors may stop starting — raise it in steps until the start is confident, no higher: an excessive value removes the protection of the windings if the motor is jammed.
- **`motor_idle` and `dyn_idle_min_rpm` (Betaflight).** At a higher frequency the same throttle gives less voltage — find the minimum stable idle again on the Motors tab and take a little above it.
- **`thrust_linear` (Betaflight).** Adds throttle at low RPM: the motor command becomes x · (1 + k·(1 − x)²), x — throttle plus the PID correction (the linearization input, not the final output), k = `thrust_linear`/100 (Betaflight 4.5.3, `pid.c`, `mixer.c`). It cures a sluggish bottom end at 48–96 kHz; after going back to 24 kHz — reduce it or set it to zero.
- **Timing and demagnetization.** They do not depend directly on the PWM frequency; change them only if desyncs appeared after changing the frequency.
- **RPM filter.** Its settings do not change: eRPM is counted from commutation, not from PWM. Check after a change — DShot errors no higher than 1 % (course guideline, `bf-rpm-filter`; usually about 0) and the noise spectrum in Blackbox.
- **PID.** After changing the frequency check low throttle and prop wash; with a variable frequency some retuning may be needed.

**What the firmware can do.**

| Firmware | PWM frequency | Variable frequency | Source |
|---|---|---|---|
| BLHeli_S | always 24 kHz | no | BLHeli_S manual Rev16.x |
| Bluejay 0.21 | 24, 48 or 96 kHz; set at build time — a separate hex for each frequency, changing the frequency = reflashing | no: in the 0.21 description the authors call their experiments with a dynamic frequency “not entirely satisfactory”, and the 96 kHz mode “practically useless” | source v0.21.0 (`PWM_FREQ`), release notes, wiki |
| AM32 2.x | 8–144 kHz in 1 kHz steps, default 24 | `variable_pwm` = 1: from the set f to 2·f — f up to about 100,000 eRPM, 2·f above about 208,000 eRPM; = 2: automatic, about 27–29 periods per electrical revolution within about 36–96 kHz | source v2.22 (`main.c`, DroneCAN parameters); the limits — calculated from the code |
| BLHeli_32 | the range is set by the ESC manufacturer (per Oscar Liang — from 16 to 128 kHz) | from 32.8 — a low and a high frequency, rising with throttle; from 32.9 — “By RPM” (set the high one to maximum); disabled in sine mode | BLHeli_32 manual Rev32.x |

**Worked example: two motors.** The values of L, current and switching time are illustrative, chosen for the calculation; for your own motors L is measured with an LCR meter between two phases. Motor A, “small”: 1S, U = 4 V, L = 10 µH, hover current 1.5 A. Motor B, “large”: 6S, U = 24 V, L = 50 µH, hover current 8 A. Duty cycle D = 0.5, switch transition time 50 ns.

| Frequency | A: ΔI | A: added copper losses | A: switching losses | B: ΔI | B: added copper losses | B: switching losses |
|---|---|---|---|---|---|---|
| 24 kHz | 4.17 A | 64 % | 0.004 W | 5.00 A | 3.3 % | 0.12 W |
| 48 kHz | 2.08 A | 16 % | 0.007 W | 2.50 A | 0.8 % | 0.23 W |
| 96 kHz | 1.04 A | 4 % | 0.014 W | 1.25 A | 0.2 % | 0.46 W |

Checking one cell: ΔI = 4 · 0.5 · 0.5 / (10·10⁻⁶ · 24,000) = 4.17 A; the addition = 4.17² / (12 · 1.5²) = 0.64. For motor A, going 24 → 48 kHz reduces the copper losses from 1.64 to 1.16 of I²·R, i.e. by 29 %, at the cost of 3 mW in the switches — the gain is obvious. Going 48 → 96 kHz removes another 0.12 of I²·R, but the dead time doubles: for a layout with dead time 30 (30 · 20.4 ns = 0.61 µs) its share grows from 2.9 % to 5.9 % of the period, and 256 throttle steps remain. That is why 48 kHz is a sensible limit for a whoop. For motor B, going 24 → 48 kHz saves 2.5 % of I²·R and adds 0.12 W in the switches. With a winding resistance of tens of mΩ (`f-motors-esc`), for example 50 mΩ, I²·R = 8² · 0.05 = 3.2 W, and 2.5 % of that is 0.08 W: less than was added in the switches, so there is no point in raising the frequency. At full throttle D tends to 1, the ripple disappears, and the switching losses only grow with current.

### Bluejay settings: a table from the source code
The values below are the EEPROM bytes as Bluejay v0.21 (EEPROM layout 208) stores and parses them: the defaults from `Settings/BluejaySettings.asm`, the parsing — `Modules/Settings.asm`, the application — the `Timing`, `Power`, `Scheduler` modules. ESC Configurator shows the same parameters (settings), sometimes in its own units; if a number in the configurator does not match the table — look at the meaning, not the digit. Timing degrees are electrical.

| Setting | Default | Values | What it does per the code | When to change |
|---|---|---|---|---|
| PWM frequency | depends on the hex | 24 / 48 / 96 kHz — three separate builds (`PWM_FREQ` 0/1/2); in EEPROM it is stored only for display | the PWM period and throttle resolution (1024 / 512 / 256 steps with dead time greater than 0; with dead time 0 — 2048 / 1024 / 512) | per the section above; changing = flashing a hex of the same layout, MCU and dead time (hex name: layout_MCU_deadtime_frequency) |
| Startup power min | 21 | 0–255; on the throttle scale 1000 + v·1000/2047 → 1000–1125 | the minimum kick power at startup; each failed start adds another 40/2047 ≈ 2 %, but no more than startup power max | a motor with a heavy prop won't move from rest — raise in steps |
| Startup power max | 5 | 0–255, the firmware clips it to 80; 5/255 ≈ 2 %, 80/255 ≈ 31 % | the power limit during the startup phase and the first acceleration: protection of the windings if the motor jammed after a crash | raise only if the motor does not spin up after the kick; no higher than needed |
| RPM power protection (slope) | 9 | 0 = off, 1–13 (higher is clipped to 13) | at low RPM the power limit grows in proportion to RPM × slope, but not below startup max; twice as strict in the initial acceleration phase | stuttering and stalling at startup of large props — higher; 0 removes the RPM-proportional limit, while the startup power max limit during the startup phase remains |
| Motor timing | 4 = MediumHigh | 1 Low 0°, 2 MediumLow 7.5°, 3 Medium 15°, 4 MediumHigh 22.5°, 5 High 30° | commutation advance; always 3 during the startup phase; with a high demagnetization metric the firmware itself adds +1 step (metric ≥ 130) or +2 (≥ 160), no higher than 5 (outside the high-RPM mode) | lower — with hot motors; higher — with desyncs after demag High |
| Demag compensation | 2 = Low | 1 Disabled, 2 Low, 3 High | the ESC computes a demagnetization metric (120…≈250, a moving average); when the metric is at or above the threshold, it cuts power for that commutation step; threshold Low 160, High 130, Disabled 255 (never triggers) | High — large motors, heavy props, desyncs on a sharp throttle input; the price — a short thrust dip |
| Brake on stop | 0 | 0 off, 1 on | at zero throttle, after ~100 ms it stops running and closes all the low-side switches: the motor brakes and is held; has no effect in bidirectional mode | a copter usually doesn't need it; a plane's folding prop |
| Braking strength | 255 | 0–255 → 0–100 % | the duty cycle limit of the braking (complementary) switch in flight — the strength of active braking when throttle is chopped; 255 = full | throttle chops are too abrupt, the ESC heats up in prop wash — lower |
| Temperature protection | 0 = off | 0 off; 1–7 = 80, 90, 100, 110, 120, 130, 140 °C | at the threshold the power limit drops in steps 78 → 59 → 39 → 20 % every ~4–5 °C; the limit moves toward the setpoint by 1/255 about every 256 ms — down to 78 % in about 14 s, down to 20 % in about 52 s | enable it on a 4-in-1 without airflow; 100–110 °C — course guideline |
| Beep strength | 40 | 0–255 | the volume of service beeps (startup, arming) | to taste |
| Beacon strength | 80 | 0–255 | the volume of the beacon and of beeps on DShot commands 1–5 | louder — easier to find, but the windings heat up more |
| Beacon delay | 4 = 10 min | 1 = 1 min, 2 = 2 min, 3 = 5 min, 4 = 10 min, 5 = never | the ESC's own beacon after that many minutes without throttle, then tone 4 about every 3 s (conditions — below, “ESC beacon and DShot beacon”) | 1–2 min — for searching in the field |
| Startup beep | 1 | 0 a short beep, 1 a tune | the power-up sound | to taste |
| LED control | 0 | a byte, 2 bits per LED: 0 — off, otherwise on | the LEDs on the ESC board, if they exist in the layout | only for such boards |
| Power rating | 2 = 2S+ | 1 = 1S, 2 = 2S+ | on BB21 it selects the ADC reference voltage for the temperature sensor (1S — the internal 1.65 V, 2S+ — the 3.3 V supply); on BB51 always the “1S” path | 1S — only on 1S whoops; a wrong value distorts the temperature — both the protection and EDT lie |
| EDT safety arm | 0 | 0 off, 1 on | the motor does not start until the flight controller has sent DShot command 13 (EDT enable); otherwise the ESC beeps a refusal. The flag is reset on every normal motor stop (except in the turtle mode after a crash) | enable only if the flight controller enables EDT: Betaflight `dshot_edt = ON` and a working bidir DShot |
| Direction | 1 | 1 Normal, 2 Reversed, 3 Bidir, 4 Bidir rev | 3/4 — bidirectional mode (3D) | the direction is easier to change with a command from the flight controller |

**EDT in Bluejay** is enabled not by an ESC setting but by command 13 from the flight controller; command 14 disables it. Betaflight 4.5.3 sends command 13 to all motors on every arming attempt if `dshot_edt = ON` (OFF by default), DShot telemetry is enabled (`dshot_bidir`) and there is no separate ESC telemetry wire (`fc/core.c`). So EDT safety arm with `dshot_edt = OFF` gives an aircraft that arms, but whose motors don't spin. One more consequence (the course's conclusion from the code): if the flight controller sends DShot 0 while armed — for example, MOTOR_STOP is enabled — a motor with EDT arming (Bluejay, or AM32 with `input_type` = 4) will not start after stopping until the next arming; with such settings, do not enable EDT arming.

### AM32 settings: a table from the source code
AM32 2.22 stores 192 bytes of settings (`Inc/eeprom.h`) and converts them into working values in `loadEEpromSettings()` (`Src/main.c`). The defaults — from the EEPROM image that the configurator writes (in the source code it is duplicated by the `default_settings[]` array in `Src/DroneCAN/DroneCAN.c`, according to the comment — the 2.19 defaults); the limits — from the checks in `loadEEpromSettings()` and the DroneCAN parameter table. The defaults column of that table applies only to builds for CAN ESCs. Read the current values of your own ESC rather than relying on the table. The scale matters: the number in EEPROM is not the one in degrees or amps.

| Byte / setting | Default | Values and scale | What it does | When to change |
|---|---|---|---|---|
| `pwm_frequency` | 24 | 8–144 kHz, step 1; out of range — the target's frequency | the PWM frequency | per the section “PWM frequency” |
| `variable_pwm` | 1 | 0 — fixed; 1 — from f to 2·f by RPM; 2 — automatic | variable frequency | 0 for comparing frequencies in flight |
| `advance_level` (timing) | 26 → 15° | byte 10–42: angle = (byte − 10)·0.9375° → 0–30°; the old format 0–3 = 0 / 7.5 / 15 / 22.5°; in DroneCAN `ADVANCE_LEVEL` 0–30 without the offset of 10 | advance: the wait after the EMF zero crossing = 30° − angle; on the recovery step after demagnetization the advance is forced to 30° (wait 0). A byte outside 10–42 (except the old 0–3) → 15° | as with Bluejay: lower with hot motors, higher with desyncs |
| `auto_advance` | 0 | 0/1 | angle by duty cycle: 13–23 units → 12.2–21.6° at a duty cycle of 5–100 % | instead of a manual angle, if you don't want to tune it |
| `startup_power` | 100 | 50–150, in counts out of 2000 → +2.5…7.5 % to the minimum duty cycle | the strength of the startup kick | large props won't start — higher |
| `motor_kv` | 55 → 2220 KV | byte·40 + 20 → 20–10,220 KV | the thresholds of the power limit at low RPM: below the lower threshold the duty cycle is no more than 400 out of 2000 (20 %), toward the upper one it grows to 100 % | set the motor's real KV |
| `motor_poles` | 14 | 2–64 | the same thresholds and the sine start | the real number of magnets |
| `comp_pwm` | 1 | 0/1 | complementary PWM: active braking in flight; without it the sine start is disabled | leave at 1 |
| `brake_on_stop` | 0 | 0 off; 1 — a brake with strength `drag_brake_strength` 1–10 (×10 %, 10 = full); 2 — active hold with the duty cycle `active_brake_power` 0–5 (0.5 % per unit: 0–2.5 % plus dead time; default 2), only while armed | what the motor does after stopping | for a copter — 0 |
| `driving_brake_strength` | 10 | 1–10; below 10 it adds a dead time of 150 − 10·v counts | weaker braking when throttle is chopped in flight | the ESC heats up on throttle chops — 7–9, course guideline |
| `demag_comp` | 0 | 0 off; 1 — coasting to the EMF zero only; 2 / 3 / 4 — reducing power by 1/32, 1/16, 1/8 per step after recovery | catches a missed EMF zero crossing (waits 1.25 intervals) and restores synchronization | desyncs — 2, then higher |
| `limits.temperature` | 141 = off | 70–140 °C; out of range — off | above the threshold the duty cycle limit is immediately ≈ 25 %, and by threshold + 10 °C it goes to zero | enable with margin: triggering almost shuts the motor off |
| `limits.current` | 102 = off | byte 1–100 → a limit of 2·byte A (2–200 A) | a 1 kHz current PID reduces the duty cycle | on a weak ESC or with a battery current limit |
| `low_voltage_cut_off` | 0 | 0 off; 1 — per cell; 2 — absolute | a voltage cutoff after ~10 s below the threshold; cleared only by reconnecting power | for a copter with a flight controller — 0, the flight controller watches the battery |
| `low_cell_volt_cutoff` | 50 → 3.00 V | byte 0–100 → 2.50–3.50 V per cell (byte + 250, in units of 10 mV) | the cell count is calculated when the ESC arms: voltage / 3.70 V, with the fractional part discarded | with mode 1, arm only with a charged battery |
| `absolute_voltage_cutoff` | 10 → 5 V | 1–100 → 0.5–50 V | the threshold for mode 2 | — |
| `use_sine_start` | 0 | 0/1; switching to normal commutation at 5–25 % throttle (`sine_mode_changeover`, 15), power `sine_mode_power` 1–10 (6) | a smooth sine start | heavy props, low KV, if they don't start |
| `stall_protection` | 0 | 0–3 | raises the throttle when RPM drops; the code has a note “for crawlers and RC cars, not for multirotors” | for a copter — 0 |
| `stuck_rotor_protection` | 1 | 0/1 | shuts off the motor if the EMF disappears (the rotor has stopped) | leave at 1 |
| `dir_reversed`, `bi_direction` | 0, 0 | 0/1 | direction and 3D | direction — better with a command from the flight controller |
| `input_type` | 1 = DShot | 0 auto, 1 DShot, 2 servo, 3 serial, 4 — DShot with EDT arming, 5 — DroneCAN (CAN ESCs only) | 4: throttle is silently ignored until command 13 arrives; zero throttle removes the arming again | the analog of Bluejay's EDT safety arm |
| `telemetry_on_interval` | 0 | 0 off, 1 and above — wired (serial) telemetry | a separate telemetry wire; EDT over DShot is enabled by command 13 | with a separate ESC telemetry wire |
| `beep_volume` | 5 | 0–11 | the volume of beeps | to taste |

A worked conversion: the `advance_level` byte = 26 → (26 − 10)·0.9375 = 15°; the `limits.current` byte = 30 → 60 A; the `low_cell_volt_cutoff` byte = 30 → 2.80 V per cell. The cutoff trap: 6S, charged to 25.2 V → 2520 / 370 = 6.8 → 6 cells, threshold 16.8 V. The same pack connected after sagging to 22.0 V → 2200 / 370 = 5.9 → 5 cells, threshold 14.0 V, and the cutoff will trigger 0.47 V per cell later than intended.

### Overheating: how the ESC takes away power
Neither firmware enables thermal protection **by default**. When enabled, it behaves differently: Bluejay reduces the power limit in steps and smoothly, and at the last step leaves 20 % — in the code comment this is a “forced landing”. AM32 at the very first degree above the threshold cuts the limit to a quarter and by threshold + 10 °C — almost to zero. That is why the AM32 threshold is set above the real operating temperature, not low “just in case”. The temperature in flight is visible through EDT (`dshot_edt`).

{{diagram:chart-esc-temp-derate|With a 100 °C threshold, Bluejay takes away power in steps down to 20 %, while AM32 at 101 °C immediately leaves 25 % and by 110 °C — zero: a low AM32 threshold brings the aircraft down in hot weather.}}

### Symptom → setting: a cheat sheet
The rows give the first setting to touch, and which way. All the steps and numbers in the table are course guidelines, not manufacturer data; change one setting at a time and check with the same pack and the same maneuver.

| Symptom | Bluejay | AM32 | Course guideline | What you pay |
|---|---|---|---|---|
| Desync on a sharp throttle input (punch-out) or on a chop: the motor “sneezes”, the aircraft twitches | demag Low → High; then timing 4 → 5 (at 4 Bluejay itself goes up to 5 with strong demagnetization; a manual 5 helps if the loss of sync starts before the metric grows — the course's conclusion from the code) | `demag_comp` 0 → 2, then 3–4; `advance_level` +4…8 units (+3.75…7.5°) | one step, 3 throttle punches from hover to 100 % for each | a thrust dip on the transition; heating from the timing |
| Hot motors, the ESC is cold | PWM frequency higher (small motors); timing 4 → 3 | frequency higher; `advance_level` −4…8 units | after a pack the motor can be held in your hand for 5 s | less RPM at the top of the throttle |
| Uneven low throttle, jitter at idle | frequency 48 → 24 kHz with dead time ≥ 30; startup power min higher | `variable_pwm` 0 → 1 (if it was turned off); `startup_power` higher | N = 10·f/eRPM in hover ≥ 3 | a rougher sound, a warmer ESC |
| A motor won't start on large props (10" and larger) | startup power min and max higher; RPM power slope higher | `startup_power` 100 → 120–150; correct `motor_kv` and `motor_poles`; `use_sine_start` = 1 | +25 % of the current value per step; enough when 10 out of 10 starts succeed | more current in the windings if jammed |
| Throttle chops too abrupt, the ESC heats up in prop wash | braking strength 255 → lower | `driving_brake_strength` 10 → 7–9 | a step of 10 % of the braking strength | a softer stop after a flip, worse prop wash |
| The propeller spins after disarming, or a folding prop needs to stop | brake on stop = 1 | `brake_on_stop` = 1 | only a plane and a folding prop | current through the windings when parked with AM32 mode 2 |
| The ESC is hot, the protection triggers | frequency lower; temperature protection 100–110 °C | frequency lower; `limits.current` per the ESC's datasheet | after a pack the ESC is no hotter than 80–90 °C per EDT | less smoothness |

### ESC beacon and the Betaflight DShot beacon
It is the motors that beep: the ESC feeds an audio-frequency current into the windings. This is possible only while the ESC is powered by the flight battery. There are three sources of the “beep” command, and their requirements differ.

| What beeps | Who decides | Conditions | Needs the flight battery | Needs a live flight controller |
|---|---|---|---|---|
| Bluejay's own beacon | the ESC itself | the ESC is “armed” and receives DShot frames with zero throttle; `beacon delay` has passed (10 min by default) without throttle; the volume — beacon strength. If the signal is lost, the ESC beeps “signal lost” once and goes to wait for a signal, the beacon stays silent | yes | yes: it needs a stream of DShot frames |
| AM32 | only the flight controller | there is no beacon timer of its own; DShot commands 1–5 while the ESC is armed and the motor is stopped | yes | yes |
| Betaflight 4.5.3 DShot beacon | the flight controller | `beacon RX_LOST` and/or `beacon RX_SET` (both off by default; in RACE_PRO builds RX_SET is on); RX_SET — the BEEPER mode on a switch. The motors are not spinning, 1.2 s have passed since disarming, no arming attempt; repeats no more often than 450 ms (RX_SET) and 950 ms (RX_LOST), in practice about 0.5 and 1.0 s (course estimate: the check happens on the transitions of the beeper sequence); the tone `beeper_dshot_beacon_tone` 1–5 (default 1) = the commands DSHOT_CMD_BEACON1…5. After a beacon command, arming is delayed by 1.2 s | yes | yes |
| A standalone buzzer with its own battery | itself | power to the aircraft is lost | no | no |

If the battery flew off or came unclipped, everything goes silent: the ESC has no power, the flight controller has no power. Only a standalone buzzer with its own battery beeps. In Betaflight 2025.12 there is one interval — 450 ms, the RX_LOST beacon does not sound with USB plugged in, and RX_SET works only with a live receiver; an analysis of the conditions from the code — in a separate module.

{{lesson:bf-led-buzzer|All of Betaflight's `beeper` and `beacon` conditions from the source code, the differences of 2025.12 from 4.5, and checking the beacon on the bench.}}

### How to flash
- **Through the flight controller (passthrough).** The flight controller passes the ESC signal wire through to the computer. Betaflight: connect USB, close Betaflight App (Configurator) (the port is busy), open ESC Configurator (esc-configurator.com) in Chrome — for BLHeli_S/Bluejay and AM32; for BLHeli_32 — BLHeliSuite32 (an archived version). ArduPilot: `SERVO_BLH_AUTO = 1` for motors (for planes — `SERVO_BLH_MASK`), the DShot protocol, disconnect the GCS, keep USB, in the configurator — the “BLHeli32/AM32 Bootloader (Betaflight/Cleanflight)” interface. IOMCU (MAIN) outputs do not support passthrough — you need FMU/AUX outputs. Two more ArduPilot 4.7.2 conditions (`AP_BLHeli.cpp`): the aircraft is disarmed (requests are ignored while armed) and the program is on the `SERVO_BLH_PORT` channel (default 0 — the USB console); after `SERVO_BLH_AUTO`/`SERVO_BLH_MASK` — a reboot. The order of checks if the ESC is not found: disarmed → DShot protocol → the output is not on the IOMCU → reboot after `SERVO_BLH_*` → GCS disconnected (in detail — `ap-outputs`).
- **The target rule.** The firmware is chosen for the specific ESC board (layout/target). A wrong target — anything from incorrect operation to burned switches. The configurator usually shows the current layout — flash only a matching one.
- **Before flashing**: remove the props, save the current settings (a screenshot or a file), flash one ESC at a time if in doubt, a battery with protection (a smoke stopper).

### The flight controller: what to enable
- Betaflight: `set motor_pwm_protocol = DSHOT600` (or 300 — depending on the PID loop and the MCU, the rule is in `f-motors-esc`; on F405/F411/G47x with bidir the firmware itself sets 300), `set dshot_bidir = ON`, `set motor_poles = 14`; check — the Motors tab shows RPM, DShot errors ≤ 1 % (`bf-rpm-filter`).
- ArduPilot: `MOT_PWM_TYPE` — DShot300/600; `SERVO_DSHOT_ESC` — the ESC type: 1 BLHeli32/Kiss/AM32, 2 BLHeli_S/Bluejay, 3 and 4 — the same with EDT (temperature, voltage, current in the return channel; only if the ESC firmware supports EDT), 0 — DShot commands (reversal, beeping) are not sent; `SERVO_BLH_BDMASK` — the mask of outputs with bidirectional DShot (it exists only in a build with bidir DShot, for some boards — the `-bdshot` variant), `SERVO_BLH_POLES` — the number of poles; ESC telemetry is visible in the log (`ESC`) and is used by the harmonic notch (`INS_HNTCH_MODE = 3` — by ESC telemetry).

{{diagram:esc-firmware-choice|Choosing ESC firmware: an 8-bit ESC on BB21/BB51 — Bluejay instead of BLHeli_S, a 32-bit one — AM32 if there is a target, a working BLHeli_32 can be left as it is, with no target — don't flash.}}

### Place in the system

- **Receives:** DShot frames and the telemetry request from the flight controller (`f-motors-esc`); the motor's number of poles; the target (layout) of the specific ESC board.
- **Provides:** eRPM — to the Betaflight RPM filter and the ArduPilot harmonic notch (`bf-rpm-filter`, `ap-tuning`); via EDT — temperature, voltage and current; via the PWM frequency and timing — the motor's heating and response.
- **If you get it wrong here:** the RPM filter is enabled, but the ESC firmware does not reply over bidirectional DShot → the `DSHOT_TELEM` flag, the aircraft won't arm (`bf-arming-safety`, tree 1 in `diag-troubleshooting`). The demagnetization compensation is too small for a large motor → a desync on a sharp throttle change: the motor stops, the crash detector triggers — while the cause is in the ESC settings (tree 6 in `diag-troubleshooting`).

## practice
### Step 1. Inventory
Through passthrough, read each ESC: firmware and version, layout/target, PWM frequency, timing, direction. Write the table into the aircraft's spec sheet.

### Step 2. Bidir DShot and RPM
If the firmware supports it — enable bidirectional DShot and the number of poles in the flight controller. Betaflight: the Motors tab, with the motors spun up (without props) — RPM and the error percentage. Write down the eRPM and the mechanical RPM at 10 % throttle, check the conversion formula with your number of poles.

### Step 3. Flashing (if there is a benefit)
Only if you need bidir DShot or EDT and they are not there: BLHeli_S → Bluejay (only on BB21/BB51 MCUs) or BLHeli_32 → AM32 if there is a target. First save the settings; the target — from the layout you read. After flashing — restore the direction and check the motor order and direction.

### Step 4. PWM frequency: a comparison in flight
Do not measure without props — you need the real operating mode. First, the calculation: from the eRPM in hover (from the OSD or a flight log with props on, not from the bench) calculate N = 10·f/eRPM for 24 and 48 kHz and write down which frequency the class table recommends. Then three flights on the same charged pack along the same route (30 s of hover, a pass, a few sharp throttle chops): 24 kHz, 48 kHz and 24 kHz again. In Bluejay changing the frequency means flashing a different hex with the same layout, after which you check the motor direction; in AM32 — a parameter. The third flight is needed to find out the spread between identical flights. For each flight write down: the average hover current, the ESC temperature at the end (EDT), the motor temperature by touch or with a pyrometer, the gyro noise at mid throttle in Blackbox, the behavior on throttle chops (prop wash), whether all motors start on arming.

| Flight | Frequency | N in hover | Hover current, A | ESC t, °C | Motors | Gyro noise | Throttle chop |
|---|---|---|---|---|---|---|---|
| 1 | 24 kHz | … | … | … | … | … | … |
| 2 | 48 kHz | … | … | … | … | … | … |
| 3 | 24 kHz | … | … | … | … | … | … |

The decision rule: a difference between flights 1 and 2 counts as real only if it is larger than the difference between flights 1 and 3. If there is no difference — keep the starting value for your class from the table; if there is no starting value or you are in doubt — the lower frequency (a cooler ESC, more throttle steps).

### Step 5. Convert the settings you read into units
Without hardware, using the tables from the theory. The input data — dumps of two ESCs. Bluejay: timing 4, demag 2, temperature protection 3, beacon delay 2, startup power min 21. AM32: `advance_level` 30, `limits.current` 30, `limits.temperature` 0, `low_voltage_cut_off` 1, `low_cell_volt_cutoff` 30; a 6S battery, 22.0 V at connection. For each line write down the value with its unit and one consequence for the flight; for AM32 calculate the cell count and the cutoff threshold when connected at 22.0 V and at 25.2 V.

Self-check: the lab is done when the ESC table is filled in for every ESC (firmware and version, layout, PWM frequency, timing, direction), the RPM from the ESCs is visible in the flight controller with errors of about 0 %, the conversion checks out — mechanical RPM = eRPM / (number of poles / 2), for 14 poles that is eRPM / 7 — and the PWM frequency choice is recorded with the number N in hover for 24 and 48 kHz, with the hover current and ESC temperature from the three flights (24, 48 and again 24 kHz) and with a conclusion by the decision rule from step 4, and in step 5 (without hardware) all values (ten values and the cell count at two voltages) matched the reference below, angles — to 0.01°, cutoff thresholds — to 0.1 V.

**Reference for step 5.** Bluejay: timing 22.5° of advance, demag Low (metric threshold 160), overheat protection 100 °C, beacon after 2 min without throttle, minimum startup power ≈ 1010 on the throttle scale (≈ 1 %). AM32: (30 − 10)·0.9375 = 18.75°; current limit 60 A; thermal protection off (0 is outside the 70–140 range); 22.0 V → 2200 / 370 = 5.9 → 5 cells, threshold 5 · 2.80 = 14.0 V; 25.2 V → 6 cells, threshold 16.8 V. Typical errors: 30° instead of 18.75° — the offset of 10 and the 0.9375° step were forgotten; 30 A instead of 60 — the factor of 2 was forgotten; 16.8 V when connected at 22.0 V — the fractional part of the cell count was rounded up, while the firmware discards it.

**Reference for self-check.** The expected direction of the difference: at 24 kHz the ESC is cooler, braking and thrust at low throttle are stronger; at 48 kHz the current is smoother, the sound softer, the gyro noise at mid throttle no higher, small motors cooler. The sources give no reliable number for the size of the difference — it depends on the motor's inductance, the current and the ESC's switches, so it is measured on your own aircraft. According to the calculation in the worked example, the difference in heating is noticeable on a small motor, and fractions of a watt on a large one; if on a 7" and larger the difference turned out smaller than the spread between flights, the correct conclusion is “no difference, I'm keeping 24 kHz”. Checking the calculation: at 50,000 eRPM N = 4.8 at 24 kHz and 9.5 at 48 kHz. Common wrong results: the conclusion was drawn from two flights without the repeat — it is unknown whether it is a difference or spread; the RPM in the flight controller differs from the real one by the same factor at any throttle — the number of poles is set wrong; the frequencies were compared without props or on different packs — such a comparison tells you nothing, you need the real operating mode and the same pack; after reflashing a motor spins the wrong way — the direction was not restored; the order and direction are checked again without props.

## diagnostics
- **Symptom:** the RPM filter doesn't enable, the Motors tab shows no RPM
  - Possible cause: ESC firmware without bidir DShot (original BLHeli_S), `dshot_bidir` is off, the wrong protocol.
  - What to do: check the ESC firmware, enable bidir, if necessary — Bluejay/AM32.
- **Symptom:** a high percentage of DShot errors
  - Possible cause: interference on the signal wires, a DShot speed too high for the wire length, a poor ground.
  - What to do: DShot300 instead of 600, short wires, a common ground, ferrites if needed.
- **Symptom:** a motor twitches or stops on a sharp throttle input
  - Possible cause: loss of synchronization (desync).
  - What to do: raise the demag compensation (Bluejay Low → High, AM32 `demag_comp` 0 → 2 → 4), then the timing one step higher — Bluejay raises the timing by itself when the demagnetization metric is high; check the bearings, the windings and the length of the phase wires. If the motors are hot as a result — restore the timing and use a smaller prop.
- **Symptom:** AM32 shuts off a motor in mid-flight while the battery is still alive — or, conversely, never shuts it off
  - Possible cause: the per-cell cutoff is enabled (`low_voltage_cut_off` = 1), and the cell count was calculated when the ESC armed as voltage / 3.70 V: a sagging 6S below 22.2 V is counted as 5S, the threshold is lower than intended; with a charged pack and a high threshold — an early cutoff under load.
  - What to do: on a copter with a flight controller — `low_voltage_cut_off` = 0, the flight controller watches the battery; if a cutoff is needed — arm only with a charged pack, or use mode 2 (an absolute threshold).
- **Symptom:** the aircraft arms, but the motors don't spin; Bluejay beeps briefly when throttle is applied, AM32 silently ignores the throttle
  - Possible cause: Bluejay EDT safety arm = 1 or AM32 `input_type` = 4, while the flight controller does not send command 13 (`dshot_edt = OFF`, no bidir DShot, or a separate ESC telemetry wire is enabled).
  - What to do: `set dshot_edt = ON` and `dshot_bidir = ON` in Betaflight, or disable EDT arming in the ESC.
- **Symptom:** power drops sharply in hot weather or in a long climb, the ESC is hot after landing
  - Possible cause: the thermal protection triggered; with AM32 the first degree above the threshold leaves about 25 % of the power.
  - What to do: watch the temperature via EDT; raise the threshold to the real operating temperature with a margin, lower the PWM frequency, add airflow.
- **Symptom:** after a crash the motors are silent
  - Possible cause: `beacon` in Betaflight is off by default; Bluejay waits for `beacon delay` of 10 min; the battery flew off — the ESC and the flight controller have no power.
  - What to do: `beacon RX_LOST`, beacon delay 1–2 min; for searching without a battery — a standalone buzzer.
- **Symptom:** passthrough does not find the ESC
  - Possible cause: Configurator/the GCS is open, no battery power to the ESC, IOMCU outputs in ArduPilot, the protocol is not DShot.
  - What to do: close the other programs, connect the battery, move to FMU/AUX outputs, enable DShot.
- **Symptom:** after flashing a motor doesn't spin or heats up at rest
  - Possible cause: a wrong target/layout.
  - What to do: reflash with the correct target through the bootloader; if the bootloader is damaged — only with a programmer.

## references
- Bluejay — open-source firmware for BLHeli_S ESCs | https://github.com/bird-sanctuary/bluejay | primary | A
- AM32 — open-source firmware for ARM ESCs | https://github.com/am32-firmware/AM32 | primary | A
- ESC Configurator (web) | https://esc-configurator.com | primary | B
- ArduPilot — BLHeli32, AM32 and BLHeli_S ESCs (passthrough) | https://ardupilot.org/copter/docs/common-blheli32-passthru.html | primary | A
- Betaflight — DShot RPM filtering | https://betaflight.com/docs/wiki/guides/current/DSHOT-RPM-Filtering | primary | A
- Bluejay wiki — FAQ: which PWM settings, dead time | https://github.com/bird-sanctuary/bluejay/wiki/FAQ | primary | A
- Bluejay wiki — Concepts explained: PWM resolution, deadtime | https://github.com/bird-sanctuary/bluejay/wiki/Concepts-explained | primary | A
- Bluejay v0.21.0 — release notes | https://github.com/bird-sanctuary/bluejay/releases/tag/v0.21.0 | primary | A
- BLHeli_32 manual ARM Rev32.x (PWM frequency, By RPM) | https://github.com/bitdump/BLHeli/blob/master/BLHeli_32%20ARM/BLHeli_32%20manual%20ARM%20Rev32.x.pdf | primary | A
- BLHeli_S manual SiLabs Rev16.x (motor PWM 24 kHz) | https://github.com/bitdump/BLHeli/blob/master/BLHeli_S%20SiLabs/BLHeli_S%20manual%20SiLabs%20Rev16.x.pdf | primary | A
- Gyroflow — Supported cameras: DJI (O3/O4: a 24 kHz ESC PWM interferes with IMU sampling, 48 kHz and higher) | https://docs.gyroflow.xyz/app/getting-started/supported-cameras/dji.md | primary | A
- Bluejay source — default settings (BluejaySettings.asm) | https://github.com/bird-sanctuary/bluejay/blob/v0.21.0/src/Settings/BluejaySettings.asm | primary | A
- Bluejay source — decode of settings (Modules/Settings.asm) | https://github.com/bird-sanctuary/bluejay/blob/v0.21.0/src/Modules/Settings.asm | primary | A
- AM32 source — settings scaling, loadEEpromSettings (Src/main.c) | https://github.com/am32-firmware/AM32/blob/main/Src/main.c | primary | A
- AM32 source — default_settings[] image and DroneCAN parameter table (Src/DroneCAN/DroneCAN.c) | https://github.com/am32-firmware/AM32/blob/main/Src/DroneCAN/DroneCAN.c | primary | A
- Betaflight 4.5 — beeper.c (DShot beacon conditions) | https://github.com/betaflight/betaflight/blob/4.5-maintenance/src/main/io/beeper.c | primary | A
- Oscar Liang — Best BLHeli_32 settings (PWM frequency by use) | https://oscarliang.com/best-blheli-32-settings | secondary | B
- Oscar Liang — Bluejay firmware and best settings | https://oscarliang.com/bluejay-blheli-s/ | secondary | B
- Oscar Liang — Best AM32 settings | https://oscarliang.com/best-am32-settings | secondary | B

## checklist
- I identify the ESC type (8-bit / ARM) and the suitable firmware
- I can explain bidir DShot, eRPM and EDT, and convert eRPM to RPM
- I know what the PWM frequency, timing and demagnetization change; I choose the PWM frequency by aircraft class and the number N
- I read Bluejay and AM32 settings in units: timing in degrees, the current limit in amps, the cutoff threshold and the cell count
- From a symptom (desync, hot motors, a jerky bottom end, no start) I choose the first setting and the step
- I know what the ESC beacon and the DShot beacon need, and why without a battery only a standalone buzzer beeps
- I flash ESCs through the flight controller and check the target
- I enable RPM from the ESC in Betaflight and ArduPilot
