"""Prometheus metrics, structured logging, and performance tracking."""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager

# Prometheus metrics (lazy init — only import if prometheus_client available)
_metrics = None
_initialized = False


def _get_metrics():
    global _metrics, _initialized
    if _initialized:
        return _metrics
    _initialized = True
    try:
        from prometheus_client import Counter, Gauge, Histogram

        _metrics = {
            "review_duration": Histogram("codeguardian_review_duration_seconds", "Time per review", ["scope"]),
            "findings_total": Counter("codeguardian_findings_total", "Findings by severity", ["severity"]),
            "llm_tokens_total": Counter("codeguardian_llm_tokens_total", "LLM tokens used", ["provider", "model"]),
            "llm_cost_total": Counter("codeguardian_llm_cost_cents_total", "LLM cost in cents"),
            "active_reviews": Gauge("codeguardian_active_reviews", "Currently running reviews"),
            "agent_duration": Histogram("codeguardian_agent_duration_seconds", "Time per agent", ["agent"]),
            "cache_hits": Counter("codeguardian_cache_hits_total", "Cache hits by agent", ["agent"]),
            "errors_total": Counter("codeguardian_errors_total", "Errors by source", ["source"]),
        }
    except ImportError:
        _metrics = {}
    return _metrics


@contextmanager
def track_duration(metric_name: str, labels: dict | None = None):
    """Context manager to track operation duration via Prometheus."""
    m = _get_metrics()
    start = time.monotonic()
    try:
        yield
    finally:
        duration = time.monotonic() - start
        hist = m.get(metric_name)
        if hist:
            if labels:
                hist.labels(**labels).observe(duration)
            else:
                hist.observe(duration)


def increment(metric: str, label_values: dict | None = None, value: int = 1):
    """Increment a counter metric safely."""
    m = _get_metrics()
    c = m.get(metric)
    if c:
        if label_values:
            c.labels(**label_values).inc(value)
        else:
            c.inc(value)


def gauge_set(metric: str, value: float, labels: dict | None = None):
    """Set a gauge metric safely."""
    m = _get_metrics()
    g = m.get(metric)
    if g:
        if labels:
            g.labels(**labels).set(value)
        else:
            g.set(value)


class StructuredLogger:
    """Logger that outputs JSON-structured log records."""

    def __init__(self, name: str, level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"))
            self.logger.addHandler(handler)

    def _log(self, level: int, msg: str, **extra):
        extra_str = f" | {json.dumps(extra)}" if extra else ""
        self.logger.log(level, f"{msg}{extra_str}")

    def info(self, msg: str, **extra):
        self._log(logging.INFO, msg, **extra)

    def warning(self, msg: str, **extra):
        self._log(logging.WARNING, msg, **extra)

    def error(self, msg: str, **extra):
        self._log(logging.ERROR, msg, **extra)

    def debug(self, msg: str, **extra):
        self._log(logging.DEBUG, msg, **extra)
