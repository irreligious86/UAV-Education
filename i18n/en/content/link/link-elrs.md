---
id: link-elrs
title: "ExpressLRS: packet rate, telemetry, LQ"
level: L2
readingTime: 40 min
firmware: ExpressLRS 4.1 (checked against 4.1.0)
status: published
added: 2026-11-07
tags:
  - ExpressLRS
  - telemetry
related:
  - link-protocols
  - bf-failsafe
  - bf-rates-rc
  - rf-link-budget
  - link-edgetx
  - tx-lua-widgets
next:
  - link-vtx
source: content/link/link-elrs.md
source_hash: 3751daba3989
---

## summary
ExpressLRS (ELRS) is an open radio control system that has become the standard in FPV. This module explains the main trade-offs: packet rate versus range, 2.4 GHz versus 900 MHz, how much airtime to give to telemetry. It walks through the code to show how the binding phrase becomes a UID and where Model Match is checked, what regulatory domains and LBT do in a CE build, and how to turn an RSSI margin into range. It teaches you to bind a receiver, read LQ and RSSI in the log to tell a link problem from a setup problem, and move from ELRS 3.x to 4.x without losing contact with half your fleet. All figures come from the ELRS 4.1.0 source; the differences in 3.x are collected in a separate table.

## theory
### Packet rate: latency versus sensitivity
Packet rate is how many control packets per second the radio sends. More packets mean lower latency, but each packet is shorter and the receiver's sensitivity is worse. That is why high rates are for racing and freestyle close in, and low rates for long-range flights.

2.4 GHz modes in ELRS 4.1 (the set depends on the radio chip of the receiver and the module):

- LoRa: 50, 150, 250, 500 Hz, the main set; the lower, the farther;
- FLRC: F500, F1000, the lowest latency and shorter range. The handset ↔ module link speed limits the handset's frame interval (the mode interval × the number of repeats, `CRSFHandset.cpp:413–428`, `common.cpp:126–139`): at 115200, no faster than 4 ms (250Hz, D250; on a half-duplex module 5 ms: 200 Hz on 900 MHz, 150 Hz on 2.4 GHz); at 400k, no faster than 2 ms (500Hz, F500, D500); F1000/K1000 (1 ms) only at other speeds, for example 921k. A higher speed is set for telemetry and Lua bandwidth;
- D250, D500: FLRC at 1000 Hz with repeats (DVDA): in D500 every packet is sent twice, in D250 four times; more robust against interference;
- Full Resolution: 100Hz Full, 333Hz Full, all channels at 10 bits for wings and complex mixes;
- only on the LR1121 chip: K1000, DK250, DK500, FSK with forward error correction (FEC), the counterparts of F1000/D250/D500 for the noisy air at races.

On 900 MHz (868/915) the rates are lower: 25, 50, 100, 100Hz Full, 200 Hz and D50 (50 Hz with four repeats). On the LR1121 there are also 250 Hz, 200Hz Full and K1000 Full (FSK, the maximum throughput for MAVLink). The longer wavelength diffracts around obstacles and gets through foliage better: the choice for wings and long routes.

In 4.x, on dual-band modules you first choose `RF Band` (2.4GHz / 900MHz / X-Band) in the Lua script, and the Packet Rate list shows only that band's modes (3.x had one combined list).

### Modes and sensitivity: the table (ELRS 4.1.0, from `common.cpp`)
The columns come from the `ExpressLRS_AirRateConfig` and `ExpressLRS_AirRateRFperf` tables (`src/src/common.cpp:9–103`: three sets, SX127x, LR1121, SX1280; the same thresholds appear in the Lua labels, `TXModuleParameters.cpp:23–37`): packet interval, sensitivity threshold, and the telemetry ratio that the `Std` setting picks. RFMD is the mode number that the OSD and the radio's `RFMD` sensor show; 4.x numbers them differently (in 3.x 250 Hz was `7`, now it is `27`).

| Band | Mode in Lua | Packet interval | Sensitivity | Telem `Std` | RFMD (4.x) | Chip | When |
|---|---|---|---|---|---|---|---|
| 2.4 GHz | 50Hz | 20 ms | −115 dBm | 1:16 | 21 | SX1280, LR1121 | maximum range on 2.4 |
| 2.4 GHz | 100Hz Full | 10 ms | −112 | 1:32 | 23 | SX1280, LR1121 | wing, 8–16 channels at 10 bits |
| 2.4 GHz | 150Hz | 6.67 ms | −112 | 1:32 | 24 | SX1280, LR1121 | long range with good latency |
| 2.4 GHz | 250Hz | 4 ms | −108 | 1:64 | 27 | SX1280, LR1121 | the standard for freestyle/racing |
| 2.4 GHz | 333Hz Full | 3 ms | −105 | 1:128 | 28 | SX1280, LR1121 | full resolution with low latency |
| 2.4 GHz | 500Hz | 2 ms | −105 | 1:128 | 29 | SX1280, LR1121 | lowest latency on LoRa, close in |
| 2.4 GHz | D250 / D500 | 1 ms over the air, new data at 250 / 500 Hz | −104 | 1:128 | 30 / 31 | SX1280 | interference, racing |
| 2.4 GHz | F500 / F1000 | 2 ms / 1 ms | −104 | 1:128 | 32 / 33 | SX1280 | racing, short distance |
| 2.4 GHz | DK250 / DK500 / K1000 | 1 ms over the air | −103 | 1:128 | 34 / 35 / 36 | LR1121 | racing on the LR1121 |
| 900 MHz | 25Hz | 40 ms | −123 | 1:8 | 0 | SX127x, LR1121 | extreme range |
| 900 MHz | 50Hz | 20 ms | −120 | 1:16 | 1 | SX127x, LR1121 | long range |
| 900 MHz | 100Hz | 10 ms | −117 | 1:32 | 2 | SX127x, LR1121 | balance of range and latency |
| 900 MHz | 100Hz Full | 10 ms | −112 | 1:32 | 3 | SX127x, LR1121 | wing, full resolution |
| 900 MHz | 200Hz | 5 ms | −112 | 1:64 | 5 | SX127x, LR1121 | close in on 900 |
| 900 MHz | D50Hz | 5 ms over the air, new data at 50 Hz | −112 | 1:64 | 10 | SX127x, LR1121 | interference on 900 |
| 900 MHz | 200Hz Full / 250Hz | 5 ms / 4 ms | −111 | 1:64 | 6 / 7 | LR1121 | fast 900 modes |
| 900 MHz | K1000 Full | 1 ms | −101 | 1:128 | 11 | LR1121 | MAVLink, maximum data |
| X-Band | X100Hz Full / X150Hz | 10 ms / 6.67 ms | −112 | 1:32 | 100 / 101 | two LR1121 (GemX) | 900 and 2.4 at once |

Every −3 dB of sensitivity = ×0.71 in range; 50 → 250 Hz on 2.4 = −7 dB ≈ ×0.45. The LoRa mode thresholds in 4.x are the same as in 3.x: reflashing adds no range. The range calculation is in the "Radio link budget and range" module, and the interactive tool is below.

### Link margin: from the mode threshold to range
The threshold in the table is the level at which the receiver still decodes packets. Margin M = RSSI − S, dB. In free space the received power falls by 20 dB for every tenfold increase in distance (`rf-link-budget`), so:

- 6 dB of margin ≈ range ×2 (exactly 10^(6/20) = 1.995), 3 dB is ×1.41, 10 dB is ×3.16;
- if RSSI was measured at distance d₀, the required margin M_req holds out to d = d₀ · 10^((RSSI − S − M_req)/20).

