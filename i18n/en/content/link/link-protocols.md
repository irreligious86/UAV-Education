---
id: link-protocols
title: "SBUS, CRSF and UART inversion"
level: L1
readingTime: 15 min
firmware: CRSF / SBUS
status: published
added: 2026-11-07
tags:
  - SBUS
  - CRSF
  - UART
related:
  - link-elrs
  - bf-ports
next:
  - link-elrs
source: content/link/link-protocols.md
source_hash: 5f1611e6151c
---

## summary
The receiver sends stick positions to the flight controller over one of several serial protocols. Today the two main ones are the old SBUS (FrSky, Futaba) and CRSF (TBS Crossfire, ExpressLRS). This module explains the physical difference between them, what an "inverted" signal is, why SBUS was a constant headache on F4 flight controllers, and how to wire each protocol correctly.

## theory
### What a UART frame is
A UART sends bytes one bit at a time: a start bit, 8 data bits, an (optional) parity bit, then stop bits. When idle, the line sits at logic one, the high level. The start bit pulls it to zero; the receiver catches that edge and starts counting bits.

### What "inverted" means
In an inverted signal everything is flipped: idle is low, a one is low, a zero is high. The data is the same; only the electrical levels are reversed. Feed an inverted signal into a normal UART and the receiver sees garbage, because it looks for the start bit in the wrong place.

### SBUS
- 100000 baud, 8 data bits, even parity, 2 stop bits (8E2);
- the signal is inverted by the protocol's definition, not as an exception;
- a 25-byte frame: 16 proportional channels of 11 bits each, 2 digital channels, and the frame lost and failsafe flags;
- one-way: receiver → flight controller only; telemetry goes back over a separate wire (SmartPort).

"Non-inverted SBUS" means a signal someone flipped back for compatibility. It is a workaround, not a different protocol.

### Why F4 boards struggled with SBUS
The UARTs of STM32F4 microcontrollers cannot invert their input in hardware. F7, H7 and G4 parts have a bit for this in the USART registers, so inversion is switched on in software. That is why F4 boards carried a separate hardware inverter on one UART (the pad is usually labeled SBUS), and SBUS did not work on the other ports without modification.

### CRSF
- an ordinary non-inverted UART, 8N1;
- full duplex over two wires (TX and RX): channels go down and telemetry comes back up on the same port;
- the speed in the specification is 416666 baud for full duplex, and it can be negotiated higher for lower latency (CRSF v3; in Betaflight this is `crsf_use_negotiated_baud`, which you leave OFF with ELRS 4.1.0: an ELRS receiver never proposes a speed change, see `bf-ports`);
- each frame carries a frame type and a CRC, and the protocol is extensible: channels, telemetry, link statistics, device parameters.

Hence the practical rule: CRSF needs no inverter and works on any free UART of any MCU family.

### CRSF inside (per the TBS specification)
Frame: `[sync 0xC8 or address][length][type][payload][CRC8]`; length = frame size − 2 (valid range 2 to 62); the CRC8 uses polynomial 0xD5 and covers the type and the payload. The extended header adds destination and origin addresses (for device parameters, MSP over CRSF). Key frame types:
- **0x16 RC Channels Packed** — 16 channels of 11 bits in 22 bytes; center = 992 ticks = 1500 µs, conversion `us = (ticks − 992)·5/8 + 1500` (so 172…1811 ticks ↔ 988…2012 µs). With the "cut" failsafe type the frames simply stop arriving; the specification recommends that the FC wait 1 s before starting its own failsafe routine.
- **0x14 Link Statistics** — uplink RSSI of antennas 1/2 (dBm × −1), uplink link quality (%), SNR (dB), active antenna, RF profile, TX power, downlink RSSI/LQ/SNR. This is where the OSD gets LQ and RSSI dBm.
- Telemetry: 0x08 Battery Sensor, 0x02 GPS, 0x1E Attitude, 0x21 Flight Mode and others; the FC sends them to the receiver, which passes them to the radio.
Routing: a device with more than one CRSF port forwards frames between them (a star network, no loops); that is how the radio sees the FC through the module.

