---
id: inav-telemetry-gcs
title: "INAV telemetry and links: CRSF/SmartPort/LTM/MAVLink, MSP RC, Bluetooth and ground stations"
level: L2
readingTime: 75 min
firmware: INAV 9.1 (checked against 9.1.0)
status: published
added: 2026-11-20
tags:
  - INAV
  - telemetry
  - CRSF
  - SmartPort
  - LTM
  - MAVLink
  - MSP
  - serial
  - ground station
related:
  - inav-setup-scratch
  - inav-missions
  - inav-osd-hd
  - inav-cli-backup
  - link-elrs
  - link-edgetx
  - link-telemetry-radios
  - comp-mavlink
  - mav-protocol
  - bf-ports
next:
  - inav-missions
source: content/inav/inav-telemetry-gcs.md
source_hash: b984dd3865b4
---

## summary
A flight controller on INAV reports about itself over several protocols and accepts commands from outside over several as well, and all of them share the same UARTs. This module works through them from the INAV 9.1.0 source: the port function bits and the rules by which two functions coexist on one UART; what exactly goes out over CRSF, SmartPort, LTM and MAVLink and how often; which incoming MAVLink messages the handler really understands (the list is short); how the MSP receiver and the `MSP RC OVERRIDE` mode work and what happens to them on a link loss; what a Bluetooth bridge and a ground station need. The practice is a calculation exercise: decode a `serial` dump and find the conflicts, compute the MAVLink byte budget for SiK and ELRS, build an `msp_override_channels` mask and find three errors in a config.

## theory
### The map: who talks to whom
This module is about how an INAV flight controller exchanges data with the radio, a ground station and a companion computer. The reading order: first the protocol map (the table below) and the port rules — who coexists with whom on one UART; then the “downlink” protocols in turn: CRSF, SmartPort, LTM, MAVLink with its settings and the short list of what INAV accepts; after them — “uplink” control over MSP: the MSP receiver, MSP RC Override and the command `MSP2_INAV_SET_AUX_RC`; at the end radio bridges and ground stations. The sections on MAVLink “fly here”, MSP RC Override and `SET_AUX_RC` contain safety warnings — they are about cases where someone other than the pilot controls the channels. Port assignment during the initial setup is in `inav-setup-scratch`, the downlink bandwidth in `link-elrs`, the sensors on the radio in `link-edgetx`, mission upload in `inav-missions`.

| Protocol | Port function (bit · number) | Direction | Who reads it | Baud rate |
|---|---|---|---|---|
| CRSF telemetry | none of its own: it rides on the receiver port `RX_SERIAL` (6 · 64) | down + MSP both ways | an EdgeTX radio through ELRS / Crossfire | 420000, fixed |
| SmartPort | `TELEMETRY_SMARTPORT` (5 · 32) | down on polling + MSP | FrSky X-series receivers, the radio | 57600, fixed |
| LTM | `TELEMETRY_LTM` (4 · 16) | down only | antenna trackers, OSDs, ground stations with LTM support | from the telemetry field, `AUTO` = 19200 |
| MAVLink | `TELEMETRY_MAVLINK` (8 · 256) | down + a narrow set of commands up | MAVLink ground stations, a companion, an ADS-B receiver | from the telemetry field, `AUTO` = 57600 |
| MSP | `MSP` (0 · 1) | request — reply | INAV Configurator, mobile apps, a companion script, HD video (`inav-osd-hd`) | from the MSP field, 115200 by default |
| HoTT, IBUS, SMS | 3 · 8, 9 · 512, 19 · 524288 | down | Graupner and FlySky radios, a SIM800 modem | 19200, 115200, from the telemetry field |

{{diagram:inav-telemetry-port-map|Telemetry to the radio goes over the receiver port and needs no port function of its own; LTM, MAVLink and SmartPort take separate UARTs; MSP is the only protocol through which the flight controller is configured, and there are no more than three ports with it.}}

Telemetry is enabled by `feature TELEMETRY`: without it the `TELEMETRY` task (500 Hz, idle priority) is not started, and all the protocols are silent at once, including CRSF. While the CLI is open, telemetry is stopped too.

### Ports: the function mask and what is compatible with what
The line `serial <id> <mask> <msp> <gps> <telemetry> <peripheral>` (in detail — `inav-cli-backup`): `id` 0…7 — UART1…UART8, 20 — USB VCP, 30 and 31 — SoftSerial. The mask is the sum of the bits from `io/serial.h`. A function can be added and removed by bit number: `serial 2 +4`, `serial 2 -4`.

| Bit | Number | Function | Bit | Number | Function |
|---|---|---|---|---|---|
| 0 | 1 | MSP | 9 | 512 | TELEMETRY_IBUS |
| 1 | 2 | GPS | 15 | 32768 | LOG |
| 2 | 4 | unused (the former FrSky D) | 18 | 262144 | ESCSERIAL (ESC telemetry) |
| 3 | 8 | TELEMETRY_HOTT | 19 | 524288 | TELEMETRY_SIM |
| 4 | 16 | TELEMETRY_LTM | 23 | 8388608 | SMARTPORT_MASTER |
| 5 | 32 | TELEMETRY_SMARTPORT | 25 | 33554432 | MSP_OSD (DisplayPort) |
| 6 | 64 | RX_SERIAL | 26 | 67108864 | GIMBAL |
| 7 | 128 | BLACKBOX | 27 | 134217728 | GIMBAL_HEADTRACKER |
| 8 | 256 | TELEMETRY_MAVLINK | | | |

The rules of `isSerialConfigValid()`:

