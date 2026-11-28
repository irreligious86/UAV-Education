---
id: mav-routing
title: "MAVLink routing and transport: radio, 4G, multiple GCSs"
level: L3
readingTime: 45 min
firmware: ArduPilot 4.7 (checked against 4.7.3) · PX4 · MAVLink 2
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
source_hash: f41b7ab09fc4
---

## summary
As soon as more than one participant is connected to the vehicle (a GCS over a radio, a companion, a second GCS over 4G, a camera), the question is who receives which packets. MAVLink has no "network layer": routing rests on sysid/compid conventions and on tables that every node builds from the packets it has seen. The module goes through these rules in the ArduPilot source, the tools (mavlink-router, MAVProxy, mavp2p), the transports (UART, UDP, TCP, SiK radios, 4G/LTE through NAT and VPN), and the link metrics (latency, loss, jitter), measured under artificial impairment with `tc netem`. Lab: a router with three clients, and heartbeat RTT measured as the network degrades.

## theory
### Addressing: sysid and compid
- **sysid** is a vehicle or a station. Vehicles: usually 1…250 (the spec allows any ID 1…255; unique within one network!), a GCS usually 255 (a second one 254, and so on).
- **compid** is a component within a system: autopilot 1, cameras 100–105, gimbal 154, onboard computer 191–194, peripheral 158, GCS application 190. Your own script on the companion gets its own compid in the same system as the autopilot.
- A message either has `target_system`/`target_component` fields (addressed) or does not (telemetry, broadcast in nature). A target of 0 means "everyone".

### Forwarding rules (as in ArduPilot)
The source file `libraries/GCS_MAVLink/MAVLink_routing.cpp` states the rules explicitly. The autopilot processes a packet itself if it has no target, has target_system 0, or is addressed to it, including to its own sysid with target_component 0 or with no such field, and also to its own sysid with a compid that has not been seen on any port. It forwards the packet to **another** port if:
1. the message has no target_system, or target_system = 0: to every port where at least one packet has been seen (HEARTBEAT is handled separately and goes out to every active port, which is how routes can appear in the first place);
2. target_system is someone else's, and packets from that sysid have already been seen on that port;
3. target_system is its own: if target_component is set (≠ 0), to the port where packets from that sysid/compid pair have been seen; if target_component = 0 or the field is missing, to every port where any component of its own sysid has been seen (a camera, a script), while also processing it itself.

Consequences to know by heart:
- **A route appears only after the first packet from the target.** A silent script on the companion will not receive a single addressed command from the GCS, so have it send its own heartbeat.
- A packet is never sent back to the port it came in on.
- The routing table is reset on reboot; a GCS must notice a decrease in `time_boot_ms` in `SYSTEM_TIME` and relearn the routes.
- A port can be excluded from forwarding: in ArduPilot, `MAVn_OPTIONS` bit 1, "Don't forward mavlink to/from" (`SERIALn_OPTIONS` bit 10 before 4.7; on upgrade the bit is moved over automatically, and one left set in `SERIALn_OPTIONS` fails a pre-arm check). You need this, for example, for a port with a "chatty" device on it.

{{diagram:mav-forward-tree|The forwarding rules as a tree: a broadcast packet goes to every port where someone has been seen, an addressed one only to where the target has been seen; a silent component is unreachable.}}

{{diagram:mavlink-topology|A typical topology: the autopilot and a companion router connect GCSs over radio and 4G with the onboard components.}}

### Tools
- **mavlink-router** (C++, a systemd service): one or more UARTs + UDP/TCP endpoints, routing by the same rules, filtering by msgid, tlog recording. The standard on a Raspberry Pi/Jetson; configuration is covered in the comp-raspberry module.
- **MAVProxy** (Python): both a router (`--out`) and a console GCS with modules. Handy for debugging, heavier for permanent use on board.
- **mavp2p** (Go): a lightweight router with the same purpose, a single binary.
- In the autopilot itself: every port with `SERIALn_PROTOCOL = 2` (MAVLink2) takes part in forwarding. Sometimes you do not need the companion as a router at all; two autopilot ports are enough.

### Transports
| Transport | Latency | Loss | Notes |
|---|---|---|---|
| UART to the companion | < 1 ms | ~0 | 921600 baud ≈ 90 KB/s; needs a common GND and 3.3 V levels |
| SiK radio 433/868/915 | 30–100 ms | 0–10 % | air rate 64 kbit/s by default, half-duplex TDM; `RADIO_STATUS` (109) with RSSI/noise/free buffer space (`txbuf`); ECC halves the throughput |
| ELRS/Crossfire MAVLink | 10–50 ms | depends on the rate | telemetry shares the air with control: a narrow link |
| Wi-Fi | 2–20 ms | bursts | range of hundreds of meters; UDP broadcast is convenient but noisy |
| 4G/LTE | 50–300 ms, jitter | 0–5 %, dropouts | the modem has a private IP behind the carrier's NAT: no incoming connections |

**NAT and 4G.** A vehicle behind NAT does not accept incoming connections. Options: (1) a VPN (WireGuard/Tailscale/ZeroTier) that puts the vehicle and the GCS in the same virtual network; (2) a relay server with a public IP that both connect to (mavlink-router as a TCP server on a VPS); (3) cloud services. A VPN also encrypts, which MAVLink signing does not. For MAVLink over IP, prefer UDP: on loss, TCP retransmits stale data and gives you "telemetry from the past" with delays of seconds.

