---
id: mav-protocol
title: "MAVLink inside out: frame, CRC, dialects, signing"
level: L3
readingTime: 45 min
firmware: ArduPilot · PX4
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
source_hash: 0cf684a93bbb
---

## summary
In the comp-mavlink module MAVLink was “a library that sends messages.” Here it becomes a protocol you can read by eye in a hex dump. We take apart the v1 and v2 frames byte by byte, the sequence number and how to count losses with it, CRC-16/MCRF4XX and why a CRC_EXTRA byte is mixed into it, why MAVLink 2 truncates trailing zeros in the payload and what that breaks in homemade parsers. Then — where messages come from: XML dialects, `mavgen`, field order on the wire (not the one in the XML), extension fields and compatibility. The last part is packet signing: what the 13 bytes consist of, how the key gets into the autopilot, and what signing protects against and what it doesn't. Lab: a frame decoder without the pymavlink parser, your own dialect with a new message, automated tests in `examples/mavlink/`.

## theory
### The MAVLink 2 frame
| Byte | Field | Meaning |
|---|---|---|
| 0 | STX = `0xFD` | start of frame (v1 — `0xFE`) |
| 1 | len | payload length after zero truncation (0–255) |
| 2 | incompat_flags | bit 0 — frame is signed; unknown bit → frame is dropped |
| 3 | compat_flags | an unknown bit can be ignored |
| 4 | seq | sequence number 0–255 from this sender |
| 5 | sysid | sending system |
| 6 | compid | sending component |
| 7–9 | msgid | 24 bits, little-endian |
| 10… | payload | len bytes |
| +2 | checksum | CRC-16/MCRF4XX, little-endian |
| +13 | signature | only if incompat_flags & 1 |

The v2 header is 10 bytes, v1 is 6 (no flags, msgid is 1 byte, i.e. only messages with ID < 256). All multi-byte numbers are little-endian. The minimum v2 frame is 12 bytes, the maximum is 280.

{{diagram:mavlink2-frame|MAVLink 2 frame: a 10-byte header, the payload, the CRC and an optional signature.}}

### seq and losses
Each sender (a sysid/compid pair) increments seq modulo 256. A receiver that sees seq_new ≠ seq_old + 1 knows that (seq_new − seq_old − 1) mod 256 frames were lost. That's exactly how QGC and Mission Planner compute “link quality” and the loss percentage — without any feedback from the radio. The trap: if one channel has two different senders with the same sysid/compid (for example, two copies of the same script), the loss count becomes meaningless and routing becomes unpredictable.

### CRC and CRC_EXTRA
The checksum is computed over all bytes after STX through the end of the payload (header without STX + payload), using CRC-16/MCRF4XX (polynomial 0x1021 in reflected form, initial value 0xFFFF; the check value for “123456789” is 0x6F91). Then one more byte is “fed” into the CRC — **CRC_EXTRA**, computed from the message definition: its name and the list of fields with their types. It is not in the frame.

Why: if the sender and receiver have different definitions for the same msgid (a field was added, a type changed), the length may match but the meaning won't. CRC_EXTRA makes such frames invalid: the receiver silently drops them. Hence the classic symptom “the link is up, heartbeat is there, but this one message doesn't arrive” — the dialects diverged on one message.

```python
def x25_crc(data: bytes, crc: int = 0xFFFF) -> int:
    for b in data:
        tmp = b ^ (crc & 0xFF)
        tmp = (tmp ^ (tmp << 4)) & 0xFF
        crc = ((crc >> 8) ^ (tmp << 8) ^ (tmp << 3) ^ (tmp >> 4)) & 0xFFFF
    return crc
```

### Payload zero truncation
MAVLink 2 strips **trailing zero bytes** from the payload before sending: a `COMMAND_LONG` with param5–param7 = 0 goes out shorter than 33 bytes. The receiver must pad the payload with zeros to the full struct size before unpacking. A homemade parser that checks `len == sizeof(struct)` will drop half the messages, and it will look like “random losses.” At least one payload byte is always kept.

### Field order on the wire
Fields in the XML are in an order convenient for humans. On the wire they are **sorted by type size in descending order** (uint64/double → uint32/int32/float → uint16 → uint8/char), stable within the same size, and the **extension fields** (after the `<extensions/>` tag) go at the end in XML order. This way the struct is aligned without holes. In pymavlink this is `ordered_fieldnames`; in the C headers — the field order in `mavlink_*_t`. CRC_EXTRA uses the fields in wire order, without extension fields: that's why adding an extension field doesn't break compatibility, while changing an old field does.

### Dialects and mavgen
Messages are described in XML: `minimal.xml` (HEARTBEAT, PROTOCOL_VERSION) ⊂ `standard.xml` ⊂ `common.xml` ⊂ `ardupilotmega.xml` (via `<include>`). Your own dialect is an XML that includes `common.xml`, with your own messages in a dedicated ID range. `mavgen` generates a library from it:

```bash
python -m pymavlink.tools.mavgen --lang=Python3 --wire-protocol=2.0 --output=mydialect.py mydialect.xml
python -m pymavlink.tools.mavgen --lang=C --wire-protocol=2.0 --output=generated/ mydialect.xml
```