1. Ports with MSP — from 1 to 3 (`MAX_MSP_PORT_COUNT`), and USB VCP counts.
2. No more than two functions on a port.
3. Only two kinds of pair are allowed: MSP + one of {HOTT, SMARTPORT, LTM, MAVLINK, IBUS, BLACKBOX, LOG} or RX_SERIAL + one of {LTM, IBUS}.
4. Everything else is an error: MAVLink + SmartPort, MSP + DisplayPort, MSP + GPS, RX_SERIAL + MAVLink.

If even one rule is violated, `validateAndFixConfig()` resets the **whole** port table to the board default on saving and loading. The symptom: after `save` the receiver and the GPS are gone although you touched one port.

On a port shared with MSP telemetry runs only while armed (while disarmed the port belongs to MSP). `telemetry_switch = ON` changes the condition: the `TELEMETRY` mode appears, and the port is switched with a switch rather than by arming. On a dedicated port telemetry always runs.

There are four baud rate fields — one per role of the port: MSP, GPS, telemetry, peripherals (DisplayPort, ESC, gimbal). The values allowed in the CLI are from the table `baudRates[]`: 1200…2470000; 0 in the telemetry field means `AUTO`. The Ports tab in Configurator 9 offers fewer: MSP 2400…230400, telemetry `AUTO` and 1200…460800.

### General telemetry settings
| Setting | Default | Allowed | Meaning |
|---|---|---|---|
| `telemetry_switch` | OFF | OFF / ON | a port shared with MSP is switched by the `TELEMETRY` mode, not by arming |
| `telemetry_inverted` | OFF | OFF / ON | invert the standard signal inversion (SmartPort, HoTT) |
| `telemetry_halfduplex` | ON | OFF / ON | SmartPort: a single wire on TX; also taken into account in the MAVLink pauses |
| `report_cell_voltage` | OFF | OFF / ON | SmartPort, IBUS and CRSF: send the average cell voltage instead of the battery voltage |
| `frsky_pitch_roll` | OFF | OFF / ON | SmartPort: pitch and roll in 0.1° instead of raw AccX/Y/Z |
| `frsky_use_legacy_gps_mode_sensor_ids` | OFF | OFF / ON | SmartPort: the old ids Tmp1 / Tmp2 instead of 470 / 480; to be removed in INAV 10 |
| `smartport_fuel_unit` | MAH | PERCENT / MAH / MWH | what to send in the Fuel sensor |
| `ltm_update_rate` | NORMAL | NORMAL / MEDIUM / SLOW | the LTM schedule |
| `hott_alarm_sound_interval` | 5 | 0…120 s | the pause between HoTT alarms |
| `ibus_telemetry_type` | 0 | 0…255 | the variant of the IBUS sensor set |
| `sim_pin`, `sim_ground_station_number`, `sim_transmit_interval`, `sim_transmit_flags`, `sim_low_altitude` | "0000", empty, 60 s, failsafe only, −32767 | an interval from 10 s | SMS telemetry through a SIM800; an SMS with the word RTH activates the return |

### CRSF: what goes to the radio
Telemetry has no `crsf_*` settings: a receiver with `serialrx_provider = CRSF` on a port with mask 64 plus `feature TELEMETRY`. The schedule is built at startup from what is on board; a full cycle is 100 ms, that is, each frame in the list goes at 10 Hz if the receiver manages to take them.

| Frame | Type | Length on the wire | Condition | EdgeTX sensors (`link-edgetx`) |
|---|---|---|---|---|
| Attitude | 0x1E | 10 | always | `Ptch`, `Roll`, `Yaw` |
| Battery | 0x08 | 12 | always | `RxBt`, `Curr`, `Capa`, `Bat%` |
| Flight mode | 0x21 | 5 + the string length | always | `FM` |
| GPS | 0x02 | 19 | `feature GPS` | `GPS`, `GSpd`, `Hdg`, `GAlt`, `Sats` |
| Vario | 0x07 | 6 | a barometer or a fixed wing with GPS | `VSpd` |
| Baro altitude | 0x09 | 6 | a barometer | `Alt` |
| RPM | 0x0C | 5 + 3 per motor | ESC telemetry is working | `RPM` |
| Temperature | 0x0D | 5 + 2 per sensor | ESCs or temperature sensors | `Temp` |
| Airspeed | 0x0A | 6 | an airspeed sensor is detected (including `VIRTUAL`); its health is not checked | `ASpd` |

The altitude in the GPS frame is the estimated altitude above the start point plus a 1000 m offset, not the altitude above sea level. The frames 0x09, 0x0A, 0x0C, 0x0D appeared in 9.x (present in 9.1.0, absent in 8.0.1).

The `FM` string in 9.1.0 has no `*` and `!` suffixes, which Betaflight sends:

| Before arming | Armed (the first match from top to bottom) |
|---|---|
| `OK` — ready to arm; `WAIT` — waiting for the fix and the home point; `!ERR` — arming is disabled | `LAND`, `!FS!`, `HRST`, `MANU`, `GEO`, `TURT`, `RTH` / `WRTH`, `LOTR` (fixed wing) / `HOLD`, `CRUZ`, `CRSH`, `WP`, `AH`, `ANGL`, `HOR`, `ANGH`, otherwise `ACRO` |

A script or a voice alert that waits for `AIR` or `ANGL*` will not trigger on INAV 9: `AIR` was removed, and `GEO`, `TURT`, `WRTH`, `LOTR` were added.

A flight controller with GPS and a barometer offers the receiver about 620 bytes/s (six frames, 62 bytes per 100 ms cycle), while the ELRS air link carries orders of magnitude less. ELRS 4.1.0 computes the downlink bandwidth like this (`TXModuleParameters.cpp`, integer division): burst = ⌊512 · f / N / 1000⌋ − 1, but no less than 1; bit/s = B · 8 · burst · f / N / (burst + 1), where f is the packet rate, N the telemetry ratio, B = 5 bytes in the ordinary modes and 10 in Full (plus 48 bit/s in Full). 250 Hz at `Std` 1:64 is 78 bit/s, less than 10 bytes/s: a 19-byte GPS frame is updated once every few seconds. If you need the coordinates for finding a crashed aircraft (`link-edgetx`, the SD Logs), set 1:8 — 146 bytes/s.

