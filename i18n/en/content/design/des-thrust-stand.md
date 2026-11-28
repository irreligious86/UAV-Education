---
id: des-thrust-stand
title: "Thrust stand: load cell + HX711, current, RPM, efficiency"
level: L2
readingTime: 40 min
firmware: ESP32 (Arduino core 2.x / 3.x), no autopilot
status: published
tags:
  - thrust stand
  - load cell
  - HX711
  - propulsion
  - measurements
related:
  - f-aero-props
  - f-motors-esc
  - el-measure
  - comp-esp32
  - f-safety
next:
  - aero-stability
source: content/design/des-thrust-stand.md
source_hash: e41928b9dc5e
---

## summary
A manufacturer's thrust table was taken with their ESC, their prop and at their temperature; your combination can differ by 5–15 %, and the only way to find out is a thrust stand. This module teaches you to build a stand on an ESP32 (a load cell + HX711, an INA226 for current and voltage, an optical sensor for RPM), calibrate it (scale, tare, drift, creep), compute the uncertainty, the g/W curve, C_T and the figure of merit FM. The main path is processing a realistic data set based on the T-Motor MN4006 KV380 + 15×5 table; the hardware section covers building and calibrating a real stand.

## theory
### What the stand measures and why
The minimum is four quantities with one timestamp: thrust T, voltage U, current I, RPM n. From them: P = U·I, the specific thrust T/P (g/W) and C_T. A reaction torque sensor Q adds the shaft power P_shaft = 2π·n·Q, and with it the drive efficiency and the prop FM.

{{diagram:stand-signal-chain|A stand is four channels with one timestamp. Safety (the current limit, the command timeout) lives in the ESP32 and depends neither on the HX711 nor on the PC.}}

### The load cell and the HX711
A bar load cell is a Wheatstone bridge of four strain gauges. The output is proportional to the load and to the excitation voltage: U_out = S·U_exc·F/F_rated, where S is the sensitivity in mV/V. A typical cheap bar (the TAL220 series; the figures are from the TAL220F datasheet, which gives 1.0 mV/V for the 1–3 kg capacities, and we take a 5 kg bar to be the same) has S = 1.0 ± 0.15 mV/V, nonlinearity and hysteresis ±0.05 % FS, creep ±0.1 % FS over 30 min, and a temperature effect on zero of ±0.2 % FS per 10 °C. For a 5 kg bar that is ±2.5 g of nonlinearity, ±5 g of creep and ±10 g of zero shift per 10 °C. Hence the main rule: tare before and after every run.

The HX711 is a 24-bit ADC for a bridge. Channel A at gain 128 gives a full-scale input of ±0.5·AVDD/128 (±20 mV at 5 V). The rate is 10 or 80 samples/s (the RATE pin; the course uses 10: each sample is averaged 8 times longer, so the noise is lower, and over a 10 s throttle step that is still 100 samples, of which the first seconds after the step are discarded; 80 is only for fast processes, such as the motor spinning up after a throttle step, at the cost of noise; course guideline), the format is two's complement, saturating at 800000h / 7FFFFFh. The bridge is usually powered from the same AVDD, so the measurement is ratiometric and does not depend on the exact voltage: S·128·2²³ / 0.5 = 2 147 484 counts at full scale, that is about 430 counts/g for a 5 kg bar. 24 PD_SCK pulses carry the data, and the 25th selects channel A×128. The trap is elsewhere: if PD_SCK stays high for longer than 60 µs, the chip enters power-down. An interrupt (Wi-Fi, another ISR) in the middle of a read corrupts the sample, so the read must run in a critical section.

### Calibration: the error model
The model of a raw sample: raw = b + k·m + e_nonlin + e_hyst + e_creep(t) + e_drift(t) + noise.

- **Tare b** is the mean with no load. Its drift (the motor and ESC warm the bar) is removed with a zero before and after the run and linear interpolation in time.
- **Scale k** is a least-squares fit over 5–6 known masses: k = Σ(m−m̄)(y−ȳ) / Σ(m−m̄)². The residuals after the fit give the nonlinearity.
- **Hysteresis** is the difference in readings at the same mass when loading and when unloading.
- **Creep** is a slow rise of the reading under a constant load: small for a 10 s step, noticeable in a 30 min run.
- **Geometry.** Calibrate with a force along the prop axis at the point where thrust is applied: a string from the motor axis over a pulley on a bearing to the weights, or the stand turned with its axis up. A "weight on the bar" placed elsewhere gives a lever-arm error.

### Current, voltage, RPM
The INA226 measures the drop across a shunt (full scale ±81.92 mV, LSB 2.5 µV) and the bus voltage (up to 36 V, LSB 1.25 mV). The calibration register is CAL = 0.00512 / (Current_LSB·R_shunt). With a 2 mΩ shunt and Current_LSB = 1.25 mA you get CAL = 2048 and a full scale of 40.96 A, and the shunt dissipates 0.45 W at 15 A. The current error is set by the shunt tolerance (usually 1 %), not by the ADC. Measure the voltage at the ESC input, not at the power supply.

