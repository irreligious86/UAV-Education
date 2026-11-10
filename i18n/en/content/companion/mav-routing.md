---
id: mav-routing
title: "MAVLink routing and transport: radio, 4G, multiple GCSs"
level: L3
readingTime: 45 min
firmware: ArduPilot · PX4
status: published
added: 2026-11-08
tags:
  - MAVLink
  - routing
  - mavlink-router
  - SiK
  - 4G
related:
  - mav-services
  - comp-raspberry
  - rf-link-budget
next:
  - mav-component
source: content/companion/mav-routing.md
source_hash: a32d46f7ef51
---

## summary
As soon as more than one participant is connected to a vehicle — a GCS over radio, a companion, a second GCS over 4G, a camera — the question comes up of who receives which packets. MAVLink has no “network layer”: routing relies on sysid/compid conventions and on tables that each node builds from the packets it has seen. This module goes through these rules using the ArduPilot source code, the tools (mavlink-router, MAVProxy, mavp2p), the transports (UART, UDP, TCP, SiK radio, 4G/LTE through NAT and VPN), and the link metrics — latency, loss, jitter — measuring them under artificial impairment with `tc netem`. Lab: a router with three clients and a heartbeat RTT measurement as the network degrades.

## theory
### Addressing: sysid and compid
- **sysid** — a vehicle or a station. Vehicles: 1…250 (unique on one network!), the GCS is usually 255 (a second one — 254 and so on).
- **compid** — a component within a system: autopilot 1, cameras 100–105, gimbal 154, onboard computer 191–194, peripherals 158, GCS application 190. Your own script on the companion gets its own compid in the same system as the autopilot.
- A message can have `target_system`/`target_component` fields (addressed) or not have them (telemetry — broadcast by nature). target 0 means “everyone.”

### Forwarding rules (as in ArduPilot)
The source file `libraries/GCS_MAVLink/MAVLink_routing.cpp` states the rules explicitly. The autopilot handles a packet itself if it has no target, has target_system 0, or is addressed to it. And it forwards it to **another** port if:
1. the message has no target_system, or target_system = 0;
2. target_system is someone else's, and packets from that sysid have already been seen on that port;
3. target_system is its own, there is a target_component, and packets from that sysid/compid pair have already been seen on that port.

Consequences you need to know by heart:
- **A route appears only after the first packet from the addressee.** A script on the companion that stays silent won't receive a single addressed command from the GCS — let it send its own heartbeat.
- A packet is never sent back to the port it came in on.
- The routing table is reset on reboot; the GCS must notice `time_boot_ms` decreasing in `SYSTEM_TIME` and relearn the routes.
- A port can be excluded from forwarding: in ArduPilot 4.7+ — `MAVn_OPTIONS` bit 1 “Don't forward mavlink to/from,” in 4.6 and earlier — `SERIALn_OPTIONS` bit 10. You need this, for example, for a port with a “chatty” device on it.

{{diagram:mavlink-topology|Typical topology: the autopilot and the companion router connect the GCS over radio and over 4G to the onboard components.}}

### Tools
- **mavlink-router** (C++, a systemd service): one or more UARTs + UDP/TCP endpoints, routing by the same rules, filtering by msgid, tlog recording. The standard for Raspberry Pi/Jetson; configuration is in the comp-raspberry module.
- **MAVProxy** (Python): both a router (`--out`) and a console GCS with modules. Handy for debugging, heavier for permanent onboard use.
- **mavp2p** (Go): a lightweight router for the same purpose, a single binary.
- In the autopilot itself: every `SERIALn_PROTOCOL = 2` (MAVLink2) port takes part in forwarding. Sometimes you don't need the companion as a router at all — two autopilot ports are enough.

### Transports
| Transport | Latency | Loss | Notes |
|---|---|---|---|
| UART to the companion | < 1 ms | ~0 | 921600 baud ≈ 90 KB/s; needs a common GND and 3.3 V levels |
| SiK radio 433/868/915 | 30–100 ms | 0–10 % | air rate 64 kbit/s by default, half-duplex TDM; `RADIO_STATUS` (109) with RSSI/noise/free buffer space (`txbuf`); ECC halves the throughput |
| ELRS/Crossfire MAVLink | 10–50 ms | depends on rate | telemetry shares the air with control — a narrow channel |
| Wi-Fi | 2–20 ms | bursts | range of hundreds of meters; UDP broadcast is convenient but noisy |
| 4G/LTE | 50–300 ms, jitter | 0–5 %, dropouts | the modem has a private IP behind the carrier's NAT: no incoming connections |

