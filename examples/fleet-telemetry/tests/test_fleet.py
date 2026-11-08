"""Run: python -m pytest -q examples/fleet-telemetry/tests"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ingest  # noqa: E402
import publisher  # noqa: E402
import schema  # noqa: E402


class FakeLink:
    """Broker path that can be down for given time windows and duplicates some deliveries (QoS 1)."""
    def __init__(self, ing, clock, down=(), dup=0.0, seed=0):
        self.ing, self.clock, self.down, self.dup = ing, clock, down, dup
        self.rng = random.Random(seed)

    def publish(self, topic, payload):
        t = self.clock[0]
        if any(a <= t < b for a, b in self.down):
            return False
        self.ing.handle(topic, payload, t)
        if self.rng.random() < self.dup:
            self.ing.handle(topic, payload, t)
        return True


def sample(t, k=0, bat=90, ekf=True):
    return {"t": float(t), "lat": 50.45 + k * 1e-3, "lon": 30.52, "alt": 40.0, "bat_v": 15.8, "bat_pct": bat,
            "mode": "AUTO", "ekf_ok": ekf, "gs": 8.0, "sats": 17}


def run(minutes=10, rate=2, down=(), n=3, dup=0.0):
    rows, clock = [], [0.0]
    ing = ingest.Ingest(rows)
    pubs = [publisher.Publisher(f"uav{k}", FakeLink(ing, clock, down, dup, seed=k)) for k in range(n)]
    steps = int(minutes * 60 * rate)
    for i in range(steps):
        clock[0] = i / rate
        for k, p in enumerate(pubs):
            p.tick(sample(clock[0], k))
    for _ in range(200):               # let backlogs drain after the run
        clock[0] += 1 / rate
        for k, p in enumerate(pubs):
            if p.buf:
                p.tick(sample(clock[0], k))
    return ing, pubs, rows


def test_three_vehicles_ten_minutes_no_loss_with_duplicates():
    ing, pubs, rows = run(dup=0.05)
    for p in pubs:
        got = sorted(r["seq"] for r in rows if r["id"] == p.id)
        assert got == list(range(p.seq))          # every seq exactly once
    assert ing.duplicates > 0 and not ing.rejected


def test_sixty_second_outage_is_backfilled_in_order():
    ing, pubs, rows = run(down=[(120, 180)])
    for p in pubs:
        seqs = [r["seq"] for r in rows if r["id"] == p.id]
        assert sorted(seqs) == list(range(p.seq)) and seqs == sorted(seqs)   # nothing lost, order kept
        assert p.thinned == 0


def test_buffer_overflow_thins_old_samples_but_keeps_recent():
    rows, clock = [], [0.0]
    ing = ingest.Ingest(rows)
    p = publisher.Publisher("uav0", FakeLink(ing, clock, down=[(0, 100)]), max_buffer=50)
    for i in range(150):
        clock[0] = i
        p.tick(sample(i))
    assert p.thinned > 0
    ts = [r["t"] for r in rows]
    assert 99.0 in ts and len(set(range(80, 100)) & set(int(t) for t in ts)) == 20   # last 20 s intact


def test_schema_versioning_and_garbage():
    ok = schema.encode({**sample(1), "id": "a", "seq": 0})
    m, err = schema.validate(ok)
    assert err is None and m["v"] == 1
    extra = json.loads(ok); extra["new_field"] = 1
    assert schema.validate(json.dumps(extra).encode())[1] is None          # additions do not break ingest
    v2 = json.loads(ok); v2["v"] = 2
    assert "version" in schema.validate(json.dumps(v2).encode())[1]
    for bad in (b"\xff\xfe", b"[1,2]", b'{"v":1}', ok.replace(b'"lat":50.45', b'"lat":95.0')):
        assert schema.validate(bad)[0] is None
    rows = []; ing = ingest.Ingest(rows)
    ing.handle("fleet/b/telem", ok, 0)                                      # topic says b, message says a
    assert not rows and ing.rejected == {"topic/id mismatch": 1}


def test_alerts():
    rows = []; ing = ingest.Ingest(rows)
    for vid, s in (("a", sample(0)), ("b", sample(0, bat=12)), ("c", sample(0, ekf=False))):
        ing.handle(f"fleet/{vid}/telem", schema.encode({**s, "id": vid, "seq": 0}), 0)
    ing.handle("fleet/a/telem", schema.encode({**sample(15), "id": "a", "seq": 1}), 15)
    assert ing.alerts(15) == [("b", "no data"), ("c", "no data")]
    assert ing.alerts(5) == [("b", "battery low"), ("c", "ekf")]


def test_traffic_per_vehicle_hour_is_documented_scale():
    _, pubs, _ = run(minutes=1, rate=2, n=1)
    per_hour_mb = pubs[0].sent_bytes * 60 / 1e6
    assert 0.5 < per_hour_mb < 2.0          # ≈1 MB/h at 2 Hz JSON before MQTT/TLS overhead
