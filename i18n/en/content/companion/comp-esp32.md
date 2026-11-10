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
source_hash: 0985c735e3ff
---

## summary
The ESP32 is the perfect “little companion”: UART, Wi-Fi, BLE, a display, a dirt-cheap price and boot in a fraction of a second. This module covers three typical roles: onboard peripherals (sensors, indication), a Wi-Fi ↔ FC MAVLink bridge, and a radio companion. The last one is shown on a project for the RadioMaster TX16S: an ESP32-S3 with a screen that shows telemetry in flight and brings up an access point for setup from a phone on the ground. The traps covered: the EdgeTX Lua widget lifecycle, UART levels, the power budget and a verifiable radio shutdown.

## theory
### Three roles of the ESP32
1. **Onboard peripherals.** Polling sensors over I2C, addressable LEDs, servos, relays. The link to the FC goes over UART via MAVLink or a simple text protocol.
2. **MAVLink bridge.** The ESP32 receives MAVLink over UART from the FC and serves it over Wi-Fi (UDP) to a phone or laptop. Many off-the-shelf Wi-Fi telemetry modules work this way; your own version is a few dozen lines.
3. **Radio companion.** The ESP32 is connected to the AUX port of an EdgeTX radio, a Lua script on the radio sends it the state (mode, arm, telemetry), and the ESP32 shows it on its own display and provides a settings interface.

### UART: levels and wires
The ESP32 runs at 3.3 V. Flight controllers and EdgeTX radios are also 3.3 V on UART, but check with a multimeter before connecting. The wires are crossed over, and a common GND is mandatory. The baud rate with the radio is whatever is set in the port settings, usually 115200.

### EdgeTX: the AUX port and Lua
In the radio settings (Hardware), the AUX1/AUX2 ports have a “Lua” mode: scripts then get access to the functions `serialWrite(str)`, `serialRead([num])` and `setSerialBaudrate(baudrate)`. `serialRead` with no argument reads up to the first newline, so a “one line = one message” string protocol fits it naturally.

### Trap: the widget lifecycle
An EdgeTX widget has two functions: `refresh()` is called when the widget is visible on the screen, `background()` when it is hidden. If you put the heartbeat send only in `refresh()`, the companion loses the link as soon as the pilot switches screens. The fix: a shared `tick()` function that both of them call.

### Safe by default
A design decision of the project: undefined state = FLIGHT mode, Wi-Fi off. The access point comes up only when the ESP32 has received an explicit “disarmed” from the radio. Every settings write goes through two steps: STAGE (prepare) → APPLY (apply with an automatic backup), and the in-flight write protection is duplicated on both sides — in Lua and in the ESP32 firmware.

Turning the radio off must be verifiable: `WiFi.mode(WIFI_OFF)` plus `esp_wifi_stop()`, not the assumption “we never turned it on”.

### Power
An ESP32-S3 with active Wi-Fi draws peaks of hundreds of milliamps. From the radio battery or a BEC that is noticeable; in FLIGHT mode with the radio off it is several times less. The budget is calculated per mode, not from the average.

### A minimal MAVLink bridge on the ESP32 (the code idea)
UART2 (`Serial2.begin(921600, SERIAL_8N1, RX_PIN, TX_PIN)`) ↔ WiFi UDP: everything that comes from the FC goes to UDP at the last client's address (or broadcast 14550); everything that comes over UDP goes to UART. 1 KB buffers, no MAVLink parsing (the bridge is transparent); a task on the second FreeRTOS core (the “Embedded” module): core 0 is the Wi-Fi stack, core 1 is the UART copying with a priority above `loop()`. The latency of such a bridge is a few ms; losses happen when Wi-Fi is overloaded (2.4 GHz shares the air with ELRS 2.4 — onboard, a Wi-Fi bridge only makes sense for setup on the ground; turn it off in flight).

### An onboard sensor over MAVLink
The ESP32 as a system component: it sends `HEARTBEAT` (its own component_id: `MAV_COMP_ID_PERIPHERAL` (158) or one from the USER1–USER75 range (25–99)), data as `NAMED_VALUE_FLOAT`/`NAMED_VALUE_INT` (visible in the GCS and in the `NVAL` log), or `DISTANCE_SENSOR` (132) for your own rangefinder — ArduPilot accepts it as `RNGFND1_TYPE = 10` (MAVLink) and uses it in the EKF/landing. Library: the `mavlink` C headers from the generator (`common.xml`, 100 KB of flash), or a minimal hand-written frame builder with CRC (the “MAVLink protocols” module).

### Worked example: a radio companion (the TX16S project)
The line protocol: radio → ESP32 `S,<mode>,<armed>,<vbat>,<rssi>\n` every 500 ms; ESP32 → radio `A,<cmd>,<arg>\n`. ESP32 states: FLIGHT (radio off; the default and on a line timeout > 2 s) → GROUND (the radio sent `armed=0` for ≥ 3 s in a row: Wi-Fi AP, web settings) → FLIGHT on any `armed=1`. Settings: STAGE (JSON in RAM) → APPLY (NVS write with a copy of the previous version) only in GROUND; the Lua on the radio blocks `APPLY` if telemetry shows armed. Testing: a line emulator from a PC over USB-UART, transition and timeout scenarios, then the real radio without an aircraft.

