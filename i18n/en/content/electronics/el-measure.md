---
id: el-measure
title: "Measurements: multimeter, oscilloscope, logic analyzer"
level: L2
readingTime: 50 min
firmware: Betaflight 2025.12.5 · ArduPilot 4.7 (checked against 4.7.3) · PX4 1.18 (parameters checked against v1.18.0) · INAV 9.1.0 (sensor calibration checked against the source)
status: published
added: 2026-11-08
tags:
  - measurements
  - oscilloscope
  - logic analyzer
  - DShot
  - current sensor
  - calibration
related:
  - el-power-design
  - el-emi
  - bf-setup-scratch
  - px4-setup-scratch
  - ctl-signals
next:
  - el-emi
source: content/electronics/el-measure.md
source_hash: c8e63aea0d35
---

## summary
What separates an engineer from an assembler is measuring instead of assuming. This module covers three instruments: the multimeter (voltage, current, continuity, resistance), the oscilloscope (sag, ripple, PWM/DShot waveforms, noise) and the logic analyzer (decoding UART, I2C, SPI, DShot). What to measure, how to connect, how not to burn the instrument or the aircraft, and how to read the result. Separately: how current sensors work (shunt and Hall), why sampling at a low rate shows frequencies that do not exist (aliasing), and how to calibrate the flight controller's voltage and current sensors in Betaflight, ArduPilot and PX4: the formulas from the source, the direction of the proportion, one-point and two-point calibration. The lab: calculating the calibration from bench measurements for three firmwares with the script's actual output, then the same measurements on hardware.

## theory
### Multimeter
- **Voltage**: in parallel with the load. Useful: the voltage of each battery cell (balance), 5 V and 9 V on the BEC under load.
- **Continuity**: before applying power: + to − on the power bus, 5 V to GND. A beep means a short. On a capacitor the resistance rises as it charges; that is normal.
- **Current**: in series, through the 10 A jack; above that only with a clamp meter or the FC current sensor. Never measure voltage in current mode: that is a short circuit through the meter.
- **Resistance**: checking motor windings (three identical values of hundredths to tenths of an ohm: an ordinary multimeter mostly shows the 0.1–0.3 Ω resistance of its leads here, so zero the leads (REL) and compare the three pairs with each other; for precision use the voltage-drop method, `el-wiring`), and broken wires.
- Limitation: a multimeter shows the average/RMS and does not see short sags and ripple.

