---
id: link-telemetry-radios
title: "Telemetry radios: SiK, RFD900, ELRS MAVLink, IP radios and LTE"
level: L2
readingTime: 30 min
firmware: ArduPilot 4.5+ (checked against 4.7.3) · PX4 1.18 (parameters checked against v1.18.0) · SiK 2.x
status: published
tags:
  - telemetry
  - SiK
  - RFD900
  - telemetry radio
related:
  - link-elrs
  - rf-link-budget
  - mav-routing
  - rf-antennas
next:
  - mav-routing
source: content/link/link-telemetry-radios.md
source_hash: 3331c85ab268
---

## summary
The RC link controls the aircraft; telemetry connects it to the ground station: map, mission, parameters, warnings. On a 5" quad ELRS telemetry is enough; an aircraft flying a mission several kilometers out needs a MAVLink link with known range, throughput and diagnostics. This module covers the SiK family (433/868/915 MHz, 100 mW) and the RFD900 (up to 1 W), configuring them with AT commands and what each parameter means, `RADIO_STATUS` and fade margin, ELRS in MAVLink mode, IP radios and mesh for multiple aircraft and video, LTE for beyond-the-horizon flights, and how to choose a link for the job.

## theory
### What you need from telemetry
- **Throughput.** A typical set of ArduPilot MAVLink streams is a few kilobytes per second; parameter and mission downloads come in bursts. 64 kbit/s over the air (≈ 8 KB/s) is plenty; 2–8 kbit/s is enough only for a minimal set of messages.
- **Range** is set by the link budget (the "Radio link budget and range" module): power, antennas, frequency, receiver sensitivity. Sensitivity improves as the air data rate goes down, by roughly 3 dB for every halving; 6 dB of margin is twice the range.
- **Latency and duplex.** SiK is time-division (TDM): the transmitters take turns, and latency is tens of milliseconds. That matters for real-time control (a joystick over telemetry), not for missions.
- **Legality.** 433, 868 and 915 MHz have different power and duty-cycle rules in different regions; you configure the radio for your country (`MIN_FREQ`, `MAX_FREQ`, `TXPOWER`, `DUTY_CYCLE`).

### SiK: the parameters you need to understand
SiK firmware runs on most "3DR/Holybro telemetry" radios and on the RFD900x (its own branch). You configure it in Mission Planner (SiK Radio) or by hand: `+++` with a one-second pause before and after → `OK`, `ATI5` lists the parameters, `ATSn=x` writes one, `AT&W` saves, `ATZ` reboots; `RT` instead of `AT` does the same on the remote radio.

| Register | Parameter | Meaning |
|---|---|---|
| S1 | `SERIAL_SPEED` | UART speed in "one-byte form" (57 = 57600); the flight controller uses the same |
| S2 | `AIR_SPEED` | air data rate, kbit/s; 64 by default, lower means farther but slower |
| S3 | `NETID` | network ID, the same on both radios of a pair, different on neighboring aircraft |
| S4 | `TXPOWER` | power, dBm (20 = 100 mW on SiK; up to 30 = 1 W on the RFD900x) |
| S5 | `ECC` | error-correcting code: halves the useful throughput, not recommended |
| S6 | `MAVLINK` | 1 = MAVLink packet framing and `RADIO_STATUS` injection; 2 = in SiK 1.9 also RC_OVERRIDE priority; in 2.x (with MAVLink2 support) that mode was removed and 2 behaves like 1 |
| S8/S9 | `MIN_FREQ`/`MAX_FREQ` | frequency range, kHz, per your country's rules |
| S10 | `NUM_CHANNELS` | number of frequency-hopping channels (FHSS) |
| S11 | `DUTY_CYCLE` | share of time spent transmitting, %; 100 if the rules set no limit |
| S15 | `MAX_WINDOW` | TDM window, ms; smaller means lower latency and lower throughput |

Both sides must match in `AIR_SPEED`, `NETID`, `ECC`, `MIN/MAX_FREQ`, `NUM_CHANNELS`, or the radios will not link.

Where to start with `NUM_CHANNELS` and `MAX_WINDOW`: at the firmware defaults. `MAX_WINDOW` = 131 ms is both the default and the maximum (anything larger does not fit the 13-bit field, SiK `Firmware/radio/parameters.c`); lower it only for lower latency (a joystick, RC_OVERRIDE), and then check that the telemetry stream in the GCS has not dropped. Change `NUM_CHANNELS` only if your country's rules require a different number of hopping channels for FHSS in the chosen band; set both radios the same.

