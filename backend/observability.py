"""Request-scoped logging context and lightweight metrics."""

from __future__ import annotations

import contextvars
import logging
from typing import Any

import time

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id",
    default="-",
)

_metrics: dict[str, int] = {
    "audit_post_total": 0,
    "audit_post_cache_hit": 0,
    "audit_post_cache_miss": 0,
    "audit_report_get_hit": 0,
    "audit_report_get_miss": 0,
    "compare_report_get_hit": 0,
    "compare_report_get_miss": 0,
}

_timings_ms: dict[str, dict[str, float]] = {}


def metrics_snapshot() -> dict[str, Any]:
    return {
        **dict(_metrics),
        "timings_ms": {k: dict(v) for k, v in _timings_ms.items()},
    }


def inc_metric(key: str, n: int = 1) -> None:
    _metrics[key] = _metrics.get(key, 0) + n


def observe_timing(stage: str, duration_ms: float) -> None:
    d = _timings_ms.get(stage)
    if d is None:
        d = {"count": 0.0, "sum": 0.0, "max": 0.0}
        _timings_ms[stage] = d
    d["count"] += 1.0
    d["sum"] += float(duration_ms)
    d["max"] = max(d["max"], float(duration_ms))


class stage_timer:
    def __init__(self, stage: str):
        self.stage = stage
        self.t0 = 0.0

    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        observe_timing(self.stage, (time.perf_counter() - self.t0) * 1000.0)
        return False


class RequestIdLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


def configure_logging() -> None:
    root = logging.getLogger()
    if getattr(root, "_cd_audit_configured", False):
        return

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [request_id=%(request_id)s] %(name)s: %(message)s",
        ),
    )
    handler.addFilter(RequestIdLogFilter())
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    root._cd_audit_configured = True  # type: ignore[attr-defined]
