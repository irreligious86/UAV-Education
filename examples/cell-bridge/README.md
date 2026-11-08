# Cellular bridge (project #9 starter)

The companion-side logic of a 4G/Wi-Fi link to the GCS that a VPN alone does not give you: command traffic
first, telemetry within a budget that follows link quality, and reconnection with backoff. Tested against a
simulated tunnel with loss, latency and an outage — no network, no root.

```bash
python -m pytest -q tests      # 4 tests: 20 % loss + 300 ms, telemetry share, coalescing, 30 s outage
```

| Piece | What it does |
|---|---|
| `priority()` | COMMAND_LONG/ACK, PARAM_*, MISSION_*, HEARTBEAT, STATUSTEXT — control, never dropped |
| `TokenBucket` | uplink bytes/s budget (cellular uplink is small and expensive) |
| `Scheduler` | control FIFO; telemetry coalesced per message id (newest wins); headroom kept for control |
| `LinkQuality` | EWMA of loss and RTT → telemetry share 0.8 … 0.2 |
| `Reconnector` | 0.5 → 8 s exponential backoff, reset on success |

Real deployment (course page "Проекты → 9"): WireGuard with `PersistentKeepalive` (NAT on cellular),
mavlink-router or this scheduler on the companion, `tc qdisc add dev wg0 root netem loss 20% delay 300ms`
for measurements, and the vehicle-side GCS failsafe (`FS_GCS_ENABLE`) verified in SITL — the bridge must
never be the only thing standing between a lost link and a safe action.