{{diagram:chart-sik-airspeed|Relative SiK range versus air data rate: going from 64 to 16 kbit/s gives about 6 dB and roughly twice the range.}}

### RADIO_STATUS and fade margin
With `MAVLINK = 1` the radio injects the `RADIO_STATUS` message (id 109) into the stream: `rssi`, `remrssi` (signal strength at the local and remote end), `noise`, `remnoise`, `txbuf` (free space in the transmit buffer, %), error counters. ArduPilot lowers the stream rates by itself based on `txbuf` if the link cannot keep up, which is why `SERIAL_SPEED` can be higher than what the air link carries.
- Converting RSSI to dBm (approximately): dBm ≈ RSSI / 1.9 − 127.
- **Fade margin** ≈ (RSSI − noise) / 2, dB. Every 6 dB of margin is a twofold range margin: 18 dB at the test distance ≈ ×8.
- The 1 m test: RSSI on both sides above ~190 on a standard SiK (a course guideline, not a SiK specification); less means a damaged antenna or radio.

### Other options
- **RFD900x/ux**: the same SiK logic, 900 MHz, up to 1 W, diversity antennas; for long-range planes and VTOLs. More power also means stricter requirements for the supply (pulse current) and for antenna separation from the GNSS.
- **ELRS in MAVLink mode** (since ELRS 3.5; in 4.x the receiver output switches to MAVLink by itself when `Link Mode = MAVLink`, and Gemini doubles the telemetry bandwidth): RC and MAVLink telemetry over one link; telemetry reaches the ground station through the TX Backpack over Wi-Fi (UDP 14550) or over the transmitter's own USB (460800). The upside is one radio link and ELRS range; the downside is narrow telemetry bandwidth, so the streams are trimmed. In ArduPilot the receiver port gets `SERIALn_PROTOCOL = 2`, `SERIALn_BAUD = 460`, `RSSI_TYPE = 5`, and this port's stream rates are 1 Hz; receiver and transmitter run ELRS 3.5.0+ of the same major version (checked against 4.1.0), TX Backpack 1.5.0+ (details on the MAVLink page of the ELRS documentation).
- **Herelink and similar all-in-one units**: RC, HD video and telemetry in one handset with an Android ground station.
- **IP radios and mesh** (Microhard, Doodle Labs, Silvus and others): an Ethernet bridge over radio: MAVLink over UDP, video, SSH to the companion computer, several aircraft on one network. Expensive, but the standard for serious systems; routing is in the `mav-routing` module.
- **LoRa**: very long range at a few kbit/s; fine for a minimal set (position, status), not for parameters and missions.
- **LTE/4G**: beyond-the-horizon links over a carrier network (the "Cellular bridge" project): range is limited by coverage, latency is 50–200 ms with unpredictable dropouts; you need a VPN or a relay because of NAT, and a link-loss failsafe is mandatory.

### MAVLink over the ELRS Backpack via Wi-Fi
The chain: flight controller UART (MAVLink2, 460800) → ELRS receiver → the ELRS air link (in MAVLink mode the telemetry ratio is forced to 1:2) → TX module → TX Backpack → Wi-Fi → UDP 14550 → ground station. The bottleneck is not Wi-Fi but the ELRS air link: downlink telemetry takes the response slots, and uplink MAVLink shares packets with the RC channels. The module's USB is a second path to the ground station, but a radio's internal module does not have one, so only the Backpack remains.

