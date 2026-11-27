---
id: f-micro-whoop
title: "Whoops and micros: 1S/2S, AIO, SPI receivers and connectors"
level: L2
readingTime: 45 min
firmware: Betaflight 2025.12 (checked against 2025.12.5; the ELRS V4 branch — against tag 2026.6.1) · ExpressLRS 4.1.0 · Bluejay 0.21+
status: published
tags:
  - whoop
  - micro
  - 1S
  - AIO
  - ELRS SPI
  - BT2.0
  - LiHV
related:
  - f-power
  - f-electricity-101
  - f-components-choice
  - f-esc-firmware
  - link-elrs
  - bf-rpm-filter
  - bf-ports
  - bf-setup-scratch
  - link-digital-video
  - f-safety
  - f-regulations
  - bf-pid-reg-in-bf
next:
  - bf-setup-scratch
source: content/foundation/f-micro-whoop.md
source_hash: f60ad75f3c42
---

## summary
A whoop is a 65–75 mm aircraft with prop guards running on a single cell (1S). It is what people most often start with, and it is the most convenient thing to train on at home. It is not built like a 5": one “5-in-1” board instead of a stack, an ELRS receiver inside the flight controller firmware, and half of the voltage loss comes from the connector and the cell itself. After this module you choose a micro class for the job, calculate 1S sag from internal resistance and the connector, understand what you pay for an AIO, stay out of the “Betaflight 2025.12 + radio on ELRS 4.x” trap, and know which Betaflight parameters set a whoop apart from a five-inch. The lab needs no hardware: calculating the drop across the connector and finding three errors in a training `diff`.

## theory
### Micro classes: what to choose
The answer to “which size do I get first”: for an apartment — 65 mm 1S, for a yard with no wind — 75 mm 1S, for a park — 3–3.5" under 250 g. It makes sense to buy the first aircraft as a BNF (ready-made, for your own radio): you will have to solder during repairs anyway, and building from scratch is better left for the second one. The order of purchases, the radio, the goggles and the budget of the whole kit are in `f-starter-kit`.

| Class | Power | Motors, KV | Props | Dry weight | Battery | Flight time | Where to fly |
|---|---|---|---|---|---|---|---|
| Whoop 65 mm | 1S | 0702 (less often 0802), 23,000–30,000 | 31 mm, 2–3 blades | 15–20 g | 1S 260–300 mAh | 3–4 min (estimate) | room, hall |
| Whoop 75 mm | 1S | 0802, 22,000–28,000 | 40 mm | 20–24 g | 1S 450–580 mAh | 5–7 min | apartment, yard in calm air |
| Whoop 75–85 mm | 2S | 1002–1103, 10,000–15,000 (estimate) | 40–50 mm | 30–45 g (estimate) | 2S 300–450 mAh | 3–5 min (estimate) | yard, outdoors |
| Toothpick 2–3" | 1S–3S (S to match the motor KV, `f-aero-props`, “KV for the prop”; estimate) | 1102–1404, 5,000–11,000 (estimate) | open 2–3" | 35–80 g (estimate) | 2S–3S 300–550 mAh | 3–6 min (estimate) | outdoors, park |
| 3.5" under 250 g | 3S–4S (S to match the motor KV, `f-aero-props`, “KV for the prop”; estimate) | 1404–1505, 3,000–4,600 (estimate) | 3.5" | 110–160 g, takeoff weight < 250 g (estimate) | 4S 650–850 mAh | 5–9 min (estimate) | park, freestyle |

Where the numbers come from. The 65 and 75 mm rows are manufacturer product pages and Oscar Liang's review as of November 2026: the record 65 mm build is 15.4 g, a production BNF is 17.1 g, typically 18–20 g; the BETAFPV Air75 II is 20.2–21.3 g, 0802 motors at 22,000 / 25,000 / 28,000 KV, claimed time 6:50–7:30 on 480 mAh. The claimed time is a calm hover. Rows marked “estimate” are orders of magnitude from catalogs, not verified on specific products. KV for your cell count and where to start within the range (from the middle; closer to the top for a light and racing build, to the bottom for a heavy one) — the rule “KV × cell count is almost constant for one prop” and Oscar Liang's table in `f-aero-props`: a 75 mm whoop on 2S is listed there at 12,000–14,000 KV, a 3.5" on 4S at 2500–4000 (cinewhoop and freestyle); the estimates in this table agree with them in order of magnitude.

The table follows a single logic: the smaller the prop, the higher the KV and RPM and the lower the efficiency (`f-aero-props`). An 0802 motor at 28,000 KV on 3.8 V gives about 106,000 RPM with no load. Hence 3–7 minutes of flight and currents of up to 9 A per motor (BETAFPV 0802 28,000 KV datasheet: 9 A, 34 W).

**1S or 2S.** 1S is quieter, lighter and safer indoors. 2S gives a thrust margin for outdoors, but it is hard to control in a room. 85 mm frames are usually built for 2S. Weight also determines the rules: the 250 g threshold applies in many countries, but “under 250 g” does not mean “no rules” (`f-regulations`).

