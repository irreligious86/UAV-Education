---
id: link-telemetry-radios
title: "Telemetry Radio Modems: SiK, RFD900, ELRS MAVLink, IP Radios and LTE"
level: L2
readingTime: 30 min
firmware: ArduPilot 4.5+ · PX4 1.15+ · SiK 2.x
status: published
tags:
  - telemetry
  - SiK
  - RFD900
  - radio modem
related:
  - link-elrs
  - rf-link-budget
  - mav-routing
  - rf-antennas
next:
  - mav-routing
source: content/link/link-telemetry-radios.md
source_hash: 523021309862
---

## summary
The RC link controls the vehicle, while telemetry connects it to the ground station: map, mission, parameters, warnings. On a 5" ELRS telemetry is enough; a vehicle flying a mission several kilometers out needs a MAVLink channel with known range, throughput and diagnostics. This module covers the SiK family (433/868/915 MHz, 100 mW) and RFD900 (up to 1 W), setting them up with AT commands and what each parameter means, `RADIO_STATUS` and fade margin, ELRS in MAVLink mode, IP radios and mesh for multiple vehicles and video, LTE for beyond-the-horizon flights — and how to pick a channel for the job.

## theory
### What you need from telemetry
- **Throughput.** A typical set of ArduPilot MAVLink streams is a few kilobytes per second; parameter and mission uploads are bursts. 64 kbit/s over the air (≈ 8 KB/s) is plenty, 2–8 kbit/s is enough only for a minimal set of messages.
- **Range** is set by the link budget (the “Radio Link Budget” module): power, antennas, frequency, receiver sensitivity. Sensitivity improves as you lower the air data rate — roughly 3 dB for every halving; 6 dB of margin means twice the range.
- **Latency and duplex.** SiK is time-division (TDM): the transmitters take turns, latency is tens of milliseconds. For real-time control (a joystick over telemetry) this matters, for missions it doesn't.
- **Legality.** 433, 868 and 915 MHz have different power and duty-cycle rules in different regions; you configure the modem for your country (`MIN_FREQ`, `MAX_FREQ`, `TXPOWER`, `DUTY_CYCLE`).

### SiK: the parameters you need to understand
SiK firmware runs on most “3DR/Holybro telemetry radios” and on the RFD900x (its own branch). Set it up in Mission Planner (SiK Radio) or by hand: `+++` with a one-second pause before and after → `OK`, `ATI5` — list the parameters, `ATSn=x` — write one, `AT&W` — save, `ATZ` — reboot; `RT` instead of `AT` does the same for the remote modem.

| Register | Parameter | Meaning |
|---|---|---|
| S1 | `SERIAL_SPEED` | UART baud rate in “one-byte form” (57 = 57600); the same on the flight controller |
| S2 | `AIR_SPEED` | air data rate, kbit/s; 64 by default, lower means farther but slower |
| S3 | `NETID` | network ID, identical within a pair; different for neighboring vehicles |
| S4 | `TXPOWER` | power, dBm (20 = 100 mW on SiK; up to 30 = 1 W on RFD900x) |
| S5 | `ECC` | error-correcting code: halves the useful data rate, not recommended |
| S6 | `MAVLINK` | 1 — aligns to MAVLink packets and injects `RADIO_STATUS`; 2 — also prioritizes RC_OVERRIDE |
| S8/S9 | `MIN_FREQ`/`MAX_FREQ` | frequency range, kHz — per your country's rules |
| S10 | `NUM_CHANNELS` | number of frequency-hopping (FHSS) channels |
| S11 | `DUTY_CYCLE` | share of time spent transmitting, %; 100 if the rules don't limit it |
| S15 | `MAX_WINDOW` | TDM window, ms; smaller means lower latency and lower throughput |

Both sides must match in `AIR_SPEED`, `NETID`, `ECC`, `MIN/MAX_FREQ`, `NUM_CHANNELS`, otherwise the modems won't link.

{{diagram:chart-sik-airspeed|Relative SiK range versus air data rate: going from 64 down to 16 kbit/s gains about 6 dB and roughly twice the range.}}

### RADIO_STATUS and fade margin
With `MAVLINK = 1` the modem injects the `RADIO_STATUS` message (id 109) into the stream: `rssi`, `remrssi` (signal at the local and remote end), `noise`, `remnoise`, `txbuf` (free space in the transmit buffer, %), error counters. ArduPilot uses `txbuf` to lower stream rates on its own when the link can't keep up — which is why `SERIAL_SPEED` can be higher than what the air link carries.
- Converting RSSI to dBm (approximately): dBm ≈ RSSI / 1.9 − 127.
- **Fade margin** ≈ (RSSI − noise) / 2, dB. Every 6 dB of margin is a twofold range reserve: 18 dB at the test distance ≈ ×8.
- 1 m test: RSSI on both sides above ~190 on a standard SiK; lower means a damaged antenna or modem.