### SmartPort
The receiver polls the flight controller, which answers with one value per poll, going round the table `frSkyDataIdTable`. It needs a separate UART with mask 32; on F7 and H7 — a wire on TX, `telemetry_inverted = OFF`, `telemetry_halfduplex = ON`; on an F4 without a hardware inverter it does not work directly (you need the uninverted output of the receiver and `telemetry_inverted = ON`, or SoftSerial).

| Sensor | id | Contents |
|---|---|---|
| VFAS, Curr, Fuel | 0x0210, 0x0200, 0x0600 | voltage, current, Fuel per `smartport_fuel_unit` |
| Alt, VSpd | 0x0100, 0x0110 | altitude and vertical speed, only with a barometer |
| GPS, GSpd, GAlt, Hdg | 0x0800, 0x0830, 0x0820, 0x0840 | coordinates (two polls), speed, GPS altitude, course |
| 0420, 0450, 0460 | 0x0420, 0x0450, 0x0460 | distance to home, course over ground, azimuth to home |
| 0430, 0440 or AccX/Y/Z | 0x0430, 0x0440 or 0x0700…0x0720 | angles with `frsky_pitch_roll = ON`, otherwise accelerations |
| 470, 480 | 0x0470, 0x0480 | modes (seven digits ABCDEFG) and the GPS state; the old Tmp1 / Tmp2 — 0x0400 / 0x0410 |
| A4, ASpd | 0x0910, 0x0A00 | average cell, airspeed |

In 9.x sensor 470 grew from five digits to seven: the digits B (autoland, turtle, geozone, loiter) and A (WRTH, Angle Hold) were added.

### LTM
LightTelemetry is a one-way stream for narrow channels. A frame: `$T`, a type letter, the data, a checksum. The schedule is 10 slots of 100 ms.

| Frame | Length | Contents | NORMAL | MEDIUM | SLOW |
|---|---|---|---|---|---|
| A | 10 | pitch, roll, heading | 10 Hz | 5 | 2 |
| G | 18 | coordinates, speed, altitude, satellites | 5 | 2 | 2 |
| S | 11 | voltage, mAh, RSSI, speed, mode and arm state | 5 | 2 | 1 |
| O | 18 | the home point | 1 | 2 | 1 |
| N | 10 | the navigation state, the waypoint number | 3 | 1 | 1 |
| X | 10 | HDOP, sensor health, the disarm reason | 1 | 1 | 1 |
| Total, bytes/s | | | 303 | 164 | 105 |

The port is opened for transmit only. At 2400 baud NORMAL is silently replaced with MEDIUM, at 1200 — any schedule with SLOW. Who reads LTM cannot be seen from the INAV tree: the documentation names “OSD, ground stations and antenna trackers” without a list; check particular trackers and apps against their own descriptions — this was not verified in this module.

### MAVLink: the settings
| Setting | Default | Allowed | What it sends |
|---|---|---|---|
| `mavlink_version` | 2 | 1…2 | the frame version; with 1 the channels go as `RC_CHANNELS_RAW` (8 channels) |
| `mavlink_sysid` | 1 | 1…255 | the System ID (since 9.0) |
| `mavlink_autopilot_type` | GENERIC | GENERIC / ARDUPILOT | the autopilot field in HEARTBEAT (since 9.0) |
| `mavlink_ext_status_rate` | 2 Hz | 0…255 | `SYS_STATUS` |
| `mavlink_rc_chan_rate` | 1 | 0…255 | `RC_CHANNELS` (18 channels) |
| `mavlink_pos_rate` | 2 | 0…255 | `GPS_RAW_INT`, `GLOBAL_POSITION_INT`, `GPS_GLOBAL_ORIGIN` |
| `mavlink_extra1_rate` | 2 | 0…255 | `ATTITUDE` |
| `mavlink_extra2_rate` | 2 | 0…255 | `VFR_HUD` |
| `mavlink_extra3_rate` | 1 | 0…255 | `BATTERY_STATUS`, `SCALED_PRESSURE`, `STATUSTEXT` (if the OSD has a system message) |
| `mavlink_min_txbuffer` | 33 % | 0…100 | the threshold of the free modem buffer from `RADIO_STATUS` |
| `mavlink_radio_type` | GENERIC | GENERIC / ELRS / SIK | the conversion of RSSI and LQ from `RADIO_STATUS` for the OSD |

`HEARTBEAT` and `SYSTEM_TIME` go once a second regardless of the streams (in 8.0.1 HEARTBEAT traveled together with `VFR_HUD` in the extra2 stream). `REQUEST_DATA_STREAM` requests are not handled: the rates are set only with the settings. The mode in HEARTBEAT is translated into ArduCopter or ArduPlane mode numbers, so `mavlink_autopilot_type = ARDUPILOT` makes the ground station show familiar names.

The stream counter is built so that the real rate is lower than the set one: f = 50 / (⌊50 / r⌋ + 1). For r = 1 that is 0.98 Hz, for 2 — 1.92, for 10 — 8.33, and the ceiling is 25 Hz for any r ≥ 26. That is how it is while the flight controller has not seen `RADIO_STATUS`: transmission happens no more often than once every 20 ms. As soon as a modem (SiK with `MAVLINK = 1`, ELRS in MAVLink mode) has sent `RADIO_STATUS`, the 20 ms pause is turned off for good until a reboot, and the pace is set by the modem buffer: we send while at least `mavlink_min_txbuffer` percent is free. The rate settings then determine the proportions of the streams, not hertz. This is a conclusion from reading `handleMAVLinkTelemetry()`; it was not measured on hardware.