**Brushed and brushless.** The first whoops of the mid-2010s flew on 6 and 7 mm brushed motors: cheap, but the brushes wore out within tens of flights, and thrust dropped from pack to pack. From about 2018–2019 the class moved to brushless 0603–0802 motors with four ESCs on the same board. Betaflight still supports brushed builds: protocol `BRUSHED`, 16 kHz PWM, `motor_idle` 700 by default. There are almost no new boards for them.

### 1S physics: sag, cell and connector
On a 5" on 6S, a 0.3 V loss is 1.3 % of the voltage. On a whoop on 1S, the same 0.3 V is 8 %. That is why on 1S every milliohm is counted:

U at the board = E − I · (R cell + R wire + R connector).

- **R cell.** Small cells have a large one: tens of milliohms. The calculations in this module assume 60 mΩ for 300 mAh (an assumption; measure your own cell with the charger). With wear and in the cold it grows 1.5–2 times (`f-power`).
- **R wire.** 22 AWG is 53 mΩ/m. A 2 × 40 mm pigtail gives 4.2 mΩ.
- **R connector.** There are two contacts in the circuit: positive and negative.

| Connector | Contact | Current per the manufacturer | Contact resistance | Remarks |
|---|---|---|---|---|
| PH2.0 (JST PH, 2 mm pitch) | crimp, AWG 32–24 wire | 2 A per contact (JST datasheet, AWG 24); BETAFPV states 4.5 A for the whoop version | ≤ 10 mΩ new, ≤ 20 mΩ after testing (JST) | a signal connector used as a power connector; leaving the market |
| BT2.0 (BETAFPV) | 1.0 mm “banana” | 9 A continuous, 15 A peak | no figure; estimate — a few mΩ, like the A30 | the BETAFPV standard; 22 AWG wire |
| A30 (GNB) | “banana” | 15 A, 30 A peak | 1.6 mΩ | partially mechanically compatible with BT2.0 |
| GNB27 (GNB) | “banana” | 9 A continuous, 15 A peak (seller's product page; the name hints at 27 A — not confirmed) | not published | not compatible with A30 and BT2.0 |

The A30 and GNB27 data are taken from seller product pages citing GNB, not from a datasheet. The conclusion does not change because of that: the PH2.0 contact is an order of magnitude worse. At 10 A an aged PH2.0 pair eats 0.40 V and heats up by 4 W, an A30 — 0.03 V and 0.3 W (calculation in the practice section).

{{diagram:chart-micro-connector-sag|With the same cell (E = 3.90 V, 60 mΩ) a board with an aged PH2.0 sees 3.30 V already at 5.8 A, and with an A30 — only at 8.9 A: the connector takes away a third of the available current.}}

The answer to “BT2.0 or PH2.0”: get BT2.0 or A30 and do not mix standards within one battery fleet. A PH2.0 → BT2.0 adapter brings back the PH2.0 resistance, so there is no point in it.

**LiHV.** Almost all 1S cells for whoops are LiHV: charged to 4.35 V/cell instead of 4.20 V. This adds a few percent of capacity and voltage at the start of the flight. Charge to 4.35 V only cells marked HV (3.8 V nominal). Storage is 3.80–3.90 V, as for ordinary LiPo (`f-power`). Whoop cells are a consumable: after 50–100 cycles the resistance grows noticeably (estimate), and the flight gets shorter before the capacity drops.

**Charging 1S.** Two classes of devices as of November 2026:
- Parallel chargers with 4–6 ports and a separate channel per cell. The simple and safe option, current usually up to 1 A per port.
- Series charging boards: 4–6 1S cells are connected into a 4S–6S “pack” with a balance connector, and an ordinary balance charger charges them. Fast, but the cells must be of the same capacity and in the same condition, and the charger must support LiHV. An empty slot without a jumper means an open circuit or the wrong cell count. Check that the charger has detected as many S as there are cells inserted.

A 1C current (300 mA for 300 mAh) is a safe reference point. The remaining LiPo rules are in `f-power` and `f-safety`.

### The “5-in-1” AIO: what is on the board and what you pay for it
A whoop board combines the flight controller, four ESCs, the receiver and an analog transmitter (FC + ESC + RX + VTX; the OSD or the current sensor is counted as the separate fifth element). It weighs 3–5 g versus 15–20 g for a 20×20 stack. The answer to “stack or AIO”: up to 3" there is almost no choice — AIO; from 5" up — a stack, because it can be repaired part by part and the currents there are higher.

| MCU | Betaflight 2025.12 target | UARTs in the platform | DShot with `dshot_bidir = ON` | What this means |
|---|---|---|---|---|
| STM32F411 | `STM32F411` | 3 (UART1, 2, 6) | forced DSHOT300, PID ≤ 4 kHz with an 8 kHz gyro | the most common and the tightest: 100 MHz, 512 KB of flash |
| STM32G473 | `STM32G47X` | 6 (UART1–5, LPUART1) | the same restriction (`USE_PID_DENOM_CHECK`) | 170 MHz, more peripherals |
| AT32F435 | `AT32F435G` / `AT32F435M` | 8 (UART1–8) | no restriction in the code: DSHOT600 and 8 kHz are allowed | 288 MHz; its own set of drivers and targets |

The UART count is the platform ceiling. Fewer are broken out on the board: some are taken by the built-in VTX, the receiver and the OSD. The MCU clock frequencies are quoted from memory of the datasheets.

What you pay with:
- **Repairability.** A burned FET of one ESC means replacing the whole board.
- **UARTs.** On an F411 one or two are free. A digital VTX (MSP DisplayPort), an external receiver and GPS will not fit together (`bf-ports`).
- **Blackbox.** The board either has no flash or has 8–16 MB (estimate). Without logs, filter tuning is done by ear (`bf-blackbox`).
- **Gyro.** They fit whatever is in supply: BMI270 (3.2 kHz in Betaflight), ICM-42688-P (8 kHz), new sensors at 6.4–6.7 kHz. Some boards with non-standard sensors work only on the manufacturer's firmware — read the product page before flashing an official build.
- **ESC current.** Typically 5–12 A per channel. On 2S and heavy props the margin is small.

The ESCs on such boards are 8-bit (EFM8 BB21/BB51) with Bluejay firmware: bidirectional DShot and 24/48/96 kHz PWM. For whoops 48 kHz is the usual choice: small motors with low inductance lack current smoothness at 24 kHz, while 96 kHz adds little and leaves fewer throttle steps and more dead-time losses — the motors find it harder to start. The selection rule, the calculation and reflashing are in `f-esc-firmware`.

### The ELRS SPI receiver and the version trap
An ordinary ELRS receiver is a separate module with its own MCU (ESP8285/ESP32) and its own firmware. It talks to the flight controller over a UART using the CRSF protocol. An SPI receiver has no MCU of its own: only the SX1280 radio chip is soldered onto the board, connected to the flight controller MCU over SPI. The whole ELRS protocol is executed by Betaflight (`src/main/rx/expresslrs*.c`).

Consequences:
- **Such a receiver has no ELRS firmware.** It cannot be updated over Wi-Fi or with ExpressLRS Configurator. The “ELRS version” equals the version and build options of Betaflight.
- **Setup.** `rx_spi_protocol = EXPRESSLRS`, the domain `expresslrs_domain` (`ISM2400` or `CE2400`), `expresslrs_model_id` (255 — Model Match off).
- **Binding.** Method 1 — a phrase: the Binding phrase field on the Receiver tab, or manually `set expresslrs_uid = 250,207,69,233,211,154` and `save`. The UID is the first 6 bytes of the MD5 of the string `-DMY_BINDING_PHRASE="phrase"`; the example is computed for the phrase `my whoop 2026`. Method 2 — `bind_rx` in the CLI (or the Bind Receiver button), then `[Bind]` in the radio's Lua script. The default UID is six zeros: the receiver is not bound.
- **Modes.** The table in `expresslrs_common.c` of 2025.12 for 2.4 GHz contains FLRC 1000 and 500 Hz and LoRa 500, 250, 150, 50 Hz. It has no Full Res modes and no D- or K-modes.
- **Range** is lower than with a separate receiver: there is no amplifier and no diversity, and the antenna is a bit of wire on the board.

**The version trap.** In Betaflight 2025.12.5, `expresslrs_common.h` has `#define ELRS_OTA_VERSION_ID 3`. This number is mixed into the packet CRC initializer and into the seed of the hopping sequence. In ExpressLRS 4.1.0 `OTA_VERSION_ID` equals 4 (`src/include/targets.h`). The result: a radio on ELRS 4.x and an SPI receiver on Betaflight 2025.12 do not see each other at all — no binding, no link, with the correct phrase. From the outside it looks like “the built-in receiver won't bind after updating the radio”.

{{diagram:micro-elrs-spi-trap|An SPI receiver on Betaflight 2025.12 speaks ELRS 3 and does not link with a radio on 4.x; there are three ways out: keep the radio or a second module on 3.x, fit an external receiver over a UART, or move to Betaflight 2026.6 with the ELRSV4 option.}}

Options:
1. **Leave the transmitter on ELRS 3.x** or keep a second external module on 3.x for whoops. Then all the other receivers stay on 3.x too: 3 and 4 are incompatible in both directions.
2. **Fit an external ELRS receiver over a UART** (0.5–1 g), flash it with 4.x, and in Betaflight change `RX_SPI` to `RX_SERIAL` + CRSF. You need a free UART — on an F411 that is not always the case.
3. **Betaflight 2026.6 with the `ELRSV4` build option.** Verified in the source of tag 2026.6.1: under `USE_ELRSV4` the same file sets `ELRS_OTA_VERSION_ID 4`. According to the documentation the option is entered in the Custom Defines field, and by default the build stays on V3. A build with `ELRSV4` stops working with 3.x transmitters. The course targets 2025.12, so this option means moving the board to another version with its own `diff` and a check of the manufacturer's target.

### Betaflight for a whoop: what differs from a 5"
Verified against the 2025.12.5 source (`cli/settings.c`, `pg/motor.c`, `flight/pid.c`, `sensors/battery.c`, `config/config.c`). The “for a whoop” column is typical practice; where it says “estimate”, the number is chosen for the aircraft.

| Parameter | Default | Range, unit | For a whoop | Notes |
|---|---|---|---|---|
| `motor_pwm_protocol` | `DSHOT600`; on F411 — `DSHOT300` | PWM, ONESHOT125, ONESHOT42, MULTISHOT, BRUSHED, DSHOT150/300/600, PROSHOT1000, DISABLED | `DSHOT300` | on F411, F405 and G47x with `dshot_bidir = ON` the firmware itself changes 600 to 300 |
| `dshot_bidir` | `OFF` | OFF / ON | `ON` | needed by the RPM filter and dynamic idle; the ESCs run Bluejay |
| `pid_process_denom` | depends on the board | 1–16 | 2 with an 8 kHz gyro (PID 4 kHz) | on F411/G47x with bidir the firmware raises it to 2 if the gyro is faster than 4 kHz |
| `motor_poles` | 14 | 4–255, magnets | 12 | 0702–1103 motors are usually 9N12P; count the magnets on the bell |
| `motor_idle` | 550 (brushed 700) | 0–2000, 0.01 % | 600–1000 (estimate); start — the minimum stable idle in the Motors tab without props and a little above (`f-esc-firmware`) | before 2025.12 — `dshot_idle_value`; 550 = 5.5 % |
| `dyn_idle_min_rpm` | 0 (off) | 0–200, ×100 RPM | the procedure below the table (course estimate) | silently does not work without `dshot_bidir`; the motor floor becomes 0 %, and until the first throttle raise the increase is limited by `motor_idle` (in 4.5 — `dyn_idle_start_increase`) |
| `dyn_idle_max_increase` | 150 | 10–255, 0.1 % | 150 | the ceiling of the throttle increase |
| `rpm_filter_harmonics` | 3 | 0–3 | 3; fewer — by the rule below the table (harmonics are dropped from the top) | 0 turns the filter off |
| `rpm_filter_min_hz` | 100 | 30–200, Hz | 100 | below this frequency the notches fade out |
| `vbat_sag_compensation` | 0 | 0–150, % | 100 (estimate: on 1S the same 0.3 V of loss is already 8 % of the voltage, see the paragraph on milliohms above, and the response softens toward the end of the pack; check — `debug_mode = BATTERY`, `bf-pid-reg-in-bf`) | evens out thrust between 4.20 V and `vbat_warning_cell_voltage` |
| `thrust_linear` | 0 | 0–150, % | 20–40 (estimate) | adds throttle at low RPM, where at 48–96 kHz PWM the thrust and braking are weaker than at 24 kHz (`f-esc-firmware`) |
| `tpa_mode` | `D` | PD / D | `D` | what exactly to attenuate |
| `tpa_rate` | 65 | 0–100, % | 65 | attenuation at full throttle |
| `tpa_breakpoint` | 1350 | 1000–2000 | 1350 | the throttle from which TPA acts |
| `tpa_low_rate` | 20 | 0–100, % | 20 | attenuates D at low throttle against shaking on the ground; without `tpa_low_always = ON` — only until the throttle first passes above `tpa_low_breakpoint` after power-up |
| `tpa_low_breakpoint` | 1050 | 1000–2000 | 1050 | the upper bound of the low-throttle zone |
| `vbat_max_cell_voltage` | 430 | 100–500, 0.01 V | 440 for LiHV | see below |
| `vbat_warning_cell_voltage` | 350 | 100–500, 0.01 V | 330–340 (estimate) | must be above `vbat_min_cell_voltage` |
| `vbat_min_cell_voltage` | 330 | 100–500, 0.01 V | 310–320 (estimate) | the LAND NOW threshold |
| `force_battery_cell_count` | 0 (auto) | 0–24 | 1 on 1S | removes the auto-detection error |

Five places where a whoop does not behave like a 5":
- **RPM and idle.** A light prop stops instantly. With a low `motor_idle` the motor loses sync in a flip, and the whoop falls. The comment in `mixer_init.c` says it directly: first find a static idle for a reliable start, then turn on dynamic idle.
- **Dynamic idle: the starting value.** The target of `dyn_idle_min_rpm` is RPM, and on a high-KV whoop the static idle spins the motor much faster than on a 5" (the Betaflight documentation advises 30–40 for a 5", `bf-features-tour`), so the 5" value does not suit a whoop. The procedure (course estimate): (1) find a `motor_idle` for a reliable start (`f-esc-firmware`: the minimum stable idle in the Motors tab and slightly above); (2) fly with dynamic idle off and find in Blackbox the RPM of the slowest motor at zero throttle; (3) `dyn_idle_min_rpm` = that RPM / 100, rounded down — the target is no higher than what the static idle already gave; (4) turn it on and check with `debug_mode = DYN_IDLE` in a flat fall (step 5 of the `bf-features-tour` lab): debug[3] (the minimum RPM in rev/s × 10, `mixer.c`; a target of 30 = 3000 RPM = 50 rev/s → 500) is no lower than the target −10 %, flips without dropouts. Without `dshot_bidir` the feature silently does not work.
- **How many RPM filter harmonics.** `rpm_filter_harmonics` = N enables harmonics 1…N and drops only from the top (`flight/rpm_filter.c`): it cannot remove the 2nd while keeping the 3rd — for that the harmonic weight in `rpm_filter_weights` is set to 0. The mechanism (course estimate, `f-frame-mech`): the 1st harmonic carries the motor and prop imbalance, and the harmonic whose number equals the blade count carries the blade-pass frequency. Hence the rule: for a two-blade prop N ≥ 2, for a three-blade — N = 3 (the default, there is nowhere to go lower); for a four-blade (common on 65–75 mm whoops) the blade-pass frequency is the 4th harmonic, which the RPM filter does not cover at all: the dynamic notch catches it (`bf-filters`). The number of notches is motors × N per axis (on a quadcopter with N = 3 — 12 per axis, 36 over three axes; an X8 has twice as many), so on an F411 with the `LOAD` flag you first zero the weight of the harmonic that has no line on the spectrogram, and lower N only if it is the top harmonic and it is not the blade-pass frequency. The check is the gyro spectrogram before and after the filter: the motor lines on the remaining harmonics are attenuated, and there was no line on the removed one (the method is in `bf-rpm-filter`).
- **RPM filter at 4 kHz.** On F411 and G47x with an 8 kHz gyro the scheme is the same: DSHOT300, PID 4 kHz. With a BMI270 (3.2 kHz) the PID runs at 3.2 kHz. Filter setup is in `bf-rpm-filter`.
- **LiHV and `vbat_max_cell_voltage`.** In `battery.c` the battery is considered connected only if the voltage is no higher than `vbat_max_cell_voltage` or is above 6.00 V. A fresh LiHV is 4.35 V. With the default 430 it lands in the 4.31–6.00 V “dead zone”: the cell count and the alarm thresholds are not computed until the voltage sags to 4.30 V. Set 440.

