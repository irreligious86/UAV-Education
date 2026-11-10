---
id: link-protocols
title: "SBUS, CRSF and UART Inversion"
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
source_hash: bd84de264961
---

## summary
The receiver sends stick positions to the flight controller using one of several serial protocols. Today the two main ones are the old SBUS (FrSky, Futaba) and CRSF (TBS Crossfire, ExpressLRS). This module explains the physical difference between them, what an “inverted” signal is, why SBUS caused endless problems on F4 controllers, and how to wire each protocol correctly.

## theory
### What a UART frame is
UART sends bytes serially: a start bit, 8 data bits, an (optional) parity bit, stop bits. In the idle state the line sits at logical one — the high level. The start bit pulls it down to zero, and the receiver catches that edge and starts counting.

### What “inverted” means
In an inverted signal everything is the other way around: idle is low, a one is low, a zero is high. The data is the same, only the electrical levels are flipped. If you feed an inverted signal into a regular UART, the receiver sees garbage: it waits for the start bit in the wrong place.

### SBUS
- 100000 baud, 8 data bits, even parity, 2 stop bits (8E2);
- the inverted signal is the protocol standard, not an exception;
- 25-byte frame: 16 proportional channels of 11 bits, 2 digital channels, frame lost and failsafe flags;
- one-way: receiver → controller only, telemetry goes back over a separate wire (SmartPort).

The phrase “uninverted SBUS” means a signal that someone flipped back for compatibility. It's a workaround, not a different protocol.

### Why F4 struggled with SBUS
The UART of STM32F4 microcontrollers can't invert its input in hardware. F7, H7 and G4 have a bit for this in the USART register, and inversion is enabled in software. That's why F4 boards put a separate hardware inverter on one UART (the pad is usually labeled SBUS), and on the other ports SBUS didn't work without modification.

### CRSF
- a regular uninverted UART, 8N1;
- full duplex on two wires (TX and RX): channels down, telemetry up over the same port;
- the spec speed is 416666 baud for full duplex; it can negotiate higher for lower latency;
- the frame has a packet type and a CRC, and the protocol is extensible: channels, telemetry, link statistics, device parameters.

Hence the practical rule: CRSF doesn't need an inverter and works on any free UART of any series.

### CRSF inside (per the TBS spec)
Frame: `[sync 0xC8 or address][length][type][payload][CRC8]`; length = frame size − 2 (from 2 to 62); CRC8 with polynomial 0xD5 is calculated over the type and payload. The extended header adds destination/origin addresses (for device parameters, MSP over CRSF). Key types:
- **0x16 RC Channels Packed** — 16 channels of 11 bits in 22 bytes; center = 992 ticks = 1500 µs, conversion `us = (ticks − 992)·5/8 + 1500` (i.e. 172…1811 ticks ↔ 988…2012 µs). With a “cut” type failsafe, frames simply stop arriving — the spec recommends the FC wait ~1 s before its own failsafe procedure.
- **0x14 Link Statistics** — uplink RSSI of antennas 1/2 (dBm·−1), uplink LQ (%), SNR (dB), active antenna, RF profile, TX power, downlink RSSI/LQ/SNR. This is exactly where the OSD gets LQ and RSSI dBm.
- Telemetry: 0x08 Battery, 0x02 GPS, 0x1E Attitude, 0x21 Flight Mode and others — the FC sends them to the receiver, and the receiver to the radio.
Routing: a device with several CRSF ports forwards frames between them (a star without loops) — that's how the radio sees the FC through the module.

{{diagram:crsf-frame|CRSF frame: 26 bytes for 16 channels, frame type and CRC8.}}

Betaflight receives CRSF at 420000 baud by default (`serialrx_provider = CRSF`); the spec says 416666 8N1 — the difference is within UART tolerance (< 1%).

### SBUS inside
A 25-byte frame every 7–14 ms: `0x0F`, 22 bytes × 11-bit channels (1–16), a flags byte (channels 17/18, `frame lost`, `failsafe`), `0x00`. Values 172…1811 ↔ 988…2012 µs (the same scale as in CRSF — not a coincidence). The receiver sets the `failsafe` flag when the link is lost — the firmware must read it (Betaflight reads the flag automatically), otherwise the FC failsafe will never trigger while the receiver “holds” the last values.

{{diagram:sbus-frame|SBUS frame: 25 bytes, 16 channels of 11 bits and a flags byte with the failsafe indicator.}}

### Comparison by latency and reliability
| Protocol | Direction | Speed | Update | Frame latency | CRC |
|---|---|---|---|---|---|
| PWM (per channel) | → | — | 50 Hz | 20 ms | no |
| PPM | → | — | ~50 Hz | 20+ ms | no |
| SBUS | → (+S.Port separately) | 100 kbaud, inverted | 70–140 Hz | 7–14 ms | no (parity only) |
| CRSF | ↔ | 420 kbaud | up to 1 kHz (depends on the link) | 1–4 ms | CRC8 |
| Ghost, FPort | ↔ | 420 k / 115.2 k | high / 100 Hz | low / medium | yes |
The course's takeaway: new builds — CRSF (ELRS/Crossfire/Tracer); SBUS — only for old hardware.

