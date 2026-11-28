---
id: mav-protocol
title: "MAVLink inside out: frame, CRC, dialects, signing"
level: L3
readingTime: 45 min
firmware: MAVLink 2 (checked against mavlink/mavlink master, November 2026) · ArduPilot 4.7 (checked against 4.7.3) · PX4 1.18 (checked against v1.18.0)
status: published
added: 2026-11-08
tags:
  - MAVLink
  - protocol
  - CRC
  - mavgen
  - signing
related:
  - comp-mavlink
  - mav-services
  - emb-protocols
next:
  - mav-services
source: content/companion/mav-protocol.md
source_hash: 510b0bde3b48
---

## summary
In the comp-mavlink module, MAVLink was "a library that sends messages". Here it becomes a protocol you can read by eye in a hex dump. We take v1 and v2 frames apart byte by byte, look at the sequence number and how to count packet loss from it, at CRC-16/MCRF4XX and why a CRC_EXTRA byte is mixed into it, and at why MAVLink 2 truncates trailing zeros in the payload and what that breaks in home-made parsers. Then we look at where messages come from: XML dialects, `mavgen`, the field order on the wire (not the XML order), extension fields, and compatibility. The last part is packet signing: what the 13 bytes are made of, how the key gets into the autopilot, and what signing protects against and what it does not. Lab: a frame decoder without the pymavlink parser, your own dialect with a new message, automated tests in `examples/mavlink/`.

## theory
### The MAVLink 2 frame
| Byte | Field | Meaning |
|---|---|---|
| 0 | STX = `0xFD` | start of frame (v1: `0xFE`) |
| 1 | len | payload length after zero truncation (0–255) |
| 2 | incompat_flags | bit 0: the frame is signed; an unknown bit → the frame is dropped |
| 3 | compat_flags | an unknown bit can be ignored |
| 4 | seq | sequence number 0–255 from this sender |
| 5 | sysid | sending system |
| 6 | compid | sending component |
| 7–9 | msgid | 24 bits, little-endian |
| 10… | payload | len bytes |
| +2 | checksum | CRC-16/MCRF4XX, little-endian |
| +13 | signature | only if incompat_flags & 1 |

The v2 header is 10 bytes, v1 is 6 (no flags, a 1-byte msgid, so only messages with IDs < 256). All multi-byte numbers are little-endian. The minimum v2 frame is 12 bytes, the maximum 280.

{{diagram:mavlink2-frame|A MAVLink 2 frame: a 10-byte header, the payload, the CRC, and the optional signature.}}

### seq and packet loss
Every sender (a sysid/compid pair) increments seq modulo 256. A receiver that sees seq_new ≠ seq_old + 1 knows that (seq_new − seq_old − 1) mod 256 frames were lost. That is exactly how QGC and Mission Planner compute "link quality" and the loss percentage, with no feedback from the radio at all. The trap: if one link carries two different senders with the same sysid/compid (two copies of the same script, for example), the loss count becomes meaningless and routing becomes unpredictable. Note that seq counts per sending channel: a router that filters messages by msgid (mav-routing) makes the GCS see "loss" that is not real.

### CRC and CRC_EXTRA
The checksum covers every byte after STX up to the end of the payload (the header without STX + the payload), using CRC-16/MCRF4XX (polynomial 0x1021 in reflected form, initial value 0xFFFF; the check value for "123456789" is 0x6F91). Then one more byte is "fed" into the CRC: **CRC_EXTRA**, computed from the message definition, that is, its name and the list of fields with their types. It is not in the frame.

Why: if the sender and the receiver have different definitions for the same msgid (a field added, a type changed), the length may match while the meaning does not. CRC_EXTRA makes such frames invalid, and the receiver silently drops them. Hence the classic symptom "the link is up, the heartbeat is there, but this one message never arrives": the dialects diverged on a single message.

```python
def x25_crc(data: bytes, crc: int = 0xFFFF) -> int:
    for b in data:
        tmp = b ^ (crc & 0xFF)
        tmp = (tmp ^ (tmp << 4)) & 0xFF
        crc = ((crc >> 8) ^ (tmp << 8) ^ (tmp << 3) ^ (tmp >> 4)) & 0xFFFF
    return crc
```