RPM comes from an optical sensor (a mark on the bell, RPM = 60·10⁶ / (period_µs · marks)) or from ESC telemetry. Bidirectional DShot reports eRPM, and the mechanical RPM is eRPM / (number of poles / 2). The MN4006 has 24 poles, so the divider is 12.

### Dimensionless coefficients
Per the UIUC definitions (Brandt & Selig): C_T = T / (ρ·n²·D⁴), C_P = P_shaft / (ρ·n³·D⁵), with n in rev/s and D in m. Air density ρ = p / (287.05·T_K), which at 20 °C and 101.325 kPa is 1.204 kg/m³. Measure it on the day of the run: at 35 °C it is 5 % lower, and so is the thrust at the same RPM.

The figure of merit is the fraction of the real shaft power that is the ideal power of an actuator disc:

**FM = P_id / P_shaft, P_id = T^1.5 / √(2·ρ·A), A = π·D²/4.**

In terms of coefficients based on n and D: FM = C_T^1.5 / (√(π/2)·C_P). The well-known formula C_T^1.5 / (√2·C_P) from helicopter textbooks may be used only with helicopter C_T and C_P, normalized by Ω·R. If you plug propeller coefficients into it, you get an FM 11 % below the truth. Without a torque sensor all you have is P_el, and P_id / P_el = FM·η_drive: that is a system efficiency, not the quality of the prop.

### Place in the system

- **Receives:** the motor, ESC and prop as one combination (`f-motors-esc`); eRPM over bidirectional DShot (`f-esc-firmware`); the methods of measuring current and voltage (`el-measure`); the ESP32 with its interrupts (`comp-esp32`).
- **Provides:** the measured g/W, C_T and system FM to the vehicle sizing (`des-sizing`); the real maximum thrust of your combination to the T/W check.
- **If you get it wrong here:** no tare before and after the run → the zero drift from warming goes into the thrust, the FM is wrong, and the calculated flight time does not match the log (`des-sizing`). An eRPM divider from the wrong pole count → RPM and C_T are wrong; the same mistake in `motor_poles` puts the RPM filter off the noise (`bf-rpm-filter`).

## practice
### Step 1. The data set
The basis is the T-Motor MN4006 KV380 table with a 15×5 CF prop at 24 V: seven throttle points from 50 to 100 %, current, RPM, torque, thrust. The generator builds a "stand" log from it with the errors from the theory: HX711 noise, nonlinearity, 0.8 g hysteresis, 1.2 g creep, +4 g zero drift, vibration of 0.8 % of thrust, INA226 quantization. The motor specimen is made "slightly worse than the datasheet": RPM 1.5 % lower (same C_T) and current 5 % higher (a different ESC). The job of the processing is to find this.

```python
#!/usr/bin/env python3
"""Synthetic thrust-stand log: T-Motor MN4006 KV380 + 15x5 CF @ 24 V (store.tmotor.com table)
plus realistic HX711 / INA226 / optical-tach errors. Reproducible: seed 42, stdlib only."""
import csv, math, random

R = random.Random(42)
# throttle %, current A, RPM, thrust g  -- manufacturer table, 15x5 CF, 24 V
TABLE = [(50, 3.1, 3746, 805), (55, 4.1, 4089, 959), (60, 4.8, 4358, 1093), (65, 5.8, 4634, 1236),
         (75, 8.3, 5215, 1561), (85, 10.7, 5627, 1823), (100, 15.0, 6177, 2228)]
K, OFS, FS = 431.7, 84213, 5000.0           # counts/g, zero unbalance (counts), cell capacity g
SPS = 10                                     # HX711 RATE=0

def raw(m_g, extra_g=0.0):                  # cell + HX711: nonlinearity <=0.03 %FS, noise 40 counts
    nl = 4 * 0.0003 * FS * (m_g / FS) * (1 - m_g / FS)
    return round(OFS + K * (m_g + nl + extra_g) + R.gauss(0, 40))

with open("calib.csv", "w", newline="") as f:          # 20 samples per weight, load up then down
    w = csv.writer(f); w.writerow(["dir", "ref_g", "raw"])
    for d, seq in (("up", [0, 100, 200, 500, 1000, 2000]), ("down", [1000, 500, 0])):
        for m in seq:
            for _ in range(20):
                w.writerow([d, m, raw(m, 0.8 if d == "down" and m else 0.0)])

with open("creep.csv", "w", newline="") as f:          # 1000 g left on for 600 s
    w = csv.writer(f); w.writerow(["t_s", "raw"])
    for i in range(600 * SPS):
        t = i / SPS
        w.writerow([t, raw(1000, 1.2 * (1 - math.exp(-t / 300)))])

# the specimen: 1.5 % lower RPM than the datasheet (C_T unchanged) and 5 % more current (other ESC)
with open("run.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["t_s", "thr", "raw", "volt", "amp", "rpm"])
    t, T_END = 0.0, 20 + len(TABLE) * 10 + 20
    def row(thr, thrust, amp, rpm):
        global t
        drift = 4.0 * t / T_END                              # zero drift +4 g (cell warms up)
        vib = R.gauss(0, 0.008 * thrust + 1.5) if thrust else 0.0
        a = amp + R.gauss(0, 0.015) if amp else R.gauss(0, 0.002)
        v = 24.0 - 0.02 * a + R.gauss(0, 0.005)
        r = rpm * (1 + R.gauss(0, 0.003)) if rpm else 0
        w.writerow([f"{t:.1f}", thr, raw(thrust, drift + vib), f"{round(v / 0.00125) * 0.00125:.5f}",
                    f"{round(a / 0.00125) * 0.00125:.5f}", round(r)])
        t += 1 / SPS
    for _ in range(20 * SPS): row(0, 0, 0, 0)                # pre-tare, motor stopped
    for thr, amp, rpm, thrust in TABLE:
        n = rpm * 0.985
        for _ in range(10 * SPS): row(thr, thrust * 0.985 ** 2, amp * 1.05, n)
    for _ in range(20 * SPS): row(0, 0, 0, 0)                # post-tare
print("calib.csv creep.csv run.csv written")
```

