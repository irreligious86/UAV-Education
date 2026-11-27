---
id: bf-ports
title: "Ports and the receiver: UART setup and connecting the RC link"
level: L1
readingTime: "30 min"
firmware: Betaflight 2025.12 (checked against 2025.12.5)
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
source_hash: 7ad3e5f6f532
---

## summary

**UART** is the basis for connecting the receiver, GPS, telemetry, VTX and other devices to the flight controller in Betaflight. The **Ports** tab decides whether control reaches the firmware at all.

**In this article:**

- how to read a **pinout** and not take the port used by USB;
- **wiring** for SBUS, CRSF/ELRS, FPort, IBUS, Spektrum;
- **Serial Rx** in the **Ports** tab + the protocol choice in the **Receiver** tab;
- typical failures (**MSP**, limits, F4/SBUS).

## theory

### What a UART is and why ports are configured

A **UART** is a serial interface: a pair of **TX** (transmit) and **RX** (receive) lines. In the **Ports** tab every physical UART is given a role: **Serial Rx**, **GPS**, telemetry, **MSP** and so on.

**The rule:** one UART carries **one main role** for its data stream at a time. Combining, for example, **Serial Rx** and **Telemetry Output** on one port without understanding the protocol often produces a conflict and “breaks” the saving of settings.

### Receiver types and wiring

The protocol determines both the wiring and the **Serial Receiver Provider** setting in the configurator.

- **SBUS** (FrSky, Futaba, some DJI) — in BF: **SBUS**. The receiver signal → **RX** of the chosen UART (not TX).
- **CRSF** (TBS Crossfire, **ExpressLRS**) — in BF: **CRSF**. For a serial ELRS receiver the move from 3.x to 4.x changes nothing in the ports (the same CRSF, 420000 baud); an on-board SPI ELRS receiver takes no port, but under 2025.12 it stays on ELRS 3 and will not link with a module on 4.x (link-elrs). **Receiver RX → FC TX**, **receiver TX → FC RX** (the classic crossover connection for full duplex).
- **FPort** (FrSky) — **FrSky FPort**; one wire, and the inversion/pin depend on the board and the version — check the FC manual.
- **IBUS** (FlySky, Turnigy) — **IBUS**, signal → **RX**.
- **Spektrum DSM** — **SPEKTRUM1024** / **SPEKTRUM2048**, the signal wire per the receiver documentation.

**F4 and SBUS:** some boards have **no** hardware inverter for the inverted SBUS signal — use the dedicated **SBUS** pin on the FC or another protocol — for a new build **CRSF** (ELRS): it is not inverted and is full duplex (`link-protocols`, “new builds — CRSF”); FPort — only if you already have a FrSky receiver, and it has the same dependence of inversion on the board; otherwise an external inverter is needed.

### Betaflight 4.4+ and Cloud Build

From **4.4.0**, a **Cloud Build** puts only the selected **receiver protocols** into the firmware. By default only **CRSF** is selected in Firmware Flasher; **SBUS** and **GHST** also have to be selected by hand. **IBUS**, **Spektrum** and others must be **selected explicitly** for the build — otherwise the receiver is “silent” with any wiring. A separate case is an ELRS receiver wired on the board over SPI (a whoop AIO): it needs no UART, and its code lives in the Betaflight firmware. In 2025.12 this is ELRS 3 (`ELRS_OTA_VERSION_ID 3`), so such a board will not link with a transmitter on ELRS 4; ELRS 4 support for SPI receivers appears only in 2026.6. The options: a transmitter on 3.x for this model, or a separate receiver on a UART (link-elrs).

### MSP limits

**MSP** is needed by the configurator and by some devices. The limit: **no more than three** ports with **MSP** enabled at the same time; with a fourth the port configuration is considered invalid and at boot **all of it** is reset to defaults. The check is made by `isSerialConfigValid()` in `io/serial.c` (the same in 4.5 and 2025.12.5): USB VCP, on which MSP is mandatory, counts toward the three; MSP can share a port only with telemetry, Blackbox or VTX (MSP + Displayport), and any other pair of functions on one port — except a few pairs with Serial RX (for example, an SBUS receiver on the RX line and FrSky Hub, LTM or MAVLink telemetry on the TX line) — also makes the configuration invalid. A port with only the VTX_MSP bit and no MSP is invalid too: this function is allowed only in a pair (`bitCount == 1` in the same function).

