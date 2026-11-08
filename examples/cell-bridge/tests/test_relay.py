"""Run: python -m pytest -q examples/cell-bridge/tests

A discrete-time model of the tunnel: random loss, fixed latency and an outage window. The GCS retries a
COMMAND_LONG every 1.5 s until the COMMAND_ACK arrives (as the course's mav_client does).
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import relay  # noqa: E402

TELEM = {30: 36, 33: 36, 74: 28, 1: 39, 24: 50, 147: 54}     # ATTITUDE, GLOBAL_POSITION_INT, VFR_HUD, SYS_STATUS…


def simulate(loss=0.2, latency=0.3, rate_bps=6000, seconds=120, outage=None, seed=1, dt=0.02):
    rng = random.Random(seed)
    sch = relay.Scheduler(relay.TokenBucket(rate=rate_bps, burst=rate_bps * 0.25))
    in_flight, delivered = [], []              # (arrive_t, tag)
    cmds_sent, acked, cmd_latency = {}, {}, []
    tel_rx = 0
    t = 0.0
    next_cmd, cmd_id = 2.0, 0
    retry_at = {}
    while t < seconds:
        down = outage and outage[0] <= t < outage[1]
        # autopilot output: telemetry at 10–50 Hz each
        for mid, size in TELEM.items():
            if rng.random() < dt * 20:
                sch.push(mid, bytes(size))
        # a command reaches the vehicle -> ACK queued as control traffic
        for arr, tag in [x for x in in_flight if x[0] <= t and x[1][0] == "cmd"]:
            in_flight.remove((arr, tag))
            sch.push(relay.COMMAND_ACK, b"ACK" + tag[1].to_bytes(2, "little") + bytes(5))
        for f in sch.pop_ready(t):
            lost = down or rng.random() < loss
            sch.quality.update(lost, None if lost else 2 * latency)
            if not lost:
                in_flight.append((t + latency, ("up", f)))
        for arr, tag in [x for x in in_flight if x[0] <= t and x[1][0] == "up"]:
            in_flight.remove((arr, tag))
            f = tag[1]
            if f.startswith(b"ACK"):
                k = int.from_bytes(f[3:5], "little")
                if k not in acked:
                    acked[k] = t
                    cmd_latency.append(t - cmds_sent[k])
            else:
                tel_rx += 1
        # GCS: a new command every 10 s, retried every 1.5 s until ACKed (downlink has the same loss)
        if t >= next_cmd:
            cmds_sent[cmd_id] = t; retry_at[cmd_id] = t; cmd_id += 1; next_cmd += 10
        for k in cmds_sent:
            if k not in acked and t >= retry_at[k]:
                retry_at[k] = t + 1.5
                if not down and rng.random() >= loss:
                    in_flight.append((t + latency, ("cmd", k)))
        t += dt
    return sch, cmds_sent, acked, cmd_latency, tel_rx


def test_commands_get_through_at_20pct_loss_and_300ms():
    sch, sent, acked, lat, tel = simulate()
    assert set(acked) == set(sent) - {k for k, ts in sent.items() if ts > 115}
    assert tel > 0
    lat = [x for seed in range(1, 6) for x in simulate(seed=seed)[3]]
    first_try = sum(x < 0.7 for x in lat) / len(lat)     # 0.8 × 0.8 = 0.64 expected without retries
    assert 0.45 < first_try < 0.85 and max(lat) < 9.0   # retries, not queueing, set the tail


def test_bad_link_lowers_telemetry_share_not_control():
    good = relay.LinkQuality(); bad = relay.LinkQuality()
    for _ in range(50):
        good.update(False, 0.08); bad.update(True if _ % 3 == 0 else False, 0.6)
    assert good.telemetry_share() > 0.75 and bad.telemetry_share() < 0.35


def test_control_never_dropped_telemetry_coalesced():
    sch = relay.Scheduler(relay.TokenBucket(rate=100, burst=100))
    for i in range(20):
        sch.push(30, bytes([i]) * 36)                 # ATTITUDE flood
    sch.push(relay.COMMAND_ACK, bytes(10))
    assert len(sch.telemetry) == 1 and sch.dropped[30] == 19
    out = sch.pop_ready(1.0)
    assert out[0] == bytes(10)                        # control first
    assert out[-1] == bytes([19]) * 36 if len(out) > 1 else True   # newest attitude only


def test_outage_30s_recovers_and_reconnect_backoff():
    sch, sent, acked, lat, tel = simulate(loss=0.05, outage=(40, 70))
    during = [k for k, ts in sent.items() if 40 <= ts < 70]
    assert during and all(k in acked for k in during)               # retried until the link came back
    assert all(acked[k] >= 70 for k in during)
    r = relay.Reconnector()
    waits = []
    for i in range(7):
        r.failed(i); waits.append(r.next_at - i)
    assert waits == [0.5, 1, 2, 4, 8, 8, 8]
    r.ok(); assert r.due(0)