Example (the `examples/elrs-uid/uid_lab.py` lab, section 5). At 1 km RSSI = −80 dBm, 2.4 GHz 250Hz mode (−108 dBm): a margin of 28 dB. The course guideline is to keep 12 dB (within the 10–15 dB range from `rf-link-budget`). The extra 16 dB give ×6.31, so 12 dB of margin remains out to 6.3 km. The same aircraft at 150Hz (−112): 10.0 km; at 50Hz (−115): 14.1 km; at F1000 (−104): 4.0 km. Reality is usually 5–10 dB worse than the calculation (`rf-link-budget`); the course guideline is to allow a 6 dB correction, which halves each of these ranges (6.3 → 3.2 km). Gemini and the D modes do not change the threshold: they hold LQ in interference, they do not add dB.

{{lesson:rf-link-budget|The full link budget: power, antennas, FSPL and where the 10–15 dB of margin comes from.}}

### Telemetry: the 1:N ratio
The telemetry ratio says which one packet in N goes to the return link. Telemetry interval = ratio × 1000 / packet rate (ms). For example, 500 Hz at 1:128 is one telemetry packet every 256 ms. There are two packet types: LINK (link statistics, at least every 512 ms, always present) and DATA (flight controller telemetry and MSP). If a lot of data has to go to the radio (GPS, the Lua configurator), the ratio is set more often (1:8, 1:4).

The `Telem Ratio` options in the Lua script, in list order (`TXModuleParameters.cpp:59`): `Std`, `Off`, `1:128`, `1:64`, `1:32`, `1:16`, `1:8`, `1:4`, `1:2`, `Race`. In MAVLink mode only `1:2` stays in the list.

- `Std` (the default) is not one number: the module substitutes the current mode's ratio (the `Telem Std` column in the table) and sends it to the receiver in the SYNC packet (`UpdateTlmRatioEffective`, `tx_main.cpp:336–380`). As a result `Std` keeps 2.6–8 telemetry packets per second in any mode: 25/50/100/200 Hz once every 320 ms, 150 Hz 213 ms, 250 and 500 Hz 256 ms, 333Hz Full 384 ms, F1000 128 ms (lab, section 6).
- `Race` is `TLM_RATIO_DISARMED` in the code: `Std` while disarmed, `Off` while armed.
- `Off`: no return link at all, so no aircraft RQly and RSSI on the radio and no Dynamic Power.
- When the radio sends data up (the Lua menu, MSP, a phrase change), the module raises the ratio to 1:2 for one SYNC cycle to get the answer faster (`tx_main.cpp:343–353`, `588–594`). The boost lasts one SYNC cycle per send, so the reply to a request comes faster, but scripts with constant traffic (`bf.lua`) are still slow at 1:64 and below (`link-edgetx`).

A telemetry slot takes the place of an RC packet: at that moment the flight controller sees a double interval. Betaflight discards such a sample when it estimates the packet rate (`bf-rates-rc`, the section on RC smoothing), so `rc_smoothing_info` shows the mode's rate, not "the rate minus telemetry". How many bytes per second an INAV flight controller itself offers, and how to size the bandwidth for it, is in `inav-telemetry-gcs`.

What changed in 4.x (the 4.0.0 release notes): in normal (non-Full Res) modes telemetry bandwidth grew by about 30 %; in Gemini mode the data travels over both RF paths, and the bandwidth doubles; `TQly` is computed over the last 100 receptions (25 in 3.x); link statistics reach the radio even when the receiver is not connected. In 4.1 "Telemetry Lost" is declared not at once but after a pause that grows with the telemetry interval, so there are fewer false alarms.

### UID: how the phrase becomes the link address
The binding phrase itself is never sent over the air. ExpressLRS Configurator takes the whole string `-DMY_BINDING_PHRASE="phrase"`, prefix and quotes included, computes its MD5 and keeps the first 6 bytes. That is the UID: when building from source, `src/python/build_flags.py:71–74` (the log shows `UID bytes: …`); when flashing a prebuilt unified build, `src/python/binary_configurator.py:35–44`. The Web UI computes the MD5 itself, in the browser, and sends a finished UID: it trims spaces at the ends of the phrase, and it accepts 4–6 comma-separated numbers as a ready UID without hashing, padding with zeros on the left (`html/src/pages/binding-panel.js:91–104`, `114`). `binary_configurator.py` understands such numbers only without spaces (`12,34,56,78`). Bind Phrase Manager passes the phrase to the firmware over MSP, and the firmware hashes it itself (`src/lib/CONFIG/config.cpp:14–41`, called from `RxTxEndpoint.cpp:80`); numbers are not recognized as a UID there. Case and inner spaces matter: `my-quad-2026` and `My-quad-2026` give different UIDs.

Where the UID bytes go (`OTA_VERSION_ID = 4`):

- the hopping generator seed: UID[2..5], last byte XOR 4 (`src/lib/OTA/OTA.cpp:41–45`), from which the FHSS channel order is built;
- the packet CRC initial value: (UID[4]·256 + UID[5]) XOR 0x0400 (`OTA.cpp:28–39`);
- UID4 and UID5 in plain text in every SYNC packet (`tx_main.cpp:407–409`): the receiver uses them to recognize its transmitter.

UID[0] and UID[1] never go over the air. Whether a receiver is bound is decided by UID[2..5]: all zeros mean "not bound" (`OtaUidIsBound`). The protocol version is mixed into both the seed and the CRC, so 3.x and 4.x do not see each other.

The `examples/elrs-uid/uid_lab.py` lab (its output is saved next to it, `uid_lab_output.txt`) computes this following the 4.1 code:

- `my-quad-2026` → MD5 `fa93550f9b26…`, UID `250,147,85,15,155,38`, seed `0x550F9B22`, CRC `0x9F26`;
- `My-quad-2026` → UID `54,156,141,56,214,221`; of the 240 positions of the 2.4 GHz sequence, 7 match, and 3 of them are the sync channel that starts every block;
- on 2.4 GHz the sequence is 3 blocks of 80 channels, each channel exactly once per block; each block starts with sync channel 40 (2440.4 MHz).

What the phrase does and does not do:

- **it does:** separate links. A different phrase means a different hopping order and a different CRC: the receiver will not accept someone else's packets even if they arrive on its channel;
- **it does not:** act as a password or encryption. Packets are not encrypted, and UID4 and UID5 fly in the clear in every SYNC. The phrase does not protect against interception or jamming;
- **the same phrase for two pilots:** a receiver can sync to someone else's radio. Model Match catches this partly; different phrases catch it reliably.