```text
$ python3 gen_stand_data.py
calib.csv creep.csv run.csv written
$ wc -l *.csv
   181 calib.csv
  6001 creep.csv
  1101 run.csv
```

### Step 2. Calibration, creep, drift
One script: blocks 1–3 are the calibration and the points, block 4 is the uncertainty (step 4).

```python
#!/usr/bin/env python3
"""Thrust-stand processing: calibration, creep, drift, g/W, C_T, uncertainty."""
import csv, math, statistics as st
from collections import defaultdict

rd = lambda fn: list(csv.DictReader(open(fn)))
RHO, D = 1.204, 15 * 0.0254                    # 20 C, 101.325 kPa; 15" prop
DS = {50: (805, 74), 55: (959, 98), 60: (1093, 115), 65: (1236, 139),   # datasheet: g, W
      75: (1561, 199), 85: (1823, 257), 100: (2228, 360)}

# 1. calibration: least squares raw = b + k*m on the loading branch
g = defaultdict(list)
for r in rd("calib.csv"): g[(r["dir"], int(r["ref_g"]))].append(int(r["raw"]))
up = sorted((m, st.mean(v)) for (d, m), v in g.items() if d == "up")
xm, ym = st.mean(m for m, _ in up), st.mean(y for _, y in up)
k = sum((m - xm) * (y - ym) for m, y in up) / sum((m - xm) ** 2 for m, _ in up)
b = ym - k * xm
res = [(y - b - k * m) / k for m, y in up]
hyst = max((st.mean(g[("down", m)]) - st.mean(g[("up", m)])) / k for m in (500, 1000))
noise = st.stdev(g[("up", 0)]) / k
print(f"k = {k:.2f} counts/g, offset = {b:.0f}, max residual = {max(map(abs, res)):.2f} g, "
      f"hysteresis = {hyst:.2f} g, noise = {noise:.2f} g")

# 2. creep: last 60 s vs first 30 s under 1000 g
c = [int(r["raw"]) for r in rd("creep.csv")]
creep = (st.mean(c[-600:]) - st.mean(c[:300])) / k
print(f"creep 1000 g / 10 min = {creep:+.2f} g")

# 3. run: zero before/after, linear drift correction, steady 2..10 s of each step
run = rd("run.csv")
zero = [r for r in run if r["thr"] == "0"]
pre = [r for r in zero if float(r["t_s"]) < 20]; post = [r for r in zero if float(r["t_s"]) >= 20]
z0, z1 = st.mean(int(r["raw"]) for r in pre), st.mean(int(r["raw"]) for r in post)
t0, t1 = st.mean(float(r["t_s"]) for r in pre), st.mean(float(r["t_s"]) for r in post)
print(f"zero drift over run = {(z1 - z0) / k:+.2f} g")
GW = sorted((t, t / p) for t, p in DS.values())      # datasheet g/W vs thrust
def gw_ds(T):                                       # linear interpolation, extrapolate at the ends
    (a, fa), (b, fb) = next(((p, q) for p, q in zip(GW, GW[1:]) if T <= q[0]), GW[-2:])
    return fa + (fb - fa) * (T - a) / (b - a)
steps = defaultdict(list)
for r in run:
    if r["thr"] != "0": steps[int(r["thr"])].append(r)
print("thr   T,g    I,A    P,W   g/W   rpm    C_T    T/T_ds  gW/gW_ds(same T)")
out = []
for thr, rows in sorted(steps.items()):
    rows = rows[20:]                                   # drop 2 s of spool-up
    tm = st.mean(float(r["t_s"]) for r in rows)
    zt = z0 + (z1 - z0) * (tm - t0) / (t1 - t0)
    T = (st.mean(int(r["raw"]) for r in rows) - zt) / k
    sT = st.stdev(int(r["raw"]) for r in rows) / k
    I = st.mean(float(r["amp"]) for r in rows); V = st.mean(float(r["volt"]) for r in rows)
    n = st.mean(float(r["rpm"]) for r in rows) / 60
    ct = T / 1000 * 9.80665 / (RHO * n ** 2 * D ** 4)
    Tds, Pds = DS[thr]
    out.append((thr, T, sT, len(rows), I, V))
    print(f"{thr:3d} {T:7.1f} {I:6.2f} {V*I:6.1f} {T/(V*I):5.2f} {n*60:5.0f} {ct:.4f} "
          f"{T/Tds:6.3f} {T/(V*I)/gw_ds(T):7.3f}")

# 4. uncertainty budget for the 50 % point (standard uncertainties, g)
thr, T, sT, N, I, V = out[0]
u = {"noise+vibration s/sqrt(N/5)": sT / math.sqrt(N / 5),
     "scale factor (weights 0.05 %)": T * 0.0005 / math.sqrt(3),
     "nonlinearity (max residual)": max(map(abs, res)) / math.sqrt(3),
     "drift correction (half)": abs(z1 - z0) / k / 2 / math.sqrt(3),
     "creep": abs(creep) / math.sqrt(3), "hysteresis": abs(hyst) / 2 / math.sqrt(3)}
for name, val in u.items(): print(f"  {name:31s} {val:5.2f} g")
uT = math.sqrt(sum(v * v for v in u.values()))
uI = 0.01 / math.sqrt(3)                               # shunt 1 % tolerance dominates
ugw = math.sqrt((uT / T) ** 2 + uI ** 2)
print(f"T = {T:.0f} g, U(k=2) = {2*uT:.1f} g ({200*uT/T:.2f} %); g/W = {T/(V*I):.2f} +/- {2*ugw*T/(V*I):.2f} (k=2)")
```