{{diagram:esp32-roles|Three roles of the ESP32 in the course: a UART ↔ Wi-Fi/BLE bridge, its own MAVLink component and a radio companion on the AUX port.}}

## practice
### Step 1. Echo between the radio and the ESP32
1. On the radio: Hardware → AUX1 → Lua mode, 115200.
2. The script `/SCRIPTS/TOOLS/echo.lua` on the radio sends a line and prints the reply.
3. On the PC, instead of the ESP32 — a USB-UART and a terminal (`picocom -b 115200 /dev/ttyUSB0`). Criterion: a line of 200+ characters goes back and forth without losses.
4. Only after that — the ESP32.

### Step 2. The ESP32 firmware skeleton (PlatformIO, Arduino)
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

The source of truth for “arm” is the switch plus the heartbeat, not the state from CRSF telemetry: it can be missing or lag behind.

### Step 4. Repository structure
`firmware/` (PlatformIO), `lua/` (radio scripts), `web/` (the settings page, served from the ESP32), `docs/` (the message protocol). The protocol is a separate document: every line, its fields and who is allowed to send it.

### What you should get and what to record
- **Echo test.** 200+ characters go out and come back without losses or corruption. If they get lost, the culprit is almost always the port baud rate or the ground. First get a clean echo with the USB-UART, and only then connect the ESP32 — otherwise you can't tell whose fault it is.
- **The S-line stream.** In the ESP32 debug output (USB port, `Serial`) the `S,…` lines arrive every 500 ms ± 50 ms, and whether the widget is visible on the radio screen doesn't affect this: `tick()` is called from both `refresh()` and `background()`.
- **Transitions.** Record the time of every transition using `millis()` debug stamps. Disarm — GROUND and a Wi-Fi access point after 3 s. Arm — FLIGHT immediately, Wi-Fi off. Cable from the radio pulled out in GROUND — FLIGHT after 2 s. A garbage line doesn't change the state.
- **Testing on a PC without the radio.** The same scenarios are checked with an emulator: a script on the PC sends S-lines to the USB-UART at the right rate and with dropouts. This is faster and more repeatable than flipping a switch.

### docs/protocol.md
Every protocol line gets its own section: format (`S,<mode>,<armed>,<vbat>,<rssi>`), fields and units, who sends it and how often, what the receiver does on a format error and when lines are missing. A protocol that isn't in a document turns into “whatever the code does” and breaks at the first edit.

The lab counts as done when the echo test with the USB-UART passes on 200+ characters, the widget sends S-lines from `refresh()` and `background()`, the ESP32 drops to FLIGHT on a line timeout with a measured time, and the protocol is described in `docs/`.

## diagnostics
- **Symptom:** the companion loses the link when the radio screen changes
  - Possible cause: sending only in `refresh()`.
  - What to do: a shared `tick()` in `refresh()` and `background()`.
- **Symptom:** lines arrive truncated
  - Possible cause: `serialRead` is called less often than data arrives, and the buffer overflows.
  - What to do: read in every `tick()`, shorten the messages, lower the rate.
- **Symptom:** the access point came up in flight
  - Possible cause: protection on only one side.
  - What to do: check arm both in Lua and in the firmware; heartbeat timeout → FLIGHT.
- **Symptom:** the ESP32 reboots when Wi-Fi turns on
  - Possible cause: a supply voltage sag (peaks of 300–500 mA).
  - What to do: a 470 µF capacitor on 3.3 V, a BEC/LDO with headroom, don't power it from a radio pin without checking the current.
- **Symptom:** the Lua on the radio doesn't see the ESP32's replies
  - Possible cause: the AUX port isn't in Lua mode, baud rate, TX/RX.
  - What to do: Hardware → AUX = Lua, `setSerialBaudrate`, an analyzer on the line.

## references
- EdgeTX Lua API Reference | https://luadoc.edgetx.org/ | primary | A
- EdgeTX Lua serial API source (api_general.cpp, GitHub) | https://github.com/EdgeTX/edgetx/blob/main/radio/src/lua/api_general.cpp | primary | A
- ESP32 Arduino core — Wi-Fi API (GitHub) | https://github.com/espressif/arduino-esp32 | primary | A
- PlatformIO — Documentation | https://docs.platformio.org/ | primary | A

## checklist
- UART levels checked with a multimeter, GND is common
- Echo test with the USB-UART passed on 200+ characters
- Heartbeat is sent from `refresh()` and `background()`
- Undefined state = FLIGHT, Wi-Fi verifiably off
- In-flight write protection on both sides
- Power budget calculated per mode