{{diagram:bf-serial-valid-tree|The port check at boot: more than three ports with MSP or a disallowed pair of functions on one port — and the whole port configuration is reset to defaults.}}

**Tip:** the **USB** connection to the PC usually uses a separate channel; do not reassign it to the receiver without understanding the board schematic.

### The `serial` command: what is actually stored
The Ports tab is a wrapper around `serial <id> <function mask> <msp baud> <gps baud> <telemetry baud> <blackbox baud>`: the port identifier (in 2025.12 — a name: `UART1`, `UART3`, `VCP`, `SOFT1`…; `diff` writes names, for example `serial UART3 64 …`. In 4.5 — a number: 0 = UART1, 1 = UART2, … 20 = VCP/USB, 30+ = SoftSerial; 2025.12 accepts the numbers too), the function bit mask (MSP = 1, GPS = 2, … Serial RX = 64, Blackbox = 128, ESC Sensor, SmartAudio, Tramp, MSP DisplayPort — their own bits; the exact values are in the `serialPortFunction_e` enum in `src/main/io/serial.h`), and the baud rates. That is why `diff all` contains lines such as `serial UART3 64 115200 57600 0 115200` (in 4.5 — `serial 2 64 115200 57600 0 115200`) — UART3 = Serial RX. Reading them is useful when moving configs between boards: UART numbers differ from board to board.

The bits of the function mask (`serialPortFunction_e`, `src/main/io/serial.h`; the same in 4.5 and 2025.12, except for bit 262144 added in 2025.12 — GIMBAL, a serial gimbal); the port mask is the sum of the bits of its functions:

| Bit | Function (Ports tab label) | Bit | Function (Ports tab label) |
|---|---|---|---|
| 1 | MSP | 1024 | ESC Sensor (ESC) |
| 2 | GPS | 2048 | SmartAudio (VTX (TBS SmartAudio)) |
| 4 | FrSky Hub telemetry (FrSky) | 4096 | IBUS telemetry (iBUS) |
| 8 | HoTT telemetry (HoTT) | 8192 | IRC Tramp (VTX (IRC Tramp)) |
| 16 | LTM telemetry (LTM) | 16384 | RunCam Device Protocol (Camera (RunCam Protocol)) |
| 32 | SmartPort telemetry (SmartPort) | 32768 | TF lidar (Benewake LIDAR) |
| 64 | Serial RX (Serial Rx) | 65536 | FrSky OSD (OSD (FrSky Protocol)) |
| 128 | Blackbox (Blackbox logging) | 131072 | VTX_MSP (VTX (MSP + Displayport)) |
| 512 | MAVLink telemetry (MAVLink) | | |

Examples (in 2025.12 notation; in 4.5 the numbers 1, 0 and 2 instead of the names): `serial UART2 64 …` — the receiver; `serial UART1 131073 115200 …` — an HD system (DJI/Walksnail/HDZero): 131073 = MSP (1) + VTX_MSP (131072), and the 131072 bit alone without MSP gives no OSD (bf-hd-osd-video); `serial UART3 2048 …` — SmartAudio. Bit 256 is not used. CRSF telemetry has no separate bit: it goes over the Serial RX port with `feature TELEMETRY`.

### Receiver parameters that are not in the Ports tab
- `serialrx_inverted` (OFF by default) changes the polarity **relative to the protocol standard**: for SBUS (inverted by the standard) ON = a normal non-inverted signal, for CRSF/FPort ON = inverted (`rx/sbus.c`, `rx/fport.c`, `rx/crsf.c`). On F7, H7 and G4 the UART itself does the inversion; on F4 only the board's hardware inverter does (the `INVERTER` resource), if this UART has one; without it, SBUS on an F4 goes to the pad marked SBUS.
- `serialrx_halfduplex` — receive and transmit over the single wire of the TX pad (FPort, SRXL2). The default depends on the build (`pg/rx.c`): ON if the firmware has FPort or SRXL2 but not the whole set of CRSF, GHST, IBUS, SBUS, Spektrum, XBUS; otherwise OFF. After a Cloud Build check `get serialrx_halfduplex`.
- `crsf_use_negotiated_baud` (OFF by default): CRSF starts at 420000 baud (`CRSF_BAUDRATE`); with ON the FC accepts a baud rate change command from the receiver (CRSF v3) and starts at the last negotiated rate from the persistent area (`getCrsfCachedBaudrate()` in `telemetry/crsf.c`; if nothing is there — 420000 again). For ELRS — OFF: an ELRS 4.1.0 receiver does not send the baud rate change command (subcommand 0x70 is in neither `src/include/crsf_protocol.h` nor `src/lib/CrsfProtocol`), and the rate of its UART is set by the receiver firmware option `uart_baud` (`rx_main.cpp`). ON — only with a receiver that sends such a command.

