"""Uplink scheduler for a MAVLink link over a cellular tunnel — project #9 starter.

Runs on the companion between the autopilot serial port and the WireGuard tunnel (in place of, or behind,
mavlink-router). Three ideas, each testable without a network:

1. Priority: commands, mission and parameter traffic and HEARTBEAT go before bulk telemetry.
2. Budget: a token bucket limits uplink bytes/s; telemetry that does not fit is dropped *by stream*,
   keeping the newest sample of each message type (a stale ATTITUDE is worthless, a lost COMMAND_ACK is not).
3. Adaptation: the telemetry share of the budget follows measured link quality (loss, RTT), so a bad
   cell lowers the telemetry rate instead of drowning the commands.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# MAVLink common message ids
HEARTBEAT, PARAM_VALUE, COMMAND_ACK, STATUSTEXT = 0, 22, 77, 253
MISSION_IDS = {39, 40, 41, 43, 44, 45, 47, 51, 73}          # MISSION_* incl. ITEM_INT, REQUEST_INT, ACK
CONTROL = {HEARTBEAT, PARAM_VALUE, COMMAND_ACK, STATUSTEXT, 23, 76} | MISSION_IDS   # 23 PARAM_SET, 76 COMMAND_LONG


def priority(msgid: int) -> int:
    return 0 if msgid in CONTROL else 1


@dataclass
class TokenBucket:
    rate: float                 # bytes/s
    burst: float                # bytes
    tokens: float = 0.0
    t: float = 0.0

    def refill(self, now: float) -> None:
        self.tokens = min(self.burst, self.tokens + (now - self.t) * self.rate)
        self.t = now

    def take(self, n: int) -> bool:
        if self.tokens >= n:
            self.tokens -= n
            return True
        return False


@dataclass
class LinkQuality:
    """EWMA of loss and RTT from the heartbeat/ping exchange with the GCS side."""
    loss: float = 0.0
    rtt: float = 0.1
    alpha: float = 0.2

    def update(self, lost: bool, rtt: float | None) -> None:
        self.loss = (1 - self.alpha) * self.loss + self.alpha * (1.0 if lost else 0.0)
        if rtt is not None:
            self.rtt = (1 - self.alpha) * self.rtt + self.alpha * rtt

    def telemetry_share(self) -> float:
        """Fraction of the budget telemetry may use: 0.8 on a good link down to 0.2 on a bad one."""
        bad = min(1.0, max(self.loss / 0.3, (self.rtt - 0.15) / 0.6, 0.0))
        return 0.8 - 0.6 * bad


@dataclass
class Scheduler:
    bucket: TokenBucket
    quality: LinkQuality = field(default_factory=LinkQuality)
    control: list = field(default_factory=list)              # FIFO, never dropped
    telemetry: dict = field(default_factory=dict)            # msgid -> newest frame (coalescing)
    dropped: dict = field(default_factory=dict)

    def push(self, msgid: int, frame: bytes) -> None:
        if priority(msgid) == 0:
            self.control.append(frame)
        else:
            if msgid in self.telemetry:
                self.dropped[msgid] = self.dropped.get(msgid, 0) + 1
            self.telemetry[msgid] = frame

    def pop_ready(self, now: float) -> list[bytes]:
        """Frames allowed onto the tunnel now: all control that fits, then telemetry within its share."""
        self.bucket.refill(now)
        out = []
        while self.control and self.bucket.take(len(self.control[0])):
            out.append(self.control.pop(0))
        reserve = self.bucket.burst * (1 - self.quality.telemetry_share())   # keep headroom for control
        for msgid in sorted(self.telemetry):
            f = self.telemetry[msgid]
            if self.bucket.tokens - len(f) >= reserve and self.bucket.take(len(f)):
                out.append(f)
                del self.telemetry[msgid]
        return out


class Reconnector:
    """Exponential backoff with a cap for re-establishing the tunnel/UDP socket; reset on success."""
    def __init__(self, base: float = 0.5, cap: float = 8.0):
        self.base, self.cap, self.attempt, self.next_at = base, cap, 0, 0.0

    def due(self, now: float) -> bool:
        return now >= self.next_at

    def failed(self, now: float) -> None:
        self.next_at = now + min(self.cap, self.base * 2 ** self.attempt)
        self.attempt += 1

    def ok(self) -> None:
        self.attempt, self.next_at = 0, 0.0