```text
$ python3 process_stand.py
k = 432.01 counts/g, offset = 84254, max residual = 0.15 g, hysteresis = 0.81 g, noise = 0.06 g
creep 1000 g / 10 min = +0.97 g
zero drift over run = +3.29 g
```

Reading it. k = 432.01 counts/g matches the estimate from the theory (≈ 430). The residual after the fit is 0.15 g: over 0–2 kg the nonlinearity is below the vibration noise. Hysteresis of 0.81 g and creep of +0.97 g over 10 min are visible, but small. The zero drift of +3.29 g over the run is already 0.4 % of the thrust at the first point. Without the correction by the "after" zero, the whole curve would have shifted up.

### Step 3. The g/W curve and C_T
```text
thr   T,g    I,A    P,W   g/W   rpm    C_T    T/T_ds  gW/gW_ds(same T)
 50   780.7   3.25   77.9 10.03  3689 0.0798  0.970   0.907
 55   931.6   4.30  102.9  9.05  4027 0.0799  0.971   0.907
 60  1058.3   5.04  120.4  8.79  4290 0.0800  0.968   0.918
 65  1198.2   6.09  145.4  8.24  4564 0.0800  0.969   0.910
 75  1515.7   8.72  207.6  7.30  5138 0.0799  0.971   0.914
 85  1768.6  11.23  267.1  6.62  5539 0.0802  0.970   0.913
100  2161.9  15.75  373.1  5.79  6085 0.0812  0.970   0.914
```

Compare with the datasheet at equal thrust, not at equal "throttle": the throttle percentage depends on the ESC calibration. The last column is the stand's g/W relative to the table's g/W at the same thrust. C_T = 0.080 is constant across the points and matches the datasheet (0.0798 at 50 %, 0.0813 at 100 % from the table): the prop and the thrust channel are fine, and the thrust is 3 % lower only because the RPM is lower. At the same time g/W is consistently 8–9 % below the datasheet, and that is the electrical part: ESC, wiring, voltage. It is not noise, because the g/W uncertainty is ±1.3 % (step 4).

{{diagram:chart-stand-gpw|The stand gives g/W 8–9 % below the T-Motor table at the same thrust, while C_T matches: the prop is fine, the losses are in the drive. The difference is 6–7 times larger than the ±1.3 % uncertainty.}}

Application. A 3.5 kg quadcopter needs 880 g per motor. Per the datasheet that is a current of 3.1 + (880 − 805)/(959 − 805)·1.0 ≈ 3.6 A, that is 86 W and 10.2 g/W. Per the stand it is about 9.4 g/W (interpolating between 780.7 and 931.6 g), and the hover time will be 8 % shorter than the datasheet-based calculation.

### Step 4. The uncertainty budget
```text
  noise+vibration s/sqrt(N/5)      2.08 g
  scale factor (weights 0.05 %)    0.23 g
  nonlinearity (max residual)      0.09 g
  drift correction (half)          0.95 g
  creep                            0.56 g
  hysteresis                       0.23 g
T = 781 g, U(k=2) = 4.7 g (0.61 %); g/W = 10.03 +/- 0.13 (k=2)
```

