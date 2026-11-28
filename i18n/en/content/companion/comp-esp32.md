---
id: comp-esp32
title: "ESP32 and peripherals"
level: L2
readingTime: 30 min
firmware: ESP32 / EdgeTX
status: published
added: 2026-11-07
tags:
  - ESP32
  - EdgeTX
  - UART
related:
  - comp-mavlink
  - link-protocols
next:
  - comp-raspberry
source: content/companion/comp-esp32.md
source_hash: bea4214de241
---

## summary
The ESP32 is an ideal "small companion": UART, Wi-Fi, BLE, a display, a price of pocket change and a boot time of a fraction of a second. The module covers three typical roles: onboard peripheral (sensors, indication), a Wi-Fi ↔ FC MAVLink bridge, and a radio companion. The last one is shown on a project for the RadioMaster TX16S: an ESP32-S3 with a screen that shows telemetry in flight and brings up an access point on the ground for configuration from a phone. The pitfalls covered: the EdgeTX Lua widget lifecycle, UART levels, the power budget and a verifiable radio shutdown.

## theory
### Three roles for an ESP32
1. **Onboard peripheral.** Polling I2C sensors, addressable LEDs, servos, relays. The link to the FC is a UART carrying MAVLink or a simple text protocol.
2. **MAVLink bridge.** The ESP32 receives MAVLink from the FC over UART and serves it over Wi-Fi (UDP) to a phone or laptop. Many off-the-shelf Wi-Fi telemetry modules work this way; your own version is a few dozen lines.
3. **Radio companion.** The ESP32 is connected to the AUX port of an EdgeTX radio; a Lua script on the radio sends it the state (mode, arm, telemetry), and the ESP32 shows it on its own display and provides a configuration interface.

### UART: levels and wiring
The ESP32 runs at 3.3 V. Flight controllers and EdgeTX radios also use 3.3 V on their UARTs, but check with a multimeter before you connect them. TX goes to RX and RX to TX, and a common GND is mandatory. The baud rate to the radio is whatever is set in the port settings, usually 115200.

### EdgeTX: the AUX port and Lua
In the radio's Hardware settings, the AUX1/AUX2 ports have a "Lua" mode: scripts then get access to `serialWrite(str)`, `serialRead([num])` and `setSerialBaudrate(baudrate)`. Without an argument, `serialRead` reads up to and including the first newline, so a line-based protocol ("one line, one message") maps onto it naturally.

### Pitfall: the widget lifecycle
An EdgeTX widget has two functions: `refresh()` is called while the widget is visible on screen, `background()` while it is hidden. If you put the heartbeat only in `refresh()`, the companion loses the link as soon as the pilot switches screens. The fix: a shared `tick()` function that both of them call.

### Safe by default
A design decision of the project: an undefined state = FLIGHT mode with Wi-Fi off. The access point comes up only after the ESP32 has received an explicit "disarmed" from the radio. Every settings write goes in two steps: STAGE (prepare) → APPLY (apply with an automatic backup), and the in-flight write protection is duplicated on both sides, in the Lua script and in the ESP32 firmware.

Turning the radio off must be verifiable: `WiFi.mode(WIFI_OFF)` plus `esp_wifi_stop()`, not the assumption "we never turned it on".

### Power
An ESP32-S3 with Wi-Fi active draws peaks of hundreds of milliamps. From the radio battery or a BEC that is noticeable; in FLIGHT mode with the radio off it is several times less. You budget power per mode, not by the average.

### A minimal MAVLink bridge on an ESP32 (the code idea)
UART2 (`Serial2.begin(921600, SERIAL_8N1, RX_PIN, TX_PIN)`) ↔ WiFi UDP: everything that arrives from the FC goes out over UDP to the address of the last client (or broadcast 14550); everything that arrives over UDP goes to the UART. 1 KB buffers, no MAVLink parsing (the bridge is transparent); a task on the second FreeRTOS core (the "Embedded" module): core 0 runs the Wi-Fi stack, core 1 the UART copying at a priority above `loop()`. The latency of such a bridge is a few ms; packets get lost when Wi-Fi is congested (2.4 GHz shares the air with ELRS 2.4, so on board a Wi-Fi bridge belongs to ground configuration only and is switched off in flight).