{{diagram:crsf-frame|A CRSF frame: 26 bytes for 16 channels, the frame type and CRC8.}}

By default Betaflight receives CRSF at 420000 baud (`serialrx_provider = CRSF`); the specification says 416666 8N1, and the difference is within UART tolerance (< 1%).

### SBUS inside
A 25-byte frame every 7–14 ms: `0x0F`, 22 bytes of 11-bit channels (1–16), a flags byte (channels 17/18, `frame lost`, `failsafe`), `0x00`. Values 172…1811 ↔ 988…2012 µs (the same scale as CRSF, and not by accident). The receiver sets the `failsafe` flag when the link is lost, and the firmware must read it (Betaflight reads the flag on its own); otherwise failsafe never triggers in the FC while the receiver "holds" the last values.

{{diagram:sbus-frame|An SBUS frame: 25 bytes, 16 channels of 11 bits and a flags byte with the failsafe bit.}}

### Latency and reliability compared
| Protocol | Direction | Speed | Update rate | Frame latency | CRC |
|---|---|---|---|---|---|
| PWM (per channel) | → | — | 50 Hz | 20 ms | no |
| PPM | → | — | ~50 Hz | 20+ ms | no |
| SBUS | → (+S.Port separately) | 100 kbaud, inverted | 70–140 Hz | 7–14 ms | no (parity only) |
| CRSF | ↔ | 420 kbaud | up to 1 kHz (link-dependent) | 1–4 ms | CRC8 |
| Ghost, FPort | ↔ | 420 k / 115.2 k | high / 100 Hz | low / medium | yes |
The course's conclusion: CRSF (ELRS/Crossfire/Tracer) for new builds; SBUS only for old hardware.

