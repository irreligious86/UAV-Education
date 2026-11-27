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
source_hash: d0ba0890a07a
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

{{diagram:chart-measure-current-calibration|A calibration from one flight is accurate only at that flight's average current: a sensor with a 50 mV offset is off by +74 % at 2 A, while two clamp-meter points give < 0.5 % over the whole range.}}

### DShot on the oscilloscope
A DShot frame is 16 bits: 11 throttle bits, 1 telemetry bit, 4 CRC bits. Each bit is a pulse: “1” is long (~75% of the bit period), “0” is short (~37%). DShot600 is 600 kbit/s, a bit ≈ 1.67 µs, a frame ≈ 27 µs. On screen — a burst of 16 pulses repeating at the PID loop rate (for example, every 125 µs at 8 kHz). Problems you can see: ringing on the edges (long wire, no termination), a level that doesn't reach 3.3 V (weak driver), dropped frames.

{{diagram:dshot600-pulse-train|Frame 0x82C6 over time: the pulse width carries the bit — a “1” stays high for ~75 % of the bit, a “0” for ~37 %, and the 16 bits of DShot600 take ≈ 27 µs.}}

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

Calculation lab (no hardware): `calib_lab.py` computes new voltage and current calibration values for Betaflight, ArduPilot and PX4 from bench measurements, compares a one-point (mAh) calibration with a two-point one and checks aliasing. The script and its real output:

```python
# calib_lab.py — FC voltage/current sensor calibration for Betaflight, ArduPilot and PX4.
# python3 calib_lab.py   (pure Python 3). Inputs = bench measurements, props off.
V_METER, V_FC = 24.12, 23.71            # multimeter on XT60 vs FC reading (all three FCs read the same)
I_CLAMP = [2.0, 10.0, 25.0]             # DC clamp meter, A (bench load: resistor bank / motor test, props off)
BF_FC = [2.63, 8.13, 18.44]             # Betaflight OSD amps,  ibata_scale 400, ibata_offset 0
AP_FC = [4.20, 13.00, 29.50]            # ArduPilot CURR,  BATT_AMP_PERVLT 40.0, BATT_AMP_OFFSET 0
PX_FC = [3.82, 11.82, 26.82]            # PX4 battery_status.current_a, BAT1_A_PER_V 36.367515, BAT_V_OFFS_CURR 0

def fit(x, y):                          # least squares y = k*x + c
    n = len(x); mx, my = sum(x) / n, sum(y) / n
    k = sum((a - mx) * (b - my) for a, b in zip(x, y)) / sum((a - mx) ** 2 for a in x)
    return k, my - k * mx

print("VOLTAGE (proportional in all three)")
print(f"  BF vbat_scale     110    -> {110 * V_METER / V_FC:.1f} -> 112 (uint8); "
      f"check: {V_FC * 112 / 110:.2f} V vs {V_METER} V")
print(f"  AP BATT_VOLT_MULT 11.0   -> {11.0 * V_METER / V_FC:.3f}")
print(f"  PX4 BAT1_V_DIV    18.1   -> {18.1 * V_METER / V_FC:.3f}")

print("CURRENT, two-parameter fit over 3 clamp points")
k, c = fit(BF_FC, I_CLAMP)              # I_true = k*I_fc + c ;  I_mA = 10000*mV/scale + offset
# new scale = old / k ; new offset = k*old_offset + c*1000 (old offset 0 mA)
print(f"  BF  fit I_true = {k:.4f}*I_fc {c:+.3f} A -> ibata_scale {400 / k:.0f}, "
      f"ibata_offset {c * 1000:.0f} mA")
for name, rd, P, off in (("AP ", AP_FC, 40.0, 0.0), ("PX4", PX_FC, 36.367515, 0.0)):
    v = [i / P + off for i in rd]       # sensor volts the FC saw: I = (V - off) * P
    P2, c2 = fit(v, I_CLAMP)            # I_true = P2*V + c2 = P2*(V - off2)
    print(f"  {name} sensor V = {[round(x, 4) for x in v]} -> A_PER_V {P2:.3f}, offset {-c2 / P2:.4f} V")

print("SCALE-ONLY calibration from mAh (no offset), BF example")
mah_fc, mah_charger = 1018, 1350        # one flight: FC counted vs charger put back
s1 = 400 * mah_fc / mah_charger
print(f"  ibata_scale 400 * {mah_fc}/{mah_charger} = {s1:.0f}")
for i_true in (2.0, 10.0, 25.0):
    mv = 50 + 27.5 * i_true             # the sensor used to make the readings above: 50 mV + 27.5 mV/A
    i1 = 10000 * mv / s1 / 1000
    i2 = 10000 * mv / round(400 / k) / 1000 + c
    print(f"  {i_true:5.1f} A true: scale-only {i1:6.2f} A ({(i1 / i_true - 1) * 100:+5.1f} %), "
          f"two-point {i2:6.2f} A ({(i2 / i_true - 1) * 100:+5.1f} %)")

print("ALIASING: what a sampled reading shows")
for f, fs, who in ((24000, 10000, "scope 100 ms/div, 10 kpts"), (24000, 50, "BF current task 50 Hz"),
                   (117, 100, "BF attitude task 100 Hz, 117 Hz vibration"), (1010, 1000, "1 kHz log")):
    fa = abs(f - round(f / fs) * fs)
    print(f"  {f} Hz sampled at {fs} Hz ({who}) -> looks like {fa:g} Hz")
```


```text
VOLTAGE (proportional in all three)
  BF vbat_scale     110    -> 111.9 -> 112 (uint8); check: 24.14 V vs 24.12 V
  AP BATT_VOLT_MULT 11.0   -> 11.190
  PX4 BAT1_V_DIV    18.1   -> 18.413
CURRENT, two-parameter fit over 3 clamp points
  BF  fit I_true = 1.4548*I_fc -1.827 A -> ibata_scale 275, ibata_offset -1827 mA
  AP  sensor V = [0.105, 0.325, 0.7375] -> A_PER_V 36.364, offset 0.0500 V
  PX4 sensor V = [0.105, 0.325, 0.7375] -> A_PER_V 36.368, offset 0.0500 V
SCALE-ONLY calibration from mAh (no offset), BF example
  ibata_scale 400 * 1018/1350 = 302
    2.0 A true: scale-only   3.48 A (+74.1 %), two-point   1.99 A ( -0.4 %)
   10.0 A true: scale-only  10.77 A ( +7.7 %), two-point   9.99 A ( -0.1 %)
   25.0 A true: scale-only  24.45 A ( -2.2 %), two-point  24.99 A ( -0.0 %)
ALIASING: what a sampled reading shows
  24000 Hz sampled at 10000 Hz (scope 100 ms/div, 10 kpts) -> looks like 4000 Hz
  24000 Hz sampled at 50 Hz (BF current task 50 Hz) -> looks like 0 Hz
  117 Hz sampled at 100 Hz (BF attitude task 100 Hz, 117 Hz vibration) -> looks like 17 Hz
  1010 Hz sampled at 1000 Hz (1 kHz log) -> looks like 10 Hz
```

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
