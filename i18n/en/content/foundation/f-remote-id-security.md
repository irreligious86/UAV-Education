---
id: f-remote-id-security
title: "Remote ID and Aircraft Security: Broadcast, MAVLink Signing, Firmware Protection"
level: L3
readingTime: 35 min
firmware: ArduPilot 4.5+ · PX4 1.15+ · MAVLink 2
status: published
tags:
  - Remote ID
  - security
  - MAVLink signing
  - firmware
related:
  - f-regulations
  - mav-routing
  - nav-resilience
  - link-elrs
  - mav-component
next:
  - mav-component
source: content/foundation/f-remote-id-security.md
source_hash: 91c2d66964de
---

## summary
Two questions a UAV engineer must close before series operation: “can the regulator see who is flying” and “can a stranger control my aircraft”. The first is Remote ID: the aircraft in flight broadcasts its identifier, its position and the pilot's position, and in a number of countries this is a mandatory condition for flying. The second is the attack surface: the RC link, MAVLink telemetry, GNSS, the companion computer's network and the firmware itself. The module covers what Remote ID transmits and how, how it is connected to ArduPilot and PX4, how MAVLink 2 signing works and what it does *not* do, where the companion is exposed, and how firmware is protected against substitution. The lab — enable signing in SITL and prove that unsigned commands are rejected.

## theory
### Remote ID: what is transmitted
Remote ID (Drone ID) is an on-board broadcast that an ordinary smartphone near the aircraft can receive. Under the ASTM F3411 standard (the basis of the US rules) and the European standard (ASD-STAN EN 4709-002) the messages contain:
- the aircraft identifier (serial number) and/or the operator registration number;
- the aircraft's position, altitude, speed and heading;
- the position of the controller/pilot (or of the takeoff point — depending on the rules);
- a timestamp and status (including emergency).

The transport is Bluetooth (4 legacy and 5 long range) and Wi-Fi (NAN and Beacon). It is a **broadcast**, with no connection to a server, so it works without internet.

### Who must comply and when
Checked against the regulators' pages on 2026-11-17; the rules change, check the official page before you fly. This is not legal advice.

| Where | Who must comply | How to comply | Dates |
|---|---|---|---|
| USA (FAA, Part 89) | every aircraft that must be registered: any flight under Part 107 and recreational flights with an aircraft heavier than 250 g | built-in Remote ID, an external broadcast module, or flying only in designated FRIA zones | in force (mandatory for most flights since March 2024) |
| USA, exception | an aircraft of no more than 0.55 lb (250 g) that flies only recreationally is not registered (14 CFR 48.15) — Remote ID is not required | — | — |
| EU (EASA) | direct Remote ID is part of the requirements for classes C1–C3 and for the specific category; the operator registration number is uploaded to the aircraft's Remote ID system | built-in or a module | in force |
| United Kingdom (CAA) | UK1, UK2, UK3, UK5, UK6 | the built-in Direct Remote ID function: enter your Remote ID and enable it before the flight | from 1 January 2026 |
| United Kingdom, second stage | UK0 from 100 g with a camera; UK4 (models), unless exempt; home-built and legacy aircraft from 100 g with a camera | built-in or a module | from 1 January 2028 |

For a home-built FPV aircraft this means: in the US — a broadcast module (or a FRIA) if the aircraft is registered; in the UK — the deadline is 1 January 2028 if the aircraft is 100 g or more and has a camera; in the EU — by class and operation category. Other countries have their own rules, and they change — check with your aviation regulator before your first flight; the `f-regulations` module is the starting point and has the table of official pages.

### Remote ID on ArduPilot and PX4
- **A module over MAVLink or DroneCAN** takes the position from the autopilot and broadcasts it. Ready-made modules (Cube ID, Holybro and others with OpenDroneID support) or the open **ArduRemoteID** — ArduPilot firmware for ESP32-S3/ESP32-C3 boards connected over MAVLink or DroneCAN (CAN needs an external transceiver).
- **A standalone broadcast module** — with its own GPS and battery; not connected to the autopilot.
- **What to choose** (course guideline): on ArduPilot and PX4 — a module over MAVLink or DroneCAN: the position comes from the autopilot, and a certified ArduPilot build will not let you take off without a working Remote ID. Betaflight and INAV have no OpenDroneID subsystem (it is not in the 2025.12.5 and 9.1.0 sources), so there — a standalone broadcast module. The check in both cases — a Remote ID scanner app on a phone sees the aircraft before takeoff.
- **ArduPilot**: the OpenDroneID subsystem — `DID_ENABLE`, the port `DID_MAVPORT` or `DID_CANDRIVER`, `DID_OPTIONS`. Certified configurations use a special firmware build with tamper protection and pre-takeoff checks: without a working Remote ID the aircraft won't arm. ArduRemoteID can lock its parameters against changes (changes only through signed commands).
- **PX4**: supports OpenDroneID messages and external modules; enabling and checks — per the Remote ID section of the documentation for your version.
- MAVLink messages: the `OPEN_DRONE_ID_*` family (`OPEN_DRONE_ID_BASIC_ID`, `_LOCATION`, `_SYSTEM`, `_OPERATOR_ID`); the pilot's position is sent to the module by the GCS (`OPEN_DRONE_ID_SYSTEM`).