The length of a MAVLink 2 frame is the payload plus 12 bytes (`comp-mavlink`, `mav-protocol`). From the library in the 9.1.0 tree: `SYS_STATUS` 55, `RC_CHANNELS` 54, the three position messages 64 + 40 + 32 = 136, `ATTITUDE` 40, `VFR_HUD` 32, `BATTERY_STATUS` + `SCALED_PRESSURE` 66 + 28 = 94, `HEARTBEAT` + `SYSTEM_TIME` 21 + 24 = 45, `STATUSTEXT` 66. This is an upper bound: MAVLink 2 truncates trailing zero bytes.

The nominal budget, bytes/s = 55 · ext + 54 · rc + 136 · pos + 40 · extra1 + 32 · extra2 + 94 · extra3 + 45. At the defaults — 719.

{{diagram:chart-inav-mavlink-budget|Every hertz of the position stream costs 136 bytes/s, a hertz of ATTITUDE — 40: at the defaults 719 bytes/s get through SiK and ELRS 500 Hz but not through ELRS 250 and 150 Hz at a 1:2 ratio.}}

### MAVLink: what INAV accepts
The documentation `Telemetry.md` in the 9.1.0 tag still calls MAVLink “transmit-only”. The code accepts exactly this:

| Incoming | What INAV 9.1.0 does |
|---|---|
| `MISSION_COUNT`, `MISSION_ITEM`, `MISSION_REQUEST_LIST`, `MISSION_REQUEST`, `MISSION_CLEAR_ALL` | upload and download of a mission in RAM, only while disarmed, up to 120 waypoints; only `NAV_WAYPOINT` and `NAV_RETURN_TO_LAUNCH` are accepted, the frame `GLOBAL_RELATIVE_ALT`, `autocontinue = 1`. There are no `_INT` variants |
| `MISSION_ITEM` with `current = 2` while armed | “fly here”: waypoint 255, the frame `GLOBAL`; only with `GCS NAV` and POSHOLD active |
| `COMMAND_INT` with `MAV_CMD_DO_REPOSITION` | the same, with the heading from param4; the other commands — `UNSUPPORTED` (since 9.x) |
| `RC_CHANNELS_OVERRIDE` | the channels of the receiver `serialrx_provider = MAVLINK`, 18 channels; the System ID is not checked |
| `RADIO_STATUS` | `txbuf` for flow control; RSSI and LQ if the receiver is MAVLINK |
| `ADSB_VEHICLE`, `HEARTBEAT` from ADS-B | the list of aircraft for the OSD |
| `PARAM_REQUEST_LIST` | a single empty `PARAM_VALUE` so that the ground station stops asking |

What is missing: `COMMAND_LONG` (arming, a mode change, RTL from a ground station button), `SET_MODE`, parameters, `MISSION_ITEM_INT`, geozones and rally points. A MAVLink ground station for INAV is a map and instruments, not configuration. How to get this stream to a phone or a laptop through the ELRS Backpack over Wi-Fi is described in `link-elrs`. `RC_CHANNELS_OVERRIDE` here is not “an override on top of the radio” but the receiver itself: this is how ELRS works in MAVLink mode (`link-elrs`): a port with mask 256 at 460800, `receiver_type = SERIAL`, `serialrx_provider = MAVLINK`, `mavlink_radio_type = ELRS`.

**Safety.** “Fly here” moves the aircraft on a command from the ground. It is enabled only by the `GCS NAV` mode together with POSHOLD; do not put `GCS NAV` on a switch that is always on.

### The MSP receiver and MSP RC Override
`receiver_type = MSP`: the channels arrive with the command `MSP_SET_RAW_RC` (200), up to 34 values of 16 bits in `map` order; `MSP_RC` (105) reads them back (an example with a script is in `inav-setup-scratch`). Frames are needed at least 5 times a second: the signal is considered lost after 200 ms of silence, and then the ordinary failsafe follows.

MSP RC Override replaces some of the channels of the real receiver with values from the same `MSP_SET_RAW_RC`. The conditions: `receiver_type` is not MSP, the `MSP RC OVERRIDE` mode is active, the channel is marked in `msp_override_channels`. Bit 0 is roll, 1 pitch, 2 yaw, 3 throttle, bit 4 is AUX1 (CH5) and so on: bit = channel number − 1. The channel that carries the `MSP RC OVERRIDE` mode itself is always excluded from the mask — the radio can turn the override off whatever the frames contain.

What happens on failures (`rx/msp_override.c`, `rx/rx.c`):

- **The main receiver is lost.** Failsafe is counted from it only: 200 ms + `failsafe_delay` × 100 ms after valid frames stopped (0.7 s by default — that is the lower bound: if the receiver did not set the failsafe flag in the frame itself, its signal timeout is added to it, 100 ms for serial receivers), and the failsafe procedure takes control. The MSP stream does not “extend” the link.
- **The MSP frames are lost.** The overridden channels hold the last value for another 200 + 200 + `failsafe_delay` × 100 ms (0.9 s), then return to the pilot.
- **Start.** The override begins only after MSP frames have been arriving for 200 ms + `failsafe_recovery_delay` × 100 ms.

**Safety.** A mask with bit 3 hands the throttle to a script. Put the mode on a switch, not on a permanently active range, and test without propellers.

The differences from 8.0.1: there MSP RC Override was commented out in `target/common.h` and required a custom build; in 9.x (present in 9.1.0) it is included in stock firmware, and the mask grew from 16 to 32 bits (the limit of `msp_override_channels` 65535 → 4294967295).