The systematic contributions are uniform (divide by √3), and the total is the root of the sum of squares. The vibration samples are correlated, so the effective N is five times smaller (80 → 16). Vibration and drift dominate: what needs improving is the prop balance and the warm-up, not the ADC resolution. In g/W the main contribution is the 1 % shunt tolerance.

### Step 5. FM and drive efficiency from the datasheet torque
The stand has no torque sensor, but the T-Motor table has a torque column. With it you can separate the losses of the prop and of the drive:

```python
import math
RHO, D = 1.204, 15 * 0.0254
A = math.pi * D ** 2 / 4
# datasheet 15x5 @ 24 V: throttle, thrust g, power W (electric), rpm, torque N*m
for thr, Tg, Pel, rpm, tau in [(50, 805, 74, 3746, 0.15), (75, 1561, 199, 5215, 0.29), (100, 2228, 360, 6177, 0.40)]:
    T, n = Tg / 1000 * 9.80665, rpm / 60
    Psh = tau * 2 * math.pi * n                      # shaft power
    Pid = T ** 1.5 / math.sqrt(2 * RHO * A)          # ideal induced power (actuator disk)
    CT, CP = T / (RHO * n**2 * D**4), Psh / (RHO * n**3 * D**5)
    print(f"{thr:3d}%  P_shaft={Psh:5.1f} W  eta_drive={Psh/Pel:.2f}  P_ideal={Pid:5.1f} W  "
          f"FM={Pid/Psh:.2f}  FM(CT,CP)={CT**1.5/(math.sqrt(math.pi/2)*CP):.2f}  "
          f"wrong CT^1.5/(sqrt2*CP)={CT**1.5/(math.sqrt(2)*CP):.2f}  FM*eta={Pid/Pel:.2f}")
```

```text
 50%  P_shaft= 58.8 W  eta_drive=0.80  P_ideal= 42.3 W  FM=0.72  FM(CT,CP)=0.72  wrong CT^1.5/(sqrt2*CP)=0.64  FM*eta=0.57
 75%  P_shaft=158.4 W  eta_drive=0.80  P_ideal=114.3 W  FM=0.72  FM(CT,CP)=0.72  wrong CT^1.5/(sqrt2*CP)=0.64  FM*eta=0.57
100%  P_shaft=258.7 W  eta_drive=0.72  P_ideal=194.9 W  FM=0.75  FM(CT,CP)=0.75  wrong CT^1.5/(sqrt2*CP)=0.67  FM*eta=0.54
```

The prop FM comes out at 0.72–0.75 (the torque in the table is given to two significant figures, hence ±3–4 %), and the motor with the ESC delivers 72–80 % of the electrical power to the shaft. At full throttle the drive efficiency drops to 0.72: the copper losses grow as I². The `wrong` column shows what the helicopter formula gives with propeller coefficients.

### Step 6. The stand firmware (ESP32, PlatformIO)
`platformio.ini`: `platform = espressif32`, `board = esp32dev`, `framework = arduino`, `monitor_speed = 115200`. The HX711 is read by hand, without a library, so that the critical section is visible. Safety is checked every 100 ms in the main loop, independently of the HX711 (a dead HX711 does not stop it), and nothing in the loop may block for longer than a few milliseconds.

