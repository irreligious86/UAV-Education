"""Ingest service core — project #2 starter.

handle(topic, payload) validates, de-duplicates by (id, seq) (QoS 1 delivers at least once, the backlog may
repeat), checks that the topic matches the id inside the message, and hands rows to a sink
(InfluxDB/TimescaleDB writer in the real service, a list in tests). Alerts are evaluated per vehicle.
"""
from __future__ import annotations

import schema

ALERT_BAT_PCT = 25
ALERT_STALE_S = 10.0


class Ingest:
    def __init__(self, sink):
        self.sink = sink
        self.seen: dict[str, set[int]] = {}
        self.last_rx: dict[str, float] = {}
        self.last: dict[str, dict] = {}
        self.rejected: dict[str, int] = {}
        self.duplicates = 0

    def handle(self, topic: str, payload: bytes, now: float) -> None:
        m, err = schema.validate(payload)
        parts = topic.split("/")
        if m is None or len(parts) != 3 or parts[0] != "fleet" or parts[2] != "telem" or parts[1] != m["id"]:
            reason = err or "topic/id mismatch"
            self.rejected[reason] = self.rejected.get(reason, 0) + 1
            return
        s = self.seen.setdefault(m["id"], set())
        if m["seq"] in s:
            self.duplicates += 1
            return
        s.add(m["seq"])
        self.sink.append(m)
        self.last_rx[m["id"]] = now
        if m["t"] >= self.last.get(m["id"], {}).get("t", -1):
            self.last[m["id"]] = m

    def alerts(self, now: float) -> list[tuple[str, str]]:
        out = []
        for vid, rx in self.last_rx.items():
            if now - rx > ALERT_STALE_S:
                out.append((vid, "no data"))
                continue
            m = self.last[vid]
            if 0 <= m["bat_pct"] < ALERT_BAT_PCT:
                out.append((vid, "battery low"))
            if not m["ekf_ok"]:
                out.append((vid, "ekf"))
        return sorted(out)