### `MSP2_INAV_SET_AUX_RC` and the other new MSP2 commands
The new command `MSP2_INAV_SET_AUX_RC` (0x2230) sets the channels CH13…CH32 on top of the receiver — without a mode, without a mask and without an arming check; it cannot change CH1…CH12 (a frame with a start channel below 13 is rejected). Unlike MSP RC Override it is in no way tied to whether the sender is alive.

**Safety: the override latches.** The values sit in a separate array (`mspAuxOverlay` in `rx/rx.c`) and are overlaid on the receiver channels in every cycle while they are non-zero. There is no timeout. A zero in a frame means “do not change this channel”, so the sender cannot write a zero and thereby give the channel back to the receiver: the array is cleared only by rebooting the flight controller. Any MSP port will accept the command — USB with the Configurator, a Bluetooth bridge, a companion, MSP over the radio link. The consequences:

- a channel that has received a value even once does not respond to the switch on the radio until a reboot: only the last written number is in effect;
- if the device hung, disconnected or lost its link, its last value stays in force — a mode enabled this way on CH13…CH32 will not turn off by itself;
- the only exception is a channel marked in `msp_override_channels` while the `MSP RC OVERRIDE` mode is active: for that time the `SET_AUX_RC` override on it is skipped.

The rule: **keep ARM, the FAILSAFE mode, RTH, MANUAL, the `MSP RC OVERRIDE` switch itself and any other mode that safety depends on, on CH5…CH12.** On CH13…CH32 put only what is harmless to leave on or off until landing: lights, the camera, the OSD layout. If a device that sends this command is connected to an MSP port, consider the channels it writes to as handed over to it for the whole flight.

Two more 9.1 commands for a ground station and a companion: `MSP2_INAV_SET_WP_INDEX` (0x2221) — jump to waypoint N of the active mission (only while armed and in WP mode), `MSP2_INAV_SET_CRUISE_HEADING` (0x2223) — set the heading in hundredths of a degree in Cruise or Course Hold. The missions themselves are in `inav-missions`.

### MSP over radio, Bluetooth and mLRS
- **MSP through the control link.** CRSF carries MSP in the frames 0x7A / 0x7C (request) and 0x7B (reply, chunks of 58 bytes), SmartPort — in its own frames. The input buffer is 96 bytes, and the reply waits for a free telemetry slot. This is how the Lua scripts of the radio work. Whether the Configurator works over this channel through the ELRS Backpack is not described in the INAV tree — not verified.
- **Bluetooth and a Wi-Fi bridge.** For the flight controller this is an ordinary UART with mask 1: the module passes bytes transparently. The baud rate of the MSP field must match the baud rate of the module (often 9600 on the HC-05/06 — check for your module). Configurator 9 can connect over Serial, BLE, TCP and UDP; the BLE code lists modules on the CC2541, Nordic nRF and two SpeedyBee types. A port with a bridge uses one of the three MSP ports.
- **mLRS.** The CLI command `bind_msp_rx <port>` (since 9.1) sends the MSP receiver the bind request `MSP2_RX_BIND` (0x3001); the port is 0…7, and it must be open and configured for MSP.

### Ground stations
| Station | Protocol | What is confirmed by the 9.1.0 tree |
|---|---|---|
| INAV Configurator 9 | MSP | full configuration; Serial, BLE, TCP, UDP |
| mwp (Mission planner for INAV) | MSP, LTM, MAVLink | the tree has only the XML mission schema `docs/development/wp_mission_schema` with the mwp namespace; the capabilities of the application — not verified |
| Mobile apps | MSP over Bluetooth or Wi-Fi | the firmware needs only an MSP port; the capabilities of the apps — not verified |
| QGroundControl, Mission Planner, MAVProxy | MAVLink | telemetry per the table above; no parameters, no arm and mode commands; a mission can be uploaded only with `MISSION_ITEM` messages without `_INT` — which ones a particular station uses was not verified |

### What changed since 8.0
| Was in 8.0.1 | Now in 9.x (present in 9.1.0) |
|---|---|
| CRSF: Attitude, Battery, FM, GPS, Vario | + Baro altitude, Airspeed, RPM, Temperature |
| `FM`: has `AIR` | `AIR` removed; `GEO`, `TURT`, `WRTH`, `LOTR` added |
| SmartPort 470: five digits | seven digits (the digits A and B) |
| MAVLink: HEARTBEAT in the extra2 stream, no `COMMAND_INT` | HEARTBEAT and SYSTEM_TIME once a second, separately; `DO_REPOSITION`; `mavlink_sysid`, `mavlink_autopilot_type` (9.0) |
| MSP RC Override only in a custom build, a 16-bit mask | stock, a 32-bit mask; `MSP2_INAV_SET_AUX_RC` (holds CH13…CH32 until a reboot) |
| — | `bind_msp_rx`, `MSP2_INAV_SET_WP_INDEX`, `MSP2_INAV_SET_CRUISE_HEADING` (9.1) |

### Place in the system
- **Receives:** the UARTs and their baud rates from the port table (`inav-setup-scratch`, `inav-cli-backup`); the position estimate, the battery and the modes from the rest of the firmware; the downlink bandwidth from the radio link (`link-elrs`, `link-telemetry-radios`).
- **Provides:** the sensors and the mode string to the radio (`link-edgetx`); the MAVLink stream to a ground station and a companion (`comp-mavlink`, `mav-protocol`); control channels from MSP and mission waypoints to navigation (`inav-missions`).
- **If you get it wrong here:** an invalid pair of functions on one UART resets the whole port table — the receiver and the GPS are gone, and you end up looking for the cause in them; a fourth MSP port for Bluetooth has the same effect; a safety mode on CH13…CH32 can be latched by any MSP device with the command `MSP2_INAV_SET_AUX_RC`; an override mask with throttle and a permanently enabled mode hand the motor to a script — the consequences show up in `inav-mc-tuning` and failsafe.