### Setup from a phone
On the FC side this is ordinary MSP on a UART: a free port with the MSP function (bit 1, 115200), no more than three MSP ports. On the application side — per the Betaflight App documentation (2025.12.1+): the web version connects over Bluetooth to boards with built-in BLE (those supported by the SpeedyBee app and some others), and the native Android app — over USB OTG and over Wi-Fi through an ELRS receiver (TCP). An external UART ↔ Bluetooth/Wi-Fi bridge (HC-05, ESP32) works only with an application that is able to connect to it. Save the config from a phone the same way: `diff all` to a file at the end.

### Functions by port: compatibility
| Function | Wires | Can share the port with | Notes |
|---|---|---|---|
| Serial RX (CRSF) | TX+RX | nothing | full duplex, telemetry on the same port |
| Serial RX (SBUS) | RX | — | an inverter on F4 |
| GPS | TX+RX | — | 57600 (the default; at 115200 the documentation reports dropped frames, `bf-gps-setup`), UBX; `gps_auto_config` |
| MSP (configurator/computer) | TX+RX | — | ≤ 3 ports with MSP |
| MSP DisplayPort (HD OSD) | TX+RX | — | 115200, the VTX settings go through the same port |
| ESC Sensor (ESC telemetry) | RX | — | one shared wire from all the ESCs |
| VTX SmartAudio / Tramp | TX | — | one wire; SA at 4800 baud |
| Telemetry (SmartPort/MAVLink/LTM) | TX (or TX+RX) | — | for the radio/ground station |
| Blackbox (an external OpenLog logger) | TX | — | rare |
| SoftSerial | any 2 pins | — | up to 19200 (the firmware limits it), MSP and Serial RX are not allowed on it |
Out of resources? `resource serial_tx 11 A09`/`resource serial_rx 11 A10` — softserial on free pads (LED, PPM), with a caveat about CPU load.

### A worked example: distributing 5 devices over 4 UARTs on an F405
The devices: ELRS (CRSF), GPS, a digital VTX (DisplayPort), ESC telemetry, a SmartAudio VTX — no: a digital and an analog VTX are never fitted together; so let it be an analog VTX with SmartAudio + a camera with the RunCam protocol. UART1 — CRSF (the SBUS port is not what is needed), UART2 — GPS, UART3 — SmartAudio (the TX pin), UART4 — ESC Sensor (the RX pin), RunCam Device — on SoftSerial 11 on the LED pad. The rule: full-duplex devices first (CRSF, GPS, DisplayPort), then single-wire ones, then softserial for what is not critical.

{{diagram:bf-uart-plan|A worked example: five devices on the four UARTs of an F405 — full-duplex ones first, then single-wire ones, then softserial.}}

### Place in the system

- **Receives:** the physical UARTs of the board and their pinout (`f-fc-sensors`); the protocol and signal polarity of the receiver (`link-protocols`); the set of protocols included in the build (`bf-custom`).
- **Provides:** RC frames — to the firmware (`bf-rates-rc`); ports for GPS (`bf-gps-setup`), HD OSD and VTX (`bf-hd-osd-video`); the `serial` lines — to `diff all` (`bf-cli`).
- **If you get it wrong here:** MSP is enabled on a fourth port → at boot the whole port configuration is reset to defaults, the receiver disappears, and arming is blocked by the `RXLOSS` flag (`bf-arming-safety`). SBUS is fed to a UART of an F4 board without an inverter → garbage instead of frames, no channels; the electrical side of the signal is covered in `link-protocols`.

## practice

### Step 1. Identifying the UARTs on the FC

