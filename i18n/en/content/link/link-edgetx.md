---
id: link-edgetx
title: "An EdgeTX radio: models, mixes, telemetry and modules"
level: L2
readingTime: 50 min
firmware: EdgeTX 2.12 (checked against 2.12.5) · ExpressLRS 4.1 · Betaflight 2025.12
status: published
added: 2026-11-18
tags:
  - EdgeTX
  - radio
  - telemetry
  - CRSF
related:
  - link-protocols
  - link-elrs
  - bf-failsafe
  - bf-modes-osd
  - bf-rates-rc
  - tx-lua-widgets
next:
  - link-elrs
source: content/link/link-edgetx.md
source_hash: 6ac1c354eabc
---

## summary
EdgeTX is open firmware for radios: it reads the sticks and switches, computes the channels and hands them to the RF module, and in the other direction it receives telemetry and turns it into voice, logs and screens. This module covers the whole path: firmware and the SD card, radio settings, a quadcopter model step by step (Inputs → Mixes → Outputs, arm on CH5, modes, warnings), CRSF telemetry with a table of sensors and thresholds, Lua, external modules and CRSF speed, the USB simulator. After it you will build a model from scratch, compute exactly what goes over the air in microseconds and CRSF units, and set up voice alarms. The lab is pen-and-paper, no hardware: a model table, channel values and three logical switches.

## theory
### What EdgeTX is and which radio to get
EdgeTX is a fork of OpenTX (2021), now the main firmware for RadioMaster, Jumper, iFlight, HelloRadioSky, Flysky and some FrSky radios (there are no BetaFPV radios among the 2.12.5 release targets). The stable version as of November 2026 is **2.12.5** "Queen Anne's Revenge" (October 2026); 3.0 has not been released even as a release candidate: its pre-release was postponed (the 2.12.0 release notes), and only nightly builds are available. Radios on STM32F2 (old FrSky X7 / X9D+, Jumper T-Lite, the first RadioMaster TX12) stayed on the 2.11 branch, which gets fixes but no new features.

There are two interfaces, and their menus are named differently:

| Class | Screen | Examples (2.12.5 targets) | SD card archive | For whom |
|---|---|---|---|---|
| Monochrome | 128×64 | RadioMaster Pocket, Boxer, Zorro, TX12 MK2, GX12; Jumper T-Pro S, T20, T14, Bumblebee | `bw128x64.zip` | FPV: everything you need, cheaper, longer battery life |
| Wide monochrome | 212×64 | FrSky X9D+ 2019, X9E | `bw212x64.zip` | FrSky legacy |
| Color touchscreen | 480×272 and larger | RadioMaster TX16S / TX16S MK3 / TX15; Jumper T15, T16, T18; Flysky EL18, PL18 | `c480x272.zip`, `c480x320.zip`, `c320x480.zip` | widgets, maps, Yaapu, many models of different types |

Which radio to buy first (the question asked most often on forums): EdgeTX, a built-in ExpressLRS 2.4 GHz module, Hall-effect gimbals, an external module bay (in case you ever need 900 MHz, Crossfire or multiprotocol) and USB-C with joystick mode for the simulator. The form factor is chosen by grip: "gamepad" style (Pocket, Zorro, T-Pro) for thumbers, full-size (Boxer, TX16S) for pinchers. A color screen does not affect control. A price guideline as of November 2026 (not checked against price lists, changes fast): compact monochrome $60–100, full-size monochrome $100–160, color $200–350. Radio classes with prices and the order for buying the whole kit are in `f-starter-kit`.

### Firmware, bootloader and SD card
A radio consists of three parts, and their versions must match: the **bootloader**, the **firmware** and the **SD card contents** (scripts, themes, widgets; sounds are a separate archive per language). An SD card version mismatch is the most common cause of "after the update the sounds and scripts disappeared".

- **EdgeTX Buddy** (buddy.edgetx.org): a web flasher in a Chromium browser: the radio in DFU mode (off, connected over USB; each model has its own way to enter it), and Buddy downloads the firmware and assembles the SD card by itself.
- **Through the bootloader**: put the `.bin` in `/FIRMWARE`, choose `Flash bootloader` from the SD card menu, then power the radio on with the horizontal trims pushed inward (on most models) and choose `Write Firmware` in the bootloader. It does not depend on computer drivers.
- **EdgeTX Companion**: a desktop program: a model and radio settings editor, a radio simulator, a log viewer. It is convenient to build and check a model in it without powering up the transmitter.

SD card folders you need to know: `/MODELS` (`model1.yml`… and `labels.yml`), `/RADIO` (`radio.yml`: calibration, switches, internal module type), `/SCRIPTS`, `/WIDGETS`, `/SOUNDS/en`, `/LOGS`, `/SCREENSHOTS`, `/FIRMWARE`, `/THEMES`, `/TEMPLATES`. Settings are stored as YAML text, so **a radio backup = a copy of the whole SD card** (USB mode `USB Storage (SD)`), and to move one model its `.yml` is enough. Make a copy before every update.

