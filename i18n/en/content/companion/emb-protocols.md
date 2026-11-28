---
id: emb-protocols
title: "UART, I2C, SPI, CAN at the signal and driver level"
level: L3
readingTime: 40 min
firmware: any firmware (ArduPilot names checked against 4.7.3)
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
source_hash: 7febaa4c8265
---

## summary
The "Connecting Peripherals" module taught you to connect ready-made parts; this one teaches you to build your own: what bits look like on the wire, why there is a start bit and an ACK, where framing errors and NACKs come from, how timing is computed and bus length is limited, and how to write a sensor driver from scratch (an I2C barometer/IMU on an ESP32: registers, block reads, error handling, timeouts). It ends with DroneCAN: CAN 2.0 frames, arbitration, node IDs, why large vehicles need it, and what a DroneCAN packet looks like in an analyzer.

## theory
### UART
Asynchronous: there is no clock line; both sides know the baud rate. A frame: a start bit (0), 5–9 data bits (LSB first), an optional parity bit, 1–2 stop bits (1). 8N1 at 115200 → 10 bits per byte → 11 520 bytes/s. The receiver samples in the middle of each bit (usually with ×16 oversampling); a baud rate error up to ~3–5% is tolerated, beyond that you get a **framing error**. Errors: framing (the stop bit is not 1: wrong baud rate/inversion), overrun (a byte was not collected in time: you need DMA/interrupts), noise. Inversion (SBUS): the levels are flipped, idle = 0. Levels are 3.3 V TTL; RS-232/RS-485 use other levels/a differential pair (long lines).

The driver: a receive ring buffer fed by an interrupt/DMA, a protocol frame parser (CRSF: `[address][length][type][payload][CRC8 0xD5]`; MAVLink: magic 0xFD, length, seq, sysid/compid, msgid, CRC16 with CRC_EXTRA), and an inter-byte timeout for resynchronization.

### I2C
Synchronous, two open-drain lines with pull-ups: SCL and SDA. The master generates the clock; a transaction: START (SDA↓ while SCL=1) → a 7-bit address + the R/W bit → an ACK from the target (SDA↓ on the 9th clock) → data bytes with ACK/NACK → STOP. Reading a register: START, address+W, the register number, a **repeated START**, address+R, the data, NACK on the last byte, STOP. Speeds: 100/400 kHz (Fast-mode), 1 MHz (Fast-mode Plus). Limits: bus capacitance ≤ 400 pF (up to Fast-mode; 550 pF in Fast-mode Plus) → wires up to ~30–50 cm, pull-ups of 2.2–4.7 kΩ (lower values give sharper edges and more current). Errors: NACK on the address (no device/wrong address/no power), NACK on data, a **stuck bus** (the target holds SDA=0 after a master glitch; fixed by clocking SCL 9 times by hand, "bus recovery"), clock stretching (the target holds SCL low, and the master must be able to wait; some MCUs/sensors have trouble with this).

{{diagram:i2c-transaction|Reading a register over I2C: the address with the write bit, the register address, a repeated start, the address with the read bit, the data.}}

### SPI
Synchronous, full duplex: SCLK, MOSI, MISO, CS (one line per device). No addresses and no ACK: the master pulls CS low and clocks, and every clock shifts one bit in each direction. The CPOL/CPHA modes (0–3) set the clock polarity/phase and must match the datasheet (ICM42688: mode 0 or 3). Speeds up to tens of MHz (a gyro at 8–24 MHz, flash at 50+). Reading a register: an address byte with the R bit (often the top bit = 1), then N dummy bytes on MOSI while the data comes back on MISO. A burst read of 14 IMU bytes in one transaction is what every firmware does. There are no "protocol" errors: integrity can only be checked by meaning (the WHO_AM_I register, values within range). Keep traces short: SPI is rarely routed off the board.

What a 14-byte IMU block costs. SPI: an address byte + 14 bytes at 8 clocks each = 120 clocks: 15 µs at 8 MHz, 5 µs at 24 MHz. I2C: address+W, register, address+R, and 14 bytes at 9 clocks each (8 bits + ACK), plus START, repeated START, and STOP ≈ 156 clocks: 390 µs at 400 kHz, 156 µs at 1 MHz, 1.56 ms at 100 kHz. UART 8N1: 10 bits per byte: 1.2 ms at 115200, 152 µs at 921600. The whole 8 kHz loop is 125 µs (`emb-basics`), which is why an 8 kHz gyro is connected only over SPI, while I2C is left to the barometer and the compass with their tens of hertz.

{{diagram:chart-bus-imu-read-time|A 14-byte IMU block: SPI fits in 5–15 µs, while I2C even at 1 MHz (156 µs) and a UART at 921600 (152 µs) take longer than the whole 8 kHz loop.}}

### CAN and DroneCAN
CAN 2.0: a differential pair, CAN_H/CAN_L, 120 Ω terminators at both ends, up to 1 Mbit/s (up to 40 m at 1 Mbit/s; longer runs need lower rates). A frame: an 11-bit or 29-bit (extended) identifier, the DLC, up to 8 data bytes, CRC15, and an ACK from any receiver. **Arbitration**: everyone transmits at once, a dominant 0 beats a recessive 1, and the lower ID wins with no time lost; the priority is built into the ID. The CAN controller in the MCU receives/sends frames in hardware and filters by ID; errors are counted (error passive once an error counter reaches 128, bus-off once the transmit error counter reaches 256: the node disconnects itself).