{{lesson:bf-pid-reg-in-bf|What `thrust_linear`, dynamic idle and `vbat_sag_compensation` do to the motor output according to the code, and how to check it with the DYN_IDLE and BATTERY debug modes.}}

On 1S the convention is to land when the voltage under load has dropped to 3.3 V, and not to take it below 3.1–3.2 V. After the throttle is cut the voltage returns to 3.6–3.7 V (estimate). Why the thresholds are lower than the 3.50 / 3.30 V defaults for 4–6S: on 1S the same 0.3 V of cell and connector sag is 8 % of the voltage (section “1S physics”), and with a 3.5 V threshold the alarm comes on a punch-out with a half-empty cell; and landing in a room takes seconds, so no reserve for the return is needed. Do not go below 3.0 V under load on 1S either — this is the datasheet limit of LiPo, common to all classes (the threshold table in `f-power`). The check after landing on the alarm: a rest voltage of 3.6–3.7 V, and the charger put back no more than 0.8 of the capacity (≤ 240 mAh into a 300 mAh cell). If the alarm comes early with 3.8 V at rest, the connector or an old cell is to blame (step 2 of the practice), and the thresholds are not lowered below the table: that is exactly what “lower them as a last resort” means in the troubleshooting section.

### Digital video on a whoop: the weight budget
The analog camera and VTX on a 5-in-1 board weigh 1.5–3 g (estimate), with a power of 25–400 mW. Digital is heavier and more demanding on power:

| System | Weight | Power | Remarks |
|---|---|---|---|
| HDZero Whoop Lite VTX + Nano Lite | 4.5 g VTX + 1.5 g camera + 0.4 g antenna ≈ 6.4 g (the seller writes “about 7 g”) | 1S–3S | 25 / 200 mW; the bundle has been discontinued at some sellers |
| Walksnail Avatar HD Mini 1S Lite | 8.7 g kit (VTX 5.1 g, camera 1.8 g, antenna 0.5 g) | 3.1–5 V | up to 350 mW |
| DJI O4 Air Unit (Lite) | 8.2 g with the camera (5.1 g without it), 9.2–9.3 g with the camera mount, antenna 0.75 g | 3.7–13.2 V | about 3 W at rest, 6 W at 700 mW; below 3.5–3.7 V the picture is unstable, on 1S a step-up BEC is needed |

Digital adds 6–9 g (the table above) to a 65 mm whoop weighing 18 g, that is 35–50 %. That is why digital whoops are 75–80 mm with 40–45 mm props and a 450–580 mAh cell. For 65 mm in a room, analog remains a sensible choice (`link-digital-video`).

### Safety at home and why a whoop is a trainer
A 25 g whoop with prop guards is almost harmless, but “almost” includes eyes, hair, pets and a burning LiPo. The rules are short:
- Do not fly toward a face, yours or anyone else's. Spectators stay behind you or wear glasses.
- Long hair and fur wind around the shaft. After that the ESC heats up within seconds: disarm at once.
- Charge 1S the same way as big packs: on a non-flammable surface and under supervision (`f-safety`).
- VTX indoors — 25 mW. More is not needed, and your channel neighbor will thank you.
- The arm switch and failsafe are set up as strictly as on a 5" (`bf-setup-scratch`, `bf-failsafe`).

