"""Python reference for the CRSF telemetry parser: encoder (to build fixtures) and decoder.
Field layouts and units follow the TBS CRSF specification; the C parser in firmware/ must agree with it."""
from __future__ import annotations

import math
import struct

SYNC = 0xC8


def crc8(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0xD5) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def frame(ftype: int, payload: bytes, sync: int = SYNC) -> bytes:
    body = bytes([ftype]) + payload
    return bytes([sync, len(body) + 1]) + body + bytes([crc8(body)])


def battery(v: float, a: float, mah: int, pct: int) -> bytes:
    return frame(0x08, struct.pack(">hh", round(v * 10), round(a * 10)) + mah.to_bytes(3, "big") + bytes([pct]))


def link_stats(rssi1: int, rssi2: int, lq: int, snr: int, profile: int = 2, power: int = 3, drssi: int = -60, dlq: int = 100, dsnr: int = 8) -> bytes:
    return frame(0x14, struct.pack(">BBBbBBBBBb", -rssi1, -rssi2, lq, snr, 0, profile, power, -drssi, dlq, dsnr))


def attitude(pitch_deg: float, roll_deg: float, yaw_deg: float) -> bytes:
    r = lambda d: round(math.radians(d) / 1e-4)
    return frame(0x1E, struct.pack(">hhh", r(pitch_deg), r(roll_deg), r(yaw_deg)))


def gps(lat: float, lon: float, kmh: float, hdg: float, alt_m: int, sats: int) -> bytes:
    return frame(0x02, struct.pack(">iiHHHB", round(lat * 1e7), round(lon * 1e7), round(kmh * 10), round(hdg * 100), alt_m + 1000, sats))


def decode_stream(data: bytes) -> list[dict]:
    """Same state machine as the C parser; returns decoded frames in order."""
    out, i, n = [], 0, len(data)
    while i < n:
        if data[i] not in (0xC8, 0x00, 0xEA, 0xEE):
            i += 1; continue
        if i + 1 >= n: break
        ln = data[i + 1]
        if ln < 2 or ln > 62:
            i += 1; continue
        if i + 2 + ln > n: break
        body, c = data[i + 2:i + 1 + ln], data[i + 1 + ln]
        if crc8(body) != c:
            i += 2 + ln; continue      # like the C parser: a bad frame is consumed whole
        t, pl = body[0], body[1:]
        if t == 0x08 and len(pl) >= 8:
            v, a = struct.unpack(">hh", pl[:4])
            out.append({"type": 8, "v": v / 10, "a": a / 10, "mah": int.from_bytes(pl[4:7], "big"), "pct": pl[7]})
        elif t == 0x14 and len(pl) >= 10:
            out.append({"type": 20, "rssi1": -pl[0], "rssi2": -pl[1], "lq": pl[2], "snr": struct.unpack(">b", pl[3:4])[0], "dlq": pl[8]})
        elif t == 0x1E and len(pl) >= 6:
            p, r, y = (math.degrees(x * 1e-4) for x in struct.unpack(">hhh", pl[:6]))
            out.append({"type": 30, "pitch": p, "roll": r, "yaw": y})
        elif t == 0x02 and len(pl) >= 15:
            la, lo, _, _, alt, s = struct.unpack(">iiHHHB", pl[:15])
            out.append({"type": 2, "lat": la / 1e7, "lon": lo / 1e7, "alt": alt - 1000, "sats": s})
        else:
            out.append({"type": t})
        i += 2 + ln
    return out