### An onboard sensor over MAVLink
The ESP32 as a system component: it sends `HEARTBEAT` (with its own component_id: `MAV_COMP_ID_PERIPHERAL` (158) or one from the USER1–USER75 range (25–99)), data as `NAMED_VALUE_FLOAT` (visible in the GCS and, in ArduPilot, in the `NVAL` log; `NAMED_VALUE_INT` is shown by the GCS but ArduPilot does not log it), or `DISTANCE_SENSOR` (132) for your own rangefinder, which ArduPilot accepts as `RNGFND1_TYPE = 10` (MAVLink) and uses in the EKF and for landing. Library: the `mavlink` C headers from the generator (`common.xml`; header-only, so only the messages you call end up in flash: a few KB for HEARTBEAT, a couple of data messages and the parser), or a minimal hand-written frame builder with CRC (the "MAVLink protocols" module).

### Worked example: the radio companion (the TX16S project)
Line protocol: radio → ESP32 `S,<mode>,<armed>,<vbat>,<rssi>\n` every 500 ms; ESP32 → radio `A,<cmd>,<arg>\n`. ESP32 states: FLIGHT (radio off; the default, and also on a line timeout > 2 s) → GROUND (the radio has sent `armed=0` for ≥ 3 s in a row: Wi-Fi AP, web settings) → FLIGHT on any `armed=1`. Settings: STAGE (JSON in RAM) → APPLY (an NVS write keeping a copy of the previous version), only in GROUND; the Lua script on the radio blocks `APPLY` if telemetry shows the vehicle armed. Testing: a line emulator on a PC over a USB-UART, scenarios for transitions and timeouts, then the real radio without a vehicle.

{{diagram:esp32-tx-companion-states|Radio companion states: by default and after more than 2 s of silence, FLIGHT with the radio off; GROUND and the settings only after 3 s of armed=0 in a row.}}

{{diagram:esp32-roles|The three ESP32 roles in the course: a UART ↔ Wi-Fi/BLE bridge, a MAVLink component of its own, and a radio companion on the AUX port.}}

### The ESP32 as a flight controller: what exists and what to expect
Whether an ESP32 can replace a flight controller is not decided by the board's price but by whether your chip is in the target list of **the firmware version you actually fly**. Status as of November 22, 2026, checked against the source of the course's target versions:

| Firmware | ESP32 in the target version | What it means |
|---|---|---|
| ArduPilot 4.7.3 | the `AP_HAL_ESP32` HAL exists, 10 board definitions (`esp32buzz`, `esp32s3devkit`, `esp32s3m5stampfly` and others) | build from source on Linux only; the port README lists DShot, GPIO and ESC telemetry under "not done yet"; StampFly has `SCHED_LOOP_RATE 150` with the comment "flash won't go faster", against Copter's default of 400 Hz, brushed motors, logging over MAVLink |
| Betaflight 2025.12.5 | no: platforms STM32, AT32, APM32, PICO | 2026.6 (outside the course's target version) added the `src/platform/ESP32` platform with the targets ESP32S3 and ESP32WROOM (plus the skeleton targets ESP32C5, ESP32P4; source at tag 2026.6.2): DShot is there (`dshot_esp32.c`), bidirectional DShot and bit-bang are disabled (`#undef USE_DSHOT_TELEMETRY`, `USE_DSHOT_BITBANG` in `target.h`), blackbox defaults to a UART; per the release notes the status is **experimental** |
| INAV 9.1.0 | no targets at all | — |
| PX4 1.18.0 | `boards/espressif/esp32`, version 0.1 | the build config has neither EKF2 nor the attitude controllers: it is a starting point, not a flight controller |
| ESP-FC (a separate project, MIT, latest tag v0.2.1; lists from the master branch README) | ESP32 and ESP32-S3 recommended, S2, C3, RP2040, RP2350 experimental | compatible with Betaflight Configurator; up to a 4 kHz loop with an SPI gyro; ACRO, ANGLE, AIRMODE, Quad X only; no altitude hold and no GPS; the author states that this is not Betaflight and that some Configurator tabs do not work |
| ExpressLRS 4.1.0 | receivers on ESP32, ESP32-C3, ESP32-S3 | receiver outputs provide 50–400 Hz PWM and DShot300 straight to ESCs and servos, but without stabilization: for a simple plane, not for a copter |

Why the ESP32 hits a ceiling: code executes from external SPI flash through a cache, hence the 150 Hz in ArduPilot on the StampFly. The Wi-Fi radio on the same die shares 2.4 GHz with ELRS (see the bridge section above). Most STM32 FCs run from on-chip flash (H750/H730 "ExST" boards also execute from external QSPI flash), and STM32 has DShot in all four of the course's firmwares.

**Selection rule.**

1. The goal is to understand controller code, an indoor brushed whoop, a test bench → an ESP32 is fine: ESP-FC, or ArduPilot on the StampFly.
2. GPS navigation, more than 250 g, flight beyond visual line of sight, a payload → STM32: F405 for Betaflight and INAV, H7 for ArduPilot and PX4 (`ap-intro`, the "Which board to buy" section).
3. Check: open the target list in the source of your version (`src/platform` in Betaflight, `libraries/AP_HAL_*/hwdef` in ArduPilot) and find your board there. If it is not there, the board is not part of the release, and it is not suitable for the tasks in item 2. On ArduPilot, compare the actual main loop rate `PM.LR` in the log with `SCHED_LOOP_RATE` and look at `PM.NLon` (the number of long loops): if `LR` is noticeably below the configured rate and `NLon` keeps growing, the processor cannot keep up.

### Where it fits

- **Takes in:** MAVLink from the FC over a 3.3 V UART (`comp-mavlink`); state lines (mode, arm, battery, RSSI) from the radio's Lua script over the AUX port; power from a BEC or the radio battery.
- **Hands off:** the same stream over Wi-Fi UDP to a phone or laptop; `DISTANCE_SENSOR` and `NAMED_VALUE_FLOAT` as a system component (`mav-component`); telemetry on its own display.
- **If you get this wrong:** a Wi-Fi bridge left on in flight → it shares 2.4 GHz with ELRS and the control link suffers; LQ and RSSI are covered in `link-elrs`. The heartbeat only in the widget's `refresh()` → the pilot switched screens, the companion lost the radio and fell back to FLIGHT on the timeout: the settings are unavailable even though the vehicle is on the ground.

## practice
### Step 1. Echo between the radio and the ESP32
1. On the radio: Hardware → AUX1 → Lua mode, 115200.
2. The script `/SCRIPTS/TOOLS/echo.lua` on the radio sends a line and prints the reply.
3. On the PC, instead of the ESP32: a USB-UART and a terminal (`picocom -b 115200 /dev/ttyUSB0`). Pass criterion: a line of 200+ characters makes the round trip without loss.
4. Only after that, the ESP32.

### Step 2. ESP32 firmware skeleton (PlatformIO, Arduino)
```cpp
#include <Arduino.h>
#include <WiFi.h>
#include <esp_wifi.h>

enum class Mode { FLIGHT, GROUND };
Mode mode = Mode::FLIGHT;            // undefined state == FLIGHT
unsigned long lastLine = 0;          // last valid S-line from the radio
unsigned long disarmedSince = 0;     // 0 = not continuously disarmed
const unsigned long LINE_TIMEOUT_MS = 2000;
const unsigned long GROUND_AFTER_MS = 3000;

void radioOff() {
  WiFi.mode(WIFI_OFF);
  esp_wifi_stop();                   // verifiable off, not assumed off
}

void enterGround() {
  WiFi.mode(WIFI_AP);
  WiFi.softAP("tx16s-companion", "change-me");
  mode = Mode::GROUND;
}

void enterFlight() {
  radioOff();
  mode = Mode::FLIGHT;
}

void setup() {
  Serial.begin(115200);              // USB debug
  Serial1.begin(115200, SERIAL_8N1, 18, 17);  // RX, TX pins to the radio AUX port
  radioOff();
}

void loop() {
  unsigned long now = millis();
  if (Serial1.available()) {
    String line = Serial1.readStringUntil('\n');   // one line == one message
    // S,<mode>,<armed>,<vbat>,<rssi>  — the protocol above; armed is the third field
    if (line.startsWith("S,")) {
      int a = line.indexOf(',', 2);                 // end of <mode>
      if (a > 0 && a + 1 < (int)line.length()) {
        lastLine = now;
        bool armed = line.charAt(a + 1) == '1';
        if (armed) {
          disarmedSince = 0;
          if (mode == Mode::GROUND) enterFlight();  // any armed=1 -> FLIGHT at once
        } else {
          if (disarmedSince == 0) disarmedSince = now;
          if (mode == Mode::FLIGHT && now - disarmedSince >= GROUND_AFTER_MS) enterGround();
        }
      }
    }
  }
  if (now - lastLine > LINE_TIMEOUT_MS) {
    disarmedSince = 0;                // a gap breaks "continuously disarmed"
    if (mode == Mode::GROUND) enterFlight();   // lost the radio: fail safe
  }
}
```

### Step 3. An EdgeTX widget with a shared tick()
```lua
-- companion.lua (widget): send the S-line every 500 ms whether visible or not
-- protocol: S,<mode>,<armed>,<vbat>,<rssi>\n  (see docs/protocol.md)
local lastSend = 0

local function tick()
  local now = getTime()                       -- 10 ms units
  if now - lastSend >= 50 then
    local _, fmName = getFlightMode()
    local armed = getValue("sa") > 0          -- example: arm switch on SA
    local vbat = getValue("RxBt") or 0        -- CRSF telemetry; 0 when the sensor is missing
    local rssi = getValue("1RSS") or 0
    serialWrite(string.format("S,%s,%d,%.2f,%d\n", fmName or "?", armed and 1 or 0, vbat, rssi))
    lastSend = now
  end
end

local function create(zone, options) return { zone = zone } end
local function update(widget, options) end
local function background(widget) tick() end
local function refresh(widget, event, touch)
  tick()
  lcd.drawText(widget.zone.x, widget.zone.y, "companion link", SMLSIZE)
end

return { name = "Companion", create = create, update = update, refresh = refresh, background = background }
```

The source of truth for "arm" is the switch plus the heartbeat, not the state from CRSF telemetry: that may be missing or late.

### Step 4. Repository layout
`firmware/` (PlatformIO), `lua/` (radio scripts), `web/` (the settings page, served by the ESP32), `docs/` (the message protocol). The protocol is a separate document: every line, its fields, and who is allowed to send it.

### What you should end up with and what to record
- **Echo test.** 200+ characters go out and come back without loss or corruption. If they get lost, the culprit is almost always the baud rate or the ground. Get a clean echo with the USB-UART first and only then connect the ESP32; otherwise you cannot tell whose fault it is.
- **The S-line stream.** In the ESP32 debug output (the USB port, `Serial`), `S,…` lines arrive every 500 ms ± 50 ms, and whether the widget is visible on the radio screen makes no difference: `tick()` is called from both `refresh()` and `background()`.
- **Transitions.** Record the time of each transition from `millis()` debug timestamps. Disarm: after 3 s, GROUND and the Wi-Fi access point. Arm: FLIGHT at once, Wi-Fi off. The cable from the radio pulled out in GROUND: FLIGHT after 2 s. A garbage line does not change the state.
- **Testing on a PC without the radio.** The same scenarios are checked with an emulator: a PC script sends S-lines to the USB-UART at the right pace and with dropouts. That is faster and more repeatable than flipping a switch.

### docs/protocol.md
Every protocol line gets its own section: the format (`S,<mode>,<armed>,<vbat>,<rssi>`), fields and units, who sends it and how often, what the receiver does on a format error and when lines stop arriving. A protocol that is not in the document turns into "whatever the code does" and breaks at the first edit.

Self-check: the lab is done when the USB-UART echo test passes with 200+ characters, the widget sends S-lines from `refresh()` and `background()`, the ESP32 drops to FLIGHT on the line timeout, and the `millis()` timestamps match the specified timings (S-lines every 500 ms ± 50 ms; disarm → GROUND after 3 s; cable pulled → FLIGHT after 2 s; a garbage line does not change the state), and `docs/protocol.md` records for every protocol line the format, the fields with units, who sends it and how often, and how the receiver reacts to a format error and to missing lines.

## diagnostics
- **Symptom:** the companion loses the link when the radio screen changes
  - Possible cause: sending only from `refresh()`.
  - What to do: a shared `tick()` in `refresh()` and `background()`.
- **Symptom:** lines arrive truncated
  - Possible cause: `serialRead` is called less often than data arrives, and the buffer overflows.
  - What to do: read on every `tick()`, shorten the messages, lower the rate.
- **Symptom:** the access point came up in flight
  - Possible cause: the protection exists on one side only.
  - What to do: check the arm state in both the Lua script and the firmware; a heartbeat timeout → FLIGHT.
- **Symptom:** the ESP32 reboots when Wi-Fi turns on
  - Possible cause: a supply voltage dip (peaks of 300–500 mA).
  - What to do: a 470 µF capacitor on 3.3 V, a BEC/LDO with headroom, and do not power it from a radio pin without checking the current.
- **Symptom:** the Lua script on the radio does not see the ESP32's replies
  - Possible cause: the AUX port is not in Lua mode, the baud rate, TX/RX.
  - What to do: Hardware → AUX = Lua, `setSerialBaudrate`, a logic analyzer on the line.

## references
- EdgeTX Lua API Reference | https://luadoc.edgetx.org/ | primary | A
- EdgeTX Lua serial API source (api_general.cpp, GitHub) | https://github.com/EdgeTX/edgetx/blob/main/radio/src/lua/api_general.cpp | primary | A
- ESP32 Arduino core — Wi-Fi API (GitHub) | https://github.com/espressif/arduino-esp32 | primary | A
- PlatformIO — Documentation | https://docs.platformio.org/ | primary | A
- ArduPilot Copter-4.7.3 — AP_HAL_ESP32 README and hwdef esp32s3m5stampfly | https://github.com/ArduPilot/ardupilot/tree/Copter-4.7.3/libraries/AP_HAL_ESP32 | primary | A
- Betaflight 2026.6 Release Notes (ESP32 experimental; accessed 2026-11-22) | https://betaflight.com/docs/wiki/release/Betaflight-2026-6-Release-Notes | primary | A
- PX4 v1.18.0 — boards/espressif/esp32 | https://github.com/PX4/PX4-Autopilot/tree/v1.18.0/boards/espressif/esp32 | primary | A
- ExpressLRS 4.1.0 — src/targets and include/common.h (PWM/DShot output modes) | https://github.com/ExpressLRS/ExpressLRS/blob/4.1.0/src/include/common.h | primary | A
- ESP-FC — README (MCUs, features, limitations; accessed 2026-11-22) | https://github.com/rtlopez/esp-fc | primary | B

## checklist
- UART levels checked with a multimeter, common GND
- The USB-UART echo test passed with 200+ characters
- The heartbeat is sent from `refresh()` and `background()`
- Undefined state = FLIGHT, Wi-Fi verifiably off
- In-flight write protection on both sides
- Power budget calculated per mode