Why train on a whoop in particular. The cost of a mistake is a bent prop. Six cells of 3.5 minutes each is 20 minutes of flight time per evening without a trip to the field. The firmware, rates and acro mode are the same as on a 5", so the skill transfers. The training program is in `ops-pilot-training`.

### Place in the system
- **Receives:** the sag formulas and LiPo rules (`f-power`, `f-electricity-101`); the relationship between RPM, KV and prop size (`f-aero-props`, `f-motors-esc`); the protocol version and the binding phrase (`link-elrs`); the ESC firmware and PWM frequency (`f-esc-firmware`).
- **Provides:** the aircraft class and the weight budget — to component selection (`f-components-choice`); the number of free UARTs — to port setup (`bf-ports`); the DSHOT300 + PID 4 kHz combination — to the filters (`bf-rpm-filter`); a ready trainer — to `ops-pilot-training`.
- **If you get it wrong here:** PH2.0 or an old cell → sag → a false LAND NOW and a VTX reboot, which will surface in `bf-modes-osd` and `link-vtx`. A radio on ELRS 4.x with an SPI receiver → “won't bind”, and people look for it in `link-elrs`. `motor_poles = 14` on a 12-pole motor → notches off the frequency, noise and hot motors in `bf-rpm-filter`.

## practice
No hardware is needed. All the numbers are calculated with the formulas from the theory. The check script was run, and its output is given in step 2.

