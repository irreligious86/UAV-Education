---
id: emb-protocols
title: "UART, I2C, SPI, CAN at the signal and driver level"
level: L3
readingTime: 40 min
firmware: any firmware
status: published
added: 2026-11-08
tags:
  - UART
  - I2C
  - SPI
  - CAN
  - driver
related:
  - emb-basics
  - el-measure
  - el-peripherals
next:
  - fw-reading
source: content/companion/emb-protocols.md
source_hash: bc732bff4a16
---

## summary
The “Connecting peripherals” module taught you to hook up ready-made parts; this one teaches you to build your own: what bits look like on the wire, why there is a start bit and an ACK, where framing errors and NACKs come from, how timings are calculated and why bus length is limited, and how to write a sensor driver from scratch (an I2C barometer/IMU on an ESP32: registers, block reads, error handling, timeouts). It ends with DroneCAN: CAN 2.0 frames, arbitration, node ID, why big aircraft need it and what a DroneCAN packet looks like in an analyzer.

## theory
### UART
Asynchronous: there is no clock line, both sides know the baud rate. Frame: a start bit (0), 5–9 data bits (LSB first), optional parity, 1–2 stop bits (1). 8N1 at 115200 → 10 bits per byte → 11,520 bytes/s. The receiver samples in the middle of the bit (usually ×16 oversampling); a baud-rate error of up to ~3–5% is tolerable, more than that gives a **framing error**. Errors: framing (stop bit is not 1 — wrong baud rate/inversion), overrun (the byte was not picked up in time — you need DMA/an interrupt), noise. Inversion (SBUS): levels are flipped, idle = 0. Levels are 3.3 V TTL; RS-232/RS-485 use other levels/a differential pair (long lines).

Driver: a receive ring buffer filled by an interrupt/DMA, a protocol frame parser (CRSF: `[address][length][type][payload][CRC8 0xD5]`; MAVLink: magic 0xFD, length, seq, sysid/compid, msgid, CRC16 with CRC_EXTRA), an inter-byte timeout for resynchronization.

### I2C
Synchronous, two open-drain lines with pull-ups: SCL, SDA. The master generates the clock; a transaction: START (SDA↓ while SCL=1) → 7-bit address + R/W bit → ACK from the slave (SDA↓ on the 9th clock) → data bytes with ACK/NACK → STOP. Register read: START, address+W, register number, **repeated START**, address+R, data, NACK on the last byte, STOP. Speeds 100/400 kHz (fast), 1 MHz (fast-plus). Limits: bus capacitance ≤ 400 pF → wires up to ~30–50 cm, pull-ups 2.2–4.7 kΩ (lower — steeper edges, more current). Errors: NACK on the address (no device/wrong address/no power), NACK on data, a **stuck bus** (the slave holds SDA=0 after a master glitch — cured by clocking SCL 9 times manually, “bus recovery”), clock stretching (the slave holds SCL low — the master must be able to wait; some MCUs/sensors have trouble with it).

{{diagram:i2c-transaction|Reading a register over I2C: address with the write bit, register address, repeated start, address with the read bit, data.}}

### SPI
Synchronous, full duplex: SCLK, MOSI, MISO, CS (one line per device). No addresses and no ACK: the master pulls CS low, outputs clocks, and every clock shifts a bit in both directions. CPOL/CPHA modes (0–3) — clock polarity/phase, must match the datasheet (ICM42688 — mode 0 or 3). Speeds up to tens of MHz (gyro 8–24 MHz, flash 50+). Register read: an address byte with the R bit (often the MSB = 1), then N garbage bytes on MOSI — the data comes back on MISO. A 14-byte IMU burst read in a single transaction — that is how every firmware does it. There are no “protocol” errors — integrity is checked only by meaning (the WHO_AM_I register, values within range). Short traces: SPI is almost never routed off the board.

### CAN and DroneCAN
CAN 2.0: a differential pair CAN_H/CAN_L, 120 Ω terminators at both ends, up to 1 Mbit/s (up to 40 m at 1 Mbit, longer — slower). Frame: an 11- or 29-bit (extended) identifier, DLC, up to 8 data bytes, CRC15, ACK from any receiver. **Arbitration**: everyone transmits at once, a dominant 0 beats a recessive 1 — the lower ID wins with no time lost; priority is built into the ID. The CAN controller in the MCU receives/sends frames in hardware and filters by ID; errors are counted (error passive/bus-off at 256 errors — the node disconnects itself).

**DroneCAN** (formerly UAVCAN v0): on top of CAN — a 29-bit ID with priority, message type and source node ID (1–127), multi-frame messages with a transfer CRC and a toggle bit, dynamic node ID allocation (DNA), standard types: `uavcan.equipment.gnss.Fix2`, `ahrs.MagneticFieldStrength2`, `esc.RawCommand/Status`, `power.BatteryInfo`, `range_sensor.Measurement`. Why on big aircraft: one twisted pair for all devices, the noise immunity of a differential pair and CRC, telemetry from every ESC, hot-swapping nodes, long lines (a 2 m wing), no more “one UART — one device”. Tool: DroneCAN GUI Tool (an SLCAN adapter or the flight controller as a bridge via `CAN_SLCAN_CPORT`) — you see the nodes, node parameters, messages.

### Driver: what it must have
1. Bus initialization and a device check (WHO_AM_I/chip id).
2. Configuration (registers): range, rate, filters.
3. Block reads with a timeout; return an error, never hang.
4. Conversion of raw units to physical ones (LSB → °/s, Pa).
5. Error handling: counters, re-initialization after N errors in a row, bus recovery for I2C.
6. Thread safety: a mutex on the bus if there are several devices.