### Radio settings (Radio Setup and Hardware)
| Setting | Where | Default (2.12.5) | What to set and why |
|---|---|---|---|
| Stick calibration | Hardware → Calibration | factory | after flashing and repairs; move the sticks in a cross to the stops with normal force, not in circles |
| Mode (stick layout) | Radio Setup | Mode 2 in factory builds (set when the firmware is built) | Mode 2: throttle and yaw on the left. It changes only which stick means what, not the channel order |
| Default channel order | Radio Setup | AETR on radios with an internal CRSF or multiprotocol module, otherwise RETA | AETR is what Betaflight, INAV, ArduPilot and PX4 expect. Applies only to new models |
| Battery meter range | Hardware | depends on the radio | 2S Li-Ion: 6.0–8.4 V; the `Battery low` alarm at 6.6–6.8 V |
| Audio / Haptic | Radio Setup | sound and vibration on | voice volume above beep volume: alarms must be audible at the field |
| ADC filter | Hardware, with a per-model override (`Global` / `Off` / `On`) | on | **turn off** for models with a flight controller: the filter smooths small stick movements, and the flight controller smooths them itself (RC smoothing, `bf-rates-rc`); double filtering adds latency and steps |
| Internal RF type | Hardware | per radio (`CRSF`, `Multi`…) | for a built-in ELRS, `CRSF`, 921k speed by default |
| Switch type | Hardware → Switches | per radio | `None` / `Toggle` (momentary) / `2POS` / `3POS`; after replacing a switch, change the type here |
| USB mode | Radio Setup | Ask | `Joystick` if the radio is often connected to a simulator |
| Inactivity | Radio Setup | 10 min | a reminder that the radio was left on |

### Inputs → Mixes → Outputs
Any model is a pipeline of three screens. **Inputs** prepare the "controls" (stick, weight, expo), **Mixes** decide what goes into a channel (and add several sources together), **Outputs** fit the channel to the "hardware" (reverse, center, limits). Inside, everything is computed in units of ±1024 = ±100 %.

{{diagram:edgetx-mixer-pipeline|The signal passes through Inputs, Mixes and Outputs and goes to the module: +50 % roll with expo 40 becomes 35.1 %, 1679 µs and 1279 in CRSF units.}}

Formulas (from `mixer.cpp`, `pulses/ppm.cpp`, `pulses/crossfire.cpp`):

- an Input line: `y = expo(x)·weight/100 + offset`; a Mix line: `y = curve(src)·weight/100 + offset`; the offset is added **after** the weight and is not scaled by it;
- several lines of one channel are combined by `Multiplex`: `Add` (sum), `Multiply`, `Replace` (replaces everything above while its switch is active);
- expo: `y = k·x³ + (1 − k)·x`, where `x` is the deflection 0…1 and `k` is expo/100. The ends do not change and the middle gets "softer": at expo 40, 50 % stick gives 35 %;
- to microseconds: `us = 1500 + 5.12·p`, so −100 % → 988, 0 → 1500, +100 % → 2012 (with Extended limits ±150 % → 732…2268);
- to CRSF: `crsf = 992 + trunc(out·4/5)` (C integer division: the fraction is truncated toward zero), where `out = 10.24·p`: −100 % → 173, 0 → 992, +100 % → 1811. Betaflight converts back as `0.62477·crsf + 881`: 989.1 / 1500.8 / 2012.5 µs. The Receiver tab gets the integer part, 989 / 1500 / 2012; after the ELRS 10-bit packing the center may show 1499–1500. That is not a calibration error.