### Step 1. Input data
A 65 mm whoop, a 1S 300 mAh LiHV cell. Assumptions: the EMF of a half-discharged cell E = 3.90 V, internal resistance 60 mΩ, a pigtail of 2 × 40 mm of 22 AWG wire (52.96 mΩ/m). The connector is two contacts in the circuit. We compare three cases: a new PH2.0 (10 mΩ per contact, the maximum per the JST datasheet), a PH2.0 after wear (20 mΩ) and an A30 (1.6 mΩ).

Before calculating, write down: the wire resistance (0.080 m × 52.96 mΩ/m), the resistance of the connector circuit for each case (twice the contact resistance) and two currents — 3.5 A (hover) and 10 A (a sharp throttle punch).

### Step 2. The drop across the connector and the voltage at the board
Calculate by hand U connector = I · 2 · R contact, the power P = I² · R and U at the board = E − I · (R cell + R wire + R connector). Compare with the script output:

```
wire: 4.24 mOhm
--- I = 3.5 A; cell sag 0.210 V, wire 0.015 V
PH2.0 new   (JST: 10 mOhm max/contact): drop 0.070 V, heat 0.24 W, V at board 3.605 V
PH2.0 aged  (JST: 20 mOhm max/contact): drop 0.140 V, heat 0.49 W, V at board 3.535 V
A30         (GNB: 1.6 mOhm/contact)   : drop 0.011 V, heat 0.04 W, V at board 3.664 V
--- I = 10.0 A; cell sag 0.600 V, wire 0.042 V
PH2.0 new   (JST: 10 mOhm max/contact): drop 0.200 V, heat 2.00 W, V at board 3.058 V
PH2.0 aged  (JST: 20 mOhm max/contact): drop 0.400 V, heat 4.00 W, V at board 2.858 V
A30         (GNB: 1.6 mOhm/contact)   : drop 0.032 V, heat 0.32 W, V at board 3.226 V
--- current at which the board sees 3.30 V/3.50 V
PH2.0 new   (JST: 10 mOhm max/contact): 3.50 V at 4.75 A, 3.30 V at 7.12 A
PH2.0 aged  (JST: 20 mOhm max/contact): 3.50 V at 3.84 A, 3.30 V at 5.76 A
A30         (GNB: 1.6 mOhm/contact)   : 3.50 V at 5.93 A, 3.30 V at 8.90 A
```

What follows from this. The cell makes the main contribution: 0.6 V out of 3.9 V at 10 A. But an aged PH2.0 adds another 0.40 V and dissipates 4 W in a contact the size of a match head. With the Betaflight defaults (warning 3.50 V, critical threshold 3.30 V) a whoop on such a connector will show LAND NOW at 5.8 A with a half-full cell. With an A30 the same threshold is reached at 8.9 A.

### Step 3. Flight time
t (min) = capacity (Ah) × fraction used × 60 / average current. A check against the datasheet: 480 mAh in 6:50 is 4.21 A at 100 % depletion and 3.37 A at 80 %. Now your own case: 300 mAh, 80 %, average current 3.6 A → 0.3 × 0.8 × 60 / 3.6 = 4.0 min. Calculate the same for an average current of 5 A (active flying) and write down the answer.

### Step 4. Three errors in the `diff`
Below is a **training example composed by the module's author**: it is not the output of a real board. The parameter names and ranges are verified against the Betaflight 2025.12.5 source. The aircraft: a 65 mm whoop, 1S LiHV, 0702 motors (9N12P), an F411 board with an 8 kHz gyro and an ELRS SPI receiver.

```
# training example: a diff fragment for a 65 mm 1S whoop
set rx_spi_protocol = EXPRESSLRS
set expresslrs_uid = 250,207,69,233,211,154
set motor_pwm_protocol = DSHOT300
set dshot_bidir = ON
set motor_poles = 9
set motor_idle = 800
set vbat_max_cell_voltage = 440
set vbat_min_cell_voltage = 350
set vbat_warning_cell_voltage = 330
set force_battery_cell_count = 2
set pid_process_denom = 2
profile 0
set vbat_sag_compensation = 100
set thrust_linear = 30
```