```cpp
// Thrust stand: HX711 (thrust) + INA226 (V, I) + optical tach (RPM) + ESC PWM. CSV at 10 Hz.
#include <Arduino.h>
#include <Wire.h>

const int HX_DOUT = 16, HX_SCK = 17, ESC_PIN = 25, TACH_PIN = 27;
const float I_LIMIT = 16.0f;          // A: MN4006 KV380 peak 16 A (180 s); fuse 20 A in series
const uint32_t CMD_TIMEOUT_MS = 500;  // no valid command from the PC -> throttle 0, disarm
const int RAMP_PER_TICK = 2;          // % per 100 ms tick = 20 %/s
const uint8_t INA = 0x40;
const int TACH_PPR = 1;               // reflective marks per revolution

portMUX_TYPE hxMux = portMUX_INITIALIZER_UNLOCKED;
volatile uint32_t tachPeriodUs = 0, tachLastUs = 0;
bool armed = false; int thrCmd = 0, thrOut = 0; uint32_t lastCmdMs = 0;

int32_t hx711Read() {                 // call only when DOUT is low (data ready)
  uint32_t v = 0;
  portENTER_CRITICAL(&hxMux);         // PD_SCK high > 60 us = power-down: no interrupts here
  for (int i = 0; i < 25; i++) {      // 24 data bits + 25th pulse: channel A, gain 128
    digitalWrite(HX_SCK, HIGH); delayMicroseconds(1);
    if (i < 24) v = (v << 1) | digitalRead(HX_DOUT);
    digitalWrite(HX_SCK, LOW);  delayMicroseconds(1);
  }
  portEXIT_CRITICAL(&hxMux);
  if (v & 0x800000) v |= 0xFF000000;  // sign-extend 24-bit two's complement
  return (int32_t)v;
}

void inaWrite(uint8_t reg, uint16_t val) {
  Wire.beginTransmission(INA); Wire.write(reg); Wire.write(val >> 8); Wire.write(val & 0xFF);
  Wire.endTransmission();
}
bool inaRead(uint8_t reg, int16_t &out) {  // false = I2C error: INA226 lost or not answering
  Wire.beginTransmission(INA); Wire.write(reg);
  if (Wire.endTransmission(false) != 0 || Wire.requestFrom(INA, (uint8_t)2) != 2) return false;
  uint8_t hi = Wire.read(), lo = Wire.read();  // MSB first: two separate reads, defined order
  out = (int16_t)((hi << 8) | lo); return true;
}

void IRAM_ATTR tachIsr() { uint32_t now = micros(); tachPeriodUs = now - tachLastUs; tachLastUs = now; }

void escWriteUs(int us) {             // 50 Hz, 16-bit: 1 us = 65536 / 20000 counts
  uint32_t duty = ((uint32_t)us * 65536UL + 10000UL) / 20000UL;
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(ESC_PIN, duty);
#else
  ledcWrite(0, duty);
#endif
}

void safetyTick(bool inaOk, float amps) {  // called every 100 ms from loop()
  if (millis() - lastCmdMs > CMD_TIMEOUT_MS) { armed = false; thrCmd = 0; }  // PC silent
  if (armed && (!inaOk || fabsf(amps) > I_LIMIT)) {  // fabsf: a reversed shunt reads < 0
    armed = false; thrCmd = 0;        // restart only after a new "arm" and a new "tNN"
    Serial.println(inaOk ? "#TRIP overcurrent" : "#TRIP INA226 lost");
  }
  if (!armed) thrOut = 0;             // disarm cuts immediately, ramp only upwards
  else thrOut += constrain(thrCmd - thrOut, -100, RAMP_PER_TICK);
  escWriteUs(1000 + thrOut * 10);
}

void handleSerial() {                 // "arm", "disarm", "t55" (throttle %), sent >= 5 Hz by the PC
  if (!Serial.available()) return;
  String s = Serial.readStringUntil('\n'); s.trim();  // waits <= 10 ms (setTimeout in setup)
  if (s == "arm") { if (thrOut == 0 && thrCmd == 0) armed = true; }  // arm only at throttle 0
  else if (s == "disarm") { armed = false; thrCmd = 0; }
  else if (s.startsWith("t")) thrCmd = constrain(s.substring(1).toInt(), 0, 100);
  else return;                        // unknown line or noise: does not refresh the timeout
  lastCmdMs = millis();
}

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(10);              // never block the safety loop on a partial line (default 1000 ms)
  pinMode(HX_SCK, OUTPUT); digitalWrite(HX_SCK, LOW);
  pinMode(HX_DOUT, INPUT_PULLUP);     // DOUT wire off -> reads HIGH = "not ready", no garbage reads
  pinMode(TACH_PIN, INPUT_PULLUP); attachInterrupt(TACH_PIN, tachIsr, FALLING);
  Wire.begin();
  inaWrite(0x00, 0x4527);             // AVG 16, VBUSCT = VSHCT = 1.1 ms, continuous
  inaWrite(0x05, 2048);               // CAL = 0.00512 / (1.25 mA * 2 mOhm)
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttach(ESC_PIN, 50, 16);
#else
  ledcSetup(0, 50, 16); ledcAttachPin(ESC_PIN, 0);
#endif
  escWriteUs(1000);
  Serial.println("ms,thr,raw,volt,amp,rpm");
}

void loop() {
  handleSerial();
  static uint32_t tSafe = 0; static float volt = 0, amp = 0;
  if (millis() - tSafe >= 100) {      // safety every 100 ms, whether or not the HX711 is alive
    tSafe += 100;
    int16_t rv, ra; bool ok = inaRead(0x02, rv) && inaRead(0x04, ra);
    if (ok) { volt = rv * 0.00125f; amp = ra * 0.00125f; }
    safetyTick(ok, amp);              // I2C error = sensor lost = trip
  }
  if (digitalRead(HX_DOUT) == LOW) {  // HX711 RATE=0: a new sample every 100 ms
    int32_t raw = hx711Read();
    uint32_t per = tachPeriodUs;
    float rpm = (per && micros() - tachLastUs < 500000UL) ? 60e6f / (per * TACH_PPR) : 0;
    Serial.printf("%lu,%d,%ld,%.3f,%.3f,%.0f\n", millis(), thrOut, (long)raw, volt, amp, rpm);
  }
}
```

Without a board, the logic is checked on a PC: the same `main.cpp` is built with `g++ -std=c++17`, with the Arduino API replaced by stubs and with HX711 and INA226 simulators; in the safety test the HX711 is "not ready" the whole time, the PC sends commands at 5 Hz, the serial stub behaves like the Arduino `Stream` (a line without `\n` blocks `readStringUntil` for the whole timeout), and the INA226 simulator can report a reversed shunt or drop off the I²C bus. The output (identical for core 2 and core 3):

