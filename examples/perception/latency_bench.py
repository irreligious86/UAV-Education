#!/usr/bin/env python3
"""Profile an inference function the way an on-board budget needs it: warm-up, percentiles, budget verdict.

  python latency_bench.py --size 320 --runs 200 --budget-ms 50

Without a model at hand the default workload is a numpy convolution stack of comparable shape; pass
your own callable via `bench(fn, ...)` in Python (ONNX Runtime, OpenCV DNN, TFLite...).
"""
from __future__ import annotations

import argparse
import statistics
import time

import numpy as np


def percentile(sorted_vals: list[float], q: float) -> float:
    """Linear-interpolated percentile of an already sorted list, q in [0, 100]."""
    if not sorted_vals:
        raise ValueError("empty")
    k = (len(sorted_vals) - 1) * q / 100.0
    lo, hi = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def summarize(samples_ms: list[float], budget_ms: float) -> dict:
    s = sorted(samples_ms)
    p50, p95, p99 = percentile(s, 50), percentile(s, 95), percentile(s, 99)
    return {"n": len(s), "mean": statistics.fmean(s), "p50": p50, "p95": p95, "p99": p99, "max": s[-1],
            "fps_p50": 1000.0 / p50 if p50 > 0 else float("inf"), "budget_ms": budget_ms,
            "ok": p99 <= budget_ms, "over_budget_frac": sum(1 for x in s if x > budget_ms) / len(s)}


def bench(fn, arg, runs: int = 100, warmup: int = 10) -> list[float]:
    for _ in range(warmup):
        fn(arg)
    out = []
    for _ in range(runs):
        t0 = time.perf_counter()
        fn(arg)
        out.append((time.perf_counter() - t0) * 1000.0)
    return out


def toy_model(size: int):
    rng = np.random.default_rng(0)
    w = [rng.standard_normal((16, 16)).astype(np.float32) for _ in range(4)]

    def run(img):
        x = img
        for k in w:
            x = np.maximum(x @ np.tile(k, (x.shape[1] // 16, x.shape[1] // 16))[: x.shape[1], : x.shape[1]], 0) * 1e-3
        return x
    return run


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--size", type=int, default=320)
    ap.add_argument("--runs", type=int, default=100)
    ap.add_argument("--budget-ms", type=float, default=50.0)
    a = ap.parse_args()
    img = np.random.default_rng(1).standard_normal((a.size, a.size)).astype(np.float32)
    r = summarize(bench(toy_model(a.size), img, a.runs), a.budget_ms)
    print(" ".join(f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}" for k, v in r.items()))


if __name__ == "__main__":
    main()
