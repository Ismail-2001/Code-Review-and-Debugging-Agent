"""Observability setup — Prometheus metrics, structured logging, tracing."""

from __future__ import annotations

import time
import os
from contextlib import contextmanager

try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

# ============================================================
# Metrics Definitions
# ============================================================

if PROMETHEUS_AVAILABLE:
    review_duration = Histogram(
        "codeguardian_review_duration_seconds",
        "Time to complete a review",
        ["status"],
        buckets=[10, 30, 60, 120, 300, 600, 1800],
    )

    findings_total = Counter(
        "codeguardian_findings_total",
        "Total findings by severity and category",
        ["severity", "category"],
    )

    llm_tokens_total = Counter(
        "codeguardian_llm_tokens_total",
        "Total LLM tokens used",
        ["model", "operation"],
    )

    llm_cost_total = Counter(
        "codeguardian_llm_cost_cents_total",
        "Total LLM cost in cents",
        ["model"],
    )

    active_reviews = Gauge(
        "codeguardian_active_reviews",
        "Number of reviews currently in progress",
    )

    agent_duration = Histogram(
        "codeguardian_agent_duration_seconds",
        "Time per agent execution",
        ["agent", "status"],
        buckets=[1, 5, 10, 30, 60, 120],
    )

    cache_hits = Counter(
        "codeguardian_cache_hits_total",
        "Cache hits by agent",
        ["agent"],
    )

    errors_total = Counter(
        "codeguardian_errors_total",
        "Errors by type",
        ["type"],
    )


# ============================================================
# Metrics API
# ============================================================

@contextmanager
def track_duration(metric_name: str, labels: dict | None = None):
    """Context manager to track operation duration."""
    start = time.monotonic()
    try:
        yield
    finally:
        elapsed = time.monotonic() - start
        _record_histogram(metric_name, elapsed, labels or {})


def record_finding(severity: str, category: str):
    """Record a finding for metrics."""
    if PROMETHEUS_AVAILABLE:
        findings_total.labels(severity=severity, category=category).inc()


def record_llm_usage(model: str, operation: str, tokens: int, cost_cents: float):
    """Record LLM token usage and cost."""
    if PROMETHEUS_AVAILABLE:
        llm_tokens_total.labels(model=model, operation=operation).inc(tokens)
        llm_cost_total.labels(model=model).inc(cost_cents)


def record_cache_hit(agent: str):
    """Record a cache hit."""
    if PROMETHEUS_AVAILABLE:
        cache_hits.labels(agent=agent).inc()


def record_error(error_type: str):
    """Record an error."""
    if PROMETHEUS_AVAILABLE:
        errors_total.labels(type=error_type).inc()


def metrics_endpoint():
    """Return Prometheus metrics in text format."""
    if PROMETHEUS_AVAILABLE:
        return generate_latest(REGISTRY)
    return "# Prometheus not available\n"


def _record_histogram(name: str, value: float, labels: dict):
    """Record a histogram metric."""
    if PROMETHEUS_AVAILABLE:
        if name == "agent_duration":
            agent = labels.get("agent", "unknown")
            status = labels.get("status", "unknown")
            agent_duration.labels(agent=agent, status=status).observe(value)


# ============================================================
# Structured Logging
# ============================================================

import logging
import json


class StructuredLogger:
    """JSON-structured logger for machine parsing."""

    def __init__(self, name: str = "codeguardian"):
        self.logger = logging.getLogger(name)

    def _log(self, level: str, message: str, **kwargs):
        extra = {
            "service": "codeguardian",
            "environment": os.getenv("ENVIRONMENT", "development"),
            **kwargs,
        }
        record = {"level": level, "message": message, "timestamp": time.time(), **extra}
        text = json.dumps(record, default=str)

        if level == "ERROR":
            self.logger.error(text)
        elif level == "WARN":
            self.logger.warning(text)
        elif level == "DEBUG":
            self.logger.debug(text)
        else:
            self.logger.info(text)

    def info(self, msg: str, **kwargs):
        self._log("INFO", msg, **kwargs)

    def error(self, msg: str, **kwargs):
        self._log("ERROR", msg, **kwargs)

    def warn(self, msg: str, **kwargs):
        self._log("WARN", msg, **kwargs)

    def debug(self, msg: str, **kwargs):
        self._log("DEBUG", msg, **kwargs)


logger = StructuredLogger()