```text
HX711 decode (DOUT pin mode INPUT_PULLUP):
  sent         0 -> read         0
  sent         1 -> read         1
  sent        -1 -> read        -1
  sent   8388607 -> read   8388607
  sent  -8388608 -> read  -8388608
  sent    421646 -> read    421646
Safety (HX711 not ready the whole time, PC commands at 5 Hz):
  t= 500 ms thrOut=10% ESC=1100 us
  t= 900 ms thrOut=18% ESC=1180 us
  t=1300 ms thrOut=26% ESC=1260 us
  t=1700 ms thrOut=34% ESC=1340 us
  700 ms without commands: armed=0 thrOut=0% ESC=1000 us
  t100 for 1 s without a new arm: armed=0 thrOut=0%
  arm while t100 is pending: armed=0 (refused)
  t0, arm, t100 for 1 s: armed=1 thrOut=20%
  partial line "dis" (no newline), then silence: longest loop() 10 ms, disarmed 589 ms after the last valid command
  re-armed, t100 for 1 s: thrOut=20%
  serial> #TRIP overcurrent
  17 A: armed=0 thrOut=0% ESC=1000 us
  arm after the trip, no new tNN: armed=1 thrOut=0%
  t100 for 1 s: thrOut=20%
  serial> #TRIP overcurrent
  reversed shunt, -17 A: armed=0 thrOut=0% ESC=1000 us
  re-armed, t100 for 1 s: thrOut=20%
  serial> #TRIP INA226 lost
  INA226 off the bus: armed=0 thrOut=0% ESC=1000 us
  serial> #TRIP INA226 lost
  arm + t100 with the INA226 still off: armed=0 thrOut=0%
```

The sign is extended correctly at the scale limits, the ramp holds 20 %/s, and all of this with a dead HX711: 500 ms of silence cuts the throttle and disarms the stand, and it starts again only after `t0`, `arm` and a fresh `tNN`; a line cut off without `\n` holds `loop()` for at most 10 ms and does not extend the timeout (with the default 1000 ms `Stream` timeout and a timeout refreshed by any line, the same test gave a 1000 ms freeze, the stand stayed armed and the throttle went to 0 only 1.8 s after the last valid command); 17 A, −17 A (a reversed shunt) and a lost INA226 all trip.