### Worked example: the receiver doesn't work
F405, an SBUS receiver connected to `RX3`, in Ports — Serial RX on UART3, in Receiver — SBUS; no channels. Diagnosis: UART3 on this board has no hardware inverter → garbage. Solutions: move it to the port with the inverter (the `SBUS`/`RX1` pad per the board description), or enable `serialrx_inverted = ON` only on F7/H7, or switch the receiver to CRSF (ELRS) — then any UART works. Checking with a logic analyzer: idle low = inverted signal (the “Measurements” module).

## practice
### Connecting CRSF / ExpressLRS to Betaflight
1. Wires crossed over: receiver TX → controller RX, receiver RX → controller TX. Plus 5 V and GND.
2. Ports: enable Serial RX on that UART.
3. Receiver: Serial, CRSF provider, telemetry enabled.
4. In the CLI, check that the port isn't inverted and isn't half-duplex:

```
get serialrx
set serialrx_provider = CRSF
set serialrx_inverted = OFF
set serialrx_halfduplex = OFF
save
```

### Connecting SBUS
1. On F4 — only to a UART with a hardware inverter (the SBUS pad per the board schematic) or to a receiver that can output an uninverted signal.
2. On F7/H7 — to any UART, Betaflight will enable the inversion itself.
3. Provider `SBUS`. Touch the `serialrx_inverted` parameter only if the receiver outputs uninverted SBUS.

### Check
Receiver tab: the channels move together with the sticks, the channel order matches (AETR), the range is around 1000–2000.

### What you should get and what to write down
- **CLI.** `get serialrx` prints all the receiver settings. For CRSF you expect `serialrx_provider = CRSF`, `serialrx_inverted = OFF`, `serialrx_halfduplex = OFF`. Write down the output before and after the change.
- **Receiver tab.** The channels move together with the sticks and in the right order: roll, pitch, throttle, yaw (AETR). With CRSF/ELRS the end values are around 988–2012, with SBUS around 1000–2000 depending on the radio. Stick center is 1500 ± a few units; otherwise you need a calibration or subtrim on the radio.
- **Failsafe.** Turn off the radio: in Receiver the channels go to their failsafe values, and the `RXLOSS` flag appears in `status`. Turn it on — the channels are back. This checks that the link is actually being monitored.
- **CRSF telemetry.** On the radio (EdgeTX: Model → Telemetry → Discover new sensors), link quality sensors (RSSI, LQ) and the aircraft battery voltage appear. If LQ is there but voltage isn't, check whether telemetry is enabled in Betaflight and whether the voltage sensor is connected.
- **SBUS on F4.** If the channels don't move at all, the signal is almost always going into a UART without a hardware inverter. Move the wire to the SBUS pad per the board schematic.

The lab counts as done when the receiver protocol is identified and written down, `serialrx_inverted` and `serialrx_halfduplex` are checked with `get` and the output written down, channels and failsafe are checked on the Receiver tab, and for CRSF the telemetry (LQ and voltage) is visible on the radio.

## diagnostics
- **Symptom:** the receiver is bound, but the channels don't move in Receiver
  - Possible cause: TX/RX are swapped or the wrong UART is selected in Ports.
  - What to do: check the crossover soldering and the UART number per the board schematic.
- **Symptom:** SBUS on F4 doesn't work on any port
  - Possible cause: connected to a UART without an inverter.
  - What to do: find the pad with the inverter on the schematic or use the receiver's uninverted output.
- **Symptom:** channels work, but there's no telemetry on the radio (CRSF)
  - Possible cause: the controller TX → receiver RX wire isn't soldered, or half-duplex is enabled.
  - What to do: check the second wire and `serialrx_halfduplex = OFF`.
- **Symptom:** the sticks “twitch” in place
  - Possible cause: noise on the line, a bad GND or the wrong speed.
  - What to do: check the common GND, move the wire away from the power lines.
- **Symptom:** channels arrive, but the FC failsafe doesn't trigger when you turn off the radio
  - Possible cause: the receiver “holds” the last values, the SBUS failsafe flag isn't being read, or CRSF isn't set to “cut”.
  - What to do: set the receiver to “no pulses”/cut or failsafe values; check the FC's reaction on the ground without props.
- **Symptom:** LQ in the OSD is 100%, but RSSI dBm isn't shown
  - Possible cause: the OSD element is set to channel-based RSSI rather than CRSF Link Statistics.
  - What to do: enable the “RSSI dBm”/“Link quality” element (Betaflight: `osd_link_quality_pos`, `osd_rssi_dbm_pos`), disable `rssi_channel`.

## references
- CRSF Protocol Specification — TBS (GitHub) | https://github.com/tbs-fpv/tbs-crsf-spec | primary | A
- Configuring FC for ExpressLRS — ExpressLRS Docs | https://www.expresslrs.org/quick-start/receivers/configuring-fc/ | primary | A
- SBUS library and protocol description — Bolder Flight Systems | https://github.com/bolderflight/sbus | secondary | B

## checklist
- I know which protocol the receiver outputs
- For SBUS on F4, a UART with an inverter is selected
- For CRSF: TX/RX crossed over, both wires soldered
- `serialrx_inverted` and `serialrx_halfduplex` are checked with `get`
- The channels and their order are checked on the Receiver tab