**DroneCAN** (formerly UAVCAN v0): on top of CAN, a 29-bit ID with the priority, the message type, and the source node ID (1–127), multi-frame messages with a transfer CRC and a toggle bit, dynamic node ID allocation (DNA), and standard types: `uavcan.equipment.gnss.Fix2`, `ahrs.MagneticFieldStrength2`, `esc.RawCommand/Status`, `power.BatteryInfo`, `range_sensor.Measurement`. Why large vehicles use it: one twisted pair for every device, the noise immunity of a differential pair and the CRC, telemetry from every ESC, hot-swappable nodes, long runs (a 2 m wing), and no more "one UART, one device". The tool: DroneCAN GUI Tool (with an SLCAN adapter, or the flight controller as a bridge with `CAN_SLCAN_CPORT`) shows the nodes, node parameters, and messages.

### A driver: what it must have
1. Bus initialization and a device check (WHO_AM_I/chip id).
2. Configuration (registers): range, rate, filters.
3. Block reads with a timeout; return an error, never hang.
4. Conversion of raw units to physical ones (LSB → °/s, Pa).
5. Error handling: counters, reinitialization after N errors in a row, bus recovery for I2C.
6. Thread safety: a mutex on the bus if there are several devices.

### Where it fits in the system

- **Takes in:** levels, pull-ups, and bus wiring (`el-peripherals`); interrupts and DMA for lossless reception (`emb-basics`); a scope trace and logic analyzer decode (`el-measure`).
- **Puts out:** a driver that returns physical units or an error: measurements to a MAVLink component (`mav-component`), frames to the CRSF and MAVLink parsers (`mav-protocol`), nodes to the DroneCAN bus (`el-dronecan`).
- **If you get this wrong:** an I2C read without a timeout → a stuck bus hangs the task, and the loop with it; then jitter or the watchdog (`emb-basics`). CAN without terminators → errors pile up, the node goes bus-off, and the GPS or ESCs drop off the bus (`el-dronecan`).

## practice
### Step 1. An I2C sensor driver (ESP32, ESP-IDF; the example uses the legacy `driver/i2c.h` API, which is end-of-life as of ESP-IDF v6.0; new projects use `driver/i2c_master.h`: `i2c_master_transmit_receive`/`i2c_master_transmit`)
An example for the BMP280 (address 0x76/0x77, chip id 0x58 in register 0xD0; since ESP-IDF v6.0 driver headers no longer include FreeRTOS, so `pdMS_TO_TICKS` needs `#include "freertos/FreeRTOS.h"`):
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
Read at 50 Hz and print; after 5 errors in a row, reinitialize and log it.

### Step 2. The analyzer
Capture the transaction: START, address+W, 0xF7, repeated START, address+R, 6 bytes, NACK, STOP. Match the bytes with the output. Write down the transaction duration at 400 kHz (expect ~0.2 ms).

### Step 3. Break the bus
Disconnect SDA while running → NACK/timeout, the error counter, reinitialization; short SDA to ground for a second → a stuck bus; implement recovery (9 SCL clocks in GPIO mode) and show the bus coming back.

### Step 4. DroneCAN (if you have a node)
DroneCAN GUI Tool through the flight controller's SLCAN bridge: see the node ID, `GetNodeInfo`, the GPS/compass messages; capture a CAN frame with an analyzer and split the 29-bit ID into priority/type/source.

### What you should see and what to write down
- **Reading the sensor.** BMP280 register 0xD0 returns chip id 0x58, the first check that the driver is talking to the right device. If you get 0x60, it is a BME280 (which also measures humidity). Pressure and temperature after compensation with the calibration coefficients look plausible: about 1000 hPa and room temperature. Raise the board by a meter, and the pressure drops by about 0.12 hPa.
- **Transaction duration.** Reading 6 bytes with a repeated start at 400 kHz is about 85 bus clocks (addresses, register, data, ACKs) × 2.5 µs ≈ 0.21 ms. Compare with the analyzer: if it is noticeably longer, the driver pauses between bytes or the pull-ups are weak (slow edges).
- **Errors.** A disconnected SDA gives a NACK or a timeout, the error counter grows, and after five in a row the driver reinitializes and logs it. SDA held to ground hangs the bus. Nine SCL clocks in GPIO mode release the target, and reading resumes. Write down the time from the fault to recovery.
- **CAN.** The 29-bit ID of a DroneCAN frame is split into the priority, the message type, and the sender node number, and the number matches what DroneCAN GUI Tool shows.

Self-check: the lab is done when your own driver reads the I²C sensor with a chip id check (0x58 for the BMP280; 0x60 means a BME280) and gives about 1000 hPa and room temperature, the bus is captured with an analyzer and the transaction duration is compared with the ≈ 0.21 ms estimate (noticeably longer means pauses between bytes in the driver or weak pull-ups), and a bus fault is reproduced and handled: the error counter grows, five in a row trigger a reinitialization with a log entry, nine SCL clocks release the bus, reading resumes, and the time from the fault to recovery is recorded.

## diagnostics
- **Symptom:** the UART receives garbage
  - Possible cause: baud rate/inversion/no common ground; overrun without DMA.
  - What to do: check with an analyzer, DMA reception, framing/overrun counters.
- **Symptom:** an I2C transaction "hangs"
  - Possible cause: the target holds SDA; clock stretching not supported.
  - What to do: timeouts in the driver, bus recovery, drop to 100 kHz.
- **Symptom:** SPI returns 0xFF/0x00
  - Possible cause: CS does not go low, the CPOL/CPHA mode, too fast.
  - What to do: a scope on CS/SCLK, the mode from the datasheet, a WHO_AM_I test.
- **Symptom:** a CAN node goes bus-off
  - Possible cause: no terminators, mismatched bit rates, H/L swapped.
  - What to do: 120 Ω at both ends, one bit rate, error counters.
- **Symptom:** the sensor works on the bench but not on board
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
- I wrote a driver with timeouts, error handling, and recovery
- I captured a transaction with an analyzer and matched it with the code