Find three errors and for each one write down what the pilot will see. Answers:
1. `motor_poles = 9`. In the designation 9N12P, nine is the stator teeth, and there are 12 magnets. Betaflight divides eRPM by the number of pole pairs, so the RPM is overstated by a factor of 12/9 = 1.33: at a real 30,000 RPM the notch will sit at 667 Hz instead of 500 Hz. Noise gets through, the motors heat up. It should be 12.
2. `force_battery_cell_count = 2` on 1S. The thresholds are multiplied by 2: warning 7.00 V, critical 6.60 V with a 4.35 V pack. The OSD shows a cell voltage of 2.17 V and a constant LAND NOW. It should be 1.
3. The thresholds are swapped: the warning at 330 is below the critical at 350. By the logic of `battery.c` the WARNING state will occur only at 3.29 V, and CRITICAL right after it (the condition ≤ 3.49 V is already met). There is no early warning. It should be, for example, 340 and 320.

The remaining lines are correct: DSHOT300 and `pid_process_denom = 2` are the mandatory combination for an F411 with bidir, and 440 is the right maximum for LiHV.

### Moving to real hardware
Props stay off until the last item.
1. Save the `diff all` of your board to a file before any changes.
2. Measure the internal resistance of three of your cells with the charger and substitute it into the formula from step 2.
3. The Motors tab: with `dshot_bidir = ON` the RPM is displayed, and DShot errors are no higher than 1 % (the course reference value, `bf-rpm-filter`). Count the magnets on the bell and compare with `motor_poles`.
4. Connect a fresh LiHV: the OSD shows 1S and a voltage of 4.3–4.35 V, with no alarm.
5. Check the link: `status` does not show `RXLOSS`. Props are still off: arm, switch off the radio and make sure that failsafe triggers.
6. Props on, the first flight — in a room with no people or pets, in Angle mode, 30 seconds of hover.

Criteria for hardware: the measured cell resistance is written down; the RPM in Motors matches KV × voltage in order of magnitude (the example from the theory: 28,000 KV at 3.8 V — about 106,000 RPM with no load); the battery alarm does not appear on a fresh cell and does appear before landing.

Self-check: the lab is complete when (the calculation path): the drop across the connector and the voltage at the board have been calculated by hand for three connectors at 3.5 and 10 A and matched the script output in step 2 to within 0.01 V; the flight time for 5 A came out at 2.9 min; three errors were found in the `diff`, and the numerical consequence of each matched the answers in step 4: the notch at 667 Hz instead of 500 Hz; thresholds of 7.00 and 6.60 V with 2.17 V per cell in the OSD; WARNING only at 3.29 V. For hardware, additionally: items 2–5 are done, and the result of each is written in your aircraft log next to the criterion.

**Reference for self-check.** A correct analysis of the `diff` names exactly three lines — `motor_poles = 9`, `force_battery_cell_count = 2` and the pair of thresholds 350 / 330 — and gives the number from step 4 for each. Two common mistakes: `motor_pwm_protocol = DSHOT300` and `pid_process_denom = 2` are listed as errors (for an F411 with `dshot_bidir = ON` this is the mandatory combination) or `vbat_max_cell_voltage = 440` is (for LiHV this is the correct maximum); `motor_poles` is corrected to 14 instead of 12 — that is the default, while a 9N12P has twelve magnets. If in step 2 the drop across the connector came out exactly half of what the script output shows, the second contact was forgotten.

## diagnostics
- **Symptom:** the built-in receiver stopped linking after the radio was updated, the phrase is correct
  - Possible cause: the radio is on ELRS 4.x, while the SPI receiver on Betaflight 2025.12 speaks OTA version 3.
  - What to do: put the module back on 3.x, fit an external receiver over a UART, or build Betaflight 2026.6 with `ELRSV4`. Flashing the “receiver” through ExpressLRS Configurator is useless: its firmware does not exist.
- **Symptom:** LAND NOW after a minute of flight, and after landing the cell shows 3.8 V
  - Possible cause: sag across the PH2.0 connector or an old cell, not discharge.
  - What to do: calculate as in step 2, switch to BT2.0/A30, measure the cell resistance, retire the worn ones. Lower the thresholds as a last resort.
- **Symptom:** a fresh LiHV is connected, but the OSD does not show the cell count and gives no alarms
  - Possible cause: 4.35 V is above `vbat_max_cell_voltage = 430`, so the battery is considered not connected.
  - What to do: `set vbat_max_cell_voltage = 440`, and optionally `force_battery_cell_count = 1`.
- **Symptom:** the whoop falls in a flip or on a sharp throttle cut
  - Possible cause: the motor loses sync at low throttle: a low `motor_idle`, dynamic idle does not work without `dshot_bidir`.
  - What to do: raise `motor_idle` in steps of 50–100, enable `dshot_bidir`, check the Bluejay version (`f-esc-firmware`).
- **Symptom:** after enabling the RPM filter the motors are hot and the noise in the log is still there
  - Possible cause: `motor_poles = 14` (the default) or 9 on a 12-pole motor.
  - What to do: count the magnets, set the number, compare the RPM in the Motors tab.
- **Symptom:** the video of a digital whoop breaks up on throttle
  - Possible cause: the 1S voltage sags below the VTX operating voltage (for the O4 Lite — below 3.5–3.7 V).
  - What to do: a 5 V step-up BEC, a BT2.0/A30 connector, fresh cells.