{{diagram:remote-id-data-path|The Remote ID module doesn't know the position by itself: the autopilot provides it over MAVLink or DroneCAN, the pilot's position comes from the GCS; on a certified build a non-working module blocks arming.}}

### Attack surface
| Channel | Threat | Protection |
|---|---|---|
| RC link | someone else's transmitter with the same binding, jamming | a unique binding phrase in ELRS (it is a pair identifier, not encryption), a well-thought-out failsafe |
| MAVLink telemetry | foreign commands: mode change, disarm, mission upload | MAVLink 2 signing, separate keys per aircraft, MAVLink 1 disabled on radio ports |
| GNSS | jamming, spoofing | EKF checks, navigation without GNSS, assessment per `nav-resilience` |
| Companion | open Wi-Fi, default password, SSH, UDP telemetry to the whole segment, DDS without protection | SSH keys instead of passwords, a firewall, telemetry only to the required address, limited discovery and SROS2 |
| Firmware | substitution of the firmware or parameters | signed firmware and a secure bootloader, version control of parameters |

### MAVLink 2 signing: how it works
- The aircraft and the GCS share a **32-byte secret key**. 13 bytes are appended to each packet: link ID (1 byte), timestamp (6 bytes, in units of 10 µs since 1 January 2015) and the signature (6 bytes — the first 48 bits of SHA-256 over the key, header, payload, CRC, link ID and timestamp).
- The timestamp must increase — a replay of a recorded packet is rejected.
- **ArduPilot**: on MAVLink 2 ports, commands without a correct signature are not executed, downlink telemetry flows as before. USB is **not protected** — the key can be changed or erased over USB (physical access = full access). MAVLink 1 has no signing — radio ports are switched to MAVLink 2 (`SERIALn_PROTOCOL = 2`). In Mission Planner: Setup → Advanced → MAVLink Signing.
- **Signing is authentication, not encryption.** The traffic remains readable: position, mission and parameters are visible to anyone with a receiver. Encryption — at the radio level (for example, AES in some telemetry modems, the key in WFB-ng) or a VPN over IP.

### Companion: the network is the main hole
- A Raspberry Pi or Jetson with the default password, SSH with password login and a Wi-Fi access point is the first thing an attacker will find.
- `mavlink-router`/MAVProxy broadcasting telemetry to the broadcast address hand it to everyone on the network — specify the exact address of the GCS.
- ROS 2 by default discovers participants via multicast across the whole network. `ROS_DOMAIN_ID` separates systems but **does not protect** them; in Jazzy `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` limits discovery to the machine. DDS authentication and encryption — SROS2 (DDS Security).

### Firmware and parameters
- ArduPilot supports **signed firmware**: a public key is burned into the bootloader, and the firmware is signed with the private key; the bootloader will not start unsigned firmware. The key is kept outside the repository, the procedure — per the Secure Firmware documentation.
- Parameters are also a security configuration: keep a reference parameter file in git (the `eng-ci-configs` module), compare it before flight.

{{diagram:security-surface|Attack channels on the aircraft and their protection: binding and failsafe for RC, MAVLink 2 signing for telemetry, EKF checks for GNSS, a firewall and SROS2 for the companion, signed firmware.}}

### Place in the system

- **Receives:** position, altitude and speed from the autopilot over MAVLink or DroneCAN (`comp-mavlink`, `el-dronecan`); the pilot's position from the GCS; the identification requirement for your country (`f-regulations`).
- **Provides:** the Remote ID broadcast; MAVLink 2 signing on the radio ports (the frame — `mav-protocol`); network rules for the companion (`comp-raspberry`); a reference parameter file in git (`eng-ci-configs`).
- **If you get it wrong here:** a radio port was left on MAVLink 1 or without signing → a foreign command changes the mode or disarms; in the log it looks like a disarm “by itself” (tree 6 in `diag-troubleshooting`, the `MODE.Rsn` field). On a build with mandatory Remote ID the module is not working → the aircraft won't arm, and you need to look not at the motors but at PreArm (`ap-safety-fs`).

## practice
### Step 1. A map of your aircraft
The table from the theory for your own aircraft: which channels exist, what is currently open (port, protocol, password, address). Mark the three most dangerous items.

### Step 2. Signing in SITL
Start ArduPilot SITL with MAVProxy. Enable signing:
```text
signing setup mysecretphrase
```
MAVProxy will pass the key to the autopilot and start signing its packets. Then, from a separate script without the key, try to change the mode:
```python
from pymavlink import mavutil
m = mavutil.mavlink_connection("udpin:0.0.0.0:14551"); m.wait_heartbeat()
m.set_mode("GUIDED")                       # unsigned
print(m.recv_match(type="COMMAND_ACK", blocking=True, timeout=3))
```
Connect the script via `--out udp:127.0.0.1:14551` in MAVProxy or a separate SITL port. If the command goes through MAVProxy, that is expected: MAVProxy is connected to SITL's SERIAL0 (`tcp:127.0.0.1:5760`), and ArduPilot treats channel 0 as secure (like USB) and accepts unsigned packets — connect the script directly to a SITL port (`tcp:127.0.0.1:5763`, SERIAL2). Write down: whether the mode was accepted without the key, then — with the key:
```python
import hashlib
key = hashlib.sha256(b"mysecretphrase").digest()   # MAVProxy derives the key the same way
m.setup_signing(key, sign_outgoing=True)
```
Check that with the key the mode changes. Separately check that downlink telemetry is readable even without the key — signing does not encrypt.

