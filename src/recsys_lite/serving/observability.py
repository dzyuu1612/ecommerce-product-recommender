"""Minimal in-process metrics, exported in Prometheus text-exposition format.

Standing in for the Prometheus + Pushgateway + Grafana stack: no external
process to run, but any real Prometheus server can still scrape
`/metrics` on this API directly if you point one at it.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, float] = defaultdict(float)
        self._latencies_ms: list[float] = []
        self._started_at = time.time()

    def inc(self, name: str, value: float = 1.0) -> None:
        with self._lock:
            self._counters[name] += value

    def observe_latency_ms(self, value: float) -> None:
        with self._lock:
            self._latencies_ms.append(value)
            if len(self._latencies_ms) > 2000:
                self._latencies_ms = self._latencies_ms[-1000:]

    def render_prometheus(self) -> str:
        with self._lock:
            lines = [f"# HELP recsys_lite_uptime_seconds process uptime",
                     "# TYPE recsys_lite_uptime_seconds gauge",
                     f"recsys_lite_uptime_seconds {time.time() - self._started_at:.2f}"]
            for name, value in sorted(self._counters.items()):
                lines.append(f"# TYPE {name} counter")
                lines.append(f"{name} {value}")
            if self._latencies_ms:
                sorted_lat = sorted(self._latencies_ms)
                p50 = sorted_lat[len(sorted_lat) // 2]
                p95 = sorted_lat[int(len(sorted_lat) * 0.95) - 1]
                lines.append("# TYPE recsys_lite_recommend_latency_ms_p50 gauge")
                lines.append(f"recsys_lite_recommend_latency_ms_p50 {p50:.2f}")
                lines.append("# TYPE recsys_lite_recommend_latency_ms_p95 gauge")
                lines.append(f"recsys_lite_recommend_latency_ms_p95 {p95:.2f}")
            return "\n".join(lines) + "\n"


METRICS = Metrics()
