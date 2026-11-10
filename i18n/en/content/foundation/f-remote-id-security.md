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
source_hash: 654aac96c08a
---

## summary
Two questions a UAV engineer has to settle before production operation: “can the regulator see who is flying” and “can a stranger control my aircraft”. The first is Remote ID: in flight the aircraft broadcasts its identifier, coordinates and the pilot's position, and in a number of countries this is a mandatory condition for flying. The second is the attack surface: the RC link, MAVLink telemetry, GNSS, the companion computer's network and the firmware itself. This module breaks down what Remote ID transmits and how, how it is connected to ArduPilot and PX4, how MAVLink 2 signing works and what it does *not* do, where the companion is exposed, and how firmware is protected from being swapped. The lab: enable signing in SITL and prove that unsigned commands are dropped.

## theory
### Remote ID: what is transmitted
Remote ID (Drone ID) is a broadcast from the aircraft that an ordinary smartphone near the aircraft can receive. Under the ASTM F3411 standard (the US rules are based on it) and the European standard (ASD-STAN EN 4709-002) the messages contain:
- the aircraft identifier (serial number) and/or the operator registration number;
- the aircraft's coordinates, altitude, speed and heading;
- the coordinates of the transmitter/pilot (or of the takeoff point — depending on the rules);
- a timestamp and status (including emergency status).

The transport is Bluetooth (4 legacy and 5 long range) and Wi-Fi (NAN and Beacon). This is a **broadcast**, with no connection to a server, so it works without internet.

### Who needs it and when
In the USA it's the FAA Part 89 rule (mandatory for most flights since March 2024): built-in Remote ID, an external broadcast module (“beacon”), or flying only in specially designated areas (FRIA). In the EU, direct Remote ID is part of the requirements for classes C1–C3 and for the specific category, plus the operator registration number. Other countries have their own rules, and they change — check with your aviation regulator before the first flight; the `f-regulations` module is your starting point.

### Remote ID on ArduPilot and PX4
- **A module over MAVLink or DroneCAN** takes coordinates from the autopilot and broadcasts them. Off-the-shelf modules (Cube ID, Holybro and others with OpenDroneID support) or the open **ArduRemoteID** — ArduPilot firmware for ESP32-S3/ESP32-C3 boards connected over MAVLink or DroneCAN (CAN needs an external transceiver).
- **A standalone beacon** — with its own GPS and battery; it isn't connected to the autopilot.
- **ArduPilot**: the OpenDroneID subsystem — `DID_ENABLE`, port `DID_MAVPORT` or `DID_CANDRIVER`, `DID_OPTIONS`. Certified configurations use a special firmware build with tamper protection and pre-takeoff checks: without working Remote ID the aircraft won't arm. ArduRemoteID can lock its own parameters against changes (changes only via signed commands).
- **PX4**: supports OpenDroneID messages and external modules; enabling and checks follow the Remote ID section of the docs for your version.
- MAVLink messages: the `OPEN_DRONE_ID_*` family (`OPEN_DRONE_ID_BASIC_ID`, `_LOCATION`, `_SYSTEM`, `_OPERATOR_ID`); the pilot's coordinates are sent to the module by the GCS (`OPEN_DRONE_ID_SYSTEM`).

### Attack surface
| Channel | Threat | Protection |
|---|---|---|
| RC link | someone else's transmitter with the same binding, jamming | a unique binding phrase in ELRS (it identifies the pair, it is not encryption), a well-thought-out failsafe |
| MAVLink telemetry | someone else's commands: mode change, disarm, mission upload | MAVLink 2 signing, separate keys per aircraft, MAVLink 1 disabled on radio ports |
| GNSS | jamming, spoofing | EKF checks, navigation without GNSS, assessment per `nav-resilience` |
| Companion | open Wi-Fi, default password, SSH, UDP telemetry to the whole segment, unprotected DDS | SSH keys instead of passwords, firewall, telemetry only to the required address, restricted discovery and SROS2 |
| Firmware | swapped firmware or parameters | signed firmware and a secure bootloader, version control of parameters |

### MAVLink 2 signing: how it works
- The aircraft and the GCS share a **32-byte secret key**. 13 bytes are appended to each packet: link ID (1 byte), timestamp (6 bytes, in units of 10 µs since January 1, 2015) and signature (6 bytes — the first 48 bits of SHA-256 over the key, header, payload, CRC, link ID and timestamp).
- The timestamp must increase — a replay of a recorded packet is dropped.
- **ArduPilot**: on MAVLink 2 ports, commands without a valid signature are not executed; downlink telemetry flows as before. USB is **not protected** — over USB you can change or erase the key (physical access = full access). MAVLink 1 has no signing — radio ports are switched to MAVLink 2 (`SERIALn_PROTOCOL = 2`). In Mission Planner: Setup → Advanced → MAVLink Signing.
- **Signing is authentication, not encryption.** The traffic stays readable: coordinates, mission and parameters are visible to anyone with a receiver. Encryption happens at the radio level (for example, AES in some telemetry modems, the key in WFB-ng) or via a VPN over IP.

### Companion: the network is the biggest hole
- A Raspberry Pi or Jetson with a default password, password-based SSH and a Wi-Fi access point is the first thing an attacker will find.
- `mavlink-router`/MAVProxy broadcasting telemetry to the broadcast address hand it to everyone on the network — specify the GCS's exact address.
- By default ROS 2 discovers participants via multicast across the whole network. `ROS_DOMAIN_ID` separates systems but does **not protect** them; in Jazzy `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` restricts discovery to the machine. DDS authentication and encryption is SROS2 (DDS Security).

