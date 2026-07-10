"""
Metrics collection for Atomic Search.

Provides performance and usage metrics.
"""

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class MetricPoint:
    """Single metric data point."""
    value: float
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """Collects and stores metrics."""

    def __init__(self):
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._timers: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.RLock()
        self._start_time = time.time()

    def increment(self, name: str, value: float = 1, labels: Dict[str, str] = None):
        """Increment a counter."""
        with self._lock:
            key = self._make_key(name, labels)
            self._counters[key] += value

    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """Set a gauge value."""
        with self._lock:
            key = self._make_key(name, labels)
            self._gauges[key] = value

    def observe(self, name: str, value: float, labels: Dict[str, str] = None):
        """Observe a histogram value."""
        with self._lock:
            key = self._make_key(name, labels)
            self._histograms[key].append(value)

            # Keep last 1000 values
            if len(self._histograms[key]) > 1000:
                self._histograms[key] = self._histograms[key][-1000:]

    def timing(self, name: str, duration_ms: float, labels: Dict[str, str] = None):
        """Record timing information."""
        with self._lock:
            key = self._make_key(name, labels)
            self._timers[key].append(duration_ms)

            if len(self._timers[key]) > 1000:
                self._timers[key] = self._timers[key][-1000:]

    def start_timer(self, name: str, labels: Dict[str, str] = None) -> float:
        """Start a timer."""
        return time.time()

    def stop_timer(self, name: str, start_time: float, labels: Dict[str, str] = None):
        """Stop a timer and record duration."""
        duration_ms = (time.time() - start_time) * 1000
        self.timing(name, duration_ms, labels)

    def get_counter(self, name: str, labels: Dict[str, str] = None) -> float:
        """Get counter value."""
        with self._lock:
            key = self._make_key(name, labels)
            return self._counters.get(key, 0)

    def get_gauge(self, name: str, labels: Dict[str, str] = None) -> Optional[float]:
        """Get gauge value."""
        with self._lock:
            key = self._make_key(name, labels)
            return self._gauges.get(key)

    def get_histogram_stats(self, name: str, labels: Dict[str, str] = None) -> Dict:
        """Get histogram statistics."""
        with self._lock:
            key = self._make_key(name, labels)
            values = self._histograms.get(key, [])

            if not values:
                return {}

            sorted_values = sorted(values)
            n = len(sorted_values)

            return {
                "count": n,
                "sum": sum(values),
                "mean": sum(values) / n,
                "min": min(values),
                "max": max(values),
                "p50": sorted_values[n // 2],
                "p90": sorted_values[int(n * 0.9)] if n > 1 else sorted_values[0],
                "p95": sorted_values[int(n * 0.95)] if n > 1 else sorted_values[0],
                "p99": sorted_values[int(n * 0.99)] if n > 1 else sorted_values[0],
            }

    def get_timer_stats(self, name: str, labels: Dict[str, str] = None) -> Dict:
        """Get timer statistics."""
        return self.get_histogram_stats(name, labels)

    def get_all_metrics(self) -> Dict:
        """Get all metrics."""
        with self._lock:
            uptime = time.time() - self._start_time

            return {
                "uptime_seconds": uptime,
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    k: self.get_histogram_stats("", {"__internal__": k})["__internal__"]
                    for k in self._histograms.keys()
                } if False else {},
                "timers": {
                    k: self.get_timer_stats("", {"__internal__": k})
                    for k in self._timers.keys()
                },
            }

    def reset(self):
        """Reset all metrics."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._timers.clear()

    def _make_key(self, name: str, labels: Dict[str, str] = None) -> str:
        """Create metric key from name and labels."""
        if not labels:
            return name

        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"


class RequestMetrics:
    """Request-specific metrics."""

    def __init__(self):
        self.collector = MetricsCollector()

    def record_request(self, endpoint: str, method: str, status: int, duration_ms: float):
        """Record a request."""
        labels = {"endpoint": endpoint, "method": method, "status": str(status)}
        self.collector.increment("requests_total", labels=labels)
        self.collector.timing("request_duration_ms", duration_ms, labels=labels)

    def record_search(self, query: str, engine: str, results_count: int, duration_ms: float):
        """Record a search request."""
        self.collector.increment("searches_total", labels={"engine": engine})
        self.collector.observe("search_results_count", results_count, labels={"engine": engine})
        self.collector.timing("search_duration_ms", duration_ms, labels={"engine": engine})

    def record_error(self, error_type: str, endpoint: str):
        """Record an error."""
        self.collector.increment("errors_total", labels={
            "type": error_type,
            "endpoint": endpoint
        })

    def record_cache_hit(self, hit: bool):
        """Record cache hit/miss."""
        self.collector.increment("cache_hits" if hit else "cache_misses")

    def get_summary(self) -> Dict:
        """Get metrics summary."""
        return {
            "requests_total": self.collector.get_counter("requests_total"),
            "searches_total": self.collector.get_counter("searches_total"),
            "errors_total": self.collector.get_counter("errors_total"),
            "cache_hit_rate": self._calculate_cache_hit_rate(),
            "search_stats": self.collector.get_timer_stats("search_duration_ms"),
        }

    def _calculate_cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        hits = self.collector.get_counter("cache_hits")
        misses = self.collector.get_counter("cache_misses")
        total = hits + misses

        return (hits / total * 100) if total > 0 else 0


# Global metrics collector
metrics = MetricsCollector()
request_metrics = RequestMetrics()
