---
id: bf-ports
title: "Ports and Receiver: UART Setup and Connecting the RC Link"
level: L1
readingTime: "30 min"
firmware: Betaflight 4.5+
status: published
tags:
  - ports
  - UART
  - receiver
  - Serial RX
  - wiring
references:
  - title: "Ports Tab — Betaflight Documentation"
    url: "https://www.betaflight.com/docs/wiki/app/ports-tab"
    tier: primary
    stack: betaflight
  - title: "Serial (UART) configuration — Betaflight Documentation"
    url: "https://betaflight.com/docs/wiki/guides/current/Serial"
    tier: primary
    stack: betaflight
  - title: "Betaflight Setup Guide — receiver and ports"
    url: "https://betaflight.com/docs/wiki/getting-started/setup-guide"
    tier: primary
    stack: betaflight
  - title: "ExpressLRS — Configuring the flight controller"
    url: "https://www.expresslrs.org/quick-start/receivers/configuring-fc/"
    tier: primary
    stack: betaflight
  - title: "Connecting EZ ID to Betaflight for GPS Passthrough — Flite Test"
    url: "https://www.flitetest.com/articles/connecting-ez-id-to-betaflight-for-gps-passthrough"
    tier: secondary
    stack: betaflight
related:
  - bf-intro
  - bf-modes-osd
next:
  - bf-modes-osd
source: content/betaflight/bf-ports.md
source_hash: 381df4def8cc
---

## summary

**UART** is the foundation for connecting the receiver, GPS, telemetry, VTX and more to the flight controller in Betaflight. The **Ports** tab decides whether your control inputs ever reach the firmware.

**In this article:**

- how to read the **pinout** and not take over the USB port;
- **wiring** for SBUS, CRSF/ELRS, FPort, IBUS, Spektrum;
- **Serial Rx** in the **Ports** tab + choosing the protocol in the **Receiver** tab;
- typical failures (**MSP**, limits, F4/SBUS).

## theory

### What UART is and why port setup matters

**UART** is a serial interface: a pair of **TX** (transmit) and **RX** (receive). In the **Ports** tab each physical UART is assigned a role: **Serial RX**, **GPS**, telemetry, **MSP** and so on.

**Rule:** one UART carries **one main role** for the data stream at a time. Combining, for example, **Serial Rx** and **Telemetry Output** on one port without understanding the protocol often causes a conflict and “breaks” saving the settings.

### Receiver types and wiring

The protocol determines both the wiring and the **Serial Receiver Provider** entry in the configurator.

- **SBUS** (FrSky, Futaba, some DJI) — in BF: **SBUS**. Signal from the receiver → **RX** of the chosen UART (not TX).
- **CRSF** (TBS Crossfire, **ExpressLRS**) — in BF: **CRSF**. **Receiver RX → FC TX**, **receiver TX → FC RX** (the classic crossover connection for full duplex).
- **FPort** (FrSky) — **FrSky FPort**; one wire, inversion/pin depend on the board and version — check your FC manual.
- **IBUS** (FlySky, Turnigy) — **IBUS**, signal → **RX**.
- **Spektrum DSM** — **SPEKTRUM1024** / **SPEKTRUM2048**, signal wire per the receiver documentation.

**F4 and SBUS:** some boards have **no** hardware inverter for inverted SBUS — use the dedicated **SBUS** pin on the FC or another protocol (**FPort** etc.), otherwise you'll need an external inverter.

### Betaflight 4.4+ and Cloud Build

Since **4.4.0**, when building via **Cloud Build**, only the selected **receiver protocols** get into the firmware. By default only **CRSF** is checked in the Firmware Flasher; **SBUS** and **GHST** also have to be selected manually. **IBUS**, **Spektrum** and others must be **explicitly checked** at build time — otherwise the receiver “stays silent” no matter how it's wired.

### MSP limits

**MSP** is needed by the configurator and some devices. The limit: **no more than three** UARTs with **MSP** enabled at the same time; with a fourth, the port configuration is considered invalid and on boot **all** of it is reset to defaults.

**Tip:** the **USB** connection to the PC usually takes a separate channel; don't reassign it to the receiver without understanding the board's schematic.

