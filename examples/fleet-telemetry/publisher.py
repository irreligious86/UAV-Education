"""Companion-side publisher with a store-and-forward buffer — project #2 starter.

The transport is anything with publish(topic, payload) -> bool (True = broker accepted). A real one wraps
paho-mqtt (publish(...).is_published() after wait, or on_publish callbacks); tests use a fake that drops
the link. While the link is down samples go to a bounded buffer; on reconnect the backlog is sent oldest
first at a limited rate so the live stream is not starved. When the buffer is full, the oldest samples are
thinned (every second one dropped) instead of losing the most recent minutes.
"""
from __future__ import annotations

from collections import deque

import schema


class Publisher:
    def __init__(self, vehicle_id: str, transport, max_buffer: int = 3600, backlog_per_tick: int = 20):
        self.id, self.tx = vehicle_id, transport
        self.topic = f"fleet/{vehicle_id}/telem"
        self.buf: deque[bytes] = deque()
        self.max_buffer, self.backlog_per_tick = max_buffer, backlog_per_tick
        self.seq = 0
        self.sent_bytes = 0
        self.thinned = 0

    def _send(self, payload: bytes) -> bool:
        ok = self.tx.publish(self.topic, payload)
        if ok:
            self.sent_bytes += len(payload)
        return ok

    def _buffer(self, payload: bytes) -> None:
        if len(self.buf) >= self.max_buffer:
            kept = deque(p for i, p in enumerate(self.buf) if i % 2 == 0)
            self.thinned += len(self.buf) - len(kept)
            self.buf = kept
        self.buf.append(payload)

    def tick(self, sample: dict) -> None:
        """Call at the publish rate (1–5 Hz) with the latest vehicle state."""
        payload = schema.encode({**sample, "id": self.id, "seq": self.seq})
        self.seq += 1
        for _ in range(min(self.backlog_per_tick, len(self.buf))):   # backlog first, oldest first
            if not self._send(self.buf[0]):
                break
            self.buf.popleft()
        if self.buf or not self._send(payload):     # keep order: never overtake the backlog
            self._buffer(payload)
