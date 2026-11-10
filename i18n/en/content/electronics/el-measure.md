---
id: el-measure
title: "Measurements: Multimeter, Oscilloscope, Logic Analyzer"
level: L2
readingTime: 30 min
firmware: any firmware
status: published
added: 2026-11-08
tags:
  - measurements
  - oscilloscope
  - logic analyzer
  - DShot
related:
  - el-power-design
  - el-emi
next:
  - el-emi
source: content/electronics/el-measure.md
source_hash: 603b8ab39703
---

## summary
What separates an engineer from an assembler is that the engineer measures instead of assuming. This module is about three instruments: the multimeter (voltage, current, continuity, resistance), the oscilloscope (sags, ripple, PWM/DShot waveforms, noise) and the logic analyzer (decoding UART, I2C, SPI, DShot). What to measure, how to connect, how not to fry the instrument or the aircraft, and how to read the result.

## theory
### Multimeter
- **Voltage** — in parallel with the load. Useful: the voltage of each battery cell (balance), 5 V and 9 V on the BEC under load.
- **Continuity** — before applying power: + to − on the power bus, 5 V to GND. A beep = a short. With a capacitor the resistance rises as it charges — that's normal.
- **Current** — in series, through the 10 A jack; anything more — only with a clamp meter or through the FC current sensor. Never measure voltage in current mode: that's a short circuit through the meter.
- **Resistance** — checking motor windings (three identical values of a few tenths of an ohm), a broken wire.
- Limitation: a multimeter shows the average/RMS; it doesn't see brief sags and ripple.

### Oscilloscope
Shows voltage over time. For on-board work 2 channels and 50–100 MHz are enough; a USB oscilloscope will do too.

- **Sag**: a channel on the power bus, timebase 100 ms/div, trigger on the falling edge; punch the throttle — you see the depth and duration of the dip.
- **Ripple**: AC coupling (removes the DC component), 20–50 mV/div, timebase 10–50 µs/div — you see the ESC/BEC switching frequency and the p-p amplitude. Measure with a short ground spring instead of the long alligator clip — otherwise you pick up noise from the probe itself.
- **Signals**: PWM servos — a 1–2 ms pulse every 20 ms (50 Hz); UART — bursts of bits with idle at the high level; DShot — bursts of 16 pulses of different widths.
- **A ×10 probe** reduces the load on the circuit and extends the bandwidth; for 3.3 V logic it's mandatory.

### DShot on the oscilloscope
A DShot frame is 16 bits: 11 throttle bits, 1 telemetry bit, 4 CRC bits. Each bit is a pulse: “1” is long (~75% of the bit period), “0” is short (~37%). DShot600 is 600 kbit/s, a bit ≈ 1.67 µs, a frame ≈ 27 µs. On screen — a burst of 16 pulses repeating at the PID loop rate (for example, every 125 µs at 8 kHz). Problems you can see: ringing on the edges (long wire, no termination), a level that doesn't reach 3.3 V (weak driver), dropped frames.

### Logic analyzer
Records digital levels on many channels and decodes protocols. A cheap 8-channel 24 MHz one with software like PulseView/sigrok is enough for UART up to 1 Mbaud, I2C at 400 kHz, SPI up to a few MHz and DShot600 (you need ≥ 4–5 samples per bit — 12–24 MHz is better).

- **UART**: connect to the TX line and GND, set the baud rate (115200 for MSP, 420000 for CRSF!), the decoder shows the bytes. You can see: the wrong baud rate (garbage), inversion (SBUS is an inverted UART at 100000 8E2).
- **I2C**: SDA and SCL, the decoder shows addresses and ACK/NACK. A NACK on an address — the sensor isn't there or the address is different; no pull-up — the lines don't go high.
- **SPI**: CLK, MOSI, MISO, CS — reading the gyro registers.
- A common ground with the aircraft — always. Levels are 3.3 V; most analyzers tolerate 5 V lines, 12 V — no.

### Measurement safety
- Props off for any measurement on ESCs/motors.
- The oscilloscope ground is tied to protective earth: on a circuit that isn't referenced to earth (battery powered) that's fine; on a mains-powered supply you must not clip the probe ground to a point that carries a potential.
- The probe never touches two pins at once: tiny FC pads are the number one way to cause a short with the instrument.