## practice
The lab is a calculation exercise: no flight controller and no simulator. All the configurations below are a teaching example assembled by hand, not the output of a real aircraft. The numbers were recomputed with a script using the formulas from the theory.

### Step 1. Decode the port dump
A fixed wing on an F405, six UARTs.

```
serial 20 1 115200 115200 0 115200
serial 0 64 115200 115200 0 115200
serial 1 2 115200 115200 0 115200
serial 2 17 57600 115200 9600 115200
serial 3 288 115200 115200 57600 115200
serial 4 33554433 115200 115200 0 115200
serial 5 1 9600 115200 0 115200
```

Write down for each line: the port, the functions, at what baud rate and when each one works. Find the rule violations and write the corrected lines, keeping Bluetooth on UART6, LTM on UART3 and MAVLink on UART4.

Answer. VCP — MSP. UART1 (64) — the receiver; with CRSF the baud rate is 420000, and the field is not used. UART2 (2) — GPS, 115200. UART3 (17 = 16 + 1) — MSP at 57600 while disarmed and LTM at 9600 while armed: the pair is allowed. UART4 (288 = 256 + 32) — MAVLink and SmartPort: two telemetry protocols on one port, not allowed. UART5 (33554433 = 33554432 + 1) — DisplayPort and MSP: not allowed. UART6 (1) — MSP at 9600, Bluetooth. There are four ports with MSP: VCP, UART3, UART5, UART6 — more than three. The result: three violations, and after `save` and a reboot the whole table is reset to the default. The fix: `serial 3 256 115200 115200 57600 115200` and `serial 4 33554432 115200 115200 0 115200`; three MSP ports remain.

### Step 2. The MAVLink budget
Calculate the nominal budget for three sets and decide whether it fits into the link. The rule: the budget is no more than 80 % of the bandwidth. The bandwidths: SiK on a 57600 UART — the port carries 5760 bytes/s, and by the conditions of the problem half is available for the downlink, 2880 bytes/s (the air time is shared between the two directions); ELRS in MAVLink mode — a 1:2 ratio, the ordinary modes, B = 5, the formula from the CRSF section.

| Set | ext | rc | pos | extra1 | extra2 | extra3 |
|---|---|---|---|---|---|---|
| A, defaults | 2 | 1 | 2 | 2 | 2 | 1 |
| B, for a companion | 2 | 1 | 5 | 10 | 2 | 1 |
| C, economical | 1 | 0 | 1 | 1 | 1 | 1 |

Answer. A: 110 + 54 + 272 + 80 + 64 + 94 + 45 = 719 bytes/s. B: 110 + 54 + 680 + 400 + 64 + 94 + 45 = 1447. C: 55 + 0 + 136 + 40 + 32 + 94 + 45 = 402. The ELRS 1:2 bandwidth: 150 Hz — burst 37, 2921 bit/s, 365 bytes/s; 250 Hz — burst 63, 4921 bit/s, 615 bytes/s; 500 Hz — burst 127, 9921 bit/s, 1240 bytes/s.

| Link | Bandwidth | 80 % | A, 719 | B, 1447 | C, 402 |
|---|---|---|---|---|---|
| SiK 57600 | 2880 | 2304 | yes | yes | yes |
| ELRS 500 Hz | 1240 | 992 | yes | no | yes |
| ELRS 250 Hz | 615 | 492 | no | no | yes |
| ELRS 150 Hz | 365 | 292 | no | no | no |

For 150 Hz you also have to drop extra2 and extra3: 55 + 136 + 40 + 45 = 276 bytes/s. The real rates of set B are below nominal: extra1 = 10 gives 50 / (5 + 1) = 8.33 Hz, pos = 5 — 50 / 11 = 4.55 Hz.

### Step 3. The override mask
1. A companion has to control roll, pitch, yaw and AUX5 (CH9). What is `msp_override_channels`?
2. Decode the mask 4111.
3. The mask is 127, and the `MSP RC OVERRIDE` mode is assigned to AUX3 (CH7). Which channels are actually overridden?
4. `failsafe_delay = 5`. The companion script hung, the radio is connected: after how long do the channels return to the pilot? The radio lost the link, the script keeps sending frames: what happens?

Answer. (1) Bits 0, 1, 2 and 8: 1 + 2 + 4 + 256 = 263. (2) 4111 = 4096 + 15: bits 0…3 and 12 — roll, pitch, yaw, throttle and CH13. (3) Bit 6 is excluded, the effective mask is 63: CH1…CH6. (4) For 200 + 200 + 5 · 100 = 900 ms the channels hold the last value of the script, then return to the pilot. On a loss of the radio failsafe comes after 200 + 500 = 700 ms regardless of the script.

### Step 4. Four aircraft and three errors
Choose the protocol and write down the settings: (a) a fixed wing with ELRS and an EdgeTX radio; (b) FrSky X-series: SBUS on UART1, S.Port on UART3, an F7 board; (c) an antenna tracker through a 9600 baud modem on UART4; (d) a companion on UART5, 115200.

Answer. (a) CRSF: `serial 0 64 …`, `serialrx_provider = CRSF`, `feature TELEMETRY`; there is no separate port function; the telemetry ratio is in the ELRS Lua. (b) SmartPort: `serial 2 32 …`, a wire on TX, `telemetry_inverted = OFF`, `telemetry_halfduplex = ON`; for Lua dashboards `frsky_pitch_roll = ON`. (c) LTM: `serial 3 16 115200 115200 9600 115200`, `ltm_update_rate = NORMAL` — 303 bytes/s with 960 available. (d) MAVLink: `serial 4 256 115200 115200 115200 115200`, `mavlink_version = 2`, the rates per the budget.