**NAT and 4G.** A vehicle behind NAT can't accept incoming connections. Options: (1) a VPN — WireGuard/Tailscale/ZeroTier, the vehicle and GCS get addresses on the same virtual network; (2) a relay server with a public IP that both connect to (mavlink-router in TCP server mode on a VPS); (3) cloud services. A VPN also encrypts — which MAVLink signing doesn't do. For MAVLink over IP, UDP is preferable: under loss TCP retransmits old data and gives you “telemetry from the past” with delays of seconds.

### Link metrics and how to measure them
- **RTT** — from sending to the reply: `TIMESYNC` or `MAV_CMD_REQUEST_MESSAGE`/reply, or a heartbeat echo via your own message. Median and 95th percentile, not the mean.
- **Loss** — from gaps in seq (the mav-protocol module) and from `RADIO_STATUS.rxerrors`.
- **Jitter** — the spread of intervals between packets of a stream with a nominal rate.
- **Throughput** — the sum of frame sizes per second; compare it with the link budget.

You can reproduce impairments on Linux without a radio:

```bash
sudo tc qdisc add dev lo root netem delay 120ms 40ms distribution normal loss 5%
# ... measurements ...
sudo tc qdisc del dev lo root
```

### Link security
MAVLink signing protects against command spoofing, a VPN against eavesdropping and spoofing on the IP segment, frequency hopping and AES in the radio modem on the radio segment. None of these protect against jamming — failsafe procedures and autonomy protect against that (the nav-resilience module).

## practice
### Step 1. A router with three clients
On your machine: ArduPilot SITL (or `examples/mavlink/fake_vehicle.py`) → `mavlink-routerd` (or `mavproxy.py --out`) → three clients: QGC on 14550, your script on 14551, a tlog logger on 14552. Check: a script without its own heartbeat doesn't receive the `COMMAND_ACK` addressed to it; with a heartbeat, it does.

### Step 2. RTT and loss under netem
Write `link_probe.py`: every 100 ms it sends `TIMESYNC` (tc1 = 0, ts1 = now_ns), receives the reply, records the RTT; in parallel it counts losses from seq. Run 3 `tc netem` scenarios (clean, 120±40 ms + 5 %, 300±150 ms + 15 %), plot RTT histograms and compare the median/p95 with the configured values.

### Step 3. UDP vs TCP
Repeat scenario 3 through the router's TCP endpoint. Show on a plot the growing “telemetry” latency (time_boot_ms in ATTITUDE vs the receiver's clock) — the head-of-line blocking effect.

### Step 4. Your system's layout
Draw the topology of your vehicle (or a training one): all nodes with sysid/compid, ports, transports, where signing/VPN is enabled, what gets forwarded where. This goes into the engineering folder of the track's capstone.

The lab is passed when the router serves three clients, you have RTT/loss plots for three scenarios, the TCP effect is shown and the layout is drawn.

## diagnostics
- **Symptom:** a script on the companion gets no replies to its commands
  - Possible cause: it doesn't send a heartbeat — the autopilot doesn't know the route to its compid; or the compid collides with another one.
  - What to do: a 1 Hz heartbeat from the script, a unique compid.
- **Symptom:** two GCSs “fight”: modes jump, parameters get overwritten
  - Possible cause: both have sysid 255; or both send RC override.
  - What to do: different sysids; control rights for only one; in ArduPilot `MAV_GCS_SYSID`/`SYSID_MYGCS` for failsafe.
- **Symptom:** over 4G telemetry arrives with a delay of seconds and then “catches up”
  - Possible cause: TCP over a lossy link.
  - What to do: UDP; if needed, TCP only for MAVFTP/parameters.
- **Symptom:** a port with a peripheral floods the radio with traffic
  - Possible cause: all packets from that port are forwarded to the others.
  - What to do: disable forwarding for the port (MAVn_OPTIONS bit 1 / SERIALn_OPTIONS bit 10), a filter in the router.

## references
- MAVLink — Routing | https://mavlink.io/en/guide/routing.html | primary | A
- ArduPilot — MAVLink_routing.cpp (forwarding rules, source) | https://github.com/ArduPilot/ardupilot/blob/master/libraries/GCS_MAVLink/MAVLink_routing.cpp | primary | A
- mavlink-router | https://github.com/mavlink-router/mavlink-router | primary | A
- mavp2p | https://github.com/bluenviron/mavp2p | primary | A
- ArduPilot — SiK telemetry radio | https://ardupilot.org/copter/docs/common-sik-telemetry-radio.html | primary | A
- Linux tc-netem (man page) | https://man7.org/linux/man-pages/man8/tc-netem.8.html | primary | A

## checklist
- I know the sysid/compid ranges and why they must be unique
- I can state the forwarding rules and why a silent component is unreachable
- I choose a transport for the task and understand the limits of SiK and 4G (NAT)
- I measure RTT, loss and jitter and reproduce a bad network with netem
- I explain why UDP is better than TCP for telemetry
- I draw my system's topology with addresses and link protection