### Moving to real hardware
Hardware: an ESP32 DevKit, a 5 kg bar (a 2.2× margin over 2228 g; the rule (course guideline): the smallest standard bar capacity ≥ 2 × the maximum thrust, a margin for throttle jerks and vibration, and check the permissible overload in the bar's datasheet; a larger-capacity bar gives fewer counts per gram, 10 kg instead of 5 halves it to about 215 counts/g, so there is no point in a margin beyond 2×), an HX711 with RATE = 0, an INA226 with a 2 mΩ shunt in the negative lead, an optical sensor, an ESC with a PWM input, a 20 A fuse, a 24 V power supply with a current limit, or 6S. The tip of a 15" blade at 6177 RPM moves at π·0.381·103 ≈ 123 m/s: a broken prop piece is a bullet.

1. **Mechanics, no prop.** The stand on two clamps, airflow away from the bar and away from people, at least 1–2 prop diameters from walls, floor and ceiling (closer, recirculation changes the thrust). A ring or mesh around the disc. The plane of rotation is a no-go zone, and you work with safety glasses.
2. **Electrics, no prop.** The first power-up through a smoke stopper or a power supply limited to 2 A. Check that the INA226 shows the supply voltage within ±0.05 V of a multimeter, and that the current rises with throttle rather than falling (shunt polarity). Check the spin direction and the RPM at 20 % throttle with the optical sensor and with a tachometer.
3. **Calibration, no prop.** Warm up for 15 min. Load with weights 0–100–200–500–1000–2000 g along the prop axis (a pulley on a bearing), then unload. 20 samples per point. Compute k, the residuals and the hysteresis with the step 2 script. Leave 1000 g on for 10 min: that is the creep.
4. **Emergency paths, no prop.** Power the ESP32 from a separate 5 V (not only USB) and stop the PC script / pull the USB data cable: the throttle must go to 0 within 0.6 s and the stand must disarm. Temporarily set `I_LIMIT` = 1 A: you must get `#TRIP`. Disconnect the INA226 SDA wire while armed: you must get `#TRIP INA226 lost`. Pull the HX711 DOUT wire: safety must keep working.
5. **The run, prop fitted (only here).** Tighten the nut and confirm the direction. The PC script sends a command at ≥ 5 Hz (the firmware cuts the throttle 0.5–0.6 s after the last command). Zero for 20 s, then 7 steps of 10 s (50…100 %), and zero again for 20 s. Keep the emergency power switch of the ESC in your hand. At 100 % the example specimen draws 15.75 A, almost the 16 A limit (the datasheet peak is 16 A for 180 s), so hold the top step no longer than 10 s. Record the temperature and pressure and compute ρ.
6. **Processing** with the same script. Compare with the table at equal thrust.

Hardware criteria: calibration residual ≤ 3 g, zero drift ≤ 5 g and corrected, ≥ 5 throttle points, C_T constant within ±5 %, the g/W difference from the datasheet at equal thrust explained with U (k = 2).

Self-check: the lab is done when: (main path) the generator and the processing have been run, and k, the drift and the table of points match the ones shown; the uncertainty budget is computed for one point; from C_T and g/W you have concluded where the losses are, in the prop or in the drive; FM is computed from the datasheet torque with the correct formula; (hardware) items 1–6 are done, the emergency paths are checked without a prop, and the hardware criteria are met.

## diagnostics
- **Symptom:** rare huge thrust jumps (thousands of grams) or values near ±8388608
  - Possible cause: an interrupt (Wi-Fi, another ISR) stretched a PD_SCK pulse beyond 60 µs: the HX711 went into power-down or the bits shifted.
  - What to do: read in `portENTER_CRITICAL`, turn Wi-Fi off during the run, discard samples at the scale limits.
  - What the log shows: single outliers on a steady signal.
- **Symptom:** under a constant load the reading slowly rises, and the zero after the run does not match the zero before
  - Possible cause: bar creep and the temperature effect on zero (±0.2 % FS per 10 °C, up to ±10 g on a 5 kg bar).
  - What to do: a 15 min warm-up, a zero before and after, a linear correction in time, short steps.
- **Symptom:** the thrust is negative, or it rises when a weight is removed
  - Possible cause: A+ and A− swapped, or the bar is mounted upside down; at the motor, a prop mounted upside down or the wrong spin direction.
  - What to do: swap the signal wires or the sign of k, check the prop and the direction.
- **Symptom:** the thrust is 10–20 % above the datasheet with normal current
  - Possible cause: calibration at a different point of force application (a lever-arm error), or a pulley with friction ate part of the weight; the prop is close to the floor or a wall.
  - What to do: calibrate along the prop axis, check the hysteresis, move the stand 1–2 D away.
- **Symptom:** C_T matches the datasheet, but g/W is 5–15 % lower
  - Possible cause: losses in the drive: a different ESC and timing, thin or long wires, the voltage measured at the power supply instead of the ESC.
  - What to do: measure U at the ESC input, compare with the ESC from the table, check the wire gauges.
  - Consequences: the hover time will be shorter than the datasheet-based calculation in the same proportion.
- **Symptom:** the RPM is twice the expected value, or C_T jumps from point to point
  - Possible cause: the optical sensor sees two marks or reflections from the blades, a wrong `TACH_PPR`, or a wrong pole divider for eRPM.
  - What to do: one matte mark, a shield from light, a cross-check with an external tachometer.
- **Symptom:** the motor keeps spinning when the PC hangs or a sensor drops out
  - Possible cause: safety is tied to the sensor read loop, a blocking read (`readStringUntil` with the default 1 s timeout) stalls the loop, or there is no command timeout.
  - What to do: a safety check every 100 ms independent of the sensors, nothing blocking in the loop (`Serial.setTimeout(10)`), a 0.5 s timeout with a disarm, a hardware power switch for the ESC.
  - Consequences: an uncontrolled 15" prop means injury.

## checklist
- The stand is on clamps, the prop is behind a ring, ≥ 1–2 D to the walls
- The current limit and the timeout are checked without a prop
- Calibration along the prop axis, k and the residuals recorded
- A zero before and after the run, the drift corrected
- g/W is compared with the datasheet at equal thrust, with U (k = 2) given

## references
- T-Motor — MN4006 KV380 Antigravity: specifications and test data | https://store.tmotor.com/product/mn4006-kv380-motor-antigravity-type.html | primary | A
- Avia Semiconductor — HX711 24-bit ADC for weigh scales, datasheet | https://cdn.sparkfun.com/datasheets/Sensors/ForceFlex/hx711_english.pdf | primary | A
- Texas Instruments — INA226 current/power monitor, datasheet | https://www.ti.com/lit/ds/symlink/ina226.pdf | primary | A
- HTC Sensor — TAL220F miniature load cell, datasheet | https://cdn.shopify.com/s/files/1/0761/6561/1847/files/TAL220F.pdf | primary | A
- Brandt, Selig — Propeller Performance Data at Low Reynolds Numbers (AIAA 2011-1255) | https://m-selig.ae.illinois.edu/pubs/BrandtSelig-2011-AIAA-2011-1255-LRN-Propellers.pdf | primary | A
- Espressif — Arduino-ESP32 LEDC API | https://docs.espressif.com/projects/arduino-esp32/en/latest/api/ledc.html | primary | A
- bogde/HX711 — Arduino library for HX711 (alternative to manual reading) | https://github.com/bogde/HX711 | primary | B