### Other options
- **RFD900x/ux** — the same SiK logic, 900 MHz, up to 1 W, diversity antennas; for long-range planes and VTOL. More power also means tougher requirements on the power supply (pulse current) and on antenna separation from the GNSS.
- **ELRS in MAVLink mode** (ELRS 3.5+) — RC and MAVLink telemetry over one link; telemetry reaches the GCS through the TX Backpack over Wi-Fi (UDP 14550) or over the transmitter's own USB (460800). Pro: one radio channel and ELRS range; con: a narrow telemetry pipe, so streams get trimmed. In ArduPilot, the receiver port: `SERIALn_PROTOCOL = 2`, `SERIALn_BAUD = 460`, `RSSI_TYPE = 5`, stream rates for that port — 1 Hz; receiver and transmitter on ELRS 3.5.0+, TX Backpack 1.5.0+ (details on the MAVLink page of the ELRS documentation).
- **Herelink and similar “all-in-one” systems** — RC, HD video and telemetry in one radio with an Android GCS.
- **IP radios and mesh** (Microhard, Doodle Labs, Silvus and others) — an Ethernet bridge over radio: MAVLink over UDP, video, SSH to the companion, several vehicles on one network. Expensive, but the standard for serious systems; routing is covered in the `mav-routing` module.
- **LoRa** — very long range at a few kbit/s: fine for a minimal set (position, status), not for parameters and missions.
- **LTE/4G** — beyond-the-horizon link through a carrier network (the “Cellular Bridge” project): range is limited by coverage, latency is 50–200 ms with unpredictable dropouts; you need a VPN or a relay because of NAT, and a mandatory link-loss failsafe.

### How to choose
| Task | Channel |
|---|---|
| Missions within 1–3 km, simple GCS | SiK 100 mW, `AIR_SPEED` 64 |
| Long-range plane, 10+ km | RFD900x, directional antenna on the ground, lower `AIR_SPEED` |
| FPV/small vehicle, a single radio channel | ELRS in MAVLink mode |
| Video + telemetry + several vehicles | IP radio / mesh |
| Beyond the horizon, within coverage | LTE + VPN, backup radio channel |

Redundancy: two independent telemetry channels (e.g. SiK + LTE) on different flight controller ports — the GCS sees the vehicle through either one.

## practice
### Step 1. Setting up a SiK pair
Connect the modem to the computer (USB-UART or through Mission Planner). Read `ATI5` of the local and `RTI5` of the remote one. Write down the parameter table; set a `NETID` unique to your vehicle and the frequency range per your country's rules. `AT&W`, `ATZ` on both (remote first: `RT&W`, `RTZ`).

### Step 2. 1 m test and RADIO_STATUS
Modems one meter apart: RSSI on both sides. Connect to the flight controller (or SITL through the modem), find `RADIO_STATUS` in the MAVLink inspector, write down `rssi`, `remrssi`, `noise`, `txbuf`. Convert RSSI to dBm, calculate the fade margin.

### Step 3. Range margin
On the ground, move the modems 100–200 m apart (or block the line of sight). Write down RSSI, noise and the fade margin. Estimate the range while keeping 6–10 dB in reserve for antenna orientation changes and interference. Repeat with `AIR_SPEED = 32` on both ends; compare with the model (+3 dB per halving).

### Step 4. Link load
A pymavlink script counts bytes per second and prints the free buffer space `RADIO_STATUS.txbuf`:
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
Compare the stream with the throughput of your `AIR_SPEED`. Download the parameters — how far does the free space in `txbuf` drop?

The lab is complete when the modem pair is configured with a unique `NETID` and a frequency range per your country's rules, `RADIO_STATUS` has been read and converted to dBm and fade margin, the distance test has been done at two `AIR_SPEED` values with a conclusion, and the link load has been measured.

## diagnostics
- **Symptom:** the modems won't link (green LED blinking)
  - Possible cause: mismatched `NETID`, `AIR_SPEED`, `ECC`, frequency range or number of channels.
  - What to do: `ATI5` and `RTI5`, make them match, `AT&W`, `ATZ` on both.
- **Symptom:** the link is up, but the GCS gets no data
  - Possible cause: the modem's `SERIAL_SPEED` doesn't match the flight controller port's baud rate, the port isn't set to MAVLink, TX/RX are swapped.
  - What to do: check the port baud rate and protocol (`SERIALn_BAUD`, `SERIALn_PROTOCOL`) and the wiring.
- **Symptom:** telemetry drops out at a few hundred meters
  - Possible cause: low fade margin, antennas with different polarization or shadowed by the airframe, interference from the video transmitter or a nearby GNSS.
  - What to do: RSSI/noise from `RADIO_STATUS`, vertical antennas on both sides, move the antenna out from under the frame, lower `AIR_SPEED`.
- **Symptom:** parameters and missions take very long to load
  - Possible cause: a narrow channel (low `AIR_SPEED`, ECC enabled), the channel is busy with streams.
  - What to do: turn ECC off, load on the ground, lower stream rates (`MAVn_*` in ArduPilot 4.7, numbered from 1: MAV1 is the former SR0; before 4.7 — `SRn_*`).
- **Symptom:** two vehicles see each other's telemetry
  - Possible cause: the same `NETID`.
  - What to do: a unique `NETID` for each pair, different vehicle sysids (`MAV_SYSID`, before 4.7 — `SYSID_THISMAV`; in PX4 — `MAV_SYS_ID`).

## references
- ArduPilot — SiK telemetry radio | https://ardupilot.org/copter/docs/common-sik-telemetry-radio.html | primary | A
- ArduPilot — SiK radio advanced configuration | https://ardupilot.org/copter/docs/common-3dr-radio-advanced-configuration-and-technical-information.html | primary | A
- SiK firmware (source) | https://github.com/ArduPilot/SiK | primary | A
- MAVLink — RADIO_STATUS | https://mavlink.io/en/messages/common.html#RADIO_STATUS | primary | A
- ExpressLRS — MAVLink | https://www.expresslrs.org/software/mavlink/ | primary | B

## checklist
- I know what throughput and range telemetry requires
- I set up a SiK pair with AT commands and understand every key parameter
- I read `RADIO_STATUS`, convert RSSI to dBm and calculate the fade margin
- I understand the trade-off between air data rate and range
- I choose between SiK, RFD900, ELRS MAVLink, IP radio and LTE for the job