### Step 3. Companion
On your companion (or a virtual machine): `ss -tulpn` — which ports are listening and on which addresses. Close what isn't needed, SSH — key only, telemetry — to the exact address of the GCS. For ROS 2 — check `ros2 node list` from another machine on the same network before and after `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`.

### Step 4. Remote ID (if you have a module)
Connect a module (ready-made or ArduRemoteID on an ESP32-S3) over MAVLink, enable `DID_ENABLE`, set the port. With a smartphone and the OpenDroneID app, check that the identifier, the aircraft's position and the pilot's position are visible. If you have no module — compile, from your country's rules, a list of requirements for your aircraft and how to meet them.

Self-check: the lab is done when the channel map is compiled and the three most dangerous items are marked in it; in SITL three results are written down with the script connected to `tcp:127.0.0.1:5763`: without the key the mode does not change, with the key it does, downlink telemetry is readable in both cases (if the mode changed without the key — the script goes through MAVProxy and channel 0, which is the trap from step 2, not a signing failure); the `ss -tulpn` output is saved before and after, and in the second one only the required ports on specific addresses remain; for Remote ID — the OpenDroneID app shows the identifier, the aircraft's position and the pilot's position, or a list of your country's requirements with a decision for each one is written down.

## diagnostics
- **Symptom:** after enabling signing the GCS “sees” the aircraft, but commands don't go through
  - Possible cause: the key on the GCS does not match the autopilot's key.
  - What to do: select the same key in the GCS; if it is lost — change or erase the key over USB.
- **Symptom:** signing is enabled, but someone else's GCS still controls the aircraft
  - Possible cause: the radio port runs MAVLink 1, the command came over USB, or through a node that signs for everyone (a router with the key).
  - What to do: `SERIALn_PROTOCOL = 2` on the radio ports, check the routing chain, the key only for those who control the aircraft.
- **Symptom:** the aircraft won't arm with a Remote ID error
  - Possible cause: the module is not connected or has not received the pilot's position, no link with the GCS, no operator ID set.
  - What to do: check the link with the module, the `OPEN_DRONE_ID_SYSTEM` data from the GCS, the module's parameters.
- **Symptom:** the companion's telemetry is visible to everyone on the network
  - Possible cause: output to a broadcast address, ROS 2 discovery across the whole network.
  - What to do: the GCS address instead of broadcast, a firewall, limited discovery, SROS2.
- **Symptom:** after an update the firmware does not start on a secure bootloader
  - Possible cause: the firmware is not signed or is signed with a different key.
  - What to do: sign it with your key by the Secure Firmware procedure.

## references
- ArduPilot — MAVLink2 signing | https://ardupilot.org/copter/docs/common-MAVLink2-signing.html | primary | A
- MAVLink — Message signing | https://mavlink.io/en/guide/message_signing.html | primary | A
- ArduPilot — Remote ID (OpenDroneID) | https://ardupilot.org/copter/docs/common-remoteid.html | primary | A
- ArduRemoteID — open Remote ID firmware | https://github.com/ArduPilot/ArduRemoteID | primary | A
- FAA — Remote Identification of drones | https://www.faa.gov/uas/getting_started/remote_id | primary | A
- FAA — Recreational Flyers (Remote ID for registered aircraft, FRIA; accessed 2026-11-17) | https://www.faa.gov/uas/recreational_flyers | primary | A
- eCFR — 14 CFR Part 48, § 48.15 (who does not register; accessed 2026-11-17) | https://www.ecfr.gov/current/title-14/chapter-I/subchapter-C/part-48 | primary | A
- UK CAA — Remote ID (classes and the 2026/2028 dates; accessed 2026-11-17) | https://www.caa.co.uk/drones/drone-regulations/policy-programmes/remote-id-rid/ | primary | A
- EASA — FAQ: Open category (registration number in the Remote ID system; accessed 2026-11-17) | https://www.easa.europa.eu/en/the-agency/faqs/open-category | primary | A
- ROS 2 — Security (SROS2) | https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Security.html | primary | A

## checklist
- I can explain what Remote ID broadcasts and over which radio channels
- I know where to find my country's requirements and how to meet them
- I connect a Remote ID module to ArduPilot over MAVLink or DroneCAN
- I can list the attack channels on the aircraft and the protection for each
- I enable MAVLink 2 signing and understand that it does not encrypt
- I lock down the companion's network and limit ROS 2 discovery
- I know what signed firmware and a secure bootloader are
