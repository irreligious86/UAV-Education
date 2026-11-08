#!/usr/bin/env python3
"""Decode a raw MAVLink 2 frame byte by byte, without pymavlink's parser.

  python decode_frame.py fd09000001010000000000000000020300030300
  python decode_frame.py --hex-file capture.txt

Prints the header fields, verifies the CRC against CRC_EXTRA from the dialect, and unpacks
the payload with the message's struct format taken from pymavlink's generated dialect.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mavlink_crc import frame_crc  # noqa: E402

from pymavlink.dialects.v20 import ardupilotmega as mav  # noqa: E402


def decode(frame: bytes) -> dict:
    if frame[0] != 0xFD:
        raise ValueError(f"not a MAVLink 2 frame (STX {frame[0]:#04x})")
    length, incompat, compat, seq, sysid, compid = frame[1:7]
    msgid = frame[7] | (frame[8] << 8) | (frame[9] << 16)
    payload = frame[10:10 + length]
    crc_rx = frame[10 + length] | (frame[11 + length] << 8)
    signed = bool(incompat & 0x01)
    cls = mav.mavlink_map.get(msgid)
    out = {"len": length, "incompat_flags": incompat, "compat_flags": compat, "seq": seq, "sysid": sysid,
           "compid": compid, "msgid": msgid, "name": cls.msgname if cls else None, "signed": signed, "crc_rx": crc_rx}
    if cls is None:
        out["crc_ok"] = None
        return out
    out["crc_ok"] = frame_crc(frame, cls.crc_extra) == crc_rx
    # MAVLink 2 trims trailing zero bytes of the payload: pad back to the full struct size
    unpacker = cls.unpacker                      # struct.Struct with the wire format of the message
    padded = payload + b"\x00" * (unpacker.size - len(payload))
    values = list(unpacker.unpack(padded))
    # arrays are flattened in the struct: regroup them by array_lengths
    fields, i = {}, 0
    for name, alen in zip(cls.ordered_fieldnames, cls.array_lengths):
        if alen and cls.fieldtypes[cls.fieldnames.index(name)] != "char":
            fields[name] = tuple(values[i:i + alen]); i += alen
        else:
            fields[name] = values[i]; i += 1
    out["fields"] = fields
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hex", nargs="?", help="frame as hex string")
    ap.add_argument("--hex-file", help="file with one hex frame per line")
    a = ap.parse_args()
    frames = [a.hex] if a.hex else [ln.strip() for ln in Path(a.hex_file).read_text().splitlines() if ln.strip()]
    for hx in frames:
        d = decode(bytes.fromhex(hx.replace(" ", "")))
        print(f"{d['name'] or '?'} (id {d['msgid']}) seq={d['seq']} sys={d['sysid']} comp={d['compid']} len={d['len']} "
              f"signed={d['signed']} crc={'ok' if d['crc_ok'] else 'BAD' if d['crc_ok'] is False else 'unknown msg'}")
        for k, v in d.get("fields", {}).items():
            print(f"    {k} = {v}")


if __name__ == "__main__":
    main()