1. Find the **pinout** (the silkscreen on the board or the manufacturer's site).
2. The UARTs are labeled **UART1…** or **RX1/TX1** and correspond to the rows in the **Ports** tab.

**Tip:** **USB** on STM32 boards is a separate virtual port (the USB VCP row in Ports), not UART1; the exception is rare boards with an external USB-UART bridge — do not choose that port for the receiver without reading the schematic.

### Step 2. Physically connecting the receiver

1. **Remove power** from the FC before soldering or plugging into a connector.
2. Take a **free** UART for the receiver (it is often convenient to leave the USB channel as is and use **UART2/UART3**).
3. Wire it per the list above (**SBUS → RX**, **CRSF → crossover** and so on).
4. Check the **solder joints** and that there are no **shorts** between neighboring pins.

### Step 3. The Ports tab

1. Connect the FC over **USB** and open **Betaflight App** (for 4.5 — Configurator 10.10).
2. **Ports** — find the **UART** row that the receiver goes to.
3. **Do not disable MSP** on a UART that is also needed for the connection to the PC (see the board manual).
4. Enable only **Serial Rx** on the chosen UART; turn **the other functions** on the same UART off (**MSP**, extra telemetry and so on, if they conflict with your wiring).
5. **Save and Reboot**.

**Exercise without hardware: `serial` masks.** Part A. Write down the function mask for every port of the worked example (F405, five devices): UART1 — the CRSF receiver, UART2 — GPS, UART3 — SmartAudio, UART4 — ESC Sensor, SoftSerial — RunCam Device Protocol, USB VCP — MSP. Separately — the mask of the port of an HD system (MSP + VTX) and of the port of an external Blackbox logger.

Part B. Decode the masks in the table, count the ports with MSP and find all the violations (a teaching example, assembled by hand; the baud rates are omitted). Then write down the corrected masks, knowing what is physically connected: to UART1 — a Bluetooth bridge for setup from a phone, to UART2 — the ELRS receiver, to UART3 — GPS, to UART4 — the ESC telemetry wire, UART5 is empty, to UART6 — an HD system with OSD; there is no analog VTX on the aircraft.

| `diff` line | Mask |
|---|---|
| `serial VCP …` | 1 |
| `serial UART1 …` | 1 |
| `serial UART2 …` | 64 |
| `serial UART3 …` | 2050 |
| `serial UART4 …` | 1025 |
| `serial UART5 …` | 1 |
| `serial UART6 …` | 131072 |

### Step 4. The receiver protocol (the Receiver tab)

1. After the reboot — the **Receiver** tab.
2. **Receiver Mode:** **Serial (via UART)** (as in the configurator hint).
3. **Serial Receiver Provider** — strictly to match the hardware:

   - TBS Crossfire / **ELRS** → **CRSF**
   - FrSky **SBUS** → **SBUS**
   - FrSky **FPort** → **FrSky FPort**
   - FlySky / Turnigy → **IBUS**
   - Spektrum → **SPEKTRUM1024** / **SPEKTRUM2048**

4. **Save and Reboot**.

### Step 5. Checking Receiver

1. The receiver is **bound** to the radio (the indication per its manual).
2. The **Receiver** tab — moving the sticks and switches **moves the channel bars**.
3. The range is typically **~1000–2000**, the center **~1500**.

### Step 6. Additionally

- The bars move the “wrong” channels — **Channel Map** (**AETR**, **TAER** …) in **Receiver**.
- The ends of the range are off — **endpoints** on the radio or `rxrange` in the **CLI**.
- **Telemetry to the radio** (CRSF/ELRS): it usually goes over the same UART as control; if needed, check the **Telemetry** options in **Configuration** for your setup.

Self-check: the lab is complete when:
- part A: UART1 = 64, UART2 = 2, UART3 = 2048, UART4 = 1024, SoftSerial = 16384, VCP = 1; the HD system = 131073; the Blackbox logger = 128;
- part B, decoding: 2050 = 2 + 2048 (GPS + SmartAudio), 1025 = 1 + 1024 (MSP + ESC Sensor), 131072 — the VTX bit alone without MSP;
- part B, the count: there are four ports with MSP (VCP, UART1, UART4, UART5) against a limit of three;
- exactly four violations are found, and you have written down how a boot with such a configuration will end (the reference is below);
- the corrected masks: VCP = 1, UART1 = 1, UART2 = 64, UART3 = 2, UART4 = 1024, UART5 = 0, UART6 = 131073; the ports with MSP are now three (VCP, UART1, UART6);
- on hardware (if you have it): after steps 3–5 `diff all` contains one `serial` line per port in use, and every mask decodes into the function that is actually wired.

**Reference for self-check.** The four violations: (1) four ports with MSP instead of at most three; (2) UART3 — two functions of different devices on one port (GPS and SmartAudio); (3) UART4 — MSP together with ESC Sensor, while MSP shares a port only with telemetry, Blackbox or VTX; (4) UART6 — bit 131072 without MSP: there will be no OSD. The result: the port configuration is invalid and at boot all of it is reset to defaults — the receiver disappears, and arming is blocked by the `RXLOSS` flag. Frequent wrong answers: “there are three ports with MSP, the limit is not exceeded” — VCP was not counted; the mask of the HD system written as 131072 — the MSP bit (1) was forgotten; 2050 read as one function — a port mask always decomposes into powers of two from the table, and every term is a separate function; in part A a telemetry bit was added for CRSF — CRSF has none, telemetry goes over the Serial RX port with `feature TELEMETRY`.

## diagnostics

- **Symptom:** After the ports are saved and the FC reboots, the settings “roll back”.
  - Possible cause: a conflict of functions on one UART (**Serial Rx** + an extra **MSP** and the like) or the limit of **MSP** on three ports.
  - What to do: in the **Ports** tab leave only what is needed on the receiver's UART; make sure there are no more than three ports with **MSP**; save and reboot.

- **Symptom:** The bars in **Receiver** do not move, and the receiver is linked.
  - Possible cause: **Serial Rx** is on the wrong UART; a wrong **Provider**; firmware without the required protocol (**Cloud Build**).
  - What to do: check **Ports** and **Configuration**; for BF **4.4+** rebuild the firmware with the required receiver protocol.

- **Symptom:** CRSF/ELRS works, but there is no telemetry on the radio.
  - Possible cause: telemetry is off in the link settings, or the provider is not **CRSF**.
  - What to do: **Serial Receiver Provider = CRSF**; enable telemetry per the ELRS/radio manual.

- **Symptom:** SBUS on an F4 does not work.
  - Possible cause: no inverter, the signal does not go to the **SBUS** pin / the wrong UART.
  - What to do: the **SBUS** pin on the board, a change of protocol to CRSF (or FPort for a FrSky receiver), an external inverter.

- **Symptom:** The bars move but do not fit within 1000–2000.
  - Possible cause: **endpoints** on the radio; `rxrange` is not set.
  - What to do: set the travel on the radio; if needed, **`rxrange`** in the CLI.

- **Symptom:** After GPS passthrough was set up, the MSP settings “disappear”.
  - Possible cause: the limit of **three** ports with **MSP** is exceeded.
  - What to do: disable **MSP** where it is not needed; leave no more than three ports with MSP.
- **Symptom:** after Ports is saved the configurator “drops out”
  - Possible cause: MSP is disabled on the USB/VCP port, or MSP is enabled on a 4th port.
  - What to do: connect through another port/DFU, `serial VCP 1 115200 …` (in 4.5 — `serial 20 1 115200 …`) for VCP.
- **Symptom:** ESC Sensor gives no telemetry
  - Possible cause: the wire is on TX instead of RX, the ESC has no telemetry, `esc_sensor` is not enabled.
  - What to do: the RX pin, the ESC firmware, `feature ESC_SENSOR` in the CLI (or bidirectional DShot as an alternative for RPM).

## references

- Ports Tab — Betaflight Documentation | https://www.betaflight.com/docs/wiki/app/ports-tab | primary | A
- Serial (UART) configuration — Betaflight Documentation | https://betaflight.com/docs/wiki/guides/current/Serial | primary | A
- Betaflight Setup Guide — receiver and ports | https://betaflight.com/docs/wiki/getting-started/setup-guide | primary | A
- ExpressLRS — Configuring the flight controller | https://www.expresslrs.org/quick-start/receivers/configuring-fc/ | primary | A
- Connecting EZ ID to Betaflight for GPS Passthrough — Flite Test | https://www.flitetest.com/articles/connecting-ez-id-to-betaflight-for-gps-passthrough | secondary | B