Air link capacity per the MAVLink page of the ELRS documentation (developers' estimates, documentation version of 2026-11-09):

| Mode | Down, B/s | Down with Gemini | Up with RC |
|---|---|---|---|
| F1000 (2.4 GHz) | ~2375 | ~4755 | ~1190 |
| 333Hz Full | ~1470 | ~2935 | ~735 |
| 250Hz | ~590 | ~1175 | ~300 |
| 50Hz | ~110 | ~225 | ~60 |
| 200Hz Full (900 MHz, LR1121) | ~880 | ~1760 | ~445 |

For comparison: SiK at `AIR_SPEED = 64` tops out at around 8 KB/s of raw air rate for both directions together (the useful stream is less), roughly 5 times the downlink of 333Hz Full.

Procedure:
1. **Versions.** ELRS ≥ 3.5.0 on the module and the receiver, TX Backpack ≥ 1.5.0; both devices ESP-based (`link-elrs`).
2. **Enabling.** In the Lua script: `Link Mode = MAVLink` with the receiver off; `Backpack → Telemetry = WiFi`. Not the `Enable Backpack WiFi` item: that one puts the Backpack into firmware update mode.
3. **Ground station.** Network `ExpressLRS TX Backpack XXXXXX`, password `expresslrs`, UDP 14550. The access point's range is 5–10 m: keep the laptop or tablet next to the radio. The firewall must not block UDP.
4. **Speed for the job.** Transfer time: t = N × L / B. A `PARAM_VALUE` message in MAVLink2 is 25 bytes of payload + 12 of overhead = 37 bytes. For N = 1000 parameters (an estimate; the exact number is the `param_count` field): F1000 15.6 s, 333Hz Full 25.2 s, 250Hz 62.7 s, 50Hz 336 s (5.6 min), not counting retries. Hence the ELRS documentation's rule: download parameters and upload the mission at F1000/K1000 or 333Hz Full on the ground, then switch to the flight mode.
5. **Streams.** The receiver port's `MAVn_*` = 1 Hz, except `MAVn_ADSB`, `MAVn_PARAMS` and `MAVn_RAW_CTRL` = 0.

{{diagram:chart-elrs-param-download|Download time is proportional to the number of parameters (parallel lines on log axes): 1000 parameters take 15.6 s at F1000 and 336 s at 50Hz, which is why parameters are downloaded in a fast mode on the ground.}}

How to check: the ground station connected over UDP and downloaded the parameters in about the t from step 4; in `RADIO_STATUS` the `txbuf` field does not sit at zero. The `rssi` field here is LQ × 2.55 (ELRS 4.1.0 source, `SerialMavlink.cpp`), and `remrssi` is the RSSI of the receiver's antenna 1 in dBm with the minus sign dropped (85 = −85 dBm); the SiK formula "dBm ≈ RSSI / 1.9 − 127" does not apply to ELRS. The Backpack transmits in 2.4 GHz next to the control link; at races, forwarding is turned off.

### A PX4 flight controller port for a telemetry radio
PX4 1.18 (checked against `mavlink/module.yaml` and `Tools/serial/generate_config.py` v1.18.0). A SiK radio goes on TELEM1: that is the port of MAVLink instance 0, and it is enabled by default.

| Parameter | Default | What it sets | Decision |
|---|---|---|---|
| `MAV_0_CONFIG` | TELEM 1 (101) | which port instance 0 runs on | radio on TELEM2: `MAV_1_CONFIG` = TELEM 2 (default 0 = Disabled), and the parameters below with `MAV_1_` |
| `SER_TEL1_BAUD` | 57600 | the port's UART speed | equal to the radio's `SERIAL_SPEED` (S1 = 57) |
| `MAV_0_RATE` | 1200 B/s | the ceiling of the total MAVLink stream in bytes per second, not the port speed; 0 = baud / 20 | no higher than the air link's useful throughput: SiK at `AIR_SPEED` 64 can use 0 (57600 / 20 = 2880 B/s); ELRS 250Hz (~590 B/s down) 500 |
| `MAV_0_RADIO_CTL` | 1 (on) | throttle the stream rates by `txbuf` from `RADIO_STATUS` | leave it at 1; it works only if the radio sends `RADIO_STATUS` (`MAVLINK` = 1 on SiK) |
| `MAV_0_MODE` | 0 Normal | the set of streams | a narrow link (LoRa, ELRS at a low packet rate): 13 Low Bandwidth (since 1.16) or 7 Minimal |

All five are read when MAVLink starts: reboot after a change. Check: in the MAVLink Console, `mavlink status` for the instance on the right device shows `tx rate max` equal to `MAV_0_RATE` (or baud / 20 with 0), `tx` no higher than that, `type: RADIO Link` (the radio sends `RADIO_STATUS`; otherwise `MAV_0_RADIO_CTL` is useless), and `txbuf` not sitting at zero. Port numbers on a specific board and the second MAVLink instance are in `px4-hardware-peripherals`.

### How to choose
| Job | Link |
|---|---|
| Missions within 1–3 km, a simple ground station | SiK 100 mW, `AIR_SPEED` 64 |
| A long-range plane, 10+ km | RFD900x, a directional antenna on the ground, a lower `AIR_SPEED` |
| FPV/small aircraft, one radio link | ELRS in MAVLink mode |
| Video + telemetry + several aircraft | IP radio / mesh |
| Beyond the horizon, within coverage | LTE + VPN, a backup radio link |

Redundancy: two independent telemetry links (for example SiK + LTE) on different flight controller ports, so the ground station sees the aircraft through either one.

### Where it fits in the system

- **Takes in:** the MAVLink stream from a flight controller port; the link budget: power, antennas, frequency, sensitivity (`rf-link-budget`, `rf-antennas`); for MAVLink mode, the ELRS link (`link-elrs`).
- **Puts out:** the map, parameters and mission to the ground station; `RADIO_STATUS` with RSSI, noise and `txbuf`, which ArduPilot uses to lower the stream rates; a link for several participants on the network (`mav-routing`).
- **If you get this wrong:** `AIR_SPEED`, `NETID` or the frequency range differ between the two radios → no link, and it looks like a misconfigured flight controller port. `AIR_SPEED` lowered for range without regard to the traffic → the air link cannot keep up, `txbuf` drops, the streams get trimmed. A powerful RFD900x without antenna separation from the GNSS → interference with the satellite receiver (`el-emi`, `est-gnss`).

## practice
### Step 1. Setting up a SiK pair
Connect the radio to a computer (USB-UART or through Mission Planner). Read `ATI5` of the local radio and `RTI5` of the remote one. Write down the parameter table; set a `NETID` unique to your aircraft and the frequency range per your country's rules. `AT&W`, `ATZ` on both (the remote first: `RT&W`, `RTZ`).

### Step 2. The 1 m test and RADIO_STATUS
Radios one meter apart: RSSI on both sides. Connect to the flight controller (or SITL through the radio), find `RADIO_STATUS` in the MAVLink inspector, record `rssi`, `remrssi`, `noise`, `txbuf`. Convert RSSI to dBm and compute the fade margin.

### Step 3. Range margin
On the ground, separate the radios by 100–200 m (or block line of sight). Record RSSI, noise and fade margin. Estimate the range with a 6–10 dB margin for antenna turns and interference (a course guideline; it is less than the 10–15 dB for RC in `rf-link-budget` because telemetry does not control the aircraft: losing it does not bring the aircraft down unless a GCS failsafe is set on it; if one is, or the link carries control, use the RC margin). Repeat with `AIR_SPEED = 32` on both ends; compare with the model (+3 dB per halving).

### Step 4. Link load
A pymavlink script counts bytes per second and prints the free space in the `RADIO_STATUS.txbuf` buffer:
```python
from pymavlink import mavutil
import time
m = mavutil.mavlink_connection("/dev/ttyUSB0", baud=57600); m.wait_heartbeat()
t0, nbytes = time.time(), 0
while time.time() - t0 < 30:
    msg = m.recv_match(blocking=True, timeout=1)
    if msg is None:
        continue
    nbytes += len(msg.get_msgbuf())
    if msg.get_type() == "RADIO_STATUS":
        print(f"rssi {msg.rssi} rem {msg.remrssi} noise {msg.noise} buffer free {msg.txbuf}%")
print(f"{nbytes / 30 / 1024:.1f} KB/s down")
```
Compare the stream with the throughput of your `AIR_SPEED`. Download the parameters: how does the free space in `txbuf` drop?

Self-check: the lab is done when the radio pair is set up with a unique `NETID` and a frequency range per your country's rules (`ATI5` and `RTI5` match in `AIR_SPEED`, `NETID`, `ECC`, `MIN/MAX_FREQ`, `NUM_CHANNELS`), `RADIO_STATUS` has been read and converted to dBm (RSSI / 1.9 − 127) and to fade margin ((RSSI − noise) / 2), RSSI on both sides at 1 m is above ~190 (the course guideline), the distance test has been done at two `AIR_SPEED` values and compared with the model, and the measured stream in KB/s is written next to the air link throughput.

**Reference answer for self-check.** Checking the formulas: RSSI 190 is −27 dBm; 18 dB of margin at the test distance is roughly ×8 in range. Going from `AIR_SPEED` 64 to 32 should raise the margin by about 3 dB; a normal MAVLink stream is a few KB/s against a ceiling of about 8 KB/s at 64 kbit/s, and during a parameter download `txbuf` drops. RSSI noticeably below 190 at 1 m (the course guideline) means a damaged antenna or radio, and measuring further is pointless. The remote radio does not answer `RTI5` after a parameter change: the pair has diverged in `AIR_SPEED`, `NETID` or frequencies; change the remote first (`RT&W`, `RTZ`), then the local one.

## diagnostics
- **Symptom:** the radios do not link (green LED blinking)
  - Possible cause: `NETID`, `AIR_SPEED`, `ECC`, the frequency range or the number of channels do not match.
  - What to do: `ATI5` and `RTI5`, align them, `AT&W`, `ATZ` on both.
- **Symptom:** the link is up, the ground station gets no data
  - Possible cause: the radio's `SERIAL_SPEED` does not match the flight controller port speed, the port is not set to MAVLink, TX/RX are swapped.
  - What to do: check the port speed and protocol (`SERIALn_BAUD`, `SERIALn_PROTOCOL`) and the wiring.
- **Symptom:** telemetry drops out at a few hundred meters
  - Possible cause: a small fade margin, antennas with different polarization or shadowed by the airframe, interference from the video transmitter or a nearby GNSS.
  - What to do: RSSI/noise from `RADIO_STATUS`, vertical antennas on both sides, move the antenna out from under the frame, lower `AIR_SPEED`.
- **Symptom:** parameters and the mission take very long to load
  - Possible cause: a narrow link (low `AIR_SPEED`, ECC on), the link busy with streams.
  - What to do: turn ECC off, load on the ground, lower the stream rates (`MAVn_*` in ArduPilot 4.7, numbered from 1: MAV1 is the former SR0; before 4.7, `SRn_*`).
- **Symptom:** two aircraft see each other's telemetry
  - Possible cause: the same `NETID`.
  - What to do: a unique `NETID` for each pair, different aircraft sysids (`MAV_SYSID`, before 4.7 `SYSID_THISMAV`; in PX4 `MAV_SYS_ID`).
- **Symptom:** the laptop is connected to the Backpack's Wi-Fi, but the ground station gets nothing on UDP 14550
  - Possible cause: the Backpack was switched on with `Enable Backpack WiFi` (firmware update mode) instead of `Backpack → Telemetry = WiFi`; the Backpack is older than 1.5.0; a firewall blocks UDP; the receiver is off and there is no link.
  - What to do: `Telemetry = WiFi` in the Lua script, update the Backpack, allow UDP, check the `C` in the corner of the Lua script (module and receiver connected).

## references
- ArduPilot — SiK telemetry radio | https://ardupilot.org/copter/docs/common-sik-telemetry-radio.html | primary | A
- ArduPilot — SiK radio advanced configuration | https://ardupilot.org/copter/docs/common-3dr-radio-advanced-configuration-and-technical-information.html | primary | A
- SiK firmware (source) | https://github.com/ArduPilot/SiK | primary | A
- MAVLink — RADIO_STATUS | https://mavlink.io/en/messages/common.html#RADIO_STATUS | primary | A
- ExpressLRS — MAVLink | https://www.expresslrs.org/software/mavlink/ | primary | B
- ExpressLRS 4.1.0, source `src/src/rx-serial/SerialMavlink.cpp` (RADIO_STATUS fields) | https://github.com/ExpressLRS/ExpressLRS/blob/4.1.0/src/src/rx-serial/SerialMavlink.cpp | primary | A
- MAVLink — PARAM_VALUE (25 bytes of payload) | https://mavlink.io/en/messages/common.html#PARAM_VALUE | primary | A

## checklist
- I know what throughput and range telemetry needs
- I set up a SiK pair with AT commands and understand each key parameter
- I read `RADIO_STATUS`, convert RSSI to dBm and compute fade margin
- I understand the trade of air data rate for range
- I compute parameter download time over ELRS with t = N × L / B and know that `rssi` in `RADIO_STATUS` from ELRS is LQ
- I choose between SiK, RFD900, ELRS MAVLink, IP radio and LTE for the job