### Worked example: the receiver does not work
An F405, an SBUS receiver wired to `RX3`, Serial RX on UART3 in Ports, SBUS in Receiver; no channels. Diagnosis: UART3 on this board has no hardware inverter → garbage. Fixes: move the wire to the port with the inverter (the `SBUS`/`RX1` pad, per the board's documentation); or switch the receiver to non-inverted SBUS output and set `serialrx_inverted = ON` (for SBUS, ON means "the signal is not inverted", see bf-ports); or replace the receiver with a CRSF one (ELRS), which works on any UART. F7/H7/G4 do not have this problem: the UART inverts by itself with `serialrx_inverted = OFF`. To check with a logic analyzer: an idle-low line is an inverted signal (the "Measurements" module).

### TBS Crossfire and Tracer versus ELRS today
From the flight controller's side there is no difference: all three systems output CRSF, so the wiring, the UART without an inverter and `serialrx_provider = CRSF` are the same, and swapping a Crossfire receiver for an ELRS one needs no changes in the FC firmware. Over the air they are incompatible: a Crossfire module does not see an ELRS receiver, and vice versa.

What sets TBS apart (Crossfire and Tracer manuals, revision 2022-08-08, firmware 6.16 and 6.17):

| | Crossfire | Tracer | ELRS 4.1 (`link-elrs`) |
|---|---|---|---|
| Band | 868 or 915 MHz, by region | 2.4 GHz | 2.4 GHz, 900 MHz, both on the LR1121 |
| Packet rate | Dynamic (150 ↔ 50 Hz by link quality; the manual calls it the best choice for most cases), 50 or 150 Hz; 4 Hz only in forced-telemetry mode | fixed 250 Hz | 25–1000 Hz, chosen in the Lua script |
| Transmitter power | Micro TX V2: 25 mW…1 W, Standard/Lite: 10 mW…2 W; on USB: 10 mW | 25–100 mW | depends on the module |
| Binding | put the transmitter into Bind (Lua Agent Lite, Agent Desktop/Web, the Micro TX button), then press the receiver button within a minute of power-up | the same | binding phrase, no button needed |
| Rebinding needed | after a region change, a transmitter firmware update, enabling Multi-bind, a receiver reset, a Model ID change, an encryption change | the same except the region (one band only); also with another transmitter without Multi-bind | when the phrase changes |
| Updates | TBS Agent over USB; the receiver is flashed over the air at the next bind | the same | Wi-Fi, USB, Passthrough |
| Receiver failsafe | `FS. Mode`: Cut (recommended when failsafe is handled in the FC) or a set position | the same | for CRSF: silence, the FC decides |

How to choose:
1. **The fleet is already on Crossfire and the radio has a TBS module**: keep it. The aircraft work, and a second system needs a second RF module (an internal ELRS plus an external TBS in the radio's module bay, `link-edgetx`).
2. **A new build**: ELRS. Open firmware, both bands, MAVLink mode (`link-telemetry-radios`), binding by phrase without buttons.
3. **Long-range flight on 900 MHz**: both systems will do. The sensitivity of every ELRS mode is published (`link-elrs`); the Crossfire manual gives a single figure, "up to −130 dBm", not tied to a mode, so the course has not verified a range comparison of the two systems.

How to check a receiver swap: in Receiver the channels are AETR with endpoints at 988–2012, the OSD shows LQ, and with the radio switched off `RXLOSS` appears; on a Crossfire receiver, `FS. Mode = Cut` is set beforehand.

### Where it fits in the system

- **Takes in:** the channels the receiver got over the air (`link-elrs`); a flight controller UART of the right polarity, with or without an inverter (`bf-ports`, `f-fc-sensors`).
- **Puts out:** 16 channels on the 988…2012 µs scale to the stick chain (`bf-rates-rc`); Link Statistics, LQ and RSSI dBm, for the OSD (`bf-modes-osd`); the link-loss signal, silence in CRSF or the failsafe flag in SBUS (`bf-failsafe`).
- **If you get this wrong:** inverted SBUS on a normal UART of an F4 board → garbage instead of frames, no channels, arming blocked by the `RXLOSS` flag (`bf-ports`, `bf-arming-safety`). Endpoints of 988…2012 not mapped to 1000…2000 → about 1.2 % of stick travel at each end (2.3 % in total) is dead; the `rxrange` command fixes it (`bf-rates-rc`).

## practice
### Connecting CRSF / ExpressLRS to Betaflight
1. Cross the wires: receiver TX → flight controller RX, receiver RX → flight controller TX. Plus 5 V and GND.
2. Ports: enable Serial Rx on that UART.
3. Receiver: Serial (via UART), provider CRSF, telemetry on.
4. In the CLI, check that the port is neither inverted nor half-duplex:

```
get serialrx
set serialrx_provider = CRSF
set serialrx_inverted = OFF
set serialrx_halfduplex = OFF
save
```

### Connecting SBUS
1. On F4, only on a UART with a hardware inverter (the SBUS pad, per the board's schematic) or with a receiver that can output a non-inverted signal.
2. On F7/H7/G4, on any UART; Betaflight switches inversion on by itself.
3. Provider `SBUS`. Touch `serialrx_inverted` only if the receiver outputs non-inverted SBUS.

### Check
Receiver tab: the channels move with the sticks, the channel order matches (AETR), the range is about 1000–2000.

### What you should get and what to record
- **CLI.** `get serialrx` prints every receiver setting with `serialrx` in its name. For CRSF expect `serialrx_provider = CRSF`, `serialrx_inverted = OFF`, `serialrx_halfduplex = OFF`. Record the output before and after the change.
- **Receiver tab.** The channels move with the sticks and in the right order: roll, pitch, throttle, yaw (AETR). With CRSF/ELRS the endpoints are about 988–2012, with SBUS about 988–2012 (FrSky ±100 %), depending on the radio's endpoints. Stick center is 1500 ± a few units; otherwise you need a calibration or subtrim on the radio.
- **Failsafe.** Switch the radio off: in Receiver the channels go to their failsafe values, and `status` shows the `RXLOSS` flag. Switch it back on and the channels return. This checks that the link really is monitored.
- **CRSF telemetry.** On the radio (EdgeTX: Model → Telemetry → Discover new) link-quality sensors (RSSI, LQ) and the aircraft's battery voltage appear. If LQ is there but voltage is not, check that telemetry is enabled in Betaflight and that the voltage sensor is connected.
- **SBUS on F4.** If the channels do not move at all, the signal is almost always on a UART without a hardware inverter. Move the wire to the SBUS pad shown in the board's schematic.

Self-check: the lab is done when the receiver protocol is identified and written down, the `get serialrx` output before and after the change is saved (for CRSF it shows `serialrx_provider = CRSF`, `serialrx_inverted = OFF`, `serialrx_halfduplex = OFF`), the Receiver tab shows the channels in AETR order with endpoints around 988–2012 (CRSF/ELRS) and a center of 1500 ± a few units, `status` shows `RXLOSS` with the radio off, and for CRSF the radio shows LQ and voltage.

**Reference answer for self-check.** The correct result is all four checks in the list above matching the expected values. Channels do not move at all on an F4 with SBUS: the signal is on a UART without a hardware inverter. With the radio off the channels do not go to their failsafe values and `RXLOSS` does not appear: the link is not monitored, the receiver holds the last values. LQ is on the radio but voltage is not: telemetry is off in Betaflight or the voltage sensor is not connected.

## diagnostics
- **Symptom:** the receiver is bound, but the channels in Receiver do not move
  - Possible cause: TX/RX swapped, or the wrong UART selected in Ports.
  - What to do: check the crossed wiring and the UART number against the board's schematic.
- **Symptom:** SBUS on an F4 does not work on any port
  - Possible cause: wired to a UART without an inverter.
  - What to do: find the pad with the inverter in the schematic, or use the receiver's non-inverted output.
- **Symptom:** channels are there, but no telemetry on the radio (CRSF)
  - Possible cause: the flight controller TX → receiver RX wire is not soldered, or half-duplex is on.
  - What to do: check the second wire and `serialrx_halfduplex = OFF`.
- **Symptom:** the sticks "jitter" in place
  - Possible cause: noise on the line, a poor GND or the wrong speed.
  - What to do: check the common GND, route the wire away from the power leads.
- **Symptom:** channels arrive, but failsafe in the FC does not trigger when the radio is switched off
  - Possible cause: the receiver "holds" the last values and does not report the loss: a PWM/PPM output without "no pulses", or an SBUS output that does not set the failsafe flag (Betaflight and INAV read the flag on their own).
  - What to do: set the receiver to "no pulses"/cut or to a mode with the failsafe flag; check the FC's reaction on the ground with the props off.
- **Symptom:** LQ in the OSD is 100%, but RSSI dBm is not shown
  - Possible cause: the OSD element is set up for RSSI from a channel, not from CRSF Link Statistics.
  - What to do: enable the "RSSI dBm value"/"Link quality" element (Betaflight: `osd_link_quality_pos`, `osd_rssi_dbm_pos`), turn off `rssi_channel`.

## references
- CRSF Protocol Specification — TBS (GitHub) | https://github.com/tbs-fpv/tbs-crsf-spec | primary | A
- Configuring FC for ExpressLRS — ExpressLRS Docs | https://www.expresslrs.org/quick-start/receivers/configuring-fc/ | primary | A
- TBS CROSSFIRE manual, rev. 2022-08-08, FW 6.16 (opened 2026-11-22) | https://www.team-blacksheep.com/media/files/tbs-crossfire-manual.pdf | primary | A
- TBS TRACER manual, rev. 2022-08-08, FW 6.17 (opened 2026-11-22) | https://www.team-blacksheep.com/media/files/tbs-tracer-manual.pdf | primary | A
- SBUS library and protocol description — Bolder Flight Systems | https://github.com/bolderflight/sbus | secondary | B

## checklist
- I know which protocol the receiver outputs
- For SBUS on an F4, a UART with an inverter is selected
- For CRSF: TX/RX crossed, both wires soldered
- `serialrx_inverted` and `serialrx_halfduplex` checked with `get`
- Channels and their order checked in the Receiver tab
- I know that Crossfire, Tracer and ELRS look the same to the FC (CRSF), but do not link to each other over the air