### Link metrics and how to measure them
- **RTT**, from sending to the reply: `TIMESYNC`, or `MAV_CMD_REQUEST_MESSAGE` and its reply, or a heartbeat echo through a message of your own. Use the median and the 95th percentile, not the mean.
- **Loss**, from gaps in seq (the mav-protocol module) and from `RADIO_STATUS.rxerrors`.
- **Jitter**, the spread of the intervals between packets of a stream with a nominal rate.
- **Throughput**, the sum of frame sizes per second; compare it with the link budget.

You can reproduce impairment on Linux without a radio:

```bash
sudo tc qdisc add dev lo root netem delay 120ms 40ms distribution normal loss 5%
# ... measurements ...
sudo tc qdisc del dev lo root
```

### Link security
MAVLink signing protects against spoofed commands, a VPN against eavesdropping and spoofing on the IP segment, frequency hopping and AES in the radio on the radio segment. None of these protects against jamming; what protects you there are failsafe procedures and autonomy (the nav-resilience module).

### Where it fits in the system

- **Takes in:** frames with sysid/compid and seq (`mav-protocol`); every participant's heartbeat, without which there is no route; the transport throughput (`link-telemetry-radios`, `rf-link-budget`).
- **Puts out:** a copy of the stream to every client, the GCS, scripts, the logger (`comp-raspberry`); addressed commands to the onboard components (`mav-component`); RTT, loss, and jitter metrics.
- **If you get this wrong:** the script on the companion is silent → there is no route to it, and addressed commands from the GCS do not arrive; it looks like "the component froze" (`mav-component`). TCP over 4G with loss → "telemetry from the past" with a delay of seconds, and the operator reacts to an outdated picture; choosing a link is covered in `link-telemetry-radios`.

## practice
### Step 1. A router with three clients
On your machine: ArduPilot SITL (or `examples/mavlink/fake_vehicle.py`) → `mavlink-routerd` (or `mavproxy.py --out`) → three clients: QGC on 14550, your script on 14551, a tlog logger on 14552. Check: a script without its own heartbeat does not receive the `COMMAND_ACK` messages addressed to it; with a heartbeat, it does.

### Step 2. RTT and loss under netem
Write `link_probe.py`: every 100 ms it sends a `TIMESYNC` (tc1 = 0, ts1 = now_ns), receives the reply, and logs the RTT; in parallel it counts loss from seq. Run 3 `tc netem` scenarios (clean, 120±40 ms + 5 %, 300±150 ms + 15 %), plot RTT histograms, and compare the median/p95 with the expected values. What to expect: `netem` on `dev lo` delays every packet that leaves through the loopback, in both directions and on every local hop. So the median RTT ≈ N × delay, where N is how many times the request and the reply together pass through the loopback: a script connected directly to SITL gives N = 2; through a router on the same machine (script ↔ router ↔ SITL), N = 4. For 120±40 ms that is 240 ms or 480 ms; for 300±150 ms, 600 ms or 1200 ms; the spread adds up as the square root of N (σ ≈ 57 or 80 ms for the first scenario), and p95 ≈ median + 1.6σ. One-way stream loss by seq is 1 − 0.95^(N/2): 5 % over one UDP hop, about 10 % over two; for 15 %, 15 % and about 28 %. A TCP hop shows no loss: it turns into latency.

### Step 3. UDP vs TCP
Repeat scenario 3 through the router's TCP endpoint. Plot how the "telemetry" latency grows (time_boot_ms in ATTITUDE against the receiver's clock): the head-of-line blocking effect.

### Step 4. A diagram of your system
Draw the topology of your vehicle (or a training one): every node with its sysid/compid, ports, transports, where signing/VPN is on, what is forwarded where. This goes into the engineering folder of the track's capstone.

Self-check: the lab is done when the router serves three clients and the script receives the `COMMAND_ACK` addressed to it only after its own heartbeat; RTT histograms are plotted for the three scenarios, and the median, p95, and seq loss are compared with the values expected from step 2 (clean link: a few milliseconds and 0 % loss; 120±40 ms and 5 %: a median RTT of 240 ms with a direct connection or 480 ms through a local router; 300±150 ms and 15 %: 600 or 1200 ms; tolerance ±10 % on the median and ±20 % of the computed value on p95 and loss; a median around 120 ms means the delay acts in one direction only, so the request or the reply does not go through `lo`); the step 3 plot shows TCP "telemetry" latency growing to seconds under loss ("telemetry from the past") while UDP does not; and the diagram is drawn with all the sysid/compid, ports, and transports.

## diagnostics
- **Symptom:** the script on the companion gets no replies to its commands
  - Possible cause: it sends no heartbeat, so the autopilot has no route to its compid; or its compid collides with another one.
  - What to do: a 1 Hz heartbeat from the script, a unique compid.
- **Symptom:** two GCSs "fight": modes jump, parameters get overwritten
  - Possible cause: both have sysid 255; or both send RC overrides.
  - What to do: different sysids; control rights to one of them; in ArduPilot, `MAV_GCS_SYSID` (`SYSID_MYGCS` before 4.7) for the failsafe.
- **Symptom:** over 4G, telemetry lags by seconds and then "catches up"
  - Possible cause: TCP over a lossy link.
  - What to do: UDP; if you must use TCP, only for MAVFTP/parameters.
- **Symptom:** a port with a peripheral floods the radio with traffic
  - Possible cause: every packet from that port is forwarded to the others.
  - What to do: disable forwarding for the port (`MAVn_OPTIONS` bit 1; `SERIALn_OPTIONS` bit 10 before 4.7), or filter in the router.

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
- I pick a transport for the job and understand the limits of SiK and 4G (NAT)
- I measure RTT, loss, and jitter and reproduce a bad network with netem
- I can explain why UDP beats TCP for telemetry
- I draw the topology of my system with addresses and link protection