### Zero truncation in the payload
MAVLink 2 drops **trailing zero bytes** of the payload before sending: a `COMMAND_LONG` with `confirmation` = 0 goes out as 32 bytes instead of 33 (param1–param7 come first on the wire, so their zeros never end up at the tail). The receiver must pad the payload with zeros up to the full struct size before unpacking. A home-made parser that checks `len == sizeof(struct)` will drop half the messages, and it will look like "random packet loss". At least one payload byte is always kept.

{{diagram:mav-rx-frame-flow|Receiving a frame step by step: a corrupted byte and diverged dialects both end in a silent drop at the CRC check with CRC_EXTRA, while truncated zeros must be padded back, not rejected.}}

### Field order on the wire
In the XML, fields are listed in an order that suits humans. On the wire they are **sorted by type size, largest first** (uint64/double → uint32/int32/float → uint16 → uint8/char), stable within one size, and **extension fields** (after the `<extensions/>` tag) go at the end in XML order. That way the struct is aligned with no gaps. In pymavlink this is `ordered_fieldnames`; in the C headers it is the field order in `mavlink_*_t`. CRC_EXTRA uses the fields in wire order, without the extension fields: that is why adding an extension field does not break compatibility, while changing an existing field does.

### Dialects and mavgen
Messages are defined in XML: `minimal.xml` (HEARTBEAT) ⊂ `standard.xml` ⊂ `common.xml` ⊂ `ardupilotmega.xml` (through `<include>`). Your own dialect is an XML file that includes `common.xml` and adds its own messages in a dedicated ID range. `mavgen` generates a library from it:

```bash
python -m pymavlink.tools.mavgen --lang=Python3 --wire-protocol=2.0 --output=mydialect.py mydialect.xml
python -m pymavlink.tools.mavgen --lang=C --wire-protocol=2.0 --output=generated/ mydialect.xml
```

Rules that save days of debugging: the msgid of a new message must not collide with existing ones; after changing the XML, rebuild **every** side (autopilot, companion, GCS); check the generated CRC_EXTRA in both places. For experiments without rebuilding the autopilot there are ready-made general-purpose messages: `NAMED_VALUE_FLOAT` (251), `NAMED_VALUE_INT` (252), `DEBUG_VECT` (250), `TUNNEL` (385, arbitrary bytes with a payload type).

### Packet signing
A signed frame (incompat_flags bit 0) carries 13 bytes: link_id (1), timestamp (6 bytes, in units of 10 µs since January 1, 2015), signature (the first 6 bytes of a SHA-256 hash of "secret key + header + payload + CRC + link_id + timestamp"). The receiver checks the signature and that the timestamp increases monotonically: this protects against both spoofing and replay of a captured frame.

The key (32 bytes) reaches the autopilot in a `SETUP_SIGNING` (256) message over a trusted link, usually USB; ArduPilot stores it in flash and at boot starts the timestamp one minute past the last saved one. In Mission Planner it is "SETUP → Advanced → MAVLink Signing"; in QGC, the MAVLink settings. PX4 gained signing only in 1.18.0 (v1.17.0 does not have it): the key lives on the SD card (`mavlink/mavlink-signing-key.bin`), signing is on whenever a key is present (unsigned HEARTBEAT and RADIO_STATUS are still accepted on every link), `SETUP_SIGNING` is accepted on any link but rejected while armed, and signing is removed with a signed all-zero key (`mavlink_sign_control.cpp`, `mavlink_main.cpp`, v1.18.0). In ArduPilot 4.7+, bit 0 of `MAVn_OPTIONS` ("Accept unsigned MAVLink2 messages") allows unsigned packets on a specific channel; in 4.6 and earlier there is no such setting, and with signing on, unsigned packets are accepted only on channel 0 (USB) and for `RADIO_STATUS` (4.7 keeps both of these exceptions, `GCS_Signing.cpp`).

What signing does **not** do: it does not encrypt (telemetry is still readable), it does not protect against jamming, and it is useless if the key sits in the open on a laptop. For encryption, use a VPN over an IP link (WireGuard) or a radio with built-in AES.

### Where it fits in the system