### The `serial` command: what is actually stored
The Ports tab is a wrapper around `serial <id> <function mask> <msp baud> <gps baud> <telemetry baud> <blackbox baud>`: the port identifier (in 4.5: 0 = UART1, 1 = UART2, … 20 = VCP/USB, 30+ = SoftSerial; in 2025.12 `diff` writes names, e.g. `serial UART3 64 …`), the function bitmask (MSP = 1, GPS = 2, … Serial RX = 64, Blackbox = 128, ESC Sensor, SmartAudio, Tramp, MSP DisplayPort — their own bits; the exact values are the `serialPortFunction_e` enum in `src/main/io/serial.h`), and the baud rates. That's why `diff all` contains lines like `serial 2 64 115200 57600 0 115200` — UART3 = Serial RX. Reading them is useful when moving configs between boards: UART numbering differs between boards.

### Functions per port: compatibility
| Function | Wires | Can share a port with | Notes |
|---|---|---|---|
| Serial RX (CRSF) | TX+RX | nothing | full duplex, telemetry on the same port |
| Serial RX (SBUS) | RX | — | inverter on F4 |
| GPS | TX+RX | — | 57600/115200, UBX; `gps_auto_config` |
| MSP (configurator/computer) | TX+RX | — | ≤ 3 ports with MSP |
| MSP DisplayPort (HD OSD) | TX+RX | — | 115200, VTX settings through the same port |
| ESC Sensor (ESC telemetry) | RX | — | one shared wire from all ESCs |
| VTX SmartAudio / Tramp | TX | — | one wire; SA 4800 baud |
| Telemetry (SmartPort/MAVLink/LTM) | TX (or TX+RX) | — | for the radio/ground station |
| Blackbox (external OpenLog logger) | TX | — | rare |
| SoftSerial | any 2 pins | — | up to 19200 (limited by firmware), MSP and Serial RX not allowed on it |
Not enough resources for everything? `resource serial_tx 11 A09`/`resource serial_rx 11 A10` — softserial on free pads (LED, PPM), with a CPU caveat.

### Worked example: fitting 5 devices onto 4 UARTs on an F405
Devices: ELRS (CRSF), GPS, digital VTX (DisplayPort), ESC telemetry, SmartAudio VTX — no: you can't have a digital and an analog VTX at the same time; so make it an analog VTX with SmartAudio + a camera with the RunCam protocol. UART1 — CRSF (you don't need the SBUS port), UART2 — GPS, UART3 — SmartAudio (TX pin), UART4 — ESC Sensor (RX pin), RunCam Device — on SoftSerial 11 via the LED pad. The rule: full-duplex first (CRSF, GPS, DisplayPort), then single-wire, then softserial for non-critical stuff.

{{diagram:bf-uart-plan|Worked example: five devices on four F405 UARTs — full-duplex first, then single-wire, then softserial.}}

## practice

### Step 1. Identifying the UARTs on the FC

