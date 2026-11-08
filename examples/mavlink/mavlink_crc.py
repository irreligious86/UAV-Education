"""MAVLink checksum from scratch: CRC-16/MCRF4XX (X.25) plus CRC_EXTRA.

The point of this file is to be read, not reused: pymavlink has the same code in
`mavutil.x25crc`. Use it to decode a frame by hand in the `mav-protocol` lab.
"""
from __future__ import annotations


def x25_crc(data: bytes, crc: int = 0xFFFF) -> int:
    """CRC-16/MCRF4XX over `data`, continuing from `crc` (init 0xFFFF)."""
    for b in data:
        tmp = b ^ (crc & 0xFF)
        tmp = (tmp ^ (tmp << 4)) & 0xFF
        crc = ((crc >> 8) ^ (tmp << 8) ^ (tmp << 3) ^ (tmp >> 4)) & 0xFFFF
    return crc


def frame_crc(frame: bytes, crc_extra: int) -> int:
    """Checksum of a MAVLink 1 or 2 frame: everything after the STX byte up to (not including)
    the CRC itself, then one extra byte CRC_EXTRA from the message definition."""
    stx = frame[0]
    length = frame[1]
    header_len = 10 if stx == 0xFD else 6          # v2: len,incompat,compat,seq,sysid,compid,msgid(3) ; v1: len,seq,sysid,compid,msgid
    body = frame[1:header_len + length]
    return x25_crc(bytes([crc_extra]), x25_crc(body))


def crc_extra_from_fields(msg_name: str, fields: list[tuple[str, str]]) -> int:
    """CRC_EXTRA as mavgen computes it: CRC over "NAME " then "type name " per field (array
    length byte appended for arrays), folded to 8 bits. `fields` must be in *wire order*
    (sorted by type size, descending, extensions last) — pymavlink's `ordered_fieldnames`."""
    crc = x25_crc((msg_name + " ").encode())
    for ftype, fname in fields:
        base = ftype.split("[")[0]
        crc = x25_crc((base + " ").encode(), crc)
        crc = x25_crc((fname + " ").encode(), crc)
        if "[" in ftype:
            n = int(ftype[ftype.index("[") + 1:-1])
            crc = x25_crc(bytes([n]), crc)
    return (crc & 0xFF) ^ (crc >> 8)