- **Takes in:** a byte stream from a UART driver with a ring buffer (`emb-protocols`); an XML dialect shared by the autopilot, the companion, and the GCS; the signing key over a trusted link.
- **Puts out:** valid frames with sysid/compid to routing, and seq to loss counting (`mav-routing`); unpacked messages to the protocol exchanges (`mav-services`); protection against spoofed commands (`f-remote-id-security`).
- **If you get this wrong:** dialects diverged on one message → CRC_EXTRA does not match and the frame is silently dropped: the heartbeat is there, but the sensor data never reaches the autopilot (`mav-component`). A home-made parser that checks `len == sizeof(struct)` drops truncated frames → "random loss" of commands and extra retries (`mav-services`).

## practice
### Step 1. A decoder by hand
`examples/mavlink/` contains `mavlink_crc.py` and `decode_frame.py`. First, without opening them, take the hex string of a HEARTBEAT frame (the test prints one, or use `mavlink_connection(...).mav.heartbeat_encode(...).pack(...)`) and mark every field on paper using the table above. Then run:

```bash
cd examples/mavlink
python decode_frame.py <hex>
python -m pytest -q tests/test_protocol.py
```

Corrupt one payload byte and confirm that the CRC fails; corrupt seq, and the CRC fails too (seq is covered by the CRC), while a parser that only checks the length would not notice.

### Step 2. CRC_EXTRA by hand
The `crc_extra_from_fields` function reproduces mavgen. The test checks it against pymavlink for five messages without extension fields. Add `SYS_STATUS` to the test and explain why it fails without changing the function (it has extension fields, and they must be excluded).

### Step 3. Your own dialect
Write `mydialect.xml` with `<include>common.xml</include>` and one message, `PAYLOAD_STATUS` (an ID in a free range; fields: `uint32_t time_boot_ms`, `float temperature`, `uint8_t state`, `char[16] name`). Generate the Python library, send the message over UDP, and receive it with a second script. Look at the order in which the fields landed on the wire, and check CRC_EXTRA with the function from step 2.

### Step 4. Loss from seq
Run `fake_vehicle.py --loss 0.2` and write a receiver that computes the HEARTBEAT/PARAM_VALUE loss percentage from seq. Compare it with the configured 20 %.

Self-check: the lab is done when the `tests/test_protocol.py` tests pass, your paper markup of the frame matches the `decode_frame.py` output field for field, a corrupted payload byte and a corrupted seq both make the CRC fail, you have written down why the `SYS_STATUS` test fails without changes (the extension fields must be excluded), your dialect's `PAYLOAD_STATUS` message is received by the second script and its CRC_EXTRA matches the function from step 2, and the seq-based loss counter shows close to the configured 20 %.

## diagnostics
- **Symptom:** the heartbeat flows, but one particular message never arrives
  - Possible cause: different definitions of the message → CRC_EXTRA did not match, and the frame was dropped.
  - What to do: compare CRC_EXTRA in both libraries; rebuild every side from the same XML.
- **Symptom:** your own parser loses some COMMAND_LONG/SET_POSITION_TARGET messages
  - Possible cause: a len == sizeof(struct) check, while MAVLink 2 truncated the zeros.
  - What to do: pad the payload with zeros to the full size.
- **Symptom:** after enabling signing, QGC does not connect
  - Possible cause: the GCS has no key, and the channel does not accept unsigned packets.
  - What to do: enter the same key in the GCS; temporarily allow unsigned packets over USB.
- **Symptom:** the loss counter shows 50 % with a good radio
  - Possible cause: two senders with the same sysid/compid on one link.
  - What to do: give every script/component a unique compid.

## references
- MAVLink — Serialization (packet format, CRC_EXTRA, truncation) | https://mavlink.io/en/guide/serialization.html | primary | A
- MAVLink — Message signing | https://mavlink.io/en/guide/message_signing.html | primary | A
- MAVLink — Dialects and mavgen | https://mavlink.io/en/guide/xml_schema.html | primary | A
- pymavlink — generator and Python dialects (source) | https://github.com/ArduPilot/pymavlink | primary | A
- ArduPilot — MAVLink2 signing (setup) | https://ardupilot.org/planner/docs/common-MAVLink2-signing.html | primary | A

## checklist
- I can mark up a MAVLink 2 frame byte by byte and know what the CRC covers
- I can explain what CRC_EXTRA is for and what symptom diverged dialects produce
- I account for payload zero truncation when parsing
- I know the field order on the wire and the role of extension fields
- I build my own dialect with mavgen and check it on both sides
- I understand what signing protects against and what it does not
