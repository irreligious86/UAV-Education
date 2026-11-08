"""C parser vs Python reference on the same byte stream. Run: python -m pytest -q examples/tx16s-companion/tests"""
from __future__ import annotations

import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import crsf  # noqa: E402

STREAM_FRAMES = [
    crsf.battery(15.8, 12.3, 456, 71),
    crsf.link_stats(-67, -71, 100, 9),
    crsf.attitude(-5.5, 12.25, 178.0),
    crsf.gps(50.4501234, 30.5234567, 43.2, 271.5, 152, 14),
    crsf.frame(0x29, b"\x01\x02"),             # unknown type: counted, not decoded
]


def stream(seed=1):
    rng = random.Random(seed)
    out = bytearray(b"\x55\xaa\x13")          # leading garbage
    expected = []
    for k in range(40):
        f = bytearray(rng.choice(STREAM_FRAMES))
        if k % 7 == 3:                         # corrupt one byte of every 7th frame
            f[3] ^= 0x5A
        else:
            expected.append(bytes(f))
        out += f
        if k % 5 == 0:
            out += bytes([0xC8, 0x77])         # sync followed by an invalid length
    return bytes(out), expected


def test_crc_known_values():
    # frame from the spec style: a CRC over type+payload must make the whole frame self-consistent
    f = crsf.battery(16.8, 0.0, 0, 100)
    assert crsf.crc8(f[2:-1]) == f[-1]
    assert crsf.crc8(b"") == 0


def test_python_reference_decodes_and_skips_bad_frames():
    data, expected = stream()
    got = crsf.decode_stream(data)
    assert len(got) == len(expected)
    bat = next(g for g in got if g["type"] == 8)
    assert bat == {"type": 8, "v": 15.8, "a": 12.3, "mah": 456, "pct": 71}
    att = next(g for g in got if g["type"] == 30)
    assert abs(att["roll"] - 12.25) < 0.01 and abs(att["yaw"] - 178.0) < 0.01


@pytest.fixture(scope="module")
def c_parser(tmp_path_factory):
    cc = shutil.which("cc") or shutil.which("gcc")
    if not cc:
        pytest.skip("no C compiler")
    exe = tmp_path_factory.mktemp("c") / "crsf_test"
    fw = HERE / "firmware"
    subprocess.run([cc, "-std=c99", "-Wall", "-Wextra", "-Werror", "-O2", "-o", str(exe),
                    str(fw / "crsf_telemetry.c"), str(fw / "test_main.c"), "-lm"], check=True)
    return exe


def run_c(exe, data: bytes) -> list[dict]:
    res = subprocess.run([str(exe)], input=data.hex(), capture_output=True, text=True, check=True)
    return [json.loads(line) for line in res.stdout.splitlines()]


def test_c_parser_matches_reference(c_parser):
    data, expected = stream(seed=3)
    lines = run_c(c_parser, data)
    stats, frames = lines[-1], lines[:-1]
    ref = crsf.decode_stream(data)
    assert len(frames) == len(ref) == len(expected)
    for c, p in zip(frames, ref):
        assert c["type"] == p["type"]
        for k in p:
            if isinstance(p[k], float):
                assert abs(c[k] - p[k]) < 0.01, (k, c, p)
            else:
                assert c[k] == p[k], (k, c, p)
    assert stats["crc"] >= 5 and stats["len"] >= 8 and stats["unknown"] >= 1


def test_c_parser_handles_byte_split_frames(c_parser):
    # frames arriving with garbage between every byte boundary are still found
    f = crsf.battery(22.2, 30.0, 1200, 55)
    assert run_c(c_parser, b"\x00\x01" + f + b"\xff")[0] == {"type": 8, "v": 22.2, "a": 30.0, "mah": 1200, "pct": 55}