The course guideline: make the phrase unique (not `expresslrs` and not the aircraft's name from your videos), but do not treat it as a secret.

{{diagram:elrs-uid-model-match|Phrase → MD5 → UID: bytes 2–5 set the hopping, 4–5 the CRC, and with Model Match the low 6 bits of UID5 carry the model number. The link comes up on the high bits; channels reach the FC only when all of them match.}}

### Binding phrase and binding methods
The binding phrase is not a password and not encryption. It yields the UID (the first 6 bytes of the MD5 of the string `-DMY_BINDING_PHRASE="…"`, section above), which sets the frequency-hopping pattern. A unique phrase keeps you from interfering with neighbors on the same pattern. The radio and the receiver must have the same phrase and the same ELRS major version: 4.x links only with 4.x, 3.x only with 3.x. If the major versions differ, no binding method will work.

Methods (all available since 3.4.0 and kept in 4.x):

| Method | What to do | Requirements |
|---|---|---|
| Phrase | the same Binding Phrase flashed into the module and the receiver (ExpressLRS Configurator) or entered in the Web UI, Binding tab | after the phrase changes the receiver links by itself, no buttons needed |
| Phrase from the radio | the `ExpressLRS Bind` tool (Bind Phrase Manager) writes the phrase into the module or the receiver without Wi-Fi | ELRS 4.1+ on the device being changed; the Lua package from the ExpressLRS/Lua repository, EdgeTX 2.12.1+ |
| Three power-ups | turn the radio off; power the receiver three times, removing power within the first 2 s each time; the LED double-blinks with a pause; turn the radio on and press `[Bind]` in the Lua script | works on a receiver with a phrase too (since 3.4.0) |
| Button | hold the receiver button for 1.5 s (or short the boot pad to ground), then `[Bind]` in the Lua script | a receiver with a button or pad |
| From Betaflight | `bind_rx` in the CLI or the Bind Receiver button on the Receiver tab, then `[Bind]` in the Lua script | Betaflight 4.5.0+; a receiver over CRSF or a built-in SPI one |

Receiver LED: a slow 0.5 s blink means waiting for the transmitter; a double blink is binding mode; solid means connected; a triple blink means connected but Model Match did not match; very fast blinking is Wi-Fi mode. A binding stays until a new one is done; to leave bind mode without binding, reboot, and the old binding remains. The receiver option `Bind Storage` (`Persistent` by default, `Volatile` keeps the binding only until power is removed; 4.1 also lists `Returnable` and `Administered`) sets whether it is kept.

A built-in SPI receiver (ELRS on the flight controller board, without a separate module) is bound from Betaflight: the phrase on the Receiver tab or `bind_rx`. Its "ELRS version" is set by the flight controller firmware, not by ELRS Configurator; see the section on the upgrade.

### Model Match
The module keeps a separate set of settings (Packet Rate, Telem Ratio, Switch Mode, Model Match, Max Power, Dynamic) for each receiver number: 64 slots (`CONFIG_TX_MODEL_CNT`, `lib/CONFIG/config.h:34`). The number is set in EdgeTX: the `Receiver` field in the model's RF module settings (`Receiver No.` / `RxNum` on monochrome screens), 0…63 (`MAX_RXNUM`, `pulses/modules_helpers.h:662`). When a model is selected, the radio sends the module the CRSF command `MODEL_SELECT_ID` (0x05) with this number (`radio/src/pulses/crossfire.cpp:79–92`, EdgeTX 2.12.5).

How it works in ELRS 4.1:

1. `Model Match = On` in the Lua script while connected: the module sends its number to the receiver over MSP, and 0xFF for `Off` (`TXModuleParameters.cpp:855–870`). The receiver stores it (`RxTxEndpoint.cpp:84–91`). In the Lua script the number shows in the line `Model Match (ID: NN)`.
2. In every SYNC packet a module with Model Match on changes the last byte of the UID: UID5 XOR (¬ID AND 0x3F). Only the low 6 bits are affected (`tx_main.cpp:411–415`, `MODELMATCH_MASK = 0x3f`).
3. The receiver accepts a SYNC if UID4 and the high 2 bits of UID5 match: the link is up, LQ and telemetry flow. It outputs channels to the flight controller (CRSF, PWM, SBUS) only if the whole UID5 equals its own UID5 XOR (¬ID_receiver AND 0x3F). For ID 0xFF the mask is zero (`rx_main.cpp:1013–1090`, `rx-serial/devSerialIO.cpp:134–136`). On a mismatch SBUS behaves as in failsafe (`SerialSBUS.cpp:26–29`): with `SBUS failsafe = No Pulses` it goes silent, with `Last Pos` it sends frames with the failsafe flag; the LED triple-blinks, and the Lua script shows `Model Mismatch`.

In the lab, for UID5 = 38: a module with ID 1 sends 24 in SYNC, and a receiver with ID 1 outputs channels. A module with ID 2 sends 27, and a receiver with ID 1 answers `Model Mismatch`. There is also a mismatch in two "mixed" cases: a module with Model Match on ID 0 and a receiver without Model Match (0xFF); a module with Model Match off and a receiver with a stored ID.

With `Off` on both sides the receiver works with any model that also has Model Match off. This mainly protects against flying on the wrong model in the radio (wrong layout, wrong mixes), not against someone else's radio. Turn it on when several aircraft share one phrase.

Where it breaks:

- **a copy of a model in EdgeTX** gets the same number, and Model Match cannot tell the two aircraft apart. After copying, change `Receiver` (EdgeTX can pick a free number starting from 1, `findNextUnusedModelId`) and turn Model Match on again on the new aircraft;
- **the number was changed after enabling**: the receiver keeps the old one, so `Model Mismatch` until you toggle Model Match Off → On while connected;
- **6 bits are compared:** EdgeTX has exactly 64 numbers (0…63), so no collisions; a number 65 set some other way would collide with 1 (lab, the last line of section 4).

### Regulatory domains and LBT
The domain sets the FHSS frequency grid: the range and the number of channels (`src/lib/FHSS/FHSS.cpp:19–52`, ELRS 4.1):

| Domain (string in Lua) | Range, MHz | Channels | Note |
|---|---|---|---|
| `AU915` | 915.5–926.9 | 20 | 900 MHz, Australia |
| `FCC915` | 903.5–926.9 | 40 | 900 MHz, USA (FCC) |
| `EU868` | 863.275–869.575 | 13 | 868 MHz, EU |
| `IN866` | 865.375–866.95 | 4 | 866 MHz, India |
| `AU433` / `EU433` | 433.42–434.42 / 433.1–434.45 | 3 / 3 | 433 MHz |
| `US433` / `US433W` | 433.25–438.0 / 423.5–438.0 | 8 / 20 | 433 MHz |
| `ISM2G4` | 2400.4–2479.4 | 80 | 2.4 GHz, no LBT |
| `CE_LBT` | 2400.4–2479.4 | 80 | 2.4 GHz with Listen Before Talk (EN 300 328) |

For 900 MHz the domain is chosen in ExpressLRS Configurator at flashing (the `Regulatory_Domain_*` flag → the domain number in the firmware settings, `build_flags.py:148–176`; without a domain a 900 MHz build stops with the error `Please define a Regulatory_Domain`). On 2.4 GHz `CE_LBT` is a separate firmware variant (`Regulatory_Domain_EU_CE_2400`). The domain shows in the Lua script next to the version, separated by `/` on dual-band devices (`addDomainInfo`, `FHSS.cpp:178–215`).

**Different domains on the radio and the receiver.** The number of channels, the step and the sync channel (number = channel count / 2) differ, and the receiver waits for SYNC where the radio does not send it. For the phrase from the lab: on `FCC915` the sync channel is 20 = 915.5 MHz, on `EU868` it is channel 6 ≈ 866.4 MHz. There is no link with any phrase and any binding method, and it looks like "it won't bind". `ISM2G4` and `CE_LBT` share the same grid in 4.1, so by the code they do link; the LBT side just stays silent at times.

**How LBT works** (`src/lib/LBT/LBT.cpp`). Before every transmission (a control packet on the radio side, `tx_main.cpp:630–638`, and a telemetry packet on the receiver, `rx_main.cpp:535`) the radio listens to the channel and measures the instantaneous RSSI. The measurement is taken after a settling time: on the SX1280, for LoRa SF5 100 µs, SF6 141, SF7 218, SF8 480 µs, for FLRC 80 µs. If the RSSI is not below the threshold, the packet is not sent. The threshold is derived from EN 300 328 for a 0.8 MHz bandwidth: TL = −70 dBm/MHz + 10·lg 0.8 + 10·lg(100 mW / P), that is, −71 dBm at 100 mW:

| Power | LoRa threshold, dBm | FLRC threshold, dBm |
|---|---|---|
| 10 mW | −61 | −63 |
| 25 mW | −65 | −67 |
| 50 mW | −68 | −70 |
| 100 mW and above | −71 | −73 |

LBT is on if the configured power (`Max Power`) is above 10 mW (`LbtEnableIfRequired`), and the threshold follows the current power: under Dynamic Power at 10 mW the "10 mW" row applies. On the LR1121, LBT works only in the 2.4 GHz and X-Band modes (in X-Band only the 2.4 GHz radio is checked), and the settling times there are different: LoRa SF5–SF7 22 µs, SF8 240 µs, FSK 40 µs. A CE build limits power on 2.4 GHz to 100 mW (`POWERMGNT.h:92`, in the Lua script the line `100mW 2G4 CE LIMIT`), and on the LR1121 to 25 mW across the whole sub-GHz band (`POWERMGNT.cpp:249–255`, the line `25/100mW 868M/2G4 CE LIMIT`). In a CE build, `TQly` on the radio shows the share of slots in which LBT allowed transmission, not the telemetry quality (`tx_main.cpp:693–697`). Dynamic Power divides RQly by it so as not to raise the power because of busy air (`dynpower.cpp:148–151`). The takeaway: at a crowded field, a low `TQly` in a CE build means a busy channel, not range.

### LQ and RSSI
- RQly (uplink LQ): how many of the radio's last 100 packets reached the receiver;
- TQly: the same for telemetry in the opposite direction;
- RSSI: signal strength in dBm; the margin is counted down to the sensitivity threshold of the current packet rate.

LQ answers "are the packets getting through", RSSI answers "how much margin is left". LQ at 100% with RSSI right at the threshold means you are at the edge even if everything flies: according to the ELRS documentation, LQ drops "off a cliff" as soon as RSSI approaches the sensitivity limit. That is why the RSSI warning in the OSD is set 5–10 dB above the mode's threshold; the course guideline is threshold + 10 dB, as in `rf-link-budget` and `link-edgetx`: for 250 Hz (−108 dBm), −98 dBm (and no lower than −103 dBm). The FLRC modes (F, D) always show SNR = 0.

### The latency the pilot feels
The packet interval is 1/rate: 250 Hz → 4 ms, 50 Hz → 20 ms; plus processing in the radio (the EdgeTX mixer at the module's rate, ~1–3 ms), CRSF at 420 kbaud (~0.6 ms) and RC smoothing in the FC. The Betaflight PT3 auto cutoff with `rc_smoothing_auto_factor = 30` is 0.375 · f_rx: 18 Hz at 50 Hz and 187 Hz at 500 Hz. From the stick movement to 50 % of the setpoint takes ≈ 22 ms at 50 Hz and ≈ 2.1 ms at 500 Hz (`bf-rates-rc`, the "ELRS 50 Hz versus 500 Hz" table). Of that, on average half a packet interval (10 and 1 ms) is waiting for the packet, and the rest (≈ 12 and ≈ 1.2 ms) is the PT3 itself. Smoothing and the packet interval contribute comparable amounts, and both grow as the packet rate goes down. Going from 150 → 250 Hz is noticeable in racing; 250 → 500 hardly at all against the filters and the motor (the "Stick to motor latency" widget in the "Control theory" module).

{{lesson:bf-rates-rc|How Betaflight measures the packet rate, chooses the RC smoothing cutoff, and why feedforward behaves differently at 50 Hz and 500 Hz, with the calculation.}}

Switch mode sets how channels 5–12 are sent (the sticks are always 10 bits); you can change it only while not connected to the receiver:

- `Hybrid`: AUX1 as one bit (arm) in every packet, AUX2–AUX7 with 6 positions each, AUX8 with 16 positions, one switch per packet;
- `Wide`: AUX1 as one bit, AUX2–AUX8 with 64 positions each (in 3.x, 128 positions with a telemetry ratio slower than 1:4); needed to show transmitter power in the OSD;
- Full Res (only for 100Hz Full, 333Hz Full and the other "Full" modes): `8ch`, channels 1–8 at 10 bits in every transmission; `12ch Mixed`, channels 1–4 at the full rate and 5–12 at half rate; `16ch Rate/2`, all 16 at half rate. The range is the extended CRSF limits, 885–2115 µs. In 4.x channel 5 in these modes is an ordinary proportional channel (in 3.x it was a one-bit arm, and 8ch meant channels 1–4 and 6–9).

In every mode except `16ch Rate/2` the receiver duplicates the arm flag into channel 14 (AUX10), and channels 15 and 16 carry LQ and RSSI.

What to choose (a course guideline): `Hybrid` for a quadcopter whose AUX channels have only two- and three-position switches (6 positions are enough); `Wide` when an AUX needs smooth travel (a knob, a gimbal servo, wing flaps) or transmitter power in the OSD; Full Res only if you need 10-bit AUX channels at the full rate. Check on the Receiver tab: every AUX moves through all its positions without gaps.

{{diagram:latency-chain|What the latency from the stick to the aircraft's response is made of; the biggest contributions come from the radio packet and the motor's inertia.}}

### Arming: CH5 or a separate switch
ELRS has to know whether the aircraft is armed: when armed, the module stops adjusting link parameters, Dynamic Power raises the power to maximum on telemetry loss, and `Race` turns telemetry off. The arm flag is sent in every packet, so a disarm gets through even at poor LQ.

- `Arm using: CH5`: the classic and the only option in 3.x: arm on AUX1, around 1000 µs is disarmed, around 2000 µs is armed. A three-position switch on this channel has to be reduced to two states in the mixer.
- `Arm using: Switch`: new in 4.0: in EdgeTX 2.11.0+, in the model's RF module settings (Model Setup → Internal/External RF) you choose `Arm using = Switch` and any switch or logical source. The radio passes the arm state to the module in a separate byte of the channels frame, and channel 5 is freed.
- What to choose (a course guideline): `CH5` if channel 5 can take a two-position arm switch; it works with any EdgeTX and any ELRS; `Switch` when CH5 is needed for something else or the arm comes from a three-position or logical source without a mixer. In both cases the check is the same, in the paragraph below: arm in the flight controller and arm in ELRS are one and the same switch.

Nothing changes on the flight controller side: arming in Betaflight, INAV, ArduPilot and PX4 is still assigned to a channel in the flight controller itself (usually AUX1). If it is assigned there to a channel other than the one ELRS treats as arm, the module will consider the aircraft disarmed in flight, with lowered Dynamic Power and link adjustment.

### Dynamic power and telemetry
Dynamic Power (`Dyn` in the `TX Power` folder): the module starts at minimum power and raises it by itself when the statistics from the aircraft get worse, and lowers it close in. `Max Power` is the ceiling. The 4.1 logic (`dynpower.cpp`):

- LoRa modes go by SNR: in 4.x the "raise" and "lower" thresholds are computed from accumulated SNR statistics (mean and spread) at LQ ≥ 99 %, and the mode's table thresholds (3 and 9.5 dB for 250 Hz) remain as fallbacks; lowering happens only at a mean LQ ≥ 95 %;
- FLRC and FSK (F, D, K) go by RSSI: raise if the average of 5 samples is closer than 15 dB to the sensitivity threshold, lower if it is farther than 21 dB and LQ ≥ 95 %;
- LQ dropped by 20 % at once or below 50 %: straight to maximum; LQ below 85 %: one step up;
- telemetry lost while armed: maximum; a second missed statistics packet in a row: one step up.

Dynamic Power needs telemetry: with `Off`, and with `Race` while armed, it does not work. The minimum is the ratio from the `Std` column: a LINK packet with statistics arrives at least every 512 ms (`common.cpp:219`), that is, about twice a second. Instead of `Dyn` you can choose AUX9–AUX12: switch up for dynamic, down for a fixed `Max Power`.

A telemetry ratio of 1:128 gives a telemetry interval of 128/250 s ≈ 0.5 s at 250 Hz: enough for voltage/LQ, slow for GPS coordinates (for long range, 1:16…1:32 or `Std`; `Race` turns telemetry off while armed and does not suit long range). The telemetry channel is the same link, so MAVLink over ELRS shares bandwidth with control; for a ground station with missions a separate radio or 4G is better.

### Gemini, GemX and LR1121
Gemini sends the same packet simultaneously over two RF paths on two frequencies: 40 MHz apart on 2.4 GHz and about 10 MHz apart on 900 MHz. You need a module with two radio chips and a true-diversity receiver (two receive paths). Gemini does not add range, since the mode's sensitivity is the same; it holds LQ in interference right up to the edge. With the D modes the redundancy adds up: D500 + Gemini is four copies of the packet on four frequencies.

The module's Antenna Mode: `Gemini`, `Ant 1`, `Ant 2`, `Switch` (alternating). In 4.x the module negotiates with the receiver by itself: if the receiver has a single chip, Gemini drops to `Switch`, and the receiver no longer has an `Rx Mode` field in the Lua script (in 3.x the modes were set by hand on both sides, and Gemini with a single-antenna receiver only added noise to the air from the second path).

The LR1121 is a radio chip that works on both 900 MHz and 2.4 GHz. A receiver or module built on it switches between bands from the Lua script (`RF Band`) and gets the K modes and the fast 900 modes, up to 20 modes in all. Two LR1121 chips give Gemini Xrossband (GemX, `X-Band`): the X150Hz and X100Hz Full modes send one packet on 900 MHz (antenna 1) and on 2.4 GHz (antenna 2) at once; Antenna Mode is then locked to `Gemini`. Only a GemX receiver links in the GemX modes; a single-chip LR1121 and ordinary SX1280/SX127x do not hear them.

### MAVLink mode
Since 3.5.0 ELRS can carry MAVLink in both directions: RC and telemetry share one link and one flight controller UART. You need an ESP module and an ESP receiver (4.x has no other hardware). To enable it: with the receiver off, `Link Mode = MAVLink` in the Lua script. In 4.x the receiver output switches to MAVLink by itself; in 3.x it was set by hand (`Other Devices` → receiver → `Protocol = MAVLINK`). The mode forces Telem Ratio 1:2 and Switch Mode `Hybrid` or `16ch Rate/2`; `Wide` is incompatible.

Flight controller setup per the MAVLink page of the ELRS documentation (ArduPilot names checked against Copter 4.7.3):

| Firmware | Receiver port parameters |
|---|---|
| ArduPilot | `SERIALn_PROTOCOL = 2` (MAVLink2), `SERIALn_BAUD = 460`, `RSSI_TYPE = 5` (TelemetryRadioRSSI); this port's `MAVn_*` streams (before 4.7, `SRn_*`) = 1, except `MAVn_ADSB`, `MAVn_PARAMS` and `MAVn_RAW_CTRL` = 0 |
| PX4 | port speed 460800 8N1 (`SER_TELn_BAUD`), `MAV_0_CONFIG` = this port, `MAV_0_RATE` = 9600 B/s |
| INAV 8+ (checked against 9.1.0) | Ports: MAVLink telemetry, 460800, RX Serial off; Receiver: `SERIAL`, provider MAVLink; `set mavlink_radio_type = ELRS`. Monitoring only, not full configuration |
| Betaflight 2025.12+ | Ports: Serial RX on, Telemetry Output = MAVLink, 460800; receiver provider `MAVLINK` |

The ordinary CRSF mode for ArduPilot uses other values: `SERIALn_PROTOCOL = 23` (RCIN), `RSSI_TYPE = 3`, in `RC_OPTIONS` bits 9 (suppress the CRSF mode/rate message for ELRS) and 13 (420 kbaud), and if the protocol is detected wrongly, `RC_PROTOCOLS = 512` (bit 9, CRSF); step by step in the ap-setup-scratch module.

MAVLink leaves the module for the ground station by two paths: the USB of an external module (a serial port, 460800) or the TX Backpack over Wi-Fi (UDP 14550). The radio meanwhile gets its telemetry in the usual CRSF form: the module converts it from MAVLink; the Yaapu script works in this mode only with 4.x.

### ELRS Backpack
The Backpack is a second ESP microcontroller with Wi-Fi inside most TX modules, plus separate boards for goggles. It has its own firmware and its own version numbering (1.x), is updated separately from ELRS, and binds with the same phrase. What it does:

- over ESP-NOW it passes the video band and channel chosen in VTX Administrator in the Lua script to goggles with a VRX Backpack: the channel changes at once on the VTX and on the goggles;
- it forwards telemetry: `Backpack → Telemetry = ESPNOW` (an antenna tracker and other ESP devices, since 3.4) or `WiFi` (MAVLink to the ground station, UDP 14550; Backpack 1.5.0+);
- for MAVLink over Wi-Fi you enable exactly `Telemetry = WiFi`; the `WiFi Connectivity → Enable Backpack WiFi` item is the Backpack's firmware update mode. Access point `ExpressLRS TX Backpack XXXXXX`, password `expresslrs`, address 10.0.0.1.

ESP-NOW and Wi-Fi occupy 2.4 GHz next to the control link: at races, telemetry forwarding is turned off.

### Failsafe on the receiver side
The receiver outputs a channels frame only for a received packet. No packets, no CRSF frames: the flight controller sees silence and starts its own failsafe on its own timer (Stage 1 in Betaflight, `RC_FS_TIMEOUT` in ArduPilot). The receiver itself declares the link lost later, after `DisconnectTimeoutMs` from the mode table: 2.5 s for 500 and 333 Hz and FLRC, 3 s for 250 Hz on 2.4 GHz and 200 Hz on 900 MHz, 3.5 s for 150 and 100 Hz and for the 900 MHz 250Hz and 200Hz Full modes on the LR1121, 4 s for 50 Hz, 6 s for 25 Hz; after that it goes back to searching for the transmitter.

{{lesson:bf-failsafe|What the flight controller does with this silence: RXLOSS, holding channels for 300 ms, Stage 1 and the DROP / AUTO-LAND / GPS Rescue procedures.}}

The receiver has failsafe settings only for outputs where "silence" cannot be conveyed:

- SBUS output, `SBUS failsafe`: `No Pulses` (the receiver goes silent) or `Last Pos` (sends the last values with the failsafe bit);
- PWM outputs, per channel: a set position (`Set Position`), `No Pulses` or `Last Position`; positions are set in the Web UI or with the `[Set Failsafe Pos]` button in the Lua script.

For CRSF + a flight controller there is nothing to set in the receiver: link-loss behavior is defined entirely in the flight controller (the bf-failsafe module). With a Model Match mismatch the receiver behaves as in failsafe and does not output channels.

### Firmware: targets, `hardware.json`, Web UI and Wi-Fi
In 4.x only the ESP8285, ESP32, ESP32-C3 and ESP32-S3 platforms remain, and all builds are "unified": one firmware per chip and radio family (`Unified_ESP32_2400_RX`, `Unified_ESP8285_900_TX`, `Unified_ESP32_LR1121_RX`…), while the pinout of a specific device is set by the `hardware.json` file in flash. ExpressLRS Configurator fills in the right layout for the selected device by itself; by hand it is changed on the Hardware page of the Web UI.

Update methods: Wi-Fi, UART/USB, Betaflight Passthrough through the flight controller for a receiver, and through the radio (EdgeTX Passthrough) for a module. Over Wi-Fi:

1. Module: Lua → `WiFi Connectivity` → `Enable WiFi`. Receiver: power it with the radio off and wait 60 s (`AUTO_WIFI_ON_INTERVAL`, changeable in the Web UI); the LED blinks very fast.
2. Connect to the `ExpressLRS TX` or `ExpressLRS RX` access point, password `expresslrs`, and open http://10.0.0.1/ (on a home network, `elrs_tx.local` / `elrs_rx.local`).
3. Upload the firmware file that Configurator built for this device and wait for the reboot without removing power.

The Web UI was redone in 4.0: a menu on the left with the pages Information (version, domain, UID), Binding, Options, Connections (PWM outputs), Serial (the receiver UART protocol and speed, CRSF 420000 by default), Buttons, Import/Export (the module's model settings), Hardware.

Before moving 3.x → 4.x, be sure to download `hardware.json` (and write down the Options tab settings): the file system changed from SPIFFS to LittleFS, an in-place update is impossible, and custom `hardware.json` and `options.json` are erased. PWM output assignments and the Serial protocol are kept. This matters most for homemade and reflashed devices whose layout is not in Configurator's list.

### Moving 3.x → 4.x: what was renamed and changed
The update order:

1. Check the hardware. STM32 devices are not supported in 4.x: FrSky R9 (R9M, R9MM, R9MX, R9 Slim), ImmersionRC Ghost, Happymodel PP and the STM32-based ES915, SIYI FM30, early NamimnoRC Flash/Voyager. They stay on 3.x for good. Built-in SPI receivers are a separate case, see below.
2. Save `hardware.json` and the Options settings of every device through the Web UI.
3. Flash the TX module to 4.1.0. From that moment it sees no receiver on 3.x, so flash the whole fleet, not "one at a time over the weekends".
4. Flash the receivers: over Wi-Fi or through Betaflight Passthrough (no link to the radio is needed for this). The phrase stays the same, the UID is computed from it the same way, and no rebinding is needed.
5. Radio: delete `elrsV3.lua` and `elrsV3.luac` from `SCRIPTS/TOOLS` and put in `elrs.lua` (it works with all versions from 2.0 on) or the package from ExpressLRS/Lua. For `Arm using = Switch`, update EdgeTX to 2.11.0+.
6. Update the module and goggles Backpack to the current 1.x (at least 1.5.0 for MAVLink over Wi-Fi).
7. Check on the bench with props off: `C` in the corner of the Lua script, version 4.1.0 on both devices, channels on the Receiver tab, arm and disarm, failsafe by turning the radio off, the Switch Mode and Model Match of every model.

What the upgrade does not touch: the wire and protocol to the flight controller (CRSF, 420000 baud; the Betaflight, INAV, ArduPilot and PX4 settings for a serial receiver stay the same), the binding phrase, the LoRa mode sensitivity thresholds, 4.0 ↔ 4.1 compatibility (any 4.x versions work together).

| What changed | 3.x (3.5/3.6) | 4.x (4.1.0) | Since release |
|---|---|---|---|
| Radio protocol version (`OTA_VERSION_ID`) | 3 | 4: mixed into the CRC and the hopping sequence seed, so 3.x and 4.x do not sync and do not bind by any method | 4.0.0 |
| Supported platforms | ESP8285, ESP32, STM32 | only ESP8285, ESP32, ESP32-C3, ESP32-S3; STM32 removed | 4.0.0 |
| Targets | unified and per-device (`Frsky_TX_R9M`, `GHOST_2400_TX`…) | only `Unified_*` + `hardware.json` | 4.0.0 |
| Device file system | SPIFFS | LittleFS; custom `hardware.json` and `options.json` are erased on update | 4.0.0 |
| Lua script | `elrsV3.lua` | `elrs.lua` (one for all versions); delete the old one | 4.0.0 |
| Arming method | only CH5 (AUX1) | `Arm using`: CH5 or Switch (EdgeTX 2.11.0+) | 4.0.0 |
| Full Res `8ch` | channels 1–4 and 6–9, CH5 a one-bit arm | channels 1–8, CH5 proportional; the arm flag duplicated into CH14 | 4.0.0 |
| Full Res `12ch Mixed` | 1–4 at full rate, 6–13 at half rate, CH5 arm | 1–4 full, 5–12 half; CH13 is not generated | 4.0.0 |
| Switch Mode `Wide` | 128 positions (64 with telemetry at 1:2 and 1:4) | always 64 positions | 4.0.0 |
| Antenna Mode / Gemini | by hand on the module and on the receiver (`Rx Mode`) | negotiated automatically; no `Rx Mode` field | 4.0.0 |
| Band selection on the LR1121 | a combined Packet Rate list (`50 2.4G`, `100 Low Band`…) | a separate `RF Band` item: 2.4GHz / 900MHz / X-Band | 4.0.0 |
| LR1121 modes | 16 (K1000 Full, DK500, X100 Full, X150…) | 20: K1000 and DK250 added on 2.4, 25Hz and D50 on 900 | 4.0.0 |
| RFMD mode numbers in the OSD and telemetry | 1–19 (250 Hz = 7) | 0–36 and 100–101 (250 Hz on 2.4 = 27) | 4.0.0 |
| Telemetry bandwidth | baseline | about +30 % in non-Full Res modes; ×2 in Gemini | 4.0.0 |
| `TQly` window | 25 receptions | 100 receptions | 4.0.0 |
| MAVLink: receiver protocol | by hand, `Protocol = MAVLINK` | set automatically with `Link Mode = MAVLink`; Yaapu works | 4.0.0 |
| Dynamic Power | fixed SNR thresholds from the mode table | thresholds from SNR statistics; in 4.1 it lowers power more readily (mean + 0.5 σ instead of + 1.5 σ) | 4.0.0 / 4.1.0 |
| Web UI | one page with tabs, Hardware hidden | a menu of pages, Hardware available | 4.0.0 |
| Receiver outputs | CRSF, SBUS, SUMD, DJI RS2 Pro, HoTT, MAVLink | added `DisplayPort` (waking a DJI Air Unit from low-power mode), GPS NMEA input, DShot 3D on PWM | 4.0.0 |
| Changing the phrase from the radio | no (only the Web UI or reflashing) | Bind Phrase Manager in Lua | 4.1.0 |
| "Telemetry Lost" | right after a few misses | after a pause that depends on the telemetry interval | 4.1.0 |

A known conflict: built-in SPI receivers. On all-in-one whoop boards the ELRS radio chip sits directly on the flight controller's SPI bus, and the ELRS protocol is run by Betaflight (`src/main/rx/expresslrs*.c`), not by the ExpressLRS firmware. In Betaflight 2025.12 (checked against 2025.12.5) that code has `ELRS_OTA_VERSION_ID 3` with no alternatives: such a board is an ELRS 3 receiver, and it will not link with a module on 4.x however you bind it. Betaflight 2026.6 (checked against 2026.6.2) added the `USE_ELRSV4` build variant (typed as `ELRSV4` into the Custom Defines field of Cloud Build, shown only in expert mode; it is not in the option list) with `ELRS_OTA_VERSION_ID 4`; without that option it is still version 3. Options for a board with an SPI receiver on the course's firmware (2025.12): keep a 3.x module for it; fit a separate serial ELRS receiver on a free UART and switch to `serialrx_provider = CRSF`; move this particular board to 2026.6 with the `ELRSV4` build. ExpressLRS Configurator does not flash SPI receivers.

### Worked example: setup for a 7" long-range quad
900 MHz 100Hz Full (−112) or 2.4 GHz 150Hz (−112), chosen by the interference situation and the antennas (900 means bigger antennas and better diffraction); if you need range rather than 10-bit channels, plain 100Hz (−117) is better on 900; power from the budget for 10 km with a 12 dB margin (the "Radio link budget and range" module); telemetry 1:32 (which is exactly `Std` for both modes); Dynamic Power ON; Wide switch mode; arm on AUX1 (`Arm using: CH5`) or a separate switch; warnings in EdgeTX: RSSI dBm (the `1RSS`/`2RSS` sensor) ≤ −100 "caution", ≤ −105 "turn back"; LQ (`RQly`) < 70% warning; in the OSD `osd_rssi_dbm_pos`, `osd_link_quality_pos`; on link loss a CRSF receiver simply stops sending channels, and the action is set in the FC: GPS Rescue/RTH.

### Where it fits in the system

- **Takes in:** stick positions and the arm flag from the radio; the power and antennas that make up the link margin (`rf-link-budget`, `rf-antennas`); flight controller telemetry for the return link (`bf-gps-setup`).
- **Puts out:** CRSF frames on the flight controller UART (`link-protocols`); the packet rate, to RC smoothing and feedforward (`bf-rates-rc`); LQ and RSSI, to the OSD (`bf-modes-osd`); silence on link loss, to failsafe (`bf-failsafe`).
- **If you get this wrong:** the TX module is updated to 4.x, but a receiver or an SPI board on Betaflight 2025.12 stays on 3.x → no link, `RXLOSS` on the flight controller, arming blocked (`bf-arming-safety`, `bf-ports`). The packet rate is too high for the distance → a small RSSI margin, LQ drops "off a cliff", failsafe triggers (`bf-failsafe`, `rf-link-budget`).

## practice

{{widget:elrs-calc}}

Where the radio link sits in the "stick → motor" chain and how much it really weighs next to RC smoothing, the filters and the motor:

{{widget:link-latency}}

### Choosing a mode for the job
1. Freestyle, racing, flights within line of sight: 2.4 GHz, 250–500 Hz or F500.
2. 7–10" for long-range flights: 2.4 GHz 150 Hz or 900 MHz 100 Hz.
3. Wing, long routes, forest: 900 MHz, 50–100 Hz.

### Setup on the radio (ELRS Lua)
1. Tools → ExpressLRS (`elrs.lua`; in 3.x the script was called `elrsV3.lua`): on a dual-band module first `RF Band`, then Packet Rate and Telem Ratio. Change them only on the ground: changing the mode drops the link.
2. TX Power: for flights close in, do not set the maximum: the module heats up, and you light up your neighbors. Dynamic Power will raise the power by itself when LQ drops. The `Max Power` ceiling: no higher than your country's permitted power (EIRP) including antenna gain (`f-regulations`, `rf-link-budget`), and within that limit, the power at which the link budget gives a 12 dB margin at the farthest point of the route (`rf-link-budget`); more only adds heat and light-up.
3. After a mode change, check that the receiver is connected again (`C` in the top right corner of the Lua script) and that the version line of the module and the receiver starts with the same digit (4.x).

### Analyzing the link from a Blackbox log
1. Enable RSSI/LQ logging in Betaflight (the `rssi` and link quality fields).
2. After the flight, find the stretches where LQ falls below ~70% or RSSI approaches the threshold.
3. Match them with the RXLOSS moments in the OSD and with the drone's attitude. A real-world example: on a 10" quad RSSI hovered around 26–52%, dropped below 30% for tens of seconds, and that is exactly where the RXLOSS events happened. The culprit was the receiver antenna, not the PID settings.

### Exercise without hardware: mode, telemetry, margin and versions
No radio or receiver needed, only the mode table and the section on moving 3.x → 4.x from the theory.

**1. Three aircraft.** For each, take the packet interval, the sensitivity threshold and the `Std` telemetry ratio from the mode table, then compute the telemetry interval (ratio × 1000 / packet rate) and the range for the RSSI warning in the OSD (5–10 dB above the threshold): (a) a 5" freestyle quad, 2.4 GHz 250Hz; (b) a 7" for long-range flights, 2.4 GHz 150Hz; (c) a wing, 900 MHz 50Hz.

**2. Margin from the log.** At the farthest point of the route the log shows RSSI = −96 dBm. Compute the margin to the threshold for the 2.4 GHz 250Hz, 150Hz, 500Hz and 50Hz modes. Then estimate by what factor the range changes going from 250Hz → 50Hz on 2.4 GHz, 250Hz → 500Hz on 2.4 GHz and 100Hz → 25Hz on 900 MHz: range changes as 10 to the power (Δ dB / 20), the same rule as "−3 dB = ×0.71" in the theory.

**3. Will they link?** For each pair, write one of three outcomes, "linked", "no link", "linked, no channels", and the reason. The binding phrase is the same unless stated otherwise.

| # | Transmitter | Receiver |
|---|---|---|
| 1 | module on 4.1.0 | serial receiver on 3.6 |
| 2 | module on 4.1.0 | serial receiver on 4.0.0 |
| 3 | module on 4.1.0 | built-in SPI receiver, Betaflight 2025.12 |
| 4 | module on 4.1.0 | built-in SPI receiver, Betaflight 2026.6, build without `ELRSV4` |
| 5 | module on 4.1.0 | built-in SPI receiver, Betaflight 2026.6, build with `ELRSV4` |
| 6 | module on 3.6 | FrSky R9MM on 3.x |
| 7 | module on 4.1.0, `Model Match = On`, Receiver ID 2 | receiver on 4.1.0 with Receiver ID 1 stored |
| 8 | module on 4.1.0 | receiver on 4.1.0 with a different phrase |

**4. Telemetry and power.** A 7" long-range quad needs Dynamic Power. Which of the `Telem Ratio` options, `Std`, `Race`, `Off`, `1:32`, keep it working while armed, and what does MAVLink mode force?

**5. UID and Model Match.** Run `python3 examples/elrs-uid/uid_lab.py` (Python 3, standard library only). (a) Write down the UID for `my-quad-2026` and `My-quad-2026` and how many positions of the 2.4 GHz hopping sequence they share. (b) UID5 = 38, Model Match on, the model's `Receiver` in EdgeTX = 5. Which UID5 byte goes into SYNC? The receiver stores ID 5: will channels flow? The receiver stores 0xFF: will they? (c) The radio is flashed with the `FCC915` domain, the receiver with `EU868`, one phrase. Will there be a link, and why?

**6. Range from margin.** At 0.8 km the log shows RSSI = −86 dBm, 2.4 GHz 150Hz mode. Out to what distance does a 12 dB margin hold in free space? How much is that with a 6 dB reality correction? What range does switching to 250Hz give under the same conditions?

Self-check: the lab is done when:
- exercise 1: (a) 4 ms, −108 dBm, 1:64, telemetry every 256 ms, warning −103…−98 dBm; (b) 6.67 ms, −112 dBm, 1:32, 213 ms, −107…−102 dBm; (c) 20 ms, −120 dBm, 1:16, 320 ms, −115…−110 dBm;
- exercise 2: margins of 12, 16, 9 and 19 dB; range ×2.24, ×0.71 and ×2.0 (3 % tolerance);
- exercise 3: linked in rows 2, 5 and 6; no link in rows 1, 3, 4 and 8; in row 7 linked, no channels;
- exercise 4: `Std` and `1:32` work; `Race` and `Off` do not; MAVLink forces 1:2 and Switch Mode `Hybrid` or `16ch Rate/2`;
- exercise 5: (a) `250,147,85,15,155,38` and `54,156,141,56,214,221`, 7 of 240 positions match (3 of them the sync channel); (b) 38 XOR (¬5 AND 0x3F) = 38 XOR 58 = 28; with ID 5 the channels flow, with 0xFF there is a link but no channels; (c) no link: 40 channels versus 13, sync channel 915.5 MHz versus ≈ 866.4 MHz;
- exercise 6: a margin of 26 dB, the extra 14 dB → ×5.01 → 4.0 km ± 0.1; with the 6 dB correction 2.0 km; at 250Hz (−108) a margin of 22 dB → 2.5 km (1.3 km with the correction);
- on hardware (if you have it): in the Lua script the module and receiver versions start with the same digit, `C` is in the corner, and the RSSI warning threshold in the OSD or on the radio lies within the range computed in exercise 1 for your mode.

**Reference answer for self-check.** The reasons in exercise 3: 1, different major versions, `OTA_VERSION_ID` 3 and 4 do not sync by any binding method; 2, any 4.x versions work together; 3, the SPI receiver is run by Betaflight, and in 2025.12 that is ELRS 3; 4, without the `ELRSV4` option 2026.6 is still version 3; 5, version 4 on both sides; 6, both sides on 3.x, but the STM32 receiver stays on 3.x for good, and this module cannot be updated while that receiver is in the fleet; 7, the receiver establishes the link but does not output channels to the flight controller: the LED triple-blinks, the Lua script shows `Model Mismatch`; 8, different phrases give different UIDs, and the receiver waits for its transmitter until the phrases match or a binding is done another way. In exercise 4, `Race` turns telemetry off while armed, and Dynamic Power does not work without telemetry. Common wrong answers: in row 3, "rebind with the phrase": the protocol version is built into the flight controller firmware, binding will not help; in exercise 2, the margin computed from −108 dBm for every mode: each mode has its own threshold; the range for +7 dB written as ×0.45: that is the factor for the reverse change (50 → 250 Hz), and 1/0.45 ≈ 2.2; the telemetry interval for 150Hz written as 256 ms: for this mode `Std` is 1:32, not 1:64. In exercise 5 a common mistake in (a) is treating the phrase as case-insensitive (one letter changes the whole MD5); in (b), XOR with the number itself (38 XOR 5 = 35) instead of ¬ID AND 0x3F. In exercise 6 a common mistake is computing range as 10^(Δ/10): that is the law for power; range goes with the exponent Δ/20.

## diagnostics
- **Symptom:** RXLOSS when turning with your back to the pilot
  - Possible cause: the receiver antenna is shadowed by the frame or carbon fiber.
  - What to do: move the antenna out, angle it, check it for damage.
- **Symptom:** LQ "sags" in waves although the drone is close
  - Possible cause: strong 2.4 GHz interference (Wi-Fi, other pilots) or a damaged radio antenna.
  - What to do: try the D250/D500 modes or 900 MHz, check the TX antenna.
- **Symptom:** will not bind after an update
  - Possible cause: different ELRS major versions (module 4.x, receiver 3.x or the other way round) or different binding phrases.
  - What to do: update both sides to the same major version, check the phrase; the version shows in the Lua script and on the Information page of the Web UI.
- **Symptom:** 900 MHz: the same phrase and version, but no link with any binding method
  - Possible cause: different regulatory domains on the module and the receiver (for example `FCC915` and `EU868`): a different grid and a different sync channel.
  - What to do: compare the domain shown next to the version in the Lua script on both devices; reflash one of them with the right domain.
- **Symptom:** CE build on 2.4 GHz: `TQly` is low although the aircraft is close
  - Possible cause: in a `CE_LBT` build `TQly` is the share of slots where LBT allowed transmission; the channel is busy with Wi-Fi or other pilots.
  - What to do: look at RQly and RSSI; change the location or the mode; remember that power in CE is limited to 100 mW.
- **Symptom:** two pilots on one phrase, and one's receiver sometimes latches onto the other's radio
  - Possible cause: the same UID; both have Model Match off.
  - What to do: different phrases; Model Match with different `Receiver` numbers as a second line of defense.
- **Symptom:** after updating the module to 4.x a whoop with a built-in receiver does not link
  - Possible cause: the SPI receiver runs on Betaflight's code, and in 2025.12 that is ELRS 3.
  - What to do: a 3.x module for this model, a separate serial receiver, or Betaflight 2026.6 with the `ELRSV4` build (typed into Custom Defines in expert mode; the "Moving 3.x → 4.x" section).
- **Symptom:** after updating to 4.x the Web UI settings are gone or the device does not work as before
  - Possible cause: the file system change erased `hardware.json` and Options.
  - What to do: upload the saved `hardware.json` on the Hardware page and set Options again; for a production device, reflash choosing the exact model in Configurator.
- **Symptom:** two ExpressLRS entries in Tools, or the script hangs on "Loading…"
  - Possible cause: `elrsV3.lua` is still there; the model does not have the CRSF module enabled, or the link speed is too low.
  - What to do: delete `elrsV3.lua`/`.luac` and keep `elrs.lua`; check Internal/External RF = CRSF and Baudrate.
- **Symptom:** linked, "Model Mismatch" in the Lua script, no channels reach the flight controller
  - Possible cause: the receiver stores a different Receiver ID; the model was copied in EdgeTX, or the number was changed after enabling Model Match.
  - What to do: while connected, toggle Model Match Off → On (stores the current ID) or On → Off (clears it).
- **Symptom:** F1000 is not available
  - Possible cause: the radio ↔ module link speed is 115200 or 400k, where F1000 (a 1 ms interval) is not available (`CRSFHandset.cpp:413–428`); or the receiver is not on an SX1280.
  - What to do: set Baudrate to 921k or higher in the EdgeTX module settings; on the LR1121, K1000 instead of F1000.
- **Symptom:** LQ 100%, but the control twitches
  - Possible cause: a low packet rate with high `rc_smoothing`, or telemetry too frequent.
  - What to do: 250 Hz, look at `debug_mode = RC_SMOOTHING`, ratio 1:64.
- **Symptom:** range in the field is half the calculated one
  - Possible cause: antennas (polarization, carbon), onboard interference, Dynamic Power not keeping up.
  - What to do: the "Antennas" and "Interference" modules; a fixed power for the test; LQ/RSSI to the log.

## references
- ExpressLRS 4.0.0 — Release Notes | https://github.com/ExpressLRS/ExpressLRS/releases/tag/4.0.0 | primary | A
- ExpressLRS 4.1.0 — Release Notes | https://github.com/ExpressLRS/ExpressLRS/releases/tag/4.1.0 | primary | A
- Signal Health (RF Mode Indexes, sensitivity) — ExpressLRS Docs | https://www.expresslrs.org/info/signal-health/ | primary | A
- Binding — ExpressLRS Docs | https://www.expresslrs.org/quick-start/binding/ | primary | A
- Switch Configs — ExpressLRS Docs | https://www.expresslrs.org/software/switch-config/ | primary | A
- Gemini — ExpressLRS Docs | https://www.expresslrs.org/software/gemini/ | primary | A
- MAVLink — ExpressLRS Docs | https://www.expresslrs.org/software/mavlink/ | primary | A
- SPI Receivers — ExpressLRS Docs | https://www.expresslrs.org/hardware/spi-receivers/ | primary | A
- ExpressLRS FAQ | https://www.expresslrs.org/faq/ | primary | A
- Telemetry Bandwidth — ExpressLRS Docs | https://www.expresslrs.org/info/telem-bandwidth/ | primary | A
- Lua Script How-To — ExpressLRS Docs | https://www.expresslrs.org/quick-start/transmitters/lua-howto/ | primary | A
- ExpressLRS — source code (GitHub) | https://github.com/ExpressLRS/ExpressLRS | primary | A
- ExpressLRS 4.1.0 — src/python/build_flags.py (UID from the phrase, domains) | https://raw.githubusercontent.com/ExpressLRS/ExpressLRS/4.1.0/src/python/build_flags.py | primary | A
- ExpressLRS 4.1.0 — src/src/common.cpp (modes, thresholds, Std) | https://raw.githubusercontent.com/ExpressLRS/ExpressLRS/4.1.0/src/src/common.cpp | primary | A
- ExpressLRS 4.1.0 — src/lib/FHSS/FHSS.cpp (domains, hopping sequence) | https://raw.githubusercontent.com/ExpressLRS/ExpressLRS/4.1.0/src/lib/FHSS/FHSS.cpp | primary | A
- ExpressLRS 4.1.0 — src/lib/LBT/LBT.cpp (Listen Before Talk) | https://raw.githubusercontent.com/ExpressLRS/ExpressLRS/4.1.0/src/lib/LBT/LBT.cpp | primary | A
- ExpressLRS 4.1.0 — src/src/rx_main.cpp (SYNC and Model Match check) | https://raw.githubusercontent.com/ExpressLRS/ExpressLRS/4.1.0/src/src/rx_main.cpp | primary | A
- EdgeTX 2.12.5 — radio/src/pulses/crossfire.cpp (MODEL_SELECT_ID) | https://raw.githubusercontent.com/EdgeTX/edgetx/v2.12.5/radio/src/pulses/crossfire.cpp | primary | A

## checklist
- Packet rate chosen for the job, not "the maximum"
- Telem ratio matches the amount of telemetry needed
- A unique binding phrase, one ELRS major version on the module and all receivers (built-in SPI ones included)
- One regulatory domain on the module and the receivers (900 MHz); I understand what CE_LBT does to TQly
- I know the RSSI margin at my distance and the range at a 12 dB margin
- Before moving to 4.x `hardware.json` is saved, and afterwards `elrsV3.lua` is deleted
- Arm on AUX1 or `Arm using = Switch`; Model Match checked on every model
- RSSI and LQ are logged
- The receiver antenna is moved out and not shadowed by the frame