Three instrument properties change the result. **Accuracy** is specified as ±(% of reading + counts of the least significant digit): on a meter with ±(0.5 % + 2 counts) on the 200.0 mV range, a 25.0 mV reading is only good to ±0.33 mV (0.5 % × 25.0 + 2 × 0.1); for calibrating a current sensor on a 0.25 mΩ shunt that is 1.3 % (an example calculation; look up your own meter's class in its manual). **Input resistance** in voltage mode is ~10 MΩ: on a 10 kΩ : 1 kΩ flight controller divider the meter has almost no effect, but on high-impedance circuits (100 kΩ pull-ups and above) it becomes a load itself. **Burden voltage** in current mode: the internal shunt of the 10 A jack drops a fraction of a volt at full current, so when you feed a 5 V rail through the ammeter the load sees less than 5 V; above a few amps use only a clamp meter or a sensor. On a non-sinusoidal AC voltage a meter without True RMS multiplies the rectified average by 1.11 (the sine form factor): on a ±2.5 V square wave it shows 2.78 V instead of 2.50 V RMS (+11 %); look at the waveform with a scope.

### Current sensors: shunt and Hall
Current on board is measured in two ways, and the method determines what you calibrate.

- **Shunt**: a resistor of a fraction of a milliohm in the power path; the voltage U = I·R is amplified by an op amp on the ESC or PDB. A 0.25 mΩ shunt at 100 A gives 25 mV and dissipates I²R = 2.5 W. Pros: linear and stable. Cons: millivolts next to power switching pick up interference, and the amplifier's zero offset gives a nonzero reading at zero current. A shunt in the negative wire (low-side) shifts the board ground by I·R: at 100 A that is the same 25 mV between the ESC "ground" and the battery ground.
- **Hall sensor**: measures the conductor's magnetic field, galvanically isolated, almost no losses. Cons: the zero offset drifts with temperature, and a nearby magnet or current-carrying wire adds error. Betaflight and INAV historically use a default of 400 (40 mV/A) for the Allegro ACS758 Hall sensor, as the comment in the source says.
- **Clamp meter**: the same Hall sensor in a split magnetic core. For DC you need a DC clamp: cheap AC clamps (current transformers) read zero on DC.

Any of these sensors is described by two numbers: slope (mV/A) and offset (mV at zero current). The flight controller knows them only from parameters, which is why you calibrate the sensor instead of trusting the default.

### Oscilloscope
Shows voltage over time. For an aircraft, 2 channels and 50–100 MHz are enough (a course guideline); a USB scope works too.

- **Sag**: a channel on the power bus, 100 ms/div timebase, trigger on the falling edge; a sharp throttle punch shows the depth and duration of the dip.
- **Ripple**: AC coupling (removes the DC component), 20–50 mV/div, 10–50 µs/div timebase: you see the ESC/BEC switching frequency and the p-p amplitude. Measure with a short ground spring instead of the long alligator lead, otherwise you pick up interference from the probe itself.
- **Signals**: servo PWM is a 1–2 ms pulse every 20 ms (50 Hz); UART is bursts of bits with the idle line high; DShot is bursts of 16 pulses of varying width.
- **A ×10 probe** loads the circuit less and widens the bandwidth; for 3.3 V logic it is mandatory.

Bandwidth and rise time are related by the rule t_r ≈ 0.35 / BW: a 50 MHz scope itself "draws" an edge no faster than 7 ns, a 100 MHz one 3.5 ns. For DShot600 (1.67 µs bit) even 20 MHz is enough; for ringing on ESC MOSFET edges you need 100 MHz and a ×10 probe (at ×1 a typical probe has a bandwidth of only a few MHz; a course guideline, check your probe's datasheet). Measure BEC ripple with the 20 MHz bandwidth limit on: that cuts off radio noise that has nothing to do with the supply.

**Probe ground and ground loops.** The ground clip of a benchtop scope is connected to the protective earth of the outlet. If the flight controller is connected over USB to a laptop that is also earthed through its power supply, a loop forms through the two grounds: interference current flows in it, and the trace looks noisier than the aircraft really is. On a battery, with the laptop on its battery, there is no such loop. On mains power, never clip the probe ground to a point that is not circuit ground (for example, the positive side of a shunt): that is a short circuit through the earth wire.

### Sampling and aliasing
A digital instrument and a flight controller do not see the signal continuously; they take samples at a rate f_s. Anything above f_s/2 (the Nyquist frequency) appears in the data at a false frequency f_alias = |f − k·f_s|, where k is the nearest integer to f/f_s. Three places where this bites in practice:

1. **A long scope timebase.** Sample rate = memory depth / (10 divisions × time per division). 10 thousand points of memory at 100 ms/div is 10 kHz: 24 kHz ESC ripple is drawn as 4 kHz (from the lab). The sign: the "ripple frequency" changes when you change the timebase. The cure: a short timebase or peak detect mode.
2. **The flight controller's current sensor.** Betaflight 2025.12.5 polls the current in a 50 Hz task and smooths it with a 1 Hz PT1 filter (`ibat_lpf_period` = 10, in tenths of a second); ArduCopter 4.7.3 reads the battery in a 10 Hz task. ESC ripple at tens of kHz cannot be measured at that sample rate in principle; the flight controller reading is only good for average current and mAh.
3. **Logs.** A gyro logged at 1 kHz shows a 1010 Hz vibration as 10 Hz. That is why an analog or digital filter below f_s/2 is placed before the sampling (Betaflight: `acc_lpf_hz` 25 Hz before the 100 Hz attitude task).

{{lesson:ctl-signals|Gyro spectrum, log rate and anti-aliasing filters, with a synthetic signal where the answer is known.}}

### Calibrating the flight controller's voltage and current sensors
In every firmware the voltage is directly proportional to the divider factor, so the calibration is the same: **new = old × V_multimeter / V_FC**. Current is different: in Betaflight and INAV the slope is set in mV/A (the reading is **inversely** proportional to the parameter), in ArduPilot and PX4 in A/V (the reading is **directly** proportional). Getting the direction of the proportion backwards is the most common mistake: the current is not corrected but goes twice as far off.

The formulas from the source:
- Betaflight 2025.12.5 (`sensors/current.c`): I[mA] = 10000 · U[mV] / `ibata_scale` + `ibata_offset`; the offset is added **after** the scale, in mA.
- ArduPilot 4.7.3 (`AP_BattMonitor_Analog.cpp`): I = (U − `BATT_AMP_OFFSET`) · `BATT_AMP_PERVLT`; U = (U_pin − `BATT_VLT_OFFSET`) · `BATT_VOLT_MULT`.
- PX4 1.18.0 (`analog_battery.cpp`): I = (U − `BAT_V_OFFS_CURR`) · `BAT1_A_PER_V`; U = U_ADC · `BAT1_V_DIV`; the code clips negative current to 0 (`fmaxf(current_a, 0.f)`) only when the current filter is enabled, `BAT1_I_FILT` > 0 (default 0); in that case an excessive offset is invisible at zero, so check it at a low current.
- INAV 9.1.0 (`sensors/battery.c`): I = (U − offset)/`current_meter_scale`, scale in 0.1 mV/A; in the code the offset is subtracted as `current_meter_offset` × 100 µV, i.e. in units of 0.1 mV, although the parameter description says "millivolts" (inferred from the code, line 557).

**One point or two.** Calibrating against the charger's mAh (one flight) corrects only the slope and is accurate at that flight's average current. If the sensor has a zero offset, the error at low current stays large: in the lab, a sensor with a 50 mV offset is off by +74 % at 2 A and by −2.2 % at 25 A after a one-flight calibration. Two or more points against a clamp meter (a low and a high current) give both the slope and the offset: an error of < 0.5 % over the whole range. The order: voltage first, then the offset at zero motor current, then the slope at high current, and a check against the mAh after a flight (course guideline: within < 5 % of the charger).

| Firmware | Parameter | Default | Unit | Reading vs parameter |
|---|---|---|---|---|
| Betaflight 2025.12.5 | `vbat_scale` | 110 (0…255; the board can override it) | divider factor × 10 (with `vbat_divider` 10) | direct |
| Betaflight 2025.12.5 | `vbat_divider`, `vbat_multiplier` | 10, 1 | — | additional divisors in the formula: V = U_pin·vbat_scale/(vbat_divider·vbat_multiplier); 110/10 = 11 = a 10 kΩ : 1 kΩ divider |
| Betaflight 2025.12.5 | `ibata_scale` | 400 (−16000…16000) | 0.1 mV/A | inverse |
| Betaflight 2025.12.5 | `ibata_offset` | 0 | mA, after the scale | offset |
| Betaflight 2025.12.5 | `ibat_lpf_period` | 10 | 0.1 s (PT1 1 Hz) | — |
| ArduPilot 4.7.3 | `BATT_VOLT_MULT` | 10.1 or from hwdef (MatekH743: 11.0) | V/V | direct |
| ArduPilot 4.7.3 | `BATT_AMP_PERVLT` | 17.0 or from hwdef (MatekH743: 40.0) | A/V | direct |
| ArduPilot 4.7.3 | `BATT_AMP_OFFSET`, `BATT_VLT_OFFSET` | 0, 0 | V, before the scale | offset |
| PX4 1.18.0 | `BAT1_V_DIV` | −1 in module.yaml; on fmu-v6c `set-default` 18.1 | V/V | direct, reboot required |
| PX4 1.18.0 | `BAT1_A_PER_V` | −1 in module.yaml; on fmu-v6c `set-default` 36.367515 | A/V | direct, reboot required |
| PX4 1.18.0 | `BAT_V_OFFS_CURR` | 0 | V, before the scale | offset |
| INAV 9.1.0 | `vbat_scale`, `current_meter_scale` | 1100, 400 (if the board does not set them) | ×100 of the divider; 0.1 mV/A | direct; inverse |

{{lesson:bf-setup-scratch|Step-by-step calibration of vbat_scale, ibata_scale and ibata_offset in Betaflight 2025.12 on the bench and after a flight, with error criteria.}}

{{diagram:chart-measure-current-calibration|A one-flight calibration is accurate only at that flight's average current: a sensor with a 50 mV offset is off by +74 % at 2 A, while two clamp-meter points give < 0.5 % over the whole range.}}

### DShot on the oscilloscope
A DShot frame is 16 bits: 11 throttle bits, 1 telemetry bit, 4 CRC bits. Each bit is a pulse: a "1" is long (~75% of the bit period), a "0" is short (~37%). DShot600 is 600 kbit/s, a bit is ≈ 1.67 µs (high time ≈ 1.25 µs for a "1" and ≈ 0.62 µs for a "0"), a frame is ≈ 16 × 1.67 ≈ 27 µs. On screen it is a burst of 16 pulses repeating at the PID loop rate (for example, every 125 µs at 8 kHz). Problems you can see: ringing on the edges (a long wire, no termination), a level that does not reach 3.3 V (a weak driver), dropped frames.

{{diagram:dshot600-pulse-train|Frame 0x82C6 over time: the bit is carried by the pulse width; a "1" stays high for ~75 % of the bit, a "0" for ~37 %, and the 16 bits of DShot600 take ≈ 27 µs.}}

### Logic analyzer
Records digital levels on many channels and decodes protocols. A cheap 8-channel 24 MHz unit with software such as PulseView/sigrok is enough for UART up to 1 Mbaud, I2C at 400 kHz, SPI up to a few MHz and DShot600 (you need ≥ 4–5 samples per bit, preferably 12–24 MHz).

- **UART**: connect to the TX line and GND, set the baud rate (115200 for MSP, 420000 for CRSF!), and the decoder shows the bytes. What you can see: the wrong baud rate (garbage), inversion (SBUS is an inverted UART at 100000 8E2).
- **I2C**: SDA and SCL; the decoder shows addresses and ACK/NACK. A NACK on the address means the sensor is absent or has a different address; no pull-up means the lines do not go high.
- **SPI**: CLK, MOSI, MISO, CS: reading the gyro registers.
- Always share ground with the aircraft. Levels are 3.3 V; most analyzers tolerate 5 V lines, but not 12 V.

### Measurement safety
- Props off for any measurement involving ESCs/motors.
- The scope ground is connected to protective earth: on a circuit that is not referenced to earth (battery power) this is fine; on a mains-powered supply you must not clip the probe ground to a point at a potential.
- The probe must not touch two pins at once: the tiny pads on an FC are the main way to cause a short with an instrument.

{{diagram:measure-tools|Which instrument for which question: values from the multimeter, waveforms from the oscilloscope, protocols from the logic analyzer.}}

### Where it fits in the system

- **Takes in:** measurement points: buses and BEC rails (`el-power-design`), UART and I²C lines (`el-peripherals`), the DShot signal (`f-motors-esc`); a hypothesis from the troubleshooting tree (`diag-troubleshooting`).
- **Puts out:** facts: BEC voltage under load, depth and duration of sag, ripple amplitude, protocol bytes and baud rate, into the branches of the tree (`diag-troubleshooting`); voltage and current calibration factors into the remaining battery estimate (`f-power`).
- **If you get this wrong:** current calibrated with the proportion backwards, or with one point on a sensor with an offset → the mAh in the OSD are wrong, and the capacity warning and the mAh failsafe come at the wrong time (`bf-setup-scratch`, `px4-setup-scratch`). Sag hunted with a multimeter (it shows the average) → "the power is fine", yet the flight controller reboots on a throttle punch; you need a scope on the power bus (`el-power-design`). The UART decoder set to 115200 instead of 420000 for CRSF → garbage on screen and the false conclusion "the receiver is faulty" (`link-protocols`).

## practice
### Step 1. Map of measurement points
On the aircraft diagram, mark: the power bus, the 5 V output, the 9 V output, the receiver UART, DShot on one motor, the compass I2C. Find convenient pads.

### Step 2. Sag under load
Without props the measurement is meaningless: use the log (VBAT in hover) or a scope on a test stand with a real load (the aircraft tied down, props on, short throttle pulses, with extreme care and an observer). Record: U at no load, U at maximum, the duration of the dip.

### Step 3. BEC ripple
AC coupling, 5 V under the receiver/GPS load. Record p-p and frequency. Compare with and without the capacitor on the power bus.

### Step 4. DShot and UART with the analyzer
Capture a DShot frame at low throttle without props: decode the 16 bits by hand, calculate the throttle value (DShot 48–2047) and check the CRC. Capture CRSF between the receiver and the FC at 420000 baud: find the channels frame (type 0x16).

### Step 5. Calibrating the voltage and current sensors (calculation)
The main path for this step is a calculation without hardware, from bench measurements. Input data: the multimeter on the XT60 reads 24.12 V, the flight controller 23.71 V; the DC clamp on the power wire reads 2, 10 and 25 A (the load is a resistor bank or a motor test without props), and three flight controllers with their boards' defaults showed the currents recorded in the script. The sensor is the same one: 50 mV + 27.5 mV/A. The script calculates the new factors for Betaflight, ArduPilot and PX4, compares a one-flight (mAh) calibration with a two-point one, and checks the aliasing from the theory.

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

Actual output of `python3 calib_lab.py`:

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

How to read it. Voltage in all three firmwares is corrected with one proportion; in Betaflight `vbat_scale` is an integer (uint8), so 111.9 rounds to 112 and an error of 0.02 V remains (less than 4 mV per cell on 6S). Current: Betaflight gets a new `ibata_scale` = 400 / 1.4548 = 275, which is **smaller** than the old one even though the flight controller was reading low: the reading is inversely proportional to the parameter. ArduPilot and PX4 recover the sensor's properties directly: 36.36 A/V (= 1/27.5 mV/A) and an offset of 0.050 V. The "scale-only" lines show the cost of a one-point calibration on a sensor with an offset.

### Step 6. Measurement table
Table: point, instrument, value, normal range, conclusion.

### A decoded DShot frame
Throttle value 1046, telemetry bit 0. Twelve bits: `10000010110 0`. CRC = (v ⊕ v>>4 ⊕ v>>8) & 0xF = 6 (`0110`), where v is these 12 bits. The frame is the 16 bits `1000001011000110` (0x82C6). On the scope each DShot600 bit lasts ≈ 1.67 µs: a "1" is a long high pulse, a "0" a short one. From your captured frame, calculate the value and CRC and compare them with the throttle you set.

### What you should get and what to record
- **Sag under load:** VBAT in the log in hover and during a short full-throttle punch: the difference and how it relates to the internal resistance from the "Electricity" module.
- **BEC ripple:** the peak-to-peak (p-p) amplitude on 5 V under load is tens of millivolts for a good BEC (a course guideline). Hundreds of millivolts mean interference in the video and sensor glitches. Record p-p and frequency with and without the capacitor on the power bus.
- **CRSF:** the channels frame starts with the address byte `0xC8`, then the length `0x18` (24) and the type `0x16` (RC channels packed): 16 channels of 11 bits each.
- **Table:** point, instrument, value, normal range, conclusion: one row per measurement. Without the "normal range" column a measurement tells you nothing.

### Moving to real hardware
Props are off for every calibration step. The sequence for current calibration: (1) multimeter on the XT60, the flight controller on the battery: correct the voltage to an error of < 0.05 V per cell (a course guideline); (2) motors stopped, electronics current only (0.2–0.5 A on the clamp, a course guideline): check the zero; (3) a 5–30 A load: a bank of power resistors or a motor test without props in short 3–5 s pulses, the clamp on one power wire (on both at once the clamp reads zero), recording the flight controller reading at the same moment; (4) calculation with the step 5 script; (5) after a flight, compare the mAh with the charger. Abort the test if the wires or connector get noticeably hotter than usual or the current rises without a command: disconnect the battery. Criteria: voltage within 0.05 V per cell; current at the three points within 3 % of the clamp (a course guideline: the combined error of the clamp and the reading); mAh after a flight within 5 % of the charger.

Self-check: the lab is done when (calculation path) the step 5 script produced output matching the one shown: `vbat_scale` 112, `BATT_VOLT_MULT` 11.190, `BAT1_V_DIV` 18.413, `ibata_scale` 275 and `ibata_offset` −1827 mA, `A_PER_V` 36.364 / 36.368 and an offset of 0.0500 V, scale-only 302 with a +74.1 % error at 2 A; you can explain without the script why `ibata_scale` went down while `BATT_AMP_PERVLT` for the same sensor became 36.4, and calculate f_alias = |24000 − 2·10000| = 4000 Hz; (hardware) the sag under load has been measured and related to the internal resistance, a DShot frame has been captured with the analyzer and decoded by hand, with the calculated CRC matching the last four bits of the frame and the throttle value matching what you set (check the formula on the decoded frame first: 1046 → CRC 6, 0x82C6), or in a CRSF frame you found `0xC8`, the length `0x18` and the type `0x16`; the BEC ripple has been measured with and without the capacitor and recorded in the table with the normal ranges (tens of millivolts p-p is a good BEC, hundreds a bad one); after calibration the current at the three points is within 3 % of the clamp, and the flight's mAh are within 5 % of the charger.

**Reference answer for self-check.** The correct Betaflight current calibration from the step 5 data: `ibata_scale` 275, `ibata_offset` −1827 mA; ArduPilot and PX4: 36.36 A/V and 0.050 V. All three describe the same 27.5 mV/A sensor with a 50 mV offset. Common wrong results: `ibata_scale` 400 × 1.4548 = 582 means the proportion is backwards and the current will read even lower (for ArduPilot/PX4 the opposite mistake is dividing instead of multiplying); the mAh calibration matched after the flight, but in hover or on the ground the current is off by tens of percent, meaning the offset was not taken into account and you need a second point; the clamp reads zero on the power pair, meaning both wires, plus and minus, are inside the jaws and their fields cancel.

## diagnostics
- **Symptom:** the multimeter shows 5.0 V, but the FC reboots
  - Possible cause: a short sag that the multimeter cannot see.
  - What to do: a scope with a falling-edge trigger, or the log.
- **Symptom:** huge ripple on everything on the scope
  - Possible cause: the long probe ground lead picks up interference.
  - What to do: a ground spring, measure right at the capacitor.
- **Symptom:** the analyzer shows garbage on the UART
  - Possible cause: the wrong baud rate or inversion (SBUS).
  - What to do: find the right baud rate, enable inversion in the decoder.
- **Symptom:** an I2C sensor does not respond (NACK)
  - Possible cause: no pull-up, a different address, SDA/SCL swapped.
  - What to do: check the idle levels (they must be high), scan the addresses.
- **Symptom:** the mAh in the OSD match the charger, but on the ground with the battery connected the flight controller shows 1–2 A
  - Possible cause: a one-point calibration on a sensor with a zero offset.
  - What to do: a second point at low current against the clamp; correct `ibata_offset` (Betaflight) or `BATT_AMP_OFFSET` / `BAT_V_OFFS_CURR`.
- **Symptom:** after calibration the current is even further from the truth
  - Possible cause: the proportion is backwards: in Betaflight and INAV the reading is inversely proportional to the scale, in ArduPilot and PX4 directly.
  - What to do: recalculate with the formula from the theory table; on PX4 reboot the flight controller (the parameter is reboot required).
- **Symptom:** the ripple frequency on screen changes when you change the timebase
  - Possible cause: aliasing: too few samples for a long timebase.
  - What to do: a short timebase (10–50 µs/div) or peak detect; check f_s = memory / (10 × time per division).
- **Symptom:** ringing on the DShot edges
  - Possible cause: long signal wires, no common ground with the ESC.
  - What to do: shorten them, add a ground next to the signal, drop DShot to 300.

## references
- Betaflight 2025.12.5 — `src/main/sensors/current.c` (ibata_scale, ibata_offset, 50 Hz task) | https://raw.githubusercontent.com/betaflight/betaflight/2025.12.5/src/main/sensors/current.c | primary | A
- ArduPilot Copter-4.7.3 — `AP_BattMonitor_Analog.cpp` (BATT_VOLT_MULT, BATT_AMP_PERVLT, BATT_AMP_OFFSET) | https://raw.githubusercontent.com/ArduPilot/ardupilot/Copter-4.7.3/libraries/AP_BattMonitor/AP_BattMonitor_Analog.cpp | primary | A
- PX4 v1.18.0 — `battery_status/module.yaml` and `analog_battery.cpp` (BAT1_V_DIV, BAT1_A_PER_V, BAT_V_OFFS_CURR) | https://raw.githubusercontent.com/PX4/PX4-Autopilot/v1.18.0/src/modules/battery_status/analog_battery.cpp | primary | A
- Betaflight — DSHOT ESC Protocol | https://betaflight.com/docs/development/API/Dshot | primary | A
- sigrok — PulseView (logic analyzer software) | https://sigrok.org/wiki/PulseView | primary | A
- Crossfire/CRSF protocol — TBS (community reference) | https://github.com/crsf-wg/crsf/wiki | secondary | B

## checklist
- I know that a multimeter does not see sag and ripple
- I captured 5 V ripple with AC coupling and a ground spring
- I decoded a DShot frame by hand
- I decoded UART/I2C with the analyzer
- All measurements involving ESCs are done without props
- I know where the current reading is directly and where inversely proportional to the parameter, and I calibrate with two points
- I calculate the scope sample rate from the timebase and recognize aliasing