{{diagram:chart-edgetx-expo|Expo in the radio bends the stick response with a cubic curve: at 40 % the stick's midpoint gives 35 % instead of 50 %, and the ends stay in place.}}

**Expo and rates belong in the flight controller, not in the radio.** Betaflight, INAV and ArduPilot compute the rotation rate from the stick position with their own rates and expo (`bf-rates-rc`). Expo in the radio is applied on top: the curve becomes the product of the two, it is not visible in the configurator or in Blackbox, and less resolution is left around the stick center. The same goes for weight: a weight of 80 % on roll does not "soften" control, it cuts the maximum rate by 20 % and breaks the `rxrange` check. The rule for aircraft with a flight controller: Inputs at weight 100, expo 0; everything else in the flight controller. Expo, dual rates and curves in the radio are for where there is no flight controller: a glider on a PWM receiver, a car, a boat.

{{lesson:bf-rates-rc|How Betaflight turns channel microseconds into deg/s: the Actual formula, RC smoothing and feedforward, which is why expo in the radio stays at zero.}}

**Trims are turned off for a multicopter.** A trim shifts the channel center (up to ±25 %, about ±128 µs; the default `Fine` step is 0.4 %). The flight controller takes the shifted center as a command: in Acro the aircraft slowly rotates, and on yaw the arming check may fail. Drift is cured by accelerometer calibration and tuning, not by trim. To turn them off: in every Inputs line set the `Trim` field to `OFF` (or remove `Trim` in the Mixes lines). The freed trim buttons can be used as sources.

### A quadcopter model step by step
The example's switch layout: `SA` two-position, `SB` and `SC` three-position, `SD` two-position. A two-position switch as a source gives −100 % (up) and +100 % (down), a three-position one −100 / 0 / +100.

| Step | Screen | What to do | Why |
|---|---|---|---|
| 1 | Model Select | New Model, named after the aircraft | one model, one aircraft |
| 2 | Model Setup → Internal RF | Mode `CRSF`, Channel Range CH1–CH16, your own `Receiver No.` | built-in ELRS; with an external module, Internal RF `Off`, External RF `CRSF` |
| 3 | Inputs | I1 Ail, I2 Ele, I3 Thr, I4 Rud: weight 100, expo 0, Trim `OFF` | the AETR order is created automatically; you only turn off the trims |
| 4 | Mixes | CH1…CH4 ← I1…I4, weight 100 | already created by the template |
| 5 | Mixes | CH5 ← `SA`, weight 100 | arm: 988 µs disarmed, 2012 armed |
| 6 | Mixes | CH6 ← `SB`, CH7 ← `SD`, CH8 ← `SC`, weight 100 | modes: the three positions fall into the ranges 900–1300 / 1300–1700 / 1700–2100 (`bf-modes-osd`) |
| 7 | Outputs | change nothing: Min −100, Max +100, Subtrim 0, center 1500 | endpoints and center are fitted in the flight controller (`rxrange`), not here |
| 8 | Model Setup → Pre-start Checks | Throttle state on; Switch positions: `SA↑` and the rest in their "safe" positions | the radio will not silently start transmitting with arm on |
| 9 | Model Setup → Other | ADC filter `Off` | see the radio settings table |
| 10 | Model Setup → Timer 1 | Mode `ON`, Switch `SA↓`, voice countdown | air time by arm |
| 11 | Telemetry | `Discover new` with the aircraft powered, then `Stop` | the sensors appear |
| 12 | Logical switches + Special functions | alarms for LQ, voltage, capacity; `SD Logs` | details below |

This is a minimal 8-channel layout: CH8 = AUX4, and in general AUXn = CH(n + 4). The team layout from `bf-modes-osd` (ANGLE on AUX3 = CH7, FAILSAFE on AUX6 = CH10, BEEPER on AUX7 = CH11, PREARM on AUX8 = CH12) needs mixes up to CH12, and the Channel Range CH1–CH16 from step 2 allows that. Use one layout on all aircraft and check it against `aux` in the flight controller.

### Arm on CH5, warnings and failsafe
**Why arm goes on CH5 specifically.** ExpressLRS sends the arm state as a separate bit in every packet and switches its own behavior by it (power, telemetry). By default `Arm using: CH5`: the module considers the aircraft armed when the CH5 value is above the middle, more than 992 in CRSF units, that is, above 1500 µs (`CRSF_to_BIT`). That is why CH5 gets a two-position switch with full travel; a three-position switch, or a "weight 50 + offset 50" mix that gives exactly 1500 µs in the "off" position, leaves zero margin to the threshold. ELRS 4 and EdgeTX 2.11+ offer an alternative: the model's module settings get `Arm using: Switch` (the line is shown only when the module has answered as ELRS 4.0+); details in `link-elrs`. In the flight controller arming is still assigned to a channel.

**Power-up warnings.** `Throttle state` triggers if the throttle is more than 1.6 % above the bottom stop (16 units out of 1024), `Switch positions` if a switch is not in its stored position (a new model checks all switches, in the "up" position). While a warning is on screen the radio waits; do not disable them "because they get in the way", set the right positions instead.

**Failsafe.** The `Failsafe mode` item (`Not set` / `Hold` / `Custom` / `No pulses` / `Receiver`) exists only for protocols where the receiver executes it on the radio's command: FrSky D16 and ACCESS, R9M, Flysky AFHDS, some multiprotocol-module protocols. CRSF (ELRS, Crossfire), Ghost, SBUS and PPM have no such item: on link loss the receiver stops outputting frames, and the flight controller decides what to do (`link-elrs`, the section on receiver failsafe, and `bf-failsafe`).

### Reference: what a quadcopter model uses
| Item | Screen | New model default | Range | For a quadcopter |
|---|---|---|---|---|
| Internal RF → Mode | Model Setup | `Off` in an empty model | Off, CRSF, Multi, XJT… per radio | `CRSF` for a built-in ELRS |
| Baudrate | Internal: Hardware; External: in the model | 921k internal, 400k external | 115k, 400k, 921k, 1.87M, 3.75M, 5.25M | see the section on modules |
| Channel Range | Internal / External RF | CH1–CH16 | start and number of channels | leave as is |
| Receiver No. | Internal / External RF | 0 | 0–63 | unique within the protocol |
| Arm using | Internal / External RF (ELRS 4+) | `CH5` | CH5, Switch | `CH5` unless there is a reason otherwise |
| Throttle → Source | Model Setup | Thr | any source | Thr |
| Throttle → Trim idle only | Model Setup | off | on/off | off (for combustion engines) |
| Pre-start → Throttle state | Model Setup | on | on/off, Custom position | on |
| Pre-start → Switch positions | Model Setup | all switches, "up" | off or a position for each | arm in "off" |
| Trims → Trim Step | Model Setup | Fine (0.4 %) | Exponential, Extra Fine 0.2 %, Fine, Medium 0.8 %, Coarse 1.6 % | does not matter: trims are off |
| Trims → Extended trims | Model Setup | off (±25 %) | ±25 / ±100 % | off |
| Other → ADC filter | Model Setup | `Global` (= on) | Global, Off, On | `Off` |
| Timer 1…3 → Mode | Model Setup | `OFF` | OFF, ON, Strt (Start), THs (Throttle), TH% (Throttle %), THt (Throttle Start) | `ON` + the arm switch |
| Input: Source / Weight / Offset | Inputs | stick / 100 / 0 | weight and offset ±100 | 100 / 0 |
| Input: Curve | Inputs | Expo 0 | Diff, Expo, Func, Custom | Expo 0 |
| Input: Trim | Inputs | on | OFF or any trim | `OFF` |
| Mix: Source / Weight / Offset | Mixes | I1…I4 / 100 / 0 | weight and offset ±500 (`gvars.h`), ±100 in practice | 100 / 0 |
| Mix: Switch | Mixes | none (the line is always active) | switch, LS, mode | none |
| Mix: Multiplex | Mixes | `Add` | Add, Multiply, Replace | `Add` |
| Mix: Delay / Slow | Mixes | 0 | seconds | 0 (a delay in control) |
| Output: Min / Max | Outputs | −100 / +100 | up to ±150 with Extended limits | do not change |
| Output: Subtrim / PPM Center | Outputs | 0 / 1500 µs | ±100 % / center ±500 µs | do not change |
| Output: Inverted | Outputs | off | on/off | off: reverse in the flight controller |

The defaults come from `model_init.cpp`, `edgetx.cpp`, `gvars.h` and `translations/i18n/en.h` at tag v2.12.5.

### Timers, logical switches, special functions
- **Timers** (3 of them): count time by a switch or the throttle; `Persistent` keeps the value between power-ups, handy for total flight time.
- **Logical switches** (`L01`…`L64`): conditions that behave like switches: `a<x`, `a>x`, `|a|>x`, `AND`, `OR`, `XOR`, `Edge`, `Sticky`, `Timer`. Each has an `AND switch` (the condition is evaluated only while that switch is on), `Delay` (how long the condition must hold) and `Duration`. Important: if the source is a telemetry sensor and there is no telemetry, the switch is **false**, so an LQ alarm will not fire on a complete link loss; for that there is the built-in "telemetry lost".
- **Special functions** (`SF1`…`SF64`, global ones in Radio Settings): an action triggered by a switch or LS: `Play Track` (a sound file), `Play Value` (speak a sensor value), `Play Sound`, `Haptic`, `Vario`, `Inst. Trim`, `Screenshot` (into `/SCREENSHOTS`), `SD Logs` (CSV recording at a set interval), `Override` (force a channel value), `Reset`, `Set` (a timer), `Adjust` (a global variable), `Volume`, `Backlight`, `Lua Script`, `RangeCheck`, `ModuleBind`, `SetFailsafe`, `Trainer`.
- **Global variables** (`GV1`…): numbers substituted for a weight, offset or limit, and they can depend on the mode; the radio's **Flight modes** (`FM0`…`FM8`): sets of trims and GVs switched by a switch. They have nothing to do with the flight controller's modes; on a quadcopter with a flight controller they are hardly needed, on gliders and planes without one they are the main tool.

`SD Logs` is also a way to find a crashed aircraft: the function writes `/LOGS/<model>-<date>.csv` with all sensors, sticks and channels in µs; if the flight controller sends GPS, the `GPS` column keeps the last received coordinates. The same coordinates stay on the telemetry screen after link loss, and the standard SD card of color radios has the `GPS Model Locator` and `Model Locator (by RSSI)` tools. The search procedure is in `ops-field`.

### CRSF telemetry: sensors and thresholds
Sensors appear after `Telemetry → Discover new` with the link running. The first ten come from the receiver itself (link statistics), the rest from the flight controller, if telemetry is enabled in it and the flight controller's TX wire goes to the receiver's RX (`link-protocols`). The names come from `telemetry/crossfire.cpp` and `translations/untranslated.h`.

| Sensor | Unit | What it is | Typical alarm |
|---|---|---|---|
| `1RSS`, `2RSS` | dBm | signal level at the receiver antennas | mode sensitivity + 10 dB (250 Hz: −108 → −98 dBm) |
| `RQly` | % | LQ: the share of packets received by the receiver | warning 70–80, critical 50 |
| `RSNR` | dB | signal-to-noise ratio at the receiver | drops before LQ; the threshold depends on the mode |
| `ANT` | — | the receiver's active antenna | — |
| `RFMD` | — | link mode number (the table in `link-elrs`) | — |
| `TPWR` | mW | current transmitter power | useful to announce with Dynamic power |
| `TRSS`, `TQly`, `TSNR` | dBm, %, dB | the same for the return link (telemetry), measured by the radio's module | `TQly` below 50: telemetry is unreliable |
| `RxBt` | V (0.1) | battery voltage from the flight controller | LiPo: 3.5 V × cell count, critical 3.3 V × cells; Li-Ion 3.3 and 3.0 V × cells, a 1S whoop 3.3–3.4 and 3.1–3.2 V (table and reasons in `f-power`) |
| `Curr` | A | current | — |
| `Capa` | mAh | capacity used | 80 % of battery capacity |
| `Bat%` | % | remaining, as estimated by the flight controller | 20–25 % |
| `GPS`, `GSpd`, `Hdg`, `GAlt`, `Sats` | coordinates, km/h, °, m, count | GPS data | `Sats` below the threshold set in the flight controller |
| `Alt`, `VSpd` | m, m/s | altitude and vertical speed (baro) | the source for `Vario` |
| `Ptch`, `Roll`, `Yaw` | rad | angles | — |
| `FM` | text | flight controller mode; Betaflight sends `ACRO`, `ANGL`, `HOR`, `AIR`, `RTH`, `!FS!` and a suffix before arming: `*` ready, `!` arming blocked, `?` GPS Rescue not ready; INAV has its own set of strings without suffixes (`inav-telemetry-gcs`) | — |

Less common are `RRSP`, `RPWR`, `TRSP`, `TFPS` (Crossfire frames), `ASpd`, `RPM`, `Temp`, `Cels`, `Volt`, `Date`. The thresholds in the table are community practice and follow from the sensitivity table; they are not a standard, so tune them for your aircraft.

Built-in alarms (the `Rqly` section of the Telemetry page for CRSF): `Low alarm` 45 and `Critical alarm` 42, values inherited from FrSky RSSI. For CRSF the radio compares `RQly` with them, so "RF signal low" sounds at LQ below 45 %, which is too late. That is why LQ and the battery are announced with your own logical switches (in the practice). Betaflight's `RxBt` is the whole battery voltage, or the per-cell average with `report_cell_voltage = ON`; set the threshold in the same units.

### Lua scripts
| Folder | What is there | How it runs |
|---|---|---|
| `/SCRIPTS/TOOLS` | tools: `elrs.lua`, `bf.lua` | color: quick menu Tools → Apps; monochrome: SYS → Tools |
| `/SCRIPTS/TELEMETRY` | telemetry screens of monochrome radios | Model → Display |
| `/WIDGETS/<name>/main.lua` | widgets for color radios | quick menu UI Setup → Screen 1… |
| `/SCRIPTS/FUNCTIONS` | background scripts | the `Lua Script` special function |
| `/SCRIPTS/MIXES` | mix scripts | Model → Mixer Scripts; do not use for the main channels: a killed script disables its mix line |

- **ExpressLRS Lua** (`elrs.lua`): module and receiver setup: packet rate, telemetry ratio, power, binding, Wi-Fi. One file for all ELRS versions; `C` in the corner means the receiver is connected.
- **Betaflight Lua** (`bf.lua` + the `/SCRIPTS/BF` folder): PID, rates, VTX from the radio. It works through MSP packed into telemetry frames, so it needs: telemetry enabled in Betaflight, an ELRS telemetry ratio other than `Off`, EdgeTX 2.4.0+. The Betaflight project recommends 400k for CRSF; at higher speeds the script usually works too, but if you get link errors, start with 400k. With sparse telemetry (1:64 and slower) the pages load slowly; set the ratio to 1:8 or faster while tuning.
- **Yaapu Telemetry**: a screen and widget for ArduPilot (horizon, mode, messages) over CRSF or FrSky passthrough; it is configured on the ArduPilot side and only mentioned here.

{{lesson:tx-lua-widgets|Your own Lua telemetry widget for a color radio: the lifecycle, CRSF sensors, debugging in the simulator and a ready LinkBox with a test harness.}}

### External modules, CRSF speed, multiprotocol
- **Bays.** JR (full-size: TX16S, Boxer), Nano / Lite (compact: Zorro, Pocket, X-Lite; the mechanics differ between manufacturers, so check the compatibility of the specific pair). The module is powered by the radio: a 1 W ELRS module noticeably shortens run time.
- **Internal vs External.** Only one module is active in a model: with an external one, `Internal RF: Off`, `External RF: CRSF`. An old radio with an internal CC2500 or multiprotocol module is moved to ELRS either with an external module in the bay or by replacing the internal board, if the manufacturer makes one; after the replacement change `Hardware → Internal RF type`.
- **CRSF speed** (radio ↔ module, not to be confused with the 420000 baud of receiver ↔ flight controller): the higher the packet rate, the more frames per second the UART has to carry.

| Baudrate | Recommended packet rate (ELRS documentation, with margin) | Hard firmware limit (`CRSFHandset.cpp`, 4.1.0) | Notes |
|---|---|---|---|
| 115k | — | 250 Hz (200 Hz on a half-duplex module) | only very old radios; mixer period 16 ms |
| 400k | up to 250 Hz | 500 Hz | the default for an external module; a safe choice for Lua |
| 921k | up to 500 Hz | none | the default for an internal CRSF module |
| 1.87M | F1000 and other modes with 1000 frames per second from the radio | none | the limit of the Jumper T-Pro / T20 internal module |
| 3.75M, 5.25M | headroom | none | 5.25M is not available to an external module on STM32F4 radios |

Choose the speed by the second column: it leaves the UART headroom for telemetry and Lua. The third column is where ELRS itself lowers the packet rate if the speed is too low for the selected mode: at 400k the 500 Hz mode still works, F1000 no longer does. The `Status` line of the module settings shows the actual rate (for example `500 Hz` with F1000 selected at 400k). On old FrSky X9D+ and X7 radios with a slow inverter, `Sample Mode: OneBit` helps.

{{lesson:link-elrs|Which packet rate to choose for range and latency: each mode's sensitivity, the telemetry ratio and the link margin.}}

- **Multiprotocol module** (MPM, 4-in-1: CC2500, NRF24L01, A7105, CYRF6936): one board for FrSky D8/D16, Flysky AFHDS 2A, DSM2/DSMX, Futaba S-FHSS and dozens of toy protocols. Needed for BNF aircraft and old receivers; for new builds, ELRS.

### Model match and model copies
The radio reports `Receiver No.` (0–63) to the module as the model number; EdgeTX shows `ID is unique` or `ID used in: …` next to it. On FrSky and DSM the receiver stores the number at binding and ignores other models. On ELRS the number works only if `Model Match` is enabled in the Lua script (`link-elrs`); otherwise any model with the same phrase controls any receiver. A copy of a model inherits the number, so after `Duplicate` change `Receiver No.` right away, or the settings of "the wrong" aircraft (other switches, another arm) will put this one in the air.

### Trainer and the USB simulator
- **Trainer:** `Master` (instructor) and `Slave` (student) connect by cable through the `Jack` socket, over SBUS/CPPM in the module bay, over Bluetooth, through the multiprotocol module or CRSF. The instructor hands chosen channels to the student with a switch (the `Trainer` special function).
- **Simulator:** over USB the radio selects `USB Joystick (HID)` and shows up on the computer as a game controller without drivers. In `Classic` mode channels CH1–CH8 are axes and CH9–CH32 are buttons; `Advanced` lets you assign an axis or button to each channel. Make a separate model for the simulator with Internal and External RF off: the radio does not transmit and lasts longer. The simulator reads the same channels after the mixes, so the arm switch and modes work as in real life. How many hours to fly before the first real flight and which simulator to choose are in the `ops-pilot-training` module; the community guideline is at least 5–10 hours in Acro.

### Where it fits in the system
- **Takes in:** channel and mode-range requirements from the flight controller (`bf-modes-osd`, `bf-rates-rc`), link and arm parameters from ExpressLRS (`link-elrs`), CRSF telemetry frames over the return link (`link-protocols`).
- **Puts out:** 16 channels in CRSF units to the module and on to the receiver, the model number for Model Match, voice alarms and a CSV log for the pilot; the last coordinates for the search procedure in `ops-field`.
- **If you get this wrong:** expo or weight in the radio distort the rates and `rxrange` in `bf-rates-rc`; an arm that does not use the full travel of CH5 leaves ELRS in the "disarmed" state, so Dynamic Power will not raise the power to maximum on telemetry loss (`link-elrs`); trims left on cause drift in Acro; a model copy with the same receiver number breaks the failsafe check from `bf-failsafe` on someone else's aircraft.

## practice
The lab is pen-and-paper: build a model on paper (or in Companion), compute what goes over the air, and design the alarms. No hardware needed. The example aircraft: a 5" quadcopter, Betaflight, ELRS 250 Hz, a 6S 1300 mAh battery; the switch layout as in the theory (`SA` 2-pos., `SB` 3-pos., `SC` 3-pos., `SD` 2-pos.).

### Step 1. The model table
Fill in three tables: Inputs (4 lines: source, weight, expo, trim), Mixes (8 lines: channel, source, weight, offset) and Outputs (8 lines: Min, Max, Subtrim, center, reverse). Channel assignment: CH1–CH4 AETR, CH5 arm (`SA`), CH6 ACRO / ANGLE / HORIZON mode (`SB`), CH7 PREARM (`SD`), CH8 BEEPER (`SC`). Expected result: Inputs are 100 / 0 / `OFF` everywhere, Mixes have weight 100 and offset 0 everywhere, Outputs are at the defaults. If something came out differently, write down why.

### Step 2. Channel values
Compute by hand with the formulas from the theory (`us = 1500 + 5.12·p`, `crsf = 992 + trunc(10.24·p·4/5)`, `BF = 0.62477·crsf + 881`) the values for the positions in the table below, then compare. The table was produced by a script that reproduces the integer arithmetic of `mixer.cpp` and `crossfire.cpp` (run while preparing the module; a hand calculation may differ by 1 unit):

```
channel and position                       %   int.    us  CRSF   BF, us
CH1 Ail  stick +50 %, expo 0            50.0    512  1756  1401   1756.3
CH1 Ail  stick +50 %, expo 40           35.1    359  1679  1279   1680.1
CH2 Ele  stick -100 %                 -100.0  -1024   988   173    989.1
CH3 Thr  stick -100 % (idle)          -100.0  -1024   988   173    989.1
CH3 Thr  stick +20 %                    20.0    205  1602  1156   1603.2
CH4 Rud  stick 0 %                       0.0      0  1500   992   1500.8
CH5 SA up (disarmed), weight 100      -100.0  -1024   988   173    989.1
CH5 SA down (armed), weight 100        100.0   1024  2012  1811   2012.5
CH5 SA up, weight 50 + offset 50         0.0      0  1500   992   1500.8
CH6 SB middle                            0.0      0  1500   992   1500.8
CH8 SC up, weight 80                   -80.0   -819  1091   337   1091.5
CH8 SC down, weight 80                  80.0    819  1909  1647   1910.0
expo 40: 25 % -> 15.6 | 50 % -> 35.1 | 75 % -> 61.9 | 100 % -> 100.0
```

Answer three questions in writing. (a) By how many degrees per second does the roll command change at 50 % stick if Betaflight has linear rates with a 670 deg/s maximum and someone set expo 40 in the radio? Answer: 335 → 235 deg/s, and the configurator does not show it. (b) What is dangerous about the "weight 50 + offset 50" line on CH5? Answer: "off" = 992, and ELRS treats anything strictly above 992 as armed, a margin of zero units. (c) Do 1091 and 1909 µs (weight 80 on CH8) fall into the mode ranges 900–1300 and 1700–2100? Yes, with a margin of 209 µs to the boundaries: weight 80 is acceptable for a switch, but it gains nothing.

### Step 3. Three logical switches
Design the alarms and write them as a table: function, V1, V2, AND switch, Delay, and the related Special function. A sample with the threshold calculation:

| LS | Function | V1 | V2 | AND | Delay | Special function |
|---|---|---|---|---|---|---|
| `L01` | `a<x` | `RQly` | 70 | `SA↓` | 0.5 s | `Play Track` "LQ low" + `Play Value RQly`, repeat 5 s |
| `L02` | `a<x` | `RxBt` | 21.0 V | `SA↓` | 2.0 s | `Play Value RxBt`, repeat 10 s |
| `L03` | `a>x` | `Capa` | 1040 mAh | — | 0 | `Play Track` "battery", `Haptic`, repeat 15 s |

The calculation: `L02`: 6 cells × 3.5 V = 21.0 V; the 2 s delay filters out sag under throttle (without it the alarm will shout at every acceleration). `L03`: 80 % of 1300 mAh = 1040 mAh; `Capa` does not depend on sag, so no delay is needed. `L01`: the threshold is above the built-in 45 %; at 250 Hz and a telemetry ratio of 1:64 the link statistics update rarely, and the 0.5 s delay removes single dips. `AND = SA↓` disables the alarms on the bench until the aircraft is armed. Check yourself: what will the radio say on a complete link loss? `L01` stays silent (no telemetry, so the switch is false), and the built-in "telemetry lost" fires.

Recompute the table for your own aircraft (cell count, capacity, link mode) and add a fourth Special functions line: `SD Logs` at a 1.0 s interval on `SA↓`.

### Moving to real hardware
Props stay off until the last item. Create the model on the radio, run `Discover new` with the aircraft powered, open the Receiver tab in Betaflight Configurator and compare: center 1499–1500, endpoints 988–989 and 2012, AETR order, CH5 jumping between the extreme values. Check arm and disarm with the switch, turn the radio off and make sure the flight controller went into failsafe (`bf-failsafe`). Record a log (`SD Logs`), open the CSV in Companion or a spreadsheet and find the `RQly`, `RxBt`, `CH5(us)` columns. Criteria: the stick values (CH1–CH4) match the calculation within ±2 µs; in the Hybrid and Wide switch modes (`link-elrs`) the receiver outputs switch channels as 1000 / 1500 / 2000 µs (arm 1000 / 2000), which is ELRS packing, not a model error; the `L02` alarm fires when a battery discharged to the threshold is connected, or with a temporarily raised threshold; the log has all three sensors.

Self-check: the lab is done when: (1) the three model tables are filled in and match the expected result of step 1 (Inputs 100 / 0 / `OFF`, Mixes weight 100 and offset 0, Outputs at the defaults), and every difference has its reason written down; (2) the values in µs and CRSF units have been computed by hand for all positions from step 2 and agree with the table within 1 unit, and your answers to questions (a)–(c) match the ones given: 335 → 235 deg/s, a margin of 0 units, a margin of 209 µs; (3) the three logical switches have been recomputed for your aircraft: the `L02` threshold equals the cell count × 3.5 V, the `L03` threshold is 80 % of battery capacity, and for each delay you wrote down what it filters out; (4) for the hardware path, your records contain a screenshot of the Receiver tab and a CSV log with `RQly`, `RxBt` and `CH5(us)`, and they pass the criteria from the "Moving to real hardware" section. Items 1–3 are the calculation path, item 4 only if you have a radio and an aircraft.

**Reference answer for self-check.** A correct step 3 table for your own aircraft differs from the sample only in the V2 numbers (cells × 3.5 V and 0.8 × capacity; in the sample, 21.0 V and 1040 mAh): `AND` is the arm switch, `L01` and `L02` have a delay and `L03` has zero. Two common mistakes: `L02` has no delay, so the alarm shouts at every acceleration; the `L02` threshold is written in units other than those the flight controller sends `RxBt` in (the whole battery, or the per-cell average with `report_cell_voltage = ON`), so the alarm sounds all the time or never. The third is expecting `L01` to announce a complete link loss: without telemetry it is false, and the loss is announced by the built-in "telemetry lost".

## diagnostics
- **Symptom:** the telemetry list has only link sensors (`1RSS`, `RQly`, `TPWR`…), no `RxBt`, `FM`, `GPS`.
  Possible cause: the flight controller does not send telemetry: it is disabled in the settings, or the flight controller's TX wire is not connected to the receiver's RX.
  What to do: enable telemetry in the flight controller, check the wire (`link-protocols`), then `Delete all` and `Discover new`.
- **Symptom:** no sensors at all, `Discover new` finds nothing.
  Possible cause: ELRS telemetry ratio `Off`, the receiver is not bound, the model has the wrong module selected (Internal instead of External) or the wrong protocol.
  What to do: open `elrs.lua` and see whether there is a `C` in the corner; check the module Mode and the ratio.
- **Symptom:** at power-up the radio shows "SWITCH WARNING" ("CONTROL" on color radios) or "Throttle not idle" and goes no further.
  Possible cause: a switch is not in the position set in Pre-start Checks, or the throttle is not at zero; a model copy inherited the positions from the original.
  What to do: return the switches and throttle; if the positions are set wrong, put the switches where they should be and store them with a long press of Enter on the Switch positions line.
- **Symptom:** after calibration the channel center is 1480–1520 instead of 1500, and the endpoints do not reach 988 / 2012.
  Possible cause: calibrated in circles or by forcing past the stops; a trim or Subtrim is on; the weight in Inputs is below 100.
  What to do: recalibrate in a cross; zero the trims (`Reset` in Trims), check Inputs and Outputs; a center of 1499–1500 in Betaflight with 1500 on the radio is normal.
  Consequences: drift in Acro, arming refused because throttle or yaw is not at zero.
- **Symptom:** `Status` shows 500 Hz with F1000 selected in Lua (or 250 Hz with 500 Hz selected on an old radio); telemetry drops out, Lua scripts load with errors.
  Possible cause: the CRSF speed is too low for the mode (400k for F1000, 115k for 500 Hz) or too high for the radio and the module.
  What to do: 921k for 500 Hz, 1.87M for F1000; on errors, go back to 400k and 250 Hz; on old X9D+ / X7 (EdgeTX 2.11) turn on `OneBit`.
- **Symptom:** you selected the "Quad 2" model, but aircraft no. 1 responds (or both do).
  Possible cause: the model is a copy with the same `Receiver No.`; Model Match is off in ELRS, and the phrase is shared.
  What to do: a unique `Receiver No.` for each model, Model Match `On`, and write the number into the receiver again (`link-elrs`).
  Consequences: arming with a different switch, someone else's modes: the aircraft takes off with an unexpected configuration.
- **Symptom:** the aircraft arms, but when telemetry dips Dynamic Power does not raise the power to maximum, and the link is lost earlier than usual.
  Possible cause: arming in the flight controller is not on CH5, or CH5 does not go above the middle, so ELRS considers the aircraft disarmed.
  What to do: arm on CH5 with full travel, or `Arm using: Switch`.
- **Symptom:** the battery voice alarm fires at every acceleration.
  Possible cause: the logical switch has no delay, and the threshold is compared with the instantaneous sag.
  What to do: `Delay` of 1.5–2 s, or an alarm on `Capa`.
- **Symptom:** after an update the voice and scripts are gone, or widgets/tools show script errors (EdgeTX 2.12 does not check the SD card version at power-up, so there is no warning).
  Possible cause: the SD card contents are from another EdgeTX version.
  What to do: unpack the SD card archive for your version and screen class over the old contents (models and your own scripts are not overwritten), and add the sound pack.
- **Symptom:** the simulator does not see the radio, or the axes are mixed up.
  Possible cause: `USB Storage` selected instead of `Joystick`; a charge-only cable; the model's channel order is not AETR.
  What to do: USB mode `Ask` or `Joystick`, a separate model for the simulator, calibration in the simulator itself.

## checklist
- Bootloader, firmware and SD card versions match; a copy of the SD card is saved.
- Sticks calibrated; Mode and the AETR order set before creating models.
- Model: one active RF module, a unique `Receiver No.`.
- Inputs: weight 100, expo 0, trims `OFF`; Outputs at the defaults.
- CH5 is a two-position arm switch with full travel (or `Arm using: Switch`).
- Throttle state and Switch positions are enabled and set sensibly.
- ADC filter `Off` for models with a flight controller.
- Sensors discovered; alarms for LQ, voltage and capacity checked on the bench.
- `SD Logs` records on arm; the radio's date and time are set.
- CRSF speed matches the packet rate; `Status` shows the expected rate.
- For the simulator, a separate model without RF.

## references
- EdgeTX, source code, tag v2.12.5 (mixer.cpp, model_init.cpp, pulses/crossfire.cpp, telemetry/crossfire.cpp, telemetry/crossfire.h, logs.cpp) | https://github.com/EdgeTX/edgetx/tree/v2.12.5/radio/src | primary | A
- EdgeTX v2.12.5 — release notes | https://github.com/EdgeTX/edgetx/releases/latest | primary | A
- EdgeTX User Manual v2.12 (repository, 2.12 branch) | https://github.com/EdgeTX/edgetx-user-manual | primary | A
- EdgeTX User Manual — Internal / External RF | https://github.com/EdgeTX/edgetx-user-manual/blob/2.12/color-radios/model-settings/model-setup/internal-external-rf.md | primary | A
- ExpressLRS — Radio Preparation (baud rate, ADC filter, Internal / External RF) | https://www.expresslrs.org/quick-start/transmitters/tx-prep/ | primary | A
- Betaflight TX Lua Scripts — README (requirements: telemetry, EdgeTX 2.4.0+, 400K) | https://github.com/betaflight/betaflight-tx-lua-scripts | primary | A
- Betaflight, src/main/rx/crsf.c — converting CRSF units to microseconds | https://github.com/betaflight/betaflight/blob/master/src/main/rx/crsf.c | primary | A
- ExpressLRS 4.1.0, src/lib/Handset/CRSFHandset.cpp (`getMinPacketInterval`: the packet-rate limit by UART speed) | https://github.com/ExpressLRS/ExpressLRS/blob/4.1.0/src/lib/Handset/CRSFHandset.cpp | primary | A

## notes
Checked against the EdgeTX v2.12.5 source (commit 0ebe2e98), the 2.12 branch of the manual (October 2026), ExpressLRS 4.1.0 and Betaflight 2025.12. Not checked against primary sources: radio prices, the lists of STM32F2 radios, the compatibility of specific Nano / Lite modules between manufacturers, Yaapu details and the exact wording of on-screen warnings. Menu item names follow the color interface; on monochrome radios the same settings are gathered on one page, MODEL → SETUP.