### Firmware and parameters
- ArduPilot supports **signed firmware**: a public key is baked into the bootloader, the firmware is signed with the private key; the bootloader won't start unsigned firmware. The key is kept outside the repository; the procedure follows the Secure Firmware documentation.
- Parameters are security configuration too: keep a reference parameter file in git (module `eng-ci-configs`) and compare against it before flight.

{{diagram:security-surface|Attack channels on the aircraft and their protection: binding and failsafe for RC, MAVLink 2 signing for telemetry, EKF checks for GNSS, firewall and SROS2 for the companion, signed firmware.}}

## practice
### Step 1. A map of your aircraft
The table from the theory section, for your aircraft: which channels exist, what is open right now (port, protocol, password, address). Mark the three most dangerous items.

### Step 2. Signing in SITL
Start ArduPilot SITL with MAVProxy. Enable signing:
```text
signing setup mysecretphrase
```
MAVProxy will pass the key to the autopilot and start signing its own packets. Then, from a separate script without the key, try to change the mode:
```python
from pymavlink import mavutil
m = mavutil.mavlink_connection("udpin:0.0.0.0:14551"); m.wait_heartbeat()
m.set_mode("GUIDED")                       # unsigned
print(m.recv_match(type="COMMAND_ACK", blocking=True, timeout=3))
```
Connect the script via `--out udp:127.0.0.1:14551` in MAVProxy or a separate SITL port. If the command goes through MAVProxy, that's expected: MAVProxy is connected to SITL's SERIAL0 (`tcp:127.0.0.1:5760`), and ArduPilot treats channel 0 as protected (like USB) and accepts unsigned packets — connect the script directly to a SITL port (`tcp:127.0.0.1:5763`, SERIAL2). Record: whether the mode was accepted without the key, then — with the key:
```python
import hashlib
key = hashlib.sha256(b"mysecretphrase").digest()   # MAVProxy derives the key the same way
m.setup_signing(key, sign_outgoing=True)
```
Check that the mode changes with the key. Separately, check that downlink telemetry is readable even without the key — signing doesn't encrypt.

### Step 3. Companion
On your companion (or a virtual machine): `ss -tulpn` — which ports are listening and on which addresses. Close what isn't needed, SSH by key only, telemetry to the GCS's exact address. For ROS 2, check `ros2 node list` from another machine on the same network before and after `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`.

### Step 4. Remote ID (if you have a module)
Connect the module (off-the-shelf or ArduRemoteID on an ESP32-S3) over MAVLink, enable `DID_ENABLE`, set the port. Use a smartphone with the OpenDroneID app to check that the identifier and the aircraft's and pilot's coordinates are visible. If you don't have a module, compile a list of requirements for your aircraft under your country's rules and a way to meet them.

The lab counts as done when the channel map is compiled, you've proven in SITL that an unsigned command isn't executed and a signed one is, the companion's open ports are listed and the unnecessary ones closed, and for Remote ID — either a broadcast check or a list of requirements with a solution.

## diagnostics
- **Symptom:** after enabling signing the GCS “sees” the aircraft, but commands don't go through
  - Possible cause: the key on the GCS doesn't match the autopilot's key.
  - What to do: select the same key in the GCS; if lost, change or erase the key over USB.
- **Symptom:** signing is enabled, but someone else's GCS can still control the aircraft
  - Possible cause: the radio port runs MAVLink 1, the command came over USB, or through a node that signs for everyone (a router with the key).
  - What to do: `SERIALn_PROTOCOL = 2` on radio ports, check the routing chain, the key only for those who are in control.
- **Symptom:** the aircraft won't arm with a Remote ID error
  - Possible cause: the module isn't connected or hasn't received the pilot's coordinates, no link with the GCS, operator ID not set.
  - What to do: check the link with the module, the `OPEN_DRONE_ID_SYSTEM` data from the GCS, the module's parameters.
- **Symptom:** the companion's telemetry is visible to everyone on the network
  - Possible cause: output to the broadcast address, ROS 2 discovery across the whole network.
  - What to do: the GCS address instead of broadcast, firewall, restricted discovery, SROS2.
- **Symptom:** after an update the firmware doesn't start on the secure bootloader
  - Possible cause: the firmware isn't signed or is signed with a different key.
  - What to do: sign it with your key following the Secure Firmware procedure.

## references
- ArduPilot — MAVLink2 signing | https://ardupilot.org/copter/docs/common-MAVLink2-signing.html | primary | A
- MAVLink — Message signing | https://mavlink.io/en/guide/message_signing.html | primary | A
- ArduPilot — Remote ID (OpenDroneID) | https://ardupilot.org/copter/docs/common-remoteid.html | primary | A
- ArduRemoteID — open Remote ID firmware | https://github.com/ArduPilot/ArduRemoteID | primary | A
- FAA — Remote Identification of drones | https://www.faa.gov/uas/getting_started/remote_id | primary | A
- ROS 2 — Security (SROS2) | https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Security.html | primary | A

## checklist
- I can explain what Remote ID broadcasts and over which radio channels
- I know where to find my country's requirements and how to meet them
- I can connect a Remote ID module to ArduPilot over MAVLink or DroneCAN
- I can list the attack channels on the aircraft and the protection for each
- I can enable MAVLink 2 signing and understand that it doesn't encrypt
- I can lock down the companion's network and restrict ROS 2 discovery
- I know what signed firmware and a secure bootloader are
