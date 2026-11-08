"""Fleet telemetry message schema v1 — project #2 starter.

Topic: fleet/<vehicle_id>/telem   (QoS 1; retained "fleet/<id>/status" carries online/offline via MQTT last will)
Message: compact JSON, one object per sample. "v" is mandatory and comes first; unknown fields are ignored,
so a v1 ingest keeps working when publishers add fields (minor additions keep v=1; a breaking change bumps v).
"""
from __future__ import annotations

import json

VERSION = 1
REQUIRED = {           # field: (type, min, max)
    "v": (int, 1, 1),
    "id": (str, None, None),
    "seq": (int, 0, None),
    "t": (float, 0, None),          # vehicle UTC time, s
    "lat": (float, -90, 90), "lon": (float, -180, 180), "alt": (float, -500, 10000),
    "bat_v": (float, 0, 100), "bat_pct": (int, -1, 100),
    "mode": (str, None, None),
    "ekf_ok": (bool, None, None),
}
OPTIONAL = {"gs": (float, 0, 200), "rssi": (int, 0, 255), "sats": (int, 0, 64)}


def encode(sample: dict) -> bytes:
    msg = {"v": VERSION, **{k: sample[k] for k in REQUIRED if k != "v"}}
    msg.update({k: sample[k] for k in OPTIONAL if k in sample})
    return json.dumps(msg, separators=(",", ":")).encode()


def validate(raw: bytes) -> tuple[dict | None, str | None]:
    """Return (message, None) or (None, reason). Never raises on bad input: ingest must survive garbage."""
    try:
        m = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return None, "not json"
    if not isinstance(m, dict):
        return None, "not an object"
    if m.get("v") != VERSION:
        return None, f"unsupported version {m.get('v')!r}"
    for k, (typ, lo, hi) in {**REQUIRED, **{k: v for k, v in OPTIONAL.items() if k in m}}.items():
        if k not in m:
            return None, f"missing {k}"
        x = m[k]
        if typ is float and isinstance(x, int) and not isinstance(x, bool):
            x = float(x)
        if not isinstance(x, typ) or (typ is int and isinstance(x, bool)):
            return None, f"bad type {k}"
        if (lo is not None and x < lo) or (hi is not None and x > hi):
            return None, f"out of range {k}"
        m[k] = x
    return m, None