Rules that save days of debugging: the msgid of a new message must not overlap existing ones; after changing the XML, rebuild **all** sides (autopilot, companion, GCS); check the generated CRC_EXTRA in both places. For experiments without rebuilding the autopilot there are ready-made generic messages: `NAMED_VALUE_FLOAT` (251), `NAMED_VALUE_INT` (252), `DEBUG_VECT` (250), `TUNNEL` (385, arbitrary bytes with a payload type).

### Packet signing
A signed frame (incompat_flags bit 0) carries 13 bytes: link_id (1), timestamp (6 bytes, unit — 10 µs since January 1, 2015), signature (the first 6 bytes of SHA-256 of “secret key + header + payload + CRC + link_id + timestamp”). The receiver checks the signature and that the timestamp is monotonic — this protects against both spoofing and replay of an intercepted frame.

The key (32 bytes) is passed to the autopilot with the `SETUP_SIGNING` message (256) over a trusted channel — usually USB; ArduPilot stores it in flash and on boot takes a timestamp one minute ahead of the last saved one. In Mission Planner — “Advanced → MAVLink Signing,” in QGC — the MAVLink settings. In ArduPilot 4.7+ bit 0 of the `MAVn_OPTIONS` parameter (“Accept unsigned MAVLink2 messages”) allows unsigned packets on a specific channel; in 4.6 and earlier there is no such setting — with signing enabled, unsigned packets are accepted only on channel 0 (USB) and for `RADIO_STATUS`.

What signing does **not** do: it doesn't encrypt (telemetry is still visible), it doesn't protect against jamming, and it's useless if the key sits in the clear on a laptop. For encryption — a VPN over the IP link (WireGuard) or a radio with built-in AES.

## practice
### Step 1. Decoder by hand
`examples/mavlink/` contains `mavlink_crc.py` and `decode_frame.py`. First, without opening them, take the hex string of a HEARTBEAT frame (the test prints it, or `mavlink_connection(...).mav.heartbeat_encode(...).pack(...)`) and mark up all the fields on paper using the table above. Then run:

```bash
cd examples/mavlink
python decode_frame.py <hex>
python -m pytest -q tests/test_protocol.py
```

Corrupt one payload byte and make sure the CRC doesn't match; corrupt seq — the CRC won't match either (seq is part of the CRC), while a parser that only checks the length wouldn't notice.

### Step 2. CRC_EXTRA by hand
The `crc_extra_from_fields` function reproduces mavgen. The test compares it against pymavlink for five messages without extension fields. Add `SYS_STATUS` to the test and explain why it doesn't pass without changing the function (it has extension fields — they need to be excluded).

### Step 3. Your own dialect
Write `mydialect.xml` with `<include>common.xml</include>` and one message `PAYLOAD_STATUS` (ID in a free range, fields: `uint32_t time_boot_ms`, `float temperature`, `uint8_t state`, `char[16] name`). Generate the Python library, send the message over UDP and receive it with a second script. Look at the order in which the fields landed on the wire, and check CRC_EXTRA with the function from step 2.

### Step 4. Losses from seq
Run `fake_vehicle.py --loss 0.2` and write a receiver that computes the HEARTBEAT/PARAM_VALUE loss percentage from seq. Compare it with the configured 20 %.

The lab is passed when the `tests/test_protocol.py` tests pass, and you have the hand-marked frame, a generated dialect with a received message, and a loss counter.

## diagnostics
- **Symptom:** heartbeat comes through, but one particular message doesn't arrive
  - Possible cause: different message definitions → CRC_EXTRA mismatch, frame dropped.
  - What to do: compare CRC_EXTRA in both libraries; rebuild all sides from the same XML.
- **Symptom:** your own parser loses some COMMAND_LONG/SET_POSITION_TARGET
  - Possible cause: a len == sizeof(struct) check, while MAVLink 2 truncated the zeros.
  - What to do: pad the payload with zeros to the full size.
- **Symptom:** after enabling signing, QGC doesn't connect
  - Possible cause: the GCS doesn't have the key, and the channel doesn't accept unsigned packets.
  - What to do: enter the same key in the GCS; temporarily allow unsigned packets over USB.
- **Symptom:** the loss counter shows 50 % with a good radio link
  - Possible cause: two senders with the same sysid/compid on one channel.
  - What to do: a unique compid for each script/component.

## references
- MAVLink — Serialization (packet format, CRC_EXTRA, truncation) | https://mavlink.io/en/guide/serialization.html | primary | A
- MAVLink — Message signing | https://mavlink.io/en/guide/message_signing.html | primary | A
- MAVLink — Dialects and mavgen | https://mavlink.io/en/guide/xml_schema.html | primary | A
- pymavlink — generator and Python dialects (source) | https://github.com/ArduPilot/pymavlink | primary | A
- ArduPilot — MAVLink2 signing (setup) | https://ardupilot.org/planner/docs/common-MAVLink2-signing.html | primary | A

## checklist
- I mark up a MAVLink 2 frame byte by byte and know what goes into the CRC
- I explain why CRC_EXTRA is needed and what symptom diverging dialects produce
- I account for payload zero truncation when parsing
- I know the field order on the wire and the role of extension fields
- I build my own dialect with mavgen and verify it on both sides
- I understand what signing protects against and what it doesn't