1. Find the **pinout** (silkscreen on the board or the manufacturer's website).
2. UARTs are labeled **UART1…** or **RX1/TX1** and correspond to the rows in the **Ports** tab.

**Tip:** **USB** on STM32 boards is a separate virtual port (the USB VCP row in Ports), not UART1; the exception is rare boards with an external USB-UART bridge — don't pick that port for the receiver without reading the schematic.

### Step 2. Physically connecting the receiver

1. **Power off** the FC before soldering/plugging into the connector.
2. Use a **free** UART for the receiver (it's often convenient to leave the USB channel as is and take **UART2/UART3**).
3. Solder per the table above (**SBUS → RX**, **CRSF → crossover** etc.).
4. Check the **soldering** and that there are no **shorts** between neighboring pins.

### Step 3. Ports tab

1. Connect the FC via **USB**, open **Betaflight Configurator**.
2. **Ports** — find the **UART** row the receiver goes to.
3. **Don't disable MSP** on a UART that you also need for the PC connection (see the board manual).
4. Enable only **Serial Rx** on the chosen UART; turn **other functions** on the same UART off (**MSP**, extra telemetry etc., if they conflict with your setup).
5. **Save and Reboot**.

### Step 4. Receiver protocol (Configuration)

1. After the reboot — the **Receiver** tab.
2. **Receiver Mode:** **Serial-based receiver** (as the configurator hint says).
3. **Serial Receiver Provider** — strictly to match the hardware:

   - TBS Crossfire / **ELRS** → **CRSF**
   - FrSky **SBUS** → **SBUS**
   - FrSky **FPort** → **FrSky FPort**
   - FlySky / Turnigy → **IBUS**
   - Spektrum → **SPEKTRUM1024** / **SPEKTRUM2048**

4. **Save and Reboot**.

### Step 5. Checking the Receiver

1. The receiver is **bound** to the radio (indication per the manual).
2. **Receiver** tab — moving the sticks and switches **moves the channel bars**.
3. The range is typically **~1000–2000**, center **~1500**.

### Step 6. Extras

- Bars respond to the “wrong” channels — **Channel Map** (**AETR**, **TAER** …) on **Receiver**.
- Range ends are off — **endpoints** on the radio or `rxrange` in the **CLI**.
- **Telemetry to the radio** (CRSF/ELRS): usually goes over the same UART as control; if needed, check the **Telemetry** options in **Configuration** for your link.

## diagnostics

- **Symptom:** After saving the ports and rebooting, the settings “rolled back.”
  - Possible cause: a function conflict on one UART (**Serial Rx** + an extra **MSP** etc.) or the **MSP** limit of three ports.
  - What to do: in the **Ports** tab leave only what's needed on the receiver UART; make sure no more than three ports have **MSP**; save and reboot.

- **Symptom:** In **Receiver** the bars don't move, the receiver is linked.
  - Possible cause: **Serial Rx** on the wrong UART; wrong **Provider**; firmware without the needed protocol (**Cloud Build**).
  - What to do: check **Ports** and **Configuration**; for BF **4.4+** rebuild the firmware with the needed receiver protocol.

- **Symptom:** CRSF/ELRS works, but there's no telemetry on the radio.
  - Possible cause: telemetry is disabled in the link settings or the provider isn't **CRSF**.
  - What to do: **Serial Receiver Provider = CRSF**; enable telemetry per the ELRS/radio manual.

- **Symptom:** SBUS on F4 won't come up.
  - Possible cause: no inverter, the signal doesn't go to the **SBUS** pin / wrong UART.
  - What to do: the **SBUS** pin on the board, **FPort**, an external inverter, or a different protocol.

- **Symptom:** The bars move but don't fit into 1000–2000.
  - Possible cause: **endpoints** on the radio; `rxrange` not set.
  - What to do: set the travel on the radio; if needed, **`rxrange`** in the CLI.

- **Symptom:** After setting up GPS passthrough, MSP settings “disappear.”
  - Possible cause: the limit of **three** ports with **MSP** is exceeded.
  - What to do: disable **MSP** where it isn't needed; leave no more than three UARTs with MSP.
- **Symptom:** after saving Ports, the configurator “drops off”
  - Possible cause: MSP disabled on the USB/VCP port, or MSP enabled on a 4th port.
  - What to do: connect through another port/DFU, `serial 20 1 115200 …` for VCP.
- **Symptom:** ESC Sensor gives no telemetry
  - Possible cause: wire on TX instead of RX, ESC without telemetry, `esc_sensor` not enabled.
  - What to do: RX pin, ESC firmware, `feature ESC_SENSOR` in the CLI (or bidirectional DShot as an alternative for RPM).

## references

- Ports Tab — Betaflight Documentation | https://www.betaflight.com/docs/wiki/app/ports-tab | primary | A
- Serial (UART) configuration — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/Serial | primary | A
- Betaflight Setup Guide — receiver and ports | https://betaflight.com/docs/wiki/getting-started/setup-guide | primary | A
- ExpressLRS — Configuring the flight controller | https://www.expresslrs.org/quick-start/receivers/configuring-fc/ | primary | A
- Connecting EZ ID to Betaflight for GPS Passthrough — Flite Test | https://www.flitetest.com/articles/connecting-ez-id-to-betaflight-for-gps-passthrough | secondary | B