Now find three errors in the config of an aircraft that has (b), (c) and (d) all at once:

```
feature -TELEMETRY
serial 0 64 115200 115200 0 115200
serial 2 32 115200 115200 0 115200
serial 3 16 115200 115200 9600 115200
serial 4 256 115200 115200 0 115200
set serialrx_provider = SBUS
set telemetry_inverted = OFF
set telemetry_halfduplex = OFF
set ltm_update_rate = NORMAL
set mavlink_version = 2
```

Answer. (1) `feature -TELEMETRY`: the telemetry task is not started, and all three protocols are silent. (2) `telemetry_halfduplex = OFF` with a single wire on TX: the port is opened as separate lines, the flight controller does not hear the receiver polls, and SmartPort is silent. (3) The MAVLink port has a telemetry baud rate of 0 — that is `AUTO`, 57600, and the companion expects 115200. The LTM line is fine.

### Moving to real hardware
The propellers stay off for all items.
1. Save a `diff all`. Configure one protocol, `save`, after the reboot run `serial` and make sure that the table was not reset.
2. CRSF: on the radio `Discover new`, compare the sensor list with the frame table; switch modes and check the `FM` string.
3. MAVLink: connect a ground station through a USB-UART adapter at the baud rate of the port; the message inspector should show only the messages from the table.
4. MSP RC Override: a mask without bit 3, the mode on a switch; on the Receiver tab the channel follows the script with the switch on and returns to the radio about a second after the script stops.

Self-check: the lab is done when:
- step 1: three violations are named (UART4, UART5, four MSP ports), and both corrected lines match the answer character for character (calculation);
- step 2: you got 719, 1447 and 402 bytes/s, bandwidths of 365, 615 and 1240 bytes/s, and the “yes / no” table matches in all twelve cells (calculation);
- step 3: you got 263, the set “CH1…CH4 and CH13”, an effective mask of 63, times of 900 and 700 ms (calculation);
- step 4: the four sets of settings match in the port function and the key settings, and the three errors from the answer are named (calculation);
- hardware: the port table after a reboot is the one you entered; the sensors and the messages match the tables of the module.

**Reference for the self-check.** The correct result is the numbers above. Typical errors: (1) in step 1 UART3 was called a violation — the pair MSP + LTM is allowed, LTM simply runs only while armed; (2) in step 2 the ELRS bandwidth came out as 375, 625, 1250 — the link statistics slot was forgotten, the factor burst / (burst + 1); (3) in step 3 you got 526 — the bits were counted from one, not from zero; (4) in step 4 the baud rate 115200 in the MSP field of the LTM port was called an error — for LTM only the third baud rate field is read.

## diagnostics
- **Symptom:** after `save` the receiver, the GPS and the OSD are gone, and the Ports tab looks like a factory one
  - Possible cause: an invalid pair of functions on one UART or more than three ports with MSP — the firmware reset the whole table.
  - What to do: restore the `serial` lines from `diff all`; fix the pair by the rules of the section on ports.
- **Symptom:** the radio has only the link sensors (`1RSS`, `RQly`), there are no `RxBt`, `GPS`, `FM`
  - Possible cause: `feature TELEMETRY` is off; the TX wire of the flight controller is not connected to the receiver; the CLI is open.
  - What to do: `feature TELEMETRY`, `save`; on the radio `Delete all` and `Discover new`.
- **Symptom:** the coordinates on the radio are updated once every few seconds
  - Possible cause: the ELRS telemetry ratio `Std` at 250–500 Hz gives less than 10 bytes/s.
  - What to do: set 1:8 or a lower packet rate in the ELRS Lua; recalculate the bandwidth with the formula.
- **Symptom:** a voice alert for the mode stopped triggering after an update to INAV 9
  - Possible cause: the `FM` strings changed: there is no `AIR`, and `LOTR`, `WRTH`, `GEO`, `TURT` appeared.
  - What to do: correct the conditions on the radio using the table of strings.
- **Symptom:** SmartPort is silent on an F7 board
  - Possible cause: `telemetry_halfduplex = OFF`; the wire on RX instead of TX; `telemetry_inverted = ON` without modifying the receiver.
  - What to do: the wire on TX, `telemetry_inverted = OFF`, `telemetry_halfduplex = ON`.
- **Symptom:** LTM or MAVLink on a port shared with MSP runs only in flight
  - Possible cause: that is the design: a shared port is given to telemetry while armed.
  - What to do: dedicate a separate UART or enable `telemetry_switch` and assign the `TELEMETRY` mode.
- **Symptom:** a MAVLink ground station sees the aircraft but does not read parameters, does not arm and does not upload a mission
  - Possible cause: INAV does not handle parameters, `COMMAND_LONG` and `MISSION_ITEM_INT`.
  - What to do: configure through the Configurator over MSP; upload missions over MSP (`inav-missions`).
- **Symptom:** the ground station receives garbage or nothing
  - Possible cause: the telemetry baud rate field is 0 (`AUTO`): MAVLink — 57600, LTM — 19200; the ground station uses a different baud rate.
  - What to do: set the baud rate explicitly in the third baud rate field.
- **Symptom:** a script sends `MSP_SET_RAW_RC`, and the channels do not change
  - Possible cause: the `MSP RC OVERRIDE` mode is not active; the channel is not in the mask or it is the channel of the mode itself; frames less often than 5 a second; less than 0.7 s has passed since the stream started.
  - What to do: check Modes, the mask and the frame rate (50 Hz with a margin).
  - Consequences: with a mask that includes throttle and a permanently active mode the script controls the motor.