{{diagram:measure-tools|Which instrument for which question: values — multimeter, waveform — oscilloscope, protocol — logic analyzer.}}

## practice
### Step 1. Map of measurement points
On the aircraft's schematic mark: the power bus, the 5 V output, the 9 V output, the receiver UART, DShot on one motor, the compass I2C. Find convenient pads.

### Step 2. Sag under load
Without props the measurement is meaningless — use the log (VBAT in hover) or an oscilloscope on a test stand with a real load (aircraft tied down, props on, short throttle pulses, extremely carefully and with an observer). Record: U with no load, U at maximum, duration of the dip.

### Step 3. BEC ripple
AC coupling, 5 V under receiver/GPS load. Record p-p and frequency. Compare with/without a capacitor on the power bus.

### Step 4. DShot and UART with the analyzer
Capture a DShot frame at low throttle without props: decode the 16 bits by hand, compute the throttle value (DShot 48–2047) and check the CRC. Capture CRSF between the receiver and the FC at 420000 baud: find the channels frame (type 0x16).

### Step 5. Report
A table: point, instrument, value, normal range, conclusion.

### A decoded DShot frame
Throttle value 1046, telemetry bit 0. Twelve bits: `10000010110 0`. CRC = (v ⊕ v>>4 ⊕ v>>8) & 0xF = 6 (`0110`), where v is those 12 bits. The frame is 16 bits `1000001011000110` (0x82C6). On the oscilloscope each DShot600 bit lasts ≈ 1.67 µs: “1” is a long high pulse, “0” a short one. From your captured frame compute the value and the CRC and compare them with the throttle you set.

### What you should get and what to record
- **Sag under load:** VBAT in the log in hover and at a short burst of full throttle — the difference and how it relates to the internal resistance from the “Electricity” module.
- **BEC ripple:** the swing (p-p) on 5 V under load — tens of millivolts for a good BEC. Hundreds of millivolts mean interference in the video and sensor glitches. Record p-p and frequency with and without the capacitor on the power bus.
- **CRSF:** the channels frame starts with the address byte `0xC8`, then the length `0x18` (24) and the type `0x16` (RC channels packed): 16 channels of 11 bits each.
- **Table:** point, instrument, value, normal range, conclusion — one row per measurement. Without the “normal range” column a measurement tells you nothing.

The lab is passed when the sag under load is measured and tied to internal resistance, a DShot or UART frame is captured with the analyzer and decoded with a CRC check, and the BEC ripple is measured with and without the capacitor and recorded in the table with normal ranges.

## diagnostics
- **Symptom:** the multimeter shows 5.0 V, but the FC reboots
  - Possible cause: a brief sag the multimeter can't see.
  - What to do: an oscilloscope with a falling-edge trigger, or the log.
- **Symptom:** the oscilloscope shows huge ripple on everything
  - Possible cause: the long probe ground wire picks up noise.
  - What to do: a ground spring, measure right at the capacitor.
- **Symptom:** the analyzer shows garbage on UART
  - Possible cause: wrong baud rate or inversion (SBUS).
  - What to do: find the right baud rate, enable inversion in the decoder.
- **Symptom:** an I2C sensor doesn't respond (NACK)
  - Possible cause: no pull-up, a different address, SDA/SCL swapped.
  - What to do: check the idle levels (they should be high), scan the addresses.
- **Symptom:** DShot edges ring
  - Possible cause: long signal wires, no common ground with the ESC.
  - What to do: shorten them, add a ground next to the signal, drop DShot to 300.

## references
- Betaflight — DSHOT ESC Protocol | https://betaflight.com/docs/development/API/Dshot | primary | A
- sigrok — PulseView (logic analyzer software) | https://sigrok.org/wiki/PulseView | primary | A
- Crossfire/CRSF protocol — TBS (community reference) | https://github.com/crsf-wg/crsf/wiki | secondary | B

## checklist
- I know a multimeter doesn't see sags and ripple
- I captured 5 V ripple with AC coupling and a ground spring
- I decoded a DShot frame by hand
- I decoded UART/I2C with an analyzer
- All measurements on ESCs — without props
