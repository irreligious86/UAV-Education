"""mav-protocol lab: hand-written CRC and frame decoder agree with pymavlink."""
from pymavlink.dialects.v20 import ardupilotmega as mav

from decode_frame import decode
from mavlink_crc import crc_extra_from_fields, frame_crc, x25_crc


class _Buf:
    def write(self, b):
        pass


def make_frame(msg) -> bytes:
    m = mav.MAVLink(_Buf(), srcSystem=1, srcComponent=1)
    return bytes(msg.pack(m))


def test_x25_check_value():
    # CRC-16/MCRF4XX check value for "123456789"
    assert x25_crc(b"123456789") == 0x6F91


def test_crc_extra_matches_dialect():
    # messages without extension fields: CRC_EXTRA covers all of them (extensions are excluded by mavgen)
    for cls in (mav.MAVLink_heartbeat_message, mav.MAVLink_attitude_message, mav.MAVLink_command_long_message,
                mav.MAVLink_param_value_message, mav.MAVLink_global_position_int_message):
        fields = list(zip(cls.fieldtypes_ordered if hasattr(cls, "fieldtypes_ordered") else
                          [cls.fieldtypes[cls.fieldnames.index(n)] for n in cls.ordered_fieldnames], cls.ordered_fieldnames))
        # array types in pymavlink are given as base type + array_lengths
        fixed = []
        for (t, n) in fields:
            i = cls.fieldnames.index(n)
            alen = cls.array_lengths[cls.ordered_fieldnames.index(n)] if hasattr(cls, "array_lengths") else 0
            fixed.append((f"{t}[{alen}]" if alen else t, n))
        assert crc_extra_from_fields(cls.msgname, fixed) == cls.crc_extra, cls.msgname


def test_decode_attitude_frame():
    msg = mav.MAVLink_attitude_message(12345, 0.1, -0.2, 1.5, 0.01, 0.02, 0.03)
    frame = make_frame(msg)
    d = decode(frame)
    assert d["name"] == "ATTITUDE" and d["msgid"] == 30
    assert d["crc_ok"]
    assert d["fields"]["time_boot_ms"] == 12345
    assert abs(d["fields"]["yaw"] - 1.5) < 1e-6


def test_trailing_zero_truncation():
    # MAVLink 2 trims trailing zero bytes from the payload; the decoder must pad back
    msg = mav.MAVLink_command_long_message(1, 1, 400, 0, 1, 0, 0, 0, 0, 0, 0)
    frame = make_frame(msg)
    assert frame[1] < 33        # COMMAND_LONG payload is 33 bytes untruncated
    d = decode(frame)
    assert d["crc_ok"] and d["fields"]["command"] == 400 and d["fields"]["param1"] == 1.0


def test_corrupted_byte_fails_crc():
    frame = bytearray(make_frame(mav.MAVLink_attitude_message(1, 0, 0, 0, 0, 0, 0)))
    frame[12] ^= 0x40
    assert decode(bytes(frame))["crc_ok"] is False
    assert frame_crc(bytes(frame), mav.MAVLink_attitude_message.crc_extra) != frame[-2] | (frame[-1] << 8)