- **Symptom:** a switch on CH13 or higher stopped working: the mode is on (or off) regardless of the radio, and on the Receiver tab the channel sits at one value
  - Possible cause: an MSP device (a companion, a script, a ground station) sent `MSP2_INAV_SET_AUX_RC` for this channel. The value is held without a timeout, and a zero in a frame means “do not change” — the sender cannot remove the override, even if it is already disconnected.
  - What to do: reboot the flight controller — there is no other way to clear the override; move the mode to CH5…CH12; find out which device sends the command.
  - Consequences: if ARM, RTH or MANUAL was on such a channel, the pilot loses that switch until a reboot; the aircraft may stay armed after the device fails.
- **Symptom:** a Bluetooth module connects, but the Configurator does not see the flight controller
  - Possible cause: the baud rate of the MSP field does not equal the baud rate of the module; TX and RX are swapped; it is a fourth MSP port.
  - What to do: set the baud rate of the module, check the wires, remove MSP from the extra port.

## checklist
- [ ] A `diff all` is saved before editing the ports
- [ ] No more than two functions on each UART, the pair is an allowed one; no more than three ports with MSP
- [ ] `feature TELEMETRY` is enabled
- [ ] LTM and MAVLink have the telemetry baud rate set explicitly, not `AUTO`
- [ ] The MAVLink budget is calculated and does not exceed 80 % of the link bandwidth
- [ ] The ELRS telemetry ratio is chosen for the coordinate rate you need
- [ ] `msp_override_channels` has no bit 3 unless the script needs the throttle; the mode is on a switch
- [ ] ARM, failsafe, RTH, MANUAL and the `MSP RC OVERRIDE` switch are assigned to CH5…CH12: any MSP device can latch the channels CH13…CH32 with the command `MSP2_INAV_SET_AUX_RC` until a reboot
- [ ] `GCS NAV` is not permanently active
- [ ] After `save` and a reboot `serial` shows what you entered

## references
- INAV 9.1.0 io/serial.h and serial.c (function bits, coexistence rules, baud rates) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/io/serial.c | primary | A
- INAV 9.1.0 settings.yaml (telemetry and MAVLink settings, `msp_override_channels`) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/settings.yaml | primary | A
- INAV 9.1.0 telemetry/crsf.c (frames, schedule, mode strings, MSP) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/telemetry/crsf.c | primary | A
- INAV 9.1.0 telemetry/smartport.c (sensors and their ids) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/telemetry/smartport.c | primary | A
- INAV 9.1.0 telemetry/ltm.c (frames and the three schedules) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/telemetry/ltm.c | primary | A
- INAV 9.1.0 telemetry/mavlink.c (outgoing streams, incoming handlers, flow control) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/telemetry/mavlink.c | primary | A
- INAV 9.1.0 rx/msp_override.c and rx/rx.c (channel override, timeouts) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/rx/msp_override.c | primary | A
- INAV 9.1.0 fc/fc_msp.c (`MSP_SET_RAW_RC`, `MSP2_INAV_SET_AUX_RC`, `SET_WP_INDEX`, `SET_CRUISE_HEADING`) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/fc_msp.c | primary | A
- INAV 9.1.0 fc/cli.c (`serial`, `bind_msp_rx`) | https://github.com/iNavFlight/inav/blob/9.1.0/src/main/fc/cli.c | primary | A
- INAV 9.1.0 docs/Telemetry.md (connecting SmartPort, LTM; the MAVLink section is outdated, see notes) | https://github.com/iNavFlight/inav/blob/9.1.0/docs/Telemetry.md | primary | B
- INAV 9.1.0 docs/Serial.md (the port function table) | https://github.com/iNavFlight/inav/blob/9.1.0/docs/Serial.md | primary | B
- INAV Configurator 9 serialPortHelper.js (function names and baud rate lists of the Ports tab) | https://github.com/iNavFlight/inav-configurator/blob/master/js/serialPortHelper.js | primary | B
- ExpressLRS 4.1.0 TXModuleParameters.cpp and common.cpp (the telemetry bandwidth calculation) | https://github.com/ExpressLRS/ExpressLRS/blob/4.1.0/src/lib/tx-crsf/TXModuleParameters.cpp | primary | B
- MAVLink common message set (message lengths) | https://mavlink.io/en/messages/common.html | primary | B

## notes
The firmware was not built or run: running INAV SITL is not available in this environment, and all the behavior was obtained by reading the INAV 9.1.0 source and comparing it with 8.0.1. Not verified on hardware: the real rates of the MAVLink streams, the behavior after the first `RADIO_STATUS`, the hold time of the overridden channels (0.9 s is a calculation from the constants of the code).

Discrepancies between the documentation and the code in the 9.1.0 tag: `docs/Telemetry.md` calls MAVLink “transmit-only” although the handler accepts missions, `DO_REPOSITION`, `RC_CHANNELS_OVERRIDE` and `RADIO_STATUS`; the same file lists “FrSky” among the protocols, but bit 2 in `io/serial.h` is marked as unused (in the port function list of Configurator 9, `serialPortHelper.js`, the entry `TELEMETRY_FRSKY` nevertheless remains). The comment on the CRSF Airspeed frame says “dm/s”, while the formula in the code gives 0.1 km/h.

The ELRS bandwidth was computed with the formula ELRS 4.1.0 itself uses to show the number in the Lua; the throughput of MAVLink mode was not measured. Half of the UART bandwidth for SiK is a condition of the problem, not a property of the modem. The MAVLink message lengths are taken from the library in the INAV 9.1.0 tree (`lib/main/MAVLink/common`) as maximums.

The capabilities of mwp, mobile apps, QGroundControl, Mission Planner and MAVProxy lie outside the INAV tree and were not verified here: the ground station table states only what follows from the code of the firmware and the Configurator.