## practice
### Step 1. An I2C sensor driver (ESP32, ESP-IDF; the example uses the legacy `driver/i2c.h` API, which is declared end-of-life as of ESP-IDF v6.0 — new projects use `driver/i2c_master.h`: `i2c_master_transmit_receive`/`i2c_master_transmit`)
Example for the BMP280 (address 0x76/0x77, chip id 0x58 in register 0xD0):
```c
static esp_err_t rd(uint8_t reg, uint8_t *buf, size_t n) {       // repeated-START read, 50 ms timeout
  return i2c_master_write_read_device(I2C_NUM_0, ADDR, &reg, 1, buf, n, pdMS_TO_TICKS(50));
}
static esp_err_t wr(uint8_t reg, uint8_t val) {
  uint8_t b[2] = { reg, val };
  return i2c_master_write_to_device(I2C_NUM_0, ADDR, b, 2, pdMS_TO_TICKS(50));
}
esp_err_t bmp280_init(void) {
  uint8_t id; ESP_RETURN_ON_ERROR(rd(0xD0, &id, 1), TAG, "no response");
  if (id != 0x58) return ESP_ERR_NOT_FOUND;
  ESP_RETURN_ON_ERROR(rd(0x88, calib, 24), TAG, "calib");         // dig_T1..dig_P9
  return wr(0xF4, 0x57);                                            // osrs_t x2, osrs_p x16, normal mode
}
esp_err_t bmp280_read(float *temp_c, float *press_pa) {
  uint8_t d[6]; esp_err_t e = rd(0xF7, d, 6); if (e != ESP_OK) { errors++; return e; }
  int32_t adc_p = (d[0] << 12) | (d[1] << 4) | (d[2] >> 4), adc_t = (d[3] << 12) | (d[4] << 4) | (d[5] >> 4);
  /* compensation formulas from the datasheet (bmp280_compensate_T/P) */ ...
  return ESP_OK;
}
```
Read at 50 Hz and print; after 5 errors in a row, re-initialize and log it.

### Step 2. Analyzer
Capture the transaction: START, address+W, 0xF7, repeated START, address+R, 6 bytes, NACK, STOP. Match the bytes with the printed output. Record the transaction duration at 400 kHz (expect ~0.2 ms).

### Step 3. Break the bus
Disconnect SDA on the fly → NACK/timeout, error counter, re-initialization; short SDA to ground for a second → stuck bus; implement recovery (9 SCL clocks in GPIO mode) and show it recovering.

### Step 4. DroneCAN (if you have a node)
DroneCAN GUI Tool through the flight controller's SLCAN bridge: see the node ID, `GetNodeInfo`, GPS/compass messages; capture a CAN frame with the analyzer and decode the 29-bit ID into priority/type/source.

### What you should get and what to record
- **Sensor read.** Register 0xD0 of the BMP280 returns chip id 0x58 — the first check that the driver is talking to the right device. If you get 0x60, it is a BME280 (it has humidity too). Pressure and temperature after compensation with the calibration coefficients are plausible: about 1000 hPa and room temperature. Raise the board by a meter — the pressure drops by about 0.12 hPa.
- **Transaction duration.** A 6-byte read with a repeated start at 400 kHz is about 85 bus clocks (addresses, register, data, ACKs) × 2.5 µs ≈ 0.21 ms. Compare with the analyzer: noticeably longer means the driver pauses between bytes or the line has weak pull-ups (slow edges).
- **Errors.** A disconnected SDA gives a NACK or a timeout, the error counter grows, after five in a row — re-initialization with a log entry. SDA held to ground hangs the bus. Nine SCL clocks in GPIO mode release the slave device and reading resumes. Record the time from the fault to recovery.
- **CAN.** The 29-bit ID of a DroneCAN frame is decoded into priority, message type and sender node number, and the number matches what DroneCAN GUI Tool shows.

The lab counts as done when the I²C sensor is read by your own driver with a chip id check, the bus is captured by the analyzer with the transaction duration, and a bus error is reproduced and handled with recovery.

## diagnostics
- **Symptom:** UART receives garbage
  - Possible cause: baud rate/inversion/no common ground; overrun without DMA.
  - What to do: check with an analyzer, DMA reception, framing/overrun counters.
- **Symptom:** an I2C transaction “hangs”
  - Possible cause: the slave holds SDA; clock stretching not supported.
  - What to do: timeouts in the driver, bus recovery, drop to 100 kHz.
- **Symptom:** SPI returns 0xFF/0x00
  - Possible cause: CS does not go low, CPOL/CPHA mode, too fast.
  - What to do: scope on CS/SCLK, mode per the datasheet, WHO_AM_I test.
- **Symptom:** a CAN node goes bus-off
  - Possible cause: no terminators, mismatched baud rates, H/L swapped.
  - What to do: 120 Ω at both ends, one baud rate, error counters.
- **Symptom:** the sensor works on the bench but not on the aircraft
  - Possible cause: interference on I2C from power wiring, wire length.
  - What to do: shorter/twisted/shielded wires, SPI or CAN instead of I2C.

## references
- NXP — I2C-bus specification and user manual (UM10204) | https://www.nxp.com/docs/en/user-guide/UM10204.pdf | primary | A
- DroneCAN — Specification | https://dronecan.github.io/Specification/1._Introduction | primary | A
- Bosch — BMP280 datasheet BST-BMP280-DS001 (registers, compensation) | https://bluerobotics.com/wp-content/uploads/2022/05/BMP280-DATASHEET.pdf | primary | A

## checklist
- I can draw a UART frame and an I2C transaction with ACK/NACK
- I know the SPI modes and why there is no ACK
- I understand CAN arbitration and the structure of a DroneCAN ID
- I wrote a driver with timeouts, error handling and recovery
- I captured a transaction with an analyzer and matched it to the code