- **Symptom:** a series charging board, and the charger shows fewer cells than are inserted
  - Possible cause: a cell is not pushed fully into the slot or is deeply discharged.
  - What to do: do not start the charge, check each cell separately.

## checklist
- The class is chosen for the flying site: 65 mm 1S — room, 75 mm — yard, 3–3.5" — park
- All cells and aircraft use one connector standard (BT2.0 or A30), no adapters
- LiHV cells are charged to 4.35 V, stored at 3.80–3.90 V, worn ones retired
- I know my board's MCU, the number of free UARTs and whether there is flash for Blackbox
- The ELRS version on the radio matches what Betaflight on the board supports (2025.12 → ELRS 3)
- `motor_poles` equals the number of magnets, `dshot_bidir = ON`, RPM is visible in the Motors tab
- `vbat_max_cell_voltage = 440` for LiHV, the warning is above the critical threshold
- `diff all` is saved before changes
- Indoors the VTX is at 25 mW, spectators wear glasses or stay behind you

## references
- Betaflight 2025.12.5: rx/expresslrs_common.h (ELRS_OTA_VERSION_ID 3) | https://github.com/betaflight/betaflight/blob/2025.12.5/src/main/rx/expresslrs_common.h | primary | A
- Betaflight 2026.6.1: rx/expresslrs_common.h (USE_ELRSV4 → OTA 4) | https://github.com/betaflight/betaflight/blob/2026.6.1/src/main/rx/expresslrs_common.h | primary | A
- Betaflight 2025.12.5: cli/settings.c (parameter names and ranges) | https://github.com/betaflight/betaflight/blob/2025.12.5/src/main/cli/settings.c | primary | A
- Betaflight 2025.12.5: sensors/battery.c (battery detection, thresholds) | https://github.com/betaflight/betaflight/blob/2025.12.5/src/main/sensors/battery.c | primary | A
- Betaflight 2025.12.5: config/config.c (DSHOT300 and pid_process_denom with bidir) | https://github.com/betaflight/betaflight/blob/2025.12.5/src/main/config/config.c | primary | A
- ExpressLRS 4.1.0: include/targets.h (OTA_VERSION_ID 4) | https://github.com/ExpressLRS/ExpressLRS/blob/4.1.0/src/include/targets.h | primary | A
- Betaflight docs: Build Options (ELRSV4) | https://betaflight.com/docs/wiki/guides/current/Build-Options | primary | A
- Betaflight 2026.6 Release Notes | https://betaflight.com/docs/wiki/release/Betaflight-2026-6-Release-Notes | primary | A
- JST PH connector datasheet (2 A, 10/20 mΩ) | https://cdn.sparkfun.com/assets/0/e/f/7/2/ePH.pdf | primary | A
- BETAFPV: BT2.0 Whoop Cable Pigtail (9 A / 15 A, PH2.0 4.5 A) | https://betafpv.com/products/bt2-0-1s-whoop-cable-pigtail | primary | B
- BETAFPV: Air75 II (weight, motors, flight time) | https://betafpv.com/collections/air-whoops/products/air75-ii-brushless-whoop-quadcopter | primary | B
- BETAFPV: 0802 Brushless Motors 2026 (KV, current, power) | https://betafpv.com/collections/motors/products/0802-brushless-motors-2026 | primary | B
- RaceDayQuads: GNB A30 connector (15 A / 30 A, 1.6 mΩ) | https://www.racedayquads.com/products/gaoneng-gnb-a30-connector-male-5-pack-1 | secondary | B
- RaceDayQuads: GNB27 connector (9 A / 15 A) | https://racedayquads.com/products/gnb27-connector-5-pack-choose-version | secondary | C
- Caddx: Walksnail Avatar HD Mini 1S Lite Kit | https://www.caddxfpv.com/blogs/news/review-walksnail-avatar-hd-mini-1s-lite-kit-ultra-lightweight-camera-vtx-combo-for-micro-drones | primary | B
- ReadyMadeRC: HDZero Whoop Lite Bundle | https://www.readymaderc.com/products/details/hdzero-whoop-lite-bundle-vtx-camera | secondary | B
- Oscar Liang: Best Tiny Whoop | https://oscarliang.com/best-tiny-whoop/ | secondary | B
- Oscar Liang: A30 battery connector | https://oscarliang.com/a30-battery-connector/ | secondary | B
- Oscar Liang: DJI O4 Air Unit (Lite) review | https://oscarliang.com/dji-o4-air-unit-lite/ | secondary | B
- Oscar Liang: ExpressLRS 4.0 | https://oscarliang.com/expresslrs-4/ | secondary | B

## notes
- Not verified against primary sources and marked in the text as estimates: the classes of 2S whoops, toothpicks and 3.5" (motors, weight, time), the typical values of `motor_idle`, `thrust_linear`, `vbat_sag_compensation` and the battery thresholds for a whoop, the amount of flash memory on the boards, cell life in cycles, the weight of the analog video chain.
- BETAFPV does not publish the contact resistance of BT2.0; the A30 and GNB27 data come from seller product pages. The GNB27 “27 A” rating from the name could not be confirmed.
- The years of the move from brushed to brushless motors and the MCU clock frequencies are given from memory.
- Specific models are named only as examples as of November 2026; product lines change faster than classes.
